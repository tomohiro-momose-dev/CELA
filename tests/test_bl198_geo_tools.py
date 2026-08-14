"""
BL-198: geo_tools.py（gsi_geocode / gsi_get_elevation / gsi_calc_distance_bearing /
calc_road_route）の単体テストと、cela_main.pyへの配線確認。
実ネットワーク呼び出しは一切行わない（httpx呼び出しはmonkeypatchで差し替える）。

各フェイクレスポンスは、実際に公式エンドポイントへアクセスして得られた実レスポンス
（2026-08-09確認、`docs/refs/gsi_api/api_notes.md`・
`docs/refs/openrouteservice/api_notes.md`に記録）の構造をそのまま再現している。

背景: BL-195〜197でプロンプト誘導（acceptance_criteriaを超える実測手段を義務付けない）を
導入したが、それは「実測できないものを要求しない」しか達成できず、実測できるものを実測する
余地を広げるものではなかった。本BLは実在の公式・準公式APIをExpert/Detectorへ与え、標高・
直線距離・住所ジオコーディング・道路距離を実測値で満たせるようにする。

参照: docs/design/back_log/issue_backlog.md BL-198、BL-184（web_tools.pyの先例）。
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
    """[BL-198] GSI向けの1秒スロットリングでテストが遅くならないよう無効化する。"""
    monkeypatch.setattr(geo_tools, "_last_gsi_request_at", 0.0)
    monkeypatch.setattr(geo_tools.time, "sleep", lambda _s: None)


# ---------------------------------------------------------------------------
# 1. gsi_geocode
# ---------------------------------------------------------------------------

def test_gsi_geocode_parses_coordinates(monkeypatch):
    """[BL-198] GeoJSONのcoordinatesは[経度, 緯度]の順（実レスポンスで確認済み）。"""
    payload = [{
        "geometry": {"coordinates": [138.152313, 35.998463], "type": "Point"},
        "type": "Feature",
        "properties": {"addressCode": "", "title": "長野県茅野市塚原"},
    }]
    monkeypatch.setattr(geo_tools.httpx, "get", lambda *a, **kw: _FakeResponse(payload))
    result = geo_tools.gsi_geocode_handler({"query": "長野県茅野市塚原"}, {}, {})
    assert result["results"][0]["title"] == "長野県茅野市塚原"
    assert result["results"][0]["lon"] == 138.152313
    assert result["results"][0]["lat"] == 35.998463


def test_gsi_geocode_requires_query():
    assert geo_tools.gsi_geocode_handler({}, {}, {})["status"] == "error"


def test_gsi_geocode_reports_not_found_on_empty_list(monkeypatch):
    monkeypatch.setattr(geo_tools.httpx, "get", lambda *a, **kw: _FakeResponse([]))
    assert geo_tools.gsi_geocode_handler({"query": "存在しない住所"}, {}, {})["status"] == "not_found"


def test_gsi_geocode_wraps_transport_errors(monkeypatch):
    def boom(*a, **kw):
        raise RuntimeError("network down")
    monkeypatch.setattr(geo_tools.httpx, "get", boom)
    result = geo_tools.gsi_geocode_handler({"query": "茅野市"}, {}, {})
    assert result["status"] == "error" and "network down" in result["message"]


# ---------------------------------------------------------------------------
# 2. gsi_get_elevation
# ---------------------------------------------------------------------------

def test_gsi_get_elevation_returns_measured_value(monkeypatch):
    monkeypatch.setattr(
        geo_tools.httpx, "get",
        lambda *a, **kw: _FakeResponse({"elevation": 791.6, "hsrc": "1m（レーザ）"}),
    )
    result = geo_tools.gsi_get_elevation_handler({"lat": 35.994124, "lon": 138.152337}, {}, {})
    assert result["elevation_m"] == 791.6
    assert result["data_source"] == "1m（レーザ）"


def test_gsi_get_elevation_treats_dashes_as_not_found(monkeypatch):
    """[BL-198] 公式仕様どおり、取得不可地点はelevation/hsrcが文字列"-----"で返る。"""
    monkeypatch.setattr(
        geo_tools.httpx, "get",
        lambda *a, **kw: _FakeResponse({"elevation": "-----", "hsrc": "-----"}),
    )
    result = geo_tools.gsi_get_elevation_handler({"lat": 0.0, "lon": 0.0}, {}, {})
    assert result["status"] == "not_found"


def test_gsi_get_elevation_rejects_non_numeric_coordinates():
    result = geo_tools.gsi_get_elevation_handler({"lat": "北緯35度", "lon": None}, {}, {})
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 3. gsi_calc_distance_bearing
# ---------------------------------------------------------------------------

def _fake_distance_response(geo_length="12020.841"):
    return _FakeResponse({"OutputData": {
        "geoLength": geo_length,
        "azimuth1": "68.4454277777778",
        "azimuth2": "248.518369444444",
    }})


def test_gsi_calc_distance_bearing_parses_geolength(monkeypatch):
    monkeypatch.setattr(geo_tools.httpx, "get", lambda *a, **kw: _fake_distance_response())
    result = geo_tools.gsi_calc_distance_bearing_handler(
        {"lat1": 35.994124, "lon1": 138.152337, "lat2": 36.033861, "lon2": 138.276389}, {}, {},
    )
    assert result["straight_line_distance_m"] == pytest.approx(12020.841)
    assert result["azimuth1_deg"] == pytest.approx(68.4454277777778)


def test_gsi_calc_distance_bearing_always_warns_it_is_not_road_distance(monkeypatch):
    """[BL-198] 直線距離を道路距離として誤用させないための注記は必須（本BLの核心的ガード）。"""
    monkeypatch.setattr(geo_tools.httpx, "get", lambda *a, **kw: _fake_distance_response())
    result = geo_tools.gsi_calc_distance_bearing_handler(
        {"lat1": 35.9, "lon1": 138.1, "lat2": 36.0, "lon2": 138.2}, {}, {},
    )
    assert "道路距離" in result["note"]
    assert "calc_road_route" in result["note"]


def test_gsi_calc_distance_bearing_handles_identical_points(monkeypatch):
    """[BL-198] 公式仕様どおり、出発点と到着点が一致するとgeoLengthは空文字列になる。"""
    monkeypatch.setattr(geo_tools.httpx, "get", lambda *a, **kw: _fake_distance_response(""))
    result = geo_tools.gsi_calc_distance_bearing_handler(
        {"lat1": 35.9, "lon1": 138.1, "lat2": 35.9, "lon2": 138.1}, {}, {},
    )
    assert result["status"] == "error"


# ---------------------------------------------------------------------------
# 4. calc_road_route（OpenRouteService）
# ---------------------------------------------------------------------------

def test_calc_road_route_requires_api_key(monkeypatch):
    monkeypatch.delenv("CELA_ORS_API_KEY", raising=False)
    result = geo_tools.calc_road_route_handler(
        {"lat1": 35.9, "lon1": 138.1, "lat2": 36.0, "lon2": 138.2}, {}, {},
    )
    assert result["status"] == "error"
    assert "CELA_ORS_API_KEY" in result["message"]


def test_calc_road_route_parses_summary_and_counts_call(monkeypatch):
    monkeypatch.setenv("CELA_ORS_API_KEY", "test-key")
    monkeypatch.setattr(
        geo_tools.httpx, "post",
        lambda *a, **kw: _FakeResponse({"routes": [{"summary": {"distance": 15320.4, "duration": 1180.2}}]}),
    )
    state = {}
    result = geo_tools.calc_road_route_handler(
        {"lat1": 35.994124, "lon1": 138.152337, "lat2": 36.033861, "lon2": 138.276389}, state, {},
    )
    assert result["road_distance_m"] == pytest.approx(15320.4)
    assert result["duration_s"] == pytest.approx(1180.2)
    assert result["profile"] == "driving-car"
    assert state["road_route_call_count"] == 1


def test_calc_road_route_sends_lon_lat_order(monkeypatch):
    """[BL-198] ORSのcoordinatesは[経度, 緯度]の順（GSI住所検索APIと同じ、緯度経度の順ではない）。"""
    monkeypatch.setenv("CELA_ORS_API_KEY", "test-key")
    captured = {}

    def fake_post(url, **kwargs):
        captured["json"] = kwargs.get("json")
        return _FakeResponse({"routes": [{"summary": {"distance": 1.0, "duration": 2.0}}]})

    monkeypatch.setattr(geo_tools.httpx, "post", fake_post)
    geo_tools.calc_road_route_handler(
        {"lat1": 35.9, "lon1": 138.1, "lat2": 36.0, "lon2": 138.2}, {}, {},
    )
    assert captured["json"]["coordinates"] == [[138.1, 35.9], [138.2, 36.0]]


def test_calc_road_route_enforces_run_scoped_call_limit(monkeypatch):
    monkeypatch.setenv("CELA_ORS_API_KEY", "test-key")
    result = geo_tools.calc_road_route_handler(
        {"lat1": 35.9, "lon1": 138.1, "lat2": 36.0, "lon2": 138.2},
        {"road_route_call_count": 30}, {"max_road_route_calls": 30},
    )
    assert result["status"] == "error" and "上限" in result["message"]


# ---------------------------------------------------------------------------
# 5. cela_main.pyへの配線確認
# ---------------------------------------------------------------------------

_GEO_TOOL_NAMES = ["gsi_geocode", "gsi_get_elevation", "gsi_calc_distance_bearing", "calc_road_route"]


@pytest.mark.parametrize("tool_name", _GEO_TOOL_NAMES)
def test_geo_tools_registered_in_tool_dispatch(tool_name):
    assert tool_name in cela_main.TOOL_DISPATCH


@pytest.mark.parametrize("tool_name", _GEO_TOOL_NAMES)
def test_geo_tools_attached_to_call_expert(tool_name):
    src = inspect.getsource(cela_main.call_expert)
    assert tool_name in src


@pytest.mark.parametrize("tool_name", _GEO_TOOL_NAMES)
def test_geo_tools_attached_to_call_detector_both_passes(tool_name):
    """[BL-198] Detectorはドメイン妥当性（Pass1）・数値監査（Pass2）の2パス構成であり、
    どちらのツール一覧文にも載っている必要がある（片方だけだと監査経路により素通りする）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count(tool_name) >= 2


def test_call_expert_guidance_warns_straight_line_is_not_road_distance():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-198" in src
    assert "直線距離を道路距離として" in src


def test_call_detector_guidance_mentions_bl198_verification():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-198") >= 2


def test_road_route_call_limit_wired_into_state_and_config():
    src = inspect.getsource(cela_main)
    assert "max_road_route_calls" in src
    assert "road_route_call_count" in src
