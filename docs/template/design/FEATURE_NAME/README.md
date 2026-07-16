# FEATURE_NAME — ドキュメント索引

> このファイルは機能ドキュメントの **索引** と **Source of Truth 定義** です。  
> 新規プロジェクトでは `FEATURE_NAME` を実機能名にリネームしてください。

---

## ドキュメントの役割（運用モデル）

本プロジェクトは **ハイブリッド型（docs 正）** で管理する。

| レイヤ | 置き場 | 役割 |
|--------|--------|------|
| **要件の出発点・作業用マスター** | [要件定義.md](要件定義.md) | 背景・タスク・完了条件・調査結果。**設計フェーズの正** |
| **詳細設計・実装仕様** | `phase0/` `phase1/` … | Phase ごとの How・制約・テスト観点 |
| **未決・実装タスク** | [issue_backlog.md](issue_backlog.md) | BL-xxx（バグ、未実装、未確定） |
| **意思決定** | [decision_log.md](decision_log.md) | **決定理由必須**（Why。BL の「何を直すか」とは分離） |
| **進捗・完了判定** | [STATUS.md](STATUS.md) / [phase_gates.md](phase_gates.md) / [traceability.md](traceability.md) | 今どこか、いつ Done か、要件カバレッジ |
| **展開** | [rollout_plan.md](rollout_plan.md) | 本番導入（不要なら削除） |
| **任意: エピック入口** | GitHub Issue（短文） | 外部向け要約 + 本 README へのリンクのみ |

```mermaid
flowchart TB
    REQ[要件定義.md<br/>出発点・マスター]
    PHASE[phaseN 設計書]
    BL[issue_backlog.md]
    DL[decision_log.md]
    GH[GitHub Issue<br/>任意・要約のみ]
    REQ --> PHASE
    PHASE --> BL
    REQ --> DL
    BL --> STATUS[STATUS.md]
    REQ --> TRACE[traceability.md]
    GH -.->|リンクのみ| REQ
```

**要点:** 要件の詳細詰めはリポジトリ内 `docs/` で行う。GitHub Issue に全詳細を書き溜めしない。Issue は後付けでもよい。

---

## まず読むもの

| 優先 | ファイル | 用途 |
|------|---------|------|
| 1 | **[STATUS.md](STATUS.md)** | 今のフェーズ・ブロッカー・次アクション |
| 2 | **[要件定義.md](要件定義.md)** | 要件マスター |
| 3 | **[issue_backlog.md](issue_backlog.md)** | 実装タスク・未確定（BL-xxx） |
| 4 | **[phase_gates.md](phase_gates.md)** | Phase / プロジェクト完了の定義 |

---

## ドキュメントの正（Source of Truth）

| 種別 | 正 | 補足 |
|------|-----|------|
| 要件・受け入れ条件 | **本ディレクトリ**（特に `要件定義.md`） | Issue は要約のみ |
| エージェントとの要件詰め | `要件定義.md` | ここを更新 |
| 実装タスク・バグ | `issue_backlog.md` | レビュー指摘も BL |
| 意思決定 | `decision_log.md` | 決定後に関連 BL を `done` へ |
| 進捗サマリー | `STATUS.md` | マイルストーン時に更新 |
| Phase 完了判定 | `phase_gates.md` | |
| 要件カバレッジ・試験要約 | `traceability.md` | T-* |
| 展開 | `rollout_plan.md` | 任意 |

---

## 外部トラッカー（GitHub Issue 等）との同期

設計フェーズでは **ローカル `docs/` が先行** する。毎保存の自動同期は行わない。

| タイミング | 操作 |
|-----------|------|
| 要件・仕様を詰める | `要件定義.md` および該当 `phase*/` を更新。決定は `decision_log.md` |
| 実装タスクが出た | `issue_backlog.md` に BL 起票 |
| Phase 完了・要件凍結 | 任意で Issue 本文サマリーを更新 |
| プロジェクト Close | `phase_gates.md` と `traceability.md` の受け入れ条件達成後 |

**Issue に書く内容（推奨）:** 背景（数行）、完了条件（箇条書き）、本 README へのリンク。  
**Issue に書かない内容:** Phase 詳細、プロトコル全文、バックログ、レビュー全文。

**過去コメント:** 全面編集しない。方針変更は新規コメントまたは先頭注記のみ。

---

## 実装フェーズ（記入例）

| Phase | 内容 | 状態 | ドキュメント |
|-------|------|------|-------------|
| Phase 0 | 方針・調査 | （記入） | [phase0/](phase0/) |
| Phase 1 | （記入） | （記入） | [phase1/](phase1/) |
| Phase 2 | （記入） | （記入） | （予定） |

---

## 試験メモの置き場

| 内容 | 置き場 |
|------|--------|
| PASS/FAIL 要約 | [traceability.md](traceability.md) T-* |
| 失敗・次に直すこと | [issue_backlog.md](issue_backlog.md) BL-* |
| 手順・環境の詳細 | `phaseN/phaseN_dryrun.md` |
| 生ログ | プロジェクトで決めたログディレクトリ |

---

## 関連コード（記入）

| 種別 | パス |
|------|------|
| （主要実装） | （記入） |
