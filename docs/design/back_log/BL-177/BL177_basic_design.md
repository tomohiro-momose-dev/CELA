# BL-177（User AI部分）: `generate_user_utterance`をDetectorの2段監査パスと同型の段階化構造へ分解する 基本設計

## Context

BL-176（本セッションで実装済み）は、Userが1発言で「現タスクの承認」と「次タスクへの指示」を混在させると、承認の成立確認（`write_agreement`の即時DBコミット＋事後Detector監査）と次タスクへの遷移判定（`decision_extractor`の自由文脈抽出）という2つの独立経路の食い違いにより状態が壊れうる問題に対し、`_resolve_task_transition`への機械的ゲート（事後の安全網）で対応した。

ユーザーはこれをさらに一歩進め、「Detectorが既にドメイン妥当性レビュー→数値検算の2段構成で監査しているのと同じように、User AI側も『レビュー→issue確認→レビュー・issue確認から統合した承認判断→次タスク指示（または現タスク修正指示）』という段階的ワークフローとして、段階ごとにプロンプトを変えながら回せないか」と提案した（BL-177として起票済み、`docs/design/back_log/issue_backlog.md`）。この設計が実現すれば、「次タスク指示」ステージ自体を「統合承認判断ステージがApproved相当と結論した場合のみ起動する」という条件で直列化でき、そもそもLLMに「承認と次指示を同時に言う」余地を与えなくなる——BL-176のゲートが事後に検知・拒否するのに対し、こちらは発生源を断つ。ユーザーの指示（「BL176を実装後、BL177のまずはユーザー部分のステージ化設計を行って」）により、BL-177全体（Expert・Detector等の他ノードも含む一般化）のうち、今回はUser AIの`generate_user_utterance`部分に絞って設計する。

## 前提として確認した既存アーキテクチャ：`call_detector`の2段パス（`cela_main.py:5924-6462`）

これが今回のUser AIステージ化が模倣すべき、実際に動いている唯一の前例。読み取れる設計原則は以下の4点：

1. **物理的に1つの関数の中に、独立した複数の`_query_and_parse_with_retry`呼び出しを直列に並べる**（新しいグラフノードは作らない・グラフの往復は増えない）。ドメインレビューパス（`cela_main.py:6242`）→数値監査パス（`cela_main.py:6394`）の順。
2. **各パスは完全に別のプロンプト文字列とツールリストを持つ**（会話履歴を共有した`messages`配列の継続ではなく、それぞれが独立した1発のプロンプト）。前段の結果は、次段のプロンプトへ**テキストとして埋め込む**だけ（`domain_findings_block`、`cela_main.py:6265-6271`）。
3. **各パスは独立してツール呼び出し（副作用）を持ちうる**——両パスとも`WRITE_AGREEMENT_TOOL`・`WRITE_ISSUE_TOOL`を持つ。ステージ化＝「どのステージが書き込み権限を持つか」を分離することではなく、「判断の観点を分離する」ことが主目的。
4. **最終統合はPythonコード側で行う**（`_severity_order`によるmax集約、`cela_main.py:6418-6424`）。3段目の追加LLM呼び出しで統合させてはいない。

## スコープ：どのターンをステージ化するか

`generate_user_utterance`は現在、通常の「Expertの成果物レビュー」以外に複数の特殊モードを1つの巨大プロンプトに同居させている。ステージ化は**通常モードのみ**に適用し、以下は現状の単発呼び出しのまま温存する（無理に4段へ押し込まない）：

- `essence_dialogue_active`（BL-126 Stage D、`cela_main.py:7335`）: Facilitatorとの本質対話応答。レビュー対象がExpertの成果物ではないため対象外。
- `expert_pending_question`（BL-130、`cela_main.py:7354`）: Expertが質問のみで成果物を出していないターン。
- `state.get("drift_flag") or state.get("constraint_issue") in ["major"]`（BL-142/143、`cela_main.py:7475`）: 直前の自分の発言がDetectorに差し戻された、自己修正ターン。新しいExpert成果物のレビューではなく「自分の前回発言の訂正」なので、レビュー→issue確認→承認判断という段階分けの対象にならない。
- `state["turn_count"] >= max_turns - 2`（`cela_main.py:7496`）: 終盤のPROJECT_COMPLETE宣言。
- `not state["chat_history"]`（初回ターン）: レビュー対象のExpert発言がまだ存在しない。

対象となるのは「Expertが成果物を提出し、Userがそれを評価する」通常ターンのみ。この分岐自体は`generate_user_utterance`冒頭で判定し、非対象時は**現行の単発`query_AI`呼び出しをそのまま残す**（後方互換・低リスク）。

