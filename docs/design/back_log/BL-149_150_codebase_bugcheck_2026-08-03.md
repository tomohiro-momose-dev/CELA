# コードベース全体バグチェック結果 — 2026-08-03

> **実施日**: 2026-08-03
> **実施者**: Cline (deepseek/deepseek-v4-flash)
> **対象**: `cela_main.py`（8000+行、145関数）、`docs/`、`log/2026-08-02/2222`
> **新規BL**: BL-149（`_safe_json_parse`ロギング不足）、BL-150（高複雑度関数のリファクタリング候補）

---

## 1. 概要

CELA（Lineage-driven AI協調システム）のコードベース全体を、Codebase Memory MCP・ドキュメント群（STATUS.md, issue_backlog.md）・直近の動作ログ（08-02/2222）を含めて精査した。

**健全性**: プロジェクトは極めて徹底したissue管理（BL-001〜BL-150）を行っており、発見されたバグのほとんどが既に追跡・対応済み。オフラインテストスイート596件Pass、`python -m py_compile`合格の状態を維持している。

**主要リスク**: 実LLM再ドライランでの効果確認が多数のBL項目で「次回待ち」のまま蓄積しており、実環境での検証がボトルネックになっている。

---

## 2. 情報保存・伝播経路のバグ

### 2.1 最重要の未対応項目（情報伝播のギャップ）

| BL | 重要度 | 内容 | 影響 | 修正難易度 |
|-----|--------|------|------|-----------|
| BL-123 | P1 | `_build_escalation_pin_text`が`call_detector`に注入されていない | Detectorが他ロール既知のescalated issueを知らず、同じ差し戻しを繰り返す | **1行追加** |
| BL-124 | P1 | BL-086のescalation系ツール（freeze/revise_goal等）が実運用で一度も呼ばれない | 前提矛盾に直面しても通常のwrite_agreementで済ませ、stagnant→HALTに至る | プロンプト誘導強化 |
| BL-121 | P1 | halt後も処理継続の原因が未確定（BL-132部分修正済み） | 強制停止が効かない可能性 | 次回ドライランで再確認 |
| BL-133 | P1 | DetectorドメインレビューのJSONパース失敗がフェイルクローズmajor化 | 非退行テストが3/3失敗、真因未診断 | 次回再現時に300字プレビューで診断 |
| BL-041 | P1 | `global_constraints`への集約が実装されたがarbiter発火条件未設計 | Resource Arbiterが実質発火しない | 設計判断待ち |
| BL-065 | P2 | R5永続化情報（internal_thought_process/goal_shift_events）の消費経路が未設計 | 書き込みのみで読み返されない | 設計要 |

### 2.2 新規発見（本チェックで追加）

#### BL-149: `_safe_json_parse`のフォールバック戦略ロギング不足（P3）

`_safe_json_parse`（complexity=16, cognitive=37, 68行）は複数のフォールバック戦略（フェンスブロック抽出・`{`/`[`優先順位判定・末尾補完等）を順に試す設計だが、どの戦略で成功・失敗したかがログ出力されない。BL-133で`_query_and_parse_with_retry`に300字プレビューを追加したが、`_safe_json_parse`自体の成功/失敗時の戦略ログは未追加。BL-088（`{`/`[`優先順位バグ）やBL-089（複数フェンスブロック混線）の類問題が再発した際、原因切り分けが困難。

#### BL-150: 高複雑度関数のリファクタリング候補（P3）

Codebase Memory MCPの複雑度メトリクスより、以下の関数がコードベース全体で最も複雑:

| 関数 | complexity | cognitive | loops | 行数 | 備考 |
|------|-----------|-----------|-------|------|------|
| `decision_extractor_node` | 26 | 91 | 5 | 202 | 抽出ロジック（User/Expert分岐）・遷移解決・DB書き込みの3責務を1関数で抱える |
| `_commit_agreement_from_tool` | 26 | 78 | 2 | 159 | CREATE/UPDATE/SUPERSEDE × Decision/Directive/Deliverable/EssenceProposalの全組合せ |
| `call_detector` | 18 | 21 | 0 | 493 | 2パス（ドメイン妥当性+数値監査）構成だが全体として長大 |

BL-098/BL-118（ファイル分割）と関連するが、ファイル分割前に個別関数の責務分割・サブ関数抽出を先行すべき。

---

## 3. 各ノードの役割と情報伝播の確認

### 3.1 グラフトポロジ（28ノード/ルーティング関数）

```
goal_essence → task_planner → task_plan_reviewer → generate_user_utterance
  → user_detector → (major) → generate_user_utterance (差し戻し)
  → (none/minor) → orchestrator → expert → expert_detector
  → (major) → expert (差し戻し)
  → (none/minor) → expert_decision_extractor → route_after_expert_decision
  → (round_count % reflection_interval == 0) → reflection → facilitator → ...
  → (otherwise) → generate_user_utterance (次ラウンド)
```

### 3.2 情報伝播の確認ポイント

