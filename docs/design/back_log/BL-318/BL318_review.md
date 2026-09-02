# BL-318 独立レビュー（cline）

実施日: 2026-08-30。実装前のPlan mode設計（初版）に対する独立レビュー。ユーザーがExitPlanModeを
拒否する形で本レビューを提示し、実装はこのレビューの指摘（C-1/I-1/I-2/M-1〜M-5）を反映した
修正版設計に基づいて行われた。AGENTS.md §16.2に従い、各指摘は実コードと突き合わせて検証した
上で採否を決定した（すべて採用）。原文をそのまま保存する。

---

clineによるレビューです

# BL-318 設計レビュー

検証方法：設計が参照する全コード箇所（ツールスキーマ `1101-1142`、impl `5511-5580`、`_resolve_task_transition` `16622-16764`、BL-190通知 `10812-10816`・消費 `5305-5345`・注入 `14812`、Stage4プロンプト `14889-14920`、`record_scheduling_decision` `3352-3375`、`_effective_current_task_id_from` `5474-5490`）を実ソースと突き合わせ、BL-191の設計書と既存テスト（BL-190/191/176/255）も確認しました。

## 総評

**方向性は妥当です。** decision_extractorの定性判断を置き換えず、BL-191の構造化フレームワークに確定的シグナルを追加する方針は §16.1（軽量な追加の優先）に合致し、BL-024（`_resolve_task_transition`唯一の書き手）も維持されます。設計が主張する前提は以下の通りすべてコードで検証済みです:

- decision_extractorの除外条件（「単なるレビューは移行に該当しない」）： `cela_main.py:13697-13700` に実在 ✓
- structured_redirect優先構造： `16637-16648` ✓
- ゲート再利用の成立： BL-125/176は `departing_task_id = state.get("current_task_id","")`（**生の値**、`16697-16700`、BL-214コメント）を使い、空文字なら BL-125 は早期return（`16609-16610`）、BL-176 は対象外（`16720-16722`）。つまりBL-190リコンサイル後（current_task_id=""）の復帰遷移は離脱ゲートに阻まれず、BL-255（対象側）のみ適用 ✓ — 設計の「ゲート複製なしで再利用」の主張は正しい
- `record_scheduling_decision` は decision_type 非依存の汎用合成（`3362-3365`）なので新type追加で破綻しない ✓
- ツール露出はStage4のみ（`14913`/`14920`）、BL-190通知の消費もStage4内（`14812`）✓

ただし、**実装前に修正すべき指摘が2件（Critical 1件）**、および確認すべき論点が多数あります。

---

## Critical

### C-1. `_schedule_task_focus_tool_impl` のファントムcurrent_task_id — 今回のインシデントと同型の誤帰属をimpl自体が再現する

設計§2の新分岐は既存変数 `current_task_id` を使いますが、これは `5530` の `_effective_current_task_id_from(state)` の戻り値です。BL-190リコンサイル後のstateは `current_task_id=""`・`current_phase=phases[0]` なので、実効値は **phases[0]の先頭タスク（今回のインシデントで14件の誤帰属を起こした 'task_1_1' そのもの）** になります。結果：

1. **`target_task_id == current_task_id` チェック（設計§2に明記）が誤拒否する** — User AIが正当に phases[0] の先頭タスクへ復帰しようとした瞬間「target_task_idは現在のタスクと同一です」で失敗し、本BLが解決しようとしている滞留状態が再現します。
2. **`record_scheduling_decision(..., current_task_id, ...)` がファントム値を departing task として記録する** — BL-146系の誤帰属クラスの再発。

`_resolve_task_transition` 側はBL-214で「departing_task_idは生の値が正しい」（`16697-16700`）とすでに裁定済みです。**advance_task分岐では「同一チェック」と「記録」の双方に生の `state.get("current_task_id", "")` を使う**ことを設計に明記してください（§13.2: フォールバック値の下流影響を書く前に追跡する、の適用）。verification に「リコンサイル後stateで phases[0].tasks[0] へのadvance_taskが成功し、scheduling_drafts行の primary_task_id が空文字であること」のテスト追加を推奨します。

## Important

### I-1. ツールdescriptionとの矛盾が残る（§15.1 / D-179と同型のドリフト）

description（`1106-1120`）には **「任意呼び出し（通常通り前進するだけの場合は呼ぶ必要はない）」** が残ります。設計§1が削除するのは「通常の『次タスクへ進む』指示とは別に」の一文だけで、修正後は **Stage4プロンプト「必ず呼べ」 vs ツールスキーマ「呼ばなくてよい」** の直接矛盾が生じます。§5の文言変更とセットで「advance_taskは通常の順方向遷移でも必須（推奨）、手戻り系（redirect_backward等）のみ任意」とdescription側も整合させてください。descriptionはdecision_typeごとの列挙説明になっているので、advance_taskの説明行の追加も明示してください。

### I-2. BL-190通知の消費経路が2箇所あり、片側はツールが使えない

