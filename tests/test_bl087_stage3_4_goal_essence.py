"""
BL-087 Stage3・Stage4: 「本質フェーズ」新設（task_planner分解より前に1回だけ、目標の
本質を言語化し全ノードへ常時注入する）と、Detector/User AIのレビュー観点への本質整合性
チェック追加（BL-069関連）。

Stage3は、BL-086のescalate_premise_concern（走行中に前提矛盾に気づいた際の事後
エスカレーション）だけでは、そもそも計画開始前に「本質を見失った計画」自体を防げない
という限界に対応する事前予防機構。goal_essenceテーブルに1回だけ保存し、
call_orchestrator/call_expert/call_detector/call_reflection/generate_user_utterance/
call_resource_arbiter/call_facilitator/call_integrator/call_reviewerの9箇所（BL-086の
D-058で確認された`state["goal"]`の9消費者と同じ集合）へ常時注入する。

参照: docs/design/issue_backlog.md BL-087、docs/design/decision_log.md D-059。
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
    db_path = str(tmp_path / "test_bl087_stage34.db")
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


# --- DB層 -------------------------------------------------------------------

def test_get_goal_essence_text_empty_when_not_yet_generated(db_conn):
    conn, run_id = db_conn
    assert cela_main._get_goal_essence_text(conn, run_id) == ""
    assert cela_main.get_goal_essence(conn, run_id) is None


def test_save_and_read_goal_essence_roundtrip(db_conn):
    conn, run_id = db_conn
    cela_main.db_save_goal_essence(conn, run_id, "高齢者の移動手段の実質的な確保", "バス3台では需要を満たせない可能性が高い")

    essence = cela_main.get_goal_essence(conn, run_id)
    assert essence["true_essence"] == "高齢者の移動手段の実質的な確保"

    text = cela_main._get_goal_essence_text(conn, run_id)
    assert "高齢者の移動手段の実質的な確保" in text
    assert "バス3台では需要を満たせない可能性が高い" in text


def test_save_goal_essence_is_idempotent_per_run(db_conn):
    """INSERT OR REPLACEにより、同一run_idで2回保存しても1行のみ残る。"""
    conn, run_id = db_conn
    cela_main.db_save_goal_essence(conn, run_id, "初版", "初版notes")
    cela_main.db_save_goal_essence(conn, run_id, "改訂版", "改訂版notes")

    rows = conn.execute("SELECT * FROM goal_essence WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 1
    assert cela_main.get_goal_essence(conn, run_id)["true_essence"] == "改訂版"


def test_call_goal_essence_analyst_is_given_python_repl_tool(monkeypatch):
    """ユーザー指摘: 本質フェーズは最も上流の判断であり、暗算のままだとハルシネーション
    リスクが後続の全タスクに伝播する。call_goal_essence_analystにもpython_replを与えること。"""
    captured = {}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None):
        captured["tools"] = tools
        return "{}"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    cela_main.call_goal_essence_analyst("テスト目標")

    # BL-093でthinkツールが追加されツールリストが増えたため、完全一致ではなく含有確認にする
    # （他の同種ノードで既に採用済みのパターンと同じ）。
    assert cela_main.PYTHON_REPL_TOOL in captured["tools"]


# --- goal_essence_node -------------------------------------------------------

def test_goal_essence_node_skips_when_already_done(db_conn, monkeypatch):
    _, run_id = db_conn
    called = {"n": 0}
    monkeypatch.setattr(cela_main, "call_goal_essence_analyst", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    state = {"run_id": run_id, "goal": "テスト目標", "goal_essence_done": True}
    result = cela_main.goal_essence_node(state)

    assert called["n"] == 0
    assert result["goal_essence_done"] is True


def test_goal_essence_node_saves_result_and_sets_flag(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_goal_essence_analyst",
        lambda goal: {"true_essence": "本質テキスト", "feasibility_notes": "懸念あり"},
    )

    state = {"run_id": run_id, "goal": "テスト目標"}
    result = cela_main.goal_essence_node(state)

    assert result["goal_essence_done"] is True
    essence = cela_main.get_goal_essence(conn, run_id)
    assert essence["true_essence"] == "本質テキスト"
    assert essence["feasibility_notes"] == "懸念あり"


# --- グラフ配線 ---------------------------------------------------------------

def test_graph_entry_point_is_goal_essence_and_wired_to_task_planner():
    compiled = cela_main.build_graph()
    graph_repr = compiled.get_graph()
    node_names = set(graph_repr.nodes.keys())
    assert "goal_essence" in node_names

    edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
    assert ("goal_essence", "task_planner") in edge_pairs
    assert ("__start__", "goal_essence") in edge_pairs


# --- Stage3: 消費者への注入配線確認（inspect.getsourceによる静的確認） -----------------
# BL-086 D-058が特定した9消費者（state["goal"]を毎ターン再埋め込みする箇所）に加え、
# task_planner/task_plan_reviewerはStage2で新設されたためD-058のリストには含まれておらず
# 当初注入漏れがあった（ユーザー指摘、2026-07-25）。計11箇所が本質テキストの注入対象。

@pytest.mark.parametrize("func_name", [
    "call_orchestrator", "call_expert", "call_detector",
    "call_reflection", "generate_user_utterance",
])
def test_state_based_consumers_call_get_goal_essence_text(func_name):
    """state/run_idを直接受け取る5関数は、_get_goal_essence_textを自分で呼び出す。"""
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "_get_goal_essence_text" in src


@pytest.mark.parametrize("func_name", [
    "call_resource_arbiter", "call_facilitator", "call_integrator", "call_reviewer",
    "call_task_planner", "call_task_plan_reviewer",
])
def test_pure_functions_accept_and_embed_goal_essence_text_param(func_name):
    """state/run_idを持たない6関数は、goal_essence_text引数を受け取りプロンプトに埋め込む
    （call_task_planner/call_task_plan_reviewerはStage2由来で当初注入漏れがあった箇所）。"""
    func = getattr(cela_main, func_name)
    sig = inspect.signature(func)
    assert "goal_essence_text" in sig.parameters

    src = inspect.getsource(func)
    assert "{goal_essence_text}" in src


def test_task_planner_node_fetches_and_passes_goal_essence_text():
    """task_planner_nodeが_get_goal_essence_textを取得し、call_task_plannerへ渡すこと
    （ユーザー指摘: goal_essenceの出力がtask_plannerに提示されていなかった注入漏れの修正確認）。"""
    src = inspect.getsource(cela_main.task_planner_node)
    assert "_get_goal_essence_text" in src
    assert "goal_essence_text=goal_essence_text" in src


@pytest.mark.parametrize("node_func_name,inner_func_name", [
    ("arbiter_node", "call_resource_arbiter"),
    ("facilitator_node", "call_facilitator"),
    ("integrator_node", "call_integrator"),
    ("reviewer_node", "call_reviewer"),
    ("task_plan_reviewer_node", "call_task_plan_reviewer"),
])
def test_node_call_sites_pass_goal_essence_text_to_pure_functions(node_func_name, inner_func_name):
    """呼び出し側ノードが、_get_goal_essence_textの結果を実際に引数として渡していること。"""
    src = inspect.getsource(getattr(cela_main, node_func_name))
    assert "goal_essence_text=_get_goal_essence_text(" in src


# --- Stage4: Detector・User AIの本質整合性チェック ------------------------------

def test_detector_domain_pass_includes_essence_consistency_instruction():
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-087 Stage4" in src
    assert "本質から" in src


def test_generate_user_utterance_includes_essence_consistency_instruction():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "BL-087 Stage4" in src
