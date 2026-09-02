# OpenRouteService Directions API 仕様キャッシュ（BL-198）

取得日: 2026-08-09（公式サイト・Restrictionsページ・複数の二次情報を照合）
実装: `geo_tools.py`（`OpenRouteServiceProvider` / `calc_road_route_handler`）

## 用途

2点間の**道路ネットワークに沿った距離・所要時間**を取得する。国土地理院のAPI
（`docs/refs/gsi_api/api_notes.md`）では直線距離しか得られないため、その補完として採用した。

## エンドポイント・認証

- `POST https://api.openrouteservice.org/v2/directions/{profile}`
- `profile`: `driving-car`（既定）、`foot-walking` 等。
- 認証: `Authorization: <APIキー>` ヘッダ。**APIキー必須**。
  無料登録: https://openrouteservice.org/dev/#/signup
- CELA側の環境変数: **`CELA_ORS_API_KEY`**（`CELA_BRAVE_SEARCH_API_KEY`と同じ運用）。
  未設定時は`geo_tools.GeoToolConfigError`として、取得方法を案内するエラーを返す
  （黙って失敗させず、モデルが直線距離へフォールバックできるようにするため）。

## リクエスト／レスポンス

リクエストボディ:

```json
{"coordinates": [[<経度1>, <緯度1>], [<経度2>, <緯度2>]]}
```

**座標は[経度, 緯度]の順**（GSI住所検索APIと同じ順序、緯度経度の順ではない）。

レスポンス（要点のみ）:

```json
{"routes": [{"summary": {"distance": <メートル>, "duration": <秒>}, ...}]}
```

`geo_tools.py`は`routes[0].summary`から`distance`（m）・`duration`（秒）を取り出す。

## 利用制限

- クエリ制約（公式Restrictionsページ）: 経由地点は最大50、最大距離6,000km。
- 無料枠のリクエスト数上限は資料により記載が揺れており（1日2,000件とする情報と2,500件と
  する情報がある）、公式Restrictionsページには日次上限の明記が無い。**APIキー発行後に
  ダッシュボードで実際の上限を確認すること**。
- CELA側では、無料枠の過剰消費を防ぐためrun単位の呼び出し回数上限
  （`AppConfig.max_road_route_calls`、既定30回/run）を`web_search`/`web_fetch`と同型に実装済み。

## 却下した代替案（BL-198）

| 候補 | 却下理由 |
|---|---|
| OSMnx + NetworkX（ローカル処理） | APIキー不要・無制限だが、OSM地域データの一括ダウンロードとグラフ構築が必要で、geopandas/shapely/fiona/pyproj等の重量級依存（Windowsでのネイティブビルド事情含む）を新たに抱える。run毎に高々十数ペアの照会という規模に見合わない |
| OSRM公開デモサーバ（router.project-osrm.org） | APIキー不要だが、公式に評価・テスト用途限定と案内されている共有デモサーバ。ドライランでの反復的な自動呼び出しは想定外の負荷であり、信頼性・継続性の保証もない |
| GraphHopper | 無料枠が500件/日とORSより少なく、他に優位点もない |
| Google Maps Distance Matrix / Directions | 無料クレジットはあるがクレジットカード登録必須で最も重いベンダーロックイン。BL-184でDuckDuckGo→Brave Search APIを選定した際の「軽量な正式APIを優先する」方針と相容れない |
