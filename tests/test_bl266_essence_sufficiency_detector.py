"""
BL-266 層3: `call_detector`のdomain_promptに、既存の本質乖離検知（BL-087 Stage4、
「今ある計画・数値が本質からずれていないか」というドリフト検知）とは別枠で、能動的な
充足性チェック（「本質が要求しているのに、計画にそもそも存在しない要素はないか」）を
追加した。判定は新規フラグ`essence_sufficiency_concern`（bool）で表現し、「今のタスクの
手直しでは解消しない、計画構造自体の欠落」と確信できる場合のみtrueにする。

trueが返った場合、detector_node側がPython側で機械的にissue_log（severity="major"、
不変条件により即座にstatus="escalated"）へCREATEする。LLM自身にwrite_issue呼び出しを
指示しない設計（ツール呼び出し忘れという新たな失敗点を増やさないため、既存のBL-096
バックアップ書き込みパターンを踏襲）。

bool判定の正規化は、call_reflectionの`still_aligned`・call_reviewerの`passed`と同じ
パターン（文字列なら"true"/"false"として大文字小文字を問わず解釈、それ以外はbool()）に
統一した。素朴な`bool(x)`だとLLMが返した文字列"false"がtruthyでTrueと誤判定される
（AGENTS.md §13.1 空文字トラップと同種のクラス）。

参照: docs/design/back_log/BL-266/BL266_investigation.md。
実LLM API呼び出しは伴わない（call_detector自体は_query_and_parse_with_retryのmonkeypatch、
detector_nodeはcall_detectorのmonkeypatchで検証する）。
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
    db_path = str(tmp_path / "test_bl266_detector.db")
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


# --- ソース確認: JSON schema・正規化ロジックの存在確認 -------------------------

def test_domain_prompt_schema_includes_essence_fields():
    src = _detector_src()
    schema_idx = src.index('Return ONLY JSON: {{"constraint_issue"')
    schema_line = src[schema_idx: schema_idx + 700]
    assert '"essence_sufficiency_concern": true/false' in schema_line
    assert '"essence_sufficiency_reason"' in schema_line


def test_domain_fallback_includes_essence_defaults():
    src = _detector_src()
    fallback_idx = src.index('fallback={"constraint_issue": "none", "comment": "", "target_excerpt"')
    fallback_block = src[fallback_idx: fallback_idx + 300]
    assert '"essence_sufficiency_concern": False' in fallback_block
    assert '"essence_sufficiency_reason": ""' in fallback_block


def test_domain_parse_failure_forces_essence_concern_false():
    """[設計判断] constraint_issueのフェイルクローズ(major)とは非対称に、
    essence_sufficiency_concernはパース失敗時にFalseへ倒す（単なるJSON解析失敗が
    issue_log起票・即時reflection遷移という重い副作用へ過大に波及しないため）。"""
    src = _detector_src()
    failed_idx = src.index("if domain_parse_failed:")
    else_idx = src.index("else:", failed_idx)
    failed_block = src[failed_idx:else_idx]
    assert "domain_essence_concern = False" in failed_block


def test_domain_essence_concern_uses_same_normalization_as_still_aligned_and_passed():
    """[AGENTS.md §15.1] is Trueのような厳格判定ではなく、既存のstill_aligned/passedと
    同じ正規化パターン（文字列なら"true"比較、それ以外はbool()）へ統一されていること。
    素朴なbool(x)への退行（文字列"false"をTrue扱いする回帰）を検出する。"""
    src = _detector_src()
    idx = src.index('_essence_val = domain_parsed.get("essence_sufficiency_concern", False)')
    nearby = src[idx: idx + 250]
    assert 'str(_essence_val).lower() == "true"' in nearby
    assert "isinstance(_essence_val, str)" in nearby
    assert "bool(_essence_val)" in nearby


def test_detector_final_return_includes_essence_fields():
    src = _detector_src()
    return_idx = src.rindex("return {")
    return_block = src[return_idx:]
    assert '"essence_sufficiency_concern": domain_essence_concern' in return_block
    assert '"essence_sufficiency_reason": domain_essence_reason' in return_block


# --- 実行時の挙動確認: call_detectorの戻り値への伝播 ----------------------------

def _install_capturing_retry(monkeypatch, captured: dict, overrides: dict | None = None):
    """[test_bl164流用] labelごとにfallbackへoverridesをマージして返す。"""
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


def test_call_detector_propagates_essence_concern_true_json_bool(db_conn, monkeypatch):
    """domain_promptがJSON boolのtrueを返した場合、call_detectorの最終戻り値まで
    essence_sufficiency_concern=Trueが伝播すること。
    【リバート検出】最終returnの合流コードを削除すると失敗する。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {
            "essence_sufficiency_concern": True,
            "essence_sufficiency_reason": "本質が言及する高齢者の移動手段への言及が計画に無い",
        },
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["essence_sufficiency_concern"] is True
    assert "高齢者" in result["essence_sufficiency_reason"]


