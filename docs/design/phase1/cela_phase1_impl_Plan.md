# R1（SQLite永続化基盤）実装計画

> **作成日**: 2026-07-18
> **対象**: 既存プロトタイプ `cela_main.py` への R1 フェーズ適用
> **参照**: 要件定義書 v35 付録B.3、ロードマップ v25 R1、Phase1〜R3設計書 v7 §2, §3.6, §6

---

## 0. 目的・基本方針

既存プロトタイプ `cela_main.py` の状態管理（Python list 上の `decisions`/`agreements`）を、変更を最小限に留めたまま SQLite へ置き換える。ノード構成・グラフ構造（LangGraph）は一切変更しない。既存の動作検証済みロジックを壊さないことが最優先。

---

## 1. 実行ポリシー

- 各実行で新しい `run_id`（タイムスタンプ＋短縮UUID）を発行し、同一 run_id のスコープ内のみで読み書きする。
- 前回実行のデータは `cela.db` ファイルに残るが、現在セッションからは不可視（全クエリ `WHERE run_id=?`）。
- **「消さない・引き継がない（run_id で分離）」**。
- **R1 はレジューム機構を含まない。run_id は毎回新規発行。前回実行データの読み出し・継続実行は行わない。**
- 完了条件B（後述）は「kill 後も同一 run_id の行が DB ファイルに残存していること」のみで検証する。

---

## 2. スキーマ（Step 1）

### 2.1 接続初期化

```python
def get_db_connection(db_path: str = "cela.db") -> sqlite3.Connection:
    conn = sqlite3.connect(db_path, timeout=60.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn
```

- `isolation_level=None`（自動コミット）。append ごと即時永続化。完了条件Bを構造的に保証。
- WAL + synchronous=NORMAL + timeout=60（F-13準拠）。

### 2.2 テーブル定義（`init_db(conn)`）

```sql
-- decisions: 既存 Decision TypedDict 対応。internal_thought_process は R5 で書き込み（NULL許容）
CREATE TABLE IF NOT EXISTS decisions (
    id TEXT, timestamp REAL, who TEXT, what TEXT, why TEXT,
    reason_missing INTEGER DEFAULT 0, internal_thought_process TEXT,
    run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id);

-- agreements: 設計書4.2準拠。R1は「壊さない」優先で decision_what/reason_why は DEFAULT ''（NOT NULL 回避）
CREATE TABLE IF NOT EXISTS agreements (
    id TEXT, turn INTEGER, action_type TEXT, status TEXT, topic TEXT,
    decision_what TEXT DEFAULT '', reason_why TEXT DEFAULT '',
    proposed_by TEXT, entry_type TEXT, phase_id TEXT,
    abstraction_level TEXT, scope TEXT, time_axis TEXT,
    depends_on TEXT, resource_claims TEXT, timestamp REAL,
    evidence TEXT, is_frozen INTEGER DEFAULT 0, internal_thought_process TEXT,
    run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_agreements_run_topic ON agreements(run_id, topic);
CREATE INDEX IF NOT EXISTS idx_agreements_run_status ON agreements(run_id, status);

-- whiteboard_drafts: R4 で書き込み。R1 は定義のみ
CREATE TABLE IF NOT EXISTS whiteboard_drafts (
    draft_id TEXT, phase_id TEXT, task_id TEXT, version INTEGER,
    content TEXT, author_role TEXT, edit_summary TEXT, timestamp REAL, run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_wb_run ON whiteboard_drafts(run_id, phase_id, task_id);

-- chat_history: R1 は list 維持。R1 は定義のみ
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT, turn INTEGER, role TEXT, content TEXT, timestamp REAL, run_id TEXT NOT NULL
);

-- current_goal: run_id なし・跨実行で引き継ぐ単一レコード。R1 は定義のみ（書き込み/読み出し未実装）
CREATE TABLE IF NOT EXISTS current_goal (
    goal_id TEXT PRIMARY KEY, core_philosophy TEXT NOT NULL, absolute_constraints TEXT, updated_at REAL
);
```

