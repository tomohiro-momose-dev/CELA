"""
BL-195: ゴール文の実データ化（長野県茅野市）に伴い、web_searchで実在precedent（例：茅野市の
AIオンデマンド交通「のらざあ」）を発見した際に、その具体的運用数値（運行本数・車両台数・
運賃・人員体制等）を検証・独自導出なしにそのまま成果物へ転記してしまうリスクへの対処。

`TARGET_GOAL`（cela_main.py）は従来「八ヶ嶺市（仮名）」という匿名化都市名を使っていたが、
駅標高・JR中央本線・人口規模等の地理的特徴から実際には特定可能であり、匿名化は答えの隠蔽に
失敗する一方、`task_1_1`の成果物が「架空都市のため実測値ではない」という長い留保に分量を
割く無駄なコストだけを生んでいた（log/2026-08-09/1100）。そこで地名を「茅野市」と明記し、
実データをゴール文へ直接埋め込む方針へ転換した。ただし、実在の解決策そのもの（2022年10月の
路線バス13路線廃止→「のらざあ」への移行）はゴール文の背景説明には含めていない（「問題」と
「解決」を分離し、「解決」側は答えそのものになるため書かない）。

残るリスクは、エージェントがrun中にweb_searchで「のらざあ」等の実例を自力発見し、その
具体的運用数値を検証なく転記することのみである。これに対し、BL-042/BL-188/BL-194が確立した
標準方針（プロンプト誘導のみ、機械的な強制ゲートは追加しない）を踏襲し、call_expert
（system_prompt・light_system_promptの両経路）とcall_detector（Pass1ドメイン妥当性・
Pass2数値監査の両パス）へ、実例数値の無derivation転記を禁止する文言を追加した。

参照: docs/design/back_log/issue_backlog.md BL-195、BL-188、BL-192、BL-194。
実LLM API呼び出しは伴わない（ソースコードの配線確認のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_expert_system_prompt_contains_bl195_guardrail():
    src = inspect.getsource(cela_main.call_expert)
    assert src.count("BL-195") >= 2, (
        "call_expertのsystem_prompt・light_system_promptの両方にBL-195ガードレールが"
        "必要（片方のみだと使用される経路によってはガードレールが素通りする）"
    )


def test_call_expert_guardrail_forbids_uncritical_transcription():
    src = inspect.getsource(cela_main.call_expert)
    assert "そのまま成果物へ転記" in src
    assert "独自に導出" in src


def test_call_expert_guardrail_requires_derivation_in_reason_why():
    src = inspect.getsource(cela_main.call_expert)
    assert "reason_whyに" in src and "導出したか" in src


def test_call_detector_contains_bl195_guardrail_in_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-195") >= 2, (
        "call_detectorのPass1（ドメイン妥当性）・Pass2（数値監査）の両方にBL-195の"
        "無derivation転記チェックが必要"
    )


def test_call_detector_guardrail_mentions_no_derivation_flagging():
    src = inspect.getsource(cela_main.call_detector)
    assert "無derivation転記" in src
    assert "minor以上の指摘対象" in src


def test_call_detector_pass2_distinguishes_copy_check_from_independent_derivation():
    src = inspect.getsource(cela_main.call_detector)
    assert "実例の数値を式に代入して" in src
    assert "独立にその数値を導出しているか" in src


def test_target_goal_names_real_city_and_separates_problem_from_solution():
    """[BL-195] TARGET_GOALはcli実行部にのみ存在しモジュールレベルの変数ではないため、
    ソースファイル全体をテキストとして走査し、意図通りの切り分けができているか確認する。"""
    with open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cela_main.py"),
        encoding="utf-8",
    ) as f:
        source_text = f.read()

    assert "長野県茅野市" in source_text
    assert "八ヶ嶺市" not in source_text, "匿名化都市名は実データ化により完全に置き換えられているはず"
    # 「問題」側（路線バス廃止の事実）は背景として使ってよい。
    # 語順（「利用者減少・採算悪化を理由に」が前文に置かれ、日付挿入がある）のため、意図を
    # 保つ2つの必須断片で確認する（BL-224 とは無関係な事前のテスト文字列ドリフトを解消）。
    assert "定時定路線バス13路線が廃止された" in source_text, (
        "TARGET_GOALは「問題」側の事実（定時定路線バス13路線の廃止）を背景として含めること"
    )
    assert "利用者減少・採算悪化を理由に" in source_text, (
        "廃止の理由（利用者減少・採算悪化）も背景として含めること"
    )
    # 「解決」側（のらざあへの移行）はゴール文の背景説明に含めてはならない
    assert "のらざあ" not in source_text
    assert "AIオンデマンド交通" not in source_text or "オンデマンド交通「のらざあ」" not in source_text


def test_target_goal_includes_precedent_reference_section():
    with open(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cela_main.py"),
        encoding="utf-8",
    ) as f:
        source_text = f.read()
    assert "実例の参照について" in source_text
    assert "実例の運行本数・車両台数・運賃・人員体制等の具体的な運用数値をそのまま本計画の数値として転記してはならない" in source_text
