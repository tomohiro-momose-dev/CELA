"""
BL-254: BL-253フォローアップ（Reviewerに束ね判定軸を追加）の際、ユーザーから
「最近のタスクプランナーの実装でレビュワー側に抜けている点も洗い出してください」と
追加調査を依頼された。`call_task_planner`の指示1〜15と`call_task_plan_reviewer`の
観点・補足ブロックを全件突き合わせた結果、以下3件がReviewer側に未反映のギャップとして
見つかり、ユーザー承認のもと実装した：

1. BL-219（派生値のconfirmed_variables登録）: task_plannerは派生値の根拠をacceptance_
   criteria本文に書くだけでなく、write_agreementのconfirmed_variablesへconfidence=
   "provisional"で機械的に登録するよう指示されているが、Reviewerの観点4「条件の明示」は
   テキスト上の条件明記しかチェックしておらず、このDB登録が実際に行われたかは未確認だった。
2. BL-196（Expertの実行環境で到達可能な水準か）: task_plannerには「Expertが実際に使える
   ツールで到達可能な水準にacceptance_criteriaを留めよ」という指示があるが、Reviewerには
   実行可能性そのものを疑う観点が一つも無かった。
3. BL-250（範囲限定文言への調査許可併記）: 「正式決定しないでください」と書く際は「調査・
   提案は行ってよい」と併記せよというルールを、Reviewerは一切チェックしていなかった。

いずれも「生成側（task_planner）にだけ判定軸があり、監査側（Reviewer）に無い」という
BL-253と同型のパターン。Reviewerの観点を5個から8個（6・7・8として追加）へ拡張し、
導入文の個数表記・重大な問題の列挙も整合させた。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-254。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _reviewer_src() -> str:
    return inspect.getsource(cela_main.call_task_plan_reviewer)


def test_reviewer_prompt_lists_review_criteria_count_consistently():
    """観点の総数が5→8（BL-254）→9（BL-266で本質充足性を追加）→10（BL-294で定義監査を
    追加）と更新され、導入文の個数表記が一貫していること。9つ以前の古い表記が
    残っていないこと。"""
    src = _reviewer_src()
    assert "10個とも" in src
    assert "9つとも" not in src
    assert "8つとも" not in src
    assert "5つとも" not in src
    assert "4つとも" not in src


def test_reviewer_mentions_bl196_feasibility_criterion():
    """[BL-196] Expertが実際に使えるツールで到達可能な水準かを確認する観点が
    追加されていること。"""
    src = _reviewer_src()
    assert "BL-196" in src
    idx = src.index("BL-196")
    nearby = src[idx: idx + 400]
    assert "python_repl" in nearby
    assert "サンドボックス" in nearby or "到達可能" in nearby


def test_reviewer_mentions_bl250_scope_limit_caveat_criterion():
    """[BL-250] 範囲限定文言に調査許可の一文が併記されているかを確認する観点が
    追加されていること。"""
    src = _reviewer_src()
    assert "BL-250" in src
    idx = src.index("BL-250")
    nearby = src[idx: idx + 400]
    assert "正式" in nearby
    assert "調査" in nearby


def test_reviewer_mentions_bl219_confirmed_variables_criterion():
    """[BL-219] 派生値がconfirmed_variablesとして登録されているかを確認する観点が
    追加されていること。"""
    src = _reviewer_src()
    assert "BL-219" in src
    idx = src.index("BL-219")
    nearby = src[idx: idx + 400]
    assert "confirmed_variables" in nearby
    assert "read_verified_fact" in nearby


def test_reviewer_major_issue_enumeration_includes_new_categories():
    """「重大な問題」の列挙にも、新たに追加した3観点に対応するカテゴリが
    含まれていること（観点だけ追加してmajor判定基準の説明が古いままという
    不整合を防ぐ回帰チェック）。"""
    src = _reviewer_src()
    idx = src.index("重大な問題")
    nearby = src[idx: idx + 250]
    assert "到達不能" in nearby
    assert "調査許可併記漏れ" in nearby
    assert "confirmed_variables未登録" in nearby


def test_reviewer_has_read_verified_fact_tool_for_bl219_check():
    """BL-219チェック（confirmed_variables登録の確認）に必要なREAD_VERIFIED_FACT_TOOLが
    Reviewerのツールリストに含まれていること（新規に追加する必要はなく既存で足りる
    ことの確認）。"""
    src = _reviewer_src()
    assert "READ_VERIFIED_FACT_TOOL" in src
