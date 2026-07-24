"""
BL-062: Detectorのmajor判定が既存Approved agreementを構造的に無効化できない問題への対応
（Detector限定でのSUPERSEDE指示配線）と、それに伴うF-8.3 Freezeの一時休止（D-045）の
オフライン検証項目。実LLM API呼び出しは伴わない。

参照: docs/design/issue_backlog.md BL-062、docs/design/decision_log.md D-045。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl062_call_detector_receives_agreements_context():
    """call_detectorのソース内で、既存の【決定事項DB】（_build_agreements_context_from_db）
    を取得しプロンプトへ埋め込んでいること（従来はDetectorに一切見えていなかった配線漏れの修正）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_build_agreements_context_from_db" in src
    assert "agreements_text" in src


def test_bl062_call_detector_instructs_supersede_on_major():
    """call_detectorのソース内で、major判定時にwrite_agreementをSUPERSEDE/target_topeicで
    呼び出すよう指示する文言が存在すること（配線の存在確認）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "SUPERSEDE" in src
    assert "target_topic" in src


def test_bl062_freeze_tool_removed_from_user_ai_tools():
    """D-045: FREEZE_AGREEMENT_TOOLはgenerate_user_utterance_nodeのtoolsリストから
    外され、呼び出し不能になっていること（本体・is_frozenガード・表示ロジックは温存のまま）。"""
    src = inspect.getsource(cela_main.generate_user_utterance_node)
    assert "FREEZE_AGREEMENT_TOOL" not in src


def test_bl062_freeze_agreement_impl_still_intact():
    """FREEZE_AGREEMENT_TOOLの定義・freeze_agreement関数・TOOL_DISPATCH登録は
    削除されておらず温存されていること（一時休止であり削除ではない）。"""
    assert hasattr(cela_main, "FREEZE_AGREEMENT_TOOL")
    assert callable(cela_main.freeze_agreement)
    assert "freeze_agreement" in cela_main.TOOL_DISPATCH
