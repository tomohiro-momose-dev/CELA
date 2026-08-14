"""
BL-212: `write_agreement`（action_type=SUPERSEDE）に、BL-062が想定した「ホワイトボードには
触れない短い無効化理由文」（decision_whatが200字以下）が渡されると、新しく作られる「有効」な
Deliverable行のdecision_whatがその短い理由文そのものになり、"WHITEBOARD:"プレフィックスを
失う。以降の`write_agreement(action_type=UPDATE, edits=...)`は、この短い理由文を
`old_content.startswith("WHITEBOARD:")`で判定する旧ロジックにより`is_whiteboard=False`と
誤判定し、`base_content=old_content`（短い理由文）に対してExpertの実際のホワイトボード引用
（`whiteboard_drafts`側には無傷で残っている）を照合してしまうため、editsが必ず0件一致で
失敗し続ける。

実インシデント: `log/2026-08-11/1034`（BL-211修正の検証run）で、Userがtask_4_2の承認を
撤回する際、DetectorがSUPERSEDE+短い無効化理由文（45字）でDeliverableを無効化し、続けて
Userも同種のUPDATE+短い撤回理由文（62字・105字）を重ねた結果、以降のExpertによる
`write_agreement(edits=...)`が17回連続で「old_textが現在のホワイトボード内容に見つかりません
でした（緩い一致0件）」に失敗した。`read_whiteboard_excerpt`では同じ語句がmatch_type='exact'
で存在確認できていたにもかかわらず失敗しており、`whiteboard_drafts`側の実データと
`agreements`側の判定ロジックが乖離していたことを示す。

対応：BL-131・BL-206と同じ設計方針（task_idを権威とし、agreements側の文字列表現は当てに
しない）に揃え、`is_whiteboard`の判定を`old_content`の文字列プレフィックスではなく
`get_latest_whiteboard(conn, run_id, phase_id, tid) is not None`（whiteboard_draftsに実際に
バージョンが存在するか）へ変更した。

参照: docs/design/back_log/issue_backlog.md BL-212、BL-131、BL-206、BL-062、BL-080。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl212.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


def _phases():
    return [{"phase_id": "phase_4", "tasks": [{"task_id": "task_4_2"}]}]


def _state(run_id):
    return {"run_id": run_id, "current_task_id": "task_4_2", "phases": _phases()}


_UNIQUE_LINE = "市街地は20分以内、山間部は30分以内のSLAを判定する。"


def _create_deliverable(conn, run_id, topic="task_4_2 停留所・予約・利用データ記録の設計"):
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": topic,
            "decision_what": _UNIQUE_LINE + "\n" + "X" * 300,
            "reason_why": "初版", "entry_type": "Deliverable",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")
    return topic


def _short_reason_supersede(conn, run_id, topic, caller_role, decision_what):
    """[BL-062] ホワイトボードには触れない短い無効化理由文によるSUPERSEDE（200字以下）。"""
    cela_main._CURRENT_CALLER_ROLE = caller_role
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "SUPERSEDE", "status": "Rejected", "topic": topic,
            "target_topic": topic,
            "decision_what": decision_what, "reason_why": "無効化",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")


# ---------------------------------------------------------------------------
# 1. 実インシデントの再現・修正確認
# ---------------------------------------------------------------------------

def test_edits_still_resolve_after_short_reason_supersede(db_conn):
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)

    _short_reason_supersede(conn, run_id, topic, "detector",
                            "task_4_2の承認維持・task_4_3移行の根拠となった承認済み成果物を無効化する。")

    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": topic + "（修正版）",
            "target_topic": topic, "reason_why": "SLA判定の修正",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
            "edits": [{"old_text": _UNIQUE_LINE, "new_text": "市街地は15分以内、山間部は25分以内のSLAを判定する。"}],
        },
        _state(run_id),
    )

    assert result["success"] is True, (
        f"短い無効化理由文によるSUPERSEDEの後、実在するold_textの照合が失敗した（BL-212再発）: {result.get('error')}"
    )


def test_chained_short_reason_supersedes_still_resolve(db_conn):
    """実インシデントは detector のSUPERSEDE → user のUPDATE(短文) が2回連続していた。
    孤児化した「短文行」が連鎖しても、修正後は毎回whiteboard_draftsを直接見るため壊れないこと。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)

    _short_reason_supersede(conn, run_id, topic, "detector",
                            "task_4_2の承認維持・task_4_3移行の根拠となった承認済み成果物を無効化する。")
    _short_reason_supersede(conn, run_id, topic, "user",
                            "task_4_2の承認およびtask_4_3への移行判断を撤回し、task_4_2を修正再提出待ちのRejectedとする。")
    _short_reason_supersede(conn, run_id, topic, "user",
                            "task_4_2の承認およびtask_4_3への移行判断を明確に撤回し、task_4_2を修正再提出待ちの"
                            "Rejectedとする。前回の承認は無効であり、修正版が再提出されるまでtask_4_3以降へ進めない。")

    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": topic + "（再修正版）",
            "target_topic": topic, "reason_why": "SLA判定の再修正",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
            "edits": [{"old_text": _UNIQUE_LINE, "new_text": "市街地は15分以内、山間部は25分以内のSLAを判定する。"}],
        },
        _state(run_id),
    )

    assert result["success"] is True, (
        f"短い無効化理由文の連鎖の後、実在するold_textの照合が失敗した: {result.get('error')}"
    )


