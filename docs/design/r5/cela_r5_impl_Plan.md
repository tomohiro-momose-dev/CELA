# R5実装計画: F-2.1拡張／F-3.7／F-8.3 Freeze／GoalShiftEvent

> 前提設計書: [cela_r5_design_v2.md](cela_r5_design_v2.md)（2026-07-23★追記済み）

## Context（なぜこの変更か）

`cela_r5_design_v2.md`が定義するR5の新規要件（F-2.1拡張・F-3.7・F-8.3 Freeze・GoalShiftEvent）を実装する。BL-041/BL-050のMVP実装（`_aggregate_global_constraints`によるarbiter実働化、`resource_claims`新スキーマ、D-042）によりGoalShiftEventの前提だった「arbiterが死んだコードパス」問題は既に解消済みであり、R5着手の障害はない。

Plan mode中の設計相談で、以下2点を確定した。

1. **decision_extractor役割転換（BL-050完了条件3）は今回含めない**（ユーザー判断）。F-3.7のコア機能（思考ログの強制記録）はdecision_extractorの役割を変えなくても実装可能なため。
2. **Detectorが既存Agreementを構造的に上書き・無効化できない問題**（Plan相談中にユーザーが新たに指摘）：調査の結果、Detectorの`major`判定は差し戻し（再プロンプト）を引き起こすのみで、User/Expertが既に書き込んだ`Approved`/`Proposed`なagreementをDB上でSUPERSEDE/無効化する構造的な仕組みは存在しないことを確認した（Detectorのwrite_agreement呼び出しにtarget_topicでSUPERSEDEする運用ガイドが無い）。これはFreeze機能固有の課題ではなく、write_agreementの権限モデル全体に及ぶより根深い課題のため、**今回のR5実装とは切り離し、ドキュメントのみで新規BLとして起票するに留める**（ユーザー判断）。F-8.3 Freezeの権限は`user`ロールのみに限定することで、この根深い課題があってもFreeze自体の意味（「絶対に覆してはならない決定」への恒久ピン留め）は損なわれない設計とする。

F-5.5（思考内エージェント化ループ）はv2設計書の既定方針通り、本フェーズでは実装せず設計検証のみのため対象外。

## 実施内容0: ドキュメントのみ（コード変更前に実施）

- `docs/design/issue_backlog.md`にBL-062を新規起票（`open`、内容：Detectorのmajor判定・Rejected書き込みが既存Agreementを構造的に上書き・無効化できない。write_agreementの権限モデル・SUPERSEDE運用ガイドの再設計が必要な大きめの課題として記録。実装は見送り）。
- `docs/design/decision_lineage.md`に新規論点を追記（本Plan相談での発見・切り分け判断を記録）。

## 実施内容1: F-2.1拡張（思考プロセス監査）＋F-3.7（思考ログの強制記録）

両者は「reasoning contentを捕捉し、消費側へ配線する」という同じ配線問題を共有するため一体で実装する。

### 1a. reasoning content の捕捉（`_query_AI_live`）

現状、`_query_AI_live`のストリーミング処理は`delta.reasoning`を受け取って`💭`表示で印字するのみで（非tools分岐、tools分岐）、その後破棄している。BL-033の`_LAST_PYTHON_CALLS`と同型のモジュールグローバルパターンを踏襲し、以下を追加する。

- モジュールグローバル`_LAST_REASONING_TEXT: str = ""`を新設（`_LAST_PYTHON_CALLS`等の近く）。
- `_query_AI_live`の冒頭で`_LAST_REASONING_TEXT`をリセットし、両分岐（非tools/tools）で`delta.reasoning`を蓄積するリストへ追記（tools分岐は現状印字のみで蓄積していないため、ここに追記処理を追加）、関数の戻り際に`_LAST_REASONING_TEXT`へ結合して格納。
- `get_last_reasoning_text() -> str`ゲッターを新設（`get_last_python_calls()`と同じ形）。

### 1b. state経由でDetectorへ配線（F-2.1）

- `LineageState`に`expert_last_reasoning: str`・`user_last_reasoning: str`を新設（BL-038/BL-061の教訓通り、TypedDict宣言必須）。
- `expert_node`・`generate_user_utterance_node`が、既存の`state["expert_last_python_calls"] = get_last_python_calls()`と同じ箇所で`state["expert_last_reasoning"] = get_last_reasoning_text()`（User側も同様）をセット。
- `call_detector`に、v2設計書§1.3の`thought_process_audit`ブロックを追加。挿入位置は既存の`expert_last_python_calls`ブロックと同じ並びとし、`state.get("expert_last_reasoning"/"user_last_reasoning", "")`（target_roleに応じて選択）を埋め込む。reasoningが空文字列（プロバイダ非対応時）の場合は「(思考ログ取得不可)」を表示し、監査プロンプトが空文字を前提に破綻しないようにする。

### 1c. 思考ログの強制記録（F-3.7）

- `make_decision(who, what, why, internal_thought_process: str | None = None)`にパラメータ追加（v2設計書§2の通り）。既存の全呼び出し元は引数省略で後方互換。
- **限定運用**（v2設計書の方針通り、全件保存はしない）：
  - `call_detector`のmajor判定分岐、`reflection_node`のstagnant判定分岐からの`make_decision`呼び出しにのみ、`internal_thought_process=get_last_reasoning_text()`（該当する直近ノードの分）を明示的に渡す。
  - `agreements`側は、`_commit_agreement_from_tool`のINSERT文（現状`internal_thought_process`列が常に`None`固定）で、`args.get("status") == "Rejected"`の場合のみ`get_last_reasoning_text()`を渡すよう変更。
