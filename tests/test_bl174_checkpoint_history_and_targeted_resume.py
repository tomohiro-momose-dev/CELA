"""
BL-174: LangGraphのcheckpointer（BL-105で導入済みの`SqliteSaver`）は、実はノード完了
（superstep）ごとに毎回別のcheckpoint_idでスナップショットを自動保存しており、
`app.get_state_history(config)`で全履歴を取得、任意の過去checkpoint_idを指定して
`app.get_state`/`app.stream`に渡せば、それ以前のノードを再実行せずそこから再開できる
（LangGraph公式のtime travel/replay）。ユーザーからの提案「ノードごとに自動スナップショット
を取り、再開時に一覧から任意のスナップショットを選べないか（ほぼgitに近い）」を受け、
この既存機能をCELAのCLIから使えるようにした：
- `--list-checkpoints RUN_ID`: 履歴をgit log風に一覧表示する新規関数`list_checkpoints`
- `--resume RUN_ID --checkpoint-id CHECKPOINT_ID`: 最新ではなく指定したcheckpointから再開する
  （`run_ai_vs_ai_loop`への`checkpoint_id`引数追加）

参照: docs/design/back_log/issue_backlog.md BL-174。実LLM API呼び出しは伴わない
（CELAの実グラフとは独立した最小の合成グラフ、および`build_graph`をスタブに差し替えた
フェイクグラフで検証する）。
"""

import os
import re
import sqlite3
import sys
from typing import TypedDict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import END, StateGraph


# ---------------------------------------------------------------------------
# list_checkpoints: CELAの実グラフとは独立した最小の合成グラフ（tests/test_checkpoint_resume.py
# と同型のnode_a/node_b＋条件分岐ループ＋END）で、実際にcheckpointerへ複数ステップぶんの
# 履歴を書き込んだ上で読み出す。
# ---------------------------------------------------------------------------

class _SyntheticState(TypedDict):
    steps: list[str]
    loop_count: int


def _build_synthetic_graph(checkpointer):
    def node_a(state):
        return {"steps": state["steps"] + ["a"], "loop_count": state["loop_count"] + 1}

    def node_b(state):
        return {"steps": state["steps"] + ["b"], "loop_count": state["loop_count"]}

    def route(state):
        return "node_b" if state["loop_count"] >= 2 else "node_a"

    g = StateGraph(_SyntheticState)
    g.add_node("node_a", node_a)
    g.add_node("node_b", node_b)
    g.set_entry_point("node_a")
    g.add_conditional_edges("node_a", route, {"node_a": "node_a", "node_b": "node_b"})
    g.add_edge("node_b", END)
    return g.compile(checkpointer=checkpointer)


def test_list_checkpoints_prints_git_log_style_history(tmp_path, monkeypatch, capsys):
    # [BL-174] get_state_historyの`next`/`metadata["writes"]`の復元はcheckpointの生データ
    # だけでなくグラフのトポロジー（ノード名・チャネル定義）にも依存するため、書き込み時と
    # 同じノード構成（node_a/node_b）で読み出す必要がある。list_checkpoints自身が渡す
    # checkpointerで合成グラフをコンパイルして返すよう、build_graphをスタブ化する。
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)

    conn = sqlite3.connect(ckpt_path, check_same_thread=False)
    checkpointer = SqliteSaver(conn)
    checkpointer.setup()
    app = _build_synthetic_graph(checkpointer)
    runtime_config = {"configurable": {"thread_id": "t-history"}}
    for _ in app.stream({"steps": [], "loop_count": 0}, config=runtime_config, stream_mode="values"):
        pass
    conn.close()

    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: _build_synthetic_graph(checkpointer))

    cela_main.list_checkpoints("t-history")
    out = capsys.readouterr().out

    assert "📜 [Checkpoints] run_id=t-history" in out
    assert "古い順" in out
    assert "checkpoint_id=" in out
    assert "完了:" in out and "次:" in out
    assert "node_a" in out and "node_b" in out
    assert "--checkpoint-id <checkpoint_id>" in out

    # [ユーザー要望] 表示順が古い順（step昇順）になっていること。
    steps = [int(m) for m in re.findall(r"step=(-?\d+)", out)]
    assert steps == sorted(steps), f"stepが昇順（古い順）で並んでいない: {steps}"


def test_list_checkpoints_reports_missing_run_id(tmp_path, monkeypatch, capsys):
    ckpt_path = str(tmp_path / "ckpt.db")
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", ckpt_path)

    cela_main.list_checkpoints("存在しないrun_id")
    out = capsys.readouterr().out
    assert "見つかりませんでした" in out


