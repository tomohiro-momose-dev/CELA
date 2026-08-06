"""
BL-184: web_search / web_fetch / read_reference_file ツール群。

設計: docs/design/back_log/BL-184/BL184_basic_design.md
独立レビュー（decision_lineage.md 論点139）を受け、cela_main.py本体（肥大化を避けるため）
から切り出した新規モジュール。Provider抽象化・SSRF検証・HTMLテキスト抽出・キャッシュ管理・
ツールハンドラ本体をここに置く。ツールスキーマ定数（WEB_SEARCH_TOOL等）・TOOL_DISPATCHへの
登録・LineageState/AppConfigへのフィールド追加はcela_main.py側で行う（本モジュールは
cela_main.pyをimportしない、循環import回避）。

ハンドラは`(args: dict, state: dict, config: dict)`という、cela_main.pyの既存TOOL_DISPATCH
統一シグネチャ（BL-131）と同じ引数構成を取る。state/configはプレーンなdictとして扱い、
cela_main.py固有のTypedDict定義には依存しない。
"""

from __future__ import annotations

import hashlib
import html.parser
import ipaddress
import os
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, unquote, urlparse

import httpx

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

WEB_CACHE_DIR = "web_cache"
_REQUEST_TIMEOUT_SECONDS = 10.0
_MAX_FETCH_BYTES = 2 * 1024 * 1024  # 2MB
_MAX_OUTPUT_CHARS = 15000
_MAX_READ_REFERENCE_CHARS = 10000
_DDG_MIN_REQUEST_INTERVAL_SECONDS = 1.0
_ALLOWED_CONTENT_TYPE_PREFIXES = ("text/",)
_USER_AGENT = "Mozilla/5.0 (compatible; CELA-research-bot/1.0)"

_DEFAULT_MAX_WEB_SEARCH_CALLS = 20
_DEFAULT_MAX_WEB_FETCH_CALLS = 20


class WebSearchConfigError(Exception):
    """[BL-184] Providerが利用不可（未対応プロバイダ・APIキー未設定等）の場合に送出する。"""


class SsrfBlockedError(Exception):
    """[BL-184] web_fetchのSSRF/安全性検証（スキーム・アドレス範囲・リダイレクト・
    Content-Type）に違反した場合に送出する。"""


# ---------------------------------------------------------------------------
# Provider抽象化（web_search）
# ---------------------------------------------------------------------------

class WebSearchProvider(Protocol):
    def search(self, query: str, max_results: int) -> list[dict]:
        """[{'title': str, 'url': str, 'snippet': str}, ...] を返す。失敗時は例外を送出する。"""
        ...


def _extract_real_url(href: str) -> str:
    """[BL-184] DuckDuckGo HTML版の結果リンクは自サイト経由のリダイレクト
    （`//duckduckgo.com/l/?uddg=<url-encoded target>&rut=...`）になっているため、
    `uddg`クエリパラメータから実際のURLを復元する（実レスポンスを2026-08-06に確認済み、
    docs/refs/duckduckgo/html_endpoint_notes.md参照）。"""
    if not href:
        return ""
    normalized = "https:" + href if href.startswith("//") else href
    parsed = urlparse(normalized)
    qs = parse_qs(parsed.query)
    if qs.get("uddg"):
        return unquote(qs["uddg"][0])
    return normalized


