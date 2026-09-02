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
    """call_detectorのソース内で、既存の【決定事項DB】を取得しプロンプトへ埋め込んで
    いること（従来はDetectorに一切見えていなかった配線漏れの修正）。
    [BL-317] 呼び出しは_build_agreements_context_for_state（内部で
    _build_agreements_context_from_dbを呼ぶ共有ヘルパー）へ統一されたため、
    直接の関数名参照ではなくagreements_textの配線自体を確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "_build_agreements_context_for_state" in src
    assert "agreements_text" in src


def test_bl062_call_detector_instructs_supersede_on_major():
    """call_detectorのソース内で、major判定時にwrite_agreementをSUPERSEDE/target_topeicで
    呼び出すよう指示する文言が存在すること（配線の存在確認）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "SUPERSEDE" in src
    assert "target_topic" in src


def test_bl086_freeze_tool_reactivated_in_user_ai_tools():
    """BL-086でD-045を乗り越え、FREEZE_AGREEMENT_TOOLをgenerate_user_utterance
    （実際にtools=[...]を保持する関数、generate_user_utterance_nodeはラッパーで
    tools=[...]を持たない）へ再び追加したことの回帰確認。BL-062自身の欠落
    （Detectorが🔒Freeze済み項目を尊重する指示を持たなかった問題）をcall_detectorの
    プロンプトに追加した上での意図的な再有効化（D-05x参照）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "FREEZE_AGREEMENT_TOOL" in src


def test_bl062_freeze_agreement_impl_still_intact():
    """FREEZE_AGREEMENT_TOOLの定義・freeze_agreement関数・TOOL_DISPATCH登録は
    削除されておらず温存されていること（一時休止であり削除ではない）。"""
    assert hasattr(cela_main, "FREEZE_AGREEMENT_TOOL")
    assert callable(cela_main.freeze_agreement)
    assert "freeze_agreement" in cela_main.TOOL_DISPATCH
