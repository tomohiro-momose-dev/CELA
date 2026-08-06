"""
BL-170: Facilitatorのescalated_issues_block（Detector等が指摘した具体的な数値issueの
生テキストをそのまま提示する箇所）に、役割境界を明示するガードレール文が無かった問題の
オフライン検証項目。

参照: log/2026-08-04/1435/log_no_prompt.md:784-995（Facilitatorがオペレーター人員体制の
労基法違反issueを読み、自分の職掌（短い誘導メッセージを1つ書くこと）を逸脱してExpertの
仕事（財務モデル全体の再計算・Deliverable再提出）を自分でやるべきだと誤認し、付与されて
いないpython_replを呼ぶ計画をthinkで29回連続宣言し続けるだけの空回りに陥り、
MAX_TOOL_ITER（30）予算を丸ごと空費して無出力に終わった実例）、
docs/design/back_log/issue_backlog.md BL-170。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl170_guardrail_appears_alongside_escalated_issues(monkeypatch):
    """escalated_issues_textが渡された場合、issue本文だけでなく、『これは誘導メッセージの
    材料であり、自分で解決する課題ではない』旨のBL-170ガードレール文もプロンプトへ
    含まれること。"""
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["messages"] = messages
        return "ダミーのファシリテーター応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    issue_text = "オペレーター4名体制での労基法違反：年2,040時間で法定上限2,000時間を超過する。"
    cela_main.call_facilitator("テストゴール", [{"role": "user", "content": "こんにちは"}], escalated_issues_text=issue_text)

    prompt_text = captured["messages"][0]["content"]
    assert issue_text in prompt_text, "escalated issueの本文がプロンプトに含まれていない（BL-096の既存挙動が退行）"
    assert "[BL-170]" in prompt_text, "BL-170ガードレール文がプロンプトに含まれていない"
    assert "python_repl" in prompt_text, "python_replツールが与えられていない旨の明示が欠落している"
    assert "自分で解決" in prompt_text or "自分でやる" in prompt_text or "あなたの役目ではありません" in prompt_text, (
        "『自分で解決する課題ではない』という役割境界の明示が欠落している"
    )


def test_bl170_no_block_and_no_guardrail_when_no_escalated_issues(monkeypatch):
    """escalated_issues_textが空（従来通りの周期的facilitator呼び出し）の場合は、
    issueブロックごとBL-170ガードレール文も出現しないこと（元の条件分岐を維持）。"""
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["messages"] = messages
        return "ダミーのファシリテーター応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    cela_main.call_facilitator("テストゴール", [{"role": "user", "content": "こんにちは"}], escalated_issues_text="")

    prompt_text = captured["messages"][0]["content"]
    assert "🚨" not in prompt_text
    assert "[BL-170]" not in prompt_text


def test_bl170_essence_dialogue_mode_never_includes_escalated_issues_block(monkeypatch):
    """essence_dialogue_active=Trueの継続対話モードでは、escalated_issues_textを渡しても
    (元々の設計通り)issueブロック自体が使われないこと（BL-170ガードレール文もFacilitator
    自身のツール一覧に応じた別文面のため、ここでは不要）。"""
    captured = {}

    def fake_query_AI(messages, client, model, label="Unknown Node", tools=None, light_system_prompt=None, state=None):
        captured["messages"] = messages
        return "ダミーのファシリテーター応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_AI)

    issue_text = "オペレーター4名体制での労基法違反"
    cela_main.call_facilitator(
        "テストゴール", [{"role": "user", "content": "こんにちは"}],
        escalated_issues_text=issue_text, essence_dialogue_active=True,
    )

    prompt_text = captured["messages"][0]["content"]
    assert issue_text not in prompt_text
    assert "[BL-170]" not in prompt_text
