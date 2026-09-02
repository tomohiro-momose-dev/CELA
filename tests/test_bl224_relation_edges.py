"""
BL-224: 判断の系譜（Decision Lineage）— relation_edges の機械的骨格（W1/W2/W3/N2）と
消費経路（C2 audit、C5 trace_lineage）のオフラインDBテスト。

Phase 1 の実装範囲:
- relation_edges テーブル ＋ ユニークな単一書き込み口 `_write_relation_edge`（実在検証つき）
- 反復走査 `_traverse_lineage`（backward/forward/both、深度制限、サイクル安全）
- W1: agreement→fact の derived_from（confirmed_variables ループで機械的に）
- W2: 新版→旧版の supersedes（_commit_agreement_from_tool の SUPERSEDE/UPDATE 経路）
- W3: depends_on エッジ（死蔵していた depends_on 列の復活）
- N2: 単独 Rejected の supersedes（共有ヘルパ _link_rejected_supersession）
- C2: `_render_lineage_audit`（_audit_report --ref の系譜節）
- C5: `trace_lineage` ツール実体（N3 応答仕様: 未知プレフィックス/解決不能/解決済み）

詳細: docs/design/back_log/BL-224/BL224_basic_design.md
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
    db_path = str(tmp_path / "test_bl224.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _append_agreement(conn, run_id, id, topic, status="Approved", reason="r",
                      decision_what="dw", entry_type="Decision", task_id="task_1_1",
                      phase_id="phase_1", depends_on="[]"):
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


# ---------------------------------------------------------------------------
# 単一書き込み口 _write_relation_edge（§15.1 単一ゲート・実在検証）
# ---------------------------------------------------------------------------

def test_write_relation_edge_rejects_missing_refs(db_conn):
    conn, run_id = db_conn
    assert not cela_main._write_relation_edge(
        conn, run_id, "agreement:nope", "fact:no_such_var", "derived_from",
        "r", "expert",
    )


def test_write_relation_edge_writes_when_both_exist(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-a", "topic_a")
    cela_main.upsert_verified_fact(
        conn, run_id, "var_a", "1", unit="", source_task_id="task_1_1",
        source_phase_id="phase_1", confirmed_by="expert", confidence="confirmed",
    )
    assert cela_main._write_relation_edge(
        conn, run_id, "agreement:AG-a", "fact:var_a", "derived_from", "r", "expert",
    )
    rows = conn.execute("SELECT * FROM relation_edges WHERE run_id=?", (run_id,)).fetchall()
    assert len(rows) == 1
    assert rows[0]["from_ref"] == "agreement:AG-a"
    assert rows[0]["to_ref"] == "fact:var_a"
    assert rows[0]["relation_type"] == "derived_from"


def test_resolve_ref_table_entity(db_conn):
    conn, run_id = db_conn
    cela_main.upsert_entity_attribute(
        conn, run_id, "ent1", "attr1", "100", "m", "confirmed", [], "r",
        "task_1_1", "phase_1", "expert",
    )
    assert cela_main._resolve_ref_table(conn.execute, run_id, "entity:ent1:attr1")
    assert not cela_main._resolve_ref_table(conn.execute, run_id, "entity:ent1")  # 裸のentityは不可
    assert not cela_main._resolve_ref_table(conn.execute, run_id, "unknown:xxx")


# ---------------------------------------------------------------------------
# 反復走査 _traverse_lineage（深度・方向・サイクル安全）
# ---------------------------------------------------------------------------

def _seed_chain(conn, run_id, edges):
    """edges = [(from_ref, to_ref, rel, reason)] を直接シードする。"""
    for fr, to, rel, reason in edges:
        edge_id = cela_main._new_record_id("REL")
        conn.execute(
            "INSERT INTO relation_edges (id, run_id, from_ref, to_ref, relation_type, reason, "
            "created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
            (edge_id, run_id, fr, to, rel, reason, "expert", time.time()),
        )


def test_traverse_backward_multihop(db_conn):
    """a→b→c の derived_from 連鎖: c から後方で a,b 両方が depth 順に返る。"""
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    _append_agreement(conn, run_id, "AG-c", "t_c")
    _seed_chain(conn, run_id, [
        ("agreement:AG-a", "agreement:AG-b", "derived_from", "r1"),
        ("agreement:AG-b", "agreement:AG-c", "derived_from", "r2"),
    ])
    found = cela_main._traverse_lineage(conn, run_id, "agreement:AG-c", "backward", 10)
    refs = {(f["ref"], f["depth"]) for f in found}
    button = {(f["ref"]) for f in found if f["depth"] == 1}
    assert "agreement:AG-b" in button
    assert ("agreement:AG-a", 2) in refs


def test_traverse_forward(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    _seed_chain(conn, run_id, [("agreement:AG-a", "agreement:AG-b", "derived_from", "r")])
    found = cela_main._traverse_lineage(conn, run_id, "agreement:AG-a", "forward", 10)
    assert [f["ref"] for f in found] == ["agreement:AG-b"]


def test_traverse_depth_limit(db_conn):
    conn, run_id = db_conn
    for i in range(5):
        _append_agreement(conn, run_id, f"AG-{i}", f"t_{i}")
    _seed_chain(conn, run_id, [
        (f"agreement:AG-{i}", f"agreement:AG-{i+1}", "derived_from", "r") for i in range(4)
    ])
    found = cela_main._traverse_lineage(conn, run_id, "agreement:AG-4", "backward", 2)
    # max_depth=2: AG-3（depth1）と AG-2（depth2）まで。depth3 の AG-1 は展開されない。
    assert {f["ref"] for f in found} == {"agreement:AG-3", "agreement:AG-2"}
    assert "agreement:AG-1" not in {f["ref"] for f in found}


def test_traverse_cycle_safe(db_conn):
    """A→B, B→A の意図的サイクルでもループせず終了する。"""
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    _seed_chain(conn, run_id, [
        ("agreement:AG-a", "agreement:AG-b", "derived_from", "r"),
        ("agreement:AG-b", "agreement:AG-a", "depends_on", "r2"),
    ])
    found = cela_main._traverse_lineage(conn, run_id, "agreement:AG-a", "both", 10)
    assert len(found) >= 2  # 有限で終了（無限ループしない）


def test_get_lineage_chain_supersedes_chronological(db_conn):
    """3世代の supersedes（1→2→3）を時系列順に返す。"""
    conn, run_id = db_conn
    for i in (1, 2, 3):
        _append_agreement(conn, run_id, f"AG-{i}", f"t_{i}")
    _seed_chain(conn, run_id, [
        ("agreement:AG-1", "agreement:AG-2", "supersedes", "r1"),
        ("agreement:AG-2", "agreement:AG-3", "supersedes", "r2"),
    ])
    chain = cela_main._get_lineage_chain(conn, run_id, "agreement:AG-3", max_depth=3)
    types = {c["relation_type"] for c in chain}
    assert types == {"supersedes"}
    # 時系列順（created_at 昇順）＝ AG-1, AG-2
    refs = [c["ref"] for c in chain]
    assert refs == ["agreement:AG-1", "agreement:AG-2"]


# ---------------------------------------------------------------------------
# W2: 新版→旧版 supersedes（_commit_agreement_from_tool の SUPERSEDE 経路）
# ---------------------------------------------------------------------------

def test_commit_w2_supersede_writes_edge(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-old", "car_count", status="Approved")
    err, _ = cela_main._commit_agreement_from_tool(
        {"action_type": "SUPERSEDE", "entry_type": "Decision", "topic": "car_count",
         "target_topic": "car_count", "decision_what": "new", "reason_why": "旧案を棄却",
         "status": "Approved",
         "depends_on": [], "resource_claims": {}, "citations": []},
        conn, run_id, "expert", "task_1_1", "phase_1",
    )
    assert err is None
    rows = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='supersedes'",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["from_ref"] == "agreement:AG-old"
    assert rows[0]["to_ref"].startswith("agreement:AG-")
    assert rows[0]["reason"] == "旧案を棄却"


# ---------------------------------------------------------------------------
# W3: depends_on エッジ（死蔵していた列の復活）
# ---------------------------------------------------------------------------

def test_commit_w3_depends_on_edge(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-base", "budget_cap")
    err, _ = cela_main._commit_agreement_from_tool(
        {"action_type": "CREATE", "entry_type": "Decision", "topic": "vehicle_count",
         "decision_what": "4", "reason_why": "r", "status": "Approved",
         "depends_on": ["AG-base"], "resource_claims": {}, "citations": []},
        conn, run_id, "expert", "task_1_1", "phase_1",
    )
    assert err is None
    rows = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='depends_on'",
        (run_id,),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["from_ref"] == "agreement:AG-base"
    assert rows[0]["to_ref"].startswith("agreement:AG-")


# ---------------------------------------------------------------------------
# N2: 単独 Rejected の supersedes（共有ヘルパが両経路で同一挙動）
# ---------------------------------------------------------------------------

def test_link_rejected_supersession_no_active_y_returns_false(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-x", "solo_topic", status="Rejected")
    assert not cela_main._link_rejected_supersession(conn, run_id, "AG-x", "solo_topic", "expert")
    assert conn.execute("SELECT COUNT(*) FROM relation_edges WHERE run_id=?", (run_id,)).fetchone()[0] == 0


def test_link_rejected_supersession_links_to_active_y(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-y", "budget", status="Approved")
    _append_agreement(conn, run_id, "AG-x", "budget", status="Rejected")  # 敗者のX
    assert cela_main._link_rejected_supersession(conn, run_id, "AG-x", "budget", "expert")
    row = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='supersedes'",
        (run_id,),
    ).fetchall()[0]
    assert row["from_ref"] == "agreement:AG-x"
    assert row["to_ref"] == "agreement:AG-y"


def test_commit_n2_rejected_writes_supersedes_edge(db_conn):
    """_commit_agreement_from_tool 経由の単独 Rejected でも同トピックの現行Yへ supersedes を張る。"""
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-y", "budget", status="Approved")
    err, _ = cela_main._commit_agreement_from_tool(
        {"action_type": "CREATE", "entry_type": "Decision", "topic": "budget",
         "decision_what": "却下案", "reason_why": "r", "status": "Rejected",
         "depends_on": [], "resource_claims": {}, "citations": []},
        conn, run_id, "expert", "task_1_1", "phase_1",
    )
    assert err is None
    new_id = cela_main._LAST_NEW_AGREEMENT_ID
    row = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='supersedes'",
        (run_id,),
    ).fetchall()[0]
    assert row["from_ref"] == f"agreement:{new_id}"
    assert row["to_ref"] == "agreement:AG-y"


# ---------------------------------------------------------------------------
# W1: agreement→fact derived_from（_write_agreement_impl の confirmed_variables ループ）
# ---------------------------------------------------------------------------

def test_write_agreement_impl_w1_derived_from_edge(db_conn):
    conn, run_id = db_conn
    res = cela_main._write_agreement_impl(
        # status='Proposed'（expertが直接書ける権限。W1 の confirmed_variables ループは
        # status と無関係に走り、agreement→fact の derived_from エッジを張る）。
        {"action_type": "CREATE", "status": "Proposed", "topic": "car_decision",
         "decision_what": "車両台数を4台とする", "reason_why": "予算から算出", "entry_type": "Decision",
         "confirmed_variables": [
             {"variable_name": "car_count", "value": "4", "unit": "台", "confidence": "confirmed"},
         ],
         "depends_on": [], "resource_claims": {}},
        conn, run_id, "expert", "task_1_1", phase_id="phase_1",
    )
    assert res.get("success") is True
    new_id = cela_main._LAST_NEW_AGREEMENT_ID
    row = conn.execute(
        "SELECT * FROM relation_edges WHERE run_id=? AND relation_type='derived_from'",
        (run_id,),
    ).fetchall()[0]
    assert row["from_ref"] == f"agreement:{new_id}"
    assert row["to_ref"] == "fact:car_count"


# ---------------------------------------------------------------------------
# C2: _render_lineage_audit（_audit_report --ref の系譜節）
# ---------------------------------------------------------------------------

def test_render_lineage_audit_includes_backward_and_forward(db_conn):
    conn, run_id = db_conn
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    _append_agreement(conn, run_id, "AG-c", "t_c")
    _seed_chain(conn, run_id, [
        ("agreement:AG-a", "agreement:AG-b", "derived_from", "前提A"),
        ("agreement:AG-b", "agreement:AG-c", "derived_from", "導出C"),
    ])
    out = cela_main._render_lineage_audit(conn, run_id, "agreement:AG-b")
    assert "系譜（lineage）" in out
    assert "agreement:AG-b" in out
    # backward に AG-a、forward に AG-c
    assert "agreement:AG-a" in out
    assert "agreement:AG-c" in out


# ---------------------------------------------------------------------------
# C5: trace_lineage ツール実体（globals を差し替えて実ハンドラを通す）
# ---------------------------------------------------------------------------

@pytest.fixture()
def active_handler_ctx(db_conn):
    conn, run_id = db_conn
    old_conn, old_run = cela_main._DB_CONN, cela_main._CURRENT_RUN_ID
    cela_main._DB_CONN, cela_main._CURRENT_RUN_ID = conn, run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN, cela_main._CURRENT_RUN_ID = old_conn, old_run


def test_trace_lineage_handler_unknown_prefix(active_handler_ctx):
    _, _ = active_handler_ctx
    # [BL-331] "task:"はBL-331でtasks実表を導入した既知プレフィックスになったため、
    # 本テストの意図（未知プレフィックス）を保つには別の未知プレフィックスを使う。
    res = cela_main._trace_lineage_handler({"ref": "bogus_prefix:xxx"})
    assert res["status"] == "ok"
    assert res["lineage"] == []


def test_trace_lineage_handler_unresolved_ref(active_handler_ctx):
    conn, run_id = active_handler_ctx
    _append_agreement(conn, run_id, "AG-a", "t_a")
    res = cela_main._trace_lineage_handler({"ref": "agreement:not_in_run"})
    assert res["status"] == "ok"
    assert res["lineage"] == []
    assert "run 内に該当 ref はありません" in res["result"]


def test_trace_lineage_handler_resolved_with_lineage(active_handler_ctx):
    conn, run_id = active_handler_ctx
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    _seed_chain(conn, run_id, [("agreement:AG-a", "agreement:AG-b", "derived_from", "r")])
    res = cela_main._trace_lineage_handler({"ref": "agreement:AG-b", "direction": "backward"})
    assert res["status"] == "ok"
    assert len(res["lineage"]) == 1
    assert res["lineage"][0]["ref"] == "agreement:AG-a"
    assert res["lineage"][0]["relation_type"] == "derived_from"
