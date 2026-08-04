"""
BL-087 Stage2: task_plan_reviewer_node（task_planner_node直後に1回だけ発火する、
実行開始前の計画レビューゲート）。

前提の質を上げる一連の改善（BL-087）のStage1（task_plannerの曖昧表記禁止指示・
User AIの二重指示バグ修正）に続く段階。task_planner_nodeがフェーズ・タスク計画を
生成した直後に、実行が始まる前にその計画全体（曖昧表現・タスク過不足・順序妥当性）を
レビューし、重大な問題があればtask_plannerへ差し戻して再生成させる。差し戻しは最大2回
までとし、上限到達後は指摘が残っていても計画を承認して進行する（無限ループ防止）。

参照: docs/design/issue_backlog.md BL-087、docs/design/decision_log.md D-059。
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
    db_path = str(tmp_path / "test_bl087_stage2.db")
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


SAMPLE_PHASES = [{"phase_id": "phase_1", "title": "テストフェーズ", "tasks": [
    {"task_id": "task_1_1", "acceptance_criteria": ["何かを確認する"], "depends_on": [], "owns_variables": []}
]}]


def test_reviewer_skips_when_plan_review_already_done(db_conn, monkeypatch):
    """plan_review_done済みなら、call_task_plan_reviewerを一切呼ばず即座にパスする
    （チェックポイント再開のたびにレビューLLM呼び出しが再発火するとトークン浪費になるため）。"""
    _, run_id = db_conn
    called = {"n": 0}
    monkeypatch.setattr(cela_main, "call_task_plan_reviewer", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    state = {"run_id": run_id, "goal": "テスト目標", "phases": SAMPLE_PHASES, "plan_review_done": True}
    result = cela_main.task_plan_reviewer_node(state)

    assert called["n"] == 0
    assert result["phases"] == SAMPLE_PHASES


def test_reviewer_skips_when_no_phases_yet(db_conn, monkeypatch):
    """phasesが未確定（task_plannerがまだ何も生成していない）ならレビュー自体をスキップする。"""
    _, run_id = db_conn
    called = {"n": 0}
    monkeypatch.setattr(cela_main, "call_task_plan_reviewer", lambda *a, **k: called.__setitem__("n", called["n"] + 1))

    state = {"run_id": run_id, "goal": "テスト目標", "phases": []}
    result = cela_main.task_plan_reviewer_node(state)

    assert called["n"] == 0
    assert result.get("plan_review_done") is not True


def test_reviewer_approves_plan_when_constraint_issue_none(db_conn, monkeypatch):
    """constraint_issue=noneなら、plan_review_done=Trueとしてphasesはそのまま維持される。"""
    _, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda phases, goal, **kwargs: {"risk": "low", "constraint_issue": "none", "comment": "問題なし", "observations": ""},
    )

    state = {"run_id": run_id, "goal": "テスト目標", "phases": SAMPLE_PHASES}
    result = cela_main.task_plan_reviewer_node(state)

    assert result["plan_review_done"] is True
    assert result["phases"] == SAMPLE_PHASES


def test_reviewer_rejects_plan_and_clears_phases_for_regeneration(db_conn, monkeypatch):
    """constraint_issue=majorかつretry_count<2なら、phasesをクリアしてtask_plannerへ
    差し戻す（task_planner_nodeの`not state.get("phases")`ガードにより再生成される）。
    指摘事項はplan_reviewer_feedbackへ保存され、retry_countがインクリメントされる。"""
    _, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda phases, goal, **kwargs: {"risk": "low", "constraint_issue": "major", "comment": "曖昧な表記がある", "observations": ""},
    )

    state = {"run_id": run_id, "goal": "テスト目標", "phases": SAMPLE_PHASES, "plan_reviewer_retry_count": 0}
    result = cela_main.task_plan_reviewer_node(state)

    assert result["phases"] == []
    assert result["plan_reviewer_retry_count"] == 1
    assert result["plan_reviewer_feedback"] == "曖昧な表記がある"
    assert result.get("plan_review_done") is not True


def test_reviewer_gives_up_after_retry_limit_reached(db_conn, monkeypatch):
    """retry_countが上限（2）に達した状態でmajorが出ても、無限ループにせず承認して進行する。"""
    _, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda phases, goal, **kwargs: {"risk": "low", "constraint_issue": "major", "comment": "まだ懸念あり", "observations": ""},
    )

    state = {"run_id": run_id, "goal": "テスト目標", "phases": SAMPLE_PHASES, "plan_reviewer_retry_count": 2}
    result = cela_main.task_plan_reviewer_node(state)

    assert result["plan_review_done"] is True
    assert result["phases"] == SAMPLE_PHASES


def test_call_task_planner_injects_reviewer_feedback_into_prompt(monkeypatch):
    """call_task_plannerにreviewer_feedbackを渡すと、プロンプト本文に差し戻し指摘が
    埋め込まれ、実際にqueryされたcontentへ反映されること。"""
    captured = {}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        captured["prompt"] = messages[0]["content"]
        return "[]"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    cela_main.call_task_planner("テスト目標", reviewer_feedback="acceptance_criteriaの曖昧な表記を直せ")

    assert "acceptance_criteriaの曖昧な表記を直せ" in captured["prompt"]
    assert "前回の計画案への差し戻し" in captured["prompt"]


def test_call_task_plan_reviewer_is_given_python_repl_tool(monkeypatch):
    """ユーザー指摘: 新規追加ノードも暗算に頼るとハルシネーションリスクが最上流に残るため、
    call_task_plan_reviewerにもpython_replツールを与えること。"""
    captured = {}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        captured["tools"] = tools
        return "{}"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    cela_main.call_task_plan_reviewer(SAMPLE_PHASES, "テスト目標")

    # [BL-092] diff_plan_draft_versionsツールが追加されたため、python_replが含まれることのみ
    # 確認する（完全一致ではなく部分一致。ツール一覧は今後も増えうる）。
    assert cela_main.PYTHON_REPL_TOOL in captured["tools"]


def test_call_task_planner_is_given_python_repl_tool(monkeypatch):
    """ユーザー指摘: task_plannerも比率・分割・単位換算等の計算を暗算で済ませず
    python_replで検証できるようツールを付与すること。"""
    captured = {}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        captured["tools"] = tools
        return "[]"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    cela_main.call_task_planner("テスト目標")

    # BL-093でthinkツールが追加されツールリストが増えたため、完全一致ではなく含有確認にする
    # （call_detector/call_task_plan_reviewerで既に採用済みのパターンと同じ）。
    assert cela_main.PYTHON_REPL_TOOL in captured["tools"]


def test_call_task_planner_without_feedback_omits_rejection_block(monkeypatch):
    """reviewer_feedbackを渡さない通常時は、差し戻しブロック自体がプロンプトに出ないこと。"""
    captured = {}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        captured["prompt"] = messages[0]["content"]
        return "[]"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)

    cela_main.call_task_planner("テスト目標")

    assert "前回の計画案への差し戻し" not in captured["prompt"]


def test_graph_wires_task_plan_reviewer_between_task_planner_and_generate_user_utterance():
    """build_graphが、task_planner→task_plan_reviewer→(条件分岐)という配線を持つこと。
    ソース確認ではなく実際にグラフを構築し、ノード名の存在を確認する。"""
    compiled = cela_main.build_graph()
    node_names = set(compiled.get_graph().nodes.keys())
    assert "task_plan_reviewer" in node_names


# ===========================================================================
# BL-087 Stage2改善（1549ドライランで判明した3点の是正）
# 1. Reviewerの評価較正（過敏性緩和・視点リバランス・「ゴール文にない数値の捏造要求」防止）
# 2. plan_draftsへのタスク単位の指摘書き込み（フェーズ・タスク表のホワイトボード化）
# 3. 派生値には根拠条件を必須で併記させる指示の徹底
# ===========================================================================

def test_reviewer_prompt_rebalances_structural_issues_over_numeric_precision():
    """曖昧表記の指摘に偏らず、タスク過不足・順序妥当性も同等以上に重視する指示、
    および「条件の明示」観点が追加されていること。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "同等以上に重視する" in src
    assert "条件の明示" in src


