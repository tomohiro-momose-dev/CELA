"""
BL-204: 実世界事物レジストリ（entities / entity_attributes）。

log/2026-08-10/0901で、ゴール文に`公立諏訪東京理科大学`と明記されているのにExpertが記憶から
「長野大学」（実在するが上田市の無関係な大学）と書き、ゴール文由来の学生数だけを流用する
事故が起きた。**数値は`verified_facts`にあったが、名称そのものがどこにも事実として
登録されていなかった**ため、すり替わりを検出する対象が存在しなかったのが原因。

本BLは事物を一級市民にし、属性を事物にぶら下げることで、
①名称のすり替わりを機械的に防ぎ（正典名チェック＋同一性ガード）、
②属性ごとに出典・確度を保持し、
③住所↔座標の検算を可能にする（verify_entity_geo）。

Clineによる独立レビューの指摘を反映済み：
- `confidence`は`verified_facts`と同じ2値のみ（`assumption`を追加しない）。「工学的仮定」は
  `citations[].type="expert_calculation"`で表す＝確定度と出所は直交する2軸（設計書§2.1.1）
- 列名は`confirmed_by`/`confirmed_at`（`verified_facts`へ揃える）
- `read_entity`は`attr_name`を取らず全属性を返す＝読み取り側で名前を推測させない
- モデルからのalias入力は受け付けない＝同一性ガードの抜け道を作らない

参照: docs/design/back_log/BL-204/BL204_basic_design.md、BL-203、BL-199、BL-188、BL-168。
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


# 0901の事故の実データ。ゴール文には公立諏訪東京理科大学とあり、長野大学は登場しない。
_GOAL = (
    "長野県茅野市における自動運転バス導入計画。"
    "主要拠点は、JR中央本線 茅野駅、茅野市役所、組合立諏訪中央病院、"
    "公立諏訪東京理科大学、蓼科高原である。"
)


@pytest.fixture
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl204.db")
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


def _seed_goal_entities(conn, run_id):
    for name, etype in [("茅野駅", "place"), ("茅野市役所", "place"),
                        ("組合立諏訪中央病院", "facility"),
                        ("公立諏訪東京理科大学", "organization")]:
        cela_main.register_entity_in_db(conn, run_id, name, etype,
                                        origin="goal_text", created_by="entity_registrar")


# ---------------------------------------------------------------------------
# 1. 正典名チェック（本設計の中核）
# ---------------------------------------------------------------------------

def test_goal_text_seeding_rejects_names_absent_from_goal(db_conn, monkeypatch):
    """[BL-204] 0901の実データによる回帰テスト。抽出結果に「長野大学」が混ざっても、
    ゴール文に文字列として存在しない以上、origin='goal_text'では登録されない。
    これがハルシネーションを止める機械的な要。"""
    conn, run_id = db_conn
    monkeypatch.setattr(
        cela_main, "_query_and_parse_with_retry",
        lambda *a, **kw: ({"entities": [
            {"canonical_name": "公立諏訪東京理科大学", "entity_type": "organization"},
            {"canonical_name": "長野大学", "entity_type": "organization"},   # ← 記憶由来の別大学
            {"canonical_name": "組合立諏訪中央病院", "entity_type": "facility"},
        ]}, False),
    )
    result = cela_main.seed_entities_from_goal(_GOAL, run_id)
    assert "公立諏訪東京理科大学" in result["registered"]
    assert "組合立諏訪中央病院" in result["registered"]
    assert "長野大学" in result["rejected"]
    assert cela_main.resolve_entity(conn, run_id, "長野大学") is None


def test_goal_text_seeding_is_idempotent(db_conn, monkeypatch):
    """[BL-204] resumeや計画再構成で再入場しても再抽出・二重登録しない。"""
    conn, run_id = db_conn
    calls = {"n": 0}

    def _fake(*a, **kw):
        calls["n"] += 1
        return ({"entities": [{"canonical_name": "茅野駅", "entity_type": "place"}]}, False)

    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake)
    cela_main.seed_entities_from_goal(_GOAL, run_id)
    second = cela_main.seed_entities_from_goal(_GOAL, run_id)
    assert calls["n"] == 1, "2回目でLLMを再度呼んでいる"
    assert second["skipped"] is True
    rows = conn.execute("SELECT COUNT(*) c FROM entities WHERE run_id=?", (run_id,)).fetchone()
    assert rows["c"] == 1


def test_goal_text_seeding_survives_extraction_failure(db_conn, monkeypatch):
    """[BL-204] 抽出に失敗してもrunは止めない（Expertがregister_entityで補えるため）。"""
    conn, run_id = db_conn
    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry",
                        lambda *a, **kw: ({"entities": []}, True))
    result = cela_main.seed_entities_from_goal(_GOAL, run_id)
    assert result["registered"] == []


# ---------------------------------------------------------------------------
# 2. 同一性ガード（未登録名の拒否）
# ---------------------------------------------------------------------------

def test_write_attribute_rejects_unregistered_entity_with_suggestions(db_conn):
    """[BL-204] 0901の核心：未登録の「長野大学」へ属性を書こうとすると、
    `did_you_mean`付きで差し戻される。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "長野大学", "attr_name": "elevation_m", "value": "1475"}, {})
    assert result["status"] == "unknown_entity"
    assert result["did_you_mean"], "候補が空だとモデルは復帰できない"
    assert conn.execute(
        "SELECT COUNT(*) c FROM entity_attributes WHERE run_id=?", (run_id,)
    ).fetchone()["c"] == 0


