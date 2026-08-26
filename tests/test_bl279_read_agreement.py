"""
BL-279: entry_type="Decision"/"Directive"のagreementを全文で読み返すツール（read_agreement）
の新設。

BL-277/278/280の実装で、`_build_agreements_context`が`Decision`/`Deliverable`エントリを
毎ターン全ノードへ注入しているが、`reason_why`100字・`decision_what`150字へ切り詰められる
ことが判明した。`entry_type="Deliverable"`は`read_deliverable_file`で全文を能動的に
読み返せるが、`entry_type="Decision"`/`"Directive"`にはその手段がなかった。

ユーザーとの設計対話で、当初の2案（オンデマンド読み取りツール vs 全件非切り詰め注入）の
うちオンデマンド案のみを採用した（`agreements_text`は既にBL-104のプロンプトキャッシュ設計上
「動的ブロック」として扱われており、全件非切り詰め注入案は新たにキャッシュを壊すのではなく
既に壊れている非キャッシュ領域をrun終盤ほど線形に肥大化させる性質のため）。

`task_id`のみ指定した場合、そのtask_id自身が記録した全Decision/Directiveをリストで返す
（同一タスク内検索。依存先タスクへの自動遡及は依存関係の保守コストが大きいため見送った、
ユーザー判断）。

参照: docs/design/back_log/issue_backlog.md BL-279。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl279.db")
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


def _seed(conn, run_id, *, id_, entry_type, topic, decision_what="d", reason_why="r",
          task_id="", status="Proposed", citations=None):
    cela_main.db_append_agreement(
        {
            "id": id_, "action_type": "CREATE", "status": status, "topic": topic,
            "decision_what": decision_what, "reason_why": reason_why, "proposed_by": "expert",
            "entry_type": entry_type, "phase_id": "phase_1", "task_id": task_id,
            "timestamp": time.time(), "citations": citations or [],
        },
        conn, run_id,
    )


# ---------------------------------------------------------------------------
# 1. task_idによる検索（同一タスク内の全件リスト）
# ---------------------------------------------------------------------------

def test_task_id_returns_all_matching_decisions_as_list(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="店舗選定", task_id="task_2_2",
          reason_why="9候補中3店舗を選定")
    _seed(conn, run_id, id_="AG-2", entry_type="Decision", topic="運賃案の選定", task_id="task_2_2",
          reason_why="案Bを採用")
    _seed(conn, run_id, id_="AG-3", entry_type="Decision", topic="無関係な判断", task_id="task_9_9")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_2_2"}, {})
    assert result["status"] == "ok"
    assert result["count"] == 2
    assert {a["topic"] for a in result["agreements"]} == {"店舗選定", "運賃案の選定"}


def test_task_id_only_matches_entries_recorded_under_that_exact_task_id(db_conn):
    """[同一タスク内検索の確認] 依存先タスクのagreementまで自動的に引き込まない。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="上流タスクの判断", task_id="task_1_1")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_2_2"}, {})
    assert result["status"] == "not_found"


def test_task_id_result_includes_full_reason_why_not_truncated(db_conn):
    conn, run_id = db_conn
    long_reason = "候補A・B・Cを比較検討した結果、" + "詳細な理由。" * 30
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="選定理由", task_id="task_3_1",
          reason_why=long_reason)
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_3_1"}, {})
    assert result["agreements"][0]["reason_why"] == long_reason
    assert len(result["agreements"][0]["reason_why"]) > 100  # _build_agreements_contextの100字切り詰めより長い


# ---------------------------------------------------------------------------
# 2. topic_keywordによる検索（フレーズ一致→トークンOR一致フォールバック）
# ---------------------------------------------------------------------------

def test_topic_keyword_phrase_match(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="task_planner_phase_design")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"topic_keyword": "phase_design"}, {})
    assert result["status"] == "ok"
    assert result["count"] == 1


