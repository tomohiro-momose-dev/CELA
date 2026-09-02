"""
一時停止・再開（チェックポイント）機能のオフライン検証項目。実LLM API呼び出しを伴わない。

[BL-105/D-086 Tier1] 自前JSON checkpoint（_save_checkpoint/_load_checkpoint）は、--resume時に
必ずグラフのentry_pointから全体再走行するため、generate_user_utterance_nodeの再入場ガード
欠如と相まって、ラウンド途中で一時停止したものを再開するとuser発言が二重に積まれる欠陥が
あった。LangGraph公式のcheckpointer（SqliteSaver）+ thread_id（==run_id）ベースの再開へ移行し、
中断した直後のノードから再開する（entry_pointの全体再走行にはならない）ようにした。

参照: docs/design/back_log/BL-105/BL105_basic_design.md、docs/design/back_log/issue_backlog.md
BL-105、docs/design/decision_log.md D-086。実LLM API呼び出しは伴わない。
"""

import os
import sqlite3
import sys
from typing import TypedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph


# ---------------------------------------------------------------------------
# CELAの実グラフとは独立した、最小の合成グラフ（ノードA/ノードB＋条件分岐ループ＋END）で
# LangGraph checkpointerの再開挙動そのものを検証する。CELAの実ノード（実LLM呼び出し）を
# 使わないことで、高速かつ決定論的にコア動作を確認できる。
# ---------------------------------------------------------------------------

class _SyntheticState(TypedDict):
    steps: list[str]
    loop_count: int


def _build_synthetic_graph(checkpointer):
    calls = {"node_a": 0, "node_b": 0}

    def node_a(state):
        calls["node_a"] += 1
        return {"steps": state["steps"] + ["a"], "loop_count": state["loop_count"] + 1}

    def node_b(state):
        calls["node_b"] += 1
        return {"steps": state["steps"] + ["b"], "loop_count": state["loop_count"]}

    def route(state):
        return "node_b" if state["loop_count"] >= 2 else "node_a"

    g = StateGraph(_SyntheticState)
    g.add_node("node_a", node_a)
    g.add_node("node_b", node_b)
    g.set_entry_point("node_a")
    g.add_conditional_edges("node_a", route, {"node_a": "node_a", "node_b": "node_b"})
    g.add_edge("node_b", END)
    return g.compile(checkpointer=checkpointer), calls


def test_resume_continues_from_next_pending_node_not_entry_point(tmp_path):
    """核心の回帰テスト: Ctrl+C相当（generatorを最後まで消費せず打ち切る）で中断した後、
    同じthread_idにNoneを渡すと、entry_point(node_a)からではなく中断直後のノードから
    再開し、既に完了したnode_a 1回目を再実行しない。"""
    conn = sqlite3.connect(str(tmp_path / "ckpt.db"), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    app, calls = _build_synthetic_graph(checkpointer)
    runtime_config = {"configurable": {"thread_id": "t1"}}

    # 1ステップ目だけ消費して「中断」を模擬する（checkpointerには既にnode_a 1回目の結果が保存済み）
    gen = app.stream({"steps": [], "loop_count": 0}, config=runtime_config, stream_mode="values")
    next(gen)  # 初期state
    next(gen)  # node_a 1回目実行後
    gen.close()
    assert calls["node_a"] == 1

    # 再開: Noneを渡すと、node_aの2回目から続きが走る（1回目は再実行されない）
    final_state = None
    for step in app.stream(None, config=runtime_config, stream_mode="values"):
        final_state = step
    assert calls["node_a"] == 2  # 1回目は再実行されていない
    assert calls["node_b"] == 1
    assert final_state["steps"] == ["a", "a", "b"]
    conn.close()


def test_multi_turn_same_thread_id_after_completion_does_not_duplicate_list_fields(tmp_path):
    """CELA外側whileループのパターン（同一thread_idへ毎ターン、直前の完了stateをフルdictとして
    再投入）を模擬し、リスト系フィールドが二重蓄積しないことを検証する（LineageStateの唯一の
    Annotatedフィールドgoal(_take_latest)が上書き方式である前提の裏付け）。"""
    conn = sqlite3.connect(str(tmp_path / "ckpt.db"), check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    app, calls = _build_synthetic_graph(checkpointer)
    runtime_config = {"configurable": {"thread_id": "t2"}}

    state = {"steps": [], "loop_count": 0}
    for step in app.stream(state, config=runtime_config, stream_mode="values"):
        state = step
    assert state["steps"] == ["a", "a", "b"]

    # 2「ターン」目: 直前の完了stateをそのままフル投入（CELAの毎ターンパターン）
    state["loop_count"] = 0  # ラウンドカウンタだけ更新して再投入（CELAのturn_count更新と同型）
    for step in app.stream(state, config=runtime_config, stream_mode="values"):
        state = step
    assert state["steps"] == ["a", "a", "b", "a", "a", "b"]  # 2回分、二重蓄積なし
    conn.close()


def test_build_graph_accepts_checkpointer_and_defaults_to_none():
    """build_graph()のシグネチャ変更が既存のトポロジー確認専用テストと両立することの確認。"""
    compiled_default = cela_main.build_graph()
    compiled_explicit_none = cela_main.build_graph(checkpointer=None)
    assert set(compiled_default.get_graph().nodes.keys()) == set(compiled_explicit_none.get_graph().nodes.keys())


# ---------------------------------------------------------------------------
# run_ai_vs_ai_loopのresume分岐ロジック（build_graphをスタブに差し替え、実グラフ・実LLM
# 呼び出しなしで検証する）
# ---------------------------------------------------------------------------

class _FakeSnapshot:
    def __init__(self, values, next_nodes):
        self.values = values
        self.next = next_nodes


class _FakeCompiledGraph:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.get_state_calls = 0

    def get_state(self, runtime_config):
        self.get_state_calls += 1
        return self._snapshot

    def stream(self, *_args, **_kwargs):
        return iter(())


def test_run_ai_vs_ai_loop_reports_missing_run_id_and_returns(tmp_path, monkeypatch, capsys):
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values={}, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30, "reflection_interval": 3,
                "agent_has_guardrail": True},
        resume_run_id="存在しないrun_id",
    )

    assert fake_graph.get_state_calls == 1
    assert "見つかりませんでした" in capsys.readouterr().out