def test_write_attribute_accepts_canonical_name(db_conn):
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "公立諏訪東京理科大学", "attr_name": "address",
         "value": "長野県茅野市豊平5000-1", "confidence": "confirmed",
         "citations": [{"type": "goal_text", "detail": "ゴール文"}], "reason": "ゴール文に明記された住所"}, {})
    assert result["status"] == "ok"


def test_register_entity_requires_citations(db_conn):
    """[BL-204] ゴール文に無い名前を持ち込む以上、出典を示せない登録は認めない
    （BL-188のcitations方針と同じ考え方）。"""
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "のらざあ", "entity_type": "service", "citations": []}, {})
    assert result["status"] == "error"
    assert "citations" in result["message"]


def test_register_entity_marks_origin_discovered(db_conn):
    """[BL-204] 新規登録自体は禁止しない（web_searchで正当に発見した事物はある）。
    禁止ではなく`origin`で区別する——機械的な全面禁止はBL-158型のデッドロックを招く。"""
    conn, run_id = db_conn
    result = cela_main.TOOL_DISPATCH["register_entity"](
        {"canonical_name": "のらざあ", "entity_type": "service",
         "citations": [{"type": "web", "detail": "https://example.com/"}]}, {})
    assert result["status"] == "registered"
    assert result["origin"] == "discovered"


def test_register_entity_tool_has_no_alias_parameter():
    """[BL-204/Clineレビュー軽4] モデルが自由にaliasを追加できると同一性ガードが
    そこから抜けるため、v1ではalias引数を持たせない。"""
    props = cela_main.REGISTER_ENTITY_TOOL["function"]["parameters"]["properties"]
    assert "aliases" not in props and "alias" not in props


# ---------------------------------------------------------------------------
# 3. 出典封筒（confidence は2値のみ・confirmedは出典必須）
# ---------------------------------------------------------------------------

def test_confidence_rejects_assumption_value(db_conn):
    """[BL-204/Clineレビュー中1] `confidence`は`verified_facts`と同じ2値のみ。
    「工学的仮定」はcitations.type=expert_calculationで表す（直交2軸）。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "x", "value": "1", "confidence": "assumption"}, {})
    assert result["status"] == "error"
    assert "expert_calculation" in result["message"]


def test_confidence_enum_matches_verified_facts():
    """[BL-204] スキーマ側でも既存のverified_factsのenumと一致していること。"""
    assert cela_main._ENTITY_CONFIDENCE_VALUES == ("confirmed", "provisional")
    wa_enum = (cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]
               ["confirmed_variables"]["items"]["properties"]["confidence"]["enum"])
    assert set(cela_main._ENTITY_CONFIDENCE_VALUES) == set(wa_enum)


def test_confirmed_requires_citations(db_conn):
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "y", "value": "1", "confidence": "confirmed",
         "reason": "テスト用の値"}, {})
    assert result["status"] == "error"


def test_provisional_without_citations_is_allowed(db_conn):
    """[BL-204] 暫定値は出典無しでも書ける（BL-041の「既定はprovisional」と整合）。
    ここを塞ぐと唯一の記録手段が失われBL-158型のデッドロックになる。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "y", "value": "1", "reason": "テスト用の値"}, {})
    assert result["status"] == "ok"


