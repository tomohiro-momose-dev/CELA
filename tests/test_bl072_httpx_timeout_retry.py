"""
BL-072: 実ドライラン中に`httpx.ReadTimeout`がopenai SDKのAPITimeoutErrorへラップされず
生のまま送出され、_query_AI_liveの絞り込んだ例外タプルに含まれず未捕捉のままプロセス全体を
クラッシュさせていた問題の回帰テスト。BL-059（httpx.RemoteProtocolError）と同種の問題。

参照: docs/design/issue_backlog.md BL-072。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl072_query_ai_live_catches_httpx_timeout_exception():
    """_query_AI_liveのリトライ対象例外タプルにhttpx.TimeoutException
    （ReadTimeout/ConnectTimeout/WriteTimeout/PoolTimeoutの親クラス）が
    含まれていること。個別の派生例外の都度追加ではなく親クラスで包括する。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "httpx.TimeoutException" in src
    assert "httpx.RemoteProtocolError" in src
