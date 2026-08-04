"""
BL-073: entry_type="Directive"のagreementは、対応するtask_idのDeliverableが承認されても
status="Proposed"のまま永久にDBへ残り続けていた（遷移させる経路が存在しなかった）。
これにより、reflection_nodeの「未解決」抽出（agreements.status=="Proposed"の全件、entry_type不問、
cela_main.py:3444）に、既に履行済みの指示がノイズとして出続け、実ドライランでReflectionが
毎ターン「なぜProposedのままか」の自問自答を強いられていた。

対策: Deliverableがstatus in {"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}へ
遷移した際、対応するtask_idのDirectiveを自動的にApprovedへ遷移させる
（_resolve_directive_for_task、cela_main.py）。

参照: docs/design/issue_backlog.md BL-073。
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
    db_path = str(tmp_path / "test_bl073.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _proposed_directive(task_id: str) -> dict:
    return {
        "id": f"AG-DIR-{task_id}", "timestamp": time.time(),
        "action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",
        "topic": f"{task_id} の指示", "decision_what": "タスク指示本文", "reason_why": "Userが指示",
        "proposed_by": "User", "phase_id": "phase_1", "task_id": task_id,
        "depends_on": [], "resource_claims": {},
    }


def test_bl073_resolve_directive_for_task_transitions_proposed_directive_to_approved(db_conn):
    """Proposedの指示が_resolve_directive_for_taskによりApprovedへ遷移し、
    未解決（status=="Proposed"）抽出から消えること。"""
    conn, run_id = db_conn
    cela_main.db_append_agreement(_proposed_directive("task_1_1"), conn, run_id)

    cela_main._resolve_directive_for_task(conn, run_id, "task_1_1", "phase_1", resolved_by="Agent")

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    directive_rows = [a for a in agreements if a["entry_type"] == "Directive" and a["task_id"] == "task_1_1"]
    # 旧レコードはSupersededへ、新レコードがApprovedとして追加される
    statuses = sorted(a["status"] for a in directive_rows)
    assert statuses == ["Approved", "Superseded"]

    unresolved = [a for a in agreements if a["status"] == "Proposed"]
    assert not any(a["task_id"] == "task_1_1" for a in unresolved)


def test_bl073_resolve_directive_for_task_noop_when_no_matching_directive(db_conn):
    """該当するDirectiveが無い場合は何も書き込まない（例外を出さない）。"""
    conn, run_id = db_conn
    cela_main._resolve_directive_for_task(conn, run_id, "task_nonexistent", "phase_1", resolved_by="Agent")
    assert cela_main.get_agreements_from_db(conn, run_id) == []


def test_bl073_commit_agreement_from_tool_resolves_directive_on_deliverable_approval(db_conn):
    """write_agreementツール経由（_commit_agreement_from_tool）でDeliverableがApprovedへ
    UPDATEされた際、対応するtask_idのDirectiveも自動的にApprovedへ解決されること。"""
    conn, run_id = db_conn
    cela_main.db_append_agreement(_proposed_directive("task_2_1"), conn, run_id)
    cela_main.db_append_agreement({
        "id": "AG-DELIV-1", "timestamp": time.time(),
        "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
        "topic": "task_2_1 成果物", "decision_what": "成果物本文", "reason_why": "Agentが提案",
        "proposed_by": "Agent", "phase_id": "phase_2", "task_id": "task_2_1",
        "depends_on": [], "resource_claims": {},
    }, conn, run_id)

    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved",
            "target_topic": "task_2_1 成果物", "topic": "task_2_1 成果物",
            "decision_what": "", "reason_why": "Userが承認",
        },
        conn, run_id, caller_role="user", task_id="task_2_1",
    )
    assert err is None

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    directive_rows = [a for a in agreements if a["entry_type"] == "Directive" and a["task_id"] == "task_2_1"]
    statuses = sorted(a["status"] for a in directive_rows)
    assert statuses == ["Approved", "Superseded"]


def test_bl073_decision_extractor_and_commit_tool_call_resolve_directive():
    """decision_extractor_node・_commit_agreement_from_toolの両経路のソースに、
    RESOLVING_DELIVERABLE_STATUSES判定と_resolve_directive_for_task呼び出しが
    含まれていること（配線漏れの再発防止確認）。"""
    import inspect
    extractor_src = inspect.getsource(cela_main.decision_extractor_node)
    commit_src = inspect.getsource(cela_main._commit_agreement_from_tool)
    assert "_resolve_directive_for_task" in extractor_src
    assert "_resolve_directive_for_task" in commit_src
    assert "RESOLVING_DELIVERABLE_STATUSES" in extractor_src
    assert "RESOLVING_DELIVERABLE_STATUSES" in commit_src
