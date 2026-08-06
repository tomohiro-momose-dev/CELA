"""
BL-187: `read_verified_fact`の`topic_keyword`検索は`variable_name LIKE '%keyword%' OR
reason LIKE '%keyword%'`というフレーズ全体一致のみで、AIが渡すキーワードの言い回し・語順が
保存済みの文言と一字一句噛み合わないと`not_found`になっていた。ユーザーが「read_verified_fact
で探したいものが見つからない時が散見されます。rag検索を導入して、意味検索をしてはどうか？」と
提案。AIは、1runあたりのverified_facts件数が数十件程度でありembeddingベースのRAGはオーバー
エンジニアリングと判断し、まず(1)トークン分割OR検索、(2)difflibによる近似候補フォールバック、
という新規依存なしの段階的改善を提案し、ユーザーが承認（「トークン分割OR検索＋近似候補
フォールバックを実装して」）。

`get_verified_facts_from_db`（フレーズ全体一致）→ `get_verified_facts_from_db_any_token`
（トークンOR検索、フレーズ一致がnot_foundの場合の第2段階）→ `suggest_similar_verified_facts`
（それでも0件の場合の`did_you_mean`候補提示）という3段階のフォールバックを
`_read_verified_fact_handler`に実装した。`variable_name`指定時はトークン緩和の対象外とする
（一意識別子のため曖昧化させない）。

参照: docs/design/back_log/issue_backlog.md BL-187。実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl187.db")
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


def _seed(conn, run_id, variable_name, value, reason, unit=""):
    cela_main.upsert_verified_fact(
        conn, run_id, variable_name, value, unit,
        source_task_id="task_1_1", source_phase_id="phase_1", confirmed_by="expert",
        reason=reason,
    )


# ---------------------------------------------------------------------------
# _tokenize_topic_keyword
# ---------------------------------------------------------------------------

def test_tokenize_splits_on_whitespace_and_japanese_delimiters():
    tokens = cela_main._tokenize_topic_keyword("予算・オペレーター 台数、コスト")
    assert tokens == ["予算", "オペレーター", "台数", "コスト"]


def test_tokenize_drops_single_char_tokens():
    tokens = cela_main._tokenize_topic_keyword("a b 予算")
    assert tokens == ["予算"]


def test_tokenize_empty_string_returns_empty_list():
    assert cela_main._tokenize_topic_keyword("") == []


# ---------------------------------------------------------------------------
# get_verified_facts_from_db_any_token
# ---------------------------------------------------------------------------

def test_any_token_search_matches_when_only_one_token_hits(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両台数は3台で確定（予算上限に基づく）")

    results = cela_main.get_verified_facts_from_db_any_token(conn, run_id, ["存在しない語", "予算上限"])
    assert len(results) == 1
    assert results[0]["variable_name"] == "vehicle_count"


def test_any_token_search_empty_tokens_returns_empty(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両台数は3台で確定")
    assert cela_main.get_verified_facts_from_db_any_token(conn, run_id, []) == []


# ---------------------------------------------------------------------------
# suggest_similar_verified_facts
# ---------------------------------------------------------------------------

def test_suggest_similar_finds_close_variable_name_word(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "max_vehicle_count", "2", "台数上限は2台")
    _seed(conn, run_id, "budget_cap", "5000", "予算上限は5000万円")

    # "vehicel"（typo）は"vehicle"に近い
    suggestions = cela_main.suggest_similar_verified_facts(conn, run_id, "vehicel")
    assert "max_vehicle_count" in suggestions


def test_suggest_similar_returns_empty_for_no_facts(db_conn):
    conn, run_id = db_conn
    assert cela_main.suggest_similar_verified_facts(conn, run_id, "vehicle") == []


def test_suggest_similar_returns_empty_for_empty_query(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両台数は3台")
    assert cela_main.suggest_similar_verified_facts(conn, run_id, "") == []


# ---------------------------------------------------------------------------
# _read_verified_fact_handler（3段階フォールバック統合）
# ---------------------------------------------------------------------------

def test_handler_exact_phrase_match_still_works(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両台数は3台で確定")

    result = cela_main._read_verified_fact_handler({"topic_keyword": "車両台数"})
    assert isinstance(result, list)
    assert result[0]["variable_name"] == "vehicle_count"


def test_handler_falls_back_to_token_or_search_when_phrase_misses(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両の必要台数は3台（予算上限に基づく試算）")

    # フレーズ全体「予算上限 台数」はそのままでは一致しないが、
    # トークン分割（予算上限／台数）のいずれかでヒットするはず
    result = cela_main._read_verified_fact_handler({"topic_keyword": "予算上限 台数"})
    assert isinstance(result, list)
    assert result[0]["variable_name"] == "vehicle_count"


def test_handler_returns_did_you_mean_when_nothing_matches(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, "max_vehicle_count", "2", "台数上限は2台")

    result = cela_main._read_verified_fact_handler({"topic_keyword": "vehicel"})
    assert isinstance(result, dict)
    assert result["status"] == "not_found"
    assert "max_vehicle_count" in result["did_you_mean"]
    assert "もしかして" in result["message"]


def test_handler_variable_name_lookup_does_not_use_token_relaxation(db_conn):
    """variable_name指定時は一意識別子として扱い、トークン緩和の対象外
    （完全一致しなければdid_you_meanフォールバックへ直行する）。"""
    conn, run_id = db_conn
    _seed(conn, run_id, "vehicle_count", "3", "車両台数は3台")

    result = cela_main._read_verified_fact_handler({"variable_name": "vehicle_cnt"})
    assert isinstance(result, dict)
    assert result["status"] == "not_found"


def test_handler_true_not_found_has_empty_did_you_mean(db_conn):
    conn, run_id = db_conn
    result = cela_main._read_verified_fact_handler({"topic_keyword": "何もない"})
    assert result == {
        "status": "not_found",
        "message": "該当する確定値が見つかりませんでした。",
        "did_you_mean": [],
    }
