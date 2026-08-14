# BL-198（新規）基本設計：国土地理院API＋OpenRouteServiceによる地理データの実測化

> Plan Mode（task-plan-reviewer-node-task-planner系エージェント）が作成した設計案の原文。
> AGENTS.md §7「実装前に1744のログを見て停滞の原因を調査」というユーザー指示に従い、
> BL-197の効果検証（`log/2026-08-09/1744`）を先に完了させたうえで承認・実装した。
> 要約せず全文保存する。

## Context（この変更が必要な理由）

BL-195〜197で、`長野県茅野市`の実データをゴール文に埋め込み、Stage3/4・初回ターン等の
User AI発言パス全てに「acceptance_criteriaを超える手段（特定のデータ取得元・ソフトウェア・
検証ログ）を義務付けない」というガードレールを追加した。しかしそれでもtask_1_1では、
User AI・Expert双方が独力で「一次資料およびGIS実測に基づく成果物」を求め続ける挙動が
複数回のドライラン（`log/2026-08-09/1230`, `1718`, `1733`）で再現した。プロンプト誘導
だけでは「そもそも実測手段がない」という制約自体は解消できないため、ユーザーの提案により、
**実際に使える公式・準公式APIをExpertへ与えることで、要求されている実測データの一部を
本当に実測値で満たせるようにする**方針へ転換した。

一次資料で確認した結果、以下の組み合わせで「標高」「2点間の直線距離・方位角」
「住所→緯度経度」「道路距離・所要時間」の4つのうち3つ（道路距離以外）は国土地理院の
無料・無認証APIで、道路距離はOpenRouteServiceの無料枠APIで、それぞれ正面から解決できる
ことが分かった（「道路区間単位の冬季リスク」は依然としてどのAPIでもカバーされないため、
これは従来通り公的情報の定性的な参照＋工学的仮定で扱う）。

## 調査結果（一次資料確認済み、2026-08-09）

| API | 提供元 | エンドポイント | 認証 | 提供データ |
|---|---|---|---|---|
| 標高API | 国土地理院（公式） | `https://cyberjapandata2.gsi.go.jp/general/dem/scripts/getelevation.php?lat=..&lon=..&outtype=JSON` | 不要 | 緯度経度→標高（`elevation`、データ源`hsrc`。取得不可時は`"-----"`） |
| 測量計算（距離・方位角） | 国土地理院 | `https://vldb.gsi.go.jp/sokuchi/surveycalc/surveycalc/bl2st_calc.pl?...&outputType=json` | 不要（10秒10回の目安あり） | 2点間の**測地線（直線）距離**・方位角。**道路距離ではない** |
| 住所検索（ジオコーディング） | 国土地理院 | `https://msearch.gsi.go.jp/address-search/AddressSearch?q=<住所>` | 不要 | 住所文字列→GeoJSON（`geometry.coordinates`=[経度,緯度]） |
| Directions（経路探索） | OpenRouteService | `POST https://api.openrouteservice.org/v2/directions/{profile}`（`profile`既定`driving-car`） | APIキー必須（無料登録、`Authorization`ヘッダ） | 2点間の**道路距離・所要時間** |

