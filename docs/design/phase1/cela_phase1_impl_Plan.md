# R1〜R2（SQLite永続化基盤 / ツール呼び出し基盤・機械的検算ゲート）実装計画

> **作成日**: 2026-07-18
> **対象**: 既存プロトタイプ `cela_main.py` への R1・R2 フェーズ適用
> **参照**: 要件定義書 v35 付録A.3〜A.5・B.5.1、ロードマップ v25 R1/R2、Phase1〜R3設計書 v7 §2, §3.4, §3.5, §3.6, §6

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

- §3.2〜3.4.1（write_agreement_tool / 自律的 DB 書き込み）＝ R3（R2 は Python REPL ツールのみ、write_agreement_tool は含まない）
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

---

---

# R2（ツール呼び出し基盤・機械的検算ゲート）実装計画

> **対象**: 既存プロトタイプ `cela_main.py` への R2 フェーズ適用
> **参照**: 要件定義書 v35 付録A.3〜A.5・B.5.1、ロードマップ v25 R2、Phase1〜R3設計書 v7 §3.4, §3.5（§3.5.1〜3.5.3）

## R2.0 目的・基本方針

> **設計書（v7）との整合:** 本 R2 計画は `cela_phase1_design_v7.md` §3.5.2（ツール呼び出し実装方式）・§3.5.3（Python REPL サンドボックス）に準拠。§3.5.2/§3.5.3 は 2026-07-18 に ★v9 追記で本計画内容（query_AI 集約・random 除外・decimal/fractions 維持・危険呼び出し AST 検査・多層防御）を反映済み。関連決定: `decision_log.md` D-004〜D-008、`decision_lineage.md` 論点3〜8、`issue_backlog.md` BL-006〜BL-009。

`query_AI`（および内部の `_query_AI_live`）に **Function Calling / Tool Use** 対応を追加し、Python REPL 実行ツールを実装する。実証実験（要件定義書付録A.3〜A.5）で確認された「機械的検算ゲート（F-2.6）」を、既存の正規表現ベース `verify_budget_arithmetic` から Python REPL ベースに置き換える。

R1 と同じ「壊さない」原則:
- グラフ構造（ノード・エッジ・トポロジ）は一切変更しない（設計書§3.1）。
- `query_AI` の既存シグネチャ（文字列返却）は維持し、ツール付与は**オプション引数 `tools`** で後方互換的に追加する。
- ツール呼び出しループは **`query_AI` 内に集約**し、SDK レベルの `tool_calls` を直接扱う。LangGraph の `ToolNode` は新設しない（設計書§3.5.2 の意図を `query_AI` 集中化で満たす。逸脱理由は R2.0.1 参照）。
- Replay スタブ（`(label, call_seq)` キー・最終 content キャッシュ）の契約を維持する。

## R2.0.1 設計書 §3.5.2 の `call_expert_with_tools` 例からの逸脱とその理由

設計書 §3.5.2 は「各既存ノード関数内で `tools` パラメータを渡し、`tool_calls` が返った場合はループ内で実行する」という `call_expert_with_tools` 相当のラッパー例を示していた。本計画はこれと異なり、**ツール呼び出しループを共通層 `query_AI` に集約**する。逸脱の理由は以下の通り。

1. **既存コードでは `query_AI` が事実上の共通 API 層である**: 全ノード（call_expert / call_detector / call_reviewer / call_resource_arbiter / generate_user_utterance 等）がすでに `query_AI(messages, client, model, label)` を呼んでいる。ここに `tools` 引数を1箇所追加する方が、各ノード関数ごとに `call_expert_with_tools` のような個別ラッパーを5つ作るより変更箇所が少なく、「壊さない」原則（R1 の差分最小化方針）に合致する。
2. **DRY と保守性**: 設計書例は Expert 用のみだったが、実際には Detector / Reviewer / Arbiter / User AI も同様のループが必要。5ノードすべてに個別ラッパーを作るより、`query_AI` に集約する方が重複を避けられる。
3. **Replay 境界の維持**: Replay スタブの `(label, call_seq)` キーと最終 content キャッシュは `query_AI` 内にあり、ツール実行（Python REPL）はローカル・決定的である。ループを `query_AI` 内に置くことで「1ノード呼び出し＝1フィクスチャ」の境界がそのまま保たれ、replay 時はキャッシュされた最終 content を返すだけで済む。
4. **`bind_tools` 不使用は踏襲**: 設計書が求めていた「`bind_tools`（LangChain 系ラッパー）を使わず、素の OpenAI SDK の `tools`/`tool_calls` を直接扱う」という制約は、集中化しても満たされる（単に `create_kwargs["tools"] = tools` を渡し `msg.tool_calls` を処理するだけ）。

