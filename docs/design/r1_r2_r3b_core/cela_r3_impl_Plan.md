# R3 実装計画: 自律的DB読み取り・書き込みへの移行
# (Cognitive Experience Lineage-driven Agent System - Refactor R3)

> **作成日**: 2026-07-21
> **対象**: 既存プロトタイプ `cela_main.py` への R3フェーズ適用
> **参照**: 要件定義書 v35 (F-3.1〜F-3.9, F-8.4)、ロードマップ v25 R3、Phase1〜R3設計書 v7 §3.2〜3.4.1、D-036/R3a再編
> **前提**: R1 (SQLite永続化) 完了、R2 (ツール呼び出し基盤・検算ゲート) 完了 (D-036)

---

## 0. 目的・基本方針

R3は**R3a（自律的DB/ファイル読み取り、F-3.8/F-3.9、先行実装）→R3b（自律的DB書き込み、F-3.1〜F-3.7、旧来のR3スコープ）**の2段階で実装する（D-036）。

**R3aの狙い**: T-10ドライランで発見したBL-035（フェーズ横断`verified_facts`参照不能）・BL-036（財務・需要数値ドリフト）・BL-037（`reason_why`の薄さ）の根本原因である「自律的読み取り」の欠落を解消する。

**R3bの狙い**: 要件定義書v19で宣言された設計転換（`decision_extractor_node`による事後抽出から、各AI自身の自律書き込みへの移行）を実コードに反映する。

**両フェーズ共通の方針**:
- 既存の`TOOL_DISPATCH`辞書に新ツールを追加する形で実装する（R2で確立したパターンの踏襲）
- グラフのトポロジ（ノード追加・削除）は行わない（設計書v7 §3.1の原則）
- `decision_extractor_node`は撤廃せず、書き漏れ時の予備的セーフティネットとして維持する
- **読み取りツール（F-3.8）と書き込みツール（F-3.1）は、Integrator・Resource Arbiterを含む全ツール付与対象ノードに両方とも付与する**（レビューで指摘された非対称付与を解消。詳細は§2.6・§3.4）

**★レビュー反映（2026-07-21）に関する注記**: 本計画の初版レビューで、(1) `TOOL_DISPATCH`のディスパッチ処理が`python_repl`以外のツールに構造化引数を渡せていない、(2) `write_agreement`経由の書き込みが`verified_facts`の更新経路を持たずR3aの効果を自ら空洞化する、(3) `read_deliverable_file`のパス検証がこのWindows環境で機能しない、(4) `_check_write_permission`がロール×status許可表を完全に実装していない、(5) `depends_on`が参照する`agreements.id`をLLMが一度も見ていない、という5点の指摘があり、いずれも本改訂で修正済み（該当箇所に★マークで明記）。Integrator/Arbiterへの読み書き両ツール付与の非対称性も併せて解消した。

---

## 1. 実行ポリシー

- **R3aを先に実装し、完了確認してからR3bに進む**（R3aはR3bの前提ではないが、BL-035/036/037の解消が優先）
- 各ステップで`python -m py_compile cela_main.py`による構文確認を行う
- オフラインスモークテスト（フェイククライアント、実LLM呼び出しなし）で動作確認を行う
- 実LLM呼び出しを伴うドライランは、各サブフェーズ完了後に実施する

---

## 1.5 共通前提修正（★Step 0扱い、R3a着手前に必須）

### 1.5.1 `TOOL_DISPATCH`ディスパッチ処理の引数渡し修正

**問題（致命的）**: 現行の`_query_AI_live`内ツールループ（`cela_main.py:744-748`）は以下のようになっている。

```python
if tc.function.name == "python_repl":
    result = repl_session.run(args.get("code", ""))
    python_calls_log.append({"code": args.get("code", ""), "result": result})
else:
    result = handler(args.get("code", ""))
```

`python_repl`以外のツールは`handler(args.get("code", ""))`という**単一文字列**（新ツールの引数には`"code"`キーが存在しないため常に空文字列）で呼び出される。現状`TOOL_DISPATCH`には`python_repl`しか登録がなく、この`else`分岐は一度も実行されたことがない未検証コードである。R3a/R3bで追加する`read_verified_fact`・`read_deliverable_file`・`write_agreement`はすべて`args: dict`（構造化された複数フィールド）を前提としているため、**この行を修正しない限り新ツールは全滅する**。

**修正内容**（R3a Step 0として最優先で実施）:

