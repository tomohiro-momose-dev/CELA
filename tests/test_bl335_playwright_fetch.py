"""
BL-335 Phase 1: web_fetchの既定パスとして導入したPlaywright描画フェッチの単体テスト。
実ブラウザは一切起動しない（`web_tools._ensure_browser`をmonkeypatchで完全に差し替える）。

参照: docs/design/back_log/BL-335/BL335_basic_design.md。
"""

import io
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import web_tools  # noqa: E402
from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError  # noqa: E402


# ---------------------------------------------------------------------------
# フェイクPlaywrightオブジェクト
# ---------------------------------------------------------------------------

class _FakePlaywrightResponse:
    def __init__(self, status=200, content_type="text/html"):
        self.status = status
        self.headers = {"content-type": content_type}


class _FakePlaywrightPage:
    def __init__(self, url, response=None, content_html="<p>本文</p>",
                 raise_on_goto=None, raise_on_networkidle=None):
        self.url = url
        self._response = response if response is not None else _FakePlaywrightResponse()
        self._content_html = content_html
        self._raise_on_goto = raise_on_goto
        self._raise_on_networkidle = raise_on_networkidle
        self.goto_calls = []
        self.wait_calls = []

    def goto(self, url, wait_until=None, timeout=None):
        self.goto_calls.append((url, wait_until, timeout))
        if self._raise_on_goto is not None:
            raise self._raise_on_goto
        return self._response

    def wait_for_load_state(self, state, timeout=None):
        self.wait_calls.append((state, timeout))
        if self._raise_on_networkidle is not None:
            raise self._raise_on_networkidle

    def content(self):
        return self._content_html


class _FakePlaywrightContext:
    def __init__(self, page):
        self._page = page
        self.routed = []
        self.closed = False

    def route(self, pattern, handler):
        self.routed.append((pattern, handler))

    def new_page(self):
        return self._page

    def close(self):
        self.closed = True


class _FakePlaywrightBrowser:
    def __init__(self, context):
        self._context = context
        self.new_context_calls = []

    def new_context(self, user_agent=None):
        self.new_context_calls.append(user_agent)
        return self._context


def _install_fake_browser(monkeypatch, page):
    """`_ensure_browser`を差し替え、指定したfake pageを返すbrowser/contextチェーンを
    組み立てる。テストごとにcontextを取得してrouted/closedを検証できるよう返す。"""
    context = _FakePlaywrightContext(page)
    browser = _FakePlaywrightBrowser(context)
    monkeypatch.setattr(web_tools, "_ensure_browser", lambda: browser)
    monkeypatch.setattr(web_tools, "_PAGES_RENDERED_SINCE_LAUNCH", 0)
    return context


# ---------------------------------------------------------------------------
# 1-2. ルーティング判定
# ---------------------------------------------------------------------------

def test_document_extension_bypasses_playwright_entirely(monkeypatch):
    """[Phase1テスト2] .pdf等の_DOCUMENT_EXTENSIONS URLはPlaywrightに一切触れず
    既存httpx経路へ直行すること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    called = {"playwright": False}

    def _fail_if_called(url):
        called["playwright"] = True
        return None

    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", _fail_if_called)

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        content = b"%PDF-1.4 fake"
        url = "https://example.com/file.pdf"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())

    class _FakeResult:
        text_content = "PDF本文"

    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream", lambda *a, **kw: _FakeResult())

    text = web_tools.fetch_and_extract("https://example.com/file.pdf")
    assert "PDF本文" in text
    assert called["playwright"] is False


# ---------------------------------------------------------------------------
# 3. Playwright成功パス
# ---------------------------------------------------------------------------

def test_playwright_success_feeds_into_markitdown(monkeypatch):
    """[Phase1テスト3] Playwright成功（HTML返却）→_MARKITDOWN.convert_streamが呼ばれ、
    既存のリンク解決・切り詰め処理が変わらず適用されること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://example.com/",
        content_html="<p>JS描画後の本文</p>",
    )
    context = _install_fake_browser(monkeypatch, page)

    capture = {}

    class _FakeResult:
        text_content = "[相対リンク](/foo)"

    def fake_convert_stream(stream, *, stream_info=None, url=None, **kw):
        capture["stream_info"] = stream_info
        capture["url"] = url
        capture["raw"] = stream.read()
        return _FakeResult()

    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream", fake_convert_stream)

    text = web_tools.fetch_and_extract("https://example.com/")

    assert capture["stream_info"].mimetype == "text/html"
    assert capture["url"] == "https://example.com/"
    # 既存のリンク解決処理が適用されること（相対→絶対URL）。
    assert "[相対リンク](https://example.com/foo)" in text
    assert context.closed is True


