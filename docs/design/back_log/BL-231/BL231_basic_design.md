# BL-231 実装計画: Detector ノードの生成崩壊ループ（検知・停止ガード）

## Context（なぜこの変更を行うか）

2026-08-14 の実ドライラン（run_id `1786699546-9ac0105d`、`log/2026-08-14/1945/log_no_prompt.md`）で、
Detector ノードが User 発言（task_1_1 承認＋task_1_2 指示）を監査する推論ブロックを**逐語的に
40 回**繰り返し、グラフが収束せず無限ループに陥った（ユーザーが停止指示）。実ツール実行は 1 セット
のみ（`read_issues`×1, `read_verified_fact`×3, `python_repl`×1, `trace_lineage`×0）であり、
40 回の繰り返しは実ツール再実行ではなく**モデルが同一テキストを生成し続けた「生成崩壊
（repetition degeneracy）」**である（§14 に基づく実ログ grep で実証済み）。

### 根本原因（§14 に基づくコード実証）

`_query_AI_live` のツールループは `for iteration in range(1, MAX_TOOL_ITER + 1)`（`MAX_TOOL_ITER=50`、
`cela_main.py:5079`）で、モデルが `tool_calls` を返し続ける限りループし、`tool_calls` が無くなった
時点で `return content` して正常終了する（`cela_main.py:5185-5202`）。今回の崩壊は、モデルが
「同一テキスト（`Let me do these calls.`）＋同一ツール呼び出し計画」を繰り返し返し続けたため、
`MAX_TOOL_ITER` に達するまで 50 往復 burn するか、ユーザーが 40 回目で停止するまで収束しなかった。

既存の反復関連ガードはいずれも「ツールループ非収束」しか見ており、**テキスト退化**を捉えられない：
- BL-016（残り回数通知）／BL-060（最終 iter で tools 除外）／BL-089（「同じ検証を繰り返さない」プロンプト注入）
  → いずれも予防・通知に留まり、同一出力の「機械的検知」は行わない。
- BL-202（`_MAX_NODE_REDO_ON_API_EXHAUSTION=2`）→ API 全滅時のノードやり直し上限であり、生成崩壊とは無関係。

### 本設計のゴール

モデルが同一出力を繰り返す生成崩壊を**機械的に検知**し、`MAX_TOOL_ITER` まで burn する前に
ツールループを強制終了する。検知はモデルの自己申告（プロンプト遵守）ではなくコード側で行う
（AGENTS.md §15.3「機械的検証をエージェントの自己申告より優先する」）。

---

## 設計決定（未決事項の解決）

起票時の未決事項 4 点について、以下の通り決定する。

### ① 検知方式 — 結合ハッシュのスライド窓

各 iteration の「正規化テキスト ＋ ツール呼び出し計画署名」の結合ハッシュを、直近
`WINDOW` 件のスライド窓で保持する。連続 `WINDOW` 回同一なら崩壊と判定。

- **正規化テキスト**: `re.sub(r"\s+", " ", (text or "").strip())`。不可視文字の微小な揺らぎに
  強くするためホワイトスペースを正規化する（実害は「1文字も違わず」の逐語一致だったため、
  厳密一致で十分に捕捉できるが、安全側に寄せる）。
- **ツール呼び出し計画署名**: `[(name, json.dumps(args, sort_keys=True)), ...]` をソートした
  リストのハッシュ（`json.loads` 失敗時は生引数を `_raw` に入れて同型処理）。ツールが無い場合は空文字。
- **結合**: `正規化テキスト + "␟" + 計画署名` を `hashlib.md5` でハッシュ。
- **MIN_CHARS は採用しない**。理由: ループするためには `tool_calls` が毎 iteration 存在（＝計画が
  非空）しなければならず、退化状態は「content と plan が同一」で表れる。短い定型句
  （`Let me do these calls.` 自体は 22 文字）だけではループしないため、別途長さ閾値を設ける必要が無い。
  これは「対象が短いテキストなら誤って検知しないか」という懸念への答えにもなっている：短いテキストで
  ループするには plan が同一でなければならず、結合署名で捉えられる。

### ② 停止／復旧 — 強制終了＋返却＋可視化

ガード発動時は `raise RuntimeError`（非収束）**ではなく** `return content`（最後の出力テキスト）して
ツールループを強制終了する。これで以下を同時に達成する：
- (a) `MAX_TOOL_ITER=50` 往復のトークン burn を回避（WINDOW=3 で 3 往復目に停止）。
- (b) 非収束 `RuntimeError` による出力消失を回避（下流へ最後の content を渡す）。
- (c) グラフは収束して進行する（call_detector → `_safe_json_parse` が非 JSON を安全に処理）。

大音声警告を `print` し、グローバル `_LAST_REPETITION_GUARD_TRIPPED`（dict: `label` / `iteration` /
`run_id` / `last_output_head`（冒頭 120 字））をセットして可観測性を確保する。content が空の場合は
ガード専用メッセージ（`"(BL-231ループガード: 生成崩壊を検知して強制終了しましたが、有効な出力がありませんでした)"`）
を返す。

**人間へのエスカレーションは今回実装しない。** オーケストレータ側の停止／巻き戻し配線は別課題
（BL-017 の差し戻し沼脱出機構とも性質が異なる）であり、本 BL のスコープ外とする。フラグによる
可視化のみとし、将来拡張候補として `issue_backlog.md` に据え置く。

