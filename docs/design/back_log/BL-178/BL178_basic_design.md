# BL-178: `call_expert`の`system_prompt`（フル版）／`light_system_prompt`（軽量版）を「視座は上から下、文脈は過去から現在」の順に再構成し、Detectorの差し戻し情報を両方で真に最後に読ませる 基本設計

## Context

`call_expert`は現在BL-104の原則（固定指示文を先頭・動的データを末尾、というプレフィックスキャッシュ効率重視の並び）に従っているが、ユーザーが実ログ（`log/2026-08-05/1049/log_with_prompt.md:19594-19970`）を精読した結果、この並びだけでは不十分であることが判明した。

具体的には、差し戻しターンにおいてDetectorの具体的な指摘（労働基準法・オペレーター人員体制の矛盾）を含む「⚠️【重要：Detectorからの差し戻し】」ブロックが`system_prompt`の中盤に埋め込まれる一方、`messages`配列では`system_prompt`の直後に生の`chat_history`がそのまま追記される。実ログでは`chat_history_window=4`の末尾4件がすべて無関係な「ハイブリッドモデル・3シナリオ」戦略の話題で占められており、Expertの応答は差し戻し指摘を汲み取れていなかった。ユーザーはこれを「可変部分は視座を上から下に、かつ過去から現在の順で情報提示しないと、狙った動作にならない」という設計原則として提起し、この過去ターンの調査で経験的に裏付けられた。

さらに調査の過程で、`_query_AI_live`（`cela_main.py:3512-3516`）が`light_system_prompt`をツールループiter=1完了時点で`loop_messages[0]`へ丸ごと置き換えることを確認した。これにより、iter=2以降は`system_prompt`が持っていた差し戻し情報・決定事項DB・厳守事項が完全に消え、`light_system_prompt`側には現状これらの内容が一切存在しない（BL-025 ②の「他タスク領域への逸脱防止」目的で作られた軽量版であり、差し戻し対応は設計時点で考慮されていなかった）。Expertが2回目以降のツール呼び出しへ進んだ瞬間、差し戻し修正の手がかりがコンテキストから丸ごと失われる構造的な欠落であり、フル版の並び替えだけでは解決しない別問題として扱う必要がある。

ユーザーはこの2点（フル版の並び替え、軽量版への差し戻し情報・厳守事項の追加）について、それぞれ具体的な項目順を提示し、AIが妥当性を確認した。本設計はこれを`call_expert`関数の実装レベルの変更計画へ落とし込む。

## 設計A: フル版`system_prompt`（iteration=1）— `messages`を3分割し、差し戻しを真に最後の要素にする

### 根本課題
`system_prompt`内でテキストの並び順をどう変えても、`messages`配列では`[system_prompt, ...chat_history]`という構造上、`chat_history`の最後のメッセージが常に物理的に最後に読まれる。したがって「差し戻し情報を最後に読ませる」ためには、`system_prompt`内でのテキスト位置の変更だけでは不十分で、**`chat_history`より後ろに新しいメッセージを追加する**必要がある。

### 対応方針
`system_prompt`を1つの文字列として組み立てる現行方式をやめ、**2つの文字列（先頭システムメッセージ用・末尾システムメッセージ用）に分けて組み立て**、`messages`配列を以下の3部構成にする：

```
messages = [
    {"role": "system", "content": system_prompt_leading},   # ①静的指示文＋過去〜現在の文脈（安定的な内容）
    ...chat_history（従来通り、role区別を保持したまま生メッセージとして展開）,
    {"role": "system", "content": system_prompt_trailing},  # ②決定事項DB→厳守事項→差し戻し（直近の是正内容）
]
```

複数の`role: "system"`メッセージを会話途中や末尾に挿入すること自体は、BL-093（`cela_main.py:3501-3504`、iter毎のreasoningダイジェストを`role: "system"`で末尾追記）で既に実績のあるパターンであり、新規リスクではない。

