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

**付与対象**（★レビュー反映: Resource Arbiterを追加し、R3bの書き込みツール付与対象と一致させた。読み書き両方が必要なノードに非対称な付与をしない方針、§0参照）:
- Expert（F-3.8: フェーズ横断の確定値参照、BL-035解消）
- User AI（F-3.8: 承認済み根拠の確認、BL-036解消）
- Detector（F-3.8: 過去の決定の理由を遡って検証、BL-037解消）
- Reviewer（F-3.8: 最終成果物の根拠確認）
- Integrator（F-3.8: 統合時の横断矛盾チェック）
- Resource Arbiter（F-3.8: 予算・資源判断の際にフェーズ横断の確定値を参照、★追加）

**呼び出し側の変更**:
- Expert（`call_expert`）・User AI（`generate_user_utterance`）・Detector（`call_detector`）・Reviewer（`call_reviewer`）・Resource Arbiter（`call_resource_arbiter`）は、既存の`tools=[PYTHON_REPL_TOOL]`を`tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL]`に拡張する（この5ノードは現状すでに`tools=[PYTHON_REPL_TOOL]`を持つ、`cela_main.py:1638,1763,2055,2285,2461/2466`）。
- **Integrator（`call_integrator`、`cela_main.py:2190`）は現状`tools`パラメータ自体を持たない**唯一のノードである。「既存リストの拡張」ではなく、`query_AI`呼び出しに`tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL]`を新規追加する（Integratorにpython_replも同時に付与することになるが、既存ノードとの一貫性を優先しF-2.6検算ゲートの対象に含める）。

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
| R3a-T4 | `read_deliverable_file`ツールが`log/`配下のファイルを読み取れること（実際のWindowsパス区切り、`..`によるトラバーサル拒否の両方を試験、★致命的③対応） | オフラインスモークテスト |
| R3a-T5 | `_build_task_scope_context`が全フェーズを走査すること | ユニットテスト（フェーズ横断参照） |
| R3a-T6 | Integrator・Resource Arbiterの`query_AI`呼び出しに読み取りツールが付与されていること（★レビュー反映、非対称付与の解消確認） | オフラインスモークテスト |
| R3a-T7 | `TOOL_DISPATCH`のディスパッチ処理が`args`辞書全体をハンドラへ渡すこと（★致命的①対応、R3a全体の前提） | オフラインスモークテスト（§1.5.2 R0-T2と同一） |
| R3a-T8 | BL-035/036/037と同一構成での再ドライランで財務・需要数値ドリフトが解消されること | 実LLMドライラン |

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
            "Detector/Reviewer/Arbiter/Integrator can only use status='Rejected'."
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
                "target_topic": {"type": "string", "description": "For UPDATE: the topic to update"},
                "confirmed_variables": {
                    "type": "array",
                    "description": (
                        "Optional. [F-3.9] If this decision confirms one or more values that belong to the "
                        "current task's owns_variables, list them here. Each entry is saved to the structured "
                        "fact store (verified_facts) with its reason and confidence, independent of whether "
                        "decision_extractor_node runs this turn. confidence='provisional' is a fully legitimate "
                        "value — it means 'proceeded with this value for now', not 'this is unverified/wrong'."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable_name": {"type": "string", "description": "Must match one of the current task's owns_variables"},
                            "value": {"type": "string"},
                            "unit": {"type": "string", "default": ""},
                            "confidence": {"type": "string", "enum": ["confirmed", "provisional"], "default": "confirmed"}
                        },
                        "required": ["variable_name", "value"]
                    }
                }
            },
            "required": ["action_type", "status", "topic", "decision_what", "reason_why", "entry_type"]
        }
    }
}
```

**★スキーマ追加の理由（レビュー指摘の修正）**: 初版はF-3.9の`confidence`（confirmed/provisional）区別を「`reason_why`に自由記述で書けばF-3.9準拠」と説明していたが、これでは機械可読な区別が`agreements`側で失われ、F-3.9が目指した「後で状況が変わった際に`provisional`な値だけを再検討対象として引ける」という設計意図（決定理由書D-035参照）を実現できない。`confirmed_variables`を独立したフィールドとして追加し、`_write_agreement_impl`内で`upsert_verified_fact`へ直接渡すことで、`agreements.reason_why`の自由記述と`verified_facts.confidence`の構造化区別を両立させる。

### 3.2 システム最終フィルター（F-3.2）

`write_agreement_tool`のツール呼び出し実装自体にバリデーションを埋め込む（設計書v7 §3.2.1準拠）。独立LangGraphノードは追加しない。

```python
def _write_agreement_impl(args: dict, conn, run_id: str, caller_role: str, task_id: str = "") -> dict:
    """[F-3.2] write_agreement_toolの実体。バリデーション→権限チェック→SQLiteコミット→確定値反映"""
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

    # 3. 権限チェック（呼び出し元ロール×要求statusのホワイトリスト、★修正: 全status×全ロールを網羅）
    perm_error = _check_write_permission(args, caller_role)
    if perm_error:
        return {"success": False, "error": perm_error}

    # 4. depends_onリレーション整合性チェック
    #    ★注意（レビュー指摘⑤）: ここで検証するIDは_build_agreements_context側で
    #    LLMに露出済みであることが前提（§3.2.1参照）。露出していないID空間を検証しても
    #    LLMは正しい値を書けない。
    if args.get("depends_on"):
        for dep_id in args["depends_on"]:
            exists = conn.execute(
                "SELECT 1 FROM agreements WHERE id=? AND run_id=?", (dep_id, run_id)
            ).fetchone()
            if not exists:
                return {"success": False, "error": f"depends_onに存在しないID: {dep_id}"}

    # 5. コミット
    _commit_agreement_from_tool(args, conn, run_id, caller_role)

    # 6. ★新規（レビュー指摘②の修正）: confirmed_variablesをverified_factsへ反映。
    #    decision_extractor_nodeのowned_variable_values抽出（cela_main.py:2798-2808）が
    #    「write_agreementが呼ばれなかったターンのみ」発火する予備的セーフティネットに
    #    なる（§3.5）以上、write_agreementの側にも同等の確定値保存経路がなければ、
    #    R3bの採用が進むほどverified_factsが更新されなくなりR3aの効果が消える（致命的②）。
    #    write_agreementが呼ばれた場合は、ここが確定値保存の一次経路になる。
    for cv in args.get("confirmed_variables", []) or []:
        var_name = cv.get("variable_name")
        if not var_name:
            continue
        upsert_verified_fact(
            conn, run_id, var_name, cv.get("value"), unit=cv.get("unit", ""),
            source_task_id=task_id, source_phase_id=args.get("phase_id", ""),
            confirmed_by=caller_role,
            reason=args.get("reason_why", ""),
            citations=[args.get("topic", "")],
            confidence=cv.get("confidence", "confirmed"),
        )

    return {"success": True, "message": "DB update successful"}

