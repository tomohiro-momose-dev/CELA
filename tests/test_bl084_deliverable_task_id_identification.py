"""
BL-084: entry_type="Deliverable"のUPDATE/SUPERSEDEが、topic文字列の完全一致で
既存agreement行を探しており、Expertが呼び出しごとにtopicの言い回しを変えると
（target_topic省略時のフォールバックは自分自身のtopicになる）既存行を見失い、
old_content/supersede対象が空文字扱いになる問題。

1459ドライラン(log/2026-07-24/1459/log_no_prompt.md)で、同一task_2_4に対する
UPDATE呼び出しのtopicが毎回変化し（"...確率論的リスク反映版"→
"...結論部の数値整合性修正"→"...確率論的リスク反映・修正版"）、target_topicが
一度も指定されなかったため、`edits`が2回とも
「old_textが現在のホワイトボード内容に見つかりませんでした（正規化後の緩い一致も0件でした）」
で失敗した。実際にはBL-081の緩い一致フォールバック自体は無関係で、比較対象の
base_contentがtopic不一致によりそもそも空文字になっていたことが真因だった
（`_apply_text_edits("", edits)`は常に0件/0件になる）。

対策: entry_type=="Deliverable"の場合のみ、topic文字列ではなく(phase_id, task_id)
（whiteboard_draftsと同じ識別子）でSUPERSEDE/UPDATE対象を特定する
新設`_find_active_deliverable_agreement`に切り替えた。Decision/Directiveは
このBLのスコープ外のため従来通りtopicベースのまま。

参照: docs/design/issue_backlog.md BL-084。
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
    db_path = str(tmp_path / "test_bl084.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_bl084_update_edits_succeeds_despite_topic_drift_without_target_topic(db_conn):
    """1459ログの再現: CREATE後、target_topicを一切指定せず、呼び出しごとに
    異なるtopic文字列でUPDATE+editsを送っても、(phase_id, task_id)で既存の
    ホワイトボードが見つかり、editsが正しく適用されること。"""
    conn, run_id = db_conn
    v1 = "# task_2_4 最大待ち時間シミュレーション\n\n" + ("本文。" * 60) + "\n連続超過7.1%という記載。"
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 最大待ち時間シミュレーション（確率論的リスク反映版）",
            "decision_what": v1, "reason_why": "初版作成",
            "phase_id": "phase_2", "task_id": "task_2_4",
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )
    assert err is None

    # target_topic省略・topicは前回と異なる文字列（実ログと同じドリフトパターン）
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 結論部の数値整合性修正",
            "reason_why": "古い数値を修正",
            "phase_id": "phase_2", "task_id": "task_2_4",
            "edits": [{"old_text": "連続超過7.1%という記載。", "new_text": "連続超過3.1%という記載。"}],
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )
    assert err is None, f"topicドリフトでeditsが失敗した（BL-084未修正の再発）: {err}"

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_4")
    assert latest["version"] == 2
    assert "連続超過3.1%という記載。" in latest["content"]


def test_bl084_update_marks_prior_deliverable_row_superseded_despite_topic_drift(db_conn):
    """topicが変化しても、UPDATE成功時に旧agreement行が正しくSupersededへ
    遷移すること（(phase_id, task_id)で正しい行を特定できていることの確認）。"""
    conn, run_id = db_conn
    v1 = "# task_2_4\n\n" + ("本文。" * 60)
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 初版", "decision_what": v1, "reason_why": "初版作成",
            "phase_id": "phase_2", "task_id": "task_2_4",
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 別の言い回しでの更新", "reason_why": "更新",
            "phase_id": "phase_2", "task_id": "task_2_4",
            "edits": [{"old_text": "本文。", "new_text": "改訂本文。", "replace_all": True}],
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    deliverable_rows = [a for a in agreements if a["entry_type"] == "Deliverable"]
    assert len(deliverable_rows) == 2
    statuses = sorted(a["status"] for a in deliverable_rows)
    assert statuses == ["Proposed", "Superseded"]


def test_bl084_supersede_finds_target_by_task_id_despite_topic_drift(db_conn):
    """SUPERSEDE分岐でもtarget_topic省略・topicドリフトの状況で
    (phase_id, task_id)により正しい既存行を無効化・全文置換できること。"""
    conn, run_id = db_conn
    v1 = "# task_2_4\n\n" + ("初版本文。" * 60)
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 初版", "decision_what": v1, "reason_why": "初版作成",
            "phase_id": "phase_2", "task_id": "task_2_4",
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )

    v2 = "# task_2_4（全面改訂）\n\n" + ("改訂本文。" * 60)
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "SUPERSEDE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "task_2_4 まったく違う言い回し",  # target_topic省略
            "decision_what": v2, "reason_why": "全面改訂",
            "phase_id": "phase_2", "task_id": "task_2_4",
        },
        conn, run_id, caller_role="expert", task_id="task_2_4",
    )
    assert err is None

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_2", "task_2_4")
    assert latest["version"] == 2
    assert "改訂本文。" in latest["content"]

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    deliverable_rows = [a for a in agreements if a["entry_type"] == "Deliverable"]
    statuses = sorted(a["status"] for a in deliverable_rows)
    assert statuses == ["Proposed", "Superseded"]


def test_bl084_non_deliverable_entry_types_still_use_topic_based_matching(db_conn):
    """Decision/DirectiveはBL-084のスコープ外であり、従来通りtopic文字列で
    識別されること（意図的にtarget_topic省略時は自分自身のtopicにフォールバックし、
    一致しなければold_contentは空文字のまま＝挙動を変えていないことの回帰確認）。"""
    conn, run_id = db_conn
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Decision", "status": "Proposed",
            "topic": "予算上限の決定", "decision_what": "3000万円",
            "reason_why": "初版", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    # topicが変わっているためtarget_topic省略時は既存行と一致しない（従来通りの挙動）
    err, _ = cela_main._commit_agreement_from_tool(
        {
            "action_type": "UPDATE", "entry_type": "Decision", "status": "Proposed",
            "topic": "予算上限の再検討", "decision_what": "3200万円",
            "reason_why": "見直し", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    assert err is None
    agreements = cela_main.get_agreements_from_db(conn, run_id)
    # 旧Decision行はtopic不一致のためSupersededにならず、Proposedのまま残る（従来と同じ挙動）
    old_row = next(a for a in agreements if a["topic"] == "予算上限の決定")
    assert old_row["status"] == "Proposed"


def test_bl084_find_active_deliverable_agreement_ignores_superseded_rows(db_conn):
    """_find_active_deliverable_agreementが、Supersededになった行を無視し、
    最新のアクティブな行のみを返すこと。"""
    conn, run_id = db_conn
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "CREATE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "t", "decision_what": "# doc\n\n" + ("x" * 250),
            "reason_why": "初版", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    cela_main._commit_agreement_from_tool(
        {
            "action_type": "SUPERSEDE", "entry_type": "Deliverable", "status": "Proposed",
            "topic": "t2", "decision_what": "# doc v2\n\n" + ("y" * 250),
            "reason_why": "改訂", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        conn, run_id, caller_role="expert", task_id="task_1_1",
    )
    active = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_1", "task_1_1")
    assert active is not None
    assert active["topic"] == "t2"
    assert active["status"] != "Superseded"
