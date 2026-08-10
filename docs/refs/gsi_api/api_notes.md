# 国土地理院（GSI）API 仕様キャッシュ（BL-198）

取得日: 2026-08-09（公式ドキュメント確認＋実エンドポイントへのライブ疎通で検証）
実装: `geo_tools.py`（`gsi_geocode_handler` / `gsi_get_elevation_handler` /
`gsi_calc_distance_bearing_handler`）

いずれも**認証不要**。ただし各公式ページに「サーバに過度の負担を与えないでください」との
注意書きがあるため、`geo_tools.py`側で1秒間隔の簡易スロットリング
（`_GSI_MIN_REQUEST_INTERVAL_SECONDS`）を実装している。

## 1. 住所検索API（ジオコーディング）

- エンドポイント: `https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所>`
- 実レスポンス（2026-08-09に`長野県茅野市塚原`で確認）:

```json
[{"geometry":{"coordinates":[138.152313,35.998463],"type":"Point"},
  "type":"Feature",
  "properties":{"addressCode":"","title":"長野県茅野市塚原"}}]
```

- GeoJSON Feature の配列。**`coordinates`は[経度, 緯度]の順**（緯度経度の順ではない点に注意）。
- 該当なしの場合は空配列。

## 2. 標高API（DEM）

- 公式ページ: https://maps.gsi.go.jp/development/elevation_s.html
- エンドポイント:
  `https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lat=<緯度>&lon=<経度>&outtype=JSON`
- 実レスポンス（2026-08-09に茅野駅付近 lat=35.994124, lon=138.152337 で確認）:

```json
{"elevation":791.6,"hsrc":"1m（レーザ）"}
```

- `elevation`: 標高（メートル）。`hsrc`: データソース識別子。
- `hsrc`の取りうる値と精度: `1m（レーザ）`（航空レーザ測量、最高精度）／`5m（レーザ）`／
  `5m（写真測量）`／`5m（写真測量5C）`／`10m`（等高線由来、1m単位）。
- **標高が取得できない地点では`elevation`・`hsrc`ともに文字列`"-----"`を返す**
  （`geo_tools.py`では`status="not_found"`へ変換している）。
- `callback`（JSONP）と`outtype`（JSON）はどちらか一方のみ指定すること。

## 3. 測量計算API（距離と方位角）

- 公式仕様ページ: https://vldb.gsi.go.jp/sokuchi/surveycalc/api_help.html
- エンドポイント:
  `https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/bl2st_calc.pl?outputType=json&ellipsoid=GRS80&latitude1=..&longitude1=..&latitude2=..&longitude2=..`
- パラメータ（**全て必須**）: `outputType`（`json`/`xml`）、`ellipsoid`（`GRS80`=世界測地系／
  `bessel`=日本測地系）、`latitude1`／`longitude1`（出発点、degree）、
  `latitude2`／`longitude2`（到着点、degree）。
- 実レスポンス（2026-08-09に茅野駅→蓼科方面の2点で確認）:

```json
{"OutputData":{"geoLength":"12020.841","azimuth1":"68.4454277777778","azimuth2":"248.518369444444"}}
```

- `geoLength`: 測地線距離（**メートル単位の文字列**）。`azimuth1`/`azimuth2`: 方位角（度）。
- 出発点と到着点が一致する場合、`geoLength`は空文字列になる。
- レート制限の目安: 同一IPから10秒間に10回（TKY2JGD/PatchJGDは3回）。

### [CONSTRAINT] これは直線距離であり道路距離ではない

`geoLength`は2点間の測地線（直線）距離であり、道路ネットワークに沿った距離ではない。
山間部の屈曲した道路では実際の走行距離・所要時間を大きく過小評価するため、道路距離が
必要な場合は`calc_road_route`（OpenRouteService、`docs/refs/openrouteservice/api_notes.md`）
を使うこと。`geo_tools.py`の返り値には常にこの旨の`note`を含めており、
`cela_main.py`のツール説明文・Expert/Detectorのプロンプトでも重ねて明記している。

## 提供されていないもの（BL-198のスコープ外）

- **道路距離・所要時間**: GSIのAPIでは提供されない → OpenRouteServiceで対応。
- **道路区間単位の積雪・凍結・通行規制の実測記録**: どのAPIでも構造化データとしては
  提供されていない。公的情報の定性的な参照＋根拠を明記した工学的仮定で扱う方針
  （BL-197のガードレールがこれを過剰要求しないよう抑止している）。
