"""
BL-231: Detector(および全ツールノード)の生成崩壊ループ検知・停止ガードの回帰テスト。

実 LLM は呼ばず、ストリーミング互換のモック OpenAI クライアントで `_query_AI_live` を駆動する。
モデルが「同一テキスト＋同一ツール呼び出し計画」を繰り返し返す状況を再現し、ガードが
MAX_TOOL_ITER(=50) まで burn せず早期に強制終了することを検証する（§17.1: リバートで失敗する）。

未知ツール名（TOOL_DISPATCH に存在しない）を使うことで、実 DB／実ツールハンドラの実行を回避しつつ、
tool_calls が存在するためループが継続する状況を作る。
"""

import inspect
import json
from types import SimpleNamespace

import pytest

import cela_main


# ---- モック OpenAI クライアント（ストリーミング互換） ----

def _chunks(content, plan):
    """content(文字列) と plan[(name, args_dict), ...] からストリーミングチャンク列を作る。

    plan が空なら tool_calls なしの最終回答（正常終了）とみなす。
    """
    if plan:
        chunks = []
        if content:
            chunks.append(SimpleNamespace(choices=[SimpleNamespace(
                delta=SimpleNamespace(reasoning=None, content=content, tool_calls=None),
                finish_reason=None)]))
        tc_deltas = [
            SimpleNamespace(
                index=i, id=f"call_{i}",
                function=SimpleNamespace(name=n, arguments=json.dumps(a, ensure_ascii=False)),
            )
            for i, (n, a) in enumerate(plan)
        ]
        chunks.append(SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(reasoning=None, content=None, tool_calls=tc_deltas),
            finish_reason="tool_calls")]))
        return chunks
    # 最終回答（tool_calls なし）: content は 1 チャンクのみ
    return [SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=content, tool_calls=None),
        finish_reason="stop")])]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeCompletions:
    def __init__(self, factory, counter):
        self._factory = factory
        self._counter = counter

    def create(self, **kwargs):
        self._counter[0] += 1
        n = self._counter[0]
        return _FakeStream(self._factory(n))


class _FakeClient:
    def __init__(self, factory):
        self._counter = [0]
        self.base_url = "http://fake"  # openrouter でないこと（extra_body スキップ）
        self.chat = SimpleNamespace(completions=_FakeCompletions(factory, self._counter))


DUMMY_TOOLS = [{"function": {"name": "loop_guard_test_tool"}}]


def _run(factory):
    cela_main._LAST_REPETITION_GUARD_TRIPPED = None
    client = _FakeClient(factory)
    result = cela_main._query_AI_live(
        messages=[{"role": "user", "content": "監査対象"}],
        client=client,
        model="fake",
        label="detector",
        tools=DUMMY_TOOLS,
        light_system_prompt=None,
        state=None,
    )
    return result, client._counter[0], cela_main._LAST_REPETITION_GUARD_TRIPPED


# ---- テスト ----

def test_bl231_guard_trips_on_repeated_identical_output():
    """同一 content＋同一 plan を繰り返すと WINDOW(=3) 回で強制終了し、50 往復しない。"""
    def factory(n):
        return _chunks("Let me do these calls.", [("loop_guard_test_tool", {})])

    result, create_calls, flag = _run(factory)

    # ガード発動により RuntimeError(非収束) を上げずに返ること
    assert isinstance(result, str)
    assert result == "Let me do these calls."
    # 早期停止: create は WINDOW 回（=3）のみ（50 往復していない）
    assert create_calls == cela_main._LOOP_GUARD_REPETITION_WINDOW
    # 可観測性フラグがセットされていること
    assert flag is not None
    assert flag["label"] == "detector"
    assert flag["iteration"] == cela_main._LOOP_GUARD_REPETITION_WINDOW


def test_bl231_guard_does_not_false_trip_on_healthy_loop():
    """内容が異なる 2 往復の後、tool_calls なしで正常終了するループでは発動しない。"""
    def factory(n):
        if n == 1:
            return _chunks("first distinct output", [("neg_tool_a", {})])
        elif n == 2:
            return _chunks("second distinct output", [("neg_tool_b", {"k": "v"})])
        return _chunks("final answer text", [])  # tool_calls なし → 正常終了

    result, create_calls, flag = _run(factory)

    assert result == "final answer text"
    assert flag is None  # ガードは発動していない
    assert create_calls == 3  # 正常な 3 往復（誤検知なし）


def test_bl231_guard_code_present_in_source():
    """§17.1 後段: ガード実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_LAST_REPETITION_GUARD_TRIPPED" in src
    assert "_bl231_combined_hash" in src
    assert "_LOOP_GUARD_REPETITION_WINDOW" in src
