"""
R5: F-2.1拡張（思考プロセス監査）/ F-3.7（思考ログの強制記録）/ F-8.3（Freeze）/
GoalShiftEvent の、実LLM API呼び出しを伴わないオフライン検証項目。

参照: docs/design/r5/cela_r5_design_v2.md、docs/design/r5/cela_r5_impl_Plan.md。
"""

import json
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_r5.db")
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


# ===========================================================================
# F-2.1 / F-3.7: 思考ログの捕捉・記録
# ===========================================================================

def test_r5_get_last_reasoning_text_reflects_module_global(monkeypatch):
    """get_last_reasoning_textが_LAST_REASONING_TEXTの現在値を返すこと。"""
    monkeypatch.setattr(cela_main, "_LAST_REASONING_TEXT", "テスト思考ログ")
    assert cela_main.get_last_reasoning_text() == "テスト思考ログ"


def test_r5_make_decision_stores_internal_thought_process():
    """make_decisionにinternal_thought_processを渡すとDecisionに反映され、
    省略時は"(記録なし)"がデフォルトになること。"""
    d = cela_main.make_decision(who="detector", what="w", why="y", internal_thought_process="思考の中身")
    assert d["internal_thought_process"] == "思考の中身"

    d2 = cela_main.make_decision(who="detector", what="w", why="y")
    assert d2["internal_thought_process"] == "(記録なし)"


def test_r5_db_append_decision_persists_internal_thought_process(db_conn):
    """db_append_decisionがinternal_thought_processをdecisionsテーブルへ保存すること
    （BL-061調査時点で列自体は既に読み込み済みだったことを確認済み、回帰確認）。"""
    conn, run_id = db_conn
    d = cela_main.make_decision(who="reflection", what="w", why="y", internal_thought_process="停滞の根拠")
    cela_main.db_append_decision(d, conn, run_id)
    rows = cela_main.get_decisions_from_db(conn, run_id)
    assert rows[-1]["internal_thought_process"] == "停滞の根拠"


def test_r5_agreement_records_thought_process_only_when_rejected(db_conn, monkeypatch):
    """_commit_agreement_from_tool経由のagreementsは、status='Rejected'の場合のみ
    reasoningをスナップショット保存し、それ以外（Approved等）は保存しないこと
    （トークンコスト抑制のための限定運用、v2設計書§2）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "捕捉されたreasoning")
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = ""

    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "承認事項",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Rejected", "topic": "却下事項",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    approved = next(a for a in agreements if a["topic"] == "承認事項")
    rejected = next(a for a in agreements if a["topic"] == "却下事項")
    assert approved["internal_thought_process"] is None
    assert rejected["internal_thought_process"] == "捕捉されたreasoning"


def test_r5_call_detector_thought_process_audit_uses_correct_role_field():
    """call_detectorのソース内で、target_role=='expert'ならexpert_last_reasoning、
    それ以外はuser_last_reasoningを参照する分岐が存在すること（配線の存在確認）。"""
    import inspect
    src = inspect.getsource(cela_main.call_detector)
    assert "expert_last_reasoning" in src
    assert "user_last_reasoning" in src
    assert "思考プロセス監査" in src


# ===========================================================================
# F-8.3: Freeze機能
# ===========================================================================

def test_r5_freeze_agreement_sets_is_frozen_and_logs_decision(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "予算上限",
        "decision_what": "上限1億円", "reason_why": "確定", "entry_type": "Decision",
    })
    assert result["success"] is True
    agreements = cela_main.get_agreements_from_db(conn, run_id)
    agreement_id = agreements[0]["id"]

    freeze_result = cela_main.freeze_agreement(conn, run_id, agreement_id, "絶対に覆せない予算上限のため")
    assert freeze_result["success"] is True

    refreshed = cela_main.get_agreements_from_db(conn, run_id)
    assert refreshed[0]["is_frozen"] == 1

    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert any(d["who"] == "system_freeze" for d in decisions)


def test_r5_freeze_agreement_tool_rejects_non_user_role(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["freeze_agreement"]({"agreement_id": "AG-nonexistent", "reason": "r"})
    assert result["success"] is False
    assert "user" in result["error"]


def test_r5_freeze_agreement_tool_allows_user_role(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "凍結対象",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    agreement_id = cela_main.get_agreements_from_db(conn, run_id)[0]["id"]
    result = cela_main.TOOL_DISPATCH["freeze_agreement"]({"agreement_id": agreement_id, "reason": "r"})
    assert result["success"] is True


def test_r5_frozen_agreement_rejects_supersede_and_update(db_conn):
    """Freeze済みのagreementに対するSUPERSEDE/UPDATEが拒否されること（unfreeze機構は無い設計）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "凍結トピック",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    agreement_id = cela_main.get_agreements_from_db(conn, run_id)[0]["id"]
    cela_main.freeze_agreement(conn, run_id, agreement_id, "恒久確定")

    update_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Approved", "topic": "凍結トピック",
        "target_topic": "凍結トピック", "decision_what": "変更後", "reason_why": "r", "entry_type": "Decision",
    })
    assert update_result["success"] is False
    assert "Freeze" in update_result["error"]

    supersede_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "SUPERSEDE", "status": "Approved", "topic": "凍結トピック",
        "target_topic": "凍結トピック", "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert supersede_result["success"] is False
    assert "Freeze" in supersede_result["error"]

    # 元の内容が変更されずに残っていること
    remaining = cela_main.get_agreements_from_db(conn, run_id)
    assert len(remaining) == 1
    assert remaining[0]["decision_what"] == "d"
    assert remaining[0]["status"] != "Superseded"