```python
if tc.function.name == "python_repl":
    result = repl_session.run(args.get("code", ""))
    python_calls_log.append({"code": args.get("code", ""), "result": result})
else:
    result = handler(args)   # ★修正: 構造化されたargs辞書全体を渡す
```

`TOOL_DISPATCH`に登録する各ハンドラ（`_read_verified_fact`等）は、`args`のみを受け取るシグネチャに統一する（`conn`/`run_id`/`caller_role`はクロージャ経由で束縛し、`TOOL_DISPATCH`辞書自体には`(args: dict) -> str`という単一シグネチャのみを登録する。§2.5・§3.3参照）。

### 1.5.2 完了条件

| # | 条件 | 検証方法 |
|---|------|----------|
| R0-T1 | `handler(args)`修正後も`python_repl`の既存動作（オフラインスモークテスト）が回帰しないこと | 既存テスト再実行 |
| R0-T2 | ダミーの2引数ツールを`TOOL_DISPATCH`に一時登録し、`args`辞書がそのまま渡ることを確認 | オフラインスモークテスト（新規） |

---

## 2. R3a: 自律的DB/ファイル読み取り（F-3.8/F-3.9）

### 2.1 スキーマ変更: `verified_facts`テーブルの拡張（F-3.9）

**現状のスキーマ**:
```sql
CREATE TABLE IF NOT EXISTS verified_facts (
    variable_name TEXT NOT NULL, value TEXT NOT NULL, unit TEXT DEFAULT '',
    source_task_id TEXT, source_phase_id TEXT, confirmed_by TEXT, confirmed_at REAL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (run_id, variable_name)
);
```

**F-3.9要件**（要件定義書v35.2 §F-3.9）に基づき、`{topic, value, reason, citations}`構造化タプルを保持する。

**変更内容**:
- `reason TEXT DEFAULT ''` — 理由（確認・暫定の区別を含む）
- `citations TEXT DEFAULT '[]'` — 引用元（chat_history/agreements中の参照箇所のJSON配列）
- `confidence TEXT DEFAULT 'confirmed'` — 確定/暫定の区別（`confirmed` / `provisional`）

```sql
-- R3a: verified_factsテーブルの拡張（F-3.9準拠）
-- 既存テーブルに列を追加する（ALTER TABLE）
ALTER TABLE verified_facts ADD COLUMN reason TEXT DEFAULT '';
ALTER TABLE verified_facts ADD COLUMN citations TEXT DEFAULT '[]';
ALTER TABLE verified_facts ADD COLUMN confidence TEXT DEFAULT 'confirmed';
```

**注意**: SQLiteの`ALTER TABLE ADD COLUMN`は既存行にはデフォルト値を設定するため、R1で作成済みのデータにも影響しない。`init_db`内で`ALTER TABLE`を実行するが、列が既に存在する場合は無視する（`IF NOT EXISTS`相当の挙動はSQLiteの`ALTER TABLE`にはないため、try/exceptでスキップする）。

### 2.2 `upsert_verified_fact`の拡張

**変更内容**: `reason`/`citations`/`confidence`パラメータを追加し、UPSERT文に反映する。

```python
def upsert_verified_fact(conn, run_id, variable_name, value, unit,
                         source_task_id, source_phase_id, confirmed_by,
                         reason="", citations=None, confidence="confirmed"):
    """[F-3.9] 構造化ファクトストア: {topic, value, reason, citations, confidence} を保存"""
    citations_json = json.dumps(citations or [], ensure_ascii=False)
    conn.execute(
        "INSERT INTO verified_facts (run_id, variable_name, value, unit, "
        "source_task_id, source_phase_id, confirmed_by, confirmed_at, "
        "reason, citations, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, variable_name) DO UPDATE SET "
        "value=excluded.value, unit=excluded.unit, "
        "source_task_id=excluded.source_task_id, source_phase_id=excluded.source_phase_id, "
        "confirmed_by=excluded.confirmed_by, confirmed_at=excluded.confirmed_at, "
        "reason=excluded.reason, citations=excluded.citations, confidence=excluded.confidence",
        (run_id, variable_name, str(value), unit, source_task_id, source_phase_id,
         confirmed_by, time.time(), reason, citations_json, confidence)
    )
```

### 2.3 `get_verified_facts_from_db`の拡張

**変更内容**: 戻り値に`reason`/`citations`/`confidence`を含める。トピック検索機能を追加。

