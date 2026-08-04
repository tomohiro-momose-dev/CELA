"""
BL-131: `write_agreement`がtask_id/phase_idをtask_plannerの正式な計画（state["phases"]）と
一切照合しておらず、任意のtask_idで成果物が作れてしまう構造的リスクへの対応。

`log/2026-07-29/1322`・`1708`のドライランで、Facilitatorが提案した`task_1_1_review`という
正式計画に存在しないtask_idの下でExpertが本格的な成果物（244行・6バージョン→11バージョン）を
作成し続けてしまう事象が観測された。本テストは以下3点の実装を検証する:

1. entry_type='Directive'/'Deliverable'でtask_idがstate["phases"]に実在せず、
   pending_task_idsにも含まれない場合はエラーで拒否する。
2. pending_task_ids（BL-126のFacilitator対話が正式採用前に仮登録する許可リスト）に
   含まれていれば、正式計画に無くても許可する。
3. get_latest_whiteboard/get_latest_plan_draftは(phase_id, task_id)の組ではなくtask_id単独で
   検索する（誤ったphase_id指定で既存版が「該当なし」と誤判定されバージョンが1から
   再スタートする事故、1708ログのtask_1_1_review V9で観測、を防ぐ）。
4. UPDATE/SUPERSEDE（entry_type != 'Deliverable'）でtarget_topicが省略された場合、
   topicへの暗黙フォールバックによる空振り更新を防ぐため必須化する。

参照: docs/design/back_log/issue_backlog.md BL-131、
      docs/design/back_log/BL-126/BL126_basic_design.md §2.5。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl131.db")
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


# --- (1) task_id実在チェック ---

def test_directive_with_unknown_task_id_is_rejected(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "計画外タスクの成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1_review",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert result["success"] is False
    assert "task_1_1_review" in result["error"]
    assert "正式な計画に存在しません" in result["error"]


def test_directive_with_known_task_id_is_accepted(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "正規タスクの成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert result["success"] is True


def test_decision_entry_type_is_exempt_from_task_id_check(db_conn):
    """entry_type='Decision'（ゴール直下の全体決定）はタスクに紐づかない場合があるため対象外。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Approved", "topic": "全体方針の決定",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Decision",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert result["success"] is True


# --- (2) pending_task_idsによる許可リスト ---

def test_pending_task_id_is_accepted_even_if_not_in_formal_phases(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "本質対話由来の暫定成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1_review",
        },
        {"run_id": run_id, "phases": _PHASES, "pending_task_ids": ["task_1_1_review"]},
    )
    assert result["success"] is True


# --- (3) get_latest_whiteboard/get_latest_plan_draftのtask_id単独検索 ---

def test_get_latest_whiteboard_finds_existing_version_despite_wrong_phase_id(db_conn):
    """誤ったphase_idを渡しても、既存バージョンが「該当なし」と誤判定されず正しく見つかること
    （1708ログのtask_1_1_review V9で観測された「振り出しに戻る」事故の直接原因）。"""
    conn, run_id = db_conn
    v1 = cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1_review", "初版の内容", author_role="expert", edit_summary="初版作成",
    )
    assert v1 == 1

    # 誤ったphase_id（"phase_2"）を渡しても、task_id単独で既存版を発見できること。
    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_1_1_review")
    assert wb is not None and wb["version"] == 1 and wb["content"] == "初版の内容"

    # 誤ったphase_idのままapply_whiteboard_patchを呼んでも、version=1からの再スタートではなく
    # version=2として正しく継続されること。
    v2 = cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_1_1_review", "改版の内容", author_role="expert", edit_summary="改版",
    )
    assert v2 == 2, "誤ったphase_id指定によりバージョンが1から再スタートしてしまった（BL-131回帰）"


def test_get_latest_plan_draft_finds_existing_version_despite_wrong_phase_id(db_conn):
    """plan_drafts側も同型の修正が適用されていること。"""
    conn, run_id = db_conn
    v1 = cela_main.apply_plan_patch(
        conn, run_id, "phase_1", "task_1_1", "計画初版", author_role="task_planner", edit_summary="初版作成",
    )
    assert v1 == 1

    draft = cela_main.get_latest_plan_draft(conn, run_id, "phase_9", "task_1_1")
    assert draft is not None and draft["version"] == 1

    v2 = cela_main.apply_plan_patch(
        conn, run_id, "phase_9", "task_1_1", "計画改版", author_role="task_planner", edit_summary="改版",
    )
    assert v2 == 2, "誤ったphase_id指定によりバージョンが1から再スタートしてしまった（BL-131回帰）"


# --- (4) target_topic必須化 ---

def test_update_decision_without_target_topic_is_rejected(db_conn):
    """entry_type='Decision'はtask_id実在チェックの対象外のため、target_topic必須化のみを
    単独で検証できる（Directive/Deliverableだとtask_id不足エラーが先に出てしまうため）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "新しいtopic名",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Decision",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert result["success"] is False
    assert "target_topic" in result["error"]


def test_update_decision_with_target_topic_is_accepted(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    create_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Approved", "topic": "既存の決定事項",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Decision",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert create_result["success"] is True

    update_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "既存の決定事項",
            "target_topic": "既存の決定事項",
            "decision_what": "Y" * 500, "reason_why": "r", "entry_type": "Decision",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert update_result["success"] is True


def test_deliverable_update_is_exempt_from_target_topic_requirement(db_conn):
    """DeliverableはBL-084によりphase_id/task_idベースで識別されるため、target_topic必須化の対象外。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    state = {"run_id": run_id, "phases": _PHASES}
    create_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "成果物T",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert create_result["success"] is True

    update_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "成果物T",
            "decision_what": "Y" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert update_result["success"] is True
