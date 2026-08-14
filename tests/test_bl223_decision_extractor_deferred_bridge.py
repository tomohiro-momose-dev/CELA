"""
BL-223: decision_extractorのDirective/Deferred橋渡し（BL-082/BL-154）が、2つの独立した理由で
機能していなかった問題を修正する。

実ログ（log/2026-08-13/1411, run_id=1786597142-55baeabc）で、Expertが成果物内で明示的に
先送りを宣言したにもかかわらず、その申し送りがagreements/plan_drafts/issue_logのいずれにも
残らないことが判明した。原因は2つ：

(A) `wrote_agreement_this_turn`はターン単位の粗いブール値で、Expertが同ターンで別件の
    write_agreement（成果物の登録等）を1回でも呼ぶと、decision_extractorが抽出した
    **全ての**項目（無関係なDirective/Deferredを含む）が一括でスキップされていた。
    項目単位の(entry_type, task_id)一致判定へ置き換えた。

(B) `defer_to_task_id`が空文字（申し送り先task_idが特定できない）の場合、plan_drafts追記だけ
    でなくissue_log起票（BL-154）まで丸ごとスキップされていた。issue_log起票は
    `_write_issue_impl`のCREATE分岐がdefer_to_task_idをオプション扱いしており本来空文字でも
    成立し、かつ空文字は`_get_blocking_issues_for_transition`のSQL
    （defer_to_task_id IS NULL OR ''）を免除しないため、issue_logへ起票しても抜け穴にならない。
    一方、defer_to_task_idが非空だが解決不能（LLMが実在しないtask_idを出力）な場合に
    issue_log起票をスキップするのは意図的なfail-closed設計（BL-154のテストで保証済み）であり、
    この挙動は変更しない。

参照: docs/design/back_log/issue_backlog.md BL-223。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl223.db")
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


def _base_state(run_id, phases, expert_wrote_agreement_items=None, chat_content="成果物を提示します。"):
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": phases[0],
        "current_task_id": "task_1_1",
        "chat_history": [{"role": "assistant", "content": chat_content}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": bool(expert_wrote_agreement_items),
        "expert_wrote_agreement_items": expert_wrote_agreement_items or [],
        "user_wrote_agreement": False,
        "user_wrote_agreement_items": [],
    }


def _extractor(items):
    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return (list(items), {"advances_to_phase_id": None, "advances_to_task_id": None})
    return _fake


def _get_issue_row(conn, run_id, topic):
    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, topic)
    ).fetchone()
    return dict(row) if row else None


def _get_agreement_rows(conn, run_id, topic):
    return [a for a in cela_main.get_agreements_from_db(conn, run_id) if a["topic"] == topic]


# ---------------------------------------------------------------------------
# A: 項目単位の重複判定
# ---------------------------------------------------------------------------

def test_unrelated_extracted_item_not_skipped_when_other_topic_directly_written(db_conn, monkeypatch):
    """今回のバグの直接再現: Expertが同ターンでDeliverableをwrite_agreement直接呼び出しした
    (entry_type=Deliverable, task_id=task_1_1)場合でも、無関係なDirective/Deferred抽出項目
    （別entry_type）はスキップされず正しく書き込まれること。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(
        run_id, phases,
        expert_wrote_agreement_items=[{"entry_type": "Deliverable", "task_id": "task_1_1"}],
    )
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
            "topic": "bl223_sla_defer", "content": "SLA待ち時間の解釈は本タスクのスコープ外",
            "rationale": "後続タスクで確定する", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1", "defer_to_task_id": "task_2_1",
        },
    ]))

    cela_main.decision_extractor_node(state)

    rows = _get_agreement_rows(conn, run_id, "bl223_sla_defer")
    assert len(rows) == 1
    assert rows[0]["entry_type"] == "Directive"
    assert rows[0]["status"] == "Deferred"
    assert _get_issue_row(conn, run_id, "bl223_sla_defer") is not None


