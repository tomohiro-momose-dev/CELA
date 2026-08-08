"""
BL-194: `defer_to_task_id`の解釈不統一と自己先送りによる偽の停滞判定・強制停止。

`log/2026-08-08/1514`（`facilitation_count>5`でhalt）で、停滞判定の引き金となった滞留
escalated issue20件は全件がwrite_issue(DEFER)によりtriage済み（受け皿task_id設定済み）で
あったにもかかわらず、督促経路（BL-103 pin「⚠️要対応」、BL-096/144停滞判定）だけが
`defer_to_task_id`の有無を一切見ずに全件を「未対応」として扱い続けていた。うち6件は
`task_2_1`自身への自己先送りで、DEFERの実効性が完全に打ち消されていた。

本ファイルは以下を検証する（BL194_basic_design.md §10.1に対応、実LLM API呼び出しは伴わない）：
- 述語`_is_issue_effectively_deferred`/`_get_actionable_escalated_issues`（自己先送り・
  受け皿失効リバイバル・ACKNOWLEDGE抑制の判定）
- `reflection_node`の停滞トリガーが、全件triage済みの場合にstagnantを発火させないこと
  （本事故の直接回帰テスト）
- BL-103 pinのトーン分離（要対応／対応予定確定済み／対応中の3分離、和集合の保存）
- Reflection/Facilitatorへのタスクスコープ注入（`_build_current_task_scope_brief`）
- DEFERのスコープ・エコーバック

参照: docs/design/back_log/issue_backlog.md BL-194、
      docs/design/back_log/BL-194/BL194_basic_design.md。
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
    db_path = str(tmp_path / "test_bl194.db")
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


def _insert_deliverable(conn, run_id, task_id, status, seq=1):
    """[BL-167踏襲] _is_task_completedを成立させるためのAgreement投入ヘルパー。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", status, f"{task_id}の成果物", "X" * 300, "r", "expert", "Deliverable",
         "phase_1", task_id, "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()


def _create_escalated_issue(conn, run_id, topic, task_id="task_1_1"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "後続タスクで検証が必要な事項", "severity": "major"},
        conn, run_id, "detector", "", task_id,
    )


PHASES_1_2 = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]


def _defer(conn, run_id, topic, defer_to_task_id, current_task_id="task_1_1"):
    return cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": topic, "defer_to_task_id": defer_to_task_id, "defer_reason": "理由"},
        conn, run_id, "user", "", current_task_id,
        state={"phases": PHASES_1_2},
    )


# ===========================================================================
# A. _is_issue_effectively_deferred
# ===========================================================================

