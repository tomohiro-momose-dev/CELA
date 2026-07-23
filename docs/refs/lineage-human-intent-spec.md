# Lineage — Human Intent 抽出 & SLM-3 Segment 仕様

> **版:** v0.2（2026-06-11）  
> **ステータス:** 要件正本（軸 B — Develop / 将来 LDW OS）  
> **関連:** [プロダクトビジョン](./lineage-product-vision.md) / [LDD README](./github_readme.md) / [Hydrate 5 節テンプレ](./hydrate-refresh-5-section-template.md)  
> **BACKLOG:** BL-057〜BL-061 / **要件:** `V12以降_要件定義.md` §10.11

**位置づけ:** 本仕様は **軸 B（意思決定・理由の監査）**。原点の **会話の調子（軸 A）** は Exchange / 直近 N 生 / Hydrate 付録 — [`lineage-product-vision.md`](./lineage-product-vision.md) §0。

---

## 1. 背景

LDD の核心: **AI 出力は再生成可能、Human intent は fragile**（`docs/github_readme.md`）。

現行 Lineage は **SLM-1/2 逐次要約**（Exchange = U* + A*）で Current / Open は強いが、次が弱い:

| ギャップ | 影響 |
|----------|------|
| ユーザーの **何を・なぜ・何を選ばなかったか** | Companion Reason Card / 監査 |
| A（提案）→ U（判断）の 1 単位 | Exchange 境界で分割 |
| 複数ターン U-A-U-A の **章立て** | 調査 vs 実装 vs 手動編集 |
| Agent 無し + WIP 増 | 「手動実装」推定不可 |
| Hydrate What/Why | **BL-066:** `要件定義.md` §1 二軸憲章（自動生成済） |

**合意方向:** 生ログは即 DB 保存（L0）。意味づけの正本は **背景 SLM-3（Segment）** に寄せ、SLM-1 は draft。

---

## 2. 3 層アーキテクチャ

| Layer | 名称 | タイミング | 役割 |
|-------|------|------------|------|
| **L0** | Raw | Hook 直後 | `raw_prompt` / `ai_raw_text` / git pin |
| **L1** | Draft | AI 保存直後 | SLM-1 Exchange 要約、SLM-2 Retention、embedding |
| **L2** | Canonical | 背景 idle | **SLM-3 Segment**、DecisionPair、thread_phase |

```text
Hook → DB (L0)
  → SLM-1/2 (L1 draft)
  → [debounce] SLM-3 (L2) → thread_segments / decision_pairs
  → Companion Reason Card ← L2 + Agent.md / Exchange 付録
  → Hydrate What/Why ← 要件定義 §1 憲章（L2 は載せない）
```

---

## 3. データモデル（案）

### 3.1 Segment（章）

```typescript
interface ThreadSegment {
  segment_id: string;
  thread_id: string;
  start_snapshot_id: string;
  end_snapshot_id: string;
  tip_snapshot_id: string;   // 生成時 tip（再現用）
  label: string;             // 例: "SLM 2段 vs 1段 tradeoff"
  segment_kind: 'inquire' | 'propose' | 'decide' | 'implement' | 'manual_edit' | 'meta' | 'pipeline_incident';
  intent?: string;           // 何を（what）
  outcome?: string;          // 結果・決定
  rejected?: string[];       // 選ばなかった案
  counterfactual?: string;   // 1 行（FR-15.2 前段）
  confidence: number;        // 0..1
  evidence: string[];        // 根拠タグ
  authority: 'proposed' | 'binding' | 'confirmed';  // confirmed = 人間承認
  valid_at_commit?: string;
  superseded_by?: string;
}
```

### 3.2 DecisionPair（提案 → 判断）

```typescript
interface DecisionPair {
  pair_id: string;
  thread_id: string;
  proposal_snapshot_id: string;  // A（authority=proposed 等）
  binding_snapshot_id: string;   // U（verbatim binding）
  chosen: string;
  rejected?: string[];
  exchange_id?: string;
}
```

### 3.3 USER intent 拡張（`user_input_json`）

```typescript
interface UserIntentFields {
  user_intent?: string;
  user_why?: string;
  user_decision?: string;
  user_rejected?: string | null;
  user_constraints?: string[];
  responds_to_snapshot_id?: string;  // A 提案への応答
}
```

### 3.4 thread メタ