**5. 集約方式の妥当性（Claude との合意）**: 本集中化方式は Anthropic 公式 SDK の tool_runner、OpenAI Agents SDK の Runner、LangChain の AgentExecutor と同様の一般的な主流パターンである。設計書 §3.5.2 の `call_expert_with_tools` 例は説明用の最小例だったと解釈できるため、本計画の `query_AI` 集約方針をそのまま採用する。ツール dispatch の辞書化（R2.3 の `TOOL_DISPATCH`）は、R3 で `write_agreement_tool` を追加する際にループ本体を変更せずに済む任意の改善提案として既に反映済み。

## R2.1 実装ステップ概要

| Step | 内容 | 変更対象 |
| :--- | :--- | :--- |
| 0 | **BL-001 実施（R2の頭）**: `Agreement` TypedDict の `content`/`rationale` を `decision_what`/`reason_why` にリネーム。R1ラッパー（`db_append_agreement`/`get_agreements_from_db`）のエイリアス変換コードを除去し、呼び出し側を新キー名に統一する | `Agreement` TypedDict, `db_append_agreement`, 全呼び出し側 |
| 1 | Python REPL 実行ツール（サンドボックス）の実装 | 新規関数 `_run_python_repl` |
| 2 | `query_AI` / `_query_AI_live` に `tools` 引数とツール呼び出しループを追加 | `query_AI` シグネチャ拡張 |
| 3 | `response_format=json_object` との競合解消（ツール付与時は json_mode 無効化） | `_query_AI_live` 内 |
| 4 | ツール定義 `PYTHON_REPL_TOOL` をモジュール定数として定義 | 新規定数 |
| 5 | Detector / Reviewer / Arbiter / Expert / User AI の各呼び出しにツール付与 + プロンプトへ F-2.6 ルール明記 | `call_detector`, `call_reviewer`, `call_resource_arbiter`, `call_expert`, `generate_user_utterance` |
| 6 | Detector の known false-positive（B.5.1）修正：上限内数値差は矛盾としない旨をプロンプトに復活 | `call_detector` 内コメントアウト解除 |
| 7 | `verify_budget_arithmetic`（正規表現）の扱いを A/B で判断（設計書§3.5） | `reviewer_node` 内（当面は併用維持） |
| 8 | Replay スタブの契約確認（ツール付与後も `(label, call_seq)` で最終 content をキャッシュ） | 既存維持・検証 |

## R2.2 Step 1: Python REPL 実行ツール（サンドボックス）

設計書§3.5.3 の仕様に従い、サブプロセス分離＋AST 許可リスト＋多層防御で実装する。

```python
import ast
import subprocess

# 許可モジュール（ホワイトリスト）。random は除外（検算の決定性を損なう再現性リスク）。
# decimal/fractions は浮動小数点誤差回避の目的に合致する拡張として維持（設計書§3.5.3追記・AGENTS.md§7承認済み変更）。
_ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "fractions", "decimal"}

# 危険な名前（import文なしで呼べるビルトイン・組み込み関数）。AST上の Name/Attribute/Call 参照として検査。
_DANGEROUS_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "breakpoint",
}

def _run_python_repl(code: str, timeout: float = 5.0, max_output_bytes: int = 10240) -> str:
    """Sandboxed Python execution for mechanical arithmetic/verification (F-2.6 / F-5.1).

    Only math/statistics/datetime/json/fractions/decimal allowed.
    Network/IO/system modules and dangerous builtins (open/eval/exec/__import__ etc.) are rejected at AST level.
    """
    # [CONSTRAINT] Reject dangerous imports/calls before execution to prevent sandbox escape.
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"[REPL Error] SyntaxError: {e}"
    for node in ast.walk(tree):
        # import 文のチェック
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    return f"[REPL Error] import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in _ALLOWED_IMPORTS:
                return f"[REPL Error] import from '{node.module}' is not allowed"
        # 危険な名前の参照チェック（import文なしで呼べるもの）
        elif isinstance(node, ast.Name) and node.id in _DANGEROUS_NAMES:
            return f"[REPL Error] use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr in _DANGEROUS_NAMES:
            return f"[REPL Error] use of '.{node.attr}' is not allowed"
        elif isinstance(node, ast.Call):
            # __import__('os') 等の Call 形も捕捉
            if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_NAMES:
                return f"[REPL Error] call to '{node.func.id}' is not allowed"
    try:
        # [SAFETY] 多層防御: 作業ディレクトリを書き込み不可にし、低権限ユーザーで実行。
        # AST blacklist だけでは ().__class__.__bases__ 経由等の既知の回避を完全には防げないため、
        # プロセス側の権限絞り込みと併用する（絶対に破れないサンドボックスではなく多層防御であることが設計上の限界）。
        proc = subprocess.run(
            ["python", "-I", "-c", code],  # -I: isolated mode (no env/site)
            capture_output=True, text=True, timeout=timeout,
            # user=低権限ユーザー, cwd=書き込み不可ディレクトリ を本番環境では指定
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out.encode("utf-8")) > max_output_bytes:
            out = out[:max_output_bytes] + "\n[REPL Output truncated]"
        return out.strip() or "[REPL] (no output)"
    except subprocess.TimeoutExpired:
        return f"[REPL Error] execution exceeded {timeout}s timeout"
```

