# BL-326/BL-327: old_text不一致の失敗クラスへの2段構えの対処

本ドキュメントは2つの独立したBLを扱う。BL-326（Detector注釈のID指定削除）はCline独立
レビュー（§19.1）を経て設計確定済み。BL-327（機械diffヒント）はBL-326の後にユーザーとの
追加相談で合意した、より汎用的な軽量対策。両者とも1307ログの同一インシデントに端を発するが、
対象範囲が異なる独立した変更のため、実装・テスト・コミットも分けて行う。

なお、ユーザーから3つ目の案（ツール失敗が繰り返された際に`--interactive-query`型の
「ヘルパーAI」を呼び、人間がログを見れば一目で分かる誤りをAIに診断させる汎用機構）も
提案されたが、本セッションでは設計・実装せず、`issue_backlog.md`へBL-328として発想を
記録するに留める（ユーザーの言葉を残す: 「人間がログで見ればシンプルなのに作業中AIが
かたくなに失敗する...ちょっとした介入をしてあげればスムーズに動くのに、といった場面が
あるので、汎用ヘルパーとしてあったらよいと思っている」）。

---

# BL-326: Detector注釈をdecision_id指定で機械的に削除する経路を追加する

## Context

1307ログ（run_id=1787890406-1e73a89d、task_3_5）で、Expertが約1900字のDetector指摘注釈
ブロックを`write_agreement`の`edits`（old_text/new_text）で削除しようとして5回連続失敗した。
原因は、注釈本文中の金額表記「1億1,850万」を毎回「1億**11**,850万」と誤記し（数字1文字の
transcription error）、`read_whiteboard_excerpt`で正しい全文を2回確認した後も同じ誤記を
3回繰り返したこと。BL-287の反復検知ナッジが5回目で介入するまで自己修復できなかった。

これはCELAのガード機構（old_textの厳密一致検証、失敗時の詳細diff表示、BL-287の反復検知）が
正しく機能した結果（サイレント破損なし）だが、根本原因——「注釈削除には長文の一字一句正確な
再現が必須」という設計——は解消されていない。同種の失敗はBL-202（log/2026-08-09/2348、
20回連続不一致）でも発生しており、既にBL-202はガイダンス文言の強化で対処済みだったが、
今回はそれでも再発した。

Detector注釈は`_DETECTOR_COMMENT_TEMPLATE`により、`decision_id`（例:
`D-1788150538640-f6dd80`）という短く誤記しにくい一意な識別子を持つ。この識別子を使い、
注釈ブロック全体を機械的に境界検出して削除する経路を追加すれば、長文の一字一句再現という
失敗しやすい手段を経由せずに済み、この失敗クラス自体を解消できる（ユーザー承認済みの方針）。

## 対象コードの現状（調査済み）

- `_DETECTOR_COMMENT_TEMPLATE`（cela_main.py:9343付近）:
  ```python
  _DETECTOR_COMMENT_TEMPLATE = (
      "\n> 🔴 **[Detector指摘 #{decision_id}]**: {comment}\n"
      "> （この注釈は指摘箇所を修正すると同時に削除してください）\n"
  )
  ```
  開始行は`decision_id`込みで一意。`comment`自体が複数行（埋め込み`\n`）を含みうるため、
  ブロック全体の終端は固定の閉じ行「> （この注釈は指摘箇所を修正すると同時に削除して
  ください）」で判定するのが安全（`comment`の長さ・内容に依存しない）。
- `_apply_text_edits`（cela_main.py:9250付近）: `write_agreement`のDeliverable UPDATE editsの
  唯一の実処理関数。各edit dictの`old_text`/`new_text`/`replace_all`を見て置換する。呼び出し元
  （`_write_agreement_impl`内、cela_main.py:4138付近）は他に前処理バリデーションを持たず、
  ここが実質的な唯一のゲート。
- `WRITE_AGREEMENT_TOOL`のedits schema（cela_main.py:3022-3049、`required: ["old_text",
  "new_text"]`）。もう一箇所`revise_goal`のedits（cela_main.py:3250-3261）は**ゴール文専用**
  でDetector注釈を持たないため対象外。