```typescript
interface ThreadPhaseMeta {
  thread_phase: 'explore' | 'decide' | 'implement' | 'verify' | 'blocked';
  thread_intent_summary?: string;
  last_binding_snapshot_id?: string;
}
```

### 3.5 判断軸タクソノミ（BL-063 — 計画・未実装）

LDD 監査で読む **6 軸**（ユーザー承認 2026-06-10）。What/Why/Proof を SLM-1 の 5 大基準から分離する。

| 軸 | 答える問い | USER（BL-057 ✅） | AI（BL-063 計画） |
|----|------------|-------------------|-------------------|
| **Intent** | 何をしたいか | `user_intent` | `trigger`（探索・依頼） |
| **Question** | 未決の問い | （verbatim `raw_prompt`） | `phase=discover` + trigger |
| **Decision** | 何を選んだか（What） | `user_decision` | `decision`（新規） |
| **Reason** | なぜそうしたか（Why） | `user_why` | `reason`（新規） |
| **Evidence** | 何が証明したか（Proof） | git pin / 将来 segment | `evidence`（**実測・ログのみ**） |
| **Action** | 次に何をするか | — | `changes[]` / `pending_actions[]` |

**監査の読み順（厳守）:** `Decision` → `Reason` → `Evidence`（推測は脚注「推定」）。

**現状の違和感（課題）:** `hypothesis_decision`（COMPASS）に Decision + Reason + 却下案が混在。`evidence` に理由文が押し込まれがち。BL-063 で分離。

### 3.6 AI 判断拡張（`ai_response_summary_json` — BL-063 計画）

```typescript
interface AiJudgmentFields {
  /** What — 採用案・確定方針（1〜3 文）。proposed/binding 時は空禁止推奨 */
  decision?: string;
  /** Why — 採用理由・設計根拠。Reason 専用。hypothesis_decision から分離 */
  reason?: string;
}
```

**`hypothesis_decision` の役割変更（BL-063 後）:**

| フィールド | BL-063 後の役割 |
|------------|-----------------|
| `hypothesis_decision` | **案の比較・分析**（A案/B案・tradeoff・未確定提案） |
| `decision` | **確定した What**（採用案・方針 1 行） |
| `reason` | **確定した Why**（なぜその案か） |
| `evidence` | **Proof のみ** — smoke 行・commit sha・ログ 1 行。Reason 文は**禁止** |

**SLM-1 プロンプト（計画）:** `contextCompressor.ts` — `decision` / `reason` 追加。採用理由は `reason` へ移す。

**Hydrate 表示（計画）:** `[DECISION]` / `[REASON]` / `[EVIDENCE]` を COMPASS から分離（Refresh は Evidence 任意）。

**BL 依存:** BL-063 は BL-045 拡張。BL-059 Why 節・BL-056・BL-061 の入力。

---

## 4. SLM-3 Segment Synthesizer

### 4.1 入力（構造化タイムライン — 生全文より優先）

```text
[node_id8] U | retention=verbatim | "精度優先…"
[node_id8] A | status=ARCH_DESIGN | proposed | git wip 0→0
[node_id8] U | retention=verbatim | "Bで"  ← binding candidate
[node_id8] A | status=IMPLEMENT | git wip 0→3 (+companionPanel.ts)
--- no agent IMPLEMENT but wip_delta → manual_edit candidate ---
```

各ノード行に付与: `status`, `phase/authority`, `git_commit`, `wip_file_count`, `delta_from_parent`, `changes_count`.

### 4.2 トリガ

- `onSnapshotSaved` → debounce（既定 30s idle、設定可能）
- SLM-1 処理中は **yield**（NPU 低優先）
- 手動: Companion「系譜再分析」ボタン（将来）

### 4.3 スライディング窓

- 既定: 直近 **12 ノード** または **5 Exchange 相当**
- overlap: 前 segment 境界 ±2 ノード再スキャン
- 古い segment は **1 行要約** に圧縮して次窓へ（階層要約）

### 4.4 出力

- `segments[]` upsert（`tip_snapshot_id` 版管理）
- `decision_pairs[]` upsert
- Hook Log: `[segment] 2 segments, 1 pair [thread8]`

### 4.5 検出パターン（非網羅）

