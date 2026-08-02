# BL-146/BL-147/BL-148 基本設計: BL-125タスク遷移ゲートの内容レベル迂回の解消とOrchestratorのツールループ化

**関連:** [BL-146](../issue_backlog.md#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)、[BL-147](../issue_backlog.md#bl-147-read_deliverable_fileがtask_idの実在チェックを一切行っておらずfile_path併用時は事実上無視される)、[BL-148](../issue_backlog.md#bl-148-orchestratorがcurrent_task_id計画成果物を一切参照できないままexpert選定focus_guidanceを決めていた)、[BL-125](../issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-131](../issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、[BL-109](../issue_backlog.md#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)、decision_log.md D-117・D-118・D-119、decision_lineage.md 論点97・98

**状態:** 全て実装完了（`done`）。

## Context

`log/2026-08-02/0832`ドライランのレビューで、エージェントから「BL-125のブロック表示後もOrchestratorが一時的にtask_1_2の作業を進めた」という気になる指摘があった。ユーザーから「後続タスクが修正されると依存する先発タスクの内容も整理しようとユーザーがしているか、ユーザーが単純にタスク管理ができていないか」という2つの仮説とともに、プロンプトありログでの文脈・DB提示の適切性まで含めた詳細調査の依頼があった。

3体のExploreエージェントによる並行調査の結果、`current_task_id`自体は当該run全体を通じて一度も巻き戻っていないことが判明し、当初の「巻き戻り」という説明は誤りだったと訂正した。実際の原因は以下2系統・3件の独立したバグだった。

1. **Bug A（→BL-146）**: `write_agreement`（`_write_agreement_impl`/`_commit_agreement_from_tool`）は、LLMがツール引数で指定した`task_id`をタスクプランナーの正式な計画に実在するか（BL-131）でしか検証しておらず、`state["current_task_id"]`（BL-125が遷移をブロックしている対象そのもの）とは一切照合していなかった。BL-125がタスク遷移をブロックしていても、Expertは`task_id="task_1_2"`のように任意の他タスクを指定してDeliverableを実際に書き込め（SUPERSEDEを除く）、Detectorがそれを正式な成果物としてレビューしてしまっていた。
2. **Bug B（→BL-147）**: `read_deliverable_file`は`write_agreement`よりさらに検証が甘く、存在しない`task_id`でも素通りする。特に`task_id`と`file_path`を同時指定された場合、`task_id`の実在チェックが一切行われないまま`file_path`側の読み込みに進んでしまう。
3. **Bug C（→BL-148）**: Orchestrator（`call_orchestrator`）はツールを一切持たない単発JSON応答で、プロンプトに`current_task_id`・タスク計画・issue状況が一切含まれていない。専門家選定はユーザーAI/ExpertAIの対話の生テキストのみに基づいて行われるため、対話がtask_1_2寄りに漂うと、`current_task_id`がまだ task_1_1 にピンされていても専門家選定がtask_1_2寄りに引っ張られる。実際、Detector自身がこの矛盾（「現在のタスクがtask_1_2」と言われたのにtask_1_1の受入基準が渡ってくる）を「プロンプトのバグだと思う」と自己申告していたログが残っていた。

ユーザーの仮説については、User AIが`write_issue(action_type="CREATE", task_id="task_1_2", ...)`という形で後続タスクへの申し送りを試みていた形跡（善意の依存関係整理の試み）が確認されたが、正しくは`write_issue(action_type="DEFER", defer_to_task_id=...)`を使うべきところをCREATEで代用しており、ブロック自体は解消されていなかった（ツール誤用であり、単純なタスク管理不能とは異なる）。

ユーザーからの指示: 「見つけたバグはすべて直しましょう」「Orchestratorのツールは必要な情報が見れるツールが渡されていますか？Orchestratorもツールループ化が必要です」。あわせて、「majorとなったissueや後続タスクへの申し送りは、Detector/Reflectorの正当性監査後、タスクプランナー経由で明示的にタスク化した方がissue消化がスムーズになるのでは」という設計提案があり（→ 別スコープとして[BL-145](../issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)へ分離）、意見を求められた。

## 事前調査で確定した事実（Explore + Planエージェント、実ファイル読み込みで検証済み）

- `_get_current_task(state)`（cela_main.py:4586-4596）は`current_task_id`が未設定（空文字、初回task中は常にこの状態——唯一の書き手`_resolve_task_transition`が最初の遷移までまだ発火していないため）の場合、`current_phase`の先頭タスクにフォールバックする。**Fix Aの照合は生の`state["current_task_id"]`ではなく、この実効値を使わないと、task_1_1進行中の正当な書き込みまで全滅する。**
- `TOOL_DISPATCH["write_agreement"]`（2488-2491付近）は`_task_id_from(state)`（`state.get("current_task_id") or _CURRENT_TASK_ID`、LLMがtask_idを省略した場合のみのフォールバック）を使うが、LLMが明示的にtask_idを指定すればそれが無条件で優先される。`TOOL_DISPATCH["read_deliverable_file"]`（2484付近）は当初`state`を一切`_read_deliverable_file_handler`へ渡していなかった。
- `call_orchestrator`は`[{"role":"user","content":prompt}]`という単一userメッセージ形式（`call_facilitator`/`call_integrator`と同型）。`_query_AI_live`の`light_system_prompt`スワップ条件（`loop_messages[0].get("role")=="system"`）はこの形式では常に偽になるため**`light_system_prompt`は元々no-opになる**。Fix Cは`call_expert`のパターンではなく`call_facilitator`/`call_integrator`のパターンを踏襲する。
- `tests/test_bl093_think_tool_scratchpad.py:216-227`の`test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`が`call_orchestrator`をtools=Noneであるべき関数として直接テストしている（BL-126 Stage Dで`call_facilitator`が同じ理由でこのリストから除外された前例あり）。
- `_check_write_permission`のロール表（1770-1784付近）に`"orchestrator"`エントリは存在しない——Orchestratorは元々書き込み系ツールを持つ設計になっていない。
- `decision_extractor_node`が`db_append_agreement()`を直接呼ぶ経路（BL-139のタスク遷移検出の要）は`_write_agreement_impl`を経由しないため、Fix Aの影響を受けない（意図的に対象外）。

## 実装方針

### Fix A（BL-146）: `write_agreement`のDirective/Deliverable書き込みをcurrent_task_idに限定

- 新規ヘルパー `_effective_current_task_id_from(state) -> str`（`_task_id_from`/`_phase_id_from`近傍に追加）: `state`があれば`_get_current_task(state).get("task_id", "")`を返す（`_get_current_task`の既存フォールバックロジックを再利用、二重実装しない）。`state`が`None`なら`_CURRENT_TASK_ID`等の既存グローバルから同等のフォールバックを行う。
- `TOOL_DISPATCH["write_agreement"]`に`effective_current_task_id=_effective_current_task_id_from(state)`を追加。
- `_write_agreement_impl`に`effective_current_task_id: str = ""`パラメータを追加。既存のBL-131実在チェック（`entry_type in ("Directive","Deliverable")`ブロック内）の直後に新チェックを追加:
  ```python
  if args["action_type"] != "SUPERSEDE" and effective_current_task_id and tid != effective_current_task_id:
      return {"success": False, "error": (
          f"task_id '{tid}' は現在のタスク（'{effective_current_task_id}'）と一致しません。"
          "write_agreementのCREATE/UPDATEで書き込めるのは現在進行中のタスクの内容のみです。"
          "他タスクの内容を改訂・訂正する場合はaction_type='SUPERSEDE'を使ってください。"
      )}
  ```
  - `effective_current_task_id and ...`のフェイルオープン設計により、`current_phase`/`phases`を持たない簡易`state`（既存テストのフィクスチャ含む）では従来通りゲートが働かず、既存テストへの回帰を避ける。
  - `action_type == "SUPERSEDE"`は明示的に除外（他タスクの改訂という正当な既存用途、BL-062/080/084を保護）。**プランレビュー時のユーザー確認（後述）に対する回答の通り、「後続タスクで詳細検討した結果、先発タスクの成果物も修正する必要が生じた」ケースはこのSUPERSEDE経路で確保されている。**

### Fix B（BL-147）: `read_deliverable_file`にtask_id実在チェックを追加

- `_read_deliverable_file_handler`のシグネチャに`state: dict | None = None`を追加。`task_id`が指定されている場合、既存の`_find_task_by_id`/`_pending_task_ids_from`（Fix Aと同型のBL-131パターンを再利用）で実在チェックを行い、存在しなければエラーを返す。`file_path`が同時指定されていても、このチェックを`file_path`分岐より先に行うことで、「存在しないtask_idを指定しつつfile_pathで読み込みを通過させる」抜け道を塞ぐ。
- `TOOL_DISPATCH["read_deliverable_file"]`を`lambda args, state=None: _read_deliverable_file_handler(args, state)`に変更し、`state`を実際に渡す。
- 既存タスクの成果物を他タスクから参照読みする用途（本ツールの本来の目的）は制限しない。存在しない`task_id`のみ拒否する。

### Fix C（BL-148）: Orchestratorのツールループ化 + current_task_id可視化

- `call_orchestrator`冒頭で`_CURRENT_CALLER_ROLE="orchestrator"`, `_CURRENT_TASK_ID=state.get("current_task_id","")`, `_CURRENT_PHASES=state.get("phases",[])`をセット（`call_expert`と同型、`READ_PROJECT_PLAN_TOOL`のハンドラがこのグローバルしか見ないため必須）。
- プロンプトに現在タスクの構造化情報を追加: `_build_task_scope_context(state, conn)`から`current_task_json`/`remaining_criteria_text`を取得し、`state.get("current_task_id","")`と併せて明示的にブロック化して注入する。これがDetectorの自己申告した矛盾（「現在のタスク」表示の食い違い）への直接対処となる。`_build_project_plan_toc(_CURRENT_PHASES)`によるプロジェクト計画目次も追加。
- `query_AI`呼び出しを`tools=[READ_PROJECT_PLAN_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_VERIFIED_FACT_TOOL, THINK_TOOL], state=state`付きに変更。`light_system_prompt`はこのメッセージ形式では無効化されるため付与しない。
- 書き込み系ツール（WRITE_AGREEMENT_TOOL等）は意図的に除外：Orchestratorの役割は専門家選定とfocus_guidanceの提示のみであり、`_check_write_permission`のロール表にも`"orchestrator"`は存在しない。読み取り専用に限定することで役割分離を保つ。
- `orchestrator_node`自体は変更不要（`result["expert"]`/`result.get("focus_guidance")`を読むだけの既存コードがツールループ後の最終応答にもそのまま機能する）。

## プランレビュー時のユーザーコメントと回答

Plan mode終了前、ユーザーがドキュメントへ2件のコメントを追加した。

**① Fix Aについて**: 「これは、後続タスクで詳細検討した結果、先発タスクの成果物も修正する必要があった場合の経路は確保されているか？」
→ 確保されている。`action_type="SUPERSEDE"`（BL-062/080/084で実装済み）がまさにこのケースのために存在する既存の正当な経路であり、Fix Aはこれを明示的に除外対象としている。今回塞いだのは「SUPERSEDEという正規の改訂手続きを経ずに、他タスクへ無許可でCREATE/UPDATEしてしまう」抜け道のみ。

**② issue→タスク明示化の記述について**: 「タスク表もホワイトボード化されて、差分書き込みが可能と思っていたが、違うのか？」
→ 2つの異なる層があることが判明した。`plan_drafts`テーブル（「フェーズ・タスク表ホワイトボード」、`apply_plan_patch`経由）は差分/パッチ書き込み可能な文書であり、この認識は正しい。ただし、コード上のゲート（`_find_task_by_id`、BL-125/131の実在チェック等）が実際に信頼する構造データは`state["phases"]`（task_id・依存関係・acceptance_criteriaを持つ本体）であり、これは`task_planner_node`（`state["phases"] = phases`）によりLLMが毎回まるごと再生成する方式のままで、`plan_drafts`のような差分パッチAPIは存在しない。この区別は[BL-145](../issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)の本文へ反映済み。

## テスト

- `tests/test_bl131_write_agreement_task_id_validation.py`: 既存テストは`state`に`current_phase`/`current_task_id`キーを持たないため`effective_current_task_id=""`となりゲートが自動スキップされ、無変更で通過（実行確認済み、9件Pass）。
- 新規 `tests/test_bl146_write_agreement_current_task_gate.py`（6件）: 他タスクへのDeliverable書き込み拒否、SUPERSEDEは対象外、初回タスク（`current_task_id=""`だが`current_phase`の先頭が対象タスク）で正しく許可される回帰防止テスト、ロール非依存の確認、`entry_type="Decision"`は対象外、current_phase不明時のフェイルオープン、を検証。
- 新規 `tests/test_bl147_read_deliverable_file_task_id_validation.py`（6件）: 存在しないtask_id＋file_path同時指定での拒否、実在task_idの他タスク参照読みは許可、pending_task_idsの許可、を検証。
- `tests/test_bl093_think_tool_scratchpad.py`: `test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`から`"call_orchestrator"`をリストから除去。`test_bl126_stage_d_call_facilitator_is_tool_loop_capable`を参考に、新規`test_bl148_call_orchestrator_is_tool_loop_capable`を追加し、4つの読み取り専用ツールが参照され、`WRITE_AGREEMENT_TOOL`が参照されないことをソース検査で固定化。`_NODE_TOOL_NAME_REMINDERS`辞書に`call_orchestrator`エントリを追加。
- 新規 `tests/test_bl148_orchestrator_tool_loop.py`（4件）: current_task_id関連情報のプロンプト参照、読み取り専用ツールのみの`tools=`、`state=state`の受け渡し、`orchestrator_node`の入出力契約不変、を検証。

## 発見された既存テストの回帰と対応

`tests/test_r3_smoke.py::test_bl040_read_deliverable_file_lookup_by_task_id`が、(a) `TOOL_DISPATCH["read_deliverable_file"]`を`state`引数省略で呼んでいた、(b) 存在しないtask_idの期待値が`not_found`だった、の2点でFix Bの新チェックと衝突し失敗した。原因は`pending_task_ids`には`phases`/`current_task_id`/`caller_role`と異なりグローバル変数によるフォールバックが存在しないため。実運用では`query_AI`のツールループが常に`state`を渡すためこの問題は起きないが、このテストだけが旧来の直接呼び出しパターンのままだったと判明し、`state`を明示的に渡す形・新しいエラー期待値（`not_found`→`error`）へ更新した。

## 実装結果

`python -m py_compile`合格。新規テスト16件（BL-146: 6件、BL-147: 6件、BL-148: 4件）追加。フルオフラインスイート596件Pass、`check_docs_consistency.py`合格。D-117（BL-146）・D-118（BL-147）・D-119（BL-148）として記録（あわせて未記入だったBL-144用D-116もこのパスで解消）。issue→タスク明示化の提案自体はBL-145として別スコープに分離し、実装は見送った（`plan_revision_reason`機構とBL-144の滞留検知の再利用を推奨方針として記録）。

`log/2026-08-02/2222`ドライランでの事後検証（decision_lineage.md論点98以降参照）: BL-148は6回のOrchestrator呼び出し全てで`current_task_id`ブロックが正しく注入され、専門家選定がcurrent_task_id（task_1_1）の実際の内容と一貫していることを確認（0832ログで見られた矛盾は再発せず）。BL-146/BL-147はこのランでは他タスクへの誤書き込み/誤読み込みの試み自体が発生しなかったため、ゲートは発火せず未検証（バグが無かったことの確認にはなったが、ゲートの実効性そのものはまだ実ドライランで実証されていない）。
