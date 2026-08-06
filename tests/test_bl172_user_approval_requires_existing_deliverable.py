"""
BL-172: BL-169は`caller_role=="user"`かつ`entry_type=="Deliverable"`かつ`action_type=="CREATE"`
の組み合わせのみを拒否していたが、実ドライラン`log/2026-08-04/2316`（行751-761）で、User AIが
これを拒否された直後、全く同じ内容のまま`entry_type`だけ`"Decision"`へ変えて再送し、そのまま
通ってしまう回避策が観測された。BL-169自体は正しく機能していたが、「userがExpertの仕事を代行
して完了を宣言する」という根本行動は防げていなかった。ホワイトボードファイル書き出し
（apply_whiteboard_patch）はentry_type="Deliverable"の時にしか発火しないため、この回避策では
ホワイトボード.mdが一切生成されないまま、タスクだけがApproved扱いになってDBに残っていた
（ユーザー報告「ホワイトボードや成果物のmdが生成されない」）。

修正: `_check_write_permission`に、「userがaction_type=CREATE・status=承認系（Approved等）で
書き込もうとしている場合、entry_typeを問わず、その`task_id`に対応するExpert作成のDeliverableが
実在しなければ拒否する」という一般化した分岐を追加した。正当なUserの承認は常に「既存
（Expert作成）のDeliverableをUPDATEでApproved等へ変更する」形を取るため、CREATEで承認系
statusのエントリを新規に持ち込む正規の使い方は存在しない。

参照: docs/design/back_log/issue_backlog.md BL-172、BL-169。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl172.db")
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


PHASES = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}]


def _write(conn, run_id, caller_role, **overrides):
    args = {
        "action_type": "CREATE", "status": "Approved", "topic": "task_1_1: 予算・車両調達制約の定量化",
        "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Decision",
        "task_id": "task_1_1", "phase_id": "phase_1",
    }
    args.update(overrides)
    return cela_main._write_agreement_impl(
        args, conn, run_id, caller_role, "task_1_1",
        phases=PHASES, pending_task_ids=[], effective_current_task_id="task_1_1", phase_id="phase_1",
    )


def test_user_cannot_bypass_bl169_by_relabeling_deliverable_as_decision(db_conn):
    """BL-169のDeliverable CREATE拒否直後、実ドライランで観測された『同一内容をentry_type=
    "Decision"へ変えて再送』という回避策が、今回のBL-172修正で塞がれていること（回帰の核心）。"""
    conn, run_id = db_conn
    result = _write(conn, run_id, "user", entry_type="Decision")
    assert result["success"] is False
    assert "task_1_1" in result["error"]

    rows = conn.execute("SELECT * FROM agreements WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 0


def test_user_still_cannot_create_deliverable_directly(db_conn):
    """BL-169の既存挙動（entry_type="Deliverable"のCREATE拒否）が引き続き機能すること。"""
    conn, run_id = db_conn
    result = _write(conn, run_id, "user", entry_type="Deliverable")
    assert result["success"] is False


def test_user_can_approve_after_expert_creates_deliverable(db_conn):
    """正当な流れ（Expertが先にDeliverableをCREATEし、Userがそれを承認）は無影響であること。
    UPDATEでの承認（entry_type="Deliverable"）と、承認記録用のDecision CREATEの両方を確認する。"""
    conn, run_id = db_conn
    expert_result = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1: 予算・車両調達制約の定量化",
            "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_1", "phase_id": "phase_1",
        },
        conn, run_id, "expert", "task_1_1",
        phases=PHASES, pending_task_ids=[], effective_current_task_id="task_1_1", phase_id="phase_1",
    )
    assert expert_result["success"] is True

    # Userが既存Deliverableを UPDATE で承認 -- 引き続き許可されるべき
    update_result = _write(conn, run_id, "user", action_type="UPDATE", entry_type="Deliverable")
    assert update_result["success"] is True

    # UserがDecision（CREATE）で承認記録を残す -- Deliverableが実在するので許可されるべき
    decision_result = _write(conn, run_id, "user", entry_type="Decision")
    assert decision_result["success"] is True


def test_user_can_still_create_proposed_decision_without_task_id(db_conn):
    """承認系statusでもtask_idでもない、通常のProposed/task_id無しのDecision CREATEは無影響。"""
    conn, run_id = db_conn
    result = _write(conn, run_id, "user", status="Proposed", task_id="", phase_id="")
    assert result["success"] is True


def test_user_rejecting_nonexistent_task_is_unaffected(db_conn):
    """承認系statusのみが対象。status="Rejected"（承認系ではない）はDeliverable不在でも
    このチェックの対象外（rejectedは元々ALLOWED_STATUS_BY_ROLEで許可されている挙動を維持）。"""
    conn, run_id = db_conn
    result = _write(conn, run_id, "user", status="Rejected")
    assert result["success"] is True


def test_check_write_permission_without_conn_skips_new_check():
    """conn未指定（既存の純粋呼び出し、BL-169のテスト等）では新チェックをスキップし
    従来通りの挙動を維持すること（後方互換の確認）。"""
    args = {"status": "Approved", "entry_type": "Decision", "action_type": "CREATE", "task_id": "task_1_1"}
    assert cela_main._check_write_permission(args, "user") is None
