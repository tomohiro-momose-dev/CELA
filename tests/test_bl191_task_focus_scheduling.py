"""
BL-191: Stage4駆動の過去タスク一時フォーカス切替＋併記対象タスクの明示。

BL-186で一度「(a)過去タスクへ戻る新ルートを作る／(b)前進のみで新フェーズを追加する」を検討し
(b)を選んだ判断を、ストレステスト結果を踏まえて覆し、(a)実際にcurrent_task_idを過去タスクへ
一時的に巻き戻す経路を新設した。実装場所はUser AIの既存Stage4を拡張する形とし、新規ツール
`schedule_task_focus`（decision_type: redirect_backward/joint_focus/clear_companion/
force_resume）を追加した。

ユーザー主導のユースケース通しトレースで6件のバグを発見し対策済み：
- バグ①: BL-163でフラグされた過去タスクはステータス上Approvedのまま残るため、redirect直後に
  「もう完了している」と誤判定して即座に復帰してしまう。baseline_agreement_id比較で対策。
- バグ②: 巻き戻し中にBL-190のパターン3（current_task_idクリア）が発火すると、task_focus_stack
  に積んだ元タスクへ二度と戻れなくなる永久迷子。BL-190側にforce_resumeフックを追加して対策。
- バグ③〜⑤: Detector/Reflection/Facilitatorが「意図的な手戻り中」を知らず誤判定する恐れ。
  常設ステータス表示_build_task_focus_state_textの共有で対策。
- バグ⑥: joint_focusのcompanionにも同型の早期クリアバグ。baseline比較で対策。

独立レビューでも7件の指摘を反映（force_resumeのPhase前倒し、ブリッジグローバル配線の完全性、
decision_extractor_nodeのtarget_roleガード等）。

参照: docs/design/back_log/issue_backlog.md BL-191、
      docs/design/back_log/BL-191/BL191_basic_design.md。
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
    db_path = str(tmp_path / "test_bl191.db")
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
        cela_main._LAST_SCHEDULING_DECISION = None


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]},
    {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1"}]},
]


def _base_state(run_id: str, current_task_id: str = "task_2_1", phases=None) -> dict:
    phases = phases if phases is not None else _PHASES
    current_phase = next((p for p in phases for t in p.get("tasks", []) if t["task_id"] == current_task_id), phases[0])
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": current_phase,
        "current_task_id": current_task_id,
        "round_count": 1,
        "task_focus_stack": [],
        "task_focus_companion": None,
        "task_focus_redirect_count": 0,
        "task_focus_redirect_notice": "",
        "task_focus_resume_notice": "",
    }


def _insert_deliverable(conn, run_id, phase_id, task_id, status, seq=1):
    agreement_id = f"AG-TEST-{task_id}-{seq:03d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE" if seq == 1 else "UPDATE", status, f"{task_id}の成果物", "x", "r", "expert",
         "Deliverable", phase_id, task_id, "[]", "{}", time.time() + seq, "", 0, None, run_id),
    )
    conn.commit()
    return agreement_id


# ============================================================
# 1. _schedule_task_focus_tool_impl 単体
# ============================================================

def test_tool_rejects_non_user_role(db_conn):
    _, run_id = db_conn
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "joint_focus", "companion_task_id": "task_1_1", "reason": "r"},
        cela_main.get_active_conn(), run_id, "expert", _base_state(run_id),
    )
    assert result["success"] is False
    assert "user" in result["error"]


def test_tool_requires_decision_type_and_reason(db_conn):
    _, run_id = db_conn
    state = _base_state(run_id)
    result = cela_main._schedule_task_focus_tool_impl({"decision_type": "joint_focus"}, cela_main.get_active_conn(), run_id, "user", state)
    assert result["success"] is False


def test_redirect_backward_rejects_when_no_deliverable(db_conn):
    """未着手タスク（Deliverable無し）へはredirect_backwardできない。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "redirect_backward", "target_task_id": "task_1_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "Deliverable" in result["error"]


