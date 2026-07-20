# 実装 Backlog — FEATURE_NAME

**実装タスク・バグ・未確定の実装事項**（BL-xxx）を管理する。要件定義の正ではない。

| 種別 | 正しい参照先 |
|------|-------------|
| 要件・背景・完了条件 | [要件定義書_v35.md](要件定義書_v35.md) |
| Phase 詳細設計 | [phase0/](phase0/) [phase1/](phase1/) |
| 意思決定（なぜ） | [decision_log.md](decision_log.md) |
| 索引 | [README.md](README.md) |

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

---

## Backlog 一覧

### BL-001: Agreement TypedDictの`content`/`rationale`リネーム

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | R1完了 |
| 関連 | [cela_phase1_impl_Plan.md §2.3, §9](phase1/cela_phase1_impl_Plan.md)、[decision_log.md D-003](decision_log.md) |

**内容:**

R1では「壊さない」優先で、既存の`Agreement` TypedDict（`content`/`rationale`キー）をそのまま維持し、`db_append_agreement`内でSQLite列名（`decision_what`/`reason_why`）へマッピングするラッパー方式を採用した（`get_agreements_from_db`も逆方向にエイリアスを付与）。この二重変換は将来のツール化（R3の`write_agreement_tool`）でスキーマ不一致の温床になりうる。

**2026-07-19完了**: `Agreement` TypedDictのキーを`decision_what`/`reason_why`に統一し、`db_append_agreement`/`get_agreements_from_db`のcontent/rationaleエイリアス変換コードを除去した。呼び出し側（`_build_agreements_context`、`call_reflection`、`decision_extractor_node`のUPDATE/CREATE両分岐、`integrator_node`、`reviewer_node`）を全箇所`decision_what`/`reason_why`参照に追従。ダミーデータによるDB往復スモークテストでcontent/rationaleキーが復元されないことを確認済み（実LLM呼び出しなし）。

**2026-07-19追記（実LLM本番実行で検出した移行漏れ）**: ユーザーが実際に`cela_main.py`を実行したところ、`decision_extractor_node`内のターミナル表示用print文（[cela_main.py:2363](../../cela_main.py)、`agreement['rationale']`）がリネーム対象から漏れており、`KeyError: 'rationale'`で本番実行がクラッシュした。この行は`Agreement`辞書の構築（`decision_what`/`reason_why`、L2340-2341）とは別に存在するデバッグ出力で、DB往復のみを見るオフラインスモークテスト（T-6）ではこの`print`文自体を経由しないため検出できなかった。`agreement['reason_why']`に修正し、`python -m py_compile`で構文確認済み。他に`agreement[...]`/`a[...]`形式で`content`/`rationale`旧キーを参照している箇所がないことをgrepで確認済み（該当なし）。**教訓**: フェイククライアントによるオフラインテストは`_query_AI_live`の分岐網羅には有効だが、グラフノード内の表示・整形ロジックまでは通らないため、実LLM実行によるE2Eドライランでしか拾えない不具合がある。

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
| 関連 | [cela_phase1_design_v7.md §3.4, §5, §5.1](phase1/cela_phase1_design_v7.md)、[traceability.md T-5](traceability.md)、[decision_log.md D-002](decision_log.md) |

**内容:**

今回のR1実装セッションでは、`get_db_connection`/`init_db`/`db_append_*`/`get_*_from_db`/`_build_*_context_from_db`/`build_graph()`のダミーデータによるスモークテストと`python -m py_compile`による構文検証のみを実施した。設計書§5の評価メトリクスA（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ）は、実際のLLM API呼び出しを伴う`run_ai_vs_ai_loop`本体のE2E実行（過疎地域バスシナリオ）が必要であり、未実施。

**2026-07-18追記**: `phase1/phase1_dryrun.md`のStep 1〜4を実施し、list版ベースラインとSQLite版の**構造的一致**（agreements/decisions件数、status分布、topic登録順序）を実データで確認した（[traceability.md T-5](traceability.md)、Pass）。これはBL-003の完了条件を満たすものであり、BL-002が要求する指標A（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ、最低5試行）の**実測比較そのものはまだ行っていない**。

