# 意思決定ログ（Decision Log）— FEATURE_NAME

**何を正とするか（Why）** を記録する。要件は [要件定義書_v35.md](要件定義書_v35.md)、実装タスクは [issue_backlog.md](back_log/issue_backlog.md)、進捗は [STATUS.md](STATUS.md)。

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
| **決定理由** | `config["initial_max_turnval"]=30`は実装時に仮置きしたデフォルト値であり、設計書§5の指標B「30ターン後まで予算制約を忘却・破綻させない」という記述も、この仮のデフォルト値を踏襲しただけで、30という数字自体に根拠はない。BL-002/BL-003の本質的な完了条件は「list版とSQLite版で同一の呼び出し列に対して構造的一致（件数・topic集合・status分布・順序）が取れること」（impl_Plan §7.2）であり、これは何ターンで打ち切ってもagreements/decisionsが十分な件数取れていれば成立する。加えて、`turn_count`が`app.invoke()`内で凍結される既存挙動（[BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)）により、外側ループ1回が内部で無制限に対話ラウンドを重ねうるため、「30外側ターン」は当初想定していたほど軽い目標ではないことも判明した。 |
| 決定内容 | ドライラン（BL-002）は`is_completed`/`halt`による自然終了、または`app.invoke()`の外側（次の「🔷 [Turn N]」表示直後）での意図的な打ち切りのいずれでも完了とみなす。途中終了する場合、`traceability.md`のT-*には「30ターン後まで」ではなく実際に到達したターン数を明記し、30が恣意的なデフォルト値だった旨も付記する。`app.invoke()`内部（差し戻しループの最中等）での強制終了は、fixtureが半端な状態で残りStep 4の構造比較を阻害するため避ける。 |
| 影響 | `phase1/phase1_dryrun.md`（Step 1〜Step 4の記述）、`traceability.md`の結果記録方法 |
| 関連 BL | [BL-002](back_log/issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施), [BL-003](back_log/issue_backlog.md#bl-003-recordreplayスタブの実llm応答による往復検証未実施), [BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離) |
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
| 影響 | [issue_backlog.md BL-002](back_log/issue_backlog.md)の依存関係・状態、[phase_gates.md P1-4](phase_gates.md)（Phase1 Exit条件の再定義） |
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
| 関連 BL | [BL-001](back_log/issue_backlog.md#bl-001-agreement-typeddictのcontentrationaleリネーム) |
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
| 関連 BL | [BL-010](back_log/issue_backlog.md)（新規） |
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
| 関連 BL | [BL-011](back_log/issue_backlog.md)（新規） |
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
| 関連 BL | [BL-012](back_log/issue_backlog.md)（新規） |
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
| 関連 BL | [BL-014](back_log/issue_backlog.md)（新規） |
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
| 関連 BL | [BL-014](back_log/issue_backlog.md) |
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
| 関連 BL | [BL-016](back_log/issue_backlog.md#bl-016-detectorの完全性判定の硬直性により探索的タスクでツールループが非収束クラッシュする) |
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
| 関連 BL | [BL-019](back_log/issue_backlog.md#bl-019-openrouterのreasoningパラメータが無効な形式で送られており一切発火していなかった) |
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
| 関連 BL | [BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)、[BL-017](back_log/issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り) |
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
| 関連 BL | [BL-022](back_log/issue_backlog.md#bl-022-openrouterの壊れたレスポンスによる生jsonjsondecodeerrorがd-009の絞り込んだexceptを素通りしクラッシュ) |
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
| 関連 BL | [BL-023](back_log/issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、[BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（非ブロッカーとして後回し）、[BL-018](back_log/issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない) |
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
| 関連 BL | [BL-023](back_log/issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、[BL-024](back_log/issue_backlog.md#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)、[BL-018](back_log/issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)、[BL-015](back_log/issue_backlog.md) |
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
| 関連 BL | [BL-020](back_log/issue_backlog.md#bl-020-中国語系モデル経由でまれに中国語英語出力になる問題) |
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
| 関連 BL | [BL-025](back_log/issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)、[BL-023](back_log/issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する) |
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
| 関連 BL | [BL-026](back_log/issue_backlog.md#bl-026-専門家名の固定配列valid_expertsを撤廃しorchestratorの自由記述に変更) |
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
| 関連 BL | [BL-027](back_log/issue_backlog.md#bl-027-cela_mainpyのロガーがimport時点で無条件起動し本番log配下にテスト実行の痕跡が混入する) |
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
| 関連 BL | [BL-028](back_log/issue_backlog.md#bl-028-max_tool_iterを1015に引き上げクラッシュ回避を優先) |
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
| 関連 BL | [BL-029](back_log/issue_backlog.md#bl-029-owned_variable_valuesにcontentの全文がそのまま混入する事故を修正)、[BL-030](back_log/issue_backlog.md#bl-030-owned_variable_valuesを依存関係参照専用の要約レポートとして独立フィールド化する拡張案) |
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
| 関連 BL | [BL-031](back_log/issue_backlog.md#bl-031-プロンプトのプレフィックスキャッシュヒット率を上げる構造整理コスト最適化) |
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
| 関連 BL | [BL-032](back_log/issue_backlog.md#bl-032-deliverable承認時に同一task_idの兄弟decisionが永久にproposedのまま取り残される) |
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
| 関連 BL | [BL-033](back_log/issue_backlog.md#bl-033-expertがpython_repl未使用のまま検算完了と虚偽申告できるf-26監査フラグに強制力がない) |
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
| 関連 BL | [BL-034](back_log/issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)、[BL-018](back_log/issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)（`whiteboard_drafts`/R4） |
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
| 関連 BL | [BL-035](back_log/issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない) |
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
| 関連 BL | [BL-036](back_log/issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-035](back_log/issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない) |
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
| 関連 BL | [BL-037](back_log/issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない)、[BL-034](back_log/issue_backlog.md#bl-034-deliverableのファイル保存がユーザー承認前に無条件で発生する)、[BL-035](back_log/issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[BL-036](back_log/issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例) |
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
| 関連 BL | [BL-036](back_log/issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-037](back_log/issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない) |
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
| 関連 BL | [BL-035](back_log/issue_backlog.md#bl-035-_build_task_scope_contextがフェーズ横断のdepends_on参照を解決できない)、[BL-036](back_log/issue_backlog.md#bl-036-最終計画書の財務需要数値が統合パスのたびに再ドリフトするbl-035f-38の射程がコスト計算にも及ぶ実例)、[BL-037](back_log/issue_backlog.md#bl-037-decisionagreementのreason_whyが薄くdetector自身も後から数値の根拠を辿れない) |
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
| 関連 BL | [BL-038](back_log/issue_backlog.md#bl-038-write_agreement成功後もdecision_extractor_nodeのagreement抽出がスキップされず同一トピックでdecisionとdeliverableの二重書き込みが発生する) |
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
| 関連 BL | [BL-044](back_log/issue_backlog.md#bl-044-ドライランの一時停止再開機能ctrlccheckpointjson--resume)、[BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離) |
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
| 関連 BL | [BL-005](back_log/issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)、[BL-041](back_log/issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（facilitatorはreflectionの`stagnant`/`drift_flag`判定を経由するため、reflection発火の復旧で間接的に到達可能になる） |
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
| 関連 BL | [BL-049](back_log/issue_backlog.md#bl-049-f-26検算ゲートによる注意力の偏りを是正する-数値検算とドメイン妥当性レビューの分離) |
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
| 関連 BL | [BL-041](back_log/issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている) |
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
| 関連 BL | [BL-061](back_log/issue_backlog.md#bl-061-facilitatorがreflectionの判定理由を一切受け取れず独立に時に食い違う状況判断をしていた)（BL-041が指摘するエスカレーション機構未実装とは別種の、より具体的な伝達漏れバグ） |
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
| 関連 BL | [BL-063](back_log/issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)、[BL-062](back_log/issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（本決定の背景にある根深い課題、別途起票のみ） |
| 参照 | [decision_lineage.md 論点61](decision_lineage.md) |

---

### D-045: F-8.3 Freeze機能を一時休止し、BL-062をDetector限定で先に解消する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-24 |
| 状態 | `decided` |
| 決定者 | t-momose（Freeze休止・優先順位の判断） / Claude Sonnet 5（技術調査・選択肢の提示） |
| **決定理由** | BL-064（合意メタデータの棚卸し）に続きBL-062の対応を検討する中で、ユーザーが「Freezeはユーザーの決定を絶対視するが検証手段がなく、AIの判断を妄信させることになりかねない」と再考した。一方、BL-062が指摘する逆方向の矛盾（Detectorがmajor判定を出しても、対応するApproved agreementがDB上に誤って残り続け、後続タスク・最終統合がそれを正当な確定値として参照し続ける）は既に実害が具体的に想定される問題であり、ユーザーは両者を天秤にかけてFreezeを一時休止しBL-062の解消を優先する判断をした。調査の結果、BL-062完了条件の①案（write_agreementの権限モデル拡張）は実装不要と判明した——`_check_write_permission`は`status`のみを制限し`action_type`は無制限であり、Detector/Reviewer/Arbiter/Integratorは全員既に`WRITE_AGREEMENT_TOOL`を保有し`status='Rejected'`かつ`action_type='SUPERSEDE'`を呼べる権限を最初から持っていた。真の欠落は権限ではなく、(a) Detector等がそもそも既存agreements DBのtopic一覧をプロンプト上受け取っておらず`target_topic`を指定する材料がなかったこと、(b) SUPERSEDEを使えという運用指示がプロンプトに存在しなかったこと、の2点だった。さらに調査の結果、Reviewer/Arbiter/Integratorは成果物全体・リソース配分・フェーズ横断矛盾を扱う設計であり、Detectorのような個別topic単位のSUPERSEDEが同じ意味を持つかは自明でないため、ユーザーの判断で今回はDetector限定に実装範囲を絞った（[BL-070](back_log/issue_backlog.md#bl-070-supersede運用指示をreviewerarbiterintegratorにも拡張するかの検討)として他3ロールへの拡張検討は別途起票）。 |
| 決定内容 | (1) `FREEZE_AGREEMENT_TOOL`をUser AIの`query_AI`呼び出し（`generate_user_utterance_node`、2箇所）のtoolsリストから外し、呼び出し不能にする。`freeze_agreement()`/`_freeze_agreement_tool_impl()`/`TOOL_DISPATCH`登録/`is_frozen`ガード/`_build_agreements_context`の🔒表示は一切削除せず温存する（再開時はtools配線を戻すのみで足りる設計）。(2) `call_detector`に`_build_agreements_context_from_db`による既存agreements DBビューを新規に注入し、`constraint_issue="major"`時にはwrite_agreementを`action_type="SUPERSEDE"`, `status="Rejected"`, `target_topic=<DBのtopic文字列>`で呼び出すよう明示的に指示する一文を追加する。(3) Reviewer/Arbiter/Integratorへの同様の拡張は、各ロールの役割（成果物全体審査・リソース配分・フェーズ横断統合）にtopic単位SUPERSEDEが本当に馴染むかの検討が必要なため、BL-070として別途起票し今回は対象外とする。 |
| 影響 | `cela_main.py`（`call_detector`へのagreements_text注入＋SUPERSEDE指示追加、`generate_user_utterance_node`の2箇所からFREEZE_AGREEMENT_TOOL除去）。新規`tests/test_bl062_detector_supersede.py`（4件）でDetectorへの配線・Freeze休止の両方を確認。 |
| 関連 BL | [BL-062](back_log/issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)、[BL-063](back_log/issue_backlog.md#bl-063-r5実装f-21拡張f-37f-83-freezegoalshiftevent)（F-8.3の実装元）、[BL-070](back_log/issue_backlog.md#bl-070-supersede運用指示をreviewerarbiterintegratorにも拡張するかの検討) |
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
| 関連 BL | [BL-073](back_log/issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する) |

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
| 関連 BL | [BL-075](back_log/issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する) |

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
| 関連 BL | [BL-076](back_log/issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式) |

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
| 関連 BL | [BL-078](back_log/issue_backlog.md#bl-078-orchestratorの専門家選定時の考察をfocus_guidanceとしてexpertへ注入する) |

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
| 関連 BL | [BL-074](back_log/issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)、[BL-076](back_log/issue_backlog.md#bl-076-detectorのmajor指摘をホワイトボード本文に永続的な注釈として埋め込むwordpdfコメント方式)、[BL-079](back_log/issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる) |

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
| 関連 BL | [BL-080](back_log/issue_backlog.md#bl-080-write_agreementのsupersedeがdeliverableの全文更新を破棄し実質何もしないツール呼び出しになっていた)、[BL-075](back_log/issue_backlog.md#bl-075-f-73ホワイトボードロールバックが1つ前は健全という前提に反し修正済み問題を無警告で再導入する)（誘因となったプロンプト）、[BL-062](back_log/issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（無効化用途との後方互換） |

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
| 関連 BL | [BL-081](back_log/issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)、[BL-080](back_log/issue_backlog.md#bl-080-write_agreementのsupersedeがdeliverableの全文更新を破棄し実質何もしないツール呼び出しになっていた)（誘因となった失敗経路）、[BL-074](back_log/issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（同根の正規化手法） |

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
| 関連 BL | [BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-073](back_log/issue_backlog.md#bl-073-entry_typedirectiveのagreementが対応タスク完了後もstatusproposedのまま永久残留する)（Directive無条件除外の原因となった対症療法） |

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
| 関連 BL | [BL-084](back_log/issue_backlog.md#bl-084-entry_typedeliverableのupdatesupersedeがtopic文字列ドリフトでeditsを0件0件失敗させ続けていたbl-074の未着手項目の再発)、[BL-074](back_log/issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合)（今回解消した「まだopen」の完了条件）、[BL-081](back_log/issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった)（この修正で真因ではなかったと判明した緩い一致フォールバック） |

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
| 関連 BL | [BL-085](back_log/issue_backlog.md#bl-085-ホワイトボード保存時にmarkdownファイルへも書き出す)、[BL-027](back_log/issue_backlog.md#bl-027-cela_mainpyのロガーがimport時点で無条件起動し本番log配下にテスト実行の痕跡が混入する)（同じ理由でのガード先例） |

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
| 関連 BL | [BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-025](back_log/issue_backlog.md#bl-025-expertがタスク境界を越えて他タスクのowns_variablesまで回答しツールループが非収束クラッシュする)（変更せず維持したスコープガードレール）、[BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)（比較検討した事後推論方式の先例） |

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
| 関連 BL | [BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-062](back_log/issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落)（D-045でFreezeを休止させた原因、今回両立） |

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
| 関連 BL | [BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-065](back_log/issue_backlog.md#bl-065-r5で新設したdb永続化情報internal_thought_processgoal_shift_eventsの消費表示経路が未設計)（今回初めて解消した書きっぱなし問題） |

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
| 関連 BL | [BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage 5として記録、実装は`open`）、[BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（`escalate_premise_concern`が自発的に呼ばれなかった実例、本決定の出発点） |

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
| 関連 BL | [BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage3・4として実装）、[BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)（D-058の9消費者を再利用、独立併存の対象）、[BL-069](back_log/issue_backlog.md#bl-069-expertが決定前にフェーズタスク表全体を見渡して他フェーズとの資源競合に気づけるよう軽量な指示を追加する)（Stage4の一部が合流、本体は別途） |

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
| 関連 BL | [BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Stage2改善、項目17〜21）、[BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)（`plan_drafts`拡張元） |

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
| 関連 BL | [BL-088](back_log/issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)、[BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（本バグにより差し戻しリトライ予算が無駄撃ちされていたのを発見した経緯） |

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
| 関連 BL | [BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（項目22）、[BL-088](back_log/issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)（同じ被害形態＝fallback化の別トリガーとして関連） |

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
| 関連 BL | [BL-089](back_log/issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)、[BL-088](back_log/issue_backlog.md#bl-088-_safe_json_parseがコードフェンス前に説明文が付いたjson配列をfallbackへ握りつぶすバグ)（同根の`_safe_json_parse`脆弱性、今回一般化して解消） |

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
| 関連 BL | [BL-089](back_log/issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)、[BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（項目22、D-063が横展開の出発点） |

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
| 関連 BL | [BL-090](back_log/issue_backlog.md#bl-090-goal_essence_analystがjson文字列値の末尾を全角鉤括弧で終え閉じ引用符を書き忘れる)、[BL-089](back_log/issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)（D-064の層2リトライが実害を吸収した安全網） |

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
| 関連 BL | [BL-091](back_log/issue_backlog.md#bl-091-write_agreementの成否をdetectorへ明示せずモデルの偽ツール呼び出し風テキストを鵜呑みにして誤って承認していた)、[BL-033](back_log/issue_backlog.md#bl-033-expertがpython_repl未使用のまま検算完了と虚偽申告できるf-26監査フラグに強制力がない)（同型の先行対策） |

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
| 関連 BL | [BL-079](back_log/issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる)、[BL-074](back_log/issue_backlog.md#bl-074-deliverableのtopic文字列に連続性が保証されずsupersede漏れの亡霊proposed行がdbに複数残存するbl-076のtarget_excerpt完全一致の脆さを統合) |

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
| 関連 BL | [BL-092](back_log/issue_backlog.md#bl-092-reviewerの差し戻し圧力に対しtask_plannerが数値の検算訂正ではなく該当箇所の削除抽象化で解消してしまう)、[BL-087](back_log/issue_backlog.md#bl-087-前提の質を上げる一連の改善task_plannerの曖昧表記禁止二重指示バグ修正task_plan_reviewer_node等)（Fix Aと逆方向の問題） |

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
| 関連 BL | [BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

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
| 関連 BL | [BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-072: thinkツールの最終仕様を確定する（think専用ツールに理由づけの構造化フィールド、todoとissuesのopen/closed必須、notesの追記専用化を持たせる）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み。[D-070](decision_log.md#d-070-ノード内スクラッチパッド機構はdecision_list要約圧縮を廃しglobal_working_notes全文上書き型のみに縮小する)を訂正・確定） |
| 決定者 | t-momose（D-070の「reasoning消失は実害がない」という結論の矛盾を指摘し訂正させた上で、具体的な仕様（reasoningの構造化、todo/issuesのopen/closed必須、notesの追記専用化、iter番号の機械的付与、単独呼び出しの許容）を指定） / Claude Sonnet 5（技術検証・実装） |
| **決定理由** | D-070は「`loop_messages`が全履歴を毎iteration再送するため、reasoning消失は実害がない」と結論したが、これは「tool_calls/tool結果という行動記録が保持される」事実と「reasoningという理由づけの生文章が保持される」事実を混同した誤りだった（`_StreamMessage.reasoning = None`固定により、reasoning自体はどのiterationにも再送されない。ユーザーが「思考1のreasoningは思考2に渡されているということでよいですね？」と直接確認した際に誤りが判明）。正しい結論は「reasoning消失問題は実在し、その解決策はtool_call引数という永続化されるチャネルへ理由づけを退避させること」であり、この認識のもとで設計をthinkツール（理由づけの構造化フィールドを持つ専用ツール）に一本化した。さらに、reasoningを1本の自由文にすると長いiterでモデル自身が読み返す際に取りこぼしが生じるため、action/decided/why/rejected/rejected_whyへの構造化が必要という指摘、todo/issuesは両方ともopen/closed必須のリストにすべきという指摘、notesは上書きされると過去の記録が消えるため追記専用リストにすべきという指摘、iter番号はモデルの自己申告に頼らずシステム側で機械的に付与すべき（LLMは計算・カウントを信用できないというAGENTS.md §5.1の原則と同根）という指摘、thinkは他ツールとのバンドルを必須にせず単独呼び出しも許容すべき（ReAct本来の設計思想の優先、D-071でMAX_TOOL_ITER引き上げとセット）という指摘を受け、これらすべてを最終仕様として確定した。 |
| 決定内容 | 新規ツール`THINK_TOOL`/ハンドラ`_think_handler`を新設。引数は`action`（必須）/`decided`/`why`/`rejected`/`rejected_why`（構造化された理由づけ、蓄積済み全履歴をtool結果として即座に返すことで次iterationへ実質的に"注入"する）、`todo`/`issues`（`{item, status: open/closed}`のリスト、変更時のみ送信・省略時は前回状態を保持）、`notes`（追記専用）。iter番号は新設グローバル`_CURRENT_TOOL_LOOP_ITERATION`（`_query_AI_live`のループ先頭で機械的に設定、ループ本体への唯一の追加）から取得し`reasoning_log`・`python_calls_log`の双方に刻む。配線先はDetector数値監査パス・`call_task_planner`・`call_task_plan_reviewer`の3箇所（`_reset_think_scratchpad()`で呼び出し開始時にリセット）。 |
| 影響 | `cela_main.py`（`THINK_TOOL`/`_think_handler`/`_reset_think_scratchpad`/`_CURRENT_TOOL_LOOP_ITERATION`の新設、`TOOL_DISPATCH`登録、`_query_AI_live`ループへの最小限の追加、3ノードのtools・プロンプト配線）。新規`tests/test_bl093_think_tool_scratchpad.py`（11件）。**D-073でtools付与済み全ノードへ拡張。** |
| 関連 BL | [BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-073: thinkツールの配線対象を、頻度・コストで絞った3ノードから、tools付与済みの全ノードへ拡張する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み。[D-072](decision_log.md#d-072-thinkツールの最終仕様を確定するthink専用ツールに理由づけの構造化フィールドtodoとissuesのopenclosed必須notesの追記専用化を持たせる)の対象ノード範囲を上書き） |
| 決定者 | t-momose（「対象ノードは全ノードへ。ツール呼び出し回数というより、思考のやり方の環境の整備なので」と明示的に指示） / Claude Sonnet 5（実装、tools=None4関数を含めるかを確認質問） |
| **決定理由** | D-072まではDetector数値監査パス・`call_task_planner`・`call_task_plan_reviewer`の3ノードに限定していた。これは「複数回のpython_repl呼び出しを跨ぐノードほどreasoning消失の被害を受けやすく、かつ呼び出し頻度が低いためコストが正当化される」という頻度・コストの多寡に基づく絞り込みだった。ユーザーはこの絞り込みの前提自体を退け、thinkツールの意義は個々の呼び出しのコスト対効果ではなく「思考のやり方の環境整備」という全ノード共通の基盤である、という立場を明確にした。この立場に立つと、頻度の高いノード（Expert/User等）や1回しか呼ばれないノード（Orchestrator/Reflection等）を除外する理由がなくなる。実装前に、現在`tools=None`（ツールループを一切通らない構造的に異なるコードパス）の4関数（`call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`）を含めるかどうかをAskUserQuestionで確認し、「含める（真の全ノード）」の選択を得た。 |
| 決定内容 | 既にtools付与済みだった残り6箇所（`call_expert`、`generate_user_utterance`の2呼び出し箇所、`call_goal_essence_analyst`、`call_reviewer`、`call_integrator`、`call_resource_arbiter`）に`THINK_TOOL`を追加。従来`tools=None`だった4関数（`call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`）とDetectorのドメイン妥当性レビューパスを`tools=[THINK_TOOL]`へ変更し、単一応答パスからツールループパスへ切り替えた。 |
| 影響 | `cela_main.py`（上記10箇所への`THINK_TOOL`追加・プロンプト指示・`_reset_think_scratchpad()`呼び出し）。tools=None→tools=[THINK_TOOL]化した5箇所（Detectorドメイン妥当性含む）は、初めてツールループの反復構造（残りiteration通知、最終iterationでのtools除去等）を経由するようになる構造的な変化であり、実LLM再ドライランでの想定外挙動の確認が次回待ち。既存`tests/test_bl087_stage3_4_goal_essence.py`のツール一覧完全一致アサーションを部分一致に更新。新規`tests/test_bl093_think_tool_scratchpad.py`を23件に拡張（パラメータ化テストで全ノードの配線を確認）。関連テストクラスタ174件Pass確認済み。 |
| 関連 BL | [BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-074: think+summaryを機械的に必須化し、自動reasoningダイジェストへ切り替える

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（実ドライラン`log/2026-07-25/1535`のレビュー中に「thinkを呼ぶかはモデル任せでは意味がない、reasoning引き継ぎは自動でないと文脈が通らない」と指摘。150字程度の機械的文字数切り詰め案も「ほとんど意味を成さない」と却下し、「thinkのみの単独呼び出しも強制対象に含める」と明示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | D-072実装後の実ドライランレビューで、Expert等がpython_replのみを呼びthinkを一度も呼ばないiterationが多数存在することが確認された。thinkの呼び出し自体をモデルの任意判断に委ねる設計では、「消えるreasoningチャネルから残るtool_callsチャネルへ理由づけを退避させる」というBL-093本来の目的が、実際にはほとんどのiterationで機能しないことが判明した。次善策として「古いiterationは機械的に文字数で切り詰める（例: 先頭150字）」を提案したが、実測したreasoning本文は数百〜1,500字超に及び、単純な切り詰めでは結論部分が失われ意味を成さないと判断された。理想的な解決（専用の軽量要約LLMによる要約生成）は追加のLLM呼び出しコストを伴うため見送り、代わりに「ツール呼び出しを含む全iterationはthinkを非空summary付きで併用することを機械的に強制し、モデル自身に意味のある要約を書かせる」方式（プロンプト制約＋機械的強制で乗り切る）を採用した。thinkのみの単独呼び出しも対象に含めたのは、think自身もいずれ直近verbatim窓の外へ古くなり、その時点でsummaryが無ければ持ち越す情報が欠損するため。 |
| 決定内容 | (1) `THINK_TOOL`に`summary`フィールドを追加し`required`に含める。(2) `_query_AI_live`のツールループに機械的強制ロジックを追加: あるiterationにツール呼び出しが1件でもあれば、その中に`think`呼び出し＋非空`summary`が存在することを必須とし、満たさない場合はそのiterationのツール呼び出しを一切実行せず`[SYSTEM ENFORCEMENT]`エラーを差し戻して再試行を強制する（D-009の壊れたJSON引数の自己修復パターンと同型）。(3) `_query_AI_live`のローカル変数で各iterationの生reasoningを蓄積し、直近2iter分は生reasoningそのまま、それより古い分は`_THINK_REASONING_LOG`から該当iterの`summary`を引いたダイジェスト1メッセージを、`light_system_prompt`（BL-025）と同型の「system直後・固定位置への差し替え」パターンで`loop_messages`へ都度反映する。 |
| 影響 | `cela_main.py`（`THINK_TOOL`スキーマ、`_think_handler`、`_query_AI_live`のツール実行部・自動ダイジェスト構築部）。強制によるリトライはMAX_TOOL_ITER予算を消費するため、既にiter=15前後に達する実績のあったノードで予算逼迫リスクが増す（D-071で20への引き上げ済みだが、恒久対策としてはタスク粒度をより細かくする、または1タスクを複数回に分けて思考させるノードループの再設計が必要とユーザーも認識済み、将来の課題）。新規`tests/test_bl093_d074_auto_reasoning_enforcement.py`（6件、フェイクstreamingクライアントで`_query_AI_live`を直接検証）。 |
| 関連 BL | [BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

---

### D-075: `read_verified_fact`/`read_deliverable_file`を、ツール配線だけでなく各ノードのプロンプト本文でオリエンテーションする

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（実ドライラン`log/2026-07-26/1749`のハルシネーション監査結果を受け、「read_verified_fact・read_deliverable_fileなどですが、各ノードのプロンプトで、それらのツールでこれまでの決定や理由・確定した数字を参照できるという説明を書き、さらに思考フレームワークとして最低でもiter=1で呼び出して、これまでのタスクでの決定や理由・成果物を確認し情報と文脈を同期せよ、また思考中にも、ヒントがないか積極的に参照せよと指示を書いてください。多分すべてのツールはプロンプトで使い方をオリエンテーションしないと、付け加えただけじゃAIは思った通りに動いてくれません」と指摘・指示） / Claude Sonnet 5（監査結果の裏取り・設計・実装） |
| **決定理由** | `log/2026-07-26/1749`の全文監査（別セッションのgeneral-purpose Agentに委託、本セッションで主要指摘を実ログ・`cela_main.py`と突き合わせて裏取り済み）で、`read_verified_fact`/`read_deliverable_file`が`tools=[...]`に配線されツールスキーマの`description`も存在するにもかかわらず、実際にはどのノードも能動的に呼んでおらず、他タスクで既に確定した数値と矛盾する値を独自に仮定してしまう事故（山間部片道時間が24分/36分で食い違ったまま放置、Goal Essence Analyst自身の推測が「実現可能性メモ」という架空の一次資料であるかのように後工程で「出典」扱いされる等）が繰り返し観測された。これはBL-093で判明した「ツール説明文だけでは不十分で、各ノードのプロンプト本文に名指しした指示が要る」（追記修正3、D-074関連）という教訓と同型の問題であり、ツールを`tools=[...]`に追加しスキーマに説明を書くだけでは、モデルは実際にはそれを使わないと判断した。 |
| 決定内容 | `read_verified_fact`/`read_deliverable_file`を持つ全6関数（`call_expert`/`call_detector`数値監査パス/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`generate_user_utterance`）のプロンプト本文に、(1)両ツールの目的説明（全フェーズ横断の確定値検索／過去タスク成果物の前提込み全文参照）、(2)「最低限iter=1で一度は関連キーワードでread_verified_factを呼び、他タスクの確定値・前提と文脈を同期してから作業を始めること」という思考フレームワーク上の指示、(3)思考中に気づきがあれば都度参照せよという指示、を追記した。Detectorには特に「数値の出所（ゴール文由来かAI自身の孫引きか）を追跡する」という監査役固有の観点を明記した。`verify_whiteboard_excerpt`（BL-079）・`diff_plan_draft_versions`（BL-092）は既存のプロンプト内オリエンテーションで同種の指示が既に存在すると判断し、対象外とした。 |
| 影響 | `cela_main.py`（6関数のプロンプト本文）。`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`はそもそも`read_verified_fact`/`read_deliverable_file`を持たないため対象外とした。これらのノードにも同種のツールを新規配線するかは、ツール自体の追加であり本決定のスコープ（既存ツールへのオリエンテーション追記）を超えるため、未決事項として残す。新規`tests/test_bl094_read_tool_orientation.py`（17件）。実LLM再ドライランでの効果確認（iter=1でのread_verified_fact呼び出しが実際に増えるか）は次回待ち。 |
| 関連 BL | [BL-094](back_log/issue_backlog.md#bl-094-read_verified_factread_deliverable_file等参照系ツールのノードプロンプトへのオリエンテーション追記) |

---

### D-076: `call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`にも`read_verified_fact`/`read_deliverable_file`を新規配線する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（D-075の「影響」欄で未決事項として残していた点について、「call_task_planner／call_goal_essence_analyst／call_task_plan_reviewerはそもそもread_verified_fact/read_deliverable_file、監査や差戻し時呼び出せるように配線してください」と明示指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | D-075では、`read_verified_fact`/`read_deliverable_file`を持たない`call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`へのツール新規配線は「既存ツールへのオリエンテーション追記」というD-075のスコープを超えるとして対象外・未決事項とした。しかしBL-094監査で確認した実害（Goal Essence Analystが「12kmを総ルート長」と仮定して逆算した値を、Task Plannerが気づかず再度別の値で仮定し直す循環参照）は、まさにTask Planner／Task Plan Reviewerの差し戻し再分解ループで発生しており、この2関数がread_verified_factで他ノードの確定値を確認できないこと自体が根本原因の一部だった。ユーザーが「監査や差戻し時」に呼べるようにと明示指示したため、対象を広げることを決定した。 |
| 決定内容 | `call_task_planner`（`tools=[PYTHON_REPL_TOOL, THINK_TOOL]`→`[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, THINK_TOOL]`）、`call_goal_essence_analyst`（同様に2ツール追加）、`call_task_plan_reviewer`（`tools=[PYTHON_REPL_TOOL, DIFF_PLAN_DRAFT_VERSIONS_TOOL, THINK_TOOL]`に2ツール追加）へ配線を拡張。各関数のプロンプト本文にD-075と同型のオリエンテーション（目的説明＋iter=1同期指示）を追記。ハンドラ実装（`_read_verified_fact_handler`/`_read_deliverable_file_handler`）は呼び出し元ロールに依存せず`_CURRENT_RUN_ID`のみを参照するため、ロール制限等の実装変更は不要だった。 |
| 影響 | `cela_main.py`（3関数のプロンプト本文＋`tools=[...]`)。`call_goal_essence_analyst`は通常プロジェクト最初期に1回だけ呼ばれるため、その時点では確定値がまだ存在せず実効性は限定的だが、一貫性と将来のグラフ設計変更への備えとして配線した。新規`tests/test_bl094_read_tool_orientation.py`への15件追加（計32件）、既存`tests/test_bl093_think_tool_scratchpad.py`のツール名指し回帰テストを更新。実LLM再ドライランでの効果確認（循環参照バグの再発防止が実際に機能するか）は次回待ち。 |
| 関連 BL | [BL-094](back_log/issue_backlog.md#bl-094-read_verified_factread_deliverable_file等参照系ツールのノードプロンプトへのオリエンテーション追記) |

---

### D-077: `call_task_planner`/`call_goal_essence_analyst`/`call_task_plan_reviewer`に`write_agreement`を配線し、role×status許可表を拡張する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-26 |
| 状態 | `decided`（実装済み） |
| 決定者 | t-momose（「このシステムの中で情報の抽出、保存、伝搬の観点でまだ足りないもの、あるいは未配線等ははるか？」という棚卸し依頼への回答に対し、「call_task_planner/call_goal_essence_analyst/call_task_plan_reviewerはそもそもWRITE_AGREEMENT_TOOLが配線されていない、これは問題ですね、タスクプランナーの意図や理由は後続タスクで見れるべきです」と明示指摘、続けて「1を修正後、issueの機能の計画に入ります」と実装順序を指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | BL-094でこの3関数に`read_verified_fact`/`read_deliverable_file`（read専用）を配線したことで、「他ノードの確定値・成果物は読めるが、自分自身の判断根拠を誰にも参照可能な形で書き残せない」という読み書き非対称が生じていた。特にtask_plannerのフェーズ・タスク分解の意図（なぜこの構成にしたか、却下した代替案は何か）は、現状JSON構造としてしか伝わらず、後続のExpert/User AIが「なぜこうなっているのか」を辿る手段が一切ない。ユーザーはこれを明確な欠陥と判断し、既存の`write_agreement`ロール制限パターン（Expert=Proposed限定、Detector等=Rejected限定）を延長する形での解消を指示した。 |
| 決定内容 | `_check_write_permission`の`ALLOWED_STATUS_BY_ROLE`に3ロールを追加：`task_planner`＝`{"Proposed"}`、`goal_essence_analyst`＝`{"Proposed"}`（Expertと同型、あくまで提案でありtask_plan_reviewer/実行に覆されうる）、`task_plan_reviewer`＝`{"Rejected"}`（Detector/Reviewer等と同じ監査役）。`call_task_planner`は最終JSON出力前に`write_agreement`（`entry_type="Decision"`, `topic="task_planner_phase_design"`固定文字列）でフェーズ構成の判断根拠を記録するよう必須指示。`call_goal_essence_analyst`は`true_essence`/`feasibility_notes`に収まらない検討過程がある場合のみの任意指示（本体の2フィールドは既に`goal_essence`テーブルで別途伝搬されているため）。`call_task_plan_reviewer`は`task_planner_phase_design`の記録内容に誤りがあり`major`判定の理由になっている場合、`write_agreement`（`action_type="SUPERSEDE"`, `status="Rejected"`）でSUPERSEDEするよう指示（BL-062と同型）。 |
| 影響 | `cela_main.py`（`_check_write_permission`、`WRITE_AGREEMENT_TOOL`の`description`、3関数のプロンプト本文＋`tools=[...]`＋`_CURRENT_CALLER_ROLE`設定）。新規`tests/test_bl095_task_planner_write_agreement.py`（25件）、既存`tests/test_bl093_think_tool_scratchpad.py`のツール名指し回帰テストを更新。実LLM再ドライランでの効果確認（task_plannerが実際に記録するか、後続ノードが実際に参照するか）は次回待ち。ユーザー指示により、次はBL-096（issue管理DB）の設計をPlan modeで行う。 |
| 関連 BL | [BL-095](back_log/issue_backlog.md#bl-095-call_task_plannercall_goal_essence_analystcall_task_plan_reviewerへのwrite_agreement_tool配線読み書き非対称の解消) |

---

### D-078: BL-096（issue管理DB）の基本設計と、issue_backlogのdocs/back_logへの文書構造再編

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（設計確定、実装未着手） |
| 決定者 | t-momose（再浮上トリガーは累積回数しきい値、書き込み権限はDetector・User AIの2ノード限定を選択。「issueの基本設計書をdocsにback_logフォルダを作り、さらにBL番号のフォルダを作り保存。back_logフォルダにissue_BL.mdを移動」と文書構造の再編を指示） / Claude Sonnet 5（設計・実装） |
| **決定理由** | (1) 再浮上（エスカレーション）は時限方式ではなく累積回数しきい値方式を採用し、Python側で機械的にseverityを`major`へ昇格させる設計とした。これはBL-093/095と同じ「モデルの判断に依存しない機械的強制」路線であり、BL-099が指摘した「thinkの最終的な実効性がモデル遵守に依存する」という弱点をissue管理の文脈では持ち込まないための判断。(2) 書き込み権限をMVPでDetector・User AIの2ノードに限定したのは、ユーザーが「User AIがExpertへ出す訂正指示自体を忘れるリスクがあり、issueをクローズする役目はUser AI（ユーザー側の代理）である」と明示認識したため。他の監査系ノード（Reviewer/Arbiter/Integrator）への拡張は将来課題として据え置いた。(3) 文書構造の再編（`docs/design/issue_backlog.md`→`docs/design/back_log/issue_backlog.md`、BL番号ごとの基本設計書を`docs/design/back_log/BL-xxx/`に保存）はユーザーの明示指示。BL単位の基本設計書が増えていくことを見越し、`docs/design/`配下に`back_log/`サブフォルダを設け、要件・設計・決定記録の正史と物理的に区別しつつ同一ツリー内で管理する運用とした（当初`docs/back_log/`という`docs/design/`と同階層のパスを指示されたが、ユーザー自身が誤記と判断し`docs/design/back_log/`へ修正指示、本エントリはその修正後の状態を記録）。 |
| 決定内容 | **BL-096設計（v1）**: 新規`issue_log`テーブル（`topic`/`raised_by`/`severity`/`status`/`occurrence_count`等）、`write_issue`ツール（CREATE=起票・再発、RESOLVE=解決）、`read_open_issues`ツール（読み取り）。`ALLOWED_ISSUE_ACTIONS_BY_ROLE = {"detector": {"CREATE"}, "user": {"CREATE", "RESOLVE"}}`。同一topicでの再CREATE時、`occurrence_count>=2`で機械的に`severity="major"`・`status="escalated"`へ昇格。reflectionへのエスカレーション到達はLLMツール呼び出しではなくPython側の直接DB問い合わせで保証。**本設計はD-079でv2に改訂済み**（詳細は[BL096_basic_design.md](back_log/BL-096/BL096_basic_design.md)）。**文書構造再編**: `issue_backlog.md`を`docs/design/back_log/`へ移動し、参照元8ファイルの相対リンクを修正、`scripts/check_docs_consistency.py`の`issue_backlog.md`参照パスを更新。今後のBLの基本設計書は`docs/design/back_log/BL-xxx/`配下に保存する運用とする。 |
| 影響 | `docs/design/back_log/issue_backlog.md`（移動）、`docs/design/back_log/BL-096/BL096_basic_design.md`（新規）、`docs/design/{README,STATUS,decision_lineage,decision_log,phase_gates,traceability}.md`・`docs/design/r1_r2_r3b_core/{cela_facilitator_arbiter_redesign_BL041,cela_r1_impl_Plan,cela_r2_design_BL023_task_state,r1_dryrun}.md`・`docs/design/r5/cela_r5_design_v2.md`（相対リンク修正）、`scripts/check_docs_consistency.py`（`issue_backlog.md`参照パス更新）。`check_docs_consistency.py`実行で`[OK]`を確認済み。`cela_main.py`への実装はまだ着手していない。 |
| 関連 BL | [BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-099](back_log/issue_backlog.md#bl-099-モジュールレベルグローバル状態文字列部分一致制御think必須化のモデル遵守依存) |

---

### D-079: BL-096設計をv2に改訂（READ経由の再発カウント追加、severity=major⇒status=escalated不変条件、(topic,task_id)キー変更）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（設計確定、実装未着手） |
| 決定者 | t-momose（「AIがissueを登録しようとして既にissueがある事がわかり、ならば登録しないでよいかと登録を見送る判断をしてしまわないか？」という累積回数しきい値方式への懸念を提起。`read_open_issues`のデフォルトで解決済みも見せる仕様、`get_open_issues_from_db`の改名も指示） / 別AI（`BL096_design_review.md`、B/A/D/C/G の5項目を指摘）／ Claude Sonnet 5（設計改訂） |
| **決定理由** | (1) D-078のv1設計は、再発カウント（`occurrence_count`）の増加を`write_issue(CREATE)`の再呼び出しのみに依存させていた。しかしユーザーが指摘した通り、AIが`read_issues`で既存issueの存在を確認した際「重複登録は避けるべき」と合理的に判断してCREATEを見送る可能性が高く、そうなるとエスカレーションに必要な再発シグナル自体が失われる。これはBL-099が指摘する「モデル遵守への依存」を再浮上の入口に持ち込んでしまう設計上の欠陥であり、修正が必要と判断した。(2) READ側のデフォルトを「未解決のみ」から「解決済みも含む」へ変更したのはユーザー指摘（「同じ懸念を抱いた時に解決済みが見えないと新たにissueを再登録する恐れがある」）。全件の無条件表示は別途`list_all`スイッチに分離し、通常の重複確認とissue整理・棚卸しの用途を区別した。(3) `read_open_issues`/`get_open_issues_from_db`という名前は「openのものしか見えない」という誤解を招くため、実際の挙動（解決済みも返す）に合わせて`read_issues`/`get_issues_from_db`に改名（ユーザー指摘）。(4) 別AIレビューの指摘Bは設計上の実バグ（初回`severity="major"`で起票された行が`occurrence_count=1`のまま`status='open'`に留まり、reflection側の`status='escalated'`限定クエリで拾われない）であり、実装前に必ず修正すべきと判断し採用。指摘A（重複検知キーの脆さ）・D（モデルが`write_issue`を呼ばないリスクへの機械的バックアップ）・C（description無制限肥大）・G（description列もLIKE検索対象に）も、BL-053/BL-084/BL-093の既存パターンと整合する妥当な指摘のため採用した。 |
| 決定内容 | (1) 再発カウントのトリガーをCREATE経由・READ経由の2系統にする。`read_issues`のフィルタ検索が既存のopen/escalated行にヒットし、かつヒット行の新規列`last_seen_task_id`が今回の呼び出し元`task_id`と異なる場合、`occurrence_count`を機械的にインクリメントし`last_seen_task_id`を更新する（同一task_id内での繰り返し読み取りによる二重計上は`last_seen_task_id`比較で防止）。CREATE経由・READ経由は共通ヘルパー`_bump_issue_occurrence`に統合する。(2) `read_open_issues`→`read_issues`、`get_open_issues_from_db`→`get_issues_from_db`に改名。パラメータから`include_resolved`を廃止し、フィルタ指定時はstatus不問で返す仕様に変更、新規`list_all`（bool）で無条件全件取得を分離。(3) 重複検知キーを`topic`単独から`(topic, task_id)`の2列に変更（`idx_issue_run_topic_task`インデックス）。(4) 不変条件「`severity='major'`の行は必ず`status='escalated'`」を、初回CREATE時の明示指定・閾値到達による自動昇格の両方で強制する。(5) `description`は2000文字上限のトランケーション規則を追加し、`topic`に加え`description`列もLIKE検索対象にする。(6) `detector_node`に、モデルが`write_issue`を呼ばなかった場合の機械的バックアップ書き込み（`raised_by="detector_auto"`、task単位でtopicを束ねる粗い集約）を追加する。 |
| 影響 | `docs/design/back_log/BL-096/BL096_basic_design.md`をv2に全面改訂。`cela_main.py`への実装はまだ着手していない（次回実装時にこのv2設計に従う）。 |
| 関連 BL | [BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-080: BL-096設計をv3に改訂（重複検知キーをtopic単独に差し戻し、reflection/facilitatorへの機械的接続とエスカレーション解除通知を追加）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（設計確定、実装未着手） |
| 決定者 | t-momose（「call_reflectionでは、issue経由ではほぼ自分が何か考えるわけではなく、機械的にfacilitatorに橋渡しする役目という理解でよいか」の確認、facilitatorへのルーティングを機械的強制にする指示、「issue解決後にエスカレーション直前の状態に戻す」復帰通知の必要性を提起） / Claude Sonnet 5（設計改訂・矛盾の発見） |
| **決定理由** | (1) D-079（v2）は別AIレビュー指摘Aを採用し重複検知キーを`(topic, task_id)`にしたが、対話の中で設計者自身（Claude）がこれとREAD経由の再発カウント（同じくD-079で追加）との矛盾に気づいた：BL-096は「タスクをまたいで再発する懸念」の追跡が本質的な目的なのに、`task_id`を識別キーに含めると別タスクでの再発が別行として扱われ、原理的にエスカレーションしなくなる。BL-084のDeliverable識別パターン（`phase_id`/`task_id`で識別）は「1つのタスクに帰属する成果物」に妥当な設計だが、「タスク横断で再発する懸念」という性質の異なるBL-096にそのまま転用すべきではないと判断し、`topic`単独キーに差し戻した。(2) READ経由の再発カウントを無条件にすると、広いキーワード検索が偶然ヒットしただけで誤ってカウントされるリスクがあるため、「`topic_keyword`と`task_id`が両方明示されている」場合のみに限定し、精度を上げた。(3) ユーザーからの確認「call_reflectionはissue経由ではほとんど考えず機械的にfacilitatorへ橋渡しするだけか」に対し、既存コード（`call_reflection`のプロンプトに既にある「未解決が残っていればcompletedにしてはいけない」という指示、`route_after_reflection`のルーティングロジック）を実際に読んで確認した結果、この理解は正しく、かつBL-051が当初求めていた「issueリストをフェーズ終了条件とする」は既存のreflection/facilitator機構がそのまま使えることが判明した。ユーザーの追加指示により、discussion_statusの上書きをプロンプト指示ではなく機械的強制にすることを決定。(4) ユーザーから「issue解決後にエスカレーション直前の状態に戻すべきでは、userも次に何をすべきか迷うのでは」との指摘。調査の結果`current_task_id`等の作業状態はreflection/facilitatorに一切書き換えられず保持されることを確認したが、facilitatorが開く「広い問い直しモード」からAI自身が自力で抜け出す明示的な合図が無い、という指摘は妥当と判断し、エスカレーション解除の一度きりの復帰通知機構を追加することにした。 |
| 決定内容 | (1) 重複検知キーを`topic`単独に差し戻す（`task_id`/`phase_id`はメタデータのみ）。(2) READ経由の再発カウント条件を「`topic_keyword`と`task_id`が両方指定され、ヒット行が`open`/`escalated`で`last_seen_task_id`と異なる」の4条件に厳格化。(3) `reflection_node`で、`issue_log`に`status='escalated'`の行が1件でもあれば、モデルの`discussion_status`判定を無視し機械的に`"stagnant"`へ上書きする（既存の`route_after_reflection`のルーティングはそのまま使う）。`facilitator_node`にも同じ直接DB問い合わせでescalated issueの構造化情報（topic/description/occurrence_count）を渡し、`call_facilitator`のプロンプトに「この具体的懸念の解消を最優先事項として提示する」専用指示ブロックを追加する。(4) `LineageState`に`escalation_active`/`escalation_just_resolved_notice_pending`を追加し、escalated件数が0件に戻った瞬間を検知して、次のExpert/User AI呼び出し時に一度だけ「エスカレーションは解消された、通常のタスク遂行に戻ってよい」という復帰通知を注入する。 |
| 影響 | `docs/design/back_log/BL-096/BL096_basic_design.md`をv3に全面改訂。`cela_main.py`への実装は完了（D-081参照）。 |
| 関連 BL | [BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-081: BL-096実装完了。実装中に発見したtask_idフィルタとREAD経由再発検知の意味論衝突を修正

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「設計書にまとめ、実装に入ってください」との指示） / Claude Sonnet 5（実装・実装中の設計修正） |
| **決定理由** | v3設計をそのまま実装しテストを書いたところ、`_read_issues_handler`のテストで実際にバグが判明した：`get_issues_from_db`の`task_id`引数を`topic_keyword`と同時に指定した場合、これを行の`task_id`列に対する完全一致フィルタとして適用すると、design docの想定シナリオ（task_1で起票された懸念をtask_3から`read_issues(topic_keyword=..., task_id="task_3")`で再発見する）そのものが`task_id`列不一致（"task_1" ≠ "task_3"）によりヒットしなくなり、READ経由の再発検知が機能しないことが分かった。これは`task_id`引数に「検索フィルタ（この行はtask_id=Xに属するか）」と「呼び出し元の現在の文脈（再発カウント比較用）」という2つの異なる意味を持たせてしまっていたことが原因。 |
| 決定内容 | `_read_issues_handler`で、`topic_keyword`が指定されている場合は`task_id`を検索フィルタには使わない（`get_issues_from_db`への`task_id`引数を`None`にする）よう修正。この場合の`task_id`はもっぱら再発カウント判定（`last_seen_task_id`との比較）専用の「呼び出し元の現在task_id」として扱う。`task_id`が`topic_keyword`なしで単独指定された場合（タスクスコープの一覧閲覧用途）は、従来通り行の`task_id`列に対するフィルタとして機能する。 |
| 影響 | `cela_main.py`（`_read_issues_handler`）。新規`tests/test_bl096_issue_log.py`（42件）で本修正後の挙動を検証済み。`python -m py_compile`合格、関連クラスタ198件Pass、`check_docs_consistency.py`合格。実LLM再ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-082: task_plannerにread_plan_draftツールを配線し、差し戻し時に前回のホワイトボードを参照させる（BL-101）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ドライラン中に「taskプランナーが差し戻された際に、前回自分が作ったフェーズ・タスク表のホワイトボードを見ておらず、丸ごと作り直している」と発見しドライランを停止。「フェーズ・タスク表ってホワイトボード化していましたよね？そのホワイトボードを参照、差分修正でいけませんか？」とパッチ方式を提案した後、「タスクプランナーのプロンプトにホワイトボードI/Oツールの明示と説明を追加」と実装範囲を指定） / Claude Sonnet 5（原因調査・実装） |
| **決定理由** | コード調査の結果、`task_plan_reviewer_node`が差し戻し時に`state["phases"]=[]`で前回計画を完全消去し、`call_task_planner`は自由文の`reviewer_feedback`のみを受け取っていることが根本原因と判明。`plan_drafts`ホワイトボード（BL-082/BL-087 Stage2でtask_plan_reviewerの個別指摘が書き込まれる想定だった文書）が、再生成時に一切参照されていなかった。ユーザーは当初「前回計画をbaselineとして保持し、変更が必要な部分のみパッチとして出力させ機械的にマージする」方式（モデル遵守に依存しない、より確実な対策）を提案したが、その後のユーザー指示で今回のスコープは「ホワイトボードI/Oツールの明示と説明の追加」に絞り込まれた。機械的マージ方式は、まず本ツールの効果を実ドライランで確認してから必要に応じて発展させる方針としたため、今回は見送り。 |
| 決定内容 | 新規`READ_PLAN_DRAFT_TOOL`/`_read_plan_draft_handler`/`get_latest_plan_draft_by_task_id`を追加。`get_latest_plan_draft_by_task_id`は既存の`get_latest_plan_draft`と異なりphase_id指定を要求しない（task_plannerは特定phaseに紐づく実行文脈を持たないため）。`call_task_planner`のtools=[...]に追加し、差し戻し時のプロンプトで「指摘のあったtask_idは必ずread_plan_draftで前回の記述とtask_plan_reviewerの個別指摘を確認し、その部分だけを修正する。指摘のないフェーズ・タスクは作り直さない」旨を明記した。あわせて、BL-095のwrite_agreement（entry_type="Decision"）がread_deliverable_file（entry_type="Deliverable"限定）で参照不能という副次的な不整合も発見したが、今回は対応範囲外とし別途Fix 2として残した。 |
| 影響 | `cela_main.py`（新規関数3つ、`TOOL_DISPATCH`、`call_task_planner`のtools=[...]・プロンプト）。新規`tests/test_bl101_task_planner_plan_draft_tool.py`（8件）。実装過程で、新規プロンプト文中に既存テストが監視する文言（「前回の計画案への差し戻し」）を無条件ブロックにも重複記載してしまい、既存テスト`test_call_task_planner_without_feedback_omits_rejection_block`を破壊するミスを起こしたため、文言を修正して解消（`test_bl061...`のBL-096起因の別regressionも同じタイミングで発見・修正）。`python -m py_compile`合格、関連クラスタ218件Pass。実LLM再ドライランでの効果確認、および機械的マージ方式への発展要否の判断は次回待ち。 |
| 関連 BL | [BL-101](back_log/issue_backlog.md#bl-101-task_plannerが差し戻し時に前回のフェーズタスク表ホワイトボードを参照せず全面再作成する) |

---

### D-083: Detectorのドメイン妥当性レビューパスにBL-096/既存監査ツール群を配線する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「detectorのドメインレビュワーにはthinkツールしかありません。'read_verified_fact', 'read_deliverable_file', 'write_agreement', 'verify_whiteboard_excerpt', 'write_issue', 'read_issues'は渡してもよい気がします」と指摘） / Claude Sonnet 5（実装） |
| **決定理由** | `call_detector`は「ドメイン妥当性レビュー」（前提・設計自体の現実性を見る第1段）と「数値監査（検算）」（第2段）の2パスから成るが、数値監査パス側は`read_verified_fact`/`read_deliverable_file`/`write_agreement`/`verify_whiteboard_excerpt`/`write_issue`/`read_issues`をすべて持つ一方、ドメイン妥当性レビューパスは`tools=[THINK_TOOL]`のみだった。前提・設計の現実性を評価する上でも、既存の確定値・出典を確認する（`read_verified_fact`/`read_deliverable_file`）、指摘引用を検証する（`verify_whiteboard_excerpt`）、決定を記録する（`write_agreement`）、軽微な懸念を後続タスクへ引き継ぐ（`write_issue`/`read_issues`、BL-096）能力に本質的な違いはなく、片方のパスだけツールアクセスが欠けている理由がない。 |
| 決定内容 | ドメイン妥当性レビューパス（`label="Detector (Domain Review)"`）の`tools=[...]`に`READ_VERIFIED_FACT_TOOL`・`READ_DELIVERABLE_FILE_TOOL`・`WRITE_AGREEMENT_TOOL`・`VERIFY_WHITEBOARD_EXCERPT_TOOL`・`WRITE_ISSUE_TOOL`・`READ_ISSUES_TOOL`を追加（`THINK_TOOL`は既存のまま維持）。あわせてプロンプトに、BL-096の`write_issue`/`read_issues`利用手順と、利用可能ツール一覧＋BL-093のthink併用必須ルールの明記を追加（数値監査パスの既存文言に準拠）。 |
| 影響 | `cela_main.py`（`call_detector`のドメイン妥当性レビューパスの`tools=[...]`・プロンプト）。既存`tests/test_bl093_think_tool_scratchpad.py::test_call_detector_domain_review_pass_also_wires_think_tool`が、ツールリスト増加によりTHINK_TOOLの検出ウィンドウ（label出現位置+200文字）を超えてしまい失敗したため、ウィンドウを+400文字に拡張して修正（挙動変更ではなく、ツール追加に伴う正当なテスト更新）。関連クラスタ109件Pass。 |
| 関連 BL | [BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-084: hydrate（ノード間コンテキスト引き継ぎ）にissue_log pinとthink要約を導入し、User AI発言の欠落・無制限タイムラインを修正する（BL-103）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（NPU-Context-Saverの過去設計との対比を依頼し、pin導入・think要約採用・escalated issue詳細込み注入の3点を承認。実装直前に`user_always_remember`フラグの意図を確認され、当初計画通り窓付き統一を承認） / Claude Sonnet 5（NPU側コード調査、CELA側の欠落2件の発見、設計提案・実装） |
| **決定理由** | `_build_hydrate_context`は`decisions`直近N件を機械的にスライスするだけで、窓の外は要約すら残らず消える設計だった。ユーザーが過去に設計したNPU-Context-Saverのhydrate機構（pin・RAG・トークン予算による段階的間引き）と対比した結果、CELAはRAGの代替として`read_verified_fact`等のプル型ツールを既に持つためRAG導入は過剰投資、トークン予算制御はNPU固有の事情（ローカルSLMのcontext枯渇）でありCELAには不要と判断し見送った。一方「pin」（重要情報を recency に関係なく常時提示）は低コスト・高効果と判断し、BL-096で新設済みの`issue_log` escalated行を転用することで新規インフラなしに実現できると判断した。facilitatorのフィードバックがchat_history末尾追記のみでwindow超過後に消える設計（cela_main.py:7130-7136）だったため、call_expert/generate_user_utteranceへのescalated issue注入は「同じ内容の二重表明」ではなく「facilitatorの発言が消えた後の穴埋め」と整理し、ユーザーは詳細込みでの注入を選択した。調査中、`generate_user_utterance_node`がUser AIの発言を一度も`decisions`テーブルに記録しておらずhydrate要約チャネルから完全に欠落していること、`generate_user_utterance`内の独自インラインタイムラインが`get_decisions_from_db`の全件を無制限に展開しExpert側の窓付き実装と非対称であることを発見し、スコープに追加した。 |
| 決定内容 | 新規`get_last_think_summary()`（`get_last_reasoning_text()`と同パターンで、BL-093 thinkスクラッチパッドの最終`decided`/`why`を要約として返す）を追加。`expert_node`の`make_decision`呼び出しを`why=get_last_think_summary() or (output or "")[:150]`に改善。`generate_user_utterance_node`に欠落していた`make_decision`/`db_append_decision`呼び出しを新規追加。`generate_user_utterance`内の無制限インラインタイムラインを`_build_hydrate_context_from_db`呼び出しへ置き換え、Expert側と同じ窓・要約ロジックに統一。新規`_build_escalation_pin_text()`をcall_expert/generate_user_utterance双方のhydrate_context直後に連結。`call_reflection`内の同種インラインタイムラインは「定期的な全履歴監査」という別役割のため対象外とし変更しない。新規テーブル・スキーマ変更なし。 |
| 影響 | `cela_main.py`（`get_last_think_summary`/`_build_escalation_pin_text`新設、`expert_node`/`generate_user_utterance_node`/`generate_user_utterance`/`call_expert`の変更）。設計書は`docs/design/back_log/BL-103/BL103_basic_design.md`。新規`tests/test_bl103_hydrate_context_improvements.py`（12件）で検証。既存`tests/test_bl086_escalation_freeze_goal_revision.py`の2テストが`generate_user_utterance_node`の新規DB書き込みで壊れたため、DBモック追加で修正（BL-061と同型の回帰）。`python -m py_compile`合格、関連クラスタ179件Pass。実LLM再ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-103](back_log/issue_backlog.md#bl-103-hydrateノード間コンテキスト引き継ぎの改善)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、BL-093（think必須化・機械的強制） |

---

### D-085: call_expertのphases_json全文表示を目次＋on-demandツールへ変更し、プロンプトを「固定指示文が先頭、動的データが末尾」の順に並び替える（BL-104）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「フェーズ・タスク表全体はuser以外はツール呼び出しで必要な時に見るようにしても支障ないか？」と提案、OpenRouterのキャッシュヒット率40%→5%急落を報告し「固定文字はプロンプトの上にできるだけまとめてキャッシュヒット率の改善になるかとも思っています」と仮説を提示、「OK進めて。他のノードも順次プロンプト順の整理を進めてください」「並び変え続行してください」と実装を承認、ドライラン`log/2026-07-27/1911`でキャッシュヒット率13-15%への改善を報告） / Claude Sonnet 5（`phases_json`の重複性・BL-025整合性の調査、プレフィックスキャッシュの構造分析、設計・実装、ドライランログのレビュー） |
| **決定理由** | DBから直接測定した結果、`call_expert`の`phases_json`（13,361文字、毎回全文）は`_build_task_scope_context`が既に提供する`current_task_json`/`verified_facts_json`/`deferred_notes_text`とほぼ機能的に重複しており、BL-025のスコープガードレール（Expertが他タスクのowns_variables領域に踏み込むことを防ぐ）の趣旨からもむしろ逆効果であると判断した。また`light_system_prompt`への差し替えロジック（cela_main.py:2734）により`phases_json`はtool loopのiter=1にしか実際には見えていないことも確認した。プロンプトキャッシュの急落については、`call_expert`のプロンプト組み立て順を実際にトレースした結果、変動する内容（expert_name・ターン数表示・agreements_text）が冒頭に、分量として最大の固定指示文ブロックがその後ろに配置されており、プレフィックスキャッシュ（先頭一致ベース）が冒頭のわずかな変動で後続の固定ブロックごとキャッシュミスする構造だったことを確認した。ツールループの反復回数増加による希薄化（別要因）も併発している可能性はあるが、40%→5%という急落幅の大きさからプレフィックス不一致が主因と判断した。 |
| 決定内容 | 新規`READ_PROJECT_PLAN_TOOL`/`_read_project_plan_handler`/`_build_project_plan_toc`/`_CURRENT_PHASES`を追加し、`call_expert`の`phases_json`全文表示を`phase_id`/`task_id`/`title`のみの軽量ToCに変更、全文が必要な場合は`read_project_plan`ツールで能動的に取得させる（User AI/`call_task_plan_reviewer`は全体像把握が本質的に必要なため`phases_json`全文を維持）。あわせて`call_expert`のプロンプトを、各ブロックの位置的参照（「上記の」等）の有無を個別に確認した上で、固定指示文グループを冒頭にまとめ、`agreements_text`・ターン数表示・`hydrate_context`等の最も変動が激しい内容を末尾に配置する順序へ並び替える。他ノード（`generate_user_utterance`・`call_detector`等）へも同一原則を順次展開する。 |
| 影響 | `cela_main.py`（新規ツール・ヘルパー、`call_expert`/`generate_user_utterance`/`call_detector`(domain_prompt・数値監査prompt両方)/`call_orchestrator`/`call_resource_arbiter`/`call_facilitator`/`call_integrator`/`call_reviewer`/`call_task_plan_reviewer`の構造変更）。設計書は`docs/design/back_log/BL-104/BL104_basic_design.md`。新規`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`（36件）で検証、関連クラスタ327件Pass。`call_reflection`は位置的参照の多段連鎖により機械的分離が困難と判断し自己完結するBL-093説明の移動のみに留めた。`call_task_planner`（reviewer_feedback_blockの先頭配置を前提とする位置的参照あり、かつ低頻度）・`call_goal_essence_analyst`（1回しか呼ばれずキャッシュ効果ゼロ）は意図的に見送り。ドライラン`log/2026-07-27/1911`（call_expert等3ノードまで適用時点でのチェックポイント再開）でキャッシュヒット率5%→13-15%への改善を確認し、ログレビューでも異常挙動・品質劣化は検出されなかった。全ノード適用後の実際のキャッシュヒット率改善確認は次回ドライラン待ち。 |
| 関連 BL | [BL-104](back_log/issue_backlog.md#bl-104-call_expertのphases_json目次化read_project_planツール新設プロンプトのキャッシュ効率改善)、BL-025（スコープガードレール）、[BL-103](back_log/issue_backlog.md#bl-103-hydrateノード間コンテキスト引き継ぎの改善) |

---

### D-087: `_query_AI_live`の自動reasoningダイジェストをindex固定差し替えから末尾再配置へ変更する（BL-106）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-104適用後もキャッシュヒット率が1時間平均5.5%と改善しないことを報告し原因調査を依頼。私の初期説明中「古いiterの要約部分は不変のはずでは」と的確な反証を提示し、原因の切り分けを訂正させた上で「修正してください、ドライランで様子を見ます」と実装を承認） / Claude Sonnet 5（`_query_AI_live`のツールループ内部を再調査し、digestの挿入位置がindex 1固定であることを発見・報告。ユーザーの反証を受けて説明を訂正し、根本原因（可変部分と不変部分が同一メッセージに同居し、かつtool履歴より手前にある）を再整理・実装） |
| **決定理由** | BL-093/D-074の自動reasoningダイジェストは、system prompt（index 0）直後のindex 1へ`insert`し、以降は同じindexへ上書きしていた。これはindex 2以降にある実質的な会話履歴（tool呼び出し・tool結果。iterごとに肥大化し、本来最もキャッシュ効果が大きいはずの部分）より**手前**に位置する。ユーザーからの指摘を受けて検証した結果、digest内の既に確定したthink summary部分自体は不変であることを確認したが、それは可変部分（直近`_AUTO_REASONING_VERBATIM_ITERS`件の生reasoning全文）と同一の1メッセージに同居しており、そのメッセージ自体がindex 2以降より手前にあるため、digestの総文字数がiterごとに伸縮するたびに、それより後ろの全メッセージの絶対位置がずれ、プレフィックスキャッシュ（絶対位置での先頭一致方式）がindex 2以降で毎iterミスしていたことが根本原因と判明した。BL-104が確立した「固定・安定した内容を先頭、変化する内容を末尾に」という原則を、このツールループ内部のdigest配置だけが逆に踏んでいたことになる。 |
| 決定内容 | digestメッセージを固定index（1）ではなくオブジェクト参照（`auto_reasoning_digest_message`）で追跡し、都度`loop_messages`の末尾から前回分を取り除いて末尾に付け直す方式に変更（`cela_main.py`のツールループ内、旧`auto_reasoning_digest_index`変数を廃止）。これによりdigestより前の会話履歴のプレフィックスキャッシュを維持しつつ、変化し続けるdigest自体はBL-104の原則どおり末尾に閉じ込める。 |
| 影響 | `cela_main.py`（`_query_AI_live`内の自動reasoningダイジェスト配置ロジック）。既存テスト`tests/test_bl093_d074_auto_reasoning_enforcement.py`のdigest位置検証（旧: index 1固定）を新方式（末尾）に合わせて更新。`python -m py_compile`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass。実LLM再ドライランでの効果確認はユーザーが実施予定。 |
| 関連 BL | [BL-106](back_log/issue_backlog.md#bl-106-_query_ai_liveの自動reasoningダイジェストがtool呼び出し履歴より手前index-1に居座り毎iterプレフィックスキャッシュを破壊していた)、[BL-104](back_log/issue_backlog.md#bl-104-call_expertのphases_json目次化read_project_planツール新設プロンプトのキャッシュ効率改善)、BL-093（think必須化・機械的強制） |

---

### D-088: `provider.order`固定を`session_id`ベースのsticky routingへ切り替える（BL-107）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-27 |
| 状態 | `decided`（実装完了、フラグでの復元手段を維持） |
| 決定者 | t-momose（BL-106修正後も「iter時はキャッシュヒット0%のまま」と報告。私の初期仮説（provider.order常設が原因）に対し「provider固定はだいぶ前からで、それでも50%前後あった。26日17時台以降に急落した」と時系列の矛盾を指摘し、より精密な原因整理を要求した上で「分かりましたsession_idに変えてください。ただし、もとに戻せるようにして下さい」と実装を承認・復元手段を明示的に要求） / Claude Sonnet 5（WebFetchでOpenRouter公式ドキュメント・ブログを調査しsticky routingとprovider.orderの排他関係を発見、ユーザーの時系列指摘を`git log`で裏付け照合し原因を再整理・実装） |
| **決定理由** | OpenRouter公式ドキュメント（[Prompt Caching Guide](https://openrouter.ai/docs/guides/best-practices/prompt-caching)）・公式ブログ（[Sticky Routing](https://openrouter.ai/blog/tutorials/prompt-caching-sticky-routing/)）に「`provider.order`を手動指定するとsticky routingが無効化される」と明記されている。既存コードは`_query_AI_live`内で常時`provider.order=["novita/fp8","parasail/fp8"]`（`allow_fallbacks: False`）を指定しており、これがsticky routingを恒常的に無効化していた。ユーザーからの反証（provider固定は古くからあり、それでも50%前後の実績があった）を受けて`git log`を確認したところ、BL-093コミット（`4a0bb46`、2026-07-26 18:03、"Wire THINK_TOOL into every LLM-calling node including previously tools=None single-shot ones"）以前は多くのノードが`tools=None`の単発呼び出しであり、そちらはsticky routing不要のクロスコールキャッシュ（同一の固定指示文プレフィックスを持つ別リクエスト同士でのヒット）で50%前後を維持できていたと判明。BL-093でほぼ全ノードがtoolsループ経由に切り替わったことで、元々存在した「ループ内（sticky routing必須）はprovider.orderのせいで0%」という弱点の影響範囲が急拡大し、平均値の急落として表面化したと整理し、ユーザーの時系列指摘と技術的に矛盾しないことを確認した上で決定した。 |
| 決定内容 | `_query_AI_live`内に切り替えフラグ`_USE_STICKY_SESSION_ROUTING`（`cela_main.py`、`provider_preferences`定義直後）を新設。`True`の場合は`provider.order`を送らず、`extra_body["session_id"] = f"{_CURRENT_RUN_ID}-{label_lower}"`（run_id＋ノード種別で安定したID）を渡してsticky routingを有効化する。`False`に戻せば元の`provider.order`固定（novita/parasail限定・fallback禁止）へワンラインで復元できる（ユーザーの「もとに戻せるように」という明示要求への対応）。速度低下等の問題が実測された場合はこのフラグをFalseに戻す。 |
| 影響 | `cela_main.py`（`_query_AI_live`の`extra_body`構築部）。`python -m py_compile`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass（挙動を変えない構造のため新規テストは追加していない）。実LLM再ドライランでユーザーが「確かにキャッシュヒットは改善しました」と効果を確認済み（2026-07-27）、速度面の悪化報告なし。 |
| 関連 BL | [BL-107](back_log/issue_backlog.md#bl-107-providerorder固定がopenrouterのsticky-routingを無効化しておりtoolsループ内の連続リクエストでキャッシュが構造的に0だった)、[BL-106](back_log/issue_backlog.md#bl-106-_query_ai_liveの自動reasoningダイジェストがtool呼び出し履歴より手前index-1に居座り毎iterプレフィックスキャッシュを破壊していた)、BL-093 |

---

### D-089: 自動reasoningダイジェストの「直近N iterは生・古いのは要約」窓方式を廃止し、要約せず全iterを単純累積する方式へ全面置換する（BL-108）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-107適用後「改善したがやはり微妙かもしれない」と報告し、digestの実際の書かれている位置を確認するよう依頼。実測データ（要約方式6,341文字 vs 単純累積19,324文字）の提示を受けて「要約せず、単純に生ログを積み上げたほうがキャッシュが働き、結果的に安いしシンプルかな？」と提案し、複数案の比較提示から「累積方式に完全置換え」を明示選択） / Claude Sonnet 5（`log_with_prompt.md`がiteration 2以降を記録していないことを発見、`log_no_prompt.md`から実際のコードロジックで digest を再構築して実測データを提示、ユーザー提案の妥当性を試算で検証し実装） |
| **決定理由** | `log/2026-07-28/0033`の実ログ（Detectorノード）を再構築した結果、窓方式（`_AUTO_REASONING_VERBATIM_ITERS=2`）では要約済み部分は数十〜数百文字と軽微な一方、直近2iter分の生reasoning全文は1回あたり数千文字（最大6,077文字）に達し、digest全体の大半を占めていることを確認した。窓の境界に当たる古いiterが生reasoning全文→summaryへ切り替わるたびdigestの中身自体が毎iter変化しており、BL-106でdigestを末尾に固定した後もこの「窓の境界変化」という不安定要因が残っていた。ユーザー提案（要約廃止・単純累積）を同ログで試算した結果、プロンプトの絶対サイズは増える（iter8時点で6,341文字→19,324文字、約3倍）ものの、既存部分が二度と書き換えられない単調増加構造になるため、BL-106のtail配置と合わせて既存部分のプレフィックスキャッシュがより確実に機能する。加えてAI自身の`summary`による情報欠落リスクも無くなり、`_AUTO_REASONING_VERBATIM_ITERS`の窓管理・`_THINK_REASONING_LOG`逆引きロジックが不要になる副次的な単純化効果もある。プロンプトサイズ増加というトレードオフはユーザーに明示した上で承認を得た。 |
| 決定内容 | `_query_AI_live`のツールループ内（`cela_main.py`）で、`_AUTO_REASONING_VERBATIM_ITERS`の窓管理と`_THINK_REASONING_LOG`からのsummary逆引きを廃止。`auto_reasoning_history`に蓄積した全iterationの生reasoningを要約せず`[iter Nの思考(全文)]`としてそのまま末尾追記し続ける方式に統一する。BL-106のdigest末尾配置（オブジェクト参照での追跡・付け替え）ロジック自体は変更しない。 |
| 影響 | `cela_main.py`（`_query_AI_live`の自動reasoningダイジェスト構築部）。既存テスト`test_auto_reasoning_digest_uses_verbatim_for_recent_and_summary_for_older`を`test_auto_reasoning_digest_accumulates_without_summarizing`に改名し窓方式の検証を削除、`test_auto_reasoning_digest_content_captured_via_create_kwargs`をiter1も生reasoningのまま含まれることを確認するよう修正。`python -m py_compile`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_r3_smoke.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`計135件Pass、フルオフラインスイート完了（425 passed、1件は単体再実行で合格する一過性の失敗）。実LLM再ドライランでユーザーが「30分平均で45%くらいに回復」と確認（2026-07-28）。ただし、キャッシュ割引率（約1/10）とサイズ増加（約3倍）を踏まえた机上試算（`cost=size×(1-0.9×hit_rate)`）では、損益分岐点（3倍サイズが1倍サイズの無キャッシュ状態と並ぶには約74%以上のヒット率が必要）に届いておらず、$コスト面では旧方式より高くつく可能性がある旨をユーザーに提示済み。実際の$コストはOpenRouter Activityダッシュボードでの実測が必要、現時点では未確認。 |
| 関連 BL | [BL-108](back_log/issue_backlog.md#bl-108-自動reasoningダイジェストの直近n-iterは生それより古いのは要約窓方式が要約への切り替わり自体で毎iter不安定になっていたため要約を廃止し単純な累積方式へ全面置換)、[BL-106](back_log/issue_backlog.md#bl-106-_query_ai_liveの自動reasoningダイジェストがtool呼び出し履歴より手前index-1に居座り毎iterプレフィックスキャッシュを破壊していた)、[BL-107](back_log/issue_backlog.md#bl-107-providerorder固定がopenrouterのsticky-routingを無効化しておりtoolsループ内の連続リクエストでキャッシュが構造的に0だった)、BL-093 |

---

### D-090: 複数ツールを組み合わせて検討する必要のない単発判定・抽出4ノードから`THINK_TOOL`を外し、tools=Noneの単一応答パスへ差し戻す（BL-109）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ログを見て「Decision Extractorってthinkしかツールを持っていない？」と質問。私の回答（thinkは単発タスクには不要な仕組み）を受けて「think、つまりメモ帳が思考の手助けになるかと思いましたが要らないですかね？」と確認し、ネイティブreasoningで代替できるとの説明を受けて「なるほど。ではthinkしかツールがないノードは抜きましょう」と全4ノードの差し戻しを指示） / Claude Sonnet 5（`tools=[THINK_TOOL]`のみのノードを`grep`で全件洗い出し、`think`ツールの存在理由が単発タスクに適用されないことを説明、reasoning_effort_levelのフォールバック依存という副次的な罠を発見・修正して実装） |
| **決定理由** | `call_orchestrator`/`call_decision_extractor`/`call_reflection`/`call_facilitator`はいずれもDBの読み書きを行わない単発判定・抽出タスクで、`think`ツールが本来解決する「OpenRouter配下の多くのプロバイダがreasoningトークンをターンをまたいで自動的に引き継がない」問題は、そもそも複数ターンにまたがらない単発タスクには発生しない。これら4ノードは元々（BL-093以前）`tools=None`の単一応答パスであり、その状態でも`reasoning_effort_level`（Decision Extractorは"medium"、Reflectionは"high"）がネイティブに付与されていたため、`think`ツール無しでも「JSON/回答を書く前に一呼吸置いて考える」効果は既に得られる。BL-093が全ノードへ`THINK_TOOL`を一律配線した際、この4ノードだけは効果が重複するだけで、代わりにツールループ化（digest構築・think強制・複数回のAPI往復）という余計なコストだけを負っていた。 |
| 決定内容 | 4ノードの`query_AI`呼び出しから`tools=[THINK_TOOL]`を削除しtools=None（デフォルト）へ差し戻し、各関数内の think 案内文も削除。副次的に、`orchestrator`/`facilitator`は`reasoning_effort_level`を`elif tools is not None: "medium"`という**tools付与ノード向けフォールバック経由でしか**得ていなかったことが判明したため（`_query_AI_live`、`cela_main.py`）、単純にtools=Noneへ戻すとreasoningがサイレントに無効化されてしまう。これを防ぐため`if label_lower in ("detector", "decision extractor", "orchestrator", "facilitator")`へ両ラベルを明示追加し、tools=None化後もreasoning_effort_level="medium"を維持する。`_reset_think_scratchpad()`呼び出しはBL-103の`get_last_think_summary()`がノード呼び出し境界の目印として使うため、4ノードとも削除せず維持する。 |
| 影響 | `cela_main.py`（4ノードの`query_AI`呼び出し、`_query_AI_live`のreasoning_effort_level判定）。`tests/test_bl093_think_tool_scratchpad.py`の`_ALL_THINK_WIRED_FUNCS`から4関数を除外し、`test_previously_tools_none_functions_no_longer_pass_tools_none`を`test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`に置換、reasoning_effort_level明示追加を確認する新規テストを追加。`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`の`test_call_reflection_bl093_mentioned_exactly_once_near_top`/`test_call_facilitator_bl093_precedes_reflection_block`（前提消滅につき廃止）を削除。`python -m py_compile`合格、関連クラスタ145件Pass。実LLM再ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-109](back_log/issue_backlog.md#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)、BL-093 |

---

### D-091: `_query_AI_live`のthink機械的強制（差し戻し）を撤廃し、thinkは任意呼び出しへ緩和する（BL-110）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-109の議論を受けて「であるならば、自由なthinkの使用も意味がないですね。というか、今はコンテキストを丸ごと引き継いでいるので、think自体も意味がないか」と機械的強制そのものの必要性を問い直し、私の説明（BL-108のdigestで既に解決済み）を受けて「thikは残して、他ツールとの強制は外してください」と実装範囲を明確に指示） / Claude Sonnet 5（`_query_AI_live`の`delta.reasoning`蓄積がthink呼び出しの有無に無関係であることをコードで確認し提示、強制ロジックの削除と関連プロンプト文言の全面修正を実装） |
| **決定理由** | BL-093/D-074が`think`ツールを導入した理由は「OpenRouter配下の多くのプロバイダはreasoningトークンをターンをまたいで自動的に引き継がない」ためだったが、`_query_AI_live`（`cela_main.py`）を確認したところ、ネイティブのreasoning（`delta.reasoning`）はthink呼び出しの有無に一切関係なく毎iter無条件で`reasoning_parts_all`へ蓄積されており、BL-108によりこれが要約されずそのままdigestとして次のiterへ引き継がれることが判明した。つまりBL-093/D-074が本来解決しようとした問題は、think呼び出しの有無に関わらず既にBL-108の仕組みで解決済みであり、`think`固有に残る価値は「decided/why/rejected/rejected_whyの構造化」のみで、当初の「さもなくば思考が消える」という強い理由づけに比べ根拠が弱い。一方、機械的強制（差し戻し）自体は、このセッション中に何度も測定した「think未添付差し戻し」（12回、3回、21回...）という実コスト（往復回数・トークン消費）を生み続けていた。ユーザーは`think`ツール自体の価値（decided/why等の構造化）は否定せず、強制（他ツールとのペアリング必須化）のみを問題視し撤廃を指示した。 |
| 決定内容 | `_query_AI_live`のツールループ内（`cela_main.py`）から、`think`(summary付き)の有無をチェックして違反時にツール呼び出し全体を差し戻す分岐を削除し、`msg.tool_calls`を無条件でdispatchするBL-093以前と同型の構造に戻す。`think`ツール自体・`TOOL_DISPATCH["think"]`・`_think_handler`・BL-108のreasoning自動蓄積（digest）ロジックはすべて維持し、モデルが任意に`think`を呼べば従来通り記録される。あわせて、もう存在しない強制を前提にした案内文を全面修正する：英語ツールスキーマ側の`"[BL-093] MANDATORY: you MUST also call \`think\`..."`（14ツール、byte-identical）を`"[BL-110] Optionally call \`think\`...it is no longer required..."`へ、日本語プロンプト側の「〜を同時に呼ぶことを厳守しろ！think無しでこれらのツールだけを呼ぶと、その応答のツール呼び出しは一切実行されず、丸ごと無駄になります。」（10ノード）を「〜を呼んで検討過程を書き残しても構いません。」へ、それぞれ置換する。 |
| 影響 | `cela_main.py`（`_query_AI_live`のツール呼び出しdispatchロジック、think関連の英語ツールスキーマ14箇所・日本語プロンプト10箇所）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`の`test_tool_call_without_think_is_rejected_and_not_executed`/`test_standalone_think_without_summary_is_also_rejected`を、差し戻されず実行されることを検証する`test_bl110_tool_call_without_think_now_executes_normally`/`test_bl110_standalone_think_without_summary_still_executes`に置換し、モジュールdocstringもBL-108/BL-110の経緯を反映するよう更新。`python -m py_compile`合格、`tests/test_bl093_think_tool_scratchpad.py`/`tests/test_bl093_d074_auto_reasoning_enforcement.py`/`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`/`tests/test_r3_smoke.py`計130件Pass、フルオフラインスイート実行中。実LLM再ドライランでの効果確認（think差し戻し起因の往復削減・レイテンシ/コスト低減）は次回待ち。 |
| 関連 BL | [BL-110](back_log/issue_backlog.md#bl-110-_query_ai_liveのthink機械的強制差し戻しを撤廃しthinkは任意呼び出しへ緩和する)、[BL-109](back_log/issue_backlog.md#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)、[BL-108](back_log/issue_backlog.md#bl-108-自動reasoningダイジェストの直近n-iterは生それより古いのは要約窓方式が要約への切り替わり自体で毎iter不安定になっていたため要約を廃止し単純な累積方式へ全面置換)、BL-093 |

---

### D-092: BL-108の「全iter分を1メッセージに再結合し末尾へ付け直す」方式を、真の単調増加（append-only）へ再修正する（BL-111）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-108/BL-110適用後もキャッシュヒットが改善しないため`_query_AI_live`のコードをGeminiに提示し第三者レビューを依頼、その調査結果と修正コード案をそのまま共有し「検討してください」と実装判断を委ねた） / Claude Sonnet 5（Geminiの指摘内容をコード上で実際にトレースして検証し、正しいと判断した上で実装。あわせてユーザーがIDEで直接編集していた`_USE_STICKY_SESSION_ROUTING`等のチューニング箇所を尊重し変更しなかった） |
| **決定理由** | Gemini（Google）へ`_query_AI_live`全文を提示した第三者レビューにより、BL-108の実装が「新規のtool呼び出しメッセージ→古いdigestを削除→全iter分を再結合した新digestを末尾に付け直す」という手順を毎iter行っており、これによりiterNのリクエストでdigestが占めていた位置（＝末尾）に、iterN+1のリクエストでは新規tool呼び出しメッセージが来ることになり、そこから後ろ全体（新digest含む、本来最もキャッシュさせたかった蓄積履歴部分）が毎iterプレフィックス不一致になる、という指摘を受けた。プレフィックスキャッシュが機能する絶対条件は「一度追加したメッセージは二度と変更・削除・移動しない」ことであり、BL-108は「常に末尾に置く」ことはできていたが「一度置いたら動かさない」ことができていなかった。実際にiter2向けリクエスト`[system, user, assistant1, tool1, digest_1]`とiter3向けリクエスト`[system, user, assistant1, tool1, assistant2, tool2, digest_2]`をコード上でトレースし、共通する厳密なプレフィックスが先頭4メッセージまでしかないことを確認し、Gemini指摘が正しいと判断した。 |
| 決定内容 | 全iter分を1つのdigestメッセージに再結合するのをやめ、「そのiterationの生reasoningだけ」を独立した新規systemメッセージとして末尾に追記し、以後は一切変更・削除・移動しない方式（真のappend-only）に変更する（`_query_AI_live`、`cela_main.py`）。`auto_reasoning_history`/`auto_reasoning_digest_message`の変数・追跡ロジックは不要になるため削除する。 |
| 影響 | `cela_main.py`（`_query_AI_live`の自動reasoningダイジェスト構築部）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`の`test_auto_reasoning_digest_content_captured_via_create_kwargs`を新構造に合わせて修正し、新規`test_bl111_consecutive_requests_are_a_strict_prefix_of_each_other`で「iterNへのリクエストがiterN+1へのリクエストの厳密な先頭部分になっている」というプレフィックスキャッシュの必須条件そのものを直接検証する回帰テストを追加した（BL-108時点でこのテストが存在すれば即座に発覚したはずのバグであり、今後の再発防止として機能する）。`tests/test_bl093_think_tool_scratchpad.py`の`test_bl109_reasoning_effort_level_preserved_for_reverted_nodes`も、ユーザーがIDEで`reasoning_effort_level`のラベル分岐・値を直接手動チューニング中だったため、固定文字列一致ではなく構造的な検証（`orchestrator`/`facilitator`が`elif tools is not None`フォールバックより前で明示的にマッチしていること）に変更し、ユーザーの変更内容自体には一切手を加えなかった。`python -m py_compile`合格、関連クラスタ131件Pass、フルオフラインスイート実行中。実LLM再ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-111](back_log/issue_backlog.md#bl-111-bl-108の全iter分を1メッセージに再結合し末尾へ付け直す方式が新規tool呼び出しメッセージの追加によりdigestの相対位置が毎iterずれる同型の不具合を残しており真の単調増加append-onlyへ再修正)、[BL-108](back_log/issue_backlog.md#bl-108-自動reasoningダイジェストの直近n-iterは生それより古いのは要約窓方式が要約への切り替わり自体で毎iter不安定になっていたため要約を廃止し単純な累積方式へ全面置換)、[BL-106](back_log/issue_backlog.md#bl-106-_query_ai_liveの自動reasoningダイジェストがtool呼び出し履歴より手前index-1に居座り毎iterプレフィックスキャッシュを破壊していた)、BL-093 |

---

### D-093: THINK_TOOLスキーマの`description`に残っていたBL-093時代のMANDATORY強制文言・旧window方式の説明を、実装（BL-108/BL-110/BL-111）の実態に合わせて書き換える（BL-113）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（`log/2026-07-28/1420`ドライランのレビュー依頼を受けた流れで、issue登録・タスク表・DB操作等の全般精査を依頼し、続けてプロンプト整理の要否を相談。3体のExploreエージェントによる調査結果に対しAskUserQuestionで「THINK_TOOLの書き換え漏れ修正」を最優先スコープとして選択） / Claude Sonnet 5（3体のExploreエージェントでノード別プロンプト構成・ツールschema重複・ドメイン特化表現を並行調査し、THINK_TOOLスキーマの`description`がBL-110の全面書き換え（14ツール）から漏れていたことを発見・報告し実装） |
| **決定理由** | BL-110で`_query_AI_live`のthink機械的強制ロジックを撤廃した際、think以外の14ツールスキーマの`description`は`"[BL-110] Optionally call \`think\`...it is no longer required..."`へ正しく書き換えたが、**THINK_TOOL自身のスキーマだけ書き換え対象から漏れており**、撤廃したはずの`"MANDATORY RULE (enforced mechanically, not a suggestion): EVERY SINGLE response...MUST include a think call...NONE of that response's tool calls...will be executed"`という文言がそのまま残っていた。これは実装（BL-110の無条件dispatch）と直接矛盾する誤情報をモデルに送り続けている状態であり、単なる文言の古さではなく実バグ。加えて同じ`description`と`summary`パラメータの説明文には、BL-108/BL-111で撤廃済みの「直近N iterのみ生・古いものは要約」という旧window方式を前提にした表現（`raw reasoning window`、`ages out`等）も残っており、こちらもBL-108以降の実際の挙動（要約せず全iterationをappend-onlyで蓄積）と食い違っていた。 |
| 決定内容 | THINK_TOOLの`description`（`cela_main.py`）から、BL-093のMANDATORY強制文言と旧window方式の説明を削除し、他14ツールと同じトーンで「thinkは任意（呼べばsummary等が記録される）」「生reasoningはthink呼び出しの有無に関わらずネイティブに自動蓄積される（BL-108/BL-111）」という実態に即した説明に書き換える。あわせて`summary`パラメータの説明文からも「ages out of the raw reasoning window」という旧window前提の表現を削除する。`"required": ["action", "summary"]`（thinkコール自体のパラメータ必須指定）は変更しない。他に発見された3件（`call_orchestrator`の静的/動的順序バグ、バス特化表現の一般化、重複ボイラープレートの統合）は今回のスコープ外とし、別途方針を決めてから対応する。 |
| 影響 | `cela_main.py`のTHINK_TOOL定義（`description`、`summary`パラメータの`description`）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`・`tests/test_bl093_think_tool_scratchpad.py`にTHINK_TOOLのdescription文字列を直接assertするテストは無いことを確認済み。`python -m py_compile`合格、`tests/test_bl093_d074_auto_reasoning_enforcement.py`・`tests/test_bl093_think_tool_scratchpad.py`・`tests/test_r3_smoke.py`計97件Pass。実LLM再ドライランでの効果確認（誤ったMANDATORY文言に反応した不要な差し戻し挙動が消えるか等）は次回待ち。 |
| 関連 BL | [BL-113](back_log/issue_backlog.md#bl-113-think_toolスキーマのdescriptionに残っていたbl-093時代のmandatory強制文言旧window方式の説明を実装bl-108bl-110bl-111の実態に合わせて書き換える)、BL-110、BL-108、BL-111 |

---

### D-094: ノード別思考フレームワーク（BL-117）を具体化する際は、「呼び出し順序の固定」ではなく「目的別行動オプション＋罠（ピットフォール）」で表現する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（設計原則の採用。プロンプトへの実装自体はBL-117の△4ノード対応時に別途行う） |
| 決定者 | t-momose（BL-117の評価コメント「ラベル貼りのリスク：フレームワーク名を書くだけでは効果が薄く、手順・チェックリストまで落とし込む必要がある」を受け、Geminiに「ツール使用も含めた全体のガイドラインを設けたい」と相談し、Detectorを例に1→2→3の番号付き手順案を提示。Geminiから返ってきた「番号付き手順ではなく3層モデル（マインドセット／目的別行動オプション／罠）が良い」という提案を持ち込み、「手順を定めすぎてAIの思考の幅を削ぐか、緩いガイドラインで気づきが出る余裕を残すか、塩梅が難しい」と迷いを共有） / Claude Sonnet 5（自身のBL-117コメントとGeminiの提案が同じ懸念に見えて実は異なる軸——フレームワークの中身の空疎さ（ラベル貼り）と呼び出し順序の固定（作業ゲー化）——を指しており対立しないことを整理。Geminiの3層モデルが両方を同時に解決する設計であることを確認し、あわせてGemini提案の「共通ツール利用の鉄則」部分はBL-115（重複ボイラープレート統合）と重複するスコープであり新規に書くのではなく集約対象であることを切り分けて提示） |
| **決定理由** | BL-117の評価で「フレームワーク名を書くだけでは効果が薄い」と指摘したが、これは番号付き手順を要求するものではない。番号付き手順（1→2→3の固定順序）は、文脈上既に情報がある場面や検算が不要な場面でも「順番通りにツールを叩かねば」という判断をAIに強いてしまい、無駄なツールループや柔軟な思考の放棄（作業ゲー化）を招く。一方、フレームワークの内容自体（判断基準・チェックリスト）が空疎なままだと、フレームワーク名を書いても実質的な行動変化を生まない（元々のBL-117での懸念）。Geminiの3層モデル（①マインドセット＝そのノード固有の視座、②目的別行動オプション＝「〜を確認したいときはこのツールを使う」という条件分岐型の提示で順序は固定しない、③罠＝AIが陥りがちなミスをネガティブ制約として明記）は、①③で具体性を持たせつつ②で順序の自由度を保つため、両方の懸念を同時に解消できる。 |
| 決定内容 | 今後BL-117のフレームワーク導入（特に△評価の4ノード: Goal Essence Analyst/Resource Arbiter/Facilitator/User AI）や、その他ノードの思考フレームワーク明文化を実装する際は、「番号付き手順」ではなく「マインドセット／目的別行動オプション（条件分岐型、順序不問）／罠（ピットフォール）」の3層構造で記述する設計原則を採用する。Gemini提案中の「共通ツール利用の鉄則」（暗算禁止・既存事実優先・思考の連続性・巨大出力抑制等）は、既に大半のノードプロンプトに存在し重複しているだけ（BL-115で特定済み）であり、この決定のスコープでは新規に書き起こさず、BL-115側での集約対象として扱う。 |
| 影響 | 今回はコード変更なし（設計原則の記録のみ）。将来のBL-117実装（特に△4ノード）・BL-116（ドメイン特化表現の一般化）・BL-115（重複ボイラープレート統合）の実装方針に適用される。 |
| 関連 BL | [BL-117](back_log/issue_backlog.md#bl-117-各ノードへのドメイン非依存な思考フレームワーク導入gemini提案の評価)、[BL-116](back_log/issue_backlog.md#bl-116-プロンプトへのバス交通シナリオ特化例の埋め込みおよび冗長な指示文ゴミ文字混入)、[BL-115](back_log/issue_backlog.md#bl-115-ノードプロンプト間の重複ボイラープレートおよびcall_decision_extractorの未使用デッドコードprompt_old) |

---

### D-095: BL-091のwrite_agreement成否シグナルに「今回ターンのみの判定である」旨の罠（ピットフォール）注記を追加する（BL-119）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-28 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（`log/2026-07-28/1420`ドライラン継続レビューの報告を受け、BL-091のシグナルが「今回ターンのみ」の判定であることをDetectorに明示すべきという私の提案に対し、「これはまさに先ほどの議論の罠の一例ですね。こういうのはプロンプトに書くべきですね」と、D-094の設計原則（具体性は順序でなく判断基準と罠に持たせる）の実例として追認。AskUserQuestionで「今すぐ小さく修正」を選択し、BL-117全体の実装を待たず独立した修正として着手することを承認） / Claude Sonnet 5（1420ログを再調査し、task_1_2の数値修正登録を巡ってDetectorが3試行多数決で`major`と繰り返し判定するループがログ全体の約半分を占めていたことを発見・報告、原因をBL-091文言の断定的な表現に特定し修正を実装） |
| **決定理由** | `call_detector`の`write_agreement_status_block`（BL-091、cela_main.py:4821-4839）は、今回のターンでwrite_agreementが成功しなかった場合、「実際には一切反映されていません...発言内容がそれと食い違う場合はconstraint_issue='major'」という断定的な文言をDetectorへ送っていた。しかし「今回のターンで新規呼び出しが0回」であることは「過去のターンも含め一切反映されていない」ことを意味しない——実際にtask_1_2の修正内容は別の過去ターンで既に登録済み（`AG-1785225752828`）だった。この文言の曖昧さにより、相手（Expert）が過去の登録内容を正しく参照して「更新した」と述べているだけの正当な発言を、Detectorが3試行多数決で繰り返し「虚偽の完了報告」と誤判定し、ログ全体の約半分を占める長時間の差し戻し応酬を招いた。Detector自身が最終的に`read_deliverable_file`で過去の登録内容を確認し「実害はない」と自己修正して収束したが、そこに至るコスト（トークン消費・往復回数）が大きい。これはD-094で採用した設計原則（フレームワーク・ツール説明の具体性は「呼び出し順序の固定」ではなく「判断基準と罠（ピットフォール）」で持たせる）の実例であり、番号手順を追加するのではなく、Detectorが陥りがちな誤判定パターンをネガティブ制約として明記する形で対応するのが適切と判断した。 |
| 決定内容 | `write_agreement_status_block`（`cela_main.py`）の「今回success=0」時の文言に、以下の罠の説明を追加する: (1) これはあくまで「今回のターン内」の話であり、過去のターンで既に登録済みの場合は0でも正常であること、(2) 相手が「更新した」「登録した」と主張していたら、まず【R4: 現在タスクの成果物・最新ホワイトボード】や既存のDecision/Agreementの内容を実際に確認し主張と一致するかで判定すること、(3) 内容が一致するなら過去のターンで既に反映済みという正常な状態であり虚偽ではないこと。今回success=0という理由だけで即`major`にせず、必要なら`read_deliverable_file`で過去の登録内容を確認してから判断すること。 |
| 影響 | `cela_main.py`（`call_detector`の`write_agreement_status_block`、4830-4841行目付近）。`tests/test_bl091_write_agreement_status_and_bl079_excerpt_verify.py`は`write_agreement_status_block`という変数名・`BL-091`タグの存在を構造的にアサートするのみで文言変更の影響を受けず、7件Pass。`python -m py_compile`合格。実LLM再ドライランで、過去ターンで既に登録済みのケースにおける同様の誤判定・長時間応酬の再発有無を確認するのは次回待ち。 |
| 関連 BL | [BL-119](back_log/issue_backlog.md#bl-119-bl-091のwrite_agreement成否シグナルが今回ターンのみの判定であることをdetectorに明示しておらず過去ターンで既に登録済みのケースを虚偽の完了報告と繰り返し誤判定していた)、[BL-117](back_log/issue_backlog.md#bl-117-各ノードへのドメイン非依存な思考フレームワーク導入gemini提案の評価)、BL-091 |

---

### D-096: `_query_AI_live`のツールループ進捗を、APIエラーリトライ（`for attempt`）をまたいで保持し、同一iteration番号から再開する（BL-122）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-29 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-120〜129を自ら調査しBL-122として「Nemotron使用時にリトライ発生回数がDeepSeek比で明らかに増えている」ことを記録した上で、BL-126/130/131の基本設計を保存しようとした直前に「その前に、APIエラー時にiterが無条件で巻き戻されるのを直しましょう。これはもったいなすぎる」と優先順位の変更を指示） / Claude Sonnet 5（`_query_AI_live`の実コードを確認し、`loop_messages`等の初期化位置が根本原因であることを特定、最小差分の修正方針を設計し実装） |
| **決定理由** | `_query_AI_live`（`cela_main.py`）のツール呼び出しループは、一時的なAPIエラー（BL-009/BL-046/BL-059/BL-072/BL-083で追加されてきた例外群）発生時、外側の`for attempt in range(len(delays)+1):`リトライループの`try`ブロック先頭から丸ごとやり直される。この`try`ブロック内に`loop_messages`（会話履歴）と`tool_calls_used`/`python_calls_log`/`reasoning_parts_all`（蓄積変数）の初期化が含まれていたため、リトライのたびにそれまでの全iterationの進捗が丸ごと破棄され、`iteration`カウンタも1から再スタートしていた。NVIDIA Nemotron 3 Ultra使用時にAPIエラー頻度がDeepSeek比で明らかに増加したこと（BL-122）により、この既知の粗さ（BL-009で「許容済み」、BL-046で「見送り」と据え置かれてきた）による実害（進んだiterationの手戻り、トークン・時間の浪費）が顕在化した。 |
| 決定内容 | `loop_messages`/`tool_calls_used`/`python_calls_log`/`reasoning_parts_all`の初期化、および新規`iteration_start`変数を外側の`for attempt`リトライループの外（関数冒頭）へ移動し、リトライをまたいで保持する。`for iteration in range(1, MAX_TOOL_ITER+1):`を`for iteration in range(iteration_start, MAX_TOOL_ITER+1):`に変更し、ループ本体の先頭で`iteration_start = iteration`を都度更新することで、APIエラー時に同じiteration番号から再開する（1から再スタートしない、既に成功したiterationも重複実行しない）。tools無し単発呼び出し経路（cross-iteration状態を持たない）は変更しない。`repl_session`の生成場所（各attemptで作り直す）はBL-014の設計意図（ノード・リトライをまたいだpython_repl状態の非共有）を尊重し変更しない。 |
| 影響 | `cela_main.py`（`_query_AI_live`、cela_main.py:2396付近）。副次的に、従来は1回のAPIエラーでiteration=1から際限なく再開でき実質`MAX_TOOL_ITER=20`の上限を超過できてしまっていたが、本修正により真の意味で20回の上限が機能するようになった（`MAX_TOOL_ITER`の値自体は変更なし、仕様の厳格化）。`tests/test_bl093_d074_auto_reasoning_enforcement.py`に新規`test_bl122_api_error_mid_loop_resumes_same_iteration_without_discarding_progress`を追加し、フェイククライアントでiteration 2の途中に`httpx.TimeoutException`を模擬、リトライ後にiteration 1の進捗（think要約等）が保持されiteration 2から再開されることを検証。`python -m py_compile`合格、関連クラスタ98件Pass。実LLM再ドライランでの効果確認（Nemotron使用時のリトライ実害減少）は次回待ち。 |
| 関連 BL | [BL-122](back_log/issue_backlog.md#bl-122-apiエラー時のツールループ全体巻き戻しリトライbl-009bl-046がモデル変更nemotron後に発生頻度が明らかに増加し実害が拡大している)、BL-009、BL-046 |

---

### D-097: `detector_node`の全決定履歴再出力バグ（BL-132）を修正し、`--resume`直後にhalt済みcheckpointを検知して停止する防御を追加する（BL-121調査）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-29 |
| 状態 | `decided`（一部実装完了、BL-121本体は`open`のまま） |
| 決定者 | t-momose（「BL-122付近のP1のバグをつぶしましょう」と、BL-122に隣接する未着手P1の解消を指示） / Claude Sonnet 5（BL-121を対象に選定し、ログ精査・コード調査から根本原因の切り分けを実施、独立したBL-132を発見し先に修正） |
| **決定理由** | BL-121（`facilitation_count>3`によるhalt設定が3回記録されたのに外側ループが停止しない）を再現調査するため`log/2026-07-29/0751`の`log_no_prompt.md`全17265行を精査した結果、単一継続プロセスであること、`facilitation_count`のリセット箇所がコード中に存在しないこと、それにもかかわらずrun終了時点のcheckpointが`facilitation_count=2`と観測された3回のhaltと数値的に矛盾することを確認した。調査の過程で、`detector_node`（`cela_main.py:6972`）が呼び出しのたびに`get_decisions_from_db(...)[1:]`で全決定履歴を丸ごと再取得・再出力するバグ（変数名「this_turn」に反しrun全体を毎回再表示）を発見し、これがBL-121で観測された「同じhalt決定が複数回見える」現象の少なくとも一因、かつBL-128（同一検算コメント反復）の主因である可能性が高いと判断した。この再出力バグを解消しない限り、次回ドライランのログでも「本当に何回haltが発生したか」を正確に判別できないため、BL-121本体の根本原因確定より先にBL-132を修正すべきと判断した。あわせて、D-086で既に指摘されていた「`--resume`は必ずgoal_essenceから全体を再走行する」という設計上の性質を踏まえ、`--resume`直後に`state.get("halt")`を一切チェックせず外側whileループへ入っていた実装上の欠落（BL-121仮説(b)）を独立した安全策として修正した。 |
| 決定内容 | (1) `detector_node`末尾の全履歴再取得・再出力（`get_decisions_from_db(...)[1:]`）を廃止し、この呼び出し自体が直前に作成した`decision`1件のみを出力するよう変更（BL-132、`done`）。(2) `run_ai_vs_ai_loop`の`--resume`処理直後に、読み込んだcheckpointが既に`halt=True`だった場合は即座に処理を停止するチェックを追加（BL-121仮説(b)への対症、`done`）。(3) BL-121本体（3回に見えるhalt発生の正体）は、上記(1)適用後の次回ドライランで決定ログの重複表示が解消された状態を確認してから再判定することとし、`open`のまま維持する。BL-122（同一ターン内のツールループ巻き戻し）が本事象の原因である可能性（仮説(a)）は、コード経路が独立していることを確認済みで、否定的と判断した。 |
| 影響 | `cela_main.py`（`detector_node`、`run_ai_vs_ai_loop`の`--resume`分岐）。`python -m py_compile`合格、関連クラスタ（`test_bl093_d074_auto_reasoning_enforcement.py`/`test_bl093_think_tool_scratchpad.py`/`test_r3_smoke.py`/`test_bl104_project_plan_toc_and_prompt_reorder.py`）132件Pass。実LLM再ドライランでのログ肥大化解消・BL-121原因切り分けの効果確認は次回待ち。 |
| 関連 BL | [BL-121](back_log/issue_backlog.md#bl-121-facilitation_count3review_count3によるhaltが3回セットされたにもかかわらず外側ループが一度も停止せず会話が継続していた)、[BL-132](back_log/issue_backlog.md#bl-132-detector_nodeが呼び出しのたびに全決定履歴を再取得再出力しておりログ肥大化とbl-121の原因切り分けを妨げていた)、BL-128、D-086 |

---

### D-098: TOOL_DISPATCHの全ハンドラをstate受け渡し可能な`(args, state)`形式へ統一する（BL-131前提）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-131のtask_id検証実装のために「TOOL_DISPATCHのstate受け渡しのみにします」とスコープを絞った上で「BL-131の前に片づけたほうがいいですか？」と着手順序を確認） / Claude Sonnet 5（`_write_agreement_impl`のtask_id検証には`state["phases"]`参照が必須であり、先にTOOL_DISPATCHを直さないと既存の`_CURRENT_PHASES`グローバルを一時拡張してすぐ剥がす二度手間になると説明し着手順序を提案） |
| **決定理由** | `TOOL_DISPATCH`（R2実装時に導入）はツール名→ハンドラの辞書だがハンドラは`args`のみを受け取り、`run_id`/`task_id`/`caller_role`等の実行時コンテキストは呼び出し元ノードが都度設定するモジュールレベルglobal（`_CURRENT_RUN_ID`等）経由でしか渡せなかった（BL-099で既に指摘済みの技術的負債）。BL-131の`task_id`実在チェックには`state["phases"]`が必要だが、対応するグローバル`_CURRENT_PHASES`は`call_expert`1箇所でしか設定されておらず、他ノードでも正しく動くようにするには同じ負債パターンをさらに拡張することになる。ユーザーとの設計議論の結果、この機会にグローバルを増やす代わりに`state`を明示的に受け渡す方式へ切り替えることで合意した。 |
| 決定内容 | `_query_AI_live`/`query_AI`/`_query_and_parse_with_retry`に`state: dict \| None = None`パラメータを追加し、ツール実行箇所を`handler(args, state)`に変更。`TOOL_DISPATCH`の全15エントリを`(args, state=None)`の2引数ラムダへ統一し、`state`未指定（`None`）の場合は既存の`_CURRENT_*`グローバルへフォールバックすることで後方互換を維持。`write_agreement`/`freeze_agreement`/`escalate_premise_concern`/`resolve_premise_concern`/`revise_goal`/`write_issue`は`state`経由で`run_id`/`task_id`/`phase_id`を優先的に取得するヘルパー（`_run_id_from`等）を新設。既にstateを持つノード（`call_expert`/`generate_user_utterance`/`call_detector`）は`state=state`を追加するのみ、従来stateを受け取っていなかった6関数（`call_resource_arbiter`/`call_integrator`/`call_task_planner`/`call_reviewer`/`call_goal_essence_analyst`/`call_task_plan_reviewer`）には新規`state`パラメータを追加し呼び出し元ノードから伝播させた。`_CURRENT_RUN_ID`/`_CURRENT_TASK_ID`/`_CURRENT_PHASES`グローバル自体は残す（完全撤去はBL-099の別スコープ）が、以後の新規参照は`state`経由を優先する。 |
| 影響 | `cela_main.py`（`_query_AI_live`/`query_AI`/`_query_and_parse_with_retry`のシグネチャ、`TOOL_DISPATCH`全体、6ノード関数のシグネチャ、呼び出し元ノードでの引数追加、計約20箇所）。既存テスト40件が`TOOL_DISPATCH`の各エントリを`args`1個だけで呼ぶ旧呼び出し規約に依存しており失敗したため`state=None`デフォルトを追加し解消、さらにTOOL_DISPATCH実装詳細（think handlerとの同一性、`handler(args)`という呼び出し文字列）に依存していた回帰テスト2件を新しい規約に合わせて更新。`python -m py_compile`合格、関連クラスタ166件Pass。 |
| 関連 BL | [BL-131](back_log/issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、BL-099 |

---

### D-099: `write_agreement`にtask_id/phase_id実在チェックと`target_topic`必須化を実装し、`get_latest_whiteboard`/`get_latest_plan_draft`をtask_id単独検索へ統一する（BL-131）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「"/compact"後にBL126-131を実装」と依頼、実装順序についてもBL-131を最初にする方針を確認済み） / Claude Sonnet 5（設計（BL126_basic_design.md §2.5）に基づき実装、`_find_task_by_id`/`_find_phase_id_for_task`という既存ヘルパーを再利用） |
| **決定理由** | `log/2026-07-29/1322`・`1708`の両ドライランで、`task_1_1_review`という**task_plannerの正式計画に存在しないtask_id**でExpertが本格的な成果物を作成し続ける事故が繰り返し観測された。`_write_agreement_impl`は`depends_on`のID存在チェックは持つが、`task_id`/`phase_id`が`state["phases"]`に実在するかは一切検証しておらず、これが直接原因だった。あわせて`get_latest_whiteboard`が`(phase_id, task_id)`の組でしか検索していなかったため、誤ったphase_id指定時に既存版が「該当なし」と誤判定されバージョンが1から再スタートする事故（1708ログのtask_1_1_review V9で観測）も、根本原因の一部として特定された。`plan_drafts`側に既に存在する`get_latest_plan_draft_by_task_id`（task_idはrun_id内で一意という命名規約を前提にphase_idを問わず検索する設計）という前例に倣い、拒否ではなく検索方法自体を修正する方針を採用した。 |
| 決定内容 | (1) `_write_agreement_impl`に`entry_type in ("Directive","Deliverable")`の場合の`task_id`実在チェックを追加（`_find_task_by_id(phases, tid)`で検索し、見つからず`pending_task_ids`にも無ければ拒否。`entry_type="Decision"`は対象外）。(2) `LineageState`に新規フィールド`pending_task_ids: list[str]`（初期値`[]`）を追加——BL-126のFacilitator対話が正式採用前に仮登録する許可リストとして先行追加。(3) `get_latest_whiteboard`/`get_latest_plan_draft`のWHERE句からphase_idを除きtask_id単独検索へ変更、phase_id食い違いは警告ログのみに留める。(4) `entry_type != "Deliverable"`のUPDATE/SUPERSEDEで`target_topic`省略時に`topic`へ暗黙フォールバックしていたのを必須パラメータ化。 |
| 影響 | `cela_main.py`（`_write_agreement_impl`、`get_latest_whiteboard`、`get_latest_plan_draft`、`LineageState`、初期state生成箇所）。新規`tests/test_bl131_write_agreement_task_id_validation.py`（9件）、既存`tests/test_r3_smoke.py`の3件を`pending_task_ids`経由で許可する形に更新。`python -m py_compile`合格、関連クラスタ166件Pass。実LLM再ドライランでの`task_1_1_review`型事故の再発防止確認は次回待ち。BL-130・BL-126（Essence Dialogue等）の実装は次回以降。 |
| 関連 BL | [BL-131](back_log/issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、D-098 |

---

### D-100: Expertが成果物を出さずにUser AIへ質問できる`ask_user_question`ツールを新設し、相談ターンではDetector/Decision Extractorの監査・抽出をスキップする（BL-130）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「次の実装開始」と依頼、BL126_basic_design.md §8の推奨実装順序でBL-131の次に位置づけ） / Claude Sonnet 5（設計（同design.md §2・§3・§13.2）に基づき実装） |
| **決定理由** | 従来はUser AI→Expertへの一方向指示のみで、Expertが要求の曖昧さ等で本当に前進できない場合でも、質問する手段がなく見切り発車で成果物を作らざるを得なかった。`log/2026-07-29/1322`の1件（Facilitatorが提起した前提矛盾のエスカレーション自体は既存のescalate_premise_concernで対応可能だが、それとは別に「単純な情報不足・方向性確認」のための軽量な相談経路が欠けていた）を踏まえ設計されたBL-130を実装。相談ターンは成果物のレビューではないため、既存のDetector（数値監査）・Decision Extractor（合意抽出）をそのまま適用すると意味のない監査コストと誤判定リスクを生むため、専用のモード分岐でスキップする方針とした。 |
| 決定内容 | (1) 新規ツール`ASK_USER_QUESTION_TOOL`/`_ask_user_question_tool_impl`（expertロールのみ許可、`question_text`/`blocking_reason`必須）を追加し、`_LAST_ASK_USER_QUESTION`という`_LAST_GOAL_REVISION`と同型のブリッジ変数・`get_last_ask_user_question()`を新設、`query_AI`の既存リセット処理に合流させた。`call_expert`のツールリスト・`light_system_prompt`・固定プロンプト文言に追加。(2) `LineageState`に`expert_consultation_mode: bool`/`expert_pending_question: str`を追加。`expert_node`が`get_last_ask_user_question()`の結果でこの2フィールドをセット/リセットする（呼ばれなかった場合は明示的にFalse/""へリセットし、前ターンからの残留を防ぐ）。(3) `detector_node`に軽量パス分岐を追加：`target_role=="assistant"`かつ`expert_consultation_mode`の場合、`call_detector`のLLM呼び出し自体をスキップし`constraint_issue="none"`を返す（BL-033の検算フェイルクローズもこの軽量パスには適用しない）。(4) `route_after_expert_detector`に新分岐を追加し、`expert_consultation_mode`時は`expert_decision_extractor`を経由せず直接`generate_user_utterance`へ渡す（Decision Extractorが「何も抽出しない」ことを、呼び出し自体のスキップという形で実現）。(5) `generate_user_utterance`（§13.2のモード切替設計）に、`expert_pending_question`検出時の固定プロンプト文言（「成果物ではなく質問への回答」であることの明示）を追加。(6) `generate_user_utterance_node`がUser AIの回答生成直後に両フラグを消費・リセットする。 |
| 影響 | `cela_main.py`（新規ツール定義・ハンドラ・TOOL_DISPATCH・`LineageState`・初期state・`call_expert`・`expert_node`・`detector_node`・`route_after_expert_detector`とそのグラフエッジマッピング・`generate_user_utterance`・`generate_user_utterance_node`）。新規`tests/test_bl130_ask_user_question.py`（15件）。`python -m py_compile`合格、関連クラスタ256件Pass。実LLM再ドライランでの相談チャネルの実動作確認は次回待ち。BL-126（Essence Dialogue等）の実装は次回以降。 |
| 関連 BL | [BL-130](back_log/issue_backlog.md#bl-130-expertが成果物を出さずにuser-aiへ質問相談できる双方向チャネルが未設計現状はuserexpertへの一方向指示のみ)、D-098、D-099 |

---

### D-101: `call_reflection`に層2リトライ（BL-089パターン）を適用し、単発のJSONパース失敗が即座に`stagnant`判定へ直結する事故を修正する（BL-120）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「最後まで進めて」と依頼、BL126_basic_design.md §8の推奨順序でBL-126 Stage D着手前にBL-120修正が前提と位置づけ） / Claude Sonnet 5 |
| **決定理由** | `log/2026-07-28/1420`で、`call_reflection`のJSONパース失敗フォールバック（`stagnant`固定）が5回連続で発火し、正常進行中の議論を繰り返し強制巻き戻す実害が確認されていた（BL-120、記録のみで放置）。原因はBL-089で他ノード（task_plan_reviewer/task_planner/goal_essence_analyst）に既に適用済みの層2リトライ（`_query_and_parse_with_retry`、D-005）が`call_reflection`にだけ適用されておらず、単発のquery_AI+_safe_json_parseのままだったこと。真因が特定できたため、BL-126 Stage D（迎合監査基準の追加）の前提として先に修正した。 |
| 決定内容 | `call_reflection`の単発`query_AI`+`_safe_json_parse`呼び出しを`_query_and_parse_with_retry`でラップ。リトライを使い切った場合のみ、従来通り`stagnant`へフェイルクローズする（安全側の判定方針自体、フォールバック値は変更しない——真の修正点は「1回の一時的なパース崩れだけで即座にそこへ落ちなくなったこと」）。 |
| 影響 | `cela_main.py`（`call_reflection`）。新規テスト2件（`tests/test_bl089_json_fence_and_failclosed_review.py`に追加）。`python -m py_compile`合格。 |
| 関連 BL | [BL-120](back_log/issue_backlog.md#bl-120-call_reflectionのjsonパース失敗フォールバックがstagnant即断となっており正常進行中の議論を繰り返し強制巻き戻ししていた) |

---

### D-102: BL-126 Stage A（`goal_drafts`バージョニング）・Stage B（Detector `review_mode="goal_change"`）を実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「最後まで進めて」と依頼） / Claude Sonnet 5（BL126_basic_design.md §4・§5・§8の推奨順序に基づき実装） |
| **決定理由** | BL-126の本質対話（Essence Dialogue）ワークフロー実装の基盤として、(1) ゴール文の全文履歴を版管理する仕組み、(2) ゴール改定そのものを専用の判断基準で監査する仕組みが必要だが、いずれも既存の反応的`revise_goal`経路（BL-086）にまだ適用されておらず、Stage D（対話モード）着手前にこの2つを既存経路で先行検証しておく方針とした（design.md §8実装順序）。 |
| 決定内容 | **Stage A**: `goal_drafts`テーブル・`apply_goal_patch`/`get_latest_goal_draft`を新設（whiteboard_drafts/plan_draftsと同型のappend-onlyバージョニング、run_id単独キー）。`_revise_goal_tool_impl`が改定成功時に`apply_goal_patch`を呼ぶよう配線。**Stage B**: `call_detector`に`review_mode: Literal["task_output","goal_change"]`（デフォルト"task_output"）を追加し、`domain_role_instruction`の算出ブロックのみを§5の4判断基準（旧文が追記として保持されているか／理由づけの相応性／スコープ逸脱の有無／数値的最適性は評価しない）へ差し替える直交した軸とする。`generate_user_utterance_node`が`revise_goal`成功時に`goal_revision_pending_review`をセットし、次の`detector_node`がこれを消費して`review_mode="goal_change"`を使う（既存の`route_after_user_detector`等のルーティングロジックは無変更）。 |
| 影響 | `cela_main.py`（`goal_drafts`スキーマ、`apply_goal_patch`/`get_latest_goal_draft`、`_revise_goal_tool_impl`、`call_detector`、`LineageState`、`generate_user_utterance_node`、`detector_node`）。新規テスト2件（`tests/test_bl086_escalation_freeze_goal_revision.py`に追加）・新規`tests/test_bl126_stage_b_goal_change_review_mode.py`（6件）。`python -m py_compile`合格。 |
| 関連 BL | [BL-126](back_log/issue_backlog.md#bl-126-bl-086の前提エスカレーションはexpertのリアクティブな経路に限定されておりfacilitatoruser-aiがゴール制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計)、D-101 |

---

### D-103: BL-126 Stage C（Task Plannerのラン途中再構成・supersede機構）を実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「最後まで進めて」と依頼） / Claude Sonnet 5 |
| **決定理由** | 従来の`task_planner_node`は`turn_count==1 and not phases`のみで発火し、ラン途中で計画全体を見直す経路が存在しなかった。BL-126の本質対話が収束した後、計画を実際に反映させる受け皿が必要（design.md §6・§8実装順序）。 |
| 決定内容 | ガードを`(turn_count==1 and not phases) or state.get("plan_revision_reason")`へ緩和し、消費は「後」ではなくガード判定直後（先頭）で行う（チェックポイント再開時の多重発火防止）。`call_task_planner`に`existing_phases`/`revision_reason`引数を追加し、無関係な既存タスクに触れず影響を受けるタスクのみ見直すよう指示する固定ブロックを注入。新しい計画に含まれなくなった既存task_idは削除ではなく`state["phases_superseded"]`へ記録し、`write_agreement(entry_type="Directive", action_type="SUPERSEDE", status="Proposed")`で監査証跡を残す（task_plannerロールはProposedのみ許可のため、他ロールのSUPERSEDEとはstatusが異なる）。再構成後は`plan_review_done=False`にリセットし、既存のtask_plan_reviewer_nodeを再度通す。`task_plan_reviewer_node`がラン途中の再構成をmajor判定で差し戻す場合は、既存の`plan_reviewer_retry_count`上限ロジックをそのまま再利用しつつ、`plan_revision_reason`を再セットして新設ガード経由で再発火させる（`turn_count==1`ガードに依存する既存の`phases=[]`だけでは、ラン途中では再発火しないため）。 |
| 影響 | `cela_main.py`（`task_planner_node`、`call_task_planner`、`task_plan_reviewer_node`、`LineageState`）。新規`tests/test_bl126_stage_c_task_planner_reconfiguration.py`（7件）。`python -m py_compile`合格。 |
| 関連 BL | [BL-126](back_log/issue_backlog.md#bl-126-bl-086の前提エスカレーションはexpertのリアクティブな経路に限定されておりfacilitatoruser-aiがゴール制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計)、D-102 |

---

### D-104: BL-126 Stage D（Facilitatorのツールループ化・`EssenceProposal`・Essence Dialogueループ・Reflection迎合監査）を実装する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「最後まで進めて」と依頼） / Claude Sonnet 5（設計調査の過程で、design.mdが前提としていた`route_after_facilitator`の既存ルーティング（4分岐）が実際のコードでは2分岐（halt/end_turn）のみだったという記述の食い違いを発見し、実際のグラフ構造——`run_ai_vs_ai_loop`が`app.stream()`を外側`while`ループで繰り返し呼び出し、各呼び出しがentry_pointから再入場する構造（goal_essence/task_planner/task_plan_reviewerの冪等ガードにより実質generate_user_utteranceまで素通りする）——に基づいて実装方針を再設計した） |
| **決定理由** | BL-126の核心である「Facilitator↔User AIの本質対話」を実現するには、Facilitatorが単発の助言役ではなく能動的にツールを使い、User AIとの往復を経て収束できる必要がある。design.mdの前提記述（既存ルーティングの分岐数）に事実誤認があったため、実装着手前にコードを直接確認し、正しい前提（外側whileループが「1ターン」の単位であり、次のfacilitator/generate_user_utterance遷移は次の外側ループ呼び出しで自然に発生する）に基づいて設計をやり直した。これにより、当初懸念していた「core turn loopの大規模な書き換え」ではなく、既存ノードは変更せず`generate_user_utterance`の出力エッジ1本を条件分岐化するだけで安全に実現できることが判明した。 |
| 決定内容 | (1) `write_agreement`に`entry_type="EssenceProposal"`を追加（新規ツールは起こさず既存のagreements/権限枠組みを再利用、facilitatorロールはProposedのみ許可）。(2) `escalate_premise_concern`の許可ロールに`facilitator`を追加。(3) `call_facilitator`をTHINK_TOOL/ESCALATE_PREMISE_CONCERN_TOOL/WRITE_AGREEMENT_TOOLを持つツールループへ変更（BL-109からの意図的な差し戻し、本関数のみ対象外化）。essence_dialogue_active時は専用の対話継続プロンプトへ切り替える（§13.2）。(4) `_LAST_ESSENCE_PROPOSAL`/`get_last_essence_proposal()`を`_LAST_GOAL_REVISION`と同型のブリッジとして新設。(5) `LineageState`に`essence_dialogue_active`/`essence_dialogue_round`/`essence_dialogue_max_rounds`（5）/`essence_dialogue_topic`/`last_essence_proposal`を追加。(6) `facilitator_node`が、EssenceProposal新規提起で対話を開始し、Userの承認（`last_essence_proposal`がstate経由で橋渡しされ、topic一致かつstatus="Approved"）で収束して`plan_revision_reason`をセット（Stage Cへ接続）、または上限ラウンド到達でタイムアウトして通常フローへ復帰する。対話中は`facilitation_count`を消費しない（§3.2）。(7) `generate_user_utterance_node`がUser AIのターン直後に`last_essence_proposal`をstateへ橋渡し。(8) `generate_user_utterance`に`essence_dialogue_active`時の専用プロンプト（elif連鎖で`expert_pending_question`と排他）を追加。(9) グラフの`generate_user_utterance`→`user_detector`固定エッジを条件分岐化し、`essence_dialogue_active`時は`user_detector`を経由せず`facilitator`へ直接戻す（既存の通常監査フローには一切影響しない）。(10) `call_reflection`に迎合（collusion）監査基準（転換の"回数"ではなく"重大さに見合った理由づけの有無"を問う、D-094の判断基準路線）を追加。 |
| 影響 | `cela_main.py`（`write_agreement`関連3箇所、`escalate_premise_concern`、`call_facilitator`、`facilitator_node`、`generate_user_utterance_node`、`generate_user_utterance`、`build_graph`のエッジ定義、`call_reflection`、`LineageState`、初期state）。既存回帰テスト3件を新規約に更新（BL-109のcall_facilitator除外含む）。新規`tests/test_bl126_stage_d_essence_dialogue.py`（16件）。`python -m py_compile`合格、関連クラスタ512件Pass。実LLM再ドライランでの本質対話フローの実動作確認は次回待ち。 |
| 関連 BL | [BL-126](back_log/issue_backlog.md#bl-126-bl-086の前提エスカレーションはexpertのリアクティブな経路に限定されておりfacilitatoruser-aiがゴール制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計)、D-103 |

---

### D-105: BL-114（`call_orchestrator`の静的/動的順序矛盾）は、コードでなくコメントを実態に合わせて修正する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（Plan agentの設計案をレビューし採用） |
| **決定理由** | `call_orchestrator`はBL-104のコメントで「静的先頭・動的末尾」を謳いながら実際は動的な`goal_context`が先頭にあるという矛盾があった。JSON形式指示（末尾の短い固定ブロック）を静的先頭グループへ合流させる案も検討したが、`call_task_plan_reviewer`など他ノードの既存実装が既に「動的ブロックの後にJSON形式指示を残す」形で正しく機能しており、動的ブロックでプレフィックスキャッシュの連続一致が一度途切れた後は短い末尾ブロックを先頭へ動かしてもキャッシュヒット率上の利益がないため、コード側をこの既存の確立済みパターンに合わせ、矛盾していたコメントの記述を修正する方針とした。 |
| 決定内容 | プロンプトを「静的（役割・肩書き生成指示・BL-078 focus_guidance）→動的（`goal_context`→`user_input`→`agreements_text`→`history_text`）→JSON形式指示（末尾）」の順に並び替え、コメントも実態に一致させた。同じ箇所で専門家タイトル例のドメイン非依存化（BL-116）も同時に実施。 |
| 影響 | `cela_main.py`（`call_orchestrator`のみ）。既存の順序回帰テスト（`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`）は相対順序を保ったため無修正でPass。`python -m py_compile`合格。 |
| 関連 BL | [BL-114](back_log/issue_backlog.md#bl-114-call_orchestratorの静的動的順序がコード自身のbl-104コメントと矛盾している) |

---

### D-106: BL-115（ノードプロンプト間の重複ボイラープレート）は、既存の`inspect.getsource()`ベーステストを壊さない範囲でのみ共有化する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | Plan agent（設計案の主要な制約発見・回避策の提案）/ Claude Sonnet 5（採用・実装） |
| **決定理由** | `tests/test_bl093_think_tool_scratchpad.py`（`test_node_prompt_names_its_own_tools_alongside_think`等）と`tests/test_bl094_read_tool_orientation.py`は、各ノード関数自身の`inspect.getsource()`にツール名・"BL-093"・"BL-094"等のリテラル文字列が含まれることを要求する設計になっている（BL-093/BL-094導入時に「文言更新忘れを検知する」目的で意図的にそう作られていた）。これは重複ボイラープレートの一部を安易にヘルパー関数へ隠すと、そのテスト群がサイレントに無意味化する（ヘルパーの中身は見ずキャッシュ的にPassし続けるが実際には検知力を失う）のではなく、むしろテストが期待通り「壊れて」教えてくれる、という健全な設計だと判断した。したがって、全ての重複を無条件に集約するのではなく、各ケースでテストとの整合性を個別に検証し、真にbyte-identicalまたは同型の箇所のみ共有化し、テスト制約と衝突する箇所（BL-094同期説明・ツール一覧文）は各関数にliteralのまま残す、という判断基準を採用した。 |
| 決定内容 | (1) `call_decision_extractor`の未使用`prompt_old`（約60行）を削除。(2) モジュールレベル共有定数`_BL093_THINK_VALUE_PARAGRAPH`/`_THINK_TRAILER_SENTENCE`、共有関数`_verification_throttle_warning(example="")`を新設し、byte-identical/近似だった7関数（`call_task_planner`/`call_resource_arbiter`/`call_integrator`/`call_reviewer`/`call_goal_essence_analyst`/`generate_user_utterance`/`call_task_plan_reviewer`、および`call_expert`の`light_system_prompt`）に適用。(3) `call_detector`内の`domain_prompt`/`prompt`間の重複（気づき欄・issue引き継ぎ説明）は、関数外へは出さずローカル変数（`_observations_block`/`_issue_carryover_prefix`）で関数内集約。(4) BL-094同期説明は当初`_bl094_sync_template()`というパラメータ化ヘルパーを試みたが、`test_bl094_read_tool_orientation.py`の制約に抵触することが実際にテスト失敗で判明したため撤回し、各関数にliteralのまま残した（撤回の経緯をコード中にコメントとして明記）。(5) ツール一覧文（「あなたが使えるツールは...」）も同様の理由で各呼び出し元にインラインのまま維持。(6) `call_expert`の`system_prompt`/`light_system_prompt`の意図的な二重化（BL-025）は統合しない。 |
| 影響 | `cela_main.py`（9関数＋新規共有定数/関数群）。既存テスト11件（`test_bl087_stage2_task_plan_reviewer_node.py`/`test_bl087_task_planner_prompt_and_resubmission_fix.py`/`test_bl089_anti_repetition_instructions.py`/`test_bl094_read_tool_orientation.py`/`test_bl104_project_plan_toc_and_prompt_reorder.py`）を、共有ヘルパーへの集約に伴うリテラル文字列変更に合わせて更新。フルオフラインスイート514件Pass。 |
| 関連 BL | [BL-115](back_log/issue_backlog.md#bl-115-ノードプロンプト間の重複ボイラープレートおよびcall_decision_extractorの未使用デッドコードprompt_old) |

---

### D-107: BL-116（バス交通ドメイン特化例）は具体的な数値・語彙のみを一般化し、各例が伝える教訓（judgment criteria）自体は変更しない

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（Plan agentの設計案をレビューし採用） |
| **決定理由** | D-094が既に確立した設計原則（フレームワークの具体性は「判断基準と罠」に持たせるべきで、ラベル貼りに終わらせない）と同じ理由により、単に具体例を削除するのではなく、各例が実際に伝えている教訓（例: `call_task_plan_reviewer`の「Reviewerが絶対値の確定を強く求めすぎるとtask_plannerがゴール文にない数値をでっち上げる」という因果関係）は保持したまま、教訓を支える具体的な数値・ドメイン語彙（「山間部12km」「車両単価2,500万円」等）だけを一般化されたプレースホルダ表現に置き換える方針とした。教訓ごと薄めてしまうと、BL-117で議論した「フレームワーク名だけのラベル貼り」と同じ失敗を、今度は「具体例だけのラベル貼り」という形で繰り返すことになるため。 |
| 決定内容 | `call_task_plan_reviewer`/`call_task_planner`/`call_orchestrator`/`call_decision_extractor`の具体的な数値・ドメイン例を一般化。`call_expert`/`call_detector`/`generate_user_utterance`の労基法・シフト関連の記述は実際に読み直した結果、既に汎用的な表現であることを確認し変更しなかった（記録のみ）。`run_ai_vs_ai_loop`のCLIデフォルトデモゴール文字列は、ノードの指示文ではなくユーザーが選択する実行シナリオであるためスコープ外として変更しなかった。あわせて`generate_user_utterance`のf-string由来のゴミ引用符混入バグ（各行が個別に閉じられているかのように書かれ、`\n"`というリテラルな引用符がプロンプト本文へ混入していた）を発見・修正し、再発防止の回帰テスト2件を追加。 |
| 影響 | `cela_main.py`（4関数のドメイン例＋`generate_user_utterance`の複数箇所）。既存テスト2件（`test_bl087_stage2_task_plan_reviewer_node.py::test_reviewer_prompt_forbids_fabricating_values_absent_from_goal_text`・`test_bl087_task_planner_prompt_and_resubmission_fix.py::test_bl087_task_planner_prompt_references_the_12km_15_percent_failure_example`）を一般化後のリテラル文字列に合わせて更新。新規回帰テスト2件追加。フルオフラインスイート514件Pass。実LLM再ドライランでの一般化後のモデル理解度確認は次回待ち。 |
| 関連 BL | [BL-116](back_log/issue_backlog.md#bl-116-プロンプトへのバス交通シナリオ特化例の埋め込みおよび冗長な指示文ゴミ文字混入) |

---

### D-108: issue_logの「今すぐ解決」と「明示的に将来のtaskへ先送り」の二択（DEFER）はBL-082の申し送りパターンをそのまま再利用する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | ユーザー（スケジュール調整の必要性を指摘）＋Claude Sonnet 5（既存BL-082パターンの再利用を提案・実装） |
| **決定理由** | issue_logのescalated行にBL-086同様の「今回の発言内で必ず解決してください」という強制文言を追加する提案に対し、ユーザーから「フェーズをまたいだり、先送りされているものはそのタスクで解決するなど、スケジュール調整も必要」との指摘があった。前提エスカレーション（BL-086）は「ゴール文言と真の目的の矛盾」という即断すべき性質の懸念であるのに対し、issue_logの懸念は本質的にタスク横断・フェーズ横断の性質を持ちうる（BL-134の実例も、task_1_1で検知された懸念が実際にはtask_1_2の数値に関わるものだった）。強制解決一辺倒にすると、正当に後続タスクへ引き継ぐべき懸念まで無理やり今すぐ解決させようとする圧力になり、BL-082が「申し送り」（Directive/status=Deferred/defer_to_task_id）として既に解決済みの問題を車輪の再発明することになる。BL-082の`_append_deferred_note_to_plan`は「対象taskの計画文書に申し送りを追記する」という実績のある経路であり、issue_logにも同じ`defer_to_task_id`という語彙・同じ関数をそのまま再利用することで、一貫した設計にした。 |
| 決定内容 | `write_issue`ツールに`action_type="DEFER"`を追加（userロールのみ許可、RESOLVEと同じ権限階層）。`defer_to_task_id`（必須、task_planner確定済みリストへの実在チェック付き、BL-039のドット/アンダースコア正規化も踏襲）・`defer_reason`（必須）を指定すると、issue_logの`status`は変更せず（open/escalatedのまま）、新設した`defer_to_task_id`列のみ更新し、既存の`_append_deferred_note_to_plan`をそのまま呼び出して対象taskの計画文書へ申し送りを追記する。BL-125のタスク遷移ゲートは、この`defer_to_task_id`が設定済みの行をブロック対象から除外することで、「今すぐ解決」「明示的に将来のtaskへ先送り」のどちらかが済んでいれば遷移を許可する。 |
| 影響 | `cela_main.py`（`issue_log`テーブルへの`defer_to_task_id`列追加マイグレーション、`WRITE_ISSUE_TOOL`のパラメータ拡張、`_check_issue_permission`、`_write_issue_impl`のDEFER分岐）。新規テスト`tests/test_bl136_issue_visibility_and_transition_gate.py`のDEFER関連8件でカバー。 |
| 関連 BL | [BL-136](back_log/issue_backlog.md#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ) |

---

### D-109: BL-125のタスク遷移ゲートは、離脱するtaskに紐づくseverity='major'（=escalated）かつ未先送りのissueのみをブロック対象とする（minorはブロックしない）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-30 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（設計・実装）、ユーザー承認（Plan Mode） |
| **決定理由** | 当初、`raised_by='detector_auto'`（機械的バックアップ書き込み、severityは常にminorでCREATEされ再発回数のみでmajor化する）による昇格をゲート対象から除外する案を検討したが、ユーザーから「同じ問題が何度も見つかった＝未解決」という機械的昇格自体がD-079/D-080の意図通りの設計（強制的にmajor化し強制的に解決させる計画）であるとの説明を受け、この案を撤回した。結果として、raised_byを問わずseverity='major'（不変条件によりstatus='escalated'を伴う）であれば等しくゲート対象とする、というシンプルな基準に統一した。一方、severity='minor'（status='open'）はBL-136（本セッションでPart Aとして可視化）の対象に留め、タスク遷移そのものはブロックしない——軽微な懸念まで機械的に遷移をブロックすると、ドライラン全体が些細な指摘で頻繁に停止し、BL-096が意図した「軽量な気づきの記録」という性質と矛盾するため。 |
| 決定内容 | `_get_blocking_issues_for_transition`は`status='escalated' AND severity='major' AND last_seen_task_id=<離脱task> AND defer_to_task_id IS NULL/''`のみを対象とする。`raised_by`による除外は行わない。 |
| 影響 | `cela_main.py`（`_get_blocking_issues_for_transition`、`_resolve_task_transition`）。新規テストで`raised_by`を問わずブロックされること、およびminorはブロックされないことを確認（`tests/test_bl136_issue_visibility_and_transition_gate.py`）。 |
| 関連 BL | [BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-134](back_log/issue_backlog.md#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった) |

---

### D-110: BL-134候補(a)は罠（ピットフォール）注記として追加し、候補(c)（Detectorのconstraint_issue判定基準の緩和）は見送る

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-31 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（設計・実装・候補(c)見送りの判断） |
| **決定理由** | BL-134の未着手候補は2つあった。候補(a)「Expertが部分的な要件を無根拠に拡大解釈する際、ゴール文中の根拠を明示的に求める」はD-094が確立した「マインドセット／目的別行動オプション／罠」の3層モデルに沿った罠（ピットフォール）として素直に追加できる。一方、候補(c)「Detectorが疑義に気づきながらconstraint_issue判定に反映しない点の見直し」は、実際に`call_detector`のドメイン妥当性レビュープロンプト（判定基準）を確認したところ、「情報が不足していて確認できないことをmajorの根拠にしてはいけない」という制約が意図的に設けられていることが判明した。この制約はBL-012/D-011・BL-133が守ろうとしている「モデルの誤検知（false positive）を過度に許容しない」という設計と表裏一体であり、`tests/test_f26_detection.py::test_detector_no_false_positive_within_cap`という非退行テストで直接保護されている。24時間365日問題はまさに「ゴール文の『常駐』の解釈が曖昧」という情報不足型の疑義であり、現行基準通りconstraint_issue=majorではなくobservationsに回ったのは設計通りの動作だった。この経路（observations→issue_log）が実際に是正フローへ接続されていなかったことこそが真の問題であり、それは同日中にBL-125/BL-136で既に解消済みである。したがって候補(c)は、機能していない箇所ではなく、既に機能している判定基準を追加検証した上で「変更不要」と判断し、見送ることにした。 |
| 決定内容 | call_expert（Expertのドメイン妥当性チェック直後）とgenerate_user_utterance（User AIのドメインレビューチェックリスト）の双方に、部分的な要件の無根拠な拡大解釈を避けるための罠注記を追加。拡大解釈する場合はゴール文中の根拠を明示し、根拠が無い場合はconfidence="provisional"として扱いwrite_issueで記録するよう指示する。call_detectorの判定基準（`情報が不足していて確認できない`ことをmajorの根拠にしない、という文言）は変更しない。 |
| 影響 | `cela_main.py`（`call_expert`・`generate_user_utterance`の2箇所へプロンプト追加のみ、判定ロジック自体の変更なし）。新規テスト`tests/test_bl134_unsupported_generalization_guard.py`（3件、うち1件はcall_detectorの判定基準が変更されていないことを確認する非退行テスト）。フルオフラインスイート553件Pass。 |
| 関連 BL | [BL-134](back_log/issue_backlog.md#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった)、[BL-012](back_log/issue_backlog.md#bl-012-b51既知誤判定detectorの偽陽性の非退行テストが未定義)、[BL-133](back_log/issue_backlog.md#bl-133-test_detector_no_false_positive_within_capb51非退行d-011が層2リトライ枯渇によるフェイルクローズで33失敗しモデルの誤判定と誤認されるところだった) |

---

### D-111: `_resolve_task_transition`のトリガーを単一LLM出力フィールドだけに依存させず、抽出済みDirectiveからのフォールバックで補強する（BL-139）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-31 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ドライランレビュー依頼・「すぐ治しましょう」の実装指示）、Claude Sonnet 5（原因特定・設計・実装） |
| **決定理由** | `log/2026-07-31/0908`のレビューで、`checkpoint.json`の`current_task_id`が最後まで`task_1_2`のまま更新されず、対話ログ・whiteboardsの実態（task_2_1が数百ターン進行）と乖離していることが判明した。原因を追跡すると、`_resolve_task_transition`（BL-024の唯一の書き手）は`call_decision_extractor`という単一のLLM呼び出しが返す巨大なJSON出力の一項目`advances_to_task_id`のみに依存しており、当該ターンではUserが明示的にtask_2_1着手を指示し`extracted_events`自体には正しくtask_2_1向けのDirectiveが抽出されていたにもかかわらず、トップレベルの`advances_to_task_id`だけがnullで返るという抽出漏れが起きていた（`_resolve_task_transition`の完了・拒否いずれの`print`ログもrun全体で一件も出現せず、遷移処理自体が一度も成立していなかったことをログから直接確認）。これは単発の不運ではなく、大きなJSON出力の中でトップレベルの補助フィールドがLLMに軽視されやすいという構造的なリスクであり、BL-096（issue_logの自動起票バックアップ）と同種の「LLMの直接出力だけに頼らず、既に抽出できている構造化データから機械的に補完できる場合は補完する」という安全網パターンを適用するのが最も低リスクで即効性のある対策と判断した。プロンプト文言の調整のみで再発防止を図る案（BL-024の指示をさらに強調する等）も検討したが、プロンプト強化は再発リスクを下げるだけで根絶を保証できず、コード側の決定的な安全網の方が優先度が高いと判断した。BL-082の明示的先送り（`status="Deferred"`）は「今は移行しない」という意思表示であるため、フォールバック対象から明示的に除外する（先送りしたはずのDirectiveが誤って即時遷移トリガーとして扱われる事故を防ぐため）。 |
| 決定内容 | `decision_extractor_node`内、`_resolve_task_transition`呼び出し直前に、抽出済み`extracted_events`の中から現在タスクと異なる有効な`task_id`を持つDirective（`status != "Deferred"`）を探し、見つかればそれを`transition`の代替シグナルとして採用する。対象は`target_role="user"`の抽出のみ（Expert自身はタスク遷移を決定する権限を持たないため、BL-024の元の指示文言も User側の役割指示にのみ存在する）。LLMが正しく`advances_to_task_id`を返した場合はフォールバックは介入しない。 |
| 影響 | `cela_main.py`（`decision_extractor_node`）。新規テスト`tests/test_bl139_transition_fallback_from_directive.py`（4件: 実インシデント再現、Deferredの除外確認、正常経路の非上書き確認、Expert側では発火しないことの確認）。フルオフラインスイート557件Pass。 |
| 関連 BL | [BL-139](back_log/issue_backlog.md#bl-139-decision_extractor_nodeのtransition抽出がllm出力の1項目に依存しており明示的な次タスク指示があってもcurrent_task_idが更新されないことがあった)、[BL-024](back_log/issue_backlog.md#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)、[BL-039](back_log/issue_backlog.md#bl-039-decision_extractorが出力するtask_idの表記ゆれドット-vs-アンダースコアによりタスク遷移がドライラン全体で1回も成功していない)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ) |

---

### D-112: `THINK_TOOL`の`issues`パラメータを`scratch_concerns`へ改名し、`write_issue`との違いをdescriptionで明示する（BL-140）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-31 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（仮説提起・実装指示）、Claude Sonnet 5（検証・実装） |
| **決定理由** | `log/2026-07-31/1129`のレビューで、issue_logがモデル自身によって能動的に使われない件について、ユーザーから「thinkに書けば永遠に残ると勘違いしているのでは」という仮説が提起された。`THINK_TOOL`の実際のパラメータ定義を確認したところ、まさに`issues`という名前のフィールドが存在し、ツール全体のdescriptionにも「nothing is summarized away or aged out」（BL-108/BL-111）という永続性を示唆する文言があった。しかし`_think_handler`の実装は、この`issues`をモジュールレベルのグローバル変数（`_THINK_ISSUES`）へ一時保存するだけでDBには一切書き込まず、`_reset_think_scratchpad()`が`think`ツールを付与する各ノード関数の呼び出し開始時（＝1ターンごと）に必ず空にするため、そのツールループが終わった瞬間に完全に消える一時メモに過ぎなかった。実際、1129ログの4550行目でDetectorが`think(issues=[...])`へ書いた5件の懸念と、後に別のDetector呼び出しで実際に`write_issue`された懸念（21611〜21637行）がほぼ同一内容であり、モデルが「thinkに書いた＝記録した」と誤解して`write_issue`（真に永続化されターンをまたいで見える）の呼び出しを怠るリスクを裏付ける実例と判断した。名前の類似が原因の構造的な罠であるため、プロンプト文言の追加ではなくパラメータ名自体の改名で根本的に曖昧さを排除するのが最も確実な対策と判断した。 |
| 決定内容 | `THINK_TOOL`の`issues`パラメータを`scratch_concerns`へ改名し、descriptionに「このツール呼び出しループ内限定の一時メモであり、`write_issue`のような永続的なissue_logではない。ターンをまたいで残したい懸念は`write_issue`を使うこと」という趣旨を明記する。対応するモジュール変数`_THINK_ISSUES`→`_THINK_SCRATCH_CONCERNS`、`_think_handler`の返り値キー`current_issues`→`current_scratch_concerns`も同期して改名する。加えて、ユーザーから「各ノードのプロンプトでのツール説明では？」との指摘を受け、JSONツールスキーマのdescriptionだけでなく、`write_issue`と`think`が同一ターンで併記される`call_detector`（`_issue_carryover_prefix`共有変数）・`generate_user_utterance`のシステムプロンプト本文（自然言語の地の文）にも同趣旨の注記を追加する。モデルが実際の判断時に重視するのはJSONスキーマの細部より地の文の可能性が高く、両経路を揃えることで初めて曖昧さの排除が徹底される。 |
| 影響 | `cela_main.py`（`THINK_TOOL`定義・`_think_handler`・関連グローバル変数、`call_detector`の`_issue_carryover_prefix`・`generate_user_utterance`のプロンプト本文）。新規テスト3件（`tests/test_bl093_think_tool_scratchpad.py::test_think_tool_scratch_concerns_param_disambiguates_from_write_issue`・`test_call_detector_prompt_body_disambiguates_scratch_concerns_from_write_issue`・`test_generate_user_utterance_prompt_body_disambiguates_scratch_concerns_from_write_issue`）、既存テスト2件をキー名変更に追随。フルオフラインスイート560件Pass。次回ドライランでissue_log起票率の実際の改善が見られるかは要観察（プロンプトの曖昧さの一因を除去したのみで、モデルの行動が必ず変わる保証はない）。 |
| 関連 BL | [BL-140](back_log/issue_backlog.md#bl-140-think_toolのissuesパラメータ名がwrite_issueissue_logと混同されモデルが懸念を書いて満足し永続化しない誤解を誘発していた)、[BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-113: 【誤診断のためretracted】`expert_node`は差し戻し再提出をchat_historyへ新規追記せず、直前のassistantエントリを上書きする、という決定は撤回する（BL-141はinvalid）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-07-31（決定）／2026-08-01（撤回） |
| 状態 | `retracted`（誤診断に基づく決定だったため撤回。詳細はBL-141のissue_backlog記載を参照） |
| 決定者 | t-momose（問題提起・方針提示）、Claude Sonnet 5（原因特定・実装、および誤診断の発見・撤回） |
| **決定理由（当初、誤り）** | `expert_node`の末尾（`call_expert`呼び出し以降）だけを確認し、`chat_history`へ`assistant`メッセージが無条件追記されていると誤って結論づけた。 |
| **撤回理由** | `expert_node`の**冒頭**（`call_expert`呼び出しの直前）に、このセッション開始前から既に「`constraint_issue=="major"`のとき、chat_history末尾が`assistant`ならpopしてから呼ぶ」というガード節が存在しており（`git show HEAD:cela_main.py`で確認、User側`generate_user_utterance_node`にも同型のpopロジックあり）、差し戻しのたびに「pop 1件・append 1件」で正味の増減が0になる設計が既に機能していた。つまり報告された「chat_history_windowが同一タスクの往復だけで埋まる」問題は当初から存在せず、この決定・実装は不要な重複コードを追加するものだった。 |
| 対応 | 追加した重複コード（`expert_node`末尾の上書き処理）を削除し、既存の冒頭popロジックのみへ戻した。回帰テスト`tests/test_bl141_expert_retry_chat_history_collapse.py`は、既存の冒頭popロジックを正しく検証する内容へ全面差し替えた。 |
| 教訓 | 対象関数のソースを部分的にしか読まずに「無条件で実行される」と断定しない。ループ内の条件分岐が関数冒頭のガード節にあるパターンは見落としやすく、`inspect.getsource()`等で関数全体を俯瞰してから挙動を判断すべきだった。 |
| 関連 BL | [BL-141](back_log/issue_backlog.md#bl-141-誤診断のためinvaliddetectorexpertの差し戻しループのたびにchat_historyへ新規assistantメッセージが無条件追記されると当初診断したが実在しなかった)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ) |

---

### D-114: Userの承認発言がmajor判定された際、Expertへの修正指示の代わりに承認を言い換えるだけの空回りを防ぐため、承認の明示的撤回をプロンプトで強制する（BL-142）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-01 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（診断の言語化・方針提示）、Claude Sonnet 5（原因特定・実装） |
| **決定理由** | `log/2026-08-01/2329`で、task_1_1がホワイトボードVer.1〜21まで改訂され続け`stagnant`判定でHALTした原因を調査した。ドメイン上の欠陥（M-07の人件費倍率が「2.5倍」と「3倍」で矛盾したまま残存等）は正当だったが、構造的な増幅要因も判明した：Userの「承認・次タスクへ移行」発言が`user_detector`にmajor判定されると、`route_after_user_detector`がExpertではなくUser AI自身へ差し戻す設計のため、19399〜19480行で実質同じ承認文が5ラウンド言い換えられるだけの空回りが発生し、根本原因（ホワイトボードの数値矛盾）には一切手が入らなかった。ユーザーが「ユーザーの承認系の発言の監査は、間違っている部分を指摘しつつ、承認を取り消し、エキスパートに訂正させるよう促すような言葉を発信するようにプロンプトで強くガイドラインしてあげなければならない」と整理し、これを採用した。既存の差し戻しプロンプトには一般的な「Agent AIへ修正を要求してください」という指示はあったが、「却下された発話が承認だった場合は明示的に撤回せよ」という具体的な指示が欠けていたため、モデルが言い回しを変えるだけで同じ承認を繰り返す抜け道を許していた。なお、この挙動変化がモデル切り替え（過去のGemini 2.5から現在のOpenRouter経由`ling_3_flash`への変更、`cela_main.py`のコメントアウトされた旧設定から確認）に起因する可能性についてユーザーから言及があったが、断定はできないため、原因追及よりプロンプト側の防御強化を優先した。 |
| 決定内容 | `generate_user_utterance`のmajor判定時プロンプトブロックへ、却下された前回発話が「承認」「次タスクへの移行」だった場合は、言い回しを変えただけの同じ承認の繰り返しを禁止し、`write_agreement(status="Rejected")`で承認を明確に撤回した上でAgent AIへ具体的な修正指示を出すことを求める一文を追加する。 |
| 影響 | `cela_main.py`（`generate_user_utterance`）。新規テスト`tests/test_bl142_user_approval_retraction_guidance.py`（2件）。次回ドライランで実際にUser AIが承認撤回→Expert差し戻しの動作をとるようになるかは要観察（プロンプト強化のみで、モデルの行動が必ず変わる保証はない）。 |
| 関連 BL | [BL-142](back_log/issue_backlog.md#bl-142-userの承認発言がmajor判定されてもexpertへの修正指示ではなくuser-ai自身への言い直し要求に留まり同じ承認を言い回しを変えて繰り返す空回りが発生していた)、[BL-124](back_log/issue_backlog.md#bl-124-bl-086escalate_premise_concernfreeze_agreementrevise_goalがツールとして常時提供されているのにまさに想定されたケースで一度も使われずstagnanthaltに至った) |

---

### D-115: 差し戻しプロンプトへ、Mermaid等の全体図ではなくPython側で機械的に計算した「現在地ラベル」（差し戻し回数・繰り返し検知）を注入する（BL-143）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-01 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（設計相談・確認質問）、Claude Sonnet 5（調査・設計・実装） |
| **決定理由** | ユーザーから「各ノードが今の状況とやるべきことの整理をもっとよりよくできる仕組みはないか、例えばMermaidで図を書いて議論の流れを示し、いま自分がやるべき思考の分岐を示せないか」との相談があった。AIは、LLMに図の解釈という追加の推論ステップを委ねるより、CELAが既にBL-086/BL-125/BL-136/BL-142で使っている「Pythonのif/elseでstateを判定し、該当分岐専用の指示文だけを決定論的に注入する」パターンの方が確実性が高いと回答した。続けてユーザーが「いま現在はDetectorの指摘文だけのっているんでしたっけ？」と確認し、AIが調査した結果、User/Expert双方の差し戻しプロンプトには`constraint_issue_log[-1:]`（Detectorの直近1件の判定の生repr）のみが載っており、「何回目の差し戻しか」（`user_retry_count`/`expert_retry_count`はルーティング判定にのみ使われプロンプトには一切出ていなかった）・「前回と同じ指摘の繰り返しか」という、Python側で既に計算可能なのに渡っていない情報が欠けていたことが判明した。BL-142で見た「Userが気づかず同じ承認を繰り返す」空回りも、この現在地情報の欠如が一因と考え、Mermaid案は採らずPython側で計算する現在地ラベルを追加する方針とした。 |
| 決定内容 | 新規ヘルパー`_build_retry_situation_label(state, retry_count, max_retries=3)`を新設し、(1) 差し戻し回数と残り試行回数（`route_after_*_detector`の`retry_count>=3`エスカレーション条件と揃えたmax_retries=3）、(2) `retry_count>=2`（同一差し戻し連鎖内であることが保証される場合のみ）で`constraint_issue_log`直近2件のcommentを`difflib.SequenceMatcher`比較し類似度0.6以上なら繰り返し警告、の2点を機械的に生成し、`call_expert`・`generate_user_utterance`双方の差し戻しプロンプト冒頭へ注入する。 |
| 影響 | `cela_main.py`（新規`_build_retry_situation_label`、`call_expert`・`generate_user_utterance`）。新規テスト`tests/test_bl143_retry_situation_label.py`（8件）。フルオフラインスイート574件Pass。次回ドライランでUser/Expertがこの現在地情報を踏まえた行動を取るようになるかは要観察。 |
| 関連 BL | [BL-143](back_log/issue_backlog.md#bl-143-差し戻しプロンプトにdetectorの指摘文だけが載っており何回目の差し戻しか前回と同じ指摘の繰り返しかというpython側で計算可能な現在地情報が渡っていなかった)、[BL-142](back_log/issue_backlog.md#bl-142-userの承認発言がmajor判定されてもexpertへの修正指示ではなくuser-ai自身への言い直し要求に留まり同じ承認を言い回しを変えて繰り返す空回りが発生していた) |

---

### D-116: `reflection_node`のBL-096機械的stagnant上書きを、escalated issueの単なる「存在」ではなく「ユーザーノードを3回通過しても未解決」という滞留に条件を絞る（BL-144）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-02 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（閾値の指定・承認）、Claude Sonnet 5（調査・設計・実装） |
| **決定理由** | `log/2026-08-02/0832`のドライランレビューで、reflection自身が明確に`"continuing"`（健全な進捗中）と判定していたサイクルまで、BL-096の機械的上書き（escalated行が1件でもあれば無条件でstagnant化）によりfacilitation_countの猶予が誤って消費されていたことが判明した。AIから「同じescalated issueが複数サイクルにわたって進展していない場合のみstagnantとする」という改善方針を提案したところユーザーが同意し、具体的な閾値として「ユーザーノード（`generate_user_utterance_node`）を3回通過する」を明示的に指定した。 |
| 決定内容 | `LineageState`へ新規フィールド`escalated_issue_first_seen_round: dict[str, int]`（issue_log行id→初めてescalated状態で観測した`round_count`）を追加。`reflection_node`はescalated行ごとに初観測roundを記録し、現在の`round_count`との差が3以上（＝ユーザーノードを3回通過しても未解決）の行が1件でもあれば`discussion_status`を`"stagnant"`へ上書きする。解決・先送り済みで一覧から消えたissueは追跡からも削除する（再度escalatedになれば新規の滞留として扱う）。 |
| 影響 | `cela_main.py`（`LineageState`、`reflection_node`、初期state辞書）。新規テスト`tests/test_bl144_escalated_issue_staleness_threshold.py`（4件）。`python -m py_compile`合格、フルオフラインスイート578件Pass。`write_issue`のRESOLVE/DEFERが依然ほぼ呼ばれない現状では、閾値を上げるだけでは根本解決にならず、issueの実際の解決を促す仕組み（BL-136の強制プロンプト、BL-145の検討中の方針等）との併用が前提。 |
| 関連 BL | [BL-144](back_log/issue_backlog.md#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設) |

---

### D-117: `write_agreement`のCREATE/UPDATEは実効上のcurrent_task_idと一致するタスクのみを対象とし、SUPERSEDEのみ例外とする（BL-146）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-02 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（バグ修正の承認、SUPERSEDE経路の確保についての確認質問）、Claude Sonnet 5（調査・設計・実装） |
| **決定理由** | `log/2026-08-02/0832`の「BL-125ブロック後もOrchestratorがtask_1_2の作業を進めた」という指摘の詳細調査で、`current_task_id`自体は巻き戻っておらず、実際には`write_agreement`がBL-131（task_plannerの計画への実在チェック）しか行っておらずBL-125のブロック対象（`state["current_task_id"]`）とは無関係に任意タスクへの書き込みを許してしまう、という別のバグが根本原因だと判明した。書き込み（進捗の記録）は、遷移がまだ許可されていないタスクに対しては行わせるべきではないという判断のもと、current_task_id一致を強制する方針とした。ユーザーから「後続タスクの検討結果、先発タスクの成果物を修正する必要がある場合の経路は確保されているか」との確認があり、既存のSUPERSEDE機構（BL-062/080/084）がまさにこの正規の改訂経路であることを確認し、このゲートの対象外として維持することで合意した。read（参照読み）側は別問題としてBL-147で対応し、こちらは書き込みのみに限定した（他タスクの成果物を参照しながら作業すること自体は正当な用途のため）。 |
| 決定内容 | `_effective_current_task_id_from(state)`（`_get_current_task`のcurrent_phase先頭タスクへのフォールバックを再利用）を新設し、`_write_agreement_impl`でentry_type in (Directive, Deliverable)かつaction_type != SUPERSEDEの場合、task_idがこの実効値と一致しなければ拒否する。`current_phase`/`phases`情報が無い簡易呼び出しはフェイルオープンでスキップする。 |
| 影響 | `cela_main.py`（`_effective_current_task_id_from`、`_write_agreement_impl`、`TOOL_DISPATCH["write_agreement"]`）。新規テスト`tests/test_bl146_write_agreement_current_task_gate.py`（6件）。既存`tests/test_bl131_write_agreement_task_id_validation.py`（9件）は無修正でPass。フルオフラインスイート596件Pass。 |
| 関連 BL | [BL-146](back_log/issue_backlog.md#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-131](back_log/issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク) |

---

### D-118: `read_deliverable_file`はtask_id指定時、file_path併用の有無に関わらず計画への実在チェックを先に行う（BL-147）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-02 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（調査・設計・実装、ユーザーの包括承認「見つけたバグはすべて直す」の範囲内） |
| **決定理由** | D-117と同じ調査過程で、`read_deliverable_file`が`write_agreement`（BL-131）と異なりtask_idの実在チェックを一切行っておらず、特にtask_idと`file_path`を同時指定した場合はtask_idが実質無視されfile_path側でそのまま読めてしまう抜け道があると判明した。読み取り（他タスクの成果物を参照する用途）自体はD-117とは異なり正当な用途のため制限すべきではないが、「存在しない/誤ったtask_idを指定しても気づかれない」という防御の欠如自体はBL-131と同型のリスクであり、既存パターン（実在チェック）を再利用して塞ぐこととした。 |
| 決定内容 | `_read_deliverable_file_handler`に`state`引数を追加し実際に受け取るようにした上で、task_id指定時はfile_path分岐に入るより先に`_find_task_by_id`/`pending_task_ids`による実在チェックを行う。存在する他タスクの成果物への参照読みは従来通り制限しない。 |
| 影響 | `cela_main.py`（`_read_deliverable_file_handler`、`TOOL_DISPATCH["read_deliverable_file"]`）。新規テスト`tests/test_bl147_read_deliverable_file_task_id_validation.py`（6件）。既存`tests/test_r3_smoke.py::test_bl040_read_deliverable_file_lookup_by_task_id`をstate明示指定・新エラー挙動に合わせて更新。フルオフラインスイート596件Pass。 |
| 関連 BL | [BL-147](back_log/issue_backlog.md#bl-147-read_deliverable_fileがtask_idの実在チェックを一切行っておらずfile_path併用時は事実上無視される)、[BL-131](back_log/issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、[BL-040](back_log/issue_backlog.md#bl-040-read_deliverable_fileがfile_path直接指定に依存し実質的に発見不能だった問題) |

---

### D-119: Orchestratorに読み取り専用ツール（read_project_plan/read_deliverable_file/read_verified_fact/think）のみを付与し、書き込み系ツールは与えない（BL-148）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-02 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「Orchestratorのツールは必要な情報が見れるツールが渡されていますか？Orchestratorもツールループ化が必要です」との明示的指示）、Claude Sonnet 5（調査・設計・実装） |
| **決定理由** | `log/2026-08-02/0832`調査で、Orchestrator（`call_orchestrator`）がツールを一切持たない単発JSON応答で、`current_task_id`・計画・issue状況を一切参照できないまま専門家選定を行っていることが判明した。対話の生テキストのみに基づく選定が、BL-125でブロックされているタスクとは別のタスクへ対話が漂った際に専門家選定を引きずられさせ、Detector自身が「プロンプトのバグだと思う」と自己申告するほどの構造的矛盾を生んでいた。これはBL-109（call_orchestratorを含む単発判定4ノードからTHINK_TOOLを外しtools=Noneへ差し戻した決定）への回帰ではないかと検討したが、BL-109の趣旨は「複数ツールを組み合わせる必要のない単発判定タスクにTHINK_TOOL単体だけ持たせても無意味」という点にあり、今回付与するのは複数の実質的な読み取りツールであるため趣旨は異なる。BL-126 Stage Dで`call_facilitator`が同様の理由（本質対話で書き込み系ツールが必要になった）でBL-109対象外へ変更された前例があり、これと同型の「正当な理由が生じたノードをBL-109対象から個別に除外する」パターンを踏襲した。書き込み系ツールを与えない理由は、Orchestratorの出力が専門家選定メタデータに限定され状態を変更しない役割であるため（`_check_write_permission`のロール表にも`"orchestrator"`は存在しない）。 |
| 決定内容 | `call_orchestrator`のプロンプトへ`_build_task_scope_context`/`_build_project_plan_toc`による現在タスクの構造化情報を追加し、`query_AI`呼び出しへ`tools=[READ_PROJECT_PLAN_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_VERIFIED_FACT_TOOL, THINK_TOOL], state=state`を付与する（書き込み系ツールは含めない）。BL-109の対象一覧から`call_orchestrator`を除外する。`orchestrator_node`の入出力契約は変更しない。 |
| 影響 | `cela_main.py`（`call_orchestrator`）。既存`tests/test_bl093_think_tool_scratchpad.py::test_bl109_single_shot_judgment_nodes_reverted_to_tools_none`を更新、新規`test_bl148_call_orchestrator_is_tool_loop_capable`・`_NODE_TOOL_NAME_REMINDERS`エントリ、新規`tests/test_bl148_orchestrator_tool_loop.py`（4件）追加。既存`tests/test_bl078_orchestrator_focus_guidance.py`は無修正でPass。フルオフラインスイート596件Pass。ツールループ化によるレイテンシ・トークンコスト増（他の周期実行ノードより高頻度で呼ばれるため）は次回実ドライランでの観察事項として残す。 |
| 関連 BL | [BL-148](back_log/issue_backlog.md#bl-148-orchestratorがcurrent_task_id計画成果物を一切参照できないままexpert選定focus_guidanceを決めていた)、[BL-109](back_log/issue_backlog.md#bl-109-複数ツールを組み合わせて検討する必要のない単発判定抽出4ノードorchestratordecision-extractorreflectionfacilitatorからthink_toolを外しtoolsnoneの単一応答パスへ差し戻す)、[BL-146](back_log/issue_backlog.md#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた) |

---

### D-120: `call_detector`のescalation pin注入はドメイン妥当性レビュー（Pass 1）にのみ行い、数値監査（Pass 2）は対象外とする（BL-123）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（調査・設計・実装、ユーザーの「即効性項目セット（BL-123・BL-135）」選択の範囲内） |
| **決定理由** | 別AI（Cline/deepseek経由）によるコードベース全体レビューでBL-123（`_build_escalation_pin_text`が`call_expert`/`generate_user_utterance`には注入されているが`call_detector`には一切注入されていない）が再指摘され、コードを直接確認して正確と検証した。`call_detector`はドメイン妥当性レビュー（Pass 1、前提・実現可能性等を評価）と数値監査（Pass 2、算術検算に専念、既存の明示的指示で「ここでは検算する必要はありません」とスコープを絞っている）という独立した2つのLLM呼び出しを持つため、どちらに注入するかが実装上の分岐点だった。escalated issueは典型的にドメイン・前提レベルの懸念（労基法、実現可能性等）でありPass 1と意味的に最も適合すること、Pass 1の指摘が既存の`domain_findings_block`経由でPass 2へ既に伝播する設計があることから、Pass 1のみへの注入で十分と判断し、Pass 2の「検算専念」というスコープの明確さを崩さないことを優先した。 |
| 決定内容 | `call_detector`内、`domain_prompt`構築直前で`escalation_pin`/`escalation_pin_block`を計算し（`_build_escalation_pin_text(get_active_conn(), state["run_id"])`、`call_expert`と同じ条件分岐パターン）、`domain_prompt`のf-string内、他のDB由来コンテキストブロック（Freeze状況等）と並ぶ位置へ埋め込む。`prompt`（数値監査パス）側には注入しない。 |
| 影響 | `cela_main.py`（`call_detector`）。新規テスト`tests/test_bl123_detector_escalation_pin.py`（3件: `_build_escalation_pin_text`参照確認、Pass 1限定の確認、条件分岐埋め込みの確認）。フルオフラインスイート600件Pass。実LLM再ドライランでDetectorがescalated issueを把握した上で判定していることの確認は次回待ち。 |
| 関連 BL | [BL-123](back_log/issue_backlog.md#bl-123-call_detectorだけがescalated-issueの強制注入_build_escalation_pin_textbl-103を受け取っておらず他ロールが既に折り込み済みの懸念を独立に再判定してしまう)、[BL-103](back_log/issue_backlog.md#bl-103-hydrateノード間コンテキスト引き継ぎの改善) |

---

### D-121: `ask_user_question`の`blocking_reason`を`expert_pending_question`と同じ寿命でstateへ伝播し、User AIの相談応答プロンプトへ表示する（BL-135）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | Claude Sonnet 5（調査・設計・実装、ユーザーの「即効性項目セット（BL-123・BL-135）」選択の範囲内） |
| **決定理由** | 別AI（Cline/deepseek経由）のレビューでBL-135（`ASK_USER_QUESTION_TOOL`の`required`パラメータ`blocking_reason`がUser AIの相談応答プロンプトに埋め込まれていない）が再指摘された。調査の結果、`_ask_user_question_tool_impl`は既に`blocking_reason`を`_LAST_ASK_USER_QUESTION`へ正しく格納し`get_last_ask_user_question()`もそれを含む辞書を返す設計だったため、ツール本体の変更は不要と判明し、欠けていたのは`expert_node`での`state`への反映と`generate_user_utterance`での表示のみだった。`expert_pending_question`と全く同じライフサイクル（`expert_node`が設定、`generate_user_utterance_node`が消費・リセット）を持つ姉妹フィールドとして扱うのが最も一貫性が高いと判断した。 |
| 決定内容 | `LineageState`へ`expert_blocking_reason: str`を追加（`expert_pending_question`の直後、同じ寿命管理コメント下）。初期state辞書にも追加。`expert_node`が`state["expert_pending_question"]`設定の直後に`state["expert_blocking_reason"] = _ask_q["blocking_reason"] if _ask_q else ""`を追加。`generate_user_utterance_node`の消費・リセット箇所（`expert_consultation_mode`/`expert_pending_question`のリセットと同じ場所）にも`expert_blocking_reason`のリセットを追加。`generate_user_utterance`のBL-130相談応答モードのプロンプトへ、`質問: {state['expert_pending_question']}`の直後に`理由: {state.get('expert_blocking_reason', '')}`を追記。 |
| 影響 | `cela_main.py`（`LineageState`、初期state辞書、`expert_node`、`generate_user_utterance_node`、`generate_user_utterance`）。`tests/test_bl130_ask_user_question.py`へ4件のアサーション追加＋新規テスト1件（計5件変更）。フルオフラインスイート600件Pass。`ask_user_question`が実際に呼ばれるドライランでの表示確認は次回待ち。 |
| 関連 BL | [BL-135](back_log/issue_backlog.md#bl-135-ask_user_questionのblocking_reasonがuser-aiの相談応答プロンプトに埋め込まれていない)、[BL-130](back_log/issue_backlog.md#bl-130-expertが成果物を出さずにuser-aiへ質問相談できる双方向チャネルが未設計現状はuserexpertへの一方向指示のみ) |

---

### D-122: `_apply_text_edits`のold_text不一致エラーへ、格納内容の実際のスニペットを含める（BL-151）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「2の修正案で修正」との指示、「他で同じような装飾字の罠がないか調査」の追加指示）、Claude Sonnet 5（原因特定・設計・実装・調査） |
| **決定理由** | `log/2026-08-03/1110`ドライランで、BL-086の中心機能である`revise_goal`（発注者自身が前提矛盾に気づきゴールを是正する経路）が初めて実発火したにもかかわらず、edits[0]が最低9回連続で同一理由で失敗し続けていることが判明した。原因は`generate_user_utterance`がゴール文を表示する際に付加する装飾（「👉 {user_goal}」、6736行目、改行を挟まず本文と同じ行に連結）が、`revise_goal`が実際に照合する`_CURRENT_GOAL_TEXT`（装飾を含まない生のシナリオ定義文）には存在しないことだった。修正案として(1)`_revise_goal_tool_impl`が照合前に先頭の「👉 」を機械的に除去する狭い対症療法、(2)`_apply_text_edits`が不一致時に実際の格納内容をエラーへ含め、モデルが同ターン内で自己修復できるようにする堅牢な修正、の2案を提示したところユーザーが(2)を選択した。(2)は特定の絵文字パターンに依存しない一般解であり、`write_agreement`の同種`edits`経路（whiteboard更新）にも同じ恩恵が及ぶ点、および将来別の表示専用装飾が同種の乖離を生んだ場合にも自己修復可能になる点で、根本原因への対症療法(1)より優れると判断した。 |
| 決定内容 | `_apply_text_edits`（cela_main.py:4041〜）へ`content_label: str = "現在のホワイトボード内容"`パラメータを追加。`exact_count==0`（完全一致・緩い一致とも0件）の分岐で、`current_content`の先頭`_TEXT_EDIT_SNIPPET_MAX_CHARS`（400字）をエラーメッセージへ追記する（超過時は「…（以下省略）」を付与）。`_revise_goal_tool_impl`の呼び出しでは`content_label="現在のゴール文"`を明示指定する。あわせて`state['goal']`/`user_goal`の全埋め込み箇所（`call_orchestrator`・`call_expert`・`call_reflection`）と、`write_agreement`が参照するホワイトボード表示・Decision型agreements一覧表示を調査し、同型の装飾は他にも存在するが（a）exact-text一致を要求する`revise_goal`はuserロール専用でExpert/Orchestrator/Reflectionは呼べない、（b）ホワイトボード表示は見出しと本文が改行で分離されており同一行連結の罠になっていない、（c）Decision型agreements一覧の同一行連結装飾は`write_agreement`の`edits`機構がentry_type="Deliverable"限定のため対象外、の3点により現状は機能的な罠になっていないことを確認し、追加のコード変更は不要と判断した。 |
| 影響 | `cela_main.py`（`_apply_text_edits`、`_revise_goal_tool_impl`）。新規テスト`tests/test_bl151_apply_text_edits_error_snippet.py`（8件）追加。既存`tests/test_bl081_edits_loose_match_fallback.py`・`tests/test_bl086_escalation_freeze_goal_revision.py`は無修正でPass。`python -m py_compile`合格。08-03/1110ドライランは本修正後の再ドライランでの効果確認が次回待ち（本修正時点でランは継続中のため、修正はコードへのみ適用しライブプロセスへは影響しない）。 |
| 関連 BL | [BL-151](back_log/issue_backlog.md#bl-151-revise_goalのold_textがプロンプト表示専用の絵文字装飾を含んでいたため9回以上自己修復に失敗し続けた)、[BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化)、[BL-081](back_log/issue_backlog.md#bl-081-write_agreementのeditsold_textnew_textがmarkdownテーブル行頭の全角スペースパイプ記号の有無で完全一致に失敗しやすかった) |

---

### D-123: escalated issueをReflectorの正当性監査経由でタスクプランナーへ組み込む際、issueは`resolved`ではなく新ステータス`planned`へ遷移させる（BL-145）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（`resolved`→`planned`への変更指示、DEFER済み除外・監査行不要・回数上限不要の各確認）、Claude Sonnet 5（調査・設計・実装、Plan ModeでExplore/Planエージェントを併用） |
| **決定理由** | `log/2026-08-03/1347`で、detector_auto起票の汎用issueが一度もRESOLVE/DEFERされないままBL-125のタスク遷移ゲートを塞ぎ続けSUPERSEDE迂回（BL-152の引き金）を招く実害を確認し、ユーザー提案済みのBL-145（issue→タスク明示化）に着手した。Plan agentの当初案は「task_planner_nodeの計画再構成成功直後、対象issueを即座にresolvedにする」だったが、ユーザーが「resolvedとするのは語弊が生まれる可能性がある」「延期も可能とする」「無理やり解決しようとして議論のデッドロック化も避けたい」と指摘。task_plannerが計画へ組み込んだ事実は「対応予定ができた」に過ぎず「本当に解決した」ことの証明にはならないため、真の解決確認はuser role経由の既存write_issue(RESOLVE)に委ね、task_planner側は新ステータス`planned`（計画済み）への遷移に留めるべき、というユーザー自身の設計判断による。あわせて、既にDEFER済みのstale issueは二重の受け皿を避けるため対象外とする、write_agreementでの追加監査行は既存のdecision_log+resolution_note相当の記録で十分なため追加しない、issue駆動の再構成回数に追加の上限は設けない（planned後はescalated一覧・滞留追跡から自然に外れ自己抑制される）、の3点もユーザー確認済み。 |
| 決定内容 | `reflection_node`がBL-144の滞留検知（3ラウンド未解決）と既存DEFER除外フィルタで対象issueを特定し、`plan_revision_reason`/新規`plan_revision_issue_ids`経由で`task_planner_node`へ引き継ぐ。`task_planner_node`は計画再構成成功後、新規ヘルパー`_mark_issue_planned`（id基準の直接DB更新、`_check_issue_permission`を経由しない非LLMゲート）で対象issueを`status='planned'`へ遷移させ、埋め込み先task_idを既存の`defer_to_task_id`列（BL-136のDEFERと同じ意味を再利用）に記録する。`'planned'`は`_write_issue_impl`の`status != 'resolved'`判定を満たすため、既存のDEFER（さらなる先送り）・CREATE経由の再発検知（occurrence_count>=2での再escalated化）がコード変更なしでそのまま機能する。真の`resolved`化はuser roleの既存経路にのみ許可する。`state["phases"]`への軽量差分編集APIの新設は本BLの範囲外とし、既存の`plan_revision_reason`→全再生成経路を再利用する（将来BLへ切り出し）。`facilitator_node`のEssence Dialogue収束には、`plan_revision_reason`使用中は上書きしない防御ガードを追加（グラフトポロジ解析上は現状衝突しないが将来の変更への防御）。`planned`issueは`generate_user_utterance`へ非強制の参考情報として可視化する。 |
| 影響 | `cela_main.py`（`LineageState`、`reflection_node`、`task_planner_node`、新規`_mark_issue_planned`/`_get_planned_issues`/`_build_planned_issue_pin_text`、`facilitator_node`、`generate_user_utterance`）。新規テスト`tests/test_bl145_issue_driven_plan_formalization.py`（16件）追加。既存BL-096/086/126 Stage C・D/136/144/146-148関連テスト（132件）は無修正でPass。`python -m py_compile`合格、フルオフラインスイート623件Pass。実ドライランでの効果確認（issue formalizationの実発火、`planned`issueの後続タスク内言及）は次回待ち。 |
| 関連 BL | [BL-145](back_log/issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)、[BL-136](back_log/issue_backlog.md#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-144](back_log/issue_backlog.md#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた)、[BL-152](back_log/issue_backlog.md#bl-152-verify_whiteboard_excerptが今レビューすべき成果物ではなく常にcurrent_task_idのホワイトボードだけを見ていた) |

---

### D-124: Expertへ`write_issue`の直接アクセスを与えず、`decision_extractor_node`のDirective/Deferred自動抽出をissue_logへ橋渡しする（BL-154）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（issue_logスキーマ・BL-125判定基準の確認質問、「先送りはすべてissueにまとめたほうがよい？」への「お願いします」承認）、Claude Sonnet 5（調査・設計・実装、Plan agent 1体を併用） |
| **決定理由** | BL-145完了後のQ&Aで、issue_log（write_issueツール）・agreementsのDirective/Deferred（decision_extractor_nodeの自動抽出）・plan_draftsの「先送り事項」という3つの並行した先送り追跡機構が互いを認識していないことが判明した。特にExpertは`write_issue`ツール自体を持たない（`WRITE_ISSUE_TOOL`は`call_detector`/`generate_user_utterance`のみ）ため、Expertが成果物内で宣言する先送りはagreements/plan_drafts経由でしか捕捉されず、BL-125の遷移ゲート・BL-144の滞留検知・BL-145のタスク明示化というissue_log依存のセーフティネットが一切効かない状態だった。Expertへ`write_issue`の直接アクセスを与える案は、BL-025のロール分離思想（Detectorの独立監査という趣旨とExpertの自己申告が混同される）に反するため採用せず、代わりに`decision_extractor_node`という既存のPython側自動処理が、既存の自動抽出と同時にissue_log側にも橋渡しする方式を採用した。 |
| 決定内容 | `_check_issue_permission`へ`decision_extractor_auto`（CREATE専用、`detector_auto`と同型の内部専用ロール、`WRITE_ISSUE_TOOL`のスキーマは無変更でLLM経路からは到達不能）を追加。`_write_issue_impl`のCREATE分岐を拡張し、このロールのみ`defer_to_task_id`を作成時点で設定可能に（再発時は最新宣言が勝つ、他ロールは無変更）。`decision_extractor_node`のDirective/Deferred処理箇所（既存の`_append_deferred_note_to_plan`直後）へ、このロールでの`_write_issue_impl`呼び出しを追加。Expert/User双方の抽出ブランチに`target_role`によるゲーティングをせず一律適用する（BL-082がかつてUserブランチだけ先送り検出が欠けていた非対称バグの前例を踏まえた判断）。`_build_open_issue_pin_text`を拡張し`defer_to_task_id`設定済みのopen issueには対応予定task_idを表示する。BL-125/144/145は`raised_by`を一切参照しないため無変更で対応する。 |
| 影響 | `cela_main.py`（`_check_issue_permission`、`_write_issue_impl`、`decision_extractor_node`、`_build_open_issue_pin_text`）。新規テスト`tests/test_bl154_decision_extractor_issue_log_bridge.py`（8件）追加。既存BL-082/096/125/136/139/144/145関連テストは無修正でPass。`python -m py_compile`合格、フルオフラインスイート630件Pass（1件failedは本BLと無関係の既存未コミット差分、issue_backlog.md BL-154参照）。留意点：この経路由来のissueは`defer_to_task_id`が誕生時から設定済みのため、escalated化後もBL-125のブロック判定には決して該当しない（手動DEFER済みissueと同じ既存仕様、新規の抜け穴ではない）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-154](back_log/issue_backlog.md#bl-154-decision_extractorのdirectivedeferred自動抽出をissue_logへも橋渡しする)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-145](back_log/issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する) |

### D-125: `MAX_TOOL_ITER`を20→30へ引き上げる（BL-155）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装済み、テスト追従のみ実施） |
| 決定者 | t-momose（承認・理由提示） |
| **決定理由** | task_plan_reviewerによる差し戻し発生時、task_plannerが差し戻し対象タスクの内容を1件ずつ改めて把握し直す過程でツール呼び出し回数が嵩み、旧上限20に迫り非収束クラッシュのリスクが実ドライランで観測されたため。値自体は本セッション開始前から作業ツリーに未コミットで変更済み（コード内コメントに変更理由の追記なし、対応するBL/D記録も未作成）だった。フルオフラインスイートで`tests/test_bl093_think_tool_scratchpad.py::test_max_tool_iter_raised_to_20`の失敗として顕在化したため、AGENTS.md §7（定数変更の厳格管理）に従い実装は変更せずユーザーに確認を仰いだところ、上記理由が明示的に提示されたため正式に承認・記録する。 |
| 決定内容 | `cela_main.py`の`MAX_TOOL_ITER`は30のまま維持（コード変更なし）。既存の変更履歴コメント（BL-014→BL-028→BL-093の来歴が並記されている箇所）へ20→30の変更理由を追記。テストを`test_max_tool_iter_raised_to_30`へ改名し期待値を30に更新。 |
| 影響 | `cela_main.py`（コメントのみ追記、`MAX_TOOL_ITER`の値自体は無変更）、`tests/test_bl093_think_tool_scratchpad.py`（テスト名・期待値更新）。フルオフラインスイートの唯一の失敗が解消。 |
| 関連 BL | [BL-155](back_log/issue_backlog.md#bl-155-max_tool_iterの2030変更未コミット差分にbldを事後付与)、[BL-154](back_log/issue_backlog.md#bl-154-decision_extractorのdirectivedeferred自動抽出をissue_logへも橋渡しする) |

### D-126: `_query_AI_live`のAPIエラーリトライ時print文言を、BL-122導入後の実際の挙動（このiteration単位のみやり直し）に合わせて修正する（BL-156）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-03 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ドライラン中のログを見て「APIエラー時には直前の思考は温存されるんでしたっけ？」と質問、「さくっと直してください」で承認） |
| **決定理由** | 調査の結果、`loop_messages`/`reasoning_parts_all`/`iteration_start`はBL-122によりリトライを跨いで温存され、失われるのはエラー発生時点のiteration自体の途中経過のみと判明した。一方、リトライ時のprint文言「ツールループを最初からやり直します」はBL-122以前（当時は実際にiter=1へ巻き戻っていた）の挙動を説明する隣接コメントがそのまま残っており、現在の実装と食い違っていた。表示文言のみのズレでロジックへの影響はないため、コメント同様に簡潔な修正で足りると判断した。 |
| 決定内容 | print文言を「このiterationのAPI呼び出しをやり直します」へ修正。隣接するBL-046由来コメントへBL-122以降は巻き戻らない旨を追記。 |
| 影響 | `cela_main.py`（`_query_AI_live`のprint文言・コメントのみ）。ロジック変更なし、対応テストなし。 |
| 関連 BL | [BL-156](back_log/issue_backlog.md#bl-156-_query_ai_liveのapiエラーリトライ時のprint文言がbl-122以前のiter1へ巻き戻る挙動のまま実装と食い違っていた)、[BL-122](back_log/issue_backlog.md#bl-122-apiエラー時のツールループ全体巻き戻しリトライbl-009bl-046がモデル変更nemotron後に発生頻度が明らかに増加し実害が拡大している) |

### D-127: D-079/D-080の「occurrence_count>=2で機械的にmajor/escalated」不変条件に、raised_by='detector_auto'の例外を追加する（BL-157）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「2233のログをレビュー、task_idの遷移が上手くいっていないようです」「プロンプトありログも読んで状況を追加で確認して」の指示、続くAskUserQuestionで「両方まとめて設計する（推奨）」を選択して承認）、Claude Sonnet 5（調査・設計・実装、Plan agent1体を併用） |
| **決定理由** | BL-134調査時点（issue_backlog.md記載）では`detector_auto`起票行がoccurrence_countにより昇格すること自体は「同じtopicが繰り返し検出される＝未解決のまま何度も見つかっている」というD-079/D-080の意図通りと判断されていた。しかし`log/2026-08-03/2233`で、`current_task_id`が実際の会話の主題（task_1_2）より遅れているタイミングで`detector_node`のBL-096バックアップが`detector_observation_task_1_1`という粗い集約キーに書き込んだ結果、task_1_1についての懸念とtask_1_2についての無関係な懸念が同一行にマージされ、「同じ懸念の再発」ではなく単なるバケツキー衝突がmajor/escalated昇格の引き金になった実例を確認した。BL-134調査時にはこの「バケツキー衝突による偽の再発」という区別が具体的に発見されておらず、素朴な`occurrence_count`のみの判定は`detector_auto`の粗い集約設計（BL-096自身のdocstring「モデルの判断を上書きするものではなく...保険に留める」）とは整合しないと判断した。 |
| 決定内容 | `_bump_issue_occurrence`（およびその昇格を複製している`_read_issues_handler`のミラーロジック）に`row["raised_by"] != "detector_auto"`の条件を追加し、`detector_auto`起票行は`occurrence_count`に関わらず常に`severity='minor'/status='open'`のままとする。他ロール（`detector`/`user`/`decision_extractor_auto`）の既存挙動は無変更。真に再発する懸念を確実に追跡したい場合は、明示的な`write_issue`呼び出しで固有のtopicを選ぶことを引き続き前提とする（BL-096/BL-136が元々catch-allをフォールバック位置づけとしていたことと整合）。あわせてユーザー指示「今後このようなコード側の機械的・暗黙的動作のブラックボックスを可視化するために、すべての動作にprintによるでバックログを追加してください」を受け、再発カウント・昇格・抑制の各分岐へprintログを追加した。 |
| 影響 | `cela_main.py`（`_bump_issue_occurrence`、`_read_issues_handler`）。新規テスト`tests/test_bl157_detector_auto_occurrence_exemption.py`（5件）追加。既存`tests/test_bl096_issue_log.py`等5ファイルは無修正でPass（`detector_auto`をoccurrence経由で昇格させる既存テストが存在しないことを確認済み）。`python -m py_compile`合格、フルオフラインスイート643件Pass。BL-144/BL-145の滞留検知・タスク明示化機構は`detector_auto`起票行に対しては到達不能になるが、これはBL-145が回避しようとしていた根本原因を本修正が解消した結果であり、他ロール起票行には引き続き有効。 |
| 関連 BL | [BL-157](back_log/issue_backlog.md#bl-157-bl-096の自動バックアップdetector_autoがcurrent_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ見せかけの再発でmajorescalated化していた)、[BL-158](back_log/issue_backlog.md#bl-158-detectorの-user-レビューパスに未解決issueを残したままの前進を機械的に却下する仕組みを追加)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、[BL-134](back_log/issue_backlog.md#bl-134-expertがゴール文にない24時間365日監視前提を無根拠に確定値化しdetectorがmajorエスカレーションしたのに未解決のままtask進行を許してしまった) |

### D-128: Detectorの User レビューパスへ、未解決issueを残したままの前進を機械的に却下する決定論的ゲートを追加する（BL-158）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「根本的にはユーザーがタスクを次に進めてはいけませんし、detectorが弾くべきです」という原則提示、続くAskUserQuestionで「両方まとめて設計する（推奨）」を選択して承認） |
| **決定理由** | `generate_user_utterance`は既に`_get_forced_escalated_issues_text`（BL-136）で「今回の発言でRESOLVE/DEFERを必ず呼べ」とUser AIへソフトに指示しているが、実ドライラン`log/2026-08-03/2233`でUser AIがこれを無視して直接「次タスクへ進め」と発言し、`call_detector`（target_role="user"）も判定基準に「現在のタスクに未解決のescalated issueが残ったまま前進しようとしていないか」のチェックが一切なく`constraint_issue="none"`のまま通過させてしまう実例を確認した。ソフトなプロンプト指示は既に無視される実績がある（BL-136自身の導入経緯でも「0/7件しか解決されなかった」と記録済み）ため、LLMの指示追従に頼らない決定論的なPython側の機械的却下が必要と判断した。 |
| 決定内容 | BL-125の実ゲートと完全に同一の`_get_blocking_issues_for_transition`を単一の判断源として再利用し、`detector_node`（target_role=="user"のみ、BL-033ブロック直後）へ機械的却下ロジックを追加。ブロック対象issueが存在し、かつ今回のターンで`write_issue(RESOLVE/DEFER)`が成功していない場合、`call_detector`のLLM判定に関わらず`constraint_issue`を`"major"`へ上書きする。判定には新規フラグ`user_wrote_issue_resolution`（`_LAST_WRITE_AGREEMENT_SUCCEEDED`と同型の新規グローバル`_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED`＋アクセサ＋`LineageState`フィールド）を新設し使用する。この却下は「前進しようとしている発言」に限定せず、ブロック対象issueが残っている限り毎ターン発火する（BL-136の既存の強制文言も同様に無条件のため整合。`route_after_user_detector`の3回リトライ上限があるため無限ループにはならない）。 |
| 影響 | `cela_main.py`（`_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED`関連一式、`detector_node`、`LineageState`、`generate_user_utterance_node`）。新規テスト`tests/test_bl158_detector_rejects_premature_advancement.py`（7件）追加。`python -m py_compile`合格、フルオフラインスイート643件Pass、BL-096/136/144/145/154関連98件も無退行。留意点：フラグは「今回RESOLVE/DEFERのどれかが成功したか」という粗い真偽値であり、「ブロック中の複数issueのうちどれを解決したか」までは区別しない（最初の実装はこの粒度、必要なら後続で絞り込む）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-158](back_log/issue_backlog.md#bl-158-detectorの-user-レビューパスに未解決issueを残したままの前進を機械的に却下する仕組みを追加)、[BL-157](back_log/issue_backlog.md#bl-157-bl-096の自動バックアップdetector_autoがcurrent_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ見せかけの再発でmajorescalated化していた)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](back_log/issue_backlog.md#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性) |

### D-129: cela_main.py全体（約50箇所）のサイレントな機械的・暗黙的動作へprintによる可視化を一括追加する（BL-159）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「今後このようなコード側の機械的・暗黙的動作のブラックボックスを可視化するために、すべての動作にprintによるでバックログを追加してください」に続き「機械的・暗黙的動作の可視化はコード内のすべての個所について実施してください。全体のデバッグ性を高めます」と全体適用を明示指示、AskUserQuestionで調査順序・優先度範囲・実装単位の3点を確認して承認） |
| **決定理由** | BL-157/158の調査で、DB内部で静かにoccurrence_countが上がってescalated化する、Detectorの判定が機械的に上書きされる、といった挙動が一切printされておらず、その分ドライランのログから根本原因を突き止める調査に時間を要した。これはBL-157/158に限った局所的な問題ではなく、cela_main.py全体に共通する設計上の欠落（重要な決定が下される箇所ほどコンソールに何も出ない）と判断し、ユーザーの明示指示に基づき全体へ適用する。 |
| 決定内容 | Explore agent 2体でcela_main.py全体（約9300行）を2パスで完全走査し、約50箇所を12段階のTierに分類（halt/不変条件強制、goal/agreement変異、権限拒否、issueライフサイクル、plan注釈のfire-and-forget、LLM JSONパース失敗フォールバック、verified_facts上書き、ルーティング異常、モード切替、LLM向けone-shot通知、コスメティックなフォールバック、ストリーミング内部/スキーマ移行）。AskUserQuestionで(a)未調査範囲も含め先に全体調査完了、(b)Tier 1〜11すべて対応（低優先度分も含む）、(c)Tierごとに順次py_compileして進める、の3点を確認の上、Tierごとにprintを追加しながら`python -m py_compile`・要所でフルオフラインスイートを実行して回帰がないことを確認した。 |
| 影響 | `cela_main.py`（約50箇所、Tier 1〜12）。調査の副産物として`run_ai_vs_ai_loop`内の実バグ（決定表示の`else`節がトリプルクォート文字列リテラルのまま`print()`に渡されておらず、orchestrator/decision_extractor以外の全ロールの決定がコンソールに一切出力されていなかった死にコード）を発見し、実際の`print(...)`呼び出しへ修正した（唯一の動作変更）。他は全て既存動作を変えない純粋な可視化追加。テスト変更なし、`python -m py_compile`合格、フルオフラインスイート643件Pass（Tierごとに複数回確認）。 |
| 関連 BL | [BL-159](back_log/issue_backlog.md#bl-159-cela_mainpy全体約50箇所のサイレントな機械的暗黙的動作へprintによる可視化を追加)、[BL-157](back_log/issue_backlog.md#bl-157-bl-096の自動バックアップdetector_autoがcurrent_task_idキーの陳腐化により無関係な指摘を同一バケツへ混入させ見せかけの再発でmajorescalated化していた)、[BL-158](back_log/issue_backlog.md#bl-158-detectorの-user-レビューパスに未解決issueを残したままの前進を機械的に却下する仕組みを追加) |

---

### D-130: `_query_AI_live`の非ツール分岐・ツール呼び出しループ双方に、contentが空・reasoningが非空の場合のフォールバックを追加し、`call_decision_extractor`にも層2リトライを追加する（BL-160）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ログレビュー指示「08-04/0715,0807のログをレビュー」を受けAIが根本原因を特定・報告し起票、続けて「BL起票後、修正プランをお願いします」の指示でPlan Modeによる設計・実装を承認） |
| **決定理由** | `log/2026-08-04/0807`で`current_task_id`が実行全体を通して固着する実害が発生し、原因を追ったところ、`_query_AI_live`のtools=None分岐（`call_decision_extractor`が経由）が、モデルが完成した最終JSONを丸ごとreasoningチャンネル（`delta.reasoning`）へ出力しcontentチャンネルが空のまま応答を終えたケースを「空応答」として扱い、reasoning側に既に出ている正しい答えを一切参照せずに`"(APIから空の応答が返されました)"`を返していたことが判明した。ユーザーからの補足で、当該ドライランはモデルをリリース直後の`deepseek-v4-flash-0731`に切り替えて実行しておりモデル自体の不安定性が引き金である可能性が示されたが、「reasoning側に完成した答えが出てもプログラム側が拾わず握りつぶす」という設計上の穴自体はモデル非依存のコード側欠陥であり、修正が必要と判断した。 |
| 決定内容 | (1) tools=None分岐（`cela_main.py:3076-3114`）・(2) ツール呼び出しループの最終応答（`cela_main.py:3236-3246`、Expert/User AI/Detector等ツールを持つ全ノードが通る同型の欠陥箇所）の両方に、content空・reasoning非空の場合のみreasoning全文（(2)は既存の`_reasoning_start_idx`で最終iterationのみに絞る）を代替contentとして使うフォールバックを追加。(3) `call_decision_extractor`（従来リトライなしの単発呼び出し）を既存の`_query_and_parse_with_retry`でラップし、他のJSON判定ノードと同水準の層2リトライ保護を持たせた。`_safe_json_parse`自体は無変更（既にプロース混在JSONに頑健な設計だったため）。 |
| 影響 | `cela_main.py`（`_query_AI_live`2箇所、`call_decision_extractor`1箇所）。新規テスト`tests/test_bl160_reasoning_channel_content_fallback.py`（8件）追加。`python -m py_compile`合格、フルオフラインスイート651件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-160](back_log/issue_backlog.md#bl-160-_query_ai_liveが最終回答がreasoningチャンネルへ出力されcontentが空になったケースを空応答としてサイレントに握りつぶし1ターン分のdecisiondirectivedeliverable抽出タスク遷移シグナルが丸ごと失われる)、[BL-159](back_log/issue_backlog.md#bl-159-cela_mainpy全体約50箇所のサイレントな機械的暗黙的動作へprintによる可視化を追加) |

---

### D-131: `write_agreement`の`phase_id`に、`task_id`と同型の現在フェーズへのフォールバックを追加する（BL-161）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ログレビュー指示「1018のログをレビュー、エキスパートがホワイトボードのeditに苦戦しています」を受けAIが根本原因を特定・報告、続けて「分かりました。まず修正し、後にドキュメント整備してください」の指示で即実装を承認） |
| **決定理由** | `log/2026-08-04/1018`で、Expertの`write_agreement`(UPDATE, edits)呼び出しが11回連続で「old_textが見つかりません」失敗となり、MAX_TOOL_ITERの約半分を空費する実害が発生した。原因は`_commit_agreement_from_tool`の`phase_id = args.get("phase_id", "")`にフォールバックが一切なく、Expertがphase_idを省略すると`_find_active_deliverable_agreement`が既存Deliverableを発見できず`old_content=""`のまま`_apply_text_edits`が必ず0件一致で失敗する構造だったため。`task_id`には既にBL-146由来の同型フォールバック（`_effective_current_task_id_from`/`_task_id_from`）があり、`phase_id`用の`_phase_id_from(state)`も既に定義済みだったが、`write_agreement`のTOOL_DISPATCH配線がそれを呼んでいなかっただけの配線漏れであり、修正箇所・リスクともに小さいと判断し、ユーザー指示通りPlan Modeを経ずに直接実装した。 |
| 決定内容 | `_commit_agreement_from_tool`・`_write_agreement_impl`双方へ`phase_id: str = ""`引数を追加し、`phase_id = args.get("phase_id") or phase_id`（`tid`と同じパターン）へ変更。フォールバック発動時にprint通知を追加（BL-159の可視化方針を踏襲）。TOOL_DISPATCH配線（`write_agreement`）へ`phase_id=_phase_id_from(state)`を追加。CREATE/UPDATE/SUPERSEDEいずれも同一の`phase_id`変数を共有するため1箇所の修正で全action_typeに一律適用される。 |
| 影響 | `cela_main.py`（`_commit_agreement_from_tool`・`_write_agreement_impl`・TOOL_DISPATCH配線の3箇所）。新規テスト`tests/test_bl161_write_agreement_phase_id_fallback.py`（4件）追加。`python -m py_compile`合格、関連既存テスト（BL-084/131/146/151）30件無退行、フルオフラインスイート655件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-161](back_log/issue_backlog.md#bl-161-write_agreementのphase_idにフォールバックが一切なくexpertが省略するとeditsホワイトボード差分更新が必ず0件一致で失敗し続ける)、[BL-146](back_log/issue_backlog.md#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた) |

---

### D-132: `revise_goal`の`old_goal_text`をstateへ橋渡しし、Detectorのgoal_change監査プロンプトへ直接埋め込む（BL-162）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ログレビュー指示「ログレビューを続行、ゴールが書き換えられましたが、次のdetectorがちょっと困っています」を受けAIが根本原因を特定・報告、続けて「修正してください」の指示で即実装を承認） |
| **決定理由** | `log/2026-08-04/1123`で、ゴール改定（`revise_goal`、BL-086）直後の`review_mode="goal_change"`監査（BL-126 Stage B）において、Detectorが判定基準1「旧文が置換ではなく追記として保持されているか」を確認しようと`read_verified_fact`/`read_deliverable_file`を計5回試すも全て`not_found`となり、「旧ゴール文が不明のため包含関係は確認不可」と自ら申告する空振りが発生した。原因は`generate_user_utterance_node`が`_LAST_GOAL_REVISION`ブリッジから`new_goal_text`のみを`state["goal"]`へ反映し`old_goal_text`を捨てていたためで、Detectorの持つツールはいずれも「現在の」状態しか読めず旧ゴール文の取得経路が原理的に存在しなかった。BL-160/BL-161と同型の「橋渡し変数の配線漏れ」であり、修正箇所・リスクともに小さいと判断し、ユーザー指示通りPlan Modeを経ずに直接実装した。 |
| 決定内容 | `LineageState`へ`goal_revision_old_text: str`を追加。`generate_user_utterance_node`が`_goal_revision.get("old_goal_text") or ""`を`state["goal_revision_old_text"]`へ橋渡し。`call_detector`のgoal_change用`domain_role_instruction`へ、旧文（`state.get("goal_revision_old_text", "")`）と新文（既存の`goal`変数）を直接埋め込み、Detectorがツール呼び出しなしに比較できるようにした。 |
| 影響 | `cela_main.py`（`LineageState`定義・`generate_user_utterance_node`・`call_detector`の3箇所）。新規テスト`tests/test_bl162_goal_revision_old_text_bridge.py`（4件）追加。`python -m py_compile`合格、既存`tests/test_bl126_stage_b_goal_change_review_mode.py`（6件）無退行、フルオフラインスイート659件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-162](back_log/issue_backlog.md#bl-162-ゴール改定revise_goal直後のdetector-goal_change監査が旧ゴール文を取得する手段を持たず判定基準の1つを実質評価できない)、[BL-160](back_log/issue_backlog.md#bl-160-_query_ai_liveが最終回答がreasoningチャンネルへ出力されcontentが空になったケースを空応答としてサイレントに握りつぶし1ターン分のdecisiondirectivedeliverable抽出タスク遷移シグナルが丸ごと失われる)、[BL-161](back_log/issue_backlog.md#bl-161-write_agreementのphase_idにフォールバックが一切なくexpertが省略するとeditsホワイトボード差分更新が必ず0件一致で失敗し続ける) |

---

### D-133: `revise_goal`成功時、承認済みの過去タスクへ「新ゴールとの整合性要再確認」issueを機械的に起票する（BL-163）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-162の調査を受けた設計相談「ゴール承認後にタスクを1_1からやり直させた方が良いか」に対し、AIが全面リスタート／完全受け身双方の欠点を説明した上で折衷案（機械的issue起票）を提案し、ユーザーが「これでいきましょう。注記が最初に出てくれば、AIの混乱も少ないはずです」と採用。AskUserQuestionでissue重大度（minor/open採用）・実現範囲（既存の起票の仕組みに乗せるだけ採用）の2点を確認） |
| **決定理由** | ゴール改定（`revise_goal`、BL-086）後、それ以前に承認済みだった過去タスクの成果物は旧ゴールの前提のまま放置される。全面リスタートは、矛盾していたのは特定の前提・数値だけであるにもかかわらずコストが大きく、CELAの既存アーキテクチャ（SUPERSEDE改訂、BL-096 issue管理、BL-144滞留検知、BL-145タスク明示化）が「前進しながら必要な箇所だけ修正する」設計思想であることとも不整合。一方、後続タスクが偶然気づくことへ期待する完全受け身な設計は見落としリスクがある。折衷案として、ゴール改定成功時に承認済み過去タスクへ機械的に整合性再確認issueを起票し、既存の解決フロー（RESOLVE/DEFER、BL-144滞留検知）に確実に乗せることとした。 |
| 決定内容 | `ALLOWED_ISSUE_ACTIONS_BY_ROLE`へ新規ロール`"revise_goal_auto": {"CREATE"}`を追加。`_revise_goal_tool_impl`の成功パス末尾で、`get_agreements_from_db`を`_find_active_deliverable_agreement`（BL-084）と同型のdedupロジックで走査し、最新statusが`RESOLVING_DELIVERABLE_STATUSES`（Approved/Approved_with_Conditions/Implicitly_Accepted）に含まれる全`(phase_id, task_id)`へ、topic=`goal_revision_consistency_check_<phase_id>_<task_id>`・severity="minor"のissueを`_write_issue_impl`で直接起票する。既存のpin builder（`_build_open_issue_pin_text`等）は無変更で、severity="minor"のため既存のUser AI向けopen issue一覧へ自然に乗り、BL-136の強制RESOLVE/DEFER文言・BL-125/158のタスク遷移ブロック（いずれもmajor/escalated対象）は発動しない。タスク限定サーフェシング（そのtask_idに触れた瞬間だけ注入する新規機構）は既存CELAに前例がなく大規模になるため、今回は既存の起票の仕組みに乗せるだけに留めた（将来必要になれば別BL）。 |
| 影響 | `cela_main.py`（`ALLOWED_ISSUE_ACTIONS_BY_ROLE`・`_revise_goal_tool_impl`の2箇所）。新規テスト`tests/test_bl163_revise_goal_auto_flags_past_tasks.py`（6件）追加。`python -m py_compile`合格、既存BL-086/096/136/144/154関連101件無退行、フルオフラインスイート665件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-163](back_log/issue_backlog.md#bl-163-revise_goal成功時既に承認済みの過去タスクへ新ゴールとの整合性要再確認issueを機械的に起票する)、[BL-162](back_log/issue_backlog.md#bl-162-ゴール改定revise_goal直後のdetector-goal_change監査が旧ゴール文を取得する手段を持たず判定基準の1つを実質評価できない)、[BL-086](back_log/issue_backlog.md#bl-086-前提エスカレーション経路-freeze復活-ゴール改定goalshifteventの実消費化) |

---

### D-134: Detectorの「Recent Decisions（参考程度）」節を、生reasoning（`internal_thought_process`）込みの生データから`who`/`what`/`why`のみのキュレーション済み要約へ変更し、出所限定の注意書きを追加する（BL-164）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（ログレビュー継続で発見したBL-164の修正案をAIが提示、ユーザーから「internal_thought_process除去で監査能力の粒度が落ちないか」「ゼロベースで見せるべき情報構造を設計するなら」の2点質問を受けPlan Modeで討議、承認） |
| **決定理由** | `log/2026-08-04/1123`のtask_1_3監査で、`Detector`が`verify_whiteboard_excerpt`を29回中11回失敗させ続けMAX_TOOL_ITER=30へ2回到達する実害を確認。原因は`recent_decitions`（直近2件のdecisions行）が`SELECT *`の生データ（`internal_thought_process`列込み）をそのままプロンプトへ埋め込んでおり、既にsupersede済みのホワイトボード版への一字一句引用が`internal_thought_process`内に残ったまま次のDetectorへ渡り、最新内容と誤認されたため。ユーザーの質問に対しては、`thought_process_audit`（今回ターンのExpert/User AI自身の思考過程を専用に監査する既存ブロック）が「思考ログ監査」の本来の役割を既に担っており、`recent_decitions`側の`internal_thought_process`は用途外の重複混入であることを確認。`call_detector`の全体構成を4層に整理した結果、修正が必要なのは「継続性・参考情報」層（`recent_decitions`）のみで、ゼロベースでの大規模な情報構造再設計は不要と判断した。 |
| 決定内容 | `recent_decitions`（`cela_main.py:5812`）を`who`/`what`/`why`のみのキュレーション済み要約へ変更（`internal_thought_process`等の生列を除外）。「Recent Decisions（参考程度）」節の直前（`cela_main.py:6204`）へ、target_excerpt/verify_whiteboard_excerptの根拠にはR4節（現在タスクの最新ホワイトボード）の内容のみを使用するよう明示する注意書きを追加。既存のBL-079指示を、引用の出所を限定する形で補強。ブロックの並び順（BL-104のキャッシュ効率化原則）は無変更。 |
| 影響 | `cela_main.py`（`call_detector`関数内の2箇所）。`recent_decitions`は同関数内でのみ定義・使用されるが、`call_detector`はDetector（Domain Review・数値監査の両パス）全ての共通経路のため全監査呼び出しに影響する変更。新規テスト`tests/test_bl164_recent_decisions_no_raw_reasoning_leak.py`（4件）追加。`python -m py_compile`合格、既存Detector関連テスト（BL-079/091/093/104/126/162）102件無退行、フルオフラインスイート669件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-164](back_log/issue_backlog.md#bl-164-detectorへのrecent-decisions参考程度節が前回decisionの生reasoninginternal_thought_processを丸ごと埋め込んでおりsupersede済みホワイトボードの古い引用をdetectorが誤採用しmax_tool_iterを浪費する)、[BL-152](back_log/issue_backlog.md#bl-152-verify_whiteboard_excerptが今レビューすべき成果物ではなく常にcurrent_task_idのホワイトボードだけを見ていた)、[BL-079](back_log/issue_backlog.md#bl-079-ホワイトボード注釈の一致失敗をdetector自身にフィードバックし同一ツールループ内でリトライさせる) |

---

### D-135: `_build_agreements_context`のDeliverableアイコン判定を3分岐へ変更し、Rejectされた成果物が✅と表示されないようにする（BL-166）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「1123のログをくまなくレビューして、他にバグがないかをクロールしてほしい」との指示を受けAIが発見・報告、続けて「3件とも起票の後直ちに修正する必要がありますね」の指示で即実装を承認） |
| **決定理由** | ドライラン一時停止・再開を繰り返す過程（`log/2026-08-04/1123`→`1355`→`1435`）で、User AIがRejectされたまま一度も承認されていないtask_1_3を「Completed and approved (Ver.9)」と誤認し、未解決の労基法違反issueを残したまま次タスクへ進もうとしていた実害を確認。`cela.db`の直接クエリで該当agreements行が`status="Rejected"`のまま最新であることを確認した上でコードを追跡し、`_build_agreements_context`のDeliverable用アイコン判定`"📄" if status == "Proposed" else "✅"`が、Approved系だけでなくRejectedも無条件で✅にしてしまうことを特定した。Decision/Directive用の分岐には存在するRejected専用の保護（elseで⚠️に落とす）がDeliverable用だけ欠けていた。 |
| 決定内容 | `RESOLVING_DELIVERABLE_STATUSES`を再利用し、Deliverableのアイコン判定を`status == "Proposed"`（📄）／`status in RESOLVING_DELIVERABLE_STATUSES`（✅）／それ以外（⚠️）の3分岐へ変更。ラベルも`status == "Rejected"`の場合`"[却下成果物]"`を返すよう追加。 |
| 影響 | `cela_main.py`（`_build_agreements_context`関数内）。`_build_agreements_context`はUser AI・Expert・Detector・Orchestrator等ほぼ全ノードの決定事項DB表示に共通で使われるため、Rejectされた成果物がある全てのランに影響する変更。新規テスト`tests/test_bl166_rejected_deliverable_icon.py`（6件）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-166](back_log/issue_backlog.md#bl-166-_build_agreements_contextのアイコンラベル判定がrejectされた成果物を承認済みと表示してしまう)、[BL-062](back_log/issue_backlog.md#bl-062-detector等のmajor判定rejected書き込みが既存agreementを構造的に上書き無効化できないwrite_agreement権限モデルの監査ガバナンス欠落) |

---

### D-136: BL-145の滞留issue再構築フィルタとBL-136の強制解決プロンプトへ、defer_to_task_id受け皿タスクの完了判定を追加する（BL-167）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-166と同じクロールで「タスク再構築でissue/タスク番号の依存関係が崩壊するのでは、旧ゴールの2台という数字が残ったままissueも触られていない」との指摘を受けAIが根本原因を特定・報告、「3件とも起票の後直ちに修正する必要がありますね」の指示で即実装を承認） |
| **決定理由** | `log/2026-08-04/1435`で、Reflectionが3件のescalated issueを滞留と検出しstagnant化したにもかかわらず、Task Plannerへ実際に引き継がれたのは1件のみだったことを確認。コード追跡の結果、BL-145の`_formalizable_stale`フィルタが「`defer_to_task_id`が設定済み＝受け皿タスクが既にある」という前提で除外しており、その受け皿タスクが既に完了（Approved）しているかどうかを一切検証していなかったことが判明。受け皿タスクが完了してもissueが解決されないまま、`defer_to_task_id`が過去に一度設定された事実だけで恒久的に除外され続ける「永久迷子」状態を生んでいた。同型の欠陥がBL-136の`_get_forced_escalated_issues_text`（User AI向け毎ターン強制解決プロンプト）にも存在することも判明した。 |
| 決定内容 | 新規ヘルパー`_is_task_completed(conn, run_id, task_id)`を追加し、`_formalizable_stale`フィルタと`_get_forced_escalated_issues_text`の両方に配線。受け皿タスクが既に完了済みなのにissueが未解決の場合は「受け皿は失効した」とみなし、再度タスク化・強制解決プロンプトの対象に含める。 |
| 影響 | `cela_main.py`（新規ヘルパー1関数、既存フィルタ2箇所）。新規テスト`tests/test_bl167_defer_to_task_id_completed_target.py`（9件）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-167](back_log/issue_backlog.md#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)、[BL-145](back_log/issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する)、[BL-144](back_log/issue_backlog.md#bl-144-reflection_nodeのbl-096機械的stagnant上書きがescalated-issueの単なる存在で無条件発火しreflection自身が健全な進捗と判定した回まで停滞扱いしていた) |

---

### D-137: `revise_goal`成功時、BL-163が列挙する影響過去タスクをverified_factsのstale警告にも再利用する（BL-168）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL-167と同じクロールでAIが根本原因を特定・報告、「3件とも起票の後直ちに修正する必要がありますね」の指示で即実装を承認） |
| **決定理由** | BL-167の実害（再構築後のtask_1_1がゴール改定前の車両単価のまま出力された）を追跡した結果、`read_verified_fact`が`max_vehicle_count='2'`等、ゴール改定前にtask_1_1が確定した値を無警告で返し続けていたことが原因と判明。`upsert_verified_fact`は`(run_id, variable_name)`のUPSERT方式で、再度upsertされない限り内容の新旧を問わず永久に「現在の確定値」として供給され続け、`agreements`テーブルのような「現在性」を判定する仕組みが`verified_facts`には存在しなかった。BL-163（ゴール改定時に承認済み過去タスクへ整合性再確認issueを起票する仕組み）は`agreements`のみを対象にしており、`verified_facts`という別の永続化経路は対象外だった。 |
| 決定内容 | BL-163が既に計算している「ゴール改定によって影響を受ける過去タスクの`(phase_id, task_id)`一覧」（`_flagged`）をそのまま再利用し、`_revise_goal_tool_impl`のBL-163ブロック直後で、該当task_idを`source_task_id`に持つ`verified_facts`行の`reason`列へ「⚠️[BL-168: ゴール改定後未確認]」という警告を付記する（`value`自体は過去の事実として正しいため改変しない）。BL-163と同一箇所・同一トリガーに相乗りさせ、二重のロジックを避けた。 |
| 影響 | `cela_main.py`（`_revise_goal_tool_impl`関数内）。新規テスト`tests/test_bl168_verified_facts_stale_after_goal_revision.py`（5件）追加。`python -m py_compile`合格、既存BL-062/096/136/144/145/163関連100件無退行、フルオフラインスイート689件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-168](back_log/issue_backlog.md#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない)、[BL-163](back_log/issue_backlog.md#bl-163-revise_goal成功時既に承認済みの過去タスクへ新ゴールとの整合性要再確認issueを機械的に起票する)、[BL-167](back_log/issue_backlog.md#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける) |

### D-138: BL-168修正の遡及漏れ（修正デプロイ前に発生済みのゴール改定）は、既存run限定の特殊事情としてバックフィルせず現状のまま許容する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（対応しない） |
| 決定者 | t-momose |
| **決定理由** | `log/2026-08-04/1548`のドライランログをレビューした際、User AIへ提示されたtask_1_3のプロンプトで、task_1_1由来の`verified_facts`（`max_vehicle_count='2'`、`initial_cost_breakdown`の「車両費2500万円/台」）がBL-168の警告マーカー無しで「確定済み・再導出禁止」として表示されていることを発見。DBを直接確認しマーカーが付いていないことを確認した上で原因を特定：この実行の`revise_goal`呼び出し（車両単価2,500万→500〜1,000万への改定）は`log/2026-08-04/1123`セッションで発生済みであり、BL-168の修正コード（`_revise_goal_tool_impl`内でのみ発火）が実装される前の出来事だった。1435→1546→1548はチェックポイント再開のため`revise_goal`が再実行されず、修正が一度も通らないまま残っている。ユーザーへ「新規BLとして起票しこのrunをバックフィルすべきか、今後のrevise_goalからのみ有効という割り切りで良いか」を確認したところ、「今だけが特殊な状況なのでこのままでよい」との回答を得た。この実行は本来ならクリーンな新runで再現するはずの検証用ドライランであり、修正コードのデプロイタイミングと偶然重なった一過性の状態であるため、恒久的なバックフィル機構（DBマイグレーション等）を追加する必要性は乏しいと判断。 |
| 決定内容 | BL-168の修正は「今後の`revise_goal`呼び出し」にのみ適用される設計のまま据え置く。既存run（run_id=1785806334-3666e80a）の`verified_facts`に対する遡及的なバックフィルは行わない。将来的に同種の「修正デプロイ前に発生した状態」がクリーンな新runでも問題になる場合は、改めてBLとして起票し直す。 |
| 影響 | コード変更なし。ドキュメントのみ。 |
| 関連 BL | [BL-168](back_log/issue_backlog.md#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない) |

### D-139: `write_agreement`の権限チェックへ、role×entry_type×action_typeの制限を追加し、UserによるDeliverableの自作自演を禁止する（BL-169）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（AIが`log/2026-08-04/1548`をhaltまで追跡し根本原因を報告、「そうしましょう」の指示で実装を承認） |
| **決定理由** | `1548`ログで、task_1_3の最終リトライ中にUser AIが`write_agreement(entry_type="Deliverable", action_type="CREATE", status="Proposed", ...)`を自ら呼び出し、財務モデル成果物を丸ごと執筆・提出した上で受入基準を自己採点し次タスクへ一方的に移行する事象を発見。`_check_write_permission`（`cela_main.py:1859`）がstatusのみで判定しておりrole×entry_typeの制限が存在せず、`user`ロールが本来Expertの役目であるDeliverableの新規作成を行うことを何も止めていなかったことがコード確認で判明。今回はDetectorのドメインレビューが物理的輸送力の矛盾を`major`判定で捕捉したため実害は限定的だったが、Detectorが見逃せば「Userが自分で書いた成果物をUserが自分で承認する」自作自演がノーチェックで通り得る構造的な穴であり、Reflectionが実際に"User is approving defective deliverables (collusion)"と判定してstagnant→haltに至った一因でもあった。 |
| 決定内容 | `_check_write_permission`に、`caller_role=="user"`かつ`entry_type=="Deliverable"`かつ`action_type=="CREATE"`の組み合わせを拒否する分岐を追加する。既存Deliverableへのstatus変更（承認・却下等、UPDATE/SUPERSEDE）は従来通り許可し、Expertによる新規作成にも影響しない。 |
| 影響 | `cela_main.py`（`_check_write_permission`関数内）。新規テスト`tests/test_bl169_user_deliverable_create_forbidden.py`（9件）追加。既存`test_bl146_write_agreement_current_task_gate.py`・`test_r4_smoke.py`の一部テストが、userロールでDeliverable CREATEを行うテスト用ショートカットに依存していたため、テスト意図を変えない形で修正（前者はaction_typeをUPDATEへ、後者はexpert CREATE→user UPDATE承認の2段階へ）。`python -m py_compile`合格、既存BL-062/084/095/126/127/131/146関連80件無退行、フルオフラインスイート698件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-169](back_log/issue_backlog.md#bl-169-write_agreementの権限チェックがstatusのみを見ておりuserがexpertを介さず成果物deliverableを自作自己提出できてしまう)、[BL-166](back_log/issue_backlog.md#bl-166-_build_agreements_contextのアイコンラベル判定がrejectされた成果物を承認済みと表示してしまう)、[BL-167](back_log/issue_backlog.md#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)、[BL-168](back_log/issue_backlog.md#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない) |

### D-086: checkpoint/resume機構をLangGraph本来のcheckpointer/`@task`ベースへ移行するか（BL-105）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（Tier 1実装完了、Tier 2は将来課題として見送り） |
| 決定者 | t-momose（当初`pending`のまま放置されていたが、本日「そろそろLangGraphの正式なチェックポイントを実装したい」と要望があり再着手・決定） |
| **決定理由** | 論点自体はBL-105起票時（`pending`）から変わらず：自前JSON checkpointは`--resume`時に必ずグラフのentry_point（`goal_essence`）から全体を再走行するため、`generate_user_utterance_node`の再入場ガード欠如と相まってラウンド途中の一時停止でuser発言が二重に積まれる。`log/2026-08-04/1123→1355→1435→1546→1548`という同一runが5つの異なる`log/`ディレクトリへ跨ってCtrl+C/`--resume`を繰り返した実例を追跡する中で再燃し、ユーザーから実装着手の要望があった。着手前にユーザーへ「将来ヒューマンインザループ（HITL）実装を見据えるとTier1/Tier2どちらが良いか」を確認され、`interrupt()`ベースのHITLはTier1（`checkpointer`導入）があれば動作するが、"Do not create new records before an `interrupt` call. Re-running the node upon resume will create duplicate records"という公式ドキュメントの制約により、`interrupt()`呼び出し前に副作用（DB書き込み等）があると再開時に重複実行される。CELAの意味のある意思決定点（`write_agreement`/`revise_goal`/`escalate_premise_concern`）はほぼ全てExpert/User AI/Facilitatorのツールループ内部で発生するため、実用的なHITLゲートを後で入れるにはTier2相当の対応が最終的には必要になり得るが、**`@task`への分解粒度は具体的なゲート設計（どのツール呼び出しの前で人間に止まってほしいか）に強く依存するため、HITL要件が無い現時点で汎用的に分解すると過剰設計になるリスクが高い**と回答。ユーザーが「Tier1だけで」と回答し、候補Bを採択した。 |
| 決定内容 | 候補B（Tier 1: LangGraph本来の`checkpointer`（`SqliteSaver`）+ `thread_id`（==`run_id`）ベースの再開へ移行し、自前JSON checkpoint/`--resume <path>` CLIを置き換え）を採用する。候補C（Tier 2、`_query_AI_live`のツールループ内の各呼び出しを`@task`化しノード内部途中の再開にも対応）は、将来ヒューマンインザループ機能を具体的に設計するタイミングで、そのゲートが実際にどのツール呼び出しの前に必要かに応じて改めて着手する。 |
| 影響 | `cela_main.py`（`run_ai_vs_ai_loop`・`build_graph`・CLI引数）、`requirements.txt`（新規、`langgraph-checkpoint-sqlite`追加）、`.gitignore`（`cela_checkpoints.db*`追加）、`tests/test_checkpoint_resume.py`（全面書き換え）、`tests/tools/db_checker.py`（run_id自動検出をDB経由へ）。詳細設計は`docs/design/back_log/BL-105/BL105_basic_design.md`参照。新規テスト6件、既存関連4テストファイル計85件無退行、フルオフラインスイート700件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-105](back_log/issue_backlog.md#bl-105-checkpointresume機構がentry_pointから全体再走行するため未応答のuser発言が二重に積まれるlanggraph本来のcheckpointertask未導入という設計ギャップ) |

### D-140: Facilitatorの`escalated_issues_block`へ役割境界のガードレール文を追加する（BL-170）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-04 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（AIが`think`連発ログの意味を根本原因まで調査・報告、他11ノードへの横展開調査も経た上で「実装してください」の指示で承認） |
| **決定理由** | ユーザーから「thinkを連発している時があるが意味があるのか」との質問を受け思考ログを調査した結果、`log/2026-08-04/1435/log_no_prompt.md:784-995`でFacilitatorが`think`を29回連続呼び出し（`MAX_TOOL_ITER=30`をほぼ空費）、実際にはpython_replを一度も呼ばず「Python REPLで計算します」という同一文を反復するだけの空回りに陥っていたことを発見。プロンプトダンプ（`log_with_prompt.md`）で根本原因を特定：Facilitatorの本来の役目（短い誘導メッセージを1つ書くこと）とツール権限（`python_repl`は意図的に不付与）に対し、`escalated_issues_block`（`cela_main.py:6901-6912`）がDetectorの具体的・数値満載の却下理由を「その解消を最優先事項として明確に提示してください」という強い指示文とともにそのまま埋め込んでおり、「これはあなた自身が解決するのではなく誘導メッセージの材料に過ぎない」という役割境界の明示が無かった。モデルはiter=1のthink argsの時点で既にExpertの仕事（財務モデル全面再構築・成果物提出）を自分の仕事だと誤認しており、実行不能な計画を宣言し続けていた。ユーザー指示によりFacilitator以外の全11ノードへ同型パターンの横展開調査をgeneral-purposeエージェントで実施したが、他ノードでは注入内容とツール権限が一致しており（Expertは同種の却下文を渡されるがpython_repl/write_agreement双方を保有）、プロンプト内のツール名申告文言（11箇所）と実際の`tools=[...]`の不一致もゼロ件だった。孤立した穴と判定し、Facilitator一箇所のみを修正することとした。 |
| 決定内容 | `escalated_issues_block`へ、「これはあなたが書く誘導メッセージの材料（背景情報）であり、あなた自身が数値の再計算・成果物の作成を行う役目ではない。python_replのような検算ツールもDeliverable新規作成の権限も与えられていない」旨のガードレール文（`[BL-170]`マーカー付き）を追加する。escalated_issues_textが空の場合・`essence_dialogue_active=True`の継続対話モードはこのブロック自体を使わないため無影響。 |
| 影響 | `cela_main.py`（`call_facilitator`内`escalated_issues_block`）。新規テスト`tests/test_bl170_facilitator_escalated_issues_guardrail.py`（3件）追加。`python -m py_compile`合格、既存`test_bl061_facilitator_reflection_note.py`・`test_bl126_stage_d_essence_dialogue.py`・`test_bl096_issue_log.py`計65件無退行。フルオフラインスイート703件中702件Pass（1件は`shift_id`のミリ秒タイムスタンプ衝突による既存の低頻度flakyテストで本修正と無関係、単体実行では5件Pass）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-170](back_log/issue_backlog.md#bl-170-facilitatorのescalated_issues_blockに役割境界の明示が無くモデルがexpertの仕事数値検算成果物再提出を自分の仕事だと誤認して空回りする)、[BL-093](back_log/issue_backlog.md#bl-093-ノード内スクラッチパッド-thinkツール理由づけの退避ツールループ内の可変todoissuenotesメモ) |

### D-141: OpenRouter無料枠の日次上限エラーを検知したら、リトライせずCtrl+Cと同じ経路で即座に一時停止する（BL-171）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（`log/2026-08-04/2344`を確認し「無料枠を使い果たした時に無理やりリトライし続けて、進行が滅茶苦茶になってしまっている」「このエラーになった時に自動一次停止するようにしてくれませんか」と報告・要望） |
| **決定理由** | `log_no_prompt.md`行13808以降で、OpenRouter無料枠の日次上限エラー（`Error code: 429 - Rate limit exceeded: free-models-per-day-high-balance.`、`X-RateLimit-Reset`は翌日固定のタイムスタンプ）に対し、既存の一時的APIエラー向けリトライ機構（層1: 指数バックオフ、層2: JSON解析失敗リトライ）がそのまま適用され、数時間分にわたり同一の429が延々と繰り返されていることを確認。日次上限は待ち時間程度のリトライでは絶対に解消しないため、全リトライを使い切った末に`_query_AI_live`が返すプレースホルダ文字列がJSON解析に失敗し続け、最終的に「層2リトライを使い切ってもJSON判定を取得できませんでした。フェイルクローズ(major)します」という**実際のドメイン監査を伴わない偽のmajor判定**がDetector等から機械的に返り続けていた。これが以降のルーティング（差し戻し・reflection等）を汚染し、ドライランの進行を実質的に破壊していた。 |
| 決定内容 | 新規例外`DailyQuotaExhaustedError`を定義し、`_query_AI_live`のAPIエラーexcept節で`isinstance(e, RateLimitError) and "per-day" in str(e)`を満たす場合はリトライを一切行わず即座に送出する。`run_ai_vs_ai_loop`側で、既存の`except KeyboardInterrupt:`と並べてこの例外を捕捉し、Ctrl+Cと全く同じ一時停止経路（LangGraph checkpointerは完了済みノードまで既に自動保存済み、`--resume <run_id>`で再開）へ合流させる。他の一時的なAPIエラー（接続断・タイムアウト・"per-day"を含まないRateLimitError等）の既存リトライ経路は無変更のまま維持する。 |
| 影響 | `cela_main.py`（`DailyQuotaExhaustedError`新規定義、`_query_AI_live`のexcept節、`run_ai_vs_ai_loop`の`app.stream()`周りのtry/except）。新規テスト`tests/test_bl171_daily_quota_pause.py`（3件）追加。`python -m py_compile`合格、既存BL-072/083/143/141/160関連28件・`test_checkpoint_resume.py`無退行、フルオフラインスイート706件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-171](back_log/issue_backlog.md#bl-171-openrouter無料枠の日次上限エラーが他の一時的apiエラーと同じリトライ経路に乗り無意味なリトライと偽のフェイルクローズmajorを延々と繰り返して進行を破壊する)、[BL-009](back_log/issue_backlog.md#bl-009-r2-ツールループのリトライ粒度層1層2の粗さを許容する)、[BL-105](back_log/issue_backlog.md#bl-105-checkpointresume機構がentry_pointから全体再走行するため未応答のuser発言が二重に積まれるlanggraph本来のcheckpointertask未導入という設計ギャップ) |

### D-142: `write_agreement`の権限チェックを「entry_typeの区別」から「承認対象のDeliverable実在確認」へ一般化する（BL-172）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（`log/2026-08-04/2316`を自ら精読し「ユーザーAIが自分でタスクを始めて1_1完了を宣言してしまっていました」と根本原因を特定した上で、AIの一般化案提示に対し「埋めてください」と実装を承認） |
| **決定理由** | ユーザーの「ホワイトボードや成果物のmdが生成されない」という報告を受け調査した結果、`log/2026-08-04/2316/log_no_prompt.md:751-761`で、User AIがBL-169（entry_type="Deliverable"のCREATE拒否）でブロックされた直後、全く同じ内容のまま`entry_type`だけ`"Decision"`に変えて再送し成功していたことを確認。ホワイトボード書き出し（`apply_whiteboard_patch`）はentry_type="Deliverable"の時にしか発火しないため、この回避策ではホワイトボード.mdが一切生成されないままタスクだけがApproved扱いになっていた。BL-169は「Deliverableとして自作する」経路のみを塞いでおり、「userがExpertの仕事を代行して完了を宣言する」という根本行動自体は防げていなかったため、entry_type単位の判定では同種の回避策が今後も再発しうると判断した。 |
| 決定内容 | `_check_write_permission`に`conn`/`run_id`/`task_id`/`phase_id`を任意引数として追加し（`conn`未指定時は新チェックをスキップし完全な後方互換を維持）、「`caller_role=="user"`が`action_type=="CREATE"`かつ`status`が承認系（`RESOLVING_DELIVERABLE_STATUSES`）の場合、entry_typeを問わず、対象`task_id`にExpert作成のDeliverable（既存の`_find_active_deliverable_agreement`、BL-084）が実在するかを確認し、無ければ拒否する」という分岐へ一般化する。正当なUser承認は常に「既存Deliverableのstatus変更（UPDATE）」の形を取るため、CREATEで承認系statusのエントリを新規に持ち込む正規の使い方はentry_typeを問わず存在せず、既存の正当な利用（Expert作成後のUser承認等）は影響を受けない。 |
| 影響 | `cela_main.py`（`_check_write_permission`のシグネチャ拡張・新分岐、`_write_agreement_impl`の呼び出し箇所）。新規テスト`tests/test_bl172_user_approval_requires_existing_deliverable.py`（6件）追加。実装過程で発覚した既存2ファイル3テスト（`test_bl146_write_agreement_current_task_gate.py`・`test_r3_smoke.py`、いずれも実在しないtask_idへ承認系statusでCREATEするテスト用ショートカットに依存）を、各テストの検証意図を保ったまま修正。`python -m py_compile`合格、既存BL-084/146/161/169関連46件・`test_r3_smoke.py`51件無退行、フルオフラインスイート712件中711件Pass（1件は`goal_shift_events.shift_id`のミリ秒タイムスタンプ衝突による既知のflakyテストで本修正と無関係、BL-173として別途記録）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-172](back_log/issue_backlog.md#bl-172-bl-169のentry_typedeliverable限定ブロックをuserがentry_typedecisionへの付け替えで回避しホワイトボードmdが一切生成されなくなる)、[BL-169](back_log/issue_backlog.md#bl-169-write_agreementの権限チェックがstatusのみを見ておりuserがexpertを介さず成果物deliverableを自作自己提出できてしまう)、[BL-084](back_log/issue_backlog.md#bl-084-entry_typedeliverableのupdatesupersedeがtopic文字列ドリフトでeditsを0件0件失敗させ続けていたbl-074の未着手項目の再発) |

---

## 未決定（pending）

---

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
