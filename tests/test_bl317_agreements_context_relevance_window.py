"""
BL-317: agreementsコンテキストを「現在タスク関連＋直近N件」へ有限化する。

実測（run_id=1787890406-1e73a89d）で、`_build_agreements_context_from_db`が生成する文字列が
138,547文字（≈77,000トークン）に肥大化しており、毎ターン・全5ノード呼び出し箇所（call_
orchestrator/call_expert/call_detector/generate_user_utterance x2）へ無条件に丸ごと注入
されていたことが判明した。decision側（`_build_hydrate_context`、別テーブル`decisions`）は
既に`expert_history_window`で窓化済みで、agreements側だけこの対称性が欠けていた。

Freeze機構（is_frozen=1）が実DBで0件（事実上未使用）だったため、単純な直近N件ウィンドウでは
なく「現在タスク自身＋直接依存タスクは無制限、それ以外は直近window件」の関連性優先方式を
採用した（ユーザー選択）。

独立レビューでA〜Jの指摘を受け反映済み。特にA（最重要）: 当初案は生の行（Superseded/
Directive等の表示除外対象も含む）に対して直近window件を数えていたが、実測で直近40 raw行の
うち実際に表示されるのはわずか23件だった（Superseded/Directive混入）。表示フィルタ述語
`_is_agreement_displayable`を`_build_agreements_context`と共有し、表示対象に絞り込んでから
window件数を数える設計へ修正した。

参照: docs/design/back_log/issue_backlog.md BL-317、
      docs/design/back_log/BL-317/BL317_basic_design.md、BL317_review.md。
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
    db_path = str(tmp_path / "test_bl317.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _insert(conn, run_id, id, task_id, entry_type="Decision", status="Approved",
            topic=None, phase_id="phase_1", ts=None):
    cela_main.db_append_agreement({
        "id": id, "action_type": "CREATE", "entry_type": entry_type, "status": status,
        "topic": topic or id, "decision_what": f"{id}の内容", "reason_why": "r",
        "proposed_by": "Agent", "phase_id": phase_id, "task_id": task_id,
        "depends_on": [], "resource_claims": {}, "timestamp": ts if ts is not None else time.time(),
    }, conn, run_id)


# ============================================================
# 1. _select_relevant_agreements 単体
# ============================================================

def test_relevant_task_agreements_unlimited(db_conn):
    """現在タスク自身のagreementsは、windowを超える件数でもすべて残る。"""
    conn, run_id = db_conn
    for i in range(60):
        _insert(conn, run_id, f"AG-cur-{i:03d}", "task_2_1", ts=1000 + i)
    text = cela_main._build_agreements_context_from_db(conn, run_id, current_task_id="task_2_1",
                                                          task_depends_on=[], window=40)
    for i in range(60):
        assert f"AG-cur-{i:03d}の内容" in text or f"AG-cur-{i:03d}" in text


def test_dependent_task_agreements_unlimited(db_conn):
    """task_depends_onに含まれるtask_idのagreementsもすべて残る
    （task_5_1_2→task_5_2_1の実例パターン: 依存タスクの確定値を監査時に参照する）。"""
    conn, run_id = db_conn
    for i in range(50):
        _insert(conn, run_id, f"AG-dep-{i:03d}", "task_5_1_2", ts=1000 + i)
    _insert(conn, run_id, "AG-cur-000", "task_5_2_1", ts=2000)
    text = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_5_2_1", task_depends_on=["task_5_1_2"], window=40
    )
    for i in range(50):
        assert f"AG-dep-{i:03d}" in text


def test_window_counts_displayable_not_raw(db_conn):
    """[独立レビュー指摘A・H] windowは「実際に表示される」行基準でなければならない。
    無関係タスクの直近raw行の大半をSuperseded/Directiveで埋めても、表示対象
    （Decision/Deliverable・非Superseded・非Directive）が正しくwindow件残ることを確認する。
    生の行に対して窓をかける旧実装ではこのテストは通らない（表示対象がwindow未満しか残らない）。
    """
    conn, run_id = db_conn
    _insert(conn, run_id, "AG-cur-000", "task_2_1", ts=100000)
    # 無関係タスクへ、表示対象10件の前後にSuperseded/Directiveを大量に挟む
    ts = 0
    for i in range(30):
        _insert(conn, run_id, f"AG-noise-{i:03d}", "task_9_9", status="Superseded", ts=ts)
        ts += 1
    for i in range(10):
        _insert(conn, run_id, f"AG-disp-{i:03d}", "task_9_9", ts=ts)
        ts += 1
    for i in range(30):
        _insert(conn, run_id, f"AG-directive-{i:03d}", "task_9_9", entry_type="Directive", ts=ts)
        ts += 1

    text = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_2_1", task_depends_on=[], window=10
    )
    for i in range(10):
        assert f"AG-disp-{i:03d}" in text


def test_backward_compat_empty_current_task_id_returns_all(db_conn):
    """current_task_id未指定（既定""）では従来通り全件返る
    （tests/test_bl071_agreement_timestamp_crash.py:57・
    tests/test_bl224_phase2_lineage_consumption.py:237の前提を壊さないことの明示的確認）。"""
    conn, run_id = db_conn
    for i in range(50):
        _insert(conn, run_id, f"AG-{i:03d}", "task_9_9", ts=1000 + i)
    text = cela_main._build_agreements_context_from_db(conn, run_id)
    for i in range(50):
        assert f"AG-{i:03d}" in text


def test_depends_on_empty_string_does_not_leak_unrelated_task(db_conn):
    """[独立レビュー指摘C] depends_onに空文字が混在していても、task_id=""のagreement行が
    誤って関連集合に混入しないことを確認する（BL-318のデータ是正で実際にtask_id=""行を
    1件作成済み——空文字混入の実害は仮説ではない）。
    """
    conn, run_id = db_conn
    _insert(conn, run_id, "AG-cur-000", "task_3_2_1", ts=100000)
    # task_id=""の無関係な行（BL-318のplan_revisionパターンを模す）
    for i in range(50):
        _insert(conn, run_id, f"AG-empty-{i:03d}", "", ts=1000 + i)
    text = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_3_2_1", task_depends_on=["task_2_1", ""],
        window=5,
    )
    # task_id=""の行はwindow=5より前の古いものは切り捨てられ、「無関係」バケット扱いのまま
    # （空文字混入により無制限に昇格していないこと）を確認する
    assert "AG-empty-000" not in text
    assert "AG-empty-049" in text  # 最新5件のうち1つ


def test_task_depends_on_helper_defensive(db_conn):
    """[独立レビュー指摘C] _task_depends_onはNone・欠落・空文字混入いずれでも安全に劣化する。"""
    assert cela_main._task_depends_on({}) == []
    assert cela_main._task_depends_on({"depends_on": None}) == []
    assert cela_main._task_depends_on({"depends_on": []}) == []
    assert cela_main._task_depends_on({"depends_on": ["task_1_1", "", None, "task_2_1"]}) == ["task_1_1", "task_2_1"]


# ============================================================
# 2. 実測サイズ縮小
# ============================================================

def test_filtered_size_smaller_than_unfiltered(db_conn):
    """フィルタ後の文字数が明確に縮小することを確認する
    （AGENTS.md §17.1相当: フィルタ処理を無効化〈window=Noneではなく巨大値で近似〉すると
    差が消えることも併せて確認）。"""
    conn, run_id = db_conn
    for i in range(300):
        task_id = "task_2_1" if i < 20 else f"task_{i % 15}_9"
        _insert(conn, run_id, f"AG-{i:04d}", task_id, ts=1000 + i)

    unfiltered = cela_main._build_agreements_context_from_db(conn, run_id)
    filtered = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_2_1", task_depends_on=[], window=40
    )
    assert len(filtered) < len(unfiltered)
    # フィルタを実質無効化（window=10000）すると差がほぼ消える
    unfiltered_via_huge_window = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_2_1", task_depends_on=[], window=10000
    )
    assert len(unfiltered_via_huge_window) >= len(filtered)


# ============================================================
# 3. 絞り込み明示ノート（ユーザー指摘）
# ============================================================

def test_trimmed_notice_present_when_trimming_occurs(db_conn):
    """絞り込みが実際に発生した場合、返り値にread_agreement誘導の注記が含まれること。"""
    conn, run_id = db_conn
    _insert(conn, run_id, "AG-cur-000", "task_2_1", ts=100000)
    for i in range(50):
        _insert(conn, run_id, f"AG-{i:03d}", "task_9_9", ts=1000 + i)
    text = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_2_1", task_depends_on=[], window=10
    )
    assert "このリストは全件ではありません" in text
    assert "read_agreement" in text


def test_trimmed_notice_absent_when_nothing_trimmed(db_conn):
    """絞り込みが発生しない場合（current_task_id未指定、または全件がwindow内）は
    注記が含まれないこと。"""
    conn, run_id = db_conn
    for i in range(5):
        _insert(conn, run_id, f"AG-{i:03d}", "task_9_9", ts=1000 + i)

    text_no_task_id = cela_main._build_agreements_context_from_db(conn, run_id)
    assert "このリストは全件ではありません" not in text_no_task_id

    text_within_window = cela_main._build_agreements_context_from_db(
        conn, run_id, current_task_id="task_2_1", task_depends_on=[], window=40
    )
    assert "このリストは全件ではありません" not in text_within_window


# ============================================================
# 4. _build_agreements_context_for_state 統合
# ============================================================

def test_build_agreements_context_for_state_uses_current_task_and_depends_on(db_conn):
    conn, run_id = db_conn
    phases = [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1", "depends_on": []}]},
        {"phase_id": "phase_2", "tasks": [{"task_id": "task_2_1", "depends_on": ["task_1_1"]}]},
    ]
    state = {
        "run_id": run_id, "phases": phases,
        "current_phase": phases[1], "current_task_id": "task_2_1",
    }
    for i in range(50):
        _insert(conn, run_id, f"AG-dep-{i:03d}", "task_1_1", ts=1000 + i)
    text = cela_main._build_agreements_context_for_state(conn, state, {"agreements_context_recency_window": 5})
    for i in range(50):
        assert f"AG-dep-{i:03d}" in text  # 依存タスクなので無制限に残る


def test_build_agreements_context_for_state_defaults_window_without_config(db_conn):
    """call_detectorのようにconfigを渡さない呼び出しでも既定window=40で安全に動作する。"""
    conn, run_id = db_conn
    phases = [{"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1", "depends_on": []}]}]
    state = {"run_id": run_id, "phases": phases, "current_phase": phases[0], "current_task_id": "task_1_1"}
    text = cela_main._build_agreements_context_for_state(conn, state)
    assert isinstance(text, str)
