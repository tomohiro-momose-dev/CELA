# Lineage — プロダクトビジョン（3 段ラダー）

> **版:** v0.1（2026-06-11）  
> **ステータス:** 戦略正本（実装前の一部含む）  
> **関連:** [`要件定義.md`](../要件定義.md) §1 / [`pitch-lineage-one-pager.md`](./pitch-lineage-one-pager.md) / [`lineage-human-intent-spec.md`](./lineage-human-intent-spec.md)

---

## 0. 真の出発点 —「会話の調子」を引き継ぎたい

### 痛み（タスク継続ではない）

チャットを切り替える理由（ハルシネーション・tok 爆発）は **合理的** だが、人間が嫌がるのは **認知コスト** である。

| 状態 | 体験 |
|------|------|
| **仕上がったスレッド** | 相手が自分の考え・困りごとを理解している。議論の **調子（tuning）** がある |
| **新しいスレッド** | 初めましての議論相手。要約を貼っても **直前までの調子に戻りにくい** |

ダッシュボードや BACKLOG だけ渡すと **次に何をするか** は戻るが、**どう一緒に考えていたか** は戻らない。

### カーネマン的フレーミング

人は **System 2 を自ら働かせず**、AI 提案を **System 1 で心地よく受け取りたい**（認知コスト最小化）。

しかし採用の瞬間は頭の中に閉じ、後から次の問いが来る:

- どう解釈したか
- 何を採用したか
- **なぜそう判断したか**

**人の頭に内包されると、あとから取れない。** だから OS が肩代わりする層が必要になる（軸 B）。

### なぜ Exchange / 直近 N ターン生に拘るか

Hydrate 憲章（What/Why）や Current/Open は **Where** には効く。  
**調子** に効くのは:

- 直近 N ターンの **生ログ**（言い回し・揺れ・未確定の空気）
- **Exchange** 可読列（U/A のリズム）
- Segment の **章 intent**（調べごと・探索の途中）

→ 付録 B / Zone A は tok を食っても残す設計判断（BL-042 / BL-064）。

---

## 1. 歴史 — なぜ Cursor から始めたか

```text
Gemini 等ブラウザチャット（調べごと・アイディア）
  → ハルシネ / tok → 新チャット → 再教育 → 調子が戻らない（原点）
  → ブラウザ DOM フックはアップデートで不安定
  → まず Cursor（IDE）で Hook + Hydrate を実証
  → 継承物が開発情報に収束（git・Agent・BACKLOG）
  → memory.md 型 handoff への収束（Zenn 的エージェント運用）
  → 副次的仮説: 意思決定・理由の監査の方が差別化になる（LDD / 軸 B）
  → 2026-06: 二軸（憲章）+ 三プロダクトラダーへ整理
```

---

## 2. 三プロダクトラダー（上から見た別軸）

**本リポジトリは中段。上段・下段は別軸のプロダクト（コア共有）。**

```text
┌─────────────────────────────────────────────────────────────┐
│  LDW / LDM OS（将来）                                         │
│  Lineage-Driven Work / Management                            │
│  「普段の仕事で AI と話すならここ」— チャット入り口 + API 中継   │
│  横断メモ・採用検知・系譜検索・ゴール移動監査                    │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────┐
│  Lineage for Develop（本 repo・現在）                          │
│  VS Code / Cursor 拡張 — 監査（軸 B）+ Hydrate 部品（軸 A）      │
└────────────────────────────┬────────────────────────────────┘
                             │
┌────────────────────────────┴────────────────────────────────┐
│  Lineage for AI Chat（原点・次の水平展開）                      │
│  汎用 Web チャット — Self-Healing フック + lineage-core        │
│  第一候補: Gemini Web（Chrome 拡張）                           │
└─────────────────────────────────────────────────────────────┘
```

| プロダクト | 主戦場 | フック | 軸 A 効き | 軸 B 効き |
|-----------|--------|--------|-----------|-----------|
| **Lineage for AI Chat** | 調べごと・日常 AI 対話 | Chrome + Self-Healing DOM | **高**（周辺文脈が薄い） | 中（採用メモ MVP から） |
| **Lineage for Develop** | エージェント開発 | Cursor `state.vscdb` 等 | 中（開発文脈豊富） | **高**（git・ADR・Segment） |
| **LDW OS** | 全業務 AI 協働 | 自前 UI（API で各社 LLM） | 高 | 高 |

