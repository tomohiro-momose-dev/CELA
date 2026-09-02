"""
BL-257: `calc_road_route`はOpenRouteServiceの`profile="driving-car"`（乗用車の自由走行時間）
を返すが、これがバス等の公共交通の公式時刻表上の所要時間と別物であることがどこにも
明記されていなかった。

実ドライラン（`log/2026-08-17/0757`、run_id=1786921069-6bb4a6a5）のtask_2_1で、Expertが
横谷峡のGIS実測値（calc_road_route: 12.22分）を「確認済みの通常期接続単位」として扱い、
公式バス案内（茅野駅からメルヘン街道バスで約35分）と混同・整合させないまま成果物へ含め、
Detectorから3回連続でmajor判定（差し戻し）を受けた。同じrun内で他のタスク（task_1_1〜
task_1_3）がいずれも初回提出で一発承認だったのに対し、task_2_1だけ17バージョンまで
かかった一因となった。

ユーザーとの対話でこの数値差（12.22分 vs 約35分）の性質を検討し、信号待ちのような
副次的な要因ではなく、そもそも「乗用車の自由走行時間」と「バスの停留所停車・巡航速度・
ダイヤ遵守を含む運行時間」という**別の計測対象**であることを特定。この区別を、実際に
数値を出すExpert側（call_expert、通常/軽量プロンプトの両方）と、それを検算するDetector側
（数値監査パス・ドメインレビューパスの両方）の両方に明記した——Expertが混同しないための
生成時ガードと、Detectorが「車の走行時間とバスの時刻表が一致しない」ことを誤って
「実測値との食い違い」としてmajor判定しないための監査時ガードの両方が必要なため。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-257。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_tool_schema_documents_car_vs_transit_distinction():
    """CALC_ROAD_ROUTE_TOOLのdescriptionに、乗用車の自由走行時間であり公共交通の
    運行時間とは別物である旨が明記されていること。"""
    desc = cela_main.CALC_ROAD_ROUTE_TOOL["function"]["description"]
    assert "BL-257" in desc
    assert "driving-car" in desc
    assert "bus" in desc.lower() or "transit" in desc.lower()


def test_call_expert_full_prompt_mentions_car_vs_transit_distinction():
    """call_expertの通常プロンプトに、車の自由走行時間とバスの公式所要時間を
    混同しないよう明記されていること。"""
    src = inspect.getsource(cela_main.call_expert)
    assert src.count("BL-257") >= 2  # フル版・軽量版の両方
    idx = src.index("BL-257")
    nearby = src[idx: idx + 300]
    assert "乗用車" in nearby
    assert "バス" in nearby


def test_call_expert_instructs_keeping_both_values_separate():
    """混同した場合に上書きするのではなく、出典を分けて別値として保持するよう
    指示されていること。"""
    src = inspect.getsource(cela_main.call_expert)
    idx = src.index("BL-257")
    nearby = src[idx: idx + 400]
    assert "別" in nearby


def test_call_detector_numeric_audit_pass_avoids_false_positive():
    """call_detectorの数値監査パスが、車とバスの所要時間が一致しないこと自体を
    「実測値との食い違い」として誤ってmajorにしないよう明記していること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-257") >= 2  # ドメインレビューパス・数値監査パスの両方
    idx = src.index("BL-257")
    nearby = src[idx: idx + 400]
    assert "混同" in nearby or "別物" in nearby


def test_call_detector_still_flags_actual_confusion():
    """一致しないこと自体は問題視しないが、AgentがGIS値とバス所要時間を実際に
    混同・上書きしている場合は引き続き指摘対象とする旨が残っていること
    （BL-257が数値監査そのものを無効化していないことの確認）。"""
    src = inspect.getsource(cela_main.call_detector)
    idx = src.index("BL-257")
    nearby = src[idx: idx + 500]
    assert "混同" in nearby
