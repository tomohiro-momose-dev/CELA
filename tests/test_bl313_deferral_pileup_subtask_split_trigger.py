"""
BL-313: 先送り（defer_to_task_id）が特定タスクへ集中した場合、サブタスク分解の検討を
task_plannerへ促す。

ユーザー報告: task_5_1にdefer_to_task_idが20件集中していることが判明（全てseverity='minor'/
status='open'）。実DBを確認したところtask_3_2・task_5_5も閾値ちょうど5件で同時に
オーバーロードしていた。既存のBL-233（`_get_overloaded_defer_targets`）は検知はするが、
実ログでは123回警告を出すだけで何も是正していなかった。

当初「BL-233の対象をstatus='open'へ拡張すればBL-145の停滞トリガーが自然に反応する」という
軽量案を検討したが、調査の結果これは誤りだったと判明した——BL-145の停滞判定チェーン
（reflection_node）は`_get_escalated_issues()`（status='escalated'限定）が起点であり、
status='open'の行はどんな条件でも到達しない。そこで、BL-145が使う土台（plan_revision_reason/
plan_revision_issue_ids/_mark_issue_planned、task_planner_nodeの再発火ガード、
call_task_plannerのrevision_block注入）はそのまま再利用しつつ、独立した新しいトリガー条件
（BL-313）をreflection_nodeへ追加した。

ユーザーが依頼した別AIツールによる独立レビューで、(A)ログ出力の欠落、(B)変数名の実体との
不一致、(C)挿入位置がif _stale_escalated:ブロックの内側になるリスク、(D)_mark_issue_planned
のdefer_to_task_id上書きによる誤誘導、(E)複数ターゲット同時発火が実DBで確認済み、の指摘を
受け、いずれも実コード再読・実DB再クエリで裏取りした上で設計に反映した。

参照: docs/design/back_log/issue_backlog.md BL-313、
      docs/design/back_log/BL-313/BL313_basic_design.md。
実LLM API呼び出しは伴わない（call_reflectionをmonkeypatchする）。
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
    db_path = str(tmp_path / "test_bl313.db")
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


PHASES_WITH_TARGETS = [
    {"phase_id": "phase_1", "title": "既存フェーズ", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_5_1", "acceptance_criteria": ["配車仕様を定義する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_3_2", "acceptance_criteria": ["車種を選定する"], "depends_on": [], "owns_variables": []},
        {"task_id": "task_5_5", "acceptance_criteria": ["冬季運行可否を判定する"], "depends_on": [], "owns_variables": []},
    ]},
]


def _create_open_issue_deferred(conn, run_id, topic, defer_to_task_id, phases=None):
    """severity='minor'（→status='open'）のissueを1件起票し、指定task_idへDEFERする。
    BL-233/BL-313が実際に見る「先送りが積み上がった状態」を最短で再現するヘルパー。"""
    phases = phases or PHASES_WITH_TARGETS
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "後続タスクで検証が必要な事項", "severity": "minor"},
        conn, run_id, "detector", "", "task_1_1",
    )
    result = cela_main._write_issue_impl(
        {"action_type": "DEFER", "topic": topic, "defer_to_task_id": defer_to_task_id, "defer_reason": "後で検証"},
        conn, run_id, "user", "", "task_1_1",
        state={"phases": phases},
    )
    assert result["success"] is True, result


def _reflection_base_state(run_id):
    return {
        "risk_register": [], "goal": "g", "run_id": run_id, "round_count": 1,
        "escalated_issue_first_seen_round": {}, "phases": PHASES_WITH_TARGETS,
    }


def _make_reflection_mock(monkeypatch):
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "順調に見える。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)


def test_bl313_fires_at_threshold_in_a_single_round(db_conn, monkeypatch):
    """BL-145と異なり、BL-313はラウンド滞留を要求しない——閾値到達で即座に発火する。"""
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_pileup_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))

    assert "[BL-313]" in state["plan_revision_reason"]
    assert "task_5_1" in state["plan_revision_reason"]
    assert len(state["plan_revision_issue_ids"]) == cela_main._DEFERRAL_PILEUP_THRESHOLD


def test_bl313_does_not_fire_below_threshold(db_conn, monkeypatch):
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD - 1):
        _create_open_issue_deferred(conn, run_id, f"bl313_below_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))

    assert state.get("plan_revision_reason", "") == ""
    assert state.get("plan_revision_issue_ids", []) == []


def test_bl313_handles_multiple_simultaneous_overloaded_targets(db_conn, monkeypatch):
    """[レビュー指摘E] 実DBで実際に確認された「3ターゲット同時オーバーロード」を再現する。"""
    conn, run_id = db_conn
    for i in range(5):
        _create_open_issue_deferred(conn, run_id, f"bl313_t521_{i}", "task_5_1")
    for i in range(6):
        _create_open_issue_deferred(conn, run_id, f"bl313_t521b_{i}", "task_5_1")  # 計11件
    for i in range(5):
        _create_open_issue_deferred(conn, run_id, f"bl313_t32_{i}", "task_3_2")
    for i in range(5):
        _create_open_issue_deferred(conn, run_id, f"bl313_t55_{i}", "task_5_5")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))

    for target in ("task_5_1", "task_3_2", "task_5_5"):
        assert target in state["plan_revision_reason"]
    assert len(state["plan_revision_issue_ids"]) == 11 + 5 + 5


def test_bl313_does_not_force_discussion_status_to_stagnant(db_conn, monkeypatch):
    """[レビュー指摘・設計方針] BL-145と異なり、BL-313は「滞留」ではなく「受け皿の偏り」を
    扱うため、discussion_statusをstagnantへ上書きしない。"""
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_nostagnant_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))

    assert "[BL-313]" in state["plan_revision_reason"]
    assert state["discussion_status"] == "continuing"  # モックの返り値のまま変化しない


def test_bl313_does_not_overwrite_existing_plan_revision_reason(db_conn, monkeypatch):
    """first-write-wins: BL-145等が既にplan_revision_reasonを確保していればBL-313は譲る。"""
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_collision_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id)
    state["plan_revision_reason"] = "task_plan_reviewerによる差し戻し"
    state = cela_main.reflection_node(state)

    assert state["plan_revision_reason"] == "task_plan_reviewerによる差し戻し"
    assert state.get("plan_revision_issue_ids", []) == []


def test_bl313_yields_to_bl145_when_both_conditions_true_in_same_round(db_conn, monkeypatch):
    """[設計方針: 優先順位] 同一のreflection_node呼び出し内でBL-145（滞留escalated）と
    BL-313（先送り集中）が両方"新規に"成立する場合、コード順序上BL-145が先に
    plan_revision_reasonを確保する。

    [注意] 先送り集中issueを最初から用意すると、BL-313はラウンド滞留を要求しないため
    1回目の呼び出し（round=1、escalated issueはまだ非stale）で先に発火してしまい、
    2回目の呼び出し時点では既にplan_revision_reasonが埋まっているため「同一ラウンドでの
    競合」を検証できない。escalated issueだけを先に3ラウンド滞留させ、pileup issueは
    2回目の呼び出し直前に作ることで、両条件が同一呼び出し内で初めて同時に真になる状況を
    再現する。"""
    conn, run_id = db_conn
    # BL-145側: escalated（major）issueを先に起票し、3ラウンド滞留させる。
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "bl313_vs_bl145_escalated", "description": "重大な懸念", "severity": "major"},
        conn, run_id, "detector", "", "task_1_1",
    )
    _make_reflection_mock(monkeypatch)

    state = _reflection_base_state(run_id)
    state = cela_main.reflection_node(state)  # round=1、初観測（pileupはまだ無いのでBL-313は不発）
    assert state.get("plan_revision_reason", "") == ""

    # BL-313側: ここで初めて先送り集中を用意する。
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_vs_bl145_pileup_{i}", "task_5_1")

    state["round_count"] = 4  # escalated issueは3ラウンド経過（stale）、pileupも今回初めて閾値到達
    state = cela_main.reflection_node(state)

    assert "[BL-145]" in state["plan_revision_reason"]
    assert "[BL-313]" not in state["plan_revision_reason"]
    assert state["discussion_status"] == "stagnant"  # BL-145が上書きした結果


def test_bl313_planned_status_naturally_prevents_retrigger(db_conn, monkeypatch):
    """[§17.1相当の設計確認] task_planner_node相当の事後処理（_mark_issue_planned）を
    適用すると、対象issueはstatus='planned'となりCOUNTクエリから外れ、閾値を割って
    再発火しなくなること（追加コードなしで冪等性が成立する設計であることの確認）。"""
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_idempotent_{i}", "task_5_1")

    assert cela_main._get_overloaded_defer_targets(conn, run_id) == {"task_5_1"}

    ids = [
        r["id"] for r in conn.execute(
            "SELECT id FROM issue_log WHERE run_id=? AND defer_to_task_id='task_5_1'", (run_id,)
        ).fetchall()
    ]
    for issue_id in ids:
        assert cela_main._mark_issue_planned(conn, run_id, issue_id, embedded_task_ids=["task_5_1_1"]) is True

    assert cela_main._get_overloaded_defer_targets(conn, run_id) == set()


def test_bl313_reflection_node_end_to_end_then_task_planner_node_marks_planned(db_conn, monkeypatch):
    """[統合] reflection_nodeがBL-313を発火→task_planner_nodeが実際にissueをplanned化する
    まで、既存のBL-145用post-processing（汎用パス）が変更なしで機能することを確認する。"""
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_e2e_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))
    assert len(state["plan_revision_issue_ids"]) == cela_main._DEFERRAL_PILEUP_THRESHOLD

    split_phases = [
        {"phase_id": "phase_1", "tasks": [
            {"task_id": "task_5_1_1", "acceptance_criteria": []},
            {"task_id": "task_5_1_2", "acceptance_criteria": []},
        ]},
    ]
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: split_phases)

    tp_state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": PHASES_WITH_TARGETS,
        "plan_revision_reason": state["plan_revision_reason"],
        "plan_revision_issue_ids": state["plan_revision_issue_ids"],
        "plan_review_done": True, "round_count": 1,
    }
    result = cela_main.task_planner_node(tp_state)

    assert result["plan_revision_issue_ids"] == []
    for issue_id in state["plan_revision_issue_ids"]:
        row = conn.execute("SELECT status, defer_to_task_id FROM issue_log WHERE id=?", (issue_id,)).fetchone()
        assert row["status"] == "planned"
        assert row["status"] != "resolved"


def test_bl313_reason_text_mentions_subtask_split_suggestion(db_conn, monkeypatch):
    conn, run_id = db_conn
    for i in range(cela_main._DEFERRAL_PILEUP_THRESHOLD):
        _create_open_issue_deferred(conn, run_id, f"bl313_wording_{i}", "task_5_1")
    _make_reflection_mock(monkeypatch)

    state = cela_main.reflection_node(_reflection_base_state(run_id))

    assert "サブタスク" in state["plan_revision_reason"]
    assert "分割" in state["plan_revision_reason"]
    # ユーザー指定の命名例（task_5_1_1等）が例示として含まれること
    assert "_1" in state["plan_revision_reason"]