def test_redirect_backward_rejects_when_target_is_current_task(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "redirect_backward", "target_task_id": "task_2_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False


def test_redirect_backward_rejects_when_stack_non_empty(db_conn):
    """深さ1固定：既に中断中のフォーカスがある間は新規redirect_backwardを拒否する。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    state["task_focus_stack"] = [{"task_id": "task_2_1", "phase_id": "phase_2", "reason": "既存",
                                   "pushed_at_round": 1, "focused_task_id": "task_1_1", "baseline_agreement_id": ""}]
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "redirect_backward", "target_task_id": "task_1_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "深さ1" in result["error"]


def test_redirect_backward_rejects_past_max_count(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    state["task_focus_redirect_count"] = cela_main._MAX_TASK_FOCUS_REDIRECTS
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "redirect_backward", "target_task_id": "task_1_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "上限" in result["error"]


def test_redirect_backward_success_captures_baseline_agreement_id(db_conn):
    """成功時、redirect時点の最新Deliverable agreement_idがbaseline_agreement_idとして
    _LAST_SCHEDULING_DECISIONへ記録されること（バグ①対策の入口）。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "redirect_backward", "target_task_id": "task_1_1", "reason": "ゴール改定の影響"},
        conn, run_id, "user", state,
    )
    assert result["success"] is True
    decision = cela_main.get_last_scheduling_decision()
    assert decision["decision_type"] == "redirect_backward"
    assert decision["target_task_id"] == "task_1_1"
    assert decision["baseline_agreement_id"] == agreement_id
    # scheduling_draftsにも記録される
    history = cela_main.get_scheduling_decision_history(conn, run_id)
    assert len(history) == 1
    assert history[0]["decision_type"] == "redirect_backward"


def test_joint_focus_success_and_rejects_self_or_nonexistent(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    # 存在しないtask_id
    bad = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "joint_focus", "companion_task_id": "task_9_9", "reason": "r"}, conn, run_id, "user", state
    )
    assert bad["success"] is False
    # 自分自身
    self_ref = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "joint_focus", "companion_task_id": "task_2_1", "reason": "r"}, conn, run_id, "user", state
    )
    assert self_ref["success"] is False
    # 成功
    ok = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "joint_focus", "companion_task_id": "task_1_1", "reason": "依存関係"}, conn, run_id, "user", state
    )
    assert ok["success"] is True
    decision = cela_main.get_last_scheduling_decision()
    assert decision["companion_task_id"] == "task_1_1"


# ============================================================
# 2. _apply_backward_redirect / _maybe_resume_forward_focus / _force_resume_forward_focus
# ============================================================

def test_apply_backward_redirect_pushes_stack_and_switches_focus(db_conn):
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    redirect = {"target_task_id": "task_1_1", "reason": "テスト理由", "baseline_agreement_id": "AG-BASE-1"}
    cela_main._apply_backward_redirect(state, redirect)
    assert state["current_task_id"] == "task_1_1"
    assert state["current_phase"]["phase_id"] == "phase_1"
    assert len(state["task_focus_stack"]) == 1
    entry = state["task_focus_stack"][0]
    assert entry["task_id"] == "task_2_1"  # 中断された元のフォワードタスク
    assert entry["focused_task_id"] == "task_1_1"
    assert entry["baseline_agreement_id"] == "AG-BASE-1"
    assert state["task_focus_redirect_count"] == 1
    assert "task_1_1" in state["task_focus_redirect_notice"]


def test_apply_backward_redirect_double_push_is_noop(db_conn):
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    state["task_focus_stack"] = [{"task_id": "task_2_1", "phase_id": "phase_2", "reason": "既存",
                                   "pushed_at_round": 1, "focused_task_id": "task_1_1", "baseline_agreement_id": ""}]
    cela_main._apply_backward_redirect(state, {"target_task_id": "task_1_1", "reason": "r2", "baseline_agreement_id": ""})
    assert len(state["task_focus_stack"]) == 1  # 変わらない


