"""
BL-085: ホワイトボード保存時にDB（whiteboard_drafts）だけでなく、sqliteクエリなしで
中身を確認・diffできるようMarkdownファイルへも書き出してほしいというユーザー要望への対応。

新設`_write_whiteboard_to_file`を`apply_whiteboard_patch`から呼び出し、
`{log_dir}/whiteboards/{phase_id}_{task_id}_V{version}.md`へバージョンごとに個別保存する。

★[CONSTRAINT] BL-027と同じ理由（importやオフラインテストでlog/配下を無断汚染しない）で、
`MultiLogger._instance`が設定されている（＝実際のドライラン実行中である）場合のみ書き出す。
BL-080〜BL-084のテストはtmp_path上のDBに対しapply_whiteboard_patchを大量に呼ぶため、
無条件で書き出すと本番log/配下がテスト実行のたびに汚染されてしまう。

参照: docs/design/issue_backlog.md BL-085。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl085.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


@pytest.fixture()
def active_multilogger(tmp_path, monkeypatch):
    """MultiLoggerが実行時に初期化済みであるかのように偽装し、log_dirをtmp_path配下に
    向ける（実プロジェクトのlog/を汚染せずに書き出し経路を検証するため）。"""
    monkeypatch.setattr(cela_main.MultiLogger, "_instance", object())
    fake_log_dir = str(tmp_path / "fake_log_dir")
    monkeypatch.setattr(cela_main.MultiLogger, "log_dir", fake_log_dir)
    return fake_log_dir


def test_bl085_apply_whiteboard_patch_writes_file_when_multilogger_active(db_conn, active_multilogger):
    """MultiLoggerが初期化済み（実行時）の場合、apply_whiteboard_patchがバージョンごとに
    Markdownファイルを書き出すこと。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_4", "# 初版本文\n\nテスト内容V1",
        author_role="expert", edit_summary="初版作成",
    )
    v2 = cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_2", "task_2_4", "# 改訂本文\n\nテスト内容V2",
        author_role="expert", edit_summary="修正",
    )
    assert v2 == 2

    wb_dir = os.path.join(active_multilogger, "whiteboards")
    v1_path = os.path.join(wb_dir, "phase_2_task_2_4_V1.md")
    v2_path = os.path.join(wb_dir, "phase_2_task_2_4_V2.md")
    assert os.path.isfile(v1_path), "V1のファイルが書き出されていない"
    assert os.path.isfile(v2_path), "V2のファイルが書き出されていない"

    with open(v1_path, encoding="utf-8") as f:
        v1_content = f.read()
    with open(v2_path, encoding="utf-8") as f:
        v2_content = f.read()

    assert "テスト内容V1" in v1_content
    assert "テスト内容V2" in v2_content
    # 旧バージョンを上書きせず、両方のファイルが個別に残っていること（DBのappend-only方針と同じ）
    assert "テスト内容V1" not in v2_content
    assert "phase_id=phase_2" in v1_content
    assert "task_id=task_2_4" in v1_content
    assert "version=1" in v1_content
    assert "author_role=expert" in v1_content


def test_bl085_apply_whiteboard_patch_skips_file_write_when_multilogger_inactive(db_conn, tmp_path, monkeypatch):
    """MultiLoggerが未初期化（テスト/import時）の場合、ファイル書き出しをスキップし、
    DB保存のみ行われること（本番log/配下を汚染しないことの回帰確認）。"""
    monkeypatch.setattr(cela_main.MultiLogger, "_instance", None)
    fake_log_dir = str(tmp_path / "should_not_be_created")
    monkeypatch.setattr(cela_main.MultiLogger, "log_dir", fake_log_dir)

    conn, run_id = db_conn
    v = cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1", "本文",
        author_role="expert", edit_summary="初版作成",
    )
    assert v == 1
    assert not os.path.isdir(fake_log_dir), "MultiLogger未初期化なのにファイルが書き出された"


def test_bl085_write_whiteboard_to_file_returns_none_when_multilogger_inactive(monkeypatch):
    """_write_whiteboard_to_file自体も、MultiLogger未初期化時はNoneを返し何もしないこと。"""
    monkeypatch.setattr(cela_main.MultiLogger, "_instance", None)
    result = cela_main._write_whiteboard_to_file(
        "phase_1", "task_1_1", 1, "本文", "expert", "初版作成"
    )
    assert result is None