def _check_write_permission(args, caller_role):
    """[F-3.2] 権限チェック: ロール×status許可表を全組み合わせで判定する（★修正）。

    旧実装はApproved/Rejectedの2値しか判定しておらず、例えばExpertが
    Approved_with_Conditions/Implicitly_Acceptedで書き込んでも、Detector/Reviewer/
    Arbiter/IntegratorがProposedで書き込んでもブロックされない欠陥があった
    （レビュー指摘④）。全5 statusについて、ロールごとの許可集合を明示する。
    """
    ALLOWED_STATUS_BY_ROLE = {
        "expert": {"Proposed"},
        "user": {"Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"},
        "detector": {"Rejected"},
        "reviewer": {"Rejected"},
        "arbiter": {"Rejected"},
        "integrator": {"Rejected"},  # ★追加: R3bでIntegratorにもwrite_agreementを付与するため
    }
    status = args.get("status")
    allowed = ALLOWED_STATUS_BY_ROLE.get(caller_role, set())
    if status not in allowed:
        return f"{caller_role}はstatus='{status}'を書き込めません（許可: {sorted(allowed)}）"
    return None
```

**注記（Integratorの許可statusについて）**: Integratorは既存コードでは`decisions`テーブルへ「矛盾検知」を直接ログする専用経路（`cela_main.py:3086`、`make_decision`＋`db_append_decision`）を持ち、`agreements`への書き込み経路は今回のR3bで初めて持つことになる。役割上はDetector/Reviewer/Arbiterと同じ「横断的な矛盾の指摘」であるため、他の3ロールと同様`Rejected`のみを許可する設計とした。Integratorに他のstatusを許可する具体的なユースケースが出てきた場合は、この許可表を個別に見直す。

### 3.2.1 `depends_on`が参照するIDのLLMへの露出（★新規、レビュー指摘⑤）

**問題**: `_write_agreement_impl`は`depends_on`内の各IDを`agreements.id`（`AG-{timestamp}`形式、`decision_extractor_node`/`write_agreement`がコミット時にサーバー側で自動生成、`cela_main.py:2865`等）に対して検証する。しかし、既存の`_build_agreements_context`（`cela_main.py:1208-1269`）がプロンプトに出力する各行は`{icon}{type_label} {clean_topic}: {content_preview}`のみで、**`id`フィールドを一切含まない**。LLMは存在すら知らないIDを`depends_on`に指定することはできず、このままでは`depends_on`は実質的に常に空配列でしか使われない。

**修正内容**: `_build_agreements_context`の出力行の先頭に`id`を追記し、LLMが`depends_on`にどのIDを指定すればよいか本文中から読み取れるようにする。

```python
# cela_main.py:1267付近、_build_agreements_context内
lines.append(f"[{a.get('id', '?')}] {icon}{type_label} {clean_topic}: {content_preview}")
```

既存の呼び出し元（Hydrateコンテキスト等）は文字列をそのまま人間可読なプロンプトとして使っているだけで、`id`プレフィックスの追加によって既存の解析ロジックが壊れる箇所はない（`_build_agreements_context`の戻り値をパースして再利用している箇所は現状なし、要件定義書4.2のAgreement表示仕様にも反しない）。

### 3.2.2 ツール結果の二重JSONエンコード（★新規、R3b実装レビューで発見。R3aにも遡って影響）

**✅ 修正実装済み（2026-07-21、Claude Sonnet 5が直接修正）**: `_read_verified_fact_handler`・`_read_deliverable_file_handler`・`_write_agreement_impl`を生のdict/list/str返却へ変更し、`_query_AI_live`のwrite_agreement成功判定も`_safe_json_parse`を経由しない直接判定に簡略化した。オフラインスモークテストで、`json.dumps`一回で正しく復元できることを確認済み。

**問題**: `_query_AI_live`のツールループ末尾（`cela_main.py:1056-1059`）は、`python_repl`を含む全ツールの結果を無条件で`json.dumps(result, ensure_ascii=False)`してから`loop_messages`（LLMへの`role: "tool"`メッセージ）に積む。

```python
loop_messages.append({
    "role": "tool", "tool_call_id": tc.id,
    "content": json.dumps(result, ensure_ascii=False),
})
```

`python_repl`の`result`は`repl_session.run(...)`が返す**素の文字列**なので、ここで1回だけJSONエンコードされ問題ない。しかし、`_read_verified_fact_handler`・`_write_agreement_impl`・`_read_deliverable_file_handler`のエラー/not_found分岐は、ハンドラ自身の内部で**既に`json.dumps(...)`された文字列**を返している。その結果、末尾の`json.dumps(result, ...)`が**二重にJSONエンコード**してしまい、LLMに渡る`content`は以下のように、本来のJSONオブジェクトではなく「JSON文字列を表すJSON文字列」というエスケープまみれの値になる。

```python
>>> handler_result = '{"success": true, "message": "DB update successful"}'  # ハンドラの戻り値（既にjson.dumps済み）
>>> json.dumps(handler_result, ensure_ascii=False)  # 末尾でさらにエンコード
'"{\\"success\\": true, \\"message\\": \\"DB update successful\\"}"'
```

実機で`read_verified_fact`・`write_agreement`を呼び出して確認したところ、この二重エンコードを再現した（本セッションでのオフライン検証）。LLMが誤読する可能性は低くないが、少なくとも意図通りのクリーンなJSON構造ではなく、ツールの`description`が約束する形と食い違う。**R3aの`read_verified_fact`/`read_deliverable_file`にも既に存在する不具合**であり、R3aレビュー時点（本ドキュメントの§2.4.3レビュー）ではハンドラの戻り値を直接呼び出すオフラインテストしか行っておらず、`_query_AI_live`の末尾処理まで通した検証をしていなかったため見落としていた。

**修正方針**: 各ハンドラは`json.dumps(...)`済みの文字列ではなく、**素のPythonオブジェクト（dict、または`read_deliverable_file`成功時のようなプレーン文字列）を返す**ように統一する。JSONへの変換は`_query_AI_live`末尾の1箇所（`json.dumps(result, ...)`）だけで行う。

- `_read_verified_fact_handler`: `return {"status": "not_found", "message": "..."}` / `return results`（すでにdictのリスト。`json.dumps`しない）
- `_write_agreement_impl`: 全ての`return json.dumps({...}, ...)`を`return {...}`（生dict）に変更
- `_read_deliverable_file_handler`: エラー/not_found分岐を`return {"status": "error", "message": "..."}`に変更（成功時の`return content[:10000]`はプレーン文字列のままでよい、変更不要）
- `_query_AI_live`内、`write_agreement`成功判定（§3.5.1）も単純化できる: `result`が既に生dictになるため、`_safe_json_parse(result, fallback={})`を挟まず`if isinstance(result, dict) and result.get("success"):`で直接判定してよい

### 3.2.3 `write_agreement`経由のDeliverable保存処理の欠落（★新規、R3b実装レビューで発見。本計画書§3.1〜3.2自体の記述漏れ）

**問題**: `decision_extractor_node`（既存コード、`cela_main.py`旧2810-2860行目付近）には、`entry_type=="Deliverable"`の場合に本文を`save_deliverable_to_file`でファイル保存し`decision_what`に`FILE_PATH:{filepath}`というポインタを格納する処理と、UPDATE時に短い要約でファイルパスを上書きしないための保護処理（「🛡️ ファイル上書き防止の鉄壁の保護」ブロック）が存在する。

しかし、本計画書§3.1（`WRITE_AGREEMENT_TOOL`定義）・§3.2（`_write_agreement_impl`/`_commit_agreement_from_tool`）は、Deliverableのファイル保存について**一度も言及していなかった**。実装（`_commit_agreement_from_tool`）はこの欠落をそのまま反映し、`args.get("decision_what", "")`を無条件でそのまま`agreements.decision_what`列にINSERTしている。実機検証の結果、`write_agreement`で`entry_type="Deliverable"`・`action_type="CREATE"`・500文字の本文を送信したところ、**ファイルには一切保存されず、生の本文がSQLiteの`decision_what`列に直接格納される**ことを確認した。

これはBL-034（Deliverableがユーザー承認前にファイル保存される問題）とは別の、むしろ逆方向の問題である。R3bの目的は「Expert自身が能動的にAgreement DBへ書き込む」ことであり、Expertは`write_agreement`で`status="Proposed"`かつ`entry_type="Deliverable"`を書ける唯一のロールなので、**R3b運用開始後、Deliverableの大半がこの未対応の経路を通ることになる**。放置すると、(a) 成果物本文がファイルではなくDBに直接蓄積されデータベース肥大化・既存のファイルベース運用との不整合を招く、(b) `_build_agreements_context`の`FILE_PATH:`判定（「(ファイルに出力済み: ...)」表示）が機能せず生本文がそのままプレビュー表示される、という実害が出る。

**修正方針**: `_commit_agreement_from_tool`に、`decision_extractor_node`の既存ロジックと同等のDeliverable処理を追加する。

```python
def _commit_agreement_from_tool(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str) -> None:
    entry_type = args.get("entry_type", "Decision")
    action_type = args.get("action_type", "CREATE")
    topic = args.get("topic", "")
    raw_content = args.get("decision_what", "")
    content = raw_content

    # ★新規: Deliverableのファイル保存（decision_extractor_nodeの既存ロジックを移植）
    if entry_type == "Deliverable" and action_type == "CREATE":
        if len(raw_content) > 200:
            filepath = save_deliverable_to_file(topic, raw_content)
            content = f"FILE_PATH:{filepath}"
        # 200文字未満はそのまま短文として保存（decision_extractor_node同様、
        # write_agreementの場合はstate["expert_output"]のような代替バックアップ元がないため
        # raw_contentをそのまま使う。Expertは本文をdecision_whatに直接渡す前提のため
        # 極端に短い成果物は想定薄いが、念のためraw_contentへのフォールバックとする）

    if action_type == "SUPERSEDE":
        ...  # 既存のまま

    if action_type == "UPDATE":
        target_topic = args.get("target_topic", topic)
        old_content = ""
        for a in reversed(get_agreements_from_db(conn, run_id)):
            if a["topic"] == target_topic and a.get("status") != "Superseded":
                old_content = a["decision_what"]
                db_supersede_agreement(a["id"], conn, run_id)
                break
        # ★新規: ファイル上書き防止（decision_extractor_nodeの既存ロジックを移植）
        if entry_type == "Deliverable" and old_content.startswith("FILE_PATH:"):
            if not content or (not content.startswith("FILE_PATH:") and len(content) < 200):
                content = old_content
            elif not content.startswith("FILE_PATH:") and len(content) >= 200:
                filepath = save_deliverable_to_file(target_topic, content)
                content = f"FILE_PATH:{filepath}"

    # 以降、INSERT INTO agreements ... は content（raw_contentではない）を使う
