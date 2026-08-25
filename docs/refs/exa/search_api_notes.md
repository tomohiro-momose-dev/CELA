# Exa Search API — 実装用リファレンス（raw HTTP、SDK不使用）

- 取得元URL: https://docs.exa.ai/reference/search-api-guide-for-coding-agents
  （リダイレクト先: https://exa.ai/docs/reference/search-api-guide-for-coding-agents）
- 取得日: 2026-08-26
- CELAのweb_search実装（`web_tools.py`）はBrave/DuckDuckGoともraw httpx呼び出しで、
  公式SDK（`exa-py`）は使わない方針（ユーザー承認、BL-271）。以下は同方針でExaを
  実装するために必要な最小限の情報のみを抜粋する。全パラメータ・型・エンドポイント
  一覧は上記URLが正（Canonical reference）。挙動が食い違う場合は上記URLを再取得して
  確認すること。

## エンドポイント

- `POST https://api.exa.ai/search`

## 認証ヘッダー

- `Authorization: Bearer $EXA_API_KEY`
- `Content-Type: application/json`

（ユーザー提供のクイックスタート抜粋にあった`exa-py`のPython SDK例は
`Exa(api_key=...)`のみでヘッダー形式を明示していなかったため、raw HTTP実装に
必要なヘッダー形式は上記URLを別途fetchして確認した。）

## リクエストボディ（camelCase、CELAで使う最小セット）

```json
{
  "query": "検索クエリ文字列",
  "type": "auto",
  "numResults": 10,
  "contents": {"highlights": true}
}
```

- `type`: 既定`"auto"`（バランス型）。CELAでは既定のまま固定して使う（`fast`/`deep`等の
  切り替えは本実装のスコープ外）。
- `numResults`: 1〜10（CELAの`web_search`ツール引数`max_results`と同じ意味）。
- `contents.highlights`: `true`でクエリ関連の抜粋を返す（Brave/DuckDuckGoの`snippet`に
  相当）。

## レスポンス形状

トップレベル:

```json
{
  "requestId": "string",
  "searchType": "string",
  "results": [ ... ],
  "output": {...},
  "costDollars": {"total": 0.0}
}
```

`results[]`の各要素（`contents.highlights: true`指定時に関係するフィールドのみ）:

- `title`: string
- `url`: string
- `highlights`: string配列（クエリ関連抜粋、複数件あり得る）
- （他に`id`/`publishedDate`/`author`/`image`/`favicon`/`text`/`summary`等があるが、
  CELAの`{title, url, snippet}`統一フォーマットには不要なため無視する）

CELAの`WebSearchProvider.search()`契約（`{'title': str, 'url': str, 'snippet': str}`の
リスト）に合わせるため、`highlights`配列を`" / "`で結合して`snippet`とする。

## HTTPステータスコード

- `401`: APIキー無効・欠落（`"Invalid or missing API key"`）
- `429`: レート制限・利用上限超過（`"Rate limit exceeded"`）
- `400`/`422`: バリデーションエラー
- `500`: サーバーエラー

BL-270で`BraveSearchProvider`に追加した「run内では回復しない失敗はWebSearchConfigError
へ変換し、以後の呼び出しを短絡する」という設計方針を踏襲し、Exaでは`401`（APIキー
無効・欠落）と`429`（利用上限超過）の両方を`WebSearchConfigError`として扱う
（Braveの`402`とは異なるステータスコードだが、意味論的に同じ「run内では回復しない
プロバイダ側の利用不可」カテゴリのため）。