def test_attribute_table_uses_confirmed_by_column(db_conn):
    """[BL-204/Clineレビュー中2] 列名はverified_factsへ揃える。"""
    conn, _ = db_conn
    cols = {r[1] for r in conn.execute("PRAGMA table_info(entity_attributes)").fetchall()}
    assert "confirmed_by" in cols and "confirmed_at" in cols
    assert "recorded_by" not in cols


# ---------------------------------------------------------------------------
# 4. 読み取り（全属性を返す・属性名を推測させない）
# ---------------------------------------------------------------------------

def test_read_entity_returns_all_attributes(db_conn):
    """[BL-204/Clineレビュー軽3] `attr_name`引数を持たず全属性を返すことで、
    読み取り側で属性名を推測する場面自体を無くす。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    for an, v in [("address", "A"), ("coordinates", "35.9,138.1"), ("elevation_m", "796")]:
        cela_main.TOOL_DISPATCH["write_entity_attribute"](
            {"entity": "茅野駅", "attr_name": an, "value": v, "reason": "テスト用の値"}, {})
    result = cela_main.TOOL_DISPATCH["read_entity"]({"entity": "茅野駅"}, {})
    assert {a["attr_name"] for a in result["attributes"]} == {"address", "coordinates", "elevation_m"}


def test_read_entity_tool_has_no_attr_name_parameter():
    props = cela_main.READ_ENTITY_TOOL["function"]["parameters"]["properties"]
    assert "attr_name" not in props


def test_new_attribute_name_echoes_existing_names(db_conn):
    """[BL-204/Clineレビュー軽3] 新しい属性名を作ったときだけ既存一覧を返し、
    表記ゆれによる重複作成（coordinates と coordinate の併存）に気づけるようにする。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "coordinates", "value": "35.9,138.1", "reason": "テスト用の値"}, {})
    result = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "coordinate", "value": "35.9,138.1", "reason": "テスト用の値"}, {})
    assert result.get("created_new_attribute") is True
    assert "coordinates" in result["all_attribute_names"]
    # 既存属性の更新では一覧を返さない（毎回返すとノイズになるため）
    again = cela_main.TOOL_DISPATCH["write_entity_attribute"](
        {"entity": "茅野駅", "attr_name": "coordinates", "value": "36.0,138.2", "reason": "テスト用の値"}, {})
    assert "created_new_attribute" not in again


def test_read_entity_lists_all_when_no_entity_given(db_conn):
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["read_entity"]({}, {})
    assert len(result["entities"]) == 4


# ---------------------------------------------------------------------------
# 5. verify_entity_geo（住所↔座標の検算）
# ---------------------------------------------------------------------------

