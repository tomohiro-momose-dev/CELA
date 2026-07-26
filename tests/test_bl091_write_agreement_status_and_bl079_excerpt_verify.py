"""
BL-091: write_agreementが実際に成功したかどうかをDetectorに明示する。
BL-079: target_excerptをJSON確定前にverify_whiteboard_excerptツールで検証させ、
         一致失敗をDetector自身にフィードバックして同一ツールループ内で調整・再試行
         できるようにする。あわせて、severityで優先された側の引用が一致しない場合に
         もう一方の一致する引用へプログラム的に差し替えるフォールバックも追加する。

実ドライラン（`log/2026-07-25/1913`）で発見した事故: task_2_1のExpertがwrite_agreementの
edits（正規のツール呼び出し）に失敗した直後、最終iterationでツールが強制的に外された
ところ、モデル（DeepSeek系）が独自のツール呼び出し風の疑似XML（`<｜DSML｜tool_calls>...`）
を平文でそのまま出力した。これは実際には一切実行されていない（
`get_last_write_agreement_succeeded()=False`とシステム自身が記録している）にも
かかわらず、Detectorはこの平文の「主張」を鵜呑みにし、物理的矛盾が解消された・
acceptance_criteriaを充足していると誤って承認、Decision Extractorも虚偽のUPDATEを
DBに記録した。実際のホワイトボードファイルは1バージョン前（V2）のまま、誤った
記述・数値が残っていた。

参照: docs/design/issue_backlog.md BL-091・BL-079、docs/design/decision_log.md D-067。
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
    db_path = str(tmp_path / "test_bl091_bl079.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._DB_CONN = conn
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN = None
        conn.close()


# ---------------------------------------------------------------------------
# BL-091: write_agreement成否のDetectorへの明示
# ---------------------------------------------------------------------------

def test_call_detector_source_includes_write_agreement_status_block():
    """call_detectorのソースに、write_agreement成否をDetectorへ明示するブロックが
    存在すること（両パス＝ドメイン妥当性レビュー・数値監査の双方に配線されていること）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-091" in src
    assert "write_agreement_status_block" in src
    assert "expert_wrote_agreement" in src
    assert "user_wrote_agreement" in src
    # 両プロンプト文字列（domain_prompt/prompt）双方に埋め込まれていること
    assert src.count("{write_agreement_status_block}") >= 2


def test_verify_whiteboard_excerpt_handler_true_when_write_agreement_failed_and_claim_mismatches(db_conn):
    """write_agreementが失敗した状態で、Expertの発言内容と実際のホワイトボードが食い違う
    シナリオを模擬し、verify_whiteboard_excerptで「主張された修正後の文言」を検索すると
    一致しない（＝まだ反映されていない）ことを検出できること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_1",
        "停車後約40.5秒で通信障害エリアを通過するため通信が自然復旧する。", "expert", "V2"
    )
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._CURRENT_PHASE_ID = "phase_2"
    cela_main._CURRENT_TASK_ID = "task_2_1"
    try:
        # Expertが「修正した」と主張する文言（実際にはホワイトボードに反映されていない）
        result = cela_main._verify_whiteboard_excerpt_handler(
            {"excerpt": "停車後はPhase 3で能動的復旧試行を継続する。"}
        )
        assert result["ok"] is False
        assert "0件" in result["reason"] or "件" in result["reason"]

        # 一方、実際に現存する文言は一意に一致すること
        result2 = cela_main._verify_whiteboard_excerpt_handler(
            {"excerpt": "停車後約40.5秒で通信障害エリアを通過するため通信が自然復旧する。"}
        )
        assert result2["ok"] is True
        assert result2["match_type"] == "exact"
    finally:
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_PHASE_ID = ""
        cela_main._CURRENT_TASK_ID = ""


def test_verify_whiteboard_excerpt_handler_loose_match(db_conn):
    """完全一致0件でも、正規化後（太字記法・改行等の揺れを無視）に一意一致すればok=trueとなること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "この設計でも**完全な常時2名は達成できない**。", "expert", "初版"
    )
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._CURRENT_PHASE_ID = "phase_1"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    try:
        result = cela_main._verify_whiteboard_excerpt_handler(
            {"excerpt": "この設計でも完全な常時2名は達成できない。"}
        )
        assert result["ok"] is True
        assert result["match_type"] == "loose"
    finally:
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_PHASE_ID = ""
        cela_main._CURRENT_TASK_ID = ""


def test_verify_whiteboard_excerpt_handler_empty_excerpt():
    result = cela_main._verify_whiteboard_excerpt_handler({"excerpt": ""})
    assert result["ok"] is False


def test_verify_whiteboard_excerpt_tool_registered_in_dispatch_and_detector_tools():
    assert "verify_whiteboard_excerpt" in cela_main.TOOL_DISPATCH
    assert cela_main.TOOL_DISPATCH["verify_whiteboard_excerpt"] is cela_main._verify_whiteboard_excerpt_handler
    src = inspect.getsource(cela_main.call_detector)
    assert "VERIFY_WHITEBOARD_EXCERPT_TOOL" in src


def test_call_detector_prompt_instructs_to_verify_before_finalizing_target_excerpt():
    src = inspect.getsource(cela_main.call_detector)
    assert "verify_whiteboard_excerpt" in src
    assert "BL-079" in src


def test_call_detector_has_programmatic_excerpt_fallback_when_preferred_excerpt_mismatches():
    """ドメイン妥当性レビュー（tools=Noneのためverify_whiteboard_excerptを呼べない）が選んだ
    target_excerptが実際にはホワイトボードと一致しない場合、数値監査パス側の（検証済みの
    可能性が高い）引用へプログラム的に差し替えるフォールバックが存在すること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_excerpt_matches_uniquely" in src
    assert "_fallback_excerpt" in src

