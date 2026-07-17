# 要件トレーサビリティ — FEATURE_NAME

**要件が Phase・実装・検証でカバーされているか**を管理する。

| 種別 | 参照先 |
|------|--------|
| 要件マスター | [要件定義.md](要件定義.md) |
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

詳細手順は `phaseN/phaseN_dryrun.md`、失敗は BL へ。

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
