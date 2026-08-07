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

### 5. ツール説明文（`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`）

- 一次ソース優先・最新性・批判的評価の指示を追記（BL-184実装時点の説明文を拡張）。
- **追記（ユーザー指摘、初回実装時に漏れていた）**: 「必要な情報はweb_searchで能動的に探しに
  行く（記憶からの推測で済ませない）」「新規のweb_search/web_fetch呼び出しの前に、
  `read_reference_file`のkeyword検索でこのrun内の既存キャッシュ（call limitを消費しない）を
  先に確認する」というガイドラインを`WEB_SEARCH_TOOL`/`READ_REFERENCE_FILE_TOOL`の説明文へ
  追加した。

### 6. 各ノードのシステムプロンプト本文への反映（ユーザー指摘、初回実装時に漏れていた）

ツールスキーマの説明文だけでなく、他の既存ツール（`read_verified_fact`/`read_deliverable_file`
等、BL-094のパターン）と同様に、各ノードのシステムプロンプト本文にも「あなたが使えるツールは
...です」という明示的な列挙と、web検索・キャッシュ利用のガイドライン段落を追加した：

- **task_planner/task_plan_reviewer/Expert（軽量プロンプト）**: 番号付き指示として
  「ゴール文にない現実世界の事実が必要なら推測せずweb_searchで調べる」「新規呼び出し前に
  read_reference_fileでこのrun内の既存キャッシュを先に確認する」「web検索結果は一次ソース優先」
  「citationsで引用元を明示する」を追加し、ツール列挙にweb_search/web_fetch/
  read_reference_fileを追記。
- **Detector（両パス）/Reflection/Facilitator**: 「citations付きのweb由来の主張について、
  read_reference_fileでキャッシュ本文を確認し主張との整合性を検証できる（新規のweb検索・取得は
  行わない）」という監査役向けの短い段落を追加し、ツール列挙にread_reference_fileを追記。
  Facilitator・Reflectionはそもそも「あなたが使えるツールは...」という明示列挙自体が
  存在しなかったため、この機会に新設した。

### 7. 実ドライラン（`log/2026-08-07/1047`）でのweb_search未使用の実測、および見つかった実装漏れ

ユーザーが実ドライランログをレビューし、Expertがオペレーター人件費単価（`@3,500円/h`）や
労働基準法の条文番号（`第34条`）を、一切web_searchで裏取りせず学習知識から断定していた実例を
発見した（`log/2026-08-07/1047/log_no_prompt.md:396`等）。`web_search`/`web_fetch`の実行ログは
run全体で0件、`web_cache/`ディレクトリも未作成だった。

原因調査の結果、**BL-188の初回実装（本ドキュメント第5節）には見落としがあった**ことが判明した：
`call_expert`のガイダンス文言は、iter=2以降にのみ使われる`light_system_prompt`側にしか
追加されておらず、iter=1（最初の応答、ツールを呼ぶかどうかを最初に判断するタイミング）に
使われる`system_prompt`（フル版）には、web_search/web_fetch/read_reference_fileへの言及が
一切無かった。ツール自体のdescription（`WEB_SEARCH_TOOL`等）にはガイダンスがあるが、
システムプロンプト本文としての明示的な後押しが、最初の意思決定タイミングに欠落していた。

ユーザーからの指示（「webサーチをするすべてのノードのプロンプトに以下の趣旨を加えてください：
モデルの学習知識から導き出した回答や思考も、学習知識が必ずしも正確であり、最新の情勢を反映して
いるものとは限らない。必ずwebサーチで信頼できる1次情報から確認・裏どりをし、追跡可能な出典や
参考資料を用いて根拠を明示せよ」）を受け、以下を実装した：

- **`call_expert`のフル`system_prompt`（iter=1）**: F-2.6機械的検算ゲートの直後に、
  「学習知識を無検証で断定しない（必須）」という新規ブロックを追加（初回実装時に完全に欠落
  していた箇所）。
