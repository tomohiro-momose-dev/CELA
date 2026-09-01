"""
BL-330: decision_extractor_nodeの直接書き込みフォールバック経路（write_agreementツール本体
＝_write_agreement_implとは別の書き込み口）が、UPDATE/Approved_with_Conditions時の旧レコード
特定を`topic`文字列一致のみ（`task_id`不問）で行っており、topicが一致する別task_idの行を
誤って掴んでしまう欠陥の再現・修正確認。

実インシデント: log/2026-08-31/1917（run_id=1787890406-1e73a89d）で、task_4_2のOpEx成果物と
同じtopic文字列を持つtask_4_1側の誤登録行が存在した状態でUPDATE(Approved_with_Conditions)が
発生し、そのtask_4_1側の行がsupersedeされ、かつtask_4_2の新しい行がtask_4_1のホワイトボード
ポインタ（WHITEBOARD:phase_4:task_4_1）を継承してしまった。

この設計は既にBL-084で解決済みのはずだった——`_write_agreement_impl`内の同型3箇所
（4041-4049のSUPERSEDE分岐・4098-4119のUPDATE分岐・4241-4250のsupersede実行分岐）は、
いずれも`entry_type=="Deliverable"`の場合のみ`_find_active_deliverable_agreement`
（task_id基準）を使う分岐が既に入っている。decision_extractor_node自身の直接書き込み経路
（旧17957-17964）だけがこの3箇所と非対称に取り残されていた（AGENTS.md §13.4）。

対応: 該当箇所をentry_type=="Deliverable"の場合のみ`_find_active_deliverable_agreement`
（task_id基準）を使う分岐へ変更し、非Deliverable（Decision/Directive）は従来通りtopic一致の
ままとする（BL-084のスコープ外という既存の意図的設計を維持）。

参照: docs/design/back_log/BL-330/BL330_basic_design.md、issue_backlog.md BL-330。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl330.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


def _phases():
    return [{"phase_id": "phase_4", "tasks": [{"task_id": "task_4_1"}, {"task_id": "task_4_2"}]}]


def _base_state(run_id, phases, chat_content, current_task_id="task_4_2"):
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": phases[0],
        "current_task_id": current_task_id,
        "chat_history": [{"role": "user", "content": chat_content}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False,
        "user_wrote_agreement": False,
    }


def _mock_extractor(item):
    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return ([item], {"advances_to_phase_id": None, "advances_to_task_id": None})
    return _fake


def _create_deliverable(conn, run_id, phases, task_id, topic, content_marker):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    phase_id = next(p["phase_id"] for p in phases if any(t["task_id"] == task_id for t in p["tasks"]))
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": topic,
            "decision_what": content_marker + "。" + "X" * 300,
            "reason_why": "初版", "entry_type": "Deliverable",
            "phase_id": phase_id, "task_id": task_id,
        },
        {"run_id": run_id, "current_task_id": task_id, "phases": phases},
    )
    assert result["success"] is True, result.get("error")
    return topic


# ---------------------------------------------------------------------------
# 1. 1917実インシデントの再現: topic衝突時、task_idで正しい行を選ぶこと
# ---------------------------------------------------------------------------

def test_deliverable_update_picks_row_by_task_id_not_by_topic_alone(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()
    shared_topic = "task_4_2成果物（案）：OpEx人件費の積算（遠隔監視員・現場措置要員・コールセンター）"

    # task_4_2の正当な初版を先に作る。
    _create_deliverable(conn, run_id, phases, "task_4_2", shared_topic, "task_4_2の正しい内容")
    # task_4_1へ同じtopicで誤登録された行（1917のb6f773相当、後発）。
    _create_deliverable(conn, run_id, phases, "task_4_1", shared_topic, "task_4_1の無関係な内容（誤登録）")

    state = _base_state(run_id, phases, "task_4_2を条件付き承認します。", current_task_id="task_4_2")
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved_with_Conditions",
        "target_topic": shared_topic, "content": "承認条件つきコメント", "rationale": "承認",
        "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_2",
    }))

    cela_main.decision_extractor_node(state)

    task_4_2_target = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_4", "task_4_2")
    task_4_1_target = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_4", "task_4_1")

    assert task_4_2_target is not None
    assert task_4_2_target["status"] == "Approved_with_Conditions"
    # task_4_1側の行は無関係のまま生き残っている必要がある（誤ってsupersedeされ、
    # そのホワイトボードポインタをtask_4_2側が継承していないこと＝1917再発防止の核心）。
    assert task_4_1_target is not None, "task_4_1のDeliverableが誤ってsupersedeされた（BL-330再発）"
    assert task_4_1_target["status"] != "Superseded"
    assert task_4_1_target["decision_what"].startswith("WHITEBOARD:")


# ---------------------------------------------------------------------------
# 2. 非退行: 非Deliverable（Decision/Directive）は従来通りtopic一致で動作すること
# ---------------------------------------------------------------------------

def test_decision_update_still_uses_topic_match_non_regression(db_conn, monkeypatch):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    first = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_4_2却下判定",
            "decision_what": "初回の却下理由", "reason_why": "r", "entry_type": "Decision",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        {"run_id": run_id, "current_task_id": "task_4_2"},
    )
    assert first["success"] is True

    phases = _phases()
    state = _base_state(run_id, phases, "改めて却下します。", current_task_id="task_4_2")
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Decision", "status": "Rejected",
        "target_topic": "task_4_2却下判定", "content": "更新後の却下理由", "rationale": "r2",
        "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_2",
    }))

    cela_main.decision_extractor_node(state)

    rows = [a for a in cela_main.get_agreements_from_db(conn, run_id) if a["topic"] == "task_4_2却下判定"]
    superseded = [a for a in rows if a["status"] == "Superseded"]
    active = [a for a in rows if a["status"] != "Superseded"]
    assert len(superseded) == 1
    assert len(active) == 1
    assert active[0]["decision_what"] == "更新後の却下理由"


# ---------------------------------------------------------------------------
# 3. 対象task_idにアクティブなDeliverableが存在しない場合、従来通りold_content=""のまま
# ---------------------------------------------------------------------------

def test_deliverable_update_with_no_active_row_for_task_id_behaves_as_before(db_conn, monkeypatch):
    conn, run_id = db_conn
    phases = _phases()
    state = _base_state(run_id, phases, "task_4_2成果物（案）を提出します。", current_task_id="task_4_2")
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved_with_Conditions",
        "target_topic": "task_4_2成果物（案）：まだ存在しないtopic", "content": "初回の承認相当",
        "rationale": "承認", "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_2",
    }))

    # 例外を投げず、supersede対象なしのまま処理が完了すること。
    cela_main.decision_extractor_node(state)

    target = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_4", "task_4_2")
    assert target is not None
    assert target["status"] == "Approved_with_Conditions"


# ---------------------------------------------------------------------------
# 4. target_topicが実体のtopicへ揃うこと（呼び出し元のtarget_topicがドリフトしているケース）
# ---------------------------------------------------------------------------

def test_deliverable_update_target_topic_snaps_to_actual_topic(db_conn, monkeypatch, capsys):
    conn, run_id = db_conn
    phases = _phases()
    actual_topic = "task_4_2成果物（案）：OpEx人件費の積算・確定Ver.3"
    _create_deliverable(conn, run_id, phases, "task_4_2", actual_topic, "task_4_2の内容")

    state = _base_state(run_id, phases, "task_4_2を承認します。", current_task_id="task_4_2")
    # LLMが少しドリフトしたtarget_topicを返す（実体は上のactual_topicのまま）。
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved_with_Conditions",
        "target_topic": "task_4_2成果物（案）：OpEx人件費の積算（ドリフトした言い回し）",
        "content": "承認コメント", "rationale": "承認", "proposed_by": "User",
        "phase_id": "phase_4", "task_id": "task_4_2",
    }))

    cela_main.decision_extractor_node(state)

    rows = [a for a in cela_main.get_agreements_from_db(conn, run_id) if a["topic"] == actual_topic]
    active = [a for a in rows if a["status"] != "Superseded"]
    assert len(active) == 1, "target_topicドリフトにより実体のtopicへ追従できず孤児化した"
    assert active[0]["status"] == "Approved_with_Conditions"
