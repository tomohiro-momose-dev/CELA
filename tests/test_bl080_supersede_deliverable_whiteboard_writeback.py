"""
BL-080: entry_type="Deliverable"に対するaction_type="SUPERSEDE"が、旧agreement行の
status変更のみで即座にreturnし、Expertが渡したdecision_what（全文）を完全に破棄した
まま「成功」を返す実質何もしないツール呼び出しになっていた問題。

1319ドライラン(log/2026-07-24/1319/log_no_prompt.md)で発見。ExpertがBL-075のプロンプト
（editsの完全一致に失敗した場合、decision_whatによる全文更新＝SUPERSEDEを使えという誘導）
に従いSUPERSEDEを実行したところ、write_agreementは{'success': True}を返したが、直後に
read_deliverable_fileで読み戻すと旧内容のままだった。ExpertはこれをAI自身の理由で
「システムの反映タイミングの問題」と誤って自己正当化し、Detector/Userからハルシネーション
（虚偽の更新完了報告）と判定され続ける無限ループに陥っていた。実際にはツール自体が
ホワイトボードへ一切書き込んでいなかったことが根本原因。

対策: entry_type=="Deliverable"かつSUPERSEDEでlen(decision_what) > 200
（CREATE/UPDATE全文置換と同一の閾値）の場合、CREATE/UPDATEと同様にapply_whiteboard_patch
で新版を保存する。BL-062のDetectorによる無効化用途（短い理由文のみ、ホワイトボードには
触れない）との後方互換は同じ閾値で維持される。

参照: docs/design/issue_backlog.md BL-080。
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
    db_path = str(tmp_path / "test_bl080.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_bl080_supersede_deliverable_with_long_content_writes_to_whiteboard(db_conn):
    """entry_type=Deliverableに対しSUPERSEDE＋長文decision_whatを渡した場合、
    旧agreement行がSupersededになるだけでなく、実際にwhiteboard_draftsへ
    新しいバージョンとして保存されること（read_deliverable_fileが読める状態になること）。"""
    conn, run_id = db_conn
    long_content_v1 = "# task_1_1 予算内訳書\n\nオペレーター3名体制。\n" + ("初版の本文。" * 60)
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_1 予算内訳書", "decision_what": long_content_v1,
            "reason_why": "初版作成", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None

    long_content_v2 = "# task_1_1 予算内訳書（修正版）\n\nオペレーター4名体制。\n" + ("修正版の本文。" * 60)
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "SUPERSEDE", "entry_type": "Deliverable", "status": "Proposed",
            "target_topic": "task_1_1 予算内訳書", "topic": "task_1_1 予算内訳書（修正版）",
            "decision_what": long_content_v2, "reason_why": "オペレーター4名体制への修正",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest is not None, "SUPERSEDEされた全文がwhiteboard_draftsへ保存されていない"
    assert "4名体制" in latest["content"]
    assert latest["version"] == 2

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    deliverable_rows = [a for a in agreements if a["entry_type"] == "Deliverable"]
    statuses = sorted(a["status"] for a in deliverable_rows)
    assert statuses == ["Proposed", "Superseded"]
    new_row = next(a for a in deliverable_rows if a["status"] == "Proposed")
    assert new_row["decision_what"].startswith("WHITEBOARD:")


def test_bl080_supersede_with_short_reason_does_not_touch_whiteboard(db_conn):
    """BL-062のDetectorによる無効化用途（短い理由文のみのSUPERSEDE）は、
    従来通りホワイトボードに触れず、agreements行のcontentに短文をそのまま保持すること
    （後方互換の維持）。"""
    conn, run_id = db_conn
    long_content_v1 = "# task_1_1 予算内訳書\n\n" + ("本文をここに記載する。" * 30)
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Approved",
            "topic": "task_1_1 予算内訳書", "decision_what": long_content_v1,
            "reason_why": "初版作成", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )

    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "SUPERSEDE", "entry_type": "Deliverable", "status": "Rejected",
            "target_topic": "task_1_1 予算内訳書", "topic": "task_1_1 予算内訳書",
            "decision_what": "労基法違反のため無効化", "reason_why": "常時2名要件未達",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="detector", task_id="task_1_1",
    )
    assert err is None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 1, "短い理由文のみのSUPERSEDEはホワイトボードを増版させないはず"

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    rejected_row = next(a for a in agreements if a["status"] == "Rejected")
    assert rejected_row["decision_what"] == "労基法違反のため無効化"


def test_bl080_supersede_no_longer_returns_early_without_inserting_new_row():
    """_commit_agreement_from_toolのソースが、SUPERSEDE分岐で即座にreturn Noneせず、
    CREATE/UPDATE共通のホワイトボード保存・INSERT処理へ続く配線になっていること
    （以前は`return None`で新規agreement行が一切INSERTされなかった）。"""
    import inspect
    src = inspect.getsource(cela_main._commit_agreement_from_tool)
    supersede_block = src.split('if action_type == "SUPERSEDE":')[1].split("depends_on_val")[0]
    code_lines = [
        line for line in supersede_block.splitlines()
        if line.strip() and not line.strip().startswith("#")
    ]
    assert not any(line.strip() == "return None" for line in code_lines)
    assert 'action_type in ("CREATE", "SUPERSEDE")' in src
