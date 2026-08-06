"""
BL-136 / BL-125: issue_logの可視性強化とタスク遷移ゲート。

`log/2026-07-30/1236`のレビューで、issue_logが「起票されるが解決されない」状態
（7件中0件がresolved）であることが判明した。原因は2点の設計上の非対称性:

1. 可視性の非対称: status='escalated'行だけが毎ターン自動表示され、status='open'
   （minor）行はread_issuesを能動的に呼ばない限り見えなかった。
2. 強制力の非対称: BL-086の前提エスカレーションには「今回の発言内で必ず解決して
   ください」という強制文言があるが、issue_logのRESOLVE指示は条件付き・任意だった。

さらにBL-134（Expertが24時間365日前提を無根拠に確定値化し、Detectorがmajor
エスカレーションしたのに未解決のままtask進行を許してしまった）の再発防止として、
`_resolve_task_transition`（BL-024の唯一の書き手）に、未解決・未先送りのsevere
issueによるタスク遷移ゲート（BL-125）を追加した。

BL-082の申し送り（Directive/status=Deferred/defer_to_task_id）と同じ思想で、
issue_logにも`write_issue(action_type="DEFER", ...)`を追加し、「今すぐ解決」と
「明示的に将来のtaskへ先送り」の二択をUser AIに与える（強制解決一辺倒による
無期限ブロックを避けるため）。

参照: docs/design/back_log/issue_backlog.md BL-125/BL-134/BL-136、
docs/design/decision_log.md D-xxx。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl136.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


_TASK_1_1 = {
    "task_id": "task_1_1", "title": "初期整理",
    "description": "初期の整理を行う。",
    "acceptance_criteria": ["整理済みであること"],
    "depends_on": [], "owns_variables": [],
}
_TASK_1_2 = {
    "task_id": "task_1_2", "title": "詳細分析",
    "description": "詳細な分析を行う。",
    "acceptance_criteria": ["分析済みであること"],
    "depends_on": ["task_1_1"], "owns_variables": [],
}
_PHASE_1 = {"phase_id": "phase_1", "tasks": [_TASK_1_1, _TASK_1_2]}


def _insert_approved_deliverable(conn, run_id, task_id, seq=1):
    """[BL-176] _resolve_task_transitionは離脱先task_idにApproved相当のDeliverableが
    無いと遷移をブロックするため、遷移元task_idの承認成立をテスト側で用意する。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", "Approved", f"{task_id}の成果物", "X" * 300, "r", "expert", "Deliverable",
         "phase_1", task_id, "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()


def _base_state(run_id: str, current_task_id: str = "task_1_1") -> dict:
    return {
        "run_id": run_id,
        "phases": [_PHASE_1],
        "current_phase": _PHASE_1,
        "current_task_id": current_task_id,
        "task_transition_blocked_issue_topics": [],
    }


# --- Part A: _get_open_issues / _build_open_issue_pin_text ---