- Expertへの注釈削除ガイダンスが3箇所ある（いずれも「注釈ブロックだけを対象にした短い
  old_textで個別に削除してください」という同じ指示）:
  - cela_main.py:11281-11286（`call_expert`のR4編集方針・BL-193）
  - cela_main.py:12721-12732（同、Detector差し戻し時のフル版プロンプト・BL-202）
  - cela_main.py:12881-12890（同、軽量版プロンプト・BL-202）

## 設計

### 1. 注釈ブロックの境界検出ヘルパー（新規）

`_DETECTOR_COMMENT_TEMPLATE`のすぐ後に追加。

**[Cline独立レビュー（§19.1）で指摘・検証済みの修正1]** 閉じマーカーを新しい文字列リテラルで
複製すると、テンプレート文言が将来変わった際に閉じマーカーだけ取り残され、
`_find_detector_annotation_span`がサイレントにNoneを返す（＝この修正自体が静かに死ぬ）
というAGENTS.md §15.1違反（同じルールの2箇所表現）になる。閉じマーカー・開始マーカー接頭辞
とも、新規リテラルにせず`_DETECTOR_COMMENT_TEMPLATE`自身から導出する（閉じ行は
`{decision_id}`/`{comment}`プレースホルダを含まないため導出は安全、Clineが実際に導出結果を
検算し正しいことを確認済み）。導出が壊れていないことを検証するテンプレート整合性テストを
必須にする（Verification 1参照）。

```python
_DETECTOR_COMMENT_CLOSE_MARKER = _DETECTOR_COMMENT_TEMPLATE.strip("\n").split("\n")[-1]
_DETECTOR_COMMENT_START_PREFIX = _DETECTOR_COMMENT_TEMPLATE.split("{decision_id}")[0].lstrip("\n")

def _find_detector_annotation_span(content: str, decision_id: str) -> tuple[int, int] | None:
    """decision_idで特定されるDetector注釈ブロック（開始マーカー直前の改行～閉じマーカー直後の
    改行まで）の(start, end)半開区間を返す。見つからなければNone。commentが複数行にわたっても
    （embedded \\nがあっても）、閉じマーカーは_DETECTOR_COMMENT_TEMPLATEにより必ずcomment直後の
    固定行として続くため、開始マーカー以降で最初に現れる行頭の閉じマーカーがこの注釈自身の
    終端となる。

    [既知の制限・Cline指摘F5] commentの本文が、たまたま閉じマーカーと全く同じ文字列を
    行頭に含む場合（極めて稀）、そこで誤って終端と判定されうる。発生確率が無視できる水準の
    ため、検出ロジックの複雑化は行わずこの制限を明記するに留める。
    """
    start_marker = f"{_DETECTOR_COMMENT_START_PREFIX}{decision_id}]**:"
    start_idx = content.find(start_marker)
    if start_idx == -1:
        return None
    block_start = start_idx - 1 if start_idx > 0 and content[start_idx - 1] == "\n" else start_idx
    # [Cline指摘5・軽微・ハードニング] commentの本文に偶然閉じマーカーと同じ文字列が
    # 含まれる場合の誤検出を防ぐため、閉じマーカーは行頭（直前が"\n"）にあるものだけを見る。
    search_from = start_idx
    while True:
        close_idx = content.find(_DETECTOR_COMMENT_CLOSE_MARKER, search_from)
        if close_idx == -1:
            return None
        if close_idx == 0 or content[close_idx - 1] == "\n":
            break
        search_from = close_idx + 1
    block_end = close_idx + len(_DETECTOR_COMMENT_CLOSE_MARKER)
    if block_end < len(content) and content[block_end] == "\n":
        block_end += 1
    return block_start, block_end


_ANNOTATION_ID_RE = re.compile(re.escape(_DETECTOR_COMMENT_START_PREFIX) + r"([^\]]+)\]\*\*:")


def _list_detector_annotation_ids(content: str) -> list[str]:
    """診断用: content内に現存する全Detector注釈のdecision_id一覧を出現順で返す
    （remove_annotation_idが見つからなかった場合のエラーメッセージで、実際に存在するIDを
    提示するため）。

    **[Cline第2回独立レビューF1]** 正規表現を新規リテラルで複製すると、指摘1で修正した
    閉じマーカー・開始マーカーと同じAGENTS.md §15.1違反（同一ルールの2箇所表現）になる
    ため、`_DETECTOR_COMMENT_START_PREFIX`から`re.escape`で導出する。
    """
    return _ANNOTATION_ID_RE.findall(content)
```

