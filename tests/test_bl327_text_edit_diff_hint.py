"""
BL-327: old_text不一致エラーへ機械的diffヒントを追加する。

BL-326（Detector注釈のID指定削除）の議論の中で、ユーザーから「ツール失敗が続いた時に
interactive-query型のヘルパーAIを呼んで診断させてはどうか」という提案があった。1307ログの
実例（「1億1,850万」を「1億11,850万」と誤記）は、人間がログを一目見れば即座に気づけるレベル
の相違であり、これはLLMをもう1体呼ばなくても`difflib`による機械的な文字単位diffで同じ効果が
得られる、という軽量な代替案をこちらから提示し、ユーザーが承認した（ヘルパーAI案自体は
BL-328として発想のみ記録）。

`_nearest_content_snippet`（old_text不一致時の「最も近い実際の内容」提示）が既に計算済みの
最長一致ブロック（`difflib.Match`）を再利用し、その直前・直後の食い違いを機械的に
ピンポイント指摘する`_adjacent_divergence_hint`を追加した。

設計はPlan mode + Cline独立レビュー（AGENTS.md §19.1、2回・指摘1〜7およびF1〜F5を反映、
実際にPythonコードを実行して検証済み）を経て確定。
docs/design/back_log/BL-326/BL326_327_basic_design.md参照。実LLM API呼び出しは伴わない。
"""

import difflib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _match(content: str, old_text: str) -> difflib.Match:
    matcher = difflib.SequenceMatcher(None, content, old_text, autojunk=False)
    return matcher.find_longest_match(0, len(content), 0, len(old_text))


# ---------------------------------------------------------------------------
# 1. `_adjacent_divergence_hint` 単体テスト
# ---------------------------------------------------------------------------

def test_hint_fires_when_divergence_after_match_block():
    content = "共通の前置き部分がここにある。あいうえお。"
    old_text = "共通の前置き部分がここにある。かきくけこ。"
    m = _match(content, old_text)
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    assert "一致ブロックに隣接する食い違い箇所" in hint
    assert "一致ブロック直後" in hint
    assert "あいうえお" in hint or "かきくけこ" in hint


def test_hint_fires_when_divergence_before_match_block():
    content = "先頭が違う。共通の後置き部分がここにある。"
    old_text = "先頭は別物。共通の後置き部分がここにある。"
    m = _match(content, old_text)
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    assert "一致ブロック直前" in hint


def test_hint_fires_on_both_sides_when_both_diverge():
    content = "前A。共通の中央部分がここにある。後A。"
    old_text = "前B。共通の中央部分がここにある。後B。"
    m = _match(content, old_text)
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    assert "一致ブロック直前" in hint
    assert "一致ブロック直後" in hint


def test_hint_empty_when_match_covers_entire_content_and_old_text():
    """[境界] contentとold_textが完全に同一の場合、一致ブロックが全体を覆い前後の窓が
    両方とも空になるため、空文字列を返すこと。"""
    content = "完全に同じテキスト"
    old_text = "完全に同じテキスト"
    m = _match(content, old_text)
    assert m.size == len(content) == len(old_text)
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    assert hint == ""


def test_hint_empty_at_document_start_boundary_when_only_after_side_exists_and_matches():
    """[境界] 一致ブロックが両者の先頭から始まり（before窓が両方とも空）、直後も
    完全に一致する場合は空文字列を返すこと。"""
    content = "先頭共通部分" + "X" * 50
    old_text = "先頭共通部分" + "X" * 50
    m = _match(content, old_text)
    assert m.a == 0 and m.b == 0
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    assert hint == ""


