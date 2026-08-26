"""
BL-236拡張: write_issue(RESOLVE/DEFER)が、human_research_prompt付きissue（人間の回答
（--answer-human-input）でしか解決してはいけないHILゲート行）を、AIロールが自己解決・
自己先送りできてしまっていた欠陥の修正。

ユーザーが別チャットでの調査により、実ドライラン（log/2026-08-14/1825、log/2026-08-26/0031）
のDBを直接確認し発見した：BL-236のHILゲートissue（topic=goal_escalation_hil_ESC-...）が
issue_log上はstatus='resolved'（resolved_by='user'）になっていたが、これはUser AIが
write_issue(action_type="RESOLVE")で自己解決したものであり、--answer-human-input経由の
resolved_by='human_operator'ではなかった。実際にはgoal_escalationsテーブルの該当行は
今もstatus='Open'、verified_factsにも承認値は一度も書き込まれておらず、その後の
revise_goal呼び出しは3回とも「HIL未承認」で拒否され続けていた。にもかかわらず
--pending-human-inputは「実地調査待ちのissueはありません」と表示し、運用者はこの
エスカレーションが未決着であることに気づけなかった。

根本原因: `_write_issue_impl`のRESOLVE分岐は`resolution_note`の存在と`existing`
（`SELECT *`で取得済み、human_research_prompt列を含む）の存在しかチェックしておらず、
`existing["human_research_prompt"]`が非空（＝人間しか解決してはいけない行）かどうかを
一切見ていなかった。DEFER分岐も同型の欠落があった（AGENTS.md §13.5「クラスとして直す」）。

対応: モジュールレベル共有ヘルパー`_is_human_only_issue`を新設し、RESOLVE・DEFER両分岐で
human_research_prompt非空の行を拒否する。`_answer_human_input`（CLI経由、
--answer-human-input）は`_write_issue_impl`を一切経由しない独立実装のため無影響。

参照: docs/design/back_log/issue_backlog.md（本BL）、BL-217（human_research_prompt機構の
原設計）、BL-236（escalate_premise_concernのHILゲート）。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


PHASES_1_2 = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl236_human_only_issue_guard.db")
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


def _flag_args(**overrides):
    args = {
        "topic": "goal_escalation_hil_ESC-test",
        "variable_name": "goal_escalation_decision_ESC-test",
        "human_research_prompt": "このエスカレーションを承認するか判断し、--answer-human-inputで回答してください。",
        "description": "ゴール文の前提改定はAI自身に委ねられないため、人間の判断が必要。",
    }
    args.update(overrides)
    return args


def _create_ordinary_issue(conn, run_id, topic="ordinary_topic", task_id="task_1_1"):
    return cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "通常の懸念"},
        conn, run_id, "detector", "", task_id,
    )


# --- _is_human_only_issue（単体） ---------------------------------------------

def test_is_human_only_issue_true_when_prompt_present():
    assert cela_main._is_human_only_issue({"human_research_prompt": "確認してください"}) is True


def test_is_human_only_issue_false_when_prompt_empty():
    assert cela_main._is_human_only_issue({"human_research_prompt": ""}) is False


def test_is_human_only_issue_false_when_key_absent():
    assert cela_main._is_human_only_issue({}) is False


def test_is_human_only_issue_false_when_row_none():
    assert cela_main._is_human_only_issue(None) is False


# --- RESOLVE分岐のガード ------------------------------------------------------

def test_write_issue_resolve_rejects_human_only_issue(db_conn):
    """[本事故の直接回帰テスト] human_research_prompt付きissueはwrite_issue(RESOLVE)で
    解決できないこと。【リバート検出】ガード削除で成功してしまう。"""
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")

    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "goal_escalation_hil_ESC-test",
         "resolution_note": "発注者として承認しrevise_goalで改定した"},
        conn, run_id, "user", "", "task_1_1",
    )

    assert result["success"] is False
    assert "人間" in result["error"]

    row = conn.execute(
        "SELECT status, resolved_by FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "goal_escalation_hil_ESC-test"),
    ).fetchone()
    assert row["status"] != "resolved"
    assert row["resolved_by"] is None or row["resolved_by"] == ""


def test_write_issue_resolve_still_works_for_ordinary_issue(db_conn):
    """[対照] human_research_promptを持たない通常issueは従来通りRESOLVEできること
    （誤ブロックの回帰防止）。"""
    conn, run_id = db_conn
    _create_ordinary_issue(conn, run_id, "ordinary_resolve")

    result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "ordinary_resolve", "resolution_note": "対応済み"},
        conn, run_id, "user", "", "task_1_1",
    )

    assert result["success"] is True
    row = conn.execute(
        "SELECT status, resolved_by FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "ordinary_resolve"),
    ).fetchone()
    assert row["status"] == "resolved"
    assert row["resolved_by"] == "user"


# --- DEFER分岐のガード --------------------------------------------------------

def test_write_issue_defer_rejects_human_only_issue(db_conn):
    """[BL-236拡張・同型の穴] human_research_prompt付きissueはwrite_issue(DEFER)でも
    先送りできないこと。【リバート検出】ガード削除で成功してしまう。"""
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")

    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "goal_escalation_hil_ESC-test",
         "defer_to_task_id": "task_1_2", "defer_reason": "後続タスクで検討する"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": PHASES_1_2},
    )

    assert result["success"] is False
    assert "人間" in result["error"]

    row = conn.execute(
        "SELECT defer_to_task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "goal_escalation_hil_ESC-test"),
    ).fetchone()
    assert row["defer_to_task_id"] == ""


def test_write_issue_defer_still_works_for_ordinary_issue(db_conn):
    """[対照] human_research_promptを持たない通常issueは従来通りDEFERできること。"""
    conn, run_id = db_conn
    _create_ordinary_issue(conn, run_id, "ordinary_defer")

    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "ordinary_defer",
         "defer_to_task_id": "task_1_2", "defer_reason": "後続タスクで検討する"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": PHASES_1_2},
    )

    assert result["success"] is True
    row = conn.execute(
        "SELECT defer_to_task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "ordinary_defer"),
    ).fetchone()
    assert row["defer_to_task_id"] == "task_1_2"


# --- --answer-human-input（CLI経路）は無影響であること -------------------------

def test_answer_human_input_still_resolves_human_only_issue(db_conn):
    """[非退行] _answer_human_input（--answer-human-input経由）は_write_issue_implを
    経由しない独立実装のため、今回のガードの影響を受けず引き続き解決できること。"""
    conn, run_id = db_conn
    cela_main._flag_needs_human_input_tool_impl(_flag_args(), conn, run_id, "expert", "phase_1", "task_1_1")

    result = cela_main._answer_human_input(
        conn, run_id, "goal_escalation_hil_ESC-test", "approved", "",
        "開発者が判断", "承認する。",
    )

    assert result["success"] is True
    row = conn.execute(
        "SELECT status, resolved_by FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "goal_escalation_hil_ESC-test"),
    ).fetchone()
    assert row["status"] == "resolved"
    assert row["resolved_by"] == "human_operator"


# --- 実際の事故シナリオの再現（escalate_premise_concern経由） -------------------

def test_full_scenario_self_resolve_blocked_and_revise_goal_still_rejected(db_conn):
    """[実ドライラン再現] escalate_premise_concernでHILゲート起票→User AIが
    write_issue(RESOLVE)で自己解決を試みる→拒否される→revise_goalは引き続き
    「HIL未承認」で拒否され続けること、という一連の流れをend-to-endで検証する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"

    escalate_result = cela_main.TOOL_DISPATCH["escalate_premise_concern"](
        {
            "concern_summary": "12時間運行制約と補填上限4000万円が両立しない",
            "implicated_constraint": "運行時間帯7:30-19:30",
            "why_conflicts_with_true_need": "現実的などの体制でも同時成立しない",
            "suggested_reframe": "運行時間帯を短縮するか補填上限を見直す",
        },
        {"run_id": run_id, "phases": PHASES_1_2, "current_task_id": "task_1_1", "current_phase": PHASES_1_2[0]},
    )
    assert escalate_result["success"] is True
    escalation_id = escalate_result["escalation_id"]
    hil_topic = f"goal_escalation_hil_{escalation_id}"

    # User AIがHILゲートissueを自己解決しようとする（実ドライランで実際に起きたこと）
    self_resolve_result = cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": hil_topic,
         "resolution_note": "発注者として承認しrevise_goalで改定した"},
        conn, run_id, "user", "", "task_1_1",
    )
    assert self_resolve_result["success"] is False

    # revise_goalは引き続き拒否されること（真のHIL未承認のまま）
    revise_result = cela_main.TOOL_DISPATCH["revise_goal"](
        {
            "escalation_id": escalation_id,
            "edits": [{"old_text": "7:30〜19:30", "new_text": "8:00〜16:00"}],
            "reason_why": "12時間運行では補填上限を超過するため",
        },
        {"run_id": run_id, "phases": PHASES_1_2, "current_task_id": "task_1_1", "current_phase": PHASES_1_2[0]},
    )
    assert revise_result["success"] is False
    assert "承認" in revise_result["error"] or "HIL" in revise_result["error"]