def test_not_deferred_when_defer_to_task_id_empty(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a1")
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a1'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "task_1_1") is False


def test_deferred_to_other_incomplete_task_is_effective(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a2")
    _defer(conn, run_id, "a2", "task_1_2")
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a2'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "task_1_1") is True


def test_deferred_to_completed_task_is_not_effective_bl167_preserved(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a3")
    _defer(conn, run_id, "a3", "task_1_2")
    _insert_deliverable(conn, run_id, "task_1_2", "Approved")
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a3'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "task_1_1") is False


def test_self_deferral_is_not_effective(db_conn):
    """[BL-194本丸] defer_to_task_id == current_task_idの自己先送りは「先送りされていない」。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a4")
    # tool boundary（S8）は拒否するため、DBを直接書き換えて自己先送り状態を模擬する
    # （消費側の多重防御自体を検証する目的のため、UPDATE経由で意図的に不整合状態を作る）。
    conn.execute("UPDATE issue_log SET defer_to_task_id='task_1_1' WHERE run_id=? AND topic='a4'", (run_id,))
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a4'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "task_1_1") is False


def test_self_deferral_check_skipped_when_current_task_id_empty(db_conn):
    """current_task_idが空文字（初回ターン等）のときは自己先送り判定をスキップし、
    BL-167の受け皿失効判定のみへ安全に縮退する（R7）。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a5")
    conn.execute("UPDATE issue_log SET defer_to_task_id='task_1_2' WHERE run_id=? AND topic='a5'", (run_id,))
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a5'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "") is True


def test_deferred_to_approved_with_conditions_counts_as_completed(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "a6")
    _defer(conn, run_id, "a6", "task_1_2")
    _insert_deliverable(conn, run_id, "task_1_2", "Approved_with_Conditions")
    row = conn.execute("SELECT * FROM issue_log WHERE run_id=? AND topic='a6'", (run_id,)).fetchone()
    assert cela_main._is_issue_effectively_deferred(conn, run_id, dict(row), "task_1_1") is False


# ===========================================================================
# B. _get_actionable_escalated_issues
# ===========================================================================

def test_actionable_excludes_only_effectively_deferred(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "b1")  # 未先送り→actionable
    _create_escalated_issue(conn, run_id, "b2")
    _defer(conn, run_id, "b2", "task_1_2")  # 他タスクへ正当に先送り→除外
    _create_escalated_issue(conn, run_id, "b3")
    conn.execute("UPDATE issue_log SET defer_to_task_id='task_1_1' WHERE run_id=? AND topic='b3'", (run_id,))  # 自己先送り→actionable
    topics = {r["topic"] for r in cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1")}
    assert topics == {"b1", "b3"}


def test_actionable_excludes_non_escalated_statuses(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "b4", "description": "d", "severity": "minor"},
        conn, run_id, "detector", "", "task_1_1",
    )
    topics = {r["topic"] for r in cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1")}
    assert "b4" not in topics


def test_actionable_empty_when_all_triaged_bl194_core_regression(db_conn):
    """[本事故の直接回帰テスト] 全件が正当にDEFER済みなら空リストを返す
    （log/2026-08-08/1514で20件全件がtriage済みだったにもかかわらず停滞判定が
    発火した事故の一次修正）。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "b5")
    _defer(conn, run_id, "b5", "task_1_2")
    _create_escalated_issue(conn, run_id, "b6")
    _defer(conn, run_id, "b6", "task_1_2")
    assert cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1") == []


def test_actionable_excludes_acknowledged_when_round_count_given(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "b7")
    cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": "b7", "ack_reason": "対応中"},
        conn, run_id, "user", "", "task_1_1", state={"round_count": 1},
    )
    # round_countを渡さなければACK抑制はかからない
    assert len(cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1")) == 1
    # round_countを渡すとTTL内はACK抑制がかかる
    assert cela_main._get_actionable_escalated_issues(conn, run_id, "task_1_1", round_count=1) == []


# ===========================================================================
# C. reflection_node の停滞トリガー
# ===========================================================================

def _reflection_base_state(run_id, round_count, current_task_id="task_1_1"):
    return {
        "risk_register": [], "goal": "g", "run_id": run_id, "round_count": round_count,
        "escalated_issue_first_seen_round": {}, "current_task_id": current_task_id,
    }


def _make_reflection_mock(monkeypatch):
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に見える。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)


def test_stagnant_not_triggered_when_all_issues_triaged(db_conn, monkeypatch):
    """[halt再発防止の中核] 全件がDEFER済み（受け皿確定）なら、4ラウンド経過してもstagnantに
    上書きされない。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "c1")
    _defer(conn, run_id, "c1", "task_1_2")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] != "stagnant"


def test_stagnant_still_triggered_for_untriaged_issue_bl144_preserved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "c2")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"


def test_stagnant_triggered_after_receptacle_revival_bl167_preserved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "c3")
    _defer(conn, run_id, "c3", "task_1_2")
    _insert_deliverable(conn, run_id, "task_1_2", "Approved")  # 受け皿が失効
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"


