"""
BL-214: 「現在のタスクは何か」の解決が一部経路で生の`state["current_task_id"]`のままだった。

`current_task_id`の唯一の書き手は`_resolve_task_transition`（BL-024）であり、最初のタスク遷移が
発生するまで空文字のままである。BL-146はこれを`_effective_current_task_id_from`
（current_phase先頭タスクへのフォールバック）で解決したが、その規則は`write_agreement`の
ゲート経路にしか適用されておらず、他経路へ波及していなかった（AGENTS.md §15.1 の再発）。

実害（`log/2026-08-11/2030`, run_id=1786436794-a9d79ae6 で実測）:
1. `generate_user_utterance`の`_CURRENT_TASK_ID`が空 → BL-177/178の承認検証が使う
   `_is_task_completed`が常にFalse → 各フェーズの先頭タスクで正常な承認が必ず
   `ApprovalRecordingFailed`へ落ち、3回分のLLM呼び出しが毎回無駄になっていた。
2. `TOOL_DISPATCH["write_issue"]`が`_task_id_from(state)`（＝生の値）を渡し、
   `_write_issue_impl`が`args["task_id"]`を完全に無視していたため、LLMが正しく
   `"task_id": "task_1_1"`を送っていても空文字で保存されていた（実runの8件全て）。
   これによりBL-125遷移ゲート／BL-144滞留追跡／BL-145再構成／BL-194 actionableが
   軒並み無効化されていた。

本テストは以下を検証する:
1. `_task_id_from`が`current_task_id=""`でもcurrent_phase先頭タスクを返すこと（S1）
2. 設定済みの`current_task_id`を優先すること（非退行）
3. `write_issue`が`args["task_id"]`を尊重すること（S3）
4. `write_issue`が`args`未指定なら実効解決値で保存すること（S3）
5. 実在しないtask_idの申告は採用せず実効値へ倒すこと（S3の[CONSTRAINT]）
6. 初回タスクで起票したissueがBL-125遷移ゲートに正しく検出されること（下流影響の回帰）
7. `_is_task_completed("")`が警告を出すこと（S5）
8. 実インシデント再現: 初回タスクでDeliverableをApprovedにした直後、BL-177/178が使う
   `_is_task_completed(_CURRENT_TASK_ID)`が成功と判定すること
9. 配線固定: `generate_user_utterance`のソースに生の`current_task_id`読みが残っていないこと
10. 非退行: `_resolve_task_transition`の`departing_task_id`は生の値のままであること（例外）

参照: docs/design/back_log/BL-214/BL214_basic_design.md。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
    {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1"}]},
]


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl214.db")
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


def _first_task_state(run_id):
    """初回タスク進行中（_resolve_task_transitionが未発火）のstate。"""
    return {"run_id": run_id, "phases": _PHASES, "current_task_id": "",
            "current_phase": _PHASES[0]}


# --- S1: _task_id_from の一元化 ---------------------------------------------

def test_task_id_from_resolves_first_task_when_current_task_id_is_empty(db_conn):
    _conn, run_id = db_conn
    cela_main._CURRENT_TASK_ID = ""
    assert cela_main._task_id_from(_first_task_state(run_id)) == "task_1_1"


def test_task_id_from_prefers_explicit_current_task_id(db_conn):
    """非退行: 遷移済みなら生の値がそのまま返る。"""
    _conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_2",
             "current_phase": _PHASES[0]}
    assert cela_main._task_id_from(state) == "task_1_2"


def test_effective_resolution_never_loses_an_explicit_current_task_id(db_conn):
    """[BL-214] 実装中に発見。`current_phase`を持たない簡易state（reflection/detector等）では
    `_get_current_task`が`{}`を返すため、明示的に設定済みのcurrent_task_idまで失われていた。
    この関数を全経路の唯一の解決口にした以上、既知の値を失うことは許されない。"""
    _conn, run_id = db_conn
    cela_main._CURRENT_TASK_ID = ""
    minimal = {"run_id": run_id, "current_task_id": "task_1_1"}  # phases/current_phaseなし
    assert cela_main._effective_current_task_id_from(minimal) == "task_1_1"
    assert cela_main._task_id_from(minimal) == "task_1_1"


def test_effective_resolution_keeps_bl146_phase_first_ordering(db_conn):
    """[非退行] phase由来の解決を優先する順序を変えないこと。current_task_idがcurrent_phaseの
    タスク一覧に存在しない場合はBL-146どおり先頭タスクへ寄せる（BL-190の計画再構成が依存）。"""
    _conn, run_id = db_conn
    cela_main._CURRENT_TASK_ID = ""
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_9_9",
             "current_phase": _PHASES[0]}
    assert cela_main._effective_current_task_id_from(state) == "task_1_1"


# --- S3: write_issue の task_id 決定 -----------------------------------------

def test_write_issue_honors_explicit_task_id_from_args(db_conn):
    """実runの症状の直接再現。LLMが"task_id"を送っているのに空で保存されていた。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main._CURRENT_TASK_ID = ""
    result = cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "license_surrender_rate_derivation",
         "severity": "minor", "description": "d", "task_id": "task_1_1",
         "phase_id": "phase_1"},
        _first_task_state(run_id),
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT task_id, last_seen_task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "license_surrender_rate_derivation"),
    ).fetchone()
    assert row["task_id"] == "task_1_1"
    assert row["last_seen_task_id"] == "task_1_1"