### 2. `_apply_text_edits`の拡張

各edit dictで`old_text`の代わりに`remove_annotation_id`を指定できるようにする。
`old_text`/`new_text`方式と排他的な独立ブランチとして、ループの先頭に追加する
（既存の完全一致→緩い一致のロジックには一切触れない＝非退行）。

```python
for i, e in enumerate(edits):
    if not isinstance(e, dict):
        return None, (...)  # 既存のまま

    remove_annotation_id = e.get("remove_annotation_id", "")
    old_text = e.get("old_text", "")
    # [Cline指摘4・軽微] 両方指定された場合に片方を黙って無視するとAGENTS.md §13.4
    # （検証の対称性）違反になりうるため、明示エラーにする。
    if remove_annotation_id and old_text:
        return None, (
            f"edits[{i}]: old_textとremove_annotation_idは同時に指定できません。"
            f"いずれか一方のみを指定してください。"
        )
    if remove_annotation_id:
        span = _find_detector_annotation_span(content, remove_annotation_id)
        if span is None:
            existing_ids = _list_detector_annotation_ids(content)
            # [Cline指摘6・軽微] _apply_text_editsはrevise_goal（ゴール文編集、3579行）とも
            # 共有される。「ホワイトボード」固定文言だとゴール文編集時に不整合な表示になるため、
            # content_label非依存の中立的な文言にする。
            ids_text = "、".join(existing_ids) if existing_ids else "(現在、Detector注釈は存在しません)"
            return None, (
                f"edits[{i}]: decision_id='{remove_annotation_id}'のDetector注釈が"
                f"{content_label}に見つかりませんでした。現在存在する注釈のdecision_id: {ids_text}"
            )
        start, end = span
        # [Cline指摘3・重要] block_startは先行"\n"を消費するため（純粋削除時に余分な空行を
        # 残さないための設計、Verification 2で往復一致を検証済み）、new_textを独立行として
        # 挿入したい場合は呼び出し側がnew_textの先頭に"\n"を含める必要がある。自動正規化は
        # 行わない（している/していないを暗黙にすると別の失敗クラスを生むため）。この要件を
        # ツールdescription・ガイダンス4箇所すべてに明記する（§4参照）。
        content = content[:start] + e.get("new_text", "") + content[end:]
        continue

    new_text = e.get("new_text", "")
    ... # 既存のold_text分岐（変更なし）
    if not old_text:
        return None, f"edits[{i}]: old_textまたはremove_annotation_idのいずれかを指定してください。"
```

`new_text`省略時は空文字（純粋な削除）。1307ログの実例のように「短い訂正記録に置換」したい
場合は`new_text`に`"\n"`から始まる短い文字列を渡せば、独立行として削除と同時に記録を残せる
（Expertが元々やろうとしていたことをそのまま実現できる。先頭`\n`が必要な理由は上記コメント参照）。

### 3. `WRITE_AGREEMENT_TOOL`のedits schema更新（cela_main.py:3022-3049のみ、revise_goalは対象外）

- `edits.items.properties`へ`remove_annotation_id`（string）を追加。
- `required`を`["old_text", "new_text"]`から空`[]`へ変更し（old_text/new_textどちらも省略可能な
  状態を許容する必要があるため）、代わりに`description`で「old_text か remove_annotation_id の
  いずれか一方を指定」を明記する（実際の必須性は`_apply_text_edits`が機械的に強制——
  AGENTS.md §15.3: プロンプト任せにせずコード側を権威とする）。
