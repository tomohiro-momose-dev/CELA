"""
BL-086: 前提エスカレーション経路 + Freeze復活 + ゴール改定（GoalShiftEventの実消費化）。

実ドライラン（log/2026-07-24/2054）で、Expertが「オンデマンド交通なのに予算制約から
逆算して35人乗りバスを導入する」という、そもそもの前提と数値的な帳尻合わせの間に矛盾を
抱えたまま進行している事例をユーザーが発見した。調査の結果、(1) Expertが「この制約の
立て方自体が真の目的と矛盾しているのでは」と気づいても表明する手段がない、(2) User AIが
例外を承認してもそれを恒久的にピン留めするFreeze機構がD-045で無効化されたままDetectorの
独立監査に無限に再燃させられる、(3) ゴール自体（state["goal"]）を改定する手段がなく
GoalShiftEventが書きっぱなしで何も消費しない、という三重の構造的欠陥が判明した。

対策として、新設ツール escalate_premise_concern（Expert/User AI）・
resolve_premise_concern（User AI専用、却下）・revise_goal（User AI専用、承認・
ゴール改定＋Freeze）を追加し、Freezeをgenerate_user_utteranceのtoolsへ再配線、
call_detectorのプロンプトに🔒Freeze済み項目を尊重する指示を追加した。

参照: docs/design/issue_backlog.md BL-086。
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
    db_path = str(tmp_path / "test_bl086.db")
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
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_GOAL_TEXT = ""


# ===========================================================================
# escalate_premise_concern（提起）
# ===========================================================================

def test_bl086_escalate_premise_concern_allows_expert_and_user(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "35人乗りバスはオンデマンドと矛盾",
        "implicated_constraint": "導入台数上限2台（予算制約）",
        "why_conflicts_with_true_need": "オンデマンド輸送は本来小型車両が適する",
        "suggested_reframe": "小型車両を複数台導入する構成に変更",
    })
    assert result["success"] is True
    assert result["escalation_id"].startswith("ESC-")

    row = cela_main.get_goal_escalation(conn, run_id, result["escalation_id"])
    assert row is not None
    assert row["status"] == "Open"
    assert row["raised_by_role"] == "expert"


def test_bl086_escalate_premise_concern_rejects_other_roles(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })
    assert result["success"] is False
    assert "detector" in result["error"]


def test_bl086_escalate_premise_concern_requires_all_fields(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({"concern_summary": "s"})
    assert result["success"] is False
    assert "implicated_constraint" in result["error"]


# ===========================================================================
# resolve_premise_concern（却下）
# ===========================================================================

def test_bl086_resolve_premise_concern_rejects_non_user_role(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["resolve_premise_concern"]({"escalation_id": "ESC-x", "reason": "r"})
    assert result["success"] is False
    assert "user" in result["error"]


def test_bl086_resolve_premise_concern_marks_rejected_and_logs_decision(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]

    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["resolve_premise_concern"]({
        "escalation_id": escalation_id, "reason": "現行の予算制約は妥当と判断",
    })
    assert result["success"] is True

    row = cela_main.get_goal_escalation(conn, run_id, escalation_id)
    assert row["status"] == "Rejected"
    assert row["resolution_reason"] == "現行の予算制約は妥当と判断"

    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert any(d["who"] == "user" and escalation_id in d["what"] for d in decisions)


def test_bl086_resolve_premise_concern_rejects_already_resolved(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["resolve_premise_concern"]({"escalation_id": escalation_id, "reason": "r1"})
    second = cela_main.TOOL_DISPATCH["resolve_premise_concern"]({"escalation_id": escalation_id, "reason": "r2"})
    assert second["success"] is False
    assert "Rejected" in second["error"]


# ===========================================================================
# revise_goal（承認・ゴール改定）
# ===========================================================================

def test_bl086_revise_goal_rejects_non_user_role(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": "ESC-x", "edits": [{"old_text": "a", "new_text": "b"}], "reason_why": "r",
    })
    assert result["success"] is False
    assert "user" in result["error"]


def test_bl086_revise_goal_rejects_unknown_escalation_id(db_conn):
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = "台数上限は2台とする。"
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": "ESC-nonexistent", "edits": [{"old_text": "台数上限は2台とする。", "new_text": "台数上限は撤廃する。"}],
        "reason_why": "r",
    })
    assert result["success"] is False
    assert "見つかりません" in result["error"]


def test_bl086_revise_goal_fails_edits_mismatch_keeps_escalation_open(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = "台数上限は2台とする。"
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": "存在しない文言", "new_text": "x"}],
        "reason_why": "r",
    })
    assert result["success"] is False
    row = cela_main.get_goal_escalation(conn, run_id, escalation_id)
    assert row["status"] == "Open", "edits失敗時はリトライ可能なようOpenのまま維持されるべき"


def test_bl086_revise_goal_accept_updates_escalation_and_goal_shift_event(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "35人乗りバスはオンデマンドと矛盾",
        "implicated_constraint": "導入台数上限2台（予算制約）",
        "why_conflicts_with_true_need": "オンデマンド輸送は本来小型車両が適する",
        "suggested_reframe": "小型車両を複数台導入する構成に変更",
    })["escalation_id"]

    cela_main._CURRENT_CALLER_ROLE = "user"
    old_goal = "台数上限は2台とする。予算上限は1億円とする。"
    cela_main._CURRENT_GOAL_TEXT = old_goal
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": "台数上限は2台とする。", "new_text": "台数上限は撤廃し、小型車両複数台の構成を許容する。"}],
        "reason_why": "オンデマンド輸送の本質（分散した需要への即応）を優先し、台数上限の文言を見直す",
    })
    assert result["success"] is True
    assert result["new_goal_text"] == "台数上限は撤廃し、小型車両複数台の構成を許容する。予算上限は1億円とする。"
    assert result["old_goal_text"] == old_goal

    row = cela_main.get_goal_escalation(conn, run_id, escalation_id)
    assert row["status"] == "Accepted"

    shift_rows = conn.execute("SELECT * FROM goal_shift_events WHERE run_id=?", (run_id,)).fetchall()
    assert len(shift_rows) == 1
    assert shift_rows[0]["shift_kind"] == "premise_revision"
    assert shift_rows[0]["triggered_by"] == "Escalation_Resolution"
    assert shift_rows[0]["from_goal_state"] == old_goal
    assert shift_rows[0]["to_goal_state"] == result["new_goal_text"]

    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert any(d["who"] == "user" and escalation_id in d["what"] for d in decisions)


def test_bl086_revise_goal_with_freeze_agreement_id_freezes_and_blocks_supersede(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "35人乗り採用の妥当性判断",
        "decision_what": "予算制約の下でピーク需要を満たすため35人乗り車両を採用する",
        "reason_why": "確定", "entry_type": "Decision",
    })
    agreement_id = cela_main.get_agreements_from_db(conn, run_id)[0]["id"]

    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = "台数上限は2台とする。"
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": "台数上限は2台とする。", "new_text": "台数上限は撤廃する。"}],
        "reason_why": "承認する",
        "freeze_agreement_id": agreement_id,
    })
    assert result["success"] is True
    assert result["frozen_agreement_id"] == agreement_id

    refreshed = cela_main.get_agreements_from_db(conn, run_id)
    assert refreshed[0]["is_frozen"] == 1

    supersede_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "SUPERSEDE", "status": "Rejected", "topic": "再監査で誤り判定",
        "target_topic": "35人乗り採用の妥当性判断", "decision_what": "誤りと判断", "reason_why": "r",
        "entry_type": "Decision",
    })
    assert supersede_result["success"] is False
    assert "Freeze" in supersede_result["error"]


# ===========================================================================
# generate_user_utterance_node 配線: state["goal"]への反映
# ===========================================================================

def test_bl086_generate_user_utterance_node_wiring_references_get_last_goal_revision():
    src = inspect.getsource(cela_main.generate_user_utterance_node)
    assert "get_last_goal_revision" in src
    assert 'state["goal"]' in src


def test_bl086_generate_user_utterance_node_applies_goal_revision_to_state(monkeypatch):
    # generate_user_utterance_nodeは実行時にのみ設定されるモジュールレベルのconfigを
    # 参照するため（__main__ブロックでのみ代入）、テストでは名前解決できれば十分。
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "発言内容")
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: {
        "new_goal_text": "改定後のゴール文", "old_goal_text": "改定前", "escalation_id": "ESC-1",
    })
    state = {
        "goal": "改定前", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [],
    }
    result = cela_main.generate_user_utterance_node(state)
    assert result["goal"] == "改定後のゴール文"


def test_bl086_generate_user_utterance_node_keeps_goal_unchanged_when_no_revision(monkeypatch):
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "発言内容")
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    state = {
        "goal": "変わらないゴール", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [],
    }
    result = cela_main.generate_user_utterance_node(state)
    assert result["goal"] == "変わらないゴール"


# ===========================================================================
# プロンプト配線（inspect.getsource による機械的な確認）
# ===========================================================================

def test_bl086_call_expert_wiring_narrow_channel_only():
    """Expertは提起のみ許可され、却下・承認ツールへはアクセスできないこと
    （BL-025スコープガードレールを緩めない、というBL-086の中心的な制約の機械的保証）。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "ESCALATE_PREMISE_CONCERN_TOOL" in src
    assert "_get_escalation_status_text_for_expert" in src
    assert "RESOLVE_PREMISE_CONCERN_TOOL" not in src
    assert "REVISE_GOAL_TOOL" not in src


