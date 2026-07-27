"""
BL-096: 監査系ノードの軽微な指摘（observations/minor）を追跡するissue管理DBの新設。

Detectorの`observations`（軽微な気づき、BL-051）が状態リストの直近3件しかプロンプトに
戻らず古いものが実質消滅する問題、および`constraint_issue="minor"`が記録されるだけで
再監査・再浮上の保証がない問題（BL-051/BL-096）に対応する、新設`issue_log`テーブルと
`write_issue`/`read_issues`ツールの実装を検証する。

設計はv3（`docs/design/back_log/BL-096/BL096_basic_design.md`）に基づく：
- 重複検知キーは`topic`単独（task_id/phase_idはメタデータのみ）。
- 再発カウントはCREATE経由（無条件）とREAD経由（topic_keyword+task_id明示、
  last_seen_task_idと異なる場合のみ）の二重トリガー。occurrence_count>=2で
  severity='major'・status='escalated'へ機械的に昇格する不変条件。
- reflection/facilitatorへの機械的接続、エスカレーション解除の復帰通知。

参照: docs/design/back_log/issue_backlog.md BL-096、
docs/design/decision_log.md D-078/D-079/D-080。
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
    db_path = str(tmp_path / "test_bl096_issue_log.db")
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


# --- _check_issue_permission の直接検証 ---

def test_detector_can_create():
    assert cela_main._check_issue_permission({"action_type": "CREATE"}, "detector") is None


def test_detector_cannot_resolve():
    error = cela_main._check_issue_permission({"action_type": "RESOLVE"}, "detector")
    assert error is not None
    assert "detector" in error


def test_user_can_create_and_resolve():
    assert cela_main._check_issue_permission({"action_type": "CREATE"}, "user") is None
    assert cela_main._check_issue_permission({"action_type": "RESOLVE"}, "user") is None


def test_detector_auto_can_only_create():
    assert cela_main._check_issue_permission({"action_type": "CREATE"}, "detector_auto") is None
    error = cela_main._check_issue_permission({"action_type": "RESOLVE"}, "detector_auto")
    assert error is not None


def test_unknown_role_denied():
    error = cela_main._check_issue_permission({"action_type": "CREATE"}, "expert")
    assert error is not None
    assert "expert" in error


# --- _write_issue_impl: CREATE (新規・再発) ---

def test_create_new_issue(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_a", "description": "最初の懸念"},
        conn, run_id, "detector", "phase_1", "task_1_1",
    )
    assert result["success"] is True
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_topic_a")).fetchone()
    assert row is not None
    assert row["occurrence_count"] == 1
    assert row["status"] == "open"
    assert row["severity"] == "minor"
    assert row["task_id"] == "task_1_1"


def test_create_with_major_severity_sets_escalated_immediately(db_conn):
    """[別AIレビュー指摘B] 初回CREATE時にseverity='major'を明示指定した場合も、
    不変条件によりstatus='escalated'が同時に設定されなければならない。
    """
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_major", "description": "重大な懸念",
         "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_topic_major")).fetchone()
    assert row["severity"] == "major"
    assert row["status"] == "escalated"


def test_recreate_same_topic_increments_occurrence_and_escalates(db_conn):
    """CREATE経由の再発カウントは無条件（task_idの異同を問わない）。2回目でescalated。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_b", "description": "1回目"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_b", "description": "2回目"},
        conn, run_id, "detector", "", "task_1_1",
    )
    assert result["success"] is True
    assert result["occurrence_count"] == 2
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_topic_b")).fetchone()
    assert row["occurrence_count"] == 2
    assert row["severity"] == "major"
    assert row["status"] == "escalated"
    assert "1回目" in row["description"]
    assert "2回目" in row["description"]


def test_recreate_key_is_topic_only_not_task_id(db_conn):
    """[D-080] 重複検知キーはtopic単独。別task_idからの再CREATEでも同一issueとして再発扱いされる
    （タスク横断の再発検知というBL-096の目的自体のため、v2の(topic,task_id)キー案は撤回した）。
    """
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_cross_task", "description": "task_1での懸念"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_cross_task", "description": "task_3での再発"},
        conn, run_id, "detector", "", "task_3_1",
    )
    assert result["occurrence_count"] == 2
    rows = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_cross_task")).fetchall()
    assert len(rows) == 1  # 別行にならず1行に統合される


def test_create_missing_description_fails(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_c"}, conn, run_id, "detector", "", "",
    )
    assert result["success"] is False


def test_create_missing_topic_fails(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "description": "説明のみ"}, conn, run_id, "detector", "", "",
    )
    assert result["success"] is False


