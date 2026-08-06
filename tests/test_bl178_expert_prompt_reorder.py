"""
BL-178: call_expertのsystem_prompt（フル版）／light_system_prompt（軽量版）を
「視座は上から下、文脈は過去から現在」の順に再構成し、Detectorの差し戻し情報を
両方で真に最後に読ませる回帰テスト。

背景:
- ユーザーが実ログ（log/2026-08-05/1049/log_with_prompt.md）を精読した結果、差し戻し
  ブロックがsystem_promptの中盤にある一方、messages配列では[system, ...chat_history]
  という構造上chat_historyの末尾メッセージが常に物理的に後ろへ来るため、Expertが
  Detectorの指摘を汲み取れていない実例を確認した。
- 対応として、system_promptを`system_prompt_leading`（静的指示文＋過去〜現在の文脈）と
  `system_prompt_trailing`（決定事項DB→厳守事項→差し戻し）の2つに分割し、messages配列を
  [leading, ...chat_history, trailing]の3部構成にした（差し戻し情報をchat_historyより
  後ろへ配置することで、初めて構造的に「最後に読ませる」を実現する）。
- light_system_prompt（ツールループiter=2以降の軽量版）にも、従来存在しなかった厳守事項・
  Detectorからの差し戻し情報を新規追加し、ユーザー提示の11項目順へ並び替えた。

参照: docs/design/back_log/BL-178/BL178_basic_design.md、
docs/design/back_log/issue_backlog.md BL-178、docs/design/decision_log.md D-147。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# ソースコード上の並び順・新規ブロックの存在確認
# ---------------------------------------------------------------------------

def test_system_prompt_split_into_leading_and_trailing_variables():
    src = inspect.getsource(cela_main.call_expert)
    assert "system_prompt_leading" in src
    assert "system_prompt_trailing" in src


def test_leading_block_order_goal_before_plan_toc_before_intro():
    """[BL-178] leading（chat_historyより前）の新順序: ゴール → プロジェクト計画目次 →
    「文脈の参考として...」導入文。ユーザー指定順（旧項目番号11→13→20）。"""
    src = inspect.getsource(cela_main.call_expert)
    goal_idx = src.index("【あなたの絶対的な行動指針】")
    plan_toc_idx = src.index("📊 [プロジェクト進行計画 目次]")
    intro_idx = src.index("文脈の参考として以下に直近の会話を示します")
    assert goal_idx < plan_toc_idx < intro_idx


def test_leading_block_hydrate_context_precedes_intro_sentence():
    """[BL-178] 「以下は直近の会話です」という予告の直後に実際の直近raw chat_historyが
    来るよう、hydrate_context（過去の圧縮ログ）は導入文より前に配置する。"""
    src = inspect.getsource(cela_main.call_expert)
    hydrate_idx = src.index("【過去の会話を圧縮したシステム判断ログ】")
    intro_idx = src.index("文脈の参考として以下に直近の会話を示します")
    assert hydrate_idx < intro_idx


def test_trailing_block_order_matches_user_specified_sequence():
    """[BL-178] trailing（chat_historyより後ろ）の新順序（ユーザー指定、旧項目番号
    22→12→16→17→19→14→15→10→21→23→18）: 決定事項DB → Detectorの気づき → 申し送り →
    エスカレーション状況 → エスカレーション再開通知 → スコープ（現在のタスク） →
    ホワイトボード → Orchestratorの着眼点 → 制限時間 → 厳守事項 → 差し戻し。
    エスカレーション状況・申し送り・差し戻しは条件付きブロックのためソース順のみ検証する。"""
    src = inspect.getsource(cela_main.call_expert)
    trailing_start_idx = src.index('system_prompt_trailing += f"\\n【プロジェクトの合意')
    db_idx = src.index('【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\\n{agreements_text}', trailing_start_idx)
    detector_idx = src.index("_build_detector_observations_block(state)", trailing_start_idx)
    deferred_idx = src.index("📌 【BL-082: 他タスクからの申し送り事項（先送り）】", trailing_start_idx)
    escalation_status_idx = src.index("_escalation_status_text", deferred_idx)
    escalation_resume_idx = src.index("_build_escalation_resume_notice(state)", trailing_start_idx)
    scope_idx = src.index("📏 【回答のスコープについて（厳守）】", trailing_start_idx)
    whiteboard_idx = src.index("📋 【R4: 成果物の差分編集】", trailing_start_idx)
    focus_idx = src.index("🎯 【このタスクで特に注意すべき観点（Orchestratorより）】", trailing_start_idx)
    turn_count_idx = src.index("⏳ 【制限時間】", trailing_start_idx)
    kensyu_idx = src.index("上記の【決定事項DB】はシステム側で自動管理されます", trailing_start_idx)
    rejection_idx = src.index("⚠️ 【重要：Detectorからの差し戻し】", trailing_start_idx)
    assert (
        trailing_start_idx < db_idx < detector_idx < deferred_idx < escalation_status_idx
        < escalation_resume_idx < scope_idx < whiteboard_idx < focus_idx < turn_count_idx
        < kensyu_idx < rejection_idx
    )


def test_leading_block_does_not_contain_trailing_only_blocks():
    """DB・Detectorの気づき・スコープ・ホワイトボード・Orchestratorの着眼点は
    すべてtrailing側に移動しており、leading側の組み立てコード（ゴール〜導入文の間）
    には登場しないことを確認する。"""
    src = inspect.getsource(cela_main.call_expert)
    leading_start_idx = src.index("system_prompt_leading = system_prompt")
    intro_idx = src.index("文脈の参考として以下に直近の会話を示します")
    leading_build_src = src[leading_start_idx:intro_idx]
    assert "_build_detector_observations_block" not in leading_build_src
    assert "📋 【R4: 成果物の差分編集】" not in leading_build_src
    assert "🎯 【このタスクで特に注意すべき観点" not in leading_build_src


def test_messages_append_trailing_system_message_after_chat_history_branches():
    """messages.append({"role": "system", "content": system_prompt_trailing})が
    どちらのis_stateless_mode分岐（if/else）よりもソースコード上で後にあることを確認する。"""
    src = inspect.getsource(cela_main.call_expert)
    else_branch_idx = src.rindex("for msg in state[\"chat_history\"]:")
    trailing_append_idx = src.index('messages.append({"role": "system", "content": system_prompt_trailing})')
    assert else_branch_idx < trailing_append_idx


def test_light_system_prompt_order_task_info_before_tool_list_before_individual_tools():
    """[BL-178] 軽量版の新順序: 現在のタスク情報 → ツール一覧の明示 → 個別ツール説明。
    現行(BL-104時代)はツール一覧が末尾にあったが、先頭寄りへ移動した。"""
    src = inspect.getsource(cela_main.call_expert)
    task_info_idx = src.index('f"【現在のタスク】\\n{current_task_json}\\n\\n"')
    tool_list_idx = src.index("【重要】あなたが使えるツールはpython_repl")
    escalate_idx = src.index("[BL-086] ゴール文の制約そのものが真の目的と矛盾している")
    assert task_info_idx < tool_list_idx < escalate_idx


def test_light_system_prompt_python_repl_mandate_comes_after_individual_tool_descriptions():
    """python_repl必須の一言は、個別ツール説明群（BL-086〜BL-093）より後ろへ移動した。"""
    src = inspect.getsource(cela_main.call_expert)
    think_idx = src.index("[BL-093] thinkツールで検討過程を残せます")
    python_repl_idx = src.index("数値的根拠は python_repl ツールで検算し、暗算での提示は禁止します。\\n")
    assert think_idx < python_repl_idx


def test_light_system_prompt_new_kensyu_block_has_no_dangling_reference():
    """[BL-178] 軽量版の厳守事項はフル版と異なりDBブロックが存在しないため、
    「上記の」という空参照を持たない独立文であることを確認する。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "決定事項DBはシステム側で自動管理されます。あなたの回答内でDBのブロックを" in src
    # フル版の「上記の【決定事項DB】は」という後方参照文言が、軽量版側では使われていない
    # （軽量版の厳守事項ブロックが独自の書き換え文言を持つことの確認）。
    light_start_idx = src.index("light_system_prompt = (")
    light_kensyu_idx = src.index("⚠️ 【厳守事項】決定事項DBはシステム側で自動管理されます", light_start_idx)
    assert light_kensyu_idx > light_start_idx


