# Phase Exit Criteria（完了定義）— FEATURE_NAME

各 Phase の **Done** を誰が見ても同じ判断できるように定義する。

| ドキュメント | 役割 |
|-------------|------|
| 本書 | Phase / プロジェクト全体の完了判定 |
| [phaseN/](phase0/) | 実装詳細・How |
| [issue_backlog.md](issue_backlog.md) | 残タスク（BL） |
| [要件定義.md](要件定義.md) | 要件マスター |

関連: [STATUS.md](STATUS.md) | [traceability.md](traceability.md) | [README.md](README.md)

---

## プロジェクト Close 条件

| # | 条件 | 検証方法 | 状態 |
|---|------|----------|------|
| G-1 | （記入: 受け入れ条件） | | ☐ |
| G-2 | （記入） | | ☐ |
| G-3 | [traceability.md](traceability.md) AC すべて達成 | | ☐ |
| G-4 | Phase 0〜N の Exit すべて達成 | 本書 | ☐ |

---

## Phase 0 — 方針・調査

**目的:** （記入）

| # | Exit 条件 | 状態 |
|---|-----------|------|
| P0-1 | （記入） | ☐ |
| P0-2 | 決定が [decision_log.md](decision_log.md) に記録されている | ☐ |

---

## Phase 1 — R1: SQLite永続化基盤

**目的:** 既存プロトタイプの`state["decisions"]`/`state["agreements"]`（Python list）をSQLiteへ置き換える。グラフ構造・ノード構成は変更しない。

**スコープ外:** ツール呼び出し・`write_agreement_tool`（R2/R3）、`whiteboard_drafts`書き込み（R4）

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P1-1 | 設計書が存在する | `cela_phase1_design_v7.md`, `cela_phase1_impl_Plan.md` | ☑ |
| P1-2 | 実装が設計に沿う | 照合済み（DB層・LineageState・全ノードのDB経由化・system_prompt=[]バグ修正・Replayスタブ） | ☑ |
| P1-3 | 必須 BL が `done` または合意延期 | BL-001（R2着手前判断で延期合意）、BL-004（P3のため延期） | ☑（延期合意） |
| P1-4 | ドライラン / 試験合格（R1スコープ） | スモークテスト・構文チェックはPass（T-3, T-4）。実データによる**構造的一致**（list版⇔SQLite版、agreements/decisions件数・status分布・順序）はT-5でPass、BL-003 done | ☑ |

**Phase 1 Done = 上記すべて ☑**

**注記（[D-002](decision_log.md)、2026-07-18）**: 設計書§0の対応表は§5評価メトリクス（指標A・B・C）を元々「R1〜R3共通」と分類している。実データドライラン（T-5）で、F-2.6検算ゲート（Python REPL、R2実装）が無いことに起因する差し戻しが多発することが確認されたため、指標A・B・Cの本格的な実測比較はR2実装後に行う（BL-002、`blocked`）。これはR1固有のスコープ（SQLite永続化・グラフトポロジ維持）の検証を妨げるものではなく、P1-4はR1スコープの構造的検証（上記）をもって達成とする。指標A・B・Cの実測はPhase 2（R2）以降のExit条件として引き継ぐ。

---

## Phase 2 — R2: ツール呼び出し基盤・機械的検算ゲート

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P2-1 | F-2.6機械的検算ゲート（Python REPL）実装 | `cela_phase1_design_v7.md §3.5.3` | ☐ |
| P2-2 | 評価メトリクスA（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ、最低5試行）の実測比較（[BL-002](issue_backlog.md)、[D-002](decision_log.md)） | `traceability.md` T-* | ☐ |

---

## サインオフ

| Phase | 完了日 | 判定者 | 備考 |
|-------|--------|--------|------|
| Phase 0 | | | |
| Phase 1 | | | |
| Project Close | | | |