```python
def get_verified_facts_from_db(conn, run_id, variable_names=None, topic=None):
    """[F-3.9] 構造化ファクトストアから検索。variable_namesまたはtopicでフィルタ"""
    if topic:
        rows = conn.execute(
            "SELECT * FROM verified_facts WHERE run_id=? AND variable_name LIKE ?",
            (run_id, f"%{topic}%")
        ).fetchall()
    elif variable_names:
        placeholders = ",".join(["?"] * len(variable_names))
        rows = conn.execute(
            f"SELECT * FROM verified_facts WHERE run_id=? AND variable_name IN ({placeholders})",
            (run_id, *variable_names)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM verified_facts WHERE run_id=?",
            (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]
```

### 2.4 読み取り専用ツール定義（F-3.8）

`PYTHON_REPL_TOOL`と同様に、`TOOL_DISPATCH`に登録する読み取り専用ツールを2つ新規定義する。

#### 2.4.1 `read_verified_fact`ツール

```python
READ_VERIFIED_FACT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_verified_fact",
        "description": (
            "Search verified facts (confirmed values) across ALL phases. "
            "You can search by variable name (e.g. 'vehicle_count') or by topic keyword. "
            "Returns the value, reason, citations, and confidence level. "
            "Use this to access cross-phase dependencies that are not in your current phase's scope."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variable_name": {
                    "type": "string",
                    "description": "Exact variable name to search for (e.g. 'vehicle_count', 'annual_operating_cost')"
                },
                "topic_keyword": {
                    "type": "string",
                    "description": "Topic keyword for fuzzy search (e.g. '車両', '予算', '需要')"
                }
            }
        }
    }
}
```

#### 2.4.2 `read_deliverable_file`ツール

```python
READ_DELIVERABLE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_deliverable_file",
        "description": (
            "Read a deliverable file from the log/deliverables/ directory. "
            "Use this to reference previous task outputs for cross-phase integration. "
            "Returns the file content as text."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "file_path": {
                    "type": "string",
                    "description": "Full path to the deliverable file (e.g. 'log/2026-07-20/1421/deliverables/task_3_2_budget.md')"
                }
            },
            "required": ["file_path"]
        }
    }
}
```

#### 2.4.3 ツールハンドラ関数

```python
def _read_verified_fact(args: dict, conn: sqlite3.Connection, run_id: str) -> str:
    """[F-3.8] verified_facts読み取りツールのハンドラ"""
    variable_name = args.get("variable_name")
    topic_keyword = args.get("topic_keyword")
    results = get_verified_facts_from_db(conn, run_id,
                                          variable_names=[variable_name] if variable_name else None,
                                          topic=topic_keyword)
    if not results:
        return json.dumps({"status": "not_found", "message": "該当する確定値が見つかりませんでした。"}, ensure_ascii=False)
    return json.dumps(results, ensure_ascii=False, indent=2)

def _read_deliverable_file(args: dict) -> str:
    """[F-3.8] Deliverableファイル読み取りツールのハンドラ

    ★修正（レビュー指摘③）: `save_deliverable_to_file`（cela_main.py:134-138）は
    `os.path.join(log_dir, "deliverables", filename)`でパスを生成しており、本環境（Windows）では
    実際のパスは`log\\2026-07-20\\1421\\deliverables\\...`のようにバックスラッシュ区切りになる。
    旧案の`file_path.startswith("log/")`（フォワードスラッシュ固定の文字列前方一致）は、
    (a) この環境で実在するパスを常に拒否してしまう、(b) `log/../secret.txt`のような
    パストラバーサルを防げない、という2つの欠陥を持っていた。`pathlib.Path.resolve()`で
    絶対パスに正規化した上で`relative_to()`によるディレクトリ包含チェックに変更する。
    """
    file_path = args.get("file_path", "")
    if not file_path:
        return json.dumps({"status": "error", "message": "file_pathが指定されていません。"}, ensure_ascii=False)
    base_dir = Path("log").resolve()
    try:
        resolved = Path(file_path).resolve()
        resolved.relative_to(base_dir)
    except ValueError:
        return json.dumps({"status": "error", "message": "logディレクトリ外へのアクセスは禁止されています。"}, ensure_ascii=False)
    if not resolved.exists() or not resolved.is_file():
        return json.dumps({"status": "not_found", "message": f"ファイルが見つかりません: {file_path}"}, ensure_ascii=False)
    try:
        content = resolved.read_text(encoding="utf-8")
        return content[:10000]  # 大量出力防止
    except Exception as e:
        return json.dumps({"status": "error", "message": str(e)}, ensure_ascii=False)
```

