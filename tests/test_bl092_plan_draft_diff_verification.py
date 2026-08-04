"""
BL-092: task_plan_reviewerの差し戻し圧力に対し、task_plannerが数値の検算・訂正ではなく
該当箇所の削除・抽象化で「解消」してしまうパターンへの対策。

別AIによる`log/2026-07-25/1913`のログレビュー結果をさらに追跡した結果、reviewerが
指摘した数値矛盾（task_2_2の往復24km/48km混在、task_3_4の「約1,200万円」等）が、
実際には数値を検算して訂正したのではなく、該当するタスクの記述内容ごと削除するか
抽象的な表現に差し替えることで矛盾自体が計画から消滅していたことが判明した。
LLM（task_plan_reviewer）自身の記憶・印象に頼った「前回と比べてどう変わったか」の
判断では、こうした「検証せず消しただけ」のケースを見抜けない可能性が高い。

対策: task_planner_nodeは再生成のたびに全タスクのplan_draftsスケルトンを
author_role="task_planner"で版として積み増している（BL-082/BL-087 Stage2改善）ため、
同一task_idの直近2回のtask_planner版を機械的にdiffすれば「前回指摘した記述が
実際にどう変わったか」を客観的事実として確認できる。新規ツール
`diff_plan_draft_versions`をtask_plan_reviewerに追加し、記憶・印象ではなく
機械的diffに基づいて判断するよう指示した。

参照: docs/design/issue_backlog.md BL-092、docs/design/decision_log.md D-069。
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
    db_path = str(tmp_path / "test_bl092_diff.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        conn.close()


def _seed_task_planner_round(conn, run_id, task_id, description, criteria):
    task = {
        "task_id": task_id, "title": "テストタスク", "description": description,
        "acceptance_criteria": criteria, "depends_on": [], "owns_variables": [],
    }
    cela_main.apply_plan_patch(
        conn, run_id, "phase_2", task_id, cela_main._render_plan_skeleton(task),
        author_role="task_planner", edit_summary="計画生成",
    )


def test_diff_shows_deletion_not_correction(db_conn):
    """reviewerが指摘した具体的な数値記述が、訂正ではなく丸ごと削除されたケースで、
    diffが「該当行が消えた」ことを機械的に示すこと（今回のBL-092の核心シナリオ）。"""
    conn, run_id = db_conn
    _seed_task_planner_round(
        conn, run_id, "task_2_2",
        "往復24km（片道12kmの往復）を前提に輸送力を試算する。",
        ["片道約41分・サイクル約93分・輸送力約19人/台であること"],
    )
    _seed_task_planner_round(
        conn, run_id, "task_2_2",
        "エッジケースのフェールセーフ概念設計を行う。",
        ["異常時のフェールセーフ動作が定義されていること"],
    )
    result = cela_main._diff_plan_draft_versions_handler({"task_id": "task_2_2"})
    assert result["ok"] is True
    assert result["prev_version"] == 1
    assert result["latest_version"] == 2
    # 削除された行がdiffの"-"側に、新しい行が"+"側に出ること
    assert "-往復24km（片道12kmの往復）を前提に輸送力を試算する。" in result["diff"]
    assert "+エッジケースのフェールセーフ概念設計を行う。" in result["diff"]
    # 数値そのもの（19人/台等）が新版に「訂正」として追加された行（+行）は存在しない＝「消滅」
    added_lines = [line for line in result["diff"].splitlines() if line.startswith("+") and not line.startswith("+++")]
    assert not any("19人" in line for line in added_lines)


def test_diff_shows_actual_correction(db_conn):
    """数値が実際に検算・訂正された（記述自体は残り、値だけ変わった）ケースで、
    diffが変更箇所を示すこと。"""
    conn, run_id = db_conn
    _seed_task_planner_round(
        conn, run_id, "task_3_4",
        "購入2台＋リース1台の場合の赤字額は約1,200万円と試算する。",
        ["赤字額が補助金枠内であること"],
    )
    _seed_task_planner_round(
        conn, run_id, "task_3_4",
        "購入2台＋リース1台の場合の赤字額は約1,550万円と試算する。",
        ["赤字額が補助金枠内であること"],
    )
    result = cela_main._diff_plan_draft_versions_handler({"task_id": "task_3_4"})
    assert result["ok"] is True
    assert "-購入2台＋リース1台の場合の赤字額は約1,200万円と試算する。" in result["diff"]
    assert "+購入2台＋リース1台の場合の赤字額は約1,550万円と試算する。" in result["diff"]


def test_diff_insufficient_versions(db_conn):
    """task_planner版が1件しかない場合、ok=Falseで理由付きエラーを返すこと。"""
    conn, run_id = db_conn
    _seed_task_planner_round(conn, run_id, "task_1_1", "初回のみ", ["何か"])
    result = cela_main._diff_plan_draft_versions_handler({"task_id": "task_1_1"})
    assert result["ok"] is False
    assert "1件" in result["reason"]


def test_diff_unknown_task_id(db_conn):
    result = cela_main._diff_plan_draft_versions_handler({"task_id": "task_9_9"})
    assert result["ok"] is False


def test_diff_empty_task_id():
    result = cela_main._diff_plan_draft_versions_handler({"task_id": ""})
    assert result["ok"] is False


def test_diff_no_actual_change_reports_identical(db_conn):
    conn, run_id = db_conn
    _seed_task_planner_round(conn, run_id, "task_1_2", "同じ内容", ["同じ基準"])
    _seed_task_planner_round(conn, run_id, "task_1_2", "同じ内容", ["同じ基準"])
    result = cela_main._diff_plan_draft_versions_handler({"task_id": "task_1_2"})
    assert result["ok"] is True
    assert "差分はありません" in result["diff"]


def test_tool_registered_in_dispatch():
    assert "diff_plan_draft_versions" in cela_main.TOOL_DISPATCH
    direct = cela_main._diff_plan_draft_versions_handler({})
    via_dispatch = cela_main.TOOL_DISPATCH["diff_plan_draft_versions"]({})
    assert direct == via_dispatch


def test_call_task_plan_reviewer_wires_diff_tool_and_instruction():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "DIFF_PLAN_DRAFT_VERSIONS_TOOL" in src
    assert "diff_plan_draft_versions" in src
    assert "BL-092" in src
