"""
BL-104: call_expertのphases_json全文表示を目次（ToC）＋on-demandツールへ変更し、
プロンプトを「固定指示文が先頭、動的データが末尾」の順に並び替える。

背景:
- DBから直接測定した結果、call_expertの`phases_json`（全フェーズ・全タスク完全JSON）は
  13,361文字あり、`_build_task_scope_context`が既に提供するcurrent_task_json/
  verified_facts_json/deferred_notes_textとほぼ機能的に重複していた。BL-025の
  スコープガードレール（Expertが他タスクのowns_variables領域に踏み込むことを防ぐ）の
  趣旨とも逆行するため、常時表示はphase_id/task_id/titleのみの軽量な目次（ToC）に
  とどめ、全文詳細が必要な場合は新設read_project_planツールで能動的に取得させる。
- ユーザーからOpenRouterのプロンプトキャッシュヒット率が40%→5%へ急落したとの報告を
  受け調査したところ、call_expertのプロンプト組み立て順が「変動する内容が冒頭、分量最大の
  固定指示文がその後ろ」というプレフィックスキャッシュに最も不利な構造だったことを確認。
  固定指示文を冒頭、動的データ（決定事項DB・現在タスク情報等）を末尾に配置する順序へ
  並び替えた。

参照: docs/design/back_log/BL-104/BL104_basic_design.md、
docs/design/back_log/issue_backlog.md BL-104、docs/design/decision_log.md D-085。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# _build_project_plan_toc
# ---------------------------------------------------------------------------

def test_build_project_plan_toc_empty_phases_returns_placeholder():
    assert cela_main._build_project_plan_toc([]) == "(まだフェーズ・タスク計画がありません)"


def test_build_project_plan_toc_formats_phase_and_task_titles_only():
    phases = [
        {
            "phase_id": "phase_1", "title": "前提条件の整理",
            "tasks": [
                {"task_id": "task_1_1", "title": "人口動態分析", "description": "詳細説明は含まれないはず"},
                {"task_id": "task_1_2", "title": "地理制約整理"},
            ],
        },
        {"phase_id": "phase_2", "title": "運行設計", "tasks": []},
    ]
    toc = cela_main._build_project_plan_toc(phases)
    assert "- [phase_1] 前提条件の整理" in toc
    assert "  - [task_1_1] 人口動態分析" in toc
    assert "  - [task_1_2] 地理制約整理" in toc
    assert "- [phase_2] 運行設計" in toc
    # descriptionやacceptance_criteria等の詳細はToCに含めない（軽量目次であることの確認）
    assert "詳細説明は含まれないはず" not in toc


# ---------------------------------------------------------------------------
# read_project_plan ツール
# ---------------------------------------------------------------------------

def test_read_project_plan_handler_returns_current_phases(monkeypatch):
    fake_phases = [{"phase_id": "phase_1", "title": "t", "tasks": []}]
    monkeypatch.setattr(cela_main, "_CURRENT_PHASES", fake_phases)
    result = cela_main._read_project_plan_handler({})
    assert result == fake_phases


def test_tool_dispatch_has_read_project_plan():
    assert "read_project_plan" in cela_main.TOOL_DISPATCH


def test_read_project_plan_tool_schema_present():
    assert cela_main.READ_PROJECT_PLAN_TOOL["function"]["name"] == "read_project_plan"


# ---------------------------------------------------------------------------
# call_expert: phases_json全文表示の撤去・ToC/read_project_planへの置換
# ---------------------------------------------------------------------------

def test_call_expert_no_longer_dumps_full_phases_json():
    src = inspect.getsource(cela_main.call_expert)
    assert "json.dumps(state.get(\"phases\"" not in src
    assert "_build_project_plan_toc(" in src
    assert "READ_PROJECT_PLAN_TOOL" in src
    assert "read_project_plan" in src


def test_call_expert_sets_current_phases_global():
    src = inspect.getsource(cela_main.call_expert)
    assert "_CURRENT_PHASES = state.get(\"phases\", [])" in src


# ---------------------------------------------------------------------------
# call_expert: プロンプト並び替え（固定指示文が先頭、動的データが末尾）
# ---------------------------------------------------------------------------

def test_call_expert_static_instructions_precede_dynamic_agreements_text():
    """分量最大の固定指示文ブロック（エージェントとしての行動原則）が、最も変動が
    激しいagreements_textの埋め込み位置よりソースコード上で前にあることを確認する。
    """
    src = inspect.getsource(cela_main.call_expert)
    static_idx = src.index("🔥 【エージェントとしての行動原則】")
    dynamic_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\\n{agreements_text}')
    assert static_idx < dynamic_idx


def test_call_expert_static_instructions_precede_turn_count_display():
    src = inspect.getsource(cela_main.call_expert)
    static_idx = src.index("【F-2.6 機械的検算ゲート（必須）】")
    turn_count_idx = src.index('現在は **{turn_count} ターン目**')
    assert static_idx < turn_count_idx


def test_call_expert_confirmed_provisional_block_moved_to_static_group():
    """確定値/暫定値の区別ブロックは位置的参照を持たない自己完結した指示文のため、
    固定指示文グループ（agreements_textより前）へ移動されていることを確認する。
    """
    src = inspect.getsource(cela_main.call_expert)
    confirmed_idx = src.index("🔀 【確定値と暫定値の区別（重要）】")
    dynamic_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\\n{agreements_text}')
    assert confirmed_idx < dynamic_idx


def test_call_expert_db_warning_block_stays_after_agreements_text():
    """「上記の【決定事項DB】は…」は位置的参照を持つため、agreements_textの直後という
    相対位置を維持していることを確認する（並び替えの対象外）。
    """
    src = inspect.getsource(cela_main.call_expert)
    dynamic_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\\n{agreements_text}')
    warning_idx = src.index("上記の【決定事項DB】はシステム側で自動管理されます")
    assert dynamic_idx < warning_idx


def test_call_expert_rejection_block_stays_after_whiteboard_section():
    """「上記📋セクションに示されている現在のホワイトボードは…」はR4セクション（📋）
    への位置的参照を持つため、ホワイトボード表示ブロックの後という相対位置を維持する。
    """
    src = inspect.getsource(cela_main.call_expert)
    whiteboard_idx = src.index("📋 【R4: 成果物の差分編集】")
    rejection_idx = src.index("上記📋セクションに示されている現在のホワイトボードは")
    assert whiteboard_idx < rejection_idx


# ---------------------------------------------------------------------------
# generate_user_utterance（User AI）: プロンプト並び替え
# User AIはphases_json全文表示を維持する（プロジェクトオーナーとして全体像の把握が
# 本質的に必要なため、call_expertとは異なりread_project_plan化の対象外）。
# ---------------------------------------------------------------------------

def test_generate_user_utterance_still_shows_full_phases_json():
    """User AIはcall_expertと異なりphases_json全文表示を維持する（ユーザー指定によりスコープ外）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert 'json.dumps(state.get("phases"' in src


