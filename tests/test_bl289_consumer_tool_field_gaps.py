"""
BL-289: BL-288（read_agreementの6キー欠落）と同型の情報非対称バグが他の消費系ツールにも
存在していた不具合修正（read_plan_draft/read_deliverable_file/trace_lineage）。

ユーザーがBL-288の修正を受け、「書き込みテーブル ↔ 対応する読み取りツール」の全ペアを
テーブル定義（init_db）と実装で突き合わせ、以下3件の欠落を発見した:
- read_plan_draft（get_latest_plan_draft_by_task_id）: author_role/edit_summary/timestamp/
  draft_idが欠落。特にedit_summary（なぜこの版に改訂したか）が欠落していた。
- read_deliverable_file（ホワイトボード経路、get_latest_whiteboard）: contentのみのプレーン
  文字列を返し、author_role/edit_summary/timestamp/draft_idが完全に捨てられていた。
- trace_lineage（_traverse_lineage/_trace_lineage_handler）: created_by/created_at/
  source_task_id/source_phase_id/idが欠落。「なぜこの系譜線が引かれたか」を辿るツール自体が
  線を引いた主体・時期・文脈を返していなかった。

ツール結果はLLMへ渡る直前に必ずjson.dumps(result, ...)される（_query_AI_liveのディスパッチ
ループ）ため、read_deliverable_fileの戻り値をプレーン文字列からdictへ変更しても二重エンコード
の問題は生じない（調査確認済み）。

参照: docs/design/back_log/issue_backlog.md BL-289。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl289.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


@pytest.fixture()
def active_handler_ctx(db_conn):
    """[BL-224test流用] グローバルconn/run_idを差し替えてハンドラを実ツール経路で通す。"""
    conn, run_id = db_conn
    old_conn, old_run = cela_main._DB_CONN, cela_main._CURRENT_RUN_ID
    cela_main._DB_CONN, cela_main._CURRENT_RUN_ID = conn, run_id
    try:
        yield conn, run_id
    finally:
        cela_main._DB_CONN, cela_main._CURRENT_RUN_ID = old_conn, old_run


def _append_agreement(conn, run_id, id_, topic, status="Approved", entry_type="Decision",
                       task_id="task_1_1", phase_id="phase_1", decision_what="dw"):
    cela_main.db_append_agreement(
        {
            "id": id_, "action_type": "CREATE", "status": status, "topic": topic,
            "decision_what": decision_what, "reason_why": "r", "proposed_by": "expert",
            "entry_type": entry_type, "phase_id": phase_id, "task_id": task_id,
            "timestamp": time.time(), "depends_on": [], "resource_claims": {},
        },
        conn, run_id,
    )


# ---------------------------------------------------------------------------
# 1. read_plan_draft（get_latest_plan_draft_by_task_id）
# ---------------------------------------------------------------------------

def test_read_plan_draft_returns_previously_missing_fields(active_handler_ctx):
    conn, run_id = active_handler_ctx
    cela_main.apply_plan_patch(
        conn, run_id, phase_id="phase_1", task_id="task_1_1",
        new_content="計画本文", author_role="task_planner",
        edit_summary="レビュー指摘Aを受けてtask_1_1のacceptance_criteriaを分割",
    )
    result = cela_main.TOOL_DISPATCH["read_plan_draft"]({"task_id": "task_1_1"})
    assert result["content"] == "計画本文"
    assert result["author_role"] == "task_planner"
    assert result["edit_summary"] == "レビュー指摘Aを受けてtask_1_1のacceptance_criteriaを分割"
    assert result["draft_id"]
    assert result["timestamp"] is not None


# ---------------------------------------------------------------------------
# 2. read_deliverable_file（ホワイトボード経路、get_latest_whiteboard）
# ---------------------------------------------------------------------------

def test_read_deliverable_file_whiteboard_path_returns_previously_missing_fields(active_handler_ctx):
    conn, run_id = active_handler_ctx
    _append_agreement(conn, run_id, "AG-1", "topic_a", entry_type="Deliverable",
                       decision_what="WHITEBOARD:phase_1:task_1_1")
    cela_main.apply_whiteboard_patch(
        conn, run_id, phase_id="phase_1", task_id="task_1_1",
        new_content="成果物本文", author_role="expert",
        edit_summary="一次資料の裏付けを追加して確定値へ更新",
    )
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_1_1"}, {"phases": [], "pending_task_ids": ["task_1_1"]}
    )
    assert isinstance(result, dict)
    assert result["content"] == "成果物本文"
    assert result["author_role"] == "expert"
    assert result["edit_summary"] == "一次資料の裏付けを追加して確定値へ更新"
    assert result["draft_id"]
    assert result["timestamp"] is not None


def test_read_deliverable_file_file_path_branch_still_returns_dict_with_content(tmp_path, db_conn, monkeypatch):
    """[BL-289] FILE_PATH経路（実ファイル読み取り）はDBメタデータを持たないため、
    contentキーのみのdictを返す（他のNoneを捏造しない、AGENTS.md §13）。
    base_dirがカレントディレクトリ相対の"log"に固定されているため、実際にlog/配下へ
    一時ファイルを作成してテストする。
    """
    conn, run_id = db_conn
    scratch_dir = Path("log") / "_test_bl289_scratch"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    scratch_file = scratch_dir / "sample.txt"
    scratch_file.write_text("ファイル本文", encoding="utf-8")
    try:
        result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
            {"file_path": str(scratch_file)}, {}
        )
        assert result == {"content": "ファイル本文"}
    finally:
        scratch_file.unlink(missing_ok=True)
        try:
            scratch_dir.rmdir()
        except OSError:
            pass


# ---------------------------------------------------------------------------
# 3. trace_lineage（_traverse_lineage / _trace_lineage_handler）
# ---------------------------------------------------------------------------

def _seed_chain(conn, run_id, edges):
    """edges = [(from_ref, to_ref, rel, reason, created_by, source_task_id, source_phase_id)]"""
    for fr, to, rel, reason, created_by, source_task_id, source_phase_id in edges:
        edge_id = cela_main._new_record_id("REL")
        conn.execute(
            "INSERT INTO relation_edges (id, run_id, from_ref, to_ref, relation_type, reason, "
            "created_by, created_at, source_task_id, source_phase_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
            (edge_id, run_id, fr, to, rel, reason, created_by, time.time(), source_task_id, source_phase_id),
        )
        return edge_id


def test_trace_lineage_returns_previously_missing_fields(active_handler_ctx):
    conn, run_id = active_handler_ctx
    _append_agreement(conn, run_id, "AG-a", "t_a")
    _append_agreement(conn, run_id, "AG-b", "t_b")
    edge_id = _seed_chain(conn, run_id, [
        ("agreement:AG-a", "agreement:AG-b", "derived_from", "根拠あり",
         "expert", "task_1_1", "phase_1"),
    ])
    res = cela_main._trace_lineage_handler({"ref": "agreement:AG-b", "direction": "backward"})
    assert res["status"] == "ok"
    assert len(res["lineage"]) == 1
    edge = res["lineage"][0]
    assert edge["id"] == edge_id
    assert edge["created_by"] == "expert"
    assert edge["created_at"] is not None
    assert edge["source_task_id"] == "task_1_1"
    assert edge["source_phase_id"] == "phase_1"


# ---------------------------------------------------------------------------
# 4. §17.1後段: ソース存在証明
# ---------------------------------------------------------------------------

def test_get_latest_plan_draft_by_task_id_selects_missing_columns_in_source():
    import inspect
    src = inspect.getsource(cela_main.get_latest_plan_draft_by_task_id)
    for col in ("author_role", "edit_summary", "draft_id"):
        assert col in src


def test_get_latest_whiteboard_selects_missing_columns_in_source():
    import inspect
    src = inspect.getsource(cela_main.get_latest_whiteboard)
    for col in ("author_role", "edit_summary", "draft_id"):
        assert col in src


def test_trace_lineage_handler_includes_missing_columns_in_source():
    import inspect
    src = inspect.getsource(cela_main._trace_lineage_handler)
    for col in ("created_by", "created_at", "source_task_id", "source_phase_id"):
        assert col in src