def test_create_permission_denied_for_wrong_role(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_topic_d", "description": "説明"},
        conn, run_id, "expert", "", "",
    )
    assert result["success"] is False


def test_description_truncation_beyond_2000_chars(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_long", "description": "x" * 1900},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_long", "description": "y" * 500},
        conn, run_id, "detector", "", "task_2",
    )
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_long")).fetchone()
    assert len(row["description"]) <= cela_main._ISSUE_DESCRIPTION_MAX_LEN
    assert "truncated" in row["description"]
    assert "y" * 500 in row["description"]  # 直近の内容は残る


# --- _write_issue_impl: RESOLVE ---

def test_resolve_success(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_resolve_a", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_resolve_a", "resolution_note": "対応済み"},
        conn, run_id, "user", "", "",
    )
    assert result["success"] is True
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_resolve_a")).fetchone()
    assert row["status"] == "resolved"
    assert row["resolved_by"] == "user"
    assert row["resolution_note"] == "対応済み"


def test_resolve_missing_note_fails(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_resolve_b", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_resolve_b"}, conn, run_id, "user", "", "",
    )
    assert result["success"] is False


def test_resolve_nonexistent_topic_fails(db_conn):
    conn, run_id = db_conn
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_no_such_topic", "resolution_note": "対応済み"},
        conn, run_id, "user", "", "",
    )
    assert result["success"] is False


def test_resolve_denied_for_detector(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_resolve_c", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_resolve_c", "resolution_note": "対応済み"},
        conn, run_id, "detector", "", "",
    )
    assert result["success"] is False


def test_resolve_reports_escalation_cleared_true_when_last_one(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_esc_a", "description": "1", "severity": "major"},
        conn, run_id, "detector", "", "task_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_esc_a", "resolution_note": "解決"},
        conn, run_id, "user", "", "",
    )
    assert result["escalation_cleared"] is True


def test_resolve_reports_escalation_cleared_false_when_others_remain(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_esc_b1", "description": "1", "severity": "major"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_esc_b2", "description": "1", "severity": "major"},
        conn, run_id, "detector", "", "task_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_esc_b1", "resolution_note": "解決"},
        conn, run_id, "user", "", "",
    )
    assert result["escalation_cleared"] is False


# --- get_issues_from_db / _read_issues_handler ---

def test_get_issues_from_db_includes_resolved_by_default(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_read_a", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_read_a", "resolution_note": "解決済み"},
        conn, run_id, "user", "", "",
    )
    results = cela_main.get_issues_from_db(conn, run_id, topic_keyword="bl096_read_a")
    assert len(results) == 1
    assert results[0]["status"] == "resolved"
    assert results[0]["resolution_note"] == "解決済み"


def test_get_issues_from_db_description_like_search(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_desc_search", "description": "特殊なキーワードXYZ123を含む"},
        conn, run_id, "detector", "", "task_1",
    )
    results = cela_main.get_issues_from_db(conn, run_id, topic_keyword="XYZ123")
    assert len(results) == 1


def test_get_issues_from_db_list_all_ignores_filters(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_list_all_1", "description": "a"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_list_all_2", "description": "b"},
        conn, run_id, "detector", "", "task_2",
    )
    results = cela_main.get_issues_from_db(conn, run_id, list_all=True, topic_keyword="not_matching_anything")
    topics = {r["topic"] for r in results}
    assert "bl096_list_all_1" in topics
    assert "bl096_list_all_2" in topics


def test_read_issues_handler_requires_a_filter_or_list_all(db_conn):
    result = cela_main._read_issues_handler({})
    assert result["status"] == "error"


def test_read_issues_handler_not_found(db_conn):
    result = cela_main._read_issues_handler({"topic_keyword": "nonexistent_topic_xyz"})
    assert result["status"] == "not_found"


# --- READ経由の再発カウント（4条件） ---

