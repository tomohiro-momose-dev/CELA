"""
BL-326: Detector注釈をdecision_id指定で機械的に削除する経路を追加する。

1307ログ（run_id=1787890406-1e73a89d、task_3_5）実インシデント: Expertが約1900字の
Detector指摘注釈ブロックをwrite_agreementのedits（old_text/new_text）で削除しようとして
5回連続失敗した。原因は、注釈本文中の金額表記「1億1,850万」を毎回「1億11,850万」と誤記
（数字1文字のtranscription error）したこと。read_whiteboard_excerptで正しい全文を2回
確認した後も同じ誤記を繰り返しており、長文の一字一句正確な再現という設計自体が失敗しやすい
ことが判明した（BL-202と同型の再発）。

Detector注釈は_DETECTOR_COMMENT_TEMPLATEにより短く誤記しにくい一意なdecision_id
（例: 'D-1788150538640-f6dd80'）を持つ。このIDを指定してブロック全体を機械的に境界検出・
削除する経路（edits要素のremove_annotation_id）を追加し、old_textでの逐語再現を経由しない
削除手段を提供する。

設計はPlan mode + Cline独立レビュー（AGENTS.md §19.1、2回・指摘1〜7およびF1〜F5を反映）を
経て確定。docs/design/back_log/BL-326/BL326_basic_design.md参照。
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
# 1. `_find_detector_annotation_span` / `_list_detector_annotation_ids` 単体テスト
# ---------------------------------------------------------------------------

def _annotation(decision_id: str, comment: str) -> str:
    return cela_main._DETECTOR_COMMENT_TEMPLATE.format(decision_id=decision_id, comment=comment)


def test_template_derived_markers_are_consistent_with_template():
    """[Cline指摘1] 閉じマーカー・開始マーカー接頭辞が、新規リテラルではなく
    _DETECTOR_COMMENT_TEMPLATE自身から導出されていること（テンプレート整合性テスト）。"""
    assert cela_main._DETECTOR_COMMENT_CLOSE_MARKER == "> （この注釈は指摘箇所を修正すると同時に削除してください）"
    assert cela_main._DETECTOR_COMMENT_START_PREFIX == "> 🔴 **[Detector指摘 #"
    # テンプレートを実際にformatした結果にも、導出したマーカーが含まれること。
    ann = _annotation("D-1", "テスト")
    assert cela_main._DETECTOR_COMMENT_START_PREFIX in ann
    assert cela_main._DETECTOR_COMMENT_CLOSE_MARKER in ann


def test_find_span_simple_single_line_comment():
    ann = _annotation("D-1", "単純な指摘")
    content = "本文A。" + ann + "本文B。"
    span = cela_main._find_detector_annotation_span(content, "D-1")
    assert span is not None
    start, end = span
    assert content[:start] + content[end:] == "本文A。本文B。"


def test_find_span_multi_paragraph_embedded_newline_comment():
    """[1307ログの実データに近い形] comment自体が複数段落（embedded改行）を含む場合。"""
    comment = "【ドメイン妥当性レビュー】前提は成立する。\n【数値監査】1億1,850万の根拠を確認した。"
    ann = _annotation("D-1788150538640-f6dd80", comment)
    content = "前段。\n" + ann + "後段。"
    span = cela_main._find_detector_annotation_span(content, "D-1788150538640-f6dd80")
    assert span is not None
    start, end = span
    assert content[:start] + content[end:] == "前段。\n後段。"


def test_find_span_returns_none_for_unknown_decision_id():
    ann = _annotation("D-1", "指摘")
    content = "本文。" + ann
    assert cela_main._find_detector_annotation_span(content, "D-999") is None


def test_find_span_returns_none_when_close_marker_missing():
    """開始マーカーはあるが閉じマーカーがない（壊れた/切り詰められた）文書。"""
    content = "本文。\n> 🔴 **[Detector指摘 #D-1]**: 指摘だけあって閉じ行がない"
    assert cela_main._find_detector_annotation_span(content, "D-1") is None


def test_find_span_leaves_no_extra_blank_lines_around():
    """削除後に前後の余分な空行を残さない（block_startが先行改行を消費、block_endが
    閉じマーカー直後の改行を消費する設計の確認）。"""
    ann = _annotation("D-1", "指摘")
    orig = "行A\n行B"
    mid = orig.index("行B")
    inserted = orig[:mid] + ann + orig[mid:]
    span = cela_main._find_detector_annotation_span(inserted, "D-1")
    start, end = span
    removed = inserted[:start] + inserted[end:]
    assert removed == orig, repr(removed)


def test_find_span_hardening_close_marker_text_inside_comment_not_at_line_start():
    """[Cline指摘5] commentの本文に偶然閉じマーカーと同じ文字列が「行頭ではない」形で
    含まれていても、誤って早期終端しないこと。"""
    close = cela_main._DETECTOR_COMMENT_CLOSE_MARKER
    comment = f"本文中に「{close}」という語句を含む指摘"
    ann = _annotation("D-1", comment)
    content = "前。" + ann + "後。"
    span = cela_main._find_detector_annotation_span(content, "D-1")
    assert span is not None
    start, end = span
    assert content[end:].startswith("後。"), f"誤って早期終端した: {content[end:end+20]!r}"


def test_find_span_hardening_start_marker_text_inside_other_comment_not_at_line_start():
    """[Cline指摘§19.4-2] 別の注釈のcomment本文に、たまたま対象decision_idの開始マーカー
    文字列が「行頭ではない」形で含まれていても、そちらを誤って本物の開始マーカーと
    みなさないこと（開始マーカー検索にも行頭条件を課す対称性の確認）。"""
    fake_ref = f"{cela_main._DETECTOR_COMMENT_START_PREFIX}D-1]**: "
    ann_other = _annotation("D-OTHER", f"本文中に「{fake_ref}」という誤参照を含む")
    ann_real = _annotation("D-1", "本物の指摘")
    content = "前。" + ann_other + "中。" + ann_real + "後。"

    span = cela_main._find_detector_annotation_span(content, "D-1")
    assert span is not None
    start, end = span
    # 本物のD-1注釈（ann_real）が削除され、ann_otherは無傷で残ること。
    removed = content[:start] + content[end:]
    assert ann_other in removed, "誤って別の注釈（引用元）が対象になった"
    assert "本物の指摘" not in removed


def test_find_span_returns_none_when_own_close_marker_missing_before_next_annotation():
    """[Cline指摘§19.4-1・重要] 対象注釈自身の閉じマーカーが欠損・改変されている場合、
    次の別の注釈の閉じマーカーまでサイレントに踏み込んで過剰削除しないこと（fail-loud）。
    実際に起こりうる状況：過去の部分編集等で対象注釈の閉じ行だけが失われ、開始マーカーの
    後に別の注釈がそのまま続く壊れた文書。"""
    close = cela_main._DETECTOR_COMMENT_CLOSE_MARKER
    start_prefix = cela_main._DETECTOR_COMMENT_START_PREFIX
    # D-1の開始マーカーはあるが、閉じマーカーが失われたまま直後にD-2の注釈が続く壊れた文書。
    broken = (
        "前。\n"
        f"{start_prefix}D-1]**: 指摘だが閉じ行が失われている\n"
        f"{start_prefix}D-2]**: 別の指摘\n{close}\n後。"
    )
    assert cela_main._find_detector_annotation_span(broken, "D-1") is None, (
        "対象注釈自身の閉じマーカーが無いのに、D-2の閉じマーカーまで踏み込んで"
        "spanを返してしまっている（サイレントな過剰削除のリスク）"
    )
    # D-2側は正常に検出・削除できること（隣接する正常な注釈への非退行確認）。
    span2 = cela_main._find_detector_annotation_span(broken, "D-2")
    assert span2 is not None


def test_find_span_at_document_head_position_zero():
    """[エッジケース] 注釈が文書の先頭（position 0）から始まる場合も正しく境界検出できること。"""
    ann = _annotation("D-1", "先頭の指摘").lstrip("\n")
    content = ann + "本文。"
    span = cela_main._find_detector_annotation_span(content, "D-1")
    assert span is not None
    start, end = span
    assert start == 0
    assert content[:start] + content[end:] == "本文。"


def test_list_detector_annotation_ids_multiple():
    ann_a = _annotation("D-A", "一つ目")
    ann_b = _annotation("D-B", "二つ目")
    content = "本文1。" + ann_a + "本文2。" + ann_b + "本文3。"
    assert cela_main._list_detector_annotation_ids(content) == ["D-A", "D-B"]


def test_list_detector_annotation_ids_empty_when_none():
    assert cela_main._list_detector_annotation_ids("注釈のない普通の本文") == []


# ---------------------------------------------------------------------------
# 2. [Cline指摘2] 挿入→削除の往復一致テスト（実挿入パターンを再現）
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl326.db")
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
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""


def test_roundtrip_mid_line_insertion_then_removal_restores_original(db_conn):
    """target_excerptが行途中で終わる場合の挿入→remove_annotation_idでの削除が、
    挿入前の元テキストと完全一致すること。mid-line挿入時は前後の行が正しく連結される
    ――これはバグではなく意図した挙動であることを固定する。"""
    conn, run_id = db_conn
    orig = "固定費は2,000万円(N=4台)とする。備考も同じ行内にある。"
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_3", "task_3_5", orig, "expert", "初版")

    ok, _ = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_3", "task_3_5",
        target_excerpt="2,000万円(N=4台)",
        comment="根拠不明な暫定値",
        decision_id="D-1",
    )
    assert ok is True
    annotated = cela_main.get_latest_whiteboard(conn, run_id, "phase_3", "task_3_5")["content"]
    assert annotated != orig

    merged, err = cela_main._apply_text_edits(annotated, [{"remove_annotation_id": "D-1"}])
    assert err is None, err
    assert merged == orig, repr(merged)


def test_roundtrip_table_row_shift_insertion_then_removal_restores_original(db_conn):
    """BL-322のテーブル行末シフト後の挿入→remove_annotation_idでの削除が、挿入前の
    元テキストと完全一致すること（テーブル行が分断されたまま残らないことも含む）。"""
    conn, run_id = db_conn
    table_row = "| a | b | c |"
    orig = f"前段。\n{table_row}\n後段。"
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", orig, "expert", "初版")

    ok, _ = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_2", "task_2_1",
        target_excerpt="| a | b",  # テーブル行の途中までしか引用しない（BL-322実インシデントの形）
        comment="表の値を確認",
        decision_id="D-2",
    )
    assert ok is True
    annotated = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_1")["content"]
    assert table_row in annotated, "BL-322対策により行は分断されていないはず"

    merged, err = cela_main._apply_text_edits(annotated, [{"remove_annotation_id": "D-2"}])
    assert err is None, err
    assert merged == orig, repr(merged)


# ---------------------------------------------------------------------------
# 3. `_apply_text_edits` 統合テスト
# ---------------------------------------------------------------------------

def test_apply_text_edits_remove_annotation_id_pure_deletion():
    ann = _annotation("D-1", "指摘")
    content = "本文A。" + ann + "本文B。"
    merged, err = cela_main._apply_text_edits(content, [{"remove_annotation_id": "D-1"}])
    assert err is None, err
    assert merged == "本文A。本文B。"


def test_apply_text_edits_remove_annotation_id_with_leading_newline_new_text():
    """new_textの先頭に改行を含めれば、独立行として短い訂正記録に置換できること。"""
    ann = _annotation("D-1", "指摘")
    content = "本文A。" + ann + "本文B。"
    merged, err = cela_main._apply_text_edits(
        content, [{"remove_annotation_id": "D-1", "new_text": "\n【訂正済み】対応完了。"}]
    )
    assert err is None, err
    assert merged == "本文A。\n【訂正済み】対応完了。本文B。"


def test_apply_text_edits_remove_annotation_id_unknown_id_lists_existing_ids():
    ann = _annotation("D-EXISTING", "指摘")
    content = "本文。" + ann
    merged, err = cela_main._apply_text_edits(content, [{"remove_annotation_id": "D-NOT-FOUND"}])
    assert merged is None
    assert "D-NOT-FOUND" in err
    assert "D-EXISTING" in err


def test_apply_text_edits_remove_annotation_id_with_no_annotations_present():
    merged, err = cela_main._apply_text_edits("注釈のない本文", [{"remove_annotation_id": "D-1"}])
    assert merged is None
    assert "現在、Detector注釈は存在しません" in err


def test_apply_text_edits_old_text_and_remove_annotation_id_together_is_rejected():
    """[Cline指摘4] 両方指定された場合は片方を黙って無視せず、明示エラーにすること。"""
    ann = _annotation("D-1", "指摘")
    content = "本文。" + ann
    merged, err = cela_main._apply_text_edits(
        content, [{"old_text": "本文。", "new_text": "変更後。", "remove_annotation_id": "D-1"}]
    )
    assert merged is None
    assert "同時に指定できません" in err


def test_apply_text_edits_old_text_path_unaffected_non_regression():
    """[非退行] remove_annotation_id未指定時、old_text方式は従来通り動作すること。"""
    content = "変更前のテキストです。"
    merged, err = cela_main._apply_text_edits(
        content, [{"old_text": "変更前", "new_text": "変更後"}]
    )
    assert err is None, err
    assert merged == "変更後のテキストです。"


def test_apply_text_edits_old_text_missing_and_no_remove_annotation_id_gives_clear_error():
    merged, err = cela_main._apply_text_edits(content := "本文", [{"new_text": "x"}])
    assert merged is None
    assert "remove_annotation_id" in err


# ---------------------------------------------------------------------------
# 4. 1307ログの実インシデント再現テスト
# ---------------------------------------------------------------------------

def test_1307_incident_reproduction_old_text_fails_but_remove_annotation_id_succeeds():
    """実際に失敗したannotation本文に近い形（金額表記の数字1文字誤記）を再現し、
    旧方式（old_text、誤記入り）では引き続き失敗しうる一方、remove_annotation_id方式
    なら一発で成功することを確認する。"""
    real_comment = (
        "【ドメイン妥当性レビュー】前提設計自体は現実的で成立する。"
        "②ただし§4建設費合計「約1億3,550万〜1億9,950万円」は構成要素の和"
        "（9,000〜12,600＋1,000〜1,500＋1,050＋500〜800＋300〜600＝1億1,850万〜1億6,550万円・"
        "python_repl検算）と一致せず両端とも約1,700万円過大（issue_log起票済み）。"
    )
    ann = _annotation("D-1788150538640-f6dd80", real_comment)
    content = "本文の続き。\n" + ann + "後続の本文。"

    # 実際に5回連続失敗した誤記（「1億1,850万」→「1億11,850万」の数字1文字重複）を
    # 含むold_textでの削除は、完全一致・緩い一致とも失敗すること。
    typo_old_text = ann.replace("1億1,850万〜1億6,550万円", "1億11,850万〜1億6,550万円")
    merged_old, err_old = cela_main._apply_text_edits(content, [{"old_text": typo_old_text, "new_text": ""}])
    assert merged_old is None
    assert err_old is not None

    # remove_annotation_id方式なら、本文の逐語再現が一切不要で一発で成功する。
    merged_new, err_new = cela_main._apply_text_edits(
        content, [{"remove_annotation_id": "D-1788150538640-f6dd80"}]
    )
    assert err_new is None, err_new
    assert merged_new == "本文の続き。\n後続の本文。"


# ---------------------------------------------------------------------------
# 5. [Cline指摘6] revise_goal（ゴール文編集）との共有経路の確認
# ---------------------------------------------------------------------------

def test_apply_text_edits_remove_annotation_id_via_goal_text_content_label_fails_cleanly():
    """_apply_text_editsはrevise_goal（content_label="現在のゴール文"）とも共有される
    実装のため、remove_annotation_idを渡すこと自体は機械的に到達可能。ゴール文には
    Detector注釈が存在しないため常に「見つかりませんでした」エラーになるが、
    content_label非依存の中立的な文言でクリーンに失敗すること（「ホワイトボード」という
    固定文言が誤って混入しないこと）。"""
    goal_text = "本市の自動運転バス導入計画のゴール文。"
    merged, err = cela_main._apply_text_edits(
        goal_text, [{"remove_annotation_id": "D-1"}], content_label="現在のゴール文"
    )
    assert merged is None
    assert "現在のゴール文" in err
    assert "ホワイトボード" not in err


# ---------------------------------------------------------------------------
# 6. `write_agreement`ツール経由の統合テスト
# ---------------------------------------------------------------------------

_PHASES = [{"phase_id": "phase_3", "tasks": [{"task_id": "task_3_5"}]}]


def test_write_agreement_tool_path_remove_annotation_id_updates_whiteboard(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_3_5",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"

    # [entry_type=Deliverable かつ CREATE の場合、len(raw_content) > 200 でなければ
    # whiteboard_draftsへ昇格しない（BL-062との後方互換のための閾値）ため、200字超にする。
    orig = "# task_3_5 車庫仕様書\n\n本文。" + "補足説明。" * 40
    create_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_3_5成果物",
            "decision_what": orig, "reason_why": "初版", "entry_type": "Deliverable",
            "phase_id": "phase_3", "task_id": "task_3_5",
        },
        state,
    )
    assert create_result["success"] is True, create_result.get("error")

    ok, _ = cela_main._annotate_whiteboard_with_detector_comment(
        conn, run_id, "phase_3", "task_3_5",
        target_excerpt="本文。",
        comment="金額の根拠を確認",
        decision_id="D-3",
    )
    assert ok is True
    cela_main._LAST_WHITEBOARD_READS.add("task_3_5")

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_3_5成果物（注釈削除）",
            "reason_why": "指摘対応済みのため注釈を削除", "entry_type": "Deliverable",
            "phase_id": "phase_3", "task_id": "task_3_5",
            "edits": [{"remove_annotation_id": "D-3"}],
        },
        state,
    )
    assert result["success"] is True, result.get("error")

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_3", "task_3_5")
    assert latest["content"] == orig
    assert "D-3" not in latest["content"]
