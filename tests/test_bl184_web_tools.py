"""
BL-184: web_tools.py（web_search/web_fetch/read_reference_file）の単体テスト。
実ネットワーク呼び出しは一切行わない（httpx呼び出しはmonkeypatchで差し替える）。

DuckDuckGo HTML版のパーサ検証用サンプルは、実際に`https://html.duckduckgo.com/html/`へ
`httpx.get(url, params={"q": "python programming language"})`でアクセスして得られた
実レスポンス（2026-08-06確認）のマークアップ構造を基にしている
（docs/refs/duckduckgo/html_endpoint_notes.md参照）。

参照: docs/design/back_log/BL-184/BL184_basic_design.md、issue_backlog.md BL-184。
"""

import inspect
import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402
import web_tools  # noqa: E402

# 実際のhtml.duckduckgo.com/html/レスポンスから採取した1件分のマークアップ（簡略化）。
_SAMPLE_DDG_HTML = """
<div class="result results_links results_links_deep web-result ">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F&amp;rut=abc">Welcome to Python.org</a>
    </h2>
    <div class="result__extras">
      <div class="result__extras__url">
        <a class="result__url" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F&amp;rut=abc">www.python.org</a>
      </div>
    </div>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F&amp;rut=abc">The mission of the <b>Python</b> Software Foundation is to promote <b>Python</b>.</a>
    <div class="clear"></div>
  </div>
</div>
<div class="result results_links results_links_deep web-result ">
  <div class="links_main links_deep result__body">
    <h2 class="result__title">
      <a rel="nofollow" class="result__a" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F&amp;rut=def">Python Docs</a>
    </h2>
    <a class="result__snippet" href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fdocs.python.org%2F&amp;rut=def">Official documentation.</a>
    <div class="clear"></div>
  </div>
</div>
"""


# ---------------------------------------------------------------------------
# _extract_real_url
# ---------------------------------------------------------------------------

def test_extract_real_url_decodes_uddg_redirect():
    href = "//duckduckgo.com/l/?uddg=https%3A%2F%2Fwww.python.org%2F&rut=abc"
    assert web_tools._extract_real_url(href) == "https://www.python.org/"


def test_extract_real_url_passes_through_direct_link():
    assert web_tools._extract_real_url("https://example.com/page") == "https://example.com/page"


def test_extract_real_url_empty_returns_empty():
    assert web_tools._extract_real_url("") == ""


# ---------------------------------------------------------------------------
# _DdgHtmlParser（実レスポンス由来のマークアップで検証）
# ---------------------------------------------------------------------------

def test_ddg_parser_extracts_two_results_from_sample_markup():
    parser = web_tools._DdgHtmlParser()
    parser.feed(_SAMPLE_DDG_HTML)
    parser.close()
    assert len(parser.results) == 2
    assert parser.results[0]["title"].strip() == "Welcome to Python.org"
    assert "python.org" in parser.results[0]["url"]
    assert "Python" in parser.results[0]["snippet"]
    assert parser.results[1]["title"].strip() == "Python Docs"


def test_ddg_parser_handles_empty_html():
    parser = web_tools._DdgHtmlParser()
    parser.feed("<html><body>no results</body></html>")
    parser.close()
    assert parser.results == []


# ---------------------------------------------------------------------------
# DuckDuckGoSearchProvider / get_search_provider
# ---------------------------------------------------------------------------

def test_duckduckgo_provider_search_parses_and_limits_results(monkeypatch):
    class _FakeResponse:
        text = _SAMPLE_DDG_HTML
        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_tools, "_last_ddg_request_at", 0.0)
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        return _FakeResponse()

    monkeypatch.setattr(web_tools.httpx, "get", fake_get)
    provider = web_tools.DuckDuckGoSearchProvider()
    results = provider.search("python programming language", max_results=1)

    assert captured["url"] == "https://html.duckduckgo.com/html/"
    assert captured["params"] == {"q": "python programming language"}
    assert len(results) == 1
    assert results[0]["title"] == "Welcome to Python.org"
    assert results[0]["url"] == "https://www.python.org/"


def test_get_search_provider_defaults_to_brave(monkeypatch):
    monkeypatch.delenv("CELA_WEB_SEARCH_PROVIDER", raising=False)
    provider = web_tools.get_search_provider()
    assert isinstance(provider, web_tools.BraveSearchProvider)


def test_get_search_provider_can_select_duckduckgo(monkeypatch):
    monkeypatch.setenv("CELA_WEB_SEARCH_PROVIDER", "duckduckgo")
    provider = web_tools.get_search_provider()
    assert isinstance(provider, web_tools.DuckDuckGoSearchProvider)


def test_get_search_provider_rejects_unknown_provider(monkeypatch):
    monkeypatch.setenv("CELA_WEB_SEARCH_PROVIDER", "tavily")
    with pytest.raises(web_tools.WebSearchConfigError):
        web_tools.get_search_provider()


def test_ddg_provider_search_raises_on_anomaly_challenge(monkeypatch):
    """[BL-184] 実測（2026-08-07）で確認したBot対策チャレンジページを検知した場合、
    空の結果リストではなく明示的なエラーを送出すること。"""
    class _FakeBlockedResponse:
        text = '<div class="anomaly-modal__title">Unfortunately, bots use DuckDuckGo too.</div>'
        def raise_for_status(self):
            pass

    monkeypatch.setattr(web_tools, "_last_ddg_request_at", 0.0)
    monkeypatch.setattr(web_tools.httpx, "get", lambda *a, **kw: _FakeBlockedResponse())
    provider = web_tools.DuckDuckGoSearchProvider()
    with pytest.raises(web_tools.WebSearchConfigError):
        provider.search("query", max_results=5)


# ---------------------------------------------------------------------------
# BraveSearchProvider
# ---------------------------------------------------------------------------

def test_brave_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("CELA_BRAVE_SEARCH_API_KEY", raising=False)
    provider = web_tools.BraveSearchProvider()
    with pytest.raises(web_tools.WebSearchConfigError):
        provider.search("query", max_results=5)


def test_brave_provider_search_maps_fields(monkeypatch):
    class _FakeBraveResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "web": {
                    "results": [
                        {"title": "T1", "url": "https://example.com/1", "description": "D1"},
                        {"title": "T2", "url": "https://example.com/2", "description": "D2"},
                    ]
                }
            }

    monkeypatch.setenv("CELA_BRAVE_SEARCH_API_KEY", "test-key")
    captured = {}

    def fake_get(url, params=None, timeout=None, headers=None):
        captured["url"] = url
        captured["params"] = params
        captured["headers"] = headers
        return _FakeBraveResponse()

    monkeypatch.setattr(web_tools.httpx, "get", fake_get)
    provider = web_tools.BraveSearchProvider()
    results = provider.search("python", max_results=1)

    assert captured["url"] == "https://api.search.brave.com/res/v1/web/search"
    assert captured["headers"]["X-Subscription-Token"] == "test-key"
    assert len(results) == 1
    assert results[0] == {"title": "T1", "url": "https://example.com/1", "snippet": "D1"}


