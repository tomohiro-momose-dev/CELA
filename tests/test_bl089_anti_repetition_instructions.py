"""
BL-089追記: task_planner（項目7、既存）に続き、python_repl/ツールループを持つ他の
全ノードにも「同じ検証・計算を繰り返さない」指示を追加する。

実ドライラン（`log/2026-07-25/1705`）で、task_plan_reviewerが同一の4観点レビューを
phase-by-phaseで3回以上ゼロから再導出し、MAX_TOOL_ITERの終盤を「念のため最終確認」の
繰り返しに浪費する様子を確認した。ユーザーの「他のノードも何回も何回も同じ思考を
繰り返しすぎることが多々ありました」との指摘を受け、tools=[...]でpython_repl等の
ツールアクセスを持つ全ノード（ツールループの反復・MAX_TOOL_ITER到達のリスクがある
ノード）に、同種の指示を追加した。tools=Noneの関数（call_orchestrator、
call_decision_extractor、call_reflection、call_facilitator）はツールループ自体を
持たないため対象外。

参照: docs/design/issue_backlog.md BL-089、docs/design/decision_log.md D-065。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_expert_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_expert)
    assert "同じ検証・計算を繰り返さない" in src


def test_call_detector_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_detector)
    assert "同じ計算を繰り返さない" in src


def test_call_resource_arbiter_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_resource_arbiter)
    assert "同じ検証・計算を繰り返さない" in src


def test_call_integrator_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_integrator)
    assert "同じ検証・計算を繰り返さない" in src


def test_call_reviewer_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_reviewer)
    assert "同じ検証・計算を繰り返さない" in src


def test_generate_user_utterance_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "同じ検証・計算を繰り返さない" in src


def test_call_goal_essence_analyst_has_anti_repetition_instruction():
    src = inspect.getsource(cela_main.call_goal_essence_analyst)
    assert "同じ検証・計算を繰り返さない" in src


def test_call_task_plan_reviewer_has_anti_repetition_instruction_and_single_block_rule():
    """task_plan_reviewerは、1705/1814ログの両方の実例（過剰な再検討・複数JSON
    ブロックの混在）を踏まえ、追加で「最終回答のJSONブロックは1つだけ」という
    指示も持つこと。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "同じ検証・計算を繰り返さない" in src
    assert "1つだけ" in src


def test_call_task_planner_still_has_its_own_anti_repetition_instruction():
    """既存のitem7（このBLの出発点）が引き続き存在すること（回帰確認）。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "繰り返し再確認しないでください" in src