**設計判断**: サブプロセスは `python -I`（isolated mode）で起動。AST 検査は import 文だけでなく呼び出し式全体（open/eval/exec/__import__ 等の Name/Attribute/Call 参照）を見る。タイムアウト 5 秒、出力 10KB 制限（設計書§3.5.3 準拠）。`random` は検算の決定性（再現性）を損なうため許可リストから除外。`decimal`/`fractions` は浮動小数点誤差回避の目的に合致する拡張として維持し、設計書§3.5.3 の許可リストに理由付きで追記、AGENTS.md§7（定数変更の厳格管理）に沿って承認済み変更として扱う。

## R2.3 Step 2 & 3: `query_AI` のツール対応と json_mode 競合解消

`query_AI` に `tools: list[dict] | None = None` を追加。内部の `_query_AI_live` に同じく渡し、ツール付与時はツール呼び出しループを行い、かつ `response_format=json_object` を**設定しない**。

- `query_AI` シグネチャ拡張: `def query_AI(messages, client, model, label="Unknown Node", tools=None) -> str:` とし、REPLAY_MODE の record/replay ロジックは既存のまま（最終 content をキャッシュ）。
- `_query_AI_live` シグネチャ拡張: `tools=None` を追加。
- `use_json_mode = any(kw in label_lower for kw in STRUCTURED_OUTPUT_LABEL_KEYWORDS)` の直後に `if tools is not None: use_json_mode = False` を入れる（設計書§3.5.1：ツール付与時は json_object と排他）。
- `create_kwargs` 構築時に `if tools is not None: create_kwargs["tools"] = tools` を追加。
- **ツールループは既存の `try/except`（指数バックオフ `delays=[8,16,32,64,128]`）の「内側」で回す**。外側に置くと一時的な API エラーでツールループ全体が未捕捉例外としてクラッシュする。