## ステージ設計（4段階、いずれも`generate_user_utterance`内にインライン実装——理由は下記「制約1」参照）

### Stage 1: レビュー（ドメイン妥当性）
- 既存の「【検算とドメインレビューの役割分担】」（`cela_main.py:7299-7321`、数値はDetector済みなのでUserはドメイン妥当性に集中、という既存の役割分担指示）をそのままこのステージの核に据える。
- ツール: `READ_VERIFIED_FACT_TOOL`・`READ_DELIVERABLE_FILE_TOOL`・`THINK_TOOL`のみ（read-only、承認や書き込みはまだ行わない）。
- 出力: `{"domain_concerns": "...", "scope_compliant": true/false, "review_comment": "..."}`

### Stage 2: issue確認
- 既存のissue関連ブロック（BL-096のwrite_issue/read_issues指示、BL-086の未解決エスカレーション強制解決、BL-136/158の`_get_forced_escalated_issues_text`強制解決文言、BL-136の`_build_open_issue_pin_text`/`_build_planned_issue_pin_text`参考表示）をこのステージに集約する。Stage 1の`review_comment`をテキストとして埋め込む。
- ツール: `READ_ISSUES_TOOL`・`WRITE_ISSUE_TOOL`・`ESCALATE_PREMISE_CONCERN_TOOL`・`RESOLVE_PREMISE_CONCERN_TOOL`・`REVISE_GOAL_TOOL`・`FREEZE_AGREEMENT_TOOL`・`THINK_TOOL`。
- 出力: `{"issues_handled": true/false, "remaining_concerns": "..."}`

### Stage 3: 統合承認判断
- Stage 1・Stage 2の結果をテキストで提示し、承認可否のみを判断させる。既存の「厳守事項」（`cela_main.py:7229-7241`、承認基準の厳しさに関する指示）をここへ移す。
- ツール: `WRITE_AGREEMENT_TOOL`・`THINK_TOOL`のみ（このステージだけが承認を確定できる、という単一責任にする）。
- 出力: `{"approval_status": "Approved/Approved_with_Conditions/Rejected/Pending", "approval_reason": "..."}`
- **自己申告とツール呼び出し結果の不一致への対応（設計レビューで発見・修正した論点）**: `approval_status`が承認系（`RESOLVING_DELIVERABLE_STATUSES`）なのに`get_last_write_agreement_succeeded()`が`False`という食い違いを、**LLMにではなくPythonコード側で機械的に判定する**（BL-091「ツール呼び出しを伴わない自己申告を信用しない」・BL-176「LLMの判断を機械的ゲートで裏取りする」と同じ設計原則。Stage 4をこの判定の"監査役"にはしない——Stage 4のLLMは`get_last_write_agreement_succeeded()`を直接参照できず、Stage 3の技術的な成否を正しく検知できる保証がないため）。
  - 不一致を検出した場合、**Stage 4のquery_AI呼び出しは一切行わず**、Python側の制御フローがStage 3のquery_AIを訂正指示付きで再度呼び出す（最大2回、`_query_and_parse_with_retry`のJSONパース失敗リトライと同型の「同一ステージ内リトライ」）。再試行プロンプトには「あなたはApprovedと回答しましたが、write_agreementツールの呼び出しが実際には成功していません。承認を確定するには、必ずwrite_agreementツールを呼び出してください」という具体的な訂正指示を付与する。
  - 当初案（食い違いを検知したら`approval_status`を黙って`Pending`に落としてStage 4の修正指示分岐へ渡す）はレビューで却下した。Stage 3のLLMは「もう承認した」と思い込んだままStage 4へ渡ることになり、Stage 4は「技術的にApprovedが記録されていない」ことを知らないまま、Expertの成果物に対する実質的な修正指示をでっち上げて書いてしまう（＝存在しない欠陥を指摘する矛盾したメッセージがExpertへ送られる）リスクがあるため。
  - リトライを使い切ってもなお食い違いが解消しない場合のみ、Stage 4へは進めるが、`approval_status`を通常の`Rejected`（ドメイン上の却下）とは区別した専用ラベル`"ApprovalRecordingFailed"`として渡す。Stage 4はこのラベルを見た場合、「成果物自体への修正指示」ではなく「承認記録が技術的に完了しなかったため、今回のターンでは進行を見送り、次ターンで改めて承認を試みる」という技術的な待機メッセージを書くよう、専用の分岐プロンプトを使う（Expertへ実在しない欠陥を指摘するメッセージを送らないため）。

