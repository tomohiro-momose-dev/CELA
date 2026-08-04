"""
BL-126 Stage D: Facilitatorのツールループ化 + 本質対話（Essence Dialogue）ループ +
Reflectionの迎合（collusion）監査基準の追加。

Facilitatorが「議論への単発の介入」役に留まらず、write_agreement(entry_type="EssenceProposal")
でゴールの前提・制約そのものを問い直す対話を開始し、User AIとの往復（generate_user_utterance
⇄ facilitator、既存のuser_detector経由の通常監査をこの間だけスキップ）を経て、Userの承認
（EssenceProposalのUPDATE/Approved）またはラウンド上限（5）到達で収束/タイムアウトする。
収束時はplan_revision_reasonをセットし、Stage C（Task Plannerのラン途中再構成）へ引き継ぐ。

参照: docs/design/back_log/issue_backlog.md BL-126、
      docs/design/back_log/BL-126/BL126_basic_design.md §2・§3・§7・§13.2。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl126_stage_d.db")
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


# --- write_agreement: entry_type="EssenceProposal" ------------------------------

def test_facilitator_can_write_essence_proposal_as_proposed(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "essence_dialogue_bus_size",
            "decision_what": "車両サイズの前提を問い直したい", "reason_why": "需要密度と矛盾",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    assert result["success"] is True


def test_facilitator_cannot_write_essence_proposal_as_approved(db_conn):
    """[BL-095型の制約] facilitatorはtask_planner/goal_essence_analystと同様、自らの提起を
    Approvedとして名乗れない（最終承認はUser AIの役目）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Approved", "topic": "essence_dialogue_bus_size",
            "decision_what": "車両サイズの前提を問い直したい", "reason_why": "需要密度と矛盾",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    assert result["success"] is False


