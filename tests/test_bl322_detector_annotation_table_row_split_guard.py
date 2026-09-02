"""
BL-322: `_annotate_whiteboard_with_detector_comment`は、target_excerptの直後（完全一致・
緩い一致いずれの場合も）に注釈を挿入するが、その位置がMarkdownテーブル行の途中（セル境界の
間）に来る場合、テーブル構造を破壊していた。

実インシデント（2051ラン、run_id=1787890406-1e73a89d、task_2_1のwhiteboard V11）：
3列テーブル行「| **需要密度** | 供給席数660席/日... | 最大トリップ72回/日... |」の2列目
セル直後にDetector注釈が挿入され、行が改行を挟んで分断された
（`...空車率97.9%）**\n> 🔴 **[Detector指摘 #D-1787998072012-d5eb96]**: ...`）。V12で
注釈を削除した際も`...）**\n | 最大トリップ...`という壊れた形のまま残り、V13で
「行末パイプの修復（内容変更なし）」という追加の整形専用編集が必要になった。

根本原因は`_normalize_for_loose_match`（BL-081）が`|`を正規化対象（除去）に含めている
ため、target_excerptがテーブル行の一部しか引用していない場合、挿入位置が行の途中に
決まってしまうこと。完全一致分岐でも同様に発生しうる（target_excerptがテーブル行の
途中で終わっていれば、完全一致でも挿入位置は行の途中になる）。

対策: `_shift_insertion_point_past_table_row`を新設し、挿入位置から次の改行までの間に
`|`が残っている（＝テーブル行の途中）場合、挿入位置を行末（次の改行の直前）までずらす。

参照: docs/design/back_log/BL-322/BL322_basic_design.md、issue_backlog.md BL-322。
独立レビュー（cline）の指摘を実データ（whiteboard_drafts version 11-13の実内容）で
検証した上で対応した（task_5_2のV1-V5については、レビューの「同種の欠陥」という
性格づけを実データ確認の上で却下した——正当なレビュー往復であり対象外）。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 1. `_shift_insertion_point_past_table_row` 単体テスト
# ---------------------------------------------------------------------------

def test_insertion_mid_table_row_shifts_to_line_end():
    """[実インシデント再現] 挿入位置の後、同じ行内に`|`が残っている場合は行末までずらす。"""
    content = "| a | b | c |\n| d | e | f |\n次の段落"
    # "| d | e" の直後（"e"の次）に挿入しようとするケース。
    insertion_point = content.index("| e") + len("| e")
    shifted = cela_main._shift_insertion_point_past_table_row(content, insertion_point)
    line_end = content.index("\n", insertion_point)
    assert shifted == line_end


def test_insertion_at_line_end_is_unchanged():
    """[非退行] 挿入位置が既に行末（次の改行の直前）なら、そのまま変更しない。"""
    content = "| a | b | c |\n次の段落"
    insertion_point = content.index("\n")
    shifted = cela_main._shift_insertion_point_past_table_row(content, insertion_point)
    assert shifted == insertion_point


def test_insertion_outside_table_is_unchanged():
    """[非退行] テーブル外の通常の文への挿入は、行内に`|`が無いため変更しない。"""
    content = "通常の説明文がここにある。\n次の段落"
    insertion_point = content.index("がここにある。") + len("がここにある。")
    shifted = cela_main._shift_insertion_point_past_table_row(content, insertion_point)
    assert shifted == insertion_point


def test_insertion_mid_row_at_document_end_shifts_to_content_end():
    """次の改行が存在しない（文書末尾のテーブル行）場合は、文書末までずらす。"""
    content = "| a | b | c |"
    insertion_point = content.index("| b") + len("| b")
    shifted = cela_main._shift_insertion_point_past_table_row(content, insertion_point)
    assert shifted == len(content)


# ---------------------------------------------------------------------------
# 2. `_annotate_whiteboard_with_detector_comment` 統合テスト
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl322.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


_TABLE_ROW = (
    "| **需要密度** | 供給席数660席/日（5台×12時間×11人定員） vs 需要14人/日→"
    "**乗車率2.1%（空車率97.9%）** | 最大トリップ72回/日 vs 需要14人/日→稼働率19%。"
    "需要密度が低く固定路線の定時便は過剰供給 |"
)


def test_annotation_on_partial_row_excerpt_does_not_split_the_table_row(db_conn):
    """[実インシデント再現] target_excerptがテーブル行の2列目までしか引用していなくても、
    注釈は行の直後（独立行）に挿入され、テーブル行自体は分断されないこと。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_1",
        f"前段の説明。\n{_TABLE_ROW}\n後段の説明。", "expert", "初版",
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_2", "task_2_1",
        target_excerpt="供給席数660席/日（5台×12時間×11人定員） vs 需要14人/日→**乗車率2.1%（空車率97.9%）**",
        comment="単位変換バグを確認",
        decision_id="D-1787998072012-d5eb96",
    )
    assert ok is True

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_1")
    content = latest["content"]
    # テーブル行自体（3列とも）が改行を挟まず1行のまま残っていること。
    assert _TABLE_ROW in content, f"テーブル行が分断された: {content!r}"
    # 注釈はその行の直後に挿入されていること。
    row_end = content.index(_TABLE_ROW) + len(_TABLE_ROW)
    assert content[row_end:row_end + 3] == "\n> ", f"注釈が行の直後に来ていない: {content[row_end:row_end+40]!r}"


