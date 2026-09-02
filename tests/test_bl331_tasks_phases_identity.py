"""
BL-331: task_id/phase_idの「識別」（今どれが正本として実在するか）をDAGとして
機械的に管理するPhase 1。

BL-330の根本原因調査で、CELAには「task_id/phase_idが今現在実在するか」を検証できるDBテーブルが
1つも存在しないことが判明した。Task/PhaseはLangGraph checkpoint内のJSON（state["phases"]）に
しか存在せず、BL-224のrelation_edgesは`task:<task_id>`参照型を「実表の行として検証できない」
という理由で明示的に却下していた。

本BLは新規`tasks`/`phases`テーブルを導入し、`task_planner_node`が計画を確定するたびに
（初回計画・再構成の両方で）これらのテーブルを同期する。BL-329が既に計算済みの
「復元されたか／真にsupersedeされたか」の判定結果をそのまま再利用し、判定ロジックを重複させない。
あわせて`_resolve_ref_table`へ`task:`/`phase:`参照プレフィックスを追加し（BL-224の却下理由を
解消）、タスク分割の系譜（task_5_2→task_5_2_1）を`split_from`フィールド＋新規`split_from`
relation_typeのrelation_edgesエッジとして記録する。

設計はPlan mode + Cline独立レビュー（AGENTS.md §19.1、H-1〜H-3・M-1〜M-3・L-1〜L-4を反映）を
経て確定。docs/design/back_log/BL-331/BL331_basic_design.md参照。
実LLM API呼び出しは伴わない。
"""

import copy
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl331.db")
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


def _create_approved_deliverable(conn, run_id, phase_id, task_id, status="Approved"):
    cela_main.db_append_agreement(
        {
            "id": f"AG-test-{task_id}", "action_type": "CREATE", "status": status,
            "topic": f"{task_id}成果物", "decision_what": f"{task_id}の成果物本文。",
            "reason_why": "テスト用", "proposed_by": "expert", "entry_type": "Deliverable",
            "phase_id": phase_id, "task_id": task_id, "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "is_frozen": 0,
            "internal_thought_process": None, "citations": "[]",
        },
        conn, run_id,
    )


def _base_state(run_id, phases, extra=None):
    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": copy.deepcopy(phases),
        "plan_revision_reason": "テスト用の再構成", "plan_review_done": True,
        "round_count": 4,
    }
    if extra:
        state.update(extra)
    return state


def _task_row(conn, run_id, task_id):
    return conn.execute(
        "SELECT * FROM tasks WHERE run_id=? AND task_id=?", (run_id, task_id)
    ).fetchone()


def _phase_row(conn, run_id, phase_id):
    return conn.execute(
        "SELECT * FROM phases WHERE run_id=? AND phase_id=?", (run_id, phase_id)
    ).fetchone()


# ---------------------------------------------------------------------------
# 1. スキーマ: PRIMARY KEYによるtask_id/phase_id一意性の保証
# ---------------------------------------------------------------------------

def test_tasks_table_primary_key_rejects_duplicate(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES (?, ?, ?, '', 'active', '', ?, ?)",
        ("task_1_1", run_id, "phase_1", now, now),
    )
    with pytest.raises(cela_main.sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
            "VALUES (?, ?, ?, '', 'active', '', ?, ?)",
            ("task_1_1", run_id, "phase_1", now, now),
        )