def test_bug1_resume_does_not_fire_when_task_already_approved_before_redirect(db_conn):
    """【バグ①回帰テスト】redirect先が既にApproved状態のまま（BL-163フラグ済みの典型ケース）の
    状態で、Expertがまだ何も提出していない時点では復帰しないこと。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    assert state["current_task_id"] == "task_1_1"
    # Expertはまだ何も新しい成果物を出していない（DBはbaseline_agreement_idのままApproved）
    cela_main._maybe_resume_forward_focus(state, conn, run_id)
    assert state["current_task_id"] == "task_1_1"  # 復帰していない
    assert len(state["task_focus_stack"]) == 1


def test_bug1_resume_fires_once_new_deliverable_is_approved(db_conn):
    """redirect後、実際に新しいDeliverableが作られ承認されて初めて復帰すること。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    # Expertが新版を提出し、User AIが承認した（新しいagreement行が追加される）
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved", seq=2)
    cela_main._maybe_resume_forward_focus(state, conn, run_id)
    assert state["current_task_id"] == "task_2_1"  # 元のフォワードタスクへ復帰
    assert state["task_focus_stack"] == []
    assert "task_1_1" in state["task_focus_resume_notice"]


def test_resume_reresolves_phase_after_bl190_style_reorg(db_conn):
    """BL-190型のフェーズ再構成が復帰待ち中に起きても、スタックのtask_idさえ残っていれば
    正しいフェーズを再解決して復帰できること。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved", seq=2)
    # フェーズ再構成: task_2_1がphase_2からphase_3へ移動
    state["phases"] = [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]},
        {"phase_id": "phase_3", "tasks": [{"task_id": "task_2_1"}]},
    ]
    cela_main._maybe_resume_forward_focus(state, conn, run_id)
    assert state["current_task_id"] == "task_2_1"
    assert state["current_phase"]["phase_id"] == "phase_3"


def test_resume_degrades_gracefully_when_stacked_task_vanished(db_conn):
    """復帰先（スタック上のフォワードタスク）自体が計画再構成で消失した場合、
    スタックのみクリアされ警告に留まる（クラッシュしない）。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved", seq=2)
    # task_2_1が新計画のどこにも存在しない
    state["phases"] = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}]
    cela_main._maybe_resume_forward_focus(state, conn, run_id)
    assert state["task_focus_stack"] == []


def test_force_resume_pops_unconditionally_and_creates_followup_issue(db_conn):
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    # まだ何も新しい成果物は無い（force_resumeは未解決のまま打ち切る安全弁）
    cela_main._force_resume_forward_focus(state)
    assert state["current_task_id"] == "task_2_1"
    assert state["task_focus_stack"] == []
    assert "task_1_1" in state["task_focus_resume_notice"]
    issues = cela_main.get_all_open_issues(conn, run_id) if hasattr(cela_main, "get_all_open_issues") else None
    rows = conn.execute("SELECT * FROM issue_log WHERE run_id=?", (run_id,)).fetchall()
    assert any("task_focus_force_resume_unresolved_task_1_1" == r["topic"] for r in rows)


def test_force_resume_noop_when_stack_empty(db_conn):
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._force_resume_forward_focus(state)
    assert state["current_task_id"] == "task_2_1"


# ============================================================
# 3. _apply_joint_focus / _maybe_clear_resolved_companion / _get_task_focus_companion_text
# ============================================================

def test_apply_joint_focus_sets_companion_without_touching_current_task(db_conn):
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_joint_focus(state, {
        "companion_task_id": "task_1_1", "companion_phase_id": "phase_1",
        "reason": "依存関係", "baseline_agreement_id": "",
    })
    assert state["current_task_id"] == "task_2_1"  # 不変
    companion = state["task_focus_companion"]
    assert companion["companion_task_id"] == "task_1_1"
    assert companion["primary_task_id"] == "task_2_1"


