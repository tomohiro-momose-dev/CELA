"""
BL-041 (global_constraintsの実働化) / BL-050 (決定事項DBの変遷履歴可視化) の
実LLM API呼び出しを伴わないオフライン検証項目。

参照: docs/design/issue_backlog.md BL-041, BL-050、
      docs/design/r1_r2_r3b_core/cela_facilitator_arbiter_redesign_BL041.md §3.1。
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
    db_path = str(tmp_path / "test_bl041_bl050.db")
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
# BL-041: global_constraintsの実働化
# ===========================================================================

def test_bl041_aggregate_global_constraints_detects_overrun():
    """新構造{name: {phase_id, value, total_cap}}のresource_claimsを持つagreementsから
    _aggregate_global_constraintsがGlobalConstraintを正しく集約し、
    check_global_constraint_overrunが超過を検出できること。"""
    agreements = [
        {
            "id": "AG-1", "status": "Approved", "entry_type": "Decision",
            "resource_claims": json.dumps({
                "初期導入予算": {"phase_id": "task_1_1", "value": 60000000, "total_cap": 100000000}
            }),
        },
        {
            "id": "AG-2", "status": "Approved", "entry_type": "Decision",
            "resource_claims": json.dumps({
                "初期導入予算": {"phase_id": "task_2_1", "value": 60000000, "total_cap": 100000000}
            }),
        },
    ]
    gcs = cela_main._aggregate_global_constraints(agreements)
    assert len(gcs) == 1
    assert gcs[0]["name"] == "初期導入予算"
    assert gcs[0]["total_cap"] == 100000000
    assert gcs[0]["claims"] == {"task_1_1": 60000000, "task_2_1": 60000000}

    state = {"global_constraints": gcs}
    overruns = cela_main.check_global_constraint_overrun(state)
    assert len(overruns) == 1
    assert overruns[0]["constraint"] == "初期導入予算"
    assert overruns[0]["over_by"] == 20000000


def test_bl041_aggregate_global_constraints_skips_superseded_and_malformed():
    """SupersededなagreementsのclaimsはOFFされること、旧形式（平坦な{name: 数値}）や
    壊れたJSONはクラッシュせず静かにスキップされること。"""
    agreements = [
        {
            "id": "AG-1", "status": "Superseded", "entry_type": "Decision",
            "resource_claims": json.dumps({
                "初期導入予算": {"phase_id": "task_1_1", "value": 90000000, "total_cap": 100000000}
            }),
        },
        {
            "id": "AG-2", "status": "Approved", "entry_type": "Decision",
            "resource_claims": json.dumps({"旧形式予算": 5000000}),
        },
        {
            "id": "AG-3", "status": "Approved", "entry_type": "Decision",
            "resource_claims": "{invalid json",
        },
        {
            "id": "AG-4", "status": "Approved", "entry_type": "Decision",
            "resource_claims": "",
        },
    ]
    gcs = cela_main._aggregate_global_constraints(agreements)
    assert gcs == [], "Supersededや不正形式のclaimsは集約対象に含まれるべきではない"


def test_bl041_arbiter_node_fires_on_real_overrun(db_conn, monkeypatch):
    """arbiter_nodeが毎回agreements DBから動的にglobal_constraintsを再集約し、
    実際に超過があればcall_resource_arbiterへ到達すること（従来は常に空振りしていた回帰確認）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = ""

    for phase_id, value in [("task_1_1", 60000000), ("task_2_1", 60000000)]:
        cela_main.TOOL_DISPATCH["write_agreement"]({
            "action_type": "CREATE", "status": "Approved", "topic": f"予算クレーム-{phase_id}",
            "decision_what": "d", "reason_why": "r", "entry_type": "Decision", "phase_id": phase_id,
            "resource_claims": {"初期導入予算": {"phase_id": phase_id, "value": value, "total_cap": 100000000}},
        })

    called_with = {}

    def fake_call_resource_arbiter(goal, overrun, phases, **kwargs):
        called_with["overrun"] = overrun
        return {"phases_to_revise": ["task_1_1"], "rationale": "予算超過のため再配分"}

    monkeypatch.setattr(cela_main, "call_resource_arbiter", fake_call_resource_arbiter)

    state = {"run_id": run_id, "goal": "テストゴール", "phases": []}
    result_state = cela_main.arbiter_node(state)

    assert called_with, "実際に予算超過があるのにcall_resource_arbiterへ到達しなかった（BL-041の回帰）"
    assert called_with["overrun"]["constraint"] == "初期導入予算"
    assert result_state["phases_to_revise"] == ["task_1_1"]


def test_bl041_arbiter_node_no_overrun_short_circuits(db_conn, monkeypatch):
    """超過が無い場合はcall_resource_arbiterに到達せず、phases_to_reviseが空のまま返ること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = ""

    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "予算クレーム-余裕あり",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision", "phase_id": "task_1_1",
        "resource_claims": {"初期導入予算": {"phase_id": "task_1_1", "value": 10000000, "total_cap": 100000000}},
    })

    def fail_if_called(*a, **k):
        raise AssertionError("超過が無いのにcall_resource_arbiterが呼ばれた")

    monkeypatch.setattr(cela_main, "call_resource_arbiter", fail_if_called)

    state = {"run_id": run_id, "goal": "テストゴール", "phases": []}
    result_state = cela_main.arbiter_node(state)
    assert result_state["phases_to_revise"] == []


# ===========================================================================
# BL-050: 決定事項DBの変遷履歴可視化
# ===========================================================================

def test_bl050_agreements_context_shows_prior_superseded_diff(db_conn):
    """同一topicでUPDATEされた場合、_build_agreements_contextの出力に現行内容だけでなく
    直前のSuperseded版の内容・理由も差分として表示されること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = ""

    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "車両台数",
        "decision_what": "車両台数は3台とする", "reason_why": "初期見積もり", "entry_type": "Decision",
    })
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Approved", "topic": "車両台数",
        "target_topic": "車両台数",
        "decision_what": "車両台数は2台とする", "reason_why": "3台から2台へ変更、予算不足のため",
        "entry_type": "Decision",
    })

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    ctx = cela_main._build_agreements_context(agreements)

    assert "車両台数は2台とする" in ctx, "現行版の内容が表示されていない"
    assert "3台から2台へ変更" in ctx, "現行版自身のreason_why（変更理由）が表示されていない"
    assert "前版 Superseded" in ctx, "直前版の差分表示（BL-050）が出力に含まれていない"
    assert "車両台数は3台とする" in ctx, "直前版の内容がSuperseded表示に含まれていない"
    assert "初期見積もり" in ctx, "直前版の当時の理由がSuperseded表示に含まれていない"


def test_bl050_agreements_context_no_diff_line_when_no_prior_version():
    """初回CREATEのみの場合はSuperseded差分行が出ないこと（誤発火の回帰確認）。"""
    agreements = [{
        "id": "AG-1", "status": "Approved", "entry_type": "Decision",
        "topic": "初回のみ", "decision_what": "初回の内容", "reason_why": "初回の理由",
    }]
    ctx = cela_main._build_agreements_context(agreements)
    assert "前版 Superseded" not in ctx


def test_bl050_write_agreement_tool_reason_why_requires_change_rationale_on_update():
    """WRITE_AGREEMENT_TOOLのreason_why説明文が、UPDATE/SUPERSEDE時に前の値からの
    変更理由を明示するよう要求する文言を含んでいること（プロンプト指示の存在確認）。"""
    desc = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["reason_why"]["description"]
    assert "UPDATE" in desc and "SUPERSEDE" in desc
    assert "changed from the previous value" in desc
