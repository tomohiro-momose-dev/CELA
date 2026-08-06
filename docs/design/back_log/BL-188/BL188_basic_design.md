# BL-188: 全ての情報にソース（citations）を明示させる 基本設計

## Context

BL-184（web_search/web_fetch/read_reference_fileのcela_main.py配線）完了報告に対し、ユーザーから
以下の要望があった:

> 数字などの確定値、暫定値のdb登録は既にあるが、引用や参照元を明示させたい。数字だけではなくて、
> 基本的にはすべての情報のソースを明示させたい。また、情報は可能な限り最新のものを参照し、
> 基本的には公的な一次ソースを参照させる。web検索で得た情報も、鵜呑みにはせず批判的思考で
> 評価しながら使用する。

コード調査の結果、`citations`という概念自体は既にDBスキーマ上存在していたが、実質的に機能して
いなかったことが判明した:

- `verified_facts.citations`列（F-3.9/R3a、`upsert_verified_fact`）は存在するが、
  `_write_agreement_impl`内の呼び出し（旧: `cela_main.py`の`_commit_agreement_from_tool`
  内confirmed_variablesループ付近）では`citations=[args.get("topic", "")]`と、**そのDecisionのtopic文字列がそのまま入るだけ**だった。
  実在のURL・文書・根拠を表すものではない。
- `WRITE_AGREEMENT_TOOL`のスキーマ（`confirmed_variables`パラメータ定義）には、そもそも
  `citations`をLLMが渡すためのフィールド自体が存在しなかった。LLMは本物の引用元を渡そうとしても
  渡す手段がなかった。
- `agreements`テーブル本体（Decision/Deliverableのレコードそのもの）には、構造化されたソース欄が
  一切なく、自由記述の`evidence`列（F-2.6、主にpython_repl検算結果の記録用）しかなかった。

つまり「見つからない」以前に「そもそも書ける場所がない／書いても実質的に捨てられる」状態だった。

## 設計方針の確認（AskUserQuestion）

実装規模とリスクが異なる2つの分岐点をユーザーに確認した（過去のBL-042「Detectorの硬直判定で
ツールループが同じ論点を延々再検討した」事故の再発を避ける目的）。

1. **citations未記載の強制力**: 「プロンプト誘導のみ（推奨・まず様子見）」を選択。
   Detectorのminor/major判定への機械的な組み込みは今回は行わない。
2. **citations欄の適用範囲**: 「agreementsテーブル（Decision/Deliverable本体）にも新規citations列を
   追加」を選択。`confirmed_variables`限定の小さな修正ではなく、Decision/Deliverable全体に
   構造化ソース欄を持たせる、より野心的な変更を採用。

## 実装内容

### 1. スキーマ

- `agreements`テーブルへ`citations TEXT DEFAULT '[]'`列を追加（`CREATE TABLE`定義、および
  既存DBとの後方互換のため`_ensure_agreements_citations_column`マイグレーション関数を新設、
  `_ensure_agreements_task_id_column`と同型のパターン）。
- `verified_facts.citations`（既存、F-3.9/R3a）はそのまま。

### 2. `WRITE_AGREEMENT_TOOL`スキーマ拡張

- トップレベル`citations`パラメータ（配列、`{"type": "web"/"goal_text"/"prior_agreement"/
  "expert_calculation"/"user_input"/"document", "detail": "URLや説明文"}`のリスト）を追加。
  このDecision/Deliverable全体（decision_what/reason_why）が何に基づくかを表す。
- `confirmed_variables[]`の各要素にも同じ形の`citations`サブフィールドを追加。個々の確定値ごとに
  異なるソースを持ちうるため（例: 車両台数はExpertの試算、運賃は外部相場のURL）、トップレベルとは
  独立に指定できる。
- ツール説明文へ、一次ソース優先・最新情報優先・web検索結果の批判的評価を促す指示を追記
  （「Prefer authoritative primary sources over secondary summaries」「cross-check surprising or
  load-bearing numbers against a second source」等）。