# ---------------------------------------------------------------------------
# run_ai_vs_ai_loopのcheckpoint_id配線（build_graphをスタブに差し替え、実グラフ・実LLM
# 呼び出しなしで検証する。tests/test_checkpoint_resume.pyの_FakeSnapshot/_FakeCompiledGraph
# と同型のパターン）
# ---------------------------------------------------------------------------

class _FakeSnapshot:
    def __init__(self, values, next_nodes):
        self.values = values
        self.next = next_nodes


class _FakeCompiledGraph:
    def __init__(self, snapshot, stream_states):
        self._snapshot = snapshot
        self._stream_states = list(stream_states)
        self.get_state_configs: list[dict] = []
        self.stream_configs: list[dict] = []

    def get_state(self, runtime_config):
        self.get_state_configs.append(runtime_config)
        return self._snapshot

    def stream(self, _next_input, config, stream_mode="values"):
        self.stream_configs.append(config)
        state = self._stream_states.pop(0) if self._stream_states else dict(self._snapshot.values)
        return iter([state])


def test_run_ai_vs_ai_loop_rejects_checkpoint_id_without_resume(monkeypatch, capsys):
    def _should_not_be_called(**_kwargs):
        raise AssertionError("checkpoint_idのみ指定・resume_run_id無しの場合、build_graphを呼ぶ前に拒否すべき")

    monkeypatch.setattr(cela_main, "build_graph", _should_not_be_called)

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30, "reflection_interval": 3,
                "agent_has_guardrail": True},
        resume_run_id=None,
        checkpoint_id="some-checkpoint-id",
    )

    assert "--checkpoint-idは--resume" in capsys.readouterr().out


def test_run_ai_vs_ai_loop_passes_checkpoint_id_into_get_state_config(tmp_path, monkeypatch):
    snapshot = _FakeSnapshot(
        values={"db_path": str(tmp_path / "cela.db"), "turn_count": 5, "max_turns": 0, "halt": False},
        next_nodes=(),
    )
    fake_graph = _FakeCompiledGraph(snapshot, stream_states=[])
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30, "reflection_interval": 3,
                "agent_has_guardrail": True},
        resume_run_id="run-x",
        checkpoint_id="ckpt-abc",
    )

    assert len(fake_graph.get_state_configs) == 1
    assert fake_graph.get_state_configs[0]["configurable"]["checkpoint_id"] == "ckpt-abc"
    assert fake_graph.get_state_configs[0]["configurable"]["thread_id"] == "run-x"


def test_run_ai_vs_ai_loop_drops_checkpoint_id_after_first_stream_call(tmp_path, monkeypatch):
    """[BL-174] 核心の回帰テスト: 指定checkpoint_idは最初のapp.stream()呼び出しにのみ使い、
    2ターン目以降はthread_idのみのconfigへ切り替わること（固定したままだと毎ターン同じ
    過去の分岐点から再フォークし続けてしまい前進しない）。"""
    snapshot = _FakeSnapshot(
        values={"db_path": str(tmp_path / "cela.db"), "turn_count": 1, "max_turns": 2, "halt": False},
        next_nodes=("some_node",),  # pending_resume_drain=True -> 最初のnext_inputはNone
    )
    turn1_state = {"turn_count": 1, "max_turns": 2, "halt": False, "is_completed": False, "discussion_status": "continuing"}
    turn2_state = {"turn_count": 2, "max_turns": 2, "halt": False, "is_completed": False, "discussion_status": "continuing"}
    fake_graph = _FakeCompiledGraph(snapshot, stream_states=[turn1_state, turn2_state])
    monkeypatch.setattr(cela_main, "build_graph", lambda checkpointer=None: fake_graph)
    monkeypatch.setattr(cela_main, "CELA_CHECKPOINT_DB_PATH", str(tmp_path / "ckpt.db"))
    monkeypatch.setattr(cela_main, "get_decisions_from_db", lambda conn, run_id: [])

    cela_main.run_ai_vs_ai_loop(
        target_goal="テスト目標",
        config={"pattern": 4, "is_stateless_mode": True, "initial_max_turnval": 30, "reflection_interval": 3,
                "agent_has_guardrail": True},
        resume_run_id="run-x",
        checkpoint_id="ckpt-abc",
    )

    assert len(fake_graph.stream_configs) == 2, "max_turns=2で2ターン走るはず"
    assert fake_graph.stream_configs[0]["configurable"].get("checkpoint_id") == "ckpt-abc", (
        "1回目のstream()は指定checkpoint_idから分岐させる必要がある"
    )
    assert "checkpoint_id" not in fake_graph.stream_configs[1]["configurable"], (
        "2回目以降はthread_idのみのconfigへ切り替わり、新しい分岐の最新checkpointを辿るべき"
    )
