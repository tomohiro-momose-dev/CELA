"""
BL-194: 自己先送り（defer_to_task_id==実行中タスク自身）のtool boundary拒否と、
その代償として同時導入したACKNOWLEDGE（第三の正直な選択肢）。

`log/2026-08-08/1514`で、滞留escalated issue20件中6件が`task_2_1`自身への先送り（自己先送り）
だった。DEFERの実装は受け皿task_idの実在チェックのみで自己参照を禁じておらず、「督促されるが
是正経路は全て沈黙する」不死身のissueを生んでいた。自己先送りをtool boundaryで拒否すると
BL-158の機械的差し戻しゲートが再発火するため、正直な出口（ACKNOWLEDGE）を同時導入する
（BL194_basic_design.md §3.2〜§5、D-164/D-165）。

`_BL194_ACK_TTL_ROUNDS=3`/`_BL194_ACK_MAX_GRANTS=2`はAGENTS.md §7に基づきユーザー承認済み。

参照: docs/design/back_log/issue_backlog.md BL-194、
      docs/design/back_log/BL-194/BL194_basic_design.md。
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
    db_path = str(tmp_path / "test_bl194_ack.db")
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


PHASES_1_2 = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]


def _create_escalated_issue(conn, run_id, topic, task_id="task_1_1"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "後続タスクで検証が必要な事項", "severity": "major"},
        conn, run_id, "detector", "", task_id,
    )


def _acknowledge(conn, run_id, topic, round_count=0, caller_role="user"):
    return cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": topic, "ack_reason": "現在タスクの責務であり対応中"},
        conn, run_id, caller_role, "", "task_1_1", state={"round_count": round_count},
    )


# ===========================================================================
# マイグレーション冪等性
# ===========================================================================

def test_migration_adds_three_ack_columns_idempotently(db_conn):
    conn, run_id = db_conn
    cela_main.init_db(conn)  # 2回目
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    assert {"acknowledged_until_round", "acknowledged_count", "acknowledge_reason"} <= cols


# ===========================================================================
# 自己先送りの拒否（S8）
# ===========================================================================

def test_self_deferral_rejected_with_acknowledge_hint(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "s1")
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "s1", "defer_to_task_id": "task_1_1", "defer_reason": "理由"},
        conn, run_id, "user", "", "task_1_1", state={"phases": PHASES_1_2},
    )
    assert result["success"] is False
    assert "ACKNOWLEDGE" in result["error"]


def test_self_deferral_rejection_leaves_defer_to_task_id_unchanged(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "s2")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "s2", "defer_to_task_id": "task_1_1", "defer_reason": "理由"},
        conn, run_id, "user", "", "task_1_1", state={"phases": PHASES_1_2},
    )
    row = conn.execute("SELECT defer_to_task_id FROM issue_log WHERE run_id=? AND topic='s2'", (run_id,)).fetchone()
    assert row["defer_to_task_id"] == ""


def test_self_deferral_rejection_does_not_pollute_plan_drafts(db_conn):
    """拒否時にplan_draftsが汚染されない（_append_deferred_note_to_planが呼ばれない）ことの確認。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "s3")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "s3", "defer_to_task_id": "task_1_1", "defer_reason": "理由"},
        conn, run_id, "user", "", "task_1_1", state={"phases": PHASES_1_2},
    )
    draft = conn.execute(
        "SELECT * FROM plan_drafts WHERE run_id=? AND task_id='task_1_1'", (run_id,)
    ).fetchone()
    assert draft is None


def test_non_self_deferral_still_succeeds(db_conn):
    """自己先送り拒否の追加が、正当な他タスクへのDEFERを壊していないことの確認。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "s4")
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "s4", "defer_to_task_id": "task_1_2", "defer_reason": "理由"},
        conn, run_id, "user", "", "task_1_1", state={"phases": PHASES_1_2},
    )
    assert result["success"] is True


# ===========================================================================
# ACKNOWLEDGE 基本動作（S7）
# ===========================================================================

def test_acknowledge_success_keeps_status_and_severity_unchanged_d079_d080(db_conn):
    """[D-079/D-080の回帰テスト] ACKNOWLEDGE成功でもstatus='escalated'/severity='major'は不変。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "t1")
    result = _acknowledge(conn, run_id, "t1", round_count=0)
    assert result["success"] is True
    row = conn.execute("SELECT status, severity FROM issue_log WHERE run_id=? AND topic='t1'", (run_id,)).fetchone()
    assert row["status"] == "escalated"
    assert row["severity"] == "major"


