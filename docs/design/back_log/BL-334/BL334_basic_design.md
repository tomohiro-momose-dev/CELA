# BL-334: web_fetch/PDFレンダリング/xlsx実務限界の3段階改善（Phase 1〜3）

## Context

本セッションの実ドライランログ監査で、CELAの外部情報取得パイプライン（BL-184/BL-188/BL-200/BL-221）に3つの独立した実害が確認された。いずれも「取得はできているが、取得した情報がLLMにとって実質的に読めない/存在しない」という同型の問題であり、対症療法ではなく構造的な改善が必要と判断した。

1. **JS描画コンテンツの欠落**: `web_tools.fetch_and_extract(url)`（`web_tools.py:431-485`）は素の`httpx.Client().get(url)`による静的HTTP取得のみを行い、`MarkItDown().convert_stream(...)`へ渡す。CAMPFIREのクラウドファンディングページ（`https://camp-fire.jp/projects/926343/view`）で、Deliverableが引用した来場者数等の本文がキャッシュ（`web_cache/c284bd8209951e46.md`、191行）に一切存在しないことをgrepで確認済み。同じURLの`web_search`スニペットには該当テキストが見えており、検索エンジンのクローラーがCELA自身の静的`httpx`取得では見えないコンテンツ（クライアントサイドJS描画）を見ていることを示す。
2. **縦書き日本語表ヘッダのPDF抽出破損／地図PDFの原理的限界**: `web_cache/40d17513c6c29834.md`（警察庁の免許更新統計PDF）で、縦書き表ヘッダの都道府県名が「青森」→「森」「青」の2行に分離、「岩手」→「手」「岩」に分離するなど、pdfminer（markitdownのPDF経路が使用）が縦書き表の読み順を再構成できず完全に無意味な文字列になっている。`web_cache/15ec6faeecea5b45.md`（茅野市バス路線図PDF）では「車山高原」→「車車山山高高原原」の文字重複、`(cid:7165)`のような未マップグリフIDが出現。後者は地図（空間情報）そのものであり、テキスト抽出の質をいくら上げても原理的に意味を持たない。
3. **人間向けレイアウトのExcelがNaNだらけのMarkdownダンプになる**: `log/2026-08-26/2334/log_no_prompt.md:17338+`で、茅野市の年齢別人口xlsx（3ブロック横並び＋装飾ガター列）が1枚のフラットなMarkdown表に変換され、ガター列が全てNaNとして出力される。行列整列自体は壊れていないため、コンバータを変えても（markitdown→pandas等）同じ問題が再発する。必要なのはAIに**プログラム的アクセス**（サンドボックス化`python_repl`内のpandas）を与え、`dropna()`/スライス/フィルタで自分でブロックを切り出させることである。

### ユーザー決定済み事項（前提として扱う）

- **単一BL-334・3 Phase構成**（3つの別BL番号ではない）。`docs/design/back_log/BL-331/BL331_basic_design.md`の形式を踏襲する。
- **Visionモデルは`glm-5.3-flash`**（`cela_main.py:362`の`glm_5_3_flash`定数、`client_openrouter`経由。OpenRouter公式で"native multimodal model"としてtext/image/video入力対応を確認済み。D-162の13ロール変数、`cela_main.py:411-465`、が既に全てこのモデルを指しており新規モデル配線は不要）。`mimo-v2.5`（`cela_main.py:360`、未配線・テキスト生成崩壊の既往歴あり）は使わない。
- **Playwrightは`web_fetch`の既定パス**（オプトインではなく常時有効）。Playwright失敗時のみ既存の`httpx`静的取得へフォールバック。キャッシュがURLキー・グローバル・永続（BL-200）であるため、Playwrightのコストは「URLごとに生涯1回」しか発生しない。これは`docs/design/back_log/BL-184/BL184_basic_design.md`が記録するD-157（Google検索自動化のためのChromium/ChromeDriverをユーザー提案→依存重量・ToS・`MAX_TOOL_ITER`圧迫の懸念からBrave Search APIへ変更）とは異なるリスクプロファイルである：検索クエリは呼ぶたびに変化しキャッシュヒットしないため起動コストを毎回払うが、`web_fetch`はURL単位でキャッシュヒットするため償却される。「一度起動したブラウザプロセスをプロセス生涯にわたって使い回す」設計は`_PythonReplSession`（`cela_main.py:644-732`）の「毎回起動コストを払わない」思想と同型。ページ/コンテキストごとにクローズ、ブラウザ自体は使い回す。
- **PDFラスタライズライブラリはpypdfium2**（BSD/Apache系のクリーンなライセンス、Google PDFiumのバインディング）。PyMuPDF（AGPL-3.0）は不採用。
- **python_replへのpandas追加に伴うSSRF迂回リスクは、REPL子プロセス側で`socket.socket`を無効化して対処**（プロンプト注意書きのみでは不十分と判断）。

---

## 設計

### 1. Phase 1 — Playwright描画フェッチ（既定パス、httpx静的フォールバック）

#### 1.1 ブラウザのライフサイクル・配置場所

`web_tools.py`にモジュールレベルの遅延シングルトンを新設する（`_MARKITDOWN = MarkItDown()`と同型だが、Playwrightは起動/終了APIを持つため遅延初期化にする）：

