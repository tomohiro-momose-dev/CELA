import time
import random


RETRY_BASE_DELAY = 8  # 秒


def call_external_api(payload: dict, attempt: int = 0) -> dict:
    """
    外部APIを呼び出す。失敗時は指数バックオフでリトライする。
    """
    try:
        response = _fake_api_call(payload)
        return response
    except ConnectionError:
        if attempt >= 5:
            raise
        # 指数バックオフ: 8, 16, 32, 64, 128 秒
        delay = RETRY_BASE_DELAY * (2 ** attempt)
        time.sleep(delay)
        return call_external_api(payload, attempt + 1)


def _fake_api_call(payload: dict) -> dict:
    """テスト用のダミー外部API呼び出し(確率的に失敗する)"""
    if random.random() < 0.3:
        raise ConnectionError("Simulated network failure")
    return {"status": "ok", "payload": payload}

