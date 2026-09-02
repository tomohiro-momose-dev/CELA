"""
BL-147: `read_deliverable_file`は`write_agreement`（BL-131）と異なりtask_idの実在チェックを
一切行っておらず、存在しないtask_idでも素通りしていた。特にtask_idとfile_pathを同時指定した
場合、task_idの実在チェックが一切行われないままfile_path側の読み込みに進んでしまい、
「存在しないtask_idを指定しつつfile_pathで読み込みを通過させる」抜け道になっていた。

本テストは以下を検証する:
1. task_idがtask_plannerの正式な計画（state["phases"]）にもpending_task_idsにも実在しない場合は
   拒否する。
2. 上記(1)の状態でfile_pathが同時指定されていても、task_idの実在チェックが優先され拒否される
   （抜け道の再現・修正確認）。
3. task_idが実在するが該当タスクにまだDeliverableが無い場合は、従来通りnot_foundを返す
   （このゲートによる過剰な制限が無いことの確認）。
4. 実在する他タスク（現在のタスクではない）の成果物への参照読みは引き続き許可される
   （本ツールの本来の目的である「他タスクの成果物を参照読みする」用途を制限しないこと）。
5. pending_task_ids（BL-126のFacilitator対話が正式採用前に仮登録する許可リスト）に含まれていれば
   許可する（BL-131と同型）。

参照: docs/design/back_log/issue_backlog.md BL-147。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl147.db")
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
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
]


def test_unknown_task_id_is_rejected(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_9_9_nonexistent"}, state,
    )
    assert result["status"] == "error"
    assert "task_9_9_nonexistent" in result["message"]
    assert "正式な計画に存在しません" in result["message"]


def test_unknown_task_id_is_rejected_even_with_file_path_supplied(db_conn):
    """task_idとfile_pathを同時指定した場合の抜け道が塞がれていること。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_9_9_nonexistent", "file_path": "log/2026-01-01/0000/whiteboards/anything.md"},
        state,
    )
    assert result["status"] == "error"
    assert "task_9_9_nonexistent" in result["message"]


def test_known_task_id_without_deliverable_yet_returns_not_found(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_1_1"}, state,
    )
    assert result["status"] == "not_found"


def test_reading_other_existing_task_deliverable_is_still_allowed(db_conn):
    """実在する他タスクの成果物への参照読みは制限しない（本来の目的）。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    write_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_2の成果物",
            "decision_what": "task_1_2の成果物本文" + "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_2",
        },
        state,
    )
    assert write_result["success"] is True

    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_1_2"}, state,
    )
    # [BL-289] ホワイトボード経路はdict化され、author_role/edit_summary/timestamp/draft_idも返る
    assert isinstance(result, dict)
    assert "task_1_2の成果物本文" in result["content"]


def test_pending_task_id_is_accepted_even_if_not_in_formal_phases(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "pending_task_ids": ["task_1_1_review"]}
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_1_1_review"}, state,
    )
    assert result["status"] == "not_found"  # 実在チェックは通過し、成果物が無いだけ


def test_no_task_id_no_topic_keyword_falls_through_to_missing_argument_error(db_conn):
    """task_id自体が指定されない従来のtopic_keyword/file_path単独パスは、
    このゲートの追加によって影響を受けないこと。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {}, state,
    )
    assert result["status"] == "error"
    assert "いずれかを指定してください" in result["message"]