### ③ 対象ノード — 共有ループ内に実装（Detector 発端・全ノード共通）

ガードは `_query_AI_live` のツールループ内（全ツールノードの収束点）に置く。これは AGENTS.md §15.1
「単一ソース」に従い、Detector 以外の全ツールノード（Expert / User AI / Resource Arbiter / Integrator 等）
も同型の崩壊から保護する。BL-231 は「Detector 監査ノードで発見された」事象だが、根本原因は共有ループ
にあるため、Detector 専用パッチにするのは §15.1 違反（再 Fragment 化）である。

### ④ 実装タイミング

ユーザー指示「BL-231に取り掛かる」（2026-08-14）により、本 BL の `in_progress` 化と実装を開始する。

---

## 新規定数（AGENTS.md §7 承認要）

| 定数 | 値（提案） | 理由 |
|------|-----------|------|
| `_LOOP_GUARD_REPETITION_WINDOW` | `3` | 連続して同一結合署名が何回出たら崩壊とみなすか。実害は 40 回連続のため、3 で十分早期停止できる。2 だと「計画を再掲してから進展」する正常パターンを誤検知する恐れがあるため 3 とする。 |

上記 1 件。`MIN_CHARS` は採用せず（②参照）。定数の追加・変更は §7 によりユーザーの明示的文書承認が
必要。実装時は提案値を一旦適用し、承認を得てから確定とする（承認前は warning 扱い）。

---

## 変更対象ファイル

- `cela_main.py`:
  - モジュールレベル: `_LAST_REPETITION_GUARD_TRIPPED = None` を `_LAST_*` グローバル群へ追加
    （`query_AI` の reset ブロック `cela_main.py:4748-4758` へ追加・初期化）。
  - 関数 `_bl231_norm_text(text)` ／ `_bl231_plan_sig(tool_calls)` ／ `_bl231_combined_hash(msg)`
    を新設（ヘルパ、純関数）。
  - `_query_AI_live` 冒頭: `_recent_combined_hashes: list[str] = []` を `loop_messages` と同様に
    API エラーリトライ（`while True`）の外側で初期化（§15.4 の「状態の保持」パターン、BL-122 準拠）。
  - `_query_AI_live` ツールループ内: `msg` 構築直後（`cela_main.py:5183` 直後）、`tool_calls` 有無の
    分岐前に結合ハッシュ更新＋崩壊判定を挿入。発動時は警告 print ＋ `_LAST_REPETITION_GUARD_TRIPPED`
    セット＋ `return content`。
  - 定数ブロック: `_LOOP_GUARD_REPETITION_WINDOW = 3`（§7 注釈付き）。
- `tests/test_bl231_loop_guard.py`（新規）: §17.1 に準拠。
- `docs/design/back_log/issue_backlog.md`: BL-231 状態 `open` → `in_progress`、設計書リンク追加、
  未決事項 4 点の解決を記録。

---

## テスト（§17.1: リバートで失敗する回帰テスト）

`tests/test_bl231_loop_guard.py` は実 LLM を呼ばず、モック OpenAI クライアント（ストリーミング互換）
で `_query_AI_live` を駆動する。

- **モック戦略**: `client.chat.completions.create` が、各 iteration で同一の `content`（短い定型句）＋
  同一の `tool_calls`（**TOOL_DISPATCH に存在しない未知ツール名** `loop_guard_test_tool`）をストリーミング
  チャンクで返す fake を実装。未知ツール名を使うことで、実 DB／実ツールハンドラ（`read_issues` 等）の
  実行を回避しつつ、`tool_calls` が存在するためループが継続する状況を再現する。
- **正例（ガード発動）**: `_query_AI_live(tools=[...], label="detector", ...)` を呼び、
  1. `RuntimeError` を上げずに `return` すること、
  2. `client.create` の呼び出し回数が `WINDOW`（=3）であること（50 往復せず早期停止）、
  3. 返却値が最後の content（退化テキスト）であること、
  4. `_LAST_REPETITION_GUARD_TRIPPED` がセットされ `label=="detector"` を含むこと、
  を検証。
- **負例（誤検知なし）**: 1 iter 目と 2 iter 目で `content`／`tool_calls` が異なり、3 iter 目で
  `tool_calls` なし（正常終了）となる fake を用い、ガードが発動せず `_LAST_REPETITION_GUARD_TRIPPED`
  が `None` のままであることを検証（正常な 2 往復ループを誤検知しないことを確認）。
- **存在証明（§17.1 後段）**: `_query_AI_live` の `inspect.getsource` が
  `_LAST_REPETITION_GUARD_TRIPPED` と `_bl231_combined_hash` を含むことを表明。実装を削除しても
  テストが落ちることを保証する。

---

## 検証

- `python -m py_compile cela_main.py`
- `python -m pytest tests/test_bl231_loop_guard.py -q`
- フルオフラインスイート（§17.3）の該当部分を通す。
- 実 LLM 再ドライラン（AGENTS.md §17.2）は BL-224 Phase 2 の検証と併せて実施し、同一 run で
  (a) ガードが発動しない通常收束、(b) もし退化が再発すれば WINDOW=3 で早期停止することを確認。