def test_acknowledge_sets_ttl_and_increments_count(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "t2")
    result = _acknowledge(conn, run_id, "t2", round_count=5)
    assert result["acknowledged_until_round"] == 5 + cela_main._BL194_ACK_TTL_ROUNDS
    assert result["remaining_grants"] == cela_main._BL194_ACK_MAX_GRANTS - 1
    row = conn.execute("SELECT acknowledged_count FROM issue_log WHERE run_id=? AND topic='t2'", (run_id,)).fetchone()
    assert row["acknowledged_count"] == 1


def test_acknowledge_rejected_for_open_status(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "t3", "description": "d", "severity": "minor"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = _acknowledge(conn, run_id, "t3")
    assert result["success"] is False


def test_acknowledge_rejected_when_topic_not_found(db_conn):
    conn, run_id = db_conn
    result = _acknowledge(conn, run_id, "nonexistent")
    assert result["success"] is False


def test_acknowledge_rejected_without_ack_reason(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "t4")
    result = cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": "t4"},
        conn, run_id, "user", "", "task_1_1", state={"round_count": 0},
    )
    assert result["success"] is False


def test_third_acknowledge_rejected_and_suggests_resolve_or_defer(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "t5")
    assert _acknowledge(conn, run_id, "t5", round_count=0)["success"] is True
    assert _acknowledge(conn, run_id, "t5", round_count=0)["success"] is True
    third = _acknowledge(conn, run_id, "t5", round_count=0)
    assert third["success"] is False
    assert "RESOLVE" in third["error"]
    assert "DEFER" in third["error"]


def test_acknowledge_role_restricted_to_user(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "t6")
    for role in ("detector", "detector_auto", "decision_extractor_auto", "revise_goal_auto"):
        result = _acknowledge(conn, run_id, "t6", caller_role=role)
        assert result["success"] is False, f"{role} should not be allowed to ACKNOWLEDGE"


# ===========================================================================
# 消費者側の抑制（万能の逃げ道化防止）
# ===========================================================================

def test_forced_escalated_text_excludes_acknowledged(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u1")
    _acknowledge(conn, run_id, "u1", round_count=1)
    text = cela_main._get_forced_escalated_issues_text(conn, run_id, "task_1_1", round_count=1)
    assert "u1" not in text


def test_blocking_issues_for_transition_ignores_acknowledged_by_default(db_conn):
    """[逃げ道化防止の核心] 離脱ゲート本体（既定exclude_acknowledged=False）は、
    ACKNOWLEDGE中でも未解決のまま離脱させない。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u2")
    _acknowledge(conn, run_id, "u2", round_count=1)
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert any(r["topic"] == "u2" for r in blocking)


def test_blocking_issues_for_transition_excludes_acknowledged_when_requested(db_conn):
    """BL-158の機械的差し戻し（督促経路）だけがexclude_acknowledged=Trueを使う。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u3")
    _acknowledge(conn, run_id, "u3", round_count=1)
    blocking = cela_main._get_blocking_issues_for_transition(
        conn, run_id, "task_1_1", exclude_acknowledged=True, round_count=1
    )
    assert not any(r["topic"] == "u3" for r in blocking)


def test_acknowledge_expires_after_ttl_and_resumes_blocking_and_stagnation(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u4")
    _acknowledge(conn, run_id, "u4", round_count=0)  # 有効: round 0〜3
    # TTL内（round=2）はまだ抑制される
    still_suppressed = cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1", round_count=2)
    assert not any(r["topic"] == "u4" for r in still_suppressed)
    # TTL経過後（round=3、acknowledged_until_round=3なので3>3はFalse=失効）は督促に復帰
    revived = cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1", round_count=3)
    assert any(r["topic"] == "u4" for r in revived)


def test_reoccurrence_resets_acknowledge_ttl(db_conn):
    """[不死身化防止の最重要ガード] ACK中に同topicが再発（CREATE）すると
    acknowledged_until_roundが即座に0へリセットされる。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u5")
    _acknowledge(conn, run_id, "u5", round_count=0)
    row = conn.execute("SELECT acknowledged_until_round FROM issue_log WHERE run_id=? AND topic='u5'", (run_id,)).fetchone()
    assert row["acknowledged_until_round"] > 0
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "u5", "description": "再発しました", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    row = conn.execute("SELECT acknowledged_until_round FROM issue_log WHERE run_id=? AND topic='u5'", (run_id,)).fetchone()
    assert row["acknowledged_until_round"] == 0


def test_defer_success_resets_acknowledge_ttl(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "u6")
    _acknowledge(conn, run_id, "u6", round_count=0)
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "u6", "defer_to_task_id": "task_1_2", "defer_reason": "やはり別タスクの責務"},
        conn, run_id, "user", "", "task_1_1", state={"phases": PHASES_1_2},
    )
    row = conn.execute("SELECT acknowledged_until_round FROM issue_log WHERE run_id=? AND topic='u6'", (run_id,)).fetchone()
    assert row["acknowledged_until_round"] == 0
