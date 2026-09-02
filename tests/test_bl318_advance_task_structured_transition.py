"""
BL-318: schedule_task_focusへ`advance_task`を追加し、通常タスク遷移を構造化ツールで確定させる。

実インシデント: ライブラン（run_id=1787890406-1e73a89d）で、BL-313による自動サブタスク分割
（task_3_2 → task_3_2_1/task_3_2_2）後、BL-190の「真の削除」分岐がcurrent_task_idを
クリアし復帰通知を注入したが、User AIの復帰発言は`call_decision_extractor`
（cela_main.py:13697-13700）の「単なるレビューは移行に該当しない」という除外条件に
該当してしまい、current_task_idが3時間以上'task_1_1'（フォールバック値）のまま更新されず、
14件のagreementが誤帰属した。

対応: decision_extractorの定性判断は残しつつ（フォールバックとして温存）、BL-191の
schedule_task_focus／structured_redirect優先ロジックへ新しいdecision_type="advance_task"を
追加し、通常の順方向タスク遷移を構造化ツールで確定的に記録できるようにした。
_resolve_task_transitionのBL-125/176/255ゲート・task_id正規化・フェーズ横断探索は
一切複製せず自由文脈経路と共用する。

独立レビュー（BL318_review.md）の指摘を反映済み:
- C-1: `_schedule_task_focus_tool_impl`のadvance_task分岐は、_effective_current_task_id_from
  （BL-190リコンサイル後はフォールバック値を返す）ではなく生のcurrent_task_idを使う。
- I-1: ツールdescriptionとStage4プロンプトの「必ず呼べ」指示の矛盾を解消。
- I-2: BL-190復帰通知の消費を、schedule_task_focusツールを持つStage4専用の
  `_build_task_reassigned_notice`へ分離（`_build_task_transition_blocked_notice`から独立）。

参照: docs/design/back_log/issue_backlog.md BL-318、
      docs/design/back_log/BL-318/BL318_basic_design.md。
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
    db_path = str(tmp_path / "test_bl318.db")
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
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1", "depends_on": []}]},
    {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1", "depends_on": ["task_1_1"]}]},
    {
        "phase_id": "phase_3",
        "tasks": [
            {"task_id": "task_3_2_1", "depends_on": ["task_2_1"]},
            {"task_id": "task_3_2_2", "depends_on": ["task_3_2_1"]},
        ],
    },
]


def _base_state(run_id: str, current_task_id: str = "task_2_1", phases=None, current_phase_override=None) -> dict:
    phases = phases if phases is not None else _PHASES
    current_phase = current_phase_override
    if current_phase is None:
        current_phase = next(
            (p for p in phases for t in p.get("tasks", []) if t["task_id"] == current_task_id), phases[0]
        )
    return {
        "run_id": run_id, "phases": phases, "current_phase": current_phase,
        "current_task_id": current_task_id, "round_count": 1,
        "task_focus_stack": [], "task_focus_companion": None,
        "task_focus_redirect_count": 0,
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "",
        "task_transition_blocked_unmet_deps_task_id": "",
        "task_transition_blocked_unmet_deps": [],
    }


def _insert_deliverable(conn, run_id, phase_id, task_id, status, seq=1):
    agreement_id = f"AG-TEST-{task_id}-{seq:03d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE" if seq == 1 else "UPDATE", status, f"{task_id}の成果物", "X" * 300, "r",
         "expert", "Deliverable", phase_id, task_id, "[]", "{}", time.time() + seq, "", 0, None, run_id),
    )
    conn.commit()
    return agreement_id


# ============================================================
# 1. _schedule_task_focus_tool_impl のadvance_task分岐
# ============================================================

def test_advance_task_success_records_raw_current_task_id(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_2_1", "reason": "次工程へ"},
        conn, run_id, "user", state,
    )
    assert result["success"] is True
    decision = cela_main.get_last_scheduling_decision()
    assert decision["decision_type"] == "advance_task"
    assert decision["target_task_id"] == "task_2_1"
    assert decision["target_phase_id"] == "phase_2"
    row = conn.execute(
        "SELECT primary_task_id FROM scheduling_drafts WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)
    ).fetchone()
    assert row["primary_task_id"] == "task_1_1"


def test_advance_task_does_not_require_existing_deliverable(db_conn):
    """redirect_backwardと異なり、advance_taskは未着手タスク（Deliverable無し）への
    通常遷移を許可する（自由文脈経路と同じ挙動）。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_2_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is True


