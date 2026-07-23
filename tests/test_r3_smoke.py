"""
R3 (R3a: 自律的DB/ファイル読み取り、R3b: 自律的DB書き込み) 完了条件のうち、
実LLM API呼び出しを伴わないオフライン検証項目。

参照: docs/design/r1_r2_r3b_core/cela_r3_impl_Plan.md §2.8 (R3a完了条件)、
      §3.7 (R3b完了条件)。

実LLMドライランが必要な項目（R3a-T8、R3b-T8〜T10。指標C/A/E/Fの実測）は
本ファイルの対象外 — ドライラン実施後にtraceability.md T-*として別途記録する。
"""

import json
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    """R1のSQLite基盤（module-levelシングルトン）をテスト用一時DBで初期化する。
    R3aの_CURRENT_RUN_IDもここでセット・後始末する。"""
    db_path = str(tmp_path / "test_r3.db")
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


# ===========================================================================
# R3a: 自律的DB/ファイル読み取り（F-3.8/F-3.9）
# ===========================================================================

def test_r3a_t1_verified_facts_schema_has_r3a_columns(db_conn):
    """R3a-T1: verified_factsにreason/citations/confidence列が追加されていること。"""
    conn, _ = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(verified_facts)").fetchall()}
    assert {"reason", "citations", "confidence"} <= cols


def test_r3a_t2_upsert_verified_fact_stores_reason_citations_confidence(db_conn):
    """R3a-T2: upsert_verified_factがreason/citations/confidence（provisional含む）を保存すること。"""
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "vehicle_count", 3, unit="台",
        source_task_id="task_2_1", source_phase_id="phase_2", confirmed_by="expert",
        reason="暫定値として進めた", citations=["task_2_1"], confidence="provisional",
    )
    rows = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["vehicle_count"])
    assert len(rows) == 1
    assert rows[0]["confidence"] == "provisional"
    assert json.loads(rows[0]["citations"]) == ["task_2_1"]
    assert rows[0]["reason"] == "暫定値として進めた"

    # [BL-041] デフォルト（confidence未指定）はprovisional。呼び出し元が明示的に
    # confidence="confirmed"を判断しない限り、安全側（暫定扱い）に倒す方針に変更。
    cela_main.upsert_verified_fact(
        conn, run_id, "budget_cap", 30000000, unit="円",
        source_task_id="task_1_3", source_phase_id="phase_1", confirmed_by="user",
    )
    rows2 = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["budget_cap"])
    assert rows2[0]["confidence"] == "provisional"


def test_r3a_t3_get_verified_facts_from_db_topic_and_all(db_conn):
    """R3a-T3: get_verified_facts_from_dbのtopic検索・全件検索が機能すること。"""
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "vehicle_count", 3, unit="台",
        source_task_id="task_2_1", source_phase_id="phase_2", confirmed_by="expert",
    )
    by_name = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["vehicle_count"])
    assert len(by_name) == 1

    by_topic = cela_main.get_verified_facts_from_db(conn, run_id, topic="vehicle")
    assert len(by_topic) == 1

    all_rows = cela_main.get_verified_facts_from_db(conn, run_id)
    assert len(all_rows) == 1

    none_found = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["nonexistent"])
    assert none_found == []


def test_bl053_get_verified_facts_topic_search_matches_japanese_reason(db_conn):
    """BL-053: topic_keywordはAIが渡す日本語の説明的キーワード（例:「予算」）がほとんどだが、
    variable_nameは英語スネークケース識別子のため、reason列（日本語理由文）も検索対象に
    含めないと構造的にほぼ一致しない（実ドライランでnot_found率41%を確認）。"""
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "annual_deficit", -704, unit="万円/年",
        source_task_id="task_1_1", source_phase_id="phase_1", confirmed_by="expert",
        reason="年間運営費1,696万円から運賃収入2,400万円を引いた実質赤字額（予算上限3,000万円以内）",
    )
    by_japanese_topic = cela_main.get_verified_facts_from_db(conn, run_id, topic="予算")
    assert len(by_japanese_topic) == 1
    assert by_japanese_topic[0]["variable_name"] == "annual_deficit"


