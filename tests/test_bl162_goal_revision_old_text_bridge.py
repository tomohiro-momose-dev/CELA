"""
BL-162: `revise_goal`成功時、`generate_user_utterance_node`は`_LAST_GOAL_REVISION`ブリッジから
`new_goal_text`のみを`state["goal"]`へ反映し、`old_goal_text`はどこにも保存せずその場で
捨てていた。一方、次に走るDetectorの`review_mode="goal_change"`監査（BL-126 Stage B）の
判定基準1は「旧文が置換ではなく追記として保持されているか」であり、実際の旧ゴール文が
必要だが、Detectorが持つツール（read_verified_fact/read_deliverable_file/read_issues）は
いずれも「現在の」状態しか読めないため原理的に取得不可能だった（実ログ`log/2026-08-04/1123`で、
Detectorが計5回ツールを試して全てnot_foundになり「旧ゴール文が不明のため包含関係は
確認不可」と自ら申告する空振りを確認）。

`generate_user_utterance_node`が新規`state["goal_revision_old_text"]`へ`old_goal_text`も
橋渡しし、`call_detector`のgoal_change用domain_role_instructionへ直接埋め込むことで、
Detectorがツール呼び出しなしに旧文・新文を直接比較できるようにした。

参照: docs/design/back_log/issue_backlog.md BL-162。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl162.db")
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


def test_generate_user_utterance_node_bridges_old_goal_text_after_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "承認します")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(
        cela_main, "get_last_goal_revision",
        lambda: {"new_goal_text": "改定後のゴール", "old_goal_text": "改定前の旧ゴール文", "escalation_id": "ESC-1"},
    )

    state = {
        "round_count": 0, "constraint_issue": "none", "user_retry_count": 0,
        "chat_history": [], "turn_count": 1, "run_id": run_id, "goal": "改定前の旧ゴール文",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result["goal"] == "改定後のゴール"
    assert result["goal_revision_old_text"] == "改定前の旧ゴール文"
    assert result["goal_revision_pending_review"] is True


def test_generate_user_utterance_node_does_not_set_old_text_without_goal_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "通常の指示です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)

    state = {
        "round_count": 0, "constraint_issue": "none", "user_retry_count": 0,
        "chat_history": [], "turn_count": 1, "run_id": run_id, "goal": "変わらないゴール",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert "goal_revision_old_text" not in result


def test_generate_user_utterance_node_handles_missing_old_goal_text_gracefully(db_conn, monkeypatch):
    """old_goal_textがブリッジ側で欠落していても（None）、KeyErrorにならず空文字になること。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "承認します")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(
        cela_main, "get_last_goal_revision",
        lambda: {"new_goal_text": "改定後のゴール", "old_goal_text": None, "escalation_id": "ESC-1"},
    )

    state = {
        "round_count": 0, "constraint_issue": "none", "user_retry_count": 0,
        "chat_history": [], "turn_count": 1, "run_id": run_id, "goal": "旧ゴール",
    }
    result = cela_main.generate_user_utterance_node(state)

    assert result["goal_revision_old_text"] == ""


def test_call_detector_source_embeds_old_goal_text_in_goal_change_prompt():
    """call_detectorのgoal_change分岐が、state経由のold_goal_textをdomain_role_instructionへ
    直接埋め込んでいること（Detector自身がツールで探し回る必要がないこと）をソース確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    goal_change_idx = src.index('review_mode == "goal_change"')
    goal_change_block = src[goal_change_idx:goal_change_idx + 2000]
    assert 'state.get("goal_revision_old_text"' in goal_change_block
    assert "改定前のゴール文" in goal_change_block
    assert "旧文を探すためのツール呼び出しは不要です" in goal_change_block