def test_generate_user_utterance_static_stance_block_precedes_dynamic_agreements_text():
    """「発注者としてのスタンス」（自己完結・位置的参照なし）が、
    最も変動が激しいagreements_textの埋め込み位置よりソースコード上で前にあることを確認する。
    """
    src = inspect.getsource(cela_main.generate_user_utterance)
    static_idx = src.index("【発注者としてのスタンス（質について）】")
    dynamic_idx = src.index("現在までの決定事項・検討状況DB】")
    assert static_idx < dynamic_idx


def test_generate_user_utterance_anti_repetition_block_precedes_dynamic_agreements_text():
    src = inspect.getsource(cela_main.generate_user_utterance)
    static_idx = src.index("【同じ検証・計算を繰り返さない（重要）】")
    dynamic_idx = src.index("現在までの決定事項・検討状況DB】")
    assert static_idx < dynamic_idx


def test_generate_user_utterance_mandatory_rules_block_precedes_scope_block():
    """「厳守事項」は「後述の【現在のタスクで未充足の要求項目】」「【R4: 現在のホワイトボード】」
    への位置的参照（前方参照）を持つため、それらを含むスコープブロックより前という
    相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.generate_user_utterance)
    rules_idx = src.index("後述の【現在のタスクで未充足の要求項目】")
    scope_idx = src.index("【現在のタスクで未充足の要求項目（これ以外を新たに追加要求しないこと）】")
    assert rules_idx < scope_idx


def test_generate_user_utterance_bl094_block_stays_after_scope_block():
    """「上記の【この値は確定済みです】は…」はスコープブロックの確定値表示への
    位置的参照（後方参照）を持つため、スコープブロックの後という相対位置を維持する。
    """
    src = inspect.getsource(cela_main.generate_user_utterance)
    scope_idx = src.index("【この値は確定済みです。再導出を指示・要求しないでください】")
    bl094_idx = src.index("上記の【この値は確定済みです】は現在タスクに関連する確定値の一部にすぎません")
    assert scope_idx < bl094_idx


# ---------------------------------------------------------------------------
# call_detector: domain_promptの並び替え（固定指示文が先頭、動的データが末尾）
# ---------------------------------------------------------------------------

def test_call_detector_domain_prompt_static_blocks_precede_dynamic_history_text():
    """気づき欄・write_issue説明・ツール一覧（自己完結・位置的参照なし）が、
    最も変動が激しいhistory_text（今回評価するやり取り本文）の埋め込み位置より
    ソースコード上で前にあることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    static_idx = src.index("【BL-051軽量版: 気づき欄】constraint_issueの判定")
    dynamic_idx = src.index("【今回評価するターンのやり取り】\\n{history_text}")
    assert static_idx < dynamic_idx