```python
    # ツール名 → 実処理のマッピング（差し替え可能な対応表。R3 で write_agreement_tool 等を追加予定）
    TOOL_DISPATCH = {
        "python_repl": _run_python_repl,
    }

    # ツール呼び出しループ（tools 付与時のみ。既存 try/except リトライの内側で回す）
    MAX_TOOL_ITER = 5
    loop_messages = list(messages)
    create_kwargs["messages"] = loop_messages
    for _ in range(MAX_TOOL_ITER):
        response = client.chat.completions.create(**create_kwargs)
        choice = response.choices[0]
        msg = choice.message
        # [CONSTRAINT] 出力打ち切り検出: 既存非ツールパスと同様に、max_tokens 超過で
        # tool_calls の引数 JSON が途中で切れた場合を明示的に検出する。
        # この ValueError は APIError 系ではないため、外側の except に飲み込まれず
        # ログに「トークン予算不足が原因」と一目でわかる形で伝播する（後述の層1リトライ絞り込みと組み合わせ）。
        if choice.finish_reason == "length":
            raise ValueError("Tool call output truncated due to max_tokens limit")
        if not getattr(msg, "tool_calls", None):
            content = msg.content
            return content if content is not None else "(APIから空の応答が返されました)"
        loop_messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            handler = TOOL_DISPATCH.get(tc.function.name)
            if handler is None:
                result = f"[REPL Error] unknown tool: {tc.function.name}"
            else:
                # [SAFETY] LLM が壊れた引数 JSON を返した場合、例外を外に投げるのではなく
                # ツール結果としてモデルに返し、MAX_TOOL_ITER の予算内で自己修復させる。
                # （クラッシュさせると既存リトライに飲み込まれ原因が隠蔽されるため）
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError as e:
                    loop_messages.append({
                        "role": "tool", "tool_call_id": tc.id,
                        "content": json.dumps({"error": f"invalid arguments JSON: {e}"}, ensure_ascii=False),
                    })
                    continue
                result = handler(args.get("code", ""))
            loop_messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        create_kwargs["messages"] = loop_messages
    # [CONSTRAINT] 非収束は一時的な API 障害ではなく設計上の異常事態。
    # 外側の except を APIError 系に絞ることで、この RuntimeError は握りつぶされず
    # ログに「ツールループが収束しなかった」と一目でわかる形で伝播する。
    raise RuntimeError(f"ツール呼び出しが{MAX_TOOL_ITER}回を超えて収束しませんでした")
```

**注意**: 非ツール呼び出し（`tools=None`）は既存の `if choice.finish_reason == "length"` 以降の分岐を通る。両者を `tools is None` で分岐させ、既存ロジックを壊さない。

**ツール dispatch の分離（設計上の定石）**: ループ本体（call→tool_calls 判定→実行→結果追加→再 call）は `query_AI` 内に1箇所集約し、ツール名→実処理のマッピングは `TOOL_DISPATCH` 辞書に分離した。現状は `python_repl` 1個のみだが、R3 で `write_agreement_tool` が加わることを見越し、辞書に `{"python_repl": _run_python_repl, "write_agreement_tool": ...}` を追加するだけでループ本体に触れずにツールを拡張できる。

**層1リトライの絞り込み（例外の隠蔽防止）**: 既存の `except Exception as e:`（指数バックオフ `delays=[8,16,32,64,128]`、合計約248秒）は「一時的なAPI障害（レート制限・タイムアウト等）」と「ロジックエラー（LLMの壊れた引数・ツールループ非収束）」を区別せず、両方に同じバックオフをかけた上で最終的に `(サーバー高負荷によるAPIエラー)` という誤った診断メッセージに丸めてしまう。後者は再試行しても直る見込みが薄いため、外側の `except` を OpenAI SDK の API 関連例外に絞り込む：`from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError` を import し、`except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:` とする。これにより、上記の `ValueError`（max_tokens 打ち切り）・`RuntimeError`（非収束）・`json.JSONDecodeError`（ただし本計画ではツール結果として返すため発生しない）等のロジック起因例外はそのまま伝播し、ログ上で原因が一目でわかる。

**リトライ粒度の留意点（層1＝API呼び出し失敗リトライ）**: ツールループは既存 `try/except`（指数バックオフ、ただし対象をAPIError系に絞り込み済み）の内側にあるため、1回の `create()` が一時APIエラーならそのブロック内で再試行される。ただしこの方式はリトライ単位が「ツールループ全体」と粗く、ループ途中で `create()` が失敗すると `loop_messages`（途中経過）ごと最初からやり直しになる。実害は軽微（MAX_TOOL_ITER=5、Python REPL はローカルで失敗しにくい）と判断し当面許容。将来的に改善する場合は BL 起票で対応（R2.12 参照）。

**層2リトライ（JSON パース失敗時のフェイルクローズ）**: ツール付与により `use_json_mode=False` となり、Detector/Reviewer の JSON 抽出安定性が下がる。そのため `_safe_json_parse` が失敗（fallback 相当を返した）場合は、それを例外として扱いノード呼び出し自体を再試行する「層2リトライ」を追加する（層1＝API呼び出し失敗リトライとは別レイヤー）。層2リトライの上限（例: 2〜3回）を使い切った場合の fallback は、現状の `{"constraint_issue": "none"}`（フェイルオープン）ではなく、**major 側に倒す（フェイルクローズ）**こと。F-2.6 検算ゲート導入の目的（暗算を信用しない）を損なわないため。

## R2.4 Step 4: ツール定義定数

