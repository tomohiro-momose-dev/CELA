"""
BL-206: write_agreementのUPDATE(edits)が、実際には存在するold_textに対して繰り返し
「見つかりません（緩い一致0件）」で失敗し続ける事故の根本原因の再現・修正確認。

調査の結果、原因は`decision_extractor_node`のUPDATE分岐（フォールバック経路）にあった。
以下2種類のドリフトにより、アクティブなDeliverable agreementが「孤児化」（Superseded化
された上で、`_find_active_deliverable_agreement`が二度と発見できない識別子で置き換わる）
していた：

1. **entry_typeドリフト**: `log/2026-08-11/0016`のtask_2_3で、Userの却下発言が
   `entry_type='Decision'`として抽出されたが、supersede対象を探すループが
   `topic`一致だけを条件にしており`entry_type`を見ていなかったため、同一topicの
   Deliverable行までSuperseded化してしまった。
2. **phase_idドリフト**: `log/2026-08-10/1905`のtask_1_4・`log/2026-08-10/2100`の
   task_2_2で、LLMが`"phase_id": ""`（空文字）を返した際、`item.get("phase_id", default)`
   がキー欠落時にしかdefaultを使わないため空文字がそのまま採用され（`_commit_agreement_from_tool`
   側でBL-161が既に修正した同型のバグ）、`_find_active_deliverable_agreement`の
   phase_id完全一致条件に一致しなくなった。

孤児化すると`_find_active_deliverable_agreement`が`None`を返し、`old_content=""`→
`base_content=""`となって、以降の`write_agreement(edits=...)`が全て「old_textが
現在のホワイトボード内容に見つかりませんでした（緩い一致0件）」で失敗し続ける
（エラーメッセージに添える近傍スニペットも常に空文字になる）。

対応：
1. supersede対象を探すループへ`entry_type`一致条件を追加。
2. `decision_extractor_node`のphase_id導出を`item.get("phase_id", default)`から
   `item.get("phase_id") or default`（`task_id`と同型）へ修正。
3. 防御として`_find_active_deliverable_agreement`をBL-131/`get_latest_whiteboard`と
   同じ設計（task_id単独で検索し、phase_id不一致は警告のみ）へ変更。

参照: docs/design/back_log/issue_backlog.md BL-206。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl206.db")
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
    return [{"phase_id": "phase_2", "tasks": [{"task_id": "task_2_3"}]}]


def _base_state(run_id, phases, chat_content):
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": phases[0],
        "current_task_id": "task_2_3",
        "chat_history": [{"role": "user", "content": chat_content}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False,
        "user_wrote_agreement": False,
    }


def _create_deliverable(conn, run_id, topic="task_2_3 路線候補の需要・SLA適合性評価"):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": topic,
            "decision_what": "唯一無二の識別可能な原文断片。" + "X" * 300,
            "reason_why": "初版", "entry_type": "Deliverable",
            "phase_id": "phase_2", "task_id": "task_2_3",
        },
        {"run_id": run_id, "current_task_id": "task_2_3", "phases": _phases()},
    )
    assert result["success"] is True, result.get("error")
    return topic


def _mock_extractor(item):
    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return ([item], {"advances_to_phase_id": None, "advances_to_task_id": None})
    return _fake


# ---------------------------------------------------------------------------
# 1. entry_typeドリフト: Decision抽出がDeliverableを孤児化させないこと
# ---------------------------------------------------------------------------

def test_decision_extraction_does_not_supersede_deliverable_with_same_topic(db_conn, monkeypatch):
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)
    phases = _phases()
    state = _base_state(run_id, phases, "task_2_3を承認しません。")

    # [BL-206] Userの却下がentry_type='Decision'として抽出される（実際に観測されたパターン）。
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Decision", "status": "Rejected",
        "target_topic": topic, "content": "受入基準未充足のため却下", "rationale": "路線比較が不足",
        "proposed_by": "User", "phase_id": "phase_2", "task_id": "task_2_3",
    }))

    cela_main.decision_extractor_node(state)

    target = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_2", "task_2_3")
    assert target is not None, "Decision抽出によってDeliverableが孤児化した（BL-206再発）"
    assert target["status"] != "Superseded"
    assert target["decision_what"].startswith("WHITEBOARD:")


def test_decision_extraction_still_supersedes_matching_decision_topic(db_conn, monkeypatch):
    """[非退行確認] entry_type一致条件の追加で、Decision同士の正当なsupersedeまで
    止めていないことを確認する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    first = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_2_3 却下判定",
            "decision_what": "初回の却下理由", "reason_why": "r", "entry_type": "Decision",
            "phase_id": "phase_2", "task_id": "task_2_3",
        },
        {"run_id": run_id, "current_task_id": "task_2_3"},
    )
    assert first["success"] is True

    phases = _phases()
    state = _base_state(run_id, phases, "改めて却下します。")
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Decision", "status": "Rejected",
        "target_topic": "task_2_3 却下判定", "content": "更新後の却下理由", "rationale": "r2",
        "proposed_by": "User", "phase_id": "phase_2", "task_id": "task_2_3",
    }))

    cela_main.decision_extractor_node(state)

    rows = [a for a in cela_main.get_agreements_from_db(conn, run_id) if a["topic"] == "task_2_3 却下判定"]
    superseded = [a for a in rows if a["status"] == "Superseded"]
    active = [a for a in rows if a["status"] != "Superseded"]
    assert len(superseded) == 1
    assert len(active) == 1
    assert active[0]["decision_what"] == "更新後の却下理由"


