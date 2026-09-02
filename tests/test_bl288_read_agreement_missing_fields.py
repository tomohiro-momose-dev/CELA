"""
BL-288: read_agreement（_query_agreements_core）が返すキーに複数の欠落があった不具合修正。

ユーザーがagreementsテーブルの全カラム（cela_main.py:6660-6668、init_db）と
`_query_agreements_core`が実際に返すキーを突き合わせ、以下6キーの欠落を発見した:
- proposed_by: 誰が書いたか
- internal_thought_process: [R5 F-3.7] status=="Rejected"の場合のみ保存される、
  却下判定の生の思考過程全文（reason_whyより詳細）。BL-279の目的（「なぜこの判断に
  至ったかを能動的に読み返せるようにする」）に最も直結する情報源だった。
- depends_on: 系譜（lineage）を辿るための他agreement IDへのリンク。
- timestamp: 複数エントリの前後関係・絶対時刻。
- is_frozen: 人間が明示的に承認しロックした項目かどうか（🔒）。
- resource_claims: 予算・車両台数等の共有上限リソースの主張構造（BL-041）。
run_idのみは単一run内のため情報価値が無く、意図的な省略として問題ない。

参照: docs/design/back_log/issue_backlog.md BL-288。実LLM API呼び出しは伴わない。
"""

import inspect
import json
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl288.db")
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


def _seed(conn, run_id, *, id_, entry_type="Decision", topic="t", task_id="task_1_1",
          status="Proposed", proposed_by="expert", timestamp=None, depends_on=None,
          resource_claims=None, is_frozen=0, internal_thought_process=None):
    """db_append_agreementはis_frozen/internal_thought_processを常に0/Noneで固定INSERTする
    （BL-288が修正する読み取り側とは無関係な既存の書き込み側の設計）。テストでこれらの
    値を持つ行を作るため、db_append_agreement呼び出し後にUPDATEで直接上書きする。
    """
    cela_main.db_append_agreement(
        {
            "id": id_, "action_type": "CREATE", "status": status, "topic": topic,
            "decision_what": "d", "reason_why": "r", "proposed_by": proposed_by,
            "entry_type": entry_type, "phase_id": "phase_1", "task_id": task_id,
            "timestamp": timestamp if timestamp is not None else time.time(),
            "depends_on": depends_on or [], "resource_claims": resource_claims or {},
        },
        conn, run_id,
    )
    if is_frozen or internal_thought_process is not None:
        conn.execute(
            "UPDATE agreements SET is_frozen=?, internal_thought_process=? WHERE id=? AND run_id=?",
            (1 if is_frozen else 0, internal_thought_process, id_, run_id),
        )


def _one(result):
    assert result["status"] == "ok"
    assert result["count"] == 1
    return result["agreements"][0]


# ---------------------------------------------------------------------------
# 1. 欠落していた各キーが返るようになったこと
# ---------------------------------------------------------------------------

def test_returns_proposed_by(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", proposed_by="goal_essence_analyst")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["proposed_by"] == "goal_essence_analyst"


def test_returns_internal_thought_process_for_rejected_entries(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", status="Rejected",
          internal_thought_process="長い生の思考過程...却下に至った経緯")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["internal_thought_process"] == "長い生の思考過程...却下に至った経緯"


def test_internal_thought_process_is_none_when_not_rejected(db_conn):
    """[R5 F-3.7] status=="Rejected"以外では保存されない（NULLのまま）仕様を、
    キー自体は必ず返る（欠落しない）形で確認する。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", status="Proposed")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    agreement = _one(result)
    assert "internal_thought_process" in agreement
    assert agreement["internal_thought_process"] is None


def test_returns_depends_on_parsed_as_list(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-2", depends_on=["AG-1787800000000-aaaaaa"])
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["depends_on"] == ["AG-1787800000000-aaaaaa"]


def test_returns_resource_claims_parsed_as_dict(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1",
          resource_claims={"vehicle_count": {"phase_id": "phase_1", "value": 5, "total_cap": 8}})
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["resource_claims"] == {
        "vehicle_count": {"phase_id": "phase_1", "value": 5, "total_cap": 8}
    }


def test_returns_timestamp(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", timestamp=1787800000.5)
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["timestamp"] == 1787800000.5


def test_returns_is_frozen_true_when_frozen(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", is_frozen=1)
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["is_frozen"] is True


def test_returns_is_frozen_false_by_default(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["is_frozen"] is False


# ---------------------------------------------------------------------------
# 2. 防御的パース（不正なJSON文字列でもクラッシュしないこと）
# ---------------------------------------------------------------------------

def test_depends_on_malformed_json_falls_back_to_empty_list(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1")
    conn.execute("UPDATE agreements SET depends_on=? WHERE id=?", ("{not valid json", "AG-1"))
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["depends_on"] == []


def test_resource_claims_malformed_json_falls_back_to_empty_dict(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1")
    conn.execute("UPDATE agreements SET resource_claims=? WHERE id=?", ("[not a dict", "AG-1"))
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["resource_claims"] == {}


def test_resource_claims_non_dict_json_falls_back_to_empty_dict(db_conn):
    """旧形式（平坦な配列等）が紛れ込んでも{}へフォールバックする（_aggregate_global_constraints
    と同じ「非dictは静かにスキップ」方針、AGENTS.md §15.1で共有ヘルパー化）。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1")
    conn.execute("UPDATE agreements SET resource_claims=? WHERE id=?", (json.dumps([1, 2, 3]), "AG-1"))
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert _one(result)["resource_claims"] == {}


# ---------------------------------------------------------------------------
# 3. run_idは意図的に除外されたままであること
# ---------------------------------------------------------------------------

def test_run_id_is_intentionally_not_returned(db_conn):
    """run_idは単一run内では情報価値が無いため、意図的にキーへ含めない。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert "run_id" not in _one(result)


# ---------------------------------------------------------------------------
# 4. §17.1後段: ソース存在証明
# ---------------------------------------------------------------------------

def test_all_previously_missing_keys_present_in_source():
    src = inspect.getsource(cela_main._query_agreements_core)
    for key in ("proposed_by", "internal_thought_process", "depends_on",
                "resource_claims", "timestamp", "is_frozen"):
        assert f'"{key}"' in src, f"'{key}'キーが_query_agreements_coreのソースに見当たりません"
