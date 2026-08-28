# BL-289/BL-290: 消費系ツールの情報非対称バグを一括修正、goal_escalations用の読み取りツールを新設

## Context

BL-288（`read_agreement`の6キー欠落）修正を受け、ユーザーが同型のバグが他の消費系ツールにも無いか自ら監査し、issue_backlog.mdへBL-289（3件の具体的な欠落）とBL-290（読む口自体が存在しない欠落）として詳細に記録した。両BLとも設計は「open・未着手」の状態で、今回「同様に修正してください」という指示を受けた。BL-288で確立した方針（欠落しているカラムを返り値に追加、防御的パースが必要な列は専用ヘルパーで対応、§17.1でリバート検証）をそのまま踏襲する。

追加調査で以下を確認済み：
- ツール結果はLLMへ渡る直前に必ず`json.dumps(result, ensure_ascii=False)`される（`cela_main.py`、`_query_AI_live`のディスパッチループ、`loop_messages.append({"role": "tool", ..., "content": json.dumps(result, ...)})`）。つまり**現状でも`_read_deliverable_file_handler`が返すプレーン文字列は既にJSON文字列としてクォート表示されている**——dict化してキーを追加しても、モデルから見た表示形式の質的な変化（二重エンコード等）は生じない。BL-289が懸念していた「返り値の形状変更」は、実際には低リスクな変更であることを確認した。
- `_read_deliverable_file_handler`は`TOOL_DISPATCH`経由でのみ参照されており（`cela_main.py:5283`）、Python側の直接呼び出し元は存在しない。戻り値をstr→dictへ変更しても内部コードへの影響はない。
- `get_latest_whiteboard`は13箇所から呼ばれているが、いずれも既存キー（`version`/`content`等）へのアクセスのみで、新規キー追加は非破壊的。
- `get_goal_escalation`（`cela_main.py:2986`）は既に`SELECT *`→dict化された全カラム返却のヘルパーとして存在し、BL-290はこれをそのまま再利用できる。

## 設計

### BL-289 ①: `read_plan_draft`（`get_latest_plan_draft_by_task_id`）

`cela_main.py:7820-7825`のSELECT文へ`draft_id, author_role, edit_summary, timestamp`を追加し、返り値dictにも含める。`_read_plan_draft_handler`（`cela_main.py:1601`）は既に`draft`をそのまま返しているため無改修。

### BL-289 ②: `read_deliverable_file`のホワイトボード経路（`get_latest_whiteboard`）

1. `get_latest_whiteboard`（`cela_main.py:7654-7673`）のSELECT文へ`draft_id, author_role, edit_summary, timestamp`を追加し、返り値dictにも含める（既存13呼び出し元は非破壊）。
2. `_read_deliverable_file_handler`（`cela_main.py:2213`）のWHITEBOARD成功パス（`cela_main.py:2256`）を、`return wb["content"][:10000]`から
   ```python
   return {
       "content": wb["content"][:10000],
       "author_role": wb.get("author_role"), "edit_summary": wb.get("edit_summary"),
       "timestamp": wb.get("timestamp"), "draft_id": wb.get("draft_id"),
   }
   ```
   へ変更する。FILE_PATH経路（`cela_main.py:2278`、実ファイル読み取り）はDBメタデータを持たないため対象外（BL-289の指摘範囲外）とし、`{"content": content[:10000]}`へ変更してdict形状のみ揃える（キー追加はしない、Noneの捏造を避ける、AGENTS.md §13）。
3. 関数シグネチャの戻り値型注釈を`dict | str`から`dict`へ更新する。

### BL-289 ③: `trace_lineage`（`_traverse_lineage`）

`_traverse_lineage`（`cela_main.py:7353-7416`）のbackward/forward両方のSQL SELECTへ`id, created_by, source_task_id, source_phase_id`を追加し、`found.append({...})`にも含める。`_trace_lineage_handler`（`cela_main.py:7538-7591`）の`resolved`リスト内包表記（`cela_main.py:7578-7585`）へ同じ4キーを追加する。`_traverse_lineage`の他の呼び出し元（`_get_backward_dependencies`/`_get_forward_dependents`/`_get_lineage_chain`）はキー追加のみで非破壊。

### BL-290: `read_escalation`ツールの新設

`get_goal_escalation`（`cela_main.py:2986`、`SELECT *`で全カラム、既存）をそのまま再利用。新規に`get_goal_escalations_by_task_id(conn, run_id, task_id)`（`get_open_goal_escalations`と同じ場所・同じスタイル、statusを問わず全件をcreated_at順で返す）を追加する。

```python
def get_goal_escalations_by_task_id(conn: sqlite3.Connection, run_id: str, task_id: str) -> list[dict]:
    """[BL-290] 指定task_idで提起された全エスカレーション（status問わず）をcreated_at順で返す。"""
    rows = conn.execute(
        "SELECT * FROM goal_escalations WHERE run_id=? AND task_id=? ORDER BY created_at ASC",
        (run_id, task_id)
    ).fetchall()
    return [dict(r) for r in rows]
```

新規ツール定義（`READ_AGREEMENT_TOOL`の直後に配置）:
```python
READ_ESCALATION_TOOL = {
    "type": "function",
    "function": {
        "name": "read_escalation",
        "description": (
            "[BL-290] Read the full detail of a goal-premise escalation raised via "
            "escalate_premise_concern (concern_summary/implicated_constraint/why_conflicts/"
            "suggested_reframe/status/resolution_reason) -- not just the concern_summary shown "
            "in the ambient status pin every turn. implicated_constraint/why_conflicts/"
            "suggested_reframe are otherwise never surfaced again after the turn they were raised. "
            "Pass escalation_id (shown bracketed in the ambient pin, e.g. '[ESC-...]') for an exact "
            "lookup, or task_id to list all escalations raised under that task."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "escalation_id": {"type": "string", "description": "Exact escalation_id from the ambient pin."},
                "task_id": {"type": "string", "description": "List all escalations raised under this task_id."}
            }
        }
    }
}
```

