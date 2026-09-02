"""
BL-287: ツール呼び出し引数の完全一致反復の専用検知（訂正ナッジ→無効なら強制終了）。

log/2026-08-27/1634で、Expertが同一web_searchクエリを8回連続で繰り返す生成崩壊を
起こし、BL-231の閾値10への引き上げ（同日の別対応）により検知が16イテレーションまで
遅れ、この崩壊が4回連続発生してrun全体のweb_search呼び出しの74%（59/80回）を空費した。

web_search等の外部APIはほぼ決定論的なため、同一引数の再呼び出しは原因（デコード崩壊か、
モデルの誤った再試行判断か）を問わず無価値と機械的に断定できる。自由文の言い直し
（BL-231本体、`_LOOP_GUARD_REPETITION_WINDOW`=10、進捗との区別が曖昧なため閾値を高く
取る）とは性質が異なるため、専用の閾値（`_TOOL_CALL_REPEAT_NUDGE_THRESHOLD`=3）と
専用の対応（即時強制終了ではなく、まず訂正ナッジをループへ注入して1回だけ自己修復の
機会を与え、それでも同一引数が続く場合のみ強制終了）を実装する。

[BL-231との数学的関係] ツールループはtool_callsが空の応答で即座に正常終了するため、
反復ウィンドウに入る全iterationは必ずtool_callsを持つ。`_bl231_combined_hash`
（テキスト+plan_sigの結合）がN回一致するなら、その部分文字列である`_bl231_plan_sig`も
必ずN回一致する。本閾値(3) < `_LOOP_GUARD_REPETITION_WINDOW`(10)であるため、本チェックは
既存のBL-231終了ロジックより常に先に発火する（tests/test_bl231_loop_guard.pyの
`test_bl231_guard_trips_on_repeated_identical_output`参照）。BL-231本体のコードは
変更せず、万一の保険としてそのまま残している。

実LLM API呼び出しは伴わない（`_query_AI_live`をモックのストリーミング互換クライアントで駆動）。
"""

import inspect
import json
from types import SimpleNamespace

import pytest

import cela_main


# ---- モック OpenAI クライアント（ストリーミング互換、渡されたkwargsを記録する） ----

def _chunks(content, plan):
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
    return [SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=content, tool_calls=None),
        finish_reason="stop")])]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeCompletions:
    def __init__(self, factory, counter, captured_kwargs):
        self._factory = factory
        self._counter = counter
        self._captured_kwargs = captured_kwargs

    def create(self, **kwargs):
        self._counter[0] += 1
        n = self._counter[0]
        # [BL-287] kwargs["messages"]はloop_messagesへの参照であり、呼び出し後も
        # ミューテートされ続ける。呼び出し時点のスナップショットとして保存しないと、
        # 全capturedエントリが最終状態を指してしまい「N回目の呼び出し時点で何が
        # 渡されていたか」を検証できなくなる。
        snapshot = dict(kwargs)
        if "messages" in snapshot:
            snapshot["messages"] = [dict(m) for m in snapshot["messages"]]
        self._captured_kwargs.append(snapshot)
        return _FakeStream(self._factory(n))


class _FakeClient:
    def __init__(self, factory):
        self._counter = [0]
        self.captured_kwargs = []
        self.base_url = "http://fake"  # openrouterでないこと（extra_bodyスキップ）
        self.chat = SimpleNamespace(completions=_FakeCompletions(factory, self._counter, self.captured_kwargs))


DUMMY_TOOLS = [{"function": {"name": "fake_repeat_tool"}}]


def _run(factory):
    cela_main._LAST_REPETITION_GUARD_TRIPPED = None
    client = _FakeClient(factory)
    result = cela_main._query_AI_live(
        messages=[{"role": "user", "content": "監査対象"}],
        client=client,
        model="fake",
        label="Expert",
        tools=DUMMY_TOOLS,
        light_system_prompt=None,
        state=None,
    )
    return result, client._counter[0], cela_main._LAST_REPETITION_GUARD_TRIPPED, client.captured_kwargs


# ---- テスト ----

