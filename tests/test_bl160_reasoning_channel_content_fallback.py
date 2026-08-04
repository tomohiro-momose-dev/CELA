"""
BL-160: `_query_AI_live`は`delta.content`（contentチャンネル）のみを最終回答として使い、
`delta.reasoning`（reasoningチャンネル）はグローバル`_LAST_REASONING_TEXT`への保存以外に
一切使われていなかった。実ログ（log/2026-08-04/0807）でモデルが最終JSONを丸ごとreasoning
チャンネルへ出力しcontentが空のまま応答を終えるケースが3/4回再現し、そのたびに
`current_task_id`の遷移シグナルを含む抽出結果が全損した（`current_task_id`が実行終了まで
固着）。finish_reason=="length"のチェックは既存コードでこの箇所より前にあるため、
到達した時点でmax_tokens打ち切りではなく自発的終了であることが保証されている。

tools=None分岐（単発JSON判定ノード用）とツール呼び出しループの最終応答（全ツール付与
ノード共通）の両方に同型の欠陥があったため、両方を修正した。あわせて`call_decision_extractor`
（従来リトライ皆無の単発呼び出しだった）を`_query_and_parse_with_retry`でラップし、
他のJSON判定ノードと同水準の層2リトライ保護を持たせた。

参照: docs/design/back_log/issue_backlog.md BL-160、docs/design/decision_log.md D-130。
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


def _reasoning_chunk(text: str, finish_reason=None) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(reasoning=text), finish_reason=finish_reason)])


def _content_chunk(text: str, finish_reason=None) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(content=text), finish_reason=finish_reason)])


def _stop_chunk() -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(), finish_reason="stop")])


def _tool_call_chunk(index: int, tc_id: str, name: str, arguments: dict) -> _FakeChunk:
    return _FakeChunk([_FakeChoice(_FakeDelta(tool_calls=[
        _FakeToolCallDelta(index, tc_id, name, json.dumps(arguments, ensure_ascii=False))
    ]))])


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


def _run_tools_none(chunks: list[_FakeChunk], label: str = "Decision Extractor") -> str:
    cela_main._reset_think_scratchpad()
    client = _FakeClient([chunks])
    return cela_main._query_AI_live(
        messages=[{"role": "user", "content": "extract please"}],
        client=client, model="fake-model", label=label,
        tools=None,
    )


def _run_tool_loop(iterations: list[list[_FakeChunk]], label: str = "TestLoop") -> str:
    cela_main._reset_think_scratchpad()
    client = _FakeClient(iterations)
    return cela_main._query_AI_live(
        messages=[{"role": "system", "content": "system prompt"}, {"role": "user", "content": "do the task"}],
        client=client, model="fake-model", label=label,
        tools=[cela_main.PYTHON_REPL_TOOL, cela_main.THINK_TOOL],
    )


# ---------------------------------------------------------------------------
# tools=None分岐（call_decision_extractor / call_reflectionが通る経路）
# ---------------------------------------------------------------------------

def test_bl160_tools_none_uses_reasoning_when_content_empty():
    """contentが空・reasoningに完成したJSONがある場合、reasoning全文を代替として返すこと。"""
    json_text = '{"extracted_events": [], "advances_to_task_id": "task_1_3"}'
    result = _run_tools_none([_reasoning_chunk(json_text, finish_reason="stop")])
    assert result == json_text
    fallback = {"extracted_events": []}
    parsed = cela_main._safe_json_parse(result, fallback=fallback)
    assert parsed is not fallback
    assert parsed["advances_to_task_id"] == "task_1_3"


def test_bl160_tools_none_both_empty_still_returns_sentinel():
    """回帰確認: content・reasoning共に空なら従来通りsentinelを返すこと。"""
    result = _run_tools_none([_stop_chunk()])
    assert result == "(APIから空の応答が返されました)"


def test_bl160_tools_none_content_present_ignores_reasoning():
    """回帰確認: contentが非空ならreasoningの有無に関わらずcontentのみを返すこと。"""
    result = _run_tools_none([
        _reasoning_chunk("この内容は無視されるべき下書きの思考"),
        _content_chunk('{"extracted_events": []}', finish_reason="stop"),
    ])
    assert result == '{"extracted_events": []}'


# ---------------------------------------------------------------------------
# ツール呼び出しループの最終応答（Expert/Detector/Orchestrator等が通る経路）
# ---------------------------------------------------------------------------

def test_bl160_tool_loop_uses_final_iteration_reasoning_when_content_empty():
    """最終iterationがcontent空・reasoning非空で終了した場合、そのiterationのreasoningを
    代替として返すこと。かつ、それより前のiterationの無関係なreasoningが混入しないこと。"""
    final_json = '{"risk": "low", "constraint_issue": "none"}'
    iterations = [
        [_reasoning_chunk("iter1の無関係な思考"), _tool_call_chunk(0, "call_1", "python_repl", {"code": "1+1"})],
        [_reasoning_chunk(final_json, finish_reason="stop")],
    ]
    result = _run_tool_loop(iterations)
    assert result == final_json
    assert "iter1の無関係な思考" not in result


def test_bl160_tool_loop_both_empty_still_returns_sentinel():
    """回帰確認: 最終iterationのcontent・reasoning共に空なら従来通りsentinelを返すこと。"""
    iterations = [
        [_tool_call_chunk(0, "call_1", "python_repl", {"code": "1+1"})],
        [_stop_chunk()],
    ]
    result = _run_tool_loop(iterations)
    assert result == "(APIから空の応答が返されました)"


def test_bl160_tool_loop_content_present_ignores_reasoning():
    """回帰確認: 最終iterationのcontentが非空ならreasoningの有無に関わらずcontentのみを返すこと。"""
    iterations = [
        [_tool_call_chunk(0, "call_1", "python_repl", {"code": "1+1"})],
        [_reasoning_chunk("下書きの思考"), _content_chunk("done", finish_reason="stop")],
    ]
    result = _run_tool_loop(iterations)
    assert result == "done"


# ---------------------------------------------------------------------------
# call_decision_extractorの層2リトライ保護
# ---------------------------------------------------------------------------

def test_bl160_call_decision_extractor_retries_via_query_and_parse_with_retry(monkeypatch):
    """call_decision_extractorが_query_and_parse_with_retryでラップされ、1回目失敗・
    2回目成功のケースでリトライが機能し、正しいtransitionが取得できること。"""
    call_count = {"n": 0}
    responses = [
        "(APIから空の応答が返されました)",
        '{"extracted_events": [], "advances_to_phase_id": null, "advances_to_task_id": "task_1_3"}',
    ]

    def _fake_query_AI(messages, client, model, label="Unknown Node", tools=None, **kwargs):
        idx = call_count["n"]
        call_count["n"] += 1
        return responses[idx]

    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)
    chat_history = [{"role": "user", "content": "task_1_2を承認、task_1_3へ進んでください"}]
    events, transition = cela_main.call_decision_extractor(chat_history, existing_topics=[], target_role="user")

    assert call_count["n"] == 2
    assert events == []
    assert transition["advances_to_task_id"] == "task_1_3"


def test_bl160_call_decision_extractor_exhausts_retry_and_returns_empty(monkeypatch):
    """回帰確認: 層2リトライ（既定2回）を使い切った場合、従来通り抽出結果が空になること
    （フェイルクローズ、クラッシュしないこと）。"""
    call_count = {"n": 0}

    def _always_empty_query_AI(messages, client, model, label="Unknown Node", tools=None, **kwargs):
        call_count["n"] += 1
        return "(APIから空の応答が返されました)"

    monkeypatch.setattr(cela_main, "query_AI", _always_empty_query_AI)
    chat_history = [{"role": "user", "content": "task_1_2を承認、task_1_3へ進んでください"}]
    events, transition = cela_main.call_decision_extractor(chat_history, existing_topics=[], target_role="user")

    assert call_count["n"] == 3  # 初回 + 既定max_retries=2回
    assert events == []
    assert transition == {"advances_to_phase_id": None, "advances_to_task_id": None}
