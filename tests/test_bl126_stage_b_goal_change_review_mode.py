"""
BL-126 Stage B: Detectorの「目標変更レビュー」モード（review_mode="goal_change"）。

revise_goalによるゴール文改定は、通常の成果物レビューとは判断基準が異なる
（旧文が置換でなく追記として保持されているか／理由づけが懸念の重大さに見合っているか／
変更が懸念の範囲内に収まっているか／新しい目標文の数値的最適性そのものは評価しない）。
既存の反応的revise_goal経路（BL-086）にも先行して適用し、BL-126のEssence Dialogue
（Stage D、未実装）着手前に動作確認しておく（design.md §5・§8実装順序）。

参照: docs/design/back_log/issue_backlog.md BL-126、
      docs/design/back_log/BL-126/BL126_basic_design.md §5・§13.2。
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
    db_path = str(tmp_path / "test_bl126_stage_b.db")
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


# --- call_detectorのreview_mode分岐（ソース確認） -------------------------------

def test_call_detector_has_review_mode_parameter_defaulting_to_task_output():
    sig = inspect.signature(cela_main.call_detector)
    assert "review_mode" in sig.parameters
    assert sig.parameters["review_mode"].default == "task_output"


def test_call_detector_source_branches_on_goal_change_review_mode():
    src = inspect.getsource(cela_main.call_detector)
    assert 'review_mode == "goal_change"' in src
    # §5の4判断基準がgoal_changeブロックに含まれていること
    assert "追記" in src
    assert "スコープ逸脱" in src
    assert "数値的な最適性" in src


# --- generate_user_utterance_nodeでのフラグ設定 ----------------------------------

def test_generate_user_utterance_node_sets_pending_review_after_goal_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "承認します")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(
        cela_main, "get_last_goal_revision",
        lambda: {"new_goal_text": "改定後のゴール", "old_goal_text": "旧ゴール", "escalation_id": "ESC-1"},
    )

    state = {
        "round_count": 0,
        "constraint_issue": "none",
        "user_retry_count": 0,
        "chat_history": [],
        "turn_count": 1,
        "run_id": run_id,
        "goal": "旧ゴール",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result["goal"] == "改定後のゴール"
    assert result["goal_revision_pending_review"] is True


def test_generate_user_utterance_node_does_not_set_pending_review_without_goal_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "通常の指示です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)

    state = {
        "round_count": 0,
        "constraint_issue": "none",
        "user_retry_count": 0,
        "chat_history": [],
        "turn_count": 1,
        "run_id": run_id,
        "goal": "変わらないゴール",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result.get("goal_revision_pending_review", False) is False


# --- detector_nodeでのreview_mode選択・フラグ消費 --------------------------------

def test_detector_node_uses_goal_change_review_mode_and_consumes_flag(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured = {}

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        captured["review_mode"] = review_mode
        return {"risk": "low", "constraint_issue": "none", "comment": "OK"}

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = {
        "chat_history": [{"role": "user", "content": "revise_goalしました"}],
        "goal_revision_pending_review": True,
        "expert_last_python_calls": [],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
    }
    result = cela_main.detector_node(state)

    assert captured["review_mode"] == "goal_change"
    # 単発フラグのため、消費後は必ずリセットされること（次ターン以降へ引き継がない）
    assert result["goal_revision_pending_review"] is False


def test_detector_node_uses_task_output_review_mode_when_flag_not_set(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured = {}

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        captured["review_mode"] = review_mode
        return {"risk": "low", "constraint_issue": "none", "comment": "OK"}

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = {
        "chat_history": [{"role": "user", "content": "通常の指示です"}],
        "expert_last_python_calls": [],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
    }
    cela_main.detector_node(state)

    assert captured["review_mode"] == "task_output"