def test_light_system_prompt_rejection_block_conditioned_on_drift_or_major():
    src = inspect.getsource(cela_main.call_expert)
    light_start_idx = src.index("light_system_prompt = (")
    rejection_guard_idx = src.index(
        'if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:', light_start_idx
    )
    rejection_text_idx = src.index("⚠️ 【重要：Detectorからの差し戻し】あなたの前回の発言はDetectorにより差し戻されました。")
    assert light_start_idx < rejection_guard_idx < rejection_text_idx


def test_light_system_prompt_whiteboard_precedes_rejection_block():
    """軽量版でも「上記のホワイトボード本文には...」という後方参照が成立するよう、
    ホワイトボード表示が差し戻しブロックより前にあることを確認する。"""
    src = inspect.getsource(cela_main.call_expert)
    whiteboard_idx = src.index('f"\\n[R4] {whiteboard_text}\\n"')
    rejection_idx = src.index("上記のホワイトボード本文には「> 🔴")
    assert whiteboard_idx < rejection_idx


# ---------------------------------------------------------------------------
# 実行時のmessages/light_system_prompt構造確認
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl178.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def _minimal_expert_state(run_id: str, **overrides) -> dict:
    phase = {
        "phase_id": "phase_1",
        "title": "テストフェーズ",
        "tasks": [
            {
                "task_id": "task_1_1",
                "title": "テストタスク",
                "description": "テスト用の説明",
                "acceptance_criteria": ["基準A"],
                "depends_on": [],
                "owns_variables": ["変数A"],
            }
        ],
    }
    state = {
        "run_id": run_id,
        "goal": "テストゴール文",
        "user_input": "",
        "turn_count": 1,
        "chat_history": [
            {"role": "user", "content": "task_1_1を実施してください"},
            {"role": "assistant", "content": "前回の成果物です"},
        ],
        "phases": [phase],
        "current_phase": phase,
        "current_task_id": "task_1_1",
        "task_criteria_status": {},
        "expert_focus_guidance": "",
        "drift_flag": False,
        "constraint_issue": "none",
        "constraint_issue_log": [],
        "expert_retry_count": 0,
        "expert_output": "(取得不可)",
        "selected_expert": "テスト専門家",
    }
    state.update(overrides)
    return state