def test_phases_table_primary_key_rejects_duplicate(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO phases (phase_id, run_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES (?, ?, '', 'active', '', ?, ?)",
        ("phase_1", run_id, now, now),
    )
    with pytest.raises(cela_main.sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO phases (phase_id, run_id, title, status, superseded_reason, created_at, updated_at) "
            "VALUES (?, ?, '', 'active', '', ?, ?)",
            ("phase_1", run_id, now, now),
        )


# ---------------------------------------------------------------------------
# 2. 初回計画で両テーブルが埋まること
# ---------------------------------------------------------------------------

def test_initial_plan_populates_tasks_and_phases(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_1", "title": "フェーズ1", "tasks": [
        {"task_id": "task_1_1", "title": "タスク1-1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    state = {"run_id": run_id, "goal": "テスト目標", "turn_count": 1, "phases": {}, "round_count": 0}
    cela_main.task_planner_node(state)

    t = _task_row(conn, run_id, "task_1_1")
    p = _phase_row(conn, run_id, "phase_1")
    assert t is not None and t["status"] == "active"
    assert p is not None and p["status"] == "active"


# ---------------------------------------------------------------------------
# 3〜4. 再計画: BL-329復元 vs 真のsupersede
# ---------------------------------------------------------------------------

EXISTING_PHASES = [
    {"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
]


def test_restored_task_stays_active_in_tasks_table(db_conn, monkeypatch):
    """task_5_2（Approved Deliverableあり）はBL-329により計画へ復元される。tasks側も
    supersededにならず'active'のままであること。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))

    t = _task_row(conn, run_id, "task_5_2")
    assert t is not None
    assert t["status"] == "active"
    assert t["superseded_reason"] == ""


def test_genuinely_removed_task_becomes_superseded(db_conn, monkeypatch):
    """task_5_1（Deliverableなし）は従来通りsupersede対象。tasks側も'superseded'かつ
    superseded_reasonがrevision_reasonと一致すること。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))

    t = _task_row(conn, run_id, "task_5_1")
    assert t is not None
    assert t["status"] == "superseded"
    assert t["superseded_reason"] == "テスト用の再構成"


# ---------------------------------------------------------------------------
# 5. フェーズが丸ごと消える再計画
# ---------------------------------------------------------------------------

def test_phase_removed_entirely_becomes_superseded(db_conn, monkeypatch):
    conn, run_id = db_conn
    existing = [
        {"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
            {"task_id": "task_5_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        ]},
    ]
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_6", "title": "フェーズ6", "tasks": [
        {"task_id": "task_6_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    cela_main.task_planner_node(_base_state(run_id, existing))

    p = _phase_row(conn, run_id, "phase_5")
    assert p is not None
    assert p["status"] == "superseded"
    assert p["superseded_reason"] == "テスト用の再構成"


def test_phase_survives_when_its_task_is_restored(db_conn, monkeypatch):
    """フェーズ内の全タスクが消えるように見えても、承認済みタスクの復元によりフェーズ自体が
    浅コピーで復元される（BL-329既存挙動）ケースで、phasesテーブルも'active'のままであること。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    # 新計画にphase_5自体が一切登場しない（フェーズごと消えたように見えるケース）。
    new_phases = [{"phase_id": "phase_6", "title": "フェーズ6", "tasks": [
        {"task_id": "task_6_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))

    result_phase_ids = {p["phase_id"] for p in result["phases"]}
    assert "phase_5" in result_phase_ids, "task_5_2復元によりphase_5も浅コピー復元されるはず"
    p = _phase_row(conn, run_id, "phase_5")
    assert p is not None and p["status"] == "active"


# ---------------------------------------------------------------------------
# 6. tasks行が一度も存在しないtask_idがsupersede対象になるエッジケース
# ---------------------------------------------------------------------------

def test_supersede_without_prior_tasks_row_creates_synthetic_row(db_conn, monkeypatch):
    """パース全滅でfallback_phaseが採用され、tasksテーブルに一度も行が無かったtask_idが
    いきなりsupersede対象になるケースでも、合成行が作られること。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    fallback_like = [{"phase_id": "phase_1", "title": "全体", "tasks": [
        {"task_id": "task_1_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(fallback_like))

    # 事前にtasksテーブルへtask_5_1の行を作らないまま、既存計画にのみ存在させる。
    cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))

    t = _task_row(conn, run_id, "task_5_1")
    assert t is not None, "tasksテーブルに一度も行が無かったtask_idのsupersedeで合成行が作られていない"
    assert t["status"] == "superseded"


# ---------------------------------------------------------------------------
# 7. task:/phase: 参照の _resolve_ref_table 解決（status不問）
# ---------------------------------------------------------------------------

def test_resolve_ref_table_task_prefix_status_agnostic(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('task_a', ?, 'phase_1', '', 'active', '', ?, ?)", (run_id, now, now))
    conn.execute(
        "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('task_b', ?, 'phase_1', '', 'superseded', 'x', ?, ?)", (run_id, now, now))

    assert cela_main._resolve_ref_table(conn.execute, run_id, "task:task_a") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, "task:task_b") is True, "supersede済みも解決できるはず（status不問）"
    assert cela_main._resolve_ref_table(conn.execute, run_id, "task:task_nonexistent") is False


def test_resolve_ref_table_phase_prefix(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO phases (phase_id, run_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('phase_a', ?, '', 'active', '', ?, ?)", (run_id, now, now))
    assert cela_main._resolve_ref_table(conn.execute, run_id, "phase:phase_a") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, "phase:phase_nonexistent") is False


# ---------------------------------------------------------------------------
# 8. trace_lineageでのtask:参照の解決・レンダリング
# ---------------------------------------------------------------------------

def test_trace_lineage_handler_resolves_task_ref(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('task_a', ?, 'phase_1', 'タスクA', 'active', '', ?, ?)", (run_id, now, now))
    res = cela_main._trace_lineage_handler({"ref": "task:task_a"})
    assert res["status"] == "ok"
    assert "run 内に該当 ref はありません" not in res.get("result", "")


def test_resolve_ref_line_renders_task_and_phase(db_conn):
    conn, run_id = db_conn
    now = time.time()
    conn.execute(
        "INSERT INTO tasks (task_id, run_id, phase_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('task_a', ?, 'phase_1', 'タスクA', 'active', '', ?, ?)", (run_id, now, now))
    conn.execute(
        "INSERT INTO phases (phase_id, run_id, title, status, superseded_reason, created_at, updated_at) "
        "VALUES ('phase_1', ?, 'フェーズ1', 'active', '', ?, ?)", (run_id, now, now))
    task_line = cela_main._resolve_ref_line(conn, run_id, "task:task_a")
    phase_line = cela_main._resolve_ref_line(conn, run_id, "phase:phase_1")
    assert "タスクA" in task_line and "phase_1" in task_line
    assert "フェーズ1" in phase_line


# ---------------------------------------------------------------------------
# 9. split_fromによるrelation_edges書き込み
# ---------------------------------------------------------------------------

def test_split_from_creates_relation_edge(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved_with_Conditions")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": [], "split_from": ""},
        {"task_id": "task_5_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": [], "split_from": "task_5_2"},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))

    edges = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='split_from'", (run_id,)
    ).fetchall()
    assert len(edges) == 1
    assert edges[0]["from_ref"] == "task:task_5_2"
    assert edges[0]["to_ref"] == "task:task_5_2_1"


# ---------------------------------------------------------------------------
# 10・14. split_from validatorの検証（存在しない参照・初回計画での拒否）
# ---------------------------------------------------------------------------

def _phases(tasks_by_phase: dict) -> list:
    return [
        {"phase_id": pid, "title": pid, "tasks": tasks}
        for pid, tasks in tasks_by_phase.items()
    ]


def test_split_from_dangling_reference_rejected():
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1_1", "depends_on": [], "split_from": "task_1_1"},
    ]})
    existing = _phases({"phase_1": [{"task_id": "task_1_9", "depends_on": []}]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases, existing)
    assert ok is False
    assert "task_1_1_1" in msg and "task_1_1" in msg


def test_split_from_valid_reference_passes():
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1_1", "depends_on": [], "split_from": "task_1_1"},
    ]})
    existing = _phases({"phase_1": [{"task_id": "task_1_1", "depends_on": []}]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases, existing)
    assert ok is True
    assert msg == ""


def test_split_from_rejected_on_initial_plan():
    """existing_phasesが空（初回計画）の場合、split_from非空は常に不正。"""
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1", "depends_on": [], "split_from": "task_0_1"},
    ]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases, None)
    assert ok is False
    assert "task_1_1" in msg


