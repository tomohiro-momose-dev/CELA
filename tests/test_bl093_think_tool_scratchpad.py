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
    """[BL-131/TOOL_DISPATCH state化] ハンドラは`_think_handler`への薄いラムダに変わった
    （`(args, state=None)`で受けてargsのみ`_think_handler`へ委譲する）ため、直接の同一性
    ではなく実際に委譲される挙動で検証する。"""
    assert "think" in cela_main.TOOL_DISPATCH
    _reset_all()
    args = {"action": "dispatch-check", "summary": "dispatch経由の呼び出し確認"}
    direct = cela_main._think_handler(dict(args))
    _reset_all()
    via_dispatch = cela_main.TOOL_DISPATCH["think"](dict(args))
    assert direct == via_dispatch


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


def test_think_handler_todo_and_scratch_concerns_require_open_closed_status_and_are_sticky():
    """todo/scratch_concernsは変更がある時だけ送ればよく、省略時は前回状態を保持する。"""
    _reset_all()
    r1 = cela_main._think_handler({
        "action": "初期todoをリストアップ",
        "todo": [{"item": "往復距離の確認", "status": "open"}],
        "scratch_concerns": [{"item": "単位の食い違いに気づいた", "status": "open"}],
    })
    assert r1["current_todo"] == [{"item": "往復距離の確認", "status": "open"}]
    # todo/scratch_concernsを省略 → 前回状態がそのまま維持される
    r2 = cela_main._think_handler({"action": "何もアップデートしない検討"})
    assert r2["current_todo"] == [{"item": "往復距離の確認", "status": "open"}]
    assert r2["current_scratch_concerns"] == [{"item": "単位の食い違いに気づいた", "status": "open"}]
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
        "scratch_concerns": [{"item": "y", "status": "open"}], "notes": "z",
    })
    cela_main._reset_think_scratchpad()
    assert cela_main._CURRENT_TOOL_LOOP_ITERATION == 0
    assert cela_main._THINK_REASONING_LOG == []
    assert cela_main._THINK_TODO == []
    assert cela_main._THINK_SCRATCH_CONCERNS == []
    assert cela_main._THINK_NOTES == []


def test_think_tool_scratch_concerns_param_disambiguates_from_write_issue():
    """[BL-140] `issues`という名前が`write_issue`（DBへ永続化されターンをまたいで見える）と
    混同され、モデルがここへ懸念を書いて満足し`write_issue`を呼ばずに終わる（懸念がツール
    ループ終了と同時に消える）実例が実ドライランで観測された。パラメータ名を`scratch_concerns`
    へ改め、description内で明示的に`write_issue`と対比させたことを確認する。"""
    props = cela_main.THINK_TOOL["function"]["parameters"]["properties"]
    assert "issues" not in props
    assert "scratch_concerns" in props
    description = props["scratch_concerns"]["description"]
    assert "write_issue" in description
    assert "NOT" in description


def test_call_detector_prompt_body_disambiguates_scratch_concerns_from_write_issue():
    """[BL-140] ツールのJSONスキーマ説明だけでなく、call_detector（domain review）の
    システムプロンプト本文（write_issueとthinkが並記される箇所）にも、scratch_concernsが
    ターンをまたいで引き継がれない一時メモであることの明示的な注記があること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-140" in src
    assert "scratch_concerns" in src


def test_generate_user_utterance_prompt_body_disambiguates_scratch_concerns_from_write_issue():
    """[BL-140] generate_user_utterance（write_issue/read_issues/thinkが並記される箇所）にも
    同様の注記があること。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "BL-140" in src
    assert "scratch_concerns" in src


def test_max_tool_iter_raised_beyond_20():
    """[BL-155] task_plan_reviewerによる差し戻し後、task_plannerが差戻しタスクを1件ずつ
    把握し直す過程でiter=20（旧上限）に迫る実績がドライランで観測されたため、20から引き上げ。
    その後もドライランの実績に応じて調整されている（30→50）ため、特定の数値ではなく
    「元の20より緩和されていること」だけを固定する（BL-199のmax_web_search_calls
    テストと同じ考え方）。"""
    import re
    src = inspect.getsource(cela_main._query_AI_live)
    m = re.search(r"MAX_TOOL_ITER = (\d+)", src)
    assert m, "MAX_TOOL_ITERの代入が見つかりません"
    assert int(m.group(1)) > 20


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
# [BL-109] call_orchestrator/call_decision_extractor/call_reflection/call_facilitatorは
# 一度tools=[THINK_TOOL]へ変更したが、いずれも複数ツールを組み合わせて検討する必要のない
# 単発判定・抽出タスクであり、thinkツールが解決する「複数iterをまたぐreasoning引き継ぎ」問題
# 自体が発生しないため、tools=Noneの単一応答パスへ差し戻した（ネイティブのreasoning_effort_level
# はlabel名を明示追加して維持）。このリストからは除外する。
_ALL_THINK_WIRED_FUNCS = [
    "call_expert",
    "generate_user_utterance",
    "call_goal_essence_analyst",
    "call_reviewer",
    "call_integrator",
    "call_resource_arbiter",
]


import pytest as _pytest