- **`call_expert`のlight_system_prompt/`call_task_planner`/`call_task_plan_reviewer`**: 既存の
  BL-188ガイダンス文言を、ユーザー指定の趣旨（学習知識の正確性・最新性への疑い→web検索での
  裏取り→追跡可能な出典の明示）に沿って書き換え・強化した。

**副次的に発見・対応した事項**: `task_plan_reviewer_node`の差し戻し上限（`plan_reviewer_retry_count`
の比較値）が、ユーザーにより手動で2から5へ変更されていたことを確認した（`cela_main.py`の
`task_plan_reviewer_node`内）。関連するコメント3箇所と、この値をハードコードして
いた既存テスト`tests/test_bl087_stage2_task_plan_reviewer_node.py::test_reviewer_gives_up_after_retry_limit_reached`
を新しい上限値（5）に合わせて修正した（ユーザー確認済み）。

**検証**: `python -m py_compile cela_main.py`合格、オフライン全テストスイート777件通過
（`tests/test_f26_detection.py`のみOpenRouter日次クォータ枯渇による既知のflaky除外）。
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
残存していた）。原因はユーザー側の別プロセスによる`cela_main.py`への同時ファイル操作（競合書き込み）
と判明した。該当2箇所を再適用し、`grep`によるマーカー総数の突合（`WEB_SEARCH_TOOL`/
`WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`の出現数が定義1件+アタッチ先ノード数と一致することを
確認等）とテスト実行で全体の整合性を再確認した。同一ファイルへの同時編集が今後も起こりうる前提で、
大きな編集作業の後には内容の再グレップ確認を徹底する。

## 8. PDF読み取り対応、および「検索ばかりで深掘りしない」パターンへの対処（2026-08-07）

ユーザーが実ドライラン`log/2026-08-07/1244`をレビューし、以下2点を指摘した。

**指摘1: web_fetchがPDFを読めない**。政府・自治体・研究機関の一次資料はPDF配布が非常に多い
（`road-to-the-l4.go.jp`、`mlit.go.jp`等）。従来の`web_fetch`はContent-Typeを`text/*`のみに
限定していたため（BL-184時点の設計）、Expertが最も権威ある一次資料（例:
`.../pdf/20240228_theme01.pdf`）へ`web_fetch`した際、`許可されていないContent-Typeです:
'application/pdf'`で拒否されていた（`log/2026-08-07/1244/log_no_prompt.md`の611-612行目）。
ユーザーへ「新規依存（`pypdf`等）が必要になるがBL-184以来の依存ゼロ方針から外れる」と確認したところ、
「これにこだわる必要はありません」との回答を得て実装した。

**指摘2: web_searchを繰り返すばかりで、有望な結果を深掘り（web_fetch）しない**。同ログを詳細に
確認したところ、iter=2の最初の検索で既に複数の高品質な一次情報（`road-to-the-l4.go.jp`の複数ページ、
SOMPOインスティチュートの記事等）がヒットしていたにもかかわらず、Expertはそれらを一切fetchせず、
iter=3〜7で言い回しを変えた検索を5回連続で重ね、iter=8で初めてfetchを試みたがそれがPDFで拒否され、
さらにiter=9〜10で検索を続け、iter=11でようやく最初の成功fetchに至っていた。最終的にはiter=17で
（tool_calls使用16回、うちfetch2回）citations付きの充実した成果物を完成させており「無限ループ」
ではなかったが、fetchに至るまでの検索の重複・非効率は明確な改善対象と判断した。

**実装内容**:

1. **PDF抽出対応**（`web_tools.py`）: `requirements.txt`へ`pypdf`（純Python実装、システム依存
   なし、BL-105/D-086の新規依存追加の先例と同じ「提案→承認→requirements.txt追加→実装」手順）を
   追加。`fetch_and_extract`のContent-Type判定を`text/*`に加えて`application/pdf`も許可し、
   `_extract_pdf_text`（`pypdf.PdfReader`でページ単位に`extract_text()`、改ページで連結、
   先頭50ページ`_MAX_PDF_PAGES`まで）を新設。PDFはバイナリ構造（xrefテーブル等）を持つため
   HTMLと異なりバイト列の途中切り捨てが安全でない（パース自体が失敗しうる）ことを踏まえ、
   サイズ上限超過時は切り捨てずに明示エラーとする設計にした。スキャン画像PDF（OCR要）は
   `extract_text()`が空文字を返すため対象外（見送り、将来必要になれば別途検討）。