def test_bl086_generate_user_utterance_wiring_full_resolution_toolset():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "ESCALATE_PREMISE_CONCERN_TOOL" in src
    assert "RESOLVE_PREMISE_CONCERN_TOOL" in src
    assert "REVISE_GOAL_TOOL" in src
    assert "FREEZE_AGREEMENT_TOOL" in src
    assert "_get_open_escalations_text" in src
    assert "_CURRENT_GOAL_TEXT" in src


def test_bl086_call_detector_wiring_frozen_awareness_both_passes():
    """call_detectorの両パス（ドメイン妥当性・数値監査）が🔒Freeze済み項目を尊重する
    指示を持っていること。Detector自身はescalate/resolve/reviseのいずれのツールも
    持たない（out of scope）ことも合わせて確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_get_frozen_agreements_text" in src
    assert src.count("BL-086") >= 2
    assert "ESCALATE_PREMISE_CONCERN_TOOL" not in src
    assert "RESOLVE_PREMISE_CONCERN_TOOL" not in src
    assert "REVISE_GOAL_TOOL" not in src


# ===========================================================================
# _find_active_deliverable_agreement等の既存機構との非干渉確認
# ===========================================================================

def test_bl086_get_open_goal_escalations_returns_only_open_in_order(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    id1 = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "1つ目", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]
    id2 = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "2つ目", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["resolve_premise_concern"]({"escalation_id": id1, "reason": "却下"})

    open_list = cela_main.get_open_goal_escalations(conn, run_id)
    assert len(open_list) == 1
    assert open_list[0]["escalation_id"] == id2
