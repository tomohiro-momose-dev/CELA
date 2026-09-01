# BL-335 Plan Review（独立レビュー: Clineに代わる手動レビュー分）

- 対象: BL-335 3段階改善計画（Playwright描画フェッチ / PDF Vision / REPL pandas）
- レビュー方法: 計画内の全ファイル:行番号主張・証拠主張を実コード/実ファイルと突き合わせ（§16.2）。Cline §19.1レビューは実行環境不調によりユーザー了承済み省略、本レビューが代替。
- 検証日: 2026-09-01、HEAD=ea09d0a（DAG_impl）

## 0. 検証済み事実（計画の主張と実コードの突合結果）

以下はすべて**実コードで確認済み・主張どおり**:

| 主張 | 検証結果 |
|---|---|
| fetch_and_extract = web_tools.py:431-485、素のhttpx静的取得のみ | ✅ (442-443: `httpx.Client(follow_redirects=False).get`) |
| validate_url_for_fetch = 384-413、getaddrinfo後IP検査 | ✅ |
| _DOCUMENT_EXTENSIONS = web_tools.py:74（.pdf,.docx,.xlsx,.xls,.pptx,.epub,.csv） | ✅ |
| write_cache = 503-509（Markdownのみ保存） | ✅ |
| _ALLOWED_IMPORTS = 549-552 / _DANGEROUS_NAMES = 555-558（"open"含む） | ✅ |
| _REPL_SESSION_BOOTSTRAP = 625-641 / _PythonReplSession = 644-732 / `_run_python_repl`の`["python", ...]` = 613 | ✅ |
| PYTHON_REPL_TOOL = 735 / WEB_FETCH_TOOL = 1234-1269 | ✅ |
| glm_5_3_flash = cela_main.py:362 / mimo_2_5 = 360（参照箇所なし=未配線） | ✅ |
| 13ロール変数がglm_5_3_flashに統一 = 411-465 | ✅ |
| _TRACE_LINEAGE_USAGE_PARAGRAPH ≈ 11667 / _task_planner_tools ≈ 12432 / _expert_tools ≈ 13287（WEB_FETCH_TOOL保有） / _task_plan_reviewer_tools ≈ 17150 | ✅ |
| _query_AI_live = 6439 / _RUNTIME_TOOL_LIMIT_KEYS = 5755 / _resume_config_overrides_from = 5763 | ✅ |
| 証拠: 縦書き表ヘッダ崩れ（web_cache/40d17513c6c29834.md に「森」「青」「手」「岩」単独行 ×12） | ✅ |
| 証拠: 文字重複・(cid:7165)（web_cache/15ec6faeecea5b45.md ×6） | ✅ |
| 証拠: CAMPFIRE本文欠落（web_cache/c284bd8209951e46.md 192行、「来場/達成金額/パトロン」0ヒット） | ✅ |
| 証拠: xlsx→NaNダンプ（log/2026-08-26/2334/log_no_prompt.md NaN ×526） | ✅ |
| requirements.txtは既存2依存ともunpinned | ✅ |

問題設定自体は実データに裏付けられており、対症療法でなく構造改善とする判断は妥当。

## 1. 重大指摘（実装着手前にユーザー判断が必要）

### R1（High）: Playwrightのリダイレクト追従が既存の明示的設計決定と矛盾する

現行`fetch_and_extract`は301/302/303/307/308を`SsrfBlockedError`で**拒否**し（web_tools.py:444-448）、
`WEB_FETCH_TOOL`のdescriptionにも「**Redirects are NOT followed** (fetch the redirect target url directly
instead)」と明記されている（cela_main.py:1255）。一方`page.goto()`は透過的にリダイレクトを追う。
計画は最終URLのSSRF再検証（§1.2）には言及するが、**このポリシー矛盾自体に触れていない**。

- 影響: Playwrightが既定パスになると、httpx時代にエラーになっていたURLが黙ってリダイレクト先の
  内容を返すようになる。同一URLが経路によって異なる結果を返す二重動作になり、§15.1（一つのルール
  一箇所）の精神にも反する。
