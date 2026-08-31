"""
BL-329: 計画再構成が承認済みDeliverableを除去しないよう、生成時点で検証・自己修正させる。

1633ログ（run_id=1787890406-1e73a89d）実インシデント: BL-313のサブタスク分割トリガーが、
既に承認済みだったtask_5_2/task_5_5のDeliverableごとタスクを無条件で「廃止」し、分割後の
新task_idからは参照不能になった。read_deliverable_fileが「該当するDeliverableが見つかり
ませんでした」を24回連発した。

根本原因: call_task_planner（cela_main.py）がLLM出力（新しいphases JSON）に対して意味的な
検証を一切行っていなかった（AGENTS.md §15.3違反）。

対応: 既存の_query_and_parse_with_retryのvalidatorフック（BL-213 F3で導入済み）を再利用し、
(1) depends_on整合性、(2) 再構成時の承認済みtask_id保護、の2検証を生成時点でLLMに自己修正
させる一次防御を追加。BL-283の差し戻し再出力（_enforce_decision_lineage_json）にも同じ
validatorを適用する。一次防御のretry失敗・パース全滅時の保険として、task_planner_nodeの
removed_task_idsループへ機械的復元（二次防御）も追加。

設計はPlan mode + Cline独立レビュー（AGENTS.md §19.1、3回・指摘1〜7・F1〜F7を反映）を
経て確定。docs/design/back_log/BL-329/BL329_basic_design.md参照。
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
    db_path = str(tmp_path / "test_bl329.db")
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
    """task_idにentry_type='Deliverable'・指定statusのagreement行を作る最小ヘルパー。"""
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


# ---------------------------------------------------------------------------
# 1. `_validate_task_plan_depends_on_integrity` 単体テスト
# ---------------------------------------------------------------------------

def _phases(tasks_by_phase: dict) -> list:
    return [
        {"phase_id": pid, "title": pid, "tasks": tasks}
        for pid, tasks in tasks_by_phase.items()
    ]


def test_depends_on_integrity_passes_when_all_deps_exist():
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1", "depends_on": []},
        {"task_id": "task_1_2", "depends_on": ["task_1_1"]},
    ]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases)
    assert ok is True
    assert msg == ""


def test_depends_on_integrity_fails_on_dangling_reference():
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1", "depends_on": ["task_9_9"]},
    ]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases)
    assert ok is False
    assert "task_1_1" in msg
    assert "task_9_9" in msg


def test_depends_on_integrity_fails_on_duplicate_task_id():
    phases = _phases({"phase_1": [
        {"task_id": "task_1_1", "depends_on": []},
        {"task_id": "task_1_1", "depends_on": []},
    ]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases)
    assert ok is False
    assert "重複" in msg


def test_depends_on_integrity_fails_on_missing_task_id():
    phases = _phases({"phase_1": [
        {"task_id": "", "title": "名前なしタスク", "depends_on": []},
    ]})
    ok, msg = cela_main._validate_task_plan_depends_on_integrity(phases)
    assert ok is False
    assert "task_idがありません" in msg


def test_depends_on_integrity_passes_on_empty_phases():
    ok, msg = cela_main._validate_task_plan_depends_on_integrity([])
    assert ok is True
    assert msg == ""


# ---------------------------------------------------------------------------
# 2. `_build_protected_task_id_validator` 単体テスト
# ---------------------------------------------------------------------------

def test_protected_task_id_validator_passes_when_present():
    validator = cela_main._build_protected_task_id_validator({"task_5_2"})
    phases = _phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]})
    ok, msg = validator(phases)
    assert ok is True


def test_protected_task_id_validator_fails_when_missing():
    validator = cela_main._build_protected_task_id_validator({"task_5_2", "task_5_5"})
    phases = _phases({"phase_5": [{"task_id": "task_5_2_1", "depends_on": []}]})
    ok, msg = validator(phases)
    assert ok is False
    assert "task_5_2" in msg
    assert "task_5_5" in msg


def test_protected_task_id_validator_always_passes_when_empty_set():
    """[非退行] 保護対象が空（＝初回計画相当）の場合は常に合格すること。"""
    validator = cela_main._build_protected_task_id_validator(set())
    ok, msg = validator(_phases({"phase_1": [{"task_id": "task_1_1", "depends_on": []}]}))
    assert ok is True


# ---------------------------------------------------------------------------
# 3/4. `call_task_planner` 統合テスト（validator retryが実際に機能すること）
# ---------------------------------------------------------------------------

def _no_pending_decisions(monkeypatch):
    """_enforce_decision_lineage_jsonが早期returnするよう、pending decisionを空にする。"""
    monkeypatch.setattr(cela_main, "_pending_decision_candidates", lambda: [])


def test_call_task_planner_self_corrects_missing_protected_task_id(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2")
    _no_pending_decisions(monkeypatch)

    bad_phases = _phases({"phase_5": [{"task_id": "task_5_2_1", "depends_on": []}]})
    good_phases = _phases({"phase_5": [
        {"task_id": "task_5_2", "depends_on": []},
        {"task_id": "task_5_2_1", "depends_on": []},
    ]})
    responses = [copy.deepcopy(bad_phases), copy.deepcopy(good_phases)]

    def _fake_query_AI(messages, client=None, model=None, label="Unknown Node", tools=None,
                        light_system_prompt=None, state=None):
        import json
        return json.dumps(responses.pop(0))

    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)

    result = cela_main.call_task_planner(
        "テストゴール", state={"run_id": run_id},
        existing_phases=_phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]}),
        revision_reason="テスト用の再構成",
    )

    result_ids = {t["task_id"] for p in result for t in p["tasks"]}
    assert "task_5_2" in result_ids, "validatorのretryにより自己修正された2回目の応答が採用されるはず"
    assert not responses, "2回とも消費されているはず"


def test_call_task_planner_self_corrects_dangling_depends_on(db_conn, monkeypatch):
    conn, run_id = db_conn
    _no_pending_decisions(monkeypatch)

    bad_phases = _phases({"phase_1": [{"task_id": "task_1_1", "depends_on": ["task_9_9"]}]})
    good_phases = _phases({"phase_1": [{"task_id": "task_1_1", "depends_on": []}]})
    responses = [copy.deepcopy(bad_phases), copy.deepcopy(good_phases)]

    def _fake_query_AI(messages, client=None, model=None, label="Unknown Node", tools=None,
                        light_system_prompt=None, state=None):
        import json
        return json.dumps(responses.pop(0))

    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)

    result = cela_main.call_task_planner("テストゴール", state={"run_id": run_id})

    all_deps = [dep for p in result for t in p["tasks"] for dep in t.get("depends_on", [])]
    assert "task_9_9" not in all_deps


def test_call_task_planner_applies_validator_to_bl283_retry_output_too(db_conn, monkeypatch):
    """[Cline指摘F1・call_task_planner配線の直接確認] BL-283（未記録Decision）の差し戻し
    再出力にもvalidatorが適用されること。1回目のquery_AI呼び出し（_query_and_parse_with_
    retry内）は保護task_idを含む正しいJSONを返す（validator合格・retry無し）が、
    _pending_decision_candidatesが非空を返すためBL-283の差し戻しが発火し、2回目の
    query_AI呼び出し（_enforce_decision_lineage_json内）は保護task_idを欠いた不正なJSONを
    返す。call_task_plannerのvalidator配線（cela_main.py:12352-12356）が無ければ、この
    不正な2回目の出力がそのまま採用されてしまう。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2")
    monkeypatch.setattr(
        cela_main, "_pending_decision_candidates",
        lambda: [{"decided": "x", "why": "y", "rejected": "z", "rejected_why": "w"}],
    )

    good_first_response = _phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]})
    bad_bl283_retry = _phases({"phase_5": [{"task_id": "task_5_2_1", "depends_on": []}]})
    responses = [copy.deepcopy(good_first_response), copy.deepcopy(bad_bl283_retry)]

    def _fake_query_AI(messages, client=None, model=None, label="Unknown Node", tools=None,
                        light_system_prompt=None, state=None):
        import json
        return json.dumps(responses.pop(0))

    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)

    result = cela_main.call_task_planner(
        "テストゴール", state={"run_id": run_id},
        existing_phases=_phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]}),
        revision_reason="テスト用の再構成",
    )

    result_ids = {t["task_id"] for p in result for t in p["tasks"]}
    assert result_ids == {"task_5_2"}, (
        "BL-283差し戻しの不正な再出力ではなく、validator合格済みの1回目の出力が"
        "採用されるはず"
    )
    assert not responses, "2回とも消費されているはず"


