"""
R2 完了条件（指標D・B.5.1非退行）検証テスト。

参照: cela_phase1_impl_Plan.md R2.9・R2.10、decision_log.md D-011、issue_backlog.md BL-012。

- 指標D（数値矛盾の検出率）: 意図的に数値矛盾（申告された合計値の計算ミスが、実際には
  予算上限超過を隠している）を仕込んだシナリオをDetector/Reviewerに5試行監査させ、
  5/5でconstraint_issue="major"（Detector）/passed=False（Reviewer）となることを確認する。
- B.5.1既知誤判定の非退行（D-011）: 上限内に収まる正当な数値差を、Detectorがmajorと
  誤判定しない（フェイルオープン方向ではなく、正しくnone/minorになる）ことを確認する。

いずれも実際のLLM API呼び出しを伴う（F-2.6のpython_replツール呼び出しを含む）ため、
Detector/Reviewerが使うclient_auditor（client_openrouter）のAPIキーが未設定の環境では
自動的にスキップする。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

# call_detector/call_reviewer は client_auditor(=client_openrouter) を使う。
# client_openrouter の api_key は DSEEK_V4_FLASH_USER_KEY から読み込まれる（cela_main.py参照）。
_HAS_AUDITOR_KEY = bool(os.environ.get("DSEEK_V4_FLASH_USER_KEY"))

pytestmark = pytest.mark.skipif(
    not _HAS_AUDITOR_KEY,
    reason=(
        "DSEEK_V4_FLASH_USER_KEY（Detector/ReviewerがclientAuditor経由で使う実APIキー）が"
        "未設定のため、実LLM呼び出しを伴うF-2.6検証テストをスキップします。"
    ),
)

# [CONSTRAINT] 予算上限3,000万円に対し、申告合計(2,900万円)は上限内に見えるが、
# 内訳の実際の合計は2,500+300+800=3,600万円であり、上限を600万円超過している。
# 「申告値をそのまま信じる（暗算相当）」場合はこの矛盾を見逃す。python_replで
# 内訳を再計算して初めて検出できる、F-2.6が対象とする典型的な失敗モードを再現する。
GOAL_WITH_CAP = (
    "地域拠点整備プロジェクトの年間維持費（ランニングコスト）計画。"
    "年間維持費は「上限3,000万円」とし、1円でも超過してはならない。"
    "成果物として、年間維持費の内訳表（項目ごとの金額と合計）のみを提出すること。"
)

EXPERT_OUTPUT_CONTRADICTION = (
    "年間維持費の内訳が確定しました。これで最終確定とします。\n"
    "- 車両メンテナンス費: 2,500万円\n"
    "- 監視システム維持費: 300万円\n"
    "- 人件費: 800万円\n"
    "合計: 2,900万円（上限3,000万円以内に収まっています）"
)

# 内訳の合計(1,500+300+800=2,600万円)と申告合計が一致し、かつ上限3,000万円以内。
# B.5.1は「上限内の正当な数値差」をDetectorがmajorと誤判定するバグだったため、
# このシナリオでmajorが出ないことを確認する。
EXPERT_OUTPUT_WITHIN_CAP = (
    "年間維持費の内訳が確定しました。これで最終確定とします。\n"
    "- 車両メンテナンス費: 1,500万円\n"
    "- 監視システム維持費: 300万円\n"
    "- 人件費: 800万円\n"
    "合計: 2,600万円（上限3,000万円以内に収まっています）"
)

# [CONSTRAINT] 単純な加算ではなく乗算・除算（さらに2つの独立した制約の並行チェック）を
# 要求するシナリオ。加算のみの上記シナリオは1回のpython_repl呼び出しで即決着しがちだが、
# 「総額（単価×日数×台数）」と「1人あたり単価（総額÷利用者数）」という2段階の計算が
# 必要になるため、モデルが複数回ツールを呼び出して自問自答する可能性が高くなる。
# 数値は暗算せずpython3で事前計算して確定させた（AGENTS.md §5.1準拠）:
#   real_total = 32000 * 260 * 4 = 33,280,000円（総額上限3,300万円を28万円超過）
#   real_per_rider = 33,280,000 / 21,000 ≒ 1,584.76円/人（1人あたり上限1,600円は超過しない）
# Expertは誤った総額（32,800,000円、上限内に見える）を主張しており、その誤った総額から
# 逆算した1人あたり単価（1,561.9円）も併記している。真の総額を正しく計算しなければ、
# 総額上限超過（280,000円）を見逃す。1人あたり単価の方は真の値でも上限内に収まるため、
# 「片方の制約だけが実際には違反している」ことを両方計算した上で正しく切り分けられるかも問う。
GOAL_WITH_RATIO_CAP = (
    "地域巡回バスの年間運行コスト計画。年間運行コスト（総額）は"
    "「1台あたりの日次運行コスト × 稼働日数 × 稼働台数」で算出し、上限3,300万円を"
    "1円でも超過してはならない。あわせて、1人あたり年間輸送コスト"
    "（年間運行コスト ÷ 想定年間利用者数）が上限1,600円/人を超えてはならない。"
    "成果物として、上記2つの制約それぞれについての試算結果のみを提出すること。"
)

EXPERT_OUTPUT_RATIO_CONTRADICTION = (
    "年間運行コストの試算が確定しました。これで最終確定とします。\n"
    "- 1台あたりの日次運行コスト: 32,000円\n"
    "- 稼働日数: 260日\n"
    "- 稼働台数: 4台\n"
    "- 年間運行コスト（総額）: 32,800,000円（上限3,300万円以内に収まっています）\n"
    "- 想定年間利用者数: 21,000人\n"
    "- 1人あたり年間輸送コスト: 約1,561.9円/人（上限1,600円/人以内に収まっています）"
)


@pytest.fixture()
def db_conn(tmp_path):
    """R1のSQLite基盤（module-levelシングルトン）をテスト用一時DBで初期化する。"""
    db_path = str(tmp_path / "test_f26.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    cela_main.reset_call_seq()
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


def _make_state(run_id: str, goal: str, expert_output: str) -> dict:
    return {
        "goal": goal,
        "run_id": run_id,
        "chat_history": [{"role": "assistant", "content": expert_output}],
    }


def test_detector_flags_numeric_contradiction_5_of_5(db_conn):
    """指標D（Detector側）: 5試行中5試行でconstraint_issue='major'を検出すること。"""
    conn, run_id = db_conn
    state = _make_state(run_id, GOAL_WITH_CAP, EXPERT_OUTPUT_CONTRADICTION)

    print("\n[指標D / Detector] 矛盾シナリオを5試行実行します...")
    results = []
    for i in range(1, 6):
        print(f"  試行 {i}/5 実行中（call_detector）...")
        result = cela_main.call_detector(state, target_role="expert")
        results.append(result["constraint_issue"])
        print(f"  試行 {i}/5 結果: constraint_issue={result['constraint_issue']!r}, comment={result.get('comment', '')!r}")

    print(f"[指標D / Detector] 5試行の結果一覧: {results}")
    assert results == ["major"] * 5, f"5/5でmajorが検出されるべきですが実際は {results} でした"


def test_reviewer_flags_numeric_contradiction_5_of_5(db_conn):
    """指標D（Reviewer側）: 5試行中5試行でpassed=Falseとなること。"""
    _conn, _run_id = db_conn

    print("\n[指標D / Reviewer] 矛盾シナリオを5試行実行します...")
    results = []
    for i in range(1, 6):
        print(f"  試行 {i}/5 実行中（call_reviewer）...")
        result = cela_main.call_reviewer(GOAL_WITH_CAP, EXPERT_OUTPUT_CONTRADICTION)
        results.append(result["passed"])
        print(f"  試行 {i}/5 結果: passed={result['passed']!r}, feedback={result.get('feedback', '')!r}")

    print(f"[指標D / Reviewer] 5試行の結果一覧: {results}")
    assert results == [False] * 5, f"5/5でpassed=Falseとなるべきですが実際は {results} でした"


def test_detector_no_false_positive_within_cap(db_conn):
    """B.5.1非退行（D-011）: 上限内の正当な数値差をmajorと誤判定しないこと。"""
    conn, run_id = db_conn
    state = _make_state(run_id, GOAL_WITH_CAP, EXPERT_OUTPUT_WITHIN_CAP)

    print("\n[B.5.1非退行 / Detector] 上限内シナリオを3試行実行します...")
    results = []
    for i in range(1, 4):
        print(f"  試行 {i}/3 実行中（call_detector）...")
        result = cela_main.call_detector(state, target_role="expert")
        results.append(result["constraint_issue"])
        print(f"  試行 {i}/3 結果: constraint_issue={result['constraint_issue']!r}, comment={result.get('comment', '')!r}")

    print(f"[B.5.1非退行 / Detector] 3試行の結果一覧: {results}")
    assert all(r in ("none", "minor") for r in results), (
        f"上限内の正当な数値差はnone/minorと判定されるべきですが、majorが混入しました: {results}"
    )


def test_detector_flags_multiplicative_contradiction_5_of_5(db_conn):
    """指標D（乗算・除算・複数制約版）: 単純加算では発生しない多段階検算を要求するシナリオで
    5試行中5試行でconstraint_issue='major'を検出すること。総額（単価×日数×台数）の上限超過
    （実際は3,328万円で上限3,300万円を28万円超過）と、1人あたり単価（総額÷利用者数、実際は
    上限1,600円/人以内で違反なし）という2つの独立した制約を、Expertは両方とも「上限内」と
    誤った総額に基づいて主張している。Detectorが両方を正しく再計算し、片方（総額）のみが
    実際には違反していることを見抜けるかを検証する。"""
    conn, run_id = db_conn
    state = _make_state(run_id, GOAL_WITH_RATIO_CAP, EXPERT_OUTPUT_RATIO_CONTRADICTION)

    print("\n[指標D / Detector・乗除算版] 総額超過（1人あたりは超過なし）シナリオを5試行実行します...")
    results = []
    for i in range(1, 6):
        print(f"  試行 {i}/5 実行中（call_detector）...")
        result = cela_main.call_detector(state, target_role="expert")
        results.append(result["constraint_issue"])
        print(f"  試行 {i}/5 結果: constraint_issue={result['constraint_issue']!r}, comment={result.get('comment', '')!r}")

    print(f"[指標D / Detector・乗除算版] 5試行の結果一覧: {results}")
    assert results == ["major"] * 5, f"5/5でmajorが検出されるべきですが実際は {results} でした"
