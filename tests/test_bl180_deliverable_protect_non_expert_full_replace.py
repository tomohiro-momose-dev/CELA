"""
BL-180: BL-179で追加したStage3（統合承認判断）プロンプトの「decision_whatは短い承認コメントで
構いません」という文言に文字数の言及がなく、User AIが200字を超える承認理由を書いた結果、
BL-127の「200字以下なら保護」判定に外れて全文置換の抜け道（`_commit_agreement_from_tool`の
`len(raw_content) > 200`分岐）へ入り、既存の完全なホワイトボード本文（Expertが作成した詳細
仕様書）が3行の承認コメントへ丸ごと上書きされる事故が発生した。

`log/2026-08-05/1639`のtask_1_2で実際に発生（Ver.1の74行の詳細仕様書がVer.2で3行の承認文へ
全置換）。task_1_1では同じStage3が`edits`を使ったため無事だったが、`edits`使用はLLMの任意
判断に委ねられており、保証されていなかった。

根本原因: 200字という長さだけでUPDATEの意図（承認コメント vs 全文置換）を判定していたが、
BL-169により entry_type="Deliverable" の内容執筆はexpertロールのみに許可されている
（user/detector等は承認・却下しかできない）。したがって、既にホワイトボード化済みの完全版に
対してexpert以外がedits未指定でUPDATEする場合、文字数によらず常に「承認/却下コメント」であり、
全文置換の正当な用途は存在しない。

対策: `_commit_agreement_from_tool`のUPDATE分岐で、200字超の全文置換パスへ入る条件に
`caller_role == "expert" or not is_whiteboard`を追加。expert以外からの更新は、既にホワイト
ボード化済みの完全版が存在する限り、decision_whatの長さによらず常に保護する。

参照: docs/design/back_log/issue_backlog.md BL-180。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl180.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _create_whiteboard_deliverable(conn, run_id):
    long_content = "# task_1_2 詳細仕様書\n\n必要台数3台と算出。\n" + ("補足説明文。" * 40)
    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_2 成果物", "decision_what": long_content,
            "reason_why": "初版作成", "phase_id": "phase_1", "task_id": "task_1_2",
        },
        conn, run_id, caller_role="expert", task_id="task_1_2",
    )
    assert err is None
    assert warning is None
    return long_content


def test_user_role_long_decision_what_on_whiteboard_is_protected_not_replaced(db_conn):
    """[BL-180実インシデント再現] User AI（Stage3）が200字を超える承認コメントをdecision_what
    で送っても、既存の完全なホワイトボード本文は上書きされずprotected_warningが返ること。"""
    conn, run_id = db_conn
    original_content = _create_whiteboard_deliverable(conn, run_id)

    long_approval_comment = (
        "【第3段 統合承認判断】task_1_2成果物を承認する（Approved）。受入基準3点（①ピーク時需要"
        "約66.7人/時、②必要台数3台、③代替案4台・10人/便の不足）はすべて充足。明記事項（輸送能力"
        "のみから導いた台数で予算整合はタスク2_1、仮定値3点のprovisional登録と実証要検証、"
        "demand_timeslot_gapのタスク3_2引き継ぎ）も発注者指示どおり。confidence指針も指示どおり"
        "（4変数すべてprovisional、ピーク時需要66.7人/時は機械的導出のためowns_variablesに含めず"
        "導出根拠200÷3を明記）。第1段・第2段の残存懸念はすべて後続タスク（1_3・2_1・3_2・4系）"
        "への引き継ぎ事項として適切に処理されており、本タスクの不備ではない。task_1_2をクローズする。"
    )
    assert len(long_approval_comment) > 200

    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved",
            "topic": "task_1_2 成果物", "decision_what": long_approval_comment,
            "reason_why": "承認", "phase_id": "phase_1", "task_id": "task_1_2",
        },
        conn, run_id, caller_role="user", task_id="task_1_2",
    )
    assert err is None
    assert warning is not None
    assert "task_1_2" in warning or "成果物" in warning

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_2")
    assert latest["version"] == 1, "expert以外からの長文decision_whatはホワイトボードを増版させないはず"
    assert latest["content"] == original_content, "既存の完全版が上書きされず温存されているはず"


def test_expert_role_long_decision_what_still_replaces_as_before(db_conn):
    """[対照/非退行確認] expertロールによる200字超のdecision_what全文置換は、BL-180以前と
    同じくそのまま反映されること（既存のBL-127正常系を壊していないことの確認）。"""
    conn, run_id = db_conn
    _create_whiteboard_deliverable(conn, run_id)

    revised_content = "# task_1_2 詳細仕様書（改訂版）\n\n必要台数4台に修正。\n" + ("補足説明文。" * 40)
    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_1_2 成果物", "decision_what": revised_content,
            "reason_why": "Detector指摘を受けた全文改訂", "phase_id": "phase_1", "task_id": "task_1_2",
        },
        conn, run_id, caller_role="expert", task_id="task_1_2",
    )
    assert err is None
    assert warning is None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_2")
    assert latest["version"] == 2
    assert "4台に修正" in latest["content"]


def test_detector_role_long_decision_what_on_whiteboard_is_also_protected(db_conn):
    """[BL-180一般化] user以外の非expertロール（detector）でも同様に保護されること。"""
    conn, run_id = db_conn
    original_content = _create_whiteboard_deliverable(conn, run_id)

    long_rejection_comment = (
        "この成果物には重大な計算ミスがあり却下します。前提値の根拠が不十分であり、"
        "特に平均往復時間の設定が実態と乖離しています。再検証の上、再提出してください。"
        "併せて代替案の比較も見直しが必要です。"
    ) * 3
    assert len(long_rejection_comment) > 200

    err, warning = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Rejected",
            "topic": "task_1_2 成果物", "decision_what": long_rejection_comment,
            "reason_why": "却下", "phase_id": "phase_1", "task_id": "task_1_2",
        },
        conn, run_id, caller_role="detector", task_id="task_1_2",
    )
    assert err is None
    assert warning is not None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_2")
    assert latest["version"] == 1
    assert latest["content"] == original_content
