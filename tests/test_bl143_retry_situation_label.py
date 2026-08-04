"""
BL-143: Detectorのmajor差し戻しプロンプトには、従来Detectorの指摘文（constraint_issue_logの
直近1件）だけが載っており、「これが何回目の差し戻しか」「前回と同じ指摘が繰り返されているのか」
はPython側で計算可能な情報（user_retry_count/expert_retry_count、constraint_issue_logの
直近2件の類似度）なのにプロンプトへは渡っていなかった。BL-142で見た「Userが同じ承認を言い回しを
変えて繰り返す」空回りは、この現在地情報の欠如が一因と考え、_build_retry_situation_labelで
機械的な現在地サマリーを生成し、call_expert/generate_user_utteranceの差し戻しプロンプト冒頭へ
追加した。

参照: docs/design/back_log/issue_backlog.md BL-143。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _state_with_log(log, extra=None):
    state = {"constraint_issue_log": log}
    if extra:
        state.update(extra)
    return state


def test_retry_label_shows_count_and_remaining_budget():
    log = [{"turn": 1, "severity": "major", "comment": "予備車がゼロで冗長性に欠ける。"}]
    label = cela_main._build_retry_situation_label(_state_with_log(log), retry_count=1)
    assert "1回目の差し戻し" in label
    assert "あと2回" in label


def test_retry_label_at_limit_shows_zero_remaining():
    log = [{"turn": 3, "severity": "major", "comment": "同じ懸念です。"}]
    label = cela_main._build_retry_situation_label(_state_with_log(log), retry_count=3)
    assert "3回目の差し戻し" in label
    assert "あと0回" in label


def test_retry_label_skips_repeat_check_on_first_retry():
    """retry_count==1では連鎖内に比較対象がまだ無いため、直前の（無関係な過去の）
    major判定と誤って比較しない。"""
    log = [
        {"turn": 1, "severity": "major", "comment": "全く別のタスクの全く別の懸念事項です。"},
        {"turn": 5, "severity": "major", "comment": "全く別のタスクの全く別の懸念事項です。"},
    ]
    label = cela_main._build_retry_situation_label(_state_with_log(log), retry_count=1)
    assert "繰り返されています" not in label


def test_retry_label_flags_repeated_same_comment():
    """retry_count>=2で、直近2件のcommentがほぼ同一なら「繰り返し」警告を出す。"""
    comment = "遠隔監視オペレーターの兼務問題が未解消です。監視漏れ・応答遅延のリスクがあります。"
    log = [
        {"turn": 3, "severity": "major", "comment": comment},
        {"turn": 4, "severity": "major", "comment": comment},
    ]
    label = cela_main._build_retry_situation_label(_state_with_log(log), retry_count=2)
    assert "繰り返されています" in label


def test_retry_label_does_not_flag_genuinely_different_comments():
    log = [
        {"turn": 3, "severity": "major", "comment": "予備車がゼロで冗長性に欠ける。"},
        {"turn": 4, "severity": "major", "comment": "通信死活区でのレベル4継続手順が未定義。"},
    ]
    label = cela_main._build_retry_situation_label(_state_with_log(log), retry_count=2)
    assert "繰り返されています" not in label


def test_retry_label_handles_empty_log():
    label = cela_main._build_retry_situation_label(_state_with_log([]), retry_count=1)
    assert "1回目の差し戻し" in label


def test_call_expert_wires_retry_situation_label():
    src = inspect.getsource(cela_main.call_expert)
    assert "_build_retry_situation_label" in src
    assert "expert_retry_count" in src


def test_generate_user_utterance_wires_retry_situation_label():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "_build_retry_situation_label" in src
    assert "user_retry_count" in src
