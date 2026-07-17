# 実装 Backlog — FEATURE_NAME

**実装タスク・バグ・未確定の実装事項**（BL-xxx）を管理する。要件定義の正ではない。

| 種別 | 正しい参照先 |
|------|-------------|
| 要件・背景・完了条件 | [要件定義.md](要件定義.md) |
| Phase 詳細設計 | [phase0/](phase0/) [phase1/](phase1/) |
| 意思決定（なぜ） | [decision_log.md](decision_log.md) |
| 索引 | [README.md](README.md) |

---

## 凡例

| 状態 | 意味 |
|------|------|
| `open` | 未着手・未確定 |
| `blocked` | 他タスク完了待ち |
| `done` | 確定・完了 |

| 優先度 | 意味 |
|--------|------|
| P0 | 次マイルストーン前に必須（動作破綻） |
| P1 | Phase 完了前に対応 |
| P2 | 後続 Phase で確定 |
| P3 | 改善・削除候補 |

---

## 優先対応一覧（記入）

| ID | 重要度 | 対象 | 概要 | 優先度 |
|----|--------|------|------|--------|
| BL-001 | 中 | `cela_main.py` (Agreement TypedDict) | `content`/`rationale`を`decision_what`/`reason_why`にリネームし、R1ラッパーのマッピングを除去 | P1 |
| BL-002 | 高 | `cela_main.py` (R1全体) | R1完了条件（評価メトリクスA・B・C、設計書§5）の実データによるA/Bドライラン未実施 | P0 |
| BL-003 | 中 | `cela_main.py` (Record&Replayスタブ) | 実LLM応答を使ったrecord→replay往復検証（impl_Plan §7.2合格基準1・2）未実施 | P1 |
| BL-004 | 低 | `cela_main.py` (死んだimport) | `from secrets import choice`、`from unittest import result` の未使用import除去 | P3 |

---

## Backlog 一覧

### BL-001: Agreement TypedDictの`content`/`rationale`リネーム

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P1 |
| 依存 | R1完了 |
| 関連 | [cela_phase1_impl_Plan.md §2.3, §9](phase1/cela_phase1_impl_Plan.md) |

**内容:**

R1では「壊さない」優先で、既存の`Agreement` TypedDict（`content`/`rationale`キー）をそのまま維持し、`db_append_agreement`内でSQLite列名（`decision_what`/`reason_why`）へマッピングするラッパー方式を採用した（`get_agreements_from_db`も逆方向にエイリアスを付与）。この二重変換は将来のツール化（R3の`write_agreement_tool`）でスキーマ不一致の温床になりうる。

**完了条件:**

- `Agreement` TypedDictのキーを`decision_what`/`reason_why`に統一する（呼び出し側コードも追従）。
- `db_append_agreement`/`get_agreements_from_db`のcontent/rationaleエイリアス変換コードを除去する。
- 実施判断はR2着手前に行う（impl_Plan §9準拠）。

---

### BL-002: R1完了条件の実データA/Bドライラン未実施

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P0 |
| 依存 | なし |
| 関連 | [cela_phase1_design_v7.md §5, §5.1](phase1/cela_phase1_design_v7.md) |

**内容:**

今回のR1実装セッションでは、`get_db_connection`/`init_db`/`db_append_*`/`get_*_from_db`/`_build_*_context_from_db`/`build_graph()`のダミーデータによるスモークテストと`python -m py_compile`による構文検証のみを実施した。設計書§5の評価メトリクスA（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ）は、実際のLLM API呼び出しを伴う`run_ai_vs_ai_loop`本体のE2E実行（過疎地域バスシナリオ）が必要であり、未実施。

**完了条件:**

- `phase1/phase1_dryrun.md`を新規作成し、手順化する。
- 変更前（list版）と変更後（SQLite版）を同一タスクで実行し、指標A・B・Cを比較する。
- 結果を`traceability.md`のT-*に記録する。

---

### BL-003: Record&Replayスタブの実LLM応答による往復検証未実施

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P1 |
| 依存 | BL-002 |
| 関連 | [cela_phase1_impl_Plan.md §7](phase1/cela_phase1_impl_Plan.md) |

**内容:**

`query_AI`のREPLAY_MODE（record/replay/off）・call_seqキー機構・キャッシュミス時の例外送出は、ダミークライアントによるスモークテストのみ実施済み。実際のLLM応答を使い、list版ベースラインの実行結果と、SQLite版をreplay実行した結果を比較する回帰確認（impl_Plan §7.2の合格基準1「構造的一致」・2「Hydrate再現性」）は未実施。

**完了条件:**

- list版ベースライン実行 → recordモード実行 → SQLite版実装への切替 → replayモード実行、の手順で構造的一致を確認する。
- 結果を`traceability.md`のT-*に記録する。

---

### BL-004: 死んだimportの除去

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [cela_phase1_design_v7.md §6](phase1/cela_phase1_design_v7.md) |

**内容:**

`cela_main.py`冒頭の`from secrets import choice`、`from unittest import result`は機能に影響しない未使用importだが、`result`変数のシャドーイングリスクがある。設計書§6の方針に従い、R1では無関係な清掃として混在させず、BL起票のみに留めた。

**完了条件:**

- 該当2行を削除し、`result`のシャドーイングが実際に発生しないことを確認する。

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
