# Brave Search API 調査メモ（Web Search）

- 取得日: 2026-08-07
- 用途: BL-184（`web_search`ツール、Braveプロバイダ実装）。DuckDuckGo（`html.duckduckgo.com/html/`
  スクレイピング）がBot対策の画像認証チャレンジ（`anomaly-modal`）で数回のリクエストのうちに
  即ブロックされることを実測で確認したため（`docs/refs/duckduckgo/html_endpoint_notes.md`
  更新参照）、正式APIであるBrave Search APIへ切り替える。

## エンドポイント

`https://api.search.brave.com/res/v1/web/search`（GET）

## 認証

ヘッダ `X-Subscription-Token: <API_KEY>` にAPIキーを渡す。APIキーは
[Brave Search API](https://brave.com/search/api/)でサブスクリプション登録の上取得する
（無料枠あり）。

## リクエスト例

```
curl -s --compressed "https://api.search.brave.com/res/v1/web/search?q=brave+search" \
  -H "Accept: application/json" \
  -H "Accept-Encoding: gzip" \
  -H "X-Subscription-Token: <YOUR_API_KEY>"
```

## クエリパラメータ（主要なもの）

- `q`: 検索クエリ文字列。
- `count`: 1ページあたりの最大結果数（最大20、既定20）。
- `offset`: 開始位置（0始まり、最大9）。
- `country`, `search_lang`, `safesearch`等: 今回は未使用（既定値のまま）。

## レスポンス構造（主要なもの）

```json
{
  "query": {"original": "...", "more_results_available": true},
  "web": {
    "results": [
      {"title": "...", "url": "...", "description": "...", "extra_snippets": [...]}
    ]
  }
}
```

`web.results[].title` / `.url` / `.description` を`{title, url, snippet}`へマッピングする
（`description`を`snippet`として扱う）。

## 出典

- [Brave Search API Documentation](https://api.search.brave.com/app/documentation/web-search/get-started)
- [Web Search API Request Headers](https://api-dashboard.search.brave.com/app/documentation/web-search/request-headers)
- [Responses - Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/responses)
- [Query Parameters - Brave Search API](https://api-dashboard.search.brave.com/app/documentation/web-search/query)

## 実装への反映

`web_tools.py`の`BraveSearchProvider`が上記仕様でGETリクエストを送る。APIキーは環境変数
`CELA_BRAVE_SEARCH_API_KEY`から読み、未設定時は`WebSearchConfigError`を送出し
`web_search`ツール自体を「利用不可」として明示エラーを返す（`python_repl`の安全なエラー
返却パターンを踏襲、既存のBL184_basic_design.md方針通り）。`CELA_WEB_SEARCH_PROVIDER`の
既定値をduckduckgoからbraveへ変更する（decision_lineage.md 論点142参照）。
