"""
BL-276: ログファイル（log_no_prompt.md/log_with_prompt.md）の各行頭へ実行時刻を付与し、
事後的に各ステップの所要時間を追跡できるようにする。

`MultiLogger.write()`は`sys.stdout`差し替え経由でPython組み込みの`print()`から呼ばれるが、
`print()`は1回の呼び出しで本体テキストとend('\n')を別々の`write()`として渡すため、単純に
毎write()呼び出しの先頭へタイムスタンプを付けると、文の途中や巨大な複数行JSON dumpの内部に
まで挿入されてしまう。`MultiLogger._stamp_for_file`は「このwrite()呼び出し自体が行頭から
始まるか」だけを見て判定し、行頭から始まる場合にのみメッセージの先頭（1箇所のみ、埋め込まれた
改行ごとには付け直さない）へ`[HH:MM:SS]`を付与する。

ターミナル表示は対象外（生のmessageをそのまま出す）。file_with_prompt/file_no_promptは
is_prompt_modeにより受け取る内容が分岐する（file_with_promptのみが受け取るメッセージがある）
ため、行頭状態はそれぞれ独立に追跡する。

参照: docs/design/back_log/issue_backlog.md BL-276。実LLM API呼び出しは伴わない。
"""

import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

_TS_RE = re.compile(r"^\[\d{2}:\d{2}:\d{2}\] ")


# ---------------------------------------------------------------------------
# 1. _stamp_for_file（純粋関数、self未使用のためインスタンス生成不要）
# ---------------------------------------------------------------------------

def _stamp(message, at_line_start):
    # _stamp_for_fileはselfを参照しないため、未束縛メソッドとしてNoneを渡して直接呼べる。
    return cela_main.MultiLogger._stamp_for_file(None, message, at_line_start)


def test_stamp_applied_at_line_start():
    stamped, new_state = _stamp("hello\n", True)
    assert _TS_RE.match(stamped)
    assert stamped.endswith("hello\n")
    assert new_state is True


def test_stamp_not_applied_mid_line():
    stamped, new_state = _stamp("world\n", False)
    assert stamped == "world\n"
    assert new_state is True


def test_empty_message_passthrough():
    stamped, new_state = _stamp("", True)
    assert stamped == ""
    assert new_state is True  # 空メッセージは状態を変えない


def test_multiline_message_only_stamps_once_at_the_top():
    """[設計判断] 埋め込まれた改行ごとに付け直すと巨大な複数行JSON dump等の内部にまで
    タイムスタンプが挿入され可読性を落とすため、呼び出し1回につき先頭のみ付与する。"""
    stamped, new_state = _stamp("line1\nline2\nline3\n", True)
    lines = stamped.split("\n")
    assert _TS_RE.match(lines[0])
    assert lines[1] == "line2"
    assert lines[2] == "line3"
    assert new_state is True


def test_at_line_start_becomes_false_without_trailing_newline():
    stamped, new_state = _stamp("partial output", True)
    assert _TS_RE.match(stamped)
    assert new_state is False

    # 続きのwrite()（行頭ではない）はタイムスタンプを付けない
    stamped2, new_state2 = _stamp(" continued\n", new_state)
    assert stamped2 == " continued\n"
    assert new_state2 is True


# ---------------------------------------------------------------------------
# 2. MultiLogger.write()の統合確認（tmp_path隔離、BL-175と同じ後始末パターン）
# ---------------------------------------------------------------------------

