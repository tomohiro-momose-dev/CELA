# 要件トレーサビリティ — FEATURE_NAME

**要件が Phase・実装・検証でカバーされているか**を管理する。

| 種別 | 参照先 |
|------|--------|
| 要件マスター | [要件定義書_v35.md](要件定義書_v35.md) |
| 完了定義 | [phase_gates.md](phase_gates.md) |
| 実装タスク | [issue_backlog.md](issue_backlog.md) |

---

## タスク（要件定義より）

| タスク | Phase | 成果物 / 証跡 | 状態 |
|--------|-------|--------------|------|
| （記入） | | | ☐ |

---

## 受け入れ基準（AC）

| ID | 完了条件 | 主担当 Phase | 検証方法 | 関連 BL | 状態 |
|----|----------|-------------|---------|---------|------|
| AC-1 | （要件定義の完了条件と対応） | | | | ☐ |
| AC-2 | | | | | ☐ |
| AC-3 | | | | | ☐ |

---

## 機能要件 → Phase

| 機能 | 説明 | Phase | 設計 / 実装 | 状態 |
|------|------|-------|------------|------|
| F-1 | （記入） | | | ☐ |

---

## 検証証跡（記入用）

| 試験 ID | 内容 | 実施日 | 実施者 | 結果 | ログ / 備考 |
|---------|------|--------|--------|------|------------|
| T-1 | （例: 最小ドライラン） | | | | |
| T-2 | （例: 通し試験） | | | | |
| T-3 | R1 SQLite永続化層のスモークテスト（`get_db_connection`/`init_db`/`db_append_decision`/`db_append_agreement`/`db_supersede_agreement`/`get_*_from_db`/`_build_*_context_from_db`をダミーデータで実行し、内容一致・Superseded除外・接続クローズ後の再オープンでの残存を確認） | 2026-07-18 | Claude (実装セッション) | Pass | `python -m py_compile cela_main.py` も合格。実際のLLM API呼び出しを伴う`run_ai_vs_ai_loop`本体のE2E実行、および設計書§5.1の本番シナリオ（過疎地域バスA/Bテスト）でのドライランは未実施（BL-002参照） |
| T-4 | Record&Replayスタブ（`query_AI`のREPLAY_MODE=record/replay、call_seqキー、キャッシュミス時の例外送出）のダミークライアントによるスモークテスト | 2026-07-18 | Claude (実装セッション) | Pass | 実際のLLM応答を使ったrecord→replayの往復検証（impl_Plan §7.2の合格基準1・2）は未実施（BL-003参照） |
| T-5 | 実データA/Bドライラン（過疎地域バスシナリオ）。list版ベースライン（コミット`5ef0382`＋Record/Replayスタブ移植）をRecordモードで実行し、Turn 1〜Turn 2完了直後（Turn 3開始直後、`app.invoke()`外側）で打ち切り。同フィクスチャ（45件、`(label, call_seq)`キー）をSQLite版（コミット`2133989`）でReplay実行し、構造的一致（合格基準1、impl_Plan §7.2）を確認 | 2026-07-18 | ユーザー（実行）/ Claude（Replay実行・検証） | Pass | agreements件数15=15、decisions件数47=47、status分布（Proposed 6/Approved_with_Conditions 2/Rejected 1/Superseded 6）一致、topic登録順序（`ORDER BY id`）一致。Replayはseq=45（`User AI`、Turn 3冒頭）で想定通りのキャッシュミス例外を発生させて停止 — list版ベースラインの停止点と完全に一致し、それより前は全件再現。**30ターン完走はしていない**（[decision_log.md D-001](decision_log.md)により必須要件から除外済み）。Hydrate再現性（合格基準2）・再起動後保持（合格基準3、SQLite版側）は本試験の対象外、指標A・C（設計書§5）も未測定 — 詳細は[issue_backlog.md BL-002](issue_backlog.md)参照 |
| T-6 | R2（ツール呼び出し基盤・機械的検算ゲート）実装後のオフラインスモークテスト（実LLM API呼び出しなし）。(a) BL-001: `db_append_agreement`/`get_agreements_from_db`/`_build_agreements_context_from_db`のダミーデータDB往復で`decision_what`/`reason_why`が正しく往復し`content`/`rationale`エイリアスが復元されないことを確認。(b) `_run_python_repl`単体: 許可モジュール(math/statistics/datetime/json/fractions/decimal)の正常動作、不許可import(os等)・危険ビルトイン呼び出し(open/eval/exec/__import__)のAST拒否、`random`除外(D-007)、タイムアウト、構文エラーハンドリングを個別に確認。(c) `query_AI`ツール呼び出しループ: OpenAI SDK互換のフェイククライアント（`.chat.completions.create`をスクリプト化）により、tools=None時の非破壊、python_repl往復と最終応答返却、壊れたtool_call引数JSONの自己修復（D-009）、`MAX_TOOL_ITER=5`非収束時の`RuntimeError`伝播（D-009）、`finish_reason="length"`のツールループ内検出（D-009）の5パターンを検証。`python -m py_compile cela_main.py`および`tests/test_f26_detection.py`の`pytest --collect-only`（3件収集、import含めて成功）も合格 | 2026-07-19 | Claude（実装セッション） | Pass | いずれも実LLM API呼び出しは伴わない（コスト・時間ゼロ）。**指標D（数値矛盾検出率5/5）・指標C（収束性とコストのトレードオフ）の実測、および`tests/test_f26_detection.py`自体の実LLM実行はこのセッションでは未実施** — 課金・実行時間を伴うためユーザーの明示的な指示を待って実施する（[issue_backlog.md BL-002](issue_backlog.md)、[BL-012](issue_backlog.md)参照） |
| T-7 | 指標D（数値矛盾検出率）の実LLM実測。`tests/test_f26_detection.py`をユーザーが`py -m pytest tests/test_f26_detection.py -v -s`で実行（`client_auditor`=`client_openrouter`、実API呼び出し）。1回目の実行で試行3/5がMAX_TOOL_ITER=5非収束によりFAILED（Detectorが`print()`なしの裸の式`2500 + 300 + 800`を3回連続送信し`"[REPL] (no output)"`を受け取り続け、iter=4・5でようやく`print()`に切替えたが応答前に予算切れ）。原因はBL-013：`_run_python_repl`が`python -I -c`の非対話実行のため裸の式は無出力になるが、`PYTHON_REPL_TOOL`の説明文にその旨の明記がなかったこと。ツール説明文に`print()`必須の警告を追記（BL-013）した上で再実行 | 2026-07-19 | ユーザー（実行）/ Claude（ログ解析・修正） | Pass（再実行後） | **1回目**: Detector 4/5 major検出、1件非収束でFAILED（指標D未達、原因はBL-013のツール定義不備）。**BL-013修正後の再実行**: `test_detector_flags_numeric_contradiction_5_of_5`5/5でmajor、`test_reviewer_flags_numeric_contradiction_5_of_5`5/5でpassed=False、`test_detector_no_false_positive_within_cap`3/3でnone（B.5.1非退行）。3 passed in 330.04s。非収束0件、`python_repl`呼び出しはほぼ全試行iter=1で正答（`print()`忘れによる無出力は再発せず）。指標D（5/5検出）達成を実LLMで確認（[issue_backlog.md BL-012](issue_backlog.md)完了）。**指標C（収束性とコストのトレードオフ、変更前後・最低5試行比較）は未測定**（[issue_backlog.md BL-002](issue_backlog.md)参照） |
| T-8 | 指標D追加検証（乗算・除算・複数制約版）。単純加算のみのT-7シナリオでは1回のツール呼び出しで即決着しがちなため、より複雑な検算（総額=単価×日数×台数の乗算、1人あたり単価=総額÷利用者数の除算という2種の演算、かつ独立した2制約の並行チェック）を要求する`test_detector_flags_multiplicative_contradiction_5_of_5`を新規追加し実LLM実行。Expertは誤った総額（32,800,000円、上限3,300万円以内に見える）を主張しているが、正しい計算（32,000×260×4=33,280,000円）では上限を280,000円超過。一方1人あたり単価は正しい値（33,280,000÷21,000≒1,584.76円）でも上限1,600円/人以内で違反なし、という「2制約のうち片方のみ実際には違反」という設計 | 2026-07-19 | ユーザー（実行）/ Claude（シナリオ設計・ログ解析） | Pass | 5/5でconstraint_issue='major'。全試行で「総額は上限超過・1人あたりは上限内」という2制約の切り分けが判定コメントに正しく反映された（例: 試行1「1人あたり年間輸送コストは...上限1,600円/人以内なので、そちらの制約は満たしている」）。ツール呼び出し回数は試行ごとに1〜3回とばらつきがあり（複数回に分けて自問するケースと1回で両方計算するケースの両方が観測された）、非収束は0件。`print()`忘れによる無出力（BL-013）の再発もなし。1 passed in 151.11s | 
| T-9 | BL-019（reasoning可視化）と既存F-2.6（python_repl機械的検算）の組み合わせ効果の定性検証。本番ドライラン（`Expert:requirement_engineer`、Phase1 task_1_1「地域データの収集と整理」）で、ツール呼び出し前後に💭思考ログが可視化されたことにより、「検算→誤りに気づく→再検算→修正」という自己修正サイクルが外部ログから追跡可能になったことを確認 | 2026-07-19 | ユーザー（実行）/ Claude（ログ解析） | Pass（定性的確認、定量指標は未測定） | 山間部区間の勾配計算で単位換算ミス（`elevation_diff(250, m単位) / mountain_dist(4, km扱いのまま) * 100`で正しくは6.25%のところ6250%と誤表示、`log/2026-07-19/2056/log_no_prompt.md:686`）が発生。次iterの💭思考が「that's wrong because mountain_dist should be in meters, not km」と自ら誤りを検出し（同ファイル699-703行目）、python_replで単位を統一して再計算・6.25%に修正（同721行目）。F-2.6の機械的検算とBL-019の思考可視化が組み合わさることで、ツール使用を伴う探索的タスクが実質的にステップバイステップの思考・検証・自己修正サイクルとして機能していることが実ログで定性的に確認された。なお同ログにはBL-020修正前の中国語思考混入（同ファイル2426行目）も観測されており、BL-020の実装動機を裏付ける実例にもなっている。自己修正の発生率等の定量測定は本試験の対象外。**追加事例（2026-07-19、`Expert:cost_optimizer`、task_1_2「予算制約の明文化」）**: 数値・単位ミスとは異なる種類の自己修正として、Python構文エラー（`1台あたり_トリップ数`等、数字始まりの識別子は無効というPython言語仕様違反）による`[REPL Error] SyntaxError: invalid syntax`をiter=1で受け、iter=2の💭思考が「variable names can't start with a number」と正しく原因を診断したが、修正コードに`3台輸送力`という同種の数字始まり識別子を再び残してしまい同一エラーが再発。iter=3の💭思考で該当行・該当識別子を正確に特定し`台数3_輸送力`へ改名して解消、以降は計算が正常に進行した。1回で完全に直らず2回越しで収束する例もあることを示す実例（ログファイルは本会話内で共有されたもので、セッション終了後のファイルパスは未確定） |
| T-10 | **BL-023 Phase A適用後、初の全18タスク・全6フェーズ完走**。実ドライラン（`log/2026-07-20/1421`、2026-07-20 14:21起動〜23:36ユーザーが手動停止）。task_planner分解（6フェーズ・18タスク、acceptance_criteria/depends_on/owns_variables付き）に基づき、Phase 1（基礎データ分析）〜Phase 6（全体検証・総合導入計画完成）まで、`decision_extractor`による全成果物のファイル出力（`log/2026-07-20/1421/deliverables/`、21ファイル）とDB記録を伴って完走。実行中にBL-026〜BL-033（専門家自由記述選択・`MultiLogger`誤起動・MAX_TOOL_ITER引き上げ・`owned_variable_values`要約汚染・兄弟Decision承認カスケード欠如・Expert検算未実施の虚偽申告対策等）を発見・一部修正（詳細は[issue_backlog.md](issue_backlog.md)、[decision_log.md](decision_log.md) D-024〜D-030） | 2026-07-20 | ユーザー（実行・停止判断）/ Claude（ログ解析・検算） | Pass（定性的完走確認。指標C の定量的な変更前後比較は未実施） | **task_6_3（総合導入計画の完成）での自己修正サイクル**: Expertがピーク輸送力を`60÷13.8×9×3=117人/時`と二重計上で誤計算しDetectorが`major`で差し戻し（2回、うち1回は同じ誤りをそのまま再提出）。3回目のリトライで誤りを自認し、task_2_1で確定済みの車両時間モデル（8.35時間必要／9.0時間利用可能）に基づく実効輸送力`71.9人/時`を提示、Ver.1.2として正式に修正・承認された。`expert_retry_count>=3`の`reflection`エスカレーション上限には達しておらず、通常のリトライ枠内（3回以内）で収束（BL-035で懸念した無限ループは本件では発生せず）。修正後の数値をPython REPLで独立検算し、`task_2_1`自身の余裕率7.78%と`Ver.1.2`の余裕率7.78%が数式的に一致することを確認（でっち上げ値ではなく既存の車両時間モデルの正当な再利用と判断）。なお、task_2_1由来の`8.35車両時間`という数値へExpertがアクセスできたのは、`_build_task_scope_context`のフェーズ横断`verified_facts`参照（BL-035で構造的に不可能と判明）経由ではなく、毎ターンの「合意・決定事項・検討状況DB」recap内でDecision型エントリの生テキストとして偶然表示されていたため（Deliverable型は`FILE_PATH:`ポインタのみで本文が出ないのと対照的）。**プロセスの手動停止**は、既に承認済みのVer.1.2の数値をlogic_verifierペルソナが再度追認した後、Detectorが独立検算で再確認している最中（python_repl実行後、判定文の出力前）に行われたもので、結論には影響しない（Claudeが同一の4数値を独立に再検算し、Detectorの判定が出ていれば`none`だったことを確認済み）。**指標C（収束性とコストのトレードオフ、R1版/BL-023適用前後の比較）はこの1試行のみでは未測定**（[BL-002](issue_backlog.md)参照、比較対象となるBL-023適用前のベースライン試行が必要） |

詳細手順は `phaseN/phaseN_dryrun.md`、失敗は BL へ。

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
| 2026-07-19 | T-6追加（R2実装後のオフラインスモークテスト、Pass）。実LLM呼び出しを伴う指標C・Dの実測はユーザー指示待ちのため未記録。 |
| 2026-07-19 | T-7・T-8追加（指標D実LLM実測、いずれもPass）。T-9追加（BL-019による思考可視化とF-2.6検算の組み合わせで、本番ドライランの実ログから自己修正サイクルを定性的に確認、Pass）。 |
| 2026-07-20 | T-10追加。BL-023 Phase A適用後初の全18タスク・全6フェーズ完走（`log/2026-07-20/1421`）をPassとして記録。task_6_3のピーク輸送力誤計算がDetectorの差し戻しにより3回のリトライ内で自己修正されたことを確認（無限ループ懸念は本件では発生せず）。指標Cの定量比較はベースライン試行が別途必要なため未達成のまま。 |
