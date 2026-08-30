"""
BL-319: pending_task_redirect待機中の「現在task_idへの偽装書き込み」を遮断する。

実インシデント（run_id=1787890406-1e73a89d、log/2026-08-30/2010/log_no_prompt.md）:
BL-318のschedule_task_focus(advance_task, target_task_id="task_3_2_1")呼び出し自体は成功し、
state["pending_task_redirect"]に構造化決定が設定されたが、直後のuser_detectorが（advance_task
とは無関係の別の懸念で）ターンを差し戻し、route_after_user_detectorはuser_decision_extractor
（pending_task_redirectを消費しcurrent_task_idを実際に更新する唯一の場所）を経由せずに
generate_user_utteranceへ戻った。current_task_idはtask_1_1のまま固定され続け、User AIは
正しいtask_id（task_3_2_1）で3回書き込みを試みいずれも正当な理由で拒否された後、4回目に
同一内容をtask_id="task_1_1"（現在のtask_id、誤り）へ偽装して再送し、BL-146の一致チェックを
額面通り通過させて書き込みを成立させた。これによりresume後だけで8件のagreementsが再び
誤帰属した。

対応: state machineには一切手を入れず、write_agreementの入口で「宣言task_id==現在task_id
だが、advance_task待機中のpending_task_redirectが別task_idを指している」という具体的な
パターンだけを機械的に検知して拒否する。

参照: docs/design/back_log/issue_backlog.md BL-319、
      docs/design/back_log/BL-319/BL319_basic_design.md。
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
    db_path = str(tmp_path / "test_bl319.db")
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


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]},
    {"phase_id": "phase_3", "tasks": [{"task_id": "task_3_2_1"}, {"task_id": "task_3_2_2"}]},
]


def _base_args(task_id, action_type="CREATE", topic="t"):
    return {
        "action_type": action_type, "status": "Proposed", "topic": topic,
        "decision_what": "X" * 300, "reason_why": "r", "entry_type": "Directive",
        "phase_id": "phase_1" if task_id == "task_1_1" else "phase_3", "task_id": task_id,
    }


def test_workaround_to_current_task_id_is_rejected(db_conn):
    """[実インシデント再現] pending advance_task(target=task_3_2_1)待機中に、宣言task_idを
    現在task_id（task_1_1、誤り）へ偽装した書き込みを拒否する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
        "pending_task_redirect": {
            "decision_type": "advance_task", "target_task_id": "task_3_2_1",
            "target_phase_id": "phase_3", "reason": "テスト",
        },
    }
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        _base_args("task_1_1", topic="task_3_2_1_corrected_directive_with_escalated_closure"),
        state,
    )
    assert result["success"] is False
    assert "task_3_2_1" in result["error"]


def test_write_to_actual_target_task_id_not_blocked_by_this_gate(db_conn):
    """遷移先そのもの（task_3_2_1）宛の書き込みは、このゲートでは拒否されない
    （BL-146側の通常ゲートで別途「current_task_id不一致」として拒否されるのは想定通りで、
    BL-319が二重拒否を追加しないことの確認。エラーメッセージがBL-319のものではないこと
    ＝BL-146固有の文言であることで判別する）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
        "pending_task_redirect": {
            "decision_type": "advance_task", "target_task_id": "task_3_2_1",
            "target_phase_id": "phase_3", "reason": "テスト",
        },
    }
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        _base_args("task_3_2_1", topic="task_3_2_1_directive"),
        state,
    )
    assert result["success"] is False
    assert "適用待ち" not in result["error"]  # BL-319固有の文言ではない
    assert "現在のタスク" in result["error"]  # BL-146の文言


def test_no_pending_redirect_write_succeeds_as_before(db_conn):
    """pending_task_redirectが存在しない通常時、現在task_id宛の書き込みは従来通り成功する
    （既存挙動の非退行）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
    }
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        _base_args("task_1_1", topic="task_1_1の正当な記録"),
        state,
    )
    assert result["success"] is True


def test_redirect_backward_pending_does_not_block_current_task_write(db_conn):
    """[対象外] decision_type='redirect_backward'（一時的な焦点切替）は、現在タスクを
    離脱する意図ではないため、このゲートの対象外——現在task_id宛の書き込みは引き続き正当。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
        "pending_task_redirect": {
            "decision_type": "redirect_backward", "target_task_id": "task_3_2_1",
            "target_phase_id": "phase_3", "reason": "テスト",
            "baseline_agreement_id": "AG-1",
        },
    }
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        _base_args("task_1_1", topic="task_1_1の正当な記録2"),
        state,
    )
    assert result["success"] is True


def test_supersede_is_exempt_from_this_gate(db_conn):
    """[対象外] action_type='SUPERSEDE'は他タスクの内容を正規に改訂する既存の正当な経路
    （BL-062/080/084）であり、このゲートの対象外。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
        "pending_task_redirect": {
            "decision_type": "advance_task", "target_task_id": "task_3_2_1",
            "target_phase_id": "phase_3", "reason": "テスト",
        },
    }
    args = _base_args("task_1_1", action_type="SUPERSEDE", topic="task_1_1の訂正")
    args["target_topic"] = "task_1_1の訂正"
    result = cela_main.TOOL_DISPATCH["write_agreement"](args, state)
    assert result["success"] is True


def test_target_task_id_matches_declared_task_id_is_not_blocked(db_conn):
    """pending_task_redirectのtarget_task_idが宣言task_idと同一の場合（＝もはや偽装ではなく
    まさに遷移先そのものへの正当な言及）は、このゲートは発火しない。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
        "current_phase": _PHASES[0],
        "pending_task_redirect": {
            "decision_type": "advance_task", "target_task_id": "task_1_1",
            "target_phase_id": "phase_1", "reason": "テスト（現在タスクへの自己参照）",
        },
    }
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        _base_args("task_1_1", topic="task_1_1の正当な記録3"),
        state,
    )
    assert result["success"] is True