### 2.3 列名の設計判断

- 物理列は設計書DDL準拠の `decision_what` / `reason_why` を採用。
- 既存 `Agreement` TypedDict の `content` / `rationale` はラッパー `db_append_agreement` 内でマッピング（`a["content"]` → `decision_what`、`a["rationale"]` → `reason_why`）。
- `decision_what` / `reason_why` は **`TEXT DEFAULT ''`**（NOT NULL 回避）。既存で `content`/`rationale` が欠ける dict が流れてくるリスクを避けるため。厳格な NOT NULL 制約の強化は R3 の TypedDict リネーム時にまとめて実施。
- `issue_backlog.md` に BL 起票：「`Agreement` TypedDict の `content`/`rationale` を `decision_what`/`reason_why` にリネームし、R1ラッパーのマッピングを除去する」。**実施判断は R2 着手前**に行う。

---

## 3. 接続管理

- Connection は **module-level のシングルトン**（`_DB_CONN` グローバル変数）で管理。`state` には `db_conn` を入れない（`sqlite3.Connection` はシリアライズ不可・`check_same_thread=True` の既定を持ち、将来の LangGraph checkpointer / R11 フォーク実行で破綻するため）。
- `LineageState` には **`run_id: str` と `db_path: str` のみ**を保持。
- `run_ai_vs_ai_loop` 冒頭で `_DB_CONN = get_db_connection(db_path)` を初期化、ループ終了時に `try/finally` で `_DB_CONN.close()`。
- 各ノード内は `conn = get_active_conn()`（シングルトンを返す関数）で取得。state を経由しないためシリアライズ問題なし。

---

## 4. 書き込みラッパーとキー削除

### 4.1 LineageState の変更

- `LineageState` TypedDict から `"decisions": list[Decision]` と `"agreements": list[Agreement]` の2行を**意図的に削除**。
  - **理由**: DB化し忘れた参照漏れを `KeyError` で機械的に検出し、静かな乖離（空 list でたまたま動いてしまう）を防ぐため。
- 代わりに `"run_id": str` と `"db_path": str` を追加。
- `chat_history` は R1 では list 維持のためキーは残す。

### 4.2 ラッパー関数

```python
def db_append_decision(d: dict, conn, run_id: str):
    conn.execute(
        "INSERT INTO decisions (id, timestamp, who, what, why, reason_missing, internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?)",
        (d.get("id"), d.get("timestamp"), d.get("who"), d.get("what"), d.get("why"),
         1 if d.get("reason_missing") else 0, d.get("internal_thought_process"), run_id)
    )

def db_append_agreement(a: dict, conn, run_id: str):
    # content/rationale → decision_what/reason_why にマッピング
    depends_on_val = json.dumps(a.get("depends_on", []), ensure_ascii=False) if isinstance(a.get("depends_on"), (list, dict)) else (a.get("depends_on") or "[]")
    resource_claims_val = json.dumps(a.get("resource_claims", {}), ensure_ascii=False) if isinstance(a.get("resource_claims"), (list, dict)) else (a.get("resource_claims") or "{}")
    conn.execute(
        "INSERT INTO agreements (id, turn, action_type, status, topic, decision_what, reason_why, proposed_by, entry_type, phase_id, abstraction_level, scope, time_axis, depends_on, resource_claims, timestamp, evidence, is_frozen, internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (a.get("id"), a.get("turn"), a.get("action_type"), a.get("status"), a.get("topic"),
         a.get("content", ""), a.get("rationale", ""), a.get("proposed_by"), a.get("entry_type"),
         a.get("phase_id"), a.get("abstraction_level"), a.get("scope"), a.get("time_axis"),
         depends_on_val, resource_claims_val, a.get("timestamp"), None, 0, None, run_id)
    )
```

### 4.3 呼び出し側変更

