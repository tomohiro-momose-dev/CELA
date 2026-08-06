"""
BL-169: `write_agreement`の権限チェックが`status`しか見ておらず、role×(entry_type, action_type)の
組み合わせを一切制限していなかったため、User AI（発注者役）がExpertを介さず
entry_type="Deliverable", action_type="CREATE"で成果物そのものを自作・自己提出できてしまう。

実ログ`log/2026-08-04/1548`（BL-166〜168修正後のドライラン再開分）で、task_1_3の4回目（最終）
リトライ中、User AIが11回のpython_repl計算の末にwrite_agreement(entry_type="Deliverable",
action_type="CREATE", status="Proposed", task_id="task_1_3", ...)を自ら呼び出して財務モデル
成果物を丸ごと執筆・提出し、直後の発言で受入基準を自己採点して✅と宣言、Expertを介さず次タスク
task_2_1への移行を一方的に指示するに至った（`verified_facts`の更新ログにも`by=user`）。
Detector（Domain Review）が今回はたまたま`major`判定で捕捉したが、`_check_write_permission`
（cela_main.py:1859）はstatusのみで判定しておりrole×entry_typeの制限が無いため、
Detectorが見逃せば「Userが自分で書いた成果物をUserが自分で承認する」完全な自作自演が
ノーチェックで通ってしまう構造だった。Reflectionはこれを"User is approving defective
deliverables (collusion)"と判定し、最終的にシステムはstagnant→haltに至った。

修正: `_check_write_permission`に、caller_role=="user" かつ entry_type=="Deliverable" かつ
action_type=="CREATE" の組み合わせを拒否する分岐を追加した（UPDATE/SUPERSEDEによる既存
Deliverableへのstatus変更・訂正指示は従来通り許可、Expertによる新規作成は無影響）。

参照: docs/design/back_log/issue_backlog.md BL-169、BL-166、BL-167、BL-168。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# _check_write_permission 単体（DB接続不要の純粋関数）
# ---------------------------------------------------------------------------

def test_user_cannot_create_deliverable():
    args = {"status": "Proposed", "entry_type": "Deliverable", "action_type": "CREATE"}
    error = cela_main._check_write_permission(args, "user")
    assert error is not None
    assert "Deliverable" in error
    assert "CREATE" in error


def test_user_can_update_existing_deliverable_to_approved():
    args = {"status": "Approved", "entry_type": "Deliverable", "action_type": "UPDATE"}
    assert cela_main._check_write_permission(args, "user") is None


def test_user_can_reject_existing_deliverable():
    args = {"status": "Rejected", "entry_type": "Deliverable", "action_type": "UPDATE"}
    assert cela_main._check_write_permission(args, "user") is None


def test_user_can_supersede_deliverable():
    args = {"status": "Rejected", "entry_type": "Deliverable", "action_type": "SUPERSEDE"}
    assert cela_main._check_write_permission(args, "user") is None


def test_user_can_still_create_decision():
    """Deliverable以外のentry_type（Decision等）は従来通りuserのCREATEを許可する。"""
    args = {"status": "Proposed", "entry_type": "Decision", "action_type": "CREATE"}
    assert cela_main._check_write_permission(args, "user") is None


def test_expert_can_still_create_deliverable():
    """Expert（本来の成果物作成者）は無影響であること。"""
    args = {"status": "Proposed", "entry_type": "Deliverable", "action_type": "CREATE"}
    assert cela_main._check_write_permission(args, "expert") is None


# ---------------------------------------------------------------------------
# _write_agreement_impl（TOOL_DISPATCH経由の実行パス）
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl169.db")
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


def test_write_agreement_impl_rejects_user_create_deliverable(db_conn):
    conn, run_id = db_conn
    phases = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_3"}]}]
    result = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_3 成果物",
            "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_3", "phase_id": "phase_1",
        },
        conn, run_id, "user", "task_1_3",
        phases=phases, pending_task_ids=[], effective_current_task_id="task_1_3", phase_id="phase_1",
    )
    assert result["success"] is False
    assert "Deliverable" in result["error"]

    rows = conn.execute("SELECT * FROM agreements WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 0


def test_write_agreement_impl_still_allows_expert_create_deliverable(db_conn):
    conn, run_id = db_conn
    phases = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_3"}]}]
    result = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_3 成果物",
            "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_3", "phase_id": "phase_1",
        },
        conn, run_id, "expert", "task_1_3",
        phases=phases, pending_task_ids=[], effective_current_task_id="task_1_3", phase_id="phase_1",
    )
    assert result["success"] is True


def test_write_agreement_impl_still_allows_user_to_approve_expert_deliverable(db_conn):
    """回帰確認: Userが既存（Expert作成）のDeliverableを承認するUPDATEは従来通り通ること。"""
    conn, run_id = db_conn
    phases = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_3"}]}]
    create_result = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_3 成果物",
            "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_3", "phase_id": "phase_1",
        },
        conn, run_id, "expert", "task_1_3",
        phases=phases, pending_task_ids=[], effective_current_task_id="task_1_3", phase_id="phase_1",
    )
    assert create_result["success"] is True

    approve_result = cela_main._write_agreement_impl(
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "task_1_3 成果物",
            "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_3", "phase_id": "phase_1",
        },
        conn, run_id, "user", "task_1_3",
        phases=phases, pending_task_ids=[], effective_current_task_id="task_1_3", phase_id="phase_1",
    )
    assert approve_result["success"] is True