def test_same_entry_type_and_task_id_still_skipped_as_duplicate(db_conn, monkeypatch):
    """既存の防止機能の非退行: 直接書き込みと同じ(entry_type, task_id)の抽出項目は、
    従来通りスキップされること。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(
        run_id, phases,
        expert_wrote_agreement_items=[{"entry_type": "Decision", "task_id": "task_1_1"}],
    )
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Decision", "status": "Proposed",
            "topic": "bl223_duplicate_decision", "content": "重複するはずの内容",
            "rationale": "dummy", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
    ]))

    cela_main.decision_extractor_node(state)

    assert _get_agreement_rows(conn, run_id, "bl223_duplicate_decision") == []


def test_same_entry_type_different_task_id_not_treated_as_duplicate(db_conn, monkeypatch):
    """(entry_type, task_id)の組で判定するため、entry_typeが同じでもtask_idが異なれば
    重複とみなさないこと。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(
        run_id, phases,
        expert_wrote_agreement_items=[{"entry_type": "Decision", "task_id": "task_1_2"}],
    )
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Decision", "status": "Proposed",
            "topic": "bl223_different_task", "content": "別タスクの内容",
            "rationale": "dummy", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
    ]))

    cela_main.decision_extractor_node(state)

    assert len(_get_agreement_rows(conn, run_id, "bl223_different_task")) == 1


# ---------------------------------------------------------------------------
# B: defer_to_task_idの3状態
# ---------------------------------------------------------------------------

def test_empty_defer_to_task_id_still_creates_issue_log_row(db_conn, monkeypatch):
    """B-1: 申し送り先task_idが特定できない（空文字）場合でも、issue_logへは起票されること。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
            "topic": "bl223_no_target", "content": "後続タスクで確定する",
            "rationale": "スコープ外", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1", "defer_to_task_id": "",
        },
    ]))

    cela_main.decision_extractor_node(state)

    row = _get_issue_row(conn, run_id, "bl223_no_target")
    assert row is not None
    assert row["severity"] == "minor"
    assert row["status"] == "open"
    assert not row["defer_to_task_id"]
    assert row["raised_by"] == "decision_extractor_auto"


def test_empty_defer_to_task_id_skips_plan_drafts_append(db_conn, monkeypatch):
    """B-2: 空文字の場合、対象タスクが不明なためplan_drafts追記は行われないこと（非退行）。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
            "topic": "bl223_no_target_plan", "content": "後続タスクで確定する",
            "rationale": "スコープ外", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1", "defer_to_task_id": "",
        },
    ]))

    cela_main.decision_extractor_node(state)

    for phase in phases:
        for task in phase["tasks"]:
            draft = cela_main.get_latest_plan_draft(conn, run_id, phase["phase_id"], task["task_id"])
            if draft is not None:
                assert "後続タスクで確定する" not in draft["content"]
                assert "スコープ外" not in draft["content"]


def test_resolvable_defer_to_task_id_creates_both_plan_drafts_and_issue_log(db_conn, monkeypatch):
    """B-3: 従来通り、解決可能なdefer_to_task_idはplan_drafts追記・issue_log起票の両方が
    行われること（非退行）。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
            "topic": "bl223_resolvable", "content": "詳細はここに記載",
            "rationale": "後続タスクで扱う方が適切", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1", "defer_to_task_id": "task_2_1",
        },
    ]))

    cela_main.decision_extractor_node(state)

    row = _get_issue_row(conn, run_id, "bl223_resolvable")
    assert row is not None
    assert row["defer_to_task_id"] == "task_2_1"
    draft = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert draft is not None
    assert "詳細はここに記載" in draft["content"] or "後続タスクで扱う方が適切" in draft["content"]


def test_unresolvable_defer_to_task_id_skips_both_issue_log_and_plan_drafts(db_conn, monkeypatch):
    """B-4: 非空だが解決不能（実在しないtask_id）な場合は、issue_log・plan_draftsともに
    作成されないこと（BL-154の既存fail-closed設計と同じ前提を本ファイルでも保証する。
    独立レビューで指摘され、修正Bの分岐設計時に明示的に区別した）。"""
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases)
    monkeypatch.setattr(cela_main, "call_decision_extractor", _extractor([
        {
            "action_type": "CREATE", "entry_type": "Directive", "status": "Deferred",
            "topic": "bl223_unresolvable", "content": "存在しないタスクへの先送り",
            "rationale": "dummy", "proposed_by": "Agent",
            "phase_id": "phase_1", "task_id": "task_1_1", "defer_to_task_id": "task_nonexistent",
        },
    ]))

    cela_main.decision_extractor_node(state)

    assert _get_issue_row(conn, run_id, "bl223_unresolvable") is None
