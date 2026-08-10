"""
BL-198: 国土地理院API＋OpenRouteServiceによる地理データの実測化ツール群。

設計: docs/design/back_log/issue_backlog.md BL-198。
BL-195〜197でプロンプト誘導（acceptance_criteriaを超える実測手段を義務付けない）を
導入したが、それだけでは「実測できないものを要求しない」しか達成できず、「実測できるものを
実測する」余地を広げるものではなかった。本モジュールは、実在の公式・準公式APIをExpert/
Detectorへ与えることで、標高・2点間の直線距離・方位角・住所ジオコーディング・道路距離を
実際の実測値で満たせるようにする。

web_tools.py（BL-184）と同型の構成（cela_main.pyへ依存しない、Provider抽象化、
`(args, state, config)`統一シグネチャ）を踏襲する。web_fetchと異なり対象ドメインは
全て固定の公式エンドポイントであり、ユーザー入力URLを受け付けないため、汎用SSRF検証
（validate_url_for_fetch）は不要。
"""

from __future__ import annotations

import os
import time
from typing import Protocol

import httpx

_REQUEST_TIMEOUT_SECONDS = 10.0

# [BL-198] 国土地理院の各APIページに「サーバに過度の負担を与えないでください」との
# 注意書きがあるため、DuckDuckGoスロットリング（BL-184）と同型の簡易間隔制御を行う。
_GSI_MIN_REQUEST_INTERVAL_SECONDS = 1.0
_last_gsi_request_at = 0.0


class GeoToolConfigError(Exception):
    """[BL-198] APIキー未設定等、ツールが利用不可の場合に送出する（web_tools.WebSearchConfigErrorと同型）。"""


def _throttle_gsi() -> None:
    global _last_gsi_request_at
    elapsed = time.monotonic() - _last_gsi_request_at
    if elapsed < _GSI_MIN_REQUEST_INTERVAL_SECONDS:
        time.sleep(_GSI_MIN_REQUEST_INTERVAL_SECONDS - elapsed)
    _last_gsi_request_at = time.monotonic()


# ---------------------------------------------------------------------------
# 1. GSI住所検索API（ジオコーディング）
# ---------------------------------------------------------------------------
# [BL-198][実測 2026-08-09] 実レスポンスを確認済み:
# https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所>
# -> [{"geometry":{"coordinates":[経度,緯度],"type":"Point"},
#      "type":"Feature","properties":{"addressCode":"","title":"<正規化住所>"}}, ...]
# 認証不要。docs/refs/gsi_api/api_notes.md参照。

_GSI_GEOCODE_URL = "https://msearch.gsi.go.jp/address-search/AddressSearch"