def test_playwright_uses_networkidle_bestEffort(monkeypatch):
    """domcontentloaded後にnetworkidleをベストエフォート待機し、タイムアウトしても
    致命的失敗にはならないこと（Playwright成功として扱う）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://example.com/spa",
        content_html="<p>SPA本文</p>",
        raise_on_networkidle=PlaywrightTimeoutError("networkidle timeout"),
    )
    _install_fake_browser(monkeypatch, page)
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": "SPA本文"})())

    text = web_tools.fetch_and_extract("https://example.com/spa")
    assert "SPA本文" in text
    assert len(page.wait_calls) == 1


# ---------------------------------------------------------------------------
# 4-5. フォールバックのトリガー条件
# ---------------------------------------------------------------------------

def test_playwright_navigation_exception_falls_back_to_httpx(monkeypatch):
    """[Phase1テスト4] Playwrightナビゲーション例外→httpxフォールバックへ切り替わり、
    fetch_and_extractの最終結果はhttpx経路の値になること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://example.com/",
        raise_on_goto=PlaywrightTimeoutError("navigation timeout"),
    )
    _install_fake_browser(monkeypatch, page)

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = "<p>httpxフォールバック本文</p>".encode("utf-8")
        url = "https://example.com/"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": "httpxフォールバック本文"})())

    text = web_tools.fetch_and_extract("https://example.com/")
    assert "httpxフォールバック本文" in text


def test_playwright_short_content_does_not_trigger_fallback(monkeypatch):
    """[Phase1テスト5] レンダリング結果が短い/空だが例外は出ていないケースでは
    フォールバックが発生しないこと（誤診断防止の直接テスト）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(url="https://example.com/tiny", content_html="")
    _install_fake_browser(monkeypatch, page)

    httpx_called = {"value": False}

    def _fail_if_httpx_called(**kw):
        httpx_called["value"] = True
        raise AssertionError("httpx経路が呼ばれてはいけない")

    monkeypatch.setattr(web_tools.httpx, "Client", _fail_if_httpx_called)
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": ""})())

    web_tools.fetch_and_extract("https://example.com/tiny")
    assert httpx_called["value"] is False


# ---------------------------------------------------------------------------
# 6. SSRF route guard
# ---------------------------------------------------------------------------

class _FakeRoute:
    def __init__(self):
        self.aborted = False
        self.continued = False

    def abort(self):
        self.aborted = True

    def continue_(self):
        self.continued = True


class _FakeRequest:
    def __init__(self, url):
        self.url = url


def test_ssrf_route_guard_aborts_blocked_url(monkeypatch):
    """[Phase1テスト6] 検証NGなURL（プライベートIP解決させるフェイクDNS）への
    サブリソースリクエストがroute.abort()されること。"""
    def _raise(url):
        raise web_tools.SsrfBlockedError("blocked")

    monkeypatch.setattr(web_tools, "validate_url_for_fetch", _raise)
    route = _FakeRoute()
    web_tools._ssrf_route_guard(route, _FakeRequest("http://169.254.169.254/latest/meta-data/"))
    assert route.aborted is True
    assert route.continued is False


def test_ssrf_route_guard_continues_allowed_url(monkeypatch):
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    route = _FakeRoute()
    web_tools._ssrf_route_guard(route, _FakeRequest("https://example.com/style.css"))
    assert route.continued is True
    assert route.aborted is False


def test_playwright_registers_ssrf_route_guard(monkeypatch):
    """描画フェッチが実際にcontext.route("**/*", _ssrf_route_guard)を登録していること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(url="https://example.com/", content_html="<p>本文</p>")
    context = _install_fake_browser(monkeypatch, page)
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": "本文"})())

    web_tools.fetch_and_extract("https://example.com/")
    assert len(context.routed) == 1
    pattern, handler = context.routed[0]
    assert pattern == "**/*"
    assert handler is web_tools._ssrf_route_guard


# ---------------------------------------------------------------------------
# 7. 最終着地URLのSSRF再検証
# ---------------------------------------------------------------------------

def test_playwright_landed_url_ssrf_failure_propagates(monkeypatch):
    """[Phase1テスト7] Playwright着地後の最終URL（page.url）がSSRF検証NGなら
    例外化されること。"""
    def _validate(url):
        if "internal.example" in url:
            raise web_tools.SsrfBlockedError("内部アドレスへの着地を検知しました。")

    monkeypatch.setattr(web_tools, "validate_url_for_fetch", _validate)
    page = _FakePlaywrightPage(url="https://internal.example/secret", content_html="<p>本文</p>")
    _install_fake_browser(monkeypatch, page)

    with pytest.raises(web_tools.SsrfBlockedError):
        web_tools.fetch_and_extract("https://example.com/redirect-me")