**注意**: `Path("log").resolve()`はプロセスのカレントディレクトリ基準で`log/`を解決する。`cela_main.py`は常にプロジェクトルートから起動される前提（既存の`MultiLogger`・`save_deliverable_to_file`も同じ前提に依存）のため、追加の設定変更は不要。`pathlib.Path`は本ファイル冒頭に未importのため、`cela_main.py`側で`from pathlib import Path`の追加が必要（変更対象ファイル一覧§6に反映済み）。

### 2.5 `TOOL_DISPATCH`への登録

**★修正（§1.5.1のディスパッチ修正を前提）**: ディスパッチループが`handler(args)`（辞書全体）を渡すよう修正済みなので、`TOOL_DISPATCH`の各エントリは`(args: dict) -> str`という単一シグネチャで統一できる。`conn`・`run_id`はモジュールレベル変数経由でクロージャに束縛する（`_LAST_PYTHON_CALLS`と同様、LangGraphが1プロセス内でノードを同期的に逐次実行する現行アーキテクチャ前提のパターンを踏襲、BL-033参照）。

```python
TOOL_DISPATCH = {
    "python_repl": _run_python_repl,
    "read_verified_fact": lambda args: _read_verified_fact(args, get_active_conn(), _CURRENT_RUN_ID),
    "read_deliverable_file": _read_deliverable_file,
}
```

**注意**: `read_verified_fact`は`conn`と`run_id`を必要とする。モジュールレベルの`_CURRENT_RUN_ID`変数を`run_ai_vs_ai_loop`冒頭でセットし、ハンドラから参照する。

### 2.6 ツール付与ノードの拡張

R3aでは読み取りツールを**全ノードに付与する**。ただしPython REPLと同様に、ツール呼び出しループ内で処理されるため、既存の`query_AI`の`tools`パラメータに追加するだけでよい。

**付与対象**:
- Expert（F-3.8: フェーズ横断の確定値参照、BL-035解消）
- User AI（F-3.8: 承認済み根拠の確認、BL-036解消）
- Detector（F-3.8: 過去の決定の理由を遡って検証、BL-037解消）
- Reviewer（F-3.8: 最終成果物の根拠確認）
- Integrator（F-3.8: 統合時の横断矛盾チェック）

**呼び出し側の変更**: 各ノード関数（`call_expert`、`generate_user_utterance`、`call_detector`、`call_reviewer`、`call_integrator`）で、既存の`tools=[PYTHON_REPL_TOOL]`を`tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL]`に拡張する。

### 2.7 `_build_task_scope_context`の修正（BL-035直接対応）

**問題**: 現行の`_build_task_scope_context`は`state["current_phase"]["tasks"]`のみを走査し、フェーズ横断の`depends_on`参照を解決できない。

**修正方針**: R3aで読み取りツールを導入するが、プロンプトに渡すコンテキスト（`verified_facts_json`）も改善する。走査対象を`state["current_phase"]["tasks"]`から`state["phases"]`全体に拡張する。

```python
def _build_task_scope_context(state, conn):
    current_task = _get_current_task(state)
    current_task_json = json.dumps(current_task, ensure_ascii=False, indent=2) if current_task else "(タスク未確定)"

    depends_on_task_ids = current_task.get("depends_on", [])
    dependency_variable_names = []
    # BL-035修正: 全フェーズを走査して依存タスクのowns_variablesを解決
    for phase in state.get("phases", []):
        for t in phase.get("tasks", []):
            if t.get("task_id") in depends_on_task_ids:
                dependency_variable_names.extend(t.get("owns_variables", []))

    verified_facts_rows = get_verified_facts_from_db(conn, state["run_id"], dependency_variable_names) if dependency_variable_names else []
    verified_facts_json = json.dumps(verified_facts_rows, ensure_ascii=False, indent=2) if verified_facts_rows else "(依存タスクの確定値はまだありません)"

    # ... (残りは既存と同一)
```

### 2.8 R3a完了条件