def test_call_task_planner_returns_last_attempt_when_retries_exhausted(db_conn, monkeypatch):
    """[非退行] validatorが最後まで不合格でも、_query_and_parse_with_retryはクラッシュせず
    最後の出力をそのまま返すこと（既存機構の挙動確認）。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2")
    _no_pending_decisions(monkeypatch)

    always_bad = _phases({"phase_5": [{"task_id": "task_5_2_1", "depends_on": []}]})

    def _fake_query_AI(messages, client=None, model=None, label="Unknown Node", tools=None,
                        light_system_prompt=None, state=None):
        import json
        return json.dumps(copy.deepcopy(always_bad))

    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)

    result = cela_main.call_task_planner(
        "テストゴール", state={"run_id": run_id},
        existing_phases=_phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]}),
        revision_reason="テスト用の再構成",
    )
    result_ids = {t["task_id"] for p in result for t in p["tasks"]}
    assert result_ids == {"task_5_2_1"}, "リトライを使い切っても最後の出力がそのまま返るはず"


# ---------------------------------------------------------------------------
# 5. `_enforce_decision_lineage_json` 統合テスト（Cline指摘F1）
# ---------------------------------------------------------------------------

def test_enforce_decision_lineage_json_reverts_to_prior_parsed_when_retry_output_invalid(monkeypatch):
    monkeypatch.setattr(
        cela_main, "_pending_decision_candidates",
        lambda: [{"decided": "x", "why": "y", "rejected": "z", "rejected_why": "w"}],
    )
    monkeypatch.setattr(cela_main, "_record_decision_lineage_gap_issue", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "_LAST_WRITE_AGREEMENT_ITEMS", [])

    good_parsed = _phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]})
    bad_retry_output = _phases({"phase_5": [{"task_id": "task_5_2_1", "depends_on": []}]})

    monkeypatch.setattr(cela_main, "query_AI", lambda *a, **k: __import__("json").dumps(bad_retry_output))

    validator = cela_main._build_protected_task_id_validator({"task_5_2"})
    result = cela_main._enforce_decision_lineage_json(
        "prompt", good_parsed, client=None, model=None, label="Task Planner",
        tools=[], state=None, validator=validator,
    )

    assert result == good_parsed, "validator不合格の再出力ではなく、直前のparsedが採用されるはず"


def test_enforce_decision_lineage_json_accepts_retry_output_when_valid(monkeypatch):
    monkeypatch.setattr(
        cela_main, "_pending_decision_candidates",
        lambda: [{"decided": "x", "why": "y", "rejected": "z", "rejected_why": "w"}],
    )
    monkeypatch.setattr(cela_main, "_record_decision_lineage_gap_issue", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "_LAST_WRITE_AGREEMENT_ITEMS", [])

    good_parsed = _phases({"phase_5": [{"task_id": "task_5_2", "depends_on": []}]})
    good_retry_output = _phases({"phase_5": [
        {"task_id": "task_5_2", "depends_on": []}, {"task_id": "task_5_2_1", "depends_on": []},
    ]})

    monkeypatch.setattr(cela_main, "query_AI", lambda *a, **k: __import__("json").dumps(good_retry_output))

    validator = cela_main._build_protected_task_id_validator({"task_5_2"})
    result = cela_main._enforce_decision_lineage_json(
        "prompt", good_parsed, client=None, model=None, label="Task Planner",
        tools=[], state=None, validator=validator,
    )

    assert result == good_retry_output


def test_enforce_decision_lineage_json_validator_none_is_non_regression(monkeypatch):
    """[非退行] validator省略（デフォルトNone）時は従来通り再出力をそのまま採用すること
    （detector等、他の呼び出し元の挙動を変えないことの確認）。"""
    monkeypatch.setattr(
        cela_main, "_pending_decision_candidates",
        lambda: [{"decided": "x", "why": "y", "rejected": "z", "rejected_why": "w"}],
    )
    monkeypatch.setattr(cela_main, "_record_decision_lineage_gap_issue", lambda *a, **k: None)
    monkeypatch.setattr(cela_main, "_LAST_WRITE_AGREEMENT_ITEMS", [])
    monkeypatch.setattr(cela_main, "query_AI", lambda *a, **k: '{"a": 1}')

    result = cela_main._enforce_decision_lineage_json(
        "prompt", {"a": 0}, client=None, model=None, label="Detector", tools=[], state=None,
    )
    assert result == {"a": 1}


# ---------------------------------------------------------------------------
# 6. `task_planner_node` 二次防御（機械的復元）統合テスト
# ---------------------------------------------------------------------------

EXISTING_PHASES_WITH_APPROVED = [
    {"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        {"task_id": "task_5_2", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]},
]


def _base_state(run_id, extra=None):
    state = {
        "run_id": run_id, "goal": "テスト目標", "turn_count": 5,
        "phases": copy.deepcopy(EXISTING_PHASES_WITH_APPROVED),
        "plan_revision_reason": "テスト用の再構成", "plan_review_done": True,
        "round_count": 4,
    }
    if extra:
        state.update(extra)
    return state


def test_task_planner_node_restores_approved_task_instead_of_superseding(db_conn, monkeypatch):
    """task_5_1（Deliverableなし）は従来通りsupersede、task_5_2（Approved Deliverable
    あり）は廃止されず計画へ復元されること（1633ログの実インシデントの再発防止確認）。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    # 新計画はtask_5_1・task_5_2どちらも含まない（validatorが機能しなかった場合を模す）。
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": [
        {"task_id": "task_5_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(_base_state(run_id))

    result_ids = {t["task_id"] for p in result["phases"] for t in p["tasks"]}
    assert "task_5_2" in result_ids, "承認済みDeliverableを持つtask_5_2は復元されるはず"
    assert "task_5_2_1" in result_ids
    superseded_ids = {s["task_id"] for s in result.get("phases_superseded", [])}
    assert "task_5_1" in superseded_ids
    assert "task_5_2" not in superseded_ids


def test_task_planner_node_restore_writes_audit_directive(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved_with_Conditions")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": []}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    cela_main.task_planner_node(_base_state(run_id))

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    restored = [a for a in agreements if a["topic"] == "task_plan_task_5_2_restored_by_bl329"]
    assert len(restored) == 1
    assert restored[0]["entry_type"] == "Directive"


def test_task_planner_node_restores_implicitly_accepted_status(db_conn, monkeypatch):
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Implicitly_Accepted")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": []}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(_base_state(run_id))

    result_ids = {t["task_id"] for p in result["phases"] for t in p["tasks"]}
    assert "task_5_2" in result_ids


