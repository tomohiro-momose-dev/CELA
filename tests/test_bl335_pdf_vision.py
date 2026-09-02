"""
BL-335 Phase 2: read_pdf_page_as_imageツール（PDFページの画像化→glm-5.3-flash Vision）の
単体テスト。実LLM API呼び出しは伴わない（client_openrouter.chat.completions.createを
raiseする/返り値を返すフェイクで代替）。実PDFバイト列はpypdfium2自身の新規ドキュメント
生成APIで最小限のものをその場で作る。

参照: docs/design/back_log/BL-335/BL335_basic_design.md §2。
"""

import io
import os
import sys

import httpx
import pytest
from openai import APIError, APIConnectionError, RateLimitError

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402
import web_tools  # noqa: E402
import pypdfium2 as pdfium  # noqa: E402


def _make_pdf_bytes(page_count: int = 2) -> bytes:
    pdf = pdfium.PdfDocument.new()
    for _ in range(page_count):
        pdf.new_page(200, 200)
    buf = io.BytesIO()
    pdf.save(buf)
    return buf.getvalue()


def _seed_cache(tmp_path, monkeypatch, url="https://example.com/doc.pdf", page_count=2):
    """web_cache/へ.md（Source行付き）と.pdf（生バイト）の両方を配置する（BL-335適用後の
    正常なキャッシュ状態を模す）。"""
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    pdf_bytes = _make_pdf_bytes(page_count)
    md_path = web_tools.cache_file_path(url)
    web_tools.write_cache(md_path, url, "PDF本文（テキスト抽出、壊れている想定）")
    raw_path = web_tools.raw_cache_file_path(url, ".pdf")
    web_tools.write_raw_cache(raw_path, pdf_bytes)
    return md_path.name, url


class _FakeCompletions:
    def __init__(self, responses):
        """responsesは呼び出しごとに1つずつ消費するリスト。要素は文字列（成功時の応答本文）
        または例外インスタンス。"""
        self._responses = list(responses)
        self.call_count = 0

    def create(self, **kwargs):
        self.call_count += 1
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        message = type("Msg", (), {"content": item})()
        choice = type("Choice", (), {"message": message})()
        return type("Resp", (), {"choices": [choice]})()


class _FakeChat:
    def __init__(self, responses):
        self.completions = _FakeCompletions(responses)


class _FakeClient:
    def __init__(self, responses):
        self.chat = _FakeChat(responses)


def _install_fake_client(monkeypatch, responses):
    fake = _FakeClient(responses)
    monkeypatch.setattr(cela_main, "client_openrouter", fake)
    return fake


def _make_connection_error():
    req = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    return APIConnectionError(request=req)


def _make_rate_limit_error():
    req = httpx.Request("POST", "https://api.example.com/v1/chat/completions")
    resp = httpx.Response(429, request=req, json={"error": {"message": "rate limited"}})
    return RateLimitError("Error code: 429", response=resp, body=None)


# ---------------------------------------------------------------------------
# 成功パス・キャッシュ
# ---------------------------------------------------------------------------

def test_success_writes_cache_and_consumes_budget(tmp_path, monkeypatch):
    path, url = _seed_cache(tmp_path, monkeypatch)
    _install_fake_client(monkeypatch, ["ページ1の転記結果"])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "ok"
    assert result["pages"] == [{"page_number": 1, "description": "ページ1の転記結果"}]
    assert state["pdf_vision_call_count"] == 1
    cache_path = web_tools.pdf_vision_cache_file_path(url, 1)
    assert cache_path.exists()
    assert "ページ1の転記結果" in web_tools.strip_cache_header(cache_path.read_text(encoding="utf-8"))


def test_empty_vision_response_is_not_cached_or_counted(tmp_path, monkeypatch):
    """[Cline手動レビュー指摘2] 空応答をキャッシュ・カウント消費してしまうと、以後
    呼び出すたびに空文字がキャッシュヒットとして返り続け、モデルが実際には何も
    返せていないことに二度と気づけなくなる。エラー化し、キャッシュ・カウンタとも
    変更しないことを検証する。"""
    path, url = _seed_cache(tmp_path, monkeypatch)
    fake = _install_fake_client(monkeypatch, [""])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "error"
    assert "空の応答" in result["message"]
    assert fake.chat.completions.call_count == 1
    assert state["pdf_vision_call_count"] == 0
    assert not web_tools.pdf_vision_cache_file_path(url, 1).exists()


