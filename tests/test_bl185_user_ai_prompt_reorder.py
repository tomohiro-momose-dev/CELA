"""
BL-185: generate_user_utterance（User AIの単発呼び出しパス。差し戻し再送・初回ターン・
本質対話応答・Expert相談応答・終盤のPROJECT_COMPLETE宣言ターンで使われる。通常の
Expertレビューターンで使われるStage1-4パイプラインは_is_normal_review_turnにより除外され
対象外）のsystem_promptを「視座は上から下、文脈は過去から現在」の順に再構成し、
Detectorの差し戻し情報・エスカレーション再開通知・タスク遷移ブロック通知を
真に最後（chat_historyより後ろ）に読ませる回帰テスト。BL-178でcall_expertに導入した
のと同型のリファクタリング。

背景:
- ユーザーが実ログ（log/2026-08-06/1149）を精読した結果、Detectorがmajor判定で
  差し戻した直後のUser AIの最初の思考が、差し戻された事実に一切触れず、削除された
  はずの「前回の完了宣言」をそのまま一字一句繰り返していた実害を確認した。
- 根本原因は、差し戻し通知がsystem_promptの中盤（🚨最終盤の超重要指示・
  エスカレーション再開通知・タスク遷移ブロック通知よりも前）に配置されていたのに対し、
  messages配列は[system, ...chat_history]という構造上chat_history側が常に物理的に
  後ろへ来るため、chat_history_window=4件の直近の会話（Expertの長大な完了報告等）に
  差し戻し通知が埋もれていたこと。
- 対応として、system_promptを`system_prompt_leading`（静的指示文＋過去〜現在の文脈）と
  `system_prompt_trailing`（決定事項DB→エスカレーション通知→タスク遷移通知→最終盤指示→
  差し戻し通知（最後））の2つに分割し、messages配列を[leading, ...chat_history, trailing]
  の3部構成にした。あわせてユーザー指示により、エスカレーション再開通知・タスク遷移
  ブロック通知は差し戻し以外の通常の単発呼び出しパスでも常にtrailing側（chat_historyより
  後ろ）に配置されるようにした。

参照: docs/design/back_log/BL-185/BL185_basic_design.md（予定）、
docs/design/back_log/issue_backlog.md BL-185、docs/design/decision_log.md D-154（予定）。
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
# ソースコード上の並び順・新規変数の存在確認
# ---------------------------------------------------------------------------

def _fallback_src() -> str:
    """generate_user_utteranceのソースのうち、_is_normal_review_turn分岐（Stage1-4
    パイプライン）を除いた、単発呼び出しパス（本BLの対象）だけを切り出す。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    marker = "# ここから先は実行中に変化する動的な内容。[BL-185]"
    start = src.index(marker)
    return src[start:]


def test_system_prompt_split_into_leading_and_trailing_variables():
    src = _fallback_src()
    assert "system_prompt_leading = system_prompt" in src
    assert 'system_prompt_trailing = ""' in src


def test_trailing_block_order_db_before_notices_before_final_turn_before_rejection():
    """[BL-185] trailingの新順序: 決定事項DB → エスカレーション再開通知 →
    タスク遷移ブロック通知 → 最終盤の超重要指示 → 差し戻し通知（最後）。"""
    src = _fallback_src()
    db_idx = src.index("現在までの決定事項・検討状況DB")
    escalation_resume_idx = src.index("_build_escalation_resume_notice(state)")
    transition_blocked_idx = src.index("_build_task_transition_blocked_notice(state)")
    final_turn_idx = src.index("🚨 【最終盤の超重要指示】")
    rejection_idx = src.index("⚠️ 【重要】")
    assert db_idx < escalation_resume_idx < transition_blocked_idx < final_turn_idx < rejection_idx


def test_rejection_block_is_last_append_to_trailing_before_messages_append():
    """[BL-185] 差し戻し通知ブロックが、system_prompt_trailingへの最後の追記であり、
    その直後にmessages.append({"role": "system", "content": system_prompt_trailing})が
    続くことを確認する（＝trailing全体の最後に位置する）。"""
    src = _fallback_src()
    rejection_idx = src.index('if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:')
    # 差し戻しブロックの後、他のsystem_prompt_trailing += は一切登場しないこと
    after_rejection = src[rejection_idx:]
    assert after_rejection.count("system_prompt_trailing +=") == 1  # 差し戻しブロック自身の1回のみ
    messages_leading_idx = src.index('messages = [{"role": "system", "content": system_prompt_leading}]')
    trailing_append_idx = src.index('messages.append({"role": "system", "content": system_prompt_trailing})')
    assert rejection_idx < messages_leading_idx < trailing_append_idx


def test_final_turn_instruction_mentions_rejection_priority():
    """[BL-185] 🚨最終盤の超重要指示に、差し戻し対応を優先すべき旨の注記が
    追加されていることを確認する（プロジェクト完了宣言による差し戻し無視の防止）。"""
    src = _fallback_src()
    final_turn_idx = src.index("🚨 【最終盤の超重要指示】")
    final_turn_block = src[final_turn_idx:final_turn_idx + 1500]
    assert "差し戻し" in final_turn_block
    assert "拙速にプロジェクト完了" in final_turn_block


