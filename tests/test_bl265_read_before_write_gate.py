"""
BL-265: write_agreement/revise_goalのeditsをread-before-writeで機械的にゲートする。

`write_agreement`の`edits`（`whiteboard_drafts`へのold_text/new_text差分編集）は、
プロンプト上の指示文でのみ「先に該当箇所を読んでから編集せよ」と促されているだけで、
機械的な強制が一切なかった。これがBL-080/193/211/212で繰り返された「対象を読まずに
old_textを記憶・憶測で組み立てて失敗する」事故の構造的な土壌だった。

D-206/D-207（thinkツールの毎iteration必須化に付随する生reasoning差し替えの強制、情報破壊的
副作用を理由に撤回）・BL-242/D-211（依存タスク未読の機械的検知は警告に留め強制はしない、と
明示的に決定済み）という2つの既存の却下済み決定との関係整理が必要だったが、本ゲートは
「モデルの推論内容」や「複数タスクをまたぐ意味論的完全性」ではなく、「特定の対象への
read_whiteboard_excerpt呼び出しが、このedits呼び出しより先に実際にあったか」という構造的な
事実（ツール使用順序）のみを機械的に判定するため性質が異なると判断し、ユーザーが機械的拒否
（案A）を選択した（2026-08-25）。

対応：`read_whiteboard_excerpt`成功時に`_LAST_WHITEBOARD_READS`（task_idの集合）へ記録し、
`_write_agreement_impl`の検証チェーン（BL-131のtask_id実在チェックと同じ並び、4.7）で、
`entry_type="Deliverable"`かつ`edits`指定時のみ、同一ターン内の読み取り記録の有無を確認する。
`goal_drafts`側（`revise_goal`）は対象外（`state["goal"]`が近静的に常時注入される性質のため）。

参照: docs/design/back_log/issue_backlog.md BL-265、
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
    db_path = str(tmp_path / "test_bl265.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._LAST_WHITEBOARD_READS = set()
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_PHASE_ID = ""
        cela_main._LAST_WHITEBOARD_READS = set()


_PHASES = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}]}]


def _create_deliverable(run_id, marker: str = "一意に識別可能な原文断片"):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": f"{marker}。" + "X" * 300, "reason_why": "初版",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True, result.get("error")
    return marker, state


# ============================================================
# 1. _read_whiteboard_excerpt_handler: 成功時のみ記録すること
# ============================================================

def test_successful_read_records_task_id(db_conn):
    _, run_id = db_conn
    marker, state = _create_deliverable(run_id)
    result = cela_main.TOOL_DISPATCH["read_whiteboard_excerpt"]({"keyword": marker}, state)
    assert result["ok"] is True
    assert "task_1_1" in cela_main._LAST_WHITEBOARD_READS


def test_keyword_not_found_does_not_record(db_conn):
    """一致0件（ok=False）の場合、Expertは実際の内容を目にしていないため記録しないこと。"""
    _, run_id = db_conn
    _marker, state = _create_deliverable(run_id)
    result = cela_main.TOOL_DISPATCH["read_whiteboard_excerpt"]({"keyword": "存在しないキーワードXYZ"}, state)
    assert result["ok"] is False
    assert "task_1_1" not in cela_main._LAST_WHITEBOARD_READS


def test_ambiguous_match_does_not_record(db_conn):
    """複数一致（一意に特定できない、ok=False）の場合も記録しないこと。"""
    _, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": "X" * 50 + "重複語句" + "Y" * 50 + "重複語句" + "Z" * 50,
            "reason_why": "初版", "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    result = cela_main.TOOL_DISPATCH["read_whiteboard_excerpt"]({"keyword": "重複語句"}, state)
    assert result["ok"] is False
    assert "task_1_1" not in cela_main._LAST_WHITEBOARD_READS


# ============================================================
# 2. write_agreement(edits=...): ゲート本体
# ============================================================

def test_edits_rejected_without_prior_read(db_conn):
    """【BL-265本体】read_whiteboard_excerptでの確認記録が無いまま、editsを使うUPDATEを
    試みると拒否されること。"""
    _, run_id = db_conn
    marker, state = _create_deliverable(run_id)
    assert "task_1_1" not in cela_main._LAST_WHITEBOARD_READS

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（更新）",
            "target_topic": "task_1_1の成果物", "reason_why": "修正",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
            "edits": [{"old_text": marker, "new_text": "修正済みの原文断片"}],
        },
        state,
    )
    assert result["success"] is False
    assert "read_whiteboard_excerpt" in result["error"]

    # DBへ何も書き込まれていないこと（拒否は本当に副作用ゼロであること）
    wb = cela_main.get_latest_whiteboard(cela_main.get_active_conn(), run_id, "phase_1", "task_1_1")
    assert wb["version"] == 1


def test_edits_succeeds_after_prior_read(db_conn):
    """【BL-265本体・正常系】read_whiteboard_excerptで実際に確認した後なら、editsを使う
    UPDATEが成功すること（TOOL_DISPATCH経由の実配線での確認、モックなし）。"""
    _, run_id = db_conn
    marker, state = _create_deliverable(run_id)

    read_result = cela_main.TOOL_DISPATCH["read_whiteboard_excerpt"]({"keyword": marker}, state)
    assert read_result["ok"] is True

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（更新）",
            "target_topic": "task_1_1の成果物", "reason_why": "修正",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
            "edits": [{"old_text": marker, "new_text": "修正済みの原文断片"}],
        },
        state,
    )
    assert result["success"] is True, result.get("error")
    wb = cela_main.get_latest_whiteboard(cela_main.get_active_conn(), run_id, "phase_1", "task_1_1")
    assert wb["version"] == 2
    assert "修正済みの原文断片" in wb["content"]


def test_read_of_different_task_id_does_not_satisfy_gate(db_conn):
    """task_2_2を読んでも、task_1_1へのeditsは満たされないこと（対象を取り違えたなりすまし
    防止、BL-131のtask_id権威主義と同じ考え方）。"""
    _, run_id = db_conn
    marker, state = _create_deliverable(run_id)
    cela_main._LAST_WHITEBOARD_READS.add("task_2_2")  # 別task_idを読んだことにする

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（更新）",
            "target_topic": "task_1_1の成果物", "reason_why": "修正",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
            "edits": [{"old_text": marker, "new_text": "修正済みの原文断片"}],
        },
        state,
    )
    assert result["success"] is False
    assert "read_whiteboard_excerpt" in result["error"]


# ============================================================
# 3. ゲートの適用範囲: edits以外の経路は対象外であること
# ============================================================

def test_create_not_gated(db_conn):
    """CREATEはeditsを使わないため、read記録が無くても拒否されないこと。"""
    _, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1の成果物",
            "decision_what": "新規の成果物本文。" + "X" * 300, "reason_why": "初版",
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True


def test_update_with_full_decision_what_not_gated(db_conn):
    """UPDATEでもeditsを使わず全文（decision_what）で置き換える経路は、本ゲートの対象外
    であること（read-before-write問題はeditsのold_text照合特有の脆弱性であり、全文置換には
    old_textマッチングという失敗モード自体が存在しないため）。"""
    _, run_id = db_conn
    marker, state = _create_deliverable(run_id)
    assert "task_1_1" not in cela_main._LAST_WHITEBOARD_READS

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1の成果物（全文更新）",
            "target_topic": "task_1_1の成果物", "reason_why": "全文修正",
            "decision_what": "全面改訂後の新しい原文。" + "Y" * 300,
            "entry_type": "Deliverable", "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True, result.get("error")


def test_non_deliverable_edits_not_gated(db_conn):
    """entry_type != "Deliverable"の場合、uses_editsがそもそも成立しないため対象外であること
    （editsパラメータはDeliverable専用の差分編集機構のため）。"""
    _, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1", "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "設計判断メモ",
            "decision_what": "アルゴリズムAを採用する。", "reason_why": "性能要件を満たすため",
            "entry_type": "Decision",
        },
        state,
    )
    assert result["success"] is True


# ============================================================
# 4. query_AIによるターンごとのリセット
# ============================================================

def test_last_whiteboard_reads_reset_wired_into_query_ai():
    """次のquery_AI呼び出し（＝新しいターン）の先頭で_LAST_WHITEBOARD_READSがリセットされる
    配線が存在すること（他の_LAST_*一時バッファと同じ「LangGraph単一プロセス同期実行前提」の
    スコープ、_LAST_DELIVERABLE_READ_TASK_IDSと同型のinspect.getsourceパターン）。実際に
    query_AIを実行すると外部API呼び出しの初期化処理まで走ってしまうため、ソース上の配線を
    確認する（他の複数箇所での挙動確認は既存のquery_AI関連テストが担う）。"""
    import inspect
    source = inspect.getsource(cela_main.query_AI)
    assert "_LAST_WHITEBOARD_READS = set()" in source
    global_line = next(line for line in source.splitlines() if line.strip().startswith("global "))
    assert "_LAST_WHITEBOARD_READS" in global_line
