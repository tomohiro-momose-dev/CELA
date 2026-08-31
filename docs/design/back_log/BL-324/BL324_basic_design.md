# BL-324: 「真に人間の判断が必要」なissueを、Reflector監査を経て（または監査役自身の
判断で）グラフ全体の一時停止へ接続する

## 【この設計に至った経緯（重要）】

当初の提案（BL-158の機械的差し戻しをhuman-onlyで除外するだけの修正）は、ユーザーから
2回の訂正を受けて撤回した。

1回目：ユーザーは「human-onlyのissueが立った時点で即座にHILへ移行し人間の回答を
待つべき」と指摘——理由は「必要な情報・判断をペンディングしたままタスクが進むと、
人間回答後に手戻りが発生するリスクがある」ため。これを受け、`escalate_premise_concern`
が持つ「グラフ全体を一時停止しHIL回答後に--resumeで復帰する」既存機構
（`pause_for_human_node`）を`flag_needs_human_input`にも適用する方向へ設計変更した。

2回目：ユーザーは「即座に」の意味をさらに精緻化した——(a) User AI/Expert/Detectorが
「AIの知見・WEB検索では埒が明かない（合理的仮定値の使用が危険で実世界の判断が必要）」
と判断した場合は、即座に一時停止するのではなく、まずReflectorへ回し、HIL候補の内容と
周辺議論を俯瞰した監査で「合理的」と認められて初めて一時停止を発行する。(b)
Reflector/Facilitator自身が定期監査の中で「指摘を重ねても停滞する」「前提・条件の
根本的な食い違い」と判断した場合は、追加監査を挟まず直接一時停止する。

以下はユーザーとの往復で確認済み：
- 既存`flag_needs_human_input`を拡張（新規ツールは作らない）。
- Facilitatorの現行「facilitation_countが5回超でhalt（不可逆停止）」は、この新しい
  一時停止（人間回答後--resumeで復帰可能）へ置き換える。

## Context

現在HILで一時停止中のライブラン（run_id=1787890406-1e73a89d）で、User AIが
`escalate_premise_concern`によりプロセス上の矛盾（ESC-1788103398227-4a6f3f）を提起した。
実DB調査（issue_log id=9df606db-996e-4796-a678-a93767d42e02、
topic=`existing_power_contract_capacity_verification`、task_id=task_3_4）で以下を確認した：

- `human_research_prompt`が設定された人間専用issue（車庫候補地の電力契約容量、AIには
  照会手段なし）。`write_issue(RESOLVE)`/`write_issue(DEFER)`は`_is_human_only_issue`
  （cela_main.py:4645）により構造的に拒否される（BL-236の意図的な保護）。`ACKNOWLEDGE`は
  `_BL194_ACK_MAX_GRANTS=2`（cela_main.py:5169）で使い切り済み。結果、AI側でこのissueを
  「今回のターンで正式に対処した」と記録する手段が一つも残っていない。
- Expertは既に「50kW暫定推定＋条件付き判定＋要人間確認flag」という形で透明に対応済み
  （issue_logの`acknowledge_reason`参照）。この判断の正しさを検証するのはDetectorの
  独立監査であり、今回の変更でも一切変更しない。

現状`flag_needs_human_input`（Expert専用、cela_main.py:1056/4939）はissue_logへ記録する
だけで、グラフは一切停止しない（`escalate_premise_concern`のみが`pause_for_human_node`
経由でグラフ全体を一時停止する）。今回、両者を「本当に人間の判断が必要」という共通の
意味で統合し、発行元roleに応じた二段階の運用にする。

## 設計

### 1. `flag_needs_human_input`の呼び出し可能role拡大

`_flag_needs_human_input_tool_impl`（cela_main.py:4939）の許可チェックを
`caller_role != "expert"` から `caller_role not in ("expert", "user", "detector",
"reflector", "facilitator")` へ拡大する。

ツール自体（`FLAG_NEEDS_HUMAN_INPUT_TOOL`）を以下のツールリストへ追加する
（`ESCALATE_PREMISE_CONCERN_TOOL`が既に配線されている箇所と対応。Reflectorは
tool-callingループを持たないため対象外——後述）：
- Expert: `_expert_tools`（cela_main.py:12794）——**既に配線済み、変更不要**
- User AI: `_user_ai_main_tools`（15657付近）、Stage2の issue確認ツールリスト（14956付近）
- Detector: `_detector_numeric_tools`（13592付近）、`_detector_domain_tools`（13340付近）
- Facilitator: `_facilitator_tools`（14568付近）

