"""
BL-171: OpenRouter無料枠の日次上限（例: "Rate limit exceeded: free-models-per-day-high-balance"）
エラーが、他の一時的なAPIエラーと同じ指数バックオフ・層2リトライ経路に乗ってしまい、
X-RateLimit-Resetが翌日固定のタイムスタンプであるため何時間リトライしても解消せず、
最終的に無意味な「フェイルクローズ(major)」を延々と繰り返して進行を破壊していた問題
（`log/2026-08-04/2344`で実機確認、ユーザー報告）のオフライン検証項目。

参照: docs/design/issue_backlog.md BL-171。実LLM API呼び出しは伴わない
（`client.chat.completions.create`をraiseするフェイクで代替）。
"""

import inspect
import os
import sys

import httpx
import pytest
from openai import RateLimitError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _make_rate_limit_error(message: str) -> RateLimitError:
    req = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    resp = httpx.Response(429, request=req, json={"error": {"message": message}})
    return RateLimitError(f"Error code: 429 - {message}", response=resp, body=None)


class _FakeCompletions:
    def __init__(self, exc: Exception):
        self._exc = exc
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        raise self._exc


class _FakeChat:
    def __init__(self, exc: Exception):
        self.completions = _FakeCompletions(exc)


class _FakeClient:
    """base_urlに'openrouter'を含めず、provider.order等の分岐を単純化する。"""
    def __init__(self, exc: Exception):
        self.chat = _FakeChat(exc)
        self.base_url = "https://api.example.com/v1"


def test_daily_quota_error_raises_immediately_without_retry_backoff(monkeypatch):
    """"per-day"を含むRateLimitErrorは、通常の指数バックオフ（8/16/32/64/128秒）を
    一切待たず、DailyQuotaExhaustedErrorとして即座に送出されること。"""
    sleep_calls = []
    monkeypatch.setattr(cela_main.time, "sleep", lambda s: sleep_calls.append(s))

    exc = _make_rate_limit_error("Rate limit exceeded: free-models-per-day-high-balance. ")
    fake_client = _FakeClient(exc)

    with pytest.raises(cela_main.DailyQuotaExhaustedError):
        cela_main._query_AI_live(
            [{"role": "user", "content": "hello"}], client=fake_client, model="test-model", label="Test", tools=None,
        )

    assert fake_client.chat.completions.call_count == 1, "リトライせず1回で打ち切られるべき"
    assert sleep_calls == [5], (
        f"attempt冒頭の固定sleep(5)以外に、バックオフ用のsleepが呼ばれてはいけない: {sleep_calls}"
    )


def test_non_daily_rate_limit_error_still_uses_normal_retry(monkeypatch):
    """"per-day"を含まない（例: per-minuteの）RateLimitErrorは、従来通り通常の
    指数バックオフリトライを経由し、最終的にフォールバック文字列を返すこと
    （BL-171の変更が既存のリトライ経路を壊していないことの回帰確認）。"""
    sleep_calls = []
    monkeypatch.setattr(cela_main.time, "sleep", lambda s: sleep_calls.append(s))

    exc = _make_rate_limit_error("Rate limit exceeded: please retry in 20s.")
    fake_client = _FakeClient(exc)

    result = cela_main._query_AI_live(
        [{"role": "user", "content": "hello"}], client=fake_client, model="test-model", label="Test", tools=None,
    )

    assert result == "(サーバー高負荷によるAPIエラー)"
    assert fake_client.chat.completions.call_count == 6, "5回のバックオフリトライ＋最終試行で計6回呼ばれるはず"
    # 各attempt冒頭の固定sleep(5)×6回 + attempt<5の各回のバックオフsleep（8/16/32/64/128）×5回 = 11回
    assert sleep_calls == [5, 8, 5, 16, 5, 32, 5, 64, 5, 128, 5], sleep_calls


def test_run_ai_vs_ai_loop_catches_daily_quota_exhausted_like_keyboard_interrupt():
    """run_ai_vs_ai_loopが、KeyboardInterruptと同じ一時停止経路（checkpointer保存済み、
    --resumeでの再開案内）でDailyQuotaExhaustedErrorも捕捉していること。"""
    src = inspect.getsource(cela_main.run_ai_vs_ai_loop)
    assert "except DailyQuotaExhaustedError as e:" in src
    assert "--resume" in src.split("except DailyQuotaExhaustedError as e:")[1][:500]
