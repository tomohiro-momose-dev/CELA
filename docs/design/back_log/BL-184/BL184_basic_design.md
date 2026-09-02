# BL-184（予定）: `web_search`/`web_fetch`/`read_reference_file` ツールの新設 基本設計

## Context

直前のセッションで、複数の実ドライラン（08-05〜08-06分）とtask_1_1〜task_6_1の全成果物を監査した結果、CELAは完全にクローズドな世界（ゴール文＋内部の相互参照）だけで動作しており、「50km²のサービスエリアは現実的か」「山間部道路の実際の勾配・冬季速度」「車両単価2,500万円は市場相場と合うか」といった前提が、検証されないまま`provisional`のまま積み上がっていく構造的な弱点が確認された（例: task_1_3が「15%×12km→L≥80km」という物理的矛盾を一度も計算せず素通りした、task_6_1の「片道12km→7-10km」の再設定が幾何学的な推測に留まった等）。

ユーザーはこれを受けて、以下の2つの改善方向を提示した:
1. **制約充足の原文照合**（ゴール文の該当箇所と提案内容を機械的に突き合わせ「言い換え」を検出する仕組み）→ *今回は対象外*。「まだ最終QA層（Integrator/Arbiter/Reviewer）が発火していないので、それを含めて様子を見る」との判断で、今回のスコープからは明示的に除外された。
2. **web検索・ファイルIOの実装**（現実世界の地理・数値を確認しながら計画を進める）→ **本設計のスコープ**。

既存ツール（`python_repl`, `read_verified_fact`, `read_deliverable_file`等）の設計パターン（`TOOL_DISPATCH`辞書・`(args, state)`統一シグネチャ・role非ゲート＝読み取り専用ツールはcaller_role制限なし・resolve-and-contain方式のパス検証・タイムアウト+出力打ち切り）を踏襲する。検索プロバイダは未確定（ユーザー確認済み: 「まだ決めない、Provider抽象化して提案」）のため、具体的なAPIに依存しない抽象化レイヤーで設計する。

## 設計方針（3ツール構成）

Claude Code自身のWebSearch/WebFetch/Readの分離を参考に、役割を3つに分ける:

1. **`web_search(query, max_results=5)`** — 検索エンジンAPIへクエリを投げ、`{title, url, snippet}`のリストを返す。ページ本文は取得しない（軽量・低コスト）。
2. **`web_fetch(url)`** — 指定URLの本文をHTMLから抽出したプレーンテキストとして返す。取得結果は`web_cache/`へ自動キャッシュし、以降の同一URLへの再アクセスはキャッシュから返す（コスト削減・run内の一貫性確保）。
3. **`read_reference_file(path または keyword)`** — `web_cache/`配下（および将来的にユーザーが手動で置くreference資料）を読み取り専用で参照する。`read_deliverable_file`と同じ「resolve-and-contain」方式でパス検証する。

### なぜ3つに分けるか
- `web_search`だけでは本文が読めず、`web_fetch`だけでは何を取得すべきか分からない（既存の`read_project_plan`→`read_deliverable_file`の「一覧→詳細」パターンと同型）。
- `read_reference_file`を独立させることで、Detector等のレビュー系ノードには「新規の外部通信はさせず、Expertが既に取得済みの証跡だけを読ませる」という非対称な権限設計が可能になる（後述）。

## Provider抽象化レイヤー

```python
class WebSearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[dict]:
        """[{'title': str, 'url': str, 'snippet': str}, ...] を返す。失敗時は例外。"""
```

- `get_search_provider()`が環境変数`CELA_WEB_SEARCH_PROVIDER`（既定: `brave`）を見て実装を選択する薄いファクトリ関数。抽象化自体は維持し、Providerを切り替え可能にする。
- **初期実装はDuckDuckGoを選定していたが、実装完了後の実測でBraveへ変更した**（詳細は次項「初期実装プロバイダの変更（2026-08-07）」参照）。DuckDuckGo実装自体はコードとして残し、`CELA_WEB_SEARCH_PROVIDER=duckduckgo`で引き続き選択可能。

### 初期実装プロバイダの変更（2026-08-07）: DuckDuckGo → Brave Search API

