"""
BL-335 Phase 3: python_replサンドボックスへのpandasアクセス（read_cached_bytesヘルパー＋
socket.socket無効化によるSSRF迂回対策）の単体テスト。`_PythonReplSession`は実サブプロセス
（sys.executable）を起動する——モックではなく実運用相当の経路で検証する。

参照: docs/design/back_log/BL-335/BL335_basic_design.md §3。
"""

import io
import os
import sys

import openpyxl
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402
import web_tools  # noqa: E402


def _make_xlsx_bytes() -> bytes:
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.append(["name", "age"])
    ws.append(["Alice", 30])
    ws.append(["Bob", 25])
    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


def _seed_xlsx_cache(tmp_path, monkeypatch, url="https://example.com/data.xlsx"):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    web_tools.write_cache(web_tools.cache_file_path(url), url, "xlsx本文（markitdown変換済み、崩れている想定）")
    raw_path = web_tools.raw_cache_file_path(url, ".xlsx")
    web_tools.write_raw_cache(raw_path, _make_xlsx_bytes())
    return raw_path.name


@pytest.fixture
def session():
    s = cela_main._PythonReplSession(timeout=15.0)
    yield s
    s.close()


# ---------------------------------------------------------------------------
# pandas + read_cached_bytes の正常系
# ---------------------------------------------------------------------------

def test_pandas_reads_cached_xlsx_via_read_cached_bytes(tmp_path, monkeypatch, session):
    xlsx_name = _seed_xlsx_cache(tmp_path, monkeypatch)
    code = (
        "import pandas as pd, io\n"
        "raw = read_cached_bytes(" + repr(xlsx_name) + ")\n"
        "df = pd.read_excel(io.BytesIO(raw))\n"
        "print(df.shape)\n"
        "print(list(df.columns))\n"
    )
    out = session.run(code)
    assert "(2, 2)" in out
    assert "'name', 'age'" in out


def test_read_cached_bytes_rejects_path_traversal(tmp_path, monkeypatch, session):
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    (tmp_path / "web_cache").mkdir(parents=True, exist_ok=True)
    code = "print(read_cached_bytes('../outside.txt'))\n"
    out = session.run(code)
    assert "ValueError" in out or "Error" in out


# ---------------------------------------------------------------------------
# サンドボックス境界（既存不変条件の非退行）
# ---------------------------------------------------------------------------

def test_open_still_rejected_by_ast_safety_check(tmp_path, monkeypatch, session):
    """[BL-335] read_cached_bytes以外の経路でファイルを読めないことの回帰確認。
    _check_repl_code_safetyはLLM生成コード（openの呼び出し）にのみ適用される。"""
    result = cela_main._check_repl_code_safety("open('/etc/passwd').read()")
    assert result is not None
    assert "open" in result


def test_disallowed_import_still_rejected():
    result = cela_main._check_repl_code_safety("import os\nprint(os.getcwd())")
    assert result is not None
    assert "os" in result


def test_pandas_and_io_now_allowed():
    assert cela_main._check_repl_code_safety("import pandas\nprint(1)") is None
    assert cela_main._check_repl_code_safety("import io\nprint(1)") is None


# ---------------------------------------------------------------------------
# [Cline diffレビューF1] pandas経由のローカルファイルアクセスも遮断する
# ---------------------------------------------------------------------------

def test_pandas_cannot_read_arbitrary_local_file(session):
    """[Cline diffレビューF1] pandas.read_csv/read_excel等はbuiltins.openを禁止する
    AST検査を経由しないため、read_cached_bytes以外の任意ローカルファイルを直接読めて
    しまっていた（requirements.txtの読み取りを実プローブで確認済み）。builtins.open/
    io.open自体の無効化で塞がれていること。"""
    out = session.run(
        "import pandas as pd\n"
        "try:\n"
        "    pd.read_csv('requirements.txt', header=None)\n"
        "    print('READ_SUCCEEDED')\n"
        "except OSError as e:\n"
        "    print('BLOCKED', str(e)[:60])\n"
    )
    assert "BLOCKED" in out
    assert "READ_SUCCEEDED" not in out