| # | 条件 | 検証方法 |
|---|------|----------|
| R3a-T1 | `verified_facts`テーブルに`reason`/`citations`/`confidence`列が追加されること | `python -c "import sqlite3; conn=sqlite3.connect('cela.db'); print(conn.execute('PRAGMA table_info(verified_facts)').fetchall())"` |
| R3a-T2 | `upsert_verified_fact`が`reason`/`citations`/`confidence`を保存すること | オフラインスモークテスト |
| R3a-T3 | `read_verified_fact`ツールがフェーズ横断の確定値を返すこと | オフラインスモークテスト |
| R3a-T4 | `read_deliverable_file`ツールが`log/`配下のファイルを読み取れること | オフラインスモークテスト |
| R3a-T5 | `_build_task_scope_context`が全フェーズを走査すること | ユニットテスト（フェーズ横断参照） |
| R3a-T6 | BL-035/036/037と同一構成での再ドライランで財務・需要数値ドリフトが解消されること | 実LLMドライラン |

---

## 3. R3b: 自律的DB書き込みへの移行（F-3.1〜F-3.7）

### 3.1 `write_agreement_tool`の定義（F-3.1）

要件定義書4.2の`agreements`フルスキーマに準拠したJSONスキーマを持つツールを定義する。設計書v7 §3.2準拠。

```python
WRITE_AGREEMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "write_agreement",
        "description": (
            "Save a decision, directive, or deliverable to the agreements database. "
            "Always separate What (decision_what) and Why (reason_why). "
            "For numeric claims, include Python REPL verification results in evidence (F-2.6). "
            "Expert can only use status='Proposed'. "
            "User AI can use all statuses. "
            "Detector/Reviewer/Arbiter can only use status='Rejected'."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["CREATE", "UPDATE", "SUPERSEDE"]
                },
                "status": {
                    "type": "string",
                    "enum": ["Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"]
                },
                "topic": {"type": "string", "description": "Brief heading"},
                "decision_what": {"type": "string", "description": "What was decided/proposed"},
                "reason_why": {"type": "string", "description": "Why adopted or rejected"},
                "evidence": {"type": "string", "description": "Objective evidence (F-2.6: include Python REPL results for numeric claims)"},
                "entry_type": {
                    "type": "string",
                    "enum": ["Decision", "Directive", "Deliverable"]
                },
                "phase_id": {"type": "string"},
                "task_id": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
                "resource_claims": {"type": "object"},
                "target_topic": {"type": "string", "description": "For UPDATE: the topic to update"}
            },
            "required": ["action_type", "status", "topic", "decision_what", "reason_why", "entry_type"]
        }
    }
}
```

### 3.2 システム最終フィルター（F-3.2）

`write_agreement_tool`のツール呼び出し実装自体にバリデーションを埋め込む（設計書v7 §3.2.1準拠）。独立LangGraphノードは追加しない。

```python
def _write_agreement_impl(args: dict, conn, run_id: str, caller_role: str) -> dict:
    """[F-3.2] write_agreement_toolの実体。バリデーション→権限チェック→SQLiteコミット"""
    # 1. 構造チェック
    required = ["action_type", "status", "topic", "decision_what", "reason_why", "entry_type"]
    missing = [f for f in required if not args.get(f)]
    if missing:
        return {"success": False, "error": f"必須フィールドが不足: {missing}"}

    # 2. enum値チェック
    valid_actions = {"CREATE", "UPDATE", "SUPERSEDE"}
    valid_statuses = {"Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"}
    valid_entries = {"Decision", "Directive", "Deliverable"}
    if args["action_type"] not in valid_actions:
        return {"success": False, "error": f"不正なaction_type: {args['action_type']}"}
    if args["status"] not in valid_statuses:
        return {"success": False, "error": f"不正なstatus: {args['status']}"}
    if args["entry_type"] not in valid_entries:
        return {"success": False, "error": f"不正なentry_type: {args['entry_type']}"}

    # 3. 権限チェック（呼び出し元ロール×要求statusのホワイトリスト）
    perm_error = _check_write_permission(args, caller_role)
    if perm_error:
        return {"success": False, "error": perm_error}

    # 4. depends_onリレーション整合性チェック
    if args.get("depends_on"):
        for dep_id in args["depends_on"]:
            exists = conn.execute(
                "SELECT 1 FROM agreements WHERE id=? AND run_id=?", (dep_id, run_id)
            ).fetchone()
            if not exists:
                return {"success": False, "error": f"depends_onに存在しないID: {dep_id}"}

    # 5. コミット
    _commit_agreement_from_tool(args, conn, run_id, caller_role)
    return {"success": True, "message": "DB update successful"}

def _check_write_permission(args, caller_role):
    """[F-3.2] 権限チェック: ApprovedはUser AIのみ、Rejectedは差し戻し権限4ノード"""
    status = args.get("status")
    if status == "Approved":
        if caller_role != "user":
            return f"ApprovedはUser AIのみ書き込めます（呼び出し元: {caller_role}）"
    elif status == "Rejected":
        allowed = {"user", "detector", "reviewer", "arbiter"}
        if caller_role not in allowed:
            return f"Rejectedは{allowed}のいずれかのみ書き込めます（呼び出し元: {caller_role}）"
    return None
```