def test_call_detector_domain_prompt_bl076_block_stays_after_whiteboard_block():
    """「上記ホワイトボードの本文から」はwhiteboard_blockへの位置的参照を持つため、
    whiteboard_blockの後という相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    whiteboard_idx = src.index('f"{whiteboard_block}"')
    bl076_idx = src.index("上記ホワイトボードの本文から")
    assert whiteboard_idx < bl076_idx


def test_call_detector_domain_prompt_tool_list_precedes_frozen_agreements():
    """ツール一覧説明（固定）が、Freeze状況テキスト（実行中に変化しうる動的データ）より
    ソースコード上で前にあることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    static_idx = src.index("あなたが使えるツールはread_verified_fact")
    dynamic_idx = src.index("_get_frozen_agreements_text(get_active_conn()")
    assert static_idx < dynamic_idx


# ---------------------------------------------------------------------------
# call_detector: 数値監査パス（第2段のprompt変数）の並び替え
# ---------------------------------------------------------------------------

def _numeric_prompt_start(src: str) -> int:
    """call_detectorのソース中、数値監査パス用promptの開始位置（軸1/軸2の定義文、
    domain_promptには存在しないためユニークなマーカー）を返す。
    """
    return src.index("以下の2軸は**完全に独立した別の評価軸**です")


def test_call_detector_numeric_prompt_axis_definitions_precede_goal():
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    goal_idx = src.index('System Goal: {goal}\\n', start)
    assert start < goal_idx


def test_call_detector_numeric_prompt_goal_precedes_agreements_text():
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    goal_idx = src.index('System Goal: {goal}\\n', start)
    agreements_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB】\\n{agreements_text}', start)
    assert goal_idx < agreements_idx