class _DdgHtmlParser(html.parser.HTMLParser):
    """[BL-184] html.duckduckgo.com/html/ の検索結果ページから{title, url, snippet}を
    抽出する軽量パーサ。実レスポンス（2026-08-06確認）のマークアップ:
        <a class="result__a" href="//duckduckgo.com/l/?uddg=...">タイトル</a>
        <a class="result__snippet" href="...">スニペット本文（<b>強調</b>を含む）</a>
    非公式スクレイピングのため、DuckDuckGo側のマークアップ変更で壊れる可能性がある
    （BL184_basic_design.md記載のリスク）。
    """

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict] = []
        self._current: dict | None = None
        self._capturing: str | None = None  # "title" | "snippet" | None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag != "a":
            return
        attrs_dict = dict(attrs)
        classes = (attrs_dict.get("class") or "").split()
        href = attrs_dict.get("href", "") or ""
        if "result__a" in classes:
            # 新しい結果の開始。直前の結果が確定していれば先に確定させる。
            if self._current is not None:
                self.results.append(self._current)
            self._current = {"title": "", "url": href, "snippet": ""}
            self._capturing = "title"
        elif "result__snippet" in classes and self._current is not None:
            self._capturing = "snippet"

    def handle_endtag(self, tag: str) -> None:
        if tag == "a":
            self._capturing = None

    def handle_data(self, data: str) -> None:
        if self._capturing == "title" and self._current is not None:
            self._current["title"] += data
        elif self._capturing == "snippet" and self._current is not None:
            self._current["snippet"] += data

    def close(self) -> None:
        super().close()
        if self._current is not None:
            self.results.append(self._current)
            self._current = None


_last_ddg_request_at = 0.0


class DuckDuckGoSearchProvider:
    """[BL-184] html.duckduckgo.com/html/ をGET+自前パースする非公式スクレイピング実装。
    公式検索APIが存在しないための代替（Instant Answer APIは通常の検索結果を返さないため
    不適）。APIキー不要。GET+クエリパラメータで動作することを実レスポンスで確認済み
    （docs/refs/duckduckgo/html_endpoint_notes.md）。
    """

    _SEARCH_URL = "https://html.duckduckgo.com/html/"

    def search(self, query: str, max_results: int) -> list[dict]:
        global _last_ddg_request_at
        # [SAFETY] レート制限・一時ブロック回避のためのスロットリング（BL184_basic_design.md）。
        elapsed = time.monotonic() - _last_ddg_request_at
        if elapsed < _DDG_MIN_REQUEST_INTERVAL_SECONDS:
            time.sleep(_DDG_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
        resp = httpx.get(
            self._SEARCH_URL,
            params={"q": query},
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={"User-Agent": _USER_AGENT},
        )
        _last_ddg_request_at = time.monotonic()
        resp.raise_for_status()
        # [BL-184][実測 2026-08-07] 数回のリクエストだけで即座にBot対策の画像認証
        # チャレンジ（`anomaly-modal`）が返ることを確認した（docs/refs/duckduckgo/
        # html_endpoint_notes.md）。空の結果リストを黙って返すと、LLMが「Web上に
        # 情報が存在しない」と誤解する危険があるため、明示的なエラーとして送出する。
        if "anomaly-modal" in resp.text or "challenge-form" in resp.text:
            raise WebSearchConfigError(
                "web_search is temporarily blocked: DuckDuckGoのBot対策チャレンジが"
                "発生しました。時間をおくか、別のProvider（例: CELA_WEB_SEARCH_PROVIDER=brave）"
                "への切り替えを検討してください。"
            )
        parser = _DdgHtmlParser()
        parser.feed(resp.text)
        parser.close()
        results = []
        for r in parser.results[:max_results]:
            results.append({
                "title": r["title"].strip(),
                "url": _extract_real_url(r["url"]),
                "snippet": r["snippet"].strip(),
            })
        return results


_BRAVE_API_KEY_ENV_VAR = "CELA_BRAVE_SEARCH_API_KEY"


class BraveSearchProvider:
    """[BL-184] Brave Search API（正式API、無料枠あり）を使う実装。DuckDuckGoの非公式
    スクレイピングが実測でBot対策チャレンジに即ブロックされたため（上記コメント参照）、
    既定Providerとして採用した（docs/refs/brave_search/api_notes.md、
    decision_lineage.md 論点142）。
    """

    _SEARCH_URL = "https://api.search.brave.com/res/v1/web/search"

    def search(self, query: str, max_results: int) -> list[dict]:
        api_key = os.environ.get(_BRAVE_API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise WebSearchConfigError(
                f"web_search is not configured: 環境変数{_BRAVE_API_KEY_ENV_VAR}が"
                "設定されていません。Brave Search APIキーを取得し設定してください "
                "（https://brave.com/search/api/）。"
            )
        resp = httpx.get(
            self._SEARCH_URL,
            params={"q": query, "count": max(1, min(max_results, 20))},
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={
                "Accept": "application/json",
                "Accept-Encoding": "gzip",
                "X-Subscription-Token": api_key,
            },
        )
        resp.raise_for_status()
        payload = resp.json()
        raw_results = (payload.get("web") or {}).get("results") or []
        results = []
        for r in raw_results[:max_results]:
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": r.get("description", ""),
            })
        return results


