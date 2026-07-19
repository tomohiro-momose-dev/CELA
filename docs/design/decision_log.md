# 意思決定ログ（Decision Log）— FEATURE_NAME

**何を正とするか（Why）** を記録する。要件は [要件定義書_v35.md](要件定義書_v35.md)、実装タスクは [issue_backlog.md](issue_backlog.md)、進捗は [STATUS.md](STATUS.md)。

運用モデル: [README.md](README.md)

| 状態 | 意味 |
|------|------|
| `decided` | 決定済み。**決定理由の記載が必須** |
| `pending` | 未決定。決定時に `決定理由` を必ず記入 |
| `superseded` | より新しい決定に置き換え済み |

---

## 記録テンプレート（`decided` 時は全項目必須）

| 項目 | 必須 | 説明 |
|------|------|------|
| 日付 | ☑ | 決定日 |
| 決定者 | ☑ | 誰が決めたか |
| **決定理由** | **☑** | なぜこの選択か。代替案を却下した根拠。空欄不可 |
| 決定内容 | ☑ | 何を正とするか（1〜3文） |
| 影響 | ☑ | 変更が及ぶ範囲 |
| 関連 BL | — | あれば相互リンク |
| 参照 | — | 要件定義 / phase / レビュー等 |

> **原則: 理由なき決定は許されない。**

---

## 決定済み（decided）