def test_split_from_nested_within_same_revision_rejected():
    """同一リビジョン内で新規に生まれたtask_id同士のネスト分割は不正
    （split_fromがexisting_phasesではなく今回の候補内の新規task_idを指す）。"""
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1_1", "depends_on": [], "split_from": "task_1_1"},
        {"task_id": "task_1_1_1_1", "depends_on": [], "split_from": "task_1_1_1"},
    ]})
    existing = _phases({"phase_1": [{"task_id": "task_1_1", "depends_on": []}]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases, existing)
    assert ok is False
    assert "task_1_1_1_1" in msg


# ---------------------------------------------------------------------------
# 11. 再活性化: 一度supersededになったtask/phaseが再登場したらactiveへ戻ること
# ---------------------------------------------------------------------------

def test_reactivated_task_returns_to_active(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})

    # replan N: task_5_1が消える（superseded化）。
    new_phases_n = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases_n))
    state = cela_main.task_planner_node(_base_state(run_id, EXISTING_PHASES))
    assert _task_row(conn, run_id, "task_5_1")["status"] == "superseded"

    # replan N+1: task_5_1が再登場。
    new_phases_n1 = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases_n1))
    state["plan_revision_reason"] = "2回目の再構成"
    cela_main.task_planner_node(state)

    t = _task_row(conn, run_id, "task_5_1")
    assert t["status"] == "active"
    assert t["superseded_reason"] == ""


# ---------------------------------------------------------------------------
# 12. resume冪等性: 同じ内容で再度syncしても重複・不整合が生じないこと
# ---------------------------------------------------------------------------

def test_split_from_edge_does_not_duplicate_on_resync(db_conn):
    """[Cline指摘・§19.4] tasks/phasesはON CONFLICT DO UPDATEで冪等だが、split_fromの
    relation_edgesは毎回無条件INSERTだと重複蓄積する（checkpoint resume等での再実行を想定）。
    同一のsplit_fromを含むphasesを2回同期しても、エッジは1本のままであること。"""
    conn, run_id = db_conn
    phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": [], "split_from": ""},
        {"task_id": "task_5_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": [], "split_from": "task_5_2"},
    ]}]
    cela_main._sync_task_phase_identity(conn, run_id, phases, [], {}, "")
    cela_main._sync_task_phase_identity(conn, run_id, phases, [], {}, "")

    edges = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='split_from'", (run_id,)
    ).fetchall()
    assert len(edges) == 1, "split_fromエッジが再同期で重複した"


def test_sync_task_phase_identity_is_idempotent(db_conn):
    conn, run_id = db_conn
    phases = EXISTING_PHASES
    cela_main._sync_task_phase_identity(conn, run_id, phases, [], {}, "")
    cela_main._sync_task_phase_identity(conn, run_id, phases, [], {}, "")

    rows = conn.execute("SELECT * FROM tasks WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 2, "同じphasesを2回同期しても重複行が生じないこと"
    for r in rows:
        assert r["status"] == "active"


# ---------------------------------------------------------------------------
# 13. 個別revert確認用の対象関数が実在すること（§17.1の前提確認）
# ---------------------------------------------------------------------------

def test_sync_task_phase_identity_function_exists():
    assert callable(cela_main._sync_task_phase_identity)
    assert callable(cela_main._validate_task_plan_depends_on_integrity)
