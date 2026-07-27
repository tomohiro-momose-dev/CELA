"""
BL-101: task_plannerに「フェーズ・タスク表」ホワイトボード（plan_drafts）を読む
read_plan_draftツールを配線する。

実ドライラン（log/2026-07-27/1438）で、task_plan_reviewerに差し戻されたtask_plannerが、
前回自分が作成したフェーズ・タスク表のホワイトボード（plan_drafts、BL-082/BL-087 Stage2）を
一切参照せず、ゴール文と差し戻し指摘の要約テキストだけを頼りに毎回全フェーズ・全タスクを
一から作り直している実例が観測された。task_planner_nodeの再生成呼び出し
（call_task_planner）にも、task_plan_reviewer由来の`## レビュワーからの指摘（要修正）`が
書き込まれた最新のホワイトボード内容そのものは渡っていなかった。

対策として、task_planner自身が能動的に確認できる読み取り専用ツール`read_plan_draft`を
新設し、差し戻し時のプロンプトで「指摘のあったtask_idについては必ずこのツールで前回の
記述を確認してから修正する」よう指示した。

参照: docs/design/back_log/issue_backlog.md BL-101、docs/design/decision_log.md。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl101_plan_draft_tool.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        conn.close()


def test_get_latest_plan_draft_by_task_id_finds_without_phase_id(db_conn):
    conn, run_id = db_conn
    cela_main.apply_plan_patch(
        conn, run_id, "phase_2", "task_2_3", "初期スケルトン", author_role="task_planner",
        edit_summary="初期計画生成",
    )
    result = cela_main.get_latest_plan_draft_by_task_id(conn, run_id, "task_2_3")
    assert result is not None
    assert result["phase_id"] == "phase_2"
    assert result["content"] == "初期スケルトン"


def test_get_latest_plan_draft_by_task_id_returns_latest_version(db_conn):
    conn, run_id = db_conn
    cela_main.apply_plan_patch(
        conn, run_id, "phase_1", "task_1_1", "版1", author_role="task_planner", edit_summary="初回",
    )
    cela_main.apply_plan_patch(
        conn, run_id, "phase_1", "task_1_1", "版2（レビュワー指摘反映済み）", author_role="task_plan_reviewer",
        edit_summary="指摘追記",
    )
    result = cela_main.get_latest_plan_draft_by_task_id(conn, run_id, "task_1_1")
    assert result["content"] == "版2（レビュワー指摘反映済み）"


def test_get_latest_plan_draft_by_task_id_not_found(db_conn):
    conn, run_id = db_conn
    result = cela_main.get_latest_plan_draft_by_task_id(conn, run_id, "task_nonexistent")
    assert result is None


def test_read_plan_draft_handler_returns_content(db_conn):
    conn, run_id = db_conn
    cela_main.apply_plan_patch(
        conn, run_id, "phase_3", "task_3_1", "タスク3-1の記述", author_role="task_planner",
        edit_summary="初期計画生成",
    )
    result = cela_main._read_plan_draft_handler({"task_id": "task_3_1"})
    assert result["content"] == "タスク3-1の記述"
    assert result["phase_id"] == "phase_3"


def test_read_plan_draft_handler_not_found(db_conn):
    result = cela_main._read_plan_draft_handler({"task_id": "task_nonexistent"})
    assert result["status"] == "not_found"


def test_read_plan_draft_handler_missing_task_id(db_conn):
    result = cela_main._read_plan_draft_handler({})
    assert result["status"] == "error"


def test_tool_dispatch_has_read_plan_draft():
    assert "read_plan_draft" in cela_main.TOOL_DISPATCH


def test_call_task_planner_passes_read_plan_draft_tool():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "READ_PLAN_DRAFT_TOOL" in src
    assert "BL-101" in src
    assert "read_plan_draft" in src