def test_call_detector_numeric_prompt_history_text_is_last_dynamic_block():
    """今回評価するターンのやり取り（history_text）は最も変動が激しいため、
    決定事項DB・ホワイトボードより後、JSON出力指示の直前という末尾に配置されていることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    agreements_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB】\\n{agreements_text}', start)
    history_idx = src.index('【今回評価するターンのやり取り】', start)
    schema_idx = src.index('Return ONLY JSON: {{"risk"', start)
    assert agreements_idx < history_idx < schema_idx


def test_call_detector_numeric_prompt_thought_process_audit_stays_after_python_calls_block():
    """thought_process_auditの「上記のBL-033機械的検算記録と突き合わせて」はpython_calls_block
    への位置的参照を持つため、python_calls_blockの後という相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    python_calls_idx = src.index('f"{python_calls_block}\\n"', start)
    thought_audit_idx = src.index('f"{thought_process_audit}\\n"', start)
    assert python_calls_idx < thought_audit_idx


def test_call_detector_numeric_prompt_bl076_block_stays_after_whiteboard_block():
    """数値監査パスのBL-076（「上記ホワイトボードの本文から」）もwhiteboard_blockの後という
    相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    whiteboard_idx = src.index('f"{whiteboard_block}"', start)
    bl076_idx = src.index("上記ホワイトボードの本文から", start)
    assert whiteboard_idx < bl076_idx


def test_call_detector_numeric_prompt_bl086_bl062_stay_after_agreements_text():
    """BL-086/BL-062はいずれも「上記DB」（agreements_text）への位置的参照を持つため、
    agreements_textの後という相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_detector)
    start = _numeric_prompt_start(src)
    agreements_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB】\\n{agreements_text}', start)
    bl086_idx = src.index("上記DBで🔒アイコンが付いている項目は", start)
    bl062_idx = src.index("その原因が上記DB内の", start)
    assert agreements_idx < bl086_idx < bl062_idx


# ---------------------------------------------------------------------------
# call_orchestrator: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_orchestrator_static_instruction_precedes_user_input():
    src = inspect.getsource(cela_main.call_orchestrator)
    static_idx = src.index("Taskを遂行するために最も適した専門家の肩書き")
    dynamic_idx = src.index('Task(ユーザーAIの指示): {state["user_input"]}')
    assert static_idx < dynamic_idx


def test_call_orchestrator_user_input_precedes_agreements_and_history():
    src = inspect.getsource(cela_main.call_orchestrator)
    user_input_idx = src.index('Task(ユーザーAIの指示): {state["user_input"]}')
    agreements_idx = src.index("{agreements_text}\\n")
    history_idx = src.index("{history_text}\\n")
    assert user_input_idx < agreements_idx < history_idx


# ---------------------------------------------------------------------------
# call_resource_arbiter: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_resource_arbiter_static_instructions_precede_goal_and_overrun():
    src = inspect.getsource(cela_main.call_resource_arbiter)
    static_idx = src.index("【F-2.6 機械的検算ゲート（必須）】予算超過判定は")
    goal_idx = src.index("■ 目標: {goal}")
    overrun_idx = src.index("リソース「{overrun['constraint']}」が")
    assert static_idx < goal_idx < overrun_idx


# ---------------------------------------------------------------------------
# call_reflection: BL-093の説明を固定ブロックへ移動（最小限の安全な変更のみ）
# ---------------------------------------------------------------------------

# [BL-109] call_reflection/call_facilitatorはtools=[THINK_TOOL]をtools=None（単一応答パス）へ
# 差し戻したのに伴い「【BL-093】必要であれば、thinkツールで検討過程を書き残しても構いません。」の
# 文言自体を両関数から削除したため、その位置関係を検証していた
# test_call_reflection_bl093_mentioned_exactly_once_near_top / test_call_facilitator_bl093_precedes_reflection_block
# は前提が消滅し廃止した。unresolved_textとの相対位置に関する制約は元々BL-093文言側にのみ
# あったものなので、削除に伴い検証対象自体がなくなっている。


