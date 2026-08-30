# BL-321: write_agreement(Deliverable)の本文見出し/task_id不整合ガード

（本設計はBL-320と同一の調査・Plan modeセッションで作成された。症状①・BL-320側の設計は
`docs/design/back_log/BL-320/BL320_basic_design.md`を参照。ExitPlanModeで承認された
プラン本文をそのまま保存する。）

## Context

BL-320のContextと同一（`docs/design/back_log/BL-320/BL320_basic_design.md`参照）。

### 症状②: Deliverable書き込みに内容/task_id整合性チェックが存在しない

`log/2026-08-30/2051/log_no_prompt.md:854-878`より：Expertの`current_task_id`はこの回、
正当に`task_1_1`だった（オーケストレーターも同ターンでtask_1_1の専門家選定を行っている、
`log/2026-08-30/2051/log_no_prompt.md:741`）。しかしUserの指示は「task_3_2_1成果物の
正式確定」であり、ExpertはBL-146設計（`write_agreement`のDeliverable書き込みは呼び出し元の
current_task_idにのみ許可）に気づきつつ（Expert自身の思考ログ「I cannot edit the
task_3_2_1 deliverable via edits here...」）、それでも`entry_type=Deliverable,
action_type=CREATE`を強行。結果、本文が丸ごとtask_3_2_1の内容（「# task_3_2_1 車両選定の
前提補完確認」から始まる）であるにもかかわらず、`task_id=task_1_1`のwhiteboard
（`phase_1_task_1_1_V11.md`）として保存された。

この回はモデル出力自体も劣化しており（`topic`/`task_id`引数に`"task_firm_placeholder"`,
`"Ver.firm_placeholder"`という文字列が混入 — `cela_main.py`内にこの文字列は存在せず、
CELA側のテンプレートバグではなく純粋なモデル劣化と確認済み）、Expertがどのtask_idへ
書くべきかを取り違えた可能性を示唆している。

`_write_agreement_impl`/`_commit_agreement_from_tool`には、Deliverable本文の見出しが
宣言先task_idと矛盾していないかを見るガードが存在しない。BL-146/BL-319はtask_idの
「宣言と現在タスクの一致」は見るが、「宣言task_idと本文の中身が実際に対応しているか」は
一切見ていない——ここが症状②の未検証ギャップ。

## 設計: write_agreement(Deliverable)の本文見出し/task_id不整合ガード

新規ヘルパー関数（`_commit_agreement_from_tool`の直前、`cela_main.py:3957`付近）:

```python
_DELIVERABLE_HEADING_TASK_ID_RE = re.compile(r'^#{1,3}\s*(task_\d+(?:_\d+)*)\b')

def _deliverable_heading_task_id_mismatch(content: str, tid: str) -> str | None:
    """[BL-321] 成果物本文の先頭見出しが宣言先task_idと異なるtask_idを名指ししていれば、
    そのtask_idを返す（見出しにtask_id言及なし、または一致していればNone）。
    実インシデント（log/2026-08-30/2051）: current_task_id=task_1_1のまま
    「# task_3_2_1 車両選定の前提補完確認」という他タスクの本文がtask_1_1の
    whiteboardへ丸ごと保存された。task_id自体は権威（BL-131/BL-212の設計方針）として
    扱い続けるが、見出しとの矛盾は書き込み前に機械的に検知できる安全網として追加する。
    """
    first_line = content.lstrip().split("\n", 1)[0]
    m = _DELIVERABLE_HEADING_TASK_ID_RE.match(first_line)
    if m and m.group(1) != tid:
        return m.group(1)
    return None
```

適用箇所は`_commit_agreement_from_tool`内、Deliverableの本文が「新規に」whiteboardへ
書き込まれる2箇所（どちらも既存のtid/phase_idが確定済みで、`apply_whiteboard_patch`
呼び出し直前）:

1. CREATE/SUPERSEDE時の初版保存（`cela_main.py:4038-4046`）
2. UPDATE時のedits未指定・全文置換（`not is_whiteboard`）分岐（`cela_main.py:4121-4126`）

**UPDATE-with-edits分岐（4087-4104）は対象外**——このパスはBL-265ガードにより
`read_whiteboard_excerpt`で実際の現在内容を確認済みであることが前提であり、既存task_idに
紐づくwhiteboardへの差分適用のため、見出し全体の付け替えが起きる局面ではない。

各箇所で`apply_whiteboard_patch`呼び出し直前に：
```python
_mismatch_tid = _deliverable_heading_task_id_mismatch(raw_content, tid)
if _mismatch_tid:
    return (
        f"成果物本文の見出しが'{_mismatch_tid}'を名指ししていますが、"
        f"書き込み先task_idは'{tid}'です（phase_id='{phase_id}'）。"
        f"本文の内容と書き込み先task_idが一致していません。"
        f"'{_mismatch_tid}'として書くつもりなら、write_agreementのtask_id引数を"
        f"'{_mismatch_tid}'に修正するか（current_task_idと異なる場合はまず正しい"
        f"タスクへ遷移してから）、本文の見出しを現在のタスク（'{tid}'）の内容に"
        f"修正してください。"
    ), None
```
（`_commit_agreement_from_tool`の戻り値型`tuple[str | None, str | None]`に合わせ、
第1要素をエラーメッセージとして返す——既存のFreeze拒否等と同じ形式。）

**誤検知許容範囲**: 見出し1行目のみを対象とし、正規表現は`task_\d+(_\d+)*`の厳密な形
（本文中の自由な言及ではなく行頭の見出しマーカー直後）に限定するため、「task_3_2_2の
スコアリングはtask_3_2_1の前提に依存する」のような本文中の相互参照は対象外——見出しが
まさに他タスクを名乗っているケース（今回の実インシデントそのもの）のみを検知する、
狭いスコープの安全網とする。

## 対象外・トレードオフ

- この修正は「モデルが反復collapseで劣化出力を返す」こと自体は防げない（プロバイダ/
  モデル側の問題の可能性）。これはCELA側の対処範囲外として明示する。
- 見出し1行目のみを見るため、見出しにtask_id言及がない成果物（多くのDeliverableは
  見出しにtask_idを含めない）には無力——今回のExpertが偶然「# task_3_2_1 ...」という
  慣習的な見出しを書いていたために検知可能だった。完全な内容分類（本文全体がどのタスクに
  ついてか）は不可能なため、これは「捕まえられる範囲だけ捕まえる」安全網として設計する
  （過剰な一般化はしない）。

## Critical Files

- `cela_main.py`:
  - `_commit_agreement_from_tool`直前（3957手前）: ヘルパー関数追加
  - `_commit_agreement_from_tool`内2箇所（4038, 4121付近）: ガード呼び出し追加

## Verification

1. `_deliverable_heading_task_id_mismatch`単体テスト——見出し一致/不一致/見出しに
   task_id言及なしの3パターン。`_commit_agreement_from_tool`統合テストで、今回の
   実インシデント相当（tid="task_1_1"、content先頭"# task_3_2_1 ..."）が拒否される
   ことを確認する回帰テスト。UPDATE-with-edits分岐は対象外のままであることも確認。
2. `python -m py_compile cela_main.py`
3. 影響範囲テスト: 既存のBL-131/BL-146/BL-212関連テストを再実行し非退行確認。
4. フルオフラインスイート実行。