def get_search_provider() -> WebSearchProvider:
    """[BL-184] `CELA_WEB_SEARCH_PROVIDER`環境変数（既定: brave）を見てProviderを選択する
    ファクトリ。当初はDuckDuckGo（非公式スクレイピング、APIキー不要）を既定としていたが、
    実測でBot対策チャレンジに即ブロックされることを確認したため、既定をBrave Search API
    （正式API、APIキー要）へ変更した（`docs/refs/duckduckgo/html_endpoint_notes.md`の
    追記、decision_lineage.md 論点142）。DuckDuckGo実装は`CELA_WEB_SEARCH_PROVIDER=
    duckduckgo`で引き続き選択可能（Provider抽象化の意図通り）。"""
    provider_name = os.environ.get("CELA_WEB_SEARCH_PROVIDER", "brave").strip().lower()
    if provider_name == "brave":
        return BraveSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    raise WebSearchConfigError(
        f"web_search is not configured: 未対応のプロバイダです（CELA_WEB_SEARCH_PROVIDER="
        f"{provider_name!r}）。現在実装済みなのは'brave'/'duckduckgo'です。"
    )


# ---------------------------------------------------------------------------
# SSRF対策（web_fetch）
# ---------------------------------------------------------------------------

def validate_url_for_fetch(url: str) -> None:
    """[BL-184][SAFETY] web_fetch対象URLの安全性を検証する。スキームはhttp/httpsのみ許可、
    ホスト名解決後の全IPがprivate/loopback/link-local/multicast/reserved/unspecifiedで
    ないことを確認する。違反時はSsrfBlockedErrorを送出する。

    [SAFETY][既知の残存リスク] ここでの検証後、実際のHTTPリクエスト（httpx）が独立に
    再度DNS解決を行うため、検証時と接続時で異なるIPに切り替わるDNSリバインディング
    （TOCTOU）を完全には防げない。真の対策（検証済みIPへ直接接続しHostヘッダのみ元の
    ホスト名を送る等）はTLS証明書検証との両立が複雑なため、本リリースでは見送り、
    既知のリスクとして記録する（BL184_basic_design.md）。CELAはローカル開発者が制御する
    単一プロセスとして動作し、悪意ある第三者が同一プロセスの実行タイミングに合わせて
    能動的にDNSレコードを切り替える現実的な脅威シナリオは低いと判断した。
    """
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise SsrfBlockedError(f"許可されていないスキームです: {parsed.scheme!r}（http/httpsのみ許可）")
    hostname = parsed.hostname
    if not hostname:
        raise SsrfBlockedError("URLからホスト名を取得できませんでした。")
    try:
        addrinfos = socket.getaddrinfo(hostname, None)
    except socket.gaierror as e:
        raise SsrfBlockedError(f"ホスト名を解決できませんでした: {hostname} ({e})")
    for info in addrinfos:
        ip = ipaddress.ip_address(info[4][0])
        if (ip.is_private or ip.is_loopback or ip.is_link_local
                or ip.is_multicast or ip.is_reserved or ip.is_unspecified):
            raise SsrfBlockedError(
                f"内部/予約済みアドレスへのアクセスは禁止されています: {hostname} -> {ip}"
            )