def test_call_detector_propagates_essence_concern_true_string_bool(db_conn, monkeypatch):
    """domain_promptが文字列"true"を返した場合も正しく正規化されTrueになること
    （素朴なbool(x)なら文字列"false"がTrue扱いされる回帰の対照テスト）。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {"essence_sufficiency_concern": "true"},
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["essence_sufficiency_concern"] is True


def test_call_detector_string_false_normalizes_to_false(db_conn, monkeypatch):
    """[回帰検出] domain_promptが文字列"false"を返した場合、素朴なbool("false")なら
    Trueになってしまうところ、正しくFalseへ正規化されること。"""
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured, overrides={
        "Detector (Domain Review)": {"essence_sufficiency_concern": "false"},
    })

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["essence_sufficiency_concern"] is False


def test_call_detector_essence_concern_false_by_default(db_conn, monkeypatch):
    conn, run_id = db_conn
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    assert result["essence_sufficiency_concern"] is False
    assert result["essence_sufficiency_reason"] == ""


def test_call_detector_domain_parse_failure_does_not_force_essence_concern(db_conn, monkeypatch):
    def _always_fail(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        return dict(fallback), True

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _always_fail)
    conn, run_id = db_conn

    result = cela_main.call_detector(_minimal_state(run_id), target_role="expert")

    # フェイルクローズでconstraint_issueはmajorになるが、essence_sufficiency_concernは
    # falseのままであること（重い副作用の過大波及を防ぐ設計、上記ソース検査の実挙動確認）。
    assert result["constraint_issue"] == "major"
    assert result["essence_sufficiency_concern"] is False


# --- detector_node: issue_log起票・stateフラグ設定 ------------------------------

def _detector_node_state(run_id: str, last_role: str = "user") -> dict:
    return {
        "chat_history": [{"role": last_role, "content": "テスト発言"}],
        "expert_last_python_calls": [],
        "constraint_issue_log": [],
        "turn_count": 1,
        "run_id": run_id,
        "current_phase": {"phase_id": "phase_1"},
    }


def test_detector_node_writes_issue_on_essence_concern(db_conn, monkeypatch):
    conn, run_id = db_conn

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        return {
            "risk": "low", "constraint_issue": "none", "comment": "OK", "observations": "",
            "essence_sufficiency_concern": True,
            "essence_sufficiency_reason": "本質が要求する範囲が計画に反映されていない",
        }

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = _detector_node_state(run_id)
    cela_main.detector_node(state)

    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic LIKE 'essence_sufficiency_concern_%'",
        (run_id,),
    ).fetchone()
    assert row is not None, "essence_sufficiency_concern由来のissueがissue_logへ起票されていません"
    assert row["severity"] == "major"
    assert row["status"] == "escalated"
    assert row["raised_by"] == "detector_auto"


def test_detector_node_sets_pending_flag_on_essence_concern(db_conn, monkeypatch):
    conn, run_id = db_conn

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        return {
            "risk": "low", "constraint_issue": "none", "comment": "OK", "observations": "",
            "essence_sufficiency_concern": True,
            "essence_sufficiency_reason": "理由",
        }

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = _detector_node_state(run_id)
    result = cela_main.detector_node(state)

    assert result["essence_sufficiency_concern_pending"] is True


def test_detector_node_no_issue_when_essence_concern_false(db_conn, monkeypatch):
    """[誤発火の回帰防止] essence_sufficiency_concern=Falseのとき、対応するtopicのissueが
    作成されないこと。"""
    conn, run_id = db_conn

    def _fake_call_detector(state, target_role, review_mode="task_output"):
        return {
            "risk": "low", "constraint_issue": "none", "comment": "OK", "observations": "",
            "essence_sufficiency_concern": False,
            "essence_sufficiency_reason": "",
        }

    monkeypatch.setattr(cela_main, "call_detector", _fake_call_detector)

    state = _detector_node_state(run_id)
    result = cela_main.detector_node(state)

    row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic LIKE 'essence_sufficiency_concern_%'",
        (run_id,),
    ).fetchone()
    assert row is None
    assert result.get("essence_sufficiency_concern_pending", False) is False
