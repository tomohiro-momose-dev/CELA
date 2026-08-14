"""
BL-193: write_agreement(edits=...)によるホワイトボード書き換えの繰り返し失敗対策。

1514ログ（log/2026-08-08/1514、task_2_1）で、50KB超に育ったホワイトボードの途中セクション
（3.6節）を修正しようとしたExpertが、Detector注釈ブロックごと巻き込んだ巨大なold_textを
一字一句正確に再現できず、同一パターンの失敗を8回連続で繰り返す事故が発生した。

原因を調査した結果、BL-151で追加された「不一致時に実際の格納内容のスニペットを見せて自己修復
させる」機構（_apply_text_edits）が、対象文書サイズに関わらず**常に文書先頭400文字**しか
見せていなかったため、編集対象が先頭から遠い節にある大規模文書では一度も実際の対象箇所が
見えず、自己修復が機能していなかったことが判明した。

対策は3点：
1. _nearest_content_snippet: 不一致時のスニペットを、old_textとの最長共通部分
   （difflib.SequenceMatcher）の周辺へ差し替える（有意な一致が無ければBL-151の元の
   「文書先頭」挙動へフォールバック）。
2. read_whiteboard_excerptツール: write_agreementのold_textを組み立てる前に、Expertが
   キーワード指定で対象箇所の"現在の"実際の文字列だけをピンポイントで取得できるようにする
   （verify_whiteboard_excerpt、BL-079・Detector専用、と同じ判定ロジックを流用するが、
   目的が逆で「検証のみ」ではなく「実際の中身を返す」）。
3. R4編集方針プロンプト（_build_task_scope_context）へ、old_textを最小限に保つ（Detector
   注釈ブロック等の無関係な周辺を巻き込まない）指示と、read_whiteboard_excerptの使用推奨を
   追記。

参照: docs/design/back_log/issue_backlog.md BL-193。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ===========================================================================
# _nearest_content_snippet: 不一致時スニペットが「文書先頭固定」ではなく
# 「old_textに最も近い実際の箇所」を返すこと
# ===========================================================================

def _make_large_document() -> str:
    """複数セクションを持つ大規模文書を模したテストフィクスチャ。"""
    section1 = "# 文書タイトル\n\n## 1. 前提\n" + ("前提の説明。" * 100) + "\n\n"
    target_section = "## 3.6 対象セクション\n| 属性 | 値 |\n|---|---|\n| 現役世代 | 44 |\n| 子供 | 28 |\n\n"
    trailing = "## 9. 末尾セクション\n" + ("末尾の説明。" * 100)
    return section1 + target_section + trailing


def test_nearest_content_snippet_finds_region_near_old_text_not_document_head():
    content = _make_large_document()
    # old_textは対象セクションの表を狙っているが、値が微妙に食い違い一致しない
    old_text = "## 3.6 対象セクション\n| 属性 | 値 |\n|---|---|\n| 現役世代 | 45 |\n| 子供 | 27 |\n\n"
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert "3.6 対象セクション" in snippet
    # 「常に文書先頭」だった旧BL-151挙動なら先頭見出しから始まるはず（=対象セクションが遠いほど
    # 見えない）。今回のスニペットは対象箇所周辺なので先頭固定にはならない。
    assert not snippet.startswith("# 文書タイトル")


def test_nearest_content_snippet_falls_back_to_head_when_old_text_unrelated():
    content = _make_large_document()
    old_text = "存在しない全く無関係な文字列XYZ123"
    snippet = cela_main._nearest_content_snippet(content, old_text)
    assert snippet.startswith("# 文書タイトル")
    assert "…（以下省略）" in snippet


def test_nearest_content_snippet_short_content_unchanged_from_bl151_behavior():
    content = "短い本文です。"
    snippet = cela_main._nearest_content_snippet(content, "存在しない")
    assert snippet == content


def test_apply_text_edits_error_uses_nearest_snippet_for_large_document():
    content = _make_large_document()
    old_text = "## 3.6 対象セクション\n| 属性 | 値 |\n|---|---|\n| 現役世代 | 45 |\n| 子供 | 27 |\n\n"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": old_text, "new_text": "x"}])
    assert merged is None
    assert "3.6 対象セクション" in err
    assert "# 文書タイトル" not in err


# ===========================================================================
# _read_whiteboard_excerpt_handler: DBを使った実際の呼び出し経路
# ===========================================================================

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl193.db")
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
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_PHASE_ID = ""


def _state_for(run_id: str, task_id: str = "task_2_1", phase_id: str = "phase_2") -> dict:
    return {
        "run_id": run_id,
        "current_task_id": task_id,
        "current_phase": {"phase_id": phase_id, "tasks": [{"task_id": task_id}]},
    }


def test_read_whiteboard_excerpt_empty_keyword_rejected(db_conn):
    conn, run_id = db_conn
    result = cela_main._read_whiteboard_excerpt_handler({"keyword": ""}, _state_for(run_id))
    assert result["ok"] is False
    assert "keyword" in result["reason"]


def test_read_whiteboard_excerpt_no_current_task_rejected(db_conn):
    conn, run_id = db_conn
    state = {"run_id": run_id, "current_task_id": "", "current_phase": {}}
    result = cela_main._read_whiteboard_excerpt_handler({"keyword": "x"}, state)
    assert result["ok"] is False


def test_read_whiteboard_excerpt_no_whiteboard_yet(db_conn):
    conn, run_id = db_conn
    result = cela_main._read_whiteboard_excerpt_handler({"keyword": "x"}, _state_for(run_id))
    assert result["ok"] is False
    assert "存在しません" in result["reason"]


def test_read_whiteboard_excerpt_exact_single_match_returns_window(db_conn):
    conn, run_id = db_conn
    content = _make_large_document()
    v = cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", content, "expert", "初版")
    result = cela_main._read_whiteboard_excerpt_handler(
        {"keyword": "## 3.6 対象セクション", "context_chars": 100}, _state_for(run_id)
    )
    assert result["ok"] is True
    assert result["match_type"] == "exact"
    assert result["version"] == v
    assert "3.6 対象セクション" in result["excerpt"]
    assert "# 文書タイトル" not in result["excerpt"]


def test_read_whiteboard_excerpt_loose_match_ignores_markdown_bold_and_spacing(db_conn):
    conn, run_id = db_conn
    content = "# タイトル\n\n**重要な見出し**  の本文です。\n\n" + ("後続。" * 50)
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", content, "expert", "初版")
    # 太字記法・空白の有無を変えたkeywordで検索（完全一致は0件、緩い一致は1件のはず）
    result = cela_main._read_whiteboard_excerpt_handler(
        {"keyword": "重要な見出し の本文です。"}, _state_for(run_id)
    )
    assert result["ok"] is True
    assert result["match_type"] == "loose"


def test_read_whiteboard_excerpt_zero_matches_reports_reason(db_conn):
    conn, run_id = db_conn
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", "本文です。", "expert", "初版")
    result = cela_main._read_whiteboard_excerpt_handler({"keyword": "存在しない語句"}, _state_for(run_id))
    assert result["ok"] is False
    assert result["match_count"] == 0


def test_read_whiteboard_excerpt_multiple_matches_reports_count(db_conn):
    conn, run_id = db_conn
    content = "重複語句A。中身1。\n重複語句A。中身2。"
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", content, "expert", "初版")
    result = cela_main._read_whiteboard_excerpt_handler({"keyword": "重複語句A"}, _state_for(run_id))
    assert result["ok"] is False
    assert result["match_count"] == 2


def test_read_whiteboard_excerpt_context_chars_clamped_to_max(db_conn):
    conn, run_id = db_conn
    content = "見出し。" + ("あ" * 10000)
    cela_main.apply_whiteboard_patch(conn, run_id, "phase_2", "task_2_1", content, "expert", "初版")
    result = cela_main._read_whiteboard_excerpt_handler(
        {"keyword": "見出し。", "context_chars": 999999}, _state_for(run_id)
    )
    assert result["ok"] is True
    # 上限3000でクランプされているので、極端に巨大なexcerptにはならない
    assert len(result["excerpt"]) < 7000


# ===========================================================================
# 配線確認: ツール登録・Expertのtools一覧・R4プロンプトへの結線
# ===========================================================================

def test_read_whiteboard_excerpt_registered_in_tool_dispatch():
    assert "read_whiteboard_excerpt" in cela_main.TOOL_DISPATCH


def test_read_whiteboard_excerpt_tool_schema_shape():
    tool = cela_main.READ_WHITEBOARD_EXCERPT_TOOL
    assert tool["function"]["name"] == "read_whiteboard_excerpt"
    assert "keyword" in tool["function"]["parameters"]["properties"]
    assert tool["function"]["parameters"]["required"] == ["keyword"]


def test_call_expert_source_attaches_read_whiteboard_excerpt_tool():
    import inspect
    source = inspect.getsource(cela_main.call_expert)
    assert "READ_WHITEBOARD_EXCERPT_TOOL" in source


def test_build_task_scope_context_source_mentions_bl193_minimal_old_text_guidance():
    import inspect
    source = inspect.getsource(cela_main._build_task_scope_context)
    assert "BL-193" in source
    assert "read_whiteboard_excerpt" in source