def gsi_geocode_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-198] `gsi_geocode`ツールのハンドラ。住所文字列から緯度経度候補を取得する。"""
    query = (args.get("query") or "").strip()
    if not query:
        return {"status": "error", "message": "queryは必須です。"}

    _throttle_gsi()
    try:
        resp = httpx.get(_GSI_GEOCODE_URL, params={"q": query}, timeout=_REQUEST_TIMEOUT_SECONDS)
        resp.raise_for_status()
        features = resp.json()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"gsi_geocode失敗: {e}"}

    if not features:
        return {"status": "not_found", "message": f"'{query}'に該当する住所が見つかりませんでした。"}

    results = []
    for f in features[:5]:
        coords = (f.get("geometry") or {}).get("coordinates") or [None, None]
        results.append({
            "title": (f.get("properties") or {}).get("title", ""),
            "lon": coords[0],
            "lat": coords[1],
        })
    return {"results": results}


# ---------------------------------------------------------------------------
# 2. GSI標高API
# ---------------------------------------------------------------------------
# [BL-198][実測 2026-08-09] 実レスポンスを確認済み:
# https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lat=..&lon=..&outtype=JSON
# -> {"elevation": 791.6, "hsrc": "1m（レーザ）"}
# 取得不可の地点では elevation/hsrc が文字列"-----"になる（公式ヘルプ記載）。認証不要。

_GSI_ELEVATION_URL = "https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php"


def gsi_get_elevation_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-198] `gsi_get_elevation`ツールのハンドラ。緯度経度から標高（メートル）を取得する。"""
    try:
        lat = float(args.get("lat"))
        lon = float(args.get("lon"))
    except (TypeError, ValueError):
        return {"status": "error", "message": "lat/lonは数値で指定してください。"}

    _throttle_gsi()
    try:
        resp = httpx.get(
            _GSI_ELEVATION_URL, params={"lat": lat, "lon": lon, "outtype": "JSON"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"gsi_get_elevation失敗: {e}"}

    elevation = payload.get("elevation")
    hsrc = payload.get("hsrc")
    if elevation == "-----" or elevation is None:
        return {
            "status": "not_found",
            "message": f"lat={lat}, lon={lon}の標高データが取得できませんでした（データ提供範囲外の可能性）。",
        }
    return {
        "elevation_m": elevation,
        "data_source": hsrc,
        "note": "国土地理院DEMによる実測標高値。data_sourceはデータの解像度・取得手法を示す（1m/5m/10m等）。",
    }


# ---------------------------------------------------------------------------
# 3. GSI測量計算API（距離・方位角）
# ---------------------------------------------------------------------------
# [BL-198][実測 2026-08-09] 実レスポンスを確認済み:
# https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/bl2st_calc.pl?
#   outputType=json&ellipsoid=GRS80&latitude1=..&longitude1=..&latitude2=..&longitude2=..
# -> {"OutputData":{"geoLength":"12020.841","azimuth1":"68.44...","azimuth2":"248.51..."}}
# geoLengthはメートル単位の文字列。認証不要（目安として10秒10回程度に留めることが推奨）。
# [CONSTRAINT] これは2点間の測地線（直線）距離であり、道路距離ではない。呼び出し元
# （cela_main.pyのツール説明文）で必ず明記し、道路距離が必要な場合はcalc_road_route
# （OpenRouteService）を使うよう案内すること。

_GSI_DISTANCE_URL = "https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/bl2st_calc.pl"


def gsi_calc_distance_bearing_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-198] `gsi_calc_distance_bearing`ツールのハンドラ。2点間の測地線距離・方位角を
    計算する。返り値には「道路距離ではない」旨の注記を常に含める。"""
    try:
        lat1 = float(args.get("lat1"))
        lon1 = float(args.get("lon1"))
        lat2 = float(args.get("lat2"))
        lon2 = float(args.get("lon2"))
    except (TypeError, ValueError):
        return {"status": "error", "message": "lat1/lon1/lat2/lon2は数値で指定してください。"}

    _throttle_gsi()
    try:
        resp = httpx.get(
            _GSI_DISTANCE_URL,
            params={
                "outputType": "json", "ellipsoid": "GRS80",
                "latitude1": lat1, "longitude1": lon1,
                "latitude2": lat2, "longitude2": lon2,
            },
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"gsi_calc_distance_bearing失敗: {e}"}

    output = payload.get("OutputData") or {}
    geo_length = output.get("geoLength")
    if not geo_length:
        return {
            "status": "error",
            "message": "距離が計算できませんでした（出発点と到着点が一致している可能性があります）。",
        }
    return {
        "straight_line_distance_m": float(geo_length),
        "azimuth1_deg": float(output["azimuth1"]) if output.get("azimuth1") else None,
        "azimuth2_deg": float(output["azimuth2"]) if output.get("azimuth2") else None,
        "note": (
            "これは2点間の測地線（直線）距離・方位角であり、道路距離・道路経由の所要時間ではない。"
            "道路距離が必要な場合はcalc_road_routeを使うこと。"
        ),
    }


# ---------------------------------------------------------------------------
# 4. 道路経路探索（OpenRouteService Directions API）
# ---------------------------------------------------------------------------

_ORS_API_KEY_ENV_VAR = "CELA_ORS_API_KEY"
_DEFAULT_MAX_ROAD_ROUTE_CALLS = 20


class RoadRouteProvider(Protocol):
    def route(self, lat1: float, lon1: float, lat2: float, lon2: float, profile: str) -> dict:
        """{'distance_m': float, 'duration_s': float} を返す。失敗時は例外を送出する。"""
        ...


class OpenRouteServiceProvider:
    """[BL-198] OpenRouteService Directions API（無料枠あり、要APIキー）を使う実装。
    OSMnx+NetworkX（ローカル処理、依存重量・Windows導入の複雑さが今回の規模に見合わない）、
    OSRM公開デモサーバ（評価用途限定・反復自動呼び出しに不適）、GraphHopper（無料枠が
    ORSより少ない）、Google Maps（クレジットカード登録必須で依存が最も重い）を比較検討し、
    BL-184のBrave Search API選定と同じ「軽量な正式APIを優先する」方針でORSを採用した
    （docs/refs/openrouteservice/api_notes.md参照）。
    """

    _DIRECTIONS_URL = "https://api.openrouteservice.org/v2/directions/{profile}"

    def route(self, lat1: float, lon1: float, lat2: float, lon2: float, profile: str) -> dict:
        api_key = os.environ.get(_ORS_API_KEY_ENV_VAR, "").strip()
        if not api_key:
            raise GeoToolConfigError(
                f"calc_road_route is not configured: 環境変数{_ORS_API_KEY_ENV_VAR}が"
                "設定されていません。OpenRouteServiceの無料APIキーを取得し設定してください "
                "（https://openrouteservice.org/dev/#/signup）。"
            )
        resp = httpx.post(
            self._DIRECTIONS_URL.format(profile=profile),
            json={"coordinates": [[lon1, lat1], [lon2, lat2]]},
            headers={"Authorization": api_key, "Content-Type": "application/json"},
            timeout=_REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        payload = resp.json()
        summary = payload["routes"][0]["summary"]
        return {"distance_m": summary["distance"], "duration_s": summary["duration"]}


def get_road_route_provider() -> RoadRouteProvider:
    return OpenRouteServiceProvider()


def calc_road_route_handler(args: dict, state: dict, config: dict) -> dict:
    """[BL-198] `calc_road_route`ツールのハンドラ。2点間の道路距離・所要時間を取得する。
    run単位の呼び出し回数上限（`config["max_road_route_calls"]`、既定20）を持つ
    （web_search_handlerと同型、無料枠APIの過剰消費防止）。"""
    try:
        lat1 = float(args.get("lat1"))
        lon1 = float(args.get("lon1"))
        lat2 = float(args.get("lat2"))
        lon2 = float(args.get("lon2"))
    except (TypeError, ValueError):
        return {"status": "error", "message": "lat1/lon1/lat2/lon2は数値で指定してください。"}
    profile = (args.get("profile") or "driving-car").strip()

    count = state.get("road_route_call_count", 0)
    limit = config.get("max_road_route_calls", _DEFAULT_MAX_ROAD_ROUTE_CALLS)
    if count >= limit:
        return {
            "status": "error",
            "message": f"calc_road_routeの呼び出し上限（{limit}回/run）に達しました。",
        }

    try:
        provider = get_road_route_provider()
        result = provider.route(lat1, lon1, lat2, lon2, profile)
    except GeoToolConfigError as e:
        return {"status": "error", "message": str(e)}
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "message": f"calc_road_route失敗: {e}"}

    state["road_route_call_count"] = count + 1
    return {
        "road_distance_m": result["distance_m"],
        "duration_s": result["duration_s"],
        "profile": profile,
        "note": "道路ネットワークに沿った実測距離・所要時間（OpenRouteService）。",
    }
