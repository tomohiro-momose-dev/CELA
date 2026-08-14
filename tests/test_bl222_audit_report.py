"""
BL-222: 人間が成果物の数値・内容を「5W1H」で監査できる読み取り専用CLIレポート
（`--audit-report RUN_ID [--task-id TASK_ID] [--phase-id PHASE_ID]`）。

きっかけ: ユーザーが「成果物を見た時に、この数字や内容が5W1Hに基づいて検査できない。
現状はログから解析してもらう形」と課題を提起。当初案（本文への隠し文字での経緯注釈）は
BL-074/076/202で既知の「文字列一致ベースの注釈は本文編集で追従できず腐る」という脆さと
同じ土台に乗るため見送り、代わりに既にDBへ構造化保存済みの根拠（verified_factsの
reason/citations/confidence、agreementsのreason_why/citations）を、本文を一切変更せず
別ビューとして機械的に取り出すレポートを新設した。LLM呼び出しは行わないため、本文の
編集有無に関わらず常に正確。

「リアルタイム監視」は、cela.dbがWALモード（`get_db_connection`）で動作しているため、
run実行中でも別プロセスから読み取り専用で安全にアクセスできることを利用し、本コマンドを
シェル側の`watch`等で定期実行することで実現する（CELA側に常駐プロセスは持たせない）。
BL-217の`--pending-human-input`（同じくWALモードを利用した実行中run向け読み取り専用CLI）
と同型のパターン。

参照: docs/design/issue_backlog.md BL-222、BL-217（同型のCLI設計）。
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
    db_path = str(tmp_path / "test_bl222.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_audit_report_empty_run_shows_zero_counts(db_conn):
    conn, run_id = db_conn
    report = cela_main._audit_report(conn, run_id)
    assert "run全体" in report
    assert "verified_facts） 0件" in report
    assert "agreements） 0件" in report


def test_audit_report_includes_verified_fact_5w1h(db_conn):
    """変数名・値・理由・出典・確定者・確定タスクの5W1Hが全て含まれること。"""
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "vehicle_count", "4", unit="台",
        source_task_id="task_2_1", source_phase_id="phase_2",
        confirmed_by="expert", reason="予算上限1億円÷単価2500万円から算出",
        citations=[{"type": "expert_calculation", "detail": "100000000/25000000=4"}],
        confidence="confirmed",
    )
    report = cela_main._audit_report(conn, run_id)
    assert "vehicle_count" in report
    assert "4台" in report
    assert "予算上限1億円÷単価2500万円から算出" in report
    assert "expert" in report
    assert "task_2_1" in report
    assert "expert_calculation" in report
    assert "confirmed" in report


def test_audit_report_includes_agreement_5w1h(db_conn):
    conn, run_id = db_conn
    cela_main.db_append_agreement(
        {
            "id": "AG-test-1", "action_type": "CREATE", "status": "Approved",
            "topic": "vehicle_count_decision", "decision_what": "車両台数を4台とする",
            "reason_why": "予算制約から算出した上限に一致するため",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_2",
            "task_id": "task_2_1", "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "citations": "[]",
        },
        conn, run_id,
    )
    report = cela_main._audit_report(conn, run_id)
    assert "vehicle_count_decision" in report
    assert "車両台数を4台とする" in report
    assert "予算制約から算出した上限に一致するため" in report
    assert "expert" in report
    assert "task_2_1" in report


def test_audit_report_filters_verified_facts_by_task_id(db_conn):
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "in_scope_var", "1", unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    cela_main.upsert_verified_fact(
        conn, run_id, "out_of_scope_var", "2", unit="", source_task_id="task_9_9",
        source_phase_id="phase_9", confirmed_by="expert", confidence="confirmed",
    )
    report = cela_main._audit_report(conn, run_id, task_id="task_1_1")
    assert "in_scope_var" in report
    assert "out_of_scope_var" not in report
    assert "task_id=task_1_1" in report


def test_audit_report_filters_by_phase_id_when_no_task_id(db_conn):
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "phase1_var", "1", unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    cela_main.upsert_verified_fact(
        conn, run_id, "phase2_var", "2", unit="", source_task_id="task_2_1",
        source_phase_id="phase_2", confirmed_by="expert", confidence="confirmed",
    )
    report = cela_main._audit_report(conn, run_id, phase_id="phase_1")
    assert "phase1_var" in report
    assert "phase2_var" not in report


def test_audit_report_task_id_takes_precedence_over_phase_id(db_conn):
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "target_var", "1", unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    cela_main.upsert_verified_fact(
        conn, run_id, "same_phase_other_task_var", "2", unit="", source_task_id="task_1_9",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    report = cela_main._audit_report(conn, run_id, task_id="task_1_1", phase_id="phase_1")
    assert "target_var" in report
    assert "same_phase_other_task_var" not in report


def test_audit_report_filters_agreements_by_task_id(db_conn):
    conn, run_id = db_conn
    cela_main.db_append_agreement(
        {
            "id": "AG-in-scope", "action_type": "CREATE", "status": "Approved",
            "topic": "in_scope_topic", "decision_what": "in-scope", "reason_why": "x",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_1",
            "task_id": "task_1_1", "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "citations": "[]",
        },
        conn, run_id,
    )
    cela_main.db_append_agreement(
        {
            "id": "AG-out-of-scope", "action_type": "CREATE", "status": "Approved",
            "topic": "out_of_scope_topic", "decision_what": "out-of-scope", "reason_why": "y",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_9",
            "task_id": "task_9_9", "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "citations": "[]",
        },
        conn, run_id,
    )
    report = cela_main._audit_report(conn, run_id, task_id="task_1_1")
    assert "in_scope_topic" in report
    assert "out_of_scope_topic" not in report


def test_audit_report_does_not_call_any_ai(db_conn):
    """[設計判断の回帰防止] LLM呼び出しを一切行わないこと（本文編集で腐らない、常に正確、
    という設計の核心）。query_AI/_query_and_parse_with_retryへの参照が無いことを確認する。"""
    import inspect
    src = inspect.getsource(cela_main._audit_report)
    assert "query_AI" not in src
    assert "_query_and_parse_with_retry" not in src


def test_cli_wiring_audit_report_flag_registered():
    """argparseに--audit-report/--task-id/--phase-idが登録されていること
    （実際のCLI起動テストはprocess起動コストが高いため、ソース確認に留める）。"""
    import inspect
    src = inspect.getsource(cela_main)
    assert '"--audit-report"' in src
    assert '"--task-id"' in src
    assert '"--phase-id"' in src
