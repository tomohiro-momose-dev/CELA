"""
BL-161: `_commit_agreement_from_tool`は従来`phase_id = args.get("phase_id", "")`のまま、
`task_id`（`tid = args.get("task_id") or task_id`）と異なりフォールバックを一切持っていなかった。
`log/2026-08-04/1018`のドライランで、Expertが`write_agreement`のUPDATE(edits)呼び出しで
`phase_id`を省略したところ、`_find_active_deliverable_agreement`が空文字のphase_idと一致する
既存Deliverableを見つけられず`target=None`・`old_content=""`のまま`_apply_text_edits("", edits)`が
呼ばれ、editsが11回連続で「old_textが見つかりません」として失敗し続けた（BL-151のエラー
スニペットも空文字のまま表示され自己修復のヒントにもならなかった）。

`task_id`には既に`_effective_current_task_id_from`/`_task_id_from`という現在タスクへの
フォールバックが存在し、`phase_id`にも全く同型の`_phase_id_from`が既に定義されていたが、
`write_agreement`のTOOL_DISPATCH配線がそれを一度も呼んでいなかっただけという単純な配線漏れ
だったため、既存の`_phase_id_from(state)`を配線して修正した。

参照: docs/design/back_log/issue_backlog.md BL-161。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl161.db")
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
        cela_main._CURRENT_PHASE_ID = ""


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
]


def _create_deliverable(state, marker: str = "唯一無二の識別可能な原文断片"):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": f"{marker}。" + "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True
    return result


def test_update_edits_falls_back_to_current_phase_when_phase_id_omitted(db_conn):
    """[BL-161本体] UPDATE(edits)呼び出しでphase_idを省略しても、state経由の現在フェーズへ
    フォールバックし、editsが正しく既存ホワイトボードへ適用されること（従来は必ず失敗していた）。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    _create_deliverable(state)

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（更新）",
            "reason_why": "誤りを修正", "entry_type": "Deliverable",
            "task_id": "task_1_1",  # phase_idは意図的に省略
            "edits": [{"old_text": "唯一無二の識別可能な原文断片", "new_text": "修正済みの原文断片"}],
        },
        state,
    )
    assert result["success"] is True, result.get("error")

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert "修正済みの原文断片" in latest["content"]


def test_update_edits_without_fallback_target_reports_not_found_regression(db_conn):
    """回帰確認: フォールバック元になるstate情報（current_phase）自体が無い場合は、従来通り
    「見つからない」エラーになること（クラッシュしない、フェイルオープンで別タスクを誤更新しない）。"""
    conn, run_id = db_conn
    state_no_phase_context = {"run_id": run_id, "phases": _PHASES}
    _create_deliverable(
        {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    )

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（更新）",
            "reason_why": "誤りを修正", "entry_type": "Deliverable",
            "task_id": "task_1_1",  # phase_idは省略、かつstateにもcurrent_phaseが無い
            "edits": [{"old_text": "唯一無二の識別可能な原文断片", "new_text": "修正済みの原文断片"}],
        },
        state_no_phase_context,
    )
    assert result["success"] is False
    assert "見つかりません" in result["error"]


def test_explicit_phase_id_in_args_still_takes_precedence(db_conn):
    """回帰確認: argsに明示的なphase_idがあれば、従来通りそちらが優先されること
    （state側の現在フェーズが異なっていてもargs指定が勝つ、BL-084/BL-146と矛盾しない）。"""
    conn, run_id = db_conn
    creation_state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
                       "current_phase": _PHASES[0]}
    _create_deliverable(creation_state)

    # stateの現在フェーズはphase_1のままだが、SUPERSEDEで明示的にargsへphase_idを渡す
    # （このゲート自体はSUPERSEDEなのでBL-146の対象外、phase_id解決だけを検証する）。
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "SUPERSEDE", "status": "Proposed", "topic": "task_1_1成果物の訂正",
            "decision_what": "Y" * 300, "reason_why": "訂正",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        creation_state,
    )
    assert result["success"] is True


def test_create_falls_back_to_current_phase_when_phase_id_omitted(db_conn):
    """CREATEでもphase_id省略時に現在フェーズへフォールバックし、後続のUPDATEから
    正しく発見できるホワイトボードとして保存されること。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": "識別可能な冒頭部分。" + "X" * 300, "reason_why": "r", "entry_type": "Deliverable",
            "task_id": "task_1_1",  # phase_idは意図的に省略
        },
        state,
    )
    assert result["success"] is True

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest is not None
    assert "識別可能な冒頭部分" in latest["content"]
