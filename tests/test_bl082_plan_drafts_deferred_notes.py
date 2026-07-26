"""
BL-082: task_plannerの計画をwhiteboard_draftsと同種の版管理文書として永続化し、
先送り事項（Deferred）を対象タスクへ確実に申し送れるようにする。

`log/2026-07-24/1349`のドライランで、User AIが「積雪・通信エリアの区間切り出しは
task_2_1/task_2_2で具体化されるべき」と先送り判断を発言したが、以下の二重の理由で
この申し送りが消失することが判明した。

1. `call_decision_extractor`の「先送りの検出」ルールがExpert側の抽出ブランチにしか
   実装されておらず、User AI側のブランチには存在しなかった（今回の実例はUser AIの
   発言だったため抽出自体が発動しなかった）。
2. たとえ`entry_type="Directive", status="Deferred"`として正しく抽出されても、
   `_build_agreements_context`がentry_type="Directive"を無条件で全除外しており、
   後続タスクのExpert/User AI/Detectorには一切見えない構造だった。

対策として、`plan_drafts`テーブル（whiteboard_draftsの完全ミラー）を新設し、
`decision_extractor_node`が申し送り先task_idを解決した上でその計画文書へ追記、
`call_expert`・`generate_user_utterance`・`call_detector`の3箇所すべてで
参照できるよう配線した。

参照: docs/design/issue_backlog.md BL-082。
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
    db_path = str(tmp_path / "test_bl082.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


_SAMPLE_TASK = {
    "task_id": "task_2_1", "title": "必要車両台数の算出",
    "description": "予算・需要制約から必要台数を算出する。",
    "acceptance_criteria": ["予算内であること", "ピーク需要を満たすこと"],
    "depends_on": ["task_1_3"], "owns_variables": ["vehicle_count"],
}


def test_bl082_plan_draft_roundtrip(db_conn):
    """get_latest_plan_draft/apply_plan_patchがwhiteboard_draftsと同様に
    バージョンを積み増しながら往復できること。"""
    conn, run_id = db_conn
    assert cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1") is None

    v1 = cela_main.apply_plan_patch(conn, run_id, "phase_2", "task_2_1", "初版", "task_planner", "初版作成")
    assert v1 == 1
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert latest == {"version": 1, "content": "初版"}

    v2 = cela_main.apply_plan_patch(conn, run_id, "phase_2", "task_2_1", "第2版", "decision_extractor", "追記")
    assert v2 == 2
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert latest == {"version": 2, "content": "第2版"}


def test_bl082_append_deferred_note_lazily_seeds_skeleton(db_conn):
    """plan_draftが未生成の場合、_append_deferred_note_to_planがtask_for_skeletonから
    骨格文書を遅延生成した上で先送り事項を追記すること（一括事前シードではなく遅延生成）。"""
    conn, run_id = db_conn
    ok = cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="積雪・通信エリアの地形照合を要検証", source_task_id="task_1_3",
        task_for_skeleton=_SAMPLE_TASK,
    )
    assert ok is True
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert latest is not None
    assert "必要車両台数の算出" in latest["content"]
    assert "【task_1_3より】積雪・通信エリアの地形照合を要検証" in latest["content"]
    # [BL-087 Stage2改善] プレースホルダ文字列自体は後続の「レビュワーからの指摘」セクションに
    # 未使用のまま残るため（別セクションの空欄）、先送り事項セクション直後がプレースホルダで
    # ないことをピンポイントで確認する（グローバルなnot in判定は使えなくなった）。
    after_heading = latest["content"].split(cela_main._PLAN_DEFERRED_HEADING + "\n", 1)[1]
    assert not after_heading.startswith(cela_main._PLAN_DEFERRED_PLACEHOLDER)


def test_bl082_append_deferred_note_accumulates_multiple_appends(db_conn):
    """複数回の追記が正しく蓄積され、既存の申し送り事項を上書きしないこと
    （「次の見出しを探す」ロジックを使わない、見出し直後への固定挿入の回帰確認）。"""
    conn, run_id = db_conn
    cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="1つ目の申し送り", source_task_id="task_1_3", task_for_skeleton=_SAMPLE_TASK,
    )
    cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="2つ目の申し送り", source_task_id="task_1_1", task_for_skeleton=_SAMPLE_TASK,
    )
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    assert latest["version"] == 2
    assert "【task_1_3より】1つ目の申し送り" in latest["content"]
    assert "【task_1_1より】2つ目の申し送り" in latest["content"]
    # 他のセクション（確定すべき変数）が消えていないこと
    assert "vehicle_count" in latest["content"]


def test_bl082_append_deferred_note_noop_when_target_unresolvable(db_conn):
    """既存のplan_draftも無く、task_for_skeletonもNoneの場合（申し送り先task_idが
    解決できない）は例外を出さずFalseを返すこと。"""
    conn, run_id = db_conn
    ok = cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_9", "task_nonexistent",
        note_text="どこにも届かないはずの申し送り", source_task_id="task_1_3",
        task_for_skeleton=None,
    )
    assert ok is False
    assert cela_main.get_latest_plan_draft(conn, run_id, "phase_9", "task_nonexistent") is None


def test_bl082_heading_regex_ignores_false_positive_in_description(db_conn):
    """タスクのdescriptionに見出し文字列そのものが偶然含まれていても、
    行アンカー付き正規表現により誤って別位置に追記されないこと。"""
    conn, run_id = db_conn
    tricky_task = {
        **_SAMPLE_TASK,
        "description": "この説明文には偶然「## 先送り事項（他タスクからの申し送り）」という文字列が含まれる。",
    }
    ok = cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="正しい位置に追記されるべき申し送り", source_task_id="task_1_3",
        task_for_skeleton=tricky_task,
    )
    assert ok is True
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_2", "task_2_1")
    # 正規表現は行全体が見出しと一致する箇所（本物の見出し）にのみマッチするため、
    # description内の部分一致は誤ってヒットしない。
    content = latest["content"]
    real_heading_idx = content.index(cela_main._PLAN_DEFERRED_HEADING + "\n")
    note_idx = content.index("正しい位置に追記されるべき申し送り")
    assert note_idx > real_heading_idx


def test_bl082_get_deferred_notes_text_empty_when_no_draft_or_placeholder(db_conn):
    """plan_draftが存在しない場合、およびプレースホルダのままの場合は空文字を返すこと
    （プロンプトのトークン消費を避けるため）。"""
    conn, run_id = db_conn
    assert cela_main._get_deferred_notes_text(conn, run_id, "phase_2", "task_2_1") == ""

    cela_main.apply_plan_patch(
        conn, run_id, "phase_2", "task_2_1",
        cela_main._render_plan_skeleton(_SAMPLE_TASK), "task_planner", "初版作成",
    )
    assert cela_main._get_deferred_notes_text(conn, run_id, "phase_2", "task_2_1") == ""


def test_bl082_get_deferred_notes_text_returns_formatted_block_after_append(db_conn):
    """先送り事項が追記された後は、_get_deferred_notes_textが整形済みブロックを返すこと。"""
    conn, run_id = db_conn
    cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="積雪エリアの地形照合を要検証", source_task_id="task_1_3",
        task_for_skeleton=_SAMPLE_TASK,
    )
    text = cela_main._get_deferred_notes_text(conn, run_id, "phase_2", "task_2_1")
    assert "積雪エリアの地形照合を要検証" in text
    assert "申し送り" in text


def test_bl082_build_task_scope_context_includes_deferred_notes_text(db_conn):
    """_build_task_scope_contextの返り値にdeferred_notes_textキーが含まれ、
    実際にplan_draftの内容を反映すること。"""
    conn, run_id = db_conn
    cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_2", "task_2_1",
        note_text="申し送りテキスト", source_task_id="task_1_3", task_for_skeleton=_SAMPLE_TASK,
    )
    state = {
        "run_id": run_id,
        "current_phase": {"phase_id": "phase_2", "tasks": [_SAMPLE_TASK]},
        "current_task_id": "task_2_1",
        "phases": [{"phase_id": "phase_2", "tasks": [_SAMPLE_TASK]}],
        "task_criteria_status": {},
    }
    ctx = cela_main._build_task_scope_context(state, conn)
    assert "deferred_notes_text" in ctx
    assert "申し送りテキスト" in ctx["deferred_notes_text"]


def test_bl082_wiring_call_expert_and_generate_user_utterance_and_call_detector():
    """「呼び出し忘れ」防止: call_expert・generate_user_utterance・call_detectorの
    3箇所すべてのソースに先送り事項の参照が含まれていること。"""
    expert_src = inspect.getsource(cela_main.call_expert)
    user_src = inspect.getsource(cela_main.generate_user_utterance)
    detector_src = inspect.getsource(cela_main.call_detector)
    assert "deferred_notes_text" in expert_src
    assert "deferred_notes_text" in user_src
    assert "_get_deferred_notes_text" in detector_src


def test_bl082_wiring_decision_extractor_node_appends_deferred_notes():
    """decision_extractor_nodeのソースに、Deferred判定時の_append_deferred_note_to_plan
    呼び出し配線が含まれていること。"""
    src = inspect.getsource(cela_main.decision_extractor_node)
    assert "_append_deferred_note_to_plan" in src
    assert 'status == "Deferred"' in src
    assert "defer_to_task_id" in src


def test_bl082_wiring_both_extractor_branches_request_defer_to_task_id():
    """call_decision_extractorのプロンプトが、Expert・User双方のブランチで
    先送り検出とdefer_to_task_idの出力を要求していること（BL-023時点ではExpert側にしか
    無かった非対称性の回帰防止）。"""
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert src.count("BL-082") >= 2
    assert src.count("defer_to_task_id") >= 2