`web_tools.py`実装完了後、実際に`html.duckduckgo.com/html/`へ疎通確認したところ、**数回のリクエストだけで即座にBot対策の画像認証チャレンジ**（HTTP 202、`anomaly-modal`／"Unfortunately, bots use DuckDuckGo too."）が返るようになり、5秒後の再試行でも解除されなかった（実測結果は`docs/refs/duckduckgo/html_endpoint_notes.md`の追記を参照）。設計時に想定していた「レート制限・一時ブロックのリスク」は理論上の懸念に留まらず、即時的かつ高頻度に発生する実害であることが判明した。

ユーザーへ報告した上で、(a) 検知して明示エラー化しこのまま進める、(b) 他の無料/低コストProviderへ切り替える、(c) Chromium/ChromeDriverによるブラウザ自動化でGoogle検索を叩く、(d) 今回はweb_search機能を保留する、の4案を提示した。ユーザーが当初(c)を提案したが、AIから「依存関係が一気に重くなる（ブラウザバイナリ100MB超）、Google検索はDuckDuckGo以上に自動化を敵視しておりToS上・技術上のリスクが高い、ブラウザ起動コストが`MAX_TOOL_ITER`を圧迫しかねない」という懸念を説明したところ、ユーザーが**Brave Search API（正式API、無料枠あり）への切り替え**を選択した。

**実装済み**：`BraveSearchProvider`（`https://api.search.brave.com/res/v1/web/search`、ヘッダ`X-Subscription-Token`でAPIキー認証、`web.results[].{title,url,description}`を`{title,url,snippet}`へマッピング）を追加し、`get_search_provider()`の既定値を`brave`へ変更。APIキーは環境変数`CELA_BRAVE_SEARCH_API_KEY`から読み、未設定時は`WebSearchConfigError`で明示エラーを返す。`DuckDuckGoSearchProvider`側にも、Bot対策チャレンジページを検知した場合に空の結果リストではなく明示エラーを返す防御（実測で判明したリスクへの対処）を追加した。API仕様の調査メモは`docs/refs/brave_search/api_notes.md`にsource URL・取得日付きでキャッシュ済み（AGENTS.md §9準拠）。

### DuckDuckGoの実装方式と注意点
DuckDuckGoには公式の検索APIが存在しない（Instant Answer APIは通常のWeb検索結果を返さないため今回の用途には不適）。現実的な選択肢は2つ:

| 方式 | 内容 | 依存パッケージ |
|---|---|---|
| **A. 自前で`html.duckduckgo.com/html/`をHTTP GET＋自前パース（推奨）** | `httpx`でHTML版検索結果ページを取得し、`web_fetch`用に用意する軽量HTMLパーサ（後述）を再利用して`{title, url, snippet}`を抽出 | 追加なし（既存の`httpx`のみ、後述） |
| B. `ddgs`（旧`duckduckgo_search`）パッケージを利用 | 非公式ライブラリがスクレイピング処理をラップ済み | `ddgs`が追加で必要 |

**Aを推奨**: AGENTS.mdの依存追加最小化方針に合致し（`httpx`は既存依存の再利用であり新規追加ですらない、後述）、`web_fetch`向けに実装するHTMLテキスト抽出ロジックを流用できるため実装コストも小さい。ただし以下のリスクは事前に明記しておく:
- 非公式スクレイピングのため、DuckDuckGo側のページ構造変更で**予告なく壊れる可能性**がある（公式APIのようなSLA・後方互換保証はない）。
- 短時間に大量アクセスするとレート制限・一時ブロックを受ける可能性がある → 前述の`max_web_search_calls`上限に加え、**リクエスト間隔（例: 最低1秒）を強制するスロットリング**を実装に含める。
- 利用規約上グレーゾーンである点はユーザーとして認識の上で採用（自動化スクレイピングを明示的に禁止する条項がある点は留意）。
- 将来的にクエリ量が読めてきた場合や信頼性に問題が出た場合は、Provider抽象化により`CELA_WEB_SEARCH_PROVIDER`切り替えのみでTavily等へ移行できる。
- APIキーは環境変数から読み、未設定時は`web_search`ツール自体を「利用不可」として明示エラーを返す（起動時クラッシュではなく、ツール呼び出し時にLLMへ`{"error": "web_search is not configured..."}`を返す — `python_repl`の安全なエラー返却パターンを踏襲）。DuckDuckGo選定時はこの分岐は事実上使われない（キー不要）が、Provider抽象化の一貫性のため維持する。
- **オフラインテストでは`FakeSearchProvider`（固定レスポンスを返すテストダブル）を注入**し、実ネットワーク呼び出しを一切行わない（既存の「実LLM API呼び出しは伴わない」というテスト方針と同型）。
- 実装するProviderは初期はDuckDuckGoの1つのみ。設計上は複数Provider対応だが、実装は選定されたもの1つに限定し、過剰実装を避ける。
- **HTTPメソッド**: `https://html.duckduckgo.com/html/?q=<query>`へのGETリクエスト（`httpx.get(url, params={"q": query}, timeout=10)`）で動作することを公開スクレイピングガイド複数件で確認済み（AGENTS.md §9準拠、調査メモは[`docs/refs/duckduckgo/html_endpoint_notes.md`](../../../refs/duckduckgo/html_endpoint_notes.md)にsource URL・取得日付きでキャッシュ済み）。POST対応は現時点では不要と判断するが、実装時に実レスポンスで動作確認し、GETで結果が得られない場合は同メモを更新の上でPOST対応を追加検討する。

