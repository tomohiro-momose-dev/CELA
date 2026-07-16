# ドキュメント／エージェント運用テンプレート

このディレクトリは、**新しいプロジェクトの出発点**としてコピーする一般化ひな型です。

本リポジトリ（SW-921H MAC 機能）で使っている「ハイブリッド型 docs 正」モデルを一般化し、**GitHub Issue ではなく `要件定義.md` を要件の出発点**にしています。

---

## 使い方（新規プロジェクト）

1. 本ディレクトリ全体を新リポジトリへコピーする（または必要なファイルだけ）。
2. ルートの [`AGENTS.md`](AGENTS.md) をプロジェクトルートへ配置する（パス中の `FEATURE_NAME` を実名に置換）。
3. `design/FEATURE_NAME/` を `docs/design/<実機能名>/` にリネームする。
4. [`design/FEATURE_NAME/要件定義.md`](design/FEATURE_NAME/要件定義.md) から背景・タスク・完了条件を書き始める。
5. エージェントには「まず `docs/design/<機能>/README.md` と `STATUS.md` を読め」と指示する。

任意: GitHub Issue は後からエピック入口として短く作ってよい（docs へのリンクのみ）。**詳細の正は常に docs。**

---

## 含まれるもの

| パス | 役割 |
|------|------|
| [`AGENTS.md`](AGENTS.md) | エージェント常時適用ルール（コピー先: リポジトリルート） |
| [`design/FEATURE_NAME/README.md`](design/FEATURE_NAME/README.md) | 機能ドキュメントの索引・Source of Truth |
| [`design/FEATURE_NAME/要件定義.md`](design/FEATURE_NAME/要件定義.md) | **要件の出発点・作業用マスター** |
| `STATUS.md` / `phase_gates.md` / `traceability.md` | 進捗・完了定義・試験証跡 |
| `decision_log.md` / `issue_backlog.md` | Why / 実装タスク(BL) |
| `rollout_plan.md` | 展開計画（不要なら削除可） |
| `phase0/` `phase1/` | Phase 設計の置き場 |
| [`refs/README.md`](refs/README.md) | ニッチ言語公式リファレンスのキャッシュ置き場 |

---

## 核心ルール（要約）

1. **詳細の正は `docs/`** — Issue / チャットに詳細を溜めない  
2. **レイヤを混ぜない** — 要件 / 決定(Why) / BL / 進捗を分離  
3. **エージェントは索引を先に読む** — STATUS → 要件定義 → backlog → gates  
4. **決定には理由必須**  
5. **ニッチ言語は公式リファレンスをキャッシュしてから実装**  
6. **試験メモは T-* / BL / dryrun に分担**

詳細は各ファイルおよび [`AGENTS.md`](AGENTS.md) の Documentation Model を参照。
