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
| P1-4 | ドライラン / 試験合格 | スモークテスト・構文チェックはPass（T-3, T-4）。実データA/Bドライラン（設計書§5指標A・B・C）はBL-002として未達 | ☐ |

**Phase 1 Done = 上記すべて ☑**（P1-4未達のため現時点でPhase 1は未Close）

---

## Phase 2 — （名称・必要なら追加）

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P2-1 | （記入） | | ☐ |

---

## サインオフ

| Phase | 完了日 | 判定者 | 備考 |
|-------|--------|--------|------|
| Phase 0 | | | |
| Phase 1 | | | |
| Project Close | | | |
