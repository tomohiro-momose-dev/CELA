"""
BL-277: 複数候補から絞り込む意思決定について、選定基準・却下理由の記録を強制レベルへ格上げする。

`log/2026-08-26/0031`のtask_2_2で、Expertが実際にはweb_searchで9件前後の商業施設候補を
発見していたが、採用した3店舗について「なぜ他候補ではなくこの3店なのか」がどこにも記録されて
いなかった（`write_entity_attribute`の`reason`列は空文字、`write_agreement`の`reason_why`も
店舗選定の基準には触れていなかった）。

調査の結果、`write_agreement`の`reason_why`は既に空文字禁止済み（`_write_agreement_impl`の
必須フィールドチェックが`not args.get(f)`を使っており空文字も拒否する）と判明したため、
機械的ゲートの新規追加は`write_entity_attribute`の`reason`（従来は完全に任意、空文字許可）
のみが対象。`write_agreement`側はツールdescriptionのプロンプト強化のみで対応する
（内容の意味論的妥当性判定はBL-278/Detectorに委ね、D-206/D-207/D-211の「モデル推論内容への
機械的介入は避ける」という既存方針と整合させる）。

参照: docs/design/back_log/issue_backlog.md BL-277。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl277.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._CURRENT_CALLER_ROLE = "expert"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""


def _seed_entity(conn, run_id, name="茅野駅"):
    cela_main.register_entity_in_db(conn, run_id, name, "place",
                                     origin="goal_text", created_by="entity_registrar")


# ---------------------------------------------------------------------------
# 1. write_entity_attributeのreason無条件必須化（機械的ゲート、新規）
# ---------------------------------------------------------------------------

def test_write_entity_attribute_rejects_missing_reason(db_conn):
    conn, run_id = db_conn
    _seed_entity(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "x", "value": "1"}, {})
    assert result["status"] == "error"
    assert "reason" in result["message"]


def test_write_entity_attribute_rejects_empty_string_reason(db_conn):
    """[BL-277/AGENTS.md §13.1] 空文字はキー不在と違い`.get(key, default)`のフォールバックを
    すり抜けるため、明示的に非空チェックしていることの確認。"""
    conn, run_id = db_conn
    _seed_entity(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "x", "value": "1", "reason": ""}, {})
    assert result["status"] == "error"


def test_write_entity_attribute_rejects_whitespace_only_reason(db_conn):
    conn, run_id = db_conn
    _seed_entity(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "x", "value": "1", "reason": "   "}, {})
    assert result["status"] == "error"


def test_write_entity_attribute_accepts_non_empty_reason(db_conn):
    """対照テスト：非空reasonなら従来通り成功する（誤ブロックの回帰防止）。"""
    conn, run_id = db_conn
    _seed_entity(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "x", "value": "1", "reason": "ゴール文に明記された値"}, {})
    assert result["status"] == "ok"


def test_reason_guard_precedes_citations_check_ordering():
    """[実装ドキュメント] confidence enum検証の直後・citations取得の前にreasonチェックを
    挿入した（未登録entity・confidence不正のテストの失敗経路を変えないための位置選択）。
    ソース上の順序を固定する。"""
    src = inspect.getsource(cela_main._write_entity_attribute_handler)
    reason_idx = src.index('reason = (args.get("reason")')
    citations_idx = src.index('citations = args.get("citations")')
    assert reason_idx < citations_idx


# ---------------------------------------------------------------------------
# 2. WRITE_ENTITY_ATTRIBUTE_TOOLスキーマの必須化
# ---------------------------------------------------------------------------

def test_write_entity_attribute_tool_requires_reason():
    required = cela_main.WRITE_ENTITY_ATTRIBUTE_TOOL["function"]["parameters"]["required"]
    assert "reason" in required


def test_write_entity_attribute_tool_reason_description_mentions_bl277():
    desc = cela_main.WRITE_ENTITY_ATTRIBUTE_TOOL["function"]["parameters"]["properties"]["reason"]["description"]
    assert "BL-277" in desc
    assert "required" in desc.lower() or "non-empty" in desc.lower()


# ---------------------------------------------------------------------------
# 3. write_agreementのreason_why/entry_typeスキーマ強化（プロンプトのみ、機械的ゲートなし）
# ---------------------------------------------------------------------------

def test_write_agreement_reason_why_description_mentions_bl277():
    desc = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["reason_why"]["description"]
    assert "BL-277" in desc


def test_write_agreement_entry_type_has_description_mentioning_bl280_bl277():
    """[BL-280] entry_typeは従来description自体が存在しなかった。"""
    entry_type_schema = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["entry_type"]
    assert "description" in entry_type_schema
    assert "BL-280" in entry_type_schema["description"]
    assert "BL-277" in entry_type_schema["description"]


def test_write_agreement_reason_why_already_rejects_empty_string(db_conn):
    """[BL-277の前提事実の回帰確認] write_agreementのreason_whyは本BL着手前から既に
    空文字を拒否している（`missing = [f for f in required if not args.get(f)]`が
    空文字にもTrueになるため）。write_entity_attribute側とは異なり、この経路に
    新規の機械的ゲートは追加していない。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "x",
            "decision_what": "x", "reason_why": "", "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is False
    assert "reason_why" in result["error"]


# ---------------------------------------------------------------------------
# 4. 実際の事故シナリオの再現（end-to-end回帰テスト）
# ---------------------------------------------------------------------------

def test_full_scenario_multi_candidate_selection_without_reason_is_rejected(db_conn):
    """[BL-277] `log/2026-08-26/0031`の実事故シナリオ：複数候補（9店舗）から一部（3店舗）を
    選んだ際、reasonを書かずにwrite_entity_attributeしようとすると拒否される。"""
    conn, run_id = db_conn
    _seed_entity(conn, run_id, "オギノ茅野ショッピングセンター")
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "オギノ茅野ショッピングセンター", "attr_name": "採用理由", "value": "採用"}, {})
    assert result["status"] == "error"

    # reasonを明記すれば通る（本来あるべきだった記録）
    result2 = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "オギノ茅野ショッピングセンター", "attr_name": "採用理由", "value": "採用",
         "reason": "9候補中、駅からの徒歩圏内かつ生鮮食品を扱う点でA・コープ2店より優先"}, {})
    assert result2["status"] == "ok"
