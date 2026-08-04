"""
BL-144: reflection_nodeのBL-096機械的stagnant上書きが「issue_logにescalated行が1件でも
存在すれば無条件」だったため、reflection自身のLLM判定が"continuing"（健全な進捗中）だった
回まで無条件でstagnant上書きされ、facilitation_countの貴重な猶予（既定3回）を消費して
しまう実害が実ドライラン（log/2026-08-02/0832）で確認された。BL-136導入後もwrite_issueの
RESOLVE/DEFERがほぼ呼ばれない現状では、escalated行の「存在」だけを見ると常に発火するため、
「同じescalated issueがユーザーノード（round_count）を3回通過しても未解決のまま」という
滞留を条件に絞る。

参照: docs/design/back_log/issue_backlog.md BL-144。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl144.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        conn.close()


def _create_escalated_issue(conn, run_id, topic="bl144_topic"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "重大な懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )


def _base_state(run_id, round_count):
    return {
        "risk_register": [], "goal": "g", "run_id": run_id, "round_count": round_count,
        "escalated_issue_first_seen_round": {},
    }


def test_no_override_on_first_sighting_even_if_escalated(db_conn, monkeypatch):
    """escalated issueを初めて観測したround（滞留0）では、reflection自身の"continuing"判定を
    上書きしない（従来は無条件でstagnant化していた）。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に是正が進んでいる。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = _base_state(run_id, round_count=3)
    result = cela_main.reflection_node(state)

    assert result["discussion_status"] == "continuing"


def test_override_after_issue_persists_three_rounds(db_conn, monkeypatch):
    """同じescalated issueが3ラウンド（round_count差3）以上未解決のまま残ると、
    reflection自身の"continuing"判定であっても機械的にstagnantへ上書きする。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に見える。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = _base_state(run_id, round_count=3)
    state = cela_main.reflection_node(state)  # 初回観測（round=3）
    assert state["discussion_status"] == "continuing"

    state["round_count"] = 6  # 3ラウンド経過、まだ同じissueがescalatedのまま
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"


def test_tracking_cleared_when_issue_resolved(db_conn, monkeypatch):
    """issueが解決されescalated一覧から消えると、滞留追跡からも削除される
    （再度escalatedになった場合は新規の滞留として扱われる）。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl144_resolve_me")
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = _base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    assert len(state["escalated_issue_first_seen_round"]) == 1

    cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl144_resolve_me", "resolution_note": "対応済み"},
        conn, run_id, "user", "", "task_1_1",
    )
    state["round_count"] = 2
    state = cela_main.reflection_node(state)

    assert state["escalated_issue_first_seen_round"] == {}
    assert state["discussion_status"] == "continuing"


def test_multiple_escalated_issues_only_one_stale_still_triggers(db_conn, monkeypatch):
    """複数のescalated issueのうち1件でも3ラウンド以上滞留していれば上書きする。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl144_old")
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = _base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)  # bl144_oldをround=1で初観測

    _create_escalated_issue(conn, run_id, topic="bl144_new")
    state["round_count"] = 4  # bl144_oldは3ラウンド滞留、bl144_newは初観測
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"
