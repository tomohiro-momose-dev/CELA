# 意思決定の系譜（Decision Lineage）— CELA

**目的:** `decision_log.md` の D-xxx が「何を決めたか（結論）」を簡潔に記録するのに対し、本ファイルは「誰が・なぜ・どういう議論の経緯でその結論に至ったか」を保持する。CELA自体が目指す思想（Lineage-driven：意思決定の系譜を機械的根拠付きで残す）を、開発プロセス自身にも適用したもの。

**運用ルール（[AGENTS.md](../../AGENTS.md) §4.9 準拠）:**

- 1エントリ＝1回のレビュー/議論セッション。時系列で追記（過去エントリは編集しない、訂正は新規エントリで）。
- 各論点で「誰が提起したか」「誰が決めたか」を明記する。AI（Claude等）が提起・提案した内容も、そのまま「AI提起」と書く（人間の発言に偽装しない）。
- 「〜だから」「〜なので」という、事実と決定をつなぐ因果関係の文脈を省略しない。結論だけを書かない。
- `decision_log.md` の `D-xxx` および `issue_backlog.md` の `BL-xxx` と相互リンクする。

---

## 2026-07-18: R2実装計画（ツール呼び出し基盤・機械的検算ゲート）レビュー

**参加者:** t-momose（ユーザー）、Claude Sonnet 5（レビュー実施AI）

**背景:** `cela_phase1_impl_Plan.md` に追記されたR2部分（Function Calling / Python REPLサンドボックス / F-2.6検算ゲート）のレビュー依頼。

