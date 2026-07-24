"""
BL-076/D-048: Detectorのmajor指摘を、プロンプト注入（毎ターン再構成され消える一時情報）
だけでなく、ホワイトボード本文にWord/PDFのコメント機能のように永続的な注釈として
埋め込む機能の回帰テスト。

ユーザーが「ホワイトボードに直接detectorの指摘と理由を載せれば永続化されてプロンプト注入
より気づく可能性が高いし、指摘箇所が明白」と提案し、案A（grep容易なタグ）と
案B（視認性の高いMarkdown引用）のハイブリッド形式（D-048）を採用した。

参照: docs/design/issue_backlog.md BL-076、decision_log.md D-048。
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
    db_path = str(tmp_path / "test_bl076.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_bl076_annotate_inserts_hybrid_comment_after_unique_excerpt(db_conn):
    """target_excerptがホワイトボード内で一意一致する場合、その直後に
    案A（タグ・ID付き）＋案B（Markdown引用）のハイブリッド注釈が挿入されること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_2",
        "車両はリースと後付け改造で調達する。\n他の記述。", "expert", "初版"
    )

    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_2", "task_2_2",
        target_excerpt="車両はリースと後付け改造で調達する。",
        comment="リース会社が認証もするのは契約範囲外になる可能性がある、再考せよ",
        decision_id="D-1784850088729",
    )
    assert ok is True
    assert "完全一致" in reason

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_2")
    assert latest["version"] == 2
    assert "車両はリースと後付け改造で調達する。" in latest["content"]
    assert "🔴" in latest["content"]
    assert "[Detector指摘 #D-1784850088729]" in latest["content"]
    assert "リース会社が認証もするのは契約範囲外になる可能性がある" in latest["content"]
    assert "削除してください" in latest["content"]
    assert "他の記述。" in latest["content"]


def test_bl076_annotate_noop_when_excerpt_not_unique_or_missing(db_conn):
    """target_excerptが0件一致・複数件一致・空文字の場合は注釈を挿入せず、
    ホワイトボードのバージョンも変化しないこと（誤った位置への注釈を防ぐ）。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_2", "AとBとAが並ぶ。", "expert", "初版")

    for bad_excerpt in ["存在しない文言", "A", ""]:
        ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
            conn, run_id, "phase_2", "task_2_2",
            target_excerpt=bad_excerpt, comment="なにか指摘", decision_id="D-999",
        )
        assert ok is False
        assert reason

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_2")
    assert latest["version"] == 1, "一致しない場合はバージョンが増えないはず"


def test_bl076_call_detector_prompts_request_target_excerpt():
    """call_detectorの両パス（ドメイン妥当性レビュー・数値監査）のプロンプトが、
    ホワイトボード注釈挿入に使うtarget_excerptを要求していること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count('"target_excerpt"') >= 2
    assert "BL-076" in src


def test_bl076_detector_node_wires_annotation_on_major():
    """detector_nodeのソースが、major判定時に_annotate_whiteboard_with_detector_commentを
    呼び出す配線を含んでいること。"""
    src = inspect.getsource(cela_main.detector_node)
    assert "_annotate_whiteboard_with_detector_comment(" in src
    assert 'target_role == "assistant"' in src
