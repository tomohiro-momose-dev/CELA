# R4実装計画: ホワイトボード差分パッチ化

## Context（なぜこの変更か）

R3a/R3b完了後の実ドライラン（`log/2026-07-21/2248`）は長時間化・トークン消費が大きく、検証コストが高いとユーザーが判断。根本原因の一つは、Expertが成果物（Deliverable）を修正するたびに**全文を再生成**していること（`decision_extractor_node`/`write_agreement`のDeliverable保存は今もExpertの出力全文をそのまま保存する構造）。既存のR4設計書（`docs/design/r4/cela_r4_design.md`）はこの問題を認識し「差分パッチ化」という方向性を示していたが、**Expertが提示する「変更箇所」を既存の完全版へどう安全にマージするか**が未定義だった（自由記述の部分修正をそのままDBに上書き保存すると、触れていない箇所の内容が失われる）。

ユーザーへの確認の結果、**Claude Code自身のEditツールと同じ方式**（`old_text`の完全一致検索→`new_text`へ置換、一致しない/複数一致する場合はエラーを返しExpertに修正させる）を採用する方針とした。この方式はLLMに行番号やunified diff形式を要求せず、マージ処理も100%機械的（決定的）なため、他の2案（構造化セクション方式、unified diff方式）より実装リスクが低い。

**副次的な効果**: この変更により、DeliverableのCREATE/UPDATEが`write_agreement`ツール経由に一本化されるため、BL-038（`write_agreement`後もdecision_extractorがDeliverable抽出をスキップし損ねる問題）の影響範囲が実質的に縮小する（Deliverable種別についてはdecision_extractor側の抽出ロジックをフォールバックのみに格下げできるため）。

**明示的にスコープ外**: BL-041（facilitator/Resource Arbiter再設計）、BL-005（turn_count凍結）、F-7.4（高品質初版生成ルールの試験導入、既存設計書§2.5）は本計画に含めない。F-7.4は将来の拡張として設計書に残すが、今回の実装対象外とする。

---

## 実装方針

### 1. `whiteboard_drafts`用のDBヘルパー関数（新規、`cela_main.py`）

既存の`whiteboard_drafts`テーブル（`init_db`で定義済み、未使用）を使う。既存のDBアクセス関数（`get_agreements_from_db`等）と同じ様式（`conn`, `run_id`を明示的に受け取る）に合わせる。

```python
def get_latest_whiteboard(conn, run_id: str, phase_id: str, task_id: str) -> dict | None:
    """最新バージョンの{version, content}を返す。存在しなければNone。"""

def apply_whiteboard_patch(conn, run_id: str, phase_id: str, task_id: str,
                            new_content: str, author_role: str, edit_summary: str) -> int:
    """新バージョンとしてINSERTし、version番号を返す（cela_r4_design.md §2.2の実装、run_id対応版）。"""

def rollback_whiteboard(conn, run_id: str, phase_id: str, task_id: str, reason: str) -> None:
    """直前バージョンの内容を新バージョンとして再INSERTする（design.md §2.3のロールバック方式）。"""

def _apply_text_edits(current_content: str, edits: list[dict]) -> tuple[str | None, str | None]:
    """Claude Code Editツールと同じ方式: 各editの{old_text, new_text, replace_all}を
    current_contentに対し完全一致検索→置換。old_textが0件/複数件（replace_all=False時）の
    場合はNone, エラーメッセージを返す。全edit成功時は(新content, None)を返す。"""
```

### 2. `WRITE_AGREEMENT_TOOL`スキーマ拡張（`cela_main.py`）

`entry_type=="Deliverable"`のケース向けに、`decision_what`（全文）に加えて任意の`edits`配列を追加する。

```python
"edits": {
    "type": "array",
    "description": (
        "For entry_type='Deliverable' UPDATE only. Instead of restating the full document in "
        "decision_what, provide targeted text replacements against the CURRENT whiteboard version "
        "shown in your system prompt. Each old_text must match exactly (and uniquely unless "
        "replace_all=true) in the current content, or this call fails with an error you can retry."
    ),
    "items": {
        "type": "object",
        "properties": {
            "old_text": {"type": "string"},
            "new_text": {"type": "string"},
            "replace_all": {"type": "boolean", "default": False},
        },
        "required": ["old_text", "new_text"],
    },
}
```

### 3. `_write_agreement_impl`/`_commit_agreement_from_tool`の分岐追加

- **CREATE + entry_type=="Deliverable" + `decision_what`が200文字超**: 現行の`save_deliverable_to_file`呼び出しを`apply_whiteboard_patch(..., new_content=raw_content, ...)`（version=1）に置き換え。`decision_what`は`WHITEBOARD:{phase_id}:{task_id}`ポインタにする。
- **UPDATE + entry_type=="Deliverable" + `edits`が指定されている場合**: `get_latest_whiteboard`で現行版を取得 → `_apply_text_edits`適用。失敗時は**DBに一切書き込まず**`{"success": False, "error": "..."}`を返す（`_write_agreement_impl`のバリデーション段階、権限チェックと同じ位置に追加）。成功時は`apply_whiteboard_patch`で新バージョンをINSERT。
- **UPDATE + entry_type=="Deliverable" + `edits`なし（`decision_what`に全文）**: 全文置換の抜け道として維持。`apply_whiteboard_patch`にそのまま渡す（大規模な構成変更等、snippet編集が非現実的なケース用）。
- 既存のファイルベース版管理（`save_deliverable_to_file`/`_archive_old_deliverable_file`、BL-040実装分）は**削除しない**。`integrator_node`の最終統合文書（1回限りの大きな成果物、バージョン管理不要）はこのままファイル方式を使う。per-task Deliverableのみホワイトボード方式に切り替える。