def test_run_ai_vs_ai_loop_fresh_run_never_calls_get_state(tmp_path, monkeypatch):
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values={}, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
    # streamが空のため、whileループは1回も回らずcurrent_turn<=max_turnsで即座にelse節へ抜ける。
    # DB接続は本物のcela.db（get_db_connection）を使うため、tmp_path配下へ逃がす。
    db_path = str(tmp_path / "cela.db")

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 0, "reflection_interval": 3,
                "agent_has_guardrail": True},
        db_path=db_path,
        resume_run_id=None,
    )

    assert fake_graph.get_state_calls == 0


def test_resume_refreshes_config_derived_limits_from_current_config(tmp_path, monkeypatch, capsys):
    """[BL-201] チェックポイントから復元したstateは、そのrunが開始された時点のconfigの値
    （呼び出し回数上限・goal_reference_dir）を固定で保持している。BL-199でmax_web_search_calls
    を30→50へ緩和した後もresumeしたrunが30回で頭打ちになっていた
    （log/2026-08-09/2313で実機確認）ため、resume時に現在のconfigの値へ再同期する。
    会話状態（chat_history等）は上書きしないことを、stateにそれらのキーを含めず検証する。"""
    stale_state = {
        "db_path": str(tmp_path / "cela.db"),
        "turn_count": 5,
        "halt": True,  # 早期returnさせ、グラフ実行やDB接続を発生させずに済ませる
        "discussion_status": "halted",
        "max_web_search_calls": 30,
        "max_web_fetch_calls": 30,
        "max_road_route_calls": 30,
        "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30, "reflection_interval": 3,
                "agent_has_guardrail": True, "max_web_search_calls": 50, "max_web_fetch_calls": 40,
                "max_road_route_calls": 25, "goal_reference_dir": "docs/refs/chino_city"},
        resume_run_id="run-with-stale-limits",
    )

    assert stale_state["max_web_search_calls"] == 50
    assert stale_state["max_web_fetch_calls"] == 40
    assert stale_state["max_road_route_calls"] == 25
    assert stale_state["goal_reference_dir"] == "docs/refs/chino_city"


def test_task_planner_node_skips_replanning_when_phases_already_exist():
    """再開時、turn_count==1のままtask_planner_nodeを再度通っても、
    既にphasesが確定済みならcall_task_plannerを再実行しない（冪等性ガード）。"""
    state = {
        "turn_count": 1,
        "phases": [{"phase_id": "phase_1", "title": "既存フェーズ", "tasks": []}],
        "run_id": "test-run",
    }
    result = cela_main.task_planner_node(state)
    # phasesが上書きされていない（既存の内容のまま）ことを確認
    assert result["phases"] == [{"phase_id": "phase_1", "title": "既存フェーズ", "tasks": []}]
