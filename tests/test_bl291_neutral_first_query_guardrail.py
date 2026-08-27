"""
BL-291: 探索段階でモデルの事前知識（固有名詞）が検索クエリに混入し、複数候補の発見自体が
阻害される問題への対応。

実ドライラン（log/2026-08-27/1909）で、ゴール文が「複数点在している」とのみ記載し特定の
ブランド名を一切挙げていないにもかかわらず、Expertが検索前の内部思考の時点で「イオン茅野店?」
と自らの事前知識から施設名を連想し、その名前を最初のweb_searchクエリへそのまま含めてしまった
（`{"query": "茅野市 スーパー商業施設 大型店 イオン ザ・ビッグ 住所"}`）。結果、他の実在候補
（Aコープ・デリシア等）は探索対象にすら入らず、比較イベント自体が発生しなかった。BL-278の
Domain Reviewは「成果物に複数候補比較の痕跡があるか」を見る設計のため、比較イベントが最初から
存在しない本件は構造的に捕捉できない。

対応: `WEB_SEARCH_TOOL`のtool definitionへガードレールを追加した。web_searchはExpert以外
（task_planner/Detector/User AI等）からも呼ばれる共有ツールのため、call_expert等の個別
プロンプトへの重複記載ではなく、単一の共有箇所（AGENTS.md §15.1）へ追加した。CELAは交通課題
特化のエージェントではないため、施設・業者名に限らず、あらゆる分野の固有名詞に適用される
一般化した文言にした（ユーザー指摘）。

参照: docs/design/back_log/BL-291/BL291_292_basic_design.md、issue_backlog.md BL-291。
実LLM API呼び出しは伴わない。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _web_search_description() -> str:
    return cela_main.WEB_SEARCH_TOOL["function"]["description"]


def test_web_search_description_contains_bl291_guardrail():
    desc = _web_search_description()
    assert "[BL-291]" in desc


def test_bl291_guardrail_is_domain_agnostic():
    """[一般化確認] ユーザー指摘により、施設・業者名に限定せず、製品・技術・規格・人物・組織等
    あらゆる固有名詞に適用される一般的な文言になっていること。特定分野（交通・商業施設）に
    紐づく単語だけがハードコードされていないことを確認する。"""
    desc = _web_search_description()
    idx = desc.index("[BL-291]")
    block = desc[idx: idx + 700]
    # 一般化された種類の列挙が含まれること（英語の tool description 内）
    assert "product" in block or "technology" in block or "organization" in block
    # ドライラン固有の具体例（イオン等）がハードコードされていないこと
    assert "イオン" not in block
    assert "商業施設" not in block
    assert "supermarket" not in block.lower()


def test_bl291_guardrail_mentions_unverified_hypothesis_condition():
    desc = _web_search_description()
    idx = desc.index("[BL-291]")
    block = desc[idx: idx + 700]
    assert "goal text" in block or "citations" in block
    assert "training knowledge" in block or "unverified hypothesis" in block


def test_bl291_guardrail_positioned_after_bl188_anti_pattern():
    """挿入位置がBL-188のAVOID anti-patternブロックの直後であること。"""
    desc = _web_search_description()
    bl188_idx = desc.index("AVOID this anti-pattern")
    bl291_idx = desc.index("[BL-291]")
    assert bl188_idx < bl291_idx


def test_web_search_parameters_schema_unchanged():
    """[スコープ確認] BL-291はdescriptionのみの変更であり、parameters（query/max_results）
    のJSON schemaは変更しない。"""
    params = cela_main.WEB_SEARCH_TOOL["function"]["parameters"]
    assert set(params["properties"].keys()) == {"query", "max_results"}
    assert params["required"] == ["query"]


def test_bl188_existing_anti_pattern_text_still_intact():
    """[回帰確認] BL-291追加時に既存のBL-188アンチパターン警告文を壊していないこと。"""
    desc = _web_search_description()
    assert "repeatedly calling web_search with ever-broader" in desc
    assert "web_fetch it BEFORE running another search" in desc