**LDD ≠ Spark 的タスク振り分け。** 「どの AI に投げるか」より **どう話し・どう決め・どう覚え・どう引き継ぐか**。

---

## 3. LDW OS 内の三層（上段の内部）

```text
LDW OS
  ├─ 協働層: チャット + エージェント監査（採用検知・Reason・グラフ検索）
  └─ 引き継ぎ層: Hydrate（調子・文脈）— OS 内の一機能
```

能動 UX（将来）例:

```text
[LDD] AI の B 案を採用したように見えます。
      後で説明できますか？ メモ → [________]
      [あとで] [メモする]

後日: グラフの decide タグ / キーワード検索 → Exchange + 紐づけメモ
```

現状: Companion Reason Card + Decision Log（BL-060/066）が **受動的 MVP**。能動ポップアップは BL-061 以降。

---

## 4. Lineage for AI Chat — 概要

> **設計正本:** [`lineage-for-ai-chat-architecture.md`](./lineage-for-ai-chat-architecture.md)（話題単位 Zone・話題ピッカー・chat profile 一式）

### 要点（ビジョン要約）

- **Self-Healing DOM フック** — Gemini Web 等のセレクタ破壊をローカル SLM で修復。
- **Hydrate は develop より軽量** — status pin / RAG / 憲章なし。**話題（Chapter）ごと Zone A/B/C** + **引き継ぎ話題選択**。
- **非対称圧縮 + Exchange** — USER 生（近傍）/ AI 圧縮は lineage-core 共有。
- **出力** — `handoffContext.md`（会話マップ + 章別引き継ぎ）。

### 実装フェーズ（要約）

| Phase | 内容 |
|-------|------|
| G0–G1 | Chrome フック + Self-Healing |
| G2–G3 | L0 + Chapter SLM + `ChatHydrateBuilder` |
| G3.5–G4 | 話題ピッカー + tok 予算 |
| G5 | 軽量採用メモ（軸 B 任意） |

詳細・スキーマ・受け入れ基準は **正本** を参照。

---

## 5. Develop スライス内の二軸（本 repo）

[`要件定義.md`](../要件定義.md) §1.0 参照。ビジョン文書の **三プロダクト** とはスケールが異なる。

| 軸 | Develop での意味 |
|----|------------------|
| **A チャット継続** | Refresh・Exchange・Zone A |
| **B 意思決定監査** | Segment・DecisionPair・Reason Card |

Hydrate 先頭 What/Why = **プロダクト憲章**（§1.3）。調子は **付録**。

---

## 6. 戦略 — アダプタ量産 vs 入り口 OS

| 方針 | 評価 |
|------|------|
| Copilot / 各ブラウザ用アプリ量産 | フック不安定・メモ/系譜がバラバラ |
| **LDW OS がチャット入り口** + API 中継 | フック一箇所・LDD 一貫。**長期本命** |
| **Lineage for AI Chat（Chrome）** | OS 以前の **ブリッジ**。原点の痛みに直撃 |

---

## 7. ドキュメント対応表

| 文書 | 役割 |
|------|------|
| 本文書 | 3 段ラダー・原点・Self-Healing 要約 |
| [`lineage-for-ai-chat-architecture.md`](./lineage-for-ai-chat-architecture.md) | **AI Chat 設計正本**（Chapter Zone・handoff） |
| `要件定義.md` §1 | Develop 向け二軸・Hydrate 憲章 |
| `pitch-lineage-one-pager.md` | 3 分ピッチ |
| `github_readme.md` | GitHub 公開用英語 README 草案 |
| `lineage-human-intent-spec.md` | 軸 B データモデル |

---

## 8. 一言

> **Lineage は会話を保存するのではなく、次の会話を stranger にしない。**  
> **タスクだけでなく、議論の調子と、あとから説明できる自分を残す。**
