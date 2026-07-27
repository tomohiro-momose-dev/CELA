"""
BL-103: hydrate（ノード間コンテキスト引き継ぎ）の改善。

ユーザーからhydrate設計の相談を受け、ユーザー自身が過去に設計したNPU-Context-Saver
（C:\\ai_work\\NPU-Context-Saver、pin・Time-Aware RAG・トークン予算による段階的間引き）
のhydrate機構と対比した結果、以下を実装する:

1. issue_logのescalated行をhydrate_contextへ常時マージするpin（_build_escalation_pin_text）。
   facilitatorのフィードバックはchat_history末尾追記のみでchat_history_window超過後に
   消えるため、call_expert/generate_user_utteranceのambient contextへ毎ターンDBから
   直接注入し「発言が消えた後の穴埋め」とする。
2. BL-093のthinkツール最終呼び出し内容（decided/why）をdecisions.whyに採用し、
   生テキスト先頭100文字の機械的truncationだった劣化版要約を改善する
   （新設get_last_think_summary()）。
3. 従来generate_user_utterance_nodeがUser AIの発言を一度もdecisionsテーブルに
   記録しておらず、hydrate要約チャネルから完全に欠落していた非対称を解消する。
4. generate_user_utterance内の独自インラインタイムラインがget_decisions_from_dbの
   全件を無制限に展開しておりExpert側の窓付き_build_hydrate_context_from_dbと
   非対称だった問題を、共通ヘルパーへの統一で解消する。

参照: docs/design/back_log/BL-103/BL103_basic_design.md、
docs/design/back_log/issue_backlog.md BL-103、docs/design/decision_log.md D-084。
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


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl103_hydrate.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        conn.close()


@pytest.fixture(autouse=True)
def _reset_think_scratchpad_around_test():
    cela_main._reset_think_scratchpad()
    yield
    cela_main._reset_think_scratchpad()


# ---------------------------------------------------------------------------
# get_last_think_summary()
# ---------------------------------------------------------------------------

def test_get_last_think_summary_empty_scratchpad_returns_empty_string():
    assert cela_main.get_last_think_summary() == ""


def test_get_last_think_summary_prefers_decided_and_why():
    cela_main._think_handler({
        "action": "a", "summary": "s",
        "decided": "task_1_2承認、task_1_3へ進む",
        "why": "3項目すべて充足",
    })
    assert cela_main.get_last_think_summary() == "task_1_2承認、task_1_3へ進む（3項目すべて充足）"


def test_get_last_think_summary_falls_back_to_summary_when_decided_empty():
    cela_main._think_handler({"action": "確認中", "summary": "検算を継続中"})
    assert cela_main.get_last_think_summary() == "検算を継続中"


def test_get_last_think_summary_uses_last_entry_only():
    cela_main._think_handler({"action": "a1", "summary": "s1", "decided": "d1", "why": "w1"})
    cela_main._think_handler({"action": "a2", "summary": "s2", "decided": "d2", "why": "w2"})
    assert cela_main.get_last_think_summary() == "d2（w2）"


# ---------------------------------------------------------------------------
# _build_escalation_pin_text()
# ---------------------------------------------------------------------------

def test_build_escalation_pin_text_empty_when_no_escalated_issues(db_conn):
    conn, run_id = db_conn
    assert cela_main._build_escalation_pin_text(conn, run_id) == ""


def test_build_escalation_pin_text_formats_escalated_rows(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    for _ in range(2):
        cela_main._write_issue_impl(
            {"action_type": "CREATE", "topic": "operator_shortage_peak", "severity": "minor",
             "description": "ピーク時のオペレーター不足"},
            conn, run_id, "detector",
        )
    text = cela_main._build_escalation_pin_text(conn, run_id)
    assert "operator_shortage_peak" in text
    assert "ピーク時のオペレーター不足" in text
    assert "累積2回発生" in text
    assert "raised_by=detector" in text


# ---------------------------------------------------------------------------
# expert_node: why=get_last_think_summary()
# ---------------------------------------------------------------------------

def test_expert_node_uses_last_think_summary_for_decision_why(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "成果物本文")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    cela_main._think_handler({
        "action": "a", "summary": "s",
        "decided": "task_1_1完了と判断", "why": "3項目すべて充足",
    })
    state = {
        "chat_history": [], "expert_retry_count": 0, "constraint_issue": "none",
        "constraint_issue_log": [], "selected_expert": "テスト専門家",
        "run_id": run_id, "current_task_id": "task_1_1",
    }
    cela_main.expert_node(state)
    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert len(decisions) == 1
    assert decisions[0]["why"] == "task_1_1完了と判断（3項目すべて充足）"


def test_expert_node_falls_back_to_truncated_output_when_no_think(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "成果物本文" * 50)
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = {
        "chat_history": [], "expert_retry_count": 0, "constraint_issue": "none",
        "constraint_issue_log": [], "selected_expert": "テスト専門家",
        "run_id": run_id, "current_task_id": "task_1_1",
    }
    cela_main.expert_node(state)
    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert decisions[0]["why"] == ("成果物本文" * 50)[:150]


# ---------------------------------------------------------------------------
# generate_user_utterance_node: 欠落していたmake_decision呼び出しの追加
# ---------------------------------------------------------------------------

def test_generate_user_utterance_node_records_decision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "Expertへの指示内容")
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    cela_main._think_handler({
        "action": "a", "summary": "s",
        "decided": "task_1_2の追加修正を指示", "why": "予算超過が未解消のため",
    })
    state = {
        "goal": "g", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [], "run_id": run_id,
    }
    cela_main.generate_user_utterance_node(state)
    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert len(decisions) == 1
    assert decisions[0]["who"] == "user"
    assert decisions[0]["why"] == "task_1_2の追加修正を指示（予算超過が未解消のため）"


def test_generate_user_utterance_node_falls_back_to_truncated_input_when_no_think(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "発言" * 100)
    monkeypatch.setattr(cela_main, "get_last_write_agreement_succeeded", lambda: False)
    monkeypatch.setattr(cela_main, "get_last_reasoning_text", lambda: "")
    monkeypatch.setattr(cela_main, "get_last_goal_revision", lambda: None)
    state = {
        "goal": "g", "round_count": 0, "constraint_issue": "none",
        "user_retry_count": 0, "chat_history": [], "run_id": run_id,
    }
    cela_main.generate_user_utterance_node(state)
    decisions = cela_main.get_decisions_from_db(conn, run_id)
    assert decisions[0]["why"] == ("発言" * 100)[:150]


# ---------------------------------------------------------------------------
# generate_user_utterance: 無制限インラインタイムライン撤去・共通ヘルパー統一・pin注入
# ---------------------------------------------------------------------------

def test_generate_user_utterance_uses_shared_hydrate_context_helper():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_hydrate_context_from_db(" in src
    assert "_build_escalation_pin_text(" in src
    # 旧・無制限インラインタイムライン（get_decisions_from_dbの全件をfor文で展開する実装）が
    # 残っていないこと。
    assert 'for i, d in enumerate(get_decisions_from_db(' not in src


def test_call_expert_injects_escalation_pin():
    src = inspect.getsource(cela_main.call_expert)
    assert "_build_escalation_pin_text(" in src