```python
_PLAYWRIGHT = None            # sync_playwright().start()の戻り値
_BROWSER = None                # Chromium Browserインスタンス（プロセス生涯で1つ）
_PAGES_RENDERED_SINCE_LAUNCH = 0

def _ensure_browser():
    """[BL-334] プロセス生涯で1つのChromiumを起動・使い回す遅延シングルトン。
    _PythonReplSession（cela_main.py）の「起動コストを毎回払わない」思想と同型。"""
    global _PLAYWRIGHT, _BROWSER
    if _BROWSER is not None:
        return _BROWSER
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT = sync_playwright().start()
    _BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
    return _BROWSER

def _shutdown_browser() -> None:
    """[BL-334] atexitフックとテストのteardown両方から呼ぶ。"""
    global _PLAYWRIGHT, _BROWSER
    if _BROWSER is not None:
        try:
            _BROWSER.close()
        except Exception:
            pass
        _BROWSER = None
    if _PLAYWRIGHT is not None:
        try:
            _PLAYWRIGHT.stop()
        except Exception:
            pass
        _PLAYWRIGHT = None

atexit.register(_shutdown_browser)
```

- **メモリリーク対策**: 1つのURLはキャッシュ済みなら二度とPlaywrightを通らないが、初回runで数十〜数百の未キャッシュURLを連続してレンダリングする可能性はある（`max_web_fetch_calls`は既定30〜400/run、実運用では100超の実績あり）。ページ/コンテキストは呼び出しごとにcloseするのが一次防御。加えて`_PAGES_RENDERED_SINCE_LAUNCH`が新規定数`_PLAYWRIGHT_RECYCLE_AFTER_N_PAGES`（提案値50、要ユーザー承認）を超えたらブラウザを再起動する二次防御を入れる。
- 呼び出しごとに新規`BrowserContext`＋`Page`を作成し、`try/finally`で必ずクローズする（永続`Page`を使い回さない）。

#### 1.2 レンダリング手順（HTML→既存`_MARKITDOWN.convert_stream`は不変）

```python
def _fetch_html_via_playwright(url: str) -> str | None:
    """成功時は post-JS HTML文字列。既知の失敗（起動エラー・タイムアウト・クラッシュ）は
    Noneを返しhttpxフォールバックへ委ねる。それ以外の予期しない例外は伝播させる。"""
    from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError
    browser = _ensure_browser()
    context = browser.new_context(user_agent=_USER_AGENT)
    context.route("**/*", _ssrf_route_guard)   # §1.3
    try:
        page = context.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=_PLAYWRIGHT_NAV_TIMEOUT_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=_PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # SPAが継続ポーリングしidleに到達しないページは珍しくない。取れた分で進める。
        # [SSRF] JSリダイレクト等で着地した最終URLも再検証する（httpxのfollow_redirects=Falseと
        # 異なりPlaywrightは透過的にリダイレクトを追うため）。
        validate_url_for_fetch(page.url)
        if response is not None:
            # [Cline手動レビューR4] page.goto()はhttpxのraise_for_status()と異なり4xx/5xxで
            # 例外を投げない。現行契約（resp.raise_for_status()でエラー化）と揃えるため、
            # 非2xxはPlaywright失敗として扱いhttpx経路へフォールスルーする（httpx側が
            # raise_for_status()で従来通りエラー化する）。
            if response.status >= 400:
                return None
            landed_ct = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
            if landed_ct and not landed_ct.startswith("text/html"):
                return None  # 文書系(PDF等)に着地→Playwrightは不適、呼び出し元がhttpx文書経路へ
        html = page.content()
        # [Cline手動レビューR3] 現行httpx経路は_MAX_FETCH_BYTES（web_tools.py:468-471）を
        # convert_stream呼び出し前に必ず適用している。Playwright経路にも同一ルールを
        # 適用しないと、巨大SPAのHTMLがmarkitdownへ無制限に渡ってしまう（AGENTS.md §15.1:
        # 同一ルールは同一箇所の判定に揃える）。
        if len(html.encode("utf-8")) > _MAX_FETCH_BYTES:
            return None  # httpx経路へフォールスルー（httpx側で同じ上限が改めて適用される）
        _PAGES_RENDERED_SINCE_LAUNCH_INCREMENT()
        return html
    except (PlaywrightError, PlaywrightTimeoutError) as e:
        print(f"⚠️ [web_fetch] Playwright描画に失敗、httpx静的フェッチへフォールバック: {e}")
        return None
    finally:
        context.close()
```

- `wait_until`は`domcontentloaded`のみだと非同期描画コンテンツ（CAMPFIREの本文等）を取りこぼす可能性が高いため、追加で`networkidle`をベストエフォート待機する（タイムアウトしても致命的失敗にはしない＝「レンダリング結果がたまたま少ない」ケースを誤ってフォールバックと混同しない）。
- **フォールバックのトリガー条件を明確化**: ブラウザ起動失敗・`page.goto()`タイムアウト・ページクラッシュ（`PlaywrightError`/`PlaywrightTimeoutError`）・HTTPステータス4xx/5xx・サイズ上限超過（`_MAX_FETCH_BYTES`）のみ。コンテンツが短い/少ないことはフォールバック条件に含めない（これら以外の理由で例外が飛ばない限りフォールバックしない）。

#### 1.3 SSRF対策の拡張（新しい攻撃面であることを明記）

既存の`validate_url_for_fetch`（`web_tools.py:384-413`）はナビゲーション前の1回のチェックであり、Playwrightは（a）JSリダイレクト・meta refreshを透過的に追う、（b）ページが読み込むサブリソース（画像・スクリプト・XHR）についても実際にネットワーク接続する、という**httpxパスには存在しなかった新しいSSRF面**を持ち込む。これは`web_tools.py:389-395`が既に許容している「検証後の再解決によるTOCTOU」よりも一段重い懸念（サブリソース越しの内部ネットワーク到達）であり、設計上の新規リスクとして明記し、Cline独立レビューで重点的に検証してもらう。

対策：
1. **ナビゲーション前**: 既存どおり`validate_url_for_fetch(url)`。
2. **`context.route("**/*", handler)`によるリクエスト単位の検証**: 全リクエスト（メインフレームのナビゲーションだけでなく、画像・スクリプト等のサブリソースも含む）に対し`validate_url_for_fetch`相当のチェックをかけ、失敗したものは`route.abort()`する。

