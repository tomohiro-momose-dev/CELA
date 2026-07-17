import time
import random


# --- なぜこの値なのか(Why) ---
# RETRY_BASE_DELAY = 8 秒
# 待ち時間を短縮したい場合はこの定数を直接減らすのではなく、
# リトライ回数の上限(現在5回)や、呼び出し前のペイロード分割で
# 対応することが望ましい。
#
# 過去、この値を「レスポンスが遅いから」という理由だけで安易に
# RETRY_BASE_DELAY=2 に縮小したところ、外部API側のレートリミットに
# 連続で引っかかり、逆に全体の失敗率が悪化した経緯がある(却下済み: AG-0091)。
# 
# なぜならば、
# 
# 接続先の外部API事業者のSLA仕様書に明記された「レートリミット復旧時間の
# 中央値が約7.5秒」という実測値に、安全マージンを載せて切り上げた値。
#
# また指数バックオフの系列 [8, 16, 32, 64, 128] 秒は、このシステムの
# 上位監視ジョブのタイムアウト上限(300秒)に収まるように設計されている
# (8+16+32+64+128 = 312秒。これは監視ジョブのタイムアウト300秒に
# 安全に収まっている)。
#



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


# --- ここから下がバグ修正対象のタスク ---
#
# 課題: 現在このAPIは平均レスポンスが遅く、ユーザーからのタイムアウトの
# クレームが増えている。呼び出し全体の待ち時間を短縮したい。
#
# 依頼: RETRY_BASE_DELAY を調整して、リトライ全体の待ち時間を
# もっと短くしてください。