- description文言に「Detector注釈ブロックを削除したい場合は、old_textでの逐語再現ではなく
  remove_annotation_id（例: 'D-1788150538640-f6dd80'、注釈内の`#`直後の識別子）を使うことを
  強く推奨する。長文の一字一句再現は失敗しやすい。new_textを独立行として挿入したい場合は
  new_textの先頭に'\n'を含めること（省略時は前の行に連結される）」という趣旨を追記する
  （後半はCline指摘3の反映）。

### 4. 3箇所のガイダンス文言更新

cela_main.py:11281-11286・12721-12732・12881-12890の3箇所とも、「注釈ブロックだけを対象に
した短いold_textで個別に削除してください」という指示を、「old_textでの逐語再現ではなく
write_agreementのedits要素で`remove_annotation_id`（注釈内の`#`直後のID、例:
'D-1788150538640-f6dd80'）を指定して削除することを強く推奨する（old_textより確実・簡潔）。
短い訂正記録に置き換えたい場合は、new_textの先頭に改行を含めて独立行にすること」という
趣旨に更新する。全文書き換えではなく既存文言への最小限の追記・置換とする。

### 5. スコープ外・非対応・共有関数への影響（Cline指摘6の反映）

- `revise_goal`のedits（ゴール文専用、Detector注釈なし）はスキーマ上は対象外だが、
  `_apply_text_edits`自体は`revise_goal`（3579行）とも共有される実装のため、
  `remove_annotation_id`を渡すこと自体は機械的に到達可能である。ゴール文にDetector注釈は
  存在しないため常に「見つかりませんでした」エラーになるだけで実害はないが、
  content_label非依存の中立的なエラー文言にする（§2で対応済み）ことと、この共有経路を
  テストで確認すること（Verification 6）をこのBLのスコープに含める。
- 既存のold_text方式は撤去しない（remove_annotation_idはあくまで追加の選択肢。Detector注釈
  以外の通常編集は引き続きold_text/new_textを使う）。
- 注釈が複数同時に存在する場合の一括削除（配列指定等）は導入しない。1回のedits要素で1つの
  decision_idを指定する既存の「1箇所ずつ」方針（BL-202）を踏襲する。

## Critical Files

- `cela_main.py`:
  - `_DETECTOR_COMMENT_TEMPLATE`直後（9343付近）: `_DETECTOR_COMMENT_CLOSE_MARKER`・
    `_find_detector_annotation_span`・`_list_detector_annotation_ids`を新規追加
  - `_apply_text_edits`（9250付近）: ループ先頭に`remove_annotation_id`分岐を追加
  - `WRITE_AGREEMENT_TOOL`のedits schema（3022-3049）: `remove_annotation_id`プロパティ追加、
    `required`緩和、description更新
  - ガイダンス文言3箇所（11281-11286・12721-12732・12881-12890）更新
- `tests/test_bl326_detector_annotation_removal_by_id.py`（新規）

## Verification

1. `_find_detector_annotation_span`単体テスト: 単純な1行commentの注釈、embedded改行を含む
   複数段落commentの注釈（1307ログの実データに近い形）、closeマーカーが見つからない場合
   （None）、decision_idが存在しない場合（None）、注釈直前の改行の扱い（ブロック前後に余分な
   空行を残さないこと）、comment本文に閉じマーカーと同じ文字列が偶然含まれる場合に誤検出
   しないこと（Cline指摘5）。加えて`_DETECTOR_COMMENT_CLOSE_MARKER`/`_DETECTOR_COMMENT_
   START_PREFIX`が実際に`_DETECTOR_COMMENT_TEMPLATE`から導出された値であること
   （テンプレート整合性テスト、Cline指摘1）。
2. **[Cline指摘2・重要]** 挿入→削除の往復一致テスト: `_annotate_whiteboard_with_detector_
   comment`の実挿入パターン2通り（(a) target_excerptが行途中で終わる場合の挿入、
   (b) BL-322のテーブル行末シフト後の挿入）を再現し、注釈挿入直後の文書に対して
   `remove_annotation_id`で削除した結果が、挿入前の元テキストと完全一致することを確認する
   （mid-line挿入時は前後の行が正しく連結される――これはバグではなく意図した挙動であることを
   テストで固定する）。