def test_bug6_companion_does_not_clear_immediately_when_already_completed_at_declare(db_conn):
    """【バグ⑥回帰テスト】宣言時点で既にcompleted状態のcompanionを設定しても、
    _maybe_clear_resolved_companionが即座にクリアしないこと（baseline比較が効いている）。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_joint_focus(state, {
        "companion_task_id": "task_1_1", "companion_phase_id": "phase_1",
        "reason": "既に承認済みだが関連あり", "baseline_agreement_id": agreement_id,
    })
    cela_main._maybe_clear_resolved_companion(state, conn, run_id)
    assert state["task_focus_companion"] is not None  # まだクリアされない


def test_companion_clears_once_new_deliverable_approved(db_conn):
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_joint_focus(state, {
        "companion_task_id": "task_1_1", "companion_phase_id": "phase_1",
        "reason": "依存関係", "baseline_agreement_id": agreement_id,
    })
    _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved", seq=2)
    cela_main._maybe_clear_resolved_companion(state, conn, run_id)
    assert state["task_focus_companion"] is None


def test_get_task_focus_companion_text_mentions_supersede(db_conn):
    """joint_focus中にExpertが併記タスクを直そうとする場合のSUPERSEDE注意（ケースF）。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    state["task_focus_companion"] = {
        "companion_task_id": "task_1_1", "companion_phase_id": "phase_1",
        "primary_task_id": "task_2_1", "reason": "r", "declared_at_round": 1, "baseline_agreement_id": "",
    }
    text = cela_main._get_task_focus_companion_text(state)
    assert "task_1_1" in text
    assert "SUPERSEDE" in text


def test_get_task_focus_companion_text_empty_when_unset():
    state = {"task_focus_companion": None}
    assert cela_main._get_task_focus_companion_text(state) == ""


# ============================================================
# 4. _build_task_focus_state_text / _build_task_focus_transition_notice
# ============================================================

def test_build_task_focus_state_text_reflects_stack_and_companion():
    state = {
        "current_task_id": "task_1_1",
        "task_focus_stack": [{"task_id": "task_2_1", "reason": "テスト理由", "phase_id": "phase_2",
                               "pushed_at_round": 1, "focused_task_id": "task_1_1", "baseline_agreement_id": ""}],
        "task_focus_companion": {"companion_task_id": "task_5_1", "primary_task_id": "task_3_1", "reason": "併記理由"},
    }
    text = cela_main._build_task_focus_state_text(state)
    assert "task_1_1" in text
    assert "task_2_1" in text
    assert "task_5_1" in text


def test_build_task_focus_state_text_empty_when_nothing_set():
    state = {"task_focus_stack": [], "task_focus_companion": None}
    assert cela_main._build_task_focus_state_text(state) == ""


def test_transition_notice_one_shot_consumption():
    state = {"task_focus_redirect_notice": "テスト通知", "task_focus_resume_notice": ""}
    text = cela_main._build_task_focus_transition_notice(state)
    assert "テスト通知" in text
    assert state["task_focus_redirect_notice"] == ""
    assert cela_main._build_task_focus_transition_notice(state) == ""


# ============================================================
# 5. decision_extractor_node 統合（構造化決定の優先・target_roleガード・one-shot消費）
# ============================================================

def _de_state(run_id: str, chat_last_role: str, phases=None) -> dict:
    phases = phases if phases is not None else _PHASES
    return {
        "run_id": run_id, "phases": phases,
        "current_phase": phases[1], "current_task_id": "task_2_1",
        "chat_history": [{"role": chat_last_role, "content": "テスト発言"}],
        "round_count": 1, "constraint_issue_log": [],
        "task_focus_stack": [], "task_focus_companion": None,
        "task_focus_redirect_count": 0, "task_focus_redirect_notice": "", "task_focus_resume_notice": "",
        "pending_task_redirect": None,
    }