| 経路 | 状態 | 備考 |
|------|------|------|
| `state["goal"]` → 9消費者 | ✅ 正常 | `generate_user_utterance_node`の1箇所で書き換え→全消費者に自動伝播 |
| `expert_wrote_agreement` → `decision_extractor_node` | ✅ 修正済み(BL-038) | LineageState TypedDict宣言漏れが原因、D-038で修正 |
| `_LAST_PYTHON_CALLS` → `detector_node` | ✅ 修正済み(BL-045) | 即時反映に修正、APIエラー時の記録消失を解消 |
| `last_reflection_note` → `call_facilitator` | ✅ 修正済み(BL-061) | デッドパラメータを実際の引数に置換 |
| escalated issue → `call_expert`/`generate_user_utterance` | ✅ 正常(BL-103) | `_build_escalation_pin_text`でpin注入 |
| **escalated issue → `call_detector`** | **❌ 未配線(BL-123)** | **最重要の情報伝播ギャップ** |
| `round_count` → reflection/facilitator発火 | ✅ 修正済み(BL-048) | `turn_count`凍結(BL-005)を`round_count`で迂回 |
| `current_task_id` → `_get_current_task` | ✅ 修正済み(BL-139) | Directive抽出からのフォールバック追加 |
| `current_task_id` → `write_agreement`ゲート | ✅ 修正済み(BL-146) | current_task_id以外への書き込みを拒否 |
| `current_task_id` → `read_deliverable_file`ゲート | ✅ 修正済み(BL-147) | 存在しないtask_idでの読み込みを拒否 |
| Orchestrator → `current_task_id`/計画参照 | ✅ 修正済み(BL-148) | ツールループ化＋読み取り専用4ツール付与 |

### 3.3 死んだコード・未使用要素

| 要素 | 状態 | BL |
|------|------|-----|
| `chat_history`/`current_goal`テーブル | INSERT/SELECT一件もなし | BL-067 (open) |
| `current_task_summary` | Hydrate 3段構想の未実装残骸 | BL-068 (open) |
| `global_constraints`集約 | 実装されたがarbiter発火条件未設計 | BL-041 (partial) |
| `internal_thought_process`列 | 書き込みのみで読み返されない | BL-065 (open) |
| `goal_shift_events`テーブル | 書き込みのみで読み返されない | BL-065 (open) |
| `whiteboard_drafts.author_role`/`edit_summary` | 保存されるが読み出されない | BL-066 (open) |

---

## 4. コード精制度・複雑度

### 4.1 複雑度メトリクス上位（Codebase Memory MCPより）

| 関数 | complexity | cognitive | loops | loop_depth | 行数 | 備考 |
|------|-----------|-----------|-------|-----------|------|------|
| `decision_extractor_node` | 26 | 91 | 5 | 2 | 202 | 最複雑。3責務を1関数で抱える |
| `_commit_agreement_from_tool` | 26 | 78 | 2 | 1 | 159 | CREATE/UPDATE/SUPERSEDE全組合せ |
| `build_graph` | 20 | 22 | 0 | 0 | 295 | グラフ構築、条件付きエッジ多数 |
| `call_detector` | 18 | 21 | 0 | 0 | 493 | 2パス構成だが全体として長大 |
| `_write_agreement_impl` | 18 | 25 | 2 | 1 | 109 | バリデーション→権限→コミット→確定値反映 |
| `_safe_json_parse` | 16 | 37 | 0 | 0 | 68 | 複数フォールバック戦略 |
| `call_reflection` | 4 | 4 | 2 | 1 | 167 | タイムライン構築ループ |

### 4.2 ホットスポット（fan-in上位）

| 関数 | fan_in | 役割 |
|------|--------|------|
| `get_active_conn` | 28 | DB接続管理（全ノードが依存） |
| `make_decision` / `db_append_decision` | 17 | Decision作成・DB書き込み |
| `_reset_think_scratchpad` | 13 | thinkツール状態リセット |
| `_get_goal_essence_text` | 11 | Goal Essence取得（全ノード注入） |
| `get_agreements_from_db` | 10 | Agreement取得 |
| `get_latest_whiteboard` | 8 | ホワイトボード取得 |
| `query_AI` | 8 | AI呼び出し集約点 |
| `_query_and_parse_with_retry` | 6 | 層2リトライ付きクエリ |
| `_safe_json_parse` | 5 | JSONパース |

### 4.3 例外タプルの推移（ネットワーク層の堅牢性）

| BL | 例外クラス | 状態 |
|-----|-----------|------|
| BL-022 | `json.JSONDecodeError` | done |
| BL-059 | `httpx.RemoteProtocolError` | done |
| BL-072 | `httpx.TimeoutException` | done |
| BL-083 | `httpx.ReadError` | done |
| — | `httpx.ConnectError`/`WriteError`/`PoolError` | BL-072で`TimeoutException`親クラス経由でカバー済み |

---

## 5. 改善提案・気づき

### 5.1 即効性のある改善

