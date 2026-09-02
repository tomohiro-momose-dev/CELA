# BL-322: Detector注釈挿入がMarkdownテーブル行を分断する欠陥の根本修正

（ExitPlanModeで承認されたプラン本文をそのまま保存する。）

## Context

ユーザーが依頼した独立レビュー（cline）で、2051ラン（run_id=1787890406-1e73a89d）の
whiteboard版数の大半が「内容の議論」ではなく「整形修復」であり、edit適用ツールの欠陥が
議論コストを2〜3倍に膨らませているとの指摘があった。cline提案は「edit_summaryで内容変更版/
整形修復版を区分し、phase gate進捗指標から整形版を除外する」という症状側の対処だった。

実データで検証した結果、指摘の一部は正確で一部は不正確だった：

- **task_2_1のV13は実際に「整形修復のみ」だった**（正確）。V11の実内容
  （`whiteboard_drafts run_id=1787890406-1e73a89d task_id=task_2_1 version=11`）を確認すると、
  Detector注釈が3列markdownテーブル行の**2列目セルの直後・3列目セルの直前**に挿入され、
  行が改行を挟んで分断されていた（`...乗車率2.1%（空車率97.9%）**\n> 🔴 **[Detector指摘
  #D-1787998072012-d5eb96]**: ...`）。V12で注釈を削除した際、`...）**\n | 最大トリップ...`
  という壊れた形（本来同一行にあるべき3列目セルの前に余分な改行が残る）のまま残り、
  V13で人手同然の「行末パイプ修復」編集が追加で必要になった。
- **task_5_2のV1〜V5を同種の欠陥とみなすのは不正確**（cline指摘を再検証し却下）。中身を
  確認したところ、User承認条件①②③（山間実効席数訂正・DRT近似の保守性明示・§2.3誤式証明の
  誤帰属訂正）へ個別に対応した正当なレビュー往復であり、ツールの欠陥ではなくレビューが
  機能して実際の誤りを潰した記録そのものだった。

**根本原因**: `_annotate_whiteboard_with_detector_comment`（cela_main.py:9324）は
`target_excerpt`の一致判定に`_normalize_for_loose_match`（cela_main.py:9280）の緩い一致を
使う。この正規化は空白・`*`（太字記法）に加え**`|`（テーブル区切り）も除去対象**である
（BL-081でtarget_excerpt/edits共通の一致精度向上のため追加）。Detector指摘の`target_excerpt`
がテーブル行の一部（今回は2列目まで）しか引用していない場合、注釈の挿入位置がその引用の
末尾＝行の途中に決まってしまい、Markdownテーブル構造を破壊する。これは緩い一致特有の
問題ではなく、完全一致（`exact_count==1`）分岐でも`target_excerpt`が行の途中で終わって
いれば同様に発生しうる——両分岐に共通する「挿入位置をtarget_excerptの直後に固定する」
という設計そのものが原因。

**スコープの判断**: `_normalize_for_loose_match`/`_find_loose_match_spans`はExpert自身の
`edits`（`_apply_text_edits`、cela_main.py:9181）とも共有されているが、あちらは
「置換」であり「挿入」ではないため破壊のメカニズムが異なる（実証拠なし）。今回は
`_annotate_whiteboard_with_detector_comment`の実証拠がある挿入位置の欠陥のみを対象とし、
`_apply_text_edits`側は根拠のない拡大解釈をしない（AGENTS.md §14「表面的な一致は診断で
はない」）。

cline提案の「指標から除外」は症状（版数の見かけの水増し）を隠すだけで、テーブル破壊
そのもの・Expertの修復ターンという実コストは残り続けるため不採用とし、挿入位置の
根本修正を行う（ユーザー承認済み：「根本修正を行ってください」）。

## 設計

### 挿入位置の調整ロジック

新規ヘルパー関数（`_annotate_whiteboard_with_detector_comment`の直前）:

```python
def _shift_insertion_point_past_table_row(content: str, insertion_point: int) -> int:
    """[BL-322] 挿入位置が丁度Markdownテーブル行の途中（セル境界の間）に来る場合、
    テーブル構造を壊さないよう行末まで挿入位置をずらす。
    実インシデント（task_2_1 V11）: 3列テーブル行の2列目セル直後に注釈を挿入した結果、
    3列目セルと行末|が注釈の後ろへ押し出され、Markdownとして破綻した。
    挿入位置から次の改行までの間に`|`が残っていれば、その行はまだ終わっていない
    （テーブル行の途中）と判断し、挿入位置を行末（次の改行の直前、無ければ文書末）まで
    ずらす——注釈は独立した行としてテーブル行の直後に挿入される。
    """
    newline_pos = content.find("\n", insertion_point)
    line_end = newline_pos if newline_pos != -1 else len(content)
    if "|" in content[insertion_point:line_end]:
        return line_end
    return insertion_point
```