def test_brave_provider_handles_missing_web_results_key(monkeypatch):
    class _FakeEmptyResponse:
        def raise_for_status(self):
            pass
        def json(self):
            return {"query": {"original": "x"}}

    monkeypatch.setenv("CELA_BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "get", lambda *a, **kw: _FakeEmptyResponse())
    provider = web_tools.BraveSearchProvider()
    assert provider.search("x", max_results=5) == []


# ---------------------------------------------------------------------------
# BL-271: ExaSearchProvider（raw httpx実装、SDK不使用）
# ---------------------------------------------------------------------------

def test_get_search_provider_can_select_exa(monkeypatch):
    monkeypatch.setenv("CELA_WEB_SEARCH_PROVIDER", "exa")
    provider = web_tools.get_search_provider()
    assert isinstance(provider, web_tools.ExaSearchProvider)


def test_exa_provider_requires_api_key(monkeypatch):
    monkeypatch.delenv("EXA_API_KEY", raising=False)
    provider = web_tools.ExaSearchProvider()
    with pytest.raises(web_tools.WebSearchConfigError):
        provider.search("query", max_results=5)


def test_exa_provider_search_maps_fields_and_joins_highlights(monkeypatch):
    class _FakeExaResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {
                "requestId": "r1",
                "searchType": "auto",
                "results": [
                    {
                        "title": "T1", "url": "https://example.com/1",
                        "highlights": ["抜粋1", "抜粋2"],
                    },
                    {"title": "T2", "url": "https://example.com/2", "highlights": []},
                ],
            }

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    captured = {}

    def fake_post(url, json=None, timeout=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeExaResponse()

    monkeypatch.setattr(web_tools.httpx, "post", fake_post)
    provider = web_tools.ExaSearchProvider()
    results = provider.search("python", max_results=2)

    assert captured["url"] == "https://api.exa.ai/search"
    assert captured["headers"]["Authorization"] == "Bearer test-key"
    assert captured["json"]["query"] == "python"
    assert captured["json"]["numResults"] == 2
    assert captured["json"]["contents"] == {"highlights": True}
    assert len(results) == 2
    assert results[0] == {"title": "T1", "url": "https://example.com/1", "snippet": "抜粋1 / 抜粋2"}
    assert results[1] == {"title": "T2", "url": "https://example.com/2", "snippet": ""}


def test_exa_provider_handles_missing_results_key(monkeypatch):
    class _FakeEmptyResponse:
        status_code = 200
        def raise_for_status(self):
            pass
        def json(self):
            return {"requestId": "r1"}

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "post", lambda *a, **kw: _FakeEmptyResponse())
    provider = web_tools.ExaSearchProvider()
    assert provider.search("x", max_results=5) == []


def test_exa_provider_raises_config_error_on_401(monkeypatch):
    """[BL-271] APIキー無効はWebSearchConfigErrorへ変換され、web_search_handlerの
    短絡ロジック（BL-270と同型）へ合流すること。"""
    class _FakeUnauthorizedResponse:
        status_code = 401
        def raise_for_status(self):
            raise httpx.HTTPStatusError("401", request=None, response=self)

    monkeypatch.setenv("EXA_API_KEY", "invalid-key")
    monkeypatch.setattr(web_tools.httpx, "post", lambda *a, **kw: _FakeUnauthorizedResponse())
    provider = web_tools.ExaSearchProvider()

    with pytest.raises(web_tools.WebSearchConfigError) as exc_info:
        provider.search("query", max_results=5)
    assert "401" in str(exc_info.value) or "APIキー" in str(exc_info.value)


def test_exa_provider_raises_config_error_on_429(monkeypatch):
    class _FakeRateLimitedResponse:
        status_code = 429
        def raise_for_status(self):
            raise httpx.HTTPStatusError("429", request=None, response=self)

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "post", lambda *a, **kw: _FakeRateLimitedResponse())
    provider = web_tools.ExaSearchProvider()

    with pytest.raises(web_tools.WebSearchConfigError) as exc_info:
        provider.search("query", max_results=5)
    assert "429" in str(exc_info.value)
    assert "read_reference_file" in str(exc_info.value)
    assert "web_fetch" in str(exc_info.value)


def test_exa_provider_other_http_errors_not_treated_as_config_error(monkeypatch):
    """[対照] 401/429以外のHTTPエラー（例: 500）はWebSearchConfigErrorへ変換されず、
    従来どおりraise_for_status()由来の汎用例外のままであること。"""
    class _FakeServerErrorResponse:
        status_code = 500
        def raise_for_status(self):
            raise httpx.HTTPStatusError("500", request=None, response=self)

    monkeypatch.setenv("EXA_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "post", lambda *a, **kw: _FakeServerErrorResponse())
    provider = web_tools.ExaSearchProvider()

    with pytest.raises(httpx.HTTPStatusError):
        provider.search("query", max_results=5)


# ---------------------------------------------------------------------------
# validate_url_for_fetch（SSRF対策）
# ---------------------------------------------------------------------------

def test_validate_url_rejects_non_http_scheme():
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.validate_url_for_fetch("ftp://example.com/file")


def test_validate_url_rejects_loopback(monkeypatch):
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("127.0.0.1", 0))],
    )
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.validate_url_for_fetch("http://internal.example/")


def test_validate_url_rejects_private_range(monkeypatch):
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("10.0.0.5", 0))],
    )
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.validate_url_for_fetch("http://intranet.example/")


def test_validate_url_rejects_link_local_metadata_ip(monkeypatch):
    """169.254.169.254（クラウドメタデータエンドポイント）はlink-localとして拒否される。"""
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("169.254.169.254", 0))],
    )
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.validate_url_for_fetch("http://metadata.example/")


def test_validate_url_accepts_public_address(monkeypatch):
    monkeypatch.setattr(
        web_tools.socket, "getaddrinfo",
        lambda host, port: [(None, None, None, None, ("93.184.216.34", 0))],
    )
    web_tools.validate_url_for_fetch("https://example.com/")  # 例外が出なければOK


def test_validate_url_dns_failure_raises(monkeypatch):
    def _raise(host, port):
        raise web_tools.socket.gaierror("not found")
    monkeypatch.setattr(web_tools.socket, "getaddrinfo", _raise)
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.validate_url_for_fetch("http://nonexistent.invalid/")


