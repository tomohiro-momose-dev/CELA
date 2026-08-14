"""
BL-219: task_plannerが計画分解の段階で置いた暫定係数を構造化して残し、
task_plan_reviewerが計画承認時に残した個別指摘を、実行フェーズのExpert/Detector/
User AIへ確実に届ける。

きっかけ: ユーザーが実runのログ（run_id=1786457890-3273d6dd）を調査した際、
「1日の需要8,500人」という数値の根拠が見つからないと指摘した。調査の結果、この数値は
task_plannerが計画分解の段階で自ら行った概算（ピーク3時間の外挿）であり、
task_plan_reviewerの`think`ツール呼び出しの中で「導出根拠が不明、要確認」と
明示的に指摘されていたにもかかわらず、その指摘が構造化データとしてどこにも残らず、
後続タスク（task_1_4）の実行時には一切参照できなかったことが判明した。

原因は2つ：
1. task_plannerが計算に使った暫定係数を登録する手段が無かった（acceptance_criteria/
   descriptionの自由記述テキストに埋め込むだけで、read_verified_factで検索できる
   構造化記録にならない）。
2. task_plan_reviewerが`per_task_comments`でtask_id別に残した指摘（plan_draftsの
   「## レビュワーからの指摘（要修正）」セクション）は、task_plannerが差し戻し後に
   read_plan_draftで読み返す場合しか消費されず、計画がconstraint_issue="none"で
   承認された場合は実行フェーズのExpert/Detector/User AIに一切届かなかった
   （AGENTS.md §15.4: 消費経路のない記録）。

対策：
- task_plannerのwrite_agreement呼び出し（既存のBL-095経路）に、暫定係数を
  confirmed_variables（confidence="provisional", citations type="expert_calculation"）
  として登録するようプロンプトで指示する（新規ツールは追加しない）。
- 「先送り事項」セクションと同じ自動注入経路（_get_deferred_notes_text）の隣に、
  「レビュワーからの指摘」セクションを読む_get_reviewer_comments_textを新設し、
  call_expert/call_detector/generate_user_utteranceの3箇所へ配線する
  （write_issueの新規権限付与はしない。BL-136の「明示的な先送り判断はUser AIのみ」
  という既存の設計原則には触れない）。

参照: docs/design/issue_backlog.md BL-219、BL-082（先送り事項の自動注入の前例）、
BL-087 Stage2（task_plan_reviewerのper_task_comments配線）。
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
    db_path = str(tmp_path / "test_bl219.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()


_SAMPLE_TASK = {
    "task_id": "task_1_4", "title": "平日1日需要の算出",
    "description": "属性別の移動需要を積み上げ、平日1日の総需要を算出する。",
    "acceptance_criteria": ["需要の内訳が示されること"],
    "depends_on": ["task_1_3"], "owns_variables": ["daily_demand"],
}


def test_bl219_get_reviewer_comments_text_empty_when_no_draft_or_placeholder(db_conn):
    """plan_draftが存在しない場合、およびプレースホルダのままの場合は空文字を返すこと。"""
    conn, run_id = db_conn
    assert cela_main._get_reviewer_comments_text(conn, run_id, "phase_1", "task_1_4") == ""

    cela_main.apply_plan_patch(
        conn, run_id, "phase_1", "task_1_4",
        cela_main._render_plan_skeleton(_SAMPLE_TASK), "task_planner", "初版作成",
    )
    assert cela_main._get_reviewer_comments_text(conn, run_id, "phase_1", "task_1_4") == ""


def test_bl219_get_reviewer_comments_text_returns_formatted_block_after_append(db_conn):
    """_append_reviewer_comment_to_planで指摘が追記された後、_get_reviewer_comments_text
    が整形済みブロックを返すこと（constraint_issue="none"で承認された場合を想定、
    「先送り事項」ではなく「レビュワーからの指摘」セクションのみを対象とする）。"""
    conn, run_id = db_conn
    ok = cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_4",
        comment_text="平日3時間ピーク需要の外挿係数（30-40%/50-60%）の根拠が不明。要検証。",
        task_for_skeleton=_SAMPLE_TASK,
    )
    assert ok is True
    text = cela_main._get_reviewer_comments_text(conn, run_id, "phase_1", "task_1_4")
    assert "外挿係数" in text
    assert "task_plan_reviewer" in text


def test_bl219_reviewer_comments_does_not_leak_into_deferred_notes(db_conn):
    """「レビュワーからの指摘」セクションへの追記が、別セクションである「先送り事項」の
    読み取り（_get_deferred_notes_text）に混入しないこと（BL-087 Stage2で見出しを
    分離した意図の回帰確認）。"""
    conn, run_id = db_conn
    cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_4",
        comment_text="レビュワー指摘のみのはずのテキスト", task_for_skeleton=_SAMPLE_TASK,
    )
    assert cela_main._get_deferred_notes_text(conn, run_id, "phase_1", "task_1_4") == ""


def test_bl219_deferred_notes_does_not_leak_into_reviewer_comments(db_conn):
    """逆方向: 「先送り事項」への追記が「レビュワーからの指摘」の読み取りに混入しないこと。"""
    conn, run_id = db_conn
    cela_main._append_deferred_note_to_plan(
        conn, run_id, "phase_1", "task_1_4",
        note_text="先送り事項のみのはずのテキスト", source_task_id="task_1_3",
        task_for_skeleton=_SAMPLE_TASK,
    )
    assert cela_main._get_reviewer_comments_text(conn, run_id, "phase_1", "task_1_4") == ""


def test_bl219_build_task_scope_context_includes_reviewer_comments_text(db_conn):
    """_build_task_scope_contextの返り値にreviewer_comments_textキーが含まれ、
    実際にplan_draftの内容を反映すること。"""
    conn, run_id = db_conn
    cela_main._append_reviewer_comment_to_plan(
        conn, run_id, "phase_1", "task_1_4",
        comment_text="スコープコンテキスト経由で見えるべき指摘", task_for_skeleton=_SAMPLE_TASK,
    )
    state = {
        "run_id": run_id,
        "current_phase": {"phase_id": "phase_1", "tasks": [_SAMPLE_TASK]},
        "current_task_id": "task_1_4",
        "phases": [{"phase_id": "phase_1", "tasks": [_SAMPLE_TASK]}],
        "task_criteria_status": {},
    }
    ctx = cela_main._build_task_scope_context(state, conn)
    assert "reviewer_comments_text" in ctx
    assert "スコープコンテキスト経由で見えるべき指摘" in ctx["reviewer_comments_text"]


def test_bl219_wiring_call_expert_and_generate_user_utterance():
    """「呼び出し忘れ」防止: call_expert・generate_user_utteranceのソースに、レビュワー
    指摘を実際にプロンプトへ注入する行（変数への代入だけでなく、見出し文言を含む
    埋め込み箇所そのもの）が含まれていること。変数代入の有無だけを見ると、実際の
    埋め込み行を削っても検知できない（revert-verificationで確認済み）ため、見出し
    文言 "BL-219: task_plan_reviewerからの指摘" の出現を対象にする。"""
    marker = "BL-219: task_plan_reviewerからの指摘"
    expert_src = inspect.getsource(cela_main.call_expert)
    user_src = inspect.getsource(cela_main.generate_user_utterance)
    assert marker in expert_src
    assert marker in user_src


def test_bl219_wiring_call_detector():
    """call_detectorは_get_reviewer_comments_textの戻り値をヘッダ文言ごと素通しする
    実装のため（BL-082のdeferred_notes_textと同じ流儀）、ソース中に見出し文言そのもの
    は現れない。関数呼び出しだけでなく、その戻り値をdeferred_notes_blockへ実際に
    連結する行（`deferred_notes_block += f"{_reviewer_comments}\\n"`）まで存在する
    ことを確認する（関数参照だけの確認では、連結行を削っても検知できない）。"""
    detector_src = inspect.getsource(cela_main.call_detector)
    assert "_get_reviewer_comments_text" in detector_src
    assert 'deferred_notes_block += f"{_reviewer_comments}\\n"' in detector_src


def test_bl219_wiring_generate_user_utterance_has_both_sites():
    """generate_user_utteranceには2つの注入箇所（Stage系の緩和ロジック側と、
    _build_task_scope_context経由の最終プロンプト側）があり、両方に見出し文言
    "BL-219: task_plan_reviewerからの指摘"が独立して現れること。"""
    user_src = inspect.getsource(cela_main.generate_user_utterance)
    assert user_src.count("BL-219: task_plan_reviewerからの指摘") >= 2


def test_bl219_no_new_write_issue_permission_granted():
    """[設計判断の回帰防止] task_plan_reviewerにwrite_issueのDEFER権限を新規付与しない
    （BL-136「明示的な先送り判断はUser AIのみ」という既存原則を維持する、という
    ユーザーとの合意）。ALLOWED_ISSUE_ACTIONS_BY_ROLEのソースにtask_plan_reviewerが
    含まれていないことを確認する。"""
    src = inspect.getsource(cela_main._check_issue_permission)
    assert '"task_plan_reviewer"' not in src


def test_bl219_task_planner_prompt_instructs_confirmed_variables_for_derived_values():
    """task_plannerのプロンプトが、write_agreementの同じ呼び出しでconfirmed_variables
    にconfidence="provisional"・citations type="expert_calculation"として暫定係数を
    登録するよう指示していること（新規ツールを追加せず、既存のBL-095 write_agreement
    経路を拡張したことの確認）。指示6・指示10それぞれ固有の文言で個別に検証する
    （どちらか一方だけ削られても検知できるように、共通語だけでは判定しない）。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "confirmed_variables" in src
    assert "expert_calculation" in src
    # 指示6固有: アンカリングへの言及（派生値のテキスト埋め込みだけでは不十分という指摘）
    assert "アンカリング" in src
    # 指示10固有: write_agreement呼び出しへのconfirmed_variables列挙指示そのもの
    assert "独立に確定させるべき" in src
    # 新規ツールを追加していないこと（既存のWRITE_AGREEMENT_TOOLのみで完結する設計）。
    assert "UPSERT_VERIFIED_FACT_TOOL" not in src
