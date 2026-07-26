"""
BL-093: ノード内スクラッチパッド `think`ツール（ツールループ内の可変todo/issue/notesメモ、
および理由づけの退避）。

`_query_AI_live`のツールループは、モデルのreasoning（chain-of-thought生文章）を
`_StreamMessage`で`None`固定にして捨てており（content/tool_callsのみがloop_messagesへ
再送される）、次iterationでモデルは前回どのツールを何の引数で呼んだかという記録だけから
理由を再構築している。`think`ツールに理由づけ（action/decided/why/rejected/rejected_why）
を書かせ、tool結果として即座に蓄積済み全履歴を返すことで、消えるreasoningチャネルから
残るtool_callsチャネルへ理由づけを退避させる。todo/issuesはopen/close必須のリスト、notesは
上書きされない追記専用リストとして分離する。iter番号はモデルの自己申告に頼らず
`_CURRENT_TOOL_LOOP_ITERATION`（`_query_AI_live`が機械的に更新）から機械的に取る。

参照: docs/design/issue_backlog.md BL-093、docs/design/decision_log.md D-070/D-071。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _reset_all():
    cela_main._reset_think_scratchpad()


def test_think_tool_registered_in_dispatch():
    assert "think" in cela_main.TOOL_DISPATCH
    assert cela_main.TOOL_DISPATCH["think"] is cela_main._think_handler


def test_think_handler_records_reasoning_with_mechanical_iteration_number():
    """reasoningのiter番号はモデルの自己申告ではなく_CURRENT_TOOL_LOOP_ITERATIONから機械的に取る。"""
    _reset_all()
    cela_main._CURRENT_TOOL_LOOP_ITERATION = 3
    result = cela_main._think_handler({
        "action": "往復距離の前提を確認する",
        "decided": "往復24kmと確定",
        "why": "原文に「往復」と明記されている",
        "rejected": "片道24km説",
        "rejected_why": "原文の記述と矛盾するため",
    })
    assert result["reasoning_log_so_far"][-1]["iter"] == 3
    assert result["reasoning_log_so_far"][-1]["decided"] == "往復24kmと確定"
    assert result["reasoning_log_so_far"][-1]["rejected"] == "片道24km説"


def test_think_handler_accumulates_reasoning_across_multiple_calls():
    """複数回呼ぶと、過去の全reasoningが毎回まとめて返される（次iterへの"注入"）。"""
    _reset_all()
    cela_main._CURRENT_TOOL_LOOP_ITERATION = 1
    cela_main._think_handler({"action": "1回目の検討"})
    cela_main._CURRENT_TOOL_LOOP_ITERATION = 2
    result = cela_main._think_handler({"action": "2回目の検討"})
    actions = [e["action"] for e in result["reasoning_log_so_far"]]
    assert actions == ["1回目の検討", "2回目の検討"]


def test_think_handler_todo_and_issues_require_open_closed_status_and_are_sticky():
    """todo/issuesは変更がある時だけ送ればよく、省略時は前回状態を保持する。"""
    _reset_all()
    r1 = cela_main._think_handler({
        "action": "初期todoをリストアップ",
        "todo": [{"item": "往復距離の確認", "status": "open"}],
        "issues": [{"item": "単位の食い違いに気づいた", "status": "open"}],
    })
    assert r1["current_todo"] == [{"item": "往復距離の確認", "status": "open"}]
    # todo/issuesを省略 → 前回状態がそのまま維持される
    r2 = cela_main._think_handler({"action": "何もアップデートしない検討"})
    assert r2["current_todo"] == [{"item": "往復距離の確認", "status": "open"}]
    assert r2["current_issues"] == [{"item": "単位の食い違いに気づいた", "status": "open"}]
    # todoを更新（closeへ変更）
    r3 = cela_main._think_handler({
        "action": "確認完了",
        "todo": [{"item": "往復距離の確認", "status": "closed"}],
    })
    assert r3["current_todo"] == [{"item": "往復距離の確認", "status": "closed"}]


def test_think_handler_notes_are_append_only_not_overwritten():
    """notesは上書きされず、送るたびに追記される（既存分は消えない）。"""
    _reset_all()
    r1 = cela_main._think_handler({"action": "メモ1", "notes": "最初のメモ"})
    assert r1["notes_so_far"] == ["最初のメモ"]
    r2 = cela_main._think_handler({"action": "メモ2", "notes": "2つ目のメモ"})
    assert r2["notes_so_far"] == ["最初のメモ", "2つ目のメモ"]
    # notesを省略しても既存分は消えない
    r3 = cela_main._think_handler({"action": "メモなしの検討"})
    assert r3["notes_so_far"] == ["最初のメモ", "2つ目のメモ"]


def test_reset_think_scratchpad_clears_all_state():
    cela_main._CURRENT_TOOL_LOOP_ITERATION = 5
    cela_main._think_handler({
        "action": "何か", "todo": [{"item": "x", "status": "open"}],
        "issues": [{"item": "y", "status": "open"}], "notes": "z",
    })
    cela_main._reset_think_scratchpad()
    assert cela_main._CURRENT_TOOL_LOOP_ITERATION == 0
    assert cela_main._THINK_REASONING_LOG == []
    assert cela_main._THINK_TODO == []
    assert cela_main._THINK_ISSUES == []
    assert cela_main._THINK_NOTES == []


def test_max_tool_iter_raised_to_20():
    src = inspect.getsource(cela_main._query_AI_live)
    assert "MAX_TOOL_ITER = 20" in src


def test_query_ai_live_stamps_mechanical_iteration_globally():
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_CURRENT_TOOL_LOOP_ITERATION = iteration" in src
    assert '"iteration": iteration' in src


def test_call_detector_wires_think_tool_and_instruction():
    src = inspect.getsource(cela_main.call_detector)
    assert "THINK_TOOL" in src
    assert "_reset_think_scratchpad()" in src
    assert "BL-093" in src


def test_call_task_planner_wires_think_tool_and_instruction():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "THINK_TOOL" in src
    assert "_reset_think_scratchpad()" in src
    assert "BL-093" in src


def test_call_task_plan_reviewer_wires_think_tool_and_instruction():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "THINK_TOOL" in src
    assert "_reset_think_scratchpad()" in src
    assert "BL-093" in src


# 「対象ノードは全ノードへ。ツール呼び出し回数というより、思考のやり方の環境の整備なので」
# というユーザー指示により、当初の3ノード限定から全LLM呼び出し関数へ拡張した。
# tools=None（単一応答パス）だった4関数もtools=[THINK_TOOL]へ変更しツールループパスに
# 切り替わっている点が、既存tools付与ノードへの追加と異なる（構造的な変化）。
_ALL_THINK_WIRED_FUNCS = [
    "call_expert",
    "generate_user_utterance",
    "call_goal_essence_analyst",
    "call_reviewer",
    "call_integrator",
    "call_resource_arbiter",
    "call_orchestrator",
    "call_decision_extractor",
    "call_reflection",
    "call_facilitator",
]


import pytest as _pytest


@_pytest.mark.parametrize("func_name", _ALL_THINK_WIRED_FUNCS)
def test_all_nodes_wire_think_tool_and_reset(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "THINK_TOOL" in src, f"{func_name} does not reference THINK_TOOL"
    assert "_reset_think_scratchpad()" in src, f"{func_name} does not reset the think scratchpad"


def test_call_detector_domain_review_pass_also_wires_think_tool():
    """[BL-093] ドメイン妥当性レビュー（tools=None→[THINK_TOOL]）も全ノード対象化に含まれる。"""
    src = inspect.getsource(cela_main.call_detector)
    assert 'label="Detector (Domain Review)"' in src
    # ドメイン妥当性レビューの呼び出しブロックにTHINK_TOOLが含まれていること
    domain_call_idx = src.index('label="Detector (Domain Review)"')
    nearby = src[max(0, domain_call_idx - 400):domain_call_idx + 200]
    assert "THINK_TOOL" in nearby


def test_previously_tools_none_functions_no_longer_pass_tools_none():
    """call_orchestrator/call_decision_extractor/call_reflection/call_facilitatorは
    tools=Noneの単一応答パスからツールループパス（tools=[THINK_TOOL]）へ切り替わった。
    """
    for func_name in ["call_orchestrator", "call_decision_extractor", "call_reflection", "call_facilitator"]:
        src = inspect.getsource(getattr(cela_main, func_name))
        assert "tools=[THINK_TOOL]" in src, f"{func_name} should now pass tools=[THINK_TOOL]"


# [BL-093 追記修正2] log/2026-07-26/1713で、モデルがpython_repl等を呼ぶ判断時にTHINK_TOOL側の
# 制約を参照しておらず差し戻しが再発したため、think以外の全ツール自身の説明文にも
# 同一のリマインダーを追記した。これが欠落すると同じ空費が再発するため回帰テスト化する。
_OTHER_TOOL_NAMES = [
    "PYTHON_REPL_TOOL", "READ_VERIFIED_FACT_TOOL", "READ_DELIVERABLE_FILE_TOOL",
    "VERIFY_WHITEBOARD_EXCERPT_TOOL", "DIFF_PLAN_DRAFT_VERSIONS_TOOL", "WRITE_AGREEMENT_TOOL",
    "FREEZE_AGREEMENT_TOOL", "ESCALATE_PREMISE_CONCERN_TOOL", "RESOLVE_PREMISE_CONCERN_TOOL",
    "REVISE_GOAL_TOOL",
]


@_pytest.mark.parametrize("tool_name", _OTHER_TOOL_NAMES)
def test_other_tools_remind_to_call_think_with_summary(tool_name):
    tool_def = getattr(cela_main, tool_name)
    description = tool_def["function"]["description"]
    assert "think" in description and "summary" in description, (
        f"{tool_name}'s description does not remind the model to call think with a summary"
    )


# [BL-093 追記修正3] log/2026-07-26/1713のツール説明文修正後も再度失敗が観測されたため
# （ユーザー指摘: 「先ほど私が書いたように各ノードのプロンプトに各ツールはthinkとともに
# 使用せよと明示してください」）、ツール説明文だけでなく各ノードのプロンプト本文にも、
# そのノードが実際に使えるツール名を名指しした「【重要】あなたが使えるツールは...」の
# 一文を追記した。ツール一覧が変わったのにこの一文の更新を忘れると検知できるよう、
# ノードごとに期待されるツール名（プロンプト中に書いた素のツール名文字列）を回帰テスト化する。
_NODE_TOOL_NAME_REMINDERS = {
    "call_task_planner": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
    ],
    "call_expert": [
        "python_repl", "read_verified_fact", "read_deliverable_file",
        "write_agreement", "escalate_premise_concern",
    ],
    "call_detector": [
        "python_repl", "read_verified_fact", "read_deliverable_file",
        "write_agreement", "verify_whiteboard_excerpt",
    ],
    "call_resource_arbiter": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
    ],
    "call_integrator": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
    ],
    "call_reviewer": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
    ],
    "generate_user_utterance": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
        "escalate_premise_concern", "resolve_premise_concern", "revise_goal", "freeze_agreement",
    ],
    "call_goal_essence_analyst": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "write_agreement",
    ],
    "call_task_plan_reviewer": [
        "python_repl", "read_verified_fact", "read_deliverable_file", "diff_plan_draft_versions",
        "write_agreement",
    ],
}


@_pytest.mark.parametrize("func_name", list(_NODE_TOOL_NAME_REMINDERS.keys()))
def test_node_prompt_names_its_own_tools_alongside_think(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "あなたが使えるツールは" in src, (
        f"{func_name} does not name its available tools alongside think in the prompt body"
    )
    for tool_name in _NODE_TOOL_NAME_REMINDERS[func_name]:
        assert tool_name in src, f"{func_name}'s tool-naming reminder is missing '{tool_name}'"
