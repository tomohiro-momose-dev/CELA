"""
BL-176: `_resolve_task_transition`が離脱先task_idの承認成立を検証しておらず、Userが1発言で
「現タスクの承認」と「次タスクへの指示」を同時に行うと状態が壊れうる問題への対応。

ユーザー報告: 「ユーザーが現タスクを承認することと次タスクの指示を明確に分けれないか？ユーザーが
2つを同時に行ってしまうので、detectorの監査をすり抜けると未承認のまま次タスクが進むことがある
（task_idが動かない）」。

コード調査の結果、(1) `write_agreement`は呼び出し時点でDBへ即コミットされ、Detectorの監査は
事後にターン全体へかかる仕組みで承認自体を差し戻す機構ではないこと、(2) `current_task_id`の
唯一の書き手`_resolve_task_transition`（BL-024）は遷移先の実在確認とBL-125の未解決issueブロック
は行うが、離脱するtask_idのDeliverableが実際にApproved相当（BL-167の`_is_task_completed`）かを
一切検証していないこと、(3) その入力`advances_to_task_id`は`write_agreement`とは独立した
`call_decision_extractor`（BL-139のフォールバック含む）がUser発言全文を自由文脈で読んで抽出した
もので、承認の成否とは無関係に遷移意図だけを検出する設計であることを確認した。

対応: `_resolve_task_transition`に、BL-125/BL-146と同型の機械的ゲートを追加した。
「departing_task_idが空でなく、かつ`_is_task_completed`でなければ、たとえadvances_to_task_idが
有効なtask_idを指していても遷移を拒否する」。ブロック時は一度きりの通知
（`task_transition_blocked_unapproved_task_id`、BL-125の`task_transition_blocked_issue_topics`と
同じone-shotパターン）を次のUser AIターンへ注入する。

参照: docs/design/back_log/issue_backlog.md BL-176、BL-125、BL-146、BL-167。
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
    db_path = str(tmp_path / "test_bl176.db")
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


_PHASE_1 = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}


def _base_state(run_id: str, current_task_id: str = "task_1_1") -> dict:
    return {
        "run_id": run_id,
        "phases": [_PHASE_1],
        "current_phase": _PHASE_1,
        "current_task_id": current_task_id,
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "",
    }


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


# --- _resolve_task_transitionのゲート本体 ---

def test_blocks_when_departing_task_has_no_deliverable_at_all(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_1"
    assert state["task_transition_blocked_unapproved_task_id"] == "task_1_1"


def test_blocks_when_departing_task_deliverable_is_only_proposed(db_conn):
    """成果物は提出済みだが未承認（Proposed）の場合はまだ遷移を許可しない。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_1", "Proposed")
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_1"
    assert state["task_transition_blocked_unapproved_task_id"] == "task_1_1"


def test_blocks_when_departing_task_deliverable_is_rejected(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_1", "Rejected")
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_1"


def test_allows_when_departing_task_deliverable_is_approved(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_2"
    assert state["task_transition_blocked_unapproved_task_id"] == ""


def test_allows_when_departing_task_deliverable_is_approved_with_conditions(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "task_1_1", "Approved_with_Conditions")
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_2"


def test_allows_first_transition_when_no_departing_task_yet(db_conn):
    """current_task_idが空（まだ一度もタスクに着手していない）場合、承認すべき前任taskが
    存在しないためBL-176のゲート対象外とする。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_1"}
    )
    assert state["current_task_id"] == "task_1_1"


def test_bl125_issue_gate_still_takes_precedence_and_fires_without_a_deliverable(db_conn):
    """[BL-125との共存] 未解決issueが残っている場合はBL-125のゲートが先に発火し、
    BL-176用の通知フィールドはセットされない（両者は排他）。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl176_coexist", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    state = _base_state(run_id, current_task_id="task_1_1")
    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_2"}
    )
    assert state["current_task_id"] == "task_1_1"
    assert "bl176_coexist" in state["task_transition_blocked_issue_topics"]
    assert state["task_transition_blocked_unapproved_task_id"] == ""


# --- _build_task_transition_blocked_notice のBL-176分岐 ---

def test_notice_returns_empty_when_neither_flag_set():
    state = {"task_transition_blocked_issue_topics": [], "task_transition_blocked_unapproved_task_id": ""}
    assert cela_main._build_task_transition_blocked_notice(state) == ""


def test_notice_returns_text_and_clears_for_unapproved_task():
    state = {
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "task_1_1",
    }
    notice = cela_main._build_task_transition_blocked_notice(state)
    assert "BL-176" in notice
    assert "task_1_1" in notice
    assert state["task_transition_blocked_unapproved_task_id"] == ""


def test_notice_prefers_bl125_topics_when_both_somehow_set():
    """両フラグが同時にセットされることは実運用では起きない（排他）が、通知関数自体は
    BL-125を優先し、BL-176側は消費せず温存する（フェイルセーフの確認）。"""
    state = {
        "task_transition_blocked_issue_topics": ["bl125_topic"],
        "task_transition_blocked_unapproved_task_id": "task_1_1",
    }
    notice = cela_main._build_task_transition_blocked_notice(state)
    assert "BL-125" in notice
    assert state["task_transition_blocked_unapproved_task_id"] == "task_1_1"


# --- 配線・型の確認 ---

def test_lineage_state_has_bl176_field():
    annotations = cela_main.LineageState.__annotations__
    assert "task_transition_blocked_unapproved_task_id" in annotations


def test_generate_user_utterance_injects_blocked_transition_notice():
    import inspect
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_task_transition_blocked_notice" in src
