"""
BL-237: thinkを毎iteration必須（プロンプトレベル、機械的強制なし）にする回帰テスト。

背景: log/2026-08-15/1735・1954で、Task Plan Reviewerのreasoningチャンネルが
単一iteration内で同じ結論を延々と再導出し続ける「生成崩壊」が発生した。当初、
thinkを呼んだiterationは生reasoningの引き継ぎを省略し、thinkの構造化summaryだけに
絞る案を実装したが、web検索結果の統合過程・詳細な検討・最終出力やJSON構造の下書きなど、
summaryの1-3文には収まらない実質的な内容までthink必須化と組み合わさって失われる副作用が
あるとユーザーが指摘したため撤回した。最終的な設計は、生reasoningの引き継ぎは常に無条件の
まま維持し（情報を一切壊さない）、thinkは純粋加算（毎iteration必須の構造化decided/whyの
チェックポイント）に留める。単一iteration内の生成崩壊そのものへの対処は、情報の中身に
踏み込まないmax_tokens上限（別途）に委ねる。

実LLMは呼ばず、tests/test_bl231_loop_guard.pyと同型のストリーミング互換モック
OpenAIクライアントで_query_AI_liveを駆動する（§17.1: リバートで失敗することを確認済み）。
"""

import json
from types import SimpleNamespace

import cela_main


def _chunks(reasoning, content, plan):
    """reasoning(思考チャンネル)・content(応答チャンネル)・plan([(name, args), ...])から
    ストリーミングチャンク列を作る。planが空ならtool_callsなしの最終回答とみなす。
    """
    chunks = []
    if reasoning:
        chunks.append(SimpleNamespace(choices=[SimpleNamespace(
            delta=SimpleNamespace(reasoning=reasoning, content=None, tool_calls=None),
            finish_reason=None)]))
    if plan:
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
    chunks.append(SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=content, tool_calls=None),
        finish_reason="stop")]))
    return chunks


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeCompletions:
    """[BL-237] kwargsのmessages（=loop_messages）を呼び出しごとに記録する。"""
    def __init__(self, factory):
        self._factory = factory
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs["messages"])
        n = len(self.calls)
        return _FakeStream(self._factory(n))


class _FakeClient:
    def __init__(self, factory):
        self.base_url = "http://fake"
        self.chat = SimpleNamespace(completions=_FakeCompletions(factory))


REASONING_TEXT = "iterationの生reasoning本文（web検索結果の統合過程や下書きを含みうる）"


def _run(factory):
    cela_main._reset_think_scratchpad()
    client = _FakeClient(factory)
    result = cela_main._query_AI_live(
        messages=[{"role": "user", "content": "レビューしてください"}],
        client=client,
        model="fake",
        label="task plan reviewer",
        tools=[{"function": {"name": "think"}}, {"function": {"name": "dummy_other_tool"}}],
        light_system_prompt=None,
        state=None,
    )
    return result, client.chat.completions.calls


def test_raw_reasoning_carries_forward_even_when_think_was_called():
    """[BL-237] iter=1でthinkを呼んでも、生reasoningの引き継ぎは省略されないこと
    （web検索結果の統合過程や下書きなど、thinkのsummaryに収まらない内容を壊さないため）。"""
    def factory(n):
        if n == 1:
            return _chunks(REASONING_TEXT, None, [("think", {"action": "reviewing", "summary": "ok"})])
        return _chunks(None, "final answer", [])

    result, calls = _run(factory)

    assert result == "final answer"
    messages_for_iter2 = calls[1]
    digest_messages = [
        m for m in messages_for_iter2
        if m.get("role") == "system" and "iter 1 の思考ログ（自動保存）" in m.get("content", "")
    ]
    assert len(digest_messages) == 1, (
        "thinkを呼んでも生reasoningの引き継ぎが維持されていること（BL-237の情報損失回避方針）"
    )
    assert REASONING_TEXT in digest_messages[0]["content"]


def test_think_summary_is_additionally_carried_alongside_raw_reasoning():
    """thinkを呼んだ場合、生reasoningに加えてthinkの構造化summary（tool結果）も
    引き継がれること（置き換えではなく加算）。"""
    def factory(n):
        if n == 1:
            return _chunks(REASONING_TEXT, None, [("think", {"action": "reviewing", "summary": "ok"})])
        return _chunks(None, "final answer", [])

    result, calls = _run(factory)

    messages_for_iter2 = calls[1]
    think_tool_results = [
        m for m in messages_for_iter2
        if m.get("role") == "tool" and "reasoning_log_so_far" in m.get("content", "")
    ]
    assert len(think_tool_results) == 1
    digest_messages = [
        m for m in messages_for_iter2
        if m.get("role") == "system" and "の思考ログ（自動保存）" in m.get("content", "")
    ]
    assert len(digest_messages) == 1


def test_raw_reasoning_still_carries_forward_when_think_not_called():
    """thinkを呼ばなかった場合も、従来通り生reasoningダイジェストが引き継がれること（回帰確認）。"""
    def factory(n):
        if n == 1:
            return _chunks(REASONING_TEXT, None, [("dummy_other_tool", {})])
        return _chunks(None, "final answer", [])

    result, calls = _run(factory)

    assert result == "final answer"
    messages_for_iter2 = calls[1]
    digest_messages = [
        m for m in messages_for_iter2
        if m.get("role") == "system" and "iter 1 の思考ログ（自動保存）" in m.get("content", "")
    ]
    assert len(digest_messages) == 1
    assert REASONING_TEXT in digest_messages[0]["content"]


def test_think_tool_description_states_mandatory_every_iteration():
    """THINK_TOOLのスキーマ説明文自体が「毎iteration必須」を明示していること
    （プロンプト側だけでなく、モデルに渡る関数定義そのものと矛盾しないため）。"""
    description = cela_main.THINK_TOOL["function"]["description"]
    assert "EVERY iteration" in description


def test_think_tool_description_does_not_claim_raw_reasoning_is_dropped():
    """[BL-237] thinkを呼ぶと生reasoningが失われる、という誤った説明が残っていないこと
    （情報損失を避けるためswap案を撤回した経緯と矛盾しないための存在証明）。"""
    description = cela_main.THINK_TOOL["function"]["description"]
    assert "does NOT replace or drop" in description