# ---------------------------------------------------------------------------
# call_facilitator: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_facilitator_called_reason_reference_still_precedes_reflection_block():
    """「※あなたが呼ばれた理由（下記）は」はreflection_blockへの前方参照のため、
    reflection_blockより前という相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_facilitator)
    ref_idx = src.index("※あなたが呼ばれた理由（下記）は")
    reflection_block_idx = src.index("{reflection_block}")
    assert ref_idx < reflection_block_idx


# ---------------------------------------------------------------------------
# call_integrator: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_integrator_static_instructions_precede_goal_and_merged_text():
    """[BL-115] 検証回数抑制注意書きは共有ヘルパー_verification_throttle_warning()へ
    集約されたため、呼び出し式そのものを静的ブロックの位置マーカーとして使う。"""
    src = inspect.getsource(cela_main.call_integrator)
    static_idx = src.index("_verification_throttle_warning()")
    goal_idx = src.index("■ 目標: {goal}")
    merged_idx = src.index("{merged_text}")
    assert static_idx < goal_idx < merged_idx


# ---------------------------------------------------------------------------
# call_reviewer: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_reviewer_static_instructions_precede_goal_and_deliverable_text():
    src = inspect.getsource(cela_main.call_reviewer)
    static_idx = src.index("【F-2.6 機械的検算ゲート（必須）】成果物中の数値的主張")
    goal_idx = src.index("■ 達成すべき【目標(Goal)】:")
    deliverable_idx = src.index("{deliverable_text}")
    assert static_idx < goal_idx < deliverable_idx


# ---------------------------------------------------------------------------
# call_task_plan_reviewer: プロンプト並び替え
# ---------------------------------------------------------------------------

def test_call_task_plan_reviewer_static_criteria_precede_goal_and_phases_json():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    static_idx = src.index("1. 曖昧な表記")
    goal_idx = src.index("■ 目標: {goal}")
    phases_json_idx = src.index("{phases_json}")
    assert static_idx < goal_idx < phases_json_idx


def test_call_task_plan_reviewer_bl092_uekara_reference_stays_after_ambiguity_block():
    """BL-092内の「上記の通り数値の捏造要求はしないこと」は曖昧さ混同注意ブロックへの
    位置的参照を持つため、そのブロックの後という相対位置を維持していることを確認する。
    """
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    ambiguity_idx = src.index("【重要: 曖昧さの指摘とゴール文にない数値の捏造要求を混同しない】")
    bl092_reference_idx = src.index("上記の通り数値の捏造要求はしないこと")
    assert ambiguity_idx < bl092_reference_idx


# ---------------------------------------------------------------------------
# [BL-116] generate_user_utterance: ゴミ引用符混入バグの再発防止
# ---------------------------------------------------------------------------

def test_generate_user_utterance_first_turn_block_has_no_stray_quote_artifacts():
    """[BL-116] triple-quoted f-string内で各行が誤って個別に閉じられているかのように
    書かれ、`\\n`直後のリテラルな引用符（例: `...です。\\n"`）がプロンプト本文へそのまま
    混入していたバグ（2026-07-30発見・修正）の再発防止。修正前はこの断片の直後に
    孤立した`"`が続いていた。
    """
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert 'あなたは目標を達成するための優秀な【プロジェクトオーナー（発注者）】です。\\n"' not in src
    assert 'あなたは目標を達成するための優秀な【プロジェクトオーナー（発注者）】です。\\n' in src


def test_generate_user_utterance_decisions_timeline_block_has_no_stray_quote_artifacts():
    """[BL-116] 決定事項・タイムラインブロック（system_prompt += (f\"\"\"...\"\"\")）でも
    同種のゴミ引用符混入が発生していた箇所の再発防止。
    """
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert '【直近の各役割の行動、評価、その理由リスト】"\\n' not in src
    assert '{timeline_str}"\\n\\n' not in src