def test_is_whiteboard_flag_survives_short_reason_supersede():
    """`_commit_agreement_from_tool`内のis_whiteboard判定ロジックそのものを、修正後の
    `_write_agreement_impl`ソースで固定する（テスト側の再現ロジックと本体の配線が
    乖離しても検知できるようにするため）。"""
    import inspect
    src = inspect.getsource(cela_main._commit_agreement_from_tool)
    assert 'is_whiteboard = get_latest_whiteboard(conn, run_id, phase_id, tid) is not None' in src, (
        "is_whiteboardの判定がwhiteboard_drafts直接参照から後退している（BL-212再発）"
    )
    assert 'old_content.startswith("WHITEBOARD:")' not in src.split("is_whiteboard =", 1)[-1].split("\n")[0]


# ---------------------------------------------------------------------------
# 1.5. BL-212追補（F2/F5）: 汚染された短文行が「伝播し続けない」こと
#
# BL-213横断監査のF2で、is_whiteboardの判定は直したが保護分岐の中身が
# `content = old_content`のままだったため、一度BL-212の短文行が生まれると
# 以降の全ての更新へ短文がコピーされ、agreements側は永久にポインタを取り戻せない
# （汚染が世代を越えて伝播する）ことが判明した。F5は同じ問題が
# decision_extractor_nodeのフォールバック経路にも残っていたもの。
# ---------------------------------------------------------------------------

def _short_comment_update(conn, run_id, topic, caller_role, decision_what):
    """edits未指定・短文のUPDATE（User AI/Detectorの承認・却下コメントの典型形）。"""
    cela_main._CURRENT_CALLER_ROLE = caller_role
    return cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": topic,
            "target_topic": topic, "decision_what": decision_what, "reason_why": "承認",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )


def _active_deliverable_row(conn, run_id):
    return cela_main._find_active_deliverable_agreement(conn, run_id, "phase_4", "task_4_2")


def test_short_reason_residue_is_repaired_on_next_protected_update(db_conn):
    """[F2] 短文SUPERSEDEで汚染された後、次の保護されたUPDATEでポインタが復元されること。
    従来は`content = old_content`のため短文が伝播し続けていた。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)
    _short_reason_supersede(conn, run_id, topic, "detector", "承認済み成果物を無効化する。")

    # 汚染の確認（この時点ではポインタを失っている）
    assert not _active_deliverable_row(conn, run_id)["decision_what"].startswith("WHITEBOARD:")

    result = _short_comment_update(conn, run_id, topic, "user", "内容を確認し承認します。")
    assert result["success"] is True, result.get("error")

    row = _active_deliverable_row(conn, run_id)
    assert row["decision_what"] == "WHITEBOARD:phase_4:task_4_2", (
        f"保護分岐がポインタを復元していない（BL-213 F2再発）: {row['decision_what']!r}"
    )


def test_repaired_pointer_makes_integrator_see_real_content(db_conn):
    """[F2→F1] ポインタが復元された結果、`integrator_node`の抽出条件
    （entry_type='Deliverable' かつ status='Approved'）に載る行が、短文ではなく
    実際のホワイトボード本文を指すこと。F1（最終統合文書に短文が載る）の前提条件が
    F2の修正によって解消されることの確認。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)
    _short_reason_supersede(conn, run_id, topic, "detector", "承認済み成果物を無効化する。")
    _short_comment_update(conn, run_id, topic, "user", "内容を確認し承認します。")

    approved = [
        a for a in cela_main.get_agreements_from_db(conn, run_id)
        if a["entry_type"] == "Deliverable" and a["status"] == "Approved"
    ]
    assert approved, "承認済みDeliverableが1件も無い"
    for a in approved:
        assert a["decision_what"].startswith(("WHITEBOARD:", "FILE_PATH:")), (
            f"承認済みDeliverableがポインタではなく短文を保持している（F1の実害条件）: {a['decision_what']!r}"
        )