# ---------------------------------------------------------------------------
# 8. 非HTML着地
# ---------------------------------------------------------------------------

def test_playwright_discards_result_when_landed_content_type_is_not_html(monkeypatch):
    """[Phase1テスト8] 着地レスポンスのContent-Typeがtext/htmlでない場合、Playwright結果を
    破棄しhttpx文書経路へフォールスルーすること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://example.com/download?id=123",
        response=_FakePlaywrightResponse(status=200, content_type="application/pdf"),
        content_html="<binary garbage>",
    )
    _install_fake_browser(monkeypatch, page)

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "application/pdf"}
        content = b"%PDF-1.4 real pdf bytes"
        url = "https://example.com/download?id=123"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": "PDF本文（httpx経由）"})())

    text = web_tools.fetch_and_extract("https://example.com/download?id=123")
    assert "PDF本文（httpx経由）" in text


# ---------------------------------------------------------------------------
# [Cline手動レビューR3] サイズ上限
# ---------------------------------------------------------------------------

def test_playwright_html_over_size_limit_falls_back_to_httpx(monkeypatch):
    """[Phase1テスト10・Cline手動レビューR3] Playwright経由のHTMLが_MAX_FETCH_BYTESを
    超える場合、httpx経路へフォールスルーすること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    huge_html = "<p>" + ("あ" * (web_tools._MAX_FETCH_BYTES + 1)) + "</p>"
    page = _FakePlaywrightPage(url="https://example.com/huge-spa", content_html=huge_html)
    _install_fake_browser(monkeypatch, page)

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<p>httpx\xe7\xb5\x8c\xe7\x94\xb1\xe3\x81\xae\xe6\x9c\xac\xe6\x96\x87</p>"
        url = "https://example.com/huge-spa"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": "httpx経由の本文"})())

    text = web_tools.fetch_and_extract("https://example.com/huge-spa")
    assert "httpx経由の本文" in text


# ---------------------------------------------------------------------------
# [Cline手動レビューR4] 4xx/5xx応答
# ---------------------------------------------------------------------------

def test_playwright_4xx_response_falls_back_to_httpx(monkeypatch):
    """[Phase1テスト11・Cline手動レビューR4] page.goto()の応答が4xx/5xxの場合、
    Playwright結果を破棄しhttpx経路へフォールスルーし、httpx側のraise_for_status()で
    従来通りエラー化されること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://example.com/not-found",
        response=_FakePlaywrightResponse(status=404, content_type="text/html"),
        content_html="<p>404ページ</p>",
    )
    _install_fake_browser(monkeypatch, page)

    class _FakeResp:
        status_code = 404
        headers = {"content-type": "text/html"}
        content = b"<p>404</p>"
        url = "https://example.com/not-found"

        next_request = None

        def raise_for_status(self):
            raise web_tools.httpx.HTTPStatusError("404", request=None, response=None)

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())

    with pytest.raises(web_tools.httpx.HTTPStatusError):
        web_tools.fetch_and_extract("https://example.com/not-found")


# ---------------------------------------------------------------------------
# ブラウザライフサイクル
# ---------------------------------------------------------------------------

def test_ensure_browser_reuses_existing_instance(monkeypatch):
    """[BL-335] プロセス生涯で1つのChromiumを起動・使い回す（毎回起動しない）。"""
    launch_calls = {"count": 0}

    class _FakeChromium:
        def launch(self, headless=True):
            launch_calls["count"] += 1
            return object()

    class _FakePlaywrightInstance:
        chromium = _FakeChromium()

        def stop(self):
            pass

    monkeypatch.setattr(web_tools, "_PLAYWRIGHT", None)
    monkeypatch.setattr(web_tools, "_BROWSER", None)

    import sys as _sys
    fake_module = type(_sys)("playwright.sync_api")
    fake_module.sync_playwright = lambda: type(
        "SP", (), {"start": lambda self: _FakePlaywrightInstance()}
    )()
    monkeypatch.setitem(_sys.modules, "playwright.sync_api", fake_module)

    b1 = web_tools._ensure_browser()
    b2 = web_tools._ensure_browser()
    assert b1 is b2
    assert launch_calls["count"] == 1
    web_tools._shutdown_browser()


# ---------------------------------------------------------------------------
# [Cline手動レビューF1] ブラウザ起動/context生成/route登録の失敗もフォールバック対象
# ---------------------------------------------------------------------------

def _install_fake_httpx_fallback(monkeypatch, body="httpxフォールバック本文"):
    """httpx経路がbodyを返すようfetch_and_extractの後段をモックする。"""
    class _FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = body.encode("utf-8")
        url = "https://example.com/"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())
    monkeypatch.setattr(web_tools._MARKITDOWN, "convert_stream",
                         lambda *a, **kw: type("R", (), {"text_content": body})())


def test_playwright_browser_launch_failure_falls_back_to_httpx(monkeypatch):
    """[Cline手動レビューF1] _ensure_browser()自体がPlaywrightErrorを送出しても、
    docstring契約どおりhttpxフォールバックへ委ねること（以前はtry外にあり伝播していた）。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "_PAGES_RENDERED_SINCE_LAUNCH", 0)

    def _raise_launch():
        raise PlaywrightError("Executable doesn't exist. chromium未インストール")

    monkeypatch.setattr(web_tools, "_ensure_browser", _raise_launch)
    _install_fake_httpx_fallback(monkeypatch)

    text = web_tools.fetch_and_extract("https://example.com/")
    assert "httpxフォールバック本文" in text


