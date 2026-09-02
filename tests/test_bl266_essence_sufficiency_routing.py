"""
BL-266 層4: `essence_sufficiency_concern_pending`フラグ（detector_nodeがセット）を、
reflectionへの即時escalationへ接続するルーティング拡張と、Reflector側の滞留閾値差別化。

【設計上の重要な訂正】Planエージェントの原案は`route_after_user_detector`/
`route_after_expert_detector`（detector直後、decision_extractorの前）に即時escalation
分岐を追加する設計だったが、直接コード確認の結果これは誤りと判明した。この位置だと
decision_extractor_node（発言から決定・合意事項を抽出するノード）を経由せずreflectionへ
直行してしまい、essence_sufficiency_concernは「発言自体は受理された」場合にも立ちうる
フラグであるため、受理されたはずの発言からの決定・合意事項抽出が丸ごとスキップされる
実装バグになる（3回連続差し戻しの既存ケースは発言そのものが却下されているため無関係）。
正しい挿入位置はdecision_extractor実行後の`route_after_user_decision`/
`route_after_expert_decision`である。

加えて、単に即時escalationするだけでは`reflection_node`のBL-145滞留判定
（3ラウンド固定）が独立して効くため、ユーザーが懸念した「3ラウンド遅延」問題が
実質解消されない。`essence_sufficiency_concern`由来のissue（topic接頭辞で識別）に限り、
滞留閾値を1ラウンドへ短縮した（ゼロにはしない——User AIに最低1ラウンドは
write_issue(RESOLVE/DEFER)で誤検知を訂正する機会を残すことが暴走防止の要件）。

参照: docs/design/back_log/BL-266/BL266_investigation.md。
実LLM API呼び出しは伴わない。ルーティング関数はbuild_graph内のクロージャのため、
test_bl181/test_bl183と同じ手法（inspect.getsource(cela_main.build_graph)でのソース
切り出し）で検証する。
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
    db_path = str(tmp_path / "test_bl266_routing.db")
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


def _build_graph_source() -> str:
    return inspect.getsource(cela_main.build_graph)


# --- pop-guard非干渉の回帰確認（BL-262と同種の事故クラス） --------------------

def test_is_detector_redo_required_does_not_include_essence_concern():
    """[CONSTRAINT] essence_sufficiency_concern_pendingは、発言のやり直し（pop-guard）とは
    別種のシグナルであり、_is_detector_redo_requiredへ絶対に含めてはならない。含まれると、
    受理された発言がpop-guardで誤って取り消される（BL-262の教訓の再発）。"""
    src = inspect.getsource(cela_main._is_detector_redo_required)
    assert "essence_sufficiency_concern" not in src


# --- ルーティング関数のソース確認: 誤った挿入位置（*_detector側）に無いこと ------

def test_route_after_user_detector_does_not_check_essence_concern():
    """[設計訂正の回帰確認] essence_sufficiency_concern_pendingのチェックは
    route_after_user_detector（decision_extractorの前）には存在しないこと
    （存在すると決定抽出がスキップされる実装バグへ逆戻りする）。"""
    src = _build_graph_source()
    idx = src.index("def route_after_user_detector(state")
    next_def_idx = src.index("def route_after_user_decision(state")
    body = src[idx:next_def_idx]
    assert "essence_sufficiency_concern" not in body


def test_route_after_expert_detector_does_not_check_essence_concern():
    src = _build_graph_source()
    idx = src.index("def route_after_expert_detector(state")
    next_def_idx = src.index("def route_after_expert_decision(state")
    body = src[idx:next_def_idx]
    assert "essence_sufficiency_concern" not in body


# --- ルーティング関数のソース確認: 正しい挿入位置（*_decision側）にあること ------

def _route_after_user_decision_body() -> str:
    src = _build_graph_source()
    idx = src.index("def route_after_user_decision(state")
    end_idx = src.index('"user_decision_extractor",\n        route_after_user_decision,', idx)
    return src[idx:end_idx]


def _route_after_expert_decision_body() -> str:
    src = _build_graph_source()
    idx = src.index("def route_after_expert_decision(state")
    end_idx = src.index('"expert_decision_extractor", route_after_expert_decision,', idx)
    return src[idx:end_idx]


def test_route_after_user_decision_checks_essence_concern_pending():
    body = _route_after_user_decision_body()
    assert "essence_sufficiency_concern_pending" in body
    assert '"reflection"' in body


def test_route_after_expert_decision_checks_essence_concern_pending():
    body = _route_after_expert_decision_body()
    assert "essence_sufficiency_concern_pending" in body
    assert '"reflection"' in body


def test_route_after_user_decision_resets_flag_after_check():
    """単発消費フラグであること——チェック直後にFalseへリセットする代入があること
    （goal_revision_pending_reviewと同型のライフサイクル）。"""
    body = _route_after_user_decision_body()
    idx = body.index("essence_sufficiency_concern_pending")
    nearby = body[idx: idx + 200]
    assert 'state["essence_sufficiency_concern_pending"] = False' in nearby


def test_route_after_expert_decision_resets_flag_after_check():
    body = _route_after_expert_decision_body()
    idx = body.index("essence_sufficiency_concern_pending")
    nearby = body[idx: idx + 200]
    assert 'state["essence_sufficiency_concern_pending"] = False' in nearby


def test_route_after_user_decision_checks_essence_before_transition_block():
    """遷移ブロック判定より本質充足性の懸念を優先すること（実装計画§4-2の判断:
    遷移ブロックは既に進行中の是正ループのため、それより先に割り込ませない設計も
    あり得たが、本実装は独立した新規シグナルとして優先させた。位置の回帰確認）。"""
    body = _route_after_user_decision_body()
    essence_idx = body.index("essence_sufficiency_concern_pending")
    transition_idx = body.index("task_transition_blocked_unapproved_task_id")
    assert essence_idx < transition_idx


def test_route_after_user_decision_destination_map_includes_reflection():
    """[設計訂正の回帰確認] route_after_user_decisionはこれまで一度もreflectionへ
    遷移したことがなく、宛先マップに新規追加が必須だった点の回帰確認
    （マップへの追加漏れがあると、"reflection"を返してもLangGraphが未知の宛先として
    エラーになる）。"""
    src = _build_graph_source()
    idx = src.index('"user_decision_extractor",\n        route_after_user_decision,')
    map_block = src[idx: idx + 400]
    assert '"reflection": "reflection"' in map_block


def test_route_after_expert_decision_destination_map_already_includes_reflection():
    """[対照] route_after_expert_decisionは既存の周期reflection遷移があるため、
    宛先マップの変更は不要だった点の確認（変更が必要だったのはuser側のみという
    非対称性の記録）。"""
    src = _build_graph_source()
    idx = src.index('"expert_decision_extractor", route_after_expert_decision,')
    map_block = src[idx: idx + 200]
    assert '"reflection": "reflection"' in map_block


def test_build_graph_compiles_without_error():
    """新規分岐追加後もグラフが例外なくコンパイルできること（宛先マップの記述 miss等の
    構造的エラーがあればここで検出される）。"""
    compiled = cela_main.build_graph()
    assert compiled is not None


# --- reflection_node: 滞留閾値の差別化 ------------------------------------------

def test_reflection_node_source_defines_reduced_threshold_for_essence_topic():
    src = inspect.getsource(cela_main.reflection_node)
    assert "_BL266_ESSENCE_STALE_ROUNDS = 1" in src
    assert "_DEFAULT_STALE_ROUNDS = 3" in src
    assert 'essence_sufficiency_concern_' in src


def _seed_escalated_issue(conn, run_id: str, topic: str, task_id: str = "task_1_1") -> None:
    now = time.time()
    conn.execute(
        "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
        "description, occurrence_count, last_seen_task_id, defer_to_task_id, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, ?, ?, 'major', 'escalated', ?, 1, ?, '', ?, ?)",
        (uuid.uuid4().hex, run_id, topic, "detector_auto", "phase_1", task_id, "テスト懸念", task_id, now, now),
    )
    conn.commit()


def _minimal_reflection_state(run_id: str, round_count: int) -> dict:
    return {
        "run_id": run_id,
        "goal": "テストゴール",
        "decisions": [],
        "agreements": [],
        "chat_history": [],
        "turn_count": 1,
        "max_turns": 50,
        "constraint_issue_log": [],
        "risk_register": [],
        "round_count": round_count,
        "halt": False,
    }


def test_essence_topic_becomes_stale_after_one_round(db_conn, monkeypatch):
    """essence_sufficiency_concern_接頭辞のissueは、1ラウンド経過だけでplan_revision_reasonへ
    昇格すること（通常issueの3ラウンド閾値より短い）。
    【リバート検出】4-3の閾値差別化を固定3へ戻すと失敗する。"""
    conn, run_id = db_conn
    topic = "essence_sufficiency_concern_task_1_1"
    _seed_escalated_issue(conn, run_id, topic)

    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "make_decision", lambda **kwargs: {"who": "reflection"})
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *args, **kwargs: None)

    state = _minimal_reflection_state(run_id, round_count=0)
    # 1ラウンド目でissueを認識させる（first_seen_round=0を記録するだけ、まだ昇格しない）
    cela_main.reflection_node(state)
    assert state.get("plan_revision_reason") is None

    state["round_count"] = 1
    cela_main.reflection_node(state)

    assert state.get("plan_revision_reason") is not None
    assert topic in state["plan_revision_reason"]
    assert len(state.get("plan_revision_issue_ids", [])) == 1


def test_normal_topic_still_requires_three_rounds(db_conn, monkeypatch):
    """[対照] essence_sufficiency_concern_接頭辞を持たない通常issueは、従来どおり3ラウンド
    経過するまでplan_revision_reasonへ昇格しないこと（既存BL-144/BL-145の不変条件の回帰防止）。"""
    conn, run_id = db_conn
    topic = "ordinary_topic_task_1_1"
    _seed_escalated_issue(conn, run_id, topic)

    monkeypatch.setattr(cela_main, "call_reflection", lambda state, config: {
        "still_aligned": True, "discussion_status": "continuing", "note": "",
    })
    monkeypatch.setattr(cela_main, "config", {}, raising=False)
    monkeypatch.setattr(cela_main, "make_decision", lambda **kwargs: {"who": "reflection"})
    monkeypatch.setattr(cela_main, "db_append_decision", lambda *args, **kwargs: None)

    state = _minimal_reflection_state(run_id, round_count=0)
    cela_main.reflection_node(state)

    state["round_count"] = 1
    cela_main.reflection_node(state)
    assert state.get("plan_revision_reason") is None, "1ラウンドでは通常issueは昇格しないはず"

    state["round_count"] = 2
    cela_main.reflection_node(state)
    assert state.get("plan_revision_reason") is None, "2ラウンドでは通常issueは昇格しないはず"

    state["round_count"] = 3
    cela_main.reflection_node(state)
    assert state.get("plan_revision_reason") is not None, "3ラウンド経過で通常issueは昇格するはず"
