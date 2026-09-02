"""
BL-321: `write_agreement`(entry_type=Deliverable)には、成果物本文の見出しが宣言先task_idと
実際に対応しているかを見るガードが存在しなかった。

実インシデント（`log/2026-08-30/2051/log_no_prompt.md:854-878`、run_id=1787890406-1e73a89d）：
Expertのcurrent_task_idはこの回、正当に`task_1_1`だった。しかしUserの指示は「task_3_2_1
成果物の正式確定」であり、ExpertはBL-146設計（Deliverable書き込みは呼び出し元の
current_task_idにのみ許可）に気づきつつ（Expert自身の思考ログ「I cannot edit the
task_3_2_1 deliverable via edits here...」）、それでも`entry_type=Deliverable,
action_type=CREATE`を強行。結果、本文が丸ごとtask_3_2_1の内容（「# task_3_2_1 車両選定の
前提補完確認」から始まる）であるにもかかわらず、`task_id=task_1_1`のwhiteboard
（`phase_1_task_1_1_V11.md`）として保存された。

BL-146/BL-319はtask_idの「宣言と現在タスクの一致」は見るが、「宣言task_idと本文の中身が
実際に対応しているか」は一切見ていなかった。BL-321は、成果物本文の先頭見出しが宣言先task_idと
異なるtask_idを名指ししている場合に書き込みを拒否する、狭いスコープの安全網を追加する。

参照: docs/design/back_log/BL-321/BL321_basic_design.md、issue_backlog.md BL-321。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 1. `_deliverable_heading_task_id_mismatch` 単体テスト
# ---------------------------------------------------------------------------

def test_matching_heading_returns_none():
    content = "# task_1_1 定量分析レポート\n\n本文…"
    assert cela_main._deliverable_heading_task_id_mismatch(content, "task_1_1") is None


def test_mismatched_heading_returns_the_named_task_id():
    """[実インシデント再現] task_1_1へ書こうとしているのに見出しがtask_3_2_1を名乗っている。"""
    content = "# task_3_2_1 車両選定の前提補完確認（正式確定 Ver.3）\n\n本文…"
    assert cela_main._deliverable_heading_task_id_mismatch(content, "task_1_1") == "task_3_2_1"


def test_no_task_id_mention_in_heading_returns_none():
    """[誤検知回避] 見出しにtask_id言及が無いDeliverable（多くのケース）は対象外。"""
    content = "# 茅野市 地域高齢者移動弱者推計 定量分析レポート\n\n本文…"
    assert cela_main._deliverable_heading_task_id_mismatch(content, "task_1_1") is None


def test_task_id_mention_only_in_body_is_not_flagged():
    """[誤検知回避] 見出しではなく本文中の相互参照（例:「task_3_2_1の前提に依存する」）は
    対象外——見出し1行目のみを見る狭いスコープの安全網であること。"""
    content = "# task_1_1 定量分析レポート\n\n本タスクはtask_3_2_1の前提に依存する。"
    assert cela_main._deliverable_heading_task_id_mismatch(content, "task_1_1") is None


def test_heading_with_hash2_or_hash3_is_detected():
    content = "## task_5_2 待ち時間解析モデル\n\n本文…"
    assert cela_main._deliverable_heading_task_id_mismatch(content, "task_1_1") == "task_5_2"


def test_empty_content_returns_none():
    assert cela_main._deliverable_heading_task_id_mismatch("", "task_1_1") is None


# ---------------------------------------------------------------------------
# 2. `_commit_agreement_from_tool` / `write_agreement`ツール経路 統合テスト
# ---------------------------------------------------------------------------

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl321.db")
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
    {"phase_id": "phase_3", "tasks": [{"task_id": "task_3_2_1"}, {"task_id": "task_3_2_2"}]},
]

_MISMATCHED_CONTENT = "# task_3_2_1 車両選定の前提補完確認（正式確定 Ver.3）\n\n" + "本文。" * 100
_MATCHING_CONTENT = "# task_1_1 定量分析レポート\n\n" + "本文。" * 100


def test_create_with_mismatched_heading_is_rejected(db_conn):
    """[実インシデント再現] current_task_id=task_1_1のまま、他タスクを名乗る本文のCREATEを
    拒否すること（BL-146の一致チェックは通過するが、本文/task_id不整合で拒否される）。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_3_2_1成果物正式確定Ver.3",
            "decision_what": _MISMATCHED_CONTENT, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is False
    assert "task_3_2_1" in result["error"] and "task_1_1" in result["error"]

    assert cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1") is None, (
        "拒否されたはずの内容がwhiteboard_draftsへ書き込まれてしまっている"
    )


def test_create_with_matching_heading_succeeds(db_conn):
    """[非退行] 見出しがtask_idと一致していれば従来通り成功すること。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1成果物",
            "decision_what": _MATCHING_CONTENT, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True, result.get("error")
    assert cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1") is not None


def test_create_with_no_heading_task_id_succeeds(db_conn):
    """[非退行] 見出しにtask_id言及がない一般的な成果物は、従来通りブロックされないこと。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    content = "# 茅野市 地域高齢者移動弱者推計 定量分析レポート\n\n" + "本文。" * 100

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1成果物",
            "decision_what": content, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is True, result.get("error")


def test_update_full_replace_with_mismatched_heading_is_rejected(db_conn):
    """UPDATE(edits未指定・全文置換、not is_whiteboard分岐)でも同じガードが効くこと。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1成果物（初回全文提出）",
            "decision_what": _MISMATCHED_CONTENT, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert result["success"] is False
    assert "task_3_2_1" in result["error"] and "task_1_1" in result["error"]


def test_update_with_edits_path_is_not_covered_by_this_guard(db_conn):
    """[設計上の対象外を確認] UPDATE(edits指定)分岐はBL-265により既存内容の読み取り確認済みが
    前提であり、見出し全体の付け替えが起きる局面ではないため、このガードの対象外とする設計
    判断（docs/design/back_log/BL-321参照）。既存whiteboardへのedits適用自体は、見出し行が
    たまたま他タスクのtask_idを含んでいても、このBL-321ガードでは拒否されないことを確認する
    （BL-146の宛先一致チェックなど、他の既存ガードは引き続き別途働く）。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    # まず正規に見出しの一致するDeliverableを作成する。
    create_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_1_1成果物",
            "decision_what": _MATCHING_CONTENT, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
        },
        state,
    )
    assert create_result["success"] is True
    cela_main._LAST_WHITEBOARD_READS.add("task_1_1")

    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_1_1成果物（更新）",
            "reason_why": "誤りを修正", "entry_type": "Deliverable",
            "phase_id": "phase_1", "task_id": "task_1_1",
            "edits": [{"old_text": "定量分析レポート", "new_text": "定量分析レポート（改訂）"}],
        },
        state,
    )
    assert result["success"] is True, result.get("error")
