"""
BL-263: ホワイトボードの改版に収束条件（「これ以上編集しない」条件）が存在せず、成果物が
延々と推敲され続けていた問題。

実ドライラン（`log/2026-08-10`〜`08-11`、run_id=1786337594-17df8ff3）で、改版数の中央値が
15〜18であるのに対しtask_2_1が51版・task_8_3が49版まで伸び、しかもターン20最後の書き込みは
「予約方法 → 予約種別」という用語統一のみの2件差分だった。実質的な設計判断ではなく語彙の
磨き込みに最終ターンを消費しており、版数が伸び続けること自体が収束の失敗を示していた。

従来存在したのは`_build_task_scope_context`内の「version>=3なら空回りのサインかもしれない」
というプロンプト注入のみで、強制力もカウント記録もない。AGENTS.md §15.3のとおり、プロンプトの
注意喚起は守られない実績があるため、機械的に数えられる量で検知する必要があった。

対策: `apply_whiteboard_patch`で新バージョン作成後、版数が
`_WHITEBOARD_VERSION_ESCALATION_STEP`（=20）の倍数に達したら、収束していない兆候として
issue_logへ機械的に起票する（caller_role="whiteboard_version_auto"）。topicをtask単位で固定して
既存の`_bump_issue_occurrence`の昇格ラダー（同一topicの2回目でescalatedへ機械昇格、D-079/D-080）
へ相乗りさせるため、Ver.20はminor、Ver.40で自動的にescalatedへ昇格する。

参照: docs/design/back_log/issue_backlog.md BL-263。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl263.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _bump_to_version(conn, run_id, target_version: int, task_id: str = "task_1_1") -> int:
    """target_version版までapply_whiteboard_patchを繰り返す。"""
    version = 0
    for i in range(target_version):
        version = cela_main.apply_whiteboard_patch(
            conn, run_id, "phase_1", task_id, f"# 成果物 第{i + 1}稿\n\n本文。",
            author_role="expert", edit_summary=f"第{i + 1}稿",
        )
    return version


def _stall_issues(conn, run_id, task_id: str = "task_1_1") -> list:
    rows = conn.execute(
        "SELECT topic, raised_by, severity, status, occurrence_count, description "
        "FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, f"whiteboard_not_converging_{task_id}"),
    ).fetchall()
    return [dict(r) for r in rows]


def test_no_escalation_below_threshold(db_conn):
    """[対照] 閾値未満（19版）では起票されないこと。中央値15〜18のタスクを常時鳴らさないため。"""
    conn, run_id = db_conn
    assert _bump_to_version(conn, run_id, 19) == 19
    assert _stall_issues(conn, run_id) == []


def test_escalation_fires_exactly_at_threshold(db_conn):
    """[BL-263本体] 20版に達した時点で、収束していない兆候としてissue_logへ起票されること。"""
    conn, run_id = db_conn
    assert _bump_to_version(conn, run_id, 20) == 20

    issues = _stall_issues(conn, run_id)
    assert len(issues) == 1, "閾値ちょうどで1件だけ起票されるはず"
    assert issues[0]["raised_by"] == "whiteboard_version_auto"
    assert issues[0]["occurrence_count"] == 1
    assert issues[0]["severity"] == "minor"
    assert "20版" in issues[0]["description"]


def test_no_duplicate_escalation_between_thresholds(db_conn):
    """閾値の倍数以外では起票されず、再発カウントが無意味に膨らまないこと。"""
    conn, run_id = db_conn
    _bump_to_version(conn, run_id, 39)

    issues = _stall_issues(conn, run_id)
    assert len(issues) == 1
    assert issues[0]["occurrence_count"] == 1, "20版〜39版の間は再発扱いしないはず"


def test_second_threshold_auto_escalates_via_existing_ladder(db_conn):
    """[BL-263 / D-079・D-080] 40版で2回目の起票となり、既存の昇格ラダーにより
    severity=major・status=escalatedへ機械的に昇格すること（別途の昇格実装を持たない）。"""
    conn, run_id = db_conn
    _bump_to_version(conn, run_id, 40)

    issues = _stall_issues(conn, run_id)
    assert len(issues) == 1
    assert issues[0]["occurrence_count"] == 2
    assert issues[0]["severity"] == "major", "2回目の到達でmajorへ昇格するはず"
    assert issues[0]["status"] == "escalated", "escalation_pin等の意思決定経路へ載るはず"


def test_bl157_suppression_does_not_apply(db_conn):
    """[BL-263] BL-157のdetector_auto昇格抑制の巻き添えにならないこと。版数はDetectorの
    自由記述メモと違い機械的に数えた事実であり、誤検知の余地がないため抑制対象外とした。"""
    conn, run_id = db_conn
    _bump_to_version(conn, run_id, 40)

    issues = _stall_issues(conn, run_id)
    assert issues[0]["raised_by"] != "detector_auto"
    assert issues[0]["status"] == "escalated"


def test_escalation_is_per_task(db_conn):
    """topicがtask単位であり、別タスクの版数と混ざらないこと。"""
    conn, run_id = db_conn
    _bump_to_version(conn, run_id, 20, task_id="task_1_1")
    _bump_to_version(conn, run_id, 5, task_id="task_1_2")

    assert len(_stall_issues(conn, run_id, "task_1_1")) == 1
    assert _stall_issues(conn, run_id, "task_1_2") == []


def test_apply_whiteboard_patch_still_returns_version(db_conn):
    """[非退行] 起票フックを足しても戻り値（新バージョン番号）が変わらないこと。"""
    conn, run_id = db_conn
    assert _bump_to_version(conn, run_id, 3) == 3
    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 3


# --- production側の配線が残っていること（テストだけが通り続ける状態を防ぐ） ---

def test_apply_whiteboard_patch_wires_escalation():
    src = inspect.getsource(cela_main.apply_whiteboard_patch)
    assert "_escalate_stalled_whiteboard(" in src
    assert "_WHITEBOARD_VERSION_ESCALATION_STEP" in src


def test_internal_role_is_permitted_for_create_only():
    """内部専用ロールがCREATEのみ許可であること（RESOLVE等を持たせない）。"""
    src = inspect.getsource(cela_main._check_issue_permission)
    assert '"whiteboard_version_auto": {"CREATE"}' in src
