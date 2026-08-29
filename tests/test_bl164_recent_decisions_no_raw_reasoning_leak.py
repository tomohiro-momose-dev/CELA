"""
BL-164: Detectorへの「Recent Decisions（参考程度）」節が、直近2件のdecisions行を
`SELECT *`のまま（`internal_thought_process`列込み）JSON化してプロンプトへ埋め込んで
いた。task_1_3のホワイトボードがVer.3→Ver.5→Ver.7と全面改訂される中、直近decisionの
1つが「直前のDetector自身がVer.3を却下した際の判定record」だったため、その
`internal_thought_process`（数千字規模の生の思考過程）に、既にsupersede済みの
ホワイトボード内容への一字一句引用がverbatimで残っていた。新しいDetectorはこれを
誤って`target_excerpt`候補として採用し、実際の最新ホワイトボードには存在しない
テキストを`verify_whiteboard_excerpt`で検証し続け（実測29回中11回失敗）、
MAX_TOOL_ITER=30に到達して「最終iteration」の強制テキスト応答に追い込まれた
（同一run内で2回再現、`log/2026-08-04/1123`）。

`recent_decitions`を`who`/`what`/`why`のみのキュレーション済み要約へ絞り、
「Recent Decisions（参考程度）」節の直前に、target_excerpt/verify_whiteboard_excerpt
の根拠には使わないよう明示する注意書きを追加した。

参照: docs/design/back_log/issue_backlog.md BL-164、docs/design/decision_log.md D-134。
実LLM API呼び出しは伴わない（_query_and_parse_with_retryをmonkeypatchしてプロンプト
文字列のみを捕捉する）。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl164.db")
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


# ---------------------------------------------------------------------------
# ソース確認: 注意書き・キュレーション化ロジックそのものの存在確認
# ---------------------------------------------------------------------------

def test_call_detector_source_no_longer_dumps_raw_decision_rows():
    src = inspect.getsource(cela_main.call_detector)
    assert 'json.dumps(get_decisions_from_db(get_active_conn(), state["run_id"])[-2:], ensure_ascii=False)' not in src
    assert '"who": d.get("who", "")' in src
    assert '"what": d.get("what", "")' in src
    assert '"why": d.get("why", "")' in src
    assert "internal_thought_process" not in src.split('recent_decitions = json.dumps(')[1][:400]


def test_call_detector_source_has_recent_decisions_provenance_warning():
    """[BL-312で文面を再構成] 元は「直近の決定事項は…参考情報」→「target_excerptや
    verify_whiteboard_excerptの根拠には…」の順だったが、キャッシュ効率化のため
    自己完結文へ書き換えた際に「target_excerptやverify_whiteboard_excerptの根拠には…
    （直近の決定事項は…参考情報であり…）」と主従を入れ替えた（内容は不変）。
    3つの語すべてがRecent Decisionsの動的ブロックより前に存在することを確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    warning_idx = src.index("直近の決定事項は状況把握のための参考情報")
    target_excerpt_idx = src.index("target_excerptやverify_whiteboard_excerptの根拠には")
    recent_idx = src.index('Recent Decisions（参考程度）: {recent_decitions}')
    assert warning_idx < recent_idx
    assert target_excerpt_idx < recent_idx
    assert "verify_whiteboard_excerpt" in src[target_excerpt_idx:recent_idx]


# ---------------------------------------------------------------------------
# 実行時の挙動確認: 実際にcall_detectorを走らせ、構築されたプロンプト文字列を検証する
# ---------------------------------------------------------------------------

def _install_capturing_retry(monkeypatch, captured: dict):
    def _fake_query_and_parse_with_retry(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        captured[label] = prompt
        return dict(fallback), False

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake_query_and_parse_with_retry)


def _minimal_state(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "goal": "テストゴール",
        "chat_history": [{"role": "user", "content": "テスト発言"}],
        "current_phase": {
            "phase_id": "phase_1",
            "tasks": [{"task_id": "task_1_1", "title": "t", "acceptance_criteria": []}],
        },
        "current_task_id": "task_1_1",
    }


def test_recent_decitions_excludes_internal_thought_process_at_runtime(db_conn, monkeypatch):
    conn, run_id = db_conn
    stale_excerpt = "| **現実的複合リスク** | 需要 −20% + 電気代 +30% | **296** | **✅（ギリギリ）** |"
    cela_main.db_append_decision(
        cela_main.make_decision(
            who="detector", what="risk=low, constraint_issue=major",
            why=f"古いホワイトボードの引用: {stale_excerpt}",
            internal_thought_process=f"生の思考過程の中に{stale_excerpt}がverbatimで残っている" * 20,
        ),
        conn, run_id,
    )
    cela_main.db_append_decision(
        cela_main.make_decision(who="expert", what="タスクを実行", why="再提出しました"),
        conn, run_id,
    )

    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)

    cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert captured, "call_detectorがLLM呼び出し（モック経由）に到達していません"
    # Recent Decisions（参考程度）節は数値監査パス（label="Detector"）のみに存在する
    # （domain_prompt/"Detector (Domain Review)"にはそもそもこの節がない）。
    # thought_process_audit節は語義説明として"internal_thought_process"という語を正当に
    # 含むため（`以下はExpert/User AIの内部思考過程（internal_thought_process）です`）、
    # プロンプト全体ではなくRecent Decisions節のJSONペイロード部分だけを切り出して検査する。
    numeric_prompt = captured["Detector"]
    recent_decisions_payload = numeric_prompt.split("Recent Decisions（参考程度）: ", 1)[1].split("\n\n", 1)[0]
    assert "internal_thought_process" not in recent_decisions_payload, (
        "Recent Decisions節のJSONペイロードにinternal_thought_processというキー名が残存しています"
    )
    assert stale_excerpt in recent_decisions_payload, (
        "Recent Decisions節からwhy欄の内容（正当な要約）まで失われています"
    )


def test_recent_decitions_survives_empty_decisions(db_conn, monkeypatch):
    """decisionsが1件も無くてもcall_detectorがクラッシュしないこと（[-2:]の空リスト安全性の回帰）。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)

    cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert captured
    # Recent Decisions（参考程度）節は数値監査パス（label="Detector"）のみに存在する
    # （domain_prompt/"Detector (Domain Review)"にはそもそもこの節がない）。
    assert "Recent Decisions（参考程度）: []" in captured["Detector"]
