"""
BL-123: `_build_escalation_pin_text`（issue_logのescalated行を強制的にプロンプトへpinする、
BL-103）は`call_expert`と`generate_user_utterance`には注入されているが、`call_detector`には
一切注入されていなかった。Expert/User AIが既に把握しているはずの懸念を、それを監査する
Detectorだけが知らないまま独立に判定してしまう非対称性があった。

本テストはソース検査のみで以下を検証する（実LLM API呼び出しは伴わない）:
1. `_build_escalation_pin_text`が`call_detector`のソースに参照されていること。
2. 注入位置がPass 1（ドメイン妥当性レビュー、`domain_prompt`）内であり、Pass 2（数値監査、
   `prompt`）の開始位置より前であること（Pass 2は算術検算に専念する設計のため意図的に対象外）。

参照: docs/design/back_log/issue_backlog.md BL-123。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _numeric_prompt_start(src: str) -> int:
    """call_detectorのソース中、数値監査パス用promptの開始位置（軸1/軸2の定義文、
    domain_promptには存在しないためユニークなマーカー）を返す（test_bl104と同型）。
    """
    return src.index("以下の2軸は**完全に独立した別の評価軸**です")


def test_call_detector_references_build_escalation_pin_text():
    src = inspect.getsource(cela_main.call_detector)
    assert "_build_escalation_pin_text" in src


def test_escalation_pin_injected_only_into_domain_review_pass():
    src = inspect.getsource(cela_main.call_detector)
    numeric_start = _numeric_prompt_start(src)
    pin_idx = src.index("_build_escalation_pin_text")
    assert pin_idx < numeric_start, "escalation pinはPass 1（ドメイン妥当性レビュー）にのみ注入する設計"
    # Pass 2側（numeric_start以降）には別途の呼び出しが存在しないことを確認する。
    assert "_build_escalation_pin_text" not in src[numeric_start:]


def test_escalation_pin_block_conditionally_embedded_in_domain_prompt():
    """escalation_pinが空の場合はブロックごと省略され、非空の場合のみラベル付きで
    埋め込まれる（call_expert/generate_user_utteranceと同じ条件分岐パターン）ことを確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "escalation_pin_block" in src
    assert "エスカレーション中の懸念（要対応、issue_log）" in src
    assert 'if escalation_pin else ""' in src
