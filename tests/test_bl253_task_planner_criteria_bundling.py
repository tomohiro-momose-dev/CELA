"""
BL-253: task_plannerの分割ルール（BL-023、acceptance_criteria最大3個・超過時に分割）は
「個数」だけを見ており、「1個のacceptance_criteriaが実質的に複数の独立した分析を暗黙に
束ねていないか」は判定していなかった。

ユーザーが`log/2026-08-16/1832`の実際の成果物（task_2_1「需要調査設計とピーク需要の推計
方法」）を見て「一つのタスクでの成果物もなかなかの量がある。サブタスク化して個別項目に
集中させる方が良いか？」と提起。調査したところ、task_2_1のacceptance_criteriaは3個以内
（BL-023のルール通り）だったが、実際の成果物は①調査方法の役割・限界表、②午前ピーク分離の
8段階手順、③縮小・基準・上振れの3シナリオそれぞれの独立した設計、④2系統の後続タスクへの
引継ぎ、⑤検証状況一覧、という複数の独立した分析を1つの受入基準の中に束ねたものだった。
これはBL-023が元々解決しようとした「粗い分解による検証コストの乗算的増大」の抜け道
（acceptance_criteriaの個数制約はクリアしつつ、1個の基準の中身自体が広すぎる）であると
判断し、無制限の細分化（Detector監査・User AI承認ラウンドの増加という別のコストを生む）
ではなく、task_plannerの既存の分割判定基準（指示3）へ「個数が3以内でも、1個の基準が独立
した複数シナリオ・複数対象を暗黙に束ねていないか」という判定軸を追加する、より的を絞った
軽量な対処とした（ユーザー承認）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-253。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_task_planner_prompt_mentions_bl253():
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-253" in src


def test_task_planner_prompt_instructs_checking_bundled_scenarios_within_one_criterion():
    """個数制約（3個以内）とは独立に、1個の基準が複数シナリオ・複数対象を暗黙に
    束ねていないかを確認せよという指示文言が含まれること。"""
    src = inspect.getsource(cela_main.call_task_planner)
    idx = src.index("BL-253")
    nearby = src[idx: idx + 400]
    assert "複数のシナリオ" in nearby or "複数対象" in nearby
    assert "暗黙" in nearby


def test_task_planner_prompt_applies_even_when_count_is_within_limit():
    """「個数が3以内でも」対象になる、という条件が明記されていること（BL-023の個数
    ルールだけでは防げなかった抜け道であることが伝わるように）。"""
    src = inspect.getsource(cela_main.call_task_planner)
    idx = src.index("BL-253")
    nearby = src[idx: idx + 400]
    assert "3以内" in nearby or "個数" in nearby
