"""
BL-278: Domain Reviewの検証観点に、複数候補からの絞り込みに対する選定妥当性・十分性
チェックを追加する。

`log/2026-08-26/0031`のtask_2_2商業施設選定監査で、2段階のDetectorレビュー（Domain Review
＋数値監査）のどちらにも「商業施設3店舗の選定は本質に照らして十分か」という観点が存在せず、
選定基準が一切記録されていなかった（BL-277）ことと相まって、Detectorが「3店舗が列挙されて
いる」という事実だけを既に吟味済みの前提として暗黙的に受け入れ、先へ進んでしまっていた。

対応: `call_detector`のDomain Reviewパス（1段目、数値監査ではない）のdomain_promptへ、
「複数候補からの選定基準がreason_why等に明記されているか」「明記されている場合はその基準が
本質に照らして十分か」を確認する観点を追加した。既存のBL-087 Stage4（本質ドリフト検知）・
BL-266（本質充足性チェック）と同じ「本質記述と照らし合わせる」パターンを踏襲し、新規JSON
フィールドは追加せず既存の`constraint_issue`/`comment`へ判定結果を反映させる（BL-278自身が
「それ自体をminor以上のconstraint_issueとして指摘」と定めているため）。

参照: docs/design/back_log/issue_backlog.md BL-278。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _domain_prompt_source() -> str:
    """`call_detector`内、domain_promptを組み立てるコードブロックのみを抽出する
    （数値監査パスの誤検知を避けるため、`domain_prompt = (`から次のトップレベル代入までを
    切り出す）。"""
    src = inspect.getsource(cela_main.call_detector)
    start = src.index("domain_prompt = (")
    end = src.index("_reset_think_scratchpad()", start)
    return src[start:end]


def test_domain_prompt_contains_bl278_selection_check():
    block = _domain_prompt_source()
    assert "BL-278" in block
    assert "選定基準" in block


def test_domain_prompt_bl278_check_positioned_after_essence_blocks():
    """[実装ドキュメント] BL-087 Stage4（本質ドリフト）・BL-266（本質充足性）と同じ
    「本質記述と照らし合わせる」パターンを踏襲するため、両ブロックの直後に配置した。"""
    block = _domain_prompt_source()
    bl087_idx = block.index("BL-087 Stage4")
    bl266_idx = block.index("[BL-266]")
    bl278_idx = block.index("[BL-278:")
    assert bl087_idx < bl266_idx < bl278_idx


def test_domain_prompt_bl278_check_mentions_second_line_of_defense():
    """理由が書かれていない場合はBL-277（記録の必須化）がすり抜けた場合の第二の防波堤として
    minor以上へ差し戻す、という求める対応の要件をプロンプトが明示していること。"""
    block = _domain_prompt_source()
    assert "BL-277" in block
    assert "minor" in block


def test_domain_prompt_bl278_check_references_essence_for_sufficiency_evaluation():
    """基準が明記されている場合、本質記述と突き合わせて十分性を評価する指示があること。"""
    block = _domain_prompt_source()
    idx = block.index("[BL-278:")
    tail = block[idx:idx + 900]
    assert "本質" in tail


def test_numeric_audit_pass_not_modified_by_bl278():
    """[スコープ確認] BL-278はDomain Reviewパス（1段目）のみを対象とし、数値監査パス
    （2段目）は変更しない。数値監査パスのJSONスキーマに新規フィールドが混入していないこと
    を確認する（既存のcriteria_status等のみを持つこと）。"""
    src = inspect.getsource(cela_main.call_detector)
    numeric_schema_idx = src.index(
        '\'Return ONLY JSON: {{"risk": "low/medium/high", "constraint_issue": "none/minor/major", '
        '"comment": "判定理由", "criteria_status": [true/false, ...], '
    )
    numeric_schema_line = src[numeric_schema_idx:numeric_schema_idx + 400]
    assert "essence_sufficiency_concern" not in numeric_schema_line
    assert "BL-278" not in numeric_schema_line


def test_domain_review_json_schema_unchanged_no_new_field():
    """[実装ドキュメント] BL-278は新規JSONフィールドを追加せず、既存のconstraint_issue/
    commentへ判定結果を反映させる設計とした。Domain Reviewパスの最終JSON要求に、BL-266の
    'essence_sufficiency_concern'を超える新規フィールドが増えていないことを確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    schema_idx = src.index("Return ONLY JSON: {{\"constraint_issue\"")
    schema_line = src[schema_idx:schema_idx + 500]
    assert "essence_sufficiency_concern" in schema_line
    assert "bl278" not in schema_line.lower().replace("_", "")
