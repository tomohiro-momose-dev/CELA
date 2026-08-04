"""
BL-130: Expertが成果物を出さずにUser AIへ質問・相談できる双方向チャネル。

従来はUser AI→Expertへの一方向指示のみで、Expertが要求の曖昧さ等で本当に前進できない
場合でも見切り発車で成果物を作らざるを得なかった。ask_user_questionツールを新設し、
Expertが呼ぶと当該ターンは成果物レビュー扱いではなく「質問ターン」として扱われ、
Detector/Decision Extractorの厳格な監査・抽出をスキップしてUser AIへ直接質問を提示する。

参照: docs/design/back_log/issue_backlog.md BL-130、
      docs/design/back_log/BL-126/BL126_basic_design.md §2・§3・§13.2。
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


def _reset_globals():
    cela_main._LAST_ASK_USER_QUESTION = None
    cela_main._CURRENT_CALLER_ROLE = ""


# --- ツール本体（_ask_user_question_tool_impl） --------------------------------

def test_ask_user_question_rejects_non_expert_caller():
    _reset_globals()
    result = cela_main._ask_user_question_tool_impl(
        {"question_text": "仕様の解釈について", "blocking_reason": "複数の解釈があり判断できない"},
        caller_role="user",
    )
    assert result["success"] is False
    assert "expert" in result["error"]


def test_ask_user_question_requires_both_fields():
    _reset_globals()
    result = cela_main._ask_user_question_tool_impl({"question_text": "質問だけ"}, caller_role="expert")
    assert result["success"] is False
    assert "必須" in result["error"]


def test_ask_user_question_success_records_last_ask_user_question():
    _reset_globals()
    assert cela_main.get_last_ask_user_question() is None

    result = cela_main._ask_user_question_tool_impl(
        {"question_text": "調達方法Aと Bのどちらを採用しますか？", "blocking_reason": "acceptance_criteriaがどちらの前提かに依存する"},
        caller_role="expert",
    )
    assert result["success"] is True

    recorded = cela_main.get_last_ask_user_question()
    assert recorded == {
        "question_text": "調達方法Aと Bのどちらを採用しますか？",
        "blocking_reason": "acceptance_criteriaがどちらの前提かに依存する",
    }


def test_ask_user_question_tool_registered_in_dispatch():
    """[BL-131/TOOL_DISPATCH state化] 他ハンドラと同じく`(args, state=None)`の薄いラムダ経由。"""
    assert "ask_user_question" in cela_main.TOOL_DISPATCH

    _reset_globals()
    cela_main._CURRENT_CALLER_ROLE = "expert"
    args = {"question_text": "dispatch経由の確認", "blocking_reason": "テスト"}
    result = cela_main.TOOL_DISPATCH["ask_user_question"](dict(args))
    assert result["success"] is True
    assert cela_main.get_last_ask_user_question()["question_text"] == "dispatch経由の確認"


def test_query_ai_resets_last_ask_user_question(monkeypatch):
    """query_AI呼び出しごとに_LAST_ASK_USER_QUESTIONがリセットされること
    （_LAST_GOAL_REVISION等の既存フィールドと同型のライフサイクル）。"""
    _reset_globals()
    cela_main._ask_user_question_tool_impl(
        {"question_text": "前回ターンの質問", "blocking_reason": "r"}, caller_role="expert",
    )
    assert cela_main.get_last_ask_user_question() is not None

    monkeypatch.setattr(cela_main, "_query_AI_live", lambda *a, **k: "OK")
    cela_main.query_AI([{"role": "user", "content": "x"}], client=None, model="m", label="test")
    assert cela_main.get_last_ask_user_question() is None


# --- call_expertへのツール追加・プロンプト文言 ----------------------------------

def test_call_expert_includes_ask_user_question_tool_in_tools_list():
    src = inspect.getsource(cela_main.call_expert)
    assert "ASK_USER_QUESTION_TOOL" in src


def test_call_expert_light_system_prompt_mentions_ask_user_question():
    src = inspect.getsource(cela_main.call_expert)
    assert "ask_user_question" in src


# --- expert_nodeのフラグ設定・リセット -------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl130.db")
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


def _base_expert_state(run_id: str) -> dict:
    return {
        "chat_history": [],
        "expert_retry_count": 0,
        "constraint_issue": "none",
        "constraint_issue_log": [],
        "selected_expert": "テスト専門家",
        "run_id": run_id,
        "current_task_id": "task_1_1",
    }


def test_expert_node_sets_consultation_mode_when_ask_user_question_called(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "質問があります")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(
        cela_main, "get_last_ask_user_question",
        lambda: {"question_text": "この前提で進めてよいですか？", "blocking_reason": "r"},
    )

    state = _base_expert_state(run_id)
    result = cela_main.expert_node(state)

    assert result["expert_consultation_mode"] is True
    assert result["expert_pending_question"] == "この前提で進めてよいですか？"
    assert result["expert_blocking_reason"] == "r"


def test_expert_node_resets_consultation_mode_when_not_called(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "成果物です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)

    state = _base_expert_state(run_id)
    state["expert_consultation_mode"] = True
    state["expert_pending_question"] = "残留していたはずの前回の質問"
    state["expert_blocking_reason"] = "残留していたはずの前回の理由"
    result = cela_main.expert_node(state)

    assert result["expert_consultation_mode"] is False
    assert result["expert_pending_question"] == ""
    assert result["expert_blocking_reason"] == ""


# --- detector_nodeの軽量パス ----------------------------------------------------

def test_detector_node_skips_call_detector_during_expert_consultation(db_conn, monkeypatch):
    conn, run_id = db_conn
    called = {"n": 0}

    def _fail_if_called(*args, **kwargs):
        called["n"] += 1
        raise AssertionError("expert_consultation_mode中はcall_detectorを呼んではならない")

    monkeypatch.setattr(cela_main, "call_detector", _fail_if_called)

    state = {
        "chat_history": [{"role": "assistant", "content": "質問があります"}],
        "expert_consultation_mode": True,
        "expert_last_python_calls": [],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
    }
    result = cela_main.detector_node(state)

    assert called["n"] == 0
    assert result["constraint_issue"] == "none"


def test_detector_node_still_audits_normal_expert_turn(db_conn, monkeypatch):
    """expert_consultation_modeがFalse（通常の成果物ターン）ではcall_detectorが呼ばれること
    （軽量パス追加による既存経路への回帰がないことの確認）。"""
    conn, run_id = db_conn
    called = {"n": 0}

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        called["n"] += 1
        return {"risk": "low", "constraint_issue": "none", "comment": "OK"}

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = {
        "chat_history": [{"role": "assistant", "content": "成果物です"}],
        "expert_consultation_mode": False,
        "expert_last_python_calls": [{"code": "1+1", "result": "2"}],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
    }
    cela_main.detector_node(state)

    assert called["n"] == 1


# --- generate_user_utterance_nodeでのフラグ消費 ---------------------------------

def test_generate_user_utterance_node_resets_expert_consultation_flags(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "回答: Aで進めます")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = {
        "round_count": 0,
        "constraint_issue": "none",
        "user_retry_count": 0,
        "chat_history": [],
        "expert_consultation_mode": True,
        "expert_pending_question": "調達方法Aと Bのどちらですか？",
        "expert_blocking_reason": "acceptance_criteriaがどちらの前提かに依存する",
        "turn_count": 1,
        "run_id": run_id,
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result["expert_consultation_mode"] is False
    assert result["expert_pending_question"] == ""
    assert result["expert_blocking_reason"] == ""


def test_generate_user_utterance_injects_pending_question_into_prompt():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert 'state.get("expert_pending_question")' in src
    assert "成果物ではありません" in src


def test_generate_user_utterance_injects_blocking_reason_into_prompt():
    """[BL-135] blocking_reasonが質問文の直後に埋め込まれ、User AIが「本当にブロッキングな
    質問か」を判断する材料として提示されることを確認する。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "expert_blocking_reason" in src
    question_idx = src.index("質問: {state['expert_pending_question']}")
    reason_idx = src.index("理由: {state.get('expert_blocking_reason', '')}")
    assert question_idx < reason_idx


# --- グラフルーティング（expert_consultation_mode時のバイパス） -------------------

def test_expert_detector_edge_to_generate_user_utterance_exists():
    """route_after_expert_detectorの新分岐（BL-130）がグラフの宣言済みエッジとして
    存在すること（expert_decision_extractorを経由せずUser AIへ直行するバイパス）。"""
    compiled = cela_main.build_graph()
    graph_repr = compiled.get_graph()
    edge_pairs = {(e.source, e.target) for e in graph_repr.edges}
    assert ("expert_detector", "generate_user_utterance") in edge_pairs


def test_route_after_expert_detector_source_checks_consultation_mode_first():
    src = inspect.getsource(cela_main.build_graph)
    idx = src.find("def route_after_expert_detector")
    assert idx != -1
    snippet = src[idx: idx + 800]
    assert "expert_consultation_mode" in snippet
    assert '"generate_user_utterance"' in snippet