### `system_prompt_leading`の構成順（現行の`system_prompt`の対応箇所を移動するのみ、文言は変更しない）
1. （変更なし）識名・5ターン毎サマリー・🔥行動原則（escalate_premise_concern/ask_user_question説明含む）・📝回答形式・F-2.6検算ゲート・同じ検証を繰り返さない・ドメイン妥当性チェック・BL-134罠・🔀確定値/暫定値区別（`cela_main.py:5625-5741`、静的ブロック、無変更）
2. `expert_focus_guidance`（Orchestratorの着眼点、あれば）
3. 絶対的な行動指針＝ゴール文＋`_get_goal_essence_text`
4. `_build_detector_observations_block(state)`
5. `project_plan_toc`（📊プロジェクト進行計画 目次）
6. `task_scope_context`（現在のタスク／確定済みの値／未充足の要求項目）
7. `whiteboard_text`（📋R4: 成果物の差分編集）
8. `deferred_notes_text`（BL-082申し送り、あれば）
9. `escalation_status_text`（BL-086エスカレーション状況、あれば）
10. `_build_escalation_resume_notice(state)`（BL-096）
11. 「文脈の参考として以下に直近の会話を示します」導入文
12. （stateless modeのみ）`hydrate_context`＋`escalation_pin`＋`open_issue_pin`

### `system_prompt_trailing`の構成順（新設、`messages`末尾へ追加）
13. ⏳制限時間／終盤警告（turn_count関連）
14. 【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】＝`agreements_text`
15. ⚠️厳守事項（DB自作・勝手な決定宣言の禁止、位置的参照「上記の【決定事項DB】」はそのまま — 直前の14と同一メッセージ内に維持するため参照関係は崩れない）
16. ⚠️【重要：Detectorからの差し戻し】（`drift_flag`または`constraint_issue=="major"`の場合のみ、`_retry_label`＋前回却下内容＋Detector指摘事項＋対応方針。位置的参照「上記📋セクション」はwhiteboard_textが①側11番目より前に存在するため、別メッセージへ分かれても文脈上は成立する）

### 既存テストへの影響（`test_bl104_project_plan_toc_and_prompt_reorder.py`を確認済み）
`inspect.getsource(cela_main.call_expert)`によるソースコード上の位置検証7件（静的ブロックが動的ブロックより前／DB直後に厳守事項／whiteboard直後より後に差し戻し、等）は、いずれも「静的グループ全体 < 動的グループ全体」「DB→厳守事項の隣接順」「whiteboard→差し戻しの前後関係」のみを検証しており、動的グループ内部の細かい並び替えは検証していない。上記の新順序はこれらの制約をすべて維持したまま実現できるため、**この7件は無改修で通過する見込み**（BL-177実装時にBL-104テストの書き直しが不要だったのと同型の結果）。新規順序自体（例：expert_focus_guidanceがgoalより前、差し戻しが本当に最後の要素であること等）を検証する新規テストを別途追加する。

## 設計B: `light_system_prompt`（iter=2以降）— 内部順序の並び替え＋新規2ブロック追加

### 既知の限界（設計スコープとして明記）
`light_system_prompt`は`_query_AI_live`により`loop_messages[0]`（system role）へ丸ごと置換されるだけであり（`cela_main.py:3512-3516`）、`loop_messages[1:]`（元の`chat_history`＋以降積み上がるtool呼び出し履歴）はこの一度の置換の影響を受けず、そのままindex 0の直後に残り続ける。したがって、**`light_system_prompt`内部でどれだけ差し戻し情報を末尾に配置しても、iter=3以降に積み上がるtool呼び出し履歴の方が物理的にはさらに後ろへ来る**ため、設計Aと同じ意味での「真に最後」は達成できない。この制約は`query_AI`共通基盤（全ノード共有）に踏み込む変更が必要になり、本BLのスコープ外とする。今回は「差し戻し情報が軽量版に一切存在しない」という現状（=0）を「末尾に条件付きで存在する」（設計Aと同じ相対原則を適用）へ改善するに留め、真の解決（tool呼び出し履歴の末尾へ定期的にリマインダーを再注入する等、BL-016/BL-056bの残り回数通知と同型の仕組み）は`issue_backlog.md`へ将来検討課題として記録する。