def test_advance_task_rejects_nonexistent_target(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_9_9", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "存在しません" in result["error"]


def test_advance_task_rejects_same_as_raw_current_task_id(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_1_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "同一" in result["error"]


def test_advance_task_uses_raw_current_task_id_not_fallback_c1_regression(db_conn):
    """[独立レビュー指摘C-1回帰] BL-190リコンサイル直後を模した状態
    （current_task_id=""、current_phase=phases[0]）では、_effective_current_task_id_fromは
    phases[0]の先頭タスク（task_1_1）へフォールバックする。advance_taskがこの実効値ではなく
    生のcurrent_task_id("")を使うことで、
    (a) target_task_idがたまたまtask_1_1と一致しても「現在タスクと同一」と誤って拒否されず、
    (b) scheduling_drafts.primary_task_idがフォールバック値ではなく生の値（空文字）で
        記録されることを確認する。ここを実効値のまま実装すると、BL-146/BL-211と同型の
        誤帰属をこのツール自身が再生産する。
    """
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="", current_phase_override=_PHASES[0])
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_1_1", "reason": "再計画後の復帰"},
        conn, run_id, "user", state,
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT primary_task_id FROM scheduling_drafts WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)
    ).fetchone()
    assert row["primary_task_id"] == ""


def test_advance_task_rejects_when_task_focus_stack_nonempty(db_conn):
    """[独立レビュー指摘M-2] redirect_backward中にadvance_taskでcurrent_task_idを動かすと、
    一時中断中のフォワードタスクとの対応関係が壊れるため拒否する。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    state["task_focus_stack"] = [{"task_id": "task_2_1", "phase_id": "phase_2"}]
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_3_2_1", "reason": "r"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False
    assert "force_resume" in result["error"]
    assert state["task_focus_stack"]  # 変更されていない


def test_advance_task_rejects_non_user_role(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_2_1", "reason": "r"},
        conn, run_id, "expert", state,
    )
    assert result["success"] is False
    assert "user" in result["error"]


def test_advance_task_requires_reason(db_conn):
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_1_1")
    result = cela_main._schedule_task_focus_tool_impl(
        {"decision_type": "advance_task", "target_task_id": "task_2_1"},
        conn, run_id, "user", state,
    )
    assert result["success"] is False


# ============================================================
# 2. _resolve_task_transition: advance_taskがBL-125/176/255ゲートを共用すること
# ============================================================

def test_resolve_task_transition_advance_task_blocked_by_bl125(db_conn):
    conn, run_id = db_conn
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl318_block_a", "description": "懸念", "severity": "major"},
        conn, run_id, "detector", "phase_2", "task_2_1",
    )
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state, {},
        structured_redirect={"decision_type": "advance_task", "target_task_id": "task_3_2_1", "target_phase_id": "phase_3"},
    )
    assert state["current_task_id"] == "task_2_1"  # 更新されていない
    assert "bl318_block_a" in state["task_transition_blocked_issue_topics"]


def test_resolve_task_transition_advance_task_blocked_by_bl176(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Proposed")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state, {},
        structured_redirect={"decision_type": "advance_task", "target_task_id": "task_3_2_1", "target_phase_id": "phase_3"},
    )
    assert state["current_task_id"] == "task_2_1"
    assert state["task_transition_blocked_unapproved_task_id"] == "task_2_1"


def test_resolve_task_transition_advance_task_blocked_by_bl255(db_conn):
    """target_task_id='task_3_2_2'のdepends_on=['task_3_2_1']が未完了のためブロックされる。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state, {},
        structured_redirect={"decision_type": "advance_task", "target_task_id": "task_3_2_2", "target_phase_id": "phase_3"},
    )
    assert state["current_task_id"] == "task_2_1"
    assert state["task_transition_blocked_unmet_deps_task_id"] == "task_3_2_2"
    assert "task_3_2_1" in state["task_transition_blocked_unmet_deps"]


