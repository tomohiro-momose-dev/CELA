"""
BL-210: `_resolve_task_transition`が、`advances_to_phase_id`が省略された（null）場合に
探索対象フェーズを常にcurrent_phaseへ決め打ちしていたため、フェーズをまたぐタスク遷移
（例: phase_3のtask_3_2からphase_4のtask_4_0）を`call_decision_extractor`が
`advances_to_task_id`だけ正しく抽出し`advances_to_phase_id`をnullのまま返すと、探索対象が
current_phase（phase_3）に固定され、task_4_0はそこに存在しないため「存在しないtask_id」
として拒否され続ける事故が発生した。

`log/2026-08-11/0118`の実ドライランで、Userが「task_3_2を条件付き承認し、次にtask_4_0を
指示する」と明示し、`call_decision_extractor`が8回にわたり
`{"advances_to_phase_id": null, "advances_to_task_id": "task_4_0"}`を正しく抽出したにも
かかわらず、毎回「⚠️ 存在しないtask_id 'task_4_0' への遷移要求を無視しました」で拒否され、
Expertは「実行コンテキストがtask_3_2のまま」として一切前進できず、最終的にReflectionが
「切替拒否の反復＝実質的な停滞」と判定してシステムをHALTさせた。

`_resolve_task_transition`のすぐ下にBL-191で定義済みの`_find_phase_containing_task`
（task_idの所属フェーズを全フェーズ横断で探す）が既に存在していたが、`redirect_backward`
専用の経路でしか使われておらず、この自由文脈`advances_to_task_id`抽出の経路には
配線されていなかった。

対応：`advances_to_phase_id`が省略され`advances_to_task_id`がcurrent_phaseに存在しない
場合、`_find_phase_containing_task`で全フェーズ横断探索してから最終的に「存在しない」と
判定するよう変更した。あわせて、探索で見つかったフェーズがcurrent_phaseと異なる場合は
current_phaseも追従して更新する（advances_to_phase_idが明示されていない場合でも）。

参照: docs/design/back_log/issue_backlog.md BL-210、BL-191、BL-125、BL-176。
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
    db_path = str(tmp_path / "test_bl210.db")
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


_PHASE_3 = {"phase_id": "phase_3", "tasks": [{"task_id": "task_3_1"}, {"task_id": "task_3_2"}]}
_PHASE_4 = {"phase_id": "phase_4", "tasks": [{"task_id": "task_4_0"}, {"task_id": "task_4_1"}]}
_PHASES = [_PHASE_3, _PHASE_4]


def _base_state(run_id: str, current_task_id: str = "task_3_2") -> dict:
    return {
        "run_id": run_id,
        "phases": _PHASES,
        "current_phase": _PHASE_3,
        "current_task_id": current_task_id,
        "task_transition_blocked_issue_topics": [],
        "task_transition_blocked_unapproved_task_id": "",
    }


def _insert_approved_deliverable(conn, run_id, task_id, phase_id="phase_3", seq=1):
    """[BL-176] 遷移元task_idの承認成立が無いとゲートで拒否されるため用意する。"""
    agreement_id = f"AG-TEST-{seq:06d}"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, evidence, is_frozen, "
        "internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, "CREATE", "Approved", f"{task_id}の成果物", "X" * 300, "r", "expert", "Deliverable",
         phase_id, task_id, "[]", "{}", time.time(), "", 0, None, run_id),
    )
    conn.commit()


# ---------------------------------------------------------------------------
# 1. 実インシデントの再現・修正確認（advances_to_phase_id=null かつ 別フェーズのtask_id）
# ---------------------------------------------------------------------------

def test_cross_phase_task_id_resolves_without_explicit_phase_id(db_conn):
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_2")
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": None, "advances_to_task_id": "task_4_0"}
    )

    assert state["current_task_id"] == "task_4_0", (
        "advances_to_phase_id省略時にフェーズをまたぐtask_idが解決できず、BL-210が再発した"
    )
    assert state["current_phase"]["phase_id"] == "phase_4", (
        "current_task_idは更新されたがcurrent_phaseが追従しておらず、不整合な状態になった"
    )


def test_cross_phase_task_id_with_dotted_notation_resolves_too(db_conn):
    """[BL-039併存確認] ドット区切り表記（task_4.0）でも、フェーズ横断探索は
    正規化後の文字列で機能すること。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_2")
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": None, "advances_to_task_id": "task_4.0"}
    )

    assert state["current_task_id"] == "task_4_0"
    assert state["current_phase"]["phase_id"] == "phase_4"


# ---------------------------------------------------------------------------
# 2. 非退行確認
# ---------------------------------------------------------------------------

def test_same_phase_task_id_still_resolves_without_explicit_phase_id(db_conn):
    """[非退行] 同一フェーズ内の遷移（従来から動いていたケース）が壊れていないこと。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_1")
    state = _base_state(run_id, current_task_id="task_3_1")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": None, "advances_to_task_id": "task_3_2"}
    )

    assert state["current_task_id"] == "task_3_2"
    assert state["current_phase"]["phase_id"] == "phase_3"


def test_unknown_task_id_still_rejected_after_cross_phase_search(db_conn):
    """[非退行] 全フェーズ探索しても存在しないtask_idは、引き続き拒否されること
    （フェイルクローズが失われていないこと）。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_2")
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": None, "advances_to_task_id": "task_9_9"}
    )

    assert state["current_task_id"] == "task_3_2"
    assert state["current_phase"]["phase_id"] == "phase_3"


def test_explicit_phase_id_still_takes_precedence_over_search(db_conn):
    """[非退行] advances_to_phase_idが明示されている場合は、従来通りそちらを優先し、
    全フェーズ探索を経由しないこと（BL-084/BL-146との整合）。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_2")
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_4", "advances_to_task_id": "task_4_0"}
    )

    assert state["current_task_id"] == "task_4_0"
    assert state["current_phase"]["phase_id"] == "phase_4"


def test_bl125_blocking_issue_gate_still_applies_to_cross_phase_transition(db_conn):
    """[非退行] フェーズ横断探索で解決した遷移にも、BL-125の未解決issueブロックが
    引き続き適用されること。"""
    conn, run_id = db_conn
    _insert_approved_deliverable(conn, run_id, "task_3_2")
    cela_main._write_issue_impl(
        {"action_type": "CREATE", "topic": "cross_phase_blocker", "severity": "major",
         "description": "未解決の重大issue"},
        conn, run_id, "detector", task_id="task_3_2", phase_id="phase_3",
    )
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": None, "advances_to_task_id": "task_4_0"}
    )

    assert state["current_task_id"] == "task_3_2", "BL-125ゲートを迂回してしまった"
    assert state["task_transition_blocked_issue_topics"] == ["cross_phase_blocker"]


def test_phase_id_only_transition_without_task_id_still_uses_current_phase_fallback(db_conn):
    """[非退行] advances_to_task_idが無く、advances_to_phase_idだけが指定される
    （タスク不問のフェーズのみ遷移）ケースでも壊れていないこと。"""
    run_id = db_conn[1]
    state = _base_state(run_id, current_task_id="task_3_2")

    cela_main._resolve_task_transition(
        state, {"advances_to_phase_id": "phase_4", "advances_to_task_id": None}
    )

    assert state["current_task_id"] == "task_3_2"  # task_idは変更されない
    assert state["current_phase"]["phase_id"] == "phase_4"