```python
def _ssrf_route_guard(route, request) -> None:
    try:
        validate_url_for_fetch(request.url)
    except SsrfBlockedError:
        route.abort()
        return
    route.continue_()
```

コスト（全サブリソースごとにDNS解決＋検証）は懸念だが、`socket.getaddrinfo`はOS/DNSキャッシュにより通常十分高速であり、SSRF対策の完全性を優先する（性能最適化自体は§スコープ外）。
3. **ナビゲーション後**: 最終着地URL（`page.url`）も`validate_url_for_fetch`で再検証する（§1.2内に実装済み、JSリダイレクト対策）。

#### 1.3.5 リダイレクト方針の転換（Cline手動レビューR1、重大指摘・要ユーザー承認）

**指摘**: 現行`fetch_and_extract`は301/302/303/307/308を`SsrfBlockedError`で明示的に拒否しており（`web_tools.py:444-448`）、関数docstring自身が「リダイレクト経由のSSRFバイパスを構造的に防ぐ」ためと理由を明記している。`WEB_FETCH_TOOL`のdescription（`cela_main.py:1255`）にも「Redirects are NOT followed (fetch the redirect target url directly instead)」とLLM向けに明言済み。ところが`page.goto()`はリダイレクトを透過的に追うため、Playwrightが既定パスになると**同じツール・同じdescriptionのまま、経路によってリダイレクト追従の有無が変わる二重動作**になる（AGENTS.md §15.1違反）。

**解決方針（本設計での採用案）**: リダイレクト追従を「許可」する方向へポリシー自体を転換する。§1.3のroute guard（全リクエストのSSRF検証）と最終URL再検証により、リダイレクト追従によるSSRFバイパスは構造的に塞がれたままである一方、http→httpsの正規リダイレクト等を毎回エラーにする現行の実用上の不便を解消できる。**Playwright経路・httpx経路の双方でリダイレクト追従を許可し、httpx側の`follow_redirects=False`＋301/302/303/307/308即エラーの分岐（`web_tools.py:444-448`）を撤去して`follow_redirects=True`へ変更、最終着地URLを`validate_url_for_fetch`で検証する**（Playwright経路と同じ安全策に統一、AGENTS.md §15.1）。

この転換は以下を伴う：
- `WEB_FETCH_TOOL`のdescription文言（`cela_main.py:1255`「Redirects are NOT followed」）を「リダイレクトは追従されるが最終URLもSSRF検証される」旨に更新。
- `decision_log.md`への新規D-xxx記録が必須（既存の明示的設計決定＝BL-184時点でのリダイレクト拒否の理由を覆す変更のため、AGENTS.md §4「決定の理由」の記録対象）。
- 既存テスト（301/302等が`SsrfBlockedError`になることを検証している既存ケース）の更新。

#### 1.4 ルーティング判定（Playwrightを通す/通さないの事前判定）

「Content-Typeを知るには一度リクエストする必要がある」という循環を避けるため、既存の拡張子ヒューリスティック（`_DOCUMENT_EXTENSIONS`、`web_tools.py:74`）をそのまま単一情報源として再利用する（AGENTS.md §15.1、新しい判定基準を増設しない）：

- URLパス末尾拡張子が`_DOCUMENT_EXTENSIONS`（`.pdf,.docx,.xlsx,.xls,.pptx,.epub,.csv`）に該当 → Playwrightを経由せず、既存のhttpxバイト取得経路へ直行（文書はブラウザで「開く」ものではない — ChromiumはPDFを内蔵ビューアで開いてしまい、素のPDFバイト列が取れない）。
- 該当しない場合 → まずPlaywrightを試す。ナビゲーション成功後、レスポンスの`Content-Type`が`text/html`でないと判明した場合（拡張子だけでは判別できない`/download?id=123`のようなURLが実は文書だったケース）は、Playwright結果を破棄し、同じ最終URLに対して既存のhttpx文書取得経路へフォールスルーする（§1.2内で実装済み）。

`fetch_and_extract`は次のように再構成する（既存ロジックを`_fetch_bytes_via_httpx`として抽出、新規に分岐を追加するのみ、`convert_stream`呼び出しは変更しない）：

```python
def fetch_and_extract(url: str) -> str:
    validate_url_for_fetch(url)
    url_extension = Path(urlparse(url).path).suffix.lower()
    if url_extension not in _DOCUMENT_EXTENSIONS:
        html = _fetch_html_via_playwright(url)   # 失敗/非HTML着地時はNone
        if html is not None:
            result = _MARKITDOWN.convert_stream(
                io.BytesIO(html.encode("utf-8")),
                stream_info=StreamInfo(mimetype="text/html", extension=".html"),
                url=url,
            )
            return _finish(result.text_content, url)
        print(f"ℹ️ [web_fetch] Playwright非適用/失敗のためhttpx静的フェッチへ: {url}")
    # 既存の httpx 静的フェッチ + ドキュメント種別判定（変更なし）
    return _fetch_via_httpx_and_convert(url, url_extension)
```

#### 1.5 依存関係

`requirements.txt`へ`playwright`を追加。**`pip install`だけでは完結しない**（Chromiumバイナリの別途取得`playwright install chromium`が必要、約100〜300MB）ことをセットアップ手順として明記する。CI/開発者マシン双方でこの手順が要ることをユーザーへ明示的に確認する。

---

### 2. Phase 2 — PDFページ画像化 → glm-5.3-flash Vision（AIオプトイン）

#### 2.1 ラスタライズライブラリ

**pypdfium2**（ユーザー承認済み）。システムバイナリ不要、インメモリでPNG化できる。API成熟度で不足があればその時点で個別に検討する。

