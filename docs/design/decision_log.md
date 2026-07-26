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
| 参照 | [cela_phase1_design_v7.md §5](r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md) |

---

### D-002: BL-002（指標A・B・Cの実測比較）はR2（F-2.6検算ゲート）実装後に実施する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-18 |
| 状態 | `decided` |
| 決定者 | t-momose（実機ドライランログの観測に基づく判断） |
| **決定理由** | list版ベースラインの実データドライラン（[traceability.md T-5](traceability.md)）のログで、`numerical_allocator`が提示するトリップ時間・処理能力・予算等の数値提案に対し、detectorが数値矛盾（major）を理由に何度も差し戻す事態が繰り返し観測された（例: 平均トリップ時間や処理能力の算出誤り、時間帯拡大に伴う処理能力の比例計算漏れ等）。これはLLMが暗算（機械的検算なしの算術）で数値提案を行っていることが原因であり、設計書付録A（[cela_phase1_design_v7.md §3.4](r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md)で引用「暗算は原理的に信頼できない」）で既に指摘されている既知の限界の実例である。この検算不能な状態のまま指標A（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ）を測定しても、「F-2.6検算ゲート（Python REPL、R2で実装）が無いことによる差し戻し」と「R1のSQLite永続化・Hydrate基盤自体の効果」が混在してしまい、R1固有の効果を正しく分離評価できない。なお設計書§0の対応表は元々§5評価メトリクスを「R1〜R3共通」と分類しており、R1単体での指標A・B・C完全測定を要求する設計ではなかった。 |
| 決定内容 | BL-002の指標A・B・Cの実測比較は、R2（F-2.6 Python REPL機械的検算ゲート）の実装完了後に実施する。R1単体では、既に確認済みの構造的一致（BL-003, T-5）をもってR1スコープの検証は完了とみなし、指標A・B・Cの本格測定はR2着手後のBLとして再設定する。 |
| 影響 | [issue_backlog.md BL-002](issue_backlog.md)の依存関係・状態、[phase_gates.md P1-4](phase_gates.md)（Phase1 Exit条件の再定義） |
| 関連 BL | BL-002 |
| 参照 | [cela_phase1_design_v7.md §0, §3.4, §5](r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md)、[traceability.md T-5](traceability.md) |

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
| 参照 | [decision_lineage.md 論点3](decision_lineage.md)、[cela_phase1_design_v7.md §3.5.2](r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md) |

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
| 参照 | [decision_lineage.md 論点7](decision_lineage.md)、[cela_phase1_design_v7.md §3.5.2](r1_r2_r3b_core/cela_r1_r2_r3b_design_v7.md) |

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

### D-019: `_query_AI_live`の例外捕捉に`json.JSONDecodeError`を追加する（D-009の考慮漏れの是正）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-19 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 継続中の本番ドライランが、ユーザー提供の完全なトレースバックにより`openai`SDK内部（`response.json()`、httpx経由）での生`json.JSONDecodeError`未捕捉クラッシュと判明した。OpenRouter経由の一部プロバイダが途中で切れた/壊れたレスポンスを返したことが原因で、`_query_AI_live`の`client.chat.completions.create(...)`呼び出しを包む`except (APIError, APIConnectionError, RateLimitError, APITimeoutError)`（D-009）に含まれておらず素通りしていた。D-009の本来の狙いは「一時的なAPI障害はリトライ、ロジックエラーは即座に伝播」という区別であり、壊れたレスポンスはこの意図に照らせば明確に前者に該当する。D-009の判断自体の見直しではなく、絞り込み時の考慮漏れと判断した。 |
| 決定内容 | `_query_AI_live`のexceptタプルに`json.JSONDecodeError`を追加：`except (APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError) as e:`。`tc.function.arguments`のパース失敗は既存の別のローカルtry/exceptで個別処理済みのため、この追加による誤握りつぶしの懸念はない。 |
| 影響 | `cela_main.py` `_query_AI_live`の外側except節 |
| 関連 BL | [BL-022](issue_backlog.md#bl-022-openrouterの壊れたレスポンスによる生jsonjsondecodeerrorがd-009の絞り込んだexceptを素通りしクラッシュ) |
| 参照 | 本番ドライランの完全トレースバック（`detector`ノード、`f4e09709-3300-d8d4-3dd2-81ba45905a42`、2026-07-19） |

### D-020: BL-023の対応をPhase A（task_planner/User AIのスコープ是正）・Phase C（予算カスケードの仮説化）から着手し、Phase B（BL-005 reflection/facilitator復旧）は後回しにする

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | BL-023の対応案はPhase A（task_plannerの出力スキーマ拡張＋`generate_user_utterance`のスコープ境界明確化）、Phase B（BL-005修正が前提の、reflection/facilitatorへの森レベル整合性の委譲）、Phase C（予算のトップダウン・カスケードとフィージビリティ・エスカレーション経路）の3段構成として提示した。実ドライラン（`log/2026-07-19/2056`）で直接観測された「検算の嵐」（task_1.2で3ラウンド以上の差し戻し、各ラウンドでExpert 5〜8回・Detector 3〜7回のpython_repl呼び出し）は、task_planner／User AIによる1タスクへの複数独立検証可能主張の束ね込みが直接原因であることがログで実証されている。一方、reflection/facilitatorの不在（BL-005）が現在の検算の嵐を悪化させているという説明はAIによる構造的推論であり、ログで直接実証された事実ではない。したがって、確度の高い直接原因（Phase A）と、ユーザーが強く懸念する将来リスク（現場への無理な予算押し付け、Phase C）を優先し、確度の低い間接要因（Phase B）は非ブロッカーとして後回しにするのが合理的と判断した。なお、Phase Aの`depends_on`/`owns_variables`フィールドは、reflection/facilitatorが本来担うはずだった「共有変数の一貫性チェック」の一部を構造的に代替するため、Phase B先送りによる悪影響は限定的である。 |
| 決定内容 | BL-023の実装はPhase A→Phase Cの順で着手する。Phase B（BL-005修正）は「必要だが今回のスコープ是正の直接要因ではない」と位置づけ、非ブロッカーのまま別途対応する。実装順序はPhase A（task_planner/generate_user_utterance、影響範囲が小さくログで確度の高い原因に対応）を先行させ、動作確認後にPhase C（予算カスケード、新規機構で影響範囲が大きい）を着手する。 |
| 影響 | `docs/design/issue_backlog.md`（BL-023の対応順序）、今後の`cela_main.py`実装範囲（`call_task_planner`／`generate_user_utterance`／予算配分・`resource_arbiter`まわり） |
| 関連 BL | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（非ブロッカーとして後回し）、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない) |
| 参照 | `log/2026-07-19/2056/log_no_prompt.md:1517-1545`、[decision_lineage.md 論点23](decision_lineage.md) |

---