出典：[国土地理院 標高API公式ページ](https://maps.gsi.go.jp/development/elevation_s.html)、
[国土地理院 測量計算サイトAPI仕様](https://vldb.gsi.go.jp/sokuchi/surveycalc/api_help.html)、
国土地理院住所検索API実レスポンス確認、OpenRouteService公式サイト・Restrictionsページ
（無料枠の正確な日次上限は資料により2,000〜2,500件/日と揺れがあり、実装時にAPIキー
発行後のダッシュボードで確定値を再確認する）。

## 却下した代替案（道路距離）

- **OSMnx + NetworkX（ローカル処理）**：APIキー不要・無制限だが、OSM地域データの一括
  ダウンロードとグラフ構築が必要で、geopandas/shapely/fiona/pyproj等の重量級依存
  （Windowsでのネイティブビルド事情も含め軽くない）を新たに抱える。今回必要なのは
  run毎に高々十数ペアの経路照会であり、ローカルルーティンググラフを常設する規模では
  ない。BL-188のmarkitdown採用（「情報の質のためなら依存重量を許容する」）とは異なり、
  今回は既存の軽量REST API（ORS）で同じ目的を十分達成できるため見送る。
- **OSRM公開デモサーバ（router.project-osrm.org）**：APIキー不要だが、公式に評価・
  テスト用途限定と案内されている共有デモサーバであり、ドライランでの反復的な自動呼び出しは
  想定外の負荷になり得る。信頼性・継続性の保証もない。
- **GraphHopper**：無料枠が500件/日とORS（2,000〜2,500件/日）より少なく、他に優位点もない。
- **Google Maps Distance Matrix/Directions**：無料クレジットはあるがクレジットカード
  登録必須で最も重いベンダーロックイン。BL-184でDuckDuckGo→Brave Search API選定時に
  確立した「依存を軽く保つ」方針と相容れない。

## 設計

### 新規モジュール `geo_tools.py`

`web_tools.py`と同型の構成（cela_main.pyへの依存を持たない、Provider抽象化、
`(args, state, config)`統一シグネチャ）で新設する。

- `gsi_geocode_handler`：住所→緯度経度・住所文字列表記（GSI住所検索API）
- `gsi_get_elevation_handler`：緯度経度→標高・データ源識別子（GSI標高API）
- `gsi_calc_distance_bearing_handler`：2点の緯度経度→測地線距離・方位角（GSI測量計算API）
- `calc_road_route_handler`：2点（緯度経度または住所）→道路距離・所要時間
  （OpenRouteService Directions API、`RoadRouteProvider` Protocolで抽象化し将来の
  プロバイダ追加に備える。`CELA_ORS_API_KEY`環境変数未設定時は`WebSearchConfigError`
  と同型の設定エラーを返す設計をBrave Search Provider実装から踏襲）

いずれも固定の公式エンドポイントのみを叩くため、`web_fetch`のような汎用SSRF検証は不要
（対象ドメインが固定・ユーザー入力URLを受け付けない）。GSI系は簡易スロットリング
（`_DDG_MIN_REQUEST_INTERVAL_SECONDS`と同型、1秒間隔程度）のみ、ORSはrun単位の
呼び出し回数上限（後述）で保護する。

### `cela_main.py`側の配線（BL-184と同じ分担）

- 新規ツールスキーマ4件（`GSI_GEOCODE_TOOL`等）を`WEB_SEARCH_TOOL`等の定義に隣接して追加。
  説明文には**「distance_bearingは直線距離であり道路距離ではない。道路距離が必要な場合は
  calc_road_routeを使うこと」**という誤用防止の一文を必須で入れる。
- `TOOL_DISPATCH`へ4エントリを`web_search`等と同型のlambdaで登録。
- `LineageState`/`AppConfig`へ`road_route_call_count`/`max_road_route_calls`
  （既定20/run程度、`max_web_search_calls`と同型）を追加。GSI系3ツールは呼び出しコストが
  低いため専用の上限カウンタは設けず、既存のMAX_TOOL_ITER（ツールループ全体の往復上限）に
  委ねる。
- `call_expert`（system_prompt・light_system_prompt両方）・`call_detector`
  （Pass1・Pass2両方）のツールリストへ4ツールを追加。Detectorには「Expertの標高・距離主張を
  この4ツールで検算できる」という一文を追加（BL-188の根拠実在性チェックと同じ位置づけ）。
- BL-197で追加した「手段を義務付けない」誘導文の隣に、「ただし標高・直線距離・道路距離
  そのものは、これらのツールで実際に取得できるため、取得できるものは実測値を使うことが
  望ましい（web_searchでの間接的な言及より優先する）」という一文を足し、
  「実測できないものを要求しない」と「実測できるものは実測する」を両立させる。

### 環境変数（ユーザー側の準備事項）

`CELA_ORS_API_KEY`：OpenRouteServiceの無料アカウント登録（https://openrouteservice.org/dev/#/signup）
で取得し、環境変数に設定する必要がある（`CELA_BRAVE_SEARCH_API_KEY`と同じ運用）。
GSI系3ツールはAPIキー不要のため準備不要。

## ドキュメント更新（AGENTS.md §4、実装時に必須）

- `docs/refs/gsi_api/api_notes.md`：3APIの仕様・出典URL・取得日をキャッシュ。
- `docs/refs/openrouteservice/api_notes.md`：Directions APIの仕様・出典URL・取得日・
  無料枠の実測値（キー取得後に確認した正確な値）をキャッシュ。
- `docs/design/back_log/issue_backlog.md`：BL-198起票、BL-195/196/197・BL-184/188と
  相互リンク。
- `docs/design/decision_log.md`：「道路距離取得手段としてOSMnx/OSRM/GraphHopper/Google
  MapsではなくOpenRouteServiceを選ぶ」「標高・直線距離はGISへ実測を義務付けるのではなく、
  実際に取得可能なAPIを与える方向で解決する」の2件をD-xxxとして記録。
- `docs/design/decision_lineage.md`：BL-195〜198に至る一連の議論（匿名化の失敗→実データ化→
  ユーザーからのAPI提案→調査→設計）を1エントリとして記録。

## テスト計画

新規`tests/test_bl198_geo_tools.py`（`tests/test_bl184_web_tools.py`のモック境界パターンに
準拠、`httpx.get`/`httpx.post`をモック）：
- 4ハンドラそれぞれの正常系（レスポンスのパース）・異常系（`elevation="-----"`、
  APIキー未設定、HTTPエラー）
- `gsi_calc_distance_bearing`のレスポンス文字列に「道路距離ではない」旨の注記が
  常に含まれること
- `inspect.getsource(cela_main.call_expert)`/`call_detector`に4ツール名が両経路とも
  含まれることの配線確認テスト（BL-184/195と同型）

## 実装順序

1. `geo_tools.py`新設（4ハンドラ、Provider抽象化）
2. `cela_main.py`：ツールスキーマ・TOOL_DISPATCH・LineageState/AppConfig拡張・
   call_expert/call_detectorへの付与・BL-197誘導文の補記
3. `docs/refs/`キャッシュ2件
4. 新規テスト
5. `docs/design`更新（backlog/decision_log/decision_lineage）
6. `python -m py_compile`、新規テスト、既存`test_bl184_web_tools.py`等の無退行確認、
   `check_docs_consistency.py`

## 検証方法

- `python -m py_compile cela_main.py geo_tools.py`
- `pytest tests/test_bl198_geo_tools.py tests/test_bl184_web_tools.py -q`
- `python scripts/check_docs_consistency.py`
- （ユーザー側）`CELA_ORS_API_KEY`取得後、次回ドライランでExpertが実際に4ツールを呼び、
  標高・直線距離・道路距離を実測値として使い、かつBL-197の誘導により道路区間単位の
  冬季リスクまでは過剰要求しないことを目視確認する。

## 実装後の追記（Plan完了後の実施結果）

- 実装完了は`issue_backlog.md` BL-198セクションを参照（テスト29件、Detector Pass1/Pass2
  両方への配線含む）。
- ユーザーによる`CELA_ORS_API_KEY`登録後、`calc_road_route`をライブAPIに対して実行し
  動作確認済み（2026-08-09）：茅野駅付近→蓼科方面の2点間で`road_distance_m=15358.5`
  （約15.4km）・`duration_s=873.1`・`profile=driving-car`を取得。同区間のGSI測量計算API
  による直線距離（`geoLength=12020.841`、約12.0km）と比較すると道路距離が約28%長く、
  山間部の道路の屈曲を踏まえて妥当な差であることを確認した。直線距離と道路距離が実際に
  区別して機能していることが実データで裏付けられた。