def test_get_open_issues_returns_only_open(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_open_a", "description": "軽微な懸念"},
        conn, run_id, "detector", "", "task_1_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_escalated_a", "description": "重大な懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    results = cela_main._get_open_issues(conn, run_id)
    topics = {r["topic"] for r in results}
    assert "bl136_open_a" in topics
    assert "bl136_escalated_a" not in topics


def test_build_open_issue_pin_text_formats_open_rows(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_open_b", "description": "参考情報として出るべき懸念"},
        conn, run_id, "detector", "", "task_1_1",
    )
    text = cela_main._build_open_issue_pin_text(conn, run_id)
    assert "bl136_open_b" in text
    assert "参考情報として出るべき懸念" in text


def test_build_open_issue_pin_text_empty_when_none(db_conn):
    conn, run_id = db_conn
    assert cela_main._build_open_issue_pin_text(conn, run_id) == ""


def test_call_expert_and_generate_user_utterance_inject_open_issue_pin():
    expert_src = inspect.getsource(cela_main.call_expert)
    user_src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_open_issue_pin_text" in expert_src
    assert "_build_open_issue_pin_text" in user_src


# --- Part B: write_issue DEFER action ---

def test_user_can_defer_detector_cannot():
    assert cela_main._check_issue_permission({"action_type": "DEFER"}, "user") is None
    error = cela_main._check_issue_permission({"action_type": "DEFER"}, "detector")
    assert error is not None


def test_defer_requires_defer_to_task_id(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_defer_a", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_defer_a", "defer_reason": "後で対応"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is False


def test_defer_requires_defer_reason(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_defer_b", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_defer_b", "defer_to_task_id": "task_1_2"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is False


def test_defer_requires_existing_issue(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_no_such_topic",
         "defer_to_task_id": "task_1_2", "defer_reason": "理由"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is False


def test_defer_invalid_task_id_fails(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_defer_c", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_defer_c",
         "defer_to_task_id": "task_nonexistent", "defer_reason": "理由"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is False


def test_defer_success_sets_column_and_appends_plan_note(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_defer_d", "description": "24h/365dの前提疑義",
         "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_defer_d",
         "defer_to_task_id": "task_1_2", "defer_reason": "詳細分析タスクで再検討する"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl136_defer_d")
    ).fetchone()
    assert row["defer_to_task_id"] == "task_1_2"
    # statusは変更されない（解決済みにはならない）
    assert row["status"] == "escalated"

    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_1", "task_1_2")
    assert latest is not None
    assert "bl136_defer_d" in latest["content"]
    assert "詳細分析タスクで再検討する" in latest["content"]


def test_defer_normalizes_dotted_task_id(db_conn):
    """[BL-039踏襲] 'task_1.2'のようなドット区切りもアンダースコア正規化して受理する。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_defer_e", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_defer_e",
         "defer_to_task_id": "task_1.2", "defer_reason": "理由"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl136_defer_e")
    ).fetchone()
    assert row["defer_to_task_id"] == "task_1_2"


# --- Part C: 強制解決文言 ---

def test_get_forced_escalated_issues_text_includes_escalated_without_defer(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_forced_a", "description": "対応必須の懸念",
         "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    text = cela_main._get_forced_escalated_issues_text(conn, run_id)
    assert "bl136_forced_a" in text
    assert "RESOLVE" in text
    assert "DEFER" in text


def test_get_forced_escalated_issues_text_excludes_deferred(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl136_forced_b", "description": "既に先送り済みの懸念",
         "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl136_forced_b",
         "defer_to_task_id": "task_1_2", "defer_reason": "後続タスクで対応"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    text = cela_main._get_forced_escalated_issues_text(conn, run_id)
    assert "bl136_forced_b" not in text


def test_get_forced_escalated_issues_text_empty_when_none(db_conn):
    conn, run_id = db_conn
    assert cela_main._get_forced_escalated_issues_text(conn, run_id) == ""


def test_generate_user_utterance_injects_forced_escalated_issues_text():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_get_forced_escalated_issues_text" in src


# --- Part D: BL-125 タスク遷移ゲート ---

def test_get_blocking_issues_for_transition_returns_major_escalated_for_task(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl125_block_a", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert len(blocking) == 1
    assert blocking[0]["topic"] == "bl125_block_a"


def test_get_blocking_issues_for_transition_excludes_minor(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl125_minor_a", "description": "軽微な懸念"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []


def test_get_blocking_issues_for_transition_excludes_deferred(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl125_deferred_a", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl125_deferred_a",
         "defer_to_task_id": "task_1_2", "defer_reason": "後で"},
        conn, run_id, "user", "", "", state=_base_state(run_id),
    )
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []


def test_get_blocking_issues_for_transition_excludes_other_task(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl125_other_task", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_2",
    )
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []


def test_resolve_task_transition_blocks_when_major_issue_unresolved(db_conn):
    """[BL-134再現] severity=major・status=escalatedのissueが未解決のまま
    task_1_1→task_1_2への遷移を試みると、ブロックされcurrent_task_idは変わらない。"""
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "bl134_repro", "description": "24h/365d前提の疑義",
             "severity": "major"},
            conn, run_id, "detector", "phase_1", "task_1_1",
        )
        state = _base_state(run_id, current_task_id="task_1_1")
        cela_main._resolve_task_transition(
            state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
        )
        assert state["current_task_id"] == "task_1_1"
        assert "bl134_repro" in state["task_transition_blocked_issue_topics"]
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def test_resolve_task_transition_allows_when_resolved(db_conn):
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "bl125_resolved_a", "description": "懸念", "severity": "major"},
            conn, run_id, "detector", "phase_1", "task_1_1",
        )
        cela_main._write_issue_impl(
            {"action_type": "RESOLVE", "topic": "bl125_resolved_a", "resolution_note": "解決済み"},
            conn, run_id, "user", "", "",
        )
        _insert_approved_deliverable(conn, run_id, "task_1_1")  # [BL-176] 離脱先の承認成立を用意
        state = _base_state(run_id, current_task_id="task_1_1")
        cela_main._resolve_task_transition(
            state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
        )
        assert state["current_task_id"] == "task_1_2"
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def test_resolve_task_transition_allows_when_deferred(db_conn):
    """明示的にDEFERされたissueは遷移をブロックしない（BL-082同様のスケジュール調整）。"""
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "bl125_deferred_b", "description": "懸念", "severity": "major"},
            conn, run_id, "detector", "phase_1", "task_1_1",
        )
        cela_main._write_issue_impl(
            {"action_type": "DEFER", "topic": "bl125_deferred_b",
             "defer_to_task_id": "task_1_2", "defer_reason": "task_1_2で対応予定"},
            conn, run_id, "user", "", "", state=_base_state(run_id),
        )
        _insert_approved_deliverable(conn, run_id, "task_1_1")  # [BL-176] 離脱先の承認成立を用意
        state = _base_state(run_id, current_task_id="task_1_1")
        cela_main._resolve_task_transition(
            state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
        )
        assert state["current_task_id"] == "task_1_2"
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def test_resolve_task_transition_allows_when_no_blocking_issue(db_conn):
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        _insert_approved_deliverable(conn, run_id, "task_1_1")  # [BL-176] 離脱先の承認成立を用意
        state = _base_state(run_id, current_task_id="task_1_1")
        cela_main._resolve_task_transition(
            state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
        )
        assert state["current_task_id"] == "task_1_2"
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def test_build_task_transition_blocked_notice_returns_empty_when_no_topics():
    state = {"task_transition_blocked_issue_topics": []}
    assert cela_main._build_task_transition_blocked_notice(state) == ""


def test_build_task_transition_blocked_notice_returns_text_and_clears():
    state = {
        "task_transition_blocked_issue_topics": ["bl134_repro"],
        "current_task_id": "task_1_1",
    }
    notice = cela_main._build_task_transition_blocked_notice(state)
    assert "BL-125" in notice
    assert "bl134_repro" in notice
    assert state["task_transition_blocked_issue_topics"] == []


def test_generate_user_utterance_injects_blocked_transition_notice():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_task_transition_blocked_notice" in src


def test_lineage_state_has_task_transition_blocked_field():
    annotations = cela_main.LineageState.__annotations__
    assert "task_transition_blocked_issue_topics" in annotations


def test_issue_log_has_defer_to_task_id_column(db_conn):
    conn, _run_id = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    assert "defer_to_task_id" in cols