def test_structured_redirect_takes_priority_over_freetext_transition(db_conn, monkeypatch):
    """構造化決定（pending_task_redirect）が、call_decision_extractorが返す自由文脈の
    advances_to_task_idより優先されること。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _de_state(run_id, "user")
    state["pending_task_redirect"] = {
        "decision_type": "redirect_backward", "target_task_id": "task_1_1",
        "target_phase_id": "phase_1", "reason": "テスト", "baseline_agreement_id": agreement_id,
    }

    def _fake_extractor(*a, **k):
        # 自由文脈側は矛盾する遷移（task_2_1のまま）を返すが、構造化決定が優先されるはず
        return [], {"advances_to_task_id": None, "advances_to_phase_id": None}

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_extractor)
    result = cela_main.decision_extractor_node(state)
    assert result["current_task_id"] == "task_1_1"
    # one-shot消費: 次に呼んでも再適用されない
    assert result.get("pending_task_redirect") is None


def test_pending_task_redirect_not_consumed_on_expert_turn(db_conn, monkeypatch):
    """【バグ④/独立レビュー指摘6-3回帰テスト】target_role=="expert"（chat_history末尾がassistant）
    の場合、pending_task_redirectがセットされていても消費・適用されないこと。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _de_state(run_id, "assistant")
    state["pending_task_redirect"] = {
        "decision_type": "redirect_backward", "target_task_id": "task_1_1",
        "target_phase_id": "phase_1", "reason": "テスト", "baseline_agreement_id": agreement_id,
    }

    def _fake_extractor(*a, **k):
        return [], {"advances_to_task_id": None, "advances_to_phase_id": None}

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_extractor)
    result = cela_main.decision_extractor_node(state)
    assert result["current_task_id"] == "task_2_1"  # redirectは適用されない


