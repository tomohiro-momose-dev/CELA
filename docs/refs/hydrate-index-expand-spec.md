# Hydrate 索引化 + lineage-expand CLI 仕様

> **版:** v0.3（2026-06-11）  
> **ステータス:** 要件正本（実装前）  
> **BACKLOG:** BL-064  
> **関連:** [Refresh 5 節テンプレ](./hydrate-refresh-5-section-template.md) / [Human Intent 仕様](./lineage-human-intent-spec.md) / [パイプラインアーキテクチャ](./architecture-pipeline-tags.md)

---

## 1. 背景・課題

Refresh 用 `hydrateContext.md` は Exchange 全文を同梱するため **tok が膨らむ**（例: 100+ exchanges で ~13k 級）。一方、次チャットの実用目的は **現 Phase / Open BL の継続** が多く、直近ターン + タスク台帳で足りる場面が多い。

**Cursor 等ネイティブ履歴との関係:** Cursor は同一チャット内の履歴圧縮を持つ。Lineage が **二重に全文リプレイ** する必要はない。Refresh は **新 Agent チャットへのブートストラップ** が本筋（`agent-transcripts` の代替ではない）。

**マルチ IDE（ユーザー承認 2026-06-11）:** VS Code + GitHub Copilot 等では Hook / 履歴 API が異なり、動作は未検証。**それでも中身は LDD 用に設計**する。展開の正本は Lineage DB（`context_saver.db`）。Cursor `agent-transcripts` や Copilot ネイティブ履歴に依存しない。

---

## 2. 方針（ユーザー承認 2026-06-11）

| 採用 | 却下 |
|------|------|
| **3 段グラデーション** — Zone A 生 / Zone B Exchange 可読 / Zone C 豊かな索引（§4.2） | 2 帯のみ（生 + 索引） |
| **N=10 / M=30 標準** — `recentFullTextCount` / `exchangeReadableCount` | 固定全文同梱 |
| **M の自動調整** — `packMaxEstTokens` + Footprint で Zone B を縮小 | M 固定で 18k 超過 |
| **Node CLI** `lineage-expand` — DB から id で展開 | Python / ユーザー手動実行 |
| **Agent が能動的に expand**（Rules + hydrate ヘッダ指示） | 毎ターン全祖先を hydrate に載せる |
| **Zone C は豊かな索引** — phase / status / 1 行サマリ必須 | id のみリスト |
| **デバッグ用に現行 Exchange 可読全文を残す**（§4.3） | 索引化で現行出力を完全削除 |
| **LDD 構造化ビュー**（判断・git pin・BL） | Cursor `agent-transcripts` の置き換え |

---

## 3. 役割分担

```text
【同一チャット中】
  エージェント環境の履歴 … 会話継続の主役
  Lineage Hook … DB 蓄積・git pin・Companion（サイドカー）

【Refresh → 新チャット】
  hydrate … 5節 + Open + Topic + Zone A/B/C 付録（§4.2）
  Agent … @hydrate 読込後、必要時のみ lineage-expand

【深掘り】
  lineage-expand … Lineage DB（要約 JSON・USER raw・ai_raw_text）
  agent-transcripts … 最後の手段の生ログ（BL-005 寄り・既定では使わない）
```

---

## 4. Hydrate パック構成（Refresh 既定・BL-064 後）

| 層 | 内容 | 既存/新規 |
|----|------|----------|
| ヘッダ | lineage メタ、`exchange_tiers`、effective M | 既存 + **新規** |
| 5 節 | What / Why / Current / Open / Next（BL-055） | 計画 |
| BACKLOG Open | `BacklogReader` | 既存 |
| Topic Index | `npu:` 対応表 | 既存 |
| **Zone A〜C** | tip から遡る **3 段グラデーション**（§4.2） | **新規** |
| ヘッダ指示 | Agent は必要時 `npm run lineage:expand` を実行 | **新規** |

**トークン目安:** 全文 100+ exchanges → 3 段 + M 自動調整で Refresh 注入を **おおよそ 50–75% 削減**（深掘り expand は別ターン）。

### 4.1 ターンの定義

**1 ターン = 1 snapshot ノード**（USER / AI）。既存 `fullTextNodeIds` / `recentFullTextCount` と同じ単位。Exchange 帯の判定は、Exchange の **先端 assistant ノード** が tip から何番目かで決める。

