# BL-086（仮番号）: 前提エスカレーション経路 + Freeze復活 + ゴール改定（GoalShiftEventの実消費化）

## Context（なぜこの変更か）

実ドライラン（`log/2026-07-24/2054`）で、Expertが「オンデマンド交通なのに予算制約から逆算して35人乗りバスを導入する」という、そもそもの前提（オンデマンド輸送の性質）と数値的に無理やり帳尻を合わせた結論の間に矛盾を抱えたまま進行している事例をユーザーが発見した。

調査の結果、以下の構造的欠陥が判明した：

1. Expertは`absolute_constraints`（予算・ヘッドウェイ等）の文言を厳守することしかできず、「この制約の立て方自体が本来解決すべき課題（高齢者の移動手段確保）に対して逆効果かもしれない」と気づいても、それを表明し検討させる手段が一切ない（BL-025のスコープガードレールは他タスクへの越権を防ぐためのものであり、そもそも論を封じる意図ではないが、結果的に同じ「厳しく限定された思考空間」を作っている）。
2. たとえUser AIが例外を承認しても、それを恒久的にピン留めする`Freeze`機構（`is_frozen`/`freeze_agreement`）はD-045で意図的に無効化されたままであり、次のDetector監査で同じ論点が独立に`major`判定→SUPERSEDEされ、承認が無限に覆される構造的リスクがある（BL-062はDetectorの独立した正しさを守るために作られたが、その代償として「人間が既に審議した例外」を区別する手段が失われた）。
3. ゴール自体（`state["goal"]`という単一の文字列）を書き換える手段が存在せず、R5で作った`GoalShiftEvent`（`detect_goal_shift`/`goal_shift_events`）は`arbiter_node`の資源再配分判定からしか発火せず、しかも発火してもDB書き込みのみで何も消費されない「書きっぱなし」（BL-065、`open`のまま）。

ユーザーの指示：「エスカレーション経路も作りこみ、freezeを復活させて、高齢者の移動手段の確保という本質的課題の解決という視点に登り、例え当初目標を越境しても最適な着地点にたどり着けるようにしたい」。

3つのExploreエージェント（Escalation/スコープガードレール調査、Freeze/Detectorプロンプト調査、ゴール構造/GoalShiftEvent調査）とPlanエージェントによる設計、および全ての重要な行番号・関数シグネチャの直接検証（`cela_main.py`読み込みで裏取り済み）を経て、以下の実装計画を確定した。

## 検証済みの重要な事実

- `state["goal"]`（`LineageState.goal`, 2480行目付近）は`Annotated[str, _take_latest]`の単一プローズ文字列で、`TARGET_GOAL`から一度セットされたきり（グラフ起動時、5650行目）**一度も再代入されていない**（grep確認済み）。`_take_latest`リデューサーのため、どこかのノードが`{"goal": new_text}`を返せばLangGraphが即座に上書きする——**フレームワーク側は既にミュータブルに対応しており、実行するノードが存在しないだけ**。
- `state["goal"]`は9箇所の呼び出し元（call_expert 2911/2997、call_resource_arbiter 3207/3783、generate_user_utterance 3906、task_planner_node 4432、call_detector×2 4537/4545、call_facilitator 4955、integrator/master doc 5014、call_integrator 5051、call_reviewer 5111）が毎ターン新鮮に埋め込むため、**たった1箇所（User AIの改定処理ノード）でstate["goal"]を書き換えられれば、残り8箇所は自動的に次ターンから改定後の内容を見る**。個別配線は不要。
- `generate_user_utterance`のUser AIプロンプトには既に「動かせない真の制約」と「見直し可能な例示的前提」を区別し、後者なら前提自体の見直しを検討させる文言が存在する（4197-4203行目）。今回の機能はこれに構造化ツールを与えるだけで、既存の思想と矛盾しない。
- `FREEZE_AGREEMENT_TOOL`（877-899）/`freeze_agreement()`（902-917、`{"success":bool,...}`を返す）/`_freeze_agreement_tool_impl()`（920-928、`caller_role != "user"`で拒否）は実装済みだが、**全ての`tools=[...]`箇所（3191, 3473, 3812, 4026, 4103, 4305, 4313）のどこにも含まれておらず完全に呼び出し不能**（D-045）。`_commit_agreement_from_tool`のis_frozenガード（SUPERSEDE: 1003-1007、UPDATE: 1042-1044・1052-1054）はcaller_role非依存で効くため、Detector発のSUPERSEDEも同様にブロックされる（`tests/test_r5_thought_log_freeze_goalshift.py`で確認済み）。
- `_build_agreements_context`（2578-2662）は`is_frozen`項目を🔒アイコン付きで先頭ソート済み（2596, 2607-2609）だが、**🔒の意味を説明する文言がどこにも無い**——現状は完全に無意味な視覚記号。
- `call_detector`は2パス構成：ドメイン妥当性レビュー（`domain_prompt`, 3337-3371）は**agreements_textを一切受け取っていない**（`System Goal: {goal}`が3357行目）。数値監査メインパス（`prompt`, 3401-3467）は`agreements_text`を3436行目で埋め込み、直後にBL-062のSUPERSEDE指示（3437-3442）が続く——ここが新規フリーズ尊重指示の挿入点。
- `TOOL_DISPATCH`（1193-1203）・書き込み成功フラグの特殊分岐（`if tc.function.name == "write_agreement":`, 1623-1626）・`query_AI`冒頭のグローバルリセット（1268-1272）は、いずれも今回追加する`_LAST_GOAL_REVISION`用の`elif`/リセット行を追加するだけで済む、既に確立されたパターン（`_LAST_WRITE_AGREEMENT_SUCCEEDED`等と全く同型）。
- `generate_user_utterance_node`（4374-4399）が`state["user_wrote_agreement"] = get_last_write_agreement_succeeded()`（4393行目）を返り値に反映している箇所が、今回`state["goal"] = ...`を追加する自然な挿入点。
- `db_append_goal_shift_event(shift, conn, run_id)`（1923-1936）の引数順・`goal_shift_events`テーブルの列（1867-1878: shift_id, timestamp, shift_kind, from_goal_state, to_goal_state, reason_why, evidence, triggered_by, triggering_agreement_id, run_id）を確認済み、そのまま再利用する。
- `make_decision(who, what, why, internal_thought_process=None)`（4401行目）のシグネチャを確認済み、そのまま再利用する。
- 既存テスト`tests/test_bl062_detector_supersede.py`の`test_bl062_freeze_tool_removed_from_user_ai_tools`は、実は`generate_user_utterance_node`（ラッパー関数、tools=[...]を持たない）のソースをチェックしており**元々ほぼ無意味な検証だった**（本物のtools=[...]は`generate_user_utterance`側にある）。今回Freeze復活に伴い、正しい対象関数を見るよう修正しつつ意図を反転させる。

