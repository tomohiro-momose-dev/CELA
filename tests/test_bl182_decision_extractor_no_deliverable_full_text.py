"""
BL-182: `call_decision_extractor`のExpert向けプロンプトが、write_agreement経由で既に登録済み
（かつwrote_agreement_this_turn=Trueの場合はまるごと破棄される）Deliverable本文の「全文複製」を
要求していたため、大きな成果物（例: task_5_1のフェールセーフプロトコル・マニュアル）では
生成が長くなりすぎてJSON出力がmax_tokens付近で打ち切られ、`_query_and_parse_with_retry`の
3回のリトライすべてが失敗し、そのターンの抽出（Decision/Directive/Deliverable）が全損する
事故が発生した（`log/2026-08-05/2311/log_no_prompt.md:5568-5665`）。

ユーザー指摘: この機能は元々decision_extractorがDBへ直接登録していた時代の名残であり、
write_agreement/write_issueが今は本流の登録経路である。write_agreementが呼ばれたターンは
decision_extractor_nodeの当該抽出結果自体が丸ごと破棄され（`wrote_agreement_this_turn=True`
分岐）、呼ばれなかった場合の保険（fallback）でも`content`が短ければ`state["expert_output"]`
（Agentの発言全文）が自動的に使われる（`cela_main.py:9013-9023`）ため、decision_extractor
自身がcontentに全文を複製する必要は元々なかった。

対策: Deliverable抽出の「全文複製」要求を撤廃し、200字以内の簡潔な要約で十分と明記した
（Decision/Directive抽出、DEFER検出、advances_to_task_id検出はいずれも維持）。

参照: docs/design/back_log/issue_backlog.md BL-182、docs/design/decision_log.md D-151。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _captured_prompt(monkeypatch, target_role: str) -> str:
    captured = {}

    def _fake_query_and_parse_with_retry(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        captured["prompt"] = prompt
        return fallback, False

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake_query_and_parse_with_retry)
    cela_main.call_decision_extractor(
        chat_history=[{"role": "assistant", "content": "task_5_1の成果物をwrite_agreementで登録しました。"}],
        existing_topics=["task_5_1 成果物"],
        target_role=target_role,
        owns_variables=[],
        valid_task_ids=["task_5_1"],
    )
    assert "prompt" in captured, "call_decision_extractorがquery_AIを呼ばなかった"
    return captured["prompt"]


def test_expert_prompt_no_longer_demands_verbatim_deliverable_text(monkeypatch):
    prompt = _captured_prompt(monkeypatch, "expert")
    assert "絶対に要約しないこと" not in prompt
    assert "全文をそのまま content に格納せよ" not in prompt
    assert "全文" not in prompt or "要約" in prompt  # 「全文」への言及があれば必ず不要である旨とセット


def test_expert_prompt_allows_brief_deliverable_summary():
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert "BL-182" in src
    assert "200字以内" in src


def test_decision_and_directive_extraction_instructions_are_preserved(monkeypatch):
    """[非退行確認] Decision/Directiveの抽出指示・DEFER検出指示は変更されていないこと。"""
    prompt = _captured_prompt(monkeypatch, "expert")
    assert '"Decision": 今回Agentが提案した新たなルールや計算結果' in prompt
    assert "BL-023/BL-082: 先送りの検出" in prompt
    assert "defer_to_task_id" in prompt


def test_user_branch_still_forces_empty_content_on_evaluation_update(monkeypatch):
    """[非退行確認] User側のUPDATE（評価のみ）はcontent空文字強制のまま。"""
    prompt = _captured_prompt(monkeypatch, "user")
    assert "は必ず空文字" in prompt


def test_common_rules_create_instruction_mentions_200_char_summary(monkeypatch):
    prompt = _captured_prompt(monkeypatch, "expert")
    assert "200字以内の簡潔な要約で構いません" in prompt
