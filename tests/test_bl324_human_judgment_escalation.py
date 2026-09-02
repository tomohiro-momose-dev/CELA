"""
BL-324: 「真に人間の判断が必要」なissueを、Reflector監査を経て（または監査役自身の判断で）
グラフ全体の一時停止へ接続する。

背景: 現在HILで一時停止中のライブラン（run_id=1787890406-1e73a89d）で、User AIが
escalate_premise_concernにより「human-only issue（human_research_prompt付き）が
RESOLVE/DEFER（BL-236の保護、human-onlyは拒否）/ACKNOWLEDGE（BL-194、上限2回で枯渇）
のいずれでも解消できず、BL-158の機械的差し戻しが無限に繰り返される」というプロセス上の
矛盾を提起した。

ユーザーとの往復で以下の設計に確定した:
- flag_needs_human_input（従来expert専用）をuser/detector/reflector/facilitatorへ拡大。
- user/expert/detector起票時は即座には一時停止せず、issue_log.human_judgment_status=
  'pending_reflector_review'として記録され、次回reflection_node巡回でReflectorが監査する。
  confirmと判定されればグラフ全体を一時停止、insufficientと判定されればReflectorの根拠付きで
  即座にstatus='resolved'とする。
- reflector/facilitator自身が起票した場合は、既に監査・調停の役割を担っているため
  human_judgment_status='confirmed'で直接起票され、追加監査を挟まず即座に一時停止する。
- Facilitatorの既存「facilitation_count > 5 → halt（不可逆停止）」は、この新しい
  一時停止（人間回答後--resumeで復帰可能）へ置き換える。

独立レビュー（Cline CLI、AGENTS.md §19）で以下2点の欠落を指摘され、実コード確認の上で
設計に反映した:
- resumeガードがissue_log系の新経路に対応していなかった（未回答でも素通り/永久にresume
  不可のいずれかになる欠陥）→ issue_log.status=='resolved'を権威ストアとして確認してから
  resumeを許可するガードを追加。
- facilitation_countがresume時にリセットされない → halt（不可逆）を一時停止（可逆）へ
  変更すると、resume直後に即座に再一時停止する無限ループになる → facilitator起票の一時停止
  解除時のみリセットする。

副次的に発見したBL-158の不整合（`_get_blocking_issues_for_transition`呼び出しが
`exclude_acknowledged`を渡しておらずdocstringの意図と実装が乖離）も同時に修正した。

参照: docs/design/back_log/BL-324/BL324_basic_design.md、issue_backlog.md BL-324。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl324.db")
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


PHASES_1 = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}]


# ===========================================================================
# 1. マイグレーション
# ===========================================================================

def test_migration_adds_human_judgment_status_column_idempotently(db_conn):
    conn, run_id = db_conn
    cela_main.init_db(conn)  # 2回目
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    assert "human_judgment_status" in cols


# ===========================================================================
# 2. _flag_needs_human_input_tool_impl: role拡大とhuman_judgment_status分岐
# ===========================================================================

@pytest.mark.parametrize("caller_role", ["expert", "user", "detector", "reflector", "facilitator"])
def test_flag_needs_human_input_allows_all_five_roles(db_conn, caller_role):
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        {
            "topic": f"topic_{caller_role}", "variable_name": "v1",
            "human_research_prompt": "確認事項", "description": "AIには不可能な理由",
        },
        conn, run_id, caller_role, "phase_1", "task_1_1",
    )
    assert result["success"] is True, result


def test_flag_needs_human_input_rejects_disallowed_role(db_conn):
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        {
            "topic": "topic_x", "variable_name": "v1",
            "human_research_prompt": "確認事項", "description": "理由",
        },
        conn, run_id, "facilitator_impersonator", "phase_1", "task_1_1",
    )
    assert result["success"] is False
    assert "flag_needs_human_input" in result["error"]


@pytest.mark.parametrize("caller_role,expected_status", [
    ("expert", "pending_reflector_review"),
    ("user", "pending_reflector_review"),
    ("detector", "pending_reflector_review"),
    ("reflector", "confirmed"),
    ("facilitator", "confirmed"),
])
def test_flag_needs_human_input_status_by_role(db_conn, caller_role, expected_status):
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        {
            "topic": f"topic_status_{caller_role}", "variable_name": "v1",
            "human_research_prompt": "確認事項", "description": "理由",
        },
        conn, run_id, caller_role, "phase_1", "task_1_1",
    )
    assert result["human_judgment_status"] == expected_status
    row = conn.execute(
        "SELECT human_judgment_status FROM issue_log WHERE id=?", (result["id"],)
    ).fetchone()
    assert row["human_judgment_status"] == expected_status


# ===========================================================================
# 3. _should_pause_for_human / pause_for_human_node
# ===========================================================================

def test_should_pause_for_human_true_for_human_judgment_issue():
    assert cela_main._should_pause_for_human({"pending_human_judgment_issue_id": "issue-1"}) is True


def test_should_pause_for_human_false_when_both_absent():
    assert cela_main._should_pause_for_human({}) is False


def test_should_pause_for_human_true_when_either_set():
    assert cela_main._should_pause_for_human(
        {"paused_for_premise_escalation": False, "pending_human_judgment_issue_id": "issue-1"}
    ) is True


def test_pause_for_human_node_reports_human_judgment_issue(db_conn, capsys):
    conn, run_id = db_conn
    flag_result = cela_main._flag_needs_human_input_tool_impl(
        {
            "topic": "power_contract", "variable_name": "existing_contract_capacity_kw",
            "human_research_prompt": "電力会社へ照会してください", "description": "AIには照会不能",
        },
        conn, run_id, "facilitator", "phase_1", "task_1_1",
    )
    state = {"run_id": run_id, "turn_count": 3, "pending_human_judgment_issue_id": flag_result["id"]}
    result = cela_main.pause_for_human_node(state)
    assert result is state
    out = capsys.readouterr().out
    assert "power_contract" in out
    assert "電力会社へ照会してください" in out
    row = conn.execute(
        "SELECT who, what FROM decisions WHERE run_id=? ORDER BY rowid DESC LIMIT 1", (run_id,)
    ).fetchone()
    assert row["who"] == "system"


def test_pause_for_human_node_prefers_premise_escalation_report(db_conn):
    """両方（設計上排他だが念のため）設定されていても、premise_escalation側の報告を優先する。"""
    conn, run_id = db_conn
    state = {
        "run_id": run_id, "turn_count": 1,
        "pending_premise_escalation_id": "ESC-nonexistent",
        "pending_human_judgment_issue_id": "issue-nonexistent",
    }
    result = cela_main.pause_for_human_node(state)
    assert result is state  # クラッシュしないことの確認


# ===========================================================================
# 4. Facilitatorのブリッジ配線とhalt→一時停止への変更
# ===========================================================================

def test_facilitator_node_source_references_human_judgment_bridge():
    src = inspect.getsource(cela_main.facilitator_node)
    assert "get_last_human_judgment_flag" in src
    assert "pending_human_judgment_issue_id" in src


def test_facilitator_node_sets_pending_issue_on_confirmed_flag(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: None)
    monkeypatch.setattr(cela_main, "get_last_human_judgment_flag", lambda: {
        "issue_id": "issue-facilitator-1", "caller_role": "facilitator", "human_judgment_status": "confirmed",
    })
    state = {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール", "run_id": run_id, "last_reflection_note": "",
        "essence_dialogue_active": False, "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5, "essence_dialogue_topic": "",
        "last_essence_proposal": None,
    }
    result = cela_main.facilitator_node(state)
    assert result["pending_human_judgment_issue_id"] == "issue-facilitator-1"


def test_facilitator_node_ignores_pending_reflector_review_flag(db_conn, monkeypatch):
    """user/expert/detector起票（pending_reflector_review）はfacilitator_nodeでは
    一時停止トリガーにならないこと（Reflectorの監査を経るまで一時停止しない設計）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")
    monkeypatch.setattr(cela_main, "get_last_premise_escalation", lambda: None)
    monkeypatch.setattr(cela_main, "get_last_human_judgment_flag", lambda: {
        "issue_id": "issue-expert-1", "caller_role": "expert", "human_judgment_status": "pending_reflector_review",
    })
    state = {
        "facilitation_count": 0,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール", "run_id": run_id, "last_reflection_note": "",
        "essence_dialogue_active": False, "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5, "essence_dialogue_topic": "",
        "last_essence_proposal": None,
    }
    result = cela_main.facilitator_node(state)
    assert result.get("pending_human_judgment_issue_id", "") == ""


