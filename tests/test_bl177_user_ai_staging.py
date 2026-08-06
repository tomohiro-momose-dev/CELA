"""
BL-177（User AI部分）: `generate_user_utterance`を、Detectorの2段監査パス（BL-049/BL-054）と
同型の4段階（レビュー→issue確認→統合承認判断→次タスク指示/現タスク修正指示/承認記録失敗の
待機メッセージ）へ分解する実装の検証。

設計はPlan modeで確定し`docs/design/back_log/BL-177/BL177_basic_design.md`に保存済み。
設計レビューでユーザーが指摘した「Stage3の承認記録がStage4で握りつぶされ、矛盾した修正指示が
出る」リスクへの対応として、自己申告（approval_status）とツール呼び出し結果
（get_last_write_agreement_succeeded）の不一致は、Stage4のLLMにではなくPythonコード側で
機械的に判定し、不一致時はStage3自体を訂正指示付きで再試行する（最大2回）設計とした。

参照: docs/design/back_log/issue_backlog.md BL-177、BL-176。
実LLM API呼び出しは伴わない（`_query_and_parse_with_retry`/`query_AI`をmonkeypatch）。
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
    db_path = str(tmp_path / "test_bl177.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    orig_wrote_agreement = cela_main._LAST_WRITE_AGREEMENT_SUCCEEDED
    orig_wrote_issue = cela_main._LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._LAST_WRITE_AGREEMENT_SUCCEEDED = orig_wrote_agreement
        cela_main._LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED = orig_wrote_issue


_TASK_1_1 = {
    "task_id": "task_1_1", "title": "初期整理",
    "description": "初期の整理を行う。",
    "acceptance_criteria": ["整理済みであること"],
    "depends_on": [], "owns_variables": [],
}
_PHASE_1 = {"phase_id": "phase_1", "tasks": [_TASK_1_1]}


def _insert_approved_deliverable(conn, run_id, task_id="task_1_1", phase_id="phase_1", seq=1):
    """[BL-178フォローアップ] Stage3の承認記録が実際にExpertの成果物（entry_type="Deliverable"）
    自体を更新したことを、_is_task_completed（BL-167）が検知できるようDB行を用意する。
    fakeのwrote_agreement=Trueだけでは（BL-178修正前の不具合と同様）このDB状態を再現しないため、
    Stage3の成功を期待するテストではこのヘルパーで明示的に用意する。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", "Approved", f"{task_id}の成果物", "X" * 300, "r", "expert", "Deliverable",
         phase_id, task_id, "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()

_CONFIG = {
    "is_stateless_mode": False,
    "user_always_remember": False,
    "chat_history_window": 4,
}


def _normal_turn_state(run_id: str) -> dict:
    """通常のレビューターン（ステージ化パイプラインの対象）を模した最小state。"""
    return {
        "run_id": run_id,
        "goal": "テストゴール",
        "phases": [_PHASE_1],
        "current_phase": _PHASE_1,
        "current_task_id": "task_1_1",
        "chat_history": [{"role": "assistant", "content": "成果物を提出します。"}],
        "turn_count": 2,
        "max_turns": 20,
        "constraint_issue": "none",
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "",
        "escalation_active": False,
        "escalation_just_resolved_notice_pending": False,
    }


def _install_stage_fakes(monkeypatch, responses: dict, call_log: list):
    """responses: label -> dict（毎回同じ応答） または label -> list[dict]（呼び出しごとに順に消費、
    尽きたら最後の値を再利用）。各エントリは {"result": {...}, "parse_failed": bool,
    "wrote_agreement": bool} の形。"""
    call_counts: dict = {}

    def _fake_query_and_parse_with_retry(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        call_log.append(("retry", label, prompt))
        idx = call_counts.get(label, 0)
        call_counts[label] = idx + 1
        spec = responses.get(label, {})
        if isinstance(spec, list):
            entry = spec[min(idx, len(spec) - 1)] if spec else {}
        else:
            entry = spec
        cela_main._LAST_WRITE_AGREEMENT_SUCCEEDED = entry.get("wrote_agreement", False)
        cela_main._LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED = entry.get("wrote_issue_resolution", False)
        if entry.get("parse_failed"):
            return dict(fallback), True
        return dict(entry.get("result", fallback)), False

    def _fake_query_AI(messages, client, model, label="Unknown Node", tools=None, state=None):
        call_log.append(("query_AI", label, messages))
        entry = responses.get(label, {})
        return entry.get("content", "次のタスクへ進んでください。")

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake_query_and_parse_with_retry)
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI)


