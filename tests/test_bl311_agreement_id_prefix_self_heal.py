"""
BL-311: depends_on/freeze_agreement_idのID枝番省略を前方一致で自己修復する。

ユーザー要望（原文、1809ログの分析後）: 「write_agreementのdepends_on検証がID枝番の
不一致に対して代替経路（例：SUPERSEDEしたい対象の検索・再試行を促す）を提供していない、
これは、改善しましょう」。設計選択（AskUserQuestion）: 「自己修復＋候補提示
（Recommended）」を選択——前方一致でrun内にちょうど1件だけ見つかれば自己修復して処理を
継続し、0件なら現状通り拒否、2件以上（同一ミリ秒作成等の稀な曖昧ケース）なら候補ID一覧
付きで拒否する（憶測で決め打ちしない）。

経緯: log/2026-08-29/1809で、Detectorがdepends_on/citationに`AG-1787986026078`
（本来は`_new_record_id`が付与する枝番込みで`AG-1787986026078-8663f0`）と枝番を
落として参照し、write_agreementのguardに2回連続で拒否された（実ログ [19:06:38]
[19:06:59]）。結局Detectorはこの依存関係の記録を諦め、citationへ「検証漏れと判明」と
書くだけに留まり、古い誤った監査記録（AG-1787986026078-8663f0、「全数値完全一致・
計算ミスなし」と判定していたもの）はstatus='Reviewed'のまま差し替えられずDB内に
残存した（cela.dbで確認済み）。IDは`_new_record_id`によりf"{prefix}-{ts_ms}-
{uuid6桁}"形式で採番され（BL-215）、ts_ms部分はほぼ一意なため、前方一致による
自己修復は安全に成立する。

参照: BL-215（ID採番の一意性設計）、BL-224（depends_on→relation_edgesのW3エッジ）、
AGENTS.md §13.2（憶測でフォールバックしない）・§13.4（同種の検証は全書き込み経路で
対称に、freeze_agreementも同じ脆弱性を持っていたため同時に修正）・§13.5（クラスごと
修正）・§15.1（単一の解決ヘルパーを共有）。
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
    db_path = str(tmp_path / "test_bl311.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    # [BL-269相当の防御] _CURRENT_TASK_IDはteardownでのみリセットする既存フィクスチャ
    # 群（test_bl086等）に倣っていたが、フルスイート実行時に他のテストファイルが
    # 例外等でteardownを完走できず残した古い値（例: 'task_1_1'）を引き継ぐと、
    # BL-172のガードが本テストとは無関係なtask_idに対して誤爆する（実際にフルスイート
    # でのみ再現した）。setup側でも明示的に空へ倒し、他テストの残留状態に依存しない。
    cela_main._CURRENT_TASK_ID = ""
    cela_main._CURRENT_PHASE_ID = ""
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""


def _create_agreement(conn, run_id, topic="t"):
    """テスト用にagreementを1件作成し、実IDを返す。"""
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": topic,
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    return cela_main.get_agreements_from_db(conn, run_id)[-1]["id"]


def test_bl311_exact_match_unchanged_no_regression(db_conn):
    """[非退行] 厳密一致するIDはそのまま解決され、候補リストは空。"""
    conn, run_id = db_conn
    full_id = _create_agreement(conn, run_id)
    resolved, candidates = cela_main._resolve_agreement_id(conn, run_id, full_id)
    assert resolved == full_id
    assert candidates == []


def test_bl311_truncated_id_self_heals_when_unique(db_conn):
    """枝番（-uuid6桁）を落としたIDでも、run内で前方一致がちょうど1件ならフルIDへ自己修復する。"""
    conn, run_id = db_conn
    full_id = _create_agreement(conn, run_id)
    truncated_id = full_id.rsplit("-", 1)[0]  # 末尾の枝番だけ落とす
    assert truncated_id != full_id
    resolved, candidates = cela_main._resolve_agreement_id(conn, run_id, truncated_id)
    assert resolved == full_id
    assert candidates == []


def test_bl311_nonexistent_id_returns_none_with_no_candidates(db_conn):
    """[非退行] 本当に存在しないIDは、前方一致も無ければ(None, [])のまま（拒否される）。"""
    conn, run_id = db_conn
    _create_agreement(conn, run_id)
    resolved, candidates = cela_main._resolve_agreement_id(conn, run_id, "AG-0000000000000")
    assert resolved is None
    assert candidates == []


def test_bl311_ambiguous_prefix_returns_candidates_without_guessing(db_conn):
    """[境界値] 同一ミリ秒作成等でrun内に前方一致が2件以上ある場合、憶測で決め打ちせず
    候補ID一覧を返す（§13.2: 曖昧な場合はフォールバックしない）。"""
    conn, run_id = db_conn
    shared_prefix = "AG-9999999999999"
    id_a = f"{shared_prefix}-aaaaaa"
    id_b = f"{shared_prefix}-bbbbbb"
    for aid in (id_a, id_b):
        conn.execute(
            "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, "
            "proposed_by, entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, "
            "evidence, is_frozen, internal_thought_process, citations, run_id) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (aid, "CREATE", "Approved", "t", "d", "r", "user", "Decision",
             "", "", "[]", "{}", time.time(), "", 0, None, "[]", run_id),
        )
    conn.commit()
    resolved, candidates = cela_main._resolve_agreement_id(conn, run_id, shared_prefix)
    assert resolved is None
    assert sorted(candidates) == sorted([id_a, id_b])


def test_bl311_prefix_match_does_not_leak_across_run_id(db_conn):
    """[越権防止] 前方一致は同一run_idに限定され、他runのagreementへは自己修復しない。"""
    conn, run_id = db_conn
    other_run_id = f"other-{run_id}"
    full_id = f"AG-8888888888888-cccccc"
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, "
        "proposed_by, entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, "
        "evidence, is_frozen, internal_thought_process, citations, run_id) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (full_id, "CREATE", "Approved", "t", "d", "r", "user", "Decision",
         "", "", "[]", "{}", time.time(), "", 0, None, "[]", other_run_id),
    )
    conn.commit()
    resolved, candidates = cela_main._resolve_agreement_id(conn, run_id, "AG-8888888888888")
    assert resolved is None
    assert candidates == []


def test_bl311_write_agreement_depends_on_self_heals_and_writes_full_id(db_conn):
    """[統合] write_agreementのdepends_onへ枝番省略IDを渡しても自己修復され、
    実際にrelation_edges/depends_on列にはフルIDが記録される（1809ログの実障害の再現・解消確認）。"""
    conn, run_id = db_conn
    dep_full_id = _create_agreement(conn, run_id, topic="task_2_1_audit_verdict")
    dep_truncated_id = dep_full_id.rsplit("-", 1)[0]

    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Rejected", "topic": "task_2_1_ver8_audit",
        "decision_what": "d2", "reason_why": "r2", "entry_type": "Decision",
        "depends_on": [dep_truncated_id],
    })
    assert result["success"] is True

    agreements = cela_main.get_agreements_from_db(conn, run_id)
    new_agreement = next(a for a in agreements if a["topic"] == "task_2_1_ver8_audit")
    import json
    assert json.loads(new_agreement["depends_on"]) == [dep_full_id]

    edges = [tuple(r) for r in conn.execute(
        "SELECT from_ref, to_ref FROM relation_edges WHERE run_id=? AND relation_type='depends_on'",
        (run_id,),
    ).fetchall()]
    assert (f"agreement:{dep_full_id}", f"agreement:{new_agreement['id']}") in edges


def test_bl311_write_agreement_depends_on_still_rejects_nonexistent_id(db_conn):
    """[非退行] 本当に存在しないIDへのdepends_onは、従来通り拒否される（メッセージ文言も維持）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Rejected", "topic": "t2",
        "decision_what": "d2", "reason_why": "r2", "entry_type": "Decision",
        "depends_on": ["AG-0000000000000-ffffff"],
    })
    assert result["success"] is False
    assert "depends_onに存在しないID" in result["error"]


def test_bl311_freeze_agreement_self_heals_truncated_id(db_conn):
    """[統合] freeze_agreementツールに枝番省略IDを渡しても自己修復され、正しいagreementがfreezeされる
    （freeze_agreementはwrite_agreementのdepends_onと同じ脆弱性を持っていたため、対称に修正: §13.4）。"""
    conn, run_id = db_conn
    full_id = _create_agreement(conn, run_id)
    truncated_id = full_id.rsplit("-", 1)[0]

    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["freeze_agreement"]({
        "agreement_id": truncated_id, "reason": "test",
    })
    assert result["success"] is True
    assert result["agreement_id"] == full_id

    refreshed = cela_main.get_agreements_from_db(conn, run_id)
    assert refreshed[0]["is_frozen"] == 1


def test_bl311_cli_source_wiring_present():
    """[配線確認] _resolve_agreement_idがwrite_agreementのdepends_on検証とfreeze_agreementの
    両方から呼ばれていること（§13.4: 対称な検証）。"""
    import inspect
    src = inspect.getsource(cela_main)
    assert "def _resolve_agreement_id(" in src
    assert src.count("_resolve_agreement_id(conn, run_id,") == 2  # freeze_agreement + write_agreementのdepends_on検証