def test_reviewer_prompt_forbids_fabricating_values_absent_from_goal_text():
    """ゴール文自体が与えていない絶対値を無理に確定させる差し戻しをしないよう、
    実際にドライランで観測された数値捏造の実例がNG例として埋め込まれていること
    （Stage 1aでtask_1_3の実例を埋め込んだのと同じパターン）。[BL-116] 具体的な
    バス交通ドメインの数値（旧: 「総ルート長80km」）はドメイン非依存の表現へ
    一般化されたため、一般化後の表現（「総量100単位」）で検証する。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "総量100単位" in src
    assert "でっち上げ" in src


def test_reviewer_output_schema_includes_per_task_comments():
    """call_task_plan_reviewerのプロンプトが、plan_draftsへ書き込むための
    per_task_comments（task_id単位の指摘配列）を出力形式として要求していること。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "per_task_comments" in src
    assert '"task_id"' in src


def test_call_task_planner_prompt_requires_condition_for_derived_values():
    """派生値（比率・制約から計算した数値）を書く際は、根拠条件を必ず併記させる
    指示がtask_plannerのプロンプトに含まれていること（「3台が上限」のような
    条件抜きの断定が、後続AIに絶対制約と誤読されるのを防ぐ）。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "根拠条件" in src
    assert "派生値" in src


def test_render_plan_skeleton_includes_reviewer_comment_heading():
    """_render_plan_skeletonが生成する骨格文書に、「先送り事項」と並んで
    「レビュワーからの指摘（要修正）」セクションが含まれること。"""
    skeleton = cela_main._render_plan_skeleton(SAMPLE_PHASES[0]["tasks"][0])
    assert cela_main._PLAN_REVIEW_HEADING in skeleton
    assert cela_main._PLAN_REVIEW_PLACEHOLDER in skeleton
    assert cela_main._PLAN_DEFERRED_HEADING in skeleton


def test_append_reviewer_comment_to_plan_lazily_seeds_and_appends(db_conn):
    """plan_draftが未生成でも、_append_reviewer_comment_to_planがtask_for_skeletonから
    骨格文書を生成した上でレビュワー指摘を追記すること（_append_deferred_note_to_planの
    完全なミラー）。"""
    conn, run_id = db_conn
    task = SAMPLE_PHASES[0]["tasks"][0]
    ok = cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_1",
        comment_text="acceptance_criteriaの表現が曖昧です", task_for_skeleton=task,
    )
    assert ok is True
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_1", "task_1_1")
    assert latest is not None
    assert "acceptance_criteriaの表現が曖昧です" in latest["content"]
    # レビュワー指摘セクション直後がプレースホルダのままでないことを確認する（先送り事項
    # セクションは未使用のまま残るため、同一文字列のプレースホルダに対するグローバルな
    # not in判定は使えない）。
    after_heading = latest["content"].split(cela_main._PLAN_REVIEW_HEADING + "\n", 1)[1]
    assert not after_heading.startswith(cela_main._PLAN_REVIEW_PLACEHOLDER)


def test_append_reviewer_comment_to_plan_accumulates_multiple_appends(db_conn):
    """複数回の追記が蓄積され、既存のレビュワー指摘や他セクション（先送り事項等）を
    上書きしないこと。"""
    conn, run_id = db_conn
    task = SAMPLE_PHASES[0]["tasks"][0]
    cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_1", "1つ目の指摘", task_for_skeleton=task,
    )
    cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_1", "2つ目の指摘", task_for_skeleton=task,
    )
    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_1", "task_1_1")
    assert latest["version"] == 2
    assert "1つ目の指摘" in latest["content"]
    assert "2つ目の指摘" in latest["content"]
    assert "受入基準" in latest["content"]


def test_append_reviewer_comment_to_plan_noop_when_target_unresolvable(db_conn):
    """plan_draftが存在せず、task_for_skeletonもNoneの場合は例外を出さずFalseを返すこと。"""
    conn, run_id = db_conn
    ok = cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_9", "task_nonexistent", "届かないはずの指摘", task_for_skeleton=None,
    )
    assert ok is False


def test_find_phase_id_for_task_resolves_and_falls_back_to_empty():
    """_find_phase_id_for_taskがphases配列からphase_idを正しく解決し、
    見つからない場合は空文字を返すこと。"""
    assert cela_main._find_phase_id_for_task(SAMPLE_PHASES, "task_1_1") == "phase_1"
    assert cela_main._find_phase_id_for_task(SAMPLE_PHASES, "task_nonexistent") == ""


def test_task_planner_node_seeds_plan_drafts_skeleton_for_every_task(db_conn, monkeypatch):
    """task_planner_nodeが初期計画生成直後に、全フェーズ・全タスク分のplan_draftsスケルトンを
    事前生成すること（従来は_append_deferred_note_to_plan等が呼ばれるまで存在せず、
    task_plan_reviewer_nodeが動く時点で書き込み先が無かった問題への対策）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "call_task_planner", lambda *a, **k: SAMPLE_PHASES)

    state = {"turn_count": 1, "phases": [], "run_id": run_id, "goal": "テスト目標"}
    cela_main.task_planner_node(state)

    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_1", "task_1_1")
    assert latest is not None
    assert latest["version"] == 1


def test_task_plan_reviewer_node_writes_per_task_comments_into_plan_drafts(db_conn, monkeypatch):
    """task_plan_reviewer_nodeが、call_task_plan_reviewerの返すper_task_commentsを
    plan_draftsへtask_id単位で書き込み、plan_reviewer_feedbackにもタスク別指摘が
    整形結合されて反映されること。"""
    conn, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "call_task_plan_reviewer",
        lambda phases, goal, **kwargs: {
            "risk": "medium", "constraint_issue": "major", "comment": "全体講評テキスト",
            "observations": "", "per_task_comments": [{"task_id": "task_1_1", "comment": "この記述は曖昧です"}],
        },
    )

    state = {"run_id": run_id, "goal": "テスト目標", "phases": SAMPLE_PHASES, "plan_reviewer_retry_count": 0}
    result = cela_main.task_plan_reviewer_node(state)

    latest = cela_main.get_latest_plan_draft(conn, run_id, "phase_1", "task_1_1")
    assert latest is not None
    assert "この記述は曖昧です" in latest["content"]

    assert "全体講評テキスト" in result["plan_reviewer_feedback"]
    assert "[task_1_1] この記述は曖昧です" in result["plan_reviewer_feedback"]
