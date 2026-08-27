"""
BL-283: think⇔write_agreement(Decision)の混同解消と、全ノード共通の機械的差し戻しゲート。

ユーザー依頼のログレビュー（`log/2026-08-26/2334`）のDB集計で、Expert/User AIが
write_agreement自体は多用する（Expert12回・User6回）のに`entry_type="Decision"`だけは
一度も選んでいないことが判明した。一方`think`の`decided`/`rejected`は頻繁に使われている。
これはBL-140で`scratch_concerns`と`write_issue`の間で一度経験した事故と同型の混同である。

対応は①プロンプト上の明文化（THINK_TOOL description）と②機械的な差し戻し（コード側が
無条件に検査し、不足があれば無条件に1回だけ差し戻す）の両方。AIが任意に呼ぶ「許可申請
ツール」方式は「AI依存」という同じ弱点を抱えるためユーザー指摘により不採用とした。
差し戻しは1回のみ、その後もなお不足していればissue_log（major）へ機械的に記録する。

参照: docs/design/back_log/issue_backlog.md BL-283。実LLM API呼び出しは伴わない
（query_AIはモンキーパッチする）。
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
    db_path = str(tmp_path / "test_bl283.db")
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


@pytest.fixture(autouse=True)
def _reset_think_and_agreement_globals():
    """[BL-283] 各テストの前後で_THINK_REASONING_LOG/_LAST_WRITE_AGREEMENT_ITEMSを
    クリーンな状態に戻す（他テストからの汚染防止）。"""
    cela_main._reset_think_scratchpad()
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []
    yield
    cela_main._reset_think_scratchpad()
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []


def _think_entry(decided="", rejected="", why="理由", rejected_why="却下理由"):
    return {"iter": 1, "action": "a", "summary": "s", "decided": decided, "why": why,
            "rejected": rejected, "rejected_why": rejected_why}


# ---------------------------------------------------------------------------
# 1. _pending_decision_candidates
# ---------------------------------------------------------------------------

def test_pending_candidates_empty_when_no_think_entries():
    cela_main._THINK_REASONING_LOG = []
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []
    assert cela_main._pending_decision_candidates() == []


def test_pending_candidates_requires_both_decided_and_rejected():
    cela_main._THINK_REASONING_LOG = [
        _think_entry(decided="X", rejected=""),  # rejectedが空なので対象外
        _think_entry(decided="", rejected="Y"),  # decidedが空なので対象外
    ]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []
    assert cela_main._pending_decision_candidates() == []


def test_pending_candidates_counts_against_decision_writes():
    cela_main._THINK_REASONING_LOG = [
        _think_entry(decided="A", rejected="A'"),
        _think_entry(decided="B", rejected="B'"),
    ]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = [{"entry_type": "Decision", "task_id": "t"}]
    pending = cela_main._pending_decision_candidates()
    assert len(pending) == 1
    assert pending[0]["decided"] == "B"


def test_pending_candidates_ignores_non_decision_entry_types():
    cela_main._THINK_REASONING_LOG = [_think_entry(decided="A", rejected="A'")]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = [{"entry_type": "Deliverable", "task_id": "t"}]
    pending = cela_main._pending_decision_candidates()
    assert len(pending) == 1


def test_pending_candidates_empty_when_writes_cover_all():
    cela_main._THINK_REASONING_LOG = [_think_entry(decided="A", rejected="A'")]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = [{"entry_type": "Decision", "task_id": "t"}]
    assert cela_main._pending_decision_candidates() == []


# ---------------------------------------------------------------------------
# 2. _record_decision_lineage_gap_issue
# ---------------------------------------------------------------------------

def test_record_decision_lineage_gap_issue_writes_major_escalated(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    state = {"run_id": run_id, "current_task_id": "task_1_1", "current_phase": {"phase_id": "phase_1"}}
    pending = [{"decided": "A", "why": "wa", "rejected": "A'", "rejected_why": "ra"}]
    cela_main._record_decision_lineage_gap_issue("Expert:test", pending, 0, state)
    row = conn.execute(
        "SELECT severity, status, raised_by, task_id FROM issue_log WHERE run_id=? AND topic LIKE 'decision_lineage_gap_%'",
        (run_id,)
    ).fetchone()
    assert row is not None
    assert row["severity"] == "major"
    assert row["status"] == "escalated"
    assert row["raised_by"] == "decision_lineage_gap_auto"
    assert row["task_id"] == "task_1_1"


def test_record_decision_lineage_gap_issue_noop_without_state():
    # stateがNoneの場合は例外を出さず何もしない（get_active_conn等を呼ばない）
    cela_main._record_decision_lineage_gap_issue("Expert:test", [{"decided": "A", "rejected": "B"}], 0, None)


def test_check_issue_permission_allows_only_create_for_decision_lineage_gap_auto():
    err = cela_main._check_issue_permission({"action_type": "CREATE"}, "decision_lineage_gap_auto")
    assert err is None
    err = cela_main._check_issue_permission({"action_type": "RESOLVE"}, "decision_lineage_gap_auto")
    assert err is not None


# ---------------------------------------------------------------------------
# 3. _enforce_decision_lineage_freetext / _enforce_decision_lineage_json
# ---------------------------------------------------------------------------

def _fake_query_AI_writing_decisions(n_decisions, answer="リトライ後の回答"):
    """リトライ呼び出し時にn_decisions件のDecisionをwrite_agreementしたかのように
    _LAST_WRITE_AGREEMENT_ITEMSへ反映するfake query_AI。"""
    def _fn(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        cela_main._LAST_WRITE_AGREEMENT_ITEMS = [
            {"entry_type": "Decision", "task_id": "t"} for _ in range(n_decisions)
        ]
        return answer
    return _fn


def test_enforce_freetext_returns_content_unchanged_when_no_pending(monkeypatch):
    cela_main._THINK_REASONING_LOG = []
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []

    def _fail_if_called(*a, **k):
        raise AssertionError("pendingが無い場合はquery_AIを再度呼んではならない")
    monkeypatch.setattr(cela_main, "query_AI", _fail_if_called)

    result = cela_main._enforce_decision_lineage_freetext(
        [{"role": "user", "content": "prompt"}], "元の回答",
        client=None, model="m", label="Expert:test", tools=[], state={"run_id": "r"},
    )
    assert result == "元の回答"


def test_enforce_freetext_retry_success_adopts_new_content(monkeypatch):
    cela_main._THINK_REASONING_LOG = [{"decided": "A", "why": "w", "rejected": "B", "rejected_why": "rw"}]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI_writing_decisions(1, "リトライ後の回答"))

    result = cela_main._enforce_decision_lineage_freetext(
        [{"role": "user", "content": "prompt"}], "元の回答",
        client=None, model="m", label="Expert:test", tools=[], state={"run_id": "r"},
    )
    assert result == "リトライ後の回答"


def test_enforce_freetext_retry_still_short_records_issue(monkeypatch, db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    cela_main._THINK_REASONING_LOG = [{"decided": "A", "why": "w", "rejected": "B", "rejected_why": "rw"}]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI_writing_decisions(0, "リトライしても直らなかった回答"))

    state = {"run_id": run_id, "current_task_id": "task_1_1", "current_phase": {"phase_id": "phase_1"}}
    result = cela_main._enforce_decision_lineage_freetext(
        [{"role": "user", "content": "prompt"}], "元の回答",
        client=None, model="m", label="Expert:test", tools=[], state=state,
    )
    assert result == "リトライしても直らなかった回答"
    row = conn.execute(
        "SELECT severity FROM issue_log WHERE run_id=? AND topic LIKE 'decision_lineage_gap_%'", (run_id,)
    ).fetchone()
    assert row is not None
    assert row["severity"] == "major"


def test_enforce_json_returns_parsed_unchanged_when_no_pending(monkeypatch):
    cela_main._THINK_REASONING_LOG = []
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []

    def _fail_if_called(*a, **k):
        raise AssertionError("pendingが無い場合はquery_AIを再度呼んではならない")
    monkeypatch.setattr(cela_main, "query_AI", _fail_if_called)

    original = {"constraint_issue": "none"}
    result = cela_main._enforce_decision_lineage_json(
        "prompt", original, client=None, model="m", label="Detector", tools=[], state={"run_id": "r"},
    )
    assert result is original


def test_enforce_json_retry_success_adopts_new_parsed(monkeypatch):
    cela_main._THINK_REASONING_LOG = [{"decided": "A", "why": "w", "rejected": "B", "rejected_why": "rw"}]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []

    def _fake(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        cela_main._LAST_WRITE_AGREEMENT_ITEMS = [{"entry_type": "Decision", "task_id": "t"}]
        return '{"constraint_issue": "major"}'
    monkeypatch.setattr(cela_main, "query_AI", _fake)

    result = cela_main._enforce_decision_lineage_json(
        "prompt", {"constraint_issue": "none"}, client=None, model="m", label="Detector", tools=[], state={"run_id": "r"},
    )
    assert result == {"constraint_issue": "major"}


def test_enforce_json_retry_malformed_response_falls_back_to_original_parsed(monkeypatch, db_conn):
    conn, run_id = db_conn
    cela_main._THINK_REASONING_LOG = [{"decided": "A", "why": "w", "rejected": "B", "rejected_why": "rw"}]
    cela_main._LAST_WRITE_AGREEMENT_ITEMS = []

    def _fake(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        return "not json at all"
    monkeypatch.setattr(cela_main, "query_AI", _fake)

    original = {"constraint_issue": "none"}
    state = {"run_id": run_id, "current_task_id": "task_1_1", "current_phase": {"phase_id": "phase_1"}}
    result = cela_main._enforce_decision_lineage_json(
        "prompt", original, client=None, model="m", label="Detector", tools=[], state=state,
    )
    assert result == original


# ---------------------------------------------------------------------------
# 4. THINK_TOOLの断り書き
# ---------------------------------------------------------------------------

def test_think_tool_decided_field_disclaims_persistence():
    decided_desc = cela_main.THINK_TOOL["function"]["parameters"]["properties"]["decided"]["description"]
    assert "write_agreement" in decided_desc
    assert "Decision" in decided_desc


def test_decision_lineage_directive_mentions_think_is_not_persistent():
    directive = cela_main._build_decision_lineage_directive('"Proposed"')
    assert "think" in directive


# ---------------------------------------------------------------------------
# 5. 12ノードへの配線確認（ソース検査）
# ---------------------------------------------------------------------------

_WIRED_NODE_FUNCS = [
    "call_task_planner", "call_orchestrator", "call_expert", "call_detector",
    "call_resource_arbiter", "call_reflection", "call_facilitator", "call_integrator",
    "call_reviewer", "generate_user_utterance", "call_goal_essence_analyst",
    "call_task_plan_reviewer",
]


@pytest.mark.parametrize("func_name", _WIRED_NODE_FUNCS)
def test_node_wires_decision_lineage_enforcement(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "_enforce_decision_lineage_freetext(" in src or "_enforce_decision_lineage_json(" in src, \
        f"{func_name}にBL-283のenforcementラッパーが配線されていません"


def test_decision_extractor_not_wired_with_enforcement():
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert "_enforce_decision_lineage_freetext(" not in src
    assert "_enforce_decision_lineage_json(" not in src
