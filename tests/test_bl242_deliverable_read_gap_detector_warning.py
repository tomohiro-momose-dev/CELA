"""
BL-242: Expertが依存タスク（depends_on）の成果物を実際にread_deliverable_fileで読んだかを
機械的に検知し、読んでいない依存先があればDetectorへ警告する（BL-033の「Expertがpython_repl
を使わなかったことをDetectorへ警告する」パターンの横展開）。

log/2026-08-16/1000で、task_7_1のExpertが依存タスク7件中5件の成果物を一度も読まずに
統合文書を書いていた実インシデントへの対応。ターンの強制差し戻しは行わず（BL-108→BL-110/
D-206→D-207で「機械的強制は往復コスト過大」と判断した経緯を踏襲）、監査側（Detector）へ
事実を伝えるに留める。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-242。
"""

import inspect
import json
import os
import sys
import time
import uuid
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl242.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""


_PHASES = [
    {"phase_id": "phase_5", "tasks": [{"task_id": "task_5_4"}, {"task_id": "task_6_3"}]},
]


def _seed_deliverable(state, run_id, task_id, phase_id, topic, content):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": topic,
            "decision_what": content, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": phase_id, "task_id": task_id,
        },
        state,
    )
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 追跡機構そのもの（_LAST_DELIVERABLE_READ_TASK_IDS / get_last_deliverable_reads）
# ---------------------------------------------------------------------------

def test_successful_read_records_task_id(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(state, run_id, "task_5_4", "phase_5", "task_5_4 成果物", "本文" + "X" * 500)
    cela_main._LAST_DELIVERABLE_READ_TASK_IDS = []

    result = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"task_id": "task_5_4"}, state)

    # [BL-289] ホワイトボード経路はdict化された
    assert isinstance(result, dict)
    assert cela_main.get_last_deliverable_reads() == ["task_5_4"]


def test_not_found_read_does_not_record(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    cela_main._LAST_DELIVERABLE_READ_TASK_IDS = []

    result = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"task_id": "task_6_3"}, state)

    assert result["status"] == "not_found"
    assert cela_main.get_last_deliverable_reads() == []


# ---------------------------------------------------------------------------
# _query_AI_liveレベル: モデルが実際にread_deliverable_fileを呼んだ場合の記録とリセット
# ---------------------------------------------------------------------------

def _chunks(plan):
    tc_deltas = [
        SimpleNamespace(
            index=i, id=f"call_{i}",
            function=SimpleNamespace(name=n, arguments=json.dumps(a, ensure_ascii=False)),
        )
        for i, (n, a) in enumerate(plan)
    ]
    return [SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=None, tool_calls=tc_deltas),
        finish_reason="tool_calls")])]


def _final_chunk(text):
    return [SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=text, tool_calls=None),
        finish_reason="stop")])]


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeCompletions:
    def __init__(self, factory):
        self._factory = factory
        self._n = 0

    def create(self, **kwargs):
        self._n += 1
        return _FakeStream(self._factory(self._n))


class _FakeClient:
    def __init__(self, factory):
        self.base_url = "http://fake"
        self.chat = SimpleNamespace(completions=_FakeCompletions(factory))


def test_query_ai_live_records_deliverable_read_during_tool_loop(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(state, run_id, "task_5_4", "phase_5", "task_5_4 成果物", "本文" + "X" * 500)

    def factory(n):
        if n == 1:
            return _chunks([("read_deliverable_file", {"task_id": "task_5_4"})])
        return _final_chunk("done")

    cela_main._reset_think_scratchpad()
    cela_main._LAST_DELIVERABLE_READ_TASK_IDS = []  # 直接_query_AI_liveを呼ぶテストのため手動リセット
    result = cela_main._query_AI_live(
        messages=[{"role": "user", "content": "go"}],
        client=_FakeClient(factory), model="fake", label="Expert",
        tools=[{"function": {"name": "read_deliverable_file"}}],
        light_system_prompt=None, state=state,
    )

    assert result == "done"
    assert cela_main.get_last_deliverable_reads() == ["task_5_4"]


def test_query_ai_wrapper_resets_deliverable_reads_alongside_python_calls():
    """[BL-242本体] `_query_AI_live`自身はターンをまたいだ状態をリセットしない設計
    （_LAST_PYTHON_CALLS等と同型で、呼び出し元の`query_AI`ラッパーがリセットを担う）。
    そのため、`_LAST_DELIVERABLE_READ_TASK_IDS`が`query_AI`のリセット対象globalリストに
    正しく含まれていることをソースで確認する（含まれていなければ、前のExpertターンの
    読み取り記録が次のターンへ誤って持ち越されてしまう）。"""
    src = inspect.getsource(cela_main.query_AI)
    assert "_LAST_DELIVERABLE_READ_TASK_IDS" in src
    reset_line = next(line for line in src.splitlines() if "_LAST_PYTHON_CALLS = []" in line)
    idx = src.index(reset_line)
    # global宣言の中に含まれているか（宣言行はreset_lineの直前にあるはず）
    global_decl = src[:idx].splitlines()[-1]
    assert "_LAST_DELIVERABLE_READ_TASK_IDS" in global_decl


# ---------------------------------------------------------------------------
# call_detectorのプロンプト構築ロジック（既存のBL-104/BL-126系テストと同様、ソース確認）
# ---------------------------------------------------------------------------

def test_call_detector_builds_deliverable_reads_gap_block_from_depends_on():
    """[§17.1向け存在証明] call_detectorのソースに、depends_onと
    expert_last_deliverable_readsの差分からdeliverable_reads_blockを構築し、
    最終プロンプトへ組み込む処理が実在すること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "expert_last_deliverable_reads" in src
    assert "_unread_deps" in src
    assert "deliverable_reads_block" in src
    assert "{deliverable_reads_block}" in src


def test_deliverable_reads_gap_block_does_not_force_turn_rejection():
    """[設計意図の確認] BL-242は警告のみで、ターンを機械的に差し戻す仕組み（BL-158型の
    constraint_issue強制上書き等）は持たないこと。BL-033のpython_repl版フェイルクローズ
    （"BL-033フェイルクローズ"という文字列で実装されている）と混同していないかを確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    # BL-242のブロック自体が"major"へ強制的に上書きするコードを含んでいないこと
    bl242_start = src.index("[BL-242]")
    bl242_related = src[bl242_start:bl242_start + 1500]
    assert 'result["constraint_issue"] = "major"' not in bl242_related