## 実施内容

### Phase 1: スキーマ（新規テーブル・グローバル変数）

1. `init_db`のexecutescriptブロック、`goal_shift_events`のCREATE INDEX群（1879-1881行目）の直後・閉じ`"""`（1882行目）の手前に、新規`goal_escalations`テーブルを追加：
   ```sql
   CREATE TABLE IF NOT EXISTS goal_escalations (
       escalation_id TEXT PRIMARY KEY, run_id TEXT NOT NULL,
       phase_id TEXT, task_id TEXT, raised_by_role TEXT NOT NULL,
       concern_summary TEXT NOT NULL, implicated_constraint TEXT NOT NULL,
       why_conflicts TEXT NOT NULL, suggested_reframe TEXT NOT NULL,
       status TEXT NOT NULL DEFAULT 'Open',
       resolution_reason TEXT, resolved_agreement_id TEXT,
       created_at REAL NOT NULL, resolved_at REAL
   );
   CREATE INDEX IF NOT EXISTS idx_goal_escalations_run_status ON goal_escalations(run_id, status);
   ```
   `plan_drafts`（版管理文書）とは性質が異なる「単発の意思決定レコード」のため、新規1テーブルとして独立させる（`agreements`への相乗りや、BL-067で死んでいる`current_goal`テーブルの再利用はしない——後者は`core_philosophy`/`absolute_constraints`という別スキーマで、`state["goal"]`のプローズ文字列とは形が合わない）。

2. 新規グローバル（`_CURRENT_RUN_ID`等の並び、747行目付近）：
   ```python
   _CURRENT_GOAL_TEXT: str = ""  # [BL-086] revise_goalが編集対象とする現在のgoal本文
   ```

3. 新規「直前アクション」グローバル+getter（`_LAST_WHITEBOARD_EDIT`等の並び、1215-1227行目付近）：
   ```python
   _LAST_GOAL_REVISION: dict | None = None

   def get_last_goal_revision() -> dict | None:
       return dict(_LAST_GOAL_REVISION) if _LAST_GOAL_REVISION else None
   ```
   `query_AI`冒頭のリセットブロック（1268-1272）に`_LAST_GOAL_REVISION = None`を追加。

### Phase 2: 新規ツール3種（`FREEZE_AGREEMENT_TOOL`直後、900-928行目付近に追加）