### `_annotate_whiteboard_with_detector_comment`の改修

現状、完全一致分岐は`content.replace(target_excerpt, target_excerpt + annotation, 1)`で
挿入位置を暗黙に扱い、緩い一致分岐は`content[:orig_end+1] + annotation + content[orig_end+1:]`
で明示的に扱っている。両分岐を「挿入位置（int）を求める」→「共通の調整・スプライス」の形へ
統一し、調整ロジックを一箇所に集約する：

```python
def _annotate_whiteboard_with_detector_comment(
    conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
    target_excerpt: str, comment: str, decision_id: str
) -> tuple[bool, str]:
    latest = get_latest_whiteboard(conn, run_id, phase_id, task_id)
    if not latest:
        return False, "ホワイトボードが存在しません"
    content = latest["content"]
    annotation = _DETECTOR_COMMENT_TEMPLATE.format(decision_id=decision_id, comment=comment)
    if not target_excerpt:
        return False, "target_excerptが空文字でした"

    exact_count = content.count(target_excerpt)
    if exact_count == 1:
        start = content.find(target_excerpt)
        insertion_point = start + len(target_excerpt)
        match_desc = "完全一致で挿入"
    else:
        norm_content, index_map = _normalize_for_loose_match(content)
        norm_excerpt, _ = _normalize_for_loose_match(target_excerpt)
        loose_count = norm_content.count(norm_excerpt) if norm_excerpt else 0
        if not norm_excerpt or loose_count != 1:
            reason = (
                f"完全一致0件・正規化後緩い一致も{loose_count}件でした"
                if exact_count == 0 else
                f"完全一致が{exact_count}件（一意でない）で、正規化後緩い一致も{loose_count}件でした"
            )
            return False, reason
        norm_start = norm_content.find(norm_excerpt)
        norm_end = norm_start + len(norm_excerpt) - 1
        orig_end = index_map[norm_end]
        insertion_point = orig_end + 1
        match_desc = "正規化後の緩い一致で挿入"

    # [BL-322] テーブル行途中への挿入によるMarkdown破壊を防ぐ。
    insertion_point = _shift_insertion_point_past_table_row(content, insertion_point)
    new_content = content[:insertion_point] + annotation + content[insertion_point:]

    apply_whiteboard_patch(
        conn, run_id, phase_id, task_id, new_content,
        author_role="system_detector_annotation",
        edit_summary=f"[Detector注釈] {comment[:80]}"
    )
    return True, match_desc
```

戻り値`(True, match_desc)`のmatch_desc文言は既存と同一に保つ（呼び出し元がこの文字列を
判定に使っていないか確認済み——ログ出力のみ）。

## 対象外・トレードオフ

- `_apply_text_edits`（Expertの通常edits経路）は同じ`_normalize_for_loose_match`を使うが、
  挿入ではなく置換であり実インシデントの証拠が無いため、今回は対象外とする。将来同種の
  破壊が観測されたら別BLとして扱う。
- テーブル行の判定は「挿入位置から次の改行までの間に`|`があるか」という単純なヒューリスティクス
  であり、コードブロック内の`|`（稀）等を誤判定する可能性はゼロではないが、既存の
  `_normalize_for_loose_match`が既に`|`をテーブル区切りとして特別扱いしている設計方針と
  一致しており、過剰な一般化はしない。

## Critical Files

- `cela_main.py`: `_shift_insertion_point_past_table_row`新規ヘルパー追加、
  `_annotate_whiteboard_with_detector_comment`（9324付近）の改修
- `tests/test_bl322_detector_annotation_table_row_split_guard.py`（新規）

## Verification

1. `_shift_insertion_point_past_table_row`単体テスト——挿入位置の後に`|`がある（テーブル
   行途中）場合は行末へシフト、無い場合（テーブル外・行末）は不変、次の改行が無い
   （文書末尾）場合は文書末へ。
2. `_annotate_whiteboard_with_detector_comment`統合テスト——実インシデント再現
   （3列テーブル行の2列目までを`target_excerpt`とした場合、注釈が行の直後・独立行として
   挿入され、テーブル行自体は分断されないこと）、完全一致・緩い一致の両分岐で同様に
   機能すること、テーブル外の通常文への注釈挿入は従来通り動作すること（非退行）。
3. `python -m py_compile cela_main.py`
4. 影響範囲テスト: 既存のBL-076/BL-074関連テスト（`_annotate_whiteboard_with_detector_comment`
   を使う既存テストがあれば）を再実行し非退行確認。
5. フルオフラインスイート実行。
6. 実装後、`docs/design/back_log/BL-322/BL322_basic_design.md`へ実装前保存、
   `issue_backlog.md`にBL-322を記載（優先対応一覧＋詳細セクション両方、pre-commitフックの
   整合チェック対応）、`decision_log.md`へ決定を記録する。