def test_r3a_t3b_read_verified_fact_tool_via_dispatch(db_conn):
    """R3a-T3: read_verified_factツール（TOOL_DISPATCH経由）がフェーズ横断の確定値を返すこと。
    R3b-T11（二重JSONエンコード回帰確認）も兼ねる: 戻り値は生のdict/listであること。
    """
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "vehicle_count", 3, unit="台",
        source_task_id="task_2_1", source_phase_id="phase_2", confirmed_by="expert",
    )
    found = cela_main.TOOL_DISPATCH["read_verified_fact"]({"variable_name": "vehicle_count"})
    assert isinstance(found, list), "二重JSONエンコード回帰: json.dumps済み文字列ではなく生listを返すべき"
    assert found[0]["value"] == "3"
    # 1回のjson.dumpsで正しくLLM向けcontentへ変換できること
    restored = json.loads(json.dumps(found, ensure_ascii=False))
    assert restored[0]["value"] == "3"

    not_found = cela_main.TOOL_DISPATCH["read_verified_fact"]({"variable_name": "nonexistent"})
    assert isinstance(not_found, dict), "二重JSONエンコード回帰: json.dumps済み文字列ではなく生dictを返すべき"
    assert not_found["status"] == "not_found"


def test_r3a_t4_read_deliverable_file_path_validation():
    """R3a-T4: read_deliverable_fileがlog/配下は読める・トラバーサル/範囲外は拒否すること
    （Windows実パス、log/外、`..`の3パターン）。"""
    test_dir = os.path.join("log", "_test_r3a_t4")
    os.makedirs(test_dir, exist_ok=True)
    legit_path = os.path.join(test_dir, "sample.md")
    with open(legit_path, "w", encoding="utf-8") as f:
        f.write("hello r3a")
    try:
        ok = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"file_path": legit_path})
        assert ok == "hello r3a"

        traversal = cela_main.TOOL_DISPATCH["read_deliverable_file"]({
            "file_path": os.path.join(test_dir, "..", "..", "cela_main.py")
        })
        assert isinstance(traversal, dict) and traversal["status"] == "error"

        outside = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"file_path": "requirements-dev.txt"})
        assert isinstance(outside, dict) and outside["status"] == "error"

        missing = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"file_path": os.path.join(test_dir, "nope.md")})
        assert isinstance(missing, dict) and missing["status"] == "not_found"
    finally:
        os.remove(legit_path)
        os.rmdir(test_dir)


