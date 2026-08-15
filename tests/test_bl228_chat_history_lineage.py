"""
BL-228 (BL-224 Phase 3): chat_history スパイン活性化 ＋ ref プレフィックス拡張 ＋
detector 差戻の構造化（W2）のオフラインDBテスト。

実 LLM は呼ばず、DB を直接操作して以下を検証する:
- W1: _write_chat_history_row が死蔵 chat_history を活性化（行が蓄積する）
- ref 拡張: turn:/issue:/whiteboard:/detector_review: が _resolve_ref_table で True、未知は False
- trace_lineage: turn:<id> を受け付け、外向きエッジを返す
- W2: _bl228_record_detector_review が detector_reviews 行挿入 ＋ is_rollback=1 ＋
      detector_review:<id> → turn:<id> エッジを書く
- C4: _render_lineage_audit(turn:<id>) が whiteboard 版歴を含む

§17.1: 各経路を個別にリバートすると対応テストが失敗する（存在証明含む）。
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
    db_path = str(tmp_path / "test_bl228.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


def _seed_turn(conn, run_id, *, turn=2, task_id="task_1_1", phase_id="phase_1",
               role="user", content="発言本文"):
    """W1 ゲートで chat_history 行を書き、その autoincrement id を返す。"""
    return cela_main._write_chat_history_row(
        conn, run_id, turn=turn, task_id=task_id, phase_id=phase_id,
        role=role, content=content,
    )


def _seed_issue(conn, run_id, topic="detector_observation_task_1_1",
                phase_id="phase_1", task_id="task_1_1"):
    _t = time.time()
    conn.execute(
        "INSERT INTO issue_log (run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, created_at, updated_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (run_id, topic, "detector_auto", phase_id, task_id, "minor", "escalated",
         "obs", 1, _t, _t),
    )
    return topic


def _seed_whiteboard(conn, run_id, phase_id="phase_1", task_id="task_1_1", version=1,
                     content="whiteboard v1"):
    conn.execute(
        "INSERT INTO whiteboard_drafts (phase_id, task_id, version, content, author_role, timestamp, run_id) "
        "VALUES (?,?,?,?,?,?,?)",
        (phase_id, task_id, version, content, "assistant", time.time(), run_id),
    )


# ---------------------------------------------------------------------------
# W1: 死蔵 chat_history の活性化
# ---------------------------------------------------------------------------

def test_write_chat_history_row_activates_dead_table(db_conn):
    conn, run_id = db_conn
    # 実装前は chat_history への INSERT 経路が存在しなかった（死蔵）。
    # ヘルパ経由で行が蓄積することを確認（リバートで 0 件→失敗）。
    tid = cela_main._write_chat_history_row(
        conn, run_id, turn=3, task_id="task_1_1", phase_id="phase_1",
        role="user", content="活性化テスト",
    )
    assert tid > 0
    cnt = conn.execute(
        "SELECT COUNT(*) FROM chat_history WHERE run_id=?", (run_id,)
    ).fetchone()[0]
    assert cnt >= 1
    row = conn.execute(
        "SELECT turn, task_id, phase_id, role, content, is_rollback FROM chat_history WHERE id=?",
        (tid,),
    ).fetchone()
    assert row["turn"] == 3
    assert row["task_id"] == "task_1_1"
    assert row["phase_id"] == "phase_1"
    assert row["role"] == "user"
    assert row["content"] == "活性化テスト"
    assert row["is_rollback"] == 0


# ---------------------------------------------------------------------------
# ref プレフィックス拡張
# ---------------------------------------------------------------------------

def test_resolve_ref_table_new_prefixes_true(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id)
    topic = _seed_issue(conn, run_id)
    _seed_whiteboard(conn, run_id)
    # detector_review は W2 ヘルパで作成（turn と紐づく）
    cela_main._bl228_record_detector_review(
        conn, run_id, turn_id=tid, task_id="task_1_1", phase_id="phase_1",
        risk="medium", constraint_issue="minor", comment="c",
    )
    assert cela_main._resolve_ref_table(conn.execute, run_id, f"turn:{tid}") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, f"issue:{topic}") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, "whiteboard:phase_1:task_1_1") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, "detector_review:1") is True


def test_resolve_ref_table_unknown_prefix_false(db_conn):
    conn, run_id = db_conn
    assert cela_main._resolve_ref_table(conn.execute, run_id, "foo:bar") is False
    assert cela_main._resolve_ref_table(conn.execute, run_id, "turn:999999") is False


def test_resolve_ref_line_turn_branch(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id, role="assistant", content="監査対象の発言")
    line = cela_main._resolve_ref_line(conn, run_id, f"turn:{tid}")
    assert isinstance(line, str)
    assert "turn" in line or "発言" in line


# ---------------------------------------------------------------------------
# trace_lineage が turn:<id> を受け付ける（C5 拡張）
# ---------------------------------------------------------------------------

def test_trace_lineage_handler_accepts_turn_ref(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id, task_id="task_1_1", phase_id="phase_1")
    _seed_whiteboard(conn, run_id, version=1, content="wb v1")
    # turn → whiteboard エッジ（W2 の下流結合と同型）
    assert cela_main._write_relation_edge(
        conn, run_id, f"turn:{tid}", "whiteboard:phase_1:task_1_1",
        "depends_on", "test edge", "detector",
        source_task_id="task_1_1", source_phase_id="phase_1",
    )
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    try:
        result = cela_main._trace_lineage_handler({"ref": f"turn:{tid}"}, {})
        assert result["status"] == "ok"
        refs = [e["ref"] for e in result["lineage"]]
        assert "whiteboard:phase_1:task_1_1" in refs
    finally:
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = None


# ---------------------------------------------------------------------------
# W2: detector 差戻の構造化
# ---------------------------------------------------------------------------

def test_w2_record_detector_review_inserts_and_flags_turn(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id, task_id="task_1_1", phase_id="phase_1")
    review_id = cela_main._bl228_record_detector_review(
        conn, run_id, turn_id=tid, task_id="task_1_1", phase_id="phase_1",
        risk="medium", constraint_issue="minor", comment="弱い部分",
        criteria_status=[{"criterion": "c1", "status": "NG"}], observations="観察",
    )
    assert review_id is not None
    # detector_reviews 行
    rows = conn.execute(
        "SELECT * FROM detector_reviews WHERE run_id=?", (run_id,)
    ).fetchall()
    assert len(rows) == 1
    assert rows[0]["turn_id"] == tid
    assert rows[0]["constraint_issue"] == "minor"
    assert rows[0]["comment"] == "弱い部分"
    # chat_history の is_rollback が立つ
    flag = conn.execute(
        "SELECT is_rollback FROM chat_history WHERE id=?", (tid,)
    ).fetchone()[0]
    assert flag == 1
    # detector_review:<id> → turn:<id> エッジ
    edges = conn.execute(
        "SELECT from_ref, to_ref FROM relation_edges WHERE run_id=?", (run_id,)
    ).fetchall()
    assert ("detector_review:%d" % review_id, "turn:%d" % tid) in [
        (e["from_ref"], e["to_ref"]) for e in edges
    ]


def test_w2_turn_to_artifact_edges_resolve(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id, task_id="task_1_1", phase_id="phase_1")
    topic = _seed_issue(conn, run_id)
    _seed_whiteboard(conn, run_id, version=2, content="wb v2")
    # W2 の turn→artifact 下流結合（detector_node 内の inline 呼び出しと同型）
    assert cela_main._write_relation_edge(
        conn, run_id, f"turn:{tid}", f"issue:{topic}", "depends_on",
        "turn→issue", "detector", source_task_id="task_1_1", source_phase_id="phase_1",
    )
    assert cela_main._write_relation_edge(
        conn, run_id, f"turn:{tid}", "whiteboard:phase_1:task_1_1", "depends_on",
        "turn→whiteboard", "detector", source_task_id="task_1_1", source_phase_id="phase_1",
    )
    assert cela_main._resolve_ref_table(conn.execute, run_id, f"issue:{topic}") is True
    assert cela_main._resolve_ref_table(conn.execute, run_id, "whiteboard:phase_1:task_1_1") is True


# ---------------------------------------------------------------------------
# C4: turn の系譜描画に whiteboard 版歴を含む
# ---------------------------------------------------------------------------

def test_render_lineage_audit_turn_includes_whiteboard_timeline(db_conn):
    conn, run_id = db_conn
    tid = _seed_turn(conn, run_id, task_id="task_1_1", phase_id="phase_1")
    _seed_whiteboard(conn, run_id, version=1, content="初版")
    _seed_whiteboard(conn, run_id, version=2, content="修正版")
    out = cela_main._render_lineage_audit(conn, run_id, f"turn:{tid}")
    assert "turn:" in out
    assert "当該タスク task_1_1 の whiteboard 版歴" in out
    assert "v1" in out and "v2" in out


def test_init_db_migrates_old_chat_history_schema(tmp_path):
    # §17.1 回帰: BL-228 以前の旧スキーマ（task_id 列なし）の既存DBで init_db が
    # idx_chat_history_run_task(run_id, task_id) 作成時に no such column で崩れないこと。
    db_path = str(tmp_path / "old.db")
    conn = cela_main.get_db_connection(db_path)
    # 旧 chat_history（task_id なし）を事前作成
    conn.executescript(
        "CREATE TABLE decisions (id TEXT, run_id TEXT NOT NULL);"
        "CREATE TABLE chat_history ("
        " id INTEGER PRIMARY KEY AUTOINCREMENT, run_id TEXT NOT NULL, turn INTEGER,"
        " role TEXT, content TEXT, timestamp REAL);"
    )
    conn.close()
    # 再オープンして init_db（旧来の既存DBに相当）
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)  # 旧来はここで OperationalError でクラッシュしていた
    cols = {r[1] for r in conn.execute("PRAGMA table_info(chat_history)").fetchall()}
    assert "task_id" in cols and "is_rollback" in cols
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='index' AND name='idx_chat_history_run_task'"
    ).fetchone() is not None
    # detector_reviews も新規作成される
    assert conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name='detector_reviews'"
    ).fetchone() is not None
    conn.close()



# ---------------------------------------------------------------------------
# 存在証明（§17.1 後段）: 実装を削除してもテストが落ちることを保証
# ---------------------------------------------------------------------------

def test_ref_extension_present_in_source():
    src_resolve = inspect.getsource(cela_main._resolve_ref_table)
    for prefix in ("turn:", "issue:", "whiteboard:", "detector_review:"):
        assert prefix in src_resolve, f"{prefix} 分岐が _resolve_ref_table に無い"
    src_trace = inspect.getsource(cela_main._trace_lineage_handler)
    assert "_LINEAGE_REF_PREFIXES" in src_trace
    assert "turn:" in src_trace and "detector_review:" in src_trace
    # W2 ヘルパの存在
    assert "_bl228_record_detector_review" in inspect.getsource(cela_main._bl228_record_detector_review)


def test_trace_lineage_usage_paragraph_wired_into_expert_and_user_prompts():
    """[BL-228] trace_lineageは「配線済みだがいつ呼ぶか指示が無く未発火」だった
    （1314ログでは0回呼び出し、AGENTS.md §15.4 入口はあるが出口＝消費経路が無い状態）。
    ツール自体・_TRACE_LINEAGE_USAGE_PARAGRAPHの定義に加え、Expert/User AI各Stageの
    プロンプト生成関数のソースに実際に注入されていることまで確認する（存在証明のみでは
    「定義したが誰も呼ばない」再発を検知できないため）。
    """
    assert hasattr(cela_main, "_TRACE_LINEAGE_USAGE_PARAGRAPH")
    src_expert = inspect.getsource(cela_main.call_expert)
    assert "trace_lineage" in src_expert
    assert "TRACE_LINEAGE_TOOL" in src_expert
    src_user = inspect.getsource(cela_main.generate_user_utterance)
    assert "_TRACE_LINEAGE_USAGE_PARAGRAPH" in src_user
