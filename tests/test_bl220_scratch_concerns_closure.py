"""
BL-220: think の scratch_concerns を、最終出力の直前に必ず整理・外部化させる。

きっかけ: BL-219の調査で、task_plan_reviewerがthinkツールの中で「約8,500人/日は
derived number, need to check calculation（要検算）」と自ら懸念を示していたにも
かかわらず、その懸念がどこにも構造化記録として残らず、後続タスクから一切参照できな
かったことが判明した（`log/2026-08-11/2318:4080`）。

`think`ツールには既にscratch_concernsという懸念追跡欄がある（BL-140）が、「最終出力の
直前に実際に見直す」ことを明示的に指示している箇所がプロンプト側になかったのが直接原因
だった。ユーザーの指示：
- thinkとwrite_issueの両方が使えるノードでは、最終出力前にscratch_concernsを整理し、
  未解決ならissueとして起票するようプロンプトで指示する。
- write_issueが使えないノードでは、最終出力（構造化JSON等）の中で懸念を示すよう
  プロンプトで指示する。

対策として、共有ヘルパー`_scratch_concerns_closure_instruction`を新設し（AGENTS.md §15.1、
BL-115共有プロンプト定型文と同じ集約方針）、thinkツールを持つ16箇所全て（call_task_planner・
call_orchestrator・call_expert（本体・light_system_prompt）・call_detector（2モード）・
call_resource_arbiter・call_facilitator（2分岐）・call_integrator・call_reviewer・
generate_user_utterance（Stage1-4＋特殊モード一括ループ）・call_goal_essence_analyst・
call_task_plan_reviewer）へ機械的に挿入した。部分的な適用は「懸念が消える」という同じ欠陥を
別ノードで再現するだけなので避けた（AGENTS.md §15.2）。

参照: docs/design/issue_backlog.md BL-220、BL-219（消費経路の欠落という同型の欠陥）、
BL-140（scratch_concerns自体の初出）。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

_RUNTIME_MARKER = "BL-220: 最終出力前にscratch_concernsを整理する"
_CALL_SITE_MARKER = "_scratch_concerns_closure_instruction("


def test_bl220_helper_escalation_tools_branch_mentions_the_tool():
    """escalation_toolsが与えられた場合、そのツール名を含む「記録してから出力」文言になり、
    final_output_fieldへの言及（「〜へ必ず明記」の定型文）は出さないこと。"""
    text = cela_main._scratch_concerns_closure_instruction("observations", escalation_tools="write_issue")
    assert "write_issue" in text
    assert "確実に記録してから" in text
    assert "へ必ず明記してください" not in text


def test_bl220_helper_no_escalation_tools_branch_mentions_output_field():
    """escalation_toolsを省略した場合、final_output_fieldへ明記するよう指示する文言になり、
    存在しないツール名を挙げないこと。"""
    text = cela_main._scratch_concerns_closure_instruction("rationale")
    assert "「rationale」へ必ず明記してください" in text
    assert "確実に記録してから" not in text


def test_bl220_helper_always_mentions_marker_and_scratch_concerns():
    """両分岐とも、機械的なBL-220マーカーとscratch_concernsへの言及を含むこと
    （テストの検知用マーカーであると同時に、モデルへの一貫した見出しでもある）。"""
    for text in (
        cela_main._scratch_concerns_closure_instruction("observations", escalation_tools="write_issue"),
        cela_main._scratch_concerns_closure_instruction("rationale"),
    ):
        assert _RUNTIME_MARKER in text
        assert "scratch_concerns" in text


@pytest.mark.parametrize(
    "func_name,min_count",
    [
        ("call_task_planner", 1),
        ("call_orchestrator", 1),
        ("call_expert", 2),  # 本体system_prompt + light_system_prompt
        ("call_detector", 2),  # task_output mode + 他mode
        ("call_resource_arbiter", 1),
        ("call_facilitator", 2),  # essence_dialogue_active分岐 + 通常分岐
        ("call_integrator", 1),
        ("call_reviewer", 1),
        ("generate_user_utterance", 5),  # Stage1/2/3/4 + 特殊モード一括ループ
        ("call_goal_essence_analyst", 1),
        ("call_task_plan_reviewer", 1),
    ],
)
def test_bl220_wiring_marker_present_in_each_node(func_name, min_count):
    """「呼び出し忘れ」防止: think を持つ全16箇所（関数単位では11関数）のソースに、
    BL-220マーカーが期待される回数以上含まれていること。"""
    func = getattr(cela_main, func_name)
    src = inspect.getsource(func)
    assert src.count(_CALL_SITE_MARKER) >= min_count, (
        f"{func_name}: expected >= {min_count} occurrences, found {src.count(_CALL_SITE_MARKER)}"
    )


def test_bl220_seed_entities_from_goal_intentionally_excluded():
    """[設計判断の回帰防止] seed_entities_from_goal（entity登録専用の最小限ノード）は
    意図的に対象外とした。将来的にscratch_concernsの実質的な使用が増えた場合のみ
    追加を検討する、というスコープ判断のドキュメント化。"""
    src = inspect.getsource(cela_main.seed_entities_from_goal)
    assert _CALL_SITE_MARKER not in src