1. **BL-123の修正（1行）**: `call_detector`に`_build_escalation_pin_text`を注入するだけで、Detectorの誤差し戻しループが大幅に減少する可能性が高い。`call_expert`（`:6086`）と`generate_user_utterance`（`:4700`）の2箇所で既に呼ばれているのと同じパターンを`call_detector`（`:4767`〜）に追加するだけ。

2. **BL-133の診断**: 次回ドライランで`_query_and_parse_with_retry`の300字プレビューログからJSONパース失敗の真因（モデルがJSONを一切出力していないのか、ツールループがMAX_TOOL_ITERまで消費されたのか、API側の一時的不調か）を特定できる。

### 5.2 設計改善の方向性

3. **ファイル分割（BL-098/118）**: 8000行の単一ファイルを永続化層/ツール層/ノード層/ログ層に分割する前に、BL-150で特定した高複雑度関数の責務分割を先行すべき。`decision_extractor_node`は抽出ロジック・遷移解決・DB書き込みの3責務に分割可能。`_commit_agreement_from_tool`はaction_type×entry_typeのマトリックスをサブ関数へ分離可能。

4. **issue管理の実効性向上**: BL-136でDEFER/強制解決文言を追加したが、実際のRESOLVE/DEFER呼び出し率は依然低い。BL-145（issue→正式タスク化）の設計と、`state["phases"]`への軽量差分API（1タスク追加・削除・修正）の実装が必要。

5. **`_safe_json_parse`のロギング強化（BL-149）**: フォールバック戦略の成功/失敗をログ出力することで、BL-088/BL-089類問題の再発時に原因切り分けが容易になる。

### 5.3 アーキテクチャレベルの気づき

6. **実LLM検証のボトルネック**: 150個のBL項目のうち、多くが「実LLM再ドライランでの効果確認は次回待ち」の状態。オフラインテスト596件Passは堅牢だが、実環境での検証が蓄積している未検証項目の解消に不可続。

7. **モデル依存性**: DeepSeek系とNVIDIA Nemotron 3 Ultraで明らかに挙動が異なる（BL-122/BL-124で確認）。Nemotronはより視座の高い対応（前提の疑問視・エスカレーション判断）が可能だが、リトライ頻度も増加。プロンプト設計が特定モデルに最適化されすぎないよう注意が必要。

8. **キャッシュヒット率**: BL-104〜111の改善で45%まで回復したが、損益分岐点（約74%）には未達。BL-108のプロンプトサイズ増加（約3倍）とのトレードオフの実$コスト評価が必要。

9. **08-02/2222ログの分析**: 19個のホワイトボードバージョン（V1-V19）は、task_1_1が改訂ループに入っていたことを示唆。BL-142（承認撤回ガイダンス）とBL-143（差し戻し状況ラベル）の実装後だが、実効果の確認は次回ドライラン待ち。ログはOpenRouter無料枠の日次上限到達＋Ctrl+Cで終了しており、クラッシュではない。

10. **再帰的自己改変のリスク（BL-138）**: AIが捏造・確定値化した数字が後続議論に連鎖的影響（バタフライ効果）を与える現象は既にBL-134等で実例観測済み。将来のアーキテクチャ自己改変着手時には「改変ループの外側に固定監査層」が必要という設計原則をBL-138として記録済み。

---

## 6. 結論

CELAのコードベースは、150個のBL項目による徹底的なバグ追跡と修正の歴史を持ち、オフラインテスト596件Passを維持する堅牢な状態である。主要な情報伝播経路のバグ（BL-038/045/061/139/146/147/148等）は既に修正済み。

**最も重要な未対応項目はBL-123（Detectorへのescalation pin未注入）**である。これは1行の追加で修正可能であり、Detectorの誤差し戻しループを大幅に減少させる効果が期待できる。

本チェックで新規発見したBL-149（`_safe_json_parse`ロギング不足）とBL-150（高複雑度関数のリファクタリング候補）は、いずれもP3（改善・削除候補）として`issue_backlog.md`に追加済みである。

---

## 付録: チェック対象一覧

| 対象 | 方法 | 結果 |
|------|------|------|
| Codebase Memory MCP `list_projects` | プロジェクト発見 | C-ai_work-CELA (2432 nodes, 4569 edges) |
| Codebase Memory MCP `get_architecture` | アーキテクチャ概要 | 145 functions, 28 routing functions |
| Codebase Memory MCP `search_graph` | 関数一覧・複雑度 | BL-149/150の特定 |
| `docs/design/STATUS.md` | プロジェクト状態 | Phase 5/R5実装完了、実LLM検証待ち |
| `docs/design/back_log/issue_backlog.md` | BL項目一覧 | BL-001〜BL-150（150項目） |
| `log/2026-08-02/2222/log_no_prompt.md` | 直近ログ | 19ホワイトボード版、API上限到達で終了 |
| `log/2026-08-02/2222/checkpoint.json` | チェックポイント | 最終状態確認 |
| `search_files` (routing/node functions) | グラフ構造 | 28ノード/ルーティング関数確認 |
| `search_files` (`_build_escalation_pin_text`) | BL-123確認 | `call_detector`への未配線を確認 |