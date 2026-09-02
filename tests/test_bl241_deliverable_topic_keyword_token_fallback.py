"""
BL-241: `read_deliverable_file`/`_resolve_deliverable_pointer`のtopic_keyword照合が、
キーワード文字列全体（スペース区切りの複数語をそのまま連結した文字列）が実際のtopic文字列に
一字一句連続して含まれていないと一致しない仕様だったため、モデルの推測キーワードが実際の
topic文言と完全一致しない現実的なケースでほぼ確実に空振りしていた。

log/2026-08-16/1000で、task_7_1のExpertがtask_5_4/task_6_3の成果物読み取りを3回とも
"not_found"で失敗し、以降depends_onの残り5タスクへの読み取りを一切試みないまま統合文書を
書いた実インシデントが確認された。

修正は2段階:
①（初版）read_verified_fact側のBL-187と同型のトークン分割OR検索フォールバックを追加。
②（ユーザー指摘）BL-084で「Deliverableの識別は(phase_id, task_id)を権威とする」方針が
  既に確立されているため、task_idが指定されている場合はtopic_keywordの一致を一切求めない
  よう変更（①のトークンフォールバックは、task_id未指定でtopic_keywordのみの検索の場合に
  限定して残す）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-241。
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
    db_path = str(tmp_path / "test_bl241.db")
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
        cela_main._CURRENT_TASK_ID = ""


_PHASES = [
    {"phase_id": "phase_5", "tasks": [{"task_id": "task_5_4"}, {"task_id": "task_5_5"}]},
]


def _seed_deliverable(state, run_id, task_id, phase_id, topic, content):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": topic,
            "decision_what": content, "reason_why": "r", "entry_type": "Deliverable",
            "phase_id": phase_id, "task_id": task_id,
        },
        state,
    )
    assert result["success"] is True


def test_task_id_given_ignores_topic_keyword_mismatch_entirely(db_conn):
    """[BL-241本体、ユーザー指摘後の最終挙動] task_idが指定されていれば、topic_keywordが
    完全に無関係でも一致する（BL-084: Deliverableの識別はtask_idが権威、topic_keywordは
    task_id未指定時の絞り込み専用）。実インシデントの再現・修正確認。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(
        state, run_id, "task_5_4", "phase_5",
        "task_5_4 財務統合判定（赤字補填・運賃案）",
        "task_5_4の成果物本文" + "X" * 500,
    )
    # 実インシデントと同型: 推測キーワードが実際のtopic文言と全く噛み合わない。
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_5_4", "topic_keyword": "冬季 除雪 通信障害"}, state,
    )
    # [BL-289] ホワイトボード経路はdict化された
    assert isinstance(result, dict), f"not_foundのまま: {result}"
    assert "task_5_4の成果物本文" in result["content"]


def test_task_id_given_without_topic_keyword_still_works(db_conn):
    """回帰確認: task_idのみ指定（topic_keyword省略）の既存の使い方は引き続き機能する。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(
        state, run_id, "task_5_4", "phase_5",
        "task_5_4 財務統合判定（赤字補填・運賃案）",
        "task_5_4の成果物本文" + "X" * 500,
    )
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"task_id": "task_5_4"}, state,
    )
    # [BL-289] ホワイトボード経路はdict化された
    assert isinstance(result, dict)
    assert "task_5_4の成果物本文" in result["content"]


def test_topic_keyword_only_exact_phrase_match_without_task_id(db_conn):
    """task_id未指定・topic_keywordのみの検索: フレーズ全体一致は従来通り機能する。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(
        state, run_id, "task_5_4", "phase_5",
        "task_5_4 財務統合判定（赤字補填・運賃案）",
        "task_5_4の成果物本文" + "X" * 500,
    )
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"topic_keyword": "財務統合判定"}, state,
    )
    # [BL-289] ホワイトボード経路はdict化された
    assert isinstance(result, dict)
    assert "task_5_4の成果物本文" in result["content"]


def test_topic_keyword_only_token_fallback_without_task_id(db_conn):
    """[BL-241 トークンフォールバック] task_id未指定でも、topic_keywordの個々のトークンが
    topicに含まれていれば、フレーズ全体一致が失敗した後のフォールバックで一致すること。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(
        state, run_id, "task_5_4", "phase_5",
        "task_5_4 財務統合判定（赤字補填・運賃案）",
        "task_5_4の成果物本文" + "X" * 500,
    )
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"topic_keyword": "費用 運賃 赤字補填 統合判定"}, state,
    )
    # [BL-289] ホワイトボード経路はdict化された
    assert isinstance(result, dict), f"not_foundのまま: {result}"
    assert "task_5_4の成果物本文" in result["content"]


def test_topic_keyword_only_no_matching_tokens_returns_not_found(db_conn):
    """task_id未指定・topic_keywordのみの検索で、本当に無関係なキーワードでは
    誤って一致しない（過剰緩和の防止、複数タスクが存在する状況で誤って別タスクを返さないため）。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES}
    _seed_deliverable(
        state, run_id, "task_5_4", "phase_5",
        "task_5_4 財務統合判定（赤字補填・運賃案）",
        "task_5_4の成果物本文" + "X" * 500,
    )
    result = cela_main.TOOL_DISPATCH["read_deliverable_file"](
        {"topic_keyword": "冬季 除雪 通信障害"}, state,
    )
    assert result["status"] == "not_found"


def test_bl241_task_id_priority_code_present_in_source():
    """§17.1 後段: 実装を削除してもテストが落ちることを保証する存在証明。"""
    src = inspect.getsource(cela_main._resolve_deliverable_pointer)
    assert "if task_id:" in src
    assert "candidates = deliverables" in src
    assert "_tokenize_topic_keyword(topic_keyword)" in src