```

**完了条件（追加）**: `write_agreement`で`entry_type="Deliverable"`・200文字超の`decision_what`を送信した際、`log/.../deliverables/`配下にファイルが生成され、`agreements.decision_what`が`FILE_PATH:`で始まることをオフラインスモークテストで確認する。

### 3.3 ツールループへの統合

R2で確立した`TOOL_DISPATCH`パターンに従い、`write_agreement`を追加する。`_write_agreement_impl`は§3.2の修正で`task_id`引数を追加したため、`_CURRENT_TASK_ID`もモジュールレベル変数として束縛する。

```python
TOOL_DISPATCH = {
    "python_repl": _run_python_repl,
    "read_verified_fact": lambda args: _read_verified_fact(args, get_active_conn(), _CURRENT_RUN_ID),
    "read_deliverable_file": _read_deliverable_file,
    "write_agreement": lambda args: _write_agreement_impl(
        args, get_active_conn(), _CURRENT_RUN_ID, _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    ),
}
```

**注意**: `write_agreement`は`caller_role`と`task_id`（confirmed_variablesの`source_task_id`用）を必要とする。`_CURRENT_CALLER_ROLE`・`_CURRENT_TASK_ID`をモジュールレベル変数として、各ノード関数の`query_AI`呼び出し前にセットする（`_CURRENT_TASK_ID`は`state["current_task_id"]`から取得できるノードではそれを、取得できないノード（Integrator等、現在タスクという概念を持たない）では空文字のままにする）。

### 3.4 各ノードへのツール付与とcaller_role設定

| ノード | write_agreement付与 | 許可status | caller_role |
|--------|---------------------|------------|-------------|
| Expert | ✅ | Proposedのみ | "expert" |
| User AI | ✅ | 全status | "user" |
| Detector | ✅（★v3b追加） | Rejectedのみ | "detector" |
| Reviewer | ✅（★v3b追加） | Rejectedのみ | "reviewer" |
| Arbiter | ✅（★v3b追加） | Rejectedのみ | "arbiter" |
| Integrator | ✅（★レビュー反映で追加） | Rejectedのみ | "integrator" |

**★レビュー反映**: 初版はIntegratorをこの表から漏らしており、R3a（読み取り）ではIntegratorに付与しR3b（書き込み）では付与しない、逆にArbiterはR3aで付与せずR3bでのみ付与するという非対称な状態になっていた。読み書き両ツールが必要なノードには両方を付与する方針（§0）に統一し、IntegratorをR3bにも追加した。

**呼び出し側の変更**:
- Expert/User AI/Detector/Reviewer/Arbiterは既存の`tools=[PYTHON_REPL_TOOL, ...]`（R3aで拡張済み）に`WRITE_AGREEMENT_TOOL`を追加する。
- **Integrator（`call_integrator`）はR3aで新規に`tools`パラメータを追加済み**（§2.6参照）なので、そのリストに`WRITE_AGREEMENT_TOOL`も含める。
- 各ノード関数で`query_AI`を呼ぶ前に`global _CURRENT_CALLER_ROLE; _CURRENT_CALLER_ROLE = "expert"`のようにロールを設定する。Integratorの場合は`"integrator"`を設定する。

### 3.5 `decision_extractor_node`の位置づけ変更（設計書v7 §3.3準拠）

- `decision_extractor_node`は**撤廃しない**
- ただし「各役割のAIが自身でツールを書き出すのが基本経路」とする
- `decision_extractor_node`は「書き漏れ時の予備的セーフティネット」として維持
- 各ターンで`write_agreement`が一度も呼ばれない場合のみ、`decision_extractor_node`のAgreement抽出（`extracted_items`のDB書き込み）を発火させる
- **ただし`verified_facts`への確定値保存（`owned_variable_values`抽出、`cela_main.py:2798-2808`）は、`write_agreement`が呼ばれたかどうかに関わらず引き続き毎ターン実行する**（★レビュー指摘②の修正）。理由: `write_agreement`の`confirmed_variables`（§3.1）は呼び出し側のAIが明示的に指定した場合のみ`verified_facts`を更新するため、AIが`confirmed_variables`を指定し忘れた場合の保険として、既存の`decision_extractor_node`によるverified_facts抽出は独立した経路として残す必要がある。これにより「`write_agreement`の採用率が上がるほど`verified_facts`が更新されなくなる」という自己矛盾（致命的②）を避ける。

**実装方針**:
- 既存の`decision_extractor_node`のロジックのうち、Agreement/Decisionの書き込み部分は「`write_agreement`が呼ばれなかった場合のみ」に条件分岐するが、`owned_variable_values`→`upsert_verified_fact`の部分（2798-2808行目）は条件分岐せず現状のまま毎ターン実行する
- 各ノード（Expert/User AI/Detector/Reviewer/Arbiter/Integrator）の`query_AI`呼び出し時に`write_agreement`ツールを付与し、AIが自律的に書き込む
- `decision_extractor_node`は現在と同じタイミングで発火し、ツール呼び出しが行われなかった会話ターンを事後的に補完する

### 3.5.1 「今ターン`write_agreement`が呼ばれたか」の検知機構（★新規、レビュー指摘G4）

**問題**: §3.5は「`write_agreement`が呼ばれなかった場合のみAgreement書き込みを行う」という意図は明記していたが、**その検知手段を具体的に与えていなかった**。この欠落により、実装時に何を条件にすればよいか判断できず、`decision_extractor_node`側の条件分岐が実装されない事態を招いた（本節はこの欠落そのものの修正）。

**修正内容**: BL-033で導入済みの`_LAST_PYTHON_CALLS`/`get_last_python_calls()`（`query_AI()`呼び出しのたびにリセットされ、ツールループ内で蓄積されるモジュールレベルの記録）と全く同じパターンを踏襲する。

```python
# query_AI()冒頭、_LAST_PYTHON_CALLS = [] のすぐ隣でリセットする
_LAST_WRITE_AGREEMENT_SUCCEEDED = False


