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

## 追記（2026-08-07）: 実運用でBot対策ブロックを実測、Braveへ切替

`web_tools.py`実装後、実際に`html.duckduckgo.com/html/`へ数回（1回目は成功、2回目以降は
数十秒間隔でも）アクセスしたところ、Bot対策の画像認証チャレンジページ（HTTP 202、本文に
`anomaly-modal`／`"Unfortunately, bots use DuckDuckGo too."`を含む、`challenge-form`で
"Select all squares containing a duck"を要求）が即座に返るようになり、5秒後の再試行でも
解除されなかった。設計時に想定していた「レート制限・一時ブロックのリスク」は理論上の懸念に
留まらず、数回の疎通確認だけで実際に発動する即時的な問題であることが実測で判明した。

この結果を受け、`CELA_WEB_SEARCH_PROVIDER`の初期実装をDuckDuckGo（非公式スクレイピング）
からBrave Search API（正式API、`docs/refs/brave_search/api_notes.md`参照）へ切り替えた
（ユーザー判断、decision_lineage.md 論点142）。`DuckDuckGoSearchProvider`実装自体はコードとして
残し（Provider抽象化により`CELA_WEB_SEARCH_PROVIDER=duckduckgo`でいつでも切替可能）、既定
選択のみBraveへ変更する。