### 2. issue_logへ`human_judgment_status`列を追加

```sql
ALTER TABLE issue_log ADD COLUMN human_judgment_status TEXT DEFAULT ''
```
（既存の`ALTER TABLE issue_log ADD COLUMN ...`スキーマ移行パターン、cela_main.py:7757
付近に倣う。）値は以下の3状態＋既定の空文字（本機構と無関係の既存issueすべて）：
- `'pending_reflector_review'` — user/expert/detectorが起票し、Reflectorの監査待ち。
- `'confirmed'` — Reflectorが承認、またはreflector/facilitator自身が直接起票——
  グラフ全体の一時停止をトリガーする。
- `'reviewed_insufficient'` — Reflectorが「人間の判断は不要、合理的仮定値で足りる」と
  判定——直後にissue自体を`status='resolved'`とし、Reflectorの判断根拠を
  `resolution_note`へ記録する（AIを待機状態のまま放置しない）。

`_flag_needs_human_input_tool_impl`で、caller_roleに応じて`human_judgment_status`の
初期値を分岐する：
```python
_initial_status = "confirmed" if caller_role in ("reflector", "facilitator") else "pending_reflector_review"
```

### 3. 一時停止トリガーの拡張（`pause_for_human_node`系の一般化）

既存の`escalate_premise_concern`用一時停止機構（`state["paused_for_premise_escalation"]`
+ `state["pending_premise_escalation_id"]`、`_should_pause_for_human`、
`pause_for_human_node`）と並ぶ、新しいstateフィールドを追加する：
```python
pending_human_judgment_issue_id: str  # LineageState TypedDictへ追加
```

`_should_pause_for_human`（cela_main.py:15764）を拡張：
```python
def _should_pause_for_human(state: dict) -> bool:
    return bool(state.get("paused_for_premise_escalation")) or bool(state.get("pending_human_judgment_issue_id"))
```
既存の5箇所の呼び出し元（すべて`_should_pause_for_human(state)`→`"pause_for_human"`への
ルーティング）は変更不要——判定関数の拡張だけで自動的に新トリガーを拾う。

`pause_for_human_node`（cela_main.py:18317）を拡張し、`pending_human_judgment_issue_id`が
設定されている場合はissue_logから該当行を取得し、`human_research_prompt`/`description`を
使って同型の一時停止メッセージを出力する（`pending_premise_escalation_id`と排他的に分岐）。

resume時のクリーンアップ（cela_main.py:18901/18916-18933付近）で、
`pending_premise_escalation_id`と同様に`pending_human_judgment_issue_id`もリセットする。

**[Cline独立レビューで発覚・検証済みの必須修正 2-1]** 既存のresumeガード
（18915-18933）は`_get_goal_escalation_hil_decision`（`goal_escalations`系の回答有無を
`verified_facts`から確認）のみをチェックしており、issue_log系の新経路には対応しない。
このままだと「回答なしでresumeが素通りする」または「resumeが永久にできない」のいずれかの
欠陥になる。`pending_human_judgment_issue_id`が設定されている場合、issue_logから
該当行の`status`を引き、`status=='resolved'`（`--answer-human-input`——既存のBL-217
CLI、`_answer_human_input`が`status='resolved'`をセットする、cela_main.py:9560-9564——
で人間が回答済み）であることを権威ストア（§13.3）から確認してから一時停止を解除する。
未解決なら`paused_for_premise_escalation`の場合と同型のメッセージ
（`--answer-human-input --topic <topic> --value <確定値> --unit <単位> --source <出典>`
を促す）を出して`return`する。`paused_for_premise_escalation`と
`pending_human_judgment_issue_id`は同時に立ちうる想定はしない（設計上排他）が、
念のため両方のガードを独立して順にチェックする。