def get_last_write_agreement_succeeded() -> bool:
    """[R3b] 直前のquery_AI呼び出しのツールループ内で、write_agreementが
    1回でも成功したか（success=Trueで返ったか）を返す。"""
    return _LAST_WRITE_AGREEMENT_SUCCEEDED


# query_AI()内、_LAST_PYTHON_CALLS = [] と同じ場所に追加
def query_AI(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None):
    global _call_seq_counter, _LAST_PYTHON_CALLS, _LAST_WRITE_AGREEMENT_SUCCEEDED
    _LAST_PYTHON_CALLS = []
    _LAST_WRITE_AGREEMENT_SUCCEEDED = False
    ...


# _query_AI_liveのツールループ、else分岐（result = handler(args)の直後）
result = handler(args)
if tc.function.name == "write_agreement" and isinstance(result, dict) and result.get("success"):
    global _LAST_WRITE_AGREEMENT_SUCCEEDED
    _LAST_WRITE_AGREEMENT_SUCCEEDED = True
```

**stateへのキャプチャ**: `_LAST_PYTHON_CALLS`が`expert_node`内で`state["expert_last_python_calls"] = get_last_python_calls()`としてキャプチャされているのと全く同じ場所・同じタイミングで、以下を追加する。

- `expert_node`（`call_expert`呼び出し直後）: `state["expert_wrote_agreement"] = get_last_write_agreement_succeeded()`
- User AIのノード（`generate_user_utterance`呼び出し直後）: `state["user_wrote_agreement"] = get_last_write_agreement_succeeded()`

**`decision_extractor_node`側の条件分岐**:

```python
# target_role判定の直後（既存の「直前の発言者が誰かを履歴の末尾から自動判定する」ブロックの後）
wrote_agreement_this_turn = (
    state.get("expert_wrote_agreement", False) if target_role == "expert"
    else state.get("user_wrote_agreement", False)
)
```

`call_decision_extractor`（LLM呼び出し自体）は`owned_variable_values`抽出のため無条件で毎ターン実行し続けるが、`extracted_items`をループして`db_append_agreement`/`db_supersede_agreement`を呼ぶブロック全体を`if not wrote_agreement_this_turn:`で囲む。`owned_variable_values`→`upsert_verified_fact`の処理（2798-2808行目）はこの条件の**外側**に置き、無条件のまま維持する。

**注意（Detector/Reviewer/Arbiter/Integratorの`write_agreement`について）**: これら4ノードは`Rejected`のみの書き込み権限であり、`decision_extractor_node`が拾う対象は「直前の発言者（Expert/User AI）のchat_history」であるため、Detector等が`write_agreement`を呼んでも`wrote_agreement_this_turn`の判定には影響しない（意図的）。Detector等のRejected書き込みは`decision_extractor_node`のセーフティネットと独立して常に有効な経路のままとする。

### 3.6 Reason記載の強制粒度（BL-037対応）

R3bで実装するツール呼び出し時に、プロンプトに以下の指示を追加する：

- `write_agreement`の`reason_why`には、(1)前提条件、(2)出典・根拠、(3)却下した代替案（あれば）を含めること
- 「暫定値として進めた」ことは正当な理由として認められる（F-3.9準拠）
- 計算過程の中間仮定（ルート距離・所要時間等）は、`owns_variables`に含まれる場合のみ個別Decisionとして追跡する

### 3.7 R3b完了条件

| # | 条件 | 検証方法 |
|---|------|----------|
| R3b-T1 | `write_agreement`ツールが`TOOL_DISPATCH`に登録されること | `python -c "from cela_main import TOOL_DISPATCH; assert 'write_agreement' in TOOL_DISPATCH"` |
| R3b-T2 | Expertが`Proposed`以外のstatusを書き込めないこと（`Approved`/`Approved_with_Conditions`/`Rejected`/`Implicitly_Accepted`すべてを個別に試験） | オフラインスモークテスト |
| R3b-T3 | Detector/Reviewer/Arbiter/Integratorが`Rejected`以外を書き込めないこと（★Integrator追加、全statusを網羅的に試験） | オフラインスモークテスト |
| R3b-T4 | User AIが全statusを書き込めること | オフラインスモークテスト |
| R3b-T5 | `decision_extractor_node`が引き続き正常に動作すること。特に`owned_variable_values`→`verified_facts`の抽出が、`write_agreement`呼び出し有無に関わらず毎ターン実行されること（★追加、致命的②の回帰確認） | 既存テスト回帰＋新規オフラインスモークテスト |
| R3b-T6 | `confirmed_variables`を指定した`write_agreement`呼び出しが`verified_facts`へ正しく反映されること（confidence='provisional'を含む） | オフラインスモークテスト（★新規） |
| R3b-T7 | `depends_on`に指定したIDが`_build_agreements_context`の出力に実際に出現していること（LLMが参照可能なIDのみを検証対象にできることの確認） | オフラインスモークテスト（★新規） |
| R3b-T8 | 指標A（却下案の回避率）: 同じ制約に再度ぶつかったタスクで、AIが既に却下された案を再提案しないこと | 実LLMドライラン |
| R3b-T9 | 指標E（自律書き込みカバレッジ80%以上、取りこぼし率20%以下） | 実LLMドライランログ解析 |
| R3b-T10 | 指標F（Rejected自律書き込みの正確性）: 5ノード（Detector/Reviewer/Arbiter/Integrator/User AI）すべてで明示的な却下事案に`Rejected`書き込みが発生すること（★Integrator追加） | 実LLMドライランログ解析 |
| R3b-T11 | `read_verified_fact`/`write_agreement`のツール結果がLLMに二重JSONエンコードされずに渡ること（§3.2.2、★新規） | オフラインスモークテスト（`json.loads`一回でdictへ復元できることを確認） |
| R3b-T12 | `write_agreement`で`entry_type="Deliverable"`・200文字超の`decision_what`を送信した際、`log/.../deliverables/`にファイルが生成され`agreements.decision_what`が`FILE_PATH:`で始まること（§3.2.3、★新規） | オフラインスモークテスト |
| R3b-T13 | `write_agreement`によるDeliverableのUPDATEで、短い要約が既存のFILE_PATHを上書きしないこと（§3.2.3のファイル上書き防止ロジック） | オフラインスモークテスト |

---

## 4. 既知の制約とリスク

| 項目 | 内容 | 対応 |
|------|------|------|
| BL-011 | OpenRouter経由の複数バックエンドでのFunction Calling対応が未検証 | R3a/R3bの新ツールも同様のリスク。MVP後の網羅検証に委ねる（D-010準拠） |
| BL-005 | `turn_count`凍結によりreflection/facilitatorが発火不能 | R3のスコープ外（R4着手時にまとめて対応） |
| BL-017 | 差し戻しループ沼からの脱出機構 | R3のスコープ外（R4着手時にまとめて対応） |
| BL-021 | プロンプト自体の英語化 | R3のスコープ外 |
| `TOOL_DISPATCH`のディスパッチ引数（★致命的①、修正済み） | `_query_AI_live`が`python_repl`以外のツールに`args.get("code","")`（空文字列）しか渡していなかった | §1.5.1で`handler(args)`に修正。R3a/R3b全ツールの前提条件 |
| `verified_facts`の更新経路の空洞化（★致命的②、修正済み） | `write_agreement`採用率が上がるほど`decision_extractor_node`のowned_variable_values抽出が発火しなくなり、verified_factsが更新されなくなる自己矛盾 | `write_agreement`に`confirmed_variables`フィールドを追加（§3.1）し、`_write_agreement_impl`内で直接`upsert_verified_fact`を呼ぶ（§3.2）。かつ`decision_extractor_node`のverified_facts抽出部分は`write_agreement`呼び出し有無に関係なく毎ターン独立実行する（§3.5、保険としての二重化） |
| `read_deliverable_file`のパス検証（★致命的③、修正済み） | `file_path.startswith("log/")`はWindows環境の実パス（バックスラッシュ区切り）を常に拒否し、かつパストラバーサルも防げない | `pathlib.Path.resolve()`＋`relative_to()`によるディレクトリ包含チェックに変更（§2.4.3） |
| `_check_write_permission`の許可表不備（★中程度④、修正済み） | Approved/Rejectedの2値しかチェックしておらず、他のstatusは全ロールに開放されていた | ロール×status全組み合わせの許可表に変更（§3.2） |
| `depends_on`のID非露出（★中程度⑤、修正済み） | LLMは`agreements.id`を一度もプロンプト中で見ないため`depends_on`を正しく指定できない | `_build_agreements_context`の各行に`id`を追記（§3.2.1） |
| `_CURRENT_RUN_ID` / `_CURRENT_CALLER_ROLE` / `_CURRENT_TASK_ID` | ツールハンドラからDB接続・run_id・呼び出し元ロール・task_idを参照するためのモジュールレベル変数 | `_query_AI_live`自体のシグネチャは変更しない（既存の`_LAST_PYTHON_CALLS`と同じ、LangGraphの単一プロセス同期実行を前提としたモジュールグローバル方式を踏襲）。各ノード関数が`query_AI`呼び出し直前にこれらのグローバル変数をセットする |

---

## 5. 実装順序（推奨）

### Step 0: 共通前提修正（★新規、最優先）
- `_query_AI_live`のツールディスパッチ処理を`handler(args.get("code", ""))`→`handler(args)`に修正（§1.5.1、致命的①）
- ダミーツールによる回帰テストで`python_repl`の既存動作に影響がないことを確認

### Step 1: R3a スキーマ変更
- `verified_facts`テーブルに`reason`/`citations`/`confidence`列を追加（`init_db`内でALTER TABLE）
- `upsert_verified_fact`のシグネチャ拡張
- `get_verified_facts_from_db`のトピック検索対応

### Step 2: R3a 読み取りツール定義
- `READ_VERIFIED_FACT_TOOL` / `READ_DELIVERABLE_FILE_TOOL`の定義
- `_read_verified_fact`のハンドラ実装
- `_read_deliverable_file`のハンドラ実装（`pathlib.Path`によるディレクトリ包含チェック、§2.4.3、致命的③）
- `TOOL_DISPATCH`への登録（Step 0修正後の`handler(args)`前提）
- `from pathlib import Path`をファイル冒頭のimportに追加

### Step 3: R3a `_build_task_scope_context`修正（BL-035）
- 走査対象を`state["phases"]`全体に拡張

### Step 4: R3a ツール付与
- Expert/User AI/Detector/Reviewer/Resource Arbiterの`tools`リストに読み取りツールを追加（既存の`tools=[PYTHON_REPL_TOOL]`を拡張）
- **Integratorの`query_AI`呼び出しに`tools`パラメータを新規追加**（現状`tools`なし、★レビュー反映）
- `_CURRENT_RUN_ID`グローバル変数を導入し、`run_ai_vs_ai_loop`冒頭でセット（`_query_AI_live`自体のシグネチャは変更しない、§4参照）

### Step 5: R3a 検証
- `python -m py_compile`構文確認
- オフラインスモークテスト（フェーズ横断参照、ファイル読み取り、Windowsパス区切りでの`read_deliverable_file`動作、`log/`外へのトラバーサル拒否）

### Step 6: R3b `write_agreement`ツール定義
- `WRITE_AGREEMENT_TOOL`の定義（`confirmed_variables`フィールドを含む、§3.1、中程度対応）
- `_build_agreements_context`に`id`表示を追加（§3.2.1、中程度⑤対応）
- `_write_agreement_impl`（`confirmed_variables`→`upsert_verified_fact`反映を含む、§3.2、致命的②対応） / `_check_write_permission`（全status×全ロール許可表、§3.2、中程度④対応） / `_commit_agreement_from_tool`の実装
- `TOOL_DISPATCH`への登録（`_CURRENT_TASK_ID`も束縛）

### Step 7: R3b ツール付与とcaller_role設定
- Expert/User AI/Detector/Reviewer/Arbiter/**Integrator**への`write_agreement`ツール付与（★Integrator追加）
- `_CURRENT_CALLER_ROLE`・`_CURRENT_TASK_ID`グローバル変数の導入
- 各ノード関数で`query_AI`呼び出し前のロール・task_id設定
- `decision_extractor_node`のうちAgreement書き込み部分のみ「write_agreement未呼び出し時」の条件分岐を追加し、`owned_variable_values`→`verified_facts`抽出部分は無条件のまま維持（§3.5、致命的②対応の一部）

### Step 8: R3b 検証
- `python -m py_compile`構文確認
- オフラインスモークテスト（権限チェックの全ロール×全status網羅、構造チェック、confirmed_variables反映、depends_on ID可視性）

### Step 9: 統合ドライラン
- R3a+R3b適用後の実LLMドライラン
- BL-035/036/037の解消確認
- 指標A/E/Fの実測

---

## 6. 変更対象ファイル一覧

| ファイル | 変更内容 |
|----------|----------|
| `cela_main.py` | `from pathlib import Path`追加、ツールディスパッチの`handler(args)`修正（致命的①）、verified_factsスキーマ拡張、upsert/get関数拡張、読み取りツール定義・ハンドラ（パス検証修正済み）、write_agreementツール定義・ハンドラ（confirmed_variables対応）、`_build_agreements_context`へのid表示追加、`_check_write_permission`の全ロール×全status許可表、TOOL_DISPATCH更新、Integrator/Resource Arbiterを含む各ノードのtoolsリスト更新、`_build_task_scope_context`修正、`_CURRENT_RUN_ID`/`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`グローバル変数（`_query_AI_live`自体のシグネチャは変更しない） |
| `docs/design/r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md` | R3a/R3b該当節の追記（§3.2〜3.4.1にR3a読み取りツールの記述を追加） |
| `docs/design/phase_gates.md` | P3a-1〜P3a-4、P3b-1〜P3b-2の状態更新 |
| `docs/design/STATUS.md` | アクティブPhase・次アクション更新 |