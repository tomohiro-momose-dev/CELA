"""
BL-203: (A) gsi_geocodeが施設名を無視して大字の代表点を返すことによる「誤った場所の
正しい実測値」の混入、(B) BL-201のresume時config再同期がラウンド途中中断のrunに効いて
いなかった件の修正。

log/2026-08-10/0901（run_id=1786246233-0d2e0184のresume）で、成果物に
「諏訪中央病院（標高1,239m）」「長野大学（標高1,475m）」という誤りが混入した。

(A) 国土地理院の住所検索APIは**住所ジオコーダであり施設（POI）検索ではない**。
    施設名は完全に無視され、住所部分だけで解決される。実エンドポイントで確認（2026-08-10）:
      "長野県茅野市豊平 長野大学"            -> title="長野県茅野市豊平" (36.008595, 138.295898)
      "長野県茅野市豊平 公立諏訪東京理科大学"  -> title="長野県茅野市豊平" (36.008595, 138.295898) 同一
      "長野県茅野市豊平"                     -> title="長野県茅野市豊平" (36.008595, 138.295898) 同一
      "長野県茅野市豊平5000-1"               -> title="長野県茅野市豊平５０００番地" (36.009003, 138.184799)
    大字止まりで返るのは**大字の代表点**であり、大字が山側へ広がる地域では施設の実位置と
    数km・標高で数百m離れる。この座標をgsi_get_elevationへ渡すと1,475m（実際にGSIが返す
    正しい実測値だが、場所が違う）が得られ、平地の大学が「山間部・冬季高リスク・初期対象外」と
    誤判定された。番地まで指定すれば894.2m（妥当）が得られることも実測で確認済み。
    ハルシネーションが「実測値」として洗浄されるため、推測値より発見が難しい。
    → 返却titleから解決粒度を判定し、大字止まりなら必ず警告を返す。

(B) BL-201は「resume時にローカルのstateを書き換える」実装だったが、snapshot.nextが非空
    （Ctrl+C中断の大半）だと`app.stream(None, ...)`が呼ばれ、そのローカルstateがLangGraphへ
    渡らないため一切効いていなかった。0901ではweb_searchが50ではなく30、calc_road_routeが
    30ではなく20のまま動作していた。
    → 実行時設定を実際に読むのはツールハンドラの`config`引数だけなので、TOOL_DISPATCHで
      注入する（LangGraphのチェックポイント意味論に触れない）。

参照: docs/design/back_log/issue_backlog.md BL-203、BL-198、BL-199、BL-201。
実ネットワーク呼び出しは行わない（httpx呼び出しはmonkeypatchで差し替える）。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402
import geo_tools  # noqa: E402


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


@pytest.fixture(autouse=True)
def _no_throttle_sleep(monkeypatch):
    monkeypatch.setattr(geo_tools, "_last_gsi_request_at", 0.0)
    monkeypatch.setattr(geo_tools.time, "sleep", lambda _s: None)


def _feature(title, lon, lat):
    return {"geometry": {"coordinates": [lon, lat], "type": "Point"},
            "type": "Feature", "properties": {"addressCode": "", "title": title}}


# ---------------------------------------------------------------------------
# (A-1) 解決粒度の判定
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected", [
    # 実エンドポイントで確認した実際の返却title（2026-08-10）
    ("長野県茅野市豊平５０００番地", "point"),
    ("長野県茅野市玉川４３００番地", "point"),
    ("長野県茅野市塚原二丁目６番１号", "point"),
    ("長野県茅野市豊平", "area_centroid"),
    ("長野県茅野市玉川", "area_centroid"),
    ("長野県茅野市", "area_centroid"),
])
def test_classify_geocode_precision(title, expected):
    assert geo_tools._classify_geocode_precision(title) == expected


# ---------------------------------------------------------------------------
# (A-2) ハンドラの返り値
# ---------------------------------------------------------------------------

def test_geocode_area_centroid_returns_warning(monkeypatch):
    """[BL-203] 施設名を含むクエリでも大字止まりで返るため、警告が必須。
    これが無いと『誤った場所の正しい実測値』が黙って下流へ流れる。"""
    monkeypatch.setattr(geo_tools.httpx, "get",
                        lambda *a, **kw: _FakeResponse([_feature("長野県茅野市豊平", 138.295898, 36.008595)]))
    result = geo_tools.gsi_geocode_handler({"query": "長野県茅野市豊平 公立諏訪東京理科大学"}, {}, {})
    assert result["results"][0]["precision"] == "area_centroid"
    assert "warning" in result
    # 警告は「なぜ危険か」と「次に何をすべきか」の両方を含む
    assert "住所ジオコーダ" in result["warning"]
    assert "番地" in result["warning"]


def test_geocode_point_precision_has_no_warning(monkeypatch):
    """[BL-203] 番地まで解決できた場合は警告を出さない（正常な使い方を妨げない）。"""
    monkeypatch.setattr(geo_tools.httpx, "get",
                        lambda *a, **kw: _FakeResponse([_feature("長野県茅野市豊平５０００番地", 138.184799, 36.009003)]))
    result = geo_tools.gsi_geocode_handler({"query": "長野県茅野市豊平5000-1"}, {}, {})
    assert result["results"][0]["precision"] == "point"
    assert "warning" not in result


def test_geocode_still_returns_coordinates_alongside_warning(monkeypatch):
    """[BL-203] 警告を出しても座標自体は返す（エラーにはしない）。大字の代表点にも
    正当な用途はあり、機械的に禁止するとBL-158型のデッドロックを招くため。"""
    monkeypatch.setattr(geo_tools.httpx, "get",
                        lambda *a, **kw: _FakeResponse([_feature("長野県茅野市玉川", 138.263565, 35.986366)]))
    result = geo_tools.gsi_geocode_handler({"query": "長野県茅野市玉川 諏訪中央病院"}, {}, {})
    assert result["results"][0]["lat"] == 35.986366
    assert result["results"][0]["lon"] == 138.263565
    assert "warning" in result


# ---------------------------------------------------------------------------
# (A-3) スキーマ・プロンプトへの反映
# ---------------------------------------------------------------------------

def test_geocode_tool_schema_warns_facility_names_are_ignored():
    desc = cela_main.GSI_GEOCODE_TOOL["function"]["description"]
    assert "BL-203" in desc
    assert "SILENTLY IGNORED" in desc
    assert "banchi" in desc
    assert "area_centroid" in desc


def test_expert_prompt_requires_address_not_facility_name():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-203" in src
    assert "住所ジオコーダ" in src
    # フルsystem_prompt側・light_system_prompt側の両方に入っていること
    assert src.count("BL-203") >= 2


def test_expert_prompt_forbids_renaming_locations_from_memory():
    """[BL-203] 0901では、ゴール文に公立諏訪東京理科大学と明記されているにもかかわらず
    Expertが記憶から『長野大学』（実在するが上田市の無関係な大学）と書いた。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "ゴール文" in src and "言い換え" in src