新規ハンドラ（`_read_agreement_handler`の直後に配置、`TOOL_DISPATCH`へ`"read_escalation": lambda args, state=None: _read_escalation_handler(args)`を登録）:
```python
def _read_escalation_handler(args: dict) -> dict:
    """[BL-290] read_escalationツールの実体。read_agreement（BL-279）と同型だが、
    goal_escalationsは1行=1件のためentry_typeフィルタ等は不要な単純な設計。
    """
    escalation_id = (args.get("escalation_id") or "").strip()
    task_id = (args.get("task_id") or "").strip()
    if not escalation_id and not task_id:
        return {"status": "error", "message": "escalation_id、task_idのいずれかを指定してください。"}
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    if escalation_id:
        row = get_goal_escalation(conn, run_id, escalation_id)
        if not row:
            return {"status": "not_found", "message": f"escalation_id={escalation_id!r} が見つかりませんでした。"}
        return {"status": "ok", "count": 1, "escalations": [row]}
    rows = get_goal_escalations_by_task_id(conn, run_id, task_id)
    if not rows:
        return {"status": "not_found", "message": f"task_id={task_id!r} に該当するエスカレーションが見つかりませんでした。"}
    return {"status": "ok", "count": len(rows), "escalations": rows}
```

**配線範囲**: `READ_AGREEMENT_TOOL`が既に配線されている全13箇所（task_planner/orchestrator/expert/detector×2/resource_arbiter/integrator/reviewer/generate_user_utterance Stage3+main/goal_essence_analyst/task_plan_reviewer）に、同じ並びで`READ_ESCALATION_TOOL`を追加する。escalate_premise_concern/resolve_premise_concernは特定ロールに偏るが、read_agreement等の既存読み取りツールが全ノード共通で配線されている前例があり一貫性を優先し、統一配線する。

## 検討したが見送った代替案

- `_read_deliverable_file_handler`のFILE_PATH経路にもauthor_role等のNoneを埋めて完全に同一形状にする案: 実在しないメタデータをNoneで埋めるのは実体の無い情報を捏造して見せることに近く、AGENTS.md §13の精神（fallbackの意味を吟味する）に反する。`content`キーのみ共通化するに留める。
- `read_escalation`を`escalate_premise_concern`/`resolve_premise_concern`保有ノードのみに限定配線する案: read_agreement等の既存読み取りツールが全ノード共通で配線されている前例と一貫性を欠くため見送り、全13箇所へ統一配線する。

## Critical Files

- `cela_main.py`:
  - `get_latest_plan_draft_by_task_id`（7813-7825）: SELECT・返り値dictへ4キー追加
  - `get_latest_whiteboard`（7654-7673）: SELECT・返り値dictへ4キー追加
  - `_read_deliverable_file_handler`（2213-2280）: WHITEBOARD成功パスをdict化、FILE_PATH成功パスも`{"content":...}`のdict化、戻り値型注釈更新
  - `_traverse_lineage`（7353-7416）: backward/forward両SELECT・`found.append`へ4キー追加
  - `_trace_lineage_handler`（7538-7591）: `resolved`リスト内包表記へ4キー追加
  - 新規`get_goal_escalations_by_task_id`（`get_open_goal_escalations`の直後）
  - 新規`READ_ESCALATION_TOOL`（`READ_AGREEMENT_TOOL`の直後）、新規`_read_escalation_handler`（`_read_agreement_handler`の直後）、`TOOL_DISPATCH`登録
  - `READ_ESCALATION_TOOL`を既存13箇所の`READ_AGREEMENT_TOOL`と同じ並びに追加配線
- `tests/test_bl289_consumer_tool_field_gaps.py`（新規）: read_plan_draft/read_deliverable_file/trace_lineageそれぞれの新規キー確認、`_read_deliverable_file_handler`のFILE_PATH経路が引き続き動作すること、§17.1
- `tests/test_bl290_read_escalation.py`（新規）: escalation_id/task_id両検索、not_found/error、全13ノードへの配線確認（ソース検査、BL-283系のパターンを踏襲）、§17.1

## Verification

1. `python -m py_compile cela_main.py`
2. 新規2テストファイルを実行し全件成功を確認
3. 既存の関連テスト（`test_bl101_task_planner_plan_draft_tool.py`、whiteboard/read_deliverable_file関連、`test_bl224`系のtrace_lineageテスト、`test_bl086`系のescalation関連）を再実行し非退行を確認
4. AGENTS.md §17.1（各変更箇所を個別にリバートし対応テストが失敗することを確認後、復元）
5. フルオフラインスイートを実行し、既知のBL-269（4件）以外に新規失敗が無いことを確認
6. 実装後、`docs/design/back_log/issue_backlog.md`のBL-289/BL-290を`done`化し、`decision_log.md`へ決定を記録

---

**[事後追記]** 本ドキュメントは実装完了・コミット（`f969a0b`）後に、AGENTS.md §7（BL-scoped plansはdocs/design/back_log/BL-xxx/へ保存）の遵守漏れが発覚したため、Plan Mode実行時に実際に承認・実行された計画内容をそのまま保存したものです（内容は実装時点のものと同一、事後の書き換えなし）。