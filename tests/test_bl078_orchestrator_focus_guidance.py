"""
BL-078/D-049: Orchestratorが専門家選定時に既に考えている「このタスクで特に注意すべき観点」
（従来は選定理由reasonとしてログにのみ残り、Expertには一切伝わっていなかった）を、
新設focus_guidanceフィールドとして明示的に出力させ、orchestrator_node経由でstateへ保存し、
call_expertのプロンプト（フル版・軽量版の両方）へ注入する回帰テスト。

Detectorの「監査の観点を変えるだけで仕事ぶりが変わる」効果と同じ発想を、
Orchestrator→Expertの選定フローに応用したもの。

参照: docs/design/issue_backlog.md BL-078、decision_log.md D-049。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl078_call_orchestrator_prompt_and_fallback_include_focus_guidance():
    """call_orchestratorのプロンプトがfocus_guidanceを明示的に要求し、
    フォールバック・戻り値の両方にfocus_guidanceキーが含まれること。"""
    src = inspect.getsource(cela_main.call_orchestrator)
    assert "focus_guidance" in src
    assert "BL-078" in src


def test_bl078_orchestrator_node_stores_focus_guidance_in_state():
    """orchestrator_nodeのソースが、call_orchestratorの結果からfocus_guidanceを
    state["expert_focus_guidance"]へ保存する配線を含んでいること。"""
    src = inspect.getsource(cela_main.orchestrator_node)
    assert '"expert_focus_guidance"' in src
    assert 'result.get("focus_guidance"' in src


def test_bl078_call_expert_injects_focus_guidance_into_both_prompts():
    """call_expertのソースが、state["expert_focus_guidance"]をフル版・軽量版
    両方のプロンプトへ注入する配線を含んでいること。"""
    src = inspect.getsource(cela_main.call_expert)
    assert 'state.get("expert_focus_guidance"' in src
    # フル版system_promptと軽量版light_system_promptの両方に登場すること
    assert src.count("expert_focus_guidance") >= 2


def test_bl078_lineagestate_declares_expert_focus_guidance_field():
    """LangGraphが未宣言キーを伝播しない仕様（BL-038の教訓）に従い、
    expert_focus_guidanceがLineageState TypedDictに宣言されていること。"""
    assert "expert_focus_guidance" in cela_main.LineageState.__annotations__
