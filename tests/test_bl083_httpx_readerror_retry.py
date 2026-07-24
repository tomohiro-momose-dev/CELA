"""
BL-083: 実ドライラン中に`httpx.ReadError`（Windows WinError 10054、接続の強制切断）が
openai SDKでラップされず生のまま送出され、_query_AI_liveの絞り込んだ例外タプルに
含まれず未捕捉のままプロセス全体をクラッシュさせていた問題の回帰テスト。
BL-059（httpx.RemoteProtocolError）/BL-072（httpx.TimeoutException）と同型の再発。

参照: docs/design/issue_backlog.md BL-083。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl083_query_ai_live_catches_httpx_read_error():
    """_query_AI_liveのリトライ対象例外タプルにhttpx.ReadError
    （接続の強制切断で送出される）が含まれていること。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "httpx.ReadError" in src
    assert "httpx.TimeoutException" in src
    assert "httpx.RemoteProtocolError" in src
