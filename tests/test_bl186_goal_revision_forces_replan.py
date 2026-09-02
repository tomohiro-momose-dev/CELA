"""
BL-186: ゴール改定（`revise_goal`、BL-086）成功時、既存のBL-163/BL-168が承認済み過去タスクへ
severity="minor"のissueを起票し、verified_factsへ警告を付記するところまでは実装済みだった。
しかしminor issueはBL-136/BL-145の強制解決ルート（major/escalated専用）に乗らず、
read_issuesもpull型ツールのためどのプロンプトにも自動注入されない。実ドライラン
（log/2026-08-06/1432）で、ゴール改定によりphase1-5の過去タスク13件が整合性未確認のまま
flagされたが、ランが既にphase6/task_6_1（計画上の最終タスク）にあり通常のタスク遷移では
phase1-5へ戻る経路が無いため、この13件が誰にも参照されないまま放置されるリスクをユーザーへ
報告した。

ユーザーと相談の結果、「タスク遷移で過去タスクへ戻る新ルート」ではなく、「ゴール改定時に
BL-145（滞留escalated issueをplan_revision_reason経由でtask_plannerへ強制引き継ぐ既存の
仕組み）と同型の配線で、task_plannerを強制的に再発火させ、新規フェーズ（phase7以降）として
過去タスクの再検証タスクを追記させる」方式を採用した（ユーザー承認: 「お願いします」）。

`_revise_goal_tool_impl`がBL-163の`_flagged`（影響を受けた過去タスク一覧）と起票した
issue_idを再利用し、`plan_revision_reason`/`plan_revision_issue_ids`を戻り値に含める。
`generate_user_utterance_node`が`_LAST_GOAL_REVISION`ブリッジ経由でこれを受け取り、
`state["plan_revision_reason"]`へ反映する（BL-145と同じ、他要因が既にセット済みなら
上書きしないガード付き）。`task_planner_node`/`call_task_planner`自体は無改修（既存の
revision_reason消費ロジックをそのまま再利用）。

参照: docs/design/back_log/issue_backlog.md BL-186、docs/design/decision_log.md D-155（予定）。
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
    db_path = str(tmp_path / "test_bl186.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_GOAL_TEXT = ""
        cela_main._LAST_GOAL_REVISION = None


def _insert_agreement_row(conn, run_id: str, seq: int, phase_id: str, task_id: str, topic: str,
                           status: str, entry_type: str = "Deliverable"):
    """[テスト専用] agreements行を直接INSERTする（test_bl163と同じ決定論的ID付与パターン）。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", status, topic, "X" * 300, "r", "expert", entry_type, phase_id, task_id,
         "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()
    return agreement_id


def _revise_goal(run_id: str, old_goal: str, new_text_pair: tuple[str, str]):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "予算と要件の構造的矛盾",
        "implicated_constraint": "台数上限",
        "why_conflicts_with_true_need": "要件を満たすには台数が不足",
        "suggested_reframe": "フェーズ分割方式へ変更",
    })["escalation_id"]

    # [BL-236] revise_goalは人間のHIL承認（--answer-human-input相当）を必須とするため、
    # このテストヘルパーでも承認済み状態を再現する。
    cela_main.upsert_verified_fact(
        cela_main.get_active_conn(), run_id,
        cela_main._goal_escalation_hil_variable(escalation_id),
        "approved", "", "", "", "human_operator", confidence="confirmed",
    )

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = old_goal
    return cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": new_text_pair[0], "new_text": new_text_pair[1]}],
        "reason_why": "構造的矛盾の解消のため",
    })


# ---------------------------------------------------------------------------
# _revise_goal_tool_impl（TOOL_DISPATCH["revise_goal"]）の戻り値
# ---------------------------------------------------------------------------

def test_revise_goal_returns_plan_revision_reason_when_past_tasks_flagged(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 2, "phase_2", "task_2_1", "task_2_1の成果物", "Approved_with_Conditions")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    reason = result.get("plan_revision_reason", "")
    assert reason
    assert result["escalation_id"] in reason
    assert "phase7以降" in reason
    assert "task_1_1" in reason
    assert "task_2_1" in reason
    assert "既存フェーズの内容は書き換えないで" in reason


