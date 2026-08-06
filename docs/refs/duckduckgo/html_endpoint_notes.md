# DuckDuckGo HTML版検索エンドポイント（`html.duckduckgo.com/html/`）調査メモ

- 取得日: 2026-08-06
- 用途: BL-184（`web_search`ツール、DuckDuckGoプロバイダ実装）の設計検証

## HTTPメソッド

`https://html.duckduckgo.com/html/?q=<SEARCH_QUERY>` のように、クエリをURLパラメータ（`q`）として
付与する **GET** リクエストで動作する。POSTを要求する動作は複数の公開スクレイピングガイドで
確認できず、GET+クエリパラメータが標準的な実装方法として広く使われている。

- 出典: [How to Scrape DuckDuckGo SERP Data: 4 Proven Methods](https://brightdata.com/blog/web-data/how-to-scrape-duckduckgo)
- 出典: [How to scrape DuckDuckGo: 3 working methods](https://roundproxies.com/blog/scrape-duckduckgo/)

## 特徴

- JS非依存の静的HTML版で、動的版（duckduckgo.com、AI要約等を含む）より軽量。
- 従来型のページネーション（"Next"ボタン）を使用。
- 非公式スクレイピングである点は変わらず、ページ構造変更・レート制限のリスクは引き続き認識すること
  （BL184_basic_design.mdの「DuckDuckGoの実装方式と注意点」参照）。

## 実装への反映

BL-184設計では`httpx.get(url, params={"q": query}, timeout=10)`でGETリクエストを送る方式を採用する
（POST対応の実装は不要と判断）。ただし実装時に実際のレスポンスを確認し、GETで結果が得られない
場合はこのメモを更新した上でPOST対応を追加検討する。