## 安全設計

### `web_search`
- クエリの長さ上限・`max_results`上限（既定5、最大10）をツールスキーマでバリデーション。
- タイムアウト10秒（`httpx.get(..., timeout=10)`）。
- **run単位の呼び出し回数上限**: 新規`LineageState`フィールド`web_search_call_count`を追加し、`config`に`max_web_search_calls`（既定20程度）を設け、超過時はツールがエラー文字列を返す（実APIコスト・レイテンシの上限をMAX_TOOL_ITERと同型の思想で管理）。**この上限は「run全体（全ノード呼び出しの累積）」のカウントであり、`MAX_TOOL_ITER=30`（`cela_main.py:3332`、1回の`query_AI`呼び出し内でのツール往復回数の上限）とはスコープが異なる。両者は数値として単純比較できないが、独立管理のままだと「1回の`call_expert`呼び出し内でweb_search/web_fetchだけを繰り返し呼び、`MAX_TOOL_ITER`を使い切って最終テキスト回答へ到達できなくなる」リスクは残る（BL-014と同種の非収束パターン）。対策として、`web_search`/`web_fetch`の1回の呼び出しコストを`python_repl`と同程度の「軽量な1手」として扱い、同一query_AI呼び出し内での大量連投は`max_web_search_calls`/`max_web_fetch_calls`の値自体を控えめ（既定案20/run全体、後述）にすることで間接的に抑える。将来的に単一呼び出し内での偏重が実ドライランで観測された場合、BL-014と同様の対応（プロンプト指示での抑制）を追加検討する。**
- 結果は`{title, url, snippet}`のみで本文は含めない＝この時点でプロンプト肥大化のリスクは低い。

### `web_fetch`
- **SSRF対策**: スキームは`http`/`https`のみ許可。ホスト名を`socket.gethostbyname`で解決し、`ipaddress`モジュールでprivate/loopback/link-local/multicastレンジを拒否（`localhost`, `127.0.0.1`, `169.254.x.x`, `10.x.x.x`, `192.168.x.x`等）。CELAはローカルマシン上で動くバックエンドから任意URLを取得するため、内部ネットワークへのアクセスを塞ぐことが必須。**DNSリバインディング対策（検証時と実接続時で別IPに解決されるTOCTOU問題）**: `socket.gethostbyname`で解決したIPアドレスを検証後にそのまま接続先として使う（ホスト名を再解決させない）。具体的には、`httpx`のクライアントへカスタムトランスポート、または検証済みIPを直接指定したURLで接続し`Host`ヘッダのみ元のホスト名を送る方式のいずれかを実装時に選定する（詳細実装方式は次段階の実装Plan doc側で確定させる）。
- Content-Typeは`text/html`・`text/plain`に加え、`text/*`全般（`application/xhtml+xml`等の実務上よく返る亜種を含む）を許可する（バイナリ・PDF等は初回スコープ外、将来課題として`issue_backlog.md`へ記録）。
- サイズ上限（例: 2MB）を超えたレスポンスは打ち切り。
- HTML→テキスト変換は**追加の重量級依存を避け、標準ライブラリの`html.parser.HTMLParser`を使った軽量なタグ除去**で実装する（`BeautifulSoup`等の追加は今回見送り、抽出品質が実運用で不十分と判明した場合に改めて依存追加を提案する）。`<script>`/`<style>`タグは、開始タグ検出時から対応する終了タグまでの区間を丸ごと本文抽出の対象外とする（内容を含めるとJS/CSSノイズでプロンプトが肥大化するため、パーサ実装の必須要件として明記する）。
- 出力は`python_repl`と同じ`max_output_bytes`方式で打ち切り（例: 上限15000字、`[Fetch Output truncated]`マーカー付き）。
- **キャッシュ**: 取得成功時、`web_cache/<run_id>/<sha256(url)[:16]>.md`へ、`# Source: {url}\n# Fetched: {ISO日時}\n\n{抽出テキスト}`の形式で書き出す（AGENTS.md §9の「official reference は `docs/refs/<tool>/`へsource URL+fetch date付きで保存」という既存の内部原則と同型のパターン。ただし`web_cache/`はrun単位の実行時証跡でありAGENTS.md §9の"開発時の恒久リファレンス"とは性質が異なるため別ディレクトリとし、`.gitignore`に追加する）。同一URLへの再`web_fetch`はキャッシュを先にチェックし、あればAPI呼び出しをスキップする（コスト削減、かつ同一run内での内容の一貫性を保証）。
- **run単位の呼び出し回数上限**: `web_fetch_call_count` / `max_web_fetch_calls`（既定20程度）。ただしキャッシュヒットはカウントしない。