def test_facilitation_count_exceeded_pauses_instead_of_halting(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")
    state = {
        "facilitation_count": 5,  # インクリメントされて6になり上限(5)超過
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール", "run_id": run_id, "last_reflection_note": "",
        "essence_dialogue_active": False, "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5, "essence_dialogue_topic": "",
        "last_essence_proposal": None, "current_phase": {"phase_id": "phase_1"},
        "current_task_id": "task_1_1",
    }
    result = cela_main.facilitator_node(state)
    assert result.get("halt", False) is False, "halt=Trueが立ってはいけない（BL-324でpauseへ置き換え）"
    assert result.get("pending_human_judgment_issue_id"), "一時停止issue_idが設定されていない"
    row = conn.execute(
        "SELECT human_judgment_status, raised_by, status FROM issue_log WHERE id=?",
        (result["pending_human_judgment_issue_id"],)
    ).fetchone()
    assert row["human_judgment_status"] == "confirmed"
    assert row["raised_by"] == "facilitator"
    assert row["status"] == "escalated"


def test_facilitation_count_exceeded_falls_back_to_halt_when_flag_creation_fails(db_conn, monkeypatch):
    """[実装後レビュー(Cline)指摘/AGENTS.md §13.2] issue起票自体が失敗した場合、旧コード
    （無条件halt）と同じ「確実に止める」安全側へフォールバックすること。理由の分からない
    無限ループ（pendingもhaltも立たずreturnし続ける）を防ぐ。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_facilitator", lambda goal, chat_history, reflection_note="", **kwargs: "続けます")
    # facilitator_nodeが生成する予定のtopicと同じtopicで、未解決issueを先に作っておくことで
    # _flag_needs_human_input_tool_impl内の重複チェックにより起票を失敗させる。
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
        "human_variable_name, human_judgment_status, created_at, updated_at) "
        "VALUES (?, ?, ?, 'facilitator', 'phase_1', 'task_1_1', 'major', 'escalated', "
        "'既存', 1, 'task_1_1', '', '', '', '', ?, ?)",
        (str(uuid.uuid4()), run_id, f"facilitation_stalemate_{run_id}_0", time.time(), time.time())
    )
    conn.commit()
    state = {
        "facilitation_count": 5,
        "chat_history": [{"role": "assistant", "content": "直近の発言"}],
        "goal": "テストゴール", "run_id": run_id, "last_reflection_note": "",
        "essence_dialogue_active": False, "essence_dialogue_round": 0,
        "essence_dialogue_max_rounds": 5, "essence_dialogue_topic": "",
        "last_essence_proposal": None, "current_phase": {"phase_id": "phase_1"},
        "current_task_id": "task_1_1", "round_count": 0,
    }
    result = cela_main.facilitator_node(state)
    assert result.get("halt") is True, "issue起票失敗時はhalt=Trueへフォールバックすべき"
    assert result.get("pending_human_judgment_issue_id", "") == ""


# ===========================================================================
# 4b. resumeガード: 複数confirmed行の消費（実装後レビュー(Cline)指摘）
# ===========================================================================

def test_resume_chains_to_next_confirmed_issue_when_multiple_pending(tmp_path, monkeypatch):
    """[実装後レビュー(Cline)指摘/AGENTS.md §15.4] Reflectorが1回の監査で複数件をconfirmし、
    stateには最初の1件しか載らない場合でも、resumeガードが「他に未解決のconfirmed行が
    残っていないか」を確認し、あれば一時停止を継続すること（取り残しの防止）。"""
    db_path = str(tmp_path / "cela.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = "run-multiple-confirmed"
    tracked_id = str(uuid.uuid4())
    other_id = str(uuid.uuid4())
    for _id, _topic, _status in ((tracked_id, "topic_a", "resolved"), (other_id, "topic_b", "escalated")):
        conn.execute(
            "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
            "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
            "human_variable_name, human_judgment_status, created_at, updated_at) "
            "VALUES (?, ?, ?, 'reflector', 'phase_1', 'task_1_1', 'major', ?, "
            "'desc', 1, 'task_1_1', '', 'prompt', 'var', 'confirmed', ?, ?)",
            (_id, run_id, _topic, _status, time.time(), time.time())
        )
    conn.commit()
    conn.close()

    stale_state = {
        "db_path": db_path, "turn_count": 5, "max_turns": 30, "halt": False,
        "discussion_status": "continuing",
        "pending_human_judgment_issue_id": tracked_id,
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id=run_id,
    )

    assert fake_graph.stream_calls == [], "他にconfirmed行が残っているのにresumeが通ってしまった"


def test_resume_proceeds_when_no_other_confirmed_issues_remain(tmp_path, monkeypatch):
    """[非退行] 追跡中のissueだけが存在し、他に残っていない場合は通常通りresumeが通ること。"""
    db_path = str(tmp_path / "cela.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = "run-single-confirmed"
    tracked_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
        "human_variable_name, human_judgment_status, created_at, updated_at) "
        "VALUES (?, ?, 'topic_only', 'reflector', 'phase_1', 'task_1_1', 'major', 'resolved', "
        "'desc', 1, 'task_1_1', '', 'prompt', 'var', 'confirmed', ?, ?)",
        (tracked_id, run_id, time.time(), time.time())
    )
    conn.commit()
    conn.close()

    stale_state = {
        "db_path": db_path, "turn_count": 5, "max_turns": 30, "halt": False,
        "discussion_status": "continuing",
        "pending_human_judgment_issue_id": tracked_id,
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id=run_id,
    )

    assert fake_graph.stream_calls != [], "他に残っているconfirmed行が無いのにresumeが拒否された"


# ===========================================================================
# 5. Reflectorの監査（reflection_node/call_reflectionの拡張）
# ===========================================================================

def _seed_pending_review_issue(conn, run_id, topic="pending_topic", task_id="task_1_1"):
    result = cela_main._flag_needs_human_input_tool_impl(
        {
            "topic": topic, "variable_name": "v1",
            "human_research_prompt": "確認事項", "description": "理由",
        },
        conn, run_id, "expert", "phase_1", task_id,
    )
    assert result["success"] is True
    return result["id"]


def _base_reflection_state(run_id):
    return {
        "run_id": run_id, "goal": "テストゴール", "risk_register": [],
        "constraint_issue_log": [], "chat_history": [], "round_count": 1,
        "current_task_id": "task_1_1", "current_phase": {"phase_id": "phase_1"},
        "task_criteria_status": {}, "facilitation_count": 0,
    }


def test_reflection_node_confirms_pending_issue(db_conn, monkeypatch):
    conn, run_id = db_conn
    issue_id = _seed_pending_review_issue(conn, run_id, "power_contract")
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
        "human_judgment_reviews": [
            {"issue_id": issue_id, "decision": "confirm", "reasoning": "合理的仮定値は危険"},
        ],
        "new_human_judgment_escalation": None,
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = _base_reflection_state(run_id)
    result = cela_main.reflection_node(state)
    assert result["pending_human_judgment_issue_id"] == issue_id
    row = conn.execute("SELECT human_judgment_status FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["human_judgment_status"] == "confirmed"


def test_reflection_node_resolves_insufficient_issue(db_conn, monkeypatch):
    conn, run_id = db_conn
    issue_id = _seed_pending_review_issue(conn, run_id, "minor_concern")
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
        "human_judgment_reviews": [
            {"issue_id": issue_id, "decision": "insufficient", "reasoning": "既存データで十分代替可能"},
        ],
        "new_human_judgment_escalation": None,
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = _base_reflection_state(run_id)
    result = cela_main.reflection_node(state)
    assert result.get("pending_human_judgment_issue_id", "") == ""
    row = conn.execute(
        "SELECT human_judgment_status, status, resolved_by, resolution_note FROM issue_log WHERE id=?", (issue_id,)
    ).fetchone()
    assert row["human_judgment_status"] == "reviewed_insufficient"
    assert row["status"] == "resolved"
    assert row["resolved_by"] == "reflector"
    assert "既存データで十分代替可能" in row["resolution_note"]


def test_reflection_node_ignores_review_for_already_confirmed_issue(db_conn, monkeypatch):
    """[AGENTS.md §13.4] pending_reflector_review以外の行への誤指定は無視すること
    （既にconfirmed済みの行を、古い/誤ったreviewで再度書き換えない）。"""
    conn, run_id = db_conn
    result = cela_main._flag_needs_human_input_tool_impl(
        {"topic": "already_confirmed", "variable_name": "v1",
         "human_research_prompt": "確認事項", "description": "理由"},
        conn, run_id, "facilitator", "phase_1", "task_1_1",
    )
    issue_id = result["id"]
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
        "human_judgment_reviews": [
            {"issue_id": issue_id, "decision": "insufficient", "reasoning": "誤指定"},
        ],
        "new_human_judgment_escalation": None,
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = _base_reflection_state(run_id)
    cela_main.reflection_node(state)
    row = conn.execute("SELECT human_judgment_status FROM issue_log WHERE id=?", (issue_id,)).fetchone()
    assert row["human_judgment_status"] == "confirmed", "confirmed済みの行がinsufficientで上書きされてしまった"


def test_reflection_node_creates_new_escalation(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
        "human_judgment_reviews": [],
        "new_human_judgment_escalation": {
            "topic": "reflector_new_concern", "variable_name": "reflector_var",
            "human_research_prompt": "根本的な前提の食い違いを人間が判断してください",
            "description": "指摘を重ねても議論が改善しない",
        },
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = _base_reflection_state(run_id)
    result = cela_main.reflection_node(state)
    assert result.get("pending_human_judgment_issue_id"), "Reflector自身の新規起票が一時停止をトリガーしていない"
    row = conn.execute(
        "SELECT human_judgment_status, raised_by, topic FROM issue_log WHERE id=?",
        (result["pending_human_judgment_issue_id"],)
    ).fetchone()
    assert row["human_judgment_status"] == "confirmed"
    assert row["raised_by"] == "reflector"
    assert row["topic"] == "reflector_new_concern"


def test_reflection_node_no_pending_issues_is_noop(db_conn, monkeypatch):
    """[非退行] pending issueが無い通常ターンでクラッシュ・誤発火しないこと。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
        "human_judgment_reviews": [], "new_human_judgment_escalation": None,
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    state = _base_reflection_state(run_id)
    result = cela_main.reflection_node(state)
    assert result.get("pending_human_judgment_issue_id", "") == ""


def test_call_reflection_prompt_includes_pending_issues(db_conn, monkeypatch):
    conn, run_id = db_conn
    issue_id = _seed_pending_review_issue(conn, run_id, "prompt_visibility_check")
    cela_main._DB_CONN = conn
    monkeypatch.setattr(cela_main, "get_active_conn", lambda: conn)
    monkeypatch.setattr(cela_main, "get_decisions_from_db", lambda c, r: [])
    monkeypatch.setattr(cela_main, "get_agreements_from_db", lambda c, r: [])
    monkeypatch.setattr(cela_main, "_get_goal_essence_text", lambda c, r: "")
    monkeypatch.setattr(cela_main, "_build_task_focus_state_text", lambda s: "")
    monkeypatch.setattr(cela_main, "_build_current_task_scope_brief", lambda s: "")
    monkeypatch.setattr(cela_main, "_build_decision_lineage_directive", lambda x: "")
    monkeypatch.setattr(cela_main, "_get_escalated_issues", lambda c, r: [])
    monkeypatch.setattr(cela_main, "_is_issue_effectively_deferred", lambda *a, **k: False)
    monkeypatch.setattr(cela_main, "_is_issue_acknowledged_active", lambda *a, **k: False)

    captured = {}

    def _fake_query_and_parse_with_retry(prompt, **kwargs):
        captured["prompt"] = prompt
        return {"still_aligned": True, "discussion_status": "continuing", "note": ""}, False

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake_query_and_parse_with_retry)
    monkeypatch.setattr(cela_main, "_enforce_decision_lineage_json", lambda *a, **k: a[1])

    state = {
        "run_id": run_id, "goal": "テストゴール", "risk_register": [],
        "constraint_issue_log": [], "chat_history": [], "round_count": 1,
        "current_task_id": "task_1_1", "current_phase": {"phase_id": "phase_1"},
    }
    cela_main.call_reflection(state, {})
    assert "prompt_visibility_check" in captured["prompt"]
    assert issue_id in captured["prompt"]