# ---------------------------------------------------------------------------
# fetch_and_extract
# ---------------------------------------------------------------------------

class _FakeRequest:
    """[Cline手動レビュー指摘1・BL-335] httpx.Request相当の最小フェイク。build_requestが
    返し、send()の引数として渡される。responseを持たせておくと、send()がその応答を
    返す（多段ホップの2段目以降を表現するのに使う）。"""
    def __init__(self, url, response=None):
        self.url = url
        self.response = response


class _FakeFetchResponse:
    def __init__(self, status_code=200, content_type="text/html; charset=utf-8",
                 text="<p>Hello</p>", encoding="utf-8", url=None, next_request=None):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.content = text.encode(encoding)
        self.encoding = encoding
        # [BL-335] 手動リダイレクト追従後の最終着地URL。テストが明示しなければ
        # リクエストURLと同一（＝リダイレクト無し）として扱う。
        self.url = url
        # [Cline手動レビュー指摘1・BL-335] Noneでない場合、httpx.Response.next_requestと
        # 同じ意味を持つ_FakeRequest（次ホップのURL＋そのホップのsend()が返すべき応答）。
        # 多段リダイレクトを表現するのに使う。
        self.next_request = next_request

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class _FakeClient:
    def __init__(self, response, **kwargs):
        self._response = response
        # [BL-335] httpx.Client()へ渡されたkwargsをテストから検証できるよう記録しておく。
        self.init_kwargs = kwargs
        self.sent_urls = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def build_request(self, method, url, headers=None):
        return _FakeRequest(url)

    def send(self, request, follow_redirects=False):
        # [Cline手動レビュー指摘1・BL-335] 手動1ホップ追従（web_tools._fetch_via_httpx_and_convert）
        # を模擬する。requestが2段目以降の_FakeRequest（.responseを持つ）ならそれを返し、
        # 初回（build_request由来、.responseなし）はClient構築時の_responseを返す。
        self.sent_urls.append(request.url)
        resp = request.response or self._response
        if resp.url is None:
            resp.url = request.url
        return resp


def _patch_httpx_client(monkeypatch, response, capture_kwargs=None):
    """httpx.Clientをコンテキストマネージャ互換のフェイクへ差し替える
    （ラムダを関数属性として代入するとインスタンスアクセス時に束縛メソッド化され
    第一引数にselfが渡ってしまうため、functools.partialで回避する）。
    [BL-335] capture_kwargsにdictを渡すと、httpx.Client(**kwargs)へ渡された引数を
    そこへ書き込める。戻り値は生成された_FakeClientインスタンス（sent_urls等の検証用）。"""
    import functools

    client_holder = {}

    def _factory(resp, **kwargs):
        if capture_kwargs is not None:
            capture_kwargs.update(kwargs)
        client = _FakeClient(resp, **kwargs)
        client_holder["client"] = client
        return client

    monkeypatch.setattr(web_tools.httpx, "Client", functools.partial(_factory, response))
    return client_holder


class _FakeMarkItDownResult:
    def __init__(self, text_content):
        self.text_content = text_content


def _patch_markitdown(monkeypatch, text_content=None, exc=None, capture=None):
    """[BL-188] web_tools._MARKITDOWN.convert_streamをモックする（既存のhttpx.Clientモックと
    同じ方針：外部ライブラリの内部実装ではなく、呼び出し境界を差し替える。実際のHTML/PDF
    バイナリ構造を組み立てずに済む）。"""

    def fake_convert_stream(stream, *, stream_info=None, url=None, **kwargs):
        if capture is not None:
            capture["stream_info"] = stream_info
            capture["url"] = url
            capture["raw"] = stream.read()
        if exc is not None:
            raise exc
        return _FakeMarkItDownResult(text_content)

    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream", fake_convert_stream)


def _force_httpx_path(monkeypatch):
    """[BL-335] fetch_and_extractは`_DOCUMENT_EXTENSIONS`外のURLをまずPlaywright経路へ
    通すのが既定になった。既存のhttpx経路（`_fetch_via_httpx_and_convert`）を単体で
    検証するテストは、Playwrightが「非適用/失敗」だった場合（Noneを返す）を模擬して
    フォールバックさせる——これは実運用でPlaywrightが使えない/失敗した場合と同じ経路。"""
    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", lambda url: None)


def test_fetch_and_extract_success(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(text="<p>本文</p>"))
    _patch_markitdown(monkeypatch, text_content="# 見出し\n\n本文です。")
    text = web_tools.fetch_and_extract("https://example.com/")
    assert "本文です" in text


def test_fetch_and_extract_passes_content_type_and_url_to_markitdown(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(content_type="text/html; charset=utf-8"))
    capture = {}
    _patch_markitdown(monkeypatch, text_content="本文", capture=capture)
    web_tools.fetch_and_extract("https://example.com/page/")
    assert capture["stream_info"].mimetype == "text/html"
    assert capture["url"] == "https://example.com/page/"


