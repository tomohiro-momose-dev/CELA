"""
BL-292: BL-278の「十分性」定義が本質記述との主観的照合に留まり、人口・需要規模に対する
定量的カバレッジを検証しない問題への対応。

ユーザー指摘「十分性というのは、例えば人口が5万人いるのにスーパーを1か所とするのは合理的
ではない、こういう事」を受け、BL-278のdomain_prompt文言を確認したところ、「十分性」判定は
LLMが「本質記述」と「選定基準」という2つの散文を主観的に見比べる言語的判断に留まり、規模指標
（人口・需要量等）に対する定量的なカバレッジ計算は一切要求されていなかった。

対応は6箇所（一般化した「規模適合性」= 何らかのリソース〈拠点数・容量・人員・予算等〉が
対象規模〈人口・需要量・処理件数・負荷等〉に対して量的に十分か、を定性的な存在確認ではなく
定量的な比率・カバレッジ計算で判断させること）:
  ① call_expert: F-2.6検算ゲート直後に定量計算の明記を要求
  ② call_detector Domain Review: 独立JSONフィールド quantitative_sufficiency_concern/
     _reason を新設（BL-266のessence_sufficiency_concernと同型のコードパターン）。
     機械的floor enforcement付き（concern=Trueならconstraint_issueをminor以上へ引き上げ）。
  ③ 数値監査パス（2段目）: domain_findings_block経由でconcern=Trueの場合に独立検算を指示
  ④ call_task_planner: 指示文品質ガイドへ規模適合性の要求を追加
  ⑤ _USER_AI_ROLE_MANDATE: レビュー・指示の両Stageに共通する単一箇所へ追加
  ⑥ call_reviewer（最終QA）: 新規チェック項目として追加（passed/feedback既存スキーマ内）

ユーザー指摘により「新規JSONフィールドは追加しない」という当初方針を撤回した。理由:
(a) プロンプトキャッシュのヒット率はモデル・プロバイダー依存であり、現行構成では当時ほど
    ネックではないと判明したこと、(b) 軽量・高速モデルは思考が浅く結論を急ぎがちなため、
    一文をプロンプトへ埋め込むだけでなく独立フィールドで明示的な回答を強制する構造的な
    補強が必要、という2点。

参照: docs/design/back_log/BL-291/BL291_292_basic_design.md、issue_backlog.md BL-292、
docs/design/decision_log.md D-番号未定（実装後に追記）。
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
    db_path = str(tmp_path / "test_bl292.db")
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


def _detector_src() -> str:
    return inspect.getsource(cela_main.call_detector)


# ---------------------------------------------------------------------------
# ① call_expert: F-2.6 検算ゲート直後
# ---------------------------------------------------------------------------

def test_call_expert_contains_bl292_quantitative_calc_instruction():
    src = inspect.getsource(cela_main.call_expert)
    idx = src.index("F-2.6 機械的検算ゲート")
    block = src[idx: idx + 400]
    assert "BL-292" in block
    assert "python_repl" in block


# ---------------------------------------------------------------------------
# ④ call_task_planner: 指示文品質ガイド
# ---------------------------------------------------------------------------

def test_call_task_planner_contains_bl292_scale_adequacy_instruction():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "[BL-292" in src
    idx = src.index("[BL-292")
    block = src[idx: idx + 300]
    assert "定量的なカバレッジ" in block or "定量的なカバレッジ・比率" in block


# ---------------------------------------------------------------------------
# ⑤ _USER_AI_ROLE_MANDATE
# ---------------------------------------------------------------------------

def test_user_ai_role_mandate_contains_bl292_instruction():
    assert "[BL-292]" in cela_main._USER_AI_ROLE_MANDATE
    assert "定量的なカバレッジ" in cela_main._USER_AI_ROLE_MANDATE


# ---------------------------------------------------------------------------
# ⑥ call_reviewer: 最終QAチェック項目
# ---------------------------------------------------------------------------

def test_call_reviewer_contains_bl292_checklist_item():
    src = inspect.getsource(cela_main.call_reviewer)
    assert "規模適合性の再検証チェック" in src
    idx = src.index("規模適合性の再検証チェック")
    block = src[idx: idx + 400]
    assert "passed: false" in block


def test_call_reviewer_schema_unchanged_no_new_field():
    """[スコープ確認] Reviewerの出力スキーマ（passed/feedback/reasoning）に新規フィールドは
    追加しない（既存スキーマ内でチェック項目を表現する設計）。"""
    src = inspect.getsource(cela_main.call_reviewer)
    schema_idx = src.index("Return ONLY JSON:")
    schema_block = src[schema_idx: schema_idx + 300]
    assert '"passed"' in schema_block
    assert '"feedback"' in schema_block
    assert '"reasoning"' in schema_block
    assert "quantitative_sufficiency" not in schema_block


# ---------------------------------------------------------------------------
# ② call_detector Domain Review: 新規JSONフィールドのソース確認
# ---------------------------------------------------------------------------

def test_domain_prompt_contains_bl292_scale_adequacy_check():
    src = _detector_src()
    start = src.index("domain_prompt = (")
    end = src.index("_reset_think_scratchpad()", start)
    block = src[start:end]
    assert "[BL-292: 規模適合性チェック]" in block
    assert "quantitative_sufficiency_concern" in block


def test_domain_prompt_schema_includes_quantitative_fields():
    src = _detector_src()
    schema_idx = src.index('Return ONLY JSON: {{"constraint_issue"')
    schema_line = src[schema_idx: schema_idx + 900]
    assert '"quantitative_sufficiency_concern": true/false' in schema_line
    assert '"quantitative_sufficiency_reason"' in schema_line
    # 既存フィールドを壊していないこと
    assert '"essence_sufficiency_concern": true/false' in schema_line


def test_domain_fallback_includes_quantitative_defaults():
    src = _detector_src()
    fallback_idx = src.index('fallback={"constraint_issue": "none", "comment": "", "target_excerpt"')
    fallback_block = src[fallback_idx: fallback_idx + 400]
    assert '"quantitative_sufficiency_concern": False' in fallback_block
    assert '"quantitative_sufficiency_reason": ""' in fallback_block


def test_domain_parse_failure_forces_quant_concern_false():
    src = _detector_src()
    failed_idx = src.index("if domain_parse_failed:")
    else_idx = src.index("else:", failed_idx)
    failed_block = src[failed_idx:else_idx]
    assert "domain_quant_concern = False" in failed_block


def test_domain_quant_concern_uses_same_normalization_as_essence_concern():
    src = _detector_src()
    idx = src.index('_quant_val = domain_parsed.get("quantitative_sufficiency_concern", False)')
    nearby = src[idx: idx + 250]
    assert 'str(_quant_val).lower() == "true"' in nearby
    assert "isinstance(_quant_val, str)" in nearby
    assert "bool(_quant_val)" in nearby


def test_domain_constraint_issue_floor_enforcement_present():
    """[機械的floor enforcement] quantitative_sufficiency_concern=Trueかつconstraint_issue=
    noneの場合にminorへ引き上げるコードが存在すること（AGENTS.md §15.3）。"""
    src = _detector_src()
    idx = src.index('domain_quant_reason = domain_parsed.get("quantitative_sufficiency_reason", "")')
    nearby = src[idx: idx + 900]
    assert "domain_quant_concern and domain_constraint_issue" in nearby
    assert 'domain_constraint_issue = "minor"' in nearby


def test_domain_findings_block_forwards_quant_concern_to_numeric_pass():
    src = _detector_src()
    idx = src.index("domain_findings_block = (")
    end = src.index("prompt = (", idx)
    block = src[idx:end]
    assert "domain_quant_concern" in block
    assert "domain_quant_reason" in block


def test_detector_final_return_includes_quant_fields():
    src = _detector_src()
    return_idx = src.rindex("return {")
    return_block = src[return_idx:]
    assert '"quantitative_sufficiency_concern": domain_quant_concern' in return_block
    assert '"quantitative_sufficiency_reason": domain_quant_reason' in return_block


# ---------------------------------------------------------------------------
# ②③ 実行時の挙動確認: call_detectorの戻り値への伝播・floor enforcement
# ---------------------------------------------------------------------------

def _install_capturing_retry(monkeypatch, captured: dict, overrides: dict | None = None):
    """[test_bl266流用] labelごとにfallbackへoverridesをマージして返す。"""
    overrides = overrides or {}

    def _fake_query_and_parse_with_retry(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        captured[label] = prompt
        merged = dict(fallback)
        merged.update(overrides.get(label, {}))
        return merged, False

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake_query_and_parse_with_retry)


def _minimal_state(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "goal": "テストゴール",
        "chat_history": [{"role": "user", "content": "テスト発言"}],
        "current_phase": {
            "phase_id": "phase_1",
            "tasks": [{"task_id": "task_1_1", "title": "t", "acceptance_criteria": []}],
        },
        "current_task_id": "task_1_1",
    }


def test_call_detector_propagates_quant_concern_true(db_conn, monkeypatch):
    """domain_promptがquantitative_sufficiency_concern=Trueを返した場合、call_detectorの
    最終戻り値まで伝播すること。【リバート検出】最終returnの合流コードを削除すると失敗する。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {
            "quantitative_sufficiency_concern": True,
            "quantitative_sufficiency_reason": "店舗数3に対し人口5万人のカバー率が未計算",
        },
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["quantitative_sufficiency_concern"] is True
    assert "カバー率" in result["quantitative_sufficiency_reason"]


