"""
BL-205: read_entityとread_verified_factの役割分担が伝わらず、無駄な探索呼び出しが
繰り返される問題の是正。

log/2026-08-10/1829で、BL-204でread_entityを全ノードへ展開した後、モデルが
「何か確認したい」→read_verified_factを空クエリで呼ぶ→not_found→read_entityも
entity=""で呼ぶ→名前一覧のみ（属性なし）が返る、という探索的だが非効率な呼び出しを
複数回（User AI Stage4含む）繰り返す事例が観測された。User AI (Stage4)の思考ログに
その原因がそのまま現れている：

  "The developer mentioned that the source of truth requires using the
   read_entity function. So it seems like I should call the function to
   list all entities."

BL-204導入時に書いた誘導文「レジストリが真実の源」が、read_entity（名前を持つ事物の
属性専用）とread_verified_fact（どの事物にも属さない単独の値）の境界を一切説明して
いなかったことが原因。加えて、read_entityを空引数で呼んだ場合の返り値（名前一覧のみ、
属性なし）が、次に何をすべきかを示さないため、空振りに気づきにくかった。

対応：
1. READ_ENTITY_TOOLのスキーマ説明へ、read_verified_factとの境界を明記。
2. 空引数（一覧モード）の返り値へ、次に取るべき行動のヒント（hint）を追加。
3. call_expertの主誘導文（BL-204ブロック）へ、同じ境界説明を追記。

参照: docs/design/back_log/issue_backlog.md BL-205、BL-204。
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
    db_path = str(tmp_path / "test_bl205.db")
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


# ---------------------------------------------------------------------------
# 1. 一覧モード（entity未指定）の返り値にヒントが付くこと
# ---------------------------------------------------------------------------

def test_list_mode_includes_hint_when_entities_exist(db_conn):
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "茅野駅", "place",
                                    origin="goal_text", created_by="entity_registrar")
    result = cela_main.TOOL_DISPATCH["read_entity"]({}, {})
    assert "hint" in result
    assert "read_verified_fact" in result["hint"]
    assert "属性" in result["hint"]


def test_list_mode_omits_hint_when_no_entities_registered(db_conn):
    """[BL-205] 1件も登録が無い場合、ヒントを付けても再試行の助けにならないため
    出さない（空リストの理由は別途、正典名チェックやweb_search失敗等にある）。"""
    result = cela_main.TOOL_DISPATCH["read_entity"]({}, {})
    assert result["entities"] == []
    assert "hint" not in result


def test_named_lookup_does_not_include_the_list_mode_hint(db_conn):
    """[BL-205] ヒントは一覧モード専用。個別事物の取得結果に紛れ込ませない。"""
    conn, run_id = db_conn
    cela_main.register_entity_in_db(conn, run_id, "茅野駅", "place",
                                    origin="goal_text", created_by="entity_registrar")
    result = cela_main.TOOL_DISPATCH["read_entity"]({"entity": "茅野駅"}, {})
    assert "hint" not in result


# ---------------------------------------------------------------------------
# 2. スキーマ説明にread_entity/read_verified_factの境界が明記されていること
# ---------------------------------------------------------------------------

def test_read_entity_schema_disambiguates_from_verified_fact():
    desc = cela_main.READ_ENTITY_TOOL["function"]["description"]
    assert "BL-205" in desc
    assert "read_verified_fact" in desc
    assert "names only" in desc or "attributes" in desc


def test_read_entity_schema_entity_param_hints_at_two_step_flow():
    """[BL-205] 空引数の挙動（名前のみ・属性なし）をentityパラメータの説明自体にも書く。
    ツール一覧全体の説明文を読まずパラメータだけを見るモデルにも伝わるようにする。"""
    prop = cela_main.READ_ENTITY_TOOL["function"]["parameters"]["properties"]["entity"]
    assert "names only" in prop["description"] or "no attributes" in prop["description"]


# ---------------------------------------------------------------------------
# 3. call_expertの主誘導文に境界説明が追記されていること
# ---------------------------------------------------------------------------

def test_call_expert_guidance_disambiguates_entity_vs_verified_fact():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-205" in src
    idx = src.index("BL-205")
    nearby = src[idx:idx + 500]
    assert "read_verified_fact" in nearby


# ---------------------------------------------------------------------------
# 4. 実データ回帰: log/2026-08-10/1829のUser AI (Stage4)の呼び出しパターン
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# 5. read_entityを持つ全ノードのプロンプト本文にも境界説明があること
#
# ユーザー指摘「read_entityを使用するノードのプロンプト説明にも書かないと、見落とされます」
# を受け、スキーマ説明1箇所への追記だけでは不十分と判断した。log/2026-08-10/1829の
# 混乱はUser AI (Stage4)で発生しており、そのプロンプト本文にBL-204の言及はあっても
# read_verified_factとの境界説明が無かった。read_entityをtools=[]へ付与している
# 全ノード（BL-204で対象とした6ノード＋Expert/Detector）のプロンプト本文へ、
# BL-205の境界説明を追加した。
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_name", [
    "call_task_planner", "call_task_plan_reviewer", "call_reviewer",
    "call_reflection", "call_facilitator",
])
def test_fact_checking_nodes_have_disambiguation_in_prompt_body(node_name):
    src = inspect.getsource(getattr(cela_main, node_name))
    assert "BL-205" in src, f"{node_name}のプロンプト本文にBL-205の境界説明がありません"


def test_expert_has_disambiguation_in_prompt_body():
    src = inspect.getsource(cela_main.call_expert)
    assert src.count("BL-205") >= 2, "call_expertの両経路（system_prompt/light_system_prompt）に必要"


def test_detector_has_disambiguation_in_prompt_body_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-205") >= 2, "call_detectorの両パス（Pass1/Pass2）に必要"


def test_user_ai_has_disambiguation_in_all_four_stages():
    """[BL-205] Stage1・Stage3・Stage4・非Stage4の4箇所全てに必要。特にStage4は
    log/2026-08-10/1829で実際に混乱が発生した箇所。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert src.count("BL-205") == 4


def test_regression_empty_args_call_now_yields_actionable_hint(db_conn):
    """[BL-205] 1829ログで実際に発生した呼び出し
    read_entity({"entity": "", "entity_type": ""}) を再現し、以前は
    {'entities': [...]} だけだった返り値に、次の一手（特定名で呼び直す／
    read_verified_factを使う）が示されるようになったことを確認する。"""
    conn, run_id = db_conn
    for name, etype in [
        ("JR中央本線", "route"), ("令和2年国勢調査", "system"),
        ("公立諏訪東京理科大学", "organization"), ("組合立諏訪中央病院", "facility"),
        ("茅野駅", "facility"), ("長野県茅野市", "place"),
    ]:
        cela_main.register_entity_in_db(conn, run_id, name, etype,
                                        origin="goal_text", created_by="entity_registrar")
    result = cela_main.TOOL_DISPATCH["read_entity"]({"entity": "", "entity_type": ""}, {})
    assert len(result["entities"]) == 6
    assert "hint" in result