3. `_list_detector_annotation_ids`単体テスト: 複数注釈が存在する文書からの全ID抽出。
4. `_apply_text_edits`統合テスト: `remove_annotation_id`指定での削除成功（new_text省略＝
   空文字置換／`"\n"`始まりのnew_text指定＝独立行としての短い訂正記録への置換の両方）、
   存在しないdecision_id指定時のエラー文言に現存IDが列挙されること、`old_text`と
   `remove_annotation_id`を同時指定した場合に明示エラーになること（Cline指摘4）、
   old_text方式の既存動作が一切変わっていないこと（非退行）。
5. 1307ログの実インシデント再現テスト: 実際に失敗したannotation本文（数値の「1億1,850万」を
   含む長文）を使い、旧方式（old_text）では引き続き失敗しうる一方、remove_annotation_id方式
   なら一発で成功することを確認する。
6. **[Cline指摘6]** `revise_goal`側（ゴール文編集、content_label="現在のゴール文"）で
   `remove_annotation_id`を渡した場合、ゴール文にはDetector注釈が存在しないため
   content_label非依存の中立的なエラー文言でクリーンに失敗すること。
7. `write_agreement`ツール経由の統合テスト（`_write_agreement_impl`をUPDATE/Deliverableで
   呼び、edits=[{"remove_annotation_id": "..."}]）が実際のwhiteboard_draftsへ反映されること。
8. AGENTS.md §17.1に従い、`_apply_text_edits`の新規分岐を一時的にrevertし、上記統合テストが
   失敗することを確認した上で復元する。
9. `python -m py_compile cela_main.py`。
10. 影響範囲テスト: 既存のold_text/new_text関連テスト（BL-074/BL-081/BL-151/BL-193/BL-202/
    BL-076のannotation関連）を再実行し非退行確認。
11. フルオフラインスイート実行。
12. 実装前に`docs/design/back_log/issue_backlog.md`へBL-326を起票（Cline指摘7）。
13. 実装後、Cline CLIによる独立レビュー（AGENTS.md §19.4 実装後diff）を実施し、
    指摘を実コードで検証の上反映する（§19.1 Plan段階のレビューは本セッションで実施済み・
    指摘1〜7はすべて本設計へ反映済み）。
14. `docs/design/back_log/BL-326/BL326_basic_design.md`へ本設計を保存、`decision_log.md`・
    `decision_lineage.md`へ記録する。

---

# BL-327: old_text不一致エラーへ機械的diffヒントを追加する

## Context

BL-326の議論の中で、ユーザーから「ツール失敗が続いた時にinteractive-query型のヘルパーAIを
呼んで診断させてはどうか」という提案があった。1307ログの実例（「1億1,850万」を
「1億11,850万」と誤記）は、人間がログを一目見れば即座に気づけるレベルの相違であり、
これはLLMをもう1体呼ばなくても`difflib`による機械的な文字単位diffで同じ効果が得られる、
という軽量な代替案をこちらから提示し、ユーザーが承認した（ヘルパーAI案自体はBL-328として
発想のみ記録し、本BLでは実装しない）。

対象は`_apply_text_edits`が`old_text`の完全一致・緩い一致とも失敗した場合
（`exact_count == 0`、cela_main.py:9307付近）に呼ばれる`_nearest_content_snippet`
（cela_main.py:9222）。この関数は既に`difflib.SequenceMatcher`でold_textとcontentの
最長共通部分（LCS）を特定し、その周辺窓を「参考：最も近い実際の内容」として提示している。
しかし1307ログの実例では、この周辺窓を提示されてもExpertは相違点（1文字の数字重複）自体には
自力で気づけず、同じ誤記を3回繰り返した。

## 設計

