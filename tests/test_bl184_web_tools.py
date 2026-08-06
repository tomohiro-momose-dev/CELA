"""
BL-184: web_tools.py（web_search/web_fetch/read_reference_file）の単体テスト。
実ネットワーク呼び出しは一切行わない（httpx呼び出しはmonkeypatchで差し替える）。

DuckDuckGo HTML版のパーサ検証用サンプルは、実際に`https://html.duckduckgo.com/html/`へ
`httpx.get(url, params={"q": "python programming language"})`でアクセスして得られた
実レスポンス（2026-08-06確認）のマークアップ構造を基にしている
（docs/refs/duckduckgo/html_endpoint_notes.md参照）。

参照: docs/design/back_log/BL-184/BL184_basic_design.md、issue_backlog.md BL-184。
"""

import os
import sys

import httpx
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

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
# _HtmlTextExtractor
# ---------------------------------------------------------------------------

def test_html_extractor_strips_script_and_style():
    html_text = """
    <html><head><style>body { color: red; }</style></head>
    <body>
      <script>alert('x');</script>
      <p>本文テキスト</p>
    </body></html>
    """
    extractor = web_tools._HtmlTextExtractor()
    extractor.feed(html_text)
    extractor.close()
    text = extractor.get_text()
    assert "本文テキスト" in text
    assert "color: red" not in text
    assert "alert" not in text


# ---------------------------------------------------------------------------
# fetch_and_extract
# ---------------------------------------------------------------------------

class _FakeFetchResponse:
    def __init__(self, status_code=200, content_type="text/html; charset=utf-8",
                 text="<p>Hello</p>", encoding="utf-8"):
        self.status_code = status_code
        self.headers = {"content-type": content_type}
        self.content = text.encode(encoding)
        self.encoding = encoding

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError("error", request=None, response=None)


class _FakeClient:
    def __init__(self, response, **kwargs):
        self._response = response

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def get(self, url, headers=None):
        return self._response


def _patch_httpx_client(monkeypatch, response):
    """httpx.Clientをコンテキストマネージャ互換のフェイクへ差し替える
    （ラムダを関数属性として代入するとインスタンスアクセス時に束縛メソッド化され
    第一引数にselfが渡ってしまうため、functools.partialで回避する）。"""
    import functools
    monkeypatch.setattr(web_tools.httpx, "Client", functools.partial(_FakeClient, response))


def test_fetch_and_extract_success(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(text="<p>本文</p>"))
    text = web_tools.fetch_and_extract("https://example.com/")
    assert "本文" in text


def test_fetch_and_extract_blocks_redirect(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(status_code=302))
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/")


def test_fetch_and_extract_rejects_non_text_content_type(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(content_type="application/pdf"))
    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/file.pdf")


def test_fetch_and_extract_truncates_long_output(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    long_text = "<p>" + ("あ" * 20000) + "</p>"
    _patch_httpx_client(monkeypatch, _FakeFetchResponse(text=long_text))
    text = web_tools.fetch_and_extract("https://example.com/")
    assert text.endswith("[Fetch Output truncated]")
    assert len(text) <= web_tools._MAX_OUTPUT_CHARS + len("\n[Fetch Output truncated]")


# ---------------------------------------------------------------------------
# キャッシュ
# ---------------------------------------------------------------------------

def test_cache_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    path = web_tools.cache_file_path("run-1", "https://example.com/")
    assert not path.exists()
    web_tools.write_cache(path, "https://example.com/", "本文テキスト")
    assert path.exists()
    content = path.read_text(encoding="utf-8")
    assert content.startswith("# Source: https://example.com/")
    assert web_tools.strip_cache_header(content) == "本文テキスト"


def test_cache_file_path_is_deterministic():
    p1 = web_tools.cache_file_path("run-1", "https://example.com/")
    p2 = web_tools.cache_file_path("run-1", "https://example.com/")
    p3 = web_tools.cache_file_path("run-1", "https://example.com/other")
    assert p1 == p2
    assert p1 != p3


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
# web_fetch_handler
# ---------------------------------------------------------------------------

def test_web_fetch_handler_requires_url():
    result = web_tools.web_fetch_handler({}, {}, {})
    assert result["status"] == "error"


def test_web_fetch_handler_cache_hit_skips_provider_and_count(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1", "web_fetch_call_count": 0}
    cache_path = web_tools.cache_file_path("run-1", "https://example.com/")
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
    cache_path = web_tools.cache_file_path("run-1", "https://example.com/")
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
    cache_path = web_tools.cache_file_path("run-1", "https://example.com/")
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
    cache_path = web_tools.cache_file_path("run-1", "https://example.com/target")
    web_tools.write_cache(cache_path, "https://example.com/target", "対象の本文")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com/target"}, state)
    assert "対象の本文" in result


def test_read_reference_file_by_keyword_multiple_matches(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    p1 = web_tools.cache_file_path("run-1", "https://example.com/a")
    p2 = web_tools.cache_file_path("run-1", "https://example.com/b")
    web_tools.write_cache(p1, "https://example.com/a", "A")
    web_tools.write_cache(p2, "https://example.com/b", "B")
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "example.com"}, state)
    assert result["status"] == "multiple_matches"
    assert len(result["candidates"]) == 2


def test_read_reference_file_no_args_returns_error(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    result = web_tools.read_reference_file_handler({}, {"run_id": "run-1"})
    assert result["status"] == "error"


def test_read_reference_file_not_found(monkeypatch, tmp_path):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    state = {"run_id": "run-1"}
    result = web_tools.read_reference_file_handler({"keyword": "存在しない"}, state)
    assert result["status"] == "not_found"