**[Cline独立レビューで発覚・検証済みの必須修正 2-2]** `facilitation_count`は初期化時
（18829付近、新規run作成時のみ）に0が入るが、resume時にはリセットされない
（grep確認済み：facilitation_countへの代入は17992のインクリメントと18829の初期化のみ）。
現行の`halt`（不可逆停止）はfacilitation_countが残っていても問題にならなかったが、
今回halt→一時停止（可逆）へ変更すると、resume直後の次回facilitator_node呼び出しで
`facilitation_count > 5`が再び真になり、**一時停止→resume→即再一時停止の無限ループ**に
陥る。resume時のクリーンアップで`pending_human_judgment_issue_id`をリセットする
タイミングと同じ箇所で、raised_by='facilitator'のissue由来の一時停止だった場合に限り
（他の起票元では無関係なfacilitation_countを触らない）`state["facilitation_count"] = 0`
もリセットする。

### 4. Facilitatorが直接起票する経路（ツール呼び出し、ブリッジ必要）

Facilitatorは既にtool-callingループを持つ（`_facilitator_tools`、escalate_premise_concern
の橋渡しが`facilitator_node`内に既存、cela_main.py:18042）。同じパターンで
`flag_needs_human_input`の成功をモジュールグローバル経由で橋渡しする：
新規`_LAST_HUMAN_JUDGMENT_FLAG`（成功時のissue_id等を保持）+ `get_last_human_judgment_flag()`。

**[Cline独立レビューで発覚・検証済みの必須修正 2-3]** 他のモジュールグローバルブリッジ
（`_LAST_PREMISE_ESCALATION`等）と同じ二重ガードパターンに揃える必要がある：
(a) `_query_AI`冒頭のリセットブロック（cela_main.py:6036-6050、`global`宣言リストと
毎回`None`/空へ初期化する処理）へ`_LAST_HUMAN_JUDGMENT_FLAG`を追加する（追加しないと、
前のターンの古いflagが後続の無関係なターンで誤って消費される）。(b) ツール結果処理
ループ（cela_main.py:6922-6931、`elif tc.function.name == "escalate_premise_concern":`
の並びにある「success=Falseの場合は絶対に反映しない」二重ガード）に
`elif tc.function.name == "flag_needs_human_input":`を追加し、`result.get("success")`かつ
`result`に含まれる`human_judgment_status`（`_flag_needs_human_input_tool_impl`の戻り値へ
追加する）を見て格納する。

`facilitator_node`内、既存のescalate_premise_concern橋渡し直後に追加：
```python
_human_judgment = get_last_human_judgment_flag()
if _human_judgment and _human_judgment.get("human_judgment_status") == "confirmed":
    state["pending_human_judgment_issue_id"] = _human_judgment["issue_id"]
```

Expert/User AI/Detectorの成功時も同じブリッジ経由でissue_idが取れるが、これらのroleでは
`human_judgment_status`は常に`'pending_reflector_review'`（`'confirmed'`にはならない）ため、
上記条件文は素通りする——**これらのnode（expert_node/generate_user_utterance_node/
detector_node）への橋渡し配線は不要**（Reflectorの監査を経るまで一時停止が発生しない
設計そのままで正しい）。

### 5. Facilitatorの「facilitation_count > 5 → halt」を一時停止へ変更

cela_main.py:17993-17998の`state["halt"] = True`分岐を、issue_logへ直接
`human_judgment_status='confirmed'`のCREATE行を挿入し（`raised_by='facilitator'`、
description="facilitation_countが上限(5回)に達しても議論が改善しなかったため人間の
介入が必要"）、`state["pending_human_judgment_issue_id"]`をセットして`return state`する
形へ変更する（`state["halt"]`は設定しない）。

### 6. Reflectorの監査（`reflection_node`/`call_reflection`の拡張）

Reflectorはtool-callingループを持たない単発JSON応答（`call_reflection`、cela_main.py:
14174）のため、ツール呼び出しではなく**JSON応答スキーマの拡張**で扱う。