```python
PYTHON_REPL_TOOL = {
    "type": "function",
    "function": {
        "name": "python_repl",
        "description": (
            "Execute a Python snippet for mechanical arithmetic/verification (e.g. sum, ratio, "
            "threshold comparison). Sandboxed: only math/statistics/datetime/json allowed, no network/IO. "
            "Use this to VERIFY any numeric claim before asserting correctness."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute (e.g. 'print(100+50*3)')"}
            },
            "required": ["code"],
        },
    },
}
```

## R2.5 Step 5: 各ノードへのツール付与とプロンプト改修

設計書§3.4（ツール付与範囲）に従い、以下 5 ノードに `tools=[PYTHON_REPL_TOOL]` を渡す。

| ノード | 呼び出し変更 | プロンプト追記（F-2.6 ルール） |
| :--- | :--- | :--- |
| `call_detector` | `query_AI(..., label="Detector", tools=[PYTHON_REPL_TOOL])` | 数値主張（合計・比率・閾値比較等）を含む場合、**必ず `python_repl` ツールで機械的に再計算**し、一致を確認してからでなければ `constraint_issue="major"` としない。暗算での承認は禁止。 |
| `call_reviewer` | `query_AI(..., label="Reviewer QA", tools=[PYTHON_REPL_TOOL])` | 成果物中の数値的主張（予算・数量・比率等）について、承認（passed:true）前に `python_repl` で再計算し、矛盾がないことを確認すること。 |
| `call_resource_arbiter` | `query_AI(..., label="Resource Arbiter", tools=[PYTHON_REPL_TOOL])` | 予算超過判定は `python_repl` で機械的に合計・比較してから行うこと。 |
| `call_expert` | `query_AI(..., label=f"Expert:{expert_name}", tools=[PYTHON_REPL_TOOL])` | 数値的根拠を提示する際は `python_repl` で計算を実行し、結果を明示すること。 |
| `generate_user_utterance` | `query_AI(..., label="User AI", tools=[PYTHON_REPL_TOOL])` | Expert の数値主張を批判的に監査する際、暗算に頼らず `python_repl` で再計算し、矛盾（計算ミス・ごまかし）を看破すること。 |

**json_mode の扱い**: 上記 5 ノードはいずれもツール付与により `use_json_mode=False` となる。Detector/Reviewer は既存で JSON を期待していたが、プロンプト末尾の `Return ONLY JSON: {...}` 指示は維持するため、最終テキストから `_safe_json_parse` でパース可能（設計書§3.5.1: 判定結果はツール呼び出し後の最終メッセージからテキストパース）。

**Orchestrator / Decision Extractor**: ツール非付与（`tools=None`）のまま `response_format=json_object` 維持（設計書§3.5.1）。R2 範囲外。

## R2.6 Step 6: Detector known false-positive（B.5.1）修正

`call_detector` 内で現在コメントアウトされている以下の指針を**復活（アンコメント）**する。これは付録B.5.1 で既知の誤判定（予算上限内の数値差を major と誤判定）を防ぐ必須対応。

```python
f"**追加の重要指示: 上限値（例:「上限1億円」「上限3,000万円」）を超えていない場合、"
f"あるいは上限値に近い値であっても、それは矛盾とは見なさないでください。"
f"「上限内の数値差」や「予算の上下関係」を正確に計算し、上限を超えていない場合はnoneまたはminorと判定してください。\n\n"
```

併せて、このブロックの直後に R2.5 の F-2.6 ルール（python_repl での検算）を追記する。

## R2.7 Step 7: `verify_budget_arithmetic` の扱い（A/B 判断）

設計書§3.5 の方針：「Python REPL ベースの汎用検算に置き換え後、廃止するか併用するかを A/B で判断する」。

- R2 では `reviewer_node` 内の `verify_budget_arithmetic(master_doc)` 呼び出しを**当面は併用維持**する（削除しない）。
- F-2.6 の主たるゲートは LLM の `python_repl` 呼び出しとする。
- 完了条件 D（数値矛盾検出率 5/5）の A/B テスト実施後、正規表現版の検出寄与が無いと判断されれば `issue_backlog.md` へ BL 起票して廃止を提案する。

## R2.8 Step 8: Replay スタブの契約確認

