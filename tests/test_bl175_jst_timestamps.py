"""
BL-175: ログのタイムスタンプ（MultiLoggerのログフォルダ名・「Execution Log Started at」・
reflectionのtimeline表示）と、checkpoint一覧（`--list-checkpoints`）の時刻表示がバラバラ
（実行環境のOSローカルタイムゾーンに依存、LangGraphのcheckpoint.created_atはUTC固定）だった
問題への対応。ユーザー要望「時刻ですが日本時間にGMT+9にしてほしい。また、ログにもチェック
ポイントと同じ時刻を表示し、同期をとりたい」を受け、両方を明示的にJST（UTC+9）へ統一した。

参照: docs/design/back_log/issue_backlog.md BL-175。実LLM API呼び出しは伴わない。
"""

import datetime
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_jst_constant_is_utc_plus_9():
    assert cela_main.JST.utcoffset(None) == datetime.timedelta(hours=9)


def test_multilogger_uses_jst_regardless_of_local_timezone(monkeypatch, tmp_path):
    """MultiLogger.__init__がOSローカルタイムゾーンではなく、明示的にJSTでnowを取得すること。
    datetime.datetime.now()自体をUTC固定のfixed_nowで差し替え、tzが渡された場合のみ
    UTC+9の時刻へ変換されることを確認する（呼び出し元がJSTを明示していなければズレるはず）。"""
    fixed_utc = datetime.datetime(2026, 8, 5, 0, 30, 0, tzinfo=datetime.timezone.utc)

    class _FixedDateTime(datetime.datetime):
        @classmethod
        def now(cls, tz=None):
            if tz is None:
                raise AssertionError("MultiLoggerはtz引数（JST）を明示的に渡す必要がある")
            return fixed_utc.astimezone(tz)

    monkeypatch.setattr(cela_main.datetime, "datetime", _FixedDateTime)
    monkeypatch.chdir(tmp_path)

    # [test isolation] MultiLogger.log_dirはクラス変数（他のテストのアーカイブ処理等が
    # 参照する共有状態）のため、このテストで書き換えた値を必ず元に戻す。
    original_log_dir = cela_main.MultiLogger.log_dir
    cela_main.MultiLogger._instance = None
    cela_main.MultiLogger._initialized = False
    logger = cela_main.MultiLogger()
    try:
        # UTC 2026-08-05 00:30 -> JST 2026-08-05 09:30
        assert os.path.join("log", "2026-08-05", "0930") == cela_main.MultiLogger.log_dir
        logger.file_no_prompt.flush()
        with open(logger.filename_no, encoding="utf-8") as f:
            content = f.read()
        assert "2026-08-05 09:30:00 JST" in content
    finally:
        logger.file_with_prompt.close()
        logger.file_no_prompt.close()
        cela_main.MultiLogger._instance = None
        cela_main.MultiLogger._initialized = False
        cela_main.MultiLogger.log_dir = original_log_dir


def test_list_checkpoints_displays_created_at_in_jst(tmp_path, monkeypatch, capsys):
    """[BL-174との統合] list_checkpointsが表示するcreated_at（LangGraph側はUTC固定）が
    JSTへ変換されていること。"""
    import sqlite3
    from typing import TypedDict

    from langgraph.checkpoint.sqlite import SqliteSaver
    from langgraph.graph import END, StateGraph

    class _S(TypedDict):
        x: int

    def node_a(state):
        return {"x": state["x"] + 1}

    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)

    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    g = StateGraph(_S)
    g.add_node("node_a", node_a)
    g.set_entry_point("node_a")
    g.add_edge("node_a", END)
    app = g.compile(checkpointer=checkpointer)
    for _ in app.stream({"x": 0}, config={"configurable": {"thread_id": "t-jst"}}, stream_mode="values"):
        pass
    conn.close()

    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: g.compile(checkpointer=checkpointer))

    cela_main.list_checkpoints("t-jst")
    out = capsys.readouterr().out
    assert " JST |" in out
