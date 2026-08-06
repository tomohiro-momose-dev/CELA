"""
BL-163: `revise_goal`成功時、既に承認済みの過去タスクは旧ゴールの前提のまま放置されていた。
ユーザーから「タスクを1_1からやり直させた方が良いか」との相談を受け、全面リスタートではなく、
既存のissue管理（BL-096）・SUPERSEDE改訂経路に乗せて前進しながら修正する方針を選択した
（AskUserQuestionでseverity=minor/open、既存の起票の仕組みに乗せるだけの小規模スコープを確認）。

`_revise_goal_tool_impl`が成功時、`get_agreements_from_db`から承認済み（`RESOLVING_DELIVERABLE_STATUSES`）
のDeliverableを持つ`(phase_id, task_id)`を機械的に列挙し、それぞれへ`raised_by="revise_goal_auto"`・
severity="minor"のissueを自動起票する。

過去タスクのagreements行は`write_agreement`経由ではなく直接INSERTでセットアップする
（`agreements.id`はミリ秒タイムスタンプ生成`f"AG-{int(time.time()*1000)}"`のため、
write_agreementを間を置かず連続実行すると同一idの行が複数でき、`get_agreements_from_db`の
`ORDER BY id`が新旧を安定して判別できなくなる——実運用ではLLM呼び出し等で十分な間隔が
空くため問題にならないが、テストでは決定論的な順序を明示IDで保証する）。

参照: docs/design/back_log/issue_backlog.md BL-163。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl163.db")
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
        cela_main._CURRENT_GOAL_TEXT = ""


def _insert_agreement_row(conn, run_id: str, seq: int, phase_id: str, task_id: str, topic: str,
                           status: str, entry_type: str = "Deliverable"):
    """[テスト専用] agreements行を直接INSERTする。連番`seq`をゼロ埋めしたidにすることで、
    `get_agreements_from_db`の`ORDER BY id`（文字列比較）が意図した時系列順に確実になる。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", status, topic, "X" * 300, "r", "expert", entry_type, phase_id, task_id,
         "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()
    return agreement_id


def _revise_goal(run_id: str, old_goal: str, new_text_pair: tuple[str, str]):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "予算と要件の構造的矛盾",
        "implicated_constraint": "台数上限",
        "why_conflicts_with_true_need": "要件を満たすには台数が不足",
        "suggested_reframe": "フェーズ分割方式へ変更",
    })["escalation_id"]

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = old_goal
    return cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": new_text_pair[0], "new_text": new_text_pair[1]}],
        "reason_why": "構造的矛盾の解消のため",
    })


def _issue_rows(conn, run_id):
    rows = conn.execute(
        "SELECT topic, raised_by, severity, status, phase_id, task_id FROM issue_log WHERE run_id=?", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def test_revise_goal_flags_approved_past_tasks_as_minor_open(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 2, "phase_1", "task_1_2", "task_1_2の成果物", "Approved_with_Conditions")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issues = _issue_rows(conn, run_id)
    topics = {i["topic"] for i in issues}
    assert "goal_revision_consistency_check_phase_1_task_1_1" in topics
    assert "goal_revision_consistency_check_phase_1_task_1_2" in topics
    for i in issues:
        if i["topic"].startswith("goal_revision_consistency_check_"):
            assert i["raised_by"] == "revise_goal_auto"
            assert i["severity"] == "minor"
            assert i["status"] == "open"


def test_revise_goal_does_not_flag_rejected_only_tasks(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Rejected")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issues = _issue_rows(conn, run_id)
    assert not any(i["topic"].startswith("goal_revision_consistency_check_") for i in issues)


def test_revise_goal_with_zero_completed_tasks_does_not_crash(db_conn):
    conn, run_id = db_conn
    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issues = _issue_rows(conn, run_id)
    assert not any(i["topic"].startswith("goal_revision_consistency_check_") for i in issues)


def test_revise_goal_flags_each_task_only_once_despite_multiple_updates(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Proposed")
    _insert_agreement_row(conn, run_id, 2, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 3, "phase_1", "task_1_1", "task_1_1の成果物", "Approved_with_Conditions")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issues = [i for i in _issue_rows(conn, run_id) if i["topic"].startswith("goal_revision_consistency_check_")]
    assert len(issues) == 1
    assert issues[0]["task_id"] == "task_1_1"


def test_revise_goal_flags_latest_status_when_superseded_after_approval(db_conn):
    """最新状態がSuperseded/Rejectedへ変わっていれば、承認済み過去タスクとしては対象外になること
    （dedupが最新行の状態のみを見ることの回帰確認）。"""
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 2, "phase_1", "task_1_1", "task_1_1の成果物", "Superseded")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issues = _issue_rows(conn, run_id)
    assert not any(i["topic"].startswith("goal_revision_consistency_check_") for i in issues)


def test_revise_goal_auto_role_is_registered_in_permission_table(db_conn):
    """raised_by='revise_goal_auto'のCREATEが権限エラーにならないこと（ALLOWED_ISSUE_ACTIONS_BY_ROLE確認）。"""
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "manual_check", "severity": "minor", "description": "d"},
        conn, run_id, "revise_goal_auto", "phase_1", "task_1_1",
    )
    assert result["success"] is True
