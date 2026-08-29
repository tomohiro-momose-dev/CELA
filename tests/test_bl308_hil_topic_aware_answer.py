"""
BL-308: `_interactive_hil_issue_loop`（BL-274の対話型HIL REPL）が、トピックの種類を
区別せず「確定値」を扱っていた設計バグの修正。

実機で発生した不具合（原文の再現）: ユーザーが`--interactive-hil`でgoal_escalation_hil_*
トピック（ゴール前提エスカレーションの承認/却下）を「approve」で承認したが、続く
「確定値 (value):」への入力を空Enterで済ませた。これにより`verified_facts`へ空文字列が
`confidence='confirmed'`として書き込まれた。`revise_goal`（`cela_main.py:3398`）は
`_get_goal_escalation_hil_decision`（`cela_main.py:3327`）で`verified_facts`の値と
`_GOAL_ESCALATION_HIL_APPROVED_VALUE`（"approved"）との**厳密一致**を要求するため、
空文字列は一致せず「未承認」のまま。一方`issue_log.status`は'resolved'になるため、
`--pending-human-input`では解決済みに見え、`--resume`後もAI側は承認されていないと
判定する、という食い違いが発生した（ユーザー報告「--interactive-hilで対話的にHILを
解決しましたが、レジュームしてもまだ人間の回答待ちとなる」）。

根本原因: goal_escalation_hil_*トピックは、人間が入力すべき「確定値」が自由記述ではなく
`_GOAL_ESCALATION_HIL_APPROVED_VALUE`/`_GOAL_ESCALATION_HIL_REJECTED_VALUE`という
固定文字列でなければならない特殊なトピック種別だが、`_interactive_hil_issue_loop`の
approve分岐はこれを区別せず一律で自由記述を尋ねていた（reject分岐は既に"rejected"を
自動セットしていたが、これも全トピック一律であり、goal_escalation_hil以外のトピック
（例：license_surrender_countのような数値変数）にとっては'rejected'という文字列が
確定値として書き込まれてしまう、逆方向の問題があった）。

対応: `topic.startswith(_GOAL_ESCALATION_HIL_TOPIC_PREFIX)`でトピック種別を判定し、
- goal_escalation_hil_*: approve/reject双方とも、対応する定数値を自動セットし
  自由記述を求めない。
- それ以外: approveは従来通り自由記述を求める。rejectは'rejected'という文字列を
  もはや書き込まず、既存のverified_facts値（あれば）をそのまま人間確認済みへ
  格上げする（無ければ空文字列、AGENTS.md §13: 意味を持たない文字列を数値変数へ
  書き込まない）。

参照: BL-274（原設計、`_interactive_hil_issue_loop`本体）、BL-236（goal_escalation_hilの
原設計）、AGENTS.md §13（フォールバック値の下流汚染）、§18.3（DB訂正時のバックアップ・
official API優先）。実LLM API呼び出しは伴わない（query_AIはモンキーパッチ）。
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
    db_path = str(tmp_path / "test_bl308.db")
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


def _seed_goal_escalation(conn, run_id, escalation_id="ESC-test-0001"):
    cela_main._create_goal_escalation_hil_gate(
        conn, run_id, escalation_id, phase_id="phase_2", task_id="task_2_1",
        concern_summary="通学需要とCapEx上限が両立しない",
        implicated_constraint="CapEx上限1億円",
        why_conflicts="移動弱者支援という本質と無関係な通学需要が計画を破綻させる",
        suggested_reframe="SLA対象を生活維持移動に限定する",
        raised_by_role="user",
    )
    return cela_main._goal_escalation_hil_topic(escalation_id), cela_main._goal_escalation_hil_variable(escalation_id)


def test_bl308_approve_goal_escalation_topic_does_not_prompt_for_free_text_value(db_conn):
    """[BL-308本体・不具合の直接再現の逆] goal_escalation_hil_*トピックをapproveすると、
    「確定値 (value):」への入力を一切求めず、_GOAL_ESCALATION_HIL_APPROVED_VALUEが
    自動的に書き込まれること。入力スクリプトに値を含めていないため、もし実装が誤って
    値入力を要求すればinput_fnがStopIterationを送出しテストが失敗する。"""
    conn, run_id = db_conn
    topic, variable_name = _seed_goal_escalation(conn, run_id)
    # "確定値"のプロンプトが出ないはずなので、質問ループを空Enterで抜けた後は
    # unit/source/commentの3つだけ用意する。
    input_fn = _scripted_input("", "approve", "", "", "承認します")

    cela_main._interactive_hil_issue_loop(conn, run_id, topic, input_fn, lambda m: None)

    fact = conn.execute(
        "SELECT value, confidence FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, variable_name)
    ).fetchone()
    assert fact["value"] == cela_main._GOAL_ESCALATION_HIL_APPROVED_VALUE
    assert fact["confidence"] == "confirmed"


def test_bl308_reproduces_original_bug_when_fix_is_bypassed(db_conn):
    """[根本原因の再現] BL-308適用前の挙動（value入力欄へ空文字列を人間が渡すケース）を
    _answer_human_inputへ直接シミュレートし、_get_goal_escalation_hil_decisionが
    確かに'approved'と一致しない（＝revise_goalが拒否される）ことを確認する。
    これはBL-308が防いでいる実害そのものの再現。"""
    conn, run_id = db_conn
    topic, variable_name = _seed_goal_escalation(conn, run_id, escalation_id="ESC-test-0002")
    # BL-308適用前に実際に起きていたこと: 人間が空文字列をvalueとして確定してしまう。
    cela_main._answer_human_input(conn, run_id, topic, "", "", "human_operator", "承認のつもり")
    decision = cela_main._get_goal_escalation_hil_decision(conn, run_id, "ESC-test-0002")
    assert decision != cela_main._GOAL_ESCALATION_HIL_APPROVED_VALUE
    assert decision == ""


def test_bl308_reject_goal_escalation_topic_uses_rejected_constant(db_conn):
    """[非退行] goal_escalation_hil_*トピックのreject分岐は、引き続き
    _GOAL_ESCALATION_HIL_REJECTED_VALUEを自動セットすること。"""
    conn, run_id = db_conn
    topic, variable_name = _seed_goal_escalation(conn, run_id, escalation_id="ESC-test-0003")
    input_fn = _scripted_input("", "reject", "通学需要も含めるべきと判断")

    cela_main._interactive_hil_issue_loop(conn, run_id, topic, input_fn, lambda m: None)

    fact = conn.execute(
        "SELECT value FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, variable_name)
    ).fetchone()
    assert fact["value"] == cela_main._GOAL_ESCALATION_HIL_REJECTED_VALUE


def test_bl308_topic_detection_uses_shared_prefix_constant():
    """[配線確認・§15.1] トピック種別の判定が、goal_escalation_hil_topic/variableの生成に
    使われているのと同じ定数（_GOAL_ESCALATION_HIL_TOPIC_PREFIX）を参照していること
    （固有のプレフィックス文字列をハードコードで再定義していないか）。"""
    import inspect
    src = inspect.getsource(cela_main._interactive_hil_issue_loop)
    assert "topic.startswith(_GOAL_ESCALATION_HIL_TOPIC_PREFIX)" in src


def test_bl308_rejected_value_constant_exists_and_matches_original_literal():
    """[非退行] 新設した_GOAL_ESCALATION_HIL_REJECTED_VALUE定数が、従来コード中で使われて
    いたリテラル"rejected"と同じ値であること（human_research_promptの案内文言
    "--value rejected"とも整合する）。"""
    assert cela_main._GOAL_ESCALATION_HIL_REJECTED_VALUE == "rejected"