class _HtmlTextExtractor(html.parser.HTMLParser):
    """[BL-184] 標準ライブラリのみで実装する軽量HTML→テキスト変換。`<script>`/`<style>`
    タグの内容は本文抽出の対象外とする（含めるとJS/CSSノイズでプロンプトが肥大化するため、
    BL184_basic_design.mdの必須要件）。"""

    _SKIP_TAGS = {"script", "style"}

    def __init__(self) -> None:
        super().__init__()
        self._skip_depth = 0
        self._parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth == 0:
            stripped = data.strip()
            if stripped:
                self._parts.append(stripped)

    def get_text(self) -> str:
        return "\n".join(self._parts)


def fetch_and_extract(url: str) -> str:
    """[BL-184] URLを検証・取得し、HTML本文をプレーンテキストへ変換して返す。
    リダイレクト（3xx）は追跡しない（リダイレクト先を明示的にweb_fetchすることを要求し、
    リダイレクト経由のSSRFバイパスを構造的に防ぐ）。失敗時はSsrfBlockedError/
    httpx例外を送出する（呼び出し元でcatchしてエラーレスポンスへ変換すること）。
    """
    validate_url_for_fetch(url)
    with httpx.Client(follow_redirects=False, timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        resp = client.get(url, headers={"User-Agent": _USER_AGENT})
    if resp.status_code in (301, 302, 303, 307, 308):
        raise SsrfBlockedError(
            f"リダイレクトは追跡していません（status={resp.status_code}）。"
            "リダイレクト先URLを確認し、明示的にweb_fetchしてください。"
        )
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    if not any(content_type.startswith(p) for p in _ALLOWED_CONTENT_TYPE_PREFIXES):
        raise SsrfBlockedError(f"許可されていないContent-Typeです: {content_type!r}（text/*のみ許可）")
    raw = resp.content
    if len(raw) > _MAX_FETCH_BYTES:
        raw = raw[:_MAX_FETCH_BYTES]
    text = raw.decode(resp.encoding or "utf-8", errors="replace")
    extractor = _HtmlTextExtractor()
    extractor.feed(text)
    extractor.close()
    extracted = extractor.get_text()
    if len(extracted) > _MAX_OUTPUT_CHARS:
        extracted = extracted[:_MAX_OUTPUT_CHARS] + "\n[Fetch Output truncated]"
    return extracted


# ---------------------------------------------------------------------------
# キャッシュ（web_fetch結果 / read_reference_fileの読み取り対象）
# ---------------------------------------------------------------------------

def cache_file_path(run_id: str, url: str) -> Path:
    """[BL-184] `web_cache/<run_id>/<sha256(url)[:16]>.md`のパスを返す。"""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Path(WEB_CACHE_DIR) / run_id / f"{digest}.md"


def write_cache(path: Path, url: str, text: str) -> None:
    """[BL-184] AGENTS.md §9のsource URL+fetch date付与パターンと同型のヘッダを付けて
    キャッシュファイルへ書き出す。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fetched_at = datetime.now(timezone.utc).isoformat()
    header = f"# Source: {url}\n# Fetched: {fetched_at}\n\n"
    path.write_text(header + text, encoding="utf-8")


def strip_cache_header(content: str) -> str:
    """[BL-184] write_cacheが付与したヘッダ（Source/Fetched行＋空行）を取り除き、本文のみ
    返す。ヘッダが見つからない場合はそのまま返す。"""
    parts = content.split("\n\n", 1)
    if len(parts) == 2 and parts[0].startswith("# Source:"):
        return parts[1]
    return content


# ---------------------------------------------------------------------------
# ツールハンドラ本体
# ---------------------------------------------------------------------------

def web_search_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-184] `web_search`ツールのハンドラ。run単位の呼び出し回数上限
    （`config["max_web_search_calls"]`、既定20）を超えた場合はエラーを返す。"""
    query = (args.get("query") or "").strip()
    if not query:
        return {"status": "error", "message": "queryは必須です。"}
    max_results = args.get("max_results", 5)
    try:
        max_results = max(1, min(int(max_results), 10))
    except (TypeError, ValueError):
        max_results = 5

    count = state.get("web_search_call_count", 0)
    limit = config.get("max_web_search_calls", _DEFAULT_MAX_WEB_SEARCH_CALLS)
    if count >= limit:
        return {
            "status": "error",
            "message": f"web_searchの呼び出し上限（{limit}回/run）に達しました。",
        }

    try:
        provider = get_search_provider()
        results = provider.search(query, max_results)
    except WebSearchConfigError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001 - 外部通信の失敗は種類を問わずエラーレスポンス化する
        return {"status": "error", "message": f"web_search失敗: {e}"}

    state["web_search_call_count"] = count + 1
    return {"results": results}


def web_fetch_handler(args: dict, state: dict, config: dict) -> dict | str:
    """[BL-184] `web_fetch`ツールのハンドラ。キャッシュヒット時はrun単位の呼び出し回数
    カウントを消費しない（BL184_basic_design.md）。"""
    url = (args.get("url") or "").strip()
    if not url:
        return {"status": "error", "message": "urlは必須です。"}
    run_id = state.get("run_id", "")

    cache_path = cache_file_path(run_id, url)
    if cache_path.exists():
        return strip_cache_header(cache_path.read_text(encoding="utf-8"))[:_MAX_OUTPUT_CHARS]

    count = state.get("web_fetch_call_count", 0)
    limit = config.get("max_web_fetch_calls", _DEFAULT_MAX_WEB_FETCH_CALLS)
    if count >= limit:
        return {
            "status": "error",
            "message": f"web_fetchの呼び出し上限（{limit}回/run）に達しました。",
        }

    try:
        text = fetch_and_extract(url)
    except SsrfBlockedError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"web_fetch失敗: {e}"}

    state["web_fetch_call_count"] = count + 1
    write_cache(cache_path, url, text)
    return text[:_MAX_OUTPUT_CHARS]