def test_cache_hit_does_not_consume_budget_or_call_api(tmp_path, monkeypatch):
    path, url = _seed_cache(tmp_path, monkeypatch)
    web_tools.write_cache(web_tools.pdf_vision_cache_file_path(url, 1), f"{url}#page=1", "キャッシュ済み転記")
    fake = _install_fake_client(monkeypatch, [])  # API呼び出しがあれば即IndexErrorで失敗する
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["pages"] == [{"page_number": 1, "description": "キャッシュ済み転記"}]
    assert state["pdf_vision_call_count"] == 0
    assert fake.chat.completions.call_count == 0


def test_multi_page_request_renders_each_page_separately(tmp_path, monkeypatch):
    path, url = _seed_cache(tmp_path, monkeypatch, page_count=3)
    _install_fake_client(monkeypatch, ["1ページ目", "2ページ目"])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1, "page_count": 2}, state,
    )

    assert result["pages"] == [
        {"page_number": 1, "description": "1ページ目"},
        {"page_number": 2, "description": "2ページ目"},
    ]
    assert state["pdf_vision_call_count"] == 2


# ---------------------------------------------------------------------------
# [Cline手動レビューR2] BL-335適用前キャッシュ（生バイト無し）は恒久エラー
# ---------------------------------------------------------------------------

def test_missing_raw_bytes_returns_permanent_error_without_reattempting_fetch(tmp_path, monkeypatch):
    url = "https://example.com/pre-bl335.pdf"
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    md_path = web_tools.cache_file_path(url)
    web_tools.write_cache(md_path, url, "BL-335適用前に取得済みの本文（生バイト無し）")
    # raw_cache_file_pathの.pdfは意図的に書き込まない（BL-335適用前キャッシュを模す）。
    fake = _install_fake_client(monkeypatch, [])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": md_path.name, "page_number": 1}, state,
    )

    assert result["status"] == "error"
    assert "生バイトがなく" in result["message"]
    assert fake.chat.completions.call_count == 0
    assert state["pdf_vision_call_count"] == 0


# ---------------------------------------------------------------------------
# 入力検証
# ---------------------------------------------------------------------------

def test_non_pdf_cache_returns_accurate_error_not_pre_bl335_message(tmp_path, monkeypatch):
    """[Cline手動レビュー指摘4] .xlsx等（生バイトの兄弟ファイルが実在する）を指定した場合、
    「BL-335適用前にキャッシュされたため」という虚偽の理由ではなく、PDFではない旨の
    正確なエラーを返すこと。"""
    url = "https://example.com/data.xlsx"
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    md_path = web_tools.cache_file_path(url)
    web_tools.write_cache(md_path, url, "xlsxの本文（markitdown変換済み）")
    web_tools.write_raw_cache(web_tools.raw_cache_file_path(url, ".xlsx"), b"fake xlsx bytes")
    fake = _install_fake_client(monkeypatch, [])

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": md_path.name, "page_number": 1}, {},
    )

    assert result["status"] == "error"
    assert "PDFではありません" in result["message"]
    assert "BL-335適用前" not in result["message"]
    assert fake.chat.completions.call_count == 0


def test_pre_bl335_xlsx_cache_without_raw_bytes_gets_generic_message(tmp_path, monkeypatch):
    """xlsx等でも生バイトの兄弟ファイルが一切無い（BL-335適用前にキャッシュされた等）場合は、
    「PDFではない」と断定できる根拠が無いため、汎用の生バイト欠落メッセージへフォールバックする
    （xlsxの.pdf/.xlsx双方が不在＝本当に判別材料が無いケース）。"""
    url = "https://example.com/data-no-raw.xlsx"
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    md_path = web_tools.cache_file_path(url)
    web_tools.write_cache(md_path, url, "xlsxの本文（BL-335適用前にキャッシュされた想定、生バイト無し）")

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": md_path.name, "page_number": 1}, {},
    )

    assert result["status"] == "error"
    assert "生バイトがなく" in result["message"]


def test_redirect_landed_pdf_with_extensionless_source_url_is_recognized(tmp_path, monkeypatch):
    """[Cline diffレビューF2] 元URLに拡張子が無く（例: /get-report）、リダイレクト着地先が
    .pdfだった場合でも、着地拡張子でキー化された生バイトの兄弟ファイルが実在すれば
    正しくPDFとして扱われること（元URL自身の拡張子だけを見て「PDFではない」と誤って
    永続的に拒否していた欠陥の回帰テスト）。"""
    url = "https://example.com/get-report"  # 拡張子なし（実際の着地先は.pdfだった想定）
    path, url_returned = _seed_cache(tmp_path, monkeypatch, url=url, page_count=1)
    _install_fake_client(monkeypatch, ["転記結果"])

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, {},
    )

    assert result["status"] == "ok", result


