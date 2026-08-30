# BL-320: decision_extractorの劣化出力ノーガード問題

（本設計はBL-321と同一の調査・Plan modeセッションで作成された。症状②・BL-321側の設計は
`docs/design/back_log/BL-321/BL321_basic_design.md`を参照。ExitPlanModeで承認された
プラン本文をそのまま保存する。）

## Context

2026-08-30 20:51起動のドライラン（run_id=1787890406-1e73a89d、`log/2026-08-30/2051/`）で、
ユーザーから2つの症状が報告された：

1. 「Decision Extractorが壊れた」
2. 「`phase_1_task_1_1_V11.md`のファイル名と中身のtask_idが乖離」

実ログ・DBを直接調査した結果、両方とも根っこは同じ「モデル出力がJSON生成中に反復collapseへ
突入し、劣化した（ゴミトークン・欠落フィールド）出力を返す」現象だが、CELA側の受け止め方に
**別々の未検証ギャップ**があることが判明した。ユーザーは両方の対処を承認済み（「両方対処して
ください」）。ドライランは対応中は停止済み（ユーザーが確認）。

### 症状①: decision_extractorの検証網の穴（BL-213 F3の対象漏れ）

`call_decision_extractor`の2件目の抽出イベントで、モデル出力が`"topic"`フィールドまでは
出力した後、`"_comment_removed": null, "_note_removed": null, ...`という無意味なキーの
反復生成に突入し、最終的に`"__invalid_key_to_ignore__"`等のゴミキーが延々と続いて終了した
（`log/2026-08-30/2051/log_no_prompt.md:592-651`）。本来入るべき`content`/`rationale`/
`task_id`/`phase_id`/`proposed_by`が一切出力されなかった。

`_check_extracted_event`（`cela_main.py:13644`）はentry_type/action_type/target_topic
（UPDATE時のみ）/status/topic/proposed_byしか検証しておらず、この項目は「proposed_by欠落」
というminor（正規化対象）としてのみ検出され、fatal（破棄）には該当しなかった。結果、
`item.get("task_id") or _effective_current_task_id_from(state)`（`cela_main.py:17270`）
が発火し、内容も理由も空の劣化レコードが`task_id='task_1_1'`のDirectiveとしてDBへ
サイレントに書き込まれた（実DB確認済み：`AG-1788091395328-13ee73`、topic="task__1成果物の
正式確定・Ver.提出指示（修正条件①〜④）" — 本来"task_3_2_1"のはずが数字が反復collapseで
欠落した状態）。

**注意（重要）**: `task_id`が空欄であること自体は正常系である（BL-040のコメント通り、
LLMがtask_idを省略し呼び出し元のcurrent_task_idへフォールバックするのは全ターンの約46%で
発生する意図された挙動）。したがって「task_idが空なら常にfatal」という単純な修正は、
正当な省略ケースを大量に誤って破棄する副作用がある。実際に事故の引き金になったのは
task_id単体の欠落ではなく、**この項目が実質的に空っぽ（content/rationale/task_id/phase_id
すべて欠落）だったこと**、および**ドキュメント化されたスキーマに存在しないキー
（`_comment_removed`、`__junk__`等）が大量に混入していたこと**である。この2点はどちらも
「反復collapseで劣化した出力」を高精度・低誤検知で機械的に検知できる、より的確なシグナル。

## 設計: decision_extractor抽出項目に対する劣化出力検知（2つのfatalチェックを追加）

`_check_extracted_event`（`cela_main.py:13644`）へ、既存のentry_type/action_type/
target_topicチェックと並ぶ形で以下2つのfatalチェックを追加する：

**(a) CREATE時のcontent必須化**
`action_type == "CREATE"` かつ `entry_type in {"Decision", "Directive", "Deliverable"}`
のとき、`item.get("content")`が空文字ならfatal。
- 根拠: プロンプト仕様（`cela_main.py:13892-13895`）上、UPDATE時のcontent=""は
  「Userが評価しただけ」を意味する正規パターンだが、CREATE時にcontentが空という状態は
  プロンプトのどこにも許容されていない（Deliverableでも「200字以内の要約」であって
  空文字ではない）。
- 安全性: BL-182の「write_agreement経由で既に登録済みの場合はこの抽出結果自体が
  まるごと破棄される」重複排除は、この検証より後段（消費ループ内の
  `_is_duplicate_of_direct_write`）で行われる。検証時点でfatal破棄しても、
  重複排除で結局捨てられるはずだった項目が捨てられるだけで実害はない。

**(b) 未知キー混入の検知**
ドキュメント化されたスキーマキー集合
`{"action_type","entry_type","target_topic","status","topic","content","rationale",
"proposed_by","phase_id","task_id","owned_variable_values","defer_to_task_id"}`
に含まれないキーが1件でも項目内に存在すればfatal。
- 根拠: 反復collapseは`_comment_removed`/`__junk__`等、スキーマに存在しない一意な
  キー名を生成する。これはtask_id等の特定フィールドに依存しない、汎用的で誤検知の
  少ない劣化検知シグナル。

`_sanitize_extracted_events`のfatal時ログ（`cela_main.py:13735`）は既存の破棄理由
フォーマットをそのまま使うため変更不要。`_validate_extracted_events`（`cela_main.py:13697`）
はfatalが1件でもあれば自己修正リトライを発火させる既存動線に自然に乗る——今回のような
劣化は本来リトライで是正される機会を得られるようになる（今回は検証網の穴でリトライすら
発火しなかった）。

## 対象外・トレードオフ

- この修正は「モデルが反復collapseで劣化出力を返す」こと自体は防げない（プロバイダ/
  モデル側の問題の可能性）。これはCELA側の対処範囲外として明示する。
- content必須化は、CREATE時に正当な理由でcontentが極端に短い/一見空に近いレコードを
  誤ってfatal判定する可能性はゼロではないが、空文字そのものへの判定なので誤検知余地は
  小さい。

## Critical Files

- `cela_main.py`: `_check_extracted_event`（13644付近）にfatalチェック2件追加

## Verification

1. `_check_extracted_event`単体テスト——(a) CREATE+content=""がfatal、UPDATE+content=""は
   従来通り非fatal、(b) 未知キー混入がfatal、既知キーのみは非fatal。今回の実インシデント
   JSON（簡略版）を`_sanitize_extracted_events`に通し、破棄されることを確認する回帰テスト。
2. `python -m py_compile cela_main.py`
3. 影響範囲テスト: 既存のBL-213関連テストを再実行し非退行確認。
4. フルオフラインスイート実行。