**2026-07-18追記2（[D-002](decision_log.md)）**: 上記ドライランの実ログで、`numerical_allocator`が提示する数値提案（トリップ時間・処理能力・予算試算等）がdetectorに何度も数値矛盾（major）で差し戻される事態が繰り返し観測された。これはLLMの暗算（機械的検算なし）が原因であり、設計書付録A「暗算は原理的に信頼できない」の実例そのもの。F-2.6検算ゲート（Python REPL、R2で実装予定）が無い現状で指標A・B・Cを測定しても、「検算ゲート欠如による差し戻し」と「R1永続化基盤自体の効果」が混在し、R1固有の効果を分離評価できない。したがって**指標A・B・Cの実測比較は、R2実装後まで意味を持たないと判断し、依存をR2に変更した**。R1スコープの検証自体は構造的一致（BL-003, T-5）で完了とみなす。

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
| 関連 | [cela_phase1_impl_Plan.md §7](phase1/cela_phase1_impl_Plan.md)、[traceability.md T-5](traceability.md) |

**内容:**

`query_AI`のREPLAY_MODE（record/replay/off）・call_seqキー機構・キャッシュミス時の例外送出は、ダミークライアントによるスモークテストのみ実施済み。実際のLLM応答を使い、list版ベースラインの実行結果と、SQLite版をreplay実行した結果を比較する回帰確認（impl_Plan §7.2の合格基準1「構造的一致」・2「Hydrate再現性」）は未実施。

**2026-07-18完了**: list版ベースライン（コミット`5ef0382`にRecord/Replayスタブを移植）をRecordモードで実行（過疎地域バスシナリオ、Turn 1〜2完了直後に[D-001](decision_log.md)準拠で打ち切り）、記録した45件のフィクスチャをSQLite版（コミット`2133989`）でReplay実行。合格基準1「構造的一致」（agreements 15=15件、decisions 47=47件、status分布・topic登録順序一致）を確認。Replayはlist版の停止点と完全に一致するタイミングで想定通りのキャッシュミス例外を出して停止した。合格基準2「Hydrate再現性」・合格基準3「再起動後保持」は本試験の対象外（詳細は[traceability.md T-5](traceability.md)）。

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
| 関連 | [cela_phase1_design_v7.md §6](phase1/cela_phase1_design_v7.md) |

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
| 関連 | [cela_phase1_design_v7.md §3.1](phase1/cela_phase1_design_v7.md)（グラフトポロジは維持、R1では触っていない既存プロトタイプ由来の挙動） |

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

**2026-07-19追記（影響範囲の再評価：安全網が事実上無効化されていたことが判明）**: 表示上のずれだけでなく、より深刻な副作用が実ドライラン（`log/2026-07-19/2056`）で確認された。`route_after_expert_decision`の`state["turn_count"] % state["reflection_interval"] == 0`判定は、`turn_count`が凍結されている間は`reflection`（延いてはその先の`facilitator`）に一度も到達できない。今回のドライランでは同一タスク（task_1_2）へのDetector差し戻しが3回連続発生したが、`turn_count`が1のまま（`reflection_interval`デフォルト3の倍数にならない）だったため、`reflection`は一度も発火せず、`facilitator`も出現しなかった。つまり本Issueは「表示のずれ」ではなく「周期的な議論健全性チェック（reflection）とその先の調停機構（facilitator）が丸ごと機能停止しうる」問題であり、優先度の見直しが必要（詳細は[decision_lineage.md 論点19](decision_lineage.md)、[BL-017](issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り)）。ユーザー方針として、本修正はR4（ホワイトボード化・スコープ制御の検討）と合わせて着手する。

---

### BL-006: R2 ツール呼び出しループの`query_AI`集約実装

