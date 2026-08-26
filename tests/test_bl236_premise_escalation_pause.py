"""
BL-236拡張: escalate_premise_concern成功時にグラフ実行を一時停止し、人間が
--answer-human-inputで回答した後に--resumeで再開できるようにする機能。

背景: escalate_premise_concern（BL-236）は成功時にHILゲートをissue_logへ起票し、
revise_goalの実適用のみをブロックしていたが、グラフの実行自体は止まらなかった。
実ドライラン（log/2026-08-26/0031/）で、ゴール文内部矛盾のエスカレーション提起後も
タスクが多数完了し統合フェーズまで進んでしまった事故を受け、グラフ全体を一時停止する
機能を追加する。

設計方針:
- 新規フラグ state["paused_for_premise_escalation"]（永続、単発消費ではない）と
  state["pending_premise_escalation_id"]をLineageStateへ追加。
- _LAST_GOAL_REVISIONと同型のブリッジ（_LAST_PREMISE_ESCALATION）を新設し、
  generate_user_utterance_node/expert_node/facilitator_nodeの3箇所（escalate_premise_concernは
  expert/user/facilitatorの3ロールから呼べるため）で消費してstateへ反映する。
- generate_user_utteranceのBL-177 4段階パイプラインは各段が独立したquery_AI呼び出しで
  その都度グローバルがリセットされるため、_stage_goal_revisionと同型の
  _stage_premise_escalationでステージ横断集約してから書き戻す。
- 新規ノードpause_for_human_node（halt_nodeと同型、add_edge(..., END)で無条件終端）を追加し、
  5つのルーティング関数（route_after_user_decision/route_after_expert_decision/
  route_after_reflection/route_after_facilitator/route_after_reviewer）それぞれで、
  既存のhalt判定の直後・他の判定より前に共有述語_should_pause_for_humanのチェックを追加する。
- run_ai_vs_ai_loopのresumeガードは、HIL回答（_get_goal_escalation_hil_decision）が
  確認できるまで再開を拒否し、確認できたらフラグをリセットして通常resumeへ合流する。
  pause_for_human_nodeは常にラウンド境界（snapshot.next空）で停止するため、BL-203の
  「pending_resume_drain経路でローカルstateが伝播しない」問題には該当しない。

参照: docs/design/back_log/issue_backlog.md（本BL）、BL-236（escalate_premise_concernの原設計）、
BL-086（_LAST_GOAL_REVISIONブリッジの原設計）、BL-203（resume時のconfig再同期とapp.update_state()
却下の経緯）、BL-262（ルーティング関数のソース検査パターン）。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl236_pause.db")
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


# ---------------------------------------------------------------------------
# A. _should_pause_for_human（単体）
# ---------------------------------------------------------------------------

def test_should_pause_for_human_true():
    assert cela_main._should_pause_for_human({"paused_for_premise_escalation": True}) is True


def test_should_pause_for_human_false():
    assert cela_main._should_pause_for_human({"paused_for_premise_escalation": False}) is False


def test_should_pause_for_human_false_when_key_absent():
    assert cela_main._should_pause_for_human({}) is False


# ---------------------------------------------------------------------------
# B. ブリッジ配線（ソース検査）
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_name", [
    "generate_user_utterance_node", "expert_node", "facilitator_node",
])
def test_bridge_wiring_references_get_last_premise_escalation(node_name):
    """3つの消費ノードすべてがget_last_premise_escalationを参照していること。"""
    src = inspect.getsource(getattr(cela_main, node_name))
    assert "get_last_premise_escalation" in src
    assert "paused_for_premise_escalation" in src


def test_query_ai_live_only_bridges_on_success():
    """[AGENTS.md §13] escalate_premise_concernのresult.get('success')チェックが
    _LAST_PREMISE_ESCALATIONへの代入より前にあること（revise_goalの消費パターンと
    同じ二重ガード。失敗時に反映されるとpause_for_humanが誤発火する）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    idx = src.index('tc.function.name == "escalate_premise_concern"')
    block = src[idx: idx + 500]
    assert 'result.get("success")' in block
    assert "_LAST_PREMISE_ESCALATION = {" in block


