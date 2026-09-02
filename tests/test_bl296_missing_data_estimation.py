"""
BL-296: 公表されていない値の推計に「1つの妥当な方法で確定させる」満足化規定を導入。

`log/2026-08-28/1535`で、Expert（task_1_1、免許返納累計件数）が「茅野市単位の累計は公式
統計に存在しない」状況に直面し、iter=6の単一生成ターン内で9分半・15回以上、「長野県の
構成比から按分推計する→仮定が重すぎるので却下→もっと誠実な方法があるはずと言い直す→
振り出しに戻る」という同一サイクルを繰り返し、ツール呼び出しも出力確定も行わないまま
停止した（ユーザーがCtrl+Cで手動一時停止）。

これはBL-293（役割の板挟み）・BL-294（マンデート値と検証結果の衝突）・BL-295（二択・三択の
裁量判断に打ち切り規定が無い）のいずれとも異なる4つ目のパターンで、「推計の精緻化に終わりが
無い（完璧主義ループ）」というもの。BL-295の3回多数決方式はカテゴリカルな結論の選択には
合うが、連続的に手法を洗練させ続けるこのケースには合わないため、新たに実務標準の推計手法
一覧＋満足化規定を導入した。ユーザー指摘により、Expert（producer視点）だけでなく
User AI・Detector（auditor視点：文書化された妥当な推計を理由なく差し戻さない）にも横展開した。

参照: docs/design/back_log/BL-296/BL296_basic_design.md、BL-295、BL-041。
実LLM API呼び出しは伴わない（ソース検査のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 1. _missing_data_estimation_instruction 単体
# ---------------------------------------------------------------------------

def test_lists_all_five_estimation_methods_both_perspectives():
    methods = ["代理指標の比例配分", "類似事例の転用", "フェルミ推定的分解", "レンジ（感度分析）", "前提の明示的記録"]
    for perspective in ("producer", "auditor"):
        text = cela_main._missing_data_estimation_instruction(perspective=perspective)
        for m in methods:
            assert m in text, f"{perspective}側に手法「{m}」が含まれていない"


def test_producer_perspective_tells_model_to_commit():
    text = cela_main._missing_data_estimation_instruction(perspective="producer")
    assert "確定させて" in text
    assert "再導出し続けないでください" in text


def test_auditor_perspective_tells_model_not_to_reject():
    text = cela_main._missing_data_estimation_instruction(perspective="auditor")
    assert "差し戻したり" in text
    assert "confidence=\"provisional\"" in text


def test_producer_and_auditor_wording_differs():
    """perspectiveで結び文が実際に切り替わっていること（producer固有・auditor固有の
    文言が互いに混入していないこと）。"""
    producer_text = cela_main._missing_data_estimation_instruction(perspective="producer")
    auditor_text = cela_main._missing_data_estimation_instruction(perspective="auditor")
    assert "再導出し続けないでください" in producer_text
    assert "再導出し続けないでください" not in auditor_text
    assert "差し戻したり" in auditor_text
    assert "差し戻したり" not in producer_text


def test_default_perspective_is_producer():
    default_text = cela_main._missing_data_estimation_instruction()
    producer_text = cela_main._missing_data_estimation_instruction(perspective="producer")
    assert default_text == producer_text


# ---------------------------------------------------------------------------
# 2. call_expert: producer視点で適用されていること
# ---------------------------------------------------------------------------

def test_call_expert_uses_producer_perspective():
    src = inspect.getsource(cela_main.call_expert)
    assert "_missing_data_estimation_instruction(perspective=\"producer\")" in src


def test_call_expert_instruction_is_near_bl041_block():
    """BL-041（確定値と暫定値の区別）ブロック内に挿入されていること（挿入位置の確認）。"""
    src = inspect.getsource(cela_main.call_expert)
    idx = src.index("確定値と暫定値の区別")
    nearby = src[idx: idx + 1200]
    assert "_missing_data_estimation_instruction(" in nearby


# ---------------------------------------------------------------------------
# 3. _USER_AI_ROLE_MANDATE: auditor視点で適用されていること（定数の中身を直接確認）
# ---------------------------------------------------------------------------

def test_user_ai_role_mandate_contains_auditor_instruction():
    """_USER_AI_ROLE_MANDATEは文字列定数のためgenerate_user_utteranceのソースには
    値そのものが現れない。定数の中身を直接検査する。"""
    assert "公表されていない値の推計方法" in cela_main._USER_AI_ROLE_MANDATE
    assert "差し戻したり" in cela_main._USER_AI_ROLE_MANDATE


def test_generate_user_utterance_still_references_role_mandate():
    """回帰確認: generate_user_utteranceが引き続き_USER_AI_ROLE_MANDATEを参照していること
    （BL-296の追加が定数への参照自体を壊していないこと）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_USER_AI_ROLE_MANDATE" in src


# ---------------------------------------------------------------------------
# 4. call_detector: auditor視点で適用されていること
# ---------------------------------------------------------------------------

def test_call_detector_uses_auditor_perspective():
    src = inspect.getsource(cela_main.call_detector)
    assert "_missing_data_estimation_instruction(perspective='auditor')" in src


def test_call_detector_instruction_is_near_bl188_grounding_check():
    """BL-188（根拠の実在性チェック）の直後に挿入されていること（挿入位置の確認）。"""
    src = inspect.getsource(cela_main.call_detector)
    idx = src.index("根拠の実在性チェック")
    nearby = src[idx: idx + 1500]
    assert "_missing_data_estimation_instruction(" in nearby


# ---------------------------------------------------------------------------
# 5. 既存機構との非衝突（回帰）
# ---------------------------------------------------------------------------

def test_bounded_deliberation_instruction_still_present_in_detector():
    """BL-295の3回多数決方式ヘルパーが引き続きcall_detectorに存在すること
    （BL-296の追加がBL-295を壊していないこと）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_bounded_deliberation_instruction(" in src
