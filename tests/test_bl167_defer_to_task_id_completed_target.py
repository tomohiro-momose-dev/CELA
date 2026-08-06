"""
BL-167: Reflection内のstagnant issue滞留検知が、defer_to_task_idの受け皿タスク完了後も
issueを永久に見落とし続ける。

BL-145の`_formalizable_stale`フィルタ（`not i.get("defer_to_task_id")`）は「既にdefer_to_task_id
が設定されている＝受け皿タスクが既にある」という前提で除外していたが、その受け皿タスクが実際に
完了したかどうかを一切検証していなかった。実ログ（`log/2026-08-04/1435`）で、
`defer_to_task_id="task_1_2"`が設定された「車両台数2台ではサービス要件を満たせない」issueが、
task_1_2が完了（Approved）した後も二度とタスク再構築の対象にならず、`verified_facts`（BL-168）
経由で旧ゴールの前提（車両単価2,500万円/台）が再構築後のプランに漏れ続ける実害につながった。

新規ヘルパー`_is_task_completed`（受け皿タスクがRESOLVING_DELIVERABLE_STATUSES相当かを判定）を
`_formalizable_stale`フィルタと`_get_forced_escalated_issues_text`（BL-136）の両方に配線し、
受け皿タスクが完了済みなのにissueが未解決のままの場合は「受け皿は失効した」とみなし再度
対象へ含めるようにした。

参照: docs/design/back_log/issue_backlog.md BL-167、BL-145、BL-136。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl167.db")
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


def _insert_deliverable(conn, run_id, task_id, status, seq=1):
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", status, f"{task_id}の成果物", "X" * 300, "r", "expert", "Deliverable",
         "phase_1", task_id, "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()


def _create_escalated_issue(conn, run_id, topic):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "後続タスクで検証が必要な事項", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )


# ---------------------------------------------------------------------------
# _is_task_completed 単体
# ---------------------------------------------------------------------------

def test_is_task_completed_false_when_no_deliverable(db_conn):
    conn, run_id = db_conn
    assert cela_main._is_task_completed(conn, run_id, "task_1_2") is False


def test_is_task_completed_true_when_approved_deliverable_exists(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_2", "Approved")
    assert cela_main._is_task_completed(conn, run_id, "task_1_2") is True


def test_is_task_completed_false_when_only_rejected_deliverable_exists(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_2", "Rejected")
    assert cela_main._is_task_completed(conn, run_id, "task_1_2") is False


def test_is_task_completed_uses_latest_status(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_2", "Approved", seq=1)
    _insert_deliverable(conn, run_id, "task_1_2", "Superseded", seq=2)
    assert cela_main._is_task_completed(conn, run_id, "task_1_2") is False


def test_is_task_completed_false_for_empty_task_id(db_conn):
    conn, run_id = db_conn
    assert cela_main._is_task_completed(conn, run_id, "") is False


# ---------------------------------------------------------------------------
# reflection_node の _formalizable_stale フィルタ
# ---------------------------------------------------------------------------

def _reflection_base_state(run_id, round_count):
    return {
        "risk_register": [], "goal": "g", "run_id": run_id, "round_count": round_count,
        "escalated_issue_first_seen_round": {},
    }


def _make_reflection_mock(monkeypatch):
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に見える。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)


def test_reflection_still_excludes_issue_deferred_to_incomplete_task(db_conn, monkeypatch):
    """回帰確認: 受け皿タスクがまだ未完了の場合は、従来通り除外され続けること（BL-145の想定通りの動作）。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "bl167_pending_target")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl167_pending_target", "defer_to_task_id": "task_1_2", "defer_reason": "後で見る"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]},
    )
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"
    assert state.get("plan_revision_issue_ids", []) == []


def test_reflection_includes_issue_once_deferred_target_task_completes(db_conn, monkeypatch):
    """BL-167の修正確認: 受け皿タスク(task_1_2)が完了済み（Approved）なのにissueが未解決の
    場合、受け皿は失効しているとみなし再度タスク再構築の対象へ含めること。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "bl167_completed_target")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl167_completed_target", "defer_to_task_id": "task_1_2", "defer_reason": "後で見る"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]},
    )
    _insert_deliverable(conn, run_id, "task_1_2", "Approved")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"
    assert "bl167_completed_target" in state["plan_revision_reason"]
    assert len(state["plan_revision_issue_ids"]) == 1


# ---------------------------------------------------------------------------
# _get_forced_escalated_issues_text（BL-136、User AIへの毎ターン強制解決プロンプト）
# ---------------------------------------------------------------------------

def test_forced_escalated_text_still_excludes_issue_deferred_to_incomplete_task(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "bl167_forced_pending")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl167_forced_pending", "defer_to_task_id": "task_1_2", "defer_reason": "後で見る"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]},
    )
    text = cela_main._get_forced_escalated_issues_text(conn, run_id)
    assert "bl167_forced_pending" not in text


def test_forced_escalated_text_includes_issue_once_deferred_target_task_completes(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "bl167_forced_completed")
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl167_forced_completed", "defer_to_task_id": "task_1_2", "defer_reason": "後で見る"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]},
    )
    _insert_deliverable(conn, run_id, "task_1_2", "Approved")
    text = cela_main._get_forced_escalated_issues_text(conn, run_id)
    assert "bl167_forced_completed" in text