def test_hint_asymmetric_window_lengths_are_clamped_to_minimum():
    """[Cline指摘F3] match.aとmatch.bが大きく異なる非対称ケースで、before/after窓の
    比較長がmin(context_chars, 両側の残り文字数)に正しく揃うこと（非対称な長さでの
    比較により実際以上に大きく見える表示にならないこと）。"""
    # content側はmatch直前に2文字しかない（境界近く）。old_text側は30文字以上ある。
    content = "ab" + "COMMON_BLOCK_TEXT_HERE_ABCDEFGH" + "tail"
    old_text = "0123456789ABCDEFGHIJKLMNOPQRSTUV" + "COMMON_BLOCK_TEXT_HERE_ABCDEFGH" + "tail2"
    m = _match(content, old_text)
    assert m.size >= cela_main._EDIT_SNIPPET_MIN_MATCH_SIZE
    hint = cela_main._adjacent_divergence_hint(content, old_text, m)
    # before側の実際の窓の長さがcontent側の残り文字数（2）に揃っていること
    # （old_text側の対応窓も同じ2文字だけが切り出されていること）を、
    # ヒント文字列中の「あなたの記述」行の長さから間接的に確認する。
    assert "一致ブロック直前" in hint
    before_line = [line for line in hint.splitlines() if "一致ブロック直前" in line][0]
    your_part = before_line.split("あなたの記述: …")[1].split("…")[0]
    assert your_part == old_text[m.b - 2: m.b]
    assert len(your_part) == 2


# ---------------------------------------------------------------------------
# 2. 1307ログの実インシデント再現テスト
# ---------------------------------------------------------------------------

def test_1307_incident_hint_pinpoints_the_digit_duplication():
    content = "総投資額は1億1,850万円である。内訳は以下の通り。"
    old_text = "総投資額は1億11,850万円である。内訳は以下の通り。"
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "あなたの記述" in snippet
    assert "実際の内容" in snippet
    # 誤記箇所（数字重複）周辺の文字列が、いずれかのヒント行に現れること。
    assert "1,850万" in snippet


def test_1307_incident_realistic_scale_long_surrounding_text():
    """1307ログにより近い規模（前後に長い定型文が続く）での再現。"""
    prefix = "交通需要予測の詳細。乗合タクシーは過疎地域の実勢を踏まえ需要を査定した。" * 9
    suffix = "以上より事業継続性の観点から財務計画の整合を確認した。感度分析は別添の通り。" * 9
    content = prefix + "総投資額は1億1,850万円である。" + suffix
    old_text = prefix + "総投資額は1億11,850万円である。" + suffix
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "あなたの記述" in snippet
    assert "実際の内容" in snippet


# ---------------------------------------------------------------------------
# 3. `_nearest_content_snippet` 統合テスト（非退行含む）
# ---------------------------------------------------------------------------

def test_nearest_content_snippet_appends_hint_when_significant_match_exists():
    content = "共通の長い前置き部分がここに続く文章です。あいうえお続き。"
    old_text = "共通の長い前置き部分がここに続く文章です。かきくけこ続き。"
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "機械diff・BL-327" in snippet


def test_nearest_content_snippet_no_hint_when_falls_back_to_head_snippet():
    """[非退行] 有意な一致がない（先頭スニペットへフォールバックする）場合は
    ヒントを付加しないこと。"""
    content = "全く無関係な内容のホワイトボード本文がここに入ります。" * 3
    old_text = "xyz"  # 短すぎて有意な一致が生まれない
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "機械diff・BL-327" not in snippet
    assert "あなたの記述" not in snippet


def test_bl151_bl193_existing_snippet_behavior_unaffected():
    """[非退行] 既存のBL-151/BL-193の「最も近い実際の内容」スニペット本体の挙動
    （中略・以下省略マーカー等）が変更されていないこと。"""
    content = "先頭部分。" + "共通の対象箇所テキストがここにある。" + "X" * 500
    old_text = "共通の対象箇所テキストがここにある。"
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "共通の対象箇所テキストがここにある。" in snippet
    assert "…（以下省略）" in snippet


# ---------------------------------------------------------------------------
# 4. `_apply_text_edits` 経由の統合テスト
# ---------------------------------------------------------------------------

def test_apply_text_edits_error_message_includes_diff_hint():
    content = "総投資額は1億1,850万円である。内訳は以下の通り。"
    typo_old_text = "総投資額は1億11,850万円である。内訳は以下の通り。"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": typo_old_text, "new_text": "x"}])
    assert merged is None
    assert "機械diff・BL-327" in err
    assert "あなたの記述" in err