- `state["decisions"].append(x)` → `db_append_decision(x, conn, run_id)`（全9箇所）
- `state["agreements"].append(x)` → `db_append_agreement(x, conn, run_id)`（全3箇所：decision_extractor_node の UPDATE/CREATE 分岐2箇所 + integrator_node のマスター文書登録1箇所）
- 置き換え漏れは `KeyError: 'decisions'` / `KeyError: 'agreements'` で即座に検出される。

---

## 5. 読み出し側のDB化

### 5.1 読み出し関数

```python
def get_agreements_from_db(conn, run_id):
    # ORDER BY id で登録順序を保証（SQLite は ORDER BY なしの順序を保証しない）
    rows = conn.execute("SELECT * FROM agreements WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]

def get_decisions_from_db(conn, run_id):
    rows = conn.execute("SELECT * FROM decisions WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]
```

### 5.2 置き換え対象

| 既存の参照 | 置き換え後 |
|:---|:---|
| `_build_agreements_context(state["agreements"])` | `_build_agreements_context_from_db(conn, run_id)` — `status != 'Superseded'` フィルタ維持、Rejected も `⚠️[却下事項]` として含める既存挙動維持、`decision_what`/`reason_why` 列から取得 |
| `_build_hydrate_context(state["decisions"], config)` | `_build_hydrate_context_from_db(conn, run_id, config)` — 直近 `expert_history_window` 件を SELECT |
| `call_orchestrator` 内 `state["agreements"]` | `get_agreements_from_db(conn, run_id)` |
| `call_reflection` 内 `state["decisions"]` / `state["agreements"]` | `get_decisions_from_db` / `get_agreements_from_db` |
| `generate_user_utterance` 内 `state["agreements"]` / `state["decisions"]` | `get_agreements_from_db` / `get_decisions_from_db` |
| `detector_node` 内デバッグ出力 `state["decisions"]` | `get_decisions_from_db` |
| `integrator_node` 内 `state["agreements"]`（Deliverable抽出） | `get_agreements_from_db` + `entry_type='Deliverable'` フィルタ |
| `reviewer_node` 内 `state["agreements"]`（マスター文書検索） | `get_agreements_from_db` |
| `decision_extractor_node` 内 `existing_topics` 抽出・旧 agreement 検索 | `get_agreements_from_db` + アプリケーション側フィルタ |

---

## 6. system_prompt=[] バグ修正

- `generate_user_utterance` 内 `system_prompt = []` → `system_prompt = ""`、後段の `+=` を文字列連結に統一。
- **順序**: この修正を先に適用したコードを「list版ベースライン」とし、その上で Record モード実行 → SQLite版実装 → Replay 実行とする。これによりバグ修正と DB化の差分を切り分ける。

---

## 7. 回帰確認

### 7.1 Replay スタブ機構

- `query_AI` に REPLAY_MODE（`"off"` / `"record"` / `"replay"`）を追加。
- **キー＝ `(label, call_seq)`**: `query_AI` 内で run 単位のグローバル通し番号 `call_seq` をインクリメントし、Record/Replay 共通で `(label, call_seq)` をフィクスチャのキーとする。プロンプト内容に依存しないため、揮発値（timestamp/run_id/id/連番）混入の影響を受けない。
  - **`call_seq` は run 単位でリセットすること。** module-level のグローバルカウンタにすると、Record時とReplay時でカウント開始位置がずれた瞬間に全件ミス（＝即例外）になる。
- **ハッシュは検証用のみ**: Record 時に `(label, call_seq)` に対応するメッセージの正規化ハッシュ（揮発値を除外）も一緒に保存。Replay 時に照合し、不一致なら**警告を出すが再生は続行**。
- **キャッシュミス時の挙動**: `(label, call_seq)` がフィクスチャに存在しない場合は、**実APIへフォールバックせず即座に例外で落とす**。例外メッセージ例：`RuntimeError("REPLAY cache miss at (label={label}, seq={call_seq}). フィクスチャが揃っていないか、list版とSQLite版で呼び出し順序が異なります。")`
- Record モードでも重複キーが来たら例外（順序の非決定性検出）。

