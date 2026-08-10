"""
BL-126 Stage C: Task Plannerのラン途中再構成（`plan_revision_reason`）+ supersede機構。

従来のtask_planner_nodeは`turn_count==1 and not phases`のみで発火し、ラン途中で計画全体を
再構成する経路が存在しなかった。ガードを`(turn_count==1 and not phases) or
state.get("plan_revision_reason")`へ緩和し、影響を受けるタスクのみを見直させ、新しい計画に
含まれなくなった既存task_idは削除ではなく「supersede」として扱う（`phases_superseded`への
記録 + `write_agreement(entry_type="Directive", action_type="SUPERSEDE")`による監査証跡）。

[実装範囲についての注記] 本Stageはガード緩和・`call_task_planner`のexisting_phases/
revision_reason・supersede機構という「機構」の実装であり、テストはノード関数を直接
`state["plan_revision_reason"]`をセットして呼び出す形で検証する。ラン途中でこの機構を
実際に自動発火させる経路（Facilitator/Essence Dialogue収束後のトリガー、BL-126 Stage D）は、
Stage D（Facilitatorのツールループ化）で新設される見込みであり、現時点のグラフには
task_planner/task_plan_reviewerへ戻るエッジが（初回計画パス以外に）まだ存在しない。

参照: docs/design/back_log/issue_backlog.md BL-126、
      docs/design/back_log/BL-126/BL126_basic_design.md §6・§8・§11(3)。
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
    db_path = str(tmp_path / "test_bl126_stage_c.db")
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


EXISTING_PHASES = [
    {"phase_id": "phase_1", "title": "既存フェーズ", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_1_2", "acceptance_criteria": ["別の何かを確認する"], "depends_on": [], "owns_variables": []},
    ]},
]

RECONFIGURED_PHASES = [
    {"phase_id": "phase_1", "title": "既存フェーズ", "tasks": [
        # task_1_1は維持、task_1_2は新しい計画に含まれない（=supersede対象）、task_1_3を新規追加
        {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_1_3", "acceptance_criteria": ["新しい何かを確認する"], "depends_on": [], "owns_variables": []},
    ]},
]


def test_task_planner_node_does_not_fire_mid_run_without_revision_reason(db_conn, monkeypatch):
    """ラン途中（turn_count!=1）でも、plan_revision_reasonが無ければ何もしないこと
    （既存の初回計画ガードの安全な後方互換）。"""
    _, run_id = db_conn
    called = {"n": 0}
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    state = {"run_id": run_id, "goal": "テスト目標", "turn_count": 5, "phases": EXISTING_PHASES}
    result = cela_main.task_planner_node(state)

    assert called["n"] == 0
    assert result["phases"] == EXISTING_PHASES


def test_task_planner_node_reconfigures_mid_run_when_revision_reason_set(db_conn, monkeypatch):
    """plan_revision_reasonがセットされていれば、turn_count!=1・phases既存でも再発火し、
    call_task_plannerにexisting_phases/revision_reasonが渡ること。"""
    _, run_id = db_conn
    captured = {}

    def _fake_call_task_planner(goal, reviewer_feedback="", goal_essence_text="", state=None,
                                 existing_phases=None, revision_reason=""):
        captured["existing_phases"] = existing_phases
        captured["revision_reason"] = revision_reason
        return RECONFIGURED_PHASES

    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。

    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ

    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。

    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})

    monkeypatch.setattr(cela_main, "call_task_planner", _fake_call_task_planner)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "前提が変わったため", "plan_review_done": True,
        "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert captured["existing_phases"] == EXISTING_PHASES
    assert captured["revision_reason"] == "前提が変わったため"
    assert result["phases"] == RECONFIGURED_PHASES
    # 単発トリガーのため消費後は必ずクリアされること
    assert result["plan_revision_reason"] == ""
    assert result["plan_revision_count"] == 1


def test_task_planner_node_supersedes_removed_tasks_not_deletes(db_conn, monkeypatch):
    """新しい計画に含まれなくなった既存task_id（task_1_2）が、削除ではなく
    phases_supersededへ記録され、write_agreement(SUPERSEDE)の監査証跡が残ること。"""
    conn, run_id = db_conn
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: RECONFIGURED_PHASES)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "task_1_2は不要になった", "plan_review_done": True,
        "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert len(result["phases_superseded"]) == 1
    superseded = result["phases_superseded"][0]
    assert superseded["task_id"] == "task_1_2"
    assert superseded["phase_id"] == "phase_1"
    assert superseded["reason"] == "task_1_2は不要になった"

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    supersede_records = [a for a in agreements if a["action_type"] == "SUPERSEDE" and a["task_id"] == "task_1_2"]
    assert len(supersede_records) == 1
    assert supersede_records[0]["entry_type"] == "Directive"


def test_task_planner_node_reopens_plan_review_after_mid_run_reconfiguration(db_conn, monkeypatch):
    """ラン途中再構成後は、既存のtask_plan_reviewer_node実行前ゲートを再度通す
    （plan_review_done=Falseへリセットする、design.md §11(3)：スキップしない）。"""
    _, run_id = db_conn
    # [BL-204] task_planner_nodeはcall_task_plannerと同じガード内でseed_entities_from_goalも呼ぶ。
    # 実LLM呼び出しを伴うため、call_task_plannerと同様にスタブ化する（未スタブだと日次クォータ
    # 枯渇時に実ネットワーク呼び出しへ落ちてテストが壊れる）。
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: RECONFIGURED_PHASES)

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": EXISTING_PHASES, "plan_revision_reason": "前提が変わったため", "plan_review_done": True,
        "round_count": 4,
    }
    result = cela_main.task_planner_node(state)

    assert result["plan_review_done"] is False


def test_task_plan_reviewer_node_rerequests_revision_on_major_during_mid_run(db_conn, monkeypatch):
    """[design.md §11(3)] ラン途中（turn_count!=1）でtask_plan_reviewerがmajor判定した場合、
    turn_count==1ガードに依存するphases=[]だけでは再発火しないため、plan_revision_reasonを
    再セットして新設ガード経由で再発火させること。既存のplan_reviewer_retry_count上限
    （2回）ロジックはそのまま再利用され、新しい上限は追加しない。"""
    conn, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda *a, **k: {"risk": "medium", "constraint_issue": "major", "comment": "全体に矛盾あり", "per_task_comments": []},
    )

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": RECONFIGURED_PHASES, "plan_reviewer_retry_count": 0,
    }
    result = cela_main.task_plan_reviewer_node(state)

    assert result["phases"] == []
    assert result["plan_revision_reason"]  # 空でないこと（reviewerのフィードバックが入る）
    assert result["plan_reviewer_retry_count"] == 1


def test_task_plan_reviewer_node_does_not_set_revision_reason_on_initial_turn(db_conn, monkeypatch):
    """turn_count==1の初回計画パスでは、既存通りphases=[]のみで再発火する
    （plan_revision_reasonを不要にセットしない、既存経路への回帰がないことの確認）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda *a, **k: {"risk": "medium", "constraint_issue": "major", "comment": "全体に矛盾あり", "per_task_comments": []},
    )

    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 1,
        "phases": EXISTING_PHASES, "plan_reviewer_retry_count": 0,
    }
    result = cela_main.task_plan_reviewer_node(state)

    assert result["phases"] == []
    assert result.get("plan_revision_reason", "") == ""


def test_call_task_planner_includes_revision_block_when_revision_reason_given():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "existing_phases" in src
    assert "revision_reason" in src
    assert "revision_block" in src