def test_rejection_block_mentions_final_turn_priority():
    """[BL-185] 差し戻し通知ブロック自体にも「最終盤指示より差し戻し対応を優先せよ」
    という注記があることを確認する（両方向から矛盾を防ぐ）。"""
    src = _fallback_src()
    rejection_idx = src.index("⚠️ 【重要】")
    rejection_block = src[rejection_idx:rejection_idx + 2500]
    assert "最優先" in rejection_block
    assert "完了宣言で押し切ろうと" in rejection_block


def test_messages_leading_uses_system_prompt_leading_variable():
    src = _fallback_src()
    assert 'messages = [{"role": "system", "content": system_prompt_leading}]' in src


def test_messages_trailing_append_after_both_history_branches():
    """messages.append({"role": "system", "content": system_prompt_trailing})が
    is_stateless_mode / else の両分岐よりもソースコード上で後にあることを確認する。"""
    src = _fallback_src()
    else_branch_idx = src.rindex('for msg in state["chat_history"]:')
    trailing_append_idx = src.index('messages.append({"role": "system", "content": system_prompt_trailing})')
    assert else_branch_idx < trailing_append_idx


# ---------------------------------------------------------------------------
# 実行時のmessages構造確認
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl185.db")
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


def _minimal_user_state(run_id: str, **overrides) -> dict:
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
        "user_input": "(取得不可)",
        "turn_count": 6,
        "max_turns": 30,
        "round_count": 1,
        "chat_history": [],
        "phases": [phase],
        "current_phase": phase,
        "current_task_id": "task_1_1",
        "task_criteria_status": {},
        "drift_flag": False,
        "constraint_issue": "none",
        "constraint_issue_log": [],
        "user_retry_count": 0,
        "essence_dialogue_active": False,
        "expert_pending_question": "",
        "expert_output": "(取得不可)",
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "",
    }
    state.update(overrides)
    return state


def _minimal_config() -> dict:
    return {
        "user_always_remember": True,
        "initial_max_turnval": 30,
        "is_stateless_mode": False,
        "chat_history_window": 4,
    }


def test_generate_user_utterance_messages_is_three_part_leading_history_trailing(db_conn, monkeypatch):
    """[BL-185] 初回ターン（chat_history=[]、_is_normal_review_turn=False）で
    messages配列が[system(leading), system(trailing)]の構成になり、
    決定事項DB等がtrailing側にのみ存在することを確認する。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, state=None):
        captured["messages"] = messages
        return "テスト発言"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    state = _minimal_user_state(run_id, chat_history=[])
    config = _minimal_config()
    cela_main.generate_user_utterance(state, config)

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "system"
    assert "現在までの決定事項・検討状況DB" in messages[-1]["content"]
    assert "現在までの決定事項・検討状況DB" not in messages[0]["content"]


def test_generate_user_utterance_rejection_retry_puts_notice_in_trailing_after_history(db_conn, monkeypatch):
    """[BL-185] 差し戻し再送ターン（constraint_issue="major"）で、差し戻し通知が
    messages配列の最後（chat_historyより後ろ）のtrailingメッセージに含まれ、
    先頭のleadingメッセージには含まれないことを確認する。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, state=None):
        captured["messages"] = messages
        return "テスト発言"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    state = _minimal_user_state(
        run_id,
        chat_history=[
            {"role": "user", "content": "task_6_1の成果物を承認します。プロジェクトを完了とします。"},
            {"role": "assistant", "content": "Expertの最終報告です。"},
        ],
        constraint_issue="major",
        constraint_issue_log=["労基法違反の疑いと予備費ゼロ"],
        user_input="プロジェクトを完了とします。",
    )
    config = _minimal_config()
    cela_main.generate_user_utterance(state, config)

    messages = captured["messages"]
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "system"
    assert "Detector（監査システム）により差し戻されました" in messages[-1]["content"]
    assert "Detector（監査システム）により差し戻されました" not in messages[0]["content"]
    # 差し戻し通知の中に、却下された前回発話（履歴からは削除済）が引用されていること
    assert "プロジェクトを完了とします。" in messages[-1]["content"]


def test_generate_user_utterance_no_rejection_block_on_normal_turn(db_conn, monkeypatch):
    """通常ターン（constraint_issue="none"）では差し戻し通知がmessagesに一切
    出現しないことを確認する（非退行確認）。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_ai(messages, client, model, label="Unknown Node", tools=None, state=None):
        captured["messages"] = messages
        return "テスト発言"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    state = _minimal_user_state(run_id, chat_history=[])
    config = _minimal_config()
    cela_main.generate_user_utterance(state, config)

    messages = captured["messages"]
    joined = "\n".join(m["content"] for m in messages)
    assert "Detector（監査システム）により差し戻されました" not in joined