`call_reflection`のプロンプトへ、`human_judgment_status='pending_reflector_review'`の
issue一覧（topic/human_research_prompt/description/raised_by）を新規ブロックとして注入し、
各issueについて「AI自身の合理的仮定値で十分か、真に人間の判断が必要か」を判定させる。
応答JSONスキーマへ新規フィールドを追加：
```json
{
  "discussion_status": "...",
  "human_judgment_reviews": [
    {"issue_id": "...", "decision": "confirm または insufficient", "reasoning": "..."}
  ],
  "new_human_judgment_escalation": {
    "topic": "...", "variable_name": "...", "human_research_prompt": "...",
    "description": "...", "severity": "major"
  }
}
```
（`new_human_judgment_escalation`はReflector自身が定期監査中に新たに「人間の介入が
必要」と判断した場合のみ設定、無ければnull/省略。）

`reflection_node`側（既存のBL-145 stale-escalated処理と同じ並びに追加）：
- `human_judgment_reviews`の各項目について、対象issue_logの`human_judgment_status`を
  `'confirmed'`または`'reviewed_insufficient'`へ更新。`'reviewed_insufficient'`の場合は
  `status='resolved'`、`resolved_by='reflector'`、`resolution_note=reasoning`も設定。
  `'confirmed'`が1件でもあれば`state["pending_human_judgment_issue_id"]`を設定
  （複数ある場合は最初の1件——次回resume後の巡回で残りも処理される）。
- `new_human_judgment_escalation`が設定されていれば、issue_logへ`human_judgment_status=
  'confirmed'`のCREATE行を直接挿入し（`raised_by='reflector'`）、
  `state["pending_human_judgment_issue_id"]`を設定。

### 7. BL-158の副次的な不整合修正（低リスク・低コストなので同時対応）

調査中に発見した既存バグ：`_get_blocking_issues_for_transition`のBL-158呼び出し箇所
（cela_main.py:16718-16739）は`exclude_acknowledged`引数を渡しておらず、同関数の
docstring（16888-16891）が意図する「ACK猶予期間中は督促を止める」という設計と
実装が乖離している。`exclude_acknowledged=True, round_count=state.get("round_count", 0)`
を渡すよう修正する。これは`pending_reflector_review`状態の間（Reflectorの次回巡回まで）
のみ影響する軽微な修正で、本設計の主要部分とは独立して安全に適用できる。
`human_judgment_status`に基づく除外は追加しない（Reflectorが確認するまでは通常issueと
同じ扱いのままにする、という設計方針のため）。

## 対象外・トレードオフ

- BL-125の実離脱ゲート（cela_main.py:16991-17008）は対象外。「今対応中でも未解決のまま
  離脱させない」という既存の歯止め（BL-194 D-164）は維持する。
- `pending_reflector_review`状態の間（reflection_interval、既定3ラウンド）は、issueは
  通常のescalated issueと同じ扱いを受ける（BL-125/144/145/158の対象のまま）。この間は
  「即座の一時停止」ではないが、ユーザーとの合意（2回目の訂正）通りの設計。
- Reflectorの1回の監査で複数の`pending_reflector_review`issueをまとめて処理できるが、
  一時停止トリガー（`pending_human_judgment_issue_id`）は最初の1件のみをstateへ載せる。
  resume後の次回reflection巡回で残りも同様に処理される（設計をシンプルに保つための
  意図的な単純化——同時に複数の一時停止理由を1つのstateフィールドで表現しない）。

**[Cline独立レビュー: 行番号は目安]** 以下の行番号は本Plan作成時点でのcode確認済みの位置
（Clineの独立レビューでも全件一致を確認済み）だが、実装着手までにライブラン等での
他コミットが入る可能性があるため、実装直前に関数・変数のシンボル名で改めて特定すること。

## Critical Files