### `read_reference_file`
- `read_deliverable_file`（`cela_main.py:1221-1226`）と同じ「`Path(...).resolve()` → `relative_to(base_dir)`でコンテインメント検証、範囲外なら拒否」パターンを`web_cache/`ルートに対して適用。**ベースディレクトリは`web_cache/`一本に限定する**（「将来的にユーザーが手動で置くreference資料」への参照は本設計のスコープ外とし、必要になった時点で別のベースディレクトリ・別ツール、または`resolve-and-contain`の許可リスト拡張として改めて設計する。複数ベースディレクトリを最初から許可すると、パス検証ロジックがどのディレクトリ由来かで分岐し複雑化するため、単一ディレクトリに絞ることでシンプルに保つ）。
- **`keyword`検索の仕様**: `path`が指定された場合は`web_cache/<run_id>/`からの相対パスとして解決する。`keyword`が指定された場合は、`web_cache/<run_id>/`配下の各キャッシュファイル先頭の`# Source: {url}`行に対する部分文字列一致で検索し、一致したファイルの内容を返す（複数一致時は一覧を返しpath指定での再取得を促す、`read_verified_fact`のkeyword検索と同型のUX）。これにより、`call_detector`（`read_reference_file`のみアタッチ）が、`citations`に記録されたURLから対応するキャッシュファイルへ`keyword=<URL>`で逆引きできる経路を確保する（Expertが`web_fetch`で取得した証跡を、Detectorが新規の外部通信なしに追跡できることが本ツールの主目的のため、この逆引き経路は必須要件とする）。
- 読み取り専用。書き込みツールは今回設計しない（LLMに任意ファイル書き込みを許可するリスクを避ける — 既存方針でも書き込みは`agreements`/`whiteboard_drafts`等のDB経由に限定されている）。
- 出力は`read_deliverable_file`と同じく`content[:10000]`で打ち切り。

## 権限・アタッチ設計

読み取り専用ツール（既存の`read_verified_fact`等と同様、caller_role制限なし）として、以下のノードに限定してアタッチする（過剰な同時展開を避け、最初は影響範囲を絞る）:

| ノード | アタッチするツール | 理由 |
|---|---|---|
| `call_expert` | `web_search`, `web_fetch`, `read_reference_file` | 仮定値を実際に執筆する主体。今回の監査で発見された「未検証のprovisional値」の大半はExpertの成果物に由来する |
| `call_detector`（ドメイン監査パス） | `read_reference_file`のみ | 新規の外部通信・追加コストは発生させず、Expertが既に取得済みの証跡と成果物の記述が整合しているかだけを検証させる（新規API呼び出しをレビュー側にまで広げるとコストが倍増するため） |

`call_orchestrator`・`task_planner`・User AI等への展開は本設計のスコープ外とし、実運用で効果が確認できてから`issue_backlog.md`へ拡張提案を起票する。

## 既存スキーマとの統合（`verified_facts`/`confirmed_variables`）

