"""
BL-264: LLM出力の欠落・不正値によるフォールバックと、意図された既定値としての空文字が
区別できない構造的欠陥への対応。

主エビデンス: schedule_task_focusの`baseline_agreement_id`。兄弟フィールドのtarget_task_id/
companion_task_idは存在検証されるのに対し、baseline_agreement_idは無検証で`.get(..., "")`の
まま保存されていた。LLMがこのフィールドを省略した場合（異常）に空文字となり、対象タスクに
現在アクティブなDeliverable agreementが存在せずcurrent_agreement_idも独立に空文字へ落ちた
場合、2つの独立した空文字が意味なく一致し、_maybe_resume_forward_focus/
_maybe_clear_resolved_companionの自動復帰・自動解消が無期限にブロックされる
（BL-206/210/211/212と同型の「空文字が既定値を貫通する」構造）。

対応：専用センチネル定数`_LLM_FALLBACK_SENTINEL`を新設し、baseline_agreement_idの
フォールバック値として使う。加えて、内部state由来の非文字列型フォールバック
（Category C: `_apply_backward_redirect`のcurrent_phase、`_phase_id_from`の二段フォールバック）
に、到達したら気づけるloud warningを追加する。

参照: docs/design/back_log/issue_backlog.md BL-264、
docs/design/back_log/BL-264/BL264_265_investigation.md。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl264.db")
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


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]},
    {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1"}]},
]


def _base_state(run_id: str, current_task_id: str = "task_2_1", phases=None) -> dict:
    phases = phases if phases is not None else _PHASES
    current_phase = next((p for p in phases for t in p.get("tasks", []) if t["task_id"] == current_task_id), phases[0])
    return {
        "run_id": run_id,
        "phases": phases,
        "current_phase": current_phase,
        "current_task_id": current_task_id,
        "round_count": 1,
        "task_focus_stack": [],
        "task_focus_companion": None,
        "task_focus_redirect_count": 0,
        "task_focus_redirect_notice": "",
        "task_focus_resume_notice": "",
    }


# ============================================================
# 1. センチネル定数自体
# ============================================================

def test_sentinel_is_a_distinctive_nonempty_string():
    """センチネルは空文字・空値ではなく、通常のLLM出力・DB採番IDと衝突しない構造を持つこと。"""
    sentinel = cela_main._LLM_FALLBACK_SENTINEL
    assert isinstance(sentinel, str)
    assert sentinel != ""
    assert "CELA_LLM_FIELD_MISSING" in sentinel


# ============================================================
# 2. 書き込み側: baseline_agreement_id省略時にセンチネルが使われること
# ============================================================

def test_apply_backward_redirect_uses_sentinel_when_baseline_agreement_id_omitted(db_conn):
    """redirect引数がbaseline_agreement_idを省略した場合、stack entryには空文字ではなく
    センチネルが記録されること。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {"target_task_id": "task_1_1", "reason": "テスト"})
    entry = state["task_focus_stack"][0]
    assert entry["baseline_agreement_id"] == cela_main._LLM_FALLBACK_SENTINEL
    assert entry["baseline_agreement_id"] != ""


def test_apply_backward_redirect_keeps_real_baseline_agreement_id(db_conn):
    """baseline_agreement_idが正しく渡された場合は、従来通りその値がそのまま使われること
    （センチネルへの置換は空・欠落時のみ）。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "テスト", "baseline_agreement_id": "AG-REAL-1",
    })
    entry = state["task_focus_stack"][0]
    assert entry["baseline_agreement_id"] == "AG-REAL-1"


def test_apply_joint_focus_uses_sentinel_when_baseline_agreement_id_omitted(db_conn):
    """joint_focusでも同様に、baseline_agreement_id省略時はセンチネルが記録されること。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_joint_focus(state, {"companion_task_id": "task_1_1", "reason": "テスト"})
    companion = state["task_focus_companion"]
    assert companion["baseline_agreement_id"] == cela_main._LLM_FALLBACK_SENTINEL


def test_apply_backward_redirect_logs_warning_when_sentinel_fires(db_conn, capsys):
    """センチネルが実際に発火した際、⚠️ [BL-264]のloud warningが出力されること
    （§13.2のfail-closed原則：静かに握りつぶさない）。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {"target_task_id": "task_1_1", "reason": "テスト"})
    captured = capsys.readouterr()
    assert "⚠️ [BL-264]" in captured.out
    assert "baseline_agreement_id" in captured.out


def test_apply_backward_redirect_no_warning_when_baseline_agreement_id_provided(db_conn, capsys):
    """正常にbaseline_agreement_idが渡された場合はBL-264の警告が出ないこと（過検知しない）。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "テスト", "baseline_agreement_id": "AG-REAL-1",
    })
    captured = capsys.readouterr()
    assert "⚠️ [BL-264]" not in captured.out


# ============================================================
# 3. 回帰テスト本体: 2つの独立した空文字の偶発一致バグが再発しないこと
# ============================================================