1. **`ESCALATE_PREMISE_CONCERN_TOOL`**（Expert・User AI両方が呼べる）: `concern_summary`/`implicated_constraint`/`why_conflicts_with_true_need`/`suggested_reframe`（必須4項目）+ 任意の`phase_id`/`task_id`。ツール説明文に「これは一般的な『制約が厳しい』という愚痴ではなく、スコープ外行動の許可でもない。今回のタスクのacceptance_criteriaは通常通り満たすこと」と明記し、BL-025ガードレールとの非衝突を担保する。
2. **`RESOLVE_PREMISE_CONCERN_TOOL`**（User AI専用、却下）: `escalation_id`/`reason`。
3. **`REVISE_GOAL_TOOL`**（User AI専用、承認・ゴール改定）: `escalation_id`/`edits`（`write_agreement`のDeliverable編集と同じold_text/new_text方式、`state["goal"]`という長大プローズ文への部分パッチに`_apply_text_edits`をそのまま再利用——全文置換だとゴール文全体の想定外欠落リスクがあるため）/`reason_why`/任意の`freeze_agreement_id`（指定時はその場でFreezeも実行）。

各ツールの実体関数（`_escalate_premise_concern_tool_impl`/`_resolve_premise_concern_tool_impl`/`_revise_goal_tool_impl`）と補助関数（`db_create_goal_escalation`/`get_goal_escalation`/`get_open_goal_escalations`）を`_freeze_agreement_tool_impl`直後に実装。役割ゲートは`_freeze_agreement_tool_impl`と同じ「関数内で`caller_role`を直接比較」方式（`_check_write_permission`のテーブル駆動方式とは別立て、既存Freezeの流儀を踏襲）。

`_revise_goal_tool_impl`は：`_CURRENT_GOAL_TEXT`に対し`_apply_text_edits`でパッチ→（`freeze_agreement_id`指定時のみ）既存`freeze_agreement()`を呼ぶ→`goal_escalations`を`Accepted`に更新→`db_append_goal_shift_event`で`shift_kind="premise_revision"`, `triggered_by="Escalation_Resolution"`, `from_goal_state`/`to_goal_state`に実際の改定前後テキストを記録→`make_decision`+`db_append_decision`で監査ログ。戻り値に`new_goal_text`/`old_goal_text`/`escalation_id`を含め、ツールハンドラ自身はLangGraph stateに触れられないため、この戻り値を`_LAST_GOAL_REVISION`へ橋渡しする。

`TOOL_DISPATCH`に3エントリ追加（1193-1203行目の並びと同じlambdaパターン）。ツールループの`if tc.function.name == "write_agreement":`（1623-1626）の並びに`elif tc.function.name == "revise_goal":`を追加し、成功時に`_LAST_GOAL_REVISION`をセット。

### Phase 3: プロンプト配線

1. **`call_expert`**（3073-3191付近）: `tools=[...]`（3191）に`ESCALATE_PREMISE_CONCERN_TOOL`のみ追加（Resolve/Reviseは追加しない——Expertは提起のみ、解決権限は与えない）。新規`_get_escalation_status_text_for_expert(conn, run_id)`（Open/Rejectedのみ表示、Acceptedは`state["goal"]`自体が既に改定済みのため二重通知しない）をBL-082の申し送り注入箇所の直後に追加。
2. **`generate_user_utterance`**（4122-4319）: `tools=[...]`両箇所（4305, 4313）に`ESCALATE_PREMISE_CONCERN_TOOL`/`RESOLVE_PREMISE_CONCERN_TOOL`/`REVISE_GOAL_TOOL`、および**Freeze復活の本体として`FREEZE_AGREEMENT_TOOL`も追加**（ユーザー指示「freezeを復活させて」への直接対応。`revise_goal`内蔵のfreezeとは別に、User AIが任意のタイミングで単独Freezeもできるようにする——D-044のuser限定ゲートが既に安全弁として機能するため）。両箇所の`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`セットブロック（4302-4304, 4310-4313）に`_CURRENT_GOAL_TEXT = user_goal`を追加。新規`_get_open_escalations_text(conn, run_id)`をBL-082申し送り注入箇所の直後に追加し、「今回の発言で必ずresolve_premise_concernかrevise_goalのどちらかを呼んで解決すること」と明記（先送りループの防止）。
3. **`generate_user_utterance_node`**（4374-4399）: `state["user_wrote_agreement"] = ...`（4393）の直後に
   ```python
   _goal_revision = get_last_goal_revision()
   if _goal_revision:
       state["goal"] = _goal_revision["new_goal_text"]
       print(f"🧭 [BL-086] Escalation {_goal_revision['escalation_id']} 承認によりgoalを改定しました。")
   ```