def _minimal_config() -> dict:
    return {
        "agent_has_guardrail": True,
        "initial_max_turnval": 30,
        "is_stateless_mode": False,
        "chat_history_window": 4,
    }


def test_call_expert_messages_is_three_part_leading_history_trailing(db_conn, monkeypatch):
    """[BL-178] 実行時にcall_expertが構築するmessages配列が
    [system(leading), ...chat_history, system(trailing)]の3部構成になっていることを確認する。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["messages"] = messages
        captured["light_system_prompt"] = light_system_prompt
        return "テスト成果物"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    state = _minimal_expert_state(run_id)
    config = _minimal_config()
    cela_main.call_expert("テスト専門家", state, config)

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "system"
    assert messages[1:-1] == state["chat_history"]
    # 決定事項DB・厳守事項は末尾のtrailingメッセージ側にのみ存在する
    assert "【プロジェクトの合意・決定事項・検討状況DB" in messages[-1]["content"]
    assert "⚠️ 【厳守事項】" in messages[-1]["content"]
    assert "【プロジェクトの合意・決定事項・検討状況DB" not in messages[0]["content"]


def test_call_expert_trailing_message_contains_rejection_block_only_when_drift(db_conn, monkeypatch):
    """差し戻し情報は、drift_flag/constraint_issue=="major"の場合のみ末尾メッセージへ
    含まれ、通常ターンでは出現しないことを確認する。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["messages"] = messages
        return "テスト成果物"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    config = _minimal_config()

    # 通常ターン: 差し戻しブロックは出現しない
    normal_state = _minimal_expert_state(run_id)
    cela_main.call_expert("テスト専門家", normal_state, config)
    assert "Detectorからの差し戻し" not in captured["messages"][-1]["content"]

    # 差し戻しターン: 末尾メッセージに含まれる
    retry_state = _minimal_expert_state(
        run_id,
        constraint_issue="major",
        constraint_issue_log=["労基法違反の疑い"],
        expert_output="却下された前回の提案",
    )
    cela_main.call_expert("テスト専門家", retry_state, config)
    assert "Detectorからの差し戻し" in captured["messages"][-1]["content"]
    assert "却下された前回の提案" in captured["messages"][-1]["content"]


def test_call_expert_light_system_prompt_contains_kensyu_and_conditional_rejection(db_conn, monkeypatch):
    """light_system_promptに厳守事項が常に含まれ、差し戻し情報はdrift/major時のみ
    含まれることを確認する。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["light_system_prompt"] = light_system_prompt
        return "テスト成果物"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    config = _minimal_config()

    normal_state = _minimal_expert_state(run_id)
    cela_main.call_expert("テスト専門家", normal_state, config)
    normal_light = captured["light_system_prompt"]
    assert "⚠️ 【厳守事項】" in normal_light
    assert "Detectorからの差し戻し" not in normal_light

    retry_state = _minimal_expert_state(
        run_id,
        constraint_issue="major",
        constraint_issue_log=["労基法違反の疑い"],
    )
    cela_main.call_expert("テスト専門家", retry_state, config)
    retry_light = captured["light_system_prompt"]
    assert "⚠️ 【厳守事項】" in retry_light
    assert "Detectorからの差し戻し" in retry_light
