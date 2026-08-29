"""
BL-309: 保留issueに紐づかない、自由な対話クエリ機能（`--interactive-query RUN_ID`）の追加。

ユーザー要望（原文）: 「エスカレーション以外でも、対話で内容を確認できるようにしたい。
さらに、すべてのdbへ能動的にアクセスして、例えば、値や意思決定を追いたい。ただ、ログは
あえて読ませない、dbだけで十分に追跡ができるか、つまり意思決定や事物の系譜が成り立って
いるかのテストにもなる」

既存の`--interactive-hil`（BL-274）は「保留中issueの承認/却下」フローに限定されており、
かつその内部のQ&A（`_answer_human_question`）はagreements/verified_factsの2テーブルを
事前に静的に取得してプロンプトへ貼り付けるだけで、LLM自身が能動的にDBを検索する構造では
なかった。BL-309は、保留issueの有無を問わず起動できる自由質問専用の対話REPL
（`_run_interactive_query`/`_answer_general_query`）を新設し、read_agreement/
read_verified_fact/read_entity/verify_entity_geo/read_issues/read_escalation/
read_deliverable_file/read_project_plan/trace_lineage/python_repl/thinkという、
既存の読み取り専用ツール実体（グラフ内ノードと同一実装、AGENTS.md §15.1）をツールループ
として与え、LLMが自ら能動的にDBを辿れるようにした。生の実行ログファイルを読むツールは
一切含めない（意図的な設計で、DBの記録のみで意思決定・数値の系譜を追跡できるかの
検証を兼ねる）。

参照: BL-274（既存の対話型HIL、issue紐づき）、BL-236/BL-224（trace_lineage・系譜設計）。
実LLM API呼び出しは伴わない（query_AIはモンキーパッチ）。
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
    db_path = str(tmp_path / "test_bl309.db")
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


def _scripted_input(*answers):
    it = iter(answers)

    def _fn(prompt=""):
        return next(it)
    return _fn


def test_bl309_answer_general_query_persists_to_human_qa_log(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "query_AI",
                         lambda messages, client, model, label="Unknown Node", tools=None,
                         light_system_prompt=None, state=None: "回答内容です。")

    result = cela_main._answer_general_query(conn, run_id, "license_surrender_countの経緯は？")

    assert result["success"] is True
    assert result["answer"] == "回答内容です。"
    rows = conn.execute(
        "SELECT issue_id, issue_topic, question, answer FROM human_qa_log WHERE run_id=?",
        (run_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["issue_id"] == ""
    assert rows[0]["issue_topic"] == "(general_query)"
    assert rows[0]["question"] == "license_surrender_countの経緯は？"


def test_bl309_query_is_dispatched_with_tool_loop_not_single_shot(db_conn, monkeypatch):
    """[BL-309本体] _answer_human_question（BL-274、単発・ツール無し）と異なり、
    _answer_general_queryは_INTERACTIVE_QUERY_TOOLSをtools引数として渡すこと
    （＝ツールループとして呼ばれ、LLMが能動的にDBを検索できること）。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None,
                       light_system_prompt=None, state=None):
        captured["tools"] = tools
        captured["label"] = label
        return "回答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)
    cela_main._answer_general_query(conn, run_id, "質問")

    assert captured["tools"] == cela_main._INTERACTIVE_QUERY_TOOLS
    assert captured["tools"] is not None
    assert len(captured["tools"]) > 5


def test_bl309_prompt_explicitly_forbids_log_access(db_conn, monkeypatch):
    """[BL-309本体] プロンプトに、ログファイルへ意図的にアクセスさせない旨が明記されて
    いること（ユーザー要望の核心：ログ無しでDBの記録だけで追跡できるかの検証）。"""
    conn, run_id = db_conn
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None,
                       light_system_prompt=None, state=None):
        captured["prompt"] = messages[0]["content"]
        return "回答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)
    cela_main._answer_general_query(conn, run_id, "質問")

    assert "生の実行ログファイルには一切アクセスできません" in captured["prompt"]
    assert "意図的な設計" in captured["prompt"]


def test_bl309_sets_db_globals_before_tool_loop(db_conn, monkeypatch):
    """[配線確認] read_agreement等の既存ツール実体はget_active_conn()/_CURRENT_RUN_IDという
    モジュールグローバルを参照する設計のため、ツールループへ入る前にこれらを明示的に
    設定していること（設定漏れがあるとグラフ外のCLIプロセスからのツール呼び出しが
    RuntimeError（DB connection is not initialized）で落ちる）。"""
    conn, run_id = db_conn
    cela_main._DB_CONN = None  # 意図的にクリアし、関数が自分で設定し直すことを確認する
    cela_main._CURRENT_RUN_ID = ""
    monkeypatch.setattr(cela_main, "query_AI",
                         lambda *a, **k: "回答")

    cela_main._answer_general_query(conn, run_id, "質問")

    assert cela_main._DB_CONN is conn
    assert cela_main._CURRENT_RUN_ID == run_id
    assert cela_main.get_active_conn() is conn


def test_bl309_interactive_query_loop_q_quits_without_answering(db_conn):
    conn, run_id = db_conn
    printed = []
    input_fn = _scripted_input("q")

    cela_main._run_interactive_query(conn, run_id, input_fn, printed.append)

    assert not any("🤖" in p for p in printed)
    rows = conn.execute("SELECT COUNT(*) AS n FROM human_qa_log WHERE run_id=?", (run_id,)).fetchone()
    assert rows["n"] == 0


def test_bl309_interactive_query_loop_answers_then_quits(db_conn, monkeypatch):
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "query_AI",
                         lambda *a, **k: "これが回答です。")
    printed = []
    input_fn = _scripted_input("免許返納件数は？", "q")

    cela_main._run_interactive_query(conn, run_id, input_fn, printed.append)

    assert any("これが回答です。" in p for p in printed)
    rows = conn.execute("SELECT COUNT(*) AS n FROM human_qa_log WHERE run_id=?", (run_id,)).fetchone()
    assert rows["n"] == 1


def test_bl309_interactive_query_loop_never_writes_to_issue_log(db_conn, monkeypatch):
    """[非退行] --interactive-queryは承認/却下フローを持たないため、issue_logへは
    一切書き込まないこと（_run_interactive_hilとの役割分担の確認）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "query_AI", lambda *a, **k: "回答")
    input_fn = _scripted_input("質問1", "質問2", "q")

    cela_main._run_interactive_query(conn, run_id, input_fn, lambda m: None)

    count = conn.execute("SELECT COUNT(*) AS n FROM issue_log WHERE run_id=?", (run_id,)).fetchone()
    assert count["n"] == 0


def test_bl309_tool_list_contains_no_log_reading_tool():
    """[一般化・意図の確認] _INTERACTIVE_QUERY_TOOLSに、ログファイルを読むツールが
    含まれていないこと（現状のツール一覧にそのようなツールは存在しないが、将来ログ読み込み
    ツールが追加された際に誤って混入させないための固定リスト化の確認）。"""
    tool_names = {t["function"]["name"] for t in cela_main._INTERACTIVE_QUERY_TOOLS}
    for name in tool_names:
        assert "log" not in name.lower()


def test_bl309_cli_flag_registered_and_dispatches():
    """[配線確認] --interactive-queryがargparseへ登録され、_run_interactive_queryへ
    正しくディスパッチされる分岐がソース上に存在すること。"""
    import inspect
    src = inspect.getsource(cela_main)
    assert '"--interactive-query"' in src
    assert "_cli_args.interactive_query:" in src
    assert "_run_interactive_query(_conn, _cli_args.interactive_query)" in src