### D-001: BL-002ドライランは30ターン完走を必須要件としない

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（ユーザー指示） |
| **決定理由** | `config["initial_max_turnval"]=30`は実装時に仮置きしたデフォルト値であり、設計書§5の指標B「30ターン後まで予算制約を忘却・破綻させない」という記述も、この仮のデフォルト値を踏襲しただけで、30という数字自体に根拠はない。BL-002/BL-003の本質的な完了条件は「list版とSQLite版で同一の呼び出し列に対して構造的一致（件数・topic集合・status分布・順序）が取れること」（impl_Plan §7.2）であり、これは何ターンで打ち切ってもagreements/decisionsが十分な件数取れていれば成立する。加えて、`turn_count`が`app.invoke()`内で凍結される既存挙動（[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)）により、外側ループ1回が内部で無制限に対話ラウンドを重ねうるため、「30外側ターン」は当初想定していたほど軽い目標ではないことも判明した。 |
| 決定内容 | ドライラン（BL-002）は`is_completed`/`halt`による自然終了、または`app.invoke()`の外側（次の「🔷 [Turn N]」表示直後）での意図的な打ち切りのいずれでも完了とみなす。途中終了する場合、`traceability.md`のT-*には「30ターン後まで」ではなく実際に到達したターン数を明記し、30が恣意的なデフォルト値だった旨も付記する。`app.invoke()`内部（差し戻しループの最中等）での強制終了は、fixtureが半端な状態で残りStep 4の構造比較を阻害するため避ける。 |
| 影響 | `phase1/phase1_dryrun.md`（Step 1〜Step 4の記述）、`traceability.md`の結果記録方法 |
| 関連 BL | [BL-002](issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施), [BL-003](issue_backlog.md#bl-003-recordreplayスタブの実llm応答による往復検証未実施), [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離) |
| 参照 | [cela_phase1_design_v7.md §5](phase1/cela_phase1_design_v7.md) |

---

### D-002: BL-002（指標A・B・Cの実測比較）はR2（F-2.6検算ゲート）実装後に実施する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（実機ドライランログの観測に基づく判断） |
| **決定理由** | list版ベースラインの実データドライラン（[traceability.md T-5](traceability.md)）のログで、`numerical_allocator`が提示するトリップ時間・処理能力・予算等の数値提案に対し、detectorが数値矛盾（major）を理由に何度も差し戻す事態が繰り返し観測された（例: 平均トリップ時間や処理能力の算出誤り、時間帯拡大に伴う処理能力の比例計算漏れ等）。これはLLMが暗算（機械的検算なしの算術）で数値提案を行っていることが原因であり、設計書付録A（[cela_phase1_design_v7.md §3.4](phase1/cela_phase1_design_v7.md)で引用「暗算は原理的に信頼できない」）で既に指摘されている既知の限界の実例である。この検算不能な状態のまま指標A（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ）を測定しても、「F-2.6検算ゲート（Python REPL、R2で実装）が無いことによる差し戻し」と「R1のSQLite永続化・Hydrate基盤自体の効果」が混在してしまい、R1固有の効果を正しく分離評価できない。なお設計書§0の対応表は元々§5評価メトリクスを「R1〜R3共通」と分類しており、R1単体での指標A・B・C完全測定を要求する設計ではなかった。 |
| 決定内容 | BL-002の指標A・B・Cの実測比較は、R2（F-2.6 Python REPL機械的検算ゲート）の実装完了後に実施する。R1単体では、既に確認済みの構造的一致（BL-003, T-5）をもってR1スコープの検証は完了とみなし、指標A・B・Cの本格測定はR2着手後のBLとして再設定する。 |
| 影響 | [issue_backlog.md BL-002](issue_backlog.md)の依存関係・状態、[phase_gates.md P1-4](phase_gates.md)（Phase1 Exit条件の再定義） |
| 関連 BL | BL-002 |
| 参照 | [cela_phase1_design_v7.md §0, §3.4, §5](phase1/cela_phase1_design_v7.md)、[traceability.md T-5](traceability.md) |

---

### D-003: BL-001（Agreement TypedDictのcontent/rationaleリネーム）はR2の頭で実施する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | BL-001・impl_Plan §9は「実施判断はR2着手前」と定めていたが、R2実装計画（cline作成）にはこの判断が反映されていなかった。BL-001の完了条件自体が既に「実施判断はR2着手前」と明記しているため、新たな論点はなく、既存の完了条件をそのまま実行に移す判断。 |
| 決定内容 | `Agreement` TypedDictの`content`/`rationale`キーを`decision_what`/`reason_why`に統一し、`db_append_agreement`/`get_agreements_from_db`のエイリアス変換コードを除去する作業を、R2実装の最初のステップとして行う。 |
| 影響 | `cela_main.py`（`Agreement` TypedDict、`db_append_agreement`、`get_agreements_from_db`、呼び出し側全箇所）、`cela_phase1_impl_Plan.md` R2部分 |
| 関連 BL | [BL-001](issue_backlog.md#bl-001-agreement-typeddictのcontentrationaleリネーム) |
| 参照 | [decision_lineage.md 論点2](decision_lineage.md) |

---

### D-004: ツール呼び出しループは既存の`try/except`リトライブロック内に配置する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（AIレビュー提案を採用） |
| **決定理由** | R2実装計画（cline作成）のツール呼び出しループ案は、既存`_query_AI_live`の`try/except`リトライ（`delays=[8,16,32,64,128]`）の外側・内側どちらに置くか未確定だった。外側に置くと、ツール呼び出し中の一時的なAPIエラー（レート制限等）で未捕捉例外が伝播しセッション全体がクラッシュする。ツール呼び出しはAPI往復回数が増える（最大5往復×5ノード）ため、この経路でのエラー発生率は非ツール時より高くなる。既存の他ノードと同じリトライ挙動に揃えることを優先し、内側配置を選んだ。 |
| 決定内容 | ツール呼び出しループ（R2.3）は、既存の`try/except`リトライブロックの内側で回す。これによりツールループ全体が1リトライ単位となり、失敗時は`loop_messages`の途中経過を破棄して最初からやり直す（粒度は粗いがMAX_TOOL_ITER=5・Python REPLはローカル実行のため実害は軽微と判断し許容）。 |
| 影響 | `cela_main.py` `_query_AI_live`（R2.3のツール呼び出しループ実装箇所） |
| 関連 BL | なし |
| 参照 | [decision_lineage.md 論点3](decision_lineage.md)、[cela_phase1_design_v7.md §3.5.2](phase1/cela_phase1_design_v7.md) |

---

### D-005: Detector/ReviewerのJSON判定パース失敗時は層2リトライ＋フェイルクローズとする

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（AIレビュー提案を採用） |
| **決定理由** | ツール付与により`use_json_mode=False`となるため、最終応答が安定してJSONパースできる保証が弱まる。既存`_safe_json_parse`は失敗時に例外を投げず`fallback`（Detectorは`{"constraint_issue": "none"}`）を黙って返す設計であり、これはF-2.6検算ゲート導入の目的（暗算を信用しない）と逆行するフェイルオープンである。JSONパース失敗は「正しく判定データが渡されなかった」ことと同義なので、既存のAPI呼び出し失敗リトライ（層1）とは別に、パース失敗を検知して呼び出しをやり直す層2リトライが必要と判断した。さらに、層2リトライを使い切った場合のfallbackを「none」のままにすると検算ゲートが機能しないのと同じになるため、安全側（major）に倒す。 |
| 決定内容 | Detector/Reviewer等のツール付与ノードにおいて、`_safe_json_parse`が`fallback`相当を返した場合はパース失敗とみなし、ノード呼び出し自体を再試行する層2リトライ（既存の層1＝API呼び出し失敗リトライとは独立）を追加する。層2リトライの上限を使い切った場合のfallbackは、現状の「none」ではなく「major」側に倒す（フェイルクローズ）。 |
| 影響 | `cela_main.py` `call_detector`、`call_reviewer`ほかツール付与ノードの判定パース処理 |
| 関連 BL | なし |
| 参照 | [decision_lineage.md 論点4](decision_lineage.md)、[cela_main.py:1159](../../cela_main.py) |

---

### D-006: Python REPLサンドボックスはビルトイン呼び出しのAST検査＋多層防御を追加する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（AIレビュー提案を採用） |
| **決定理由** | R2実装計画（cline作成）のAST検査は`ast.Import`/`ast.ImportFrom`ノードのみを対象としており、`open(...)`（ビルトイン、import不要）や`__import__('os')`（Callノードでimport文ではない）を素通りさせる。design v7 §3.5.3が求める「os/sys/subprocess等のI/O・システム制御系モジュールのブロック」を実質的に満たしておらず、サンドボックスエスケープが可能な状態だった。加えて、AST blacklistだけでは`().__class__.__bases__`経由等の既知の回避手法を完全には防げないため、単一の対策に依存せず多層防御とする必要がある。 |
| 決定内容 | `_run_python_repl`のAST検査に、`open`/`eval`/`exec`/`compile`/`__import__`/`globals`/`vars`/`getattr`等の危険な名前への`Name`/`Attribute`参照（呼び出し式全体）を検査対象として追加する。加えて、実行プロセス自体の権限を絞る対策（書き込み不可の作業ディレクトリ、可能なら低権限実行）を多層防御として併用し、「絶対に破れないサンドボックスではなく多層防御である」旨を設計上の限界としてdesign文書に明記する。 |
| 影響 | `cela_main.py` `_run_python_repl`、`cela_phase1_design_v7.md` §3.5.3 |
| 関連 BL | なし |
| 参照 | [decision_lineage.md 論点5](decision_lineage.md) |

---

### D-007: Python REPL許可モジュールから`random`を除去し、`decimal`/`fractions`は理由付きで維持する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（AIレビュー提案を採用） |
| **決定理由** | R2実装計画（cline作成）の`_ALLOWED_IMPORTS`は、design v7 §3.5.3の許可リスト（`math, statistics, datetime, json`）を超えて`fractions, decimal, random`を追加しており、AGENTS.md §7（定数変更の厳格管理）上、未承認の逸脱だった。`random`はセキュリティリスクではなく、検算コードに混入すると同じコードでも実行のたびに結果が変わりうるため、F-2.6が目的とする「機械的検算の決定性」自体を損なうリスクがある。`decimal`/`fractions`は浮動小数点誤差を避けた正確な検算という目的に合致するため、理由を明記した上で維持する。 |
| 決定内容 | `_ALLOWED_IMPORTS`から`random`を削除する。`decimal`/`fractions`は許可モジュールとして維持し、design v7 §3.5.3の許可リストにも理由付きで追記する（AGENTS.md §7準拠の承認済み変更として扱う）。 |
| 影響 | `cela_main.py` `_ALLOWED_IMPORTS`、`cela_phase1_design_v7.md` §3.5.3 |
| 関連 BL | なし |
| 参照 | [decision_lineage.md 論点6](decision_lineage.md) |

---

### D-008: R2.0.1（ツール呼び出しループを`query_AI`に集約する設計）を承認

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | R2実装計画（cline作成）はdesign v7 §3.5.2の`call_expert_with_tools`例（ノードごとの個別ループ）から逸脱し、ツール呼び出しループを共通層`query_AI`に集約する方式（R2.0.1）を採っていた。この逸脱の妥当性を、Anthropic公式SDKの`tool_runner`、OpenAI Agents SDKの`Runner`、LangChainの`AgentExecutor`等、業界で主流の実装パターンと照合した結果、いずれも同様の集約方式であり、design v7 §3.5.2のノード別実装例はあくまで説明用の最小サンプルに過ぎないと判断できたため、現行案のまま採用する。 |
| 決定内容 | ツール呼び出しループの実装はR2.0.1（`query_AI`への集約）の内容のまま採用する。大きな設計変更は行わない。任意の改善として、ツールのdispatch（ツール名→処理のマッピング）をループ本体から分離し辞書化しておくことを推奨する（R3の`write_agreement_tool`追加時にループ本体を変更せずに済むため）。 |
| 影響 | `cela_main.py` `query_AI`（ツールdispatch部分、任意改善） |
| 関連 BL | なし |
| 参照 | [decision_lineage.md 論点7](decision_lineage.md)、[cela_phase1_design_v7.md §3.5.2](phase1/cela_phase1_design_v7.md) |

---

### D-009: R2ツールループの例外処理を「一時的API障害」と「ロジックエラー」に区別する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（別チャットClaudeの指摘を確認の上、提案どおり採用） |
| **決定理由** | D-004でツールループを既存`try/except`（`except Exception as e:`、`cela_main.py:399-405`）の内側に配置したが、この例外節は「一時的なAPI障害」と「ロジックエラー」を区別しない。具体的には、(1) LLMが返す壊れたtool_call引数JSON（`json.loads(tc.function.arguments)`の失敗）と、(2) `MAX_TOOL_ITER`超過による非収束`RuntimeError`が、いずれも指数バックオフ（最大約248秒）を経た末に`"(サーバー高負荷によるAPIエラー)"`という誤った診断メッセージへ丸められ、原因調査を著しく妨げる。さらに、既存の非ツールパス（`cela_main.py:394-396`）が持つ`finish_reason == "length"`（出力打ち切り）検出が新設のツールループには存在せず、`max_tokens`超過によるtool_call引数の途中切れが「壊れたJSON引数」として(1)の経路に混入し、真因（トークン予算不足）が隠蔽される。 |
| 決定内容 | 以下3点を実装する。(a) `tc.function.arguments`の`json.loads`失敗は`json.JSONDecodeError`を個別に捕捉し、例外として上位に投げず`{"role": "tool", "tool_call_id": tc.id, "content": json.dumps({"error": ...})}`としてモデルに返し、モデル自身に次イテレーションで引数を自己修正させる。(b) 外側`except Exception as e:`を`except (APIError, APIConnectionError, RateLimitError, APITimeoutError) as e:`（`openai`パッケージのAPI関連例外のみ）に狭め、`RuntimeError`・`json.JSONDecodeError`・`ValueError`等のロジックエラーはバックオフ無しでそのまま伝播させる。(c) ツールループ内、`tool_calls`の有無を判定する直前に、既存非ツールパスと同じ`if choice.finish_reason == "length": raise ValueError(...)`を追加する。 |
| 影響 | `cela_main.py` `_query_AI_live`（R2.3のツール呼び出しループ実装箇所、`import`文への`APIError`等の追加） |
| 関連 BL | [BL-010](issue_backlog.md)（新規） |
| 参照 | [decision_lineage.md 論点9](decision_lineage.md)、[cela_main.py:394-405](../../cela_main.py) |

---

### D-010: プロバイダ別Function Calling対応の網羅検証はMVP段階では見送り、BLに留める

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 要件定義書v35 付録B.5.3は「Function Calling/Tool Use導入時はプロバイダごとの対応状況を事前確認する」ことを求めており、現状`_query_AI_live`はOpenRouter経由で複数の実バックエンド（`extra_body.provider.order=["baidu/fp8","siliconflow/fp8","wandb/fp8","morph"]`、`cela_main.py:383-390`）へ強制ルーティングしているため、各バックエンドがOpenAI互換の`tools`/`tool_calls`スキーマをどこまで安定サポートするかは未検証というAGENTS.mdルール2（外部API使用前のContext7確認）該当の指摘があった。ただし現時点は複数バックエンドを個別に検証しきる工数をかけるフェーズではないMVP実装であり、指標D（5/5検出）が特定プロバイダに偶然当たっただけで通過するリスクを許容してでも実装を先に進める方を優先する。 |
| 決定内容 | R2着手前に「provider.orderの各バックエンドでtool callingが機能するかの事前検証」ステップは追加しない。このリスクはBLとして明示的に記録し、可視化のみ行う。本格的な網羅検証はMVP後（Phase 2以降）に先送りする。 |
| 影響 | `cela_phase1_impl_Plan.md` R2章（検証ステップの追加は行わない） |
| 関連 BL | [BL-011](issue_backlog.md)（新規） |
| 参照 | [decision_lineage.md 論点10](decision_lineage.md)、要件定義書v35 付録B.5.3 |

---

### D-011: B.5.1既知誤判定（Detectorの偽陽性）の非退行テストを指標Dと対で追加する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（別チャットClaudeの指摘を確認の上、提案どおり採用） |
| **決定理由** | R2.6は付録B.5.1で既知の誤判定（上限内の数値差をDetectorが`major`と誤判定するバグ）を修正するプロンプトを復活させるが、R2.9の完了条件（指標D）は「矛盾を仕込んだケースを5/5検出できること」という陽性検出のみを定義しており、「上限内の正当な数値差を誤って`major`と判定しない」という陰性側（偽陽性回避）の非退行テストが計画・`phase1_dryrun.md`のいずれにも存在しない。R2.5で追加する「数値主張は必ず`python_repl`で再計算してから`major`と判定する」指示と、R2.6の「上限内の数値差は矛盾と見なさない」指示は将来調整され得るため、どちらかの文言変更でB.5.1のバグが再発しても、指標Dのテストのみでは検知できない。 |
| 決定内容 | `test_f26_detection.py`に、上限内の正当な数値差（予算超過していない）を仕込んだ成果物のテストケースを追加し、「`none`または`minor`と判定され`major`にならないこと」を検証する非退行テストを実装する。R2.9の完了条件表に指標Dと対になる基準（B.5.1既知誤判定の非退行）として明記し、R2.10のテスト格納先にも追記する。 |
| 影響 | `cela_phase1_impl_Plan.md` R2.9・R2.10、`tests/test_f26_detection.py`（新規テストケース） |
| 関連 BL | [BL-012](issue_backlog.md)（新規） |
| 参照 | [decision_lineage.md 論点11](decision_lineage.md)、impl_Plan R2.6・R2.9・R2.10 |

---

### D-012: `manage_adr`（Codebase Memory MCP）の採用は見送る

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | Gemini調査では「D-xxxごとに個別レコードとして登録・検索できる」という想定だったが、実機検証（D-001〜D-011を登録）の結果、`manage_adr`はプロジェクトにつき1つの固定6セクション文書（PURPOSE/STACK/ARCHITECTURE/PATTERNS/TRADEOFFS/PHILOSOPHY）を丸ごと読み書きする方式であり、D-xxx単位のID管理・`search_graph`等からの全文検索は不可能（実際に`search_graph`で検索してもADR内容はヒットせず、コードグラフ側の結果のみ返った）と判明した。個別決定の一覧が出たところで結局`decision_log.md`本体を読みに行くことになり、二重管理のコストに見合わない。 |
| 決定内容 | `manage_adr`は採用せず、`decision_log.md`/`decision_lineage.md`（markdown、git管理）のみを意思決定の正とする運用を継続する。 |
| 影響 | ドキュメント運用（`docs/design`のみが正のまま維持、MCP側への二重登録は行わない） |
| 関連 BL | なし |
| 参照 | 本セッションでの`manage_adr`実地検証（登録・`get`・`sections`・`search_graph`照合） |

---

### D-013: `docs/design`の相互リンク整合性を検証する静的リンタを新設する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | D-xxx/BL-xxxの相互リンクが増えるにつれ手動での整合維持が困難になり（`manage_adr`不採用の理由もこれと同根、D-012）、実際に本セッション中の作業だけでもリンク切れ・表と詳細セクションの不一致が複数発生していた。JiraのようなPMツール導入は「`docs/design`が正」という既存方針と衝突するため見送り、リポジトリ内で完結する軽量な静的チェックスクリプトを追加する方針とした。 |
| 決定内容 | `scripts/check_docs_consistency.py`を新設。(1) `docs/design`内のmarkdownリンクの参照先ファイル存在確認、(2) リンクのアンカーがGitHub方式の見出しスラッグと一致するかの確認、(3) `decision_log.md`で`decided`なのに決定理由が空のエントリ検出、(4) `issue_backlog.md`の優先対応一覧表とBL-xxx詳細セクションの1:1対応確認、の4点をチェックする。初回実行で18件の不整合（本セッションのリンクミス、BL-006〜009の表反映漏れ、テンプレート由来の`要件定義.md`/`cela_roadmap_vXX.md`未置換リンク8箇所）を検出し、すべて修正済み。 |
| 影響 | 新規 `scripts/check_docs_consistency.py`。`decision_lineage.md`・`decision_log.md`・`issue_backlog.md`・`README.md`・`phase_gates.md`・`rollout_plan.md`・`traceability.md`・`phase0/README.md`・`phase1/README.md`のリンク修正 |
| 関連 BL | なし（CI/pre-commit組み込みは任意の将来対応） |
| 参照 | [decision_lineage.md 論点13](decision_lineage.md) |

---

### D-014: `MAX_TOOL_ITER`を5から10へ引き上げる（暫定、挙動を見て調整）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 実機ドライラン（Expert:cost_optimizerノード）で、`MAX_TOOL_ITER=5`全回が`tool_calls`を返し、最終テキスト回答を送る余地が残らないまま非収束の`RuntimeError`で本番クラッシュした。原因の大半はBL-014で特定した別バグ（python_replがセッション状態を保持せず`NameError`が発生／絵文字printでの`UnicodeEncodeError`）による無駄撃ちだが、それらを修正してもなお「5回とも検算に使うと最終回答の余地がゼロになる」という設計自体の余裕のなさは残る。Expertのような探索的に複数回検算したいノードには、Detector/Reviewerの単純検算より多めの往復予算が必要と判断した。 |
| 決定内容 | `_query_AI_live`の`MAX_TOOL_ITER`を5から10に引き上げる。恒久値ではなく、B・C（BL-014のバグ修正）適用後の実機ドライランでの挙動を見て、過大であれば絞る前提の暫定値とする。 |
| 影響 | `cela_main.py` `_query_AI_live`（ツール呼び出しループの往復上限） |
| 関連 BL | [BL-014](issue_backlog.md)（新規） |
| 参照 | 実機ドライランログ（Expert:cost_optimizer、非収束クラッシュ、2026-07-19） |

---

### D-015: `python_repl`を対話的（状態保持）セッションに変更する（BL-014原因A）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `_run_python_repl`は呼び出しごとに独立プロセスを起動する設計だったため、本番ドライランでExpertが前回呼び出しで定義した変数を次の呼び出しで参照して`NameError`となり、非収束クラッシュの一因となった（BL-014原因A）。対応案として「ツール説明文で状態非保持を明記する」（実装コスト小）と「対話的永続プロセス化」（実装コスト大）の2案があったが、ユーザーは「エージェントAIは一発で多角的に検証できるようpythonコードを書いており、この書き方を活かしたい。単発呼び出し方式では、前回の計算結果をモデルが自分のテキスト記憶に頼って次の計算に転記することになり、これはF-2.6が排除しようとしていた『暗算・記憶によるヒューマンエラー』と同種のリスクを残す。無駄な思考ループも避けたい」という理由で、実装コストが増えても対話型セッション化を選ぶべきと判断した。AIもこれに同意：単発方式は「値をモデルが覚えて転記する」経路を残す点でF-2.6の思想（LLMの記憶を信用せず機械的に検算する）と整合しない。 |
| 決定内容 | `_run_python_repl`のAST安全検査を`_check_repl_code_safety`として共通化し、新規クラス`_PythonReplSession`（`subprocess.Popen`による遅延起動、stdin/stdoutのJSON行＋センチネル区切りプロトコル、タイムアウト時のセッションリセット＋明示的エラーメッセージ、`try/finally`によるプロセス確実終了）を追加。状態は1回のツールループ（1回の`_query_AI_live`呼び出し）内でのみ保持し、ノード・リトライをまたいでは共有しない。AST安全検査は状態保持後も送信コードごとに毎回実施する。既存の`_run_python_repl`（ステートレス版）は単体テスト・将来の単発検算用途向けに維持。 |
| 影響 | `cela_main.py` `_run_python_repl`、`_check_repl_code_safety`（新規）、`_PythonReplSession`（新規）、`_query_AI_live`のツールループ、`PYTHON_REPL_TOOL`の説明文 |
| 関連 BL | [BL-014](issue_backlog.md) |
| 参照 | [decision_lineage.md 論点14](decision_lineage.md)、本番ドライランログ（Expert:cost_optimizer、2026-07-19） |

---

### D-016: BL-016（探索的タスクでの10回ツール呼び出し非収束）へ2点の対応を実施する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 本番ドライランで、Expertが車両配車の組合せ最適化という探索的タスクに取り組み、iter=9で実質的に妥当な結論に達していたにもかかわらずiter=10で不要な再検算を行い、テキスト最終回答の余地がゼロのままMAX_TOOL_ITER=10で非収束クラッシュした（BL-016）。ログ解析の結果、原因は(1)モデルが残りツール呼び出し可能回数を知らないため引き際を判断できないこと、(2)Detectorの完了度判定が「ユーザーの指摘全点に一度で完全に応える」という二値判定しかなく、「部分的に妥当な結論＋明示的な申し送り」を受理する経路がないこと、の2点と特定した。数値検算そのものの厳格さ（F-2.6ゲート）はBL-016の原因ではなく引き続き必要なため、これは変更しない。 |
| 決定内容 | (1) `_query_AI_live`のツールループで、残りイテレーション数が2以下になった時点（`remaining_iters <= 2`）で`[SYSTEM NOTICE]`という残り回数の明示メッセージを`loop_messages`に注入し、次の応答で打ち切るよう促す。(2) `call_detector`のAgent評価用プロンプトに、「未対応項目が残っていても、何が未着手かを具体的に名指しした上で次のステップとして明示している場合はそれだけでは major にせず minor とする」という明示的な例外規定を追加する。数値矛盾・計算ミスの検算に関する要求（F-2.6ゲート、python_repl必須）は変更しない。 |
| 影響 | `cela_main.py` `_query_AI_live`のツールループ（残りiter通知の注入）、`call_detector`のAgent評価分岐（L1427〜）と共通major定義（L1452〜） |
| 関連 BL | [BL-016](issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする) |
| 参照 | [decision_lineage.md 論点16](decision_lineage.md)、本番ドライランログ`log/2026-07-19/1012/log_no_prompt.md`（Expert:requirement_engineer、2026-07-19） |

---

### D-017: OpenRouterのreasoningパラメータ形式を修正し、ツール付与ノードにも思考ログを追加する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーから「ログに自己会話のつぶやきを出したい」という要望があり調査したところ、`query_AI`/`_query_AI_live`がOpenRouterへ送っていた`create_kwargs["reasoning_effort"] = "low"/"medium"`はOpenRouter公式ドキュメント（ネスト形式`reasoning: {"effort": ...}`が正）に照らして無効なキーであることが判明。実機検証（`deepseek-v4-flash`）で、旧形式では`message.reasoning`が常に`null`、正しい形式では実際の思考テキストが返ることを確認した。つまりDetector/decision extractor/Reflection/Reviewのreasoning_effort設定はこれまで一切効果を発揮していなかった。加えて、ツール呼び出し前後の「なぜこのツールを呼ぶか」「結果をどう解釈したか」という思考は`message.content`ではなく`message.reasoning`に現れることも実機確認したため、ツール付与ノード（Expert/User AI/Resource Arbiter等）にもこれを付与しログ出力する方が、ユーザーが要望した「ツールループ中のつぶやきの可視化」に直接応える。 |
| 決定内容 | `query_AI`/`_query_AI_live`の`reasoning_effort`設定をネストした`extra_body["reasoning"]["effort"]`形式に修正（OpenRouter利用時のみ、既存のプロバイダ優先順位指定と同じ`extra_body`にマージ）。対象ノードをDetector/decision extractor（low）、Reflection/Review（medium、従来通り）に加え、ツールが付与されている全ノード（Expert/User AI/Resource Arbiter等、low）に拡張。非ツールパス・ツールループパスの両方で、レスポンスの`reasoning`フィールドが非空の場合に`💭 [{label}] 思考:`としてログ出力する。 |
| 影響 | `cela_main.py` `query_AI`/`_query_AI_live`のreasoning_effort決定ロジックとextra_body構築、非ツールパス・ツールループパスの思考ログ出力 |
| 関連 BL | [BL-019](issue_backlog.md#bl-019-openrouterのreasoningパラメータが無効な形式で送られており一切発火していなかった) |
| 参照 | [decision_lineage.md 論点18](decision_lineage.md)、[OpenRouter Reasoning Tokens公式ドキュメント](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens) |

---

### D-018: R4ホワイトボード編集方式は、コーディングエージェント方式（遅延取得＋機械的照合パッチ）を採用する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | R4設計書（`cela_phase2_design_R4.md`）現行案の`{whiteboard_content}`全文注入＋LLM自己申告差分方式は、出力トークンは削減できるが、入力側のスコープやLLMの内部推論範囲は制御できないという指摘があった（ユーザー提起）。AIが自身（Claude Code）の構造を説明：ファイルは自動でコンテキストに入らず、Grep（検索）→Read（該当範囲のみ取得）→Edit（`old_string`が実ファイル内容と完全一致することを要求される機械的パッチ）という経路でのみ情報が入る。この方式は「総読了量」で劇的に勝るとは限らないが、(a) 変更規模に応じた遅延的・選択的取得と、(b) 差分の正しさが自己申告ではなく機械的な完全一致照合で検証される点で、安全性・品質の面でLLM自己申告方式より優れる。ユーザーはこれを安全性・品質の観点から採用すると決定した。 |
| 決定内容 | R4（ホワイトボード差分パッチ化）が実際に着手される際、Expertに`whiteboard_content`を無条件に全文注入する現行案ではなく、セクション単位で検索・取得するツール（Grep/Read相当）を持たせ、パッチ適用も「旧内容が完全一致することを条件に差し替える」機械的照合を伴う方式（Edit相当）を採用する方針とする。R4設計書自体の改訂はR4着手時に行う（現時点では方針決定のみ）。 |
| 影響 | `cela_phase2_design_R4.md`（将来の改訂対象、未着手）、BL-005・BL-017（R4着手時に合わせて対応する既存の関連Issue） |
| 関連 BL | [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)、[BL-017](issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り) |
| 参照 | [decision_lineage.md 論点19](decision_lineage.md)、[decision_lineage.md 論点20](decision_lineage.md) |

---

## 未決定（pending）

### D-00N: （題名）

| 項目 | 内容 |
|------|------|
| 状態 | `pending` |
| 論点 | （記入） |
| 候補 | A. … / B. … |
| **決定理由** | **（決定時に必須）** |
| 決定内容 | **（未記入）** |

---

## 決定の記録ルール

1. 新しい決定は **D-xxx を追記**（連番）
2. `decided` にするには **`決定理由` 必須**
3. 過去決定を覆す場合は旧エントリを `superseded` にし、新 D-xxx の理由に変更理由を書く
4. backlog の「未確定」系は決定後に BL を `done` へ更新し相互リンク
5. 要件に影響する決定は **本ログと `要件定義.md`（必要なら `phase*/`）を更新**

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-07-18 | D-007・D-008 の「design v7 §3.5.3 / §3.5.2 への反映（追記予定）」を実行。§3.5.2 に query_AI 集約方針の ★v9 追記、§3.5.3 に random 除外・decimal/fractions 維持・危険呼び出し AST 検査・多層防御の ★v9 追記を実施。issue_backlog.md に BL-006〜BL-009 を新規起票し相互リンク。 |
