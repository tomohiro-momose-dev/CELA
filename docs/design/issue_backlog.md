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
| BL-005 | 中 | `cela_main.py` (`build_graph()`既存トポロジ) | `state["turn_count"]`が`app.invoke()`1回の間凍結され、外側ループの「Nターン目」表示・上限が実際の対話ラウンド数と一致しない | P2 |
| BL-006 | 中 | `cela_main.py` (`query_AI`) | ~~R2 ツール呼び出しループの`query_AI`集約実装（D-008）~~ → `done`（R2実装） | P1 |
| BL-007 | 高 | `cela_main.py` (`_run_python_repl`) | ~~R2 Python REPL サンドボックスの多層防御・危険呼び出し AST 検査（D-006）~~ → `done`（R2実装） | P1 |
| BL-008 | 低 | `cela_main.py` (`_ALLOWED_IMPORTS`) | ~~R2 許可モジュールから`random`を除去、`decimal`/`fractions`は理由付き維持（D-007）~~ → `done`（R2実装） | P2 |
| BL-009 | 低 | `cela_main.py` (`query_AI`ツールループ) | ~~R2 ツールループのリトライ粒度（層1/層2）の粗さを許容する（D-004）~~ → `done`（`[CONSTRAINT]`コメントで明示済み） | P3 |
| BL-010 | 高 | `cela_main.py` (`_query_AI_live` ツールループ) | ~~ツールループの例外（壊れたJSON引数・非収束・truncation）が既存の広い`except Exception`に飲み込まれ原因が隠蔽される（D-009）~~ → `done`（R2実装） | P1 |
| BL-011 | 中 | `cela_main.py` (`_query_AI_live` プロバイダルーティング) | OpenRouter経由の複数バックエンドでのFunction Calling対応状況が未検証（D-010、MVPでは見送り） | P2 |
| BL-012 | 高 | `tests/test_f26_detection.py` (R2) | ~~B.5.1既知誤判定（Detectorの偽陽性）の非退行テストが指標Dと対で定義されていない（D-011）~~ → `done`（テスト実装済み。実LLM実行で指標D 5/5・5/5・非退行3/3を確認、T-7） | P1 |
| BL-013 | 高 | `cela_main.py` (`PYTHON_REPL_TOOL`) | ~~実LLM実行でDetectorが`print()`なしの裸の式を繰り返しツール呼び出しし非収束・テスト失敗~~ → `done`（ツール説明文修正後の再実行で非収束0件、T-7） | P1 |
| BL-014 | 高 | `cela_main.py` (`_run_python_repl`, `_PythonReplSession`, `_query_AI_live`) | ~~本番ドライラン（Expertノード）で非収束クラッシュ。原因A)状態非保持のNameError、B)絵文字printのUnicodeEncodeError、C)MAX_TOOL_ITER不足~~ → `done`（A: 対話的セッション化、B: `-X utf8`、C: 暫定10。オフライン確認済み、実LLM再ドライラン待ち） | P0 |

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

## 更新履歴

| 日付 | 内容 |
|------|------|
| YYYY-MM-DD | 初版 |
| 2026-07-18 | BL-010・BL-011を新規起票（別チャットClaudeのR2レビュー指摘、D-009・D-010準拠）。 |
| 2026-07-18 | BL-012を新規起票（別チャットClaudeのR2レビュー指摘、D-011準拠）。 |
| 2026-07-19 | R2実装完了に伴い、BL-001・BL-006・BL-007・BL-008・BL-009・BL-010・BL-012を`done`化。実装は`cela_main.py`に反映済み、実LLM呼び出しなしのオフラインスモークテスト（`_run_python_repl`単体、フェイククライアントによる`query_AI`ツールループ、BL-001のDB往復）で検証済み。BL-011（プロバイダ別Function Calling検証）はD-010どおりMVP後に据え置き、`open`のまま。テスト実行基盤としてpytestを`requirements-dev.txt`に追加し導入（ユーザー承認済み）。 |
