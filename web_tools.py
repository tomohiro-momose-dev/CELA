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

import atexit
import hashlib
import html.parser
import io
import ipaddress
import os
import re
import socket
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from urllib.parse import parse_qs, unquote, urljoin, urlparse

import httpx
import pypdfium2 as pdfium
from markitdown import MarkItDown, MarkItDownException, StreamInfo

# ---------------------------------------------------------------------------
# 定数
# ---------------------------------------------------------------------------

WEB_CACHE_DIR = "web_cache"
# [BL-221] 50MB到達を見込んだダウンロードが10秒のタイムアウトに収まらない実例（低速な
# 自治体サーバー等）を避けるため、サイズ上限の引き上げに合わせて延長する。
_REQUEST_TIMEOUT_SECONDS = 30.0
# [BL-221] 8MB→50MBへユーザー承認のもと引き上げ。ダウンロード自体はもはや容量では拒否せず、
# markitdown変換後の全文はwrite_cacheでweb_cache/へそのまま保存される（切り詰めなし）。
# モデルへの初回返却（_MAX_OUTPUT_CHARS）とread_reference_fileの素読み（_MAX_READ_REFERENCE_CHARS）
# は引き続きトークン消費を抑えるため切り詰めるが、read_reference_fileのgrepパラメータ
# （BL-221で新設）でキャッシュ全文から必要箇所を前後の文脈付きで検索できる。
_MAX_FETCH_BYTES = 50 * 1024 * 1024  # 50MB
_MAX_OUTPUT_CHARS = 15000
_MAX_READ_REFERENCE_CHARS = 10000
_DDG_MIN_REQUEST_INTERVAL_SECONDS = 1.0
# [BL-188] 公的機関・自治体の一次資料はPDF配布が多く、text/*限定ではweb_fetchで読めない
# 実例が実ドライラン（log/2026-08-07/1244）で確認されたため、application/pdfを追加許可する。
# [BL-218] 自治体サイトはWord/Excel等のOffice文書も配布することが多い（ユーザー指摘：茅野市HP）。
# markitdownは各コンバータが対応するmimetype/拡張子のどちらかが一致すれば変換できるため、
# ここでの事前許可判定もContent-Typeと「URLパス末尾の拡張子」の両方を見る——自治体サイトは
# Content-Typeが不正確（application/octet-stream等）なことも珍しくなく、拡張子だけが正しい
# 手がかりというケースを取りこぼさないため。
# 対象は意図的に「文書系」に限定する：Zip（zip爆弾的なリソース消費リスクがあり、SSRF対策の
# サイズ上限（_MAX_FETCH_BYTES）は圧縮後サイズにしか効かない）、Image/Audio（markitdownの
# vision/音声変換にはllm_clientが別途必要で、このプロジェクトでは未設定のため実質使えない）は
# 除外した（ユーザー承認）。
_DOCUMENT_MIME_TYPE_PREFIXES = (
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",  # .docx
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",        # .xlsx
    "application/vnd.openxmlformats-officedocument.presentationml",             # .pptx
    "application/vnd.ms-excel",  # .xls（旧形式）
    "application/excel",         # .xls（旧形式の別表記）
    "application/csv",           # text/csvは既存のtext/プレフィックスで既に許可済み
    "application/epub",
    "application/epub+zip",
    "application/x-epub+zip",
)
_DOCUMENT_EXTENSIONS = (".pdf", ".docx", ".xlsx", ".xls", ".pptx", ".epub", ".csv")
_USER_AGENT = "Mozilla/5.0 (compatible; CELA-research-bot/1.0)"

# [BL-335] PlaywrightのDOMContentLoaded待機タイムアウト。
_PLAYWRIGHT_NAV_TIMEOUT_MS = 30_000
# [BL-335] domcontentloaded後、ベストエフォートで待つnetworkidleのタイムアウト。SPAが
# 継続ポーリングし続けidleに到達しないページは珍しくないため、タイムアウトしても致命的
# 失敗にはしない（取れた分でconvert_streamへ進む）。
_PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS = 5_000
# [BL-335] Chromiumの既知のメモリリーク傾向に対する二次防御。1runで数十〜数百の未
# キャッシュURLを連続レンダリングする可能性があるため、一定ページ数ごとにブラウザ
# プロセス自体を再起動する。
_PLAYWRIGHT_RECYCLE_AFTER_N_PAGES = 50
# [BL-335] Phase 2（PDF画像化）・Phase 3（xlsx pandas読み込み）が元の生バイト列を必要と
# するため、markitdown変換後のMarkdownとは別に、PDF/xlsx/xlsのみ生バイトも保存する
# （AGENTS.md §15.4「入口を作ったら出口も」— 消費経路がある形式に限定）。
_RAW_CACHEABLE_EXTENSIONS = (".pdf", ".xlsx", ".xls")
# [Cline手動レビュー指摘1・BL-335] httpx.Client(follow_redirects=True)のような自動追従は
# 中間ホップへ実際に接続してから最終URLだけを検証するため、内部アドレスへの中間リダイレクトが
# SSRF検証をすり抜けて実接続してしまう（blind SSRF）。手動で1ホップずつ追従するため、
# 無限リダイレクトを防ぐ上限をhttpxの既定（20）より保守的に設定する。
_MAX_REDIRECT_HOPS = 10