def _fresh_logger(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    original_log_dir = cela_main.MultiLogger.log_dir
    cela_main.MultiLogger._instance = None
    cela_main.MultiLogger._initialized = False
    logger = cela_main.MultiLogger()
    return logger, original_log_dir


def _close_logger(logger, original_log_dir):
    logger.file_with_prompt.close()
    logger.file_no_prompt.close()
    cela_main.MultiLogger._instance = None
    cela_main.MultiLogger._initialized = False
    cela_main.MultiLogger.log_dir = original_log_dir


def test_write_stamps_log_files_but_not_terminal(monkeypatch, tmp_path):
    logger, original_log_dir = _fresh_logger(monkeypatch, tmp_path)
    try:
        captured_terminal = []
        monkeypatch.setattr(logger, "terminal", type(
            "FakeTerm", (), {"write": lambda self, m: captured_terminal.append(m), "flush": lambda self: None}
        )())

        # print("🔧 test message") 相当: 本体write()とend('\n')write()の2回に分かれる
        logger.write("🔧 test message")
        logger.write("\n")

        logger.file_with_prompt.flush()
        logger.file_no_prompt.flush()
        with open(logger.filename_no, encoding="utf-8") as f:
            content_no = f.read()
        with open(logger.filename_with, encoding="utf-8") as f:
            content_with = f.read()

        # ターミナルは無加工のまま
        assert captured_terminal == ["🔧 test message", "\n"]
        # ログファイルは行頭にタイムスタンプが付く
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\] 🔧 test message", content_no)
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\] 🔧 test message", content_with)
    finally:
        _close_logger(logger, original_log_dir)


def test_write_does_not_double_stamp_the_newline_only_write(monkeypatch, tmp_path):
    """print()の本体write()とend('\n')のwrite()が連続しても、2つ目のwrite()（改行のみ）に
    タイムスタンプが付いて`[HH:MM:SS] \n`のような空行が挿入されないこと。"""
    logger, original_log_dir = _fresh_logger(monkeypatch, tmp_path)
    try:
        logger.write("line A")
        logger.write("\n")
        logger.write("line B")
        logger.write("\n")

        logger.file_no_prompt.flush()
        with open(logger.filename_no, encoding="utf-8") as f:
            content = f.read()

        # 各行は1回だけタイムスタンプされ、改行だけの空スタンプ行は挿入されない
        assert content.count("line A") == 1
        assert content.count("line B") == 1
        stamped_lines = [l for l in content.split("\n") if _TS_RE.match(l)]
        assert any("line A" in l for l in stamped_lines)
        assert any("line B" in l for l in stamped_lines)
        assert not any(l.strip() == "" for l in [_TS_RE.sub("", l) for l in stamped_lines])
    finally:
        _close_logger(logger, original_log_dir)


def test_prompt_mode_and_no_prompt_mode_track_line_start_independently(monkeypatch, tmp_path):
    """[BL-276] is_prompt_mode=Trueの間はfile_with_promptのみが更新され、file_no_promptの
    行頭状態は変化しない（両ファイルの内容が分岐しても、それぞれ独立に正しくスタンプされる）。"""
    logger, original_log_dir = _fresh_logger(monkeypatch, tmp_path)
    try:
        logger.set_prompt_mode(True)
        logger.write("prompt-only content\n")  # file_with_promptのみ

        logger.set_prompt_mode(False)
        logger.write("shared content\n")  # 両方

        logger.file_with_prompt.flush()
        logger.file_no_prompt.flush()
        with open(logger.filename_with, encoding="utf-8") as f:
            content_with = f.read()
        with open(logger.filename_no, encoding="utf-8") as f:
            content_no = f.read()

        assert "prompt-only content" in content_with
        assert "prompt-only content" not in content_no
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\] prompt-only content", content_with)
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\] shared content", content_with)
        assert re.search(r"\[\d{2}:\d{2}:\d{2}\] shared content", content_no)
    finally:
        _close_logger(logger, original_log_dir)


# ---------------------------------------------------------------------------
# 3. §17.1後段: ソース存在証明
# ---------------------------------------------------------------------------

def test_stamp_helper_present_in_source():
    import inspect
    src = inspect.getsource(cela_main.MultiLogger)
    assert "_stamp_for_file" in src
    assert "_at_line_start_with" in src
    assert "_at_line_start_no" in src