| パターン | 信号 |
|----------|------|
| 質問フェーズ | 連続 U + DEBUG_LOG / inquire |
| 提案 → 判断 | A(proposed) の次 U(verbatim) |
| 手動実装 | wip_delta && !agent changes && IMPLEMENT ノード薄 |
| パイプライン事故 | Hook `要約フォールバック` / U-U-U |
| ノイズ | omit 束 / chitchat meta |

---

## 5. 何を・なぜ — 多層マップ（正本優先順）

| 優先 | ソース | 何を | なぜ | 却下 |
|------|--------|------|------|------|
| 1 | 人間 confirm 済 segment / ADR | label / intent | outcome | rejected[] |
| 2 | DecisionPair + binding U verbatim | chosen | raw_prompt | rejected |
| 3 | SLM-3 segment (confidence≥閾値) | intent | outcome | rejected |
| 4 | Rules `Decision:` / `Reason:` / `Rejected:` 行 | Decision | Reason | Rejected |
| 5 | SLM-1 `decision` / `reason`（BL-063） | decision | reason | segment.rejected |
| 6 | SLM-1 draft trigger / compass | 要約 | 要約 | A案/B案（BL-056） |
| 7 | 推定のみ | 脚注「推定」 | — | — |

---

## 6. 会話中誘導（Rules — BL-057）

`.cursor/rules/lineage-human-intent.mdc` 参照。

- tradeoff 時 **応答末尾 1 問** + 可能なら **AskQuestion**
- 実装・BACKLOG 起票前: **2 案以上** なら選択を促す
- binding 時: `Decision:` / `Reason:` / `Rejected:` 推奨
- **設計・BL 議論時は AI も追加案を能動提示**（ユーザーが「他に提案は？」と聞かなくても 1〜3 案）

---

## 7. Hydrate 連携（BL-059 / BL-055）

Refresh 先頭 5 節:

| 節 | 主入力（BL-059 以降） |
|----|----------------------|
| **What** | 要件ヘッダ + `thread_phase` + segment 最新 intent |
| **Why** | `segment_kind=decide` + DecisionPair + rejected 表 |
| **Current** | git pin + Closed BACKLOG + segment 末尾 |
| **Open** | BacklogReader（既存） |
| **Next** | Open P1/P2 + AI_Plan_log 1 行 |

Exchange 列・Topic Index → **付録**（現行維持）。

---

## 8. Companion UX（BL-060）

- **thread_phase** バッジ（スレッド先端）
- **Segment 章** タイムライン上オーバーレイ or 折りたたみパネル
- **Decision Log** フォーム（任意）→ `user_intent` 直書き
- **confirm キュー** — SLM-3 `binding`/`decide` → 人間 1 クリックで `confirmed`

---

## 9. 監査・ゲート（BL-061 / BL-062）

### 9.1 ターン内（BL-061 — intra-thread）

- **confidence + evidence** 表示（Hydrate 脚注）
- **intent_drift** — USER verbatim vs trigger vs segment.intent（**同一スレッド内**）
- **staleness** — `valid_at_commit` 後の大 refactor
- **plan_reality_gap** — BACKLOG + AI_Plan_log vs segment 実績
- **Refresh 品質ゲート**（任意設定）— binding 無し警告
- **Hooks Plan ゲート**（任意）— `AI_Plan_log.md` 未更新なら `preToolUse` deny
- **反実仮想 1 行** — decide segment の `counterfactual`

### 9.2 エポック間 — ゴール変化（BL-062 — inter-epoch）

実装・議論の進行で **プロジェクトゴール自体** が動く（現実の壁・新要素取り込み・無意識ドリフト）。LDD の Phase/Refresh 境界が比較ポイント。

#### GoalSnapshot

```typescript
interface GoalSnapshot {
  goal_snapshot_id: string;
  thread_id: string;
  tip_snapshot_id: string;
  captured_at: string;
  source: 'refresh' | 'phase_start' | 'phase_complete' | 'manual';
  what_summary: string;           // 要件ヘッダ + thread_intent_summary
  open_backlog_ids: string[];     // BL-057, BL-058...
  open_backlog_priorities?: Record<string, string>;  // P1/P2
  ai_plan_slice?: string;         // 当該 Phase 1 行
  phase_label?: string;           // Phase 10 等
  declared_goal_line?: string;    // LDD 開始テンプレ「今回のゴール」行（verbatim）
}
```

**捕捉タイミング:** Refresh パック生成直前、`runContextPackOnMain(refresh)`、Phase 完了チェックリスト実行時、Companion 手動。