def test_write_issue_falls_back_to_effective_task_id_when_args_omit_it(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main._CURRENT_TASK_ID = ""
    result = cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "no_task_id_supplied",
         "severity": "minor", "description": "d"},
        _first_task_state(run_id),
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "no_task_id_supplied"),
    ).fetchone()
    assert row["task_id"] == "task_1_1"


def test_write_issue_saves_declared_task_id_when_effective_resolution_fails(db_conn):
    """[BL-214] 最後の砦。実効解決が空のときだけ申告値を採用する。
    実効解決の適用漏れが将来再発しても、LLMが明示していれば壊れない二重の防御。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main._CURRENT_TASK_ID = ""
    # current_phase/phases/current_task_idをいずれも持たないstate＝実効解決が不能。
    result = cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "rescued_by_declared_task_id",
         "severity": "minor", "description": "d", "task_id": "task_1_1"},
        {"run_id": run_id},
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "rescued_by_declared_task_id"),
    ).fetchone()
    assert row["task_id"] == "task_1_1"


def test_write_issue_does_not_let_a_declared_task_id_evade_the_transition_gate(db_conn):
    """[REJECTED: args優先] task_idはBL-125遷移ゲートの鍵である。申告を無条件採用すると、
    LLMが別タスクのtask_idを付けるだけで離脱元から未解決issueを外せる抜け道になる。
    現在のタスクと異なる申告は採用せず、警告のうえ現在のタスクで記録する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main._CURRENT_TASK_ID = ""
    result = cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "gate_evasion_attempt", "severity": "major",
         "description": "d", "task_id": "task_1_2"},
        _first_task_state(run_id),   # 実効現在タスクは task_1_1
    )
    assert result["success"] is True
    row = conn.execute(
        "SELECT task_id, last_seen_task_id FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "gate_evasion_attempt"),
    ).fetchone()
    assert row["task_id"] == "task_1_1"
    assert row["last_seen_task_id"] == "task_1_1"
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert "gate_evasion_attempt" in [b["topic"] for b in blocking]


# --- 下流影響の回帰: BL-125 遷移ゲート ---------------------------------------

def test_issue_raised_on_first_task_blocks_transition(db_conn):
    """§3.2の下流影響。task_id=''で保存されていた頃は、離脱元タスクのissueとして
    検出されず、未解決のsevere issueがあっても遷移を止められなかった。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    cela_main._CURRENT_TASK_ID = ""
    cela_main.TOOL_DISPATCH["write_issue"](
        {"action_type": "CREATE", "topic": "unresolved_major_on_first_task",
         "severity": "major", "description": "d", "task_id": "task_1_1"},
        _first_task_state(run_id),
    )
    blocking = cela_main._get_blocking_issues_for_transition(conn, run_id, "task_1_1")
    assert [b["topic"] for b in blocking] == ["unresolved_major_on_first_task"]


# --- S5: 沈黙の解消 -----------------------------------------------------------

def test_is_task_completed_warns_on_empty_task_id(db_conn, capsys):
    conn, run_id = db_conn
    assert cela_main._is_task_completed(conn, run_id, "") is False
    assert "BL-214" in capsys.readouterr().out


# --- 実インシデント再現 -------------------------------------------------------

def test_approval_verification_succeeds_on_first_task(db_conn):
    """実インシデントの再現。初回タスクでExpertの成果物をApprovedへUPDATEした直後、
    BL-177/178の検証が使う`_is_task_completed(_CURRENT_TASK_ID)`が成功と判定すること。
    修正前は`_CURRENT_TASK_ID`が空でDBの中身に関わらず常にFalseだった。"""
    conn, run_id = db_conn
    state = _first_task_state(run_id)

    cela_main._CURRENT_CALLER_ROLE = "expert"
    assert cela_main.TOOL_DISPATCH["write_agreement"](
        {"action_type": "CREATE", "status": "Proposed", "topic": "人口統計・移動弱者実態の整理",
         "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
         "phase_id": "phase_1", "task_id": "task_1_1"},
        state,
    )["success"] is True

    cela_main._CURRENT_CALLER_ROLE = "user"
    assert cela_main.TOOL_DISPATCH["write_agreement"](
        {"action_type": "UPDATE", "status": "Approved", "topic": "人口統計・移動弱者実態の整理",
         "target_topic": "人口統計・移動弱者実態の整理",
         "decision_what": "Approved", "reason_why": "r", "entry_type": "Deliverable",
         "phase_id": "phase_1", "task_id": "task_1_1"},
        state,
    )["success"] is True

    # Stageパイプライン先頭と同じ解決を行う。
    effective = cela_main._effective_current_task_id_from(state)
    assert effective == "task_1_1"
    assert cela_main._is_task_completed(conn, run_id, effective) is True


# --- 配線固定・例外の非退行 ---------------------------------------------------

def test_user_utterance_pipeline_no_longer_reads_raw_current_task_id():
    """[AGENTS.md §17.1] ノード内部の分岐を直接呼べないため、本番コードの配線が
    残っていることをソースで固定する。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert '_CURRENT_TASK_ID = _effective_current_task_id_from(state)' in src
    assert '_CURRENT_TASK_ID = state.get("current_task_id"' not in src


def test_resolve_task_transition_keeps_departing_task_id_raw():
    """[BL-214 例外] departing_task_idは「実際に遷移が起きた履歴」であり、初回は空でなければ
    ならない。実効解決へ寄せるとBL-125/176ゲートが初回遷移で誤発火する。"""
    src = inspect.getsource(cela_main._resolve_task_transition)
    assert 'departing_task_id = state.get("current_task_id", "")' in src
    assert 'departing_task_id = _effective_current_task_id_from(state)' not in src