# [BL-188] HTML/PDFの本文抽出をMicrosoft markitdown（Markdown化）へ一本化する。
# ユーザー指摘：pypdf/html.parserベースの独自抽出は表構造・見出し階層・リンクの文脈的位置を
# 失い、実ドライランで表が単語の羅列になる実害を確認した。markitdownはHTML/PDFいずれも
# 見出し（#/##）・表（|---|）・リンク（[text](url)、本文中の自然な位置に維持）を保った
# Markdownへ変換できることを実データ（国交省PDF・RoAD to the L4のHTML）で検証済み。
# 依存重量（onnxruntime/numpy/Pillow等、約100MB）は許容とユーザーが判断（情報取得の質を
# 依存の軽さより優先）。MarkItDownインスタンスは状態を持たないため再利用可能、モジュール
# レベルで1つだけ生成する。
_MARKITDOWN = MarkItDown()
# markitdown出力中の相対リンク（`](/path)`等）を絶対URLへ解決するための正規表現。
# markitdownのconvert_stream(url=...)はソースURLをメタデータとして使うのみで相対リンクの
# 自動解決は行わないため（実データで確認済み）、後処理で解決する。
_MARKDOWN_LINK_RE = re.compile(r"\]\(([^)\s]+)")

_DEFAULT_MAX_WEB_SEARCH_CALLS = 400  # [BL-314] configにキーが無い場合の最終フォールバック。CLI既定(400)と揃える。
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
        # [BL-270] 402 Payment Requiredは、Brave Search APIの契約上の利用上限（無料枠等）
        # に到達した場合に返る。他のHTTPエラー（一時的なネットワーク不調等）とは異なり、
        # 同じrun内でリトライしても回復する見込みが無いため、生のhttpxエラー文字列を
        # そのままLLMへ返すのではなく、WebSearchConfigError（既に「APIキー未設定」等の
        # 恒久的な利用不可状態を表現している既存の型）に載せ、web_search_handler側の
        # 短絡ロジック（一度検知したら以後の呼び出しはAPIを叩かず同じ説明を即座に返す）
        # へ合流させる。
        if getattr(resp, "status_code", None) == 402:
            raise WebSearchConfigError(
                "web_search is temporarily unavailable: Brave Search APIの利用上限"
                "（無料枠等）に達したため、402 Payment Requiredが返されました。この上限は"
                "run内で待っても回復しません。今回のrunでは、read_reference_file"
                "（過去にweb_fetchで取得・キャッシュ済みのページ本文をkeyword検索、呼び出し"
                "回数上限を消費しない）で既に調査済みの情報が無いか先に確認し、それでも"
                "見つからなければ、既に判明している公式サイトURLへweb_fetchを直接呼んで"
                "代替してください。"
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


_EXA_API_KEY_ENV_VAR = "EXA_API_KEY"


class ExaSearchProvider:
    """[BL-271] Exa Search API（正式API、AI検索特化、APIキー要）を使う実装。
    BraveSearchProvider/DuckDuckGoSearchProviderと同じくraw httpx呼び出しで実装し、
    公式SDK（`exa-py`）は新規依存を避けるため使わない（ユーザー承認）。
    `CELA_WEB_SEARCH_PROVIDER=exa`で手動選択できる、既定Provider（brave）の代替
    （BL-270のような自動フォールバックは対象外、Provider抽象化の意図通り手動切替のみ）。
    REST仕様は`docs/refs/exa/search_api_notes.md`（2026-08-26取得）を参照。
    """

    _SEARCH_URL = "https://api.exa.ai/search"

    def search(self, query: str, max_results: int) -> list[dict]:
        api_key = os.environ.get(_EXA_API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise WebSearchConfigError(
                f"web_search is not configured: 環境変数{_EXA_API_KEY_ENV_VAR}が"
                "設定されていません。Exa APIキーを取得し設定してください "
                "（https://dashboard.exa.ai）。"
            )
        resp = httpx.post(
            self._SEARCH_URL,
            json={
                "query": query,
                "type": "auto",
                "numResults": max(1, min(max_results, 10)),
                "contents": {"highlights": True},
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
        )
        # [BL-271] 401（APIキー無効・欠落）・429（レート制限／利用上限超過）は、Braveの
        # 402（BL-270）と同じく「run内では回復しない、プロバイダ側の利用不可」カテゴリ。
        # HTTPステータスコード自体はBraveと異なるが意味論的に同型のため、同じ
        # WebSearchConfigError→web_search_handlerの短絡ロジックへ合流させる。
        _status = getattr(resp, "status_code", None)
        if _status == 401:
            raise WebSearchConfigError(
                "web_search is not configured: Exa Search APIキーが無効です。"
                f"環境変数{_EXA_API_KEY_ENV_VAR}の値を確認してください"
                "（https://dashboard.exa.ai）。"
            )
        if _status == 429:
            raise WebSearchConfigError(
                "web_search is temporarily unavailable: Exa Search APIのレート制限・"
                "利用上限に達したため、429 Rate limit exceededが返されました。この上限は"
                "run内で待っても回復しません。今回のrunでは、read_reference_file"
                "（過去にweb_fetchで取得・キャッシュ済みのページ本文をkeyword検索、呼び出し"
                "回数上限を消費しない）で既に調査済みの情報が無いか先に確認し、それでも"
                "見つからなければ、既に判明している公式サイトURLへweb_fetchを直接呼んで"
                "代替してください。"
            )
        resp.raise_for_status()
        payload = resp.json()
        raw_results = payload.get("results") or []
        results = []
        for r in raw_results[:max_results]:
            # [BL-271] Exaは単一のsnippet文字列ではなく、クエリ関連抜粋の配列
            # （highlights）を返す。CELAのWebSearchProvider契約（{title, url, snippet}）
            # に合わせ、複数件あれば結合する。
            highlights = r.get("highlights") or []
            results.append({
                "title": r.get("title", ""),
                "url": r.get("url", ""),
                "snippet": " / ".join(h for h in highlights if h),
            })
        return results


def get_search_provider() -> WebSearchProvider:
    """[BL-184] `CELA_WEB_SEARCH_PROVIDER`環境変数（既定: brave）を見てProviderを選択する
    ファクトリ。当初はDuckDuckGo（非公式スクレイピング、APIキー不要）を既定としていたが、
    実測でBot対策チャレンジに即ブロックされることを確認したため、既定をBrave Search API
    （正式API、APIキー要）へ変更した（`docs/refs/duckduckgo/html_endpoint_notes.md`の
    追記、decision_lineage.md 論点142）。DuckDuckGo実装は`CELA_WEB_SEARCH_PROVIDER=
    duckduckgo`で引き続き選択可能（Provider抽象化の意図通り）。[BL-271] Exa Search API
    も`CELA_WEB_SEARCH_PROVIDER=exa`で選択可能（Braveの利用上限到達時の手動代替）。"""
    provider_name = os.environ.get("CELA_WEB_SEARCH_PROVIDER", "brave").strip().lower()
    if provider_name == "brave":
        return BraveSearchProvider()
    if provider_name == "duckduckgo":
        return DuckDuckGoSearchProvider()
    if provider_name == "exa":
        return ExaSearchProvider()
    raise WebSearchConfigError(
        f"web_search is not configured: 未対応のプロバイダです（CELA_WEB_SEARCH_PROVIDER="
        f"{provider_name!r}）。現在実装済みなのは'brave'/'duckduckgo'/'exa'です。"
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


# ---------------------------------------------------------------------------
# Playwright描画フェッチ（BL-335）
# ---------------------------------------------------------------------------
# [BL-335] web_fetchの既定パス。クライアントサイドJS描画コンテンツが静的httpx取得では
# 取得できない実害（CAMPFIREクラウドファンディングページ等、docs/design/back_log/BL-335/
# BL335_basic_design.md参照）を受けて導入した。web_fetchはURLキーのグローバル・永続
# キャッシュ（BL-200）を持つため、Playwrightの起動コストは「URLごとに生涯1回」しか
# 発生しない——毎回クエリが変わりキャッシュヒットしない検索自動化（D-157で依存重量を
# 理由に見送られた）とはリスクプロファイルが異なる。
_PLAYWRIGHT = None            # sync_playwright().start()の戻り値
_BROWSER = None                # Chromium Browserインスタンス（プロセス生涯で1つ）
_PAGES_RENDERED_SINCE_LAUNCH = 0


def _ensure_browser():
    """[BL-335] プロセス生涯で1つのChromiumを起動・使い回す遅延シングルトン。
    _PythonReplSession（cela_main.py、BL-014）の「起動コストを毎回払わない」思想と同型。
    1ページごとに新規BrowserContext/Pageを作るため、ブラウザ自体の使い回しは安全
    （ページ間の状態共有はcontext単位で分離される）。"""
    global _PLAYWRIGHT, _BROWSER
    if _BROWSER is not None:
        return _BROWSER
    from playwright.sync_api import sync_playwright
    _PLAYWRIGHT = sync_playwright().start()
    _BROWSER = _PLAYWRIGHT.chromium.launch(headless=True)
    return _BROWSER


def _shutdown_browser() -> None:
    """[BL-335] atexitフックとテストのteardown両方から呼ぶ。"""
    global _PLAYWRIGHT, _BROWSER, _PAGES_RENDERED_SINCE_LAUNCH
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
    _PAGES_RENDERED_SINCE_LAUNCH = 0


atexit.register(_shutdown_browser)


def _ssrf_route_guard(route, request) -> None:
    """[BL-335][SAFETY] Playwrightはナビゲーション自体だけでなく、ページが読み込む
    サブリソース（画像・スクリプト・XHR等）についても実際にネットワーク接続する。
    これはhttpxパスには存在しなかった新しいSSRF面であり、全リクエストへ
    validate_url_for_fetch相当のチェックをかけ、失敗したものはabortする。"""
    try:
        validate_url_for_fetch(request.url)
    except SsrfBlockedError:
        route.abort()
        return
    route.continue_()


def _fetch_html_via_playwright(url: str) -> tuple[str, str] | None:
    """[BL-335] 成功時は(HTML文字列, 最終着地URL)を返す。着地URLはリダイレクト追従後の
    相対リンク解決（Cline手動レビューF2）に使う。既知の失敗（起動エラー・タイムアウト・
    クラッシュ・4xx/5xx応答・非HTML着地・サイズ上限超過）はNoneを返しhttpx静的フェッチへの
    フォールバックに委ねる。それ以外の予期しない例外は伝播させる（D-009: 一時的障害は
    リトライ・ロジックエラーは即座に伝播）。
    「レンダリング結果が短い/空だが例外は出ていない」ケースはフォールバック対象に
    含めない——正当に短いページを誤ってフォールバックと混同しないため。
    """
    from playwright.sync_api import Error as PlaywrightError, TimeoutError as PlaywrightTimeoutError

    global _PAGES_RENDERED_SINCE_LAUNCH
    if _PAGES_RENDERED_SINCE_LAUNCH >= _PLAYWRIGHT_RECYCLE_AFTER_N_PAGES:
        _shutdown_browser()
    # [Cline手動レビューF1] ブラウザ起動・context生成・route登録もtry内に含める。
    # 以前はこの3行がtryの外にあり、ここで発生したPlaywrightErrorがdocstringの
    # 「フォールバックに委ねる」契約に反して伝播していた（chromium未インストール等の
    # 環境不備でweb_fetchが全面的に使用不能になる実害を実プローブで確認）。
    context = None
    try:
        browser = _ensure_browser()
        context = browser.new_context(user_agent=_USER_AGENT)
        context.route("**/*", _ssrf_route_guard)
        page = context.new_page()
        response = page.goto(url, wait_until="domcontentloaded", timeout=_PLAYWRIGHT_NAV_TIMEOUT_MS)
        try:
            page.wait_for_load_state("networkidle", timeout=_PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS)
        except PlaywrightTimeoutError:
            pass  # SPAが継続ポーリングしidleに到達しないページは珍しくない。取れた分で進める。
        # [SSRF][BL-335] JSリダイレクト等で着地した最終URLも再検証する（httpx経路と同様、
        # リダイレクト自体は許可した上で最終URLを検証する方針、D-285）。
        validate_url_for_fetch(page.url)
        if response is not None:
            # [Cline手動レビューR4] page.goto()はhttpxのraise_for_status()と異なり4xx/5xxで
            # 例外を投げない。既存契約（raise_for_status()でエラー化）と揃えるため、
            # 非2xxはPlaywright失敗として扱いhttpx経路へフォールスルーする。
            if response.status >= 400:
                return None
            landed_ct = (response.headers.get("content-type") or "").split(";")[0].strip().lower()
            if landed_ct and not landed_ct.startswith("text/html"):
                return None  # 文書系(PDF等)に着地→Playwrightは不適、呼び出し元がhttpx文書経路へ
        html = page.content()
        # [Cline手動レビューR3] httpx経路が課しているサイズ上限（_MAX_FETCH_BYTES）を
        # Playwright経路にも同一適用する（AGENTS.md §15.1: 同一ルールは同一箇所の判定に揃える）。
        if len(html.encode("utf-8")) > _MAX_FETCH_BYTES:
            return None  # httpx経路へフォールスルー（httpx側で同じ上限が改めて適用される）
        _PAGES_RENDERED_SINCE_LAUNCH += 1
        return html, page.url
    except (PlaywrightError, PlaywrightTimeoutError) as e:
        print(f"⚠️ [web_fetch] Playwright描画に失敗、httpx静的フェッチへフォールバック: {e}")
        return None
    finally:
        if context is not None:
            context.close()


def _resolve_relative_markdown_links(markdown_text: str, base_url: str) -> str:
    """[BL-188] markitdown出力中のMarkdownリンク/画像記法 `](url)` の相対URLを、fetch元の
    base_urlを基準に絶対URLへ解決する。markitdownの`convert_stream(url=...)`はソースURLを
    メタデータとして保持するのみで相対リンクの自動解決は行わないことを実データで確認済み
    （相対のまま返すと、モデルがそのURLをそのままweb_fetchしても解決できない）。
    """
    def _replace(m: re.Match) -> str:
        raw_url = m.group(1)
        if raw_url.startswith(("http://", "https://", "data:", "mailto:", "tel:", "#")):
            return m.group(0)
        return "](" + urljoin(base_url, raw_url)

    return _MARKDOWN_LINK_RE.sub(_replace, markdown_text)


def fetch_and_extract(url: str) -> str:
    """[BL-184][BL-188][BL-335] URLを検証・取得し、本文をMarkdownへ変換して返す（見出し・表・
    リンクの文脈的位置を保持する）。HTML/PDFいずれもMicrosoft markitdownで変換する。

    [BL-335] `_DOCUMENT_EXTENSIONS`に該当しないURL（＝HTMLページと推定）は、まず
    Playwright（ヘッドレスChromium）で描画取得を試みる（クライアントサイドJS描画コンテンツが
    静的httpx取得では取得できない実害への対応、BL335_basic_design.md参照）。文書系URL
    （.pdf/.xlsx等）はブラウザで「開く」ものではない（ChromiumはPDFを内蔵ビューアで開いて
    しまい素のバイト列が取れない）ため、既存のhttpxバイト取得経路へ直行する。

    [Cline手動レビューR1・BL-335] リダイレクト（3xx）は追跡する（従来は明示的に拒否して
    いたが、Playwrightがpage.goto()で透過的に追従するため、同じツールが経路によって
    振る舞いが変わる矛盾を解消する方向へポリシーを転換した）。SSRFバイパス対策は
    最終着地URLの再検証（本関数・_fetch_html_via_playwright双方）とPlaywright側の
    サブリソースroute guardで構造的に維持する。失敗時はSsrfBlockedError/httpx例外/
    MarkItDownExceptionを送出する（呼び出し元でcatchしてエラーレスポンスへ変換すること）。
    """
    validate_url_for_fetch(url)
    url_extension = Path(urlparse(url).path).suffix.lower()
    if url_extension not in _DOCUMENT_EXTENSIONS:
        playwright_result = _fetch_html_via_playwright(url)
        if playwright_result is not None:
            html, landed_url = playwright_result
            try:
                result = _MARKITDOWN.convert_stream(
                    io.BytesIO(html.encode("utf-8")),
                    stream_info=StreamInfo(mimetype="text/html", extension=".html"),
                    url=landed_url,
                )
            except MarkItDownException as e:
                raise SsrfBlockedError(f"コンテンツの変換に失敗しました（text/html）: {e}")
            # [Cline手動レビューF2] 相対リンクの解決ベースは元urlでなく着地URL。
            # ホストが変わるリダイレクトでは元urlを使うと誤った絶対URLになる。
            extracted = _resolve_relative_markdown_links(result.text_content, landed_url)
            if len(extracted) > _MAX_OUTPUT_CHARS:
                extracted = extracted[:_MAX_OUTPUT_CHARS] + "\n[Fetch Output truncated]"
            return extracted
        print(f"ℹ️ [web_fetch] Playwright非適用/失敗のためhttpx静的フェッチへ: {url}")
    return _fetch_via_httpx_and_convert(url, url_extension)


def _fetch_via_httpx_and_convert(url: str, url_extension: str) -> str:
    """[BL-184][BL-188][BL-335] 従来のhttpx静的取得＋markitdown変換経路。HTML/PDF/xlsx等
    すべての文書形式に対応し、`fetch_and_extract`のPlaywright経路が非適用/失敗だった
    場合のフォールバック先でもある。
    """
    # [Cline手動レビュー指摘1・BL-335] follow_redirects=Trueによる自動追従は、各中間ホップへ
    # 実際に接続した後で最終URLだけを検証するため、内部アドレスへ向く中間リダイレクトが
    # SSRF検証をすり抜けて実接続してしまう（blind SSRF）。1ホップずつ手動で追従し、
    # 接続する前に毎回validate_url_for_fetchを通す（Playwright経路のroute guardが
    # 全リクエストを個別検証しているのと同水準に揃える、AGENTS.md §15.1）。
    with httpx.Client(timeout=_REQUEST_TIMEOUT_SECONDS) as client:
        request = client.build_request("GET", url, headers={"User-Agent": _USER_AGENT})
        hops = 0
        while True:
            validate_url_for_fetch(str(request.url))
            resp = client.send(request, follow_redirects=False)
            if resp.next_request is None:
                break
            hops += 1
            if hops > _MAX_REDIRECT_HOPS:
                raise SsrfBlockedError(f"リダイレクトが上限（{_MAX_REDIRECT_HOPS}回）を超えました。")
            request = resp.next_request
    landed_url = str(resp.url)
    resp.raise_for_status()
    content_type = resp.headers.get("content-type", "").split(";")[0].strip().lower()
    # [BL-218] URLパス末尾の拡張子もヒントとして使う。自治体サイトはContent-Typeが不正確
    # （application/octet-stream等）なことがあり、拡張子だけが正しい手がかりというケースを
    # Content-Type単独の判定では取りこぼす。着地後のURLで再計算する（リダイレクト先が
    # 元URLと異なる拡張子を持つ場合があるため）。
    landed_extension = Path(urlparse(landed_url).path).suffix.lower()
    is_recognized_mimetype = content_type.startswith("text/") or content_type.startswith(_DOCUMENT_MIME_TYPE_PREFIXES)
    is_recognized_extension = landed_extension in _DOCUMENT_EXTENSIONS or url_extension in _DOCUMENT_EXTENSIONS
    if not is_recognized_mimetype and not is_recognized_extension:
        raise SsrfBlockedError(
            f"許可されていない形式です（Content-Type={content_type!r}, 拡張子={landed_extension!r}）。"
            "対応形式: text/*, PDF, Word(.docx), Excel(.xlsx/.xls), PowerPoint(.pptx), CSV, EPUB"
        )
    raw = resp.content
    # [SAFETY] PDFはバイナリ構造（xrefテーブル等）を持つため途中切り捨てが安全でない
    # （パース自体が失敗しうる）。HTMLも含め、markitdown（内部でpdfminer/BeautifulSoup等の
    # より厳格なパーサを使う）に渡すバイト列は、切り捨てずサイズ上限超過時に明示エラーとする
    # よう統一する（html.parserベースの旧実装は寛容だったが、より厳密なパーサでは壊れた
    # 入力がエラーの原因になりうるため）。
    if len(raw) > _MAX_FETCH_BYTES:
        raise SsrfBlockedError(
            f"コンテンツのサイズが上限（{_MAX_FETCH_BYTES // (1024 * 1024)}MB）を超えています。"
        )
    effective_extension = landed_extension or url_extension
    if effective_extension in _RAW_CACHEABLE_EXTENSIONS:
        # [BL-335] Phase 2/3の前提整備。markitdown変換の成否とは独立に生バイト列を保存する
        # （変換が例外送出しても、テキスト抽出が完全失敗したPDFでもvisionツールは使える）。
        write_raw_cache(raw_cache_file_path(url, effective_extension), raw)
    try:
        result = _MARKITDOWN.convert_stream(
            io.BytesIO(raw),
            # [BL-218] extensionも渡す。markitdownの各コンバータはmimetype/extensionのいずれか
            # 一致すれば受理するため、Content-Typeが誤っていても拡張子側で正しく変換できる。
            stream_info=StreamInfo(mimetype=content_type, extension=effective_extension or None),
            url=landed_url,
        )
    except MarkItDownException as e:
        raise SsrfBlockedError(f"コンテンツの変換に失敗しました（{content_type}）: {e}")
    # [Cline手動レビューF2・BL-335] 相対リンクの解決ベースは元urlでなく着地URL
    # （landed_url）。D-285でリダイレクト追従を許可した結果、ホストが変わるリダイレクトでは
    # 元urlを使うと誤った絶対URLを[Links found on this page]に並べることになるため。
    extracted = _resolve_relative_markdown_links(result.text_content, landed_url)
    if len(extracted) > _MAX_OUTPUT_CHARS:
        extracted = extracted[:_MAX_OUTPUT_CHARS] + "\n[Fetch Output truncated]"
    return extracted


# ---------------------------------------------------------------------------
# キャッシュ（web_fetch結果 / read_reference_fileの読み取り対象）
# ---------------------------------------------------------------------------

def cache_file_path(url: str) -> Path:
    """[BL-184→BL-200] `web_cache/<sha256(url)[:16]>.md`のパスを返す。当初は
    `web_cache/<run_id>/`とrun単位で分離していたが、同一URLの再取得コスト（web_fetchの
    呼び出し回数消費・応答待ち）はrunをまたいでも同じであり、run単位の分離はそのコストを
    毎回リセットして無駄にするだけだった（log/2026-08-09/2222を機にユーザーが指摘）。
    URLをキーとしたグローバル共有キャッシュへ変更し、以前のrunで取得済みのページは以後の
    全runで無料・即時に再利用できるようにする。"""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Path(WEB_CACHE_DIR) / f"{digest}.md"


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


def raw_cache_file_path(url: str, extension: str) -> Path:
    """[BL-335] cache_file_path()と同じsha256(url)[:16]ハッシュを使い、拡張子だけ差し替える
    （.mdと同じキーで見つけられるようにする、AGENTS.md §15.1）。Phase 2（PDF画像化）・
    Phase 3（xlsx pandas読み込み）が元の生バイト列を必要とするため、markitdown変換後の
    Markdownとは別に、PDF/xlsx/xlsのみ保存する（`_RAW_CACHEABLE_EXTENSIONS`）。"""
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
    return Path(WEB_CACHE_DIR) / f"{digest}{extension}"


def write_raw_cache(path: Path, raw: bytes) -> None:
    """[BL-335] raw_cache_file_path()で決まるパスへ生バイト列をそのまま書き出す。
    markitdown変換の成否とは独立に呼ぶ（変換が例外送出しても、テキスト抽出が完全失敗した
    PDFでもPhase 2のvisionツールは使える）。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)


def pdf_vision_cache_file_path(url: str, page_number: int) -> Path:
    """[BL-335] `read_pdf_page_as_image`のvisionモデル応答をキャッシュするパス。
    write_cache/strip_cache_headerとヘッダ形式互換（AGENTS.md §15.1、既存の
    キャッシュ読み書きコードをそのまま再利用できるようにする）。"""
    digest = hashlib.sha256(f"{url}#page={page_number}".encode("utf-8")).hexdigest()[:16]
    return Path(WEB_CACHE_DIR) / f"{digest}.pdfvision.md"


def pdf_page_count(pdf_bytes: bytes) -> int:
    """[BL-335 Phase 2] PDFの総ページ数を返す。read_pdf_page_as_imageのpage_number範囲検証に使う。"""
    with pdfium.PdfDocument(pdf_bytes) as pdf:
        return len(pdf)


def render_pdf_page_to_png_bytes(pdf_bytes: bytes, page_number: int, dpi: int = 150) -> bytes:
    """[BL-335 Phase 2] 1-indexed page_numberをPNGへレンダリングする（pypdfium2使用）。
    scaleは72dpi=1.0基準（pypdfium2公式ドキュメント）のため、dpi/72で換算する。"""
    with pdfium.PdfDocument(pdf_bytes) as pdf:
        page = pdf[page_number - 1]
        bitmap = page.render(scale=dpi / 72)
        pil_image = bitmap.to_pil()
        buf = io.BytesIO()
        pil_image.save(buf, format="PNG")
        return buf.getvalue()


_CACHE_PREVIEW_BODY_CHARS = 300


def _cache_preview(path: Path) -> str:
    """[BL-216] キャッシュ候補一覧向けの短い要約。Source URL（write_cacheのヘッダ）に加え、
    本文冒頭を添えることで、モデルがファイルを開かずにどの候補が目的のページかを判断できる
    ようにする。ファイル名自体はsha256ハッシュで人間にもモデルにも意味を持たないため。"""
    content = path.read_text(encoding="utf-8", errors="ignore")
    lines = content.split("\n", 2)
    source_line = lines[0] if lines and lines[0].startswith("# Source:") else ""
    body = strip_cache_header(content).strip().replace("\n", " ")
    snippet = body[:_CACHE_PREVIEW_BODY_CHARS]
    if len(body) > _CACHE_PREVIEW_BODY_CHARS:
        snippet += "…"
    return f"{source_line}\n{snippet}" if source_line else snippet


_GREP_CONTEXT_LINES = 3
_GREP_MAX_MATCH_BLOCKS = 30


def _grep_with_context(content: str, pattern: str, context_lines: int = _GREP_CONTEXT_LINES) -> str | None:
    """[BL-221] `content`を行単位でパターン検索し、各マッチ行の前後`context_lines`行を
    添えて`grep -C`相当の形式で返す。BL-221でダウンロード容量上限を8MB→50MBへ引き上げた
    ため、read_reference_fileの素読み（_MAX_READ_REFERENCE_CHARSで切り詰め）だけでは
    巨大なキャッシュ済み文書の必要箇所に到達できなくなる。全文はキャッシュに切り詰めなしで
    保存済み（write_cache）なので、ここではそのファイルを直接読み、マッチ箇所の周辺だけを
    返すことでトークン消費を抑えたまま任意の位置にアクセスできるようにする。
    大文字小文字を区別する単純な部分一致（read_reference_fileのkeyword検索と同じ方式）。
    マッチが無ければNoneを返す（呼び出し側でnot_foundメッセージを組み立てる）。
    [BL-252] `grep`という名称・パラメータ名から、Expertは`|`区切りでOR検索できると
    自然に類推するが、正規表現エンジンは使っておらず`pattern in line`のリテラル部分
    一致のみだったため、`|`を含む行が実際には存在せず常にnot_foundになっていた
    （実ログでは`|`を含むgrepパターン7件中7件が不一致、含まないもの7件中7件が成功という
    完全な相関を確認）。正規表現化（re.search）はReDoS等の新たなリスクを持ち込むため、
    観測された実際の用途（単純なOR）にのみ対応する`|`分割によるいずれか一致へ限定する。
    """
    lines = content.split("\n")
    terms = [t for t in pattern.split("|") if t]
    if not terms:
        return None
    match_indices = [i for i, line in enumerate(lines) if any(t in line for t in terms)]
    if not match_indices:
        return None

    truncated = len(match_indices) > _GREP_MAX_MATCH_BLOCKS
    match_indices = match_indices[:_GREP_MAX_MATCH_BLOCKS]

    # [grep -C相当] 隣接・重複するコンテキスト窓は1つのブロックへ統合する
    # （マッチが密集している場合に同じ行を何度も出力しないため）。
    windows: list[tuple[int, int]] = []
    for idx in match_indices:
        start = max(0, idx - context_lines)
        end = min(len(lines) - 1, idx + context_lines)
        if windows and start <= windows[-1][1] + 1:
            windows[-1] = (windows[-1][0], max(windows[-1][1], end))
        else:
            windows.append((start, end))

    blocks = []
    for start, end in windows:
        block_lines = [f"{i + 1}: {lines[i]}" for i in range(start, end + 1)]
        blocks.append("\n".join(block_lines))
    result = "\n--\n".join(blocks)
    if truncated:
        result += (
            f"\n--\n[{len(match_indices)}件のマッチのうち先頭{_GREP_MAX_MATCH_BLOCKS}件のみ表示。"
            "より具体的なgrepパターンで絞り込んでください]"
        )
    return result


# ---------------------------------------------------------------------------
# ツールハンドラ本体
# ---------------------------------------------------------------------------

def web_search_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-184] `web_search`ツールのハンドラ。run単位の呼び出し回数上限
    （`config["max_web_search_calls"]`、既定20）を超えた場合はエラーを返す。

    [BL-270] `WebSearchConfigError`（APIキー未設定・Brave 402等、run内では回復しない
    系統の失敗）を一度検知したら、`state`にそのメッセージを記録し、以後の呼び出しは
    実際のHTTPリクエストを送らず同じ説明を即座に返す。402は同じrun内で何度リトライ
    しても解消しないため、無駄な往復とLLMのiteration消費を避ける。"""
    query = (args.get("query") or "").strip()
    if not query:
        return {"status": "error", "message": "queryは必須です。"}

    _unavailable_message = state.get("web_search_provider_unavailable_message")
    if _unavailable_message:
        return {"status": "error", "message": _unavailable_message}
    # [BL-218] 既定を5→10へ引き上げ。実ログで、5件では目的の情報に届かず同じqueryや
    # 近い言い換えで何度もweb_searchを呼び直す（run単位の呼び出し上限を無駄に消費する）
    # 傾向が確認されたため（ユーザー指摘）。
    # [BL-282] 10→15へ再度引き上げ。長時間runの実ログレビューで、依然として同じqueryの
    # 言い換え再検索が多発し、run単位のweb_search呼び出し上限を早々に枯渇させている
    # ことが判明したため（ユーザー指摘）。上限（15）と揃えることで、通常時は追加の
    # 呼び出し判断をモデルに委ねず最初から候補を広く見せる。なおExa Providerは
    # ベンダーAPI仕様上numResultsが1-10までしか受け付けないため、Exa選択時は
    # 15を指定しても実際には10件に制限される（get_search_provider内で別途clamp）。
    max_results = args.get("max_results", 15)
    try:
        max_results = max(1, min(int(max_results), 15))
    except (TypeError, ValueError):
        max_results = 15

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
        # [BL-270] run内では回復しない系統の失敗として記録し、以後の呼び出しを短絡する。
        state["web_search_provider_unavailable_message"] = str(e)
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001 - 外部通信の失敗は種類を問わずエラーレスポンス化する
        return {"status": "error", "message": f"web_search失敗: {e}"}

    state["web_search_call_count"] = count + 1
    return {"results": results}


def web_fetch_handler(args: dict, state: dict, config: dict) -> dict | str:
    """[BL-184] `web_fetch`ツールのハンドラ。キャッシュヒット時はrun単位の呼び出し回数
    カウントを消費しない（BL184_basic_design.md）。[BL-200] キャッシュはURLキーの
    グローバル共有（`web_cache/`直下）のため、過去の別runで既に取得済みのURLは
    このrunでも呼び出し回数を消費せず即座に返る。"""
    url = (args.get("url") or "").strip()
    if not url:
        return {"status": "error", "message": "urlは必須です。"}

    cache_path = cache_file_path(url)
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
    `web_cache/`一本に限定する。`read_deliverable_file`と同じ
    `Path(...).resolve()` → `relative_to(base_dir)`のresolve-and-containパターンで
    パス脱出を防ぐ。`keyword`指定時は各キャッシュファイル先頭の`# Source: {url}`行への
    部分一致検索を行う（Detectorが`citations`のURLから逆引きする経路、必須要件）。
    [BL-200] キャッシュはURLキーのグローバル共有のため、このrun自身がweb_fetchした
    ページだけでなく、過去の別runで既に取得済みのページも読める（`state`引数は
    TOOL_DISPATCHの統一シグネチャに合わせて受け取るのみで、現在は未使用）。
    """
    base_dir = Path(WEB_CACHE_DIR).resolve()
    path = args.get("path") or ""
    keyword = args.get("keyword") or ""
    grep = args.get("grep") or ""

    if grep and not path:
        # [BL-244 2026-08-15/2149・2239ログ調査] pathを別ターンで先に確認させる設計だったが、
        # 実ドライランでは4件以上の異なるExpertロールが独立に「keywordとgrepを同じ呼び出しに
        # 同時指定する」形で呼んでおり（read_reference_file全26回中12回=46%がこの理由の
        # status_errorだった）、単発の呼び出し形として自然に出てくることが判明した。
        # keywordが同時に指定されていれば、grepを拒否する前にkeywordでpathを解決できないか
        # 試す（0件/複数件時は従来通りnot_found/multiple_matchesへフォールバック、解決できる
        # 情報が既に揃っているのに問答無用でエラーにしていたのを緩和する）。
        if not keyword:
            return {"status": "error", "message": "grepはpathと組み合わせて指定してください（対象ファイルを先に特定する必要があります）。"}
        resolved = _resolve_reference_cache_path_by_keyword(base_dir, keyword)
        if resolved is None:
            return {"status": "not_found", "message": f"'{keyword}'に該当するキャッシュファイルが見つかりませんでした。"}
        if isinstance(resolved, dict):
            return resolved
        path = resolved

    if path:
        try:
            resolved = (base_dir / path).resolve()
            resolved.relative_to(base_dir)
        except ValueError:
            return {"status": "error", "message": "web_cache外へのアクセスは禁止されています。"}
        if not resolved.exists() or not resolved.is_file():
            return {"status": "not_found", "message": f"ファイルが見つかりません: {path}"}
        content = resolved.read_text(encoding="utf-8")
        if grep:
            # [BL-221] キャッシュは切り詰めなしの全文（write_cache）なので、_MAX_READ_REFERENCE_CHARS
            # による素読みの切り詰めを経由せず、全文に対してgrepする。
            grepped = _grep_with_context(strip_cache_header(content), grep)
            if grepped is None:
                return {"status": "not_found", "message": f"'{grep}'に該当する行が見つかりませんでした。"}
            return grepped
        return content[:_MAX_READ_REFERENCE_CHARS]

    if keyword:
        if not base_dir.exists():
            return {"status": "not_found", "message": "web_cacheにまだキャッシュファイルがありません。"}
        resolved = _resolve_reference_cache_path_by_keyword(base_dir, keyword)
        if resolved is None:
            return {"status": "not_found", "message": f"'{keyword}'に該当するキャッシュファイルが見つかりませんでした。"}
        if isinstance(resolved, dict):
            return resolved
        return (base_dir / resolved).read_text(encoding="utf-8")[:_MAX_READ_REFERENCE_CHARS]

    return {"status": "error", "message": "pathまたはkeywordのいずれかを指定してください。"}


def _resolve_reference_cache_path_by_keyword(base_dir: Path, keyword: str) -> str | dict | None:
    """[BL-244] read_reference_fileのkeyword解決ロジックの共通化。0件はNone、1件は
    ファイル名(str)、複数件はmultiple_matchesのdictを返す。read_reference_file_handlerの
    keyword単独ブランチと、grep+keyword同時指定時の先行解決の両方から呼ばれる。"""
    matches: list[str] = []
    for f in sorted(base_dir.glob("*.md")):
        head = f.read_text(encoding="utf-8", errors="ignore")[:500]
        if keyword in head:
            matches.append(f.name)
    if not matches:
        return None
    if len(matches) > 1:
        # [BL-216] ファイル名はsha256(url)[:16]のハッシュのため、候補一覧だけでは
        # どれが目的のページか一切判別できず、モデルは1件ずつpathで開いて中身を確認する
        # しかなかった（keyword検索の目的である「再取得の回避」が事実上働かなくなる）。
        # 一覧の段階でSource URLと本文冒頭を添え、開かずに選べるようにする。
        candidates = [
            {"path": name, "preview": _cache_preview(base_dir / name)}
            for name in matches
        ]
        return {
            "status": "multiple_matches",
            "message": "複数のキャッシュファイルが該当しました。previewを確認し、pathを指定して再取得してください。",
            "candidates": candidates,
        }
    return matches[0]


# [BL-199] 実行中のweb_search/web_fetchとは別に、開発者がAGENTS.md §9に従って事前収集した
# ゴール固有の参照データ（`docs/refs/<goal>/`、run開始前に人間が用意する）を、run単位の
# 呼び出し回数制限を消費せずに読めるようにする。log/2026-08-09/2222で、Expertが既に
# `docs/refs/chino_city/chino_city_data.md`にキャッシュ済みの施設住所・座標を知らずに
# web_searchで同じ情報を再検索し、run単位の呼び出し上限（30回）を使い果たしていたことが
# 判明した（read_reference_fileはweb_cache/<run_id>/専用でdocs/refs/を読めないため、
# 既存ツールでは代替できなかった）。
def read_goal_reference_handler(args: dict, state: dict) -> dict | str:
    """[BL-199] `read_goal_reference`ツールのハンドラ。ベースディレクトリは
    `state["goal_reference_dir"]`（run開始時にAppConfigからコピー、未設定なら無効）
    一本に限定する。`read_reference_file`と同じresolve-and-containパターンでパス脱出を
    防ぐが、対象はweb_cacheの実行時キャッシュではなく開発者が事前キュレーションした
    静的参照データである点が異なる（AGENTS.md §9のdocs/refs/運用そのもの）。
    """
    goal_reference_dir = state.get("goal_reference_dir") or ""
    if not goal_reference_dir:
        return {"status": "not_configured", "message": "このrunにはgoal_reference_dirが設定されていません。"}
    base_dir = Path(goal_reference_dir).resolve()
    path = args.get("path") or ""
    keyword = args.get("keyword") or ""

    if not base_dir.exists() or not base_dir.is_dir():
        return {"status": "not_found", "message": "参照データディレクトリが見つかりません。"}

    if path:
        try:
            resolved = (base_dir / path).resolve()
            resolved.relative_to(base_dir)
        except ValueError:
            return {"status": "error", "message": "参照データディレクトリ外へのアクセスは禁止されています。"}
        if not resolved.exists() or not resolved.is_file():
            return {"status": "not_found", "message": f"ファイルが見つかりません: {path}"}
        return resolved.read_text(encoding="utf-8")[:_MAX_READ_REFERENCE_CHARS]

    if keyword:
        matches: list[str] = []
        for f in sorted(base_dir.rglob("*.md")):
            body = f.read_text(encoding="utf-8", errors="ignore")
            if keyword in body:
                matches.append(str(f.relative_to(base_dir)))
        if not matches:
            return {"status": "not_found", "message": f"'{keyword}'に該当する参照データが見つかりませんでした。web_searchを使ってください。"}
        if len(matches) > 1:
            return {
                "status": "multiple_matches",
                "message": "複数の参照データファイルが該当しました。pathを指定して再取得してください。",
                "candidates": matches,
            }
        return (base_dir / matches[0]).read_text(encoding="utf-8")[:_MAX_READ_REFERENCE_CHARS]

    return {"status": "error", "message": "pathまたはkeywordのいずれかを指定してください。"}
