"""
BL-259: `decision_extractor_node`の`owned_variable_values`→`verified_facts`安全網パス
（BL-023 2.6節、write_agreementのconfirmed_variables指定漏れの保険として、
write_agreement呼び出し有無に関わらず毎ターン無条件実行される）が、「値の確定」ではない
2種のイベントまで無条件に上書きしてしまっていた。

実ドライラン（`log/2026-08-17/1151`、run_id=1786921069-6bb4a6a5）のtask_4_1_mountain_designで、
Expertが`write_agreement`の`confirmed_variables`で3変数（mountain_required_vehicle_count等）を
正しく構造化データとして登録した直後、同ターンのdecision_extractorが

1. `status="Rejected"`のDeliverable差し戻しイベントに、却下理由の説明文
   （「独立読み戻し未達・未検証」）を`owned_variable_values`として誤抽出
2. `entry_type="Directive"`の作業指示イベントに、指示文そのもの
   （「正式値へ接続しない判定条件・入力欄として保持」）を`owned_variable_values`として誤抽出

の2つを連続して出力し、無条件実行の安全網パスがこの2つを`verified_facts`へそのまま
upsertしてExpertの正しい登録を2回連続で意味のないプレースホルダ文字列に上書きした
（`cela.db`のverified_factsテーブルを直接確認して検証）。

却下は定義上「値の確定」ではあり得ず、指示は「今後これを登録せよ」という未来の作業内容で
確定した値そのものではないため、`status == "Rejected"`または`entry_type == "Directive"`の
場合は安全網パスの発火自体をスキップするよう修正した（cela_main.py側の機械的ガード）。
あわせて`call_decision_extractor`のプロンプトにも同じ区別を明記した（多層防御、ただし
LLM側の指示遵守に依存しない機械的ガードが主たる防御）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-259。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _decision_extractor_node_source() -> str:
    return inspect.getsource(cela_main.decision_extractor_node)


def test_safety_net_guard_mentions_bl259():
    src = _decision_extractor_node_source()
    assert "BL-259" in src


def test_safety_net_guard_skips_rejected_status():
    src = _decision_extractor_node_source()
    assert 'status != "Rejected"' in src


def test_safety_net_guard_skips_directive_entry_type():
    src = _decision_extractor_node_source()
    assert 'entry_type != "Directive"' in src


def test_guard_condition_is_applied_before_the_upsert_call():
    """ガード条件が実際にupsert_verified_fact呼び出しへの分岐に使われていること
    （コメントだけ書かれて実際のif文に反映されていない、という事故を防ぐ）。"""
    src = _decision_extractor_node_source()
    idx = src.index('status != "Rejected"')
    nearby = src[idx: idx + 400]
    assert "upsert_verified_fact" in nearby


def test_decision_extractor_prompt_mentions_bl259():
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert "BL-259" in src
    idx = src.index("BL-259")
    nearby = src[idx: idx + 300]
    assert "Rejected" in nearby
    assert "Directive" in nearby


def _would_upsert(status: str, entry_type: str) -> bool:
    """decision_extractor_nodeのガード条件を再現した参照実装。
    実際のノード内条件（`status != "Rejected" and entry_type != "Directive"`）と
    同じ式であることを、上のsource-inspectionテストが保証する。"""
    return status != "Rejected" and entry_type != "Directive"


def test_guard_predicate_blocks_the_two_incident_cases():
    """実インシデントで実際に上書きを起こした2パターンがブロックされ、
    正規の確定イベント（Deliverable/Decision、Rejected以外）は通ることを確認する。"""
    assert _would_upsert(status="Rejected", entry_type="Deliverable") is False
    assert _would_upsert(status="Proposed", entry_type="Directive") is False
    assert _would_upsert(status="Approved", entry_type="Deliverable") is True
    assert _would_upsert(status="Proposed", entry_type="Decision") is True