def read_reference_file_handler(args: dict, state: dict) -> dict | str:
    """[BL-184] `read_reference_file`ツールのハンドラ。ベースディレクトリは
    `web_cache/<run_id>/`一本に限定する（BL184_basic_design.md）。`read_deliverable_file`
    と同じ`Path(...).resolve()` → `relative_to(base_dir)`のresolve-and-containパターンで
    パス脱出を防ぐ。`keyword`指定時は各キャッシュファイル先頭の`# Source: {url}`行への
    部分一致検索を行う（Detectorが`citations`のURLから逆引きする経路、必須要件）。
    """
    run_id = state.get("run_id", "")
    base_dir = (Path(WEB_CACHE_DIR) / run_id).resolve()
    path = args.get("path") or ""
    keyword = args.get("keyword") or ""

    if path:
        try:
            resolved = (base_dir / path).resolve()
            resolved.relative_to(base_dir)
        except ValueError:
            return {"status": "error", "message": "web_cache外へのアクセスは禁止されています。"}
        if not resolved.exists() or not resolved.is_file():
            return {"status": "not_found", "message": f"ファイルが見つかりません: {path}"}
        return resolved.read_text(encoding="utf-8")[:_MAX_READ_REFERENCE_CHARS]

    if keyword:
        if not base_dir.exists():
            return {"status": "not_found", "message": "このrunにはまだキャッシュファイルがありません。"}
        matches: list[str] = []
        for f in sorted(base_dir.glob("*.md")):
            head = f.read_text(encoding="utf-8", errors="ignore")[:500]
            if keyword in head:
                matches.append(f.name)
        if not matches:
            return {"status": "not_found", "message": f"'{keyword}'に該当するキャッシュファイルが見つかりませんでした。"}
        if len(matches) > 1:
            return {
                "status": "multiple_matches",
                "message": "複数のキャッシュファイルが該当しました。pathを指定して再取得してください。",
                "candidates": matches,
            }
        return (base_dir / matches[0]).read_text(encoding="utf-8")[:_MAX_READ_REFERENCE_CHARS]

    return {"status": "error", "message": "pathまたはkeywordのいずれかを指定してください。"}