@_pytest.mark.parametrize("func_name", _ALL_THINK_WIRED_FUNCS)
def test_all_nodes_wire_think_tool_and_reset(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "THINK_TOOL" in src, f"{func_name} does not reference THINK_TOOL"
    assert "_reset_think_scratchpad()" in src, f"{func_name} does not reset the think scratchpad"


def test_call_detector_domain_review_pass_also_wires_think_tool():
    """[BL-093] ドメイン妥当性レビュー（tools=None→[THINK_TOOL]）も全ノード対象化に含まれる。
    [BL-204] tools=[...]の一覧はBL-198/199/204等で継続的にツールが追加されており、
    固定の文字数窓では脆くなる。窓サイズではなく、labelの直後に現れるtools=[...]の
    1行そのものにTHINK_TOOLが含まれるかで判定する。"""
    src = inspect.getsource(cela_main.call_detector)
    assert 'label="Detector (Domain Review)"' in src
    domain_call_idx = src.index('label="Detector (Domain Review)"')
    tools_line_start = src.index("tools=[", domain_call_idx)
    tools_line_end = src.index("]", tools_line_start)
    assert "THINK_TOOL" in src[tools_line_start:tools_line_end]


def test_bl109_single_shot_judgment_nodes_reverted_to_tools_none():
    """[BL-109] call_decision_extractor/call_reflectionは複数ツールを組み合わせて
    検討する必要のない単発判定・抽出タスクであり、thinkツールが解決する「複数iterをまたぐ
    reasoning引き継ぎ」問題自体が発生しないため、tools=[THINK_TOOL]のツールループパスから
    単一応答パス（tools=None、query_AIのtools引数省略）へ差し戻した。
    [BL-126 Stage D] call_facilitatorはこの後、本質対話（Essence Dialogue）でescalate_premise_
    concern/write_agreement(EssenceProposal)を自ら呼べる必要が生じたため、この一覧から除外し
    ツールループ化した（BL-109の対象外へ変更、design.md §2/§13.2参照）。
    [BL-148] call_orchestratorも同様に、current_task_id/計画/成果物を能動的に確認する必要が
    生じたためこの一覧から除外し、読み取り専用ツールを持つツールループ化した
    （test_bl148_call_orchestrator_is_tool_loop_capable参照）。
    """
    for func_name in ["call_decision_extractor", "call_reflection"]:
        src = inspect.getsource(getattr(cela_main, func_name))
        assert "THINK_TOOL" not in src, f"{func_name} should no longer reference THINK_TOOL"


def test_bl126_stage_d_call_facilitator_is_tool_loop_capable():
    """[BL-126 Stage D] call_facilitatorはTHINK_TOOL/ESCALATE_PREMISE_CONCERN_TOOL/
    WRITE_AGREEMENT_TOOLを持つツールループパスへ変更されたこと（BL-109からの意図的な差し戻し）。"""
    src = inspect.getsource(cela_main.call_facilitator)
    assert "THINK_TOOL" in src
    assert "ESCALATE_PREMISE_CONCERN_TOOL" in src
    assert "WRITE_AGREEMENT_TOOL" in src


def test_bl148_call_orchestrator_is_tool_loop_capable():
    """[BL-148] call_orchestratorはcurrent_task_id/計画/成果物を能動的に確認できるよう、
    読み取り専用ツール（read_project_plan/read_deliverable_file/read_verified_fact/think）を
    持つツールループパスへ変更された（BL-109からの意図的な差し戻し）。専門家選定メタデータの
    生成以外の役割は持たず状態も変更しないため、write_agreement等の書き込み系ツールは
    意図的に持たないことをレグレッションガードとして固定する。"""
    src = inspect.getsource(cela_main.call_orchestrator)
    assert "THINK_TOOL" in src
    assert "READ_PROJECT_PLAN_TOOL" in src
    assert "READ_DELIVERABLE_FILE_TOOL" in src
    assert "READ_VERIFIED_FACT_TOOL" in src
    assert "WRITE_AGREEMENT_TOOL" not in src
    assert "ESCALATE_PREMISE_CONCERN_TOOL" not in src


def test_bl109_reasoning_effort_level_preserved_for_reverted_nodes():
    """[BL-109] orchestrator/facilitatorはtools=None化前、reasoning_effort_levelを
    `elif tools is not None`経由（tools付与ノード向けのフォールバック）でしか得ていなかった
    ため、tools=None化のサイレントな副作用でreasoningが無効化されないよう、明示的な
    label分岐（`elif tools is not None`より前）へ追加されていること。具体的な効果レベルの
    値・他ラベルとのグルーピングはチューニング対象のため固定文字列では検証しない。
    """
    src = inspect.getsource(cela_main._query_AI_live)
    fallback_idx = src.index('elif tools is not None:')
    for label in ("orchestrator", "facilitator"):
        label_idx = src.index(f'"{label}"')
        assert label_idx < fallback_idx, (
            f'"{label}" should be explicitly matched before the `elif tools is not None` '
            "fallback, not rely on it"
        )


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
    "call_orchestrator": [
        "read_project_plan", "read_deliverable_file", "read_verified_fact",
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