- `cela_main.py`:
  - `_flag_needs_human_input_tool_impl`（4939付近）: 許可role拡大、
    `human_judgment_status`初期値分岐、戻り値へ`human_judgment_status`追加
    （モジュールグローバルブリッジが読むため）
  - `_query_AI`冒頭のリセットブロック（6036-6050付近）へ`_LAST_HUMAN_JUDGMENT_FLAG`追加
  - ツール結果処理ループ（6922-6931付近）へ`flag_needs_human_input`の
    成功時ブリッジ格納を追加
  - ツールリスト4箇所（Detector×2、User AI×2）へ`FLAG_NEEDS_HUMAN_INPUT_TOOL`追加
  - `_facilitator_tools`は既存配線を確認のみ（無ければ追加）
  - User AI/Detector/Facilitatorの該当ノードプロンプトへ、
    「いつflag_needs_human_input（拡張版）を使うべきか」の説明を追記
    （D-179型の「スキーマにだけあってプロンプトで説明されないツール」事故の再発防止）
  - issue_logスキーマ移行（`human_judgment_status`列追加、7757付近のパターンに倣う）
  - `_should_pause_for_human`（15764）、`pause_for_human_node`（18317）の拡張
  - resume時クリーンアップ（18901/18916-18933付近）の拡張:
    `pending_human_judgment_issue_id`のissue_log `status`確認（`resolved`でなければ
    resume拒否）、リセット、`facilitation_count`の条件付きリセット（facilitator発の
    一時停止だった場合のみ）
  - `facilitator_node`（17948）: escalate_premise_concernブリッジ直後に新規ブリッジ追加、
    facilitation_count>5のhalt分岐（17993-17998）を一時停止へ変更
  - `call_reflection`（14174）: プロンプトへpending issue一覧を注入、JSON応答スキーマ拡張
  - `reflection_node`（17692）: `human_judgment_reviews`/`new_human_judgment_escalation`の
    処理を追加。`reviewed_insufficient`時の`status='resolved'`直接書き込みは
    `_is_human_only_issue`ガード付き正規経路（write_issue RESOLVE）と別の第2書き込み経路と
    なるため、`decision_log.md`にその旨と対称性の判断（`human_judgment_status`は
    `pending_reflector_review`の行のみ対象とする不変条件）を明記する（AGENTS.md §13.4）。
  - `_get_blocking_issues_for_transition`のBL-158呼び出し箇所（16718-16739）へ
    `exclude_acknowledged=True`を追加
  - `LineageState`（10519付近）へ`pending_human_judgment_issue_id: str`追加
- `tests/test_bl324_human_judgment_escalation.py`（新規）

## Verification

1. `_flag_needs_human_input_tool_impl`——5role全てから呼び出し可能なこと、
   caller_role別の`human_judgment_status`初期値（expert/user/detector→
   pending_reflector_review、reflector/facilitator→confirmed）。
2. `pause_for_human_node`/`_should_pause_for_human`——`pending_human_judgment_issue_id`
   設定時に一時停止すること、`pending_premise_escalation_id`との排他的な報告分岐、
   両方未設定時は非退行。
3. Facilitatorのツール呼び出し経由での直接確定→一時停止までの統合テスト。
4. facilitation_count>5でのhalt→一時停止への変更（`state["halt"]`が設定されず
   `pending_human_judgment_issue_id`が設定されること）。
5. Reflectorの監査ロジック——`human_judgment_reviews`のconfirm/insufficient両方の
   処理（issue_log更新、insufficientはstatus='resolved'化）、`new_human_judgment_
   escalation`によるReflector自身の新規起票、両方揃った場合の優先順位。
6. resumeクリーンアップの拡張確認——(a) issue未解決（status≠'resolved'）ならresumeが
   拒否されメッセージが出ること、(b) 解決済みならresumeが通り`pending_human_judgment_
   issue_id`と（facilitator発の場合のみ）`facilitation_count`がリセットされること、
   (c) resume後に即座に再度facilitator_nodeがhalt/一時停止しないこと（無限ループの
   再発防止テスト）。
7. BL-158の`exclude_acknowledged=True`修正の単体テスト（ACK猶予期間中は督促されない、
   猶予切れ後は従来通り督促される）。AGENTS.md §17.1に従い、修正をrevertして新規
   テストが失敗することを確認した上で復元する。
8. `python -m py_compile cela_main.py`
9. 影響範囲テスト: BL-236/BL-194/BL-217/BL-126(Stage D)/BL-313関連テストを再実行し非退行確認
   （escalate_premise_concernの既存経路・facilitation_countの既存経路に触れるため）。
10. フルオフラインスイート実行。
11. 実装後、`docs/design/back_log/BL-324/BL324_basic_design.md`へ実装前保存、
    `issue_backlog.md`にBL-324を記載（優先対応一覧＋詳細セクション両方）、
    `decision_log.md`へ決定を記録する。resumeの判断は別途ユーザーと相談する
    （このBLのスコープには含めない）。
