"""
BL-290: goal_escalationsを読む専用ツール（read_escalation）の新設。

BL-289の監査過程で、goal_escalationsテーブル（concern_summary/implicated_constraint/
why_conflicts/suggested_reframe/status/resolution_reason等）を読む専用ツールがそもそも
存在しないことが判明した。唯一露出しているのは_get_escalation_status_text_for_expertに
よる常時注入（concern_summaryのみを短く表示）であり、implicated_constraint/why_conflicts/
suggested_reframe/却下時のresolution_reasonは、提起時のツール呼び出し引数としてDBに
保存された後、二度と誰にも読み返されなかった。

read_agreement（BL-279）と同型の設計として、escalation_idまたはtask_idで検索できる
read_escalationツールを新設した。goal_escalationsは1行=1件のためentry_typeフィルタ等は
不要な単純な設計。既存のget_goal_escalation（SELECT *で全カラム、BL-086既存）をそのまま
再利用し、新規get_goal_escalations_by_task_idをtask_id検索用に追加した。

配線は、read_agreement等の既存読み取りツールが全ノード共通で配線されている前例に倣い、
READ_AGREEMENT_TOOLが配線されている全12箇所へ同じ並びで追加した。

参照: docs/design/back_log/issue_backlog.md BL-290。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl290.db")
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


def _seed_escalation(conn, run_id, task_id="task_1_1", phase_id="phase_1"):
    return cela_main.db_create_goal_escalation(
        conn, run_id, phase_id, task_id, "expert",
        concern_summary="車両台数の下限が輸送能力要件と矛盾する",
        implicated_constraint="OpEx上限4000万円/年",
        why_conflicts="OpEx上限を満たす車両台数では、ピーク帯の輸送能力要件を満たせない",
        suggested_reframe="OpEx上限を維持しつつ、運行頻度ではなく車両定員の見直しで能力を確保する",
    )


# ---------------------------------------------------------------------------
# 1. escalation_idによる検索
# ---------------------------------------------------------------------------

def test_read_escalation_by_id_returns_full_detail(db_conn):
    conn, run_id = db_conn
    esc_id = _seed_escalation(conn, run_id)
    result = cela_main.TOOL_DISPATCH["read_escalation"]({"escalation_id": esc_id})
    assert result["status"] == "ok"
    assert result["count"] == 1
    escalation = result["escalations"][0]
    assert escalation["escalation_id"] == esc_id
    assert escalation["implicated_constraint"] == "OpEx上限4000万円/年"
    assert escalation["why_conflicts"] == "OpEx上限を満たす車両台数では、ピーク帯の輸送能力要件を満たせない"
    assert escalation["suggested_reframe"] == "OpEx上限を維持しつつ、運行頻度ではなく車両定員の見直しで能力を確保する"
    assert escalation["status"] == "Open"


def test_read_escalation_by_id_not_found(db_conn):
    result = cela_main.TOOL_DISPATCH["read_escalation"]({"escalation_id": "ESC-nonexistent"})
    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# 2. task_idによる検索（複数件）
# ---------------------------------------------------------------------------

def test_read_escalation_by_task_id_returns_all_matching(db_conn):
    conn, run_id = db_conn
    esc1 = _seed_escalation(conn, run_id, task_id="task_2_2")
    esc2 = cela_main.db_create_goal_escalation(
        conn, run_id, "phase_1", "task_2_2", "user",
        concern_summary="別の懸念", implicated_constraint="制約B",
        why_conflicts="矛盾B", suggested_reframe="再構成案B",
    )
    _seed_escalation(conn, run_id, task_id="task_9_9")  # 無関係タスク
    result = cela_main.TOOL_DISPATCH["read_escalation"]({"task_id": "task_2_2"})
    assert result["status"] == "ok"
    assert result["count"] == 2
    assert {e["escalation_id"] for e in result["escalations"]} == {esc1, esc2}


def test_read_escalation_by_task_id_not_found(db_conn):
    result = cela_main.TOOL_DISPATCH["read_escalation"]({"task_id": "task_9_9"})
    assert result["status"] == "not_found"


def test_read_escalation_includes_resolution_reason_for_rejected(db_conn):
    """[BL-290] 却下時のresolution_reasonも読み返せることを確認する
    （ambient pinの表示より詳細な情報が必要になり得る場面）。"""
    conn, run_id = db_conn
    esc_id = _seed_escalation(conn, run_id)
    conn.execute(
        "UPDATE goal_escalations SET status='Rejected', resolution_reason=? WHERE escalation_id=?",
        ("真の制約ではなく見直し可能な前提と判断したため却下", esc_id),
    )
    result = cela_main.TOOL_DISPATCH["read_escalation"]({"escalation_id": esc_id})
    assert result["escalations"][0]["resolution_reason"] == "真の制約ではなく見直し可能な前提と判断したため却下"


# ---------------------------------------------------------------------------
# 3. エラーケース
# ---------------------------------------------------------------------------

def test_read_escalation_requires_at_least_one_param(db_conn):
    result = cela_main.TOOL_DISPATCH["read_escalation"]({})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 4. 配線確認（read_agreementが配線されている全ノードと同じ並びで配線されていること）
# ---------------------------------------------------------------------------

_WIRED_NODE_FUNCS = [
    "call_task_planner", "call_orchestrator", "call_expert", "call_detector",
    "call_resource_arbiter", "call_integrator", "call_reviewer",
    "generate_user_utterance", "call_goal_essence_analyst", "call_task_plan_reviewer",
]


@pytest.mark.parametrize("func_name", _WIRED_NODE_FUNCS)
def test_node_wires_read_escalation_tool(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "READ_ESCALATION_TOOL" in src, f"{func_name}にREAD_ESCALATION_TOOLが配線されていません"


def test_tool_dispatch_registers_read_escalation():
    assert "read_escalation" in cela_main.TOOL_DISPATCH


# ---------------------------------------------------------------------------
# 5. §17.1後段: ソース存在証明
# ---------------------------------------------------------------------------

def test_read_escalation_handler_source_present():
    src = inspect.getsource(cela_main._read_escalation_handler)
    assert "get_goal_escalation" in src
    assert "get_goal_escalations_by_task_id" in src