def test_user_can_approve_essence_proposal(db_conn):
    """User AIはentry_type問わず全statusを持つため、EssenceProposalのApproved確定ができる。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "essence_dialogue_bus_size",
            "decision_what": "車両サイズの前提を問い直したい", "reason_why": "需要密度と矛盾",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "essence_dialogue_bus_size",
            "target_topic": "essence_dialogue_bus_size",
            "decision_what": "承認します", "reason_why": "妥当な再検討だった",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    assert result["success"] is True


def test_essence_proposal_is_exempt_from_task_id_check():
    """[BL-131との整合] entry_type='EssenceProposal'はDecisionと同様、特定タスクに紐づかない
    全体決定でありうるため、task_id実在チェックの対象外であること。"""
    src = inspect.getsource(cela_main._write_agreement_impl)
    idx = src.index('if args["entry_type"] in ("Directive", "Deliverable"):')
    snippet = src[idx: idx + 100]
    assert "EssenceProposal" not in snippet


# --- get_last_essence_proposal ブリッジ -----------------------------------------

def test_get_last_essence_proposal_captures_successful_write(db_conn):
    conn, run_id = db_conn
    cela_main._LAST_ESSENCE_PROPOSAL = None
    assert cela_main.get_last_essence_proposal() is None

    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "essence_dialogue_x",
            "decision_what": "本質を問い直したい", "reason_why": "理由",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    proposal = cela_main.get_last_essence_proposal()
    assert proposal is not None
    assert proposal["topic"] == "essence_dialogue_x"
    assert proposal["status"] == "Proposed"
    assert proposal["action_type"] == "CREATE"


def test_query_ai_resets_last_essence_proposal(monkeypatch, db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "essence_dialogue_x",
            "decision_what": "本質を問い直したい", "reason_why": "理由",
            "entry_type": "EssenceProposal",
        },
        {"run_id": run_id, "phases": []},
    )
    assert cela_main.get_last_essence_proposal() is not None

    monkeypatch.setattr(cela_main, "_query_AI_live", lambda *a, **k: "OK")
    cela_main.query_AI([{"role": "user", "content": "x"}], client=None, model="m", label="test")
    assert cela_main.get_last_essence_proposal() is None


# --- escalate_premise_concern: facilitatorロール許可 -----------------------------

def test_facilitator_can_escalate_premise_concern(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "facilitator"
    result = cela_main.TOOL_DISPATCH["escalate_premise_concern"](
        {
            "concern_summary": "車両サイズの前提が矛盾", "implicated_constraint": "台数上限2台",
            "why_conflicts_with_true_need": "オンデマンド輸送には小型車が適する",
            "suggested_reframe": "小型車両複数台",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


# --- facilitator_node: essence dialogueの開始・継続・収束・タイムアウト -----------

def _base_facilitator_state(run_id: str) -> dict:
    return {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール",
        "run_id": run_id,
        "last_reflection_note": "",
        "essence_dialogue_active": False,
        "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5,
        "essence_dialogue_topic": "",
        "last_essence_proposal": None,
    }


def test_facilitator_node_opens_essence_dialogue_on_new_proposal(db_conn, monkeypatch):
    conn, run_id = db_conn

    def fake_call_facilitator(goal, chat_history, reflection_note="", **kwargs):
        cela_main._CURRENT_CALLER_ROLE = "facilitator"
        cela_main.TOOL_DISPATCH["write_agreement"](
            {
                "action_type": "CREATE", "status": "Proposed", "topic": "essence_dialogue_x",
                "decision_what": "本質を問い直したい", "reason_why": "理由",
                "entry_type": "EssenceProposal",
            },
            {"run_id": run_id, "phases": []},
        )
        return "本質を問い直したいのですが、よろしいですか？"

    monkeypatch.setattr(cela_main, "call_facilitator", fake_call_facilitator)

    state = _base_facilitator_state(run_id)
    result = cela_main.facilitator_node(state)

    assert result["essence_dialogue_active"] is True
    assert result["essence_dialogue_round"] == 1
    assert result["essence_dialogue_topic"] == "essence_dialogue_x"


def test_facilitator_node_does_not_increment_facilitation_count_during_active_dialogue(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")

    state = _base_facilitator_state(run_id)
    state["facilitation_count"] = 3  # 既に上限ぎりぎりだが、対話モード中はここに触れないはず
    state["essence_dialogue_active"] = True
    state["essence_dialogue_round"] = 1
    result = cela_main.facilitator_node(state)

    assert result["facilitation_count"] == 3
    assert result.get("halt") is not True


def test_facilitator_node_converges_and_sets_plan_revision_reason_on_user_approval(db_conn, monkeypatch):
    monkeypatch.setattr(cela_main, "call_facilitator", lambda *a, **k: (_ for _ in ()).throw(AssertionError("収束時はcall_facilitatorを呼んではならない")))
    conn, run_id = db_conn

    state = _base_facilitator_state(run_id)
    state["essence_dialogue_active"] = True
    state["essence_dialogue_round"] = 2
    state["essence_dialogue_topic"] = "essence_dialogue_x"
    state["last_essence_proposal"] = {
        "topic": "essence_dialogue_x", "status": "Approved", "action_type": "UPDATE",
        "reason_why": "小型車両複数台の構成へ見直す",
    }
    result = cela_main.facilitator_node(state)

    assert result["essence_dialogue_active"] is False
    assert result["essence_dialogue_round"] == 0
    assert result["plan_revision_reason"] == "小型車両複数台の構成へ見直す"


def test_facilitator_node_times_out_without_plan_revision_reason(db_conn, monkeypatch):
    monkeypatch.setattr(cela_main, "call_facilitator", lambda *a, **k: (_ for _ in ()).throw(AssertionError("タイムアウト時はcall_facilitatorを呼んではならない")))
    conn, run_id = db_conn

    state = _base_facilitator_state(run_id)
    state["essence_dialogue_active"] = True
    state["essence_dialogue_round"] = 5
    state["essence_dialogue_max_rounds"] = 5
    state["essence_dialogue_topic"] = "essence_dialogue_x"
    result = cela_main.facilitator_node(state)

    assert result["essence_dialogue_active"] is False
    assert result.get("plan_revision_reason", "") == ""


def test_facilitator_node_continues_dialogue_when_not_yet_converged_or_timed_out(db_conn, monkeypatch):
    conn, run_id = db_conn
    called = {"n": 0}

    def fake_call_facilitator(goal, chat_history, reflection_note="", **kwargs):
        called["n"] += 1
        return "さらに議論を深めましょう"

    monkeypatch.setattr(cela_main, "call_facilitator", fake_call_facilitator)

    state = _base_facilitator_state(run_id)
    state["essence_dialogue_active"] = True
    state["essence_dialogue_round"] = 2
    state["essence_dialogue_topic"] = "essence_dialogue_x"
    state["last_essence_proposal"] = None  # Userはまだ承認していない
    result = cela_main.facilitator_node(state)

    assert called["n"] == 1
    assert result["essence_dialogue_active"] is True
    assert result["essence_dialogue_round"] == 3


# --- generate_user_utterance_node: last_essence_proposalの橋渡し -----------------

def test_generate_user_utterance_node_bridges_last_essence_proposal(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "承認します")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    monkeypatch.setattr(
        cela_main, "get_last_essence_proposal",
        lambda: {"topic": "essence_dialogue_x", "status": "Approved", "action_type": "UPDATE", "reason_why": "r"},
    )

    state = {
        "round_count": 0, "constraint_issue": "none", "user_retry_count": 0,
        "chat_history": [], "turn_count": 1, "run_id": run_id, "goal": "テストゴール",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result["last_essence_proposal"] == {
        "topic": "essence_dialogue_x", "status": "Approved", "action_type": "UPDATE", "reason_why": "r",
    }


# --- generate_user_utteranceのモード分岐（§13.2/§13.3） --------------------------

def test_generate_user_utterance_essence_dialogue_prompt_takes_priority_over_expert_question():
    """[§13.3] essence_dialogue_activeとexpert_pending_questionが同時に立つことは想定しないが、
    elif連鎖により必ずessence_dialogue側が優先されること（排他性の実装確認）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    if_idx = src.index('if state.get("essence_dialogue_active"):')
    elif_idx = src.index('elif state.get("expert_pending_question"):')
    assert if_idx < elif_idx


# --- グラフルーティング（generate_user_utterance -> facilitator バイパス） -------

def test_generate_user_utterance_to_facilitator_edge_exists():
    compiled = cela_main.build_graph()
    graph_repr = compiled.get_graph()
    edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
    assert ("generate_user_utterance", "facilitator") in edge_pairs
    assert ("generate_user_utterance", "user_detector") in edge_pairs


# --- Reflection迎合（collusion）監査基準 -----------------------------------------

def test_call_reflection_includes_collusion_audit_criteria():
    src = inspect.getsource(cela_main.call_reflection)
    assert "迎合" in src
    assert "重大さに見合っている" in src