2. **「検索ばかりで深掘りしない」への対処**（`WEB_SEARCH_TOOL`説明文）: 「有望な結果が見つかったら
   別の言い回しで検索し直す前にweb_fetchすること」「スニペット10件より、しっかり読み込んだ
   1ページの方が価値が高い」という明示的なアンチパターン警告を追加。強制ロジック（例:
   N回連続search後は自動でfetchを促す機械的介入）は設けず、プロンプト誘導のみとした
   （BL-188全体の「プロンプト誘導のみ、まず様子見」という既定方針を踏襲、Detector等での
   機械的な連続search回数カウントはBL-042の硬直判定の再発リスクがあるため見送り）。

**検証**: 新規テスト4件（`test_fetch_and_extract_extracts_pdf_text`、
`test_fetch_and_extract_rejects_oversized_pdf`、`test_fetch_and_extract_truncates_pdf_to_max_pages`、
既存の`test_fetch_and_extract_rejects_non_text_content_type`を`test_fetch_and_extract_rejects_
non_text_non_pdf_content_type`へ改名・PDFは許可対象になったため`application/octet-stream`で
再検証）を`tests/test_bl184_web_tools.py`へ追加、`pypdf.PdfReader`自体をモックする方式
（実際のPDFバイナリを組み立てず、既存のhttpx.Clientモックと同じ「外部境界を差し替える」方針）を
採用。同ファイル44件全通過、オフライン全テストスイート780件通過（`test_f26_detection.py`は
OpenRouter日次クォータ枯渇による既知のflakyのため除外）、`python -m py_compile`合格。

## 9. web_fetchのページ内リンク一覧対応（2026-08-07）

ユーザーが「web_fetchで特定のページを見ても、ページ内のリンクは表示されない。良い情報がある
ページに入ってもそこから網羅的に情報を集めることはできませんか？」と指摘。`_HtmlTextExtractor`が
`<a href>`のhrefを完全に破棄し本文テキストのみ抽出していたため、良質なインデックスページ
（例: `.../case/`のような一覧ページ）へ到達しても、そこからサブページへ辿る手段がなかった。

**実装内容**:

- `_HtmlTextExtractor`を拡張し、`<a href>`のテキスト＋href（`urljoin`でfetch対象URLを基準に
  絶対URL化）を収集する（`javascript:`/`mailto:`/`tel:`/フラグメントのみ`#`のhrefと、リンク
  テキストが空のものは除外、同一URLは重複排除）。
- `fetch_and_extract`は、本文抽出後（`_MAX_OUTPUT_CHARS`による切り捨て後）に
  `[Links found on this page]`セクションを追記する。上位`_MAX_LINKS_SHOWN`（20）件に限定し、
  超過分は「(...N more links omitted)」と件数のみ表示する（インデックスページ等でのプロンプト
  肥大化を防ぐ）。本文の文字数上限とは別枠で追記するため、本文とリンク一覧が共倒れで切り捨て
  られることはない。
- PDFはリンク抽出の対象外（見送り、`pypdf`でのハイパーリンク抽出は別途調査が必要なため）。
- `WEB_FETCH_TOOL`の説明文へ、リンク一覧の使い方（インデックスページからサブページへのナビゲー
  ション）と、無制限に辿り続けないよう促す注意（「1トピックあたり1〜2階層まで」「run単位の
  呼び出し回数上限はリンク経由のfetchにも同様に適用される」）を追加。機械的な深さ制限は設けず、
  既存のrun単位呼び出し回数上限とプロンプト誘導の組み合わせで対処する（BL-188全体の
  「プロンプト誘導のみ、まず様子見」という既定方針を踏襲）。