def test_path_traversal_rejected(tmp_path, monkeypatch):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    result = cela_main._read_pdf_page_as_image_handler(
        {"path": "../outside.md", "page_number": 1}, {},
    )
    assert result["status"] == "error"
    assert "web_cache外" in result["message"]


def test_page_number_below_one_rejected(tmp_path, monkeypatch):
    path, _ = _seed_cache(tmp_path, monkeypatch)
    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 0}, {},
    )
    assert result["status"] == "error"
    assert "1以上" in result["message"]


def test_page_number_out_of_range_rejected(tmp_path, monkeypatch):
    path, _ = _seed_cache(tmp_path, monkeypatch, page_count=2)
    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 5}, {},
    )
    assert result["status"] == "error"
    assert "全2ページ" in result["message"]


def test_page_count_over_limit_rejected(tmp_path, monkeypatch):
    path, _ = _seed_cache(tmp_path, monkeypatch, page_count=5)
    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1, "page_count": 4}, {},
    )
    assert result["status"] == "error"
    assert "1〜3" in result["message"]


# ---------------------------------------------------------------------------
# 呼び出し上限
# ---------------------------------------------------------------------------

def test_call_limit_enforced(tmp_path, monkeypatch):
    path, _ = _seed_cache(tmp_path, monkeypatch)
    monkeypatch.setattr(cela_main, "_RUNTIME_TOOL_LIMITS", {"max_pdf_vision_calls": 1})
    _install_fake_client(monkeypatch, [])
    state = {"pdf_vision_call_count": 1}  # 既に上限まで消費済み

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "error"
    assert "呼び出し上限" in result["message"]


# ---------------------------------------------------------------------------
# [2026-09-01ユーザー承認] 軽いリトライ（一時的な接続エラーのみ1回まで）
# ---------------------------------------------------------------------------

def test_light_retry_succeeds_on_second_attempt(tmp_path, monkeypatch):
    path, url = _seed_cache(tmp_path, monkeypatch)
    fake = _install_fake_client(monkeypatch, [_make_connection_error(), "リトライ後成功"])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "ok"
    assert result["pages"] == [{"page_number": 1, "description": "リトライ後成功"}]
    assert fake.chat.completions.call_count == 2
    assert state["pdf_vision_call_count"] == 1


def test_gives_up_after_retry_exhausted(tmp_path, monkeypatch):
    path, url = _seed_cache(tmp_path, monkeypatch)
    fake = _install_fake_client(
        monkeypatch, [_make_connection_error(), _make_connection_error()],
    )
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "error"
    assert fake.chat.completions.call_count == 2
    assert state["pdf_vision_call_count"] == 0
    assert not web_tools.pdf_vision_cache_file_path(url, 1).exists()


def test_rate_limit_error_does_not_retry(tmp_path, monkeypatch):
    """RateLimitErrorは一時的な接続断とは異なり実質的なエラーの可能性が高いため、
    軽いリトライの対象外（即座にエラーを返す）。"""
    path, url = _seed_cache(tmp_path, monkeypatch)
    fake = _install_fake_client(monkeypatch, [_make_rate_limit_error()])
    state = {"pdf_vision_call_count": 0}

    result = cela_main._read_pdf_page_as_image_handler(
        {"path": path, "page_number": 1}, state,
    )

    assert result["status"] == "error"
    assert fake.chat.completions.call_count == 1
    assert state["pdf_vision_call_count"] == 0


# ---------------------------------------------------------------------------
# web_tools側のPDFレンダリングヘルパー
# ---------------------------------------------------------------------------

def test_render_pdf_page_to_png_bytes_produces_real_png():
    pdf_bytes = _make_pdf_bytes(page_count=1)
    png_bytes = web_tools.render_pdf_page_to_png_bytes(pdf_bytes, 1, dpi=72)
    assert png_bytes[:8] == b"\x89PNG\r\n\x1a\n"


def test_pdf_page_count_matches_document():
    pdf_bytes = _make_pdf_bytes(page_count=4)
    assert web_tools.pdf_page_count(pdf_bytes) == 4
