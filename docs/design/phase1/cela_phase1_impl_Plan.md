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

`query_AI`（および内部の `_query_AI_live`）に **Function Calling / Tool Use** 対応を追加し、Python REPL 実行ツールを実装する。実証実験（要件定義書付録A.3〜A.5）で確認された「機械的検算ゲート（F-2.6）」を、既存の正規表現ベース `verify_budget_arithmetic` から Python REPL ベースに置き換える。

R1 と同じ「壊さない」原則:
- グラフ構造（ノード・エッジ・トポロジ）は一切変更しない（設計書§3.1）。
- `query_AI` の既存シグネチャ（文字列返却）は維持し、ツール付与は**オプション引数 `tools`** で後方互換的に追加する。
- ツール呼び出しループは各ノード関数内で SDK レベルの `tool_calls` を直接扱い、LangGraph の `ToolNode` は新設しない（設計書§3.5.2）。
- Replay スタブ（`(label, call_seq)` キー・最終 content キャッシュ）の契約を維持する。

## R2.1 実装ステップ概要

| Step | 内容 | 変更対象 |
| :--- | :--- | :--- |
| 1 | Python REPL 実行ツール（サンドボックス）の実装 | 新規関数 `_run_python_repl` |
| 2 | `query_AI` / `_query_AI_live` に `tools` 引数とツール呼び出しループを追加 | `query_AI` シグネチャ拡張 |
| 3 | `response_format=json_object` との競合解消（ツール付与時は json_mode 無効化） | `_query_AI_live` 内 |
| 4 | ツール定義 `PYTHON_REPL_TOOL` をモジュール定数として定義 | 新規定数 |
| 5 | Detector / Reviewer / Arbiter / Expert / User AI の各呼び出しにツール付与 + プロンプトへ F-2.6 ルール明記 | `call_detector`, `call_reviewer`, `call_resource_arbiter`, `call_expert`, `generate_user_utterance` |
| 6 | Detector の known false-positive（B.5.1）修正：上限内数値差は矛盾としない旨をプロンプトに復活 | `call_detector` 内コメントアウト解除 |
| 7 | `verify_budget_arithmetic`（正規表現）の扱いを A/B で判断（設計書§3.5） | `reviewer_node` 内（当面は併用維持） |
| 8 | Replay スタブの契約確認（ツール付与後も `(label, call_seq)` で最終 content をキャッシュ） | 既存維持・検証 |

## R2.2 Step 1: Python REPL 実行ツール（サンドボックス）

設計書§3.5.3 の仕様に従い、サブプロセス分離＋AST 許可リストで実装する。

```python
import ast
import subprocess

# 許可モジュール（ホワイトリスト）
_ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "fractions", "decimal", "random"}

def _run_python_repl(code: str, timeout: float = 5.0, max_output_bytes: int = 10240) -> str:
    """Sandboxed Python execution for mechanical arithmetic/verification (F-2.6 / F-5.1).

    Only math/statistics/datetime/json and pure stdlib arithmetic are allowed.
    Network/IO/system modules (os, sys, subprocess, socket, etc.) are rejected at AST level.
    """
    # [CONSTRAINT] Reject dangerous imports before execution to prevent sandbox escape.
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"[REPL Error] SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    return f"[REPL Error] import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in _ALLOWED_IMPORTS:
                return f"[REPL Error] import from '{node.module}' is not allowed"
    try:
        proc = subprocess.run(
            ["python", "-I", "-c", code],  # -I: isolated mode (no env/site)
            capture_output=True, text=True, timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out.encode("utf-8")) > max_output_bytes:
            out = out[:max_output_bytes] + "\n[REPL Output truncated]"
        return out.strip() or "[REPL] (no output)"
    except subprocess.TimeoutExpired:
        return f"[REPL Error] execution exceeded {timeout}s timeout"
```

**設計判断**: サブプロセスは `python -I`（isolated mode）で起動し、ネットワーク/ファイル I/O 系モジュールを AST で事前ブロック。タイムアウト 5 秒、出力 10KB 制限（設計書§3.5.3 準拠）。

## R2.3 Step 2 & 3: `query_AI` のツール対応と json_mode 競合解消

`query_AI` に `tools: list[dict] | None = None` を追加。内部の `_query_AI_live` に同じく渡し、ツール付与時はツール呼び出しループを行い、かつ `response_format=json_object` を**設定しない**。

- `query_AI` シグネチャ拡張: `def query_AI(messages, client, model, label="Unknown Node", tools=None) -> str:` とし、REPLAY_MODE の record/replay ロジックは既存のまま（最終 content をキャッシュ）。
- `_query_AI_live` シグネチャ拡張: `tools=None` を追加。
- `use_json_mode = any(kw in label_lower for kw in STRUCTURED_OUTPUT_LABEL_KEYWORDS)` の直後に `if tools is not None: use_json_mode = False` を入れる（設計書§3.5.1：ツール付与時は json_object と排他）。
- `create_kwargs` 構築時に `if tools is not None: create_kwargs["tools"] = tools` を追加。
- ツール付与時は以下のループを追加（非ツール時は既存ロジックのまま）:

```python
    # ツール呼び出しループ（tools 付与時のみ）
    MAX_TOOL_ITER = 5
    loop_messages = list(messages)
    create_kwargs["messages"] = loop_messages
    for _ in range(MAX_TOOL_ITER):
        response = client.chat.completions.create(**create_kwargs)
        choice = response.choices[0]
        msg = choice.message
        if not getattr(msg, "tool_calls", None):
            content = msg.content
            return content if content is not None else "(APIから空の応答が返されました)"
        loop_messages.append(msg.model_dump())
        for tc in msg.tool_calls:
            if tc.function.name == "python_repl":
                result = _run_python_repl(json.loads(tc.function.arguments).get("code", ""))
            else:
                result = f"[REPL Error] unknown tool: {tc.function.name}"
            loop_messages.append({
                "role": "tool", "tool_call_id": tc.id,
                "content": json.dumps(result, ensure_ascii=False),
            })
        create_kwargs["messages"] = loop_messages
    raise RuntimeError(f"ツール呼び出しが{MAX_TOOL_ITER}回を超えて収束しませんでした")
```

**注意**: 非ツール呼び出し（`tools=None`）は既存の `if choice.finish_reason == "length"` 以降の分岐を通る。両者を `tools is None` で分岐させ、既存ロジックを壊さない。

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

| 指標 | 測定方法 | 成功条件 |
| :--- | :--- | :--- |
| **D. 数値矛盾の検出率** | 意図的に数値矛盾を仕込んだ成果物（RETRY_BASE_DELAY 実験と同種）を Detector / Reviewer に監査させる（`pytest` による自動テスト：`tests/test_f26_detection.py`）。 | 5 試行中 5 試行で矛盾を検出すること（付録A.5 の実測値を合格基準）。 |
| **C. 収束性とコストのトレードオフ** | 同一タスクを変更前後で複数回（最低 5 試行）実行し、差し戻し回数・総ターン数・総トークン消費量をログから集計。 | (a) 差し戻し回数・収束までのターン数が変更前より減少すること。(b) 1 ターンあたりトークン増加が N-6 許容範囲（実測約 4.5 倍）内であること。「総トークン削減」は成功条件としない（設計書§5）。 |

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