_DEFAULT_RESPONSES = {
    "User AI (Stage1: レビュー)": {
        "result": {"domain_concerns": "", "scope_compliant": True, "review_comment": "問題なし"},
    },
    "User AI (Stage2: issue確認)": {
        "result": {"issues_handled": True, "remaining_concerns": ""},
    },
    "User AI (Stage3: 統合承認判断)": {
        "result": {"approval_status": "Approved", "approval_reason": "基準を満たしている"},
        "wrote_agreement": True,
    },
    "User AI (Stage4)": {"content": "次のタスクへ進んでください。"},
}


# ---------------------------------------------------------------------------
# ソース確認
# ---------------------------------------------------------------------------

def test_source_defines_all_four_stages():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "Stage1: レビュー" in src
    assert "Stage2: issue確認" in src
    assert "Stage3: 統合承認判断" in src
    assert "Stage4" in src


def test_source_uses_resolving_deliverable_statuses_for_stage4_branch():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "RESOLVING_DELIVERABLE_STATUSES" in src
    assert "ApprovalRecordingFailed" in src


def test_source_stage3_instructs_updating_the_deliverable_itself():
    """[BL-178フォローアップ] Stage3のプロンプトが、承認を新しいDecisionエントリとして
    CREATEするのではなく、Expertの成果物（Deliverable）自体をUPDATEするよう明示的に
    指示していることを確認する（実ドライランで発見された不具合の再発防止）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert '_find_active_deliverable_agreement(' in src
    assert 'entry_type=\\"Deliverable\\"' in src
    assert 'target_topic=\\"{_deliverable_topic}' in src


def test_source_stage3_mismatch_check_uses_is_task_completed():
    """[BL-178フォローアップ] Stage3の食い違い判定が、単なる`get_last_write_agreement_succeeded()`
    だけでなく、BL-176のゲートと同一基準の`_is_task_completed`も併用していることを確認する
    （write_agreementは成功したが対象がDeliverableでなかった、というケースを検知するため）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    mismatch_check_idx = src.index("get_last_write_agreement_succeeded() and _is_task_completed(")
    assert mismatch_check_idx > 0


# ---------------------------------------------------------------------------
# ルーティング: 通常ターンはステージ化パイプラインへ、特殊モードは現行の単発呼び出しへ
# ---------------------------------------------------------------------------

def test_normal_turn_routes_to_staged_pipeline(db_conn, monkeypatch):
    conn, run_id = db_conn
    call_log: list = []
    _install_stage_fakes(monkeypatch, _DEFAULT_RESPONSES, call_log)

    content = cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    labels = [c[1] for c in call_log]
    assert "User AI (Stage1: レビュー)" in labels
    assert "User AI (Stage2: issue確認)" in labels
    assert "User AI (Stage3: 統合承認判断)" in labels
    assert "User AI (Stage4)" in labels
    assert content == "次のタスクへ進んでください。"


@pytest.mark.parametrize("flag_key,flag_value", [
    ("essence_dialogue_active", True),
    ("expert_pending_question", "何か質問"),
    ("drift_flag", True),
])
def test_special_mode_bypasses_staged_pipeline(db_conn, monkeypatch, flag_key, flag_value):
    """[BL-126/BL-130/BL-142] 特殊モードでは現行の単発query_AI呼び出しのまま（ステージ化対象外）。"""
    conn, run_id = db_conn
    call_log: list = []
    _install_stage_fakes(monkeypatch, {"User AI": {"content": "単発応答"}}, call_log)

    state = _normal_turn_state(run_id)
    state[flag_key] = flag_value
    content = cela_main.generate_user_utterance(state, _CONFIG)

    labels = [c[1] for c in call_log]
    assert "User AI (Stage1: レビュー)" not in labels
    assert "User AI (Stage3: 統合承認判断)" not in labels
    assert "User AI" in labels
    assert content == "単発応答"


