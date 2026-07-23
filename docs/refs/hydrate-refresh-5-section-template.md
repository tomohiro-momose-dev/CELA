# Refresh 用 Hydrate — 5 セクション テンプレート

> **版:** v1.2（2026-06-11）  
> **ステータス:** **仕様・手書きテンプレ**（自動生成 **BL-055**、What/Why 正本 **BL-066** / `要件定義.md` §1.3）  
> **根拠:** 第三者レビュー（ChatGPT × 要件定義）— LDD は「会話」ではなく **判断の系譜** を継承する  
> **関連:** [プロダクトビジョン](./lineage-product-vision.md) / [ピッチ 1 枚](./pitch-lineage-one-pager.md) / [LDD 運用](./Linage-driven-development-operations.md) / [Human Intent 仕様](./lineage-human-intent-spec.md)

---

## 0. なぜ 5 セクションか

| 従来の Hydrate | 理想形（Refresh） |
|----------------|-------------------|
| 選別祖先 + Exchange 列（時系列ログ寄り） | **What / Why / Current / Open / Next** の判断サマリー |
| 全文に近いノードが混ざると tok 膨張 | 5 節が正しければ **数万 tok の先祖があっても再構築精度が高い** |
| 「何をしたか」は残りやすい | **「なぜそうしたか」「捨てた案」** が弱くなりがち（既知ギャップ） |

**Refresh プリセット** は Code Bundle なし・本線継続が前提。開発用途では全文ログより **判断の系譜** の方が価値が高い。

---

## 1. セクション定義

| 節 | 英名 | 答える問い | 主な情報源（自動化時） |
|----|------|------------|------------------------|
| **What** | What | このアプリは何のための製品か | `要件定義.md` §1 — 製品一言・LDD・Phase・**軸 A/B 各 1 行**（`readProductCharter`） |
| **Why** | Why | なぜこのプロダクトを作るか | `要件定義.md` §1.1–1.2 **軸 A/B 目的要約**（ハルシネーション補完禁止） |
| **Current** | Current | 今どこまで来ているか | `as_of_commit`、直近 Closed（BACKLOG）、バージョン、smoke 状況 |
| **Open** | Open | 未解決・未着手は何か | `BACKLOG.md` `## Open`（**信頼境界・単一ソース**） |
| **NEXT_RECOMMENDATION** | — | **次に 1 本何をやるか + なぜ** | `AI_Plan_log.md` 正本（BL-055 同梱）。Open とは別 |
| **Next** | Next | 次に何をするか（補助） | Open の P1/P2 先頭 + 任意スライス 1 行 |

**信頼境界（厳守）**

- **Open** の真実は `BACKLOG.md` のみ。`AI_Implement_log.md` の `pending_actions` は歴史。
- **What/Why** は **プロダクト憲章**（チャット継続 + 意思決定監査の二軸）。セッション判断・却下案は **Companion Reason Card** / 付録 B（L2 Segment は Hydrate 先頭に載せない）。
- **Goal evolution（BL-062 以降）:** 直近 1〜3 件の `GoalShiftEvent`。`silent_drift` は脚注「推定」。詳細は `docs/lineage-human-intent-spec.md` §9.2。
- 詳細 Exchange 列は **付録**（5 節の下）。5 節だけ読めば再開できる構成にする。
- **BL-064 以降（本番 `gradient`）:** 付録は **3 段** — Zone A 生（N=10）/ Zone B Exchange 可読（M≤30、tok で自動調整）/ Zone C 豊かな索引。深掘りは `lineage:expand`。
- **デバッグ:** 現行 Exchange 可読全文は `full_readable`（`hydrateContext.debug.*.md` / Companion デバッグ出力）。

---

## 2. 空テンプレート（コピー用）