#### 2.2 生バイト列キャッシュ（Phase 2/3共有の前提整備）

**現状のギャップ**: `write_cache`（`web_tools.py:503-509`）はmarkitdown変換後のMarkdownしか保存しない。Phase 2（PDFを画像化して見る）・Phase 3（xlsxをpandasで読む）はどちらも元の生バイト列が必要で、これは両Phaseに共通する前提整備である。

`fetch_and_extract`のhttpx文書取得分岐（`raw = resp.content`取得直後）で、**PDF/xlsx/xlsのみ**（AGENTS.md §15.4「入口を作ったら出口も」— 消費経路がある形式に限定し、docx/pptx/epub/csvは対象外とする）、markitdown変換の成否とは独立に生バイト列を保存する：

```python
_RAW_CACHEABLE_EXTENSIONS = (".pdf", ".xlsx", ".xls")

def raw_cache_file_path(url: str, extension: str) -> Path:
    """[BL-334] cache_file_path()と同じsha256(url)[:16]ハッシュを使い、拡張子だけ差し替える
    （.mdと同じキーで見つけられるようにする、AGENTS.md §15.1）。"""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Path(WEB_CACHE_DIR) / f"{digest}{extension}"

def write_raw_cache(path: Path, raw: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
```

`fetch_and_extract`内、サイズ上限チェック通過後・`convert_stream`呼び出し前に、`url_extension in _RAW_CACHEABLE_EXTENSIONS`なら`write_raw_cache`する（markitdown変換が例外送出しても既に書き込み済みのため、テキスト抽出が完全失敗したPDFでもPhase 2のvisionツールは使える）。

**既存キャッシュ済みURLに対する出口の欠落（Cline手動レビューR2、要対応）**: この生バイト保存は`fetch_and_extract`の実取得経路にしか無く、`web_fetch_handler`は`.md`キャッシュヒット時に実取得自体をスキップする（`web_tools.py:649-679`）。したがって**BL-334適用前に既に`.md`だけキャッシュ済みのPDF/xlsx URLは、再度`web_fetch`してもキャッシュヒットで終わるため兄弟の生バイトファイルが永久に生成されない**。「もう一度fetchすればrawが手に入る」という案内はこのケースで嘘になる（AGENTS.md §15.4: 出口を明示しないまま入口だけ作らない）。

**採用する解決策**: `read_pdf_page_as_image`/Phase 3のREPL読み取りヘルパーは、対応する兄弟の生バイトファイルが存在しない場合、再ダウンロードを試みず**「このPDF/xlsxはBL-334適用前にキャッシュされたため生バイトが無く、画像化/pandas読み込みはできません。再度web_fetchで生成し直すには、キャッシュファイルを手動で削除する必要があります」という恒久的な明示エラー**を返す（軽量案）。生バイトのみの再ダウンロードを許す案は、予算管理・SSRF経路の再考が必要になる重量案のため本BLではスコープ外とする（既存の「スコープ外」節に追記）。この挙動を`_PDF_VISION_USAGE_PARAGRAPH`・`PYTHON_REPL_TOOL`descriptionの両方に明記する。

#### 2.3 新規ツール: `read_pdf_page_as_image`（AIオプトイン）

`web_tools.py`にPDFレンダリングの純粋関数を置く（LLMクライアント非依存、テスト容易、cela_main.pyをimportしない既存方針を維持）:

```python
def render_pdf_page_to_png_bytes(pdf_bytes: bytes, page_number: int, dpi: int = 150) -> bytes:
    """[BL-334] 1-indexed page_number をPNGへレンダリングする（pypdfium2使用）。"""
```

ツールスキーマ・ハンドラ・vision呼び出しはcela_main.py側に置く：

```python
READ_PDF_PAGE_AS_IMAGE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_pdf_page_as_image",
        "description": (
            "[BL-334] Render a specific page of a cached PDF as an image and get a vision-model "
            "transcription/description of it. Use this INSTEAD OF trusting the plain-text extraction "
            "when that text looks broken: single kanji/kana characters split onto separate lines "
            "(vertical Japanese table headers often extract this way, e.g. '青森' becoming two lines "
            "'森'/'青'), doubled/repeated characters (e.g. '車車山山高高原原'), unmapped glyph markers "
            "like '(cid:1234)', or when the page is self-evidently a map/diagram/floorplan (its actual "
            "information cannot be expressed as extracted text at all). Costs vision tokens and consumes "
            "a separate run-scoped call limit -- do not use it as a first resort, only when the text "
            "extraction is demonstrably unusable or the content is inherently spatial. 'path' is the "
            "same .md cache filename returned by web_fetch/read_reference_file for this PDF."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "The .md cache filename for this PDF (from web_fetch/read_reference_file)."},
                "page_number": {"type": "integer", "description": "1-indexed page number to render."},
                "page_count": {"type": "integer", "description": "Optional: render this many consecutive pages (max _MAX_PDF_VISION_PAGES_PER_CALL, default 1)."},
            },
            "required": ["path", "page_number"],
        },
    },
}
```

TOOL_DISPATCHエントリ・ハンドラ（`_trace_lineage_handler`等と同じ配置規約）:

```python
def _read_pdf_page_as_image_handler(args: dict, state: dict) -> dict:
    # 1. path→sibling .pdf のresolve-and-contain解決（web_tools.WEB_CACHE_DIR基準）
    # 2. state["pdf_vision_call_count"] / config["max_pdf_vision_calls"] のrun単位上限チェック
    #    （キャッシュヒットは上限を消費しない、web_fetch_handlerと同型）
    # 3. web_tools.pdf_vision_cache_file_path(hash, page)にヒットすればそれを返す
    # 4. web_tools.render_pdf_page_to_png_bytes(...) → base64 → 単発の
    #    client_openrouter.chat.completions.create(model=glm_5_3_flash, messages=[
    #        {"role": "user", "content": [
    #            {"type": "text", "text": _PDF_VISION_PROMPT},
    #            {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}},
    #        ]}
    #    ], timeout=_PDF_VISION_API_TIMEOUT_SECONDS)
    # 5. 成功: web_cacheへ書き込み、カウンタ加算、{"page_number":N,"description":text}を返す
    # 6. 失敗: {"status":"error","message":...}（カウンタ・キャッシュは変更しない、リトライ可能に）
```

**このハンドラはTOOL_DISPATCH中で唯一自らLLM API呼び出しを行う**（他の全ハンドラはDB/ファイルIOのみ）。この非対称性をコード上の目立つコメントとして明記する。

**専用の軽量Vision呼び出しヘルパー**: `_query_AI_live`（`cela_main.py:6439-`）は全13+ノードが共有する文字列content専用のホットパスであり、multipart contentを通すために手を入れるとリグレッションリスクが高い。よって`_query_AI_live`は一切変更せず、`_read_pdf_page_as_image_handler`内で`client_openrouter.chat.completions.create(...)`を直接、非ストリーミング・**リトライ/バックオフ/反復ガードなしの単発呼び出し**として行う（オプトイン・低頻度な呼び出しであり、失敗時は通常のツールエラーとしてLLMへ返しLLM自身の予算内でリトライさせる方が`_query_AI_live`の`while True`無限リトライループより安全）。この「リトライなし」というトレードオフは明示的にユーザー確認が必要な設計判断としてフラグする。

#### 2.4 呼び出し先ノード・使用ガイダンス

現在`web_fetch`が付いている3ノード（`_task_planner_tools`＝`cela_main.py:12432`、`_expert_tools`＝`cela_main.py:13287`【WEB_FETCH_TOOL/PYTHON_REPL_TOOL保有を実コードで確認済み】、`_task_plan_reviewer_tools`＝`cela_main.py:17150`）へ`READ_PDF_PAGE_AS_IMAGE_TOOL`を追加する。`_TRACE_LINEAGE_USAGE_PARAGRAPH`（`cela_main.py:11667-11681`）と同じ共有段落パターンで`_PDF_VISION_USAGE_PARAGRAPH`を新設し、上記3ノードのプロンプト構築箇所へ注入する（トリガー条件をユーザーの実例＝青森/岩手の分離、車山高原の重複、`(cid:7165)`をそのまま例示に使う）。

#### 2.5 ガードレール・キャッシュ

- 新規`max_pdf_vision_calls`（AppConfig/LineageState/`_RUNTIME_TOOL_LIMIT_KEYS`/`_resume_config_overrides_from`— `max_web_fetch_calls`が触っている箇所と同じ配線）。既定値は要ユーザー承認（提案: 10〜20/run、vision token単価が高いため`max_web_fetch_calls`より小さく）。
- `_MAX_PDF_VISION_PAGES_PER_CALL`（提案3）、レンダリングDPI（提案150）、Vision API単発タイムアウト秒（提案60）——いずれもAGENTS.md §7の承認対象として明記。
- キャッシュ: `pdf_vision_cache_file_path(url, page_number)`を新設し、`web_tools.write_cache`/`strip_cache_header`をそのまま再利用（ヘッダ形式互換、AGENTS.md §15.1）。キャッシュヒットは`max_pdf_vision_calls`を消費しない（`web_fetch`と同型）。

---

### 3. Phase 3 — `python_repl`内のpandasアクセス

#### 3.1 `requirements.txt`追加

`pandas`、`openpyxl`（`pandas.read_excel(engine="openpyxl")`のエンジン用、openpyxl自体をLLM側コードが`import`する必要はない — pandas内部が呼ぶため、`_ALLOWED_IMPORTS`には追加不要）。既存2行がunpinnedであることに合わせ本BLもunpinnedを提案するが、pin/unpinどちらにするかは実装時にユーザー確認を仰ぐ。

#### 3.2 `_ALLOWED_IMPORTS`（`cela_main.py:549-552`）拡張

`"pandas"`と`"io"`を追加する（`io`は`pd.read_excel(io.BytesIO(...))`に必須、現行セットに含まれていないことを実コードで確認済み。openpyxlは追加不要）。

**この拡張が既存の設計不変条件を破ることを明記**: `_ALLOWED_IMPORTS`直前のコメント（`cela_main.py:546-548`）は「いずれもI/O・ファイルシステム・OS・ネットワークアクセスを一切持たない純粋計算・データ構造ユーティリティであり、既存のサブプロセス分離＋AST危険呼び出し検査のサンドボックス境界を拡張しない」と明記しており、過去の全追加（BL-058のitertools等、D-007のdecimal/fractions）はこの条件を満たすことで正当化されてきた。pandasはこの条件を破る初めての追加であり、`pd.read_excel(url)`等でURLを直接読めてしまうため、`validate_url_for_fetch`のSSRFチェック・`max_web_fetch_calls`予算管理のいずれも経由しない新しいネットワーク到達経路になる。

**対策（ユーザー承認済み）**: REPL子プロセス側（信頼済みのブートストラップスクリプト内）で`socket.socket`を常にOSErrorを送出するダミーへ差し替える。pandasが内部で使うurllib3/requests/fsspec等のHTTPライブラリは最終的にすべて`socket.socket(...)`を経由するため、個別ライブラリを追いかけずに1箇所で遮断できる。`read_cached_bytes`（§3.3）は純ローカルファイルIOのみで`socket`を使わないため影響を受けない。