def test_generate_user_utterance_stage_aggregates_premise_escalation():
    """[BL-177] Stage2でescalate_premise_concernが成功しても、後続Stage3/4のquery_AI呼び出しで
    リセットされずに最終的な_LAST_PREMISE_ESCALATIONへ書き戻されること。
    _stage_goal_revisionと同型の集約パターンをソース検査で確認する。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_stage_premise_escalation" in src
    assert "get_last_premise_escalation()" in src
    assert "_LAST_PREMISE_ESCALATION = _stage_premise_escalation" in src


# ---------------------------------------------------------------------------
# C. 3ノードの実挙動: escalate_premise_concern成功検知でフラグをセットする
# ---------------------------------------------------------------------------

def test_generate_user_utterance_node_sets_paused_flag_on_escalation(monkeypatch):
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "発言内容")
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: {
        "escalation_id": "ESC-1", "caller_role": "user", "concern_summary": "前提矛盾",
    })
    monkeypatch.setattr(cela_main, "get_active_conn", lambda: None)
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "_write_chat_history_row", lambda *a, **k: 0)
    monkeypatch.setattr(cela_main, "get_last_think_summary", lambda: "")
    state = {
        "goal": "テストゴール", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [], "run_id": "test-run",
    }
    result = cela_main.generate_user_utterance_node(state)
    assert result["paused_for_premise_escalation"] is True
    assert result["pending_premise_escalation_id"] == "ESC-1"


def test_generate_user_utterance_node_keeps_flag_false_when_no_escalation(monkeypatch):
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "発言内容")
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: None)
    monkeypatch.setattr(cela_main, "get_active_conn", lambda: None)
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "_write_chat_history_row", lambda *a, **k: 0)
    monkeypatch.setattr(cela_main, "get_last_think_summary", lambda: "")
    state = {
        "goal": "テストゴール", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [], "run_id": "test-run",
    }
    result = cela_main.generate_user_utterance_node(state)
    assert result.get("paused_for_premise_escalation", False) is False
    assert result.get("pending_premise_escalation_id", "") == ""


def test_expert_node_sets_paused_flag_on_escalation(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "成果物です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: {
        "escalation_id": "ESC-2", "caller_role": "expert", "concern_summary": "前提矛盾",
    })
    state = {
        "chat_history": [], "expert_retry_count": 0, "constraint_issue": "none",
        "constraint_issue_log": [], "selected_expert": "テスト専門家",
        "run_id": run_id, "current_task_id": "task_1_1",
    }
    result = cela_main.expert_node(state)
    assert result["paused_for_premise_escalation"] is True
    assert result["pending_premise_escalation_id"] == "ESC-2"


def test_facilitator_node_sets_paused_flag_on_escalation(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: {
        "escalation_id": "ESC-3", "caller_role": "facilitator", "concern_summary": "前提矛盾",
    })
    state = {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール", "run_id": run_id, "last_reflection_note": "",
        "essence_dialogue_active": False, "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5, "essence_dialogue_topic": "",
        "last_essence_proposal": None,
    }
    result = cela_main.facilitator_node(state)
    assert result["paused_for_premise_escalation"] is True
    assert result["pending_premise_escalation_id"] == "ESC-3"


# ---------------------------------------------------------------------------
# D. ルーティング関数（ソース検査）: haltが先、pauseは後。宛先マップにpause_for_humanがある
# ---------------------------------------------------------------------------

def _build_graph_source() -> str:
    return inspect.getsource(cela_main.build_graph)


@pytest.mark.parametrize("router,edges_anchor", [
    ("route_after_user_decision", '"user_decision_extractor",\n        route_after_user_decision,'),
    ("route_after_expert_decision", '"expert_decision_extractor", route_after_expert_decision,'),
    ("route_after_reflection", '"reflection",\n        route_after_reflection,'),
    ("route_after_facilitator", '"facilitator",\n        route_after_facilitator,'),
    ("route_after_reviewer", '"reviewer",\n        route_after_reviewer,'),
])
def test_router_checks_halt_before_pause_and_registers_destination(router, edges_anchor):
    src = _build_graph_source()
    idx = src.index(f"def {router}(state")
    body = src[idx: idx + 1600]
    assert "_should_pause_for_human(state)" in body, f"{router}にpause判定が無い"
    if 'state["halt"]' in body:
        halt_pos = body.index('state["halt"]')
    else:
        halt_pos = body.index('state.get("halt")')
    pause_pos = body.index("_should_pause_for_human(state)")
    assert halt_pos < pause_pos, f"{router}: halt判定がpause判定より後になっている"
    assert 'return "pause_for_human"' in body

    edges_idx = src.index(edges_anchor)
    edges_block = src[edges_idx: edges_idx + 400]
    assert '"pause_for_human": "pause_for_human"' in edges_block, f"{router}の宛先マップにpause_for_humanが無い"


def test_pause_for_human_node_registered_and_routes_to_end():
    app = cela_main.build_graph()
    nodes = app.get_graph().nodes
    assert "pause_for_human" in nodes
    assert "halt" in nodes


def test_pause_for_human_node_writes_decision(db_conn):
    conn, run_id = db_conn
    state = {
        "run_id": run_id, "turn_count": 3,
        "pending_premise_escalation_id": "ESC-nonexistent",
    }
    result = cela_main.pause_for_human_node(state)
    assert result is state
    row = conn.execute(
        "SELECT who, what FROM decisions WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)
    ).fetchone()
    assert row["who"] == "system"
    assert "一時停止" in row["what"]


# ---------------------------------------------------------------------------
# E. run_ai_vs_ai_loopのouterループ: resumeガード・通常break判定
# ---------------------------------------------------------------------------

class _FakeSnapshot:
    def __init__(self, values, next_nodes):
        self.values = values
        self.next = next_nodes


class _FakeCompiledGraph:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.get_state_calls = 0
        self.stream_calls = []

    def get_state(self, runtime_config):
        self.get_state_calls += 1
        return self._snapshot

    def stream(self, *args, **kwargs):
        self.stream_calls.append(args)
        return iter(())


def test_resume_blocks_when_premise_escalation_unanswered(tmp_path, monkeypatch, capsys):
    stale_state = {
        "db_path": str(tmp_path / "cela.db"),
        "turn_count": 5, "halt": False,
        "paused_for_premise_escalation": True,
        "pending_premise_escalation_id": "ESC-unanswered",
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id="run-paused-unanswered",
    )

    assert fake_graph.stream_calls == []
    assert "回答待ち" in capsys.readouterr().out


def test_resume_proceeds_and_resets_flag_when_premise_escalation_answered(tmp_path, monkeypatch):
    stale_state = {
        "db_path": str(tmp_path / "cela.db"),
        "turn_count": 5, "max_turns": 30, "halt": False,
        "discussion_status": "continuing",
        "paused_for_premise_escalation": True,
        "pending_premise_escalation_id": "ESC-answered",
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
    monkeypatch.setattr(cela_main, "_get_goal_escalation_hil_decision", lambda conn, rid, esc_id: "approved")

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id="run-paused-answered",
    )

    assert fake_graph.stream_calls != []
    passed_state = fake_graph.stream_calls[0][0]
    assert passed_state["paused_for_premise_escalation"] is False
    assert passed_state["pending_premise_escalation_id"] == ""


def test_resume_halt_still_wins_over_pause(tmp_path, monkeypatch, capsys):
    """halt=Trueかつpaused_for_premise_escalation=Trueの場合、既存のhalt早期returnが
    先に発火し、pauseガードには到達しないこと（優先順位の回帰検出）。"""
    stale_state = {
        "db_path": str(tmp_path / "cela.db"),
        "turn_count": 5, "halt": True, "discussion_status": "halted",
        "paused_for_premise_escalation": True,
        "pending_premise_escalation_id": "ESC-both",
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id="run-halt-and-paused",
    )

    assert fake_graph.stream_calls == []
    assert "既にhalt済み" in capsys.readouterr().out


def test_run_loop_breaks_on_paused_flag_without_halt(tmp_path, monkeypatch, capsys):
    """streamが1回のみyieldし、その結果がpaused_for_premise_escalation=True（halt=False）
    であれば、whileループがbreakしてrunが終了すること。"""
    db_path = str(tmp_path / "cela.db")

    class _OneShotFreshGraph:
        def get_state(self, runtime_config):
            raise AssertionError("新規runでget_stateは呼ばれないはず")

        def stream(self, initial_state, config, stream_mode):
            yielded_state = dict(initial_state)
            yielded_state["halt"] = False
            yielded_state["paused_for_premise_escalation"] = True
            yielded_state["pending_premise_escalation_id"] = "ESC-live"
            yielded_state["discussion_status"] = "continuing"
            yield yielded_state

    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _OneShotFreshGraph())
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        db_path=db_path,
        resume_run_id=None,
    )

    assert "前提エスカレーション" in capsys.readouterr().out
