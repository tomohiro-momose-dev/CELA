"""
BL-127: `write_agreement`のUPDATEがDB上は成功しても、ホワイトボード本体には反映されない
（または反映確認に失敗する）ケースが実際に発生した問題。

`log/2026-07-28/1233`のDetector再検証で発見。需要試算の計算ミスについてExpertが
`write_agreement`で`UPDATE`を実行し「修正が正常に適用されたことを確認しました」と
自己申告したが、Detectorが再検証したところホワイトボード本文には旧値が3箇所とも残存していた。

根本原因: `_commit_agreement_from_tool`のUPDATE分岐には、entry_type="Deliverable"かつ
edits未指定・decision_whatが200字以下の短文（＝「承認コメント」等とみなす保護仕様、H2踏襲）
の場合にホワイトボード本体を意図的に上書きしない「保護」ブランチが存在するが、従来は
`print()`のみでLLM側の呼び出し元へは一切伝わらず、他の実際に反映されたUPDATEと同一の
`{"success": True}`が返っていた。ExpertはDB上「成功」と返ってきたことをもって、実際には
一切変更されていないホワイトボードに対し「修正が反映された」と誤って自己申告していた。

対策: `_commit_agreement_from_tool`の戻り値を`str | None`（error）から
`tuple[str | None, str | None]`（error, protected_warning）へ拡張し、保護ブランチが
発動した場合はprotected_warningに具体的な理由を設定。`_write_agreement_impl`はこれを
`{"success": True, ..., "warning": "..."}`としてツール呼び出し元（Expert/User AI）へ
明示的に伝える。

参照: docs/design/back_log/issue_backlog.md BL-127。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl127.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


_PHASES = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}]


def _create_whiteboard_deliverable(conn, run_id):
    long_content = "# task_1_1 需要試算\n\n140人/日、−65%と算出。\n" + ("補足説明文。" * 40)
    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算", "decision_what": long_content,
            "reason_why": "初版作成", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    assert warning is None
    return long_content


# --- _commit_agreement_from_tool レベル ---

def test_commit_update_short_content_on_whiteboard_returns_protected_warning(db_conn):
    """[BL-127実インシデント再現] editsを指定せず200字以下の短文のみでUPDATEすると、
    ホワイトボード本体は変更されない（保護仕様）が、従来はそのことが呼び出し元へ
    一切伝わらなかった。今回の修正でprotected_warningとして明示されること。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算", "decision_what": "修正が正常に適用されたことを確認しました",
            "reason_why": "1月係数の適用漏れを修正", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    assert warning is not None
    assert "task_1_1 需要試算" in warning

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 1, "短文のみのUPDATEはホワイトボードを増版させないはず"
    assert "140人/日" in latest["content"], "旧値が残存しているはず（保護仕様が正しく機能）"


def test_commit_update_no_content_no_edits_returns_protected_warning(db_conn):
    """decision_what/editsのいずれも指定しないUPDATEも、実質的な変更が無いため
    protected_warningを返すこと。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算", "decision_what": "",
            "reason_why": "コメントのみ", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    assert warning is not None


def test_commit_update_with_edits_returns_no_warning(db_conn):
    """[対照] editsで実際に差分置換が成功した場合はprotected_warningがNoneのままで、
    ホワイトボードは実際にバージョンアップすること（正常系への影響がないことの確認）。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算",
            "edits": [{"old_text": "140人/日、−65%と算出。", "new_text": "105人/日、−74%と算出。"}],
            "reason_why": "1月係数の適用漏れを修正", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    assert warning is None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 2
    assert "105人/日" in latest["content"]
    assert "140人/日" not in latest["content"]


def test_commit_update_with_long_raw_content_on_existing_whiteboard_is_protected(db_conn):
    """[BL-261] edits未指定で200字を超える全文が渡された場合でも、既にホワイトボード化
    済みの完全版が存在する限りcaller_role="expert"でも全文置換されず、既存の完全版が
    保護されてprotected_warningが返ること（旧仕様=expertは無条件通過、はtask_1_5の
    282行→2行消失事故の直接原因だったため保護対象へ変更）。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    new_long_content = "# task_1_1 需要試算（修正版）\n\n105人/日、−74%と算出。\n" + ("補足説明文。" * 40)
    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算", "decision_what": new_long_content,
            "reason_why": "全文修正", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    assert warning is not None and "edits" in warning

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 1
    assert "105人/日" not in latest["content"]


# --- _write_agreement_impl レベル（ツール応答としてExpertへ実際に返る形） ---

def test_write_agreement_impl_surfaces_warning_for_protected_update(db_conn):
    """[BL-127] write_agreementツールの応答自体に"warning"フィールドが含まれ、
    Expertが次のターンで気づける形になっていること。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    result = cela_main._write_agreement_impl(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算", "decision_what": "修正が正常に適用されたことを確認しました",
            "reason_why": "1月係数の適用漏れを修正", "phase_id": "phase_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1", phases=_PHASES,
    )
    assert result["success"] is True
    assert "warning" in result
    assert result["warning"]

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 1, "警告が出るケースでは実際にホワイトボードが更新されていないはず"


def test_write_agreement_impl_no_warning_for_successful_edits_update(db_conn):
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    result = cela_main._write_agreement_impl(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 需要試算",
            "edits": [{"old_text": "140人/日、−65%と算出。", "new_text": "105人/日、−74%と算出。"}],
            "reason_why": "1月係数の適用漏れを修正", "phase_id": "phase_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1", phases=_PHASES,
    )
    assert result["success"] is True
    assert "warning" not in result
