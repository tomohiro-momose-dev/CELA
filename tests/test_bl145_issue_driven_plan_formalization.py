"""
BL-145: escalated issueを、Reflectorの正当性監査（BL-144の滞留検知）を経由してタスク
プランナーへ明示的に組み込む。

`log/2026-08-03/1347`ドライランで、detector_auto起票の汎用issue（16回occurrence蓄積）が
一度もRESOLVE/DEFERされないままBL-125のタスク遷移ゲートを塞ぎ続け、Expert/User AIが
SUPERSEDEで正規のゲートを迂回し続ける実害（BL-152の引き金にもなった）を確認した。

対策として、reflection_nodeがBL-144の滞留検知（同一escalated issueがユーザーノードを
3回通過しても未解決）を使い、既にDEFER済みでないstale issueをplan_revision_reason経由で
task_planner_nodeへ引き継ぐ。task_planner_nodeは計画再構成成功後、対象issueを
（`resolved`ではなく）新ステータス`planned`へ遷移させ、埋め込み先task_idを
`defer_to_task_id`列（BL-136のDEFERと同じ「今このissueの面倒を見ているtask_id」という
意味）に記録する。`resolved`は、実際に解決されたと確認できたときのみuser roleが
既存のwrite_issue(RESOLVE)で明示的に行う（task_plannerが計画へ組み込んだだけでは
「本当に解決した」ことにはならない、というユーザー指摘による設計）。

参照: docs/design/back_log/issue_backlog.md BL-145、
      docs/design/back_log/BL-145/BL145_basic_design.md。
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
    db_path = str(tmp_path / "test_bl145.db")
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


def _create_escalated_issue(conn, run_id, topic="bl145_topic"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "後続タスクで検証が必要な事項", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )


def _reflection_base_state(run_id, round_count):
    return {
        "risk_register": [], "goal": "g", "run_id": run_id, "round_count": round_count,
        "escalated_issue_first_seen_round": {},
    }


EXISTING_PHASES = [
    {"phase_id": "phase_1", "title": "既存フェーズ", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []},
    ]},
]

RECONFIGURED_PHASES = [
    {"phase_id": "phase_1", "title": "既存フェーズ", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_1_2", "acceptance_criteria": ["bl145_topicへの対応を含む新タスク"], "depends_on": [], "owns_variables": []},
    ]},
]


def _make_reflection_mock(monkeypatch):
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に見える。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)


# ===========================================================================
# Part A: reflection_node のトリガー判定
# ===========================================================================

def test_reflection_node_sets_plan_revision_reason_and_issue_ids_on_stale_escalated_issue(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_stale")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)  # 初観測（round=1）
    state["round_count"] = 4  # 3ラウンド経過、未解決のまま
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"
    assert "bl145_stale" in state["plan_revision_reason"]
    assert "[BL-145]" in state["plan_revision_reason"]
    assert len(state["plan_revision_issue_ids"]) == 1

    issue_row = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_stale")
    ).fetchone()
    assert state["plan_revision_issue_ids"] == [issue_row["id"]]


def test_reflection_node_bundles_multiple_stale_issues_into_one_revision(db_conn, monkeypatch):
    """実ログ(log/2026-08-03/1347)で実際に2件同時に滞留していたケースを再現する。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_stale_a")
    _create_escalated_issue(conn, run_id, topic="bl145_stale_b")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert "bl145_stale_a" in state["plan_revision_reason"]
    assert "bl145_stale_b" in state["plan_revision_reason"]
    assert len(state["plan_revision_issue_ids"]) == 2


def test_reflection_node_excludes_already_deferred_stale_issue_from_formalization(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_deferred")
    _make_reflection_mock(monkeypatch)

    # 既存タスクへ先送り済み（BL-136のDEFER）にしておく。
    cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl145_deferred", "defer_to_task_id": "task_1_1", "defer_reason": "後で見る"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": EXISTING_PHASES},
    )

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"  # 滞留自体は引き続き検知される
    assert state.get("plan_revision_issue_ids", []) == []  # だがタスク化対象からは除外
    assert state.get("plan_revision_reason", "") == ""


