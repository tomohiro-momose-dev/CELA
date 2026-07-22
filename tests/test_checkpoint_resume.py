"""
一時停止・再開（チェックポイント）機能のオフライン検証項目。実LLM API呼び出しを伴わない。

ユーザー要望: ドライランが長時間化しやすく連続稼働が難しいため、Ctrl+Cでの一時停止と
checkpoint.jsonからの再開を追加した。参照: decision_lineage.md（2026-07-22セッション）。
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_save_and_load_checkpoint_roundtrip(tmp_path):
    checkpoint_path = str(tmp_path / "checkpoint.json")
    state = {
        "goal": "テスト目標", "run_id": "test-run-1", "db_path": "cela.db",
        "turn_count": 3, "chat_history": [{"role": "user", "content": "こんにちは"}],
        "phases": [{"phase_id": "phase_1", "tasks": []}],
    }
    config = {"pattern": 4, "initial_max_turnval": 30, "reflection_interval": 3}

    cela_main._save_checkpoint(checkpoint_path, state, config, current_turn=3)

    loaded_state, loaded_config, loaded_turn = cela_main._load_checkpoint(checkpoint_path)
    assert loaded_state == state
    assert loaded_config == config
    assert loaded_turn == 3


def test_save_checkpoint_is_atomic_no_leftover_tmp_file(tmp_path):
    checkpoint_path = str(tmp_path / "checkpoint.json")
    cela_main._save_checkpoint(checkpoint_path, {"a": 1}, {"b": 2}, current_turn=1)
    assert os.path.isfile(checkpoint_path)
    assert not os.path.isfile(f"{checkpoint_path}.tmp")


def test_save_checkpoint_overwrites_previous_content(tmp_path):
    checkpoint_path = str(tmp_path / "checkpoint.json")
    cela_main._save_checkpoint(checkpoint_path, {"turn_count": 1}, {}, current_turn=1)
    cela_main._save_checkpoint(checkpoint_path, {"turn_count": 5}, {}, current_turn=5)

    with open(checkpoint_path, "r", encoding="utf-8") as f:
        payload = json.load(f)
    assert payload["state"]["turn_count"] == 5
    assert payload["current_turn"] == 5


def test_task_planner_node_skips_replanning_when_phases_already_exist():
    """再開時、turn_count==1のままtask_planner_nodeを再度通っても、
    既にphasesが確定済みならcall_task_plannerを再実行しない（冪等性ガード）。"""
    state = {
        "turn_count": 1,
        "phases": [{"phase_id": "phase_1", "title": "既存フェーズ", "tasks": []}],
        "run_id": "test-run",
    }
    result = cela_main.task_planner_node(state)
    # phasesが上書きされていない（既存の内容のまま）ことを確認
    assert result["phases"] == [{"phase_id": "phase_1", "title": "既存フェーズ", "tasks": []}]
