"""
BL-217: 実地調査が必要な暫定値を、Expertが正直にフラグし、人間が専用CLIで回答する仕組み
（Human-in-the-Loop）。

`log/2026-08-12/1046` の`task_1_1`で、`license_return_annual`（免許自主返納者数）が
「市独自統計未公表。task_1_3でヒアリング実施」という理由で暫定値のまま記録されていた。
これはCELAの既存DEFER機構（`write_issue(action_type="DEFER")`）の誤用である——DEFERは
「別のAIタスクが後で解決できる」ことを前提とした仕組みだが、実地ヒアリングは後続タスクも
同じAIが実行する以上、原理的に実行不可能で、AIは「後で解決される」という体裁だけを
整えた偽の解決計画を作っていた。

本設計は、①Expert専用の新ツール`flag_needs_human_input`（`defer_to_task_id`相当の
パラメータを持たず、DEFERとは構造的に排他）で正直に「人間にしか解決できない」と宣言する
経路、②専用CLI（`--pending-human-input`/`--answer-human-input`）で人間が`verified_facts`へ
直接確定値を書き込む経路、③人間の回答を各ノードへ知らせる毎ターンの一度きりの通知、の
3点を実装する。

本設計の核心は、既存のBL-125遷移ゲート（`_get_blocking_issues_for_transition`）が
無改修のまま正しく機能する点にある——新ツールで起票したissueは`defer_to_task_id`が
常に空のため、`severity='major'`なら既存SQLが自然にタスク遷移をブロックし、人間が
`--answer-human-input`で解決すれば同じSQLから自然に外れる。

参照: docs/design/back_log/issue_backlog.md BL-217。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
]


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl217.db")
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
        cela_main._CURRENT_CALLER_ROLE = ""


def _flag_args(**overrides):
    args = {
        "topic": "license_return_annual",
        "variable_name": "license_return_annual",
        "human_research_prompt": "茅野署または市高齢福祉課へ、直近1年の免許自主返納者数を確認してください。",
        "description": "市独自統計は未公表で、web_searchでも一次資料が見つからなかった。",
    }
    args.update(overrides)
    return args


# --- スキーマ移行の冪等性 -----------------------------------------------------

def test_ensure_issue_log_human_input_columns_is_idempotent(db_conn):
    conn, _run_id = db_conn
    cela_main._ensure_issue_log_human_input_columns(conn)
    cela_main._ensure_issue_log_human_input_columns(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    assert {"human_research_prompt", "human_notice_delivered_at", "human_variable_name"} <= cols


# --- flag_needs_human_input ---------------------------------------------------

def test_flag_needs_human_input_allowed_only_for_expert(db_conn):
    conn, run_id = db_conn
    for role in ("user", "detector", "detector_auto", "decision_extractor_auto"):
        result = cela_main._flag_needs_human_input_tool_impl(
            _flag_args(), conn, run_id, role, "phase_1", "task_1_1")
        assert result["success"] is False, f"role={role}は拒否されるべき"


def test_flag_needs_human_input_rejects_missing_required_fields(db_conn):
    conn, run_id = db_conn
    for missing in ("topic", "variable_name", "human_research_prompt", "description"):
        args = _flag_args()
        args.pop(missing)
        result = cela_main._flag_needs_human_input_tool_impl(
            args, conn, run_id, "expert", "phase_1", "task_1_1")
        assert result["success"] is False, f"{missing}欠落は拒否されるべき"


def test_flag_needs_human_input_major_severity_escalates(db_conn):
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        _flag_args(severity="major"), conn, run_id, "expert", "phase_1", "task_1_1")
    assert result["success"] is True
    row = conn.execute("SELECT status, defer_to_task_id FROM issue_log WHERE run_id=? AND topic=?",
                        (run_id, "license_return_annual")).fetchone()
    assert row["status"] == "escalated"
    assert row["defer_to_task_id"] == ""


def test_flag_needs_human_input_defaults_to_major(db_conn):
    """[CONSTRAINT] severityを省略した場合の既定値がmajorであること（設計通り）。"""
    conn, run_id = db_conn
    args = _flag_args()
    assert "severity" not in args
    result = cela_main._flag_needs_human_input_tool_impl(args, conn, run_id, "expert", "phase_1", "task_1_1")
    assert result["success"] is True
    row = conn.execute("SELECT severity, status FROM issue_log WHERE run_id=? AND topic=?",
                        (run_id, "license_return_annual")).fetchone()
    assert row["severity"] == "major"
    assert row["status"] == "escalated"


def test_flag_needs_human_input_minor_severity_does_not_escalate(db_conn):
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        _flag_args(severity="minor"), conn, run_id, "expert", "phase_1", "task_1_1")
    assert result["success"] is True
    row = conn.execute("SELECT status FROM issue_log WHERE run_id=? AND topic=?",
                        (run_id, "license_return_annual")).fetchone()
    assert row["status"] == "open"


def test_flag_needs_human_input_rejects_duplicate_topic(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")
    result = cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")
    assert result["success"] is False


# --- _flag_needs_human_input_report ------------------------------------------

def test_report_returns_only_open_prompted_issues(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")
    # 通常のwrite_issue（human_research_promptを持たない）は対象外
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "ordinary_issue", "severity": "minor", "description": "d"},
        {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]},
    )
    report = cela_main._flag_needs_human_input_report(conn, run_id)
    assert [r["topic"] for r in report] == ["license_return_annual"]


def test_report_excludes_resolved_issues(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")
    cela_main._answer_human_input(conn, run_id, "license_return_annual", "128", "人",
                                   "茅野警察署への電話確認", "回答あり。")
    report = cela_main._flag_needs_human_input_report(conn, run_id)
    assert report == []


# --- _answer_human_input ------------------------------------------------------

def test_answer_human_input_writes_confirmed_verified_fact_and_resolves_issue(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")

    result = cela_main._answer_human_input(
        conn, run_id, "license_return_annual", "128", "人",
        "茅野警察署への電話確認(2026-08-12)", "窓口担当者から回答あり。",
    )
    assert result["success"] is True
    assert result["variable_name"] == "license_return_annual"

    facts = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["license_return_annual"])
    assert len(facts) == 1
    assert facts[0]["value"] == "128"
    assert facts[0]["confidence"] == "confirmed"
    assert facts[0]["confirmed_by"] == "human_operator"
    citations = facts[0]["citations"]
    assert "human_field_research" in citations
    assert "茅野警察署" in citations

    issue_row = conn.execute("SELECT status, resolved_by, resolution_note FROM issue_log WHERE run_id=? AND topic=?",
                              (run_id, "license_return_annual")).fetchone()
    assert issue_row["status"] == "resolved"
    assert issue_row["resolved_by"] == "human_operator"
    assert issue_row["resolution_note"] == "窓口担当者から回答あり。"


def test_answer_human_input_rejects_unknown_topic(db_conn):
    conn, run_id = db_conn
    result = cela_main._answer_human_input(conn, run_id, "nonexistent_topic", "1", "", "", "")
    assert result["success"] is False


def test_answer_human_input_rejects_double_answer(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")
    first = cela_main._answer_human_input(conn, run_id, "license_return_annual", "128", "人", "s1", "c1")
    assert first["success"] is True
    second = cela_main._answer_human_input(conn, run_id, "license_return_annual", "999", "人", "s2", "c2")
    assert second["success"] is False
    # 元の回答が上書きされていないことも確認する。
    facts = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["license_return_annual"])
    assert facts[0]["value"] == "128"


# --- BL-125連携（本設計の核） --------------------------------------------------

def test_major_flagged_issue_blocks_task_transition_until_answered(db_conn):
    """[本設計の核] 新ツールで起票したissueはdefer_to_task_idが常に空のため、既存のBL-125
    ゲート（_get_blocking_issues_for_transition）が新しいゲートロジックなしに正しく機能する。"""
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(
        _flag_args(severity="major"), conn, run_id, "expert", "phase_1", "task_1_1")

    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert [b["topic"] for b in blocking] == ["license_return_annual"]

    cela_main._answer_human_input(conn, run_id, "license_return_annual", "128", "人", "s", "c")

    blocking_after = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking_after == []


def test_minor_flagged_issue_does_not_block_task_transition(db_conn):
    """[非退行] minor severityは元々ゲート対象外（write_issueの既存挙動と同型）。"""
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(
        _flag_args(severity="minor"), conn, run_id, "expert", "phase_1", "task_1_1")
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert blocking == []


# --- _build_human_input_answered_notice ---------------------------------------

def test_notice_fires_once_after_answer_and_marks_delivered(db_conn):
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")

    assert cela_main._build_human_input_answered_notice(conn, run_id) == ""

    cela_main._answer_human_input(
        conn, run_id, "license_return_annual", "128", "人", "茅野警察署への電話確認",
        "窓口担当者から回答あり。年度によりばらつきがあるため次年度以降は再確認要。",
    )

    notice = cela_main._build_human_input_answered_notice(conn, run_id)
    assert "license_return_annual" in notice
    assert "窓口担当者から回答あり" in notice

    delivered_at = conn.execute(
        "SELECT human_notice_delivered_at FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "license_return_annual")
    ).fetchone()["human_notice_delivered_at"]
    assert delivered_at is not None

    second_notice = cela_main._build_human_input_answered_notice(conn, run_id)
    assert second_notice == ""


def test_notice_does_not_fire_for_ai_resolved_issues(db_conn):
    """[非退行] 通常のwrite_issue(RESOLVE)（human_research_promptを持たない、resolved_byが
    human_operator以外）は、この通知の対象にならないこと。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "ordinary_issue", "severity": "minor", "description": "d"}, state)
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "RESOLVE", "topic": "ordinary_issue", "resolution_note": "対応済み"}, state)
    assert cela_main._build_human_input_answered_notice(conn, run_id) == ""


# --- ツール定義・配線の固定（AGENTS.md §17.1向けの配線テスト） -----------------

def test_flag_needs_human_input_has_no_defer_to_task_id_parameter():
    """[CONSTRAINT] defer_to_task_id相当のパラメータを持たない——「AIタスクへの先送り」と
    「人間への先送り」が同一issue上で混在する余地を、バリデーションではなく構造で無くす。"""
    props = cela_main.FLAG_NEEDS_HUMAN_INPUT_TOOL["function"]["parameters"]["properties"]
    assert "defer_to_task_id" not in props


def test_flag_needs_human_input_is_wired_into_tool_dispatch():
    assert "flag_needs_human_input" in cela_main.TOOL_DISPATCH


def test_flag_needs_human_input_tool_is_attached_to_expert():
    import inspect
    src = inspect.getsource(cela_main.call_expert)
    assert "FLAG_NEEDS_HUMAN_INPUT_TOOL" in src


def test_citations_enum_includes_human_field_research():
    props = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]
    citation_type_enum = props["citations"]["items"]["properties"]["type"]["enum"]
    assert "human_field_research" in citation_type_enum
    assert "user_input" in citation_type_enum  # 既存値との共存を確認（置き換えではなく追加）