def test_reflection_node_does_not_overwrite_existing_plan_revision_reason(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_collision")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state["plan_revision_reason"] = "task_plan_reviewerによる差し戻し"
    state = cela_main.reflection_node(state)

    assert state["plan_revision_reason"] == "task_plan_reviewerによる差し戻し"
    assert state.get("plan_revision_issue_ids", []) == []


def test_reflection_node_no_formalization_when_not_stale(db_conn, monkeypatch):
    """回帰確認: BL-144の既存テスト（初観測では上書きしない）と同様、非stale時は何もしない。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_fresh")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=3)
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "continuing"
    assert state.get("plan_revision_reason", "") == ""
    assert state.get("plan_revision_issue_ids", []) == []


# ===========================================================================
# Part B: task_planner_node による決定論的な'planned'遷移
# ===========================================================================

def test_task_planner_node_marks_issue_planned_after_issue_driven_reconfiguration(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_topic")
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_topic")
    ).fetchone()["id"]

    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: RECONFIGURED_PHASES)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "[BL-145] bl145_topicの滞留",
        "plan_revision_issue_ids": [issue_id], "plan_review_done": True, "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    row = conn.execute("SELECT * FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["status"] == "planned"
    assert row["status"] != "resolved"
    assert row["defer_to_task_id"] in {"task_1_1", "task_1_2"}
    assert result["plan_revision_issue_ids"] == []


def test_task_planner_node_clears_plan_revision_issue_ids_even_without_issue_driven_revision(db_conn, monkeypatch):
    """既存のreviewer差し戻し・Essence Dialogue由来の再構成（plan_revision_issue_idsが空）
    では、issue_logに一切触れないこと（回帰確認）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: RECONFIGURED_PHASES)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "前提が変わったため",
        "plan_review_done": True, "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert result["plan_revision_issue_ids"] == []
    assert cela_main.get_issues_from_db(conn, run_id, list_all=True) == []