### Stage 4: 次タスク指示 / 現タスク修正指示 / 承認記録失敗の待機メッセージ（＝関数の戻り値）
- Stage 3の`approval_status`により3方向に分岐する（同じ関数内のif/elif/else、LLM呼び出しは1回のまま——プロンプト文面を切り替えるだけ）:
  1. `RESOLVING_DELIVERABLE_STATUSES`（`cela_main.py:4004`、Approved/Approved_with_Conditions/Implicitly_Accepted）に含まれる場合: 「次タスクへの指示」プロンプト。
  2. `"ApprovalRecordingFailed"`（Stage 3のリトライを使い切っても自己申告とツール呼び出しが食い違ったまま、上記参照）の場合: 「承認記録が技術的に完了しなかったため、今回は進行を見送り、次ターンで改めて承認する」という技術的な待機メッセージ専用プロンプト。Expertの成果物内容には一切言及させない（実在しない欠陥をでっち上げさせないため）。
  3. それ以外（`Rejected`等、ドメイン上の正当な却下）: 「現タスクへの修正指示」プロンプト。
- ここに、既存の`_build_escalation_resume_notice`（BL-096）・`_build_task_transition_blocked_notice`（BL-125/**BL-176**）・`_build_detector_observations_block`を配置する（次タスクへ進めるかどうかの最終確認に関わる情報のため）。BL-176の通知は、Stage 3が"Approved"と判断していても`_resolve_task_transition`側で改めて機械的に検証される、という二重の安全網として引き続き機能する（Stage 3のLLM自己申告だけに依存しない）。
- ツール: `THINK_TOOL`のみ（この段階では新たな副作用を起こさない。既存の「同じ検証・計算を繰り返さない」指示もここに残す）。
- 出力: 自由文（現行`content`と同じ形式）。これがそのまま関数の戻り値・`chat_history`への追記内容になる。

## 制約1（最重要）：ステージは別関数へ切り出さず`generate_user_utterance`内にインラインで実装する

19個の既存テストファイルが`inspect.getsource(cela_main.generate_user_utterance)`でプロンプト文言の存在・相対順序を検証している（例: `test_bl104_project_plan_toc_and_prompt_reorder.py`のキャッシュ順序テスト、`test_bl136_issue_visibility_and_transition_gate.py`・`test_bl093_think_tool_scratchpad.py`等の文言存在テスト）。各ステージのプロンプト構築ロジックを別のトップレベル関数（例: `_build_review_stage_prompt`）へ切り出すと、その関数内の文字列は`generate_user_utterance`のソースから消え、既存テストが軒並み壊れる。`call_detector`自身も2段パスを別関数化せず単一関数内に直接書いている前例に倣い、**4ステージすべてを`generate_user_utterance`の関数本体内に、明確なセクションコメント区切りで直接記述する**。これにより、文言の「存在」を確認する系のテストは無改修で通る（後述「影響を受けるテスト」参照）。

## 制約2（重大なバグリスク）：ターン単位トラッカーのグローバル変数が「最後のステージ呼び出し」でリセットされる

`query_AI()`は呼び出しのたびに`_LAST_WRITE_AGREEMENT_SUCCEEDED`・`_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED`・`_LAST_REASONING_TEXT`・`_LAST_GOAL_REVISION`・`_LAST_ESSENCE_PROPOSAL`を無条件にリセットする（`cela_main.py:2991-2999`）。`generate_user_utterance_node`（`cela_main.py:7630`）は`generate_user_utterance`が返った**後**に`get_last_write_agreement_succeeded()`等のgetterを呼び、`state["user_wrote_agreement"]`等へ反映する（R3b §3.5.1のAgreement二重書き込み防止、BL-158のissue解決チェック、BL-086のgoal改定、BL-126 Stage Dのessence proposal橋渡しがすべてこれに依存）。

4回`query_AI`を呼ぶ設計にすると、**Stage 2でwrite_issue(RESOLVE)が成功しても、その後のStage 3・Stage 4の`query_AI`呼び出しがこれらのグローバルを再度Falseへリセットしてしまい、ノード側から見えなくなる**（Stage 3のwrite_agreement成功もStage 4の呼び出しで同様に消される）。

**対応方針**: `generate_user_utterance`内で、各ステージの`query_AI`呼び出し直後に該当するgetterをローカル変数へOR集約する（例: `stage_wrote_agreement = stage_wrote_agreement or get_last_write_agreement_succeeded()`）。関数の最後（`return content`の直前）で、集約したローカル変数を対応するモジュールグローバルへ`global`宣言の上で書き戻す。これにより`generate_user_utterance_node`の既存の読み取りコードは一切変更不要になる。`_LAST_GOAL_REVISION`・`_LAST_ESSENCE_PROPOSAL`はbool ORではなく「非Noneの最後の値」を採用する（複数ステージで同時に発生することは想定しないが、防御的に後勝ちとする）。`_LAST_REASONING_TEXT`は「最後に実質的な判断を下したステージ」の理由を代表値とする（Stage 4が自由文を生成しない修正指示分岐の場合はStage 3の理由を、通常はStage 4の理由を採用）——この選択は実装時に再検討可能な軽微な判断のため、設計上のオープン事項として明記するに留める。

## 制約3：BL-104のプロンプト順序テスト群は前提が崩れるため、保存ではなく作り直しが必要

`test_bl104_project_plan_toc_and_prompt_reorder.py`は「1つの`system_prompt`文字列の中での相対順序」を検証している（例: 静的スタンス文が`agreements_text`より前にあること）。ステージ化後は`system_prompt`が1つではなく4つの独立したプロンプト文字列に分かれるため、この前提そのものが成立しなくなる。**これは想定内の破壊的変更**として扱い、「同じ内容を維持しつつテストだけ直す」のではなく、各ステージのプロンプト内で改めてキャッシュ効率の良い順序（固定文言→ステージ内で変動する内容）を設計し直し、テストもステージ単位の順序検証へ書き直す。

## 制約4：LLM呼び出し回数増加（BL-171の無料枠コストとのトレードオフ）

各ステージのツールリストを上記のように最小限・排他的に絞ることで、各ステージのツールループ自体は現行より短く収まる想定だが、`query_AI`の呼び出し回数は最大4倍になる。BL-176実装時と同様、実ドライランでの効果測定時にAPI呼び出し数・所要時間を計測し、許容できない場合は「Stage 1+2統合」「Stage 3+4統合」等の粒度調整を検討する（設計のフォールバックオプションとして記録）。

## BL-176との関係（重複ではなく多層防御）

Stage 3→Stage 4の条件分岐により、通常ターンでは「未承認のまま次タスクへ進む」という状況はプロンプト構造上ほぼ起こらなくなる。しかし以下のケースでBL-176のゲートは引き続き必要:
- Stage 3のLLM自己申告と実際のツール呼び出し結果が食い違うケース（BL-091と同種の虚偽申告リスク）。
- 上記「対象外」の特殊モード（drift/major再送、essence_dialogue等）は今回ステージ化の対象外のままであり、そちらの経路では引き続きBL-176のみが安全網。
- `_resolve_task_transition`は`decision_extractor`という別ノードの独立した抽出結果に基づいて動くため、Stage 4のプロンプトが正しく分岐していても、`decision_extractor`側の抽出ミスは別途あり得る。

したがってBL-176のゲートは**削除・弱化しない**。

## 今回のスコープ外（設計しない範囲）

- Expert・Detector以外の他ノード（Task Planner、Facilitator等）へのステージ化一般化はBL-177の範囲だが、今回はUser AI部分のみ。
- 上記「対象外」の特殊モード自体のステージ化。
- 実装（コード変更）そのもの——本設計はドキュメントとして`docs/design/back_log/BL-177/BL177_basic_design.md`に保存し、実装は別途ユーザー承認を得てから着手する。

## 検証方針（実装着手時）

1. `python -m py_compile cela_main.py`
2. 影響を受ける19ファイルのうち、文言存在チェックのみのテストは無改修で通ることを確認。
3. `test_bl104_project_plan_toc_and_prompt_reorder.py`のUser AI関連テストを、ステージ単位の順序検証へ書き直す。
4. 制約2のグローバル変数集約について、Stage 2でissue解決・Stage 3で承認、という2ステージにまたがる副作用が両方とも`state["user_wrote_agreement"]`・`state["user_wrote_issue_resolution"]`へ正しく反映されることを検証する専用テストを新設する（現状こういうケースを踏むテストが存在しないため、新規カバレッジ）。
4.5. Stage 3の自己申告とツール呼び出し結果の不一致ケース（設計レビューで発見）について、(a) リトライで解消するケース、(b) リトライを使い切り`"ApprovalRecordingFailed"`としてStage 4へ渡るケース、それぞれでStage 4がExpertの成果物内容へ一切言及しない技術的待機メッセージを生成することを検証するテストを新設する。
5. フルオフラインスイート実行。
6. 実ドライランでのAPI呼び出し回数・所要時間の実測（制約4のトレードオフ判断材料）。

## 次のステップ

本設計をレビュー後、`docs/design/back_log/BL-177/BL177_basic_design.md`として保存し、`issue_backlog.md`のBL-177へ「Userステージ化: 設計完了、実装は承認待ち」を追記する。実装はユーザーの明示的な承認を得てから別セッション/別ターンで着手する。