- **`confidence`のenum（`confirmed`/`provisional`、`cela_main.py:1371`）は変更しない**（AGENTS.md §7「重要定数の変更は事前承認必須」対象であり、既存のBL-041設計思想と衝突するリスクがあるため今回は触れない）。
- 代わりに、**既存の`citations`フィールド（`verified_facts`テーブル・`confirmed_variables[].citations`、共に既存カラム）をそのまま活用**し、web_fetchで得たURLを`citations`配列へ記録するようExpert向けプロンプトへ指示を追加する。
- Web由来の値は単一情報源への依存であり無条件の`confirmed`昇格はさせない方針とし、`confidence="provisional"`を維持しつつ`citations`でトレーサビリティを持たせる（＝データモデルは無改修、プロンプト指示のみで実現）。
- **既存の`citations`使用箇所との整合**: `_read_verified_fact_handler`周辺（`cela_main.py:2339`）に`citations=[args.get("topic", "")]`という、トピック文字列を`citations`へ格納する既存の使い方が存在する。本設計のURL格納と意味が混在する懸念があるが、`citations`は元々「値の根拠を追跡する自由記述の配列」という設計であり（既存も「トピック名」という文字列を格納しているのみで、URL形式を強制するスキーマ制約は元から無い）、web由来のURLを追加要素として同じ配列に加えることは既存の使い方の延長線上にあり、型としての衝突は無い。ただし読み手が「これはトピック名かURLか」を区別できるよう、web_fetch由来の要素は`f"web:{url}"`のようにプレフィックスを付けて格納する運用をExpert向けプロンプト指示に含める（実装コストを増やさずに曖昧さを解消する）。

## 依存パッケージ

- **新規依存の追加は不要**。`cela_main.py`は既に`httpx`をimportし使用している（`cela_main.py:37`、BL-072/BL-083のリトライ処理で`httpx.RemoteProtocolError`/`httpx.TimeoutException`/`httpx.ReadError`を捕捉済み）。`requests`ではなく既存の`httpx`をそのまま再利用する（`httpx.get(url, params=..., timeout=10)`）。AGENTS.md「Controlled Dependencies」（未インストールパッケージを任意にimportしない）方針に、依存追加そのものを回避することでより厳格に整合する。
- DuckDuckGo実装は自前HTTP+自前パースのため`ddgs`等のスクレイピング専用パッケージも不要。
- DuckDuckGoはAPIキー不要のため、`langgraph-checkpoint-sqlite`（D-086）のようなAPIキー取得待ちは発生せず、依存追加そのものが不要になったことで、設計承認が下り次第すぐに実装着手可能（`requirements.txt`の変更も不要）。

## 実装ファイル

- `cela_main.py`: 新規ツールスキーマ定数（`WEB_SEARCH_TOOL`, `WEB_FETCH_TOOL`, `READ_REFERENCE_FILE_TOOL`）、`TOOL_DISPATCH`への登録、`call_expert`/`call_detector`の`tools=[...]`への追加、`LineageState`への`web_search_call_count`/`web_fetch_call_count`フィールド追加、`AppConfig`への`max_web_search_calls`/`max_web_fetch_calls`追加。
- `web_tools.py`（新規モジュール）: Provider抽象化（`WebSearchProvider` Protocol・`_get_search_provider()`）、SSRF検証（DNSリバインディング対策込み）、HTMLテキスト抽出（`<script>`/`<style>`除去込み）、ハンドラ本体（`_web_search_handler`, `_web_fetch_handler`, `_read_reference_file_handler`）をここに切り出す。`cela_main.py`は約490KBまで肥大化しており、これらのロジックは他ノードのビジネスロジックから独立しているため、新規追加分から別モジュール化を既定方針とする（既存コードの`cela_main.py`集約自体は変更しない、新規追加分のみの切り出し）。
- `requirements.txt`: 変更なし（新規依存が無いため）。
- `.gitignore`: `web_cache/`追加。
- 新規テスト: `tests/test_bl184_web_search_file_io.py`（Provider抽象化のFake差し替え、SSRF拒否ケース、キャッシュヒット時にAPI呼び出しをスキップすること、呼び出し回数上限、read_reference_fileのパス脱出拒否等）。実ネットワーク呼び出しは一切行わない。
- ドキュメント: `docs/design/back_log/BL-184/BL184_basic_design.md`（本設計を実装完了後に原文保存）、`issue_backlog.md`にBL-184起票、`decision_log.md`にD-153（Provider抽象化・依存追加の決定理由）、`decision_lineage.md`に論点136（今回の監査結果からこの設計に至った経緯）。

