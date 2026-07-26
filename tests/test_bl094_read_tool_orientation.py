"""
BL-094: read_verified_fact/read_deliverable_fileの「オリエンテーション」不足対策。

BL-093で全ノードのプロンプトに「使えるツール名」を列挙したが、それだけでは
read_verified_fact/read_deliverable_fileが「何のためのツールか」「いつ使うべきか」を
モデルが理解できず、実ドライラン（log/2026-07-26/1749）で他タスクの確定値と矛盾する
数値を独自に仮定する事故（山間部片道時間が24分/36分で食い違う、「実現可能性メモ」という
AI自身の推測を出典扱いする等）が繰り返し観測された。

対策として、これら2ツールを持つ全6関数（call_expert/call_detector数値監査パス/
call_resource_arbiter/call_integrator/call_reviewer/generate_user_utterance）の
プロンプト本文に、(1)ツールの目的説明、(2)最低限iter=1で一度は呼び出し他タスクの
確定値と同期せよという思考フレームワーク上の指示、を追加した。

[BL-094追記] ユーザーから「call_task_planner／call_goal_essence_analyst／
call_task_plan_reviewerはそもそもread_verified_fact/read_deliverable_fileを持たない。
監査や差戻し時に呼び出せるように配線してほしい」との追加指示を受け、この3関数にも
READ_VERIFIED_FACT_TOOL/READ_DELIVERABLE_FILE_TOOLを配線し、同様のオリエンテーション
（目的説明＋iter=1同期指示）を追記した。特にcall_task_planner/call_task_plan_reviewerは
Task Plan Reviewerによる差し戻し→task_planner再分解のループを構成する関数であり、
実ドライラン1749で観測された「Goal Essence Analystが仮定した値をTask Plannerが
気づかず再度別の値で仮定し直す」循環参照バグの再発防止を狙う。call_goal_essence_analyst
は通常プロジェクト最初期に1回だけ呼ばれるため実質的な確定値はまだ存在しないことが
多いが、一貫性のため同様に配線した。

参照: docs/design/issue_backlog.md BL-094、docs/design/decision_log.md D-075。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest

import cela_main  # noqa: E402


# call_detector本体はnumeric passとdomain reviewの両方を含む1つの関数なので、
# BL-094の記述はnumeric pass側のブロックにのみ存在する（domain reviewはread_verified_fact/
# read_deliverable_fileを持たないため対象外）。他8関数は関数全体が対象。
_READ_TOOL_ORIENTED_FUNCS = [
    "call_expert",
    "call_detector",
    "call_resource_arbiter",
    "call_integrator",
    "call_reviewer",
    "generate_user_utterance",
    "call_task_planner",
    "call_goal_essence_analyst",
    "call_task_plan_reviewer",
]


@pytest.mark.parametrize("func_name", _READ_TOOL_ORIENTED_FUNCS)
def test_node_prompt_explains_read_verified_fact_and_read_deliverable_file(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "BL-094" in src, f"{func_name} does not mention BL-094"
    assert "read_verified_fact" in src
    assert "read_deliverable_file" in src


@pytest.mark.parametrize("func_name", _READ_TOOL_ORIENTED_FUNCS)
def test_node_prompt_mandates_iter1_sync_check(func_name):
    """[BL-094] 最低限iter=1で一度はread_verified_factを呼び、他タスクの決定・確定値と
    文脈を同期せよという思考フレームワーク上の指示が明記されていること。"""
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "iter=1で" in src, (
        f"{func_name} does not instruct the model to sync context via read_verified_fact at iter=1"
    )


def test_detector_orientation_frames_traceability_of_numbers():
    """[BL-094] Detectorは特に「数値の出所」（ゴール文由来か、他ノードの自己申告の孫引きか）を
    追跡する監査役なので、その観点がread_verified_fact/read_deliverable_fileの説明に
    明記されていること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "出所" in src


def test_resource_arbiter_orientation_present():
    src = inspect.getsource(cela_main.call_resource_arbiter)
    assert "既存の配分・決定と同期する" in src


def test_integrator_orientation_present():
    src = inspect.getsource(cela_main.call_integrator)
    assert "横断確認する" in src


def test_reviewer_orientation_present():
    src = inspect.getsource(cela_main.call_reviewer)
    assert "最終成果物の数値根拠を追跡する" in src


def test_user_ai_orientation_present():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "既存の決定と同期する" in src


def test_task_planner_orientation_present():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "既存の確定値と同期する" in src


def test_goal_essence_analyst_orientation_present():
    src = inspect.getsource(cela_main.call_goal_essence_analyst)
    assert "既存の確定値の有無を確認する" in src


def test_task_plan_reviewer_orientation_present():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "数値の出所を確認する" in src


@pytest.mark.parametrize("func_name,tool_const_name", [
    ("call_task_planner", "READ_VERIFIED_FACT_TOOL"),
    ("call_task_planner", "READ_DELIVERABLE_FILE_TOOL"),
    ("call_goal_essence_analyst", "READ_VERIFIED_FACT_TOOL"),
    ("call_goal_essence_analyst", "READ_DELIVERABLE_FILE_TOOL"),
    ("call_task_plan_reviewer", "READ_VERIFIED_FACT_TOOL"),
    ("call_task_plan_reviewer", "READ_DELIVERABLE_FILE_TOOL"),
])
def test_newly_wired_functions_pass_the_tool_constants(func_name, tool_const_name):
    """[BL-094] プロンプト本文のオリエンテーションだけでなく、実際にtools=[...]へ
    READ_VERIFIED_FACT_TOOL/READ_DELIVERABLE_FILE_TOOLが配線されていることを確認する。"""
    src = inspect.getsource(getattr(cela_main, func_name))
    assert tool_const_name in src, f"{func_name} does not pass {tool_const_name} in its tools=[...] list"