4. **`call_detector`**:
   - ドメイン妥当性パス（3337-3371）: `System Goal: {goal}`（3357）の直前に新規`_get_frozen_agreements_text(conn, run_id)`（🔒項目のみの軽量テキスト、agreements_text全体は渡さずトークンコストを抑える）を埋め込み、`domain_role_instruction`前後に「🔒項目は人間が既に審議し承認した意図的な例外であり、同じ論点をmajor/minorの根拠にしない」旨を追記。
   - 数値監査メインパス（3401-3467）: 既存BL-062指示（3437-3442）の**直前**に「🔒Freeze済み項目は同じ論点で再度major判定・SUPERSEDEしない（Freeze済みへのSUPERSEDE/UPDATEはツール呼び出し自体がエラーになる）。ただし新規の別問題は従来通り厳格に評価し、Freeze項目への軽微な懸念はconstraint_issueを上げずobservationsに留める」という一文を追加。Detectorの`tools=[...]`（3473）自体は変更しない（Escalation関連ツールは付与しない）。

### Phase 4: テスト

新規`tests/test_bl086_escalation_freeze_goal_revision.py`（`test_r5_thought_log_freeze_goalshift.py`/`test_bl082_plan_drafts_deferred_notes.py`と同じfixtureパターン）:

- エスカレーション提起: expert/user許可、他ロール拒否、必須項目欠落エラー、DB行がOpenで作成されること。
- 却下パス: user限定ゲート、status→Rejected、二重解決エラー、Decision記録。
- 承認パス: user限定ゲート、未知/解決済みescalation_idエラー、edits不一致エラー（escalationはOpenのまま＝リトライ可能）、成功時のgoal_escalations更新・goal_shift_events行（shift_kind="premise_revision"、from/to_goal_stateが実際の前後テキスト）・freeze_agreement_id指定時のis_frozen反映とその後のSUPERSEDE/UPDATE拒否。
- `generate_user_utterance_node`配線: `inspect.getsource`で`get_last_goal_revision`参照確認、monkeypatchで`get_last_goal_revision`が値を返すよう差し替え`state["goal"]`が更新されることを確認。
- 3箇所（call_expert/generate_user_utterance/call_detector）の`inspect.getsource`配線確認テスト（新規ツール・新規ヘルパー関数名の存在、Expertのソースに`RESOLVE_PREMISE_CONCERN_TOOL`/`REVISE_GOAL_TOOL`が**含まれないこと**でナローチャネルを機械的に保証）。
- 既存`tests/test_r5_thought_log_freeze_goalshift.py`の5件は無変更で通ることを確認（`_build_agreements_context`/`freeze_agreement`/is_frozenガード自体は触らない）。
- `tests/test_bl062_detector_supersede.py`の`test_bl062_freeze_tool_removed_from_user_ai_tools`は、本来チェックすべき`generate_user_utterance`（tools=[...]の実体）を対象にし、アサーションを反転（`FREEZE_AGREEMENT_TOOL`が**含まれる**ことを確認）、テスト名を`test_bl086_freeze_tool_reactivated_in_user_ai_tools`に変更。同ファイルの他3件は無変更。

全体: `python -m py_compile cela_main.py`、オフラインスモークテスト全件（現在150件+新規十数件）Pass、`python scripts/check_docs_consistency.py`。

### Phase 5: BL/D化（実装完了後）

- `docs/design/issue_backlog.md`にBL-086として起票・`done`化。
- `docs/design/decision_log.md`にD-056〜D-058（またはまとめてD-056）として、(1) ツール呼び出し型エスカレーション採用の理由（decision_extractor推論型より確実）、(2) Freeze復活の経路（revise_goal内蔵＋User AI単独ツールの両方を復活させた理由、D-045を今回どう乗り越えたか）、(3) `state["goal"]`への部分パッチ方式・`shift_kind="premise_revision"`新設の理由を記録。D-045は`superseded`化し、新D番号を指す相互リンクを追加。

## 検証方法

- `python -m py_compile cela_main.py`
- `python -m pytest tests/ -q --ignore=tests/test_f26_detection.py`（既存150件＋新規テスト全件Pass、`test_bl062_detector_supersede.py`の更新後テストも含む）
- `PYTHONIOENCODING=utf-8 python scripts/check_docs_consistency.py`
- 手動統合確認（BL-082のときと同様）: `_escalate_premise_concern_tool_impl`→`_revise_goal_tool_impl`を直接呼び、`state["goal"]`相当の文字列が実際に改定され、対象agreementが`is_frozen=1`になり、その後のSUPERSEDE試行がエラーになることをスクリプトで確認。
- 実LLM再ドライランでの効果確認（Expertが今回のような前提矛盾に気づいた際に実際に`escalate_premise_concern`を呼び、User AIが`revise_goal`で応答し、次のDetector監査が同じ論点を再度major判定しないこと）は次回待ち。