def test_no_decision_what_update_also_repairs_pointer(db_conn):
    """[F2] decision_what/editsのいずれも無いUPDATE（状態のみ更新）でも、
    ホワイトボードが実在するならポインタへ復元されること。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)
    _short_reason_supersede(conn, run_id, topic, "detector", "承認済み成果物を無効化する。")

    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": topic,
            "target_topic": topic, "decision_what": "状態のみ更新します。", "reason_why": "承認",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")
    assert _active_deliverable_row(conn, run_id)["decision_what"] == "WHITEBOARD:phase_4:task_4_2"


def test_unpromoted_short_deliverable_is_not_falsely_pointed(db_conn):
    """[F2 非退行] ホワイトボードが一度も作られていない短文Deliverableに対しては、
    ポインタを捏造しないこと（is_whiteboardが偽なら従来通りold_contentを維持）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    create = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_4_2 短い暫定メモ",
            "decision_what": "暫定メモ（200字未満のためホワイトボード化されない）",
            "reason_why": "初版", "entry_type": "Deliverable",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert create["success"] is True, create.get("error")
    assert cela_main.get_latest_whiteboard(conn, run_id, "phase_4", "task_4_2") is None

    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "topic": "task_4_2 短い暫定メモ",
            "target_topic": "task_4_2 短い暫定メモ", "decision_what": "承認します。",
            "reason_why": "承認", "entry_type": "Deliverable",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")
    row = _active_deliverable_row(conn, run_id)
    assert not row["decision_what"].startswith("WHITEBOARD:"), (
        "ホワイトボード未作成なのにポインタを捏造した（存在しない実体を指す行が生まれる）"
    )


def test_decision_extractor_fallback_repairs_pointer(db_conn, monkeypatch):
    """[F5] write_agreementが呼ばれなかったターンのフォールバック経路でも、
    ポインタを失った行がホワイトボード実在の確認によって復元されること。
    従来は`old_content.startswith("WHITEBOARD:")`が偽になり保護が発火せず、
    LLMの200字要約で上書きされてフル本文が孤立していた。"""
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    topic = _create_deliverable(conn, run_id)
    _short_reason_supersede(conn, run_id, topic, "detector", "承認済み成果物を無効化する。")
    active_topic = _active_deliverable_row(conn, run_id)["topic"]

    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return ([{
            "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Approved",
            "target_topic": active_topic, "topic": active_topic,
            "content": "承認しました。（LLMによる短い要約）", "rationale": "受入基準を満たすため",
            "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_2",
        }], {"advances_to_phase_id": None, "advances_to_task_id": None})

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake)

    state = {
        "run_id": run_id, "phases": _phases(), "current_phase": _phases()[0],
        "current_task_id": "task_4_2",
        "chat_history": [{"role": "user", "content": "task_4_2を承認します。"}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False, "user_wrote_agreement": False,
    }
    cela_main.decision_extractor_node(state)

    row = _active_deliverable_row(conn, run_id)
    assert row["decision_what"] == "WHITEBOARD:phase_4:task_4_2", (
        f"フォールバック経路でポインタが復元されず、短い要約で上書きされた（BL-213 F5再発）: "
        f"{row['decision_what']!r}"
    )


def test_decision_extractor_fallback_does_not_touch_non_deliverable(db_conn, monkeypatch):
    """[F5 非退行] 同じtask_idにホワイトボードが存在しても、entry_typeがDeliverable以外の
    項目の本文をポインタ文字列へ差し替えないこと（判定をDeliverableに限定していることの確認）。"""
    conn, run_id = db_conn
    cela_main._DB_CONN = conn
    cela_main._CURRENT_RUN_ID = run_id
    _create_deliverable(conn, run_id)

    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "task_4_2 運用方針の合意",
            "decision_what": "初回の合意内容", "reason_why": "r", "entry_type": "Decision",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )

    def _fake(chat_history, existing_topics, target_role, owns_variables=None, valid_task_ids=None):
        return ([{
            "action_type": "UPDATE", "entry_type": "Decision", "status": "Approved",
            "target_topic": "task_4_2 運用方針の合意", "topic": "task_4_2 運用方針の合意",
            "content": "改訂後の合意内容", "rationale": "見直したため",
            "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_2",
        }], {"advances_to_phase_id": None, "advances_to_task_id": None})

    monkeypatch.setattr(cela_main, "call_decision_extractor", _fake)

    state = {
        "run_id": run_id, "phases": _phases(), "current_phase": _phases()[0],
        "current_task_id": "task_4_2",
        "chat_history": [{"role": "user", "content": "合意を改訂します。"}],
        "task_transition_blocked_issue_topics": [],
        "expert_wrote_agreement": False, "user_wrote_agreement": False,
    }
    cela_main.decision_extractor_node(state)

    decision = next(
        a for a in reversed(cela_main.get_agreements_from_db(conn, run_id))
        if a.get("entry_type") == "Decision" and a.get("status") != "Superseded"
    )
    assert decision["decision_what"] == "改訂後の合意内容", (
        f"Deliverable以外の本文までポインタへ差し替わった: {decision['decision_what']!r}"
    )


