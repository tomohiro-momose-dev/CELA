"""
BL-237: thinkが呼ばれたiterationでは、生reasoning全文の次iterationへの引き継ぎ
（BL-093ダイジェスト）を省略し、既にtool結果として渡っているthinkの構造化summary
（累積reasoning_log_so_far）だけに絞る回帰テスト。

背景: log/2026-08-15/1735・1954で、Task Plan Reviewerのreasoningチャンネルが
単一iteration内で同じ結論を延々と再導出し続ける「生成崩壊」が発生した。原因調査の結果、
_query_AI_liveが「そのiterationの生reasoning全文（迷い・撤回を含む）」を無条件に次
iterationのcontextへ引き継いでいたことが判明（BL-093/BL-108/BL-111）。thinkを呼んだ
iterationは、その理由づけが既に構造化されたtool結果として渡っているため、生reasoningの
二重引き継ぎを省き、迷いの言い回しが次iterationへそのまま伝播することを防ぐ。

実LLMは呼ばず、tests/test_bl231_loop_guard.pyと同型のストリーミング互換モック
OpenAIクライアントで_query_AI_liveを駆動する（§17.1: リバートで失敗することを確認済み）。
"""

import inspect
import json
from types import SimpleNamespace

import pytest

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
    """[BL-237] kwargsのmessages（=loop_messages）を呼び出しごとに記録する。
    これにより「iter Nで何を引き継いだか」を次のcreate()呼び出し引数から検証できる。
    """
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


REASONING_TEXT = "But actually, hmm, let me reconsider this from the start..."


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


def test_think_called_iteration_skips_raw_reasoning_carryover():
    """iter=1でthinkを呼んだ場合、iter=2へ渡るmessagesに『iter 1 の思考ログ（自動保存）』
    という生reasoningダイジェストが含まれないこと（thinkのtool結果のみが引き継がれる）。"""
    def factory(n):
        if n == 1:
            return _chunks(REASONING_TEXT, None, [("think", {"action": "reviewing", "summary": "ok"})])
        return _chunks(None, "final answer", [])

    result, calls = _run(factory)

    assert result == "final answer"
    assert len(calls) == 2
    messages_for_iter2 = calls[1]
    digest_messages = [
        m for m in messages_for_iter2
        if m.get("role") == "system" and "の思考ログ（自動保存）" in m.get("content", "")
    ]
    assert digest_messages == [], (
        "thinkを呼んだiterationの生reasoningダイジェストが引き継がれてしまっている"
    )
    # thinkのtool結果（構造化summary）自体は引き継がれていること
    think_tool_results = [
        m for m in messages_for_iter2
        if m.get("role") == "tool" and "reasoning_log_so_far" in m.get("content", "")
    ]
    assert len(think_tool_results) == 1


def test_think_not_called_iteration_keeps_raw_reasoning_carryover_fallback():
    """iter=1でthinkを呼ばなかった場合、従来通り生reasoningダイジェストがiter=2へ引き継がれること
    （フォールバック、情報欠落を防ぐ）。"""
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


def test_bl237_guard_code_present_in_source():
    """§17.1 後段: 実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_think_called_this_iter" in src
    assert "and not _think_called_this_iter" in src


def test_think_tool_description_states_mandatory_every_iteration():
    """THINK_TOOLのスキーマ説明文自体が「毎iteration必須」を明示していること
    （プロンプト側だけでなく、モデルに渡る関数定義そのものと矛盾しないため）。"""
    description = cela_main.THINK_TOOL["function"]["description"]
    assert "EVERY iteration" in description
