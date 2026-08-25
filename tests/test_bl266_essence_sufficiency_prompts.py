"""
BL-266 層1・層2: 「本質(true_essence)充足性」の網羅チェックを、計画立案
（call_task_planner）・計画レビュー（call_task_plan_reviewer）の各プロンプトへ追加した。

既存の本質乖離検知（BL-087 Stage4、call_detector）は「既に立てた計画・数値が本質から
ずれていないか」というドリフト検知に留まり、「本質が要求しているのに計画にそもそも
存在しない要素」を見つける網羅性・十分性チェックではなかった。この欠落は、ユーザーが
CELAとは独立した実験で観測した失敗パターン（計画立案時点で目標文の重要な手がかりを
見落とし、実行後半になってから気づく）に直結する。

設計の詳細経緯は docs/design/back_log/BL-266/BL266_investigation.md、実装計画は
同ディレクトリの実装計画（Plan Mode成果物）を参照。

本テストはプロンプト文言のソース検査のみで、実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _planner_src() -> str:
    return inspect.getsource(cela_main.call_task_planner)


def _reviewer_src() -> str:
    return inspect.getsource(cela_main.call_task_plan_reviewer)


# --- 層1: call_task_planner ---------------------------------------------------

def test_task_planner_prompt_has_essence_coverage_instruction16():
    """指示16として本質充足性の網羅チェックが追加されていること。"""
    src = _planner_src()
    assert "BL-266" in src
    assert "指示16の網羅性チェック" in src
    idx = src.index("[BL-266: 本質充足性の網羅チェック")
    nearby = src[idx: idx + 700]
    assert "本質" in nearby
    assert "網羅" in nearby


def test_task_planner_instruction16_is_distinguished_from_drift_detection():
    """[AGENTS.md §15.1] 網羅性チェック（新規）とドリフト検知（既存、call_detector側）が
    別の観点であることが、指示文の中で明示されていること。"""
    src = _planner_src()
    idx = src.index("[BL-266: 本質充足性の網羅チェック")
    nearby = src[idx: idx + 700]
    assert "ドリフト検知" in nearby or "call_detector" in nearby


def test_task_planner_reminder_appears_after_goal_essence_text():
    """{goal_essence_text}注入直後・Return ONLY JSON array直前に、指示16への短い参照が
    あること（規則の実体は指示16の1箇所にのみ書き、ここは参照のみに留める設計）。"""
    src = _planner_src()
    essence_idx = src.index("{goal_essence_text}")
    reminder_idx = src.index("[BL-266] 上記【🎯 本質】が提示されている場合、指示16の網羅性チェック")
    return_idx = src.index("Return ONLY JSON array")
    assert essence_idx < reminder_idx < return_idx


def test_task_planner_reminder_does_not_restate_the_rule():
    """参照部分自体は判定基準の実体（「対象となる主体」等の詳細）を重複記述していないこと
    （AGENTS.md §15.1: 単一の真実源。重複記述はドリフトの温床になる）。"""
    src = _planner_src()
    reminder_idx = src.index("[BL-266] 上記【🎯 本質】が提示されている場合、指示16の網羅性チェック")
    return_idx = src.index("Return ONLY JSON array")
    reminder_block = src[reminder_idx:return_idx]
    assert "対象となる主体" not in reminder_block


# --- 層2: call_task_plan_reviewer ----------------------------------------------

def test_task_plan_reviewer_lists_nine_criteria():
    """観点の総数が8→9へ更新され、導入文の個数表記が一貫していること。"""
    src = _reviewer_src()
    assert "9つとも" in src
    assert "8つとも" not in src
    assert "2・3・4・5・6・7・8・9" in src


def test_task_plan_reviewer_criterion9_mentions_bl266():
    """観点9として本質充足性チェックが追加され、既存の観点1〜8（曖昧さ・過不足等）とは
    別の観点であることが明示されていること。"""
    src = _reviewer_src()
    assert "9. [BL-266] 本質充足性" in src
    idx = src.index("9. [BL-266] 本質充足性")
    nearby = src[idx: idx + 500]
    assert "本質" in nearby
    assert "call_detector" in nearby


def test_task_plan_reviewer_major_enumeration_includes_essence_gap():
    """「重大な問題」の列挙にも、観点9に対応する「本質充足性の欠落」が含まれていること
    （観点だけ追加してmajor判定基準の説明が古いままという不整合を防ぐ回帰チェック、
    test_bl254と同型）。"""
    src = _reviewer_src()
    idx = src.index("重大な問題")
    nearby = src[idx: idx + 300]
    assert "本質充足性の欠落" in nearby


def test_task_plan_reviewer_json_schema_unchanged_for_essence_check():
    """[設計判断] 層2はJSON出力キーを新設しない（observations/comment/per_task_comments
    で表現する）。専用キーは層3（call_detector）のみに追加する非対称設計であることの
    回帰確認——誤って層2にもessence_sufficiency_concernキーが追加されていないこと。"""
    src = _reviewer_src()
    return_idx = src.index("Return ONLY JSON")
    schema_block = src[return_idx: return_idx + 600]
    assert "essence_sufficiency_concern" not in schema_block