# ---------------------------------------------------------------------------
# 2. phase_idドリフト: 空文字のphase_idでもフォールバックが効くこと
# ---------------------------------------------------------------------------

def test_empty_string_phase_id_falls_back_to_current_phase(db_conn, monkeypatch):
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)
    phases = _phases()
    state = _base_state(run_id, phases, "task_2_3の成果物を修正します。")

    # [BL-206] LLMがキーを省略せず"phase_id": ""を明示的に返すケース（実観測パターン）。
    monkeypatch.setattr(cela_main, "call_decision_extractor", _mock_extractor({
        "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
        "target_topic": topic, "content": "短い更新コメント", "rationale": "微修正",
        "proposed_by": "Agent", "phase_id": "", "task_id": "task_2_3",
    }))

    cela_main.decision_extractor_node(state)

    target = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_2", "task_2_3")
    assert target is not None, "空文字phase_idがフォールバックせず孤児化した（BL-206再発）"
    assert target["phase_id"] == "phase_2"


# ---------------------------------------------------------------------------
# 3. _find_active_deliverable_agreementのフェイルセーフ化（BL-131/get_latest_whiteboardと同型）
# ---------------------------------------------------------------------------

def test_find_active_deliverable_agreement_ignores_phase_id_mismatch(db_conn, capsys):
    """[BL-206] phase_idが完全一致しなくても、task_idが一致しSupersededでなければ
    発見できること（get_latest_whiteboardと同じ設計）。不一致時は警告のみ出す。"""
    conn, run_id = db_conn
    _create_deliverable(conn, run_id)

    found_correct = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_2", "task_2_3")
    assert found_correct is not None

    found_mismatched = cela_main._find_active_deliverable_agreement(conn, run_id, "phase_9", "task_2_3")
    assert found_mismatched is not None
    assert found_mismatched["id"] == found_correct["id"]
    assert "phase_id不一致" in capsys.readouterr().out

    found_empty = cela_main._find_active_deliverable_agreement(conn, run_id, "", "task_2_3")
    assert found_empty is not None
    assert found_empty["id"] == found_correct["id"]


def test_find_active_deliverable_agreement_still_none_for_unknown_task(db_conn):
    """[非退行確認] task_id自体が存在しなければ引き続きNoneを返すこと。"""
    conn, run_id = db_conn
    _create_deliverable(conn, run_id)
    assert cela_main._find_active_deliverable_agreement(conn, run_id, "phase_2", "task_9_9") is None


def test_find_active_deliverable_agreement_still_none_for_superseded_only(db_conn):
    """[非退行確認] 該当task_idのDeliverableが全てSupersededなら引き続きNoneを返すこと。"""
    conn, run_id = db_conn
    _create_deliverable(conn, run_id)
    for a in cela_main.get_agreements_from_db(conn, run_id):
        if a["task_id"] == "task_2_3":
            cela_main.db_supersede_agreement(a["id"], conn, run_id)

    assert cela_main._find_active_deliverable_agreement(conn, run_id, "phase_2", "task_2_3") is None