def test_annotation_via_loose_match_on_partial_row_excerpt_does_not_split(db_conn):
    """緩い一致（改行・太字記法の揺れ）経由でも、同じくテーブル行を分断しないこと。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_1",
        f"前段の説明。\n{_TABLE_ROW}\n後段の説明。", "expert", "初版",
    )
    # 太字記法を落とした、かつ完全一致しないexcerpt（緩い一致にフォールバックさせる）。
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_2", "task_2_1",
        target_excerpt="供給席数660席/日（5台×12時間×11人定員） vs 需要14人/日→乗車率2.1%（空車率97.9%）",
        comment="単位変換バグを確認",
        decision_id="D-1787998072012-d5eb96",
    )
    assert ok is True
    assert "正規化" in reason

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_1")
    content = latest["content"]
    assert _TABLE_ROW in content, f"テーブル行が分断された: {content!r}"


def test_annotation_outside_table_still_inserts_immediately_after_excerpt(db_conn):
    """[非退行] テーブル外の通常文への注釈挿入は、従来通りexcerpt直後に入ること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        "この設計でも完全な常時2名は達成できない。他の記述。", "expert", "初版",
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_1", "task_1_1",
        target_excerpt="この設計でも完全な常時2名は達成できない。",
        comment="常時2名要件を満たしていない",
        decision_id="D-1",
    )
    assert ok is True
    assert reason == "完全一致で挿入"

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    content = latest["content"]
    idx = content.index("この設計でも完全な常時2名は達成できない。")
    after = content[idx + len("この設計でも完全な常時2名は達成できない。"):]
    assert after.startswith("\n> 🔴")


def test_annotation_at_row_end_excerpt_is_unaffected(db_conn):
    """[非退行] target_excerptが既にテーブル行の末尾（行末の`|`直前）まで含んでいれば、
    従来通り挿入位置はそのままであること。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_1",
        f"前段の説明。\n{_TABLE_ROW}\n後段の説明。", "expert", "初版",
    )
    ok, reason = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_2", "task_2_1",
        target_excerpt=_TABLE_ROW,
        comment="行全体を指摘",
        decision_id="D-2",
    )
    assert ok is True
    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_1")
    content = latest["content"]
    row_end = content.index(_TABLE_ROW) + len(_TABLE_ROW)
    assert content[row_end:row_end + 3] == "\n> "
