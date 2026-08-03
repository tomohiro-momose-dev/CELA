# BL-145 実装: escalated issueをReflectorの正当性監査経由でタスクプランナーへ明示的に組み込む

Plan Mode（Explore 1体 + Plan 1体）で作成した実装計画に、ユーザーとの設計協議（`resolved`→`planned`への変更等）を反映した最終版。実装結果は`docs/design/back_log/issue_backlog.md`のBL-145詳細セクション参照。

## Context

`log/2026-08-03/1347`ドライランのレビューで、`detector_observation_task_1_1`という汎用issue（detector_auto起票、16回occurrence蓄積、「後続タスクで検証すべき事項」の寄せ集め）が一度もRESOLVE/DEFERされないままBL-125のタスク遷移ゲートを塞ぎ続け、Expert/User AIがSUPERSEDEで正規のゲートを迂回し続けるという実害を確認した（この迂回がBL-152の引き金にもなった）。これはBL-136（issueが起票されても解決されない）が今も生きている実例であり、ユーザーが以前から提案していたBL-145（issueを正式タスクとして計画に組み込む）がまさにこの種の問題への解決策になる。

調査の結果、以下が判明している：
- `state["plan_revision_reason"]`（非空でtask_planner_nodeを再発火させる唯一の既存トリガー）は現在2箇所でのみセットされる：`task_plan_reviewer_node`のmajor差し戻し、`facilitator_node`のEssence Dialogue収束。issue_log側からこれをセットする経路は存在しない。
- `task_planner_node`は常に`call_task_planner`による全計画の一括LLM再生成であり、`state["phases"]`に対する部分的な差分編集APIは存在しない（BL-126 Stage Cの「supersede機構」も、LLMが返した新計画とold_phasesの`task_id`集合差分を事後的に記帳するだけの監査ブックキーピングであり、編集プリミティブそのものではない）。
- BL-144の滞留検知（`escalated_issue_first_seen_round`、同一escalated issueがユーザーノードを3回通過しても未解決）は「正当性がありかつ解消されていない」ことを示す既存シグナルとして転用できる。
- `write_issue(DEFER)`は既存task_idへの先送りしかできず、新規タスクを作る経路が無い。

**スコープ限定の決定**（ユーザー確認済み）：`state["phases"]`への軽量な差分編集API（1タスク単位の追加・削除・修正プリミティブ）は本BLでは作らない。既存の`plan_revision_reason`→`task_planner_node`全再生成という、reviewer差し戻し・Essence Dialogue収束が既に使っている経路をそのまま再利用する。差分APIは、全再生成方式が実運用で不十分と分かった場合の将来BLとして切り出す。

## グラフトポロジ検証（Plan agentによる衝突リスク解析）

`reflection_node`は`task_planner_node`へ直接のエッジを持たない（`route_after_reflection`は`halt`/`integrator`/`facilitator`/`end_turn`のみ）。したがって`reflection_node`がセットした`plan_revision_reason`は、次の外側`while`ループ反復（次Turnの`task_planner_node`起点）でのみ消費される——これは`facilitator_node`のEssence Dialogue収束が既に確立しているのと同一のターン跨ぎハンドオフであり、新規のレイテンシではない。

衝突リスクの解析（Plan agentによるグラフrouting全経路のトレース）：
- `task_plan_reviewer_node`は`plan_revision_reason`をTurn開始直後にのみセットし、即座に`task_planner`へ戻る（同一Turn内で`reflection_node`より先に消費・クリアされる）。
- `facilitator_node`のEssence Dialogue収束は`route_after_facilitator`が常に`halt`/`end_turn`のみを返す（同一Turnへループバックしない）ため、`reflection_node`が同一Turn内で`facilitator`へルーティングされるケース（`discussion_status=="stagnant"`）では、その時点で`essence_dialogue_active`は必ず`False`——つまりEssence Dialogue収束ブロック自体に到達しない。
- Turn跨ぎでも、`task_planner_node`は毎Turn冒頭で必ず実行され`plan_revision_reason`を消費・クリアするため、複数の要因が跨Turnで蓄積することもない。

