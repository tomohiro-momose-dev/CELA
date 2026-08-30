"""
BL-320: `call_decision_extractor`の抽出項目に対する検証網（BL-213 F3）に、モデル出力の
反復collapse（ゴミトークン・欠落フィールドの劣化生成）を検知するfatalチェックが無かった。

実インシデント（`log/2026-08-30/2051/log_no_prompt.md:592-651`、run_id=1787890406-1e73a89d）：
2件目の抽出イベントで、モデル出力が"topic"フィールドまでは出力した後、
`"_comment_removed": null, "_note_removed": null, ...`という無意味なキーの反復生成に突入し、
最終的に`"__invalid_key_to_ignore__"`等のゴミキーが延々と続いて終了した。本来入るべき
content/rationale/task_id/phase_idが一切出力されず、proposed_byも欠落していた。

既存の`_check_extracted_event`（BL-213 F3）はentry_type/action_type/target_topic
（UPDATE時）/status/topic/proposed_byしか検証しておらず、この項目は「proposed_by欠落」の
minor（正規化対象）としてのみ検出され、fatal（破棄）に該当しなかった。結果、
`item.get("task_id") or _effective_current_task_id_from(state)`が発火し、内容も理由も
空の劣化レコードが誤ったtask_id（current_task_id、内容とは無関係な別タスク）へ
サイレントに書き込まれた（実DB確認済み: AG-1788091395328-13ee73）。

BL-320はこの検証網へ、task_id等の特定フィールドに依存しない汎用的な劣化検知として、
以下2つのfatalチェックを追加する：
(a) action_type="CREATE"時にcontentが空 → fatal（UPDATE時のcontent=""は正規パターンの
    ため対象外）
(b) ドキュメント化されたスキーマに存在しないキーが混入 → fatal

参照: docs/design/back_log/BL-320/BL320_basic_design.md、issue_backlog.md BL-320。
実LLM API呼び出しは伴わない。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _ok_item(**over):
    item = {
        "action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",
        "topic": "task_4_3運賃・住民負担配慮の設計着手指示", "content": "…", "rationale": "…",
        "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_3",
    }
    item.update(over)
    return item


# ---------------------------------------------------------------------------
# (a) CREATE時のcontent必須化
# ---------------------------------------------------------------------------

def test_create_with_empty_content_is_fatal():
    ok, msg = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(content="")]})
    assert ok is False
    assert "content" in msg


def test_create_with_missing_content_key_is_fatal():
    item = _ok_item()
    del item["content"]
    ok, msg = cela_main._validate_extracted_events({"extracted_events": [item]})
    assert ok is False
    assert "content" in msg


def test_update_with_empty_content_is_not_fatal():
    """[非退行] UPDATE時のcontent=""は「Userが評価しただけ」を意味する正規パターン
    （プロンプト仕様）であり、この新チェックの対象外であること。"""
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(action_type="UPDATE", target_topic="既存トピック", content="")]})
    assert ok is True


def test_create_with_content_passes():
    ok, _ = cela_main._validate_extracted_events({"extracted_events": [_ok_item()]})
    assert ok is True


# ---------------------------------------------------------------------------
# (b) 未知キー混入の検知
# ---------------------------------------------------------------------------

def test_unknown_key_is_fatal():
    ok, msg = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(_comment_removed=None)]})
    assert ok is False
    assert "_comment_removed" in msg


def test_multiple_unknown_keys_are_reported():
    ok, msg = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(__junk__="", __invalid_key_to_ignore__="")]})
    assert ok is False
    assert "__junk__" in msg and "__invalid_key_to_ignore__" in msg


def test_only_known_keys_passes():
    ok, _ = cela_main._validate_extracted_events({"extracted_events": [_ok_item()]})
    assert ok is True


def test_owned_variable_values_key_is_not_flagged_as_unknown():
    """[非退行] 既存の正規フィールドowned_variable_valuesが誤検知されないこと。"""
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(owned_variable_values={"population": "53618"})]})
    assert ok is True


def test_defer_to_task_id_key_is_not_flagged_as_unknown():
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(status="Deferred", defer_to_task_id="task_5_1")]})
    assert ok is True


# ---------------------------------------------------------------------------
# 実インシデント回帰テスト
# ---------------------------------------------------------------------------

def test_incident_regression_degenerate_item_is_discarded():
    """[実インシデント再現] log/2026-08-30/2051相当: contentもtask_id/phase_idも一切出力されず
    proposed_byも欠落・ゴミキーが混入した項目が、`_sanitize_extracted_events`で破棄されること。
    修正前はproposed_by欠落のみがminor検出され、この項目はDBへ書き込まれていた。"""
    degenerate_item = {
        "action_type": "CREATE",
        "entry_type": "Directive",
        "status": "Proposed",
        "topic": "task__1成果物の正式確定・Ver.提出指示（修正条件①〜④）",
        "_comment_removed": None,
        "_note_removed": None,
        "__invalid_key_to_ignore__": "",
        "__junk__": "",
    }
    clean = cela_main._sanitize_extracted_events([degenerate_item, _ok_item(topic="正常な項目")])
    assert [c["topic"] for c in clean] == ["正常な項目"], (
        f"劣化した項目が破棄されず流れた（BL-320再発）: {clean}"
    )


def test_incident_regression_triggers_self_correction_retry():
    """[実インシデント再現] 修正前は検証網の穴でfatalが1件も検出されず、自己修正リトライ自体が
    発火しなかった。修正後はfatal（content欠落 or 未知キー）が検出され、リトライの機会を得る
    ことを確認する。"""
    degenerate_item = {
        "action_type": "CREATE",
        "entry_type": "Directive",
        "status": "Proposed",
        "topic": "task__1成果物の正式確定・Ver.提出指示（修正条件①〜④）",
        "_comment_removed": None,
    }
    ok, msg = cela_main._validate_extracted_events({"extracted_events": [degenerate_item]})
    assert ok is False
    assert msg != ""