- `db_append_decision`は既に`internal_thought_process`列を読み込み済み（変更不要）。

### スコープ外（v2設計書通り据え置き）

- decision_extractorの役割転換（BL-050完了条件3）。
- `write_agreement_tool_impl_with_thought`という専用ラッパー関数は導入しない（上記の限定的な条件分岐で十分なため、v2設計書の擬似コードより簡潔な実装とする）。

## 実施内容2: F-8.3 Freeze機能

### 2a. `freeze_agreement`関数

```python
def freeze_agreement(conn: sqlite3.Connection, run_id: str, agreement_id: str, reason: str) -> None:
    conn.execute("UPDATE agreements SET is_frozen = 1 WHERE id = ? AND run_id = ?", (agreement_id, run_id))
    decision = make_decision(who="system_freeze", what=f"Agreement {agreement_id} をFreeze（永久ピン留め）", why=reason)
    db_append_decision(decision, conn, run_id)
```

### 2b. 新規専用ツール`FREEZE_AGREEMENT_TOOL`

既存の`WRITE_AGREEMENT_TOOL`（14パラメータで既に複雑）を汚さず、新規の小さな専用ツールとして追加（パラメータ: `agreement_id`, `reason`）。`TOOL_DISPATCH["freeze_agreement"]`で、`_CURRENT_CALLER_ROLE == "user"`のみ許可（それ以外は`_check_write_permission`と同様のエラーメッセージを返す）。User AIのツールリストにのみ追加する（Expert/Detector/Reviewer/Arbiter/Integratorのtoolsには追加しない）。

### 2c. SUPERSEDE/UPDATEガード

`_commit_agreement_from_tool`のSUPERSEDE分岐・UPDATE分岐の対象行検索時、対象行が`is_frozen == 1`であれば処理を中断しエラーメッセージ（「このagreementはFreeze済みのため変更できません」）を返す。Freezeは「絶対に覆してはならない決定への恒久ピン留め」という設計意図（v2§3）のため、unfreeze機構は設けない。

### 2d. `_build_agreements_context`への反映

`decisions_and_deliverables`リスト構築直後、ループ開始前に以下を追加:
```python
decisions_and_deliverables.sort(key=lambda a: (not a.get("is_frozen"), a.get("timestamp", 0)))
```
既存のBL-050差分表示ロジックには影響しない（ソート順序のみの変更）。あわせて既存のicon判定に`is_frozen`時の🔒プレフィックスを追加する（表示上の視認性のため）。

## 実施内容3: GoalShiftEvent

### 3a. スキーマ追加

`init_db`に`goal_shift_events`テーブルを新規追加（v2設計書§4.1のDDLをそのまま使用）。

### 3b. `call_resource_arbiter`への`requires_goal_constraint_change`追加

既存プロンプトのJSON出力指定に`requires_goal_constraint_change: true/false`を追加し、v2設計書§4.3の指示文をプロンプトに追記。

### 3c. `detect_goal_shift`関数

v2設計書§4.2の擬似コードをそのまま実装。

### 3d. `arbiter_node`への配線

`arbiter_node`内、`result = call_resource_arbiter(...)`の直後（既存の`make_decision(who="arbiter", ...)`呼び出しの前後）に追加:
```python
shift = detect_goal_shift(state, result)
if shift is not None:
    db_append_goal_shift_event(shift, get_active_conn(), state["run_id"])  # 新規ヘルパー、goal_shift_eventsへINSERT
```

## テスト方針

各節ごとに`tests/test_r5_*.py`（新規、既存`test_bl041_bl050.py`等の構成に倣う）を追加し、以下を最低限カバーする。

- F-2.1/F-3.7: `_query_AI_live`のreasoning捕捉はモック（実際のストリーミングをテストするのは困難なため、`get_last_reasoning_text()`getterの単体テストと、`make_decision`のinternal_thought_process受け渡し、`_commit_agreement_from_tool`のRejected時のみ記録、を直接テスト）。
- F-8.3: `freeze_agreement`実行後、`is_frozen=1`になること・`FREEZE_AGREEMENT_TOOL`が`user`以外から拒否されること・Freeze済み行へのSUPERSEDE/UPDATEが拒否されること・`_build_agreements_context`でFrozen項目が先頭に来ること。
- GoalShiftEvent: `detect_goal_shift`が`requires_goal_constraint_change=true`時のみイベントを返すこと、`arbiter_node`経由で`goal_shift_events`テーブルへ実際にINSERTされること（`call_resource_arbiter`はモック）。
- 全体: `python -m py_compile cela_main.py`、既存スモークテスト（`test_r3_smoke.py`/`test_r4_smoke.py`/`test_checkpoint_resume.py`/`test_bl041_bl050.py`/`test_bl061_facilitator_reflection_note.py`、計82件）の非退行確認。

## ドキュメント更新（実装完了後）

- `docs/design/issue_backlog.md`にBL番号を割り当て（F-2.1/F-3.7/F-8.3/GoalShiftEventそれぞれ、またはまとめて1件）、完了条件を記録。
- `docs/design/decision_log.md`に主要な設計判断（Freeze権限をuserのみに限定した理由等）をD-xxxとして記録。
- `docs/design/decision_lineage.md`に本実装の経緯（decision_extractor役割転換の見送り、監査ガバナンス欠落の発見とBL分離）を論点として記録。
- `cela_r5_design_v2.md`の「未確定事項まとめ」を実装完了に応じて更新。
- `python scripts/check_docs_consistency.py`で整合性確認。