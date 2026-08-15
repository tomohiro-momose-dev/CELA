"""
BL-093/D-074: thinkツールを呼ぶかどうかをモデルの任意判断に委ねると、大半のiterationで
結局reasoningが引き継がれないことが判明した（ユーザー指摘）ため、当初は「ツール呼び出しを
含む全iterationはthinkを非空summary付きで併用すること」を`_query_AI_live`側で機械的に
強制していた（違反時はツール呼び出しを一切実行せず差し戻す）。

[BL-108/BL-110] その後、ネイティブのreasoning（delta.reasoning）が think の呼び出しに関わらず
毎iter無条件にdigestへ蓄積されるようになり、思考ログの引き継ぎ自体はthink無しでも成立するように
なったため、機械的強制（差し戻し）は撤廃し、thinkツール自体は任意呼び出しとして残した。

[BL-237] 「think無しでも生reasoningが無条件に引き継がれる」設計自体が、迷い・撤回を含む
生の言い回しをそのまま次iterationへ運び、後続iterationが同じ結論を延々と再導出し続ける
生成崩壊の一因と判明した（log/2026-08-15/1735・1954）。thinkを毎iteration必須のプロンプト
指示へ戻したが（機械的な差し戻しは伴わない、往復コスト増を避けるため）、当初検討した
「thinkを呼んだiterationは生reasoningの代わりにthinkのsummaryだけを引き継ぐ」swap案は、
web検索結果の統合過程・下書きなどsummaryに収まらない実質的内容が失われる副作用がある
（ユーザー指摘）ため撤回し、**生reasoningの引き継ぎは常に無条件のまま維持**している
（本ファイルの既存テストが検証する挙動そのものに変更なし）。

この一連の挙動は`_query_AI_live`の内部ループそのものを検証する必要があり、既存テストが行っている
`query_AI`/`_query_and_parse_with_retry`レベルのモンキーパッチでは到達できないため、OpenAIの
streamingレスポンスを模したフェイククライアントで直接検証する。

参照: docs/design/issue_backlog.md BL-093/BL-108/BL-110/BL-237、docs/design/decision_log.md D-074。
"""

import json
import os
import sys

import httpx

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