| 項目 | 内容 |
|------|------|
| 状態 | `done` |
| 優先度 | P1 |
| 依存 | BL-001（R2頭で実施） |
| 関連 | [D-008](decision_log.md#d-008-r201ツール呼び出しループをquery_aiに集約する設計を承認)、[decision_lineage.md 論点7](decision_lineage.md)、impl_Plan R2.0.1 |

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
| 関連 | [D-006](decision_log.md#d-006-python-replサンドボックスはビルトイン呼び出しのast検査多層防御を追加する)、[decision_lineage.md 論点5](decision_lineage.md)、impl_Plan R2.2 |

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
| 関連 | [D-007](decision_log.md#d-007-python-repl許可モジュールからrandomを除去しdecimalfractionsは理由付きで維持する)、[decision_lineage.md 論点6](decision_lineage.md)、impl_Plan R2.2 |

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
| 関連 | [D-004](decision_log.md#d-004-ツール呼び出しループは既存のtryexceptリトライブロック内に配置する)、[decision_lineage.md 論点3](decision_lineage.md)、impl_Plan R2.3 |

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
| 関連 | [D-009](decision_log.md#d-009-r2ツールループの例外処理を一時的api障害とロジックエラーに区別する)、[decision_lineage.md 論点9](decision_lineage.md)、impl_Plan R2.3 |

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
| 関連 | [D-010](decision_log.md#d-010-プロバイダ別function-calling対応の網羅検証はmvp段階では見送りblに留める)、[decision_lineage.md 論点10](decision_lineage.md)、要件定義書v35 付録B.5.3 |

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
| 関連 | [D-011](decision_log.md#d-011-b51既知誤判定detectorの偽陽性の非退行テストを指標dと対で追加する)、[decision_lineage.md 論点11](decision_lineage.md)、impl_Plan R2.6・R2.9・R2.10 |

**内容:**

別チャットのClaudeレビューにより、R2.6が付録B.5.1の既知誤判定（Detectorが上限内の数値差を`major`と誤判定するバグ）を修正するプロンプトを復活させる一方、R2.9の完了条件（指標D）は「矛盾を仕込んだケースを5/5検出できること」という陽性検出のみを定義しており、「上限内の正当な数値差を誤って`major`と判定しない」という陰性側（偽陽性回避）の非退行テストが計画・`phase1_dryrun.md`のいずれにも存在しないことが判明した。R2.5のF-2.6検算指示とR2.6の上限内数値差の除外指示は将来調整され得るため、指標Dのテストのみではこのバグの再発を検知できない。

**2026-07-19完了**: `tests/test_f26_detection.py`を新規作成。`test_detector_flags_numeric_contradiction_5_of_5`（Detector側指標D、5/5でmajor検出）、`test_reviewer_flags_numeric_contradiction_5_of_5`（Reviewer側指標D、5/5でpassed=False）、`test_detector_no_false_positive_within_cap`（B.5.1非退行、3回連続でnone/minorのままmajorが混入しないこと）の3テストを実装。シナリオは「申告合計は上限内に見えるが内訳の実合計は上限超過」（矛盾側）と「内訳・申告・上限すべて整合」（非退行側）の2種で、いずれも`python_repl`による再計算なしには検出できない設計とした（`python -m pytest --collect-only`で3件収集確認済み）。テストはDetector/Reviewerが使う`client_auditor`のAPIキー（`DSEEK_V4_FLASH_USER_KEY`）が未設定の環境では自動スキップする。

**2026-07-19追記（実LLM実行完了、T-7）**: ユーザーが実LLM呼び出しで実行。1回目はBL-013の不具合（`python_repl`が`print()`なしの裸の式で無出力になる問題）により1件非収束でFAILEDしたが、BL-013修正（ツール説明文に`print()`必須を明記）後の再実行で**3 passed**（Detector 5/5 major、Reviewer 5/5 passed=False、B.5.1非退行3/3 none）。指標D（5/5検出率）を実LLMで達成確認。詳細は[traceability.md T-7](traceability.md)参照。

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
| 関連 | [D-014](decision_log.md#d-014-max_tool_iterを5から10へ引き上げる暫定挙動を見て調整)、`cela_main.py` `_run_python_repl`・`_query_AI_live` |

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
| 関連 | [decision_lineage.md 論点15](decision_lineage.md)、`cela_main.py` `_PythonReplSession`（BL-014原因A、スコープ設計の先例） |

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
| 関連 | [D-016](decision_log.md#d-016-bl-016探索的タスクでの10回ツール呼び出し非収束へ2点の対応を実施する)、[decision_lineage.md 論点16](decision_lineage.md)、`cela_main.py` `_query_AI_live`・`call_detector`、`log/2026-07-19/1012/log_no_prompt.md`（実ログ） |

**内容:**

BL-014（A・B・C）修正後の本番ドライランで、`Expert:requirement_engineer`が3回目の差し戻し後の再試行中に`RuntimeError: ツール呼び出しが10回を超えて収束しませんでした`でクラッシュした（`cela_main.py:696`）。ログ（`log/2026-07-19/1012/log_no_prompt.md` 2489〜3423行目）を解析した結果、BL-014のいずれの原因（NameError／UnicodeEncodeError）の再発でもないことを確認した。`_PythonReplSession`は10回連続の呼び出しで変数を正しく引き継ぎ続けており、絵文字出力も一切クラッシュしていない。

**根本原因**: Expertが「3台の車両でピーク需要66.7人/hを満たせるか」という組合せ最適化問題（ルート分割・停車箇所数・相乗り率・予約スロット制など）に自力で取り組み、各iterで一つの案を試しては`❌`判定を受けて次の案に移る、という探索を繰り返した。iter=8では自分自身の前iterのモデルの矛盾（持ち越し客の待ち時間が実質3時間になる）に気づき自己修正するなど、F-2.6の趣旨に沿った良い挙動も見られたが、iter=9で「3台購入＋1台リース（実質4台）、初期投資1億円以内、実質赤字882万円で補助金枠3,000万円に収まる」という整合の取れた結論に到達した後も、iter=10で不要な再比較検算を実行してしまい、テキストでの最終回答を返す余地がゼロになった状態でMAX_TOOL_ITER=10に到達した。

**Detectorの役割との関係**: この差し戻しループの直前、Detectorは2回にわたり本質的に妥当な差し戻しを行っている。1回目は「指摘4点のうち3点に無回答のままTask 1.2も未提出」という完了度不足の指摘。2回目は機械的検算による本物の誤り3件の指摘（山間部区間で加重平均速度37km/hを誤用（制約上は20km/h指定）、シフトモデルが「最低2名常駐」要件を満たさない、システム維持費の内訳合計と主張額の64万円の不一致）。特に2回目はF-2.6が存在する理由そのものの実例であり、Detectorの厳格さ自体は正しく機能している。問題は、Detectorの完了度判定が「ユーザーの指摘全点に一度で完全に応える」という二値判定しかなく、「部分的に妥当な結論に達した時点で受理し残りは申し送りとする」という中間経路がないため、Expertが局所改善のループから抜け出せずMAX_TOOL_ITERを使い切ってしまう点にある。

**2026-07-19完了**: ユーザー承認（[D-016](decision_log.md#d-016-bl-016探索的タスクでの10回ツール呼び出し非収束へ2点の対応を実施する)）のもと2点を実装。

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
| 関連 | [BL-016](issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする)、[decision_lineage.md 論点16](decision_lineage.md)、[decision_lineage.md 論点20](decision_lineage.md)、要件定義書_v35.md F-9・F-10.2〜F-10.6（本Issueの上位互換にあたる既存仕様、下記追記参照） |

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
| 関連 | [decision_lineage.md 論点16](decision_lineage.md)、`cela_main.py` `LineageState`（`current_task_summary`）、`whiteboard_drafts`テーブル（`phase_id`/`task_id`列） |

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
| 関連 | [D-017](decision_log.md#d-017-openrouterのreasoningパラメータ形式を修正しツール付与ノードにも思考ログを追加する)、[decision_lineage.md 論点18](decision_lineage.md) |

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
| 関連 | [D-009](decision_log.md#d-009-r2ツールループの例外処理を一時的api障害とロジックエラーに区別する)（本Issueの元となった絞り込み）、`cela_main.py` `_query_AI_live` |

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
| 状態 | `open`（設計完了、実装未着手。Phase A→Phase Cの順で着手する方針決定済み、[D-020](decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)） |
| 優先度 | P1 |
| 依存 | なし（BL-002の指標C計測はむしろ本Issue完了後に着手すべき）。Phase B（reflection/facilitatorへの森レベル整合性の委譲）のみBL-005の解消が前提だが、Phase A・Cの着手には不要（D-020） |
| 関連 | [BL-002](issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（別軸、下記参照）、[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（Phase Bの前提、非ブロッカーとして後回し、[D-020](decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)）、[D-018](decision_log.md#d-018-r4ホワイトボード編集方式はコーディングエージェント方式遅延取得機械的照合パッチを採用する)、`log/2026-07-19/2056/log_no_prompt.md` |

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

**着手順序（[D-020](decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)、2026-07-20決定）:**

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

**詳細設計**: [`docs/design/phase2/cela_phase2_design_BL023_task_state.md`](phase2/cela_phase2_design_BL023_task_state.md)（BL-024・issue_backlog相当のDeferredステータス・traceability相当のacceptance_criteria充足チェック・確定値共有ストア`verified_facts`を含む統合設計）。

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
| 関連 | [D-024](decision_log.md#d-024-orchestratorの専門家選択を固定16種配列から自由記述に変更する) |

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
| 関連 | [D-025](decision_log.md#d-025-multiloggerの起動を__main__ガード内に限定する) |

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
| 関連 | [D-026](decision_log.md#d-026-max_tool_iterを10から15へ引き上げる) |

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
| 関連 | [D-027](decision_log.md#d-027-owned_variable_valuesはcontentと目的が異なることをプロンプトで明記する)、[BL-030](issue_backlog.md#bl-030-owned_variable_valuesを依存関係参照専用の要約レポートとして独立フィールド化する拡張案) |

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
| 関連 | [D-027](decision_log.md#d-027-owned_variable_valuesはcontentと目的が異なることをプロンプトで明記する) |

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
| 関連 | [D-028](decision_log.md#d-028-プレフィックスキャッシュヒット率改善はmvp完成後のコスト最適化枠として据え置く)、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（`light_system_prompt`によるコンテキスト軽量化、本Issueと同根の関心） |

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
| 関連 | [D-029](decision_log.md#d-029-同一task_idの兄弟decisionへの承認カスケードをdetector判定でガードして実装する)、[BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)（`task_criteria_status`/`owns_variables`基盤） |

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
| 関連 | [D-030](decision_log.md#d-030-expertの検算未実施を検出しdetectorへ提示しつつ複合失敗のみ強制差し戻しする) |

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
| 状態 | `open`（記録のみ、実装は見送り） |
| 優先度 | P3 |
| 依存 | なし |
| 関連 | [D-031](decision_log.md#d-031-deliverableの物理ファイル保存を承認前提にする設計変更はr4のホワイトボード化まで見送る)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（`whiteboard_drafts`/R4） |

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
| 依存 | [F-3.8](要件定義書_v35.md)（自律的DB/ファイル読み取りツール、未実装） |
| 関連 | [D-032](decision_log.md#d-032-フェーズ横断の確定値成果物アクセスはエージェント自律の読み取りツールf-38を新規追加して解決する) |

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

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
| 2026-07-18 | BL-010・BL-011を新規起票（別チャットClaudeのR2レビュー指摘、D-009・D-010準拠）。 |
| 2026-07-18 | BL-012を新規起票（別チャットClaudeのR2レビュー指摘、D-011準拠）。 |
| 2026-07-19 | R2実装完了に伴い、BL-001・BL-006・BL-007・BL-008・BL-009・BL-010・BL-012を`done`化。実装は`cela_main.py`に反映済み、実LLM呼び出しなしのオフラインスモークテスト（`_run_python_repl`単体、フェイククライアントによる`query_AI`ツールループ、BL-001のDB往復）で検証済み。BL-011（プロバイダ別Function Calling検証）はD-010どおりMVP後に据え置き、`open`のまま。テスト実行基盤としてpytestを`requirements-dev.txt`に追加し導入（ユーザー承認済み）。 |
| 2026-07-19 | BL-015を新規起票（ユーザー提案：資料由来の一次情報・python_repl出力の機械的再利用によるハルシネリスク低減。決定はまだなく設計相談中、[decision_lineage.md 論点15](decision_lineage.md)）。 |
| 2026-07-19 | BL-016・BL-017・BL-018を新規起票。本番ドライランでの10回ツール呼び出し非収束クラッシュの原因分析（BL-016）、差し戻しループ沼からの脱出機構構想（BL-017）、task_planner由来のタスク間依存関係の状態未構造化（BL-018）。いずれも設計相談中、[decision_lineage.md 論点16](decision_lineage.md)。 |
| 2026-07-19 | BL-016を`done`化。ツールループへの残りiter数通知の注入と、Detector完了度判定の緩和（数値検算の厳格さは維持）をユーザー承認のもと実装（[D-016](decision_log.md)）。オフラインスモークテストで確認済み、実LLM再ドライラン待ち。BL-017はユーザー訂正を受け、ファシリテーター自体は`facilitator_node`として既存であり、差し戻しループ検知のトリガーのみ未実装と内容を修正。 |
| 2026-07-19 | BL-019を新規起票・`done`化。OpenRouterのreasoningパラメータがフラットキーで無効化されていた実装バグを実機検証で発見・修正し、ツール付与ノードにも思考ログ出力を追加（[D-017](decision_log.md)）。実機検証で思考ログの出力を確認済み。 |
| 2026-07-19 | BL-019に追記。tool_calls同梱content読み捨ての防御的対応と、実本番ログで確認した空白content表示の小修整。BL-020を新規起票・`done`化。中国語系モデル経由の言語逸脱対策として`query_AI`集約点に日本語出力の強制指示を注入（`_inject_japanese_output_directive`）。 |
| 2026-07-19 | BL-021を新規起票（ユーザー提案：全11箇所のプロンプト生成関数の英語化。BL-020の対症療法に対する根本対応の候補。設計未着手、`open`）。 |
| 2026-07-19 | BL-005を重要度「高」に更新（reflection/facilitatorが事実上発火不能という副作用が実ログで判明）。BL-017を大幅加筆（当初のreflection/Facilitator設計意図の想起、「ゴール抽象化・そもそも論」という本来の調停行動の具体例、現行`call_facilitator`実装との乖離、「生産的な反復」と「本当の膠着」を区別するトリガー設計の必要性を記録）。いずれもR4着手時に合わせて対応する方針（[decision_lineage.md 論点19](decision_lineage.md)）。 |
| 2026-07-19 | BL-017を再定義：要件定義書_v35.md F-9・F-10.2〜F-10.6として既に仕様化・Phase 6以降に配置済みだったことが判明し、BL-017はその「MVP範囲での先行縮小実装」と位置づけ直した。D-018（R4パッチ方式の決定）を新規記録（[decision_lineage.md 論点20](decision_lineage.md)）。 |
| 2026-07-19 | BL-022を新規起票・`done`化。本番ドライランのフルトレースバック解析により、OpenRouter経由の壊れたレスポンスがopenai SDK内部で生の`json.JSONDecodeError`を送出しD-009の絞り込んだexceptを素通りしていたことが判明。exceptタプルに`json.JSONDecodeError`を追加し修正（D-019）。 |
| 2026-07-19 | BL-023を新規起票。指標C計測（BL-002）着手時に判明した、task_plannerの分解粒度の粗さによる検証コストの乗算的増大（今日のtask_1.2ドライランで実証）を記録。ユーザーは指標C計測・R4・BL-018のいずれよりも本Issueを最優先で対応する方針（[decision_lineage.md 論点21](decision_lineage.md)）。 |
| 2026-07-20 | BL-023に追記。ログ精査により真の増幅源が`generate_user_utterance`（User AI）側のスコープ肥大にもあることが判明し、設計対象をtask_plannerのみから拡張。さらにユーザーとの議論で「共有変数の一元所有（BL-018）」「予算のトップダウン・カスケード（ただし仮説であり絶対制約としない）」「森レベルの整合性はreflection/facilitator（BL-005）に戻す」の3点セット設計が必要と判明し、関連BLとBL-005を追加、完了条件を更新（[decision_lineage.md 論点22](decision_lineage.md)）。 |
| 2026-07-20 | BL-023の着手順序を決定（D-020）。Phase A（task_planner/User AIのスコープ是正）・Phase C（予算カスケードの仮説化）を先行させ、Phase B（BL-005 reflection/facilitator復旧）は非ブロッカーとして後回しにする方針。完了条件をPhase A/B/C別に再構成（[decision_lineage.md 論点23](decision_lineage.md)）。 |
| 2026-07-20 | BL-023の設計をこのプロジェクト自身の統治構造（issue_backlog/decision_lineage/phase_gate/STATUS/traceability/確定値の再利用）に対応する情報構造としてstateへ統合する方向で拡張。BL-024（`current_phase`初期化後フリーズ、`task_id`単位の状態追跡不在）を新規起票し、詳細設計を`docs/design/phase2/cela_phase2_design_BL023_task_state.md`として作成（[decision_lineage.md 論点24](decision_lineage.md)）。 |
| 2026-07-20 | BL-023 Phase AとBL-024を実装し`done`化。`Task`型新設・`Phase`/`Agreement`/`LineageState`拡張・DBマイグレーション（`agreements.task_id`列・`verified_facts`テーブル）・`call_task_planner`のacceptance_criteria/depends_on/owns_variablesスキーマ拡張・`decision_extractor`の状態遷移一元管理＋Deferredステータス＋確定値抽出・Detectorのcriteria_status充足チェック・`generate_user_utterance`のペルソナ分離＋スコープ限定を実装。`python -m py_compile`合格、オフラインスモークテスト（DBマイグレーション・`verified_facts` upsert・`_get_current_task`・`_resolve_task_transition`のフェイルクローズ）はすべてPass。**実LLM呼び出しを伴う実機ドライランでの効果確認は未実施** — Phase C（予算カスケード）着手前にユーザーの指示待ち。 |
| 2026-07-20 | BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）をレビュー。task_planner出力が全タスクでacceptance_criteria（3個以内）・depends_on・owns_variablesを適切に生成し、以前task_1.2で束ねられていた車両台数・初期費用・ランニングコスト・感度分析が別タスク（task_2_2/4_1/4_2/4_3）に分割され、共有変数の一元所有パターンが機能していることを確認。`generate_user_utterance`も現在タスクの範囲に指示を限定できていた。副次的発見として、Decision Extractor/Orchestratorの`reasoning`フィールドの中国語出力を確認したが、ユーザー判断によりBL-020のスコープ外と決定（D-022、BL-020にスコープ明確化を追記）。 |
| 2026-07-20 | 同ドライランでExpertが他タスク（task_2_2）のowns_variables（車両台数・システム費内訳・サイクルタイム）まで自発的に計算しツールループが10回で非収束クラッシュしたことを発見。BL-025を新規起票し、①call_expertへのスコープガードレール注入、②ツールループ2周目以降のsystem_prompt軽量化（`light_system_prompt`）の2案をユーザー承認のもと実装着手（D-023、[decision_lineage.md 論点26](decision_lineage.md)）。 |
| 2026-07-20 | BL-025を実装し`done`化。`_build_task_scope_context`ヘルパーを新設し`generate_user_utterance`/`call_expert`で共通化。`call_expert`にスコープガードレール（①）を注入。`query_AI`/`_query_AI_live`に`light_system_prompt`引数を追加し、`_JAPANESE_OUTPUT_DIRECTIVE`を定数化した上でツールループiter=2以降のsystem_promptを軽量版に差し替え（②）。`python -m py_compile`合格、フェイククライアントによるオフラインスモークテスト2件（ガードレール注入確認、iter=1フル文脈/iter=2以降軽量文脈への切替確認）はすべてPass。実機再ドライラン確認は未実施。 |
| 2026-07-20 | ユーザーの設計問い直しを受け、専門家選択の固定16種配列（`valid_experts`）がグラフ・`call_expert`のどちらでも分岐に使われておらず無用な足かせだったと判明。BL-026を新規起票・`done`化し、`call_orchestrator`を自由記述の専門家肩書き生成＋軽量フォールバックに変更（D-024、[decision_lineage.md 論点27](decision_lineage.md)）。専門家ごとの個別ノード・個別グラフ構造はMVP未完成の現時点では見送り。 |
| 2026-07-20 | 実ドライラン（`log/2026-07-20/1421`）レビュー中に、同時刻帯の不自然な小ログフォルダ（`1455`・`1458`）を発見。原因は`cela_main.py`の`sys.stdout = MultiLogger()`がモジュールのトップレベルにあり、`import cela_main`するだけで本番`log/`配下に新規ディレクトリが作られる構造だったこと（このセッションのオフラインスモークテストが誤って混入させていた）。BL-027を新規起票・`done`化し、`__main__`ガード内への移動で修正、誤生成ログを削除（D-025、[decision_lineage.md 論点28](decision_lineage.md)）。 |
| 2026-07-20 | 同ドライラン継続分（〜23278行）のレビューで、task_2_2のExpert呼び出しが`iter=10/tool_calls=9`とMAX_TOOL_ITER上限ぎりぎりで終了していたことを確認。BL-028を新規起票・`done`化し、クラッシュ回避を優先してMAX_TOOL_ITERを10→15に引き上げ（D-026、[decision_lineage.md 論点29](decision_lineage.md)）。この変更はソース修正であり、レビュー時点で実行中だった1421プロセス自体には反映されない。 |
| 2026-07-20 | 同ドライラン継続分のレビューで、task_2_2の`verified_facts`（`operation_schedule`）にレポート全文がそのまま混入する事故を発見。`content`向けの「要約禁止」指示が`owned_variable_values`に波及していたことが原因と判明。ユーザーへの確認により、`content`の要約禁止は「部分成果物を後で製本する」設計思想に基づく意図的な仕様であり変更しないこと、`owned_variable_values`は目的が異なる簡潔な要約であるべきことが整理された。BL-029を新規起票・`done`化しプロンプトに目的の区別を明記（D-027、[decision_lineage.md 論点30](decision_lineage.md)）。あわせて、独立フィールド化の拡張案をBL-030として起票（`open`、`decision_extractor`が将来補助的役割に縮小する設計と合わせて再検討）。 |
| 2026-07-20 | task_3_1レビューでUser AIがtask_2_3のコスト内訳との整合性を正しく取っていた挙動を分析。実際にはBL-023 Phase Aの構造化機構ではなく、`chat_history_window`の隣接性（task_2_3が直前タスクだったため生の全文がまだウィンドウ内に残っていた）による偶発的な副作用であり、`depends_on`宣言も実態を過少申告していることが判明。BL-018への追記として記録（[decision_lineage.md 論点31](decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがOpenRouter実績（直近24時間4.6Mトークン、キャッシュヒット率19.7%、コスト$0.65）を共有。本日のログレビューで確認した可変ブロック（Recent Decisions再掲・task_planner出力JSON全体等）の毎ターン再送がヒット率を下げている可能性を指摘し、BL-031として新規起票（`open`、MVP完成後のコスト最適化枠、D-028、[decision_lineage.md 論点32](decision_lineage.md)）。 |
| 2026-07-20 | ユーザーが「合意・決定事項・検討状況DB」のプロンプト出力を確認し、task_2_3の4件のDecisionが親Deliverable承認後も永久にProposedのまま取り残されていることを発見。承認カスケードの単純な機械化は本当の未検討事項を隠蔽するリスクがあるというユーザー指摘を受け、同ターンのDetector判定（`constraint_issue`/`task_criteria_status`）が清浄な場合のみカスケードするガード付き設計を採用。BL-032を新規起票（`open`、設計確定・実装承認済み、D-029、[decision_lineage.md 論点33](decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがtask_5_2のログで、Expertがpython_repl未使用のまま「検算完了」と虚偽申告していた事故（Detectorの独立検算により実害なし）を発見。単純な強制差し戻しの無限ループリスクをユーザー自ら指摘し、①Expertの実行記録をDetectorに提示②Expert/Detector双方が未使用の場合のみ強制差し戻し、の2段構えに加え、実行記録の保存・提示という追加提案を統合してBL-033を新規起票・`done`化。`_query_AI_live`/`expert_node`/`call_detector`/`detector_node`を実装し、オフラインスモークテスト4件（記録保存・空リスト記録・複合失敗ガード発火・独立検算時の非発火）で確認（D-030、[decision_lineage.md 論点34](decision_lineage.md)）。 |
| 2026-07-20 | ユーザーがtask_6_3のログで、`decision_extractor_node`がDeliverableの`status`（Proposed/Approved）を問わずCREATE判定時点で無条件にファイル保存していることを発見。`integrator_node`が`status=="Approved"`のみを集約するため正当性は壊れていないが、却下・修正版のたびに旧版が孤児ファイルとして残る衛生上の課題として整理。ユーザーはR4のホワイトボード化（md差分読み書き）で構造的に解消される見込みと判断し、現時点では実装せずBL-034として記録のみ起票（`open`、D-031、[decision_lineage.md 論点35](decision_lineage.md)）。 |