def test_joint_focus_structured_decision_continues_freetext_logic(db_conn, monkeypatch):
    """joint_focusはcurrent_task_idを変えないため、その後の自由文脈遷移ロジックが
    そのまま続行されること（構造化決定後もreturnしない）。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _de_state(run_id, "user")
    state["pending_task_redirect"] = {
        "decision_type": "joint_focus", "companion_task_id": "task_1_1",
        "companion_phase_id": "phase_1", "reason": "テスト", "baseline_agreement_id": "",
    }

    def _fake_extractor(*a, **k):
        return [], {"advances_to_task_id": None, "advances_to_phase_id": None}

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_extractor)
    result = cela_main.decision_extractor_node(state)
    assert result["task_focus_companion"]["companion_task_id"] == "task_1_1"
    assert result["current_task_id"] == "task_2_1"  # 変わらない


# ============================================================
# 6. scheduling_drafts CRUD / _build_stale_past_tasks_text / _build_scheduling_history_text
# ============================================================

def test_scheduling_drafts_crud_round_trip(db_conn):
    conn, run_id = db_conn
    assert cela_main.get_latest_scheduling_decision(conn, run_id) is None
    v1 = cela_main.record_scheduling_decision(conn, run_id, "redirect_backward", "task_2_1", "phase_2", "", "", "理由A", "user")
    assert v1 == 1
    v2 = cela_main.record_scheduling_decision(conn, run_id, "joint_focus", "task_3_1", "phase_3", "task_1_1", "phase_1", "理由B", "user")
    assert v2 == 2
    latest = cela_main.get_latest_scheduling_decision(conn, run_id)
    assert latest["version"] == 2
    assert latest["decision_type"] == "joint_focus"
    history = cela_main.get_scheduling_decision_history(conn, run_id)
    assert len(history) == 2
    assert history[0]["version"] == 2  # 新しい順


def test_build_stale_past_tasks_text_lists_open_bl163_issues(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "goal_revision_consistency_check_phase_1_task_1_1",
         "severity": "minor", "description": "ゴール改定により再確認が必要"},
        conn, run_id, "revise_goal_auto", "phase_1", "task_1_1",
    )
    text = cela_main._build_stale_past_tasks_text(conn, run_id)
    assert "task_1_1" in text
    assert "redirect_backward" in text


def test_build_stale_past_tasks_text_empty_when_none_open(db_conn):
    conn, run_id = db_conn
    assert cela_main._build_stale_past_tasks_text(conn, run_id) == ""


def test_build_scheduling_history_text(db_conn):
    conn, run_id = db_conn
    assert cela_main._build_scheduling_history_text(conn, run_id) == ""
    cela_main.record_scheduling_decision(conn, run_id, "redirect_backward", "task_2_1", "phase_2", "", "", "理由A", "user")
    text = cela_main._build_scheduling_history_text(conn, run_id)
    assert "redirect_backward" in text


# ============================================================
# 7. BL-190 × BL-191 結合テスト（バグ②：フォーカス中タスクが再構成で消失）
# ============================================================

def test_bug2_reconcile_force_resumes_when_focused_task_vanishes_mid_redirect(db_conn, monkeypatch):
    """【バグ②回帰テスト】redirect_backward中に、フォーカス中のtask_idを含まない新phasesで
    task_planner_node（BL-190のパターン3経路）が走った場合、task_focus_stackが永久に残らず
    強制popで元のフォワードタスクへ復帰すること。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    state["goal"] = "テスト目標"
    state["turn_count"] = 5
    state["plan_revision_reason"] = "task_plan_reviewerの指摘による全体再編"
    state["plan_review_done"] = True
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    assert state["current_task_id"] == "task_1_1"

    # 新計画からtask_1_1（フォーカス中の過去タスク）自体が消える
    new_phases = [{"phase_id": "phase_9", "title": "新規", "tasks": [
        {"task_id": "task_9_9", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: new_phases)

    result = cela_main.task_planner_node(state)

    # フォーカス中タスク（task_1_1）・復帰先（task_2_1）の両方が新計画から消える二重消失
    # パターン。_force_resume_forward_focus自体もresume_phaseを解決できずスタックのみ
    # クリアするため、_reconcile_current_phase_after_replanが「真の削除・統合」処理へ
    # フォールスルーし、current_task_idを確実にクリアする（無効なtask_idに張り付いたまま
    # 残り続ける事故を防ぐ）。
    assert result["task_focus_stack"] == []
    assert result["current_task_id"] == ""
    assert "task_1_1" in result["task_reassigned_after_replan_notice"]


def test_bug2_reconcile_force_resumes_to_surviving_forward_task(db_conn, monkeypatch):
    """フォーカス中の過去タスクは消えるが、復帰先のフォワードタスクは新計画にも残っている場合、
    正しくそちらへ復帰できること。"""
    conn, run_id = db_conn
    agreement_id = _insert_deliverable(conn, run_id, "phase_1", "task_1_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    state["goal"] = "テスト目標"
    state["turn_count"] = 5
    state["plan_revision_reason"] = "task_plan_reviewerの指摘による全体再編"
    state["plan_review_done"] = True
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "r", "baseline_agreement_id": agreement_id,
    })
    assert state["current_task_id"] == "task_1_1"

    # task_1_1（フォーカス中）は消えるが、task_2_1（復帰先）は新計画にも存在する
    new_phases = [{"phase_id": "phase_5", "title": "新規", "tasks": [
        {"task_id": "task_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: new_phases)

    result = cela_main.task_planner_node(state)

    assert result["task_focus_stack"] == []
    assert result["current_task_id"] == "task_2_1"
    assert result["current_phase"]["phase_id"] == "phase_5"


def test_no_interaction_when_stack_empty_normal_replan_unaffected(db_conn, monkeypatch):
    """task_focus_stackが空の通常の計画再構成では、BL-190の既存挙動が非退行であること。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    state["goal"] = "テスト目標"
    state["turn_count"] = 5
    state["plan_revision_reason"] = "通常の再構成"
    state["plan_review_done"] = True
    new_phases = [
        {"phase_id": "phase_1", "title": "新規", "tasks": [{"task_id": "task_1_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []}]},
        {"phase_id": "phase_2", "title": "新規", "tasks": [{"task_id": "task_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []}]},
    ]
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: new_phases)
    result = cela_main.task_planner_node(state)
    assert result["current_task_id"] == "task_2_1"
    assert result["current_phase"]["phase_id"] == "phase_2"
