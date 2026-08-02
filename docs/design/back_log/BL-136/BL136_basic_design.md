# BL-136/BL-125 基本設計: issue_log可視化強化・DEFER申し送り・タスク遷移ゲート

**関連:** [BL-125](../issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](../issue_backlog.md#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-096](../issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-134](../issue_backlog.md#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった)、decision_lineage.md 論点90

**状態:** 本設計書の対象範囲（Part A〜D、BL-125・BL-136）は**全て実装完了（`done`）**。

**回収の経緯:** [BL-146] 本ドキュメントは、実装当時（2026-07-30、Plan Modeで3体のExploreエージェントによる調査を経て確定）に作成されたPlan本体を、後日（2026-08-02、back_logフォルダの整理指示を受けて）このセッションで読み取れた内容から復元・保存したもの。実装はこの設計書通りに完了しており、内容自体は当時のものを保っている（要約・改変していない）。

## Context

ドライラン `log/2026-07-30/1236` のレビューで、`issue_log`（BL-096: Detector/User AIが懸念を記録する仕組み）が「起票されるが解決されない」状態であることが判明した。このrunでは7件のissueが起票されたが、`resolved_by`/`resolved_at`が埋まった行は**0件**。BL-134（Expertが24時間365日前提を無根拠に確定値化し、Detectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった）はその一例に過ぎず、原因を調査したところ以下2点の設計上の非対称性が根本原因と判明した。

1. **可視性の非対称**: `status='escalated'`（severity=major・再発2回以上）の行だけが`_build_escalation_pin_text`経由で毎ターンプロンプトに自動表示される。`status='open'`（minor）の行は`read_issues`を能動的に呼ばない限り一切見えない。
2. **強制力の非対称**: BL-086の前提エスカレーション（`escalate_premise_concern`）には`_get_open_escalations_text`が「判断を先送りせず、今回の発言内で必ず解決してください」という明示的な強制文言＋具体的なツール名を伴って毎ターン注入される。一方issue_logのRESOLVE指示は「解消していれば明示的にクローズしてください」という条件付き・任意の文面に留まり、強制力がない。
3. **タスク遷移ゲート（BL-125）が存在しない**: `current_task_id`/`current_phase`の唯一の書き手`_resolve_task_transition`（cela_main.py:7464）は、`issue_log`のopen/escalated状態を一切参照せず、task_planner確定済みのphase/task_idかどうかだけを検証してそのまま遷移を許可している。BL-134の実例では、severity=major・status=escalatedのissueが未解決のままtask_1_1→task_1_2の遷移が起きた。

ユーザーからの指示: (1) minorも表示する、(2) escalated issue_logにもBL-086同様の強制解決文言・毎ターン表示を追加する、ただし(3) フェーズをまたぐ・先送りされるissueもあるため、機械的にスケジュール調整（先送り）できる余地を残すこと。

3点目については、既存のBL-082「申し送り」機構（`entry_type=Directive, status=Deferred, defer_to_task_id=<対象task_id>` → `_append_deferred_note_to_plan`で対象taskの計画文書に追記）が全く同じ思想（強制即時解決ではなく、名指しした将来のtaskへ明示的にハンドオフする）で既に実装・実績がある。issue_logにもこのパターンを流用し、「今すぐ解決」と「明示的に将来のtaskへ先送り」の二択をUser AIに与える設計とする。

## 実装方針

### Part A: minor（open）issueの可視化

- 新規ヘルパー `_get_open_issues(conn, run_id) -> list[dict]`（cela_main.py:2217 `_get_escalated_issues`の直後に追加。クエリは`status='open'`のみ変更した同型）。
- 新規ヘルパー `_build_open_issue_pin_text(conn, run_id) -> str`（`_build_escalation_pin_text`の直後に追加。同じフォーマットだが見出しは強制色を持たせない「ご参考」トーンにする）。
- 注入先: `call_expert`（cela_main.py:5077-5079付近、既存の`escalation_pin`注入のすぐ後）と`generate_user_utterance`（6501-6503付近）。ラベルは`【ℹ️ 未解決の軽微な懸念（参考、issue_log）】`のように、強制色のある`⚠️`と区別する。
- Facilitatorへは注入しない（Facilitatorの役割は「最優先で解消すべき懸念」に絞るという既存設計意図を尊重し、minorは対象外のままとする）。

### Part B: issue_logへのDEFER操作追加（BL-082パターンの流用）

- **スキーマ変更**: `issue_log`テーブルへ`defer_to_task_id TEXT DEFAULT ''`列を追加。既存の`agreements`/`verified_facts`と同じ`PRAGMA table_info`→`ALTER TABLE ADD COLUMN`パターン（cela_main.py:3330-3332付近）を`issue_log`のCREATE TABLE直後に追加するマイグレーション関数として実装。
- **`WRITE_ISSUE_TOOL`のパラメータ拡張**（cela_main.py:671-714）: `action_type`のenumに`"DEFER"`を追加。新規パラメータ`defer_to_task_id`（DEFER時必須、申し送り先の実在task_id）を追加。descriptionに「今すぐ解決できない場合はRESOLVEではなくDEFERで、対応を予定している具体的なtask_idを明示すること。理由もなく無期限に放置することはできない」という説明を追記。
- **`_check_issue_permission`**（1771-1785）: `ALLOWED_ISSUE_ACTIONS_BY_ROLE["user"]`に`"DEFER"`を追加（RESOLVEと同じくuserロールのみ）。
- **`_write_issue_impl`**（2112-2183）にDEFER分岐を追加:
  - `defer_to_task_id`必須チェック、`existing`行必須チェック（RESOLVEと同様）。
  - 対象task_idがtask_planner確定済みの計画に実在するか検証（`_resolve_task_transition`と同じ実在チェックロジックを再利用、無効なら失敗を返す）。
  - `issue_log`の該当行に`defer_to_task_id`をUPDATE（statusは変更しない＝open/escalatedのまま）。
  - 既存の`_append_deferred_note_to_plan`（3628）をそのまま呼び出し、対象taskの計画文書へ申し送りを追記する（BL-082と全く同じ経路を再利用）。

### Part C: 強制解決文言の追加（BL-086パターンの流用、DEFER逃げ道つき）

- 新規ヘルパー `_get_forced_escalated_issues_text(conn, run_id) -> str`（`_get_open_escalations_text`, 3751-3773と同型）。対象は`status='escalated'`かつ`defer_to_task_id=''`の行のみ（既に先送り済みのものは対象外）。
- 文言は`_get_open_escalations_text`と同じトーンで統一:
  > 「【⚠️ BL-096: 未解決の重大issue（今回必ず対応してください）】...write_issue(action_type="RESOLVE", topic="...", resolution_note="...")で解決するか、今このタスクで対応すべきでない場合はwrite_issue(action_type="DEFER", topic="...", defer_to_task_id="...", ...)で対応予定のtaskを明示してください。理由なく放置することはできません。」
- 注入先は`generate_user_utterance`のみ（RESOLVE/DEFERを呼べるのはuserロールだけのため、Expertに強制しても実行手段がない）。既存の`_build_escalation_pin_text`によるpinとは別に、この強制文言ブロックを追加する（cela_main.py:6501-6503付近、`_get_open_escalations_text`の注入パターン踏襲）。
- 既存の受動的な`_build_escalation_pin_text`によるpinは残す（Expert側は今まで通り「参考情報」として見るだけで十分。強制はUser AI側のみに集中させる）。

### Part D: BL-125 — タスク遷移ゲート

- 新規ヘルパー `_get_blocking_issues_for_transition(conn, run_id, departing_task_id) -> list[dict]`: `status in ('open','escalated') AND severity='major' AND last_seen_task_id=? AND defer_to_task_id=''`で該当issueを取得。
  - severity='major'のみを遷移ブロック対象とする（minorはブロックせず、Part Aの可視化のみで十分という整理）。
  - `defer_to_task_id`が設定済み（Part Bで明示的に先送り済み）のものはブロック対象から除外＝「今すぐ解決 or 明示的に先送り」のどちらかが済んでいれば遷移を許可する。
- `_resolve_task_transition`（7464-7500）冒頭に、関数の現在の`state["current_task_id"]`（＝離脱しようとしているtask）を使ったゲートチェックを追加:
  - ブロック対象issueが存在する場合、遷移を**適用せず**（既存の「存在しないtask_id」拒否と同じフェイルクローズパターン）、警告printと共に`state["task_transition_blocked_issues"]`（ブロックしたissueのtopic一覧）をセットして関数を抜ける。
  - 次のUser AIターンのプロンプトで、このフラグを検知したら「直前の発言は次タスクへの移行として解釈されましたが、以下の未解決issueがあるため移行をブロックしました：<topic一覧>。write_issue(RESOLVE)かwrite_issue(DEFER)で対応してください」という明示的な差し戻しメッセージを注入する（`_build_escalation_resume_notice`と同じ「one-shot注入して消費後クリア」パターンを踏襲した新規ヘルパーを追加）。

## 変更対象ファイル

- `cela_main.py`: 上記Part A〜D（スキーマ移行、WRITE_ISSUE_TOOL、`_check_issue_permission`、`_write_issue_impl`、新規ヘルパー群、`call_expert`/`generate_user_utterance`/`_resolve_task_transition`への注入）。
- `tests/`: 新規テストファイル（またはtest_bl096系への追加）— DEFER操作の権限・実在チェック・plan_drafts追記、開いているissueのpin、強制文言の注入、`_resolve_task_transition`のゲートブロック/許可の両方（defer_to_task_id設定済みなら通る）を検証。
- `docs/design/back_log/issue_backlog.md`: BL-125を`open`→実装済みへ更新、BL-134に「対応済み」追記、新規BL（もしあれば）起票。
- `docs/design/decision_log.md`: D-xxx（DEFERアクション追加の設計判断、ゲートのスコープをseverity=major・departing task限定にした理由、BL-082パターン再利用の判断）。
- `docs/design/decision_lineage.md`: 本セッションの議論（「issueが活発に使われなくなった理由」の調査から今回の対応方針まで）を1エントリとして記録。

## 検証方法

- 各ステップ後 `python -m py_compile cela_main.py`。
- 新規/既存テスト: `tests/test_bl096*`（存在すれば）、`tests/test_bl125*`（新規）、加えて`_resolve_task_transition`の既存呼び出し元に影響が出ていないか`tests/test_bl087_*`等の関連テストを実行。
- 最終的にフルオフラインスイート（`pytest tests/ -q --ignore=tests/test_f26_detection.py`）を1回実行し、既存挙動への回帰がないことを確認。
- `python scripts/check_docs_consistency.py`で最終確認。
- 可能であれば、BL-134の実インシデントを模したシナリオ（severity=major issueを未解決のままtask遷移を試みる）を軽量な単体テストとして再現し、ゲートが実際にブロックすることを確認する。

## 実装結果（要約、詳細は issue_backlog.md BL-136/BL-125 参照）

新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`（28件、BL-134実インシデント再現含む）を追加、既存`test_r3_smoke.py`のBL-039テスト2件をDB接続前提の変更に合わせて修正。`python -m py_compile`合格、フルオフラインスイート542件Pass、`check_docs_consistency.py`合格。D-108（DEFER操作の設計、BL-082パターン再利用）・D-109（ゲート対象をraised_by不問でseverity='major'に統一する判断）として記録。
