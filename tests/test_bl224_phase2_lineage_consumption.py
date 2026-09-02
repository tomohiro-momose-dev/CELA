"""
BL-224 Phase 2: 系譜（lineage）の消費経路テスト（§15.4: 入口と同時に出口を検証）。

Phase 1 が relation_edges テーブルと書き込み骨格（W1/W2/W3/N2/C2/C5）を実装した。
Phase 2 は「書いた線を誰が読むか」という消費経路を実装した:
- W4: confirmed_variables[].derived_from による 値→値 の系譜エッジ（無効 ref はスキップ＋警告）
- C4: 上流値変更時の下流（従属側）への陳腐化マーカー前方伝播（idempotent）
- C1: Hydrate コンテキスト（_build_agreements_context）の系譜（変遷＋前提）表示
- C3: task_plan_reviewer の provisional-on-provisional アンカリング検査

すべて LLM を呼ばないオフライン DB テスト。実 LLM 呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl224_p2.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-p2-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _append_agreement(conn, run_id, id, topic, status="Approved", decision_what="dw",
                      reason="r", entry_type="Decision", phase_id="phase_1",
                      task_id="task_1_1", depends_on="[]"):
    """db_append_agreement の既存テスト呼び出しと揃えたシードヘルパ。"""
    cela_main.db_append_agreement(
        {
            "id": id, "action_type": "CREATE", "status": status,
            "topic": topic, "decision_what": decision_what, "reason_why": reason,
            "proposed_by": "expert", "entry_type": entry_type, "phase_id": phase_id,
            "task_id": task_id, "depends_on": depends_on, "resource_claims": "{}",
            "timestamp": time.time(), "evidence": "", "citations": "[]",
        },
        conn, run_id,
    )


def _seed_fact(conn, run_id, name, value, confidence="confirmed", citations=None):
    conn.execute(
        "INSERT INTO verified_facts (run_id, variable_name, value, unit, source_task_id, "
        "source_phase_id, confirmed_by, confirmed_at, reason, citations, confidence) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, name, str(value), "", "task_1_1", "phase_1", "expert",
         time.time(), "seed", json_dumps(citations), confidence),
    )


def json_dumps(citations):
    import json
    return json.dumps(citations or [], ensure_ascii=False)


# ---------------------------------------------------------------------------
# W4: confirmed_variables[].derived_from による 値→値 系譜（無効 ref はスキップ＋警告）
# ---------------------------------------------------------------------------

def test_w4_write_agreement_creates_fact_to_fact_derived_from_edge(db_conn):
    conn, run_id = db_conn
    # 派生元となる fact を事前に実在させる（_write_relation_edge は ref 実在検証を行う）
    _seed_fact(conn, run_id, "budget_cap", 1000, confidence="confirmed")

    res = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Decision",
            "topic": "car_count", "decision_what": "車両台数を4台とする",
            "reason_why": "予算から算出",
            "confirmed_variables": [
                {"variable_name": "car_count", "value": "4", "unit": "台",
                 "derived_from": ["fact:budget_cap"]},
            ],
        },
        conn, run_id, "expert",
    )
    assert res.get("success") is True, res
    # fact:car_count → fact:budget_cap の derived_from エッジが張られていること
    rows = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='derived_from' "
        "AND from_ref='fact:car_count' AND to_ref='fact:budget_cap'",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1


def test_w4_invalid_derived_from_ref_is_skipped_with_warning(db_conn):
    conn, run_id = db_conn
    res = cela_main._write_agreement_impl(
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Decision",
            "topic": "x_count", "decision_what": "xを1とする",
            "reason_why": "r",
            "confirmed_variables": [
                {"variable_name": "x_count", "value": "1",
                 "derived_from": ["bogus:ref", "task:foo"]},
            ],
        },
        conn, run_id, "expert",
    )
    assert res.get("success") is True
    # 事実保存は失敗せず、警告のみ
    assert "derived_from の一部が無効なためスキップされました" in (res.get("warning") or "")
    assert "bogus:ref" in (res.get("warning") or "")
    assert "task:foo" in (res.get("warning") or "")
    # 無効 ref の値→値（fact:→fact:）エッジは書かれない（W1 の agreement→fact 骨格エッジは
    # 別途書かれるため、here では fact: 始まりの derived_from のみを数える）
    rows = conn.execute(
        "SELECT COUNT(*) FROM relation_edges WHERE run_id=? AND relation_type='derived_from' "
        "AND from_ref LIKE 'fact:%'",
        (run_id,),
    ).fetchone()[0]
    assert rows == 0


# ---------------------------------------------------------------------------
# C4: 上流値変更時の下流（従属側）への陳腐化マーカー前方伝播（idempotent）
# ---------------------------------------------------------------------------

def test_c4_staleness_marker_propagates_to_downstream_fact(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, "budget_cap", 1000, confidence="confirmed")
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional")
    # derived_from エッジ: from=従属側(下流) → to=ソース側(上流)
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:budget_cap", "derived_from",
        "r", "expert",
    )

    # 上流 budget_cap を 1000→1200 へ変更
    cela_main.upsert_verified_fact(
        conn, run_id, "budget_cap", 1200, unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    reason = conn.execute(
        "SELECT reason FROM verified_facts WHERE run_id=? AND variable_name='car_count'",
        (run_id,),
    ).fetchone()[0]
    assert "⚠️[BL-224: 上流変更で要再確認]" in reason

    # さらに 1200→1300 へ変更してもマーカーは重複しない（idempotent）
    cela_main.upsert_verified_fact(
        conn, run_id, "budget_cap", 1300, unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    reason2 = conn.execute(
        "SELECT reason FROM verified_facts WHERE run_id=? AND variable_name='car_count'",
        (run_id,),
    ).fetchone()[0]
    assert reason2.count("⚠️[BL-224: 上流変更で要再確認]") == 1


def test_c4_no_marker_when_value_unchanged(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, "budget_cap", 1000, confidence="confirmed")
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional")
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:budget_cap", "derived_from", "r", "expert",
    )
    # 同値再 upsert（1000→1000）ではマーカーを伝播しない
    cela_main.upsert_verified_fact(
        conn, run_id, "budget_cap", 1000, unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    reason = conn.execute(
        "SELECT reason FROM verified_facts WHERE run_id=? AND variable_name='car_count'",
        (run_id,),
    ).fetchone()[0]
    assert "⚠️[BL-224: 上流変更で要再確認]" not in (reason or "")


def test_c4_staleness_marker_propagates_to_downstream_entity_attribute(db_conn):
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "茅野市", "city", "goal_text", "expert")
    cela_main.upsert_entity_attribute(
        conn, run_id, "茅野市", "population", 1000, "", "confirmed", [], "seed",
        "task_1_1", "phase_1", "expert",
    )
    cela_main.upsert_entity_attribute(
        conn, run_id, "茅野市", "tax_base", 500, "", "provisional", [], "seed",
        "task_1_1", "phase_1", "expert",
    )
    # tax_base は population に依存（from=従属側 → to=ソース側）
    assert cela_main._write_relation_edge(
        conn, run_id, "entity:茅野市:tax_base", "entity:茅野市:population",
        "derived_from", "r", "expert",
    )
    # 上流 population を 1000→1200 へ変更
    cela_main.upsert_entity_attribute(
        conn, run_id, "茅野市", "population", 1200, "", "confirmed", [], "changed",
        "task_1_1", "phase_1", "expert",
    )
    reason = conn.execute(
        "SELECT reason FROM entity_attributes WHERE run_id=? AND entity_id='茅野市' "
        "AND attr_name='tax_base'",
        (run_id,),
    ).fetchone()[0]
    assert "⚠️[BL-224: 上流変更で要再確認]" in reason


# ---------------------------------------------------------------------------
# C1: Hydrate コンテキスト（_build_agreements_context）の系譜表示
# ---------------------------------------------------------------------------

def test_c1_lineage_rendered_when_conn_available(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-old", "car_count", status="Superseded",
                      decision_what="5台", reason="予算超過")
    _append_agreement(conn, run_id, "AG-new", "car_count", status="Approved",
                      decision_what="3台", reason="ピーク輸送力で再計算")
    _append_agreement(conn, run_id, "AG-base", "budget_cap", status="Approved",
                      decision_what="予算上限", reason="r")
    # 変遷連鎖: AG-old → AG-new (supersedes)
    assert cela_main._write_relation_edge(
        conn, run_id, "agreement:AG-old", "agreement:AG-new", "supersedes",
        "予算超過のため棄却", "expert",
    )
    # 前提: AG-new は AG-base に depends_on
    assert cela_main._write_relation_edge(
        conn, run_id, "agreement:AG-base", "agreement:AG-new", "depends_on",
        "r", "expert",
    )

    out = cela_main._build_agreements_context_from_db(conn, run_id)
    assert "系譜（変遷）" in out, out
    assert "前提" in out, out
    # 棄却された旧版の理由が変遷ストーリーに含まれる
    assert "予算超過" in out


def test_c1_fallback_to_prior_superseded_when_no_conn(db_conn):
    conn, run_id = db_conn
    # メモリ上の agreements リストのみ（conn なし）でフォールバック動作を確認
    agreements = [
        {"id": "AG-a", "entry_type": "Decision", "status": "Superseded",
         "topic": "car_count", "decision_what": "5台", "reason_why": "予算超過",
         "citations": "[]", "evidence": "", "is_frozen": 0, "timestamp": 1.0},
        {"id": "AG-b", "entry_type": "Decision", "status": "Approved",
         "topic": "car_count", "decision_what": "3台", "reason_why": "再計算",
         "citations": "[]", "evidence": "", "is_frozen": 0, "timestamp": 2.0},
    ]
    # conn=None では _find_prior_superseded による1ホップ表示へフォールバック
    out = cela_main._build_agreements_context(agreements, conn=None, run_id="")
    assert "前版 Superseded" in out, out
    assert "系譜（変遷）" not in out


# ---------------------------------------------------------------------------
# C3: task_plan_reviewer の provisional-on-provisional アンカリング検査
# ---------------------------------------------------------------------------

def test_c3_flags_provisional_on_provisional_anchoring(db_conn):
    conn, run_id = db_conn
    # 弱い祖先: provisional かつ expert_calculation のみを根拠
    _seed_fact(conn, run_id, "base_estimate", 8500, confidence="provisional",
               citations=[{"type": "expert_calculation", "detail": "仮算"}])
    # 対象: 同じく provisional、かつ base_estimate に derived_from
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional",
               citations=[{"type": "expert_calculation", "detail": "試算"}])
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:base_estimate", "derived_from", "r", "expert",
    )
    comment = cela_main._check_provisional_anchoring(conn, run_id, "car_count")
    assert comment is not None
    assert "base_estimate" in comment


def test_c3_no_flag_when_anchored_to_confirmed(db_conn):
    conn, run_id = db_conn
    # 確定済みの祖先へ依存しているならアンカリング懸念はない
    _seed_fact(conn, run_id, "base_estimate", 8500, confidence="confirmed",
               citations=[{"type": "web", "detail": "実測値"}])
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional")
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:base_estimate", "derived_from", "r", "expert",
    )
    comment = cela_main._check_provisional_anchoring(conn, run_id, "car_count")
    assert comment is None


def test_c3_no_flag_when_target_is_confirmed(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, "car_count", 4, confidence="confirmed")
    comment = cela_main._check_provisional_anchoring(conn, run_id, "car_count")
    assert comment is None


def test_c3_run_provisional_anchoring_check_returns_task_id(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, "base_estimate", 8500, confidence="provisional",
               citations=[{"type": "expert_calculation", "detail": "仮算"}])
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional",
               citations=[{"type": "expert_calculation", "detail": "試算"}])
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:base_estimate", "derived_from", "r", "expert",
    )
    phases = [{
        "phase_id": "phase_1",
        "tasks": [{"task_id": "task_1_1", "owns_variables": ["car_count"]}],
    }]
    findings = cela_main._run_provisional_anchoring_check(conn, run_id, phases)
    assert len(findings) == 1
    assert findings[0][0] == "task_1_1"
    assert "base_estimate" in findings[0][1]


def test_c3_run_provisional_anchoring_check_empty_when_anchored(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, "base_estimate", 8500, confidence="confirmed",
               citations=[{"type": "web", "detail": "実測"}])
    _seed_fact(conn, run_id, "car_count", 4, confidence="provisional")
    assert cela_main._write_relation_edge(
        conn, run_id, "fact:car_count", "fact:base_estimate", "derived_from", "r", "expert",
    )
    phases = [{
        "phase_id": "phase_1",
        "tasks": [{"task_id": "task_1_1", "owns_variables": ["car_count"]}],
    }]
    assert cela_main._run_provisional_anchoring_check(conn, run_id, phases) == []