#### GoalShiftEvent

```typescript
type GoalShiftKind =
  | 'scope_expand'
  | 'scope_narrow'
  | 'priority_reorder'
  | 'architecture_pivot'
  | 'constraint_hit'
  | 'silent_drift';

interface GoalShiftEvent {
  shift_id: string;
  thread_id: string;
  from_goal_snapshot_id: string;
  to_goal_snapshot_id: string;
  shift_kind: GoalShiftKind;
  from_goal: string;
  to_goal: string;
  why?: string;
  rejected?: string[];
  binding_snapshot_id?: string;
  confidence: number;             // silent_drift は閾値未満で脚注「推定」
  evidence: string[];             // node_id8, BL diff, commit sha
}
```

#### 検知シグナル

| shift_kind | 典型シグナル |
|------------|--------------|
| scope_expand | Open BL 集合増、AI_Plan_log 新 Phase 節、segment intent 拡張 + decide |
| scope_narrow | BL Closed/延期、要件非目標明記 |
| priority_reorder | 同一 Open 集合で P1 行入替 |
| architecture_pivot | compass/rejected 質的変更、DecisionPair |
| constraint_hit | ERROR_RESOLVED → 直後 decide、smoke fail 言及 |
| silent_drift | binding 無し・Open 同じ・segment.intent 距離↑ |

#### 監査出力

- Hydrate **What** 末尾: `### Goal evolution`（直近 1〜3 shift、confidence 脚注）
- Companion: Refresh / Phase 境界にエポック縦線 + shift ツールチップ
- Hook Log: `[goal-shift] scope_expand BL-057+058 [thread8]`

---

## 10. 既存 BL との関係

| BL | 関係 |
|----|------|
| BL-045 | Exchange / SLM-1/2 基盤。L1 draft として維持 |
| BL-055 | 5 節合成。**Why/What は BL-059（Segment 入力）が本命** |
| BL-056 | compass 却下案。**DecisionPair / segment.rejected と統合** |
| BL-063 | **AI `reason` / `decision` 分離** — COMPASS/evidence 混在解消。SLM-1 + Hydrate + 監査チェーン |
| BL-046 | binding Why の durable 層（ADR） |
| BL-054 | Exchange UI。**Segment 章と併存** |
| BL-062 | **Goal Shift 監査**。BL-058 segment 比較 + Refresh エポック。**intent_drift（BL-061）と分離** |

---

## 11. 実装フェーズ

| Phase | BL | 内容 |
|-------|-----|------|
| P0 | BL-057 | Rules + Decision 形式 + USER intent 型 |
| P1 | BL-058 | DecisionPair ヒューリスティック + git 差分行 + manual_edit ルール |
| P1 | BL-058 | SLM-3 MVP + DB + smoke |
| P2 | BL-059 | Hydrate 5 節 ← segments |
| P2 | BL-063 | AI `decision`/`reason` + SLM-1 プロンプト + Hydrate `[REASON]` |
| P2 | BL-060 | Companion segment / Decision Log / confirm |
| P2 | BL-062 | GoalSnapshot 捕捉 + GoalShiftEvent + Hydrate Goal evolution |
| P3 | BL-061 | intra-thread 監査・ゲート・Hooks 任意 |

---

## 12. 未決（起票時メモ）

- SLM-1 を draft のみに弱めるか
- segment 保存: 新テーブル vs `globalStorage` JSON
- 窓サイズ・debounce 既定値（F5 + 計測）
- binding の human confirm 必須か任意か
- `sanitizeSummaryChanges` と対象名 path の整合（技術負債）
- GoalSnapshot 保存: 新テーブル `goal_snapshots` vs JSON blob
- silent_drift の confidence 閾値（F5 + 監査サンプル）
- BL-063: 既存ノードの `hypothesis_decision` → `decision`/`reason` バックフィル要否
- BL-063: `evidence` に Reason が混入した履歴のクリーンアップ方針（再要約 vs 脚注のみ）

---

## 13. 参照

- `docs/architecture-pipeline-tags.md`
- `docs/hydrate-refresh-5-section-template.md`
- `src/ExchangeBuilder.ts` — 現行 U*+A*
- `src/ContextPipeline.ts` — SLM-1/2
- `V12以降_要件定義.md` — FR-10.25〜FR-10.34
- `docs/Linage-driven-development-operations.md` — Phase/Refresh エポック運用
