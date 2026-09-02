"""
BL-295: 裁量判断（結論が割れうる二択・三択の判定）の「打ち切り規定」を汎用ヘルパー化する。

`log/2026-08-28/1313`で、Detector（Domain Review, Pass 1）が`constraint_issue=none`の判定
自体は正しく完了させた直後、「observationsに書いた気づきをwrite_issueで後続タスクへ永続化
すべきか」という別の裁量判断に入り、41秒間・単一の生成ターン内で同一の二択を30回以上往復し、
ツール呼び出しも出力確定も行わないまま停止した（ユーザーがCtrl+Cで手動一時停止）。

call_detectorのPass 2（数値監査パス）には既に「判定のブレ防止（3回多数決方式）」という
実証済みの打ち切り機構があったが、constraint_issueのmajor/minor境界判定にしかスコープされて
おらず、Pass 1のwrite_issue永続化判断はカバーしていなかった。この機構を`_bounded_deliberation_
instruction`として汎用ヘルパー化し、Pass 1（write_issue永続化判断）・generate_user_utterance
（write_issueのRESOLVE/DEFER/ACKNOWLEDGE選択、2箇所）へ横展開した。あわせて、Pass 2直後の
`_verification_throttle_warning`とほぼ手書き重複していたブロック（§15.1違反）も共有ヘルパー
呼び出しへ置換した。

Explore調査で見つかったもう1つの非対称（BL-292 `quantitative_sufficiency_concern`に、姉妹
フィールドBL-266 `essence_sufficiency_concern`が持つ「判断に迷う場合はfalseのまま」という
既定値の逃げ道が欠けていた）も併せて解消した。

参照: docs/design/back_log/BL-295/BL295_basic_design.md、BL-096、BL-266、BL-292。
実LLM API呼び出しは伴わない（ソース検査のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 1. _bounded_deliberation_instruction 単体
# ---------------------------------------------------------------------------

def test_bounded_deliberation_instruction_embeds_judgment_description():
    text = cela_main._bounded_deliberation_instruction("観察をwrite_issueで永続化すべきかの判断")
    assert "観察をwrite_issueで永続化すべきかの判断" in text


def test_bounded_deliberation_instruction_contains_majority_vote_core_phrases():
    text = cela_main._bounded_deliberation_instruction("何らかの判断")
    assert "3回多数決方式" in text
    assert "trial1" in text
    assert "多数だった結論" in text
    assert "無限に再検討し続けないでください" in text


def test_bounded_deliberation_instruction_different_calls_are_independent():
    """judgment_descriptionが異なれば埋め込まれる文言も変わる（パラメータ化の確認）。"""
    text_a = cela_main._bounded_deliberation_instruction("判断A")
    text_b = cela_main._bounded_deliberation_instruction("判断B")
    assert "判断A" in text_a and "判断A" not in text_b
    assert "判断B" in text_b and "判断B" not in text_a


# ---------------------------------------------------------------------------
# 2. call_detector Pass 2: 既存ブロックがヘルパー呼び出しへ置換されていること
# ---------------------------------------------------------------------------

def test_detector_pass2_uses_bounded_deliberation_helper():
    src = inspect.getsource(cela_main.call_detector)
    assert "_bounded_deliberation_instruction(" in src
    assert "constraint_issueの判定（特にminorとmajorの境界）" in src


def test_detector_pass2_no_longer_hand_duplicates_verification_throttle_text():
    """§15.1: Pass2の「同じ計算を繰り返さない」手書きブロックは共有ヘルパー
    _verification_throttle_warning呼び出しに置換され、手書き重複が解消されていること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_verification_throttle_warning(" in src
    idx = src.index("_verification_throttle_warning(")
    assert "example=" in src[idx: idx + 60]


def test_detector_pass2_majority_vote_wording_preserved():
    """既存挙動の非退行: 3回多数決方式の核心文言（trial表記・多数決）は_bounded_deliberation_
    instructionヘルパー本体に存在し、call_detectorはそれを呼び出す形で引き続き利用すること
    （文言自体はヘルパーへ切り出されたため、call_detector側は呼び出し式で確認する）。"""
    helper_src = inspect.getsource(cela_main._bounded_deliberation_instruction)
    assert "trial1" in helper_src
    assert "3回多数決方式" in helper_src
    detector_src = inspect.getsource(cela_main.call_detector)
    assert "_bounded_deliberation_instruction(" in detector_src


# ---------------------------------------------------------------------------
# 3. call_detector Pass 1（domain_prompt）: BL-096のwrite_issue永続化判断への適用
# ---------------------------------------------------------------------------

def test_detector_domain_prompt_has_write_issue_persistence_closure():
    src = inspect.getsource(cela_main.call_detector)
    assert "observationsに書いた懸念をwrite_issueで永続化すべきかの判断" in src


def test_detector_domain_prompt_closure_is_near_issue_carryover_prefix():
    """_issue_carryover_prefix（BL-096の永続化指示）の直後に打ち切り規定が来ること
    （挿入位置の確認、離れた無関係な箇所に付いていないことの回帰防止）。"""
    src = inspect.getsource(cela_main.call_detector)
    idx = src.index("_issue_carryover_prefix}")
    nearby = src[idx: idx + 300]
    assert "_bounded_deliberation_instruction(" in nearby


# ---------------------------------------------------------------------------
# 4. generate_user_utterance: write_issueのRESOLVE/DEFER/ACKNOWLEDGE選択への適用
# ---------------------------------------------------------------------------

def test_generate_user_utterance_has_resolve_defer_acknowledge_closure():
    src = inspect.getsource(cela_main.generate_user_utterance)
    count = src.count("write_issueでRESOLVE/DEFER/ACKNOWLEDGEのいずれを選ぶべきかの判断")
    assert count >= 2, (
        "Stage2の懸念確認プロンプトとStage4の指示作成プロンプトの両方に"
        f"打ち切り規定が追加されているはずだが、{count}箇所しか見つからなかった"
    )


def test_generate_user_utterance_closure_follows_resolve_explanation():
    """RESOLVE手順の説明直後に打ち切り規定が来ること（挿入位置の確認）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    marker = "issueをクローズする役目はあなたです"
    start = 0
    found_count = 0
    while True:
        idx = src.find(marker, start)
        if idx == -1:
            break
        nearby = src[idx: idx + 200]
        assert "_bounded_deliberation_instruction(" in nearby or "write_issueでRESOLVE/DEFER/ACKNOWLEDGE" in nearby
        found_count += 1
        start = idx + len(marker)
    assert found_count >= 2


# ---------------------------------------------------------------------------
# 5. BL-292 quantitative_sufficiency_concernの非対称解消
# ---------------------------------------------------------------------------

def test_quantitative_sufficiency_concern_has_default_to_false_escape():
    src = inspect.getsource(cela_main.call_detector)
    idx = src.index("'quantitative_sufficiency_concern'をtrueにしてください")
    nearby = src[idx: idx + 120]
    assert "判断に迷う" in nearby
    assert "falseのままにしてください" in nearby


def test_essence_and_quantitative_concern_now_symmetric():
    """姉妹フィールド同士で「判断に迷う場合の既定値」の記述パターンが揃っていること。"""
    src = inspect.getsource(cela_main.call_detector)
    essence_idx = src.index("'essence_sufficiency_concern'をtrueにしてください")
    quant_idx = src.index("'quantitative_sufficiency_concern'をtrueにしてください")
    essence_nearby = src[essence_idx: essence_idx + 250]
    quant_nearby = src[quant_idx: quant_idx + 250]
    assert "判断に迷う" in essence_nearby
    assert "判断に迷う" in quant_nearby


# ---------------------------------------------------------------------------
# 6. 既存の反復抑制テスト（BL-089）との整合
# ---------------------------------------------------------------------------

def test_detector_still_has_anti_repetition_instruction_marker():
    """BL-089回帰: call_detectorが依然としてanti-repetition指示（共有ヘルパー経由）を
    持っていること。test_bl089_anti_repetition_instructions.py側でも同様に確認される。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_verification_throttle_warning(" in src