```markdown
# Lineage — Hydrated Context (Refresh)

> pack_preset: refresh | Tip: {snapshot_id8} | as_of_commit: {sha12} | dirty: {bool}
> est_tokens: ~{n} | exchanges_selected: {n} / ancestors_total: {n}

---

## What — 何を作っているか

- **製品:** Lineage（VS Code/Cursor 拡張）— AI 協働の **判断の系譜** をローカル保存し Hydrate で次スレッドへ注入
- **方法論:** LDD（Lineage-Driven Development）
- **現フェーズ / スコープ:** Phase {N} — {1行でスコープ}
- **軸 A — チャット継続:** {非対称圧縮・RAG・Hydrate 同期 1 行}
- **軸 B — 判断の系譜:** {意思決定・理由・却下案の系譜保存 1 行}
- **今回のチャットの役割:** 本線 Refresh 継続 / 脇道調査 / （該当を1つ）

---

## Why — なぜこのプロダクトを作るか

- **軸 A — チャット継続:** {§1.2 軸 A 目的 1 行}
- **軸 B — 意思決定監査:** {§1.2 軸 B 目的 1 行}

> セッション判断・却下案の詳細は Companion Reason Card / 付録 B を参照。

---

## Current — 現在地

- **バージョン:** v{X.Y.Z}
- **Git:** `{sha12}` @ `{branch}` (dirty: {yes|no})
- **直近完了（BACKLOG Closed 先頭）:**
  - BL-xxx: {1行}
- **スモーク / F5:** {PASS 一覧 or 残り手動項目}
- **既知ギャップ:** {1〜3 行}

---

## NEXT_RECOMMENDATION

> 単一推奨。正本: `AI_Plan_log.md` §NEXT_RECOMMENDATION。仕様: `docs/hydrate-next-recommendation-spec.md`

**BL-058** — SLM-3 Segment Synthesizer MVP

**WHY:**
- DecisionPair は in-memory のみ（BL-057 完了）
- Segment 正本（L2）未構築
- BL-059 / BL-060 / BL-062 が BL-058 依存

**BLOCKED_BY:** なし

**ALT:** BL-064（並行可）/ BL-063（並行可）

**VERIFY:** `smoke:segment-synthesizer` + F5 idle debounce

**CONTEXT:** Phase 10 — Human Intent / SLM-3

---

## Open — 未解決課題

> タスクの真実はこの節のみ。AI_Implement_log.md の pending は無視。

| ID | Pri | Task |
|----|-----|------|
| {BACKLOG Open テーブルをそのまま} |

---

## Next — 次にやること

1. **P1:** BL-xxx — {1行}
2. **P2:** BL-xxx — {1行}
3. **人間チェック:** {F5 手動・リリースタグ等}

---

## 付録 A — Topic Index（コンパクト）

| Node | Status | Topic |
|------|--------|-------|

## 付録 B — Exchanges（選別・oldest → newest）

（現行 `hydrateContext.md` の Exchange 列。5 節だけで足りないときの参照用）
```

---

## 3. 記入例（Lineage 本リポジトリ・2026-06-08 時点）

手動 Refresh 前の **参照用サンプル**。コミット SHA・Open は生成時点で更新すること。

```markdown
# Lineage — Hydrated Context (Refresh)

> pack_preset: refresh | Tip: 92f9c833 | as_of_commit: 61b3db778bca | dirty: false
> est_tokens: ~12500 | exchanges_selected: 144 / ancestors_total: 330

---

## What — 何を作っているか

- **製品:** Lineage — エージェント時代の「判断の系譜」OS（Git がコード系譜なら、Lineage は判断系譜）
- **方法論:** LDD — 人間が注入境界を設計し、BACKLOG に真実を固定、チャットは短期記憶
- **現フェーズ:** Phase 10 Lineage v1.0 — Exchange 要約 v2・リブランド・ADR/Freeze・5 節 Hydrate 仕様化
- **今回のチャット:** 本線 Refresh。第三者レビュー（判断継承・Lens Cross）を仕様に落とし込み中

---

## Why — なぜそうしたか

### 確定した方針
- **Hydrate はログではなく判断サマリー** — Refresh 先頭に What/Why/Current/Open/Next（本ドキュメント）。実装は BL-055
- **BACKLOG が Agent 向け実行キューの正本** — Linear 等は人間向け。BL-049 で provider アダプター
- **Code Bundle からメタ文書を除外** — `AI_Implement_log.md` 全文混入は denylist + `changes∩diff` で遮断（2026-06-08 修正）
- **要約 v2 は Exchange 単位** — USER+AI 束で `phase/work_kind/authority`。BL-045 が技術芯

### 検討して却下した案
| 案 | 却下理由 | 根拠 |
|----|----------|------|
| Hydrate に Agent.md 全文を同梱 | tok 膨張・二重管理。Topic Index + ワークスペース参照で十分 | ノード 5ad07252 議論 |
| 固定 regex のみで status 判定 | 文脈判断は LLM が適する。例題 few-shot + フォールバック | v0.12.0 / BL-029 |
| Linear を BACKLOG 代替にする | Issue は「何を」まで。Agent の注入境界・却下案はモデル外 | ノード 4125344e |

### まだ議論が開いている論点
- **捨てた案の自動保存** — 現行要約だけでは A 案却下理由が落ちる。Lens Cross（FR-14.3）・反実仮想（FR-15.2）で補完予定

---

## Current — 現在地

- **バージョン:** v0.12.0（package.json）
- **Git:** `61b3db77` @ main (dirty: false)
- **直近完了:** BL-029 Topic Index + LLM status、BL-043 NPU/FLM、BL-037 日常 Refresh、BL-045 Exchange 要約 v2（smoke PASS・F5 一部残）
- **スモーク:** hydrate-selection / topic-index / footprint PASS
- **既知ギャップ:** Why 節の自動品質、却下案の構造化、github-copilot DB 未接続

---

## Open — 未解決課題

（`BACKLOG.md` `## Open` を生成時に同梱 — 手書き時はそちらを正とする）