def test_verify_entity_geo_detects_area_centroid_mismatch(db_conn, monkeypatch):
    """[BL-204] 0901の実データ回帰。豊平の大字代表点（36.008595,138.295898）を座標として
    保存していた事物について、住所（豊平5000-1）を引き直すと約9km離れた地点
    （36.009003,138.184799）が返り、不一致として検出できること。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    for an, v in [("address", "長野県茅野市豊平5000-1"),
                  ("coordinates", "36.008595, 138.295898")]:
        cela_main.TOOL_DISPATCH["write_entity_attribute"](
            {"entity": "公立諏訪東京理科大学", "attr_name": an, "value": v, "reason": "テスト用の値"}, {})
    monkeypatch.setattr(
        cela_main.geo_tools, "gsi_geocode_handler",
        lambda args, state, config: {"results": [{
            "title": "長野県茅野市豊平５０００番地", "lon": 138.184799,
            "lat": 36.009003, "precision": "point"}]},
    )
    result = cela_main.TOOL_DISPATCH["verify_entity_geo"](
        {"entity": "公立諏訪東京理科大学"}, {})
    assert result["verdict"] == "mismatch"
    assert result["gap_km"] > 5


def test_verify_entity_geo_reports_consistent_when_close(db_conn, monkeypatch):
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    for an, v in [("address", "長野県茅野市豊平5000-1"),
                  ("coordinates", "36.009003, 138.184799")]:
        cela_main.TOOL_DISPATCH["write_entity_attribute"](
            {"entity": "公立諏訪東京理科大学", "attr_name": an, "value": v, "reason": "テスト用の値"}, {})
    monkeypatch.setattr(
        cela_main.geo_tools, "gsi_geocode_handler",
        lambda args, state, config: {"results": [{
            "title": "長野県茅野市豊平５０００番地", "lon": 138.184799,
            "lat": 36.009003, "precision": "point"}]},
    )
    result = cela_main.TOOL_DISPATCH["verify_entity_geo"]({"entity": "公立諏訪東京理科大学"}, {})
    assert result["verdict"] == "consistent"


def test_verify_entity_geo_not_applicable_without_address(db_conn):
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    result = cela_main.TOOL_DISPATCH["verify_entity_geo"]({"entity": "茅野駅"}, {})
    assert result["status"] == "not_applicable"


# ---------------------------------------------------------------------------
# 6. ゴール改定時の警告付記（BL-168の先例へ揃える）
# ---------------------------------------------------------------------------

def test_goal_revision_marks_entity_attributes_stale(db_conn):
    """[BL-204/設計書§6決定4] entity_attributesもverified_factsと同じ性質（上書きされない限り
    現在値として返り続ける）を持つため、BL-168と同じ扱いを適用する。新しい扱いを発明しない。"""
    src = inspect.getsource(cela_main._revise_goal_tool_impl)
    assert "entity_attributes" in src
    assert "UPDATE entity_attributes SET reason=?" in src


# ---------------------------------------------------------------------------
# 7. 配線とプロンプト
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("tool_name", ["register_entity", "write_entity_attribute",
                                       "read_entity", "verify_entity_geo"])
def test_tools_registered_in_dispatch(tool_name):
    assert tool_name in cela_main.TOOL_DISPATCH


def test_expert_gets_write_tools_but_not_the_audit_tool():
    """[BL-204] Expertは記録する側、Detectorは検算する側。verify_entity_geoは監査ツール。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "REGISTER_ENTITY_TOOL" in src
    assert "WRITE_ENTITY_ATTRIBUTE_TOOL" in src
    assert "READ_ENTITY_TOOL" in src
    assert "VERIFY_ENTITY_GEO_TOOL" not in src


def test_detector_gets_read_and_audit_tools_on_both_passes():
    """[BL-204] Detectorはドメイン妥当性（Pass1）・数値監査（Pass2）の2パス構成であり、
    どちらにも付与されている必要がある（片方だけだと監査経路により素通りする）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("READ_ENTITY_TOOL") >= 2
    assert src.count("VERIFY_ENTITY_GEO_TOOL") >= 2
    assert "WRITE_ENTITY_ATTRIBUTE_TOOL" not in src


def test_expert_prompt_guidance_is_domain_agnostic():
    """[BL-204/ユーザー決定3] v1から全事物型を対象にするため、プロンプト誘導は
    ドメイン非依存の一般的表現で書く（BL-196でユーザーが明示した規律）。
    特定ゴールに寄せた語（茅野・GIS・バス等）を含めない。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-204" in src
    start = src.index("BL-204: 課題に登場する事物の事実はレジストリで管理する")
    block = src[start:start + 1400]
    for goal_specific in ("茅野", "GIS", "諏訪", "自動運転"):
        assert goal_specific not in block, f"ゴール固有語'{goal_specific}'がBL-204誘導文に混入"


def test_expert_prompt_forbids_renaming_and_requires_citations():
    src = inspect.getsource(cela_main.call_expert)
    assert "ゴール文に書かれた表記をそのまま" in src or "ゴール文の表記をそのまま" in src
    assert "expert_calculation" in src


def test_detector_prompt_mentions_registry_cross_check_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-204") >= 2
    assert "read_entity" in src and "verify_entity_geo" in src


