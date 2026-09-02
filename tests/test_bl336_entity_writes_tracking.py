"""
BL-336: entity DB（register_entity/write_entity_attribute）への書き込みを、BL-033
（_LAST_PYTHON_CALLS）・BL-242（_LAST_DELIVERABLE_READ_TASK_IDS）と同型のパターンで
機械的に追跡する（_LAST_ENTITY_WRITES / get_last_entity_writes）。

GAIAパイロット（1959年USDA脱水青果物等級規格）のドライラン監査で、Expertが3回の独立した
タスク実行を通じて一度もentity DBへ登録しなかったことが判明した。この機械的追跡は、
Detector側の保険機構（provisional代理登録、test_bl336_detector_entity_insurance.py）が
「今回のExpertターンでentity DB書き込みが0件だったか」を自己申告に頼らず判定するための
土台になる。

参照: docs/design/back_log/BL-336/BL336_basic_design.md、BL-204、BL-033、BL-242。
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


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl336.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._LAST_ENTITY_WRITES = []
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._LAST_ENTITY_WRITES = []


# ---------------------------------------------------------------------------
# 1. ハンドラの真の成功パスのみが記録されること
# ---------------------------------------------------------------------------

def test_register_entity_success_appends_to_last_entity_writes(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard",
         "citations": [{"type": "web", "detail": "https://example.com/frozen-peas"}]}, {})
    assert result["status"] == "registered"
    assert cela_main.get_last_entity_writes() == [{"entity": "Frozen Peas", "attr_name": None}]


def test_register_entity_already_registered_does_not_append(db_conn):
    """[BL-336/Cline指摘P2-2] 冪等な早期リターン（既存事物への再登録試行）は
    新規の書き込みではないため、追跡対象に含めない。"""
    conn, run_id = db_conn
    citations = [{"type": "web", "detail": "https://example.com/frozen-peas"}]
    first = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard", "citations": citations}, {})
    assert first["status"] == "registered"
    cela_main._LAST_ENTITY_WRITES = []  # 1件目の記録をクリアしてから2回目を試す

    second = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard", "citations": citations}, {})
    assert second["status"] == "already_registered"
    assert cela_main.get_last_entity_writes() == []


def test_register_entity_error_does_not_append(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard", "citations": []}, {})
    assert result["status"] == "error"
    assert cela_main.get_last_entity_writes() == []


def test_write_entity_attribute_success_appends_to_last_entity_writes(db_conn):
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "Frozen Peas", "regulatory_standard",
                                    origin="discovered", created_by="expert")
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "Frozen Peas", "attr_name": "1959_effective_date", "value": "1959-05-28",
         "confidence": "confirmed",
         "citations": [{"type": "document", "detail": "AMS-141"}],
         "reason": "1959年文書のFrozen/Chilledセクションに記載"}, {})
    assert result["status"] == "ok"
    assert cela_main.get_last_entity_writes() == [
        {"entity": "Frozen Peas", "attr_name": "1959_effective_date"}
    ]


def test_write_entity_attribute_unknown_entity_does_not_append(db_conn):
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "存在しない品目", "attr_name": "x", "value": "1", "reason": "r"}, {})
    assert result["status"] == "unknown_entity"
    assert cela_main.get_last_entity_writes() == []


def test_multiple_writes_accumulate_in_order(db_conn):
    """[BL-336] 44品目のような多数のentity書き込みが、呼び出し順にすべて積まれること。"""
    conn, run_id = db_conn
    for name in ["Frozen Peas", "Frozen Broccoli", "Frozen Spinach"]:
        cela_main.TOOL_DISPATCH["register_entity"](
            {"canonical_name": name, "entity_type": "regulatory_standard",
             "citations": [{"type": "document", "detail": "AMS-141"}]}, {})
        cela_main.TOOL_DISPATCH["write_entity_attribute"](
            {"entity": name, "attr_name": "1959_effective_date", "value": "1959-01-01",
             "reason": "r"}, {})
    writes = cela_main.get_last_entity_writes()
    assert len(writes) == 6
    assert writes[0] == {"entity": "Frozen Peas", "attr_name": None}
    assert writes[1] == {"entity": "Frozen Peas", "attr_name": "1959_effective_date"}
    assert writes[-1] == {"entity": "Frozen Spinach", "attr_name": "1959_effective_date"}


def test_get_last_entity_writes_returns_a_copy(db_conn):
    """[BL-336] get_last_python_calls/get_last_deliverable_readsと同じく、呼び出し元が
    返り値を変更しても内部バッファへ影響しないこと。"""
    conn, run_id = db_conn
    cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard",
         "citations": [{"type": "document", "detail": "AMS-141"}]}, {})
    writes = cela_main.get_last_entity_writes()
    writes.append({"entity": "改竄", "attr_name": None})
    assert cela_main.get_last_entity_writes() == [{"entity": "Frozen Peas", "attr_name": None}]


# ---------------------------------------------------------------------------
# 2. query_AI()によるリセット（§17.1: inspect.getsourceでの存在証明、BL-242と同型）
# ---------------------------------------------------------------------------

def test_query_ai_wrapper_resets_entity_writes_alongside_python_calls():
    """[BL-336本体] `_query_AI_live`自身はターンをまたいだ状態をリセットしない設計
    （_LAST_PYTHON_CALLS等と同型で、呼び出し元の`query_AI`ラッパーがリセットを担う）。
    `_LAST_ENTITY_WRITES`がglobal宣言・リセット代入の両方に含まれていなければ、
    前のExpertターンのentity書き込み記録が次のターンへ誤って持ち越される
    （NameErrorにはならず、意図しない別スコープの新規グローバル生成にもなりうる）。"""
    src = inspect.getsource(cela_main.query_AI)
    assert "_LAST_ENTITY_WRITES = []" in src
    reset_line = next(line for line in src.splitlines() if "_LAST_PYTHON_CALLS = []" in line)
    idx = src.index(reset_line)
    global_decl = src[:idx].splitlines()[-1]
    assert "_LAST_ENTITY_WRITES" in global_decl, (
        "_LAST_ENTITY_WRITESがquery_AI()のglobal宣言に含まれていない"
        "（NameErrorまたは別スコープの新規グローバル生成の原因になる）"
    )