def test_read_issues_bumps_occurrence_when_topic_and_task_id_given_and_different(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_readbump_a", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    results = cela_main._read_issues_handler({"topic_keyword": "bl096_readbump_a", "task_id": "task_2"})
    assert isinstance(results, list)
    assert results[0]["occurrence_count"] == 2
    assert results[0]["status"] == "escalated"
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_readbump_a")).fetchone()
    assert row["occurrence_count"] == 2
    assert row["last_seen_task_id"] == "task_2"


def test_read_issues_does_not_bump_when_same_task_id(db_conn):
    """同一task_id内での繰り返しread_issuesは再発とみなさない（二重計上防止）。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_readbump_b", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._read_issues_handler({"topic_keyword": "bl096_readbump_b", "task_id": "task_1"})
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_readbump_b")).fetchone()
    assert row["occurrence_count"] == 1


def test_read_issues_does_not_bump_when_task_id_only(db_conn):
    """topic_keywordなし・task_idのみの検索は再発カウント対象外（誤爆防止）。"""
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_readbump_c", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._read_issues_handler({"task_id": "task_2"})
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_readbump_c")).fetchone()
    assert row["occurrence_count"] == 1


def test_read_issues_does_not_bump_when_list_all(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_readbump_d", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._read_issues_handler({"list_all": True, "topic_keyword": "bl096_readbump_d", "task_id": "task_2"})
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_readbump_d")).fetchone()
    assert row["occurrence_count"] == 1


def test_read_issues_does_not_bump_resolved_row(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_readbump_e", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_readbump_e", "resolution_note": "解決"},
        conn, run_id, "user", "", "",
    )
    cela_main._read_issues_handler({"topic_keyword": "bl096_readbump_e", "task_id": "task_2"})
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl096_readbump_e")).fetchone()
    assert row["occurrence_count"] == 1
    assert row["status"] == "resolved"


# --- _get_escalated_issues ---

def test_get_escalated_issues_returns_only_escalated(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_esc_open", "description": "open"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_esc_escalated", "description": "escalated", "severity": "major"},
        conn, run_id, "detector", "", "task_1",
    )
    results = cela_main._get_escalated_issues(conn, run_id)
    topics = {r["topic"] for r in results}
    assert "bl096_esc_escalated" in topics
    assert "bl096_esc_open" not in topics


# --- TOOL_DISPATCH配線 ---

def test_tool_dispatch_has_write_issue_and_read_issues():
    assert "write_issue" in cela_main.TOOL_DISPATCH
    assert "read_issues" in cela_main.TOOL_DISPATCH


# --- ノードのtools=[...]配線・プロンプトオリエンテーション ---

def test_call_detector_passes_write_issue_and_read_issues_tools():
    src = inspect.getsource(cela_main.call_detector)
    assert "WRITE_ISSUE_TOOL" in src
    assert "READ_ISSUES_TOOL" in src
    assert "BL-096" in src


def test_generate_user_utterance_passes_write_issue_and_read_issues_tools():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "WRITE_ISSUE_TOOL" in src
    assert "READ_ISSUES_TOOL" in src
    assert "BL-096" in src


def test_detector_node_has_auto_backup_write():
    src = inspect.getsource(cela_main.detector_node)
    assert "detector_auto" in src
    assert "_write_issue_impl" in src


# --- reflection/facilitatorへの機械的接続 ---

def test_reflection_node_overrides_discussion_status_when_escalated():
    src = inspect.getsource(cela_main.reflection_node)
    assert "_get_escalated_issues" in src
    assert "escalation_active" in src
    assert '"stagnant"' in src


def test_call_reflection_merges_escalated_issues_into_prompt():
    src = inspect.getsource(cela_main.call_reflection)
    assert "_get_escalated_issues" in src


def test_facilitator_node_injects_escalated_issues_text():
    src = inspect.getsource(cela_main.facilitator_node)
    assert "_get_escalated_issues" in src
    assert "escalated_issues_text" in src


def test_call_facilitator_has_escalated_issues_param():
    sig = inspect.signature(cela_main.call_facilitator)
    assert "escalated_issues_text" in sig.parameters


# --- エスカレーション解除の復帰通知 ---

def test_build_escalation_resume_notice_returns_empty_when_not_pending():
    state = {"escalation_just_resolved_notice_pending": False}
    assert cela_main._build_escalation_resume_notice(state) == ""


def test_build_escalation_resume_notice_returns_text_and_resets_flag(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl096_notice_topic", "description": "懸念"},
        conn, run_id, "detector", "", "task_1",
    )
    cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl096_notice_topic", "resolution_note": "解決"},
        conn, run_id, "user", "", "",
    )
    state = {
        "escalation_just_resolved_notice_pending": True,
        "current_task_id": "task_2",
        "run_id": run_id,
    }
    notice = cela_main._build_escalation_resume_notice(state)
    assert "BL-096" in notice
    assert "bl096_notice_topic" in notice
    assert state["escalation_just_resolved_notice_pending"] is False


def test_call_expert_and_generate_user_utterance_inject_resume_notice():
    assert "_build_escalation_resume_notice" in inspect.getsource(cela_main.call_expert)
    assert "_build_escalation_resume_notice" in inspect.getsource(cela_main.generate_user_utterance)


# --- LineageStateフィールド ---

def test_lineage_state_has_escalation_fields():
    annotations = cela_main.LineageState.__annotations__
    assert "escalation_active" in annotations
    assert "escalation_just_resolved_notice_pending" in annotations
