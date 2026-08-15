"""
BL-151: _apply_text_edits/revise_goalの「old_textが見つからない」エラーへ、実際の
格納内容のスニペットを含める修正。

08-03/1110ドライラン（log/2026-08-03/1110/log_no_prompt.md）で、revise_goalのedits[0]の
old_textが、generate_user_utteranceのプロンプト表示専用の絵文字プレフィックス
（"👉 {user_goal}"、cela_main.py:6736）を含んでいたため、_CURRENT_GOAL_TEXT（実際の
格納内容には絵文字を含まない）と一致せず、モデルが同じ誤った引用を9回以上再試行し続けた
（BL-056bの残り回数通知で打ち切られるまで自己修復できなかった）事例が確認された。

対策として、_apply_text_edits がexact_count==0のエラーに実際の内容の先頭スニペットを
含めるようにし（content_labelパラメータで呼び出し元ごとの文脈も明示）、同ターン内での
自己修復を可能にした。あわせて他の箇所に同種の「表示専用装飾」の罠がないか調査した
（call_expert:5302、call_reflection:6349にも同型の"👉 {state['goal']}"装飾があるが、
いずれもexact_text一致を要求するツールを持たない/呼べないロールのプロンプトであり、
現状は機能的な罠になっていないことを確認した）。

参照: docs/design/issue_backlog.md BL-151。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl151_not_found_error_includes_actual_content_snippet():
    content = "実際の格納内容はこれです。装飾は含まれません。"
    merged, err = cela_main._apply_text_edits(
        content, [{"old_text": "👉 実際の格納内容はこれです。", "new_text": "x"}]
    )
    assert merged is None
    assert "実際の格納内容はこれです。装飾は含まれません。" in err


def test_bl151_default_content_label_is_whiteboard():
    merged, err = cela_main._apply_text_edits("本文", [{"old_text": "存在しない", "new_text": "x"}])
    assert merged is None
    assert "現在のホワイトボード内容に見つかりませんでした" in err


def test_bl151_custom_content_label_is_used_in_error():
    merged, err = cela_main._apply_text_edits(
        "本文", [{"old_text": "存在しない", "new_text": "x"}], content_label="現在のゴール文"
    )
    assert merged is None
    assert "現在のゴール文に見つかりませんでした" in err
    # [BL-193] スニペットの見出し文言が「実際の先頭部分」固定から「old_textに最も近い実際の内容」
    # （文書サイズに応じてold_textとの最長一致箇所周辺へ差し替え）へ変更された。
    assert "【参考：現在のゴール文のうち、あなたのold_textに最も近い実際の内容】" in err


def test_bl151_snippet_is_truncated_for_long_content():
    long_content = "あ" * (cela_main._TEXT_EDIT_SNIPPET_MAX_CHARS + 100)
    merged, err = cela_main._apply_text_edits(long_content, [{"old_text": "存在しない", "new_text": "x"}])
    assert merged is None
    assert "あ" * cela_main._TEXT_EDIT_SNIPPET_MAX_CHARS in err
    assert "あ" * (cela_main._TEXT_EDIT_SNIPPET_MAX_CHARS + 1) not in err
    assert "…（以下省略）" in err


def test_bl151_snippet_not_truncated_when_content_fits():
    short_content = "短い本文です。"
    merged, err = cela_main._apply_text_edits(short_content, [{"old_text": "存在しない", "new_text": "x"}])
    assert merged is None
    assert short_content in err
    assert "…（以下省略）" not in err


def test_bl151_ambiguous_multi_match_error_unchanged_shape():
    """複数箇所一致（exact_count>1・replace_all未指定）の分岐は、本修正の対象外で
    従来通り「N箇所に一致」形式のエラーのままであること（回帰確認）。"""
    content = "AとBとAが並ぶ。"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": "A", "new_text": "X"}])
    assert merged is None
    assert "箇所に一致し" in err
    assert "【参考：" not in err


# ===========================================================================
# revise_goal経由での結線確認（DBを使う実際の呼び出し経路）
# ===========================================================================

@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl151.db")
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
        cela_main._CURRENT_GOAL_TEXT = ""


def test_bl151_revise_goal_mismatch_error_reveals_actual_goal_text(db_conn):
    """08-03/1110の実インシデントの再現: old_textに表示専用の装飾（👉）を含めて
    呼び出した場合、エラーに実際のゴール文（装飾なし）が含まれ、モデルが同ターン内で
    正しいold_textへ修正できる材料が渡ること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    escalation_id = cela_main.TOOL_DISPATCH["escalate_premise_concern"]({
        "concern_summary": "s", "implicated_constraint": "c",
        "why_conflicts_with_true_need": "w", "suggested_reframe": "r",
    })["escalation_id"]

    # [BL-236] revise_goalは人間のHIL承認（--answer-human-input相当）を必須とするため、
    # このテスト（edits不一致エラーの中身を確認する）でも承認済み状態を再現する。
    cela_main.upsert_verified_fact(
        conn, run_id, cela_main._goal_escalation_hil_variable(escalation_id),
        "approved", "", "", "", "human_operator", confidence="confirmed",
    )

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main._CURRENT_GOAL_TEXT = "過疎地域向け「AIオンデマンド自動運転バス」の導入計画と安全基準策定"
    result = cela_main.TOOL_DISPATCH["revise_goal"]({
        "escalation_id": escalation_id,
        "edits": [{"old_text": "👉 過疎地域向け「AIオンデマンド自動運転バス」の導入計画と安全基準策定", "new_text": "x"}],
        "reason_why": "r",
    })
    assert result["success"] is False
    assert "現在のゴール文に見つかりませんでした" in result["error"]
    assert "過疎地域向け「AIオンデマンド自動運転バス」の導入計画と安全基準策定" in result["error"]