### 3.3 ツールループへの統合

R2で確立した`TOOL_DISPATCH`パターンに従い、`write_agreement`を追加する。

```python
TOOL_DISPATCH = {
    "python_repl": _run_python_repl,
    "read_verified_fact": lambda args: _read_verified_fact(args, get_active_conn(), _CURRENT_RUN_ID),
    "read_deliverable_file": _read_deliverable_file,
    "write_agreement": lambda args: _write_agreement_impl(args, get_active_conn(), _CURRENT_RUN_ID, _CURRENT_CALLER_ROLE),
}
```

**注意**: `write_agreement`は`caller_role`を必要とする。`_CURRENT_CALLER_ROLE`をモジュールレベル変数として、各ノード関数の`query_AI`呼び出し前にセットする。

### 3.4 各ノードへのツール付与とcaller_role設定

| ノード | write_agreement付与 | 許可status | caller_role |
|--------|---------------------|------------|-------------|
| Expert | ✅ | Proposedのみ | "expert" |
| User AI | ✅ | 全status | "user" |
| Detector | ✅（★v3b追加） | Rejectedのみ | "detector" |
| Reviewer | ✅（★v3b追加） | Rejectedのみ | "reviewer" |
| Arbiter | ✅（★v3b追加） | Rejectedのみ | "arbiter" |

**呼び出し側の変更**: 各ノード関数で`query_AI`を呼ぶ前に`global _CURRENT_CALLER_ROLE; _CURRENT_CALLER_ROLE = "expert"`のようにロールを設定する。

### 3.5 `decision_extractor_node`の位置づけ変更（設計書v7 §3.3準拠）

- `decision_extractor_node`は**撤廃しない**
- ただし「各役割のAIが自身でツールを書き出すのが基本経路」とする
- `decision_extractor_node`は「書き漏れ時の予備的セーフティネット」として維持
- 各ターンで`write_agreement`が一度も呼ばれない場合のみ、`decision_extractor_node`を発火させる

**実装方針**:
- 既存の`decision_extractor_node`のロジックは変更しない
- 各ノード（Expert/User AI/Detector/Reviewer/Arbiter）の`query_AI`呼び出し時に`write_agreement`ツールを付与し、AIが自律的に書き込む
- `decision_extractor_node`は現在と同じタイミングで発火し、ツール呼び出しが行われなかった会話ターンを事後的に補完する

### 3.6 Reason記載の強制粒度（BL-037対応）

R3bで実装するツール呼び出し時に、プロンプトに以下の指示を追加する：

- `write_agreement`の`reason_why`には、(1)前提条件、(2)出典・根拠、(3)却下した代替案（あれば）を含めること
- 「暫定値として進めた」ことは正当な理由として認められる（F-3.9準拠）
- 計算過程の中間仮定（ルート距離・所要時間等）は、`owns_variables`に含まれる場合のみ個別Decisionとして追跡する

### 3.7 R3b完了条件

| # | 条件 | 検証方法 |
|---|------|----------|
| R3b-T1 | `write_agreement`ツールが`TOOL_DISPATCH`に登録されること | `python -c "from cela_main import TOOL_DISPATCH; assert 'write_agreement' in TOOL_DISPATCH"` |
| R3b-T2 | Expertが`Proposed`以外のstatusを書き込めないこと | オフラインスモークテスト |
| R3b-T3 | Detector/Reviewer/Arbiterが`Rejected`のみ書き込めること | オフラインスモークテスト |
| R3b-T4 | User AIが全statusを書き込めること | オフラインスモークテスト |
| R3b-T5 | `decision_extractor_node`が引き続き正常に動作すること | 既存テスト回帰 |
| R3b-T6 | 指標A（却下案の回避率）: 同じ制約に再度ぶつかったタスクで、AIが既に却下された案を再提案しないこと | 実LLMドライラン |
| R3b-T7 | 指標E（自律書き込みカバレッジ80%以上、取りこぼし率20%以下） | 実LLMドライランログ解析 |
| R3b-T8 | 指標F（Rejected自律書き込みの正確性）: 4ノードすべてで明示的な却下事案に`Rejected`書き込みが発生すること | 実LLMドライランログ解析 |

