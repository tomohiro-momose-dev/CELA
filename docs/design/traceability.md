# 要件トレーサビリティ — FEATURE_NAME

**要件が Phase・実装・検証でカバーされているか**を管理する。

| 種別 | 参照先 |
|------|--------|
| 要件マスター | [要件定義書_v35.md](要件定義書_v35.md) |
| 完了定義 | [phase_gates.md](phase_gates.md) |
| 実装タスク | [issue_backlog.md](issue_backlog.md) |

---

## タスク（要件定義より）

| タスク | Phase | 成果物 / 証跡 | 状態 |
|--------|-------|--------------|------|
| （記入） | | | ☐ |

---

## 受け入れ基準（AC）

| ID | 完了条件 | 主担当 Phase | 検証方法 | 関連 BL | 状態 |
|----|----------|-------------|---------|---------|------|
| AC-1 | （要件定義の完了条件と対応） | | | | ☐ |
| AC-2 | | | | | ☐ |
| AC-3 | | | | | ☐ |

---

## 機能要件 → Phase

| 機能 | 説明 | Phase | 設計 / 実装 | 状態 |
|------|------|-------|------------|------|
| F-1 | （記入） | | | ☐ |

---

## 検証証跡（記入用）

| 試験 ID | 内容 | 実施日 | 実施者 | 結果 | ログ / 備考 |
|---------|------|--------|--------|------|------------|
| T-1 | （例: 最小ドライラン） | | | | |
| T-2 | （例: 通し試験） | | | | |
| T-3 | R1 SQLite永続化層のスモークテスト（`get_db_connection`/`init_db`/`db_append_decision`/`db_append_agreement`/`db_supersede_agreement`/`get_*_from_db`/`_build_*_context_from_db`をダミーデータで実行し、内容一致・Superseded除外・接続クローズ後の再オープンでの残存を確認） | 2026-07-18 | Claude (実装セッション) | Pass | `python -m py_compile cela_main.py` も合格。実際のLLM API呼び出しを伴う`run_ai_vs_ai_loop`本体のE2E実行、および設計書§5.1の本番シナリオ（過疎地域バスA/Bテスト）でのドライランは未実施（BL-002参照） |
| T-4 | Record&Replayスタブ（`query_AI`のREPLAY_MODE=record/replay、call_seqキー、キャッシュミス時の例外送出）のダミークライアントによるスモークテスト | 2026-07-18 | Claude (実装セッション) | Pass | 実際のLLM応答を使ったrecord→replayの往復検証（impl_Plan §7.2の合格基準1・2）は未実施（BL-003参照） |
| T-5 | 実データA/Bドライラン（過疎地域バスシナリオ）。list版ベースライン（コミット`5ef0382`＋Record/Replayスタブ移植）をRecordモードで実行し、Turn 1〜Turn 2完了直後（Turn 3開始直後、`app.invoke()`外側）で打ち切り。同フィクスチャ（45件、`(label, call_seq)`キー）をSQLite版（コミット`2133989`）でReplay実行し、構造的一致（合格基準1、impl_Plan §7.2）を確認 | 2026-07-18 | ユーザー（実行）/ Claude（Replay実行・検証） | Pass | agreements件数15=15、decisions件数47=47、status分布（Proposed 6/Approved_with_Conditions 2/Rejected 1/Superseded 6）一致、topic登録順序（`ORDER BY id`）一致。Replayはseq=45（`User AI`、Turn 3冒頭）で想定通りのキャッシュミス例外を発生させて停止 — list版ベースラインの停止点と完全に一致し、それより前は全件再現。**30ターン完走はしていない**（[decision_log.md D-001](decision_log.md)により必須要件から除外済み）。Hydrate再現性（合格基準2）・再起動後保持（合格基準3、SQLite版側）は本試験の対象外、指標A・C（設計書§5）も未測定 — 詳細は[issue_backlog.md BL-002](issue_backlog.md)参照 |
| T-6 | R2（ツール呼び出し基盤・機械的検算ゲート）実装後のオフラインスモークテスト（実LLM API呼び出しなし）。(a) BL-001: `db_append_agreement`/`get_agreements_from_db`/`_build_agreements_context_from_db`のダミーデータDB往復で`decision_what`/`reason_why`が正しく往復し`content`/`rationale`エイリアスが復元されないことを確認。(b) `_run_python_repl`単体: 許可モジュール(math/statistics/datetime/json/fractions/decimal)の正常動作、不許可import(os等)・危険ビルトイン呼び出し(open/eval/exec/__import__)のAST拒否、`random`除外(D-007)、タイムアウト、構文エラーハンドリングを個別に確認。(c) `query_AI`ツール呼び出しループ: OpenAI SDK互換のフェイククライアント（`.chat.completions.create`をスクリプト化）により、tools=None時の非破壊、python_repl往復と最終応答返却、壊れたtool_call引数JSONの自己修復（D-009）、`MAX_TOOL_ITER=5`非収束時の`RuntimeError`伝播（D-009）、`finish_reason="length"`のツールループ内検出（D-009）の5パターンを検証。`python -m py_compile cela_main.py`および`tests/test_f26_detection.py`の`pytest --collect-only`（3件収集、import含めて成功）も合格 | 2026-07-19 | Claude（実装セッション） | Pass | いずれも実LLM API呼び出しは伴わない（コスト・時間ゼロ）。**指標D（数値矛盾検出率5/5）・指標C（収束性とコストのトレードオフ）の実測、および`tests/test_f26_detection.py`自体の実LLM実行はこのセッションでは未実施** — 課金・実行時間を伴うためユーザーの明示的な指示を待って実施する（[issue_backlog.md BL-002](issue_backlog.md)、[BL-012](issue_backlog.md)参照） |

詳細手順は `phaseN/phaseN_dryrun.md`、失敗は BL へ。

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