**検証**: 新規テスト4件（リンク一覧付記・空/javascriptリンク除外・上位N件への絞り込み・
PDFにはリンクセクションが付かないこと）を`tests/test_bl184_web_tools.py`へ追加、同ファイル48件
全通過。オフライン全テストスイート783件通過（`test_f26_detection.py`除外、
`test_bl168_verified_facts_stale_after_goal_revision.py::test_revise_goal_marking_is_idempotent_
on_repeated_revision`はフルスイート実行時のみ発生する既知のタイミング依存flaky［BL-173の
`shift_id`ミリ秒精度衝突、単体実行では常に通過］であり本変更とは無関係）、`python -m py_compile`
合格。

## 10. Detectorへのweb_search追加、Expert検索義務の強化、Detector根拠実在性チェック（D-160）

ユーザーが実ドライラン`log/2026-08-07/1312`をレビューし、(1) Expertが7回呼ばれ全てweb_search/
web_fetch装備済みだったが一度も使わず、根拠のない前提数値（デマンドタクシー運営費
`@8,000円/日`）で大規模な戦略分析を構築していたこと、(2) それを差し戻したDetectorの反論
（最低賃金法に基づく試算）自体もD-158の設計通りweb_search非搭載のため学習知識のみに依って
いたことを指摘。「①Detectorにもweb_search追加、②Expertの検索義務強化、③Detector監査に
根拠実在性チェックを追加」との指示を受け実装した。

- `call_detector`の両パス（ドメイン監査・数値監査）の`tools=[...]`へ`WEB_SEARCH_TOOL`/
  `WEB_FETCH_TOOL`を追加（D-158で「監査役には新規の外部通信を発生させない」としていた方針の
  一部改訂、D-158側に改訂注記を追加）。
- Detector両パスのプロンプトへ「根拠の実在性チェック」段落を追加：citationsが
  `expert_calculation`/`prior_agreement`のみで外部一次情報の裏付けがなく、Detector自身も
  真偽の確信が持てない前提数値があればweb_searchで検証し、実態と乖離していれば
  constraint_issueの根拠にする、という指示。
- Expertのフル/light system_promptのBL-188ガイダンスへ「【最低限】ゴール文にない数値を
  新たに前提として置く場合、citationsを`expert_calculation`のみで済ませず最低1回は
  web_searchを呼ぶ」という半必須化文言を追加。

機械的な強制ゲート（Detectorのminor/major判定ロジックへの組み込み）は引き続き見送り、
プロンプト強化に留めた（BL-042の硬直化リスク回避）。詳細は`decision_log.md` D-160を参照。

## 11. HTML/PDF抽出をMicrosoft markitdownへ全面置換（D-161）

ユーザーがPDF抽出結果（`log/2026-08-07/1312`）を見て「単純な文字解析だと体裁が崩れ、図もなく
結構厳しい」と指摘し、Microsoft markitdown（PDF/HTML等をMarkdown化するPythonユーティリティ）
の利用を提案。実データ側比較（国交省PDF・RoAD to the L4のHTML）で、markitdownがPDFの表を
Markdownテーブルとして、HTMLを見出し階層・リンクの文脈的位置を保った形で変換できることを
確認した上で、ユーザーが「依存が重くても情報取得の質を優先したい」と判断し、`pypdf`/独自
`_HtmlTextExtractor`をmarkitdownへ全面置換した。詳細は`decision_log.md` D-161を参照
（依存重量の内訳、相対リンク解決の後処理、サイズ上限の安全設計統一等）。

**この置換により不要になった実装**: BL-188セクション9で追加した「ページ末尾への
`[Links found on this page]`リンク一覧付記」機構は、markitdownがリンクを本文中の文脈的
位置に`[text]（url）`形式（Markdownリンク記法）で自然に保持するため撤去した
（より良い形で目的を達成）。