**結論**：現状のグラフトポロジでは実際の衝突は起こり得ない。ただし将来のグラフ変更に対する防御として、以下2つの安価なガードを追加する（§実装方針3・5）：
1. `reflection_node`は`not state.get("plan_revision_reason")`の場合のみ新規にセットする。
2. `facilitator_node`のEssence Dialogue収束ブロックも、`plan_revision_reason`が既に非空なら上書きせず次回へ持ち越す。

## ユーザーとの設計協議で確定した変更点

当初のPlan agentの提案は「task_planner_nodeの計画再構成成功後、対象issueを直ちに`resolved`にする」だったが、ユーザーから以下の重要な訂正があった：

> 「resolvedとするのは、ちょっと語弊が生まれる可能性があるので、"計画済み"として、計画したタスクIDを関連つけるようにしたい。さらに、そのタスクに取り掛かりやはり解決しない場合、さらなる後続タスクへの延期も可能とする。ただし、容易に延期を連発するリスクはあるが、無理やり解決しようとして、差戻しループなどの議論のデットロック化も避けたい。resolvedは本当に解決した場合に状態を変える。ちなみに、issueの解決タスクは、新規ではなく既存タスク内に混ぜることも可能とする——あるタスク内で同時に考えたほうが筋が良い場合、または同時に考えなければならない場合も存在するはず」

この指摘を受け、以下の設計へ変更した：

1. **既にDEFER済みのstale issueは対象外**：`defer_to_task_id`が既に設定済みのescalated issueはBL-145のタスク化対象から除外する（`_get_forced_escalated_issues_text`が既に使っている`AND (defer_to_task_id IS NULL OR defer_to_task_id='')`フィルタを再利用）。二重の受け皿による矛盾を避ける。
2. **`resolved`にはしない。新ステータス`planned`（計画済み）を導入する**：task_plannerが計画再構成に成功しても、issueを「本当に解決した」ことにはならない——計画上のタスクに組み込まれた（=対応予定ができた）だけである。`resolved`は、実際にその内容が検証され本当に解決したと確認できたときのみ、user role経由の既存`write_issue(RESOLVE)`で人間側代理（User AI）が明示的に行う。
   - 新issue_log.status値: `'planned'`。
   - 埋め込み先のtask_id記録は既存の`defer_to_task_id`列を再利用する（BL-136のDEFERと概念的に同じ「今この issue の面倒を見ているtask_id」という意味であり、(1)の除外フィルタにより同一issueが同時にDEFER先とplanned先の両方を持つことはない。新規列は追加しない）。
   - 埋め込み先は新規タスクに限らない。task_plannerが既存タスクのdescription/acceptance_criteriaへ組み込む形でもよい（ユーザー確認済み：「同じタスク内で同時に考えたほうが筋が良い場合」を許容）。
   - **`planned`後もさらなる先送りは可能**：既存の`_write_issue_impl`のDEFER/CREATE/RESOLVEはいずれも`status != 'resolved'`を判定条件にしており、`planned`はこの条件を満たすため**コード変更なしで**既存のDEFER（別タスクへの再先送り）・CREATE経由の再発検知（`_bump_issue_occurrence`が occurrence_count>=2で機械的に`severity=major, status=escalated`へ戻す）が今まで通り機能する。つまり「そのタスクで結局解決しなかった」場合の再エスカレーション・再先送りは既存機構がそのまま面倒を見る——BL-145が追加で対応する必要はない。
   - **可視性のギャップに対する追加提案**：`planned`のまま放置されると「resolvedではないがescalatedからも消えて誰も見ない」という新しい形のBL-136問題を再生産しかねない。対策として、User AI向けに`planned`issueを非強制の「参考情報」として一覧表示する軽量ブロックを追加した（BL-136の強制解決文言とは異なり、無理に今すぐ対応させる圧力はかけない——ユーザーが懸念した「差し戻しループ等のデッドロック化」を避ける）。
3. **監査行（write_agreement）は追加しない**：既存の`make_decision`（task_planner_nodeの末尾）と`issue_log`の記録で十分と判断。
4. **再構成回数の上限は設けない**：一度`planned`になったissueは`_get_escalated_issues`（`status='escalated'`のみ抽出）から外れ、`escalated_issue_first_seen_round`の滞留追跡からも自然に外れるため、再度stale化するには別issueとして3ラウンド分の滞留が必要になり、自然に発火頻度が抑制される。

