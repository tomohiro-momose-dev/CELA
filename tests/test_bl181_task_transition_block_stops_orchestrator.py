"""
BL-181: BL-125がタスク遷移をブロックした（current_task_idを更新しなかった）にもかかわらず、
Orchestrator/Expertが直近の会話文脈（Userが既に発言した次タスクの指示）だけを頼りに
先走ってしまい、write_agreementのtask_id不一致ゲートに阻まれたExpertがtask_idを誤登録する
回避策を取ってしまう事故が実際に発生した（`log/2026-08-05/1833`、task_4_1に未解決の
severity='major'issue「task_4_1_route_length_ratio_contradiction」が残ったまま、
task_4_2の成果物がtask_id='task_4_1'として誤登録された）。

根本原因: `_resolve_task_transition`（BL-125、user_decision_extractor内）は
`state["task_transition_blocked_unapproved_task_id"]`を機械的にセットするが、直後の
`route_after_user_decision`はこの値を一切参照せず、無条件に"orchestrator"へ進めていた。
`_build_task_transition_blocked_notice`（BL-125の通知）はgenerate_user_utterance
（User AI）のプロンプトにしか注入されておらず、Orchestrator/Expertはブロックの存在を
一切知らされていなかった。

対策（2段防御、ユーザー設計）:
1. 第1段（意味的・user_detector）: target_role="user"のDetector監査へ、次タスクへの
   移行時に現在タスクのmajor/escalated issueが未対応のまま残っていないかread_issuesで
   確認する指示を追加（`role_specific_instruction`のBL-181節）。これがmajorを出せば
   既存のroute_after_user_detectorがgenerate_user_utteranceへ差し戻す（Expertは
   一切呼ばれない）。
2. 第2段（機械的な最終防衛線・route_after_user_decision）: BL-125が
   `task_transition_blocked_unapproved_task_id`をセットした場合、LLMを介さず
   Python側のみでorchestratorへ進めずgenerate_user_utteranceへ差し戻す。

参照: docs/design/back_log/issue_backlog.md BL-181、docs/design/decision_log.md D-150。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 第2段: route_after_user_decision（build_graph内のネスト関数、ソース確認）
# ---------------------------------------------------------------------------

def _build_graph_source() -> str:
    return inspect.getsource(cela_main.build_graph)


def test_route_after_user_decision_checks_transition_blocked_flag():
    src = _build_graph_source()
    assert "def route_after_user_decision(state: LineageState):" in src
    # route_after_user_decisionの本体だけを切り出す
    start = src.index("def route_after_user_decision(state: LineageState):")
    end = src.index("graph.add_conditional_edges(\n        \"user_decision_extractor\"", start)
    body = src[start:end]
    assert 'task_transition_blocked_unapproved_task_id' in body
    assert '"generate_user_utterance"' in body


def test_route_after_user_decision_checks_block_before_ready_for_review():
    """BL-125のブロックチェックは、ready_for_review（完了宣言）より先に判定されること
    （ブロック中に誤ってintegratorへ進んでしまわないため）。"""
    src = _build_graph_source()
    start = src.index("def route_after_user_decision(state: LineageState):")
    end = src.index("graph.add_conditional_edges(\n        \"user_decision_extractor\"", start)
    body = src[start:end]
    block_idx = body.index("task_transition_blocked_unapproved_task_id")
    ready_idx = body.index('"ready_for_review"')
    assert block_idx < ready_idx


def test_user_decision_extractor_conditional_edges_include_generate_user_utterance():
    """build_graph()呼び出し時に例外なくコンパイルでき、user_decision_extractorの
    条件分岐マッピングにgenerate_user_utteranceへの新規遷移が登録されていること。"""
    src = _build_graph_source()
    edges_start = src.index('"user_decision_extractor",\n        route_after_user_decision,')
    edges_block = src[edges_start:edges_start + 400]
    assert '"generate_user_utterance": "generate_user_utterance"' in edges_block


def test_build_graph_compiles_without_error():
    compiled = cela_main.build_graph()
    assert compiled is not None


# ---------------------------------------------------------------------------
# 第1段: user_detector向けrole_specific_instructionのBL-181節（ソース確認）
# ---------------------------------------------------------------------------

def test_call_detector_source_has_bl181_task_transition_homework_check():
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-181" in src
    assert "read_issues" in src
    assert "RESOLVE" in src and "DEFER" in src
    # target_role == "user" の分岐内にあることを確認
    user_branch_idx = src.index('if target_role == "user":\n        role_specific_instruction')
    bl181_idx = src.index("BL-181")
    assert bl181_idx > user_branch_idx