---

## 4. 既知の制約とリスク

| 項目 | 内容 | 対応 |
|------|------|------|
| BL-011 | OpenRouter経由の複数バックエンドでのFunction Calling対応が未検証 | R3a/R3bの新ツールも同様のリスク。MVP後の網羅検証に委ねる（D-010準拠） |
| BL-005 | `turn_count`凍結によりreflection/facilitatorが発火不能 | R3のスコープ外（R4着手時にまとめて対応） |
| BL-017 | 差し戻しループ沼からの脱出機構 | R3のスコープ外（R4着手時にまとめて対応） |
| BL-021 | プロンプト自体の英語化 | R3のスコープ外 |
| `_CURRENT_RUN_ID` | ツールハンドラからDB接続・run_idを参照するためのモジュールレベル変数 | `_query_AI_live`内で`TOOL_DISPATCH`を呼ぶ前にセットする必要がある。現在の`_query_AI_live`には`run_id`パラメータがないため、拡張が必要 |
| `_CURRENT_CALLER_ROLE` | `write_agreement`の権限チェックに必要な呼び出し元ロール | 各ノード関数で`query_AI`呼び出し前にグローバル変数をセットする |

---

## 5. 実装順序（推奨）

### Step 1: R3a スキーマ変更
- `verified_facts`テーブルに`reason`/`citations`/`confidence`列を追加（`init_db`内でALTER TABLE）
- `upsert_verified_fact`のシグネチャ拡張
- `get_verified_facts_from_db`のトピック検索対応

### Step 2: R3a 読み取りツール定義
- `READ_VERIFIED_FACT_TOOL` / `READ_DELIVERABLE_FILE_TOOL`の定義
- `_read_verified_fact` / `_read_deliverable_file`のハンドラ実装
- `TOOL_DISPATCH`への登録

### Step 3: R3a `_build_task_scope_context`修正（BL-035）
- 走査対象を`state["phases"]`全体に拡張

### Step 4: R3a ツール付与
- Expert/User AI/Detector/Reviewer/Integratorの`tools`リストに読み取りツールを追加
- `query_AI`/`_query_AI_live`に`run_id`パラメータを追加（ツールハンドラからのDB参照用）

### Step 5: R3a 検証
- `python -m py_compile`構文確認
- オフラインスモークテスト（フェーズ横断参照、ファイル読み取り）

### Step 6: R3b `write_agreement`ツール定義
- `WRITE_AGREEMENT_TOOL`の定義
- `_write_agreement_impl` / `_check_write_permission` / `_commit_agreement_from_tool`の実装
- `TOOL_DISPATCH`への登録

### Step 7: R3b ツール付与とcaller_role設定
- 全ノードへの`write_agreement`ツール付与
- `_CURRENT_CALLER_ROLE`グローバル変数の導入
- 各ノード関数で`query_AI`呼び出し前のロール設定

### Step 8: R3b 検証
- `python -m py_compile`構文確認
- オフラインスモークテスト（権限チェック、構造チェック）

### Step 9: 統合ドライラン
- R3a+R3b適用後の実LLMドライラン
- BL-035/036/037の解消確認
- 指標A/E/Fの実測

---

## 6. 変更対象ファイル一覧

| ファイル | 変更内容 |
|----------|----------|
| `cela_main.py` | verified_factsスキーマ拡張、upsert/get関数拡張、読み取りツール定義・ハンドラ、write_agreementツール定義・ハンドラ、TOOL_DISPATCH更新、各ノードのtoolsリスト更新、`_build_task_scope_context`修正、`_query_AI_live`へのrun_idパラメータ追加、`_CURRENT_CALLER_ROLE`グローバル変数 |
| `docs/design/r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md` | R3a/R3b該当節の追記（§3.2〜3.4.1にR3a読み取りツールの記述を追加） |
| `docs/design/phase_gates.md` | P3a-1〜P3a-4、P3b-1〜P3b-2の状態更新 |
| `docs/design/STATUS.md` | アクティブPhase・次アクション更新 |