"""
BL-141（invalid・記録用）: 当初「expert_nodeは差し戻しのたびにchat_historyへassistant
メッセージを無条件追記しており、chat_history_windowが同一タスクの往復だけで埋まる」と
診断し修正を実装したが、これはexpert_node関数の一部（末尾の追記部分）しか確認せずに
出した誤った結論だった。実際にはexpert_node冒頭（call_expert呼び出し直前）に、この
診断より前から既に次のガード節が存在していた：

    if state.get("constraint_issue") in ("major"):
        if state["chat_history"] and state["chat_history"][-1]["role"] == "assistant":
            state["chat_history"].pop()
            state["expert_retry_count"] += 1

Detectorがmajor判定で差し戻す＝state["constraint_issue"] == "major"のときはcall_expertを
呼ぶ前に直前の却下された提出をpopしており、末尾で新しい提出をappendするため、差し戻しが
何回続いてもchat_historyの長さは一定に保たれる（pop 1件・append 1件で正味の増減は0）。
つまり報告された問題は当初から存在せず、BL-141の実装（末尾での上書き処理）は不要な重複
コードだった。誤診断に基づくコードは削除済み。本ファイルは、実際に存在する冒頭popロジック
を対象に検証内容を全面差し替えたもの。

参照: docs/design/back_log/issue_backlog.md BL-141（invalid）・decision_log.md D-113（撤回）。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl141.db")
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


def _base_expert_state(run_id: str, chat_history=None, constraint_issue: str = "none") -> dict:
    return {
        "chat_history": chat_history if chat_history is not None else [],
        "expert_retry_count": 0,
        "constraint_issue": constraint_issue,
        "constraint_issue_log": [],
        "selected_expert": "テスト専門家",
        "run_id": run_id,
        "current_task_id": "task_1_1",
    }


def test_expert_node_appends_fresh_assistant_message_when_not_a_retry(db_conn, monkeypatch):
    """constraint_issueがmajorでなければ（新規タスク・通常ターン）、通常通り新規
    assistantメッセージを追記する。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "初回の成果物です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)

    state = _base_expert_state(run_id, [{"role": "user", "content": "task_1_1を実施してください"}])
    result = cela_main.expert_node(state)

    assert result["chat_history"] == [
        {"role": "user", "content": "task_1_1を実施してください"},
        {"role": "assistant", "content": "初回の成果物です"},
    ]


def test_expert_node_pops_previous_submission_on_major_retry(db_conn, monkeypatch):
    """constraint_issue="major"（Detector差し戻し）の場合、call_expertを呼ぶ前に
    直前の却下された提出をchat_historyからpopし、expert_retry_countを加算する。
    その後の新しい提出はappendされるため、正味chat_historyのエントリ数は変わらない。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "差し戻しを受けた修正版です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)

    state = _base_expert_state(run_id, [
        {"role": "user", "content": "task_1_1を実施してください"},
        {"role": "assistant", "content": "初回の成果物です（Detectorに差し戻された）"},
    ], constraint_issue="major")
    result = cela_main.expert_node(state)

    assert len(result["chat_history"]) == 2, "差し戻し再提出でchat_historyのエントリ数が増えてはいけない"
    assert result["chat_history"][-1] == {"role": "assistant", "content": "差し戻しを受けた修正版です"}
    assert result["chat_history"][0]["role"] == "user"
    assert result["expert_retry_count"] == 1


def test_expert_node_multiple_major_retries_still_leave_one_assistant_entry(db_conn, monkeypatch):
    """3回連続でmajor判定を受けた場合でも、chat_history上のassistantエントリは1件のまま
    （最新の再提出内容に更新され続ける）ことを確認する。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)

    state = _base_expert_state(
        run_id, [{"role": "user", "content": "task_1_1を実施してください"}],
    )
    for i in range(1, 4):
        state["constraint_issue"] = "major" if i > 1 else "none"
        monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config, i=i: f"再提出{i}回目")
        state = cela_main.expert_node(state)

    assert len(state["chat_history"]) == 2
    assert state["chat_history"][-1] == {"role": "assistant", "content": "再提出3回目"}
    assert state["expert_retry_count"] == 2


def test_expert_node_does_not_pop_when_last_entry_is_not_assistant(db_conn, monkeypatch):
    """major判定でも、chat_history末尾がassistantでなければpopしない（誤ってuser発言を
    消してしまわないためのガード）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "成果物です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "get_last_ask_user_question", lambda: None)

    state = _base_expert_state(
        run_id, [{"role": "user", "content": "task_1_1を実施してください"}], constraint_issue="major",
    )
    result = cela_main.expert_node(state)

    assert result["chat_history"] == [
        {"role": "user", "content": "task_1_1を実施してください"},
        {"role": "assistant", "content": "成果物です"},
    ]
    assert result["expert_retry_count"] == 0