# ===========================================================================
# 6. BL-158の副次修正: exclude_acknowledged=True
# ===========================================================================

def _seed_blocking_issue(conn, run_id, topic="bl158_blocking", task_id="task_1_1"):
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "1回目", "severity": "major"},
        conn, run_id, "detector", "phase_1", task_id,
    )
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": topic, "description": "2回目"},
        conn, run_id, "detector", "phase_1", task_id,
    )


def test_get_blocking_issues_excludes_acknowledged_when_flagged(db_conn):
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id, "ack_test_topic")
    cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": "ack_test_topic", "ack_reason": "対応中"},
        conn, run_id, "user", "phase_1", "task_1_1", state={"round_count": 0},
    )
    blocking_default = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert len(blocking_default) == 1, "既定(exclude_acknowledged=False)は非退行で従来通り含む"

    blocking_excluded = cela_main._get_blocking_issues_for_transition(
        conn, run_id, "task_1_1", exclude_acknowledged=True, round_count=0
    )
    assert blocking_excluded == [], "ACK猶予期間中はexclude_acknowledged=Trueで除外されるべき"


def test_bl158_detector_node_does_not_force_major_during_ack_window(db_conn, monkeypatch):
    """[実装ドキュメントの意図修正] BL-158の呼び出し箇所がexclude_acknowledged=Trueを
    渡すようになったため、ACK猶予期間中はdetector_nodeが機械的にmajorへ上書きしないこと。"""
    conn, run_id = db_conn
    _seed_blocking_issue(conn, run_id, "ack_window_topic")
    cela_main._write_issue_impl(
        {"action_type": "ACKNOWLEDGE", "topic": "ack_window_topic", "ack_reason": "対応中"},
        conn, run_id, "user", "phase_1", "task_1_1", state={"round_count": 0},
    )
    monkeypatch.setattr(cela_main, "call_detector", lambda state, target_role, review_mode="task_output": {
        "risk": "low", "constraint_issue": "none", "comment": "元の判定コメント", "observations": "",
    })
    state = {
        "chat_history": [{"role": "user", "content": "次のタスクへ進め"}],
        "expert_consultation_mode": False,
        "expert_last_python_calls": [{"code": "1+1", "result": "2"}],
        "constraint_issue_log": [], "turn_count": 1, "run_id": run_id,
        "current_task_id": "task_1_1", "user_wrote_issue_resolution": False,
        "round_count": 0,
    }
    result = cela_main.detector_node(state)
    assert result["constraint_issue"] == "none", "ACK猶予期間中なのに機械的にmajorへ上書きされた"