### 4. `call_expert`のプロンプト変更（`_build_task_scope_context`拡張）

`_build_task_scope_context`に、現在タスクの最新ホワイトボード版（存在すれば）を取得し返す処理を追加。`call_expert`のフル版・軽量版system_promptの両方に、design.md §2.4のプロンプト文言（現在のホワイトボードVer.N全文を提示し、「全文書き換え不要、write_agreementツールの`edits`で変更箇所のみ提示」という指示）を追加する。

### 5. `call_detector`のプロンプト変更

Deliverable編集ターンを正しく検証するには、Expertの直近発言（差分の要約のみ）だけでなく**編集後の完全版**が必要。`call_detector`に、現在タスクの最新ホワイトボード内容（該当あれば）を取得しプロンプトに含める処理を追加する。

### 6. `integrator_node`の読み込み分岐追加

```python
if content_data.startswith("FILE_PATH:"):
    ...(既存のまま)
elif content_data.startswith("WHITEBOARD:"):
    _, phase_id, task_id = content_data.split(":", 2)
    latest = get_latest_whiteboard(_conn, _run_id, phase_id, task_id)
    content_text = latest["content"] if latest else "(⚠️ホワイトボードが見つかりません)"
```

### 7. `read_deliverable_file`ツールの拡張（BL-040実装分との統合）

`_read_deliverable_file_handler`/`_resolve_deliverable_file_path`に、`WHITEBOARD:`ポインタの解決を追加（ファイルI/Oではなく`get_latest_whiteboard`を呼ぶ）。Detector/Expert/Userがtask_id/topic_keywordで検索する際、内部でFILE_PATH方式かWHITEBOARD方式かを意識せず使えるようにする。

### 8. ロールバック（F-7.3）の配線

`_LAST_WHITEBOARD_EDIT`モジュールレベル変数（`{phase_id, task_id, version}`、BL-033の`_LAST_PYTHON_CALLS`と同じ「LangGraph単一プロセス同期実行前提」パターン）を新設し、`_commit_agreement_from_tool`のwhiteboard patch適用成功時にセットする。`expert_node`冒頭の`constraint_issue=="major"`時の差し戻し処理（既存: `chat_history`の直前アシスタント発言をpop）に、`rollback_whiteboard`呼び出しを追加する。

### 9. `decision_extractor_node`のDeliverable抽出（変更最小限）

既存の全文抽出ロジック（`entry_type=="Deliverable"`かつファイル保存）はそのまま**フォールバックとして残す**（ExpertがWrite_agreementツールを使わず素のプロセ回答だけでDeliverableらしき内容を出した場合の安全網、既存の`owned_variable_values`安全網と同じ思想）。新規のロジック追加は不要。

---

## 対象ファイル

- `cela_main.py`（上記1〜8の全変更）
- `docs/design/r4/cela_r4_design.md`（承認後、上記「差分マージ方式の決定」を追記。既存の§2.2〜2.4疑似コードをold_text/new_text方式に更新）
- `docs/design/r4/cela_r4_impl_Plan.md`（AGENTS.md §7準拠、本計画の保存先。新規作成）
- `tests/test_r4_smoke.py`（新規、下記検証参照）
- `docs/design/issue_backlog.md` / `decision_lineage.md`（実装後、着手内容と決定を記録）

---

## 検証方法

- `tests/test_r4_smoke.py`にオフラインスモークテストを追加（実LLM不要）:
  - `apply_whiteboard_patch`→`get_latest_whiteboard`のバージョン往復
  - `_apply_text_edits`: 正常系（単一一致置換）、異常系（0件一致、複数件一致でreplace_all=false時のエラー）、`replace_all=true`での複数置換
  - `TOOL_DISPATCH["write_agreement"]`でDeliverable CREATE→`WHITEBOARD:`ポインタ生成・V1保存を確認
  - 同UPDATE（`edits`指定）→V2保存、内容が正しくマージされていることを確認
  - `rollback_whiteboard`後、`get_latest_whiteboard`が正しい内容を返すことを確認
  - `integrator_node`が`WHITEBOARD:`ポインタを正しく読めることを確認（既存の`FILE_PATH:`テストと対で追加）
  - `read_deliverable_file`が`WHITEBOARD:`ポインタ経由でも内容を返すことを確認
- `python -m py_compile cela_main.py`
- 既存の`tests/test_r3_smoke.py`（50件）が非退行でPassすること
- 実LLM再ドライランで、同一Deliverableを複数回修正するタスクにおいてExpertの出力トークン数が明確に減っていることを確認（design.md §3の完了条件と対応）
