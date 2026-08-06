"""
BL-146: `write_agreement`はtask_idがtask_plannerの正式計画に実在するか（BL-131）しか検証しておらず、
`state["current_task_id"]`（BL-125がタスク遷移をブロックしている対象そのもの）とは一切照合していなかった。
そのため、BL-125が`current_task_id`のタスク遷移をブロックしていても、Expert等は`write_agreement`の
`task_id`引数に任意の他タスクを指定することで、実際にDeliverableを書き込めてしまっていた
（`log/2026-08-02/0832`のドライランで、ブロック中のcurrent_task_id以外のタスクへ実際に成果物が
書き込まれ、Detectorがそれを正式な成果物としてレビューしてしまう実害を確認）。

本テストは以下を検証する:
1. entry_type='Directive'/'Deliverable'かつaction_type != 'SUPERSEDE'で、task_idが
   実効上の現在タスク（`_get_current_task`のフォールバックと同一ロジック）と一致しない場合は拒否する。
2. action_type='SUPERSEDE'はこのゲートの対象外（他タスクの内容を正規に改訂する既存の正当な経路、
   BL-062/080/084）。
3. `current_task_id`が空文字（初回タスク進行中、`_resolve_task_transition`がまだ一度も発火していない
   状態）でも、`current_phase`の先頭タスクへの書き込みは正しく許可される（回帰防止：これを誤ると
   初回タスクの正当な書き込みまで全滅する）。
4. ロールに依存しないこと。
5. entry_type='Decision'はこのゲートの対象外（BL-131と同じスコープ）。

参照: docs/design/back_log/issue_backlog.md BL-146。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl146.db")
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
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
]


def test_deliverable_write_to_other_task_is_rejected_while_blocked(db_conn):
    """BL-125でcurrent_task_id=task_1_1のままブロックされていても、write_agreementの
    task_id引数にtask_1_2を指定すればすり抜けていた実害（0832ログ）の再現・修正確認。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_2の成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_2",
        },
        state,
    )
    assert result["success"] is False
    assert "task_1_2" in result["error"] and "task_1_1" in result["error"]


def test_supersede_to_other_task_is_exempt_from_the_gate(db_conn):
    """SUPERSEDEは後続タスクでの検討結果、先発タスクの成果物を改訂する正規の経路であり、
    このゲートの対象外（レビューコメント①への回答）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_2",
             "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "SUPERSEDE", "status": "Proposed", "topic": "task_1_1成果物の訂正",
            "decision_what": "Y" * 500, "reason_why": "後続タスクの検討で誤りが判明したため",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True


def test_first_task_write_is_accepted_when_current_task_id_is_still_empty(db_conn):
    """current_task_idが空文字（初回タスク進行中、_resolve_task_transitionが未発火）でも、
    current_phaseの先頭タスクへの書き込みは実効上のcurrent_taskとして正しく許可される。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "",
             "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True


def test_gate_applies_regardless_of_caller_role(db_conn):
    """[BL-169] userはentry_type='Deliverable'をaction_type='CREATE'では新規作成できなくなった
    （その組み合わせは別のより早い権限チェックで拒否される）ため、ここではUPDATEを使って
    「ロールを問わずcurrent_task_idゲートが適用される」ことを検証する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "task_1_2の成果物(user)",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_2",
        },
        state,
    )
    assert result["success"] is False
    assert "task_1_1" in result["error"]


def test_decision_entry_type_is_exempt_from_the_gate(db_conn):
    """entry_type='Decision'はBL-131のtask_id実在チェック同様、このゲートの対象外。
    [BL-172] statusは意図的に"Proposed"を使う（"Approved"だと、対象task_idにExpert作成の
    Deliverableが実在するかを見る別の権限チェック(BL-172)に引っかかり、本テストが検証したい
    BL-146ゲートの挙動と無関係な理由で失敗するため）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "全体方針の決定",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Decision",
        },
        state,
    )
    assert result["success"] is True


def test_gate_skipped_when_no_current_task_context_available(db_conn):
    """current_phase/phasesを持たない簡易stateではフェイルオープンでゲートをスキップする
    （既存のtest_bl131系フィクスチャへの非回帰を保証）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "current_phase不明時の成果物",
            "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_2",
        },
        {"run_id": run_id, "phases": _PHASES},
    )
    assert result["success"] is True