`_build_task_transition_blocked_notice` は **Stage4（`14812`、ツールあり）** と **差し戻し・本質対話・Expert相談・終盤・初回ターン経路（`15267`、ツール一覧 `15251-15254` に schedule_task_focus なし）** の2箇所でone-shot消費されます。再計画の直後のラウンドが差し戻しラウンドだと、§4の新文言「schedule_task_focusツールを〜呼び」が**ツールを呼べないプロンプトに注入されてフラグだけ消費**されます。対応案：
- (a) 文言を「次回の最終段（Stage4）で〜」と段取り表現に変える（最小変更）
- (b) このnoticeの消費をStage4側に限定する（`15267`側でスキップ）
- (c) 該当経路にもツールを露出する（重い、非推奨）

設計にどれを採るか明記してください。最低限でも既知の限界として記載が必要です。

## Minor

- **M-1**: `_resolve_task_transition` のadvance_task分岐で `target_task_id` が空だった場合、`16652` で無音no-opします。impl側バリデーションが非空を保証する旨をコメントに残すか、loud warningを推奨（§15.4 出口確認）。
- **M-2**: `task_focus_stack` 非空（redirect_backward中断中）にadvance_taskが呼ばれると、スタックが宙吊りのまま `current_task_id` が動きます。自由文脈経路にも同型の穴はありますが、構造化ツールで明示的に呼べるようになるため、redirect_backwardと同じく「force_resumeで先に解消」ガード（`5544-5545`と同型）を入れるか、スコープ外として限界に明記することを推奨します。
- **M-3**: `_resolve_task_transition`（`16631-16635`）と `_schedule_task_focus_tool_impl` のdocstringにadvance_taskの説明を追記すること（§6 ステールコメント防止）。設計の変更箇所リストに入っていません。
- **M-4**: verification に `tests/test_bl190_current_phase_reconcile_after_replan.py`（`100-101` で通知文言 "廃止・統合" をアサート）と `tests/test_bl191_task_focus_scheduling.py:581` への影響確認を明示してください。新文言は「廃止・統合」とtask_id言及を保持しているため壊れない見込みですが、影響範囲として列挙すべきです。
- **M-5**: 優先順位テストは既存の `test_structured_redirect_takes_priority_over_freetext_transition`（test_bl191:437）のミラーで書ける旨をテスト設計に書くと実装が楽です。

## プロセス（§4）

- 設計書の `docs/design/back_log/BL-318/BL318_basic_design.md` への保存、issue_backlog起票、decision_log記載は設計どおりで問題ありません。加えて、**「ユーザーとの協議の結果…」という経緯は `decision_lineage.md` への記録対象**です（§4.9: 誰が何を根拠に決めたかの対話記録、D-xxxと相互リンク）。
- ライブラン適用時に誤帰属14件の是正を別合意とする立場は妥当です（§18.3: 破壊的修正前のバックアップ・承認手続きに整合）。

## 結論

| 区分 | 内容 |
|------|------|
| 承認（現状のまま実装可） | 方針（構造化シグナル追加＋自由文脈温存）、§3の分岐構造、ゲート再利用、verification項目の大半、データ是正のスコープ外宣言 |
| 修正後に実装可 | **C-1**（生のcurrent_task_id使用。修正しないとインシデント再現）、**I-1**（description整合） |
| 要判断 | **I-2**（通知消費経路の対応方針 a/b/c） |
| 推奨 | M-1〜M-5、decision_lineage記録 |

C-1は設計のコードスニペット自体に手を入れる必要があるため、このまま実装すると「BL-318がBL-146/BL-211と同型のフォールバック事故をimpl内に新設する」形になります。設計書にC-1/I-1/I-2の対応を反映した上でAct modeへ移行することを推奨します。

---

## 対応結果

すべての指摘を検証の上、採用した（詳細は`BL318_basic_design.md`および`decision_log.md` D-269）。

- **C-1**: `_schedule_task_focus_tool_impl`のadvance_task分岐で、同一チェック・`record_scheduling_decision`の両方に生の`state.get("current_task_id", "")`を使うよう修正。回帰テスト
  `test_advance_task_uses_raw_current_task_id_not_fallback_c1_regression`を追加。
- **I-1**: ツールdescriptionから「任意呼び出し」文言を削除し、advance_taskを標準的な確定記録手段として明記。
- **I-2**: 選択肢(b)を採用。`task_reassigned_after_replan_notice`の消費を`_build_task_transition_blocked_notice`から`_build_task_reassigned_notice`へ分離し、Stage4呼び出し箇所（`schedule_task_focus`ツールを持つ）からのみ消費するよう変更。15267側からは呼ばないため、ツールを持たない経路でone-shotが無為に消費されるリスクを構造的に排除した。
- **M-1**: `_resolve_task_transition`のadvance_task分岐へ、target_task_idが実質空にならない前提をコメントで明記。
- **M-2**: `task_focus_stack`非空時にadvance_taskを拒否するガードを追加。回帰テスト
  `test_advance_task_rejects_when_task_focus_stack_nonempty`を追加。
- **M-3**: `_schedule_task_focus_tool_impl`のdocstringにadvance_task分岐の説明を追記。
- **M-4**: `test_bl190_current_phase_reconcile_after_replan.py`の該当2テストを更新（
  `_build_task_transition_blocked_notice`がreassigned_noticeを消費しなくなったことを反映）、
  `test_bl191_task_focus_scheduling.py`は無変更で通過することを確認。
- **M-5**: `test_structured_redirect_takes_priority_over_freetext_transition`をミラーした
  `test_resolve_task_transition_advance_task_priority_over_conflicting_freetext`を追加。