`_nearest_content_snippet`が既に計算済みの`match`（`difflib.Match`、LCSの開始位置
`match.a`（content側）・`match.b`（old_text側）・長さ`match.size`）を再利用し、
追加の全文字列diffパスを走らせずに、**LCSブロックの直前・直後の短い窓**をold_text側と
content側で突き合わせる。LCSブロック自体は定義上完全一致することが保証されているため、
その直前・直後を見るだけで、隣接する食い違い（1307ログのような数字1文字の相違）を
低コストかつ高確度でピンポイントできる。

**[Cline第2回独立レビューF2]** 「最初の」食い違いという命名・docstringは不正確——実際に
示すのはold_text全体の最初の相違ではなく「LCSブロックに隣接する」相違（old_textに複数箇所の
相違があれば、報告されるのはLCS境界側のものであり、必ずしも文書上最初のものとは限らない、
Clineの実行検証で確認済み）。関数名を`_adjacent_divergence_hint`とし、docstringもそれに
合わせて修正する。

**[Cline第2回独立レビューF3]** `match.a`と`match.b`が大きく異なる場合（例:
`match.a=2, match.b=40`）、before側の窓はcontent側2文字・old_text側30文字という非対称な
長さで比較され、実際の相違以上に大きく見える表示になりうる（Clineの実行検証で再現確認済み）。
`context_chars`をそのまま両側にスライスするのではなく、実際に切り出せる文字数の最小値
（`min(context_chars, 残り文字数)`を content側/old_text側それぞれで独立に求めた上で、
さらに両側の最小値を取る）に揃えてから比較する。

**[Cline第2回独立レビューF4]** `find_longest_match`は最大一致ブロックを返す
（＝`match.a`/`match.b`双方に余地がある限り、隣接する1文字は必ず食い違う——さもなければ
その1文字を含めた方が長い一致になり最大性に反する）。したがって、before/after双方の窓が
非空である限り、ヒントは実質常に発火する（Clineの実行検証で確認済み）。「両側とも一致すれば
空文字列」という説明は、文書境界（`match.a==0`または`match.a+match.size==len(content)`等）で
片側・両側の窓が空になる場合にのみ該当し、それ以外では起こらない。docstringをこの実際の
挙動に合わせて修正する。

```python
_TEXT_EDIT_DIVERGENCE_CONTEXT_CHARS = 30  # [BL-327] 機械diffヒントの一致ブロック前後の表示文字数

def _adjacent_divergence_hint(content: str, old_text: str, match: "difflib.Match",
                               context_chars: int = _TEXT_EDIT_DIVERGENCE_CONTEXT_CHARS) -> str:
    """[BL-327] _nearest_content_snippetが検出した最長一致ブロック（match）に隣接する
    （直後・直前の）old_text側とcontent側の食い違いを「あなたの記述 / 実際の内容」として
    示す。最長一致ブロックそのものは両者で完全に一致することが保証されている
    （SequenceMatcherの定義）ため、その直後・直前の短い窓を見るだけで、人間がログを見れば
    一瞬で気づく類の相違（数字1文字の重複・脱落等、1307ログの実インシデント）を追加の
    LLM呼び出しなしで機械的に特定できる。

    [Cline指摘F4] find_longest_matchの最大性保証により、before/after双方の窓が非空である
    限りヒントは実質常に発火する（食い違わないなら一致をさらに延長できたはずで矛盾するため）。
    空文字列を返すのは、文書境界で片側・両側の窓が空になる場合のみ。
    """
    n_after = min(context_chars, len(content) - (match.a + match.size), len(old_text) - (match.b + match.size))
    n_before = min(context_chars, match.a, match.b)
    after_content = content[match.a + match.size: match.a + match.size + n_after]
    after_old = old_text[match.b + match.size: match.b + match.size + n_after]
    before_content = content[match.a - n_before: match.a]
    before_old = old_text[match.b - n_before: match.b]

    hints = []
    if after_old != after_content:
        hints.append(f"  [一致ブロック直後] あなたの記述: …{after_old}…\n                実際の内容 : …{after_content}…")
    if before_old != before_content:
        hints.append(f"  [一致ブロック直前] あなたの記述: …{before_old}…\n                実際の内容 : …{before_content}…")
    if not hints:
        return ""
    return "\n【一致ブロックに隣接する食い違い箇所（機械diff・BL-327）】\n" + "\n".join(hints)
```

