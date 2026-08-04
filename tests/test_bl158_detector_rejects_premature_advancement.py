"""
BL-158: Detectorの User レビューパスに、未解決・未先送りのescalated issueを残したままの
前進を機械的に却下する仕組みを追加する。

`generate_user_utterance`は既にBL-136の強制文言（`_get_forced_escalated_issues_text`）で
「今回の発言でwrite_issue(RESOLVE/DEFER)を必ず呼べ」とUser AIへソフトに指示しているが、
実ドライラン`log/2026-08-03/2233`でUser AIがこれを無視して直接「次タスクへ進め」と発言し、
`call_detector`（target_role="user"）も`constraint_issue="none"`のまま通してしまう実例が
確認された。ユーザーの原則「根本的にはユーザーがタスクを次に進めてはいけませんし、
detectorが弾くべきです」を受け、BL-125の実ゲートと完全に同一の
`_get_blocking_issues_for_transition`を単一の判断源として再利用し、LLMの指示追従に頼らない
決定論的なPython側の却下を`detector_node`に追加した。

参照: docs/design/back_log/issue_backlog.md BL-158、docs/design/decision_log.md D-128。
実LLM API呼び出しは伴わない（call_detectorはmonkeypatchで固定応答に差し替える）。
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
    db_path = str(tmp_path / "test_bl158.db")
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


def _base_state(run_id: str, chat_role: str = "user", user_wrote_issue_resolution: bool = False) -> dict:
    return {
        "chat_history": [{"role": chat_role, "content": "次のタスクへ進め"}],
        "expert_consultation_mode": False,
        "expert_last_python_calls": [{"code": "1+1", "result": "2"}],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
        "current_task_id": "task_1_1",
        "user_wrote_issue_resolution": user_wrote_issue_resolution,
    }


def _fake_call_detector_none(state, target_role, review_mode="task_output"):
    return {"risk": "low", "constraint_issue": "none", "comment": "元の判定コメント", "observations": ""}


def _seed_blocking_issue(conn, run_id, task_id="task_1_1"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl158_blocking_topic", "description": "1回目", "severity": "major"},
        conn, run_id, "detector", "phase_1", task_id,
    )
    # 2回目のCREATEでlast_seen_task_idを更新しつつescalated状態を維持する
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl158_blocking_topic", "description": "2回目"},
        conn, run_id, "detector", "phase_1", task_id,
    )


def test_detector_node_forces_major_when_blocking_issue_unresolved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "major"


def test_detector_node_does_not_override_expert_target_role(db_conn, monkeypatch):
    """target_role=="assistant"（Expert側）には影響しないこと。"""
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="assistant", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "none"


def test_detector_node_no_override_when_no_blocking_issues_exist(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "none"


def test_detector_node_no_override_when_user_wrote_issue_resolution_true(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=True)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "none"


def test_defer_success_naturally_clears_blocking_issues(db_conn, monkeypatch):
    """write_issue(DEFER)を実際に呼んだ結果、_get_blocking_issues_for_transitionが自然に
    空になるケース。user_wrote_issue_resolutionが未設定(False)のままでも、二重ガードには
    ならず正しく通過することを確認する。"""
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id)
    _phases_state = {"phases": [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
    ]}
    defer_result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl158_blocking_topic", "defer_to_task_id": "task_1_2", "defer_reason": "後続タスクで扱う"},
        conn, run_id, "user", "phase_1", "task_1_1", state=_phases_state,
    )
    assert defer_result["success"] is True
    assert cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1") == []

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)
    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "none"


def test_detector_node_preserves_original_comment_when_forcing_major(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    logged_comment = result["constraint_issue_log"][-1]["comment"]
    assert "元の判定コメント" in logged_comment
    assert "BL-158" in logged_comment


def test_detector_auto_raised_issue_never_triggers_bl158_override(db_conn, monkeypatch):
    """BL-157適用後のdetector_auto起票issueは、occurrence_countが積み上がっても
    BL-158のブロック対象に含まれないこと（両バグの相互作用の確認）。"""
    conn, run_id = db_conn
    for i in range(3):
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "detector_observation_task_1_1", "description": f"懸念{i}"},
            conn, run_id, "detector_auto", "phase_1", "task_1_1",
        )
    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector_none)

    state = _base_state(run_id, chat_role="user", user_wrote_issue_resolution=False)
    result = cela_main.detector_node(state)

    assert result["constraint_issue"] == "none"