def test_bl158_call_site_passes_exclude_acknowledged():
    """ソース検査: BL-158呼び出し箇所がexclude_acknowledged=Trueを渡していること
    （docstringが元々意図していた挙動、AGENTS.md §15.3 実装とdocstringの一致）。"""
    src = inspect.getsource(cela_main.detector_node)
    idx = src.index("_get_blocking_issues_for_transition(")
    call_block = src[idx: idx + 300]
    assert "exclude_acknowledged=True" in call_block


# ===========================================================================
# 7. resumeガードの拡張 (run_ai_vs_ai_loop)
# ===========================================================================

class _FakeSnapshot:
    def __init__(self, values, next_nodes):
        self.values = values
        self.next = next_nodes


class _FakeCompiledGraph:
    def __init__(self, snapshot):
        self._snapshot = snapshot
        self.stream_calls = []

    def get_state(self, runtime_config):
        return self._snapshot

    def stream(self, *args, **kwargs):
        self.stream_calls.append(args)
        return iter(())


def test_resume_blocks_when_human_judgment_issue_unresolved(tmp_path, monkeypatch, capsys):
    db_path = str(tmp_path / "cela.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = "run-human-judgment-unanswered"
    issue_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
        "human_variable_name, human_judgment_status, created_at, updated_at) "
        "VALUES (?, ?, 'unanswered_topic', 'facilitator', 'phase_1', 'task_1_1', 'major', 'escalated', "
        "'desc', 1, 'task_1_1', '', 'prompt', 'var', 'confirmed', ?, ?)",
        (issue_id, run_id, time.time(), time.time())
    )
    conn.commit()
    conn.close()

    stale_state = {
        "db_path": db_path, "turn_count": 5, "halt": False,
        "pending_human_judgment_issue_id": issue_id,
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id=run_id,
    )

    assert fake_graph.stream_calls == []
    assert "回答待ち" in capsys.readouterr().out


