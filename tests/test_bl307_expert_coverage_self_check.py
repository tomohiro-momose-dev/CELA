"""
BL-307: Expert側に、成果物を確定する前の「網羅性セルフチェック」を追加する予防策。

BL-306（Detector側でBL-278の選定基準チェックを強化）は事後の防波堤であり、Expert自身が
最初から見落とさないための予防策ではなかった。ユーザーとの議論（run_id=1787890406-1e73a89d
のtask_1_2で「学校群」が永明小学校（GIS代表地点）と茅野高校（通学需要の対象）という別々の
学校で食い違い、ゴール文が明示する中学校も欠落していた件）を受け、Expertを2層化する
（Detectorのように別のLLM呼び出しパスを追加する）案と、既存の単一プロンプトへ確認事項を
追記する軽量案を比較検討した。

ユーザー判断（原文）: 「うーんまずは、プロンプトで行きましょうか」——2層化（追加のLLM
呼び出し・コスト増）ではなく、まず軽量なプロンプト追記から試すことを選択。

対応: call_expertのsystem_prompt（iter=1で使われるフル版）とlight_system_prompt
（iter=2以降に差し替わる軽量版、BL-178参照）の両方に、同一のBL-307チェックリスト文言を
追加した。1箇所にしか追加しないと、Expertがiter=1で即座に成果物を確定する単発ターン
（ツールループの継続なし）では一切目に触れないため、両方への配線が必須である。

参照: BL-306（Detector側の事後チェック強化）、BL-278（原設計）、BL-178（フル/軽量2種の
system_prompt設計、iter=1後にlight_system_promptへ差し替わる仕組み）。
実LLM API呼び出しは伴わない（プロンプト文言の存在・両プロンプトへの配線確認のみ）。
"""

import inspect

import cela_main


def _call_expert_source():
    return inspect.getsource(cela_main.call_expert)


def test_bl307_checklist_present_in_full_system_prompt():
    """[BL-307本体] iter=1で使われるフル版system_promptに、網羅性セルフチェックの
    文言が含まれていること。"""
    src = _call_expert_source()
    full_block_end = src.index("ここから先は実行中に変化する動的な内容")
    full_block = src[:full_block_end]
    assert "[BL-307: 確定前の網羅性セルフチェック]" in full_block
    assert "無自覚な取り違え" in full_block


def test_bl307_checklist_present_in_light_system_prompt():
    """[BL-307本体] iter=2以降に差し替わる軽量版light_system_promptにも、同一の
    セルフチェック文言が含まれていること（iter=1で即座に成果物を確定する単発ターンでは
    フル版にしか触れないため、両方への配線が必須）。"""
    src = _call_expert_source()
    light_start = src.index("light_system_prompt = (")
    light_block = src[light_start:]
    assert "[BL-307: 確定前の網羅性セルフチェック]" in light_block
    assert "無自覚な取り違え" in light_block


def test_bl307_appears_exactly_twice():
    """[配線確認] BL-307の文言が、フル版・軽量版の計2箇所にのみ存在すること
    （3箇所以上の重複貼り付けや、片方への追記漏れを検知する）。"""
    src = _call_expert_source()
    assert src.count("[BL-307: 確定前の網羅性セルフチェック]") == 2


def test_bl307_positioned_after_scratch_concerns_closure_in_both_prompts():
    """[配線位置の確認] BL-307が、両プロンプトともscratch_concerns_closure_instructionの
    呼び出し直後（成果物確定直前の最終リマインダー群）に配置されていること。"""
    src = _call_expert_source()
    positions_closure = [m for m in _all_indices(src, "_scratch_concerns_closure_instruction(")]
    positions_bl307 = [m for m in _all_indices(src, "[BL-307: 確定前の網羅性セルフチェック]")]
    assert len(positions_closure) == 2
    assert len(positions_bl307) == 2
    for bl307_pos in positions_bl307:
        assert any(closure_pos < bl307_pos for closure_pos in positions_closure), (
            "BL-307がscratch_concerns_closure_instruction呼び出しより前に出現している"
        )


def test_bl307_is_generalized_not_school_specific():
    """[一般化の確認] BL-306と同様、学校固有の記述（小学校・中学校・高校・茅野等）を
    プロンプトへ直接埋め込んでいないこと。"""
    src = _call_expert_source()
    for m in _all_indices(src, "[BL-307: 確定前の網羅性セルフチェック]"):
        block = src[m:m + 600]
        for word in ("小学校", "中学校", "高校", "茅野"):
            assert word not in block, f"BL-307ブロックに固有名詞が残っている: {word}"


def _all_indices(haystack: str, needle: str):
    start = 0
    while True:
        idx = haystack.find(needle, start)
        if idx == -1:
            return
        yield idx
        start = idx + 1