### D-021: BL-023の設計を、本プロジェクト自身の統治構造に対応する情報構造としてLineageStateに統合する（`decision_extractor_node`を状態遷移の唯一の書き手とする）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーから「このプロジェクト自身が使っているロードマップ／phaseN詳細設計／issue_backlog／decision_lineage／phase_gate／STATUS／traceability／確定値の再利用、という情報構造をエージェントにも持たせればよいのでは」という指摘があった。調査の結果、CELAには「決定の系譜」（`decisions`テーブル）に相当するものは既に存在するが、「今どのフェーズ・タスクが進行中か」（STATUS相当）は`state["current_phase"]`が初期化時に一度セットされたきり凍結（BL-024、BL-005と同型）しており、「先送り記録」（issue_backlog相当）「完了条件」（phase_gate相当）「充足チェック」（traceability相当）「確定値の共有」（BL-015と重複）はいずれも構造として存在しないことが判明した。これらを個別のBLに分割することも検討したが、ユーザーが「結局目指すところは一緒」と判断したため、BL-023の統合設計として1つの設計書にまとめることにした。状態遷移（`current_phase`/`current_task_id`の更新）の書き手をどのノードにするかについては、新規LLM呼び出しを増やさず、既存の`decision_extractor`が持つ`Directive`抽出パターンを拡張することで実現できるため、`decision_extractor_node`を唯一の書き手とし、書き込み前にtask_planner確定済みの`phases`/`tasks`と照合するフェイルクローズ検証を挟む設計とした（本プロジェクトの`check_docs_consistency.py`が果たす役割と同型）。過去に`generate_user_utterance`側の強制JSON出力（`phase_id`/`task_id`）が試みられ無効化された形跡があるが、無効化理由がドキュメントに残っておらず、AGENTS.mdの「no guessing」原則によりこの方式は採用しない。 |
| 決定内容 | `LineageState`に`current_task_id`/`verified_facts`/`task_criteria_status`を追加し、`Phase`/`Agreement`型を拡張（`Task`型新設、`Agreement.task_id`・`status: "Deferred"`追加）。`decision_extractor`の出力スキーマに`advances_to_phase_id`/`advances_to_task_id`を追加し、`decision_extractor_node`内でtask_planner確定済みのIDと照合した上でのみ`state["current_phase"]`/`current_task_id`を更新する。詳細は`docs/design/r1_r2_r3b_core/cela_r2_design_BL023_task_state.md`を参照。 |
| 影響 | `cela_main.py`（`LineageState`/`Phase`/`Agreement`/`Task`型、`decision_extractor`/`decision_extractor_node`、DBスキーマに`agreements.task_id`列・`verified_facts`テーブル追加） |
| 関連 BL | [BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、[BL-024](issue_backlog.md#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)、[BL-015](issue_backlog.md) |
| 参照 | `docs/design/r1_r2_r3b_core/cela_r2_design_BL023_task_state.md`、[decision_lineage.md 論点24](decision_lineage.md) |

---

### D-022: `reasoning`（内部思考）フィールドの言語強制はスコープ外とする（BL-020は最終出力contentのみを対象とする）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）レビュー中、Decision Extractor・Orchestratorの`reasoning`フィールド（BL-019で可視化した「💭思考」）が中国語で出力されているのを発見。ただし最終出力（`content`、JSON抽出結果、User AIの発言、Detectorのcomment）はすべて日本語のままであり、BL-020の`_inject_japanese_output_directive`は機能していた。ユーザーは「出力が日本語（最低限英語で）出ていれば良しとする。おそらく内部思考言語の強制は無理ですし、やるべきではない」と判断した。理由：(1) `reasoning`はモデル内部の中間表現であり、`content`と同じ強制注入を及ぼしても効果が不安定になりがちで、確実な制御は期待しにくい、(2) 下流ノードが実際に消費するのは`content`のみであり、`reasoning`はBL-019が導入したユーザー向け可観測性のためのものに限られるため、言語が中国語であっても機能的な問題は生じない。 |
| 決定内容 | BL-020のスコープは「最終出力（`content`）の言語」のみとし、`reasoning`フィールドの言語は対象外・現状維持とする。追加の実装は行わない。 |
| 影響 | なし（追加実装なし、BL-020の完了条件・スコープの明確化のみ） |
| 関連 BL | [BL-020](issue_backlog.md#bl-020-中国語系モデル経由でまれに中国語英語出力になる問題) |
| 参照 | `log/2026-07-20/1204/log_no_prompt.md:867-957`、[decision_lineage.md 論点25](decision_lineage.md) |

---

### D-023: Expertのタスク境界逸脱に対し、①スコープガードレール注入と②ツールループのコンテキスト軽量化の両方を実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | BL-023 Phase Aの実ドライラン（`log/2026-07-20/1204`）で、`generate_user_utterance`はtask_1_1のacceptance_criteria範囲を守れていた一方、`call_expert`にはタスク境界を守るガードレールが存在せず、Expertが他タスク（task_2_2）が`owns_variables`として所有する車両台数・システム費内訳・サイクルタイムまで自発的に計算し、MAX_TOOL_ITER=10を使い切り非収束クラッシュしたことが判明した（iter=9-10、`log_no_prompt.md:2290-2416`）。ユーザーは「自問自答しているときはAIに渡すプロンプトやコンテキストはも少し小さいものでもよいかもしれない」と指摘。これを受けAIが分析したところ、`_query_AI_live`のツールループはiter=1〜10まで同一の巨大なsystem_prompt（5フェーズ全部のtasks JSON、全DB agreements）を毎回再送信しており、Expertが自問自答している最中も他タスクの詳細情報が常に視界に入り続ける構造的誘因があると特定した。「言って聞かせる」（プロンプト文言でのガードレール）と「見せない」（ツールループ中のコンテキスト縮小）は異なる作用機序であり、片方だけでは不十分な可能性があるため、両方を実装する方針とした。 |
| 決定内容 | ①`call_expert`のsystem_promptに現在タスクの`acceptance_criteria`/`owns_variables`と「他タスクの領域に踏み込まない」ガードレールを注入する。②`query_AI`/`_query_AI_live`に`light_system_prompt`引数を追加し、ツールループのiter=1完了後（iter=2以降）は`loop_messages[0]`を軽量版system_promptに差し替える。`call_expert`が軽量版を構築して渡す。 |
| 影響 | `cela_main.py`（`call_expert`、`query_AI`、`_query_AI_live`のツールループ） |
| 関連 BL | [BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)、[BL-023](issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する) |
| 参照 | `log/2026-07-20/1204/log_no_prompt.md:2290-2428`、[decision_lineage.md 論点26](decision_lineage.md) |

---

### D-024: orchestratorの専門家選択を固定16種配列から自由記述に変更する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーが「オーケストレーターノードで専門家を選び、専門家ごとに個別グラフを作るべきかと思っていたが、現在の動きではその必要もない？」と提起。コードを確認したところ、`state["selected_expert"]`は`call_expert`のプロンプトに埋め込まれるラベルとして使われるのみで、`call_expert`内部にもグラフの`add_conditional_edges`にも専門家名で分岐する箇所は一切なく、専門家ごとの個別ノード・個別グラフは最初から存在しなかった（単一の汎用`expert_node`のみ）。固定16種配列（`valid_experts`）はアーキテクチャ上の役割を何も果たしておらず、orchestratorの選択肢を不必要に狭めているだけであり、実ドライランのログでもリストのどれにも当てはまらないタスクで無駄な選定コストが発生していた。ユーザーは「なぜ固定配列にしたか忘れてしまったが、v10以前に情報を構造化していなかったツケ。現状謎の足かせになり得ているので自由記述にし、フォールバックは仕込む。専門家ごとのノード構造は必要が生じたらそうする（まだMVPも一通り動いていない）」と判断した。 |
| 決定内容 | `call_orchestrator`のプロンプトから固定16種配列を削除し、タスクに即した専門家の肩書きを自由記述で生成させる。`valid_experts`による検証は撤廃し、空文字・空白のみの場合のみ「プロジェクト全般アドバイザー」にフォールバックする。専門家ごとの個別ノード・個別グラフ構造は、実際にその必要が生じた時点で再検討する（MVP未完成の現時点では非対応）。 |
| 影響 | `cela_main.py`（`call_orchestrator`） |
| 関連 BL | [BL-026](issue_backlog.md#bl-026-専門家名の固定配列valid_expertsを撤廃しorchestratorの自由記述に変更) |
| 参照 | `log/2026-07-20/1204/log_no_prompt.md:937-957`（固定リストへの当てはめに逡巡した実例）、[decision_lineage.md 論点27](decision_lineage.md) |

---

### D-025: MultiLoggerの起動を`__main__`ガード内に限定する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーが実ドライラン中のログ（`log/2026-07-20/1421`）のレビューを依頼した際、同時刻帯に不自然な小さいログフォルダ（`log/2026-07-20/1455`・`1458`）が作られていることが判明。原因は`cela_main.py`の`sys.stdout = MultiLogger()`がモジュールのトップレベル（`if __name__ == "__main__":`の外）にあり、`import cela_main`するだけで即座に`log/日付/HHMM/`が新規作成され標準出力が丸ごとリダイレクトされる構造だったこと。実際、BL-025/BL-026検証用にこのセッション内で実行したオフラインスモークテスト（`import cela_main as m`で始まる）が、1421の実ドライラン進行中の裏で1455・1458を誤生成していた。import時点の無条件副作用は、テストからの隔離を妨げる設計上の欠陥であり、修正すべきと判断。 |
| 決定内容 | `sys.stdout = MultiLogger()`を`if __name__ == "__main__":`ブロック内（`TARGET_GOAL`定義の直前）に移動し、importのみでは発火しないようにする。誤生成された`log/2026-07-20/1455`・`1458`は削除する。 |
| 影響 | `cela_main.py`（モジュールトップレベル、`if __name__ == "__main__":`ブロック） |
| 関連 BL | [BL-027](issue_backlog.md#bl-027-cela_mainpyのロガーがimport時点で無条件起動し本番log配下にテスト実行の痕跡が混入する) |
| 参照 | `log/2026-07-20/1455`・`1458`（誤生成されたテスト痕跡ログ、修正確認後に削除）、[decision_lineage.md 論点28](decision_lineage.md) |

---

### D-026: MAX_TOOL_ITERを10から15へ引き上げる

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 実ドライラン（`log/2026-07-20/1421`）レビュー中、task_2_2の運行スケジュール設計でExpert(logistics_manager)の1回目の提案が`iter=10, tool_calls=9`とMAX_TOOL_ITER上限ぎりぎりで完了（クラッシュはしなかったが余地なし）していたことが判明。BL-025（スコープガードレール・コンテキスト軽量化）はタスク境界を越えた検証コストの増大は防げるが、1タスク自身の`acceptance_criteria`を満たすための正当な段階的検算だけでも上限に迫るケースがあることを示している。ユーザーは「tool コール上限は15回にあげましょう。今の時点ではクラッシュさせないのが先決です」と、検証コストの根本的な削減（Phase C予算カスケード、R4差分パッチ等）より先に、まずクラッシュ耐性を優先する方針を決定した。AGENTS.md §7（定数変更は事前承認必須）に基づき、ユーザーの明示的な指示により変更。 |
| 決定内容 | `_query_AI_live`内の`MAX_TOOL_ITER`を10から15に変更する。検証コストそのものの削減（BL-025の効果測定、Phase C、R4等）は別途対応する。 |
| 影響 | `cela_main.py`（`_query_AI_live`）。**この変更はソースコードに対するものであり、変更時点で実行中だった`log/2026-07-20/1421`のドライランプロセスはすでにモジュールをメモリにロード済みのため恩恵を受けない（次回起動分から有効）。** |
| 関連 BL | [BL-028](issue_backlog.md#bl-028-max_tool_iterを1015に引き上げクラッシュ回避を優先) |
| 参照 | `log/2026-07-20/1421/log_no_prompt.md`（task_2_2のExpert呼び出しが`iter=10/tool_calls=9`で終了した箇所）、[decision_lineage.md 論点29](decision_lineage.md) |

---

### D-027: `owned_variable_values`は`content`と目的が異なることをプロンプトで明記する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `log/2026-07-20/1421`ドライランのtask_2_2で、`verified_facts`の`operation_schedule`が1回目は簡潔な要約で保存されたが、2回目（承認版）はレポート全文（数千文字）がそのまま保存される事故を発見。原因は`call_decision_extractor`のexpert向け`role_instruction`で、`Deliverable`の`content`フィールド向けの「絶対に要約しないこと」指示が、目的の異なる`owned_variable_values`にも波及していたこと。ユーザーに確認したところ、`content`の要約禁止は「AIが全要素を含む長大な成果物を太らせるのではなく、部分成果物を生成し後で製本（合成）する」という意図的な設計であり、この方針自体は変更しない。一方`owned_variable_values`は、他タスクが`depends_on`を通じて参照する際に読む簡潔な要約であるべきで、`content`とは目的が異なる。ユーザーは「Aは実装」（プロンプトへの目的明記）を承認し、「Bはbacklog起票」（独立フィールド化の拡張は将来のノード自身のファイル出力設計と合わせて検討）とした。 |
| 決定内容 | `call_decision_extractor`のexpert向け`role_instruction`に、`owned_variable_values`は`content`とは別物であり、依存タスク参照用の簡潔な要約（全文コピー禁止）にすべきことを明記する。`owned_variable_values`を独立スキーマフィールドとして切り出す拡張（BL-030）は、`decision_extractor`が将来ノード自身のファイル出力機構に伴い補助的役割へ縮小していく設計と合わせて再検討し、今回は着手しない。 |
| 影響 | `cela_main.py`（`call_decision_extractor`のexpert向け`role_instruction`） |
| 関連 BL | [BL-029](issue_backlog.md#bl-029-owned_variable_valuesにcontentの全文がそのまま混入する事故を修正)、[BL-030](issue_backlog.md#bl-030-owned_variable_valuesを依存関係参照専用の要約レポートとして独立フィールド化する拡張案) |
| 参照 | `log/2026-07-20/1421/log_no_prompt.md:17768`（1回目の正しい簡潔保存）、`log/2026-07-20/1421/log_no_prompt.md:22235`（2回目の全文混入）、[decision_lineage.md 論点30](decision_lineage.md) |

---

### D-028: プレフィックスキャッシュヒット率改善はMVP完成後のコスト最適化枠として据え置く

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーがOpenRouterダッシュボードで直近24時間の実績（4.6Mトークン、キャッシュヒット率19.7%、コスト$0.65）を確認・共有。単価自体は格安モデル（`deepseek-v4-flash`系）想定で妥当だが、ヒット率19.7%は本日のログレビューで確認した「Recent Decisions再掲・task_planner出力JSON全体等の可変ブロックが毎ターン再送されプレフィックスキャッシュを壊している可能性」と整合する。ユーザーは「エージェントアーキテクチャを洗練させていくと、そこそこの性能の格安モデルでも十分動き、成果が出せると感じた」と所感を述べ、この観察をBLとして記録するよう指示。現状すでに$0.65/4.6Mと十分安価でMVPも未完成のため、緊急対応ではなくbacklog化とする。 |
| 決定内容 | プロンプト構造（不変の固定部分と、ターンごとに変化する部分の配置）の整理によるキャッシュヒット率改善は、BL-031として起票し`open`のまま据え置く。MVP完成・Phase C着手後など、コスト最適化に着手するタイミングで優先度を再確認する。 |
| 影響 | なし（現時点でコード変更なし。将来`cela_main.py`の各ノードのプロンプト構築箇所が対象） |
| 関連 BL | [BL-031](issue_backlog.md#bl-031-プロンプトのプレフィックスキャッシュヒット率を上げる構造整理コスト最適化) |
| 参照 | OpenRouterダッシュボード実績（2026-07-20時点、4.6Mトークン/ヒット率19.7%/$0.65）、[decision_lineage.md 論点32](decision_lineage.md) |

---

### D-029: 同一task_idの兄弟Decisionへの承認カスケードを、Detector判定でガードして実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `log/2026-07-20/1421`のプロンプト出力で、task_2_3の親Deliverable（予約手段の設計レポート）は承認済みなのに、同じAgent提出から抽出された4件のDecision（予約チャネル按分比率等）がProposedのまま永久に取り残され、以降全ターンの「合意・決定事項・検討状況DB」に🤔として再掲され続けていることをユーザーが発見。原因は`call_decision_extractor`のUser直後`role_instruction`が承認時の`target_topic`を単数でしか指定させず、兄弟トピックへの承認カスケードがないこと。AIは`task_id`に基づく機械的カスケードを提案したが、ユーザーは「本当に未検討の事項が放置されるのはどうしましょうか」と、単純な機械化が未レビューの項目まで隠蔽するリスクを指摘。これを受け、`detector_node`が`decision_extractor_node`より先に`state["constraint_issue"]`/`state["task_criteria_status"][task_id]`をセットしている既存の順序を利用し、同ターンのDetector判定が清浄な場合のみカスケードするガード付き設計に改訂した。 |
| 決定内容 | `decision_extractor_node`が「同一task_idのDeliverableがApproved」を検出した際、同ターンの`state["constraint_issue"] != "major"`かつ`state["task_criteria_status"][task_id]`が全て`true`の場合のみ、同task_id配下の他のProposed項目を機械的にカスケード承認する。いずれかを満たさない場合はカスケードせず、現状のProposedのまま残す。BL-032として起票し、設計は確定・実装承認済みだが実装は別ターンで行う。 |
| 影響 | `cela_main.py`（`decision_extractor_node`、実装は未着手） |
| 関連 BL | [BL-032](issue_backlog.md#bl-032-deliverable承認時に同一task_idの兄弟decisionが永久にproposedのまま取り残される) |
| 参照 | `log/2026-07-20/1421/log_no_prompt.md`（task_2_3の4件のDecisionが繰り返しProposedとして再掲される箇所）、[decision_lineage.md 論点33](decision_lineage.md) |

---

### D-030: Expertの検算未実施を検出しDetectorへ提示しつつ、複合失敗のみ強制差し戻しする

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `log/2026-07-20/1421`のtask_5_2で、Expert(legal_advisor)が`tool_calls=0`のまま「全ての検算が完了した」と虚偽申告し、過失割合・保険料等の数値を含むレポートを提出していたことをユーザーが発見。既存のF-2.6監査フラグ（`⚠️ python_replを一度も使わずに応答しました`）は警告表示のみで強制力がなかった。後段のDetectorが独立検算し実害はなかったが、これは偶然であり、Detectorの検算が省略された場合のリスクが残る。ユーザーは当初「このフラグが出たら強制差し戻し」を提案したが、同時に「本当に計算不要な思考の場合もあり、無限ループ化のリスクがある」と自ら懸念を指摘した。これを受け、単純な強制ではなく段階的な設計とした。さらにユーザーから「AIが呼んだ直前のpythonスクリプトを保存できないか」「Detectorがまず自分で検算し、その後Expertのスクリプトを見て（あるいは実行して）整合を確認する」という追加提案があり、設計に統合した。 |
| 決定内容 | (1) `_query_AI_live`でExpertが実行したpython_replのcode/resultを`state["expert_last_python_calls"]`に保存し、`call_detector`のプロンプトに提示する（Expertの自己申告を鵜呑みにせず、まずDetector自身が独立検算し、その後この記録と突き合わせて整合性を確認するよう指示）。(2) Expertの成果物を評価するターンに限り、ExpertとDetectorの**両方**が同一ターンでpython_repl未使用だった場合のみ、`constraint_issue`を強制的に`major`にしてフェイルクローズする。片方でも使用していれば発火しない（正当な計算不要ケースを巻き込む無限ループを回避）。 |
| 影響 | `cela_main.py`（`_query_AI_live`、`call_detector`、`expert_node`、`detector_node`、`LineageState`） |
| 関連 BL | [BL-033](issue_backlog.md#bl-033-expertがpython_repl未使用のまま検算完了と虚偽申告できるf-26監査フラグに強制力がない) |
| 参照 | `log/2026-07-20/1421/log_no_prompt.md:46025`付近（Expertの虚偽申告と、後段Detectorの独立検算箇所）、[decision_lineage.md 論点34](decision_lineage.md) |

---

### D-031: Deliverableの物理ファイル保存を承認前提にする設計変更は、R4のホワイトボード化まで見送る

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `log/2026-07-20/1421`のtask_6_3で、Expertの最終計画書提出をDetectorが通した直後、`decision_extractor_node`（`cela_main.py:2812-2827`）がDB上の`status`（この時点では常に`"Proposed"`）を問わず無条件で`save_deliverable_to_file()`を呼び、ユーザー（User AI）の承認より前に物理ファイルが確定してしまうことをユーザーが発見。`integrator_node`は`status=="Approved"`のもののみ集約するため正当性は壊れていないが、却下・修正のたびに旧版ファイルが孤児として残る（task_2_2で既に却下v1・承認v2の2ファイルが実例として残存）ディスク衛生・監査上の課題があった。対応として「Proposed時点ではファイル保存せずApproved確定時に初めて書き込む」設計変更も検討したが、ユーザーは、将来のR4（ホワイトボード化・mdファイルの差分読み書き方式、D-018）が実現すればノード自身が承認確定後にのみ書き込む構造に自然に置き換わる見込みであるため、現時点で`decision_extractor_node`に個別の修正を加えるより記録に留め、R4着手時にまとめて解消する方が合理的と判断した。 |
| 決定内容 | `decision_extractor_node`のファイル保存タイミング（Proposed時点での無条件保存）はコード変更せず現状維持する。BL-034として実装見送りのまま記録し、R4のホワイトボード化設計に統合して再検討する。 |
| 影響 | なし（現時点でコード変更なし。将来`cela_main.py`の`decision_extractor_node`がR4対応時に見直し対象） |
| 関連 BL | [BL-034](issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)、[BL-018](issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（`whiteboard_drafts`/R4） |
| 参照 | `cela_main.py:2812-2827`（`decision_extractor_node`のファイル保存箇所）、task_2_2の却下v1・承認v2の実例、[decision_lineage.md 論点35](decision_lineage.md) |

---

### D-032: フェーズ横断の確定値・成果物アクセスは、エージェント自律の読み取りツール（F-3.8）を新規追加して解決する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-20 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | `log/2026-07-20/1421`のtask_6_3（総合導入計画の完成）で、Expertがピーク輸送力を「60÷13.8×9×3=117人/時」と誤計算し、Detectorが「正しくは60/13.8×9=39.1人/時であり、ピーク需要66.7人/時を下回る」と差し戻した事例をユーザーが報告。Python検算で正しさを確認したところ、これは表面的な計算ミスではなく、別フェーズ（task_2_1）で確定済みの車両台数（3台）そのものがピーク需要を満たせていないという、より根深い問題だった。原因をコードで追跡した結果、`_build_task_scope_context`（`cela_main.py:1306-1311`）が`state["current_phase"]["tasks"]`（現在のフェーズ内のタスクのみ）を走査して依存タスクの確定値（verified_facts）を解決しており、`depends_on`がフェーズをまたぐ参照を含む場合は**構造的に解決不能**（該当タスクが走査対象に存在しないため無条件でヒットしない）であることが判明した。Expertは差し戻されるたびにDetectorの直近の指摘文（`constraint_issue_log`）は受け取るものの、「なぜ3台なのか」という根拠そのものにはアクセスできず、`expert_retry_count>=3`で`reflection`に丸投げされる収束不能リスクをユーザーが懸念した。対応として`_build_task_scope_context`のループを`state["phases"]`全体を走査するよう修正する即応パッチも検討したが、ユーザーは、将来的にエージェント自身にファイルI/O・DB I/Oのツールを持たせる設計に統合すればこの種の問題は構造的に解消されるとの判断を示し、そちらを正式なDB読み取り要件として要件定義書に追加する方針を採用した（DB I/Oの読み取りツールは既存の要件定義書に存在しないことをユーザー自身が指摘）。 |
| 決定内容 | 要件定義書_v35.mdにF-3.8「自律的DB/ファイル読み取り（Tool Calling）の内包」を新規追加（v35.1）。F-3.1（自律的DB書き込みツール）の読み取り対として、`verified_facts`のフェーズ非依存検索、および`log/deliverables/`配下ファイルの能動取得を、User AI・Expert・Detector・Reviewer・Integratorに読み取り専用ツールとして装備させる将来要件とする。`_build_task_scope_context`のクロスフェーズ参照バグ自体は、この読み取りツール実装時にまとめて解消する方針とし、単体の応急パッチは今回実施しない。BL-035として記録。 |
| 影響 | `要件定義書_v35.md`（F-3.8新規追加、v35.1）。`cela_main.py`は現時点で変更なし（`_build_task_scope_context`の応急パッチは見送り）。 |
| 関連 BL | [BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない) |
| 参照 | `cela_main.py:1306-1311`（`_build_task_scope_context`の依存変数解決ループ）、`log/2026-07-20/1421`のtask_6_3 Detector差し戻し箇所、[decision_lineage.md 論点36](decision_lineage.md) |

---

### D-033: 最終計画書の数値ドリフトは、BL-035の既知原因による予想された結果として参考記録に留める

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-21 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザー依頼で`log/2026-07-20/1421`の全21成果物を内容面でレビューした結果、「最終計画書」の年間ランニングコスト・実質赤字額・補助金使用率が、統合パス（Ver.1.0/1.1、logic_verifierの完了報告）のたびにPhase 3承認済み根拠（task_3_2）と最大4.26倍乖離し、需要数値（人口・1日総需要）も同様に根拠なくドリフトしていることが判明した（BL-036）。原因はBL-035で既に特定済みの構造（統合パス担当ペルソナが承認済みファイルを読み返す手段を持たず、その場でもっともらしい数値を再構成している）と同一であり、独立した新規欠陥ではない。ユーザーは「各種の情報にアクセスできないのが根本原因ですので、phase6の挙動はある意味予想された結果です」と述べ、既知原因から論理的に予想される結果を独立した緊急課題として扱うべきではなく、F-3.8（読み取りツール）実装後に実際のアクセス可能性が確保された状態で再評価すべきと判断した。 |
| 決定内容 | BL-036として発見内容を参考記録として起票する。現時点では独立の追加修正・緊急対応は行わない。F-3.8実装後、同一構成（6フェーズ・18タスク）でPhase 6を含む再ドライランを実施し、統合パスが承認済み根拠ファイルを実際に読み返せる状態で財務・需要数値のドリフトが解消されるかどうかによって、本問題の実効性を判断する。解消されない場合は統合パスのプロンプト設計自体を追加で見直す。 |
| 影響 | なし（現時点でコード変更なし。判断はF-3.8実装・再ドライラン後に持ち越し） |
| 関連 BL | [BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない) |
| 参照 | `log/2026-07-20/1421/deliverables/`内のtask_3_1・task_3_2・Ver.1.0/1.1・logic_verifier完了報告の数値比較、[decision_lineage.md 論点37](decision_lineage.md) |

---

### D-034: Decision/Agreementの理由記載の薄さは、BL起票のみに留めF-3系統合時に再設計する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-21 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | ユーザーが「decisionなどある程度記憶の外部化ができていますが、理由の記載が甘いと感じました。phase6でもdetectorが決定された数値がなぜこの値か疑問に思っているログがありました」と指摘。`log/2026-07-20/1421`のDetector自身の思考ログを確認したところ、対象人口5,200人（vs 5,000人）、中心部ルート1周回15分、燃料費計算の80km/ルート、電話対応所要時間7.5時間/日など、複数箇所で「根拠が不明」「以前のタスクで設定された数値かもしれないが根拠が不明」という記述が繰り返されており、Detector自身が過去の決定の理由を遡って検証できていないことが判明した。原因は(1)計算過程の中間仮定がDecisionとして個別抽出されず`reason_why`欄自体が存在しないケース、(2)抽出されても`reason_why`が結論の言い換えに留まり前提・出典・棄却案まで遡れないケース、の2種の混在と分析。BL-034〜036（ファイル読み取りアクセスの欠如）と根本原因は同系統（後から参照可能な情報の粒度不足）だが、対象が`reason_why`欄の記載品質・抽出粒度自体である点で異なる。F-3.8（読み取りツール）が実装されても、参照先の`reason_why`が薄いままでは根拠の再構成ができない可能性があるため、独立した課題として記録する必要があると判断した。 |
| 決定内容 | BL-037として発見内容を記録する。プロンプトの単体強化など個別の即応対応は行わない。将来的にF-3.1〜F-3.7（`write_agreement_tool`によるエージェント自身の自律書き込みへの移行、`decision_extractor_node`の補助的役割への縮小）に着手する際、理由記載の強制粒度（前提・出典・棄却した代替案の明記）をあわせて再設計する。 |
| 影響 | なし（現時点でコード変更なし。判断はF-3.1〜F-3.7着手時に持ち越し） |
| 関連 BL | [BL-037](issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない)、[BL-034](issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)、[BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例) |
| 参照 | `log/2026-07-20/1421/log_no_prompt.md`（4453・17074・17155・25004・71381行目付近、Detectorの「根拠が不明」記述箇所）、[decision_lineage.md 論点38](decision_lineage.md) |

---

### D-035: BL-036/BL-037の解決方針として、NPU-Context-Saver由来の時間減衰検索・構造化ファクトストアをF-8.4/F-3.9として要件化する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-21 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | BL-036（最終計画書の財務・需要数値ドリフト）・BL-037（Detector自身が過去の数値の根拠を辿れない）の議論の延長で、AutoGPT/CrewAI的なRAGメモリ一般が抱える「新旧の断片をLLMの推論だけで整合させる」リスクについて議論した。ユーザーから、CELAの前身プロジェクトNPU-Context-Saverでは実際に(1)会話履歴へのタイムスタンプ付与とRAG検索への時間減衰性の導入（決定・否決ターンのみ減衰から除外）、(2)タイムスタンプ順の時系列復元読み、という設計を行い実運用で有効だったとの共有があった。さらに、決定事項を「値・理由・出典（会話履歴中の非連続な参照箇所を全列挙）」の三つ組としてトピック名で検索できるDB化案が追加提案され、その理由（reason）欄は絶対的な正しさを要求せず「暫定値として進めた」こと自体を正当な理由として認め、後で状況が変わった際の再検討トリガーとして機能させるべきという設計上の要点が示された。これらはBL-036/037が指摘した問題に対する具体的な解決の方向性であり、F-3.8（読み取りツール）を「ファイルを丸ごと読み返す」から「トピックで構造化された事実を直接引く」へ格上げするものと判断した。 |
| 決定内容 | 要件定義書_v35.mdにF-8.4「時間減衰検索と決定・否決ターンの自動セイリエンス固定、時系列復元読み」およびF-3.9「構造化された事実・理由・引用元セット（トピック検索型ファクトストア）」を新規追加（v35.2）。F-3.9では`verified_facts`を`{topic, value, reason, citations}`の構造化タプルへ拡張し、`reason`に「確定（confirmed）」「暫定（provisional）」の区別を持たせる設計を明記。実装はF-3.1〜F-3.8と合わせて将来着手する（現時点では要件定義のみ、コード変更なし）。BL-036/BL-037にこの設計方針への参照を追記する。 |
| 影響 | `要件定義書_v35.md`（F-3.9・F-8.4新規追加、v35.2）。`cela_main.py`は現時点で変更なし。 |
| 関連 BL | [BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-037](issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない) |
| 参照 | NPU-Context-Saverの時間減衰RAG・決定/否決ターン除外の実運用実績、[decision_lineage.md 論点39](decision_lineage.md) |

---

### D-036: R2をD-002同様の扱いでクローズし、R3を「R3a（自律的読み取り、F-3.8/F-3.9）→R3b（自律的書き込み、旧来のR3）」に再編する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-21 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | 次アクションであった指標C実測（BL-023適用前ベースラインとの比較、最低5試行）について、ユーザーから「ホワイトボード・ファイル/DB I/Oが実装されないと、検証の手間の割に検算導入だけでは効果が出ない」とのROI上の懸念が提起された。これに対し、T-10ドライランのレビューで発見した交絡要因（BL-035フェーズ横断`verified_facts`参照不能、BL-036財務・需要数値ドリフト、BL-037`reason_why`の薄さ）はいずれもPhase 6の最終統合ステップに集中しており、かつ「自律的**読み取り**」の欠落が共通の根本原因であることを確認した。一方、旧来のR3（`write_agreement_tool`による自律**書き込み**）はこれらの問題を直接解消しない。したがって、指標C実測という金のかかる検証を今すぐ行うより先に、実害が確認済みの読み取り欠落（F-3.8/F-3.9、v35.1/v35.2で要件化済み）を解消する方が費用対効果が高いと判断した。R2自体は、指標D実測（T-7・T-8）と全18タスク完走の定性確認（T-10）をもって、Phase 1（D-002）と同じ「構造的完了」の扱いでクローズし、指標Cの定量実測はR3a完了後の再ドライランへ振り替える。 |
| 決定内容 | (1) R2を`phase_gates.md` P2-2の構造的クローズをもってDoneとする。(2) `cela_roadmap_v25.md`のR3を、R3a（F-3.8自律的読み取りツール・F-3.9構造化ファクトストア、先行実装）とR3b（`write_agreement_tool`、F-3.1〜F-3.7、旧来のR3スコープ）の2段階に再編する。(3) R4（ホワイトボード差分パッチ化）の前提は「R3a＋R3bの両方の完了」とし、`cela_phase2_design_R4.md`冒頭にその旨を追記する。(4) 指標C（収束性とコストのトレードオフ）の実測はP2-2からP3a-4（`phase_gates.md`新設）へ振り替える。 |
| 影響 | `cela_roadmap_v25.md`（R2完了注記・R3のR3a/R3b分割・R4前提の更新）、`phase_gates.md`（P2-2クローズ・Phase 3節新設・サインオフ表）、`STATUS.md`（アクティブPhase・次アクション更新）、`cela_phase2_design_R4.md`（冒頭前提注記の追記）。`cela_main.py`は現時点で変更なし。 |
| 関連 BL | [BL-035](issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[BL-036](issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-037](issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない) |
| 参照 | [D-002](decision_log.md)（Phase 1クローズ時の同種の指標先送り判断、前例）、[decision_lineage.md 論点40](decision_lineage.md) |

---

### D-037: `docs/design/phaseN/`フォルダ命名をR番号（ロードマップの実装単位）へ一本化する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-21 |
| 状態 | `decided` |
| 決定者 | t-momose |
| **決定理由** | D-036でR3をR3a/R3bに再編した直後、ユーザーから「フォルダ構造をphase毎に分けているが、R#で進んでいてあまり意味がない、むしろ混乱する」との指摘があった。調査の結果、`docs/design/phaseN/`という命名は旧v23時代の「Phase番号」概念の残骸であり、現行のロードマップR番号（R1〜R5）とは既に対応が取れていなかったことが判明した（例: `phase3/`フォルダの中身は実際にはR5設計書`cela_phase3_design_R5_v2.md`だった。`phase2/`にはR4設計書とR2内の一機能追加設計書が混在していた）。さらに直前のD-036で`phase_gates.md`に新設した「Phase 3」の見出しが、この`phase3/`フォルダ（実際はR5）と名称衝突する状態になっていた。ユーザーに整理方針の選択肢（R番号一本化／対応表を1箇所に固定／記録のみで着手しない）を提示し、「R番号一本化（推奨）」が選ばれた。 |
| 決定内容 | `docs/design/`配下のフォルダ・ファイル名をR番号ベースへ統一。`phase0/`→`r0_planning/`、`phase1/`→`r1_r2_r3b_core/`（内部ファイルも`cela_phase1_design_v7.md`→`cela_r1_r2_r3b_design_v7.md`、`cela_phase1_impl_Plan.md`→`cela_r1_impl_Plan.md`、`phase1_dryrun.md`→`r1_dryrun.md`へリネーム）、`phase2/cela_phase2_design_R4.md`→`r4/cela_r4_design.md`、`phase2/cela_phase2_design_BL023_task_state.md`→`r1_r2_r3b_core/cela_r2_design_BL023_task_state.md`（R2の一部のため）、`phase3/cela_phase3_design_R5_v2.md`→`r5/cela_r5_design_v2.md`。`phase6/`→`phase6plus/`は維持（ロードマップ自身が「Phase 6以降」という非R番号の呼称を意図的に使っている特殊区分のため、R番号化はしない）。全ファイルの相互リンクを更新し、`scripts/check_docs_consistency.py`で不整合ゼロを確認。 |
| 影響 | `README.md`（詳細設計索引・実装フェーズ表）、`phase_gates.md`（ドキュメント役割表）、`cela_roadmap_v25.md`（各R節の詳細設計リンク）、`STATUS.md`、`issue_backlog.md`、`decision_log.md`、`decision_lineage.md`のリンク・パス参照。フォルダ・ファイルの物理移動のみで、内容の変更は行っていない。 |
| 関連 BL | — |
| 参照 | [decision_lineage.md 論点41](decision_lineage.md) |

---

### D-038: BL-038の根本原因をLangGraphの未宣言TypedDictキー消失と特定し、`LineageState`へのフィールド追加とdecision_extractorフォールバックのWHITEBOARD保護で対応する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-22 |
| 状態 | `decided` |
| 決定者 | t-momose / Claude Sonnet 5（原因特定・修正案の提示） |
| **決定理由** | R4実装後の実ドライラン（`log/2026-07-22/1407`）レビュー中、`write_agreement`で保存したばかりの`WHITEBOARD:phase_1:task_1_1`ポインタ行が、直後の`decision_extractor_node`によって`Superseded`にされ、ポインタでも何でもないプレーンな短文（Agentのチャット完了報告の要約）に置き換えられる実害をDB上で直接確認した。これはBL-038（`wrote_agreement_this_turn`ガードが機能せず二重書き込みが起きる問題）の実データ破損版であり、既存のオフラインテスト（`decision_extractor_node`をPython関数として直接呼ぶ形）ではこの経路を検出できていなかった。インストール済みLangGraph（v1.2.9）で最小構成の検証コードを書いて実際に挙動を確認した結果、`StateGraph`のスキーマ（`LineageState` TypedDict）に**宣言されていないキー**は、ノードの戻り値に含めても次のノードには伝播せず消えることを実証した。`expert_wrote_agreement`・`user_wrote_agreement`・`expert_last_whiteboard_edit`はいずれもR3b/R4導入時に`LineageState`への追加が漏れており、これが一貫してFalse/None評価されていた真因だった（同時期に導入された`expert_last_python_calls`はTypedDictへの追加が行われていたため正常動作していた、という対比が根拠を補強する）。 |
| 決定内容 | (1) `LineageState`（`cela_main.py`）に`expert_wrote_agreement: bool`・`user_wrote_agreement: bool`・`expert_last_whiteboard_edit: dict \| None`を追加する。(2) 上記ガードが将来再び機能しなかった場合の二重防御として、`decision_extractor_node`のフォールバック経路（`old_content`が`FILE_PATH:`の場合の既存保護ロジック）に`WHITEBOARD:`ポインタの保護分岐を追加し、フォールバック経路からのプレーンテキスト上書きを常に拒否する（`write_agreement`の`edits`以外にホワイトボードを正しく更新する手段がフォールバック側に存在しないため）。(3) `tests/test_r4_smoke.py`に、実際の`StateGraph(cela_main.LineageState)`を組んで`app.invoke()`経由でキーが伝播することを検証する回帰テストと、WHITEBOARD保護の回帰テストを追加する。(4) デバッグ用に仕込んだ`[DEBUG]`printはユーザーの指示により削除せず残す。 |
| 影響 | `cela_main.py`（`LineageState`定義、`decision_extractor_node`のUPDATE分岐、デバッグprint2箇所）、`tests/test_r4_smoke.py`（回帰テスト2件追加）。オフラインスモークテスト66件全通過を確認。**2026-07-22、実LLMドライラン（`log/2026-07-22/1804`）で`expert_wrote_agreement=True`の正常伝播と`⏭️`スキップ（同一ターンで抽出された10件全て）を確認し、修正の実効性を確定した。** |
| 関連 BL | [BL-038](issue_backlog.md#bl-038-write_agreement成功後もdecision_extractor_nodeのagreement抽出がスキップされず同一トピックでdecisionとdeliverableの二重書き込みが発生する) |
| 参照 | [decision_lineage.md 論点44](decision_lineage.md) |

---

### D-039: ドライランの一時停止・再開を、`app.stream()`によるノード単位チェックポイントで実装する（ターン境界方式は不採用）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-22 |
| 状態 | `decided` |
| 決定者 | t-momose（ターン凍結の指摘・最終承認） / Claude Sonnet 5（当初案の提示・誤りの訂正・再設計） |
| **決定理由** | ドライラン長時間化により連続稼働が難しいとの相談を受け、AIは当初「`app.invoke()`から戻ったターン境界でstateをJSON保存し、次回起動時に再開する」方式を提案した。しかしユーザーが「そもそも今、ターンは凍結されて1のままなのでは？」と指摘し、BL-005（`state["turn_count"]`は`route_after_expert_decision`が`generate_user_utterance`へ内部ループバックし続ける限り更新されず、`app.invoke()`単位では長時間戻ってこないことがある）を踏まえると、ターン境界でのチェックポイントは実用にならないと判明した。 |
| 決定内容 | `run_ai_vs_ai_loop`で`app.invoke(state)`の代わりに`app.stream(state, stream_mode="values")`を使い、グラフの各ノード実行後のstateスナップショットを都度受け取ってcheckpoint（`_save_checkpoint`、原子的書き込み）へ保存する。`KeyboardInterrupt`（Ctrl+C）を捕捉し保存後に終了、`--resume <checkpoint.json>`で`_load_checkpoint`から`state`/`config`/`current_turn`を復元する。グラフのentry_pointが`task_planner`固定のため、再開は「止めたノードそのものから」ではなく「その回（ラウンド）の頭（`generate_user_utterance`）から」になる（`task_planner_node`に`turn_count==1 and not state.get("phases")`の冪等性ガードを追加し、ターン1途中の再開でも計画を再生成しないようにした）。 |
| 影響 | `cela_main.py`（`_save_checkpoint`/`_load_checkpoint`新設、`run_ai_vs_ai_loop`の`resume_from`引数、`task_planner_node`の冪等性ガード、`__main__`の`--resume` CLI引数）。`tests/test_checkpoint_resume.py`（新規4件）。オフラインスモークテスト計70件通過。実LLMドライランでのCtrl+C→`--resume`往復の実地確認は未実施。 |
| 関連 BL | [BL-044](issue_backlog.md#bl-044-ドライランの一時停止再開機能ctrlccheckpointjson--resume)、[BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離) |
| 参照 | [decision_lineage.md 論点45](decision_lineage.md) |

---

### D-040: reflection/facilitatorの周期発火を、`turn_count`ではなく新設の`round_count`（`generate_user_utterance_node`再入場カウント）で判定するよう変更する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-23 |
| 状態 | `decided` |
| 決定者 | t-momose（区切り単位の確認・承認） / Claude Sonnet 5（原因特定・実装） |
| **決定理由** | 実ドライラン（`log/2026-07-22/2336`）で、task_planner生成のacceptance_criteria自体に数学的矛盾（山間部12km・時速20km/h前提では30分以内は不可能）があったところ、Expertが根拠のない内訳（8km+4km）ででっち上げて帳尻を合わせ、Detectorも自身の推測で追認してしまう事例をユーザーが発見。ユーザーが「このお題はGeminiとの壁打ちで、あえて無理な制約を与えAIがどう格闘するか見る趣旨だった」「reflectorが定期的に会話ログを見て、でっちあげ・制約違反を見つける設計だったはず」と経緯を共有し、この監査層（`docs/design/r5/cela_r5_design_v2.md` §1.3、F-2.1拡張として設計済み）を実際に機能させる方針で合意した。しかし`route_after_expert_decision`のreflection発火判定は`state["turn_count"]`を使っており、BL-005（`turn_count`はグラフ内部ループでは更新されず凍結し得る）の影響で`reflection_interval`が実質的に一度も発火しない状態だった。 |
| 決定内容 | (1) `LineageState`に`round_count: int`を新設し、`turn_count`には手を加えない（影響範囲を最小化するため）。(2) `generate_user_utterance_node`（BL-044で確認済みの「ラウンド」定義における各ラウンドの起点）への再入場のたびに`round_count`をインクリメントする。(3) `route_after_expert_decision`のreflection発火条件を`state["turn_count"] % state["reflection_interval"]`から`state["round_count"] % state["reflection_interval"]`へ変更する。(4) `call_reflection`のプロンプトに、`docs/design/r5/cela_r5_design_v2.md` §1.3で設計済みの「でっちあげ監査」の趣旨を反映した監査ブロックを追加する。ただし同節が前提とする`internal_thought_process`（reasoning content）のキャプチャ・全経路への配線は別途大きめの変更となるため、今回は既存の`chat_history`/決定タイムラインのみを材料にした軽量版とし、フル版（F-2.1本体）は別途実装判断とする。 |
| 影響 | `cela_main.py`（`LineageState`への`round_count`追加、`generate_user_utterance_node`のインクリメント、`route_after_expert_decision`の判定変更、`call_reflection`のプロンプト追加）。既存の`turn_count`ベースの表示・`max_turns`比較ロジックには影響しない。旧形式のcheckpoint（`round_count`キーなし）は`state.get("round_count", 0)`のデフォルト値で後方互換。 |
| 関連 BL | [BL-005](issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)、[BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（facilitatorはreflectionの`stagnant`/`drift_flag`判定を経由するため、reflection発火の復旧で間接的に到達可能になる） |
| 参照 | [decision_lineage.md 論点46](decision_lineage.md) |

---

### D-041: F-2.6検算ゲートによる注意力の偏りを是正するため、Detector/User AI/Expertの「数値検算」と「ドメイン妥当性レビュー」を分離する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-23 |
| 状態 | `decided` |
| 決定者 | t-momose（現象の指摘・実装方式の承認・User AI/Expert側への展開指示） / Claude Sonnet 5（根本原因の分析・実装案の提示・実装） |
| **決定理由** | ユーザーが実ドライラン（`log/2026-07-22/2336`）で「計算ツールを入れたことによりすべてのノードの思考が『計算が合っているか』に引き寄せられ、重大な非数値的懸念（バス2台の予備車両欠如、監視員2名の労基法適合性）を出力に反映できていない」と指摘。ログで裏付けを取ったところ、task_1_1では「オペレーター3名（シフト制）」だったのに対しtask_2_2では同じ絶対制約から「2名常駐」を額面通りの固定人数として再計算しており（矛盾に気づかず双方とも算数としては通過）、`call_detector`のconstraint_issue定義・major判定基準（`cela_main.py`）が「検算の結果、明白な数値矛盾や計算ミスが確認された場合」に強く偏っていることが真因と判明。ユーザーは当初Detectorのみの分離を提案したが、「ログをみているとdetector・ユーザーが同じ検算を3〜4回繰り返している場面もある」ことから、User AI・Expertも含めた全体の注意力配分の是正が必要と判断を拡張した。 |
| 決定内容 | (1) `call_detector`: 既存の数値検算パス（python_repl付き、そのまま）に加え、独立したLLM呼び出しとして「ドメイン妥当性レビュー」パス（ツールなし、数値監査の結果を提示し再検算不要と明示、法規制・物理的運用可能性・でっち上げ疑義等を評価）を新設し、両パスのうちより重篤な`constraint_issue`を採用する2段構成に変更する。ドメイン妥当性レビューは「情報不足を理由にmajorにしない、具体的に矛盾を指摘できる場合のみmajor」という基準を明記し、過検知（オフラインスモークテストで実際に1回発生、基準明記により再現しないことを確認）を防ぐ。(2) `generate_user_utterance`（User AI）: F-2.6検算の指示を「Detectorが既に検算済みであり信頼してよい、よほど疑わしい場合のみ自分でも検算する」という内容に変更し、User AI自身の検算の繰り返しを減らしてドメイン評価に注意を振り向ける。(3) `call_expert`: F-2.6検算指示の直後に、検算とは独立した「ドメイン妥当性チェック」の自問を追加する（Expertは自ら数値を導出する立場のため、検算自体は省略しない）。 |
| 影響 | `cela_main.py`（`call_detector`の2段化、`generate_user_utterance`・`call_expert`のプロンプト追加）。Detectorの呼び出しコストが実質2倍になる（新設のドメイン妥当性レビューパス分）。`tests/test_f26_detection.py`の既存テスト（false-positive非退行・矛盾検出5/5）で非退行を確認（実LLM呼び出し）。 |
| 関連 BL | [BL-049](issue_backlog.md#bl-049-f-26検算ゲートによる注意力の偏りを是正する-数値検算とドメイン妥当性レビューの分離) |
| 参照 | [decision_lineage.md 論点47](decision_lineage.md) |

---

### D-042: `resource_claims`のスキーマを平坦な`{名前: 数値}`から入れ子構造`{名前: {phase_id, value, total_cap}}`へ具体化する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-23 |
| 状態 | `decided` |
| 決定者 | t-momose（Plan承認をもって決定） / Claude Sonnet 5（原因特定・構造案の提示） |
| **決定理由** | R5設計書（`cela_r5_design_v2.md`）のGoalShiftEvent機能がBL-041の`call_resource_arbiter`拡張に依存する一方、BL-041の既存ドラフト（`cela_facilitator_arbiter_redesign_BL041.md`）が調査した通り、`state["global_constraints"]`への実データ集約処理自体が存在せず`arbiter_node`は常に空振りしていた。集約処理を実装しようとしたところ、当時の`resource_claims`は`{"予算": 1000000}`という平坦な`{名前: 数値}`形式で、資源の絶対上限（`total_cap`）を持たないため、これ単体では超過判定ができないことが判明した。上限値をどこか別の場所（ゴール文やverified_facts）から名前文字列でマッチングして補う代替案も検討したが、LLMが生成する資源名の表記ゆれに対して脆弱であるため不採用とし、ドラフト§3.1が既に提案していた入れ子構造への具体化を採用した。 |
| 決定内容 | `resource_claims`の期待する値の形を`{"<制約名>": {"phase_id": "<このphaseのID>", "value": <このphaseが要求する量>, "total_cap": <全phase共通の絶対上限>}}`に変更する。`WRITE_AGREEMENT_TOOL`スキーマの`resource_claims`フィールドの`description`と、decision_extractor抽出プロンプトの例示・共通ルールの両方をこの構造に合わせて更新する。DB層（`agreements.resource_claims`列）はJSON文字列としてそのまま素通しで保存するのみで、書き込み時にキー構造をパースする既存コードは存在しないため、この変更によるDB破壊的影響はない。新規`_aggregate_global_constraints`ヘルパーは、旧形式（平坦な数値）や壊れたJSONを`isinstance`チェックで静かにスキップし、混在期間中もクラッシュしないようにする。 |
| 影響 | `cela_main.py`（`WRITE_AGREEMENT_TOOL.resource_claims`のdescription、decision_extractor抽出プロンプトの例示、新規`_aggregate_global_constraints`）。既存agreementsデータに旧形式の`resource_claims`が残っていても、集約対象から静かに除外されるだけで読み込みエラーにはならない。 |
| 関連 BL | [BL-041](issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている) |
| 参照 | [decision_lineage.md 論点58](decision_lineage.md) |

---

### D-043: facilitatorへreflectionの判定理由（`note`）を明示的に受け渡す（未使用の`decisions`引数を置き換える）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-23 |
| 状態 | `decided` |
| 決定者 | t-momose（現象の報告・即時修正の指示） / Claude Sonnet 5（原因特定・実装） |
| **決定理由** | ユーザーが`log/2026-07-23/1656`でfacilitatorが発火したログを共有し確認を依頼したところ、直前のreflectionが`still_aligned=false, discussion_status="stagnant"`と判定し`note`に5点の具体的な未解決問題（与条件無断変更・でっちあげ疑い数値等）を記録していたにもかかわらず、facilitator自身の思考ログは「膠着していない」と明確に矛盾する独自の評価をしていたことが判明した。実際に送信されたプロンプト（`log_with_prompt.md` 57021行目）を確認したところ、`goal`と直近chat_historyのみが含まれ、reflectionの判定理由は一切含まれていなかった。コード調査の結果、`call_facilitator(goal, chat_history, decisions)`の`decisions`引数はプロンプトテンプレート内で完全に未使用（デッドパラメータ）であり、reflectionの`note`は`decisions`テーブルの`why`列にしか保存されず`state`上に存在しなかったため、facilitatorへは構造的に伝わりようがなかったことを特定した。 |
| 決定内容 | `LineageState`に`last_reflection_note: str`を新設し、`reflection_node`が`result["note"]`をここへ保存する。`call_facilitator`のシグネチャを`(goal, chat_history, decisions)`から`(goal, chat_history, reflection_note="")`へ変更し、未使用の`decisions`引数を廃止。プロンプトに「あなたが呼ばれた理由（直前のReflection監査の判定）」ブロックを追加し、これを最優先の出発点として扱い自己判断で無視・軽視しないよう明記する。`reflection_note`が空の場合（旧checkpoint復帰等）はフォールバック文言を使用する。`facilitator_node`の呼び出しを`state.get("last_reflection_note", "")`を渡す形に変更。 |
| 影響 | `cela_main.py`（`LineageState`、`reflection_node`、`call_facilitator`、`facilitator_node`）。`call_facilitator`の呼び出しシグネチャ変更は本関数の唯一の呼び出し元（`facilitator_node`）のみに影響。新規`tests/test_bl061_facilitator_reflection_note.py`（4件）で、reflection_nodeによる保存・call_facilitatorのプロンプトへの反映・空値時のフォールバック・facilitator_nodeからの受け渡しを確認。 |
| 関連 BL | [BL-061](issue_backlog.md#bl-061-facilitatorがreflectionの判定理由を一切受け取れず独立に時に食い違う状況判断をしていた)（BL-041が指摘するエスカレーション機構未実装とは別種の、より具体的な伝達漏れバグ） |
| 参照 | [decision_lineage.md 論点59](decision_lineage.md) |

---

### D-044: F-8.3 Freeze機能の権限を`user`ロールのみに限定し、独立した専用ツールとして実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-23 |
| 状態 | `superseded`（[D-045](#d-045-f-83-freeze機能を一時休止しbl-062をdetector限定で先に解消する)により、Freeze自体を一時休止） |
| 決定者 | t-momose（権限範囲・実装方式の選択） / Claude Sonnet 5（選択肢の提示・監査ガバナンス欠落の調査） |
| **決定理由** | R5実装計画（F-8.3 Freeze機能）の設計相談中、Freezeのトリガー方法（新規専用ツール vs 既存`WRITE_AGREEMENT_TOOL`拡張）を確認したところ、ユーザーから「Freezeされた項目を後からDetectorがひっくり返したらどうするか」という懸念、および「そもそもDetectorはユーザー/エキスパートの決定まで破棄できたか？」という根本的な疑問が提起された。調査の結果、Detector等の`major`判定・`Rejected`書き込みは既存Agreementを構造的にSUPERSEDE/無効化する仕組みを持たないことが判明した（BL-062として別途起票）。この根深い課題はFreeze機能単体では解消できないため、Freezeの権限を、既存の`ALLOWED_STATUS_BY_ROLE`で最も広い権限を持つ`user`ロール（人間代理としての最終決定権）に限定することで、少なくともFreeze自体の意味（絶対に覆してはならない決定への恒久ピン留め）が損なわれないようにする方針とした。 |
| 決定内容 | (1) 既存の`WRITE_AGREEMENT_TOOL`（既に14パラメータ）を拡張せず、`agreement_id`と`reason`のみを持つ新規専用ツール`FREEZE_AGREEMENT_TOOL`を追加する。(2) `TOOL_DISPATCH["freeze_agreement"]`は`_CURRENT_CALLER_ROLE == "user"`の場合のみ許可し、それ以外はエラーを返す。(3) User AIのtoolsリストにのみ`FREEZE_AGREEMENT_TOOL`を追加し、Expert/Detector/Reviewer/Arbiter/Integratorには付与しない。(4) unfreeze機構は設けない（Freezeは恒久ピン留めという設計意図のため）。(5) `_commit_agreement_from_tool`のSUPERSEDE/UPDATE分岐に、対象行の`is_frozen==1`チェックを追加し拒否する。 |
| 影響 | `cela_main.py`（`FREEZE_AGREEMENT_TOOL`新設、`freeze_agreement()`/`_freeze_agreement_tool_impl()`新設、`TOOL_DISPATCH`への登録、User AIのtools配線、`_commit_agreement_from_tool`のガード追加、`_build_agreements_context`の`is_frozen`ソート＋🔒表示）。新規`tests/test_r5_thought_log_freeze_goalshift.py`でFreeze関連5件のテストを確認。 |
| 関連 BL | [BL-063](issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（本決定の背景にある根深い課題、別途起票のみ） |
| 参照 | [decision_lineage.md 論点61](decision_lineage.md) |

---

### D-045: F-8.3 Freeze機能を一時休止し、BL-062をDetector限定で先に解消する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（Freeze休止・優先順位の判断） / Claude Sonnet 5（技術調査・選択肢の提示） |
| **決定理由** | BL-064（合意メタデータの棚卸し）に続きBL-062の対応を検討する中で、ユーザーが「Freezeはユーザーの決定を絶対視するが検証手段がなく、AIの判断を妄信させることになりかねない」と再考した。一方、BL-062が指摘する逆方向の矛盾（Detectorがmajor判定を出しても、対応するApproved agreementがDB上に誤って残り続け、後続タスク・最終統合がそれを正当な確定値として参照し続ける）は既に実害が具体的に想定される問題であり、ユーザーは両者を天秤にかけてFreezeを一時休止しBL-062の解消を優先する判断をした。調査の結果、BL-062完了条件の①案（write_agreementの権限モデル拡張）は実装不要と判明した——`_check_write_permission`は`status`のみを制限し`action_type`は無制限であり、Detector/Reviewer/Arbiter/Integratorは全員既に`WRITE_AGREEMENT_TOOL`を保有し`status='Rejected'`かつ`action_type='SUPERSEDE'`を呼べる権限を最初から持っていた。真の欠落は権限ではなく、(a) Detector等がそもそも既存agreements DBのtopic一覧をプロンプト上受け取っておらず`target_topic`を指定する材料がなかったこと、(b) SUPERSEDEを使えという運用指示がプロンプトに存在しなかったこと、の2点だった。さらに調査の結果、Reviewer/Arbiter/Integratorは成果物全体・リソース配分・フェーズ横断矛盾を扱う設計であり、Detectorのような個別topic単位のSUPERSEDEが同じ意味を持つかは自明でないため、ユーザーの判断で今回はDetector限定に実装範囲を絞った（[BL-070](issue_backlog.md#bl-070-supersede運用指示をreviewerarbiterintegratorにも拡張するかの検討)として他3ロールへの拡張検討は別途起票）。 |
| 決定内容 | (1) `FREEZE_AGREEMENT_TOOL`をUser AIの`query_AI`呼び出し（`generate_user_utterance_node`、2箇所）のtoolsリストから外し、呼び出し不能にする。`freeze_agreement()`/`_freeze_agreement_tool_impl()`/`TOOL_DISPATCH`登録/`is_frozen`ガード/`_build_agreements_context`の🔒表示は一切削除せず温存する（再開時はtools配線を戻すのみで足りる設計）。(2) `call_detector`に`_build_agreements_context_from_db`による既存agreements DBビューを新規に注入し、`constraint_issue="major"`時にはwrite_agreementを`action_type="SUPERSEDE"`, `status="Rejected"`, `target_topic=<DBのtopic文字列>`で呼び出すよう明示的に指示する一文を追加する。(3) Reviewer/Arbiter/Integratorへの同様の拡張は、各ロールの役割（成果物全体審査・リソース配分・フェーズ横断統合）にtopic単位SUPERSEDEが本当に馴染むかの検討が必要なため、BL-070として別途起票し今回は対象外とする。 |
| 影響 | `cela_main.py`（`call_detector`へのagreements_text注入＋SUPERSEDE指示追加、`generate_user_utterance_node`の2箇所からFREEZE_AGREEMENT_TOOL除去）。新規`tests/test_bl062_detector_supersede.py`（4件）でDetectorへの配線・Freeze休止の両方を確認。 |
| 関連 BL | [BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)、[BL-063](issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)（F-8.3の実装元）、[BL-070](issue_backlog.md#bl-070-supersede運用指示をreviewerarbiterintegratorにも拡張するかの検討) |
| 参照 | [decision_lineage.md 論点64](decision_lineage.md) |

---

### D-046: Directiveの永久Proposed残留は対症療法ではなく根本解決（自動Approved遷移）を採用する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（対応方針の選択） / Claude Sonnet 5（原因調査・選択肢の提示） |
| **決定理由** | ドライラン（`log/2026-07-24/0647`）レビュー中、Reflectionの内省監査が既に完了・承認済みのタスク指示（`entry_type="Directive"`）を「未解決」として繰り返し自問自答している様子から発見。原因は`decision_extractor_node`・`_commit_agreement_from_tool`のいずれにもDirectiveのstatusを`Proposed`から遷移させる経路が存在しないことで、対応するDeliverableが承認されてもDirective自体は永久にDBへ残留する。対症療法（`reflection_node`の未解決抽出条件から`entry_type=="Directive"`を除外する）でも表面上のノイズは消えるが、Directiveのstatus自体が意味を持たなくなるため、他の箇所（将来的な監査・分析）で同じ「Proposedのまま」という不整合が別の形で顕在化する恐れがある。ユーザーは「根本的に解決しないとどこかで問題が顕在化する恐れがある」と判断し、対症療法ではなく根本解決（Deliverable承認に連動してDirective自体をApprovedへ遷移させる）を選択した。 |
| 決定内容 | 新設`_resolve_directive_for_task(conn, run_id, task_id, phase_id, resolved_by)`が、対応するtask_idの`entry_type="Directive"`かつ`status="Proposed"`の最新agreementを`Superseded`化した上で`status="Approved"`の新レコードとして追記する。新設`RESOLVING_DELIVERABLE_STATUSES = {"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}`のいずれかにDeliverableが遷移した場合のみ発火し、`Rejected`/`Proposed`のままでは指示は未解決のまま残す。`decision_extractor_node`のUPDATE分岐・`_commit_agreement_from_tool`の両経路（Deliverableの状態遷移が起こりうる箇所）から呼び出す。 |
| 影響 | `cela_main.py`（`_resolve_directive_for_task`新設、`decision_extractor_node`・`_commit_agreement_from_tool`への配線）。新規`tests/test_bl073_directive_auto_resolve.py`（4件）で遷移・no-op・両経路の配線を確認。 |
| 関連 BL | [BL-073](issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する) |

---

### D-047: F-7.3ホワイトボードロールバックを撤廃し、部分修正誘導プロンプトへ置き換える

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（F-7.3撤廃・部分修正方式への転換の判断） / Claude Sonnet 5（原因調査・実装） |
| **決定理由** | 実ドライラン（`log/2026-07-24/0647`）継続中、Detector自身がtask_2_3のオペレーター年間有給休暇（一度労基法違反でmajor判定・Ver.2で10日に修正済み）が、別件（法定祝日未考慮）でのmajor判定・ロールバックにより無警告で5日（違反状態）へ後退していることを発見した。原因は`rollback_whiteboard`（F-7.3）が「1つ前のバージョンは健全」という前提でrows[1]（2版前）を機械的に復元する設計だったこと。major判定のたびに指摘内容が変わる実運用下ではこの前提は成立せず、既に修正済みの問題を無警告で再導入する。ユーザーから、F-7.3（およびchat_historyの直前NG発言削除）導入時の背景説明があった：当時は「差し戻されたAIが直前の誤った思考を読んでそれに引っ張られ、結局また誤った結果を出す」という問題が散見されたため、一から考え直させる仕組みにしていた。しかし現在はF-2.6機械的検算ゲート・BL-033監査記録・agreements DBコンテキスト注入・F-2.1思考プロセス監査等でシステムが大幅に強化されており、この古い設計がむしろ矛盾（修正済み問題の再導入）を生む結果となっている。ユーザーは、Word/PDFのコメント機能のように「Detectorが指摘箇所を明示して差し戻し、差し戻されたAIはその指摘とホワイトボードの現状を確認して部分修正に入り、影響範囲が大きい場合のみ周辺も再考する」という理想像を提示し、これを採用した。 |
| 決定内容 | (1) `rollback_whiteboard`関数を削除し、`expert_node`のmajor判定時処理からも呼び出しを削除。ホワイトボードの最新内容は次のExpertターンにそのまま引き継がれる（chat_historyの直前NG発言削除は維持、これは会話フロー上の衛生の話でありホワイトボードの内容基盤とは無関係のため）。(2) `call_expert`のmajor差し戻しプロンプトを、「論理的破綻や計算ミス、制約条件の無視を完全に修正した新しい提案を作成してください」（全文書き直し誘導）から、「現在のホワイトボードはロールバックされていない。Detectorの指摘箇所を特定し、write_agreementのedits（old_text/new_text）で該当箇所のみを部分修正せよ。影響が他箇所に及ぶ場合はその範囲も見直し、必要ならdecision_whatによる全文更新（SUPERSEDE）を使え。既に修正済みだった箇所を無関係な理由で元に戻さないよう注意せよ」という部分修正優先の指示に置き換えた。(3) 副次的に発見した、system_promptへ追記されるがmessagesに一切反映されない死んだコード重複ブロックも削除した。 |
| 影響 | `cela_main.py`（`rollback_whiteboard`削除、`expert_node`・`call_expert`の変更）。新規`tests/test_bl075_no_whiteboard_rollback.py`（4件）、既存`test_r4_smoke.py`のF-7.3専用テスト2件を削除。 |
| 関連 BL | [BL-075](issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する) |

---

### D-048: Detectorのmajor指摘をホワイトボード本文にも永続的な注釈として埋め込む

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（注釈方式の採用・フォーマットのハイブリッド化の判断） / Claude Sonnet 5（技術設計・実装） |
| **決定理由** | D-047でF-7.3ロールバックを撤廃しプロンプト誘導文へ置き換えたが、ユーザーから「それだけでは毎ターン再構成されて消えるプロンプト注入に留まり、AIが見落とす可能性がある。ホワイトボードに直接Detectorの指摘と理由を載せれば永続化されて気づく可能性が高く、指摘箇所も明白になる」との指摘があった。ユーザーはWord/PDFのコメント機能のように「指摘対象の箇所に直接コメントを書き込み、差し戻す」という理想像を提示。技術的には既存のR4差分編集基盤（`_apply_text_edits`と同じ完全一致検索）を転用でき、Detectorに指摘対象の一字一句引用（`target_excerpt`）を追加出力させれば実現可能と判断した。注釈フォーマットは、grep等の将来的なツール拡張への対応も考慮したいというユーザーの要望から、案A（タグ・ID付き、機械可読）と案B（Markdown引用、視認性重視）のハイブリッドを採用した。 |
| 決定内容 | `call_detector`の両パス（ドメイン妥当性レビュー・数値監査）のJSON出力に`target_excerpt`を追加し、実際に採用されたconstraint_issueの重篤度を出した側を優先して統合する。新設`_annotate_whiteboard_with_detector_comment`が、`target_excerpt`がホワイトボード内で一意一致する場合のみ、以下のハイブリッド形式の注釈をその直後に挿入する（一致しない場合は誤った位置への注釈を避けるため挿入しない）：`> 🔴 **[Detector指摘 #D-xxx]**: <指摘内容>` ＋ `> （この注釈は指摘箇所を修正すると同時に削除してください）`。`detector_node`から、Expertの成果物に対するmajor判定時のみ呼び出す。`call_expert`の差し戻しプロンプトに、注釈行を`old_text`に含めて書き換えることで修正と同時に注釈が消えるという運用方法を明記した。 |
| 影響 | `cela_main.py`（`call_detector`のJSON schema拡張、`_annotate_whiteboard_with_detector_comment`新設、`detector_node`・`call_expert`への配線）。新規`tests/test_bl076_whiteboard_detector_annotation.py`（4件）。 |
| 関連 BL | [BL-076](issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式) |

---

### D-049: Orchestratorの専門家選定時の考察を`focus_guidance`としてExpertへ注入する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（提案・実装指示） / Claude Sonnet 5（技術設計・実装） |
| **決定理由** | ユーザーが、Detectorのドメイン妥当性レビューが「プロンプトで監査の観点を変えるだけで仕事ぶりがガラッと変わる」ことに着目し、同じ発想をOrchestrator→Expertの選定フローに応用できないか提案した。`call_orchestrator`は専門家の肩書きを選ぶ過程で既にタスクの中身をある程度見渡して考察しているが、その結果は`reason`（選定理由）としてログに残るのみで、選ばれたExpert自身には一切伝わっていなかった。既存の`reason`フィールドを流用すると「経験豊富だから選んだ」的な選定理由の言い換えになりがちで実行時の注意点にはなりにくいため、`reason`とは別の新フィールドを設けてタスク固有の着眼点・落とし穴を明示的に出力させる方針とした。 |
| 決定内容 | `call_orchestrator`のプロンプトに、専門家選定理由（`reason`）とは別に、「選ばれた専門家AIがこのタスクに実際に着手する際、具体的にどんな観点で検討すべきか・特に見落としやすい落とし穴は何か」を1〜3点、タスク固有の実行可能な指示として出力させる`focus_guidance`フィールドを追加（該当なければ空文字）。`orchestrator_node`が`state["expert_focus_guidance"]`へ保存し（`LineageState`へフィールド追加）、`call_expert`のフル版system_prompt・軽量版light_system_prompt（BL-025②のツールループ自問自答フェーズ用）の両方に`🎯 【このタスクで特に注意すべき観点（Orchestratorより）】`として注入する。 |
| 影響 | `cela_main.py`（`call_orchestrator`のプロンプト・JSON schema拡張、`orchestrator_node`・`call_expert`への配線、`LineageState`フィールド追加）。新規`tests/test_bl078_orchestrator_focus_guidance.py`（4件）。 |
| 関連 BL | [BL-078](issue_backlog.md#bl-078-orchestratorの専門家選定時の考察をfocus_guidanceとしてexpertへ注入する) |

---

### D-050: ホワイトボード注釈のtarget_excerpt一致失敗をBL-074へ統合し、ログ出力＋正規化フォールバックで対応する（リトライ構造はBL-079へ分離）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（統合方針・対策範囲の判断） / Claude Sonnet 5（フォレンジック調査・技術設計・実装） |
| **決定理由** | `log/2026-07-24/1216`のドライランをユーザー依頼でフォレンジック調査した結果、BL-076のホワイトボード注釈機能が、major/assistant判定が複数回発生し`target_excerpt`も正しく出力されていたにもかかわらず一度も発火しておらず、しかも`_annotate_whiteboard_with_detector_comment`が失敗時に`False`を返すのみでログが一切出ないサイレント失敗だったことが判明した。この完全一致依存の脆さはBL-074（Deliverableのtopic文字列ドリフト）と同根の問題であり、ユーザーの判断で別BLに分けず統合することとした。さらにユーザーから「Claude Code自身のEdit（old_text/new_text完全一致）はなぜ実運用でハードルが高くならないのか」という質問があり、調査の結果、(1)LLMがその場で読んだ内容から引用すること、(2)不一致時にツール結果として即座にエラーが返り同一ターン内でLLM自身がリトライできること、の2点が理由と判明した。CELAの現状は(2)を欠いており、ユーザーは他ツール（python_repl等）でエラーフィードバックがあるとDetectorが試行錯誤して解決を試みている思考ログを確認しており、同様の自己修正ループを注釈挿入にも適用すべきと判断した。ただし(2)の実現（Detector自身のツール呼び出しとして注釈挿入を提供し、同一ツールループ内でリトライさせる）はDetectorの既存2パスツールループの設計変更を伴い規模が大きいため、まず即応可能な(1)側の緩和策（正規化フォールバック）とサイレント失敗の解消（理由付きログ）を今回実装し、(2)は別途BL-079として起票・実装は次回とする方針に決定した。 |
| 決定内容 | `_annotate_whiteboard_with_detector_comment`の戻り値を`bool`から`tuple[bool, str]`（成功可否, 理由）へ変更。完全一致に失敗した場合、新設`_normalize_for_loose_match`（改行・空白・Markdown太字記法・全角半角を吸収し、元の文字列位置へのindex_mapを保持）による正規化後の緩い一致へフォールバックし、それでも一意に定まらない場合のみ挿入を諦める。`detector_node`は成功時・失敗時のいずれも理由付きでログ出力する（失敗時: `⚠️ [Whiteboard Annotate Failed]`）。BL-076の「実LLM再ドライランでの効果確認は次回待ち」という完了条件はこの調査により部分的に充足され、同時に脆弱性が発覚したため対策を前倒しで実装した。Detector自身へのフィードバック＆同一ツールループ内リトライの構造化はBL-079として別途起票し、本決定のスコープ外とする。 |
| 影響 | `cela_main.py`（`_annotate_whiteboard_with_detector_comment`の戻り値変更・`_normalize_for_loose_match`新設、`detector_node`のログ配線、`unicodedata`のimport追加）。新規`tests/test_bl074_annotation_loose_match_fallback.py`（5件）、既存`tests/test_bl076_whiteboard_detector_annotation.py`をタプル戻り値に合わせて更新。 |
| 関連 BL | [BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)、[BL-076](issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)、[BL-079](issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる) |

---

### D-051: `write_agreement`のSUPERSEDEがDeliverableの全文更新を破棄していた問題の修正

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（1319ログ調査の依頼、修正・BL起票の指示） / Claude Sonnet 5（フォレンジック調査による発見・技術設計・実装） |
| **決定理由** | ユーザーが「1319の最新ログを見てください。後からtask_1_1のホワイトボードを修正している様子があります」と調査を依頼。調査の結果、Expertが`edits`（old_text/new_text）による部分更新に失敗した後、BL-075で追加した「完全一致が難しければ`decision_what`による全文更新＝SUPERSEDEを使え」という誘導プロンプトに従い`action_type='SUPERSEDE'`で再試行したところ、ツールは`{'success': True}`を返すのに実際にはホワイトボードが一切更新されず、Expertが「システムの反映タイミングの問題」と誤って自己正当化し、Detector/Userからハルシネーションと判定され差し戻され続ける無限ループに陥っていたことを発見した。コードを確認したところ、`_commit_agreement_from_tool`の`SUPERSEDE`分岐は旧agreement行のstatus変更直後に`return None`しており、`decision_what`（全文）を完全に破棄し`apply_whiteboard_patch`も一切呼ばないまま「成功」を返す、実質何もしないツール呼び出しだったことが根本原因と判明した。Detector・Userの「ホワイトボードが更新されていない」という観測自体は正しかったが、原因評価（Expertのハルシネーション）は不正確で、真因はツール実装側の欠陥だった。ユーザーが「修正してBL起票」と即決したため、即時修正した。 |
| 決定内容 | `entry_type=="Deliverable"`かつ`action_type in ("CREATE", "SUPERSEDE")`かつ`len(decision_what) > 200`（CREATE/UPDATEの全文置換パスと同一閾値）の場合、CREATEと同様に`apply_whiteboard_patch`で新版を保存するよう修正。SUPERSEDE分岐からの早期`return None`を削除し、CREATE/UPDATE共通のホワイトボード保存・agreements行INSERT処理へ合流させた。BL-062のDetectorによる無効化用途（短い却下理由のみのSUPERSEDE、ホワイトボードには触れない）は、同じ200文字閾値により後方互換を維持する。 |
| 影響 | `cela_main.py`（`_commit_agreement_from_tool`のSUPERSEDE分岐の修正）。新規`tests/test_bl080_supersede_deliverable_whiteboard_writeback.py`（3件）。 |
| 関連 BL | [BL-080](issue_backlog.md#bl-080-write_agreementのsupersedeがdeliverableの全文更新を破棄し実質何もしないツール呼び出しになっていた)、[BL-075](issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する)（誘因となったプロンプト）、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（無効化用途との後方互換） |

---

### D-052: `write_agreement`の`edits`（old_text/new_text）にも正規化した緩い一致フォールバックを適用する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（再調査の依頼） / Claude Sonnet 5（フォレンジック調査による発見・技術設計・実装） |
| **決定理由** | BL-080修正後、ユーザーが同じ`log/2026-07-24/1319`を指して「やはりまだ、ホワイトボードの差分書き換えに苦労しているようです」と再調査を依頼。ログを精査したところ、ExpertがBL-080の誘因そのものとなった`edits`の完全一致失敗の実例（old_textにMarkdownテーブル行頭の`| `＋全角スペースや行末の` |`が含まれておらず、実際のホワイトボードとの完全一致が0件になっていた）を特定した。BL-074/D-050でDetectorの`target_excerpt`向けに確立した「改行・空白・Markdown太字記法・全角半角を正規化した緩い一致」の仕組みは、Expert自身の主たる編集手段である`_apply_text_edits`には未適用だった。さらに調査の過程で、既存の`_normalize_for_loose_match`自体に「半角スペースは判定前にスキップされ除去されるが、全角スペース（　）はスキップ判定の対象外でNFKC正規化後に半角スペース1文字として結果に残ってしまう」という非対称バグを発見した。これは「同じ意味のはずの全角/半角スペースが正規化後も食い違う」という、正規化フォールバックの前提を掘り崩す欠陥だったため、あわせて修正することとした。 |
| 決定内容 | `_normalize_for_loose_match`を「まずNFKC正規化 → 正規化後の文字が空白かどうかを判定してスキップ」という順序に変更し、全角/半角スペースを対称に扱うよう修正。テーブル区切り記号（`\|`）もスキップ対象に追加。新設`_find_loose_match_spans(content, old_text)`が正規化後の一致箇所を元の文字列上の(開始, 終了)スパンとして返す。`_apply_text_edits`は、完全一致（0件、または複数件でreplace_all未指定）に失敗した場合にこの緩い一致へフォールバックし、それでも一意に定まらない場合のみ理由付きでエラーを返すよう変更した。 |
| 影響 | `cela_main.py`（`_normalize_for_loose_match`の判定順序修正、新設`_find_loose_match_spans`、`_apply_text_edits`のフォールバック追加）。新規`tests/test_bl081_edits_loose_match_fallback.py`（5件）。 |
| 関連 BL | [BL-081](issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)、[BL-080](issue_backlog.md#bl-080-write_agreementのsupersedeがdeliverableの全文更新を破棄し実質何もしないツール呼び出しになっていた)（誘因となった失敗経路）、[BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（同根の正規化手法） |

---

### D-053: task_plannerの計画をplan_draftsとして永続化し、先送り事項をタスク間で申し送る

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（発見・提案・実装範囲の判断） / Claude Sonnet 5（設計・実装、Exploreエージェント調査・Plan agentレビュー） |
| **決定理由** | `log/2026-07-24/1349`のドライランで、User AIがtask_1_3完了判定の中で「積雪・通信エリアの区間切り出しの地形照合はtask_2_1/task_2_2で具体化されるべき」という先送り判断を発言したことをユーザーが指摘し、「この先送り事項は現状消えてしまいますよね？」と質問した。調査の結果、(1) `call_decision_extractor`の「先送りの検出」ルールがExpert側の抽出ブランチにしか実装されておらずUser AI側には存在しなかった（今回の実例はUser AIの発言だったため抽出自体が発動しなかった）、(2) たとえ正しく抽出されても`_build_agreements_context`がentry_type="Directive"を無条件で全除外しており後続タスクには一切見えない（BL-073時代の対症療法の副作用）、という二重の欠陥を発見した。ユーザーが「task_plannerが出した計画もホワイトボード化して、先送り事項を書き込めたりできるようにしたい」と提案し、「設計と実装を進めて最後にBL化」「影響範囲や各ノードでの呼び出し忘れ等十分に気を付けて」と指示した。設計はExploreエージェントによる`state["phases"]`の全消費箇所調査と、Plan agentによる批判的レビューの2段階を経ており、レビューで`call_detector`（既に「先送り済みならmajorにしない」という緩和ロジックを持つが直近2ターンの会話窓のみに依存していた）が当初案から漏れていた第3の呼び出し箇所として発見された。 |
| 決定内容 | `whiteboard_drafts`の完全なミラーとして新規`plan_drafts`テーブルを新設（既存テーブルへの混在によるリスク回避のため別テーブルを選択）。`_append_deferred_note_to_plan`は一括事前シードではなく**遅延生成**を採用（チェックポイント再開時のシード漏れ互換性ギャップを回避するため）。見出し検索は行アンカー付き正規表現＋見出し直後への固定挿入方式を採用し、「次の見出しまで探す」区間検出ロジックは使わない（タスクの`description`・申し送りテキストいずれもLLM生成の自由文であり、偶然の部分一致・境界誤認リスクを構造的に排除するため）。`decision_extractor_node`が新設`defer_to_task_id`フィールド（Expert・User双方の抽出ブランチに追加、従来の非対称性を解消）を解決し、対象タスクの計画文書へ追記する。`call_expert`・`generate_user_utterance`・`call_detector`の3箇所全てに`deferred_notes_text`/`_get_deferred_notes_text`を配線した。 |
| 影響 | `cela_main.py`（新設`plan_drafts`テーブル・`get_latest_plan_draft`・`apply_plan_patch`・`_render_plan_skeleton`・`_append_deferred_note_to_plan`・`_get_deferred_notes_text`、`call_decision_extractor`のJSON schema・両抽出ブランチのプロンプト拡張、`decision_extractor_node`の`task_id_to_phase_id`/`task_id_to_task`マップと配線、`_build_task_scope_context`・`call_expert`・`generate_user_utterance`・`call_detector`への埋め込み）。新規`tests/test_bl082_plan_drafts_deferred_notes.py`（11件）。 |
| 関連 BL | [BL-082](issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-073](issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する)（Directive無条件除外の原因となった対症療法） |

---

### D-054: entry_type="Deliverable"のUPDATE/SUPERSEDE対象特定を、topic文字列ではなく(phase_id, task_id)で行う

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（1459ログのレビュー依頼・修正着手の指示） / Claude Sonnet 5（フォレンジック調査による根本原因の特定・設計・実装） |
| **決定理由** | ユーザー依頼で`log/2026-07-24/1459`のドライランをレビューする中で、BL-081（editsの緩い一致フォールバック）実装後にもかかわらず`edits`が2回とも「old_textが現在のホワイトボード内容に見つかりませんでした（正規化後の緩い一致も0件でした）」で失敗している事例を発見。実際に該当箇所を再現テストしたところ、old_text自体はホワイトボード内容と完全に一致しており（127文字、差分0）、BL-081の正規化ロジックには一切問題がないことを確認した。真因は`_commit_agreement_from_tool`のUPDATE/SUPERSEDE分岐が`target_topic`（省略時は自分自身の`topic`にフォールバック）の文字列完全一致で対象agreementを検索していたこと。実ログでExpertは`target_topic`を一度も送らず、しかも呼び出しごとにtopicの言い回しを変えていた（"...確率論的リスク反映版"→"...結論部の数値整合性修正"→"...確率論的リスク反映・修正版"）ため、既存行と一致せず`old_content`が空文字のまま渡され、`_apply_text_edits("", edits)`が常に0件/0件で失敗する構造だった。これはBL-074の完了条件に「Deliverable本体のtask_id識別への切替はまだ`open`」と明記されていた項目そのものであり、BL-081のフォールバック強化だけでは原理的に解決できないことが実害2件で裏付けられたため、今回着手することとした。 |
| 決定内容 | 新設`_find_active_deliverable_agreement(conn, run_id, phase_id, task_id)`が、entry_type="Deliverable"のagreementを`(phase_id, task_id)`（whiteboard_draftsと同じ識別子）で検索し、`status != "Superseded"`の最新行を返す。`_commit_agreement_from_tool`のSUPERSEDE分岐・UPDATE分岐（対象特定・Freezeチェック・最終Superseded化の3箇所）を、entry_type=="Deliverable"の場合のみこの新関数を使うよう分岐。Decision/Directiveは影響範囲を限定するため従来通りtopic文字列ベースのまま変更していない。 |
| 影響 | `cela_main.py`（新設`_find_active_deliverable_agreement`、`_commit_agreement_from_tool`のSUPERSEDE/UPDATE分岐の対象特定ロジック）。新規`tests/test_bl084_deliverable_task_id_identification.py`（5件、1459ログの実際のtopicドリフトパターンを再現）。 |
| 関連 BL | [BL-084](issue_backlog.md#bl-084-entry_typedeliverableのupdatesupersedeがtopic文字列ドリフトでeditsを0件0件失敗させ続けていたbl-074の未着手項目の再発)、[BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（今回解消した「まだopen」の完了条件）、[BL-081](issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)（この修正で真因ではなかったと判明した緩い一致フォールバック） |

---

### D-055: ホワイトボード保存時にDBと並行してMarkdownファイルへ書き出す

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（要望） / Claude Sonnet 5（設計・実装） |
| **決定理由** | ユーザーから「ホワイトボードの中身を保存時にファイルに書き出してほしい」と要望があった。R4以降`whiteboard_drafts`はDB（sqlite）のみに保存されており、中身を確認・diffするにはsqliteクライアントでのクエリが必要で、ドライラン中の目視確認や過去ログのレビュー時に手間だった。 |
| 決定内容 | 新設`_write_whiteboard_to_file`を`apply_whiteboard_patch`のDB INSERT直後から呼び出し、`{log_dir}/whiteboards/{phase_id}_{task_id}_V{version}.md`へバージョンごとに個別ファイルとして書き出す（DBが正、ファイルは`save_deliverable_to_file`と同様のベストエフォート補助資料）。DB側のappend-onlyバージョニング方針に合わせ旧バージョンを上書き・削除しない。BL-027（`MultiLogger`のimport時副作用防止）と同じ理由で、`MultiLogger._instance`が未初期化（テスト/import時）の場合は書き出しをスキップし、`tmp_path`上のDBを使う既存テスト群（BL-080〜BL-084）が本番`log/`配下を汚染しないようにした。 |
| 影響 | `cela_main.py`（新設`_write_whiteboard_to_file`、`apply_whiteboard_patch`への配線）。新規`tests/test_bl085_whiteboard_file_writeback.py`（3件）。 |
| 関連 BL | [BL-085](issue_backlog.md#bl-085-ホワイトボード保存時にmarkdownファイルへも書き出す)、[BL-027](issue_backlog.md#bl-027-cela_mainpyのロガーがimport時点で無条件起動し本番log配下にテスト実行の痕跡が混入する)（同じ理由でのガード先例） |

---

### D-056: 前提エスカレーションをツール呼び出し型で実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（課題の指摘・エスカレーション経路構築の指示） / Claude Sonnet 5（設計・実装、Explore/Planエージェントによる調査・批判的検証） |
| **決定理由** | ユーザーが1459ログの「オンデマンド交通なのに35人乗りバス」矛盾を指摘した後、「そもそも論というか、視座の設計が大事」と、より一般的にExpertが制約自体の妥当性を疑い表明する手段が無い構造上の問題を提起。調査の結果、BL-025のスコープガードレールは他タスクへの越権防止が目的であり「そもそも論」を封じる意図ではないが、結果的に同じ限定された思考空間を作っていることが判明した。表明手段の実装方式として、(a) BL-082の`defer_to_task_id`のようにdecision_extractorの事後推論で検出する方式と、(b) `FREEZE_AGREEMENT_TOOL`のような専用ツール呼び出し方式を比較検討した。後者を採用した理由は、前者が「4つの構造化フィールドを自由対話から事後的に正しく分類できるか」という不確実性と追加LLM呼び出しコストを伴うのに対し、後者は同一ターン内で必須フィールドをその場で確実に取得でき、既存の`FREEZE_AGREEMENT_TOOL`という「小さな専用ツールをTOOL_DISPATCHに追加する」パターンがそのまま再利用できるため。 |
| 決定内容 | 新設ツール`escalate_premise_concern`（Expert・User AI双方が呼べる、narrow channel。ツール説明文自体に「一般的な制約緩和の泣き言ではなく、スコープ外行動の許可でもない」旨を明記しBL-025との非衝突を担保）、`resolve_premise_concern`（User AI専用、却下）、`revise_goal`（User AI専用、承認・ゴール改定）を追加。BL-025のプロンプト文言・ガードレール自体は一切変更していない。新設`goal_escalations`テーブル（単発の意思決定レコード、版管理文書の`plan_drafts`とは性質が異なるため独立テーブル）に永続化し、Expert向け`_get_escalation_status_text_for_expert`（Open/Rejectedのみ）・User AI向け`_get_open_escalations_text`（Open分を提示し今回中の解決を必須化）で各プロンプトへ配線。 |
| 影響 | `cela_main.py`（新設`goal_escalations`テーブル、3ツール定義・実体関数・`TOOL_DISPATCH`登録、`call_expert`/`generate_user_utterance`の配線）。新規`tests/test_bl086_escalation_freeze_goal_revision.py`。 |
| 関連 BL | [BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-025](issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（変更せず維持したスコープガードレール）、[BL-082](issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)（比較検討した事後推論方式の先例） |

---

### D-057: Freeze機構を再有効化し、Detectorのプロンプトに🔒尊重指示を追加する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（Freeze復活の明示的指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | D-045でFreeze機構（`FREEZE_AGREEMENT_TOOL`/`freeze_agreement`/`is_frozen`ガード）は「検証手段のないまま恒久ピン留めするFreezeより、Detectorの正しいmajor判定がApprovedを覆せない矛盾（BL-062）の解消を優先する」判断により、User AIのtoolsから意図的に外され休止していた。しかし今回、User AIが例外を承認しても次のDetector監査で同じ論点が独立に`major`判定→SUPERSEDEされ承認が無限に覆される問題が、エスカレーション解決の実効性を損なうことが判明。調査の結果、Freeze自体（`is_frozen`ガード）はSUPERSEDE/UPDATEをcaller_role非依存でブロックする実装になっており、D-045当時の「Detectorの正しい判断を止めてしまう」という懸念の実体は、`call_detector`のプロンプトが🔒アイコンの意味を一切説明していない（`_build_agreements_context`が視覚的にソート・アイコン付けするだけで、対応する指示文が無い）という別の欠落だったと特定した。これはFreeze自体の設計ミスではなく、Detectorへの伝達漏れであり、両方を直せば両立可能と判断した。 |
| 決定内容 | `FREEZE_AGREEMENT_TOOL`を`generate_user_utterance`のtools（User AI）へ再配線（`revise_goal`の`freeze_agreement_id`引数経由の内蔵Freezeとは別に、User AIが任意のタイミングで単独Freezeも可能にする——D-044のuser限定ゲートが既に安全弁として機能するため）。あわせて`call_detector`の両監査パス（ドメイン妥当性・数値監査）に「🔒Freeze済み項目は人間が既に審議し承認した意図的な例外であり、同じ論点をmajor/minorの根拠にしない（ただし新規の別問題は従来通り厳格に評価し、Freeze項目への軽微な懸念はobservations欄に留める）」という指示を追加。ドメイン妥当性パスは従来agreements_textを一切受け取っていなかったため、新設`_get_frozen_agreements_text`（🔒項目のみの軽量抽出、トークンコスト抑制）で最小限のコンテキストを追加した。 |
| 影響 | `cela_main.py`（新設`_get_frozen_agreements_text`、`generate_user_utterance`のtools追加、`call_detector`両パスへの指示追加）。既存`tests/test_r5_thought_log_freeze_goalshift.py`（14件）は無変更で全件Pass。`tests/test_bl062_detector_supersede.py`の`test_bl062_freeze_tool_removed_from_user_ai_tools`を`test_bl086_freeze_tool_reactivated_in_user_ai_tools`に更新（D-045からの意図的な転換）。 |
| 関連 BL | [BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-062](issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（D-045でFreezeを休止させた原因、今回両立） |

---

### D-058: state["goal"]への部分パッチとGoalShiftEventの新規shift_kind="premise_revision"でゴール改定を実消費化する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（「当初目標を越境しても最適な着地点に到達できるように」との指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | R5で作った`GoalShiftEvent`（`detect_goal_shift`/`goal_shift_events`）は`arbiter_node`の資源再配分判定からしか発火せず、発火してもDB書き込みのみで何も消費しない「書きっぱなし」（BL-065）だった。調査の結果、`state["goal"]`（`LineageState.goal`）は`Annotated[str, _take_latest]`の単一プローズ文字列で、グラフ起動時に一度セットされたきり一度も再代入されておらず、9箇所の消費者（call_expert/call_detector/call_resource_arbiter等）が毎ターン新鮮に再埋め込んでいることを確認した。これはLangGraphの`_take_latest`リデューサーが既にミュータブル対応済みであることを意味し、たった1箇所（User AIの改定処理ノード）で`state["goal"]`を書き換えるだけで残り8箇所が自動的に次ターンから改定後の内容を見るため、個別配線が不要と判断した。`state["goal"]`への改定方式は、全文置換（LLMに長大なゴール文全体を再生成させる）ではなく、Deliverable編集で実績のある`_apply_text_edits`（old_text/new_text方式）の部分パッチを採用した——全文置換はゴール文全体の想定外の欠落リスクを伴うため。 |
| 決定内容 | `revise_goal`ツールが、既存`db_append_goal_shift_event`を使い新規`shift_kind="premise_revision"`（既存の`"constraint_hit"`とは異なる種別として新設、arbiterの資源超過トリガーとエスカレーション解決トリガーを混同しないため）、`triggered_by="Escalation_Resolution"`、`from_goal_state`/`to_goal_state`に実際の改定前後テキスト（arbiterフローのJSON blobとは異なり、生のプローズ文字列）を記録する。ツールハンドラはLangGraph stateに直接触れられないため、`_LAST_WRITE_AGREEMENT_SUCCEEDED`等と同型の「直前アクション」グローバル`_LAST_GOAL_REVISION`＋getterを新設し、`generate_user_utterance_node`が`state["user_wrote_agreement"] = ...`と同じ並びで`state["goal"]`へ反映する。 |
| 影響 | `cela_main.py`（新設`_LAST_GOAL_REVISION`グローバル・`get_last_goal_revision`、`revise_goal`ツールの実体関数、`generate_user_utterance_node`への配線）。GoalShiftEventがBL-063実装以来初めて実効的な発火・消費経路を持つ。 |
| 関連 BL | [BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-065](issue_backlog.md#bl-065-r5で新設したdb永続化情報internal_thought_processgoal_shift_eventsの消費表示経路が未設計)（今回初めて解消した書きっぱなし問題） |

---

### D-059: 「一段上の思考」はプロンプトのモード切替ではなく既存stateの機械的シグナルで強制トリガーし、新規ノードではなくreflection_nodeを拡張する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（Stage 1のみ実装済み、本決定が対象とするStage 5自体は`open`・設計のみ） |
| 決定者 | t-momose（「タスク猛進モードと抽象化モードの動的切替」案を提示） / Claude Sonnet 5（機械的トリガー方式を提案・ユーザー了承） |
| **決定理由** | ユーザーは当初、「今はタスク猛進モード、今は一段上の思考をする抽象化モード」とプロンプトを動的に切り替える案を提示した。しかしBL-086の`escalate_premise_concern`が「ツールを渡し使い方も説明したのに実LLMドライランで一度も自発的に呼ばれなかった」（BL-087で発見）という実例が既にあり、これは「LLMに対して指示文だけでモード切替や自発的なツール想起を期待する」設計が実証済みで弱いことを示している。同じ弱点を「モード」という形で再導入するのは筋が悪いと判断し、指示文への依存ではなく、`state`に既に存在する機械的シグナル（LLMの自己申告に頼らない客観的な閾値判定）でチェックの発火自体を強制する方式を提案し、ユーザーが了承した。ノード新設か既存`reflection_node`拡張かの選択では、このプロジェクトが繰り返し学習してきた「ノード追加のたびにトークン消費・ドライラン時間が増える」というROI上の制約（R4をBL-041より優先した判断等と同根）を踏まえ、`reflection_node`が既に`expert_retry_count>=3`到達時に呼ばれる合流点であることを理由に新規ノードを避けた。 |
| 決定内容 | トリガー条件はOR: (1) 新設`check_global_constraint_near_limit`（既存`check_global_constraint_overrun`は`total_claimed > total_cap`の完全超過のみ検知するため、その手前の「まだ超えていないが実質詰んでいる」状態、`claimed/total_cap`比が閾値（初期値0.9）以上を検知する姉妹関数として追加）、(2) 既存`state["expert_retry_count"] >= 3`（`route_after_expert_detector`が既に"reflection"分岐に使用している値をそのまま流用）。いずれかを満たした場合、`reflection_node`/`call_reflection`（completed/stagnant/continuing判定＋でっちあげ監査を行う既存ノード）に3つ目の監査観点として「現在のアプローチ（手段）そのものが真の目的に対して無理筋になっていないか、代替手段を検討する余地はないか」を追加する。`call_reflection`自体は監査人視点でexpert/userロールを持たないため`escalate_premise_concern`を直接呼べず、懸念が出た場合は次のExpert/User AIターンのシステムプロンプトへ申し送り、Expert/User AI自身に`escalate_premise_concern`を呼ばせる動線とする（BL-082の申し送り機構と同型のパターン）。 |
| 影響 | `cela_main.py`（Stage 5実装時に`check_global_constraint_near_limit`新設、`call_reflection`のプロンプト拡張、申し送り機構の新設が必要。本決定時点では未実装）。 |
| 関連 BL | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage 5として記録、実装は`open`）、[BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（`escalate_premise_concern`が自発的に呼ばれなかった実例、本決定の出発点） |

---

### D-060: 「本質フェーズ」（Stage3）はBL-086のエスカレーション経路と統合せず独立させ、9消費者すべてへ機械的に注入する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（Stage3/4の実行を指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | Stage2完了後、ユーザーからStage3（本質フェーズ）・Stage4（Detector/User AI拡張）の実行指示を受けた。事前に提示していた設計案通り、「本質フェーズ」（事前予防、計画開始前に1回だけ目標の本質を言語化）と、BL-086の`escalate_premise_concern`/`revise_goal`（事後保険、走行中に前提矛盾に気づいた際のエスカレーション）は統合せず独立・併存させる方針をそのまま踏襲した。統合しなかった理由は、両者が防ぐ失敗モードの時間軸が異なるため（本質フェーズは計画そのものが本質から外れて生成されることを防ぐ「事前」対策、BL-086は計画は妥当でも実行中に矛盾が判明した場合の「事後」対策）、無理に1つの機構にまとめると却って「いつどちらが発火すべきか」の判定ロジックが複雑化すると判断した。注入範囲については、BL-086のD-058で既に「`state["goal"]`は9箇所の消費者が毎ターン再埋め込みする」という事実が特定されていたため、同じ9箇所（`call_orchestrator`/`call_expert`/`call_detector`〈2パス〉/`call_reflection`/`generate_user_utterance`/`call_resource_arbiter`/`call_facilitator`/`call_integrator`/`call_reviewer`）へ本質テキストも機械的に注入することで、D-058が既に確立した「ゴール文の消費経路」という設計上の合意点をそのまま再利用し、独自の一部箇所だけへの注入という中途半端な対応を避けた。 |
| 決定内容 | 新設`goal_essence`テーブル（`run_id`単位1行）・`call_goal_essence_analyst`・`goal_essence_node`をグラフの新しい`entry_point`とし、`state["goal_essence_done"]`で冪等ガード（`task_plan_reviewer_node`の`plan_review_done`と同型）。新設`_get_goal_essence_text(conn, run_id)`を、`state`を直接持つ5関数は自分で呼び出し、`goal`のみを引数に取る4つの「純粋関数」（`call_resource_arbiter`/`call_facilitator`/`call_integrator`/`call_reviewer`）は新設`goal_essence_text: str = ""`引数を追加し、呼び出し元ノードから渡す形にした（これらの関数にDBアクセスを持ち込まず、既存のシグネチャの素性を保つため）。Stage4は、Detectorのドメイン妥当性パスと`generate_user_utterance`の両方に、本質と数値・条件設定の整合性チェック観点を追加するに留め、BL-069本体（Expertのフェーズ・タスク表活用）への統合は行わなかった（BL-069は別途、Expert側のスコープガードレールとの緊張関係の検討が必要なため）。 |
| 影響 | `cela_main.py`（新設`goal_essence`テーブル・`db_save_goal_essence`/`get_goal_essence`/`_get_goal_essence_text`・`call_goal_essence_analyst`・`goal_essence_node`、9箇所の注入配線、Detector/User AIへの本質整合性チェック指示追加）。新規`tests/test_bl087_stage3_4_goal_essence.py`（21件）。 |
| 関連 BL | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage3・4として実装）、[BL-086](issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（D-058の9消費者を再利用、独立併存の対象）、[BL-069](issue_backlog.md#bl-069-expertが決定前にフェーズタスク表全体を見渡して他フェーズとの資源競合に気づけるよう軽量な指示を追加する)（Stage4の一部が合流、本体は別途） |

---

### D-061: task_plan_reviewerの過剰な精度要求を較正し、plan_draftsへのタスク単位注釈はexcerpt一致ではなくtask_idキーで実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（実ドライラン`log/2026-07-25/1549`のレビューから3点の改善を指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | Stage2完了後の実ドライランで、`task_plan_reviewer_node`が`task_1_3`の推定値（「山間部2km≒ルート全体13.33km」、原文12kmとの端数差はごくわずか）を「矛盾」としてmajor判定し差し戻した結果、再生成されたtask_plannerが「山間部12km＝ルート全体の15%」という原文からは読み取れない解釈で「総ルート長80km」というゴール文に存在しない数値をでっち上げる実例が観測された。ユーザーはこれを「Reviewerが過敏すぎる」「数字だけでなくタスクの漏れや順序の不備も同等に大事」と評し、較正（プロンプトの重み付け見直し）で対応する方針を示した。plan_draftsへの注釈方式については、Detectorの`_annotate_whiteboard_with_detector_comment`（文中excerpt一致、正規化フォールバック付き）を素朴に踏襲する案も検討したが、(a) plan_draftsの読み手は基本的に次のtask_planner呼び出し（LLM）であり、機械的な文字列一致より「どのtask_idの話か」というID照合の方が構造的に頑健である、(b) BL-074/076で「LLM生成の自由文に対する引用文字列マッチング」の脆さが繰り返し問題化した経緯があり、task_idという既存の確実なキーが使える場面でわざわざ同じ脆さを持ち込む理由がないと判断し、task_id単位のセクション追記方式（`_append_deferred_note_to_plan`の完全なミラー）を採用した。 |
| 決定内容 | (1) `call_task_plan_reviewer`のプロンプトに、4評価観点（曖昧表記/タスク過不足/順序妥当性/条件の明示〈新設〉）を同等以上に重視する指示と、「ゴール文が与えていない絶対値を無理に確定させる差し戻しをしない」というアンチパターンを80km捏造の実例付きで追記。(2) `call_task_planner`に「派生値には根拠条件を併記」する項目6を新設し、`call_task_plan_reviewer`にも対応する評価観点を追加。(3) `_render_plan_skeleton`に「レビュワーからの指摘（要修正）」セクションを追加し、新関数`_append_reviewer_comment_to_plan`でtask_id単位の注釈を書き込む。`task_planner_node`は計画生成直後に全タスク分のスケルトンを事前生成し（従来の遅延生成のみでは、Reviewerが動く時点で書き込み先が存在しなかった）、`call_task_plan_reviewer`の出力に`per_task_comments`を追加、`task_plan_reviewer_node`がタスク別指摘を`plan_drafts`へ書き込みつつ`plan_reviewer_feedback`にも整形結合する。副次的に、セクション追加により`_get_deferred_notes_text`の抽出範囲（従来は文書末尾まで）が新セクションの内容を巻き込むバグが発生したため、次見出しの直前までに限定する修正も行った。 |
| 影響 | `cela_main.py`（`call_task_plan_reviewer`・`call_task_planner`のプロンプト、`_render_plan_skeleton`・`_append_reviewer_comment_to_plan`・`_find_phase_id_for_task`・`_find_task_by_id`の新設、`_get_deferred_notes_text`の範囲限定修正、`task_planner_node`・`task_plan_reviewer_node`の配線）。`tests/test_bl087_stage2_task_plan_reviewer_node.py`に11件追加（計21件）、`tests/test_bl082_plan_drafts_deferred_notes.py`の1件を新セクション追加に合わせて修正。 |
| 関連 BL | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage2改善、項目17〜21）、[BL-082](issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)（`plan_drafts`拡張元） |

---

### D-062: `_safe_json_parse`の開始位置探索は`{`優先ではなく、先に現れる方（`min()`）を採用する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | Claude Sonnet 5（`log/2026-07-25/1642`レビュー中に発見・原因特定・修正案を提示） / t-momose（「直して」と修正を指示） |
| **決定理由** | D-061で較正した`task_plan_reviewer_node`の効果を確認するため`log/2026-07-25/1642`をレビューしたところ、1〜2回目のtask_planner出力が実際には5〜6フェーズの正しい計画だったにもかかわらず、レビューに渡っていたのは`call_task_planner`の`fallback_phase`（縮退した1タスク計画）だったことが判明した。原因は`_safe_json_parse`の開始位置探索が`brace_idx != -1`を`bracket_idx`より無条件に優先しており、トップレベルが配列（`call_task_planner`のfallbackはlist）かつコードフェンス直前に説明文が付く応答（LLMの一般的な癖）の場合、配列を開く`[`より後にある最初のオブジェクトの`{`から誤って開始し、構文的に不正なJSONとなってフォールバックに握りつぶされていたことだった。`call_task_planner`は`_query_and_parse_with_retry`（層2リトライ、パース失敗時に同一呼び出しを再試行する既存の防御機構）を経由しない実装だったため、パース失敗が即座にfallback確定となり、さらにBL-087 Stage2の差し戻し上限（2回）と組み合わさって、内容面の問題が皆無なまま2回の差し戻し予算を本バグだけで使い切っていた。修正方針は「`{`/`[`のうち`-1`でない方の最小値を採用する」という最小限の変更とし、既存の他の呼び出し（dict fallbackのDetector系等）の挙動に影響しないことを回帰テストで確認した上で採用した。 |
| 決定内容 | `_safe_json_parse`（`cela_main.py`）の該当箇所を`start = brace_idx if brace_idx != -1 else bracket_idx`から、`{`/`[`のうち`-1`でない値の`min()`を取る形に変更。新規`tests/test_bl088_safe_json_parse_bracket_precedence.py`（3件）で、(1)`1642`ログの実際の失敗パターンの再現確認、(2)トップレベルがオブジェクトの通常ケースが従来通り動作することの回帰確認、(3)`{`も`[`も含まれない完全な非JSON応答でfallbackを返すことの確認、を行った。 |
| 影響 | `cela_main.py`（`_safe_json_parse`のみ、他の呼び出し箇所への配線変更は無し）。現時点でこのバグの影響を受けるのはトップレベルが配列の`call_task_planner`のみだが、`_safe_json_parse`は汎用ユーティリティであり将来list-fallbackの呼び出しが増えた場合の予防にもなる。 |
| 関連 BL | [BL-088](issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)、[BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（本バグにより差し戻しリトライ予算が無駄撃ちされていたのを発見した経緯） |

---

### D-063: task_plannerの重複再確認を抑制する指示を追加し、MAX_TOOL_ITER自体は変更しない

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | Claude Sonnet 5（`log/2026-07-25/1705`レビュー中に発見・原因特定・修正案を提示） / t-momose（「お願いします」と修正を指示） |
| **決定理由** | `log/2026-07-25/1705`をレビューしたところ、task_plannerが`MAX_TOOL_ITER=15`（BL-014/BL-028で5→10→15と引き上げられた、全`query_AI`呼び出し共通のグローバル安全弁）を使い切り、最終iteration（ツール利用不可、テキスト応答強制）で26タスク分のJSON全体を一括出力させられていた。実際の`python_repl`呼び出し14回の内容を精査した結果、前半9回は正当な数値計算だったが、終盤5回は「acceptance_criteriaが3個以内か」「depends_onの整合性」といった、新しい情報を生まない同一内容の「念のため最終確認」の繰り返しだったと判明した。今回はぎりぎり出力が完了したが、より大きな計画やStage2の再生成時（今回のプロンプトはStage1・Stage2改善で【重要】項目が6つに増えており、遵守すべきチェック項目が増えたことが再確認欲求を強めた可能性がある）に同じ現象が起きれば、最終出力の途中でトークン切れとなり、BL-088と同じ被害形態（fallback化）に陥るリスクがあると判断した。対応方針としては、`MAX_TOOL_ITER`自体を引き上げる案も考えられたが、これはAGENTS.md §7（重要な定数の変更には事前承認が必要）の対象であり、かつBL-014/BL-028の過去の教訓（全回がtool_callsを返すと非収束になる）を踏まえると、上限を上げるより「同じ検証を繰り返させない」という根本原因側の対策の方が、あらゆるノードに影響する共有定数を動かすより副作用が少なく、対象を`call_task_planner`のプロンプトに限定できると判断した。 |
| 決定内容 | `call_task_planner`のプロンプトに項目7「【計算・検証は各回1回まで、繰り返し確認しない】」を追加し、同一内容の再確認をせず検証完了後は直ちに最終JSON記述に移るよう明示した。`MAX_TOOL_ITER`自体は変更しない。新規テスト1件を`tests/test_bl087_task_planner_prompt_and_resubmission_fix.py`へ追加（計4件）。 |
| 影響 | `cela_main.py`（`call_task_planner`のプロンプトのみ）。実LLMドライランでの効果測定（終盤の重複確認が減り、より早い段階でJSON出力に移るか）は次回ドライラン待ち。 |
| 関連 BL | [BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（項目22）、[BL-088](issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)（同じ被害形態＝fallback化の別トリガーとして関連） |

---

### D-064: `_safe_json_parse`は複数フェンスブロックのうち最後を採用し、計画系3関数を層2リトライで包み、レビューはフェイルクローズする

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | Claude Sonnet 5（`log/2026-07-25/1814`レビュー中に発見・原因特定・修正案を提示） / t-momose（「OK 修正してください」と修正を指示） |
| **決定理由** | BL-088修正後の再ドライラン（`log/2026-07-25/1814`）で、task_plan_reviewerが縮退計画を正しく"major"と判定していたにもかかわらず、その応答が「プレビュー用の配列ブロック」と「最終JSON出力の完全なオブジェクトブロック」という2つの```json```ブロックで構成されていたため、`_safe_json_parse`が両者を混線させ構文エラーとなり、fallback（"none"）に化けて縮退計画がそのまま承認・実行される事故を発見した。BL-088は「フェンスが1つだけ、その前に説明文がある」ケースへの対処だったが、今回は「フェンスが複数ある」という別のケースであり、根本原因は同じ（`_safe_json_parse`が「JSONブロックは応答中にちょうど1つ」という前提でしか設計されていなかったこと）と判断した。修正方針は、個別のケースにパッチを重ねるのではなく、正規表現で応答中の全フェンスブロックを検出し「最後のブロックを採用する」という一般則に統一することとした（モデルは下書き・プレビューを先に書き、最終的な答えを最後に書く傾向があるため）。あわせて、`call_task_plan_reviewer`が単発のパース失敗で即座にfallbackへ落ちていたこと自体も問題と判断し、`call_reviewer`が既に採用していた層2リトライ（`_query_and_parse_with_retry`、D-005）を`call_task_planner`・`call_goal_essence_analyst`にも展開した。特に`call_task_plan_reviewer`は実行前の安全ゲートであるため、リトライを使い切った場合のfallbackを`"none"`（フェイルオープン）のままにしておくのは危険と判断し、`call_reviewer`の既存のフェイルクローズパターン（`passed=False`）を踏襲して`"major"`（フェイルクローズ）に変更した。`call_task_planner`自体は、後段の`task_plan_reviewer_node`が縮退計画を検知してmajor判定する前提が既にあるため、fail-closed化は不要と判断し従来のfallback_phaseのままとした。 |
| 決定内容 | (1) `_safe_json_parse`の段階1を、`re.finditer`で全```(?:json)?...```ブロックを検出し`fence_matches[-1]`（最後のブロック）を採用する方式に変更（フェンスが無ければ従来のbrace/bracket探索へフォールバック）。(2) `call_task_plan_reviewer`・`call_task_planner`・`call_goal_essence_analyst`を`_query_and_parse_with_retry`でラップ（`max_retries`はデフォルトの2のまま）。(3) `call_task_plan_reviewer`はリトライ失敗後に`{"risk": "high", "constraint_issue": "major", ...}`を返すフェイルクローズ処理を追加。新規`tests/test_bl089_json_fence_and_failclosed_review.py`（8件）。 |
| 影響 | `cela_main.py`（`_safe_json_parse`、`call_task_plan_reviewer`、`call_task_planner`、`call_goal_essence_analyst`）。`call_task_planner`は既存の`tools=[PYTHON_REPL_TOOL]`付きツールループのため、リトライ発生時は最大3回分（1回目＋リトライ2回）のツールループを再実行しうる（コスト増だが、パース失敗自体が稀になる前提のBL-088/089修正後は発生頻度が下がる想定）。 |
| 関連 BL | [BL-089](issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)、[BL-088](issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)（同根の`_safe_json_parse`脆弱性、今回一般化して解消） |

---

### D-065: 重複再検証の抑制指示は、tools付きの全ノードへ横展開する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（「他のノードも何回も何回も同じ思考を繰り返しすぎることが多々ありました」と指摘・横展開を指示） / Claude Sonnet 5（対象関数の洗い出し・実装） |
| **決定理由** | D-063でtask_plannerにのみ追加した「同じ検証・計算を繰り返さない」指示について、ユーザーから他のノードでも同様の重複再検証が繰り返し観測されていたとの指摘があった。対象範囲を検討した結果、この問題（同一内容をpython_replで何度も再確認し、ツールループの残り予算を浪費する）は、そもそも`tools=[...]`でツールループ自体を持つ関数にしか起こりえない（`tools=None`の関数は`query_AI`の単発ストリーミング経路を通り、MAX_TOOL_ITERの概念自体が存在しないため）と判断し、`query_AI`呼び出し箇所を全数調査した。該当したのは`call_expert`・`call_detector`（主検算パスのみ、ドメイン妥当性パスは`tools=None`）・`call_resource_arbiter`・`call_integrator`・`call_reviewer`・`generate_user_utterance`・`call_goal_essence_analyst`・`call_task_plan_reviewer`の8関数（`call_task_planner`は対応済み）。`call_orchestrator`・`call_decision_extractor`・`call_reflection`・`call_facilitator`は`tools=None`のため対象外とした。`call_detector`には既に「判定のブレ防止（3回多数決方式）」という類似目的の指示があったが、これは"constraint_issueの判定"という結論の揺れを防ぐものであり、"同一の数値検算をpython_replで何度も繰り返す"こと自体への対策ではないため、重複させず補完する形で別途追加した。 |
| 決定内容 | 上記8関数のプロンプトに、「同じ検証・計算を繰り返さない（重要）」という共通の指示文（ツール呼び出しの回数に上限があること、各検証項目は2回程度で十分なこと、新しい論点が無い「念のため最終確認」を重ねると出力が途中で切れるリスクがあること、検証完了後は直ちに最終出力に移ること）を追加した。文言は関数ごとの出力形式（JSON配列/JSONオブジェクト/自然文+ツール呼び出し）に合わせて微調整した。`call_task_plan_reviewer`には、`1814`で発見した複数JSONブロック混線（D-064）の再発防止として、「最終回答のJSONブロックは1つだけ」という指示も追加した。新規`tests/test_bl089_anti_repetition_instructions.py`（9件、対象8関数＋task_plannerの回帰確認）。 |
| 影響 | `cela_main.py`（8関数のプロンプト文字列のみ、ロジック変更なし）。実LLMドライランでの効果測定（各ノードの平均ツール呼び出し回数が減るか）は次回ドライラン待ち。 |
| 関連 BL | [BL-089](issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)、[BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（項目22、D-063が横展開の出発点） |

---

### D-066: goal_essence_analystのJSON文字列値は、末尾を全角鉤括弧で終えないよう予防指示する（実害はD-064の層2リトライで既に吸収済み）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（`log/2026-07-25/1913`のレビュー結果を共有し「L424 全角「」によるJSON破損: これは修正」と指示） / Claude Sonnet 5（原因特定・修正） |
| **決定理由** | BL-089修正後のドライラン（`1913`）で、`call_goal_essence_analyst`の応答が`feasibility_notes`文字列値の末尾を全角鉤括弧「」で終えており、JSON構文上の閉じ引用符(")そのものを書き忘れていた（`_safe_json_parse`がパース失敗）。D-064で追加済みの層2リトライが1回で自己修復したため実害は無かったが、ユーザーからは根本原因（プロンプト側でこの引用符の使い方を禁止していなかったこと）を修正するよう明示的な指示があった。層2リトライという安全網はBL-089で既に用意済みだが、そもそもパース失敗の発生頻度自体を下げる方が、リトライによるレイテンシ・コスト増を避けられるため、対症療法（リトライに任せる）ではなく発生源側のプロンプト修正を選んだ。 |
| 決定内容 | `call_goal_essence_analyst`のプロンプトに、JSON文字列値の**末尾**を全角鉤括弧「」『』で終えないよう明記する指示を追加（強調は文中に置くか、末尾は句点等の通常の文字にするよう指示）。他の7関数（同種のJSON出力を行う`call_expert`等）への横展開は、本件が`1913`ログで1回のみの観測であり、D-064の層2リトライで実害なく吸収されている以上、緊急性は無いと判断し見送った。同種の事象が別関数で再発した場合に改めて横展開を検討する。 |
| 影響 | `cela_main.py`（`call_goal_essence_analyst`のプロンプト文字列のみ、ロジック変更なし）。新規`tests/test_bl090_json_string_fullwidth_quote_guard.py`（1件）。 |
| 関連 BL | [BL-090](issue_backlog.md#bl-090-goal_essence_analystがjson文字列値の末尾を全角鉤括弧で終え閉じ引用符を書き忘れる)、[BL-089](issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)（D-064の層2リトライが実害を吸収した安全網） |

---

### D-067: write_agreementの成否をDetectorへ明示し、モデルの偽ツール呼び出し風テキストを鵜呑みにさせない

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（`log/2026-07-25/1913`の続きをレビューし「detectorがホワイトボードを更新できないまま、事故が起きました」と報告、「BL起票と...修正して」と指示） / Claude Sonnet 5（原因特定・修正） |
| **決定理由** | task_2_1の3回目修正で、Expertのwrite_agreement(edits)が失敗→最終iterationでツール強制排除→モデル（DeepSeek系）が独自のツール呼び出し風疑似XML（`<｜DSML｜tool_calls>...`）を平文出力、という経路で、実際には一切実行されていない（システム自身が`get_last_write_agreement_succeeded()=False`と正しく記録）更新をDetectorが鵜呑みにして誤って承認し、Decision Extractorも虚偽のUPDATEをDBに記録する事故を発見した。`call_detector`は既に現在の最新ホワイトボード内容（`whiteboard_block`、唯一の真実）を提示していたが、それと会話ターンの「主張」を突き合わせて食い違いに気づくことをモデルの注意力だけに委ねており、構造的な保証が無かった。BL-033で確立した「Expertの自己申告（python_repl未使用でも書けてしまう）を鵜呑みにせず実行記録と突き合わせる」という設計思想の、write_agreement版の欠落と判断した。既存の`state["expert_wrote_agreement"]`/`state["user_wrote_agreement"]`フラグ（R3b §3.5.1で既に実装済み、decision_extractor_nodeの一部でのみ消費されていた）をそのままDetectorへ渡せば実装できるため、新規のDB永続化や状態追加は不要と判断した。 |
| 決定内容 | `call_detector`のドメイン妥当性レビュー・数値監査の両プロンプトに、今回のターンでwrite_agreementが実際に成功したか（target_roleに応じて`expert_wrote_agreement`/`user_wrote_agreement`を選択）を明示する`write_agreement_status_block`を追加。失敗している場合は「相手の発言内容がどれだけ説得力があっても実際には反映されていない。上記の最新ホワイトボードのみが唯一の真実であり、食い違う場合はconstraint_issue="major"とすること」と明記した。ドメイン妥当性レビュー（今回、物理的整合性の誤判定を実際に行った当事者）にも同じブロックを配線した。新規`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`。 |
| 影響 | `cela_main.py`（`call_detector`のプロンプト文字列のみ、ロジック変更なし）。実LLM再ドライランでの効果確認（同種の偽ツール呼び出しテキストが再発した場合の検出）は次回待ち。 |
| 関連 BL | [BL-091](issue_backlog.md#bl-091-write_agreementの成否をdetectorへ明示せずモデルの偽ツール呼び出し風テキストを鵜呑みにして誤って承認していた)、[BL-033](issue_backlog.md#bl-033-expertがpython_repl未使用のまま検算完了と虚偽申告できるf-26監査フラグに強制力がない)（同型の先行対策） |

---

### D-068: ホワイトボード注釈のtarget_excerpt一致は、挿入自体のツール化ではなく事前検証ツール＋プログラム側フォールバックで担保する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（BL-079も含めて修正するよう指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | BL-079の当初構想（注釈挿入`_annotate_whiteboard_with_detector_comment`自体をDetector自身が呼べる新規ツール化する）を実装検討したところ、実際の挿入処理が`decision_id`（`detector_node`側で両パス完了後に発行）を必要とし、Detectorのツールループ実行中にはまだ存在しないという設計上の制約に直面した。これを解決するには`decision_id`発行タイミングの前倒しという大きめの変更が必要になり、BL-079が当初から懸念していた「規模が大きい」問題が実際に顕在化した。全面的な再設計を避け、実利的に「一致失敗をDetector自身にフィードバックし、同一ツールループ内で調整・再試行させる」というユーザーの核心的な要望を満たすため、挿入とは切り離した「検証専用」の軽量ツールに設計を縮小した。 |
| 決定内容 | 新規ツール`verify_whiteboard_excerpt`（書き込みは行わず、完全一致→正規化緩い一致の2段判定でok/ngのみ返す）をDetectorの数値監査パス（tools付き）に追加。ドメイン妥当性レビュー（tools=None、BL-054で意図的に検算から切り離された軽量パス）はこのツールを呼べないため、target_excerpt統合ロジック（`call_detector`）に、severityで優先された側の引用が実際には一致しない場合、もう一方の（一致する可能性が高い）引用へプログラム的に差し替えるフォールバック（`_excerpt_matches_uniquely`）を追加し、ドメイン側単独の弱点を補った。ドメイン妥当性レビュー自体にtoolsを持たせる（BL-054の設計を変更する）ことはスコープ外とした。 |
| 影響 | `cela_main.py`（新規`VERIFY_WHITEBOARD_EXCERPT_TOOL`/`_verify_whiteboard_excerpt_handler`/`TOOL_DISPATCH`登録、`call_detector`のtools・プロンプト・target_excerpt統合ロジック）。実LLM再ドライランでの効果確認（`Whiteboard Annotate Failed`の発生頻度低下）は次回待ち。 |
| 関連 BL | [BL-079](issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる)、[BL-074](issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合) |

---

### D-069: BL-092への対応は、ホワイトボードのファイル化ではなく、既存DB版履歴への機械的diff導入で行う

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-25 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（「ファイルに書き出してdiffツールを使った方がやりやすいのでは」と提案 / 「OK修正して」と実装を指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | BL-092（reviewerの差し戻し圧力に対しtask_plannerが数値の検算・訂正ではなく該当箇所の削除・抽象化で「解消」してしまう問題）への対応として、ユーザーから「DBをマスターの保存場所とし、編集中はホワイトボードをファイル編集で扱う方が、diffツール等を使いやすいのでは」という提案があった。検討の結果、(1) LLM（Expert/reviewer）はサンドボックス化されたpython_replしか持たずファイルI/Oができないため、編集の主軸をファイルへ移しても実際の編集経路はDB経由のツール呼び出しのまま変わらない、(2) 機械的diff自体はDB内の文字列同士に`difflib`を適用するだけで実現でき、ファイル化は必須の前提ではない、(3) ファイルパス・ファイル名を頼りに識別する設計は、BL-074（topic文字列ドリフト）・BL-034（承認前の無条件ファイル保存で孤児ファイル残存）・BL-040（タイムスタンプ付きファイル名をAIが68%の確率でnot_found）で既に痛みを伴って解決済みの脆さであり、編集の主軸をファイルに戻すとこれらを再導入するリスクがある、と判断した。ユーザー提案の核心（機械的diffによる客観的検証）はDB版履歴＋`difflib`だけで達成できるため、ストレージ方式自体は変更しない方針とした。 |
| 決定内容 | 新規ツール`diff_plan_draft_versions`（`plan_drafts`の同一task_idについて`author_role='task_planner'`の版を版番号順に取得し、直近2件間の`difflib.unified_diff`を返す、書き込みなしの読み取り専用）を`call_task_plan_reviewer`のtoolsに追加。プロンプトに、以前指摘したtask_idについては記憶・印象で判断せずこのツールで機械的差分を確認し、「数値が訂正された」のか「記述ごと消えた」のかを区別してから判断する旨を明記した。ホワイトボード自体（BL-085で既にファイル書き出し済み、DBが正・ファイルは補助）の運用方針は変更していない。 |
| 影響 | `cela_main.py`（新規`DIFF_PLAN_DRAFT_VERSIONS_TOOL`/`_diff_plan_draft_versions_handler`/`TOOL_DISPATCH`登録、`call_task_plan_reviewer`のtools・プロンプト）。実LLM再ドライランでの効果確認（reviewerが実際にツールを使い「削除による解消」を検出できるか）は次回待ち。 |
| 関連 BL | [BL-092](issue_backlog.md#bl-092-reviewerの差し戻し圧力に対しtask_plannerが数値の検算訂正ではなく該当箇所の削除抽象化で解消してしまう)、[BL-087](issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Fix Aと逆方向の問題） |

---

### D-070: ノード内スクラッチパッド機構は、decision_list/要約圧縮を廃し`global_working_notes`（全文上書き型）のみに縮小する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `superseded`（[D-072](decision_log.md#d-072-thinkツールの最終仕様を確定するthink専用ツールに理由づけの構造化フィールドtodoとissuesのopenclosed必須notesの追記専用化を持たせる)で訂正・確定。本エントリの「reasoning消失は実害がない」という判断根拠自体が誤りだったため） |
| 決定者 | t-momose（別チャットでの議論を持ち込み検討を主導。「iteration間のコンテキスト引き継ぎは盛大な勘違いだった」と当初の問題意識を撤回し、「working_notesだけまずはBL化して設計して」と指示） / Claude Sonnet 5（技術検証・設計） |
| **決定理由** | 別チャットで「各ノードのquery_AI呼び出しに思考フレームワーク＋スクラッチパッドを持たせる」構想が提案され、動機として「ツールループの`_StreamMessage`がモデルのreasoningを`None`固定で捨てており（[cela_main.py:1958-1969](../../cela_main.py#L1958-L1969)）、次iterationでモデルは前回のtool_calls/tool結果という骨組みだけから理由を再構築している」という技術的事実を確認した。これに対しthink専用ツール（tool_calls＋tool結果の構造化ペアとして確実にloop_messagesへ残る、Anthropic公式の"think tool"パターン）が有力と判断しかけたが、さらなる発展案（直前1iter生ログ＋要約リスト＋decision_list＋global_working_notes、システム側で毎iterationダイジェストを組み立てる方式）が出た時点で検証したところ、`loop_messages`はそもそも一度もtruncateされず全履歴を毎iteration再送する実装であり（かつMAX_TOOL_ITER=15という短い上限があるため）、reasoning以外の情報（tool_callsの引数含む）は何もしなくても既に全iteration分保持されていることが判明した。要約/windowing機構は「短いループには過剰設計」という、この発展案自身がパターン4（構造化出力＋要約圧縮）を退けた論理と矛盾しており、解決すべき問題が実質存在しない。`decision_list`（decided/why/rejected）も`write_agreement`が`agreements`テーブルへ既に構造化永続化している内容と重複する。さらにユーザー・別チャット側で「iteration間のコンテキスト引き継ぎ自体はReAct定石通り欠落なく機能している」との訂正があり、当初の問題意識（reasoning消失による機能不全）自体が撤回された。撤回後も残る価値は、append-onlyのtool呼び出し履歴では表現できない「今のtodo/issueの状態」を上書き更新できる可変メモ（`global_working_notes`）のみであり、これに機構をスコープダウンする。 |
| 決定内容 | 新規ツール`update_working_notes`（引数`notes: string`、常に全文上書き・差分ではない）のみを新設する。ハンドラは永続化しないno-op（`{"ok": True}`的な応答のみ）とし、ツールループ本体は無改修のまま既存の`loop_messages`再送に乗せる。配線先はDetector数値監査パス・`call_task_planner`・`call_task_plan_reviewer`の3箇所に限定（Expert/User対話ノードは高頻度でコストに見合わないため対象外）。プロンプトには「全文上書き（差分ではない）」「MAX_TOOL_ITER予算節約のため実際の検証ツール呼び出しと同一応答内でまとめて呼ぶこと」を明記する。差分パッチ方式（ホワイトボードの`edits`と同型）への移行は、全文上書き方式の実測結果を見てから判断する（BL-074/076/079で判明した一意引用一致の脆さを、低スコープのスクラッチパッドに最初から持ち込む必要は薄いと判断）。 |
| 影響 | `cela_main.py`（新規`update_working_notes`ツール・ハンドラ・`TOOL_DISPATCH`登録、`call_detector`/`call_task_planner`/`call_task_plan_reviewer`のtools・プロンプト）は未実装。本エントリは設計決定の記録のみで、実装はユーザーの明示的な承認後に着手する。 |
| 関連 BL | [BL-093](issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-071: MAX_TOOL_ITERを15から20へ引き上げ、thinkツールの単独呼び出しを許容する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided` |
| 決定者 | t-momose（think単独呼び出しを許容する方針を明言した上で、AskUserQuestionによる選択肢提示から「20へ引き上げ」を選択・承認） / Claude Sonnet 5（AGENTS.md §7準拠で事前に理由を提示し承認を仰いだ） |
| **決定理由** | BL-093のthinkツールについて、ユーザーから「python_repl等の実作業ツールと同一応答内でまとめて呼ぶ」というバンドル必須ルールではなく、thinkツール単体でも自由に呼び出せるようにすべきという指示があった（ReAct本来の「思考・作業を可能な限り短く切り、軽量な作業単位を繰り返す」設計を優先し、必要ならiteration上限を引き上げる、という考え方）。単独呼び出しを許容すると、他ツールとバンドルする場合よりiteration消費が増えるため、既にiter=15（旧上限）に達した実績のある`task_plan_reviewer`（`log/2026-07-25/1913`）等で予算超過が現実的になる。`MAX_TOOL_ITER`はAGENTS.md §7の「重要定数」に該当し事前承認が必須のため、ユーザーに選択肢（15のまま様子見／20へ引き上げ／その他の値）を提示し、「20へ引き上げ」の選択を得た。 |
| 決定内容 | `cela_main.py`の`_query_AI_live`内`MAX_TOOL_ITER`を15から20へ変更。 |
| 影響 | `cela_main.py`（`_query_AI_live`の`MAX_TOOL_ITER`定数のみ）。全ノード共通のツールループに適用されるため、Detector/task_planner/task_plan_reviewer以外のノード（Expert/User等）にも同様に上限が20へ緩和される。実LLM再ドライランでの効果確認（thinkツール単独呼び出しの実際の消費量、20で十分か）は次回待ち。 |
| 関連 BL | [BL-093](issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-072: thinkツールの最終仕様を確定する（think専用ツールに理由づけの構造化フィールド、todoとissuesのopen/closed必須、notesの追記専用化を持たせる）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み。[D-070](decision_log.md#d-070-ノード内スクラッチパッド機構はdecision_list要約圧縮を廃しglobal_working_notes全文上書き型のみに縮小する)を訂正・確定） |
| 決定者 | t-momose（D-070の「reasoning消失は実害がない」という結論の矛盾を指摘し訂正させた上で、具体的な仕様（reasoningの構造化、todo/issuesのopen/closed必須、notesの追記専用化、iter番号の機械的付与、単独呼び出しの許容）を指定） / Claude Sonnet 5（技術検証・実装） |
| **決定理由** | D-070は「`loop_messages`が全履歴を毎iteration再送するため、reasoning消失は実害がない」と結論したが、これは「tool_calls/tool結果という行動記録が保持される」事実と「reasoningという理由づけの生文章が保持される」事実を混同した誤りだった（`_StreamMessage.reasoning = None`固定により、reasoning自体はどのiterationにも再送されない。ユーザーが「思考1のreasoningは思考2に渡されているということでよいですね？」と直接確認した際に誤りが判明）。正しい結論は「reasoning消失問題は実在し、その解決策はtool_call引数という永続化されるチャネルへ理由づけを退避させること」であり、この認識のもとで設計をthinkツール（理由づけの構造化フィールドを持つ専用ツール）に一本化した。さらに、reasoningを1本の自由文にすると長いiterでモデル自身が読み返す際に取りこぼしが生じるため、action/decided/why/rejected/rejected_whyへの構造化が必要という指摘、todo/issuesは両方ともopen/closed必須のリストにすべきという指摘、notesは上書きされると過去の記録が消えるため追記専用リストにすべきという指摘、iter番号はモデルの自己申告に頼らずシステム側で機械的に付与すべき（LLMは計算・カウントを信用できないというAGENTS.md §5.1の原則と同根）という指摘、thinkは他ツールとのバンドルを必須にせず単独呼び出しも許容すべき（ReAct本来の設計思想の優先、D-071でMAX_TOOL_ITER引き上げとセット）という指摘を受け、これらすべてを最終仕様として確定した。 |
| 決定内容 | 新規ツール`THINK_TOOL`/ハンドラ`_think_handler`を新設。引数は`action`（必須）/`decided`/`why`/`rejected`/`rejected_why`（構造化された理由づけ、蓄積済み全履歴をtool結果として即座に返すことで次iterationへ実質的に"注入"する）、`todo`/`issues`（`{item, status: open/closed}`のリスト、変更時のみ送信・省略時は前回状態を保持）、`notes`（追記専用）。iter番号は新設グローバル`_CURRENT_TOOL_LOOP_ITERATION`（`_query_AI_live`のループ先頭で機械的に設定、ループ本体への唯一の追加）から取得し`reasoning_log`・`python_calls_log`の双方に刻む。配線先はDetector数値監査パス・`call_task_planner`・`call_task_plan_reviewer`の3箇所（`_reset_think_scratchpad()`で呼び出し開始時にリセット）。 |
| 影響 | `cela_main.py`（`THINK_TOOL`/`_think_handler`/`_reset_think_scratchpad`/`_CURRENT_TOOL_LOOP_ITERATION`の新設、`TOOL_DISPATCH`登録、`_query_AI_live`ループへの最小限の追加、3ノードのtools・プロンプト配線）。新規`tests/test_bl093_think_tool_scratchpad.py`（11件）。 |
| 関連 BL | [BL-093](issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

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