## 実装方針（実装結果）

### 1. `LineageState`への新規フィールド

`escalated_issue_first_seen_round`の直後に`plan_revision_issue_ids: list[str]`を追加。初期state辞書にも`"plan_revision_issue_ids": []`を追加。`_save_checkpoint`/`_load_checkpoint`はstate全体をそのままJSON化するため個別対応不要。

### 2. issue_logスキーマ

`status`列にCHECK制約は無いため、マイグレーション不要で`'planned'`という値をそのまま使える。`_get_escalated_issues`（`status='escalated'`のみ）・`_get_open_issues`（`status='open'`のみ）は`planned`を対象外として扱う（意図通り）。`_write_issue_impl`のCREATE/DEFER/RESOLVEはいずれも`status != 'resolved'`判定のみで`planned`を許容する（コード変更不要）。

### 3. `reflection_node`の変更

既存の`if _stale_escalated:`ブロック内、`discussion_status = "stagnant"`上書きの直後に、DEFER済み除外フィルタ・`plan_revision_reason`未使用時のみのセット・`plan_revision_issue_ids`のセットを追加。`call_reflection`（LLM呼び出し本体、`tools=None`）は無変更——完全にPython側の決定論的処理。

### 4. `task_planner_node`の変更

`revision_reason`取得の直後に`revision_issue_ids = state.get("plan_revision_issue_ids", [])`を追加。`state["plan_revision_reason"] = ""`（消費前クリア）の直後に`state["plan_revision_issue_ids"] = []`を追加。`state["phases"] = phases`の直後、`revision_issue_ids`があれば新規ヘルパー`_mark_issue_planned`を各issue_idへ呼び出す。

新規ヘルパー`_mark_issue_planned(conn, run_id, issue_id, embedded_task_ids)`（`_write_issue_impl`の近くに配置）：id基準でissue_log行を直接`UPDATE`し`status='planned', defer_to_task_id=<task_id>`とする。`_check_issue_permission`のロール表は変更しない（task_plannerはwrite_issueツール自体を持たず、この新ヘルパーはtool経由でもLLM呼び出し経由でもない）。冪等（対象行が見つからない場合はFalseを返す）。

### 5. `facilitator_node`の防御的ガード

Essence Dialogue収束ブロックの先頭に、`plan_revision_reason`が既に使用中なら上書きせず持ち越すガードを追加（§グラフトポロジ検証参照、現状は到達しないが将来の変更に対する防御）。

### 6. `generate_user_utterance`への`planned` issue可視化

新規ヘルパー`_get_planned_issues`/`_build_planned_issue_pin_text`（`_get_open_issues`/`_build_open_issue_pin_text`と同型、`status='planned'`のみ抽出）を追加し、`generate_user_utterance`へ「参考情報」として注入（BL-136の強制解決文言とは別枠、無理な即時対応は求めない）。

## テスト

新規`tests/test_bl145_issue_driven_plan_formalization.py`（16件）：
- Part A: `reflection_node`のトリガー判定（単一/複数stale issue、DEFER済み除外、既存理由の非上書き、非stale時の非発火）
- Part B: `task_planner_node`による決定論的な'planned'遷移（`resolved`にはならないこと、`plan_revision_issue_ids`のクリア、冪等性、`_mark_issue_planned`の直接ユニットテスト）
- Part C: 'planned'後もDEFER・CREATE再発検知が既存機構のまま機能すること（回帰確認）
- Part D: `facilitator_node`の衝突防御ガード
- Part E: 'planned' issueの可視化

既存のBL-096/086/126 Stage C・D/136/144/146-148関連テスト（計132件）はすべて無修正でPass。フルオフラインスイート623件Pass（実装前600件→607件[BL-151]→623件[BL-145]）。`python -m py_compile`合格。

## 検証方法

- 各変更後 `python -m py_compile cela_main.py`。
- 新規テストを個別実行、既存のBL-144/136/126 Stage C関連テストの無退行を確認。
- フルオフラインスイート `pytest tests/ -q --ignore=tests/test_f26_detection.py` を実行。
- `python scripts/check_docs_consistency.py` で最終確認。
- 実ドライランでの動作確認（issue formalizationが実際に発火し、`planned`issueが後続task内で言及されるか）は次回ドライラン待ち。
