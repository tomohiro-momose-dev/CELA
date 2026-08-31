"""
BL-325: `--interactive-query`の`read_project_plan`が常にフェーズ・タスク一覧を空で
返していた欠陥の修正。

`read_project_plan`ツールの実体（`_read_project_plan_handler`、cela_main.py:1861）は、
グラフ実行中に各ノードがコピーするモジュールグローバル`_CURRENT_PHASES`（既定値`[]`）を
そのまま返すだけの薄いラッパーである。`--interactive-query`（BL-309）はグラフを一切
経由しない独立プロセス（`_answer_general_query`）のため、`_CURRENT_PHASES`を設定する
機会が一度もなく、`read_project_plan`は常に空リストを返していた（AGENTS.md §15.4:
ツールをツールリストへ配線しただけで、データソース側の配線を忘れていたパターン）。

修正: `list_checkpoints`（cela_main.py:19372〜、checkpointer構築部は19406以降）と同じ
「SqliteSaver + build_graph + app.get_state」パターンで、LangGraph checkpointに
永続化済みの最新`state["phases"]`を独立プロセスから読み込む
（新規関数`_load_phases_from_checkpoint`）。

参照: docs/design/back_log/issue_backlog.md BL-325、BL-309（interactive-query本体）。
実LLM API呼び出しは伴わない。checkpointへの書き込みはtest_bl174と同型の合成グラフを使う。
"""

import os
import sqlite3
import sys
from typing import TypedDict

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph


class _SyntheticState(TypedDict):
    phases: list
    turn_count: int


def _build_synthetic_graph(checkpointer):
    def node_a(state):
        return {"phases": state["phases"], "turn_count": state["turn_count"] + 1}

    g = StateGraph(_SyntheticState)
    g.add_node("node_a", node_a)
    g.set_entry_point("node_a")
    g.add_edge("node_a", END)
    return g.compile(checkpointer=checkpointer)


_SAMPLE_PHASES = [
    {
        "phase_id": "phase_1",
        "title": "フェーズ1: テスト",
        "tasks": [
            {"task_id": "task_1_1", "title": "タスク1", "description": "d",
             "acceptance_criteria": [], "depends_on": [], "owns_variables": []},
        ],
    },
]


def _write_checkpoint(ckpt_path: str, run_id: str, phases: list) -> None:
    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    app = _build_synthetic_graph(checkpointer)
    runtime_config = {"configurable": {"thread_id": run_id}}
    app.invoke({"phases": phases, "turn_count": 0}, config=runtime_config)
    conn.close()


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl325.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    try:
        yield conn
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_PHASES = []


def test_load_phases_from_checkpoint_returns_persisted_phases(tmp_path, monkeypatch):
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _build_synthetic_graph(checkpointer))
    _write_checkpoint(ckpt_path, "run-with-phases", _SAMPLE_PHASES)

    result = cela_main._load_phases_from_checkpoint("run-with-phases")

    assert result == _SAMPLE_PHASES


def test_load_phases_from_checkpoint_returns_empty_for_unknown_run_id(tmp_path, monkeypatch):
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _build_synthetic_graph(checkpointer))

    result = cela_main._load_phases_from_checkpoint("no-such-run")

    assert result == []


def test_answer_general_query_sets_current_phases_before_tool_loop(db_conn, tmp_path, monkeypatch):
    """[BL-325本体] _answer_general_queryは、query_AIのツールループへ入る前に
    _CURRENT_PHASESをチェックポイントから読み込んだ実データへ設定していること。
    read_project_planツールはこのグローバルを参照する薄いラッパーのため、これが
    設定されていれば実際の呼び出しでも正しいフェーズ・タスク一覧が返る。"""
    conn = db_conn
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _build_synthetic_graph(checkpointer))
    _write_checkpoint(ckpt_path, "run-325", _SAMPLE_PHASES)

    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None,
                       light_system_prompt=None, state=None):
        # ツールループへ入った時点でのグローバルの状態を捕捉する（read_project_planが
        # 参照するのと同じタイミング）。
        captured["current_phases_at_call"] = cela_main._read_project_plan_handler({})
        return "回答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    cela_main._answer_general_query(conn, "run-325", "タスク表を見せて")

    assert captured["current_phases_at_call"] == _SAMPLE_PHASES


def test_answer_general_query_falls_back_to_empty_when_no_checkpoint(db_conn, tmp_path, monkeypatch):
    """[非退行] runにまだチェックポイントが無い（例: 起動直後）場合でも例外を出さず、
    従来通り空リスト（＝「まだフェーズ・タスク計画がありません」表示）にフォールバックする。"""
    conn = db_conn
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _build_synthetic_graph(checkpointer))

    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None,
                       light_system_prompt=None, state=None):
        captured["current_phases_at_call"] = cela_main._read_project_plan_handler({})
        return "回答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    cela_main._answer_general_query(conn, "brand-new-run", "タスク表を見せて")

    assert captured["current_phases_at_call"] == []
