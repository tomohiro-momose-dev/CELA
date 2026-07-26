"""
BL-095: `call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`への
`WRITE_AGREEMENT_TOOL`配線（読み書き非対称の解消）。

BL-094でこの3関数にread_verified_fact/read_deliverable_file（read専用）を配線したことで、
「他ノードの確定値は読めるが、自分自身の判断根拠を誰にも参照可能な形で書き残せない」という
読み書き非対称が生じていた。ユーザー指摘（「タスクプランナーの意図や理由は後続タスクで
見れるべき」）を受け、write_agreementを新規配線し、role×status許可表を拡張した。

- task_planner/goal_essence_analystはExpertと同様status='Proposed'限定
  （自らの計画・本質分析はあくまで提案であり、後続のtask_plan_reviewer/実行に覆されうるため）。
- task_plan_reviewerはDetector/Reviewer等と同じ監査役としてstatus='Rejected'限定
  （task_plannerの判断根拠に誤りがあればBL-062と同型のSUPERSEDEパターンで無効化する）。

参照: docs/design/issue_backlog.md BL-095、docs/design/decision_log.md（着手時に追記予定）。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import cela_main  # noqa: E402


# --- role x status 許可表の直接検証（DB接続不要の純粋関数） ---

def test_task_planner_can_write_proposed():
    args = {"status": "Proposed"}
    assert cela_main._check_write_permission(args, "task_planner") is None


@pytest.mark.parametrize("status", ["Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"])
def test_task_planner_cannot_write_other_statuses(status):
    args = {"status": status}
    error = cela_main._check_write_permission(args, "task_planner")
    assert error is not None
    assert "task_planner" in error


def test_goal_essence_analyst_can_write_proposed():
    args = {"status": "Proposed"}
    assert cela_main._check_write_permission(args, "goal_essence_analyst") is None


@pytest.mark.parametrize("status", ["Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"])
def test_goal_essence_analyst_cannot_write_other_statuses(status):
    args = {"status": status}
    error = cela_main._check_write_permission(args, "goal_essence_analyst")
    assert error is not None
    assert "goal_essence_analyst" in error


def test_task_plan_reviewer_can_write_rejected():
    args = {"status": "Rejected"}
    assert cela_main._check_write_permission(args, "task_plan_reviewer") is None


@pytest.mark.parametrize("status", ["Proposed", "Approved", "Approved_with_Conditions", "Implicitly_Accepted"])
def test_task_plan_reviewer_cannot_write_other_statuses(status):
    args = {"status": status}
    error = cela_main._check_write_permission(args, "task_plan_reviewer")
    assert error is not None
    assert "task_plan_reviewer" in error


# --- 各関数がWRITE_AGREEMENT_TOOLを実際にtools=[...]へ渡していることの確認 ---

@pytest.mark.parametrize("func_name", [
    "call_task_planner", "call_goal_essence_analyst", "call_task_plan_reviewer",
])
def test_functions_pass_write_agreement_tool(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "WRITE_AGREEMENT_TOOL" in src, f"{func_name} does not pass WRITE_AGREEMENT_TOOL in tools=[...]"


# --- 各関数が呼び出し前に_CURRENT_CALLER_ROLEを正しいロール名に設定していることの確認 ---

@pytest.mark.parametrize("func_name,expected_role", [
    ("call_task_planner", "task_planner"),
    ("call_goal_essence_analyst", "goal_essence_analyst"),
    ("call_task_plan_reviewer", "task_plan_reviewer"),
])
def test_functions_set_caller_role_before_query(func_name, expected_role):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert f'_CURRENT_CALLER_ROLE = "{expected_role}"' in src, (
        f"{func_name} does not set _CURRENT_CALLER_ROLE to {expected_role!r}"
    )


# --- プロンプト本文にBL-095のオリエンテーションが存在することの確認 ---

def test_task_planner_prompt_instructs_recording_decision_rationale():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-095" in src
    assert 'entry_type="Decision"' in src
    assert "task_planner_phase_design" in src


def test_goal_essence_analyst_prompt_mentions_optional_write_agreement():
    src = inspect.getsource(cela_main.call_goal_essence_analyst)
    assert "BL-095" in src
    assert "goal_essence_analysis" in src


def test_task_plan_reviewer_prompt_instructs_supersede_of_task_planner_rationale():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "BL-095" in src
    assert "task_planner_phase_design" in src
    assert "SUPERSEDE" in src


def test_write_agreement_tool_description_mentions_new_roles():
    description = cela_main.WRITE_AGREEMENT_TOOL["function"]["description"]
    assert "task_planner" in description
    assert "goal_essence_analyst" in description
    assert "task_plan_reviewer" in description