def test_topic_keyword_token_or_fallback(db_conn):
    """フレーズ全体一致が失敗しても、_tokenize_topic_keywordによるトークンOR一致で
    救済されること（_resolve_deliverable_pointerと同型のフォールバック）。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="車両台数の決定")
    tokens = cela_main._tokenize_topic_keyword("車両 予算")
    assert tokens, "トークン化に失敗するとこのテスト自体が無意味になる"
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"topic_keyword": "車両 予算"}, {})
    assert result["status"] == "ok"


def test_no_match_returns_not_found(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"topic_keyword": "存在しないトピック"}, {})
    assert result["status"] == "not_found"


def test_missing_both_args_returns_error(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["read_agreement"]({}, {})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 3. entry_typeフィルタ
# ---------------------------------------------------------------------------

def test_deliverable_excluded_by_default(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Deliverable", topic="成果物", task_id="task_1_1",
          decision_what="WHITEBOARD:phase_1:task_1_1")
    _seed(conn, run_id, id_="AG-2", entry_type="Decision", topic="成果物", task_id="task_1_1")
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_1_1"}, {})
    assert result["count"] == 1
    assert result["agreements"][0]["entry_type"] == "Decision"


def test_deliverable_included_when_entry_type_explicit(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Deliverable", topic="成果物", task_id="task_1_1",
          decision_what="WHITEBOARD:phase_1:task_1_1")
    result = cela_main.TOOL_DISPATCH["read_agreement"](
        {"task_id": "task_1_1", "entry_type": "Deliverable"}, {})
    assert result["status"] == "ok"
    assert result["count"] == 1


def test_invalid_entry_type_returns_error(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["read_agreement"](
        {"topic_keyword": "x", "entry_type": "NotAType"}, {})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 4. Superseded除外
# ---------------------------------------------------------------------------

def test_superseded_agreement_excluded(db_conn):
    """[BL-279] _build_agreements_contextの毎ターン表示にも出ないSupersededは、
    このツールでも見せない一貫性を確認する。"""
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="改定された判断", task_id="task_4_1")
    cela_main.db_supersede_agreement("AG-1", conn, run_id)
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_4_1"}, {})
    assert result["status"] == "not_found"


# ---------------------------------------------------------------------------
# 5. citationsの防御的パース（AGENTS.md §13.1）
# ---------------------------------------------------------------------------

def test_citations_parsed_from_json_string(db_conn):
    conn, run_id = db_conn
    _seed(conn, run_id, id_="AG-1", entry_type="Decision", topic="出典あり", task_id="task_5_1",
          citations=[{"type": "web", "detail": "https://example.com/"}])
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_5_1"}, {})
    assert result["agreements"][0]["citations"] == [{"type": "web", "detail": "https://example.com/"}]


def test_malformed_citations_json_falls_back_to_empty_list(db_conn):
    """DB上のcitations列が不正なJSON文字列でもクラッシュせず[]にフォールバックすること。"""
    conn, run_id = db_conn
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, "
        "proposed_by, entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, "
        "citations, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        ("AG-BAD", "CREATE", "Proposed", "壊れたcitations", "d", "r", "expert", "Decision",
         "phase_1", "task_6_1", "[]", "{}", time.time(), "{not valid json", run_id),
    )
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_6_1"}, {})
    assert result["status"] == "ok"
    assert result["agreements"][0]["citations"] == []


def test_parse_citations_field_helper_directly():
    assert cela_main._parse_citations_field("not json") == []
    assert cela_main._parse_citations_field("") == []
    assert cela_main._parse_citations_field(None) == []
    assert cela_main._parse_citations_field(json.dumps([{"type": "web", "detail": "x"}])) == [
        {"type": "web", "detail": "x"}
    ]
    assert cela_main._parse_citations_field([{"type": "web", "detail": "x"}]) == [
        {"type": "web", "detail": "x"}
    ]


# ---------------------------------------------------------------------------
# 6. ツール配線・プロンプト指示のソース検査
# ---------------------------------------------------------------------------

_NODES_WITH_READ_AGREEMENT = [
    "call_task_planner", "call_orchestrator", "call_expert", "call_detector",
    "call_resource_arbiter", "call_integrator", "call_reviewer",
    "generate_user_utterance", "call_goal_essence_analyst", "call_task_plan_reviewer",
]


@pytest.mark.parametrize("func_name", _NODES_WITH_READ_AGREEMENT)
def test_node_has_read_agreement_tool_wired(func_name):
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "READ_AGREEMENT_TOOL" in src, f"{func_name}にREAD_AGREEMENT_TOOLが配線されていません"


def test_call_detector_wires_read_agreement_in_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("READ_AGREEMENT_TOOL") >= 2


def test_expert_has_mandatory_read_agreement_instruction():
    src = inspect.getsource(cela_main.call_expert)
    assert "必須：iter=1で一度は、read_agreement" in src


def test_user_ai_has_mandatory_read_agreement_instruction():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "必須：iter=1で一度は、read_agreement" in src


def test_bl278_domain_review_references_read_agreement_for_deep_dive():
    """[入口と出口の直結] BL-278の選定妥当性チェックが、100字要約で判定できない場合の
    展開先としてread_agreementを具体的に指示していること。"""
    src = inspect.getsource(cela_main.call_detector)
    idx = src.index("[BL-278:")
    tail = src[idx:idx + 1500]
    assert "read_agreement" in tail


def test_read_deliverable_file_description_cross_references_read_agreement():
    """モデルが誤ってread_deliverable_fileをDecision/Directiveへ試みて失敗する
    （BL-248と同型の事故）のを予防する相互参照。"""
    desc = cela_main.READ_DELIVERABLE_FILE_TOOL["function"]["description"]
    assert "read_agreement" in desc