### 4.2 3 段グラデーション（本番 Refresh 既定）

tip から遡るノード位置で 3 帯に分ける（**ユーザー承認 2026-06-11**）:

```text
tip ──────────────────────────────→ 古い

|←── Zone A: 直近 N ──→|←── Zone B: N+1 〜 M ──→|← Zone C: M+1 〜 ─→|

  生（全文）              Exchange 可読              豊かな索引 1 行
```

| 帯 | 範囲（tip から） | 出力形式 | 既定 |
|----|------------------|----------|------|
| **Zone A** | 直近 **N** ターン | USER raw + `[AI raw]` / `[full-text]` | **N = 10**（`recentFullTextCount`） |
| **Zone B** | **N+1 〜 M** ターン | `### Exchange …` + COMPASS / TRIGGER / CHANGES / EVIDENCE（**`ai_raw` なし**） | **M = 30**（`exchangeReadableCount` 上限） |
| **Zone C** | **M+1** 以降 | 豊かな索引 1 行（§6。id のみ禁止） | 残り全 Exchange |

**Zone B の意味:** 現行 `HydrationManager` の「非 fullText」表示を Exchange ブロック単位で維持。中間帯の「何が起きたか」が残り、expand 頻度を下げる。

**ピン例外:** `ARCH_DESIGN` / `verbatim` USER / DecisionPair proposal+binding は **最低 Zone B** に昇格（索引のみに落とさない）。`packMaxEstTokens` 逼迫時も Zone A を最後まで守る。

### 4.3 M の自動調整（`packMaxEstTokens` + Footprint）

**標準 M = 30** だが、注入上限に合わせて **実効 M（`effectiveReadableCount`）** を自動縮小する。

| 設定キー | 既定 | 役割 |
|----------|------|------|
| `recentFullTextCount` | **10** | N（Zone A 生。固定） |
| `exchangeReadableCount` | **30** | M の**上限**（Zone B の最古端） |
| `packMaxEstTokens` | **18_000** | 注入 tok 上限（既存） |

**調整アルゴリズム（実装指針）:**

1. 選別済み Exchange に対し、3 段で `est_tokens` を概算（`ContextFootprint` / `estimateExchangePackTokens` 再利用）
2. `est_tokens > packMaxEstTokens` のとき **M を N+1 方向に段階縮小**（Zone B を削る。Zone C 索引は維持）
3. それでも超過なら **Zone C の最古索引行から削除**（既存 `HydrateSelection` の Exchange ドロップと同順）
4. **Zone A（N=10）は既定で削らない**
5. ヘッダに `exchange_tiers: raw=10 readable={M_eff} index=older` を記録
6. **Companion Footprint Bar** に `M_eff` / 18k 使用率を表示（注入プレビューと ±5% 一致は BL-028 既存要件）

**手動上書き:** 設定で `exchangeReadableCount` を下げれば M 上限そのものを変更可能。自動調整は `min(設定 M, tok から逆算した M_eff)`。

### 4.4 デバッグモード — Exchange 可読全文（現行仕様を維持）

BL-064 は **本番 Refresh** を 3 段グラデーションにするが、**現行の全 Exchange 可読ブロック出力はデバッグ用として残す**。

| モード | 設定 / 経路 | Exchange 付録 |
|--------|-------------|---------------|
| **gradient**（本番既定） | Refresh → `hydrateContext.md` | Zone A/B/C（§4.2） |
| **full_readable**（デバッグ） | 下記トリガー | **選別済み全 Exchange** を現行どおり可読（全ノード `ai_raw` 含む） |

**`full_readable` のトリガー:**

1. **Companion デバッグ出力** — `DEBUG_EXPORT_HYDRATE` → `hydrateContext.debug.<preset>.md`
2. **設定** — `exchangeAppendixMode`: `gradient` | `full_readable`（F5 比較用）
3. **`full` プリセット** — `hydrateContext.debug.full.md`（全祖先可読）

**ヘッダ:** 本番 `exchange_appendix_mode: gradient`。デバッグは `full_readable`。

**やらないこと:** デバッグモードを Refresh 本番の既定にしない。

---

## 5. 設定（package.json 案）

```json
"npuContextSaver.hydration": {
  "recentFullTextCount": 10,
  "exchangeReadableCount": 30,
  "packMaxEstTokens": 18000,
  "exchangeAppendixMode": "gradient"
}
```

