"""
BL-190: ラン途中の計画再構成後、current_task_id/current_phaseが不整合になる問題への対処。

実ドライラン（log/2026-08-07/2355）で、task_plan_reviewerの指摘によりtask_plannerが計画全体を
再構成した（phase_7をphase_2の位置へ移動、旧phase_2〜6をphase_3〜7へ繰り下げ）直後、
`_get_current_task`が「current_task_id='task_2_1'がcurrent_phaseのタスク一覧に見つかりません」
という警告を繰り返し出し、User AIのwrite_agreement(UPDATE)がBL-146ガードに拒否される事態を
発見した。原因は`task_planner_node`が初回計画・ラン途中の再構成いずれの場合も無条件に
`current_phase = phases[0]`へリセットする一方、`current_task_id`（BL-024の唯一の書き手は
_resolve_task_transition）には一切触れないため、フェーズの並び順・phase_idが変わる規模の
再構成では両者が不整合になっていた。

対応: `_reconcile_current_phase_after_replan`を新設し、新phases全体を線形探索して
current_task_idの実在場所へcurrent_phaseを追随させる。新旧phasesの差分パターンを3通り
（①加算のみ＝無害、②構造再編＝本件のバグ、③真の削除・統合＝current_task_idをクリアし
one-shot通知でUser AIへ再判断を促す）に分類して対応する。

参照: docs/design/back_log/issue_backlog.md BL-190、docs/design/back_log/BL-190/BL190_basic_design.md。
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
    db_path = str(tmp_path / "test_bl190.db")
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


_PHASE_1 = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}
_PHASE_2 = {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1"}, {"task_id": "task_2_2"}]}

# パターン2（構造再編）: task_2_1がphase_2からphase_3へ移動した新計画
_PHASE_1_NEW = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}
_PHASE_3_NEW = {"phase_id": "phase_3", "tasks": [{"task_id": "task_2_1"}, {"task_id": "task_2_2"}]}

# パターン3（真の削除・統合）: task_2_1が新計画のどこにも存在しない
_PHASE_1_REMOVED = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}
_PHASE_2_REMOVED = {"phase_id": "phase_2", "tasks": [{"task_id": "task_9_9"}]}


# --- _reconcile_current_phase_after_replan 単体テスト ---

def test_pattern0_no_current_task_id_falls_back_to_phases_zero():
    """current_task_idが未設定（初回計画）の場合は従来通りphases[0]を採用する（非退行）。"""
    state = {"current_task_id": "", "current_phase": {}}
    cela_main._reconcile_current_phase_after_replan(state, [_PHASE_1, _PHASE_2])
    assert state["current_phase"] == _PHASE_1
    assert state.get("task_reassigned_after_replan_notice", "") == ""


def test_pattern1_additive_only_same_phase_unaffected():
    """加算のみ（既存phase・taskは変更されず新規phaseが追加されるだけ）の場合、
    current_task_idが属するphaseの内容は変わらないため、無害に同じphaseへ追随する。"""
    state = {"current_task_id": "task_2_1", "current_phase": _PHASE_2}
    new_phases = [_PHASE_1, _PHASE_2, {"phase_id": "phase_7", "tasks": []}]
    cela_main._reconcile_current_phase_after_replan(state, new_phases)
    assert state["current_phase"] == _PHASE_2
    assert state["current_task_id"] == "task_2_1"


def test_pattern2_structural_reorg_follows_task_to_new_phase():
    """構造再編（本件のバグ）：current_task_idが新しいphase_idの下へ移動していても、
    current_phaseが正しくそちらへ追随すること。"""
    state = {"current_task_id": "task_2_1", "current_phase": _PHASE_2}
    new_phases = [_PHASE_1_NEW, _PHASE_3_NEW]
    cela_main._reconcile_current_phase_after_replan(state, new_phases)
    assert state["current_phase"]["phase_id"] == "phase_3"
    assert state["current_task_id"] == "task_2_1"


def test_pattern3_true_deletion_clears_current_task_id_and_sets_notice():
    """真の削除・統合：current_task_idが新計画のどこにも存在しない場合、
    current_phaseをphases[0]へ戻し、current_task_idをクリアし、one-shot通知をセットする。"""
    state = {"current_task_id": "task_2_1", "current_phase": _PHASE_2}
    new_phases = [_PHASE_1_REMOVED, _PHASE_2_REMOVED]
    cela_main._reconcile_current_phase_after_replan(state, new_phases)
    assert state["current_phase"] == _PHASE_1_REMOVED
    assert state["current_task_id"] == ""
    assert "task_2_1" in state["task_reassigned_after_replan_notice"]
    assert "廃止・統合" in state["task_reassigned_after_replan_notice"]


def test_pattern3_empty_phases_degrades_gracefully():
    """新phasesが空配列の極端なケースでもクラッシュしない。"""
    state = {"current_task_id": "task_2_1", "current_phase": _PHASE_2}
    cela_main._reconcile_current_phase_after_replan(state, [])
    assert state["current_phase"] == {}
    assert state["current_task_id"] == ""


# --- task_planner_node統合テスト（call_task_plannerをモック） ---

_EXISTING_PHASES_FOR_NODE = [
    {"phase_id": "phase_1", "title": "既存", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
    {"phase_id": "phase_2", "title": "既存", "tasks": [
        {"task_id": "task_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
]

_RESTRUCTURED_PHASES_FOR_NODE = [
    {"phase_id": "phase_1", "title": "再編後", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
    {"phase_id": "phase_3", "title": "再編後", "tasks": [
        {"task_id": "task_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
]


def test_task_planner_node_reconciles_current_phase_on_structural_reorg(db_conn, monkeypatch):
    """task_planner_nodeが計画全体を再編した際、current_task_id（phase_2のtask_2_1）が
    新しいphase_3へ移動していても、current_phaseが正しく追随すること（BL-190の再現テスト）。"""
    _, run_id = db_conn
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: _RESTRUCTURED_PHASES_FOR_NODE)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": _EXISTING_PHASES_FOR_NODE,
        "current_task_id": "task_2_1",
        "current_phase": _EXISTING_PHASES_FOR_NODE[1],
        "plan_revision_reason": "task_plan_reviewerの指摘による全体再編",
        "plan_review_done": True, "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert result["current_phase"]["phase_id"] == "phase_3"
    assert result["current_task_id"] == "task_2_1"


def test_task_planner_node_additive_reconfiguration_keeps_current_phase(db_conn, monkeypatch):
    """加算のみの再構成（BL-145/BL-186の典型パターン）では、current_phaseの内容が
    変わらないため非退行であること。"""
    _, run_id = db_conn
    additive_phases = _EXISTING_PHASES_FOR_NODE + [
        {"phase_id": "phase_7", "title": "新規", "tasks": [
            {"task_id": "task_7_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        ]},
    ]
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: additive_phases)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": _EXISTING_PHASES_FOR_NODE,
        "current_task_id": "task_2_1",
        "current_phase": _EXISTING_PHASES_FOR_NODE[1],
        "plan_revision_reason": "ゴール改定に伴う過去タスク再検証を追加",
        "plan_review_done": True, "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert result["current_phase"]["phase_id"] == "phase_2"
    assert result["current_task_id"] == "task_2_1"


# --- _build_task_transition_blocked_notice / _build_task_reassigned_notice ---
# [BL-318][独立レビュー指摘I-2] task_reassigned_after_replan_noticeの消費は、
# schedule_task_focusツールを持たないプロンプト経路でone-shotが無為に失われるのを防ぐため、
# _build_task_transition_blocked_noticeから_build_task_reassigned_noticeへ分離された。

def test_reassigned_notice_consumed_only_by_dedicated_function():
    state = {"task_reassigned_after_replan_notice": "[BL-190] テスト通知"}
    text = cela_main._build_task_reassigned_notice(state)
    assert "テスト通知" in text
    assert state["task_reassigned_after_replan_notice"] == ""
    # 二度目の呼び出しでは何も返さない（one-shot消費済み）
    assert cela_main._build_task_reassigned_notice(state) == ""


def test_blocked_notice_no_longer_touches_reassigned_notice():
    """[BL-318][独立レビュー指摘I-2] _build_task_transition_blocked_noticeは
    task_reassigned_after_replan_noticeを一切消費・参照しない（ツールを持たないプロンプト
    経路から呼ばれてもone-shotが失われないことの保証）。"""
    state = {"task_reassigned_after_replan_notice": "[BL-190] 消費されないはずの通知"}
    text = cela_main._build_task_transition_blocked_notice(state)
    assert text == ""
    assert state["task_reassigned_after_replan_notice"] == "[BL-190] 消費されないはずの通知"


def test_notice_bl125_and_bl176_flags_take_priority():
    """2つのフラグが同時にセットされることは実際には起きないが、優先順位（BL-125→BL-176）
    が意図通りであることを確認する。"""
    state = {
        "task_transition_blocked_issue_topics": ["issue_a"],
        "task_transition_blocked_unapproved_task_id": "task_x",
    }
    text = cela_main._build_task_transition_blocked_notice(state)
    assert "BL-125" in text
    assert state["task_transition_blocked_unapproved_task_id"] == "task_x"