def test_seed_entities_called_from_task_planner_node():
    """[BL-204/ユーザー決定1] 専用ノードを新設せずtask_planner内で行う
    （build_graphのトポロジーを変更しない）。"""
    src = inspect.getsource(cela_main.task_planner_node)
    assert "seed_entities_from_goal" in src


# ---------------------------------------------------------------------------
# 8. read_entityの全ノードへの展開（事実確認に関わるノードのみ、書き込み系は拡大しない）
#
# ユーザー提案「少なくともread_entityは全ノードが使えたほうが良いのでは？」を受け、
# 読み取り専用・呼び出し予算を消費しないread_entityのみを、成果物・主張の事実確認に
# 関わるノードへ展開した。register_entity/write_entity_attribute（書き込み系）は
# Expertのみに限定したまま（誰が事物を登録・確定してよいかという権限の問題であり、
# read_entityの「見るだけ」とはリスクの性質が異なるため）。
# 対象外（call_orchestrator/call_resource_arbiter/call_integrator）は、事実確認より
# フェーズ選択・予算調整・成果物マージが主目的のノードとして意図的に除外している。
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("node_name", [
    "call_task_planner", "call_task_plan_reviewer", "call_reviewer",
    "call_reflection", "call_facilitator",
])
def test_fact_checking_nodes_gain_read_entity(node_name):
    src = inspect.getsource(getattr(cela_main, node_name))
    assert "READ_ENTITY_TOOL" in src, f"{node_name}にREAD_ENTITY_TOOLが付与されていません"
    assert "read_entity" in src, f"{node_name}のプロンプト文にread_entityの言及がありません"


def test_write_tools_not_extended_to_fact_checking_nodes():
    """[BL-204] read_entityだけを広げ、register_entity/write_entity_attributeは
    Expert専用のまま維持する（書き込み権限は拡大しない）。"""
    for node_name in ["call_task_planner", "call_task_plan_reviewer", "call_reviewer",
                      "call_reflection", "call_facilitator"]:
        src = inspect.getsource(getattr(cela_main, node_name))
        assert "REGISTER_ENTITY_TOOL" not in src, f"{node_name}にREGISTER_ENTITY_TOOLが混入"
        assert "WRITE_ENTITY_ATTRIBUTE_TOOL" not in src, f"{node_name}にWRITE_ENTITY_ATTRIBUTE_TOOLが混入"


def test_user_ai_all_four_stages_gain_read_entity():
    """[BL-204] generate_user_utterance内の4経路（Stage1レビュー・Stage3承認判断・
    Stage4修正指示・非Stage4の初回ターン等）全てにread_entityを付与する。特にStage3/4は
    BL-197（過剰な実測要求）の発生源そのものであり、要求前にレジストリを確認できることが
    直接的な再発防止になる。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    # Stage1 + Stage3 + Stage4(リトライ含め2箇所) + 非Stage4(リトライ含め2箇所) = 6箇所
    assert src.count("READ_ENTITY_TOOL") == 6


def test_excluded_nodes_do_not_gain_read_entity():
    """[BL-204] フェーズ選択・予算調整・成果物マージが主目的のノードは対象外のまま。"""
    for node_name in ["call_orchestrator", "call_resource_arbiter", "call_integrator",
                      "call_decision_extractor", "call_goal_essence_analyst"]:
        src = inspect.getsource(getattr(cela_main, node_name))
        assert "READ_ENTITY_TOOL" not in src, f"{node_name}は対象外のはずですがREAD_ENTITY_TOOLが混入"


def test_read_entity_call_via_dispatch_from_non_expert_role(db_conn):
    """[BL-204] read_entityハンドラ自体はcaller_roleに依存せず動作する（read_verified_fact等の
    既存の読み取り専用ツールと同じく、呼び出し元ロールを問わない設計であることの確認）。"""
    conn, run_id = db_conn
    _seed_goal_entities(conn, run_id)
    cela_main._CURRENT_CALLER_ROLE = "reflection"
    result = cela_main.TOOL_DISPATCH["read_entity"]({"entity": "茅野駅"}, {})
    assert result["canonical_name"] == "茅野駅"
    cela_main._CURRENT_CALLER_ROLE = "expert"