```python
# ブートストラップ内、execループに入る前:
import socket as _socket_module

class _NetworkDisabledSocket:
    def __init__(self, *args, **kwargs):
        raise OSError("[BL-334] Network access is disabled inside the python_repl sandbox. "
                      "Use read_cached_bytes(path) to read files from web_cache/ instead.")

_socket_module.socket = _NetworkDisabledSocket
```

#### 3.3 スコープドファイル読み取りヘルパー

`_REPL_SESSION_BOOTSTRAP`（`cela_main.py:625-641`）へ、`read_reference_file_handler`（`web_tools.py:714-721`）と同じresolve-and-containパターンの関数を注入する。**`open()`禁止（`_DANGEROUS_NAMES`、`cela_main.py:555-558`）はLLMが送信する`code`文字列にのみAST検査で適用され**（`_check_repl_code_safety`は`_run_python_repl`/`_PythonReplSession.run()`の両方でLLM由来コードにのみ呼ばれる）、ブートストラップ自体は信頼済みの固定ソースなので`open()`/`Path.read_bytes()`を自由に使ってよい——この非対称性を設計書上・コード上のコメントで明記する（一見矛盾に見えるため）。

```python
_REPL_SESSION_BOOTSTRAP = f"""
import sys, json, traceback, socket as _socket_module
from pathlib import Path

class _NetworkDisabledSocket:
    def __init__(self, *args, **kwargs):
        raise OSError("[BL-334] Network access is disabled inside the python_repl sandbox. "
                      "Use read_cached_bytes(path) to read files from web_cache/ instead.")
_socket_module.socket = _NetworkDisabledSocket

_WEB_CACHE_BASE_DIR = Path({{web_cache_dir!r}}).resolve()

def read_cached_bytes(path):
    # [BL-334] web_cache/配下のみ読める限定ファイルIO。read_reference_file_handler
    # （web_tools.py）と同じresolve-and-containパターン。open()自体は禁止のまま、
    # この1関数だけがLLM生成コードから呼べる例外。パス脱出はValueErrorとして
    # 通常のREPLランタイムエラーと同様にtracebackで可視化される。
    resolved = (_WEB_CACHE_BASE_DIR / path).resolve()
    resolved.relative_to(_WEB_CACHE_BASE_DIR)
    return resolved.read_bytes()

ns = {{"read_cached_bytes": read_cached_bytes}}
while True:
    line = sys.stdin.readline()
    ...  # 既存ループ本体は不変
"""
```

子プロセスの作業ディレクトリは`Popen`に`cwd=`を渡していないため親（`cela_main.py`実行時のcwd）を継承する前提（両呼び出し箇所とも確認済み、`-I`isolatedモードはこの継承に影響しない）——この前提を崩さないことを実装上の不変条件として明記する。

`PYTHON_REPL_TOOL`の`description`（`cela_main.py:739-766`付近）に`read_cached_bytes(path)`の存在・pandas利用例・`.xlsx`ファイル名が`.md`と同じハッシュの姉妹ファイルであることを追記する。同時に、既存の「no network/IO」という趣旨の記述はネットワーク遮断（socket無効化）により実質的に維持されるが、ファイルIOについては`read_cached_bytes`という限定的な例外が生まれるため文言更新が必要（`test_bl252_tool_schema_documents_pipe_or_syntax`のような文字列アサーションテストとの整合を要確認）。

#### 3.4 `subprocess.Popen(["python", ...])`のPATH解決

`_run_python_repl`（`cela_main.py:613`）・`_PythonReplSession._ensure_started`（`cela_main.py:662`）とも`"python"`をPATH解決に頼っており、`cela_main.py`自身を動かしている`sys.executable`と一致する保証がない。従来はstdlibのみのため問題が顕在化しなかったが、pandas/openpyxlは`sys.executable`側のvenvにインストールされる想定であり、PATH上の`"python"`が別インタプリタだと`ImportError`になる。両箇所を`sys.executable`へ変更する。

---

## スコープ外（本BLでは対応しない）

- Phase 1: Playwright経由のサブリソースSSRF検証（`context.route`）の性能影響の最適化（初回実装ではDNS解決コストを許容し、実測後にキャッシュ等の最適化を別BLで検討）。
- Phase 1: 複数タブ/並行fetchのスレッドセーフ化（現状のツール呼び出しループが逐次実行である前提に乗る。真の並行実行が必要になった場合は別途ロック機構が要る）。
- Phase 2: PDF以外（docx/pptx/epub）の画像化。将来、同種の抽出破損が実測された場合に別BLで検討。
- Phase 2: 動画/音声等、markitdownの他の未配線コンバータ（既存スコープ外のまま）。
- Phase 3: `_ALLOWED_IMPORTS`へのopenpyxl直接追加（pandas内部呼び出しのみで足りるため不要と結論、再検討の必要が生じたら別途）。
- 3 Phaseいずれも: 既存run群への遡及適用（過去のキャッシュ済み`.md`に対する再fetch/再rasterize等のバックフィル）は対象外。
- Phase 2/3: BL-334適用前にキャッシュ済み（`.md`のみ・兄弟の生バイトファイル無し）のPDF/xlsx URLに対する生バイトのみの再ダウンロード救済（Cline手動レビューR2の重量案）。恒久的な明示エラーで対応する軽量案を採用（§2.2参照）。

---

## テスト方針（§17.1）

