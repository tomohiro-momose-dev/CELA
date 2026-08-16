"""
BL-251: Expertは成果物にしばしば個別事項について「承認待ち」という未解決の文言を
埋め込んで提出するが、User AI（Stage3相当）には成果物全体を承認/差し戻しする動作しか
与えられておらず、個別事項単位で承認する経路が存在しなかった（ユーザー指摘：「エキスパート
からすると相手は本物の人間なのかAIなのかわかりません」「困っている様子がある」）。

調査の結果、Expertが成果物ではなく質問を投げるask_user_questionツール（BL-130）と、
それに応答するUser AIの相談応答モード（expert_consultation_mode）は既に配線済みで、
Expert→User AI→（chat_history経由で）Expertという一往復のループ自体は存在した。
塞がれていたのは2箇所：
1. Expert側: ask_user_questionの案内が「本当に前進できない場合にのみ使え」という抑制的な
   トーンで、個別の小さな採否確認への使用を明示していなかった。
2. User AI側: 相談応答モードの固定プロンプトが「write_agreementの呼び出しやタスク進行の
   判断は不要です」と明記しており、write_agreementツール自体はこのモードでも渡っている
   （tools=[...]にWRITE_AGREEMENT_TOOLを含む）にもかかわらず、使用が明示的に抑制されて
   いた。承認しても記録（write_agreement status="Approved"）が残らないため、Expertは
   read_verified_fact等で後から確認できなかった。

新しい状態遷移やグラフのノード・エッジを追加する必要はなく（ループ自体は既存）、
既存の配線の使われ方を解禁・明示する軽量な修正とした。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-251。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_expert_prompt_prefers_ask_user_question_over_embedded_pending_text():
    """call_expertのソースが、成果物内に「承認待ち」を埋め込むのではなく
    ask_user_questionでその場で個別確認するよう促す文言（BL-251）を含むこと。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-251" in src
    assert "ask_user_question" in src
    idx = src.index("BL-251")
    nearby = src[idx: idx + 600]
    assert "承認待ち" in nearby or "未承認" in nearby


def test_user_ai_consultation_prompt_no_longer_blanket_forbids_write_agreement():
    """generate_user_uttteranceの相談応答モード分岐が、write_agreementを一律不要と
    決めつける文言をもう含んでいないこと（BL-251前は明示的に禁止していた）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    idx = src.index("BL-130: Agent AIからの相談")
    block = src[idx: idx + 1200]
    assert "write_agreementの呼び出しやタスク進行の" not in block


def test_user_ai_consultation_prompt_allows_individual_item_approval():
    """同じ分岐が、個別事項の採否確認である場合にwrite_agreement(status=\"Approved\"等)で
    その場で確定させてよいというBL-251の指示を含むこと。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    idx = src.index("BL-130: Agent AIからの相談")
    block = src[idx: idx + 1200]
    assert "BL-251" in block
    assert "Approved" in block
    assert "write_agreement" in block


def test_write_agreement_tool_available_in_consultation_response_path():
    """相談応答モードで実際に呼ばれるquery_AIのtools引数にWRITE_AGREEMENT_TOOLが
    含まれていること（BL-251の指示が機能するための前提条件）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "WRITE_AGREEMENT_TOOL" in src