def test_stagnant_triggered_for_self_deferred_issue_design_decision_ss34(db_conn, monkeypatch):
    """[BL194_basic_design.md §3.4の明示的な設計判断] 自己先送りは督促されるので数えられる。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "c4")
    conn.execute("UPDATE issue_log SET defer_to_task_id='task_1_1' WHERE run_id=? AND topic='c4'", (run_id,))
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id, round_count=1)
    state = cela_main.reflection_node(state)
    state["round_count"] = 4
    state = cela_main.reflection_node(state)

    assert state["discussion_status"] == "stagnant"


# ===========================================================================
# D. pinのトーン分離
# ===========================================================================

def test_escalation_pin_excludes_deferred(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "d1")
    _defer(conn, run_id, "d1", "task_1_2")
    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1")
    assert "d1" not in pin


def test_deferred_pin_shows_defer_target_and_non_forcing_tone(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "d2")
    _defer(conn, run_id, "d2", "task_1_2")
    pin = cela_main._build_deferred_issue_pin_text(conn, run_id, "task_1_1")
    assert "d2" in pin
    assert "task_1_2" in pin
    assert "解決する必要はありません" in pin


def test_escalation_and_deferred_pins_union_preserves_context(db_conn):
    """文脈が失われていないことの保証: 要対応pin ∪ 対応予定pin = 従来の全escalated集合。"""
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "d3")
    _create_escalated_issue(conn, run_id, "d4")
    _defer(conn, run_id, "d4", "task_1_2")
    escalation_pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1")
    deferred_pin = cela_main._build_deferred_issue_pin_text(conn, run_id, "task_1_1")
    assert "d3" in escalation_pin and "d3" not in deferred_pin
    assert "d4" in deferred_pin and "d4" not in escalation_pin


def test_acknowledged_pin_shows_remaining_rounds(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "d5")
    cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": "d5", "ack_reason": "対応中"},
        conn, run_id, "user", "", "task_1_1", state={"round_count": 1},
    )
    pin = cela_main._build_acknowledged_issue_pin_text(conn, run_id, 1)
    assert "d5" in pin
    assert "対応中" in pin
    assert cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", round_count=1).find("d5") == -1


def test_detector_source_mentions_bl194_scope_guard():
    source = inspect.getsource(cela_main.call_detector)
    assert "BL-194" in source
    assert "_build_deferred_issue_pin_text" in source


# ===========================================================================
# E. スコープ注入
# ===========================================================================

def test_scope_brief_includes_acceptance_criteria_and_owns_variables():
    state = {
        "current_task_id": "task_2_1",
        "current_phase": {"phase_id": "phase_2", "tasks": [
            {"task_id": "task_2_1", "description": "需要モデリング",
             "acceptance_criteria": ["ODマトリクスを作成する"], "owns_variables": ["od_matrix"]},
        ]},
    }
    brief = cela_main._build_current_task_scope_brief(state)
    assert "ODマトリクスを作成する" in brief
    assert "od_matrix" in brief
    assert "task_2_1" in brief


def test_scope_brief_empty_when_no_current_task():
    state = {"current_task_id": "", "current_phase": {}}
    assert cela_main._build_current_task_scope_brief(state) == ""


def test_scope_brief_does_not_touch_db_or_whiteboard():
    """_build_task_scope_contextと違い、DB接続を引数に取らない＝ホワイトボード全文を
    含まない軽量版であることの確認（BL-170の再現リスク回避）。"""
    sig = inspect.signature(cela_main._build_current_task_scope_brief)
    assert list(sig.parameters.keys()) == ["state"]


def test_reflection_source_references_scope_brief():
    source = inspect.getsource(cela_main.call_reflection)
    assert "_build_current_task_scope_brief" in source
    assert "BL-194" in source


def test_facilitator_source_references_scope_brief_in_both_modes():
    source = inspect.getsource(cela_main.call_facilitator)
    assert source.count("_build_current_task_scope_brief") >= 2


# ===========================================================================
# F. DEFERのスコープ・エコーバック
# ===========================================================================

def test_defer_success_echoes_target_task_scope(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "f1")
    phases = [{"phase_id": "phase_1", "tasks": [
        {"task_id": "task_1_1"},
        {"task_id": "task_1_2", "description": "詳細設計", "acceptance_criteria": ["Xを満たす"], "owns_variables": ["y"]},
    ]}]
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "f1", "defer_to_task_id": "task_1_2", "defer_reason": "後で"},
        conn, run_id, "user", "", "task_1_1", state={"phases": phases},
    )
    assert result["success"] is True
    assert result["target_task_scope"]["acceptance_criteria"] == ["Xを満たす"]
    assert result["target_task_scope"]["owns_variables"] == ["y"]


def test_defer_to_task_without_declared_scope_does_not_crash(db_conn):
    conn, run_id = db_conn
    _create_escalated_issue(conn, run_id, "f2")
    phases = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": "f2", "defer_to_task_id": "task_1_2", "defer_reason": "後で"},
        conn, run_id, "user", "", "task_1_1", state={"phases": phases},
    )
    assert result["success"] is True
    assert result["target_task_scope"]["acceptance_criteria"] == []