def test_playwright_context_creation_failure_falls_back_to_httpx(monkeypatch):
    """[Cline手動レビューF1] browser.new_context()の失敗もhttpxフォールバックへ委ねること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "_PAGES_RENDERED_SINCE_LAUNCH", 0)

    class _FailingBrowser:
        def new_context(self, user_agent=None):
            raise PlaywrightError("context creation failed")

    monkeypatch.setattr(web_tools, "_ensure_browser", lambda: _FailingBrowser())
    _install_fake_httpx_fallback(monkeypatch)

    text = web_tools.fetch_and_extract("https://example.com/")
    assert "httpxフォールバック本文" in text


# ---------------------------------------------------------------------------
# [Cline手動レビューF2] 相対リンク解決は着地URL基準
# ---------------------------------------------------------------------------

def test_playwright_relative_links_resolved_against_landed_url(monkeypatch):
    """[Cline手動レビューF2] リダイレクトでホストが変わった場合、相対リンクは
    元urlでなくpage.url（着地URL）を基準に解決されること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    page = _FakePlaywrightPage(
        url="https://landed.example.com/dir/",
        content_html="<p>本文</p>",
    )
    _install_fake_browser(monkeypatch, page)
    monkeypatch.setattr(
        web_tools._MARKITDOWN, "convert_stream",
        lambda *a, **kw: type("R", (), {"text_content": "[相対リンク](sub.html)"})(),
    )

    text = web_tools.fetch_and_extract("https://example.com/redirect-me")
    assert "[相対リンク](https://landed.example.com/dir/sub.html)" in text


def test_httpx_relative_links_resolved_against_landed_url(monkeypatch):
    """[Cline手動レビューF2] httpx経路でもリダイレクト後の着地URル（resp.url）を
    相対リンク解決の基準にすること。"""
    monkeypatch.setattr(web_tools, "validate_url_for_fetch", lambda url: None)
    monkeypatch.setattr(web_tools, "_fetch_html_via_playwright", lambda url: None)

    class _FakeResp:
        status_code = 200
        headers = {"content-type": "text/html"}
        content = b"<p>httpx fallback</p>"
        url = "https://landed.example.com/dir/"

        next_request = None

        def raise_for_status(self):
            pass

    class _FakeClient:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def build_request(self, method, url, headers=None):
            return type("Req", (), {"url": url})()

        def send(self, request, follow_redirects=False):
            return _FakeResp()

    monkeypatch.setattr(web_tools.httpx, "Client", lambda **kw: _FakeClient())
    monkeypatch.setattr(
        web_tools._MARKITDOWN, "convert_stream",
        lambda *a, **kw: type("R", (), {"text_content": "[相対リンク](sub.html)"})(),
    )

    text = web_tools.fetch_and_extract("https://example.com/redirect-me")
    assert "[相対リンク](https://landed.example.com/dir/sub.html)" in text


def test_shutdown_browser_resets_state(monkeypatch):
    closed = {"browser": False, "playwright": False}

    class _FakeBrowser:
        def close(self):
            closed["browser"] = True

    class _FakePW:
        def stop(self):
            closed["playwright"] = True

    monkeypatch.setattr(web_tools, "_BROWSER", _FakeBrowser())
    monkeypatch.setattr(web_tools, "_PLAYWRIGHT", _FakePW())
    monkeypatch.setattr(web_tools, "_PAGES_RENDERED_SINCE_LAUNCH", 12)

    web_tools._shutdown_browser()
    assert closed == {"browser": True, "playwright": True}
    assert web_tools._BROWSER is None
    assert web_tools._PLAYWRIGHT is None
    assert web_tools._PAGES_RENDERED_SINCE_LAUNCH == 0