def test_r5_build_agreements_context_sorts_frozen_first_with_lock_icon():
    agreements = [
        {"id": "AG-1", "status": "Approved", "entry_type": "Decision", "topic": "通常項目",
         "decision_what": "d1", "reason_why": "r1", "timestamp": 200, "is_frozen": 0},
        {"id": "AG-2", "status": "Approved", "entry_type": "Decision", "topic": "凍結項目",
         "decision_what": "d2", "reason_why": "r2", "timestamp": 100, "is_frozen": 1},
    ]
    ctx = cela_main._build_agreements_context(agreements)
    lines = ctx.split("\n")
    frozen_idx = next(i for i, l in enumerate(lines) if "凍結項目" in l)
    normal_idx = next(i for i, l in enumerate(lines) if "通常項目" in l)
    assert frozen_idx < normal_idx, "Freeze済み項目がtimestampより古くても先頭に来ていない"
    assert "🔒" in lines[frozen_idx]


# ===========================================================================
# GoalShiftEvent
# ===========================================================================

def test_r5_detect_goal_shift_returns_none_when_not_required():
    state = {"global_constraints": []}
    assert cela_main.detect_goal_shift(state, {"requires_goal_constraint_change": False}) is None
    assert cela_main.detect_goal_shift(state, {}) is None


def test_r5_detect_goal_shift_returns_event_when_required():
    state = {"global_constraints": [{"name": "予算", "total_cap": 100}]}
    arbiter_result = {
        "requires_goal_constraint_change": True,
        "new_allocation": {"task_1_1": 60},
        "rationale": "予算上限自体の見直しが必要",
    }
    shift = cela_main.detect_goal_shift(state, arbiter_result)
    assert shift is not None
    assert shift["shift_kind"] == "constraint_hit"
    assert shift["triggered_by"] == "Arbiter_Resource_Overrun"
    assert json.loads(shift["from_goal_state"]) == state["global_constraints"]
    assert json.loads(shift["to_goal_state"]) == arbiter_result["new_allocation"]


def test_r5_db_append_goal_shift_event_persists_row(db_conn):
    conn, run_id = db_conn
    shift = {
        "shift_kind": "constraint_hit", "from_goal_state": "{}", "to_goal_state": "{}",
        "reason_why": "テスト理由", "triggered_by": "Arbiter_Resource_Overrun",
    }
    cela_main.db_append_goal_shift_event(shift, conn, run_id)
    rows = conn.execute("SELECT * FROM goal_shift_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["shift_kind"] == "constraint_hit"
    assert rows[0]["reason_why"] == "テスト理由"


def test_r5_arbiter_node_writes_goal_shift_event_when_required(db_conn, monkeypatch):
    """arbiter_nodeが、call_resource_arbiterがrequires_goal_constraint_change=trueを
    返した場合にgoal_shift_eventsへ実際にINSERTすること（call_resource_arbiterはモック）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "予算クレーム",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision", "phase_id": "task_1_1",
        "resource_claims": {"予算": {"phase_id": "task_1_1", "value": 60000000, "total_cap": 100000000}},
    })
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "予算クレーム2",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision", "phase_id": "task_2_1",
        "resource_claims": {"予算": {"phase_id": "task_2_1", "value": 60000000, "total_cap": 100000000}},
    })

    monkeypatch.setattr(cela_main, "call_resource_arbiter", lambda goal, overrun, phases: {
        "phases_to_revise": ["task_1_1"],
        "rationale": "予算上限自体を引き上げる必要がある",
        "new_allocation": {"task_1_1": 70000000, "task_2_1": 60000000},
        "requires_goal_constraint_change": True,
    })

    state = {"run_id": run_id, "goal": "テストゴール", "phases": []}
    cela_main.arbiter_node(state)

    rows = conn.execute("SELECT * FROM goal_shift_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["shift_kind"] == "constraint_hit"