**Phase 1（`tests/test_bl334_playwright_fetch.py`新設）**
1. `web_tools._ensure_browser`/`sync_playwright`をmonkeypatchで完全に差し替え、テストで実ブラウザを一切起動しない。
2. `.pdf`等の`_DOCUMENT_EXTENSIONS`URLはPlaywrightに一切触れず既存httpx経路へ直行すること。
3. Playwright成功（HTML返却）→`_MARKITDOWN.convert_stream`が呼ばれ、既存のリンク解決・切り詰め処理が変わらず適用されること。
4. Playwrightナビゲーション例外（`PlaywrightTimeoutError`等をraiseするフェイク）→httpxフォールバックへ切り替わり、`fetch_and_extract`の最終結果はhttpx経路の値になること。
5. 「レンダリング結果が短い/空だが例外は出ていない」ケースではフォールバックが発生しないこと（誤診断防止の直接テスト）。
6. `context.route`ガード: 検証NGなURL（プライベートIP解決させるフェイクDNS）へのサブリソースリクエストが`route.abort()`されること。
7. Playwright着地後の最終URL（`page.url`）がSSRF検証NGなら例外化されること。
8. 着地レスポンスの`Content-Type`が`text/html`でない場合、Playwright結果を破棄しhttpx文書経路へフォールスルーすること。
9. **[Cline手動レビューR1]** リダイレクト方針転換後: httpx経路が`follow_redirects=True`で301/302等を追従し、最終着地URLが`validate_url_for_fetch`で検証されること（従来の「301/302は即`SsrfBlockedError`」という既存テストは新方針に合わせて更新）。プライベートIPへのリダイレクトはブロックされること。
10. **[Cline手動レビューR3]** Playwright経由のHTMLが`_MAX_FETCH_BYTES`を超える場合、httpx経路へフォールスルーすること（巨大SPA HTMLの模擬データで検証）。
11. **[Cline手動レビューR4]** `page.goto()`の応答が4xx/5xxの場合、Playwright結果を破棄しhttpx経路へフォールスルーし、httpx側の`raise_for_status()`で従来通りエラー化されること。
12. **[Cline手動レビューR2]** BL-334適用前にキャッシュ済み（`.md`のみ、兄弟の生バイトファイル無し）のPDF URLに対し`read_pdf_page_as_image`を呼ぶと、再ダウンロードせず恒久的な明示エラーを返すこと（`tests/test_bl334_pdf_vision.py`側に配置）。
13. 各項目を個別にrevertし、対応するテストが失敗することを確認した上で復元する。

**Phase 2（`tests/test_bl334_pdf_vision.py`新設、実PDFフィクスチャが必要）**
1. 最小限の有効なPDFバイト列を新規フィクスチャとして用意し、`render_pdf_page_to_png_bytes`が実際にPNGバイト列を返すことを検証（実PDFパースを伴う初のテスト）。
2. `client_openrouter.chat.completions.create`をmonkeypatchし、実API呼び出しなしで`_read_pdf_page_as_image_handler`のフルパスを検証。
3. `max_pdf_vision_calls`上限到達時のエラー化、キャッシュヒット時に上限を消費せずAPI呼び出しをスキップすること。
4. `path`引数のresolve-and-contain脱出拒否（`web_tools.py`の既存パターンと同じ攻撃ベクタで検証）。
5. 生バイト列キャッシュ（`write_raw_cache`）: markitdown変換が例外を送出しても`.pdf`ファイルが書き込み済みであること。
6. Vision API呼び出し失敗時、カウンタ・キャッシュとも変更されず`{"status":"error"}`が返ること。

**Phase 3（`tests/test_bl334_repl_pandas.py`新設、実xlsxフィクスチャが必要）**
1. `openpyxl.Workbook()`で最小xlsxバイト列を生成し`web_cache/`に配置、`read_cached_bytes`経由で`pandas.read_excel`が実際に読めることをサブプロセス経由（`_PythonReplSession`実運用相当）で検証。
2. `read_cached_bytes`のパス脱出拒否（`../`等）。
3. `_ALLOWED_IMPORTS`に`pandas`/`io`が追加され、それ以外の未許可importは従来通り拒否されること（`_check_repl_code_safety`の既存テストとの非退行）。
4. `open()`は引き続き拒否されること（`read_cached_bytes`以外の経路でファイルを読めないことの回帰確認）。
5. **`socket.socket`無効化の直接検証**: REPL内で`socket.socket()`の生成・`pd.read_csv("http://...")`のようなURL読み込みが`OSError`で拒否されること（本Phaseの中核的安全対策のため必須テスト）。
6. `sys.executable`変更後も既存の`math`/`statistics`等の検算テストが非退行であること。
7. 各項目を個別にrevertし、対応するテストが失敗することを確認した上で復元する。

**共通**
- `python -m py_compile cela_main.py web_tools.py`
- 既存`tests/test_bl184_web_tools.py`の非退行確認（モック境界の変更が既存アサーションを壊していないか）。
- ツールスキーマ説明文の文字列アサーションテスト（`test_bl252_tool_schema_documents_pipe_or_syntax`等）の更新漏れがないか全数確認。
- フルオフラインスイート実行。

---

## Critical Files

- `web_tools.py`:
  - `fetch_and_extract`（`web_tools.py:431-485`）: Playwright分岐・ルーティング判定・生バイト列キャッシュ書き込みの追加。
  - 新規: `_ensure_browser`/`_shutdown_browser`/`_fetch_html_via_playwright`/`_ssrf_route_guard`（Phase 1）、`render_pdf_page_to_png_bytes`/`raw_cache_file_path`/`write_raw_cache`/`pdf_vision_cache_file_path`（Phase 2/3共有）。
  - `validate_url_for_fetch`（`web_tools.py:384-413`）: 変更なし・再利用のみ（Playwright着地URL・サブリソースの両方から呼ぶ）。