- 選択肢: (a) ポリシーを「追従する」に変更し、routeガード＋最終URL検証でSSRF安全性を担保した上で
  WEB_FETCH_TOOL文言・テスト・decision_log（D-xxx）を更新する。http→https正規化等の合法リダイレクト
  を毎回エラーにする現行挙動は実用上不利な面があり、(a)を推奨する。/ (b) 現行ポリシーを維持し、
  `page.url`と要求URLの不一致を検出して破棄する（正規リダイレクトの誤爆が増える）。
- いずれを選んでも**decision_logへの記録とdescription・テストの同期が必須**。計画書にこの論点の記載が無い。

### R2（Medium-High）: 兄弟.rawキャッシュは「既に.mdだけキャッシュ済みのURL」に対し永遠に生成されない（出口の欠落）

§2.2の生バイト書き込みは`fetch_and_extract`の実取得経路にしか存在しない。web_fetchハンドラは.mdの
キャッシュヒット時にmarkitdown変換前の取得自体をスキップするため、**BL-335以前にキャッシュ済みの
PDF/xlsx URLは、再fetchしても（キャッシュヒットで終わるため）兄弟.rawが一生生成されない**。
「refetchすればrawは手に入る」というLLM向け案内は嘘になる。バックフィルをスコープ外とする判断自体は
妥当だが、出口（消費経路）として次のいずれかを明示的に決める必要がある（§15.4）:

- (a) `read_pdf_page_as_image`が兄弟.pdf不在時に「このPDFはBL-335以前のキャッシュでrawなし。visionは
  使えない」という恒久的・明示的エラーを返し、プロンプト段落にもその旨を書く（最軽量・推奨）。
- (b) raw不在時に限り生バイトのみの再ダウンロードを許す（予算・SSRF経路の再考が必要、重量級）。

### R3（Medium-High）: Playwright HTML経路にサイズ上限チェックが無い

§1.4の擬似コードではPlaywright成功HTMLをそのまま`convert_stream`へ渡しており、現行がconvert前に
課している`len(raw) > _MAX_FETCH_BYTES`チェック（web_tools.py:468-471）が経路上に存在しない。
巨大SPA（数MB超のHTMLは珍しくない）でmarkitdownへの入力サイズが無制限になる。`len(html.encode
("utf-8"))`で同一上限を適用すること（§15.1: 同一ルールは同一箇所に）。

### R4（Medium）: HTTPステータスの扱いが経路間で非対称になる

現行は`resp.raise_for_status()`で4xx/5xxをエラー化するが、`page.goto()`は4xx/5xxでも例外を投げない。
Playwright既定パスでは404/500ページのHTMLが正常系としてMarkdown化されて返る。`response.status >= 400`
をフォールバック（→httpx経路がraiseして既存契約どおりエラー化）に含めるか、変更を意図的に受入れるか
を決め、テストに含めること。

## 2. 中程度の指摘

### R5: routeガードの非httpスキーム方針を明示せよ

`validate_url_for_fetch(request.url)`はhttp/https以外のスキーム（data:/blob:/about:/file:等）すべてで
`SsrfBlockedError`を送出する。つまり`route.abort()`が全非httpサブリソースに適用される。fail-closedと
しては正しいが、data: URI（インライン画像・フォント）はレンダリング結果の質を下げうる。方針として
「非http/httpsは一律abort（fail-closed）」と明記し、ガードのテストにdata:/file:ケースを足すこと
（file:はローカルファイル読み取りpotentialがあり、abortされることをテストで固定する価値がある）。

### R6: pdf_visionキャッシュの.md化がキャッシュ候補一覧に出現する

検証済み: read_reference_fileの候補列挙は`base_dir.glob("*.md")`（web_tools.py:750, 809）。生バイトの
.pdf/.xlsx兄弟は`*.md`でないため候補一覧を汚さない✅。ただしvisionキャッシュをwrite_cache互換の.mdと
してweb_cacheへ書く計画のため、**ページ描写キャッシュが候補一覧に現れる**。これは再読性の面で利点に
なりうるが、意図した動作として明記すること（候補一覧の肥大も許容するか）。なお兄弟.pdfを
read_reference_fileで読むとバイナリをutf-8テキストとして返す（文字化け）— path解決時に.md以外を
拒否するか、許容するかを決めること。