### 7.2 合格基準

1. **構造的一致（必須）**: replay モードで SQLite版を走らせ、`decisions` / `agreements` テーブルから `ORDER BY id` で SELECT した結果が、list版で記録された件数・topic集合・status分布・登録順序と一致すること。
   - **注意**: status分布が一致しなかった場合、それはDB化のバグではなく replay 基盤の不備（キーずれ）である可能性の方が高い。失敗時はまずフィクスチャのヒット率を疑うこと。
2. **Hydrate 再現性（必須）**: `_build_agreements_context_from_db(conn, run_id)` の出力文字列が、list版の `_build_agreements_context()` 出力と「Rejected/Approved の含まれ方・順序」で一致すること（LLM非決定部を除く構造的比較）。
3. **再起動後保持（必須）**: プロセスを強制終了（kill）後、別プロセス（または `sqlite3` CLI）から以下を実行し、行が残存していることを確認：
   ```sql
   SELECT count(*) FROM agreements WHERE run_id = '<殺したrun_id>';
   SELECT count(*) FROM decisions  WHERE run_id = '<殺したrun_id>';
   ```
   行数が 0 より大きければ合格（自動コミットにより、kill 直前までに通過した append はすべて disk に書かれている）。
   - **レジューム（state を復元してループを再開する処理）は R1 の範囲外であり、実装しない。**
4. **完全一致は要求しない**: content/rationale のテキスト内容そのものは replay により同一になるが、そもそも replay しない通常実行では非決定であるため、合格基準から「テキストの完全一致」は除外する。

### 7.3 テスト格納先（AGENTS.md 準拠）

| 項目 | 格納先 |
|:---|:---|
| 手順・フィクスチャ生成 | `phase1/phase1_dryrun.md`（新規作成） |
| 結果サマリー | `traceability.md`（T-*） |
| 失敗・次の修正 | `issue_backlog.md`（BL-xxx） |

---

## 8. R1作業範囲外（明示的に触らない）

- §3.2〜3.5（ツール呼び出し・write_agreement_tool）＝ R2/R3
- whiteboard_drafts の書き込みロジック ＝ R4
- chat_history の SQLite 移行（list 維持・テーブル定義のみ）
- current_goal の書き込み/読み出し（テーブル定義のみ）
- 列名統一の TypedDict 側リネームは BL 起票し、実施判断は「R2着手前」

---

## 9. BL起票（R1完了後・R2着手前に判断）

- `issue_backlog.md` に BL 起票：「`Agreement` TypedDict の `content`/`rationale` を `decision_what`/`reason_why` にリネームし、R1ラッパーのマッピングを除去する」（R2着手前に実施判断）。

---

## 10. 実装時の注意点（レビュー指摘より）

1. **call_seq は run 単位でリセット**: module-level のグローバルカウンタにすると、Record時とReplay時でカウント開始位置がずれた瞬間に全件ミス（＝即例外）になる。落ちてくれるので静かに壊れはしないが、原因究明で時間を溶かしがち。
2. **status分布不一致時は replay 基盤を疑う**: replay が成立していれば status分布一致はトートロジーに近い。不一致なら DB化のバグではなく replay 基盤の不備（キーずれ）の可能性が高い。
3. **R1完了後のクエリ本数確認**: `_build_agreements_context_from_db` がノードごとに毎回全件SELECTしていないか確認しておくと、R2以降でターン数が伸びた時に効いてくる。

---

## 11. 変更履歴

| 日付 | 変更点 |
|:---|:---|
| 2026-07-18 | 初版作成。レビュー指摘①〜⑧＋B矛盾＋Replayキー＋接続管理＋NOT NULL回避＋順序担保＋実装注意2点をすべて反映した最終版。 |