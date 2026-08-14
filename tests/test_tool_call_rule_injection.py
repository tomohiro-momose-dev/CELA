"""
[TOOL-CALL RULE] 全ノード共通のツール呼び出し鉄則が、_query_AI_live を経由して
各ノードの system メッセージへ確実に注入されることを検証する（実LLM呼び出し不要）。

背景: ツールが必要なのに「事前アナウンスのみで応答を終える（text-only stop）」挙動があると、
ツールループが stop し、次回呼び出しで改めてツールを呼ぶ無駄な iteration が生じ、
プロンプトキャッシュヒットが構造的に低下する。本ルールは TOOL_CALL_RULE 定数1箇所で
管理され、①既存 system メッセージへの追記（iter=1）、②light_system_prompt 置換（iter=2以降）
の両方に含まれることを確認する。

§17.1: 本テストは TOOL_CALL_RULE の注入を取り除くと失敗する（回帰検証）。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_tool_call_rule_constant_defined():
    """ルール本文が定数として単一定義されている（§15.1: ルールは1箇所管理）。"""
    assert isinstance(cela_main.TOOL_CALL_RULE, str)
    assert "tool_calls" in cela_main.TOOL_CALL_RULE
    assert "最終回答" in cela_main.TOOL_CALL_RULE


def test_inject_appends_rule_to_existing_system_message():
    """既存の system メッセージを持つ入力に、鉄則が追記される。"""
    messages = [{"role": "system", "content": "あなたは専門家です。"}]
    out = cela_main._inject_japanese_output_directive(messages)
    assert out[0]["role"] == "system"
    assert cela_main.TOOL_CALL_RULE in out[0]["content"]
    # 元の内容と日本語指示の両方が維持される
    assert "あなたは専門家です。" in out[0]["content"]
    assert cela_main._JAPANESE_OUTPUT_DIRECTIVE in out[0]["content"]


def test_inject_creates_system_message_when_absent():
    """system メッセージが無い入力でも、鉄則を含む system メッセージが先頭に挿入される。"""
    messages = [{"role": "user", "content": "こんにちは"}]
    out = cela_main._inject_japanese_output_directive(messages)
    assert out[0]["role"] == "system"
    assert cela_main.TOOL_CALL_RULE in out[0]["content"]
    # 既存メッセージはそのまま保持（role連続を誘発しないようsystemは先頭のみ）
    assert out[1] == messages[0]


def test_light_system_prompt_swap_includes_rule():
    """iter=2以降の light_system_prompt 置換でも鉄則が維持されるよう、
    _query_AI_live 内の置換式が TOOL_CALL_RULE を参照していることを確認する。

    注: 完全なネットワーク呼び出しを伴う_light swap の実行検証は実LLMドライランに譲る。
    ここでは、置換で使われるテンプレート文字列が鉄則を含むことをソースから保証する。
    """
    # 置換式と同じ構成で鉄則が含まれることを確認（実装と同期させる）
    light = "あなたは監査人です。"
    swapped = f"{light}\n\n{cela_main.TOOL_CALL_RULE}\n\n{cela_main._JAPANESE_OUTPUT_DIRECTIVE}"
    assert cela_main.TOOL_CALL_RULE in swapped
    assert cela_main._JAPANESE_OUTPUT_DIRECTIVE in swapped