- `query_AI` の `(label, call_seq)` キーと「最終 content キャッシュ」の契約は変更なし。
- ツール付与ノードも `query_AI` 経由のため、1 回のノード呼び出し＝1 つの `(label, call_seq)` フィクスチャ（最終 content）となる。ツール実行（Python REPL）はローカル・決定的であり、replay 時はキャッシュされた最終 content をそのまま返すため問題なし。
- **注意**: R2 では Detector / Reviewer / Expert / User AI のプロンプトを変更するため、R1 で記録したフィクスチャとの**メッセージハッシュが不一致**になる（警告のみ・再生は続行）。R2 用のフィクスチャは新規に `record` モードで再取得する。

## R2.9 完了条件（ロードマップ R2 / 設計書§5 指標 C・D）

| 指標 | 測定方法 | 成功条件 | 実測値 |
| :--- | :--- | :--- | :--- |
| **D. 数値矛盾の検出率** | 意図的に数値矛盾を仕込んだ成果物（RETRY_BASE_DELAY 実験と同種）を Detector / Reviewer に監査させる（`pytest` による自動テスト：`tests/test_f26_detection.py`）。 | 5 試行中 5 試行で矛盾を検出すること（付録A.5 の実測値を合格基準）。 | **✅ 達成（2026-07-19、[traceability.md T-7](../traceability.md)）**: Detector 5/5 major、Reviewer 5/5 passed=False。B.5.1既知誤判定の非退行も3/3 none/minorで確認（副次的にD-011条件も充足）。初回実行はBL-013（`python_repl`の`print()`忘れによる無出力）で1件非収束したが、ツール説明文修正後の再実行で非収束0件・全13回のツール呼び出しのうち11回はiter=1で正答。 |
| **C. 収束性とコストのトレードオフ** | 同一タスクを変更前後で複数回（最低 5 試行）実行し、差し戻し回数・総ターン数・総トークン消費量をログから集計。 | (a) 差し戻し回数・収束までのターン数が変更前より減少すること。(b) 1 ターンあたりトークン増加が N-6 許容範囲（実測約 4.5 倍）内であること。「総トークン削減」は成功条件としない（設計書§5）。 | **未測定**（[issue_backlog.md BL-002](../issue_backlog.md)参照。`run_ai_vs_ai_loop`本体のR1版/R2版比較ドライランが必要） |

## R2.10 テスト・ドライラン手順（AGENTS.md 準拠）

| 項目 | 格納先 |
| :--- | :--- |
| 手順・フィクスチャ生成（R2 用 record） | `phase1/phase1_dryrun.md`（R1 用と同一ファイルに R2 セクションを追記） |
| 自動テスト | `tests/test_f26_detection.py`（新規作成） |
| 結果サマリー | `traceability.md`（T-*） |
| 失敗・次の修正 | `issue_backlog.md`（BL-xxx） |

## R2.11 R2 作業範囲外（明示的に触らない）

- §3.2〜3.4.1（`write_agreement_tool` / 自律的 DB 書き込み）＝ R3
- `write_agreement_tool` のツール定義・バリデーションラッパー＝ R3（R2 では Python REPL のみ）
- whiteboard_drafts の書き込みロジック ＝ R4
- F-3.7（思考ログ記録）・Freeze・GoalShiftEvent ＝ R5

## R2.12 BL起票（R2完了後）

- `issue_backlog.md` に BL 起票：「`verify_budget_arithmetic`（正規表現）の廃止判断（A/B テスト結果に基づく）」。
- `issue_backlog.md` に BL 起票（継続確認）：「R2 でプロンプトを変更したノードの replay フィクスチャを R2 用に再取得・保管」。
- `issue_backlog.md` に BL 起票（将来の改善）：「ツール呼び出しループのリトライ粒度を `create()` 単位に細分化する」。現状は既存の `try/except`（指数バックオフ）ブロック内側でループを回すため、ループ途中の1回の `create()` 失敗時に `loop_messages` ごと破棄して最初からやり直す。ツール往復が長くなるノードが増えた段階で、公式 SDK のように `create()` 単体のリトライ（ループ途中経過の保持）へ改善する。
- `issue_backlog.md` に BL 起票（設計書追記）：「設計書 §3.5.3 の許可モジュールリストに `decimal`/`fractions` を理由付きで追記（浮動小数点誤差回避の目的に合致する拡張）。`random` は検算の決定性リスクにより除外。AGENTS.md§7 の厳格管理に沿り承認済み変更として扱う」。
