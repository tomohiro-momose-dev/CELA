"""
BL-154: decision_extractorが自動抽出するagreements Directive/Deferred（BL-023/082）を、
issue_log（BL-096/136）へも同時に橋渡しする。

コードベースには3つの並行した「先送り事項」追跡機構が存在していた：(1) issue_log
（write_issueツール、detector/detector_auto=CREATE、user=CREATE/RESOLVE/DEFER）、
(2) agreementsテーブルのentry_type="Directive", status="Deferred"（decision_extractor_node
が全Expert/Userターン後に自動抽出。Expert自身はwrite_issueツールを持たないため、これが
Expert発の先送り宣言を捕捉する唯一の経路だった）、(3) plan_draftsの「先送り事項」セクション
（(2)の抽出直後に自動追記）。しかしBL-125の遷移ゲート・BL-144の滞留検知・BL-145の
issue駆動タスク明示化はいずれもissue_logのみを参照しており、(2)/(3)には一切の可視性が
なかった。

対策として、decision_extractor_nodeがDirective/Deferredを検出した際、既存のplan_drafts
申し送りと同時に、issue_log側にもseverity='minor'/status='open'で起票し（defer_to_task_id
を初回作成時点から設定）、新規内部ロール`decision_extractor_auto`（detector_autoと同型、
CREATE専用・LLMツール呼び出し経路からは到達不能）を追加した。Expertへの新規ツール付与は
行わない。

参照: docs/design/back_log/issue_backlog.md BL-154。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl154.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


def _phases():
    return [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
        {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1"}, {"task_id": "task_2_2"}]},
    ]


def _base_state(run_id, phases, chat_content="task_1_1で述べた通り、この点はtask_2_1で扱う。"):
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": phases[0],
        "current_task_id": "task_1_1",
        "chat_history": [{"role": "assistant", "content": chat_content}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False,
        "user_wrote_agreement": False,
    }


def _deferred_extractor(topic="bl154_topic", defer_to_task_id="task_2_1", source_task_id="task_1_1"):
    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (
            [
                {
                    "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
                    "topic": topic, "content": "詳細はここに記載", "rationale": "後続タスクで扱う方が適切",
                    "proposed_by": "Agent", "phase_id": "phase_1", "task_id": source_task_id,
                    "defer_to_task_id": defer_to_task_id,
                },
            ],
            {"advances_to_phase_id": None, "advances_to_task_id": None},
        )
    return _fake


def _get_issue_row(conn, run_id, topic):
    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, topic)
    ).fetchone()
    return dict(row) if row else None


def test_directive_deferred_extraction_creates_issue_log_row(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor())

    cela_main.decision_extractor_node(state)

    row = _get_issue_row(conn, run_id, "bl154_topic")
    assert row is not None
    assert row["severity"] == "minor"
    assert row["status"] == "open"
    assert row["defer_to_task_id"] == "task_2_1"
    assert row["raised_by"] == "decision_extractor_auto"


def test_plan_drafts_annotation_still_happens_alongside_issue_log(db_conn, monkeypatch):
    """既存のplan_drafts申し送り（BL-082）が、issue_log追加後も引き続き併存すること（回帰確認）。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor())

    cela_main.decision_extractor_node(state)

    draft = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert draft is not None
    assert "詳細はここに記載" in draft["content"] or "後続タスクで扱う方が適切" in draft["content"]


def test_reoccurrence_same_target_escalates_via_existing_invariant(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()

    state1 = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor())
    cela_main.decision_extractor_node(state1)

    state2 = _base_state(run_id, phases)
    cela_main.decision_extractor_node(state2)  # 同じtopic・同じdefer_to_task_idで再度抽出

    row = _get_issue_row(conn, run_id, "bl154_topic")
    assert row["occurrence_count"] == 2
    assert row["severity"] == "major"
    assert row["status"] == "escalated"
    assert row["defer_to_task_id"] == "task_2_1"  # 変化しない


def test_reoccurrence_different_target_updates_defer_to_task_id(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()

    state1 = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor(defer_to_task_id="task_2_1"))
    cela_main.decision_extractor_node(state1)

    state2 = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor(defer_to_task_id="task_2_2"))
    cela_main.decision_extractor_node(state2)

    row = _get_issue_row(conn, run_id, "bl154_topic")
    assert row["defer_to_task_id"] == "task_2_2"  # 最新の宣言が勝つ


def test_decision_extractor_auto_permission_create_only(db_conn):
    assert cela_main._check_issue_permission({"action_type": "CREATE"}, "decision_extractor_auto") is None
    assert cela_main._check_issue_permission({"action_type": "RESOLVE"}, "decision_extractor_auto") is not None
    assert cela_main._check_issue_permission({"action_type": "DEFER"}, "decision_extractor_auto") is not None


def test_unresolvable_target_task_id_skips_issue_log_creation(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(
        cela_main, "call_decision_extractor",
        _deferred_extractor(topic="bl154_unresolvable", defer_to_task_id="task_nonexistent"),
    )

    cela_main.decision_extractor_node(state)

    assert _get_issue_row(conn, run_id, "bl154_unresolvable") is None


def test_bl125_transition_gate_never_blocks_on_self_deferred_issue(db_conn, monkeypatch):
    """BL-154経由のissueはdefer_to_task_idが誕生時から設定済みのため、escalated化した後でも
    _get_blocking_issues_for_transitionの対象には決してならないこと。"""
    conn, run_id = db_conn
    phases = _phases()

    state1 = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor())
    cela_main.decision_extractor_node(state1)
    state2 = _base_state(run_id, phases)
    cela_main.decision_extractor_node(state2)  # occurrence_count=2 -> escalated化

    row = _get_issue_row(conn, run_id, "bl154_topic")
    assert row["status"] == "escalated"  # 前提: escalated化していること

    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []  # defer_to_task_id設定済みのため対象外


def test_build_open_issue_pin_text_shows_defer_target_when_present(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _deferred_extractor(topic="bl154_pinned"))
    cela_main.decision_extractor_node(state)

    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl154_plain_open", "description": "対応先未定の軽微な懸念", "severity": "minor"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )

    text = cela_main._build_open_issue_pin_text(conn, run_id)
    assert "bl154_pinned" in text
    assert "対応予定task_id=task_2_1" in text
    assert "bl154_plain_open" in text
    plain_line = [ln for ln in text.split("\n") if "bl154_plain_open" in ln][0]
    assert "対応予定task_id" not in plain_line