def test_resolve_task_transition_advance_task_success_updates_task_and_phase(db_conn):
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state, {},
        structured_redirect={"decision_type": "advance_task", "target_task_id": "task_3_2_1", "target_phase_id": "phase_3"},
    )
    assert state["current_task_id"] == "task_3_2_1"
    assert state["current_phase"]["phase_id"] == "phase_3"


def test_resolve_task_transition_advance_task_priority_over_conflicting_freetext(db_conn):
    """structured_redirect(advance_task)が、矛盾する自由文脈transitionより優先されること。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state,
        {"advances_to_phase_id": "phase_1", "advances_to_task_id": "task_1_1"},  # 矛盾する自由文脈側
        structured_redirect={"decision_type": "advance_task", "target_task_id": "task_3_2_1", "target_phase_id": "phase_3"},
    )
    assert state["current_task_id"] == "task_3_2_1"  # 構造化側が優先


def test_resolve_task_transition_advance_task_empty_target_is_noop(db_conn):
    """[独立レビュー指摘M-1] target_task_idが空で来た場合（本来は_schedule_task_focus_tool_impl
    側のバリデーションで発生しないはずだが）、既存の自由文脈経路と同じく無音no-opする。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._resolve_task_transition(
        state, {},
        structured_redirect={"decision_type": "advance_task", "target_task_id": "", "target_phase_id": None},
    )
    assert state["current_task_id"] == "task_2_1"


# ============================================================
# 3. decision_extractor_node 統合: BL-190復帰インシデントの回帰テスト
# ============================================================

def _de_state(run_id: str, chat_last_role: str, current_task_id: str = "task_2_1", current_phase=None, phases=None) -> dict:
    phases = phases if phases is not None else _PHASES
    if current_phase is None:
        current_phase = next(
            (p for p in phases for t in p.get("tasks", []) if t["task_id"] == current_task_id), phases[0]
        )
    return {
        "run_id": run_id, "phases": phases,
        "current_phase": current_phase, "current_task_id": current_task_id,
        "chat_history": [{"role": chat_last_role, "content": "テスト発言"}],
        "round_count": 1, "constraint_issue_log": [],
        "task_focus_stack": [], "task_focus_companion": None,
        "task_focus_redirect_count": 0, "task_focus_redirect_notice": "", "task_focus_resume_notice": "",
        "pending_task_redirect": None,
    }


def test_decision_extractor_node_advance_task_resolves_bl190_recovery(db_conn, monkeypatch):
    """[BL-318 本体の回帰テスト] 実インシデントの再現: current_task_idがBL-190リコンサイルで
    クリアされphases[0]先頭タスクへフォールバックした状態から、User AIがschedule_task_focus
    (advance_task)を呼べば、decision_extractorの自由文脈抽出が「単なるレビュー」として
    空振りしても正しく後継タスクへ遷移できることを確認する。"""
    conn, run_id = db_conn
    _insert_deliverable(conn, run_id, "phase_2", "task_2_1", "Approved")
    state = _de_state(run_id, "user", current_task_id="", current_phase=_PHASES[0])
    state["pending_task_redirect"] = {
        "decision_type": "advance_task", "target_task_id": "task_3_2_1",
        "target_phase_id": "phase_3", "reason": "再計画後の復帰",
    }

    def _fake_extractor(*a, **k):
        # 自由文脈側は実インシデントと同じく「単なるレビュー」として抽出漏れした想定
        return [], {"advances_to_task_id": None, "advances_to_phase_id": None}

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake_extractor)
    result = cela_main.decision_extractor_node(state)
    assert result["current_task_id"] == "task_3_2_1"
    assert result["current_phase"]["phase_id"] == "phase_3"
    # one-shot消費: pending_task_redirectは消費済み
    assert result.get("pending_task_redirect") is None