def test_revise_goal_plan_revision_issue_ids_match_created_issues(db_conn):
    conn, run_id = db_conn
    _insert_agreement_row(conn, run_id, 1, "phase_1", "task_1_1", "task_1_1の成果物", "Approved")
    _insert_agreement_row(conn, run_id, 2, "phase_2", "task_2_1", "task_2_1の成果物", "Approved")

    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True

    issue_ids = result.get("plan_revision_issue_ids", [])
    assert len(issue_ids) == 2

    rows = conn.execute(
        "SELECT id, topic, status FROM issue_log WHERE run_id=? AND topic LIKE 'goal_revision_consistency_check_%'",
        (run_id,),
    ).fetchall()
    db_ids = {r["id"] for r in rows}
    assert set(issue_ids) == db_ids
    assert all(r["status"] == "open" for r in rows)


def test_revise_goal_with_zero_flagged_tasks_returns_empty_plan_revision_fields(db_conn):
    conn, run_id = db_conn
    result = _revise_goal(run_id, "台数上限は2台とする。", ("台数上限は2台とする。", "フェーズ分割方式とする。"))
    assert result["success"] is True
    assert result.get("plan_revision_reason", "") == ""
    assert result.get("plan_revision_issue_ids", []) == []


# ---------------------------------------------------------------------------
# generate_user_utterance_node: _LAST_GOAL_REVISIONブリッジ経由でstateへの反映
# ---------------------------------------------------------------------------

def _minimal_node_state(run_id: str, **overrides) -> dict:
    state = {
        "run_id": run_id,
        "goal": "テストゴール文",
        "round_count": 1,
        "chat_history": [],
        "constraint_issue": "none",
        "user_retry_count": 0,
        "plan_revision_reason": "",
        "plan_revision_issue_ids": [],
    }
    state.update(overrides)
    return state


def test_generate_user_utterance_node_sets_plan_revision_reason_from_goal_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "テスト発言")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    cela_main._LAST_GOAL_REVISION = {
        "new_goal_text": "新ゴール文",
        "old_goal_text": "旧ゴール文",
        "escalation_id": "ESC-TEST-1",
        "plan_revision_reason": "[BL-186] 過去タスクを再検証してください: task_1_1",
        "plan_revision_issue_ids": ["issue-a", "issue-b"],
    }

    state = _minimal_node_state(run_id)
    result_state = cela_main.generate_user_utterance_node(state)

    assert result_state["plan_revision_reason"] == "[BL-186] 過去タスクを再検証してください: task_1_1"
    assert result_state["plan_revision_issue_ids"] == ["issue-a", "issue-b"]
    assert result_state["goal"] == "新ゴール文"


def test_generate_user_utterance_node_does_not_overwrite_existing_plan_revision_reason(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "テスト発言")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)

    cela_main._LAST_GOAL_REVISION = {
        "new_goal_text": "新ゴール文",
        "old_goal_text": "旧ゴール文",
        "escalation_id": "ESC-TEST-1",
        "plan_revision_reason": "[BL-186] 過去タスクを再検証してください: task_1_1",
        "plan_revision_issue_ids": ["issue-a"],
    }

    state = _minimal_node_state(
        run_id,
        plan_revision_reason="task_plan_reviewerによる差し戻し",
        plan_revision_issue_ids=[],
    )
    result_state = cela_main.generate_user_utterance_node(state)

    assert result_state["plan_revision_reason"] == "task_plan_reviewerによる差し戻し"
    assert result_state["plan_revision_issue_ids"] == []


def test_generate_user_utterance_node_no_plan_revision_reason_without_goal_revision(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "generate_user_utterance", lambda state, config: "テスト発言")
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    cela_main._LAST_GOAL_REVISION = None

    state = _minimal_node_state(run_id)
    result_state = cela_main.generate_user_utterance_node(state)

    assert result_state["plan_revision_reason"] == ""
    assert result_state["plan_revision_issue_ids"] == []
