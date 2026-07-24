"""
BL-071: 実ドライラン中に発生したクラッシュの回帰テスト。

decision_extractor経由・integrator経由で書き込まれるAgreementの辞書リテラルに
"timestamp"キーが無かったため、db_append_agreementのINSERTでtimestamp列がNULLに
なるagreementsが実際に生成されていた。R5（BL-063）で_build_agreements_contextに
追加したis_frozen優先ソート（decisions_and_deliverables.sort(key=lambda a: (...,
a.get("timestamp", 0)))）は、キーが存在しdefault値0が使われないため、None同士・
Noneとfloatの比較でTypeErrorを送出し、orchestrator_node実行中にプロセス全体を
クラッシュさせていた（実ドライランで発見）。

参照: docs/design/issue_backlog.md BL-071。
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
    db_path = str(tmp_path / "test_bl071.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def test_bl071_build_agreements_context_tolerates_null_timestamp(db_conn):
    """timestampキーを持たない（=DB上NULLになる）agreementが混在していても、
    _build_agreements_context_from_dbがTypeErrorを送出せず正常に文字列を返すこと。"""
    conn, run_id = db_conn
    # timestampキーを意図的に省略（decision_extractor経由の旧バグを再現）
    cela_main.db_append_agreement({
        "id": "AG-1", "action_type": "CREATE", "entry_type": "Decision", "status": "Approved",
        "topic": "timestampなしの合意", "decision_what": "d", "reason_why": "r",
        "proposed_by": "Agent", "phase_id": "phase_1", "task_id": "task_1_1",
        "depends_on": [], "resource_claims": {},
    }, conn, run_id)
    cela_main.db_append_agreement({
        "id": "AG-2", "action_type": "CREATE", "entry_type": "Decision", "status": "Approved",
        "topic": "timestampありの合意", "decision_what": "d", "reason_why": "r",
        "proposed_by": "Agent", "phase_id": "phase_1", "task_id": "task_1_1",
        "depends_on": [], "resource_claims": {}, "timestamp": time.time(),
    }, conn, run_id)

    result = cela_main._build_agreements_context_from_db(conn, run_id)
    assert "timestampなしの合意" in result
    assert "timestampありの合意" in result


def test_bl071_decision_extractor_agreement_literals_include_timestamp():
    """decision_extractor_nodeのソース内で、Agreement構築箇所が"timestamp"キーを
    含んでいること（配線漏れの再発防止確認）。"""
    import inspect
    src = inspect.getsource(cela_main.decision_extractor_node)
    # 2箇所のAgreementリテラル（UPDATE分岐・新規分岐）とも"timestamp": time.time()を含む
    assert src.count('"timestamp": time.time()') >= 2