- `cela_main.py`:
  - `WEB_FETCH_TOOL`（`1234-1269`）: 説明文更新（Playwrightが既定になった旨）。
  - 新規`READ_PDF_PAGE_AS_IMAGE_TOOL`・`_read_pdf_page_as_image_handler`・`TOOL_DISPATCH`エントリ・`_task_planner_tools`/`_expert_tools`/`_task_plan_reviewer_tools`への追加（`12432`/`13287`/`17150`）。
  - `_TRACE_LINEAGE_USAGE_PARAGRAPH`と同型の新規`_PDF_VISION_USAGE_PARAGRAPH`・注入箇所。
  - `_ALLOWED_IMPORTS`/`_DANGEROUS_NAMES`/`_check_repl_code_safety`（`549-591`）: `pandas`/`io`追加。
  - `_REPL_SESSION_BOOTSTRAP`/`_PythonReplSession`（`624-732`）: `read_cached_bytes`注入、`socket.socket`無効化、`sys.executable`化。
  - `PYTHON_REPL_TOOL`説明文更新。
  - `LineageState`/`AppConfig`/`_RUNTIME_TOOL_LIMIT_KEYS`/`_resume_config_overrides_from`: `max_pdf_vision_calls`追加。
- `requirements.txt`: `playwright`・`pandas`・`openpyxl`・`pypdfium2`追加、`playwright install chromium`のセットアップ手順注記。
- `tests/test_bl334_playwright_fetch.py`・`tests/test_bl334_pdf_vision.py`・`tests/test_bl334_repl_pandas.py`（いずれも新規）。
- `docs/design/back_log/BL-334/BL334_basic_design.md`（本計画を保存）。

### 実装着手前にユーザー判断が必要な未確定事項（一覧）

0. **【最重要】リダイレクト追従ポリシーの転換**（Cline手動レビューR1）: 現行の「リダイレクト非追従」という明示的設計決定（BL-184、`web_tools.py:444-448`）を「追従する（SSRF安全策付き）」へ転換する（§1.3.5）。既存のdescription文言・decision_log記録・既存テストの更新を伴う、本BL中で最も影響範囲の広い方針変更。
1. Playwrightサブリソースまで含めたSSRF route guardの採用（性能とのトレードオフ、上記§1.3で完全性優先の方針を提案）。
2. 新規数値定数群（AGENTS.md §7対象）: `_PLAYWRIGHT_NAV_TIMEOUT_MS`/`_PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS`/`_PLAYWRIGHT_RECYCLE_AFTER_N_PAGES`/`max_pdf_vision_calls`/`_MAX_PDF_VISION_PAGES_PER_CALL`/PDFレンダリングDPI/Vision API単発タイムアウト。
3. `requirements.txt`新規4依存（playwright/pandas/openpyxl/pypdfium2）のバージョンpin方針。
4. Vision呼び出しヘルパーをリトライなし単発呼び出しとする設計判断の是非。

## 独立レビュー所見（自動Cline §19.1レビューは実行環境の不調で完走せず省略、ユーザー自身が手動でCline相当のレビューを実施——`docs/design/back_log/BL-334/BL334_review.md`）

自動`scripts/cline_review.py`はモデル・ハブ再起動を変えても4回連続でタイムアウトしたため、ユーザー了承のもと自動実行は省略。代わりにユーザーが計画書をCline（相当）へ手動投入しレビューさせ、その結果を`docs/design/back_log/BL-334/BL334_review.md`として保存した。指摘4件（R1〜R4）はいずれも実コードと突き合わせ確認済み（§16.2）で、上記の設計本文へ全て反映済み——R1（リダイレクト方針転換）・R2（既存キャッシュ済みURLの生バイト欠落への恒久エラー対応）・R3（Playwright経路へのサイズ上限チェック追加）・R4（4xx/5xxのフォールスルー）。「0. 検証済み事実」節（同レビューファイル内）で計画の全ファイル:行番号主張・実データ証拠主張も実コードと突合済みであることが確認されている。

さらに私自身のセルフレビューとして以下3点を追加で反映する：

1. **`read_pdf_page_as_image`の`page_number`引数の防御的検証が未記載**: AGENTS.md §13（LLM出力は型・範囲とも信頼しない）に従い、ハンドラ内で`page_number`が1以上・実際のPDFページ数以下であることを検証し、範囲外は明示エラーで返す（黙って1ページ目にフォールバック等はしない）処理を`_read_pdf_page_as_image_handler`の設計に追記する。
2. **`socket.socket`無効化がpandasの内部HTTP経路に実効するかは実装時テストが唯一の保証**: `socket.socket`をモジュール属性として差し替える方式は、対象ライブラリが`import socket; socket.socket(...)`という属性参照呼び出しをしていれば効くが、`from socket import socket as X`のように差し替え前の参照を保持している経路があれば迂回されうる。理論的な保証ではなくPhase 3テスト項目5（`pd.read_csv("http://...")`が実際にOSErrorになることの直接検証）の合格をもって初めて有効性を確認したとみなす、という位置づけを設計書上に明記する。
3. **Playwright常設化による既存の正常系フェッチへの回帰リスク**: 一部サイトはCookie同意バナー・Accept-Language・素のUser-Agent文字列等、httpxの単純GETとPlaywrightのブラウザコンテキストとで応答が変わりうる（例: 言語切替・地域別コンテンツ）。本Phase 1は「失敗（例外）時のみフォールバック」という設計のため、こうした**応答内容の差異は例外を伴わずPlaywright経由の結果がそのまま採用される**——これが改善なのか劣化なのかはURLに依存する。スコープ外の性能最適化とは別に、ロールアウト後の実ドライランで既存run群と比較し異常が無いか監視することを実装後の手順に追加する。

## 実装後の手順

- AGENTS.md §19.4（diff-based独立レビュー）を実施し、指摘を実コードで検証の上反映。
- `issue_backlog.md`（BL-334節を`open`→`done`）を更新。
- ロールアウト後、既存の正常系フェッチ（httpx時代に問題なく取得できていたURL）に対しPlaywright経由での応答内容差異が無いか、直近のドライランログで確認する（上記所見3）。