def test_final_turn_bypasses_staged_pipeline(db_conn, monkeypatch):
    conn, run_id = db_conn
    call_log: list = []
    _install_stage_fakes(monkeypatch, {"User AI": {"content": "[PROJECT_COMPLETE]"}}, call_log)

    state = _normal_turn_state(run_id)
    state["turn_count"] = state["max_turns"] - 1
    cela_main.generate_user_utterance(state, _CONFIG)

    labels = [c[1] for c in call_log]
    assert "User AI (Stage1: レビュー)" not in labels
    assert "User AI" in labels


def test_empty_chat_history_bypasses_staged_pipeline(db_conn, monkeypatch):
    conn, run_id = db_conn
    call_log: list = []
    _install_stage_fakes(monkeypatch, {"User AI": {"content": "初回発言"}}, call_log)

    state = _normal_turn_state(run_id)
    state["chat_history"] = []
    cela_main.generate_user_utterance(state, _CONFIG)

    labels = [c[1] for c in call_log]
    assert "User AI (Stage1: レビュー)" not in labels
    assert "User AI" in labels


# ---------------------------------------------------------------------------
# Stage4の3分岐
# ---------------------------------------------------------------------------

def test_stage4_uses_next_task_prompt_when_approved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id)
    call_log: list = []
    _install_stage_fakes(monkeypatch, _DEFAULT_RESPONSES, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    stage4_call = next(c for c in call_log if c[1] == "User AI (Stage4)")
    system_msg = stage4_call[2][0]["content"]
    assert "次のタスクを指示する" in system_msg or "次タスク" in system_msg
    assert "承認理由" in system_msg


def test_stage4_uses_revision_prompt_when_rejected(db_conn, monkeypatch):
    conn, run_id = db_conn
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage3: 統合承認判断)"] = {
        "result": {"approval_status": "Rejected", "approval_reason": "基準を満たしていない"},
        "wrote_agreement": False,
    }
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    stage4_call = next(c for c in call_log if c[1] == "User AI (Stage4)")
    system_msg = stage4_call[2][0]["content"]
    assert "修正指示" in system_msg
    assert "却下・保留の理由" in system_msg


def test_stage4_uses_recording_failed_prompt_after_retries_exhausted(db_conn, monkeypatch):
    """[設計レビューで発見] approval_status=Approvedの自己申告とwrite_agreement未成功が
    3回とも食い違うと、Stage4はExpertの成果物に一切言及しない技術的待機メッセージへ分岐する。"""
    conn, run_id = db_conn
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage3: 統合承認判断)"] = [
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": False},
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": False},
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": False},
    ]
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    stage3_calls = [c for c in call_log if c[1] == "User AI (Stage3: 統合承認判断)"]
    assert len(stage3_calls) == 3, "リトライが最大2回（初回+2）行われていない"
    assert "訂正指示" in stage3_calls[1][2], "2回目の呼び出しに訂正指示が付与されていない"

    stage4_call = next(c for c in call_log if c[1] == "User AI (Stage4)")
    system_msg = stage4_call[2][0]["content"]
    assert "技術的な理由で" in system_msg or "承認手続き" in system_msg
    assert "修正指示" not in system_msg, "成果物内容への言及（実在しない欠陥のでっち上げ）を防ぐ設計に反する"


def test_stage3_retries_when_write_agreement_succeeds_but_wrong_entry_updated(db_conn, monkeypatch):
    """[BL-178フォローアップ] 実ドライラン（log/2026-08-05/1542, 1556）で発見された不具合の
    再現テスト: write_agreementの呼び出し自体は成功する（wrote_agreement=True）が、Expertの
    成果物（entry_type="Deliverable"）ではなく別のDecisionエントリを更新してしまった場合
    （＝task_1_1用のApproved Deliverable行がDBに存在しない）、get_last_write_agreement_
    succeeded()だけでは検知できず、_is_task_completed併用の食い違い判定がリトライを発火させ、
    3回とも解消しなければApprovalRecordingFailedへ落ちることを確認する。"""
    conn, run_id = db_conn
    # 意図的にDeliverable行を挿入しない（Decisionエントリ等、別の何かが更新されたのみの状態を再現）。
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage3: 統合承認判断)"] = [
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": True},
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": True},
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": True},
    ]
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    stage3_calls = [c for c in call_log if c[1] == "User AI (Stage3: 統合承認判断)"]
    assert len(stage3_calls) == 3, "write_agreementが成功しただけで（対象を検証せず）即座に成功扱いされている"
    assert "target_topic" in stage3_calls[1][2], "訂正指示にtarget_topicの指定方法が含まれていない"

    stage4_call = next(c for c in call_log if c[1] == "User AI (Stage4)")
    system_msg = stage4_call[2][0]["content"]
    assert "技術的な理由で" in system_msg or "承認手続き" in system_msg


