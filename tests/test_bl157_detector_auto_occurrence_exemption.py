"""
BL-157: BL-096の自動バックアップ（raised_by='detector_auto'）は、current_task_idキーの
陳腐化により無関係な指摘を同一バケツへ混入させ、occurrence_count>=2による機械的な
major/escalated昇格（D-079/D-080）が見せかけの再発で発火してしまう問題への対応を検証する。

実ドライラン`log/2026-08-03/2233`で確認された実例：generate_user_utterance→user_detector→
user_decision_extractorというグラフ順序上、detector_nodeのBL-096バックアップは
_resolve_task_transitionより先に実行されるため、current_task_idはまだ遷移前の値のまま
（例："task_1_1"）。User AIが次タスク（task_1_2）について発言しても、detector_nodeの
observationsは`detector_observation_task_1_1`という同一バケツへ書き込まれ、無関係な指摘が
occurrence_countを押し上げ、D-127の例外導入前は機械的にmajor/escalated化していた。

本テストは、raised_by='detector_auto'の行に限りこの機械的昇格を抑制すること（D-127）、
他ロール（detector/user）の既存挙動（D-079/D-080）が無変更であることを検証する。

参照: docs/design/back_log/issue_backlog.md BL-157、docs/design/decision_log.md D-127。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl157.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        conn.close()


def _get_row(conn, run_id, topic):
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, topic)).fetchone()
    return dict(row) if row else None


def test_detector_auto_occurrence_does_not_escalate_via_create(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "detector_observation_task_1_1", "description": "task_1_1についての懸念"},
        conn, run_id, "detector_auto", "phase_1", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "detector_observation_task_1_1", "description": "task_1_2について混入した無関係な懸念"},
        conn, run_id, "detector_auto", "phase_1", "task_1_1",
    )
    assert result["success"] is True
    assert result["occurrence_count"] == 2
    row = _get_row(conn, run_id, "detector_observation_task_1_1")
    assert row["occurrence_count"] == 2
    assert row["severity"] == "minor"
    assert row["status"] == "open"


def test_detector_auto_occurrence_does_not_escalate_via_read_issues(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "detector_observation_no_task", "description": "懸念"},
        conn, run_id, "detector_auto", "", "task_1",
    )
    results = cela_main._read_issues_handler({"topic_keyword": "detector_observation_no_task", "task_id": "task_2"})
    assert isinstance(results, list)
    assert results[0]["occurrence_count"] == 2
    assert results[0]["severity"] == "minor"
    assert results[0]["status"] == "open"
    row = _get_row(conn, run_id, "detector_observation_no_task")
    assert row["severity"] == "minor"
    assert row["status"] == "open"


def test_other_roles_still_escalate_via_create_regression(db_conn):
    """D-079/D-080の既存挙動（detector/userロール）は無変更であることの回帰確認。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl157_regression_detector", "description": "1回目"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl157_regression_detector", "description": "2回目"},
        conn, run_id, "detector", "", "task_1_1",
    )
    assert result["occurrence_count"] == 2
    row = _get_row(conn, run_id, "bl157_regression_detector")
    assert row["severity"] == "major"
    assert row["status"] == "escalated"


def test_other_roles_still_escalate_via_read_issues_regression(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl157_regression_read", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    results = cela_main._read_issues_handler({"topic_keyword": "bl157_regression_read", "task_id": "task_2"})
    assert results[0]["severity"] == "major"
    assert results[0]["status"] == "escalated"
    row = _get_row(conn, run_id, "bl157_regression_read")
    assert row["severity"] == "major"
    assert row["status"] == "escalated"


def test_detector_auto_does_not_block_transition_even_after_many_occurrences(db_conn):
    """BL-157適用後、detector_auto起票issueがBL-125/BL-158のブロック対象に含まれないこと
    （相互作用の確認）。"""
    conn, run_id = db_conn
    for i in range(5):
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "detector_observation_task_1_1", "description": f"懸念{i}"},
            conn, run_id, "detector_auto", "phase_1", "task_1_1",
        )
    row = _get_row(conn, run_id, "detector_observation_task_1_1")
    assert row["occurrence_count"] == 5
    assert row["status"] == "open"  # escalatedにならない
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []
