"""
BL-337: integratorの完全性ゲート（未承認タスクの統合混入防止）＋承認ステータス取りこぼし修正。

GAIAパイロット（1959年USDA脱水青果物等級規格）のドライラン監査で、最終統合要件定義書に
task_1_2・task_1_3（最終回答を含む）が完全に欠落していたことが判明した。原因は2つ:

1. `integrator_node`のDeliverable抽出フィルタが`status == "Approved"`の文字列完全一致
   のみで、`RESOLVING_DELIVERABLE_STATUSES`（Approved_with_Conditions/Implicitly_Accepted
   を含む単一ソース）を使っていなかった。
2. 周期的reflection（route_after_expert_decisionのround_count % reflection_interval判定）
   がUser AIの4段階承認フロー（Stage1-4）を経由せず直接reflectionへ到達しうるため、
   Detector監査は通ったがUser AIが一度もレビューしていないDeliverable（status="Proposed"
   のまま）が統合ドキュメントから完全に無視されていた。

本テストは、integrator_nodeの冒頭に追加した完全性ゲート（計画上の全タスクが
RESOLVING_DELIVERABLE_STATUSESのDeliverableを持つか確認し、持たない場合は
generate_user_utteranceへ差し戻す）と、抽出フィルタの修正を検証する。

Cline CLI独立レビュー（AGENTS.md §19.1、2回実施）で検出されたC-1（state未クリアによる
ライブロック）・C-2（current_task_id未指定）・C-3（差し戻し上限欠如）・M-1（既存
_is_task_completedとの判定差異）・M-2（空task_idの黙殺）への対応も、対応するテストで
直接検証する。

参照: docs/design/back_log/BL-337/BL337_basic_design.md、docs/design/back_log/issue_backlog.md。
実LLM API呼び出しは伴わない（call_integratorはmonkeypatch）。
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
    db_path = str(tmp_path / "test_bl337.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


def _seed_deliverable(conn, run_id, task_id, phase_id, status, topic=None, agreement_id=None):
    topic = topic or f"{task_id} 成果物"
    cela_main.db_append_agreement({
        "id": agreement_id or f"AG-{task_id}-{uuid.uuid4().hex[:6]}",
        "action_type": "CREATE", "status": status, "topic": topic,
        "decision_what": f"{task_id}の本文です。" * 5,
        "reason_why": "r", "proposed_by": "expert", "entry_type": "Deliverable",
        "phase_id": phase_id, "task_id": task_id,
        "depends_on": [], "resource_claims": {}, "timestamp": time.time(),
    }, conn, run_id)


def _phases(*task_specs):
    """task_specsは(phase_id, task_id)のタプル列。同じphase_idはまとめられる。"""
    phases = {}
    for phase_id, task_id in task_specs:
        phases.setdefault(phase_id, {"phase_id": phase_id, "title": phase_id, "tasks": []})
        phases[phase_id]["tasks"].append({"task_id": task_id, "title": task_id})
    return list(phases.values())


def _base_state(run_id, phases):
    return {
        "run_id": run_id, "goal": "テストゴール\n", "phases": phases,
        "halt": False,
    }


def _patch_no_contradiction(monkeypatch, captured_final_text=None):
    def _fake_call_integrator(goal, final_text, goal_essence_text="", state=None):
        if captured_final_text is not None:
            captured_final_text.append(final_text)
        return {"contradictions": False}
    monkeypatch.setattr(cela_main, "call_integrator", _fake_call_integrator)


def _patch_save_and_track(monkeypatch, calls):
    def _fake_save(topic, content):
        calls.append((topic, content))
        return "fake/path.md"
    monkeypatch.setattr(cela_main, "save_deliverable_to_file", _fake_save)


# ---------------------------------------------------------------------------
# 1. 修正1: RESOLVING_DELIVERABLE_STATUSESによる抽出（Approved完全一致の取りこぼし修正）
# ---------------------------------------------------------------------------

def test_implicitly_accepted_deliverable_is_included(db_conn, monkeypatch):
    """[修正1] status="Implicitly_Accepted"のDeliverableが、従来の"Approved"完全一致では
    取りこぼされていたが、修正後は統合対象に含まれる。完全性ゲートを無関係化するため
    phases=[]にする。"""
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_2", "phase_1", "Implicitly_Accepted")
    state = _base_state(run_id, phases=[])

    save_calls = []
    _patch_save_and_track(monkeypatch, save_calls)
    _patch_no_contradiction(monkeypatch)

    result = cela_main.integrator_node(state)

    assert result["discussion_status"] == "completed"
    assert len(save_calls) == 1
    _, final_text = save_calls[0]
    assert "task_1_2の本文です。" in final_text


# ---------------------------------------------------------------------------
# 2. 完全性ゲート: 未承認タスクが残っていれば統合しない
# ---------------------------------------------------------------------------

def test_pending_task_blocks_integration_and_targets_review(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    # task_1_2はDeliverableなし（未着手/未提出）
    state = _base_state(run_id, phases=_phases(("phase_1", "task_1_1"), ("phase_1", "task_1_2")))

    save_calls = []
    _patch_save_and_track(monkeypatch, save_calls)
    integrator_calls = []
    monkeypatch.setattr(
        cela_main, "call_integrator",
        lambda *a, **kw: integrator_calls.append(1) or {"contradictions": False},
    )

    result = cela_main.integrator_node(state)

    assert result["pending_task_review_task_ids"] == ["task_1_2"]
    assert result["current_task_id"] == "task_1_2"
    assert result["current_phase"]["phase_id"] == "phase_1"
    assert result["ready_for_review"] is False
    assert result["pending_task_review_count"] == 1
    assert result.get("halt") is not True
    assert save_calls == [], "未承認タスクが残っているのに統合ファイルが保存された"
    assert integrator_calls == [], "未承認タスクが残っているのにcall_integratorが呼ばれた（ゲートはcall_integratorより前でreturnすべき）"


def test_proposed_status_deliverable_counts_as_pending(db_conn, monkeypatch):
    """[実インシデント再現] task_1_3のようにDeliverableが存在してもstatus="Proposed"の
    ままなら未承認として扱う。"""
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    _seed_deliverable(conn, run_id, "task_1_3", "phase_1", "Proposed")
    state = _base_state(run_id, phases=_phases(("phase_1", "task_1_1"), ("phase_1", "task_1_3")))

    save_calls = []
    _patch_save_and_track(monkeypatch, save_calls)
    _patch_no_contradiction(monkeypatch)

    result = cela_main.integrator_node(state)

    assert result["pending_task_review_task_ids"] == ["task_1_3"]
    assert save_calls == []


# ---------------------------------------------------------------------------
# 3. 正常系の非退行: 全タスク承認済みなら従来通り統合される
# ---------------------------------------------------------------------------

def test_all_tasks_resolved_integrates_normally(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    _seed_deliverable(conn, run_id, "task_1_2", "phase_1", "Implicitly_Accepted")
    _seed_deliverable(conn, run_id, "task_1_3", "phase_1", "Approved_with_Conditions")
    state = _base_state(run_id, phases=_phases(
        ("phase_1", "task_1_1"), ("phase_1", "task_1_2"), ("phase_1", "task_1_3")))

    save_calls = []
    _patch_save_and_track(monkeypatch, save_calls)
    _patch_no_contradiction(monkeypatch)

    result = cela_main.integrator_node(state)

    assert result["pending_task_review_task_ids"] == []
    assert result["pending_task_review_count"] == 0
    assert result["discussion_status"] == "completed"
    assert len(save_calls) == 1
    _, final_text = save_calls[0]
    for tid in ("task_1_1", "task_1_2", "task_1_3"):
        assert f"{tid}の本文です。" in final_text


# ---------------------------------------------------------------------------
# 4. [Cline指摘C-1] ゲート解消後、stateが正しくクリアされること（ライブロック防止）
# ---------------------------------------------------------------------------

def test_pending_state_clears_once_task_gets_approved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    _seed_deliverable(conn, run_id, "task_1_2", "phase_1", "Proposed")
    phases = _phases(("phase_1", "task_1_1"), ("phase_1", "task_1_2"))
    state = _base_state(run_id, phases=phases)
    _patch_no_contradiction(monkeypatch)
    monkeypatch.setattr(cela_main, "save_deliverable_to_file", lambda *a, **kw: "fake/path.md")

    first = cela_main.integrator_node(dict(state))
    assert first["pending_task_review_task_ids"] == ["task_1_2"]
    assert first["pending_task_review_count"] == 1

    # User AIがtask_1_2を承認したとみなし、新しいApproved行を追加する
    _seed_deliverable(conn, run_id, "task_1_2", "phase_1", "Approved")

    second_state = dict(state)
    second_state["pending_task_review_task_ids"] = first["pending_task_review_task_ids"]
    second_state["pending_task_review_count"] = first["pending_task_review_count"]
    second = cela_main.integrator_node(second_state)

    assert second["pending_task_review_task_ids"] == [], (
        "1回目のゲート発火で残った値が2回目の呼び出し（全タスク解消済み）でもクリアされていない"
        "（BL-337 Cline指摘C-1: state channelが値を保持し続けるライブロック）"
    )
    assert second["pending_task_review_count"] == 0


# ---------------------------------------------------------------------------
# 5. [Cline指摘C-3] 差し戻し上限（3回）を超えるとhaltすること
# ---------------------------------------------------------------------------

def test_pending_review_count_exceeds_limit_halts(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_2", "phase_1", "Proposed")
    state = _base_state(run_id, phases=_phases(("phase_1", "task_1_2")))
    state["pending_task_review_count"] = 3  # 既に3回差し戻し済み
    _patch_no_contradiction(monkeypatch)
    monkeypatch.setattr(cela_main, "save_deliverable_to_file", lambda *a, **kw: "fake/path.md")

    result = cela_main.integrator_node(state)

    assert result["pending_task_review_count"] == 4
    assert result["halt"] is True


# ---------------------------------------------------------------------------
# 6. [Cline指摘M-2] task_idを持たないタスクは黙ってスキップせず警告を出す
# ---------------------------------------------------------------------------

def test_task_without_task_id_is_warned_not_silently_skipped(db_conn, monkeypatch, capsys):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    phases = [{"phase_id": "phase_1", "title": "phase_1",
               "tasks": [{"task_id": "task_1_1", "title": "t1"}, {"title": "task_idの無いタスク"}]}]
    state = _base_state(run_id, phases=phases)
    _patch_no_contradiction(monkeypatch)
    monkeypatch.setattr(cela_main, "save_deliverable_to_file", lambda *a, **kw: "fake/path.md")

    cela_main.integrator_node(state)

    captured = capsys.readouterr().out
    assert "BL-337" in captured
    assert "task_id" in captured


# ---------------------------------------------------------------------------
# 7. 既存needs_revision_phasesの同型バグ修正（矛盾解消後にクリアされること）
# ---------------------------------------------------------------------------

def test_needs_revision_phases_clears_after_contradiction_resolved(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_deliverable(conn, run_id, "task_1_1", "phase_1", "Approved")
    state = _base_state(run_id, phases=[])  # 完全性ゲートは無関係化
    monkeypatch.setattr(cela_main, "save_deliverable_to_file", lambda *a, **kw: "fake/path.md")

    monkeypatch.setattr(
        cela_main, "call_integrator",
        lambda *a, **kw: {"contradictions": True, "affected_phases": ["phase_1"], "details": "d"},
    )
    first = cela_main.integrator_node(dict(state))
    assert first["needs_revision_phases"] == ["phase_1"]

    second_state = dict(state)
    second_state["needs_revision_phases"] = first["needs_revision_phases"]
    monkeypatch.setattr(cela_main, "call_integrator", lambda *a, **kw: {"contradictions": False})
    second = cela_main.integrator_node(second_state)

    assert second["needs_revision_phases"] == [], (
        "矛盾解消後もneeds_revision_phasesが前回値を保持している"
        "（BL-337でC-1検証中に発見した既存の同型バグ）"
    )


# ---------------------------------------------------------------------------
# 8. ルーティング分岐の存在証明（§17.1、既存BL-266のsource-sliceパターン踏襲）
# ---------------------------------------------------------------------------

def test_route_after_integrator_checks_halt_before_pending():
    """[実装後diffレビューで発見] integrator_nodeは差し戻し上限超過時にstate["halt"]=True
    を設定してreturnするが、その時点でpending_task_review_task_idsは非空のまま残る。
    haltチェックがpendingチェックより後ろ（または無い）だと、"🛑 強制停止します"と
    ログに出しながら実際にはhaltノードへ到達せずgenerate_user_utteranceへ差し戻され
    続ける、fail-openの沈黙失敗になる（route_after_user_decision等、他のroute_after_*
    関数が先頭でhaltを見る既存規約と揃える）。"""
    src = inspect.getsource(cela_main.build_graph)
    body_start = src.index("def route_after_integrator")
    halt_idx = src.index('if state.get("halt"):', body_start)
    pending_idx = src.index('if state.get("pending_task_review_task_ids"):', body_start)
    assert halt_idx < pending_idx, (
        "haltチェックがpending_task_review_task_idsチェックより後ろにある"
        "（halt=Trueでもgenerate_user_utteranceへ差し戻されてしまう）"
    )


def test_route_after_integrator_checks_pending_before_needs_revision():
    src = inspect.getsource(cela_main.build_graph)
    pending_idx = src.index('if state.get("pending_task_review_task_ids"):')
    needs_revision_idx = src.index(
        'if state.get("needs_revision_phases"):',
        src.index("def route_after_integrator"),
    )
    assert pending_idx < needs_revision_idx, (
        "pending_task_review_task_idsのチェックはneeds_revision_phasesより前になければ、"
        "統合未実施（pending）と統合済みだが矛盾あり（needs_revision）の意味が入れ替わる"
    )


def test_route_after_integrator_edges_include_generate_user_utterance():
    src = inspect.getsource(cela_main.build_graph)
    idx = src.index('"integrator",\n        route_after_integrator,')
    edges_dict = src[idx:idx + 300]
    assert '"generate_user_utterance": "generate_user_utterance"' in edges_dict
    assert '"orchestrator": "orchestrator"' in edges_dict
    assert '"arbiter": "arbiter"' in edges_dict
    assert '"halt": "halt"' in edges_dict