def test_task_planner_node_restores_into_new_phase_when_phase_missing(db_conn, monkeypatch):
    """復元対象のphase_idが新計画に一つも存在しない場合、旧phaseオブジェクトを浅コピーした
    新規phaseエントリとして追加されること。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    # 新計画はphase_5自体を含まない（別のphaseだけ）。
    new_phases = [{"phase_id": "phase_9", "title": "無関係なフェーズ", "tasks": [
        {"task_id": "task_9_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(_base_state(run_id))

    restored_phase = next((p for p in result["phases"] if p["phase_id"] == "phase_5"), None)
    assert restored_phase is not None, "phase_5が旧phaseの浅コピーとして復元されているはず"
    assert restored_phase["title"] == "フェーズ5"
    restored_task_ids = {t["task_id"] for t in restored_phase["tasks"]}
    assert restored_task_ids == {"task_5_2"}


def test_task_planner_node_restored_deliverable_is_readable_end_to_end(db_conn, monkeypatch):
    """復元後、read_deliverable_fileが承認済み内容を正しく返すこと
    （1633ログの実インシデントの直接的な再発防止確認）。_resolve_deliverable_pointerは
    decision_whatがWHITEBOARD:/FILE_PATH:ポインタである行しか解決しないため（BL-084）、
    実際のwrite_agreement経由と同じくwhiteboard_draftsを実際に作った上で確認する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_RUN_ID = run_id
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_5", "task_5_2", "task_5_2の承認済み成果物本文。", "expert", "初版")
    cela_main.db_append_agreement(
        {
            "id": "AG-test-task_5_2", "action_type": "CREATE", "status": "Approved",
            "topic": "task_5_2成果物", "decision_what": "WHITEBOARD:phase_5:task_5_2",
            "reason_why": "テスト用", "proposed_by": "expert", "entry_type": "Deliverable",
            "phase_id": "phase_5", "task_id": "task_5_2", "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "is_frozen": 0,
            "internal_thought_process": None, "citations": "[]",
        },
        conn, run_id,
    )
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    new_phases = [{"phase_id": "phase_5", "title": "フェーズ5", "tasks": []}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(_base_state(run_id))

    resolved = cela_main._resolve_deliverable_pointer("task_5_2", "")
    assert resolved == "WHITEBOARD:phase_5:task_5_2"
    assert "task_5_2" not in {s["task_id"] for s in result.get("phases_superseded", [])}


def test_task_planner_node_parse_failure_fallback_scenario_still_protects(db_conn, monkeypatch):
    """[Cline指摘F2] JSONパースが全滅しfallback_phaseが採用された場合（＝一次防御が
    最初から機能しない最悪ケース）でも、二次防御だけで承認済みtask_idが失われないこと。"""
    conn, run_id = db_conn
    _create_approved_deliverable(conn, run_id, "phase_5", "task_5_2", status="Approved")
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    # fallback_phase相当（縮退計画、旧task_idを一切含まない）を返す。
    fallback_like = [{"phase_id": "phase_1", "title": "フェーズ1", "tasks": [
        {"task_id": "task_1_1", "title": "初期タスク", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(fallback_like))

    result = cela_main.task_planner_node(_base_state(run_id))

    result_ids = {t["task_id"] for p in result["phases"] for t in p["tasks"]}
    assert "task_5_2" in result_ids, "パース全滅の最悪ケースでも二次防御が承認済みtask_idを守るはず"


# ---------------------------------------------------------------------------
# 7. BL-191（一時的backward-redirect）との相互作用の非退行
# ---------------------------------------------------------------------------

def test_bl329_does_not_block_bl191_focus_vanish_reconciliation(db_conn, monkeypatch):
    """[実装後diffレビューで発覚した回帰・修正済み] BL-191のredirect_backwardは、既に
    Approved済みの過去タスクへ一時的にフォーカスを戻し、その後
    _reconcile_current_phase_after_replanが「フォーカス中task_idが新計画から消えた」ことを
    検知して強制的にfocus_stackをクリアし、フォワードタスクへ復帰する設計
    （test_bl191_task_focus_scheduling.py参照）。BL-329がこの「消えるべきtask_id」まで
    機械的に計画へ復元すると、BL-191のreconcile分岐が発火しなくなる。task_focus_stackの
    focused_task_idはBL-329の保護対象から除外し、BL-191側の既存reconcile処理に委ねる
    べきことの回帰確認。"""
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_1", "task_1_1", "task_1_1の承認済み成果物。", "expert", "初版")
    cela_main.db_append_agreement(
        {
            "id": "AG-test-task_1_1", "action_type": "CREATE", "status": "Approved",
            "topic": "task_1_1成果物", "decision_what": "WHITEBOARD:phase_1:task_1_1",
            "reason_why": "テスト用", "proposed_by": "expert", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1", "depends_on": "[]", "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "is_frozen": 0,
            "internal_thought_process": None, "citations": "[]",
        },
        conn, run_id,
    )

    phases = [
        {"phase_id": "phase_1", "title": "フェーズ1", "tasks": [
            {"task_id": "task_1_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        ]},
        {"phase_id": "phase_2", "title": "フェーズ2", "tasks": [
            {"task_id": "task_2_1", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        ]},
    ]
    current_phase = phases[1]
    state = {
        "run_id": run_id, "phases": phases, "current_phase": current_phase,
        "current_task_id": "task_2_1", "round_count": 1,
        "task_focus_stack": [], "task_focus_companion": None,
        "task_focus_redirect_count": 0, "task_focus_redirect_notice": "",
        "task_focus_resume_notice": "",
    }
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "確認のため一時的にフォーカス",
        "baseline_agreement_id": "AG-test-task_1_1",
    })
    assert state["current_task_id"] == "task_1_1"

    state["goal"] = "テスト目標"
    state["turn_count"] = 5
    state["plan_revision_reason"] = "task_plan_reviewerの指摘による全体再編"
    state["plan_review_done"] = True

    # 新計画からtask_1_1（フォーカス中の過去タスク、Approved済み）自体が消える。
    new_phases = [{"phase_id": "phase_9", "title": "新規", "tasks": [
        {"task_id": "task_9_9", "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
    ]}]
    monkeypatch.setattr(cela_main, "seed_entities_from_goal", lambda *a, **k: {"registered": [], "rejected": [], "skipped": True})
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: copy.deepcopy(new_phases))

    result = cela_main.task_planner_node(state)

    # BL-329に保護されて計画へ居座ることなく、BL-191のreconcile通り強制的にクリアされること。
    assert result["task_focus_stack"] == []
    assert result["current_task_id"] == ""
    result_ids = {t["task_id"] for p in result["phases"] for t in p["tasks"]}
    assert "task_1_1" not in result_ids
