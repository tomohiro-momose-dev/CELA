"""
BL-285: CELAのステートレスなノード構成・DB記録の必要性を概念レベルで説明する
プロンプトブロック（当初task_plannerへ試験導入、BL-286でExpert/User AIへ拡張）。

log/2026-08-27/1237で、task_plannerが指示されていない「導出変数をconfirmed_variablesとして
登録し、下流タスクがread_verified_factで参照できるようにする」という消費経路の設計を
自発的に行っていたことをユーザーが確認した。これを踏まえ、手続き的な指示（「write_agreement
で記録しろ」）だけでなく、仕組み自体（LangGraphのステートレスなノード構成、thinkや生reasoning
がツールループ終了時に消えること）を説明すれば、同様の汎化的な応用がより安定して起きる
のではという仮説をユーザーが提示し、まずtask_planner一箇所にのみ試験導入した。

その後、BL-286の全ノードプロンプト監査を経て、ユーザーの指示により当初からの主眼だった
Expert（call_expert）とUser AI（generate_user_utterance）へ拡張した。call_expertは
system_prompt（iter=1）とlight_system_prompt（iter=2以降、loop_messages[0]を置換する
軽量版）の両方に配線が必要（`_build_decision_lineage_directive`と同じ理由）。
generate_user_utteranceはStage1/2/4（WRITE_AGREEMENT_TOOLを持たない）ではなく、
`_user_ai_main_tools`を使うメイン発言生成の`system_prompt_trailing`にのみ配線した。
残り8ノードへの展開は効果を見てから判断する方針のまま。

参照: docs/design/back_log/issue_backlog.md BL-285/BL-286。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_primer_explains_statelessness_and_db_as_only_persistence():
    primer = cela_main._build_stateless_architecture_primer()
    assert "ステートレス" in primer
    assert "write_agreement" in primer
    assert "think" in primer


def test_primer_explains_read_side_as_the_lookup_channel():
    primer = cela_main._build_stateless_architecture_primer()
    assert "read_verified_fact" in primer
    assert "read_agreement" in primer


def test_task_planner_wires_the_primer():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "_build_stateless_architecture_primer()" in src


def test_call_expert_wires_the_primer_in_both_system_prompt_and_light_system_prompt():
    """[BL-286] call_expertはiter=1の`system_prompt`とiter=2以降にloop_messages[0]を
    置換する`light_system_prompt`の両方を持つ（`_build_decision_lineage_directive`と同じ
    理由）。primerが片方にしか配線されていないと、iter=2以降で仕組みの説明が消える。"""
    src = inspect.getsource(cela_main.call_expert)
    assert src.count("_build_stateless_architecture_primer()") >= 2, \
        "call_expertはsystem_prompt/light_system_promptの両方にprimerを配線する必要があります"


def test_generate_user_utterance_wires_the_primer():
    """[BL-286] generate_user_utteranceは`_user_ai_main_tools`（WRITE_AGREEMENT_TOOLを含む
    メイン発言生成）の`system_prompt_trailing`にのみ配線する。Stage1/2/4は
    WRITE_AGREEMENT_TOOLを持たないため対象外（BL-283と同じ判断）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_stateless_architecture_primer()" in src


# ---------------------------------------------------------------------------
# 段階的ロールアウト: task_planner/call_expert/generate_user_utterance以外には
# まだ配線しない（効果を確認してから展開する方針、ユーザー指示）。
# ---------------------------------------------------------------------------

_OTHER_WIRED_NODE_FUNCS = [
    "call_orchestrator", "call_detector", "call_resource_arbiter",
    "call_reflection", "call_facilitator", "call_integrator", "call_reviewer",
    "call_goal_essence_analyst", "call_task_plan_reviewer",
]


def test_other_nodes_not_yet_wired_with_the_primer():
    """[BL-285/286] 段階的ロールアウトの回帰確認: task_planner/call_expert/
    generate_user_utterance以外にまだ展開していないことを明示的にテストし、意図せぬ
    横展開（あるいは意図した展開後にこのテストの更新漏れ）に気づけるようにする。展開する
    場合は、このテストと_OTHER_WIRED_NODE_FUNCSの対象ノードを明示的に更新すること。
    """
    for func_name in _OTHER_WIRED_NODE_FUNCS:
        src = inspect.getsource(getattr(cela_main, func_name))
        assert "_build_stateless_architecture_primer()" not in src, \
            f"{func_name}に想定外にBL-285/286のprimerが配線されています（段階的ロールアウト方針を確認してください）"