### 3. 実装（`_commit_agreement_from_tool`/`_write_agreement_impl`）

- `args.get("citations", [])`をJSON化して`agreements.citations`へ永続化。
- `confirmed_variables[].citations`が指定されていればそれを`verified_facts.citations`へ使う。
  **未指定時は従来通りtopic文字列へフォールバックする**（後方互換、プロンプト誘導のみで強制しない
  という決定に対応する「弱いシグナルとして残す」設計）。
- `db_append_agreement`（レガシーパス）にも同様に`citations`列を配線（未指定時は空配列）。

### 4. 表示（`_build_agreements_context`）

- `evidence_suffix`と同型の`citations_suffix`を追加し、Detector等の監査ノードへ渡す
  コンテキスト文字列にcitationsを反映する。**BL-064（evidenceが「書き込まれるのみで表示に一切
  反映されていなかった」事故）と同型の失敗パターンを最初から回避する**ための必須対応。
- 壊れたJSON（想定外の生データ）が入っていてもクラッシュしないようtry/exceptで防御。

### 5. ツール説明文（`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`）

- 一次ソース優先・最新性・批判的評価の指示を追記（BL-184実装時点の説明文を拡張）。
- 各ノードの巨大なシステムプロンプト文字列（call_expert/call_task_planner/
  call_task_plan_reviewer/generate_user_utterance）を個別に書き換えるのではなく、
  **ツールスキーマの説明文に一元化**した。理由: これらのツールはfunction-calling仕様上、
  対象ノードへ毎回必ず提示される（システムプロンプト本文の長さに関わらず）。4箇所の巨大な
  プロンプト文字列を個別に手で編集するより、一箇所（ツール説明文）に書く方が一貫性を保ちやすく、
  今後のノード追加時にも自動的に付いてくる。

## 見送った項目（今回のスコープ外）

- Detectorのminor/major判定へのcitations欠落チェックの組み込み（ユーザー選択によりプロンプト
  誘導のみ、まず様子見）。
- `verified_facts.confidence` enum（`confirmed`/`provisional`）の変更（AGENTS.md §7の重要定数、
  BL-184時点で既に「変更しない」と確定済み、本BLでも踏襲）。

## 検証

- 新規テスト`tests/test_bl188_citations.py`9件（スキーママイグレーション2件、
  `_write_agreement_impl`のトップレベルcitations永続化2件、confirmed_variables citations
  優先/フォールバック2件、`_build_agreements_context`表示3件）全通過。
- `python -m py_compile cela_main.py web_tools.py`合格。
- 既存オフライン全テストスイート（BL-184配線直後に772件合格を確認済み）に対し、本BLの追加後も
  再実行し無退行を確認する（実行中、結果は別途記録）。

## 実装中のインシデント（記録）

実装中、`agreements`テーブルへの`citations`列追加（`CREATE TABLE`定義と
`_ensure_agreements_citations_column`関数・その呼び出し登録）を行った直後、Edit操作が
「ファイルが最後に読み込んだ時点から外部で変更されている」という警告を返し、実際にこの2箇所の
変更のみが後続の確認時点でファイルから消失していることが判明した（他の同時期の変更は全て
残存していた）。原因は特定できていない（`.clinerules/hooks__/PostToolUse.ps1`は無効化された
Cline用フックであり、Claude Code側の`.claude/settings.json`にはhooks設定自体が存在しないため、
既知のdocs自動コミットフックが直接の原因である可能性は低いと考えられる）。該当2箇所を再適用し、
`grep`によるマーカー総数の突合（`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`の
出現数が定義1件+アタッチ先ノード数と一致することを確認等）とテスト実行で全体の整合性を再確認した。
原因不明の消失が今後も起こりうる前提で、大きな編集作業の後には内容の再グレップ確認を徹底する。