def test_fetch_and_extract_resolves_relative_links(monkeypatch):
    """[BL-188] markitdownはconvert_stream(url=...)を渡しても相対リンクを自動解決しない
    （実データで確認済み）ため、fetch_and_extract側で絶対URLへ解決する。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse())
    _patch_markitdown(
        monkeypatch,
        text_content="[永平寺町の事例](/case/eiheiji/) と [外部サイト](https://other.example.com/report.pdf)",
    )
    text = web_tools.fetch_and_extract("https://example.com/case/index.html")
    assert "[永平寺町の事例](https://example.com/case/eiheiji/)" in text
    assert "[外部サイト](https://other.example.com/report.pdf)" in text


def test_fetch_and_extract_follows_redirect_and_validates_final_url(monkeypatch):
    """[Cline手動レビューR1/指摘1・BL-335] リダイレクト方針転換後: 302応答→最終200応答の
    2ホップ構成を模擬し、両ホップのURLがvalidate_url_for_fetchで検証されること、かつ
    最終的に着地先の本文が取得できることを確認する。"""
    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", lambda url: None)
    validated_urls = []
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: validated_urls.append(url))
    client_kwargs = {}
    final_response = _FakeFetchResponse(
        text="<p>リダイレクト先本文</p>", url="https://example.com/landed/",
    )
    hop1_response = _FakeFetchResponse(
        status_code=302,
        next_request=_FakeRequest("https://example.com/landed/", response=final_response),
    )
    holder = _patch_httpx_client(monkeypatch, hop1_response, capture_kwargs=client_kwargs)
    _patch_markitdown(monkeypatch, text_content="リダイレクト先の本文です。")
    text = web_tools.fetch_and_extract("https://example.com/old-path/")
    assert "リダイレクト先の本文です" in text
    # [Cline手動レビュー指摘1・BL-335] follow_redirects=Trueの自動追従（blind SSRFの原因）は
    # 撤去し、手動で1ホップずつsend(request, follow_redirects=False)する方式へ変更した。
    assert client_kwargs.get("follow_redirects") is None
    # 元URL（fetch_and_extract冒頭＋httpx経路1ホップ目）と最終着地URL（2ホップ目）が
    # 接続前に検証されること。
    assert validated_urls == [
        "https://example.com/old-path/",
        "https://example.com/old-path/",
        "https://example.com/landed/",
    ]
    assert holder["client"].sent_urls == ["https://example.com/old-path/", "https://example.com/landed/"]


def test_fetch_and_extract_blocks_intermediate_redirect_hop_before_connecting(monkeypatch):
    """[Cline手動レビュー指摘1・BL-335] 中間リダイレクトホップ（最終着地URLではない）が
    内部アドレスへ向いている場合、そのホップへ実際に接続（send）する前にSSRF検証で
    拒否されること（blind SSRF対策の直接検証）。"""
    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", lambda url: None)

    def _validate(url):
        if "169.254.169.254" in url:
            raise web_tools.SsrfBlockedError("内部アドレスへの中間リダイレクトを検知しました。")

    monkeypatch.setattr(web_tools, "validate_url_for_fetch", _validate)
    intermediate_response = _FakeFetchResponse(
        status_code=302,
        next_request=_FakeRequest("http://169.254.169.254/latest/meta-data/"),
    )
    holder = _patch_httpx_client(monkeypatch, intermediate_response)

    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/redirect-me")

    # 元URL（1回目のホップ）へは接続したが、内部アドレスへの2回目のホップは
    # validate_url_for_fetchで例外化され、send()が2回目呼ばれてはいけない
    # （＝実際には接続していない）。
    assert holder["client"].sent_urls == ["https://example.com/redirect-me"]


def test_fetch_and_extract_blocks_redirect_to_private_ip(monkeypatch):
    """[Cline手動レビューR1・BL-335] リダイレクトは追従を許可するが、最終着地URLが
    プライベートIP等（SSRF対象）であれば引き続き拒否されること。"""
    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", lambda url: None)

    def _validate(url):
        if "internal.example" in url:
            raise web_tools.SsrfBlockedError("内部アドレスへのリダイレクトを検知しました。")

    monkeypatch.setattr(web_tools, "validate_url_for_fetch", _validate)
    final_response = _FakeFetchResponse(text="<p>本文</p>", url="https://internal.example/secret")
    hop1_response = _FakeFetchResponse(
        status_code=302,
        next_request=_FakeRequest("https://internal.example/secret", response=final_response),
    )
    _patch_httpx_client(monkeypatch, hop1_response)
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/redirect-me")


def test_fetch_and_extract_rejects_non_text_non_pdf_content_type(monkeypatch):
    """[BL-188] text/*とapplication/pdf以外（例: application/octet-stream）は引き続き拒否する。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(content_type="application/octet-stream"))
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/file.bin")


def test_fetch_and_extract_accepts_pdf_content_type(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))  # [BL-335] 生バイトキャッシュ書込先
    resp = _FakeFetchResponse(content_type="application/pdf")
    resp.content = b"%PDF-1.4 fake bytes for test"
    _patch_httpx_client(monkeypatch, resp)
    capture = {}
    _patch_markitdown(monkeypatch, text_content="PDF本文のMarkdown", capture=capture)
    text = web_tools.fetch_and_extract("https://example.com/file.pdf")
    assert "PDF本文のMarkdown" in text
    assert capture["stream_info"].mimetype == "application/pdf"


def test_fetch_and_extract_rejects_oversized_content(monkeypatch):
    """[SAFETY] より厳密なパーサ（markitdown内部のpdfminer/BeautifulSoup等）へ渡す前提のため、
    HTML/PDFいずれもバイト列の途中切り捨てはせず、上限超過時は明示エラーにする。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    resp = _FakeFetchResponse()
    resp.content = b"x" * (web_tools._MAX_FETCH_BYTES + 1)
    _patch_httpx_client(monkeypatch, resp)
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/huge")


def test_fetch_and_extract_wraps_markitdown_exception(monkeypatch, tmp_path):
    """[BL-188] markitdownが変換に失敗した場合（壊れたPDF等）、MarkItDownExceptionを
    SsrfBlockedErrorへラップして返す（呼び出し元のweb_fetch_handlerが既存パターン通り
    エラーレスポンスへ変換できるようにする）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))  # [BL-335] 生バイトキャッシュ書込先
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(content_type="application/pdf"))
    _patch_markitdown(monkeypatch, exc=web_tools.MarkItDownException("broken PDF"))
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/broken.pdf")


def test_fetch_and_extract_accepts_docx_content_type(monkeypatch):
    """[BL-218] 自治体サイトが配布するWord文書を、正しいContent-Typeで受理できること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    resp = _FakeFetchResponse(
        content_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    )
    _patch_httpx_client(monkeypatch, resp)
    capture = {}
    _patch_markitdown(monkeypatch, text_content="Word本文のMarkdown", capture=capture)
    text = web_tools.fetch_and_extract("https://www.city.chino.lg.jp/soshiki/report.docx")
    assert "Word本文のMarkdown" in text
    assert capture["stream_info"].extension == ".docx"


def test_fetch_and_extract_accepts_xlsx_via_extension_when_content_type_is_wrong(monkeypatch, tmp_path):
    """[BL-218] 自治体サイトはContent-Typeが不正確（application/octet-stream等）なことが
    珍しくない。URLパスの拡張子で救えることを確認する（本テストの直接動機）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))  # [BL-335] 生バイトキャッシュ書込先
    resp = _FakeFetchResponse(content_type="application/octet-stream")
    _patch_httpx_client(monkeypatch, resp)
    capture = {}
    _patch_markitdown(monkeypatch, text_content="Excel本文のMarkdown", capture=capture)
    text = web_tools.fetch_and_extract("https://www.city.chino.lg.jp/soshiki/data.xlsx")
    assert "Excel本文のMarkdown" in text
    assert capture["stream_info"].extension == ".xlsx"
    assert capture["stream_info"].mimetype == "application/octet-stream"


@pytest.mark.parametrize("ext,content_type", [
    (".xls", "application/vnd.ms-excel"),
    (".pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
    (".epub", "application/epub+zip"),
    (".csv", "text/csv"),
])
def test_fetch_and_extract_accepts_document_formats(monkeypatch, tmp_path, ext, content_type):
    """[BL-218] Excel(旧形式)/PowerPoint/EPUB/CSVも受理する。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))  # [BL-335] .xlsのみ生バイトキャッシュ対象
    resp = _FakeFetchResponse(content_type=content_type)
    _patch_httpx_client(monkeypatch, resp)
    _patch_markitdown(monkeypatch, text_content="変換結果")
    text = web_tools.fetch_and_extract(f"https://example.com/file{ext}")
    assert "変換結果" in text


def test_fetch_and_extract_still_rejects_content_type_and_extension_both_unrecognized(monkeypatch):
    """[BL-218] 非退行：Content-Type・拡張子のどちらも文書系と認識できない場合は
    引き続き拒否する（zip爆弾リスク等を理由に対象外としたzip等を含む）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(content_type="application/zip"))
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/archive.zip")


def test_fetch_and_extract_truncates_long_output(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _force_httpx_path(monkeypatch)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse())
    _patch_markitdown(monkeypatch, text_content="あ" * 20000)
    text = web_tools.fetch_and_extract("https://example.com/")
    assert text.endswith("[Fetch Output truncated]")
    assert len(text) <= web_tools._MAX_OUTPUT_CHARS + len("\n[Fetch Output truncated]")


# ---------------------------------------------------------------------------
# キャッシュ
# ---------------------------------------------------------------------------

def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    path = web_tools.cache_file_path("https://example.com/")
    assert not path.exists()
    web_tools.write_cache(path, "https://example.com/", "本文テキスト")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Source: https://example.com/")
    assert web_tools.strip_cache_header(content) == "本文テキスト"


def test_cache_file_path_is_deterministic():
    p1 = web_tools.cache_file_path("https://example.com/")
    p2 = web_tools.cache_file_path("https://example.com/")
    p3 = web_tools.cache_file_path("https://example.com/other")
    assert p1 == p2
    assert p1 != p3


def test_cache_file_path_is_shared_across_runs(monkeypatch, tmp_path):
    """[BL-200] web_cacheはURLキーのグローバル共有であり、run_idを問わず同じパスに
    解決される。過去のrunでweb_fetch済みのURLは、別のrun_idからでも呼び出し回数を
    消費せず再利用できる（log/2026-08-09/2222でrun単位分離のコストが指摘された）。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/")
    web_tools.write_cache(cache_path, "https://example.com/", "run-1が取得した本文")

    def _should_not_be_called(url):
        raise AssertionError("fetch_and_extract should not be called on cache hit from a different run")
    monkeypatch.setattr(web_tools, "fetch_and_extract", _should_not_be_called)

    state = {"run_id": "run-2", "web_fetch_call_count": 0}
    result = web_tools.web_fetch_handler({"url": "https://example.com/"}, state, {})
    assert result == "run-1が取得した本文"
    assert state["web_fetch_call_count"] == 0


# ---------------------------------------------------------------------------
# web_search_handler
# ---------------------------------------------------------------------------

def test_web_search_handler_requires_query():
    result = web_tools.web_search_handler({}, {}, {})
    assert result["status"] == "error"


def test_web_search_handler_enforces_call_limit(monkeypatch):
    state = {"web_search_call_count": 3}
    config = {"max_web_search_calls": 3}
    result = web_tools.web_search_handler({"query": "x"}, state, config)
    assert result["status"] == "error"
    assert "上限" in result["message"]


def test_web_search_handler_success_increments_count(monkeypatch):
    class _FakeProvider:
        def search(self, query, max_results):
            return [{"title": "T", "url": "https://example.com/", "snippet": "S"}]

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _FakeProvider())
    state = {"web_search_call_count": 0}
    result = web_tools.web_search_handler({"query": "x"}, state, {})
    assert result["results"][0]["title"] == "T"
    assert state["web_search_call_count"] == 1


def test_web_search_handler_provider_not_configured(monkeypatch):
    def _raise():
        raise web_tools.WebSearchConfigError("web_search is not configured: ...")
    monkeypatch.setattr(web_tools, "get_search_provider", _raise)
    result = web_tools.web_search_handler({"query": "x"}, {}, {})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# BL-282: log/2026-08-26/2334で、task_1_4到達時点でweb_search呼び出し上限（当時100/run）
# が枯渇し、以降の全タスクでweb_searchが使えなくなる実害を確認した。
# max_resultsの既定/上限を10→15へ、max_web_search_callsの既定を100→200へ引き上げた。
# ---------------------------------------------------------------------------

def test_web_search_handler_default_max_results_is_15(monkeypatch):
    captured = {}

    class _FakeProvider:
        def search(self, query, max_results):
            captured["max_results"] = max_results
            return []

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _FakeProvider())
    web_tools.web_search_handler({"query": "x"}, {"web_search_call_count": 0}, {})
    assert captured["max_results"] == 15


def test_web_search_handler_clamps_max_results_to_15(monkeypatch):
    captured = {}

    class _FakeProvider:
        def search(self, query, max_results):
            captured["max_results"] = max_results
            return []

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _FakeProvider())
    web_tools.web_search_handler({"query": "x", "max_results": 50}, {"web_search_call_count": 0}, {})
    assert captured["max_results"] == 15


def test_default_max_web_search_calls_fallback_is_400():
    """[BL-314] 200→400へ再緩和（同run複数回のresumeを経た累積消費でTurn 8/30という
    序盤で200/200が再度枯渇したため）。"""
    assert web_tools._DEFAULT_MAX_WEB_SEARCH_CALLS == 400


def test_web_search_handler_uses_400_fallback_limit_when_config_missing(monkeypatch):
    class _FakeProvider:
        def search(self, query, max_results):
            return []

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _FakeProvider())
    state = {"web_search_call_count": 350}
    result = web_tools.web_search_handler({"query": "x"}, state, {})
    assert "results" in result, "config未指定時、既定上限400未満なので拒否されてはならない"


def test_cli_default_max_web_search_calls_is_400():
    import inspect
    import cela_main
    src = inspect.getsource(cela_main)
    assert '"max_web_search_calls": 400,' in src


# ---------------------------------------------------------------------------
# BL-270: Brave Search APIの402 Payment Required（利用上限到達）を明示的に検知し、
# run内で以後の呼び出しを実際のAPIへ送らず短絡させる。
# ---------------------------------------------------------------------------

def test_brave_provider_raises_config_error_on_402(monkeypatch):
    """402は他のHTTPエラーとは異なり、raise_for_status()の汎用例外ではなく、
    WebSearchConfigError（run内では回復しない系統の失敗を表す既存の型）として
    明示的に送出されること。"""
    class _FakePaymentRequiredResponse:
        status_code = 402
        def raise_for_status(self):
            raise httpx.HTTPStatusError("402", request=None, response=self)

    monkeypatch.setenv("CELA_BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "get", lambda *a, **kw: _FakePaymentRequiredResponse())
    provider = web_tools.BraveSearchProvider()

    with pytest.raises(web_tools.WebSearchConfigError) as exc_info:
        provider.search("query", max_results=5)
    assert "402" in str(exc_info.value)
    assert "read_reference_file" in str(exc_info.value)
    assert "web_fetch" in str(exc_info.value)


def test_brave_provider_other_http_errors_not_treated_as_config_error(monkeypatch):
    """[対照] 402以外のHTTPエラー（例: 500）は、従来どおりraise_for_status()由来の
    汎用例外のままであること（WebSearchConfigErrorへ過剰に一般化しない）。"""
    class _FakeServerErrorResponse:
        status_code = 500
        def raise_for_status(self):
            raise httpx.HTTPStatusError("500", request=None, response=self)

    monkeypatch.setenv("CELA_BRAVE_SEARCH_API_KEY", "test-key")
    monkeypatch.setattr(web_tools.httpx, "get", lambda *a, **kw: _FakeServerErrorResponse())
    provider = web_tools.BraveSearchProvider()

    with pytest.raises(httpx.HTTPStatusError):
        provider.search("query", max_results=5)


def test_web_search_handler_records_unavailable_message_on_config_error(monkeypatch):
    def _raise():
        raise web_tools.WebSearchConfigError(
            "web_search is temporarily unavailable: 402 Payment Required"
        )
    monkeypatch.setattr(web_tools, "get_search_provider", _raise)

    state = {"web_search_call_count": 0}
    result = web_tools.web_search_handler({"query": "x"}, state, {})

    assert result["status"] == "error"
    assert state["web_search_provider_unavailable_message"] == result["message"]
    # [BL-096同型の失敗] APIへ到達できなかった呼び出しは呼び出し回数を消費しない。
    assert state["web_search_call_count"] == 0


def test_web_search_handler_short_circuits_without_calling_provider_again(monkeypatch):
    """一度WebSearchConfigErrorが記録された後の2回目の呼び出しは、get_search_provider
    自体を呼ばず（＝実際のHTTPリクエストを送らず）、同じ説明を即座に返すこと。"""
    calls = {"count": 0}

    def _get_search_provider_should_not_be_called():
        calls["count"] += 1
        raise AssertionError("get_search_providerが呼ばれてはならない")

    monkeypatch.setattr(web_tools, "get_search_provider", _get_search_provider_should_not_be_called)

    state = {
        "web_search_call_count": 0,
        "web_search_provider_unavailable_message": (
            "web_search is temporarily unavailable: 402 Payment Required"
        ),
    }
    result = web_tools.web_search_handler({"query": "another query"}, state, {})

    assert calls["count"] == 0
    assert result["status"] == "error"
    assert result["message"] == state["web_search_provider_unavailable_message"]


def test_web_search_handler_unavailable_check_happens_before_call_limit_check(monkeypatch):
    """[優先順位の確認] 呼び出し上限に既に達している状態でも、provider unavailable
    メッセージが先に返ること（後から見てどちらが原因だったか紛らわしくならないよう、
    より根本的な失敗要因を優先する）。"""
    state = {
        "web_search_call_count": 5,
        "web_search_provider_unavailable_message": "web_search is temporarily unavailable: 402",
    }
    config = {"max_web_search_calls": 5}
    result = web_tools.web_search_handler({"query": "x"}, state, config)
    assert result["message"] == state["web_search_provider_unavailable_message"]


# ---------------------------------------------------------------------------
# web_fetch_handler
# ---------------------------------------------------------------------------

def test_web_fetch_handler_requires_url():
    result = web_tools.web_fetch_handler({}, {}, {})
    assert result["status"] == "error"


def test_web_fetch_handler_cache_hit_skips_provider_and_count(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1", "web_fetch_call_count": 0}
    cache_path = web_tools.cache_file_path("https://example.com/")
    web_tools.write_cache(cache_path, "https://example.com/", "キャッシュ済み本文")

    def _should_not_be_called(url):
        raise AssertionError("fetch_and_extract should not be called on cache hit")
    monkeypatch.setattr(web_tools, "fetch_and_extract", _should_not_be_called)

    result = web_tools.web_fetch_handler({"url": "https://example.com/"}, state, {})
    assert result == "キャッシュ済み本文"
    assert state["web_fetch_call_count"] == 0


def test_web_fetch_handler_enforces_call_limit(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1", "web_fetch_call_count": 5}
    config = {"max_web_fetch_calls": 5}
    result = web_tools.web_fetch_handler({"url": "https://example.com/"}, state, config)
    assert result["status"] == "error"
    assert "上限" in result["message"]


def test_web_fetch_handler_success_writes_cache_and_increments_count(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    monkeypatch.setattr(web_tools, "fetch_and_extract", lambda url: "取得した本文")
    state = {"run_id": "run-1", "web_fetch_call_count": 0}
    result = web_tools.web_fetch_handler({"url": "https://example.com/"}, state, {})
    assert result == "取得した本文"
    assert state["web_fetch_call_count"] == 1
    cache_path = web_tools.cache_file_path("https://example.com/")
    assert cache_path.exists()


def test_web_fetch_handler_ssrf_blocked_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    def _raise(url):
        raise web_tools.SsrfBlockedError("内部アドレスへのアクセスは禁止されています")
    monkeypatch.setattr(web_tools, "fetch_and_extract", _raise)
    state = {"run_id": "run-1", "web_fetch_call_count": 0}
    result = web_tools.web_fetch_handler({"url": "http://127.0.0.1/"}, state, {})
    assert result["status"] == "error"
    assert state["web_fetch_call_count"] == 0


# ---------------------------------------------------------------------------
# read_reference_file_handler
# ---------------------------------------------------------------------------

def test_read_reference_file_by_path_success(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/")
    web_tools.write_cache(cache_path, "https://example.com/", "本文")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"path": cache_path.name}, state)
    assert "本文" in result


def test_read_reference_file_path_traversal_rejected(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"path": "../../etc/passwd"}, state)
    assert result["status"] == "error"


def test_read_reference_file_by_keyword_single_match(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/target")
    web_tools.write_cache(cache_path, "https://example.com/target", "対象の本文")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com/target"}, state)
    assert "対象の本文" in result


def test_read_reference_file_by_keyword_multiple_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    p1 = web_tools.cache_file_path("https://example.com/a")
    p2 = web_tools.cache_file_path("https://example.com/b")
    web_tools.write_cache(p1, "https://example.com/a", "A")
    web_tools.write_cache(p2, "https://example.com/b", "B")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com"}, state)
    assert result["status"] == "multiple_matches"
    assert len(result["candidates"]) == 2


def test_read_reference_file_multiple_matches_candidates_include_preview(monkeypatch, tmp_path):
    """[BL-216] キャッシュファイル名はsha256ハッシュで意味を持たないため、候補一覧に
    Source URLと本文冒頭のpreviewを添え、開かずに目的のファイルを選べるようにする。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    p1 = web_tools.cache_file_path("https://example.com/a")
    p2 = web_tools.cache_file_path("https://example.com/b")
    web_tools.write_cache(p1, "https://example.com/a", "これはAページの本文です。")
    web_tools.write_cache(p2, "https://example.com/b", "これはBページの本文です。")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com"}, state)
    assert result["status"] == "multiple_matches"
    by_path = {c["path"]: c["preview"] for c in result["candidates"]}
    assert set(by_path) == {p1.name, p2.name}
    assert "https://example.com/a" in by_path[p1.name]
    assert "Aページの本文" in by_path[p1.name]
    assert "https://example.com/b" in by_path[p2.name]
    assert "Bページの本文" in by_path[p2.name]


def test_read_reference_file_preview_truncates_long_body(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    p1 = web_tools.cache_file_path("https://example.com/a")
    p2 = web_tools.cache_file_path("https://example.com/b")
    long_body = "x" * 1000
    web_tools.write_cache(p1, "https://example.com/a", long_body)
    web_tools.write_cache(p2, "https://example.com/b", "short")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com"}, state)
    by_path = {c["path"]: c["preview"] for c in result["candidates"]}
    preview_body = by_path[p1.name].split("\n", 1)[1]
    assert preview_body == "x" * 300 + "…"


def test_read_reference_file_reads_cache_written_by_a_different_run(monkeypatch, tmp_path):
    """[BL-200] read_reference_fileはstate["run_id"]でベースディレクトリを絞らなくなった
    ため、別runが書いたキャッシュも読める。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/target")
    web_tools.write_cache(cache_path, "https://example.com/target", "run-1が書いた本文")
    state = {"run_id": "run-2"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com/target"}, state)
    assert "run-1が書いた本文" in result


def test_read_reference_file_no_args_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    result = web_tools.read_reference_file_handler({}, {"run_id": "run-1"})
    assert result["status"] == "error"


def test_read_reference_file_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "存在しない"}, state)
    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# [BL-221] read_reference_file の grep パラメータ / _MAX_FETCH_BYTES 引き上げ
# ---------------------------------------------------------------------------

def test_bl221_max_fetch_bytes_raised_to_50mb():
    """[BL-221] 8MB→50MBへユーザー承認のもと引き上げたことの固定化。"""
    assert web_tools._MAX_FETCH_BYTES == 50 * 1024 * 1024


def test_grep_with_context_returns_none_when_no_match():
    assert web_tools._grep_with_context("line1\nline2\nline3", "存在しない文字列") is None


def test_grep_with_context_includes_surrounding_lines():
    content = "\n".join(f"line{i}" for i in range(1, 21))
    result = web_tools._grep_with_context(content, "line10", context_lines=2)
    assert "line8" in result
    assert "line9" in result
    assert "line10" in result
    assert "line11" in result
    assert "line12" in result
    assert "line7" not in result
    assert "line13" not in result


def test_grep_with_context_merges_overlapping_windows():
    """マッチ同士が近接している場合、コンテキスト窓が重複せず1つのブロックへ
    統合されること（同じ行が二重に出力されない）。"""
    lines = [f"line{i}" for i in range(1, 21)]
    lines[4] = "target"  # line5 -> target (index 4)
    lines[6] = "target"  # line7 -> target (index 6), context_lines=2なので窓が重なる
    content = "\n".join(lines)
    result = web_tools._grep_with_context(content, "target", context_lines=2)
    assert result.count("--") == 0  # 隣接する2マッチが1ブロックへ統合され、区切りが出ない
    assert result.count("target") == 2


def test_grep_with_context_caps_match_blocks_and_notes_truncation():
    content = "\n".join(f"target{i} spacer spacer spacer spacer" for i in range(1, 50))
    result = web_tools._grep_with_context(content, "target", context_lines=0)
    assert "先頭30件のみ表示" in result


def test_bl252_grep_with_context_pipe_matches_any_term():
    """[BL-252] `|`区切りのいずれかの語を含む行がヒットすること（OR検索）。
    実ドライラン（log/2026-08-16/1832）で、`grep="調査対象者|回答者数|利用"`のような
    パターンが、対象ファイルに実際にこれらの語が含まれているにもかかわらず
    リテラル部分一致のため常にnot_foundになっていたことを受けた修正。"""
    content = "\n".join([
        "1行目: 無関係な内容",
        "2行目: 調査対象者は約2707人である",
        "3行目: また別の無関係な内容",
        "4行目: 回答者数は880人だった",
    ])
    result = web_tools._grep_with_context(content, "調査対象者|回答者数|利用", context_lines=0)
    assert result is not None
    assert "調査対象者" in result
    assert "回答者数" in result
    assert "無関係な内容" not in result


def test_bl252_grep_with_context_pipe_no_match_still_returns_none():
    assert web_tools._grep_with_context("line1\nline2", "存在しないA|存在しないB") is None


def test_bl252_grep_with_context_pipe_single_term_still_works():
    """`|`を含まない従来通りの単一語検索が引き続き動作すること（非退行）。"""
    result = web_tools._grep_with_context("foo\nbar\nbaz", "bar", context_lines=0)
    assert result is not None
    assert "bar" in result


def test_bl252_grep_with_context_trailing_pipe_does_not_crash():
    """`"A|"`のような空語を含む分割結果でもクラッシュせず、空語を無視すること。"""
    result = web_tools._grep_with_context("foo\nbar\nbaz", "bar|", context_lines=0)
    assert result is not None
    assert "bar" in result


def test_bl252_grep_with_context_not_a_full_regex_engine():
    """`|`以外の正規表現メタ文字（`.`等）はリテラル文字として扱われること（意図的な
    仕様の維持——re.searchへの全面移行はReDoS等の新リスクを持ち込むため採用しない）。"""
    content = "a.b\nacb\naxb"
    result = web_tools._grep_with_context(content, "a.b", context_lines=0)
    assert result is not None
    assert result.count("\n") == 0  # "a.b"の1行のみヒット（"acb"はリテラル一致しない）
    assert "a.b" in result


def test_bl252_read_reference_file_grep_pipe_end_to_end(monkeypatch, tmp_path):
    """read_reference_file_handler経由でも`|`のOR検索が機能すること。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path))
    cache_file = tmp_path / "abc123.md"
    cache_file.write_text(
        "# Source: https://example.com\n# Fetched: 2026-01-01T00:00:00\n\n"
        "無関係な行\n調査対象者は2707人\n無関係な行2\n",
        encoding="utf-8",
    )
    result = web_tools.read_reference_file_handler(
        {"path": "abc123.md", "grep": "調査対象者|回答者数"}, {"run_id": "run-1"}
    )
    assert isinstance(result, str)
    assert "調査対象者" in result


def test_bl252_tool_schema_documents_pipe_or_syntax():
    """[BL-252] cela_main.py側のツールschema説明に、`|`でOR検索できる旨と、
    フル正規表現エンジンではない旨が明記されていること（Expertが誤って他の正規表現
    構文を使わないようにするため）。"""
    import cela_main
    grep_desc = cela_main.READ_REFERENCE_FILE_TOOL["function"]["parameters"]["properties"]["grep"]["description"]
    assert "|" in grep_desc
    assert "BL-252" in grep_desc


def test_read_reference_file_grep_requires_path():
    result = web_tools.read_reference_file_handler({"grep": "foo"}, {"run_id": "run-1"})
    assert result["status"] == "error"
    assert "grep" in result["message"]  # 汎用の「pathまたはkeywordを指定」エラーと区別できること


def test_read_reference_file_grep_returns_context_not_whole_file(monkeypatch, tmp_path):
    """[BL-221] pathとgrepを組み合わせると、_MAX_READ_REFERENCE_CHARSによる切り詰めを
    経由せず全文からマッチ箇所の前後だけを返すこと。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/big")
    body = ("filler line\n" * 5000) + "★目的の記述★\n" + ("filler line\n" * 5000)
    web_tools.write_cache(cache_path, "https://example.com/big", body)
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"path": cache_path.name, "grep": "★目的の記述★"}, state)
    assert "★目的の記述★" in result
    assert len(result) < len(body)


def test_read_reference_file_grep_not_found_in_existing_file(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/big")
    web_tools.write_cache(cache_path, "https://example.com/big", "ここには目的の文字列がありません")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"path": cache_path.name, "grep": "存在しないパターン"}, state)
    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# [BL-244] keyword+grepの同時指定（pathを別ターンで先に確認させず、1回のtool callで
# 完結させたいという自然な意図）。log/2026-08-15/2149・2239で、独立した4つ以上のExpertが
# それぞれ{"path": "", "keyword": X, "grep": X}という同型の呼び出しを行い、全て
# 「grepはpathと組み合わせて指定してください」で拒否されていた（read_reference_file全26回
# 中12回=46%を占めた）。keywordが一意に1件へ解決できる場合は、拒否する前にそれを試す。
# ---------------------------------------------------------------------------

def test_read_reference_file_keyword_and_grep_together_single_match_succeeds(monkeypatch, tmp_path):
    """[BL-244本体] pathを省略し、keyword+grepを同時指定した実インシデントと同型の呼び出し。
    keywordが一意に1件へ解決できるなら、以前のように問答無用でエラーにせず、そのファイルに
    対してgrepを適用して結果を返すこと。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    cache_path = web_tools.cache_file_path("https://example.com/target")
    body = ("filler line\n" * 100) + "★目的の記述★\n" + ("filler line\n" * 100)
    web_tools.write_cache(cache_path, "https://example.com/target", body)
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler(
        {"path": "", "keyword": "example.com/target", "grep": "★目的の記述★"}, state,
    )
    assert not isinstance(result, dict), f"エラー/not_foundのまま: {result}"
    assert "★目的の記述★" in result
    assert len(result) < len(body)


def test_read_reference_file_keyword_and_grep_together_no_match_returns_not_found(monkeypatch, tmp_path):
    """keywordが0件の場合は、grep用のエラーではなくkeywordのnot_foundを返すこと
    （grepを理由にした拒否メッセージへ後退しない）。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler(
        {"keyword": "存在しないキーワード", "grep": "何か"}, state,
    )
    assert result["status"] == "not_found"
    assert "存在しないキーワード" in result["message"]


def test_read_reference_file_keyword_and_grep_together_multiple_matches_returns_candidates(monkeypatch, tmp_path):
    """keywordが複数件に一致する場合は、grepを保留してmultiple_matchesの候補一覧を返すこと
    （どのファイルにgrepすべきか一意に決められないため、以前と同じ挙動に留める）。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    p1 = web_tools.cache_file_path("https://example.com/a")
    p2 = web_tools.cache_file_path("https://example.com/b")
    web_tools.write_cache(p1, "https://example.com/a", "A")
    web_tools.write_cache(p2, "https://example.com/b", "B")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler(
        {"keyword": "example.com", "grep": "何か"}, state,
    )
    assert result["status"] == "multiple_matches"
    assert len(result["candidates"]) == 2


def test_read_reference_file_grep_without_path_or_keyword_still_errors():
    """回帰確認: keywordも指定されていない場合は、従来通り即エラー
    （解決できる情報が無い以上、無条件で受理しない）。"""
    result = web_tools.read_reference_file_handler({"grep": "foo"}, {"run_id": "run-1"})
    assert result["status"] == "error"
    assert "grep" in result["message"]


def test_bl244_keyword_resolution_helper_present_in_source():
    """§17.1後段: 実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(web_tools.read_reference_file_handler)
    assert "_resolve_reference_cache_path_by_keyword" in src
    assert "if not keyword:" in src


# ---------------------------------------------------------------------------
# [BL-299] READ_REFERENCE_FILE_TOOLのgrep説明文が、BL-244で緩和済みの実装（keyword+grep
# 同時指定を許容）に追従しておらず"Requires 'path'."とだけ書かれていた（AGENTS.md §15.1
# 単一の真実源違反）。log/2026-08-28/2031で、Detectorがこの古い説明文を信じてkeyword+grepの
# 組み合わせを試すべきか約5万字・9分近くかけて逡巡した末、代わりにPDFの数値テーブルを手作業で
# 突合しようとし、その過程で同一文言を3回繰り返してBL-297/298のn-gram反復ガードに引っかかった
# （3回の自動再試行も同一の構造的な迷いを再現し、いずれも失敗）。
# ---------------------------------------------------------------------------

def test_read_reference_file_tool_grep_description_documents_keyword_combo():
    """[BL-299] grepパラメータの説明文が、keyword+grep同時指定（BL-244で実装済み）を
    明示的に許可すると書いてあること。「Requires 'path'」という、BL-244以前の
    より制限された挙動だけを示す古い文言が単独で残っていないこと。"""
    grep_desc = cela_main.READ_REFERENCE_FILE_TOOL["function"]["parameters"]["properties"]["grep"]["description"]
    assert "BL-244" in grep_desc
    assert "keyword" in grep_desc.lower()
    assert "do NOT need to resolve 'path' yourself" in grep_desc
    assert "Requires 'path'." not in grep_desc
