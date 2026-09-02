"""
BL-336: Detector側の保険機構（entity DB登録漏れのprovisional代理登録）。

Expertがentity DBへ一件も書き込まないままDetectorの差し戻しに遭うと、call_expertは
差し戻しのたびにmessages=[]で組み立て直され、前回の調査過程（read_reference_file/
web_search/web_fetchの生データ）は完全に失われる。この保険は、Expertが一次資料の事実を
列挙したのにentity DBへ一件も書かなかったパターンをDetectorが機械的に検知し、
confidence="provisional"で代理登録することで、差し戻し後もその事実を再利用可能にする。

参照: docs/design/back_log/BL-336/BL336_basic_design.md、BL-204、BL-033。
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
    db_path = str(tmp_path / "test_bl336_detector.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
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
# 1. ツール配線（§17.1向け存在証明、BL-242の同型テストと同じ手法）
# ---------------------------------------------------------------------------

def test_detector_domain_tools_include_entity_write_tools():
    """[BL-336 §2.5] _detector_domain_toolsにregister_entity/write_entity_attributeが
    配線されていること。従来はREAD_ENTITY_TOOLのみで書き込み権限がなかった。"""
    src = inspect.getsource(cela_main.call_detector)
    domain_tools_line = next(
        line for line in src.splitlines() if "_detector_domain_tools = [" in line
    )
    assert "REGISTER_ENTITY_TOOL" in domain_tools_line
    assert "WRITE_ENTITY_ATTRIBUTE_TOOL" in domain_tools_line


def test_domain_review_tool_list_text_mentions_entity_write_tools():
    """[BL-336] LLMへ提示するツール一覧の説明文にも両ツール名が追記されていること
    （実際に配線されたツールとプロンプト上の自己申告リストが食い違わないように）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "register_entity・write_entity_attribute" in src


# ---------------------------------------------------------------------------
# 2. Detectorロールからのentity DB書き込み（権限エラーにならないこと）
# ---------------------------------------------------------------------------

def test_detector_role_can_register_entity(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "Frozen Peas", "entity_type": "regulatory_standard",
         "citations": [{"type": "document", "detail": "Expertのwhiteboard本文より"}]}, {})
    assert result["status"] == "registered"
    assert cela_main.get_last_entity_writes() == [{"entity": "Frozen Peas", "attr_name": None}]


def test_detector_role_can_write_entity_attribute(db_conn):
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "Frozen Peas", "regulatory_standard",
                                    origin="discovered", created_by="detector")
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "Frozen Peas", "attr_name": "1959_effective_date", "value": "1959-05-28",
         "reason": "Detectorが今回のExpertターンの出力から代理登録（BL-336保険機構）"}, {})
    assert result["status"] == "ok"


# ---------------------------------------------------------------------------
# 3. confidence機械的強制（§2.6、Cline指摘P1-2への対応）
# ---------------------------------------------------------------------------

def test_detector_confirmed_confidence_is_forced_to_provisional(db_conn):
    """[BL-336 §2.6] Detectorが出典を添えてconfidence="confirmed"を指定しても、
    記録される値はprovisionalへ強制される（プロンプト指示のみに頼らない機械的強制、§15.3）。
    Detectorはドメイン専門知識を保証されない監査役であり、Expertの主張を独立検証した
    わけではないため。"""
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "Frozen Peas", "regulatory_standard",
                                    origin="discovered", created_by="detector")
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "Frozen Peas", "attr_name": "1959_effective_date", "value": "1959-05-28",
         "confidence": "confirmed",
         "citations": [{"type": "document", "detail": "Expertのwhiteboard本文より"}],
         "reason": "Detectorが今回のExpertターンの出力から代理登録（BL-336保険機構）"}, {})
    assert result["status"] == "ok"
    stored = conn.execute(
        "SELECT confidence FROM entity_attributes WHERE run_id=? AND attr_name=?",
        (run_id, "1959_effective_date"),
    ).fetchone()
    assert stored["confidence"] == "provisional"


def test_expert_confirmed_confidence_is_not_forced(db_conn):
    """[BL-336 §2.6] 強制はDetectorロール限定であり、Expert自身の正当なconfirmed登録
    （出典付き）まで巻き込んで劣化させないこと（既存BL-204の挙動の非退行確認）。"""
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "Frozen Peas", "regulatory_standard",
                                    origin="discovered", created_by="expert")
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "Frozen Peas", "attr_name": "1959_effective_date", "value": "1959-05-28",
         "confidence": "confirmed",
         "citations": [{"type": "document", "detail": "AMS-141"}],
         "reason": "1959年文書に記載"}, {})
    assert result["status"] == "ok"
    stored = conn.execute(
        "SELECT confidence FROM entity_attributes WHERE run_id=? AND attr_name=?",
        (run_id, "1959_effective_date"),
    ).fetchone()
    assert stored["confidence"] == "confirmed"


# ---------------------------------------------------------------------------
# 4. entity_writes_blockのtarget_role限定（§2.3、Cline指摘P1-3への対応）
# ---------------------------------------------------------------------------

def test_entity_writes_block_is_gated_on_target_role_expert():
    """[BL-336/Cline指摘P1-3] expert_last_entity_writesはExpertノードのみが書くstateであり、
    target_role="user"（User AIターンの監査）で無条件に参照すると、前回Expertターンの
    残骸を「今回0件でした」と誤って提示してしまう。ソース上、entity_writes_blockの構築が
    target_role=="expert"のガード内にあることを確認する（§17.1: ノード内部分岐の存在証明）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert 'entity_writes_block = ""' in src
    guard_idx = src.index('if target_role == "expert":')
    block_idx = src.index("entity_writes_block = (\n")
    assert guard_idx < block_idx, (
        "entity_writes_blockの本体構築がtarget_role==\"expert\"のガードより前にある"
        "（target_role=\"user\"時にstaleなデータを提示してしまう）"
    )


def test_domain_review_prompt_interpolates_entity_writes_block():
    """[BL-336/Cline指摘P1-1] python_calls_blockは数値監査用プロンプト専用で
    ドメインレビュー用プロンプトには補間されていないため、entity_writes_blockは
    ドメインレビュー用プロンプトへ別途明示的に補間する必要がある。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "{entity_writes_block}" in src


def test_domain_review_prompt_includes_provisional_and_citations_instruction():
    """[BL-336 §2.4/Cline指摘P2-3] 代理登録の指示にconfidence=provisional固定と、
    citations必須（無いとregister_entityがエラーで空振りする）の両方が明記されていること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-336: entity DB登録漏れの保険" in src
    assert "confidenceは常にprovisional固定" in src
    assert "citationsに必ず添えてください" in src
