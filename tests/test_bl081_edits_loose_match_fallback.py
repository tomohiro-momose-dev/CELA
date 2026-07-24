"""
BL-081: Expert自身の主たる編集手段であるwrite_agreementの`edits`（old_text/new_text）が、
1319ドライラン(log/2026-07-24/1319/log_no_prompt.md)で、Markdownテーブル行頭の
全角スペース・パイプ記号の有無だけで完全一致に失敗し、ExpertがBL-080で発覚した壊れた
SUPERSEDE全文置換経路へ迂回する原因になっていたことへの対策。

BL-074/D-050で確立した正規化（改行・空白・Markdown太字記法・全角半角）による緩い一致を
`_apply_text_edits`にも適用し、テーブル区切り記号（|）も正規化対象に追加した。
あわせて、全角スペース（\\u3000）がNFKC正規化前に空白判定されず結果に残ってしまう
`_normalize_for_loose_match`自体の非対称バグ（半角スペースは除去・全角スペースは残存）も
本修正で解消した。

参照: docs/design/issue_backlog.md BL-081。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl081_edits_succeeds_despite_leading_pipe_and_ideographic_space_drift():
    """1319ログで実際に発生したケース: old_textにはテーブル行頭の`| \\u3000`と
    行末の` |`が含まれていないが、実際のホワイトボードにはそれらが存在する場合でも、
    正規化後の緩い一致でeditsが成功すること。"""
    content = (
        "| 　D-1. オペレーター給与（**3名**常駐） | 500×**3** | "
        "**常時2名体制を実現するための最小人員。** |\n他の行。"
    )
    old_text = (
        "D-1. オペレーター給与（**3名**常駐） | 500×**3** | "
        "**常時2名体制を実現するための最小人員。**"
    )
    new_text = "D-1. オペレーター給与（**4名**常駐） | 500×**4** | **4名体制。**"

    merged, err = cela_main._apply_text_edits(content, [{"old_text": old_text, "new_text": new_text}])
    assert err is None
    assert "4名体制" in merged
    assert "他の行。" in merged


def test_bl081_edits_still_fails_when_ambiguous_after_normalization():
    """正規化後も一意に定まらない（0件・複数件でreplace_all未指定）場合は、
    引き続き理由付きでエラーを返すこと（安全側の挙動は維持）。"""
    content = "AとBとAが並ぶ。"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": "A", "new_text": "X"}])
    assert merged is None
    assert "件" in err

    merged2, err2 = cela_main._apply_text_edits(content, [{"old_text": "存在しない文言", "new_text": "X"}])
    assert merged2 is None
    assert "件" in err2


def test_bl081_edits_exact_match_still_takes_priority_over_loose():
    """完全一致が存在する通常ケースは、従来通り完全一致で置換されること（回帰確認）。"""
    content = "通常の文章です。"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": "通常の文章です。", "new_text": "更新後の文章です。"}])
    assert err is None
    assert merged == "更新後の文章です。"


def test_bl081_normalize_for_loose_match_treats_ideographic_space_symmetrically_with_halfwidth():
    """BL-081で修正した非対称バグの回帰確認: 全角スペース(\\u3000)と半角スペースが
    同じ扱い（両方除去）になり、正規化後の文字列が完全に一致すること。"""
    norm_fullwidth, _ = cela_main._normalize_for_loose_match("A　B")
    norm_halfwidth, _ = cela_main._normalize_for_loose_match("A B")
    assert norm_fullwidth == norm_halfwidth == "AB"


def test_bl081_find_loose_match_spans_maps_back_to_original_positions():
    """_find_loose_match_spansが返すスパンが、元の文字列上の正しい開始・終了位置を
    指していること（置換位置がずれると本文が破壊されるため）。"""
    content = "prefix| 　TARGET |suffix"
    spans = cela_main._find_loose_match_spans(content, "TARGET")
    assert len(spans) == 1
    start, end = spans[0]
    assert content[start:end + 1] == "TARGET"