def test_task_planner_node_planning_is_idempotent_on_already_resolved_issue(db_conn, monkeypatch):
    """チェックポイント再開等での二重発火を想定: 既にresolved済みのissue_idが
    plan_revision_issue_idsに残っていても、例外を出さず単に無視すること。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_already_resolved")
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_already_resolved")
    ).fetchone()["id"]
    cela_main._write_issue_impl(
        {"action_type": "RESOLVE", "topic": "bl145_already_resolved", "resolution_note": "既に対応済み"},
        conn, run_id, "user", "", "task_1_1",
    )

    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: RECONFIGURED_PHASES)
    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "[BL-145] 再開時の二重発火想定",
        "plan_revision_issue_ids": [issue_id], "plan_review_done": True, "round_count": 4,
    }
    result = cela_main.task_planner_node(state)  # 例外が出ないこと

    row = conn.execute("SELECT * FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["status"] == "resolved"  # resolvedのまま変化しない
    assert result["plan_revision_issue_ids"] == []


def test_mark_issue_planned_returns_false_when_not_found(db_conn):
    conn, run_id = db_conn
    assert cela_main._mark_issue_planned(conn, run_id, "nonexistent-id", embedded_task_ids=["task_1_1"]) is False


def test_mark_issue_planned_does_not_go_through_issue_permission_check():
    src = inspect.getsource(cela_main._mark_issue_planned)
    assert "_check_issue_permission" not in src


# ===========================================================================
# Part C: 'planned'後もDEFER・再発検知が既存機構のまま機能すること（回帰確認）
# ===========================================================================

def test_planned_issue_can_still_be_deferred_further(db_conn):
    """ユーザー要件: 「そのタスクに取り掛かりやはり解決しない場合、さらなる後続タスクへの
    延期も可能とする」——'planned'状態のissueも既存のDEFERが引き続き機能すること。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_replan")
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_replan")
    ).fetchone()["id"]
    cela_main._mark_issue_planned(conn, run_id, issue_id, embedded_task_ids=["task_1_1"])

    phases_with_next_task = [
        {"phase_id": "phase_1", "tasks": [
            {"task_id": "task_1_1", "acceptance_criteria": []},
            {"task_id": "task_1_2", "acceptance_criteria": []},
        ]},
    ]
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "bl145_replan", "defer_to_task_id": "task_1_2", "defer_reason": "task_1_1でも未解決だったため"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": phases_with_next_task},
    )
    assert result["success"] is True

    row = conn.execute("SELECT * FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["defer_to_task_id"] == "task_1_2"
    assert row["status"] == "planned"  # DEFERはstatusを変更しない


def test_planned_issue_re_escalates_via_create_reoccurrence(db_conn):
    """既存のCREATE経由の再発検知（occurrence_count>=2で機械的にescalatedへ戻る）が、
    'planned'状態のissueに対してもコード変更なしで機能すること。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_reescalate")  # occurrence=1, escalated(major)
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_reescalate")
    ).fetchone()["id"]
    cela_main._mark_issue_planned(conn, run_id, issue_id, embedded_task_ids=["task_1_2"])

    result = cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl145_reescalate", "description": "task_1_2でも解消されなかった", "severity": "minor"},
        conn, run_id, "detector", "", "task_1_2",
    )
    assert result["success"] is True
    assert result["occurrence_count"] == 2

    row = conn.execute("SELECT * FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["status"] == "escalated"
    assert row["severity"] == "major"


# ===========================================================================
# Part D: facilitator_node の衝突防御ガード
# ===========================================================================

def _base_facilitator_state(run_id: str) -> dict:
    return {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール",
        "run_id": run_id,
        "last_reflection_note": "",
        "essence_dialogue_active": True,
        "essence_dialogue_round": 2,
        "essence_dialogue_max_rounds": 5,
        "essence_dialogue_topic": "essence_dialogue_x",
        "last_essence_proposal": {
            "topic": "essence_dialogue_x", "status": "Approved", "action_type": "UPDATE",
            "reason_why": "小型車両複数台の構成へ見直す",
        },
    }


def test_facilitator_node_defers_essence_convergence_when_plan_revision_reason_already_set(db_conn, monkeypatch):
    monkeypatch.setattr(
        cela_main, "call_facilitator",
        lambda *a, **k: (_ for _ in ()).throw(AssertionError("収束を持ち越す場合はcall_facilitatorを呼んではならない")),
    )
    conn, run_id = db_conn

    state = _base_facilitator_state(run_id)
    state["plan_revision_reason"] = "[BL-145] issue駆動の理由（使用中）"
    result = cela_main.facilitator_node(state)

    assert result["plan_revision_reason"] == "[BL-145] issue駆動の理由（使用中）"
    assert result["essence_dialogue_active"] is True  # 収束せず、次回へ持ち越される


# ===========================================================================
# Part E: 'planned' issueの可視化（非強制の参考情報）
# ===========================================================================

def test_get_planned_issues_returns_only_planned_status(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_visible")
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_visible")
    ).fetchone()["id"]
    cela_main._mark_issue_planned(conn, run_id, issue_id, embedded_task_ids=["task_1_2"])

    planned = cela_main._get_planned_issues(conn, run_id)
    assert len(planned) == 1
    assert planned[0]["topic"] == "bl145_visible"


def test_build_planned_issue_pin_text_mentions_task_id_and_resolve_hint(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, topic="bl145_pin")
    issue_id = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND topic=?", (run_id, "bl145_pin")
    ).fetchone()["id"]
    cela_main._mark_issue_planned(conn, run_id, issue_id, embedded_task_ids=["task_1_2"])

    text = cela_main._build_planned_issue_pin_text(conn, run_id)
    assert "bl145_pin" in text
    assert "task_1_2" in text
    assert "RESOLVE" in text


def test_generate_user_utterance_wiring_injects_planned_issue_pin():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_planned_issue_pin_text" in src
