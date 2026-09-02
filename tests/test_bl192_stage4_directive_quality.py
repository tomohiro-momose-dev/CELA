"""
BL-192: User AI Stage4の指示文を強化し、根拠不明な数値のweb_search義務化・期待される
思考プロセスの明示を徹底する。

BL-191設計中にユーザーから追加要望：「ユーザーAIプロンプトにも...次タスクで根拠があいまいな
数値や前提・条件があるからまずはweb検索を用いて情報をしらべて、『もっともらしさ』を排除しろ
とか、次のタスクのこれをやれ、だけではなくて、網羅的にエキスパートAIにどういう思考で、どう
行動してほしいかをユーザーAIが指示する部分も強化したい」。BL-188の「プロンプト誘導のみ」
方針を踏襲し、新規state/ツール/DBスキーマなしでStage4のシステムプロンプトへ指示ブロックを
追加するのみで完結させた。

独立レビューにより、User AIには差し戻しターン等でStage3/Stage4をスキップする非Stage4パス
（generate_user_utterance内、essence_dialogue/Expert相談応答/差し戻し/終盤/初回ターン用）が
存在することが判明したため、共通定数`_BL192_DIRECTIVE_QUALITY_BLOCK`を両パスへ注入する設計へ
修正した。

参照: docs/design/back_log/issue_backlog.md BL-192、
      docs/design/back_log/BL-191/BL191_basic_design.md（BL-192セクション）。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_directive_quality_block_mentions_web_search_obligation():
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "web_search" in text
    assert "type=\"web\"" in text
    assert "もっともらしい" in text


def test_directive_quality_block_mentions_thinking_process():
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "acceptance_criteria" in text
    assert "思考プロセス" in text
    assert "task_focus_companion" in text  # BL-191との連携（依存タスクとの整合性確認）


def test_generate_user_utterance_source_references_directive_block():
    """Stage4（承認済み分岐）のプロンプト構築箇所で共通定数が参照されていること
    （ソース確認、BL-094/BL-177等の既存テストと同じinspect.getsourceパターン）。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    assert "_BL192_DIRECTIVE_QUALITY_BLOCK" in source


def test_directive_block_referenced_at_both_stage4_and_non_stage4_paths():
    """【独立レビュー指摘7-2の回帰防止】Stage4パス・非Stage4パス（差し戻し・本質対話・
    Expert相談応答・終盤・初回ターン用、いずれもgenerate_user_utterance内の別分岐）の
    両方が同一のモジュール定数_BL192_DIRECTIVE_QUALITY_BLOCKをそのまま参照しており、
    文言の二重管理になっていないこと（2箇所以上で参照されていることを確認）。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    assert source.count("_BL192_DIRECTIVE_QUALITY_BLOCK") >= 2