def test_bug_baseline_sentinel_prevents_accidental_match_with_empty_current_agreement(db_conn, monkeypatch):
    """【BL-264回帰テスト】baseline_agreement_idが異常により省略され（センチネル化）、かつ
    対象タスクに現在アクティブなDeliverable agreementが存在しない（current_agreement_idも
    独立に空文字）場合、2つの独立した値が意味なく一致して自動復帰が永久にブロックされる
    事故が起きないこと。

    修正前（`_LLM_FALLBACK_SENTINEL`ではなく`""`をフォールバックに使っていた場合）は
    `"" == ""`でTrueとなり、_maybe_resume_forward_focusが「まだ変化なし」と誤判定して
    復帰しなかった。修正後は空文字とセンチネルが構造的に一致しないため、正しく復帰する。
    """
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    # baseline_agreement_idを省略してredirectを適用（センチネルが記録される）
    cela_main._apply_backward_redirect(state, {"target_task_id": "task_1_1", "reason": "テスト"})
    assert state["task_focus_stack"][0]["baseline_agreement_id"] == cela_main._LLM_FALLBACK_SENTINEL

    # 対象タスクは完了相当だが、アクティブなDeliverable agreementは見つからない
    # （current_agreement_idが独立に空文字へ落ちるケースを直接シミュレートする）。
    monkeypatch.setattr(cela_main, "_is_task_completed", lambda *a, **k: True)
    monkeypatch.setattr(cela_main, "_find_active_deliverable_agreement", lambda *a, **k: None)

    cela_main._maybe_resume_forward_focus(state, conn, run_id)

    # 修正後: センチネル("...")と空文字("")は一致しないため、正しく復帰する。
    assert state["current_task_id"] == "task_2_1"
    assert state["task_focus_stack"] == []


def test_bug_companion_sentinel_prevents_accidental_match_with_empty_current_agreement(db_conn, monkeypatch):
    """【BL-264回帰テスト】_maybe_clear_resolved_companion側でも同型の偶発一致が起きないこと。"""
    conn, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_joint_focus(state, {"companion_task_id": "task_1_1", "reason": "テスト"})
    assert state["task_focus_companion"]["baseline_agreement_id"] == cela_main._LLM_FALLBACK_SENTINEL

    monkeypatch.setattr(cela_main, "_is_task_completed", lambda *a, **k: True)
    monkeypatch.setattr(cela_main, "_find_active_deliverable_agreement", lambda *a, **k: None)

    cela_main._maybe_clear_resolved_companion(state, conn, run_id)

    assert state["task_focus_companion"] is None


# ============================================================
# 4. Category C: 内部state由来の非文字列型フォールバックのloud failure化
# ============================================================

def test_apply_backward_redirect_warns_when_current_phase_missing(db_conn, capsys):
    """current_phaseが空の状態（本来到達しないはずの異常経路）でredirect_backwardが
    適用された場合、⚠️ [BL-264]の警告が出ること。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    state["current_phase"] = {}  # 異常状態を直接シミュレート
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "テスト", "baseline_agreement_id": "AG-REAL-1",
    })
    captured = capsys.readouterr()
    assert "⚠️ [BL-264]" in captured.out
    assert "current_phase" in captured.out


def test_apply_backward_redirect_no_warning_when_current_phase_present(db_conn, capsys):
    """current_phaseが正常に設定されている通常時は、この警告が出ないこと（過検知しない）。"""
    _, run_id = db_conn
    state = _base_state(run_id, current_task_id="task_2_1")
    cela_main._apply_backward_redirect(state, {
        "target_task_id": "task_1_1", "reason": "テスト", "baseline_agreement_id": "AG-REAL-1",
    })
    captured = capsys.readouterr()
    assert "current_phaseが空でした" not in captured.out


def test_phase_id_from_returns_state_value_when_present():
    """通常時: state["current_phase"]にphase_idがあれば、それがそのまま返ること。"""
    state = {"current_phase": {"phase_id": "phase_7"}}
    assert cela_main._phase_id_from(state) == "phase_7"


def test_phase_id_from_falls_back_to_global_silently_when_available(monkeypatch, capsys):
    """state側が空でも、モジュールglobal _CURRENT_PHASE_IDが設定済みならそれを返し、
    警告は出さないこと（正常なフォールバック経路）。"""
    monkeypatch.setattr(cela_main, "_CURRENT_PHASE_ID", "phase_9")
    result = cela_main._phase_id_from({"current_phase": {}})
    assert result == "phase_9"
    captured = capsys.readouterr()
    assert "⚠️ [BL-264]" not in captured.out


def test_phase_id_from_warns_when_both_sources_empty(monkeypatch, capsys):
    """【BL-264回帰テスト】state側・モジュールglobal双方が空の場合（本来到達しないはずの
    異常経路）、空文字を返しつつ⚠️ [BL-264]の警告を出すこと。これはBL-161の"or"パターン
    自体のフォールバック値が汚染されうる二次リスクへの対応。"""
    monkeypatch.setattr(cela_main, "_CURRENT_PHASE_ID", "")
    result = cela_main._phase_id_from({"current_phase": {}})
    assert result == ""
    captured = capsys.readouterr()
    assert "⚠️ [BL-264]" in captured.out
    assert "_phase_id_from" in captured.out