## 検証方針

1. `python -m py_compile cela_main.py`
2. 新規テスト（Fake Provider・SSRF拒否・キャッシュ・呼び出し上限・パス脱出拒否）が全てオフラインで通ること。
3. 既存の`call_expert`/`call_detector`関連テストが無改修で通ること（ツール追加は`tools=[...]`リストへの追記のみで、既存ロジックには影響しないはず）。
4. フルオフラインスイート実行、無退行確認。
5. 実際のAPIキー確定後、限定的な実ドライランで動作確認（次回以降）。

## 未確定・要ユーザー判断事項（実装着手前に確認）

1. **検索Provider = Brave Search API（正式API、`httpx`のGETリクエスト＋`X-Subscription-Token`認証）で確定**（2026-08-07、ユーザー判断。当初はDuckDuckGoを選定したが実測でBot対策チャレンジに即ブロックされたため変更、詳細は「初期実装プロバイダの変更」節参照）。**利用にはBrave Search APIキーの取得・環境変数`CELA_BRAVE_SEARCH_API_KEY`への設定が必要**（実ドライラン前にユーザー側で対応要）。DuckDuckGo実装は`CELA_WEB_SEARCH_PROVIDER=duckduckgo`で引き続き選択可能。
2. **`web_tools.py`への分割は既定方針として確定**（独立レビューでの推奨を受け、当初の「要ユーザー確認」から方針転換。新規追加分のみを切り出し、既存コードの構成は変更しない）。
3. `max_web_search_calls`/`max_web_fetch_calls`の具体的な上限値、およびDuckDuckGoスロットリング間隔（既定案: 検索20回/run、取得20回/run、リクエスト間隔1秒以上）。
4. `call_orchestrator`等、Expert/Detector以外への展開が必要かどうか（今回は対象外としたが、追加要望があれば設計に含める）。

## 独立レビューによる修正履歴（2026-08-06）

別AI（第三者）によるBL-184基本設計レビューを受け、以下を修正した（実コードで検証済みの指摘のみ反映、詳細は`decision_lineage.md`参照）:

- **依存パッケージ**: `requests`新規追加 → 既存の`httpx`（`cela_main.py:37`で使用中）を再利用する方式へ変更（実コード確認により指摘の正しさを確認）。
- **`read_reference_file`の`keyword`検索仕様**: 未定義だったため、`web_cache/<run_id>/`配下の`# Source: {url}`行への部分一致検索として明記し、Detectorが`citations`のURLから該当キャッシュファイルを逆引きできる経路を確保。
- **`MAX_TOOL_ITER`との整合性**: `MAX_TOOL_ITER=30`（`cela_main.py:3332`）は1回の`query_AI`呼び出し内のツール往復上限であり、`max_web_search_calls`/`max_web_fetch_calls`（既定20/run）はrun全体累積の上限のため、指摘の「40>30」という単純比較は不正確と判断したが、スコープの異なる2つの上限の相互作用については設計に明記していなかった点は妥当な指摘のため、リスクとして追記。
- **DNSリバインディング対策**: SSRF対策節へ追記。
- **`<script>`/`<style>`タグ除去**: HTMLパーサ仕様の必須要件として明記。
- **`read_reference_file`のベースディレクトリ**: `web_cache/`一本に限定する方針を明記（複数ディレクトリ許可はスコープ外）。
- **`citations`フィールドの既存使用箇所との整合**: 実コード確認（`cela_main.py:2339`）により指摘通りトピック文字列を格納する既存パターンを確認。型としての衝突は無いと判断しつつ、`web:`プレフィックスでの区別を追加。
- **Content-Type制限**: `text/html`・`text/plain`に加え`text/*`全般を許可するよう緩和。
- **`web_tools.py`分割**: 「要確認」から「既定方針」へ変更。
- **DuckDuckGoのGET/POST**: AGENTS.md §9に従いWeb調査を実施し、GET+クエリパラメータで動作することを確認（[`docs/refs/duckduckgo/html_endpoint_notes.md`](../../../refs/duckduckgo/html_endpoint_notes.md)）。POST対応は不要と判断。