def test_stage3_retry_succeeds_before_exhausting_and_reaches_next_task_prompt(db_conn, monkeypatch):
    """1回目は食い違うが2回目で一致すれば、Stage4は通常の次タスク指示プロンプトになる
    （ApprovalRecordingFailedへは落ちない）。"""
    conn, run_id = db_conn
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage3: 統合承認判断)"] = [
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": False},
        {"result": {"approval_status": "Approved", "approval_reason": "承認します"}, "wrote_agreement": True},
    ]
    _insert_approved_deliverable(conn, run_id)
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    stage3_calls = [c for c in call_log if c[1] == "User AI (Stage3: 統合承認判断)"]
    assert len(stage3_calls) == 2, "1回目の食い違いで即座にStage4へ進んでしまっている（Stage3の再試行が働いていない）"

    stage4_call = next(c for c in call_log if c[1] == "User AI (Stage4)")
    system_msg = stage4_call[2][0]["content"]
    assert "技術的な理由で" not in system_msg
    assert "承認理由" in system_msg


# ---------------------------------------------------------------------------
# 制約2: ターン単位トラッカーのステージ横断集約
# ---------------------------------------------------------------------------

def test_stage2_write_issue_success_is_not_lost_by_later_stage_calls(db_conn, monkeypatch):
    """[BL-177 制約2] Stage2でwrite_issue(RESOLVE/DEFER)が成功しても、後続のStage3・Stage4の
    query_AI呼び出しが_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDEDを再度Falseへリセットする
    ため、集約せずgetter任せにすると消えてしまう（このテストは集約が機能していることの確認）。"""
    conn, run_id = db_conn
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage2: issue確認)"] = {
        "result": {"issues_handled": True, "remaining_concerns": ""},
        "wrote_issue_resolution": True,
    }
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    assert cela_main.get_last_write_issue_resolve_or_defer_succeeded() is True


def test_stage3_write_agreement_success_is_not_lost_by_stage4_call(db_conn, monkeypatch):
    """[BL-177 制約2] Stage3のwrite_agreement成功が、副作用を持たないStage4呼び出し後も
    get_last_write_agreement_succeeded()から見えること（generate_user_utterance_nodeの
    R3b §3.5.1 二重書き込み防止ロジックが依存する）。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id)
    call_log: list = []
    _install_stage_fakes(monkeypatch, _DEFAULT_RESPONSES, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    assert cela_main.get_last_write_agreement_succeeded() is True


def test_neither_stage_wrote_agreement_reflects_false(db_conn, monkeypatch):
    conn, run_id = db_conn
    responses = dict(_DEFAULT_RESPONSES)
    responses["User AI (Stage3: 統合承認判断)"] = {
        "result": {"approval_status": "Rejected", "approval_reason": "不十分"},
        "wrote_agreement": False,
    }
    call_log: list = []
    _install_stage_fakes(monkeypatch, responses, call_log)

    cela_main.generate_user_utterance(_normal_turn_state(run_id), _CONFIG)

    assert cela_main.get_last_write_agreement_succeeded() is False


# ---------------------------------------------------------------------------
# generate_user_utterance_nodeとの結合（既存の読み取りコードが無改修で動くこと）
# ---------------------------------------------------------------------------

def test_generate_user_utterance_node_reflects_staged_agreement_success(db_conn, monkeypatch):
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id)
    call_log: list = []
    _install_stage_fakes(monkeypatch, _DEFAULT_RESPONSES, call_log)
    monkeypatch.setattr(cela_main, "config", _CONFIG, raising=False)

    state = _normal_turn_state(run_id)
    state["expert_consultation_mode"] = False
    state["expert_pending_question"] = ""
    state["expert_blocking_reason"] = ""
    state["user_retry_count"] = 0

    result = cela_main.generate_user_utterance_node(state)

    assert result["user_wrote_agreement"] is True
    assert result["chat_history"][-1]["role"] == "user"
    assert result["chat_history"][-1]["content"] == "次のタスクへ進んでください。"
