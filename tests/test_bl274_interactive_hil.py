"""
BL-274: HILを対話型にする（人間が質問→AIがDB情報に基づき回答→人間が承認/却下）。

現状のCELAのHILは全て「別プロセス起動のステートレスCLIコマンド」（--pending-human-input/
--answer-human-input/--resume）であり、対話ループ・REPLは一切持っていなかった。BL-236
（escalate_premise_concernのHILゲート）・BL-273（グラフの一時停止機構）は「AIが懸念を提起
→人間が承認/却下のみ回答」という一方向フローで完成していたが、ユーザーは承認/却下の前段に
「人間が自由に質問し、AIがDB情報（issue_log/agreements/verified_facts）に基づいて回答する」
という対話ラウンドを挟みたいと希望した。

設計対話で確定した3点：
1. UIは真のインタラクティブREPL（`--interactive-hil RUN_ID`、1プロセス内で複数回の質問→回答
   を繰り返し、最後にapprove/reject入力まで完結させる）。
2. 対象issueの範囲は`human_research_prompt`付き全issue（escalate_premise_concern由来・
   flag_needs_human_input由来の両方、既存--answer-human-inputと同じ条件）。
3. 質問・回答は新規`human_qa_log`テーブルへ永続化する（1issue:N質問のため列追加ではなく
   別テーブル）。

承認/却下の実処理は新規実装せず既存`_answer_human_input`をそのまま再利用し（AGENTS.md
§16.5）、BL-279の`read_agreement`検索ロジックは`_query_agreements_core`として抽出し
スタンドアロンCLIからも再利用する（AGENTS.md §15.1）。

参照: docs/design/back_log/issue_backlog.md BL-274。実LLM API呼び出しは伴わない
（query_AIはモンキーパッチする）。
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
    db_path = str(tmp_path / "test_bl274.db")
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


def _flag_args(**overrides):
    args = {
        "topic": "store_selection_basis",
        "variable_name": "store_selection_basis",
        "human_research_prompt": "商業施設3店舗の選定基準を現地確認してください。",
        "description": "9候補中3店舗のみ採用されたが選定理由が記録されていない。",
    }
    args.update(overrides)
    return args


def _seed_issue(conn, run_id, **overrides):
    cela_main._flag_needs_human_input_tool_impl(
        _flag_args(**overrides), conn, run_id, "expert", "phase_2", "task_2_2")


def _fake_query_AI(answer="ダミー回答"):
    def _fn(messages, client, model, label="Unknown Node", tools=None,
            light_system_prompt=None, state=None):
        return answer
    return _fn


# ---------------------------------------------------------------------------
# 1. human_qa_logテーブル
# ---------------------------------------------------------------------------

def test_human_qa_log_table_created(db_conn):
    conn, _run_id = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(human_qa_log)").fetchall()}
    assert {"id", "run_id", "issue_id", "issue_topic", "question", "answer", "asked_at"} <= cols


# ---------------------------------------------------------------------------
# 2. _query_agreements_core（BL-279からの抽出リファクタ）
# ---------------------------------------------------------------------------

def test_query_agreements_core_direct_call_returns_ok_shape(db_conn):
    conn, run_id = db_conn
    cela_main.db_append_agreement(
        {
            "id": "AG-1", "action_type": "CREATE", "status": "Proposed", "topic": "店舗選定",
            "decision_what": "3店舗を採用", "reason_why": "9候補中3店舗を選定",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_2",
            "task_id": "task_2_2", "timestamp": time.time(), "citations": [],
        },
        conn, run_id,
    )
    result = cela_main._query_agreements_core(conn, run_id, task_id="task_2_2",
                                               topic_keyword="", entry_type_filter="")
    assert result["status"] == "ok"
    assert result["count"] == 1
    assert result["agreements"][0]["topic"] == "店舗選定"


def test_read_agreement_handler_delegates_to_query_agreements_core():
    src = inspect.getsource(cela_main._read_agreement_handler)
    assert "return _query_agreements_core(" in src


def test_existing_bl279_tool_dispatch_still_works(db_conn):
    """[回帰確認] _read_agreement_handlerのリファクタ後もTOOL_DISPATCH経由の戻り値形状は不変。"""
    conn, run_id = db_conn
    cela_main.db_append_agreement(
        {
            "id": "AG-1", "action_type": "CREATE", "status": "Proposed", "topic": "運賃案",
            "decision_what": "案Bを採用", "reason_why": "コストが最小",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_2",
            "task_id": "task_2_2", "timestamp": time.time(), "citations": [],
        },
        conn, run_id,
    )
    result = cela_main.TOOL_DISPATCH["read_agreement"]({"task_id": "task_2_2"}, {})
    assert result["status"] == "ok"
    assert result["count"] == 1


# ---------------------------------------------------------------------------
# 3. _answer_human_question
# ---------------------------------------------------------------------------

def test_answer_human_question_no_matching_issue_returns_error(db_conn):
    conn, run_id = db_conn
    result = cela_main._answer_human_question(conn, run_id, "no_such_topic", "質問です")
    assert result["success"] is False
    assert "見つかりません" in result["error"]


def test_answer_human_question_persists_to_human_qa_log(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI("店舗選定の記録はありません。"))

    result = cela_main._answer_human_question(conn, run_id, "store_selection_basis", "選定基準は？")
    assert result["success"] is True
    assert result["answer"] == "店舗選定の記録はありません。"

    rows = conn.execute(
        "SELECT * FROM human_qa_log WHERE run_id=? AND issue_topic=?",
        (run_id, "store_selection_basis")
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["question"] == "選定基準は？"
    assert rows[0]["answer"] == "店舗選定の記録はありません。"
    assert rows[0]["issue_id"]


def test_answer_human_question_appends_multiple_rows_for_repeated_questions(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI("回答"))

    cela_main._answer_human_question(conn, run_id, "store_selection_basis", "質問1")
    cela_main._answer_human_question(conn, run_id, "store_selection_basis", "質問2")

    rows = conn.execute(
        "SELECT question FROM human_qa_log WHERE run_id=? AND issue_topic=? ORDER BY asked_at",
        (run_id, "store_selection_basis")
    ).fetchall()
    assert [r["question"] for r in rows] == ["質問1", "質問2"]


def test_answer_human_question_includes_related_agreement_in_prompt(db_conn, monkeypatch):
    """[消費経路の確認] task_idに紐づくagreementがプロンプトへ実際に渡ること。"""
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    cela_main.db_append_agreement(
        {
            "id": "AG-1", "action_type": "CREATE", "status": "Proposed", "topic": "店舗選定",
            "decision_what": "オギノ・ツルヤ・西友の3店舗を採用",
            "reason_why": "経路設計上必要な最小限の実在店舗として選定",
            "proposed_by": "expert", "entry_type": "Decision", "phase_id": "phase_2",
            "task_id": "task_2_2", "timestamp": time.time(), "citations": [],
        },
        conn, run_id,
    )
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None,
                       light_system_prompt=None, state=None):
        captured["prompt"] = messages[0]["content"]
        return "回答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)
    cela_main._answer_human_question(conn, run_id, "store_selection_basis", "選定基準は？")
    assert "オギノ・ツルヤ・西友の3店舗を採用" in captured["prompt"]
    assert "経路設計上必要な最小限の実在店舗として選定" in captured["prompt"]


# ---------------------------------------------------------------------------
# 4. _interactive_hil_issue_loop
# ---------------------------------------------------------------------------

def _scripted_input(*answers):
    it = iter(answers)

    def _fn(prompt=""):
        return next(it)
    return _fn


def test_issue_loop_approve_flow_writes_verified_fact_and_resolves_issue(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI("参考情報です。"))
    printed = []
    input_fn = _scripted_input("選定基準は？", "", "approve", "12.5", "m", "現地確認", "承認済み")

    cela_main._interactive_hil_issue_loop(conn, run_id, "store_selection_basis", input_fn, printed.append)

    fact = conn.execute(
        "SELECT * FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert fact is not None
    assert fact["value"] == "12.5"
    assert fact["unit"] == "m"
    assert fact["confirmed_by"] == "human_operator"

    issue = conn.execute(
        "SELECT status FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert issue["status"] == "resolved"

    qa_rows = conn.execute(
        "SELECT * FROM human_qa_log WHERE run_id=? AND issue_topic=?",
        (run_id, "store_selection_basis")
    ).fetchall()
    assert len(qa_rows) == 1


def test_issue_loop_reject_flow_writes_rejected_value(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    monkeypatch.setattr(cela_main, "query_AI", _fake_query_AI("参考情報です。"))
    printed = []
    input_fn = _scripted_input("", "reject", "根拠不十分のため却下")

    cela_main._interactive_hil_issue_loop(conn, run_id, "store_selection_basis", input_fn, printed.append)

    fact = conn.execute(
        "SELECT value FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert fact["value"] == "rejected"
    issue = conn.execute(
        "SELECT status, resolution_note FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert issue["status"] == "resolved"
    assert issue["resolution_note"] == "根拠不十分のため却下"


def test_issue_loop_skip_leaves_issue_unresolved(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    printed = []
    input_fn = _scripted_input("", "skip")

    cela_main._interactive_hil_issue_loop(conn, run_id, "store_selection_basis", input_fn, printed.append)

    issue = conn.execute(
        "SELECT status FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert issue["status"] != "resolved"


def test_issue_loop_q_raises_system_exit(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    input_fn = _scripted_input("q")

    with pytest.raises(SystemExit):
        cela_main._interactive_hil_issue_loop(conn, run_id, "store_selection_basis", input_fn, lambda m: None)


def test_issue_loop_b_returns_without_resolving(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    input_fn = _scripted_input("b")

    cela_main._interactive_hil_issue_loop(conn, run_id, "store_selection_basis", input_fn, lambda m: None)

    issue = conn.execute(
        "SELECT status FROM issue_log WHERE run_id=? AND topic=?",
        (run_id, "store_selection_basis")
    ).fetchone()
    assert issue["status"] != "resolved"


# ---------------------------------------------------------------------------
# 5. _run_interactive_hil（一覧・選択・ループ制御）
# ---------------------------------------------------------------------------

def test_run_interactive_hil_no_pending_issues_prints_message_and_returns(db_conn):
    conn, run_id = db_conn
    printed = []

    def _fail_input(prompt=""):
        raise AssertionError("issueが無い場合はinput_fnを呼んではならない")

    cela_main._run_interactive_hil(conn, run_id, input_fn=_fail_input, print_fn=printed.append)
    assert any("保留中のissueはありません" in m for m in printed)


def test_run_interactive_hil_invalid_index_reprompts(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    printed = []
    input_fn = _scripted_input("99", "q")

    cela_main._run_interactive_hil(conn, run_id, input_fn=input_fn, print_fn=printed.append)
    assert any("無効な番号です" in m for m in printed)


def test_run_interactive_hil_select_then_back_reshows_list(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    printed = []
    input_fn = _scripted_input("0", "b", "q")

    cela_main._run_interactive_hil(conn, run_id, input_fn=input_fn, print_fn=printed.append)
    list_headers = [m for m in printed if "保留中のissue " in m]
    assert len(list_headers) == 2, "'b'で一覧に戻った後、再度issue一覧が表示されるはず"


def test_run_interactive_hil_q_at_list_level_returns_cleanly(db_conn):
    conn, run_id = db_conn
    _seed_issue(conn, run_id)
    input_fn = _scripted_input("q")
    cela_main._run_interactive_hil(conn, run_id, input_fn=input_fn, print_fn=lambda m: None)


# ---------------------------------------------------------------------------
# 6. CLI配線の確認
# ---------------------------------------------------------------------------

def test_cli_wiring_interactive_hil_flag_registered():
    src = inspect.getsource(cela_main)
    assert '"--interactive-hil"' in src
    assert "_run_interactive_hil(_conn, _cli_args.interactive_hil)" in src