def test_detector_prompt_checks_name_and_coordinate_provenance_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-203") >= 2
    assert "誤った場所の正しい実測値" in src


# ---------------------------------------------------------------------------
# (B) 実行時設定の注入（BL-201の修正漏れ）
# ---------------------------------------------------------------------------

def test_tool_config_overrides_stale_checkpoint_limits():
    """[BL-203] チェックポイント由来の古い上限ではなく、現在のconfigの値が使われること。"""
    cela_main.set_runtime_tool_limits({
        "max_web_search_calls": 50, "max_web_fetch_calls": 40,
        "max_road_route_calls": 30, "goal_reference_dir": "docs/refs/chino_city",
    })
    stale_state = {"max_web_search_calls": 30, "max_web_fetch_calls": 30,
                   "max_road_route_calls": 20, "goal_reference_dir": "",
                   "web_search_call_count": 7}
    cfg = cela_main._tool_config(stale_state)
    assert cfg["max_web_search_calls"] == 50
    assert cfg["max_web_fetch_calls"] == 40
    assert cfg["max_road_route_calls"] == 30
    assert cfg["goal_reference_dir"] == "docs/refs/chino_city"


def test_tool_config_preserves_state_fields_and_does_not_mutate_state():
    """[BL-203] カウンタ等のstate側の値は保たれ、かつstate自体は書き換えない
    （返り値はコピー。カウンタ加算は本物のstateへ行われる必要があるため）。"""
    cela_main.set_runtime_tool_limits({"max_web_search_calls": 50})
    state = {"max_web_search_calls": 30, "web_search_call_count": 7, "run_id": "r1"}
    cfg = cela_main._tool_config(state)
    assert cfg["web_search_call_count"] == 7
    assert cfg["run_id"] == "r1"
    assert state["max_web_search_calls"] == 30  # 元のstateは不変
    cfg["web_search_call_count"] = 999
    assert state["web_search_call_count"] == 7  # コピーであることの確認