def test_r3a_t5_build_task_scope_context_scans_all_phases(db_conn):
    """R3a-T5（BL-035）: _build_task_scope_contextがcurrent_phaseだけでなく
    state["phases"]全体を走査し、フェーズ横断のdepends_onを解決できること。"""
    conn, run_id = db_conn
    cela_main.upsert_verified_fact(
        conn, run_id, "vehicle_count", 3, unit="台",
        source_task_id="task_2_1", source_phase_id="phase_2", confirmed_by="expert",
    )
    task_6_3 = {"task_id": "task_6_3", "depends_on": ["task_2_1"], "acceptance_criteria": []}
    state = {
        "run_id": run_id,
        "current_phase": {"phase_id": "phase_6", "tasks": [task_6_3]},
        "current_task_id": "task_6_3",
        "task_criteria_status": {},
        "phases": [
            {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1", "owns_variables": ["vehicle_count"]}]},
            {"phase_id": "phase_6", "tasks": [task_6_3]},
        ],
    }
    ctx = cela_main._build_task_scope_context(state, conn)
    assert "vehicle_count" in ctx["verified_facts_json"]
    assert '"3"' in ctx["verified_facts_json"]


def test_r3a_t6_integrator_and_arbiter_have_read_and_write_tools():
    """R3a-T6/R3b（レビュー指摘、非対称付与の解消確認）: Integrator・Resource Arbiterの
    両方に読み取りツール（F-3.8）と書き込みツール（F-3.1）が付与されていること。"""
    import inspect
    for fn, name in [(cela_main.call_integrator, "call_integrator"),
                      (cela_main.call_resource_arbiter, "call_resource_arbiter")]:
        src = inspect.getsource(fn)
        assert "READ_VERIFIED_FACT_TOOL" in src, f"{name} に読み取りツールが付与されていません"
        assert "READ_DELIVERABLE_FILE_TOOL" in src, f"{name} に読み取りツールが付与されていません"
        assert "WRITE_AGREEMENT_TOOL" in src, f"{name} に書き込みツールが付与されていません"


def test_r3a_t7_dispatch_passes_full_args_dict_not_code_string():
    """R3a-T7（致命的①の回帰確認）: TOOL_DISPATCHのハンドラがargs辞書全体を受け取る
    形になっており、_query_AI_liveが `handler(args)` を呼んでいること
    （旧: `handler(args.get("code", ""))` ではないこと）。"""
    import inspect
    src = inspect.getsource(cela_main._query_AI_live)
    assert "result = handler(args)" in src, (
        "ディスパッチが handler(args) を呼んでいません（致命的①の回帰）"
    )
    assert 'result = handler(args.get("code", ""))' not in src, (
        "ディスパッチが handler(args.get(\"code\", \"\")) に戻っています（致命的①の回帰）"
    )


# ===========================================================================
# R3b: 自律的DB書き込みへの移行（F-3.1〜F-3.7）
# ===========================================================================

def test_r3b_t1_write_agreement_registered():
    """R3b-T1: write_agreementツールがTOOL_DISPATCHに登録されていること。"""
    assert "write_agreement" in cela_main.TOOL_DISPATCH


@pytest.mark.parametrize("status", ["Proposed"])
def test_r3b_t2_expert_can_write_proposed(db_conn, status):
    """R3b-T2: Expertはstatus='Proposed'のみ書き込めること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": status, "topic": "t1",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert result["success"] is True


@pytest.mark.parametrize("status", ["Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"])
def test_r3b_t2_expert_cannot_write_other_statuses(db_conn, status):
    """R3b-T2: Expertは Proposed 以外の全statusで拒否されること。"""
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": status, "topic": "t2",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert result["success"] is False


@pytest.mark.parametrize("role", ["detector", "reviewer", "arbiter", "integrator"])
@pytest.mark.parametrize("status", ["Proposed", "Approved", "Approved_with_Conditions", "Implicitly_Accepted"])
def test_r3b_t3_escalation_roles_cannot_write_non_rejected(db_conn, role, status):
    """R3b-T3: Detector/Reviewer/Arbiter/Integratorは Rejected 以外の全statusで拒否されること。"""
    cela_main._CURRENT_CALLER_ROLE = role
    cela_main._CURRENT_TASK_ID = ""
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": status, "topic": f"t3-{role}-{status}",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert result["success"] is False


@pytest.mark.parametrize("role", ["detector", "reviewer", "arbiter", "integrator"])
def test_r3b_t3_escalation_roles_can_write_rejected(db_conn, role):
    """R3b-T3: Detector/Reviewer/Arbiter/Integratorは Rejected を書き込めること。"""
    cela_main._CURRENT_CALLER_ROLE = role
    cela_main._CURRENT_TASK_ID = ""
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Rejected", "topic": f"t3-ok-{role}",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert result["success"] is True


@pytest.mark.parametrize("status", ["Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"])
def test_r3b_t4_user_ai_can_write_all_statuses(db_conn, status):
    """R3b-T4: User AIは全statusを書き込めること。"""
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = "task_x"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": status, "topic": f"t4-{status}",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert result["success"] is True


def test_r3b_t5_decision_extractor_skips_agreement_write_when_write_agreement_succeeded(db_conn, monkeypatch):
    """R3b-T5（致命的②の回帰確認）: write_agreementが今ターン成功していた場合、
    decision_extractor_nodeはAgreement書き込みをスキップするが、
    owned_variable_values→verified_factsは無条件で毎ターン実行されること。"""
    conn, run_id = db_conn

    canned_items = [{
        "action_type": "CREATE", "entry_type": "Decision", "status": "Proposed",
        "topic": "スキップされるべきトピック", "content": "本文", "rationale": "理由",
        "proposed_by": "expert", "owned_variable_values": {"vehicle_count": 3},
    }]
    monkeypatch.setattr(cela_main, "call_decision_extractor", lambda *a, **k: (canned_items, {}))

    state = {
        "run_id": run_id, "turn_count": 1,
        "chat_history": [{"role": "assistant", "content": "expertの発言"}],
        "current_phase": {"phase_id": "phase_2", "tasks": [
            {"task_id": "task_2_1", "owns_variables": ["vehicle_count"], "acceptance_criteria": []}
        ]},
        "current_task_id": "task_2_1",
        "phases": [{"phase_id": "phase_2", "tasks": [
            {"task_id": "task_2_1", "owns_variables": ["vehicle_count"], "acceptance_criteria": []}
        ]}],
        "expert_wrote_agreement": True,  # ★今ターンwrite_agreementが成功済み
    }
    cela_main.decision_extractor_node(state)

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    assert not any(a["topic"] == "スキップされるべきトピック" for a in agreements), (
        "write_agreement成功ターンなのにdecision_extractorがAgreementを二重書き込みした"
    )
    facts = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["vehicle_count"])
    assert len(facts) == 1 and facts[0]["value"] == "3", (
        "verified_facts抽出はwrite_agreement呼び出し有無に関わらず無条件で実行されるべき"
    )


def test_r3b_t5b_decision_extractor_writes_agreement_when_write_agreement_not_called(db_conn, monkeypatch):
    """R3b-T5対比: write_agreementが今ターン呼ばれていない場合は、
    decision_extractor_nodeが従来通りAgreementを書き込むこと（セーフティネット機能の維持）。"""
    conn, run_id = db_conn

    canned_items = [{
        "action_type": "CREATE", "entry_type": "Decision", "status": "Proposed",
        "topic": "書き込まれるべきトピック", "content": "本文", "rationale": "理由",
        "proposed_by": "expert", "owned_variable_values": {},
    }]
    monkeypatch.setattr(cela_main, "call_decision_extractor", lambda *a, **k: (canned_items, {}))

    state = {
        "run_id": run_id, "turn_count": 1,
        "chat_history": [{"role": "assistant", "content": "expertの発言"}],
        "current_phase": {"phase_id": "phase_2", "tasks": [
            {"task_id": "task_2_1", "owns_variables": [], "acceptance_criteria": []}
        ]},
        "current_task_id": "task_2_1",
        "phases": [{"phase_id": "phase_2", "tasks": [
            {"task_id": "task_2_1", "owns_variables": [], "acceptance_criteria": []}
        ]}],
        "expert_wrote_agreement": False,  # ★今ターンwrite_agreementは呼ばれていない
    }
    cela_main.decision_extractor_node(state)

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    assert any(a["topic"] == "書き込まれるべきトピック" for a in agreements), (
        "write_agreement未呼び出しターンでdecision_extractorのセーフティネットが機能していない"
    )


def test_r3b_t6_confirmed_variables_reflected_to_verified_facts(db_conn):
    """R3b-T6: write_agreementのconfirmed_variables（confidence='provisional'含む）が
    verified_factsへ正しく反映されること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_2_1"

    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "車両台数の確定",
        "decision_what": "車両台数は3台とする", "reason_why": "暫定値として進めた",
        "entry_type": "Decision", "phase_id": "phase_2",
        "confirmed_variables": [
            {"variable_name": "vehicle_count", "value": "3", "unit": "台", "confidence": "provisional"}
        ],
    })
    assert result["success"] is True

    facts = cela_main.get_verified_facts_from_db(conn, run_id, variable_names=["vehicle_count"])
    assert len(facts) == 1
    assert facts[0]["value"] == "3"
    assert facts[0]["confidence"] == "provisional"
    assert facts[0]["reason"] == "暫定値として進めた"
    assert facts[0]["source_task_id"] == "task_2_1"


