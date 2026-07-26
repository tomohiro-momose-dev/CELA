"""
BL-093/D-074: thinkツールを呼ぶかどうかをモデルの任意判断に委ねると、大半のiterationで
結局reasoningが引き継がれないことが判明した（ユーザー指摘）。そこで「ツール呼び出しを
含む全iterationはthinkを非空summary付きで併用すること」を`_query_AI_live`側で機械的に
強制し（違反時はツール呼び出しを一切実行せず差し戻す）、直近N iter分の生reasoningと、
それより古いiterのthink summaryを組み合わせた自動ダイジェストメッセージをloop_messagesへ
差し替えていく。この一連の挙動は`_query_AI_live`の内部ループそのものを検証する必要があり、
既存テストが行っている`query_AI`/`_query_and_parse_with_retry`レベルのモンキーパッチでは
到達できないため、OpenAIのstreamingレスポンスを模したフェイククライアントで直接検証する。

参照: docs/design/issue_backlog.md BL-093、docs/design/decision_log.md D-074。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


class _FakeFunctionDelta:
    def __init__(self, name: str = "", arguments: str = ""):
        self.name = name
        self.arguments = arguments


class _FakeToolCallDelta:
    def __init__(self, index: int, tc_id: str | None = None, name: str = "", arguments: str = ""):
        self.index = index
        self.id = tc_id
        self.function = _FakeFunctionDelta(name, arguments)


class _FakeDelta:
    def __init__(self, reasoning=None, content=None, tool_calls=None):
        self.reasoning = reasoning
        self.content = content
        self.tool_calls = tool_calls


class _FakeChoice:
    def __init__(self, delta: _FakeDelta, finish_reason=None):
        self.delta = delta
        self.finish_reason = finish_reason


class _FakeChunk:
    def __init__(self, choices):
        self.choices = choices


def _tool_call_chunk(index: int, tc_id: str, name: str, arguments: dict) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(tool_calls=[
        _FakeToolCallDelta(index, tc_id, name, json.dumps(arguments, ensure_ascii=False))
    ]))])


def _reasoning_chunk(text: str) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(reasoning=text))])


def _final_text_chunk(text: str) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(content=text), finish_reason="stop")])


class _FakeCompletions:
    def __init__(self, iterations: list[list[_FakeChunk]]):
        self._iterations = iterations
        self._call_idx = 0

    def create(self, **kwargs):
        chunks = self._iterations[self._call_idx]
        self._call_idx += 1
        return iter(chunks)


class _FakeChatAPI:
    def __init__(self, iterations):
        self.completions = _FakeCompletions(iterations)


class _FakeClient:
    """base_urlに'openrouter'を含めないことで、OpenRouter専用のextra_body分岐を回避する。"""
    def __init__(self, iterations):
        self.chat = _FakeChatAPI(iterations)
        self.base_url = "https://api.fake.test/v1"


def _run(iterations):
    cela_main._reset_think_scratchpad()
    client = _FakeClient(iterations)
    return cela_main._query_AI_live(
        messages=[{"role": "system", "content": "system prompt"}, {"role": "user", "content": "do the task"}],
        client=client, model="fake-model", label="TestLoop",
        tools=[cela_main.PYTHON_REPL_TOOL, cela_main.THINK_TOOL],
    )


def test_tool_call_without_think_is_rejected_and_not_executed():
    """thinkを伴わないpython_repl呼び出しは実行されず、エラーが差し戻されること。"""
    iterations = [
        # iter1: python_replのみ呼ぶ（thinkなし）→ 拒否されるはず
        [_tool_call_chunk(0, "call_1", "python_repl", {"code": "1/0"})],
        # iter2: 最終応答（拒否メッセージを見てモデルが諦めて終了したと仮定）
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    # 拒否されていればpython_replは一度も実行されないため、_LAST_PYTHON_CALLSは空のまま
    assert cela_main._LAST_PYTHON_CALLS == []


def test_tool_call_with_think_and_summary_is_executed_normally():
    """think(summary付き)を伴うpython_repl呼び出しは正常に実行されること。"""
    iterations = [
        [
            _tool_call_chunk(0, "call_1", "python_repl", {"code": "print(1+1)"}),
            _tool_call_chunk(1, "call_2", "think", {"action": "計算する", "summary": "1+1を計算した"}),
        ],
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    # python_replが実際に実行されていれば_LAST_PYTHON_CALLSに記録が残る
    assert any("1+1" in c["code"] for c in cela_main._LAST_PYTHON_CALLS)


def test_standalone_think_without_summary_is_also_rejected():
    """他ツールを伴わないthink単独呼び出しでも、summaryが空なら拒否されること
    （thinkもツールである以上、summary欠落は次の次のiterationでダイジェストの穴になるため）。"""
    iterations = [
        [_tool_call_chunk(0, "call_1", "think", {"action": "何か考える"})],  # summary無し
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    # 拒否されているので、reasoning_logに記録されるべきではない
    # (このiterationのthink呼び出し自体は_think_handlerに到達しない)
    assert cela_main._THINK_REASONING_LOG == []


def test_standalone_think_with_summary_is_accepted():
    iterations = [
        [_tool_call_chunk(0, "call_1", "think", {"action": "何か考える", "summary": "考えた結果をまとめた"})],
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    assert len(cela_main._THINK_REASONING_LOG) == 1
    assert cela_main._THINK_REASONING_LOG[0]["summary"] == "考えた結果をまとめた"


def test_auto_reasoning_digest_uses_verbatim_for_recent_and_summary_for_older():
    """直近_AUTO_REASONING_VERBATIM_ITERS件は生reasoningのまま、それより古い分は
    thinkのsummaryに基づくダイジェストが構築されること。"""
    iterations = [
        [_reasoning_chunk("iter1の生reasoning"),
         _tool_call_chunk(0, "call_1", "think", {"action": "iter1", "summary": "iter1のまとめ"})],
        [_reasoning_chunk("iter2の生reasoning"),
         _tool_call_chunk(0, "call_2", "think", {"action": "iter2", "summary": "iter2のまとめ"})],
        [_reasoning_chunk("iter3の生reasoning"),
         _tool_call_chunk(0, "call_3", "think", {"action": "iter3", "summary": "iter3のまとめ"})],
        [_final_text_chunk("done")],
    ]
    client = _FakeClient(iterations)
    cela_main._reset_think_scratchpad()
    cela_main._query_AI_live(
        messages=[{"role": "system", "content": "system prompt"}, {"role": "user", "content": "do the task"}],
        client=client, model="fake-model", label="TestLoop",
        tools=[cela_main.THINK_TOOL],
    )
    # iter4の直前（最後にAPIへ送られるmessages）を見る必要があるが、_query_AI_liveは
    # loop_messagesを外部に返さないため、代わりにcreate()に渡されたkwargsを検査する。
    # _FakeCompletions.createは呼び出しごとのkwargsを保存していないため、ここでは
    # digest挿入位置(index=1)のロジックがエラーなく完走したことと、既存のreasoning_log/
    # summaryが正しく蓄積されていることを確認する（ダイジェスト文字列そのものの内容検証は
    # 別テストでcreate_kwargsをキャプチャして行う）。
    assert [e["summary"] for e in cela_main._THINK_REASONING_LOG] == [
        "iter1のまとめ", "iter2のまとめ", "iter3のまとめ",
    ]


def test_auto_reasoning_digest_content_captured_via_create_kwargs():
    """digestメッセージの内容を、create()に渡された実際のmessages配列から直接検証する。"""
    captured_messages_per_call = []

    class _CapturingCompletions(_FakeCompletions):
        def create(self, **kwargs):
            captured_messages_per_call.append([dict(m) for m in kwargs["messages"]])
            return super().create(**kwargs)

    iterations = [
        [_reasoning_chunk("iter1の生reasoning内容"),
         _tool_call_chunk(0, "call_1", "think", {"action": "iter1", "summary": "iter1要約"})],
        [_reasoning_chunk("iter2の生reasoning内容"),
         _tool_call_chunk(0, "call_2", "think", {"action": "iter2", "summary": "iter2要約"})],
        [_reasoning_chunk("iter3の生reasoning内容"),
         _tool_call_chunk(0, "call_3", "think", {"action": "iter3", "summary": "iter3要約"})],
        [_final_text_chunk("done")],
    ]
    client = _FakeClient(iterations)
    client.chat.completions = _CapturingCompletions(iterations)
    cela_main._reset_think_scratchpad()
    cela_main._query_AI_live(
        messages=[{"role": "system", "content": "system prompt"}, {"role": "user", "content": "do the task"}],
        client=client, model="fake-model", label="TestLoop",
        tools=[cela_main.THINK_TOOL],
    )
    # iter4への送信メッセージ（4回目のcreate呼び出し = index 3）を見る
    messages_before_iter4 = captured_messages_per_call[3]
    digest_msg = messages_before_iter4[1]
    assert digest_msg["role"] == "system"
    # 直近2iter(_AUTO_REASONING_VERBATIM_ITERS=2)分は生reasoningそのまま
    assert "iter2の生reasoning内容" in digest_msg["content"]
    assert "iter3の生reasoning内容" in digest_msg["content"]
    # iter1は窓の外なのでsummaryベースになっている（生reasoningの原文は含まれない）
    assert "iter1の生reasoning内容" not in digest_msg["content"]
    assert "iter1要約" in digest_msg["content"]