`_nearest_content_snippet`の「有意な一致あり」分岐（`match.size >= _EDIT_SNIPPET_MIN_MATCH_SIZE`
の場合）の末尾で、`snippet`に`_adjacent_divergence_hint(content, old_text, match)`の結果を
追記して返す。関数シグネチャは変更しない（戻り値は引き続き単一の文字列）ため、唯一の呼び出し元
（`_apply_text_edits`、cela_main.py:9308）の変更は不要。

`match.size < _EDIT_SNIPPET_MIN_MATCH_SIZE`（有意な共通部分なし＝文書先頭スニペットへ
フォールバックする既存分岐）ではヒントを付加しない——このケースはold_textがcontentと
ほぼ無関係であり、「隣接する食い違い」という概念自体が意味を持たないため。

## Critical Files

- `cela_main.py`:
  - `_nearest_content_snippet`直前（9222付近）: `_TEXT_EDIT_DIVERGENCE_CONTEXT_CHARS`定数・
    `_adjacent_divergence_hint`関数を新規追加
  - `_nearest_content_snippet`本体: 有意な一致あり分岐の返り値へヒントを追記
- `tests/test_bl327_text_edit_diff_hint.py`（新規）

## Verification

1. `_adjacent_divergence_hint`単体テスト: 一致ブロック直後で食い違うケース、直前で食い違う
   ケース、両方で食い違うケース、境界で窓が空になり空文字列を返すケース（`match.a`が0
   ＝直前窓が空になる、`match.a+match.size`が`len(content)`＝直後窓が空になる。**[Cline
   指摘F4反映]** 「両側とも非空なのに一致する」ケースはfind_longest_matchの最大性保証により
   構造的に発生しないため、そのようなケースはテストしない）。**[Cline指摘F3反映]**
   `match.a`と`match.b`が大きく異なる非対称ケース（例: content側は境界近く・old_text側は
   離れている）で、before/after窓の比較長が`min(context_chars, 両側の残り文字数)`に
   正しく揃うこと。
2. 1307ログの実インシデント再現テスト: 実際に送信されたold_text（「1億11,850万」誤記版）と
   実際のcontent（「1億1,850万」正記版）を使い、`_nearest_content_snippet`の返り値に
   「あなたの記述」「実際の内容」の両方が含まれ、誤記箇所（「11,850万」周辺）が
   ヒント内に現れることを確認する。
3. `_nearest_content_snippet`統合テスト: 有意な一致がある通常ケースでヒントが付加されること、
   有意な一致がない（先頭スニペットへフォールバックする）ケースではヒントが付加されない
   ことの非退行確認。既存のBL-151/BL-193関連テストが変更なく通過することも確認する。
4. `_apply_text_edits`経由の統合テスト（`old_text`不一致を発生させ、返されたエラー文言に
   機械diffヒントが含まれることを確認）。
5. AGENTS.md §17.1に従い、`_adjacent_divergence_hint`の呼び出し・追記部分を一時的にrevertし、
   上記統合テストが失敗することを確認した上で復元する。
6. `python -m py_compile cela_main.py`。
7. 影響範囲テスト: BL-151/BL-193/BL-202関連テストを再実行し非退行確認。
8. フルオフラインスイート実行。
9. 実装前に`issue_backlog.md`へBL-327（本件）とBL-328（ヘルパーAI案、`open`・未着手・
   発想のみ記録）を起票する。
10. 実装後、Cline CLIによる独立レビュー（§19.4 実装後diff）を実施し、指摘を実コードで
    検証の上反映する。
11. `docs/design/back_log/BL-327/BL327_basic_design.md`へ本設計を保存、`decision_log.md`・
    `decision_lineage.md`へ記録する。

## 実装・コミット順序

BL-326とBL-327は独立した変更のため、それぞれ個別にテスト・§19.4レビュー・コミットを行う
（1コミットにまとめない）。順序はBL-326→BL-327（本ドキュメントの記載順）。
