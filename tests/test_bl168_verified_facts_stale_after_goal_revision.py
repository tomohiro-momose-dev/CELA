"""
BL-168: `verified_facts`テーブルにゴール改定を反映するsupersede機構が一切ない。

`upsert_verified_fact`は`(run_id, variable_name)`をユニークキーとしたUPSERT方式で、該当変数が
再度`upsert_verified_fact`されない限り、内容の新旧・前提の変化を問わず永久に「現在の確定値」
として`read_verified_fact`から返り続ける。実ログ（`log/2026-08-04/1435`）で、ゴール改定
（車両単価500〜1,000万円/台へ変更）より前にtask_1_1のExpertが確定した`max_vehicle_count='2'`
等が、改定後も無警告のまま後続ノード（Task Plan Reviewer等）へ供給され続け、再構築後の
task_1_1のプランがゴール改定前の車両単価のまま出力される実害につながった。

`_revise_goal_tool_impl`が既に計算しているBL-163の`_flagged`（ゴール改定によって影響を受ける
過去タスクの`(phase_id, task_id)`一覧）をそのまま再利用し、該当task_idを`source_task_id`に
持つ`verified_facts`行の`reason`列へ警告を付記する（`value`自体は過去の事実として正しいため
改変しない）。

参照: docs/design/back_log/issue_backlog.md BL-168、BL-163。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl168.db")
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


def _insert_agreement_row(conn, run_id, seq, phase_id, task_id, topic, status, entry_type="Deliverable"):
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

    # [BL-236] revise_goalは人間のHIL承認（--answer-human-input相当）を必須とするため、
    # このテストヘルパーでも承認済み状態を再現する。
    cela_main.upsert_verified_fact(
        cela_main.get_active_conn(), run_id,
        cela_main._goal_escalation_hil_variable(escalation_id),
        "approved", "", "", "", "human_operator", confidence="confirmed",
    )

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = old_goal
    return cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": new_text_pair[0], "new_text": new_text_pair[1]}],
        "reason_why": "構造的矛盾の解消のため",
    })


def _fact_reason(conn, run_id, variable_name):
    row = conn.execute(
        "SELECT reason FROM verified_facts WHERE run_id=? AND variable_name=?", (run_id, variable_name)
    ).fetchone()
    return row["reason"] if row else None


def test_revise_goal_marks_verified_facts_from_flagged_past_task_as_stale(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    cela_main.upsert_verified_fact(
        conn, run_id, "max_vehicle_count", "2", "台", "task_1_1", "phase_1", "expert",
        reason="全シナリオで最大車両台数は2台。",
    )

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    reason = _fact_reason(conn, run_id, "max_vehicle_count")
    assert reason.startswith("⚠️[BL-168: ゴール改定後未確認]")
    assert "task_1_1" in reason
    assert "全シナリオで最大車両台数は2台。" in reason  # 元のreasonは保持される


def test_revise_goal_does_not_touch_facts_from_unflagged_task(db_conn):
    """Rejectedのみのタスク（BL-163でも対象外）由来のverified_factsは触らないこと。"""
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Rejected")
    cela_main.upsert_verified_fact(
        conn, run_id, "max_vehicle_count", "2", "台", "task_1_1", "phase_1", "expert",
        reason="全シナリオで最大車両台数は2台。",
    )

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    reason = _fact_reason(conn, run_id, "max_vehicle_count")
    assert reason == "全シナリオで最大車両台数は2台。"


def test_revise_goal_with_no_verified_facts_does_not_crash(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True


def test_revise_goal_marking_is_idempotent_on_repeated_revision(db_conn):
    """同一factが既に警告付き（同一マーカー）の場合、二重にマーカーが積み重ならないこと。"""
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    cela_main.upsert_verified_fact(
        conn, run_id, "max_vehicle_count", "2", "台", "task_1_1", "phase_1", "expert",
        reason="全シナリオで最大車両台数は2台。",
    )

    _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    reason_after_first = _fact_reason(conn, run_id, "max_vehicle_count")

    # 2回目のゴール改定（別のエスカレーション）でも、マーカーが二重に積み重ならないこと。
    _revise_goal(run_id, "フェーズ分割方式とする。", ("フェーズ分割方式とする。", "外部財源活用方式とする。"))
    reason_after_second = _fact_reason(conn, run_id, "max_vehicle_count")

    assert reason_after_first == reason_after_second
    assert reason_after_second.count("⚠️[BL-168: ゴール改定後未確認]") == 1


def test_revise_goal_only_marks_facts_from_flagged_task_ids_not_others(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 2, "phase_1", "task_1_2", "task_1_2の成果物", "Proposed")  # 未完了、_flagged対象外
    cela_main.upsert_verified_fact(
        conn, run_id, "max_vehicle_count", "2", "台", "task_1_1", "phase_1", "expert", reason="task_1_1由来"
    )
    cela_main.upsert_verified_fact(
        conn, run_id, "peak_transport_capacity", "84", "人", "task_1_2", "phase_1", "expert", reason="task_1_2由来"
    )

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    assert _fact_reason(conn, run_id, "max_vehicle_count").startswith("⚠️[BL-168: ゴール改定後未確認]")
    assert _fact_reason(conn, run_id, "peak_transport_capacity") == "task_1_2由来"
