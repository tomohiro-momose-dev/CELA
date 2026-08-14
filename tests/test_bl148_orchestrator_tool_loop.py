"""
BL-148: Orchestrator（`call_orchestrator`）はツールを一切持たない単発JSON応答で、プロンプトにも
`current_task_id`・タスク計画・issue状況が一切含まれていなかった。専門家選定はUser AI/Expert AIの
対話の生テキストのみに基づいて行われるため、対話がBL-125でブロックされているタスクとは別の
タスクへ漂うと、`current_task_id`がまだ元のタスクにピンされていても専門家選定がそちらへ引っ張られる
実害が確認された（`log/2026-08-02/0832`、Detector自身が「プロンプトのバグだと思う」と自己申告）。

本テストはソース検査のみで以下を検証する（実LLM API呼び出しは伴わない）:
1. call_orchestratorのプロンプトにcurrent_task_id/現在タスクのスコープ情報が組み込まれていること。
2. tools=に読み取り専用ツール（read_project_plan/read_deliverable_file/read_verified_fact/think）
   のみが含まれ、書き込み系ツール（write_agreement等）が含まれないこと
   （test_bl093_think_tool_scratchpad.py::test_bl148_call_orchestrator_is_tool_loop_capableで
   より詳細に検証済み、ここではプロンプト・current_task_id関連の変更点に絞る）。
3. orchestrator_nodeの既存の入出力契約（state["selected_expert"]/state["expert_focus_guidance"]）が
   変更されていないこと（BL-078の既存テストで担保、本ファイルでは変更していないことのみ確認）。

参照: docs/design/back_log/issue_backlog.md BL-148。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_orchestrator_prompt_references_current_task_id():
    src = inspect.getsource(cela_main.call_orchestrator)
    # [BL-214] 生のstate読みから実効アクセサへ一元化した。BL-148の意図（Orchestratorのプロンプトが
    # 現在タスクを構造化情報として参照すること）は変わらず、参照の仕方だけが変わっている。
    # 初回タスク進行中は生のcurrent_task_idが空文字のままで、プロンプトに現在タスクが
    # 一切現れなかった（BL-148が防ごうとした状態そのもの）。
    assert "_effective_current_task_id_from(state)" in src
    assert "_build_task_scope_context" in src


def test_call_orchestrator_tools_are_read_only():
    src = inspect.getsource(cela_main.call_orchestrator)
    for tool_name in ("READ_PROJECT_PLAN_TOOL", "READ_DELIVERABLE_FILE_TOOL", "READ_VERIFIED_FACT_TOOL", "THINK_TOOL"):
        assert tool_name in src, f"call_orchestrator does not reference {tool_name}"
    for write_tool_name in (
        "WRITE_AGREEMENT_TOOL", "ESCALATE_PREMISE_CONCERN_TOOL", "ASK_USER_QUESTION_TOOL",
        "WRITE_ISSUE_TOOL", "REVISE_GOAL_TOOL", "FREEZE_AGREEMENT_TOOL", "RESOLVE_PREMISE_CONCERN_TOOL",
    ):
        assert write_tool_name not in src, f"call_orchestrator should not reference {write_tool_name}"


def test_call_orchestrator_passes_state_to_query_ai():
    """ツールループがread_project_plan等のハンドラでstateベースのフィルタ（phases由来のtask一覧）を
    使えるよう、query_AI呼び出しにstateを渡していること。"""
    src = inspect.getsource(cela_main.call_orchestrator)
    assert "state=state" in src


def test_orchestrator_node_output_contract_unchanged():
    src = inspect.getsource(cela_main.orchestrator_node)
    assert 'state["selected_expert"]' in src
    assert 'state["expert_focus_guidance"]' in src
