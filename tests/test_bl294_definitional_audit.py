"""
BL-294: confirmed_variables/entity属性の「定義監査」機構。

`log/2026-08-28/1023`の生成崩壊（Expertが単一の生成ターン内で35分超・同一の数値矛盾を
堂々巡り）を根本原因まで遡ったところ、`log/2026-08-27/2345`（task_planner iter=26）で
`nagano_license_surrender_rate_75plus=78.3%`をconfidence="confirmed"として誤登録したことが
発端だった。出典記事の78.3%は実際には「長野県の自主返納者全体のうち75歳以上が占める構成比」
であり、task_plannerが変数名に込めた意味（返納率）とは別の統計だった。この誤登録がtask_1_1の
description/acceptance_criteriaへ複数回埋め込まれ、以降の全てのtask_1_1再実行がこの偽の
"確定値"を前提として引きずり続け、Expertが発見する一次データとの矛盾を解決できず堂々巡りに
陥っていた。

対応は3点: ①task_planner/WRITE_AGREEMENT_TOOLへ「検索意図と出典の実際の定義が一致するか」の
自己確認を追加、②task_plan_reviewer（初回計画レビュー）に定義監査の観点を追加、③タスク遂行中
にExpert/User AIが既存値へ疑義を持ちDB更新した場合、直後のDetectorがその差分（audited_by IS
NULL）を機械的に検知して監査し、mark_fact_auditedで記録する。verified_facts/entity_attributes
へaudited_by/audited_at列を追加し（既存のconfirmed_by/confirmed_atと対称）、値が実際に変わった
場合のみUPSERT文のCASE式でNULLへリセットする（BL-224/168のreason欄マーカー方式は「監査されたら
解消される」消費型の状態管理に合わないため不採用）。

参照: docs/design/back_log/BL-294/BL294_basic_design.md、BL-224、BL-266、BL-292。
実LLM API呼び出しは伴わない（query_AIはモンキーパッチまたは未使用）。
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
    db_path = str(tmp_path / "test_bl294.db")
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


def _seed_fact(conn, run_id, variable_name="nagano_license_surrender_rate_75plus",
               value="78.3", confirmed_by="task_planner", task_id="task_1_1"):
    cela_main.upsert_verified_fact(
        conn, run_id, variable_name, value, "%", task_id, "phase_1", confirmed_by,
        reason="", citations=[{"type": "web", "detail": "kashikapedia"}], confidence="confirmed",
    )


def _seed_entity_and_attribute(conn, run_id, entity_id_name="蓼科高原", attr_name="elevation",
                                value="1150", confirmed_by="task_planner", task_id="task_1_1"):
    entity_id = cela_main.register_entity_in_db(
        conn, run_id, entity_id_name, "place", origin="goal_text", created_by="entity_registrar",
    )
    cela_main.upsert_entity_attribute(
        conn, run_id, entity_id, attr_name, value, "m", "confirmed",
        [{"type": "web", "detail": "wikipedia"}], "", task_id, "phase_1", confirmed_by,
    )
    return entity_id


def _make_state(run_id, task_id="task_1_1", owns_variables=None, depends_on=None, phases=None):
    current_task = {
        "task_id": task_id,
        "owns_variables": owns_variables or [],
        "depends_on": depends_on or [],
    }
    return {
        "run_id": run_id,
        "current_task_id": task_id,
        "current_phase": {"phase_id": "phase_1", "tasks": [current_task]},
        "phases": phases if phases is not None else [{"phase_id": "phase_1", "tasks": [current_task]}],
    }


# ---------------------------------------------------------------------------
# 1. スキーマ移行
# ---------------------------------------------------------------------------

def test_audited_columns_exist_on_verified_facts(db_conn):
    conn, _ = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(verified_facts)").fetchall()}
    assert "audited_by" in cols
    assert "audited_at" in cols


def test_audited_columns_exist_on_entity_attributes(db_conn):
    conn, _ = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(entity_attributes)").fetchall()}
    assert "audited_by" in cols
    assert "audited_at" in cols


def test_ensure_audited_columns_idempotent(db_conn):
    """2回呼んでもエラーにならない（PRAGMA table_infoガードが機能している）。"""
    conn, _ = db_conn
    cela_main._ensure_audited_columns(conn)
    cela_main._ensure_audited_columns(conn)


def test_new_fact_starts_unaudited(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id)
    row = conn.execute(
        "SELECT audited_by, audited_at FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "nagano_license_surrender_rate_75plus"),
    ).fetchone()
    assert row["audited_by"] is None
    assert row["audited_at"] is None


# ---------------------------------------------------------------------------
# 2. upsert_verified_fact / upsert_entity_attribute のCASE式（監査状態リセット）
# ---------------------------------------------------------------------------

def test_upsert_verified_fact_value_change_resets_audit_status(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, value="78.3")
    conn.execute(
        "UPDATE verified_facts SET audited_by=?, audited_at=? WHERE run_id=? AND variable_name=?",
        ("task_plan_reviewer", time.time(), run_id, "nagano_license_surrender_rate_75plus"),
    )
    conn.commit()

    # Expertが疑義を持ち、値を訂正して再登録（値が実際に変わる）。
    _seed_fact(conn, run_id, value="32.1", confirmed_by="expert")

    row = conn.execute(
        "SELECT value, audited_by, audited_at FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "nagano_license_surrender_rate_75plus"),
    ).fetchone()
    assert row["value"] == "32.1"
    assert row["audited_by"] is None
    assert row["audited_at"] is None


def test_upsert_verified_fact_same_value_preserves_audit_status(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, value="78.3")
    conn.execute(
        "UPDATE verified_facts SET audited_by=?, audited_at=? WHERE run_id=? AND variable_name=?",
        ("task_plan_reviewer", 12345.0, run_id, "nagano_license_surrender_rate_75plus"),
    )
    conn.commit()

    # 同じ値を再登録（単なる再確認、値は変わらない）。
    _seed_fact(conn, run_id, value="78.3", confirmed_by="task_planner")

    row = conn.execute(
        "SELECT audited_by, audited_at FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "nagano_license_surrender_rate_75plus"),
    ).fetchone()
    assert row["audited_by"] == "task_plan_reviewer"
    assert row["audited_at"] == 12345.0


def test_upsert_entity_attribute_value_change_resets_audit_status(db_conn):
    conn, run_id = db_conn
    entity_id = _seed_entity_and_attribute(conn, run_id, value="1150")
    conn.execute(
        "UPDATE entity_attributes SET audited_by=?, audited_at=? WHERE run_id=? AND entity_id=? AND attr_name=?",
        ("detector", time.time(), run_id, entity_id, "elevation"),
    )
    conn.commit()

    cela_main.upsert_entity_attribute(
        conn, run_id, entity_id, "elevation", "1200", "m", "confirmed",
        [{"type": "web", "detail": "corrected"}], "", "task_1_1", "phase_1", "detector",
    )

    row = conn.execute(
        "SELECT value, audited_by, audited_at FROM entity_attributes WHERE run_id=? AND entity_id=? AND attr_name=?",
        (run_id, entity_id, "elevation"),
    ).fetchone()
    assert row["value"] == "1200"
    assert row["audited_by"] is None
    assert row["audited_at"] is None


def test_upsert_entity_attribute_same_value_preserves_audit_status(db_conn):
    conn, run_id = db_conn
    entity_id = _seed_entity_and_attribute(conn, run_id, value="1150")
    conn.execute(
        "UPDATE entity_attributes SET audited_by=?, audited_at=? WHERE run_id=? AND entity_id=? AND attr_name=?",
        ("detector", 54321.0, run_id, entity_id, "elevation"),
    )
    conn.commit()

    cela_main.upsert_entity_attribute(
        conn, run_id, entity_id, "elevation", "1150", "m", "confirmed",
        [{"type": "web", "detail": "re-confirmed"}], "", "task_1_1", "phase_1", "task_planner",
    )

    row = conn.execute(
        "SELECT audited_by, audited_at FROM entity_attributes WHERE run_id=? AND entity_id=? AND attr_name=?",
        (run_id, entity_id, "elevation"),
    ).fetchone()
    assert row["audited_by"] == "detector"
    assert row["audited_at"] == 54321.0


# ---------------------------------------------------------------------------
# 3. mark_fact_audited ツール実体
# ---------------------------------------------------------------------------

def test_mark_fact_audited_tool_registered_in_dispatch():
    assert "mark_fact_audited" in cela_main.TOOL_DISPATCH


def test_mark_fact_audited_rejects_disallowed_role(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id)
    result = cela_main._mark_fact_audited_impl(
        {"ref": "fact:nagano_license_surrender_rate_75plus", "audit_result": "confirmed_correct",
         "reason": "checked"},
        conn, run_id, "expert",
    )
    assert result["success"] is False


@pytest.mark.parametrize("caller_role", ["task_plan_reviewer", "detector"])
def test_mark_fact_audited_allows_task_plan_reviewer_and_detector(db_conn, caller_role):
    conn, run_id = db_conn
    _seed_fact(conn, run_id)
    result = cela_main._mark_fact_audited_impl(
        {"ref": "fact:nagano_license_surrender_rate_75plus", "audit_result": "confirmed_correct",
         "reason": "出典本文を確認し定義が一致することを確認した"},
        conn, run_id, caller_role,
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT audited_by, audited_at FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "nagano_license_surrender_rate_75plus"),
    ).fetchone()
    assert row["audited_by"] == caller_role
    assert row["audited_at"] is not None


def test_mark_fact_audited_writes_entity_attribute_ref(db_conn):
    conn, run_id = db_conn
    entity_id = _seed_entity_and_attribute(conn, run_id)
    result = cela_main._mark_fact_audited_impl(
        {"ref": f"entity:{entity_id}:elevation", "audit_result": "confirmed_correct",
         "reason": "出典（Wikipedia）の標高記述と一致することを確認した"},
        conn, run_id, "detector",
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT audited_by FROM entity_attributes WHERE run_id=? AND entity_id=? AND attr_name=?",
        (run_id, entity_id, "elevation"),
    ).fetchone()
    assert row["audited_by"] == "detector"


def test_mark_fact_audited_rejects_nonexistent_ref(db_conn):
    conn, run_id = db_conn
    result = cela_main._mark_fact_audited_impl(
        {"ref": "fact:does_not_exist", "audit_result": "confirmed_correct", "reason": "x"},
        conn, run_id, "detector",
    )
    assert result["success"] is False


def test_mark_fact_audited_rejects_non_fact_entity_ref(db_conn):
    """agreement:等、fact:/entity:以外のref形式は対象外として拒否する。"""
    conn, run_id = db_conn
    result = cela_main._mark_fact_audited_impl(
        {"ref": "agreement:AG-123", "audit_result": "confirmed_correct", "reason": "x"},
        conn, run_id, "detector",
    )
    assert result["success"] is False


def test_mark_fact_audited_requires_reason(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id)
    result = cela_main._mark_fact_audited_impl(
        {"ref": "fact:nagano_license_surrender_rate_75plus", "audit_result": "confirmed_correct",
         "reason": ""},
        conn, run_id, "detector",
    )
    assert result["success"] is False


def test_mark_fact_audited_rejects_invalid_audit_result(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id)
    result = cela_main._mark_fact_audited_impl(
        {"ref": "fact:nagano_license_surrender_rate_75plus", "audit_result": "maybe", "reason": "x"},
        conn, run_id, "detector",
    )
    assert result["success"] is False


def test_mark_fact_audited_corrected_result_still_only_marks_audit_state(db_conn):
    """audit_result='corrected'でも、mark_fact_audited自身はvalueを書き換えない
    （値の訂正は呼び出し側が事前にwrite_agreement等で行う設計、単一責務）。"""
    conn, run_id = db_conn
    _seed_fact(conn, run_id, value="78.3")
    cela_main._mark_fact_audited_impl(
        {"ref": "fact:nagano_license_surrender_rate_75plus", "audit_result": "corrected",
         "reason": "構成比を返納率として誤登録していたため訂正済み"},
        conn, run_id, "detector",
    )
    row = conn.execute(
        "SELECT value FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "nagano_license_surrender_rate_75plus"),
    ).fetchone()
    assert row["value"] == "78.3"  # mark_fact_audited単体では変わらない


# ---------------------------------------------------------------------------
# 4. _build_unaudited_facts_text のスコープ絞り込み
# ---------------------------------------------------------------------------

def test_unaudited_facts_text_empty_when_nothing_unaudited(db_conn):
    conn, run_id = db_conn
    state = _make_state(run_id, task_id="task_1_1", owns_variables=[])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert text == ""


def test_unaudited_facts_text_includes_own_owns_variables(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, variable_name="nagano_license_surrender_rate_75plus", value="78.3")
    state = _make_state(run_id, task_id="task_1_1",
                        owns_variables=["nagano_license_surrender_rate_75plus"])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert "nagano_license_surrender_rate_75plus" in text
    assert "78.3" in text


def test_unaudited_facts_text_includes_dependency_owns_variables(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, variable_name="population_total", value="54279", task_id="task_1_1")
    upstream_task = {"task_id": "task_1_1", "owns_variables": ["population_total"], "depends_on": []}
    current_task = {"task_id": "task_1_2", "owns_variables": [], "depends_on": ["task_1_1"]}
    state = {
        "run_id": run_id,
        "current_task_id": "task_1_2",
        "current_phase": {"phase_id": "phase_1", "tasks": [current_task]},
        "phases": [{"phase_id": "phase_1", "tasks": [upstream_task, current_task]}],
    }
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert "population_total" in text


def test_unaudited_facts_text_excludes_out_of_scope_variables(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, variable_name="unrelated_variable", value="1", task_id="task_9_9")
    state = _make_state(run_id, task_id="task_1_1", owns_variables=["nagano_license_surrender_rate_75plus"])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert text == ""


def test_unaudited_facts_text_excludes_already_audited(db_conn):
    conn, run_id = db_conn
    _seed_fact(conn, run_id, variable_name="nagano_license_surrender_rate_75plus", value="78.3")
    conn.execute(
        "UPDATE verified_facts SET audited_by=?, audited_at=? WHERE run_id=? AND variable_name=?",
        ("task_plan_reviewer", time.time(), run_id, "nagano_license_surrender_rate_75plus"),
    )
    conn.commit()
    state = _make_state(run_id, task_id="task_1_1",
                        owns_variables=["nagano_license_surrender_rate_75plus"])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert text == ""


def test_unaudited_facts_text_includes_entity_attributes_for_current_task(db_conn):
    conn, run_id = db_conn
    _seed_entity_and_attribute(conn, run_id, entity_id_name="蓼科高原", attr_name="elevation",
                               value="1150", task_id="task_1_1")
    state = _make_state(run_id, task_id="task_1_1", owns_variables=[])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert "elevation" in text
    assert "1150" in text


def test_unaudited_facts_text_excludes_entity_attributes_from_other_tasks(db_conn):
    conn, run_id = db_conn
    _seed_entity_and_attribute(conn, run_id, entity_id_name="蓼科高原", attr_name="elevation",
                               value="1150", task_id="task_9_9")
    state = _make_state(run_id, task_id="task_1_1", owns_variables=[])
    text = cela_main._build_unaudited_facts_text(conn, run_id, state)
    assert text == ""


# ---------------------------------------------------------------------------
# 5. ツール配線・プロンプト文言の存在確認（inspect.getsource）
# ---------------------------------------------------------------------------

def test_task_plan_reviewer_tools_include_mark_fact_audited():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "MARK_FACT_AUDITED_TOOL" in src


def test_detector_domain_tools_include_mark_fact_audited():
    src = inspect.getsource(cela_main.call_detector)
    assert "MARK_FACT_AUDITED_TOOL" in src


def test_detector_domain_prompt_calls_unaudited_facts_helper():
    src = inspect.getsource(cela_main.call_detector)
    assert "_build_unaudited_facts_text(" in src


def test_task_plan_reviewer_prompt_has_definitional_audit_criterion():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "BL-294" in src
    assert "定義監査" in src


def test_task_planner_prompt_has_bl294_self_check():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-294" in src


def test_write_agreement_tool_confirmed_variables_has_bl294_guardrail():
    desc = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["confirmed_variables"]["description"]
    assert "BL-294" in desc
