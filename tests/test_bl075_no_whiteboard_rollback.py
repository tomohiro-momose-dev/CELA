"""
BL-075/D-047: F-7.3（Detectorのmajor判定時にホワイトボードを1つ前のバージョンへ
ロールバックする機構）を撤廃した回帰テスト。

rollback_whiteboardは「1つ前のバージョンは健全」という前提で機械的に2版前の内容を
復元していたが、major判定が毎回別の新しい懸念を指摘するケースでは、1つ前のバージョンが
過去に別件でmajor判定された版であることがあり、既に修正済みだった問題（有給休暇日数の
労基法違反修正など）を無警告で再導入していた（実ドライラン `log/2026-07-24/0647` で
task_2_3のオペレーター年間稼働日数が有給10日→有給5日に退行する形で発現）。

対策として、ロールバック自体を撤廃し、ホワイトボードの最新内容を保持したまま、
Expertがwrite_agreementのeditsで指摘箇所のみを部分修正する方針に変更した
（call_expertのプロンプト誘導）。

参照: docs/design/issue_backlog.md BL-075、decision_log.md D-047。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl075_rollback_whiteboard_function_removed():
    """rollback_whiteboard関数自体がモジュールから削除されていること。"""
    assert not hasattr(cela_main, "rollback_whiteboard")


def test_bl075_expert_node_source_no_longer_calls_rollback():
    """expert_nodeのソースにrollback_whiteboard呼び出しが残っていないこと。"""
    src = inspect.getsource(cela_main.expert_node)
    assert "rollback_whiteboard(" not in src


def test_bl075_call_expert_prompt_guides_scoped_edit_over_full_rewrite():
    """call_expertのmajor差し戻しプロンプトが、全文書き直し誘導ではなく
    editsによる部分修正・影響範囲確認を指示する文言に置き換わっていること。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "部分修正" in src
    assert "edits" in src
    # 旧来の「全文書き直しを誘発する」指示文言が残っていないこと
    assert "完全に修正した新しい提案を作成してください" not in src


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl075.db")
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


def test_bl075_expert_node_does_not_revert_whiteboard_content_on_major(db_conn, monkeypatch):
    """major判定を受けたexpert_node実行後も、whiteboard_draftsの最新バージョン・内容が
    変化しない（ロールバックによる巻き戻しが発生しない）こと。call_expert自体はLLM呼び出しの
    ため軽量スタブに差し替える。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_3", "有給5日版", "expert", "初版")
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_3", "有給10日版（修正済み）", "expert", "労基法違反修正")

    before = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_3")
    assert before == {"version": 2, "content": "有給10日版（修正済み）"}

    monkeypatch.setattr(cela_main, "call_expert", lambda expert_name, state, config: "修正案です")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    state = {
        "chat_history": [{"role": "assistant", "content": "却下された前回発言"}],
        "expert_retry_count": 0,
        "constraint_issue": "major",
        "constraint_issue_log": [{"severity": "major", "comment": "別件の指摘"}],
        "selected_expert": "テスト専門家",
        "run_id": run_id,
        "current_task_id": "task_2_3",
    }
    cela_main.expert_node(state)

    after = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_3")
    assert after == before, "rollback撤廃後は、major判定を受けてもホワイトボードは巻き戻らないはず"