def test_bl110_tool_call_without_think_now_executes_normally():
    """[BL-110] thinkを伴わないpython_repl呼び出しも、差し戻されずそのまま実行されること
    （BL-108でネイティブreasoningが毎iter無条件にdigestへ蓄積されるようになり、think併用の
    機械的強制が不要になったためユーザー指示で撤廃した）。"""
    iterations = [
        [_tool_call_chunk(0, "call_1", "python_repl", {"code": "1/0"})],  # thinkなし
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    # 差し戻されず実行されているため、_LAST_PYTHON_CALLSに記録が残る
    assert any("1/0" in c["code"] for c in cela_main._LAST_PYTHON_CALLS)


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


def test_bl110_standalone_think_without_summary_still_executes():
    """[BL-110] think単独呼び出しでsummaryが空でも、差し戻されず_think_handlerに到達し
    reasoning_logへ記録されること（summary必須の機械的強制は撤廃済み）。"""
    iterations = [
        [_tool_call_chunk(0, "call_1", "think", {"action": "何か考える"})],  # summary無し
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    assert cela_main._THINK_REASONING_LOG[-1]["action"] == "何か考える"


def test_standalone_think_with_summary_is_accepted():
    iterations = [
        [_tool_call_chunk(0, "call_1", "think", {"action": "何か考える", "summary": "考えた結果をまとめた"})],
        [_final_text_chunk("done")],
    ]
    result = _run(iterations)
    assert result == "done"
    assert len(cela_main._THINK_REASONING_LOG) == 1
    assert cela_main._THINK_REASONING_LOG[0]["summary"] == "考えた結果をまとめた"


def test_auto_reasoning_digest_accumulates_without_summarizing():
    """[BL-108] 要約はせず、全iterationの生reasoningがそのまま蓄積されること
    （thinkのsummary自体はreasoning_logへの記録として引き続き必須）。"""
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
    # digest末尾追記（BL-106）のロジックがエラーなく完走したことと、既存のreasoning_log/
    # summaryが正しく蓄積されていることを確認する（ダイジェスト文字列そのものの内容検証は
    # 別テストでcreate_kwargsをキャプチャして行う）。
    assert [e["summary"] for e in cela_main._THINK_REASONING_LOG] == [
        "iter1のまとめ", "iter2のまとめ", "iter3のまとめ",
    ]


def test_auto_reasoning_digest_content_captured_via_create_kwargs():
    """digestメッセージの内容を、create()に渡された実際のmessages配列から直接検証する。
    [BL-237] 全iterationでthinkを呼んでいても、生reasoningのdigestは省略されない
    （thinkの構造化summaryは加算されるだけで、生reasoningの引き継ぎを置き換えない）。"""
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
    # [BL-111] 全iter分を1メッセージに再結合する（BL-108）のをやめ、iterationごとに独立した
    # 新規systemメッセージを末尾に追記するだけ（真の単調増加）にしたため、末尾メッセージには
    # 直近iter（iter3）の生reasoningのみが入り、iter1/iter2は末尾より手前の別メッセージとして
    # 個別に残っている。[BL-237] thinkを毎iteration呼んでいてもこの生reasoning引き継ぎは
    # 省略されない（加算のみ、置き換えではない）。
    last_msg = messages_before_iter4[-1]
    assert last_msg["role"] == "system"
    assert "iter3の生reasoning内容" in last_msg["content"]
    assert "iter1の生reasoning内容" not in last_msg["content"]
    assert "iter2の生reasoning内容" not in last_msg["content"]
    all_content = "\n".join(m.get("content", "") or "" for m in messages_before_iter4)
    assert "iter1の生reasoning内容" in all_content
    assert "iter2の生reasoning内容" in all_content


def test_bl111_consecutive_requests_are_a_strict_prefix_of_each_other():
    """[BL-111] プレフィックスキャッシュが機能する必須条件は「一度追加したメッセージを
    二度と変更・削除・移動しない」こと。iterNへのリクエストが、iterN+1へのリクエストの
    厳密な先頭部分（プレフィックス）になっていることを直接検証する
    （BL-108時点ではdigestの再構築・付け替えによりこれが破れていた：Gemini指摘）。
    """
    captured_messages_per_call = []

    class _CapturingCompletions(_FakeCompletions):
        def create(self, **kwargs):
            captured_messages_per_call.append([dict(m) for m in kwargs["messages"]])
            return super().create(**kwargs)

    iterations = [
        [_reasoning_chunk("iter1の思考"),
         _tool_call_chunk(0, "call_1", "think", {"action": "iter1", "summary": "iter1要約"})],
        [_reasoning_chunk("iter2の思考"),
         _tool_call_chunk(0, "call_2", "think", {"action": "iter2", "summary": "iter2要約"})],
        [_reasoning_chunk("iter3の思考"),
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
    # iter1〜iter4への各送信メッセージが、直後のリクエストの厳密な先頭部分になっていること。
    for i in range(len(captured_messages_per_call) - 1):
        shorter = captured_messages_per_call[i]
        longer = captured_messages_per_call[i + 1]
        assert len(longer) > len(shorter), f"call {i+1} should have grown over call {i}"
        assert longer[:len(shorter)] == shorter, (
            f"call {i} の全メッセージが call {i+1} の先頭部分と厳密に一致していない "
            "（プレフィックスキャッシュが壊れる変更）"
        )


def test_bl122_api_error_mid_loop_resumes_same_iteration_without_discarding_progress():
    """[BL-122] ツールループの途中（iteration 2）でAPIエラーが発生し外側のリトライが
    発生しても、iteration 1で蓄積した進捗（loop_messages/reasoning/think記録）が
    破棄されず、iteration 2から（1からではなく）再開されることを検証する。
    従来は`for attempt`のtryブロック内でloop_messages等が再初期化されていたため、
    リトライのたびにiteration=1から丸ごとやり直されていた。
    """
    call_log: list[str] = []

    class _FlakyCompletions(_FakeCompletions):
        def create(self, **kwargs):
            call_log.append("create")
            # 2回目のcreate()呼び出し（iteration2の最初の試行）でAPIエラーを模擬する。
            if len(call_log) == 2:
                raise httpx.TimeoutException("simulated transient API error")
            return super().create(**kwargs)

    iterations = [
        [_reasoning_chunk("iter1の思考"),
         _tool_call_chunk(0, "call_1", "think", {"action": "iter1", "summary": "iter1のまとめ"})],
        [_reasoning_chunk("iter2の思考"),
         _tool_call_chunk(0, "call_2", "think", {"action": "iter2", "summary": "iter2のまとめ"})],
        [_final_text_chunk("done")],
    ]
    client = _FakeClient(iterations)
    client.chat.completions = _FlakyCompletions(iterations)
    cela_main._reset_think_scratchpad()
    result = cela_main._query_AI_live(
        messages=[{"role": "system", "content": "system prompt"}, {"role": "user", "content": "do the task"}],
        client=client, model="fake-model", label="TestLoop",
        tools=[cela_main.THINK_TOOL],
    )
    assert result == "done"
    # create()は4回呼ばれたはず: iter1成功、iter2失敗（リトライ）、iter2再試行成功、iter3成功。
    assert len(call_log) == 4
    # iteration 1で記録されたthink要約が、iteration 2のAPIエラー・リトライを経ても
    # 失われずに残っていること（従来はここが空リストにリセットされていた）。
    assert [e["summary"] for e in cela_main._THINK_REASONING_LOG] == [
        "iter1のまとめ", "iter2のまとめ",
    ]
