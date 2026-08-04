"""
BL-139: call_decision_extractorが返すtransition["advances_to_task_id"]は、単一の大きなJSON
出力の一項目に過ぎず、実ドライラン（log/2026-07-31/0908）でUserが「task_2_1への着手指示」を
明示していても、抽出されたextracted_events自体にはtask_2_1向けのDirective（CREATE）が
正しく含まれているのに、トップレベルのadvances_to_task_idだけがnullで返るケースが発生した。
これによりcurrent_task_idが数百ターンにわたりtask_1_2のまま更新されず、BL-023の
acceptance_criteriaチェック等、current_task_id依存の全機構が誤ったタスクを参照し続けた。

対策: decision_extractor_node内で、抽出済みextracted_eventsの中に現在タスクと異なる
有効なtask_idを持つDirective（status="Deferred"を除く）があれば、transitionの代替シグナルとして
採用し、_resolve_task_transitionへ渡す（BL-096の自動起票と同型の安全網）。

参照: docs/design/back_log/issue_backlog.md BL-139。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl139.db")
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


def _base_state(run_id, phases):
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": phases[0],
        "current_task_id": "task_1_2",
        "chat_history": [{"role": "user", "content": "task_1_2を承認し、task_2_1に着手してください。"}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False,
        "user_wrote_agreement": False,
    }


def test_decision_extractor_falls_back_to_directive_task_id_when_transition_missing(db_conn, monkeypatch):
    """extracted_eventsにtask_2_1向けのDirective(CREATE)があり、transitionが空({})で
    返ってきても、current_task_idがtask_2_1へ更新されること（実インシデントの再現）。"""
    _conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)

    def _fake_call_decision_extractor(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (
            [
                {
                    "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved",
                    "target_topic": "task_1_2 成果物", "topic": "task_1_2 成果物", "content": "",
                    "rationale": "承認", "proposed_by": "User", "phase_id": "phase_1", "task_id": "task_1_2",
                },
                {
                    "action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",
                    "topic": "task_2_1 着手指示", "content": "task_2_1に着手してください。",
                    "rationale": "Userがtask_1_2完了を受け次タスクを指示", "proposed_by": "User",
                    "phase_id": "phase_2", "task_id": "task_2_1",
                },
            ],
            {"advances_to_phase_id": None, "advances_to_task_id": None},
        )

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_call_decision_extractor)

    cela_main.decision_extractor_node(state)

    assert state["current_task_id"] == "task_2_1", (
        "抽出されたDirectiveのtask_idからのフォールバックが機能せず、current_task_idが更新されなかった"
    )
    assert state["current_phase"]["phase_id"] == "phase_2"


def test_decision_extractor_fallback_ignores_deferred_directive(db_conn, monkeypatch):
    """BL-082の明示的先送り（status="Deferred"）は「今は移行しない」という意思表示のため、
    フォールバックの対象から除外されること。"""
    _conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)

    def _fake_call_decision_extractor(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (
            [
                {
                    "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
                    "topic": "細部の検討", "content": "この点はtask_2_1で扱う。",
                    "rationale": "先送り", "proposed_by": "User", "phase_id": "phase_2", "task_id": "task_2_1",
                    "defer_to_task_id": "task_2_1",
                },
            ],
            {"advances_to_phase_id": None, "advances_to_task_id": None},
        )

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_call_decision_extractor)

    cela_main.decision_extractor_node(state)

    assert state["current_task_id"] == "task_1_2", (
        "Deferredな先送り指示が誤って遷移トリガーとして扱われてしまった"
    )


def test_decision_extractor_does_not_override_explicit_transition(db_conn, monkeypatch):
    """call_decision_extractorが正しくadvances_to_task_idを返した場合は、
    フォールバックが介入せずそのまま使われること。"""
    _conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)

    def _fake_call_decision_extractor(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (
            [],
            {"advances_to_phase_id": "phase_2", "advances_to_task_id": "task_2_1"},
        )

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_call_decision_extractor)

    cela_main.decision_extractor_node(state)

    assert state["current_task_id"] == "task_2_1"


def test_decision_extractor_fallback_only_applies_to_user_role(db_conn, monkeypatch):
    """target_role="expert"（Expertの発言直後の抽出）では、Expert自身がタスク遷移を
    決定する権限を持たないため、フォールバックを適用しないこと。"""
    _conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    # 直前の発言者をExpert(assistant)に変更 -> target_role="expert"
    state["chat_history"] = [{"role": "assistant", "content": "task_2_1の成果物を提出します。"}]

    def _fake_call_decision_extractor(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (
            [
                {
                    "action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",
                    "topic": "task_2_1 成果物提出", "content": "...", "rationale": "Expertが提出",
                    "proposed_by": "Agent", "phase_id": "phase_2", "task_id": "task_2_1",
                },
            ],
            {"advances_to_phase_id": None, "advances_to_task_id": None},
        )

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_call_decision_extractor)

    cela_main.decision_extractor_node(state)

    assert state["current_task_id"] == "task_1_2"
