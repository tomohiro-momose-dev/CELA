"""
BL-248: Task Plan Reviewerが、task_plannerの分解の判断根拠を取得できず4回連続で
失敗していた問題（log/2026-08-16/1443・1512、run_id=1786859005-bc524117）。

BL-095は、task_plannerへ「write_agreement（entry_type="Decision", topic=
"task_planner_phase_design"）で分解の判断根拠を書き残す」よう指示する一方、
task_plan_reviewerへは「read_deliverable_file（task_planner_phase_design）で確認する」
よう指示していた。しかしread_deliverable_file（_resolve_deliverable_pointer、BL-084/
BL-241で確立）はentry_type="Deliverable"かつFILE_PATH:/WHITEBOARD:ポインタを持つ行だけを
対象とする設計であり、entry_type="Decision"のこの行は構造的に一致せず、実ログで
"task_id 'task_planner_phase_design' はtask_plannerの正式な計画に存在しません"という
エラーで4回連続失敗していた。

修正は「別のツールを呼ばせる」のではなく、そもそも1件しかない固定topicの値をPython側で
直接取得し、call_task_plan_reviewerのプロンプトへツール呼び出し無しで埋め込む
（current_task_json等と同型の既存パターン）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-248。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl248.db")
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


def _write_phase_design_decision(run_id, decision_what, reason_why):
    cela_main._CURRENT_CALLER_ROLE = "task_planner"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_planner_phase_design",
            "decision_what": decision_what, "reason_why": reason_why, "entry_type": "Decision",
        },
        {"run_id": run_id, "phases": []},
    )
    assert result["success"] is True


def test_no_recorded_rationale_returns_placeholder(db_conn):
    conn, run_id = db_conn
    text = cela_main._get_task_planner_phase_design_rationale_text(conn, run_id)
    assert "まだ" in text


def test_recorded_rationale_is_returned(db_conn):
    conn, run_id = db_conn
    _write_phase_design_decision(run_id, "5フェーズに分割した", "需要・道路・冬季・財務・実証を独立に検証するため")
    text = cela_main._get_task_planner_phase_design_rationale_text(conn, run_id)
    assert "5フェーズに分割した" in text
    assert "需要・道路・冬季・財務・実証を独立に検証するため" in text


def test_latest_rationale_wins_on_replan(db_conn):
    """再分解のたびにtopic="task_planner_phase_design"のDecisionが積み上がるため、
    最新の1件のみが返ること。"""
    conn, run_id = db_conn
    _write_phase_design_decision(run_id, "初版：4フェーズ", "初版の理由")
    _write_phase_design_decision(run_id, "再分解版：5フェーズ", "再分解の理由")
    text = cela_main._get_task_planner_phase_design_rationale_text(conn, run_id)
    assert "再分解版：5フェーズ" in text
    assert "初版：4フェーズ" not in text


def test_call_task_plan_reviewer_embeds_rationale_without_tool_call():
    """[BL-248本体] call_task_plan_reviewerのソースが、_get_task_planner_phase_design_
    rationale_textをPython側で呼び出しプロンプトへ直接埋め込んでいること。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "_get_task_planner_phase_design_rationale_text" in src
    assert "task_plannerが記録した分解の判断根拠" in src


def test_call_task_plan_reviewer_no_longer_instructs_broken_read_deliverable_file_call():
    """回帰確認: 「read_deliverable_file（task_planner_phase_design）で確認」という、
    entry_type不一致で常に失敗する壊れた指示文が残っていないこと。SUPERSEDE指示自体は
    維持されていること。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "read_deliverable_file（task_planner_phase_design）でtask_plannerが記録した" not in src
    assert "SUPERSEDE" in src
    assert "task_planner_phase_design" in src


def test_bl248_helper_present_in_source():
    """§17.1後段: 実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(cela_main._get_task_planner_phase_design_rationale_text)
    assert 'entry_type") == "Decision"' in src
    assert 'topic") == "task_planner_phase_design"' in src
