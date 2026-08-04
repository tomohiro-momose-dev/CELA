# 実装 Backlog — FEATURE_NAME

**実装タスク・バグ・未確定の実装事項**（BL-xxx）を管理する。要件定義の正ではない。

| 種別 | 正しい参照先 |
|------|-------------|
| 要件・背景・完了条件 | [要件定義書_v35.md](../要件定義書_v35.md) |
| Phase 詳細設計 | [r0_planning/](../r0_planning/) [r1_r2_r3b_core/](../r1_r2_r3b_core/) |
| 意思決定（なぜ） | [decision_log.md](../decision_log.md) |
| 索引 | [README.md](../README.md) |

---

## 凡例

| 状態 | 意味 |
|------|------|
| `open` | 未着手・未確定 |
| `blocked` | 他タスク完了待ち |
| `done` | 確定・完了 |

| 優先度 | 意味 |
|--------|------|
| P0 | 次マイルストーン前に必須（動作破綻） |
| P1 | Phase 完了前に対応 |
| P2 | 後続 Phase で確定 |
| P3 | 改善・削除候補 |

---

## 優先対応一覧（記入）

| ID | 重要度 | 対象 | 概要 | 優先度 |
|----|--------|------|------|--------|
| BL-001 | 中 | `cela_main.py` (Agreement TypedDict) | ~~`content`/`rationale`を`decision_what`/`reason_why`にリネームし、R1ラッパーのマッピングを除去~~ → `done`（R2実装） | P1 |
| BL-002 | 高 | `cela_main.py` (R1全体) | 構造的一致は確認済み（T-5）。評価メトリクスA・B・C（設計書§5）の実測比較はR2（検算ゲート）実装待ち（D-002） | P0 |
| BL-003 | 中 | `cela_main.py` (Record&Replayスタブ) | ~~実LLM応答を使ったrecord→replay往復検証（impl_Plan §7.2合格基準1・2）未実施~~ → `done`（T-5） | P1 |
| BL-004 | 低 | `cela_main.py` (死んだimport) | `from secrets import choice`、`from unittest import result` の未使用import除去 | P3 |
| BL-005 | 高 | `cela_main.py` (`build_graph()`既存トポロジ) | `state["turn_count"]`が`app.invoke()`1回の間凍結され、外側ループの「Nターン目」表示・上限が実際の対話ラウンド数と一致しない。**副作用として`reflection`/`facilitator`が事実上発火不能**（2026-07-19実ログで確認） | P2 |
| BL-006 | 中 | `cela_main.py` (`query_AI`) | ~~R2 ツール呼び出しループの`query_AI`集約実装（D-008）~~ → `done`（R2実装） | P1 |
| BL-007 | 高 | `cela_main.py` (`_run_python_repl`) | ~~R2 Python REPL サンドボックスの多層防御・危険呼び出し AST 検査（D-006）~~ → `done`（R2実装） | P1 |
| BL-008 | 低 | `cela_main.py` (`_ALLOWED_IMPORTS`) | ~~R2 許可モジュールから`random`を除去、`decimal`/`fractions`は理由付き維持（D-007）~~ → `done`（R2実装） | P2 |
| BL-009 | 低 | `cela_main.py` (`query_AI`ツールループ) | ~~R2 ツールループのリトライ粒度（層1/層2）の粗さを許容する（D-004）~~ → `done`（`[CONSTRAINT]`コメントで明示済み） | P3 |
| BL-010 | 高 | `cela_main.py` (`_query_AI_live` ツールループ) | ~~ツールループの例外（壊れたJSON引数・非収束・truncation）が既存の広い`except Exception`に飲み込まれ原因が隠蔽される（D-009）~~ → `done`（R2実装） | P1 |
| BL-011 | 中 | `cela_main.py` (`_query_AI_live` プロバイダルーティング) | OpenRouter経由の複数バックエンドでのFunction Calling対応状況が未検証（D-010、MVPでは見送り） | P2 |
| BL-012 | 高 | `tests/test_f26_detection.py` (R2) | ~~B.5.1既知誤判定（Detectorの偽陽性）の非退行テストが指標Dと対で定義されていない（D-011）~~ → `done`（テスト実装済み。実LLM実行で指標D 5/5・5/5・非退行3/3を確認、T-7） | P1 |
| BL-013 | 高 | `cela_main.py` (`PYTHON_REPL_TOOL`) | ~~実LLM実行でDetectorが`print()`なしの裸の式を繰り返しツール呼び出しし非収束・テスト失敗~~ → `done`（ツール説明文修正後の再実行で非収束0件、T-7） | P1 |
| BL-014 | 高 | `cela_main.py` (`_run_python_repl`, `_PythonReplSession`, `_query_AI_live`) | ~~本番ドライラン（Expertノード）で非収束クラッシュ。原因A)状態非保持のNameError、B)絵文字printのUnicodeEncodeError、C)MAX_TOOL_ITER不足~~ → `done`（A: 対話的セッション化、B: `-X utf8`、C: 暫定10。オフライン確認済み、実LLM再ドライラン待ち） | P0 |
| BL-015 | 中 | 新機能（未着手、設計要） | 資料由来の一次情報・python_repl出力を構造化データとして機械的に再利用し、LLMの記憶転記に頼らずハルシネリスクを下げる（再利用スコープはノード内限定が有力案） | P2 |
| BL-016 | 高 | `cela_main.py` (`call_detector`, `_query_AI_live`) | ~~本番ドライランでExpertが探索的タスク（車両配車の組合せ最適化）に入り、Detectorの完全性判定の硬直性から10回ツール呼び出しを使い切り非収束クラッシュ。実質的な結論はiter=9で出ていた~~ → `done`（残りiter通知の注入＋Detector完了度判定の緩和。オフライン確認済み、実LLM再ドライラン待ち） | P0 |
| BL-017 | 中 | `cela_main.py`（`facilitator_node`のトリガー拡張＋プロンプト再設計） | 「差し戻しループ沼」からの脱出機構。トリガー未実装に加え、現行`call_facilitator`は当初意図の「ゴール抽象化・そもそも論」ではなく穏やかな論点提示に留まる。「生産的な反復」と「本当の膠着」の区別が鍵 | P2 |
| BL-018 | 中 | `LineageState`（`current_task_summary`, `whiteboard_drafts`） | task_plannerが生成するタスク間の依存関係が状態に構造化されておらず、User AI/orchestratorが横断的な影響を判断できない（フェーズ・視座は既存、タスク粒度の依存関係のみが未構造化） | P2 |
| BL-019 | 高 | `cela_main.py` (`query_AI`/`_query_AI_live`) | ~~OpenRouterのreasoningパラメータをフラットな`reasoning_effort`キーで送っており無効（サイレントに無視、reasoningが一切発火していなかった）~~ → `done`（ネストした`extra_body["reasoning"]["effort"]`に修正、ツール付与ノードにも付与し思考過程をログ出力） | P1 |
| BL-020 | 中 | `cela_main.py` (`_query_AI_live`, `_inject_japanese_output_directive`) | ~~中国語系モデル（DeepSeek）経由のため、まれに中国語（まれに英語）で出力されることがある~~ → `done`（`query_AI`集約点で全呼び出しに日本語出力の指示を強制注入） | P2 |
| BL-021 | 中 | `cela_main.py`（`call_task_planner`等プロンプト生成関数11箇所） | 全プロンプトが日本語で書かれており、中国語系モデルへの指示としては非English言語である分、理解精度・言語逸脱（BL-020）両面で不利な可能性。プロンプト自体の英語化は未着手 | P2 |
| BL-022 | 高 | `cela_main.py` (`_query_AI_live`) | ~~OpenRouter経由の一部プロバイダが壊れた/途中で切れたレスポンスを返すと、openai SDK内部の`response.json()`が生の`json.JSONDecodeError`を送出し、D-009の絞り込んだexceptに含まれず未捕捉クラッシュ（実機ドライランで発生）~~ → `done`（exceptタプルに`json.JSONDecodeError`を追加、オフライン確認済み） | P0 |
| BL-023 | 高 | `cela_main.py` (`call_task_planner`, `generate_user_utterance`)、`要件定義書_v35.md`関連 | task_plannerの分解粒度が粗く、独立検証可能な複数の主張（車両台数・初期費用・ランニングコスト・感度分析等）が1タスクに束ねられ、R4未実装（差分パッチなし）と相まって検証コストが乗算的に増大。Phase A（task_planner/User AIのスコープ是正）は`done`、Phase C（予算カスケード）は未着手 | P1 |
| BL-024 | 高 | `cela_main.py` (`LineageState["current_phase"]`, `decision_extractor_node`) | ~~`current_phase`が初期化時（`phases[0]`）に一度セットされたきり以降更新されず、`task_id`単位の状態追跡も存在しない（BL-005と同型の初期化後フリーズ）~~ → `done`（`decision_extractor_node`を唯一の書き手とし、フェイルクローズ検証つきで実装） | P1 |
| BL-025 | 高 | `cela_main.py` (`call_expert`, `query_AI`/`_query_AI_live`) | 実ドライラン（`log/2026-07-20/1204`）で、`generate_user_utterance`はtask_1_1のacceptance_criteria範囲を守れていたのに対し、Expertは他タスク（task_2_2/task_4_1）が`owns_variables`として所有する車両台数・予算内訳・サイクルタイムまで自発的に計算し、ツールループが10回で非収束クラッシュ。①Expertへのスコープガードレール注入、②ツールループ2周目以降のsystem_promptを現在タスクのみに軽量化、の2案を実装 | P1 |
| BL-026 | 低 | `cela_main.py` (`call_orchestrator`) | 専門家名を固定16種の配列（`valid_experts`）に限定していたが、グラフ・`call_expert`のどちらも具体的な専門家名で分岐しておらず、単なるプロンプト埋め込みラベルに過ぎないことが判明。無用な足かせと判断し、orchestratorがタスクに即した専門家の肩書きを自由記述で生成する方式に変更 | P3 |
| BL-027 | 低 | `cela_main.py`（モジュールトップレベル、`MultiLogger`起動箇所） | `sys.stdout = MultiLogger()`がモジュールのトップレベルにあり、`import cela_main`するだけで本番`log/`配下に新規タイムスタンプディレクトリが作成される事故（実ドライラン中にセッション内のオフラインスモークテストが1455・1458を誤生成）。`if __name__ == "__main__":`ブロック内に移動して修正 | P3 |
| BL-028 | 中 | `cela_main.py` (`_query_AI_live`, `MAX_TOOL_ITER`) | 実ドライラン（`log/2026-07-20/1421`）でtask_2_2のExpert(logistics_manager)呼び出しが`iter=10/tool_calls=9`とMAX_TOOL_ITER上限ぎりぎりで終了（クラッシュはしなかったが余地なし）。1タスク自身の範囲内の検算だけでも上限に迫るケースがあることが判明し、まずクラッシュ回避を優先してMAX_TOOL_ITERを10→15に引き上げ | P1 |
| BL-029 | 中 | `cela_main.py` (`call_decision_extractor`のexpert向けrole_instruction) | `verified_facts`の`operation_schedule`（task_2_2）で、1回目は簡潔な要約が保存されたが、2回目（承認版）はレポート全文（数千文字）がそのまま保存される事故が発生。`content`（Deliverable本体）向けの「絶対に要約しないこと」指示が`owned_variable_values`にも波及したことが原因。`owned_variable_values`は`content`と目的が異なる（依存タスク参照用の簡潔な要約）ことを明記するプロンプト修正で対応 | P2 |
| BL-030 | 低 | `cela_main.py` (`call_decision_extractor`, `decision_extractor_node`) | BL-029の議論から派生。`owned_variable_values`を、依存関係参照専用の独立した「要約レポート」フィールドとして明示的に切り出す拡張案。`decision_extractor`が将来ノード自身のファイル出力機構に伴い補助的役割へ縮小していく設計と合わせて再検討する（現時点では未着手、設計相談段階） | P3 |
| BL-031 | 低 | `cela_main.py`（各ノードのプロンプト構築箇所、DB合意事項テキスト・Recent Decisions再掲・task_planner出力JSON等） | OpenRouter実績（直近24時間で4.6Mトークン、キャッシュヒット率19.7%、コスト$0.65）を確認したところ、ヒット率が低め。DB合意事項・Recent Decisions再掲・5フェーズ分のtask_planner JSON等、Decisionが1件増えるたびに末尾が変わる可変ブロックがプロンプト先頭付近に混在しており、プレフィックスキャッシュが毎ターン壊れている可能性。プロンプト構造を「安定した固定部分を先頭、変化する部分を末尾」に整理しキャッシュヒット率を上げる余地がある（MVP完成後のコスト最適化枠、現時点では未着手） | P3 |
| BL-032 | 中 | `cela_main.py` (`call_decision_extractor`のUser直後role_instruction、`decision_extractor_node`) | 実ドライラン（`log/2026-07-20/1421`）で、task_2_3のDeliverable（親レポート）は承認されたが、同じAgent提出に含まれる4件のDecision（予約チャネル按分比率・電話予約システム設計・対面相談所端末設計・運用コスト概算）はProposedのまま永久に取り残され、以降全ターンの「合意・決定事項・検討状況DB」に🤔として再掲され続けていた。承認時の`target_topic`が単数指定でしかなく、同一task_idの兄弟トピックへの承認カスケードがないことが原因。同一task_id内でも、同ターンのDetector判定（`constraint_issue`/`task_criteria_status`）が清浄な場合のみ機械的にカスケードする設計（未検討事項の隠蔽を防ぐガード付き）で対応予定（現時点では未着手、設計確定・承認済み） | P2 |
| BL-033 | 高 | `cela_main.py` (`_query_AI_live`, `call_detector`, `expert_node`, `detector_node`, `LineageState`) | 実ドライラン（`log/2026-07-20/1421`）でExpert(legal_advisor)がpython_replを一度も使わず（`tool_calls=0`）に「全ての検算が完了した」と虚偽の自己申告をした事故を発見（後段のDetectorが独立検算し実害はなかった）。①Expertが実際に実行したpython_replのcode/resultを`state["expert_last_python_calls"]`として保存しDetectorのプロンプトに提示（Expertの自己申告を鵜呑みにさせない）、②ExpertとDetectorの両方が同一ターンでpython_repl未使用だった場合のみ強制的に`constraint_issue=major`でフェイルクローズ（本当に計算不要なケースを巻き込む無限ループを避けるため「両方0回」の複合失敗に限定）、の2点を実装・スモークテスト済み | P1 |
| BL-034 | 低 | `cela_main.py` (`decision_extractor_node`) | ユーザーが実ドライラン（`log/2026-07-20/1421`）のtask_6_3で、Expertの最終計画書提出をDetectorが通した直後、`decision_extractor_node`（`entry_type=="Deliverable" and action_type=="CREATE"`）がDB上の`status`（Proposed/Approved）を問わず無条件でファイル保存する（`cela_main.py:2812-2827`）ことを発見。ユーザー承認（次ターンのUser AIの受諾表明によるUPDATE/status=Approved）より前に物理ファイルが確定してしまい、却下・修正時に旧版が孤児ファイルとして残る（task_2_2で既に2版が実例として残存）。`integrator_node`は`status=="Approved"`のみを集約するため正当性は壊れていないが、ディスク衛生・監査上の設計課題として記録。R4（ホワイトボード化・md差分読み書き、D-018）で自然に解消される見込みのため、現時点では実装を見送り記録のみ | P3 |
| BL-035 | 高 | `cela_main.py` (`_build_task_scope_context`) | 実ドライラン（`log/2026-07-20/1421`）のtask_6_3（総合導入計画の完成）で、Expertがピーク輸送力を誤計算（60÷13.8×9×3=117人/時と主張、正しくは60/13.8×9=39.1人/時でピーク需要66.7人/時を下回る）しDetectorに差し戻された事例をユーザーが発見。検算の結果、これは別フェーズ（task_2_1）確定済みの車両台数がピーク需要を満たせていないという根深い問題だったが、`_build_task_scope_context`（`cela_main.py:1306-1311`）が`state["current_phase"]["tasks"]`のみを走査するため、フェーズをまたぐ`depends_on`参照（task_6_3→task_2_1）が構造的に解決不能で、Expertは根拠の確定値にアクセスできないまま差し戻しを繰り返すリスクがある。`expert_retry_count>=3`で`reflection`に丸投げされるが収束は保証されない。即応パッチ（`state["phases"]`全体を走査するよう修正）ではなく、F-3.8（自律的DB/ファイル読み取りツール、要件定義書v35.1新規）実装時にまとめて解消する方針（D-032）。現時点では実装せず記録のみ | P2 |
| BL-036 | 中 | `cela_main.py`（`decision_extractor_node`の統合パス、task_6_3系ペルソナ） | ユーザー依頼により`log/2026-07-20/1421`の全21成果物ファイルを内容面でレビューしたところ、「最終計画書」の財務・需要数値が統合パスのたびに再ドリフトしていることを発見。年間ランニングコストがPhase 3承認値（task_3_2、2,541万円・補助金使用率4.70%）に対し、Ver.1.0/1.1（3,000万円・20.00%）、logic_verifierの完了報告（2,980万円・19.33%）と、統合の都度異なる数値になっており、赤字額は最大4.26倍の開きがある。需要側も同様にtask_1_1確定値（総人口5,000人・1日総需要400人/日）から、最終盤で「人口5,200人・1日総需要200トリップ/日」へ根拠なくドリフトしていた（Detector自身がこの乖離を検出し`minor`判定で通過させていた）。原因はBL-035と同一（統合パス担当ペルソナが承認済み根拠ファイルを実際に読み返す手段を持たず、その場で数値を再構成している）で、独立した新規欠陥ではなくBL-035／F-3.8の射程がコスト・需要計算にも及ぶことを裏付ける実例。ユーザー判断により、これは既知の根本原因（読み取りツール欠如）から予想される結果であるため参考記録に留め、F-3.8実装後に読み取りアクセスを持った状態で再度Phase 6を走らせて初めて実効性を評価する方針とし、現時点では独立の緊急対応は行わない | P2 |
| BL-037 | 中 | `cela_main.py`（`call_decision_extractor`のDecision/Agreement抽出プロンプト） | ユーザーが「decisionなどある程度記憶の外部化ができているが、理由の記載が甘い」と指摘し、`log/2026-07-20/1421`のDetector自身の思考ログに、後から確認しようとした数値の根拠を辿れず「根拠が不明」「以前のタスクで設定された数値かもしれないが根拠が不明」と繰り返し書かれている箇所（対象人口5,200人vs5,000人、1周回15分、80km/ルート、電話対応所要時間7.5時間/日等）を確認。原因は2種類：①`80km/ルート`等の中間的な計算仮定はExpertの自由記述レポート内に埋め込まれるのみで、そもそも`decision_extractor`が個別のDecision/owns_variableとして抽出しておらず`reason_why`欄自体が存在しない、②`最適導入台数は3台`のように実際にDecision化された項目でも`reason_why`が結論の言い換え程度に留まり、前提・出典・棄却した代替案までは記録されないケースがある。根本原因はBL-034〜036と同系統（後から参照可能な情報の粒度不足）だが、対象がファイル読み取りではなく`reason_why`欄の記載品質・抽出粒度自体である点で異なる。ユーザー判断により、まずBL記載のみに留め、F-3.1〜F-3.7（エージェント自身の自律書き込みツールへの移行、`decision_extractor_node`の縮小・撤廃）着手時にあわせて理由記載の強制粒度を再設計する方針とし、現時点ではプロンプトの単体強化は行わない | P2 |
| BL-038 | 高 | `cela_main.py` (`LineageState`、`decision_extractor_node`、`expert_node`) | ~~R3b実装後の実ドライランで、Expertの`write_agreement`成功後も`decision_extractor_node`のAgreement抽出がスキップされず二重書き込みが発生~~ → `done`。R4実装後のドライランでDBを直接クエリしWHITEBOARDポインタがプレーンテキストで上書きされる実害を確認、根本原因はLangGraphが`LineageState`（TypedDict）に未宣言のキー（`expert_wrote_agreement`等）をノード間で伝播しない仕様と特定（D-038）。`LineageState`へのフィールド追加とdecision_extractorフォールバックへのWHITEBOARD保護を実装、オフラインスモークテスト66件Pass | P1 |
| BL-039 | 高 | `cela_main.py` (`_resolve_task_transition`, `_get_current_task`, `call_decision_extractor`) | ~~実ドライラン（`log/2026-07-21/2248`）で、`decision_extractor`が出力する`advances_to_task_id`がドット表記（`task_1.1`等）である一方、`call_task_planner`が生成する実際の`task_id`はアンダースコア表記（`task_1_1`等）であるため、`_resolve_task_transition`の存在チェックに毎回失敗し、タスク遷移が1回も成功していなかった~~ → `done`（`_resolve_task_transition`にドット→アンダースコア正規化を追加、`call_decision_extractor`に全task_id一覧を提示してLLMに正確な表記をコピーさせる誘導を追加） | P0 |
| BL-040 | 高 | `cela_main.py` (`read_deliverable_file`, `_read_deliverable_file_handler`, `_commit_agreement_from_tool`) | ~~実ドライラン（`log/2026-07-21/2248`）で`read_deliverable_file`呼び出し31回中21回（約68%）が`not_found`。ファイル名がトピック文字列＋Unixタイムスタンプで一意に決まりAIが予測できないため、`file_path`直接指定への依存が実質的な発見不能性を招いていた~~ → `done`（`task_id`/`topic_keyword`引数を追加し、agreements DBの`FILE_PATH:`ポインタから実際のパスを逆引きする方式に変更。あわせてagreements.task_id列が`args.get("task_id")`のみに依存し、LLMが省略すると逆引きできない問題も`_CURRENT_TASK_ID`フォールバックで修正） | P1 |
| BL-041 | 高 | `cela_main.py` (`arbiter_node`, `check_global_constraint_overrun`, `global_constraints`) | ユーザーが「task_1.1で車両台数4台を決定し予算1億円を使い果たした後、システム開発費等の算出でこの決定をどう覆すか」と問いかけたことを契機に調査。`state["global_constraints"]`は`task_planner_node`での初期化（`[]`）以外に実際のクレームデータを書き込む箇所がコードベース中に一切なく、`check_global_constraint_overrun`は常に空リストを走査するため超過を検出できない。実ドライラン全文検索でも`[Resource Arbiter]`・`[facilitator]`・`[reflection]`・`phases_to_revise`はいずれも0件で、この調停機構は設計上は存在するが**実際には一度も発火し得ない死んだコードパス**であることを確認した。今回のドライランでは幸い、task_1.2が自タスクのacceptance_criteria（「予算超過時の調整案が検討されている」）内で帳尻を合わせた（残額わずか42万円）ため実害はなかったが、これは偶然であり、一度確定した決定（`vehicle_count=4`等）を後続タスクの発見（コスト不足等）を根拠に体系的に再検討させる自動メカニズムは現状存在しない。`write_agreement`のSUPERSEDE機構自体はあるが、BL-025のスコープガードレールによりExpertは自タスク外の合意を書き換えない設計のため、これも自動トリガーにはならない。設計判断が必要な項目（`global_constraints`への`resource_claims`集約タイミング、`reflection_interval`とarbiter発火条件の関係）のため、現時点では記録のみで実装は見送り | P1 |
| BL-042 | 中 | `cela_main.py` (`call_detector`のconstraint_issue判定プロンプト) | R4実装後の実ドライラン（`log/2026-07-22/1804`）で、Detectorのconstraint_issue判定（minor/major境界の運賃単価矛盾）が同じ論点をiter=8〜9以上再検討し続け、同一のpython_replコードを重複実行するなど非効率にトークンを消費していたことを発見。ユーザー提案の「3回思考し多数決を取る」方式を`call_detector`プロンプトへの指示追加として実装（コード側での強制カウントではなく、まずプロンプト指示のみで様子見）。実LLM再ドライランでの効果確認は未実施 | P2 |
| BL-043 | 低 | `cela_main.py` (`call_decision_extractor`のJSON出力方式) | ユーザー提案：「AIがJSON出力→パース失敗→1からやり直し」ではなく「ツールでJSON構造確認→OK/FAULTと不備箇所をフィードバック→該当箇所だけ直して再出力」にできないか、という相談を契機に調査。既存の`write_agreement`等のツール呼び出し引数パースには、壊れたJSONを検出した場合にエラー内容をモデルへ返し同一ツールループ内で自己修復させる仕組み（D-009）が既に存在することが判明。`decision_extractor`自体をFunction Calling方式（例:`submit_extracted_events`ツール）に作り替えこの既存の自己修復ループに一本化する案を採用したが、設計変更としてはやや大きめのためBL起票のみに留め、JSONパース失敗（`_safe_json_parse`のフォールバック採用）が実害として頻発するようになった時点で実装に着手する方針 | P3 |
| BL-044 | 中 | `cela_main.py` (`run_ai_vs_ai_loop`, `task_planner_node`, `_save_checkpoint`/`_load_checkpoint`) | ユーザー提案：ドライラン長時間化により連続稼働が難しいため一時停止・再開機能が欲しいという相談。当初案（ターン境界でのcheckpoint保存）はBL-005（`turn_count`凍結）によりターン境界が実用にならないとユーザー自身が指摘し発覚、`app.stream(state, stream_mode="values")`によるノード単位保存方式へ設計変更（D-039）。`_save_checkpoint`/`_load_checkpoint`、`run_ai_vs_ai_loop`の`resume_from`引数、`task_planner_node`の冪等性ガード（`turn_count==1 and not phases`）、`--resume` CLI引数を実装。`tests/test_checkpoint_resume.py`（4件）新規、オフラインスモークテスト計70件Pass。実LLMドライランでのCtrl+C→`--resume`往復の実地確認は未実施 | P2 |
| BL-045 | 高 | `cela_main.py` (`_query_AI_live`のツールループ、`_LAST_PYTHON_CALLS`) | ~~実ドライラン（`log/2026-07-22/2217`）で、Expertがpython_replによる検算完了・`write_agreement`成功（whiteboard Ver.1保存）の直後、同一ツールループの次iterationでAPI 429エラーが発生しリトライを使い切ってエラープレースホルダを返した際、BL-033のフェイルクローズガードが「python_repl未使用」と誤判定し`constraint_issue=major`へ強制上書き→差し戻し→保存直後のホワイトボードがロールバックされ、実際には完了していた検算成果が破棄される事故が発生~~ → `done`。根本原因は`_LAST_PYTHON_CALLS`（BL-033の判定材料）がツールループの**正常終了時のみ**更新される実装になっており、ループ途中のAPIエラー例外で打ち切られた場合、実際に実行済みのpython_repl記録が`_LAST_PYTHON_CALLS`へ反映されないまま失われていたこと（対照的に`_LAST_WRITE_AGREEMENT_SUCCEEDED`はツール実行のその場で即時セットされるため例外の影響を受けず、非対称な状態になっていた）。python_repl実行のたびに`_LAST_PYTHON_CALLS`を即時反映するよう修正し、ループが途中終了しても記録が失われないようにした | P1 |
| BL-046 | 中 | `cela_main.py` (`_query_AI_live`の`for attempt`リトライループ、except節) | ~~BL-045の再開ドライラン（`log/2026-07-22/2300`）レビュー中、ユーザーが「Expertの思考とiter番号が同じループになっているログが見える」と報告。調査の結果、`🧰 tools attached`が2回連続で印字され間に何のログもないまま`思考（iter=1）`に巻き戻る箇所（`cela_main.py:1904-1905`該当）を確認~~ → `done`。原因は、`for attempt in range(len(delays)+1):`（BL-009の既知のリトライ設計）がツール呼び出しループ全体を内包しており、途中でAPIエラーが起きても**最後の試行を使い切るまでは何も表示せず**`time.sleep`するだけで`loop_messages`/`python_calls_log`をサイレントに破棄してiter=1からやり直していたこと。リトライ発生自体を可視化するログ出力（`🔄 [{label}] 一時的なAPIエラー、{delay}秒後にツールループを最初からやり直します...`）を追加。なお、リトライ時に`loop_messages`を破棄せず継続する（`write_agreement`成功後の巻き戻りによる重複書き込みリスクを本質的に解消する）設計変更は、より大きめの変更のため今回は見送り、可視化のみ対応 | P2 |
| BL-047 | 中 | `cela_main.py` (`WRITE_AGREEMENT_TOOL`スキーマの`depends_on`、`_write_agreement_impl`の整合性チェック) | ~~ドライラン（`log/2026-07-22/2320`）で、Expertが`write_agreement`呼び出し時に`"depends_on": ["task_1_1"]`を指定し`{'success': False, 'error': 'depends_onに存在しないID: task_1_1'}`で失敗、1往復無駄にしてから`depends_on`を除去して再送する事故を2回確認~~ → `done`。真因は、`depends_on`スキーマ（`cela_main.py:782`）に説明文が一切なく、コード側の検証は`agreements`テーブルの数値行ID（`【決定事項DB】`表示の`[42]`等）を期待する一方、AIが日常的に目にしているのはtask_planner側のタスク定義の`depends_on`（`task_id`文字列を指す全く別概念、例：`"depends_on": ["task_1_1"]`）であり、同名フィールドの意味衝突がAIを誤誘導していたこと。`depends_on`のdescriptionに、agreements DBの数値ID（決定事項DB表示の`[N]`）を使うこと・task_idを入れてはいけないこと・不明なら省略してよいことを明記して修正 | P3 |
| BL-048 | 高 | `cela_main.py` (`LineageState`、`generate_user_utterance_node`、`route_after_expert_decision`、`call_reflection`) | ~~ドライラン（`log/2026-07-22/2336`）で、task_2_1のacceptance_criteria自体の数学的矛盾をExpertが根拠のない数値ででっち上げ、Detectorも無根拠な推測で追認してしまう事例をユーザーが発見。reflectorが定期的にこの種の「でっちあげ」を検出する設計（`docs/design/r5/cela_r5_design_v2.md` §1.3、F-2.1拡張）だったはずが、BL-005（`turn_count`凍結）によりreflection自体が一度も発火していなかった~~ → `done`（reflection発火の症状のみ復旧、BL-005本体は未修正）。`LineageState`に`round_count`を新設し`generate_user_utterance_node`への再入場ごとにインクリメント、`route_after_expert_decision`のreflection発火判定を`turn_count`から`round_count`へ変更。`call_reflection`のプロンプトに`cela_r5_design_v2.md` §1.3の趣旨を反映した軽量版「でっちあげ監査」ブロックを追加（`internal_thought_process`の全経路キャプチャを要するフル版は別途判断） | P1 |
| BL-049 | 高 | `cela_main.py` (`call_detector`, `generate_user_utterance`, `call_expert`) | ~~ドライラン（`log/2026-07-22/2336`）で、ユーザーが「計算ツールを入れたことによりすべてのノードの思考が『計算が合っているか』に引き寄せられ、非数値的な重大懸念（バス2台の予備車両欠如、監視員2名の労基法適合性）を出力に反映できていない」と指摘。task_1_1「3名（シフト制）」とtask_2_2「2名常駐固定」というオペレーター人数のtask間矛盾が、双方とも算数としては通過するため検出されていなかったことを確認~~ → `done`。`call_detector`を、既存の数値検算パス（python_repl付き）＋新設の独立したドメイン妥当性レビューパス（ツールなし、数値監査結果を提示し再検算不要と明示、法規制・物理的運用可能性・でっち上げ疑義を評価）の2段構成に変更、より重篤な判定を採用。`generate_user_utterance`（User AI）はDetectorの検算を信頼しドメイン評価に集中する指示へ変更、`call_expert`には検算とは独立したドメイン妥当性チェックの自問を追加。オフラインスモークテストで発見したドメイン妥当性レビューの過検知（情報不足をmajorの理由にする）は基準明記で修正済み | P1 |
| BL-050 | 中 | `cela_main.py` (`call_decision_extractor`, `_build_agreements_context`) | ドライラン（`log/2026-07-22/2336`）で、車両台数が「task_1_1で3台」→「task_4_1の指示で2台」に変わった経緯をDetectorが辿れず、根拠を確認できないまま「Userが確定値と言っている以上、調整済みと解釈できる」と流してしまう場面を確認。`write_agreement`のSUPERSEDEは旧レコードを`status='Superseded'`にして残す方式だが、①Detectorに提示する`【決定事項DB】`コンテキストが有効な行だけに絞り込まれ過去版を見せない、②新しい値の`reason_why`が「前の値から何故変わったか」を明示することを要求されていない、の2点が実質的な欠落と判明。BL-037（reason_why記載品質、既存）と同系統だが「変遷の可視化」という点で更に踏み込んだ課題。`decision_extractor`を「新規決定を抽出する」役割から「各ノードが自ら出した決定の`reason_why`が妥当な理由になっているか監査する」役割へ軸足を移す方向性と、`【決定事項DB】`への差分・変更理由の明示を提案（設計相談・BL起票のみ、実装は次回以降） | P2 |
| BL-051 | 中 | `cela_main.py` (`call_detector`, `detector_node`, フェーズ終了判定ロジック) | Detectorの現行出力（`risk`/`constraint_issue`/`comment`の単一判定）では、思考過程で気づいた致命的でない懸念が構造化されずに失われる問題をユーザーが指摘。issue_bl的な構造化リスト＋フェーズ終了ゲートという本来の方針（BL-041と同格の構造変更、設計未確定）は変更せず`open`のまま据え置き、気づきの消失を当面緩和する暫定のつなぎとして`observations`自由記述欄・`detector_observations_log`蓄積・User AI/Expertプロンプトへの毎ターン提示のみ実装 | P2 |
| BL-052 | 低 | `cela_main.py` (`WRITE_AGREEMENT_TOOL`スキーマ、ホワイトボード本文フォーマット) | ホワイトボード（`whiteboard_drafts`）の各文・意味のまとまりに、根拠となる`agreements.id`等を指す参照（例:`[AG:123]`）をExpertに明示させ、本文中の主張とDB上の決定・理由を直接紐付けられるようにする提案をユーザーが発案（BL-050の「経緯が辿れない」問題への補完策）。捏造ID・可読性低下のリスクはあるが、`depends_on`の数値ID検証（BL-047で実装済みのパターン）がそのまま転用できる見込み。BL-050（理由監査役）・BL-051（issue_bl）とセットで設計するのが筋が良い方針（ID実在チェックはdecision_extractor監査役の担当範囲に自然に乗る）（設計相談・BL起票のみ、実装は次回以降） | P3 |
| BL-053 | 高 | `cela_main.py` (`get_verified_facts_from_db`) | ~~ドライラン（`log/2026-07-22/2336`）で、`read_verified_fact`/`read_deliverable_file`呼び出し44回中18回（41%）が`not_found`になっていることをユーザーが指摘~~ → `done`。真因は、`get_verified_facts_from_db`の`topic_keyword`あいまい検索が`variable_name`列（英語スネークケース識別子、例:`vehicle_count`）のみを対象にしていた一方、AIが渡す`topic_keyword`はツール定義自体が例示する通り「予算」「オペレーター」等の日本語の説明的キーワードがほとんどで、両者が文字列として重なることが構造的にほぼ無かったこと。`verified_facts`テーブルには日本語理由文が入る`reason`列が既に存在するのに検索対象に含まれていなかった。`variable_name OR reason`のLIKE検索に変更して修正、回帰テスト1件追加（`tests/test_r3_smoke.py`） | P1 |
| BL-054 | 中 | `cela_main.py` (`call_detector`) | ユーザー提案：BL-049で導入したDetectorの2段構成（数値検算パス→ドメイン妥当性レビューパス）の実行順序を逆転し、ドメイン妥当性レビューを検算より先に実行する。検算を先に済ませると「数値は合っている」という結果に引きずられ、前提・設計そのもの（台数・人数配置等）が現実的かというドメイン評価が後手に回りやすいという趣旨。ドメイン監査プロンプトから数値監査結果への言及を除去し、代わりに数値監査プロンプト側にドメイン監査の結果を提示して踏まえさせる形へ変更 | P2 |
| BL-055 | 中 | `cela_main.py` (`call_expert`, `generate_user_utterance`) | ドライラン（`log/2026-07-23/0919`）で、AIが「車両単価2,500万円」という例示的条件に強く引っ張られ、それを疑わず既存4台の配分探索のみを繰り返す様子をユーザーが確認・指摘。ゴール文には動かせない「真の制約」（総予算上限等）と、議論の前提として例示的に与えられただけの「見直し可能な条件」（単価等）が区別なく並記されており、AIには両者を見極める手がかりがなかったことが原因と分析。`call_expert`・`generate_user_utterance`の両プロンプトに、行き詰まった場合はまず「真の制約か見直し可能な条件か」を都度見極め、後者であれば前提自体を疑ってよい（ただし真の制約の緩和は不可）という一般化した指示を追加 | P2 |
| BL-056 | 中 | `cela_main.py` (`call_reflection`) | ドライラン（`log/2026-07-23/1122`）でReflectionが発火した際、プロンプト内表示が「全30ターン中1ターン目」のままで、Reflection自身が実際の会話量との矛盾に気づき混乱するログ（"これはおかしい"）をユーザーが発見。BL-048で発火条件自体は`round_count`ベースに切り替え済みだったが、プロンプト内の表示は凍結したままの`turn_count`（BL-005）を使い続けていたことが原因。表示を`round_count`（`reflection_interval`との対応も明記）に置き換えて発火条件と表示の基準を一致させた | P2 |
| BL-057 | 高 | `cela_main.py` (`_query_AI_live`のツールループ残り回数通知、BL-016) | ドライラン（`log/2026-07-23/1256`）で、複数の代替案を数値検討する組合せ最適化的なExpertターンがMAX_TOOL_ITER=15回の非収束クラッシュで打ち切られたことをユーザーが報告（成果物のホワイトボード自体はwrite_agreement実行済みのため保存されていた）。BL-016の「残り2回」通知では、長い最終回答（成果物の書き出しを含む）を書き切る前に上限を超えてしまうケースがあると判明。通知しきい値を「残り3回」に前倒しし、残り1回の通知文言もより強い断定的な指示に強化 | P1 |
| BL-058 | 中 | `cela_main.py` (`_ALLOWED_IMPORTS`) | 同ドライラン（`log/2026-07-23/1256`）で、Expertが組合せ探索に`import itertools`を試みたがホワイトリスト（`_ALLOWED_IMPORTS`）に含まれず`[REPL Error]`で拒否されていたことをユーザーが発見。「サンドボックスから抜け出せないような標準的なツール群は許可したらどうか」と提案。I/O・ファイルシステム・OS・ネットワークアクセスを一切持たない純粋計算ユーティリティ（itertools/functools/collections/operator/re）をD-007と同じ承認プロセス（AGENTS.md§7）で追加 | P3 |
| BL-059 | 高 | `cela_main.py` (`_query_AI_live`の例外タプル) | ドライラン中に`httpx.RemoteProtocolError`（"peer closed connection without sending complete message body"）が未捕捉のままプロセス全体をクラッシュさせたことをユーザーが報告。BL-022（`json.JSONDecodeError`が絞り込んだ例外タプルから漏れていた事例）と同種の問題で、streaming応答受信中にプロバイダ側が接続を切った際のhttpx層の生例外が`(APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError)`に含まれていなかった。`httpx.RemoteProtocolError`を追加しリトライ対象化 | P1 |
| BL-060 | 高 | `cela_main.py` (`_query_AI_live`のツールループ最終iteration) | ドライラン（`log/2026-07-23/1453`）で、Expertが最終許容iteration（15回目）でも`write_agreement`（成功）を呼び、次のiterationが存在しないためMAX_TOOL_ITER非収束クラッシュに至ったことをユーザーが報告。BL-016/BL-056bの「残り回数」通知はあくまで依頼であり、モデルが最終iterationでもツール呼び出しを選ぶと強制力がなかったことが原因。最終iterationのみAPI呼び出しから`tools`を外し、構造的にツール呼び出し不可能にしてテキスト最終応答を強制することでクラッシュを解消 | P1 |
| BL-061 | 高 | `cela_main.py` (`call_facilitator`/`facilitator_node`/`reflection_node`) | ドライラン（`log/2026-07-23/1656`）で、reflectionが5点の具体的な未解決問題（与条件無断変更・でっちあげ疑い数値等）を検出し`stagnant`と判定したにもかかわらず、`facilitator`自身は「膠着していない」と独立に再判断し、無関係な軽微な論点だけを穏やかに促す食い違ったメッセージを出力していたことをユーザーが発見。真因は`call_facilitator`が受け取る`decisions`引数がプロンプト内で完全に未使用（デッドパラメータ）で、reflectionの判定理由（`note`）がfacilitatorへ一切伝わっていなかったこと。`LineageState`に`last_reflection_note`を新設し`reflection_node`が保存、`call_facilitator`のプロンプトにこれを最優先の出発点として明示する形で修正 | P1 |
| BL-062 | 高 | `cela_main.py` (`write_agreement`権限モデル全体) | R5実装計画（F-8.3 Freeze）の設計相談中、ユーザーが「Detectorはユーザーまたはエキスパートの決定まで破棄できたか？」と指摘。調査の結果、Detector/Reviewer/Arbiter/Integratorの`major`判定・`status='Rejected'`書き込みは、User/Expertが既に`write_agreement`で書き込んだ`Approved`/`Proposed`なagreementをDB上でSUPERSEDE/無効化する構造的な仕組みを持たず（target_topicでSUPERSEDEする運用ガイドがDetector側に存在しない）、実際の効果は差し戻し（再プロンプト）のみに留まることが判明。旧decision_extractor中心アーキテクチャでは「Detector監査を通過した後に抽出する」という順序が暗黙の監査ゲートだったが、R3b以降の各ノード自律書き込みへの移行でこの保証が構造的に失われている。write_agreementの権限モデル全体の再設計が必要な大きめの課題のため、BL起票のみに留め実装は見送り | P1 |
| BL-063 | 中 | `cela_main.py` (R5全体: F-2.1/F-3.7/F-8.3/GoalShiftEvent) | `cela_r5_design_v2.md`が定義するR5新規要件を実装。F-2.1（Detectorへの思考プロセス監査、`_query_AI_live`のreasoning捕捉＋`expert_last_reasoning`/`user_last_reasoning`配線）、F-3.7（`make_decision`/`_commit_agreement_from_tool`へのinternal_thought_process限定記録、Detector major・Reflection stagnant・Rejected判定時のみ）、F-8.3 Freeze（新規`freeze_agreement`＋`FREEZE_AGREEMENT_TOOL`、user限定、SUPERSEDE/UPDATEガード、`_build_agreements_context`のis_frozenソート＋🔒表示）、GoalShiftEvent（`goal_shift_events`テーブル新設、`call_resource_arbiter`への`requires_goal_constraint_change`追加、`detect_goal_shift`、`arbiter_node`配線）を実装。decision_extractorの役割転換（BL-050完了条件3）は今回スコープ外のまま。Detectorの監査ガバナンス欠落（BL-062）はFreeze権限をuser限定にすることで影響を限定 | P2 |
| BL-064 | 中 | `cela_main.py` (Agreement/Phase/Decision TypedDict, `_build_agreements_context`, `_build_hydrate_context`, `detector_node`) | 合意・決定メタデータ（`abstraction_level`/`scope`/`time_axis`の3軸区分、`turn`、`evidence`、`reason_missing`、`state["risk_flag"]`）が、書き込みロジック（WRITE_AGREEMENT_TOOL・make_decision・detector_node）とDB保存・print表示は存在するのに、実際にLLM向けコンテキストを組み立てる`_build_agreements_context`/`_build_hydrate_context`や他ノードの判定ロジックからは一度も読まれていないことをユーザーの質問により発見 | P2 |
| BL-065 | 中 | `cela_main.py` (`make_decision`/`_commit_agreement_from_tool`/`goal_shift_events`) | R5（BL-063）で新設した2つのDB永続化情報（`internal_thought_process`列、`goal_shift_events`テーブル）が、書き込みロジックのみ実装され、読み返して何かに反映する消費経路が存在しないことが判明。F-2.1の思考監査プロンプトが実際に使うのは同一ターン限りの`state["expert_last_reasoning"]`であり、DBへ永続化した`internal_thought_process`とは別物 | P2 |
| BL-066 | 低 | `cela_main.py` (`apply_whiteboard_patch`/`get_latest_whiteboard`) | `whiteboard_drafts`テーブルの`author_role`/`edit_summary`列はバージョンごとにINSERTされるが、`get_latest_whiteboard`は`version`/`content`のみをSELECTしており、誰が・どんな要約で編集したかが一切読み出されない。BL-050がagreements側に実装した差分表示と同種の仕組みがwhiteboard側に存在しない | P3 |
| BL-067 | 低 | `cela_main.py` (`init_db`) | `init_db`で定義される`chat_history`/`current_goal`テーブルが、コード全体でINSERT/SELECTが一件も存在しない完全な死んだスキーマであることが判明。実体は`state["chat_history"]`/`state["goal"]`（インメモリ）とLangGraphのcheckpointerで完結している | P3 |
| BL-068 | 中 | `cela_main.py` (`call_expert`のプロンプト、`current_task_summary`、`chat_history_window`) | `current_task_summary`は元々、docs/refsのHydrate構想（直近Nターン生ログ＋それ以降を定期要約で積み上げる3段グラデーション）に由来する設計だったが、消費側が未実装のまま放置されていたとユーザーが説明。`call_expert`には現在も「5ターン毎に議論のサマリーを出力せよ」という指示（`cela_main.py:2620`）が残るが、この出力を捕捉・蓄積する実装が存在せず、`chat_history_window`は直近N件を生ログのまま渡す固定窓のみで、それ以前のターンは要約されず単純に切り捨てられている | P2 |
| BL-069 | 中 | `cela_main.py` (`call_expert`のプロンプト、`phases_json`、BL-025スコープガードレール) | ユーザーが「木を見て森を見ず」対策として、決定前にタスク→フェーズへとズームアウトして見渡す思考フレームワーク（L1〜L4）を提案。調査の結果、`call_expert`は既に全フェーズ・全タスクの`phases_json`を毎ターン埋め込んでいる（`cela_main.py:2686-2691`）が、直後のBL-025スコープガードレール（`cela_main.py:2700-2714`）が「他タスクの値を新たに算出・提案しない」と明記しており、Expertは全体表を見えていながら能動的に活用することを事実上禁止されていることが判明。この緊張関係はBL-041自身のコードコメントが既に指摘済みで、現状の緩和策はconfidence='provisional'タグ付けのみ。ユーザーは正式なL1-L4段階分けではなく、「次フェーズのタスクが今の決定の前提を覆しうると気づく」程度の軽量な指示追加で十分と後日補足 | P2 |
| BL-070 | 中 | `cela_main.py` (`call_reviewer`/`call_resource_arbiter`/`call_integrator`) | BL-062のDetector限定実装（D-045）に伴い分離。Reviewer/Arbiter/Integratorも技術的には`WRITE_AGREEMENT_TOOL`を保有し`status='Rejected'`かつ`action_type='SUPERSEDE'`を呼べる権限を既に持つが、3ロールとも現状agreements DBのtopic一覧をプロンプト上受け取っておらず、かつ成果物全体審査・リソース配分・フェーズ横断統合という別種の役割のため、topic単位のSUPERSEDEが同じ意味を持つかの検討が必要。Detectorでの実運用結果を見てから拡張要否を判断する方針 | P2 |
| BL-071 | 高 | `cela_main.py` (`decision_extractor_node`/`integrator_node`/`_build_agreements_context`) | ユーザーの実ドライランで`orchestrator_node`実行中に`TypeError: '<' not supported between instances of 'NoneType' and 'float'`でプロセス全体がクラッシュ。原因は`decision_extractor_node`の2箇所と`integrator_node`のAgreement辞書リテラルが元々`timestamp`キーを持っておらず、`db_append_agreement`のINSERTでDB上`timestamp`列がNULLになっていたこと。R5（BL-063）で追加した`_build_agreements_context`のis_frozen優先ソート（`a.get("timestamp", 0)`）はキーが存在する場合はdefault値を使わないため、None同士・Noneとfloatの比較でクラッシュした | P0 |
| BL-072 | 高 | `cela_main.py` (`_query_AI_live`) | BL-071修正後の再ドライランで、`expert_node`のstreaming受信中に`httpx.ReadTimeout`が発生しプロセス全体がクラッシュ。BL-059（`httpx.RemoteProtocolError`が絞り込んだ例外タプルから漏れていた事例）と同型で、`httpx.ReadTimeout`もopenai SDKの`APITimeoutError`へラップされず生のまま送出されていた。個別の派生例外を都度追加するのではなく、`ReadTimeout`/`ConnectTimeout`/`WriteTimeout`/`PoolTimeout`を包含する親クラス`httpx.TimeoutException`を例外タプルに追加して解消 | P0 |
| BL-073 | 中 | `cela_main.py` (`decision_extractor_node`/`_commit_agreement_from_tool`) | `entry_type="Directive"`のagreementは、対応するtask_idのDeliverableが承認されても`status="Proposed"`のまま遷移させる経路が無く永久にDBへ残っていた。`reflection_node`の「未解決」抽出（`status=="Proposed"`の全件、entry_type不問）に既に履行済みの指示がノイズとして出続け、実ドライランでReflectionが毎ターン自問自答を強いられていた（実害はなかったが放置すると誤判定を誘発しうる根本課題）。Deliverableが`Approved`/`Approved_with_Conditions`/`Implicitly_Accepted`へ遷移した際、対応するtask_idのDirectiveも自動的に`Approved`へ解決する`_resolve_directive_for_task`を新設し、`decision_extractor_node`のUPDATE分岐と`_commit_agreement_from_tool`の両経路から呼び出すよう解消 | P2 |
| BL-074 | 中 | `cela_main.py` (`_commit_agreement_from_tool`/`decision_extractor_node`のtopic文字列一致によるUPDATE/SUPERSEDE対象特定、および`_annotate_whiteboard_with_detector_comment`のtarget_excerpt完全一致) | ユーザーとログ（`log/2026-07-24/0647`）のtask_2_2（初期導入費用内訳策定）議論の変遷をレビューする中で発見。`entry_type="Deliverable"`のUPDATE/SUPERSEDEは`target_topic`（省略時は`topic`自身）の文字列完全一致でのみ対象行を特定するが、Expert/decision_extractorはバージョンを重ねるたびに新しいtopic文字列を自由に発明しており連続性が保証されない。結果としてtask_2_2単一のDeliverableに対し、Supersede漏れの`Proposed`行が複数（実測4行）DBに残存。BL-073と同根だがDeliverable側での顕在化。**2026-07-24追記:** 1216ドライラン（`log/2026-07-24/1216`）のフォレンジック調査で、BL-076のtarget_excerpt完全一致にも同根の脆さがあり、しかも失敗がサイレント（0回発火でもログに何も出ない）で発覚を困難にしていたことが判明したためBL-076側の問題をBL-074へ統合。この部分（失敗理由ログ＋改行・空白・太字記法・全角半角を正規化した緩い一致フォールバック）は実装済み・`done`。**2026-07-24追記2:** Deliverable本体のtask_id識別への切替は、1459ログで実害2件が確認されたため[BL-084](issue_backlog.md#bl-084-entry_typedeliverableのupdatesupersedeがtopic文字列ドリフトでeditsを0件0件失敗させ続けていたbl-074の未着手項目の再発)として実装・`done`化 | P2 |
| BL-075 | 高 | `cela_main.py` (`rollback_whiteboard`/`expert_node`/`call_expert`) | 実ドライラン（`log/2026-07-24/0647`）で、task_2_3のオペレーター年間有給休暇が労基法違反（5日）としてmajor判定→Ver.2で10日に修正→**別件**の懸念（法定祝日未考慮）でmajor判定→ロールバックにより有給10日の修正が無警告で有給5日へ後退、というバージョン退行をDetector自身が発見。原因はF-7.3のロールバック（`rollback_whiteboard`）が常に「1つ前のバージョンは健全」という前提でrows[1]（2版前）へ機械的に復元する設計だったこと。この前提はmajor判定のたびに別の新しい懸念が指摘される実運用下では成り立たず、既に修正済みの問題を無警告で再導入する。ロールバック自体を撤廃し、ホワイトボードの最新内容を保持したままExpertがDetectorの指摘箇所のみを`edits`で部分修正する方針（ユーザー提案、Word/PDFコメント機能的ワークフロー）に変更 | P1 |
| BL-076 | 中 | `cela_main.py` (`call_detector`/`detector_node`/新設`_annotate_whiteboard_with_detector_comment`) | BL-075のプロンプト誘導だけでは「毎ターン再構成されるプロンプト注入」に留まり見落とされ得るとユーザーが指摘。Detectorのmajor指摘を、プロンプト注入と同時にホワイトボード本文そのものにWord/PDFのコメント機能のように永続的な注釈として埋め込む機能を追加。Detectorの両パス（ドメイン妥当性レビュー・数値監査）に`target_excerpt`（指摘対象の一字一句引用）を出力させ、ホワイトボード内で一意一致する場合のみ`> 🔴 **[Detector指摘 #ID]**: ...`形式（案A・タグ+案Bの引用のハイブリッド、ユーザー承認）の注釈をその直後に挿入する。Expertは修正時にeditsで注釈行ごと書き換えることで自然に注釈が消える設計 | P2 |
| BL-077 | 低 | `cela_main.py`（CELA自身のAI群全体、未着手・設計検討のみ） | ユーザーが、本プロジェクト自身のAGENTS.mdが定める「まずMemory/STATUS/backlogを確認してから動く」という設計思想を、CELAが動かすAI群（Expert/User AI等）自身にも適用するアイデアを提示。ホワイトボード（現状把握）と、まだ実装されていない「issue_BL」相当の仕組み（タスク内の残課題・指摘事項の永続管理）を必ず先に確認してから、User AIなら指示、Expertならタスク遂行に入るという思考ワークフロー。ユーザー自身、STATUS.md・traceability.md相当の仕組みも新たに必要になると認識しており、範囲が大きいためBL化のみ行い、設計は別途相談 | P3 |
| BL-078 | 中 | `cela_main.py` (`call_orchestrator`/`orchestrator_node`/`call_expert`) | ユーザーが、Detectorの「監査の観点をプロンプトで変えるだけで仕事ぶりがガラッと変わる」効果に着想を得て、Orchestratorが専門家選定時に既に行っているタスク内容の考察（従来は選定理由`reason`としてログにのみ残り、Expertには一切伝わっていなかった）を、新設`focus_guidance`フィールドとして明示的に出力させ、選ばれたExpertのプロンプトに注入することでタスクごとに思考を最適化できないか提案。`call_orchestrator`のプロンプト・JSON出力に`focus_guidance`（タスク固有の着眼点・注意点、`reason`＝選定理由とは別物）を追加し、`orchestrator_node`が`state["expert_focus_guidance"]`へ保存、`call_expert`のフル版・軽量版プロンプト両方に注入 | P2 |
| BL-079 | 中 | `cela_main.py` (新設`VERIFY_WHITEBOARD_EXCERPT_TOOL`/`_verify_whiteboard_excerpt_handler`、`call_detector`) | BL-074の正規化フォールバックを相談する中で、ユーザーがClaude Code自身の`Edit`ツールが同種の完全一致方式でも実運用できている理由を質問。調査の結果、Claude Codeは(1)LLMがその場で読んだ内容から引用する、(2)不一致時に即座にエラーがツール結果として返り同一ターン内でLLM自身がリトライできる、の2点が揃っているのに対し、CELAの`_annotate_whiteboard_with_detector_comment`は(2)を欠き、失敗してもDetector自身にフィードバックが返らないことが根本差だと判明。**2026-07-25追記:** `1913`ドライラン（L16700）でBL-074の正規化フォールバックも救えない0/0一致失敗が再現し、優先度をP3→P2へ引き上げ。**2026-07-25実装:** 当初案（注釈挿入自体をDetector自身が呼べるツール化）は、実際の注釈挿入がdecision_id確定後のdetector_node側後処理で行われるため、ツール呼び出し時点ではdecision_idが未確定という設計上の制約があり、規模が大きくなると判断。代わりに、挿入は事後処理のまま維持しつつ、事前に「この引用は一意に一致するか」だけを検証できる新規ツール`verify_whiteboard_excerpt`をDetectorの数値監査パス（tools付き）に追加し、一致失敗時はDetector自身が同一ツールループ内でexcerptを調整・再試行できるようにした。ドメイン妥当性レビュー（tools=None）は依然としてこのツールを呼べないため、`call_detector`のtarget_excerpt統合ロジックに、選ばれた側の引用が実際には一致しない場合もう一方の（一致する可能性が高い）引用へ差し替えるプログラム側フォールバックも追加した | P2 |
| BL-080 | 高 | `cela_main.py` (`_commit_agreement_from_tool`のSUPERSEDE分岐) | ユーザー依頼で1216ドライラン後の1319ドライランをフォレンジック調査する中で発見。`entry_type="Deliverable"`に対する`action_type="SUPERSEDE"`は、旧agreement行のstatusを`Superseded`に変更した直後に`return None`しており、Expertが渡した`decision_what`（全文）を完全に破棄し、`apply_whiteboard_patch`も一切呼ばれないまま「成功」を返す実質何もしないツール呼び出しになっていた。BL-075で追加したプロンプト（editsの完全一致に失敗した場合、decision_whatによる全文更新＝SUPERSEDEを使えという誘導）がExpertをこの壊れた経路に誘導し、Expertは`{'success': True}`を信じて「更新完了」と報告するが、直後に`read_deliverable_file`で読み戻すと旧内容のままという矛盾に直面。Expertはこれを「システムの反映タイミングの問題」と誤って自己正当化し、Detector/Userからハルシネーション（虚偽の更新完了報告）と判定され続ける無限ループに陥っていた。`entry_type=="Deliverable"`かつ`action_type in ("CREATE", "SUPERSEDE")`かつ`len(decision_what) > 200`（CREATE/UPDATE全文置換と同一閾値）の場合、CREATE同様`apply_whiteboard_patch`で新版を保存するよう修正。BL-062のDetectorによる無効化用途（短い理由文のみ、ホワイトボードには触れない）との後方互換は同じ閾値で維持 | P0 |
| BL-081 | 高 | `cela_main.py` (`_apply_text_edits`/`_normalize_for_loose_match`/新設`_find_loose_match_spans`) | ユーザーが同じ1319ドライランを指して「まだホワイトボードの差分書き換えに苦労しているようです」と再調査を依頼。調査の結果、ExpertがBL-080の誘因となった`edits`失敗（Markdownテーブル行頭の全角スペース・パイプ記号の有無だけでold_text完全一致が0件になる）の実例を特定。BL-074/D-050でDetectorのtarget_excerpt向けに確立した正規化緩い一致の仕組みを`_apply_text_edits`自身にも適用し、Expertの主たる編集手段であるeditsがその場で成功する確率を高めた（新設`_find_loose_match_spans`で正規化後の一致位置を元の文字列へ逆写像）。あわせて、`_normalize_for_loose_match`自体に「半角スペースは除去されるが全角スペース（　）はNFKC正規化後の半角スペース1文字として結果に残ってしまう」という非対称バグを発見・修正し、テーブル区切り記号（\|）も正規化対象に追加した | P1 |
| BL-082 | 高 | `cela_main.py` (新設`plan_drafts`テーブル/`get_latest_plan_draft`/`apply_plan_patch`/`_append_deferred_note_to_plan`/`_get_deferred_notes_text`、`decision_extractor_node`/`call_decision_extractor`/`_build_task_scope_context`/`call_expert`/`generate_user_utterance`/`call_detector`) | `log/2026-07-24/1349`のドライランで、User AIが「積雪・通信エリアの区間切り出しの地形照合はtask_2_1/task_2_2で具体化されるべき」と先送り判断を発言したことをユーザーが指摘し「この先送り事項は現状消えてしまいますよね？」と質問。調査の結果、二重の理由で消失することが判明: (1) `call_decision_extractor`の「先送りの検出」ルール（`entry_type=Directive, status=Deferred`として抽出）がExpert側の抽出ブランチにしか実装されておらずUser AI側には存在しなかった（今回の実例はUser AIの発言だったため抽出自体が発動しなかった）、(2) たとえ正しく抽出されても`_build_agreements_context`がentry_type="Directive"を無条件で全除外しており後続タスクには一切見えない構造だった（BL-073時代の対症療法の副作用）。ユーザーが提案した「task_plannerの計画もホワイトボード化して先送り事項を書き込めるようにする」という方向性を採用。`whiteboard_drafts`の完全ミラーとして新規`plan_drafts`テーブルを新設（既存テーブルへの混在によるリスクを避けるため）。`decision_extractor_node`が申し送り先task_id（新設`defer_to_task_id`フィールド、両抽出ブランチに追加）を解決し対象タスクの計画文書へ追記、`call_expert`・`generate_user_utterance`・`call_detector`の3箇所（Explore調査＋Plan agentによる批判的レビューで発見した見落とし箇所）すべてに配線した | P1 |
| BL-083 | 高 | `cela_main.py` (`_query_AI_live`の例外タプル) | BL-082コミット後の実ドライラン（`log/2026-07-24/1459`）で、Expert(iter=7)がedits編集を行おうとした直後、streaming受信中に相手ホストから強制切断（Windows `WinError 10054`）され、生の`httpx.ReadError`（`httpcore.ReadError`由来）が絞り込んだ例外タプルに含まれず未捕捉のままプロセス全体がクラッシュした。BL-059（`httpx.RemoteProtocolError`）/BL-072（`httpx.TimeoutException`）と同型の再発で、BL-081/BL-082のロジックとは無関係な純粋なネットワーク層の例外クラス漏れ。例外タプルに`httpx.ReadError`を追加して対応 | P0 |
| BL-084 | 高 | `cela_main.py` (`_commit_agreement_from_tool`のSUPERSEDE/UPDATE分岐、新設`_find_active_deliverable_agreement`) | ユーザー依頼で`log/2026-07-24/1459`をレビューする中で発見。BL-081実装後にもかかわらず`edits`が2回とも「old_textが見つかりませんでした（正規化後の緩い一致も0件）」で失敗していたため実際に再現テストしたところ、old_text自体は完全一致（127文字差分0）しており、BL-081の正規化ロジックには問題がないことを確認。真因は`_commit_agreement_from_tool`がUPDATE/SUPERSEDE対象を`target_topic`（省略時は自分自身のtopicにフォールバック）の文字列完全一致で検索していたこと。Expertが`target_topic`を一度も送らず、呼び出しごとにtopicの言い回しを変えていた（実例あり）ため既存行と一致せず`old_content`が空文字のまま渡され、`_apply_text_edits("", edits)`が常に0件/0件で失敗していた。BL-074の完了条件「Deliverable本体のtask_id識別への切替はまだ`open`」がまさにこれで、BL-081のフォールバック強化だけでは原理的に解決できないことが実害で裏付けられた。新設`_find_active_deliverable_agreement`で(phase_id, task_id)識別に切替（Decision/Directiveはスコープ外、従来通り） | P0 |
| BL-085 | 低 | `cela_main.py` (新設`_write_whiteboard_to_file`、`apply_whiteboard_patch`) | ユーザーから「ホワイトボードの中身を保存時にファイルに書き出してほしい」と要望。従来`whiteboard_drafts`はDB（sqlite）のみに保存され、中身を確認するにはクエリが必要だった。`apply_whiteboard_patch`から新設`_write_whiteboard_to_file`を呼び、保存の都度`{log_dir}/whiteboards/{phase_id}_{task_id}_V{version}.md`へバージョンごとに個別ファイルとして書き出す（DBのappend-onlyバージョニングと同じく上書きしない）。BL-027と同じ理由で、`MultiLogger._instance`が未初期化（テスト/import時）の場合は書き出しをスキップし、本番log/配下のテスト汚染を防止 | P3 |
| BL-086 | 高 | `cela_main.py`（新設`goal_escalations`テーブル、`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`ツール、`FREEZE_AGREEMENT_TOOL`の再配線、`call_expert`/`generate_user_utterance`/`generate_user_utterance_node`/`call_detector`） | ユーザーが1459ログ由来の「オンデマンド交通なのに予算制約から逆算して35人乗りバスを導入する」矛盾を指摘し、そもそも論の視座（高齢者の移動手段確保という本質的課題）に立ち返って前提自体を見直せる経路が無いことを議論。Expertは`absolute_constraints`の文言を厳守することしかできず前提の矛盾を表明する手段が無いこと、User AIが例外を承認してもFreeze機構（D-045で無効化中）が無いためDetectorの独立監査で無限に再燃しうること、`state["goal"]`を改定する手段が無くGoalShiftEventが書きっぱなしで何も消費されないこと（BL-065）の三重の構造的欠陥を特定。ユーザー指示「エスカレーション経路を作り込み、freezeを復活させ、本質的課題の解決という視点に登り当初目標を越境しても最適な着地点に到達できるように」に基づき、Plan mode（Exploreエージェント3件＋Planエージェント1件、全行番号を直接検証済み）で設計し実装。Expert/User AIが構造化してエスカレーションを提起する`escalate_premise_concern`（narrow channel、BL-025のスコープガードレールは変更せず）、User AI専用の却下`resolve_premise_concern`・承認＋ゴール改定`revise_goal`（`_apply_text_edits`を`state["goal"]`にも再利用、承認時にFreezeも同時実行可能）を新設。`state["goal"]`は9箇所の消費者が毎ターン再埋め込みするため、`generate_user_utterance_node`の1箇所で書き換えるだけで全消費者に自動伝播。Freezeを`generate_user_utterance`のtoolsへ再配線し、`call_detector`の両監査パスに🔒Freeze済み項目を尊重する指示を追加（BL-062自身の欠落を解消） | P1 |
| BL-087 | 高 | `cela_main.py` (`call_task_planner`、`generate_user_utterance`、新設`call_task_plan_reviewer`/`task_plan_reviewer_node`/`call_goal_essence_analyst`/`goal_essence_node`/`goal_essence`テーブル。Stage 1・2・3・4実装済み。Stage 2'・5は`open`) | BL-086実装後の実LLMドライラン（`log/2026-07-24/2358`）レビューで、`escalate_premise_concern`等BL-086の4ツールがプロンプトで説明されているにもかかわらず一度も自発的に呼ばれないことを発見（`tools attached`表示以外での言及ゼロ）。原因は`call_expert`/`generate_user_utterance`のシステムプロンプトがツールの存在・使いどころを、既存エスカレーションがある場合にのみ条件付きで説明しており、初回は何も教えていなかったこと。恒久的な説明ブロックを両プロンプトに追加したところ、翌ドライラン（`log/2026-07-25/0935`）でUser AIの思考文に初めて`escalate_premise_concern`という単語自体が登場し（結果的に不使用と判断したが、検討はした）、指示追加の効果を確認。同ログのレビュー中に別途2件のバグ・改善余地を発見: (1) `task_1_3`の`acceptance_criteria`の"(12km区間)"という表記が比率(15%)か絶対距離かを一意に確定できず、Expertが同一の誤読を4回連続（V1→V9、9版）で繰り返した、(2) User AIの標準指示が無条件に「合意に達したら成果物の出力を指示せよ」と言うため、R4のホワイトボード方式で既にApproved済みの成果物にも再提出を要求しExpertを混乱させていた。さらにユーザーから「監査・検算の前提となる計画自体が歪んでいると徒労に終わる」「バス3台で無理と分かった時点で"バスである必要は？タクシー補助では？"という一段上の思考をAIにさせたい」という要望を受け、段階的な改善計画（`docs/design/`配下の実装計画に相当する内容はPlan modeで`task-plan-reviewer-node-task-planner-glistening-coral.md`として作成）に合意。**Stage 1（実装済み）**: ①`call_task_planner`のプロンプトに、比率/絶対値の取り違えを防ぐ曖昧表記禁止指示と、今回のtask_1_3失敗例をNG例として追加。さらに暗算によるハルシネーションを避けるため`tools=[PYTHON_REPL_TOOL]`を付与（ユーザー指摘、`call_goal_essence_analyst`/`call_task_plan_reviewer`にも同様に付与）。②`generate_user_utterance`の標準指示に、未充足の`acceptance_criteria`が無くホワイトボードに成果物が既に存在する場合は再提出を求めず次のタスクへ進行するよう条件分岐を追加。**Stage 2（実装済み）**: `task_planner_node`直後（`graph.add_edge("task_planner", "task_plan_reviewer")`）に1回だけ発火する`task_plan_reviewer_node`を新設。生成された`phases`全体（曖昧表現・タスク過不足・依存順序）をDetector同等のJSON（`risk`/`constraint_issue`/`comment`）でレビューし、`constraint_issue="major"`かつ差し戻し回数が2回未満なら`state["phases"]`をクリアして`task_planner`へ差し戻す（既存の`task_planner_node`の`not state.get("phases")`ガードにより自然に再生成される、無限ループ防止のため上限到達後は指摘が残っていても承認）。差し戻し理由は新設`state["plan_reviewer_feedback"]`へ保存し、`call_task_planner`に追加した`reviewer_feedback`引数経由で再生成プロンプトに注入。再レビューがチェックポイント再開のたびに再発火しないよう、新設`state["plan_review_done"]`で`task_planner_node`と同型のturn_count==1ガードを踏襲。**Stage 3（実装済み）**: task_planner分解より前に1回だけ発火する`goal_essence_node`を新しい`entry_point`として追加（新設`goal_essence`テーブル・`call_goal_essence_analyst`）。ゴール文の大まかな実現可能性の壁打ちと目標の本質の言語化を行い、新設`_get_goal_essence_text`でBL-086 D-058の9消費者すべて（`state`経由5箇所＋`goal_essence_text`引数経由4箇所）へ常時注入。**Stage 4（実装済み）**: `call_detector`のドメイン妥当性パス・`generate_user_utterance`の両方に、本質と数値・条件設定の整合性チェック観点を追加（BL-069関連）。**Stage 2'・5（`open`、別途着手）**: フェーズ完了時にtask_plannerが残りフェーズを再計画する機構、「一段上の思考」を`reflection_node`拡張＋機械的トリガー（`global_constraints`の逼迫比率・`expert_retry_count>=3`のOR）で強制発火させる仕組み（D-059参照） | P1 |
| BL-088 | 高 | `cela_main.py` (`_safe_json_parse`) | BL-087 Stage2改善後の実ドライラン（`log/2026-07-25/1642`）レビューで、task_plannerの1〜2回目の出力が実際には正しい5〜6フェーズの計画だったにもかかわらず、`task_plan_reviewer_node`に渡った内容は縮退した1タスクのみの`fallback_phase`になっていた事象を発見。原因は`_safe_json_parse`の「先頭が`{`/`[`でない場合に開始位置を探す」ロジックが、`brace_idx`（最初の`{`の位置）が見つかりさえすれば`bracket_idx`（最初の`[`の位置）より後にあっても常に`brace_idx`を優先していたこと。トップレベルが配列（`call_task_planner`のfallbackはlist）で、かつコードフェンス前に説明文が付く応答（例:「それでは、フェーズ分解を提示します。\n\n\`\`\`json\n[{...}]」、LLMの一般的な癖）の場合、配列を開く`[`より後にある最初のオブジェクトの`{`から開始してしまい、構文的に不正なJSON（先頭の`[`を欠いた状態）になりパース失敗、fallbackへ握りつぶされていた。このバグにより、`task_plan_reviewer_node`の差し戻しリトライ予算（上限2回）が2回とも本バグによる縮退計画の却下で無駄撃ちされ、3回目（最終・強制承認）でも再現していれば縮退計画がそのまま最終計画として承認されるところだった。`{`/`[`のどちらが先に現れるかで開始位置を決めるよう修正（`min()`判定）。新規`tests/test_bl088_safe_json_parse_bracket_precedence.py`（3件、`1642`ログの実際の失敗パターンを再現）、`python -m py_compile`合格。D-062として記録 | P1 |
| BL-089 | 高 | `cela_main.py`（`_safe_json_parse`、`call_task_plan_reviewer`/`call_task_planner`/`call_goal_essence_analyst`を`_query_and_parse_with_retry`でラップ、`call_expert`/`call_detector`/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`/`call_goal_essence_analyst`/`call_task_plan_reviewer`のプロンプトに重複検証抑制指示） | ユーザー依頼でドライラン再実行（`log/2026-07-25/1814`）をレビューし、BL-088修正後もなお、task_plannerの出力がmax_tokens相当の理由で途中で切れ縮退計画にフォールバックした上、task_plan_reviewerはこの縮退計画を正しく"major"と判定していたにもかかわらず、応答が「プレビュー用の配列ブロック」と「### 最終JSON出力の完全なオブジェクトブロック」という2つの```json```ブロックで構成されていたため`_safe_json_parse`が混線し構文エラー、fallback（`constraint_issue="none"`）に化けて縮退計画がそのまま承認・実行されてしまう事象（`log/2026-07-25/1814/whiteboards/`にphase_1_task_1_1のみ存在）を発見。(1) `_safe_json_parse`を、複数の```json```フェンスブロックがあれば最後のブロックを採用するよう修正（BL-088の単一フェンス+先頭プローズのケースも包含）。(2) `call_task_plan_reviewer`/`call_task_planner`/`call_goal_essence_analyst`を既存の層2リトライ`_query_and_parse_with_retry`（D-005、`call_reviewer`/`call_detector`で既に採用済みの安全網）でラップし、単発のパース失敗で即fallbackへ落ちないようにした。(3) `call_task_plan_reviewer`は安全ゲートという性質上、リトライを使い切ってもパース失敗した場合は"none"（フェイルオープン=承認）ではなく"major"（フェイルクローズ=差し戻し）を返すよう変更。続けて、ユーザーが同じ`1705`/`1814`ログから「他のノードも何回も何回も同じ思考を繰り返しすぎることが多々あった」と指摘し、`tools=[...]`でpython_repl等のツールアクセスを持つ全8関数（tools=Noneの`call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`は対象外）のプロンプトに、既存のtask_planner項目7と同種の「同じ検証・計算を繰り返さない」指示を追加。`call_task_plan_reviewer`には追加で「最終回答のJSONブロックは1つだけ」という指示も加えた。新規`tests/test_bl089_json_fence_and_failclosed_review.py`（8件）・`tests/test_bl089_anti_repetition_instructions.py`（9件）、`python -m py_compile`合格。D-064・D-065として記録 | P1 |
| BL-090 | 中 | `cela_main.py` (`call_goal_essence_analyst`) | BL-089修正後のドライラン（`log/2026-07-25/1913`）をユーザーがレビューし発見。L424でgoal_essence_analystの応答が、`feasibility_notes`文字列値の末尾を全角鉤括弧「」で終えたため、JSON構文上の閉じ引用符(")を書き忘れた形になりパース失敗（`⚠️ JSON判定パース失敗を検知。層2リトライ 1/2...`でBL-089の層2リトライにより自己修復済み、実害なし）。プロンプトに「JSON文字列値の末尾を全角鉤括弧「」『』で終えない」旨の注意を追加し、そもそもこの種のパース失敗自体を減らす予防策とした。新規`tests/test_bl090_json_string_fullwidth_quote_guard.py`（1件）、`python -m py_compile`合格。D-066として記録 | P3 |
| BL-091 | 高 | `cela_main.py` (`call_detector`) | `log/2026-07-25/1913`のtask_2_1修正で、Expertのwrite_agreement(edits)が「old_text不一致」で失敗し最終iterationでツールが強制的に外された後、モデル（DeepSeek系）が独自のツール呼び出し風疑似XML（`<｜DSML｜tool_calls>...`）を平文でそのまま出力。`get_last_write_agreement_succeeded()=False`とシステム自身は正しく記録していたが、この成否フラグが`call_detector`のプロンプトに一切渡っておらず、Detectorはこの平文の「主張」を鵜呑みにして誤って承認（物理的矛盾が解消された、acceptance_criteria充足）、Decision Extractorも虚偽のUPDATEをDBに記録した。実際のホワイトボードはV2のまま（V3は存在せず）、誤った記述・数値が残存。BL-033（Expertのpython_repl自己申告を鵜呑みにしない）と同根・同型の欠落。`call_detector`のドメイン妥当性レビュー・数値監査の両プロンプトに、今回のターンでwrite_agreementが実際に成功したか（`state["expert_wrote_agreement"]`/`state["user_wrote_agreement"]`）を明示するブロックを追加し、失敗時は「相手の発言内容にかかわらず現在の最新ホワイトボードのみが真実」「食い違えばmajor」と指示。新規`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`、`python -m py_compile`合格。D-067として記録 | P0 |
| BL-092 | 中 | `cela_main.py` (新設`DIFF_PLAN_DRAFT_VERSIONS_TOOL`/`_diff_plan_draft_versions_handler`、`call_task_plan_reviewer`) | 別AIによる`1913`ログの独立レビュー（12項目指摘）を、さらに別チャットで各項目を実際のログ行まで追跡させた結果、数値矛盾の指摘（#1 task_2_2の往復24km/48km混在、#3 task_3_4の「約1,200万円」、#4 task_3_3の赤字誤差、#7 「10人乗り」の根拠）が、task_plan_reviewerの差し戻しを経て「解消」した実態は、数値を検算・訂正したのではなく**該当する記述・タスク内容ごと削除するか抽象的な表現に差し替える**ことで、矛盾そのものを見えなくする形だったと判明。BL-087 Fix A（reviewerの過剰な精度要求がtask_plannerに存在しない数値の捏造を誘発する問題）とは逆方向の構造的パターン。ユーザー提案（ファイル化してdiffツールを使う）を受け、ファイル中心の編集への回帰（BL-074/034/040が既に解決した脆さの再導入）は避けつつ、既にDBでバージョン管理されている`plan_drafts`（BL-082、task_planner再生成のたびにauthor_role="task_planner"で版が積み増される）に対し`difflib`で機械的diffを取る方式を採用。task_plan_reviewerが以前指摘したtask_idについて記憶・印象ではなく実際の差分（数値が訂正されたか、記述ごと消えたか）で判断できるようにした。新規`tests/test_bl092_plan_draft_diff_verification.py`（8件）、`python -m py_compile`合格。D-069として記録 | P2 |
| BL-093 | 中 | `cela_main.py`（新設`THINK_TOOL`/`_think_handler`/`_reset_think_scratchpad`、`_query_AI_live`の`_CURRENT_TOOL_LOOP_ITERATION`＋think+summary機械的強制＋自動reasoningダイジェスト、tools付与済み全13関数呼び出し箇所への配線） | スクラッチパッド議論（別チャット共有）の結論。ツールループの`_StreamMessage`がモデルのreasoningを`None`固定で捨てており、次iterでモデルは前回のtool_calls/tool結果という記録だけから理由を再構築している問題を確認。当初は「reasoning消失は実害なし」と誤って結論しかけたが（`loop_messages`が全履歴を再送する事実と、reasoning自体が再送されない事実を混同）、ユーザー指摘で訂正。理由づけ（action/decided/why/rejected/rejected_why）を書かせ、tool結果として即座に全履歴を返す`think`ツールを新設し、消えるreasoningチャネルから残るtool_callsチャネルへ理由づけを退避させた。todo/issuesはopen/close必須のリスト、notesは上書きされない追記専用リストとして分離。iter番号はモデルの自己申告に頼らず`_CURRENT_TOOL_LOOP_ITERATION`から機械的に付与。MAX_TOOL_ITERを15→20へ引き上げ（D-071）。当初はDetector数値監査パス/task_planner/task_plan_reviewerの3ノード限定だったが、ユーザー指示「対象ノードは全ノードへ」を受け、tools付与済みの全ノード＋従来tools=None（単一応答パス）だった4関数＋Detectorドメイン妥当性パスをtools=[THINK_TOOL]へ変更し拡張（D-072）。さらにユーザーから「thinkを呼ぶかはモデル任せでは意味がない、reasoning引き継ぎは自動でなければならない」との指摘を受け、`think`に`summary`フィールドを追加しrequired化、「ツール呼び出しを含む全iterationはthink+非空summaryを併用すること」を`_query_AI_live`側で機械的に強制（違反時は一切実行せず差し戻し）。直近2iter分は生reasoningそのまま・それより古い分はthinkのsummaryを使う自動ダイジェストメッセージをloop_messagesへ都度差し替える設計に確定（D-074、機械的な文字数切り詰め案は「意味を成さない」と却下）。さらに、ツールスキーマの説明文修正だけでは同種の差し戻しが再発したため、各ノードのプロンプト本文にも利用可能ツール名を名指しした指示を追記（追記修正3）。新規`tests/test_bl093_think_tool_scratchpad.py`（42件、他ツール全10種のリマインダー確認・各ノードのプロンプト本文でのツール名指しを含む）・`tests/test_bl093_d074_auto_reasoning_enforcement.py`（6件、フェイクstreamingクライアントで`_query_AI_live`を直接検証）、既存テスト2件の妥当な緩和（完全一致→含有確認）、`python -m py_compile`合格。D-070（誤りを訂正・superseded）/D-071/D-072/D-074として記録 | P2 |
| BL-094 | 中 | `cela_main.py`（`call_expert`/`call_detector`数値監査パス/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`/`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`のプロンプト本文＋後半3関数への`READ_VERIFIED_FACT_TOOL`/`READ_DELIVERABLE_FILE_TOOL`新規配線） | 実ドライラン`log/2026-07-26/1749`のハルシネーション監査（別セッションのAgentによる全文精査＋本セッションでの主要箇所の裏取り）で、`read_verified_fact`/`read_deliverable_file`が`tools=[...]`に配線されツールスキーマの`description`も存在するにもかかわらず、実際にはどのノードもこれらを能動的に呼んでおらず、他タスクで既に確定した数値と矛盾する値を独自に仮定してしまう事故が繰り返し観測された（山間部片道時間が24分/36分で食い違ったまま放置、Goal Essence Analyst自身の推測が「実現可能性メモ」という架空の一次資料であるかのように後工程で「出典」扱いされる、等）。BL-093の「ツール説明文だけでは不十分で、各ノードのプロンプト本文に名指しした指示が要る」という教訓（追記修正3）と同型の問題と判断し、read_verified_fact/read_deliverable_fileを持つ当初6関数のプロンプト本文に、(1)両ツールの目的（全フェーズ横断の確定値検索／過去タスク成果物の前提込み全文参照）の説明、(2)「最低限iter=1で一度は関連キーワードでread_verified_factを呼び、他タスクの確定値・前提と文脈を同期してから作業を始めること」という思考フレームワーク上の指示、(3)思考中に「これは他タスクで既に扱われていたかもしれない」という気づきがあれば都度参照せよという指示、を追記した。Detectorには特に「数値の出所（ゴール文由来かAI自身の孫引きか）を追跡する」観点を明記。続けてユーザー指示により、当初ツール自体を持たず対象外としていた`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`にも同ツールを新規配線し同型のオリエンテーションを追記（D-076）。新規`tests/test_bl094_read_tool_orientation.py`（32件）、既存`tests/test_bl093_think_tool_scratchpad.py`のツール名指し回帰テストを更新、`python -m py_compile`合格、関連クラスタ228件Pass。D-075/D-076として記録 | P2 |
| BL-095 | 高 | `cela_main.py`（`_check_write_permission`のロール表拡張、`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`への`WRITE_AGREEMENT_TOOL`新規配線） | BL-094完了後、情報の抽出・保存・伝搬の観点でシステムを棚卸しした際に発見。BL-094でこの3関数にread_verified_fact/read_deliverable_fileを配線したことで「他ノードの確定値は読めるが、自分の判断（なぜこのフェーズ構成にしたか、なぜrisk=mediumと判定したか等）を誰にも参照可能な形で書き残せない」という読み書き非対称が生じていた。ユーザーが「タスクプランナーの意図や理由は後続タスクで見れるべき」と明示指摘。task_planner/goal_essence_analystはExpert同様`status="Proposed"`限定、task_plan_reviewerはDetector等と同じ`status="Rejected"`限定（BL-062と同型のSUPERSEDEパターン）としてロール表を拡張し配線。新規`tests/test_bl095_task_planner_write_agreement.py`（25件）、`python -m py_compile`合格、関連クラスタ256件Pass。`done`化。 | P1 |
| BL-096 | 中 | 新規（`issue_log`テーブル、`WRITE_ISSUE_TOOL`/`READ_ISSUES_TOOL`、`call_detector`/`generate_user_utterance`/`reflection_node`/`facilitator_node`への配線） | 同じ棚卸しで発見。(1) Detectorの`observations`（軽微な気づき、BL-051）が`agreements`/`verified_facts`のどちらにも保存されず、直後数ターンのchat_history windowから外れると実質消滅する。(2) `constraint_issue`が`major`の場合はSUPERSEDEが強制されるが、`minor`は「記録するだけ」で終わり、後続タスクで実は重大だったと判明しても再浮上する保証がない。ユーザーは両者を同じ穴（正式なissue管理DBの不在）として統合し、「正式にissue管理DBと配線を作る時にそちらへ入れて管理する」方針。**基本設計v3確定（実装対象）**（累積回数しきい値による機械的エスカレーション＋厳格化したREAD経由の再発カウント、重複検知キーは`topic`単独、`severity=major⇒status=escalated`不変条件、reflectionのdiscussion_status機械的上書き＋facilitatorへの構造化データ注入、エスカレーション解除の復帰通知、MVPはDetector/User AIの2ノード限定、詳細は[BL096_basic_design.md](BL-096/BL096_basic_design.md)、改訂理由は[D-079](../decision_log.md#d-079-bl-096設計をv2に改訂read経由の再発カウント追加severitymajorstatusescalated不変条件topictask_idキー変更)・[D-080](../decision_log.md#d-080-bl-096設計をv3に改訂重複検知キーをtopic単独に差し戻しreflectionfacilitatorへの機械的接続とエスカレーション解除通知を追加)）。**実装完了**（`issue_log`テーブル・`WRITE_ISSUE_TOOL`/`READ_ISSUES_TOOL`・`_write_issue_impl`/`_check_issue_permission`/`_read_issues_handler`/`get_issues_from_db`/`_bump_issue_occurrence`/`_get_escalated_issues`/`_build_escalation_resume_notice`、`call_detector`の自動バックアップ書き込み、`generate_user_utterance`配線、`reflection_node`/`facilitator_node`/`call_reflection`/`call_facilitator`の機械的接続、`LineageState`の`escalation_active`/`escalation_just_resolved_notice_pending`フィールド。新規`tests/test_bl096_issue_log.py`42件、`python -m py_compile`合格、関連クラスタ198件Pass）。実LLM再ドライランでの効果確認は次回待ち。`done`化。 | P1 |
| BL-097 | 中 | `cela_main.py`（`think`ツールの構造化フィールド運用、確定値/推定値/運用ルールの区分表示、task_plan_reviewer等のスコープ逸脱防止・最終自己点検） | ユーザーが別AIに`log/2026-07-26`ドライランのログと本体プログラムを独立レビューさせた結果の指摘。(1) ログ上、どこまでがtask由来の確定値でどこからが今回追加した仮定・運用ルールかが埋もれやすい。(2) `think`の`decided`/`why`/`rejected`/`rejected_why`が空欄のまま進む場面があり、何を採用し何を捨てたかを後から追いにくい。改善提案として(a)数値の出所ラベル（確定値/推定値/運用ルール）の強制、(b)スコープ逸脱禁止の明文化（冒頭・末尾の両方で確認）、(c)最終チェックリスト固定化（確定値の引用漏れなし/新規数値の捏造なし/他タスクへの越境なし/責任分界が閉じている、の4項目自己点検）が挙げられた。BL-087 Fix A/C（アンチパターン明記・条件明示）およびBL-093/094の枠組みと同系統の改善。設計未着手（`open`、BL-096のPlan mode設計の後に着手予定）。 | P2 |
| BL-098 | 低 | `cela_main.py`（ファイル分割：永続化層/ツール層/プロンプト・ノード層/UI・ログ層） | ユーザーが別AIに`cela_main.py`本体を独立レビューさせた指摘（続報）。`cela_main.py`が7300行超で、ロギング・DBスキーマ・python_repl・Record/Replay・各種ツール定義・LangGraphノード実装・プロンプト本文までを単一ファイルで抱えており「巨大な一枚岩」状態。プロトタイプとしては成立しているが、商用の長期運用を見据えると責務分離（少なくとも永続化層／ツール層／プロンプト・ノード層／UI・ログ層の4分割）が保守性のために望ましいとの指摘。設計未着手（`open`、MVP機能追加より優先度は低く、機能面が一段落してから着手する方針）。 | P3 |
| BL-099 | 中 | `cela_main.py`（モジュールレベルグローバル`_CURRENT_RUN_ID`/`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`等、`get_max_tokens`の`label.lower()`部分一致制御、`think`必須化の実効性がモデル遵守に依存する構造） | 同じ別AIレビューの指摘。(1) `_CURRENT_RUN_ID`等（`cela_main.py:1061`付近）のようなモジュールレベル変数に状態管理をかなり依存しており、規模が上がると再現性・追跡性が落ちやすい。(2) `get_max_tokens`（`cela_main.py:318`）が`label.lower()`の部分一致（`MAX_TOKENS_BY_ROLE`のキーワード）でmax tokenを切り替える「ゆるい制御」になっている。(3) BL-093の`think`必須化は`_query_AI_live`側で機械的強制済みだが、最終的には「この応答に`think`が入っていること」を前提にフローが回っており、tool-call層でのより網羅的な機械的バリデーションの余地がまだ残る、との指摘。設計未着手（`open`、(1)(2)はBL-098の層分離と合わせて検討、(3)は既存のBL-093機械的強制の延長として個別に検討可能）。 | P2 |
| BL-100 | 高 | `cela_main.py`（`ESCALATE_PREMISE_CONCERN_TOOL`/`_escalate_premise_concern_tool_impl`、R5 GoalShiftEvent周辺、新設予定のBL-096 issue_logとの統合） | 同じ別AIレビューの続報。エージェントが前提（例:「移動手段はバスである」）を疑い、代替案（例:「オンデマンドタクシー補助」）を提案する際、単に提案するだけでなく「問題設定を変更した理由」を構造化して系譜として残すべきとの指摘。具体的には(1)疑った前提、(2)疑った理由、(3)代替仮説、(4)期待される利点、(5)この提案を採用するために追加で必要な情報、の5項目セット。現状の`escalate_premise_concern`（R5/BL-086、goal本文の前提を疑い改訂を提起する既存ツール）や新設予定のBL-096 `write_issue`は、懸念の「有無」と「内容の自由記述」は記録するが、上記5項目のような構造化された代替仮説・採用条件までは持たない。BL-096（issue管理DB）の基本設計と統合して検討する価値が高い（採用条件＝BL-096の`resolution_note`相当、代替仮説＝新規フィールド）。設計未着手（`open`、BL-096の基本設計の中で構造化フィールドとして統合するか、`escalate_premise_concern`側の拡張とするかを検討）。 | P1 |
| BL-101 | 高 | `cela_main.py`（新設`READ_PLAN_DRAFT_TOOL`/`_read_plan_draft_handler`/`get_latest_plan_draft_by_task_id`、`call_task_planner`への配線） | 実ドライラン`log/2026-07-27/1438`でユーザーが発見。task_plan_reviewerに差し戻されたtask_plannerが、前回自分が作成した「フェーズ・タスク表」ホワイトボード（`plan_drafts`、BL-082/BL-087 Stage2）を一切参照せず、ゴール文と差し戻し指摘の要約テキストだけを頼りに毎回全フェーズ・全タスクを一から作り直している実例を確認。`task_plan_reviewer_node`が`state["phases"] = []`で前回計画を完全消去し、`call_task_planner`は`reviewer_feedback`（自由文）のみを受け取り、`plan_drafts`に書き込まれているはずのtask_plan_reviewerの個別指摘（`_append_reviewer_comment_to_plan`）も一切プロンプトに渡っていなかったことが原因。加えて副次的に、BL-095でtask_plannerがwrite_agreement（`entry_type="Decision"`, `topic="task_planner_phase_design"`）で記録した判断根拠を、task_plan_reviewerが`read_deliverable_file(task_id="task_planner_phase_design")`で読もうとしても`entry_type="Deliverable"`限定の逆引きのため常に`not_found`になる不整合も発見（ログ2414-2415/4169-4170行目）。まず単純な対策として、task_planner自身が能動的に`plan_drafts`の最新版（task_plan_reviewerの個別指摘込み）を確認できる読み取り専用ツール`read_plan_draft`を新設し、差し戻し時のプロンプトで「指摘のあったtask_idは必ずこのツールで前回の記述を確認してから、その部分だけを修正する」よう指示した（`entry_type="Deliverable"`限定の問題は未対応、別途Fix 2として検討）。より確実な対策として、`state["phases"]`を消去せず前回計画をbaselineとして保持し、task_plannerには変更が必要な部分のみをパッチとして出力させ、Python側で機械的にマージする方式（ユーザー提案）も検討したが、まず`read_plan_draft`ツールでの効果を実ドライランで確認してから判断する方針とした。新規`tests/test_bl101_task_planner_plan_draft_tool.py`（8件）、`python -m py_compile`合格、関連クラスタ218件Pass。 | P0 |
| BL-102 | 高 | `cela_main.py`（`call_detector`、`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`のグローバル設定タイミング） | 実ドライラン`log/2026-07-27/1551`で発見。同ドライランの直前に、Detectorのドメイン妥当性レビューパス（第1段）にBL-096の`write_issue`/`read_issues`等の監査ツール群を追加したばかりだったが、`_CURRENT_CALLER_ROLE = "detector"`の設定が`call_detector`関数の後半（第2段・数値監査パスの直前）にしか存在せず、第1段実行時点では直前ノード（この回は`call_expert`が設定した`"expert"`）のroleが漏れたまま残っていた。結果、Detector(Domain Review)が`write_issue(action_type="CREATE", topic="operator_shortage_peak", ...)`を呼んだ際「expertはaction_type='CREATE'のwrite_issueを実行できません（許可: []）」で権限エラーとなり、後続タスクへ引き継ぐべきだった有効な懸念（オペレーター最低2名常駐要件とピーク時1名充当の矛盾）がissue_logへ永続化されず、`observations`欄への記載のみに留まった（BL-096が想定する「後続タスクからも検索可能」という利点が第1段では機能していなかった）。`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`の`global`宣言と代入を`call_detector`関数冒頭（第1段の前）へ移動し、後半の重複代入は削除して修正済み（`done`）。 | P0 |
| BL-103 | 中 | `cela_main.py`（`_build_hydrate_context`/`get_last_think_summary`新設/`_build_escalation_pin_text`新設/`expert_node`/`generate_user_utterance_node`/`generate_user_utterance`） | ユーザーからhydrate（ノード間コンテキスト引き継ぎ）設計の相談。ユーザー自身が過去に設計した`NPU-Context-Saver`のhydrate機構（pin・Time-Aware RAG・トークン予算による段階的間引き）と対比した結果、トークン予算制御（NPUはローカルSLMのcontext枯渇対策）とRAG（CELAは`read_verified_fact`等のプル型ツールで代替可能）は見送り、(1)`issue_log`のescalated行をhydrate_contextへ常時マージするpin導入、(2)BL-093の`think`ツール最終呼び出し内容（decided/why）を`decisions.why`に使い要約の質を上げる、(3)escalated issueをcall_expert/generate_user_utteranceのambient contextにも詳細込みで注入（facilitatorのフィードバックはchat_history末尾追記のみでchat_history_window超過後に消えるため、注入は「facilitatorの発言が消えた後の穴埋め」であり重複競合ではないと判断）の3点をユーザー承認のもと設計。調査中に副次的な2つの欠落を発見しスコープに追加：`generate_user_utterance_node`がUser AIの発言を一度も`decisions`テーブルに記録しておらずhydrate要約チャネルから完全に欠落していたこと、`generate_user_utterance`内の独自インラインタイムラインが`get_decisions_from_db`の全件を無制限に展開しておりExpert側の窓付き`_build_hydrate_context_from_db`と非対称だったこと（後者はwindowなしで置き換え、前者は共通hydrate関数に統合して解消）。設計書は`docs/design/back_log/BL-103/BL103_basic_design.md`に保存。実装完了（`done`）：新規`get_last_think_summary()`/`_build_escalation_pin_text()`を追加し、`expert_node`のwhy改善、`generate_user_utterance_node`への欠落していたmake_decision追加、`generate_user_utterance`の無制限インラインタイムラインを`_build_hydrate_context_from_db`へ置き換え、call_expert/generate_user_utterance双方へescalation pin注入を実装。新規`tests/test_bl103_hydrate_context_improvements.py`（12件）、既存`tests/test_bl086_escalation_freeze_goal_revision.py`の2テストがgenerate_user_utterance_nodeの新規DB書き込みで壊れたため、DBモック追加で修正。`python -m py_compile`合格、関連クラスタ179件Pass。 | P1 |
| BL-104 | 中 | `cela_main.py`（新設`READ_PROJECT_PLAN_TOOL`/`_read_project_plan_handler`/`_build_project_plan_toc`、全ノードのプロンプト構造並び替え） | ドライラン`log/2026-07-27/1739`のレビュー中、`call_expert`の`phases_json`（全フェーズ・全タスクの完全なJSON、13,361文字）が毎回無条件で注入されているが、`_build_task_scope_context`経由で既に`current_task_json`/`verified_facts_json`/`deferred_notes_text`が個別に届いており機能的にはほぼ重複であることが判明。`phase_id`/`task_id`/`title`のみの軽量な目次（ToC）を常時表示に変更し、全文詳細が必要な場合のみ新設`read_project_plan`ツールで能動的に取得する方式に変更（User AI/`call_task_plan_reviewer`は全体像の把握が本質的に必要なため`phases_json`全文を維持）。あわせてユーザーから、OpenRouterのプロンプトキャッシュヒット率が40%→5%へ急落したとの報告があり調査。`call_expert`のプロンプト組み立て順が、変動する内容（expert_name・ターン数表示・agreements_text等）を冒頭に、分量最大の固定指示文ブロックをその後ろに配置しており、プレフィックスキャッシュ（先頭一致ベース）が冒頭の些細な変動で丸ごとミスする構造だったことを確認（ツールループの反復回数増加による希薄化も併発している可能性はあるが、急落幅からプレフィックス不一致が主因と判断）。固定指示文を冒頭・動的データを末尾に配置する構造へ並び替え。ユーザー指示「他のノードも順次プロンプト順の整理を進めてください」「並び変え続行してください」により、`call_expert`を皮切りに全ノードへ同一原則を順次展開。設計書は`docs/design/back_log/BL-104/BL104_basic_design.md`に保存。**実装完了**: `call_expert`（read_project_plan/ToC化＋並び替え）・`generate_user_utterance`（並び替え、phases_json全文は仕様通り維持）・`call_detector`（domain_prompt・数値監査用prompt両方）・`call_orchestrator`・`call_resource_arbiter`・`call_facilitator`・`call_integrator`・`call_reviewer`・`call_task_plan_reviewer`。各ブロックの位置的参照（「上記の」「後述の」等）を個別確認した上で、参照を持つブロックは相対位置を維持したまま並び替え。**意図的に見送り**: `call_reflection`は「上記の」参照が多段連鎖しており固定/動的の機械的分離が構造上困難なため、自己完結するBL-093説明の移動のみに留めた。`call_task_planner`は「冒頭の指摘欄で指示した通り」という位置的参照がreviewer_feedback_blockの先頭配置を前提としており、かつ再分解時以外は呼ばれない低頻度ノードのため据え置き。`call_goal_essence_analyst`はプロジェクト開始前に1回だけ呼ばれ並び替えのキャッシュ効果がゼロのため据え置き。新規`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`（36件）、`python -m py_compile`合格、関連クラスタ327件Pass。実LLM再ドライラン（`log/2026-07-27/1911`、call_expert等3ノードまでの並び替え適用時点）でキャッシュヒット率5%→13-15%への改善を確認済み、異常挙動・品質劣化なし。全ノード適用後の効果は次回ドライラン待ち。 | P1 |
| BL-105 | 中 | `cela_main.py`（`run_ai_vs_ai_loop`の自前JSON checkpoint機構、`generate_user_utterance_node`）※未実装・設計検討のみ | `log/2026-07-27/2044`のツール使用失敗調査中に`⚠️ role連続を検出: index 3,4 = 'user'`という警告を発見。追跡した結果、`run_ai_vs_ai_loop`（cela_main.py:7812）が`--resume`時に必ず`app.stream(state, ...)`をグラフのentry_point（`graph.set_entry_point("goal_essence")`、cela_main.py:7572）から再実行する自前実装であることが判明。`goal_essence`/`task_planner`/`task_plan_reviewer`は`goal_essence_done`/`plan_review_done`等のフラグで再実行をスキップするが、その直後の`generate_user_utterance_node`（cela_main.py:6348）には同種のガードが無く、無条件に`state["chat_history"].append({"role": "user", ...})`する（6380行目）。差し戻し時の重複防止pop（6357-6361行目）は`constraint_issue == "major"`の時しか発火しないため、前回の一時停止が「User AIの発言をchat_historyに追記した直後、Expertがまだ応答する前」で発生していた場合、resume時にもう一つuser発言が積まれ、role連続が生じる。ユーザーから「本来はLangGraphのcheckpointerを使えば真の一時停止が利くのでは」との指摘があり、Context7で現行のLangGraph公式ドキュメント（`/websites/langchain_oss_python_langgraph`）を確認。`compile(checkpointer=...)` + `thread_id`ベースの再開はentry_pointからの全体再走行ではなく中断したノードの続きから再開するため、今回発見したバグの根本解消になることを確認した。ただしノード単位のcheckpointは「ノード内部の途中（Expert/Detectorの`_query_AI_live`ツールループの最中）」でのCtrl+Cには対応できず、そのノードは最初から再実行される。公式ドキュメントにも"Do not create new records before an `interrupt` call. Re-running the node upon resume will create duplicate records, leading to data inconsistencies."と明記されており、これがユーザーの懸念（「ツールで登録しようとしたら既にDBにあった、という混乱」）の根本原因であることを確認した。対応は3段階の選択肢として整理し、いずれを採用するかは当初**未決定**だったが、後日ユーザーから改めて実装要望があり、Tier 1（LangGraph本来の`checkpointer`+`thread_id`ベースの再開）のみを採用する方針で合意（Tier 2は将来HITL機能の具体設計時に着手）。**実装完了（`done`）**：自前JSON checkpointを`SqliteSaver`（`cela_checkpoints.db`）+ `thread_id`（==`run_id`）ベースへ全面移行し、`None`入力で「中断した直後のノードから」再開するよう`run_ai_vs_ai_loop`を書き換えた。新規テスト`tests/test_checkpoint_resume.py`（6件）追加、既存関連4テストファイル計85件無退行、フルオフラインスイート700件Pass。詳細は本表下部の詳細セクション・`docs/design/back_log/BL-105/BL105_basic_design.md`参照。 | P2 |
| BL-106 | 高 | `cela_main.py`（`_query_AI_live`のツールループ内、自動reasoningダイジェスト機構） | BL-104適用後もキャッシュヒット率が1時間平均5.5%（分単位では0%も目立つ）とユーザーから報告があり調査。原因は`_query_AI_live`のBL-093/D-074自動reasoningダイジェスト（`auto_reasoning_history`）が、system prompt（index 0）の直後・index 1という**tool呼び出し履歴（index 2以降、iterごとに肥大化する本来一番キャッシュ効果が大きい部分）より手前**に、毎iter内容が変わるメッセージとして`insert`/同一index上書きされていたこと。プレフィックスキャッシュは絶対位置での先頭一致を見るため、digest（index 1）の長さがiterごとに伸縮するたびに、それより後ろにある実質的な会話履歴全体（内容自体は不変）の絶対位置がずれ、キャッシュが毎iterミスしていた。ユーザーから「古いiterの要約部分は不変のはずでは」との指摘があり、digest文字列内の既に確定した要約部分自体は実際に不変であることを確認・訂正した上で、問題の本質は「不変部分と可変部分が同じ1メッセージに同居し、かつそのメッセージがtool履歴より手前にある」ことだと整理。**実装完了（`done`）**: digestメッセージをオブジェクト参照で追跡し、都度`loop_messages`の末尾から前回分を取り除いて末尾に付け直す方式に変更（`auto_reasoning_digest_index`固定位置差し替え→`auto_reasoning_digest_message`参照ベースの末尾再配置）。既存テスト`tests/test_bl093_d074_auto_reasoning_enforcement.py`のdigest位置検証（旧: index 1固定）を新方式（末尾）に合わせて更新。`python -m py_compile`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass。実LLM再ドライランでの効果確認は次回待ち。 | P1 |
| BL-107 | 高 | `cela_main.py`（`_query_AI_live`の`extra_body`構築部、`_USE_STICKY_SESSION_ROUTING`フラグ） | BL-106修正後もユーザーから「iter時のキャッシュヒットは0%のまま」と報告。OpenRouter公式ドキュメント・ブログをWebFetchで調査し、「`provider.order`を手動指定するとsticky routing（同一会話を同じバックエンドへ固定する仕組み）が無効化される」ことが根本原因と判明。既存コードは`extra_body["provider"] = {"order": ["novita/fp8","parasail/fp8"], "allow_fallbacks": False}`を常時指定しており、これがsticky routingを恒常的に無効化していた。ユーザーから「provider固定はだいぶ前からで、それでも50%前後あった。26日17時台以降に急落した」との指摘を受け、`git log`でBL-093コミット（`4a0bb46`、2026-07-26 18:03、"including previously tools=None single-shot ones"）を確認。BL-093以前は多くのノードがtools=Noneの単発呼び出し（sticky routing不要のクロスコールキャッシュで50%前後を維持）だったが、BL-093でほぼ全ノードがtoolsループ経由に切り替わり、元々存在した「ループ内はprovider.orderのせいで0%」という弱点の影響が急拡大したと整理し、ユーザーの時系列指摘と矛盾しないことを確認。**実装完了（`done`）**: 切り替えフラグ`_USE_STICKY_SESSION_ROUTING`を新設し、`True`時は`provider.order`を送らず`extra_body["session_id"] = f"{_CURRENT_RUN_ID}-{label_lower}"`でsticky routingを有効化、`False`に戻せば元の`provider.order`固定へワンラインで復元可能。`python -m py_compile`合格、関連クラスタ135件Pass。実LLM再ドライランでの速度・キャッシュヒット率への効果確認はユーザー実施予定。 | P1 |
| BL-108 | 高 | `cela_main.py`（`_query_AI_live`の自動reasoningダイジェスト構築部） | BL-107適用後、ユーザーから「改善したがやはり微妙かもしれない」と報告があり、digestの実際の中身をprintするよう依頼された。調査の結果、`log_with_prompt.md`はツールループの最初のiterationしか記録しておらずdigestの実物は載っていないことが判明したため、`log_no_prompt.md`の生reasoning/summaryから手元で再構築。窓方式（直近2iterは生・古いのは要約）では、窓の境界に当たる古いiterが生reasoning全文→summaryへ切り替わるたびdigestの中身自体が毎iter変化しており、生reasoning自体も1回あたり数千文字（最大6,077文字）に達しdigestの大半を占めることを確認。ユーザーから「要約せず単純に生ログを積み上げた方がキャッシュが効き安い・シンプルではないか」との提案があり、同ログで試算（iter8時点で要約方式6,341文字 vs 単純累積19,324文字、約3倍）した上で提案を支持。**実装完了（`done`）**: `_AUTO_REASONING_VERBATIM_ITERS`の窓管理と`_THINK_REASONING_LOG`からのsummary逆引きを廃止し、全iterationの生reasoningを要約せず末尾追記し続ける単純な累積方式へ全面置換。既存テスト2件を新方式に合わせて改名・修正。`python -m py_compile`合格、関連クラスタ135件Pass。プロンプト絶対サイズ増加のトレードオフはユーザー承認済み。実LLM再ドライランでユーザーが「30分平均で45%くらいに回復」と確認（2026-07-28）。ただし机上試算では損益分岐点（約74%）未達で$コスト面は要実測。 | P1 |
| BL-109 | 中 | `cela_main.py`（`call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`のtools引数、`_query_AI_live`のreasoning_effort_level判定） | ユーザーがログを見て「Decision Extractorってthinkしかツールを持っていない？」と質問。調査の結果、この4ノードはいずれもDB読み書き不要な単発判定・抽出タスクで、`think`ツールの本来の存在理由（複数iterをまたぐreasoning引き継ぎ）が適用されないと判明。ユーザーへ「メモ帳は要らないのでは」と回答したところ「なるほど、ではthinkしかツールがないノードは抜きましょう」と全4ノードの差し戻しを指示された。**実装完了（`done`）**: 4ノードとも`tools=[THINK_TOOL]`を削除しtools=Noneへ差し戻し、案内文も削除。副次的に、`orchestrator`/`facilitator`は`reasoning_effort_level`を`elif tools is not None`経由でしか得ていなかったため、tools=None化のサイレントな副作用でreasoningが無効化される罠を発見・修正（両ラベルを明示条件へ追加）。`_reset_think_scratchpad()`はBL-103のノード境界マーカーとして機能維持のため削除せず。関連テスト更新、`python -m py_compile`合格、関連クラスタ145件Pass。実LLM再ドライランでの効果確認は次回待ち。 | P2 |
| BL-110 | 中 | `cela_main.py`（`_query_AI_live`のthink機械的強制ロジック、think関連の英語ツールスキーマ14箇所・日本語プロンプト10箇所の案内文） | BL-109の議論を受け、ユーザーが「であるならば、自由なthinkの使用も意味がないですね。今はコンテキストを丸ごと引き継いでいるので、think自体も意味がないか」とBL-093/D-074の機械的強制そのものを問い直した。調査の結果、ネイティブのreasoning（delta.reasoning）はthink呼び出しの有無に関わらず毎iter無条件で蓄積されており、BL-108によりそのままdigestとして引き継がれるため、think機械的強制が本来解決していた問題（reasoning消失）は既に別経路で解決済みと判明。ユーザーが「thinkは残して、他ツールとの強制は外してください」と指示。**実装完了（`done`）**: `_query_AI_live`から差し戻し分岐を削除しBL-093以前と同型の無条件dispatch構造に戻した（thinkツール自体・TOOL_DISPATCH・digestロジックは維持）。あわせて、もう存在しない強制を前提にした案内文を英語14箇所・日本語10箇所とも全面修正。関連テスト2件を実行される前提へ置換、モジュールdocstring更新。`python -m py_compile`合格、関連クラスタ130件Pass。実LLM再ドライランでの効果確認（think差し戻し起因の往復削減）は次回待ち。 | P2 |
| BL-111 | 高 | `cela_main.py`（`_query_AI_live`の自動reasoningダイジェスト構築部） | BL-108/BL-110適用後もキャッシュヒットが改善しないため、ユーザーが`_query_AI_live`のコードをGeminiに提示し第三者レビューを依頼。Geminiの指摘: BL-108は「全iter分を1メッセージに再結合→古いdigest削除→末尾に付け直す」方式だったため、新規tool呼び出しメッセージが必ずdigestの手前に追加され、次のリクエストではdigestの旧位置に別のメッセージが来ることになり、そこから後ろ全体が毎iterプレフィックス不一致になっていた。プレフィックスキャッシュの絶対条件「一度追加したメッセージは二度と変更・削除・移動しない」を満たせていなかったと判明。実際にコードをトレースし、iter2向け・iter3向けリクエストを比較して指摘の正しさを確認。**実装完了（`done`）**: 全iter分の再結合をやめ、iterationごとの生reasoningを独立した新規systemメッセージとして末尾に追記するだけ（真のappend-only）に変更。`auto_reasoning_history`/`auto_reasoning_digest_message`は不要になり削除。新規`test_bl111_consecutive_requests_are_a_strict_prefix_of_each_other`で「iterNのリクエストがiterN+1のリクエストの厳密な先頭部分になっている」というプレフィックスキャッシュの必須条件そのものを回帰テスト化。関連クラスタ131件Pass、`python -m py_compile`合格。実LLM再ドライランでの効果確認は次回待ち。 | P1 |
| BL-112 | 中 | `cela_main.py`（User AI/`call_facilitator`相当のissue登録ロジック、および`Detector`とUser AIの`write_issue`呼び出し箇所） | `log/2026-07-28/1420`のドライランレビュー中に発見。Detectorがtask_1_1の成果物レビューで3件のissueを作成済み（`task_1_1_折り返し時間3分`、`task_1_1_実効輸送力の矛盾`、ほか）にもかかわらず、User AIが後続の承認ステップで同一の懸念点を`task_2_2_折り返し時間の現実性`・`task_2_2_実効輸送力と車両定員の矛盾`等、別のtopic名で重複登録していた。ログ上、User AIは思考ログで「Let me read the current issues first to see what's already logged」と述べていたが、実際には`read_issues`を呼ばずにそのまま`write_issue`（CREATE）を3件連続実行しており、直前の`read_issues(list_all=true)`呼び出しはtask_1_1着手前（まだissueが0件の時点）のものだった。「確認する」という意図と実際のツール呼び出しが乖離しており、後続タスクが2つのtopicを別問題として扱うと同一論点への対応が分断されるリスクがある。**状態**: `open`（コード修正は未着手、まず記録のみ）。 | P3 |
| BL-113 | 高 | `cela_main.py`（THINK_TOOLスキーマの`description`・`summary`パラメータの`description`） | BL-112起票の流れでユーザーからプロンプト全体の整理相談を受け、3体のExploreエージェントで全ノードのプロンプト構成・ツールschema重複・ドメイン特化表現を並行調査。BL-110で他14ツールのスキーマ`description`は`"[BL-110] Optionally call \`think\`...it is no longer required..."`へ正しく書き換えたが、**THINK_TOOL自身のスキーマだけ書き換え漏れ**になっており、撤廃したはずの`"MANDATORY RULE (enforced mechanically, not a suggestion): EVERY SINGLE response...MUST include a think call...NONE of that response's tool calls...will be executed"`という文言がそのまま残っていた（実装と矛盾する誤情報）。加えて`summary`パラメータの説明にも、BL-108/BL-111で撤廃済みの旧window方式（`raw reasoning window`、`ages out`）を前提にした表現が残っていた。ユーザーはAskUserQuestionで、他の3件（`call_orchestrator`の静的/動的順序バグ、バス特化表現の一般化、重複ボイラープレート統合）はスコープ外とし、この書き換え漏れ修正のみを最優先で対応する方針を選択。**実装完了（`done`）**: `description`をBL-110と同トーンの「thinkは任意、生reasoningはthink呼び出しの有無に関わらずネイティブに自動蓄積される（BL-108/BL-111）」という実態に即した説明に書き換え、`summary`パラメータの説明からも旧window前提の表現を削除。`"required": ["action", "summary"]`は変更なし。THINK_TOOLのdescription文字列を直接assertするテストが無いことを確認済み。`python -m py_compile`合格、`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_r3_smoke.py`計97件Pass。実LLM再ドライランでの効果確認は次回待ち。 | P1 |
| BL-114 | 中 | `cela_main.py`（`call_orchestrator`のプロンプト構築部） | プロンプト整理のための3体のExploreエージェント調査（BL-113と同じ調査、カテゴリA）で発見。`call_orchestrator`だけ、BL-104が謳う「静的先頭・動的末尾」のコメントと実装が矛盾（動的な`goal_context`が先頭）していた。**実装完了（`done`）**: 静的ブロック（役割・肩書き生成指示・BL-078）を先頭、動的ブロック（`goal_context`→`user_input`→`agreements_text`→`history_text`）をその後、JSON形式指示を末尾（`call_task_plan_reviewer`と同じ配置）へ並び替え。コメントも実態に合わせて修正。既存の順序回帰テスト（`test_bl104_project_plan_toc_and_prompt_reorder.py`）が無修正でPassすることを確認。 | P2 |
| BL-115 | 低 | `cela_main.py`（各ノードプロンプト内のボイラープレート説明文、`call_decision_extractor`の未使用`prompt_old`ブロック） | 同調査（カテゴリB）で発見。ノードプロンプト側に「think任意呼び出し」「read_verified_fact/read_deliverable_file同期」「同じ検証・計算を繰り返さない」等の重複ボイラープレートが多数分散、`call_decision_extractor`に未使用デッドコード`prompt_old`（約60行）も存在。**実装完了（`done`）**: `prompt_old`削除。モジュールレベル共有定数`_BL093_THINK_VALUE_PARAGRAPH`/`_THINK_TRAILER_SENTENCE`と共有関数`_verification_throttle_warning()`を新設し、byte-identicalまたは近似していた箇所（`call_task_planner`/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`call_goal_essence_analyst`/`generate_user_utterance`/`call_task_plan_reviewer`）に適用。`call_detector`内の`domain_prompt`/`prompt`間の重複（気づき欄・issue引き継ぎ説明）はローカル変数（`_observations_block`/`_issue_carryover_prefix`）で関数内集約。BL-094同期説明はパラメータ化ヘルパー化を試みたが、`tests/test_bl094_read_tool_orientation.py`が各関数自身の`inspect.getsource()`にツール名リテラルを要求するため断念し、各関数にliteralのまま残した（試行錯誤の経緯を`_THINK_TRAILER_SENTENCE`直後のコメントに明記）。同様の理由でツール一覧文（「あなたが使えるツールは...」）もヘルパー化せず各呼び出し元にインラインで維持。`call_expert`の`system_prompt`/`light_system_prompt`の意図的な二重化（BL-025）は統合していない。新規回帰テスト2件追加、既存テスト11件（`test_bl087_*`/`test_bl089_anti_repetition_instructions.py`/`test_bl094_read_tool_orientation.py`）をリファクタ後の構造に合わせて更新。フルオフラインスイート514件Pass。 | P3 |
| BL-116 | 低 | `cela_main.py`（`call_task_plan_reviewer`/`call_task_planner`/`call_orchestrator`/`call_expert`/`call_detector`/`call_decision_extractor`/`generate_user_utterance`のプロンプト文字列） | 同調査（カテゴリC）で発見。バス交通シナリオでのドライラン実績から生まれた具体的な数値・ドメイン例が複数ノードのプロンプトに埋め込まれていた。**実装完了（`done`）**: `call_task_plan_reviewer`（「山間部2km≒ルート全体13.33km」等）・`call_task_planner`（「車両単価2,500万円×初期予算1億円から3台」等）・`call_orchestrator`（専門家タイトル例）・`call_decision_extractor`（「車両は3台体制とする」）の具体的数値・ドメイン例を、教訓（Reviewerの絶対値強要によるハルシネーション誘発、派生値の根拠併記、専門家タイトルの具体性、Decision分類の例示）を保ったままドメイン非依存の一般化された表現へ置換。`generate_user_utterance`のf-string由来のゴミ引用符混入バグ（各行が個別に閉じられているかのように書かれ`\n"`がプロンプト本文へリテラル混入）も修正、再発防止の回帰テスト2件を追加。確認のみ（変更不要）: `call_expert`/`call_detector`/`generate_user_utterance`の労基法・シフト関連の記述は既に汎用的な表現であることを確認済み。対象外（スコープ外、変更なし）: `run_ai_vs_ai_loop`のCLIデフォルトデモゴール文字列はユーザーが選択する実行シナリオでありノード側指示文の話ではないため対象外。 | P3 |
| BL-117 | 低 | `cela_main.py`（全13ノードのプロンプト文字列。特にGoal Essence Analyst/Task Planner/Task Plan Reviewer/Orchestrator/Expert/Detector/Decision Extractor/Resource Arbiter/Reflection/Facilitator/Integrator/Reviewer/User AIの各ノード） | ユーザーがGeminiに依頼して作成した「各ノードに適したドメイン非依存の思考フレームワーク」提案表（例: Task Planner=WBS+MECE、Expert=ReAct+仮説検証サイクル、Detector=悪魔の代弁者+ファクトチェック等）の評価を依頼された。BL-116（バス特化例の一般化）の受け皿になりうる提案のため、各ノードの実装（docstring・実際のプロンプト本文）と突き合わせて検証した。結果、13ノード中9ノード（Task Planner/Task Plan Reviewer/Orchestrator/Expert/Detector/Decision Extractor/Reflection/Integrator/Reviewer）は提案フレームワークが実装と高い整合性を持ち採用可（◎）と判定。残り4ノード（Goal Essence Analyst/Resource Arbiter/Facilitator/User AI）は部分的に妥当だがギャップがある（△）と判定: Goal Essence Analystは「本質の言語化」観点はデザイン思考+5 Whysと合うが「大まかな実現可能性チェック（python_repl概算）」という観点1が提案に含まれていない。Resource Arbiterのトレードオフ分析は良い一致だがMoSCoW（Must/Should/Could/Won't）は現状未実装で導入するなら実質的な出力形式変更が必要。Facilitatorのリフレーミングは良い一致だがORIDモデルは現状未実装の具体的4段階質問技法で導入するなら実質的な設計が必要。User AIはOODAループという軍事由来サイクル名を書くだけでは効果が薄い懸念があり「発注者統制思考」の方が実務的に効きそう。全体所感として、フレームワーク名を書くだけの「ラベル貼り」に終わらせず具体的な手順・チェックリストまで落とし込む必要があること、BL-116で問題視した冗長性と衝突しないよう1ノードにつき主軸1つ+補助1つ程度に抑えるべきことを付記。ユーザーがAskUserQuestionで「評価のみで一旦区切り、実装は別途スコープを決めてから着手する」を選択。**状態**: `open`（評価のみ完了、コード変更は未着手。△評価の4ノードやBL-116との統合方針は次回スコープ確定時に相談）。 | P3 |
| BL-118 | 低 | `cela_main.py`（単一ファイル約8,000行超。ノード関数群・ツールschema定義・DBアクセス層・ロギング等が全て同一ファイルに同居） | BL-117の議論の流れで、ユーザーが「プロンプトの集約化（外部化）で言うと、今は1つのpythonで大きな岩になってしまっているので、クラスごとにファイル化するなど疎結合にしていく整理も考えたい」と新たな論点を提起。BL-115（重複ボイラープレート統合）はプロンプト文字列レベルの重複整理だが、本件はファイル構成そのもの（ノードごと/レイヤーごとのモジュール分割）の話で、コード規模・保守性に関する別種の懸念。**状態**: `open`（設計相談中、具体的な分割方針・粒度は未検討。ユーザーが「全体の進め方を考える」段階であり、実装スコープ・優先度は未定）。 | P3 |
| BL-119 | 中 | `cela_main.py`（`call_detector`の`write_agreement_status_block`、4821-4839行目付近） | `log/2026-07-28/1420`のドライラン継続レビューで発見。BL-091（今回ターンのwrite_agreement成否をDetectorに明示する仕組み）が「今回success=0」の場合に「実際には一切反映されていません...発言内容がそれと食い違う場合はmajor」という断定的な文言を出していたため、Detectorが3試行多数決で`major`（虚偽の完了報告）と繰り返し判定するループが発生し、ログの約半分を占める長時間の応酬になった。実際にはtask_1_2の修正内容は**別の過去ターンで既に登録済み**（`AG-1785225752828`）であり、「今回のターンで新規呼び出しが0回」は「過去にも一切反映されていない」ことを意味しない。Detector自身が最終的に`read_deliverable_file`で過去の登録内容を確認し「実害はない」と自己修正して収束したが、そこに至るまでのコストが大きかった。ユーザーがBL-117/D-094の議論（フレームワークの具体性は「順序」ではなく「判断基準と罠」に持たせる）を踏まえ、「これはまさに罠の一例。プロンプトに書くべき」と指摘し、今すぐ小さく修正する方針を選択。**実装完了（`done`）**: `write_agreement_status_block`の「今回success=0」時の文言に、「これはあくまで今回のターン内の話であり、過去のターンで既に登録済みの場合は0でも正常」「相手の主張が過去の登録内容と一致するかを確認してから判定する」「一致するなら虚偽ではない」という罠の説明を追加。`python -m py_compile`合格、`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`（構造的アサーションのみで文言変更の影響を受けない）7件Pass。 | P1 |
| BL-120 | 高 | `cela_main.py` (`call_reflection`, `_safe_json_parse`のfallback、`reflection_node`) | `log/2026-07-28/1420`（NVIDIA Nemotron 3 Ultra使用ドライラン）で発見。`call_reflection`の出力JSONパースに失敗すると即座に`stagnant`扱いにして正常進行中の議論を強制巻き戻していた（同一のParse errorが5回連続発火し反復生成の主因に）。**実装完了（`done`）**: 真因は層2リトライ（BL-089）を持たなかったことと特定し、`_query_and_parse_with_retry`でラップ。真にリトライを使い切った場合のみ従来通りstagnantへフェイルクローズ。新規テスト2件Pass。 | P1 |
| BL-121 | 高 | `cela_main.py` (`facilitator_node`の`facilitation_count>3`/`reviewer_node`の`review_count>3`によるhalt設定と、`route_after_facilitator`等のグラフルーティング、外側`while`ループの`if state["halt"]:`チェック、`run_ai_vs_ai_loop`の`--resume`直後の経路) | `log/2026-07-29/0751`で発見。「強制停止」「処理を完全停止」という`halt_node`由来の決定ログが2381/8542/13649行目の3箇所で記録されている（＝`facilitation_count>3`によって`state["halt"]=True`がセットされ、`route_after_facilitator`が`"halt"`ノードへルーティングされたことを意味する）にもかかわらず、いずれの直後にも本来出力されるはずの外側ループの`🚨 [HALT] システム停止シグナルが送信されました`・`🏁 評価ループが終了しました`が一度も出力されず、会話がそのまま継続している。**追加調査（本ターン）**: `log_no_prompt.md`全体（17265行）を精査したところ、`# Execution Log Started at:`（プロセス起動時の一意なバナー）は1件のみ、外側whileループの`🔷 [Turn N/30]`バナーも「Turn 3」の1件のみで、単一プロセスの単一継続実行であることを確認した。`facilitation_count`は`state["facilitation_count"] += 1`（`facilitator_node`内、加算はここのみ）で単調増加し、コード全体でリセット箇所は初期state生成時（run開始時に1回）以外に存在しないことを`grep`で確認済み。一方、run終了時点の`checkpoint.json`は`facilitation_count=2, halt=False`であり、3回観測された「強制停止」が単調増加するカウンタの下では整合しない。原因の一部として、BL-132（`detector_node`の全履歴再出力バグ）により過去の「強制停止」決定が複数回にわたり**再表示**されていた可能性が高く、実際に何回の「本物のhalt」が発生したかはBL-132修正後の次回ドライランで再確認する必要がある。あわせて、`_load_checkpoint`で復元した直後に`state.get("halt")`をチェックせず外側`while`ループへ入っていた実装上の欠落（BL-121仮説(b)）を確認し、**部分修正（`done`）**: `--resume`直後、既にhalt済みのcheckpointを読み込んだ場合は即座に処理を停止するチェックを追加した。ただし本事象の主要因（3回に見えるhalt発生の正体）は未確定であり、BL-132適用後の次回ドライランでの再現確認が引き続き必要。**状態**: `open`（部分修正実施、根本原因の最終確認は次回ドライラン待ち）。 | P1 |
| BL-122 | 中 | `cela_main.py` (`_query_AI_live`の`for attempt in range(...)`リトライループ、BL-009/BL-046の再確認) | `log/2026-07-28/1420`・`2257`・`2026-07-29/0751`のいずれでも、APIエラー（レート制限・タイムアウト・不完全なレスポンス）発生時に「ツールループを最初からやり直します」というBL-009/BL-046の既知の粗いリトライ粒度（`loop_messages`/`python_calls_log`を破棄しiter=1へ巻き戻る）が高頻度で発生していることを再確認した。特にNVIDIA Nemotron 3 Ultra（free）を使用したドライランではリトライ発生回数がDeepSeek使用時より明らかに増えており（1420ログだけで6箇所以上）、モデル変更によってこの既知の設計上の粗さが顕在化しやすくなることが裏付けられた。ユーザー提案：エラーで打ち切られた際、iter=1からではなく直前のコンテキスト状態（`loop_messages`等）を保持したまま該当API呼び出しのみ再試行する設計に変更する。BL-046時点では「より大きめの変更のため見送り」と判断されていたが、モデル変更後の実害増加を踏まえ優先度を再評価する必要がある。**実装完了（`done`）**: `loop_messages`/`tool_calls_used`/`python_calls_log`/`reasoning_parts_all`の初期化と新規`iteration_start`変数を、外側の`for attempt`リトライループの外（関数冒頭）へ移動し、リトライをまたいで保持されるようにした。`for iteration in range(1, MAX_TOOL_ITER+1)`を`for iteration in range(iteration_start, MAX_TOOL_ITER+1)`に変更し、ループ本体の先頭で`iteration_start = iteration`を更新することで、APIエラーによる再試行時に同じiteration番号から再開し（1から再スタートせず、既に成功したiterationも重複実行しない）ようにした。`repl_session`の生成場所はBL-014の設計意図（ノード・リトライをまたいだ状態非共有）を尊重し変更していない。副次効果として、従来は1回のAPIエラーでiteration=1から際限なく再開できてしまい実質`MAX_TOOL_ITER=20`の上限が機能していなかったが、本修正により真の意味で20回の上限が機能するようになった（MAX_TOOL_ITERの値自体は変更なし）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`に新規`test_bl122_api_error_mid_loop_resumes_same_iteration_without_discarding_progress`を追加し、iteration 2の途中でAPIエラーを模擬し、リトライ後にiteration 1の進捗（think要約等）が失われずiteration 2から再開されることを検証。`python -m py_compile`合格、関連クラスタ98件Pass。 | P2 |
| BL-123 | 高 | `cela_main.py` (`call_detector`、`_build_escalation_pin_text`の呼び出し箇所) | ユーザー指摘、および2026-08-03の別AIコードレビューでも再指摘・検証済み。`_build_escalation_pin_text`（issue_logのescalated行を強制注入する、BL-103のpin機構）が`call_expert`/`generate_user_utterance`には注入されていたが`call_detector`には一度も呼ばれていなかった。**実装完了（`done`）**: `call_detector`の2パス構成（Pass 1: ドメイン妥当性レビュー、Pass 2: 数値監査）のうちPass 1にのみ注入（Pass 1の指摘は既存の`domain_findings_block`経由でPass 2へ伝播するため）。新規テスト`tests/test_bl123_detector_escalation_pin.py`（3件）追加。`python -m py_compile`合格、フルオフラインスイート600件Pass。 | P1 |
| BL-124 | 高 | `cela_main.py` (`generate_user_utterance`のツール群、BL-086 `escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`/`freeze_agreement`) | `log/2026-07-28/2257`を`grep`し確認。BL-086（R5）で実装済みの前提エスカレーション・Freeze・ゴール改定ツール群は、User AIに常時`tools attached`として提供されていた（65, 2556, 3680, 4549, 6212行目等）にもかかわらず、**実行ログ（`🔧 [User AI] freeze_agreement 実行`等）は本ドライラン全体で一度も出現しない**。User AIは「30分待ち時間制約 vs 冬季・通信障害・昼休みの例外」という、まさにこの機構が想定する前提矛盾に直面しながら、通常の`write_agreement`（条件付き承認）で済ませてしまい、Freezeによる恒久ピン留めを使わなかった。その結果、同じ論点がDetectorに繰り返し`major`判定され続け、最終的に`stagnant`→HALTに至った（`:21524`）。NVIDIA Nemotron 3 Ultra（free）はDeepSeekと比較し「この状況はエスカレーション経路を使うべきだ」という判断への誘導が効きにくい可能性があり、同一論点で`write_agreement`の条件付き承認がN回（例:2回）以上繰り返された場合に`freeze_agreement`/`revise_goal`の使用を強く促す誘導をプロンプトに追加することを検討する。**状態**: `open`（プロンプト誘導強化要、記録のみ）。 | P1 |
| BL-125 | 中 | `cela_main.py`（`_resolve_task_transition`、`_get_blocking_issues_for_transition`） | ユーザー質問「issue未解決であればフェーズを超えられない仕組みは実装済みか」を受けて確認した際は`open`（記録のみ）だったが、BL-134の実インシデント分析を受け実装完了（`done`）。`_resolve_task_transition`（BL-024の唯一の書き手）の`task_id`遷移直前に、離脱しようとしているtaskの`last_seen_task_id`に紐づくseverity='major'（=status='escalated'）かつ未先送り（`defer_to_task_id`未設定）のissue_log行を`_get_blocking_issues_for_transition`で問い合わせ、存在すれば遷移を拒否し`state["task_transition_blocked_issue_topics"]`へ記録、次のUser AIターンへ一度だけ理由を通知する（BL-136のDEFERで明示的に先送り済みのものはブロック対象外＝スケジュール調整を許容）。新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`含め関連クラスタ542件Pass。 | P2 |
| BL-126 | 中 | `cela_main.py` (`facilitator_node`、BL-086 `revise_goal`、`task_planner_node`の再分解能力) | ユーザー発案。現行のBL-086はExpertが個別タスク遂行中に前提矛盾に気づいた場合のみ発火するリアクティブな経路に限定されており、Facilitator/User AIがゴール・制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計だった。**実装完了（`done`）**: Stage A（`goal_drafts`バージョニング）、Stage B（Detector `review_mode="goal_change"`）、Stage C（Task Plannerのラン途中再構成・supersede機構）、Stage D（Facilitatorのツールループ化・`EssenceProposal`・Essence Dialogueループ・Reflection迎合監査）を全て実装。新規テスト29件含め関連クラスタ512件Pass。 | P2 |
| BL-127 | 高 | `cela_main.py` (`write_agreement`のUPDATE適用経路、ホワイトボード本文への反映) | `log/2026-07-28/1233`のDetector再検証で発見。需要試算の計算ミス（1月係数の適用漏れにより140人/日/−65%と誤記載、正しくは105人/日/−74%）についてExpertが`write_agreement`で`UPDATE`（`AG-1785214808321`）を実行し「修正が正常に適用されたことを確認しました」と自己申告したが、Detectorが再検証したところホワイトボード本文には旧値「約140人」「−65%」が3箇所とも**残存**していた。write_agreementがDB上はUPDATE成功と記録されるにもかかわらず、成果物本体（ホワイトボード）に反映されない、または反映確認に失敗するケースが実際に発生している。ログはDetectorが不整合に気づき再調査を始めた直後に途切れており、最終的にこの不整合が解消されたか未確認。原因を特定したところ、`_commit_agreement_from_tool`のUPDATE分岐に、entry_type="Deliverable"かつedits未指定・decision_whatが200字以下の短文の場合にホワイトボード本体を意図的に上書きしない「保護」ブランチ（H2踏襲、承認コメント等と誤って全文を上書きしないための仕様）が存在するが、従来は`print()`のみでツール呼び出し元（Expert）へは一切伝わらず、実際に反映された他のUPDATEと同一の`{"success": True}`が返っていたことが判明。**実装完了（`done`）**: `_commit_agreement_from_tool`の戻り値を`str \| None`（error）から`tuple[str \| None, str \| None]`（error, protected_warning）へ拡張し、保護ブランチ発動時は具体的な理由を`protected_warning`に設定。`_write_agreement_impl`はこれを`{"success": True, ..., "warning": "..."}`としてツール応答に含め、Expert/User AIが次のターンで気づけるようにした。新規テスト`tests/test_bl127_whiteboard_update_protected_warning.py`（6件）、既存の直接呼び出しテスト3ファイル（BL-073/080/084）をタプル戻り値のアンパックに合わせて修正。`python -m py_compile`合格、フルオフラインスイート550件Pass。 | P1 |
| BL-128 | 低 | `cela_main.py` (Detectorの独立検算プロンプト、`call_detector`) | `log/2026-07-28/1420`のレビューで発見。「独立検算：システム構築費1,800万円…数値矛盾・計算ミスなし」というほぼ一言一句同一の検算コメントが5659/5673/5705/6524/8375/8856行目等、複数ターンにわたり繰り返し出現している。真に毎回独立して再計算した結果が偶然一致しているのか、過去の検算結果をテンプレ的に使い回しているのかがログからは判別できず、Detectorレビューの「独立性」が実質的に薄れているリスクがある。python_repl呼び出し自体のコード内容をターンごとに突き合わせ、同一コードの使い回しがないか機械的に検知する仕組みを検討する。**状態**: `open`（記録のみ、優先度低）。 | P3 |
| BL-129 | 低 | `cela_main.py`（長時間ドライランの安定性、プロセス終了経路全般） | `log/2026-07-28/1233`・`1420`・`2026-07-31/1129`で、ログがturn上限到達や明示的なHALT/完了メッセージなしに、あるノードの思考・ツール呼び出しの途中で唐突に途切れて終了している。プロセスのクラッシュ・OSレベルのタイムアウト・ログ書き込みの停止のいずれが原因か切り分けができていなかったが、2026-07-31にユーザーから「間違ってノートパソコンを休止状態にしたりしてしまったため」との説明があり、少なくとも大半は環境要因（意図しないPCの休止状態移行）が原因と判明。**状態**: `open`（環境要因と判明したため優先度を下げ記録のみ。休止状態と無関係な中断が再発した場合のみコード側の原因切り分けに着手）。 | P3 |
| BL-130 | 中 | `cela_main.py`（`ask_user_question`ツール新設、`expert_node`/`detector_node`/`route_after_expert_detector`/`generate_user_utterance`(_node)のモード分岐） | `log/2026-07-29/1322`レビューでのユーザー発案。現行の構造はUser AI→Expertへの指示（Detectorのレビューは挟む）にほぼ限定されており、Expert側から成果物を出さずに質問・相談できる循環が存在しない。**実装完了（`done`）**: `ASK_USER_QUESTION_TOOL`（expertのみ許可）を新設し、呼ばれると`expert_consultation_mode`/`expert_pending_question`を`expert_node`がstateへ反映。`detector_node`は当該ターンでLLM監査自体をスキップする軽量パスを取り、`route_after_expert_detector`は`expert_decision_extractor`を経由せず`generate_user_utterance`へ直行。`generate_user_utterance`が質問をUser AIへ明示提示する固定文面へ切り替え、回答生成直後にフラグを消費・リセット。新規テスト15件含め関連クラスタ256件Pass。 | P2 |
| BL-131 | 中 | `cela_main.py`（`write_agreement`のtask_id検証、task_planner計画との整合、TOOL_DISPATCHのstate受け渡し） | `log/2026-07-29/1322`レビューで発見。Facilitatorが提案した「制約見直し要求書」を`task_1_1_review`という**task_plannerの正式なフェーズ・タスク計画に存在しないtask_id**でExpertが実行し、244行・6バージョンの成果物を作成してしまった。`write_agreement`/ホワイトボード作成時にtask_idが実在の計画（`state["phases"]`）と照合されず、任意の文字列で成果物が作れてしまう。**実装完了（`done`）**: 前提としてTOOL_DISPATCHの全ハンドラをstate受け渡し可能な`(args, state)`形式へ統一（`_CURRENT_RUN_ID`等のグローバル依存を緩和、BL-099の一部解消）。その上で`_write_agreement_impl`にtask_id/phase_id実在チェック（`pending_task_ids`許可リスト込み）・`get_latest_whiteboard`/`get_latest_plan_draft`のtask_id単独検索化（誤ったphase_idでバージョンが1から再スタートする事故の修正）・`target_topic`必須化を実装。新規テスト9件含め関連クラスタ166件Pass。 | P2 |
| BL-132 | 高 | `cela_main.py`（`detector_node`、6972行目付近） | BL-121（`log/2026-07-29/0751`の「halt後も処理が継続しているように見える」問題）の再調査中に発見。`detector_node`（`user_detector`/`expert_detector`の両方が指す共通関数）の末尾で`this_turn_decisions = get_decisions_from_db(_conn, state["run_id"])[1:]`としてrun開始2件目以降の**全決定履歴**を毎回丸ごと再取得し、detector_nodeが呼ばれるたび（1run中に非常に高頻度で発生）に全件を再出力していた。変数名は「this_turn」（このターンの）だが実際には「run全体、最初の1件を除く全部」であり、ターン単位のスコープ管理が一切されていなかった。これにより(1)ログが実行が進むほどO(n^2)的に肥大化する、(2)過去のあらゆる決定（BL-121で観測された「強制停止」を含む）がdetector呼び出しのたびに再表示され続け、実際に何回・いつ発生した事象なのかがログから判別できなくなる、という実害が生じていた。BL-128（同一検算コメントが複数回出現）も同一バグが主因である可能性が高い。**実装完了（`done`）**: 全履歴の再取得・再出力をやめ、この関数呼び出し自体が直前に作成した`decision`（1件のみ）を出力するよう変更。`python -m py_compile`合格、関連クラスタ132件Pass。実LLM再ドライランでのログ肥大化解消・BL-121原因切り分けの効果確認は次回待ち。 | P1 |
| BL-133 | 高 | `cela_main.py`（`call_detector`のドメイン妥当性レビュー第1段、`_query_and_parse_with_retry`／`_safe_json_parse`） | `tests/test_f26_detection.py::test_detector_no_false_positive_within_cap`（B.5.1非退行、D-011）が2026-07-30に3/3全試行で`major`となり失敗（1回目は2026-07-28に単発flakyとして観測、当時は「モデル判定のばらつき」と判断していた）。今回、テスト出力の`comment`フィールドを実際に確認したところ、**モデルが誤った判定を下したのではなく**、`comment='(ドメイン妥当性レビューのJSON解析失敗のためフェイルクローズしました)'`——すなわち第1段（ドメイン妥当性レビュー）が層2リトライ（`_query_and_parse_with_retry`、`max_retries=2`＝計3試行）を使い切ってJSONを一切パースできず、D-005の設計通りフェイルクローズ（major）していたことが判明した。これはBL-012/D-011が想定していた「モデルの誤判定」とは別種の失敗モードであり、2026-07-28の1回目もおそらく同一の парース失敗だった可能性が高い（当時は`comment`を確認せず「ばらつき」と誤って結論づけていた）。フェイルクローズ自体（D-005の安全側原則）は変更すべきではないが、**なぜ層2リトライ3試行が全て失敗したのか**（モデルがJSONを一切出力しなかったのか、ツールループがMAX_TOOL_ITERまで消費され最終テキストが空だったのか、単なるAPI側の一時的不調か）が未診断のまま。**対応（今回実施）**: `_query_and_parse_with_retry`のパース失敗時ログに生レスポンス冒頭300字のプレビューを追加し（従来は失敗した事実のみで内容不明だった）、次回の再現時に原因を機械的に切り分けられるようにした（`python -m py_compile`合格、`tests/test_bl089_json_fence_and_failclosed_review.py`10件Pass、ロジック変更なしのため既存挙動に影響なし）。**状態**: `open`（診断ログ追加のみ完了。次回この非退行テストが再びmajorになった際、追加したプレビューログから真因を特定し、必要ならプロンプト調整・リトライ回数見直し等の恒久対応を行う）。 |
| BL-134 | 高 | `cela_main.py`（`call_expert`のExpertプロンプト、issue_logのエスカレーション解決フロー、`generate_user_utterance`のUser AI承認ロジック） | `log/2026-07-30/1236`（BL-126以降初のドライラン）レビューでユーザーが発見。ゴール文は遠隔監視オペレーターについて「最低2名常駐」としか要求しておらず、運行時間帯（8:00〜20:00の12時間、`operating_hours_start`/`operating_hours_end`として制約テーブルにも明記済み、20:00〜翌8:00は「運行外」と明言）を超えて24時間365日の監視が必要だとは一切書いていない。にもかかわらずExpertは「常時2名常駐」を無根拠に「24時間365日」体制と解釈し、`remote_operator_min_count_legal`（法的最低要員数10〜11名）を`confidence="confirmed"`として確定させ、年間人件費6,188〜9,281万円という「致命的な予算超過」の結論の土台に使っていた。Detector自身がこの疑義を実際に検知していた（issue `detector_observation_no_task`, severity=`major`, status=`escalated`: 「『常時2名常駐』を24h365日で試算（10名必要）しているが、運行時間は8-20時の12hのみ。『常駐』の解釈が曖昧で、実態に合ったシフト設計なら要員半減の可能性。」）にもかかわらず、このissueは`resolved_by`/`resolved_at`が空のまま未解決で、User AIはtask_1_1を承認しtask_1_2へ進行させてしまっていた。F-2.6/BL-033が防ごうとしている「根拠不明な前提を確定値として扱う」パターンが、監査（Detector）で検知はされたのに是正フロー（issue解決・再検討）に乗らずすり抜けかけた実例。**状態**: `done`。対応候補: (a) Expertが運行時間外の要件を確定値として一般化・拡大解釈する際に、その拡大解釈の根拠をゴール文中に明示的に求める罠注記を`call_expert`/`generate_user_utterance`へ追加→**実装完了（D-110）**。(b) severity=majorでescalatedされたissueが未解決のまま該当タスクが完了・次タスクへ進行することを防ぐゲート→**BL-125として実装完了**。(c) Detectorが疑義に気づきながらconstraint_issue判定に反映しない点の見直し→**調査の結果、意図的な誤検知抑制設計（BL-012/BL-133と表裏一体）と判明し変更不要と判断（D-110）**。 | P1 |
| BL-135 | 低 | `cela_main.py`（`ASK_USER_QUESTION_TOOL`のパラメータ定義、`generate_user_utterance`のBL-130相談応答モード分岐） | ユーザー依頼によるBL-086/BL-130新規ツール群のプロンプト・オリエンテーション品質レビューで発見、2026-08-03の別AIコードレビューで再確認。`ASK_USER_QUESTION_TOOL`の`required`パラメータ`blocking_reason`が`generate_user_utterance`のBL-130相談応答モード文面に埋め込まれておらず、User AIは質問文だけを見せられブロッキング理由を判断できなかった。**実装完了（`done`）**: `LineageState`へ`expert_blocking_reason: str`を追加、`expert_node`が`get_last_ask_user_question()`の戻り値から反映、`generate_user_utterance_node`で`expert_pending_question`と同じタイミングでリセット、`generate_user_utterance`のBL-130相談応答モードのプロンプトへ質問文の直後に理由を追記。新規/拡張テスト計5件（`tests/test_bl130_ask_user_question.py`）追加。`python -m py_compile`合格、フルオフラインスイート600件Pass。 | P3 |
| BL-136 | 高 | `cela_main.py`（`write_issue`/`_write_issue_impl`のDEFER拡張、`_get_open_issues`/`_build_open_issue_pin_text`、`_get_forced_escalated_issues_text`、`_resolve_task_transition`／`_get_blocking_issues_for_transition`） | ユーザー指摘「issueが活発に使われなくなった、たまたまか？」を受けて調査。`log/2026-07-30/1236`の実DBでissue_logを確認したところ7件中0件が`resolved`で、原因は(1)`status='escalated'`行のみ毎ターン自動表示されopen（minor）行は不可視、(2)BL-086の前提エスカレーション（`_get_open_escalations_text`、「今回の発言内で必ず解決してください」）と異なりissue_logのRESOLVE指示に強制力がない、という2点の非対称性と判明。あわせてBL-134の実インシデントを再検証し、24h/365d問題の一部（遠隔監視オペレーターのシフト）が依然`confirmed`のまま未是正であること、および「Detectorがmajor判定した」という当初の説明が不正確で、実際は`raised_by='detector_auto'`の汎用バケツ行が再発回数（occurrence_count>=2）により機械的にescalated化したものと、`raised_by='user'`が最初からmajor指定でCREATEしたものの2種が混在していたことも判明（後者はD-079/D-080の意図通りの機械的昇格設計であることをユーザーに確認済み）。**実装完了（`done`）**: (A) `_get_open_issues`/`_build_open_issue_pin_text`を新設し、status='open'行も`call_expert`/`generate_user_utterance`へ毎ターン参考情報として可視化。(B) `write_issue`に`action_type="DEFER"`を追加（userロールのみ許可、`defer_to_task_id`必須・実在チェック付き、BL-082の`_append_deferred_note_to_plan`を再利用して対象taskの計画文書へも申し送り、`issue_log`に`defer_to_task_id`列を新設）。(C) `_get_forced_escalated_issues_text`を新設し、BL-086と同型の「今回の発言内で必ずRESOLVEかDEFERを呼んでください」という強制文言を`generate_user_utterance`へ注入（既存の受動的pinとは別に追加、DEFER済みのものは対象外）。(D) BL-125として`_get_blocking_issues_for_transition`と`_resolve_task_transition`のゲートを実装（詳細はBL-125参照）。新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`（28件、BL-134実インシデント再現含む）含め関連クラスタ・フルオフラインスイート542件Pass。 | P1 |
| BL-137 | 高 | `cela_main.py`（`_apply_text_edits`、`_revise_goal_tool_impl`/`write_agreement`双方の共通経路） | 実際のドライラン実行中に`AttributeError: 'str' object has no attribute 'get'`（`_apply_text_edits`内、`e.get("old_text", "")`）で`run_ai_vs_ai_loop`全体が未捕捉クラッシュ。User AIが`revise_goal`ツールの`edits`パラメータに、`{old_text, new_text}`形式の辞書ではなく生文字列を含む配列を渡したことが原因（LLMがツールスキーマ通りの形式で出力しなかった）。`_apply_text_edits`は`write_agreement`のDeliverable/Decision UPDATE経路とも共有されている関数のため、同種の入力があれば同じ経路でクラッシュしうる。**実装完了（`done`）**: `_apply_text_edits`のループ先頭に`isinstance(e, dict)`チェックを追加し、非dict要素があれば例外を送出する代わりに`edits[{i}]: ...型の値が渡されました`という具体的なエラー文字列を返すようにした（既存のold_text空文字チェックと同じフェイルクローズ・自己修正可能パターン）。回帰テスト2件（`tests/test_r4_smoke.py`）を追加。`python -m py_compile`合格、フルオフラインスイート544件Pass。 | P1 |
| BL-138 | 低 | `docs/design/back_log/issue_backlog.md`（構想記録のみ、コード対象なし） | Sakana AIの仕組みとの雑談を発端に、ユーザーが「CELAに自らのLangGraph構造を継続改良させ、改良されたCELAが次世代のCELAをさらに改良する」再帰的自己改変構想を提起。AIが「評価基準自体のドリフト」という本質的リスクを指摘したところ、ユーザーが「これは仮定ではなく、AIが捏造・確定値化した数字が後続議論に連鎖的影響（バタフライ効果）を与えている今まさに起きていることだ」とBL-134等の実例を引いて応答。「改変ループの外側に固定監査層が必要」という設計原則を、思いつきレベルの構想ながら将来のアーキテクチャ自己改変着手時に必ず踏まえるべき制約として記録。**状態**: `open`（設計相談中、実装は未着手）。decision_lineage.md論点89に議論経緯を記録。 | P3 |
| BL-140 | 中 | `cela_main.py`（`THINK_TOOL`の`issues`パラメータ→`scratch_concerns`へ改名、`_think_handler`） | `log/2026-07-31/1129`レビュー中、ユーザーから「issueが使われない件、もしかしてthinkの方に取られている？thinkに書けば永遠に残ると勘違いしている？」との仮説提起。`THINK_TOOL`のパラメータ定義を確認したところ、まさに`issues`という名前のフィールドが存在し、ツール全体の説明文にも「nothing is summarized away or aged out」という永続性を示唆する文言があった。しかし実装（`_think_handler`）は、この`issues`をモジュールレベルのグローバル変数へ一時保存するだけで**DBには一切書き込まれず**、`_reset_think_scratchpad()`が各ノード呼び出し（＝1ターン）の開始時に必ず空にするため、**そのツールループが終わった瞬間に完全に消える**ことが判明。実際、`log/2026-07-31/1129`の4550行目でDetectorが`think(issues=[...])`へ5件の懸念（予備車なし・オペレーター兼務・フォールバック地点未特定等）を記録しており、`write_issue`（DBへ永続化されターンをまたいで見える）との名前の類似が、モデルが懸念を書いて満足し永続化を怠る誤解を誘発している可能性が高いと判断。**実装完了（`done`）**: `THINK_TOOL`の`issues`パラメータを`scratch_concerns`へ改名し、descriptionに「これは`write_issue`のissue_logとは別物で、このツール呼び出しループが終わると消える一時メモです。ターンをまたいで残したい懸念は`write_issue`を使ってください」と明記。対応するグローバル変数`_THINK_ISSUES`→`_THINK_SCRATCH_CONCERNS`、返り値キー`current_issues`→`current_scratch_concerns`も同期改名。加えてユーザー指摘「各ノードのプロンプトでのツール説明では？」を受け、`write_issue`と`think`が同一ターンで併記される`call_detector`（`_issue_carryover_prefix`）・`generate_user_utterance`のシステムプロンプト本文にも同趣旨の注記を追加。新規テスト3件追加、既存テスト2件をキー名変更に追随。`python -m py_compile`合格、フルオフラインスイート560件Pass。 | P2 |
| BL-142 | 高 | `cela_main.py`（`generate_user_utterance`のmajor判定時プロンプト） | `log/2026-08-01/2329`レビューで発見。task_1_1がVer.1〜21まで改訂され続け最終的に`stagnant`判定でHALTした原因を調査したところ、ドメイン上の欠陥（M-07の人件費倍率が「2.5倍」と「3倍」で矛盾したまま残存、違法シフト前提のOPEX数値が未修正）に加え、構造的な増幅要因が判明した：Userの「承認・次タスクへ移行」発言が`user_detector`にmajor判定されると`route_after_user_detector`がExpertではなくUser AI自身（`generate_user_utterance`）へ差し戻す設計のため、19399〜19480行では実質同じ承認文をUserが5ラウンド言い換えるだけで空回りし、その間ホワイトボードの数値矛盾には一切手が入らなかった。ユーザーが「ユーザーの承認系の発言の監査は、間違っている部分を指摘しつつ、承認を取り消し、エキスパートに訂正させるよう促すような言葉を発信するようにプロンプトで強くガイドラインしてあげなければならない」と整理。既存のmajor判定時プロンプト（`⚠️【重要】`ブロック）には「エージェントAIに正しい方向への修正を厳しく要求してください」という指示はあったが、「却下された発話が承認だった場合は明示的に撤回せよ」という具体的な指示が欠けていた。**実装完了（`done`）**: 同ブロックへ、却下された前回発話が「承認」「次タスクへの移行」だった場合はwrite_agreement(status="Rejected")で明確に撤回し、Agent AIへ成果物のどこをどう直すべきか具体的な修正指示を出すことを求める一文を追加（言い回しを変えただけの同じ承認の繰り返しを明示的に禁止）。新規テスト`tests/test_bl142_user_approval_retraction_guidance.py`（2件）追加。`python -m py_compile`合格。次回ドライランで実際にUser AIが承認撤回→Expert差し戻しの動作をとるようになるかは要観察（プロンプト強化のみで、モデルの行動が必ず変わる保証はない）。 | P1 |
| BL-144 | 高 | `cela_main.py`（`reflection_node`のBL-096機械的stagnant上書き条件） | `log/2026-08-02/0832`レビューをAgentへ委託した際、reflectionの1回目のサイクル（escalated issue 4件時点）でreflection自身のLLM判定は明確に`"continuing"`（計算誤り・法令違反が順次是正され建設的な議論が進行中、と自ら理由づけ）だったにもかかわらず、BL-096の機械的上書き（escalated行が1件でもあれば無条件でstagnant化）によりfacilitation_countの貴重な猶予（既定3回）を1つ消費していたことが判明。最終（4回目）サイクルはreflection自身も独立にstagnantと判断しており（データ捏造・自己矛盾・Expertの空応答という実質的根拠）そちらのHALTは正当だったが、そこに至る過程で健全な進捗中の回を誤ってカウント消費していた。ユーザーへ「BL-096の上書き条件を、単なる存在チェックから『同じescalated issueが複数サイクルにわたって進展していない場合のみ』へ絞る」提案をしたところユーザーが同意し、具体的な閾値として「ユーザーノードを3回通過する」を提示。**実装完了（`done`）**: 新規state`escalated_issue_first_seen_round: dict[str, int]`（issue_log行id→初めてescalated状態で観測した`round_count`）を追加。`reflection_node`はescalated行ごとに初観測roundを記録し、現在の`round_count`との差が3以上の行（＝ユーザーノードを3回通過しても未解決）が1件でもあればstagnantへ上書きする。解決・先送り済みで一覧から消えたissueは追跡からも削除（再度escalatedになれば新規の滞留として扱う）。新規テスト`tests/test_bl144_escalated_issue_staleness_threshold.py`（4件: 初観測時は上書きしないこと、3ラウンド滞留で上書きされること、解決時に追跡がクリアされること、複数issueのうち1件でも滞留していれば発火すること）追加。`python -m py_compile`合格、フルオフラインスイート578件Pass。`write_issue`のRESOLVE/DEFERが依然ほぼ呼ばれない現状では、閾値を上げても根本解決にはならず、issueの実際の解決を促す仕組み（BL-136の強制プロンプト等）との併用が前提である点に留意。 | P1 |
| BL-143 | 中 | `cela_main.py`（`_build_retry_situation_label`新設、`call_expert`/`generate_user_utterance`の差し戻しプロンプト） | ユーザーから「各ノードが今の状況とやるべきことの整理をもっとよりよくできる仕組みはないか」との相談を受け設計を検討。ユーザーの「いま現在はDetectorの指摘文だけのっているんでしたっけ？」という確認質問に対しコードを調査したところ、User AI側（`generate_user_utterance`）・Expert側（`call_expert`）双方の差し戻しプロンプトとも、実際に載っているのは`constraint_issue_log[-1:]`（Detectorの直近1件の判定を生のPython辞書reprでそのまま貼り付けたもの）のみで、「これが何回目の差し戻しか」（`user_retry_count`/`expert_retry_count`はルーティング判定にのみ使われプロンプトには一切出ていなかった）・「前回と同じ指摘が繰り返されているか」という、Python側で既に計算可能なのに渡っていない情報が欠けていたことが判明。BL-142で見た「Userが気づかず同じ承認を繰り返す」空回りも、この現在地情報の欠如が一因と考えられる。**実装完了（`done`）**: 新規ヘルパー`_build_retry_situation_label(state, retry_count, max_retries=3)`を新設。「これはこの論点に対するN回目の差し戻しです（あとM回で強制的にレビューへ回されます）」という一行に加え、`retry_count>=2`（同一の差し戻し連鎖内に比較対象が確実に存在する場合のみ）で`constraint_issue_log`の直近2件のcommentを`difflib.SequenceMatcher`で比較し、類似度0.6以上なら「前回の指摘とほぼ同じ内容が繰り返されています」という警告を追加する。`call_expert`・`generate_user_utterance`双方の差し戻しプロンプト冒頭へ注入。新規テスト`tests/test_bl143_retry_situation_label.py`（8件: 回数・残り回数表示、上限到達表示、初回差し戻し時は連鎖外との誤比較をしないこと、繰り返し検知・非検知、空ログ、両ノードへの配線確認）追加。`python -m py_compile`合格、フルオフラインスイート574件Pass。 | P2 |
| BL-141 | - | `cela_main.py`（`expert_node`のchat_history追記ロジック） | **誤診断のため`invalid`化**。当初、ユーザーの指摘「detectorとエキスパートの差戻しループは見せずにuser->エキスパートの履歴だけに整理できませんか」を受け、`expert_node`が差し戻しのたびに新規`assistant`メッセージを無条件で`chat_history`へ追記しておりウィンドウが埋まる、と診断し修正を実装したが、これは`expert_node`関数の一部（末尾の追記部分）しか確認せずに出した誤った結論だった。実際には`expert_node`冒頭（`cela_main.py`、call_expert呼び出し直前）に、このセッション開始前から既に存在するコード「`if state.get("constraint_issue") in ("major"): 直前のchat_history末尾がassistantならpopしてから`call_expert`を呼ぶ」という機構があり、差し戻し再提出のたびに「pop 1件→append 1件」でchat_historyの長さは既に一定に保たれていた（Userサイド`generate_user_utterance_node`にも同型の既存popロジックあり）。つまり報告された問題は実在しなかった。**対応**: 誤って追加した重複コード（末尾の「直前がassistantなら上書き」処理）を削除し、既存の冒頭pop機構のみに戻した。誤診断に基づくテスト`tests/test_bl141_expert_retry_chat_history_collapse.py`は、既存の冒頭pop機構を正しく検証する内容に全面差し替え。D-113・decision_lineage論点94も本訂正を反映して更新。**教訓**: 関数の一部だけを読んで「無条件追記」と断定せず、関数全体（特に冒頭のガード節）を確認してから診断すべきだった。 | - |
| BL-139 | 高 | `cela_main.py`（`decision_extractor_node`、`call_decision_extractor`のtransition抽出） | `log/2026-07-31/0908`レビューで発見。`checkpoint.json`の最終状態が`current_task_id: "task_1_2"`のままなのに、対話ログでは同日15:04:19時点で既にtask_1_2が承認されtask_2_1着手指示が明示的に記録され（decision_extractor No.61/62）、以降数百ターン・`whiteboards/`に`phase_2_task_2_1_V12〜V14`まで実際に書き込まれていた。原因を追ったところ、`_resolve_task_transition`は`call_decision_extractor`の単一LLM呼び出しが返す巨大なJSON内の一項目`advances_to_task_id`にのみ依存しており、このターンではUserの発言に「次タスクtask_2_1への着手指示」が明示されextracted_events自体にはtask_2_1向けのDirective（CREATE）が正しく含まれていたにもかかわらず、トップレベルの`advances_to_task_id`だけがnullのまま返っていた（`_resolve_task_transition`の遷移完了・拒否いずれの`print`ログも当該run全体で一件も出現せず、遷移処理自体が一度も成立していなかったことを確認）。結果、`current_task_id`依存の全機構（BL-023のacceptance_criteriaチェック等）が誤ったタスクの基準を参照し続けていた。**実装完了（`done`）**: `decision_extractor_node`内で、抽出済み`extracted_events`の中に現在タスクと異なる有効な`task_id`を持つDirective（`status="Deferred"`のBL-082明示的先送りは除外）があれば、`transition`の代替シグナルとして採用してから`_resolve_task_transition`へ渡すフォールバックを追加（BL-096の自動起票と同型の安全網）。対象はUser側の抽出（`target_role="user"`）のみ（Expertはタスク遷移を決定する権限を持たないため）。新規テスト`tests/test_bl139_transition_fallback_from_directive.py`（4件）追加、フルオフラインスイート557件Pass。 | P1 |
| BL-145 | 高 | `cela_main.py`（`reflection_node`、`task_planner_node`、新規`_mark_issue_planned`/`_get_planned_issues`/`_build_planned_issue_pin_text`、`facilitator_node`） | `log/2026-08-02/0832`のOrchestrator関連バグ調査と合わせて、ユーザーから「majorとなったissueや後続タスクへの申し送りは、Detector/Reflectorの正当性監査後、タスクプランナー経由で明示的にタスク化した方がissue消化がスムーズになるのでは」との設計提案。`log/2026-08-03/1347`ドライランで、まさにこの種の未解決issueがBL-125のタスク遷移ゲートを塞ぎ続けSUPERSEDE迂回（BL-152の引き金）を招く実例を確認し着手。**実装完了（`done`）**：`reflection_node`がBL-144の滞留検知（同一escalated issueが3ラウンド未解決）を使い、既にDEFER済みでないstale issueを`plan_revision_reason`/新規`plan_revision_issue_ids`経由で`task_planner_node`へ引き継ぐ。`task_planner_node`は計画再構成成功後、対象issueを新ステータス`planned`（`resolved`ではない）へ遷移させ、埋め込み先task_idを既存の`defer_to_task_id`列に記録する（ユーザー指摘により、当初案の即時`resolved`化から変更：「計画に組み込まれた」だけでは「本当に解決した」ことにはならず、真の解決はuser roleの既存`write_issue(RESOLVE)`に委ねる）。`planned`後もDEFER・CREATE再発検知が既存機構のままコード変更なしで機能する設計。非強制の可視化ブロックを`generate_user_utterance`へ追加。基本設計: [BL145_basic_design.md](BL-145/BL145_basic_design.md)。新規テスト`tests/test_bl145_issue_driven_plan_formalization.py`（16件）追加。`python -m py_compile`合格、フルオフラインスイート623件Pass。差分編集API（1タスク単位の追加・削除・修正プリミティブ）は本BLの範囲外とし将来BLへ切り出し。 | P1 |
| BL-146 | 高 | `cela_main.py`（`_write_agreement_impl`/`_commit_agreement_from_tool`、新規`_effective_current_task_id_from`、`TOOL_DISPATCH["write_agreement"]`） | `log/2026-08-02/0832`ドライランのOrchestrator関連バグ調査で発見。`write_agreement`はtask_idがtask_plannerの正式計画に実在するか（BL-131）しか検証しておらず、`state["current_task_id"]`（BL-125がタスク遷移をブロックしている対象そのもの）とは一切照合していなかった。そのためBL-125がタスク遷移をブロックしていても、Expert等は`task_id`引数に任意の他タスクを指定するだけで実際にDeliverableを書き込めてしまい（SUPERSEDEを除く）、Detectorがそれを正式な成果物としてレビューしてしまう実害を確認した。**実装完了（`done`）**: 新規ヘルパー`_effective_current_task_id_from(state)`（`_get_current_task`と同じcurrent_phase先頭タスクへのフォールバックを再利用、current_task_idが初回タスク進行中は空文字のままである問題に対応）を追加。`_write_agreement_impl`のBL-131実在チェック直後に、`action_type != "SUPERSEDE"`かつtask_idが実効上のcurrent_task_idと一致しない場合は拒否するチェックを追加（SUPERSEDEは他タスクの正規の改訂経路として対象外）。新規テスト`tests/test_bl146_write_agreement_current_task_gate.py`（6件）追加、既存`tests/test_bl131_write_agreement_task_id_validation.py`は無修正でPass。`python -m py_compile`合格、フルオフラインスイート596件Pass。 | P1 |
| BL-147 | 中 | `cela_main.py`（`_read_deliverable_file_handler`、`TOOL_DISPATCH["read_deliverable_file"]`） | BL-146と同じ調査で発見。`read_deliverable_file`は`write_agreement`（BL-131）と異なりtask_idの実在チェックを一切行っておらず、存在しないtask_idでも素通りしていた。特にtask_idとfile_pathを同時指定した場合、task_idの実在チェックが一切行われないままfile_path側の読み込みに進んでしまい、「存在しないtask_idを指定しつつfile_pathで読み込みを通過させる」抜け道になっていた。**実装完了（`done`）**: `_read_deliverable_file_handler`に`state`引数を追加し`TOOL_DISPATCH`から実際に渡すようにした上で、task_id指定時はfile_path分岐より先に`_find_task_by_id`/`pending_task_ids`による実在チェック（BL-131と同型）を行うようにした。実在する他タスクの成果物への参照読み（本来の目的）は制限しない。新規テスト`tests/test_bl147_read_deliverable_file_task_id_validation.py`（6件）追加。既存`tests/test_r3_smoke.py::test_bl040_read_deliverable_file_lookup_by_task_id`が、state省略（引数なし呼び出し）と存在しないtask_idの期待値（`not_found`→`error`）の2点で新チェックと衝突し失敗したため、`state`を明示的に渡す形へ更新（実行時のTOOL_DISPATCH呼び出しは全て`query_AI`のツールループ経由でstateが渡るため、この更新は実際の動作パターンとの整合を取るもの）。`python -m py_compile`合格、フルオフラインスイート596件Pass。 | P2 |
| BL-148 | 高 | `cela_main.py`（`call_orchestrator`、`_build_task_scope_context`/`_build_project_plan_toc`の再利用） | BL-146と同じ調査で発見。Orchestrator（`call_orchestrator`）はツールを一切持たない単発JSON応答で、プロンプトに`current_task_id`・タスク計画・issue状況が一切含まれていなかった。専門家選定はUser AI/Expert AIの対話の生テキストのみに基づいて行われるため、対話がBL-125でブロックされているタスクとは別のタスクへ漂うと、`current_task_id`がまだ元のタスクにピンされていても専門家選定がそちらへ引っ張られる実害が`log/2026-08-02/0832`で確認された（Detector自身が「プロンプトのバグだと思う」と自己申告するほどの構造的な矛盾）。ユーザーからも「Orchestratorのツールは必要な情報が見れるツールが渡されていますか？Orchestratorもツールループ化が必要です」との明示的な指示。**実装完了（`done`）**: `call_orchestrator`のプロンプトへ`_build_task_scope_context`（current_task_json/未充足の要求項目）・`_build_project_plan_toc`（計画目次）による現在タスクの構造化情報を追加。`query_AI`呼び出しを単発JSON応答からツールループ（`tools=[READ_PROJECT_PLAN_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_VERIFIED_FACT_TOOL, THINK_TOOL], state=state`）へ変更。Orchestratorの役割は専門家選定メタデータの生成のみで状態を変更しないため、書き込み系ツール（write_agreement等）は意図的に付与しない（`_check_write_permission`のロール表にも`"orchestrator"`は存在しない）。BL-109（単発判定ノードのtools=None化）の対象一覧から`call_orchestrator`を除外し、BL-126 Stage D（`call_facilitator`の同型の差し戻し）と同じ理由づけとした。既存`tests/test_bl093_think_tool_scratchpad.py::test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`を更新（対象リストから`call_orchestrator`を除去）、新規`test_bl148_call_orchestrator_is_tool_loop_capable`・`_NODE_TOOL_NAME_REMINDERS`エントリ・`tests/test_bl148_orchestrator_tool_loop.py`（4件）を追加。`orchestrator_node`自体は無変更（既存の入出力契約を維持）。`python -m py_compile`合格、フルオフラインスイート596件Pass。 | P1 |
| BL-149 | 低 | `cela_main.py`（`_safe_json_parse`のフォールバック戦略ロギング不足） | コードベース全体のバグチェック（2026-08-03）で発見。`_safe_json_parse`（complexity=16, cognitive=37, 68行）は複数のフォールバック戦略（フェンスブロック抽出・`{`/`[`優先順位判定・末尾補完等）を順に試す設計だが、どの戦略で成功・失敗したかがログ出力されない。BL-133で`_query_and_parse_with_retry`に300字プレビューを追加したが、`_safe_json_parse`自体の成功/失敗時の戦略ログは未追加。BL-088（`{`/`[`優先順位バグ）やBL-089（複数フェンスブロック混線）の類問題が再発した際、原因切り分けが困難。**状態**: `open`（記録のみ、優先度低）。 | P3 |
| BL-150 | 低 | `cela_main.py`（高複雑度関数のリファクタリング候補） | 同バグチェックで発見。Codebase Memory MCPの複雑度メトリクスより、`decision_extractor_node`（complexity=26, cognitive=91, 5 loops, 202行）と`_commit_agreement_from_tool`（complexity=26, cognitive=78, 159行, out-degree=12）がコードベース全体で最も複雑。`call_detector`（493行）も関数長として突出。BL-098/BL-118（ファイル分割）と関連するが、ファイル分割前に個別関数の責務分割・サブ関数抽出を先行させるべき。`decision_extractor_node`は抽出ロジック（User/Expert分岐）・遷移解決・DB書き込みの3責務を1関数で抱え、`_commit_agreement_from_tool`はCREATE/UPDATE/SUPERSEDE × Decision/Directive/Deliverable/EssenceProposalの全組合せを1関数で処理している。**状態**: `open`（記録のみ、BL-098/118のファイル分割着手時に合わせて検討）。 | P3 |
| BL-151 | 高 | `cela_main.py`（`_apply_text_edits`、`_revise_goal_tool_impl`） | `log/2026-08-03/1110`ドライラン中に発見。`revise_goal`のedits[0].old_textが、`generate_user_utterance`のプロンプト表示専用の絵文字装飾（「👉 {user_goal}」、実際の格納内容`_CURRENT_GOAL_TEXT`には含まれない）を含んでいたため、User AIが同じ誤った引用を最低9回（BL-056bの残り回数通知が発火する直前まで）再試行し続け、一度も自己修復できなかった。エラーメッセージが「一字一句正確な引用か確認してください」としか言わず実際の格納内容を一切見せていなかったことが根本原因。BL-086の中心機能（前提矛盾に気づいた発注者自身がゴールを是正する経路）が、まさにその想定シナリオで機能しなかった実インシデント。**実装完了（`done`）**: `_apply_text_edits`へ`content_label`パラメータを追加（デフォルト「現在のホワイトボード内容」、`revise_goal`からは「現在のゴール文」を指定）。`exact_count==0`（不一致）時のエラーへ、実際の格納内容の先頭400字スニペット（`_TEXT_EDIT_SNIPPET_MAX_CHARS`）を含めるようにし、同ターン内でモデルが実際の文言を見て自己修復できるようにした。あわせて同種の「表示専用装飾がツールの照合対象からずれている」箇所が他にないか調査し、`call_expert`（Expert自身のプロンプト、5319行目付近）・`call_reflection`（終了監査プロンプト、6367行目付近）・`call_orchestrator`（5055行目付近「Goal: 」プレフィックス）にも同型の装飾があるが、いずれもexact-text一致を要求するツール（`revise_goal`はuserロール専用でExpert/Orchestrator/Reflectionは呼べない）を持たない文脈であるため現状は機能的な罠になっていないことを確認した（将来ロール権限が拡張された場合の潜在リスクとして記録のみ、対応は不要と判断）。新規テスト`tests/test_bl151_apply_text_edits_error_snippet.py`（8件）追加。`python -m py_compile`合格。 | P1 |
| BL-152 | 高 | `cela_main.py`（`call_detector`の`whiteboard_block`構築、`_verify_whiteboard_excerpt_handler`、`detector_node`の注釈挿入呼び出し） | `log/2026-08-03/1347`ドライラン中（BL-151修正後の再開ラン）に発見。`verify_whiteboard_excerpt`（BL-079）が、Detectorが実際に監査しようとしている成果物ではなく、**常に`state["current_task_id"]`のホワイトボードとだけ照合している**ことが判明。ExpertがBL-146のSUPERSEDE経路（他タスク改訂の正規手段、current_task_idゲートの対象外）でtask_1_3の成果物を書き込んだ際、`current_task_id`はBL-125のゲートによりまだtask_1_1のまま（正式な遷移未成立）だった。しかし`call_detector`の`whiteboard_block`（現在タスクの最新ホワイトボードとしてDetectorへ提示するR4文脈）・`_verify_whiteboard_excerpt_handler`（`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`グローバル参照）・`detector_node`の`_annotate_whiteboard_with_detector_comment`呼び出し（実際の注釈挿入先）の3箇所すべてが無条件に`current_task_id`（task_1_1）を対象にしており、Detectorが`read_deliverable_file(task_id="task_1_3")`で正しく読んだtask_1_3の内容からどれだけ正確に引用しても`verify_whiteboard_excerpt`は常に不一致（task_1_1と照合しているため）になる。実測：わずか2ターンで`verify_whiteboard_excerpt`が96回呼ばれ79回（82%）失敗、1エピソードでは`"案A"`という2文字の引用すら失敗し続けMAX_TOOL_ITER=20を丸ごと消費（`ツールを外し、テキスト最終応答を強制`）、たまたま両タスクに共通する汎用語句`"ピーク需要"`がiter=19で偶然一致したためtarget_excerptとして採用された。この判定は最終的に`major`となり注釈挿入（`Whiteboard Annotated`ログ）まで進んでおり、task_1_3固有の批判コメント（乗合タクシー実現性・中古バス混在・山間部按分の恣意性等）が`current_task_id`基準でtask_1_1のホワイトボードへ誤って埋め込まれた可能性が高い（無関係な文書が汚染され、本来指摘すべきtask_1_3側には注釈が付かない）。修正の手掛かりとして、`expert_node`が`write_agreement`実行後に必ずセットする`state["expert_last_whiteboard_edit"]`（`{phase_id, task_id, version}`、今ターン実際に書き込まれた対象を正確に保持）が既に存在するが、`call_detector`/`detector_node`のどこからも参照されていない（現状はロールバック判定など別用途のみ）。**状態**: `open`（記録のみ、実装未着手。ユーザーがドライランを一時停止し起票を優先、他の点検と合わせて対応方針を検討中）。 | P1 |
| BL-153 | 中 | `cela_main.py`（`_check_write_permission`、`call_facilitator`のツール一覧） | `log/2026-08-03/1347`ドライラン中に発見。Facilitatorが`write_agreement(status="Proposed", action_type="SUPERSEDE", entry_type="Deliverable")`でtask_1_3の成果物本体（3案比較の全文）を書き込んでいた。`_check_write_permission`の`ALLOWED_STATUS_BY_ROLE`（`"facilitator": {"Proposed"}`、BL-126 Stage D）は`entry_type`自体を制限しておらず、`status="Proposed"`でありさえすればFacilitatorは本来Expert専用のDeliverableも書き込めてしまう。ユーザー指摘：「ファシリテーターの意思決定を残す趣旨でwrite_agreementを使えるようにしていたが、ドキュメントを書き込むことは想定していなかった。指摘は成果物直接ではなくホワイトボードに書き込む方が良いかもしれない」。**状態**: `open`（記録のみ、実装未着手。別BLとして起票、対応はロールごとの`entry_type`制限表の新設が候補）。 | P2 |
| BL-154 | 高 | `cela_main.py`（`_check_issue_permission`、`_write_issue_impl`、`decision_extractor_node`、`_build_open_issue_pin_text`） | BL-145完了後のQ&Aで、コードベースに3つの並行した「先送り事項」追跡機構（issue_log/agreements Directive-Deferred/plan_drafts）が互いを認識しておらず、BL-125の遷移ゲート・BL-144の滞留検知・BL-145のタスク明示化がいずれもissue_logのみを参照するため、Expertが成果物内で宣言した先送り（`decision_extractor_node`が自動抽出、Expert自身はwrite_issueツールを持たないためこれが唯一の捕捉経路）にはこれらのセーフティネットが一切効かないことが判明。**実装完了（`done`）**：Expertへの新規ツール付与はせず、`decision_extractor_node`がagreements Directive/Deferredの自動抽出と同時にissue_log側にも橋渡しするよう変更。新規内部ロール`decision_extractor_auto`（`detector_auto`と同型、CREATE専用、LLMツール呼び出し経路からは到達不能）を追加し、`_write_issue_impl`のCREATE分岐を拡張してこのロールのみ`defer_to_task_id`を作成時点で設定可能に（再発時は最新宣言が勝つ）。`target_role`によるゲーティングはせずExpert/User双方に一律適用（BL-082がUserブランチの非対称バグだった前例を踏まえた判断）。BL-125/144/145は`raised_by`を見ないため無変更で対応。新規テスト`tests/test_bl154_decision_extractor_issue_log_bridge.py`（8件）追加。`python -m py_compile`合格、フルオフラインスイート630件Pass（1件は無関係な既存の未コミット差分によるテスト不整合、詳細は経緯欄参照）。 | P1 |
| BL-155 | 低 | `cela_main.py`（`_query_AI_live`内コメントのみ）、`tests/test_bl093_think_tool_scratchpad.py` | BL-154検証時のフルスイートで発見。`MAX_TOOL_ITER`が作業ツリー上で20→30へ未コミット・無記録のまま変更済みだった（AGENTS.md §7違反状態）。ユーザーへ確認したところ「task_plan_reviewerの差し戻し後、task_plannerが差戻しタスクを1件ずつ把握し直す過程で上限20に引っかかる事態をログで観測したため」との理由提示があり、正式承認・記録。**実装完了（`done`）**：値は無変更（既に30）、変更履歴コメントへ追記、テストを`test_max_tool_iter_raised_to_30`へ改名し期待値更新。 | P3 |
| BL-156 | 低 | `cela_main.py`（`_query_AI_live`のAPIエラーリトライ時のprint文言・隣接コメント） | ユーザーがドライラン中のnemotron-3-ultra-550b-a55b:freeのResourceExhaustedエラーを見て「APIエラー時には直前の思考は温存されるんでしたっけ？」と質問。調査の結果、`loop_messages`/`reasoning_parts_all`/`iteration_start`はBL-122によりリトライを跨いで温存される（過去の完了済みiterationの思考ログ・tool結果は失われない）一方、エラーが起きたそのiteration自体の思考・tool_call引数はストリーミング途中で例外が飛ぶため破棄され、同じiteration番号でAPI呼び出しのみやり直されることが判明。しかし当該リトライ時のprint文言「ツールループを**最初から**やり直します」がBL-122以前（当時は本当にiter=1へ巻き戻っていた）の挙動を説明する隣接コメントのままで、現在の実装と食い違っていた。**実装完了（`done`）**：print文言を「このiterationのAPI呼び出しをやり直します」へ修正し、隣接コメントにもBL-122以降は巻き戻らない旨を追記。テスト変更なし（文言のみでロジック変更なし、対応するテストも存在せず）。 | P3 |
| BL-157 | 高 | `cela_main.py`（`_bump_issue_occurrence`、`_read_issues_handler`） | `log/2026-08-03/2233`レビューでcurrent_task_idが遷移しない問題を追跡した結果、BL-096の自動バックアップ（`detector_node`、`raised_by='detector_auto'`、汎用catch-allトピック`detector_observation_<task_id>`）が、`current_task_id`が実際の会話の主題より遅れて更新されるタイミングで無関係な指摘を同一バケツへ混入させ、occurrence_count>=2による機械的major/escalated化（D-079/D-080）を見せかけの再発で発火させていたことが判明。実例：User AIが「task_1_2をやれ」と発言→`detector_node`（target_role="user"）のobservationsがtask_1_2についての無関係な指摘→current_task_idはまだ"task_1_1"のため`detector_observation_task_1_1`へ混入→occurrence_count 1→2→major/escalated化→BL-125が（正しく設計通り）遷移をブロック。**実装完了（`done`）**：`_bump_issue_occurrence`・`_read_issues_handler`の両方に`raised_by != 'detector_auto'`の条件を追加し、detector_auto起票行はoccurrence_countに関わらずminor/openのまま維持するようにした（他ロールの既存挙動は無変更）。あわせて再発カウント・昇格・抑制の各分岐にprintログを追加（ユーザー指示：「今後このようなコード側の機械的・暗黙的動作のブラックボックスを可視化するために、すべての動作にprintによるでバックログを追加してください」）。新規テスト`tests/test_bl157_detector_auto_occurrence_exemption.py`（5件）追加。`python -m py_compile`合格、フルオフラインスイート643件Pass。 | P1 |
| BL-158 | 高 | `cela_main.py`（`detector_node`、write_issue成功トラッキング一式） | 同ログ調査の続き。ユーザーの原則「根本的にはユーザーがタスクを次に進めてはいけませんし、detectorが弾くべきです」を受け、`generate_user_utterance`の既存の強制文言（`_get_forced_escalated_issues_text`、BL-136）がUser AIに無視され得ること（実ログで確認）、かつ`call_detector`（target_role="user"）のレビュー基準に「現在のタスクに未解決のescalated issueが残ったまま前進しようとしていないか」のチェックが一切存在しなかったことを確認。**実装完了（`done`）**：LLMの指示追従に頼らない決定論的なPython側却下として、BL-125の実ゲートと完全に同一の`_get_blocking_issues_for_transition`を単一の判断源として再利用し、`detector_node`（target_role=="user"のみ）へ機械的な却下ロジックを追加した。あわせて`write_issue(RESOLVE/DEFER)`が今回のターンで成功したかを追跡する新規フラグ`user_wrote_issue_resolution`（`_LAST_WRITE_AGREEMENT_SUCCEEDED`と同型のグローバル+アクセサ+`LineageState`フィールド）を新設し、ブロック対象issueが残っており今回RESOLVE/DEFERが呼ばれていない場合のみ機械的にmajorへ上書きする。留意点：この却下は「前進しようとしている発言」に限定せず、ブロック対象issueが残っている限り毎ターン発火する（`route_after_user_detector`の3回リトライ上限があるため無限ループにはならない）。新規テスト`tests/test_bl158_detector_rejects_premature_advancement.py`（7件）追加。`python -m py_compile`合格、フルオフラインスイート643件Pass、BL-096/136/144/145/154関連98件も無退行。 | P1 |
| BL-159 | 中 | `cela_main.py`（全体、約50箇所） | ユーザー指示「機械的・暗黙的動作の可視化はコード内のすべての個所について実施してください。全体のデバッグ性を高めます」を受け、Explore agent2体でcela_main.py全体（約9300行）を2回に分けて完全走査し、printによる可視化が欠けている「サイレントな機械的・暗黙的動作」を12段階のTierに分類・列挙（halt/不変条件強制、goal/agreement変異、権限拒否、issueライフサイクル、plan注釈のfire-and-forget、LLM JSONパース失敗フォールバック、verified_facts上書き、ルーティング異常、モード切替、LLM向けone-shot通知、コスメティックなフォールバック、ストリーミング内部/スキーマ移行）。ユーザー確認（AskUserQuestion）により「未調査部分も含め全体調査を先に完了」「Tier 1〜11すべて対応」「Tierごとに順次py_compile」の方針で実施。**実装完了（`done`）**：約50箇所へprint文を追加。調査の過程で`run_ai_vs_ai_loop`内に実際のバグ（decision表示ループの`else`節が実行されないトリプルクォート文字列リテラルのままで、orchestrator/decision_extractor以外の全ロールの決定がコンソールに一切出力されていなかった死にコード）を発見し、実際のprint呼び出しへ修正した。他は全て既存動作を変えない純粋な可視化追加（DB書き込み・状態遷移・フォールバック発生・権限拒否・スキーマ移行等の事実をprintするのみ）。テスト変更なし（出力内容を検証するテストは存在せず、全て既存テストの回帰確認のみ）。`python -m py_compile`合格、Tierごとの区切りでフルオフラインスイート643件Pass（複数回）を確認。 | P3 |
| BL-160 | 高 | `cela_main.py`（`_query_AI_live`のtools=None分岐・ツール呼び出しループ最終応答、`call_decision_extractor`） | ユーザー指示「08-04/0715,0807のログをレビュー」を受け`log/2026-08-04/0715`・`log/2026-08-04/0807`をExplore agent2体でレビュー。BL-159のprint可視化により、0807で`⚠️ [Decision Extractor] JSON解析に失敗しました（生レスポンス冒頭300字: '(APIから空の応答が返されました)'）`が4回中3回発生し、そのたびに`current_task_id`の遷移シグナル（`advances_to_task_id`）を含む抽出結果全体が失われ、`current_task_id`が実行全体を通して`task_1_2`に固着したまま会話内容だけが先行する実害を確認。追加調査（`_query_AI_live`のtools=None分岐、`cela_main.py:3076-3114`を直接確認）により、3回とも失敗直前の`💭思考`ログ（`delta.reasoning`）に`advances_to_task_id`込みの完全に正しいJSONがそのまま出力されていたにもかかわらず、`content = "".join(content_parts)`（`delta.content`のみ）が空だったために`"(APIから空の応答が返されました)"`が返され、`reasoning_parts`（`_LAST_REASONING_TEXT`に保存されるのみでフォールバックには一切使われない）が丸ごと破棄されていたことが根本原因と判明。0715ではDecision Extractorの思考ストリームが同一の中国語文断片を数百回繰り返す暴走に陥りJSONが完成しないまま運用者がCtrl+Cで中断しており、同じ「reasoning/content分離の破綻」が別の形（無限化）で現れた可能性が高い。ユーザーからの補足：この回はモデルを従来の`nemotron_3_ultra`ではなく新規リリース直後の`deepseek-v4-flash-0731`（ポスト学習モデル）で実行しており、モデル自体の挙動不安定性が引き金になっている可能性がある。ただし「reasoning側に答えが出ても拾えずに握りつぶす」という設計上の穴自体は、どのモデル・プロバイダーでも同型の実害（1ターン分の抽出・遷移情報の完全消失、しかもエラーとしてすら露見しない）を引き起こしうる。**実装完了（`done`）**：Plan Modeで設計し3点を修正。(1) `tools is None`分岐（`cela_main.py:3076-3114`）へ、contentが空・reasoningが非空の場合にreasoning全文を代替contentとして採用するフォールバックを追加（`finish_reason=="length"`チェックを通過済みのため打ち切りではなく自発的終了と保証できる箇所でのみ発動）。(2) ツール呼び出しループの最終応答（`cela_main.py:3236-3246`、Expert/User AI/Detector/Orchestrator等ツールを持つ全ノードが通る経路）にも同型の欠陥があったため、既存の`_reasoning_start_idx`（BL-093でdigest切り出し用に導入済み）を使い「最終iterationだけの」reasoningに絞って同様のフォールバックを追加（過去iterationの無関係な思考が混入しないよう意図的にスコープを絞った）。(3) `call_decision_extractor`は従来リトライなしの単発呼び出しだったため、他のJSON判定ノードと同水準の保護として`_query_and_parse_with_retry`（層2リトライ、既存ヘルパー）でラップした。`_safe_json_parse`自体は無変更（フェンス抽出・`{`/`[`探索により説明文+JSON混在に既に対応済みのため、reasoningテキストを渡しても正しく抽出できる）。新規テスト`tests/test_bl160_reasoning_channel_content_fallback.py`（8件：tools=None分岐のフォールバック発火・非発火2種の回帰、ツールループ最終応答のフォールバック発火・非発火2種の回帰、call_decision_extractorのリトライ成功・リトライ全滅の2種）追加。`python -m py_compile`合格、フルオフラインスイート651件Pass。実ドライランでの効果確認は次回待ち。 | P0 |
| BL-161 | 高 | `cela_main.py`（`_commit_agreement_from_tool`、`_write_agreement_impl`、`write_agreement`のTOOL_DISPATCH配線） | ユーザー指示「1018のログをレビュー、エキスパートがホワイトボードのeditに苦戦しています」を受け`log/2026-08-04/1018`をExplore agentでレビュー。Expertの`write_agreement`(UPDATE, edits)呼び出しが11回連続で「old_textが現在のホワイトボード内容に見つかりませんでした」失敗となり、MAX_TOOL_ITER=30のうち半分近く（iter=2〜15）を空費、最終的にeditsを諦めてSUPERSEDE相当の全文書き直しに切り替える実害を確認。コード調査の結果、`_commit_agreement_from_tool`の`phase_id = args.get("phase_id", "")`（フォールバックなし）が`tid = args.get("task_id") or task_id`（呼び出し元task_idへフォールバック）と非対称であることが根本原因と判明。Expertの呼び出しに`phase_id`（`task_id`も）キー自体が無く、`_find_active_deliverable_agreement`が`phase_id=""`と一致する既存Deliverableを見つけられず`target=None`・`old_content=""`のまま`_apply_text_edits("", edits)`が呼ばれ、必ず0件一致で失敗し続けていた。BL-151のエラースニペット（実際の格納内容の先頭部分を見せて自己修復させる機能）も空文字を表示するのみで機能していなかった（真因が別にあったため）。`task_id`には既に`_effective_current_task_id_from`/`_task_id_from`という同型のフォールバックが存在し、`phase_id`にも全く同型の`_phase_id_from(state)`（BL-146時点で他用途向けに新設済み）が既に定義されていたが、`write_agreement`のTOOL_DISPATCH配線が一度も呼んでいなかっただけの配線漏れだった。**実装完了（`done`）**：`_commit_agreement_from_tool`・`_write_agreement_impl`双方に`phase_id: str = ""`引数を追加し`phase_id = args.get("phase_id") or phase_id`のフォールバックへ変更（tidと同じパターン）、フォールバック発動時にprint通知を追加。TOOL_DISPATCH配線へ`phase_id=_phase_id_from(state)`を追加。新規テスト`tests/test_bl161_write_agreement_phase_id_fallback.py`（4件：UPDATE(edits)でのフォールバック成功、フォールバック元情報が無い場合の従来通りの失敗回帰、args明示指定時の優先順位回帰、CREATEでのフォールバック確認）追加。`python -m py_compile`合格、関連既存テスト（BL-084/131/146/151）30件無退行、フルオフラインスイート655件Pass。副次所見として、Detector自動注釈がMarkdownテーブルセルを複数行に分割し将来の一字一句引用をさらに脆くする整形上の問題も発見したが、今回の11連続失敗の直接原因ではなかったため別途記録のみに留める（後続BL候補）。実ドライランでの効果確認は次回待ち。 | P0 |
| BL-162 | 中 | `cela_main.py`（`generate_user_utterance_node`、`call_detector`のgoal_change分岐、`LineageState`） | ユーザー指示「ログレビューを続行、ゴールが書き換えられましたが、次のdetectorがちょっと困っています」を受け`log/2026-08-04/1123`の続きをExplore agentでレビュー。`revise_goal`によるゴール改定（BL-086、予算・待ち時間保証等の構造的矛盾を受けフェーズ分割方式へ改定、改定自体は成功）直後の`review_mode="goal_change"`監査（BL-126 Stage B）で、Detectorが判定基準1「旧文が置換ではなく追記として保持されているか」を確認しようと`read_verified_fact`/`read_deliverable_file`をキーワードを変えて計5回試すも全て`not_found`、最終的に「旧ゴール文が不明のため包含関係は確認不可」と自ら申告する空振りを確認（MAX_TOOL_ITER超過やクラッシュには至らず`constraint_issue: "none"`で継続、実害は軽微だが判定基準を実質評価できていない）。コード調査の結果、`generate_user_utterance_node`（`cela_main.py:7437`付近）が`_LAST_GOAL_REVISION`ブリッジから`new_goal_text`のみを`state["goal"]`へ反映し、`old_goal_text`はどこにも保存せずその場で捨てていたことが根本原因と判明。Detectorが持つツール（read_verified_fact/read_deliverable_file/read_issues）はいずれも「現在の」状態しか読めないため、旧ゴール文を取得する経路が原理的に存在しなかった。**実装完了（`done`）**：`LineageState`へ新規フィールド`goal_revision_old_text: str`を追加。`generate_user_utterance_node`が`_goal_revision.get("old_goal_text") or ""`を`state["goal_revision_old_text"]`へ橋渡しするよう変更。`call_detector`のgoal_change用`domain_role_instruction`へ、`state.get("goal_revision_old_text", "")`（取得不可時は明示的なフォールバック文言）を旧文・新文（`goal`変数、既存のSystem Goal再掲と同一値）として直接埋め込み、Detectorがツール呼び出しなしに両者を直接比較できるようにした。新規テスト`tests/test_bl162_goal_revision_old_text_bridge.py`（4件：橋渡し成功、goal改定なし時に橋渡しされないこと、old_goal_textがNoneの場合に空文字へフォールバックすること、call_detectorのgoal_change分岐が実際にold_goal_textを埋め込んでいることのソース確認）追加。`python -m py_compile`合格、既存`tests/test_bl126_stage_b_goal_change_review_mode.py`（6件）無退行、フルオフラインスイート659件Pass。ユーザー指示「修正してください」に従いPlan Modeを経ずBL-161と同様の判断で直接実装、ドキュメントは事後整備。実ドライランでの効果確認は次回待ち。 | P1 |
| BL-163 | 中 | `cela_main.py`（`_revise_goal_tool_impl`、`ALLOWED_ISSUE_ACTIONS_BY_ROLE`） | BL-162の調査を受け、ユーザーから「ゴール承認後にタスクを1_1からやり直させた方が良いか、それとも後続タスクが気づいて修正してくれるのに期待するか」と設計相談。AIが、全面リスタートはコスト大かつCELAの既存アーキテクチャ（SUPERSEDE改訂・BL-096 issue管理・BL-144滞留検知・BL-145タスク明示化）と不整合であること、完全受け身は見落としリスクがあることを説明し、折衷案として「ゴール改定成功時に承認済み過去タスクへ整合性再確認issueを機械的に起票する」を提案、ユーザーが採用（「注記が最初に出てくれば、AIの混乱も少ないはず」）。AskUserQuestionで(a)issue重大度（minor/open vs major/escalated）、(b)「注記が最初に出る」の実現範囲（既存の起票の仕組みに乗せるだけ vs タスク限定サーフェシングの新規実装）の2点を確認したところ、ユーザーはいずれも推奨案（minor/open、既存の仕組みに乗せるだけ）を選択。EnterPlanModeでExplore agent1体（`_revise_goal_tool_impl`のstate非依存性、`_write_issue_impl`のCREATE分岐・内部自動起票ロールの既存パターン、完了済みタスクの列挙方法、既存pin機構のグローバルスコープを調査）を実行し承認を得て実装。**実装完了（`done`）**：`ALLOWED_ISSUE_ACTIONS_BY_ROLE`へ新規ロール`"revise_goal_auto": {"CREATE"}`を追加。`_revise_goal_tool_impl`の成功パス末尾（`db_append_decision`直後・`return`直前）へ、`get_agreements_from_db`を`reversed`で走査し`(phase_id, task_id)`ごとに最新の`entry_type="Deliverable"`行を1件だけ判定する`_find_active_deliverable_agreement`と同型のdedupロジックを追加、最新statusが`RESOLVING_DELIVERABLE_STATUSES`（Approved/Approved_with_Conditions/Implicitly_Accepted）に含まれる全タスクへ`_write_issue_impl`を直接呼び出し、topic=`goal_revision_consistency_check_<phase_id>_<task_id>`・severity="minor"のissueを機械的にCREATEする処理を追加した。既存の`_write_issue_impl`・pin builder（`_build_open_issue_pin_text`等）は無変更で、severity="minor"のため既存のUser AI向けopen issue一覧へ自然に乗り、BL-136の強制RESOLVE/DEFER文言・BL-125/158のタスク遷移ブロック（いずれもmajor/escalated対象）は発動しない。新規テスト`tests/test_bl163_revise_goal_auto_flags_past_tasks.py`（6件：承認済み2タスクへの起票、Rejectedのみのタスクの対象外確認、完了済みタスク0件でのクラッシュ非発生、複数UPDATE履歴があっても1回のみ起票、最新状態がSupersededへ変わった場合の対象外確認、`revise_goal_auto`ロールの権限登録確認）追加。`python -m py_compile`合格、既存BL-086/096/136/144/154関連101件無退行、フルオフラインスイート665件Pass。実ドライランでの効果確認は次回待ち。 | P2 |
| BL-164 | 高 | `cela_main.py`（`recent_decitions`構築、`get_decisions_from_db`、Detector系プロンプトの`Recent Decisions（参考程度）`節） | BL-163完了後、ユーザー指示「1123のログの続きをレビュー」を継続。task_1_3の財務モデル監査で、`Detector`ノードが同一ターン内で`verify_whiteboard_excerpt`を29回中11回失敗させ続け、MAX_TOOL_ITER=30に到達し`⚠️ [Detector] 最終iteration（30）のためツールを外し、テキスト最終応答を強制します`が同一run内で2回発火（`log/2026-08-04/1123/log_no_prompt.md`行11484・14373）していることを確認。原因調査の結果、`recent_decitions = json.dumps(get_decisions_from_db(conn, run_id)[-2:], ...)`（`cela_main.py:5812`）が直近2件のdecisions行を`SELECT *`丸ごとJSON化してプロンプトの「Recent Decisions（参考程度）」節（`cela_main.py:6204`）へ埋め込んでおり、そこに含まれる`internal_thought_process`（前回Detectorの生の思考過程）に、既にExpertの再提出でsupersede済みのVer.3ホワイトボードの一字一句引用（「現実的複合リスク...296...ギリギリ」、実際は改訂後Ver.5/7で「3,436」等へ変わっていた）がそのまま残っていたことが根本原因と判明。新しいDetectorはこの「参考程度」ブロックから引用文字列を誤って採用し、実際に監査対象の最新ホワイトボードには存在しないテキストを`verify_whiteboard_excerpt`で検証し続けた（プロンプトダンプで`Recent Decisions`内のdecision `D-1785815485253`のinternal_thought_processに該当引用が verbatim に含まれ、同一の古い引用が2回目の別Detector監査でも再出現したことを確認済み）。CELAの「Detector却下→Expert修正→Detector再監査」という主要ループでは、却下判定時の`internal_thought_process`（古い引用付き）と直後の修正提出が、まさに再監査タイミングでの「直近2件」になりやすく、偶然ではなく構造的に再現しうる失敗モード。BL-152（`verify_whiteboard_excerpt`が誤ったtask_idと照合し続けた事例）と症状は同型だが、原因は別（BL-152はtask_id特定の誤り、本BLはプロンプトへの生reasoningテキスト混入）。**実装完了（`done`）**：`recent_decitions`を`SELECT *`の生行から`who`/`what`/`why`のみのキュレーション済み要約へ変更（`internal_thought_process`等の生列を除外）、「Recent Decisions（参考程度）」節の直前へ「target_excerpt/verify_whiteboard_excerptの根拠には必ずR4節の内容のみを使用してください」という出所限定の注意書きを追加した。ユーザーから「internal_thought_process除去で監査能力の粒度が落ちないか」「ゼロベースで見せるべき情報構造を設計するなら」の2点質問があり、`call_detector`の既存構成を4層（監査対象そのもの／今回の裏付け証拠／今回ターンの挙動監査／継続性・参考情報）に整理した上で、`thought_process_audit`（今回ターンのExpert/User AI自身の思考過程専用、既に正しくスコープ）との役割重複を確認し、修正対象は「継続性・参考情報」層（`recent_decitions`）のみで十分と回答、大規模な情報構造の再設計は不要と判断した（`docs/design/decision_lineage.md`参照）。新規テスト`tests/test_bl164_recent_decisions_no_raw_reasoning_leak.py`（4件：ソース確認2件＋実行時挙動確認2件、`_query_and_parse_with_retry`をmonkeypatchしてプロンプト文字列を捕捉し、Recent Decisions節のJSONペイロードから`internal_thought_process`が消え`who`/`what`/`why`は残ること、decisions0件でもクラッシュしないことを確認）追加。`python -m py_compile`合格、既存Detector関連テスト（BL-079/091/093/104/126/162）102件無退行、フルオフラインスイート669件Pass。実ドライランでの効果確認は次回待ち。 | P1 |
| BL-165 | 低 | `cela_main.py`（`_write_agreement_impl`のCREATE分岐ログ、`cela_main.py:1982`） | BL-164の調査中に副次的に発見。`_write_agreement_impl`のDeliverable CREATE分岐（`cela_main.py:1982`）が、`apply_whiteboard_patch`の実際の戻り値`v`を無視し常に文字列`"Ver.1"`をログ出力している。同一イベントで`apply_whiteboard_patch`自身のログ（`cela_main.py:3994`）は正しく実際のバージョン番号（例：`Ver.5`）を出しており、同一の`write_agreement`呼び出しに対し「Ver.5」と「Ver.1」という矛盾するバージョン表示がログに並ぶ（`log/2026-08-04/1123/log_no_prompt.md`行10388-10389で確認）。機能的な実害（DB上のバージョン管理自体は正しい）はないが、ログを読む人間・エージェント双方を混乱させる（BL-164調査時に実際に一時混乱の原因になった）。**状態**: `open`（記録のみ、`print`の`"Ver.1"`を実際の`v`変数へ差し替えるだけの軽微な修正）。 | P3 |
| BL-166 | 高 | `cela_main.py`（`_build_agreements_context`のアイコン・ラベル判定、`cela_main.py:4825-4848`） | 1123ログの続行クロール中（ユーザー指示「1123のログをくまなくレビューして、他にバグがないかをクロールしてほしい」）に発見。ドライランが一時停止・再開を繰り返す過程（`log/2026-08-04/1123`→`1355`→`1435`）で、User AIが直前ターンでBL-158により差し戻されたにもかかわらず、次ターンで「task_1_3（財務持続性モデル構築）はCompleted and approved (Ver.9)」と誤認し、未解決の労基法違反issueを残したままtask_1_4へ進もうとしていたことを`log/2026-08-04/1123/log_no_prompt.md`行16265以降で発見。実際にはtask_1_3は`status="Rejected"`のまま（`cela.db`のagreements行`AG-1785818709566`で直接確認、Approvedへの更新は存在しない）で、Ver.9はホワイトボードの実体としては財務モデルの再提出ではなく却下メモそのもの（`whiteboards/phase_1_task_1_3_V9.md`の中身がRejection文）だった。原因調査の結果、`_build_agreements_context`（`cela_main.py:4793`）のアイコン判定`icon = "📄" if status == "Proposed" else "✅"`（`cela_main.py:4826`）が、Deliverableの場合`status`が`"Proposed"`以外なら`"Approved"`も`"Approved_with_Conditions"`も`"Rejected"`も無条件で✅にしてしまうことが判明。ラベル側も`type_label = "[成果物]"`固定（`cela_main.py:4835-4836`）で、Decision/Directiveエントリには存在する却下時`[却下事項]`分岐（`cela_main.py:4843-4844`）がDeliverableには一切なく、Rejectされた成果物が「✅ [成果物]」として表示され続ける。`_build_agreements_context`はUser AI・Expert・Detector・Orchestratorなどほぼ全ノードの「決定事項DB」表示に共通で使われているため、Rejectされた成果物がある限り、以降のどのノードの目にも承認済みとして映り続ける構造的欠陥。BL-062（Detectorの却下が正しくDBへ反映されるか）は解消済みだったが、今回見つかったのは「DBへの反映（status="Rejected"）は正しく起きているのに、表示ロジックがそれを握りつぶす」という一段深い、別の欠陥。**実装完了（`done`）**：`_build_agreements_context`のDeliverable分岐を、`status == "Proposed"`（📄）／`status in RESOLVING_DELIVERABLE_STATUSES`（✅）／それ以外（⚠️）の3分岐へ変更。ラベルも`status == "Rejected"`の場合`"[却下成果物]"`を返すよう追加。新規テスト`tests/test_bl166_rejected_deliverable_icon.py`（6件：Approved/Approved_with_Conditions/Implicitly_Acceptedが引き続き✅になること、Proposedが引き続き📄になること、Rejectedが✅ではなく⚠️[却下成果物]になること、正常な合意事項と混在しても各行が正しく区別されること）追加。`python -m py_compile`合格。 | P0 |
| BL-167 | 高 | `cela_main.py`（Reflection内のstagnant issue滞留検知、`_formalizable_stale`フィルタ、`cela_main.py:8654`） | BL-166と同じ調査の中、ユーザーから「タスク再構築でissue/タスク番号の依存関係が崩壊するのでは、旧ゴールの2台という数字が残ったままissueも触られていない」との指摘を受け、`log/2026-08-04/1435`（`1123`→`1355`→`1435`と再開を繰り返した末のドライラン）を調査。Reflectionが3件のescalated issue（「車両台数2台ではサービス要件を満たせない」「オペレーター常駐要件と研修費前提の矛盾」「オペレーター4名体制での労基法違反」）をユーザーノード3回通過での滞留として検出しdiscussion_statusを機械的にstagnant化（`log_no_prompt.md:756`）したにもかかわらず、実際にTask Plannerへタスク再構築の引き金として引き継がれたのは労基法違反の1件のみだった（`log_no_prompt.md:757, 1021-1022`）ことを確認。原因は`_formalizable_stale = [i for i in _stale_escalated if not i.get("defer_to_task_id")]`（`cela_main.py:8654`）というフィルタで、「車両台数2台...」issueは過去にtask_1_1で起票された際`defer_to_task_id="task_1_2"`が、「オペレーター常駐要件と研修費前提の矛盾」issueも`defer_to_task_id="task_4_1"`が既に設定されていたため除外されていた（`defer_to_task_id`が無い＝新規issueだった労基法違反issueのみが通過）。しかし**task_1_2は既にApproved済みで完了しており、二度と実行されない**——受け皿として指定されたタスクが完了しても、そのタスクが実際にissueを解決（`resolved`化）したかは一切検証されず、`defer_to_task_id`が一度でも設定された事実だけで恒久的にBL-145の再構築対象から除外され続ける「永久迷子」状態になる。実際、Task Plannerは労基法issueのみを渡されたため、再構築後のtask_1_1の説明・受入基準は「車両購入費（2,500万円/台）」「1億円÷2,500万円＝4台が理論上限」という**ゴール改定前**の車両単価のまま再出力された（`log_no_prompt.md:1174-1178`、BL-168とも関連）。**実装完了（`done`）**：新規ヘルパー`_is_task_completed(conn, run_id, task_id)`（受け皿タスクの最新Deliverableが`RESOLVING_DELIVERABLE_STATUSES`かを判定）を追加し、`_formalizable_stale`フィルタを「`defer_to_task_id`が無い、または受け皿タスクが既に完了済み」へ変更。同型の欠陥を持っていたBL-136の`_get_forced_escalated_issues_text`（User AI向け毎ターン強制解決プロンプト）にも同じヘルパーを配線し、受け皿タスク完了後は再度提示されるようにした。新規テスト`tests/test_bl167_defer_to_task_id_completed_target.py`（9件：`_is_task_completed`単体4件、`reflection_node`の`_formalizable_stale`で受け皿未完了時は従来通り除外・受け皿完了後は再度対象化される2件、`_get_forced_escalated_issues_text`で同様の2件）追加。`python -m py_compile`合格。 | P0 |
| BL-168 | 高 | `cela_main.py`（`verified_facts`テーブル・`upsert_verified_fact`/`get_verified_facts_from_db`、`_revise_goal_tool_impl`） | BL-167と同じ調査の流れで、なぜ再構築後のtask_1_1がゴール改定前の車両単価のまま出力されたのかを追跡した結果、`log/2026-08-04/1435/log_no_prompt.md`行2394-2395でTask Plan Reviewerが`read_verified_fact(topic_keyword="車両")`を呼んだ際、`max_vehicle_count='2'`（台）・`procurement_scenarios`（全シナリオ「2台」）・`initial_cost_breakdown`（「車両費2500万円/台」）という、ゴール改定（BL-086、車両単価500〜1,000万円/台へ変更）**より前**にtask_1_1のExpertが確定した値が、無警告のまま「確定値」として返されていることを確認した。`upsert_verified_fact`（`cela_main.py:4483`）は`(run_id, variable_name)`をキーとしたUPSERT方式（`ON CONFLICT ... DO UPDATE`）で、該当変数が再度`upsert_verified_fact`されない限り、内容の新旧・前提の変化を問わず永久に「現在の確定値」として`read_verified_fact`から返り続ける。ゴール改定によってtask_1_1由来のこれらの値は前提から無効化されているにもかかわらず、それを示す仕組みが一切存在しないため、Task Planner・Task Plan Reviewer等あらゆる後続ノードが無警告でこの古い値を参照し続ける。実際にこれが原因で、再構築後のtask_1_1の説明・受入基準がゴール改定前の「車両購入費2,500万円/台」「4台が理論上限」のまま据え置かれた（BL-167参照、`log_no_prompt.md:1174-1178`）。BL-163（`_revise_goal_tool_impl`の成功パス末尾で、ゴール改定時に承認済み過去タスクへ整合性再確認issueを機械的に起票する仕組み）は`agreements`（成果物）のみを対象にしており、この`verified_facts`ストアは対象外だったため、BL-163実装後もこの穴は塞がれていなかった。**実装完了（`done`）**：`_revise_goal_tool_impl`のBL-163ブロック（`_flagged`計算）の直後に、`_flagged`の各task_idを`source_task_id`に持つ`verified_facts`行を検索し、`reason`列の先頭へ`"⚠️[BL-168: ゴール改定後未確認] ..."`という警告を付記する処理を追加（`value`自体は改変しない）。既にマーキング済みの行は再度マーキングしない（同一runで複数回ゴール改定された場合の重複防止）。新規テスト`tests/test_bl168_verified_facts_stale_after_goal_revision.py`（5件：flaggedタスク由来のverified_factsへの警告付記、対象外タスク由来のfactsは無変更、verified_facts0件でのクラッシュ非発生、2回連続ゴール改定でも警告が重複しないこと、複数タスクが混在する場合にflagged対象のみ警告されること）追加。`python -m py_compile`合格。 | P0 |
| BL-169 | 高 | `cela_main.py`（`_check_write_permission`、`cela_main.py:1859`） | BL-166〜168修正後にドライランを再開した`log/2026-08-04/1548`をhaltまで追跡した際に発見。task_1_3の4回目（最終）リトライで、User AIが11回のpython_repl計算の末に`write_agreement(entry_type="Deliverable", action_type="CREATE", status="Proposed", task_id="task_1_3", ...)`を自ら呼び出し、財務モデル成果物を丸ごと執筆・提出（`verified_facts`更新ログにも`by=user`）した上で、直後の発言で受入基準を自己採点し「✅」と宣言、Expertを一切介さず次タスクtask_2_1への移行を一方的に指示していたことを`log_no_prompt.md`行3506-3866で確認した。原因は`_check_write_permission`（`cela_main.py:1859`）がstatusのみで権限判定しておりrole×entry_typeの組み合わせ制限が存在しないこと。今回はDetector（Domain Review）がピーク需要200人に対し最大輸送力168人しか運べない物理的矛盾を`major`判定で捕捉し（`log_no_prompt.md:4231`）、差し戻し上限到達でreflectionへ回り、Reflectionが`status=stagnant`・理由に"User is approving defective deliverables (collusion)"と明記（`log_no_prompt.md:6072`）、最終的にFacilitatorのリトライ予算も超過し`state["halt"]=True`でシステム全体が停止した（`log_no_prompt.md:6081-6086`）。今回はDetectorが捕捉したため実害は限定的だったが、Detectorが見逃せば「Userが自分で書いた成果物をUserが自分で承認する」自作自演がノーチェックで通り得る構造的な穴で、Expert↔Detectorの査読ループを丸ごと迂回できる。**実装完了（`done`）**：`_check_write_permission`へ`caller_role=="user"`かつ`entry_type=="Deliverable"`かつ`action_type=="CREATE"`の組み合わせを拒否する分岐を追加。既存Deliverableへのstatus変更（UPDATE/SUPERSEDE、承認・却下含む）は従来通り許可し、Expertによる新規作成にも影響しない。新規テスト`tests/test_bl169_user_deliverable_create_forbidden.py`（9件）追加、既存テスト2件（`test_bl146_write_agreement_current_task_gate.py`・`test_r4_smoke.py`）がuserロールでのDeliverable CREATEを使うテスト用ショートカットに依存していたため検証意図を保ったまま修正。`python -m py_compile`合格。 | P0 |

---

## Backlog 一覧

### BL-001: Agreement TypedDictの`content`/`rationale`リネーム

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | R1完了 |
| 関連 | [cela_phase1_impl_Plan.md §2.3, §9](../r1_r2_r3b_core/cela_r1_impl_Plan.md)、[decision_log.md D-003](../decision_log.md) |

**内容:**

R1では「壊さない」優先で、既存の`Agreement` TypedDict（`content`/`rationale`キー）をそのまま維持し、`db_append_agreement`内でSQLite列名（`decision_what`/`reason_why`）へマッピングするラッパー方式を採用した（`get_agreements_from_db`も逆方向にエイリアスを付与）。この二重変換は将来のツール化（R3の`write_agreement_tool`）でスキーマ不一致の温床になりうる。

**2026-07-19完了**: `Agreement` TypedDictのキーを`decision_what`/`reason_why`に統一し、`db_append_agreement`/`get_agreements_from_db`のcontent/rationaleエイリアス変換コードを除去した。呼び出し側（`_build_agreements_context`、`call_reflection`、`decision_extractor_node`のUPDATE/CREATE両分岐、`integrator_node`、`reviewer_node`）を全箇所`decision_what`/`reason_why`参照に追従。ダミーデータによるDB往復スモークテストでcontent/rationaleキーが復元されないことを確認済み（実LLM呼び出しなし）。

**2026-07-19追記（実LLM本番実行で検出した移行漏れ）**: ユーザーが実際に`cela_main.py`を実行したところ、`decision_extractor_node`内のターミナル表示用print文（[cela_main.py:2363](../../../cela_main.py)、`agreement['rationale']`）がリネーム対象から漏れており、`KeyError: 'rationale'`で本番実行がクラッシュした。この行は`Agreement`辞書の構築（`decision_what`/`reason_why`、L2340-2341）とは別に存在するデバッグ出力で、DB往復のみを見るオフラインスモークテスト（T-6）ではこの`print`文自体を経由しないため検出できなかった。`agreement['reason_why']`に修正し、`python -m py_compile`で構文確認済み。他に`agreement[...]`/`a[...]`形式で`content`/`rationale`旧キーを参照している箇所がないことをgrepで確認済み（該当なし）。**教訓**: フェイククライアントによるオフラインテストは`_query_AI_live`の分岐網羅には有効だが、グラフノード内の表示・整形ロジックまでは通らないため、実LLM実行によるE2Eドライランでしか拾えない不具合がある。

**完了条件:**

- `Agreement` TypedDictのキーを`decision_what`/`reason_why`に統一する（呼び出し側コードも追従）。（✅ 完了、2026-07-19に移行漏れ1箇所を追加修正）
- `db_append_agreement`/`get_agreements_from_db`のcontent/rationaleエイリアス変換コードを除去する。（✅ 完了）
- 実施判断はR2着手前に行う（impl_Plan §9準拠）。（✅ R2の頭で実施、D-003準拠）

---

### BL-002: R1完了条件の実データA/Bドライラン未実施

| 項目 | 内容 |
|------|------|
| 状態 | `blocked`（構造的一致は確認済み。指標A・B・Cの実測はR2待ち） |
| 優先度 | P0 |
| 依存 | R2（F-2.6 Python REPL機械的検算ゲート実装） |
| 関連 | [cela_phase1_design_v7.md §3.4, §5, §5.1](../r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md)、[traceability.md T-5](../traceability.md)、[decision_log.md D-002](../decision_log.md) |

**内容:**

今回のR1実装セッションでは、`get_db_connection`/`init_db`/`db_append_*`/`get_*_from_db`/`_build_*_context_from_db`/`build_graph()`のダミーデータによるスモークテストと`python -m py_compile`による構文検証のみを実施した。設計書§5の評価メトリクスA（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ）は、実際のLLM API呼び出しを伴う`run_ai_vs_ai_loop`本体のE2E実行（過疎地域バスシナリオ）が必要であり、未実施。

**2026-07-18追記**: `phase1/phase1_dryrun.md`のStep 1〜4を実施し、list版ベースラインとSQLite版の**構造的一致**（agreements/decisions件数、status分布、topic登録順序）を実データで確認した（[traceability.md T-5](../traceability.md)、Pass）。これはBL-003の完了条件を満たすものであり、BL-002が要求する指標A（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ、最低5試行）の**実測比較そのものはまだ行っていない**。

**2026-07-18追記2（[D-002](../decision_log.md)）**: 上記ドライランの実ログで、`numerical_allocator`が提示する数値提案（トリップ時間・処理能力・予算試算等）がdetectorに何度も数値矛盾（major）で差し戻される事態が繰り返し観測された。これはLLMの暗算（機械的検算なし）が原因であり、設計書付録A「暗算は原理的に信頼できない」の実例そのもの。F-2.6検算ゲート（Python REPL、R2で実装予定）が無い現状で指標A・B・Cを測定しても、「検算ゲート欠如による差し戻し」と「R1永続化基盤自体の効果」が混在し、R1固有の効果を分離評価できない。したがって**指標A・B・Cの実測比較は、R2実装後まで意味を持たないと判断し、依存をR2に変更した**。R1スコープの検証自体は構造的一致（BL-003, T-5）で完了とみなす。

**完了条件:**

- `phase1/phase1_dryrun.md`を新規作成し、手順化する。（✅ 完了）
- 変更前（list版）と変更後（SQLite版）を同一タスクで実行し、指標A・B・Cを比較する。（構造的一致のみ確認済み。指標A・B・Cの実測値比較は未実施）
- 結果を`traceability.md`のT-*に記録する。（✅ T-5として記録済み）

---

### BL-003: Record&Replayスタブの実LLM応答による往復検証未実施

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-002 |
| 関連 | [cela_phase1_impl_Plan.md §7](../r1_r2_r3b_core/cela_r1_impl_Plan.md)、[traceability.md T-5](../traceability.md) |

**内容:**

`query_AI`のREPLAY_MODE（record/replay/off）・call_seqキー機構・キャッシュミス時の例外送出は、ダミークライアントによるスモークテストのみ実施済み。実際のLLM応答を使い、list版ベースラインの実行結果と、SQLite版をreplay実行した結果を比較する回帰確認（impl_Plan §7.2の合格基準1「構造的一致」・2「Hydrate再現性」）は未実施。

**2026-07-18完了**: list版ベースライン（コミット`5ef0382`にRecord/Replayスタブを移植）をRecordモードで実行（過疎地域バスシナリオ、Turn 1〜2完了直後に[D-001](../decision_log.md)準拠で打ち切り）、記録した45件のフィクスチャをSQLite版（コミット`2133989`）でReplay実行。合格基準1「構造的一致」（agreements 15=15件、decisions 47=47件、status分布・topic登録順序一致）を確認。Replayはlist版の停止点と完全に一致するタイミングで想定通りのキャッシュミス例外を出して停止した。合格基準2「Hydrate再現性」・合格基準3「再起動後保持」は本試験の対象外（詳細は[traceability.md T-5](../traceability.md)）。

**完了条件:**

- list版ベースライン実行 → recordモード実行 → SQLite版実装への切替 → replayモード実行、の手順で構造的一致を確認する。（✅ 完了）
- 結果を`traceability.md`のT-*に記録する。（✅ T-5として記録済み）

---

### BL-004: 死んだimportの除去

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [cela_phase1_design_v7.md §6](../r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md) |

**内容:**

`cela_main.py`冒頭の`from secrets import choice`、`from unittest import result`は機能に影響しない未使用importだが、`result`変数のシャドーイングリスクがある。設計書§6の方針に従い、R1では無関係な清掃として混在させず、BL起票のみに留めた。

**完了条件:**

- 該当2行を削除し、`result`のシャドーイングが実際に発生しないことを確認する。

---

### BL-005: `turn_count`が`app.invoke()`内で凍結され、外側ターン表示・上限が実態と乖離

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [cela_phase1_design_v7.md §3.1](../r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md)（グラフトポロジは維持、R1では触っていない既存プロトタイプ由来の挙動） |

**内容:**

`run_ai_vs_ai_loop`の外側whileループは`state["turn_count"] = current_turn`をinvoke呼び出し直前に1回だけセットする（`cela_main.py` L2601相当）。しかしグラフ内のどのノードも`turn_count`を更新しない。`route_after_expert_decision`（同 L2412相当）は`state["turn_count"] % state["reflection_interval"] == 0`を判定して次に`reflection`へ進むか`generate_user_utterance`へ直接ループバックするかを決めるが、この判定はinvoke呼び出し中ずっと同じ値のまま評価され続ける。

その結果、invoke開始時点の`turn_count`が`reflection_interval`の倍数でない限り、`expert_decision_extractor`終了後は毎回グラフ内部で直接`generate_user_utterance`へループバックし、外側の`current_turn`（および画面表示の「🔷 [Turn N/30]」）は更新されないまま対話ラウンドが何度も進む。外側に制御が戻る（＝`current_turn`が進む）のは、(a) invoke開始時点でたまたま`turn_count`が`reflection_interval`の倍数だった、(b) detectorが3回連続でmajor判定を出しretry上限に達した、(c) `ready_for_review`が立った、(d) `halt`、のいずれかのみ。

**実データでの確認**（2026-07-18 12:56開始のドライラン実行ログ`log/2026-07-18/1256/log_no_prompt.md`）: 「🔷 [Turn 1 / 30]」表示は54行目に出た後、1211行目まで（1150行超）一度も更新されず、その間にnumerical_allocatorの提案→detectorのmajor判定→差し戻しのサイクルが複数回発生していた。

**影響:**

- 設計書§5の指標C（差し戻し回数・ターン数比較）の「ターン数」がPython側の`current_turn`基準だと、実際の対話ラウンド数を大幅に過小評価する。
- 30ターン上限（暴走防止ガードレール）が「外側ループ30回」という意味では機能するが、1回の外側ループが内部で無制限に対話ラウンドを重ねうるため、API呼び出し数・実行時間の上限としては期待通りに働かない。

**完了条件（未確定、方針は要判断）:**

- 対応方針（`turn_count`をノード内でインクリメントする／指標Cの集計方法を「グラフ内部ループを含む実際の対話ラウンド数」に変更する／現状維持でドキュメントに注記するのみ、等）をR2着手前までに決定し、`decision_log.md`にD-xxxとして記録する。
- 既存プロトタイプの動作実績（設計書§1「既に実装済みで実運用ログで高い検出精度が確認されている」）を壊さないことを優先し、修正する場合は最小差分に留める。

**2026-07-19追記（影響範囲の再評価：安全網が事実上無効化されていたことが判明）**: 表示上のずれだけでなく、より深刻な副作用が実ドライラン（`log/2026-07-19/2056`）で確認された。`route_after_expert_decision`の`state["turn_count"] % state["reflection_interval"] == 0`判定は、`turn_count`が凍結されている間は`reflection`（延いてはその先の`facilitator`）に一度も到達できない。今回のドライランでは同一タスク（task_1_2）へのDetector差し戻しが3回連続発生したが、`turn_count`が1のまま（`reflection_interval`デフォルト3の倍数にならない）だったため、`reflection`は一度も発火せず、`facilitator`も出現しなかった。つまり本Issueは「表示のずれ」ではなく「周期的な議論健全性チェック（reflection）とその先の調停機構（facilitator）が丸ごと機能停止しうる」問題であり、優先度の見直しが必要（詳細は[decision_lineage.md 論点19](../decision_lineage.md)、[BL-017](issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り)）。ユーザー方針として、本修正はR4（ホワイトボード化・スコープ制御の検討）と合わせて着手する。

**2026-07-23追記（reflection発火の症状のみBL-048で迂回、`turn_count`本体は依然未修正）**: [BL-048](issue_backlog.md#bl-048-reflectionfacilitatorの周期発火を新設round_countで復旧するturn_count本体は未修正)により、reflection/facilitatorの周期発火という副作用症状のみ`round_count`という別カウンタで迂回・解消した。しかし本Issueの本体（`turn_count`自体の意味、外側ターン表示・`max_turns`上限判定が実態と乖離している点）は未修正のまま残っており、本Issueは引き続き`open`とする。

---

### BL-006: R2 ツール呼び出しループの`query_AI`集約実装

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-001（R2頭で実施） |
| 関連 | [D-008](../decision_log.md#d-008-r201ツール呼び出しループをquery_aiに集約する設計を承認)、[decision_lineage.md 論点7](../decision_lineage.md)、impl_Plan R2.0.1 |

**内容:**

R2 実装計画（impl_Plan R2.0.1）の方針に基づき、ツール呼び出しループ（Function Calling / Tool Use）を各ノード関数ではなく共通層 `query_AI` に集約する。理由：①全ノードがすでに `query_AI` を呼んでおり1箇所追加が最小差分、②DRY、③Replay 境界の維持。ツール dispatch は `TOOL_DISPATCH` 辞書に分離し、R3 の `write_agreement_tool` 追加時にループ本体を変更せずに済むようする。この集約方式は Anthropic 公式 SDK の `tool_runner`、OpenAI Agents SDK の `Runner`、LangChain の `AgentExecutor` と同様の主流パターン（D-008 承認済み）。

**2026-07-19完了**: `query_AI`/`_query_AI_live`に`tools`引数を追加し、`tools is None`時は既存パス（非破壊）、`tools`付与時はMAX_TOOL_ITER=5のツール呼び出しループを既存`try/except`リトライブロック内で実行するよう実装。`TOOL_DISPATCH = {"python_repl": _run_python_repl}`をモジュールレベル定数として分離。フェイクOpenAIクライアント（実LLM API呼び出しなし）による5件のオフラインスモークテストで、非ツールパス維持・ツール往復・壊れた引数JSONの自己修復・非収束時のRuntimeError伝播・finish_reason=length検出のすべてを確認済み。

**完了条件:**

- `query_AI` 内にツール呼び出しループ（MAX_TOOL_ITER=5、既存 `try/except` リトライブロック内）を実装。（✅ 完了）
- `TOOL_DISPATCH` 辞書によるツール名→処理のマッピング分離を実装。（✅ 完了）
- design v7 §3.5.2 の `call_expert_with_tools` 例は「説明用最小サンプル」である旨を ★v9 追記で明記済み（2026-07-18 更新）。

---

### BL-007: R2 Python REPL サンドボックスの多層防御・危険呼び出し AST 検査

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [D-006](../decision_log.md#d-006-python-replサンドボックスはビルトイン呼び出しのast検査多層防御を追加する)、[decision_lineage.md 論点5](../decision_lineage.md)、impl_Plan R2.2 |

**内容:**

Python REPL サンドボックス（`_run_python_repl`）の AST 検査を、`ast.Import`/`ast.ImportFrom` のみのチェックから拡張する。`open`/`eval`/`exec`/`compile`/`__import__`/`globals`/`vars`/`getattr` 等の危険な名前を AST 上の `Name`/`Attribute`/`Call` 参照としてブロック（import 文なしで呼べるビルトインも対象）。加えて、AST blacklist の限界（`().__class__.__bases__` 経由等の既知の回避）を認め、実行プロセスを低権限ユーザー・書き込み不可ディレクトリで起動する多層防御とする。design v7 §3.5.3 に「危険呼び出し検査」「多層防御」として ★v9 追記済み（2026-07-18 更新）。

**2026-07-19完了**: `_run_python_repl`を実装（`subprocess.run(["python", "-I", "-c", code], ...)`によるisolated mode分離実行、タイムアウト5秒、出力10KB制限）。AST検査で`ast.Import`/`ast.ImportFrom`に加え、`_DANGEROUS_NAMES`（open/eval/exec/compile/__import__/globals/locals/vars/getattr/setattr/delattr/memoryview/breakpoint）を`Name`/`Attribute`/`Call`ノードとして検査。ダミーコードによるスモークテストで、`import os`・`from os import system`・`open(...)`・`__import__("os")`・`eval(...)`・`exec(...)`のすべてが`[REPL Error]`として拒否され、許可モジュール（math/statistics/datetime/json/fractions/decimal）は正常動作、タイムアウト・構文エラーも正しくハンドリングされることを確認済み（実LLM呼び出しなし、権限絞り込み自体はOS依存のためコード上は多層防御の1層目＝AST検査のみを自動テストで検証、プロセス権限絞り込みはコメントで方針明記に留まる）。

**完了条件:**

- `_run_python_repl` の AST 検査が `open`/`eval`/`exec`/`__import__` 等のビルトイン呼び出しをブロックする。（✅ 完了）
- サブプロセス実行が低権限・書き込み不可ディレクトリで起動される。（`python -I`によるisolated modeで実装。OSレベルの低権限ユーザー起動は本番運用環境依存のため未実施、設計上の限界としてコードコメントに明記済み）
- design v7 §3.5.3 の記述と実装が整合している。（✅ 完了）

---

### BL-008: R2 許可モジュールから`random`を除去、`decimal`/`fractions`は理由付き維持

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [D-007](../decision_log.md#d-007-python-repl許可モジュールからrandomを除去しdecimalfractionsは理由付きで維持する)、[decision_lineage.md 論点6](../decision_lineage.md)、impl_Plan R2.2 |

**内容:**

`_ALLOWED_IMPORTS` から `random` を削除する（`random` は検算の決定性＝再現性を損なうため）。`decimal`/`fractions` は浮動小数点誤差回避の目的に合致するため理由を明記して維持。design v7 §3.5.3 の許可モジュールリストに `fractions`/`decimal` を追記し、`random` 除外の理由を ★v9 追記済み（2026-07-18 更新）。

**2026-07-19完了**: `_ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "fractions", "decimal"}`として実装。スモークテストで`import random`が拒否され、`decimal`/`fractions`は正常動作することを確認済み。

**完了条件:**

- `_ALLOWED_IMPORTS` が `math, statistics, datetime, json, fractions, decimal` のみである。（✅ 完了）
- design v7 §3.5.3 の許可リストと実装が一致している。（✅ 完了）

---

### BL-009: R2 ツールループのリトライ粒度（層1/層2）の粗さを許容する

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 依存 | BL-006 |
| 関連 | [D-004](../decision_log.md#d-004-ツール呼び出しループは既存のtryexceptリトライブロック内に配置する)、[decision_lineage.md 論点3](../decision_lineage.md)、impl_Plan R2.3 |

**内容:**

ツール呼び出しループを既存 `query_AI` の `try/except` リトライブロック内に配置する（D-004 承認）。この方式は「ツールループ全体を1単位」としてリトライするため粒度が粗く、1回失敗すると途中経過（`loop_messages`）を捨てて最初からやり直す。実害は軽微（MAX_TOOL_ITER=5、ローカル Python REPL は失敗しにくい）と判断し当面許容するが、将来の改善候補として BL に残す。

**2026-07-19完了**: `_query_AI_live`のツールループ冒頭に`[CONSTRAINT]`タグ付きコメントでリトライ粒度の粗さと許容理由（BL-009参照）を明示済み。粒度細分化自体は本番動作での実害確認まで見送り（設計判断どおり）。

**完了条件:**

- 実装時にリトライ粒度の粗さをコードコメント（`[CONSTRAINT]` タグ推奨）で明示する。（✅ 完了）
- 本番動作で致命的な再試行コストが確認された場合のみ、粒度細分化を再検討する。（継続監視事項として残置）

---

### BL-010: R2ツールループの例外が既存の広い`except Exception`に飲み込まれ原因が隠蔽される

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-006 |
| 関連 | [D-009](../decision_log.md#d-009-r2ツールループの例外処理を一時的api障害とロジックエラーに区別する)、[decision_lineage.md 論点9](../decision_lineage.md)、impl_Plan R2.3 |

**内容:**

別チャットのClaudeレビューにより、R2.3のツール呼び出しループを既存`try/except`（`except Exception as e:`、`cela_main.py:399-405`）の内側に配置する設計（D-004）が、「一時的なAPI障害」と「ロジックエラー」を区別しない副作用を持つことが判明した。壊れたtool_call引数JSON（`json.loads`失敗）や`MAX_TOOL_ITER`非収束の`RuntimeError`が、指数バックオフ（最大約248秒）を経て`"(サーバー高負荷によるAPIエラー)"`という誤った診断に丸められ、原因調査を著しく妨げる。加えて、ツールループには既存非ツールパスにある`finish_reason == "length"`（出力打ち切り）検出が欠落しており、`max_tokens`超過によるtool_call引数の途中切れが「壊れたJSON引数」として上記の隠蔽経路に混入する。

**2026-07-19完了**: `openai`パッケージの`APIError`/`APIConnectionError`/`RateLimitError`/`APITimeoutError`をimportし、`_query_AI_live`の外側`except`をこの4例外に限定。`json.loads(tc.function.arguments)`の`JSONDecodeError`は個別捕捉しツール結果としてモデルへ返却（自己修復）。ツールループ内`tool_calls`判定前に`finish_reason == "length"`検出を追加。フェイククライアントによるオフラインスモークテストで、壊れた引数JSONの自己修復・非収束時のRuntimeError伝播・length検出の3点をすべて確認済み。

**完了条件:**

- `tc.function.arguments`の`json.loads`失敗は`json.JSONDecodeError`を個別に捕捉し、例外化せず`{"role": "tool", ...}`としてモデルに返して自己修正させる。（✅ 完了）
- 外側`except Exception as e:`を`except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:`に狭め、ロジックエラーはバックオフ無しで伝播させる。（✅ 完了）
- ツールループ内、`tool_calls`判定前に`if choice.finish_reason == "length": raise ValueError(...)`を追加する。（✅ 完了）

---

### BL-011: OpenRouter経由の複数バックエンドでのFunction Calling対応状況が未検証

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [D-010](../decision_log.md#d-010-プロバイダ別function-calling対応の網羅検証はmvp段階では見送りblに留める)、[decision_lineage.md 論点10](../decision_lineage.md)、要件定義書v35 付録B.5.3 |

**内容:**

要件定義書v35 付録B.5.3は、Function Calling/Tool Use導入時にプロバイダごとの対応状況を事前確認することを求めている。現状`_query_AI_live`はOpenRouter経由で複数の実バックエンド（`extra_body.provider.order=["baidu/fp8","siliconflow/fp8","wandb/fp8","morph"]`、`cela_main.py:383-390`）へ強制ルーティングしており、各バックエンドがOpenAI互換の`tools`/`tool_calls`スキーマをどこまで安定サポートするかは未検証。R2.9の指標D（数値矛盾検出率5/5）が「たまたま安定したプロバイダに当たっただけ」で通過している可能性がある。D-010によりMVP段階では網羅検証を見送り、リスクの可視化のみ本BLで行う。

**完了条件（MVP後・P2以降）:**

- `provider.order`の各バックエンド（baidu/fp8, siliconflow/fp8, wandb/fp8, morph）でtool callingが安定動作するか個別に検証する。
- 不安定なバックエンドがあれば`provider.order`から除外するか、`allow_fallbacks`の扱いを見直す。

---

### BL-012: B.5.1既知誤判定（Detectorの偽陽性）の非退行テストが未定義

| 項目 | 内容 |
|------|------|
| 状態 | `done`（テスト実装済み。実LLM呼び出しでの実行はユーザー指示待ち） |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [D-011](../decision_log.md#d-011-b51既知誤判定detectorの偽陽性の非退行テストを指標dと対で追加する)、[decision_lineage.md 論点11](../decision_lineage.md)、impl_Plan R2.6・R2.9・R2.10 |

**内容:**

別チャットのClaudeレビューにより、R2.6が付録B.5.1の既知誤判定（Detectorが上限内の数値差を`major`と誤判定するバグ）を修正するプロンプトを復活させる一方、R2.9の完了条件（指標D）は「矛盾を仕込んだケースを5/5検出できること」という陽性検出のみを定義しており、「上限内の正当な数値差を誤って`major`と判定しない」という陰性側（偽陽性回避）の非退行テストが計画・`phase1_dryrun.md`のいずれにも存在しないことが判明した。R2.5のF-2.6検算指示とR2.6の上限内数値差の除外指示は将来調整され得るため、指標Dのテストのみではこのバグの再発を検知できない。

**2026-07-19完了**: `tests/test_f26_detection.py`を新規作成。`test_detector_flags_numeric_contradiction_5_of_5`（Detector側指標D、5/5でmajor検出）、`test_reviewer_flags_numeric_contradiction_5_of_5`（Reviewer側指標D、5/5でpassed=False）、`test_detector_no_false_positive_within_cap`（B.5.1非退行、3回連続でnone/minorのままmajorが混入しないこと）の3テストを実装。シナリオは「申告合計は上限内に見えるが内訳の実合計は上限超過」（矛盾側）と「内訳・申告・上限すべて整合」（非退行側）の2種で、いずれも`python_repl`による再計算なしには検出できない設計とした（`python -m pytest --collect-only`で3件収集確認済み）。テストはDetector/Reviewerが使う`client_auditor`のAPIキー（`DSEEK_V4_FLASH_USER_KEY`）が未設定の環境では自動スキップする。

**2026-07-19追記（実LLM実行完了、T-7）**: ユーザーが実LLM呼び出しで実行。1回目はBL-013の不具合（`python_repl`が`print()`なしの裸の式で無出力になる問題）により1件非収束でFAILEDしたが、BL-013修正（ツール説明文に`print()`必須を明記）後の再実行で**3 passed**（Detector 5/5 major、Reviewer 5/5 passed=False、B.5.1非退行3/3 none）。指標D（5/5検出率）を実LLMで達成確認。詳細は[traceability.md T-7](../traceability.md)参照。

**完了条件:**

- `tests/test_f26_detection.py`に、上限内の正当な数値差（予算超過していない）を仕込んだ成果物のテストケースを追加し、「`none`または`minor`と判定され`major`にならないこと」を検証する。（✅ 完了）
- `cela_phase1_impl_Plan.md` R2.9の完了条件表に、指標Dと対になる基準（B.5.1既知誤判定の非退行）を明記する。（✅ 完了、指標D実測値も追記）
- R2.10のテスト格納先にも追記する。（✅ 完了、`tests/test_f26_detection.py`として存在）

---

### BL-013: `python_repl`ツールがprint()なしの裸の式で無出力になり非収束・テスト失敗を招く

| 項目 | 内容 |
|------|------|
| 状態 | `done`（プロンプト側の修正のみ実施。サンドボックス側のフォールバックは見送り、下記参照。修正効果は再実行で確認済み、T-7） |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | `cela_main.py` `PYTHON_REPL_TOOL`、`_run_python_repl`、`tests/test_f26_detection.py` |

**内容:**

`tests/test_f26_detection.py`の`test_detector_flags_numeric_contradiction_5_of_5`を実LLM呼び出しで実行したところ、試行3/5でDetectorが`python_repl`に`2500 + 300 + 800`という裸の式（`print()`なし）を3回連続で送り、いずれも`_run_python_repl`が`subprocess.run(["python", "-I", "-c", code], ...)`（非対話スクリプト実行、対話型REPLの自動エコーなし）のため`"[REPL] (no output)"`を返し続けた。iter=4・5でようやく`print()`を使った正しいコードに切り替えたが、この時点で最終応答を返す前にMAX_TOOL_ITER=5を使い切り、非収束の`RuntimeError`が送出されテストが`FAILED`した。ツール定義（`PYTHON_REPL_TOOL`の`description`・`code`パラメータの説明文）には`print()`使用例が1箇所あるのみで、「`print()`しないと出力が一切返らない」という明示的な警告がなかったことが原因。

**2026-07-19完了（プロンプト側）**: `PYTHON_REPL_TOOL`の`description`に「非対話スクリプト実行であり裸の式は出力されない、`print()`必須、`[REPL] (no output)`が返ってきたら`print()`忘れなので同じ式を繰り返さず`print()`を付けて再試行すること」を明記。`code`パラメータの説明文にも同様の注記を追加。`python -m py_compile`で構文確認済み。

**見送った代替案（サンドボックス側の自動フォールバック）**: `_run_python_repl`内でASTを解析し、最終文が裸の式（`ast.Expr`）かつ標準出力が空だった場合に自動で`print()`相当の結果を補う実装も検討したが、(a) `ast.get_source_segment`によるコード再構築が必要でサンドボックス自体の複雑度が増す、(b) プロンプト側の修正で同じ問題が解消するか実LLM再実行での効果測定が先、という理由で今回は見送った。プロンプト修正後も同種の非収束が再発するようであれば、この対応をBLとして再起票する。

**完了条件:**

- `PYTHON_REPL_TOOL`の説明文に`print()`必須の警告を明記する。（✅ 完了）
- 修正後、`tests/test_f26_detection.py`を再実行し、同種の非収束（裸の式の繰り返し）が解消したことを確認する。（✅ 完了、T-7で非収束0件を確認。全13回のツール呼び出しのうち11回はiter=1で正答、`print()`忘れの再発なし）

---

### BL-014: 本番ドライラン（Expertノード）で非収束クラッシュ — 3つの複合原因

| 項目 | 内容 |
|------|------|
| 状態 | `done`（A・B・Cすべて実装・オフライン確認済み。実LLMでの本番再ドライランは未実施） |
| 優先度 | P0 |
| 依存 | なし |
| 関連 | [D-014](../decision_log.md#d-014-max_tool_iterを5から10へ引き上げる暫定挙動を見て調整)、`cela_main.py` `_run_python_repl`・`_query_AI_live` |

**内容:**

`tests/test_f26_detection.py`の実LLM実行成功後、ユーザーが本番`cela_main.py`をドライラン中、`expert_node`（`Expert:cost_optimizer`）が`RuntimeError: ツール呼び出しが5回を超えて収束しませんでした`でクラッシュした。ログを解析した結果、3つの異なる原因が複合していた。

**原因A（未修正・設計相談中）**: `_run_python_repl`は`subprocess.run(["python", "-I", "-c", code], ...)`で呼び出しごとに**独立した新しいプロセス**を起動しており、対話的なREPLのように前回呼び出しの変数を保持しない。iter=2で定義した`annual_revenue`がiter=3の新しいプロセスに引き継がれず`NameError`が発生し、モデルが同じ変数群を再定義するiter=4の再送信を強いられた（1回分の無駄撃ち）。ツール名「python_repl」から状態保持を期待する自然な誤解であり、ツール説明文にも制約が明記されていなかった。対応方針（対話的な永続プロセスへの変更 vs 説明文での制約明記）はユーザーと設計相談中。

**原因B（2026-07-19完了）**: `-I`（isolated mode）は`PYTHONIOENCODING`等のPYTHON*環境変数を無視するため、子プロセスがcp932ロケール（Windows既定）で絵文字（✅/❌）を`print()`すると子プロセス自身が`UnicodeEncodeError`でクラッシュしていた（iter=4で発生、2回目の無駄撃ち）。`-X utf8`フラグを追加（`-I`と共存可能、実機確認済み）し、親側の`capture_output`も`text=True`から`encoding="utf-8", errors="replace"`へ変更して修正。

**原因C（2026-07-19完了、D-014）**: `MAX_TOOL_ITER=5`は「ツール呼び出しの往復回数」の上限であり、5回とも`tool_calls`が返ると最終テキスト回答を送る余地がゼロになる。原因A・Bの無駄撃ち2回を差し引いても、探索的に複数回検算したいExpertノードには余裕がなさすぎると判断し、ユーザー承認のもと10へ引き上げ（AGENTS.md §7準拠）。恒久値ではなく、原因A・B修正後の挙動を見て絞る可能性がある暫定値。

**完了条件:**

- 原因B: `_run_python_repl`のサブプロセス起動に`-X utf8`を追加し、絵文字等のUnicode文字を含む`print()`が子プロセス内でクラッシュしないことを確認する。（✅ 完了、`python -I -X utf8 -c "print(chr(0x2705))"`で実機確認、オフラインスモークテストでも確認）
- 原因C: `MAX_TOOL_ITER`を5から10へ変更する。（✅ 完了）
- 原因A: 対応方針（対話的永続プロセス化 or ツール説明文での状態非保持の明記）を決定し実装する。（✅ 完了、下記参照）
- 原因A・B・C修正後、本番ドライランで同種の非収束クラッシュが再発しないことを確認する。（オフラインスモークテストで確認済み。実LLMでの本番再ドライランは未実施）

**2026-07-19完了（原因A）**: ユーザーとの相談の結果、「エージェントは一発で多角的に検証しようとpythonコードを書いており、単発呼び出しだと結果をAI自身の記憶に頼って次の計算に持ち越すことになりhallucinationリスクがある」という理由から、対話的（状態保持）セッション化を採用（ツール説明文での回避策ではなく実装で解決）。`_run_python_repl`のAST安全検査を`_check_repl_code_safety`として共通化し、新規クラス`_PythonReplSession`を追加。

- 子プロセスは`subprocess.Popen`でツールループ開始時に1回だけ起動し（遅延起動）、コードをJSON1行としてstdin経由で送信、専用センチネル文字列（`\x00CELA_REPL_END\x00`）が出力されるまでをそのコードの結果として読み取るプロトコル。
- 状態（`ns`辞書によるexec()の名前空間）は1回のツールループ（1回の`_query_AI_live`呼び出し）の間のみ保持し、ノード・リトライをまたいでは共有しない（`_query_AI_live`内で毎回新規`_PythonReplSession()`インスタンスを生成）。
- AST安全検査（許可モジュール・危険ビルトイン）は状態保持後も**送信コードごとに毎回実施**（過去に安全と判定されたコードが実行された後でも、次の送信で`import os`等を送れば拒否される）。
- タイムアウト（デフォルト5秒）またはプロセス異常終了時は、セッションを終了し次回呼び出しで新規プロセスを立て直す。この際「セッションがリセットされ、それまでの変数は消えた」旨をエラーメッセージでモデルに明示し、無言で状態が消えて混乱するのを防ぐ。
- `try/finally`で、成功・非収束・例外いずれの終了経路でも子プロセスを確実に終了させる（ゾンビプロセス防止）。
- `PYTHON_REPL_TOOL`の説明文を更新し、「このターン内で状態が保持される（前の呼び出しの変数を再定義不要）」ことを明記。

オフラインスモークテスト（実LLM呼び出しなし、5パターン）で全て確認: (1) 呼び出し間での変数の保持、(2) 危険なimportを送っても拒否されるだけでセッション自体は生き続け直前の変数も残る、(3) 絵文字出力（原因Bの回帰確認）、(4) タイムアウト時にセッションがリセットされ明確なエラーメッセージが返り、かつ次回呼び出しでは新しいプロセスとして正常に使えること、(5) フェイククライアント経由で`_query_AI_live`を2回のツール呼び出しで動かし、1回目で定義した変数が2回目でそのまま再利用されること。テスト後・既存の5シナリオ回帰テストいずれの実行後もゾンビプロセス残存なし（`Get-Process python`で確認）。既存の`test_f26_detection.py`は`--collect-only`で引き続き4件収集を確認。

---

### BL-015: 資料由来の一次情報・python_repl出力の機械的再利用（LLM記憶転記の削減）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（設計相談中、実装未着手） |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [decision_lineage.md 論点15](../decision_lineage.md)、`cela_main.py` `_PythonReplSession`（BL-014原因A、スコープ設計の先例） |

**内容:**

本番ドライラン（BL-014の修正確認中）で、`python_repl`が対話型セッション化されたことで検算がスムーズになったことをユーザーが確認。その所感を踏まえ、ユーザーから追加提案があった：資料に記載された条件・数値や、エージェント実行中のpython出力といった「固定情報」を、LLMがいったん自分の言葉で読み書きし直す（記憶に頼って転記する）のではなく、変数やファイルに書き出してそのまま次のステップに渡す「コピペ」的な受け渡しにできないか、というもの。狙いはハルシネリスクの低減。

別チャットのClaudeからは、抽出結果をJSON/CSV等の構造化データとしてファイル/変数に保存し、以降のステップはLLMが記憶から書き直すのではなくそのデータを再読込（またはコードが直接参照）する形にすべき、という賛同回答があった。理想はLLMを介さずコードtoコードでデータを受け渡し、LLMは「どのファイルを次に使うか」の指示役に徹する案。トレードオフとして、抽出ステップ自体（資料→ファイル化）はLLMが行う以上ハルシネーションは完全には消えないこと、パイプラインが増える分の実装・管理コスト増が挙げられていた。

本セッションでの検討で、実際のドライランログ（Detectorが加重平均速度等をExpertとは独立に再計算し、両者の値が一致することを確認している箇所）を材料に、「独立再計算そのものがF-2.6の検証機構として機能している」という点を指摘した。これを踏まえ、対象を用途で切り分ける方針を提示：

- **資料由来の一次情報**（絶対目標に記載された人口・予算・単価等、外部から与えられた事実）: 構造化格納・機械的再利用が有効。転記のたびにハルシネリスクが乗る一方、事実は再計算しても同じ値にしかならないため独立再検証の意味が薄い。
- **エージェントが導出した計算値・判断**（Expertの検算結果など）: 現状どおり各ノードが独立に再計算・再検証する設計（Detectorの独立検算）を維持する方が安全性が高い。ここを機械的コピペにすると「検算」ではなく「伝言」になり、F-2.6が防ごうとしている経路とは別の弱点を生む。

ユーザーからは「情報の使いまわしはノード内に限定するといいかもしれません」という追加意見があった。これはBL-014原因Aで採用した`_PythonReplSession`のスコープ設計（1回の`_query_AI_live`呼び出し＝1ノードの間のみ状態を保持し、ノード・リトライをまたいでは共有しない）と同じ考え方であり、既存の設計方針と一貫する。

**完了条件（未確定、要設計）:**

- 資料由来の一次情報を対象とした抽出→構造化格納→再利用の対象範囲を「1ノード内」に限定するか、複数ノード・複数ターンにまたがる永続的な参照ストア（DB等）が必要かを設計判断し、`decision_log.md`にD-xxxとして記録する。
- ノード内限定とする場合、`_PythonReplSession`のスコープ設計との統一・共通化余地を検討する。
- エージェントが導出した計算値・判断は対象外とし、現状の独立再検証（Detectorの再計算等）の設計思想を維持する方針を明記する。
- 抽出ステップ自体のハルシネーションリスクへの対策（出典併記、元資料との機械的突合検証等）を設計に含める。
- 実装前にAGENTS.md §5.2（設計ブループリント）に基づき、ファイル構成・アーキテクチャ選択・既存コードとの結合点を提示しユーザー承認を得る。

---

### BL-016: Detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする

| 項目 | 内容 |
|------|------|
| 状態 | `done`（2点とも実装・オフライン確認済み。実LLMでの本番再ドライランは未実施） |
| 優先度 | P0 |
| 依存 | なし |
| 関連 | [D-016](../decision_log.md#d-016-bl-016探索的タスクでの10回ツール呼び出し非収束へ2点の対応を実施する)、[decision_lineage.md 論点16](../decision_lineage.md)、`cela_main.py` `_query_AI_live`・`call_detector`、`log/2026-07-19/1012/log_no_prompt.md`（実ログ） |

**内容:**

BL-014（A・B・C）修正後の本番ドライランで、`Expert:requirement_engineer`が3回目の差し戻し後の再試行中に`RuntimeError: ツール呼び出しが10回を超えて収束しませんでした`でクラッシュした（`cela_main.py:696`）。ログ（`log/2026-07-19/1012/log_no_prompt.md` 2489〜3423行目）を解析した結果、BL-014のいずれの原因（NameError／UnicodeEncodeError）の再発でもないことを確認した。`_PythonReplSession`は10回連続の呼び出しで変数を正しく引き継ぎ続けており、絵文字出力も一切クラッシュしていない。

**根本原因**: Expertが「3台の車両でピーク需要66.7人/hを満たせるか」という組合せ最適化問題（ルート分割・停車箇所数・相乗り率・予約スロット制など）に自力で取り組み、各iterで一つの案を試しては`❌`判定を受けて次の案に移る、という探索を繰り返した。iter=8では自分自身の前iterのモデルの矛盾（持ち越し客の待ち時間が実質3時間になる）に気づき自己修正するなど、F-2.6の趣旨に沿った良い挙動も見られたが、iter=9で「3台購入＋1台リース（実質4台）、初期投資1億円以内、実質赤字882万円で補助金枠3,000万円に収まる」という整合の取れた結論に到達した後も、iter=10で不要な再比較検算を実行してしまい、テキストでの最終回答を返す余地がゼロになった状態でMAX_TOOL_ITER=10に到達した。

**Detectorの役割との関係**: この差し戻しループの直前、Detectorは2回にわたり本質的に妥当な差し戻しを行っている。1回目は「指摘4点のうち3点に無回答のままTask 1.2も未提出」という完了度不足の指摘。2回目は機械的検算による本物の誤り3件の指摘（山間部区間で加重平均速度37km/hを誤用（制約上は20km/h指定）、シフトモデルが「最低2名常駐」要件を満たさない、システム維持費の内訳合計と主張額の64万円の不一致）。特に2回目はF-2.6が存在する理由そのものの実例であり、Detectorの厳格さ自体は正しく機能している。問題は、Detectorの完了度判定が「ユーザーの指摘全点に一度で完全に応える」という二値判定しかなく、「部分的に妥当な結論に達した時点で受理し残りは申し送りとする」という中間経路がないため、Expertが局所改善のループから抜け出せずMAX_TOOL_ITERを使い切ってしまう点にある。

**2026-07-19完了**: ユーザー承認（[D-016](../decision_log.md#d-016-bl-016探索的タスクでの10回ツール呼び出し非収束へ2点の対応を実施する)）のもと2点を実装。

1. **残りiter数の意識づけ**: `_query_AI_live`のツールループで、各iterationのツール実行結果を`loop_messages`に追加した直後に`remaining_iters = MAX_TOOL_ITER - iteration`を計算し、`0 < remaining_iters <= 2`の場合に`[SYSTEM NOTICE] ツール呼び出しの残り回数はあと{remaining_iters}回です...`という注意喚起メッセージを`role: "user"`として注入する。数値検算そのものの厳格さ（F-2.6ゲート）には触れない。
2. **Detector完了度判定の緩和**: `call_detector`のAgent評価用プロンプト（役割別分岐）と共通major定義の両方に、「未対応項目が残っていても、何が未着手かを具体的に名指しした上で次のステップとして明示している場合は、それだけでは major にせず minor とする」という明示的な例外規定を追加。数値矛盾・計算ミスの検算要求（python_repl必須）はそのまま維持。

オフラインスモークテスト（実LLM呼び出しなし、フェイククライアント使用、2パターン）で確認: (1) 常にtool_callsを返し続ける最悪ケースで、iteration=7（remaining=3）まではSYSTEM NOTICEが注入されず、iteration=9（remaining=2, iter=8処理後に注入）以降は注入され続けることを確認。(2) タスクがcapに達する前（iter=3）に完了する通常ケースでは、SYSTEM NOTICEが一度も注入されないことを確認。`python -m py_compile`で構文確認済み、`pytest --collect-only`で既存4テストの収集に影響なしを確認。

**完了条件:**

- ツールループ側で残りiter数をモデルに意識させ、残り僅少時に強制的にテキスト最終回答を促す仕組みを実装する。（✅ 完了）
- Detectorの完了度判定に「明示的な申し送り事項付きの部分回答」を合格として扱う経路を追加する（数値矛盾チェックの厳格さは維持し、完了度チェックのみ緩和する）。（✅ 完了）
- 対応方針を`decision_log.md`にD-xxxとして記録する。（✅ 完了、D-016）
- 実装後、同種の探索的タスク（組合せ最適化を要するシナリオ）で再ドライランし、非収束が解消することを確認する。（オフラインスモークテストで注入ロジックのみ確認済み。実LLMでの本番再ドライランは未実施）

---

### BL-017: 「差し戻しループ沼」からの脱出機構（ファシリテーター／そもそも論への立ち返り）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（構想段階、設計要） |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [BL-016](issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする)、[decision_lineage.md 論点16](../decision_lineage.md)、[decision_lineage.md 論点20](../decision_lineage.md)、要件定義書_v35.md F-9・F-10.2〜F-10.6（本Issueの上位互換にあたる既存仕様、下記追記参照） |

**内容:**

ユーザーの開発経緯の共有による起票。python_repl導入以前・Detector強化以前は、成果物が10ターン以内で完成しレビュワーも通過していたが、実際には計算が合わないまま文脈に流されてUser AI・Detector・Reviewerが揃って見逃す事態が多発していた（別チャットのGeminiによる確認で判明）。これに対応してDetectorを厳格化し、User AI発言直後にもDetectorノードを追加配置した結果、今度は「差し戻しループ沼」（BL-016）にはまるようになった。

この経緯から、ユーザーは「ファシリテーター」または「そもそも論に立ち返り、本質的な出発点から新たな発想で目的を達成させる（並行宇宙的な発想）」という、同じアプローチをローカルに磨き続けるループから抜け出すための機構のアイデアに至った。BL-016の直接対応（iter数の意識づけ・Detector完了度判定の緩和）とは別解であり、より根本的に「N回連続で同じ方向の局所改善を繰り返しても核心の判定が変わらない場合、前提を疑うか現時点のベストな案をいったん確定させるかの選択を促す」ような仕組みを想定している。

**現状確認（本Issueの起票にあたりユーザーから訂正を受けて確認したコード上の事実）**: `facilitator_node`／`call_facilitator`（`cela_main.py:1845`, `2567`）としてファシリテーター機構は既に実装済みである。`reflection_interval`に基づく定期タイミングで`facilitation_count`（上限3、`route_after_facilitator`）を消費しながら発火し、「議論が目標から脱線しそうな、または同じ論点で停滞していそうな」場合に、次に深掘りすべきテーマを穏やかに提示するメッセージを`chat_history`に注入する。ただし、この既存機構は**定期タイミング（reflection_interval）で発火**するものであり、「Detectorのmajor判定が同一トピックでN回連続した」「同一ノードへの差し戻しがM回連続した」といった**差し戻しループそのものを検知して介入するトリガーは持っていない**。したがって本Issueの本体は「ファシリテーターを新設すること」ではなく、**既存の`facilitator_node`／`call_facilitator`を、差し戻しループ検知という新しいトリガー系列から呼び出せるように拡張するか、別の介入ロジックを追加するか**の設計判断である。

**2026-07-19追記（当初の設計意図の想起、およびFacilitator本来の振る舞いとの乖離）**: ユーザーが当初の設計意図を想起し共有。3ターンごとのreflectionは「議論の膠着」「ゴールドリフト」の検知を目的とし、それを受けてFacilitatorが**視点を変える調停**（後に「そもそも論への立ち返り」構想に発展）を行う、という構想だった。過去の検証では、目標・制約自体を意図的にかなり無理筋（実現不可能）に設定し、エージェント・Detectorがゴールドリフトを検出できるか、Facilitatorが本質に立ち返れるかを試していた。具体例（ユーザー提示）：予算が物理的に成立しなくなった時、Facilitatorが「この課題の本質はバスの"購入"ではなく、移動の自由と可能性を社会保障としてどう提供するかである」とゴールを抽象化し、「リースや中古活用はどうか」「完全オンデマンドである必要があるか」「そもそも"バス"である必要があるか（自動運転乗用車ではだめか）」「そもそもオンデマンドである必要は」という形で、狭い視野でデッドロックした議論をゴールの抽象化・本質化から解きほぐす、という調停行動を意図していた。

今回のドライラン（`log/2026-07-19/2056`、task_1_2への3連続差し戻し）は、この意味では**Facilitatorが本来対象とすべき「膠着」ではない**。Detectorは毎回異なる本物の計算ミス（感度分析の算術ミス、走行距離算出式の循環論法、ピーク乗車率と平均乗車率の混同）を検算で見つけており、遅いが着実に前進している「生産的なイテレーション」である。単純に「N回差し戻されたらFacilitator発火」という設計にすると、この種の正当な反復収束プロセスまで中断させてしまうリスクがあるため、トリガー設計では**「同じ論点で堂々巡りしている（膠着）」と「違う論点を順に片付けている（生産的な反復）」を区別する**必要がある。

さらに、現状の`call_facilitator`実装プロンプト（`cela_main.py:1910`付近、「未決着の論点をやさしく提示する」という穏やかなナッジ）は、上記の「ゴール抽象化・本質への立ち返り」という当初の調停意図を実装していない。したがって本Issueのスコープは、(a) 差し戻しループ検知のトリガー設計に加え、(b) **Facilitator自体の振る舞い（プロンプト）を「そもそも論」的な視点転換ができるものへ作り直すこと**の両方を含む。

**reflectionとの関係（ユーザー明言）**: reflectionの周期発火（3ターンごと）はFacilitatorのトリガー設計とは**独立**しており、差し戻し状況に関わらずそのまま発火するべきである。reflectionが発火しないのはBL-005（`turn_count`凍結）由来のバグであり、BL-005修正で復活させる。Facilitatorの新トリガー設計とreflectionの周期発火は混同しないこと。

**2026-07-19追記（既存仕様との重複が判明——本Issueは上位仕様の先行実装として再定義）**: ユーザーが将来ビジョン（そもそも論への立ち返り、決定履歴のAIへの再提示、MCTSによる過去経験の再利用）を共有した際、AIが`要件定義書_v35.md`を確認したところ、本Issueが目指す機能は既に以下として詳細に仕様化されていたことが判明した。

- **F-10.6「ゴール抽象化に伴う多分岐ブランチ並行探索（MCTS-Fork）」**: 「議論がどうしても制約条件と衝突してデッドロックに陥った際、ファシリテーターが介入して上位目的（Why）まで抽象度のエスカレーションを実行し、代替アプローチを示す複数のブランチ（世界線：並行宇宙）を動的にフォークさせて別スレッドで並行探索させる」——本Issueが目指すFacilitator挙動そのもの。
- **F-9「経験のDNA伝承（Lessons Learned）」**: `[状況]→[とった手段]→[結果]→[教訓]`を`lessons_learned`テーブルに蓄積し、次回起動時にRAGで事前インジェクションする構想。
- **F-10.2〜F-10.5**: 確証バイアス検知による「悪魔の代弁者」強制起動、フレーミング効果の克服、UCB探索係数の動的ブースト、「前提破壊挑戦（ちゃぶ台返し）」の受容。
- **`goal_shift_events`テーブル**（R5タスク）: `triggered_by`列に`MCTS_Fork_Result`が既に用意されている。

これらは`cela_roadmap_v25.md`により意図的に**「Phase 6以降（検証後判断）」**へ配置されている（F-10.6「実装コストが非常に高い割に、本当にイノベーションが生まれるかの評価指標が未確立のため保留」、F-9「過去プロジェクトの失敗が別プロジェクトで実際に回避されるかを検証してから本格導入判断」等）。したがって**本Issue（BL-017）は、F-10.6の全面実装ではなく、MVP（R1〜R5）の範囲でコストを抑えて実現できる「差し戻しループ検知＋Facilitatorプロンプトのゴール抽象化対応」という、F-10.6の先行縮小実装として位置づける**。完全なMCTS-Fork（並行世界線の別スレッド探索）やF-9のRAG的な経験再利用は、要件定義書の既定方針通りPhase 6以降に持ち越す。

**完了条件（未確定、構想段階。フルスコープはPhase 6のF-10.6/F-9に委譲、本IssueはMVP範囲の先行実装のみ）:**

- 「差し戻しループ沼」または「局所改善の反復」をどう検知するか（同一ノードへの差し戻し回数、同一トピックへのDetector major判定の連続回数など）を設計する。ただし「生産的だが遅い反復」（毎回異なる本物の指摘）と「本当に膠着している反復」（同じ論点の堂々巡り）を区別できる検知条件にする。
- 検知後の介在方法（既存`facilitator_node`をこのトリガーからも呼び出せるようにするか、別ロジックを追加するか）を設計する。
- `call_facilitator`のプロンプトを、当初意図していた「ゴールの抽象化・本質への立ち返り」（例のようなそもそも論の提示）ができる内容に作り直す。現状の「未決着論点の穏やかな提示」から踏み込む。ただしF-10.6のような並行世界線の別スレッド探索までは行わず、単一スレッド内でのゴール再提示に留める（MVPスコープ）。
- reflectionの周期発火（BL-005修正で復活）とFacilitatorの新トリガーは独立したものとして設計・実装する。
- R4（ホワイトボード化・スコープ制御の検討、D-018）と合わせて着手する（ユーザー方針）。AGENTS.md §5.2の設計ブループリントを提示しユーザー承認を得てから実装する。

---

### BL-018: task_planner由来のタスク間依存関係が状態に構造化されておらず、横断的な影響判断ができない

| 項目 | 内容 |
|------|------|
| 状態 | `open`（構想段階、設計要） |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [decision_lineage.md 論点16](../decision_lineage.md)、`cela_main.py` `LineageState`（`current_task_summary`）、`whiteboard_drafts`テーブル（`phase_id`/`task_id`列） |

**内容:**

ユーザーの開発経緯の共有による起票。task_planner導入以前は、全条件を盛り込んだ巨大な成果物を毎ターン出力する挙動で、思考が分散され深く考えずに漏れのある提案（システム1的・カーネマン的な浅い出力）がUser AI・監査ノードを素通りする事態があった。これに対応してtask_plannerを導入し、フェーズ・タスク分解によりスコープを区切り、タスクごとに部分成果物を出してintegratorで最後に集約する構想とした。ただしこれには「木を見て森を見ず」（タスク単位に閉じた検討で、タスク間の依存・影響関係を見落とす）リスクがある。

**現状確認（本Issueの起票にあたり確認したコード上の事実）**: `LineageState`にはすでに`phases: list[Phase]`・`current_phase: Phase`があり、`Phase`は`phase_id`/`title`/`description`/`allowed_abstraction_levels`（視座）/`focus_scope`/`expected_time_axis`を持つ。`Agreement`（Decision/Directive/Deliverable）側にも`abstraction_level`（視座）/`scope`/`time_axis`の3軸位置情報と`depends_on: list[str]`（他Agreementへの依存参照）が既に存在する。**つまりフェーズ・視座という概念自体はすでに状態に組み込まれている。** 一方、task_plannerが生成する`tasks`配列（`task_id`/`title`/`description`、`Phase`ネスト下のリスト）は、`state["current_task_summary"]`という単なる出力テキストの先頭200文字への切り詰め（`cela_main.py:2290`）としてしか状態に残らず、`Phase`型自体には`tasks`フィールドが存在しない。SQLite側の`whiteboard_drafts`テーブルには`phase_id`/`task_id`列があるが、これはドラフト保存用でタスク間の依存関係を表現するものではない。

ユーザーが理想として挙げた「Stateにフェーズやタスクを記載し、User AIが議論をナビゲート、あるいはタスク間の依存・影響関係を見ながら進める」を実現するには、タスク粒度の構造化情報（`task_id`単位の状態・依存先task_idなど）を新たに`LineageState`に持たせる必要がある。

**完了条件（未確定、構想段階）:**

- task_plannerの`tasks`出力を`current_task_summary`への切り詰めではなく、構造化された`Task`型（`task_id`/`title`/`description`/`status`/`depends_on`等）として`LineageState`に保持する設計を検討する。
- User AIまたはorchestratorが、あるタスクの成果物・決定が他タスクに与える影響をこの構造化データから参照できるようにする経路を設計する。
- AGENTS.md §5.2の設計ブループリントを提示しユーザー承認を得てから実装する。BL-016・BL-017との優先順位をユーザーと確認する。

**追記（2026-07-20、BL-023 Phase A実装後の実ドライラン`log/2026-07-20/1421`より）:** task_3_1（初期費用の内訳計算）のUser AIレビューで、直前タスクtask_2_3（予約手段の設計）が個別に出した端末保守費・消耗品費（初年度110万円）と、task_3_1の初期費用計上（85万円、経常費用を除外）の差異を、User AIが正しく「初期費用と経常費用の区分」として整理・reconcileする場面があった。一見、BL-023 Phase Aの`depends_on`/`owns_variables`/`verified_facts`機構がクロスタスク整合性チェックとして機能した好例に見えたが、詳細を追うと**実際にはその機構は一切関与していなかった**ことが判明：

1. task_3_1の`depends_on`はtask_planner出力上`["task_2_1"]`のみで、task_2_2・task_2_3は含まれていない。
2. task_2_3の`owns_variables`（`reservation_methods`）が`verified_facts`に保存した値は`{'smartphone_app': 60, 'phone': 30, 'counter': 10}`というチャネル比率のみで、コスト内訳（110万円）はそもそも`verified_facts`に一切保存されていない。
3. この照合が可能だったのは、`generate_user_utterance`が`config["chat_history_window"]`（デフォルト4 = 直近2サイクル分の指示＋回答ペア）分の生の会話履歴をそのままプロンプトに含めており（`cela_main.py:2402`）、task_2_3がtask_3_1の**直前のタスクだった**ため、たまたまこのウィンドウ内に全文が残っていたため。

つまり、クロスタスク数値整合性チェックは現状、`depends_on`宣言に基づく構造化された確定値参照ではなく、`chat_history_window`の隣接性という偶発的な副作用に支えられている。task_planner側の`depends_on`宣言（task_3_1→task_2_1のみ）も、Expertが実際に使った情報（task_2_2のオペレーター数、task_2_3の端末・電話コスト）より実質的に狭く、依存関係グラフ自体が実態を過少申告している。タスクが2つ以上離れる、あるいは間に別タスクが挟まると、この暗黙の安全網は機能しなくなると考えられる。本Issueの「タスク間依存関係が状態に構造化されておらず」という懸念の具体的な実例として記録する。

---

### BL-019: OpenRouterのreasoningパラメータが無効な形式で送られており一切発火していなかった

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [D-017](../decision_log.md#d-017-openrouterのreasoningパラメータ形式を修正しツール付与ノードにも思考ログを追加する)、[decision_lineage.md 論点18](../decision_lineage.md) |

**内容:**

ユーザーから「ログに自己会話のつぶやきを出したい」という要望があり、まず現状把握のため`reasoning_effort`パラメータの挙動を実機検証した。OpenRouter公式ドキュメント（[Reasoning Tokens](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)）を確認したところ、正しいreasoning要求形式はネストした`reasoning: {"effort": ...}`オブジェクトであり、`query_AI`/`_query_AI_live`（Detector/decision extractor/Reflection/Review向け）が使っていたフラットな`create_kwargs["reasoning_effort"] = "low"/"medium"`はOpenRouterの認識しない無効なキーだった。

実機検証（`deepseek-v4-flash`、OpenRouter経由）でこれを確認した：
- 旧実装の形式（フラット`reasoning_effort`）→ レスポンスの`message.reasoning`は常に`null`（サイレントに無視されていた）。
- 正しい形式（`extra_body={"reasoning": {"effort": "low"}}`）→ `message.reasoning`に実際の思考テキストが返ってくる。
- ツール呼び出しを伴うターンでも、`message.content`は`null`のままだが`message.reasoning`には「なぜこのツールを呼ぶか」の思考が入っている（ツール呼び出し前後の「つぶやき」はcontentではなくreasoningフィールドに現れる）。

つまり、Detector/decision extractor/Reflection/Reviewのreasoning_effort設定はこれまで一切効果を発揮しておらず、無駄なコードだった。またExpert/User AI/Resource Arbiterなどツール付与ノードはそもそもreasoning_effortが未設定で、ツール呼び出し前後の思考を可視化する仕組みが存在しなかった。

**2026-07-19完了**: `query_AI`/`_query_AI_live`の該当箇所を修正。
- `create_kwargs["reasoning_effort"]`直接設定をやめ、`reasoning_effort_level`をローカル変数として決定した上で、OpenRouter利用時のみ既存の`extra_body`（プロバイダ優先順位指定）に`"reasoning": {"effort": reasoning_effort_level}`をマージする形に変更。
- 対象ノードを拡張：Detector/decision extractorはlow、Reflection/Reviewはmedium（従来通り）に加え、**ツールが付与されている全ノード（Expert/User AI/Resource Arbiter等）にもlowを付与**（ツール呼び出し前後の思考を可視化する目的）。
- 非ツールパス・ツールループパスの両方で、`getattr(message, "reasoning", None)`が非空の場合に`💭 [{label}] 思考:`としてログ出力する処理を追加。

実機検証（最小コストの実APIコール、`query_AI`経由）で確認: (1) Detector（非ツールパス）で思考ログが正しく出力され、JSON応答も正常。(2) Expertのツールループで、python_repl呼び出し前（「〇〇を検算してから答えを返します」）とツール結果受領後・最終回答前（「7500万円です。結果の数字だけ...」）の両方で思考ログが出力され、最終回答も正常。`py_compile`・`pytest --collect-only`・ゾンビプロセスなしを確認済み。

**完了条件:**

- OpenRouterへのreasoning要求をネストした`extra_body["reasoning"]["effort"]`形式に修正する。（✅ 完了）
- ツール付与ノード（Expert/User AI/Resource Arbiter等）にもreasoning_effort=lowを付与する。（✅ 完了）
- 非ツールパス・ツールループパスの両方で、reasoningフィールドが非空の場合にログ出力する。（✅ 完了）
- 実機検証で思考ログが実際に出力されることを確認する。（✅ 完了）

**2026-07-19追記（tool_calls同梱contentの取りこぼし対策）**: ユーザーから「思考モデルでなくても、`_query_AI_live`のレスポンス内に『ツールで計算する必要がある』的な発言が`content`側に入っているのではないか」という指摘があり、追加で実機検証した。結果、現行モデル（`deepseek-v4-flash`）は`reasoning`要求の有無に関わらず常に`reasoning`フィールドへ思考を返し、`tool_calls`同梱時の`message.content`は常に`null`であることを確認（BL-019の対応で既にこのモデルの思考は捕捉できている）。ただし`_query_AI_live`のツールループは、`tool_calls`が存在する応答の`content`を**無条件に**読み捨てており、モデル・プロバイダが変わって`content`側に発言が同梱されるケースが将来発生しても検知できない構造だったため、防御的に対応した。`msg.content`が非空かつ`tool_calls`も存在する場合に`💬 [{label}] 発言（iter=N, tool_calls同梱）:`としてログ出力する処理を追加。フェイククライアントによるオフラインスモークテストで、`.reasoning`を持たないモデルを模した`content`同梱ケースが正しく印字されることを確認済み。

**2026-07-19追記（実本番ログで確認・小修整）**: ユーザーが本番ドライラン（Expert:requirement_engineer）で実際にこのログを確認。iter=4→5で単位換算ミス（山間部区間の勾配計算で`mountain_dist`をkm単位のままメートル用の式に使い6.25%が6250%と誤表示）を💭思考が自ら検出し、python_replで再計算・修正する自己修正の実例が観測され、F-2.6検算ゲートと思考可視化の組み合わせが意図通り機能していることが実証された。一方、`💬 発言`の見出しだけ出て中身が空白になる箇所（`msg.content`が改行のみの空白文字列で、`if msg.content`の真偽判定を素通りしていたため）が見つかり、`if msg.content and msg.content.strip() and ...`に締めて修正。フェイククライアントによる回帰テスト（空白のみのcontentでは`発言`ブロックが出力されないこと）で確認済み。

---

### BL-020: 中国語系モデル経由でまれに中国語・英語出力になる問題

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | `cela_main.py` `_query_AI_live`, `_inject_japanese_output_directive`（新規） |

**内容:**

本プロジェクトの実運用モデルはOpenRouter経由の`deepseek-v4-flash`（中国語系モデル）であり、まれに出力が中国語（あるいは英語）になることがユーザーのドライラン観測で判明した。個別のプロンプト（Detector/Expert/User AI/Reviewer等、多数のプロンプト生成関数に分散）を1つずつ修正するのは保守コストが高く漏れのリスクもあるため、D-008で確立済みの「`query_AI`への集約」方針に倣い、**全呼び出しが通る単一の集約点（`_query_AI_live`）で日本語出力を強制する**方式を採用した。理想的にはプロンプト自体を英語で書きモデルの理解精度を上げるべきだが（ユーザー言、本Issueの範囲外）、当面は出力言語の強制のみ対応する。

**2026-07-19完了**: `_inject_japanese_output_directive(messages)`を新規実装し、`_query_AI_live`の冒頭（role連続チェックより前）で全`messages`に適用。既存の`messages[0]`が`system`roleの場合はその`content`へ指示文を追記（メッセージ数不変）、`system`roleが存在しない場合は新規`system`メッセージとして先頭に挿入する（既存`system`と重複させず、role連続警告を誘発しない設計）。`query_AI`のRecord/Replayハッシュ計算（`_hash_messages_for_replay`）より後段（`_query_AI_live`内部）で注入しているため、フィクスチャキーの同一性には影響しない。オフライン単体テスト3件（既存system messageへの追記・システムメッセージなし時の新規挿入・いずれのケースでもrole連続警告が発生しないこと）で確認済み。`py_compile`・`pytest --collect-only`にも影響なし。

**完了条件:**

- `query_AI`集約点で全呼び出しに日本語出力の指示を注入する。（✅ 完了）
- 既存system messageとの統合時にrole連続警告を誘発しないことを確認する。（✅ 完了）
- Record/Replayのフィクスチャキー整合性に影響しないことを確認する。（✅ 完了、注入位置が`_query_AI_live`内部のためハッシュ計算対象外）

**スコープ明確化（D-022、2026-07-20）**: BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）で、Decision Extractor・Orchestratorの`reasoning`（BL-019で可視化した「💭思考」）フィールドが中国語で出力されるのを確認した。ただし最終出力（`content`）はすべて日本語であり、本Issueが対象とする「出力言語」の強制自体は機能している。ユーザーは「出力が日本語（最低限英語）であれば良しとする。内部思考言語の強制は無理であり、やるべきではない」と判断し、`reasoning`フィールドの言語はBL-020のスコープ外・対応不要と決定した（D-022）。

---

### BL-021: プロンプト自体の英語化（日本語プロンプトが言語逸脱・理解精度に不利な可能性）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（未着手、設計要） |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [BL-020](issue_backlog.md#bl-020-中国語系モデル経由でまれに中国語英語出力になる問題)、AGENTS.md §12（コード内コメント・自動補完は英語のみという既存方針との整合） |

**内容:**

BL-020（出力言語の強制）対応時、ユーザーから「本当はすべて英語で書いて出力させるべきだが」という指摘があった。現状、本プロジェクトの全プロンプト生成関数（`call_task_planner`・`call_orchestrator`・`call_expert`・`call_detector`・`call_decision_extractor`・`call_resource_arbiter`・`call_reflection`・`call_facilitator`・`call_integrator`・`call_reviewer`・`generate_user_utterance`の計11箇所）は日本語で記述されている。実運用モデル（`deepseek-v4-flash`、中国語系）に対し、非英語（日本語）で指示を与えることは、(a) 学習データの厚みが最も大きい英語に比べて指示の理解精度が落ちる可能性、(b) 日本語プロンプトに対して中国語で応答が返ることがある（BL-020で発生を確認済み、出力強制で対症療法済み）という2点で不利に働きうる。プロンプトを英語化すれば、BL-020の「出力だけ日本語に矯正する」という対症療法ではなく、そもそも言語混線が起きにくくなる可能性がある（最終出力の日本語指定は引き続き必要）。

**完了条件（未確定、要設計）:**

- 対象11関数のプロンプトを英語化する際の方針（一括か段階的か、既存のRecord/Replayフィクスチャへの影響評価を含む）を設計する。
- プロンプト英語化後も出力は日本語を維持する（BL-020の`_inject_japanese_output_directive`はそのまま活用）。
- 英語化前後でDetector/Reviewer等の判定精度・数値検算率に差が出るか、`tests/test_f26_detection.py`相当の指標で比較検証する。
- AGENTS.md §5.2の設計ブループリントを提示しユーザー承認を得てから着手する。11関数を一度に変えるか段階的に変えるかも含め、優先順位をユーザーと確認する。

---

### BL-022: OpenRouterの壊れたレスポンスによる生`json.JSONDecodeError`がD-009の絞り込んだexceptを素通りしクラッシュ

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 依存 | なし |
| 関連 | [D-009](../decision_log.md#d-009-r2ツールループの例外処理を一時的api障害とロジックエラーに区別する)（本Issueの元となった絞り込み）、`cela_main.py` `_query_AI_live` |

**内容:**

継続中の本番ドライラン（`detector`ノード）が、以下のトレースバックで未捕捉クラッシュした。

```
File ".../openai/_response.py", line 268, in _parse
    data = response.json()
File ".../httpx/_models.py", line 832, in json
    return jsonlib.loads(self.content, **kwargs)
...
json.decoder.JSONDecodeError: Expecting value: line 1277 column 1 (char 7018)
```

ユーザー提供の完全なトレースバックを解析した結果、`client.chat.completions.create(...)`の内部（openai SDKがhttpx経由でAPIレスポンスの生ボディを`response.json()`でパースする箇所）で発生していることが判明した。OpenRouter経由の一部プロバイダが、途中で切れた/壊れたレスポンス（約7000文字で内容が終わっている）を返したことが原因。この`json.JSONDecodeError`は`_query_AI_live`の`client.chat.completions.create(**create_kwargs)`呼び出しを包む`except (APIError, APIConnectionError, RateLimitError, APITimeoutError)`（D-009で意図的に絞り込んだ範囲）に含まれておらず、素通りしてLangGraphタスク（`expert_detector`）ごとクラッシュした。

D-009の本来の狙いは「一時的なAPI障害はリトライ、ロジックエラーは即座に伝播させる」という区別だった。プロバイダが壊れたレスポンスを返すのは明確に前者に該当するため、これはD-009の設計判断の見直しではなく、単純な考慮漏れ（絞り込み時にhttpx/openai SDK内部のレスポンス解析失敗というケースを想定していなかった）と判断した。

**2026-07-19完了**: `_query_AI_live`のexceptタプルに`json.JSONDecodeError`を追加：`except (APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError) as e:`。`tc.function.arguments`のパース失敗（ツール引数JSON）は既にローカルなtry/exceptで個別処理済み（L711-719）のため、この追加によって他のロジックエラーを誤って握りつぶす懸念はない。オフラインスモークテスト（フェイククライアント、実LLM呼び出しなし）2件で確認：(1) 1回目の呼び出しで`json.JSONDecodeError`が発生しても既存の指数バックオフリトライで自動復旧し2回目で正常応答を返すこと、(2) 全リトライで発生し続けた場合も既存のAPIError系と同様に例外を再送出せず「サーバー高負荷によるAPIエラー」メッセージへ収束すること。`py_compile`・`pytest --collect-only`にも影響なし。

**完了条件:**

- `_query_AI_live`の外側exceptに`json.JSONDecodeError`を追加する。（✅ 完了）
- 既存のツール引数パース失敗処理（ローカルtry/except）との重複・誤動作がないことを確認する。（✅ 完了）
- オフラインスモークテストでリトライ・最終フォールバックの両経路を確認する。（✅ 完了）
- 実LLM環境での本番再ドライランで同種のクラッシュが再発しないことを確認する。（未実施、次回ドライラン待ち）

---

### BL-023: task_plannerの分解粒度が粗く、複合タスクの検証コストが乗算的に増大する

| 項目 | 内容 |
|------|------|
| 状態 | `open`（設計完了、実装未着手。Phase A→Phase Cの順で着手する方針決定済み、[D-020](../decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)） |
| 優先度 | P1 |
| 依存 | なし（BL-002の指標C計測はむしろ本Issue完了後に着手すべき）。Phase B（reflection/facilitatorへの森レベル整合性の委譲）のみBL-005の解消が前提だが、Phase A・Cの着手には不要（D-020） |
| 関連 | [BL-002](issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（別軸、下記参照）、[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（Phase Bの前提、非ブロッカーとして後回し、[D-020](../decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)）、[D-018](../decision_log.md#d-018-r4ホワイトボード編集方式はコーディングエージェント方式遅延取得機械的照合パッチを採用する)、`log/2026-07-19/2056/log_no_prompt.md` |

**内容:**

指標C（収束性とコストのトレードオフ、BL-002）の実測に着手しようとした際、ユーザーが「もう少しタスク・スコープ分解・制御をしないと検算の嵐で議論が進まない」と指摘したことから起票。

今日のドライラン（`log/2026-07-19/2056`）のtask_1.2「予算制約の明文化」で実際に観測された数値：Expertは1回の試行で5〜8回のpython_repl呼び出し、Detectorは1回の判定で3〜7回のpython_repl呼び出しを行い、これが同一タスクへの差し戻しとして3ラウンド以上繰り返された。task_1.2は「車両台数の導出」「初期費用の内訳」「年間ランニングコスト」「感度分析」という、本来独立に検証可能な複数の主張を1つのExpert発言・1つのDetector判定単位に束ねていた。

この粗い分解粒度が、R4未実装（差分パッチなし、全文書き直し方式）と組み合わさることで問題を増幅させている。Detectorがバンドル内の1箇所（例：感度分析の1数値）にだけ疑義を出しても、Expertはバンドル全体をゼロから作り直す必要が生じるため、**検証コストが「間違いの数」ではなく「バンドルの大きさ」に比例して乗算される**。今日観測された3ラウンド以上の差し戻しは、実質的に同じ4項目をゼロから作り直す作業を3回以上繰り返したことに相当する。

この状態のまま指標C計測（「R1版/R2版を最低5試行ずつ比較」）を実施すると、(a) 実行時間・トークン消費が非現実的な規模になる、(b) 測定される差が「R1とR2の本質的な違い」ではなく「タスク分解が粗いことによる検証コストの乗算」に支配され、指標として意味を持たない、という二重の問題がある。これはD-002が指摘した「F-2.6検算ゲートなしでの指標A・B・C計測はフェアでない」という原則と同種の構造であり、今度は「粒度の粗いタスク分解のままでの指標C計測はフェアでない」という新たな前提条件として扱うべきである。

**BL-018との違い**: BL-018はタスク**間**の依存関係の構造化（Task Aの成果物・決定がTask Bにどう影響するかの追跡）を扱う。本Issueはタスク**単体**の分解粒度（1つのタスクに独立検証可能な複数の主張が束ねられていないか）という別軸の問題であり、混同しないこと。

**ユーザー判断**: 「最初にタスク分解を詰めたほうがよさそうですね。後にすべて効きます」——指標C計測（BL-002）・R4の差分パッチ設計・BL-018のいずれよりも先に、本Issueに最優先で着手する方針。

**追加分析（真の増幅源はUser AI側にもある）:**

同ログ（1517〜1545行）を精査した結果、task_1.2のtask_planner側の元記述（「予算制約の明文化…費用項目リストを作成する」）自体は粒度として大きく破綻していないことが判明した。実際にExpertへ渡された指示文を肥大化させていたのは、`generate_user_utterance`（User AI＝発注者役）である：task_1.2には無かった「車両台数の論理的算出」（本来task_1.1の依存項目）を自発的に追加し、初期費用6項目・年間ランニングコスト6項目・収支不等式と合わせて計4系統の独立検証可能な主張を1回の発話に束ねていた。原因は`generate_user_utterance`のsystem promptが「妥協を許さないプロジェクトオーナー」として具体的数値を強く要求する一方（`cela_main.py` 2118〜2123行）、1回の発話に詰め込んでよい独立検証可能主張の数の上限や、task_planner定義のタスク範囲を超えて他タスクの依存項目を前倒し要求しないというガードレールを一切持たないため。したがって本Issueの設計対象は**task_plannerのみでなく`generate_user_utterance`（instruction生成）も含める**。

**追加分析（3点セットの構造的依存、2026-07-20）:**

ユーザーとの議論により、粒度是正だけでは「木を見て森を見ず」の副作用（依存関係を無視した局所最適化）を招く危険があることが判明。是正には以下3点をセットで設計する必要がある：

1. **共有変数の一元所有**（[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)と直結）: 車両台数のように複数タスクにまたがる数値は、所有タスク（例：task_1.1）を1つに固定し、下流タスク（task_1.2）はそれを**既知の定数として受け取り、再導出しない**。task_planner出力スキーマに`depends_on`/`owns_variables`相当のフィールドが必要。
2. **予算のトップダウン・カスケード**: 全体予算をワーカーが毎回自力で帳尻合わせするのではなく、フェーズ／タスク単位のサブ予算枠を先に配分してから渡す。**ただし、このサブ予算枠は絶対制約ではなく仮説（hypothesis）として扱うこと** — ユーザーが指摘した通り、現実の（特に日本の）委託開発で頻発する「無理な予算枠を現場に押し付け、しわ寄せを後工程に送る」病理を再現してはならない。Expertが代替案を尽くした上で「このサブ枠は構造的に非現実的」と誠実に結論した場合、それをDetectorの`major`（手抜き）として即座に差し戻すのではなく、`resource_arbiter`への調停提起として扱う明示的なエスカレーション経路が必要。現行のExpert system prompt（「制約緩和を提案しないでください」「諦めないでください」、`cela_main.py` 1379〜1384行）は、この誠実なフィージビリティ判断とただの思考停止を区別していないため、文言の見直しも本Issueのスコープに含める。
3. **森レベルの整合性はreflection/facilitatorに戻す**（[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)と直結）: 現状BL-005によりreflection/facilitatorが実質発火不能なため、User AIが個々のタスク指示ごとに森レベルの整合性チェックを肩代わりし、結果的に指示文が肥大化している。BL-023（粒度是正）とBL-005（reflection/facilitator復旧）は並行して対応しないと、粒度を細分化してもUser AIが別の形で森の番人役を抱え込み直す可能性が高い。

**着手順序（[D-020](../decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)、2026-07-20決定）:**

実ログで直接実証された直接原因（Phase A）と、ユーザーが強く懸念する将来リスク（Phase C）を優先し、確度の低い間接要因（Phase B＝BL-005）は非ブロッカーとして後回しにする。実装はPhase A（影響範囲小・確度の高い原因への対応）を先行させ、動作確認後にPhase C（新規機構・影響範囲大）に着手する。

**完了条件（Phase A、`done`——2026-07-20実装、実機再ドライラン待ち）:**

- ~~task_plannerのプロンプト・出力スキーマを見直し、各タスクに`acceptance_criteria`（独立検証可能な主張を上限個数で列挙）・`depends_on`/`owns_variables`（他タスクとの変数依存）を持たせる設計を検討する。~~ → `done`（`call_task_planner`のプロンプト・`fallback_phase`を拡張、`Task`型新設）
- ~~`generate_user_utterance`のsystem promptを見直す。単なるガードレール文の追加ではなく、「質・厳密さへの非妥協性」（維持）と「スコープの広さへの非妥協性」（1回の発話はtask_plannerが定義した当該タスクの`acceptance_criteria`の範囲に厳密に限定し、他タスクの依存項目の前倒し要求を禁止）を明確に分離した書き換えを行う。~~ → `done`（現在タスクJSON・依存確定値・未充足criteriaを注入する形に再設計）
- BL-024（`current_task_id`の一元管理）、`verified_facts`共有ストア（owns_variables実現）、Detectorの`criteria_status`充足チェック、Agreementの`Deferred`ステータスもあわせて実装済み（詳細設計`cela_phase2_design_BL023_task_state.md`）。
- 細分化のしすぎ（タスク数増大によるorchestrator/User AIのオーバーヘッド増加、タスク間依存関係の複雑化）とのバランスは、実機ドライランでの観測により検証する（未実施）。
- 対応後、同種のタスク（task_1.2相当）で差し戻しラウンド数・ツール呼び出し回数が実際に減ることをオフライン・実機の両方で確認する。オフラインスモークテスト（DBマイグレーション・`verified_facts` upsert・`_get_current_task`・`_resolve_task_transition`のフェイルクローズ）は合格。**実機での確認は未実施**。

**完了条件（Phase C、Phase A完了・動作確認後に着手）:**

- フェーズ／タスク単位の予算サブ枠を事前配分する仕組みを検討する。ただし**サブ枠は仮説であり絶対制約ではない**ことを明示し、Expertが誠実な根拠に基づき非現実的と判断した場合は`resource_arbiter`への構造化エスカレーションとして扱う経路を設ける。
- Expert system promptの「制約緩和禁止」文言を見直し、思考停止と誠実なフィージビリティ判断（検討済み代替案・却下理由を明示した上での`resource_arbiter`への調停提起）を区別できるようにする。
- `resource_arbiter`（`arbiter_node`）に、Detectorの数値矛盾検知とは別の「構造的フィージビリティ提起」ルートを追加する（詳細ルーティング設計はBL-017と合わせて検討する）。

**完了条件（Phase B、BL-005解消後に別途着手・本Issueのブロッカーではない）:**

- BL-005（reflection/facilitator復旧）解消後、森レベルの整合性チェックをUser AIから reflection/facilitator へ委譲する設計を検討する。

**共通完了条件:**

- 各Phaseの実装前に、AGENTS.md §5.2の設計ブループリントを提示しユーザー承認を得る。
- 指標C（BL-002）の本格計測は、少なくともPhase Aの対応が完了してから着手する方針とする。

**詳細設計**: [`docs/design/r1_r2_r3b_core/cela_r2_design_BL023_task_state.md`](../r1_r2_r3b_core/cela_r2_design_BL023_task_state.md)（BL-024・issue_backlog相当のDeferredステータス・traceability相当のacceptance_criteria充足チェック・確定値共有ストア`verified_facts`を含む統合設計）。

---

### BL-024: current_phaseが初期化後フリーズし、task_id単位の状態追跡が存在しない

| 項目 | 内容 |
|------|------|
| 状態 | `done`（BL-023 Phase Aと同時に実装。オフラインスモークテスト合格、実LLM再ドライラン待ち） |
| 優先度 | P1 |
| 依存 | なし（BL-005の`turn_count`凍結とは独立した別のフリーズバグ） |
| 関連 | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)（本Issueの前提）、[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（同型の凍結バグ、別変数）、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)、`docs/design/phase2/cela_phase2_design_BL023_task_state.md` |

**内容:**

BL-023 Phase A（「User AIの発話を現在のタスクのacceptance_criteriaの範囲に限定する」）の設計中に発見。`state["current_phase"]`は初期化時（`phases[0]`）に一度セットされるのみで（`cela_main.py:2300`）、以降どこからも更新されるコードパスが存在しない。**BL-005（`turn_count`凍結）と同型の「初期化後フリーズ」バグ**である。`task_id`単位の状態追跡に至っては最初から存在せず、`current_task_summary`（`cela_main.py:2362`）はExpert出力の先頭200文字を切り詰めた表示用テキストにすぎない。

`decision_extractor`のプロンプト（`cela_main.py:1754`）は各抽出アイテムに`phase_id`をLLMに出力させているが、`decision_extractor_node`（2469-2470行）はDBへの書き込みに使うのみで、`state["current_phase"]`へは一切書き戻していない。過去に`generate_user_utterance`側で`phase_id`/`task_id`を強制JSON出力させる設計が試みられた形跡があるが（2154-2164行、コメントアウト済み）、無効化の理由は本プロジェクトのドキュメントに記録がなく不明（AGENTS.md「no guessing」原則により、この方式は復活させない）。

**完了条件:**

- ~~`decision_extractor_node`を`state["current_phase"]`/新設`state["current_task_id"]`の唯一の書き手とする（詳細設計は`cela_phase2_design_BL023_task_state.md` 2.3節）。~~ → `done`（`_resolve_task_transition`実装、`decision_extractor`に`advances_to_phase_id`/`advances_to_task_id`を追加）
- ~~LLMが返すphase_id/task_idがtask_planner確定済みの`phases`/`tasks`に実在しない場合は書き込みを拒否するフェイルクローズ検証を実装する。~~ → `done`
- ~~オフラインスモークテストで、不正なIDが与えられた場合に状態が変化しないことを確認する。~~ → `done`（不正phase_id/task_idで状態不変、正当なIDでのみ更新されることを確認）
- 実LLM実行での再ドライラン確認が残タスク。

---

### BL-025: Expertがタスク境界を越えて他タスクのowns_variablesまで回答し、ツールループが非収束クラッシュする

| 項目 | 内容 |
|------|------|
| 状態 | `done`（①②とも実装。オフラインスモークテスト合格、実LLM再ドライラン待ち） |
| 優先度 | P1 |
| 依存 | BL-023 Phase A（`Task`型・`acceptance_criteria`/`owns_variables`スキーマ、`_get_current_task`）が前提 |
| 関連 | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、`log/2026-07-20/1204/log_no_prompt.md` |

**内容:**

BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）で、`generate_user_utterance`（User AI）はtask_1_1のacceptance_criteria範囲を守れていたことを確認した一方、`call_expert`（Expert）側にはタスク境界を守るガードレールが存在しないことが判明した。

具体的には、task_1_1（需要モデル・地理的制約・予算の**文書化のみ**が範囲）への差し戻し後の再試行で、Expertはtask_2_2（車両選定）が`owns_variables`として所有すべき「必要車両台数（2台 vs 3台の比較）」「システム費用の内訳配分」を独自に計算し（iter=9、`log_no_prompt.md:2290-2377`）、さらにtask_2_2の前提データである「主要拠点間の移動時間・サイクルタイム」まで計算した（iter=10、`log_no_prompt.md:2379-2416`）。これによりMAX_TOOL_ITER=10を使い切り非収束クラッシュした（`log_no_prompt.md:2428`）。

原因は2つ複合していると分析：
1. **ガードレール不在**: `call_expert`には`generate_user_utterance`のような「現在タスクのacceptance_criteria/owns_variablesの範囲に限定し、他タスクの領域まで答えない」という明示的な指示がない。
2. **コンテキストの持続的な誘惑**: `_query_AI_live`のツールループは、iter=1〜10まで同一の`system_prompt`（5フェーズ全部の`tasks` JSON、全DB agreements）を毎回再送信する。Expertが自問自答している最中も、他タスクの詳細情報が常に視界に入り続けるため、関連性から踏み込みたくなる構造的誘因がある。

さらに、Detectorが指摘したのは予算内訳の矛盾1点のみだったにもかかわらず、差し戻し後のExpert（iter=1〜10）は需要モデル・地理的制約など既に問題なかった箇所も含めてレポート全体を再検算しており（R4未実装＝差分パッチなしによる全文書き直しコスト）、これがBL-023の「バンドルの大きさに比例した検証コスト乗算」を、task_planner粒度ではなく「Expertの全文書き直し」という別経路で再現していることも確認した（この点はR4のスコープであり、本Issueでは対応しない）。

**採用する2案（ユーザー承認、両方実装）:**

- **①（言って聞かせる）**: `call_expert`のsystem_promptに、現在タスクの`acceptance_criteria`/`owns_variables`のJSONを注入し、「他タスクの`owns_variables`に該当する内容は新たに算出・提案しないこと」という明示的なガードレールを追加する（`generate_user_utterance`と対称的な設計）。
- **②（見せない）**: `_query_AI_live`のツールループに`light_system_prompt`引数を追加し、iter=1完了後（iter=2以降）は`loop_messages[0]`（system message）を、現在タスクの情報のみに絞った軽量版に差し替える。`call_expert`が軽量版system_promptを構築して渡す。全体計画の把握はiter=1で完了しているため、以降の自問自答フェーズでは不要という考えに基づく。

**完了条件:**

- ~~①②とも実装し、`python -m py_compile`・オフラインスモークテストで動作確認する。~~ → `done`（`_build_task_scope_context`ヘルパーを`generate_user_utterance`と共通化し`call_expert`にも適用。`_query_AI_live`に`light_system_prompt`引数を追加し、`_JAPANESE_OUTPUT_DIRECTIVE`を定数化。フェイククライアントによるオフラインスモークテスト2件（①system_promptへのガードレール注入確認、②iter=1はフル文脈・iter=2以降は軽量文脈に差し替わることの確認）はすべてPass）
- 実機再ドライランで、Expertが他タスクの`owns_variables`領域に踏み込まなくなることを確認する（未実施）。
- ~~②の軽量化がRecord/Replayのフィクスチャキー整合性に影響しないことを確認する~~ → `done`（`_hash_messages_for_replay`は呼び出し時点の`messages`引数を使用し、軽量化はツールループ内部iter=2以降でのみ発生するため、フィクスチャキーに影響しない設計であることをコードレベルで確認）。

---

### BL-026: 専門家名の固定配列（valid_experts）を撤廃し、orchestratorの自由記述に変更

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [D-024](../decision_log.md#d-024-orchestratorの専門家選択を固定16種配列から自由記述に変更する) |

**内容:**

ユーザーが「オーケストレーターノードで専門家を選び、専門家ごとに個別のグラフを作るべきかと思っていたが、現在の動きではその必要もない？」と提起したのを受け、`call_orchestrator`/`call_expert`/グラフのルーティングを確認したところ、以下が判明した。

- `state["selected_expert"]`は`call_expert`の`expert_name`引数としてプロンプトに埋め込まれる（「あなたは有能な{expert_name}の分野の専門家です」）だけで、`call_expert`内部で`expert_name`により処理が分岐する箇所は一切ない。
- グラフの`add_conditional_edges`も`selected_expert`の値では分岐しておらず、専門家ごとの個別ノード・個別グラフは最初から存在しない（単一の汎用`expert_node`のみ）。
- つまり固定16種配列（`valid_experts`）は、実際には何のアーキテクチャ上の役割も果たしておらず、orchestratorの選択肢を不必要に狭めていただけだった。実ドライランのログでも、リストのどれにも綺麗に当てはまらないタスクで選定に無駄な思考コストが発生していた（「requirement_engineerかboundary_checkerかnumerical_allocatorか」の長い逡巡）。

ユーザーは「なぜ固定配列にしたか忘れてしまったが、v10以前に情報を構造化していなかったツケ。現状謎の足かせになり得ているので自由記述にし、フォールバックは仕込む。専門家ごとのノード構造は必要が生じたらそうする（まだMVPも一通り動いていない）」と判断した。

**完了条件:**

- ~~`call_orchestrator`のプロンプトから固定16種配列を削除し、タスクに即した専門家の肩書きを自由記述で生成させる。~~ → `done`
- ~~`valid_experts`による検証を撤廃し、空文字・空白のみの場合のみ汎用フォールバック（「プロジェクト全般アドバイザー」）にする軽量フォールバックに置き換える。~~ → `done`
- ~~オフラインスモークテストで、自由記述の専門家名がそのまま通ること、空・不正JSON時にフォールバックすることを確認する。~~ → `done`（フェイククライアントで3ケース確認）
- 専門家ごとの個別ノード・個別グラフ構造は、実際にその必要が生じた時点で再検討する（現時点では非対応、MVP未完成のため時期尚早と判断）。

---

### BL-027: `cela_main.py`のロガーがimport時点で無条件起動し、本番`log/`配下にテスト実行の痕跡が混入する

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [D-025](../decision_log.md#d-025-multiloggerの起動を__main__ガード内に限定する) |

**内容:**

ユーザーから実ドライラン中のログ（`log/2026-07-20/1421`）のレビューを依頼された際、同時刻帯に`log/2026-07-20/1455`・`1458`という不自然な小さいログフォルダが作られていることを発見。

原因は`cela_main.py:116`（修正前）の`sys.stdout = MultiLogger()`が、`if __name__ == "__main__":`の外＝モジュールのトップレベルに置かれていたこと。これにより`import cela_main`するだけで即座に`log/日付/HHMM/`が新規作成され、プロセスの標準出力が丸ごとそこにリダイレクトされる。

BL-025/BL-026の検証用にこのセッション内で実行したオフラインスモークテスト（`smoke_orchestrator_freeform.py`ほか、いずれも`import cela_main as m`で始まる）が、まさにこの経路で1455・1458を生成していた。1421の実ドライランが進行中の裏で、無関係なテスト出力（フェイク専門家名・`goal="テスト目標"`のダミープロンプト）が本番`log/`に混入する事故となった。

**完了条件:**

- ~~`sys.stdout = MultiLogger()`を`if __name__ == "__main__":`ブロック内（`TARGET_GOAL`定義の直前）に移動し、importのみでは発火しないようにする。~~ → `done`
- ~~修正後、`import cela_main`のみを行っても`log/`配下に新規ディレクトリが作られないことを確認する。~~ → `done`（`os.listdir`差分で新規ディレクトリ0件を確認）
- ~~`python -m py_compile cela_main.py`で回帰がないことを確認する。~~ → `done`
- ~~誤って作成された`log/2026-07-20/1455`・`1458`を削除する。~~ → `done`

---

### BL-028: MAX_TOOL_ITERを10→15に引き上げ（クラッシュ回避を優先）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | [BL-014](issue_backlog.md#bl-014-本番ドライランexpertノードで非収束クラッシュ-3つの複合原因)（5→10へ変更した際の経緯）、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする) |
| 関連 | [D-026](../decision_log.md#d-026-max_tool_iterを10から15へ引き上げる) |

**内容:**

`log/2026-07-20/1421`の実ドライランレビュー中、task_2_2の運行スケジュール設計でExpert(logistics_manager)の1回目の提案が`iter=10, tool_calls=9`とMAX_TOOL_ITER上限ぎりぎりで完了していたことが判明（クラッシュはしなかったが、余地は0だった）。BL-025（スコープガードレール・コンテキスト軽量化）はタスク境界を越えた検証コストの増大は防げるが、1タスク自身の`acceptance_criteria`を満たすための正当な段階的検算だけでも上限に迫るケースがあることを示している。

ユーザーは「tool コール上限は15回にあげましょう。今の時点ではクラッシュさせないのが先決です」と判断。検証コストの根本的な削減（Phase C予算カスケード、R4差分パッチ等）より先に、まずクラッシュ耐性を優先する方針。

**完了条件:**

- ~~`MAX_TOOL_ITER`を10から15に変更する。~~ → `done`
- ~~`python -m py_compile`で回帰がないことを確認する。~~ → `done`
- 【注意】この変更は`cela_main.py`のソースコードに対するものであり、レビュー時点で実行中だった`log/2026-07-20/1421`のドライランプロセスはすでにモジュールをメモリにロード済みのため、この変更の恩恵は受けない（次回起動分から有効）。

---

### BL-029: `owned_variable_values`に`content`の全文がそのまま混入する事故を修正

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)（`owned_variable_values`/`verified_facts`の導入元） |
| 関連 | [D-027](../decision_log.md#d-027-owned_variable_valuesはcontentと目的が異なることをプロンプトで明記する)、[BL-030](issue_backlog.md#bl-030-owned_variable_valuesを依存関係参照専用の要約レポートとして独立フィールド化する拡張案) |

**内容:**

`log/2026-07-20/1421`ドライランのtask_2_2で、`verified_facts`の`operation_schedule`が2回保存されているのを発見。1回目（却下された旧版）は`3台体制、運行時間8:00-20:00、ピーク時山間部27分ヘッドウェイ、中心部15分以内配車、オフピーク2台運用、夜間1台運用`という狙い通りの簡潔な確定値だったが、2回目（承認された修正版）は**レポート全文（数千文字のMarkdown）** がそのまま`owned_variable_values`の値として保存されていた。

原因を`call_decision_extractor`のexpert向け`role_instruction`で確認したところ、`Deliverable`の`content`フィールドには「絶対に要約しないこと」という明示指示がある一方、`owned_variable_values`側にはその区別がなかった。実際のログ内のDecision Extractorの思考でも「レポートの要約ではなく...値としてレポート全文を入れるのは冗長だが、他に適切な表現がない」と、`content`向けの「要約禁止」指示が`owned_variable_values`側に誤って波及していたことが確認できた。

ユーザーに確認したところ、`content`の「要約禁止」は意図的な設計（部分成果物を後で製本・合成するため、情報を削がない）であり、この方針自体は変更しない。一方`owned_variable_values`は本来、他タスクが`depends_on`を通じて参照する際に読む簡潔な要約であるべきで、`content`とは目的が異なる。ユーザーは「Aは実装」と、プロンプトへの目的明記による修正を承認した。

**完了条件:**

- ~~`call_decision_extractor`のexpert向け`role_instruction`に、`owned_variable_values`は`content`とは別物であり簡潔な要約（全文コピー禁止）にすべきことを明記する。~~ → `done`
- ~~`python -m py_compile`で回帰がないことを確認する。~~ → `done`
- 実機再ドライラン確認は未実施（次回以降のtask実行で、`owned_variable_values`が簡潔に保たれるか要観察）。

---

### BL-030: `owned_variable_values`を依存関係参照専用の「要約レポート」として独立フィールド化する拡張案

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |
| 依存 | [BL-029](issue_backlog.md#bl-029-owned_variable_valuesにcontentの全文がそのまま混入する事故を修正) |
| 関連 | [D-027](../decision_log.md#d-027-owned_variable_valuesはcontentと目的が異なることをプロンプトで明記する) |

**内容:**

BL-029の議論から派生した設計アイデア。現状の`owned_variable_values`はDeliverable抽出と同一の`call_decision_extractor`呼び出し内で、プロンプト指示のみによって簡潔さを担保している（BL-029で修正）。ユーザーからは「依存関係で参照するように、要約レポートを別途作ってもよいかもしれません」との提案があった。

また、ユーザーによれば、実装フェーズが進むと承認・合意・成果物は各ノード自身がファイルに直接出力する設計に移行する予定であり、`decision_extractor`は将来的に補助的な役割に縮小していく。したがって`owned_variable_values`を独立スキーマフィールドとして切り出す設計は、その将来のノード自身のファイル出力機構の設計と合わせて検討するのが望ましく、現時点では単体で先行実装しない。

**完了条件（未着手）:**

- ノード自身がファイル出力する設計（将来）の検討時に、依存関係参照専用の要約フィールド（`owned_variable_values`ないし後継の仕組み）の設計をあわせて見直す。
- 現時点ではBL-029のプロンプト修正で当面の実害を止めており、本Issueはブロッカーではない。

---

### BL-031: プロンプトのプレフィックスキャッシュヒット率を上げる構造整理（コスト最適化）

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [D-028](../decision_log.md#d-028-プレフィックスキャッシュヒット率改善はmvp完成後のコスト最適化枠として据え置く)、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（`light_system_prompt`によるコンテキスト軽量化、本Issueと同根の関心） |

**内容:**

ユーザーがOpenRouterのダッシュボードで直近24時間の実績を確認したところ、4.6Mトークン・キャッシュヒット率19.7%・コスト$0.65だった。単価自体は格安モデル（`deepseek-v4-flash`系）を使っている前提で妥当だが、キャッシュヒット率19.7%は本日のログレビューで確認した以下の実態と整合する：

- 各ノードへ再送される「プロジェクトの合意・決定事項・検討状況DB」（Recent Decisionsの再掲）テキストは、Decisionが1件増えるたびに末尾の内容が変わる。
- 5フェーズ分のtask_planner出力JSON全体もほぼ全ノードのプロンプトに毎回まるごと埋め込まれている。
- BL-025で軽量化した`light_system_prompt`はツールループ2周目以降にのみ適用され、1周目やツールを使わないノード（Detector以外の多くの呼び出し）では従来通りのフルコンテキストが送られている。

これらの可変ブロックがプロンプトの先頭付近に混在していると、プレフィックスキャッシュ（先頭からの一致がキャッシュヒットの条件になる方式が一般的）が毎ターン壊れやすい。プロンプト構造を「実行を通じて不変の固定部分を先頭に、ターンごとに変化する部分（Recent Decisions・現在のタスク状態等）を末尾に」整理できれば、ヒット率の改善余地がある。

ユーザーからは「エージェントアーキテクチャを洗練させていくと、そこそこの性能の格安モデルでも十分動き、成果が出せると感じた」という所感があり、本Issueはその延長線上にあるコスト最適化の一項目として記録する。現状すでに$0.65/4.6Mと十分安価でMVPも未完成のため、緊急の優先度ではない。

**完了条件（未着手、構想段階）:**

- 各ノードのプロンプト構築箇所（`call_orchestrator`/`call_expert`/`call_detector`/`call_decision_extractor`/`generate_user_utterance`等）で、「不変の固定部分」と「ターンごとに変化する部分」を洗い出し、プロンプト内での配置順を整理する設計を検討する。
- MVP完成・Phase C（予算カスケード）着手後など、コスト最適化に着手するタイミングであらためて優先度をユーザーと確認する。

---

### BL-032: Deliverable承認時に、同一task_idの兄弟Decisionが永久にProposedのまま取り残される

| 項目 | 内容 |
|------|------|
| 状態 | `open`（設計確定・実装承認済み、未着手） |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | [D-029](../decision_log.md#d-029-同一task_idの兄弟decisionへの承認カスケードをdetector判定でガードして実装する)、[BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)（`task_criteria_status`/`owns_variables`基盤） |

**内容:**

ユーザーが実ドライラン（`log/2026-07-20/1421`）のプロンプト中の「合意・決定事項・検討状況DB」の一部を確認したところ、既に完了しているフェーズのDecisionが「🤔[提案/検討中]」のまま多数残っていることに気づいた。

具体的には、task_2_3（予約手段の設計）で親のDeliverable「予約手段の設計（スマホ以外） レポート」は`✅[確定合意]`まで進んでいるのに、同じAgent提出から抽出された4件のDecision（予約チャネルの按分比率、電話予約システムの設計、対面相談所端末の設計、運用コスト概算）は`CREATE/Proposed`のまま一度も`UPDATE`されておらず、以降の全ターンで「Recent Decisions」に🤔として再掲され続けていた（`log_no_prompt.md`内で同じ4件が10回以上繰り返し出現）。

**原因分析:** `call_decision_extractor`のUser直後`role_instruction`（`cela_main.py:1802-1833`）は承認時の`target_topic`を単数でしか指定させておらず、Agentの直前提出に含まれる兄弟トピック全部を承認済みにする指示がない。比較として、task_2_1では「task_2_1 必要車両台数の算出レポート」と「最適導入台数は3台」の両方が承認されていたが、これはUser AIの承認文がたまたま「最適導入台数は3台」という名前に直接言及していたためLLMが拾えただけであり、命名に依存する偶発的な挙動だった。

**設計上の懸念（ユーザー指摘）:** 単純に「同一task_idなら全部承認」と機械的にカスケードすると、本当にレビュー漏れがあった項目まで握りつぶしてしまうリスクがある。

**採用した設計:** `detector_node`が`decision_extractor_node`より先に実行され、`state["constraint_issue"]`と`state["task_criteria_status"][task_id]`（BL-023のacceptance_criteria充足チェック）を同一ターン内で既にセットしていることを確認。これを利用し、`decision_extractor_node`が「同一task_idのDeliverableがApproved」を検出した際、**同ターンのDetector判定が(1)`constraint_issue`が`major`でない、かつ(2)`task_criteria_status[task_id]`が全て`true`、の両方を満たす場合のみ**、同task_id配下の他のProposed項目を機械的にカスケード承認する。いずれかを満たさない場合はカスケードせず、現状のProposedのまま残す（＝本当に未検討の疑いがある場合は隠蔽しない）。

**完了条件（未着手）:**

- `decision_extractor_node`に、同一task_id内の「Deliverable Approved」検出後、Detector判定（`constraint_issue`/`task_criteria_status`）が清浄な場合のみ兄弟Proposed項目をカスケード承認するロジックを実装する。
- `python -m py_compile`で回帰がないことを確認する。
- オフラインスモークテストで、(a) 清浄な判定時にカスケードが発火すること、(b) `constraint_issue=major`または`criteria_status`に`false`がある場合にカスケードが発火しないこと、の両方を確認する。
- 将来的な拡張として、ユーザー提案の「completion宣言時にDetectorへ未検討事項の整理・差し戻しをさせる」仕組みは、より大きな設計（completion宣言という概念の新設）を要するため別途検討する。

---

### BL-033: Expertがpython_repl未使用のまま「検算完了」と虚偽申告できる/F-2.6監査フラグに強制力がない

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [D-030](../decision_log.md#d-030-expertの検算未実施を検出しdetectorへ提示しつつ複合失敗のみ強制差し戻しする) |

**内容:**

ユーザーが実ドライラン（`log/2026-07-20/1421`）のtask_5_2（エッジケースBの責任分界点明確化）で、Expert(legal_advisor)が`iter=1, tool_calls使用=0回`——python_replを一度も呼ばずに——「全ての検算が完了した。以下、最終報告を提出する。」と、過失割合や保険料試算などの数値を含む長大なレポートを提出していたことを発見した。F-2.6監査フラグ（`⚠️ python_replを一度も使わずに応答しました`）はログに記録されていたが、これは単なる警告表示であり何の強制力もなかった。

幸い、後段のDetectorが独自にpython_replで同じ数値を再検算し、すべて整合していたため実害はなかった（Expertの自己申告ではなくDetectorの独立検算が実質的な安全網として機能した）。ただし、Detectorの検算がもし省略された場合、未検証の数値がそのまま承認される可能性があるという設計上の穴が露呈した。

**検討の経緯:** ユーザーは当初「このフラグが出た場合、強制的に差し戻すか」を提案したが、同時に「本当に計算が不要な思考の場合もあり、無限ループ化のリスクがある」と自ら懸念を指摘した。これを受け、単純な強制差し戻しではなく、(1)弱いナッジ（Expertの実行記録をDetectorに提示し自己申告を鵜呑みにさせない）と(2)狭いハードゲート（ExpertとDetectorの両方が同一ターンでpython_repl未使用だった場合のみ強制差し戻し）の2段構えを提案し、ユーザーが「両方やりましょう」と承認した。さらにユーザーから「AIが呼んだ直前の一連のpythonスクリプトを保存できないか」「Detectorではまず自分で検算し、その後Expertのスクリプトを見て（あるいは実行して）整合することを確認」という追加提案があり、これを設計に統合した。

**実装内容:**

1. **python_repl実行記録の保存**: `_query_AI_live`のツールループ内で、実行した`python_repl`のcode/resultを`python_calls_log`に蓄積し、モジュールレベルの`_LAST_PYTHON_CALLS`バッファへ書き込む（`get_last_python_calls()`で取得可能）。`query_AI`の呼び出しごとにバッファをリセットするため、直前の呼び出し分のみが残る。
2. **stateへの伝播**: `expert_node`が`call_expert`実行後に`state["expert_last_python_calls"] = get_last_python_calls()`を保存し、次のDetector呼び出しから参照可能にする（`LineageState`に新フィールドを追加）。
3. **Detectorへの提示（弱いナッジ）**: `call_detector`が`state["expert_last_python_calls"]`を確認し、記録があればコード・結果を提示した上で「まず自分で独立して検算し、その後この記録と整合するか確認せよ」と指示。記録が空（Expertがpython_repl未使用）の場合は「Expertの自己申告を鵜呑みにせず必ず自分で検算せよ」という警告を注入する。
4. **複合失敗ガード（狭いハードゲート）**: `detector_node`で、Expertの成果物を評価するターン（`target_role=="assistant"`）に限り、`state["expert_last_python_calls"]`とDetector自身の`get_last_python_calls()`の**両方**が空だった場合のみ、`constraint_issue`を強制的に`"major"`に上書きしてフェイルクローズする。どちらか一方でもpython_replを使用していれば発火しない（正当な「計算不要」ケースを巻き込む無限ループを回避）。

**完了条件:**

- ~~`_query_AI_live`にpython_repl実行記録の蓄積とモジュールレベルバッファへの保存を実装する。~~ → `done`
- ~~`expert_node`が`state["expert_last_python_calls"]`へ記録を保存するようにする。~~ → `done`
- ~~`call_detector`のプロンプトにExpertの実行記録（または未使用警告）を注入する。~~ → `done`
- ~~`detector_node`に、ExpertとDetector双方がpython_repl未使用だった場合のみ`constraint_issue=major`に強制する複合失敗ガードを実装する。~~ → `done`
- ~~`python -m py_compile`で回帰がないことを確認する。~~ → `done`
- ~~オフラインスモークテストで、(a) Expertのpython_repl実行記録がstateに正しく保存されること、(b) Expertが未使用の場合は空リストが保存されること、(c) ExpertとDetector双方が未使用の場合のみ強制的にmajorになること、(d) Detectorが独立検算していれば強制されないこと、の4点を確認する。~~ → `done`（フェイククライアントで4ケース確認、全てPass）
- 実機再ドライラン確認は未実施。

---

### BL-034: Deliverableのファイル保存がユーザー承認前に無条件で発生する

| 項目 | 内容 |
|------|------|
| 状態 | `partial`（2026-07-22: R4実装によりwrite_agreement経由の主経路はwhiteboard_drafts方式へ移行し、ファイルの承認前無条件保存・孤児ファイル問題は解消。ただしdecision_extractor_nodeの安全網フォールバック経路は旧来のファイル保存ロジックのまま残っており、そちらは未解消） |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [D-031](../decision_log.md#d-031-deliverableの物理ファイル保存を承認前提にする設計変更はr4のホワイトボード化まで見送る)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（`whiteboard_drafts`/R4）、[cela_r4_impl_Plan.md](../r4/cela_r4_impl_Plan.md) |

**内容:**

ユーザーが実ドライラン（`log/2026-07-20/1421`）のtask_6_3（総合導入計画の完成）で、Expertが最終計画書を提出しDetectorが`risk=low, constraint_issue=none`で通した直後、`decision_extractor_node`が即座にファイルへ保存していることに気づいた。

**該当コード:** `decision_extractor_node`（`cela_main.py:2810-2827`）は`entry_type=="Deliverable" and action_type=="CREATE"`と判定された時点で、DB上の`status`（このタイミングでは常に`"Proposed"`）を一切参照せずに`save_deliverable_to_file()`を呼び、無条件でMarkdownファイルをディスクに書き出す。実際の承認（`status: "Approved"`への遷移）は次ターン以降、User AIが受諾の意を示した時にdecision_extractorが同一トピックへ`action_type=UPDATE`を発行して初めて成立する（`cela_main.py:1851`付近のプロンプト指示）。UPDATE時はファイルを再保存せず`old_content`（Proposed時点のファイルパス）を引き継ぐ（`cela_main.py:2848-2852`）。

**実害の切り分け:** `integrator_node`（`cela_main.py:3040`）はDB上`status=="Approved"`のもののみを集約対象とするため、未承認のまま残ったファイルが最終統合文書に混入することはなく、正当性は壊れていない。ただし、却下（Rejected）や修正版提出のたびに新しいファイルが物理保存され、旧版が孤児ファイルとしてディスクに残り続ける（task_2_2で実際に却下v1・承認v2の2ファイルが残存済み）。「ファイルが存在する＝承認済み」という誤認リスクと、ディスク上の監査証跡が肥大化する衛生上の課題がある。

**対応方針（ユーザー決定）:** 現時点でコードは変更しない。将来のR4（ホワイトボード化・mdファイルの差分読み書き方式、D-018）によって、ノード自身が承認確定後にのみファイルへ書き込む設計へ移行すれば、本問題は構造的に解消される見込みのため、記録のみに留める。

**完了条件（現時点では対応しない）:**

- （見送り）Proposed時点ではファイル保存せず`raw_content`のみを保持し、Approved確定時に初めて`save_deliverable_to_file()`を呼ぶよう`decision_extractor_node`を改修する案は、R4のホワイトボード化設計と合わせて再検討する。

---

### BL-035: `_build_task_scope_context`がフェーズ横断の`depends_on`参照を解決できない

| 項目 | 内容 |
|------|------|
| 状態 | `open`（記録のみ、実装はF-3.8実装時に統合） |
| 優先度 | P2 |
| 依存 | [F-3.8](../要件定義書_v35.md)（自律的DB/ファイル読み取りツール、未実装） |
| 関連 | [D-032](../decision_log.md#d-032-フェーズ横断の確定値成果物アクセスはエージェント自律の読み取りツールf-38を新規追加して解決する) |

**内容:**

ユーザーが実ドライラン（`log/2026-07-20/1421`）のtask_6_3（総合導入計画の完成）で、Expertがピーク輸送力を「60÷13.8×9×3=117人/時」と提出し、Detectorが「ヘッドウェイ13.8分は3台合成の間隔であり、正しくは60/13.8×9=39.1人/時。ピーク需要66.7人/時（200人÷3時間）を下回る」として`constraint_issue=major`で差し戻したログを共有した。Python検算でDetectorの指摘が正しいことを確認した（正しい輸送力39.13人/時 < ピーク需要66.67人/時、不足27.54人/時）。これは表面的な計算ミスではなく、**別フェーズ（task_2_1「必要車両台数の算出」）で確定済みの車両台数（3台）そのものがピーク需要を満たせていない**という、より根深い設計上の問題である。

**原因分析:** `_build_task_scope_context`（`cela_main.py:1306-1311`）の依存変数解決ループ：

```python
for t in state.get("current_phase", {}).get("tasks", []):
    if t.get("task_id") in depends_on_task_ids:
        dependency_variable_names.extend(t.get("owns_variables", []))
```

は`state["current_phase"]`（**現在のフェーズ単体**の`tasks`リスト）のみを走査している。task_planner側でtask_6_3の`depends_on`にtask_2_1が正しく宣言されていたとしても、task_2_1はPhase 2のタスクであり`current_phase`（Phase 6）の`tasks`には存在しないため、このループは絶対にヒットせず、`verified_facts_json`は空（「依存タスクの確定値はまだありません」）のまま返る。全フェーズを保持する`state["phases"]`（`cela_main.py:1497`/`2356`行目で使用）を見ていないことが原因であり、既知のBL-018（`depends_on`宣言自体の粗さ）とは別種の、**宣言が正しくても解決できない**実装上のギャップである。

**実害:** Expertは差し戻しのたびにDetectorの直近の指摘文（`constraint_issue_log[-1:]`）は`generate_user_utterance`経由で受け取るものの、「なぜ3台という前提なのか」という根拠の確定値にはアクセスできないまま、場当たり的に同じタスクの範囲内で修正を試みる可能性が高い。`expert_retry_count>=3`で`route_after_expert_detector`が`reflection`にエスカレーションするが、`reflection_node`のLLM判定（`discussion_status`）が「継続中」であれば何も解決せずそのターンを終える（`route_after_reflection`→`end_turn`）。クラッシュはしないが、収束せずにターン数を浪費し続けるリスクがある。

**対応方針（ユーザー決定）:** `_build_task_scope_context`のループを`state["phases"]`全体（またはフラット化したタスク一覧）を走査するよう修正する即応パッチも検討したが、ユーザーは、将来的にエージェント自身にファイルI/O・DB I/Oの読み取りツールを持たせる設計（F-3.8として要件定義書v35.1に新規追加）に統合すれば、この種のクロスフェーズ参照問題は構造的に解消される見込みであると判断。単体の応急パッチは実施せず、F-3.8実装時にまとめて解消する方針とした。

**完了条件（F-3.8実装時に統合、現時点では対応しない）:**

- （見送り）`_build_task_scope_context`の依存変数解決ループを`state["phases"]`全体走査に修正する即応パッチは、F-3.8の設計と重複するため単体では実施しない。
- F-3.8（自律的DB/ファイル読み取りツール）実装時に、フェーズ横断の`verified_facts`検索・Deliverableファイル取得の両方を満たす設計として統合する。

---

### BL-036: 「最終計画書」の財務・需要数値が統合パスのたびに再ドリフトする（BL-035／F-3.8の射程がコスト計算にも及ぶ実例）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（参考記録のみ、F-3.8実装後の再ドライランで実効性を再評価） |
| 優先度 | P2 |
| 依存 | [BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[F-3.8](../要件定義書_v35.md)（自律的DB/ファイル読み取りツール、未実装） |
| 関連 | [D-033](../decision_log.md#d-033-最終計画書の数値ドリフトはbl-035の既知原因による予想された結果として参考記録に留める)、[D-035](../decision_log.md#d-035-bl-036bl-037の解決方針としてnpu-context-saver由来の時間減衰検索構造化ファクトストアをf-84f-39として要件化する)（F-3.9構造化ファクトストアで解決を狙う） |

**内容:**

ユーザー依頼により、`log/2026-07-20/1421`の全21成果物ファイルを「現実の要件定義書としての品質」という観点で内容レビューした。個別タスクレポート（需要分析・地理調査・予算3レポート・安全基準3レポート・責任分界・予約設計・運用手順マニュアル）自体は、根拠・出典・機械検算・感度分析を伴う実務水準の内容だったが、これらを統合した「最終計画書」（Ver.1.0/Ver.1.1/Ver.1.2、およびlogic_verifierペルソナの完了報告）の財務・需要数値が、統合パスが行われるたびに異なる値へドリフトしていることが判明した。

**発見した数値の乖離（Python検算済み）：**

| | 初期費用 | 年間ランニングコスト | 実質赤字額 | 補助金使用率 |
|---|:---:|:---:|:---:|:---:|
| task_3_1/3_2（Phase 3承認済み根拠） | 10,000万円 | **2,541万円** | **141万円** | **4.70%** |
| Ver.1.0〜1.1（最終計画書） | 10,000万円 | **3,000万円** | **600万円** | **20.00%** |
| logic_verifierの完了報告（最終ターン） | 9,950万円 | **2,980万円** | 580万円 | 19.33% |

赤字額は承認済み根拠と最終計画書とで最大4.26倍の開きがある。需要側も同様に、task_1_1確定値（総人口5,000人・1日総需要400人/日・ピーク200人/3時間）から、最終盤で「総人口5,200人・1日総需要200トリップ/日」へ根拠なくドリフトしていた（200人が「1日総需要」と「ピーク需要」の両方に流用されている）。この乖離はDetector自身も検出していたが（「需要推計（200人/日、人口5,200人）は問題文の参考値（400人/日、5,000人）と異なるが...」）、致命的でないとして`minor`判定のまま通過させていた。

**原因分析:** BL-035で特定した原因と同一。統合パスを担当するペルソナ（technical_writer／logic_verifier）は、承認済みのtask_3_1/3_2/task_1_1のファイルを実際に読み返す手段を持たない（`_build_task_scope_context`のクロスフェーズ参照不能、かつ`python_repl`はファイルI/O禁止）。そのため、統合のたびに「予算上限3,000万円ちょうど」「需要200人」といった、制約は満たすがソースとは異なる、もっともらしい数値をその場で再構成している。今回の発見は、BL-035が輸送力計算という1つの事例にとどまらず、**財務・需要計算全般に及ぶ構造的な問題であること**を裏付けるものであり、独立した新規の欠陥ではない。

**ユーザー判断:** 「BL表記はしてよいですが、各種の情報にアクセスできないのが根本原因ですので、phase6の挙動はある意味予想された結果です。なので、参考程度にとどめて、最終的に必要な情報にアクセスできた時にどうなるかで判断が必要です。」との指示により、本件は既知の根本原因（読み取りツール欠如）から予想される結果として参考記録に留め、現時点では独立の緊急対応・追加修正は行わない。F-3.8実装後、Expertが実際にPhase 3/Phase 1の承認済みファイルを読み返せる状態でPhase 6を再実行し、財務・需要数値のドリフトが解消されるかどうかで初めて実効性を評価する。

**完了条件（F-3.8実装・再ドライラン後に評価）：**

- （保留）F-3.8（自律的DB/ファイル読み取りツール）実装後、同様の6フェーズ・18タスク構成でドライランを再実行し、最終計画書の財務・需要数値が承認済み根拠（task_1_1/task_3_1/task_3_2相当）と一致するかを確認する。
- 一致しない場合は、統合パスのプロンプト設計自体（読み取りツールを実際に呼び出させる指示の強制度）を追加で見直す。

**追記（2026-07-21、D-035）：** F-3.8を「ファイルを丸ごと読み返す」設計から、F-3.9「構造化された事実・理由・引用元セット（トピック検索型ファクトストア）」へ発展させる方針が決定した。統合パスが「車両費」等のトピック名で値・理由・出典を一体で引けるようになれば、都度の再構成・捏造ではなく既存の確定値を確実に再利用できるようになり、本問題の解決に直接寄与する見込み。F-3.8単体の実装より、F-3.9とあわせた実装・再ドライランでの検証が望ましい。

---

### BL-037: Decision/Agreementの`reason_why`が薄く、Detector自身も後から数値の根拠を辿れない

| 項目 | 内容 |
|------|------|
| 状態 | `open`（記録のみ、F-3.1〜F-3.7実装時に理由記載の強制粒度を再設計） |
| 優先度 | P2 |
| 依存 | [F-3.1〜F-3.7](../要件定義書_v35.md)（自律的DB書き込みツール、`decision_extractor_node`の縮小・撤廃） |
| 関連 | [D-034](../decision_log.md#d-034-decisionagreementの理由記載の薄さはbl起票のみに留めf-3系統合時に再設計する)、[D-035](../decision_log.md#d-035-bl-036bl-037の解決方針としてnpu-context-saver由来の時間減衰検索構造化ファクトストアをf-84f-39として要件化する)（F-3.9で「暫定/確定」区別を含む理由記載を要件化）、[BL-034](issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)、[BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例) |

**内容:**

ユーザーが「現状decisionなどある程度記憶の外部化ができていますが、理由の記載が甘いと感じました。phase6でもdetectorが決定された数値がなぜこの値か疑問に思っているログがありました」と指摘した。実ドライラン（`log/2026-07-20/1421`）のDetector自身の思考ログを確認したところ、後から数値の根拠を辿ろうとして辿れず、以下のように繰り返し書かれている箇所を複数確認した。

```
71381: Agentの「対象人口：5,200人」という数値も、問題文の5,000人と異なります。
       これも以前のタスクで設定された数値かもしれませんが、根拠が不明です。
17074: Agentは1周回15分としているが、その根拠が不明。
17155: 「必要501分」の根拠が不明で、検算すると486分になる。
25004: この数値の根拠が不明。1日あたりの電話予約件数は120件。
       1件あたりの平均通話時間を仮定する必要がある。
4453:  「1日あたり総走行距離：80km/ルート」とありますが、
       この80km/ルートという数字の根拠が不明です。
```

いずれも「議論の途中段階として許容範囲」「これも以前のタスクで設定された数値かもしれない」として`minor`判定のまま通過しており、**システム自身の監査役（Detector）が、過去の決定の理由を遡って検証できていない**状態が常態化していた。

**原因分析（2種類の異なる欠落が混在）：**

1. **Decisionとして抽出すらされていない中間仮定**：「80km/ルート」「1周回15分」「7.5時間/日」のような計算過程の中間的な仮定値は、Expertの自由記述レポート内の地の文に埋め込まれるのみで、`decision_extractor`がowns_variables/Decisionとして個別抽出していない。抽出されない以上`reason_why`という専用フィールド自体が存在せず、後から参照する手段がレポート本文の再読（＝BL-034〜036と同じアクセス制約）しかない。
2. **抽出されても理由が浅い**：「最適導入台数は3台」のように実際にDecision化された項目でも、`reason_why`が結論の言い換え（例：「task_2_1で確定」）に留まり、前提・出典・棄却した代替案まで遡れる形では記録されていないケースがある。

**BL-034〜036との関係：** 根本原因は同系統（後から参照可能な情報の粒度不足）だが、対象がファイル読み取りアクセスではなく、`reason_why`欄そのものの記載品質・抽出粒度である点で異なる。F-3.8（読み取りツール）が実装されてファイルへのアクセス自体は解決しても、参照先の`reason_why`が薄いままでは、遡って読んだところで「なぜその値か」を再構成できない可能性がある。

**ユーザー判断:** 「まずBL起票のみ（推奨）」との指示により、本件は記録に留め、プロンプトの単体強化などの個別対応は行わない。将来的にF-3.1〜F-3.7（`write_agreement_tool`によるエージェント自身の自律書き込みへの移行、`decision_extractor_node`の補助的役割への縮小）に着手する際、理由記載の強制粒度（前提・出典・棄却した代替案の明記）をあわせて再設計する。

**完了条件（F-3.1〜F-3.7着手時に統合、現時点では対応しない）：**

- （保留）F-3.1〜F-3.7実装時に、`write_agreement_tool`のスキーマ・プロンプトに「前提・出典・棄却した代替案」を含む理由記載を必須項目として組み込むかどうかを設計する。
- （保留）計算過程の中間仮定（ルート距離・所要時間等）をどの粒度までDecision/owns_variablesとして個別追跡すべきか、compute-heavyなタスクでの過剰抽出リスクとのバランスを含めて設計する。

**追記（2026-07-21、D-035）：** F-3.9「構造化された事実・理由・引用元セット」の新規追加により、対応の方向性がより具体化した。`reason`は絶対的な正しさを要求せず、「暫定値として進めた」という記述自体を正当な理由として認める設計とし、暫定/確定の区別をスキーマに持たせる。これにより、理由記載の「深さ」を無理に強制するのではなく、「暫定である」という性質の明示だけでも最低限の説明責任を満たせるようにし、後の再検討トリガーとしても機能させる。F-3.1〜F-3.7の再設計時、本追記の設計をあわせて反映する。

---

### BL-038: `write_agreement`成功後も`decision_extractor_node`のAgreement抽出がスキップされず、同一トピックでDecisionとDeliverableの二重書き込みが発生する

| 項目 | 内容 |
|------|------|
| 状態 | `done`（根本原因特定・修正済み、オフラインスモークテスト66件通過。**2026-07-22、実LLMドライラン（`log/2026-07-22/1804`）で`expert_wrote_agreement=True`の正常伝播と`⏭️`スキップ（同一ターンで10件全て）を確認、修正の実効性を確定**） |
| 優先度 | P1 |
| 依存 | [cela_r3_impl_Plan.md §3.5/§3.5.1](../r1_r2_r3b_core/cela_r3_impl_Plan.md)（`wrote_agreement_this_turn`検知機構） |
| 関連 | [D-036](../decision_log.md#d-036-r2をd-002同様の扱いでクローズしr3をr3a自律的読み取りf-38f-39r3b自律的書き込み旧来のr3に再編する)（R3b実装）、[D-038](../decision_log.md#d-038-bl-038の根本原因をlanggraphの未宣言typeddictキー消失と特定しlineagestateへのフィールド追加とdecision_extractorフォールバックのwhiteboard保護で対応する)（根本原因特定・修正） |

**内容:**

R3b実装後の実ドライラン（`log/2026-07-21/2248`）で発見。task_1.1にてExpertが`write_agreement`ツールで`entry_type="Decision"`, topic「必要車両台数の算出結果」, `confirmed_variables=[{"variable_name":"vehicle_count","value":"4",...}]`を`status="Proposed"`で書き込み成功（ログで`→ {'success': True, 'message': 'DB update successful'}`を確認）。設計（`cela_r3_impl_Plan.md` §3.5.1）では、この成功を受けて`decision_extractor_node`のAgreement抽出ループ（`db_append_agreement`等）は当該ターンでスキップされるはずだった。

しかし実際のログでは、直後の`decision_extractor_node`実行時に`⏭️ [decision_extractor] write_agreementが呼ばれたため...スキップしました`という該当ログが一度も出力されず、代わりに通常の抽出処理が走り、同一トピック名「必要車両台数の算出結果」で`entry_type="Deliverable"`の**別のAgreementエントリ**が新規作成され、ファイルにも保存された（`decision_extractor`自身の思考ログで「内容包含完整的报告，因此entry_type应为'Deliverable'」と判断していた）。

**調査結果（Claude Sonnet 5によるオフライン再現テスト）：**

- `expert_node`単体を、実際の`_query_AI_live`ツールループを通す形（フェイククライアントで`write_agreement`のtool_callを模擬）で検証したところ、`state["expert_wrote_agreement"]`は正しく`True`になることを確認した（`_LAST_WRITE_AGREEMENT_SUCCEEDED`グローバル変数とその伝播機構自体は単体では正常動作）。
- したがって原因は以下のいずれか、または両方の複合と考えられる：
  1. **状態伝播のバグ**：実際のグラフ実行（`expert` → `expert_detector` → `expert_decision_extractor`、いずれも`build_graph()`でのノード登録名）の中で、`state["expert_wrote_agreement"]`が何らかの理由で`decision_extractor_node`到達までに失われている。原因箇所は未特定。
  2. **設計の粒度不足**：Expertの`write_agreement`呼び出しは`entry_type="Decision"`（数値確定）のみをカバーしており、`entry_type="Deliverable"`（報告書本体・ファイル保存）は呼び出していない。`decision_extractor_node`は独自の判断でこの報告書全体をDeliverableとして抽出すべきと判定しており、これ自体は誤りではない可能性がある。§3.5.1の「write_agreementが一度でも呼ばれたらAgreement抽出を全部スキップ」という設計は、Expertが部分的にしか`write_agreement`を使わない（Decisionのみ書いてDeliverableは書かない）ケースを想定できておらず、単位が粗すぎる。

**実害:** データ破損や機能停止はない。Decision用とDeliverable用で同じ実質内容のAgreementが2件並存する状態（DB冗長化、`_build_agreements_context`のプロンプト表示が若干冗長になる程度）。

**完了条件:**

- ~~`decision_extractor_node`内に診断ログを一時追加し、次回ドライランで実際の値を確認して原因を確定させる。~~ → 2026-07-22、R4実装後の実ドライラン（`log/2026-07-22/1407`）で実害（DB上でWHITEBOARDポインタがプレーンテキストで上書きされSupersededになる事故）を直接確認し、根本原因を特定済み。
- ~~原因が(1)状態伝播バグと判明した場合：該当箇所を修正し、オフラインスモークテストで実際のグラフ経由の状態伝播を検証するテストケースを追加する~~ → 完了。

**根本原因（確定）:**

原因は仮説(1)「状態伝播のバグ」だった。インストール済みLangGraph（v1.2.9）で最小構成の再現コードを書いて実証: `StateGraph`のスキーマとして渡す`LineageState`（TypedDict）に**宣言されていないキー**は、ノードが戻り値の辞書にセットしても次のノードには伝播せず消える。`expert_wrote_agreement`・`user_wrote_agreement`・`expert_last_whiteboard_edit`（R3b/R4で導入）はいずれも`LineageState`への追加が漏れており、`expert_node`内で正しく`True`にセットされていても、`decision_extractor_node`到達時には常にデフォルト値（False/None）に戻っていた。同時期に導入された`expert_last_python_calls`はTypedDictへの追加が行われていたため正常動作しており、この対比が根本原因の裏付けとなった。

`tests/test_r3_smoke.py`/`test_r4_smoke.py`の既存テストが`decision_extractor_node`をPython関数として直接呼び出す形式だったため、LangGraphのチャネル機構（未宣言キーの消失）を経由せず、本件を検知できなかった。

**修正内容（D-038）:**

1. `LineageState`（`cela_main.py`）に`expert_wrote_agreement: bool`・`user_wrote_agreement: bool`・`expert_last_whiteboard_edit: dict | None`を追加。
2. 二重防御として、`decision_extractor_node`のフォールバック経路に`WHITEBOARD:`ポインタの保護分岐を追加（`FILE_PATH:`と同様、フォールバック経路からの上書きを禁止）。
3. `tests/test_r4_smoke.py`に、実際の`StateGraph(cela_main.LineageState)`を`app.invoke()`経由で検証する回帰テストと、WHITEBOARD保護の回帰テストを追加（オフラインスモークテスト66件全通過）。
4. **実LLM再ドライランでの最終確認（2026-07-22、`log/2026-07-22/1804`）**: `[DEBUG] decision_extractor target_role='expert' expert_wrote_agreement=True user_wrote_agreement=False -> wrote_agreement_this_turn=True`が正しく出力され、同一ターンで抽出された10件の`extracted_events`すべてに対し`⏭️ [decision_extractor] write_agreementが呼ばれたため、ExtractからAgreement書き込みをスキップしました`が出力された。修正の実効性を実機で確認。

### BL-039: `decision_extractor`が出力するtask_idの表記ゆれ（ドット vs アンダースコア）により、タスク遷移がドライラン全体で1回も成功していない

| 項目 | 内容 |
|------|------|
| 状態 | `done`（オフラインスモークテスト済み、実LLM再ドライラン未実施） |
| 優先度 | P0 |
| 依存 | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)（`_get_current_task`によるスコープ限定機構）、[BL-024](issue_backlog.md#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)（`current_phase`/`current_task_id`の状態管理）、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（Expertスコープガードレール） |
| 関連 | [decision_lineage.md 論点24・26](../decision_lineage.md)（BL-023/BL-025設計時の議論） |

**内容:**

R3b実装後の実ドライラン（`log/2026-07-21/2248`、`log_no_prompt.md`）レビュー中に発見。`call_task_planner`が生成する実際の`task_id`はアンダースコア表記（例: `"task_id": "task_1_1"`）だが、`call_decision_extractor`が返す`advances_to_task_id`はドット表記（例: `"task_1.1"`）になっており、`_resolve_task_transition`（`cela_main.py:3160-3164`）の`valid_task_ids`存在チェックに毎回一致しない。ログ全体を検索したところ、以下の8箇所すべてでタスク遷移が拒否されていた（`⚠️ [decision_extractor] 存在しないtask_id '...' への遷移要求を無視しました。`）：

```
task_1.1 → task_1.2 遷移時 / task_1.2 → task_1.3 遷移時 / task_1.3 → task_1.4 遷移時（×2）
task_1.4 → task_1.5 遷移時 / task_1.5 → task_2.1 遷移時 / task_2.1 → task_2.2 遷移時
```

`state["current_task_id"]`は初期値（空文字列）のまま一度も正しく更新されておらず、`_get_current_task`（`cela_main.py:1671-1681`）は毎ターン、フォールバック（`return tasks[0] if tasks else {}`）によりそのフェーズの先頭タスクを返し続けていた。実際、ログ後半（task_2.1評価時点、21600行台）でDetectorに提示されたacceptance_criteriaは、依然としてtask_1.1のもの（車両台数算出関連の3項目）のままだった。

`phase_id`側（`advances_to_phase_id`）はアンダースコアなしの`phase_2`等の単純な表記のため一致しており、phase遷移自体は成功していた形跡がある一方、`task_id`側だけが表記ゆれで機能していない。プロンプト側の指示例（`cela_main.py:2265`「次のタスク（task_1_2）に移行する」）自体は正しいアンダースコア表記だが、LLMが会話履歴中の自然文表記（人間がタスクを"task_1.1"のようにドットで言及する慣習）を引きずってしまっていると考えられる。

**影響範囲:** `_get_current_task`はBL-023/BL-025のスコープ限定機構の中核であり、以下すべてに波及する。
- `call_detector`のacceptance_criteria充足チェック（`cela_main.py:2043-2045`）
- `call_expert`の`light_system_prompt`（現在タスクの範囲限定、BL-025のガードレール、`cela_main.py:2017-2024`）
- `decision_extractor_node`の`owns_variables`スコープ（`cela_main.py:3189-3190`）

つまりBL-023 Phase A・BL-025で実装したスコープガードレールが、本ドライランの開始直後（task_1.2着手時点）から実質的に無効化されていた可能性が高い。実害としては、Detector判定時の`criteria_status`が終始的外れなAC（task_1.1のもの）に対するbool配列になっていた（Detector自身が思考ログ内で毎回「これはtask_1.1のACではないか」と気づき、`comment`欄で補足しつつ`risk`/`constraint_issue`自体は妥当な値に自己修正していたため、致命的な誤判定・不当な差し戻しには至っていない）。ただしExpertの`light_system_prompt`側で同様のスコープ混線が実際にどう影響したか（BL-025ガードレールが常にtask_1.1基準で発動していたか）は未確認。

**完了条件:**

- ~~`_resolve_task_transition`内で、LLMが返す`next_task_id`/`next_phase_id`を実在ID集合と照合する前に正規化~~ → `_resolve_task_transition`（`cela_main.py`）にドット→アンダースコア正規化を実装（一致しなければ従来通り拒否、フェイルクローズは維持）。
- ~~`call_decision_extractor`のプロンプトに正確なtask_id一覧を明示~~ → `call_decision_extractor`に`valid_task_ids`引数を追加し、`decision_extractor_node`から`state["phases"]`全体のtask_idをフラット化して渡すよう実装。プロンプトに一覧を提示し「一字一句コピー」を指示。
- ~~オフラインスモークテストの追加~~ → `tests/test_r3_smoke.py`に`test_bl039_task_transition_normalizes_dot_notation_task_id`（ドット表記の正規化確認）・`test_bl039_task_transition_still_rejects_truly_unknown_task_id`（フェイルクローズの非退行確認）を追加、全49件Pass。
- 修正後の再ドライランで、`_get_current_task`が実際に想定タスクを返し続けていること（Detectorのcriteria_textが各タスク固有のACになっていること）をログで確認する（**未実施、次回ドライラン待ち**）。

### BL-040: `read_deliverable_file`がfile_path直接指定に依存し、実質的に発見不能だった問題

| 項目 | 内容 |
|------|------|
| 状態 | `done`（オフラインスモークテスト済み、実LLM再ドライラン未実施。2026-07-22: R4実装によりper-task Deliverableの主経路はwhiteboard_drafts方式へ移行したため、`_Vn`バージョニング＋`old/`退避は現在`integrator_node`の最終統合文書専用。ファイル・ホワイトボードどちらの場合も`read_deliverable_file`は同一インターフェースで解決できることを維持） |
| 優先度 | P1 |
| 依存 | F-3.8（自律的DB/ファイル読み取りツール、[decision_log.md D-036](../decision_log.md)） |
| 関連 | [BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)・[BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)（F-3.8導入の動機となった読み取りアクセス欠如の系譜） |

**内容:**

実ドライラン（`log/2026-07-21/2248`、`log_no_prompt.md`）レビュー中に発見。`read_deliverable_file`の呼び出しを全件集計したところ、**31回中21回（約68%）が`not_found`で失敗**していた。原因は`save_deliverable_to_file`が生成するファイル名がトピック文字列＋Unixタイムスタンプ（例: `必要車両台数の算出結果_1784643517.md`）で一意に決まり、AIがタイムスタンプ部分を事前に予測できないため。成功した10回はいずれも、DBの`agreements`コンテキストに既に`FILE_PATH:...`の正確な文字列が表示されていて、それをそのままコピーできたケースのみだった。以下は実際に観測された当てずっぽうの試行例：

```
task_1_1_vehicle_count.md → not_found
task_1_1_vehicle_count_1784646438.md → not_found
task_1_1_vehicle_count_1784641716-3a065da7.md → not_found
task_1_3_cost_analysis.md → not_found（ドライラン停止直前も含め複数回）
```

つまり「パスを知らない限り読めない」ツールになっており、F-3.8の設計意図（自律的な事実確認）を実質的に果たせていなかった。

**実害:** クラッシュ・データ破損はない。AIが数回無駄なツール呼び出しを消費した上で断念する、またはコンテキストに既に出ている情報に頼らざるを得なくなる（F-3.8導入前の状態への実質的な後退）程度。

**完了条件:**

- ~~`read_deliverable_file`に`task_id`/`topic_keyword`引数を追加し、agreements DBの`FILE_PATH:`ポインタから実際のパスを逆引きする~~ → `READ_DELIVERABLE_FILE_TOOL`のスキーマに`task_id`/`topic_keyword`を追加（`file_path`は既知の場合のみのフォールバックに降格）。`_resolve_deliverable_file_path`ヘルパーを新設し、`entry_type=="Deliverable"`かつ`decision_what`が`FILE_PATH:`で始まるagreementsをtask_id/topic_keywordで絞り込み、複数該当時は最新（id最大）を採用。
- ~~agreements.task_id列がLLMのargs依存で欠落しがちな問題の修正~~ → `_commit_agreement_from_tool`に`task_id`引数を追加し、`args.get("task_id")`が空の場合は`_write_agreement_impl`経由で伝播される`_CURRENT_TASK_ID`をフォールバックとして使用するよう修正（従来はLLMがwrite_agreement呼び出し時に`task_id`を明示的に含めない限りDB上のtask_id列が空になり、本修正の逆引きも機能しなかった）。
- ~~オフラインスモークテストの追加~~ → `tests/test_r3_smoke.py`に`test_bl040_read_deliverable_file_lookup_by_task_id`（task_id/topic_keywordによる逆引き成功、該当なしのnot_found確認）を追加、全49件Pass。
- ~~（ユーザー追加提案、2026-07-22）ファイル名をタイムスタンプではなく`_Vn`のバージョン連番にし、旧版は`old/`フォルダへ退避する~~ → `done`。`save_deliverable_to_file`をバージョン連番方式（`deliverables/`・`deliverables/old/`双方を走査して次番号を採番）に変更し、`_archive_old_deliverable_file`ヘルパーを新設。`_commit_agreement_from_tool`・`decision_extractor_node`双方のUPDATE時新版保存パスに旧版退避を追加（BL-034の孤児ファイル問題も同時に緩和）。`test_bl040_deliverable_filenames_are_versioned_and_old_versions_archived`を追加、全50件Pass。
- 修正後の再ドライランで、`read_deliverable_file`のnot_found率が実際に低下することをログで確認する（**未実施、次回ドライラン待ち**）。

### BL-041: 一度確定した決定（例: 車両台数）を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しない（Resource Arbiter機構が死んだコードパスになっている）

| 項目 | 内容 |
|------|------|
| 状態 | `partial`（暫定値デフォルト化は実装済み。facilitator再設計・すり合わせタスクは設計判断待ち） |
| 優先度 | P1 |
| 関連 | [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（reflection/facilitatorが同様に発火不能という既知の系譜）、[BL-017](issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り)（facilitatorの調停行動そのものの設計不足、本Issueと統合予定）、[decision_lineage.md 論点42](../decision_lineage.md)（根本原因の再診断とユーザー提案の詳細）、[cela_facilitator_arbiter_redesign_BL041.md](../r1_r2_r3b_core/cela_facilitator_arbiter_redesign_BL041.md)（設計ドラフト、2026-07-22、未承認） |

**内容:**

ユーザーが「task_1.1で車両台数4台を決定し、これで初期予算1億円を使い果たしている。この後システム開発費等の算出に入るとき、この決定をどう覆すか見ものだ」と問いかけたことを契機に調査。

`cela_main.py`の`arbiter_node`/`check_global_constraint_overrun`は、`state["global_constraints"]`（各フェーズの予算取り分の合計と上限を突き合わせる構造）を見て資源超過を検出し、`call_resource_arbiter`で再配分案を調停する設計になっている。しかし`global_constraints`への書き込み箇所を全文検索したところ、`task_planner_node`での初期化（`state["global_constraints"] = []`）以外に**実際のクレームデータ（agreementsの`resource_claims`フィールド等）をこのリストに集約する処理がコードベース中に一切存在しない**ことを確認した。したがって`check_global_constraint_overrun`は常に空リストを走査するだけで超過を検出できず、`arbiter_node`は常に`phases_to_revise=[]`で早期returnする。

実ドライラン（`log/2026-07-21/2248`）全文を検索しても、`[Resource Arbiter]`・`[facilitator]`・`[reflection]`・`phases_to_revise`はいずれも0件であり、この調停機構が**設計上は存在するが実際には一度も発火し得ない死んだコードパス**であることを実行ログでも確認した。

今回のドライランでは、task_1.2（初期費用の内訳算出）自身のacceptance_criteria（「予算超過時の調整案（台数減・システム簡略化等）が検討されている」）にAgentが応える形で、システム構築費・予備費等を積算した結果9,958万円（残額わずか42万円、1億円の0.42%）に収まり、Resource Arbiterに頼らずタスク内で帳尻が合った。しかしこれは偶然のタスク設計上の救済であり、**一度確定した決定（`vehicle_count=4`等）を、後続タスクで発覚した制約違反を根拠に体系的に再検討させる自動メカニズムは現状存在しない**。`write_agreement`のSUPERSEDE機構自体はあるが、BL-025のスコープガードレールによりExpertは自タスク外のトピックを書き換えない設計であるため、これも自動トリガーとしては機能しない（Expertが自発的に「task_1.1の決定を見直すべき」と提案しない限り、誰も介入しない）。

**実害:** 今回は顕在化しなかったが、タスク分解の粒度やタスク自身のacceptance_criteriaの書き方次第では、後続タスクが解決不能な制約矛盾に陥ったまま`expert_retry_count>=3`で`reflection`に丸投げされ、そこでも収束が保証されない（BL-005/BL-017参照）ため、無限の差し戻しループやフェイルオープンでの通過につながるリスクがある。

**ユーザーによる根本原因の再診断（2026-07-22、[decision_lineage.md 論点42](../decision_lineage.md)）:**

「木を見て森を見ず」状態が発生していた。task_1.1が「必要車両台数の選定」という狭いスコープだったため、AIはそのスコープ内でのみ作業し、予算全体最適という視座を持てなかった。解決の方向性として3点を提示：

1. 暫定のリソース配分を検討するタスクを最初に置く、または確定済み数値でも合理的な理由があれば上書き可能にしタスク間で「すり合わせる」機構を持たせる。
2. 初期制約（ゴールで直接与えられた予算上限等）は絶対とする一方、検討中に導出された数値（車両台数等）はデフォルトで暫定扱いとし、後で変更の余地を残す。どこかに「すり合わせフェーズ」が必要。
3. 現実の予算折衝同様、無限に議論を続けるのではなく「何をしないか」（車両リース化、自社開発ではなく既存SaaS利用等）を含めたエスカレーションが必要で、**この役目はfacilitatorが担うべき**（facilitatorは元々「議論の膠着を緩和させる」役目であり、`reflection`同様に数ターンごとに様子を見る周期的発火タイミングの調整が必要、という補足あり）。

**完了条件:**

- ~~提案2（暫定値デフォルト化）を実装~~ → `done`。F-3.9の`verified_facts.confidence`（confirmed/provisional）を活用し、`call_expert`のシステムプロンプト（フル版・軽量版`light_system_prompt`双方）に「ゴール直接の絶対制約以外はデフォルトでconfidence='provisional'とする」原則を追加。`WRITE_AGREEMENT_TOOL.confirmed_variables`のJSON schemaとコード側デフォルト値も`"confirmed"`→`"provisional"`に変更（`cela_main.py`）。オフラインスモークテスト（`tests/test_r3_smoke.py`、既存分含め50件）で非退行を確認。なお、`decision_extractor`の`owned_variable_values`経由の安全網パス（`upsert_verified_fact`のデフォルト引数）は今回スコープ外のため`"confirmed"`のまま残っており、Expertがwrite_agreementを呼ばずowned_variable_valuesのみで確定値を出した場合はこの原則が及ばない点に留意（次回対応候補）。
- 提案3（facilitatorのエスカレーション役への再設計、`reflection_interval`同様の周期的発火）は、BL-017（reflection/facilitatorの当初設計意図復旧）と統合すべき影響範囲の広い変更のため、**今回は実装せず、`docs/design/r1_r2_r3b_core/`配下に設計書を先に作成する**方針とした（未着手）。
- 提案1（すり合わせタスクを最初に置く／上書き機構）は、facilitator再設計とあわせて検討する将来課題として保留。
- `agreements.resource_claims`を`state["global_constraints"]`へ集約するタイミング、`arbiter_node`の発火条件の設計は上記facilitator再設計と統合して検討する（未着手）。
  → **確認済み（2026-07-23、R5着手前の棚卸しで実装）**: ドラフト§3.1相当のみをMVPスコープで実装。`resource_claims`のスキーマを平坦な`{名前: 数値}`から`{名前: {phase_id, value, total_cap}}`（`WRITE_AGREEMENT_TOOL`スキーマ・decision_extractor抽出プロンプト双方を変更）に具体化し、新規`_aggregate_global_constraints`ヘルパーが`arbiter_node`の冒頭でagreements DBから毎回動的に`state["global_constraints"]`を再集約するよう配線した（`cela_main.py`）。これにより`check_global_constraint_overrun`が実際に超過を検出し`call_resource_arbiter`（LLM呼び出し）へ到達できるようになった（オフラインテスト`tests/test_bl041_bl050.py`で確認、実ドライランでの発火は別途要確認）。**ただし提案3の4段階エスカレーションメニュー（ドラフト§3.2）・facilitator 3段階制御再設計（§3.3）・BL-005の`turn_count`根本修正は今回のスコープに含めておらず、引き続き未着手**。R5のGoalShiftEvent（§4.2-4.3で`call_resource_arbiter`に依存）が土台として利用できる最低限の状態にした、というのが今回の到達点。

**2026-07-23追記（優先度の再確認）:** BL-048（reflection復旧）・BL-054/055（ドメイン先行監査・真の制約/条件の区別）の実装後、`log/2026-07-23/1656`でreflectionが実際に「ゴール・ドリフト検出（`aligned=False, status=stagnant`）」を正しく捕捉する場面を確認した（Expertが与条件の速度を無断で20km/h→28.8km/hに変更していた事例）。しかし、この検出の後に起きるのは`drift_flag=True`によるExpert/User AIへの**同じ形の差し戻し**（Detectorのmajorと同じ再プロンプト）のみで、提案3が想定していた「これ以上代替案を探すより、Userに『どの前提を崩すか』の決定を仰ぐ」という**エスカレーション**の役目は依然として存在しない。task_1_1が今も長時間収束しない一因はここにあり、reflectionの検出精度が上がったことで、逆にこのエスカレーション未実装のギャップがより明確になった（設計判断待ち、着手は引き続き保留）。

---

### BL-042: Detectorのconstraint_issue判定（minor/major境界）でツールループが同じ論点を延々再検討し、トークンを浪費する

| 項目 | 内容 |
|------|------|
| 状態 | `open`（プロンプト指示による軽量対策を実装、実LLM再ドライランでの効果確認待ち） |
| 優先度 | P2 |
| 依存 | [D-038](../decision_log.md#d-038-bl-038の根本原因をlanggraphの未宣言typeddictキー消失と特定しlineagestateへのフィールド追加とdecision_extractorフォールバックのwhiteboard保護で対応する)（同じドライランで発見） |
| 関連 | なし |

**内容:**

実LLMドライラン（`log/2026-07-22/1804`）レビュー中に発見。task_1_1のDeliverable評価で、Agentの成果物中の「平均164円/トリップ」という記載が制約「1乗車一律200円」と矛盾する件について、Detectorがconstraint_issueを"minor"にするか"major"にするかで、iter=1から少なくともiter=8〜9まで、ほぼ同じ論点・同じ数値的根拠を繰り返し再検討し続けた（一度"minor"と結論しかけては直後に「Actually, let me reconsider once more」と覆す、を何度も繰り返す）。iter=6とiter=7では全く同一のpython_replコード（acceptance_criteria充足チェック）を重複実行しており、これは言い回しの繰り返しに留まらずツール呼び出し予算（`MAX_TOOL_ITER=15`）の実消費でもある。クラッシュ・非収束エラーには至っていないが、1回の判定だけで予算の半分以上を使う状態だった。

根本原因は、Detectorのconstraint_issue判定基準プロンプト（`call_detector`）が「明白な数値矛盾ならmajor」という厳格な基準と「結論に影響しなければminorでよい」という緩やかな基準の両方を許容する書き方になっており、モデルがどちらを優先すべきか自己判断で行ったり来たりしてしまうこと。

**ユーザー提案・決定（2026-07-22）:**

ユーザーが「多数決方式（3回思考して結論の多い方を採用）」を提案。当初AIは「3回別々にAPI呼び出しをする」という3倍コスト増の方式と誤解して懸念を示したが、ユーザーが「同じ呼び出しの中で3回明示的に判定し多数決を取る」という意図であることを明確化。この方式は、単純な「2回目で強制確定」（結果が変わったかどうかを問わず機械的に打ち切る案、AI提起）よりも「たまたま偶数回目の判定が不安定だった場合のブレ」に強いという利点があるとAIが指摘し、採用が決定した。

実装方式について、(A)プロンプト指示のみでモデルに3回判定＋多数決を守らせる案と、(B)コード側でiterごとの暫定判定を強制的にカウントし3回分溜まったら機械的に多数決を計算して打ち切る案の2択をAIが提示。今回の堂々巡り自体、既存プロンプトの「無駄な再検討をするな」という趣旨の指示があっても守られなかった実績があるため(B)の方が確実だが、まず実装コストの低い(A)で様子を見て、それでも守られないなら(B)に進む、という順序でユーザーが合意。

**実装:**

`call_detector`のプロンプト（`cela_main.py`）に、「【判定のブレ防止（3回多数決方式）】」ブロックを追加。同じ論点について独立した判定を3回だけ行い（各回は結論のみ簡潔に）、3回のうち多数だった結論を採用し、それ以上の再検討を禁止する指示を挿入した。プロンプト文字列のみの変更のためロジック変更はなく、オフラインスモークテスト66件は非退行（`python -m py_compile`合格）。

**完了条件:**

- 次回実LLMドライランで、同種の判定（minor/major境界の数値矛盾）においてDetectorのツールループのiter数が明確に減少し、同一論点の重複検討・重複python_repl実行が解消されることを確認する。
- (A)のプロンプト指示だけでは守られない場合、(B)のコード側強制（iterごとの暫定判定パースと機械的多数決・強制打ち切り）に進む。

---

### BL-043: `decision_extractor`のJSON出力をFunction Calling方式に作り替え、既存の自己修復ループ（D-009）に一本化する

| 項目 | 内容 |
|------|------|
| 状態 | `open`（BL起票のみ、実装はJSONパース失敗が実害として頻発した場合に着手） |
| 優先度 | P3 |
| 依存 | [D-009](../decision_log.md)（`write_agreement`等のツール呼び出しで確立済みの、引数JSON破損時の自己修復パターン） |
| 関連 | `_safe_json_parse`・`_query_and_parse_with_retry`（[../../cela_main.py](../../../cela_main.py)、現行の層2リトライ、D-005） |

**内容:**

`decision_extractor`（`call_decision_extractor`）は現在、`tools`なしの単発`query_AI`呼び出しで長大なJSON（`extracted_events`配列）を生テキストとして出力させ、`_safe_json_parse`でパースしている。パースに失敗した場合、`_query_and_parse_with_retry`（一部の呼び出し元のみ）またはノード呼び出し自体を最初からやり直す「層2リトライ」（D-005）で対応しているが、これは**JSON全体を1から書き直させる**荒い単位のリトライであり、どこが壊れていたかのフィードバックはモデルに一切返っていない。

ユーザーから「AIがJSON出力→パース失敗→1からやり直し、ではなく、ツール使用でJSON構造を確認→AIへOK/FAULTとどこが間違っているかをフィードバック→AIが該当箇所だけ直して再出力、という流れにできないか」という提案があった。

調査の結果、このコードベースには既にほぼ同じ仕組みが`write_agreement`等のツール呼び出し引数のパースに実装済みであることが判明した（`cela_main.py`のツールループ内、`json.loads(tc.function.arguments)`が`json.JSONDecodeError`を送出した場合、クラッシュさせずエラー内容をツール結果としてモデルに返し、同一ツールループ内（`MAX_TOOL_ITER`の予算内）で自己修復させる、D-009のパターン）。

**決定（2026-07-22）:**

2つの実装案（(1) `jsonschema`ライブラリ等を使った検証専用ツールを新設し現行の生テキスト出力方式に追加する案、(2) `decision_extractor`自体をFunction Calling方式（例: `submit_extracted_events`ツール）に作り替え、D-009の既存自己修復ループに一本化する案）をAIが提示し、ユーザーは(2)を選択。ただし設計変更としてはやや大きめ（`extracted_events`配列全体をtools schemaとして定義し直す必要がある、Detector同様MAX_TOOL_ITERの予算管理が必要になる等）であるため、**今回はBL起票のみに留め、JSONパース失敗（`_safe_json_parse`のフォールバック採用）が実ドライランで実害として頻発するようになった時点で実装に着手する**方針とした。

**完了条件（着手時）:**

- `call_decision_extractor`の`tools`引数に`extracted_events`配列を受け取る専用ツール（例: `submit_extracted_events`）のJSON Schemaを定義し、Function Calling方式に変更する。
- 既存のツールループの自己修復パターン（D-009、引数JSONパース失敗時のエラーフィードバック＋同一ループ内再試行）にそのまま乗ることを確認する。
- 現行の`_safe_json_parse`ベースの単発呼び出し・層2リトライ（D-005）は本経路について不要になるため撤去する。
- `tests/test_r3_smoke.py`等のオフラインスモークテストで、壊れたJSON引数を渡した場合に自己修復ループが機能することを検証するテストケースを追加する。

---

### BL-044: ドライランの一時停止・再開機能（Ctrl+C→checkpoint.json→`--resume`）

| 項目 | 内容 |
|------|------|
| 状態 | `done`（実装・オフラインスモークテスト4件Pass。実LLMドライランでのCtrl+C→`--resume`往復の実地確認は未実施） |
| 優先度 | P2 |
| 依存 | [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（`turn_count`がグラフ内部ループの間更新されないため、ターン境界でのチェックポイントでは粒度が粗すぎると判明した経緯） |
| 関連 | [D-039](../decision_log.md)、[decision_lineage.md 論点45](../decision_lineage.md) |

**内容:**

ユーザーから「ドライランが長時間化しやすく連続稼働させ続けるのが難しいので、一時停止・再開の仕組みを組めないか」と相談。当初AIは「`app.invoke()`から戻ったターン境界でstateをJSON保存し、次回起動時に読み込んで再開する」方式を提案したが、ユーザーが「そもそも今、ターンは凍結されて1のままなのでは」と指摘。BL-005（`state["turn_count"]`はグラフ内部で`generate_user_utterance`へループバックし続ける限り更新されず、外側の`app.invoke()`単位では長時間戻ってこないことがある）を踏まえると、ターン境界でのチェックポイントは実用にならないと判断し、方式を変更した。

**実装（`cela_main.py`）:**

1. `_save_checkpoint`/`_load_checkpoint`: `state`/`config`/`current_turn`をJSONとして原子的に（一時ファイル→`os.replace`）保存・復元するヘルパーを新設。
2. `run_ai_vs_ai_loop`: `app.invoke(state)`（グラフ全体を1回で最後まで実行）の代わりに`app.stream(state, stream_mode="values")`を使い、グラフの各ノード実行後のstateスナップショットを都度受け取ってcheckpoint（そのランのログフォルダ内`checkpoint.json`）へ保存するよう変更。`KeyboardInterrupt`（Ctrl+C）を捕捉し、直前のcheckpointパスと再開コマンドを案内してから終了する。`resume_from`引数を追加し、指定時はfreshなstateを作らずcheckpointから`state`/`config`/`current_turn`・`run_id`・`db_path`を復元する（`init_db`は`CREATE TABLE IF NOT EXISTS`のため同一DBへの再接続は安全）。
3. `task_planner_node`: グラフのentry_pointが`task_planner`固定のため、再開時も必ずこのノードを通る。従来の`if state["turn_count"]==1:`だけのガードだと、ターン1の途中（既にphases確定済み）で止めた場合に計画を無条件で再生成してしまうため、`if state["turn_count"]==1 and not state.get("phases"):`に修正（冪等性）。
4. `__main__`: `argparse`で`--resume <checkpoint.jsonのパス>`を追加。指定なしは従来通り新規スタート。

**制約（設計時に明確化）:** グラフのentry_pointが`task_planner`固定のため、「止めたノードそのものから再開」ではなく「その回（ラウンド）の頭（`generate_user_utterance`、ターン2以降）から再開」になる。それでも、BL-005の影響で数百行分内部ループしうる「ターン単位」の粗い粒度と比べれば、最大でも直近1ラウンド分のやり直しで済むため実用上十分と判断した。

**完了条件:**

- `tests/test_checkpoint_resume.py`（新規4件）: checkpoint往復・原子的書き込み・上書き・`task_planner_node`冪等性ガードをオフラインで検証、全件Pass。
- 実LLMドライランで実際にCtrl+Cで一時停止し、`--resume`で再開できることを確認する（未実施）。

| 日付 | 内容 |
|------|------|
| 2026-07-22 | 新規起票・実装完了。ユーザー提案を受けチェックポイント方式を設計する過程で、当初案（ターン境界での保存）がBL-005（`turn_count`凍結）により実用にならないとユーザー自身が指摘して発覚し、`app.stream()`によるノード単位保存方式へ設計変更（D-039）。`_save_checkpoint`/`_load_checkpoint`・`run_ai_vs_ai_loop`の`resume_from`引数・`task_planner_node`の冪等性ガード・`--resume` CLI引数を実装。`tests/test_checkpoint_resume.py`（4件）新規追加、オフラインスモークテスト計70件Pass。実LLMドライランでの実地確認は次回待ち。 |

---

### BL-045: `write_agreement`成功直後のAPIエラーでBL-033フェイルクローズが誤爆し、保存済みのホワイトボードがロールバックされる

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | [D-038](../decision_log.md#d-038-bl-038の根本原因をlanggraphの未宣言typeddictキー消失と特定しlineagestateへのフィールド追加とdecision_extractorフォールバックのwhiteboard保護で対応する)（`_LAST_WRITE_AGREEMENT_SUCCEEDED`と`_LAST_PYTHON_CALLS`の非対称という同系統の状態管理欠陥） |
| 関連 | BL-033（フェイルクローズ本体） |

**内容:**

実ドライラン（`log/2026-07-22/2217`）で、Expertがpython_replによる検算を完了し`write_agreement`でホワイトボードVer.1保存に成功した直後、同一ツールループの次iterationでAPI 429エラーが発生しリトライを使い切ってエラープレースホルダ（`"(サーバー高負荷によるAPIエラー)"`）を返した。後続のDetectorは3回多数決方式で正しく`minor`判定していたが、BL-033のフェイルクローズガード（`detector_node`）が`state["expert_last_python_calls"]`の空を理由に`constraint_issue`を`major`へ強制上書きし、差し戻し→保存直後のホワイトボードがロールバックされる事故が発生した。

根本原因は`_LAST_PYTHON_CALLS`（BL-033の判定材料）が`_query_AI_live`のツールループの**正常終了時のみ**更新される実装になっており、ループ途中のAPIエラー例外で打ち切られた場合、実際に実行済みのpython_repl記録が反映されないまま失われていたこと。対照的に`_LAST_WRITE_AGREEMENT_SUCCEEDED`はツール実行のその場で即時セットされるため例外の影響を受けず、両者が非対称な状態になっていた。

**実装（`cela_main.py`）:**

python_repl実行のたびに`_LAST_PYTHON_CALLS`を即時反映するよう修正（正常終了時の更新と合わせて二重に更新されるが冪等）。ループが途中で例外終了しても、それまでに実行済みのpython_repl記録が失われなくなった。

**完了条件:**

- オフラインスモークテスト（既存74件）が非退行でPass。
- 実LLM再ドライランで、`write_agreement`成功後にAPIエラーが起きてもBL-033フェイルクローズが誤爆しないことを確認する（次回待ち）。

---

### BL-046: `_query_AI_live`のリトライがツール呼び出しループ全体をサイレントに巻き戻し、途中経過が見えない

| 項目 | 内容 |
|------|------|
| 状態 | `done`（可視化のみ対応、本質的な巻き戻り防止は見送り） |
| 優先度 | P2 |
| 依存 | BL-009（既知の粗いリトライ粒度、当時受容済み）、BL-045（同セッションで発見） |
| 関連 | なし |

**内容:**

BL-045修正後の再開ドライラン（`log/2026-07-22/2300`）をユーザーが継続レビューし、「Expertの思考とiter番号が同じループになっているログが見える」と報告。調査の結果、`🧰 tools attached`が2回連続で印字され間に何のログもないまま`思考（iter=1）`に巻き戻る箇所（`cela_main.py`該当行）を確認した。

真因は、`_query_AI_live`の`for attempt in range(len(delays)+1):`（BL-009の既知のリトライ設計）がツール呼び出しループ全体（`for iteration in range(1, MAX_TOOL_ITER+1):`）を内包しており、途中でAPIエラーが起きても**最後の試行を使い切るまでは何も表示せず**`time.sleep`するだけで`loop_messages`/`python_calls_log`をサイレントに破棄しiter=1からやり直していたこと。BL-009策定当時は`write_agreement`にDB副作用（R4のホワイトボード版管理）がなかったため「粗いリトライ粒度」として許容されていたが、現在はこの巻き戻りが`write_agreement`成功後に起きると重複バージョン書き込み等の実害リスクがある。

**実装:**

中間リトライ発生時にもログ出力を追加（`🔄 [{label}] 一時的なAPIエラー、{delay}秒後にツールループを最初からやり直します（attempt N/6）: {エラー内容}`）。リトライ時に`loop_messages`を破棄せず継続する（重複書き込みリスクの本質的解消）設計変更は、より大きめの変更のためユーザー判断により今回は見送り、可視化のみ対応。

**完了条件:**

- オフラインスモークテスト（既存74件）が非退行でPass。
- （見送り分）`loop_messages`を保持したままリトライする設計は、`write_agreement`の重複書き込みが実ドライランで実害として確認された場合に着手する。

---

### BL-047: `write_agreement`の`depends_on`パラメータの意味衝突（agreements DBの数値IDかtask_id文字列か）でAIが毎回同じエラーを起こす

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 関連 | なし |

**内容:**

ドライラン（`log/2026-07-22/2320`）で、Expert/User AIが`write_agreement`呼び出し時に`"depends_on": ["task_1_1"]`を指定し`{'success': False, 'error': 'depends_onに存在しないID: task_1_1'}`で失敗、1往復無駄にしてから`depends_on`を除去して再送する事故を2回確認した。

真因は、`WRITE_AGREEMENT_TOOL`スキーマの`depends_on`（`cela_main.py`）に説明文が一切なく、コード側の検証（`_write_agreement_impl`）は`agreements`テーブルの数値行ID（AIに提示される【決定事項DB】表示の`[42]`等）を期待する一方、AIが日常的に目にしているのはtask_planner側のタスク定義の`depends_on`（`task_id`文字列を指す全く別概念、例：`"depends_on": ["task_1_1"]`）であり、同名フィールドの意味衝突がAIを誤誘導していたこと。

**実装:**

`depends_on`のdescriptionに、agreements DBの数値ID（決定事項DB表示の`[N]`）を使うこと・task_idを入れてはいけないこと・不明なら省略してよいことを明記。

**完了条件:**

- オフラインスモークテスト（既存74件）が非退行でPass。
- 実LLM再ドライランで、同種のエラーが再発しないことを確認する（次回待ち）。

---

### BL-048: reflection/facilitatorの周期発火を新設`round_count`で復旧する（`turn_count`本体は未修正）

| 項目 | 内容 |
|------|------|
| 状態 | `done`（reflection発火の症状のみ復旧。BL-005本体＝`turn_count`自体の意味修正は未着手） |
| 優先度 | P1 |
| 依存 | [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)、[D-039](../decision_log.md#d-039-ドライランの一時停止再開をappstreamによるノード単位チェックポイントで実装するターン境界方式は不採用)（ラウンド定義を踏襲） |
| 関連 | `docs/design/r5/cela_r5_design_v2.md` §1.3（F-2.1拡張、でっちあげ検出の設計） |

**内容:**

実ドライラン（`log/2026-07-22/2336`）で、task_2_1のacceptance_criteria自体に含まれる数学的矛盾（山間部12km・時速20km/h前提では30分以内は不可能）に対し、Expertが根拠のない内訳（勾配区間8km＋平坦区間4km、複数パターンを逆算して境界値を選定）ででっち上げて帳尻を合わせ、Detectorも自身の推測（「中心部の半径2kmだから4kmは平坦なはず」）で追認してしまう事例をユーザーが発見。

ユーザーが、このお題自体が構想初期にGeminiとの壁打ちで「あえて無理な制約を与えAI達がどう格闘するか見る」という趣旨で発案されたものであり、CELA前身プログラムの会話ログをGeminiに読ませた際にも同じ指摘（AIが適当にでっちあげる）を受けていたこと、「3ターンに一回reflectorが会話ログを見て、適当にでっちあげていないか？と制約違反を見つけていた記憶がある」という経緯を共有した。実際、`docs/design/r5/cela_r5_design_v2.md` §1.3にはこの現象（「計算ツールを使っていないのに適当な数字を出している」「都合の悪い制約から意図的に目を逸らして結論を急いでいる」）を検出する思考ログ監査の設計が既に存在していた。しかし`route_after_expert_decision`のreflection発火判定（`state["turn_count"] % state["reflection_interval"] == 0`）はBL-005（`turn_count`はグラフ内部ループでは更新されず凍結し得る）の影響で実質的に一度も成立せず、reflection自体が発火していなかった。

Web検索ツールを与えて実在地域のデータで裏取りする代替案も検討したが、「地図情報なしで推論から妥当な数値を探る」という今回のお題の実験条件自体が崩れるため、まずreflection復旧を優先する方針とした（詳細は[decision_lineage.md 論点46](../decision_lineage.md)）。

**実装（`cela_main.py`）:**

1. `LineageState`に`round_count: int`を新設（`turn_count`本体には手を加えない、影響範囲最小化）。
2. `generate_user_utterance_node`（BL-044で確認済みの「ラウンド」定義における各ラウンドの起点）への再入場のたびに`round_count`をインクリメント。
3. `route_after_expert_decision`のreflection発火条件を`round_count % reflection_interval == 0`に変更。
4. `call_reflection`のプロンプトに、`cela_r5_design_v2.md` §1.3の趣旨（根拠のない数値のでっち上げ、都合の悪い制約からの逃避、Detector自身の無根拠な追認）を反映した「でっちあげ監査」ブロックを追加。ただし同節が前提とする`internal_thought_process`（reasoning content）の全経路キャプチャ・配線は別途大きめの変更となるため、今回は既存の`chat_history`/決定タイムラインのみを材料にした軽量版とした（フル版=F-2.1本体は別途判断）。

**完了条件:**

- オフラインスモークテスト（既存74件）が非退行でPass。
- 実LLM再ドライランで、`round_count`ベースのreflection/facilitatorが実際に周期発火することを確認する（次回待ち）。 → **確認済み**（`log/2026-07-23/1336`〜`1656`にわたり複数回発火）。
- reflectionの「でっちあげ監査」が実際に今回のようなパターンを検出できるかを確認する（次回待ち）。フル版（F-2.1、`internal_thought_process`配線）が必要かはこの結果を見て判断する。 → **確認済み・軽量版で十分機能**。`log/2026-07-23/1656`で、Expertが与条件「山間部平均時速20km/h」を無断で28.8km/hに変更したまま帳尻を合わせていた事例をreflectionが`aligned=False, status=stagnant`（ゴール・ドリフト検出）として正しく捕捉し、`drift_flag=True`経由でExpert/User AIへの差し戻しにも実際につながった（軽量版＝chat_history/決定タイムラインのみで検出できており、フル版internal_thought_process配線は現時点で不要と判断）。

---

### BL-049: F-2.6検算ゲートによる注意力の偏りを是正する — 数値検算とドメイン妥当性レビューの分離

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [D-041](../decision_log.md#d-041-f-26検算ゲートによる注意力の偏りを是正するためdetectoruser-aiexpertの数値検算とドメイン妥当性レビューを分離する) |

**内容:**

ドライラン（`log/2026-07-22/2336`）継続レビュー中、ユーザーが「計算ツールを入れたことによりすべてのノードが計算が合っているかに思考が引き寄せられて、逆に重大な事を出力に反映できていません。例えばいま、バスは2台で監視員は2名です。これはバスは物理的におそらく不可能で、監視員は2名は労基法や休憩時間的に成り立ちません」と指摘。

ログ調査の結果、task_1_1では「オペレーター人件費：3名（シフト制）×400万円」と計算していたのに、task_2_2では同じ絶対制約（最低2名常駐）から「2名常駐」を額面通りの固定人数として再計算しており、両者とも算数としては（それぞれの前提の下で）正しく通過していたため、task間の矛盾として一度も検出されていなかったことを確認した。根本原因は、`call_detector`のconstraint_issue定義・major判定基準（`cela_main.py`）が「検算の結果、明白な数値矛盾や計算ミスが確認された場合」に強く偏っており、F-2.6（機械的検算ゲート）導入以降、Detectorをはじめ各ノードの注意力が「数式が正しいか」に集中し、非数値的な現実妥当性（労基法、物理的運用可能性、予備・冗長性）を評価する指示が実質存在しなかったこと。

**ユーザーによる範囲拡張:**

AIは当初Detectorのみを2段構成に分割する案（または新規グラフノードとして分離する案）を提示したが、ユーザーが「detectorのみならずユーザーやエキスパートも同様に思考の偏りが出ないようにしなければならない。ログをみているとdetector、ユーザー、またdetectorと同じ検算を3回4回と繰り返している場面もあるので、ユーザーはdetectorの検算を信じてドメイン評価に重きを置き、どうしても気になる場合は検算をする」と指摘し、範囲をUser AI・Expertにも拡張。Detectorについては「数値評価とドメイン評価ととりあえず2段にするのはOK」と承認した。

**実装（`cela_main.py`）:**

1. `call_detector`: 既存の数値検算パス（python_repl付き、変更なし）に加え、独立したLLM呼び出しとして「ドメイン妥当性レビュー」パス（ツールなし、数値監査の結果を提示し「検算はやり直さなくてよい」と明示、法規制・物理的運用可能性・でっち上げ疑義等を評価）を新設。両パスのうちより重篤な`constraint_issue`（none<minor<majorの順）を採用し、コメントは両方を結合。
2. `generate_user_utterance`（User AI）: F-2.6検算指示を「Detectorが既に検算済みであり信頼してよい、よほど疑わしい場合のみ自分でも検算する」という内容に変更し、User AI自身の検算の繰り返しを減らしてドメイン評価に注意を振り向ける。
3. `call_expert`: F-2.6検算指示の直後に、検算とは独立した「ドメイン妥当性チェック」の自問（数式の辻褄合わせのための根拠のない内訳のでっち上げがないか、現実世界で本当に成立するか）を追加。Expertは自ら数値を導出する立場のため検算自体は省略しない。

**過検知の発見・修正:**

`tests/test_f26_detection.py::test_detector_no_false_positive_within_cap`（3試行とも上限内でnone/minor想定）を実行したところ、ドメイン妥当性レビューパスが「人員数・勤務時間の詳細が不明」を理由に3試行中1回`major`を誤って出力する過検知が発生（結果: `['major', 'minor', 'minor']`）。ドメイン妥当性レビューのプロンプトに「情報不足を理由にmajorにしない、与えられた情報の範囲内で具体的に矛盾を指摘できる場合のみmajor」という判定基準を明記し、再テストで解消を確認した（結果: 3試行ともnone/minor）。

**完了条件:**

- `tests/test_f26_detection.py::test_detector_no_false_positive_within_cap`・`test_detector_flags_numeric_contradiction_5_of_5`（実LLM呼び出し）で非退行を確認済み。
- 実LLM再ドライランで、task間のオペレーター人数矛盾（3名シフト制 vs 2名常駐固定）のような非数値的懸念を、ドメイン妥当性レビューパスが実際に検出できるかを確認する（次回待ち）。 → **確認済み**。`log/2026-07-23/1656`で、Expertが与条件「山間部平均時速20km/h」を無断で28.8km/hに変更した点をドメイン妥当性レビューが正しくmajor判定し、同じターンで数値監査パスは別途Expert自身の検算コード内のハードコードバグ（`hd_hill_normal=60/2`固定）を独立に発見（正解25.7分に対しExpertの主張は30.7分・30.0分と誤り）。ドメイン軸・数値軸それぞれが異なる種類の欠陥を独立に捕捉しており、BL-054（ドメイン先行）と合わせて2軸分離の設計意図通りに機能していることを確認。
- Detectorの呼び出しコストが実質2倍になる点は許容済み（ユーザー承認）だが、トークン消費の実測値は次回ドライランで確認する。

---

### BL-050: `decision_extractor`の役割転換（抽出役→理由監査役）＋決定事項の変遷履歴の可視化

| 項目 | 内容 |
|------|------|
| 状態 | `partial`（完了条件1・2は実装済み。役割転換は未着手） |
| 優先度 | P2 |
| 依存 | [BL-037](issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない)、[BL-043](issue_backlog.md#bl-043-decision_extractorのjson出力をfunction-calling方式に作り替え既存の自己修復ループd-009に一本化する) |
| 関連 | [D-041](../decision_log.md#d-041-f-26検算ゲートによる注意力の偏りを是正するためdetectoruser-aiexpertの数値検算とドメイン妥当性レビューを分離する)（役割分担の考え方が地続き） |

**内容:**

ドライラン（`log/2026-07-22/2336`）継続レビュー中、車両台数が「task_1_1で3台」→「task_4_1の指示で2台」に変わった経緯をDetectorが辿れず、実際に「車両台数が2台になった理由は何か？なぜ3台から2台になったのか経緯は監査対象外の履歴に含まれている可能性があります」と困惑した末、根拠を確認できないまま「Userが確定値と言っている以上、調整済みと解釈できる」と流してしまう場面を確認した（`log/2026-07-22/2336/log_no_prompt.md` 18652〜18692行）。

調査の結果、`write_agreement`のSUPERSEDEは実際には旧レコードを`status='Superseded'`にして**残す**（削除しない）方式であり、履歴自体は失われていないことが判明した。実質的な欠落は以下の2点：
1. Detectorに提示する`【決定事項DB】`コンテキスト（`_build_agreements_context`）が有効な行（`status != "Superseded"`）だけに絞り込まれ、過去版を見せない。
2. `write_agreement`の`reason_why`が「前の値から何故変わったか（差分の理由）」を明示することを要求されておらず、新しい値単体の妥当性しか記述されない。

BL-037（`reason_why`の記載品質が薄い、既存）と同系統だが、「変遷の可視化」という点で更に踏み込んだ課題。

**ユーザー提案:**

`decision_extractor`を「新規決定を抽出する」役割から「各ノードが自ら`write_agreement`で出した決定の`reason_why`が実際に妥当な理由になっているか監査する」役割へ軸足を移してはどうか、という提案。各ノードが自律的にツールで決定を書き込む現行アーキテクチャ（R3b以降）では、`decision_extractor`本来の「抽出」という役目は縮小傾向にあり（BL-034で既に指摘済みの傾向）、この提案は自然な延長線上にある。

**完了条件（着手時）:**

- `【決定事項DB】`コンテキストに、SUPERSEDEされた直前versionとその`reason_why`を差分表示する仕組みを追加する（Detectorが「前は何だったか」を即座に参照できるようにする）。
  → **確認済み（2026-07-23実装）**: `_build_agreements_context`（`cela_main.py`）に、同一topic・entry_typeの直近1件のSuperseded行を「└ (前版 Superseded): {内容} — 当時の理由: {理由}」として追記する処理を追加。あわせて現行行自身のreason_whyも「（理由: ...）」として表示するよう変更（従来はreason_why自体がこのコンテキストに一切出ていなかったため、変更理由の可視化にはこちらも必要と判断）。オフラインテスト`tests/test_bl041_bl050.py`で確認。
- `write_agreement`のUPDATE/SUPERSEDE時、`reason_why`に「前の値から何故変わったか」の明示を求めるスキーマ・プロンプト変更を検討する。
  → **確認済み（2026-07-23実装）**: `WRITE_AGREEMENT_TOOL.reason_why`のdescriptionおよびdecision_extractor抽出プロンプトの共通ルールに、UPDATE時は「前の値から何故・どう変わったか」を明示する要求を追加（`cela_main.py`）。実ドライランでの記載品質向上は別途要確認（プロンプト指示であり強制ではないため）。
- `decision_extractor`の役割転換（抽出役→理由監査役）は、BL-043（Function Calling化）の設計確定と合わせて具体化する。→ 今回のスコープ外、未着手のまま。

---

### BL-051: Detectorの気づきを`issue_bl`リストとして蓄積し、フェーズ終了条件とする

| 項目 | 内容 |
|------|------|
| 状態 | `open`（`observations`自由記述欄は暫定のつなぎ実装。issue_bl構造化リスト＋フェーズ終了ゲートという本来の方針自体は変更せず維持） |
| 優先度 | P2 |
| 依存 | [BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている) |
| 関連 | [BL-049](issue_backlog.md#bl-049-f-26検算ゲートによる注意力の偏りを是正する-数値検算とドメイン妥当性レビューの分離)（Detectorの出力拡張と自然に統合できる） |

**内容:**

Detectorは思考過程（`💭 [Detector] 思考`のログ）で数多くの重要な懸念（数値の根拠不明、ドメイン的な違和感等）に気づいているが、現行の出力形式が`{risk, constraint_issue: none/minor/major, comment}`という単一判定に集約されるため、致命的でない（`major`にはしない）気づきは`comment`欄に埋もれるかそもそも捨てられ、次のターンへ引き継がれない。

ユーザー提案：Detectorの気づきを、このプロジェクト自身の`issue_backlog.md`と同じ発想の構造化リスト（例: `{id, severity, description, resolved: bool, phase_id}`）として蓄積する。フェーズの終了は、このissue_blリストが解消される（全件`resolved`になる）までは完了できないゲートとし、この監視はUserとDetector双方が担う。もし解消せずに次フェーズへ進む（延期する）場合は、明確な理由が必須。

**暫定のつなぎ実装（`cela_main.py`、2026-07-23、あくまで一時対処）:**

本来の方針（issue_bl構造化リスト＋フェーズ終了ゲート）はユーザーの明示的な指示により変更しない。設計未確定・大きめの構造変更であることも変わらないため、下記は「気づきが完全に失われる」状態を当面緩和するだけの暫定的なつなぎであり、本Issue自体は`open`のまま据え置く：

- `call_detector`の数値監査パス・ドメイン妥当性レビューパスの両方の返却JSONに`observations`（自由記述、無ければ空文字）を追加。`constraint_issue`の判定（none/minor/major）とは独立した任意項目とし、判定を左右しないことをプロンプトで明示。
- `LineageState`に`detector_observations_log: list[dict]`を新設。`detector_node`で、`constraint_issue`の値に関わらず（`none`の回も含めて）`observations`が非空であれば`{turn, target_role, observations}`として蓄積する（既存の`constraint_issue_log`はminor/majorの回のみ蓄積する点で異なる）。
- 新規ヘルパー`_build_detector_observations_block`を追加し、`call_expert`・`generate_user_utterance`の両システムプロンプトに、直近3件の気づきを「参考情報（判定を左右するものではない）」として毎ターン提示するよう変更。従来の`constraint_issue_log`表示は差し戻し（`constraint_issue=="major"`）時のみだったのに対し、この気づき欄は差し戻しの有無に関わらず常時提示される点が異なる。

**設計上の論点（本来の方針・未確定のまま）:**

- issue_blエントリの永続化先（新規DBテーブル or `state`内リスト）。
- 「フェーズ終了をブロックする」ロジックをどのグラフノード・ルーティング関数に実装するか（BL-041のfacilitator/Arbiter再設計と同格の構造変更になる見込み）。
- 暫定実装の`observations`ログを、本来の方針のissue_bl候補（`resolved`管理・フェーズゲート対象）へどう昇格させるか、あるいは別物として並存させるか。

**完了条件（着手時）:**

- まず設計ドラフト（BL-041の`cela_facilitator_arbiter_redesign_BL041.md`のような形式）を作成し、ユーザー確認を経てから実装に着手する。この本来の方針の完了条件は暫定実装の追加によって変わらない。

**暫定実装の検証状況（参考）:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト（`test_r3_smoke.py`/`test_r4_smoke.py`/`test_checkpoint_resume.py`計71件）Pass。
- 実LLM再ドライランで、`none`判定の回でもDetectorの気づきが`detector_observations_log`に蓄積され、後続ターンのUser AI/Expertプロンプトに提示されることを確認する（次回待ち）。

---

### BL-052: ホワイトボード本文に決定/理由DBへのインラインID参照を埋め込む

| 項目 | 内容 |
|------|------|
| 状態 | `open`（設計相談・BL起票のみ） |
| 優先度 | P3 |
| 依存 | [BL-047](issue_backlog.md#bl-047-write_agreementのdepends_onパラメータの意味衝突agreements-dbの数値idかtask_id文字列かでaiが毎回同じエラーを起こす)（数値ID検証パターンの転用元） |
| 関連 | [BL-050](issue_backlog.md#bl-050-decision_extractorの役割転換抽出役理由監査役決定事項の変遷履歴の可視化)、[BL-051](issue_backlog.md#bl-051-detectorの気づきをissue_blリストとして蓄積しフェーズ終了条件とする) |

**内容:**

ホワイトボード（`whiteboard_drafts`）の各文・意味のまとまりに、それを裏付ける決定・理由のDB行を指す参照（例:`[AG:123]`のような`agreements.id`への参照）をExpertに明示させる提案。BL-050で指摘した「この数値の根拠は？」という調査コストを、本文に埋め込まれた参照で即座に解消できる狙い（ユーザー提案）。

BL-047で実装済みの`depends_on`の数値ID検証（agreements DBに実在する行IDかをチェックし、存在しなければエラーを返す）パターンがそのまま転用できる見込み。リスクは、①AIが実在しないIDを捏造する可能性（BL-047と同様の検証が必要）、②本文にタグが増えることによる可読性の低下、の2点。

BL-050（理由監査役）・BL-051（issue_bl）とセットで設計するのが筋が良い（ID実在チェックはdecision_extractor監査役の担当範囲に自然に乗る）という方針。

**完了条件（着手時）:**

- `WRITE_AGREEMENT_TOOL`の`decision_what`（Deliverable本文）または`edits`内で、インラインID参照の記法（例:`[AG:123]`）を定義する。
- BL-047の`depends_on`検証と同様、ID実在チェックを`_write_agreement_impl`または`decision_extractor`監査役に実装する。
- BL-050・BL-051の設計確定後、まとめて着手するか個別に着手するかを判断する。

---

### BL-053: `get_verified_facts_from_db`のtopic_keyword検索が`variable_name`列しか見ておらず、日本語キーワードで構造的にほぼ一致しない

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [BL-040](issue_backlog.md#bl-040-read_deliverable_fileがfile_path直接指定に依存し実質的に発見不能だった問題)（同種の「発見不能性」問題、`read_deliverable_file`側は解決済み） |

**内容:**

ドライラン（`log/2026-07-22/2336`）で、`read_verified_fact`/`read_deliverable_file`呼び出し44回中18回（41%）が`not_found`になっていることをユーザーが指摘した。

調査の結果、`get_verified_facts_from_db`（`cela_main.py`）の`topic_keyword`によるあいまい検索が

```python
"SELECT * FROM verified_facts WHERE run_id=? AND variable_name LIKE ?"
```

と`variable_name`列のみを対象にしていたことが真因と判明。`variable_name`は`vehicle_count`のような英語スネークケース識別子だが、`READ_VERIFIED_FACT_TOOL`のツール定義自体が`topic_keyword`の例として「'車両', '予算', '需要'」という日本語の説明的キーワードを挙げており、AIが実際に渡す値もほぼ日本語。両者が文字列として重なることは構造的にほぼ無く、"予算"・"オペレーター"・"通信"・"システム構築費"等の日本語キーワード検索がログ上ほぼ全て`not_found`になっていた。`verified_facts`テーブルには日本語理由文が入る`reason`列（`upsert_verified_fact`で保存済み）が既に存在するのに、検索対象に含まれていなかった。

**実装（`cela_main.py`）:**

`variable_name LIKE ? OR reason LIKE ?`のLIKE検索に変更し、`reason`列も検索対象に含めた。

**完了条件:**

- `tests/test_r3_smoke.py`に回帰テスト`test_bl053_get_verified_facts_topic_search_matches_japanese_reason`を追加（日本語`topic_keyword`「予算」で`reason`列にのみ「予算上限」を含む`variable_name`をヒットさせられることを確認）、既存テストと合わせてPass。
- 実LLM再ドライランで、`read_verified_fact`の`not_found`率が改善することを確認する（次回待ち）。

---

### BL-054: Detectorの2段監査パスの実行順序をドメイン監査→数値検算に変更

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | BL-049 |
| 関連 | [BL-049](issue_backlog.md#bl-049-f-26検算ゲートによる注意力の偏りを是正する-数値検算とドメイン妥当性レビューの分離), [D-041](../decision_log.md) |

**内容:**

BL-049でDetectorを「数値検算パス（python_repl付き）→ドメイン妥当性レビューパス（ツールなし、数値監査結果を提示し再検算不要と明示）」の2段構成に分離したが、ユーザーが実行順序自体を問題視した：検算を先に行うと、その「数値は合っている」という結果に評価者の注意が引きずられ、そもそもの前提・設計（車両台数、人数配置、シフト等）が現実世界で成立するかというドメイン的な観点が後回し・軽視されやすい。前提・設計そのものの妥当性は検算の結果とは無関係に、まず独立して確認されるべきという指摘。

**実装（`cela_main.py::call_detector`）:**

- `domain_prompt`を数値監査より先に構築・実行する順序へ変更。プロンプト文言から「数値の機械的検算は既に別プロセス（数値監査パス）で完了済みです」という、数値監査が先に終わっている前提の言及を除去し、代わりに「前提・設計自体に無理がないかをまず確認する」役割を明記。
- 数値検算用の`prompt`（メインの`risk`/`constraint_issue`/`criteria_status`判定）は、ドメイン監査の結果（`domain_constraint_issue`/`domain_comment`）を`domain_findings_block`として提示した上で実行するよう変更。ドメイン監査で前提自体に矛盾が指摘されている場合、それを踏まえた検算をするよう指示。
- 統合ロジック（より重篤な判定を採用）自体は変更なし。表示上のcomment順序のみ「ドメイン妥当性レビュー」を先に、「数値監査」を後に並べ替え。

**完了条件:**

- `python -m py_compile cela_main.py`合格。
- 実LLM再ドライランで、ドメイン妥当性レビューが数値検算に先行して行われ、前提・設計上の懸念がこれまで以上に拾われることを確認する（次回待ち）。

---

### BL-055: 「真の制約」と「見直し可能な条件」を区別して思考する指示をUser AI/Expertに追加

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | なし |
| 関連 | BL-054（同ドライランの発見） |

**内容:**

BL-054のドライラン（`log/2026-07-23/0919`）継続レビューで、ユーザーが「車両費2,500万円が確定事項となっているが、予算1億円は確定としてもAIが2,500万円（中古やリースなどでは下げることが可能）に引っ張られすぎている」と指摘。ログを確認したところ、Expertは「4台の枠内でどう配分するか」という組み合わせ探索（案1〜7）は行っていたが、「単価2,500万円」という前提自体を疑う発想（中古・リース・共同調達等でコストを下げ、5台目を確保する等）には至っていなかった。原因は、ゴール文中で「予算上限1億円」（動かせない真の制約）と「車両単価2,500万円」（議論の前提として与えられた例示的条件）が区別なく並記されており、AIにはこの2つを見分ける手がかりが与えられていなかったこと。

**実装（`cela_main.py`）:**

ユーザー指示により、特定の数値（車両単価）に限定せず一般化した指示として、`call_expert`・`generate_user_utterance`双方のシステムプロンプトに以下を追加：

- `call_expert`：既存の「制約が厳しい場合こそ抜本的な代替案を」という行動原則の直後に、「ゴール文には動かせない真の制約（総予算・法規制・安全基準等）と、見直し可能な前提条件（特定の調達方法を前提にした単価等）が区別なく並記されていることがある。行き詰まった場合は思考停止で条件を鵜呑みにせず、都度どちらかを見極め、見直し可能な条件であれば前提自体を疑い代替案を提案してよい（ただし真の制約自体の緩和は不可）」という趣旨のブロックを追加。
- `generate_user_utterance`：既存の「制約緩和の要求は却下せよ」という発注者としてのスタンスの直後に、却下する前に相手の要求が「真の制約」への緩和要求なのか「見直し可能な条件」への疑義なのかを自ら見極め、後者であれば却下ではなく前提の見直しを検討させる指示に切り替えるという趣旨のブロックを追加。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト（`test_r3_smoke.py`/`test_r4_smoke.py`/`test_checkpoint_resume.py`計71件）Pass。
- 実LLM再ドライランで、AIが与えられた単価等の前提条件を疑い代替調達案を検討する場面が生じるかを確認する（次回待ち）。

---

### BL-056: Reflectionプロンプト内の表示を凍結したturn_countからround_countへ統一

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 依存 | BL-048 |
| 関連 | [BL-048](issue_backlog.md#bl-048-reflectionfacilitatorの周期発火を新設round_countで復旧するturn_count本体は未修正), [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離) |

**内容:**

ドライラン（`log/2026-07-23/1122`）でReflectionが発火した際、プロンプトの末尾に表示される進行状況が「全30ターン中1ターン目」のままだったため、Reflection自身が直近の実際の会話量（複数回のExpert⇄Detector⇄User AIのやり取り）との矛盾に気づき、「注意：現在は全30ターン中1ターン目？これはおかしい。」と自ら混乱する様子をユーザーが発見。

原因はBL-048/D-040で、reflectionの**発火条件**自体は`turn_count`（BL-005で凍結）から`round_count`へ切り替え済みだったが、`call_reflection`の**プロンプト内の表示**（`⏳ 現在は 全 {max_turns} ターン中 {turn_count} ターン目 です。`）は据え置かれたままturn_countを参照し続けていたこと。発火条件と表示の基準が一致していなかったため、周期的に正しく発火しているにもかかわらず、Reflection自身に提示される情報だけが実態と乖離していた。

**実装（`cela_main.py::call_reflection`）:**

- プロンプト内の表示を`round_count`（＋`reflection_interval`との対応関係の説明）に置き換え、「ターン」は内部のやり取り往復の途中で足踏みしうるため代わりに「ラウンド」（User AI発言サイクルの周回数）を進行状況の目安として使っている旨を明記。
- 表示に使わなくなった`max_turns`のローカル変数取得を削除。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト（`test_r3_smoke.py`/`test_r4_smoke.py`/`test_checkpoint_resume.py`計71件）Pass。
- 実LLM再ドライランで、Reflectionが表示された進行状況と実際の会話量の矛盾を訴えなくなることを確認する（次回待ち）。
- なお、`turn_count`自体の意味（BL-005）や、差し戻しを含めた「やり取り数」の正式な定義（指標C計測、BL-023）は本Issueのスコープ外として据え置く。

---

### BL-057: ツールループ残り回数通知のしきい値を前倒し（BL-016の追加調整）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-016 |
| 関連 | [BL-016](issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする), BL-028（MAX_TOOL_ITER 10→15引き上げ） |

**内容:**

BL-016で導入した「ツール呼び出しの残り回数が僅少になった時点で通知し、次の応答で打ち切るよう促す」仕組み（`_query_AI_live`、`remaining_iters <= 2`で発火）は、通常のタスクでは有効だったが、ドライラン（`log/2026-07-23/1256`）で「4台制約下では解が存在しない」という組合せ最適化的な問題に対しExpertが速度・定員・運行方式・予算配分の複数代替案を数値的に検討し続けたケースで、非収束クラッシュ（MAX_TOOL_ITER=15到達によるRuntimeError）が発生した。成果物自体は差し戻し前の`write_agreement`で既に保存されていたため実害は限定的だったが、最終回答（成果物の書き出しを含む長文）を書き切るには「残り2回」の通知では猶予が足りなかったとユーザーが指摘。

**実装（`cela_main.py::_query_AI_live`）:**

- 通知の発火しきい値を`remaining_iters <= 2`から`remaining_iters <= 3`に前倒しし、最終回答を書き切るための猶予を1往復分増やした。
- 残り1回の場合の通知文言を、単なる推奨から「これ以上ツールを呼ばず、次の応答で必ずテキストのみの最終回答を出力してください。中断すると非収束エラーになり、この応答自体が失われます」というより強い断定的な指示に強化した。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト（`test_r3_smoke.py`/`test_r4_smoke.py`/`test_checkpoint_resume.py`計71件）Pass。
- 実LLM再ドライランで、組合せ最適化的に長時間探索するタスクでも非収束クラッシュせず最終回答を返せることを確認する（次回待ち）。 → **本修正だけでは不十分と判明**。直後の`log/2026-07-23/1453`で、通知（残り1回）を提示したにもかかわらずExpertが最終iterationでもツール（`write_agreement`）を呼び出し、非収束クラッシュが再発。通知は依頼に過ぎず強制力がないという限界が明らかになり、構造的にツール呼び出しを不可能にするBL-060を追加実装した。

---

### BL-058: python_replの許可モジュールにitertools等の純粋計算ユーティリティを追加

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | D-007（fractions/decimal追加の先例、同じ承認プロセス） |

**内容:**

ドライラン（`log/2026-07-23/1256`）で、Expertが「4台制約下では解なし」問題の組合せ探索（速度・定員・台数配分の総当たり検討）の途中で`import itertools`を試みたが、`_ALLOWED_IMPORTS`ホワイトリスト（`cela_main.py:378`）に含まれておらず`[REPL Error] import of 'itertools' is not allowed`で拒否され、ツール呼び出し1回を無駄にしていたことをユーザーが発見。「サンドボックスから抜け出せないような標準的なツール群は許可したらどうか」と提案。

AGENTS.md§7（定数変更は事前承認必須）に従い、AIから追加候補（I/O・ファイルシステム・OS・ネットワークアクセスを一切持たない純粋計算・データ構造ユーティリティ: `itertools`, `functools`, `collections`, `operator`, `re`）を提示し、AskUserQuestionでユーザーが「まとめて追加」を選択。

**実装（`cela_main.py`）:**

`_ALLOWED_IMPORTS`に`itertools`, `functools`, `collections`, `operator`, `re`の5モジュールを追加。いずれも既存のサブプロセス分離＋AST危険呼び出し検査（D-006）のサンドボックス境界を拡張しない（ファイル・OS・ネットワークアクセスの手段を一切提供しない）ことを確認済み。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト計71件Pass。
- `_check_repl_code_safety`/`_run_python_repl`で`import itertools`が実際に許可され動作することを手動確認済み。
- 実LLM再ドライランで、組合せ探索的なタスクで`itertools`等が実際に活用されることを確認する（次回待ち）。 → **未確認**。`log/2026-07-23/1336`（13:36開始、本修正の実装より前のプロセス）では依然`itertools`が拒否されており、修正後に新規開始したセッション（`1358`/`1453`/`1656`）ではExpertが`itertools`系の探索自体を行わなかったため、修正後の実際の許可・活用はまだ観測できていない。次回、組合せ探索的なタスクが発生した際に確認する。

---

### BL-059: streaming受信中のhttpx.RemoteProtocolErrorが未捕捉でプロセスクラッシュする

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | なし |
| 関連 | [BL-022](issue_backlog.md#bl-022-openrouterの壊れたレスポンスによる生jsonjsondecodeerrorがd-009の絞り込んだexceptを素通りしクラッシュ), D-019（同種修正の前例） |

**内容:**

ユーザーがドライラン中の実際のクラッシュ（トレースバック）を報告。`detector_node`→`call_detector`→`_query_and_parse_with_retry`→`query_AI`→`_query_AI_live`の`for chunk in stream:`（streaming応答の受信ループ）実行中に、OpenRouter経由のプロバイダ側が完全なメッセージボディを送らずに接続を切ったことで、`httpcore.RemoteProtocolError`が`httpx.RemoteProtocolError`としてopenai SDKの外側（`_query_AI_live`本体）まで生の形で伝播し、`(APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError)`という絞り込んだ例外タプルのどれにも一致せず未捕捉のままPythonプロセス全体をクラッシュさせた。

BL-022（`response.json()`内部で送出される生の`json.JSONDecodeError`が同じ理由で漏れていた事例）と全く同型の問題で、いずれも「一時的なAPI/接続障害はリトライ対象、ロジックエラーは即座に伝播」というD-009の意図には前者（一時的障害）に該当するにもかかわらず、例外タプルの絞り込みが狭すぎたことが原因。

**実装（`cela_main.py`）:**

- `import httpx`を追加。
- `_query_AI_live`の例外タプルに`httpx.RemoteProtocolError`を追加し、リトライ対象化。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト計71件Pass。
- 実LLM再ドライランで、同種の接続切断が発生してもプロセスがクラッシュせずリトライされることを確認する（次回待ち）。 → **未確認**。修正後の`log/2026-07-23/1358`/`1656`では`httpx.RemoteProtocolError`自体が再発していないため、キャッチ・リトライが実際に機能するかはまだ実例で確認できていない（コードレビュー上は例外タプルへの追加のみで確実に捕捉されるはずだが、実地での再発待ち）。

---

### BL-060: ツールループ最終iterationでのツール呼び出しによる非収束クラッシュ

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-016, BL-057 |
| 関連 | [BL-016](issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする), [BL-057](issue_backlog.md#bl-057-ツールループ残り回数通知のしきい値を前倒しbl-016の追加調整) |

**内容:**

BL-057で「残り回数」通知のしきい値を前倒し（残り3回・2回・1回で通知）したにもかかわらず、ドライラン（`log/2026-07-23/1453`）でExpertが最終許容iteration（15回目、MAX_TOOL_ITER到達）でも`write_agreement`ツールを呼び出し（成功はした）、その後に「テキストのみの最終応答」を返す機会となる次のiterationが存在しないため、そのままMAX_TOOL_ITER非収束クラッシュに至った。

根本原因は、BL-016/BL-057の「残り回数」通知はあくまでプロンプト上の**依頼**に過ぎず、モデルが最終iterationでもツール呼び出しを選択すること自体を構造的に禁止していなかったこと。通知を強めるだけでは、モデルが指示に従わない限りいつでも同じ形でクラッシュしうるという限界があった。

**実装（`cela_main.py::_query_AI_live`）:**

ツールループの最終iteration（`iteration == MAX_TOOL_ITER`）でのAPI呼び出しのみ、`create_kwargs`から`tools`キーを除いた`call_kwargs`を使用するよう変更。ツールスキーマ自体を提示しないため、モデルは構造的にツール呼び出しができず、必ずテキスト応答（`msg.tool_calls`が空）が返る。これにより、既存の「`tool_calls`が空なら正常終了として`content`を返す」分岐（L1399〜）に必ず到達し、非収束クラッシュのraise文（L1495相当）は事実上到達しなくなる。

**完了条件:**

- `python -m py_compile cela_main.py`合格、既存オフラインスモークテスト計71件Pass（本クラッシュ経路に依存するテストは存在しないことを確認済み）。
- 実LLM再ドライランで、最終iterationまでツール呼び出しが続いた場合でもクラッシュせずテキスト最終応答が返ることを確認する（次回待ち）。 → **部分確認**。本修正適用後に開始した`log/2026-07-23/1358`（7,021行）・`1656`（3,141行、継続中）のいずれも非収束クラッシュ（Traceback・「非収束」ログ）が0件。ただし「最終iterationで実際にツール呼び出しが発生し、tools除去で救済された」場面自体はまだ観測できていない（発生すれば確実に救済される設計だが、その発火自体の実例待ち）。

---

### BL-061: facilitatorがreflectionの判定理由を一切受け取れず、独立に（時に食い違う）状況判断をしていた

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（facilitatorのエスカレーション機構未実装という既存の指摘とは別種・より具体的な伝達漏れバグ）、[decision_lineage.md 論点59](../decision_lineage.md) |

**内容:**

ユーザーがドライラン（`log/2026-07-23/1656`、`log_no_prompt.md` 25134行目付近）で「facilitatorが発火した」と報告。ログを確認したところ、直前のreflectionが`still_aligned=false, discussion_status="stagnant"`と判定し、`note`に5点の具体的な未解決問題（山間部速度28.8km/hへの無断変更＝与条件違反、平坦部ルート長6.67kmのでっちあげ疑い、山間部需要88人の根拠不足、リース料480万円/台/年の類推値、待ち時間制約超過の先送り）を明記していたにもかかわらず、後続の`facilitator`自身の思考ログでは「現時点では議論が膠着しているわけではなく、順調にタスクが進行しています」「ファシリテーターの介入は、あえて必要ないかもしれません」と、reflectionの判定と明確に矛盾する独自の（より甘い）評価をしていたことを発見した。

実際に送信されたプロンプト（`log_with_prompt.md` 57021行目）を確認したところ、`goal`と直近10件の`chat_history`のみが含まれ、reflectionの`note`（具体的な5点の指摘）は一切含まれていなかった。コード側を調査した結果、`call_facilitator(goal, chat_history, decisions)`は`decisions`引数を受け取っているが、プロンプトテンプレート内では`goal`と`history_text`しか使われておらず、**`decisions`は完全に未使用（デッドパラメータ）**だったことを確認した。reflectionの判定理由（`result["note"]`）は`decisions`テーブルの`why`列にしか保存されず（`reflection_node`の`make_decision`呼び出し経由）、`state`上の直接のフィールドとしては存在しなかったため、facilitatorへは構造的に伝わりようがなかった。

facilitatorは「なぜ自分が呼ばれたか」を一切知らされないまま、直近のchat_historyだけから独自に状況を再判定するほかなく、今回はreflectionの深刻な判定と食い違う、的外れで弱いメッセージを生成する結果になった。さらに`facilitator_node`はこの1回の（内容が的外れであっても）介入だけで`drift_flag=False`・`discussion_status="continuing"`を無条件にリセットするため、reflectionが検出した未解決の問題は実質的に握り潰される構造になっていた。BL-041が既に指摘している「エスカレーション機構未実装」（reflectionの検出後の対応がDetectorのmajorと同じ一般的な差し戻しに留まる）とは別種の、より具体的な**伝達漏れ**バグである。

**実装（`cela_main.py`）:**

1. `LineageState`に`last_reflection_note: str`を新設（BL-038の教訓通り、TypedDictへの宣言漏れはノード間で値が消えるため必須）。
2. `reflection_node`が`result["note"]`をこのフィールドへ保存するよう変更。
3. `call_facilitator`のシグネチャを`(goal, chat_history, decisions)`から`(goal, chat_history, reflection_note="")`へ変更し、未使用だった`decisions`引数を、実際にプロンプトへ埋め込む`reflection_note`に置き換えた。プロンプトに「あなたが呼ばれた理由（直前のReflection監査の判定）」ブロックを追加し、「これを最優先の出発点として扱い、自分で独自に再判定してその理由を無視・軽視することは避けてください」という指示を追加。`reflection_note`が空（旧checkpointからの復帰等）の場合は「特筆すべき懸念なし」のフォールバック文言を使用。
4. `facilitator_node`の呼び出しを`call_facilitator(state["goal"], state["chat_history"], state.get("last_reflection_note", ""))`に変更（従来の`get_decisions_from_db(...)`呼び出しは不要になったため削除）。

**完了条件:**

- `python -m py_compile cela_main.py`合格、オフラインスモークテスト計82件Pass（新規`tests/test_bl061_facilitator_reflection_note.py`4件を含む: reflection_nodeが`last_reflection_note`を保存すること、`call_facilitator`のプロンプトに実際にreflection_noteの内容が含まれること、空の場合のフォールバック、`facilitator_node`が正しく引き渡すこと、をそれぞれ確認）。
- 実LLM再ドライランで、reflectionが深刻な問題を検出した際にfacilitatorのメッセージがその内容と整合する（独自に軽い判定へすり替えない）ことを確認する（次回待ち）。

---

### BL-062: Detector等の`major`判定・Rejected書き込みが、既存Agreementを構造的に上書き・無効化できない（write_agreement権限モデルの監査ガバナンス欠落）

| 項目 | 内容 |
|------|------|
| 状態 | `partial`（Detector限定で実装済み。Reviewer/Arbiter/Integratorへの拡張はBL-070として分離） |
| 優先度 | P1 |
| 依存 | [BL-034](issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)（decision_extractorの役目縮小傾向の指摘、同系統） |
| 関連 | [cela_r5_impl_Plan.md](../r5/cela_r5_impl_Plan.md)、[decision_log.md D-045](../decision_log.md#d-045-f-83-freeze機能を一時休止しbl-062をdetector限定で先に解消する)、[BL-070](issue_backlog.md#bl-070-supersede運用指示をreviewerarbiterintegratorにも拡張するかの検討)、[decision_lineage.md 論点61](../decision_lineage.md)・[論点64](../decision_lineage.md) |

**内容:**

R5実装計画（F-8.3 Freeze機能）の設計相談中、Freezeされた項目をDetectorが後から覆した場合どうなるかという議論の中で、ユーザーが「そもそもDetectorはユーザーまたはエキスパートの決定まで破棄できたか？」と根本的な疑問を提起した。

調査の結果、以下が判明した。

1. `_check_write_permission`（`ALLOWED_STATUS_BY_ROLE`）により、Detector/Reviewer/Arbiter/Integratorは`write_agreement`を`status='Rejected'`でのみ呼び出せる。
2. しかし、Detector等がこの`Rejected`書き込みを行う際、`target_topic`を指定してUser/Expertが既に書き込んだ対象の`Approved`/`Proposed`なagreementを`SUPERSEDE`/`UPDATE`する運用ガイドがプロンプト上どこにも存在しない（`target_topic`を使ったSUPERSEDE運用の指示は`decision_extractor`の抽出プロンプト側にのみ存在し、Detector自身の指示には無い）。
3. 実際には、Detectorの`major`判定が引き起こす効果は「差し戻し（再プロンプトによるExpert/User AIへの再考要求）」のみであり、`_build_agreements_context`が表示する「有効な」agreement一覧からは、Detectorに拒否された対象は自動的には外れない。Expert/Userが自発的に該当topicをSUPERSEDE/UPDATEしない限り、Detectorが「却下した」はずの内容がDB上は「承認済み」のまま残り続ける。

これは、R3b以降アーキテクチャが「各ノードが自律的に`write_agreement`で決定を書き込む」方式へ移行した副作用である。旧来のdecision_extractor中心アーキテクチャでは、「Detectorの監査を通過した会話ログからのみ決定を抽出する」という処理順序自体が暗黙の監査ゲートとして機能していたが、各ノードが監査前に直接DBへ書き込めるようになったことで、この暗黙の保証が構造的に失われている。BL-034が既に指摘した「decision_extractorの役目の縮小」と同根の問題だが、対象がより根本的な「監査によるDB内容のガバナンス」である点で区別する。

**実害:** 現時点で具体的な実データ破損は確認されていないが、Detectorが`major`判定を出しても、対応するAgreementがDB上「承認済み」のまま残り、後続タスクや最終統合（integrator）がこれを正当な確定値として参照し続けるリスクがある。F-8.3 Freeze機能は`user`ロールのみに権限を限定することで、この課題があってもFreeze自体の意味（恒久ピン留め）は損なわれないよう設計したが、Freeze対象でない通常のAgreement全般には本課題がそのまま残る。

**2026-07-24追記（解消・Detector限定）:** ユーザーがFreeze機能（D-044）とBL-062のどちらを優先するか再検討し、「検証手段のないままユーザー/AIの決定を絶対視するFreeze」より「Detectorの正しい否決がDBに反映されず永続化する矛盾」の解消を優先する判断をした（[D-045](../decision_log.md#d-045-f-83-freeze機能を一時休止しbl-062をdetector限定で先に解消する)）。実装前の再調査で、完了条件の①案（権限モデル拡張）は**そもそも不要**と判明した——`_check_write_permission`は`status`のみを制限し`action_type`は無制限で、Detector/Reviewer/Arbiter/Integratorは全員既に`WRITE_AGREEMENT_TOOL`を保有し`status='Rejected'`かつ`action_type='SUPERSEDE'`を呼べる権限を最初から持っていた。真の欠落は権限ではなく、(a) Detector等がそもそも既存agreements DBのtopic一覧をプロンプト上受け取っておらず`target_topic`を指定する材料がなかったこと、(b) SUPERSEDEを使えという運用指示がなかったこと、の2点だった。

`call_detector`に`_build_agreements_context_from_db`によるDBビューを新規注入し、`constraint_issue="major"`時にはwrite_agreementを`action_type="SUPERSEDE"`, `status="Rejected"`, `target_topic=<DBのtopic文字列>`で呼び出すよう明示的に指示する一文を追加した。Reviewer/Arbiter/Integratorは成果物全体審査・リソース配分・フェーズ横断統合という別種の役割であり、topic単位のSUPERSEDEが同じ意味を持つか自明でないため、ユーザーの判断で今回はDetector限定とし、他3ロールへの拡張検討はBL-070として分離した。

**完了条件:**

- ~~write_agreementの権限モデルを拡張するか、自動SUPERSEDE機構を追加するか、設計判断~~ → 権限は既に存在したため権限モデル変更は不要と判明。
- `call_detector`へのagreements DBビュー注入＋SUPERSEDE運用指示の追加 → `done`（本節参照）。
- Reviewer/Arbiter/Integratorへの同様の拡張 → BL-070として分離、未着手。
- BL-050の完了条件3（decision_extractorの役割転換）との統合検討は、引き続き保留。
- オフラインテスト`tests/test_bl062_detector_supersede.py`（4件）で配線を確認。`python -m py_compile`合格。実LLM再ドライランでの実発火確認は次回待ち。

---

### BL-063: R5実装（F-2.1拡張／F-3.7／F-8.3 Freeze／GoalShiftEvent）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [cela_r5_design_v2.md](../r5/cela_r5_design_v2.md)、[cela_r5_impl_Plan.md](../r5/cela_r5_impl_Plan.md)、[BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)、[BL-050](issue_backlog.md#bl-050-decision_extractorの役割転換抽出役理由監査役決定事項の変遷履歴の可視化)、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)、[decision_log.md D-044](../decision_log.md)、[decision_lineage.md 論点61](../decision_lineage.md) |

**内容:**

`cela_r5_impl_Plan.md`の計画通り、以下4機能を`cela_main.py`に実装した。

1. **F-2.1拡張（思考プロセス監査）**: `_query_AI_live`のstreaming処理が受け取る`delta.reasoning`を、従来は💭表示で印字するのみで破棄していたが、新規モジュールグローバル`_LAST_REASONING_TEXT`（`get_last_reasoning_text()`ゲッター、BL-033の`_LAST_PYTHON_CALLS`と同型パターン）へ蓄積するよう変更。`LineageState`に`expert_last_reasoning`/`user_last_reasoning`を新設し、`expert_node`/`generate_user_utterance_node`がそれぞれセット。`call_detector`に「思考プロセス監査」ブロックを追加し、target_roleに応じてExpert/User AIいずれかのreasoningを提示する（数値監査パスに配線、v2設計書§1.3）。
2. **F-3.7（思考ログの強制記録）**: `make_decision`に`internal_thought_process`パラメータを追加（既存呼び出しは省略可、後方互換）。トークンコスト抑制のため全件記録はせず、Detectorの`major`判定時・Reflectionの`stagnant`判定時・agreementsの`status='Rejected'`書き込み時のみ`get_last_reasoning_text()`をスナップショット保存する限定運用とした（v2設計書§2の方針通り）。
3. **F-8.3 Freeze機能**: 新規`freeze_agreement()`関数＋専用ツール`FREEZE_AGREEMENT_TOOL`（`agreement_id`, `reason`のみのシンプルなスキーマ、既存`WRITE_AGREEMENT_TOOL`は汚さない）を追加し、User AIのtoolsリストにのみ配線（`user`ロール限定、D-044）。`_commit_agreement_from_tool`のSUPERSEDE/UPDATE分岐に、対象行が`is_frozen==1`の場合は処理を拒否するガードを追加（unfreeze機構は設けない、恒久ピン留め）。`_build_agreements_context`に`is_frozen`優先のソートキーと🔒アイコン表示を追加。**2026-07-24追記**: [D-045](../decision_log.md#d-045-f-83-freeze機能を一時休止しbl-062をdetector限定で先に解消する)によりFreezeは一時休止（User AIのtoolsリストから`FREEZE_AGREEMENT_TOOL`を除去。本体・ガード・表示ロジックは温存）。BL-062（Detectorの誤判定がApprovedを覆せず永続化する矛盾）の解消を優先した判断のため。
4. **GoalShiftEvent**: `init_db`に`goal_shift_events`テーブルを新規追加（v2設計書§4.1のDDLに`run_id`列を追加、他テーブルとの一貫性のため）。`call_resource_arbiter`のプロンプト・JSON出力スキーマに`requires_goal_constraint_change`を追加。新規`detect_goal_shift()`関数（v2設計書§4.2の擬似コード通り）と`db_append_goal_shift_event()`ヘルパーを追加し、`arbiter_node`が`call_resource_arbiter`呼び出し直後に配線。

**今回のスコープ外（Plan mode相談で確定）:**

- decision_extractorの役割転換（BL-050完了条件3）は含めない。
- Detectorが既存Agreementを構造的に上書き・無効化できない問題は、BL-062として別途起票するに留めた（write_agreementの権限モデル全体の再設計が必要な、より根深い課題のため）。
- F-5.5（思考内エージェント化ループ）は設計検証のみでR5では未実装（v2設計書の既定方針通り）。

**完了条件:**

- `python -m py_compile cela_main.py`合格。
- 新規`tests/test_r5_thought_log_freeze_goalshift.py`（14件）を含め、オフラインスモークテスト計96件Pass。
- `python scripts/check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（Detectorの思考プロセス監査の実際の発火、Freeze機能の実運用、GoalShiftEventの実発火）は次回待ち。

---

### BL-064: 合意・決定メタデータ（3軸区分／turn／evidence／reason_missing／risk_flag）が書き込まれるのみで、監査ロジック・表示のどこからも消費されていない

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [BL-063](issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)、[BL-069](issue_backlog.md#bl-069-expertが決定前にフェーズタスク表全体を見渡して他フェーズとの資源競合に気づけるよう軽量な指示を追加する) |

**内容:**

ユーザーが`cela_main.py`の`Agreement`TypedDict（`abstraction_level`/`scope`/`time_axis`の3軸区分）を選択し「この情報が活用された形跡はあるか」と質問したことをきっかけに調査した結果、以下5点が判明した。

1. **`agreements.abstraction_level`/`scope`/`time_axis`**: 当初「`_build_agreements_context`が参照せず、対応する`Phase.allowed_abstraction_levels`等も消費ロジックが無い」と報告したが、ユーザーの指摘で追加調査した結果、**Phase側の`allowed_abstraction_levels`/`focus_scope`/`expected_time_axis`は`phases_json`として`call_expert`（`cela_main.py:2686-2691`）・`generate_user_utterance`（`cela_main.py:3771`）に毎ターン丸ごと埋め込まれており、実際には消費されていた**（前回報告の誤り、訂正済み）。一方、Agreement側（1件ごとの`abstraction_level`/`scope`/`time_axis`）はより深刻で、実際にAIが呼ぶ`write_agreement`ツール（`WRITE_AGREEMENT_TOOL`）のパラメータ定義にはこの3軸が**そもそも存在せず**、主経路の書き込み処理`_commit_agreement_from_tool`は`"design", "local", "current"`という固定文字列を常にINSERTしていた（R3b以降、decision_extractor経由でない直接書き込みが主流になったため、本来LLMに分類させる設計だったものが形骸化していた）。ユーザーと相談の結果、この per-Agreement 3軸は「視座のガードレール」という本来の意図（Phase単位で持たせるべきもの）とは粒度が異なる重複実装であり、Phase側で目的を果たせているため**完全削除**を決定。なお「木を見て森を見ず」への対策としてのより具体的な提案（ズームアウト思考）はBL-069として別途起票した。
2. **`agreements.turn`**: 保存されるがどこからも`.get("turn")`で読まれない。`timestamp`で順序は取れるため**削除**を決定。
3. **`agreements.evidence`**: `_build_agreements_context`に`reason_why`と同様の形式で**表示に配線**することを決定。
4. **`decisions.reason_missing`**: `_build_hydrate_context`に理由欠落フラグとして**表示に配線**することを決定。
5. **`state["risk_flag"]`**: `detector_node`が`result["risk"]`をコピーして保存するが、halt/drift判定自体は`result["risk"]`というローカル変数を直接参照しており、他のどのノードも`state["risk_flag"]`を一度も読まない完全な重複。**削除**を決定。

**完了条件:**

- `Agreement`TypedDict・DBスキーマ・`WRITE_AGREEMENT_TOOL`プロンプト記述・`_commit_agreement_from_tool`・decision_extractorの分類ロジック・print文から`abstraction_level`/`scope`/`time_axis`（Agreement側）を削除。
- `agreements.turn`をTypedDict・DBスキーマ・INSERT文・Agreement構築箇所から削除。
- `agreements.evidence`を`_build_agreements_context`に表示するよう配線。
- `decisions.reason_missing`を`_build_hydrate_context`に表示するよう配線。
- `state["risk_flag"]`を`LineageState`・`detector_node`・初期state辞書から削除。
- オフラインスモークテストで非退行確認、`python -m py_compile`合格。

---

### BL-065: R5で新設したDB永続化情報（internal_thought_process／goal_shift_events）の消費・表示経路が未設計

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 依存 | [BL-063](issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)（本BLが指摘する両フィールドはBL-063で新設） |
| 関連 | `docs/refs/lineage-human-intent-spec.md` §9.2、`docs/refs/hydrate-refresh-5-section-template.md` |

**内容:**

BL-064と同じ調査の流れで、R5（BL-063）実装そのものにも同型の「書くが読み返さない」ギャップが2件見つかった。

1. **`decisions`/`agreements.internal_thought_process`（F-3.7）**: Detectorの`major`判定時・Reflectionの`stagnant`判定時・agreementsの`status='Rejected'`書き込み時のみ限定的にDB保存する設計（`cela_r5_design_v2.md`§2、トークンコスト抑制のため）自体は意図通り実装されているが、これを後から読み返して何らかのプロンプト・表示に反映する消費経路が存在しない。F-2.1の思考監査プロンプト（`call_detector`内、`cela_main.py:2855-2858`）が実際に使っているのは同一ターン限りの`state["expert_last_reasoning"]`/`state["user_last_reasoning"]`であり、DBに永続化された`internal_thought_process`とは別物である。永続化した意味（後から振り返れる監査trail）が現状活きていない。
2. **`goal_shift_events`テーブル**: `detect_goal_shift`/`db_append_goal_shift_event`によるINSERTのみが実装され、対応するSELECT関数（`get_goal_shift_events_from_db`相当）がコード中に一件も存在しない。`docs/refs/lineage-human-intent-spec.md`§9.2や`docs/refs/hydrate-refresh-5-section-template.md`が想定していた「HydrateのWhatセクション末尾にGoal evolutionを表示する」という消費側の設計は、`cela_r5_design_v2.md`にも移植されないまま、今回のR5実装では書き込み側のみが着手された。

**完了条件（着手時、未着手）:**

- `internal_thought_process`をいつ・どのノード・どんな形で読み返すべきかを設計する（例: Detectorが次に同種の判定をする際、過去の類似判定理由を参照材料にする／人間向けの監査ログ表示に留める、等の方針決定が必要）。
- `goal_shift_events`の読み出し関数を実装し、少なくとも1つの消費先（例: Hydrateコンテキストへの直近1〜3件の表示）を実装する。

---

### BL-066: whiteboard_draftsの編集履歴（author_role/edit_summary）がバージョン管理はされるが、差分・執筆者情報として一切表示されない

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |
| 依存 | [BL-050](issue_backlog.md#bl-050-decision_extractorの役割転換抽出役理由監査役決定事項の変遷履歴の可視化)（agreements側に同種の差分表示を先行実装済み） |

**内容:**

`apply_whiteboard_patch`は`author_role`/`edit_summary`を含めてINSERTするが（`cela_main.py:1902-1913`）、`get_latest_whiteboard`は`version`/`content`のみをSELECTする（`cela_main.py:1892-1899`）。誰が・どんな要約でこのバージョンを編集したかはDBに保存されているのに一切読み出されない。BL-050がagreements側に実装した「直前Superseded版との差分＋reason_why表示」と同種の仕組みが、whiteboard_draftsには存在しない。

**完了条件（着手時、未着手）:**

- `get_latest_whiteboard`、または新規のwhiteboard履歴表示関数に、直前バージョンとの`author_role`/`edit_summary`を含めた差分表示を追加する。

---

### BL-067: 未使用のSQLテーブル（chat_history／current_goal）の整理

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P3 |

**内容:**

`init_db`でスキーマ定義されている`chat_history`テーブルと`current_goal`テーブルは、コード全体を検索しても`INSERT INTO`/`SELECT ... FROM`が一件も存在しない。実際の会話履歴・ゴールは`state["chat_history"]`/`state["goal"]`（インメモリ）とLangGraphのcheckpointerで完結しており、これら2テーブルは完全に死んだスキーマである。

**完了条件（着手時、未着手）:**

- 両テーブルを削除するか、将来的な用途（例: プロセス再起動をまたいだ会話ログの独立永続化）が本当にあるならその用途を明記した上で実装するかを判断する。

---

### BL-068: Hydrateスタイルのコンテキスト階層化（直近Nターン生ログ＋それ以降の定期要約）が設計のみで未実装のまま放置されている

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 関連 | `docs/refs/hydrate-index-expand-spec.md`（Zone A/B/C 3段グラデーション設計） |

**内容:**

`state["current_task_summary"]`（`cela_main.py:4109`で書き込み、BL-064で「どこからも読まれない」と判明済み）について、ユーザーから「これはHydrateの思想（`docs/refs/hydrate-index-expand-spec.md`のZone A/B/C 3段グラデーション）から来ており、AIのコンテキストに載せる直近Nターンは生ログ、それ以降は5ターン分の会話要約を積んでいく予定だったが、その部分が実装されずに放置されている」との説明があった。

実際、`call_expert`のシステムプロンプトには現在も「5ターン毎に議論のサマリーを出力せよ。数値などは消さず明示的に示すこと」という指示（`cela_main.py:2620`）が残っている。しかしこの指示に対応するExpertの出力を捕捉・蓄積し、Zone B相当の「古いターンの圧縮コンテキスト」として使う実装が一切ない。`state["current_task_summary"]`はExpertの生出力を200文字に切り詰めて保存するだけの別物で、しかもどこからも読まれない。現状の`chat_history_window`（既定4）による文脈構築は、直近N件を生ログのまま渡す固定窓のみであり、それ以前のターンは要約されず単純に切り捨てられている。

**完了条件（着手時、未着手）:**

- 5ターンごとのExpert要約出力を実際に捕捉し、`chat_history_window`の外側にあるターンをこの要約で置き換える階層化ロジックを設計・実装する。
- または、この機能自体を今回のCELAのスコープでは実装しないと明示的に決定し、`current_task_summary`と該当プロンプト指示（`cela_main.py:2620`）を削除する。

---

### BL-069: Expertが決定前にフェーズ・タスク表全体を見渡して他フェーズとの資源競合に気づけるよう、軽量な指示を追加する

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 関連 | [BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（同一の「木を見て森を見ず」現象を先に診断済み。facilitator再設計等の大きな解決策とは別に、より軽量なプロンプト改善のみを提案）、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（現在のスコープ制限指示との緊張関係） |

**内容:**

BL-064（Agreementの3軸区分）の議論の中で、ユーザーが直近で「AIが同じ検証を何度も繰り返す」「木を見て森を見ず」的な挙動を見かけたと述べ、対策として「L1（タスク内トピック）→L2（タスク内の影響）→L3（同フェーズのタスク間）→L4（フェーズ超え）」というズームアウト思考フレームワークを提案した。

調査の結果、以下が判明した。

1. `call_expert`は既に全フェーズ・全タスクを含む`phases_json`を毎ターンシステムプロンプトに埋め込んでいる（`cela_main.py:2686-2691`、「指示があったフェーズ、タスクに関しては、必ずこの計画を参照し、逸脱や矛盾がないよう思考してください」という指示付き）。ユーザーは「現在は集中すべき現在のタスクのみが見せられている」と認識していたが、実際には全体表は既に毎ターン渡っている。
2. しかし直後（`cela_main.py:2700-2714`）に、BL-025のスコープガードレールが「あなたの回答で扱ってよい内容は、以下の『現在のタスク』のacceptance_criteriaの範囲に厳密に限定してください」「他タスクがowns_variablesとして所有する値は、たとえ関連性が高く見えても新たに算出・提案しないでください」と明記しており、Expertは全体表を見えていながら、それに基づいて能動的に行動することを事実上禁止されている。
3. この緊張関係はBL-041自身のコードコメント（`cela_main.py:2718-2723`、「[BL-041] 『木を見て森を見ず』対策」）が既に名指しで言及済みであり、現状の緩和策は「他タスクの制約とまだ突き合わせていない数値はconfidence='provisional'にする」というタグ付けのみで、実際に他フェーズ・他タスクの内容を能動的に見渡させる指示にはなっていない（BL-041の完了条件にも「write_agreementのSUPERSEDEも自発的には使われない」と明記済み）。

ユーザーは後日、正式なL1〜L4の段階分けラベルまでは不要で、「次のフェーズに自動運転監視システムの設計というタスクがある→これは初期費用に含まれる可能性がある→バスの台数決定に影響するかも」程度の気づきを促す軽量な指示があれば十分だと補足した。また、フェーズ・タスク表をDBから呼び出す専用の手段（ツール）を求めていたが、実際には`phases_json`として既に毎ターン渡っていることが今回の調査で判明したため、新規ツールの追加は不要と考えられる。

**完了条件（着手時、未着手）:**

- 新規のDBフィールド・ツールは追加せず、既存の`phases_json`埋め込み（`cela_main.py:2686-2691`）またはresource_claims関連の指示（`cela_main.py:2724-2735`）の近くに、「resource_claimsを伴う決定を確定させる前に、上記フェーズ・タスク表を見渡し、同じ制約名（total_cap）を主張しうる他のフェーズ・タスクがないか一度確認せよ」という軽量な指示文を追加する。
- BL-025のスコープガードレール文言（他タスクの値を算出・提案しない）と矛盾しないよう、「提案・算出はしないが、気づきをreason_why/evidenceに書き添える、またはconfidence='provisional'に倒す」という着地点にする。
- 実LLM再ドライランで、実際にこの気づきが発生するかを確認する（BL-041の完了条件と同様、次回ドライラン待ち）。

---

### BL-070: SUPERSEDE運用指示をReviewer/Arbiter/Integratorにも拡張するかの検討

| 項目 | 内容 |
|------|------|
| 状態 | `open` |
| 優先度 | P2 |
| 依存 | [BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（Detector限定で先行実装済み）、[decision_log.md D-045](../decision_log.md#d-045-f-83-freeze機能を一時休止しbl-062をdetector限定で先に解消する) |

**内容:**

BL-062の対応方針をユーザーと相談する中で、Detector/Reviewer/Arbiter/Integratorは全員技術的には既に`WRITE_AGREEMENT_TOOL`を保有し、`status='Rejected'`かつ`action_type='SUPERSEDE'`を呼べる権限を最初から持っていることが判明した。しかし、以下の理由からReviewer/Arbiter/Integratorへの拡張は今回のBL-062実装（D-045）のスコープから分離した。

1. Reviewer/Arbiter/Integratorの3ロールとも、現状agreements DBのtopic一覧（`_build_agreements_context`相当）をプロンプト上受け取っておらず、`target_topic`を指定する材料がない（Detectorも同じ状態だったが、今回Detector限定でこれを解消した）。
2. Reviewer（成果物全体のpassed/failed判定）・Arbiter（リソース配分の再調停）・Integrator（フェーズ横断の矛盾検知）は、Detectorのような「個別の会話ターンを1件ずつ監査する」役割とは異なり、topic単位のSUPERSEDEが同じ意味を持つかが自明ではない。例えばIntegratorが検知する「矛盾」は`affected_phases`（フェーズ単位）でありtopic単位ではないため、そのままSUPERSEDE指示を移植できるとは限らない。

**完了条件（着手時、未着手）:**

- Detectorでの実運用（実LLM再ドライラン）を経て、SUPERSEDE運用が実際に有効に機能するかを確認する。
- Reviewer/Arbiter/Integratorそれぞれについて、「topic単位のSUPERSEDEが役割上意味を持つか」を個別に設計検討したうえで、必要と判断したロールにのみagreements DBビューの注入とSUPERSEDE運用指示を追加する。

---

### BL-071: `timestamp`キーを持たないAgreement辞書が`_build_agreements_context`のソートでプロセスクラッシュを引き起こす

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-063](issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)（クラッシュの原因となったis_frozeソートの追加元） |

**内容:**

ユーザーが今回の一連の修正（BL-062/064〜070、D-045）を反映した状態で実ドライランを行ったところ、1ターン目の`orchestrator_node`実行中に以下でプロセス全体がクラッシュした。

```
TypeError: '<' not supported between instances of 'NoneType' and 'float'
  at _build_agreements_context: decisions_and_deliverables.sort(key=lambda a: (not a.get("is_frozen"), a.get("timestamp", 0)))
```

調査の結果、`decision_extractor_node`のAgreement辞書リテラル2箇所（UPDATE分岐・新規分岐）と、`integrator_node`の最終統合ドキュメント登録箇所が、いずれも元々`timestamp`キーを持っていなかったことが判明した。`db_append_agreement`のINSERTは`a.get("timestamp")`（デフォルト無し）を使うため、これらの経路で書き込まれるagreementsは常にDB上`timestamp`列がNULLになっていた。この問題自体はR1以来存在していたが、R5（BL-063）で`_build_agreements_context`にis_frozen優先のソートキー`a.get("timestamp", 0)`を追加したことで、初めて実際に比較（`sort`）に使われるようになり顕在化した。`a.get("timestamp", 0)`はキー自体が存在する（値がNoneなだけ）場合はdefault値0が使われないため、None同士・Noneとfloatの比較で`TypeError`となった。なお`_find_prior_superseded`（BL-050）は同種の状況を`a.get("timestamp") or 0`という安全なパターンで既に回避しており、今回のソートだけがこのパターンに従っていなかった。

**対応:**

1. `_build_agreements_context`のソートキーを`a.get("timestamp", 0)`から`a.get("timestamp") or 0`（`_find_prior_superseded`と同じ安全なパターン）に修正。
2. `decision_extractor_node`のAgreement辞書リテラル2箇所、`integrator_node`の最終統合ドキュメント登録箇所の計3箇所に`"timestamp": time.time()`を追加し、今後この経路で書き込まれるagreementsのタイムスタンプがNULLにならないようにした。

**完了条件:**

- 新規`tests/test_bl071_agreement_timestamp_crash.py`（2件）: `timestamp`キーなしのagreementが混在していても`_build_agreements_context_from_db`がクラッシュしないこと、`decision_extractor_node`のソースが`"timestamp": time.time()`を2箇所以上含むことを確認。
- オフラインスモークテスト計102件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの再発なし確認は次回待ち（ユーザーが同一ドライランを再実行する予定）。

---

### BL-072: `httpx.ReadTimeout`が絞り込んだ例外タプルから漏れ、streaming受信中にプロセスクラッシュを引き起こす

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-059](issue_backlog.md#bl-059-streaming受信中のhttpxremoteprotocolerrorが未捕捉でプロセスクラッシュする)（同型の問題、`httpx.RemoteProtocolError`が漏れていた事例）、[BL-083](issue_backlog.md#bl-083-streaming受信中のhttpxreaderror接続の強制切断が絞り込んだ例外タプルから漏れプロセスクラッシュを引き起こす)（同型の再発、`httpx.ReadError`が漏れていた事例） |

**内容:**

BL-071修正後、ユーザーが同一ドライランを再実行したところ、`expert_node`（`call_expert`のstreaming受信中）で以下によりプロセス全体がクラッシュした。

```
httpx.ReadTimeout: The read operation timed out
  at _query_AI_live: for chunk in stream:
```

BL-059と同型の問題である。`_query_AI_live`の単一の`try`ブロック（tools有無どちらの分岐も内包、`for attempt in range(len(delays) + 1):`直下）を包む`except`タプルは`(APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError, httpx.RemoteProtocolError)`に限定されていたが、プロバイダ側のタイムアウトに由来する生の`httpx.ReadTimeout`はopenai SDKの`APITimeoutError`へラップされず、この例外タプルに含まれないまま素通りしていた。

**対応:** BL-059のように個別の派生例外（`httpx.ReadTimeout`）だけを都度追加するのではなく、`httpx.ReadTimeout`/`ConnectTimeout`/`WriteTimeout`/`PoolTimeout`をすべて包含する親クラス`httpx.TimeoutException`を例外タプルに追加した。これにより、今回未発生の他のタイムアウト種別（接続確立時のタイムアウト等）についても同種の未捕捉クラッシュが予防される。

**完了条件:**

- 新規`tests/test_bl072_httpx_timeout_retry.py`（1件）: `_query_AI_live`のソースが`httpx.TimeoutException`を例外タプルに含むことを確認。
- オフラインスモークテスト計103件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの再発なし確認は次回待ち。

---

### BL-073: `entry_type="Directive"`のagreementが対応タスク完了後もstatus="Proposed"のまま永久残留する

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | `reflection_node`の未解決抽出（`agreements.status=="Proposed"`の全件、`cela_main.py:3444`） |

**内容:**

ユーザーとログ（`log/2026-07-24/0647`）をレビューする中で発見。`reflection_node`の内省監査プロンプトは「未解決のまま残っている検討中の項目」として`agreements`のうち`status=="Proposed"`の全件（`entry_type`不問）を提示する。ところが`entry_type="Directive"`（Userのタスク指示）は、`decision_extractor_node`のプロンプト仕様上CREATE時に`status="Proposed"`で書き込まれた後、これを`Approved`等へ遷移させる経路が一切存在しなかった。ステータスが更新されるのは同じtask_idの`entry_type="Deliverable"`側のみで、指示そのものはDB上いつまでも`Proposed`のまま残り続ける。

実ドライランでは、既に完了・承認済みのtask_1_1/task_1_3の指示がReflectionの「未解決」リストに出続け、Reflection自身が「もう終わっているのになぜProposedのままか」と長々自問自答した末に「実際の完了証拠を優先すべき」と毎回自己修正していた（致命的ではないが、監査のたびに無駄な思考トークンを消費し、将来的に判断を誤らせるリスクがある構造的ノイズ）。

**対応:** 対症療法（Directiveを未解決抽出から除外する）ではなく根本解決を採用。新規`_resolve_directive_for_task(conn, run_id, task_id, phase_id, resolved_by)`関数を追加し、対応するtask_idの`entry_type="Directive"`かつ`status="Proposed"`の最新agreementを`Superseded`化した上で`status="Approved"`の新レコードとして追記する。この関数を、Deliverableの状態遷移が起こる2つの経路の両方から呼び出す：

1. `decision_extractor_node`のUPDATE分岐（Userの自然言語承認をdecision_extractorが抽出する経路）。
2. `_commit_agreement_from_tool`（Expert/Userが`write_agreement`ツールを直接呼ぶ経路）。

いずれも新設した`RESOLVING_DELIVERABLE_STATUSES = {"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}`に該当する場合にのみ発火する（`Rejected`/`Proposed`では指示は未解決のままとする）。

**完了条件:**

- 新規`tests/test_bl073_directive_auto_resolve.py`（4件）: `_resolve_directive_for_task`の遷移・no-op動作、`_commit_agreement_from_tool`経由でのDeliverable承認に伴うDirective自動解決、両経路のソースへの配線確認。
- オフラインスモークテスト計107件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（Reflectionの未解決リストからApproved済みDirectiveが消えること）は次回待ち。

---

### BL-074: Deliverableのtopic文字列に連続性が保証されず、Supersede漏れの亡霊`Proposed`行がDBに複数残存する（＋BL-076のtarget_excerpt完全一致の脆さを統合）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（target_excerpt側の正規化フォールバック＋失敗理由ログは`done`。Deliverable本体のtask_id識別への切替は次回） |
| 優先度 | P2 |
| 関連 | [BL-073](issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する)（同根の問題、Directive側の解決）、[BL-076](issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)（統合元）、[BL-079](issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる) |

**内容:**

ユーザーとtask_2_2（初期導入費用内訳策定）の議論の変遷をログ（`log/2026-07-24/0647`）で追跡する中で発見。`_commit_agreement_from_tool`・`decision_extractor_node`はいずれも、`entry_type="Deliverable"`のUPDATE/SUPERSEDE対象を`target_topic`（省略時は`topic`自身）の文字列完全一致でのみ特定する。しかしExpert/decision_extractorは同一タスクの成果物を改訂するたびに新しいtopic文字列を自由に発明しており（実測: 「task_2_2_初期導入費用内訳策定」→「task_2_2 初期導入費用の内訳策定」→「水ノ守町 自動運転バス導入 初期導入費用内訳（ver.2修正版）」→「...（ver.3：AVキット・認証コスト初期計上版）」→「初期導入費用の内訳策定（ver.3）承認」）、連続性が保証されない。

実ドライランでは、task_2_2という単一のDeliverableに対し、最終承認後もagreements DBに**4行**（うち2行が`Proposed`のまま、1行が`Approved_with_Conditions`）が非Superseded状態で残存し、`_build_agreements_context`経由でLLM向けコンテキストに出続けていることを確認した。whiteboard_drafts側（`phase_id`+`task_id`固定キー）のコンテンツ版管理自体は正しく連続しているため、実害はコンテキストの汚染・混乱に留まるが、BL-073と同根の構造的欠陥である。

**設計方針（決定済み、実装は次回）:**

`topic`はentry_type="Decision"（1タスク内に複数の論点がありうる）には妥当な識別キーだが、entry_type="Deliverable"は本アーキテクチャ上1タスクにつき1つ（whiteboard_draftsが`task_id`単位でバージョン管理している設計と整合）であり、`topic`ではなく`task_id`を識別キーとすべきと判断した。具体的には、`entry_type=="Deliverable"`のCREATE/UPDATE/SUPERSEDEいずれの場合も、`target_topic`の文字列一致に加えて（あるいは代えて）同一`task_id`かつ`entry_type=="Deliverable"`かつ非Supersededの既存行を検索・Supersede化してから新行を追記する。CREATE時（現状は無条件追記のみで既存行の検索を一切行わない）にもこの検索・Supersede化を追加することで、ver.1→ver.2のような「新しいCREATEのつもりで実質的に前バージョンを置き換える」ケースも自動的に解決される。BL-073の`_resolve_directive_for_task`と対になる`_resolve_prior_deliverable_for_task`のような関数を新設し、`_commit_agreement_from_tool`・`decision_extractor_node`の両経路（Deliverableの書き込みが起こりうる箇所）から呼び出す方針。

**完了条件（Deliverable本体・task_id識別、未実装）:**

- `_commit_agreement_from_tool`・`decision_extractor_node`の両経路で、`entry_type=="Deliverable"`のCREATE/UPDATE/SUPERSEDEいずれについても、同一`task_id`の既存非Superseded Deliverable行が自動的にSupersede化されること。
- 回帰テスト: task_2_2型のシナリオ（同一task_idに対し複数回のCREATE/UPDATE/SUPERSEDEが異なるtopic文字列で発生）で、最終的に非Superseded Deliverable行が1件のみになること。
- オフラインスモークテスト・`py_compile`・`check_docs_consistency.py`の非退行確認。
- 実装は次回セッションで着手（本ターンは発見・BL起票・設計方針決定のみ）。

---

**2026-07-24追記: BL-076のtarget_excerpt完全一致の脆さを統合（実装済み・`done`）**

1216ドライラン（`log/2026-07-24/1216/log_no_prompt.md`）のフォレンジック調査で、`constraint_issue=major`かつ`target_role=assistant`の判定が複数回発生し`target_excerpt`も正しく出力されていたにもかかわらず、成功時に出るはずの`🔴 [Whiteboard Annotated]`ログが一度も出力されていないことが判明した。原因は`_annotate_whiteboard_with_detector_comment`の完全一致依存（topic文字列ドリフトと同根の脆さ）に加え、失敗時は`return False`のみでログが一切出ないサイレント失敗だったこと。実際のケースでは、Detector自身が「AIの発言と実際のホワイトボードの内容が一致していない」という乖離を独立に発見しており（BL-062のSUPERSEDE運用に繋がった一件）、これがtarget_excerptの一致失敗の典型例だったと考えられる。

**対応（実装済み）:**

1. `_annotate_whiteboard_with_detector_comment`の戻り値を`bool`から`tuple[bool, str]`（成功可否, 理由）へ変更し、`detector_node`側で失敗時にも`⚠️ [Whiteboard Annotate Failed]`として理由（0件一致/複数件一致等）付きでログ出力するよう変更。
2. 完全一致（`content.count(target_excerpt) == 1`）に失敗した場合、新設`_normalize_for_loose_match`で改行・空白・Markdown太字記法（`**`）・全角半角の差異を吸収した正規化文字列を作り（元の文字列位置へのindex_map付き）、正規化後に一意一致する場合はそちらを採用してオリジナル文字列上の正しい位置へ注釈を挿入するフォールバックを追加。
3. リトライ（一致失敗をDetector自身のツール呼び出し結果として返し、同一ツールループ内で再試行させる構造）はスコープが大きいため、BL-079として別途起票。

**完了条件（target_excerpt側・完了）:**

- 新規`tests/test_bl074_annotation_loose_match_fallback.py`（5件）: 太字記法差異・改行空白差異・全角半角差異それぞれでの緩い一致成功、正規化後も曖昧な場合の失敗維持、`detector_node`の失敗理由ログ配線確認。
- 既存`tests/test_bl076_whiteboard_detector_annotation.py`をタプル戻り値に合わせて更新。
- オフラインスモークテスト計122件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの効果確認（1216ドライランと同様のケースで実際に注釈が挿入される、または少なくとも失敗理由がログに残ること）は次回待ち。

---

**2026-07-25追記: `1913`ドライランで正規化フォールバックも救えない0/0一致失敗を再確認**

BL-089レビュー中にユーザーが`log/2026-07-25/1913/log_no_prompt.md` L16700で`⚠️ [Whiteboard Annotate Failed] 注釈の埋め込みに失敗しました（完全一致0件・正規化後緩い一致も0件でした）`を発見。Detector自身は数値すり替え（BL-062、高齢者/非高齢者ラベルの入れ替え等）を3回多数決で正しくmajor判定・Rejected化できていたが、その判定内容をホワイトボード本文へ注釈として書き戻す段では、完全一致・正規化後緩い一致のいずれも失敗した。上記「次回待ち」としていた実LLM再ドライランでの効果確認が、まさにフォールバックでも救えない実例として再現したことになる。監査ロジック自体（BL-062運用）は健全に機能しているため実害は限定的（判定結果自体はログ・DBのAgreement側には正しく記録される）だが、ホワイトボード本文側への注釈という補助的な可視化がサイレントに欠落し続けている状態であり、根本解決にはBL-079（Detector自身へのフィードバック＋同一ツールループ内リトライ）が必要という判断材料になったため、BL-079の優先度をP3→P2へ引き上げる。

---

### BL-075: F-7.3ホワイトボードロールバックが「1つ前は健全」という前提に反し、修正済み問題を無警告で再導入する

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [D-047](../decision_log.md#d-047-f-73ホワイトボードロールバックを撤廃し部分修正誘導プロンプトへ置き換える) |

**内容:**

実ドライラン（`log/2026-07-24/0647`）継続中、task_2_3（年間ランニングコストの内訳策定）でDetector自身が以下のバージョン退行を発見した。

1. Ver.1（CREATE）：オペレーター年間有給休暇5日・年間稼働240日 → Detector: `major`（労働基準法第39条違反、法定最低10日）
2. Ver.2（CREATE）：Expertが有給10日・251日に修正 → Detector: `minor`（**別件**：法定祝日が未考慮という新しい懸念。この時点でDetector自身が「有給5日→10日はVer.2で修正済み」と明記）
3. 差し戻し発生（祝日懸念でmajor）→ `rollback_whiteboard`が発火。この時点でwhiteboard_draftsに2版（Ver.1, Ver.2）が存在するため、`rows[1]`＝Ver.1（有給5日）の内容がVer.3として復元される
4. Ver.4（CREATE）：Expertは祝日懸念のみに対応し、現在のホワイトボード（実質Ver.1の内容）を土台に作業したため、**有給10日の修正が消えて有給5日に逆戻り**

原因は`rollback_whiteboard`（F-7.3、要件定義書_v35.md該当箇所「前バージョン（Ver.3の正常な状態）へロールバックする」）が、常に「1つ前のバージョンは健全」という前提でrows[1]（2版前）を機械的に復元する設計だったこと。major判定のたびに指摘内容が変わる実運用下では、1つ前のバージョン自体が過去に別件でmajor判定された版であることがあり、この前提は成立しない。ユーザーから、F-7.3導入時の背景（差し戻し時に前のNG発言を消すのは、次のAIがそれに引っ張られて同じ誤りを繰り返すのを防ぐためだったが、F-2.6検算ゲート・BL-033監査記録・agreements DBコンテキスト注入等でシステムが大幅に強化された現在は、この設計がむしろ矛盾を生んでいる）の説明があった。

**対応:** ユーザー提案（Word/PDFのコメント機能のように、Detectorの指摘箇所を示した上で差し戻し、差し戻されたAIは指摘を読みホワイトボードを確認して部分修正、影響範囲が大きければ周辺も再考する、というワークフロー）を採用。

1. `rollback_whiteboard`関数を削除（`expert_node`からの呼び出しも削除）。ホワイトボードの最新内容は保持されたまま次のExpertターンに引き継がれる。
2. `call_expert`のmajor差し戻しプロンプトを、「完全に修正した新しい提案を作成してください」（全文書き直し誘導）から、「現在のホワイトボードはロールバックされていない。Detectorの指摘箇所を特定し、`edits`（old_text/new_text）で部分修正せよ。影響が他箇所に及ぶ場合はその範囲も見直し、必要なら`decision_what`による全文更新（SUPERSEDE）を使え。既に修正済みだった箇所を無関係な理由で元に戻さないよう注意せよ」という部分修正優先の指示に置き換えた。
3. 副次的発見: 同関数内に、`system_prompt`へ`+=`した後に一度も`messages`へ反映されない完全な**死んだコード重複ブロック**（同一の差し戻し警告メッセージが2箇所に存在し、後者は文字列変数を更新するのみでAPI呼び出しに一切影響しない）を発見し削除した。

**完了条件:**

- `rollback_whiteboard`関数が完全に削除され、`expert_node`から呼び出されないこと。
- `call_expert`のプロンプトが部分修正・影響範囲確認を指示する文言に置き換わっていること。
- 新規`tests/test_bl075_no_whiteboard_rollback.py`（4件）: 関数削除確認、`expert_node`ソースからの呼び出し削除確認、`call_expert`の新文言確認、実際にmajor判定を受けてもwhiteboard_draftsの最新内容が巻き戻らないことの機能テスト。
- 既存`tests/test_r4_smoke.py`のF-7.3ロールバック専用テスト2件を削除（機能自体の廃止のため）。
- オフラインスモークテスト計109件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（同種のバージョン退行が再発しないこと）は次回待ち。

---

### BL-076: Detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込む（Word/PDFコメント方式）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [BL-075](issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する)、[D-048](../decision_log.md#d-048-detectorのmajor指摘をホワイトボード本文にも永続的な注釈として埋め込む) |

**内容:**

BL-075でロールバックを撤廃し、`call_expert`のプロンプトに部分修正誘導文を追加したが、ユーザーから「それだけでは毎ターン再構成されて消えるプロンプト注入に留まり、AIが見落とす可能性がある。ホワイトボードに直接Detectorの指摘と理由を載せれば永続化されて気づく可能性が高いし、指摘箇所が明白になる」との指摘があった。Word/PDFのコメント機能のように、指摘対象の箇所に直接コメントを書き込み、差し戻す設計が理想として提示された。

**対応:**

1. `call_detector`の両パス（ドメイン妥当性レビュー・数値監査）のJSON出力スキーマに`target_excerpt`（ホワイトボード本文から指摘対象を一字一句そのまま引用したもの）を追加。両パスの結果は、実際に採用されたconstraint_issueの重篤度を出した側の`target_excerpt`を優先して統合する。
2. 新設`_annotate_whiteboard_with_detector_comment(conn, run_id, phase_id, task_id, target_excerpt, comment, decision_id)`が、`target_excerpt`がホワイトボード内で一意一致する場合のみ、その直後に注釈を挿入した新バージョンを`apply_whiteboard_patch`で保存する。一致しない・複数一致する・空文字の場合は挿入しない（誤った位置への注釈でExpertを混乱させないため）。
3. 注釈フォーマットは、案A（grep容易なタグ・ID付き）と案B（視認性の高いMarkdown引用）のハイブリッド（ユーザー承認、D-048）:
   ```
   > 🔴 **[Detector指摘 #D-xxx]**: <指摘内容>
   > （この注釈は指摘箇所を修正すると同時に削除してください）
   ```
4. `detector_node`から、`constraint_issue=="major"`かつExpertの成果物を評価するターン（`target_role=="assistant"`）の場合のみ呼び出す。
5. `call_expert`のBL-075差し戻しプロンプトに、注釈行を探して`old_text`に含めることで修正と同時に注釈も消えるという運用方法を明記。

**完了条件:**

- 新規`tests/test_bl076_whiteboard_detector_annotation.py`（4件）: ハイブリッド注釈の挿入確認、非一意/不一致時のno-op確認、`call_detector`両パスの`target_excerpt`要求確認、`detector_node`の配線確認。
- オフラインスモークテスト計113件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（注釈が実際にホワイトボードへ挿入され、Expertが部分修正時に注釈ごと解消すること）は次回待ち。

**2026-07-24追記:** 1216ドライランで実際に検証したところ、major/assistant判定が複数回発生したにもかかわらず注釈挿入が0回しか発火せず、しかもサイレントに失敗していたことが判明。完全一致依存の脆さという根本原因はBL-074（topic文字列ドリフト）と同根と判断し、対策（失敗理由ログ＋正規化フォールバック）はBL-074側に統合して実装した。詳細は[BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)を参照。

---

### BL-077: AGENTS.mdの「まずMemory/STATUS/backlogを確認してから動く」設計思想をCELA自身のAI群に適用する（設計検討・未着手）

| 項目 | 内容 |
|------|------|
| 状態 | `open`（設計検討のみ、実装未着手） |
| 優先度 | P3 |
| 関連 | [BL-076](issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)、[BL-051](issue_backlog.md#bl-051-detectorの気づきをissue_blリストとして蓄積しフェーズ終了条件とする)（本項目より先に起票済みの、同一構想のDetector限定・具体版。本項目はそれをExpert/User AI全体のワークフローへ一般化したもの） |

**内容:**

BL-076（ホワイトボードへの指摘埋め込み）の議論の延長として、ユーザーが「この本プロジェクト自身のAGENTS.mdのように、AIは必ずまずホワイトボードと（まだ実装されていない）issue_BL相当の仕組みを確認して現状・指摘事項・タスク内の残課題を認識してから、User AIなら指示を出し、Expertはタスクをこなす、という思考ワークフローにできないか」という設計アイデアを提示した。ユーザー自身、これを実現するにはSTATUS.md・traceability.md相当の永続的な進捗管理の仕組みも新たに必要になると認識している。

これはBL-075/BL-076（ホワイトボード本文への注釈埋め込み）よりも一段大きい構想で、CELAが動かすExpert/User AI自身に「作業前に必ず状況確認する」という規律を持たせるための、タスクごとの課題管理・進捗管理レイヤーの新設を意味する。範囲が大きいため、今回はBL化のみ行い、実装は別途設計相談の上で着手する。

**完了条件（未定、設計時に確定）:**

- ホワイトボード・issue_BL相当の仕組みをExpert/User AIの各ターン冒頭でどう確認させるか（プロンプト注入か、専用readツールか）の設計。
- issue_BL相当の永続的な課題管理データモデル（DBスキーマ or ホワイトボードへの統合）の設計。
- STATUS.md/traceability.md相当の進捗管理をCELA自身にどう持たせるかの設計。
- 本項目は次回以降のセッションで別途設計相談から着手する。

---

**2026-07-25追記: `1913`ドライランで、この構想の具体的な設計材料が見つかった（「minorな数値誤りをどう扱うか」問題への回答として。なお本項目より先に、Detector限定の同一構想が[BL-051](issue_backlog.md#bl-051-detectorの気づきをissue_blリストとして蓄積しフェーズ終了条件とする)として既に起票済みであることが判明した。BL-051の暫定つなぎ実装（`observations`欄の蓄積・次ターンのExpert/User AIへの参考提示）が、今回User AIが独立にこの誤りを拾えた一因である可能性が高い）**

BL-089レビューの延長で、ユーザーとtask_2_1（安全基準・運休判断基準策定）の成果物レビューを検討する中で発見。Detectorが実際に単位混同の計算誤り（`0.15×L < 30 → L < 200km`、正しくは`L < 3.33km`という60倍の桁違い）を検算で正しく発見したにもかかわらず、3回多数決で「参考検証セクションの誤りでacceptance_criteriaには影響しない」として`minor`判定に落ち着き、`minor`は`route_after_expert_detector`の差し戻しをトリガーしないため、誤った式・誤った結論がホワイトボードに残ったまま承認扱いになった（結果的には後続のUser AI層が独立に同じ誤りを再発見し「条件付き承認」で修正指示を出したため実害は免れたが、これは偶然の多層監査による救済であり、構造的な保証ではない）。

ユーザーはこれについて「数字が一字一句合致しないと差し戻す」という全数一致の完全性要求は、BL-088/089で見た「差し戻しの嵐」（Reviewerの過剰な精度要求がtask_plannerのハルシネーションを誘発した実例）と同じ副作用を招くため、単純に`minor`も強制差し戻しするようにはできないと整理した。その上で、「見つけた不具合や誤りは全てissue_BL相当のリストに放り込み、そのフェーズは、リスト内の全項目が`closed`にならない限り完了と見なさない」という具体的なゲート機構を、本BL-077（本プロジェクト自身のissue_backlog.md運用をCELA自身のAI群に適用する構想）の設計方針として提示した。これにより、「即時の差し戻し」と「観察のみで放置」の二択ではなく、「今すぐ直さなくてもよいが、フェーズ完了までには必ず解消される」という第三の選択肢が生まれ、`minor`判定のような軽微だが実在する誤りを、差し戻しの嵐を起こさずに確実に収束させられる可能性がある。

**完了条件への追記:**

- 上記の「フェーズ完了ゲート」（issue_BL相当のリストの全項目closeを`phase`完了条件に追加する）を、既存の完了条件（データモデル設計・確認タイミング設計・進捗管理設計）と統合して次回設計相談で具体化する。

---

### BL-078: Orchestratorの専門家選定時の考察を`focus_guidance`としてExpertへ注入する

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [D-049](../decision_log.md#d-049-orchestratorの専門家選定時の考察をfocus_guidanceとしてexpertへ注入する) |

**内容:**

ユーザーが、Detectorのドメイン妥当性レビューが「プロンプトで監査の観点を変えるだけで仕事ぶりがガラッと変わる」ことに着目し、同じ発想をOrchestrator→Expertの選定フローに応用できないか提案した。`call_orchestrator`は専門家の肩書き（役職名）を選ぶ過程で、既にある程度タスクの中身を見渡して考察しているが、その結果は`reason`（選定理由）としてログ・`make_decision`に残るのみで、選ばれたExpert自身の`call_expert`プロンプトには一切渡っていなかった。

**対応:**

1. `call_orchestrator`のプロンプトに、専門家選定の理由（`reason`）とは別に、「このタスクに実際に着手する専門家AIが、具体的にどんな観点で検討すべきか・特に見落としやすい落とし穴は何か」を1〜3点、タスク固有の実行可能な指示として出力させる`focus_guidance`フィールドを追加。JSON出力・フォールバック・戻り値のすべてに配線。
2. `orchestrator_node`が`result.get("focus_guidance", "")`を`state["expert_focus_guidance"]`へ保存（`LineageState`へフィールド追加、BL-038の教訓により必須）。
3. `call_expert`のフル版system_prompt・軽量版light_system_prompt（BL-025②のツールループ自問自答フェーズ用）の両方に、`🎯 【このタスクで特に注意すべき観点（Orchestratorより）】`として注入。

**完了条件:**

- 新規`tests/test_bl078_orchestrator_focus_guidance.py`（4件）: `call_orchestrator`のプロンプト・フォールバック確認、`orchestrator_node`の配線確認、`call_expert`のフル版・軽量版両方への注入確認、`LineageState`へのフィールド宣言確認。
- オフラインスモークテスト計117件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（`focus_guidance`が実際にタスクごとに具体的な内容で出力され、Expertの検討の質に寄与すること）は次回待ち。

---

### BL-079: ホワイトボード注釈の一致失敗をDetector自身にフィードバックし、同一ツールループ内でリトライさせる

| 項目 | 内容 |
|------|------|
| 状態 | `done`（当初構想の縮小版として実装。完全な「注釈挿入自体のツール化」は見送り、下記参照） |
| 優先度 | P2（`2026-07-25`: `1913`ドライランでの再発を受けP3から引き上げ） |
| 関連 | [BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)、[BL-091](issue_backlog.md#bl-091-write_agreementの成否をdetectorへ明示せずモデルの偽ツール呼び出し風テキストを鵜呑みにして誤って承認していた)（同じ`1913`レビューで同時対応） |

**内容:**

BL-074のtarget_excerpt正規化フォールバックを相談する中で、ユーザーから「そもそもClaude Code自身のEdit（old_text/new_text完全一致）方式は、なぜ実運用でハードルが高くならないのか」という質問があった。調査の結果、Claude CodeのEditツールが機能する理由は2点あり、(1) LLMがその場で読んだばかりの内容から引用する、(2) 不一致時にツール結果として即座にエラーが返り、同一ターン内でLLM自身がリトライできる、である。CELAの`_annotate_whiteboard_with_detector_comment`はBL-074の対応後も(2)を欠いており、一致失敗はDetectorのツールループの外側（`detector_node`側の後処理）で静かに起こるため、Detector自身は自分の引用が的を外したことを知る術がない。

ユーザーは、python_replなど他のツールでエラーフィードバックが返ってきた場合、Detectorの思考ログ上で「あの手この手を試して何とかしようとする」試行錯誤が実際に見られることを確認しており、同様の自己修正ループをホワイトボード注釈にも適用できないか提案した。

**設計方針の見直し（当初案 → 実装した縮小版）:**

当初は「注釈挿入自体（`_annotate_whiteboard_with_detector_comment`相当）をDetector自身が呼べる新規ツールにする」構想だったが、実装検討の結果、実際の注釈挿入は`decision_id`（`make_decision`/`db_append_decision`がdetector_node側で両パス完了後に発行するID）を必要とし、Detectorのツールループ実行中（まだJSON出力すら確定していない段階）にはこのIDが存在しないという設計上の制約が判明した。これを解決するには`decision_id`の発行タイミング自体を前倒しする大きめの変更が必要になり、当初懸念していた「責務・呼び出しタイミングの設計変更規模が大きい」問題が実際に顕在化する形になった。

代わりに、挿入処理自体は従来通り`detector_node`側の事後処理のまま維持しつつ、**「この引用がホワイトボード内で一意に一致するか」だけを事前検証できる新規ツール`verify_whiteboard_excerpt`**をDetectorの数値監査パス（tools付き）に追加した。これにより、ツールループ内でtarget_excerpt候補を検証→不一致なら調整して再試行、という当初ユーザーが望んだ自己修正サイクルは実現しつつ、decision_id未確定問題を回避できる。

ただしドメイン妥当性レビュー（tools=None、BL-054で意図的に検算から切り離された軽量パス）はこのツールを呼べない。ドメイン側の引用が優先採用されるケース（severityが同点以上の場合）でその引用が実際には一致しない可能性が残るため、`call_detector`のtarget_excerpt統合ロジックに、選ばれた側の引用が一致しない場合はもう一方の（検証済みの可能性が高い数値監査パス側の）引用へプログラム的に差し替えるフォールバック（`_excerpt_matches_uniquely`）も追加し、ドメイン側単独の弱点を補った。

**対応（実装済み）:**

1. 新規ツール`VERIFY_WHITEBOARD_EXCERPT_TOOL`/ハンドラ`_verify_whiteboard_excerpt_handler`を追加し、`TOOL_DISPATCH`に登録。既存の完全一致→正規化緩い一致という2段判定ロジック（BL-074/076と同型）を流用し、書き込みは行わずvalidateのみ行う。
2. Detectorの数値監査パスの`tools=[...]`にこのツールを追加し、プロンプトに「target_excerptを確定する前に必ず呼び出し、ok=falseなら調整して再試行する」旨を明記。
3. `call_detector`のtarget_excerpt統合ロジックに、選ばれた側の引用が実際にはホワイトボードと一致しない場合、もう一方の引用が一致すればそちらへ差し替えるプログラム側フォールバックを追加。

**完了条件:**

- 新規`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`にBL-079分のテストを含める（`_verify_whiteboard_excerpt_handler`の完全一致/緩い一致/空文字ケース、TOOL_DISPATCH登録確認、プロンプト文言確認、フォールバックロジックの存在確認）。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。
- 実LLM再ドライランでの効果確認（`Whiteboard Annotate Failed`の発生頻度が下がるか）は次回待ち。

---

### BL-080: `write_agreement`のSUPERSEDEがDeliverableの全文更新を破棄し、実質何もしないツール呼び出しになっていた

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-075](issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する)（誘因となったプロンプト）、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（無効化用途との後方互換）、[D-051](../decision_log.md#d-051-write_agreementのsupersedeがdeliverableの全文更新を破棄していた問題の修正) |

**内容:**

ユーザー依頼で1319ドライラン（`log/2026-07-24/1319/log_no_prompt.md`）をフォレンジック調査した結果、深刻な機能不全を発見した。`_commit_agreement_from_tool`の`action_type=="SUPERSEDE"`分岐は、対象topicの旧agreement行を`status="Superseded"`に変更した直後に`return None`しており、Expertが渡した`decision_what`（全文更新の内容）を一切使わず、`apply_whiteboard_patch`も呼ばれず、新しいagreement行のINSERTすら行わないまま、ツール呼び出し自体は`{'success': True, 'message': 'DB update successful'}`という「成功」を返していた。

実ドライランでは以下の連鎖が発生していた:
1. Expertが`edits`（old_text/new_text）でホワイトボードの部分更新を試みるが、テーブル行頭の全角スペース等の不一致で`old_textが見つかりません`エラー
2. BL-075で追加したプロンプト誘導（「完全一致が難しければ`decision_what`による全文更新＝SUPERSEDEを使え」）に従い、Expertが`action_type='SUPERSEDE'`＋`decision_what`（全文）で再試行
3. ツールは`{'success': True}`を返すが、実際にはホワイトボードは一切更新されていない
4. Expertが`read_deliverable_file`で読み戻すと旧内容のままで、「システムの反映タイミングの問題」と誤って自己正当化
5. Detector・Userはこれを（正しくは）ハルシネーション・虚偽の更新完了報告と判定し差し戻すが、Expertは同じ壊れた経路を再試行し続け、同一の失敗が繰り返される無限ループに陥っていた

Detector・Userの判定自体は「ホワイトボードが更新されていない」という観測事実としては正しかったが、原因を「Expertの虚偽報告」と評価していた点は不正確で、真因はツール実装側の欠陥だった。

**対応（実装済み）:**

`entry_type=="Deliverable"`かつ`action_type in ("CREATE", "SUPERSEDE")`かつ`len(decision_what) > 200`（CREATE/UPDATEの全文置換パスと同一の閾値）の場合、CREATEと同様に`apply_whiteboard_patch`で新版を保存するよう修正。SUPERSEDE分岐からの早期`return None`を削除し、CREATE/UPDATE共通のホワイトボード保存・agreements行INSERT処理へ合流させた。BL-062のDetectorによる無効化用途（例: 労基法違反を理由にした短い却下理由のみのSUPERSEDE、ホワイトボードには触れない）は、同じ200文字閾値により従来通りの挙動（ホワイトボード非変更、短文をagreements行のcontentへ直接保持）を維持する。

**完了条件:**

- `_commit_agreement_from_tool`のSUPERSEDE分岐が早期`return None`せず、CREATE/UPDATE共通処理へ合流すること。
- `entry_type=="Deliverable"`かつSUPERSEDE＋長文`decision_what`の場合、`get_latest_whiteboard`で新版が読めること。
- BL-062型の短文SUPERSEDE（無効化用途）はホワイトボードのバージョンを増やさないこと（後方互換）。
- 新規`tests/test_bl080_supersede_deliverable_whiteboard_writeback.py`（3件）: 長文SUPERSEDEのホワイトボード書き込み確認、短文SUPERSEDEの非変更確認（後方互換）、早期returnが削除されていることのソース確認。
- オフラインスモークテスト計125件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの効果確認（1319ドライランと同種のシナリオで、SUPERSEDE後に`read_deliverable_file`が実際に更新後の内容を返すこと）は次回待ち。

---

### BL-081: `write_agreement`の`edits`（old_text/new_text）が、Markdownテーブル行頭の全角スペース・パイプ記号の有無で完全一致に失敗しやすかった

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [BL-080](issue_backlog.md#bl-080-write_agreementのsupersedeがdeliverableの全文更新を破棄し実質何もしないツール呼び出しになっていた)（誘因となった失敗経路）、[BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（同根の正規化緩い一致手法）、[D-052](../decision_log.md#d-052-write_agreementのeditsold_textnew_textにも正規化した緩い一致フォールバックを適用する) |

**内容:**

ユーザーがBL-080修正後の同じ1319ドライラン（`log/2026-07-24/1319/log_no_prompt.md`）を指して「やはりまだ、ホワイトボードの差分書き換えに苦労しているようです」と再調査を依頼。ログを確認したところ、Expertが最初に試みた`edits`（old_text/new_text）による部分更新が、以下のようなMarkdownテーブル行頭・行末の書式差だけで完全一致に失敗していたことを特定した：

- old_text: `D-1. オペレーター給与（**3名**常駐） | 500×**3** | ...`
- 実際のホワイトボード: `| 　D-1. オペレーター給与（**3名**常駐） | 500×**3** | ... |`（先頭に`| `＋全角スペース、末尾に` |`）

この完全一致失敗がBL-080で発覚した壊れたSUPERSEDE全文置換経路へExpertを迂回させる直接の引き金になっていた。BL-074/D-050でDetectorの`target_excerpt`向けに確立した「改行・空白・Markdown太字記法・全角半角を正規化した緩い一致」の仕組みを、Expert自身の主たる編集手段である`_apply_text_edits`にも適用すべきと判断した。

さらに調査の過程で、既存の`_normalize_for_loose_match`（BL-074で新設）自体に非対称バグを発見した。半角スペースは判定前にスキップされ結果から完全に除去される一方、全角スペース（`　`）はスキップ判定の対象外だったため、NFKC正規化を経て半角スペース1文字として結果に**残ってしまい**、「同じ意味のはずの全角/半角スペースが正規化後も食い違う」という矛盾があった。

**対応（実装済み）:**

1. `_normalize_for_loose_match`を「まずNFKC正規化 → 正規化後の文字が空白かどうかを判定してスキップ」という順序に変更し、全角/半角スペースを対称に扱うよう修正。あわせてテーブル区切り記号（`|`）もスキップ対象に追加。
2. 新設`_find_loose_match_spans(content, old_text)`が、正規化後の一致箇所を元の文字列上の(開始, 終了)スパンとして返す（`_annotate_whiteboard_with_detector_comment`とは異なり、置換のため範囲全体の逆写像が必要）。
3. `_apply_text_edits`を、完全一致（0件、または複数件でreplace_all未指定）に失敗した場合、上記の緩い一致へフォールバックするよう変更。それでも一意に定まらない場合のみ、従来通り理由付きでエラーを返す。

**完了条件:**

- `_apply_text_edits`が、テーブル行頭の全角スペース・パイプ記号の有無だけの差異ではエラーを返さず、正規化後の緩い一致で置換に成功すること。
- 正規化後も一意に定まらない場合は、引き続き理由付きでエラーを返すこと（安全側の挙動を維持）。
- `_normalize_for_loose_match`の全角/半角スペース非対称バグが解消され、両者が同じ正規化結果になること。
- 新規`tests/test_bl081_edits_loose_match_fallback.py`（5件）: 1319ログ実例の再現確認、正規化後も曖昧な場合の失敗維持確認、完全一致優先の回帰確認、全角/半角スペース対称性の回帰確認、`_find_loose_match_spans`の位置逆写像確認。
- オフラインスモークテスト計130件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの効果確認（1319ドライランと同種のケースで`edits`がその場で成功し、SUPERSEDEへの迂回が発生しなくなること）は次回待ち。

---

### BL-082: task_plannerの計画をホワイトボード化し、先送り事項をタスク間で永続的に申し送りできるようにする

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [BL-073](issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する)（Directive無条件除外の原因となった対症療法）、[D-053](../decision_log.md#d-053-task_plannerの計画をplan_draftsとして永続化し先送り事項をタスク間で申し送る) |

**内容:**

`log/2026-07-24/1349`のドライランで、User AIがtask_1_3完了判定の中で「積雪・通信エリアの区間切り出しの地形照合はtask_2_1/task_2_2で具体化されるべき」という先送り判断を発言した。ユーザーが「この先送り事項は現状消えてしまいますよね？」と質問し、調査の結果、二重の理由で消失することが判明した。

1. `call_decision_extractor`のプロンプトには元々「先送りの検出」ルール（`action_type: "CREATE", entry_type: "Directive", status: "Deferred"`として抽出）が存在するが、**Expert側の抽出ブランチにしか実装されておらず、User AI側の抽出ブランチには存在しなかった**。今回の実例はUser AIの発言だったため、そもそも抽出ルールが適用されずDeliverable承認の一部として埋没した。
2. たとえ正しく`Directive`/`Deferred`として抽出されても、`_build_agreements_context`（LLM向けコンテキストを組み立てる唯一の関数）は`entry_type=="Directive"`を無条件で全除外している（BL-073時代の「完了後もProposedのまま残るDirectiveのノイズ防止」という対症療法の副作用）。つまり先送りの仕組みは設計上存在するが実質的に死んでいた。

ユーザーが「task_plannerが出した計画もホワイトボード化して、先送り事項を書き込めたりできるようにしたい」と提案し、「設計と実装を進めて最後にBL化」「影響範囲や各ノードでの呼び出し忘れ等十分に気を付けて」との指示を受けた。設計は探索エージェントによる現状調査（`state["phases"]`の全消費箇所の洗い出し）と、Plan agentによる批判的レビューの2段階を経た。

**レビューで発見された当初設計の見落とし（対応済み）:**

- **`call_detector`が第3の呼び出し箇所として漏れていた**: `call_detector`は`_build_task_scope_context`を経由せず独自に現在タスクのコンテキストを構築しており、しかも自身のプロンプトに既に「先送り済みの論点はmajorにしない」という緩和ロジックを持っていた（直近2ターンの会話窓のみに依存し、それが窓外へ流れると同じ既知の懸念を再度major判定してしまう）。当初案は`call_expert`/`generate_user_utterance`の2箇所のみを想定していたが、レビューでこの欠落が指摘され、共有ヘルパー`_get_deferred_notes_text`を新設して3箇所すべてから呼ぶ設計に修正した。
- **一括事前シードではなく遅延生成を採用**: task_planner実行時に全タスク分の計画文書を事前生成する案は、チェックポイント再開時（`task_planner_node`の冪等性ガードが再実行をスキップするため）に新規デプロイ後の既存run再開でシードが行われないという互換性ギャップを生むと指摘され、「先送り事項が実際に書き込まれる初回にのみ骨格文書を生成する」遅延生成方式に変更した。
- **マーカー検索の堅牢性強化**: 見出し文字列の検索は当初単純な`str.find`を想定していたが、タスクの`description`（LLM生成の自由文）に偶然見出し文字列が部分一致で含まれるリスクを指摘され、行アンカー付き正規表現（`re.search(r'(?m)^## 先送り事項...\s*$', content)`）に変更。また「次の見出しまでを探す」という区間検出ロジックも、申し送りテキスト自体（LLM生成の自由文）が偶然`\n## `を含んだ場合の境界誤認リスクを指摘され、「見出し直後に固定で挿入する」方式に変更し、区間終端探索ロジックそのものを排除した。

**対応（実装済み）:**

1. `whiteboard_drafts`の完全なミラーとして新規`plan_drafts`テーブルを新設（別テーブルにしたのは、`whiteboard_drafts`が今セッションでBL-080/BL-081という2つの繊細な修正を経たばかりであり、そのキー空間に別用途を混在させるリスクを避けるため）。`get_latest_plan_draft`/`apply_plan_patch`を`get_latest_whiteboard`/`apply_whiteboard_patch`の完全なミラーとして新設。
2. `_render_plan_skeleton(task)`（固定フォーマットの骨格文書生成）、`_append_deferred_note_to_plan`（遅延シード＋行アンカー正規表現＋見出し直後固定挿入）、`_get_deferred_notes_text`（プレースホルダのままなら空文字を返しトークン消費を避ける）を新設。
3. `call_decision_extractor`のJSON出力スキーマに`defer_to_task_id`（`status=="Deferred"`の場合のみ意味を持つ）を追加し、「先送りの検出」指示をExpert・User双方の抽出ブランチに追加（従来の非対称性を解消）。
4. `decision_extractor_node`に`task_id_to_phase_id`/`task_id_to_task`マップを新設（`_resolve_task_transition`の`phase_lookup`と同じ、全フェーズ一巡のパターン）し、`entry_type=="Directive" and status=="Deferred"`かつ`defer_to_task_id`が解決できる場合に`_append_deferred_note_to_plan`を呼ぶ配線を追加。解決できない場合は警告ログのみでスキップ（フェイルクローズ）。
5. `_build_task_scope_context`の返り値に`deferred_notes_text`を追加し、`call_expert`・`generate_user_utterance`に配線。`call_detector`は独自にコンテキストを構築するため`_get_deferred_notes_text`を直接呼び、ドメイン監査・数値監査両パスのプロンプトに反映。

**関連する既知の未対応事項（今回のスコープ外、参考記録）:**

- `Task` TypedDictに`status: str # "pending"/"in_progress"/"completed"/"deferred"`という未使用フィールドが既に存在する（他に一切参照なし）。本機能の先行未完成の試みの痕跡と推測され、`plan_drafts`に置き換わる形のため、将来のクリーンアップ候補として記録するに留める。
- `write_agreement`ツール（`WRITE_AGREEMENT_TOOL`のenum・`_write_agreement_impl`の`valid_statuses`）は`status="Deferred"`を受け付けない。つまりDeferredの作成経路は現状`decision_extractor_node`のみ（この事実がフック地点の選択の裏付けにもなった）。ツール側にDeferredが将来追加された場合、`decision_extractor_node`の該当分岐は`if not wrote_agreement_this_turn:`の内側にあるため実行されない可能性がある点をコードコメントで明記した。
- タスク/フェーズ構造は計画確定後は不変という前提を維持（先送りが新規タスクを生成することはない）。

**完了条件:**

- `plan_drafts`テーブル・`get_latest_plan_draft`/`apply_plan_patch`が`whiteboard_drafts`系と同型で動作すること。
- `_append_deferred_note_to_plan`が遅延シード・複数追記の蓄積・対象未解決時のフェイルクローズ・description内の偶然の部分一致排除のいずれも正しく処理すること。
- `call_expert`・`generate_user_utterance`・`call_detector`の3箇所すべてで先送り事項が参照可能であること（`inspect.getsource`による機械的な配線確認テストで担保）。
- `call_decision_extractor`のExpert・User双方のブランチが`defer_to_task_id`と先送り検出指示を含むこと。
- 新規`tests/test_bl082_plan_drafts_deferred_notes.py`（11件）。
- エンドツーエンドの手動統合確認: `decision_extractor_node`にDeferred抽出をモック注入し、対象タスクの`plan_drafts`に実際に申し送りが書き込まれ、`_get_deferred_notes_text`で正しく読み戻せることを確認済み。
- オフラインスモークテスト計141件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（1349ドライランと同様のケースで、先送り事項がtask_2_1/task_2_2開始時にプロンプトへ実際に現れること）は次回待ち。

---

### BL-083: streaming受信中の`httpx.ReadError`（接続の強制切断）が絞り込んだ例外タプルから漏れ、プロセスクラッシュを引き起こす

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-059](issue_backlog.md#bl-059-streaming受信中のhttpxremoteprotocolerrorが未捕捉でプロセスクラッシュする)、[BL-072](issue_backlog.md#bl-072-httpxreadtimeoutが絞り込んだ例外タプルから漏れstreaming受信中にプロセスクラッシュを引き起こす)（いずれも同型の問題、別の派生例外クラスが漏れていた事例） |

**内容:**

BL-082コミット後、ユーザーが新たなドライラン（`log/2026-07-24/1459`）を実行したところ、Expert(iter=7)が数値表の`edits`編集を試みようとした直後、streaming受信中に以下によりプロセス全体がクラッシュした。

```
httpcore.ReadError: [WinError 10054] 既存の接続はリモート ホストに強制的に切断されました。
httpx.ReadError: [WinError 10054] 既存の接続はリモート ホストに強制的に切断されました。
  at _query_AI_live: for chunk in stream:
```

BL-059/BL-072と同型の問題である。`_query_AI_live`の例外タプルは`(APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError, httpx.RemoteProtocolError, httpx.TimeoutException)`まで拡張済みだったが、プロバイダ側との接続がTCPレベルで強制切断された場合に送出される生の`httpx.ReadError`（`httpcore.ReadError`由来）は含まれておらず、素通りしていた。ログの直前の内容（BL-081修正後の通常のedits編集フロー）を確認したところ、BL-080/BL-081/BL-082のロジック変更とは無関係な、純粋なネットワーク層の例外クラス漏れであることを確認した。

**対応:** 例外タプルに`httpx.ReadError`を追加した。個別の派生例外を都度追加する運用が3回目（BL-059→BL-072→BL-083）であり、根本的には「openai SDK/httpxが送出しうる全ての通信系例外を網羅する」ことは困難なため、将来また未知の派生例外が漏れる可能性は残る（BL-079のDetector自己リトライ構造とは別に、通信層のフェイルセーフとして`Exception`全体を捕捉して指数バックオフ後にプロセスを継続させる、より広い防御層の検討は別途のBLとして扱う余地がある。今回はスコープ外）。

**完了条件:**

- 新規`tests/test_bl083_httpx_readerror_retry.py`（1件）: `_query_AI_live`のソースが`httpx.ReadError`を例外タプルに含むことを確認。
- オフラインスモークテスト計142件Pass、`python -m py_compile`合格。
- 実LLM再ドライランでの再発なし確認は次回待ち。

---

### BL-084: entry_type="Deliverable"のUPDATE/SUPERSEDEがtopic文字列ドリフトでeditsを0件/0件失敗させ続けていた（BL-074の未着手項目の再発）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（今回解消した「まだopen」の完了条件）、[BL-081](issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)（真因ではなかったと判明した緩い一致フォールバック）、[D-054](../decision_log.md#d-054-entry_typedeliverableのupdatesupersede対象特定をtopic文字列ではなくphase_id-task_idで行う) |

**内容:**

ユーザー依頼で`log/2026-07-24/1459`のドライランをレビューする中で、`edits`が2回とも以下のエラーで失敗している事例を発見した。

```
{'success': False, 'error': 'edits[0]: old_textが現在のホワイトボード内容に見つかりませんでした（正規化後の緩い一致も0件でした）。一字一句正確な引用か確認してください。'}
```

BL-081実装後のはずなのに緩い一致まで0件になっている点を不審に思い、ログから該当old_textと実際のホワイトボード内容を抽出して`_apply_text_edits`に直接再投入したところ、**old_text自体は127文字・差分0で完全一致した**。つまりBL-081の正規化ロジックは無関係で、`_apply_text_edits`に渡された`content`引数そのものが空文字だったことになる。

`_commit_agreement_from_tool`のコードを確認すると、UPDATE/SUPERSEDE分岐は以下のように対象agreementを`target_topic`（省略時は自分自身の`topic`）の文字列完全一致で検索していた。

```python
target_topic = args.get("target_topic", topic)
old_content = ""
for a in reversed(get_agreements_from_db(conn, run_id)):
    if a["topic"] == target_topic and a.get("status") != "Superseded":
        old_content = a["decision_what"]
        break
```

実ログのExpertは`target_topic`を一度も送らず、しかも同一task_2_4のUPDATE呼び出しのたびにtopicの言い回しを変えていた（"task_2_4 最大待ち時間シミュレーション（確率論的リスク反映版）"→"task_2_4 結論部の数値整合性修正"→"task_2_4 最大待ち時間シミュレーション（確率論的リスク反映・修正版）"）。`target_topic`が毎回新しく発明された文字列にフォールバックするため既存行と一致せず、`old_content`が空文字のまま`base_content`に渡り、`_apply_text_edits("", edits)`は`content.count(old_text)`が常に0（緩い一致も同様に0）になる。直前の成功例はExpertが偶然topicを一字一句同じにしていただけで、少しでも言い回しを変えると即座に壊れる状態だった。

これはBL-074の完了条件に明記していた「Deliverable本体のtask_id識別への切替はまだ`open`」の項目そのものであり、BL-081（editsの緩い一致フォールバック強化）だけでは原理的に解決できないことが、同一ドライラン内で2回の実害として裏付けられた。

**対応:**

新設`_find_active_deliverable_agreement(conn, run_id, phase_id, task_id)`が、entry_type="Deliverable"のagreementを`(phase_id, task_id)`（`whiteboard_drafts`と同じ識別子）で検索し、`status != "Superseded"`の最新行を返す。`_commit_agreement_from_tool`のSUPERSEDE分岐・UPDATE分岐（対象特定・Freezeチェック・最終Superseded化マークの3箇所）を、`entry_type=="Deliverable"`の場合のみこの新関数を使うよう分岐した。Decision/Directiveは影響範囲を限定するためスコープ外とし、従来通りtopic文字列ベースの挙動を変えていない。

**完了条件:**

- 新規`tests/test_bl084_deliverable_task_id_identification.py`（5件）: 1459ログの実際のtopicドリフトパターンを再現したUPDATE/SUPERSEDE成功確認、Superseded遷移確認、Decision/Directiveの従来挙動が変わっていないことの回帰確認、`_find_active_deliverable_agreement`がSuperseded行を無視することの確認。
- オフラインスモークテスト計147件Pass、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（1459ログと同様に、Expertがtopicを変えながらUPDATE/editsを繰り返すシナリオで成功すること）は次回待ち。

---

### BL-085: ホワイトボード保存時にMarkdownファイルへも書き出す

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 関連 | [D-055](../decision_log.md#d-055-ホワイトボード保存時にdbと並行してmarkdownファイルへ書き出す)、[BL-027](issue_backlog.md#bl-027-cela_mainpyのロガーがimport時点で無条件起動し本番log配下にテスト実行の痕跡が混入する)（同じ理由でテスト時の書き出しをガードした先例） |

**内容:**

ユーザーから「ホワイトボードの中身を保存時にファイルに書き出してほしい」と要望があった。`whiteboard_drafts`はR4以降DB（sqlite）のみに保存されており、中身を確認するにはクエリが必要でsqliteクライアントを開く手間があった。

**対応:**

新設`_write_whiteboard_to_file(phase_id, task_id, version, content, author_role, edit_summary)`を`apply_whiteboard_patch`のDB INSERT直後から呼び出し、`{log_dir}/whiteboards/{phase_id}_{task_id}_V{version}.md`へバージョンごとに個別ファイルとして書き出す（`save_deliverable_to_file`と同様のベストエフォート補助資料という位置づけ、DBが正）。ファイル冒頭に`phase_id`/`task_id`/`version`/`author_role`/`edit_summary`をコメントヘッダーとして埋め込む。DB側のappend-onlyバージョニング方針に合わせ、旧バージョンのファイルを上書き・削除せず全バージョンを個別に保持する。

BL-027（`MultiLogger`のimport時副作用防止）と同じ理由で、`getattr(MultiLogger, "_instance", None) is None`（＝実際のドライラン実行中ではない、テストやimport時）の場合は書き出しをスキップする。BL-080〜BL-084のテストは`tmp_path`上のDBに対し`apply_whiteboard_patch`を大量に呼ぶため、このガードがないと本番`log/`配下がテスト実行のたびに汚染されてしまう。

**完了条件:**

- 新規`tests/test_bl085_whiteboard_file_writeback.py`（3件）: `MultiLogger`初期化済み時にバージョンごとのファイルが書き出されること（内容・ヘッダー・旧版との非混在を確認）、未初期化時は`apply_whiteboard_patch`・`_write_whiteboard_to_file`のいずれもファイルを書き出さないこと。
- オフラインスモークテスト計150件Pass（既存147件＋新規3件）、`python -m py_compile`合格。テスト実行後も実プロジェクトの`log/`配下に新規ディレクトリが生成されていないことを目視確認。
- 実LLM再ドライランでの動作確認（実行のたびに`log/<date>/<time>/whiteboards/`へファイルが生成されること）は次回待ち。

---

### BL-086: 前提エスカレーション経路 + Freeze復活 + ゴール改定（GoalShiftEventの実消費化）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [D-056](../decision_log.md#d-056-前提エスカレーションをツール呼び出し型で実装する)、[D-057](../decision_log.md#d-057-freeze機構を再有効化しdetectorのプロンプトに尊重指示を追加する)、[D-058](../decision_log.md#d-058-stategoalへの部分パッチとgoalshifteventの新規shift_kindpremise_revisionでゴール改定を実消費化する)、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（スコープガードレールは変更せず維持）、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（Freeze一時休止の原因、今回両立させた）、[BL-065](issue_backlog.md#bl-065-r5で新設したdb永続化情報internal_thought_processgoal_shift_eventsの消費表示経路が未設計)（GoalShiftEventの書きっぱなし問題、今回初めて消費経路ができた） |

**内容:**

ユーザーが`log/2026-07-24/2054`の抽出済みホワイトボードをレビューする中で、「必要車両台数を2台、35人定員としているが、オンデマンドバスで35人乗りは変では」と指摘。調査の結果、この矛盾は`task_2_1`（[phase_2_task_2_1_V1.md](../../../log/2026-07-24/2054/whiteboards/phase_2_task_2_1_V1.md)）で予算制約（導入台数上限2台）を先に固定し、そこから「ピーク需要をρ<1で捌くには定員をいくつまで上げればよいか」を逆算した結果であり、オンデマンド輸送は本来分散した需要に小型車両で即応するのが定石であるという前提とは根本的に矛盾していることが判明した。

ユーザーがさらに「そもそも論というか、視座の設計が大事」「今の状態ではコンサルが数字をこねくり回して実際のPOCで即死するのが見える」と、より一般的な構造上の問題を指摘。調査の結果、以下の三重の構造的欠陥を特定した。

1. Expertは`absolute_constraints`の文言を厳守することしかできず、「この制約の立て方自体が本来解決すべき課題（高齢者の移動手段確保）に対して逆効果かもしれない」と気づいても表明する手段が無い（BL-025のスコープガードレールは他タスクへの越権防止が目的で、そもそも論を封じる意図ではないが、結果的に同じ「厳しく限定された思考空間」を作っている）。
2. たとえUser AIが例外を承認しても、それを恒久的にピン留めする`Freeze`機構はD-045で意図的に無効化されたままであり、次のDetector監査で同じ論点が独立に`major`判定→SUPERSEDEされ承認が無限に覆される（BL-062はDetectorの独立した正しさを守るために作られたが、その代償として「人間が既に審議した例外」を区別する手段が失われた）。
3. ゴール自体（`state["goal"]`という単一文字列）を書き換える手段が無く、`GoalShiftEvent`（`detect_goal_shift`/`goal_shift_events`）は`arbiter_node`の資源再配分判定からしか発火せず、発火してもDB書き込みのみで何も消費しない「書きっぱなし」（BL-065）。

ユーザーの指示「エスカレーション経路を作り込み、freezeを復活させ、高齢者の移動手段の確保という本質的課題の解決という視点に登り、当初目標を越境しても最適な着地点に到達できるようにしたい」を受け、Plan mode（Exploreエージェント3件による現状調査＋Planエージェント1件による設計、全ての重要な行番号・関数シグネチャを直接読み込みで裏取り済み）で設計・実装した。

**対応（実装済み）:**

1. 新設`goal_escalations`テーブル（単発の意思決定レコード、版管理文書の`plan_drafts`とは性質が異なるため独立テーブルとした）。
2. 新設ツール3種: `escalate_premise_concern`（Expert・User AI双方が呼べる、BL-025のスコープガードレールは一切変更せず「提起のみ・スコープ外行動の許可ではない」旨をツール説明文自体に明記）、`resolve_premise_concern`（User AI専用、却下）、`revise_goal`（User AI専用、承認・ゴール改定。`state["goal"]`という長大プローズ文への部分パッチに、Deliverable編集で実績のある`_apply_text_edits`をそのまま再利用し全文置換による想定外欠落を回避。任意で`freeze_agreement_id`を指定すればその場でFreezeも実行）。
3. ツールハンドラはLangGraph stateに直接触れられないため、`_LAST_WRITE_AGREEMENT_SUCCEEDED`等と同型の「直前アクション」モジュールグローバル`_LAST_GOAL_REVISION`＋getterを新設し、`generate_user_utterance_node`が`state["user_wrote_agreement"] = ...`と同じ並びで`state["goal"]`へ反映する。`state["goal"]`は9箇所の消費者（call_expert/call_detector/call_resource_arbiter等）が毎ターン新鮮に再埋め込むため、この1箇所の代入だけで全消費者に自動伝播する（個別配線不要）。
4. `revise_goal`は`db_append_goal_shift_event`（既存の書き込み関数）を使い新規`shift_kind="premise_revision"`、`triggered_by="Escalation_Resolution"`、`from_goal_state`/`to_goal_state`に実際の改定前後テキストを記録する。GoalShiftEventにとって、arbiter経由の`constraint_hit`に次ぐ初の実効的な発火・消費経路となる。
5. Freeze（`FREEZE_AGREEMENT_TOOL`/`freeze_agreement`/`is_frozen`ガード）をD-045以来初めて`generate_user_utterance`のtools（User AI）へ再配線。あわせて、Freeze復活の前提となる欠落——`call_detector`が🔒Freeze済み項目の意味を一切知らなかった問題——を解消するため、ドメイン妥当性パス（新設`_get_frozen_agreements_text`で軽量に埋め込み）・数値監査メインパスの両方に「🔒項目は人間が既に審議し承認した意図的な例外であり、同じ論点をmajor/minorの根拠にしない（ただし新規の別問題は従来通り厳格に評価）」という指示を追加した。
6. Expert向け`_get_escalation_status_text_for_expert`（Open/Rejectedのみ表示、Acceptedは`state["goal"]`自体が既に改定済みのため二重通知しない）、User AI向け`_get_open_escalations_text`（未解決分を毎ターン提示し「今回必ず解決する」よう指示、先送りループを防止）を新設し配線。

**完了条件:**

- 新規`tests/test_bl086_escalation_freeze_goal_revision.py`（18件）: エスカレーション提起（役割ゲート・必須項目）、却下パス（役割ゲート・二重解決防止・Decision記録）、承認パス（役割ゲート・未知ID・edits不一致時のOpen維持・goal_escalations/goal_shift_events反映・Freeze同時実行とその後のSUPERSEDE拒否）、`generate_user_utterance_node`の`state["goal"]`反映、3箇所（call_expert/generate_user_utterance/call_detector）の`inspect.getsource`配線確認（ExpertのソースにResolve/Reviseツールが含まれないことでナローチャネルを機械的に保証、DetectorのソースにEscalation系ツールが一切含まれないことも確認）。
- 既存`tests/test_r5_thought_log_freeze_goalshift.py`（14件）は無変更で全件Pass。
- `tests/test_bl062_detector_supersede.py`の`test_bl062_freeze_tool_removed_from_user_ai_tools`を`test_bl086_freeze_tool_reactivated_in_user_ai_tools`に更新（対象を`generate_user_utterance_node`から実際にtools=[...]を持つ`generate_user_utterance`へ修正しつつアサーションを反転、D-045からの意図的な転換を明記）。
- オフラインスモークテスト計168件Pass（既存150件＋新規18件）、`python -m py_compile`合格、`check_docs_consistency.py`合格。
- 実装計画は`docs/design/r5/cela_r5_escalation_freeze_goalrevision_impl_Plan.md`に保存済み。
- 実LLM再ドライランでの効果確認（Expertが今回のような前提矛盾に気づいた際に実際に`escalate_premise_concern`を呼び、User AIが`revise_goal`で応答し、次のDetector監査が同じ論点を再度major判定しないこと）は次回待ち。

---

### BL-087: 前提の質を上げる一連の改善（task_plannerの曖昧表記禁止・二重指示バグ修正・task_plan_reviewer_node等）

| 項目 | 内容 |
|------|------|
| 状態 | `partial`（Stage 1・2・3・4は`done`、Stage 2'・5は`open`） |
| 優先度 | P1 |
| 関連 | [BL-069](issue_backlog.md#bl-069-expertが決定前にフェーズタスク表全体を見渡して他フェーズとの資源競合に気づけるよう軽量な指示を追加する)（Stage 4で合流予定）、[BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（`escalate_premise_concern`等4ツール、本BLはその実効性検証から派生） |

**内容:**

BL-086実装後の実LLMドライラン（`log/2026-07-24/2358`）レビューで、`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`/`freeze_agreement`の4ツールが全ターンで`tools attached`として付与されているにもかかわらず、実行呼び出しが一件もゼロであることを発見。ログを精査した結果、思考文（💭）中にもツール名自体への言及が一切無く、ツールの存在を能動的に想起した形跡すら無かった。原因調査の結果、`call_expert`（`_get_escalation_status_text_for_expert`）・`generate_user_utterance`（`_get_open_escalations_text`）のいずれも、既存のエスカレーションが存在する場合にのみツールの使い方を説明する条件付き文言であり、エスカレーションがまだ1件も無い（＝初回で最も必要な）状況では、ツールの存在自体が一切説明されていなかったことが判明。

**対応（Stage 1、実装済み）:**

1. `call_expert`のフル`system_prompt`（【制約と条件の切り分け】セクション直後）に、`escalate_premise_concern`の使用条件（狭く構造化された懸念限定、スコープ免除にはならない、当該ターンのacceptance_criteriaは通常通り満たす、重複提起禁止）を恒久的に明記。あわせて`light_system_prompt`（ツールループiter≥2以降、従来4ツールへの言及が皆無だった箇所）にも1行のリマインダーを追加。
2. `generate_user_utterance`の標準指示（同種のセクション直後）に、`escalate_premise_concern`（自ら起点になれる）・`resolve_premise_concern`・`revise_goal`・`freeze_agreement`の4ツールすべての使いどころを恒久的に明記（`freeze_agreement`は従来`revise_goal`経由の言及しかなく単独使用の説明が皆無だった）。
3. 効果確認として翌ドライラン（`log/2026-07-25/0935`）をレビューしたところ、User AIの思考文に初めて`escalate_premise_concern`という単語が名指しで登場（「Let me also think about whether I should use escalate_premise_concern or just directly reject.」）。今回は「ゴール自体の前提矛盾ではなく`task_1_3`の`acceptance_criteria`表記の曖昧さによるExpertの誤読」と判断し不使用を選択したが、この切り分け自体は妥当であり、少なくとも検討の俎上に載るようになったことを確認。
4. 同じ`log/2026-07-25/0935`のレビュー中に、`task_1_3`で`acceptance_criteria`の"(12km区間)"という表記が「位置」か「長さ」かを一意に確定できず、Expertが同一の誤読（15%=2.175kmを12km全区間=82.8%と誤定義）を4回連続で繰り返しV1→V9（9版）の無駄な往復が発生している事例を発見。`call_task_planner`のプロンプトに、比率/絶対値等の指標の取り違えを防ぐ曖昧表記禁止指示と、今回の失敗例をNG例として追加（項目4として新設）。**追記（ユーザー指摘）**: `call_task_planner`は比率・分割・単位換算等の計算（例：面積比から距離を求める、予算から購入可能台数を見積もる）を暗算に頼っていたため、`tools=[PYTHON_REPL_TOOL]`を付与し、計画分解時点から機械計算を使わせる（項目5として新設。プロジェクト最上流のハルシネーションリスクという同じ理由で`call_goal_essence_analyst`・`call_task_plan_reviewer`にも同様に付与済み、下記12参照）。**関連バグ（[BL-088](issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)として別途起票**: Stage2改善実装後の実ドライラン（`log/2026-07-25/1642`）で、task_plannerがコードフェンス前に一言添える応答パターンにより、この`_safe_json_parse`のバグでtask_plan_reviewer_nodeの差し戻しリトライ予算が2回とも無駄撃ちされる事象を発見・修正。
5. さらに、User AIの標準指示（`user_always_remembers or turn_count==1`ブロック）が無条件に「合意に達したら相手のAIに成果物の出力を指示せよ」と指示しており、R4のホワイトボード方式で既にApproved済みの成果物に対しても再提出を要求し、Expertが「既に提出済みなのに再度出力を求められている」と混乱する余地があったバグを修正。「未充足の要求項目が無く、かつホワイトボードに成果物が既に存在する場合は、再提出を求めず次のタスクへ進行する」という条件分岐を追記。
6. ユーザーからの追加要望「監査・検算ループ自体は機能するが、その前提となる計画・目標理解が歪んでいると徒労に終わる」「バス3台で無理と分かった時点で"バスである必要は？タクシー補助では？"という一段上の思考をAIにさせたい」を受け、Plan modeで段階的な改善計画に合意（`docs/design/`外、Claude Codeのplanファイル`task-plan-reviewer-node-task-planner-glistening-coral.md`として保存）。

**対応（Stage 2、実装済み）:**

7. 新設`call_task_plan_reviewer(phases, goal)`: Detector同等のJSON（`risk`/`constraint_issue`/`comment`/`observations`）で、生成された`phases`全体を「曖昧な表記」「タスクの過不足」「depends_onの順序妥当性」の3観点からレビューする。個々のタスクの中身の是非ではなく計画の構造自体を見る、実行前1回きりのゲート。**追記（ユーザー指摘）**: 新規追加ノードが暗算に頼るとプロジェクト最上流でのハルシネーションリスクが後続全タスクに伝播するため、`tools=[PYTHON_REPL_TOOL]`を付与し、曖昧表記の実際の矛盾有無（例：比率と絶対値の整合性）を暗算でなく機械計算で確認するよう指示。
8. 新設`task_plan_reviewer_node`をグラフに追加（`graph.add_node("task_plan_reviewer", ...)`、`graph.add_edge("task_planner", "task_plan_reviewer")`、`route_after_task_plan_reviewer`による条件分岐で`phases`が空なら`task_planner`へ、そうでなければ`generate_user_utterance`へ）。`constraint_issue="major"`かつ`state["plan_reviewer_retry_count"] < 2`なら`state["phases"]`をクリアして差し戻し（`task_planner_node`の既存ガード`not state.get("phases")`により自然に再生成される）、指摘事項は新設`state["plan_reviewer_feedback"]`に保存。上限（2回）到達後はmajorが残っていても`plan_review_done=True`として強制承認し、無限ループを防止する。
9. `call_task_planner`に`reviewer_feedback: str = ""`引数を追加し、差し戻し時は再生成プロンプトの先頭に「前回の計画案への差し戻し」ブロックとして指摘事項を注入。`task_planner_node`が`state["plan_reviewer_feedback"]`を読み取って渡し、消費後にクリアする。
10. 新設`state["plan_review_done"]`は、`task_planner_node`の`turn_count==1`ガードと同型の冪等性ガード。このグラフは「entry_pointが常にtask_planner固定」で毎ターンtask_planner_node/task_plan_reviewer_nodeを通過する構造（チェックポイント再開コメント参照）のため、このガードが無いと2ターン目以降も毎回レビューLLMが再発火しトークンを浪費する。

**対応（Stage 3、実装済み）:**

11. 新設`goal_essence`テーブル（`run_id`単位で1行、`true_essence`/`feasibility_notes`/`created_at`）。BL-086の`goal_escalations`（走行中に前提矛盾に気づいた際の事後エスカレーション）とは独立・併存する事前予防機構と位置づけ。
12. 新設`call_goal_essence_analyst(goal)`: task_planner分解より前に1回だけ呼ばれ、(1)ゴール文に明示された数値制約からの大まかな実現可能性の壁打ち（詳細検算はF-2.6の役目であり、ここではオーダー感の確認に留めるが、暗算は禁止し`tools=[PYTHON_REPL_TOOL]`で機械計算させる——プロジェクト全体で最も上流の判断であるため暗算によるハルシネーションが後続の全タスクに伝播するリスクを重視、ユーザー指摘）、(2)個々の制約はあくまで「本来解決すべき本質的な課題」の手段・例示に過ぎない可能性を踏まえた本質の言語化、の2点をJSON（`true_essence`/`feasibility_notes`）で返す。
13. 新設`goal_essence_node`をグラフの新しい`entry_point`として追加（旧`task_planner`から変更、`graph.add_edge("goal_essence", "task_planner")`）。新設`state["goal_essence_done"]`により、`task_plan_reviewer_node`の`plan_review_done`と同型の冪等ガード（チェックポイント再開・毎ターン再入場のたびにレビューLLMが再発火しないため）を持つ。
14. 新設`_get_goal_essence_text(conn, run_id)`（未生成時は空文字）を、BL-086 D-058で確認された`state["goal"]`の9消費者すべて（`call_orchestrator`/`call_expert`/`call_detector`〈数値監査・ドメイン妥当性の両パス〉/`call_reflection`/`generate_user_utterance`は`state`から直接、`call_resource_arbiter`/`call_facilitator`/`call_integrator`/`call_reviewer`は新設`goal_essence_text: str = ""`引数経由で呼び出し元ノードから）へ、ゴール本文と並べて常時注入。**追記（ユーザー指摘、注入漏れの修正）**: D-058の9消費者はBL-086時点のリストであり、Stage2で新設した`call_task_planner`・`call_task_plan_reviewer`（task_planner分解・その直後のレビューという、本質フェーズの効果が最も発揮されるべき箇所）が含まれておらず本質テキストが渡っていなかった。両関数にも`goal_essence_text: str = ""`引数を追加し、`task_planner_node`・`task_plan_reviewer_node`から`_get_goal_essence_text`の結果を渡すよう修正（計11箇所への注入）。既存の`arbiter_node`/`facilitator_node`/`integrator_node`呼び出しをモックしていた4件の既存テスト（`test_bl041_bl050.py`/`test_bl061_facilitator_reflection_note.py`/`test_r4_smoke.py`/`test_r5_thought_log_freeze_goalshift.py`）が、新しい`goal_essence_text`キーワード引数を受け取れない固定シグネチャのfakeのため落ちたのを`**kwargs`許容に修正。

**対応（Stage 4、実装済み）:**

15. `call_detector`のドメイン妥当性レビューパスに「上記【🎯 本質】に照らして、数値・条件設定自体は妥当でも本質から乖離していないか」を確認する指示を追加し、乖離があればconstraint_issueをminor以上に引き上げる根拠にできるとした（BL-069の「木を見て森を見ず」対策と合流）。
16. `generate_user_utterance`の標準指示（検算とドメインレビューの役割分担セクション直後）に、同様の本質整合性チェックと、疑義がある数値は自身の判断でも根拠を問い直す指示を追加。

**対応（Stage 2改善、実装済み）:**

実ドライラン（`log/2026-07-25/1549`）をユーザーがレビューした結果、Stage2の`task_plan_reviewer_node`に3つの新しい問題が判明した。1回目のレビューで、`task_1_3`が注記付きで示した推定値（「山間部2km≒ルート全体13.33km」、原文12kmとの端数差はごくわずか）を「ルート長の矛盾」としてmajor判定し差し戻した結果、再生成された`task_planner`が「山間部12km＝ルート全体の15%」という原文からは読み取れない解釈で「総ルート長80km」という、ゴール文に存在しない数値をでっち上げてしまった。Reviewerが絶対値の確定を過度に要求したことがハルシネーションを誘発した実例。

17. `call_task_plan_reviewer`のプロンプトを較正: (a) 4つの評価観点（曖昧表記/タスク過不足/順序妥当性/条件の明示〈新設〉）を同等以上に重視するよう明記し、数値精度の指摘に偏らないようにした。(b) 「ゴール文自体が与えていない絶対値を無理に確定させる差し戻しをしてはいけない」というアンチパターンを、上記80km捏造の実例を埋め込んで明記（Stage 1aで`task_1_3`の実例を埋め込んだのと同じパターン）。ゴール文に絶対値の記載がなければ「不明である旨を明記させる」軽い修正指示に留め、数値の逆算・断定を要求しないこととした。
18. `call_task_planner`に項目6「【派生値には根拠条件を併記】」を新設。「車両3台が上限」のような派生値（ゴール文に直接の記載がない数値）を書く際は、結論の数値だけでなく前提条件（例:「新品購入の場合」）を必ず併記し、リース等の代替調達で数値が変わりうる場合はその旨も注記させる。条件を欠いた断定が、後続AIに絶対制約と誤読され代替案の検討余地を失わせるリスクへの対策（`call_task_plan_reviewer`にも対応する評価観点として反映、上記17(a)）。
19. `plan_drafts`（BL-082、フェーズ・タスク表のホワイトボード化）に、task_plan_reviewerが指摘を書き込めるよう拡張。`_render_plan_skeleton`に「先送り事項」と並ぶ第二セクション「## レビュワーからの指摘（要修正）」を追加し、新関数`_append_reviewer_comment_to_plan`（`_append_deferred_note_to_plan`の完全なミラー）を新設。Detector注釈（`_annotate_whiteboard_with_detector_comment`）のような文中excerpt一致は使わず、task_idという確実なキーで対象を特定する方式を採用（BL-074/076で既知の引用文字列マッチングの脆さを踏襲するリスクを避けるため）。
20. `call_task_plan_reviewer`の出力JSONに`per_task_comments: [{"task_id", "comment"}]`を追加し、`task_plan_reviewer_node`が各タスクの指摘を対応する`plan_drafts`へ書き込むよう配線。`task_planner_node`は初期計画生成直後（レビューが動く前）に全タスク分の`plan_drafts`スケルトンを事前生成するよう変更（従来は`_append_deferred_note_to_plan`が呼ばれるまで存在しない遅延生成のみだったため、レビュー時点では書き込み先が無かった）。`state["plan_reviewer_feedback"]`も、全体講評＋タスク別指摘（`[task_id] comment`形式）を整形結合したテキストに変更し、task_planner再生成時にどのタスクのどの記述が問題かをピンポイントで伝える。
21. `_get_deferred_notes_text`の抽出範囲を、末尾までではなく次の見出し（`## レビュワーからの指摘`）の直前までに限定する修正（19でセクションを追加した副作用で、従来は末尾まで読んでいたため新セクションの内容が先送り事項テキストに混入するバグが発生していたのを修正）。
22. 実ドライラン（`log/2026-07-25/1705`）で、`task_planner`が全15回（`MAX_TOOL_ITER`、既存のグローバル定数・BL-014/BL-028で確立済みのAPI障害対策、変更せず）のツールループを使い切り、最終iterationの強制テキスト応答（ツール利用不可）として26タスク分のJSON全体を一度に出力せざるを得ない事態を発見。実際の`python_repl`呼び出し内容を精査したところ、前半9回は正当な数値計算だったが、終盤5回は「acceptance_criteriaが3個以内か」「depends_onの整合性」等、新しい情報を生まない同一内容の「念のため最終確認」の繰り返しだったと判明（Stage1・Stage2改善で`call_task_planner`の【重要】項目が6つに増え、遵守すべきチェック項目が増えたことで再確認欲求が強まった可能性）。大規模な計画では、この繰り返しに終盤の余地を奪われた結果、最終強制出力のJSONが途中で切れて構文エラー・fallback化（BL-088と同じ被害形態、トリガーはブレース優先バグではなくトークン打ち切り）するリスクがある。`call_task_planner`のプロンプトに項目7「【計算・検証は各回1回まで、繰り返し確認しない】」を追加し、同一内容の再確認をやめて検証完了後は直ちに最終JSON記述に移るよう明示した。

**Stage 2'・5（`open`、設計のみ・実装は別途）:**

- **Stage 2'**: 各フェーズ完了時に、完了フェーズで判明した事実・矛盾・確定値を踏まえてtask_plannerが未着手の残りフェーズ・タスクのみを再分解する機構。
- **Stage 5**: 「一段上の思考」をプロンプトでの自発性に頼らず機械的トリガーで強制発火させる。トリガーはOR条件（1）`global_constraints`の`claimed/total_cap`比が閾値（初期値0.9）以上（既存`check_global_constraint_overrun`は完全超過のみ検知するため姉妹関数が必要）、（2）`expert_retry_count>=3`（既存、`route_after_expert_detector`が既に"reflection"分岐に使用）。新規ノードは作らず既存`reflection_node`/`call_reflection`に3つ目の監査観点として追加し、懸念があれば次のExpert/User AIターンへ申し送り、Expert/User AI自身に`escalate_premise_concern`を呼ばせる動線とする。

**完了条件（Stage 1〜4）:**

- 新規`tests/test_bl087_task_planner_prompt_and_resubmission_fix.py`（4件）: `call_task_planner`プロンプトへの曖昧表記禁止指示・失敗事例の埋め込み確認、`generate_user_utterance`への再提出抑制条件分岐確認、項目22の重複再確認抑制指示の埋め込み確認（いずれも`inspect.getsource`による静的確認）。
- 新規`tests/test_bl087_stage2_task_plan_reviewer_node.py`（21件）: `plan_review_done`済み・`phases`未確定時のスキップ、`constraint_issue=none`時の承認、`major`時の差し戻し（`phases`クリア・`retry_count`加算・`feedback`保存）、差し戻し上限到達後の強制承認、`call_task_planner`への`reviewer_feedback`注入・非注入時の確認、`build_graph`が`task_plan_reviewer`ノードを実際に配線していることの確認、`call_task_plan_reviewer`/`call_task_planner`が`PYTHON_REPL_TOOL`を付与されていることの確認。Stage2改善分（11件追加）: Reviewerプロンプトの較正確認（構造的観点の同等重視・80km捏造アンチパターンの埋め込み・`per_task_comments`出力形式）、`call_task_planner`の根拠条件併記指示確認、`_render_plan_skeleton`の新セクション確認、`_append_reviewer_comment_to_plan`のroundtrip/蓄積/unresolvable時のno-op、`_find_phase_id_for_task`、`task_planner_node`のplan_draftsスケルトン事前生成、`task_plan_reviewer_node`の`per_task_comments`書き込み・`plan_reviewer_feedback`整形結合の確認。
- 新規`tests/test_bl087_stage3_4_goal_essence.py`（26件）: `goal_essence`テーブルのDB層roundtrip・冪等性、`goal_essence_node`のスキップ/保存、`build_graph`の`entry_point`が`goal_essence`であることの確認、11消費者すべてへの注入配線確認（`call_task_planner`/`call_task_plan_reviewer`を含む、`inspect.getsource`/`inspect.signature`による静的確認）、Stage4のDetector/User AI本質整合性チェック追加の確認、`call_goal_essence_analyst`が`PYTHON_REPL_TOOL`を付与されていることの確認。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。
- Stage 2'・5は本BLの完了条件に含めず、着手時に新規BLを起票する。

---

### BL-088: `_safe_json_parse`がコードフェンス前に説明文が付いたJSON配列をfallbackへ握りつぶすバグ

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（このバグにより差し戻しリトライ予算が無駄撃ちされる事象から発見） |

**内容:**

BL-087 Stage2改善実装後の実ドライラン（`log/2026-07-25/1642`）をユーザーの依頼でレビューする中で、`task_plan_reviewer_node`が1〜2回目の`task_planner`出力を「acceptance_criteriaが極めて曖昧」「タスクが単一で全く分解されていない」としてmajor判定・差し戻していたが、ログを遡ると実際のLLM応答（💬発言）は5〜6フェーズに正しく分解された詳細な計画であったことが判明。`[task_planner] フェーズとタスクの分解結果`として実際に記録・レビューへ渡っていたのは、`call_task_planner`の`fallback_phase`（`phase_1`/`task_1_1`のみの縮退計画）だった。

原因を`_safe_json_parse`（`cela_main.py`）で特定: 「段階2」の開始位置探索ロジックが、
```python
brace_idx = cleaned.find("{")
bracket_idx = cleaned.find("[")
start = brace_idx if brace_idx != -1 else bracket_idx  # brace_idxが見つかれば常に優先
```
という実装で、`brace_idx`が見つかりさえすれば、それが`bracket_idx`より後の位置にあっても常に`brace_idx`を採用していた。`call_task_planner`のトップレベルは配列（`[{...}, {...}]`）であり、かつ今回のLLM応答はコードフェンス直前に「それでは、フェーズ分解を提示します。」のような一文を添えるパターン（LLMの一般的な癖）だったため、「段階1」（`cleaned.startswith("```")`によるフェンス除去）が発火せず、「段階2」で本来の開始位置である`[`より後にある最初のオブジェクトの`{`から`cleaned`を切り出してしまい、`[`を欠いた構文的に不正なJSON（`{...}, {...}]`）になっていた。これが`json.loads`失敗→fallbackという経路をたどり、縮退計画に化けていた。

このバグは`_query_and_parse_with_retry`（層2リトライ、パース失敗を検知して同一呼び出しをリトライする既存の防御機構）を経由しない`call_task_planner`で発生しており、パース失敗が直接fallbackとして確定してしまう。さらに、BL-087 Stage2の`task_plan_reviewer_node`は差し戻し上限を2回に制限しているため、`1642`のドライランでは1・2回目とも本バグによる縮退計画の却下で予算を使い切っており（内容面での差し戻しは実質ゼロ）、もし3回目（最終・強制承認）でも再現していれば、縮退計画がそのまま最終計画として承認され走行が続くところだった。

**対応（実装済み）:**

`_safe_json_parse`の該当ロジックを、`brace_idx`/`bracket_idx`のうち`-1`でないものの中で最小値（＝より先に現れる方）を採用するよう修正した。

**完了条件:**

- 新規`tests/test_bl088_safe_json_parse_bracket_precedence.py`（3件）: `1642`ログの実際の失敗パターン（コードフェンス前に説明文＋トップレベル配列）の再現確認、トップレベルがオブジェクトの通常ケースが従来通り動作することの回帰確認、`{`も`[`も含まれない完全な非JSON応答でfallbackを返すことの確認。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。

---

### BL-089: 複数JSONフェンスブロックの混線によるレビュー安全ゲートの無効化、および全ノード共通の重複再検証の抑制

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 関連 | [BL-088](issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)（同根の`_safe_json_parse`脆弱性）、[BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（`task_plan_reviewer_node`の差し戻しゲートが影響を受けた） |

**内容:**

BL-088修正後、ユーザー依頼でドライランを再実行し`log/2026-07-25/1814`をレビューしたところ、task_plannerの出力がmax_tokens相当の理由で文字列途中（`"depends_on": ["task_1_2", "task_1_3", "task_`）で切れ、縮退計画（`fallback_phase`）にフォールバックした。ここまではBL-088と同種の別トリガーだが、より深刻だったのは次の段階: `task_plan_reviewer_node`はこの縮退計画を正しく認識し、思考過程では「タスクの過不足 - MAJOR」「絶対にrework確実」と明確に`constraint_issue="major"`の判定を下していた。しかし実際の応答は、「### per_task_comments」セクションでまず`per_task_comments`フィールドだけのプレビュー配列を```json```ブロックとして書き、その後「### 最終JSON出力」セクションで本物の完全なオブジェクトを別の```json```ブロックとして書く、という2段構成になっていた。`_safe_json_parse`は「複数のJSONブロックが存在しうる」ことを想定しておらず、1つ目の小さな配列ブロックの開始位置から2つ目のオブジェクトブロックの終了位置までを不整合な形で切り出してしまい構文エラー、fallback（`constraint_issue="none"`）に化けた。結果、`plan_reviewer_retry_count`は0のまま`plan_review_done=True`となり、縮退計画がそのまま承認されて実行フェーズへ進行（`log/2026-07-25/1814/whiteboards/`に`phase_1_task_1_1`のみが存在することで確認）。安全ゲートであるレビュワーの判定が、パース層の欠陥によって「正しい差し戻し判定」から「誤った承認」へすり替わるという、BL-088より一段深刻な事故だった。

**対応（実装済み）:**

1. `_safe_json_parse`の段階1（マークダウンコードブロック除去）を、「先頭が```で始まるか」という単純な判定から、正規表現で全```json```/```` ``` ````フェンスブロックを検出し、**最後の**ブロックを採用する方式に変更（モデルが「最終的な答え」を最後に書く慣習に従う）。これによりBL-088のケース（フェンスが1つだけ、その前に説明文がある）も、今回のケース（フェンスが複数ある）も同じロジックで正しく処理できる。フェンスが1つも無い場合のみ、従来のbrace/bracket探索ロジックにフォールバックする。
2. `call_task_plan_reviewer`・`call_task_planner`・`call_goal_essence_analyst`を、既存の層2リトライ機構`_query_and_parse_with_retry`（D-005、`call_reviewer`/`call_detector`の一部パスで既に採用されていた安全網だが、この3関数には未適用だった）でラップし、単発のパース失敗で即座にfallbackへ落ちず、最大2回まで呼び出し自体をリトライするようにした。
3. `call_task_plan_reviewer`は実行前の安全ゲートという性質上、層2リトライを使い切ってもなおパース失敗した場合、`"none"`（フェイルオープン=黙って承認）ではなく`"major"`（フェイルクローズ=差し戻し）を返すよう変更（`call_reviewer`の既存のフェイルクローズパターンを踏襲）。`call_task_planner`自体は従来通り`fallback_phase`（縮退計画）へ落ちるが、これは後段の`task_plan_reviewer_node`が検知してmajor判定する前提のため、fail-closed化は不要と判断した。

続けて、ユーザーが同じ`log/2026-07-25/1705`・`1814`のレビューを踏まえ「他のノードも何回も何回も同じ思考を繰り返しすぎることが多々ありました」と指摘。`task_planner`には既にBL-087項目22として「計算・検証は各回2回まで、繰り返し確認しない」指示を追加済みだったが、これを`tools=[...]`でpython_repl等のツールアクセスを持つ他の全ノードにも展開した。

4. `tools=None`でツールループ自体を持たない`call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`を除く、以下8関数のプロンプトに同種の「同じ検証・計算を繰り返さない」指示を追加: `call_expert`、`call_detector`（主検算パス。既存の「判定のブレ防止（3回多数決方式）」とは別観点＝同一計算の反復防止として追加）、`call_resource_arbiter`、`call_integrator`、`call_reviewer`、`generate_user_utterance`、`call_goal_essence_analyst`、`call_task_plan_reviewer`。
5. `call_task_plan_reviewer`には追加で、「最終回答の```json```ブロックは1つだけ書くこと（下書き・プレビューと最終版の2段構成にしない）」という指示も加え、今回発見した複数ブロック混線の再発を防ぐ。

**完了条件:**

- 新規`tests/test_bl089_json_fence_and_failclosed_review.py`（8件）: `_safe_json_parse`が複数フェンスブロックのうち最後を採用すること（`1814`の実際のパターン再現）、単一フェンス+先頭プローズ（BL-088ケース）の回帰確認、フェンス無しでのbrace/bracket探索フォールバック確認、`call_task_plan_reviewer`/`call_task_planner`/`call_goal_essence_analyst`が層2リトライで単発パース失敗を吸収すること、`call_task_plan_reviewer`がリトライ失敗後に`major`へフェイルクローズすること、`call_task_planner`がリトライ失敗後は従来通り縮退計画を返すこと。
- 新規`tests/test_bl089_anti_repetition_instructions.py`（9件）: 対象8関数それぞれに重複検証抑制指示が含まれることの確認（`inspect.getsource`による静的確認）、`call_task_plan_reviewer`の単一JSONブロック指示の確認、`call_task_planner`の既存指示（BL-087項目22）が引き続き存在することの回帰確認。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。

---

### BL-090: goal_essence_analystがJSON文字列値の末尾を全角鉤括弧で終え、閉じ引用符を書き忘れる

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P3 |
| 関連 | [BL-089](issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)（層2リトライにより本バグは自己修復済み、実害なしだった） |

**内容:**

BL-089修正後のドライラン（`log/2026-07-25/1913`）をユーザーがレビューし発見。L424で`call_goal_essence_analyst`の応答が、`feasibility_notes`文字列値の末尾を全角鉤括弧「」（「最低限のサービスレベル」を定義し直すことで、部分的な実現可能性はある。」）で終えていた。モデルが文中の強調に使った全角鉤括弧の閉じ記号「」を、JSON構文上の閉じ引用符(")の代わりだと錯覚したのか、実際の閉じ引用符(")そのものが欠落しており、`_safe_json_parse`がパースに失敗した（ログ上は`⚠️ [Goal Essence Analyst] JSON判定パース失敗を検知。層2リトライ 1/2...`）。BL-089で追加済みの層2リトライ（`_query_and_parse_with_retry`）が即座に検知しリトライ1回目で正常な応答を得て自己修復したため実害はなかったが、根本原因（プロンプト側でこの種の引用符の使い方を禁止していなかったこと）への予防策として対応した。

**対応（実装済み）:**

1. `call_goal_essence_analyst`のプロンプトに、JSON文字列値の**末尾**を全角鉤括弧「」『』で終えないよう明記する指示を追加。強調は文中に置くか、末尾は句点等の通常の文字にするよう指示。

**完了条件:**

- 新規`tests/test_bl090_json_string_fullwidth_quote_guard.py`（1件）: プロンプトに当該指示が含まれることの確認（`inspect.getsource`による静的確認）。
- `python -m py_compile cela_main.py`合格。

---

### BL-091: write_agreementの成否をDetectorへ明示せず、モデルの偽ツール呼び出し風テキストを鵜呑みにして誤って承認していた

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P0 |
| 関連 | [BL-033](issue_backlog.md#bl-033-expertがpython_repl未使用のまま検算完了と虚偽申告できるf-26監査フラグに強制力がない)（Expertの自己申告を鵜呑みにしない、という同型の先行対策）、[BL-079](issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる)（同じ`1913`レビューで同時対応） |

**内容:**

ユーザーが`log/2026-07-25/1913`の続きをレビューし「detectorがホワイトボードを更新できないまま、事故が起きました」と報告。フォレンジック調査の結果、以下の事故を確認した:

1. task_2_1（安全基準・運休判断基準）の修正で、Expertがwrite_agreementの`edits`（正規のツール呼び出し）を試みるが「old_textが現在のホワイトボード内容に見つかりませんでした」で失敗（[L44719](../../../log/2026-07-25/1913/log_no_prompt.md)）。
2. これが最終iteration（15）だったため、ツールが強制的に外され「テキスト最終応答を強制」された。
3. ツールを持たないはずのこの最終応答で、モデル（DeepSeek系）が独自のツール呼び出し風の疑似XML構文（`<｜DSML｜tool_calls>...<｜DSML｜invoke name="write_agreement">...`）をそのまま平文として出力した（[L44744](../../../log/2026-07-25/1913/log_no_prompt.md)）。これは実際には一切実行されていない（システム自身が`[DEBUG] expert_node: get_last_write_agreement_succeeded()=False`と正しく記録している）。
4. しかし`call_detector`のプロンプトにはこの成否フラグ（`state["expert_wrote_agreement"]`/`state["user_wrote_agreement"]`）が一切渡っておらず（`expert_last_python_calls`(BL-033)や`expert_last_reasoning`(F-2.1)は渡っているのに、このフラグだけが欠落していた）、Detectorはこの偽のツール呼び出しテキストの「主張内容」を鵜呑みにし、「物理的矛盾は解消される」「acceptance_criteriaを充足している」としてrisk=low, constraint_issue=noneで承認してしまった。Decision Extractorも「UPDATE - Proposed」としてDBに記録した。
5. 実害の確認: 実際のホワイトボードファイルは`phase_2_task_2_1_V2.md`のまま（V3は存在しない）。物理的に不可能な記述（「停車後約40.5秒で通信障害エリアを通過するため通信が自然復旧する」）と誤った数値（600秒）が今も残存しているにもかかわらず、DB上は「修正済みで承認」という偽の記録が残っていた。

BL-033で確立した「Expertの自己申告（python_repl未使用でも書けてしまう）を鵜呑みにせず、実行記録と突き合わせる」という設計思想と全く同じ穴が、write_agreementの成否についても存在していたことになる。`call_detector`は既に`get_latest_whiteboard`で現在タスクの最新ホワイトボード内容（＝唯一の真実の状態）を`whiteboard_block`として提示していたが、Detector自身がこの内容と会話ターンの「主張」を突き合わせて食い違いに気づくことを、プロンプトの明示的な指示なしにモデルの注意力だけに委ねていた。

**対応（実装済み）:**

1. `call_detector`に、今回評価対象のターンでwrite_agreementが実際に成功したか（`state["expert_wrote_agreement"]`/`state["user_wrote_agreement"]`、target_roleに応じて選択）を明示する`write_agreement_status_block`を追加。失敗している場合は「相手の発言内容がどれだけ説得力があっても実際には一切反映されていない。上記の最新ホワイトボードのみが唯一の真実であり、食い違う場合はconstraint_issue="major"とすること」と明記。
2. このブロックをドメイン妥当性レビュー・数値監査の両プロンプトに配線（ドメイン妥当性レビューが今回のような物理的整合性判断を誤った当事者だったため、両方に必須）。

**完了条件:**

- 新規`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`: `call_detector`のソースに当該ブロックが両プロンプトに埋め込まれていることの確認（`inspect.getsource`による静的確認）。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。
- 実LLM再ドライランでの効果確認（同種の偽ツール呼び出しテキストが再発した場合にDetectorが正しく食い違いを検出できるか）は次回待ち。

---

### BL-092: reviewerの差し戻し圧力に対し、task_plannerが数値の検算・訂正ではなく該当箇所の削除・抽象化で「解消」してしまう

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Fix A: reviewerの過剰な精度要求が逆に数値の"捏造"を誘発する問題、本BLはその逆方向）、[BL-091](issue_backlog.md#bl-091-write_agreementの成否をdetectorへ明示せずモデルの偽ツール呼び出し風テキストを鵜呑みにして誤って承認していた)（#2の再燃が同一の事故だったことを確認） |

**内容:**

別AIによる`log/2026-07-25/1913`の独立レビュー（12項目の指摘、ユーザー共有）を、さらに別チャットで各項目を実際のログ行まで追跡させた結果、以下が判明した。

- task_planner⇔task_plan_reviewerのループは3往復（major判定: L6336, L11739 → 承認: L14213）。
- レビュアーが指摘した数値矛盾（#1 task_2_2の「往復24km」と「片道約24km前提の計算」の混在、#3 task_3_4の「約1,200万円」根拠不明、#4 task_3_3の赤字誤差、#7「10人乗り」の根拠不明）は、いずれも**数値を検算して訂正した結果ではなく、該当するタスクの記述内容ごと削除するか、より抽象的な表現に差し替えることで矛盾自体が計画から消滅**していた（例: task_2_2は「往復24km」問題ごと「エッジケースのフェールセーフ概念設計」という別内容に差し替わった）。
- 一方で#8（ルート全長Lの「不明」vs「確定」の矛盾）は、Lを一般式・感度分析のパラメータとして一貫して扱う方向で**適切に解消**されており、全ての「差し替え」が問題というわけではない。#1/#6/#8は構造的な矛盾が根本から作り直された「良い意味での解消」である一方、#3/#4/#7/#10は「数値の誤りを検証せず、該当箇所を消して見えなくしただけ」という質的に異なる「解消」だったと考えられる。
- #2（task_5_2の「約2.1分」根拠不明、通信障害エリア通過時間の単位混同）は解消されず、後続のtask_2_1実行時に同種の単位混同が「停車後40.5秒で通過」という物理的に不可能な記述として再燃していた。これはBL-091で発見・修正済みの事故（Expertのwrite_agreement失敗→最終iterationで偽ツール呼び出し風テキストを出力→Detectorが鵜呑みにして誤承認）の一部として既に対応している。
- #12（重複再計算）はdraft1で49回→draft2で24回→draft3で8回とラウンドを追うごとに明確に減少しており、D-065（重複検証抑制指示の全ノードへの展開）の実効性が実データで裏付けられた。
- このドライランはtask_2_1/2_2の実行で停止しており、Phase 3以降（収支・保険料・オペレーター試算）は一度も実行されていない。したがって#3/#4/#7/#10、および#11（保険料タスクは追加されたが、法規制・住民説明タスクは「他タスクに暗黙的に含まれる」と判断され追加されず、代替交通手段タスクも独立化されなかった）は、実行段階での再検証機会自体が無かった。

BL-087 Fix Aは「reviewerが絶対値の確定を無理強いすると、task_plannerが存在しない数値を捏造する」という過剰な精度要求のリスクに対応したものだったが、本件はその逆方向：reviewerが数値の不整合を的確に指摘しても、task_plannerが数値を実際に検算・訂正する代わりに該当箇所自体を消してしまえば、表面上はレビューを通過できてしまうという構造的な抜け道である。少なくとも今回のケースでは実害が顕在化した数値は最終計画に残っておらず（Phase 3未実行のため実行時の検証機会も無かった）、"隠れた誤り"として実行フェーズへ混入したわけではないが、これは偶然（該当タスクが差し替えで丸ごと消えたため）であり、構造的な保証ではない。

**設計方針（決定・実装済み）:**

ユーザーから「ファイルに書き出してdiffツールを使った方が確実では」という提案があった。検討の結果、DBを編集の主軸から外してファイル中心に戻すこと自体（BL-074/034/040が既に解決した「ファイルパス・ファイル名を頼りにする脆さ」を再導入するリスク）は避けつつ、提案の核心である「機械的diffによる客観的検証」は、既にDBでバージョン管理されている`plan_drafts`（BL-082、task_planner再生成のたびに全タスクの版がauthor_role="task_planner"として積み増される）に対して`difflib`を使えばファイル化なしにそのまま実現できると判断した。

**対応（実装済み）:**

1. 新規ツール`DIFF_PLAN_DRAFT_VERSIONS_TOOL`/ハンドラ`_diff_plan_draft_versions_handler`を追加し`TOOL_DISPATCH`に登録。指定task_idについて、`plan_drafts`から`author_role='task_planner'`の版を版番号順に取得し、直近2件の間の統一diff（`difflib.unified_diff`）を返す（書き込みは行わない読み取り専用）。
2. `call_task_plan_reviewer`の`tools=[...]`にこのツールを追加し、プロンプトに「以前指摘したtask_idについては記憶・印象で判断せず、`diff_plan_draft_versions`で前回との機械的な差分を確認し、指摘した論点が『数値が訂正された』のか『関連する記述ごと消えた』のかを区別してから判断すること。後者の場合はそれ自体を新たな指摘としてcommentに明記すること」という指示を追加した。

**完了条件:**

- 新規`tests/test_bl092_plan_draft_diff_verification.py`（8件）: 削除パターン（数値記述が丸ごと消える）と訂正パターン（値だけ変わる）の両方でdiffが正しく示されること、版が1件しかない場合のエラー、未知のtask_id、空文字task_id、差分なしのケース、`TOOL_DISPATCH`登録確認、`call_task_plan_reviewer`への配線確認。
- 既存`tests/test_bl087_stage2_task_plan_reviewer_node.py`のツール一覧完全一致アサーションを、ツールが増えても壊れないよう部分一致（`in`）に更新。
- `python -m py_compile cela_main.py`合格、オフラインスモークテスト全件Pass。
- 実LLM再ドライランでの効果確認（reviewerが実際にこのツールを使い、「削除による解消」を新たな指摘として検出できるか）は次回待ち。

---

### BL-093: ノード内スクラッチパッド `think`ツール（理由づけの退避＋ツールループ内の可変todo/issue/notesメモ）

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P2 |
| 関連 | [BL-092](issue_backlog.md#bl-092-reviewerの差し戻し圧力に対しtask_plannerが数値の検算訂正ではなく該当箇所の削除抽象化で解消してしまう)（同時期のスクラッチパッド議論の発端だが別テーマ）、[decision_log.md D-070](../decision_log.md#d-070-ノード内スクラッチパッド機構はdecision_list要約圧縮を廃しglobal_working_notes全文上書き型のみに縮小する)（誤った結論、D-072で訂正）、[decision_log.md D-071](../decision_log.md#d-071-max_tool_iterを15から20へ引き上げthinkツールの単独呼び出しを許容する)（MAX_TOOL_ITER引き上げ）、[decision_log.md D-072](../decision_log.md#d-072-thinkツールの最終仕様を確定するthink専用ツールに理由づけの構造化フィールドtodoとissuesのopenclosed必須notesの追記専用化を持たせる)（最終設計・実装）、[decision_log.md D-074](../decision_log.md#d-074-thinksummaryを機械的に必須化し自動reasoningダイジェストへ切り替える)（think呼び出しのモデル任意性を廃し機械的強制へ） |

**内容:**

別チャットで「各ノードのquery_AI呼び出しに思考フレームワーク＋スクラッチパッド（ノート機能）を持たせる」構想が持ち込まれ、次の経緯で議論・検証・訂正した。

1. **発端**: `_query_AI_live`のツールループ（[cela_main.py:1958-1969](../../../cela_main.py#L1958-L1969)、実装後は行番号が前後する）は、モデルの`reasoning`（chain-of-thought生文章）を`_StreamMessage`で`None`固定にして捨てており（`content`/`tool_calls`のみが`loop_messages`へ再送される）、次iterationでモデルは「前回どのツールを何の引数で呼んだか」という骨組みだけから理由を再構築している、という技術的事実を確認した。
2. 複数の実装案（content内へのメモ書き、think専用ツール、構造化出力＋要約圧縮）を比較検討する中で、一時「`loop_messages`は全履歴を毎iteration再送するため、reasoning消失は実害がない」と誤って結論しかけた。これは「tool_calls/tool結果という行動記録が保持される」事実と「reasoningという理由づけの生文章が保持される」事実を混同した誤りであり、ユーザー指摘で訂正した（reasoning自体は`_StreamMessage.reasoning = None`固定のままどのiterationにも再送されず、この問題は実在する）。
3. 一方で「直前1iterの生ログ＋要約リスト＋decision_list」という重い発展案は不要と判断した。`loop_messages`はそもそもtruncateされず全履歴を毎iteration再送する実装であり（MAX_TOOL_ITER＝短い上限もあるため）、いったんtool_call引数として書かれた情報は何もしなくても既に全iteration分保持される。要約/windowing機構は「短いループには過剰設計」という、この発展案自身がパターン4（構造化出力＋要約圧縮）を退けた際の論理と矛盾しており、解決すべき問題が実質存在しない。`decision_list`も`write_agreement`が既に`agreements`テーブルへ構造化永続化している内容と重複する。
4. 最終的にユーザーから、reasoningは構造化フィールド（action/decided/why/rejected/rejected_why）として残すべき（自由文1本だと長いiterで読み返す際に取りこぼしが生じるため）、todo/issuesはopen/close必須のリスト、notesは上書きされない追記専用リストに分離すべき、iter番号はモデルの自己申告ではなく機械的に付与すべき、thinkは他ツールとバンドル必須にせず単独呼び出しも許容すべき（ReAct本来の「軽量な思考単位を繰り返す」設計を優先し、必要ならMAX_TOOL_ITERを引き上げる）、という具体的な仕様指定を受け、これに基づき設計・実装した。

**設計・実装:**

1. 新規ツール`THINK_TOOL`/ハンドラ`_think_handler`（`cela_main.py`）。引数: `action`（必須、このiterで何を考え・しようとしているか）、`decided`/`why`（決定があれば）、`rejected`/`rejected_why`（却下案があれば）、`todo`/`issues`（`{item, status: open/closed}`のリスト、変更がある時だけ含めればよく省略時は前回状態を保持）、`notes`（追記専用、送るたびに新規1件が既存リストの末尾に追加され既存分は消えない）。
2. ハンドラは`action`等を`_THINK_REASONING_LOG`に追記し、tool結果として**蓄積済み全reasoning履歴＋現在のtodo/issues/notes**を即座に返す。これにより、消える`reasoning`チャネルではなく、`loop_messages`に確実に残る`tool_calls`/tool結果チャネルへ理由づけを退避させる（ツールループ本体の改修は不要）。
3. iter番号はモデルの自己申告に頼らず、新設グローバル`_CURRENT_TOOL_LOOP_ITERATION`（`_query_AI_live`のループ先頭で`iteration`変数から機械的に設定、この1行のみが唯一のループ本体への追加）から取得し、`_THINK_REASONING_LOG`の各エントリと`python_calls_log`（python_repl呼び出しの生ログ）の両方に刻む。
4. `_reset_think_scratchpad()`で全状態をリセット（DB・stateいずれにも永続化しない、1ノード呼び出し限定のスクラッチパッド）。各関数呼び出し開始時に`_reset_think_scratchpad()`を呼ぶ。
5. プロンプト指示: 初回でtodoを初期リストアップすること、以降はtodoに従って作業し途中の気づきは自由に追記・更新できること、他のツール呼び出しと同一応答内でまとめて呼んでも単独で呼んでもよいこと。
6. `MAX_TOOL_ITER`を15→20へ引き上げ（D-071、AGENTS.md §7準拠でユーザー承認済み）。単独呼び出しを許容する方針により、既にiter=15（旧上限）に達した実績のある`task_plan_reviewer`等で予算超過が現実的になったため。

**対象ノードの全ノードへの拡張（D-072後の追加指示）:**

当初はDetector数値監査パス・`call_task_planner`・`call_task_plan_reviewer`の3ノード限定（複数回のpython_repl呼び出しを跨ぐノードのみという頻度・コストベースの絞り込み）だったが、ユーザーから「対象ノードは全ノードへ。ツール呼び出し回数というより、思考のやり方の環境の整備なので」という指示を受けた。これは頻度・コストの多寡で対象を絞る発想自体を退け、「thinkは全ノードに共通の思考基盤である」という立場を明確にするもの。これに基づき、以下へ拡張した。

- 既にtools付与済みだった残り6箇所（`call_expert`、`generate_user_utterance`の2呼び出し箇所、`call_goal_essence_analyst`、`call_reviewer`、`call_integrator`、`call_resource_arbiter`）に`THINK_TOOL`を追加。
- 従来`tools=None`（単一応答・ツールループを一切通らない構造的に異なるコードパス）だった4関数（`call_orchestrator`、`call_decision_extractor`、`call_reflection`、`call_facilitator`）を`tools=[THINK_TOOL]`へ変更し、初めてツールループパスに乗せた。
- Detectorのドメイン妥当性レビューパス（従来`tools=None`）も同様に`tools=[THINK_TOOL]`へ変更（数値監査パスは既にBL-093初版で対応済み）。

合計でtools付与済みの全13呼び出し箇所（重複含む関数呼び出し地点ベース）に`think`ツールが行き渡った。

**自動reasoning引き継ぎの機械的強制（D-074、実ドライラン`log/2026-07-26/1535`レビュー後の追加指示）:**

実ドライランレビューで、Expert等がpython_replのみを呼びthinkを呼ばないiterationが多数あることが判明した。ユーザーから「thinkを呼ぶかどうかがモデル任せでは、reasoning引き継ぎ自体が機能しない。メモ帳（think）はあくまでメモ帳で、reasoningの引き継ぎは自動でなければ文脈が通らない」との指摘を受け、以下へ設計変更した。

1. `THINK_TOOL`に`summary`フィールドを新設（1〜3文の要約、`required`に追加）。
2. `_query_AI_live`に機械的強制ロジックを追加: あるiterationにツール呼び出しが1件でも含まれる場合、その中に`think`呼び出しがあり、かつ`summary`が非空であることを必須とする。満たさない場合、そのiterationの**ツール呼び出しを一切実行せず**（python_repl等の実処理を走らせない）、`[SYSTEM ENFORCEMENT]`エラーをtool結果として差し戻し、モデルに再試行を強制する（BL-009の「壊れたJSON引数は自己修復させる」と同型の設計）。ユーザーから「thinkのみの単独呼び出しも対象に含める」との明示指示があり、他ツールを伴わないthink単独呼び出しでもsummary必須とした（think自身もいずれ`_AUTO_REASONING_VERBATIM_ITERS`の窓外へ古くなるため、summaryが無いと持ち越す情報が欠損するという理由）。
3. 当初「古いiterationは機械的に文字数で切り詰める（例: 先頭150字）」という代替案を検討したが、reasoning本文は実測で数百〜1,500字超に及び、単純な文字数切り詰めでは結論部分が失われ「ほとんど意味を成さない」とユーザーに却下された。理想は専用の軽量要約LLMだが、追加のLLM呼び出しを避けるため、代わりに機械的強制によって**モデル自身に意味のある要約を書かせる**方式（プロンプト制約で乗り切る）を採用した。
4. 自動ダイジェスト: `_query_AI_live`内のローカル変数（グローバル化不要、1回の呼び出し内で完結）で各iterationの生reasoningを蓄積し、直近`_AUTO_REASONING_VERBATIM_ITERS`（=2）件は生reasoningそのまま、それより古い分は`_THINK_REASONING_LOG`（`think`ハンドラが機械的なiter番号付きで既に記録済み）から該当iterの`summary`を引いてダイジェスト1メッセージに集約する。`light_system_prompt`（BL-025）と同型の「system直後の固定位置（index 1）への差し替え」パターンで`loop_messages`へ都度反映し、無限に新規追加はしない。
5. 強制ロジックの副作用としてリトライがMAX_TOOL_ITER予算を消費する点はユーザーも認識済み。恒久対策（1タスクあたりのiteration予算が逼迫する場合はtask_plannerの分解粒度を上げる、または1タスクを複数回に分けて思考させるノードループの再設計）は将来の課題としてここでは対応しない。

**実ドライラン`log/2026-07-26/1705`レビューによる追記修正1:** Goal Essence Analystが差し戻しを2回連続で受ける事象を確認。原因は「thinkを一度呼べば以降のツール呼び出しが恒久的に許可される」という誤解で、iter=1でthink単独呼び出し成功→iter=2でpython_replのみ呼び差し戻し→iter=3でthink単独呼び出しを再度呼ぶ（python_replを伴わない）→iter=4でpython_replのみ呼び再度差し戻し→iter=5でようやくthink+python_replを同一応答内でまとめて呼び成功、という経緯だった（9iteration中2回、約22%を空費）。差し戻しエラーメッセージが「今回のturnでリトライしてください」としか言っておらず、「差し戻されたツール呼び出しも同一応答に含めて再送すること」を明示していなかったことが原因と判断。`THINK_TOOL`の説明文と差し戻しエラーメッセージの両方を、「このチェックは毎回の応答ごとに独立して適用され、過去にthinkを呼んだことは将来の応答に対して一切の"恒久的な許可"にならない」「リトライ時は差し戻されたツール呼び出しとthinkを同一応答にまとめて再送すること」を明示する文言に修正した。

**続く`log/2026-07-26/1713`レビューによる追記修正2:** 上記の修正後も同種の差し戻し（1回）が再発。ユーザーが「ツール説明はthinkツールだけでなく他のツールの説明にもthinkを同時に呼べと明示しないとならない」と指摘した通り、モデルは`python_repl`等を呼ぶ判断時に、その**呼び出したいツール自身の説明文**を主に参照しており、`THINK_TOOL`側にのみ書かれた制約は必ずしも参照されないことが判明。対策として、`PYTHON_REPL_TOOL`/`READ_VERIFIED_FACT_TOOL`/`READ_DELIVERABLE_FILE_TOOL`/`VERIFY_WHITEBOARD_EXCERPT_TOOL`/`DIFF_PLAN_DRAFT_VERSIONS_TOOL`/`WRITE_AGREEMENT_TOOL`/`FREEZE_AGREEMENT_TOOL`/`ESCALATE_PREMISE_CONCERN_TOOL`/`RESOLVE_PREMISE_CONCERN_TOOL`/`REVISE_GOAL_TOOL`の**全10ツールの説明文末尾**にも同一の短いリマインダー（「[BL-093] You must also call `think` with a non-empty `summary` in this SAME response...」）を追記し、どのツールを呼ぶ判断をしていても制約が視界に入るようにした。

**同じ`log/2026-07-26/1713`の再検証による追記修正3:** ツール説明文の修正後も再度失敗を確認。ユーザーが「先ほど私が書いたように各ノードのプロンプトに各ツールはthinkとともに使用せよと明示してください」と指摘した通り、ツールスキーマの`description`だけでは不十分で、各ノードの**プロンプト本文**にも、そのノードが実際に使えるツール名を名指しした指示が必要と判明。対策として、tools付与済みの全ノード（`call_task_planner`/`call_expert`/`call_detector`数値監査パス/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`/`call_goal_essence_analyst`/`call_task_plan_reviewer`）のプロンプト本文中、既存のBL-093 think指示の直後に、「あなたが使えるツールは○○・○○・thinkです。think以外のいずれかを呼ぶときは、必ずその同じ応答の中にthink（summary必須）も一緒に含めてください」という、そのノード固有のツール名を列挙した一文を追記した（think以外にツールを持たない`call_orchestrator`/`call_detector`ドメイン妥当性パス/`call_decision_extractor`/`call_reflection`/`call_facilitator`の5関数は、think単独呼び出し以外の選択肢がなくこの種の混同が起こり得ないため対象外）。

**`log/2026-07-27/1911`のレビューによる追記修正4:** 追記修正1〜3の対策後も、think未添付による差し戻しが1本のドライランログ内で12回発生していることをユーザーと確認。文面が「含めてください」「差し戻されます」という丁寧な依頼調のままであり、モデルが他ツール自身の説明文・プロンプト本文を読む際に「絶対厳守」と認識しにくいのではないかとユーザーが指摘。ユーザー提案「thinkツールと同時に呼ぶことを厳守しろ！くらいの強い言葉で書く」を受け、think以外の全ツールスキーマ説明文（14箇所）を"[BL-093] MANDATORY: you MUST also call `think`..."という命令形＋大文字強調に、tools付与済み各ノードのプロンプト本文（10箇所）を「think以外のいずれかを呼ぶ場合は、必ず同じ応答内でthink（summary必須）を同時に呼ぶことを厳守しろ！」という語調に強化した（指示内容自体は変更せず、強制力の伝わり方のみを強化）。関連クラスタ261件Pass、`python -m py_compile`合格。実LLM再ドライランでの差し戻し頻度の実際の減少確認は次回待ち。

**完了条件:**

- 新規`tests/test_bl093_think_tool_scratchpad.py`（42件）: ツール登録確認、reasoningへの機械的iter番号付与、複数回呼び出しでの累積、todo/issuesのopen/closed必須・変更時のみ更新（sticky）、notesの追記専用（上書きされない）、リセット、`MAX_TOOL_ITER=20`、ループ本体への`_CURRENT_TOOL_LOOP_ITERATION`/`"iteration"`付与、全10関数＋Detector両パスへの配線・プロンプト文言の存在確認（パラメータ化テスト）、旧`tools=None`4関数が`tools=[THINK_TOOL]`へ切り替わったことの確認、think以外の全10ツールの説明文にリマインダーが含まれることの確認（パラメータ化テスト）、tools付与済み9関数のプロンプト本文がそれぞれ自身の利用可能ツール名を名指ししていることの確認（パラメータ化テスト）。
- 新規`tests/test_bl093_d074_auto_reasoning_enforcement.py`（6件）: OpenAI streamingレスポンスを模したフェイククライアントで`_query_AI_live`を直接検証。think無しのツール呼び出しが実行されず差し戻されること、think+summary付きは正常実行されること、think単独でもsummary必須で拒否されること、直近2iter分は生reasoning・それより古い分はsummaryでダイジェストが構築されることを、実際に`create()`へ渡されたmessages配列を検査して確認。
- 既存`tests/test_bl087_stage2_task_plan_reviewer_node.py`（`call_task_planner`）・`tests/test_bl087_stage3_4_goal_essence.py`（`call_goal_essence_analyst`）のツール一覧完全一致アサーションを、ツールが増えても壊れないよう部分一致（`in`）に更新（BL-092で`call_task_plan_reviewer`側に行った修正と同型）。
- `python -m py_compile cela_main.py`合格、関連クラスタ91件Pass、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（機械的強制が実際に自己修復ループとして機能するか、要約の質、MAX_TOOL_ITER=20が実際に十分か）は次回待ち。

---

### BL-094: `read_verified_fact`/`read_deliverable_file`等「参照系」ツールのノードプロンプトへのオリエンテーション追記

**経緯:** BL-093実装後の実ドライラン`log/2026-07-26/1749`について、ユーザーから「同じことの無駄な再確認や、理由や数字の出所などがわからず数値の捏造やハルシネーションなどはあるか」というレビュー依頼を受け、別セッションのgeneral-purpose Agentに全文（当時19,195行）の精査を委託。本セッション側でも主要な指摘を実ログ・`cela_main.py`と突き合わせて裏取りした結果、以下が事実として確認された。

1. **無駄な再確認**: Task Planner再計画ターンが1ターン内で山間部片道時間を3通り計算し（36分→20.7分→矛盾に気づくが「ここは深入りせず」と放棄→結局36分採用）、末尾のExpertが3台の輸送能力を9通り以上再計算し続け、Detectorが独立検算で既に確定させた「150人/3h」を一度も参照しないまま新しい前提を作り直していた。
2. **出所不明・矛盾する数値**: Goal Essence Analyst自身が「12kmを総ルート長」と仮定して逆算した600m/1.8kmという数値が、後続のExpertのDeliverableで「出典: 実現可能性メモ」という**架空の一次資料**であるかのように扱われていた（`cela_main.py:2694`で確認した通り、「実現可能性メモ」は単に`essence['feasibility_notes']`＝Goal Essence Analyst自身の推測文をラベル付けしているだけで、独立した資料ではない）。また山間部片道時間がGoal Essence Analyst側で24分、Task Planner側で36分と食い違ったまま、どちらのノードもこの矛盾に気づかず、両方が別々の文脈で「確定値」として使われ続けていた。冬季速度70%低下（14km/h）や車両定員20人も、コード内コメントでは「仮定」と明記されているのに、Detectorが`minor`指摘した後もDeliverable自体は訂正されずに承認・伝播していた。

**根本原因（ユーザー診断）:** `read_verified_fact`/`read_deliverable_file`は`tools=[...]`に配線され、ツールスキーマの`description`も存在するが、**どのノードのプロンプト本文にも「これらのツールで過去の決定・確定値・理由を参照できる」という説明も、「いつ使うべきか」という指示も書かれていなかった**。BL-093で判明した「ツール説明文だけでは不十分で、各ノードのプロンプト本文に名指しした指示が要る」（追記修正3）という教訓と同型の問題であり、ツールを`tools=[...]`に追加するだけでは、モデルはそれを実際には使わない。

**対応内容:** `read_verified_fact`/`read_deliverable_file`を持つ全6関数（`call_expert`/`call_detector`数値監査パス/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`）のプロンプト本文に、`[BL-094: ...]`ブロックとして以下を追記した：
1. 両ツールの目的説明（`read_verified_fact`＝全フェーズ・全タスク横断で変数名/キーワードから確定値・理由・引用元・confidenceを検索、`read_deliverable_file`＝過去タスクの成果物全文を前提込みで参照）。
2. 「最低限、iter=1で一度は、関連しそうな変数名・キーワードでread_verified_factを呼び、他タスクで既に確定・仮定された値が無いか確認してから作業を始めること」という思考フレームワーク上の指示。
3. 「思考の途中で『これは他タスクで既に扱われていたかもしれない』という気づきがあれば、その都度参照し、独自の仮定で上書きしないこと」という積極的参照の指示。

Detectorには特に「Agentの数値がゴール文の直接記載か、AI自身の推測の孫引きかを見分けるために使う」という、監査役固有の観点を明記した（`出所`という語で規定テスト化）。他の「参照系」ツール（`verify_whiteboard_excerpt`＝BL-079で既に「確定前に必ず検証」という同種の指示が存在、`diff_plan_draft_versions`＝BL-092で既に「以前指摘したtask_idについて確認」という同種の指示が存在）は、既存のプロンプト内オリエンテーションで十分と判断し、今回の追記対象外とした。`python_repl`/`write_agreement`/`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`/`freeze_agreement`も同様に既存の指示で足りると判断した。

`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`（`read_verified_fact`/`read_deliverable_file`を持たない）は当初対象外とし、新規配線するかは別途の判断を要する未決事項として残していた。

**追記（D-076、ユーザー指示によるツール配線の拡張）:** ユーザーから「call_task_planner／call_goal_essence_analyst／call_task_plan_reviewerはそもそもread_verified_fact/read_deliverable_file、監査や差戻し時呼び出せるように配線してください」と明示指示があり、上記の未決事項を解消。3関数の`tools=[...]`に`READ_VERIFIED_FACT_TOOL`/`READ_DELIVERABLE_FILE_TOOL`を追加配線し、同型のオリエンテーション（目的説明＋iter=1同期指示）をプロンプト本文に追記した。特に`call_task_planner`と`call_task_plan_reviewer`は「Task Plan Reviewerが差し戻し→task_plannerが再分解」というループを構成する関数対であり、実ドライラン`1749`で観測された「Goal Essence Analystが仮定した値にTask Plannerが気づかず、別の矛盾する値を再度仮定する」循環参照バグの再発防止を狙った配線である。`call_goal_essence_analyst`は通常プロジェクト最初期に1回だけ呼ばれ、その時点では確定値がまだ存在しないことが多いため実効性は限定的だが、一貫性と将来のグラフ設計変更への備えとして同様に配線した。ハンドラ実装（`_read_verified_fact_handler`/`_read_deliverable_file_handler`）は`_CURRENT_RUN_ID`のみに依存し呼び出し元ロールへの制限がないため、追加配線に伴う実装変更は`tools=[...]`とプロンプト文言のみで完結した。

**完了条件:**

- 新規`tests/test_bl094_read_tool_orientation.py`（32件）: 対象9関数（当初6関数＋追加配線3関数）それぞれが`BL-094`・`read_verified_fact`・`read_deliverable_file`を含むこと、`iter=1で`という同期指示を含むこと（パラメータ化テスト）、Detectorが「出所」という観点を明記していること、各関数固有の見出し文言が存在すること、追加配線3関数が実際に`READ_VERIFIED_FACT_TOOL`/`READ_DELIVERABLE_FILE_TOOL`を`tools=[...]`に渡していること（パラメータ化テスト）。
- 既存`tests/test_bl093_think_tool_scratchpad.py`の`_NODE_TOOL_NAME_REMINDERS`（ツール名指しの回帰テスト）を、`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`の新しいツール一覧に合わせて更新。
- `python -m py_compile cela_main.py`合格、関連クラスタ228件Pass、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（iter=1でのread_verified_fact呼び出しが実際に増えるか、数値の出所追跡・循環参照バグの再発防止が実際に機能するか）は次回待ち。

---

### BL-095: `call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`への`WRITE_AGREEMENT_TOOL`配線（読み書き非対称の解消）

**経緯:** BL-094完了後、ユーザーから「このシステムの中で情報の抽出、保存、伝搬の観点でまだ足りないもの、あるいは未配線等ははるか？」と問われ棚卸しを実施。BL-094でこの3関数に`read_verified_fact`/`read_deliverable_file`（read専用）を配線したことで、「他ノードの確定値・成果物は読めるが、自分自身の判断根拠（なぜこのフェーズ・タスク構成にしたか、なぜ`risk=medium`と判定し`major`にしなかったか等）を誰にも参照可能な形で書き残せない」という読み書きの非対称が生じていることが判明した。ユーザーは「これは問題ですね、タスクプランナーの意図や理由は後続タスクで見れるべきです」と明示指摘し、BLとして起票・修正することとなった。

**現状整理:**
- `write_agreement`は現在`call_expert`/`call_detector`数値監査パス/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`の6関数のみに配線されている。
- `WRITE_AGREEMENT_TOOL`のスキーマ上、ロール別に`status`が制限される設計が既にある（`description`に明記：Expertは`Proposed`のみ、User AIは全ステータス、Detector/Reviewer/Arbiter/Integratorは`Rejected`のみ）。`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`はこの制限リストに含まれておらず、新規に役割を定義する必要がある。
- Task Planner/Task Plan Reviewer/Goal Essence Analystが書きたい内容は「Decision/Deliverableの数値」ではなく「計画・レビューの構造的判断そのもの」（フェーズ分解の方針、depends_on設計の意図、risk判定の理由等）であり、既存の`entry_type`（Decision/Directive/Deliverable）のうちどれに当てはめるか、あるいは新設が必要かの設計判断が要る。

**設計・実装内容（`done`）:**
1. `_check_write_permission`の`ALLOWED_STATUS_BY_ROLE`に3ロールを追加: `task_planner`＝`{"Proposed"}`、`goal_essence_analyst`＝`{"Proposed"}`（いずれもExpertと同型。自らの計画・本質分析はあくまで提案であり、後続のtask_plan_reviewer/実行に覆されうるため`Approved`等は名乗らせない）、`task_plan_reviewer`＝`{"Rejected"}`（Detector/Reviewer等と同じ監査役）。`WRITE_AGREEMENT_TOOL`の`description`にも3ロールの制限を追記。
2. `call_task_planner`: 最終JSON出力前に`write_agreement`（`entry_type="Decision"`, `status="Proposed"`, `action_type="CREATE"`, `topic="task_planner_phase_design"`固定文字列）で、フェーズ構成・タスク分割の判断根拠（フェーズ数、focus_scope/expected_time_axisの選定理由、依存関係・粒度の決定）を記録するようプロンプトに追記。`task_id`/`phase_id`は特定の1タスクに紐づかないため省略可とした。
3. `call_goal_essence_analyst`: 同様の`write_agreement`（`topic="goal_essence_analysis"`）呼び出しを、`true_essence`/`feasibility_notes`の2フィールドに収まらない検討過程（却下した本質の言語化案等）がある場合のみの**任意**指示とした（`true_essence`/`feasibility_notes`自体は既に`goal_essence`テーブルに保存され全ノードへ常時注入されるため必須にしなかった）。
4. `call_task_plan_reviewer`: `read_deliverable_file`でtask_plannerの`task_planner_phase_design`記録を確認した際、その根拠自体に誤りがあり`constraint_issue="major"`判定の理由になっている場合、`write_agreement`（`action_type="SUPERSEDE"`, `status="Rejected"`, `target_topic="task_planner_phase_design"`）でSUPERSEDEするよう指示（既存BL-062と同型パターン）。
5. 3関数それぞれの呼び出し直前に`global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID`で該当ロール名を設定（`_CURRENT_TASK_ID`は特定タスクに紐づかないため空文字）。
6. 既存の`per_task_comments`（BL-087 Stage2、`plan_drafts`への注釈）とは役割分担: `plan_drafts`は「フェーズ・タスク表への直接注釈」、`write_agreement`は「後続タスクから`read_verified_fact`/`read_deliverable_file`で検索可能な構造化決定」という別レイヤーとして併存させた。

**完了条件:**
- 新規`tests/test_bl095_task_planner_write_agreement.py`（25件）: `_check_write_permission`の新規3ロール×全status組み合わせの直接検証（DB接続不要の純粋関数テスト）、3関数が`WRITE_AGREEMENT_TOOL`を`tools=[...]`に渡していること、呼び出し前に正しいロール名を`_CURRENT_CALLER_ROLE`へ設定していること、各プロンプト本文にBL-095のオリエンテーション（`entry_type="Decision"`、固定topic文字列、SUPERSEDE指示等）が存在すること、ツールスキーマの`description`に新規3ロールが明記されていることを確認。
- 既存`tests/test_bl093_think_tool_scratchpad.py`の`_NODE_TOOL_NAME_REMINDERS`を3関数分`write_agreement`込みで更新。
- `python -m py_compile cela_main.py`合格、関連クラスタ256件Pass、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（task_plannerが実際に`task_planner_phase_design`を記録するか、後続のExpert/User AIが`read_deliverable_file`でそれを参照するか）は次回待ち。

---

### BL-096: 監査系ノードの軽微な指摘（observations/minor）を追跡するissue管理DBの新設

**経緯:** BL-095と同じ棚卸しで発見。ユーザーから「Detectorのobservationsはissue管理DBの配線を作る時にそちらに入れて管理しましょう。小さな気づきこそが結構大事」「severity（minor/major）の追跡漏れもissue_BLリストに入れてフォローさせましょう」との指示があり、この2点を統合した1つのBLとして起票する方針とした。

**現状整理（2つの症状は同根）:**
1. Detectorの`observations`（BL-051、`constraint_issue`の判定には至らないが気になった点の自由記述）は`agreements`にも`verified_facts`にも保存されず、直後数ターンの`chat_history`ウィンドウから外れると実質的に消滅する。
2. `constraint_issue="major"`はDetector/Reviewer/Arbiter/Integratorに`write_agreement`（`status="Rejected"`によるSUPERSEDE強制）を促す設計があるが、`"minor"`は判定結果を返すだけで、後続タスクで実は重大だったと判明しても再浮上・再監査される保証がない。

いずれも「監査系ノードが見つけた軽微な懸念を、忘れずに後で拾い上げて追跡する」ための正式な永続層が存在しないことが根本原因であり、ユーザーは両者を1つの「issue管理DB」に統合する方針を示した。

**基本設計v3確定・実装着手。** Plan modeでv1設計後、ユーザー指摘＋別AIレビューを経てv2・v3へ改訂（詳細は[BL096_basic_design.md](BL-096/BL096_basic_design.md)、改訂理由は[D-079](../decision_log.md#d-079-bl-096設計をv2に改訂read経由の再発カウント追加severitymajorstatusescalated不変条件topictask_idキー変更)・[D-080](../decision_log.md#d-080-bl-096設計をv3に改訂重複検知キーをtopic単独に差し戻しreflectionfacilitatorへの機械的接続とエスカレーション解除通知を追加)）：
1. スキーマ: 新規`issue_log`テーブル（`topic`/`raised_by`/`severity`/`status`/`occurrence_count`/`last_seen_task_id`等）。重複検知キーは**`topic`単独**（v2で一度`(topic,task_id)`に変更したが、タスク横断の再発検知というBL-096の目的自体と矛盾するため`topic`単独に差し戻し、v3で確定）。
2. 再浮上トリガー: **累積回数しきい値**方式を、CREATE再呼び出し経由に加え、`read_issues`で`topic_keyword`と`task_id`が両方明示され`last_seen_task_id`と異なる場合のみカウントするREAD経由トリガーで二重化（誤爆防止のため4条件に厳格化）。`occurrence_count>=2`で機械的に`severity="major"`へ昇格し、**`severity="major"`の行は常に`status="escalated"`を伴う不変条件**。
3. 既存の`agreements`/`verified_facts`との役割分担: 本DBは「まだ解決していない懸念の追跡」に特化。
4. ノード配線: MVPは**Detector・User AI（`generate_user_utterance`）の2ノードに限定**（`CREATE`は両方、`RESOLVE`はUser AIのみ）。Detectorが`write_issue`を呼ばなかった場合の機械的バックアップ書き込み（`raised_by="detector_auto"`）も追加。
5. **reflectionへの機械的接続**: `issue_log`に`status='escalated'`行が1件でもあれば、`reflection_node`が`discussion_status`をモデル判定に関わらず機械的に`"stagnant"`へ上書き（既存の`route_after_reflection`ルーティングをそのまま利用）。既存のreflection/facilitator機構が、BL-051が当初求めていた「issueリストをフェーズ終了条件とする」の役目を果たせることが判明し、新規の完了ゲートは作らずここに接続する方針とした。
6. **facilitatorへの構造化データ注入**: facilitatorにもescalated issueの構造化情報（topic/description/occurrence_count）をPython側の直接DB問い合わせで渡し、具体的な懸念を名指しして解消を促す専用指示ブロックを追加。
7. **エスカレーション解除の復帰通知**: `current_task_id`等の作業状態自体はreflection/facilitatorに破壊されないが、facilitatorが開く「広い問い直しモード」から自力で抜け出す合図がないというユーザー指摘を受け、escalated件数が0件に戻った瞬間を検知し、次のExpert/User AI呼び出し時に一度だけ「エスカレーション解消・通常のタスク遂行に戻ってよい」という復帰通知を注入する機構を追加。
8. 読み取りツールは`read_issues`（「openのものしか見えない」という誤解を避けるため改名）。デフォルトで解決済み（resolution_note込み）も検索結果に含め、無条件の全件取得は明示的な`list_all`スイッチに分離。

**完了条件:**
- 新規`tests/test_bl096_issue_log.py`（42件）: `_check_issue_permission`のロール×アクション直接検証、`_write_issue_impl`のCREATE（新規・再発・major即時escalated・トランケーション・権限拒否）、RESOLVE（成功・権限拒否・存在しないtopic・escalation_cleared判定）、`get_issues_from_db`/`_read_issues_handler`（resolved込みデフォルト・description LIKE検索・list_all・フィルタ必須エラー）、READ経由の再発カウント4条件（topic_keyword+task_id必須・別task_idでのみカウント・同一task_idや`task_id`単独やresolved行は対象外）、`_get_escalated_issues`、`TOOL_DISPATCH`配線、`call_detector`/`generate_user_utterance`のtools=[...]・プロンプトオリエンテーション、`detector_node`の自動バックアップ、`reflection_node`/`call_reflection`/`facilitator_node`/`call_facilitator`の機械的接続、`_build_escalation_resume_notice`、`LineageState`フィールドを検証。
- `python -m py_compile cela_main.py`合格、`pytest tests/ -q -k "bl093 or bl094 or bl095 or bl096 or bl087"`198件Pass、`check_docs_consistency.py`合格。
- 実LLM再ドライランでの効果確認（Detector/User AIが実際にwrite_issue/read_issuesを使うか、エスカレーション→reflection→facilitatorの機械的接続が実際に発火するか、復帰通知が機能するか）は次回待ち。

---

### BL-097: ログの確定値/推定値/運用ルール区分表示・think空欄削減・スコープ逸脱防止の徹底

**経緯:** ユーザーが別AI（本セッションとは独立したAgent）に`log/2026-07-26`のドライランログと`cela_main.py`本体を独立レビューさせた結果の指摘を受けて起票。BL-093/094/095で構築した「確定値と推定値の混同防止」「read_verified_fact/read_deliverable_fileによる同期」の路線を、ログの可読性・監査性の観点でさらに一段掘り下げる内容。

**指摘内容（別AIレビューより）:**
1. **数値の出所が埋もれる:** ログ上の数値自体は整合しているが、「どこまでがtask由来の確定値で、どこからが今回の設計仮定か」が読み手（人間レビュアー）から見て埋もれやすい。冒頭に「確定値」「補助仮定」「今回追加した運用ルール」を分けて提示するだけで可読性が上がる。
2. **`think`の構造化フィールドの空欄:** `decided`/`why`/`rejected`/`rejected_why`が空のまま進む場面があり、後から見て「何を捨てて何を採ったか」が追いにくい。ストレステスト（品質監査）用途ではこの欄を埋めさせたほうが、後でプロンプトを改善しやすい。

**改善提案（次に直すべきプロンプト設計）:**
1. **数値の出所ラベルの強制:** 「確定値」「推定値」「運用ルール」の3区分を必ず出力させ、仮定混入の事故を減らす。
2. **スコープ逸脱禁止の明文化:** 例えばtask_3_2なら「通信ロストのみ」「雪・追突は触れない」のように、冒頭と末尾の両方でスコープを確認させると安定する。
3. **最終チェックリストの固定化:** 「確定値の引用漏れなし」「新規数値の捏造なし」「他タスクへの越境なし」「責任分界が3者（Expert/User AI/Detector等）で閉じている」の4項目を、最後に自己点検させる。

**既存実装との関係:** BL-093（`think`ツールの`decided`/`why`/`rejected`/`rejected_why`フィールド新設）・BL-094（read_verified_fact/read_deliverable_fileによる確定値同期）・BL-087 Fix A/C（アンチパターン明記・派生値の条件明示）が土台にあるが、(a)出所ラベルの3区分強制、(b)`think`欄の空欄禁止、(c)スコープ逸脱防止の冒頭・末尾二重確認、(d)最終自己点検チェックリストの固定化、はいずれも未実装。

**設計未着手（`open`）。** 着手時にPlan modeで検討すべき論点：
1. 出所ラベル（確定値/推定値/運用ルール）をどの出力（`think`のsummary、最終JSON、ログ表示）に持たせるか。
2. `think`の`decided`等を空欄禁止にする場合、機械的強制（BL-093同様のバリデーション）にするか、プロンプト指示に留めるか。
3. 最終チェックリストの4項目を、どのノード（Expert/User AI/Detector/Reviewer全部か、一部か）に適用するか。
4. BL-087 Fix Aのスコープ逸脱防止（task_plan_reviewer限定）を他ノードにも横展開するか。

**完了条件:** 未定（設計後に記載）。

---

### BL-098: `cela_main.py`の責務分離（永続化層/ツール層/プロンプト・ノード層/UI・ログ層）

**経緯:** ユーザーが別AI（本セッションとは独立したAgent）に`cela_main.py`本体を独立レビューさせた指摘（BL-097と同じ回のレビューの続報）。

**指摘内容:** 内部工夫（think機構、read_verified_fact/read_deliverable_file等）は多いが、ファイル全体としては「巨大な一枚岩」感が強い。`cela_main.py`（7300行超）がロギング、DBスキーマ、python_repl、Record/Replay、各種ツール定義、LangGraphノード実装、プロンプト本文まで全部を単一ファイルで抱えており責務が密。プロトタイプとしては成立しているが、商用の長期運用を考えると、少なくとも「永続化層」「ツール層」「プロンプト/ノード層」「UI/ログ層」は分離した方が保守しやすいとの指摘。

**設計未着手（`open`）。** MVPの機能面（BL-093〜097等のドライラン品質改善）を優先し、機能が一段落してから着手する方針。着手時にPlan modeで検討すべき論点：
1. 分割単位（永続化層＝DBスキーマ・CRUD関数、ツール層＝各種`*_TOOL`定義とハンドラ、プロンプト・ノード層＝LangGraphノード関数群、UI・ログ層＝ロギング・Record/Replay）の妥当性。
2. モジュール間の依存方向（循環参照を避ける構成）。
3. 既存の`_CURRENT_*`グローバル状態（BL-099参照）を分割後にどう受け渡すか（引数化かcontext objectか）。
4. 既存テスト（`inspect.getsource`でノード関数のプロンプト文言を直接検証するテストが多数）への影響範囲。

**完了条件:** 未定（設計後に記載）。

---

### BL-099: モジュールレベルグローバル状態・文字列部分一致制御・`think`必須化のモデル遵守依存

**経緯:** BL-098と同じ別AIレビューの指摘。

**指摘内容:**
1. **グローバル状態への依存:** `_CURRENT_RUN_ID`/`_CURRENT_CALLER_ROLE`/`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`/`_CURRENT_GOAL_TEXT`（`cela_main.py:1061`付近）等のモジュールレベル変数に、実行コンテキストの受け渡しをかなり依存している。ローカル実験では十分だが、規模が上がると再現性・追跡性が落ちやすい。
2. **文字列部分一致による「ゆるい制御」:** `get_max_tokens`（`cela_main.py:318`）が`label.lower()`に対する`MAX_TOKENS_BY_ROLE`のキーワード（`"expert"`/`"user"`/`"detector"`等）の部分一致でmax tokenを切り替えている。同様に`LOW_TEMP_LABEL_KEYWORDS`/`STRUCTURED_OUTPUT_LABEL_KEYWORDS`も部分一致ベース。ラベル文字列のtypoや意図しない部分一致（例: 将来ラベルに`"reviewer"`以外の語で`"review"`を含む文字列が入る等）で誤動作しうる。
3. **`think`必須化の実効性はモデル遵守に依存:** BL-093で`think`+`summary`併用を`_query_AI_live`側で機械的強制済み（違反時は当該応答のツール呼び出しを全て差し戻す）だが、これはあくまで「thinkが入っていなければ差し戻す」という事後チェックであり、設計としては堅牢な一方、最終的な収束（モデルが指示に従ってthinkを呼ぶこと自体）はモデルの遵守に依存する部分がまだ残る。将来的にはtool-call層でのより網羅的な機械的バリデーション（例: 特定ツールの引数内容そのものの構造検証を増やす等）で安定性を高める余地がある。

**設計未着手（`open`）。** 着手時にPlan modeで検討すべき論点：
1. (1)(2)はBL-098の層分離（永続化層/ツール層等への切り出し）と合わせて検討し、`_CURRENT_*`グローバルをcontext object化・引数化するか、あるいは分離後も許容範囲かを判断する。
2. `label.lower()`部分一致を、役割を明示するenum等の型安全な機構に置き換えるかどうか。既存呼び出し箇所（ノード関数群）への影響範囲の洗い出しが必要。
3. (3)は既存のBL-093機械的強制の延長として個別に検討可能。今のところ具体的な事故は観測されていないため、優先度は(1)(2)より低い。

**完了条件:** 未定（設計後に記載）。

---

### BL-100: 前提を疑った際の「代替仮説・採用条件」を構造化して系譜として残す

**経緯:** BL-098/099と同じ別AIレビューの続報。

**指摘内容:** エージェントが前提を疑い代替案を提案する際（例:「移動手段はバスである」という前提を疑い、「オンデマンドタクシー補助」を代替提案する）、単に提案するだけでなく「問題設定を変更した理由」を以下の5項目セットで構造化して系譜として残すべきとの指摘：
1. 疑った前提（例:「移動手段はバスである」）
2. 疑った理由（例:「需要予測と運行コストが整合しない」）
3. 代替仮説（例:「オンデマンドタクシー補助」）
4. 期待される利点（例:「年間運営費を○○%削減できる可能性」）
5. この提案を採用するために追加で必要な情報（例:「タクシー事業者数、補助制度、利用実績」）

**既存実装との対応:** 現行の`ESCALATE_PREMISE_CONCERN_TOOL`（`cela_main.py:1265`、BL-086、`call_expert`/`generate_user_utterance`に配線済み）は、`implicated_constraint`（≒疑った前提）・`why_conflicts_with_true_need`（≒疑った理由）・`suggested_reframe`（≒代替仮説、ただし自由記述で「期待される利点」を定量的に分離するフィールドはない）を持つが、(4)期待される利点の定量化と(5)採用に必要な追加情報の明示という2項目に相当するフィールドが存在しない。また、この5項目セットの記録は現状state内の`goal_shift_events`相当（R5 GoalShiftEvent）に留まり、BL-096で新設予定の`issue_log`（後続タスクからの検索可能性）とは現状連携していない。

**設計未着手（`open`）。** 着手時に検討すべき論点：
1. `ESCALATE_PREMISE_CONCERN_TOOL`のパラメータに`expected_benefit`（期待される利点、定量的な見積もりを促す）・`info_needed_to_adopt`（採用に必要な追加情報）を追加する形で拡張するか、BL-096の`issue_log`に統合した新しいテーブル・ツールとして設計し直すか。
2. `info_needed_to_adopt`で列挙された「追加で必要な情報」を、後続タスク（例：需要予測タスク）が実際に確認・充足したかをどう追跡するか（BL-096の`resolution_note`／`status`遷移の再利用が候補）。
3. `resolve_premise_concern`（現行の却下専用ツール）と、この5項目セットの「採用」判断（`revise_goal`との関係）の整理。

**完了条件:** 未定（設計後に記載）。

---

### BL-101: task_plannerが差し戻し時に前回の「フェーズ・タスク表」ホワイトボードを参照せず全面再作成する

**経緯:** ユーザーによる実ドライラン（`log/2026-07-27/1438`）のリアルタイム観測。task_plan_reviewerに差し戻された後のtask_plannerの再分解を見ると、前回自分が作成したフェーズ・タスク表（`plan_drafts`ホワイトボード、BL-082/BL-087 Stage2）を一切参照せず、ゴール文と差し戻し指摘の要約テキストだけを頼りに、指摘されていない部分も含め毎回全フェーズ・全タスクを一から作り直している様子が確認された。

**根本原因（コード調査で特定）:**
1. `task_plan_reviewer_node`（差し戻し時）が`state["phases"] = []`で前回計画を即座に完全消去する。
2. `call_task_planner`は`reviewer_feedback`（自由文の指摘サマリー）と`goal`のみを受け取り、前回のフェーズ・タスクJSON構造そのものも、`plan_drafts`に書き込まれているはずのtask_plan_reviewerの個別指摘（`_append_reviewer_comment_to_plan`、BL-087 Stage2）も、一切プロンプトに渡っていなかった。

**副次的に発見した不整合:** BL-095でtask_plannerが`write_agreement(entry_type="Decision", topic="task_planner_phase_design")`として記録した判断根拠を、task_plan_reviewerが`read_deliverable_file(task_id="task_planner_phase_design")`で読もうとしているが、`read_deliverable_file`の逆引き（`_resolve_deliverable_pointer`）は`entry_type="Deliverable"`限定のため、Decision型の記録は原理的に永遠に`not_found`になる（ログ2414-2415/4169-4170行目で実際に確認）。BL-095の「task_plan_reviewerがtask_plannerの判断根拠を参照できる」という設計意図が実際には機能していなかった。

**対応（第一弾、`done`）:** task_planner自身が能動的に`plan_drafts`の最新版（task_plan_reviewerの個別指摘込み）を確認できる読み取り専用ツール`read_plan_draft`（`get_latest_plan_draft_by_task_id`のラッパー）を新設し、`call_task_planner`の差し戻し時プロンプトで「指摘のあったtask_idは必ずこのツールで前回の記述を確認し、その部分だけを修正する。指摘のないフェーズ・タスクは作り直さない」旨を明記した。

**検討したが今回は見送った、より確実な対策（ユーザー提案）:** `state["phases"]`を消去せず前回計画をbaselineとして保持し、task_plannerには変更が必要な部分のみをパッチとして出力させ、Python側で機械的にマージする方式（プロンプト指示ではなく機械的に「指摘されていない部分は不変」を保証する）。プロンプト指示による現在の対応がモデル遵守に依存する弱さを残すことは認識しているが、まず`read_plan_draft`ツールの効果を次回ドライランで確認してから、必要であれば機械的マージ方式へ発展させる方針とした。BL-095の`entry_type="Deliverable"`限定問題（Fix 2）も未対応のまま残っている。

**完了条件:**
- 新規`tests/test_bl101_task_planner_plan_draft_tool.py`（8件）: `get_latest_plan_draft_by_task_id`（phase_id不問での検索・最新版取得・not_found）、`_read_plan_draft_handler`（正常系・not_found・task_id必須エラー）、`TOOL_DISPATCH`配線、`call_task_planner`が`READ_PLAN_DRAFT_TOOL`を`tools=[...]`に渡しプロンプトにBL-101オリエンテーションを含むことを検証。
- `python -m py_compile cela_main.py`合格、関連クラスタ218件Pass（実装中に副作用で見つかった`test_bl087...`の文言重複バグも修正済み）。
- 実LLM再ドライランでの効果確認（差し戻し後、task_plannerが実際に指摘されたtask_idのみを修正し、無関係な部分を書き換えなくなるか）は次回待ち。Fix 2（`read_deliverable_file`のDecision型非対応）とパッチ/機械的マージ方式は別途検討。

---

### BL-102: Detectorのドメイン妥当性レビューパスで`_CURRENT_CALLER_ROLE`が"detector"に設定される前にwrite_issue等が呼ばれ権限エラーになる

**経緯:** [D-083](../decision_log.md#d-083-detectorのドメイン妥当性レビューパスにbl-096既存監査ツール群を配線する)でDetectorのドメイン妥当性レビューパス（第1段）に`write_issue`/`read_issues`等を配線した直後の実ドライラン（`log/2026-07-27/1551`）で発見。

**根本原因（コード調査で特定）:** `call_detector`は「ドメイン妥当性レビュー」（第1段）→「数値監査」（第2段）の2パス構成だが、`_CURRENT_CALLER_ROLE = "detector"`（および`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`）のグローバル代入は第2段の直前にしかなく、第1段実行時点ではグローバル変数は前回呼び出しノード（この回は直前に走った`call_expert`が設定した`"expert"`）の値のまま残っていた。第1段は従来`THINK_TOOL`のみで権限チェックを伴うツールを持たなかったため表面化していなかったが、`write_issue`のように`caller_role`ベースの権限チェック（`_check_issue_permission`）を持つツールを追加した瞬間にこの潜在バグが顕在化した。

**実際の被害（実ログで確認）:** Detector(Domain Review)がオペレーター最低2名常駐要件とピーク時1名充当の矛盾（有効なminor懸念）を`write_issue(action_type="CREATE", topic="operator_shortage_peak", ...)`で永続化しようとしたが、`{'success': False, 'error': "expertはaction_type='CREATE'のwrite_issueを実行できません（許可: []）"}`で拒否された。モデル自身は正しく原因を診断し（「私のロールはexpertであり…」）、フォールバックとして`observations`欄に記載する代替判断を取ったため即座の破綻はなかったが、BL-096が目的とする「後続タスクからも検索可能な形での永続化」は第1段では機能していなかった。

**対応（`done`）:** `call_detector`関数の冒頭（第1段のプロンプト構築より前）に`global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID, _CURRENT_PHASE_ID`と`_CURRENT_CALLER_ROLE = "detector"`等の代入を移動。従来第2段直前にあった同内容の重複代入は削除。

**完了条件:**
- `python -m py_compile cela_main.py`合格。
- 関連クラスタ（`bl096 or bl054 or bl076 or bl079 or bl093 or bl101 or bl062 or bl091`）113件Pass（既存挙動に影響なし）。
- 実LLM再ドライランで、Detector(Domain Review)が`write_issue(CREATE)`を権限エラーなく実行できることの確認は次回待ち。

---

### BL-103: hydrate/ノード間コンテキスト引き継ぎの改善

**経緯:** ユーザーから、`_build_hydrate_context`（decisions要約）＋`chat_history`窓（生ログ）によるノード間コンテキスト引き継ぎ設計への相談。「これで十分か・合理的か」という問いを受け、ユーザーが過去に設計した`C:\ai_work\NPU-Context-Saver`のhydrate機構（`HydrationManager.ts`/`HydrateSelection.ts`等、pin・Time-Aware RAG・トークン予算による段階的間引きを実装）を調査し対比した。

**対比結果とユーザーの判断（詳細は[BL103_basic_design.md](BL-103/BL103_basic_design.md)）:**
1. トークン予算制御（NPUの`packMaxEstTokens`）: NPUはローカルSLMのcontext枯渇対策であり、CELAでは不要（見送り）。
2. RAGによる古い関連情報の再浮上: CELAは`read_verified_fact`/`read_deliverable_file`/`read_issues`のプル型ツールで代替可能（見送り）。
3. 重要情報のpin: `issue_log`のescalated行をhydrate_contextへ常時マージする形で導入（承認）。
4. escalated issueのcall_expert/generate_user_utteranceへの注入: facilitatorのフィードバックはchat_history末尾追記のみでwindow超過後に消えるため「穴埋め」であり重複競合ではないと判断、詳細込みで注入（承認）。
5. ノード最終thinkの永続化: BL-093の`think`最終呼び出し内容（decided/why）を`decisions.why`に採用し要約の質を改善（ユーザー提案、承認）。

**調査中に発見した追加の欠落（スコープに追加）:**
- `generate_user_utterance_node`がUser AIの発言を一度も`decisions`テーブルに記録しておらず、hydrate要約チャネルから完全に欠落（Expertの発言は弱いながらも記録されるのに非対称）。
- `generate_user_utterance`内の独自インラインタイムラインが`get_decisions_from_db`の全件を無制限に展開しており、Expert側の窓付き`_build_hydrate_context_from_db`と非対称（`call_reflection`内の同種インラインタイムラインは定期的全履歴監査という別役割のため対象外）。実装前に、この無制限展開が`user_always_remember`（config、既定`True`）という名前の意図的な設計である可能性をユーザーに確認したところ、当初計画通り窓付きへ統一する方針が承認された。

**設計:** 新規`get_last_think_summary()`（`get_last_reasoning_text()`と同パターン）、`expert_node`/`generate_user_utterance_node`の`make_decision`呼び出し改善、`generate_user_utterance`のインラインタイムラインを`_build_hydrate_context_from_db`へ置き換え、新規`_build_escalation_pin_text()`をcall_expert/generate_user_utterance双方のhydrate_context直後に連結。新規テーブル・スキーマ変更なし。

**完了条件:** `python -m py_compile cela_main.py`合格、新規`tests/test_bl103_hydrate_context_improvements.py`（12件）Pass、関連クラスタ（`bl103 or bl086 or bl061 or bl096 or bl093 or bl075 or bl062 or bl033 or r4_smoke or bl101 or bl102 or bl095`）179件Pass、`check_docs_consistency.py`合格（既存の無関係な`npu_context_saver_reference_notes.md`未作成リンク切れを除く）。実LLM再ドライランでの効果確認は次回待ち。

---

### BL-104: call_expertのphases_json→目次化、read_project_planツール新設、プロンプトのキャッシュ効率改善

**経緯:** ドライラン`log/2026-07-27/1739`レビュー中に発見。詳細は[BL104_basic_design.md](BL-104/BL104_basic_design.md)。

1. `call_expert`の`phases_json`（全フェーズ・全タスク完全JSON、13,361文字）が毎回無条件注入されているが、`current_task_json`/`verified_facts_json`/`deferred_notes_text`と機能的にほぼ重複。BL-025のスコープガードレールの趣旨（他タスク領域への踏み込み防止）にも反する。
2. ユーザーからOpenRouterのプロンプトキャッシュヒット率が40%→5%へ急落したとの報告。調査の結果、`call_expert`のプロンプト組み立て順が「変動する内容が冒頭、分量最大の固定指示文がその後ろ」という、プレフィックスキャッシュに最も不利な構造だったことを確認。

**対応:** 新規`read_project_plan`ツール（全文詳細を能動的に取得）＋`phase_id`/`task_id`/`title`のみの軽量ToC常時表示に変更（User AI/task_plan_reviewerは全体像把握が本質的に必要なため`phases_json`全文を維持）。`call_expert`のプロンプトを「固定指示文を冒頭、動的データを末尾」の順に並び替え。各ブロックの位置的参照（「上記の」等）の有無を個別確認した上で並び替え可否を判断。

**進行状況:** `call_expert`・`generate_user_utterance`・`call_detector`（domain_prompt・数値監査用prompt）・`call_orchestrator`・`call_resource_arbiter`・`call_facilitator`・`call_integrator`・`call_reviewer`・`call_task_plan_reviewer`の並び替えが完了。`call_reflection`（位置的参照の多段連鎖のため最小限の変更のみ）・`call_task_planner`（reviewer_feedback_blockの先頭配置前提の位置的参照あり、かつ低頻度）・`call_goal_essence_analyst`（1回しか呼ばれずキャッシュ効果ゼロ）は意図的に見送り、理由をコード内コメントとバックログに明記。

**完了条件:** `python -m py_compile cela_main.py`合格、`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`（36件）Pass、関連クラスタ327件Pass、`check_docs_consistency.py`合格（自分の変更分に限る。既存の無関係な`npu_context_saver_reference_notes.md`未作成リンク切れを除く）。実LLM再ドライラン`log/2026-07-27/1911`（call_expert等3ノードまで適用時点のチェックポイント）でキャッシュヒット率が5%→13-15%へ改善したことを確認し、ログレビューで異常挙動・品質劣化がないことも確認済み。全ノード適用後の効果測定は次回ドライラン待ち。

---

### BL-105: checkpoint/resume機構がentry_pointから全体再走行するため未応答のUser発言が二重に積まれる（LangGraph本来のcheckpointer/`@task`未導入という設計ギャップ）

**状態:** `done`（Tier 1実装完了。Tier 2はスコープ外、将来ヒューマンインザループ機能を具体設計する際に着手）

**経緯:** `log/2026-07-27/2044`のツール使用失敗調査中に発見。

1. `run_ai_vs_ai_loop`（[cela_main.py:7812](../../../cela_main.py#L7812)）は自前のJSON checkpoint（`_save_checkpoint`/`_load_checkpoint`）を使っており、`--resume`時は必ず`app.stream(state, ...)`をグラフのentry_point（`graph.set_entry_point("goal_essence")`、[cela_main.py:7572](../../../cela_main.py#L7572)）から再実行する。
2. `goal_essence`/`task_planner`/`task_plan_reviewer`は`goal_essence_done`/`plan_review_done`等のフラグで再実行をスキップするが、その直後の`generate_user_utterance_node`（[cela_main.py:6348](../../../cela_main.py#L6348)）には同種のガードが無く、無条件に`state["chat_history"].append({"role": "user", ...})`する（6380行目）。差し戻し時の重複防止pop（6357-6361行目）は`constraint_issue == "major"`の時しか発火しないため、前回の一時停止が「User AIの発言をchat_historyに追記した直後、Expertがまだ応答する前」で発生していた場合、resume時にもう一つuser発言が積まれ、`⚠️ role連続を検出: index 3,4 = 'user'`という警告（[cela_main.py:2425](../../../cela_main.py#L2425)、既存の診断ログ）が発生する。
3. ユーザーから「本来はLangGraphのcheckpointerを使えば真の一時停止が利くのでは」との指摘があり、Context7で現行のLangGraph公式ドキュメント（`/websites/langchain_oss_python_langgraph`）を確認した。
   - `compile(checkpointer=...)` + `thread_id`ベースの再開は、entry_pointからの全体再走行ではなく**中断したノードの続きから**再開する（今回のバグの根本解消になる）。
   - ただしノード単位のcheckpointは「ノード**内部**の途中（Expert/Detectorの`_query_AI_live`ツールループの最中）」でのCtrl+Cには対応できず、そのノードは最初から再実行される。公式ドキュメントに以下の明記がある:
     > "Do not create new records before an `interrupt` call. Re-running the node upon resume will create duplicate records, leading to data inconsistencies."
   - これがユーザーの懸念（「ツールで登録しようとしたら既にDBにあった、という混乱」）の根本原因であり、真に解消するには`@task`デコレータでノード内部の個々のLLM呼び出し/tool呼び出しを個別checkpoint対象にする、さらに一段深い改修が必要と判明した。

**対応の選択肢（3段階、現時点でどれを採用するか未決定）:**

- **Tier 0（応急処置）**: `generate_user_utterance_node`等への再入場ガード追加のみ（例:「chat_historyが既に未応答のuser発言で終わっていれば再生成をスキップする」）。安価だが対症療法であり、他ノード（`reviewer_node`の[cela_main.py:7516](../../../cela_main.py#L7516)付近の無条件`user`role追加等）にも同種の潜在リスクが残る。
- **Tier 1（本質的だが中規模）**: LangGraph本来の`checkpointer`（`SqliteSaver`等）+ `thread_id`ベースの再開へ移行し、自前JSON checkpoint/`--resume <path>` CLIを置き換える。entry_point再走行バグを根絶するが、ノード内部の重複書き込みは残る。CLIの`--resume`引数・Ctrl+Cハンドリング（`KeyboardInterrupt`捕捉）・`goal_essence_done`等の既存idempotencyフラグの要否を含めた再設計が必要。
- **Tier 2（Tier 1を前提に、さらにノード内部を`@task`分解）**: Expert/Detector等が共有する`_query_AI_live`のツールループ内の各呼び出しを`@task`化し、ノード内部の途中再開にも対応する。実装コストが最大。

**完了条件（Tierを選定した後に確定）:** 未定。まずはユーザーとの設計相談でどのTierまで踏み込むかを決定してから、詳細設計書（`docs/design/back_log/BL-105/`）を作成する。

**実装完了（`done`）：** ユーザーから改めて「そろそろLangGraphの正式なチェックポイントを実装したい」との要望があり、`log/2026-08-04/1123→1355→1435→1546→1548`という同一runが5つの異なる`log/`ディレクトリへ跨って何度もCtrl+C/`--resume`を繰り返した実例を踏まえ着手。ユーザーへ「将来ヒューマンインザループ（HITL）実装を見据えるとTier1のみで足りるか」を確認され、`interrupt()`ベースのHITLはTier1（`checkpointer`）があれば動作するが、副作用を`interrupt()`呼び出し前に起こすと再開時に重複実行される制約があり、CELAの意味のある意思決定点（`write_agreement`/`revise_goal`等）はほぼ全てツールループ内部で発生するため、具体的なゲート設計が固まるまでTier2（`@task`分解）は見送るのが過剰設計を避けられると回答し、**Tier 1のみを実装する方針で合意**（詳細はdecision_lineage.md参照）。

Plan Mode（Explore不使用、既存コード調査＋LangGraph公式ドキュメントの再確認＋Plan agent 1体による検証を実施）で設計を作成し、`docs/design/back_log/BL-105/BL105_basic_design.md`として保存、ユーザー承認（ExitPlanMode）を経て実装：
- 新規依存`langgraph-checkpoint-sqlite`（`requirements.txt`新規作成）を追加・インストール。
- `_save_checkpoint`/`_load_checkpoint`（自前JSON checkpoint、`cela_main.py:206-224`）を削除。`CELA_CHECKPOINT_DB_PATH = "cela_checkpoints.db"`（リポジトリ直下、run跨ぎで単一ファイル、`thread_id == run_id`で一意に引ける）を新設。
- `build_graph(checkpointer: BaseCheckpointSaver | None = None)`へシグネチャ変更、`graph.compile(checkpointer=checkpointer)`。既存4箇所のトポロジー確認専用テスト呼び出し（引数無し）は後方互換。
- `run_ai_vs_ai_loop`を全面書き換え：`resume_run_id`（旧`resume_from`から改名）がある場合、`app.get_state(runtime_config)`で直近スナップショットを取得し、`snapshot.next`が非空（ラウンド途中で中断）なら最初の`app.stream()`入力を`None`にして「中断した直後のノードから」再開する。`snapshot.next`が空（ラウンド境界で中断）なら通常のフルstate投入。2回目以降のターンは既存通りフルstateを再投入（`goal: Annotated[str, _take_latest]`が上書き方式であることをコード確認済みのため、同一`thread_id`への繰り返し投入でも`chat_history`等が二重蓄積しないことを検証済み）。手動`_save_checkpoint`呼び出しは削除（checkpointerがノード完了ごとに自動永続化）。起動バナーに`run_id`を常時表示するよう追加。
- CLI `--resume`を`CHECKPOINT_JSON`（ファイルパス）から`RUN_ID`（run_id文字列）へ変更。
- `.gitignore`に`cela_checkpoints.db*`を追加（cela.db本体とは異なり、純粋な一時停止・再開用の一過性データのため）。
- `tests/test_checkpoint_resume.py`を全面書き換え：旧JSON checkpointの3テストを削除、CELAの実グラフとは独立した最小の合成グラフ（ノードA/B＋条件分岐ループ＋END）で「`None`入力再開が中断直後のノードから続き、完了済みノードを再実行しないこと」（核心の回帰テスト）・「同一`thread_id`への毎ターンフルstate再投入でリスト系フィールドが二重蓄積しないこと」・`build_graph()`の後方互換・`run_ai_vs_ai_loop`のresume分岐ロジック（存在しないrun_idでのエラー終了、新規runでは`get_state`を呼ばないこと）を新規追加（6件）。既存のノード冪等性テスト1件は無変更で維持。
- `tests/tools/db_checker.py`の`extract_run_id_from_checkpoint`（廃止）を`extract_latest_run_id_from_db`（`decisions`テーブルから最新run_id取得）へ置き換え。

`python -m py_compile`合格、`tests/test_checkpoint_resume.py`（6件）・既存関連4テストファイル（BL-087 Stage2/Stage3-4、BL-126 Stage D、BL-130）計85件無退行、フルオフラインスイート700件Pass。実ドライランでの効果確認（Ctrl+C→`--resume`でのuser発言重複解消）は次回の長時間ドライラン待ち。設計詳細は`docs/design/back_log/BL-105/BL105_basic_design.md`参照。

---

### BL-106: `_query_AI_live`の自動reasoningダイジェストがtool呼び出し履歴より手前（index 1）に居座り、毎iterプレフィックスキャッシュを破壊していた

**状態:** `done`

**経緯:** BL-104（プロンプト並び替え）を全ノードに適用した後もユーザーからキャッシュヒット率が改善せず1時間平均5.5%（分単位では0%も目立つ）との報告。

1. `_query_AI_live`（[cela_main.py:2414](../../../cela_main.py#L2414)）のツールループは、BL-093/D-074の自動reasoningダイジェスト機構を持つ。直近`_AUTO_REASONING_VERBATIM_ITERS`（=2）件は生reasoningのまま、それより古い分はthinkの`summary`に圧縮し、1つの`system`ロールメッセージとして`loop_messages`へ反映する。
2. 修正前は、この digest メッセージを初回のみ`loop_messages.insert(1, ...)`でsystem prompt（index 0）の直後に挿入し、以降は`loop_messages[1] = ...`という**固定index上書き**方式だった。これはindex 2以降にある実質的な会話履歴（tool呼び出し・tool結果。iterを重ねるほど肥大化し、本来最もキャッシュ効果が大きいはずの部分）より**手前**にあたる。
3. ユーザーから「古いiterの要約部分（例: `[iter1要約][iter2要約]`）はiterが進んでも不変のはずでは」との指摘があり、検証の結果、think summaryは一度確定すると変化しないため、その指摘自体は正しいことを確認・訂正。ただし、そのdigest不変部分は可変部分（直近2iterの生reasoning全文）と同じ1メッセージ内に同居しており、かつdigest自体がindex 2以降の履歴より手前にあるため、digestメッセージの長さがiterごとに伸縮するたびに、index 2以降のメッセージ（内容自体は不変）の絶対位置がずれ、プレフィックスキャッシュ（絶対位置での先頭一致方式）が毎iterミスしていたことが根本原因と特定。

**対応:** digestメッセージを固定indexではなくオブジェクト参照（`auto_reasoning_digest_message`）で追跡し、都度`loop_messages`の末尾から前回分を取り除いて末尾に付け直す方式に変更（[cela_main.py:2784-2793](../../../cela_main.py#L2784-L2793)付近）。これにより、digestより前にある安定した会話履歴のプレフィックスキャッシュが維持され、変化し続ける内容はBL-104の原則どおり末尾に閉じ込められる。

**完了条件:** `python -m py_compile cela_main.py`合格。既存テスト`tests/test_bl093_d074_auto_reasoning_enforcement.py`のdigest位置検証（旧: index 1固定）を新方式（末尾）に合わせて更新。`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass。実LLM再ドライランでの効果確認はユーザーが実施予定（`done`だが実測値は次回ドライラン待ち）。

---

### BL-107: `provider.order`固定がOpenRouterのsticky routingを無効化しており、toolsループ内の連続リクエストでキャッシュが構造的に0%だった

**状態:** `done`（`session_id`ベースのsticky routingへ切り替え、`provider.order`固定はワンラインで復元可能なフラグとして温存）

**経緯:** BL-106（digest末尾配置への修正）適用後もユーザーから「iter時はキャッシュヒット0%」との報告が継続。

1. OpenRouter公式ドキュメント・ブログ（[Prompt Caching Guide](https://openrouter.ai/docs/guides/best-practices/prompt-caching)、[Sticky Routing Blog](https://openrouter.ai/blog/tutorials/prompt-caching-sticky-routing/)）をWebFetchで確認した結果、「`provider.order`を手動指定するとsticky routing（同一会話の連続リクエストを同じバックエンドへ固定する仕組み）が無効化される」と明記されていることが判明。sticky routingが無効だと、プロンプトのプレフィックスが完全に同一でも、物理的に別のバックエンド実体へルーティングされうるためwarm cacheに当たらない。
2. 既存コード（[cela_main.py:2487-2498](../../../cela_main.py#L2487-L2498)）は`extra_body["provider"] = {"order": ["novita/fp8", "parasail/fp8"], "allow_fallbacks": False}`を常時指定しており、これがsticky routingを恒常的に無効化していた。
3. ユーザーから「provider固定はだいぶ前からで、python_replもツールとして使ってきたが、それでもキャッシュヒットは50%前後あった。26日17時台以降に急落した」との指摘があり、`git log`でBL-093コミット（`4a0bb46`、2026-07-26 18:03、"Wire THINK_TOOL into every LLM-calling node **including previously tools=None single-shot ones**"）を確認。これ以前は多くのノードが`tools=None`の単発呼び出し（toolsループを経由しない）であり、そちらはsticky routing不要のクロスコールキャッシュ（同一の固定指示文プレフィックスを持つ別リクエスト同士でのヒット）で50%前後を維持できていたと解釈。BL-093でほぼ全ノードがtoolsループ経由に切り替わったことで、元々存在した「ループ内（sticky routing必須）は`provider.order`のせいで0%」という弱点の影響範囲が急拡大し、平均値の急落として表面化したと整理し、ユーザーの時系列指摘と矛盾しないことを確認した。

**対応:** `_query_AI_live`内に切り替えフラグ`_USE_STICKY_SESSION_ROUTING`（[cela_main.py:2456](../../../cela_main.py#L2456)付近）を新設。`True`の場合は`provider.order`を送らず、`extra_body["session_id"] = f"{_CURRENT_RUN_ID}-{label_lower}"`（run_id＋ノード種別で安定したID）を渡してsticky routingを有効化。`False`に戻せば元の`provider.order`固定（novita/parasail限定・fallback禁止）に即座に復元できる。

**完了条件:** `python -m py_compile cela_main.py`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass。実LLM再ドライランでユーザーが「確かにキャッシュヒットは改善しました」と効果を確認済み（2026-07-27）。速度面の悪化報告なし。

---

### BL-108: 自動reasoningダイジェストの「直近N iterは生・それより古いのは要約」窓方式が、要約への切り替わり自体で毎iter不安定になっていたため、要約を廃止し単純な累積方式へ全面置換

**状態:** `done`

**経緯:** BL-107（sticky routing）適用後、ユーザーから「キャッシュヒットは改善したが、やはり微妙かもしれない」との報告。digestの実際の中身を確認してほしいと依頼された。

1. `log_with_prompt.md`はツールループの**最初のiterationの送信プロンプトしか記録しておらず**（[cela_main.py:2428-2438](../../../cela_main.py#L2428-L2438)、`_query_AI_live`冒頭で1回だけprintする実装）、iteration 2以降の`loop_messages`（digestを含む）は一度もログに出力されていないことが判明。ユーザーが開いていた`log/2026-07-28/0033/log_with_prompt.md`にはdigestの実物が存在しなかった。
2. `log_no_prompt.md`に残る生reasoning（`💭 [Detector] 思考（iter=N）`）と`think`のsummaryを実際のコードロジックに通して手元で再構築し、digestの実際の推移を測定。結果、要約済み部分（`[iter Nの要約]`）は数十〜数百文字と軽微な一方、直近2iter分の生reasoning全文（`_AUTO_REASONING_VERBATIM_ITERS=2`の窓）は1回あたり数千文字（最大6,077文字）に達し、digest全体の大半を占めていることを確認。窓の境界に当たる古いiterが生reasoning全文→summaryへ切り替わるたびにdigestの中身自体が変化し続けており、BL-106でdigestを末尾に固定した後もこの「窓の境界変化」という不安定要因が残っていたことが「微妙な改善」の実体と特定。
3. ユーザーから「要約せず、単純に生ログを積み上げたほうがキャッシュが働き、結果的に安いしシンプルかな？」との提案。同ログで試算した結果、iter8時点で要約方式6,341文字に対し単純累積では19,324文字（約3倍）になることを確認した上で、要約への切り替わりという不安定要因そのものが消えること（既存部分は書き換えられず追記のみになる）、AI自身のsummaryによる情報欠落リスクも無くなることから、提案を支持。

**対応:** `_AUTO_REASONING_VERBATIM_ITERS`の窓管理と`_THINK_REASONING_LOG`からのsummary逆引きロジックを廃止し、`auto_reasoning_history`に蓄積した全iterationの生reasoningを要約せずそのまま`[iter Nの思考(全文)]`として末尾追記し続ける方式に全面置換（[cela_main.py:2788-2798](../../../cela_main.py#L2788-L2798)付近）。BL-106のdigest末尾配置ロジック自体は変更なし。

**完了条件:** `python -m py_compile cela_main.py`合格。既存テスト`test_auto_reasoning_digest_uses_verbatim_for_recent_and_summary_for_older`を`test_auto_reasoning_digest_accumulates_without_summarizing`に改名し窓方式の検証を削除、`test_auto_reasoning_digest_content_captured_via_create_kwargs`をiter1も生reasoningのまま含まれることを確認するアサーションに変更。`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass、フルオフラインスイート（425 passed, 1件は再実行で再現しない一過性の失敗）も完了。実LLM再ドライランでユーザーが「30分平均で45%くらいに回復」と効果を確認済み（2026-07-28）。ただし、キャッシュ割引率（約1/10）とサイズ増加（約3倍）を踏まえた机上試算では、45%というヒット率は損益分岐点（約74%）に届いておらず、$コスト面では旧方式より高くつく可能性がある旨をユーザーに提示済み。実際の$コストはOpenRouter Activityダッシュボードでの実測が必要、現時点では未確認。

---

### BL-109: 複数ツールを組み合わせて検討する必要のない単発判定・抽出4ノード（Orchestrator/Decision Extractor/Reflection/Facilitator）から`THINK_TOOL`を外し、tools=Noneの単一応答パスへ差し戻す

**状態:** `done`

**経緯:** ユーザーが`log/2026-07-28/0033/log_no_prompt.md`を見て「Decision Extractorってthinkしかツールを持っていない？」と質問。

1. 確認したところ`call_decision_extractor`（[cela_main.py:5285](../../../cela_main.py#L5285)）は`tools=[THINK_TOOL]`のみで、DBの読み書きは行わず（会話履歴・既存トピックは全てプロンプトに埋め込み済み、抽出結果のDB反映は`decision_extractor_node`側のPythonコードが担当）、`think`の効果（複数iterをまたぐreasoningの引き継ぎ）が本来不要な単発抽出タスクであると判明。同様の設計（`tools=[THINK_TOOL]`のみ）を持つノードを`grep`で洗い出したところ、`call_orchestrator`・`call_reflection`・`call_facilitator`も同型と確認。
2. ユーザーから「メモ帳（think）が思考の補助になるかと思ったが要らないか」との確認があり、`think`ツールの本来の存在理由（OpenRouter配下の多くのプロバイダはreasoningトークンをターンをまたいで自動的に引き継がないため、手作りで引き継ぐための機構）が、そもそも単発（1ターンで完結）タスクには適用されないこと、かつこれら4ノードは元々（BL-093以前）`tools=None`の単一応答パスであり、その場合も`reasoning_effort_level`（Decision Extractorは"medium"、Reflectionは"high"）がネイティブに付与されていたため、reasoning自体は`think`ツール無しでも既に得られることを説明。ユーザーが「thinkしかツールがないノードは抜きましょう」と全4ノードの差し戻しを指示。

**対応:** `call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`の`query_AI`呼び出しから`tools=[THINK_TOOL]`を削除しtools=None（デフォルト）へ差し戻し、各関数内の「【BL-093】必要であれば、thinkツールで検討過程を書き残しても構いません。」等の案内文も削除。副次的に発見した罠として、`orchestrator`/`facilitator`は元々`reasoning_effort_level`を`elif tools is not None: "medium"`という**tools付与ノード向けのフォールバック経由でしか**得ていなかったため、単純にtools=Noneへ戻すとreasoningがサイレントに無効化される（`_query_AI_live`内、[cela_main.py:2485-2492](../../../cela_main.py#L2485-L2492)）。これを防ぐため`if label_lower in ("detector", "decision extractor", "orchestrator", "facilitator")`へ両ラベルを明示追加し、tools=None化後もreasoning_effort_level="medium"が維持されるようにした。`_reset_think_scratchpad()`呼び出し自体は、BL-103の`get_last_think_summary()`がノード呼び出し境界の目印として使うため、4ノードとも削除せず維持した。

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl093_think_tool_scratchpad.py`の`_ALL_THINK_WIRED_FUNCS`から4関数を除外し、`test_previously_tools_none_functions_no_longer_pass_tools_none`を`test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`（THINK_TOOL不参照の確認）に置換、reasoning_effort_level明示追加を確認する新規テストを追加。`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`の`test_call_reflection_bl093_mentioned_exactly_once_near_top`/`test_call_facilitator_bl093_precedes_reflection_block`（前提消滅につき廃止）を削除。関連クラスタ145件Pass。実LLM再ドライランでの効果確認は次回待ち（ループ往復削減によるレイテンシ・コスト低減が期待値）。

---

### BL-110: `_query_AI_live`のthink機械的強制（差し戻し）を撤廃し、thinkは任意呼び出しへ緩和する

**状態:** `done`

**経緯:** BL-109の議論を受け、ユーザーが「であるならば、自由なthinkの使用も意味がないですね。というか、今はコンテキストを丸ごと引き継いでいるので、think自体も意味がないか」と、BL-093/D-074のthink機械的強制そのものの必要性を問い直した。

1. `_query_AI_live`（[cela_main.py:2643-2649](../../../cela_main.py#L2643-L2649)）を確認したところ、ネイティブのreasoning（`delta.reasoning`）は`think`ツールを呼んだかどうかに一切関係なく、モデルがreasoningトークンを返す限り毎iter無条件で`reasoning_parts_all`へ蓄積されており、BL-108によりこれが要約されずそのままdigestとして次のiterへ引き継がれることを確認。つまりBL-093/D-074が本来解決しようとした「reasoningがターンをまたいで引き継がれない」問題は、think呼び出しの有無に関わらず既に別の仕組み（BL-108のdigest）で解決済みと判明。
2. `think`固有に残る価値は「decided/why/rejected/rejected_whyを構造化して明示させる」ことだけで、当初の「さもなくば思考が消える」という強い理由づけに比べ根拠が弱い一方、機械的強制（差し戻し）自体はこのセッション中に何度も測定した「think未添付差し戻し」（12回、3回、21回...）という実コストを生み続けていた。ユーザーが「thinkは残して、他ツールとの強制は外してください」と指示。

**対応:** `_query_AI_live`のツールループ内（[cela_main.py:2696](../../../cela_main.py#L2696)付近）から、think(summary付き)の有無をチェックして違反時にツール呼び出し全体を差し戻す分岐を削除し、`msg.tool_calls`を無条件でdispatchする（BL-093以前と同型の）構造に戻した。`think`ツール自体・`TOOL_DISPATCH["think"]`・`_think_handler`・BL-108のreasoning自動蓄積（digest）ロジックはすべて維持し、モデルが任意に`think`を呼べば従来通り記録される。あわせて、もう存在しない強制を前提にした案内文を全面修正: 英語ツールスキーマ側の`"[BL-093] MANDATORY: you MUST also call \`think\`..."`（14ツール、byte-identical）を`"[BL-110] Optionally call \`think\`...it is no longer required..."`へ、日本語プロンプト側の「〜を同時に呼ぶことを厳守しろ！think無しでこれらのツールだけを呼ぶと、その応答のツール呼び出しは一切実行されず、丸ごと無駄になります。」（10ノード）を「〜を呼んで検討過程を書き残しても構いません。」へ、それぞれ全面置換。

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl093_d074_auto_reasoning_enforcement.py`の`test_tool_call_without_think_is_rejected_and_not_executed`/`test_standalone_think_without_summary_is_also_rejected`を、差し戻されず実行されることを検証する`test_bl110_tool_call_without_think_now_executes_normally`/`test_bl110_standalone_think_without_summary_still_executes`に置換。モジュールdocstringもBL-108/BL-110の経緯を反映するよう更新。`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`/`tests/test_r3_smoke.py`計130件Pass、フルオフラインスイート実行中。実LLM再ドライランでの効果確認（think差し戻し起因の往復削減・レイテンシ/コスト低減）は次回待ち。

---

### BL-111: BL-108の「全iter分を1メッセージに再結合し末尾へ付け直す」方式が、新規tool呼び出しメッセージの追加によりdigestの相対位置が毎iterずれる同型の不具合を残しており、真の単調増加（append-only）へ再修正

**状態:** `done`

**経緯:** BL-108/BL-110適用後もキャッシュヒットが改善しないため、ユーザーが`_query_AI_live`のコードをGeminiに提示し第三者レビューを依頼。Geminiの指摘を受けて本人が持ち込み、内容を検証した上で反映。

1. Geminiの指摘: BL-108の実装は「新規のtool呼び出しメッセージ→古いdigestを削除→全iter分を再結合した新digestを末尾に付け直す」という手順を毎iter行っていた。これにより、iterNのリクエストでdigestが占めていた位置（＝末尾）に、iterN+1のリクエストでは新規tool呼び出しメッセージが来ることになり、そこから後ろ全体（新digest含む）が毎iterプレフィックス不一致になる。プレフィックスキャッシュが機能する絶対条件は「一度追加したメッセージは二度と変更・削除・移動しない」ことであり、BL-108は「常に末尾に置く」ことはできていたが「一度置いたら動かさない」ことができていなかった。
2. 実際にコードをトレースして検証: iter2向けリクエスト`[system, user, assistant1, tool1, digest_1]`とiter3向けリクエスト`[system, user, assistant1, tool1, assistant2, tool2, digest_2]`を比較すると、共通する厳密なプレフィックスは先頭4メッセージ（`system, user, assistant1, tool1`）までで、そこから後ろ（本来最もキャッシュさせたかった蓄積履歴部分）は一致しないことを確認。Gemini指摘は正しいと判断。

**対応:** 全iter分を1つのdigestメッセージに再結合するのをやめ、「そのiterationの生reasoningだけ」を独立した新規systemメッセージとして末尾に追記し、以後は一切変更・削除・移動しない方式（真のappend-only）に変更（[cela_main.py:2571-2582](../../../cela_main.py#L2571-L2582)のコメント、[cela_main.py:2755-2762](../../../cela_main.py#L2755-L2762)付近の実装）。`auto_reasoning_history`/`auto_reasoning_digest_message`の変数・追跡ロジックは不要になったため削除。

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl093_d074_auto_reasoning_enforcement.py`の`test_auto_reasoning_digest_content_captured_via_create_kwargs`を新構造（iterごとに独立したsystemメッセージ）に合わせて修正。新規`test_bl111_consecutive_requests_are_a_strict_prefix_of_each_other`を追加し、「iterNへのリクエストがiterN+1へのリクエストの厳密な先頭部分になっている」というプレフィックスキャッシュの必須条件そのものを直接検証する回帰テスト化した（BL-108時点ではこのテストが書かれていれば即座に発覚したはずのバグ、今後の再発防止）。`tests/test_bl093_think_tool_scratchpad.py`の`test_bl109_reasoning_effort_level_preserved_for_reverted_nodes`も、ユーザーがIDEで直接`reasoning_effort_level`のラベル分岐・値をチューニング中だったため固定文字列一致ではなく構造的な検証に変更。関連クラスタ131件Pass、フルオフラインスイート実行中。実LLM再ドライランでの効果確認は次回待ち。

---

### BL-112: Detectorが起票済みのissueをUser AIが未確認のまま別topic名で重複登録する（`read_issues`の「呼ぶつもり」と実際の呼び出しが乖離）

**状態:** `open`

**経緯:** `log/2026-07-28/1420`（BL-108〜111適用後の初回フレッシュドライラン）のレビュー中にユーザーの依頼で発見。task_1_1の成果物レビューで、Detectorが先に4件のissueを`write_issue`（CREATE）で登録済みだった（`task_1_1_運行時間の矛盾`、`task_1_1_折り返し時間3分`、`task_1_1_実効輸送力の矛盾`、`detector_observation_no_task`）。その後、User AI（`call_facilitator`相当）が成果物を承認する際、自身の思考ログで「Let me read the current issues first to see what's already logged.」と述べたにもかかわらず、実際には`read_issues`を呼ばずにそのまま`write_issue`（CREATE）を3件連続実行し、`task_2_2_折り返し時間の現実性`・`task_2_2_実効輸送力と車両定員の矛盾`・`task_2_2_リース残価率の楽観性`という別topic名で、Detectorが既に登録済みの懸念のうち2件（折り返し時間・実効輸送力）を実質的に重複登録した。User AIが直前に呼んだ`read_issues(list_all=true)`はtask_1_1着手前（まだissueが0件でnot_foundが正常だった時点）のものであり、Detectorの4件が登録された後には一度も`read_issues`を呼んでいない。

**影響:** 同一の実質的懸念が異なるtopic名・異なる`raised_by`（`detector` / `user_ai`相当）で二重に存在するため、後続タスクや別のAgentが`read_issues`で検索する際に一方しか見つけられずもう一方を見落とすリスク、またはissue件数が水増しされ全体像の把握コストが増えるリスクがある。ログ上でAIが明示的に行き詰まった形跡（無限ループ・繰り返し失敗）ではなく、「確認する」と述べた意図がツール呼び出しに反映されなかった見落とし。

**対応（未着手・要検討）:** 想定される対策candidate（実装は次回ユーザー承認後）:
1. 承認・issue登録系のノードのプロンプトに、「issueを新規作成する前に必ず`read_issues`で当該task_idの既存issueを確認し、既存issueと同一の懸念であれば新規作成せず`resolve_issue`等で参照する」ことを明示する。
2. `write_issue`のCREATE時に、同一`task_id`内で類似トピック（キーワード一致等）の既存issueがあれば警告を返す簡易重複検出をDB側に追加する。
3. 様子見: 次回以降のドライランでも同じ重複パターンが再発するか確認してから対応方針を決める。

**完了条件:** ユーザーとの相談の上、上記いずれかの対応方針を確定し実装した後、次回ドライランで同一懸念の重複issue登録が発生しないことを確認する。現時点ではコード変更なし、記録のみ。

---

### BL-113: THINK_TOOLスキーマの`description`に残っていたBL-093時代のMANDATORY強制文言・旧window方式の説明を、実装（BL-108/BL-110/BL-111）の実態に合わせて書き換える

**状態:** `done`

**経緯:** BL-112起票の流れでユーザーからプロンプト全体の整理についての相談があり、3体のExploreエージェントで(A)全ノードのシステム/ユーザープロンプト構成、(B)ツールschemaとプロンプト本文の重複、(C)ドメイン特化表現・冗長性を並行調査した。(B)の調査で、BL-110（`_query_AI_live`のthink機械的強制ロジック撤廃）の際にthink以外の14ツールスキーマの`description`は正しく書き換えられていたが、**THINK_TOOL自身のスキーマだけ書き換え対象から漏れており**、撤廃済みのはずの以下の文言がそのまま残っていることが判明した:

> "MANDATORY RULE (enforced mechanically, not a suggestion): EVERY SINGLE response you send that contains ANY tool call ... MUST include a `think` call with a non-empty `summary` IN THAT SAME RESPONSE ... NONE of that response's tool calls ... will be executed ..."

これは実装（`_query_AI_live`の無条件dispatch、BL-110）と直接矛盾する誤情報をモデルへ送り続けている状態であり、単なる文言の古さではなく実バグと判断した。加えて、同じ`description`と`summary`パラメータの説明文には、BL-108/BL-111で撤廃済みの「直近N iterのみ生・古いものは要約」という旧window方式を前提にした表現（`raw reasoning window`、`ages out`）も残っており、こちらもBL-108以降の実際の挙動（要約せず全iterationをappend-onlyで蓄積）と食い違っていた。ユーザーはAskUserQuestionで、この調査で見つかった4件の問題のうち、他の3件（`call_orchestrator`の静的/動的順序バグ、バス特化表現の一般化、重複ボイラープレートの統合）はスコープ外とし、このTHINK_TOOL書き換え漏れ修正のみを最優先で対応する方針を選択した。

**対応:** THINK_TOOLの`description`（[cela_main.py:958-967](../../../cela_main.py#L958-L967)）から、BL-093のMANDATORY強制文言と旧window方式の説明を削除し、他14ツールと同じトーンで「thinkは任意（呼べばsummary等が記録される）」「生reasoningはthink呼び出しの有無に関わらずネイティブに自動蓄積される（BL-108/BL-111）」という実態に即した説明へ書き換えた。あわせて`summary`パラメータの説明文（[cela_main.py:982-987](../../../cela_main.py#L982-L987)付近）からも「ages out of the raw reasoning window」という旧window前提の表現を削除した。`"required": ["action", "summary"]`（thinkコール自体のパラメータ必須指定）は変更していない。

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl093_d074_auto_reasoning_enforcement.py`・`tests/test_bl093_think_tool_scratchpad.py`にTHINK_TOOLのdescription文字列を直接assertするテストが無いことをgrepで確認済み（該当なし）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_r3_smoke.py`計97件Pass。実LLM再ドライランでの効果確認は次回待ち。

---

### BL-114: `call_orchestrator`の静的/動的順序が、コード自身のBL-104コメントと矛盾している

**状態:** `done`

**経緯:** BL-113と同じプロンプト整理調査（カテゴリA: システム/ユーザープロンプトの使い分け）のExploreエージェントが発見。他の大半のノードはBL-104のコメントで「静的な指示文を先頭、動的なコンテキスト（goal/DB/履歴）を末尾に置く」というプレフィックスキャッシュ最適化方針を明記し実装もその順序に沿っていたが、`call_orchestrator`だけは同じ方針をコメントで謳いながら動的な`goal_context`が先頭に置かれる逆順になっていた。実装着手前に3体のExploreエージェントで現行コード（2026-07-30時点）を再調査し直し、この乖離が実在することを再確認した。

**対応（実装完了）:** プロンプトを「静的（役割・肩書き生成指示・BL-078）→動的（`goal_context`→`user_input`→`agreements_text`→`history_text`）→JSON形式指示（末尾）」の順に並び替えた。JSON形式指示を静的先頭ブロックに含めず末尾に残したのは、`call_task_plan_reviewer`の既存の正しい実装が同じ配置であり、動的ブロックでプレフィックスキャッシュが一度途切れた後は短い末尾ブロックを先頭へ動かしても利益がないため。矛盾していたBL-104コメントも実態に合わせて修正した。同時にBL-116（専門家タイトル例の一般化）も同じ箇所に適用済み。

**完了条件:** `python -m py_compile cela_main.py`合格。既存の順序回帰テスト（`test_call_orchestrator_static_instruction_precedes_user_input`・`test_call_orchestrator_user_input_precedes_agreements_and_history`、`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`）が無修正のままPass（相対順序を保ったため）。

---

### BL-115: ノードプロンプト間の重複ボイラープレート、および`call_decision_extractor`の未使用デッドコード（`prompt_old`）

**状態:** `done`

**経緯:** BL-113と同じ調査（カテゴリB: ツールschemaとプロンプト本文の重複）のExploreエージェントが発見。「think任意呼び出し」説明・「read_verified_fact/read_deliverable_fileによるフェーズ間同期」説明・「同じ検証・計算を繰り返さない」注意書き等が10近いノードに分散重複し、`call_decision_extractor`には未使用デッドコード`prompt_old`（約60行）が存在していた。実装着手前に3体のExploreエージェントで現行コード（BL-104/113/119/126/130/131/TOOL_DISPATCH適用後）を再調査し直し、重複箇所を再確認した。

**対応（実装完了）:**
1. `call_decision_extractor`の未使用`prompt_old`ブロックを削除。
2. モジュールレベル共有定数`_BL093_THINK_VALUE_PARAGRAPH`（think任意呼び出し＋価値説明）・`_THINK_TRAILER_SENTENCE`（ツール一覧末尾の定型文）、共有関数`_verification_throttle_warning(example="")`（検証回数抑制注意書き）を新設。byte-identicalまたは近似していた箇所（`call_task_planner`/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`call_goal_essence_analyst`/`generate_user_utterance`/`call_task_plan_reviewer`/`call_expert`の`light_system_prompt`）に適用した。
3. `call_detector`は`domain_prompt`/`prompt`という2つのプロンプトを同一関数内で構築しており、気づき欄（BL-051）・issue引き継ぎ説明（BL-096）が重複していたため、関数内ローカル変数（`_observations_block`/`_issue_carryover_prefix`）に集約し両プロンプトから参照する形にした（関数内限定の重複のためモジュールレベルにはしていない）。
4. **見送った共有化とその理由**: (a) BL-094（read_verified_fact/read_deliverable_file同期説明）は当初パラメータ化ヘルパー`_bl094_sync_template()`への集約を試みたが、既存の`tests/test_bl094_read_tool_orientation.py`が各関数自身の`inspect.getsource()`に"BL-094"/"read_verified_fact"/"read_deliverable_file"/"iter=1で"のリテラル文字列が含まれることを要求しており、ヘルパー化すると呼び出し元のソースからこれらの文字列が消えてテストが壊れるため断念し、各関数にliteralのまま残した（ヘルパー自体は削除、コードにその経緯をコメントで明記）。(b) ツール一覧文（「あなたが使えるツールは...」）も同様の理由（`tests/test_bl093_think_tool_scratchpad.py`の`test_node_prompt_names_its_own_tools_alongside_think`が同種の制約を持つ）で各呼び出し元にインラインのまま維持し、末尾の定型文のみ共有化した。(c) `call_expert`の`system_prompt`/`light_system_prompt`の意図的な二重化（BL-025のプロンプトキャッシュ/token-lean tradeoff）は統合していない。

**完了条件:** `python -m py_compile cela_main.py`合格。新規回帰テスト2件（`generate_user_utterance`のゴミ引用符混入なし確認、BL-116と共通）追加。既存テスト11件（`test_bl087_stage2_task_plan_reviewer_node.py`・`test_bl087_task_planner_prompt_and_resubmission_fix.py`・`test_bl089_anti_repetition_instructions.py`・`test_bl094_read_tool_orientation.py`・`test_bl104_project_plan_toc_and_prompt_reorder.py`）が、共有ヘルパーへの集約・ドメイン例の一般化に伴うリテラル文字列変更に合わせて更新済み。フルオフラインスイート（`pytest tests/ -q --ignore=tests/test_f26_detection.py`）514件Pass。

---

### BL-116: プロンプトへのバス交通シナリオ特化例の埋め込み、および冗長な指示文・ゴミ文字混入

**状態:** `done`

**経緯:** BL-113と同じ調査（カテゴリC: ドメイン特化表現・冗長性）のExploreエージェントが発見。バス交通シナリオでのドライラン実績から生まれた具体的な数値・ドメイン例が`call_task_plan_reviewer`（「山間部2km≒ルート全体13.33km」等）・`call_task_planner`（車両台数・初期費用の内訳例）・`call_orchestrator`（専門家タイトル例）・`call_decision_extractor`（「車両は3台体制とする」）に埋め込まれ、`generate_user_utterance`にf-string由来のゴミ引用符混入も見つかっていた。実装着手前に3体のExploreエージェントで現行コード（2026-07-30時点）を再調査し直した。

**対応（実装完了）:**
1. `call_task_plan_reviewer`の実インシデント数値例を、教訓（Reviewerが絶対値の確定を強く求めすぎるとtask_plannerがゴール文にない数値をでっち上げる）を保ったままドメイン非依存の一般化された表現（「〈部分X〉2単位≒全体の13.33%」等）へ置換。
2. `call_task_planner`の車両台数・初期費用例を、教訓（派生値には根拠条件を併記する）を保ったまま一般化されたプレースホルダ表現へ置換。
3. `call_orchestrator`の専門家タイトル例を、「具体性を要求する」教訓を保ったままドメイン非依存の表現（「〈対象領域〉の需要予測専門家」等）へ一般化。
4. `call_decision_extractor`の「車両は3台体制とする」を、Decision/Directive/Deliverable分類の教訓を保ったまま一般化した例へ置換。
5. `generate_user_utterance`のf-string由来のゴミ引用符混入バグ（各行が個別に閉じられた文字列であるかのように書かれ`\n"`というリテラルな引用符がプロンプト本文へ混入していた、複数箇所）を修正。
6. **確認のみ（変更不要）**: `call_expert`/`call_detector`/`generate_user_utterance`の労働基準法・シフト関連の記述は、実際に読み直した結果、既に「労働基準法上のシフト・休憩要件、物理的な運用可能性、予備・冗長性の欠如、安全規制等」という汎用的な表現であり、バス特化のフレーミングは無いことを確認した。
7. **対象外（スコープ外）**: `run_ai_vs_ai_loop`のCLIデフォルトデモゴール文字列（バス交通シナリオそのもの）は、ノードの指示文ではなくユーザーが選択する実行シナリオであり、BL-114/115/116が対象とする「ノード側指示文のドメイン非依存性」の範囲外のため変更していない。

**完了条件:** `python -m py_compile cela_main.py`合格。`generate_user_utterance`のゴミ引用符混入なしを検証する新規回帰テスト2件を追加。既存テスト2件（`test_bl087_stage2_task_plan_reviewer_node.py::test_reviewer_prompt_forbids_fabricating_values_absent_from_goal_text`・`test_bl087_task_planner_prompt_and_resubmission_fix.py::test_bl087_task_planner_prompt_references_the_12km_15_percent_failure_example`）を一般化後のリテラル文字列に合わせて更新。フルオフラインスイート514件Pass。実LLM再ドライランでの汎用例置き換え後のモデル理解度・出力品質確認は次回待ち。

---

### BL-117: 各ノードへのドメイン非依存な思考フレームワーク導入（Gemini提案の評価）

**状態:** `open`

**経緯:** ユーザーがGeminiに依頼して作成した「各ノードに適したドメイン非依存の思考フレームワーク」提案表を持ち込み、評価を依頼した。提案表は各ノード（Goal Essence Analyst/Task Planner/Task Plan Reviewer/Orchestrator/Expert/Detector/Decision Extractor/Resource Arbiter/Reflection/Facilitator/Integrator/Reviewer/User AI）に対し、「推奨思考フレームワーク」（例: WBS+MECE、ReAct+仮説検証サイクル、悪魔の代弁者+ファクトチェック等）とその選定目的を提示するもの。BL-116（バス交通シナリオ特化例の一般化）で見つかった「具体例に頼った説明」を、名前の付いた抽象的な思考の型に置き換えることで解決しうるアプローチであり、BL-116と自然に接続する。

`cela_main.py`の各ノードの実装（docstring・実際のプロンプト本文）と突き合わせて検証した結果:

- **◎（実装とよく整合しそのまま採用可、9ノード）**: Task Planner（WBS+MECE、4183-4184行目のフェーズ/タスク/依存/owns_variables分解と一致）、Task Plan Reviewer（プレモータム分析+ボトルネック分析、6518-6539行目の4観点実行前ゲートと一致）、Orchestrator（コンピテンシー評価+コンテキスト・アサインメント、4375-4377行目の専門家選定と一致）、Expert（ReAct+仮説検証サイクル、python_replとの短サイクル実行・F-2.6検算ゲートと一致）、Detector（悪魔の代弁者+ファクトチェック、4760-4762行目の2段監査と一致）、Decision Extractor（DST+情報構造化、5228-5230行目のCREATE/UPDATE判定と一致）、Reflection（メタ認知+鳥瞰思考、5566-5567行目のcompleted/stagnant/continuing判定と一致）、Integrator（システム思考+クロス・インスペクション、5775-5777行目のタスク間・フェーズ間矛盾検知と一致）、Reviewer QA（ゼロベース思考+適合性評価、5834-5836行目のゴール適合検品と一致）。
- **△（部分的に妥当だがギャップあり、4ノード）**:
  1. Goal Essence Analyst（デザイン思考+5 Whys）: 「本質の言語化」観点には合うが、実装（6358-6384行目）は「大まかな実現可能性チェック（python_replでの概算・オーダー感把握）」という観点1が提案に含まれていない。
  2. Resource Arbiter（トレードオフ分析+MoSCoW）: トレードオフ分析は良い一致。MoSCoW（Must/Should/Could/Won't）は現状未実装（今は「縮小/多く配分」の二択的指示のみ）で、導入するなら実質的な出力形式・判断軸の変更が必要。
  3. Facilitator（リフレーミング+ORIDモデル）: リフレーミングは良い一致。ORID（Objective/Reflective/Interpretive/Decisional）は現状未実装の具体的な4段階質問技法で、導入するなら実質的なプロンプト設計が必要。
  4. User AI（OODAループ+発注者統制思考）: 観察→評価→承認/却下/軌道修正という流れ自体は合っているが、「OODA」という軍事由来サイクル名を書くだけでは効果が薄い懸念があり、「発注者統制思考」の方が実務的に効きそう。

**全体所感（実装時に踏まえるべき懸念）:**
1. フレームワーク名（「WBS」「ReAct」等）を書くだけの「ラベル貼り」は効果が薄く、各フレームワークが「具体的にどう考えるか」の手順・チェックリストまで落とし込む必要がある。
2. BL-116で「冗長な指示文」を問題視したばかりのため、1ノードにつき主軸フレームワーク1つ+補助1つ程度に抑え、説明も簡潔にすべき。
3. △評価の4ノードは他の◎評価ノードより実装の手間がかかる（名前を採用するだけでなく実質的な構造変更が伴うため）。

**対応:** 評価のみ実施。ユーザーがAskUserQuestionで「評価のみで一旦区切り、実装は別途スコープを決めてから着手する」を選択したため、コード変更は行っていない。

**完了条件:** 次回、実装スコープ（BL-116との統合可否、△評価4ノードの設計詳細）が確定した時点で、別途実装・テスト・ドキュメント更新を行う。

Geminiの提案表全文・評価根拠は`docs/design/back_log/BL-117/BL117_investigation.md`に保存。

---

### BL-118: `cela_main.py`のモジュール分割（クラス/ノード単位でのファイル化、疎結合化）

**状態:** `open`（設計相談中）

**経緯:** BL-117の議論の流れで、ユーザーが「プロンプトの集約化（外部化）で言うと、今は1つのpythonで大きな岩になってしまっているので、クラスごとにファイル化するなど疎結合にしていく整理も考えたい」と提起。BL-115（重複ボイラープレート統合）はプロンプト文字列レベルの重複整理だが、本件はそれとは別に、`cela_main.py`というファイル構成そのもの（ノード関数群・ツールschema定義・DBアクセス層・ロギング等が単一ファイルに同居している状態）を、ノードやレイヤー単位で分割し疎結合にできないか、という規模・保守性の懸念。

**現状（参考情報）:** `cela_main.py`は8,000行超。ノード関数（`call_expert`/`call_detector`等13個）、ツールschema定義（`*_TOOL`辞書15個）、DB層（`get_active_conn`/`commit_*`等）、`_query_AI_live`本体、ロギング（`MultiLogger`等）が全て同一モジュール内に定義されている。

**対応（未着手）:** 具体的な分割方針・粒度（ノードごとにファイル分割するか、レイヤー単位（tools/db/nodes/prompts）で分割するか等）は未検討。ユーザーが「全体の進め方を考える」段階であり、実装スコープ・優先度・タイミング（BL-115/116/117の実装と同時にやるか、別途やるか）は未定。

**完了条件:** 分割方針についてユーザーと相談し、設計方針を確定した上で、別途実装計画（Plan Mode）を立てる。

---

### BL-119: BL-091のwrite_agreement成否シグナルが「今回ターンのみ」の判定であることをDetectorに明示しておらず、過去ターンで既に登録済みのケースを「虚偽の完了報告」と繰り返し誤判定していた

**状態:** `done`

**経緯:** `log/2026-07-28/1420`のドライラン継続レビューで発見。BL-091（`call_detector`の`write_agreement_status_block`、4821-4839行目）は「今回のターンでwrite_agreementが成功したか」を明示する仕組みだが、成功していない場合の文言が「実際には一切反映されていません...発言内容がそれと食い違う場合はconstraint_issue='major'」という断定的なものだった。これにより、task_1_2の数値修正が実際には**別の過去ターンで既に登録済み**（`AG-1785225752828`）だったにもかかわらず、Detectorが3試行多数決で`major`（虚偽の完了報告）と繰り返し判定し、ログ全体の約半分を占める長時間の差し戻し応酬が発生した。Detector自身が最終的に`read_deliverable_file`で過去の登録内容を確認し「実害はない」と自己修正して収束したが、そこに至るコストが大きかった。

ユーザーがBL-117/D-094の議論（フレームワークの具体性は「呼び出し順序」ではなく「判断基準と罠（ピットフォール）」に持たせるべき、という設計原則）を踏まえ、「これはまさに罠の一例。プロンプトに書くべき」と指摘し、BL-117全体の実装を待たず今すぐ小さく修正する方針を選択した。

**対応:** `write_agreement_status_block`（[cela_main.py:4830-4841](../../../cela_main.py#L4830-L4841)）の「今回success=0」時の文言に、以下の罠の説明を追加した:
- これはあくまで「今回のターン内」の話であり、過去のターンで既に登録済みの場合は0でも正常であること
- 相手が「更新した」「登録した」と主張していたら、まず【R4: 現在タスクの成果物・最新ホワイトボード】や既存のDecision/Agreementの内容を実際に確認し、主張と一致するかで判定すること
- 内容が一致するなら過去のターンで既に反映済みという正常な状態であり虚偽ではないこと。今回success=0という理由だけで即`major`にせず、必要なら`read_deliverable_file`で過去の登録内容を確認してから判断すること

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`（`write_agreement_status_block`という変数名・`BL-091`タグの存在を構造的にアサートするのみで文言変更の影響を受けない）7件Pass。実LLM再ドライランで、過去ターンで既に登録済みのケースにおいて同様の誤判定・長時間応酬が再発しないことを確認するのは次回待ち。

---

### BL-120: `call_reflection`のJSONパース失敗フォールバックが`stagnant`即断となっており、正常進行中の議論を繰り返し強制巻き戻ししていた

**状態:** `done`（D-1xx参照、BL-126 Stage D着手前提として実装）

**経緯:** `log/2026-07-28/1420`（NVIDIA Nemotron 3 Ultra使用ドライラン）で発見。`call_reflection`の出力JSONパースに失敗すると`fallback={"still_aligned": False, "discussion_status": "stagnant", "note": "Parse error."}`（cela_main.py:5707）を返す設計だが、これが単なる安全側フォールバックではなく実際に繰り返し発火し、正常に進行中の議論を強制的に巻き戻す事故として実測された。同一の`[reflection] - why: 【判定: ゴール・ドリフト（目標逸脱）を検出】 Parse error.`が34545/38310/40590/42238/43578行目の計5回、ほぼ同一のFacilitator論点提示・Expertの同一task_2_2再分析を伴って出現しており、「20%需要平準化が現実的上限」という同一の結論表が29397〜38673行目に渡り反復生成される主因になっていた。

**実装内容（done）:** 真因は「単発のquery_AI+_safe_json_parseで層2リトライ（BL-089、D-005）を持たなかったこと」——1回の一時的なパース崩れが即座にstagnant判定へ直結していた。`call_reflection`を`_query_and_parse_with_retry`でラップし、他ノード（task_plan_reviewer/task_planner/goal_essence_analyst）と同型の層2リトライを適用。真にリトライを使い切った場合のみ、従来通り`stagnant`へフェイルクローズする（安全側の判定方針自体は変更しない）。

**検証:** 新規テスト2件（`tests/test_bl089_json_fence_and_failclosed_review.py`に追加）。`python -m py_compile`合格。

---

### BL-121: `facilitation_count>3`/`review_count>3`によるHALTが3回セットされたにもかかわらず、外側ループが一度も停止せず会話が継続していた

**状態:** `open`（部分修正実施、根本原因の最終確認は次回ドライラン待ち）

**経緯:** `log/2026-07-29/0751`で発見。「強制停止」「処理を完全停止」という`halt_node`由来の決定ログが2381/8542/13649行目の3箇所で記録されている（＝`facilitation_count>3`によって`state["halt"]=True`がセットされ、`route_after_facilitator`が`"halt"`ノードへルーティングされたことを意味する）にもかかわらず、いずれの直後にも本来出力されるはずの外側ループの`🚨 [HALT] システム停止シグナルが送信されました`・`🏁 評価ループが終了しました`が一度も出力されず、会話がそのまま継続している。グラフの配線自体（`halt`→`END`、外側`while`の`if state["halt"]: break`、cela_main.py:7738-7747, 7769, 7938-7940）はコード読解上は正しく見える。

**追加調査（BL-122対応の続きとして実施）:** `log_no_prompt.md`全17265行を精査。プロセス起動バナー（`# Execution Log Started at:`）は1件のみ、外側whileループの`🔷 [Turn N/30]`バナーも「Turn 3」の1件のみで、単一プロセスの単一継続実行であることを確認した（複数プロセスがログファイルを共有した形跡はない）。`state["facilitation_count"]`の加算箇所は`facilitator_node`内の`+= 1`（1箇所）のみで、リセット箇所は初期state生成時（run開始時に1回、`facilitation_count: 0`）以外に存在しないことをコード全体の`grep`で確認した。単調増加する値である以上、一度>3を超えれば以後常にhalt条件を満たし続けるはずだが、run終了時点の`checkpoint.json`は`facilitation_count=2, halt=False`であり、観測された3回の「強制停止」と整合しない。この矛盾を調査した結果、BL-132（`detector_node`が呼び出しのたびに全決定履歴を再取得・再出力していたバグ）により、過去の「強制停止」決定がその後の複数回のdetector呼び出しのたびに**再表示**されていた可能性が高いと判明した。BL-132を先に修正することで、次回ドライランのログでは各decisionが一度しか出力されなくなり、「本当に何回halt条件が満たされたのか」を正確に切り分けられるようになる。

**対応（一部実施）:** (a) API例外時のツールループ再試行（BL-122で修正済み）は本事象とは別経路であり直接の原因ではないと判断。(b) チェックポイント再読み込み直後に`state.get("halt")`を一切チェックせず外側whileループへ入っていた実装上の欠落を確認し、**修正済み（`done`）**: `run_ai_vs_ai_loop`の`--resume`処理直後に、読み込んだcheckpointが既に`halt=True`だった場合は即座に停止するチェックを追加した（`python -m py_compile`合格、関連クラスタ132件Pass）。ただし今回の`0751`ログは単一継続プロセスであり`--resume`境界を含まないため、この修正が今回の事象そのものの原因だったとは断定できない。BL-132適用後の次回ドライランで、決定ログの重複表示が解消された上で改めてhalt発生回数を確認する。

**完了条件:** BL-132適用後の次回ドライランで、halt条件が実際に何回・どの経路で満たされたかを重複表示なしに確認し、なお外側ループが停止しない実行時の乖離が残っていれば、その時点で追加調査・修正を行う。

---

### BL-122: APIエラー時のツールループ全体巻き戻しリトライ（BL-009/BL-046）が、モデル変更（Nemotron）後に発生頻度が明らかに増加し実害が拡大している

**状態:** `done`

**経緯:** `log/2026-07-28/1420`・`2257`・`2026-07-29/0751`のいずれでも、APIエラー（レート制限・タイムアウト・不完全なレスポンス）発生時に「ツールループを最初からやり直します」というBL-009/BL-046の既知の粗いリトライ粒度（`loop_messages`/`python_calls_log`を破棄しiter=1へ巻き戻る）が高頻度で発生していることを再確認した。特にNVIDIA Nemotron 3 Ultra（free）を使用したドライランではリトライ発生回数がDeepSeek使用時より明らかに増えており（1420ログだけで6箇所以上）、モデル変更によってこの既知の設計上の粗さが顕在化しやすくなることが裏付けられた。ユーザーが「もったいなすぎる」と即時修正を指示。

**対応:** `_query_AI_live`（[cela_main.py:2396](../../../cela_main.py#L2396)）の以下を修正:
1. `loop_messages`/`tool_calls_used`/`python_calls_log`/`reasoning_parts_all`の初期化、および新規`iteration_start`変数を、外側の`for attempt in range(len(delays)+1):`リトライループの**外**（関数冒頭）へ移動。tools無し単発呼び出し経路（cross-iteration状態を持たないため無変更）はそのまま。
2. `for iteration in range(1, MAX_TOOL_ITER+1):`を`for iteration in range(iteration_start, MAX_TOOL_ITER+1):`に変更し、ループ本体の先頭で`iteration_start = iteration`を都度更新。これにより、APIエラーで外側の`for attempt`がリトライされても、同じiteration番号から再開する（1から再スタートしない、既に成功したiterationも重複実行しない）。
3. `repl_session`の生成場所（各attemptで作り直す）はBL-014の設計意図（ノード・リトライをまたいだpython_repl状態の非共有）を尊重し変更していない。

**副次的な効果:** 従来は1回のAPIエラーでiteration=1から際限なく再開できてしまい、実質的に`MAX_TOOL_ITER=20`の上限を超えてツール呼び出しを重ねられていた（意図しない予算超過）。本修正により、リトライしても消費済みのiteration数は失われなくなり、真の意味で「20回まで」の上限が機能するようになった（`MAX_TOOL_ITER`の値自体は変更なし）。

**完了条件:** `python -m py_compile cela_main.py`合格。`tests/test_bl093_d074_auto_reasoning_enforcement.py`に新規`test_bl122_api_error_mid_loop_resumes_same_iteration_without_discarding_progress`を追加し、フェイククライアントでiteration 2の途中にAPIエラー（`httpx.TimeoutException`）を模擬、リトライ後にiteration 1の進捗（think要約等）が保持されたままiteration 2から再開されることを検証（`create()`呼び出し回数が期待通り4回になることも確認）。関連クラスタ98件Pass。実LLM再ドライランでの効果確認（Nemotron使用時のリトライ実害減少）は次回待ち。

---

### BL-123: `call_detector`だけがescalated issueの強制注入（`_build_escalation_pin_text`、BL-103）を受け取っておらず、他ロールが既に折り込み済みの懸念を独立に再判定してしまう

**状態:** `done`

**経緯:** ユーザー指摘を受けてコード確認。`_build_escalation_pin_text`（issue_logのescalated行をchat_history_windowのrecencyに関係なく強制注入する、BL-103のpin機構）の呼び出し箇所は`generate_user_utterance`（cela_main.py:4700）と`call_expert`（cela_main.py:6086）の2箇所のみで、**`call_detector`（cela_main.py:4767〜）には一度も呼ばれていない**。Detectorが参照できるのは`agreements_text`（決定事項DB）と直近2件の会話・decisionのみであり、他ロール（facilitator/reflection/Expert/User AI）が既に認識しているescalated issueの存在をDetectorだけが知らないまま独立に判定を続けるため、他ロールが折り込み済みの懸念について同じ差し戻し判定を繰り返すリスクがある。2026-08-03、別AI（Cline/deepseek経由）によるコードベース全体レビューでも同一の指摘があり（`docs/design/back_log/BL-149_150_codebase_bugcheck_2026-08-03.md`）、コードを直接確認して事実に間違いないことを検証した上で実装に着手した。

**対応（実施済み）:** `call_detector`は独立した2つのLLM呼び出し（Pass 1: ドメイン妥当性レビュー`domain_prompt`、Pass 2: 数値監査`prompt`）を持つ2パス構成であることを確認。escalated issueは典型的にドメイン・前提レベルの懸念（労基法、実現可能性等）でありPass 1と意味的に最も適合すること、Pass 1の指摘が既存の`domain_findings_block`経由でPass 2へ伝播する設計があること、Pass 2は算術検算のみに意図的にスコープを絞っていることから、**注入はPass 1のみに限定**した。`escalation_pin`/`escalation_pin_block`を`domain_prompt`構築直前で計算し、他のDB由来コンテキストブロック（Freeze状況等）と並ぶ位置へ`call_expert`と同じ文言・条件分岐で埋め込んだ。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl123_detector_escalation_pin.py`（3件: `_build_escalation_pin_text`参照確認、Pass 1のみへの注入確認、条件分岐埋め込みの確認）追加。フルオフラインスイート600件Pass。実LLM再ドライランでDetectorがescalated issueを把握した上で判定していることの確認は次回待ち。

---

### BL-124: BL-086（`escalate_premise_concern`/`freeze_agreement`/`revise_goal`）がツールとして常時提供されているのに、まさに想定されたケースで一度も使われず`stagnant`→HALTに至った

**状態:** `open`（プロンプト誘導強化要、記録のみ）

**経緯:** `log/2026-07-28/2257`を`grep`し確認。BL-086（R5）で実装済みの前提エスカレーション・Freeze・ゴール改定ツール群は、User AIに常時`tools attached`として提供されていた（65, 2556, 3680, 4549, 6212行目等）にもかかわらず、**実行ログ（`🔧 [User AI] freeze_agreement 実行`等）は本ドライラン全体で一度も出現しない**。User AIは「30分待ち時間制約 vs 冬季・通信障害・昼休みの例外」という、まさにこの機構が想定する前提矛盾に直面しながら、通常の`write_agreement`（条件付き承認）で済ませてしまい、Freezeによる恒久ピン留めを使わなかった。その結果、同じ論点がDetectorに繰り返し`major`判定され続け、最終的に`stagnant`→HALTに至った（21524行目）。NVIDIA Nemotron 3 Ultra（free）はDeepSeekと比較し「この状況はエスカレーション経路を使うべきだ」という判断への誘導が効きにくい可能性がある（この日の1322ログレビューで確認した「nemotronは視座が高い対応をする」という仮説と併せて、モデルごとに誘導の効きやすさが変わりうる点は要注意）。

**対応（未着手）:** 同一論点で`write_agreement`の条件付き承認がN回（例:2回）以上繰り返された場合に`freeze_agreement`/`revise_goal`の使用を強く促す誘導をプロンプトに追加することを検討する。

**完了条件:** 誘導文言を実装後、実LLM再ドライランで同一論点の繰り返し条件付き承認が減り、適切な場面でFreeze/revise_goalが使われることを確認する。

---

### BL-125: `_resolve_task_transition`はissue_logの未解決状態を参照しておらず、フェーズ単位の足止めは実装されていない（全体停止の安全弁のみ）

**状態:** `done`

**基本設計:** [BL136_basic_design.md](BL-136/BL136_basic_design.md) Part D（BL-136と一体設計、Plan Modeで3体のExploreエージェントによる調査を経て確定。後日back_logフォルダ整理の際にこのセッションで復元・保存）。

**経緯:** ユーザー質問「issue未解決であればフェーズを超えられない仕組みは実装済みか」を受けて確認した時点では、`_resolve_task_transition`（BL-024の唯一の書き手）はphase/task遷移の唯一の書き込み口でありながら、`phase_id`/`task_id`がtask_planner確定済みリストに実在するかのみをチェックし、issue_logのopen/escalated状態は一切参照していなかった。存在したのは「特定フェーズだけ待たせる」スコープを絞った足止めではなく、「escalated issueが1件でもあれば議論全体を`stagnant`扱いにし、最終的に全体をhaltさせる」（BL-096）という粗い全体停止の安全弁のみだった。

その後、BL-134（Expertが24時間365日前提を無根拠に確定値化し、Detectorがmajorエスカレーションしたのに未解決のままtask_1_1→task_1_2の遷移が起きてしまった実インシデント）の分析から、このギャップが実害を伴うことが確認され、実装に着手した。

**対応（実施済み）:** `_get_blocking_issues_for_transition(conn, run_id, departing_task_id)`を新設し、`status='escalated' AND severity='major' AND last_seen_task_id=<離脱task> AND defer_to_task_id IS NULL/''`のissue_log行を問い合わせる。`_resolve_task_transition`の`next_task_id`適用直前でこれを呼び、該当issueがあれば`canonical_task_id`への書き込みを拒否して直前の`current_task_id`を維持し（既存の「存在しないtask_id」拒否と同じフェイルクローズパターン）、ブロックしたtopic一覧を`state["task_transition_blocked_issue_topics"]`へ記録する。次のUser AIターンで`_build_task_transition_blocked_notice`（`_build_escalation_resume_notice`と同型のone-shot注入パターン）がこれを消費し「なぜ遷移がブロックされたか、RESOLVEかDEFERのどちらかを呼んでから再度移行を指示してほしい」旨を明示する。BL-136のDEFER（`defer_to_task_id`設定済み）で明示的に先送りされたissueはブロック対象から除外し、「今すぐ解決」「明示的に将来のtaskへ先送り」のどちらかが済んでいれば遷移を許可する。

**完了条件:** `python -m py_compile`合格・`tests/test_bl135_issue_visibility_and_transition_gate.py`（BL-134実インシデント再現テスト含む）・関連クラスタ・フルオフラインスイート542件Pass済み。

---

### BL-126: BL-086の前提エスカレーションはExpertのリアクティブな経路に限定されており、Facilitator＋User AIがゴール・制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計

**状態:** `done`（Stage A〜D全て実装完了、D-1xx参照）

**実装内容（done、Stage A〜D）:**
1. **Stage A（goal_drafts versioning）**: `goal_drafts`テーブル・`apply_goal_patch`/`get_latest_goal_draft`を新設（whiteboard_drafts/plan_draftsと同型）。既存の反応的`revise_goal`経路（BL-086）にも先行適用し動作確認。
2. **Stage B（Detector目標変更レビューモード）**: `call_detector`に`review_mode: Literal["task_output","goal_change"]`を追加。`revise_goal`成功直後に`goal_revision_pending_review`をセットし、次の`user_detector`が§5の4判断基準（旧文が追記として保持されているか／理由づけの相応性／スコープ逸脱の有無／数値的最適性は評価しない）で監査する。既存の反応的経路にも適用。
3. **Stage C（Task Plannerのラン途中再構成）**: `task_planner_node`のガードを`(turn_count==1 and not phases) or state.get("plan_revision_reason")`へ緩和。新しい計画に含まれなくなった既存task_idは削除ではなく`phases_superseded`へ記録し`write_agreement(entry_type="Directive", action_type="SUPERSEDE")`で監査証跡を残す。再構成後もtask_plan_reviewer_nodeをスキップせず通す（既存の差し戻し上限ロジックを再利用）。
4. **Stage D（Facilitatorのツールループ化＋Essence Dialogueループ＋Reflection迎合監査）**: `write_agreement`に`entry_type="EssenceProposal"`を追加（facilitatorはProposedのみ許可）。`call_facilitator`をTHINK_TOOL/ESCALATE_PREMISE_CONCERN_TOOL/WRITE_AGREEMENT_TOOLを持つツールループへ変更（BL-109からの意図的な差し戻し）。`facilitator_node`がEssenceProposalの提起で`essence_dialogue_active`を開始し、`generate_user_utterance`直後のルーティングを条件分岐化（対話中は`user_detector`を経由せず`facilitator`へ直接戻る）。Userの承認（EssenceProposal UPDATE/Approved）で収束し`plan_revision_reason`をセットしてStage Cへ接続、または上限5ラウンドでタイムアウトして通常フローへ復帰。`call_reflection`に迎合（collusion）監査基準（転換の回数ではなく重大さに見合った理由づけの有無）を追加。

**検証:** 新規テスト4ファイル（`test_bl126_stage_b_goal_change_review_mode.py`6件、`test_bl126_stage_c_task_planner_reconfiguration.py`7件、`test_bl126_stage_d_essence_dialogue.py`16件、BL-131時に追加済みの基盤含む）+ 既存回帰テスト修正。`python -m py_compile`合格、関連クラスタ512件Pass。実LLM再ドライランでの本質対話フロー・ラン途中再構成の実動作確認は次回待ち。

**基本設計:** [BL126_basic_design.md](BL-126/BL126_basic_design.md)（`LineageState`追加フィールド、新規/変更ツール、グラフルーティング変更、`goal_drafts`テーブル、Detectorの目標変更レビューモード、Task Plannerのラン途中再構成、Reflectionの迎合監査基準、実装順序をBL-130/BL-131とあわせて一体設計）。

**追記（2026-07-29、`log/2026-07-29/1708`での再現）:** 本BLが対象とする問題が再度実害として観測された。`task_1_1_review`が11バージョンまで積み上がり（`phase_1_task_1_1_review_V7〜V11.md`）、Reflectionが最終的に`stagnant`と正式判定してFacilitatorへ差し戻した。Detector自体は毎回「本物の新しい欠陥」（シフト計算の符号反転、モンテカルロ誤差1000倍、要件で明示された山間部の対象除外等）を正しく検出しており、Detectorのレビュー精度そのものは機能しているが、本質的な目標（安全基準・エッジケース対応・代替予約手段・Phase2-5）への着手がゼロのまま単一task_idへ延々とリソースが投入され続けるという、本BLが解決しようとしているワークフロー上の欠落を裏付ける実例となった。

**経緯:** ユーザー発案。現行のBL-086（`escalate_premise_concern`/`revise_goal`）はExpertが個別タスク遂行中に前提矛盾に気づいた場合のみ発火するリアクティブな経路に限定されている。ユーザーが提案する「facilitatorとUser AIが数ラウンドかけてゴール・制約そのものを本質的に問い直す（例：オンデマンドバスである必然性、乗合・タクシー併用、需要集中時間帯の定時路線化、市街地はシニアカー補助、特区での自動運転タクシー活用等、解決策の形自体を作り直す）」プロアクティブな創造的議論モードは未設計。`revise_goal`が`state["goal"]`への部分パッチ（old_text/new_text、全文置換ではない）方式であることは、ユーザーが希望する「元文は変えずに注釈・本質からの気づきを付け足して永続化」という要件と親和性が高く、土台として再利用できる。低コストな実装ルートとして、既存のstagnant/drift検知で発火する`facilitator_node`を「Nラウンドの本質対話モード」に拡張し、合意が出たら`task_planner_node`を再実行してタスクツリーを作り直す流れが有力（新規サブシステムの新設より既存トリガー・既存ツール・既存再計画能力の組み合わせで済む）。R6構想との重複可能性がある。

**追記（2026-07-29、`log/2026-07-29/1322`レビューを踏まえた具体化）:** 本BLが想定する設計の必要性を裏付ける実例が1322ログで観測された。Facilitatorが「20%需要平準化が限界」等の前提矛盾を`escalate_premise_concern`で3件正式にエスカレーションした後、`task_1_1_review`という**task_plannerの正式なフェーズ・タスク計画に存在しないtask_id**の下で、Expertが244行・6バージョンにわたる本格的な「制約見直し要求書・ピボット案」を作成してしまった（関連: BL-131）。これはまさに本BLが解決しようとしている「本質対話→合意→task_planner再構成→正式タスク化」という順序が未整備なために、順序が入れ替わって(合意形成前に成果物だけが先行して)発生した現象と整理できる。ユーザーが具体化したフロー案:
1. Facilitator↔User AIが数ラウンド対話し方向性を模索（この間は成果物なし）
2. 方向が固まったらUserが承認：ホワイトボード化した目標を編集（旧目標は残しつつ注釈で追加、理由記載を厳守）
3. Detectorを通し確定させる（**ただしDetectorの通常の監査モードのまま通すと無駄な差し戻しリスクがあり、「目標変更の妥当性」と「通常のタスク遂行の妥当性」を評価軸として分離する必要がある**——この塩梅の設計が課題）
4. Task Plannerがタスク表を作り直す（必要部分を編集、旧タスクは消す、後続AIが誤解しないようにする）
5. 新たな目標に向けた作業を開始（ここで初めて`task_1_1_review`のようなタスクが正式にタスク化される）

あわせて、この文脈と密接に関連する2つの追加論点:
- **Expert→User相談チャネル**（BL-130として別途起票）：これまでUser→Expertへの一方向の指示（レビューはあるにせよ）だったが、Expertが成果物を出さずにUser AIへ質問・相談できる循環を追加したい。この相談の中で`escalate_premise_concern`を使ってもよい設計とする。
- **迎合（collusion）監査**：本質対話モード・相談チャネルいずれも、User AIとExpertが「なあなあ」に妥協していくリスクを内包する。これはReflectionが本来担うべき役割（長ラウンドのチャット履歴を見て、方針転換・妥協が本質からズレていないか、妥協に見合った理由づけがあるかを監査する）であり、無理に定量化しようとせず、D-094の設計原則（具体性は「手順」でなく「判断基準と罠」に持たせる）に沿って、Reflectionの既存プロンプトに「方針転換の重大さに見合った理由づけの有無」という判断基準（罠）を明記する形が妥当と考えられる。

**モデル挙動の観察（project memory候補）:** 同日の複数ログ比較から、「DeepSeek系は指示に対して一直線に対応する傾向、NVIDIA Nemotron 3 Ultraはより視座の高い対応（前提の疑問視・エスカレーション判断）が可能」という仮説が得られた。BL-122・BL-124で確認された「Nemotron使用時にリトライ・エスカレーション判断の挙動がDeepSeek使用時と明らかに異なる」という実測とも整合する。今後のドライラン比較・解釈の前提として記録しておく価値がある。

**対応（未着手）:** 上記フローと課題（Detectorモード分離、迎合監査基準の明文化）を含め、`要件定義.md`のF-10.5（前提破壊挑戦）との整合を確認した上で、別途Plan Modeで設計を詰める。

**完了条件:** 設計方針を確定し実装計画（Plan Mode）を立てた後、別途実装・テスト・実LLM再ドライランで確認する。

---

### BL-127: `write_agreement`のUPDATEがDB上は成功しても、ホワイトボード本体には反映されない（または反映確認に失敗する）ケースが実際に発生した

**状態:** `done`

**経緯:** `log/2026-07-28/1233`のDetector再検証で発見。需要試算の計算ミス（1月係数の適用漏れにより140人/日/−65%と誤記載、正しくは105人/日/−74%）についてExpertが`write_agreement`で`UPDATE`（`AG-1785214808321`）を実行し「修正が正常に適用されたことを確認しました」と自己申告したが、Detectorが再検証したところホワイトボード本文には旧値「約140人」「−65%」が3箇所とも**残存**していた。write_agreementがDB上はUPDATE成功と記録されるにもかかわらず、成果物本体（ホワイトボード）に反映されない、または反映確認に失敗するケースが実際に発生している。ログはDetectorが不整合に気づき再調査を始めた直後に途切れており、最終的にこの不整合が解消されたか未確認だった。

**原因特定:** `_commit_agreement_from_tool`（`cela_main.py`）のUPDATE分岐には、`entry_type="Deliverable"`かつ`edits`未指定・`decision_what`が200字以下の短文の場合にホワイトボード本体を意図的に上書きしない「保護」ブランチが存在する（H2踏襲、「承認コメント等の短文で既存の完全版を誤って上書きしない」という正当な仕様）。しかし従来はこの保護が発動したことをコンソール`print()`にしか出力しておらず、ツール呼び出し元（Expert）へは一切伝わらなかった。結果として、実際にホワイトボードへ反映された正常なUPDATEと、保護により何も変更されなかったUPDATEが、どちらも同一の`{"success": True}`として返っていた。Expertは「修正が正常に適用されたことを確認しました」という**短い確認コメント自体**をdecision_whatとして送っており、これがまさに保護仕様の対象（200字以下・edits未指定）に該当したため、皮肉にも「確認しました」という自己申告のUPDATE呼び出し自体が何も変更しない結果に終わっていた。

**対応（実施済み）:** `_commit_agreement_from_tool`の戻り値を`str | None`（error）から`tuple[str | None, str | None]`（`error`, `protected_warning`）へ拡張。保護ブランチ（短文UPDATE／実質的な変更なしUPDATEの2箇所）発動時に、具体的な理由（editsパラメータの使用を促す旨を含む）を`protected_warning`へ設定するようにした。`_write_agreement_impl`はこれを受け取り、`protected_warning`が設定されている場合は成功レスポンスに`"warning"`フィールドを追加（`success`自体はTrueのまま、ツール呼び出し自体は失敗していないため）。これにより、Expert/User AIは次のツール応答から「DB上は成功したが、ホワイトボード本体は変更されていない」ことに気づき、`edits`パラメータでの再試行や200字を超える全文送信へ切り替えられる。

**影響:** `_commit_agreement_from_tool`の唯一の呼び出し元である`_write_agreement_impl`（`cela_main.py:2083`）のみを更新。既存の直接呼び出しテスト3ファイル（`tests/test_bl073_directive_auto_resolve.py`・`tests/test_bl080_supersede_deliverable_whiteboard_writeback.py`・`tests/test_bl084_deliverable_task_id_identification.py`、計8箇所）を新しいタプル戻り値のアンパック（`err, _ = ...`）に合わせて修正。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl127_whiteboard_update_protected_warning.py`（6件、BL-127の実インシデントを模した短文UPDATE再現テスト含む）追加。フルオフラインスイート550件Pass。可能であれば同一シナリオ（Detectorが計算ミスを指摘→Expertが短い確認コメントのみでUPDATE）で再ドライランを行い、Expertが`warning`フィールドを見て`edits`での再送信に自己修正することを確認する。

---

### BL-128: Detectorの独立検算コメントがほぼ一言一句同一のまま複数ターンにわたり繰り返し出現しており、レビューの「独立性」が実質的に薄れているリスクがある

**状態:** `open`（記録のみ、優先度低）

**経緯:** `log/2026-07-28/1420`のレビューで発見。「独立検算：システム構築費1,800万円…数値矛盾・計算ミスなし」というほぼ一言一句同一の検算コメントが5659/5673/5705/6524/8375/8856行目等、複数ターンにわたり繰り返し出現している。真に毎回独立して再計算した結果が偶然一致しているのか、過去の検算結果をテンプレ的に使い回しているのかがログからは判別できない。

**対応（未着手）:** python_repl呼び出し自体のコード内容をターンごとに突き合わせ、同一コードの使い回しがないか機械的に検知する仕組みを検討する。

**完了条件:** 検知仕組みを実装し、Detectorの検算が実際に毎回独立して行われていることを確認する。

---

### BL-129: 長時間ドライランで、turn上限到達やHALT/完了メッセージなしにログが唐突に途切れて終了するケースが複数確認された

**状態:** `open`（原因切り分けが必要）

**経緯:** `log/2026-07-28/1233`・`1420`の両方で、ログがturn上限到達や明示的なHALT/完了メッセージなしに、あるノードの思考・ツール呼び出しの途中で唐突に途切れて終了している（1233は10552行目でDetectorの思考途中、1420は49427行目でExpertの`write_agreement`呼び出し直前）。プロセスのクラッシュ・OSレベルのタイムアウト・ログ書き込みの停止のいずれが原因か切り分けができていない。同様の唐突な中断は`log/2026-07-31/1129`（Detector監査思考の途中、22599行目）でも観測された。

2026-07-31、ユーザーから「何回か突然ログが途切れているのも、間違ってノートパソコンを休止状態にしたりしてしまったため」との説明があり、少なくとも一部（おそらく大半）はコード側のバグではなく、実行環境（ノートPCの休止状態への意図しない移行）が原因と判明した。プロセスのクラッシュ・OSレベルのタイムアウト等のコード起因の可能性は完全には排除されないが、優先度は当初より下がる。

**対応（未着手）:** 環境要因が主因と判明したため、恒久対応（プロセス生存監視・異常終了時のスタックトレース保存）の緊急性は低いと判断。今後同様の中断が休止状態と無関係に発生した場合のみ、コード側の原因切り分けに着手する。

**完了条件:** 原因を切り分けた上で対策を実装し、長時間ドライランが異常終了せず完走することを確認する。

---

### BL-130: Expertが成果物を出さずにUser AIへ質問・相談できる双方向チャネルが未設計（現状はUser→Expertへの一方向指示のみ）

**状態:** `done`（実装完了、D-100参照）

**基本設計:** [BL126_basic_design.md](BL-126/BL126_basic_design.md)（BL-126/BL-131と一体設計。§2に`ask_user_question`ツール仕様、§3に`expert_consultation_mode`時のDetector/Decision Extractorスキップ・ルーティング変更を記載）。

**経緯:** `log/2026-07-29/1322`レビューでのユーザー発案。現行の構造はUser AI→Expertへの指示（Detectorのレビューは挟むが）という一方向の会話にほぼ限定されており、Expert側から「この前提が不明瞭なので方向性を確認したい」といった、成果物を出さない質問・相談ができる循環が存在しない。ユーザーが提案する仕組み：Expertが質問だけを行いUser AIが回答する往復を経て、その後で成果物を作り上げる、という循環を許容する。この相談の中で`escalate_premise_concern`を使ってもよい設計とする。

ユーザーとの設計議論で以下を確認・整理:
- `round_count`は現状`generate_user_utterance_node`（cela_main.py:6322）でのみ加算されており、Detector/Reflection/Facilitatorは含まれない。したがって「質問ラウンド」を導入しても新しいカウンターは不要で、Expertが「これは質問である」と明示できる手段（新ツール、または既存`write_agreement`へのフラグ追加）を用意すれば、既存のround_count・グラフルーティングの枠組みでそのまま扱える。
- 焦点は「質問ラウンドの時、Detectorはどう振る舞うべきか」（成果物監査と同じ厳格さでレビューするか、もっと軽く流すか）という較正（BL-126の課題と共通）。

**実装内容（done）:**
1. 新規`ASK_USER_QUESTION_TOOL`/`_ask_user_question_tool_impl`（expertロールのみ許可、`question_text`/`blocking_reason`必須）を追加し、`call_expert`のツールリスト・プロンプト文言（固定版・`light_system_prompt`版の両方）へ反映。
2. `_LAST_ASK_USER_QUESTION`／`get_last_ask_user_question()`（`_LAST_GOAL_REVISION`と同型のブリッジ）を新設し、`query_AI`の既存リセット処理に合流。
3. `LineageState`に`expert_consultation_mode`/`expert_pending_question`を追加。`expert_node`がツール呼び出しの有無に応じてセット/明示的にリセット。
4. `detector_node`に軽量パス分岐（`target_role=="assistant"`かつ`expert_consultation_mode`の場合、`call_detector`のLLM呼び出し自体をスキップし`constraint_issue="none"`固定）。
5. `route_after_expert_detector`に新分岐（`expert_consultation_mode`時は`expert_decision_extractor`を経由せず`generate_user_utterance`へ直行）。グラフの宣言済みエッジにも追加。
6. `generate_user_utterance`（§13.2のモード切替設計）に質問提示の固定文面を追加、`generate_user_utterance_node`が回答生成直後にフラグを消費・リセット。

**検証:** 新規`tests/test_bl130_ask_user_question.py`（15件、ツール権限・必須項目・dispatch経由呼び出し・`expert_node`のフラグ設定/リセット・`detector_node`の軽量パス/通常経路の両方・グラフエッジ存在・プロンプト文言注入を検証）。`python -m py_compile`合格、関連クラスタ256件Pass。実LLM再ドライランでの相談チャネルの実動作確認は次回待ち。

---

### BL-131: task_plannerの正式なフェーズ・タスク計画に存在しないtask_id（`task_1_1_review`等）でwrite_agreement/whiteboardが作成されてしまう構造的リスク

**状態:** `done`（実装完了）

**基本設計:** [BL126_basic_design.md](BL-126/BL126_basic_design.md) §2.5・§2.6（BL-126/BL-130と一体設計）。

**経緯:** `log/2026-07-29/1322`レビューで発見。Facilitatorが「制約見直し要求書・現実的ピボット案」の作成を`task_1_1_review`という新設タスクとして提案し、Expertがこれをそのまま実行して244行・6バージョンにわたる成果物を作成した。しかし`task_1_1_review`はtask_planner側の正式なフェーズ・タスク計画（`state["phases"]`）には一度も登録されておらず、`write_agreement`/ホワイトボード作成時にtask_idが実在の計画と照合されずに任意の文字列で成果物が作れてしまうことが判明した。`log/2026-07-29/1708`では同じ`task_1_1_review`が11バージョンまで積み上がる形で再現し、早期実装の必要性が裏付けられた。

**実装内容（`done`）:**
1. **前提: TOOL_DISPATCHのstate受け渡し化**（`cela_main.py:2177`付近）。ツールハンドラは従来`args`のみを受け取り`_CURRENT_RUN_ID`/`_CURRENT_TASK_ID`/`_CURRENT_PHASES`等のモジュールレベルglobal経由でしか実行時コンテキストを得られなかった（R2実装時からの技術的負債、BL-099）。`_query_AI_live`/`query_AI`/`_query_and_parse_with_retry`に`state`パラメータを追加し、ツール実行箇所を`handler(args, state)`に変更。`TOOL_DISPATCH`の全15エントリを`(args, state=None)`の2引数ラムダへ統一（`state`未指定時は既存globalへフォールバックし後方互換を維持）。`call_expert`/`generate_user_utterance`/`call_detector`（既にstateを持つノード）は`state=state`を追加するのみ、`call_resource_arbiter`/`call_integrator`/`call_task_planner`/`call_reviewer`/`call_goal_essence_analyst`/`call_task_plan_reviewer`（従来stateを受け取っていなかった6関数）には新規`state`パラメータを追加し、呼び出し元ノードから伝播させた。
2. **task_id/phase_id実在チェック**: `_write_agreement_impl`に、`entry_type in ("Directive","Deliverable")`の場合`task_id`が`state["phases"]`（`_find_task_by_id`で検索）に実在するか、実在しなければ`state["pending_task_ids"]`（新規`LineageState`フィールド、BL-126のFacilitator対話が正式採用前に仮登録する許可リスト用に先行追加）に含まれるかを検証するチェックを追加。いずれにも該当しなければエラーで拒否する。`entry_type="Decision"`は対象外（タスクに紐づかない全体決定もあるため）。
3. **`get_latest_whiteboard`/`get_latest_plan_draft`のtask_id単独検索化**: 従来`(phase_id, task_id)`の組でしか検索しておらず、誤ったphase_id指定で既存版が「該当なし」と誤判定されバージョンが1から再スタートする事故（1708ログのtask_1_1_review V9で観測）の直接原因だった。`plan_drafts`側に既存の`get_latest_plan_draft_by_task_id`（task_idはrun_id内で一意という命名規約を前提に検索）と同じ方式へ統一し、`phase_id`は食い違い検知の警告用途にのみ残した。
4. **`target_topic`必須化**: `entry_type != "Deliverable"`のUPDATE/SUPERSEDEで`target_topic`省略時に`topic`（今回の新しい値）へ暗黙フォールバックしていた（実質的な空振り更新になるバグ）のを、必須パラメータとして拒否するよう変更。

**検証:** 新規`tests/test_bl131_write_agreement_task_id_validation.py`（9件、task_id実在チェック・Decision除外・pending_task_ids許可・phase_id誤指定でのバージョン継続・target_topic必須化を検証）。既存の`tests/test_r3_smoke.py`のうち3件（BL-131導入前は任意のtask_idで成果物作成できていたテスト）を`pending_task_ids`経由で許可する形に更新。`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_r3_smoke.py`のTOOL_DISPATCH内部実装依存の回帰テスト2件を新しい呼び出し規約（`handler(args, state)`）に合わせて更新。`python -m py_compile`合格、関連クラスタ166件Pass。実LLM再ドライランでの`task_1_1_review`型事故の再発防止確認は次回待ち。

**完了条件:** BL-126の設計確定と合わせて対応方針を決定し、実装後にtask_planner未登録のtask_idでの成果物作成が防止されることを確認する。

---

### BL-132: `detector_node`が呼び出しのたびに全決定履歴を再取得・再出力しており、ログ肥大化とBL-121の原因切り分けを妨げていた

**状態:** `done`

**経緯:** BL-121（`log/2026-07-29/0751`の「halt後も処理が継続しているように見える」問題）の再調査中に、`detector_node`（`cela_main.py:6972`付近、`user_detector`/`expert_detector`双方が指す共通関数）の末尾で以下のコードを発見した:

```python
this_turn_decisions = get_decisions_from_db(_conn, state["run_id"])[1:]
for d in this_turn_decisions:
    print(f"  [{d['who']}]")
    ...
```

変数名は「this_turn_decisions」（このターンの決定）だが、実際には`get_decisions_from_db(...)[1:]`＝run開始2件目以降の**全決定履歴**であり、ターン単位のスコープ管理が一切されていなかった。detector_nodeはuser_detector/expert_detectorとして1run中に非常に高頻度で呼ばれるため、呼ばれるたびに毎回それまでの全決定を丸ごと再出力しており、(1)ログがrun進行とともにO(n^2)的に肥大化する、(2)過去のあらゆる決定（BL-121で観測された「強制停止」を含む）が呼び出しのたびに再表示され続け、実際に何回・いつ発生した事象なのかがログの見た目だけからは判別できなくなる、という実害があった。BL-128（「同一検算コメントが複数回出現」）も同一バグが主因である可能性が高い。

**対応（実装完了）:** 全履歴の再取得・再出力をやめ、この関数呼び出し自体が直前に作成した`decision`（1件のみ）を出力するよう変更した。DB再取得も不要になった。

**完了条件:** `python -m py_compile cela_main.py`合格、関連クラスタ（`test_bl093_d074_auto_reasoning_enforcement.py`/`test_bl093_think_tool_scratchpad.py`/`test_r3_smoke.py`/`test_bl104_project_plan_toc_and_prompt_reorder.py`）132件Pass。実LLM再ドライランでのログ肥大化解消・BL-121原因切り分けの効果確認は次回待ち。

---

### BL-133: `test_detector_no_false_positive_within_cap`（B.5.1非退行、D-011）が層2リトライ枯渇によるフェイルクローズで3/3失敗し、モデルの誤判定と誤認されるところだった

**状態:** `open`（診断ログ追加のみ完了、恒久対応は次回再現待ち）

**経緯:** 2026-07-30、`tests/test_f26_detection.py::test_detector_no_false_positive_within_cap`（上限内の正当な数値差をDetectorがmajorと誤判定しないことを検証する非退行テスト）が3試行とも`constraint_issue="major"`で失敗した。2026-07-28にも一度単発でflakyな失敗が観測されていたが、当時は単体再実行で合格したため「モデル判定のばらつき」と判断し記録のみに留めていた（issue_backlog.mdの2026-07-28付changelog参照）。

今回、失敗したテストの`comment`フィールドを実際に確認したところ、モデルが本当に「major」と誤判定していたのではなく、`comment='(ドメイン妥当性レビューのJSON解析失敗のためフェイルクローズしました)'`——すなわち`call_detector`の第1段（ドメイン妥当性レビュー）が`_query_and_parse_with_retry`の層2リトライ（`max_retries=2`＝初回込み計3試行）を丸ごと使い切ってもJSONを一切パースできず、D-005の設計原則（層2リトライを使い切った場合はフェイルオープンではなくフェイルクローズ＝major）通りに動作した結果だと判明した。これはBL-012/D-011が本来想定していた「モデルが数値を誤判定する」という失敗モードとは全く別種であり、2026-07-28の1回目も同一のパース失敗だった可能性が高い（当時`comment`の中身を確認せずに「ばらつき」と結論づけたのは誤りだった）。

D-005のフェイルクローズ原則自体（安全側は差し戻し）は正しく、変更すべきではない。しかし**なぜ層2リトライの3試行すべてが失敗したのか**（(a) モデルが最終的なJSON回答を一度も生成しないままツールループがMAX_TOOL_ITERへ達した、(b) モデルが説明文のみでJSONを一切含まない応答を返し続けた、(c) auditor側API（DeepSeek V4 Flash）の一時的な不調、のいずれか）は未診断のままであり、`_query_and_parse_with_retry`の従来のログ（「JSON判定パース失敗を検知」とだけ出力）では原因の切り分けができなかった。

**対応（今回実施）:** `_query_and_parse_with_retry`のリトライ失敗ログに、そのとき実際に得られた生レスポンス（`res`）の冒頭300字のプレビューを追加した。ロジック自体（フェイルクローズの判定・リトライ回数）は変更していない。

**完了条件:** `python -m py_compile cela_main.py`合格、`tests/test_bl089_json_fence_and_failclosed_review.py`10件Pass（ログ出力のみの変更のため既存挙動への影響なし）。次回この非退行テストが再びmajorになった際、追加した生レスポンスプレビューから(a)〜(c)のいずれが真因かを特定し、必要ならプロンプト調整・`max_retries`見直し等の恒久対応を行う。

---

### BL-134: Expertがゴール文にない「24時間365日」監視前提を無根拠に確定値化し、Detectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった

**状態:** `open`（記録のみ、対応方針は次回スコープ確定後）

**経緯:** `log/2026-07-30/1236`（BL-120/BL-126 Stage A-D/BL-130/BL-131実装後、初のドライラン）のレビューで、ユーザーが「24時間365日×2名体制」という前提そのものがおかしいのではと指摘。ログを確認したところ、ゴール文は「遠隔監視オペレーター（最低2名常駐）」としか要求しておらず、運行時間帯は「8:00〜20:00」（`operating_hours_start`/`operating_hours_end`として制約テーブルにも明記済み、20:00〜翌8:00は「運行外」と明言）に限定されている。にもかかわらずExpertは「常時2名常駐」を無根拠に「24時間365日」体制と一般化し、以下の値を`confidence="confirmed"`として確定させた:

- `remote_operator_min_count_legal`（労基法遵守後の法的最低要員数）: 10〜11名
- `remote_operator_cost_legal`（年間人件費）: 41,250,000〜61,875,000円

この24時間前提の人件費が単独で年間維持費上限3,000万円を超過することが「CONF-02: 致命的」な矛盾として`constraint_issue="major"`判定の根拠にもなっていた。もし運行時間帯（12時間/日）のみを前提にすれば、必要人時は17,520人時/年→8,760人時/年へ半減し、必要人数もおよそ半減する可能性が高い。

**この疑義は`issue_log`に記録されていた**（issue `detector_observation_no_task`、`severity="major"`、`status="escalated"`のobservationsに含まれる一文）:
> 「遠隔監視オペレーター『常時2名常駐』を24h365日で試算（10名必要）しているが、運行時間は8-20時の12hのみ。『常駐』の解釈が曖昧で、実態に合ったシフト設計なら要員半減の可能性。」

Detectorの内部思考ログ（python_repl検算過程）にも「12h/dayなら8,760人時/年→6名で足りるのでは、大きな差」という同旨の検討が残っている。つまりシステムは一度この矛盾に気づいていた。

**訂正（本セッション後半で判明）**: 上記のissue行は`raised_by='detector_auto'`（`detector_node`の機械的バックアップ書き込み、observations長≥30字なら`constraint_issue`の値に関わらず常に`severity='minor'`で起票）で、`occurrence_count=11`という再発回数によって機械的にmajor/escalatedへ昇格したもの（D-079/D-080の「同じtopicが繰り返し検出される＝未解決のまま何度も見つかっている」ことを昇格条件とする設計は意図通り）。24h/365dの一文は、その汎用バケツdescription（10件超の気づきをまとめて溜め込んだもの）の中の1項目に過ぎない。一方、`task_1_2_remote_operator_legal_vs_requirement_gap`（`raised_by='user'`、`occurrence_count=1`で最初からseverity='major'指定）は、User AI自身がこの懸念をmajorと判断して一発でCREATEしたもの（chat_history_window/expert_history_windowを過ぎると消えてしまう指摘を書き残すためのissue_logの意図通りの用法）。いずれにせよ、「Detectorのconstraint_issue=major判定（差し戻し）とissue_logへの書き込みは別経路で自動連動していない」ことが判明した。

**しかし**、これらのissueは`resolved_by`/`resolved_at`が空のまま未解決（open/escalated）で放置され、その後もUser AIはtask_1_1を承認し、task_1_2（M/M/cキューイング解析）へと進行させてしまった。24時間前提の`confirmed`値は訂正されないまま次工程に引き継がれている。

**影響:** F-2.6/BL-033が本来防ごうとしている「根拠のない前提を確定値として扱う」パターンが、監査（Detector/User AI）で検知・記録はされたのに是正フロー（issue解決・前提の再確認）に接続されず、そのまま後続タスクへすり抜けかけた実例。severity=majorでescalatedされたissueが、実際にはタスク進行を一切ブロックしていない（BL-125が指摘した「issueの未解決状態がフェーズ/タスク遷移を止めない」という既知のギャップと同根）。

**対応（全て実施済み）:**
1. **実施済み（BL-125/BL-136）**: severity="major"でstatus="escalated"のissueが未解決・未先送りのまま該当タスクの次タスクへの進行を許してしまう現状のギャップに対応した。`_resolve_task_transition`に`_get_blocking_issues_for_transition`によるゲートを追加し、離脱しようとしているtaskに紐づく未解決issueがあれば遷移をブロックする（BL-136のDEFERで明示的に先送り済みのものは許容）。あわせて、issue_logのstatus='open'（minor）行も毎ターン可視化し（従来はescalated行のみ）、escalated行についてもBL-086同様「今回の発言内で必ずRESOLVEかDEFERを呼んでください」という強制文言を追加した（詳細はBL-136参照）。
2. **実施済み（D-110）**: Expertが「最低N名常駐」のような部分的な要件を、運行時間外にまで拡大解釈して確定値化する際、その拡大解釈の根拠をゴール文中の記述に明示的に求める罠（ピットフォール）注記を`call_expert`へ追加（D-094の3層モデル路線）。根拠が無い場合はconfidence="provisional"として扱いwrite_issueで記録するよう指示。あわせて`generate_user_utterance`のドメインレビューチェックリストにも同様の確認項目を追加し、User AI側でも拾えるようにした。
3. **調査完了・変更不要と判断（D-110）**: `call_detector`のドメイン妥当性レビュー基準を確認したところ、「情報が不足していて確認できないことをmajorの根拠にしてはいけない」という制約が意図的に設けられており、これはBL-012/BL-133が守る「モデルの誤検知を過度に許容しない」という設計と表裏一体（非退行テスト`test_detector_no_false_positive_within_cap`で保護済み）と判明。24h/365d問題はまさに情報不足型の疑義であり、observationsに回ったのは設計通り。真の問題（observations→issue_logが是正フローに繋がっていなかったこと）は候補1（BL-125/BL-136）で既に解消済みのため、判定基準自体の変更は見送った。

**完了条件:** 候補(b)はBL-125/BL-136として実装・テスト（`tests/test_bl136_issue_visibility_and_transition_gate.py`のBL-134再現テスト含む）済み。候補(a)は`tests/test_bl134_unsupported_generalization_guard.py`（3件）で実装・テスト済み。候補(c)は変更不要と判断（同テストファイルに判定基準が変更されていないことを確認する非退行テストを含む）。`python -m py_compile`合格、フルオフラインスイート553件Pass。可能であれば同一シナリオで再ドライランを行い、Expertが拡大解釈の根拠明示・confidence="provisional"化を実際に行うことを確認する。

---

### BL-135: `ask_user_question`の`blocking_reason`がUser AIの相談応答プロンプトに埋め込まれていない

**状態:** `done`

**経緯:** ユーザー依頼により、BL-086（`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`）およびBL-130（`ask_user_question`）の新規ツール定義・各ロールへのオリエンテーション文面の品質をレビューした。`ESCALATE_PREMISE_CONCERN_TOOL`系のdescriptionは誤用を具体的に予防する記述（一般的な泣き言としては使えない、スコープ外への越権は許可されない等）で書かれており、`call_expert`・`generate_user_utterance`双方のオリエンテーションもescalate_premise_concernとask_user_questionを明確に対比して説明できている（`cela_main.py`:4868-4931、6414-6489）。

その中で1点、`ASK_USER_QUESTION_TOOL`（`cela_main.py`:1695-1721）の`parameters.required`に`question_text`と並んで`blocking_reason`（なぜ現在のタスクのacceptance_criteriaを前進できないブロッキング理由か）が含まれているが、`generate_user_utterance`のBL-130相談応答モード分岐（`cela_main.py`:6481-6489）は`state["expert_pending_question"]`（question_textのみ）を埋め込むだけで、blocking_reasonに相当するstate値・プロンプト埋め込みが存在しない。`expert_node`側（`cela_main.py`:7290-7295）でも`_ask_q["question_text"]`のみ`state`へ反映しており、`_ask_q["blocking_reason"]`は取得されずに捨てられている。

**影響:** Expertはツール呼び出し時にblocking_reasonの記入を必須で求められるが、その内容を実際に見て判断すべきUser AIには渡らない。結果としてUser AIは「本当に前進不可能な質問か、単なる確認のためだけの質問か」を判断する材料（Expert自身の申告理由）なしに、質問文だけを見て回答することになる。ただし、レビュー対象とした複数ドライラン（`log/2026-07-30`系列）では`ask_user_question`自体が一度も呼ばれておらず、現時点で実害が顕在化した事例は未確認。

**対応（実施済み）:** 2026-08-03、別AI（Cline/deepseek経由）によるコードベース全体レビューでも同一の指摘があり（`docs/design/back_log/BL-149_150_codebase_bugcheck_2026-08-03.md`）、ユーザーが即効性項目として実装を選択。調査の結果、`_ask_user_question_tool_impl`は既に`blocking_reason`を`_LAST_ASK_USER_QUESTION`へ正しく格納しており、`get_last_ask_user_question()`もそれを含む辞書を返す設計だったため、ツール側の変更は不要と判明（欠けていたのは`state`への反映と表示のみ）。`LineageState`へ`expert_blocking_reason: str`を追加（`expert_pending_question`の直後、初期state辞書にも追加）。`expert_node`が`state["expert_blocking_reason"] = _ask_q["blocking_reason"] if _ask_q else ""`を`expert_pending_question`と同じ行の直後に追加。`generate_user_utterance_node`の消費・リセット箇所（`expert_consultation_mode`/`expert_pending_question`のリセットと同じ場所）に`expert_blocking_reason`のリセットも追加。`generate_user_utterance`のBL-130相談応答モードのプロンプトへ、`質問: {state['expert_pending_question']}`の直後に`理由: {state.get('expert_blocking_reason', '')}`を追記。

**完了条件:** `python -m py_compile`合格。`tests/test_bl130_ask_user_question.py`へ4件のアサーション追加＋新規テスト1件（計5件変更）。フルオフラインスイート600件Pass。`ask_user_question`が実際に呼ばれるドライランで、User AIの応答プロンプトにblocking_reasonが表示されていることの実LLM確認は次回待ち。

---

### BL-136: issue_logが「起票されるが解決されない」状態だった（可視性・強制力の非対称性）

**状態:** `done`

**基本設計:** [BL136_basic_design.md](BL-136/BL136_basic_design.md)（Part A〜D、BL-125と一体設計。Plan Modeで3体のExploreエージェントによる調査を経て確定。後日back_logフォルダ整理の際にこのセッションで復元・保存）。

**経緯:** ユーザー指摘「前まではissueが活発に使われていたのに今回はあまり活用されていない。たまたまか？」を受けて調査した。`log/2026-07-30/1236`の実行時DB（`cela.db`）を`run_id`で集計したところ、issue_logに7件のissueが起票されていたが（severity=major/status=escalated 3件、severity=minor/status=open 4件）、`resolved_by`/`resolved_at`が埋まった行は**0件**だった。timestampはturn 1〜3にわたって断続的に発生しており、序盤に集中していたわけではない。

コードを確認したところ、2点の設計上の非対称性が原因と判明した:
1. **可視性の非対称**: `_build_escalation_pin_text`は`status='escalated'`行のみを毎ターン`call_expert`/`generate_user_utterance`へ自動注入していたが、`status='open'`（minor）行は`read_issues`を能動的に呼ばない限り一切見えなかった。
2. **強制力の非対称**: BL-086の前提エスカレーション（`escalate_premise_concern`）には`_get_open_escalations_text`が「判断を先送りせず、今回の発言内で必ず解決してください」という明示的な強制文言＋具体的なツール名を伴って毎ターン注入されるのに対し、issue_logのRESOLVE指示は「解消していれば明示的にクローズしてください」という条件付き・任意の文面に留まり、強制力がなかった。

BL-134の実インシデントを再検証する過程で、当初「Detectorがmajorエスカレーションした」としていた説明が不正確だったことも判明した（`raised_by='detector_auto'`の汎用バケツ行がoccurrence_count>=2の再発回数により機械的にescalated化したものと、`raised_by='user'`が最初からmajor指定でCREATEしたものの2種が混在していた）。この機械的昇格自体はD-079/D-080の意図通りの設計（「同じtopicが繰り返し検出される＝未解決のまま何度も見つかっている」ことを昇格条件とする）であるとユーザーに確認した。

**対応（実施済み）:**
- **(A) minor（open）issueの可視化**: `_get_open_issues`/`_build_open_issue_pin_text`を新設し、`call_expert`・`generate_user_utterance`双方へ`status='open'`行も参考情報として（強制色のない`ℹ️`ラベルで）毎ターン注入する。
- **(B) issue_logへのDEFER操作追加**: `write_issue`に`action_type="DEFER"`を追加（userロールのみ許可）。`defer_to_task_id`（必須、実在task_idチェック付き）・`defer_reason`（必須）を指定すると、issue_logの`status`は変更せず`defer_to_task_id`列（新設）のみ更新し、既存の`_append_deferred_note_to_plan`（BL-082）をそのまま再利用して対象taskの計画文書へも申し送りを追記する。BL-082の「申し送り」（Directive/status=Deferred）と全く同じ思想を流用し、「今すぐ解決」と「明示的に将来のtaskへ先送り」の二択をUser AIに与えることで、強制解決一辺倒による無期限ブロックを避けた。
- **(C) 強制解決文言の追加**: `_get_forced_escalated_issues_text`を新設し、`status='escalated'`かつ`defer_to_task_id`未設定の行について、BL-086の`_get_open_escalations_text`と同型の「write_issue(RESOLVE)で解決するか、write_issue(DEFER)で対応予定のtaskを明示してください。理由なく放置することはできません」という強制文言を`generate_user_utterance`へ注入する（既存の受動的pinとは別立て。RESOLVE/DEFERを呼べるのはuserロールのみのため、Expertへは注入しない）。
- **(D) BL-125（タスク遷移ゲート）**: 上記(A)(B)(C)と合わせて実装。詳細はBL-125参照。

**影響:** F-2.6/BL-033/BL-134が指摘した「監査で検知はされたのに是正フローに乗らずすり抜ける」問題の根本原因（issue_logの可視性・強制力不足）に対応した。今後のドライランで実際にRESOLVE/DEFERの呼び出し率が改善するかは、次回以降の実行ログで検証が必要。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`（28件）・既存クラスタ（BL-096/082/086）・フルオフラインスイート（`pytest tests/ -q --ignore=tests/test_f26_detection.py`）542件Pass済み。可能であれば同一シナリオで再ドライランを行い、issueのRESOLVE/DEFER呼び出し率が改善することを確認する。

---

### BL-137: `_apply_text_edits`が非dict要素を含む`edits`で未捕捉クラッシュし、`run_ai_vs_ai_loop`全体が停止した

**状態:** `done`

**経緯:** BL-136実装直後の実ドライラン実行中に、以下のトレースバックでプロセス全体がクラッシュした。

```
File "cela_main.py", line 3965, in _apply_text_edits
    old_text = e.get("old_text", "")
AttributeError: 'str' object has no attribute 'get'
```

`generate_user_utterance`内でUser AIが`revise_goal`ツール（BL-086、`edits`パラメータ必須）を呼び出した際、LLMが`edits`配列の要素として`{old_text, new_text}`形式の辞書ではなく生文字列を返したことが直接原因。`_apply_text_edits`はこの入力形状を一切検証しておらず、`e.get(...)`がそのまま例外を送出していた。`_apply_text_edits`は`revise_goal`だけでなく`write_agreement`のDeliverable/Decision UPDATE経路（`cela_main.py:1921`付近）とも共有されている関数のため、Expert側の`write_agreement`呼び出しで同様の入力があっても同じ経路でクラッシュしうる、より一般的なリスクだった。

**影響:** ツール呼び出し1回の入力不備が、そのツール呼び出しへのエラー応答に留まらず、`run_ai_vs_ai_loop`全体（LangGraphの`app.stream()`ループ）を未捕捉例外で停止させていた。長時間ドライランがこの1点の脆弱性で全損するリスクがあり、F-2.6/BL-033が目指す「フェイルクローズだが継続可能」という設計原則からの逸脱だった。

**対応（実施済み）:** `_apply_text_edits`（`cela_main.py:3949`）のループ先頭に`isinstance(e, dict)`チェックを追加。非dict要素があれば例外を送出する代わりに、`edits[{i}]: old_text/new_textを持つオブジェクト（辞書）である必要がありますが、{type(e).__name__}型の値が渡されました。`という具体的なエラー文字列を返す（既存の`old_textが空です`チェックと同じフェイルクローズ・ツールループ内自己修正可能パターン）。`edits`自体が文字列の場合（文字ごとにイテレートされる）も、最初の要素で同じチェックに引っかかり安全に停止する。

**完了条件:** `python -m py_compile`合格。回帰テスト2件（`tests/test_r4_smoke.py::test_apply_text_edits_non_dict_edit_item_returns_error_without_crashing`・`test_apply_text_edits_non_dict_edit_item_among_valid_ones_returns_error`）追加。フルオフラインスイート544件Pass。

---

### BL-138: 自己改変的CELA（自らのLangGraph構造を継続改良し次世代へ引き継ぐ構想）は、改変ループの外側に固定監査層を置かない限り評価基準自体がドリフトする

**状態:** `open`（設計相談中、思いつきレベルの構想の記録のみ、実装は未着手）

**経緯:** Sakana AI（進化的モデルマージ・集団知能）の仕組みについての雑談を発端に、CELAとの設計思想上の共通点（単一巨大モデルに頼らない複数専門ノードの協調、Decision Lineageによる経緯保持、反復改善）についてユーザーとAIで議論した。その延長でユーザーが「CELAに自己のLangGraph構造そのものを継続的に自己改良させ、改良されたCELAがさらに次世代のCELAを改良する」という再帰的自己改変の実現可能性を提起。具体案として、各ノードで異なるAIモデルを相談役として呼び出し多様な視点を集め、得られた洞察（残したいこと・こうありたい姿）を自らのシステムプロンプトへ書き込んで「自らの個性」を形成していく、という仕組みも示された。AIは技術的には既存部品（LangGraphのノード分割、ファイルI/Oツール、複数モデル呼び出し、Decision Lineageの記録思想、[[BL-086]]のFreeze機構）の延長で構築可能と回答しつつ、再帰的自己改変には「評価基準自体がドリフトする」という本質的リスクがあり、Sakanaの進化的マージも同じ課題をfitness関数の人間側固定で回避している、と類推を提示した。ユーザーはこの指摘に対し、「これは仮定の話ではなく、まさに今CELA自身で起きていることだ」と応答。AIが捏造・無根拠に確定値化した数字が後続の議論・判断へ連鎖的な影響（バタフライ効果）を与えている実例（[[BL-134]]の「24時間365日」体制への無根拠な拡大解釈、[[BL-036]]/[[BL-037]]の財務・需要数値ドリフト、[[BL-033]]の検算未実施の虚偽申告）が既にissue_backlog上に複数存在しており、これが「改変ループの外側に固定された監査層が必要」という設計原則の実例的裏付けになる、という指摘だった。

**影響:** 現時点では実装対象ではなく、将来CELA自体のアーキテクチャ改良（ノード構成・プロンプト設計）を自動化・自己改変的に進める構想が持ち上がった際に、必ず踏まえるべき設計制約として記録する。具体的には、①自己改変ループが「良し悪しを判定する評価基準・監査ロジック」自体を改変対象に含めてはならない（評価者は系譜の外に固定する）、②各世代の変更は人間承認ゲート（AGENTS.md §8「ユーザー指示なしの自律実装の禁止」）を経ずに次世代へ継承してはならない、③ドリフトの実例（[[BL-134]]等）が示す通り、監査ノード自身の指摘が実際に是正フローへ乗るところまでを機械的に保証する仕組み（[[BL-125]]/[[BL-136]]の遷移ゲート相当）がない限り、自己改変の"賢さ"だけを強化しても同じすり抜けが再生産される。

**検討事項（未決定）:** 実装に進める場合は、まずコンセプト文書（例: `docs/design/self_evolving_cela_concept.md`）として①固定監査層の設計、②世代間diffのgit/人間レビューでの承認ゲート、③複数モデルを相談役として呼ぶ構成、④得られた洞察をシステムプロンプト/ペルソナへ反映する保存先、を個別に設計してから着手する。

**決定者:** t-momose（構想提起、記録の指示）、Claude Sonnet 5（技術評価・ドリフトリスクの指摘）

**関連:** [BL-086](#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-134](#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[decision_lineage.md 論点89](../decision_lineage.md)

---

### BL-139: `decision_extractor_node`のtransition抽出がLLM出力の1項目に依存しており、明示的な次タスク指示があっても`current_task_id`が更新されないことがあった

**状態:** `done`

**経緯:** `log/2026-07-31/0908`レビューで発見。`checkpoint.json`の最終状態が`current_task_id: "task_1_2"`のままなのに、対話ログ（`log_with_prompt.md`）では同日15:04:19時点で既にtask_1_2が承認されtask_2_1着手指示が明示的に記録され（decision_extractor No.61/62）、以降数百ターンにわたり対話がtask_2_1を扱い、`whiteboards/`にも`phase_2_task_2_1_V12〜V14`まで実際に書き込まれていた（`write_agreement`等のツール呼び出しはtask_idを引数で明示的に渡すため、`current_task_id`ポインタとは独立に書けてしまう）。

`_resolve_task_transition`（BL-024の唯一の書き手）は`call_decision_extractor`の単一LLM呼び出しが返す巨大なJSON出力の一項目`advances_to_task_id`のみに依存しているが、当該ターンではUserの発言に「次タスクtask_2_1への着手指示」が明示され、`extracted_events`自体にはtask_2_1向けのDirective（`action_type="CREATE"`, `entry_type="Directive"`）が正しく抽出されていたにもかかわらず、トップレベルの`advances_to_task_id`だけがnullのまま返っていた。`_resolve_task_transition`の遷移完了（`➡️`）・拒否（`⚠️`/`🛑`）いずれの`print`ログも、`log/2026-07-31/0908`・`log/2026-07-30/1236`の両run全体で一件も出現せず、遷移処理自体が一度も成立していなかったことを確認した。

**影響:** `current_task_id`依存の全機構（BL-023の`acceptance_criteria`チェック、`_get_current_task`が返すタスク定義等）が、対話の実態と乖離した誤ったタスクの基準を参照し続けていた。BL-125（未解決issueによる遷移ゲート）も、そもそも遷移が一度も試行されなければ検証機会自体がなく、無関係に見えていたが実際は前段の本バグに起因していた。

**対応（実施済み）:** `decision_extractor_node`（`cela_main.py`）内、`_resolve_task_transition`呼び出し直前に、抽出済み`extracted_events`の中に現在タスク（`departing_task_id`）と異なる有効な`task_id`を持つDirective（`entry_type="Directive"`かつ`status != "Deferred"`）があれば、`transition`の代替シグナルとして採用してから渡すフォールバックを追加した（BL-096の自動起票と同型の安全網）。`status="Deferred"`（BL-082の明示的先送り）は「今は移行しない」という意思表示のため除外する。対象は`target_role="user"`の抽出のみに限定（Expert自身はタスク遷移を決定する権限を持たないため、BL-024の元の指示文言も User側の役割指示にのみ存在する）。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl139_transition_fallback_from_directive.py`（4件: 実インシデント再現、Deferredの除外確認、既存の正常経路を上書きしないことの確認、Expert側では発火しないことの確認）。フルオフラインスイート557件Pass。

**関連:** [BL-024](#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)、[BL-039](#bl-039-decision_extractorが出力するtask_idの表記ゆれドット-vs-アンダースコアによりタスク遷移がドライラン全体で1回も成功していない)、[BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)

---

### BL-140: `THINK_TOOL`の`issues`パラメータ名が`write_issue`/issue_logと混同され、モデルが懸念を書いて満足し永続化しない誤解を誘発していた

**状態:** `done`

**経緯:** `log/2026-07-31/1129`レビュー中、issue_logがモデル自身によって能動的に使われない件について、ユーザーから「もしかしてthinkの方に取られている？thinkに書けば永遠に残ると勘違いしている？」という仮説が提起された。`THINK_TOOL`（`cela_main.py`）のパラメータ定義を確認したところ、まさに`issues`という名前のフィールドが存在し、`description`にも「BL-108/BL-111: nothing is summarized away or aged out」という、いかにも永続的に記録されるかのような文言があった。

しかし実装（`_think_handler`）を確認すると、この`issues`はモジュールレベルのグローバル変数へ一時保存されるだけで**DBには一切書き込まれず**、`_reset_think_scratchpad()`が`think`ツールを付与する各ノード関数の呼び出し開始時（＝1ターンごと）に必ず空にするため、**そのツールループが終わった瞬間に完全に消える**、単なる同一ターン内の作業メモに過ぎないことが判明した。実際、`log/2026-07-31/1129`の4550行目でDetectorが`think(issues=[...])`へ「予備車なし」「オペレーター兼務」「フォールバック地点未特定」「通信死活区」等5件の懸念を記録しており、これは後に別のDetector呼び出しで実際に`write_issue`されたもの（21611〜21637行）とほぼ同一内容だった。`write_issue`（DBへ永続化されターンをまたいでUser/Expertへ表示される）との名前の類似が、モデルが「懸念をthinkに書いた＝記録した」と誤解し永続化（`write_issue`呼び出し）を怠るリスクを内包していると判断した。

**対応（実施済み）:** `THINK_TOOL`の`issues`パラメータを`scratch_concerns`へ改名し、descriptionへ「これは永続的なissue_logとは別物で、このツール呼び出しループが終わると消える一時メモである。ターンをまたいで残したい懸念は`write_issue`を使うこと」という趣旨の注記を明記した。対応するモジュール変数`_THINK_ISSUES`→`_THINK_SCRATCH_CONCERNS`、`_think_handler`の返り値キー`current_issues`→`current_scratch_concerns`も同期して改名した。

ユーザーから「各ノードのプロンプトでのツール説明では？」との指摘を受け追加対応：JSONツールスキーマのdescriptionだけでなく、`write_issue`と`think`が同一ターンで併記される2箇所のシステムプロンプト本文（自然言語の地の文、モデルが実際の判断時により重視しうる経路）にも、明示的な注記が欠けていたことを確認。`call_detector`（domain review、`_issue_carryover_prefix`共有変数、2パスで使用）と`generate_user_utterance`（User AI）の両方に、「thinkツールのscratch_concernsは、このツール呼び出しループの中だけで消える一時メモであり、後続タスクへは一切引き継がれません。持ち越したい懸念をscratch_concernsに書くだけで満足せず、必ずwrite_issueで記録してください」という一文を追記した。

**完了条件:** `python -m py_compile`合格。新規テスト3件（`tests/test_bl093_think_tool_scratchpad.py::test_think_tool_scratch_concerns_param_disambiguates_from_write_issue`・`test_call_detector_prompt_body_disambiguates_scratch_concerns_from_write_issue`・`test_generate_user_utterance_prompt_body_disambiguates_scratch_concerns_from_write_issue`）追加、既存テスト2件をキー名変更（`issues`→`scratch_concerns`、`current_issues`→`current_scratch_concerns`、`_THINK_ISSUES`→`_THINK_SCRATCH_CONCERNS`）に追随。フルオフラインスイート560件Pass。次回ドライランでissue_log起票率の実際の改善が見られるかは要観察。

**関連:** [BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-093](#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)

---

### BL-142: Userの承認発言がmajor判定されても、Expertへの修正指示ではなくUser AI自身への言い直し要求に留まり、同じ承認を言い回しを変えて繰り返す空回りが発生していた

**状態:** `done`

**経緯:** `log/2026-08-01/2329`レビューで、task_1_1がホワイトボードVer.1〜21まで改訂され続け、最終的にReflectionが`stagnant`と判定してHALTした原因を調査した。ドメイン上の欠陥（M-07「合法3交代制の人件費倍率」が「2.5倍」と「3倍」の矛盾する数値のまま残存、M-02のOPEX試算が違法シフト前提の数値を最後まで使用）は正当なものだったが、それに加えて構造的な増幅要因が判明した。

Userの「承認・次タスクへ移行」発言が`user_detector`に`constraint_issue="major"`と判定されると、`route_after_user_detector`（`cela_main.py`）はExpertではなく**User AI自身**（`generate_user_utterance`）へ差し戻す設計になっている（`user_retry_count`上限3回）。19399〜19480行では、この差し戻しを受けたUser AIが実質同じ承認文を5ラウンドにわたり言い回しを変えて繰り返すだけで空回りし、その間ホワイトボードの根本的な数値矛盾には一切手が入らなかった。

ユーザーがこの現象を「ユーザーの承認系の発言の監査は、間違っている部分を指摘しつつ、承認を取り消し、エキスパートに訂正させるよう促すような言葉を発信するようにプロンプトで強くガイドラインしてあげなければならない」と整理。既存のmajor判定時プロンプト（`generate_user_utterance`の`⚠️【重要】`ブロック）には「エージェントAIに正しい方向への修正を厳しく要求してください」という一般的な指示は既にあったが、「却下された発話が承認・次タスク移行だった場合は、その承認自体を明示的に撤回せよ」という具体的な指示が欠けており、モデルが「言い回しを変えるだけで同じ承認を繰り返す」抜け道を許していた。

**対応（実施済み）:** 同ブロックへ、却下された前回発話が「承認」「次タスクへの移行」だった場合は、言い回しを変えただけの同じ承認の繰り返しを禁止し、`write_agreement(action_type="UPDATE", status="Rejected")`で承認を明確に撤回した上で、Agent AIが成果物のどこをどう直すべきか具体的に示した修正指示を出すことを求める一文を追加した。次タスクへの移行は、Agent AIの修正版再提出と指摘事項の解消確認を経てから改めて行うよう明記した。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl142_user_approval_retraction_guidance.py`（2件: 撤回指示の文言存在確認、既存の差し戻しプロンプトが壊れていないことの確認）追加。

**関連:** [BL-124](#bl-124-bl-086escalate_premise_concernfreeze_agreementrevise_goalがツールとして常時提供されているのにまさに想定されたケースで一度も使われずstagnanthaltに至った)、[BL-141](#bl-141-誤診断のためinvaliddetectorexpertの差し戻しループのたびにchat_historyへ新規assistantメッセージが無条件追記されると当初診断したが実在しなかった)

---

### BL-143: 差し戻しプロンプトにDetectorの指摘文だけが載っており、「何回目の差し戻しか」「前回と同じ指摘の繰り返しか」というPython側で計算可能な現在地情報が渡っていなかった

**状態:** `done`

**経緯:** ユーザーから「各ノードが今の状況とやるべきことの整理をもっとよりよくできる仕組みはないか」との相談があった。Mermaid図で全体フローを渡す案も検討したが、LLMに図の解釈を委ねるより、CELAが既にBL-086/BL-125/BL-136/BL-142で使っている「Pythonのif/elseでstateを判定し、該当分岐専用の指示文だけを注入する」パターン（決定論的で確実性が高い）を踏襲する方針とした。

その過程でユーザーから「いま現在はDetectorの指摘文だけのっているんでしたっけ？」と確認があり、コードを調査。`generate_user_utterance`（User AI側、当時6822行）・`call_expert`（Expert側、当時5241行）双方の差し戻しプロンプトとも、実際に載っているのは`state['constraint_issue_log'][-1:]`——Detectorの直近1件の判定`{'turn': ..., 'severity': ..., 'comment': ...}`を生のPythonリストreprとしてそのまま貼り付けたものだけだと判明した。具体的に欠けていたもの：

1. **再発回数・履歴**: 同じ指摘が何回目の差し戻しか（`user_retry_count`/`expert_retry_count`は`route_after_user_detector`/`route_after_expert_detector`のルーティング判定にのみ使われ、プロンプトには一切出ていなかった）。
2. **前回との差分**: 前回の指摘と比べて同じ指摘が繰り返されているのか、新しい指摘なのか。

BL-142で見た「Userが気づかず同じ承認を言い回しを変えて繰り返す」空回りも、この現在地情報の欠如が一因と考えられる。

**対応（実施済み）:** 新規ヘルパー`_build_retry_situation_label(state, retry_count, max_retries=3)`（`cela_main.py`）を新設した。

- 常に「【現在地】これはこの論点に対するN回目の差し戻しです（あとM回で強制的にレビュー（reflection）へ回されます）」という一行を返す（`route_after_user_detector`/`route_after_expert_detector`の`retry_count >= 3`エスカレーション条件と同じ`max_retries=3`を使用し、実際の残り試行回数と食い違わないようにする）。
- `retry_count >= 2`（＝`constraint_issue_log`の末尾2件が確実に同一の差し戻し連鎖に属する——`constraint_issue_log`はminor/major判定時のみ追記され、この連鎖の外側の判定が割り込むことはないため）のときのみ、直近2件のcommentを`difflib.SequenceMatcher`で比較し、類似度0.6以上なら「前回の指摘とほぼ同じ内容が繰り返されています。同じ対応を言い回しを変えて繰り返すのではなく、指摘されている根本原因に着手してください」という警告を追加する。`retry_count == 1`では連鎖内に比較対象がまだ無いため（比較すると連鎖外の無関係な過去のmajor判定と誤って比較しうる）、この比較はスキップする。

`call_expert`・`generate_user_utterance`双方の差し戻しプロンプト冒頭（既存の「⚠️【重要】」ブロックの直前）へ注入した。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl143_retry_situation_label.py`（8件）追加。フルオフラインスイート574件Pass。次回ドライランで実際にUser/Expertがこの現在地情報を踏まえた行動を取るようになるかは要観察。

**関連:** [BL-142](#bl-142-userの承認発言がmajor判定されてもexpertへの修正指示ではなくuser-ai自身への言い直し要求に留まり同じ承認を言い回しを変えて繰り返す空回りが発生していた)、[BL-086](#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)

---

### BL-144: `reflection_node`のBL-096機械的stagnant上書きが、escalated issueの単なる「存在」で無条件発火し、reflection自身が健全な進捗と判定した回まで停滞扱いしていた

**状態:** `done`

**経緯:** `log/2026-08-02/0832`（BL-142/143実装後初のドライラン）レビューをAgentへ委託した際、reflectionの1回目のサイクル（escalated issue 4件時点、`log_no_prompt.md` 9088行付近）で、reflection自身のLLM判定は明確に`"continuing"`——「堂々巡りではなく、計算誤り・法令違反が順次是正され建設的な議論が進行中」と自ら理由づけていたことが判明した。しかしBL-096の機械的上書き（issue_logに`status='escalated'`の行が1件でもあれば無条件でstagnant化）により、このサイクルはfacilitation_countの貴重な猶予（既定3回、`facilitator_node`が`facilitation_count > 3`でHALT）を1つ消費した。最終（4回目）サイクル（escalated 10件時点）はreflection自身も独立にstagnantと判定しており（task_1_2でのデータ捏造・自己矛盾・Expertの空応答という実質的根拠）、そちらのHALT自体は正当だった。つまり「本物の停滞」で終わったこと自体は正しかったが、そこに至る過程でBL-096が健全な進捗中の回を誤って停滞扱いし、猶予を早期に消費していた。

ユーザーへ「BL-096の上書き条件を、単なる存在チェックから『同じescalated issueが複数サイクルにわたって進展していない場合のみ』へ絞る」提案をしたところユーザーが同意し、具体的な閾値として「ユーザーノードを3回通過する」を提示した（BL-136導入後もwrite_issueのRESOLVE/DEFERがほぼ呼ばれず、escalated件数が単調増加し続ける現状では、閾値を上げるだけでは根本解決にならないが、少なくとも健全な進捗を誤って停滞扱いする誤検知は減らせる）。

**対応（実施済み）:** `LineageState`へ新規フィールド`escalated_issue_first_seen_round: dict[str, int]`（issue_log行id→初めてescalated状態で観測した`round_count`の辞書）を追加。`reflection_node`は毎回`_get_escalated_issues`で取得したescalated行それぞれについて、初観測時の`round_count`を記録し（`setdefault`で初回のみセット）、現在の`round_count`との差が3以上（＝ユーザーノード＝`generate_user_utterance_node`を3回通過しても未解決のまま）の行が1件でもあれば`discussion_status`を`"stagnant"`へ上書きする。解決・先送り済みで`_get_escalated_issues`の結果から消えたissueは追跡辞書からも削除する（再度escalatedになった場合は新規の滞留として扱う）。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl144_escalated_issue_staleness_threshold.py`（4件: 初観測時（滞留0）は上書きしないこと、3ラウンド滞留で上書きされること、issue解決時に追跡辞書がクリアされること、複数issueのうち1件でも滞留していれば発火すること）追加。既存の`tests/test_bl096_issue_log.py`（ソース文字列検証のみ）・`tests/test_bl061_facilitator_reflection_note.py`は無修正でPass。フルオフラインスイート578件Pass。

**関連:** [BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-142](#bl-142-userの承認発言がmajor判定されてもexpertへの修正指示ではなくuser-ai自身への言い直し要求に留まり同じ承認を言い回しを変えて繰り返す空回りが発生していた)、[BL-143](#bl-143-差し戻しプロンプトにdetectorの指摘文だけが載っており何回目の差し戻しか前回と同じ指摘の繰り返しかというpython側で計算可能な現在地情報が渡っていなかった)

---

### BL-141: 【誤診断のためinvalid】Detector⇄Expertの差し戻しループのたびにchat_historyへ新規assistantメッセージが無条件追記される、と当初診断したが実在しなかった

**状態:** `invalid`（誤診断、既存の仕組みで既に対応済みと判明）

**経緯:** ユーザーから「detectorとエキスパートの差戻しループは見せずにuser->エキスパートの履歴だけに整理できませんか？差戻ループが続くと最初に言ったユーザー発言が見れなくなる恐れがあり、次のユーザーが前のユーザーが何を言ったかわからなくなってしまいます」との指摘。

調査時、`expert_node`のソースのうち末尾（`output = call_expert(...)`以降）だけを確認し、`state["chat_history"].append({"role": "assistant", "content": output})`が無条件実行されているように見えたため、「差し戻しのたびにchat_historyへassistantメッセージが無条件追記され、`chat_history_window`（既定4）が同一タスクの往復だけで埋まる」と誤って結論づけ、修正（直前のエントリが既にassistantなら新規追記せず上書きする処理）を追加した。

しかし後日、`expert_node`の**冒頭**（`call_expert`呼び出しの直前）を改めて確認したところ、このセッション開始前から既に次のコードが存在していたことが判明した（`git show HEAD:cela_main.py`で当該行が変更差分に含まれないことを確認済み＝コミット済みの既存コード）：

```python
if state.get("constraint_issue") in ("major"):
    if state["chat_history"] and state["chat_history"][-1]["role"] == "assistant":
        state["chat_history"].pop()
        state["expert_retry_count"] += 1
        ...
```

Detectorがmajor判定で差し戻す＝`state["constraint_issue"] == "major"`のときは、`call_expert`を呼ぶ**前**に直前のchat_history末尾（前回の却下された提出）を`pop`しており、その後末尾で新しい提出を`append`するため、正味の増減は0（pop 1件・append 1件）で、差し戻しが何回続いてもchat_historyの長さは一定に保たれていた。User側の`generate_user_utterance_node`にも同型のpopロジックが存在する（`cela_main.py`、`state["chat_history"].pop()`＋`user_retry_count`加算）。つまり報告された問題は当初から存在しなかった。

**対応（実施済み）:** 誤って追加した重複コード（`expert_node`末尾の「直前のエントリが既にassistantなら新規追記せず上書き」処理）を削除し、既存の冒頭popロジックのみへ戻した。当時この誤診断に基づいて書いた回帰テスト`tests/test_bl141_expert_retry_chat_history_collapse.py`は、既存の冒頭popロジック（`constraint_issue=="major"`をトリガーとする）を正しく検証する内容へ全面差し替えた。D-113（decision_log.md）・decision_lineage.md論点94も、本訂正を反映して更新した。

**教訓:** 対象関数のソースを部分的にしか読まずに「無条件で実行される」と断定してはならない。特に、ループ内の条件分岐が関数の**冒頭**（呼び出し前のガード節）にあるパターンは見落としやすく、末尾の処理だけを見て挙動を結論づけると誤診断に至る。次回以降、`inspect.getsource()`等で関数全体を俯瞰してから挙動を判断すること。

**関連:** [BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)

---

### BL-145: エスカレーションissue・申し送りissueを、Detector/Reflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する

**状態:** `done`

**基本設計:** [BL145_basic_design.md](BL-145/BL145_basic_design.md)（Plan Mode、Explore 1体 + Plan 1体）。

**経緯:** `log/2026-08-02/0832`レビューで見つかったOrchestrator関連のバグ調査（BL-146〜148）の過程で、ユーザーから「majorとなったissueや後続タスクへの申し送りは、Detector、もしくはReflectorで正当性の監査後、タスクプランナー経由で明示的にタスク化し整理したほうが良いかもしれない」との設計提案があった。当初は設計相談のみで実装未着手だったが、`log/2026-08-03/1347`ドライランで、detector_auto起票の汎用issue（16回occurrence蓄積）が一度もRESOLVE/DEFERされないままBL-125のタスク遷移ゲートを塞ぎ続け、Expert/User AIがSUPERSEDEで正規のゲートを迂回し続ける実害（BL-152の引き金にもなった）を確認したことを受け、実装に着手した。

調査の結果、以下が判明していた：
- `write_issue(action_type="DEFER")`（BL-136）は、対象task_idの`plan_drafts`へ申し送りテキストを追記するのみで、issueを正式な`task_id`として`state["phases"]`へ組み込む経路は存在しない。
- `state["phases"]`は`task_planner_node`が`state["plan_revision_reason"]`非空時（`task_plan_reviewer`の差し戻し／Essence Dialogue収束の2経路のみ）にのみ`existing_phases`全体をLLMで再生成する方式であり、軽量な差分APIは存在しない（BL-126 Stage Cの「supersede機構」もLLMの新計画とold_phasesの`task_id`集合差分を事後的に記帳するだけの監査ブックキーピングであり、編集プリミティブそのものではない）。
- BL-144の滞留検知（`escalated_issue_first_seen_round`：同一escalated issueがユーザーノードを3回通過しても未解決）は、「正当性がありかつ解消されていない」issueを機械的に検出する既存シグナルとして転用できる。

**スコープ限定の決定：** `state["phases"]`への軽量な差分編集API（1タスク単位の追加・削除・修正プリミティブ）は本BLでは作らない。既存の`plan_revision_reason`→`task_planner_node`全再生成という、reviewer差し戻し・Essence Dialogue収束が既に使っている経路をそのまま再利用する（差分APIは将来BLとして切り出す）。

**実装内容（実施済み）：**
1. `LineageState`へ`plan_revision_issue_ids: list[str]`を追加（`plan_revision_reason`と対でセット・クリア）。
2. `reflection_node`：BL-144の滞留検知後、既にDEFER済み（`defer_to_task_id`設定済み）でないstale escalated issueについて、`plan_revision_reason`が他要因で未使用の場合のみ、issue詳細（topic/description/occurrence_count/issue_id）を含む理由文と`plan_revision_issue_ids`をセットする。`call_reflection`（LLM呼び出し本体、`tools=None`）は無変更、完全にPython側の決定論的処理。
3. `task_planner_node`：`revision_issue_ids`を`revision_reason`と同じタイミングで取得・クリア。計画再構成成功後、新規ヘルパー`_mark_issue_planned`（id基準の直接DB更新、tool経由・LLMゲート経由ではない）で対象issueを新ステータス`'planned'`へ遷移させ、埋め込み先task_id一覧の先頭を`defer_to_task_id`列（BL-136のDEFERと同じ「今このissueの面倒を見ているtask_id」の意味を再利用）に記録する。
4. **設計協議による変更**：当初案の「即座に`resolved`化」を、ユーザー指摘（「resolvedとするのは語弊が生まれる可能性がある」「延期も可能とする」「無理やり解決しようとして議論のデッドロック化も避けたい」）を受け、`'planned'`という中間状態へ変更した。`'planned'`は`_write_issue_impl`のCREATE/DEFER/RESOLVEが判定条件とする`status != 'resolved'`を満たすため、既存のDEFER（さらなる先送り）・CREATE経由の再発検知（occurrence_count>=2での再escalated化）がコード変更なしでそのまま機能する。真の`resolved`化は、user role経由の既存`write_issue(RESOLVE)`で人間側代理が明示的に行う。
5. `facilitator_node`のEssence Dialogue収束ブロックに、`plan_revision_reason`使用中は上書きせず持ち越す防御ガードを追加（Plan agentによるグラフトポロジ解析で現状は衝突が起こり得ないことを確認済み、将来のグラフ変更に対する防御）。
6. 新規`_get_planned_issues`/`_build_planned_issue_pin_text`（`_get_open_issues`と同型）を`generate_user_utterance`へ配線し、`planned`issueを非強制の参考情報として可視化（BL-136の強制解決文言とは別枠、無理な即時対応は求めずデッドロック化を回避）。

新規テスト`tests/test_bl145_issue_driven_plan_formalization.py`（16件: reflection_nodeのトリガー判定、task_planner_nodeによる決定論的planned遷移、DEFER/CREATE再発検知の回帰確認、facilitator_nodeの衝突防御、可視化ブロック）追加。既存のBL-096/086/126 Stage C・D/136/144/146-148関連テスト（計132件）は無修正でPass。`python -m py_compile`合格、フルオフラインスイート623件Pass。

**関連:** [BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-144](#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)、[BL-082](#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-152](#bl-152-verify_whiteboard_excerptが今レビューすべき成果物ではなく常にcurrent_task_idのホワイトボードだけを見ていた)

---

### BL-146: `write_agreement`がBL-125のタスク遷移ゲート（current_task_id）を内容レベルで迂回でき、ブロック中の他タスクへ実際にDeliverableを書き込めていた

**状態:** `done`

**基本設計:** [BL146_147_148_basic_design.md](BL-146/BL146_147_148_basic_design.md)（BL-147/BL-148と一体設計。Plan Modeで3体のExploreエージェント＋Planエージェントによる調査を経て確定）。

**経緯:** `log/2026-08-02/0832`ドライランのレビューで「BL-125のブロック表示後もOrchestratorが一時的にtask_1_2の作業を進めた」という指摘があり詳細調査したところ、`current_task_id`自体は一度も巻き戻っておらず（`_resolve_task_transition`の遷移成功printが当該run全体で0件）、実際には別の独立したバグが根本原因だった。`_write_agreement_impl`/`_commit_agreement_from_tool`は、LLMがツール引数で指定した`task_id`をtask_plannerの正式な計画に実在するか（BL-131）でしか検証しておらず、`state["current_task_id"]`（BL-125が遷移をブロックしている対象そのもの）とは一切照合していなかった。そのためBL-125が`current_task_id`のタスク遷移をブロックしていても、Expertは`task_id="task_1_2"`のように任意の他タスクを指定してDeliverableを実際に書き込めてしまい（SUPERSEDEを除く）、Detectorがそれをtask_1_2の正式な成果物として本当にレビューしてしまう実害を確認した。

なお、この過程でユーザーから「後続タスクで詳細検討した結果、先発タスクの成果物も修正する必要があった場合の経路は確保されているか？」という確認があり、`action_type="SUPERSEDE"`（BL-062/080/084で実装済み、他タスクの内容を正規に改訂する既存の正当な経路）はこのゲートの対象外として維持することを確認・合意した。

**対応（実施済み）:** 新規ヘルパー`_effective_current_task_id_from(state)`（`cela_main.py`、`_pending_task_ids_from`の直後）を追加。`_get_current_task`と同じ「`current_task_id`が空文字（初回タスク進行中、`_resolve_task_transition`がまだ一度も発火していない状態）なら`current_phase`の先頭タスクへフォールバックする」ロジックを再利用し、初回タスクの正当な書き込みまで誤ってブロックしないようにした。`TOOL_DISPATCH["write_agreement"]`にこの値を渡し、`_write_agreement_impl`のBL-131実在チェック直後に、`entry_type in ("Directive", "Deliverable")`かつ`action_type != "SUPERSEDE"`かつtask_idが実効上のcurrent_task_idと一致しない場合は拒否するチェックを追加した。`current_phase`/`phases`を持たない簡易`state`（既存テストのフィクスチャ含む）ではフェイルオープンでゲートをスキップする設計とし、既存テストへの回帰を避けた。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl146_write_agreement_current_task_gate.py`（6件: 他タスクへのDeliverable書き込み拒否、SUPERSEDEは対象外、初回タスクでの正しい許可、ロール非依存、`entry_type="Decision"`は対象外、current_phase不明時のフェイルオープン）追加。既存`tests/test_bl131_write_agreement_task_id_validation.py`（9件）は無修正でPass。フルオフラインスイート596件Pass。

**関連:** [BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-131](#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、[BL-147](#bl-147-read_deliverable_fileがtask_idの実在チェックを一切行っておらずfile_path併用時は事実上無視される)、[BL-148](#bl-148-orchestratorがcurrent_task_id計画成果物を一切参照できないままexpert選定focus_guidanceを決めていた)

---

### BL-147: `read_deliverable_file`がtask_idの実在チェックを一切行っておらず、file_path併用時は事実上無視される

**状態:** `done`

**基本設計:** [BL146_147_148_basic_design.md](BL-146/BL146_147_148_basic_design.md)（BL-146/BL-148と一体設計）。

**経緯:** BL-146と同じ`log/2026-08-02/0832`調査の過程で発見。`read_deliverable_file`は`write_agreement`（BL-131）と異なりtask_idの実在チェックを一切行っておらず、存在しないtask_idを指定しても素通りしていた。特にtask_idと`file_path`を同時指定した場合、`task_id`が空でない限りDB逆引きを試みるが、逆引きが失敗し`file_path`が指定されていれば`elif not file_path:`分岐が偽になりそのまま`file_path`側の読み込みへ進んでしまうため、「存在しないtask_idを指定しつつfile_pathで読み込みを通過させる」抜け道になっていた。

**対応（実施済み）:** `_read_deliverable_file_handler`に`state: dict | None = None`引数を追加し、`TOOL_DISPATCH["read_deliverable_file"]`から実際に渡すようにした（従来は`state`を一切受け取らず破棄していた）。`task_id`が指定されている場合、`file_path`分岐に入るより前に`_find_task_by_id`/`pending_task_ids`（BL-131と同型の実在チェック）を行い、計画に存在しなければエラーを返すようにした。実在する他タスクの成果物への参照読み（本ツール本来の目的）は制限しない。

**完了条件:** `python -m py_compile`合格。新規テスト`tests/test_bl147_read_deliverable_file_task_id_validation.py`（6件: 存在しないtask_idの拒否、file_path併用時も拒否、既存task_idでDeliverable未作成時のnot_found、他タスク成果物の参照読み許可、pending_task_idsの許可、task_id省略時の非回帰）追加。既存`tests/test_r3_smoke.py::test_bl040_read_deliverable_file_lookup_by_task_id`が、（a）state省略（TOOL_DISPATCHへの引数なし呼び出し）、（b）存在しないtask_idの期待値が`not_found`から`error`へ変わった、の2点で新チェックと衝突したため、`state`を明示的に渡す形へ更新した（実運用では`query_AI`のツールループが常に`state`を渡すため、この更新は実際の呼び出しパターンとの整合を取るもの）。フルオフラインスイート596件Pass。

**関連:** [BL-131](#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、[BL-146](#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)、[BL-040](#bl-040-read_deliverable_fileがfile_path直接指定に依存し実質的に発見不能だった問題)

---

### BL-148: Orchestratorがcurrent_task_id・計画・成果物を一切参照できないまま、Expert選定・focus_guidanceを決めていた

**状態:** `done`

**基本設計:** [BL146_147_148_basic_design.md](BL-146/BL146_147_148_basic_design.md)（BL-146/BL-147と一体設計）。

**経緯:** BL-146と同じ`log/2026-08-02/0832`調査で発見。Orchestrator（`call_orchestrator`）はツールを一切持たない単発JSON応答（`tools=`引数省略）で、プロンプトに`current_task_id`・タスク計画・issue状況が一切含まれていなかった。専門家選定はUser AI/Expert AIの対話の生テキストのみに基づいて行われるため、対話がBL-125でブロックされているタスクとは別のタスクへ漂うと、`current_task_id`がまだ元のタスクにピンされていても専門家選定がそちらへ引っ張られてしまう。実際、Detector自身がこの矛盾（「現在のタスクはtask_1_2」と言われたのにtask_1_1の受入基準が渡ってくる）に気づき「プロンプトのバグだと思う」と自己申告していたログ（`log_with_prompt.md`）が残っていた。ユーザーからも「Orchestratorのツールは必要な情報が見れるツールが渡されていますか？Orchestratorもツールループ化が必要です」との明示的な指示があった。

**対応（実施済み）:** `call_orchestrator`のプロンプトへ、`_build_task_scope_context`（`current_task_json`・未充足の要求項目）と`_build_project_plan_toc`（プロジェクト計画目次）を用いた現在タスクの構造化情報ブロックを追加し、「対話文脈がどのタスクの話に読めても、専門家選定はcurrent_task_idを基準にすること」を明記した。`query_AI`呼び出しを単発JSON応答から、`tools=[READ_PROJECT_PLAN_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_VERIFIED_FACT_TOOL, THINK_TOOL], state=state`を持つツールループへ変更（`call_facilitator`/`call_integrator`等、既存の「単一userメッセージ形式の単発判定ノードをツールループ化した」前例と同型。この形式では`light_system_prompt`が元々no-opになるため付与していない）。Orchestratorの役割は専門家選定メタデータの生成のみで状態を変更しないため、`write_agreement`等の書き込み系ツールは意図的に付与しない（`_check_write_permission`のロール表にも`"orchestrator"`は存在しない）。BL-109（単発判定ノードのtools=None化対象一覧）から`call_orchestrator`を除外し、BL-126 Stage D（`call_facilitator`の同型の差し戻し）と同じ理由づけとした。`orchestrator_node`自体は無変更（既存の`state["selected_expert"]`/`state["expert_focus_guidance"]`の入出力契約を維持）。

**完了条件:** `python -m py_compile`合格。既存`tests/test_bl093_think_tool_scratchpad.py::test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`の対象リストから`call_orchestrator`を除去し、新規`test_bl148_call_orchestrator_is_tool_loop_capable`（読み取り専用4ツールの参照・書き込み系ツール非参照をソース検査で固定化）を追加。`_NODE_TOOL_NAME_REMINDERS`辞書に`call_orchestrator`エントリを追加。新規`tests/test_bl148_orchestrator_tool_loop.py`（4件: current_task_id参照、読み取り専用ツールのみ、state引き渡し、orchestrator_nodeの入出力契約不変）追加。既存`tests/test_bl078_orchestrator_focus_guidance.py`（4件）は無修正でPass。フルオフラインスイート596件Pass。

**関連:** [BL-109](#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-146](#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)

---

### BL-149: `_safe_json_parse`のフォールバック戦略ロギング不足

**状態:** `open`（記録のみ、優先度低）

**経緯:** 2026-08-03、別AI（Cline/deepseek-v4-flash経由）によるコードベース全体バグチェック（`BL-149_150_codebase_bugcheck_2026-08-03.md`）で発見。`_safe_json_parse`（Codebase Memory MCPの複雑度メトリクスでcomplexity=16, cognitive=37, 68行）は複数のフォールバック戦略（フェンスブロック抽出・`{`/`[`優先順位判定・末尾補完等）を順に試す設計だが、どの戦略で成功・失敗したかがログ出力されない。BL-133で`_query_and_parse_with_retry`に生レスポンス300字プレビューを追加したが、`_safe_json_parse`自体が「どの戦略で・なぜ」成功/失敗したかは依然不明なまま。BL-088（`{`/`[`優先順位バグ）やBL-089（複数フェンスブロック混線）と同種の問題が再発した際、原因切り分けが困難になる。

**対応（未着手）:** `_safe_json_parse`の各フォールバック戦略の成功/失敗時に、どの戦略が使われたかをログ出力する（BL-133の300字プレビューと同種の診断強化）。

**完了条件:** 実装後`python -m py_compile`合格・既存テストPass。ログ出力追加のみでロジック変更は伴わないため、既存の`tests/test_bl089_json_fence_and_failclosed_review.py`等の非退行確認で足りる想定。

**関連:** [BL-133](#bl-133-test_detector_no_false_positive_within_capb51非退行d-011が層2リトライ枯渇によるフェイルクローズで33失敗しモデルの誤判定と誤認されるところだった)、[BL-088](#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)、[BL-089](#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)

---

### BL-150: 高複雑度関数のリファクタリング候補（`decision_extractor_node`・`_commit_agreement_from_tool`等）

**状態:** `open`（記録のみ、BL-098/118のファイル分割着手時に合わせて検討）

**経緯:** 2026-08-03、別AI（Cline/deepseek-v4-flash経由）によるコードベース全体バグチェック（`BL-149_150_codebase_bugcheck_2026-08-03.md`）で発見。Codebase Memory MCPの複雑度メトリクスより、`decision_extractor_node`（complexity=26, cognitive=91, 5 loops, 202行）と`_commit_agreement_from_tool`（complexity=26, cognitive=78, 159行, out-degree=12）がコードベース全体で最も複雑。`call_detector`（493行）も関数長として突出している。`decision_extractor_node`は抽出ロジック（User/Expert分岐）・遷移解決・DB書き込みの3責務を1関数で抱え、`_commit_agreement_from_tool`はCREATE/UPDATE/SUPERSEDE × Decision/Directive/Deliverable/EssenceProposalの全組合せを1関数で処理している。BL-098/BL-118（8000行超の単一ファイルを永続化層/ツール層/ノード層/ログ層に分割する構想）と関連するが、ファイル分割前に個別関数の責務分割・サブ関数抽出を先行させるべきという指摘。

**対応（未着手）:** `decision_extractor_node`を抽出ロジック・遷移解決・DB書き込みのサブ関数へ分割、`_commit_agreement_from_tool`をaction_type×entry_typeのマトリックスごとのサブ関数へ分離することを検討。着手はBL-098/118のファイル分割スコープ確定時に合わせる。

**完了条件:** リファクタリング実施時、`python -m py_compile`合格・既存テスト（特に該当関数を直接呼ぶ/ソース検査する各種テスト）が無修正または軽微な更新でPassすること。振る舞いの変更は一切伴わないことをフルオフラインスイートで確認する。

**関連:** [BL-098](#bl-098-cela_mainpyの責務分離永続化層ツール層プロンプトノード層uiログ層)、[BL-118](#bl-118-cela_mainpyのモジュール分割クラスノード単位でのファイル化疎結合化)

---

### BL-151: `revise_goal`のold_textが、プロンプト表示専用の絵文字装飾を含んでいたため9回以上自己修復に失敗し続けた

**状態:** `done`

**経緯:** `log/2026-08-03/1110`ドライラン（BL-086/BL-126で設計した「発注者自身が前提矛盾に気づきゴールを是正する」経路が初めて実発火したケース）をレビューした際にユーザーが発見。User AIがfacilitatorの提言を受けてゴール文の手段固定（「AIオンデマンド自動運転バス」という手段が予算・地理・需要の物理的制約下で矛盾を生んでいる）に気づき、`escalate_premise_concern`→`revise_goal`という設計通りの流れを正しく踏んだにもかかわらず、`revise_goal`のedits[0]がiter=1から少なくともiter=9まで**同一の理由で連続失敗**していた。

原因を`_revise_goal_tool_impl`（cela_main.py:1663〜）と`generate_user_utterance`（同6710〜）を突き合わせて特定した。`generate_user_utterance`がUser AIへ見せるプロンプトはゴール文の先頭に表示専用の装飾を付加している（`👉 {user_goal}\n`、6736行目、改行を挟まず装飾と本文が同じ行に連結される形）。一方`revise_goal`が実際に照合する対象（`_CURRENT_GOAL_TEXT = user_goal = state["goal"]`）は、シナリオ定義の生テキスト（`TARGET_GOAL`、9040〜9041行目）そのもので絵文字を含まない。User AIが（プロンプトに忠実に）「👉 過疎地域向け「AIオンデマンド自動運転バス」の導入計画と安全基準策定」を一字一句正確に引用しようとするほど、実際の照合対象と一致しなくなるという構造的な罠だった。`_apply_text_edits`の緩い一致フォールバック（BL-081）も空白・`*`・`|`のみ正規化対象で絵文字は対象外のため救えず、失敗時のエラーメッセージも「一字一句正確な引用か確認してください」としか言わず実際の格納内容を一切見せていなかったため、User AIは同じ誤った仮説（「引用の切り方が違う」）を延々再試行し続けていた。MAX_TOOL_ITER=20への到達によるクラッシュではなく、BL-056bの「残り回数逼迫通知」（iter=17〜19で発火）が先に働いてツール呼び出しを打ち切らせる可能性が高く即座のプロセスクラッシュリスクは低かったが、このターンでのゴール改定は静かに失敗し、エスカレーションは未解決のまま残り続ける実害があった。

**対応（実施済み）:** `_apply_text_edits`（cela_main.py:4041〜）へ`content_label: str = "現在のホワイトボード内容"`パラメータを追加し、`_revise_goal_tool_impl`からの呼び出しでは`content_label="現在のゴール文"`を明示的に指定するよう変更した。`exact_count==0`（完全一致・緩い一致とも0件）でエラーを返す分岐に、`current_content`の実際の内容の先頭`_TEXT_EDIT_SNIPPET_MAX_CHARS`（400字）分をエラーメッセージへ含めるようにした（400字超の場合は「…（以下省略）」を付与）。これにより、表示用装飾と格納内容の乖離という原因不明のケースでも、モデルが同ターン内のツールループで実際の文言を見て自己修復できるようになる（BL-081「Expertが同ターン内のツールループで修正・再試行できるよう、原因を具体的に伝える」という既存の設計思想の延長）。

あわせて、同種の「プロンプト表示専用の装飾が、ツールの照合対象である格納内容からずれている」箇所が他にないか、`state['goal']`/`user_goal`の全埋め込み箇所と、`_apply_text_edits`のもう一方の呼び出し元（`write_agreement`のDeliverable UPDATE経路、1955行目）が参照するホワイトボード表示箇所を調査した。

- `call_orchestrator`（5055行目、`f"Goal: {state['goal']}\n..."`）・`call_expert`（5319行目、`👉 {state['goal']}`）・`call_reflection`（6367行目、`👉 {state['goal']}`）にも同型の装飾があるが、`revise_goal`はuserロール専用（`_revise_goal_tool_impl`の`caller_role != "user"`チェック）でOrchestrator/Expert/Reflectionはいずれも呼べないため、現状は機能的な罠になっていないことを確認した。
- `write_agreement`のDeliverable UPDATE経路が参照するホワイトボード表示（`_build_task_scope_context`の`whiteboard_text`、4706〜4708行目、および`call_detector`の`whiteboard_block`、5544〜5546行目）は、いずれも見出し行と本文が改行で明確に分離されておりgoal文のケースのような同一行連結の罠にはなっていないことを確認した。
- Decision型agreementsの一覧表示（`_build_agreements_context`、4574〜4590行目）は`[id] icon[label] topic: {content_preview}`という同一行連結の装飾を持ち、かつ`content_preview`は150字で切り詰められているが、`write_agreement`の`edits`パラメータはentry_type="Deliverable"の場合のみ処理される設計（1942〜1962行目）であり、非Deliverable（Decision）entryのUPDATEはedits機構を通らないため、現状これも機能的な罠にはなっていないことを確認した。

上記3件はいずれも現時点では実害がないため追加のコード変更は行わず、記録のみに留めた（`content_label`によるエラー可視化の一般的な強化は既に適用済みのため、将来これらの文脈でexact-text一致を要求するツールが追加された場合でも、同種のドライランでの自己修復不能状態には陥りにくい）。

**完了条件:** `python -m py_compile`合格。新規`tests/test_bl151_apply_text_edits_error_snippet.py`（8件: スニペット含有・デフォルト/カスタムcontent_label・長文切り詰め・短文非切り詰め・複数一致エラーの形状不変・revise_goal経由の実インシデント再現）追加。既存`tests/test_bl081_edits_loose_match_fallback.py`・`tests/test_bl086_escalation_freeze_goal_revision.py`は無修正でPass（エラーメッセージに「件」を含む既存アサーションと非衝突）。

**関連:** [BL-086](#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-081](#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)、[BL-137](#bl-137-_apply_text_editsが非dict要素を含むeditsで未捕捉クラッシュしrun_ai_vs_ai_loop全体が停止した)

---

### BL-152: `verify_whiteboard_excerpt`が「今レビューすべき成果物」ではなく、常に`current_task_id`のホワイトボードだけを見ていた

**状態:** `open`（記録のみ、実装未着手）

**経緯:** `log/2026-08-03/1347`ドライラン（BL-151修正後、`1110`を一時停止して再開したラン）をレビューした際にユーザーが発見・AIが調査。

このターンでは、ExpertがBL-146のSUPERSEDE経路（他タスク改訂の正規手段。`_effective_current_task_id_from`によるcurrent_task_idゲートは`action_type != "SUPERSEDE"`の場合のみ適用されるため、SUPERSEDEはこのゲートの対象外）を使ってtask_1_3の成果物を新規に書き込んでいた。Expert自身「the system says the current task is task_1_1」と認識した上で、意図的にSUPERSEDEでtask_1_3を先行して書いたという経緯がログに残っている。しかし`state["current_task_id"]`は`_resolve_task_transition`（BL-125）による正式な遷移がまだ成立していないためtask_1_1のままだった。

この状態でDetectorがtask_1_3の成果物を監査した際、以下の3箇所がすべて無条件に`state["current_task_id"]`（task_1_1）を対象にしていることが判明した：

1. `call_detector`の`whiteboard_block`構築（cela_main.py:5541〜5546、`_current_task_id = current_task.get("task_id", "")`——`current_task = _get_current_task(state)`はcurrent_task_id依存のフォールバック）。「R4: 現在タスクの成果物・最新ホワイトボード」としてDetectorへ提示される内容が、実際にレビューすべきtask_1_3ではなくtask_1_1のものになっていた。
2. `_verify_whiteboard_excerpt_handler`（cela_main.py:1229〜、BL-079）は`_CURRENT_TASK_ID`/`_CURRENT_PHASE_ID`のモジュールグローバルのみを参照し、`call_detector`冒頭（5524〜5525行目）で`state.get("current_task_id", "")`からセットされたままの値（task_1_1）と照合する。
3. `detector_node`の`_annotate_whiteboard_with_detector_comment`呼び出し（cela_main.py:7847〜7853、BL-076）も同じく`current_task_id = state.get("current_task_id", "")`（detector_node冒頭）を注釈挿入先として渡している。

DetectorはExpertの実際の提出内容を`read_deliverable_file(task_id="task_1_3")`で正しく読んで評価していたが、`verify_whiteboard_excerpt`でどれだけ正確に引用してもtask_1_1のホワイトボードと照合される限り一致するはずがない——実際、`"案A"`というたった2文字の引用すら19回連続で不一致になり続けた（`log/2026-08-03/1347`のあるエピソードで実測）。

**実測された被害規模:** わずか2ターンの間に`verify_whiteboard_excerpt`が96回呼ばれ、79回（82%）が不一致で失敗。上記の1エピソードではMAX_TOOL_ITER=20を丸ごと消費し「最終iteration（20）のためツールを外し、テキスト最終応答を強制します」に至った（tool_calls使用=19回）。たまたま両タスクに共通する汎用語句「ピーク需要」がiter=19で偶然一致したため、それが`target_excerpt`として採用された。この判定は`constraint_issue: "major"`となり、実際に`Whiteboard Annotated`（注釈挿入成功）ログまで進んでいる——つまりtask_1_3固有の批判コメント（乗合タクシー実現性の疑義、中古有人バス混在による本質乖離、山間部需要按分の恣意性、クラウド化リスク未評価）が、`current_task_id`基準でtask_1_1のホワイトボードへ誤って埋め込まれた可能性が高い。無関係な文書が汚染される一方、本来指摘すべきtask_1_3側には注釈が付かないという、silent（クラッシュしない）データ破損モードである。

**なぜ今まで気づけなかったか:** (1) このバグはクラッシュせず「不一致で再試行するモデル」という表面上の挙動しか見えないため、BL-081（Markdown装飾による引用不一致）と同種の「モデルが引用を雑にしている」問題に見えてしまい、コードを疑う動機になりにくかった。(2) `verify_whiteboard_excerpt`が最終的に「たまたま一致する汎用語句」を見つけて`ok: True`を返すことがあるため、失敗が完全な機能停止ではなく「効率が悪いだけ」に見え、個々のログを目視するだけでは79/96という失敗率が定量化されず見過ごされやすい。(3) このバグの引き金となる「current_task_idが指す対象とは別のタスクへSUPERSEDEで先行して成果物を書く」という具体的な組み合わせ自体が、BL-146（2026-08-02実装、SUPERSEDEをcurrent_task_idゲートから明示的に除外）以降に発生しやすくなった可能性がある比較的レアなシナリオであり、通常の同一タスク内レビューでは`current_task_id`と実際にレビューすべきタスクが一致するため表面化しない。

**対応の手掛かり（未実装）:** `expert_node`が`write_agreement`実行後に必ずセットする`state["expert_last_whiteboard_edit"]`（cela_main.py:7695、`get_last_whiteboard_edit()`の戻り値`{phase_id, task_id, version}`、今ターン実際に書き込まれた対象を正確に保持）が既に存在するが、`call_detector`/`detector_node`のどこからも参照されていない（現状はコメントにある通り「次ターンのロールバック判定のため」という別用途のみ）。この値が存在する場合（＝このターンでDeliverableの書き込みが実際にあった場合）はそちらを優先し、`current_task_id`はフォールバックとして扱う設計が候補になる。

**完了条件:** 未定（設計未着手のため）。

**関連:** [BL-076](#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)、[BL-079](#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-146](#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)

---

### BL-153: Facilitatorが`write_agreement`で`entry_type="Deliverable"`のタスク成果物を書き込めてしまう（想定外のロール越権）

**状態:** `open`（記録のみ、実装未着手）

**経緯:** `log/2026-08-03/1347`ドライランをレビューした際にユーザーが発見。Facilitatorが`write_agreement`（`status="Proposed"`, `action_type="SUPERSEDE"`, `entry_type="Deliverable"`）でtask_1_3の成果物本体（3案の定量比較の全文）を書き込んでいた。

`call_facilitator`のツール一覧は`[THINK_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, WRITE_AGREEMENT_TOOL]`（cela_main.py:6562）で、`_check_write_permission`（1776-1804行目）の`ALLOWED_STATUS_BY_ROLE`は`"facilitator": {"Proposed"}`——BL-126 Stage Dで「本質対話の開始提起（`entry_type="EssenceProposal"`）をProposedとしてのみ記録できる」という意図で追加されたものだが、**`entry_type`自体を制限するチェックはどこにも存在しない**。そのため`status="Proposed"`でありさえすれば、Facilitatorは`EssenceProposal`だけでなく`Deliverable`（本来Expertの成果物専用）も`Decision`も`Directive`も、意図的な設計外で書き込めてしまう。

ユーザーの整理：「ファシリテーターの意思決定を残す趣旨でwrite_agreementを使えるようにしていたが、ドキュメントを書き込むことは想定していなかった。ファシリテーターの指摘は成果物直接ではなくホワイトボードに書き込む方が良いかもしれない」——すなわちFacilitatorの所見・指摘は（a）Expertの成果物（Deliverable）を直接上書き・SUPERSEDEするのではなく、（b）ホワイトボードへの注釈（BL-076の`_annotate_whiteboard_with_detector_comment`と同種の仕組み）や、決定事項DBへの`Decision`/`EssenceProposal`としての記録に限定すべき、という設計意図とのギャップ。

**対応（未着手）:** `_check_write_permission`または`_commit_agreement_from_tool`に、ロールごとに許可する`entry_type`の制限を追加する（例: `facilitator`は`{"EssenceProposal", "Decision"}`のみ許可し`Deliverable`/`Directive`は拒否）。既存の`ALLOWED_STATUS_BY_ROLE`と対になる`ALLOWED_ENTRY_TYPE_BY_ROLE`のような表を新設する案が有力候補（詳細設計は未着手）。

**完了条件:** 未定（設計未着手のため）。

**関連:** [BL-126](#bl-126-bl-086の前提エスカレーションはexpertのリアクティブな経路に限定されておりfacilitatoruser-aiがゴール制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計)、[BL-076](#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)

---

### BL-154: decision_extractorのDirective/Deferred自動抽出をissue_logへも橋渡しする

**状態:** `done`

**経緯:** BL-145完了後、ユーザーから「そもそもissueって書いたタスクIDと解決すべきタスクID両方ありましたっけ？」「detectorがタスク遷移をブロックするときはtask_id、last_seen_task_id、defer_to_task_idのどれと現在のタスクIDを比較している？」との質問を受け調査したところ、コードベースには互いを認識しない3つの並行した「先送り事項」追跡機構が存在することが判明した：

1. **`issue_log`**（`write_issue`ツール、BL-096/136）：`detector`/`detector_auto`のみCREATE可、`user`のみRESOLVE/DEFER可。BL-125の遷移ゲート（`_get_blocking_issues_for_transition`、`last_seen_task_id`と`defer_to_task_id`空のみで判定）・BL-144の滞留検知・BL-145のタスク明示化はすべてこのテーブルだけを参照する。
2. **`agreements`テーブルの`entry_type="Directive", status="Deferred"`**（BL-023/BL-082）：`decision_extractor_node`が全Expert/Userターン後に自動抽出する。`call_decision_extractor`のプロンプト（Expert/Userの両ブランチ）が「〇〇は次タスクで扱う」という宣言を検出し`defer_to_task_id`付きで記録する。**Expertは`write_issue`ツール自体を持たない**（`WRITE_ISSUE_TOOL`は`call_detector`と`generate_user_utterance`のみ）ため、これがExpert発の先送り宣言を捕捉する唯一の経路だった。
3. **`plan_drafts`の「先送り事項」セクション**（BL-082、`_append_deferred_note_to_plan`）：上記2の抽出直後に自動追記され、申し送り先タスクのExpert/Detectorへ提示される。

ユーザーが「先送りはすべてissueにまとめたほうがよい？」と相談し、Expertへ`write_issue`の直接アクセスを与える（BL-025のロール分離思想——Detectorの独立監査という趣旨と混同される）のではなく、`decision_extractor_node`が既存の自動抽出と同時にissue_log側へも橋渡しする方針で合意した。

**実装内容（実施済み）：**
1. `_check_issue_permission`の`ALLOWED_ISSUE_ACTIONS_BY_ROLE`へ`"decision_extractor_auto": {"CREATE"}`を追加（`detector_auto`と同型の内部専用ロール。`WRITE_ISSUE_TOOL`のJSONスキーマは無変更でLLMツール呼び出し経路からは到達不能）。
2. `_write_issue_impl`のCREATE分岐を拡張し、`caller_role == "decision_extractor_auto"`の場合のみ`defer_to_task_id`を作成時点で設定可能に（他ロールは常に空文字、無変更）。同一topicが再発した場合、同ロールに限り`defer_to_task_id`を最新の宣言で上書きする（「最新の申し送り先が勝つ」、write_agreementのUPDATEと同じ思想）。
3. `decision_extractor_node`のDirective/Deferred処理（既存の`_append_deferred_note_to_plan`呼び出し直後）に、`_write_issue_impl`（`decision_extractor_auto`ロール、`severity="minor"`、`defer_to_task_id`設定済み）を追加。`target_role`によるゲーティングはしない（Expert/User双方の抽出ブランチが同じ先送り検出指示を持ち、BL-082がかつてUserブランチの非対称バグだった前例を踏まえた判断）。
4. `_build_open_issue_pin_text`（BL-136）を拡張し、`defer_to_task_id`が設定済みの`open`issueには対応予定task_idを表示するようにした（BL-145の`_build_planned_issue_pin_text`と同型のパターン）。
5. BL-125/144/145のコード自体は無変更（`raised_by`を一切見ないため、この経路由来の行も既存ロジックでそのまま扱われることを確認済み）。

**留意点（新規に判明した仕様、今後の参考として明記）：** この経路由来のissueは`defer_to_task_id`が誕生時点から設定されているため、（再発により`severity=major`/`status=escalated`へ昇格した後も）BL-125のブロック判定には決して該当しない——手動DEFER済みissueの既存の扱いと完全に一致する仕様であり新たな抜け穴ではないが、「Expertが同じ懸念を別タスクへ次々と自己先送りし続けても、遷移は一切ブロックされない」という挙動として記録しておく。

新規テスト`tests/test_bl154_decision_extractor_issue_log_bridge.py`（8件: issue_log行の作成、plan_drafts併存の回帰確認、同一ターゲットでの再発エスカレーション、異なるターゲットへの再発時のdefer_to_task_id更新、`decision_extractor_auto`ロールの権限確認、申し送り先未解決時のスキップ、BL-125ゲートの非該当確認、pin textの表示確認）追加。`python -m py_compile`合格、フルオフラインスイート630件Pass（1件failedは本BLと無関係、経緯: `tests/test_bl093_think_tool_scratchpad.py::test_max_tool_iter_raised_to_20`が、本セッション開始前から存在した未コミットの`MAX_TOOL_ITER`変更（20→30、直近コミットHEADでは20のまま）により失敗している。この変更がいつ・誰によって行われたか未確認で、AGENTS.md §7「定数変更の厳格管理」対象のため本BLの範囲外とし、ユーザーへ別途確認を仰ぐ）。

**関連:** [BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-082](#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-144](#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)、[BL-145](#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)

### BL-155: MAX_TOOL_ITERの20→30変更（未コミット差分にBL/Dを事後付与）

**状態:** `done`

**経緯:** BL-154実装検証のためのフルオフラインスイート実行で、`tests/test_bl093_think_tool_scratchpad.py::test_max_tool_iter_raised_to_20`が失敗しているのを発見した。調査の結果、`cela_main.py`の`MAX_TOOL_ITER`が作業ツリー上で既に20→30へ変更済み（直近コミットHEADでは20のまま、対応するコメント追記・BL/D記録なし）だったことが判明した。この変更は本セッションの作業ではなく、いつ・どのような経緯で行われたか記録から追えなかった。AGENTS.md §7（定数変更の厳格管理：「事前承認が必要」「独断で変更しない」）に該当するため、実装は変更せずユーザーへ理由を確認した。

ユーザーからの回答：「task_plan_reviewerによって差し戻された時、task_plannerが差し戻しタスクの内容を1つずつ把握し直す過程でツール使用上限（旧20）に引っかかる事態がログから観測されたため」。BL-093（15→20への引き上げ理由：thinkツール単独呼び出しの許容）と同種の、実ドライラン観測に基づく正当な引き上げであることが確認できたため、正式にBLを起票し決定を記録する。

**対応内容：** `cela_main.py`の値自体は無変更（既に30）。既存の変更履歴コメント（BL-014→BL-028→BL-093の来歴が並記されている箇所、`_query_AI_live`内`MAX_TOOL_ITER`定義直前）へ20→30の理由を追記。テスト`test_max_tool_iter_raised_to_20`を`test_max_tool_iter_raised_to_30`へ改名し期待値を30・理由コメントを更新。フルオフラインスイートの唯一の失敗が解消。

**基本設計:** なし（コメント追記とテスト追従のみ、Plan Mode不要の軽微な変更と判断）。

**関連:** [D-125](../decision_log.md#d-125-max_tool_iterを2030へ引き上げるbl-155)、[BL-154](#bl-154-decision_extractorのdirectivedeferred自動抽出をissue_logへも橋渡しする)、[BL-093](#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ)

---

### BL-156: `_query_AI_live`のAPIエラーリトライ時のprint文言が、BL-122以前の「iter=1へ巻き戻る」挙動のまま実装と食い違っていた

**状態:** `done`

**経緯:** ユーザーがドライラン中のnemotron-3-ultra-550b-a55b:free経由のResourceExhaustedエラー（`Upstream error from Nvidia: ... Worker local total request limit reached (32/32)`）を見て、「APIエラー時には直前の思考は温存されるんでしたっけ？」と質問。調査の結果、次の2点が判明した：

1. `loop_messages`/`reasoning_parts_all`/`iteration_start`はいずれも関数冒頭（リトライのfor attemptループの外）で初期化され、リトライしても再初期化されない（BL-122）。過去に完了したiterationの思考（`"【BL-093: iter N の思考ログ（自動保存）】"`として`loop_messages`へ既に確定済み）・tool結果はリトライ後も温存される。
2. ただしエラーが発生したそのiteration自体については、ストリーミング中（`for chunk in stream:`）に例外が飛ぶため、思考のダイジェスト化・`loop_messages`への追記処理（該当iterationの`msg`構築より後）に到達せず、そのiterationの途中経過は破棄され、同じiteration番号でAPI呼び出しのみやり直される。

この2点自体は正しい設計（BL-046/BL-122での意図的な改善）だったが、リトライ発生時のprint文言「ツールループを**最初から**やり直します」は、BL-122以前（当時は実際にiter=1へ巻き戻っていた）の挙動を説明する隣接コメントがそのまま残っていたため、現在の実装（実際にはこのiterationのAPI呼び出し1回分のみやり直し）と食い違っていた。表示専用の文言が実装の変遷に追従していなかった、BL-151と同種の軽微な事後ズレ。

**対応内容：** print文言を「一時的なAPIエラー、{delays[attempt]}秒後に**このiterationの**API呼び出しをやり直します」へ修正。隣接コメントへBL-122以降は巻き戻らない旨を追記。ロジック自体（リトライ範囲・保持される状態）は無変更。対応するテストは存在せず、既存テストへの影響もない。

**基本設計:** なし（表示文言・コメント修正のみ、Plan Mode不要）。

**関連:** [BL-155](#bl-155-max_tool_iterの2030変更未コミット差分にbldを事後付与)、[BL-122](#bl-122-apiエラー時のツールループ全体巻き戻しリトライbl-009bl-046がモデル変更nemotron後に発生頻度が明らかに増加し実害が拡大している)

---

### BL-157: BL-096の自動バックアップ（detector_auto）が、current_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ、見せかけの再発でmajor/escalated化していた

**状態:** `done`

**経緯:** ユーザー指示「2233のログをレビュー、task_idの遷移が上手くいっていないようです」を受け`log/2026-08-03/2233`をレビュー。`current_task_id`が`task_1_1`のまま進まず、User AIが「task_1_2をやれ」とExpertへ指示したにもかかわらずBL-146のゲートに弾かれてExpertが混乱していた。ユーザーからの追加指示「プロンプトありログも読んで状況を追加で確認して」を受けて深掘りした結果、独立した2つのバグの組み合わせと判明した（もう1件はBL-158）。

グラフ順序（`generate_user_utterance`→`user_detector`(`detector_node`)→`user_decision_extractor`(`decision_extractor_node`、`_resolve_task_transition`を呼ぶ）は確定済みのため、`detector_node`のBL-096バックアップ（`observations`が30字以上の場合に`f"detector_observation_{current_task_id}"`へ自動CREATE）が動く時点では、`current_task_id`はまだ遷移前の値のままである。実例：User AIが「task_1_2をやれ」と発言→`detector_node`（target_role="user"）がこの発言をレビューし、task_1_2の中身（中心部循環15分想定等）についてのobservationsを返す→current_task_idはまだ"task_1_1"のため、無関係のはずのtask_1_2についての指摘が`detector_observation_task_1_1`という同一バケツへ混入→occurrence_countが1→2に上昇→`_bump_issue_occurrence`の不変条件（D-079/D-080：occurrence_count>=2で機械的にmajor/escalated化）が発火→BL-125の`_get_blocking_issues_for_transition`が（正しく設計通り）遷移をブロック。しかし「再発」の実態は、無関係な2つの指摘が粗いバケツキーで衝突しただけであり、同じ懸念が本当に繰り返し見つかったわけではない。

**既存記録との整合:** BL-134エントリには、過去に`detector_auto`起票行がoccurrence_count=11で機械的にmajor/escalated化した事例を「意図通り」と判断した記述がある。本修正はこの判断を`detector_auto`起票行に限定して覆すものであり、D-127として明示的に記録する（サイレントな上書きにしない）。D-079/D-080の原則（「同じtopicが繰り返し検出される＝未解決のまま何度も見つかっている」）は、LLMが明示的に`write_issue`で選んだ固有のtopic文字列には妥当するが、BL-096の汎用catch-allバケツ（「モデルの判断を上書きするものではなく、呼ばなかった場合の保険に留める」という設計意図）には当てはまらない。

**対応内容：** `_bump_issue_occurrence`と`_read_issues_handler`の両方（DB書き込み経路と、read_issues結果への表示上書き経路）に`raised_by != 'detector_auto'`の条件を追加し、detector_auto起票行はoccurrence_countに関わらずseverity='minor'/status='open'のまま維持するようにした。他ロール（`detector`/`user`）の既存挙動は無変更。あわせてユーザー指示「今後このようなコード側の機械的・暗黙的動作のブラックボックスを可視化するために、すべての動作にprintによるでバックログを追加してください」を受け、再発カウント・昇格・抑制の各分岐にprintログを追加した。

**相互作用:** `_get_blocking_issues_for_transition`は`severity='major' AND status='escalated'`のみを対象とするため、本修正後はdetector_auto起票行がこの条件に達しなくなり、BL-158（後述）のチェック対象からも自動的に除外される（両者は同じ関数を単一の判断源として参照）。BL-144/BL-145の滞留検知・タスク明示化機構はdetector_auto起票行に対しては到達不能になるが、これはBL-145がそもそも回避しようとしていた「detector_autoの汎用issueが停滞する」根本原因を本修正が解消した結果であり、想定通りの帰結（他ロール起票行には引き続き有効）。

**基本設計:** Plan modeで実施（Plan agent1体、BL-158と合同設計）。

新規テスト`tests/test_bl157_detector_auto_occurrence_exemption.py`（5件：CREATE/read_issues経由それぞれの抑制確認、他ロールの回帰確認、BL-125ブロック非該当の確認）追加。`python -m py_compile`合格、フルオフラインスイート643件Pass。

**関連:** [BL-158](#bl-158-detectorの-user-レビューパスに未解決issueを残したままの前進を機械的に却下する仕組みを追加)、[BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-134](#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった)

---

### BL-158: Detectorの User レビューパスに、未解決issueを残したままの前進を機械的に却下する仕組みを追加

**状態:** `done`

**経緯:** BL-157と同じログ調査で発見。`generate_user_utterance`は既に`_get_forced_escalated_issues_text`（BL-136、run全体のescalated行を対象、task_idでの絞り込みなし）を注入し「今回の発言でRESOLVE/DEFERを必ず呼べ」とソフトな指示をしているが、実ログでUser AIはこれを無視して直接「task_1_2をやれ」と発言した。この発言は`call_detector`（target_role="user"）でレビューされるが、判定基準は「指示内容の論理破綻」「前タスクの成果物がacceptance_criteriaを満たすか」のみで、「現在のタスクに未解決のescalated issueが残ったまま前進しようとしていないか」は一切チェックしていなかった（実ログで`constraint_issue: "none"`のまま通過したことを確認済み）。

ユーザーの原則：「根本的にはユーザーがタスクを次に進めてはいけませんし、detectorが弾くべきです」。ソフトなプロンプト指示は既に無視される実績があるため、LLMの指示追従に頼らない決定論的なPython側の機械的却下として実装した。

**対応内容：** `write_issue(RESOLVE/DEFER)`が今回のターンで成功したかを追跡する新規フラグを新設（`_LAST_WRITE_AGREEMENT_SUCCEEDED`と同型のパターン：新規グローバル`_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED`、アクセサ`get_last_write_issue_resolve_or_defer_succeeded()`、ツール実行ループでの成功記録、`LineageState`の新規フィールド`user_wrote_issue_resolution`、`generate_user_utterance_node`でのstateへのコピー）。`detector_node`（target_role=="user"のみ、BL-033ブロック直後）へ、BL-125の実ゲートと完全に同一の`_get_blocking_issues_for_transition`を単一の判断源として再利用する決定論的な却下ロジックを追加：ブロック対象issueが存在し、かつ今回のターンで`user_wrote_issue_resolution`が成立していない場合、`call_detector`のLLM判定に関わらず`constraint_issue`を機械的に`"major"`へ上書きする。

**留意点：** この却下は「前進しようとしている発言」に限定せず、ブロック対象issueが残っている限り毎ターン発火する（BL-136の既存の強制文言も同様に無条件のため整合）。`route_after_user_detector`のリトライ上限（3回、超過でreflectionへ）があるため無限ループにはならない。フラグは「今回RESOLVE/DEFERのどれかが成功したか」という粗い真偽値であり、「ブロック中の複数issueのうちどれを解決したか」までは区別しない（最初の実装はこの粒度、必要なら後続で絞り込む）。

**基本設計:** Plan modeで実施（Plan agent1体、BL-157と合同設計、`docs/design/decision_lineage.md`参照）。

新規テスト`tests/test_bl158_detector_rejects_premature_advancement.py`（7件：機械的却下の発火、target_role=="assistant"への非影響、ブロック対象なし時の非発火、`user_wrote_issue_resolution=True`時の非発火、実際のDEFER成功による自然な解消、元コメントの保持、BL-157適用後のdetector_auto起票issueの非該当）追加。`python -m py_compile`合格、フルオフラインスイート643件Pass、BL-096/136/144/145/154関連98件も無退行。実ドライランでの効果確認は次回待ち。

**関連:** [BL-157](#bl-157-bl-096の自動バックアップdetector_autoがcurrent_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ見せかけの再発でmajorescalated化していた)、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-148](#bl-148-orchestratorがcurrent_task_id計画成果物を一切参照できないままexpert選定focus_guidanceを決めていた)

---

### BL-159: cela_main.py全体（約50箇所）のサイレントな機械的・暗黙的動作へprintによる可視化を追加

**状態:** `done`

**経緯:** BL-157/158の調査・修正を通じて、DB内部で静かにoccurrence_countが上がってescalated化する、Detectorの判定が機械的に上書きされる、といった「コード側の機械的・暗黙的な動作」が可視化されておらず、その分ドライランのログから根本原因を突き止める調査が難航したことをユーザーが指摘。「今後このようなコード側の機械的・暗黙的動作のブラックボックスを可視化するために、すべての動作にprintによるでバックログを追加してください」（BL-157/158実装時）に続き、「機械的・暗黙的動作の可視化はコード内のすべての個所について実施してください。全体のデバッグ性を高めます」という全体適用の指示を受けた。

**調査:** Explore agent 2体を使い、cela_main.py全体（約9300行）を2パスに分けて完全走査した（1パス目: 1-500/828-2650/3700-3830/3986-4063/4194-4260/4380-4406/6724-6773/7237-9103、2パス目: 残りの未走査範囲——`call_expert`/`call_detector`/`call_reflection`/`call_facilitator`/`call_task_planner`/`call_task_plan_reviewer`本体、`query_AI`/`_query_AI_live`のストリーミング内部、`init_db`のスキーマ移行等）。合計約50箇所を12段階のTierに分類：
1. halt/不変条件強制（risk=high即halt、facilitation_count/review_count上限、REPLタイムアウト、target_excerptのプログラム側フォールバック）
2. goal/agreement変異（escalate/resolve premise concern、revise_goal、freeze_agreement、Decision/Directive INSERT）
3. 権限/ゲーティング拒否（`_check_write_permission`/`_check_issue_permission`/`_check_repl_code_safety`/Freeze保護）
4. issueライフサイクル（write_issueのCREATE初回・RESOLVE・DEFER）
5. plan注釈のfire-and-forget（`_append_deferred_note_to_plan`/`_append_reviewer_comment_to_plan`の失敗が3箇所の呼び出し元で握りつぶされていた）
6. LLM JSONパース失敗フォールバック（`call_orchestrator`/`call_decision_extractor`/`call_resource_arbiter`/`call_integrator`が`_safe_json_parse`を直接呼び層2リトライを経由しないため、パース失敗が無言でフォールバック値に化けていた）
7. verified_facts上書き（`upsert_verified_fact`の既存値サイレント上書き）
8. ルーティング異常（`route_after_task_plan_reviewer`のみ無印字、`_get_current_task`のタスクID不一致フォールバック、Detectorの2パス判定統合・target_excerpt差し替え、`_aggregate_global_constraints`の壊れたresource_claimsスキップ）
9. モード切替/状態フラグ（Essence Dialogue開始/継続、Expert相談モード開始、Arbiterのリソース超過調停ブランチ全体、task_plannerのcurrent_phase確定、ターン予算枯渇での自然終了）
10. LLM向けone-shot通知がコンソールに見えない（`_build_escalation_resume_notice`/`_build_task_transition_blocked_notice`）＋**実バグ発見**：`run_ai_vs_ai_loop`の決定表示ループで、orchestrator/decision_extractor以外の全ロール（expert/detector/user/task_planner/arbiter/reflection等）向けの分岐が、`print(...)`ではなくトリプルクォート文字列リテラルのまま何もしない死にコードになっており、これらの決定がターン中一切コンソールに出力されていなかった
11. コスメティックなフォールバック（Orchestratorの専門家名空文字フォールバック、whiteboard/plan_drafts更新成功、read_deliverable_fileのnot_found系、`_apply_text_edits`の一致失敗）
12. ストリーミング内部/スキーマ移行（ツール残り回数僅少通知のコンソール非表示、issue_log/agreements/verified_factsの3件のサイレントALTER TABLE）

**対応内容（実施済み）：** ユーザーへAskUserQuestionで3点確認——(a) 未調査範囲も先に完全調査してから修正するか→「先に全体調査を完了させる」を選択、(b) Tier 10/11の低優先度分も含めるか→「Tier 1〜11すべて対応」を選択、(c) 実装単位→「Tierごとに分けて順次py_compile」を選択。この方針に従い、Tier 1から12まで順に約50箇所へprint文を追加し、各Tier完了後に`python -m py_compile`、要所でフルオフラインスイートを実行して回帰がないことを確認した。Tier 10で発見した`run_ai_vs_ai_loop`の死にコードは、既存の`print(f"  [{d['who']}] {d['what']} ({d['why']})")`形式の実際のprint呼び出しへ修正した（唯一の動作変更、他は全て既存動作を変えない純粋な可視化追加）。

**基本設計:** 大量の機械的な追記のためPlan Mode不使用（AskUserQuestionでの方針確認のみ）。

テスト変更なし（出力内容自体を検証するテストは存在しないため）。各Tier完了ごとに`python -m py_compile`、要所で`pytest tests/ -q --ignore=tests/test_f26_detection.py`（643件Pass、複数回確認）を実行。

**関連:** [BL-157](#bl-157-bl-096の自動バックアップdetector_autoがcurrent_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ見せかけの再発でmajorescalated化していた)、[BL-158](#bl-158-detectorの-user-レビューパスに未解決issueを残したままの前進を機械的に却下する仕組みを追加)

---

### BL-160: `_query_AI_live`が、最終回答がreasoningチャンネルへ出力されcontentが空になったケースを「空応答」としてサイレントに握りつぶし、1ターン分のDecision/Directive/Deliverable抽出・タスク遷移シグナルが丸ごと失われる

**状態:** `done`

**経緯:** ユーザー指示「08-04/0715,0807のログをレビュー」を受け`log/2026-08-04/0715`・`log/2026-08-04/0807`をExplore agent2体でレビュー。BL-159で追加したprint可視化により、0807で以下のログが4回中3回出現していることを確認：

```
⚠️ [Decision Extractor] JSON解析に失敗しました（生レスポンス冒頭300字: '(APIから空の応答が返されました)'）。このターンのDecision/Directive/Deliverable抽出は全て失われます。
```

失敗のたびに、その turn の`advances_to_task_id`（BL-024のタスク遷移シグナル）を含む抽出結果が全損し、User/Expertの会話内容は`task_1_3`→`task_2_1`と実質的に進んでいるにもかかわらず、`current_task_id`は実行終了までDBの上では`task_1_2`のまま固着した。会話が先行しDBが追随しないため、以降`write_agreement`が「task_id 'task_2_1' は現在のタスク（'task_1_2'）と一致しません」で正規の成果物登録を拒否し続け、User/Expert双方が毎ターン食い違いを説明・迂回する空転が発生した（BL-125/146/157/158系の症状と同一の見た目だが、原因は全く別）。

**根本原因:** `_query_AI_live`のtools=None非ストリーミング分岐（`cela_main.py:3076-3114`）は、ストリーミング応答を`delta.reasoning`（思考チャンネル、`reasoning_parts`に蓄積）と`delta.content`（回答チャンネル、`content_parts`に蓄積）へ振り分け、最終的に`content = "".join(content_parts)`のみを戻り値として使い（3113行目）、空なら`"(APIから空の応答が返されました)"`という固定文字列を返す（3114行目）。`reasoning_parts`は`_LAST_REASONING_TEXT`グローバルへ保存されるのみで、この空応答フォールバックには一切使われない。

`call_decision_extractor`（`cela_main.py:6403`）はこの関数を`tools`引数なしで呼ぶため必ずこの分岐を通る。実ログを直接確認したところ、3回とも失敗直前の`💭 [Decision Extractor] 思考:`ログに`advances_to_task_id`込みの完全に正しいJSONがそのまま出力されており、`finish_reason=="length"`（打ち切り）の警告ログも一切出ていない。つまりモデルは正しい最終回答を生成し終えていたが、それが丸ごと`reasoning`チャンネル側に出力され`content`チャンネルが空のまま応答が終了し、既存コードには「contentが空でreasoningが非空なら中身を確認する」という経路が存在しないため、正しい答えがそこにあるまま握りつぶされていた。

0715では同じDecision Extractorの思考ストリームが、同一の中国語文断片を数百回繰り返す暴走に陥りJSONが完成しないまま運用者がCtrl+Cで中断している。JSONが完成せず無限化した点は今回の3件（JSONは完成したがcontentに出なかった）と症状は異なるが、いずれも「reasoning/contentの分離が破綻する」という同種の不安定挙動の別の現れである可能性が高い。

**ユーザーからの補足:** この2回のドライランはモデルを従来の`nemotron_3_ultra`ではなく、リリース直後の`deepseek-v4-flash-0731`（ポスト学習モデル）に切り替えて実行しており、モデル自体の挙動不安定性が引き金になっている可能性がある。ただし「reasoning側に完成した答えが出てもプログラム側が拾わずに握りつぶす」という設計上の穴自体は、モデル固有の不具合ではなくコード側の欠落であり、どのモデル・プロバイダーの組み合わせであっても再現しうる。しかもこの握りつぶしは「JSON解析に失敗しました」という警告ログこそ出るが例外や停止には至らないため、BL-159以前は完全にサイレントに（ログにすら残らず）1ターン分の情報が消失していた。

**影響範囲:** `_query_AI_live`のtools=None分岐は`call_decision_extractor`以外にも`call_reflection`（`_query_and_parse_with_retry`経由）が通る共有コードパスであり、同型の実害が起こりうる。加えて調査の過程で、ツール呼び出しループの最終応答（`cela_main.py:3236-3246`、Expert/User AI/Detector/Orchestrator/Resource Arbiter/Facilitator/Integrator/Task Planner等ツールを持つ全ノードが通る経路）にも同一パターンの欠陥（`content = msg.content`のみを使い、空なら同じ固定文字列を返す）が存在することを確認した。

**対応内容（実施済み）：** Plan Modeで設計し3点を修正した。

1. **`tools is None`分岐**（`cela_main.py:3076-3114`）：`content`が空・`_LAST_REASONING_TEXT`（reasoning全文）が非空の場合、reasoning全文を`content`の代替として採用するフォールバックを追加。直前の`finish_reason=="length"`チェック（max_tokens打ち切り検知、既存コード）を通過済みの箇所でのみ発動するため、「打ち切りではなく自発的終了だが答えがreasoning側に出た」ケースにのみ安全に適用される。
2. **ツール呼び出しループの最終応答**（`cela_main.py:3236-3246`）：同型のフォールバックを追加。ただし全iteration累積の`_LAST_REASONING_TEXT`をそのまま使うと過去iterationの無関係な思考が混入し誤抽出のリスクがあるため、既存の`_reasoning_start_idx`（BL-093でreasoning digestの切り出し用に導入済み、`reasoning_parts_all[_reasoning_start_idx:]`で「このiterationだけ」を取り出せる）を再利用し、最終iterationのreasoningのみに意図的にスコープを絞った。
3. **`call_decision_extractor`のリトライ追加**（`cela_main.py:6252`〜）：従来は`query_AI`への単発呼び出しでリトライが一切なく、失敗＝そのターンの抽出が即座に全損していた（`call_reflection`等の他のtools=Noneノードは既に`_query_and_parse_with_retry`で保護済みだった非対称性）。同関数でラップし、他のJSON判定ノードと同水準の層2リトライ保護（既定2回）を持たせた。

`_safe_json_parse`（`cela_main.py:3438-3505`）自体は無変更。フェンスブロック抽出・`{`/`[`優先順位判定・末尾トリム（BL-088/BL-089由来）により、既に「説明文＋JSON」という混在テキストに頑健な設計だったため、reasoningテキストをそのまま渡しても正しく抽出できる。

**基本設計:** Plan modeで実施（Explore agent1体による事前調査＋Plan mode内での根本原因確認、`docs/design/decision_lineage.md`論点109参照）。

新規テスト`tests/test_bl160_reasoning_channel_content_fallback.py`（8件：tools=None分岐でのフォールバック発火・非発火2種の回帰・content優先の回帰、ツールループ最終応答でのフォールバック発火・非発火2種の回帰・content優先の回帰、`call_decision_extractor`のリトライ成功シナリオ、リトライ全滅時のフェイルクローズ回帰）追加。`python -m py_compile`合格、フルオフラインスイート651件Pass。実ドライランでの効果確認は次回待ち（deepseek-v4-flash-0731/nemotron_3_ultra双方の環境で今回の握りつぶしパターンが再発しないことを確認予定）。

**関連:** [BL-159](#bl-159-cela_mainpy全体約50箇所のサイレントな機械的暗黙的動作へprintによる可視化を追加)（本バグはBL-159のprint可視化がなければログからは発見できなかった）、[BL-125](#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-139](#bl-139-decision_extractor_nodeのtransition抽出がllm出力の1項目に依存しており明示的な次タスク指示があってもcurrent_task_idが更新されないことがあった)（トップレベル`advances_to_task_id`欠落への既存フォールバックだが、本バグはcontent自体が丸ごと空になるため`extracted_events`も含め全損しBL-139のフォールバックも機能しない）、[BL-109](#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)

---

### BL-161: `write_agreement`の`phase_id`にフォールバックが一切なく、Expertが省略するとedits（ホワイトボード差分更新）が必ず0件一致で失敗し続ける

**状態:** `done`

**経緯:** ユーザー指示「1018のログをレビュー、エキスパートがホワイトボードのeditに苦戦しています」を受け`log/2026-08-04/1018`をExplore agentでレビュー。Expertの`write_agreement`(action_type="UPDATE", entry_type="Deliverable", edits指定)呼び出しが、同一ターン中に11回連続で以下のエラーを返し続けていたことを確認：

```
edits[0]: old_textが現在のホワイトボード内容に見つかりませんでした
（正規化後の緩い一致も0件でした）。一字一句正確な引用か確認してください。
【参考：現在のホワイトボード内容の実際の先頭部分】

```

MAX_TOOL_ITER=30のうちiter=2〜15（ほぼ半分）をこの失敗ループに空費し、iter=14ではExpertが全角チルダ（〜）を誤って原因と推測し引用を微調整して再試行するも失敗、最終的にiter=16でeditsを諦め全文書き直し（SUPERSEDE相当）に切り替えたところでこのターンが終わっていた。BL-151（実際の格納内容の先頭400字をエラーへ含め自己修復させる機能）の診断スニペットが常に空文字のまま表示されており、Expertは自己修復のヒントを一切得られていなかった。

**根本原因:** `_commit_agreement_from_tool`（`cela_main.py:1864`〜）の`phase_id = args.get("phase_id", "")`（フォールバックなし）が、直後の`tid = args.get("task_id") or task_id`（呼び出し元から渡された現在タスクIDへフォールバック、BL-040由来）と非対称だった。実ログのExpert呼び出し（iter=2）には`phase_id`・`task_id`のキー自体が存在せず、`_find_active_deliverable_agreement`（`cela_main.py:1847-1861`、`(phase_id, task_id)`の完全一致で既存Deliverableを識別するBL-084由来の仕組み）が`phase_id=""`と一致する行を見つけられないため`target=None`→`old_content=""`→`is_whiteboard=False`→`base_content=""`→`_apply_text_edits("", edits)`が呼ばれ、どんなold_textを渡しても必ず0件一致で失敗する構造になっていた。

`task_id`には既に`_effective_current_task_id_from`/`_task_id_from`という「省略時は呼び出し元の現在タスクへフォールバックする」機構（BL-146）が存在し、`phase_id`にも全く同型の`_phase_id_from(state)`（`cela_main.py:2647-2648`、`(state.get("current_phase", {}) or {}).get("phase_id") or _CURRENT_PHASE_ID`）が既に定義されていたが、`write_agreement`のTOOL_DISPATCH配線（`cela_main.py:2692`付近）がこの関数を一度も呼んでいなかっただけの単純な配線漏れだった。

**対応内容：** `_commit_agreement_from_tool`・`_write_agreement_impl`双方のシグネチャへ`phase_id: str = ""`引数を追加し、`_commit_agreement_from_tool`冒頭を`phase_id = args.get("phase_id") or phase_id`（tidと同じパターン）へ変更、フォールバック発動時にprint通知（BL-159の可視化方針を踏襲）を追加。`_write_agreement_impl`から`_commit_agreement_from_tool`への呼び出しへ`phase_id`を追加で渡し、TOOL_DISPATCH配線（`write_agreement`）へ`phase_id=_phase_id_from(state)`を追加した。CREATE/UPDATE/SUPERSEDEいずれも`_commit_agreement_from_tool`内で同一の`phase_id`変数を共有するため、この1箇所の修正で全action_typeに一律適用される。`_safe_json_parse`と同様、BL-151のエラースニペット自体は無変更（`target`が正しく見つかるようになれば`old_content`が実際の内容になり、スニペットは自動的に機能する）。

**基本設計:** なし（Plan Mode不使用、根本原因の調査自体をログレビューの中で完了済みで、修正内容が3箇所へのパラメータ追加＋配線という小規模かつ明確なものだったため、ユーザーの「まず修正し、後にドキュメント整備してください」指示に従い直接実装）。

新規テスト`tests/test_bl161_write_agreement_phase_id_fallback.py`（4件：UPDATE(edits)でのフォールバック成功、フォールバック元情報（current_phase）が無いstateでの従来通りの失敗回帰、args明示指定時の優先順位回帰、CREATEでのフォールバック確認）追加。`python -m py_compile`合格、既存`tests/test_bl146_write_agreement_current_task_gate.py`・`test_bl131_write_agreement_task_id_validation.py`・`test_bl084_deliverable_task_id_identification.py`・`test_bl080_supersede_deliverable_whiteboard_writeback.py`・`test_bl151_apply_text_edits_error_snippet.py`（計30件）無退行、フルオフラインスイート655件Pass。

**副次所見（記録のみ、本BLの対応範囲外）：** Detector自動注釈（`_annotate_whiteboard_with_detector_comment`）がMarkdownテーブルセルを複数の物理行に分割し末尾に浮いた` |`を残す整形になっており、今後のExpertの一字一句引用をさらに脆くする要因になっている。今回の11連続失敗の直接原因ではなかったため、別途後続BLとして切り出すか判断が必要。

**関連:** [BL-146](#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)（`task_id`側の同型フォールバックの前例）、[BL-084](#bl-084-entry_typedeliverableのupdatesupersedeがtopic文字列ドリフトでeditsを0件0件失敗させ続けていたbl-074の未着手項目の再発)（`(phase_id, task_id)`識別への切替そのものの経緯）、[BL-151](#bl-151-revise_goalのold_textがプロンプト表示専用の絵文字装飾を含んでいたため9回以上自己修復に失敗し続けた)（本バグにより機能していなかった自己修復用エラースニペット機能）

---

### BL-162: ゴール改定（revise_goal）直後のDetector goal_change監査が、旧ゴール文を取得する手段を持たず判定基準の1つを実質評価できない

**状態:** `done`

**経緯:** ユーザー指示「ログレビューを続行、ゴールが書き換えられましたが、次のdetectorがちょっと困っています」を受け`log/2026-08-04/1123`の続きをExplore agentでレビュー。task_1_2で予算上限（最大3台）と絶対要件（30分保証に必要な9〜13台）・労基法（常駐2名=年間3,600時間で法定上限超過）の構造的矛盾が定量化され、Facilitatorのエスカレーションを経てUser AIが`revise_goal`（BL-086）で予算・待ち時間保証・安全ODD・エッジケースの4セクションをフェーズ分割方式へ改定。改定自体は成功（同一内容の重複呼び出しが1回あったが実害なく自己収束）。

改定直後、`review_mode="goal_change"`監査（BL-126 Stage B）でDetectorが判定基準1「旧文が置換ではなく追記として保持されているか（新しい文の中に、元の文の内容が包含されているか）」を確認しようとして`read_verified_fact({"topic_keyword":"ゴール"})`→`not_found`、`read_verified_fact({"topic_keyword":"goal"})`→`not_found`、`read_deliverable_file`を同様に2回→いずれも`not_found`、`read_issues(list_all=true)`を最後の手段として試行するも該当なし、という計5回の空振りの末「旧ゴール文が不明のため包含関係は確認不可」と自ら申告して`constraint_issue: "none"`を返した。MAX_TOOL_ITER超過やクラッシュには至らず実行はtask_1_3へ正常に継続しており、実害は「判定基準1を実質評価できていない」という監査品質の欠落にとどまる。

**根本原因:** `generate_user_utterance_node`（`cela_main.py:7437`付近）は、`revise_goal`成功時に`_LAST_GOAL_REVISION`ブリッジ（`{new_goal_text, old_goal_text, escalation_id}`）から`new_goal_text`のみを`state["goal"]`へ反映し、`old_goal_text`はその場で参照されず破棄していた。一方Detectorが持つツール（`read_verified_fact`/`read_deliverable_file`/`read_issues`）はいずれも「現在の」DB状態しか読めず、改定前のゴール文のスナップショットはどこにも永続化されていないため、Detectorには原理的に取得手段がなかった。BL-160/BL-161と同型の「橋渡し変数は計算されているのに、必要な消費先まで配線されていない」というクラスのバグ。

**対応内容：** `LineageState`へ新規フィールド`goal_revision_old_text: str`を追加。`generate_user_utterance_node`が`_goal_revision.get("old_goal_text") or ""`を`state["goal_revision_old_text"]`へ橋渡しするよう変更（`goal_revision_pending_review`と同じ単発フラグ的ライフサイクル、消費側は`review_mode`のゲートで自然に守られるため明示的なリセットは不要）。`call_detector`のgoal_change用`domain_role_instruction`（判定基準1の直前）へ、旧文（`state.get("goal_revision_old_text", "")`、取得不可時は明示的なフォールバック文言）と新文（既存の`goal`変数、System Goal再掲と同一値）を直接埋め込み、Detectorがツール呼び出しなしに両者を直接比較できるようにした。

**基本設計:** なし（BL-161と同様、根本原因の調査自体をログレビューの中で完了済みで、修正内容が3箇所（LineageState定義・橋渡し・プロンプト埋め込み）の明確な追加だったため、ユーザーの「修正してください」指示に従い直接実装、ドキュメントは事後整備）。

新規テスト`tests/test_bl162_goal_revision_old_text_bridge.py`（4件：橋渡し成功、goal改定なし時に橋渡しされないこと、old_goal_textがNoneの場合に空文字へフォールバックすること、call_detectorのgoal_change分岐が実際にold_goal_textを埋め込んでいることのソース確認）追加。`python -m py_compile`合格、既存`tests/test_bl126_stage_b_goal_change_review_mode.py`（6件）無退行、フルオフラインスイート659件Pass。実ドライランでの効果確認は次回待ち。

**関連:** [BL-160](#bl-160-_query_ai_liveが最終回答がreasoningチャンネルへ出力されcontentが空になったケースを空応答としてサイレントに握りつぶし1ターン分のdecisiondirectivedeliverable抽出タスク遷移シグナルが丸ごと失われる)、[BL-161](#bl-161-write_agreementのphase_idにフォールバックが一切なくexpertが省略するとeditsホワイトボード差分更新が必ず0件一致で失敗し続ける)（同型の「橋渡し変数の配線漏れ」バグの前例2件）、[BL-086](#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（revise_goal/GoalShiftEventそのものの導入経緯）

---

### BL-163: `revise_goal`成功時、既に承認済みの過去タスクへ「新ゴールとの整合性要再確認」issueを機械的に起票する

**状態:** `done`

**経緯:** BL-162の調査（`log/2026-08-04/1123`）を受け、ユーザーから「ゴール承認後にタスクを1_1からやり直させた方が良いか。それまでのタスクは旧ゴールに基づいて成果物が提出されている。のちのタスクで気づいて過去タスクの成果物を書き直してくれるかもしれないが、どちらがよいか」と設計相談があった。

AIは以下を整理して回答した：全面リスタートは、矛盾していたのは特定の前提・数値だけであるにもかかわらずコスト（トークン・時間）が大きく、CELAの既存アーキテクチャ（SUPERSEDEによる他タスク改訂、BL-096のissue管理、BL-144の滞留検知、BL-145のタスク明示化）が「前進しながら必要な箇所だけ修正する」設計思想であることとも不整合。一方、後続タスクが偶然気づくことへ期待する完全受け身な設計は見落としリスクがある。折衷案として「ゴール改定成功時に、影響しうる既存タスクへ`write_issue`で『新ゴールとの整合性要再確認』を機械的に起票し、既存の解決フロー（RESOLVE/DEFER、BL-144滞留検知）に確実に乗せる」を提案し、ユーザーが「これでいきましょう。注記が最初に出てくれば、AIの混乱も少ないはずです」と採用した。

**設計上の2択（AskUserQuestionで確認）：**
1. **issue重大度**——`minor`/`open`（採用）: バックログとして静かに記録。BL-136の強制RESOLVE/DEFER文言（major/escalated対象）は発動させず、無関係な現在タスク遂行中に毎ターン催促される煩雑さを避ける。／`major`/`escalated`（不採用）: 毎ターン強制文言が発動し、無関係なタスク進行中も催促され続ける。
2. **「注記が最初に出てくれば」の実現範囲**——既存の起票の仕組みに乗せるだけ（採用・小規模）: issue_logへCREATEするのみで、User AIの既存open issue一覧（`_build_open_issue_pin_text`）・Detector Pass-1の`escalation_pin_block`等、既存のグローバルなpin表示に自然に乗る。／該当task_idへ触れた瞬間だけピンポイント注入する新規サーフェシング機構（不採用・大規模）: 既存CELAにtask_id単位で絞り込むピン留め機構が一切無く、新規設計・実装が必要になるため今回はスコープ外（将来必要になれば別BL）。

**対応内容（実施済み）：** EnterPlanModeでExplore agent1体による事前調査（`_revise_goal_tool_impl`が`state`非依存で`conn`/`run_id`のみから完結できること、`_write_issue_impl`のCREATE分岐、`detector_auto`/`decision_extractor_auto`と同型の内部自動起票ロールパターン、`RESOLVING_DELIVERABLE_STATUSES`による完了済みタスクの列挙方法、既存pin機構が全てグローバルスコープでtask_id絞り込みを持たないこと）を経て設計・実装した。

1. `ALLOWED_ISSUE_ACTIONS_BY_ROLE`へ新規ロール`"revise_goal_auto": {"CREATE"}`を追加（`detector_auto`/`decision_extractor_auto`と同型、LLMツール呼び出し経路からは到達不能）。
2. `_revise_goal_tool_impl`の成功パス末尾（`db_append_decision`直後・`return`直前）へ、`get_agreements_from_db(conn, run_id)`を`reversed`で走査し、`_find_active_deliverable_agreement`（BL-084）と同型の「`(phase_id, task_id)`ごとに最初に出会った（＝最新の）行だけを採用する」dedupロジックで、`entry_type="Deliverable"`かつ最新statusが`RESOLVING_DELIVERABLE_STATUSES`（Approved/Approved_with_Conditions/Implicitly_Accepted）に含まれる全タスクを列挙し、それぞれへ`_write_issue_impl`を`caller_role="revise_goal_auto"`で直接呼び出す処理を追加した。topicは`f"goal_revision_consistency_check_{phase_id}_{task_id}"`（タスクごとに一意、再度のゴール改定で同一タスクが再度対象になった場合はD-079/D-080の通常の再発カウント機構がそのまま働く）。

`_write_issue_impl`本体・既存3種のpin builder（`_build_open_issue_pin_text`/`_get_forced_escalated_issues_text`/`escalation_pin_block`）は無変更。

**テスト時に判明した注意点：** `agreements.id`はミリ秒タイムスタンプ生成（`f"AG-{int(time.time()*1000)}"`）のため、テストで`write_agreement`を間を置かず連続実行すると同一idの行が複数でき、`get_agreements_from_db`の`ORDER BY id`が新旧の判別に失敗しうることが分かった（実運用ではLLM呼び出し等で十分な間隔が空くため問題にならない）。テストでは`write_agreement`経由ではなく、明示的な連番idでagreements行を直接INSERTするヘルパーに切り替えて決定論的な順序を保証した。

新規テスト`tests/test_bl163_revise_goal_auto_flags_past_tasks.py`（6件：承認済み2タスクへの起票・severity/status確認、Rejectedのみのタスクの対象外確認、完了済みタスク0件でのクラッシュ非発生、同一タスクへの複数UPDATE履歴があっても1回のみ起票、最新状態がSupersededへ変わった場合の対象外確認、`revise_goal_auto`ロールの権限登録確認）追加。`python -m py_compile`合格、既存`tests/test_bl086_escalation_freeze_goal_revision.py`・`test_bl096_issue_log.py`・`test_bl136_issue_visibility_and_transition_gate.py`・`test_bl144_escalated_issue_staleness_threshold.py`・`test_bl154_decision_extractor_issue_log_bridge.py`（計101件）無退行、フルオフラインスイート665件Pass。

**基本設計:** Plan modeで実施（Explore agent1体、AskUserQuestionでの2択確認込み、`docs/design/decision_lineage.md`参照）。

**関連:** [BL-162](#bl-162-ゴール改定revise_goal直後のdetector-goal_change監査が旧ゴール文を取得する手段を持たず判定基準の1つを実質評価できない)（本BLの発端となった調査）、[BL-086](#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（revise_goal/GoalShiftEventそのものの導入経緯）、[BL-096](#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)（issue_log機構そのもの）、[BL-144](#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)（滞留検知）、[BL-154](#bl-154-decision_extractorのdirectivedeferred自動抽出をissue_logへも橋渡しする)（内部自動起票ロールの直近の前例）

---

### BL-164: Detectorへの「Recent Decisions（参考程度）」節が、前回decisionの生reasoning（`internal_thought_process`）を丸ごと埋め込んでおり、supersede済みホワイトボードの古い引用をDetectorが誤採用しMAX_TOOL_ITERを浪費する

**状態:** `done`

**経緯:** BL-163完了後、ユーザー指示「1123のログの続きをレビュー」を継続。`log/2026-08-04/1123`のtask_1_3（財務持続性モデル構築）監査フェーズで、`Detector`ノードが同一ターン内で`verify_whiteboard_excerpt`を計29回中11回（38%）失敗させ続け、MAX_TOOL_ITER=30に到達し「⚠️ [Detector] 最終iteration（30）のためツールを外し、テキスト最終応答を強制します」が**同一run内で2回**発火（`log/2026-08-04/1123/log_no_prompt.md`行11484・14373）していることを発見した。

**根本原因（コード・プロンプトダンプ双方で確認済み）：** `recent_decitions = json.dumps(get_decisions_from_db(conn, run_id)[-2:], ensure_ascii=False)`（`cela_main.py:5812`）が、直近2件の`decisions`テーブル行を`get_decisions_from_db`の`SELECT *`結果のまま（`internal_thought_process`列を含む）JSON化し、プロンプトの「Recent Decisions（参考程度）」節（`cela_main.py:6204`）へ埋め込んでいる。

task_1_3のホワイトボードはVer.3→Ver.5→Ver.7と全面改訂を繰り返しており（「現実的複合リスク」行の実質赤字が296万円→3,436万円へ桁ごと変化）、監査対象の`Detector`呼び出し時点で「直近2件」に選ばれたのは：
1. `D-1785815485253`：**直前のDetector自身が、Ver.3ホワイトボードをmajor判定で却下した際の判定record**。その`internal_thought_process`（生の思考過程、数千字規模）に、Ver.3の一字一句引用「`| **現実的複合リスク** | 需要 −20% + 電気代 +30% + 冬季 10 日 + タクシー +25% | **296** | **✅（ギリギリ）** |`」がverbatimで残っていた。
2. `D-1785816289859`：Expertの再提出イベント（要約のみ、全文は含まれない）。

新しいDetectorはこの「参考程度」ブロックから引用文字列を誤って`target_excerpt`候補として採用し、実際に監査対象となっている最新ホワイトボード（Ver.5/7、296ではなく3,436に更新済み）には存在しないテキストを`verify_whiteboard_excerpt`で検証し続けた。プロンプトダンプ（`log_with_prompt.md`行30106）で該当引用が`internal_thought_process`内にverbatimで含まれることを直接確認済み。同一の古い引用（「253」「296」）は、後続の**別のDetector監査（2回目、no_prompt行12477-14405）でも再出現**しており、偶然の一度きりの事故ではないことを確認した。

**なぜ構造的に再現しやすいか：** CELAの主要な品質担保ループは「Detector却下（major判定・古い版への引用付き）→Expert修正→Detector再監査」であり、`[-2:]`という設計は、まさにこの再監査タイミングの直前2件として「却下判定（＝supersede直前版への引用を含むinternal_thought_process）＋直後の修正提出」を拾いやすい。つまり最も重要な「修正が実際に効いたか」を検証するタイミングでこそ、最も汚染されやすい。

**実測された被害規模：** 1回目のDetector監査ループ（no_prompt行10579-11519）で29回中11回（iter=11,12,14,15,16,18,21,23,24,26,28）が`verify_whiteboard_excerpt`失敗、2回目（no_prompt行12477-14405）でも同型の失敗パターンを確認。両方とも最終的にMAX_TOOL_ITER=30へ到達し、ツールなしの強制テキスト応答（BL-093が警告する「出力が途中で切れるリスク」に該当する状況）に追い込まれた。今回はJSON自体は出力できたが、より複雑な監査では出力途中切断の実害に発展しうる。

**BL-152との違い：** 症状（`verify_whiteboard_excerpt`の大量失敗によるMAX_TOOL_ITER浪費）はBL-152と同型だが、原因は別。BL-152は「誤ったtask_idのホワイトボードと照合していた」という参照先の取り違え。本BLは「参照先（現在の最新ホワイトボード）は正しくプロンプトに提示されているが、Detector自身が別ブロック（過去decisionの生reasoning）から古い引用を誤って拾ってしまう」というプロンプト構成・モデル側の誤読み合わせの問題。

**ユーザーとの設計討議：** BL起票後、ユーザーから2点質問があった。(a) 「internal_thought_process除去でDetectorの監査能力の粒度が落ちないか」→`cela_main.py:5885-5903`の`thought_process_audit`ブロックが、まさに「ハルシネーション・事後正当化の検出」という目的のために**現在ターンのExpert/User AI自身の思考過程のみ**を専用に提示しており、これが本来の「思考ログを監査する」機構である。`recent_decitions`に含まれる`internal_thought_process`は過去のDetector自身の判定recordであり用途が異なる重複混入であって、除去による実質的な監査能力の低下はないと回答。(b) 「Detectorに見せるべき情報構造をゼロから設計するなら」→`call_detector`の既存構成を洗い出し、4層（Tier A: 監査対象そのもの＝`whiteboard_block`/`agreements_text`/`acceptance_criteria`、Tier B: 主張の裏付け証拠＝BL-033 python_repl記録、Tier C: 今回ターンの挙動監査＝`thought_process_audit`/`write_agreement_status_block`、Tier D: 継続性・参考情報＝`recent_decitions`）に整理した結果、Tier D以外は既にsupersede-aware・適切にスコープされており、修正が必要なのはTier Dのみと回答。ゼロベースでも大枠は現行構成に近く、大規模な情報構造の再設計は不要と判断した（詳細は`docs/design/decision_lineage.md`参照）。

**実装内容（完了済み）：**
1. `recent_decitions`（`cela_main.py:5812`付近）を`SELECT *`の生行から、`who`/`what`/`why`のみのキュレーション済み要約へ変更。`internal_thought_process`・`run_id`・`reason_missing`・`id`/`timestamp`等の生列を除外。
2. 「Recent Decisions（参考程度）」節の直前（`cela_main.py:6204`付近）へ、「直近の決定事項は状況把握のための参考情報であり、ここに含まれる引用（whyの内容等）は執筆時点のホワイトボード内容である可能性があり、既に上書き・改訂されている場合があります。target_excerptやverify_whiteboard_excerptの根拠には、必ず下記【R4: 現在タスクの成果物・最新ホワイトボード】節の内容のみを使用してください」という出所限定の注意書きを追加。既存のBL-079指示（引用前にverify_whiteboard_excerptで検証）を、引用の出所を明示的に限定する形で補強。ブロックの並び順（BL-104のキャッシュ効率化原則）は無変更。

`recent_decitions`は`call_detector`関数内でのみ定義・使用され他ノードでの再利用はないが、`call_detector`はDetector（Domain Review・数値監査の両パス）全ての共通経路であり、CELAの全監査呼び出しに影響する変更である。

**テスト：** 新規`tests/test_bl164_recent_decisions_no_raw_reasoning_leak.py`（4件：`recent_decitions`が生データダンプでなくなっていることのソース確認、出所限定の注意書きが実際に埋め込まれていることのソース確認、`_query_and_parse_with_retry`をmonkeypatchして実際に`call_detector`を走らせRecent Decisions節のJSONペイロードから`internal_thought_process`キーが消え`who`/`what`/`why`は残ることを確認する実行時テスト、decisionsが0件でもクラッシュしないことの回帰確認）追加。`python -m py_compile`合格、既存Detector関連テスト（`test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`・`test_bl093_think_tool_scratchpad.py`・`test_bl104_project_plan_toc_and_prompt_reorder.py`・`test_bl126_stage_b_goal_change_review_mode.py`・`test_bl162_goal_revision_old_text_bridge.py`、計102件）無退行、フルオフラインスイート669件Pass。実ドライランでの効果確認は次回待ち。

**関連:** [BL-152](#bl-152-verify_whiteboard_excerptが今レビューすべき成果物ではなく常にcurrent_task_idのホワイトボードだけを見ていた)（`verify_whiteboard_excerpt`大量失敗という同型症状の前例、原因は別）、[BL-079](#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる)（`verify_whiteboard_excerpt`による引用前検証の仕組みそのもの）、[BL-093](#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ)（MAX_TOOL_ITER到達時の出力途中切断リスクの既存の警告）、[BL-162](#bl-162-ゴール改定revise_goal直後のdetector-goal_change監査が旧ゴール文を取得する手段を持たず判定基準の1つを実質評価できない)（同一ログレビューセッションでの直前の発見）

---

### BL-165: `write_agreement`のCREATE分岐ログが、実際のホワイトボードバージョン番号を無視し常に`"Ver.1"`と誤表示する

**状態:** `open`（記録のみ、`print`文言の軽微な修正で対応可能）

**経緯:** BL-164の調査中に副次的に発見。`_write_agreement_impl`のDeliverable CREATE分岐（`cela_main.py:1982`）：

```python
print(f"  📋 [Whiteboard] write_agreement経由の成果物 '{topic}' をwhiteboard_drafts Ver.1として保存しました（phase={phase_id}, task={tid}）。")
```

が、直前で`apply_whiteboard_patch`から受け取った実際のバージョン番号`v`（`_LAST_WHITEBOARD_EDIT = {"phase_id": phase_id, "task_id": tid, "version": v}`で正しく保持されている）を使わず、文字列`"Ver.1"`をハードコードしている。同一イベントで`apply_whiteboard_patch`自身のログ（`cela_main.py:3994`、`f"...task_id={task_id}をVer.{new_version}に更新しました..."`）は正しく実際のバージョン番号を出している。

実際のログ（`log/2026-08-04/1123/log_no_prompt.md`行10388-10389）で、同一のwrite_agreement呼び出しに対し「`task_id=task_1_3をVer.5に更新しました`」と「`'task_1_3 財務持続性モデル構築' をwhiteboard_drafts Ver.1として保存しました`」という矛盾する版数表示が並んで出力されていることを確認した。

**影響：** DB上の実際のバージョン管理（`whiteboard_drafts`テーブル・`_LAST_WHITEBOARD_EDIT`）自体は正しく、機能的な実害はない。ただしログを読む人間・エージェント双方を混乱させる（BL-164の調査時、この矛盾表示が一時的な調査の混乱要因になった）。

**対応の手掛かり（未実装）：** `cela_main.py:1982`の`"Ver.1"`を、`apply_whiteboard_patch`の戻り値`v`（同関数内で既に取得済み）へ差し替えるだけで解消する見込み。

**関連:** [BL-164](#bl-164-detectorへのrecent-decisions参考程度節が前回decisionの生reasoninginternal_thought_processを丸ごと埋め込んでおりsupersede済みホワイトボードの古い引用をdetectorが誤採用しmax_tool_iterを浪費する)（同じ調査の中で発見）

---

### BL-166: `_build_agreements_context`のアイコン・ラベル判定が、Rejectされた成果物を「✅承認済み」と表示してしまう

**状態:** `done`

**経緯:** ユーザー指示「1123のログをくまなくレビューして、他にバグがないかをクロールしてほしい」を受けた継続クロール中に発見。ドライランが一時停止・再開を繰り返す過程（`log/2026-08-04/1123`→`1355`→`1435`、いずれも同一`run_id=1785806334-3666e80a`のCtrl+C再開）で、`log/2026-08-04/1123/log_no_prompt.md`行16265以降、User AIが「task_1_3（財務持続性モデル構築）はCompleted and approved (Ver.9)」と誤認し、未解決の労基法違反issueを残したままtask_1_4へ進もうとしていたことを発見した。

**実態確認：** 実際にはtask_1_3は`status="Rejected"`のまま一度も承認されていない。`cela.db`を直接クエリし、該当agreements行（`AG-1785818709566`、topic="task_1_3 財務持続性モデル構築"）が`status="Rejected"`のまま最新であること、Approvedへの更新が一度も存在しないことを確認済み。Ver.9はホワイトボードの実体としては財務モデルの再提出ではなく却下メモそのもの（`whiteboards/phase_1_task_1_3_V9.md`の中身が「Rejecting task_1_3 Ver.8 due to...」という却下文）だった。

**根本原因（コード確認済み）：** `_build_agreements_context`（`cela_main.py:4793`）のアイコン判定：

```python
elif entry_type == "Deliverable":
    icon = "📄" if status == "Proposed" else "✅"
```

（`cela_main.py:4826`）が、Deliverableの場合`status`が`"Proposed"`以外なら`"Approved"`も`"Approved_with_Conditions"`も、そして**`"Rejected"`も**無条件で✅にしてしまう。ラベル側も`type_label = "[成果物]"`固定（`cela_main.py:4835-4836`）で、Decision/Directiveエントリには存在する却下時`[却下事項]`分岐（`cela_main.py:4843-4844`、`elif status == "Rejected": type_label = "[却下事項]"`）がDeliverableには一切ない。つまり同じ関数内でDecision/Directive用の分岐は正しく保護されている（Rejectedは`else: icon = "⚠️"`に落ちる）のに、Deliverable用の分岐だけこの保護が欠けている。

`_build_agreements_context`（`_build_agreements_context_from_db`経由）はUser AI・Expert・Detector・Orchestratorなどほぼ全ノードの「決定事項DB」表示に共通で使われているため、Rejectされた成果物がある限り、以降のどのノードの目にも「✅ [成果物]」として映り続ける構造的欠陥。実際のcontent_previewは「Rejecting task_1_3 Ver.8 due to...」というテキストで始まるため完全に不可視というわけではないが、✅アイコンという強い視覚シグナルと矛盾する自己矛盾的な表示になっており、大量のDB内容を読む中で見落とされるリスクが高い。

**BL-062との違い：** BL-062（`partial`実装済み）は「Detectorの却下判定が、DB上のstatusへ正しく反映されるか（SUPERSEDE/UPDATE運用指示の欠如）」という**書き込み側**の問題だった。今回発見したのは、status="Rejected"というDBへの反映自体は正しく起きているにもかかわらず、**表示ロジックがそれを握りつぶす**という一段深い、別の欠陥。

**対応内容（実施済み）：** 既存の`RESOLVING_DELIVERABLE_STATUSES`（`{"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}`）を再利用し、Deliverableのアイコン判定を`status == "Proposed"`（📄）／`status in RESOLVING_DELIVERABLE_STATUSES`（✅）／それ以外（⚠️）の3分岐へ変更した。ラベルも`status == "Rejected"`の場合`"[却下成果物]"`を返すよう追加した。

新規テスト`tests/test_bl166_rejected_deliverable_icon.py`（6件：Approved/Approved_with_Conditions/Implicitly_Acceptedが引き続き✅になること、Proposedが引き続き📄になること、Rejectedが✅ではなく⚠️[却下成果物]になること、正常な合意事項と混在しても各行が正しく区別されること）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。

**関連:** [BL-062](#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（Rejectedの書き込み側を解消した前例、今回は表示側）、[BL-164](#bl-164-detectorへのrecent-decisions参考程度節が前回decisionの生reasoninginternal_thought_processを丸ごと埋め込んでおりsupersede済みホワイトボードの古い引用をdetectorが誤採用しmax_tool_iterを浪費する)（同一クロールセッションでの直前の発見）、[BL-167](#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)・[BL-168](#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない)（同一クロールで連鎖的に発見した「旧ゴールの数値が残り続ける」問題群）

---

### BL-167: Reflection内のstagnant issue滞留検知が、defer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける

**状態:** `done`

**経緯:** BL-166と同じ調査の中、ユーザーから「タスクが再構築すると、issueなどのタスク番号の依存関係が崩壊する可能性があるし、タスク再構築後にどのタスクから再開されるかわからない。旧ゴールの2台という数字が残り、issueも触られていない状態が続いている」との指摘を受け、`log/2026-08-04/1435`（`1123`→`1355`→`1435`と再開を繰り返した末のドライラン）を調査した。

**確認した事実：** Reflectionが3件のescalated issue（「車両台数2台ではサービス要件を満たせない」「オペレーター常駐要件と研修費前提の矛盾」「オペレーター4名体制での労基法違反」）をユーザーノード3回通過での滞留として検出し、discussion_statusを機械的にstagnant化した（`log_no_prompt.md:756`）。しかし実際にTask Plannerへタスク再構築の引き金として引き継がれたのは、労基法違反の1件のみだった（`log_no_prompt.md:757`の`issue_ids=['71be6b5b-3790-4eaa-ab7d-a95f7efcdd12']`、`log_no_prompt.md:1021-1022`のTask Plannerへのプロンプトにも1件しか含まれていないことを確認）。

**根本原因（コード確認済み）：** `cela_main.py:8654`のフィルタ：

```python
_formalizable_stale = [i for i in _stale_escalated if not i.get("defer_to_task_id")]
```

は「既に`defer_to_task_id`が設定されている＝受け皿タスクが既にある」という前提で除外している（コメント: 「二重の受け皿を避けるため」）。しかし「車両台数2台...」issueは過去（task_1_1実行時）に`defer_to_task_id="task_1_2"`が、「オペレーター常駐要件と研修費前提の矛盾」issueも`defer_to_task_id="task_4_1"`が既に設定されていた（`cela.db`の初期issue起票時点のダンプで確認済み）。ところが**task_1_2は既にApproved済みで完了しており、二度と実行されない**。受け皿として指定されたタスクが実際に完了したかどうか、そのタスクが本当にissueを解決（`status="resolved"`化）したかどうかは一切検証されず、`defer_to_task_id`が過去に一度でも設定された事実だけで、恒久的にBL-145の再構築対象から除外され続ける「永久迷子」状態になる。労基法違反issueだけが`defer_to_task_id`未設定（比較的新しく起票されたため）だったために唯一通過し、他の2件は構造的に埋もれ続けている。

**実害：** Task Plannerは労基法issueのみを渡されたため、再構築後のtask_1_1の説明・受入基準は「車両購入費（2,500万円/台）」「1億円÷2,500万円＝4台が理論上限」という**ゴール改定前**の車両単価のまま再出力された（`log_no_prompt.md:1174-1178`）。BL-168で判明した`verified_facts`の同型の欠陥と合わさり、旧ゴールの前提が延々と生き続ける構造になっている。

**副次確認（タスクID安定性）：** 今回の再構築ではtask_1_1〜task_6_4のtask_idはすべて維持されていた（`log_no_prompt.md`の再出力プラン全体でIDの重複・欠落・変更なしを確認）。ただしこれはコードによる保証ではなく、Task Planner自身が「surgicalな変更のみ」と自己判断した結果であり、将来の別の再構築で維持される保証はない。

**対応内容（実施済み）：** 新規ヘルパー`_is_task_completed(conn, run_id, task_id)`（受け皿タスクの最新Deliverableが`RESOLVING_DELIVERABLE_STATUSES`かを判定）を追加し、`_formalizable_stale`フィルタを「`defer_to_task_id`が無い、または受け皿タスクが既に完了済み」へ変更した。調査の過程で、同型の欠陥を`_get_forced_escalated_issues_text`（BL-136のUser AI向け毎ターン強制解決プロンプト）も抱えていることが判明したため、同じヘルパーをこちらにも配線し、受け皿タスクが完了済みなのに未解決のissueは再度提示されるようにした（同一クロールで見つかった同種のバグのためBL-167のスコープ内で一括対応）。

新規テスト`tests/test_bl167_defer_to_task_id_completed_target.py`（9件：`_is_task_completed`単体4件（Deliverable無し／Approved有り／Rejectedのみ／最新statusを見る回帰確認）、`reflection_node`の`_formalizable_stale`で受け皿未完了時は従来通り除外され続けること・受け皿完了後は再度対象化されること、`_get_forced_escalated_issues_text`で同様の2件）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。

**関連:** [BL-145](#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)（本フィルタの導入元）、[BL-144](#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)（滞留検知そのもの）、[BL-168](#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない)（同じ実害の別経路）、[BL-166](#bl-166-_build_agreements_contextのアイコンラベル判定がrejectされた成果物を承認済みと表示してしまう)（同一クロールでの直前の発見）

---

### BL-168: `verified_facts`テーブルにゴール改定を反映するsupersede機構が一切ない

**状態:** `done`

**経緯:** BL-167と同じ調査の流れで、なぜ再構築後のtask_1_1がゴール改定前の車両単価のまま出力されたのかを追跡した。

**確認した事実：** `log/2026-08-04/1435/log_no_prompt.md`行2394-2395で、Task Plan Reviewerが`read_verified_fact(topic_keyword="車両")`を呼んだ際、以下の値が無警告のまま「確定値」として返された：
- `max_vehicle_count = '2'`（台）
- `procurement_scenarios`: 全シナリオ「2台」
- `initial_cost_breakdown`: 「車両費2500万円/台」

いずれもゴール改定（BL-086、車両単価500〜1,000万円/台へ変更、車両台数5〜8台へ変更）**より前**に、task_1_1のExpertが確定した値である。

**根本原因（コード確認済み）：** `upsert_verified_fact`（`cela_main.py:4483`）は`(run_id, variable_name)`をユニークキーとしたUPSERT方式（`INSERT ... ON CONFLICT(run_id, variable_name) DO UPDATE`）で、該当`variable_name`が再度`upsert_verified_fact`されない限り、内容の新旧・前提の変化を一切問わず永久に「現在の確定値」として`get_verified_facts_from_db`/`read_verified_fact`ツールから返り続ける。`agreements`テーブルの`status != "Superseded"`フィルタ（`_build_agreements_context`）のような「現在性」を判定する仕組みが、`verified_facts`には存在しない。task_1_1はゴール改定後に一度も再実行されていない（BL-167の通りTask Plannerが説明文・受入基準は書き換えたが、実際の成果物・確定値の再計算は行われていない）ため、`max_vehicle_count`等はゴール改定前の値のまま取り残されている。

**実害：** これが原因で、再構築後のtask_1_1の説明・受入基準がゴール改定前の「車両購入費2,500万円/台」「4台が理論上限」のまま据え置かれた（BL-167参照、`log_no_prompt.md:1174-1178`）。Task Plan Reviewerを含む全ての後続ノードが、`read_verified_fact`経由でこの古い値を「確定済みの定数」（`upsert_verified_fact`のdocstring: 「下流タスクはこの値を再導出せず、確定済みの定数として参照する前提」）として無警告で参照し続けるリスクがある。

**BL-163との関係：** BL-163（`_revise_goal_tool_impl`の成功パス末尾で、ゴール改定時に承認済み過去タスクへ整合性再確認issueを機械的に起票する仕組み）は`agreements`（成果物）のみを走査対象にしており、`verified_facts`ストアは対象外だった。BL-163実装当時はagreements側の対策で十分と判断していたが、今回`verified_facts`という**別の永続化経路**が同じ「ゴール改定で前提が変わったのに古い値が生き残る」問題を抱えていることが判明した。

**対応内容（実施済み）：** BL-163が既に計算している「ゴール改定によって影響を受ける過去タスクの`(phase_id, task_id)`一覧」（`_flagged`）をそのまま再利用し、`_revise_goal_tool_impl`のBL-163ブロック直後に、該当`task_id`を`source_task_id`に持つ`verified_facts`行を検索して`reason`列の先頭へ`"⚠️[BL-168: ゴール改定後未確認] ..."`という警告を付記する処理を追加した（`value`自体は改変しない、過去の事実としては正しいため）。既にこのマーカーで始まる行は再度マーキングしない（同一runで複数回ゴール改定された場合の重複防止）。BL-163の起票ロジックと同一箇所・同一トリガーに相乗りさせることで、二重のロジックを避けた。

新規テスト`tests/test_bl168_verified_facts_stale_after_goal_revision.py`（5件：flaggedタスク由来のverified_factsへの警告付記、対象外タスク由来のfactsは無変更、verified_facts0件でのクラッシュ非発生、2回連続ゴール改定でも警告が重複しないこと、複数タスクが混在する場合にflagged対象のみ警告されること）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。

**既知の遡及漏れ（対応しない、D-138）：** `log/2026-08-04/1548`で、修正デプロイ**前**に発生済みの`revise_goal`呼び出し（`log/2026-08-04/1123`、車両単価2,500万→500〜1,000万への改定）に由来する`verified_facts`（`max_vehicle_count='2'`等）が、修正後もマーカー無しのまま残っていることを確認した。BL-168の修正は`_revise_goal_tool_impl`内でしか発火しないため、チェックポイント再開（`revise_goal`を再実行しない）では遡及的に効かない。ユーザー判断により、この既存run限定の一過性事情としてバックフィルは行わず現状のまま許容する（[D-138](../decision_log.md#d-138-bl-168修正の遡及漏れ修正デプロイ前に発生済みのゴール改定は既存run限定の特殊事情としてバックフィルせず現状のまま許容する)）。

**関連:** [BL-163](#bl-163-revise_goal成功時既に承認済みの過去タスクへ新ゴールとの整合性要再確認issueを機械的に起票する)（同じ「ゴール改定後の過去タスク」問題への対策、対象範囲が異なる）、[BL-167](#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)（同じ実害の別経路、同一クロールでの発見）、[BL-166](#bl-166-_build_agreements_contextのアイコンラベル判定がrejectされた成果物を承認済みと表示してしまう)（同一クロールセッションでの発見）

---

### BL-169: `write_agreement`の権限チェックがstatusのみを見ており、UserがExpertを介さず成果物（Deliverable）を自作・自己提出できてしまう

**状態:** `done`

**経緯:** BL-166〜168修正後にドライランを再開した`log/2026-08-04/1548`を最後（halt）まで追跡し、task_1_3の4回目（最終）リトライでUser AIが11回のpython_repl計算の末に成果物を自ら執筆・提出する様子を発見した。

**確認した事実：** `log_no_prompt.md`行3506-3866で、User AIが以下を実行した：
1. `write_agreement(entry_type="Deliverable", action_type="CREATE", status="Proposed", task_id="task_1_3", decision_what="<財務モデル全文>", ...)` を自ら呼び出し、task_1_3「財務持続性モデル構築・感度分析」の成果物を丸ごと執筆・提出（`verified_facts`更新ログにも`by=user`）。
2. 直後の発言（iter=12）で受入基準をすべて自己採点「✅」と宣言し、Expertを一切介さず次タスク`task_2_1`への移行を一方的に指示。

`write_agreement`ツール自体は`['python_repl', 'read_verified_fact', 'read_deliverable_file', 'write_agreement', 'escalate_premise_concern', 'resolve_premise_concern', 'revise_goal', 'freeze_agreement', 'write_issue', 'read_issues', 'think']`としてUser AIに元から付与されており、呼び出しはツール権限上正当に成立した。

**根本原因（コード確認済み）：** `_check_write_permission`（`cela_main.py:1859`）の`ALLOWED_STATUS_BY_ROLE`は`status`のみで判定しており、`user`は`{"Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"}`全statusを許可されている。role×entry_typeの組み合わせを制限する仕組みが存在せず、`caller_role="user"`が`entry_type="Deliverable"`かつ`action_type="CREATE"`を呼ぶことを何も止めていなかった。`generate_user_utterance`のシステムプロンプトは「あなたは指示を出す側」「相手に作業を要求し...出てきた提案をレビューする」と役割を明記しているが、それを強制する権限層のガードがなかった。

**実害：** 今回はDetector（Domain Review）がピーク需要200人に対し最大輸送力168人しか運べない物理的矛盾等を`major`判定で捕捉し（`log_no_prompt.md:4231`）、User AIの差し戻し上限（3回）到達で`reflection`へ回った。Reflectionは`status=stagnant`と判定し、理由に**"User is approving defective deliverables (collusion)"**と明記（`log_no_prompt.md:6072`）。最終的にFacilitatorのリトライ予算（facilitation_count）も超過し、システム全体がhaltした（`log_no_prompt.md:6081-6086`）。今回はDetectorが捕捉したため実害は限定的だったが、**Detectorが見逃せば「Userが自分で書いた成果物をUserが自分で承認する」自作自演がノーチェックで通ってしまう**構造的な穴であり、Expert↔Detectorの査読ループを丸ごと迂回できる。既存のcollusion監査（BL-126 Stage D、Reflectionが方針転換の理由づけの妥当性を監査する仕組み）は「User/Expertが馴れ合う」リスクを想定したものであり、「Userが単独でExpertを介さず成果物を生成する」ケースは対象外だった。

**対応内容（実施済み）：** `_check_write_permission`に、`caller_role=="user"`かつ`entry_type=="Deliverable"`かつ`action_type=="CREATE"`の組み合わせを拒否する分岐を追加した。既存Deliverableへのstatus変更・訂正指示（UPDATE/SUPERSEDE、承認・却下含む）は従来通り許可し、Expertによる新規作成にも影響しない。

新規テスト`tests/test_bl169_user_deliverable_create_forbidden.py`（9件：`_check_write_permission`単体でuserのDeliverable CREATE拒否・UPDATE/SUPERSEDE許可・Decision CREATE無影響・expertのDeliverable CREATE無影響の確認、`_write_agreement_impl`経由でのuser拒否時DB非書き込み確認・expert作成成功確認・user承認UPDATE成功確認）追加。既存`tests/test_bl146_write_agreement_current_task_gate.py::test_gate_applies_regardless_of_caller_role`と`tests/test_r4_smoke.py::test_integrator_node_reads_whiteboard_pointer`がuser役でDeliverable CREATEを行うテスト用ショートカットに依存していたため、前者はaction_typeをUPDATEへ、後者はexpertによるCREATE→userによるUPDATE承認の2段階へ修正した（いずれも各テストの本来の検証意図には影響なし）。`python -m py_compile`合格、既存BL-062/084/095/126/127/131/146関連80件無退行、フルオフラインスイート698件Pass。実ドライランでの効果確認は次回待ち。

**関連:** [BL-166](#bl-166-_build_agreements_contextのアイコンラベル判定がrejectされた成果物を承認済みと表示してしまう)、[BL-167](#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)、[BL-168](#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない)（同一クロールセッションでの発見）

---

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
| 2026-07-18 | BL-010・BL-011を新規起票（別チャットClaudeのR2レビュー指摘、D-009・D-010準拠）。 |
| 2026-07-18 | BL-012を新規起票（別チャットClaudeのR2レビュー指摘、D-011準拠）。 |
| 2026-07-19 | R2実装完了に伴い、BL-001・BL-006・BL-007・BL-008・BL-009・BL-010・BL-012を`done`化。実装は`cela_main.py`に反映済み、実LLM呼び出しなしのオフラインスモークテスト（`_run_python_repl`単体、フェイククライアントによる`query_AI`ツールループ、BL-001のDB往復）で検証済み。BL-011（プロバイダ別Function Calling検証）はD-010どおりMVP後に据え置き、`open`のまま。テスト実行基盤としてpytestを`requirements-dev.txt`に追加し導入（ユーザー承認済み）。 |
| 2026-07-19 | BL-015を新規起票（ユーザー提案：資料由来の一次情報・python_repl出力の機械的再利用によるハルシネリスク低減。決定はまだなく設計相談中、[decision_lineage.md 論点15](../decision_lineage.md)）。 |
| 2026-07-19 | BL-016・BL-017・BL-018を新規起票。本番ドライランでの10回ツール呼び出し非収束クラッシュの原因分析（BL-016）、差し戻しループ沼からの脱出機構構想（BL-017）、task_planner由来のタスク間依存関係の状態未構造化（BL-018）。いずれも設計相談中、[decision_lineage.md 論点16](../decision_lineage.md)。 |
| 2026-07-19 | BL-016を`done`化。ツールループへの残りiter数通知の注入と、Detector完了度判定の緩和（数値検算の厳格さは維持）をユーザー承認のもと実装（[D-016](../decision_log.md)）。オフラインスモークテストで確認済み、実LLM再ドライラン待ち。BL-017はユーザー訂正を受け、ファシリテーター自体は`facilitator_node`として既存であり、差し戻しループ検知のトリガーのみ未実装と内容を修正。 |
| 2026-07-19 | BL-019を新規起票・`done`化。OpenRouterのreasoningパラメータがフラットキーで無効化されていた実装バグを実機検証で発見・修正し、ツール付与ノードにも思考ログ出力を追加（[D-017](../decision_log.md)）。実機検証で思考ログの出力を確認済み。 |
| 2026-07-19 | BL-019に追記。tool_calls同梱content読み捨ての防御的対応と、実本番ログで確認した空白content表示の小修整。BL-020を新規起票・`done`化。中国語系モデル経由の言語逸脱対策として`query_AI`集約点に日本語出力の強制指示を注入（`_inject_japanese_output_directive`）。 |
| 2026-07-19 | BL-021を新規起票（ユーザー提案：全11箇所のプロンプト生成関数の英語化。BL-020の対症療法に対する根本対応の候補。設計未着手、`open`）。 |
| 2026-07-19 | BL-005を重要度「高」に更新（reflection/facilitatorが事実上発火不能という副作用が実ログで判明）。BL-017を大幅加筆（当初のreflection/Facilitator設計意図の想起、「ゴール抽象化・そもそも論」という本来の調停行動の具体例、現行`call_facilitator`実装との乖離、「生産的な反復」と「本当の膠着」を区別するトリガー設計の必要性を記録）。いずれもR4着手時に合わせて対応する方針（[decision_lineage.md 論点19](../decision_lineage.md)）。 |
| 2026-07-19 | BL-017を再定義：要件定義書_v35.md F-9・F-10.2〜F-10.6として既に仕様化・Phase 6以降に配置済みだったことが判明し、BL-017はその「MVP範囲での先行縮小実装」と位置づけ直した。D-018（R4パッチ方式の決定）を新規記録（[decision_lineage.md 論点20](../decision_lineage.md)）。 |
| 2026-07-19 | BL-022を新規起票・`done`化。本番ドライランのフルトレースバック解析により、OpenRouter経由の壊れたレスポンスがopenai SDK内部で生の`json.JSONDecodeError`を送出しD-009の絞り込んだexceptを素通りしていたことが判明。exceptタプルに`json.JSONDecodeError`を追加し修正（D-019）。 |
| 2026-07-19 | BL-023を新規起票。指標C計測（BL-002）着手時に判明した、task_plannerの分解粒度の粗さによる検証コストの乗算的増大（今日のtask_1.2ドライランで実証）を記録。ユーザーは指標C計測・R4・BL-018のいずれよりも本Issueを最優先で対応する方針（[decision_lineage.md 論点21](../decision_lineage.md)）。 |
| 2026-07-20 | BL-023に追記。ログ精査により真の増幅源が`generate_user_utterance`（User AI）側のスコープ肥大にもあることが判明し、設計対象をtask_plannerのみから拡張。さらにユーザーとの議論で「共有変数の一元所有（BL-018）」「予算のトップダウン・カスケード（ただし仮説であり絶対制約としない）」「森レベルの整合性はreflection/facilitator（BL-005）に戻す」の3点セット設計が必要と判明し、関連BLとBL-005を追加、完了条件を更新（[decision_lineage.md 論点22](../decision_lineage.md)）。 |
| 2026-07-20 | BL-023の着手順序を決定（D-020）。Phase A（task_planner/User AIのスコープ是正）・Phase C（予算カスケードの仮説化）を先行させ、Phase B（BL-005 reflection/facilitator復旧）は非ブロッカーとして後回しにする方針。完了条件をPhase A/B/C別に再構成（[decision_lineage.md 論点23](../decision_lineage.md)）。 |
| 2026-07-20 | BL-023の設計をこのプロジェクト自身の統治構造（issue_backlog/decision_lineage/phase_gate/STATUS/traceability/確定値の再利用）に対応する情報構造としてstateへ統合する方向で拡張。BL-024（`current_phase`初期化後フリーズ、`task_id`単位の状態追跡不在）を新規起票し、詳細設計を`docs/design/phase2/cela_phase2_design_BL023_task_state.md`として作成（[decision_lineage.md 論点24](../decision_lineage.md)）。 |
| 2026-07-20 | BL-023 Phase AとBL-024を実装し`done`化。`Task`型新設・`Phase`/`Agreement`/`LineageState`拡張・DBマイグレーション（`agreements.task_id`列・`verified_facts`テーブル）・`call_task_planner`のacceptance_criteria/depends_on/owns_variablesスキーマ拡張・`decision_extractor`の状態遷移一元管理＋Deferredステータス＋確定値抽出・Detectorのcriteria_status充足チェック・`generate_user_utterance`のペルソナ分離＋スコープ限定を実装。`python -m py_compile`合格、オフラインスモークテスト（DBマイグレーション・`verified_facts` upsert・`_get_current_task`・`_resolve_task_transition`のフェイルクローズ）はすべてPass。**実LLM呼び出しを伴う実機ドライランでの効果確認は未実施** — Phase C（予算カスケード）着手前にユーザーの指示待ち。 |
| 2026-07-20 | BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）をレビュー。task_planner出力が全タスクでacceptance_criteria（3個以内）・depends_on・owns_variablesを適切に生成し、以前task_1.2で束ねられていた車両台数・初期費用・ランニングコスト・感度分析が別タスク（task_2_2/4_1/4_2/4_3）に分割され、共有変数の一元所有パターンが機能していることを確認。`generate_user_utterance`も現在タスクの範囲に指示を限定できていた。副次的発見として、Decision Extractor/Orchestratorの`reasoning`フィールドの中国語出力を確認したが、ユーザー判断によりBL-020のスコープ外と決定（D-022、BL-020にスコープ明確化を追記）。 |
| 2026-07-20 | 同ドライランでExpertが他タスク（task_2_2）のowns_variables（車両台数・システム費内訳・サイクルタイム）まで自発的に計算しツールループが10回で非収束クラッシュしたことを発見。BL-025を新規起票し、①call_expertへのスコープガードレール注入、②ツールループ2周目以降のsystem_prompt軽量化（`light_system_prompt`）の2案をユーザー承認のもと実装着手（D-023、[decision_lineage.md 論点26](../decision_lineage.md)）。 |
| 2026-07-20 | BL-025を実装し`done`化。`_build_task_scope_context`ヘルパーを新設し`generate_user_utterance`/`call_expert`で共通化。`call_expert`にスコープガードレール（①）を注入。`query_AI`/`_query_AI_live`に`light_system_prompt`引数を追加し、`_JAPANESE_OUTPUT_DIRECTIVE`を定数化した上でツールループiter=2以降のsystem_promptを軽量版に差し替え（②）。`python -m py_compile`合格、フェイククライアントによるオフラインスモークテスト2件（ガードレール注入確認、iter=1フル文脈/iter=2以降軽量文脈への切替確認）はすべてPass。実機再ドライラン確認は未実施。 |
| 2026-07-20 | ユーザーの設計問い直しを受け、専門家選択の固定16種配列（`valid_experts`）がグラフ・`call_expert`のどちらでも分岐に使われておらず無用な足かせだったと判明。BL-026を新規起票・`done`化し、`call_orchestrator`を自由記述の専門家肩書き生成＋軽量フォールバックに変更（D-024、[decision_lineage.md 論点27](../decision_lineage.md)）。専門家ごとの個別ノード・個別グラフ構造はMVP未完成の現時点では見送り。 |
| 2026-07-20 | 実ドライラン（`log/2026-07-20/1421`）レビュー中に、同時刻帯の不自然な小ログフォルダ（`1455`・`1458`）を発見。原因は`cela_main.py`の`sys.stdout = MultiLogger()`がモジュールのトップレベルにあり、`import cela_main`するだけで本番`log/`配下に新規ディレクトリが作られる構造だったこと（このセッションのオフラインスモークテストが誤って混入させていた）。BL-027を新規起票・`done`化し、`__main__`ガード内への移動で修正、誤生成ログを削除（D-025、[decision_lineage.md 論点28](../decision_lineage.md)）。 |
| 2026-07-20 | 同ドライラン継続分（〜23278行）のレビューで、task_2_2のExpert呼び出しが`iter=10/tool_calls=9`とMAX_TOOL_ITER上限ぎりぎりで終了していたことを確認。BL-028を新規起票・`done`化し、クラッシュ回避を優先してMAX_TOOL_ITERを10→15に引き上げ（D-026、[decision_lineage.md 論点29](../decision_lineage.md)）。この変更はソース修正であり、レビュー時点で実行中だった1421プロセス自体には反映されない。 |
| 2026-07-20 | 同ドライラン継続分のレビューで、task_2_2の`verified_facts`（`operation_schedule`）にレポート全文がそのまま混入する事故を発見。`content`向けの「要約禁止」指示が`owned_variable_values`に波及していたことが原因と判明。ユーザーへの確認により、`content`の要約禁止は「部分成果物を後で製本する」設計思想に基づく意図的な仕様であり変更しないこと、`owned_variable_values`は目的が異なる簡潔な要約であるべきことが整理された。BL-029を新規起票・`done`化しプロンプトに目的の区別を明記（D-027、[decision_lineage.md 論点30](../decision_lineage.md)）。あわせて、独立フィールド化の拡張案をBL-030として起票（`open`、`decision_extractor`が将来補助的役割に縮小する設計と合わせて再検討）。 |
| 2026-07-20 | task_3_1レビューでUser AIがtask_2_3のコスト内訳との整合性を正しく取っていた挙動を分析。実際にはBL-023 Phase Aの構造化機構ではなく、`chat_history_window`の隣接性（task_2_3が直前タスクだったため生の全文がまだウィンドウ内に残っていた）による偶発的な副作用であり、`depends_on`宣言も実態を過少申告していることが判明。BL-018への追記として記録（[decision_lineage.md 論点31](../decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがOpenRouter実績（直近24時間4.6Mトークン、キャッシュヒット率19.7%、コスト$0.65）を共有。本日のログレビューで確認した可変ブロック（Recent Decisions再掲・task_planner出力JSON全体等）の毎ターン再送がヒット率を下げている可能性を指摘し、BL-031として新規起票（`open`、MVP完成後のコスト最適化枠、D-028、[decision_lineage.md 論点32](../decision_lineage.md)）。 |
| 2026-07-20 | ユーザーが「合意・決定事項・検討状況DB」のプロンプト出力を確認し、task_2_3の4件のDecisionが親Deliverable承認後も永久にProposedのまま取り残されていることを発見。承認カスケードの単純な機械化は本当の未検討事項を隠蔽するリスクがあるというユーザー指摘を受け、同ターンのDetector判定（`constraint_issue`/`task_criteria_status`）が清浄な場合のみカスケードするガード付き設計を採用。BL-032を新規起票（`open`、設計確定・実装承認済み、D-029、[decision_lineage.md 論点33](../decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがtask_5_2のログで、Expertがpython_repl未使用のまま「検算完了」と虚偽申告していた事故（Detectorの独立検算により実害なし）を発見。単純な強制差し戻しの無限ループリスクをユーザー自ら指摘し、①Expertの実行記録をDetectorに提示②Expert/Detector双方が未使用の場合のみ強制差し戻し、の2段構えに加え、実行記録の保存・提示という追加提案を統合してBL-033を新規起票・`done`化。`_query_AI_live`/`expert_node`/`call_detector`/`detector_node`を実装し、オフラインスモークテスト4件（記録保存・空リスト記録・複合失敗ガード発火・独立検算時の非発火）で確認（D-030、[decision_lineage.md 論点34](../decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがtask_6_3のログで、`decision_extractor_node`がDeliverableの`status`（Proposed/Approved）を問わずCREATE判定時点で無条件にファイル保存していることを発見。`integrator_node`が`status=="Approved"`のみを集約するため正当性は壊れていないが、却下・修正版のたびに旧版が孤児ファイルとして残る衛生上の課題として整理。ユーザーはR4のホワイトボード化（md差分読み書き）で構造的に解消される見込みと判断し、現時点では実装せずBL-034として記録のみ起票（`open`、D-031、[decision_lineage.md 論点35](../decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがtask_6_3で、Expertのピーク輸送力誤計算（正しくは39.1人/時、ピーク需要66.7人/時を下回る）によるDetector差し戻しを報告。検算の結果これは別フェーズ（task_2_1）確定済みの車両台数の不足という根深い問題と判明。`_build_task_scope_context`が現在フェーズ内のタスクのみを走査しフェーズ横断の`depends_on`参照を構造的に解決できないバグを発見しBL-035として起票。即応パッチではなく、要件定義書に新規追加したF-3.8（自律的DB/ファイル読み取りツール、v35.1）実装時にまとめて解消する方針をユーザーが決定（D-032、[decision_lineage.md 論点36](../decision_lineage.md)）。 |
| 2026-07-21 | ユーザー依頼により`log/2026-07-20/1421`の全21成果物を内容面でレビュー。「最終計画書」の財務数値（年間ランニングコスト・実質赤字額・補助金使用率）が統合パスのたびにPhase 3承認値と最大4.26倍乖離し、需要数値（人口・1日総需要）も根拠なくドリフトしていることを発見。BL-035と同一原因（統合パスが承認済みファイルを読み返せない）の別事例と判明したため、BL-036として起票。ユーザー判断により、既知原因からの予想された結果として参考記録に留め、F-3.8実装後の再ドライランで実効性を評価する方針とした（D-033、[decision_lineage.md 論点37](../decision_lineage.md)）。 |
| 2026-07-21 | ユーザーが「decisionなどの理由記載が甘い」と指摘。Detector自身の思考ログに、対象人口5,200人・1周回15分・80km/ルート等の数値の根拠を辿れず「根拠が不明」と繰り返し書かれている箇所を確認。①中間仮定がDecisionとして抽出されずreason_why欄自体が存在しない、②抽出されても理由が結論の言い換えに留まる、の2種の欠落と判明。BL-034〜036と同系統だが対象がreason_why欄の記載品質・抽出粒度である点で異なるためBL-037として起票。ユーザー判断により、まずBL記載のみに留め、F-3.1〜F-3.7（自律的書き込みツールへの移行）着手時にあわせて再設計する方針とした（D-034、[decision_lineage.md 論点38](../decision_lineage.md)）。 |
| 2026-07-21 | ユーザーがCELAの前身プロジェクトNPU-Context-Saverでの実運用実績（時間減衰RAG検索＋決定/否決ターンの自動セイリエンス固定、タイムスタンプ順の時系列復元読み、値・理由・引用元の三つ組をトピック検索できるファクトストア）を共有し、これらをBL-036/BL-037の解決方針として要件化するよう提案。理由（reason）は絶対的な正しさを要求せず「暫定値として進めた」こと自体を正当な理由として認め、暫定/確定の区別を後の再検討トリガーとして機能させる設計を追加提起。要件定義書にF-8.4・F-3.9を新規追加（v35.2、D-035）し、BL-036・BL-037にこの解決方針への参照を追記した（[decision_lineage.md 論点39](../decision_lineage.md)）。 |
| 2026-07-21 | R3b実装後の実ドライラン（`log/2026-07-21/2248`）レビュー中に、Expertの`write_agreement`成功（task_1.1、`vehicle_count`確定）後も`decision_extractor_node`のAgreement抽出がスキップされず、同一トピックでDecision/Deliverableの二重書き込みが発生していることを発見。オフライン再現テストでは`expert_node`単体の状態伝播（`state["expert_wrote_agreement"]`）は正常動作したため、原因は実グラフ実行中の状態伝播バグか、`write_agreement`の部分的カバレッジ（Decisionのみ、Deliverableは別経路）を想定できていない設計の粒度不足のいずれかに絞り込んだ。原因未確定のためBL-038として新規起票、次回ドライラン前に診断ログの追加を推奨する内容を記録した。 |
| 2026-07-22 | 同ドライラン（`log/2026-07-21/2248`、`log_no_prompt.md`）を`log_with_prompt.md`に続けてレビューし、`decision_extractor`が出力する`advances_to_task_id`のドット表記（`task_1.1`）と実際の`task_id`のアンダースコア表記（`task_1_1`）の不一致により、ログ全体8箇所すべてでタスク遷移が失敗し、`current_task_id`が一度も更新されないままドライラン全体を通じてBL-023/BL-025のスコープガードレールが実質無効化されていたことを発見。`call_detector`・`call_expert`・`decision_extractor_node`のスコープ限定機構すべてに波及する広範なバグと判断し、BL-039として新規起票（`open`、P0）。 |
| 2026-07-22 | 同ドライラン継続分（〜52569行、停止時点まで）のレビューで2件追加発見。①`read_deliverable_file`呼び出し31回中21回（約68%）が、ファイル名のタイムスタンプ部分を予測できずnot_foundになっていたことを発見しBL-040として起票。②ユーザーからの「車両台数4台の決定をどう覆すか」という問いかけを受けて`arbiter_node`/`global_constraints`を再調査し、資源超過を集約する処理がコードベース中に存在せず、実ドライラン全文検索でもResource Arbiter/facilitator/reflectionが1件も発火していないことを確認、一度確定した決定を後続タスクの発見から自動的に再検討させる仕組みが現状存在しないことをBL-041として起票（設計判断待ちのため実装は見送り）。ユーザー指示によりBL-039・BL-040は`cela_main.py`を直接修正（task_id表記のドット→アンダースコア正規化＋LLMへのtask_id一覧提示、`read_deliverable_file`のtask_id/topic_keywordによるDB逆引き＋agreements.task_id列の`_CURRENT_TASK_ID`フォールバック）、`tests/test_r3_smoke.py`にオフラインスモークテスト4件を追加し全49件Pass、`python -m py_compile`合格を確認。両BLとも`done`化（実LLM再ドライランでの効果確認は次回待ち）。 |
| 2026-07-22 | ユーザーがBL-041を「木を見て森を見ず」（task_1.1の狭いスコープ内で作業していたことが真因）と再診断し、①暫定値デフォルト化（F-3.9のconfidence活用）②すり合わせタスク／上書き機構③facilitatorのエスカレーション役への再定義（`reflection`同様の周期的発火）の3方向を提案（[decision_lineage.md 論点42](../decision_lineage.md)）。ユーザー指示により①はcela_main.py（Expertプロンプト・WRITE_AGREEMENT_TOOLスキーマのconfidenceデフォルトを`confirmed`→`provisional`に変更）に実装、③はBL-017と統合し設計書を先に作成する方針とし実装は見送り。あわせてBL-040にユーザー提案（ファイル名を`_Vn`バージョン連番化し旧版は`old/`へ退避）を追加実装。`tests/test_r3_smoke.py`にテスト1件追加、全50件Pass。 |
| 2026-07-22 | `decision_extractor`の`owned_variable_values`安全網パス（Expertがwrite_agreementを呼ばない場合）も暫定値原則の抜け穴になっていた点を修正。`upsert_verified_fact`のデフォルト引数を`confidence="confirmed"`→`"provisional"`に変更し、既存テストの期待値も更新（全50件Pass）。`cela_main.py`・`tests/test_r3_smoke.py`をコミット（c08bbd8）。あわせてBL-041のfacilitator/Resource Arbiter再設計ドラフトを`cela_facilitator_arbiter_redesign_BL041.md`として作成（未承認・未実装、実装前にユーザー確認が必要な未決事項4点を明記）。 |
| 2026-07-22 | ユーザーがR4（ホワイトボード差分パッチ化）をBL-041実装より優先着手する決定（ドライランの長時間化・トークン消費が理由、[decision_lineage.md 論点43](../decision_lineage.md)）。Plan modeで実装計画を策定し、既存R4設計書が未定義のまま残していた「Expertの変更箇所を既存完全版へどうマージするか」をClaude Code自身のEditツール方式（old_text完全一致検索→new_text置換）で解決。`cela_main.py`に`whiteboard_drafts`のCRUD・`_apply_text_edits`を実装し、`WRITE_AGREEMENT_TOOL`に`edits`パラメータを追加。Deliverableの主経路をwhiteboard_drafts方式に全面移行（`integrator_node`最終統合文書のみ旧来のファイル方式を維持）。Expert/Detector/User AIのプロンプトに現在タスクの最新ホワイトボードを注入し、`read_deliverable_file`・ロールバック（F-7.3）も対応。`cela_r4_design.md`・`cela_r4_impl_Plan.md`を更新・新規作成。`tests/test_r4_smoke.py`（14件）新規追加、既存`test_r3_smoke.py`の3件（R3b-T12・T13、BL-040バージョニングテスト）をWHITEBOARD方式に合わせて更新。オフラインスモークテスト計64件Pass、`python -m py_compile`合格。BL-034・BL-040のステータスをR4実装反映済みに更新（`partial`/`done`のまま補足追記）。 |
| 2026-07-22 | R4実装後の実LLMドライラン（`log/2026-07-22/1407`）レビュー中、DBを直接クエリしてBL-038の実データ破損（WHITEBOARDポインタがdecision_extractorのフォールバック経路でプレーンテキスト上書きされSupersededになる事故）を確認。インストール済みLangGraph（v1.2.9）の最小再現コードで、`StateGraph`のスキーマ（`LineageState` TypedDict）に宣言されていないキーはノード間で伝播せず消えることを実証し、`expert_wrote_agreement`/`user_wrote_agreement`/`expert_last_whiteboard_edit`のTypedDict宣言漏れが真因と特定（D-038）。`LineageState`へのフィールド追加、decision_extractorフォールバックへの`WHITEBOARD:`保護分岐の追加、実グラフ経由の回帰テスト2件を`tests/test_r4_smoke.py`へ追加し、オフラインスモークテスト計66件Pass。BL-038を`done`化。 |
| 2026-07-22 | 同ドライラン継続中のログ（`log/2026-07-22/1804`）レビューで、Detectorのconstraint_issue判定（minor/major境界）が同じ論点を8〜9 iter以上再検討し続ける非効率を発見。ユーザー提案の「3回思考し多数決を取る」方式を、`call_detector`プロンプトへの指示追加（3回だけ判定し多数決で確定、以降の再検討を禁止）として実装。BL-042として新規起票（`open`、プロンプト指示のみで様子見。守られない場合はコード側で暫定判定を強制カウントし機械的に打ち切る案へ進む）。同セッションで、`task_planner`の体感的な遅さの相談を機に`_query_AI_live`へstreaming描画（tools無し・tools付きツールループの両方）を追加、`MultiLogger.write()`の`flush()`欠落（ログファイルがターミナル表示より遅れて書き込まれる原因）も修正。 |
| 2026-07-22 | 同ドライラン継続（`log/2026-07-22/1804`）で、`[DEBUG] decision_extractor target_role='expert' expert_wrote_agreement=True ... -> wrote_agreement_this_turn=True`と、同一ターンで抽出された10件全てへの`⏭️`スキップログを確認し、BL-038（D-038）の修正が実機で正しく機能することを確定。あわせて、ユーザー提案の「JSONパース失敗時にツールでの構造確認・フィードバック・部分修正」を、既存のツール呼び出し引数の自己修復ループ（D-009）へ`decision_extractor`をFunction Calling化して一本化する案として整理し、BL-043を新規起票（`open`、設計変更がやや大きいためBL起票のみに留め、JSONパース失敗が実害として頻発した場合に実装着手）。 |
| 2026-07-22 | ユーザーがドライラン（`log/2026-07-22/2217`）で「Expertが`write_agreement`でホワイトボードVer.1保存に成功した直後、サーバー高負荷エラーになり、次のDetectorが機械的にmajor判定、差戻でホワイトボードが破棄された」事故を報告。ログ調査で、Detector自身は3回多数決で正しく`minor`判定していたが、BL-033のフェイルクローズガードが`expert_last_python_calls`の空を理由に`major`へ強制上書きしていたことを確認。真因は`_LAST_PYTHON_CALLS`（BL-033判定材料）がツールループの正常終了時のみ更新される実装で、python_repl検算・write_agreement成功済みの状態でも次iterationのAPIエラー例外で打ち切られると記録が失われていたこと（`_LAST_WRITE_AGREEMENT_SUCCEEDED`は即時セットのため例外の影響を受けず非対称）。BL-045として新規起票・`done`化、`_query_AI_live`のpython_repl実行箇所で`_LAST_PYTHON_CALLS`を即時反映するよう修正。 |
| 2026-07-22 | BL-045修正後、`--resume`で再開したドライラン（`log/2026-07-22/2300`）をユーザーが継続レビューし、「Expertの思考とiter番号が同じループになっているログが見える」と報告。調査の結果、`for attempt`リトライループ（BL-009）がツール呼び出しループ全体を内包しており、途中のAPIエラーで中間リトライが発生すると**何も表示せず**`loop_messages`/`python_calls_log`をサイレントに破棄しiter=1から巻き戻していたことが真因と判明（`cela_main.py:1904-1905`で`tools attached`の2連続印字を確認）。R4のwrite_agreementにDB副作用（ホワイトボード版管理）が加わった現在、この巻き戻りが`write_agreement`成功後に起きると重複書き込みの実害リスクがあることも指摘。ユーザー判断により、まず可視化（リトライ発生をログ出力）のみ対応する方針とし、`loop_messages`を破棄しない設計変更（重複書き込みリスクの本質的解消）はBL-046として記録のみに留めた。 |
| 2026-07-22 | 続くドライラン（`log/2026-07-22/2320`）で、ユーザーが`write_agreement`の`depends_on`エラー（"depends_onに存在しないID: task_1_1"）を報告。調査の結果、`WRITE_AGREEMENT_TOOL`スキーマの`depends_on`に説明文が一切なく、検証コードは`agreements`テーブルの数値行IDを期待する一方、AIはtask_planner側の別概念（task_idのdepends_on）と混同して`"task_1_1"`を渡し、無駄な1往復を経てから自己修正していたことが判明。BL-047として新規起票・`done`化、`depends_on`のdescriptionに正しい使い方（決定事項DB表示の`[N]`を使う、task_idは不可、不明なら省略）を追記して修正。 |
| 2026-07-23 | 続くドライラン（`log/2026-07-22/2336`）で、ユーザーがtask_2_1のacceptance_criteria自体の数学的矛盾をExpertが根拠のない数値ででっち上げ、Detectorも無根拠な推測で追認した事例を発見・共有。このお題がGeminiとの壁打ちで「あえて無理な制約下でのAIの格闘を見る」趣旨で発案されたという背景、reflectorが定期的にでっちあげを検出する設計だったはずという記憶が共有され、`docs/design/r5/cela_r5_design_v2.md` §1.3に実際にその設計が存在することを確認。BL-005（`turn_count`凍結）によりreflectionの周期発火が実質機能停止していたことが判明し、Web検索ツール付与案とも比較のうえreflection復旧を優先する方針で合意（D-040）。新設`round_count`（`generate_user_utterance_node`再入場カウント、論点45のラウンド定義を踏襲）でreflection発火判定を置き換え、`call_reflection`に軽量版でっちあげ監査プロンプトを追加。BL-048として新規起票・`done`化（reflection発火の症状のみ復旧、BL-005本体は引き続き`open`）、オフラインスモークテスト74件Pass。 |
| 2026-07-23 | 同ドライラン継続レビューで、ユーザーが「計算ツールを入れたことによりすべてのノードの思考が計算の正誤に引き寄せられ、非数値的な重大懸念（バス2台の予備車両欠如、監視員2名の労基法適合性）を出力に反映できていない」と指摘。task_1_1「3名（シフト制）」とtask_2_2「2名常駐固定」というオペレーター人数のtask間矛盾が、双方とも算数としては通過するため検出されていなかったことをログで確認。当初のDetector限定の分離案を、ユーザーが「detector、ユーザーとも同じ検算を3〜4回繰り返している場面がある」ことを理由にUser AI・Expertも含む方針へ拡張し、「ユーザーはdetectorの検算を信じてドメイン評価に重きを置く」という具体的な役割分担を指示（D-041）。`call_detector`を数値検算パス＋独立したドメイン妥当性レビューパスの2段構成に変更、`generate_user_utterance`・`call_expert`のプロンプトも調整。BL-049として新規起票・`done`化。オフラインスモークテストでドメイン妥当性レビューの過検知（情報不足をmajorの理由にする）を発見し、判定基準の明記で修正・再検証済み。 |
| 2026-07-23 | 続くレビューで、ユーザーが「各ノードが出す数値などの決定事項の理由が適当すぎる。実際バスが3台か2台になった経緯がわからずdetectorが困惑していた」と指摘し、車両台数3→2の経緯をDetectorが辿れなかった実例をログで確認（`log/2026-07-22/2336` 18652〜18692行）。調査の結果、SUPERSEDEは履歴を削除せず残す方式だが、Detectorへのコンテキスト提示が有効行のみに絞られ`reason_why`も差分理由を要求していないことが実質的な欠落と判明。ユーザーから3提案：①`decision_extractor`を抽出役から理由監査役へ軸足転換、②Detectorの気づきをissue_bl的リストとして蓄積しフェーズ終了条件とする（User・Detector監視、延期は理由必須）、③ホワイトボード本文に決定/理由DBへのインラインID参照（`[AG:123]`等）を埋め込む。「まずBL化してください」との指示によりBL-050・BL-051・BL-052として新規起票（いずれも`open`、設計相談・BL起票のみで実装は見送り）。 |
| 2026-07-23 | ユーザーが「read_xxx系のツール実行に失敗している時が複数ある」と指摘。ログ調査で`read_verified_fact`/`read_deliverable_file`呼び出し44回中18回（41%）が`not_found`であることを確認。真因は`get_verified_facts_from_db`の`topic_keyword`検索が`variable_name`列（英語識別子）のみを対象とし、AIが渡す日本語キーワード（「予算」「オペレーター」等、ツール定義自体が例示する形式）と構造的にほぼ一致しなかったこと。日本語理由文が入る`reason`列が既に存在するのに検索対象外だったため、`variable_name OR reason`のLIKE検索に修正。BL-053として新規起票・`done`化、回帰テスト1件追加（`tests/test_r3_smoke.py`）でオフラインスモークテスト非退行を確認。 |
| 2026-07-23 | ユーザーがBL-049のDetector2段監査（数値検算→ドメイン妥当性レビュー）の実行順序を問題視し、「検算の前にそもそも前提の数値や設計に指摘がないかを確かめる」ためドメイン監査を先に行うよう指示。`call_detector`のプロンプト構築順序を入れ替え、ドメイン監査を数値監査の結果に依存しない独立した第一段へ、数値監査をドメイン監査の結果を踏まえる第二段へ変更（統合ロジックは変更なし）。BL-054として新規起票・`done`化、`python -m py_compile`合格。 |
| 2026-07-23 | ユーザーがBL-051（issue_blリスト＋フェーズ終了ゲート）の軽量版として、Detectorの出力に「思考過程で気づいたこと・懸念事項」を自由記述させる欄を追加し、後続ノードのプロンプトに提示するよう指示。`call_detector`の両監査パスの返却JSONに`observations`を追加、`LineageState`に`detector_observations_log`を新設し`constraint_issue`の値に関わらず（none判定でも）蓄積、新規ヘルパー`_build_detector_observations_block`を`call_expert`・`generate_user_utterance`の両プロンプトに配線し直近3件を常時提示。オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | ユーザーが「自由記述欄はとりあえずの対処で、issue_bl化路線はもとのまま維持して」と明確化。BL-051の状態表記を`partial`から`open`へ差し戻し、`observations`欄の実装はissue_bl構造化リスト＋フェーズ終了ゲートという本来の方針を変更するものではなく、気づきの消失を当面緩和する暫定のつなぎに過ぎない旨をissue_backlog.md本文に明記。 |
| 2026-07-23 | ユーザーが同ドライラン（`log/2026-07-23/0919`）で、AIが車両単価2,500万円という例示的条件に引っ張られ、それを疑わず4台配分の組み合わせ探索のみを繰り返していたことを指摘。ゴール文に「真の制約」と「見直し可能な条件」が区別なく並記されている点を原因と分析し、ユーザー指示により特定の数値に限定しない一般化した指示として、`call_expert`・`generate_user_utterance`双方に「行き詰まった場合はまず真の制約か見直し可能な条件かを見極め、後者であれば前提自体を疑ってよい（真の制約の緩和は不可）」という趣旨のプロンプトブロックを追加。BL-055として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | 続くドライラン（`log/2026-07-23/1122`）でReflectionが発火した際、プロンプト内表示が「全30ターン中1ターン目」のままでReflection自身が矛盾に混乱している様子（"これはおかしい"）をユーザーが発見。BL-048で発火条件は`round_count`ベースに切り替え済みだったが、`call_reflection`のプロンプト内表示のみ凍結した`turn_count`（BL-005）を参照し続けていたことが原因と判明。表示を`round_count`（`reflection_interval`との対応関係も明記）に置き換え、発火条件と表示の基準を一致させた。BL-056として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | 続くドライラン（`log/2026-07-23/1256`）で、組合せ最適化的なExpertターン（4台制約下の代替案探索）がMAX_TOOL_ITER=15の非収束クラッシュで打ち切られたことをユーザーが報告。成果物自体はwrite_agreement済みで保存されていたが、「上限の3回前にすぐに結論を出せと言わないと間に合わない」との指摘を受け、BL-016の残り回数通知しきい値を「残り2回」から「残り3回」に前倒しし、残り1回時の通知文言もより強い断定的な指示に強化。BL-057として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | 同ドライランで、Expertが組合せ探索中に`import itertools`を試みホワイトリスト外で拒否されていたことをユーザーが発見。「サンドボックスから抜け出せないような標準的なツール群は許可したらどうか」と提案。AIがI/O・OS・ネットワークアクセスを持たない純粋計算モジュール候補（itertools/functools/collections/operator/re）を提示し、AskUserQuestionでユーザーが一括追加を選択。`_ALLOWED_IMPORTS`（AGENTS.md§7の承認済み定数変更）に5モジュールを追加。BL-058として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格、`import itertools`が実際に動作することを手動確認。 |
| 2026-07-23 | ユーザーが実際のクラッシュ（`httpx.RemoteProtocolError: peer closed connection without sending complete message body`が`detector_node`のstreaming受信中に未捕捉のままプロセス全体をクラッシュさせたトレースバック）を報告。BL-022（`json.JSONDecodeError`が絞り込んだ例外タプルから漏れていた事例）と同型の問題と特定し、`httpx`をimportした上で`_query_AI_live`の例外タプルに`httpx.RemoteProtocolError`を追加してリトライ対象化。BL-059として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | 続くドライラン（`log/2026-07-23/1453`）で、Expertが最終許容iteration（15回目）でも`write_agreement`を呼び出し、次のiterationが存在せずMAX_TOOL_ITER非収束クラッシュに至ったことをユーザーが報告。BL-016/BL-057の「残り回数」通知はあくまで依頼に過ぎずモデルが従わない限り防げないという限界を特定し、最終iterationのみAPI呼び出しから`tools`を除いて構造的にツール呼び出しを不可能にし、テキスト最終応答を強制する方式に変更。BL-060として新規起票・`done`化、オフラインスモークテスト計71件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | ユーザーの依頼により、当日（2026-07-23）の一連のドライラン（`log/1122`〜`1656`）を通しで再レビューし、BL修正の実効性を棚卸しした（[decision_lineage.md 論点57](../decision_lineage.md)）。**確認済み**: BL-048（reflectionのround_count発火・ゴール逸脱の実検出、`drift_flag`経由の差し戻しまで機能）、BL-049/054（ドメイン先行監査が数値監査とは異なる種類の欠陥＝Expert自身の検算コードのハードコードバグを独立に発見）、BL-057/060以降のクラッシュ非再発（`1358`/`1656`でTraceback 0件）。**未確認のまま**: BL-058（itertools等の実際の活用、修正後のセッションでは組合せ探索自体が発生せず）、BL-059（httpx.RemoteProtocolErrorの再発自体がなくキャッチの実地確認は未了）、BL-056（`round_count`表示を伴う新規reflection呼び出し自体がまだ観測できていない）。あわせてBL-041に、reflectionの検出精度向上によりエスカレーション機構未実装のギャップがより明確になった旨を追記。 |
| 2026-07-23 | ユーザーの「R5実装前につぶすBLはあるか」との問いを受け、R5設計書（`cela_r5_design_v2.md`）のGoalShiftEvent（§4）が`call_resource_arbiter`の拡張に依存する一方、BL-041で確認済みの通りarbiterが死んだコードパスであること、R5のFreeze機能（§3）が`_build_agreements_context`と同系統のクエリを拡張する一方、BL-050で確認済みの視認性ギャップ（Superseded除外）がその土台に残っていることを指摘し、R5着手前にBL-041・BL-050を潰す方針で合意。Plan modeで、既存ドラフト`cela_facilitator_arbiter_redesign_BL041.md`のうち§3.1（`global_constraints`の実働化）相当のみに絞ったMVPスコープの実装計画を策定（4段階エスカレーションメニュー・facilitator再設計・BL-005根本修正は今回スコープ外として明示的に据え置き）。`cela_main.py`に`resource_claims`のスキーマ具体化（`{名前: {phase_id, value, total_cap}}`、AGENTS.md§7該当・本Planの承認をもって承認済み）、新規`_aggregate_global_constraints`ヘルパー、`arbiter_node`冒頭での動的再集約配線（BL-041）、`_build_agreements_context`への直前Superseded版差分表示＋現行行自身のreason_why表示、`WRITE_AGREEMENT_TOOL.reason_why`/decision_extractor抽出プロンプトへのUPDATE時変更理由明記要求（BL-050）を実装。新規`tests/test_bl041_bl050.py`（8件）を含めオフラインスモークテスト計78件Pass、`python -m py_compile`合格。両BLとも`partial`のまま残し、実装済み範囲と未着手範囲を完了条件に明記。 |
| 2026-07-23 | ユーザーが`log/2026-07-23/1656`でfacilitatorが発火したログを報告し確認を依頼。調査の結果、直前のreflectionが5点の具体的な未解決問題（与条件無断変更・でっちあげ疑い数値等）を検出し`stagnant`と判定していたにもかかわらず、facilitator自身は「膠着していない」と独立に再判断し無関係な軽微な論点だけを促す食い違ったメッセージを出力していたことを発見。真因は`call_facilitator`の`decisions`引数がプロンプト内で完全に未使用（デッドパラメータ）で、reflectionの判定理由がfacilitatorへ一切伝わっていなかったこと。「このバグは今直してください」との指示により、`LineageState`に`last_reflection_note`を新設し`reflection_node`が保存、`call_facilitator`のプロンプトにこれを最優先の出発点として明示する形に修正。BL-061として新規起票・`done`化、新規`tests/test_bl061_facilitator_reflection_note.py`（4件）を含めオフラインスモークテスト計82件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | ユーザーの「R5の設計はV2としてすでにありますが...実装プランを作成」との依頼を受けPlan modeでR5実装計画を策定中、F-8.3 Freeze機能の設計相談で「Detectorがユーザー/エキスパートの決定まで破棄できたか？」というユーザーの根本的な疑問から、Detector等の`major`判定・`Rejected`書き込みが既存Agreementを構造的にSUPERSEDE/無効化する仕組みを持たず、実効果は差し戻しのみに留まることを発見。これはFreeze固有の課題ではなくwrite_agreement権限モデル全体の課題と判断し、R5実装とは切り離しBL-062として新規起票（`open`、実装は見送り）。R5実装計画自体は`docs/design/r5/cela_r5_impl_Plan.md`として保存し、F-8.3 Freezeの権限は`user`ロールのみに限定する設計で確定。 |
| 2026-07-23 | `cela_r5_impl_Plan.md`に基づきR5実装を完了。F-2.1（`_query_AI_live`のreasoning捕捉、`expert_last_reasoning`/`user_last_reasoning`、Detectorへの思考プロセス監査ブロック）、F-3.7（`make_decision`のinternal_thought_process、Detector major・Reflection stagnant・Rejected時のみの限定記録）、F-8.3 Freeze（`freeze_agreement`・`FREEZE_AGREEMENT_TOOL`・user限定・SUPERSEDE/UPDATEガード・`_build_agreements_context`のis_frozenソート）、GoalShiftEvent（`goal_shift_events`テーブル・`requires_goal_constraint_change`・`detect_goal_shift`・`arbiter_node`配線）を`cela_main.py`に実装。BL-063として新規起票・`done`化。新規`tests/test_r5_thought_log_freeze_goalshift.py`（14件）を含めオフラインスモークテスト計96件Pass、`python -m py_compile`合格。 |
| 2026-07-23 | ユーザーがIDEで`Agreement`TypedDictの3軸区分フィールドを選択し「活用された形跡はあるか」と質問したことを契機に、DBスキーマ・`state`（`LineageState`）全体を対象に「書き込まれるが読まれない情報」を棚卸しした。合意・決定メタデータ（3軸区分・`turn`・`evidence`・`reason_missing`・`state["risk_flag"]`、BL-064）、R5で新設した永続化情報の消費経路欠如（`internal_thought_process`・`goal_shift_events`、BL-065）、whiteboardの編集履歴が表示されない件（`author_role`/`edit_summary`、BL-066）、完全に未使用の`chat_history`/`current_goal`テーブル（BL-067）を発見。さらにユーザーから、`current_task_summary`が元々docs/refsのHydrate 3段グラデーション構想（直近Nターン生ログ＋それ以降を定期要約）に由来する設計だったが消費側が未実装のまま放置されている旨の説明があり、BL-068として起票。1つの大きなBLにまとめず、依存関係・類似性で分類しBL-064〜BL-068の5件として個別に起票（いずれも`open`、設計判断待ち・未着手）。 |
| 2026-07-23 | BL-064のAgreement3軸区分の議論から派生し、ユーザーが「AIが同じ検証を繰り返す」「木を見て森を見ず」対策としてL1〜L4のズームアウト思考フレームワークを提案。調査の結果、`call_expert`は既に全フェーズ・全タスクの`phases_json`を毎ターン注入済みだが、直後のBL-025スコープガードレールがそれを能動的に使うことを事実上禁止しており、この緊張関係はBL-041のコードコメントが既に指摘済みと判明。ユーザーは正式なL1-L4段階分けは不要とし、軽量な指示追加で十分と後日補足、BL-069として起票（`open`、未着手）。BL-064は5項目の扱い（Agreement3軸は完全削除、`turn`/`risk_flag`削除、`evidence`/`reason_missing`は表示配線）をユーザーと個別に決定し実装、`done`化。`integrator_node`の`d['turn']`参照漏れをテストで発見・修正。オフラインスモークテスト計96件Pass、`check_docs_consistency.py`合格。 |
| 2026-07-24 | ユーザーとBL-062・BL-065の対応を相談する中で、Freeze機能（D-044）を再考し「検証手段のないままユーザー/AIの決定を絶対視するFreeze」より「Detectorの正しいmajor判定がApproved agreementを覆せず永続化する矛盾（BL-062）」の解消を優先する判断がユーザーからあった。実装前調査で、BL-062完了条件の①案（権限モデル拡張）はそもそも不要（`_check_write_permission`は`status`のみ制限し`action_type`は無制限、Detector等は最初から`status='Rejected'`+`action_type='SUPERSEDE'`を呼べた）と判明し、真の欠落はDetectorがagreements DBのtopic一覧をプロンプト上受け取っていなかったこと・SUPERSEDE運用指示がなかったことの2点と特定。ユーザーの指示によりDetector限定で実装範囲を絞り、Reviewer/Arbiter/Integratorへの拡張はBL-070として分離。`call_detector`への`_build_agreements_context_from_db`注入とSUPERSEDE指示追加、`generate_user_utterance_node`の2箇所から`FREEZE_AGREEMENT_TOOL`除去（本体・ガード・表示は温存）を実装し、D-045として記録（D-044は`superseded`化）。BL-062を`partial`化、BL-070を新規起票。新規`tests/test_bl062_detector_supersede.py`（4件）を含めオフラインスモークテスト計100件Pass、`python -m py_compile`合格。 |
| 2026-07-24 | ユーザーの依頼により`STATUS.md`・`phase_gates.md`をR4/R5の実態に合わせて更新（Phase 5節新設、P3a-1/P3a-2/P3b-1を実装確認済みとして☑化）。直後、ユーザーが実ドライランを実行し`orchestrator_node`で`TypeError: '<' not supported between instances of 'NoneType' and 'float'`によるプロセスクラッシュを報告。調査の結果、`decision_extractor_node`・`integrator_node`のAgreement辞書リテラルが`timestamp`キーを元々持たずDB上NULLになっていたところ、R5（BL-063）で追加した`_build_agreements_context`のis_frozen優先ソートが初めてこれを比較に使い顕在化したクラッシュと判明（BL-050の`_find_prior_superseded`は同種の状況を`or 0`パターンで既に回避済みだった）。ソートキーを`a.get("timestamp") or 0`に修正し、3箇所のAgreement辞書リテラルに`"timestamp": time.time()`を追加。新規`tests/test_bl071_agreement_timestamp_crash.py`（2件）を含めオフラインスモークテスト計102件Pass。BL-071として新規起票・`done`化。 |
| 2026-07-24 | BL-071修正後の再ドライランで、`expert_node`のstreaming受信中に`httpx.ReadTimeout`が絞り込んだ例外タプルから漏れ未捕捉のままプロセスクラッシュ（BL-059と同型の問題）。個別の派生例外を都度追加するのではなく、`ReadTimeout`/`ConnectTimeout`/`WriteTimeout`/`PoolTimeout`を包含する親クラス`httpx.TimeoutException`を`_query_AI_live`の例外タプルに追加して解消。新規`tests/test_bl072_httpx_timeout_retry.py`（1件）を含めオフラインスモークテスト計103件Pass。BL-072として新規起票・`done`化。 |
| 2026-07-24 | ユーザーと同ドライラン（`log/2026-07-24/0647`）のR4/R5機能稼働レビューを行う中で、Reflectionの内省監査ログが完了済みタスクの指示（Directive）を「未解決」として繰り返し自問自答している様子を発見。調査の結果、`entry_type="Directive"`のagreementは`decision_extractor_node`のUPDATE分岐・`_commit_agreement_from_tool`のいずれからも遷移させる経路がなく、CREATE時の`status="Proposed"`のままDBに永久残留する構造的欠陥と判明。ユーザーの指示により、対症療法（未解決抽出からDirectiveを除外）ではなく根本解決（②案）を採用し、新設`_resolve_directive_for_task`をDeliverable承認の両経路（decision_extractor/write_agreementツール）から呼び出しDirectiveを自動的に`Approved`へ遷移させる実装を行った。新規`tests/test_bl073_directive_auto_resolve.py`（4件）を含めオフラインスモークテスト計107件Pass、`check_docs_consistency.py`合格。BL-073として新規起票・`done`化。 |
| 2026-07-24 | ユーザーの依頼でtask_2_1承認後のtask_2_2（初期導入費用内訳策定）議論の変遷とDB更新状況をログから詳細に再構成する中で、topic文字列が版を重ねるたびに変わり（「task_2_2 初期導入費用の内訳策定」→「...ver.2修正版」→「...ver.3」→「...ver.3承認」）、Supersede漏れの`Proposed`/`Approved_with_Conditions`行が実測4行DBに残存していることを発見。また前回セッションで報告した「edits失敗の原因はモデルの一字一句コピーミス」という診断が誤りで、実際は`target_topic`未指定によりDB内の対応行が見つからず`old_content=""`となったことが根本原因と判明し訂正。BL-074として新規起票（`open`、BL-073と同根）。ユーザーと相談の上、`topic`ではなく`task_id`をDeliverableの識別キーとする設計方針（`_resolve_prior_deliverable_for_task`新設案）を決定。実装は次回。 |
| 2026-07-24 | 同ドライラン継続中、Detector自身がtask_2_3のオペレーター年間有給休暇（労基法違反で一度major判定・Ver.2で10日に修正済み）が、別件（法定祝日未考慮）でのmajor判定・ロールバックにより無警告で5日（違反状態）へ後退していることを発見。原因はF-7.3の`rollback_whiteboard`が「1つ前のバージョンは健全」という前提で機械的にrows[1]（2版前）を復元する設計だったこと。ユーザーから、この「直前のNG発言・状態を消して一から考え直させる」設計は元々「次のAIが誤った思考に引っ張られる」のを防ぐためだったが、F-2.6検算ゲート等でシステムが大幅強化された現在は逆に矛盾を生んでいるとの説明があり、Word/PDFのコメント機能のようにDetectorの指摘箇所を示して部分修正させる方式への転換を提案・採用。`rollback_whiteboard`を削除し、`call_expert`のmajor差し戻しプロンプトを全文書き直し誘導から`edits`による部分修正・影響範囲確認の指示に置き換えた。副次的に、`system_prompt`に追記されるが`messages`に反映されない死んだコード重複ブロックも発見・削除。新規`tests/test_bl075_no_whiteboard_rollback.py`（4件）追加、`test_r4_smoke.py`のF-7.3ロールバック専用テスト2件を削除。オフラインスモークテスト計109件Pass、`check_docs_consistency.py`合格。BL-075として新規起票・`done`化。D-047として記録。 |
| 2026-07-24 | ユーザーから、BL-075のプロンプト誘導だけでは毎ターン再構成されて消えるプロンプト注入に留まり見落とされうるとの指摘があり、Detectorのmajor指摘をホワイトボード本文にも永続的な注釈として埋め込む機能を追加提案・実装。`call_detector`の両パスに`target_excerpt`（一字一句引用）を追加し、新設`_annotate_whiteboard_with_detector_comment`が一意一致時のみ注釈を挿入。フォーマットは案A（grep容易なタグ）と案B（Markdown引用）のハイブリッド（ユーザー承認、D-048）。新規`tests/test_bl076_whiteboard_detector_annotation.py`（4件）含めオフラインスモークテスト計113件Pass、`check_docs_consistency.py`合格。BL-076として新規起票・`done`化。あわせて、ユーザーが提示したより大きな構想（AGENTS.mdの「まずMemory/STATUS/backlogを確認」という思想をCELA自身のAI群に適用する、issue_BL・STATUS.md・traceability.md相当の仕組みが必要）をBL-077として起票（`open`、設計検討のみ、実装は別途）。 |
| 2026-07-24 | ユーザーが、Detectorのドメイン妥当性レビューが「監査の観点をプロンプトで変えるだけで仕事ぶりがガラッと変わる」ことに着想を得て、Orchestratorが専門家選定時に既に行っているタスク考察（従来は選定理由`reason`としてログに残るのみでExpertには伝わっていなかった）を、新設`focus_guidance`として明示的に出力させ選ばれたExpertのプロンプトへ注入する提案。ユーザーの指示により、`call_orchestrator`のプロンプトにも明示（Expertの選定理由とは別に、タスク固有の着眼点・落とし穴を1〜3点求める指示を追加）した上で、`orchestrator_node`が`state["expert_focus_guidance"]`へ保存、`call_expert`のフル版・軽量版プロンプト両方に注入する実装を行った。新規`tests/test_bl078_orchestrator_focus_guidance.py`（4件）含めオフラインスモークテスト計117件Pass、`check_docs_consistency.py`合格。BL-078として新規起票・`done`化。D-049として記録。 |
| 2026-07-24 | ユーザーの依頼で`log/2026-07-24/1216`のドライランログをフォレンジック調査し、BL-073〜BL-078の各修正が実際に効いているか検証。BL-073（Directive自動解決）・BL-062（SUPERSEDE配線）・BL-078（focus_guidance）・F-2.1/F-3.7（思考プロセス監査）は実際に発火・機能していることを確認したが、BL-076（ホワイトボード注釈）はmajor/assistant判定が複数回発生したにもかかわらず一度も発火しておらず、しかも失敗がサイレント（`_annotate_whiteboard_with_detector_comment`は`False`を返すのみでログなし）だったことを発見・報告。ユーザーの指示により、この完全一致依存の脆さをBL-074（topic文字列ドリフト）と同根の問題として統合し、(1)失敗理由（0件一致/複数件一致）をログへ出す、(2)改行・空白・Markdown太字記法・全角半角を正規化した緩い一致へのフォールバック、を実装（戻り値を`tuple[bool, str]`化）。さらにユーザーから「Claude Code自身のEdit（完全一致）はなぜ実運用できるのか」との質問があり、調査の結果「その場で読んだ内容から引用する」ことに加え「不一致時に即座にエラーが返り同一ターン内でリトライできる」ことが鍵と判明。CELAのDetectorには後者が欠けており、これを取り入れる「一致失敗をDetector自身にツール結果として返し同一ツールループ内でリトライさせる」構造をユーザーが承認、規模が大きいためBL-079として起票（`open`、実装は別途）。新規`tests/test_bl074_annotation_loose_match_fallback.py`（5件）、既存`tests/test_bl076_whiteboard_detector_annotation.py`をタプル戻り値に更新、オフラインスモークテスト計122件Pass、`check_docs_consistency.py`合格。 |
| 2026-07-24 | ユーザーの依頼で`log/2026-07-24/1319`のドライランをフォレンジック調査し、「後からtask_1_1のホワイトボードを修正している様子がある」という報告の実態を特定。ExpertがBL-075のプロンプト誘導（editsの完全一致失敗時はdecision_whatによる全文更新＝SUPERSEDEを使え）に従い`action_type='SUPERSEDE'`で全文更新を試みると、ツールは`{'success': True}`を返すのに実際にはホワイトボードが一切更新されず、Expertがこれを「システムの反映タイミングの問題」と誤って自己正当化し、Detector/Userからハルシネーションと判定され差し戻され続ける無限ループを発見。根本原因は`_commit_agreement_from_tool`の`SUPERSEDE`分岐が旧agreement行のstatus変更直後に`return None`しており、`decision_what`（全文）を完全に破棄しapply_whiteboard_patchも呼ばずに「成功」を返す、実質何もしないツール呼び出しだったこと。「修正してBL起票」との指示により、`entry_type=="Deliverable"`かつ`action_type in ("CREATE", "SUPERSEDE")`かつ長文の場合はCREATE同様ホワイトボードへ保存するよう即時修正（BL-062のDetector無効化用途との後方互換は同じ200文字閾値で維持）。D-051として記録、新規`tests/test_bl080_supersede_deliverable_whiteboard_writeback.py`（3件）含めオフラインスモークテスト計125件Pass、`check_docs_consistency.py`合格。BL-080として新規起票・`done`化。 |
| 2026-07-24 | ユーザーが同じ`log/2026-07-24/1319`を指して「やはりまだ、ホワイトボードの差分書き換えに苦労しているようです」と再調査を依頼。ExpertがBL-080の誘因となった`edits`失敗の実例を特定：old_textにMarkdownテーブル行頭の`| `＋全角スペースや行末の` |`が含まれておらず完全一致0件。BL-074/D-050でDetectorのtarget_excerpt向けに確立した正規化緩い一致を`_apply_text_edits`にも適用し、新設`_find_loose_match_spans`で位置逆写像した上でフォールバック置換するよう実装。あわせて`_normalize_for_loose_match`自体の非対称バグ（半角スペースは除去されるが全角スペースはNFKC正規化後の半角スペースとして残存）を発見・修正し、テーブル区切り記号（`\|`）も正規化対象に追加。D-052として記録、新規`tests/test_bl081_edits_loose_match_fallback.py`（5件）含めオフラインスモークテスト計130件Pass、`check_docs_consistency.py`合格。BL-081として新規起票・`done`化。 |
| 2026-07-24 | ユーザーが`log/2026-07-24/1349`でUser AIの先送り発言（積雪・通信エリアの地形照合はtask_2_1/task_2_2で扱う）を指摘し「この先送り事項は現状消えてしまいますよね？」と質問。調査の結果、decision_extractorの先送り検出ルールがExpert側ブランチにしか実装されておらずUser側で発動しないこと、`_build_agreements_context`がentry_type=Directiveを無条件除外し後続タスクに一切見えないことの二重の欠陥を発見。ユーザーが「task_plannerの計画もホワイトボード化」を提案し「設計と実装を進めて最後にBL化」「呼び出し忘れ等に気を付けて」と指示。探索エージェント調査＋Plan agentの批判的レビューを経て、新規`plan_drafts`テーブル・遅延シード・行アンカー正規表現による堅牢な追記処理を設計し実装。レビューで`call_detector`が第3の呼び出し漏れ箇所として発見され配線に追加。D-053として記録、新規`tests/test_bl082_plan_drafts_deferred_notes.py`（11件）含めオフラインスモークテスト計141件Pass、`check_docs_consistency.py`合格、エンドツーエンドの手動統合確認も実施。BL-082として新規起票・`done`化。 |
| 2026-07-24 | BL-082コミット後の再ドライラン（`log/2026-07-24/1459`）で、Expert(iter=7)のedits編集直後にstreaming受信中の接続が強制切断（Windows `WinError 10054`）され、生の`httpx.ReadError`が絞り込んだ例外タプルから漏れ未捕捉のままプロセスクラッシュ（BL-059/BL-072と同型の再発、BL-081/BL-082のロジックとは無関係な純粋なネットワーク層の例外クラス漏れ）。例外タプルに`httpx.ReadError`を追加して解消。新規`tests/test_bl083_httpx_readerror_retry.py`（1件）含めオフラインスモークテスト計142件Pass、`python -m py_compile`合格。BL-083として新規起票・`done`化。 |
| 2026-07-24 | ユーザー依頼で`log/2026-07-24/1459`を精査する中で、BL-081実装後にもかかわらず`edits`が2回とも「old_textが見つかりませんでした（正規化後の緩い一致も0件）」で失敗している事例を発見。実際にold_textとホワイトボード内容を抽出し`_apply_text_edits`に再投入したところ完全一致（差分0）することを確認し、BL-081の正規化ロジックは無関係と判明。真因は`_commit_agreement_from_tool`のUPDATE/SUPERSEDE分岐が`target_topic`（省略時は自分自身のtopic）の文字列完全一致で対象を検索しており、Expertが呼び出しごとにtopicの言い回しを変えていたため既存行と一致せず`old_content`が空文字のまま渡されていたこと。BL-074の完了条件「Deliverable本体のtask_id識別への切替はまだopen」がまさにこれで、ユーザーの「修正着手してください」との指示により、新設`_find_active_deliverable_agreement`で(phase_id, task_id)識別に切替（Decision/Directiveはスコープ外、従来通り）。D-054として記録、新規`tests/test_bl084_deliverable_task_id_identification.py`（5件、1459ログの実際のtopicドリフトを再現）含めオフラインスモークテスト計147件Pass、`check_docs_consistency.py`合格。BL-084として新規起票・`done`化。 |
| 2026-07-24 | ユーザーから「ホワイトボードの中身を保存時にファイルに書き出してほしい」と要望。新設`_write_whiteboard_to_file`を`apply_whiteboard_patch`から呼び出し、`{log_dir}/whiteboards/{phase_id}_{task_id}_V{version}.md`へバージョンごとに個別Markdownファイルとして書き出すよう実装（DBが正、ファイルはベストエフォートの補助資料）。BL-027と同じ理由で`MultiLogger`未初期化時（テスト/import時）は書き出しをスキップし、本番log/配下のテスト汚染を防止。D-055として記録、新規`tests/test_bl085_whiteboard_file_writeback.py`（3件）含めオフラインスモークテスト計150件Pass、`python -m py_compile`合格。BL-085として新規起票・`done`化。 |
| 2026-07-24 | ユーザーが1459ログの抽出済みホワイトボードから「オンデマンド交通なのに35人乗りバス」の矛盾を指摘し、「そもそも論というか、視座の設計が大事」「今のコンサルが数字をこねくり回す状態ではPOCで即死する」とより一般的な構造上の課題を提起。調査の結果、(1) Expertが制約自体の妥当性を疑い表明する手段が無い、(2) User AI承認をFreezeで恒久化できずDetectorの独立監査で無限に再燃しうる（Freezeはbl-062解消のためD-045で意図的に休止中）、(3) `state["goal"]`を改定する手段が無くGoalShiftEventが書きっぱなし（BL-065）という三重の構造的欠陥を特定。ユーザーの「エスカレーション経路を作り込み、freezeを復活させ、本質的課題の視座に登り当初目標を越境しても最適な着地点に到達できるように」との指示を受け、`dev_escalation`ブランチを新設しPlan mode（Explore3件＋Plan1件）で設計。新設ツール`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`、`goal_escalations`テーブル、`FREEZE_AGREEMENT_TOOL`のUser AIへの再配線、`call_detector`両パスへの🔒尊重指示を実装。`state["goal"]`は9箇所の消費者が毎ターン再埋め込むため`generate_user_utterance_node`の1箇所の代入で全消費者に自動伝播する設計とした。D-056〜D-058として記録、実装計画は`docs/design/r5/cela_r5_escalation_freeze_goalrevision_impl_Plan.md`に保存。新規`tests/test_bl086_escalation_freeze_goal_revision.py`（18件）、`test_bl062_detector_supersede.py`の1件更新を含めオフラインスモークテスト計168件Pass、`check_docs_consistency.py`合格。BL-086として新規起票・`done`化。 |
| 2026-07-25 | BL-086実装後のドライラン（`log/2026-07-24/2358`〜`log/2026-07-25/1525`）を段階的にレビューし、BL-087（前提の質を上げる一連の改善）として、task_plannerの曖昧表記禁止・User AI二重指示バグ修正（Stage1）、`task_plan_reviewer_node`新設（Stage2）、`goal_essence_node`本質フェーズ新設（Stage3）、Detector/User AIの本質整合性レビュー（Stage4）を段階的に実装。新規追加ノードの暗算依存によるハルシネーションリスク対策として`goal_essence_node`/`task_plan_reviewer_node`/`task_planner_node`に`PYTHON_REPL_TOOL`を付与、本質テキストの注入漏れ（`call_task_planner`/`call_task_plan_reviewer`がBL-086時点の9消費者リストに含まれていなかった）も発見・修正。オフラインスモークテスト計190件Pass。続く実ドライラン（`log/2026-07-25/1549`）のユーザーレビューで、`task_plan_reviewer_node`が数値精度に偏重し過ぎて「山間部12km≒ルート全体13.33km」という妥当な推定値を「矛盾」としてmajor判定・差し戻した結果、再生成されたtask_plannerがゴール文に存在しない「総ルート長80km」という数値をでっち上げる実例を発見。ユーザーの指示（Reviewerの過敏性緩和・タスク欠落や順序不備の視点も同等に重視・`plan_drafts`〈BL-082〉へレビュワーが指摘を書き込めるように・派生値には根拠条件を必須で明示）を受け、項目17〜21（Stage2改善）として対応。新規11件を`tests/test_bl087_stage2_task_plan_reviewer_node.py`へ追加（計21件）、`python -m py_compile`合格。BL-087のStage1〜4・Stage2改善は`done`、Stage2'・5は引き続き`open`。 |
| 2026-07-25 | BL-087 Stage2改善を反映した実ドライラン（`log/2026-07-25/1642`）をユーザーの依頼でレビューしたところ、較正の効果自体は確認できた一方（Reviewerが「総ルート長は不明のままでよい」と正しく判断する様子を確認）、`task_plan_reviewer_node`が1〜2回目のtask_planner出力を「タスクが単一で全く分解されていない」として差し戻していたが、実際のLLM応答は5〜6フェーズの正しい計画であったことが判明。原因は`_safe_json_parse`が、コードフェンス前に説明文が付く応答（LLMの一般的な癖）かつトップレベルが配列の場合に、本来の開始位置`[`より後にある最初の`{`を誤って優先してしまい、構文的に不正なJSONとなりfallback（縮退した1タスク計画）へ握りつぶすバグと判明。ユーザーの「直して」との指示によりBL-088として起票・即修正（`{`/`[`のうち先に現れる方を採用するよう変更）。新規`tests/test_bl088_safe_json_parse_bracket_precedence.py`（3件、`1642`ログの実際の失敗パターンを再現）、`python -m py_compile`合格。D-062として記録。BL-088として新規起票・`done`化。 |
| 2026-07-25 | ユーザーの依頼で`log/2026-07-25/1705`をレビューし、task_plannerが`MAX_TOOL_ITER`（15、既存のグローバル定数、変更せず）を使い切り最終iterationで26タスク分のJSON全体を強制的な一括テキスト応答として出力させられていた事象を発見。`python_repl`呼び出し内容を精査したところ、終盤5回が「acceptance_criteriaが3個以内か」等、新しい情報を生まない同一内容の「念のため最終確認」の繰り返しだったと判明（今回は出力自体は間に合ったが、より大きな計画やStage2の再生成時に同じ現象が起きれば、最終出力が途中で切れてBL-088と同じ被害形態＝fallback化に陥るリスクがある）。ユーザーの「お願いします」との指示により、BL-087項目22として`call_task_planner`のプロンプトに項目7「計算・検証は各回1回まで、繰り返し確認しない」を追加。新規テスト1件を`tests/test_bl087_task_planner_prompt_and_resubmission_fix.py`へ追加（計4件）、オフラインスモークテスト（BL-087/088関連54件）Pass、`python -m py_compile`合格。 |
| 2026-07-25 | ユーザーが「ドライランをやり直しました」と`log/2026-07-25/1814`のレビューを依頼。BL-088修正後もなお、task_planner出力のmax_tokens相当の途中切れで縮退計画にフォールバックした上、task_plan_reviewerがこの縮退計画を正しく"major"と判定していたにもかかわらず、応答が「プレビュー用配列ブロック」＋「### 最終JSON出力の完全なオブジェクトブロック」という2つの```json```ブロックで構成されていたため`_safe_json_parse`が混線し構文エラー、fallback（"none"）に化けて縮退計画がそのまま承認・実行されてしまう事象を発見（`log/2026-07-25/1814/whiteboards/`にphase_1_task_1_1のみ存在することで確認）。ユーザーの「修正してください」との指示により、BL-089として起票・対応: (1) `_safe_json_parse`を複数フェンスブロックのうち最後を採用する方式に変更、(2) `call_task_plan_reviewer`/`call_task_planner`/`call_goal_essence_analyst`を既存の層2リトライ`_query_and_parse_with_retry`でラップ、(3) `call_task_plan_reviewer`はリトライ失敗時に"major"へフェイルクローズ。続けてユーザーが「他のノードも何回も何回も同じ思考を繰り返しすぎることが多々ありました」と指摘し、taskプランナー項目7と同種の重複検証抑制指示を、tools=[...]を持つ他8関数（call_expert/call_detector/call_resource_arbiter/call_integrator/call_reviewer/generate_user_utterance/call_goal_essence_analyst/call_task_plan_reviewer）のプロンプトに展開。新規`tests/test_bl089_json_fence_and_failclosed_review.py`（8件）・`tests/test_bl089_anti_repetition_instructions.py`（9件）、`python -m py_compile`合格。D-064・D-065として記録。BL-089として新規起票・`done`化。 |
| 2026-07-25 | BL-089修正後のドライラン（`log/2026-07-25/1913`）を、別チャットでのレビュー結果としてユーザーが共有。良好点（`task_plan_reviewer`の的確な差し戻し・BL-062のSUPERSEDE運用実働・サンドボックス制限からの手計算復旧・reflectionの安易でない継続判定・User AI自身の検算バグ発見）に加え4点の気づき（L424のJSON破損、L16700のWhiteboard Annotate失敗、L26206のUser AI引用転記ミス、`task_plan_reviewer`のiter=15到達）を報告。あわせてBL-089修正の実効性検証を依頼されたため、該当行を実際に読み確認: (1) L428でgoal_essence_analystのJSON判定パース失敗が層2リトライで正しく自己修復、(2) `task_plan_reviewer`がL6281・L11674の2回iter=15の強制終了に達したが、いずれも単一の完結したJSONブロックで`constraint_issue="major"`が正しく出力され、1814のような複数ブロック混線・フェイルオープンへの取り違えは再発せず。BL-089のフェイルセーフが実際に機能したことを確認。ユーザー指示により以下を追加対応: (1) L424のJSON破損（`feasibility_notes`文字列値の末尾を全角鉤括弧「」で終え閉じ引用符を書き忘れ）を`call_goal_essence_analyst`のプロンプト修正で解消（BL-090として新規起票・`done`化、D-066）。(2) L16700のWhiteboard Annotate失敗（BL-074の正規化フォールバックも救えない0/0一致）をBL-074に追記し、根本解決に必要なBL-079の優先度をP3→P2へ引き上げ。(3) L27529のログ途切れはドライラン実行中のためBLとしては起票せず。新規`tests/test_bl090_json_string_fullwidth_quote_guard.py`（1件）、`python -m py_compile`合格、`check_docs_consistency.py`合格。 |
| 2026-07-25 | ドライランがさらに進行し、ユーザーが`log/2026-07-25/1913`の続き（L26827〜L45646）をレビュー依頼。まずtask_1_3のL定義修正（Ver.2、案A=片道採用、数式変形による等価性検証済み）を確認。次にtask_2_1（安全基準策定）で、Detectorが単位混同の計算誤り（`0.15×L<30→L<200km`、正しくは`L<3.33km`という60倍の桁違い）を発見したが3回多数決2:1でminor判定となり、`route_after_expert_detector`の差し戻しをトリガーせず誤りが放置された事象を確認（後続のUser AIが独立に同じ誤りを発見し条件付き承認で事なきを得たが偶然の救済）。この「minorは強制修正されない」問題について、ユーザーから「issue_BLリストに放り込み全closeまでフェーズ完了と見なさない」という具体的な設計材料の提示があり、既存のBL-051（Detector限定の同一構想）・BL-077（一般化版）に追記・相互リンク。さらにDetectorの「3回多数決」の実装を検証したところ、単一の`query_AI`呼び出し内でモデル自身がtrial1/2/3を自己申告するだけで、独立サンプリングではないことを確認（ユーザーの疑念が的中）。続けて`1913`ログの最新部分をレビューし、task_2_1の3回目修正でExpertのwrite_agreement(edits)が失敗→最終iterationでツール強制排除→モデルが独自のツール呼び出し風疑似XML（`<｜DSML｜tool_calls>...`）を平文出力→実際には未実行（`get_last_write_agreement_succeeded()=False`）にもかかわらずDetector・Decision Extractorがこれを鵜呑みにして誤って承認・DB記録するという重大な事故を発見（実際のホワイトボードはV2のまま、物理的矛盾・誤数値が現存）。ユーザーの「BL起票と、BL79も含めて修正して」との指示により、BL-091として新規起票・対応（`call_detector`の両プロンプトにwrite_agreement成否を明示するブロックを追加）、BL-079も実装（当初の「注釈挿入自体のツール化」はdecision_id未確定問題のため見送り、代わりに`verify_whiteboard_excerpt`ツールで事前検証させ、ドメイン妥当性レビュー側の取りこぼしにはプログラム側フォールバックで対応）。新規`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`（7件）、`python -m py_compile`合格、既存BL-062/074/076/079/087/088/089/090/091関連92件Pass。D-067・D-068として記録。 |
| 2026-07-25 | ユーザーが別AI（別チャット）による`log/2026-07-25/1913`の独立レビュー結果（12項目指摘）と、さらに各項目を実際のログ行まで追跡させた結果を共有。独立レビューの12項目は全て事実に基づく正確な指摘だったことを確認。追跡の結果、#1/#6/#8は構造的な矛盾が根本から作り直される「良い解消」だった一方、#3/#4/#7/#10は数値を検算・訂正したのではなく該当箇所を削除・抽象化して見えなくしただけの「悪い解消」であり、この差し戻し圧力下での「検証せず削除して逃げる」パターンをBL-092として新規起票（記録のみ、対応方針未確定）。#2（task_5_2の根拠不明な「2.1分」）は解消されず、後続のtask_2_1実行時に同種の単位混同（「停車後40.5秒で通過」という物理的に不可能な記述）として再燃していたが、これはBL-091で既に発見・修正済みの事故と同一であることを確認（ユーザーからも「先ほど修正したもの」と確認）。#12（重複再計算）はdraft1で49回→draft2で24回→draft3で8回と明確に減少しており、D-065の実効性が実データで裏付けられた。このドライランはtask_2_1/2_2で停止しておりPhase 3以降は未実行のため、#3/#4/#7/#10/#11の一部は実行時の再検証機会自体が無かった点も記録。 |
| 2026-07-25 | ユーザーから「reviewerの差し戻し圧力に対しtask_plannerが検証せず削除して逃げる（BL-092）」問題への対応案として、ホワイトボードをファイル化しdiffツールを使う設計を提案された。検討の結果、DB編集からファイル編集への回帰はBL-074/034/040で既に解決した脆さ（ファイル名予測不能・孤児ファイル・topic文字列ドリフト）を再導入するリスクがあるため採用せず、代わりに既にDBでバージョン管理されている`plan_drafts`に対し`difflib`で機械的diffを取る新規ツール`diff_plan_draft_versions`を追加する方針を提示し、ユーザーの承認（「OK修正して」）を得て実装。`call_task_plan_reviewer`に配線し、以前指摘したtask_idについて記憶・印象ではなく実際の版間diff（数値が訂正されたか、記述ごと消えたかの機械的事実）で判断するよう指示を追加。新規`tests/test_bl092_plan_draft_diff_verification.py`（8件）、既存`test_bl087_stage2_task_plan_reviewer_node.py`のツール一覧完全一致アサーションを部分一致に修正、`python -m py_compile`合格、関連回帰111件Pass。D-069として記録。BL-092を`done`化。 |
| 2026-07-26 | ユーザーから「情報の抽出・保存・伝搬の観点で足りないものはあるか」と棚卸しを依頼され、think構造化理由づけの非永続性、Detectorのwrite_agreement監査有無、task_planner系3関数のwrite権限欠如、minor指摘の追跡漏れの4点を洗い出し。write_agreement→Detector監査は既に実装済み（グラフエッジ`expert→expert_detector`等＋ライブDB再クエリ＋BL-091成否フラグ＋BL-033独立検算＋R5思考過程監査の四重防御）と確認しユーザーの懸念を解消。残る2点をBL-095（`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`への`write_agreement`配線、読み書き非対称の解消）・BL-096（Detectorの`observations`とminor追跡漏れを統合したissue管理DB新設）として新規起票（いずれも`open`、設計未着手）。ユーザー方針により、まずBL-095を実装し、その後BL-096の設計をPlan modeで行う順序とした。 |
| 2026-07-26 | BL-095（`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`への`write_agreement`配線）を実装・`done`化。`_check_write_permission`のロール表に`task_planner`/`goal_essence_analyst`（`status="Proposed"`限定）・`task_plan_reviewer`（`status="Rejected"`限定、BL-062と同型）を追加し、3関数のプロンプトに記録・SUPERSEDE指示を追記。新規`tests/test_bl095_task_planner_write_agreement.py`（25件）、`python -m py_compile`合格、関連クラスタ256件Pass。D-077として記録。ユーザー指示により次はBL-096の設計をPlan modeで実施。 |
| 2026-07-26 | ユーザーが別AIに`log/2026-07-26`ドライランのログと本体プログラムを独立レビューさせた結果を共有。数値の出所（確定値/推定値/運用ルール）の区分表示、`think`の`decided`/`why`/`rejected`等の空欄削減、スコープ逸脱禁止の明文化・最終チェックリスト固定化の3提案をBL-097として新規起票（`open`、設計未着手）。ユーザー方針により、BL-095コミット後・BL-096のPlan mode設計に先立ち起票のみ実施。 |
| 2026-07-26 | 同じ別AIレビューの続報を共有。`cela_main.py`が責務を密に抱えた「巨大な一枚岩」であるとの指摘をBL-098（永続化層/ツール層/プロンプト・ノード層/UI・ログ層への分離）として新規起票。`_CURRENT_*`モジュールレベルグローバルへの依存、`get_max_tokens`等の文字列部分一致による「ゆるい制御」、`think`必須化が最終的にはモデル遵守に依存する構造、の3点をBL-099として新規起票。いずれも`open`・設計未着手、機能面が一段落してから着手する方針。 |
| 2026-07-27 | 同じ別AIレビューのさらなる続報。前提を疑い代替案を提案する際、「疑った前提・疑った理由・代替仮説・期待される利点・採用に必要な追加情報」の5項目セットを構造化して系譜として残すべきとの指摘をBL-100として新規起票（`open`、設計未着手）。既存の`ESCALATE_PREMISE_CONCERN_TOOL`（BL-086）が前半3項目に相当するフィールドを持つ一方、期待される利点の定量化・採用に必要な追加情報の2項目が欠けていることを確認。BL-096（issue_log）との統合可否を含め設計未着手。 |
| 2026-07-27 | BL-096（issue管理DB）の基本設計をPlan modeで確定。再浮上トリガーは累積回数しきい値方式（ユーザー選択）、書き込み権限はMVPでDetector/User AIの2ノードに限定（CREATE両方、RESOLVEはUser AIのみ）とした。設計内容は`docs/design/back_log/BL-096/BL096_basic_design.md`に保存。あわせてユーザー指示により文書構造を再編：`docs/design/issue_backlog.md`を`docs/design/back_log/issue_backlog.md`へ移動し、BL番号ごとの基本設計書を`docs/design/back_log/BL-xxx/`配下に保存する運用を新設（今後のBLもこの規則に従う）。移動に伴い参照8ファイルの相対リンクを修正し、`scripts/check_docs_consistency.py`の`issue_backlog.md`参照パスも更新、`[OK]`を確認。実装はまだ着手していない。 |
| 2026-07-27 | ユーザーから2点の指摘。(1) 文書構造のパス誤記を訂正：`docs/back_log/`ではなく`docs/design/back_log/`が正しい配置であるとの指摘を受け、`issue_backlog.md`・`BL-096/`フォルダを`docs/design/back_log/`へ再移動し、全リンクを再修正。(2) BL-096設計への実質的な懸念：累積回数しきい値によるエスカレーションが`write_issue(CREATE)`の再呼び出しのみに依存しており、AIが「既に登録済みだから」とCREATEを見送るとエスカレーションのシグナルが失われるリスクを指摘。あわせて`read_open_issues`のデフォルトで解決済みも表示すべき（全件表示は別スイッチ`list_all`）、`get_open_issues_from_db`は`get_issues_from_db`に改名、との指示。さらにユーザーが別AIによるBL-096設計書レビュー（`BL096_design_review.md`、B/A/D/C/G の5指摘）を共有。B（初回major起票がreflectionに届かない設計バグ）を含め全指摘を反映し、設計をv2に改訂（D-079）。`docs/design/back_log/BL-096/BL096_basic_design.md`を全面改訂、`check_docs_consistency.py`で`[OK]`を再確認。実装はまだ着手していない。 |
| 2026-07-27 | Claude自身がD-079（v2）の設計レビュー中に、`(topic, task_id)`重複検知キーとREAD経由の再発カウントが矛盾すること（タスク横断の再発検知というBL-096の目的自体を破壊する）を発見。ユーザーへ報告し、`topic`単独キーへの差し戻しとREAD側トリガーの4条件への厳格化を提案、承認を得た。あわせてユーザーから「call_reflectionはissue経由ではほぼ機械的にfacilitatorへ橋渡しするだけか」との確認、facilitatorルーティングの機械的強制指示、「issue解決後にエスカレーション直前の状態へ戻す復帰通知が必要では」との指摘を受け、既存コード（`call_reflection`/`route_after_reflection`/`facilitator_node`）を実際に読んで調査。BL-051が当初求めていた「issueリストをフェーズ終了条件とする」は既存のreflection/facilitator機構（discussion_status="completed"の抑制→facilitatorへのルーティング）がそのまま使えることを確認し、新規ゲートを作らずここに接続する方針に確定。`discussion_status`の機械的上書き、facilitatorへのescalated issue構造化データ注入、エスカレーション解除の一度きり復帰通知（`escalation_active`/`escalation_just_resolved_notice_pending`）を設計に追加し、v3として確定（D-080）。ユーザーの「設計書にまとめ、実装に入ってください」との指示を受け、実装に着手。 |
| 2026-07-27 | BL-096（v3設計）を実装・`done`化。`issue_log`テーブル、`WRITE_ISSUE_TOOL`/`READ_ISSUES_TOOL`、`_write_issue_impl`/`_check_issue_permission`/`_read_issues_handler`/`get_issues_from_db`/`_bump_issue_occurrence`/`_get_escalated_issues`/`_build_escalation_resume_notice`を新設し、`call_detector`（自動バックアップ書き込み含む）・`generate_user_utterance`・`reflection_node`/`call_reflection`（discussion_statusの機械的上書き）・`facilitator_node`/`call_facilitator`（escalated issue構造化データ注入）・`LineageState`（`escalation_active`/`escalation_just_resolved_notice_pending`）に配線。実装中、`_read_issues_handler`で`task_id`引数を検索フィルタと再発カウント用の呼び出し元文脈に同時に使っていたため、READ経由の再発検知（タスク横断での再発見）が機能しないバグを発見・修正（D-081）。新規`tests/test_bl096_issue_log.py`（42件）、`python -m py_compile`合格、関連クラスタ198件Pass。実LLM再ドライランでの効果確認は次回待ち。 |
| 2026-07-27 | ユーザーがドライラン中（`log/2026-07-27/1438`）に、task_plan_reviewerに差し戻されたtask_plannerが前回の「フェーズ・タスク表」ホワイトボード（plan_drafts）を参照せず全面作り直しをしている実例を報告。ドライランを停止し調査したところ、`task_plan_reviewer_node`が`state["phases"]=[]`で前回計画を消去し、`call_task_planner`には自由文のフィードバックしか渡っていないことが原因と特定。副次的にBL-095のwrite_agreement（entry_type="Decision"）がread_deliverable_file（entry_type="Deliverable"限定）で参照不能な不整合も発見。ユーザー提案の「パッチ方式・機械的マージ」も検討したが、まず軽量な対策として新規`read_plan_draft`ツールをtask_plannerに配線しBL-101として起票・実装（`done`）。実装中に見つかったplan_drafts検索・プロンプト重複の副次バグも修正。 |
| 2026-07-27 | ユーザーから「detectorのドメインレビュワーにはthinkツールしかありません。read_verified_fact/read_deliverable_file/write_agreement/verify_whiteboard_excerpt/write_issue/read_issuesは渡してもよい気がします」との指摘。数値監査パス（第2段）が既に持つ6ツールをドメイン妥当性レビューパス（第1段）にも追加し、プロンプトにもBL-096利用手順と利用可能ツール一覧を追記（D-083）。既存テスト`test_bl093...`のTHINK_TOOL検出ウィンドウをツール追加分だけ拡張して追従。関連クラスタ109件Pass、`check_docs_consistency.py`合格。ユーザー指示によりコミット（`09962d7`）。直後、ユーザー依頼で実ドライラン`log/2026-07-27/1551`をレビューしたところ、この変更で新たに露見した実バグを発見：`call_detector`の`_CURRENT_CALLER_ROLE="detector"`設定が第2段直前にしかなく、第1段実行時は直前ノード（`call_expert`）の`"expert"`のままだったため、Detector(Domain Review)の`write_issue(CREATE)`が権限エラーで拒否され、有効な懸念（オペレーター最低2名常駐とピーク時1名充当の矛盾）が`observations`止まりになっていた。BL-102として新規起票・即修正（`_CURRENT_CALLER_ROLE`等の代入を`call_detector`冒頭へ移動、`done`）。関連クラスタ113件Pass。 |
| 2026-07-27 | ユーザーからhydrate（ノード間コンテキスト引き継ぎ）設計の相談。ユーザー自身が過去に設計した`NPU-Context-Saver`のhydrate機構（pin・Time-Aware RAG・トークン予算による段階的間引き）と対比し、トークン予算制御とRAGは見送り、issue_logのescalated行のpin導入・BL-093 thinkの最終呼び出し内容を要約に採用・escalated issueのcall_expert/generate_user_utteranceへの詳細込み注入の3点を設計。調査中に、User AIの発言がdecisionsテーブルに一度も記録されていない欠落と、generate_user_utterance内の独自インラインタイムラインが無制限（unbounded）に全件展開されていた非対称も発見しスコープに追加。設計書を`docs/design/back_log/BL-103/BL103_basic_design.md`に保存、BL-103として新規起票。ユーザー指示「ドキュメントをback_logフォルダに保存して、実装」を受け実装に着手。実装前に、generate_user_utteranceの無制限インラインタイムライン撤去が`user_always_remember`フラグの意図（User AIには全部覚えていてほしい）と矛盾しないか確認したところ、当初計画通り窓付きへ統一する方針が承認された。BL-103として実装完了・`done`化。新規`get_last_think_summary()`/`_build_escalation_pin_text()`、`expert_node`/`generate_user_utterance_node`のwhy改善・欠落していたmake_decision追加、`generate_user_utterance`の共通hydrate関数への統一を実装。新規`tests/test_bl103_hydrate_context_improvements.py`（12件）、既存`test_bl086...`の2テストがgenerate_user_utterance_nodeの新規DB書き込みで壊れたため修正。`python -m py_compile`合格、関連クラスタ179件Pass。 |
| 2026-07-27 | フルオフラインテストスイート（`pytest tests/ -q -k "not live"`）実行、391 passed, 35 deselected（47分、失敗なし）。ユーザーがドライラン`log/2026-07-27/1739`の`log_with_prompt.md`を見て「プロンプトが長大」と指摘。DBから直接測定した結果、hydrate_context/agreements_text/escalation pinの合計は約3万字で、ログ上の1ノードあたり15〜19万字の6分の1未満と判明。残りの大半は(1)call_expertの`phases_json`（13,361文字、毎回全文）含む固定・準固定の指示文ブロック、(2)モデル自身の思考・成果物出力であることを特定。ユーザーから「フェーズ・タスク表全体はuser以外はツール呼び出しで必要な時に見るようにしても支障ないか」と提案があり、`call_expert`は`current_task_json`/`verified_facts_json`/`deferred_notes_text`で既に機能的に必要な情報を得ていること、BL-025のスコープガードレールの趣旨とも整合することを確認し支障なしと回答。続けてユーザーから、OpenRouterのキャッシュヒット率が40%→5%に急落した件の相談があり、`call_expert`のプロンプト組み立て順（変動内容が冒頭、固定指示文がその後ろ）がプレフィックスキャッシュに不利な構造だったことを確認・報告。ユーザーの「OK進めて。他のノードも順次プロンプト順の整理を進めてください」との指示によりBL-104として起票、設計書を`docs/design/back_log/BL-104/BL104_basic_design.md`に保存し実装着手。新規`READ_PROJECT_PLAN_TOOL`/`_read_project_plan_handler`/`_build_project_plan_toc`を追加し`call_expert`を実装（ToC化＋並び替え）、続けて`generate_user_utterance`（phases_json全文は維持しつつ並び替え）、`call_detector`のdomain_prompt（ドメイン妥当性レビュー用プロンプト）の順に、各ブロックの位置的参照（「上記の」「後述の」等）を個別確認しながら並び替えを実装。新規`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`（20件）、`python -m py_compile`合格、関連クラスタ307件Pass。`call_detector`の数値監査用`prompt`と低頻度ノードは未着手のまま継続予定。 |
| 2026-07-27 | ユーザーがドライラン（`log/2026-07-27/1911`、call_expert等3ノードまでの並び替え適用時点でチェックポイント再開）を実施し「13-15%程度まで改善しました」と報告、ログレビューを依頼。全文をgrepで確認したところTraceback/例外なし、BL-093のthink未添付差し戻しのみで想定内。`log_with_prompt.md`を直接grepし、agreements_text→「上記の【決定事項DB】は」・whiteboard→BL-076・厳守事項→スコープブロックの各位置的参照が実際の送信プロンプトでも維持されていることを確認。Expertが`read_project_plan`を1回呼び出し全フェーズ・全タスク情報を正しく取得、Detectorがtask_2_2の内部矛盾（山間部必要台数の感度分析と推奨案の不一致）をmajor判定→修正後にminorへ正しく降格、という一連の判定ロジックも健全。BL-103のUser AI発言記録も実働確認（`[user] Expertへの発言（ラウンド7）`）。異常・品質劣化は検出されず。ユーザー指示「並び変え続行してください」を受け、`call_detector`の数値監査用`prompt`・`call_orchestrator`・`call_resource_arbiter`・`call_facilitator`・`call_integrator`・`call_reviewer`・`call_task_plan_reviewer`の並び替えを実装完了。`call_reflection`は「上記の」参照の多段連鎖により機械的分離が困難と判断し、自己完結するBL-093説明の移動のみに留めた。`call_task_planner`は「冒頭の指摘欄で指示した通り」がreviewer_feedback_blockの先頭配置を前提とする位置的参照であること、`call_goal_essence_analyst`はプロジェクト開始前に1回しか呼ばれずキャッシュ効果がないことから、いずれも意図的に見送り理由をコメントで明記。`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`を36件に拡充、`python -m py_compile`合格、関連クラスタ327件Pass。BL-104を実装完了として`issue_backlog.md`/`decision_log.md`を更新。全ノード適用後の効果測定は次回ドライラン待ち。 |
| 2026-07-27 | ユーザーから速報値でキャッシュヒット率が40%前後まで改善したと報告。続けて1911ログの改めてのレビュー依頼を受け、ノード呼び出し回数・think差し戻し回数・write_agreement/python_repl/read_verified_fact/write_issue/read_issues呼び出し回数・iter分布・escalated issueのライフサイクル・最終checkpoint状態を確認。Detectorの実在バグ検出→修正確認→降格の一連の判定、issue_logのエスカレーション解決フロー、`read_project_plan`の適切な利用、`facilitation_count=0`（停滞なし）は健全と評価。一方でiter分布がノード呼び出しあたり最大12まで伸びていること（ツールループ反復増加による希薄化の裏付け）、およびthink未添付差し戻しが12回発生していることを気づきとして報告。ユーザーから「Claudeのツール使用時の文脈維持はどうやっているか（思考ストリームをそのまま再注入？）」との質問があり、Claude API（extended thinking）はthinkingブロックが署名付きで会話履歴の正式な一部として自動的に往復するのに対し、CELAはOpenRouter経由の多くのプロバイダがreasoningトークンの往復を保証しないため、`think`ツールという通常のtool_use/tool_result経由の手作りの代替チャネルで同じ効果を再現している、という構造的な違いを説明。続けてユーザーから「thinkツールと同時に呼ぶことを厳守しろ！くらいの強い言葉で書いてください」との具体的指示を受け、think以外の全ツールスキーマ説明文（14箇所、"[BL-093] MANDATORY: you MUST also call `think`..."に強化）と、tools付与済み各ノードのプロンプト本文（10箇所、「厳守しろ！」調に強化）の文言を、指示内容は変えずに強制力の伝わり方だけ強化。BL-093に追記修正4として記録。関連クラスタ261件Pass、`python -m py_compile`合格。 |
| 2026-07-27 | ユーザー依頼で`log/2026-07-27/2044`（think文言強化後の再ドライラン）のツール使用失敗を調査。think未添付差し戻しは12回→3回に減少（正規化比較でも約半減）、`write_agreement`必須フィールド不足等の他の構造化エラーは0件と、think文言強化の効果を確認。一方で新規に`⚠️ role連続を検出: index 3,4 = 'user'`という警告を発見し報告したところ、ユーザーから「昔ノードの配線ミス時によく出ていた、最近はレジューム時にも見かけていた」との補足があった。追跡した結果、`run_ai_vs_ai_loop`の自前JSON checkpoint機構が`--resume`時に必ずグラフのentry_point（`goal_essence`）から全体再走行し、`generate_user_utterance_node`には再入場ガードが無いため無条件にuser発言を二重に積んでしまうという再現性のあるバグと特定。ユーザーから「本来はLangGraphのcheckpointerを使えば真の一時停止が利くのでは」との設計上の指摘があり、Context7で現行のLangGraph公式ドキュメントを確認したところ、`checkpointer`+`thread_id`ベースの再開はentry_pointからの全体再走行ではなく中断ノードの続きから再開すること、ただしノード内部途中の再開には非対応で公式ドキュメントも"Do not create new records before an `interrupt` call"と明記していることを確認。ユーザー指示「とりあえずBL化して、ブログ用の話題を整理して」を受け、Plan Modeで方針を整理し承認を得た上で、BL-105として起票（Tier 0/1/2の3段階の対応案を整理し採否は未決定のまま`open`）。あわせて`decision_log.md`にpending論点を追加し、`docs/blog/blog_topics.md`に今回のセッションで得られた4件の題材候補（checkpoint設計の続編、Claude thinkingとの比較、プロンプト順序とキャッシュヒット率、think文言強化の効果）を追記。実装（コード変更）は行っていない。 |
| 2026-07-27 | ユーザー依頼で新規フルフレッシュラン`log/2026-07-27/2157`をレビュー。Traceback/例外0件、role連続警告0件（resumeでないため、BL-105根本原因診断の傍証）、JSON層2リトライ1件（正常復帰）、think未添付差し戻し21件（Detector系が12件/21件と過半数、iter総数比では1911/2044の中間水準で明確な悪化とは言えない）、task_1_1のExpert成果物がPython検算付きで「車両4台購入時にシステム構築費0円になる矛盾」「全賃金シナリオで年間維持費上限超過」という構造的に解けない制約を正しく可視化していることを確認、異常なしと報告。直後にユーザーから「1時間平均でキャッシュヒット率5.5%、分単位では0%も目立つ」との追加報告があり、`_query_AI_live`のツールループを再調査。BL-093/D-074の自動reasoningダイジェスト（`auto_reasoning_history`）が、system prompt（index 0）直後のindex 1という、tool呼び出し履歴（index 2以降、iterごとに肥大化する本来一番キャッシュ効果が大きい部分）より手前に、毎iter内容が変わるメッセージとして固定index上書きされていたことを発見・報告。ユーザーから「古いiterの要約部分はiterが進んでも不変のはずでは」との的確な指摘があり、think summary確定後は不変であること自体は正しいと訂正した上で、問題の本質は「可変部分と不変部分が同じメッセージに同居し、かつtool履歴より手前にある」ことだと整理し直した。ユーザー指示「修正してください、ドライランで様子を見ます」を受け、BL-106として起票・実装（`done`）：digestメッセージをオブジェクト参照（`auto_reasoning_digest_message`）で追跡し、都度`loop_messages`末尾から前回分を除去して末尾に付け直す方式に変更。既存テスト`tests/test_bl093_d074_auto_reasoning_enforcement.py`のdigest位置検証（旧: index 1固定）を新方式（末尾）へ更新。`python -m py_compile`合格、関連クラスタ135件Pass。実LLM再ドライランでの効果確認はユーザー実施予定。 |
| 2026-07-27 | BL-106修正後もユーザーから「iter時はキャッシュヒット0%のまま」と報告。ユーザーが「なぜか最新の要約は常に先頭に置かれていたのですね」とコード理解を確認した直後の再報告だったため、digest位置以外の要因を再調査。OpenRouter公式ドキュメント・ブログをWebFetchで確認したところ、「`provider.order`を手動指定するとsticky routing（同一会話の連続リクエストを同じバックエンドへ固定する仕組み）が無効化される」と明記されており、既存コードが常時`provider.order=["novita/fp8","parasail/fp8"]`を指定していることが根本原因と特定・報告。ユーザーから「釈然としません。provider固定はだいぶ前からで、python計算もツールとして使ってきたが、それでもキャッシュヒットは50%前後あった。26日17時台以降に急落した」との反証を受け、`git log`でBL-093コミット（`4a0bb46`、2026-07-26 18:03、"Wire THINK_TOOL into every LLM-calling node including previously tools=None single-shot ones"）を確認。BL-093以前は多くのノードがtools=Noneの単発呼び出しでsticky routing不要のクロスコールキャッシュにより50%前後を維持でき、BL-093でほぼ全ノードがtoolsループ経由に切り替わったことで「ループ内はprovider.orderのせいで元々0%」という弱点の影響が急拡大し急落として表面化した、という整理でユーザーの時系列指摘と矛盾しないことを説明。ユーザー指示「分かりましたsession_idに変えてください。ただし、もとに戻せるようにして下さい」を受け、BL-107として起票・実装（`done`）：切り替えフラグ`_USE_STICKY_SESSION_ROUTING`を新設し、`True`時は`provider.order`を送らず`extra_body["session_id"]=f"{_CURRENT_RUN_ID}-{label_lower}"`でsticky routingを有効化、`False`で元のprovider.order固定へワンライン復元可能にした。`python -m py_compile`合格、関連クラスタ135件Pass。実LLM再ドライランでの速度・キャッシュヒット率への効果確認はユーザー実施予定。 |
| 2026-07-28 | ユーザーからBL-107の実ドライラン結果として「確かにキャッシュヒットは改善しました」と報告があり、issue_backlog.md/decision_log.mdの完了条件を実測確認済みに更新。直後、「改善したといいましたが、やはり微妙かもしれないです」との追加報告があり、digestの実際の書かれている位置（iter番号ラベルが先頭付近か）を確認するよう依頼。調査の結果、`log_with_prompt.md`はツールループの最初のiterationの送信プロンプトしか記録しておらず（`_query_AI_live`冒頭で1回だけprintする実装）、iteration 2以降のdigestは一度もログに出力されていないことが判明。ユーザーが開いていた`log/2026-07-28/0033/log_with_prompt.md`にはdigestの実物が存在しないことを説明した上で、`log_no_prompt.md`の生reasoning/think summaryを実際のコードロジックに通して手元で再構築し提示（Detectorノードiter1〜8）。窓方式（直近2iterは生・古いのは要約）では、要約済み部分は数十〜数百文字と軽微な一方、生reasoning全文は1回あたり数千文字（最大6,077文字）に達しdigestの大半を占め、窓の境界が動くたびdigestの中身自体が毎iter変化し続けていたことが「微妙な改善」の実体と特定。ユーザーから「要約せず、単純に生ログを積み上げたほうがキャッシュが働き、結果的に安いしシンプルかな？」との提案があり、同ログで試算（iter8時点で要約方式6,341文字 vs 単純累積19,324文字、約3倍）した上で、要約への切り替わりという不安定要因自体が消えること・AI自身のsummaryによる情報欠落が無くなることを説明し支持。ユーザーが「累積方式に完全置換え」を選択（窓方式・ハイブリッド案・実測待ち案を比較検討の上での明示的選択）。BL-108として起票・実装（`done`）：`_AUTO_REASONING_VERBATIM_ITERS`の窓管理と`_THINK_REASONING_LOG`からのsummary逆引きを廃止し、全iterationの生reasoningを要約せず末尾追記し続ける方式へ全面置換。既存テスト2件を新方式に合わせて改名・修正、`python -m py_compile`合格、関連クラスタ135件Pass、フルオフラインスイート実行中。 |
| 2026-07-28 | フルオフラインスイート完了（425 passed、`test_r3a_t6_integrator_and_arbiter_have_read_and_write_tools`が1件失敗したが単体再実行では合格する一過性の失敗）。ユーザーからBL-108の実ドライラン結果として「30分平均で45%くらいに回復」と報告があり、issue_backlog.md/decision_log.mdの完了条件を更新。続けてユーザーが「キャッシュ割引はおおむね1/10の値段になるので、プロンプトが3倍でも安くなる可能性が高い」と発言したため、pythonで机上試算（`cost = size×(1-0.9×hit_rate)`）したところ、45%ヒット・3倍サイズは旧方式（1倍サイズ）のどのヒット率と比べても1.9〜2.8倍高くつき、3倍サイズが1倍サイズの無キャッシュ状態に並ぶには約74%以上のヒット率が必要という、ユーザーの想定とは逆の結果を提示・報告（実際の$コストはOpenRouter Activityダッシュボードでの実測を推奨、未確認のまま）。ユーザーがIDEで`cela_main.py`を開いた状態で、ログに出ていた「[Decision Extractor] tools attached: ['think']」を見て「Decision Extractorってthinkしかツールを持っていない？」と質問。調査の結果`call_decision_extractor`はDB読み書き不要な単発抽出タスクで`think`ツールの効果（複数iterをまたぐreasoning引き継ぎ）が本来不要と判明、同型の`call_orchestrator`/`call_reflection`/`call_facilitator`も含め報告。ユーザーが「think、つまりメモ帳が思考の手助けになるかと思いましたが要らないですかね？」と確認したため、これら4ノードは元々`tools=None`でもネイティブの`reasoning_effort_level`（Decision Extractor="medium"、Reflection="high"）を持っていたことを説明し、think tool無しでも思考の質は落ちないと回答。ユーザーが「なるほど。ではthinkしかツールがないノードは抜きましょう」と全4ノードの差し戻しを指示。BL-109として起票・実装（`done`）：4ノードとも`tools=[THINK_TOOL]`を削除しtools=Noneへ差し戻し、案内文も削除。実装中に、`orchestrator`/`facilitator`が`reasoning_effort_level`を`elif tools is not None`経由のフォールバックでしか得ていなかったため、tools=None化のサイレントな副作用でreasoningが無効化される罠を発見し、両ラベルを明示条件へ追加して修正。`_reset_think_scratchpad()`はBL-103のノード境界マーカーとして機能維持のため4ノードとも削除せず。関連テスト更新（`_ALL_THINK_WIRED_FUNCS`から4関数除外、新規テスト追加、前提が消滅した旧テスト2件を削除）、`python -m py_compile`合格、関連クラスタ145件Pass。 |
| 2026-07-28 | BL-109の議論を受け、ユーザーが「であるならば、自由なthinkの使用も意味がないですね。というか、今はコンテキストを丸ごと引き継いでいるので、think自体も意味がないか」とBL-093/D-074のthink機械的強制そのものの必要性を問い直した。`_query_AI_live`を確認したところ、ネイティブのreasoning（delta.reasoning）はthink呼び出しの有無に関わらず毎iter無条件で`reasoning_parts_all`へ蓄積されており、BL-108によりそれが要約されずそのままdigestとして次のiterへ引き継がれることを確認。BL-093/D-074が本来解決しようとした「reasoningがターンをまたいで引き継がれない」問題は、think呼び出しの有無に関係なく既にBL-108のdigestで解決済みと判明したことを報告し、`think`固有に残る価値は「decided/why/rejected等の構造化」のみで根拠は当初より弱く、機械的強制自体は「think未添付差し戻し」という実コストを生み続けていた旨を説明。ユーザーが「thikは残して、他ツールとの強制は外してください」と指示。BL-110として起票・実装（`done`）：`_query_AI_live`のツールループから、think(summary付き)の有無で差し戻すか判定する分岐を削除し、`msg.tool_calls`を無条件でdispatchするBL-093以前と同型の構造に戻した。thinkツール自体・TOOL_DISPATCH・BL-108のdigest自動蓄積ロジックは維持し、モデルが任意でthinkを呼べば従来通り記録される。あわせて、もう存在しない強制を前提にした案内文を修正：英語ツールスキーマ側の"[BL-093] MANDATORY: you MUST also call `think`..."（14箇所、byte-identical）を"[BL-110] Optionally call `think`...it is no longer required..."へ、日本語プロンプト側の「〜を同時に呼ぶことを厳守しろ！think無しでこれらのツールだけを呼ぶと、その応答のツール呼び出しは一切実行されず、丸ごと無駄になります。」（10ノード）を「〜を呼んで検討過程を書き残しても構いません。」へ、それぞれ全面置換。`tests/test_bl093_d074_auto_reasoning_enforcement.py`の差し戻し検証2件を実行される前提へ置換しモジュールdocstringも更新。`python -m py_compile`合格、関連クラスタ130件Pass、フルオフラインスイート実行中。 |
| 2026-07-28 | BL-108/BL-110適用後もキャッシュヒットが改善しないため、ユーザーが`_query_AI_live`のコードをGeminiに提示し第三者レビューを依頼、その調査結果と修正提案がユーザー経由で共有された。指摘内容: BL-108は「全iter分を1メッセージに再結合→古いdigestを削除→末尾に付け直す」方式だったため、新規tool呼び出しメッセージが必ずdigestの手前に追加され、次のリクエストではdigestの旧位置に別のメッセージが来ることになり、そこから後ろ全体（本来最もキャッシュさせたい蓄積履歴）が毎iterプレフィックス不一致になっていた。プレフィックスキャッシュが機能する絶対条件「一度追加したメッセージは二度と変更・削除・移動しない」を満たせていなかったと判明。ユーザーの提示を受け、実際にコード上でiter2向け・iter3向けリクエストの中身をトレースし、共通する厳密なプレフィックスが先頭4メッセージまでしかないことを確認してGeminiの指摘の正しさを検証。BL-111として起票・実装（`done`）：全iter分の再結合をやめ、iterationごとの生reasoningを独立した新規systemメッセージとして末尾に追記するだけ（真のappend-only）に変更、不要になった`auto_reasoning_history`/`auto_reasoning_digest_message`を削除。既存テストを新構造に合わせて修正し、新規`test_bl111_consecutive_requests_are_a_strict_prefix_of_each_other`で「iterNのリクエストがiterN+1のリクエストの厳密な先頭部分になっている」というプレフィックスキャッシュの必須条件そのものを回帰テスト化（BL-108時点でこのテストがあれば即座に発覚したはずのバグの再発防止）。あわせて、ユーザーがIDEで`_query_AI_live`の`_USE_STICKY_SESSION_ROUTING`・provider order・reasoning_effort_levelを直接手動チューニング中であることを確認したため、固定文字列に依存していた`test_bl109_reasoning_effort_level_preserved_for_reverted_nodes`を構造的な検証に変更し、ユーザーの変更を尊重してコード側は変更しなかった。関連クラスタ131件Pass、`python -m py_compile`合格、フルオフラインスイート実行中。 |
| 2026-07-28 | フルオフラインスイート完了（420 passed、2件失敗はいずれも再実行で解消: `test_r3a_t6_integrator_and_arbiter_have_read_and_write_tools`は前回同様の一過性テスト分離不良、`test_f26_detection.py::test_detector_no_false_positive_within_cap`は実LLM呼び出しを伴うテストで単体再実行では合格（682秒）しておりモデル判定のばらつきと判断、BL-108〜111の変更に起因する回帰ではないと確認）。ユーザーから`log/2026-07-28/1420`（BL-108〜111適用後初のフレッシュドライラン）のレビュー依頼を受け、Traceback/例外0件・role連続警告0件・think未添付差し戻し0件（BL-110で強制自体を撤去したため指標として消滅、想定通り）を確認。Task Plan Reviewerがtask_4_2のdepends_on順序矛盾を実際に検出・差し戻す様子、Detectorが「運行時間: 8時間/日」というシナリオ本文（8:00〜20:00=12時間）と矛盾する成果物の前提を検出しissue化、Expertが`phase_1_task_1_1_V1.md`→`V2.md`で需要充足判定を含め実質的に再計算し修正する様子を確認し、issue_log・whiteboard差分の仕組みが機能していると報告。続けてユーザーから「タスク表、ホワイトボードへの指摘書き込み、差分更新、issueの有用性、その他db操作等はどうか？情報の構造化、伝搬性、AIが必要な情報が拾えているか？また、疑問に思う事はissueへ登録をしているか？AIが困っているようなことはないか？」との追加調査依頼があり、精査した結果、Detectorが先に登録済みの3件のissue（`task_1_1_折り返し時間3分`／`task_1_1_実効輸送力の矛盾`等）を、後続のUser AI（承認ステップ）が「read_issuesで確認する」と思考ログで述べたにもかかわらず実際には呼ばずに、`task_2_2_折り返し時間の現実性`等の別topic名で重複登録していたことを発見。`write_agreement`のUPDATEが`decision_what`必須フィールド欠落で1件失敗したが次iterで即座に自己修正しておりこちらは問題なしと判断。ユーザー指示「一応記載して」を受け、重複issue登録の件をBL-112として起票（`open`、対応方針は未確定・記録のみ）。コード変更は行っていない。 |
| 2026-07-28 | ユーザーが「一定の自立性と厳密性をもってAIが仕事をしている」「issueを積極的に使い内部思考を外部化できている」と評価した上で、「そろそろプロンプトを整理する必要があるかもしれない」と提案。思考/タスクフレームワーク（ツール取説含む）のプロンプト記載、システム/ユーザープロンプトの使い分け、冗長・バス特化・誘導表現の有無、注入情報の過不足という4観点を挙げ、他に必要な観点がないか質問された。プレフィックスキャッシュとの兼ね合い（頻繁な小変更はキャッシュ効率を損なう）、手順的指示の欠落チェック（BL-112がまさにその一例）、ツールschemaとプロンプト本文の重複・分散、出力形式の一貫性という4点を追加提案。ユーザーが「planにしたので、まずは調査お願いします」と依頼したため、Plan Modeで3体のExploreエージェントを並行起動し（(A)システム/ユーザープロンプト構成、(B)ツールschema・プロンプト重複、(C)ドメイン特化表現・冗長性）、それぞれ読み取り専用で全13ノードを調査。結果、(A)全ノード中`call_expert`/`generate_user_utterance`のみ真のsystem+会話ターン形式で他11ノードは単一user メッセージに全部詰め込み、`call_orchestrator`はBL-104の静的先頭/動的末尾方針をコード自身が守っていない、(B)THINK_TOOLスキーマの`description`だけBL-110の書き換え（14ツール）から漏れておりMANDATORY強制文言・旧window方式の説明が実装と矛盾したまま残存、10箇所・8箇所規模の重複ボイラープレート複数種、(C)`call_task_plan_reviewer`に過去の実インシデントの具体的数値がそのまま埋め込まれている等のバス特化表現、`call_decision_extractor`に未使用のデッドコード（`prompt_old`）、という4件の問題を発見・報告。AskUserQuestionで対応範囲を確認したところ、ユーザーは「THINK_TOOLの書き換え漏れ修正」のみを最優先スコープとして選択し（他3件は別途）、プロンプト変更粒度は「一括でまとめて1回」を選択。THINK_TOOLの`description`・`summary`パラメータ説明をBL-110と同トーンの実態に即した文言へ書き換え（BL-113として起票・実装、`done`）。D-093として決定記録。`python -m py_compile`合格、関連クラスタ97件Pass。他3件（`call_orchestrator`順序バグ・ドメイン特化表現・重複ボイラープレート統合）は別途スコープを決めてから対応。 |
| 2026-07-28 | ユーザー指示「先ほどの調査結果,A,B,Cの残りをbl化」を受け、BL-113未対応の残り3件を新規BL化（実装はまだ行わず記録のみ）。BL-114（`open`）: カテゴリA由来、`call_orchestrator`のプロンプト構築でコメントはBL-104の「静的先頭/動的末尾」方針を謳っているが、実際には動的な`goal_context`が先頭・静的な役割説明がその後という逆順になっているコードとコメントの矛盾。BL-115（`open`）: カテゴリB由来、think任意呼び出し説明（10箇所）・read_verified_fact/read_deliverable_file同期説明（8箇所）・検証回数抑制注意書き（6箇所）・暗算禁止注意書き（8箇所）・BL-093 think価値説明（10箇所）という重複ボイラープレート群と、`call_decision_extractor`内の未使用デッドコード`prompt_old`（約60行）、`call_expert`のsystem_prompt/light_system_prompt二重化、`call_detector`の同一呼び出し内の重複。BL-116（`open`）: カテゴリC由来、`call_task_plan_reviewer`への実インシデント数値（山間部12km・ルート全体80km等）の埋め込みを筆頭に、`call_task_planner`/`call_orchestrator`/`call_expert`/`call_detector`/`call_decision_extractor`/`generate_user_utterance`に散在する車両・シフト・労働基準法等の交通シナリオ特化例、および冗長な指示文・`generate_user_utterance`のf-string由来ゴミ文字混入。いずれも対応方針は未確定で、次回スコープ確定後に着手する。コード変更は行っていない。 |
| 2026-07-28 | ユーザーが「各ノードに対して適したドメイン非依存の思考フレームワークやツールフレームワークを整理したい」と提案し、Geminiが作成した13ノード分の推奨フレームワーク表（Task Planner=WBS+MECE、Expert=ReAct+仮説検証サイクル等）を提示、評価を依頼。Plan Modeで`cela_main.py`の各ノードの実装（docstring・実際のプロンプト本文）と突き合わせて検証した結果、13ノード中9ノード（Task Planner/Task Plan Reviewer/Orchestrator/Expert/Detector/Decision Extractor/Reflection/Integrator/Reviewer）は提案が実装と高い整合性を持ち採用可（◎）、残り4ノード（Goal Essence Analyst/Resource Arbiter/Facilitator/User AI）は部分的に妥当だがギャップがある（△）と判定。Goal Essence Analystは提案（デザイン思考+5 Whys）に「大まかな実現可能性チェック」という実装済みの観点1が含まれていない、Resource ArbiterのMoSCoW・FacilitatorのORIDは現状未実装で導入するなら実質的な出力形式変更が必要、User AIのOODAは名前だけでは効果が薄い懸念、という所感を報告。フレームワーク名を書くだけの「ラベル貼り」に終わらせないこと、BL-116の冗長性問題と衝突しないよう1ノードにつき主軸1つ+補助1つ程度に抑えることを付記。AskUserQuestionでユーザーが「評価のみで一旦区切り」を選択したため、BL-117として起票（`open`、評価のみ完了・コード変更は未着手）。Geminiの提案表全文と評価根拠は`docs/design/back_log/BL-117/BL117_investigation.md`に保存。 |
| 2026-07-28 | BL-117の「ラベル貼りのリスク」所感を受け、ユーザーがGeminiに「ツール使用も含めた全体のガイドラインを設けたい」と相談し、Detectorを例にした番号付き手順案（成果物確認→issue確認→悪魔の代弁者として思考→検算→think整理→issue登録）を提示しつつ「具体的すぎるとその手法でしか行動しなくなるのでは」と自ら懸念を提起。Geminiが「番号付き手順は作業ゲー化を招くため避け、①マインドセット②目的別行動オプション（順序不問）③ツール使用の鉄則と罠（ピットフォール）の3層モデルで抽象化すべき」と回答。ユーザーが「手順を定めすぎるか緩いガイドラインで気づきの余地を残すか、塩梅が難しい」と再提起したのに対し、自身のBL-117懸念（フレームワークの中身の空疎さ）とGeminiの懸念（順序固定による作業ゲー化）は同じ問題の異なる軸で対立しないこと、Geminiの3層モデルが両方を同時に解消する設計であることを整理して報告。あわせてGemini提案の「共通ツール利用の鉄則」部分は既にBL-115で特定済みの重複ボイラープレートと同一スコープであり新規に書かずBL-115側の集約対象とすべきことを指摘。ユーザーが「とりあえずこの設計をドキュメントに記録し、全体の進め方を考える」と決定したため、D-094として記録（設計原則の採用、実装は次回BL-117の△4ノード対応時）、`decision_lineage.md`論点74としても議論の経緯を記録。あわせてユーザーが「プロンプトの集約化で言うと、今は1つのpythonで大きな岩になってしまっているので、クラスごとにファイル化するなど疎結合にしていく整理も考えたい」と新たな論点を提起したため、BL-118として新規起票（`open`、設計相談中、具体的な分割方針は未検討）。コード変更は行っていない。 |
| 2026-07-28 | ユーザー依頼で`log/2026-07-28/1420`ドライラン（継続中）を再レビュー。round_count 2→7、turn 1→3に進行、Traceback/Exception/role連続警告0件は変わらず健全だが、task_1_2の数値修正登録を巡りDetectorが3試行多数決で`major`（虚偽の完了報告）と繰り返し判定するループが発生し、ログ全体の約半分（1M文字超）を占めていたことを発見。実際には過去ターンで既に登録済み（`AG-1785225752828`）だったが、BL-091の「今回success=0」文言が「実際には一切反映されていません」と断定的だったため誤判定が連鎖し、Detector自身が最終的に`read_deliverable_file`で確認し自己修正して収束。ユーザーが直前のBL-117/D-094（フレームワークの具体性は「順序」でなく「判断基準と罠」に持たせる）の議論を踏まえ「これはまさに罠の一例。プロンプトに書くべき」と指摘し、AskUserQuestionで「今すぐ小さく修正」を選択。BL-119として起票・実装（`done`）：`write_agreement_status_block`の「今回success=0」文言に、過去ターンでの既登録は正常であること・主張内容を実際に確認してから判定すべきことを追記。`python -m py_compile`合格、`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`7件Pass。あわせてFacilitator発火1回（task_1_1スコープの論点をtask_1_2進行中に持ち出したがUser AIが正しくスコープ外と押し返し）、issue重複（BL-112パターンの再現、想定通り）を確認。 |
| 2026-07-29 | ユーザーが`log/2026-07-28/1233`・`2257`・`2026-07-29/0751`など複数ログを追加調査し、`issue_backlog.md`にBL-120〜129のサマリー行を直接追記（Reflectionのパース失敗フォールバックによる強制巻き戻し、HALT未発火の不一致、Nemotron使用時のリトライ頻発、Detectorへのescalation pin未注入、BL-086ツール群の不使用、フェーズ単位issue足止めの未実装、write_agreement UPDATE後のホワイトボード反映漏れ、Detector検算コメントの繰り返し、長時間ドライランの原因不明な途中終了等）。あわせてユーザーが`log/2026-07-29/1322`（本日別途レビュー済み）についてAIモデル変更（DeepSeek→NVIDIA Nemotron 3 Ultra）の影響を報告：「DeepSeekは指示に一直線、Nemotronはより視座の高い対応が可能」という仮説、およびescalate_premise_concernが正式なツール経由で3件エスカレーションされ、その後のAIの動作方向性を明確に変えた実例が取れたことを共有。Facilitatorが提案した「task_1_1_review」という正式計画に存在しないtask_idでの成果物作成についても議論し、①Facilitator↔User数ラウンド対話→②User承認（目標のホワイトボード編集、旧文維持＋注釈＋理由記載必須）→③Detector確認（通常監査と目標変更判定の評価軸分離が課題）→④Task Planner再構成→⑤正式タスク化、という具体的なフロー案をユーザーが提示。あわせて「Expertが成果物なしにUser AIへ質問・相談できる双方向チャネル」の必要性、およびそれに伴う「User・Expertの迎合（collusion）」リスクをReflection/Facilitatorが監査すべきという論点も提起。round_countの実装（generate_user_utterance_nodeのみで加算、Detector/Reflection/Facilitatorは含まれない）を確認し、質問ラウンド導入に新規カウンターは不要と整理。迎合監査の定量化は困難なため、D-094の設計原則（判断基準と罠）に沿いReflectionへ「方針転換の重大さに見合った理由づけの有無」という判断基準を明記する方向を提案。ユーザー指示「ドキュメントを整備して」を受け、BL-120〜129に状態/経緯/対応/完了条件の詳細セクションを追加し、本日の議論をBL-126への追記（プロアクティブな前提再交渉ワークフローの具体化、モデル挙動観察の記録）、BL-130（Expert→User相談チャネル、新規起票）、BL-131（計画外task_idでの成果物作成リスク、新規起票）として整理。コード変更は行っていない。 |
| 2026-07-29 | ユーザーがGeminiとの相談内容を踏まえ「126,130,131の基本設計を作って」と依頼。Plan ModeでExploreエージェント（BL-086ツール群・facilitator_node・task_planner_node・write_agreementのtask_id検証・round_countの実装を調査）とPlan agent（設計案作成）を実施し、AskUserQuestionで「Facilitatorはツールループ化する」「目標注釈は既存revise_goalを流用」を確認、基本設計案をまとめた。保存直前にユーザーが「その前に、APIエラー時にiterが無条件で巻き戻されるのを直しましょう。これはもったいなすぎる」とBL-122の修正を優先する指示（ExitPlanModeを拒否しての差し込み）。Plan Modeのまま`_query_AI_live`の実コードを確認し、`loop_messages`/`tool_calls_used`/`python_calls_log`/`reasoning_parts_all`の初期化が外側の`for attempt`リトライループ内にあるため、リトライのたびに丸ごと再初期化・iteration=1へ巻き戻っていた根本原因を特定。修正方針（初期化を外側ループの外へ移動、`iteration_start`で同一iterationから再開）を計画し承認を得て実装。BL-122を`done`化。BL-126/130/131の基本設計は`docs/design/back_log/BL-126/BL126_basic_design.md`への保存を保留し、次回あらためて着手する。 |
| 2026-07-29 | ユーザー指示「BL-122付近のP1のバグをつぶしましょう」を受け、BL-122に隣接する未着手P1のBL-121（`facilitation_count>3`によるhalt設定が3回記録されたのに外側ループが停止せず会話が継続していた不一致）を調査。`log/2026-07-29/0751`の`log_no_prompt.md`全17265行を精査し、プロセス起動バナー・外側`while`ループの`🔷[Turn]`バナーがともに1件のみで単一継続プロセスであることを確認、`facilitation_count`のリセット箇所がコード全体に存在しないことも`grep`で確認した上で、run終了時点のcheckpoint（`facilitation_count=2, halt=False`）と観測された3回のhaltが数値的に矛盾することを特定。調査の過程で`detector_node`（`cela_main.py:6972`）が呼び出しのたびに`get_decisions_from_db(...)[1:]`で全決定履歴を丸ごと再取得・再出力していた独立したバグ（BL-132、変数名「this_turn」に反しrun全体を再表示、ログのO(n^2)肥大化とBL-128の同一コメント反復の主因）を発見し、これがBL-121の「同じhalt決定が複数回見える」現象の少なくとも一因と判断。BL-132を実装・`done`化（この呼び出しが作成した`decision`1件のみを出力するよう変更）。あわせてBL-121仮説(b)（`--resume`直後に`state.get("halt")`をチェックせず外側ループへ入る欠落）を確認し、`run_ai_vs_ai_loop`の`--resume`処理直後に既にhalt済みのcheckpointなら即座に停止する防御チェックを追加（`done`）。ただしBL-121の根本原因（3回に見えるhalt発生の正体）はBL-132適用後の次回ドライランでの再確認が必要なため`open`のまま維持。`python -m py_compile`合格、関連クラスタ（BL-093/BL-104/R3スモーク）132件Pass。D-097として記録。 |
| 2026-07-29 | ユーザー依頼で`log/2026-07-29/1708`ドライラン（進行中）をレビューし、「`phase_1_task_1_1_review_V11.md`など永遠と作られていますが収束するのか」との懸念に回答。`task_1_1_review`が11バージョンまで積み上がっているが、Detectorは毎回でっち上げでなく本物の新しい欠陥（シフト計算の符号反転、モンテカルロ誤差1000倍、要件で明示された山間部の対象除外等）を検出しており、直近のReflectionが「本質的な目標成果物への着手ゼロのまま単一タスクで堂々巡り」という的確な理由づけで`stagnant`と正式判定、Facilitatorへ差し戻された直後であることを報告。自然収束ではなく`facilitation_count>3`による強制HALTに向かう可能性が高く、これはBL-126/130/131が未実装であることの実害の再現である旨を伝えた。ユーザー指示「まず設計をドキュメント化して」を受け、前回セッションで保留していたBL-126/BL-130/BL-131の基本設計（Plan mode成果物、Exploreエージェント調査＋Plan agent設計＋AskUserQuestion 2件で確定済みだった内容）を`docs/design/back_log/BL-126/BL126_basic_design.md`として正式保存。1708ログでの再現事実（`whiteboard_drafts`が`(phase_id, task_id)`のみで版管理されtopic列を持たないため、同一task_idに複数の異なる文書が混在しうるという設計上の注意点）を`goal_drafts`テーブル設計への補足として追記。BL-126/130/131のサマリー行・詳細セクションを「基本設計完了、実装は未着手」に更新し相互リンク。コード変更は行っていない。 |
| 2026-07-29 | ユーザーがBL-131（`write_agreement`のtask_id/phase_id実在チェック欠落）について「他に必須化をすべき項目は？decision_whatは？設計書には現状確認だけで実装への言及がない」と質問。コード確認の結果`decision_what`は既にPython側で必須化済み（`_write_agreement_impl`1886-1888行目、Deliverable+UPDATE+edits時のみ免除）と回答した上で、未実装の3点（task_id/phase_id実在チェック、`get_latest_whiteboard`が`(phase_id, task_id)`の組でしか検索せず誤ったphase_idで既存版が「該当なし」と誤判定されバージョンが1から再スタートする問題、UPDATE/SUPERSEDE時の`target_topic`省略が`topic`へ暗黙フォールバックする空振りバグ）を新規発見。ユーザーから「なぜ最初にstate渡しにしなかったのか」と問われ、`TOOL_DISPATCH`がR2実装時にモジュールレベル辞書として導入され`_query_AI_live`をLineageState非依存の汎用エンジンに保つ設計判断の副作用として、以降の機能追加のたびに`_CURRENT_TASK_ID`等のグローバルが1個ずつ生やされ続けてきた経緯（BL-099として既に記録済みの技術的負債）を説明。ユーザーから「task_idだけで引けるようにできない？」と提案があり、`plan_drafts`側に既に存在する`get_latest_plan_draft_by_task_id`（task_id単独検索、phase_id食い違いは警告のみ）という前例を踏襲する設計へ転換。さらにユーザーが「3点をBL126_basic_design.mdの§2に実装設計として追記」「TOOL_DISPATCHをstate受け渡し可能な形へ直す」「phase_idの修正も反映」を指示し、あわせて別AIによる独立レビュー（`docs/design/back_log/BL-126/BL126_review.md`、設計上のバグ2件・抜け5件・気づき7件・確認事項3件への回答を含む）が提示された。これら全てを反映しBL126_basic_design.mdをv2へ全面改訂：§2.5（BL-131実装設計）・§2.6（TOOL_DISPATCHのstate受け渡し設計、`_CURRENT_RUN_ID`/`_CURRENT_TASK_ID`/`_CURRENT_PHASES`の3グローバル廃止方針）を新規追加、facilitator⇄generate_user_utteranceエッジの既存/新規区別・Detector目標変更レビューのmajor時ルーティング等の設計バグ2件を修正、LineageStateフィールドの初期値・優先順位・型不備等の抜け5件を補完、確認事項3件（本質対話上限5回・目標変更レビューは反応的経路にも適用・ラン途中再構成はtask_plan_reviewer通過＋リビジョン上限2回）を確定、Mermaid状態遷移図・BL-096統合案を追加。issue_backlog.mdのBL-126/130/131をv2完了として更新、`check_docs_consistency.py`合格。コード変更は行っていない（設計のみ）。 |
| 2026-07-29 | ユーザーが「ユーザー、ファシリテーター対話など各モード切替時のノードごとのプロンプトはどう書き、どう切り替えるか？」と質問。既存の`call_detector`の`target_role`分岐（`domain_role_instruction`、事前に書いた固定文字列をtarget_role単位で切り替え、BL-104のキャッシュ最適化順序に従い固定指示文グループの直後・毎ターン変わる末尾より前に配置）を一般化する設計を提案し、`call_detector`(review_mode)/`call_facilitator`(essence_dialogue_active)/`generate_user_utterance`(essence_dialogue_active/expert_pending_question)/`call_expert`(モード分岐なし、動的コンテキスト注入のみ)/`call_task_planner`(plan_revision_reason)の5ノードへの適用表と、モードの排他性ルール（同時に複数モードが立たない前提、複数発生しうる場合はelif連鎖にする）を提示。ユーザーが承認しBL126_basic_design.mdへ§13「モード切替とプロンプト設計」として追記、v3へ改訂。続けてユーザーから「TOOL_DISPATCHのstate受け渡しもやりたいですが、プロンプトの整理（BL-115/116）もやりたいです、スコープ広すぎますかね？」と実装スコープに関する相談があった。AIが「TOOL_DISPATCHのstate受け渡し（配線変更・機械的・低リスク）とプロンプト整理（文面変更・判断が絡む・範囲が広い）は同じ実装パスで混ぜると切り分けが難しくなる」と回答し分離を提案、ユーザーが「TOOL_DISPATCHのstate受け渡しのみにします」と決定。続けて「これはBL-131の前に片づけたほうがいいですか？」と問われ、AIが「BL-131のtask_id実在チェックは`state['phases']`を要するため、先にTOOL_DISPATCHを片づけないと`_CURRENT_PHASES`グローバルを一時的に拡張してすぐ剥がす二度手間になる」と回答、ユーザーが「OK、先に進めて」と実装を承認。 |
| 2026-07-30 | ユーザー指示「OK、先に進めて」を受け、TOOL_DISPATCHのstate受け渡し化を実装。`_query_AI_live`/`query_AI`/`_query_and_parse_with_retry`へ`state`パラメータを追加、ツール実行箇所を`handler(args, state)`に変更、TOOL_DISPATCHの全15エントリを`(args, state=None)`の2引数ラムダへ統一。`call_resource_arbiter`/`call_integrator`/`call_task_planner`/`call_reviewer`/`call_goal_essence_analyst`/`call_task_plan_reviewer`（従来stateを受け取っていなかった6関数）に新規`state`パラメータを追加し、呼び出し元ノードから伝播。既存テスト40件がTOOL_DISPATCHの旧1引数呼び出し規約に依存して失敗したため`state=None`デフォルトで後方互換を確保、さらにTOOL_DISPATCH実装詳細に依存する回帰テスト2件（think handlerの同一性チェック、handler呼び出しのソース文字列チェック）を新しい規約に合わせて更新。その後ユーザーから「"/compact"後にBL126-131を実装」と依頼を受け、スコープの大きさを踏まえEnterPlanModeで再検討した上でBL-131（最小・独立、かつTOOL_DISPATCH state化により今まさに前提が整った）から着手する方針とし、`_write_agreement_impl`へのtask_id/phase_id実在チェック（`pending_task_ids`許可リストを`LineageState`へ新規追加）、`get_latest_whiteboard`/`get_latest_plan_draft`のtask_id単独検索化（1708ログで観測された「誤phase_idでバージョンが1から再スタート」事故の修正）、`target_topic`必須化を実装。新規`tests/test_bl131_write_agreement_task_id_validation.py`（9件）を追加し、既存テスト3件をpending_task_ids経由で許可する形に更新。BL-131を`done`化。`python -m py_compile`合格、関連クラスタ166件Pass。D-098・D-099として記録。BL-130・BL-126の実装は次回以降。 |
| 2026-07-30 | BL-131・TOOL_DISPATCH変更のマイルストーン確認として`pytest tests/ -q`をフル実行したところ、狭域クラスタ166件では捕捉されなかった20件が失敗。原因は2系統：(a) `query_AI`をモンキーパッチする既存テスト（`test_bl087_stage2_task_plan_reviewer_node.py`3件、`test_bl087_stage3_4_goal_essence.py`2件、`test_bl089_json_fence_and_failclosed_review.py`5件）のフェイク関数が新規`state`キーワード引数を受け取れず`TypeError`（`fake_query_ai`に`state=None`を追加、および`call_goal_essence_analyst`をモンキーパッチする1箇所のラムダにも追加して修正）。(b) TOOL_DISPATCH実装詳細（ハンドラのidentity）に依存する回帰テスト2件（`test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`・`test_bl092_plan_draft_diff_verification.py`の`test_tool_registered_in_dispatch`系）が、think handlerで先に適用したのと同じ「ラムダ化によりidentity一致が崩れる」問題で失敗（直接呼び出しとdispatch経由呼び出しの結果比較による挙動同値チェックへ更新）。(c) `test_r4_smoke.py`のwrite_agreement関連6件が、stateを渡さない旧来のグローバル経由呼び出し（本ファイル一貫の書き方）でBL-131のtask_id実在チェックに引っかかり失敗（`_CURRENT_PHASES`グローバルが`orchestrator_node`でしか設定されず、本ファイルのフィクスチャでは空のままだったため）。`db_conn`フィクスチャに`_CURRENT_PHASES`（`task_1_1`・`task_1_2`を含む`phase_1`）の設定/リセットを追加して解消。全て機械的な後方互換の抜け漏れであり、BL-131自体のロジック変更は不要と判断。修正後、該当5ファイル84件がPass。フルスイートの残り1件（`test_f26_detection.py::test_detector_no_false_positive_within_cap`、実LLM呼び出しを伴う既知のflakyテスト）は別途確認中。 |
| 2026-07-30 | ユーザー指示「次の実装開始」を受け、BL126_basic_design.md §8の推奨順序に従いBL-130（Expert相談チャネル）を実装。`ASK_USER_QUESTION_TOOL`/`_ask_user_question_tool_impl`（expertのみ許可）を新設し`call_expert`のツールリスト・プロンプトへ反映、`_LAST_ASK_USER_QUESTION`/`get_last_ask_user_question()`を`_LAST_GOAL_REVISION`と同型のブリッジとして追加。`LineageState`に`expert_consultation_mode`/`expert_pending_question`を追加し`expert_node`がセット/リセット。`detector_node`に軽量パス分岐（相談ターンはLLM監査自体をスキップしconstraint_issue="none"）、`route_after_expert_detector`に新分岐（相談ターンはexpert_decision_extractorを経由せずgenerate_user_utteranceへ直行、グラフエッジにも追加）を実装。`generate_user_utterance`に質問提示の固定文面、`generate_user_utterance_node`で回答生成直後にフラグを消費・リセット。新規`tests/test_bl130_ask_user_question.py`（15件）を追加。`python -m py_compile`合格、関連クラスタ256件Pass。BL-130を`done`化、D-100として記録。BL-126（Essence Dialogue等）の実装は次回以降。 |
| 2026-07-30 | ユーザー指示「最後まで進めて」を受け、BL-120（`call_reflection`のJSONパース失敗フォールバックが単発でも即`stagnant`断定していた問題、層2リトライでラップし修正・`done`）、続けてBL126_basic_design.md §8の順序通りBL-126 Stage A（`goal_drafts`テーブル・版管理）/Stage B（Detector `review_mode="goal_change"`）/Stage C（Task Plannerのラン途中再構成・supersede機構）/Stage D（`EssenceProposal`・Facilitatorのツールループ化・Essence Dialogueループ・Reflection迎合監査）を実装。設計書が誤って前提としていた`route_after_facilitator`の既存4分岐（実際は2分岐のみ）という齟齬を発見したが、`run_ai_vs_ai_loop`の外側ループが毎ターン`entry_point`から再入場する構造を確認した上で、単一の条件付きエッジ変換のみで安全に対応（大掛かりな中核ループ改修は不要と判断）。新規テスト29件を含め、フルオフラインスイート512件Pass、`check_docs_consistency.py`合格。D-101〜D-104として記録、`decision_lineage.md`論点85〜87に議論経緯を記録。BL-120・BL-126を`done`化。 |
| 2026-07-30 | 独立して走らせていた`test_f26_detection.py::test_detector_no_false_positive_within_cap`の再実行（背景ジョブ）が完了し、3/3全試行で`major`となり失敗。ユーザー指示「BL起票、修正を進める」を受け調査。テスト出力の`comment`フィールドを確認したところ、モデルの誤判定ではなく`call_detector`第1段（ドメイン妥当性レビュー）が層2リトライ（`_query_and_parse_with_retry`、計3試行）を使い切りJSON解析に失敗、D-005の設計通りフェイルクローズ（major）していたことが判明。2026-07-28の1回目のflaky報告時も同一原因だった可能性が高いが、当時`comment`を確認せず「モデル判定のばらつき」と誤って結論づけていた（BL-133として記録）。フェイルクローズ自体（D-005安全側原則）は変更せず、リトライ失敗のたびに生レスポンス冒頭300字をログ出力するよう`_query_and_parse_with_retry`を変更し、次回再現時に真因（モデルが一切JSONを出力していないのか、ツールループがMAX_TOOL_ITERまで消費されたのか、API側の一時的不調か）を機械的に切り分けられるようにした。`python -m py_compile`合格、`tests/test_bl089_json_fence_and_failclosed_review.py`10件Pass（ロジック変更なしのため既存挙動に影響なし）。BL-133は`open`のまま（診断ログ追加のみ、恒久対応は次回再現時）。 |
| 2026-07-30 | ユーザー指示「次はプロンプトの整理に移りたい」を受け、Plan ModeでBL-114/115/116（プロンプト整理、7月28日に記録のみで`open`のまま残っていた3件）に着手。3体のExploreエージェントで現行コード（BL-104/113/119/126/130/131/TOOL_DISPATCH適用後）を再調査し直した上でPlan agentが実装方針を設計、承認を得て実装。BL-114: `call_orchestrator`のプロンプトを静的先頭・動的末尾・JSON末尾の順に並び替え、矛盾していたコメントも修正。BL-115: `call_decision_extractor`の未使用`prompt_old`（約60行）を削除、共有定数`_BL093_THINK_VALUE_PARAGRAPH`/`_THINK_TRAILER_SENTENCE`と共有関数`_verification_throttle_warning()`を新設し7関数に適用、`call_detector`内の`domain_prompt`/`prompt`間の重複はローカル変数で関数内集約。BL-094同期説明・ツール一覧文は`tests/test_bl094_read_tool_orientation.py`/`test_bl093_think_tool_scratchpad.py`の`inspect.getsource()`ベースの制約と衝突するため共有化を断念し、試行錯誤の経緯をコードコメントに記録。BL-116: `call_task_plan_reviewer`/`call_task_planner`/`call_orchestrator`/`call_decision_extractor`の具体的なバス交通ドメイン数値例を、教訓を保ったまま一般化。`generate_user_utterance`のf-string由来のゴミ引用符混入バグ（`\n"`のリテラル混入、複数箇所）も発見・修正し、再発防止の回帰テスト2件を追加。実装中に`test_bl087_*`/`test_bl089_anti_repetition_instructions.py`/`test_bl094_read_tool_orientation.py`の計11件が、共有ヘルパー化・ドメイン例一般化に伴うリテラル文字列変更で壊れたため、新しい構造に合わせて更新。`python -m py_compile`合格、フルオフラインスイート（`pytest tests/ -q --ignore=tests/test_f26_detection.py`）514件Pass。BL-114/115/116を`done`化、D-105〜D-107として記録。 |
| 2026-07-30 | ユーザー指示「07-30/1050,1236がBL126以降のドライランです、レビューして」を受け、BL-126/130/131実装後初の実LLMドライラン（`log/2026-07-30/1050`→`1236`、同一run_idの再開継続）をレビュー。新規Stage B/C/D（Essence Dialogue・mid-run再構成・goal_change review）およびBL-130（ask_user_question）はいずれも未発火（シナリオがturn_count=1のまま単一task_1_1〜1_2の検証ループに終始したため機会がなかった）。BL-131（task_id実在チェック）は実際に発火し正しく機能（task_id欠落のwrite_agreement呼び出しを拒否、エージェントが自己修正）、BL-116のゴミ引用符修正も1050（修正前・混入あり）と1236（修正後・混入なし）の比較で実際に効いていることを確認。トレースバック・クラッシュは0件。続けてユーザーが「遠隔監視オペレーターの法的必要人数試算が24時間365日前提だが、ゴール文の運行時間は8-20時のみでは」と指摘。ログを精査した結果、Expertが「最低2名常駐」というゴール文の要件を無根拠に「24時間365日」体制へ拡大解釈し、`remote_operator_min_count_legal`（10-11名）・`remote_operator_cost_legal`（年4,125〜6,188万円）を`confidence="confirmed"`として確定、これが年間維持費上限超過という`major`判定の根拠になっていたことを確認。Detector自身がこの疑義（「運行時間は8-20時の12hのみ、シフト設計次第で要員半減の可能性」）をseverity="major"・status="escalated"のissueとして実際に検知していたが、`resolved_by`/`resolved_at`が空のまま未解決で、User AIがtask_1_1を承認しtask_1_2へ進行させてしまっていたことが判明。F-2.6/BL-033が防ごうとしている「根拠のない前提の確定値化」が監査で検知されつつ是正フローに乗らずすり抜けかけた実例、かつBL-125が指摘した「issue未解決状態がtask進行をブロックしない」ギャップの再現として、BL-134を新規起票（`open`、記録のみ）。コード変更は行っていない。 |
| 2026-07-30 | `log/2026-07-30/1236`のログが伸びた（turn 1/round_count 7→turn 3/round_count 10）ため再レビュー。BL-134の24時間365日前提は、電話予約オペレーターのシフトのみ8-20時の12h窓へ是正されたが、遠隔監視オペレーターのシフトは是正されずconfirmed値のまま次工程へ引き継がれており、該当issueの`resolved_by`/`resolved_at`も引き続き空だったことを確認。BL-126 Stage B（`escalate_premise_concern`によるゴール前提エスカレーション）がturn 3で初めて発火（2回）、Facilitatorが「BL-126」を明示的に引用しゴールの数値制約と本質の矛盾を提起したが、いずれも`resolve_premise_concern`/`revise_goal`による解決前にログが終了。Stage C/D・BL-130（`ask_user_question`）は引き続き未発火。Python REPL実行時エラー数件・API無応答1件はいずれもDetector検知・自己修正済みで実害なし。続けてユーザー依頼「新規ツールのプロンプトでの説明やオリエンテーションは適切に書かれているか」を受け、BL-086/BL-130関連のツール定義・オリエンテーション文面をコードで確認。全体として誤用予防・モード排他制御が明快に書けていることを確認した一方、`ASK_USER_QUESTION_TOOL`の`required`パラメータ`blocking_reason`が`generate_user_utterance`のUser AI向け相談応答文面に埋め込まれておらず、User AIがExpertの申告したブロッキング理由を見られないままask_user_questionの質問文にのみ回答する構造上の抜け漏れを発見。BL-135として新規起票（`open`、実害未確認・優先度低、記録のみ）。コード変更は行っていない。 |
| 2026-07-30 | ユーザー質問「なぜissueが活用されなくなった？たまたま？」を受け、`cela.db`の実データとコードを突き合わせて根本原因を特定。issue_logのRESOLVE指示に強制力がない（BL-086の前提エスカレーションと非対称）、status='open'（minor）行が可視化されない、という2点が原因と判明。ユーザーから「minorも表示する」「escalated issue_logにもBL-086同様の強制解決文言・毎ターン表示を追加する」「ただしフェーズをまたぐ・先送りされるissueもあるためスケジュール調整も必要」との指示を受け、Plan Modeで3体のExploreエージェントによりタスク/フェーズ遷移ゲート・issue_log全体像・facilitator/discussion_status連携を調査した上で実装方針を設計、承認を得て実装（BL-136として新規起票・即`done`化、あわせてBL-125も`done`化）。(A) `_get_open_issues`/`_build_open_issue_pin_text`でminor行を可視化。(B) `write_issue`に`action_type="DEFER"`を追加（BL-082の`_append_deferred_note_to_plan`を再利用し、対象taskの計画文書へ申し送り、issue_logに`defer_to_task_id`列を新設）。(C) `_get_forced_escalated_issues_text`でBL-086同型の強制解決文言を追加（DEFER済みは対象外）。(D) BL-125として`_resolve_task_transition`にゲートを追加し、離脱task に紐づく未解決・未先送りのsevere issueがあれば遷移をブロック、BL-134の実インシデントをテストで再現し防止できることを確認。実装途中でDEFER拡張と同名の「BL-135」を誤って使っていたことに気づき、既存のBL-135（ask_user_question blocking_reason）との重複を避けるためBL-136へ全面リネームした。新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`（28件）、既存の`tests/test_r3_smoke.py`のBL-039テスト2件がDB接続前提の変更により失敗したため`db_conn`フィクスチャを使うよう修正。`python -m py_compile`合格、フルオフラインスイート542件Pass。BL-134の詳細セクションも、上記の根本原因訂正（「Detectorがmajor判定」ではなくraised_by='detector_auto'の再発機械的昇格とraised_by='user'の直接major指定の2種混在だった）と対応状況を反映して更新した。 |
| 2026-07-30 | ユーザーから実ドライラン実行中のクラッシュ報告（`AttributeError: 'str' object has no attribute 'get'`、`_apply_text_edits`内`e.get("old_text", "")`、`run_ai_vs_ai_loop`全体が停止）。User AIの`revise_goal`ツール呼び出しで`edits`配列に辞書ではなく生文字列が渡されたことが直接原因と判明。`_apply_text_edits`は`write_agreement`のUPDATE経路とも共有される関数のため、同種のリスクがExpert側にも波及しうると判断。BL-137として新規起票・即`done`化。ループ先頭に`isinstance(e, dict)`チェックを追加し、非dict要素があれば未捕捉例外の代わりに具体的なエラー文字列を返しツールループでの自己修正を可能にした。回帰テスト2件（`tests/test_r4_smoke.py`）を追加。`python -m py_compile`合格、フルオフラインスイート544件Pass。 |
| 2026-07-31 | Sakana AIの仕組み・CELAとの設計思想の共通点についての雑談から、ユーザーが「CELAに自らのLangGraph構造を継続改良させ、改良されたCELAが次世代のCELAをさらに改良する」再帰的自己改変構想を提起。AIが技術的実現可能性を認めつつ「評価基準自体のドリフト」という本質的リスクを指摘したところ、ユーザーが「これは仮定ではなく、AIが捏造・確定値化した数字が後続議論に連鎖的影響（バタフライ効果）を与えている今まさに起きていることだ」と実例（BL-134等）を引いて応答。「もっとループの外側に監査層が必要」という原則を、思いつきレベルの構想ながら将来の設計制約として記録する価値ありと判断し、BL-138として新規起票（`open`、記録のみ、実装は未着手）。decision_lineage.md論点89に議論経緯を記録。コード変更は行っていない。 |
| 2026-07-31 | ユーザー指示「他に潰すBLは？」を受けBL-127（`write_agreement`のUPDATEがDB上成功してもホワイトボード本体に反映されないケース）を提案、ユーザー承認により着手。`_commit_agreement_from_tool`のUPDATE分岐に存在する「保護」ブランチ（entry_type="Deliverable"かつedits未指定・200字以下の短文の場合、既存の完全版を誤って上書きしないためホワイトボードへは触れない仕様）が、発動してもLLM呼び出し元へは`print()`のみで一切伝わらず、実際に反映された正常なUPDATEと同一の`{"success": True}`を返していたことが原因と判明。皮肉にも、BL-127の実インシデントでExpertが送った「修正が正常に適用されたことを確認しました」という短い自己申告コメント自体がこの保護仕様の対象（200字以下）に該当し、何も変更されない結果に終わっていた。`_commit_agreement_from_tool`の戻り値を`tuple[str\|None, str\|None]`（error, protected_warning）へ拡張し、保護発動時は`_write_agreement_impl`のツール応答へ`"warning"`フィールドとして明示するよう修正。既存の直接呼び出しテスト3ファイル（BL-073/080/084、計8箇所）をタプル戻り値のアンパックに追随させ、新規テスト`tests/test_bl127_whiteboard_update_protected_warning.py`（6件）を追加。`python -m py_compile`合格、フルオフラインスイート550件Pass。BL-127を`done`化。 |
| 2026-07-31 | ユーザー指示「次、BL-134」を受け、残っていた候補(a)(c)に着手。候補(c)（Detectorのconstraint_issue判定基準の見直し）は、実際に`call_detector`のドメイン妥当性レビュー基準を確認したところ「情報が不足していて確認できないことをmajorの根拠にしてはいけない」という制約が意図的に設けられており、これはBL-012/BL-133が守る「モデルの誤検知を過度に許容しない」設計と表裏一体（非退行テスト`test_detector_no_false_positive_within_cap`で保護済み）と判明したため、変更不要と判断し見送った（24h/365d問題が情報不足型の疑義としてobservationsに回ったのは設計通りで、真の問題は同日中にBL-125/BL-136で既に解消済み）。候補(a)は、D-094の「マインドセット／目的別行動オプション／罠」3層モデルに沿った罠注記として`call_expert`（ドメイン妥当性チェック直後）・`generate_user_utterance`（ドメインレビューチェックリスト）の双方に追加：部分的な要件（「最低N名常駐」等）を時間帯・範囲等の条件を無視して拡大解釈する際は根拠をゴール文中に明示し、根拠が無ければconfidence="provisional"として扱いwrite_issueで記録するよう指示。新規テスト`tests/test_bl134_unsupported_generalization_guard.py`（3件、候補(c)見送りの非退行確認含む）追加。`python -m py_compile`合格、フルオフラインスイート553件Pass。BL-134を`done`化、D-110として記録。 |
| 2026-07-31 | ユーザー指示「31/0908のログレビュー」を受け、BL-125/136/137/127/134実装後初の実ドライラン（`log/2026-07-31/0908`）をレビュー用にAgentへ委託。issue_logのRESOLVE/DEFERはモデル自身が`write_issue`を明示的に呼んだ形跡が依然ゼロ（BL-096の自動起票のみで26件累積）と報告を受けたが、それ以上に`checkpoint.json`の`current_task_id`が最後まで`"task_1_2"`のままで、対話ログでは同日15:04:19時点で既にtask_2_1着手指示が明示され数百ターン・`whiteboards/`のphase_2_task_2_1版まで進行していたという重大な乖離をAgentが発見。ユーザー指示「これはすぐ治しましょう」を受け直接調査し、`_resolve_task_transition`の遷移完了・拒否いずれの`print`ログも当該run全体で一件も出現していないことを確認（BL-125のゲートが悪さをしたのではなく、その前段の遷移トリガー自体が`call_decision_extractor`の1回のLLM呼び出しが返す`advances_to_task_id`のみに依存しており、Userの発言が明示的にtask_2_1着手を指示し`extracted_events`自体にはtask_2_1向けのDirectiveが正しく抽出されていたにもかかわらず、トップレベルの`advances_to_task_id`だけがnullで返っていたという抽出漏れが真因と特定）。BL-139として新規起票・即`done`化。`decision_extractor_node`に、抽出済みextracted_eventsの中に現在タスクと異なる有効なtask_idを持つDirective（`status="Deferred"`の明示的先送りは除外）があれば`transition`の代替シグナルとして採用するフォールバックを追加（BL-096と同型の安全網、対象はUser側抽出のみ）。新規テスト`tests/test_bl139_transition_fallback_from_directive.py`（4件、実インシデント再現含む）追加。`python -m py_compile`合格、フルオフラインスイート557件Pass。 |
| 2026-07-31 | ユーザー指示「1129のログレビュー」を受け、BL-139実装後初のドライラン（`log/2026-07-31/1129`）をレビュー。BL-139のフォールバックが実際に発火（`current_task_id`をtask_1_1へ正しく補完）、BL-125のゲートも初めて実際に発火（未解決severe issueによりtask_1_2への遷移をブロック、対話上はExpertが次タスクへ進む発言をしていたにもかかわらず`current_task_id`が正しくtask_1_1に保持されたことを確認）、Detectorが`write_issue`を能動的に5件CREATEするなど、修正の効果を複数確認。ただしログがDetector監査思考の途中で唐突に終了しておりプロセス中断の可能性を報告した。続けてユーザーから「issueが使われない件、もしかしてthinkの方に取られている？thinkに書けば永遠に残ると勘違いしている？」との仮説提起があり、`THINK_TOOL`の`issues`パラメータ定義を確認したところ、まさにその名前のフィールドが存在し「nothing is summarized away or aged out」という永続性を示唆する説明文もあったが、実装（`_think_handler`）はDBに一切書き込まずノード呼び出しごとに`_reset_think_scratchpad()`で消去される一時変数に過ぎないことが判明。実際に1129ログでDetectorが`think(issues=[...])`へ書いた懸念と、後に`write_issue`で実際に起票した懸念がほぼ同一内容だったことも確認し、名前の類似が誤解を誘発している可能性が高いと判断。ユーザー指示「scratch_concernsが一時的が伝わっていいです。実装してください」を受け、`THINK_TOOL`の`issues`パラメータを`scratch_concerns`へ改名しdescriptionへ`write_issue`との違いを明記（BL-140として新規起票・即`done`化）。対応するモジュール変数・返り値キーも同期改名。新規テスト1件追加、既存テスト2件をキー名変更に追随。`python -m py_compile`合格、フルオフラインスイート558件Pass。 |
| 2026-07-31 | ユーザーから2点の追加指摘。(1)「userのプロンプトにはissueを確認しろというプロンプトはありますよね？」に対し、`generate_user_utterance`に既存の`read_issues`/`write_issue(RESOLVE)`指示（BL-096導入時から存在）を確認し提示。(2)「detectorとエキスパートの差戻しループは見せずにuser->エキスパートの履歴だけに整理できませんか？差戻ループが続くと最初に言ったユーザー発言が見れなくなる恐れがあり…」との指摘を受け調査。Detectorがmajor判定で差し戻すと`route_after_expert_detector`がUserの発言を挟まず`expert_node`へ直接ループバックし（最大3回）、`expert_node`が差し戻しのたびに新規`assistant`メッセージを無条件で`chat_history`へ追記していたため、`chat_history_window`（既定4）が同一タスクの差し戻し往復だけで埋まりUserの直近の指示が押し出される実害を確認。BL-140の`_issue_carryover_prefix`変更で示した通り、まずJSONスキーマだけでなくプロンプト本文で違いを明示する重要性を踏まえ、これも根本原因（`expert_node`の無条件追記）を直す方針とした。BL-141として新規起票・即`done`化：`expert_node`末尾で、直前のchat_historyエントリが既に`assistant`（＝同一ターン内の再提出）であれば新規追記せず上書きするよう変更。新規テスト`tests/test_bl141_expert_retry_chat_history_collapse.py`（3件）追加。`python -m py_compile`合格、フルオフラインスイート563件Pass。 |
| 2026-07-31 | ユーザーから「何回か突然ログが途切れているのも、間違ってノートパソコンを休止状態にしたりしてしまったため」との説明があり、BL-129（`log/2026-07-28/1233`・`1420`等でログがHALT/完了メッセージなしに唐突に途切れる、原因未切り分けのまま`open`だった問題）の主因が、コード側のバグではなく実行環境（ノートPCの意図しない休止状態移行）だったと判明。BL-129の優先度をP2→P3へ引き下げ、経緯欄へ追記。コード変更は行っていない。 |
| 2026-08-02 | `log/2026-08-02/0832`レビュー、続けてOrchestrator（`call_orchestrator`）関連バグの調査（`write_agreement`/`read_deliverable_file`がBL-125のタスク遷移ゲートを内容レベルで迂回できる、Orchestratorが`current_task_id`/計画/issue状況を一切見れずツールも持たない、の2系統3件。BL-146〜148として別途起票予定、Plan Modeで設計検討中）。ユーザーから「majorとなったissue・後続タスクへの申し送りは、Detector/Reflectorの正当性監査後、タスクプランナー経由で明示的にタスク化した方がissue消化がスムーズになるのでは」との提案、および「タスクの修正が今後ぽろぽろ出てくるはずなので、1タスク追加・削除・修正の軽量APIが欲しい」との追加要望を受け、BL-145として新規起票（`open`、設計相談のみ）。調査の結果、`write_issue(DEFER)`は`plan_drafts`（文書ホワイトボード）への申し送りテキスト追記に留まり、コード側のゲートが実際に参照する`state["phases"]`（構造データ）へissueを正式タスクとして組み込む経路も、`state["phases"]`自体への差分編集API（1タスクだけ追加・削除・修正する軽量API）も存在しないことを確認。BL-144の滞留検知（`escalated_issue_first_seen_round`）とtask_plannerの既存再計画トリガー（`plan_revision_reason`）を再利用する方針を検討候補として記録。 |
| 2026-08-02 | ユーザー指示「FixA-Cを着手」を受け、BL-146（`write_agreement`のcurrent_task_idゲート、SUPERSEDE除く）・BL-147（`read_deliverable_file`のtask_id実在チェック）・BL-148（Orchestratorのツールループ化、読み取り専用4ツール付与）を実装。新規テスト16件追加、既存`tests/test_r3_smoke.py`のBL-040テストの回帰を修正。D-116（未記入だったBL-144分）・D-117・D-118・D-119として記録。`python -m py_compile`合格、フルオフラインスイート596件Pass、`check_docs_consistency.py`合格。続けて`log/2026-08-02/2222`ドライランをレビューし、BL-148がOrchestratorの全呼び出しで`current_task_id`ブロックを正しく注入し専門家選定の矛盾が再発しないことを確認。BL-146/147は他タスクへの誤操作の試み自体が発生せず未検証（バグの不在は確認、ゲートの実効性は未実証）。ランはOpenRouter無料枠の日次上限到達＋Ctrl+Cによる手動一時停止で終了しており、クラッシュではないことを確認。 |
| 2026-08-03 | ユーザー指示「back_logフォルダの中の整理がおざなりだったので整理をします。BL-126以降のプランや調査結果をback_logフォルダに保存。この手順がAGENTS.mdにない場合、書いておいてください」を受け、既存の`docs/design/back_log/BL-xxx/`フォルダ規約（BL-096/103/104/114-117/126、実装時にPlan mode/Explore・Planエージェントを使った案件のみ個別フォルダを持つ）をAGENTS.mdの§7へ明文化（フェーズレベルの`cela_phaseN_impl_Plan.md`規約とは別に、BL単位のPlan/調査は`back_log/BL-xxx/`へ保存する旨を追記）。あわせて、BL-126以降でPlan mode/Explore・Planエージェントによる設計・調査を経ながらback_logフォルダに未保存だった2件を特定し保存：(1) BL-125/BL-136（2026-07-30実装、当時のPlanが未保存のままだったが、本セッション冒頭で偶然読み取っていた内容から復元）→`BL-136/BL136_basic_design.md`として保存、issue_backlog.mdのBL-125/BL-136両方から相互リンク。(2) BL-146/BL-147/BL-148（本日実装、Plan本体＋Planエージェントの詳細設計レポートを統合）→`BL-146/BL146_147_148_basic_design.md`として保存、issue_backlog.mdの3件から相互リンク。BL-131は既に`BL-126/BL126_basic_design.md`§2.5・§2.6でカバー済みと確認（追加保存不要）。BL-114〜117は元々個別フォルダ済み。BL-127/130/134/137/139〜145はPlan mode/Explore・Planエージェントを使わない直接修正だったため、既存規約上フォルダ化の対象外と判断（decision_lineage.mdの各論点エントリで議論経緯は既にカバー済み）。`check_docs_consistency.py`合格（アンカーslugify不一致を数箇所発見・修正）。コード変更は行っていない。 |
| 2026-08-03 | ユーザーから、別AI（Cline/deepseek-v4-flash経由）によるコードベース全体レビュー2件（`BL-149_150_codebase_bugcheck_2026-08-03.md`・`CELA_architecture_review_2026-08-03.md`、既にback_logフォルダへ保存済み・BL-149/BL-150もCline側で先行起票済み）を読んで意見を求められた。BL-123（`call_detector`へのescalation pin未注入）の指摘をコードで直接検証し正確と確認。GLM提案の`quality_gate_node`は`_resolve_task_transition`の実際の挙動（phase境界を跨ぐ遷移も同一ゲートで判定する設計）を確認した結果、issue解決チェック部分はBL-125と重複しており新規ノードは過剰と判断、その旨をユーザーへ回答した。ユーザーが即効性項目セット（BL-123・BL-135）の実装を選択。Plan Modeで1体のExploreエージェントにより`call_detector`の2パス構成・`ask_user_question`の伝播経路を調査した上でプラン化・承認。BL-123: `call_detector`の2パス構成のうちPass 1（ドメイン妥当性レビュー）にのみ`_build_escalation_pin_text`を注入（Pass 2は算術検算専念のため対象外、Pass 1の指摘は既存の`domain_findings_block`経由でPass 2へ伝播する設計のため）。BL-135: `LineageState`へ`expert_blocking_reason`を追加し、`expert_node`→`generate_user_utterance`の消費・リセット経路を`expert_pending_question`と同じタイミングで配線、相談応答モードのプロンプトへ理由を追記。新規テスト`tests/test_bl123_detector_escalation_pin.py`（3件）追加、`tests/test_bl130_ask_user_question.py`を拡張（5件変更）。D-120（BL-123）・D-121（BL-135）として記録。`python -m py_compile`合格、フルオフラインスイート600件Pass、`check_docs_consistency.py`合格。 |
| 2026-08-03 | ユーザー指示「08-03/1110のログをレビュー」を受け、BL-086の`revise_goal`が初めて実発火したものの、`generate_user_utterance`のプロンプト表示専用の絵文字装飾（「👉」）がedits[0].old_textに紛れ込み9回以上連続で自己修復不能な失敗を繰り返していることを発見・報告。ユーザー指示「2の修正案で修正、さらに他で同じような装飾字の罠がないか調査、後にドキュメント整備」を受け、BL-151として起票・即実装。`_apply_text_edits`へ`content_label`パラメータを追加し、不一致時のエラーへ実際の格納内容の先頭400字スニペットを含めるようにした（`revise_goal`からは「現在のゴール文」ラベルを指定）。あわせて`state['goal']`/`user_goal`の全埋め込み箇所（`call_orchestrator`・`call_expert`・`call_reflection`）とホワイトボード/Decision型agreements一覧の表示箇所を調査し、いずれも現状は機能的な罠になっていないことを確認（記録のみ、追加修正なし）。新規テスト`tests/test_bl151_apply_text_edits_error_snippet.py`（8件）追加。D-122として記録。`python -m py_compile`合格。 |
| 2026-08-03 | ユーザー指示「一時停止後1347でドライラン開始、ログをレビュー」を受け、BL-151修正を反映した再開ラン（`log/2026-08-03/1347`）をレビュー。`verify_whiteboard_excerpt`（BL-079）の失敗率を実測したところ、わずか2ターンで96回中79回（82%）が不一致と判明。原因を追ったところ、Expertが正規のSUPERSEDE経路（BL-146のcurrent_task_idゲート対象外）でtask_1_3の成果物を書き込んだが`state["current_task_id"]`はBL-125のゲートによりtask_1_1のままだったため、`call_detector`の`whiteboard_block`構築・`_verify_whiteboard_excerpt_handler`・`detector_node`の注釈挿入呼び出しの3箇所すべてが、Detectorが実際に監査すべきtask_1_3ではなく無条件にcurrent_task_id（task_1_1）のホワイトボードを対象にしていることが判明。`"案A"`という2文字の引用すら19回連続不一致となりMAX_TOOL_ITER=20を消費、たまたま両タスクに共通する「ピーク需要」が偶然一致してtarget_excerptに採用され、major判定の注釈挿入まで進んでいた（task_1_3固有の批判がtask_1_1のホワイトボードへ誤って埋め込まれた可能性が高い、無関係文書の汚染）。ユーザーがドライランを一時停止し、BL-152として起票（`open`、記録のみ・実装未着手）。修正の手掛かりとして`state["expert_last_whiteboard_edit"]`（既存だが未参照）を特定。コード変更は行っていない。 |
| 2026-08-03 | ユーザー指摘によりBL-153を新規起票：Facilitatorが`write_agreement`で`entry_type="Deliverable"`のタスク成果物（task_1_3の3案比較全文）を書き込んでいたことを確認。`_check_write_permission`が`status`のみ制限し`entry_type`を制限していないことが原因。ユーザーの整理「意思決定を残す趣旨だったが成果物直接の書き込みは想定外、指摘はホワイトボードへ書く方が良いかもしれない」を反映し`open`（記録のみ）で起票。続けてBL-145（issue→タスク明示化）の設計に着手。Plan ModeでExplore 1体（task_planner再構成機構・state["phases"]スキーマ・issue_log/BL-144滞留追跡の調査）とPlan 1体（実装計画立案）を実行。ユーザーとの設計協議の結果、当初案の「issueを`resolved`に直接する」を「新ステータス`planned`（計画済み）を導入し、`resolved`は本当に解決したときのみuser roleが明示的に行う」へ修正（ユーザー指摘：「resolvedとするのはちょっと語弊が生まれる可能性がある」「延期も可能とする」「無理やり解決しようとして議論のデッドロック化も避けたい」）。また既にDEFER済みのstale issueは対象外、write_agreement監査行は追加しない、再構成回数上限は設けない、の3点もユーザー確認済み。プラン承認を得て実装着手。実装完了：`LineageState`へ`plan_revision_issue_ids`追加、`reflection_node`のissue formalizationトリガー、`task_planner_node`の新規`_mark_issue_planned`ヘルパー（'planned'状態への決定論的遷移、'resolved'にはしない）、`facilitator_node`の衝突防御ガード、`generate_user_utterance`への非強制`planned`issue可視化ブロックを実装。基本設計を`docs/design/back_log/BL-145/BL145_basic_design.md`として保存。新規テスト`tests/test_bl145_issue_driven_plan_formalization.py`（16件）追加、既存BL-096/086/126 Stage C・D/136/144/146-148関連テスト（132件）は無修正でPass。`python -m py_compile`合格、フルオフラインスイート623件Pass。BL-145を`done`化。 |
| 2026-08-03 | ユーザー質問「issueって書いたタスクIDと解決すべきタスクID両方ありましたっけ？」「detectorがタスク遷移をブロックするときはtask_id、last_seen_task_id、defer_to_task_idのどれと現在のタスクIDを比較している？」を受け調査し、issue_logの3列（起票場所task_id/last_seen_task_id、解決先defer_to_task_id）とBL-125のブロック判定が`last_seen_task_id`基準であることを回答。続けてユーザーが「先送りはすべてissueにまとめたほうがよい？」と相談し、コードベースに3つの並行した先送り追跡機構（issue_log・agreements Directive/Deferred・plan_drafts）が互いを認識していないことが判明したため、Expertへ`write_issue`ツールを新規付与するのではなく`decision_extractor_node`がissue_log側へも自動橋渡しする方針で合意し、BL-154として起票・実装。Plan ModeでPlan agent1体（コード確認込みの実装計画）を実行。新規内部ロール`decision_extractor_auto`（CREATE専用）を追加し、`_write_issue_impl`のCREATE分岐を拡張してdefer_to_task_idを作成時点で設定可能に、`decision_extractor_node`のDirective/Deferred処理へissue_log橋渡しを追加、`_build_open_issue_pin_text`へdefer_to_task_id表示を追加。BL-125/144/145は無変更で対応済みと確認。新規テスト`tests/test_bl154_decision_extractor_issue_log_bridge.py`（8件）追加。`python -m py_compile`合格、フルオフラインスイート630件Pass（1件failedは本セッション開始前からの未コミット`MAX_TOOL_ITER`変更によるもので本BLと無関係、AGENTS.md §7の定数変更管理対象のためユーザーへ別途確認予定）。BL-154を`done`化。 |
| 2026-08-03 | フルオフラインスイートの唯一の失敗（`test_max_tool_iter_raised_to_20`）についてユーザーへ確認したところ、「task_plan_reviewerによって差し戻された時、task_plannerが差戻しタスクの内容を1つずつ把握し直す過程でツール使用上限に引っかかる事態がログから観測されたため」20→30へ変更したとの理由提示があった。BL-093（15→20、thinkツール単独呼び出しの許容）と同種の正当な引き上げと確認し、BL-155として起票・即`done`化。`cela_main.py`の値は無変更（既に30）、変更履歴コメントへ理由を追記のみ。テストを`test_max_tool_iter_raised_to_30`へ改名し期待値・docstringを更新。D-125として記録。`python -m py_compile`合格、対象テストファイル45件Pass。 |
| 2026-08-03 | ユーザーがドライラン中のnemotron-3-ultra-550b-a55b:free経由のResourceExhaustedエラーを見て「APIエラー時には直前の思考は温存されるんでしたっけ？」と質問。調査の結果、BL-122によりloop_messages/reasoning_parts_all/iteration_startはリトライを跨いで温存されるが、エラー発生時点のiteration自体の途中経過は破棄され同じiteration番号でAPI呼び出しのみやり直されると回答。あわせて、リトライ時のprint文言「ツールループを最初からやり直します」がBL-122以前（当時は実際にiter=1へ巻き戻っていた）の挙動のまま実装と食い違っていることを発見し報告。ユーザー指示「さくっと直してください」を受け、BL-156として起票・即`done`化：print文言を「このiterationのAPI呼び出しをやり直します」へ修正、隣接コメントも更新。ロジック変更なし、対応テストなし。D-126として記録。`python -m py_compile`合格。 |
