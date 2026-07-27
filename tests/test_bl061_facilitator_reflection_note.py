"""
BL-061: facilitatorがreflectionの判定理由（stagnant/drift検出の具体的根拠）を
一切受け取れず、直近chat_historyのみから独自に（時に食い違う）状況判断をしていた
問題のオフライン検証項目。

参照: log/2026-07-23/1656（reflectionが5点の未解決問題・でっちあげ疑いを検出し
"stagnant"と判定したにもかかわらず、facilitator自身は「膠着していない」と
独立に再判断し、無関係な軽微な論点だけを穏やかに促す食い違ったメッセージを
生成した実例）、docs/design/issue_backlog.md BL-061。
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
    db_path = str(tmp_path / "test_bl061.db")
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


def test_bl061_reflection_node_stores_note_in_state(monkeypatch):
    """reflection_nodeがcall_reflectionのnoteをstate["last_reflection_note"]へ保存すること
    （従来はdecisionsテーブルのwhy列にしか残らず、facilitator_nodeへ渡っていなかった）。"""
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": False,
        "discussion_status": "stagnant",
        "note": "山間部速度28.8km/hへの無断変更が未解決のまま残っている。",
    })
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "get_active_conn", lambda: None)
    # [BL-096] reflection_nodeはescalated issueの有無を確認するため_get_escalated_issuesを
    # 呼ぶようになった。このテストはDB接続なしでreflection_nodeの状態遷移ロジックのみを
    # 検証する目的のため、DBアクセスをモックで無効化する。
    monkeypatch.setattr(cela_main, "_get_escalated_issues", lambda conn, run_id: [])
    # reflection_nodeはグローバルconfig（if __name__=="__main__"ブロック内でのみ設定される）
    # を参照するため、モジュールとして直接呼び出すテストではここで用意してやる必要がある。
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = {
        "risk_register": [], "goal": "g", "run_id": "r1",
    }
    result_state = cela_main.reflection_node(state)
    assert result_state["last_reflection_note"] == "山間部速度28.8km/hへの無断変更が未解決のまま残っている。"
    assert result_state["drift_flag"] is True


def test_bl061_call_facilitator_prompt_includes_reflection_note(monkeypatch):
    """call_facilitatorが送信するプロンプトに、渡されたreflection_noteの内容が
    実際に含まれること（従来は完全に欠落していた）。"""
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None):
        captured["messages"] = messages
        return "ダミーのファシリテーター応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    note = "でっちあげ疑いのある数値（平坦部ルート長6.67km）が未検証のまま使われている。"
    cela_main.call_facilitator("テストゴール", [{"role": "user", "content": "こんにちは"}], note)

    prompt_text = captured["messages"][0]["content"]
    assert note in prompt_text, "reflectionの判定理由がfacilitatorへのプロンプトに含まれていない"


def test_bl061_call_facilitator_handles_empty_reflection_note(monkeypatch):
    """reflection_noteが空（旧来のcheckpointからの復帰等）でもクラッシュせず、
    フォールバック文言が使われること。"""
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None):
        captured["messages"] = messages
        return "ダミー応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    cela_main.call_facilitator("テストゴール", [{"role": "user", "content": "こんにちは"}], "")

    prompt_text = captured["messages"][0]["content"]
    assert "特筆すべき懸念なし" in prompt_text


def test_bl061_facilitator_node_passes_last_reflection_note(db_conn, monkeypatch):
    """facilitator_nodeがstate["last_reflection_note"]をcall_facilitatorへ渡すこと
    （従来は未使用の`decisions`引数を渡すのみで、reflectionの判定理由は伝わっていなかった）。"""
    conn, run_id = db_conn
    captured = {}

    def fake_call_facilitator(goal, chat_history, reflection_note="", **kwargs):
        captured["reflection_note"] = reflection_note
        return "フィードバック"

    monkeypatch.setattr(cela_main, "call_facilitator", fake_call_facilitator)

    state = {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール",
        "run_id": run_id,
        "last_reflection_note": "重大な未解決問題がある。",
    }
    cela_main.facilitator_node(state)

    assert captured["reflection_note"] == "重大な未解決問題がある。", (
        "facilitator_nodeがlast_reflection_noteをcall_facilitatorへ渡していない"
    )