def test_call_detector_quant_concern_string_true_normalizes(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {"quantitative_sufficiency_concern": "true"},
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["quantitative_sufficiency_concern"] is True


def test_call_detector_quant_concern_string_false_normalizes(db_conn, monkeypatch):
    """[回帰検出] 素朴なbool("false")ならTrueになってしまうところ、正しくFalseへ正規化される。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {"quantitative_sufficiency_concern": "false"},
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["quantitative_sufficiency_concern"] is False


def test_call_detector_quant_concern_false_by_default(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["quantitative_sufficiency_concern"] is False
    assert result["quantitative_sufficiency_reason"] == ""


def test_call_detector_parse_failure_does_not_force_quant_concern(db_conn, monkeypatch):
    def _always_fail(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        return dict(fallback), True

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _always_fail)
    conn, run_id = db_conn

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["constraint_issue"] == "major"  # フェイルクローズ
    assert result["quantitative_sufficiency_concern"] is False


def test_call_detector_floor_enforcement_raises_none_to_minor(db_conn, monkeypatch):
    """[機械的floor enforcement] Domain Reviewがconstraint_issue="none"のままquantitative_
    sufficiency_concern=Trueを返した場合、call_detectorが機械的にminorへ引き上げること。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {
            "constraint_issue": "none",
            "quantitative_sufficiency_concern": True,
            "quantitative_sufficiency_reason": "未検証の規模適合性主張",
        },
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    # 統合ロジックは domain/numeric のうち厳しい方を採用するため、floor enforcementで
    # domain側がminorへ引き上げられていれば、最終constraint_issueも最低minor以上になる。
    assert result["constraint_issue"] != "none"


def test_call_detector_floor_enforcement_does_not_downgrade_major(db_conn, monkeypatch):
    """[回帰防止] 既にmajorと判定されている場合、floor enforcementがそれをminorへ
    引き下げてしまわないこと（"none"の場合のみ引き上げる設計）。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {
            "constraint_issue": "major",
            "quantitative_sufficiency_concern": True,
            "quantitative_sufficiency_reason": "理由",
        },
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["constraint_issue"] == "major"


def test_numeric_pass_prompt_receives_quant_concern_instruction_when_true(db_conn, monkeypatch):
    """③ domain_findings_block経由で、quantitative_sufficiency_concern=Trueの場合のみ
    数値監査パス（label="Detector"）のプロンプトへ独立検算の指示が転送されること。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {
            "quantitative_sufficiency_concern": True,
            "quantitative_sufficiency_reason": "店舗数がカバー人口比で未検証",
        },
    })

    cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    numeric_prompt = captured.get("Detector", "")
    assert "BL-292" in numeric_prompt
    assert "店舗数がカバー人口比で未検証" in numeric_prompt


def test_numeric_pass_prompt_omits_quant_instruction_when_false(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)

    cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    numeric_prompt = captured.get("Detector", "")
    assert "[BL-292]" not in numeric_prompt


# ---------------------------------------------------------------------------
# 全体: ソース存在証明
# ---------------------------------------------------------------------------

def test_bl292_markers_present_in_source():
    src = inspect.getsource(cela_main)
    assert src.count("BL-292") >= 6