# ---------------------------------------------------------------------------
# 2. 非退行確認
# ---------------------------------------------------------------------------

def test_full_replacement_supersede_still_creates_new_whiteboard_version(db_conn):
    """[非退行] raw_content>200字のSUPERSEDE（全文置換、BL-080）は従来通り新バージョンを
    作成し、is_whiteboard判定にも影響しないこと。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)

    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "SUPERSEDE", "status": "Proposed", "topic": topic + "（全面改訂）",
            "target_topic": topic,
            "decision_what": "全面改訂後の新しい原文。" + "Y" * 300,
            "reason_why": "全面改訂", "entry_type": "Deliverable",
            "phase_id": "phase_4", "task_id": "task_4_2",
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")

    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_4", "task_4_2")
    assert latest is not None
    assert latest["version"] == 2
    assert "全面改訂後の新しい原文。" in latest["content"]


def test_edits_without_any_supersede_still_work(db_conn):
    """[非退行] SUPERSEDEを一度も経由しない通常のUPDATE(edits)フローが壊れていないこと。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)

    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": topic + "（修正版）",
            "target_topic": topic, "reason_why": "通常の修正",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
            "edits": [{"old_text": _UNIQUE_LINE, "new_text": "市街地は10分以内、山間部は20分以内のSLAを判定する。"}],
        },
        _state(run_id),
    )
    assert result["success"] is True, result.get("error")


def test_no_whiteboard_yet_still_reports_not_found(db_conn):
    """[非退行] whiteboard_draftsが一度も作られていないtask_idに対するUPDATE(edits)は、
    従来通り「更新対象のホワイトボードが見つかりません」で拒否されること
    （is_whiteboardをTrueへ誤検出しないこと）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Proposed", "topic": "task_4_2 存在しない成果物",
            "target_topic": "task_4_2 存在しない成果物", "reason_why": "r",
            "entry_type": "Deliverable", "phase_id": "phase_4", "task_id": "task_4_2",
            "edits": [{"old_text": "何か", "new_text": "何か別のもの"}],
        },
        _state(run_id),
    )
    assert result["success"] is False
    assert "見つかりません" in result["error"]


def test_short_reason_supersede_still_marks_previous_row_superseded(db_conn):
    """[非退行] 短い無効化理由文によるSUPERSEDEでも、対象のsupersede自体（旧行のstatus変更）は
    引き続き機能すること。"""
    conn, run_id = db_conn
    topic = _create_deliverable(conn, run_id)

    _short_reason_supersede(conn, run_id, topic, "detector", "承認済み成果物を無効化する。")

    rows = [
        dict(r) for r in conn.execute(
            "SELECT status, decision_what FROM agreements WHERE run_id=? AND task_id='task_4_2' "
            "ORDER BY timestamp", (run_id,)
        ).fetchall()
    ]
    assert rows[0]["status"] == "Superseded"
    assert rows[0]["decision_what"].startswith("WHITEBOARD:")
    assert rows[-1]["status"] != "Superseded"