---

## Next — 次にやること

1. **P1:** BL-045 — F5 汚染スレッド目視・Exchange Hydrate 品質確認
2. **P1:** BL-044 — Lineage リブランド（表示名・README・設定キー方針）
3. **P2:** BL-055 — 本テンプレの Refresh 先頭自動合成（`HydrationManager`）
4. **P2:** BL-056 — Why 強化（却下案を `hypothesis_decision` 必須化 + decide Exchange 優先ピン）

---

## 付録

Topic Index・Exchange 列は現行 `hydrateContext.md` 生成ロジックに委譲（BL-055 で 5 節の下に付録）。**BL-064:** 3 段グラデーション（§4.2）。`docs/hydrate-index-expand-spec.md` v0.3。
```

---

## 4. 自動生成へのマッピング（BL-055 実装指針）

| 節 | 生成ロジック案 |
|----|----------------|
| What | `readProductHeader()` — 要件定義から固定 5 行 + `threads.startup_mode` |
| Why | `buildWhySection(exchanges)` — `phase=decide` / `authority=binding` / `status=ARCH_DESIGN` を時系列マージ。却下案は `hypothesis_decision` 内 `A案/B案/却下` パターン抽出 |
| Current | tip git pin + `readBacklogClosedHead(3)` + `package.json` version |
| NEXT_RECOMMENDATION | `NextRecommendationReader` ← `AI_Plan_log.md` 正本（**BL-055**） |
| Open | 既存 `BacklogReader` |
| Next | Open Pri 先頭 2 件（補助。本命は NEXT_RECOMMENDATION） |
| 付録 | Topic Index + **Zone A/B/C**（N=10 生 / M≤30 可読 / 豊かな索引）（BL-064）。expand は `lineage:expand` |

**Refresh のみ** 5 節を先頭に挿入。`side_hydrate` / `shadow_hydrate` は Open + 短い What のみでも可。

---

## 5. 限界と将来（忘れないためのメモ）

| 弱点 | 対策（ロードマップ） |
|------|----------------------|
| Exchange 全文で tok 膨張 | **BL-064** 3 段グラデーション + M 自動調整 + `lineage-expand` |
| 却下案が要約で落ちる | BL-056 + FR-15.2 反実仮想 |
| 別 AI・別時期の直交視点 | FR-14.3 Lens Cross |
| 次スレッドで「何からやるか」迷う | **NEXT_RECOMMENDATION**（`AI_Plan_log.md` 正本 → BL-055 同梱） |
| Why の主観的圧縮 | BL-046 ADR 自動出力（binding 判断を Markdown 固定） |
| チーム可視化 | BL-049 Linear / BL-052 PR 連携 |

---

## 6. 参照

- `要件定義.md` — Phase 7 Refresh・Phase 10
- `V12以降_要件定義.md` — FR-14.3 Lens Cross、FR-15.2 反実仮想
- `docs/hydrate-next-recommendation-spec.md` — NEXT_RECOMMENDATION 仕様
- `AI_Plan_log.md` — 生きた正本
- `src/HydrationManager.ts` — 現行 `packHydrationMarkdown`
- `src/prompts/contextCompressor.ts` — `hypothesis_decision` 却下案指示（v4.5+）