def test_r3b_t7_depends_on_ids_visible_in_agreements_context(db_conn):
    """R3b-T7（中程度⑤の回帰確認）: _build_agreements_contextの出力にagreements.idが
    含まれ、LLMがdepends_onへ指定できるIDを実際に読み取れること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_TASK_ID = ""
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "予算上限",
        "decision_what": "上限3000万円", "reason_why": "承認済み", "entry_type": "Decision",
    })
    agreements = cela_main.get_agreements_from_db(conn, run_id)
    assert len(agreements) == 1
    ctx = cela_main._build_agreements_context(agreements)
    assert f"[{agreements[0]['id']}]" in ctx, "agreements.idがコンテキスト本文に露出していない"

    # このIDをdepends_onに指定すればwrite_agreementの整合性チェックを通ることを確認
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "予算に依存するタスク",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
        "depends_on": [agreements[0]["id"]],
    })
    assert result["success"] is True

    bad_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "存在しないIDに依存",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
        "depends_on": ["AG-nonexistent"],
    })
    assert bad_result["success"] is False


def test_r3b_t11_write_agreement_result_not_double_encoded(db_conn):
    """R3b-T11（H1の回帰確認）: write_agreementの戻り値が生dictであり、
    json.dumps一回だけでLLM向けcontentへ変換できること（二重エンコードされないこと）。"""
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "t11",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    assert isinstance(result, dict), "write_agreementはjson.dumps済み文字列ではなく生dictを返すべき"
    tool_message_content = json.dumps(result, ensure_ascii=False)
    restored = json.loads(tool_message_content)
    assert isinstance(restored, dict) and restored["success"] is True


def test_r3b_t12_deliverable_create_via_write_agreement_saves_file(db_conn):
    """R3b-T12（H2の回帰確認、R4でホワイトボード方式に移行）: write_agreementで
    entry_type='Deliverable'・200文字超のdecision_whatを送信した際、whiteboard_draftsに
    Ver.1として保存され、agreements.decision_whatがWHITEBOARD:で始まること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"

    long_content = "X" * 500
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R3bテスト成果物T12",
        "decision_what": long_content, "reason_why": "r", "entry_type": "Deliverable",
        "phase_id": "phase_1",
    })
    assert result["success"] is True

    rows = conn.execute(
        "SELECT decision_what FROM agreements WHERE topic=? AND run_id=?",
        ("R3bテスト成果物T12", run_id),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["decision_what"] == "WHITEBOARD:phase_1:task_x"

    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_x")
    assert wb is not None and wb["version"] == 1 and wb["content"] == long_content


def test_r3b_t13_deliverable_update_protects_existing_file_path(db_conn):
    """R3b-T13（H2の回帰確認、R4でホワイトボード方式に移行）: write_agreementによる
    DeliverableのUPDATEで、editsも200文字超のdecision_whatもない（実質的に変更なしの）
    更新では新バージョンを作らず既存バージョンを維持すること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_x"

    create_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R3bテスト成果物T13",
        "decision_what": "Y" * 500, "reason_why": "r", "entry_type": "Deliverable",
        "phase_id": "phase_1",
    })
    assert create_result["success"] is True

    update_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Proposed", "topic": "R3bテスト成果物T13",
        "target_topic": "R3bテスト成果物T13", "phase_id": "phase_1",
        "decision_what": "軽微な修正のみです", "reason_why": "r", "entry_type": "Deliverable",
    })
    assert update_result["success"] is True

    rows = conn.execute(
        "SELECT decision_what FROM agreements WHERE topic=? AND run_id=? AND status != 'Superseded'",
        ("R3bテスト成果物T13", run_id),
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["decision_what"] == "WHITEBOARD:phase_1:task_x", (
        "短い要約による更新が既存のWHITEBOARDポインタを上書きしてしまった（保護ロジックの回帰）"
    )
    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_x")
    assert wb is not None and wb["version"] == 1, "実質的な変更がないのに新バージョンが作られてしまった"


# ===========================================================================
# BL-039: decision_extractorが出力するtask_idの表記ゆれ（ドット vs アンダースコア）
# ===========================================================================

def test_bl039_task_transition_normalizes_dot_notation_task_id():
    """BL-039: LLMがadvances_to_task_idを`task_1.1`のようなドット表記で返しても、
    task_planner確定済みのアンダースコア表記（`task_1_1`）に正規化して遷移が成立すること。
    修正前は単純一致比較のみで、この表記ゆれにより全ての遷移要求が拒否されていた。"""
    phase_1 = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]}
    state = {"phases": [phase_1], "current_phase": phase_1, "current_task_id": "task_1_1"}

    cela_main._resolve_task_transition(state, {"advances_to_phase_id": None, "advances_to_task_id": "task_1.2"})

    assert state["current_task_id"] == "task_1_2", (
        "ドット表記のtask_idが正規化されず、current_task_idが更新されなかった"
    )


def test_bl039_task_transition_still_rejects_truly_unknown_task_id():
    """BL-039の正規化がフェイルクローズを弱めていないこと（存在しないIDは正規化後も拒否）。"""
    phase_1 = {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}
    state = {"phases": [phase_1], "current_phase": phase_1, "current_task_id": "task_1_1"}

    cela_main._resolve_task_transition(state, {"advances_to_phase_id": None, "advances_to_task_id": "task_9.9"})

    assert state["current_task_id"] == "task_1_1", "存在しないtask_idへの遷移が誤って受理されてしまった"


# ===========================================================================
# BL-040: read_deliverable_fileがfile_path直接指定に依存し発見不能だった問題
# ===========================================================================

def test_bl040_read_deliverable_file_lookup_by_task_id(db_conn):
    """BL-040: read_deliverable_fileにtask_idを渡すだけで、AIがタイムスタンプ付き
    ファイル名を予測しなくても、agreements DBのFILE_PATHポインタから実ファイルを
    逆引きして読めること（実ドライランで31回中21回not_foundになっていた問題の修正）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"

    before = set(os.listdir("log/deliverables")) if os.path.isdir("log/deliverables") else set()
    try:
        create_result = cela_main.TOOL_DISPATCH["write_agreement"]({
            "action_type": "CREATE", "status": "Proposed", "topic": "BL040テスト成果物",
            "decision_what": "Z" * 500, "reason_why": "r", "entry_type": "Deliverable",
        })
        assert create_result["success"] is True

        by_task_id = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"task_id": "task_1_1"})
        assert isinstance(by_task_id, str) and by_task_id.startswith("Z" * 10)

        by_topic = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"topic_keyword": "BL040"})
        assert isinstance(by_topic, str) and by_topic.startswith("Z" * 10)

        not_found = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"task_id": "task_nonexistent"})
        assert isinstance(not_found, dict) and not_found["status"] == "not_found"
    finally:
        after = set(os.listdir("log/deliverables")) if os.path.isdir("log/deliverables") else set()
        for fn in after - before:
            os.remove(os.path.join("log", "deliverables", fn))