def test_pandas_cannot_write_arbitrary_local_file(tmp_path, session):
    """[Cline diffレビューF1] pd.DataFrame.to_csv等での任意パスへの書き込みも
    builtins.open/io.openの無効化で塞がれていること（実プローブで書き込み成立を
    確認済みだった欠陥の回帰テスト）。"""
    probe_path = str(tmp_path / "f1_probe.csv").replace("\\", "\\\\")
    out = session.run(
        "import pandas as pd\n"
        "try:\n"
        f"    pd.DataFrame({{'a': [1]}}).to_csv('{probe_path}')\n"
        "    print('WRITE_SUCCEEDED')\n"
        "except OSError as e:\n"
        "    print('BLOCKED', str(e)[:60])\n"
    )
    assert "BLOCKED" in out
    assert "WRITE_SUCCEEDED" not in out
    assert not (tmp_path / "f1_probe.csv").exists()


def test_existing_math_statistics_checks_non_regressed(session):
    """[BL-335] sys.executable化後もmath/statistics等の既存検算が引き続き動くこと。"""
    out = session.run("import statistics\nprint(statistics.mean([1, 2, 3]))\n")
    assert "2" in out


# ---------------------------------------------------------------------------
# [ユーザー承認済み] socket.socket無効化の直接検証（本Phaseの中核的安全対策）
# ---------------------------------------------------------------------------

def test_pandas_network_read_is_blocked_not_bypassed(session):
    """[BL-335] pandasはLLMコード側で`import socket`を書かなくても、内部依存
    （urllib3/fsspec等）が`import socket`することでネットワークへ到達しうる——
    AST許可リストはLLM自身のトップレベルimportしか見ないため、この経路はAST検査を
    素通りする。ブートストラップのsocket.socket差し替えはPythonのモジュールキャッシュ
    （sys.modules）越しに効くため、pandas内部の`import socket`も同じ差し替え済み
    オブジェクトを参照する。理論上の保証ではなく実行結果で確認する（self-review所見2）。"""
    code = (
        "import pandas as pd\n"
        "try:\n"
        "    pd.read_csv('http://169.254.169.254/latest/meta-data/')\n"
        "except Exception as e:\n"
        "    print(type(e).__name__, str(e)[:100])\n"
    )
    out = session.run(code)
    assert "OSError" in out or "URLError" in out or "ConnectionError" in out


# ---------------------------------------------------------------------------
# 生バイト無しキャッシュ（BL-335適用前）への出口
# ---------------------------------------------------------------------------

def test_read_cached_bytes_raises_file_not_found_for_missing_raw(tmp_path, monkeypatch, session):
    url = "https://example.com/pre-bl335.xlsx"
    monkeypatch.setattr(web_tools, "WEB_CACHE_DIR", str(tmp_path / "web_cache"))
    web_tools.write_cache(web_tools.cache_file_path(url), url, "BL-335適用前の本文")
    md_name = web_tools.cache_file_path(url).name
    xlsx_name = md_name.replace(".md", ".xlsx")

    code = f"print(read_cached_bytes({xlsx_name!r}))\n"
    out = session.run(code)
    assert "FileNotFoundError" in out


# ---------------------------------------------------------------------------
# _run_python_repl（単発版）側の同一対策（AGENTS.md §13.4対称性）
# ---------------------------------------------------------------------------

def test_run_python_repl_also_allows_pandas_and_blocks_network():
    # [Cline diffレビューF4] pandasのcold importは既定timeout=5.0秒だと低速環境で
    # 超過しうる（flakyリスク）ため明示的に延長する。
    out = cela_main._run_python_repl("import pandas\nprint('imported')\n", timeout=15.0)
    assert "imported" in out
    code = (
        "import pandas as pd\n"
        "try:\n"
        "    pd.read_csv('http://169.254.169.254/latest/meta-data/')\n"
        "except Exception as e:\n"
        "    print(type(e).__name__)\n"
    )
    out2 = cela_main._run_python_repl(code, timeout=15.0)
    assert "OSError" in out2 or "URLError" in out2 or "ConnectionError" in out2