---

## 6. 索引行フォーマット（Zone C・豊かな索引・必須）

id のみは禁止。最低限:

```text
| ex{id8} | {phase}/{authority}/{status} | nodes: {A_id8},{U_id8} | {1行サマリ} |
```

**サマリ優先順:**

1. `user_decision` / binding USER 先頭 40 字
2. AI `decision` / `reason`（BL-063 後）
3. `hypothesis_decision` 先頭 80 字
4. `trigger` 先頭 60 字

**ピン留め:** `ARCH_DESIGN` / `verbatim` USER / DecisionPair proposal+binding は索引でも `*` マーク（Zone B 昇格または expand 推奨）。

---

## 7. lineage-expand CLI（Node）

### 7.1 コマンド

```bash
npm run lineage:expand -- --ids <id8|uuid,...> [--format exchange|node] [--thread <uuid>]
npm run lineage:expand -- --recent <N> [--thread <uuid>]
```

- 正本: `globalStorage` の `context_saver.db`（既存 `DatabaseManager`）
- 出力: stdout（Exchange ブロック形式は `HydrationManager` と同型）
- **ユーザー手動実行は不要** — Agent がターミナルで能動実行

### 7.2 Agent 実行タイミング（Rules 案）

- Zone C 索引のみで binding / decide の根拠が不足
- ユーザーが過去判断の根拠を質問
- 5節 Why に「詳細は node xxx」とある

---

## 8. 実装スライス（BL-064）

| # | 内容 | 主なファイル |
|---|------|-------------|
| 1 | 設定 + 型 | `snapshot.ts`, `package.json` — `exchangeReadableCount`, `exchangeAppendixMode: gradient` |
| 2 | 3 段 tier 判定 | 新規 `src/HydrateExchangeTier.ts` または `HydrateExchangeIndex.ts` |
| 3 | M 自動調整 | `HydrateSelection.ts`, `ContextFootprint.ts` — `effectiveReadableCount` |
| 4 | HydrationManager 3 段出力 | `HydrationManager.ts` — Zone A/B/C 分岐 |
| 5 | 索引行ビルダ | `HydrateExchangeIndex.ts` — Zone C |
| 6 | デバッグ経路 | `extension.ts` — `DEBUG_EXPORT_HYDRATE` は常に `full_readable` |
| 7 | expand CLI | `scripts/lineage-expand.js`, `package.json` `lineage:expand` |
| 8 | hydrate ヘッダ + Footprint | `exchange_tiers` / `M_eff` 表示 |
| 9 | Rules | `.cursor/rules/` — 必要時 expand |
| 10 | smoke | `scripts/lineage-expand-smoke.js` |

**BL-055 との関係:** 5 節が先頭、Exchange は付録。BL-064 は付録を 3 段化。並行または BL-055 直後。

**見送り:** `agent-transcripts` からの expand（BL-005 延期と同様）

---

## 9. 検証

1. `npm run compile` + `smoke:lineage-expand`
2. 本番 Refresh: Zone A=10 生、Zone B≤30 Exchange 可読、Zone C=豊かな索引（`exchange_appendix_mode: gradient`）
3. 長スレッド: `est_tokens > packMaxEstTokens` 時に `M_eff < 30` となりヘッダに反映
4. Footprint / 注入プレビューが `M_eff` と `est_tokens` を表示
5. デバッグ: `hydrateContext.debug.refresh.md` は `full_readable`（現行全文）
6. Agent が `lineage:expand --ids ...` で Zone C から COMPASS/USER raw が復元

---

## 10. 未決

- 索引対象: 選別済み全 Exchange vs RAG ヒットのみ
- `side_hydrate` / `shadow_hydrate` も 3 段化するか
- Copilot 向け Rules の配布形（`.cursor/rules` 以外）

---

## 11. 参照

- `src/types/snapshot.ts` — `fullTextNodeIds`
- `src/HydrateSelection.ts` — `packMaxEstTokens` ドロップ
- `src/ContextFootprint.ts` — Footprint Bar
- `package.json` — `recentFullTextCount` / `exchangeReadableCount` / `exchangeAppendixMode`
- `src/extension.ts` — `DEBUG_EXPORT_HYDRATE`
- `src/HydrationManager.ts` — `## Exchanges` ブロック生成