### 新しい`light_system_prompt`の構成順（ユーザー提示順をそのまま採用）
1. 専門分野の名乗り
2. 現在のタスク／確定済みの値／未充足の要求項目（`current_task_json`/`verified_facts_json`/`remaining_criteria_text`）
3. `expert_focus_guidance`（あれば）
4. 他タスクowns_variables不可侵の一言
5. BL-041 confidence=provisionalの一言
6. 使えるツール一覧の明示（現行は末尾にあるものを先頭寄りへ移動）
7. escalate_premise_concern（BL-086）／ask_user_question（BL-130）／read_verified_fact・read_deliverable_file・read_project_plan（BL-094）／think（BL-093）の使い方（相対順は現状維持）
8. python_repl必須の一言（現行は5番目付近にあるものをここへ移動）
9. **新規** 厳守事項：フル版の文言「上記の【決定事項DB】は…」をそのまま流用すると軽量版にはDBブロック自体が存在せず「上記の」が空参照になるため、独立文へ書き換える（例：「決定事項DBはシステム側で自動管理されます。あなたの回答内でDBブロックを自作したり、勝手に『決定事項』と宣言したりしないでください。」）
10. `[R4] {whiteboard_text}`
11. **新規** Detectorからの差し戻し情報：`drift_flag`または`constraint_issue=="major"`の場合のみ、`_retry_label`＋Detector指摘事項（`constraint_issue_log[-1:]`）の要約を追加。フル版と異なり`previous_output`全文の再掲は行わない（軽量版の「軽量」という目的に反するため。iter=2以降はExpert自身が今回の応答を推敲中であり、「何を直すべきか」の要点があれば足りる。whiteboard本文＝10番目は既に含まれているため、[BL-076]インライン注釈との重複確認も可能）

## 実装ファイル
- `cela_main.py`の`call_expert`関数（`cela_main.py:5598-5941`）: `system_prompt`の組み立てを`system_prompt_leading`／`system_prompt_trailing`の2変数へ分割し、`messages`配列の組み立てを3部構成へ変更。`light_system_prompt`（`cela_main.py:5894-5933`）の構成順を上記11項目へ並び替え、新規2ブロックを追加。
- `tests/test_bl104_project_plan_toc_and_prompt_reorder.py`: 既存7件（call_expert関連）は無改修で通る見込みだが、実装後に確認する。新順序を検証する新規テストケースをこのファイルへ追加する（既存の`inspect.getsource`ベースのパターンを踏襲）。
- 新規テストファイル（例: `tests/test_bl178_expert_prompt_reorder.py`）: `messages`が3部構成になっていること（`call_expert`を`query_AI`をモックして直接呼び出し、`messages`の`role`/`content`を検証）、`light_system_prompt`の新規2ブロックの内容・条件分岐（drift_flag/major時のみ出現）を検証。
- `docs/design/back_log/issue_backlog.md`: BL-178を新規起票（本設計を実装完了後に「done」化）。設計Bの「既知の限界」節で触れた将来課題（tool呼び出し履歴末尾への差し戻しリマインダー再注入）をBL-178の残課題として記録する。
- `docs/design/decision_log.md`: D-147として、フル版3分割・軽量版再構成それぞれの決定理由（実ログでの裏付け・`_query_AI_live`の置換メカニズム調査結果）を記録。
- `docs/design/decision_lineage.md`: 論点128として、ログ精読での発見からユーザー提案・確認までの経緯を記録。
- `docs/design/back_log/BL-178/BL178_basic_design.md`: 本設計を原文保存（AGENTS.md §7準拠）。

## 検証方針
1. `python -m py_compile cela_main.py`
2. `test_bl104_project_plan_toc_and_prompt_reorder.py`のcall_expert関連7件が無改修で通ることを確認（想定通りでなければ、検証意図を保ったまま更新）。
3. 新規テストで、`messages`が3部構成であること・`system_prompt_trailing`が差し戻し時のみ差し戻しブロックを含み通常時は含まないこと・`light_system_prompt`の新規2ブロックが条件通り出現/非出現することを確認。
4. `test_bl078_orchestrator_focus_guidance.py`（`expert_focus_guidance`がフル版・軽量版の両方に登場することを検証、`src.count(...) >= 2`）等、call_expertのsource文字列に依存する既存テスト群が無改修で通ることを確認。
5. フルオフラインスイート実行、無退行確認。
6. 実ドライランでの効果確認（差し戻しターンでExpertがDetector指摘を正しく汲み取るようになったか）は次回以降。

## 実装しないもの（今回のスコープ外）
- `light_system_prompt`が`loop_messages[0]`に固定される構造自体の変更（tool呼び出し履歴末尾への差し戻しリマインダー再注入等）。将来課題としてissue_backlog.mdへ記録するに留める。
- `call_expert`以外のノード（Detector・Facilitator等）へのBL-177的な一般化・同種の並び替え適用（BL-177の既存スコープ外事項と同じ扱い）。