### 論点1: Phase 1のゲート状態とR2着手の関係
- **AI提起:** `phase_gates.md` P1-4が未達（BL-002の指標A・B・C実測が未実施）のまま、R2着手前提の計画が書かれている点を指摘。
- **ユーザー報告:** 別チャット（R1ドライラン）で既に、「指標A・B・Cの実測はF-2.6検算ゲート（R2）実装後でないと本質的評価が不可能」という結論に達しており、`decision_log.md` D-002・`issue_backlog.md` BL-002（open→blocked、依存をR2に変更）・`phase_gates.md`（P1-4をR1スコープの構造的一致に絞り、指標A・B・C実測はP2-2としてPhase 2へ引き継ぎ）へ既に反映済みと確認。
- **決定:** Phase 1はR1スコープ（構造的一致）をもって完了扱いとする。**根拠:** 実データドライランで、検算ゲート欠如による差し戻し（numerical_allocatorの暗算的数値提案がdetectorに繰り返し却下される事象）が観測されており、検算ゲートなしで指標A・B・Cを測っても「ゲート欠如の影響」と「R1永続化基盤自体の効果」が混在し分離評価できないため。
- **決定者:** t-momose（別チャットで既に決定、本セッションでは整合確認のみ）
- **関連:** [D-002](decision_log.md#d-002-bl-002指標abcの実測比較はr2f-26検算ゲート実装後に実施する), [BL-002](issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施)

### 論点2: BL-001（Agreement TypedDictの`content`/`rationale`リネーム）の実施タイミング
- **AI提起:** `issue_backlog.md`/impl_Plan §9が「実施判断はR2着手前」と定めているが、R2計画にこの判断が反映されていない点を指摘。
- **ユーザー決定:** BL-001はBLの完了条件通り、R2の頭で実施する。
- **決定者:** t-momose
- **関連:** [D-003](decision_log.md#d-003-bl-001agreement-typeddictのcontentrationaleリネームはr2の頭で実施する), [BL-001](issue_backlog.md#bl-001-agreement-typeddictのcontentrationaleリネーム)

### 論点3: ツール呼び出しループと既存リトライ/バックオフの関係
- **AI提起:** 新設するツール呼び出しループ（R2.3）を既存の`_query_AI_live`の`try/except`リトライ（`delays=[8,16,32,64,128]`）の外側に置くと、一時的なAPIエラーでツールループ全体がクラッシュしうる、という設計上の空白を指摘。
- **ユーザー確認:** 「try中で回し、エラーで再実行（他の再試行動作と同様）にしたほうが良い」という理解で合意。
- **AI補足（一般的な実装パターンとの照合）:** Anthropic公式SDKの`tool_runner`、OpenAI Agents SDKの`Runner`、LangChainの`AgentExecutor`のいずれも「単一の共通ループにツール呼び出しを集約する」方式が主流であり、設計書§3.5.2の`call_expert_with_tools`（ノードごとに個別ループ）はあくまで説明用の最小サンプルだった、という判断材料を提示。ただし業界標準は本来「`create()`呼び出し1回単位」でリトライするのに対し、今回の「既存tryブロックで包む」方式は「ツールループ全体を1単位」としてリトライする点で粒度が粗く、1回失敗すると途中経過（`loop_messages`）を捨てて最初からやり直すことになる、という差分も併せて提示。
- **決定:** ツール呼び出しループは既存`query_AI`の共通層に集約し（設計書§3.5.2の個別ノード実装例からは意図的に逸脱）、既存の`try/except`リトライブロックの内側で回す。リトライ粒度の粗さは実害軽微（MAX_TOOL_ITER=5、ローカル実行のPython REPL自体は失敗しにくい）と判断し、当面は許容する。
- **決定者:** t-momose（AI提案を採用）
- **関連:** [D-004](decision_log.md#d-004-ツール呼び出しループは既存のtryexceptリトライブロック内に配置する)、impl_Plan R2.3、R2.0.1

### 論点4: Detector/ReviewerのJSONパース失敗時のフェイルオープン
- **AI提起:** ツール付与により`use_json_mode=False`となるため、最終応答がJSONとして安定してパースできる保証が弱まる。現状の`_safe_json_parse`フォールバック（Detectorは`{"constraint_issue": "none"}`）は、パース失敗時に「矛盾なし」を静かに返してしまい、F-2.6検算ゲート導入の目的（暗算を信用しない）と逆行する、という点を指摘。
- **ユーザー決定:** JSONパースに失敗した時点で「正しくデータが渡されなかった」とみなし、ノード自体を再試行させる方針に賛成。
- **AI補足:** これは既存の層1リトライ（API呼び出し失敗）とは別の層2リトライ（API呼び出しは成功したがパース失敗）として実装する必要がある、既存の`_safe_json_parse`は例外を投げず黙ってfallbackを返す設計のため層1リトライには乗らない、層2リトライの上限を使い切った場合のfallbackは現状の「none」ではなく「major」側に倒す（フェイルクローズ）べき、という設計を提示。
- **決定:** 層2リトライ＋安全側（フェイルクローズ）収束の方針で確定。
- **決定者:** t-momose（AI提案を採用）
- **関連:** [D-005](decision_log.md#d-005-detectorreviewerのjson判定パース失敗時は層2リトライフェイルクローズとする)、impl_Plan R2.5・R2.6（追記予定）

### 論点5: Python REPLサンドボックスの抜け道
- **AI提起:** 現行案のAST検査は`ast.Import`/`ast.ImportFrom`ノードのみを対象としており、`open(...)`（ビルトイン、import不要）や`__import__('os')`（Callノードでimport文ではない）はノーチェックで通過する。design v7 §3.5.3が求める「os/sys/subprocess等のブロック」を実質的に満たしていない、というセキュリティ上の欠陥を指摘。
- **ユーザー決定:** 実装計画に反映することに賛成。
- **AI提示した対応方針:** (1) `open`/`eval`/`exec`/`compile`/`__import__`/`globals`/`vars`/`getattr`等の危険な名前をAST上の`Name`/`Attribute`参照としてブロックリスト化（呼び出し式全体を検査対象にする）。(2) AST blacklistのみでは既知の回避手法（`().__class__.__bases__`経由等）を完全には塞げないため、実行プロセス自体の権限も絞る多層防御（書き込み不可の作業ディレクトリ、低権限実行等）を併用し、「絶対に破れないサンドボックスではなく多層防御である」という設計上の限界を明記する。
- **決定者:** t-momose（AI提案を採用、実装計画への反映を承認）
- **関連:** [D-006](decision_log.md#d-006-python-replサンドボックスはビルトイン呼び出しのast検査多層防御を追加する)、impl_Plan R2.2（改訂予定）

### 論点6: 許可モジュールリストへの`random`追加の妥当性
- **AI提起:** impl_Planの`_ALLOWED_IMPORTS`が design v7 §3.5.3 の許可リスト（`math, statistics, datetime, json`）を超えて`fractions, decimal, random`を追加している点は、AGENTS.md §7（定数変更の厳格管理）上、未承認の逸脱にあたると指摘。
- **ユーザー質問:** `random`がなぜ問題か（潜在的リスクの内容）を確認。
- **AI回答:** `random`はセキュリティリスク（権限昇格等）ではなく、**検算の決定性を壊すリスク**である。F-2.6の目的は「暗算をせず機械的に検算する」ことだが、検算コードに`random`が混じると同じコードでも実行のたびに結果が変わりうるため、「検算した」という主張自体の信頼性が損なわれる。一方`decimal`/`fractions`は浮動小数点誤差を避けた正確な検算に資する拡張であり、目的に合致する。
- **決定:** `random`はホワイトリストから削除。`decimal`/`fractions`は理由を明記した上でdesign v7側にも反映し維持する。
- **決定者:** t-momose（AI提案を採用）
- **関連:** [D-007](decision_log.md#d-007-python-repl許可モジュールからrandomを除去しdecimalfractionsは理由付きで維持する)、impl_Plan R2.2、design v7 §3.5.3（追記予定）

### 論点7: ツール呼び出しループを`query_AI`に集約する設計（design v7 §3.5.2からの逸脱）の妥当性
- **ユーザー提起:** impl_Plan R2.0.1として、design v7 §3.5.2の`call_expert_with_tools`例（ノードごとの個別ループ）からの逸脱理由（①`query_AI`が既に共通API層である、②DRY・保守性、③Replay境界の維持、④`bind_tools`不使用の踏襲）を文書化して提示。「一般的にはどう作られているか」を確認したいという質問。
- **AI回答:** 集約方式（単一の共通ループにツール実行を集約する）は業界標準の主流である。Anthropic公式SDKの`tool_runner`、OpenAI Agents SDKの`Runner`、LangChainの`AgentExecutor`はいずれも同様の集約方式であり、design v7 §3.5.2のノード別実装例はあくまで説明用の最小サンプルに過ぎない。追加提案として、(a) ツールのdispatch（ツール名→処理のマッピング）をループ本体から分離し辞書化しておく（R3の`write_agreement_tool`追加時にループ自体を変更せずに済む）、(b) リトライ粒度の粗さ（論点3参照）をBLとして一言残しておく、の2点を提示。
- **決定:** R2.0.1の内容のまま採用する（大きな設計変更は不要と判断）。
- **決定者:** t-momose（AIの見解を確認の上、現行案を維持）
- **関連:** [D-008](decision_log.md#d-008-r201ツール呼び出しループをquery_aiに集約する設計を承認)、impl_Plan R2.0.1

### 論点8: design v7 §3.5.2 / §3.5.3 への ★v9 反映（論点5・6・7の決定の実装計画側への反映）

- **AI提起:** 論点5（D-006：ビルトイン呼び出しのAST検査＋多層防御）、論点6（D-007：random除外・decimal/fractions維持）、論点7（D-008：query_AI集約）の決定は、当時の記録では「design v7 §3.5.3（追記予定）」「design v7 §3.5.2からの逸脱」と未反映状態で留められていた。これらを実際の設計書 v7 に反映し、実装計画（impl_Plan）・decision_log・issue_backlog との整合をとる必要がある。
- **ユーザー決定:** 「設計書にない部分の合意・変更等を関連ドキュメントも更新し、整合をとれ」という指示に基づき、design v7 §3.5.2 に query_AI 集約方針の ★v9 追記、§3.5.3 に random 除外・decimal/fractions 維持・危険呼び出し AST 検査・多層防御の ★v9 追記を実施。あわせて issue_backlog.md に BL-006〜BL-009 を新規起票し D-xxx と相互リンク、decision_log.md の更新履歴に反映済みを記録した。
- **決定:** decision_lineage.md 自体は「過去エントリは編集しない」ルール（AGENTS.md §4準拠）により論点5・6・7 を書き換えず、本論点8として時系列追記する。論点5・6・7 の「追記予定」記述は、レビュー当時の未反映状態の歴史的記録としてそのまま残す。
- **決定者:** t-momose（AIの指示に基づき実施、lineageの運用ルールを遵守）
- **関連:** [D-006](decision_log.md#d-006-python-replサンドボックスはビルトイン呼び出しのast検査多層防御を追加する)、[D-007](decision_log.md#d-007-python-repl許可モジュールからrandomを除去しdecimalfractionsは理由付きで維持する)、[D-008](decision_log.md#d-008-r201ツール呼び出しループをquery_aiに集約する設計を承認)、[BL-006](issue_backlog.md)〜[BL-009](issue_backlog.md)、design v7 §3.5.2 / §3.5.3（★v9）、impl_Plan R2.0.1 / R2.2

---

### 論点9: R2ツールループの例外が既存の広い`except Exception`に飲み込まれ原因が隠蔽される

- **AI提起（別チャットのClaude）:** D-004でツールループを既存`try/except`の内側に配置したが、`json.loads(tc.function.arguments)`のパース失敗（LLMの不正なJSON引数）と`MAX_TOOL_ITER`超過の`RuntimeError`（非収束）が、いずれも既存の広い`except Exception as e:`（`cela_main.py:399-405`）に捕捉され、5回のバックオフ（最大約248秒）後に`"(サーバー高負荷によるAPIエラー)"`という誤った診断メッセージで握りつぶされる、という相互作用を指摘。計画（cline作成）にはこの言及がない。
- **ユーザー確認:** 実装コストを上げてでもエラーハンドリングの解像度を高める必要があるという方針に同意（「いずれ指摘の問題に突き当たる」ため）。
- **AI提示した対応方針:** (a) `json.loads`失敗は`json.JSONDecodeError`を個別に捕捉し、例外化せずツール結果としてモデルに返し自己修正させる。(b) 外側`except Exception`を`APIError`/`APIConnectionError`/`RateLimitError`/`APITimeoutError`（`openai`パッケージのAPI関連例外のみ）に狭め、ロジックエラーはバックオフ無しで伝播させる。
- **AI提起（同、追加指摘）:** 既存の非ツールパス（`cela_main.py:394-396`）が持つ`finish_reason == "length"`（出力打ち切り）検出が新設のツールループには欠落しており、`max_tokens`超過によるtool_call引数の途中切れが「壊れたJSON引数」として上記(a)の経路に混入し、真因（トークン予算不足）が隠蔽されると指摘。
- **ユーザー決定:** 提案どおり修正する（(a)〜(c)を実装計画に反映）。
- **決定者:** t-momose（別チャットClaudeの指摘・本セッションAIの対応案をいずれも採用）
- **関連:** [D-009](decision_log.md#d-009-r2ツールループの例外処理を一時的api障害とロジックエラーに区別する)、[BL-010](issue_backlog.md)、impl_Plan R2.3

### 論点10: プロバイダ別Function Calling対応の網羅検証（見送り判断）

- **AI提起（別チャットのClaude）:** 要件定義書v35 付録B.5.3が求める「プロバイダごとのFunction Calling対応事前確認」が計画に存在しないと指摘。`_query_AI_live`がOpenRouter経由で複数バックエンド（baidu/fp8, siliconflow/fp8, wandb/fp8, morph）へ強制ルーティングしており、各バックエンドのtool calling対応が未検証のため、R2.9の指標D（5/5検出）が特定プロバイダに偶然当たっただけの可能性がある、という懸念。AGENTS.mdルール2（外部API使用前のContext7確認）にも該当。
- **ユーザー決定:** モデル・プロバイダ依存であり、現在のMVP的な実装では網羅的な確認は見送り、BL記載に留める。
- **決定者:** t-momose
- **関連:** [D-010](decision_log.md#d-010-プロバイダ別function-calling対応の網羅検証はmvp段階では見送りblに留める)、[BL-011](issue_backlog.md)

### 論点11: B.5.1既知誤判定（Detectorの偽陽性）の非退行テストが未定義

- **AI提起（別チャットのClaude）:** R2.6は付録B.5.1の既知誤判定（Detectorが上限内の数値差を`major`と誤判定するバグ）を修正するプロンプトを復活させるが、R2.9の完了条件（指標D）は「矛盾を仕込んだケースを5/5検出できること」という陽性検出のみを定義しており、「上限内の正当な数値差を誤って`major`と判定しない」という陰性側（偽陽性回避）の非退行テストが計画・`phase1_dryrun.md`のいずれにも存在しないと指摘。
- **AI検証（本セッション）:** impl_PlanのR2.9・R2.10・`phase1_dryrun.md`を確認し、指摘の通り陰性側の基準・テストが欠落していることを確認。R2.5の「数値主張は必ず`python_repl`で再計算してから`major`と判定する」指示とR2.6の「上限内の数値差は矛盾と見なさない」指示は将来調整され得るため、指標Dのテストのみではこのバグの再発を検知できない、という具体的な懸念を提示。
- **AI提示した対応方針:** `test_f26_detection.py`に、上限内の正当な数値差を仕込んだ成果物のテストケースを追加し、「`none`または`minor`と判定され`major`にならないこと」を検証する非退行テストを実装する。R2.9の完了条件表に指標Dと対になる基準として明記し、R2.10のテスト格納先にも追記する。
- **ユーザー決定:** 提案どおり記載する。
- **決定者:** t-momose（別チャットClaudeの指摘・本セッションAIの対応案をいずれも採用）
- **関連:** [D-011](decision_log.md#d-011-b51既知誤判定detectorの偽陽性の非退行テストを指標dと対で追加する)、[BL-012](issue_backlog.md)、impl_Plan R2.6・R2.9・R2.10

### 論点12: `manage_adr`（Codebase Memory MCP）採用の是非

- **ユーザー提起:** ドキュメント整合の負荷（STATUS.md/decision_log.md/decision_lineage.md/issue_backlog.md間の相互リンク維持）を軽減する手段として、JiraのようなPMツールとADR系ツール（`manage_adr`）のどちらが適切かを質問。
- **AI回答:** タスク状態管理（Jira等）と意思決定の記録（ADR）は役割が異なる。`docs/design`が正という既存方針とも整合するADR系（`manage_adr`）をまず試すことを提案。
- **ユーザー確認材料:** Geminiによるweb調査で、`manage_adr`は「D-xxxごとに個別レコードとして登録・検索できる」ものと理解し、実地検証を依頼。
- **AI検証（本セッション）:** D-001〜D-011の要点を`manage_adr(mode='update')`で6セクション（PURPOSE/STACK/ARCHITECTURE/PATTERNS/TRADEOFFS/PHILOSOPHY）文書として登録し、`mode='get'`で永続化を確認、`mode='sections'`でセクション見出し一覧を確認。しかし`search_graph`で個別のD-xxxキーワード検索を試みたところADR内容はヒットせず、`get_architecture`にもADR内容は現れなかった。実態は「プロジェクトにつき1つの固定6セクション文書を丸ごと読み書きする」方式であり、Gemini調査が示唆した個別ID検索の仕組みは存在しないと判明。
- **ユーザー決定:** D-xxxの一覧が出たところで結局`decision_log.md`本体を読みに行くのでは二重管理と同じ、として`manage_adr`の採用を見送る。
- **決定者:** t-momose（実地検証の結果を踏まえた判断）
- **関連:** [D-012](decision_log.md#d-012-manage_adrcodebase-memory-mcpの採用は見送る)

### 論点13: `docs/design`の相互リンク整合性を検証する静的リンタの新設

- **ユーザー提起:** `manage_adr`不採用（D-012）を踏まえ、「ドキュメントが多くて整合が大変」という課題に対し、静的リンタを作ることを提案。
- **AI実装:** `scripts/check_docs_consistency.py`を新設し、markdownリンクのファイル存在確認・GitHub方式スラッグでのアンカー整合確認・`decision_log.md`の決定理由必須チェック・`issue_backlog.md`の優先対応一覧表とBL-xxx詳細セクションの1:1対応確認の4点を実装。
- **初回実行結果:** 18件の不整合を検出。内訳は、(a) 本セッションで作成したリンクの実ミス（`decision_lineage.md`論点1の`D-002`アンカー省略形、`decision_log.md` D-001の`BL-005`アンカー不一致）、(b) 別チャット（cline）が追加したBL-006〜009が優先対応一覧表に未反映、(c) テンプレート由来で`要件定義.md`/`cela_roadmap_vXX.md`という実在しないファイル名を指すリンクが8箇所（実際は`要件定義書_v35.md`/`cela_roadmap_v25.md`）。
- **ユーザー決定:** Cまで含めてすべて修正する。
- **AI対応:** 該当箇所をすべて修正し、再実行で不整合0件を確認。
- **決定者:** t-momose
- **関連:** [D-013](decision_log.md#d-013-docsdesignの相互リンク整合性を検証する静的リンタを新設する)、`scripts/check_docs_consistency.py`

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-07-18 | 初版作成。R2実装計画レビューセッション（論点1〜7）を記録。 |
| 2026-07-18 | 論点8を追記。design v7 §3.5.2/§3.5.3 への ★v9 反映（論点5・6・7の決定の実装計画側への反映）を記録。AGENTS.md §4準拠により論点5・6・7は編集せず時系列追記。 |
| 2026-07-18 | 論点9・10を追記。別チャットClaudeによるR2ツールループの例外処理指摘（D-009、BL-010）とプロバイダ別Function Calling対応の見送り判断（D-010、BL-011）を記録。 |
| 2026-07-18 | 論点11を追記。B.5.1既知誤判定の非退行テスト未定義の指摘（D-011、BL-012）を記録。 |
| 2026-07-18 | 論点12を追記。`manage_adr`の実地検証と採用見送り判断（D-012）を記録。 |
| 2026-07-18 | 論点13を追記。静的リンタ`scripts/check_docs_consistency.py`の新設・初回検出18件の修正（D-013）を記録。 |