def test_nudge_injected_and_run_recovers_when_model_diversifies():
    """3回連続同一引数でナッジが注入され、4回目でモデルが異なる引数に切り替えれば
    （自己修復に成功すれば）強制終了せず正常完了する。"""
    def factory(n):
        if n <= 3:
            return _chunks(None, [("fake_repeat_tool", {"query": "同じクエリ"})])
        if n == 4:
            return _chunks(None, [("fake_repeat_tool", {"query": "別のクエリ"})])
        return _chunks("最終回答", [])  # tool_callsなし → 正常終了

    result, create_calls, flag, captured = _run(factory)

    assert result == "最終回答"
    assert flag is None  # ガードは最終的に発動していない（強制終了していない）
    assert create_calls == 5

    # 4回目のAPI呼び出し（ナッジ後の応答を生成する呼び出し）に渡されたmessagesに、
    # ナッジ文言が含まれていること。
    fourth_call_messages = captured[3]["messages"]
    joined = json.dumps(fourth_call_messages, ensure_ascii=False)
    assert "全く同じ引数でのツール呼び出し" in joined
    assert "3回連続" in joined


def test_terminates_after_one_more_repeat_following_the_nudge():
    """ナッジ後もモデルが同一引数を繰り返した場合、10回まで待たず4回目で強制終了する。"""
    def factory(n):
        return _chunks(None, [("fake_repeat_tool", {"query": "同じクエリ"})])

    result, create_calls, flag, captured = _run(factory)

    assert "BL-287" in result
    assert "有効な出力がありませんでした" in result
    assert create_calls == cela_main._TOOL_CALL_REPEAT_NUDGE_THRESHOLD + 1
    assert flag is not None
    assert flag["trigger"] == "tool_call_repeat_after_nudge"
    assert flag["label"] == "Expert"
    assert flag["iteration"] == cela_main._TOOL_CALL_REPEAT_NUDGE_THRESHOLD + 1


def test_no_false_trigger_when_arguments_always_differ():
    """引数が毎回異なる健全なループ（実在の情報検索のように毎回クエリを変える）では
    ナッジも強制終了も発動しない。"""
    def factory(n):
        if n <= 5:
            return _chunks(None, [("fake_repeat_tool", {"query": f"クエリ{n}"})])
        return _chunks("最終回答", [])

    result, create_calls, flag, captured = _run(factory)

    assert result == "最終回答"
    assert flag is None
    assert create_calls == 6
    joined = json.dumps([c.get("messages") for c in captured], ensure_ascii=False)
    assert "全く同じ引数でのツール呼び出し" not in joined


def test_nudge_is_used_at_most_once_per_call():
    """1回のquery_AI_live呼び出し内でナッジは1回のみ。ナッジ後に別引数へ切り替えて
    さらに3回同一を繰り返しても、2回目のナッジは注入されず即座に強制終了する。"""
    def factory(n):
        if n <= 3:
            return _chunks(None, [("fake_repeat_tool", {"query": "クエリA"})])
        if n <= 6:
            return _chunks(None, [("fake_repeat_tool", {"query": "クエリB"})])
        return _chunks("最終回答", [])

    result, create_calls, flag, captured = _run(factory)

    # 4回目でクエリBに切り替わり反復カウントがリセットされるが、5,6回目で再び
    # クエリBが3回連続する前に、ナッジ済みのため4回目時点の判定はどうなるか:
    # 4回目=B(1), 5回目=B(2), 6回目=B(3) で3連続に達し、ナッジは既に使用済みのため
    # 即座に強制終了する（6回目で終了、7回目のクエリA→Bのような追加ナッジは発生しない）。
    assert "BL-287" in result
    assert create_calls == 6
    assert flag is not None
    assert flag["trigger"] == "tool_call_repeat_after_nudge"


def test_bl287_code_present_in_source():
    """§17.1後段: ガード実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_TOOL_CALL_REPEAT_NUDGE_THRESHOLD" in src
    assert "_tool_repeat_nudge_used" in src
    assert "tool_call_repeat_after_nudge" in src
    # BL-231本体のロジックは保険として無改修のまま残っていること
    assert "_bl231_combined_hash" in src
    assert "_LOOP_GUARD_REPETITION_WINDOW" in src
