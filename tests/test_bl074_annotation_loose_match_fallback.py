"""
BL-074: 「文字列完全一致への依存の脆さ」を、agreementのtopic文字列ドリフト（当初発見箇所）
だけでなく、BL-076のホワイトボード注釈target_excerptにも共通する構造的問題として統合。

1216ドライラン(log/2026-07-24/1216/log_no_prompt.md)のフォレンジック調査で、
constraint_issue=major かつ target_role=assistant の判定が複数回発生し、
target_excerptも正しく出力されていたにもかかわらず、Whiteboard Annotated ログが
一度も出力されないことが判明した。原因は_annotate_whiteboard_with_detector_commentの
完全一致依存に加え、失敗時にサイレントに(False)を返すのみでログが一切出ないことだった。

対策:
1. 失敗理由(0件一致/複数件一致等)をログへ出す
2. 完全一致に失敗した場合、正規化（改行・空白・Markdown太字記法・全角半角）した
   緩い一致へフォールバックする

参照: docs/design/issue_backlog.md BL-074（BL-076のtarget_excerpt脆弱性を統合）。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl074_loose.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_bl074_loose_match_handles_markdown_bold_drift(db_conn):
    """ホワイトボードには太字記法(**)付きで保存されているが、target_excerptには
    太字記法が無い（またはその逆）場合でも、正規化後の緩い一致で注釈が挿入されること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "この設計でも**完全な常時2名は達成できない**。他の記述。", "expert", "初版"
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="この設計でも完全な常時2名は達成できない。",
        comment="常時2名要件を満たしていない",
        decision_id="D-1",
    )
    assert ok is True
    assert "正規化" in reason
    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert "🔴" in latest["content"]


def test_bl074_loose_match_handles_whitespace_and_newline_drift(db_conn):
    """ホワイトボード側は改行入りだが、target_excerptは1行にまとまっている（またはその逆）
    場合でも、空白・改行の揺れを吸収した緩い一致で注釈が挿入されること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "オペレーター人員は\n3名体制とする。\n他の記述。", "expert", "初版"
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="オペレーター人員は3名体制とする。",
        comment="人員が不足している",
        decision_id="D-2",
    )
    assert ok is True
    assert "正規化" in reason


def test_bl074_loose_match_handles_fullwidth_halfwidth_drift(db_conn):
    """全角/半角の違い（括弧・英数字）があっても、正規化後の緩い一致で注釈が挿入されること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "固定費は2,000万円（N=4台）とする。他の記述。", "expert", "初版"
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="固定費は2,000万円(N=4台)とする。",
        comment="N=4台の前提を再確認せよ",
        decision_id="D-3",
    )
    assert ok is True
    assert "正規化" in reason


def test_bl074_loose_match_still_fails_when_ambiguous(db_conn):
    """正規化後も一意に定まらない（複数件一致・0件一致）場合は、
    引き続き挿入を諦め、理由付きでFalseを返すこと。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "**A**と A が並ぶ。", "expert", "初版"
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="A", comment="何か指摘", decision_id="D-4",
    )
    assert ok is False
    assert "件" in reason

    ok2, reason2 = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="存在しない文言", comment="何か指摘", decision_id="D-5",
    )
    assert ok2 is False
    assert "件" in reason2


def test_bl074_detector_node_logs_failure_reason_on_annotate_miss():
    """detector_nodeのソースが、注釈挿入に失敗した場合にも理由付きでログを出す
    配線を含んでいること（以前はサイレントに失敗していた問題への対策）。"""
    import inspect
    src = inspect.getsource(cela_main.detector_node)
    assert "Whiteboard Annotate Failed" in src
    assert "_annotate_reason" in src