### R7: max_pdf_vision_callsの既定値は一元化せよ（§15.1）

既存に先例不整合がある: `config.get("max_web_fetch_calls", 30)`（cela_main.py:5767）と
`_DEFAULT_MAX_WEB_FETCH_CALLS = 20`（web_tools.py:92）が乖離している。新キー追加時に既定値は
1箇所に定義し、この際ついでに既存乖離の扱い（別BLでも可）を決めておくこと。

### R8: `io`の_ALLOWED_IMPORTS追加は「本当に必要か」を先に検証

§16.1（軽量代替の検討）: pandasは環境によっては`pd.read_excel(生bytes)`を直接受ける（内部でBytesIO
ラップ）。実装時にインストール版pandasで1行確認し、bytes直渡しが動くなら`io`追加は見送れる。
`io.open`は`ast.Attribute`の"open"検査（cela_main.py:584-586）で拒否されるため安全性の追加懸念は小さいが、
サンドボックス不変条件コメント（546-548）の更新は`io`を追加しない場合でもpandas分必要。

### R9: Vision出力の切り詰め規約

ハンドラの描写出力にも既存ツールと同系の上限（_MAX_OUTPUT_CHARS相当）を適用することを計画書に明記
（現状の§2.3擬似コードに無い）。

## 3. 軽微な指摘・確認事項

- **Playwright同期APIのスレッド拘束**: `sync_playwright()`は生成スレッド以外から使えない・asyncioループ
  内では例外。検証済み: cela_main.pyにasyncio/astream/ainvoke/to_threadは皆無（threading.ThreadはREPL
  readerの1箇所=696のみ）でツールループは逐次単一スレッドのため、モジュールレベルシングルトンは現行
  安全。ただしこれは**将来LangGraphをasync化した瞬間に壊れる暗黙前提**なので、`_ensure_browser`に
  [CONSTRAINT]コメントで明記すること（§1.1コメントに含める）。
- **UA**: 実ブラウザで`Mozilla/5.0 (compatible; CELA-research-bot/1.0)`（web_tools.py:75）を名乗ると
  bot対策ページに弾かれやすくなる。Playwright用にブラウザ風UAの別定数（_PLAYWRIGHT_USER_AGENT）を
  §7承認対象に加える価値がある。計画の自己レビュー所見3（応答差異の監視）と表裏の論点。
- **networkidle待機のコスト**: ポーリング続行ページでは毎URL `_PLAYWRIGHT_NETWORKIDLE_TIMEOUT_MS`
  が満額乗る。未キャッシュ100URL/runを想定すると積もるため、この定数は短め（2〜5秒級）を推奨。
  §7承認リストに入っているので値の目安として添えること。
- `_PAGES_RENDERED_SINCE_LAUNCH_INCREMENT()`は擬似コード上未定義（実装時の細部、問題なし）。
- 兄弟.pdf不在エラー時のカウンタ不消費は§2.3の設計（失敗時カウンタ据え置き）で自然に満たされる✅。
- requirements.txtのunpinned踏襲確認済み（上記0節）✅。

## 4. テスト方針への追加要請

計画のテスト方針は§17.1のrevert検証を含み概ね十分。以下を追加:

1. R1: リダイレクト挙動（採用した方針の固定テスト。http→httpsを追従する/しない）。
2. R2: .mdキャッシュヒット時に兄弟.pdfが生成されないこと／兄弟不在時のエラー文言（採用方針の固定）。
3. R3: 上限超HTMLでエラー化されること（現行httpx経路と同じ上限であること）。
4. R4: 4xx着地時の経路挙動。
5. R5: ガードがdata:/file:スキームをabortすること。

## 5. 総評

問題設定の証拠はすべて実在し、Phase分割・フォールバック条件の明確化（「短い≠失敗」）・§13を意識した
page_number検証・socket遮断の有効性をテストで初めて保証する位置づけ等、自己レビュー所見は的確。
R1（リダイレクト）とR2（rawキャッシュの出口欠落）は設計書に追記の上、ユーザー判断（R1の方針選択、
R2の(a)/(b)、R8のio要否、§7定数群、UA方針）を得てから実装着手すること。