def test_counter_increments_go_to_real_state_not_the_config_copy(monkeypatch):
    """[BL-203] 上限はconfig（コピー）から、カウンタは本物のstateから読み書きされること。
    ここを取り違えると呼び出し回数が永久に増えず上限が機能しなくなる。"""
    import web_tools

    class _P:
        def search(self, query, max_results):
            return [{"title": "T", "url": "https://example.com/", "snippet": "S"}]

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _P())
    cela_main.set_runtime_tool_limits({"max_web_search_calls": 50})
    state = {"max_web_search_calls": 30, "web_search_call_count": 0}
    handler = cela_main.TOOL_DISPATCH["web_search"]
    handler({"query": "x"}, state)
    assert state["web_search_call_count"] == 1


def test_web_search_dispatch_uses_current_limit_not_checkpoint_limit(monkeypatch):
    """[BL-203] 0901の再現: チェックポイントの上限30に達していても、現在のconfigが50なら
    まだ呼び出せること。"""
    import web_tools

    class _P:
        def search(self, query, max_results):
            return [{"title": "T", "url": "https://example.com/", "snippet": "S"}]

    monkeypatch.setattr(web_tools, "get_search_provider", lambda: _P())
    cela_main.set_runtime_tool_limits({"max_web_search_calls": 50})
    state = {"max_web_search_calls": 30, "web_search_call_count": 30}
    result = cela_main.TOOL_DISPATCH["web_search"]({"query": "x"}, state)
    assert "results" in result, f"上限で弾かれた: {result}"
    assert state["web_search_call_count"] == 31


def test_read_goal_reference_dispatch_uses_current_config_dir(tmp_path):
    """[BL-203] goal_reference_dirも同様に現在のconfigが勝つこと（read_goal_referenceは
    stateを変更しないため、上書き済み辞書をstateとして渡してよい）。"""
    (tmp_path / "d.md").write_text("茅野駅の標高は789mです。", encoding="utf-8")
    cela_main.set_runtime_tool_limits({"goal_reference_dir": str(tmp_path)})
    stale_state = {"goal_reference_dir": ""}  # チェックポイントには未設定のまま保存されている
    result = cela_main.TOOL_DISPATCH["read_goal_reference"]({"keyword": "茅野駅"}, stale_state)
    assert "789m" in result


def test_set_runtime_tool_limits_called_at_run_start():
    """[BL-203] 新規run・resumeの両方を通る位置で設定されること。"""
    src = inspect.getsource(cela_main.run_ai_vs_ai_loop)
    assert "set_runtime_tool_limits(config)" in src
    start = src.index("set_runtime_tool_limits(config)")
    # resume分岐（if resume_run_id:）より前に置かれている＝両経路をカバーする
    assert start < src.index("if resume_run_id:")