def test_resume_proceeds_and_resets_facilitation_count_when_answered(tmp_path, monkeypatch):
    db_path = str(tmp_path / "cela.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = "run-human-judgment-answered"
    issue_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
        "human_variable_name, human_judgment_status, created_at, updated_at) "
        "VALUES (?, ?, 'answered_topic', 'facilitator', 'phase_1', 'task_1_1', 'major', 'resolved', "
        "'desc', 1, 'task_1_1', '', 'prompt', 'var', 'confirmed', ?, ?)",
        (issue_id, run_id, time.time(), time.time())
    )
    conn.commit()
    conn.close()

    stale_state = {
        "db_path": db_path, "turn_count": 5, "max_turns": 30, "halt": False,
        "discussion_status": "continuing",
        "pending_human_judgment_issue_id": issue_id,
        "facilitation_count": 6,
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id=run_id,
    )

    assert fake_graph.stream_calls != []
    passed_state = fake_graph.stream_calls[0][0]
    assert passed_state["pending_human_judgment_issue_id"] == ""
    assert passed_state["facilitation_count"] == 0, "facilitator起票の一時停止解除でfacilitation_countがリセットされていない"


def test_resume_does_not_reset_facilitation_count_for_non_facilitator_issue(tmp_path, monkeypatch):
    """他の起票元（例: reflector）由来の一時停止解除では、無関係なfacilitation_countに
    触れないこと。"""
    db_path = str(tmp_path / "cela.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = "run-human-judgment-reflector-answered"
    issue_id = str(uuid.uuid4())
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, human_research_prompt, "
        "human_variable_name, human_judgment_status, created_at, updated_at) "
        "VALUES (?, ?, 'reflector_topic', 'reflector', 'phase_1', 'task_1_1', 'major', 'resolved', "
        "'desc', 1, 'task_1_1', '', 'prompt', 'var', 'confirmed', ?, ?)",
        (issue_id, run_id, time.time(), time.time())
    )
    conn.commit()
    conn.close()

    stale_state = {
        "db_path": db_path, "turn_count": 5, "max_turns": 30, "halt": False,
        "discussion_status": "continuing",
        "pending_human_judgment_issue_id": issue_id,
        "facilitation_count": 2,
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id=run_id,
    )

    passed_state = fake_graph.stream_calls[0][0]
    assert passed_state["facilitation_count"] == 2, "reflector起票なのにfacilitation_countが触られた"


def test_resume_halt_still_wins_over_human_judgment_pause(tmp_path, monkeypatch, capsys):
    stale_state = {
        "db_path": str(tmp_path / "cela.db"),
        "turn_count": 5, "halt": True, "discussion_status": "halted",
        "pending_human_judgment_issue_id": "issue-both",
        "max_web_search_calls": 30, "max_web_fetch_calls": 30,
        "max_road_route_calls": 30, "goal_reference_dir": "",
    }
    fake_graph = _FakeCompiledGraph(_FakeSnapshot(values=stale_state, next_nodes=()))
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30,
                "reflection_interval": 3, "agent_has_guardrail": True},
        resume_run_id="run-halt-and-human-judgment-paused",
    )

    assert fake_graph.stream_calls == []
    assert "既にhalt済み" in capsys.readouterr().out