def test_bl040_deliverable_filenames_are_versioned_and_old_versions_archived():
    """BL-040: save_deliverable_to_fileがタイムスタンプではなく`_V{n}`の予測可能な連番を
    使うこと、および`_archive_old_deliverable_file`で旧版がdeliverables/old/へ退避される
    こと（古いディレクトリに旧版が積み上がらないこと）を確認する。
    ★R4以降、write_agreement経由のper-task Deliverableはwhiteboard_draftsへ移行したため、
    この2関数は現在integrator_nodeの最終統合文書（1回限り、版管理は不要）専用だが、
    ファイル名採番・退避ロジック自体の回帰は本テストで直接確認する。"""
    old_dir = os.path.join("log", "deliverables", "old")
    before = set(os.listdir("log/deliverables")) if os.path.isdir("log/deliverables") else set()
    before_old = set(os.listdir(old_dir)) if os.path.isdir(old_dir) else set()
    try:
        v1_path = cela_main.save_deliverable_to_file("BL040バージョニングテスト", "A" * 500)
        assert v1_path.endswith("_V1.md"), f"初回保存はV1になるはず: {v1_path}"
        assert "1784" not in v1_path, "ファイル名がタイムスタンプ形式のままになっている"

        cela_main._archive_old_deliverable_file(v1_path)
        assert not os.path.exists(v1_path), "旧版(V1)がdeliverables直下に残ったままになっている"
        assert os.path.isfile(os.path.join(old_dir, os.path.basename(v1_path))), (
            "旧版(V1)がdeliverables/old/へ退避されていない"
        )

        v2_path = cela_main.save_deliverable_to_file("BL040バージョニングテスト", "B" * 500)
        assert v2_path.endswith("_V2.md"), f"次の保存はV2になるはず（old/内の旧版も採番に考慮する）: {v2_path}"
    finally:
        after = set(os.listdir("log/deliverables")) if os.path.isdir("log/deliverables") else set()
        for fn in after - before:
            if fn != "old":
                os.remove(os.path.join("log", "deliverables", fn))
        after_old = set(os.listdir(old_dir)) if os.path.isdir(old_dir) else set()
        for fn in after_old - before_old:
            os.remove(os.path.join(old_dir, fn))
