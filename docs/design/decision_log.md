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

### D-143: checkpoint履歴の一覧表示・任意の過去checkpointからの再開を、LangGraph公式のtime travel機能をそのまま使ってCLIへ配線する（BL-174）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「ノードごとに自動スナップショットをとれないか、ほぼgitに近い」と提案。AIの調査結果（既存のLangGraph機能でそのまま実現可能）を受け「すばらしい、実装進めて」と承認） |
| **決定理由** | ユーザーから「タスクプランナーを毎回最初から通すのは非効率、動作が壊れた直前からやり直したい、再開時はスナップショット一覧から任意のものを選べるように」という提案があった。Context7でLangGraph公式ドキュメントを確認した結果、BL-105で導入済みの`SqliteSaver`は既にノード完了（superstep）ごとに毎回別のcheckpoint_idでスナップショットを自動保存しており、`app.get_state_history(config)`で全履歴取得、任意のcheckpoint_idを指定した`app.stream`/`app.get_state`でそこから再開（それ以前のノードは再実行されない）できる、公式のtime travel/replay機能が既に使えることが判明した。ユーザーの要望は追加のスナップショット機構を新規実装する必要がなく、CLIからこの既存機能を使うための薄い配線だけで実現できると判断した。 |
| 決定内容 | 新規関数`list_checkpoints(run_id)`と`--list-checkpoints RUN_ID`を追加し、`app.get_state_history()`の結果をgit log風（step・タイムスタンプ・完了ノード・次ノード・turn・task_id・checkpoint_id）に整形して表示する。`run_ai_vs_ai_loop`に`checkpoint_id`引数を追加し、`--resume RUN_ID --checkpoint-id CHECKPOINT_ID`で最新ではなく指定した過去checkpointから再開できるようにする。`checkpoint_id`は最初の`app.stream()`呼び出しにのみ適用し、2回目以降のターンはthread_idのみのconfigへ切り替える（固定したままだと毎ターン同じ過去の分岐点から再フォークし続け前進しないため）。 |
| 影響 | `cela_main.py`（`list_checkpoints`新規関数、`run_ai_vs_ai_loop`の`checkpoint_id`引数・resume分岐、`__main__`のCLI引数`--list-checkpoints`/`--checkpoint-id`）。新規テスト`tests/test_bl174_checkpoint_history_and_targeted_resume.py`（5件）追加。`python -m py_compile`合格、既存`test_checkpoint_resume.py`・`test_bl171_daily_quota_pause.py`計9件無退行、フルオフラインスイート717件Pass。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-174](back_log/issue_backlog.md#bl-174-checkpoint履歴の一覧表示任意の過去checkpointからの再開langgraph公式time-travelのcli配線)、[BL-105](back_log/issue_backlog.md#bl-105-checkpointresume機構がentry_pointから全体再走行するため未応答のuser発言が二重に積まれるlanggraph本来のcheckpointertask未導入という設計ギャップ) |

### D-144: ログとcheckpointの時刻表示を明示的にJST（UTC+9）へ統一し同期させる（BL-175）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「時刻ですが日本時間にGMT+9にしてほしい。また、ログにもチェックポイントと同じ時刻を表示し、同期をとりたい」と要望） |
| **決定理由** | ログ側の時刻表示（`MultiLogger`のログフォルダ名・バナー、`call_reflection`のtimeline）はOSローカルタイムゾーンに依存する`datetime.datetime.now()`/`fromtimestamp()`を使っており、checkpoint側（`list_checkpoints`のBL-174実装）が表示する`StateSnapshot.created_at`はLangGraph内部でUTC固定（実機で確認済み）だった。両者の基準が異なるため、ログとcheckpoint一覧を突き合わせても時刻が一致せず「同期」できていなかった。 |
| 決定内容 | モジュール定数`JST = datetime.timezone(datetime.timedelta(hours=9), name="JST")`を新設し、ログ側の全ての時刻表示箇所（`MultiLogger.__init__`、`call_reflection`のtimeline）に明示的に適用する。checkpoint側は保存形式（LangGraph内部のUTC）自体は変更せず、`list_checkpoints`での表示時にのみ`astimezone(JST)`で変換する。 |
| 影響 | `cela_main.py`（新規`JST`定数、`MultiLogger.__init__`、`call_reflection`のtimeline表示、`list_checkpoints`）。新規テスト`tests/test_bl175_jst_timestamps.py`（3件）追加。テスト実装中に発覚した`MultiLogger.log_dir`のテスト間分離漏れ（他テストを巻き込む副作用）も合わせて修正。`python -m py_compile`合格、フルオフラインスイート720件中719件Pass（1件はBL-173として既知のflakyテストで無関係）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-175](back_log/issue_backlog.md#bl-175-ログとcheckpointの時刻表示がバラバラosローカルタイムゾーン依存utc固定で日本時間に統一同期できていない)、[BL-174](back_log/issue_backlog.md#bl-174-checkpoint履歴の一覧表示任意の過去checkpointからの再開langgraph公式time-travelのcli配線) |

---

### D-145: `_resolve_task_transition`に、離脱先task_idの承認成立（Approved相当のDeliverable）を検証する機械的ゲートを追加する（BL-176）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「ユーザーが現タスクを承認することと次タスクの指示を明確に分けれないか。Detectorの監査をすり抜けると未承認のまま次タスクが進むことがある」と問題提起。AIが提案した機械的ゲート案を「BL176を実装後」と承認） |
| **決定理由** | コード調査の結果、承認の成立確認（`write_agreement`の即時DBコミット＋事後のDetector監査）と次タスクへの遷移判定（`_resolve_task_transition`への入力`advances_to_task_id`、`call_decision_extractor`がUser発言全文を自由文脈で読んで抽出）が完全に独立した別経路で動いており、両者の整合性を取るゲートが存在しないことを確認した。ユーザー提案の「承認と次タスク指示を別ターンに分離する」2段階ターン制は原理的に正しいが、往復増（BL-171の無料枠消費に直結）が伴う。同じ実害を、既存のBL-125（未解決issueブロック）・BL-146（task_id書き込みゲート）と同型の機械的ゲートを`_resolve_task_transition`に1つ追加するだけで、ターンを分割せずに防げると判断した。 |
| 決定内容 | `_resolve_task_transition`のBL-125チェックの直後に、「departing_task_idが空でなく、かつ`_is_task_completed`（BL-167）でなければ、advances_to_task_idが有効なtask_idを指していても遷移を拒否する」というゲートを追加する。ブロック時は新設のone-shot通知フィールド`task_transition_blocked_unapproved_task_id`（BL-125の`task_transition_blocked_issue_topics`と同型）へdeparting_task_idを記録し、`_build_task_transition_blocked_notice`が次のUser AIターンへ一度だけ理由を明示する。 |
| 影響 | `cela_main.py`（`LineageState`への新フィールド追加、`_resolve_task_transition`のゲート追加、`_build_task_transition_blocked_notice`のBL-176分岐追加）。新規テスト`tests/test_bl176_task_transition_requires_approval.py`（12件）追加。既存3ファイル5テスト（`test_bl136_issue_visibility_and_transition_gate.py`3件・`test_bl139_transition_fallback_from_directive.py`1件・`test_r3_smoke.py`1件、いずれもテスト用の遷移元task_idにApproved相当のDeliverableを用意していなかった）を、各テストの検証意図を保ったまま修正。`python -m py_compile`合格、フルオフラインスイート732件中731件Pass（1件はBL-173として既知のflakyテストで本修正と無関係）。実ドライランでの効果確認は次回待ち。 |
| 関連 BL | [BL-176](back_log/issue_backlog.md#bl-176-_resolve_task_transitionが離脱先task_idの承認成立を検証しておらずuserが1発言で承認と次タスク指示を同時に行うと状態が壊れうる)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-146](back_log/issue_backlog.md#bl-146-write_agreementがbl-125のタスク遷移ゲートcurrent_task_idを内容レベルで迂回できブロック中の他タスクへ実際にdeliverableを書き込めていた)、[BL-167](back_log/issue_backlog.md#bl-167-reflection内のstagnant-issue滞留検知がdefer_to_task_idの受け皿タスク完了後もissueを永久に見落とし続ける)、[BL-177](back_log/issue_backlog.md#bl-177-全ノードのプロンプトを複数の責務を1回のllm呼び出しに詰め込む構造からdetectorの2段監査パスと同型の段階化構造へ一般化するuser-ai部分は実装完了他ノードは未着手) |

---

### D-146: `generate_user_utterance`（User AI）を、Detectorの2段監査パスと同型の4段階パイプラインへ分解する（BL-177 User AI部分）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（BL177_basic_design.mdの設計をレビューし、Stage3/Stage4間の食い違い処理を2回の質問で修正させた上でExitPlanModeを承認。「BLL177実装をお願いします」で実装を指示） |
| **決定理由** | BL-176（`_resolve_task_transition`への機械的ゲート）は承認未成立のまま次タスクへ遷移することを事後に検知・拒否する安全網だが、発生源（Userが1回のLLM呼び出しでレビュー・issue確認・承認判断・次指示を同時に行っていること）自体は残っていた。`call_detector`が既に実践しているドメイン妥当性レビュー→数値検算の2段パス（BL-049/BL-054）と同じ設計原則をUser AI側にも適用し、「次タスク指示」ステージを「統合承認判断ステージがApproved相当と結論した場合のみ起動する」という条件で直列化すれば、LLMに「承認と次指示を同時に言う」余地自体を構造的に与えなくなり、BL-176より根本的な解決になると判断した。 |
| 決定内容 | `generate_user_utterance`の冒頭に`_is_normal_review_turn`判定を追加し、該当する場合のみStage1（レビュー、read-only）→Stage2（issue確認、write_issue/premise系ツール）→Stage3（統合承認判断、write_agreement単独所有）→Stage4（Stage3の結果で次タスク指示／現タスク修正指示／承認記録失敗の待機メッセージへ3分岐）という新設パイプラインへ分岐する。非該当（essence_dialogue/expert_pending_question/drift再送/終盤/初回ターン）の場合は既存の単発呼び出しコードを無変更のまま実行する。Stage3の自己申告（approval_status）とツール呼び出し結果（`get_last_write_agreement_succeeded()`）の食い違いは、設計レビューでの指摘（Stage4のLLMが技術的失敗を知らずに実在しない欠陥をでっち上げる恐れ）を受け、Pythonコード側で機械的に判定し、Stage4へは進まずStage3自体を最大2回まで訂正指示付きで再試行する設計とした。 |
| 影響 | `cela_main.py`（`generate_user_utterance`への早期returnブランチ追加、既存コードは無変更のまま温存）。新規テスト`tests/test_bl177_user_ai_staging.py`（16件）追加。実装過程で、`if`分岐と既存コードの両方に同名の`global`宣言があるとSyntaxErrorになるPythonの制約を発見し、重複した宣言を削除して解消した。設計時に予想していたBL-104プロンプト順序テスト群の書き直しは、既存の単発呼び出しコードを完全に温存する実装アプローチにしたことで不要だった（既存19ファイルすべて無改修で通過）。`python -m py_compile`合格、フルオフラインスイート748件Pass（無退行）。実ドライランでのAPI呼び出し回数・所要時間の実測は未実施。 |
| 関連 BL | [BL-177](back_log/issue_backlog.md#bl-177-全ノードのプロンプトを複数の責務を1回のllm呼び出しに詰め込む構造からdetectorの2段監査パスと同型の段階化構造へ一般化するuser-ai部分は実装完了他ノードは未着手)、[BL-176](back_log/issue_backlog.md#bl-176-_resolve_task_transitionが離脱先task_idの承認成立を検証しておらずuserが1発言で承認と次タスク指示を同時に行うと状態が壊れうる)、[BL-049](back_log/issue_backlog.md#bl-049-f-26検算ゲートによる注意力の偏りを是正する-数値検算とドメイン妥当性レビューの分離)、[BL-054](back_log/issue_backlog.md#bl-054-detectorの2段監査パスの実行順序をドメイン監査数値検算に変更) |

---

### D-147: `call_expert`の`system_prompt`（フル版）を`messages`3部構成へ再構成し、`light_system_prompt`（軽量版）へ厳守事項・差し戻し情報を新規追加する（BL-178）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ログ`log/2026-08-05/1049`を精読し「視座は上から下、文脈は過去から現在」の原則を提起。フル版の具体的な項目順（旧項目番号11→13→20／22→12→16→17→19→14→15→10→21→23→18）と軽量版の11項目順を提示し、実ドライラン`log/2026-08-05/1309`で実装結果を検証・訂正した） |
| **決定理由** | `messages`配列は`[system_prompt, ...chat_history]`という構造上、system_prompt内でテキストをどう並べても`chat_history`の末尾メッセージが常に物理的に最後に読まれる。実ログでDetectorの差し戻し指摘が`chat_history`の無関係な話題に埋もれてExpertに汲み取られていない実例が確認されたため、`chat_history`より後ろに新規systemメッセージ（`system_prompt_trailing`）を追加する構成へ変更する必要があると判断した。あわせて`light_system_prompt`（iter=2以降）が差し戻し情報・DB・厳守事項を一切含んでいない構造的欠落（`_query_AI_live`によるloop_messages[0]の丸ごと置換で判明）も同時に解消することとした。 |
| 決定内容 | `system_prompt`を`system_prompt_leading`（chat_historyより前）／`system_prompt_trailing`（chat_historyより後ろ、新設の末尾systemメッセージ）の2文字列へ分割し、`messages`を`[leading, ...chat_history, trailing]`の3部構成にした。フル版の並び順はユーザー指定の通り、leading側は【絶対的な行動指針】（ゴール）→プロジェクト計画目次→（stateless時hydrate_context）→「直近の会話」導入文、trailing側は決定事項DB→Detectorの気づき→申し送り→エスカレーション状況→エスカレーション再開通知→スコープ（現在のタスク）→ホワイトボード→Orchestratorの着眼点→制限時間→厳守事項→差し戻し（最後）とした。軽量版`light_system_prompt`はユーザー提示の11項目順（専門分野の名乗り→現在のタスク情報→着眼点→owns_variables不可侵→confidence=provisional→ツール一覧→各ツール使い方→python_repl必須→厳守事項［新規］→ホワイトボード→差し戻し情報［新規、条件付き］）をそのまま採用した。 |
| 影響 | `cela_main.py`の`call_expert`（`cela_main.py:5598-5993`）。新規テスト`tests/test_bl178_expert_prompt_reorder.py`（14件）追加。実装当初、AIがPlan mode設計時にフル版の並び順をユーザーの過去の明示的指示と異なる形で独自に再構成してしまい（Orchestratorの着眼点をゴールより前に配置する等）、実ドライラン（`log/2026-08-05/1309`）でユーザーに指摘・訂正された。軽量版は当初から11項目順通りに正しく実装できていた。既存の`test_bl104_project_plan_toc_and_prompt_reorder.py`（call_expert関連7件）は無改修で通過、フルオフラインスイート764件Pass・1件deselected（BL-173既知flaky）・1件fail（`test_f26_detection.py`、実LLM呼び出しを伴う既知flakyで本修正と無関係）。 |
| 関連 BL | [BL-178](back_log/issue_backlog.md#bl-178-call_expertのsystem_promptフル版light_system_prompt軽量版を視座は上から下文脈は過去から現在の順に再構成しdetectorの差し戻し情報を両方で真に最後に読ませる実装完了)、[BL-104](back_log/issue_backlog.md#bl-104-call_expertのphases_json目次化read_project_planツール新設プロンプトのキャッシュ効率改善)、[BL-177](back_log/issue_backlog.md#bl-177-全ノードのプロンプトを複数の責務を1回のllm呼び出しに詰め込む構造からdetectorの2段監査パスと同型の段階化構造へ一般化するuser-ai部分は実装完了他ノードは未着手) |

---

### D-148: BL-177 Stage3の承認記録を、Expertの成果物（Deliverable）自体へのUPDATEとして明示的に指示し、機械的検証も`_is_task_completed`併用へ強化する（BL-179）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン`log/2026-08-05/1542`→`1556`を「task切り替えに苦戦しているようです」とレビュー依頼し、AIの根本原因特定を受けて「すぐに直してください。また、同様なプロンプトの退行がないかチェックして下さい」と指示） |
| **決定理由** | Stage3が実際に呼んだ`write_agreement`（`log/2026-08-05/1542/log_no_prompt.md:2754`）は`entry_type="Decision"`の新規エントリを作成しており、Expertの元のDeliverableは`status="Proposed"`のまま一切更新されていなかった。BL-176のゲート（`_is_task_completed`）は`entry_type=="Deliverable"`の最新行のみを見るため、この状態は永久に解消されずタスク遷移が恒久的にブロックされ続ける。原因はStage3のプロンプトが「write_agreementを呼び出して確定してください」としか指示しておらず、`call_decision_extractor`やBL-172のD-142が既に確立していた「正当な承認は既存DeliverableへのUPDATE」という規約をStage3新設時に引き継いでいなかったため。単なる自己申告依存（`get_last_write_agreement_succeeded()`のみ）では「write_agreementは成功したが対象が違う」ケースを検知できないため、機械的検証もBL-176のゲートと同一基準（`_is_task_completed`）へ強化する必要があると判断した。 |
| 決定内容 | Stage3のプロンプト（`cela_main.py:7429-7476`）へ`_find_active_deliverable_agreement`（BL-084）で取得したExpertの成果物のtopicを注入し、「`action_type="UPDATE"`, `entry_type="Deliverable"`, `target_topic="<取得したtopic>"`で成果物自体を更新すること、新しいDecisionエントリを作成してはいけないこと」を明記した。Stage3の食い違い判定ループも`get_last_write_agreement_succeeded() and _is_task_completed(...)`へ強化し、write_agreementの成否だけでなく対象が正しくDeliverableだったかまで機械的に検証する。他ステージ（Stage1・2・4）を監査したが、Stage2は`escalation_id`/issue `topic`が既に明示提示済みで同種の問題は無く、Stage1・4は書き込みツールを持たないため対象外と確認した。 |
| 影響 | `cela_main.py`の`generate_user_utterance`（Stage3、`cela_main.py:7429-7476`）。新規テスト4件（`tests/test_bl177_user_ai_staging.py`）追加、既存2件をDB裏付け（Approved Deliverable行の事前INSERT）で堅牢化。`python -m py_compile`合格、`test_bl177_user_ai_staging.py`・`test_bl176_task_transition_requires_approval.py`計31件Pass（無退行）。実ドライランでの効果確認（タスク遷移が正常に進むか）は次回以降。 |
| 関連 BL | [BL-179](back_log/issue_backlog.md#bl-179-bl-177-stage3の承認記録がexpertの成果物deliverable自体を更新せず別のdecisionエントリを作成してしまいbl-176のゲートを永久に満たせない)、[BL-177](back_log/issue_backlog.md#bl-177-全ノードのプロンプトを複数の責務を1回のllm呼び出しに詰め込む構造からdetectorの2段監査パスと同型の段階化構造へ一般化するuser-ai部分は実装完了他ノードは未着手)、[BL-176](back_log/issue_backlog.md#bl-176-_resolve_task_transitionが離脱先task_idの承認成立を検証しておらずuserが1発言で承認と次タスク指示を同時に行うと状態が壊れうる)、[BL-172](back_log/issue_backlog.md#bl-172-bl-169のentry_typedeliverable限定ブロックをuserがentry_typedecisionへの付け替えで回避しホワイトボードmdが一切生成されなくなる) |

---

### D-149: `write_agreement`のDeliverable全文置換パスを、caller_role="expert"のみに限定する（BL-180）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン`log/2026-08-05/1639`を「task_1_2_V2が中途半端な文章です」とレビュー依頼。AIの根本原因報告を受け「1.2をで修正 また今回壊れたtask_1_2のV2（DB上のwhiteboard latest）をV1内容ベースで復旧もお願い」と、提示した2案（プロンプト修正／コード側修正）の両方の実施とデータ復旧を指示） |
| **決定理由** | BL-179で追加したStage3プロンプトの文言「decision_whatは短い承認コメントで構いません（保護されるため書き写し不要）」が200字という境界に触れておらず、User AIが200字を超える詳細な承認理由を書いた結果、BL-127の「200字以下なら保護」判定に外れて全文置換の抜け道（`len(raw_content) > 200`のみで判定）に入り、Expert作成の完全なホワイトボード本文が短い承認コメントへ丸ごと上書きされる実害（`log/2026-08-05/1639`のtask_1_2、Ver.1の74行がVer.2で3行へ全置換）が発生した。文字数だけでは「承認コメント」と「意図的な全文置換」を区別できないことが根本原因であり、BL-169により`entry_type="Deliverable"`の内容執筆はexpertロールのみに許可されている（user/detector等は承認・却下しかできない）という既存の権限モデルこそが、より本質的で確実な判定軸であると判断した。プロンプト側の指示（文字数を守らせる）だけに頼ると、将来別のLLM呼び出しパターンでも同種の事故が再発しうるため、コード側で構造的に不可能にする方を根本対策として優先した。 |
| 決定内容 | `_commit_agreement_from_tool`のUPDATE分岐（`cela_main.py:2102-2132`）で、200字超の全文置換パスへ入る条件を`len(raw_content) > 200`単独から`len(raw_content) > 200 and (caller_role == "expert" or not is_whiteboard)`へ変更。既にホワイトボード化済みの完全版（`is_whiteboard=True`）に対しexpert以外がedits未指定でUPDATEする場合は、文字数によらず常に保護する。あわせてStage3プロンプトの案内文言も「成果物本文自体を変更・追記したい場合はeditsパラメータを使ってください」という明確な行動指示へ書き換えた。破壊されたtask_1_2のVer.2はappend-only原則に従い削除せず、Ver.1本文＋承認記録を追記したVer.3を新規INSERTして復旧した。 |
| 影響 | `cela_main.py`の`_commit_agreement_from_tool`（`cela_main.py:2102-2132`）・Stage3プロンプト（`cela_main.py:7461-7470`）。新規テスト`tests/test_bl180_deliverable_protect_non_expert_full_replace.py`3件追加。既存BL-127の`test_commit_update_with_long_raw_content_returns_no_warning`（caller_role="expert"での全文置換）は無改修で通過（非退行確認）。`python -m py_compile`合格、既存BL-127/169/172/176/177/178関連69件と合わせて無退行確認。データ復旧はrun_id=1785911225-bcfa11e6のプロセス終了済みを確認した上で実施（書き込み競合なし）。 |
| 関連 BL | [BL-180](back_log/issue_backlog.md#bl-180-bl-179のstage3プロンプトが200字境界に触れずuser承認コメントがbl-127の全文置換の抜け道に入りexpert作成のホワイトボードを破壊する)、[BL-179](back_log/issue_backlog.md#bl-179-bl-177-stage3の承認記録がexpertの成果物deliverable自体を更新せず別のdecisionエントリを作成してしまいbl-176のゲートを永久に満たせない)、[BL-127](back_log/issue_backlog.md#bl-127-write_agreementのupdateがdb上は成功してもホワイトボード本体には反映されないまたは反映確認に失敗するケースが実際に発生した)、[BL-169](back_log/issue_backlog.md#bl-169-write_agreementの権限チェックがstatusのみを見ておりuserがexpertを介さず成果物deliverableを自作自己提出できてしまう) |

---

### D-150: BL-125のタスク遷移ブロックを、user_detector（意味的）とroute_after_user_decision（機械的）の2段で防御する（BL-181）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-05 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン`log/2026-08-05/1833`をレビューし、task_4_2の成果物がtask_id='task_4_1'として誤登録されている実害を発見・報告。AIが最初「Orchestrator側でブロックを塞ぐべき」と提案したところ、ユーザーが実際のグラフ順序（generate_user_utterance→user_detector→user_decision_extractor→orchestrator）を踏まえ「user_detectorは正にユーザーの宿題残しを止める役目のはず」「user_decision_extractorは最後の機械的な砦としてPython側のみで差し戻すのがよい」と2段構成を提案し決定） |
| **決定理由** | BL-125（`_resolve_task_transition`）は未解決の重大issueが残る場合に`current_task_id`の更新を正しくブロックしていたが、この事実はOrchestrator/Expertに一切伝わっておらず（`_build_task_transition_blocked_notice`は`generate_user_utterance`にしか注入されない）、両者は直近の会話文脈だけを頼りに次タスクの作業を開始してしまっていた。ExpertがBL-146のtask_id不一致ゲートに拒否されても正しく停止せず、task_idを付け替えて再送信する回避策を取ったため、task_4_2の成果物がtask_id='task_4_1'として誤登録され、task_4_1の本当の成果物を読めなくするデータ破損が発生した（`log/2026-08-05/1833`）。AIが最初に提案したOrchestrator側での対処は実装コストがやや高く、既存の`route_after_user_detector`（Userの誤りをUserにやり直させる既存パターン）を活用する方が自然であるとユーザーが指摘。ただしDetectorのLLM判断だけに頼ると見落としのリスクが残るため、BL-125が既に機械的に確定させている`task_transition_blocked_unapproved_task_id`をPython側のみで最終防衛線として使う方が、LLMの二重判断・二重抽出による混乱を避けられると判断した。 |
| 決定内容 | 第1段（意味的）：`call_detector`のtarget_role="user"向け`role_specific_instruction`へ、次タスクへの移行時に現在タスクのmajor/escalated issueが今回の発言内でRESOLVE/DEFERされているかを`read_issues`で確認し、未対応ならmajorとして差し戻す指示を追加。既存の`route_after_user_detector`をそのまま再利用する。第2段（機械的）：`route_after_user_decision`へ`state.get("task_transition_blocked_unapproved_task_id")`のチェックを`ready_for_review`判定より先に追加し、真の場合はLLMを介さず`orchestrator`へ進めず`generate_user_utterance`へ差し戻す。差し戻し先のメッセージは既存の`_build_task_transition_blocked_notice`をそのまま利用し、新規のメッセージ注入実装は行わない。 |
| 影響 | `cela_main.py`の`call_detector`（`cela_main.py:6188-6205`）・`build_graph`内`route_after_user_decision`（`cela_main.py:9695`付近）。新規テスト`tests/test_bl181_task_transition_block_stops_orchestrator.py`5件追加。`python -m py_compile`合格、既存BL-136/176/checkpoint-resume関連51件と合わせて無退行確認。実ドライランでの効果確認は次回以降。今回task_4_1/task_4_2で誤登録されたデータの復旧はBL-180と同様の手法で別途実施予定（本決定は再発防止のみを対象とする）。 |
| 関連 BL | [BL-181](back_log/issue_backlog.md#bl-181-bl-125のタスク遷移ブロックをorchestratorexpertが素通りしtask_idの誤登録データ破損を招く)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-136](back_log/issue_backlog.md#bl-136-issue_logが起票されるが解決されない状態だった可視性強制力の非対称性)、[BL-176](back_log/issue_backlog.md#bl-176-_resolve_task_transitionが離脱先task_idの承認成立を検証しておらずuserが1発言で承認と次タスク指示を同時に行うと状態が壊れうる) |

---

### D-151: `call_decision_extractor`のDeliverable抽出から「全文複製」要求を撤廃し、200字以内の要約で足りるとする（BL-182）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン中に発生した`⚠️ [Decision Extractor] JSON判定パース失敗を検知...層2リトライ 3/2...`エラーを報告。AIの調査（`wrote_agreement_this_turn=True`のため実害無しと確認）を受け、「これは当初はdecision_extractorが抽出していたものをユーザーやエキスパートが直接dbに登録するように変更した後の名残です。もう機能自体を削ってもいいかもしれません」と指摘。AIが提示した3案（全面撤廃／Deliverable全文複製のみ撤廃／wrote_agreement_this_turn=True時のみプロンプト自体をスキップ）のうち、「Deliverable本文の全文複製だけを撤廃（Decision/Directiveの抽出は残す）」を選択） |
| **決定理由** | `call_decision_extractor`のExpert向け指示が、write_agreement呼び出し成功時にはどのみち破棄される（`decision_extractor_node`の`if not wrote_agreement_this_turn:`分岐）Deliverable本文の全文複製を要求しており、これが大きな成果物ほどJSON出力を肥大化させmax_tokens付近での打ち切りを招いていた。さらに調査の結果、write_agreement未実行時の保険（フォールバック）経路自体（`cela_main.py:9013-9023`）が既に`content`が短い場合に`state["expert_output"]`（Agentの発言全文）を自動的に使う仕組みを備えており、decision_extractor自身が全文を複製する必要は元々無かったことが判明した。全面撤廃（advances_to_task_id検出のみ残す）は、BL-082/096/136/139/154が積み上げてきた「LLMがツールを呼び忘れた場合の最終フォールバック」を完全に失うリスクがあるため、実害の直接原因である全文複製要求のみを撤廃する最小スコープを選んだ。 |
| 決定内容 | Expert向け`role_instruction`・共通`common_rules`の「🚨成果物抽出に関する絶対ルール🚨」・JSON出力例の`content`フィールド説明・BL-029節を、いずれも「200字以内の簡潔な要約で構わない」旨へ書き換えた。Decision/Directive抽出指示、BL-082/BL-136のDEFER検出指示、`advances_to_task_id`/`advances_to_phase_id`検出、User側のUPDATE（評価のみ）時の`content`空文字強制は無変更。BL-043（Function Calling方式への全面移行）は本決定の対象外とし`open`のまま据え置く。 |
| 影響 | `cela_main.py`の`call_decision_extractor`（`cela_main.py:6586-6608, 6671-6673, 6703`）。新規テスト`tests/test_bl182_decision_extractor_no_deliverable_full_text.py`5件追加。`python -m py_compile`合格、既存BL-041/050/082/096/139/154/160関連85件と合わせて無退行確認。実ドライランでの効果確認（同種の大きな成果物でパース失敗自体が減るか）は次回以降。 |
| 関連 BL | [BL-182](back_log/issue_backlog.md#bl-182-call_decision_extractorのdeliverable全文複製要求が長大な成果物でjson出力を肥大化させmax_tokens付近での打ち切りを招く)、[BL-043](back_log/issue_backlog.md#bl-043-decision_extractorのjson出力をfunction-calling方式に作り替え既存の自己修復ループd-009に一本化する)、[BL-089](back_log/issue_backlog.md#bl-089-複数jsonフェンスブロックの混線によるレビュー安全ゲートの無効化および全ノード共通の重複再検証の抑制)、[BL-160](back_log/issue_backlog.md#bl-160-_query_ai_liveが最終回答がreasoningチャンネルへ出力されcontentが空になったケースを空応答としてサイレントに握りつぶし1ターン分のdecisiondirectivedeliverable抽出タスク遷移シグナルが丸ごと失われる) |

---

### D-152: `route_after_user_decision`のブロックフラグ判定を「BL-176（離脱先未承認）」だけでなく「BL-125本来（未解決severe issue）」も含めたORへ拡張する（BL-183）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン`log/2026-08-06/0751`をレビューし「task番号がまたずれているようです」と報告。AIの調査でBL-181の第2防衛線に穴（`task_transition_blocked_issue_topics`未チェック）があり、BL-181と同型の事故が再発していたことが判明。ユーザー指示「実装・データ復旧・テストお願い」） |
| **決定理由** | `_resolve_task_transition`が立てるブロックフラグは`task_transition_blocked_unapproved_task_id`（BL-176）と`task_transition_blocked_issue_topics`（BL-125本来）の2種類が排他的に存在するが、BL-181実装時に前者のみをチェック対象としてしまい、後者が発火した実ケース（`log/2026-08-06/0009`の`🛑 [BL-125] 'task_5_2'に未解決・未先送りのsevere issueが1件存在するため...`）を素通りさせていた。BL-181のテストもソース確認で前者の存在しか検証しておらず、欠落を検出できていなかった。両フラグは`_build_task_transition_blocked_notice`側では既に排他的に扱う設計だったため、ルーティング側だけをORに直せば足りると判断した。 |
| 決定内容 | `route_after_user_decision`（`cela_main.py:9719`）の条件を`task_transition_blocked_unapproved_task_id`と`task_transition_blocked_issue_topics`のORへ拡張。`_build_task_transition_blocked_notice`は無変更。 |
| 影響 | `cela_main.py`の`build_graph`内`route_after_user_decision`。新規テスト`tests/test_bl183_task_transition_block_severe_issue_flag.py`4件追加、既存`test_bl181_...`5件と合わせて9件無退行確認。データ復旧（`agreements`/`whiteboard_drafts`/`verified_facts`、`cela.db.bak_bl183`へバックアップ済み）。実ドライランでの効果確認は次回以降。 |
| 関連 BL | [BL-183](back_log/issue_backlog.md#bl-183-bl-181の機械的な第2防衛線がbl-125本来の未解決severe-issueブロックを見落とし素通りさせていた)、[BL-181](back_log/issue_backlog.md#bl-181-bl-125のタスク遷移ブロックをorchestratorexpertが素通りしtask_idの誤登録データ破損を招く)、[BL-125](back_log/issue_backlog.md#bl-125-_resolve_task_transitionはissue_logの未解決状態を参照しておらずフェーズ単位の足止めは実装されていない全体停止の安全弁のみ)、[BL-176](back_log/issue_backlog.md#bl-176-_resolve_task_transitionが離脱先task_idの承認成立を検証しておらずuserが1発言で承認と次タスク指示を同時に行うと状態が壊れうる) |

---

### D-153: `web_search`/`web_fetch`/`read_reference_file`ツールの検索プロバイダをDuckDuckGo（自前実装）とし、`verified_facts`の`confidence` enumは変更せず既存`citations`で対応する（BL-184）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（設計完了、実装は未着手） |
| 決定者 | t-momose（08-05〜08-06分の全ドライランログ監査を依頼し、CELAがクローズドな世界のみで動作し現実の地理・数値を検証できない弱点を確認。改善方針としてweb検索・ファイルIOの実装を提案） |
| **決定理由** | ①検索プロバイダ: 当初Provider抽象化のみ確定させ具体プロバイダは保留していたが、ユーザーが「Tavilyもいいがどのくらい検索が走るかわからないため、まずAPIキー不要・従量課金なしのDuckDuckGoにする」と判断。DuckDuckGoは公式APIを持たないため、`ddgs`等の非公式スクレイピング専用パッケージを追加するのではなく、`web_fetch`用に用意するHTMLテキスト抽出ロジックを再利用できる「自前HTTP GET＋自前パース」方式を採用し、依存パッケージを`requests`のみに絞った（AGENTS.md §7の依存追加最小化方針に合致）。②`confidence` enum: `verified_facts`/`confirmed_variables`の`confidence`（`confirmed`/`provisional`）はAGENTS.md §7の重要定数変更に該当し、BL-041の既存設計思想（web由来の値を安易に`confirmed`扱いしない）とも整合させるべきと判断し、enum自体は変更せず、既存の`citations`フィールド（データモデル無改修）でURLトレーサビリティを持たせる方針とした。③ツール3分割: `web_search`（一覧のみ・軽量）/`web_fetch`（本文取得・キャッシュ）/`read_reference_file`（キャッシュの読み取り専用参照）に分けたのは、Claude Code自身のWebSearch/WebFetch/Readの分離、および既存の`read_project_plan`→`read_deliverable_file`という「一覧→詳細」パターンとの一貫性を重視したため。 |
| 決定内容 | 初期実装の検索プロバイダをDuckDuckGo（`html.duckduckgo.com/html/`への直接HTTPリクエスト＋`html.parser.HTMLParser`ベースの自前パース）に確定。将来的な切り替えに備え`WebSearchProvider` Protocolによる抽象化は維持する。`confidence` enumは変更せず、web由来の値は`citations`で追跡する。詳細設計は`docs/design/back_log/BL-184/BL184_basic_design.md`に原文保存。 |
| 影響 | `cela_main.py`（または分割検討中の`web_tools.py`）に新規ツール3種と`TOOL_DISPATCH`登録、`requirements.txt`へ`requests`追加、`.gitignore`へ`web_cache/`追加。実装はモジュール分割可否・呼び出し回数上限の具体値・ノード展開範囲の3点をユーザー確認後に着手（詳細はBL-184参照）。 |
| 関連 BL | [BL-184](back_log/issue_backlog.md#bl-184-web_searchweb_fetchread_reference_file-ツールの新設現実世界の地理数値をグラウンディングする)、[BL-041](back_log/issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（confidence enum設計思想）、[BL-105](back_log/issue_backlog.md#bl-105-checkpointresume機構がentry_pointから全体再走行するため未応答のuser発言が二重に積まれるlanggraph本来のcheckpointertask未導入という設計ギャップ)（D-086、依存パッケージ追加の先例） |

---

### D-154: `generate_user_utterance`（User AI）にもBL-178と同型の3分割プロンプト構成を適用し、エスカレーション/タスク遷移通知も通常パスで末尾に配置する（BL-185）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ドライラン中に「detctorの差戻を無視して、プロジェクト完了を連呼している」と報告。AIの調査でBL-178と同型の構造的欠陥を発見・報告。ユーザー「OKです。差戻以外の通常パスも`_build_escalation_resume_notice`/`_build_task_transition_blocked_notice`など、意識してほしいことは末尾に置きましょう。キャッシュヒットは悪くなるかもしれませんが、それよりも行動の統制の方が大事です」） |
| **決定理由** | `generate_user_utterance`の単発呼び出しパス（差し戻し再送・初回ターン・本質対話応答・Expert相談応答・終盤宣言ターンで使用、通常のExpertレビューターンで使うStage1-4パイプラインは対象外）は、差し戻し通知を`system_prompt`中盤に組み込んでいたが、`messages`配列が`[system, ...chat_history]`という構造上`chat_history_window=4`件の直近会話が常にそれより後ろで読まれるため、差し戻し通知が埋もれ、Detectorのmajor判定直後にUser AIが削除されたはずの「前回の完了宣言」をそのまま繰り返す実害が発生した。BL-178でcall_expertに導入済みの3分割構成（`system_prompt_leading`→`chat_history`→`system_prompt_trailing`、差し戻し情報を真にchat_historyより後ろに配置）を同型適用すれば解決できると判断。ユーザーはさらに、エスカレーション再開通知・タスク遷移ブロック通知についても「差し戻し以外の通常パス」で末尾配置とするよう指示し、プロンプトキャッシュのヒット率低下という既知のトレードオフ（BL-104の原則）よりも行動の統制を優先する方針を明示した。 |
| 決定内容 | `generate_user_utterance`のsystem_promptを`system_prompt_leading`/`system_prompt_trailing`へ分割し、messagesを3部構成へ変更。`system_prompt_trailing`内の順序は「決定事項DB等の状況説明」→「エスカレーション再開通知」→「タスク遷移ブロック通知」→「🚨最終盤の超重要指示」→「差し戻し通知（最後）」とし、エスカレーション/遷移通知は通常パスでも常にtrailing側に配置。最終盤指示・差し戻し通知の両方に、互いを参照する優先順位の注記を追加。 |
| 影響 | `cela_main.py`の`generate_user_utterance`。新規テスト`tests/test_bl185_user_ai_prompt_reorder.py`10件追加、既存BL-178/104/142/143/096/176関連124件と合わせて無退行確認。`python -m py_compile`合格。Stage4パイプライン内の同種の通知配置は本決定の対象外（差し戻し時は`_is_normal_review_turn`がFalseになりStage4自体が使われないため、今回の実害には無関係と判断）。 |
| 関連 BL | [BL-185](back_log/issue_backlog.md#bl-185-generate_user_utteranceuser-aiのsystem_promptを視座は上から下文脈は過去から現在の順に再構成し差し戻し通知が完了宣言に埋もれ無視される事故を防ぐ)、[BL-178](back_log/issue_backlog.md#bl-178-call_expertのsystem_promptフル版light_system_prompt軽量版を視座は上から下文脈は過去から現在の順に再構成しdetectorの差し戻し情報を両方で真に最後に読ませる実装完了)、[BL-104](back_log/issue_backlog.md#bl-104-call_expertのphases_json目次化read_project_planツール新設プロンプトのキャッシュ効率改善) |

---

### D-155: ゴール改定時、過去タスクの再検証をBL-145と同型の配線でtask_plannerへ強制的に引き継ぐ方式を採用し、タスク遷移バックルートの新設は見送る（BL-186）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「タスク遷移で過去タスクをやり直すルートは作ったほうが良いか？それとも、ゴール改定後は強制提起にタスクプランナーに移し、過去タスクを洗いなおすタスクを追記させる（今回だとphase7以降として）方が確実に洗っていける気はしますが」と(a)(b)を提示。AIが(b)を推奨した理由を説明した上で、ユーザー「お願いします」で承認） |
| **決定理由** | BL-163/BL-168はゴール改定成功時に承認済み過去タスクへ`severity="minor"`のissueを起票するが、`minor`issueはBL-136/BL-145の強制解決ルート（major/escalated専用）に乗らず、`read_issues`がpull型ツールのためどのプロンプトにも自動注入されない。実ドライラン`log/2026-08-06/1432`で、ランが既にphase6/task_6_1（計画上の最終タスク）にあり通常のタスク遷移ではphase1-5へ戻る経路が無いため、flagされた過去タスク13件が誰にも参照されないまま放置されるリスクを確認した。(a)タスク遷移で過去task_idへ戻る新ルートは、成果物・whiteboardのバージョニング、current_task_id管理の分岐、BL-125/176の遷移ブロックロジックとの整合など新規リスクが大きい。(b)はBL-145（滞留escalated issueをplan_revision_reason経由でtask_plannerへ強制引き継ぐ既存の仕組み）と全く同型の配線を再利用でき、新しい状態機械を一切増やさずに済むため、(b)を採用した。 |
| 決定内容 | `_revise_goal_tool_impl`がBL-163の`_flagged`（影響を受けた過去タスク一覧）と起票issue_idから`plan_revision_reason`/`plan_revision_issue_ids`を組み立てて返し、`_LAST_GOAL_REVISION`ブリッジ経由で`generate_user_utterance_node`が`state["plan_revision_reason"]`へ反映する（他要因が既にセット済みの場合は上書きしないガード付き）。`task_planner_node`/`call_task_planner`は無改修とし、既存のrevision_reason消費ロジック（次ターンの`goal_essence`→`task_planner`再入場時の自動再発火、SUPERSEDE処理、`_mark_issue_planned`）をそのまま再利用する。 |
| 影響 | `cela_main.py`の`_revise_goal_tool_impl`・ツール実行ブリッジ・`generate_user_utterance_node`。新規テスト`tests/test_bl186_goal_revision_forces_replan.py`6件追加、既存BL-086/087/095/096/101/126/136/145/163/168/185関連197件と合わせて無退行確認。`python -m py_compile`合格。 |
| 関連 BL | [BL-186](back_log/issue_backlog.md#bl-186-ゴール改定時にtask_plannerへ強制的に過去タスク再検証を引き継ぐ)、[BL-163](back_log/issue_backlog.md#bl-163-revise_goal成功時既に承認済みの過去タスクへ新ゴールとの整合性要再確認issueを機械的に起票する)、[BL-168](back_log/issue_backlog.md#bl-168-verified_factsテーブルにゴール改定を反映するsupersede機構が一切ない)、[BL-145](back_log/issue_backlog.md#bl-145-エスカレーションissue申し送りissueをdetectorreflectorの正当性監査を経てタスクプランナー経由で明示的にタスク化する) |

---

### D-156: `read_verified_fact`の検索精度改善は、embeddingベースのRAGではなくトークン分割OR検索＋difflib近似候補フォールバックの段階的アプローチを採用する（BL-187）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-06 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（「read_verified_factで探したいものが見つからない時が散見されます。rag検索を導入して、意味検索をしてはどうか？」と提案。AIが規模感・依存追加コストを踏まえた段階的アプローチを提案し、ユーザーが「トークン分割OR検索＋近似候補フォールバックを実装して」と承認） |
| **決定理由** | `get_verified_facts_from_db`の`topic`検索は`variable_name LIKE '%keyword%' OR reason LIKE '%keyword%'`というフレーズ全体一致のみで、AIが渡す`topic_keyword`の言い回し・語順が保存済みの文言と噛み合わないと`not_found`になる構造的弱点があった。embeddingベースのRAG（ベクトル検索）は根本解決になり得るが、1run内の`verified_facts`件数は数十件程度に留まり、新規の埋め込みAPI呼び出し・ベクトルDB相当の依存追加はAGENTS.mdの依存追加最小化方針に対しオーバーエンジニアリングと判断した。まず新規依存ゼロで実現できるトークン分割OR検索（言い回しの違いの多くを吸収）と`difflib`（標準ライブラリ）による近似候補フォールバックで様子を見て、実ドライランで依然として意味的なギャップ（同義語・言い換え）が埋もれ続ける場合に改めてembedding方式（SQLite内にembeddingを保存しPythonでコサイン類似度計算、新規のベクトルDBは導入しない案）を検討する段階的アプローチを採用した。 |
| 決定内容 | `_read_verified_fact_handler`に3段階のフォールバックを実装：①既存のフレーズ全体一致、②`_tokenize_topic_keyword`で分割したトークンによる`get_verified_facts_from_db_any_token`のOR検索（`variable_name`指定時は対象外）、③`suggest_similar_verified_facts`による`difflib.get_close_matches`ベースの`did_you_mean`候補提示。 |
| 影響 | `cela_main.py`の`get_verified_facts_from_db`（変更なし、既存関数は温存）、新規`_tokenize_topic_keyword`/`get_verified_facts_from_db_any_token`/`suggest_similar_verified_facts`、`_read_verified_fact_handler`。新規テスト`tests/test_bl187_verified_fact_fuzzy_search.py`13件追加、既存BL-093/094/095/104/148/162/167/168/169/186関連238件と合わせて無退行確認。`python -m py_compile`合格。 |
| 関連 BL | [BL-187](back_log/issue_backlog.md#bl-187-read_verified_factのtopic_keyword検索をトークン分割or検索と近似候補フォールバックで緩和する)、[BL-053](back_log/issue_backlog.md#bl-053-get_verified_facts_from_dbのtopic_keyword検索がvariable_name列しか見ておらず日本語キーワードで構造的にほぼ一致しない) |

---

### D-157: BL-184のweb_search初期実装プロバイダをDuckDuckGo（非公式スクレイピング）からBrave Search API（正式API）へ変更する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-07 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（AIから4案（検知して明示エラー化しこのまま進める／他Providerへ切替／ブラウザ自動化／今回は保留）を提示された上で、当初「chromiumどchorome driverでgoogle検索を叩くのは？」と提案。AIがブラウザ自動化の依存重量・Google ToS/技術リスク・`MAX_TOOL_ITER`圧迫の懸念を説明したところ、「Brave Search APIに切り替える」を選択） |
| **決定理由** | `web_tools.py`実装完了後、実際に`html.duckduckgo.com/html/`へ疎通確認したところ、数回のリクエストだけで即座にBot対策の画像認証チャレンジ（HTTP 202、`anomaly-modal`）が返り、5秒後の再試行でも解除されなかった。D-153で「レート制限・一時ブロックのリスクあり」と一般論としては記録していたが、実測により理論上の懸念ではなく即時的・高頻度に発生する実害であることが判明した。ユーザーが提案したブラウザ自動化（Chromium/ChromeDriver）は技術的には有効だが、AIが（1）ブラウザバイナリ含む重量級の新規依存（BL-184が一貫して守ってきた依存追加最小化方針から大きく外れる）、（2）Google検索はDuckDuckGo以上に自動化を敵視しておりToS上・ブロック回避の持続性の両面でリスクが高い、（3）ブラウザ起動コストが`MAX_TOOL_ITER`（1回のquery_AI呼び出し内のツール往復上限）を圧迫しかねない、という懸念を説明した上で、正式APIであるBrave Search API（無料枠あり、`httpx`のみで実装可能＝新規パッケージ依存なし）への切り替えを提案し、ユーザーが承認した。 |
| 決定内容 | `web_tools.py`に`BraveSearchProvider`（`https://api.search.brave.com/res/v1/web/search`、`X-Subscription-Token`ヘッダでAPIキー認証、`web.results[].{title,url,description}`を`{title,url,snippet}`へマッピング）を追加し、`get_search_provider()`の既定値を`duckduckgo`から`brave`へ変更。APIキーは環境変数`CELA_BRAVE_SEARCH_API_KEY`から読み、未設定時は`WebSearchConfigError`。`DuckDuckGoSearchProvider`はコードとして温存し`CELA_WEB_SEARCH_PROVIDER=duckduckgo`で引き続き選択可能とした上で、Bot対策チャレンジページ検知時に空の結果リストではなく明示エラーを返す防御を追加。 |
| 影響 | `web_tools.py`（`BraveSearchProvider`追加、`get_search_provider()`既定値変更、`DuckDuckGoSearchProvider`へのチャレンジ検知追加）。API仕様調査メモを`docs/refs/brave_search/api_notes.md`（AGENTS.md §9準拠、source URL・取得日付き）へキャッシュ、`docs/refs/duckduckgo/html_endpoint_notes.md`へ実測結果を追記。新規テスト5件追加（`tests/test_bl184_web_tools.py`、Brave成功/APIキー未設定/レスポンス欠落フィールド、DuckDuckGoチャレンジ検知）、既存36件と合わせて41件全通過。`python -m py_compile`合格。**利用にはBrave Search APIキーの取得・環境変数設定がユーザー側で別途必要**（実ドライラン実施前の残作業）。 |
| 関連 BL | [BL-184](back_log/issue_backlog.md#bl-184-web_searchweb_fetchread_reference_file-ツールの新設現実世界の地理数値をグラウンディングする) |

### D-158: BL-184のcela_main.py配線パラメータ（呼び出し回数上限・アタッチ範囲）を確定する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-184の`web_tools.py`実装完了後、`cela_main.py`への配線に残っていた2つの未確定事項（`max_web_search_calls`/`max_web_fetch_calls`の具体値、Expert/Detector以外への展開要否）をユーザーへ確認した。 |
| **決定理由** | ユーザーが「呼び出し回数上限はひとまず30回」「task_planner/task_plan_reviewer/Expert/Detector/reflector/facilitatorで試してみて、必要ならUserや他にも拡張」と回答したため、この値で配線を確定した。上限30はMAX_TOOL_ITER=30（BL-155、単一query_AI呼び出し内のツール往復上限）と揃えた覚えやすい数値であり、run全体累積の上限としては妥当な初期値としてユーザーが選択したもの。ノード拡張は、task_planner/task_plan_reviewerが計画時点で現実性を検証できる方が上流での手戻りを減らせること、reflector/facilitatorも滞留issueの根拠（citations由来URL）を自ら検証できる方が良いこと、をユーザーが判断した。アタッチする具体的なツール種別（全3ツールか`read_reference_file`のみか）はAIが「事実収集・執筆役（task_planner/task_plan_reviewer/Expert）には全3ツール、監査・進行管理役（Detector両パス/Reflection/Facilitator）には`read_reference_file`のみ」という当初BL-184設計の区別原則をノード拡張後も維持する形で決定し、ユーザーの指示（各ノードで「試してみる」）の範囲内の実装判断として扱った。 |
| 決定内容 | `AppConfig`/`LineageState`の`max_web_search_calls`/`max_web_fetch_calls`を各30に設定。`call_task_planner`/`call_task_plan_reviewer`/`call_expert`は`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`の3つ全てをアタッチ。`call_detector`（ドメイン監査パス・数値監査パス両方）/`call_reflection`/`call_facilitator`には`READ_REFERENCE_FILE_TOOL`のみをアタッチ（新規の外部通信・追加コストを発生させない）。`call_reflection`は本決定に伴いBL-109以来の`tools=None`（単発判定）から`read_reference_file`単体のツールループへ変更した。`call_orchestrator`/`generate_user_utterance`（User AI）は当面スコープ外のまま。 |
| 影響 | `cela_main.py`（`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`スキーマ追加、`TOOL_DISPATCH`登録、`LineageState`/`AppConfig`拡張、6ノードの`tools=[...]`更新）、`.gitignore`（`web_cache/`追加）。`tests/test_bl184_web_tools.py`41件再通過、`python -m py_compile`合格を確認。実ドライラン確認はBrave Search APIキー設定後（ユーザー側対応）に別途実施。 |
| 関連 BL | [BL-184](back_log/issue_backlog.md#bl-184-web_searchweb_fetchread_reference_file-ツールの新設現実世界の地理数値をグラウンディングする) |

> **一部改訂（2026-08-07、D-160）**: 「`call_detector`（両パス）には`READ_REFERENCE_FILE_TOOL`のみ、新規の外部通信・追加コストを発生させない」という決定内容は、実ドライラン（`log/2026-08-07/1244`/`1312`）で監査役自身も未検証の学習知識のみで判定していた実態が判明したことを受け、D-160でweb_search/web_fetchの追加アタッチへ改訂された。他の内容（呼び出し回数上限30、task_planner/task_plan_reviewer/Expertの3ツール全アタッチ、Reflection/Facilitatorの読み取り限定）は変更なし。

---

### D-159: BL-188のcitations強制力とスキーマ適用範囲を確定する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーから「数字だけでなく全ての情報にソースを明示させたい。一次ソース・最新情報を優先し、web検索結果は批判的に評価させたい」との要望があり、調査の結果`verified_facts.citations`が実質未実装（topic文字列が機械的に入るだけ）であることが判明した。実装にあたり2つの分岐（citations未記載の強制力、citations欄の適用範囲）をAskUserQuestionで確認した。 |
| **決定理由** | 強制力について、ユーザーは「プロンプト誘導のみ（推奨・まず様子見）」を選択した。理由はBL-042（Detectorのconstraint_issue硬直判定でツールループが同じ論点を延々再検討しトークンを浪費した過去事故）と同型のリスクを避けるため——citations欄をDetectorのminor/major判定に機械的に組み込むと、同じ硬直リスクを新たに持ち込むことになる。まずはプロンプト誘導とデータの可視化（表示反映）だけで実効性を見て、弱ければ後からDetector監査へ格上げする段階的アプローチとした。適用範囲について、ユーザーは「agreementsテーブル（Decision/Deliverable本体）にも新規citations列を追加」を選択した。confirmed_variables限定の小さな修正では、数値以外の一般的なDecision/Deliverableの主張にはソースを持たせられず、要望の「数字だけでなく全ての情報」を満たせないため。 |
| 決定内容 | `agreements`テーブルへ`citations TEXT DEFAULT '[]'`列を追加。`WRITE_AGREEMENT_TOOL`にトップレベル`citations`パラメータと`confirmed_variables[].citations`サブフィールドを追加し、LLMが実際に引用元（type: web/goal_text/prior_agreement/expert_calculation/user_input/document, detail: 文字列）を渡せるようにした。未指定時は`confirmed_variables`側は従来のtopic文字列フォールバックを維持し、強制はしない。Detectorの判定ロジックへの機械的組み込みは行わない。ツール説明文（`WRITE_AGREEMENT_TOOL`/`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`）へ一次ソース優先・最新性優先・web検索結果の批判的評価を促す指示を追記し、各ノードの個別プロンプトではなくツールスキーマ側に一元化した（function-calling仕様上、対象ノードへ毎回必ず提示されるため保守性が高い）。 |
| 影響 | `cela_main.py`（`agreements`テーブルスキーマ・`_ensure_agreements_citations_column`マイグレーション・`WRITE_AGREEMENT_TOOL`スキーマ・`_commit_agreement_from_tool`・`_write_agreement_impl`・`_build_agreements_context`・`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`説明文）。新規テスト`tests/test_bl188_citations.py`9件、既存オフライン全スイートと合わせて無退行を確認。 |
| 関連 BL | [BL-188](back_log/issue_backlog.md#bl-188-全ての情報にソースcitationsを明示させる)、[BL-184](back_log/issue_backlog.md#bl-184-web_searchweb_fetchread_reference_file-ツールの新設現実世界の地理数値をグラウンディングする) |

---

### D-160: Detectorへweb_search/web_fetchを追加し、Expertの検索義務を強化し、Detector監査へ根拠実在性チェックを追加する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-188実装後の実ドライラン3件（`log/2026-08-07/1047`/`1244`/`1312`）をユーザーがレビューした結果、(1) `1312`ではExpertが7回呼ばれ全てweb_search/web_fetchを装備していたにもかかわらず一度も使わず、根拠のない前提数値（デマンドタクシー運営費`@8,000円/日`）を土台に大規模な戦略分析を構築していたこと、(2) それを差し戻したDetectorの反論（最低賃金法に基づく試算）自体もD-158の設計通りweb_search/web_fetchを持たず、Detector自身の学習知識からの推論に過ぎなかったこと、の2点が判明した。ユーザーから「(1) Detectorにもweb_searchを追加しつつ (2) Expertの検索義務を強化し (3) Detector監査も数値・提案に根拠があるかを確認する方向にプロンプトを強化してほしい」との指示を受けた。 |
| **決定理由** | D-158では「監査役（Detector/Reflection/Facilitator）には新規の外部通信を発生させない」という原則でDetectorをread_reference_file限定にしたが、実ドライランで「ExpertのAI推測をDetectorの別のAI推測で監査しているだけで、どちらも実在の相場データに当たっていない」という構造的な弱点が露呈した。Detectorが数値の妥当性を監査する以上、検算（python_repl）が式の正しさしか保証しないのと同様、外部裏取りの手段（web_search/web_fetch）を持たない監査は前提の実在性までは検証できない。プロンプト誘導のみでExpertが自発的に検索する頻度が実ドライラン3件を通じて一貫して低かった（1047: 0件、1244: 途中から発火、1312: 0件）ことから、より強い動機付け（「最低限」文言による半必須化）も必要と判断した。Detector側の強制力については、BL-188当初（D-159）は「まず様子見」としていたが、ユーザーが今回明示的に「根拠があるかを確認する形に強化」を指示したため、citationsが`expert_calculation`のみ（外部裏付けなし）の前提についてDetector自身が検証する、という形でプロンプトを強化した（Detectorのminor/major判定ロジック自体への機械的組み込みは引き続き行わず、BL-042の硬直化リスクは回避）。 |
| 決定内容 | ① `call_detector`の両パス（ドメイン監査・数値監査）の`tools=[...]`へ`WEB_SEARCH_TOOL`/`WEB_FETCH_TOOL`を追加（`READ_REFERENCE_FILE_TOOL`と合わせ、Expert/task_planner/task_plan_reviewerと同じ3ツール構成になる）。② Detectorの両パスのプロンプトへ「根拠の実在性チェック」段落を追加：citationsが`expert_calculation`/`prior_agreement`のみで外部一次情報の裏付けがなく、かつDetector自身も真偽の確信が持てない前提数値があればweb_searchで検証し、実態と乖離していればconstraint_issueの根拠にする、という指示を明記。③ Expertのフルsystem_prompt/light_system_promptのBL-188ガイダンスへ「【最低限】」文言を追加し、ゴール文にない数値を新たに前提として置く場合はcitationsを`expert_calculation`のみで済ませず最低1回はweb_searchを呼ぶことを明記（機械的な強制ゲートではなくプロンプト上の強い要請、BL-042の教訓を踏まえ引き続き機械的介入は見送り）。 |
| 影響 | `cela_main.py`（`call_detector`両パスの`tools=[...]`拡張、両パスのプロンプト追記、`call_expert`のフル/light system_promptの追記）。オフライン全テストスイート783件通過（`test_bl168_verified_facts_stale_after_goal_revision.py`の1件はBL-173起因の既知のタイミング依存flakyで単体実行では通過、本変更とは無関係）、`python -m py_compile`合格。効果測定は次回以降の実ドライランで確認する。 |
| 関連 BL | [BL-188](back_log/issue_backlog.md#bl-188-全ての情報にソースcitationsを明示させる) |

---

### D-161: web_fetchのHTML/PDF抽出をpypdf/html.parser自前実装からMicrosoft markitdownへ置き換える

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが`log/2026-08-07/1312`のPDF抽出結果を見て「単純な文字解析だと体裁が崩れ、図もなく結構厳しい」と指摘。表構造を持つPDF（国交省の乗合タクシー資料等）で、`pypdf.extract_text()`が表の行列構造を無視してテキストを流し込むだけになっていることを確認した。ユーザーがMicrosoft markitdown（PDF/HTML等をMarkdown化するPython ユーティリティ、https://github.com/microsoft/markitdown）の利用を提案し、HTML変換も含めて検証するよう指示した。 |
| **決定理由** | 実データ（`log/2026-08-07/1525`で実際にfetchされた国交省PDF、および`log/2026-08-07/1244`でExpertが辿ろうとしたRoAD to the L4のHTMLページ）で`pypdf`/独自`_HtmlTextExtractor` vs `markitdown`を側で比較した結果、markitdownはPDFの表を`| --- | --- |`形式の本物のMarkdownテーブルとして、HTMLは見出し階層（`#`/`##`/`###`）・太字・リンクを本文中の自然な位置（`[text]（url）`形式のMarkdownリンク記法）に保持したMarkdownとして返すことを確認した。特にHTMLのリンクが本文中の文脈的位置に保たれる点は、直前に独自実装した「ページ末尾へのリンク一覧付記」（BL-188セクション9）より優れており、その独自実装は本決定により不要になった。依存重量は`pypdf`（数MB、純Python）から`markitdown[pdf]`（onnxruntime/numpy/Pillow/pdfminer等を含み約100MB、内部でファイル形式自動判定にGoogleのmagikaという軽量MLモデルを使うためonnxruntimeがコア依存になる）へ大幅に増えるが、ユーザーが「情報が上手く取得できずエージェントの能力が損なわれるのは本末転倒。依存が重くても、より良くするために使える手段があるなら使いたい」と明示的に判断した。画像・図の内容理解（OCR/vision相当）は本決定の範囲外（markitdownの`llm_client`オプションで対応可能だが、追加のLLM呼び出しコストを伴うため今回は見送り、将来必要になれば別途検討）。 |
| 決定内容 | `requirements.txt`の`pypdf`を`markitdown[pdf]`へ置き換え。`web_tools.py`の`_HtmlTextExtractor`（html.parser自前実装、BL-184/BL-188で拡張したリンク収集機能含む）と`_extract_pdf_text`（pypdf自前実装）を削除し、`fetch_and_extract`をHTML/PDF共通で`MarkItDown().convert_stream(io.BytesIO(raw), stream_info=StreamInfo(mimetype=...), url=url)`を呼ぶ実装へ統一した。markitdownは`convert_stream(url=...)`を渡しても相対リンクを自動解決しないことを実データで確認したため、`_resolve_relative_markdown_links`（正規表現ベースの後処理）でMarkdownリンク記法`](url)`の相対URLをfetch元のURLを基準に絶対URLへ解決する処理を追加した。安全性面では、より厳密な内部パーサ（pdfminer/BeautifulSoup等）に渡す前提のため、HTML/PDF共通でバイト列サイズ上限超過時は（従来PDFのみだった）切り捨てず明示エラーとする方針にHTMLも統一した。ページ数上限（`_MAX_PDF_PAGES`）等のpypdf固有の細粒度制御は撤廃し、既存の総文字数上限（`_MAX_OUTPUT_CHARS`）とバイトサイズ上限（`_MAX_FETCH_BYTES`）による制御に一本化。変換失敗時（`MarkItDownException`）はSsrfBlockedErrorへラップし、既存のエラーレスポンス変換パターンをそのまま踏襲。 |
| 影響 | `requirements.txt`、`web_tools.py`（`fetch_and_extract`全面書き換え、`_HtmlTextExtractor`/`_extract_pdf_text`削除）、`cela_main.py`（`WEB_FETCH_TOOL`説明文の更新、「[Links found on this page]」への言及を削除しインラインリンクの説明へ変更）。`tests/test_bl184_web_tools.py`のfetch関連テストを全面書き換え（`pypdf`/`_HtmlTextExtractor`の内部実装ではなく`web_tools._MARKITDOWN.convert_stream`の呼び出し境界をモックする方式へ統一）。同ファイル45件、オフライン全テストスイート781件通過、`python -m py_compile`合格。 |
| 関連 BL | [BL-188](back_log/issue_backlog.md#bl-188-全ての情報にソースcitationsを明示させる) |

---

### D-162: ノードごとにLLMクライアント/モデルを個別指定できるよう役割別変数を細分化する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーから「各ノードで使用するモデルを指定したい。現在でも3〜4つほどに分けているが、ノードごとに指定したい」との要望があった。調査の結果、従来は`client_user`/`model_user`（User AI）、`client_agent`/`model_agent`（Expert・Orchestratorが共有）、`client_auditor`/`model_auditor`（Task Planner・Detector両パス・Decision Extractor・Resource Arbiter・Reflection・Facilitator・Integrator・Reviewer QA・Goal Essence Analyst・Task Plan Reviewerの計10ノードが共有）、`client_summarizer`/`model_summarizer`の4変数構成だった。特に`client_auditor`への一括集約により、性質の異なる10ノード（機械的検算中心のDetector数値監査、文脈理解中心のFacilitator等）が同一モデルに固定され、ノード特性に応じたモデル選定ができなかった。AskUserQuestionで(1)Detectorの2パス（ドメインレビュー／数値監査）を同一変数にまとめるか別々にするか、(2)モデル切り替えの方式（コード内変数の直接編集 or 環境変数での上書き対応）を確認した。 |
| **決定理由** | (1) Detectorの2パスは「与えられた情報内の論理・法令矛盾を検出する」ドメインレビューと「python_replでの検算結果を評価する」数値監査という異なる性質の監査タスクであり、ユーザーは将来的に別モデルを割り当てる可能性を残したいとして「別々に指定」を選択した。(2) 環境変数方式は.envでの切り替えを可能にする一方、既存のモデル変数定義（`deepseek`/`gemini_2_5`等）自体が既にコード内の名前付き定数として運用されており、ユーザーは普段からこのファイルを直接編集してモデルを切り替えている実運用スタイルに合わせ「コード内の変数を直接編集（現状踏襲）」を選択した。環境変数対応は追加の抽象化層となり今回のスコープでは過剰と判断された。 |
| 決定内容 | `client_agent`/`model_agent`と`client_auditor`/`model_auditor`を廃止し、ノードごとに独立した13組の`client_X`/`model_X`変数（`client_orchestrator`、`client_expert`、`client_task_planner`、`client_task_plan_reviewer`、`client_detector_domain`、`client_detector_numeric`、`client_decision_extractor`、`client_resource_arbiter`、`client_reflection`、`client_facilitator`、`client_integrator`、`client_reviewer_qa`、`client_goal_essence`、および各対応する`model_X`）へ分解した。各ノードのquery_AI呼び出し箇所（call_task_planner、call_detector両パス、call_decision_extractor、call_resource_arbiter、call_reflection、call_facilitator、call_integrator、call_reviewer_qa、call_goal_essence_analyst、call_task_plan_reviewer、call_expert、call_orchestrator）を、対応する専用変数を参照するよう変更した。デフォルト値は全ノードとも従来通り`client_openrouter`/`nemotron_3_ultra`のままとし、ユーザーが該当行のclient/model値を書き換えない限り挙動は変わらない（後方互換）。`client_user`/`model_user`（User AI）と`client_summarizer`/`model_summarizer`（要約用ローカルモデル）はそれぞれ元から単一ノード専用のため変更不要と判断した。 |
| 影響 | `cela_main.py`（設定ブロック・13箇所のquery_AI呼び出し）。`python -m py_compile`合格、フルオフラインスイート781件中780件Pass（1件はBL-173として既知のflakyテストで本修正と無関係、単体再実行では成功）。 |
| 関連 BL | [BL-189](back_log/issue_backlog.md#bl-189-ノードごとにllmクライアントモデルを個別指定できるよう役割別変数を細分化する) |

---

### D-163: 督促する対象集合と、滞留＝停滞として数える対象集合は同一の述語で決定する（BL-125離脱ゲートは明示的例外）

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-08/1514`（`facilitation_count>5`でhalt）のレビューで、停滞判定の引き金となった滞留escalated issue20件が全件`write_issue(DEFER)`済み（受け皿task_id設定済み）だったにもかかわらず`stagnant`と断罪されhaltに至った。調査の結果、`defer_to_task_id`を見て「受け皿あり」と沈黙する是正経路（BL-136強制解決文、BL-145計画化、BL-125/158遷移ゲート）と、`defer_to_task_id`を一切見ずに督促し続ける懲罰経路（BL-103 pin「要対応」、BL-096/144停滞判定）が併存しており、この2集合の乖離自体が事故の本質だった。 |
| **決定理由** | 「督促されている」issueが「督促の必要が無いと既にみなされている」issueと異なる基準で数えられていることが根本原因であり、個別のバグ修正ではなく不変条件として明文化しないと同型の乖離が別箇所で再発する。ただしBL-125の遷移ゲート（タスク離脱時の安全弁）は、督促（是正を促す）ではなく安全装置（未解決のまま離脱させない）という異なる関心事であり、統一すると「完了済みタスクへDEFERされたissueが離脱ゲートに復活し現在タスクの担当者が解けないissueでタスクを出られなくなる」という新規デッドロックを招くため、明示的な例外として据え置く。 |
| 決定内容 | `_is_issue_effectively_deferred`/`_get_actionable_escalated_issues`（BL-194）を新設し、`_get_forced_escalated_issues_text`（BL-136）・`reflection_node`の機械的停滞上書き（BL-096/144）・`facilitator_node`のescalated issue名指し（BL-096）・`_build_escalation_pin_text`（BL-103）・`_formalizable_stale`（BL-145）の5箇所が同一の述語を参照するよう統一する。`_get_blocking_issues_for_transition`（BL-125）のSQLはこの統一の**対象外**とし、その理由をコード上のコメントとして明文化する。`call_reflection`のプロンプトへ渡す一覧は全件維持し行ごとに注記のみ付す（除外すると未解決のまま`completed`を宣言できてしまうため）。 |
| 影響 | `cela_main.py`（BL-194 §2、S1〜S4）。設計は`docs/design/back_log/BL-194/BL194_basic_design.md`参照。 |
| 関連 BL | [BL-194](back_log/issue_backlog.md#bl-194-defer_to_task_idの解釈不統一と自己先送りによる偽の停滞判定強制停止) |

---

### D-164: 自己先送り（defer_to_task_id=実行中タスク自身）をtool boundaryで拒否し、代償としてACKNOWLEDGEを同時導入する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-08/1514`で、滞留escalated issue20件中6件が`task_2_1`自身への先送り（自己先送り）だった。DEFERの実装は受け皿task_idの実在チェックのみで自己参照を禁じておらず、自己先送りされたissueは「督促する経路（BL-103 pin・BL-096/144停滞判定）は点灯し続けるが、是正経路（BL-136/145/125/158）は全て沈黙する」という非対称状態になり、解消不能な滞留を生んでいた。これがtask_2_1のacceptance_criteria外の懸念（車両台数）をExpertのプロンプトへ「要対応」として刺し続けた直接原因。 |
| **決定理由** | 自己先送りを単純に拒否するだけでは、BL-158の機械的差し戻しゲート（`_get_blocking_issues_for_transition`を判断源とする）が毎ターン再発火する状態に戻り、User AIは「嘘のRESOLVE」か「別タスクへの誤配DEFER」を強いられる。実ログのUser AI自身の`think`が、この種のジレンマ（現タスクの責務だが対応中、という状態を表現する手段が無い）を長文で自覚していたことから、正直な出口が必須と判断した。第3の状態を`issue_log.status`語彙の拡張として実装する案は却下した（D-165参照）。 |
| 決定内容 | `_write_issue_impl`のDEFER分岐で、受け皿task_idが実行中タスク自身と一致する場合を拒否する（BL-194 §3）。拒否メッセージはRESOLVE/DEFER/ACKNOWLEDGEの3択を明示する。この拒否（S8）とACKNOWLEDGE（S7）は**片方のみのリリースを禁止**し、必ず同時にリリースする。 |
| 影響 | `cela_main.py`（BL-194 §3・§5、S7・S8）。既存テストへの影響: `tests/test_bl136_issue_visibility_and_transition_gate.py`のフィクスチャは`current_task_id`/`defer_to_task_id`が別task_idのため自己先送りに該当せず、本決定の実装で赤くならないことを事前確認済み。 |
| 関連 BL | [BL-194](back_log/issue_backlog.md#bl-194-defer_to_task_idの解釈不統一と自己先送りによる偽の停滞判定強制停止) |

---

### D-165: 第3のissue状態（ACKNOWLEDGE＝現在タスクの責務であり対応中）を`status`語彙の拡張ではなくTTL付き補助列で表現する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | D-164のACKNOWLEDGE（RESOLVEでもDEFERでもない第三の選択肢）を、`issue_log.status`へ新しい値（例: `'acknowledged'`）を追加する形で実装するか、既存の`status`/`severity`を変えず別の列で表現するかの選択。 |
| **決定理由** | D-079/D-080の不変条件「`severity='major'`の行は常に`status='escalated'`を伴う」に、`_write_issue_impl`のCREATE分岐・`_bump_issue_occurrence`の再発昇格・BL-125ゲートのSQL・BL-096/136/145の全`_get_*_issues`ヘルパーが依存している。`major`の行を`escalated`以外の`status`へ動かすと、これら全経路から完全に不可視になり、BL-103 pinからもBL-125遷移ゲートからも消える——まさにBL-158を無効化する万能の逃げ道になってしまう。BL-145の`planned`は`_mark_issue_planned`という非LLM・内部専用の遷移でのみ到達するため先例として援用できない。 |
| 決定内容 | `issue_log`へ`acknowledged_until_round`/`acknowledged_count`/`acknowledge_reason`の3列を追加する（`status`/`severity`は一切変更しない）。TTLラウンド数`_BL194_ACK_TTL_ROUNDS=3`（BL-144の3ラウンド滞留閾値と揃え「ACKは滞留カウントをちょうど1周期分止める」という意味を持たせる）、累計上限`_BL194_ACK_MAX_GRANTS=2`（最悪でも6ラウンドで必ず滞留判定へ復帰し不死身化しない）で承認した（AGENTS.md §7の事前承認対象定数）。BL-125の遷移ゲート本体はACK抑制の対象外とし（`exclude_acknowledged`は既定False）、「対応中」表明が離脱の免罪符にならないようにする。同一topicの再検出（`_bump_issue_occurrence`）時は`acknowledged_until_round`を即時0へリセットする。 |
| 影響 | `cela_main.py`（BL-194 §5、S7）。`init_db`へのスキーマ移行1件、`WRITE_ISSUE_TOOL`の`action_type` enumへ`"ACKNOWLEDGE"`追加。 |
| 関連 BL | [BL-194](back_log/issue_backlog.md#bl-194-defer_to_task_idの解釈不統一と自己先送りによる偽の停滞判定強制停止) |

---

### D-166: DEFERのスコープ整合性は機械判定せず、受け皿タスクのスコープをエコーバックするに留める

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-08/1514`で、`task1_3_budget_overrun_composite_service`（予算超過）が`task_2_1`（需要セグメント定義）へDEFERされ、スコープ外の内容がtask_2_1のplan_draftへ「正式に」貼り付いた。DEFER先が懸念の内容に対応したタスクかを機械的に検証すべきか。 |
| **決定理由** | LLMジャッジによる整合性判定は、DEFERがドライラン中の頻出ホットパスであるためレイテンシ・コストが跳ね判定も非決定的になる上、D-164で自己先送りという逃げ道を塞いだ後では、誤判定（偽陰性）がUser AIの唯一のtriage手段をブロックし新種のデッドロックを生む。キーワード重なりによる機械判定も、`acceptance_criteria`が日本語自由文であり形態素解析器も未導入のため、BL-074/081/193が示した「緩い文字列一致」の誤判定リスクをそのまま引き継ぐ。BL-042/BL-188が確立した「プロンプト誘導のみ、機械的ゲートは追加しない」方針を踏襲する。 |
| 決定内容 | DEFER成功時の戻り値へ、受け皿タスクの`acceptance_criteria`/`owns_variables`をそのまま含める（`target_task_scope`）。DB/LLM呼び出しは追加せず、`state["phases"]`から既に構築済みの`task_id_to_task`辞書を再利用する。ミスマッチの判断はモデル自身に委ね、同じtopicで再DEFERすれば最新の指定が有効になる旨をヒントとして返す。 |
| 影響 | `cela_main.py`（BL-194 §6、S6）。`WRITE_ISSUE_TOOL`のdescriptionへ1文追記。 |
| 関連 BL | [BL-194](back_log/issue_backlog.md#bl-194-defer_to_task_idの解釈不統一と自己先送りによる偽の停滞判定強制停止) |

---

### D-167: ゴール文の地名匿名化を廃止し、実在の長野県茅野市名＋実データを直接使用する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `TARGET_GOAL`は実在の長野県茅野市をモデルにしているが、地名を「八ヶ嶺市（仮名）」と匿名化していた。ユーザーから「茅野市は『のらざあ』というデマンド交通を導入しており、回答のカンニングとなり得てしまう」との懸念提起があり、匿名化を維持すべきか、実名へ切り替えるべきかを検討した。 |
| **決定理由** | 匿名化は地理指紋（駅標高・JR中央本線・人口規模等の組み合わせ）から実際には特定可能であり、答えの隠蔽に実効性がない一方、`task_1_1`の成果物（`log/2026-08-09/1100`）が「架空都市のため実測値ではない」という長い留保に分量を割く無駄なコストだけを生んでいた。また、CELAが測りたいのは「現実と同じ結論に到達できる推論能力」であり、実在事例（のらざあ等）へ計画が自律的に収束すること自体は望ましい検証シグナルである。地理を伏せることはこの検証目的そのものと矛盾する。実データを直接埋め込むことでラン間の再現性も向上する。 |
| 決定内容 | `TARGET_GOAL`の地名を「長野県茅野市」と明記し、人口・高齢化率・面積・標高・主要拠点アクセス・大学等の背景データをユーザー（Claude）がweb検索で確認した実データへ全面差し替える。ただし実在の解決策そのもの（2022年10月の路線バス13路線廃止→のらざあ移行）は答えの核心に相当するため、「問題」側（路線バス廃止の事実）のみ背景として採用し、「解決」側（のらざあへの移行）はゴール文へ一切含めない。 |
| 影響 | `cela_main.py`（`TARGET_GOAL`）。参照データは`docs/refs/chino_city/chino_city_data.md`へ出典URL・取得日付きでキャッシュ。 |
| 関連 BL | [BL-195](back_log/issue_backlog.md#bl-195-ゴール文の実データ化長野県茅野市実在precedentのらざあ等発見時の無derivation転記防止ガードレール) |

---

### D-168: 実在precedent（のらざあ等）発見時の対処はプロンプト誘導（転記禁止・導出過程の明記義務）に留める

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | D-167により地理データを実データ化した結果、エージェントがweb_searchで実在の類似事例（茅野市の「のらざあ」等）を発見し、その具体的運用数値（運行本数・車両台数・運賃・人員体制等）を検証・独自導出なしにそのまま成果物へ転記してしまうリスクが残った。機械的にブロックすべきか、プロンプト誘導に留めるべきかを検討した。 |
| **決定理由** | 機械判定（例：成果物の数値とWeb検索結果の数値が一致したら拒否）は、独自算出の結果がたまたま実例と近い値になった正当なケースまで誤って弾き、Expertの唯一の成果物提出手段をブロックしてBL-158型のデッドロックを再発させかねない。BL-042/BL-188/BL-194が確立した「プロンプト誘導のみ、機械的な強制ゲートは追加しない」標準方針をそのまま踏襲する。 |
| 決定内容 | `call_expert`（system_prompt・light_system_promptの両経路）と`call_detector`（Pass1ドメイン妥当性・Pass2数値監査の両パス）へ、実例数値の無検証転記を禁止し、`confirmed_variables`のreason_whyへ本課題の制約からの導出過程を明記させるプロンプト文言を追加する。Detector側は、導出過程を伴わない転記をminor以上の指摘対象とする。 |
| 影響 | `cela_main.py`（`call_expert`・`call_detector`）。 |
| 関連 BL | [BL-195](back_log/issue_backlog.md#bl-195-ゴール文の実データ化長野県茅野市実在precedentのらざあ等発見時の無derivation転記防止ガードレール) |

---

### D-169: 達成不能な受入条件の抑止は、task_planner側とUser AI側の両方へ入れる（片方では足りない）

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-09/1230`で`task_1_1`がVer.19まで空転した原因は、実行環境で原理的に達成不能な実測要求（OSM PBFの直接処理等）だった。抑止をどこへ入れるべきか。 |
| **決定理由** | 当初はtask_plannerがacceptance_criteriaへ過剰な水準を書いたことが原因と考え、そちら（BL-196）だけを直した。しかし再発したため実ログを追い直したところ、acceptance_criteria自体は妥当であり、**User AI（Stage3承認判断・Stage4差し戻し指示・初回ターンの非Stage4パス）が後付けで要求を積み増していた**ことが真因と判明した。要求水準を吊り上げうる主体が複数あるため、生成側（task_planner）と評価側（User AI）の双方へ入れないと塞ぎきれない。さらにUser AI側は3つの独立したコードパスを持ち、Stage3/4だけへ入れた時点では初回ターン（`chat_history`が空でStage3/4を通らない経路）が素通りして事故が再現した（`log/2026-08-09/1733`）ため、3経路全てへ同じ趣旨の文言を入れる必要があった。 |
| 決定内容 | BL-196として`call_task_planner`へ、BL-197として`generate_user_utterance`のStage3・Stage4・非Stage4パス（`system_prompt_trailing`）へ、それぞれ「実行環境で到達可能な水準を超える手段・検証水準を要求しない」旨のガードレールを追加する。監査の厳格さ自体（数値の裏付けを求めること）は否定せず、要求水準の上限だけを画す。 |
| 影響 | `cela_main.py`（`call_task_planner`、`generate_user_utterance`の3経路）。効果は`log/2026-08-09/1744`で検証済み。 |
| 関連 BL | [BL-196](back_log/issue_backlog.md#bl-196-task_plannerが実行環境に無い専用処理能力を前提としたacceptance_criteriaを書いてしまう)、[BL-197](back_log/issue_backlog.md#bl-197-user-aiの承認指示がタスクのacceptance_criteriaを超える手段検証水準を後付けで積み増す) |

---

### D-170: 実測手段の不足は、要求を抑止するだけでなく実際に使えるAPIを与えて解消する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | D-169のプロンプト誘導により過剰要求は止まったが、`log/2026-08-09/1744`ではweb_searchが30回/run上限に30箇所以上到達し、個別地点の座標・標高を汎用検索で都度探すことに検索予算を浪費していた。「実測できないものを要求しない」だけで十分か。 |
| **決定理由** | プロンプト誘導は抑止しかできず、「実測できるものを実測する」余地を広げない。調査の結果、標高・住所ジオコーディング・2点間の測地線距離は国土地理院の無料・無認証APIで、道路距離・所要時間はOpenRouteServiceの無料枠APIで、いずれも正面から取得可能と判明した。抑止（BL-196/197）と供給（BL-198）は対の関係にあり、両方揃って初めて「取得できるものは実測し、取得できないものは仮定として明記する」という健全な状態になる。 |
| 決定内容 | 新規モジュール`geo_tools.py`に4ツール（`gsi_geocode`/`gsi_get_elevation`/`gsi_calc_distance_bearing`/`calc_road_route`）を実装し、Expert・Detector（Pass1/Pass2）へ付与する。道路距離の提供元は、OSMnx+NetworkX（重量級依存が規模に不相応）・OSRM公開デモサーバ（評価用途限定）・GraphHopper（無料枠が少ない）・Google Maps（クレジットカード必須で最も重いロックイン）を却下し、BL-184のBrave Search API選定と同じ「軽量な正式APIを優先する」方針でOpenRouteServiceを採用する。 |
| 影響 | `geo_tools.py`（新規）、`cela_main.py`、`docs/refs/gsi_api/api_notes.md`、`docs/refs/openrouteservice/api_notes.md`。`calc_road_route`のみ環境変数`CELA_ORS_API_KEY`が必要。 |
| 関連 BL | [BL-198](back_log/issue_backlog.md#bl-198-国土地理院apiopenrouteserviceによる地理データの実測化) |

---

### D-171: 直線距離と道路距離の取り違えは、単一の注記ではなく4箇所の重複明記で防ぐ

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `gsi_calc_distance_bearing`（GSI測量計算API）が返すのは測地線＝直線距離であり道路距離ではない。これを道路距離として扱われると、山間部の屈曲した道路では所要時間・SLA達成判定が楽観側へ大きく歪む。どこで誤用を防ぐか。 |
| **決定理由** | 本プロジェクトはこれまで、単一箇所のみの注意書きが読み飛ばされる事故を繰り返し観測してきた（BL-178: 差し戻し通知がchat_historyに埋没、BL-188初回実装: light_system_promptにしか指示が無くフルsystem_promptで素通り、BL-197: Stage3/4に入れたが初回ターンの別経路が素通り）。「精度の高そうな実測値」であるがゆえに、誤用された場合の害は推測値よりむしろ大きい。冗長性のコストは低く、事故のコストは高い。 |
| 決定内容 | ①ハンドラ返り値の`note`フィールド（毎回必ず同梱、テストで常時含まれることを検証）、②ツールスキーマのdescription、③Expertのプロンプト、④Detectorのプロンプト（監査観点として「直線距離を道路距離として提示していないか」を重点確認項目に指定）、の計4箇所で重ねて明記する。 |
| 影響 | `geo_tools.py`、`cela_main.py`、`tests/test_bl198_geo_tools.py`。 |
| 関連 BL | [BL-198](back_log/issue_backlog.md#bl-198-国土地理院apiopenrouteserviceによる地理データの実測化) |

---

### D-172: 開発者事前収集の参照データ（docs/refs）へのアクセス手段が無かったため、既知の事実の再検索でweb_search上限が枯渇した

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-09/2222`で、BL-195が`docs/refs/chino_city/chino_city_data.md`へ既にキャッシュした施設住所・座標をExpertが知らずweb_searchで再検索し、30回/run上限を使い果たしていた。既存の`read_reference_file`はweb_cache（当該run内のweb_fetch結果）専用でdocs/refsを読めない。上限を上げるだけで十分か、根本的に参照経路が欠けているのではないか。 |
| **決定理由** | 上限を上げるだけでは同じ無駄な再検索が続くだけで、単に猶予が伸びるにすぎない。真因はAGENTS.md §9が定める「開発者が事前収集した参照データ」をExpert/Detectorが読む手段自体が存在しなかったことであり、`read_reference_file`と`docs/refs`は用途が異なる（前者はrun内の一時キャッシュ、後者は開発者キュレーションの静的データ）ため、既存ツールの対象ディレクトリを広げるのではなく別ツールとして新設する方が責務が明確になる。ただし参照データに無い項目（番地までの実住所等）は依然として正当なweb_search用途であり続けるため、上限緩和自体も安全弁として併用する。 |
| 決定内容 | 新規ツール`read_goal_reference`（`web_tools.py`）を追加し、`state["goal_reference_dir"]`（run開始時に`AppConfig`からコピー）配下のみを読める形でExpert・Detector（Pass1/Pass2）へ付与する。プロンプトで「web_searchの前にread_goal_referenceを確認する」優先順位を明記する。あわせて`max_web_search_calls`を30→50へ緩和する（ユーザー承認済み、AGENTS.md §7の定数変更に該当）。 |
| 影響 | `web_tools.py`、`cela_main.py`、`tests/test_bl199_goal_reference.py`。 |
| 関連 BL | [BL-199](back_log/issue_backlog.md#bl-199-web_searchの前に開発者事前収集の参照データdocsrefsを確認せず同じ事実の再検索で呼び出し上限を使い果たす) |

---

### D-173: web_cacheはrun単位で分離せず、URLキーでrunをまたいで共有する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-184の`web_cache/<run_id>/<sha256(url)[:16]>.md`は、同一URLの取得結果をrun単位で分離していた。ユーザーが「web_cacheももったいないので、runが変わっても永続的に読めるようにして」と指摘。run単位の分離を維持すべきか。 |
| **決定理由** | 同一URLをweb_fetchするコスト（呼び出し回数消費・応答待ち）はrunが変わっても同じであり、run単位の分離はそのコストを毎回リセットして無駄にしているだけだった。BL-199で新設した`read_goal_reference`（開発者事前収集データ）とは異なり、`web_cache`はエージェント自身がrun中に集めた一次資料であり、後続のrunにとっても等しく有用な情報である。キャッシュの鮮度が問題になるほど内容が短期間で変化するURLは想定されていない（AGENTS.md §9のdocs/refs運用と同様、静的な公的情報・一次資料が主対象）。 |
| 決定内容 | `cache_file_path`から`run_id`引数を除去し、`web_cache/<sha256(url)[:16]>.md`（URLキーの全run共有）へ変更する。あわせて、Expert/Detectorのプロンプトにおける外部情報の参照優先順位を「①read_goal_reference（開発者事前収集）→②read_reference_file（web_fetchキャッシュ、全run共有）→③web_search（最終手段）」という単一の3段階順序として明記する（ユーザー指示「refs探索→web_cache探索→webサーチの順で」に対応）。 |
| 影響 | `web_tools.py`、`cela_main.py`、`tests/test_bl184_web_tools.py`、`tests/test_bl199_goal_reference.py`。 |
| 関連 BL | [BL-200](back_log/issue_backlog.md#bl-200-web_cacheがrun単位で分離されており別runで既に取得済みのページも無駄に再取得していた) |

---

### D-174: resumeしたrunのstateは、呼び出し回数上限等の実行時設定をチェックポイントからではなく現在のconfigから再同期する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-199で`max_web_search_calls`を30→50へ緩和した後も、既に走っていたrunを`--resume`すると相変わらず30回で頭打ちになっていた（`log/2026-08-09/2313`で実機確認）。チェックポイントから復元した`state`が、run開始時点の古い`config`値を固定して持ち続けていたことが原因。会話履歴（chat_history等）と同じ扱いで良いのか。 |
| **決定理由** | 呼び出し回数上限・参照ディレクトリのようなフィールドは、Expert/User AIの発言や合意事項のような「会話の履歴」ではなく「実行時設定」であり、意味的に別カテゴリに属する。BL-197で発見した「チェックポイント巻き戻しはcela.db側を巻き戻さない」問題は、古い会話状態が新しい成果物汚染を引き起こす方向だったが、本件はその逆（開発者が加えた設定改善が、走行中のresumeに反映されない）であり、両方とも「チェックポイントは会話状態のスナップショットであり、それ以外の“今の正しい設定”の情報源ではない」という同じ性質から生じている。resumeのたびに実行時設定側だけ現在のconfigへ揃えるのは、会話の一貫性を損なわない安全な変更である。 |
| 決定内容 | `run_ai_vs_ai_loop`のresume分岐、`state = snapshot.values`の直後に、`max_web_search_calls`/`max_web_fetch_calls`/`max_road_route_calls`/`goal_reference_dir`の4フィールドを現在の`config`引数の値へ明示的に上書きする。呼び出し済みカウンタ自体（`web_search_call_count`等）は実際の消費実績のためリセットしない。 |
| 影響 | `cela_main.py`、`tests/test_checkpoint_resume.py`。 |
| 関連 BL | [BL-201](back_log/issue_backlog.md#bl-201---resumeしたrunのstateがresume時点のconfig変更呼び出し回数上限等を一切反映しない) |

---

### D-175: APIリトライ消尽時は、プレースホルダー文字列を「そのノードの回答」として下流へ流さず、思考ログを保持したままノードをやり直す

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `_query_AI_live`はAPIリトライ（`delays=[8,16,32,64,128]`）を使い切ると`"(サーバー高負荷によるAPIエラー)"`を返していた。`log/2026-08-09/2348`では、この文字列がExpertの発言としてDetectorへ渡り、Detectorが「Agentの応答がこれのみで指示に一切応えていない」として却下する空転が、確認できたDetector指摘7件中4件で発生した。この設計を維持してよいか。 |
| **決定理由** | プレースホルダーは「モデルの回答」ではなくインフラ障害の痕跡であり、それを回答として扱うと、Expertが1文字も作業していないのにラウンドと版番号だけが消費され、さらにDetectorの却下履歴として合意DBにも記録が残る（実害が後続ラウンドへ波及する）。一方、BL-122により`loop_messages`（それまでのreasoning・ツール結果）は既にリトライ間で保持される設計になっているため、`attempt`カウンタを巻き戻すだけで「思考ログを重ねたままノードをやり直す」ことが追加の状態管理なしに実現できる。BL-171の日次上限（やり直しても解消しない）は別経路で即座に一時停止させる先例があり、「リトライで解消するもの／しないもの」を区別する方針とも整合する。 |
| 決定内容 | リトライループを`for attempt in range(...)`から`while True`へ変更し（ループ本体は無変更。`attempt`は例外処理ブロック内でしか参照されないためインデント変更を伴わない）、`delays`消尽時にプレースホルダーを返す前にノードをやり直す分岐を追加する。やり直しは`loop_messages`/`iteration_start`を再初期化せず`attempt`のみ巻き戻す。回数は`_MAX_NODE_REDO_ON_API_EXHAUSTION=2`、やり直し前のクールダウンは`_NODE_REDO_COOLDOWN_SECONDS=180`（AGENTS.md §7の新規定数、ユーザー承認待ち）。使い切った場合は従来どおりプレースホルダーを返す（有界性の担保）。 |
| 影響 | `cela_main.py`（`_query_AI_live`）、`tests/test_bl202_edit_reliability_and_node_redo.py`。 |
| 関連 BL | [BL-202](back_log/issue_backlog.md#bl-202-サーバーエラーのプレースホルダー応答によるラウンド空転とdetector注釈を巻き込んだ巨大old_textによるedits失敗の連鎖) |

---

### D-176: ホワイトボード編集は「読む→1箇所だけ直す」を繰り返す手順とし、Detector注釈の削除は本文修正と別のeditsへ分離する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-09/2348`でedits失敗が58回発生し、その全てが`edits[0]`だった。失敗したold_textは節見出しからDetector注釈ブロックまでを含む数千字規模で、`read_whiteboard_excerpt`の窓（`…（中略）`/`…（以下省略）`）の外側を記憶で補って再構成していた。プロンプトの書き方をどう是正するか。 |
| **決定理由** | 調査の結果、Expertの不注意ではなく**プロンプト内の相互矛盾**が原因と判明した：BL-076が「注釈行ごと含めてold_textに入れよ（そうすれば修正と同時に注釈も消える）」と指示する一方、後から追加されたBL-193が「注釈ブロック全体を巻き込んで巨大なold_textにするな」と指示しており、Expertは前者に忠実に従うことで後者に違反していた。BL-193追加時にBL-076側の旧指示を残置したことが直接の原因であり、まず矛盾自体を解消する必要がある。加えて、BL-193の「read_whiteboard_excerptの使用を推奨」という弱い表現では、実際にツールを呼んだ上でなお窓の外を記憶で補う挙動が観測されたため、手順として明示する必要があった。機械的なold_text長制限も検討したが、正当な長い置換まで弾くリスクがあり、BL-042/BL-188/BL-194が確立した「プロンプト誘導のみ」の標準方針に従って見送る。 |
| 決定内容 | ①BL-076側の「注釈行ごと含めて」を撤回し、本文修正と注釈削除を別々のeditsの要素に分ける指示へ置換する（フル`system_prompt`側・`light_system_prompt`側の両方）。②編集方針を手順として明示する：old_text組み立て前に**必ず**`read_whiteboard_excerpt`で現在の文字列を取得、**1箇所ずつ**修正、old_textは一意に特定できる最短の文字列にし省略マーカーの先は含めない。③複数セクションでの矛盾を指摘された場合は、見出しではなく問題の文言そのものをkeywordに`match_count`で残り箇所を確認し全箇所を修正する。④`_apply_text_edits`の不一致エラーへ、old_textの実文字数と具体的な次の手順3点を含める（「正確に引用しろ」の反復では20回連続で自己修復できなかったため）。 |
| 影響 | `cela_main.py`（`call_expert`・`_build_task_scope_context`・`WRITE_AGREEMENT_TOOL`・`READ_WHITEBOARD_EXCERPT_TOOL`・`_apply_text_edits`）、`tests/test_bl202_edit_reliability_and_node_redo.py`。 |
| 関連 BL | [BL-202](back_log/issue_backlog.md#bl-202-サーバーエラーのプレースホルダー応答によるラウンド空転とdetector注釈を巻き込んだ巨大old_textによるedits失敗の連鎖) |

---

### D-177: 事物の同一性は「ゴール文中に文字列として実在するか」という機械的判定で守り、LLMの主観に委ねない

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-10/0901`で、ゴール文に`公立諏訪東京理科大学`とあるのにExpertが記憶から「長野大学」（実在するが無関係な大学）と書いた。数値は`verified_facts`にあったが、名称そのものが事実として登録されていなかったため、すり替わりを検出する対象が存在しなかった。事物を構造化して保存するだけで、この種の名称ハルシネーションを防げるか。 |
| **決定理由** | 保存形式を構造化しただけでは、登録する名称自体が誤っていればハルシネーションはそのまま器の中に入るだけで防げない。防ぐには、登録の入口で**客観的に検証可能な条件**を課す必要がある。ゴール文に文字列として存在するかどうかは、LLMの主観判断を要さない機械的な部分一致判定であり、これ1つで「長野大学」を`origin='goal_text'`としては登録不能にできる。全面的な新規事物登録の禁止は、web_searchで正当に発見した事物まで書けなくしBL-158型のデッドロックを招くため、`origin`で区別する（禁止ではなく可視化）方針を採る。 |
| 決定内容 | `task_planner`内の`seed_entities_from_goal`で、抽出した`canonical_name`が絶対目標の本文中に文字列として存在するかを検証し、存在しないものは`origin='goal_text'`として登録しない（`rejected`として報告するのみ）。ゴール文に無い事物は`register_entity`（`origin='discovered'`、citations必須）でのみ登録できる。 |
| 影響 | `cela_main.py`（`seed_entities_from_goal`・`register_entity_in_db`・`_register_entity_handler`）、`tests/test_bl204_entity_registry.py`。 |
| 関連 BL | [BL-204](back_log/issue_backlog.md#bl-204-実世界事物レジストリentities-entity_attributesの新設) |

---

### D-178: 事物の属性は`verified_facts`の出典封筒（confidence 2値＋citations.type）をそのまま流用し、新しい語彙（assumption等）は追加しない

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-204設計の初版は、`entity_attributes.confidence`を`confirmed`/`provisional`/`assumption`の3値としていた。独立レビュー（Cline）から、これは設計方針§2.1「既存語彙に揃え新しい語彙を足さない」との自己矛盾だと指摘された。実測値・二次情報・工学的仮定を区別する必要はBL-195〜198から続く要求であり、これをどう表現するか。 |
| **決定理由** | 検証の結果、`citations[].type`（`web`/`goal_text`/`prior_agreement`/`expert_calculation`/`user_input`/`document`）が既に「出所」を表しており、`expert_calculation`が「工学的仮定・自己導出値」を過不足なく表現できることが分かった。`confidence`（確定度：どれだけ動かないか）と`citations.type`（出所：どこから来たか）は直交する2軸であり、`assumption`は`confidence`軸への不要な語彙の追加だった。BL-076とBL-193がプロンプト内で矛盾する指示を残置し58回のedits失敗を招いた事故（BL-202/D-176）が示すように、新しい語彙・新しい状態を足すこと自体が将来の不整合の種になる。 |
| 決定内容 | `entity_attributes.confidence`は`verified_facts`と同じ`confirmed`/`provisional`の2値のみとする。「工学的仮定である」ことは`citations[].type="expert_calculation"`で表現する。列名も`verified_facts`に揃え`confirmed_by`/`confirmed_at`とする（初版の`recorded_by`/`recorded_at`から改名）。 |
| 影響 | `cela_main.py`（`entity_attributes`テーブル定義・`upsert_entity_attribute`・`_write_entity_attribute_handler`）、`docs/design/back_log/BL-204/BL204_basic_design.md`§2.1.1、`tests/test_bl204_entity_registry.py`。 |
| 関連 BL | [BL-204](back_log/issue_backlog.md#bl-204-実世界事物レジストリentities-entity_attributesの新設) |

---

### D-179: ツールの役割分担は、スキーマ説明だけでなく実際に使う各ノードのプロンプト本文にも明記する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-204で`read_entity`を8ノードへ展開した後、`log/2026-08-10/1829`でモデルが`read_entity`と`read_verified_fact`の役割分担を理解できず、空引数での探索的な呼び出しを繰り返す事例が観測された。修正としてまず`READ_ENTITY_TOOL`のスキーマ説明1箇所に境界を明記したが、ユーザーから「read_entityを使用するノードのプロンプト説明にも書かないと、見落とされます」と指摘を受けた。ツールのスキーマ説明とプロンプト本文の誘導文は、どちらか一方で足りるのか。 |
| **決定理由** | 実際に混乱が発生したUser AI (Stage4)の思考ログを確認すると、モデルはBL-204のプロンプト文言（「レジストリが真実の源」）は認識していたが、その情報源がツールのスキーマ説明ではなくプロンプト本文だったことが読み取れる。本プロジェクトは、ツール一覧を機械的な配線（`tools=[...]`）だけでなく、各ノードのプロンプト本文で毎回「あなたが使えるツールは…です」と明示的に列挙し直す設計を一貫して採用してきた（BL-198/199/200等）。スキーマ説明はAPI呼び出しの都度モデルへ渡るが、複数のツールが並ぶ中で個々の説明文がどこまで重みを持って読まれるかは保証できず、プロンプト本文の誘導文（そのノードの文脈に即した具体的な注意）の方が実効性が高いことが今回の事例で裏付けられた。 |
| 決定内容 | `READ_ENTITY_TOOL`のスキーマ説明への追記に加え、`read_entity`を付与した全8ノードそれぞれのプロンプト本文へ、`read_verified_fact`との境界説明（BL-205として）を個別に追記する。読み取り対象のツールを持たないノードには、その旨も明記し誤った代替を示さない。 |
| 影響 | `cela_main.py`（`READ_ENTITY_TOOL`、`call_expert`・`call_detector`・`call_task_planner`・`call_task_plan_reviewer`・`call_reviewer`・`call_reflection`・`call_facilitator`・`generate_user_utterance`の各プロンプト）、`tests/test_bl205_entity_verified_fact_disambiguation.py`。 |
| 関連 BL | [BL-205](back_log/issue_backlog.md#bl-205-read_entityとread_verified_factの役割分担が伝わらず無駄な探索呼び出しが繰り返される) |

---

### D-180: issueの「先送り済みか」の判定は、いつ記録されたかに関わらずdefer_to_task_idの有無だけで行う

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-10/2100`（ライブ中のドライラン）で、task_2_3→task_3_1への移行がラウンド31から36以上にわたり繰り返し差し戻されていた。DBを確認すると該当issue（`winter_vehicle_capex_conflict`）は`defer_to_task_id=task_3_1`が既に設定済みだったが、Detectorは`status='escalated'`のみを根拠に`major`判定を繰り返していた。BL-125/158の機械的ゲート（`_get_blocking_issues_for_transition`）は`defer_to_task_id`の有無で正しく判定しているのに、なぜDetector自身のLLM判定は繰り返し差し戻すのか。 |
| **決定理由** | `write_issue(DEFER)`はBL-136の設計により意図的に`status`を`escalated`のまま変更せず、`defer_to_task_id`だけを記録する（先送り後もこのissueは「重大な懸念として記録され続ける」ことに意味があるため）。ところがBL-181のDetectorプロンプト指示（`role_specific_instruction`のuser分岐3節）は`status='escalated'`の残存だけを見て、かつ「**今回の発言内で**」RESOLVE/DEFERが実行されたことを要求していた。DEFERは一度実行すれば恒久的に`defer_to_task_id`が残るにもかかわらず、承認を試みるたびに**同じラウンド内での再実行**を求める基準になっており、機械的ゲート（正しい）とDetectorの自然文判定（過剰に厳しい）が矛盾していた。これはBL-076/BL-193（プロンプト内の相互矛盾が58回のedits失敗を招いた事故、BL-202/D-176）と同型の「複数箇所に同じ規則を書いた結果、一方だけ更新漏れが起きる」パターンである。 |
| 決定内容 | BL-181のプロンプト指示を、`defer_to_task_id`が（いつ設定されたかに関わらず）既に設定済みであれば正式に先送り済みとみなし`major`としないよう修正する。`defer_to_task_id`が未設定のまま残っているissueがある場合のみ、従来通り`major`で差し戻す。 |
| 影響 | `cela_main.py`（`call_detector`のuser向け`role_specific_instruction`BL-181節）、`tests/test_bl207_defer_gate_ignores_prior_round.py`。 |
| 関連 BL | [BL-207](back_log/issue_backlog.md#bl-207-bl-181のdetectorプロンプトがdefer_to_task_id設定済みのissueにも毎ラウンド再deferを要求し無限に差し戻し続ける) |

---

### D-181: web_fetchのコンテンツサイズ上限を2MBから8MBへ緩和する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが「web検索のpdfですが、2MBに引っかかることがしばしばあるようです」と報告。`web_tools.py`の`_MAX_FETCH_BYTES`（BL-184で新設、HTML/PDF共通のダウンロード時サイズ上限）は2MBだが、政府・自治体配布のPDF一次資料はページ数・図表が多く、これを超える例が実運用で頻発していた。どの程度まで緩和するか。 |
| **決定理由** | AGENTS.md §7により定数変更には事前承認が必要。ユーザーが「5MB〜10MB程度まで増やしてください」と具体的な範囲を提示して承認したため、その中間値（8MB）を採用した。上限を撤廃せず引き続き固定値で管理するのは、BL-184設計時の安全方針（サイズ上限超過時は切り捨てず明示エラーとする）を維持するため。 |
| 決定内容 | `_MAX_FETCH_BYTES`を2MB（`2 * 1024 * 1024`）から8MB（`8 * 1024 * 1024`）へ変更する。 |
| 影響 | `web_tools.py`（`_MAX_FETCH_BYTES`）。`tests/test_bl184_web_tools.py`は定数を動的参照するため無改修。 |
| 関連 BL | [BL-208](back_log/issue_backlog.md#bl-208-web_fetchのコンテンツサイズ上限2mbに政府自治体pdfがしばしば抵触する) |

---

### D-182: 要求水準の上限（acceptance_criteriaを超えない）は、要求を出しうる全経路に置く

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-196（task_planner）・BL-197（User AI Stage3/4）で「タスクのacceptance_criteriaを超える検証水準を新たに義務付けない」というガードレールを既に入れていたにもかかわらず、`log/2026-08-11/0016`のtask_2_3で同種の空転が再発した。Detector自身が受入基準3項目すべてを`criteria_status=[true,true,true]`と判定した後もタスクが完了せず、Orchestratorの`focus_guidance`が受入基準に無い成果物（時間帯別シミュレーション、複数シナリオの補完交通モデル、冬季運休の状態遷移モデル）を要求し続けていた。ガードレールをどこまで広げるべきか。 |
| **決定理由** | BL-196/197は「要求水準を吊り上げている犯人」を実ログで特定してからその1箇所を塞ぐ、という進め方を2回繰り返した（1回目はtask_planner、2回目はUser AI）。しかし要求を出しうる経路は他にもあり、BL-078で導入した`focus_guidance`という第3の経路が素通しのまま残っていた——BL-078の実装当時はまだこの観点自体が存在しなかったためである。これはBL-205/D-179で確認した「ツールの役割分担は1箇所に書くだけでは伝播しない」、およびBL-076/BL-193/D-176の「同じ規則を複数箇所に書いた結果、一方だけ更新漏れが起きる」と同型の構造的問題であり、個別対応を繰り返すのではなく、**Expertへ作業指示を与えうる経路すべてに同じ上限を置く**という方針として明示的に決定する。 |
| 決定内容 | `call_orchestrator`の`focus_guidance`生成プロンプトへ、acceptance_criteriaを上限とするガードレール（新しい要求項目を追加する場所ではない、受入基準に無い成果物・分析・モデルを義務付けない、既に充足済みの項目にさらに高い水準を求めない）を追加する。今後Expertへ作業指示・着眼点を与える経路を新設する際は、同じ上限を併せて置くことを既定とする。 |
| 影響 | `cela_main.py`（`call_orchestrator`のプロンプト）、`tests/test_bl209_orchestrator_focus_guidance_scope.py`。 |
| 関連 BL | [BL-209](back_log/issue_backlog.md#bl-209-orchestratorのfocus_guidanceに要求水準の上限が無くacceptance_criteriaを超える要求を毎ラウンド積み増す) |

---

### D-183: Deliverableの識別（supersede対象の特定）は、entry_typeで絞り込みphase_idはフェイルセーフ照合に留める

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-206の再調査で、`decision_extractor_node`のUPDATE分岐が「topic文字列一致」だけでsupersede対象を探しており、entry_typeの異なるエントリ（Userの却下が`entry_type='Decision'`として抽出された場合）が同一topicのDeliverable行まで乗っ取ってしまうことが判明した。加えて、`phase_id`のフォールバックが`item.get(key, default)`の欠落判定に依存しており、LLMが`"phase_id": ""`を明示的に返すケースを捕捉できていなかった。識別ロジックをどう堅牢化するか。 |
| **決定理由** | supersedeループへの`entry_type`条件追加とphase_idの`or`フォールバック化は最小修正として妥当だが、それだけでは「LLMが返す識別子は将来も何らかの形でドリフトしうる」という前提に対して脆弱なままである。BL-131は既に`get_latest_whiteboard`で「task_idはrun_id内で一意」という規約に基づき、phase_idを完全一致条件からフェイルセーフな整合性チェック（不一致は警告のみ、発見は妨げない）へ格下げする設計を確立していた。`_find_active_deliverable_agreement`だけがこの規約に従わず完全一致のままだったことが、今回の孤児化を成立させる最後の1ピースだった。同じ規約を持つ2つの関数の扱いが食い違っていること自体が将来の再発源になるため、揃えることを決定として明示する。 |
| 決定内容 | `_find_active_deliverable_agreement`を、task_id単独で検索しphase_id不一致は警告のみとする設計（`get_latest_whiteboard`と同型）へ変更する。加えて、decision_extractor_nodeのsupersede対象探索は`entry_type`一致を必須条件とする。今後、Deliverableやそれに準ずる版管理対象を識別子で探す新規コードを書く場合も、「一意性の根拠となる列（この場合task_id）で検索し、それ以外の列は完全一致条件ではなくフェイルセーフな整合性チェックに留める」という設計を既定とする。 |
| 影響 | `cela_main.py`（`_find_active_deliverable_agreement`、`decision_extractor_node`のUPDATE分岐、`item.get("phase_id")`のフォールバック）、`tests/test_bl206_deliverable_orphaning.py`、`tests/test_bl161_write_agreement_phase_id_fallback.py`（既存1件の期待値を仕様変更に合わせ反転）。 |
| 関連 BL | [BL-206](back_log/issue_backlog.md#bl-206-write_agreementのedits照合が実際には空のホワイトボード内容に対して行われ本来一致するはずのold_textが繰り返し不一致になる)、BL-131 |

---

### D-184: タスク遷移先のフェーズ解決は、phase_idが省略されても常にtask_idから探索し、current_phaseへの決め打ちはフォールバックに留める

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-11/0118`で、User承認後に`call_decision_extractor`が`{"advances_to_phase_id": null, "advances_to_task_id": "task_4_0"}`を正しく抽出し続けたにもかかわらず、`_resolve_task_transition`が`task_4_0`（phase_4所属）を`current_phase`（phase_3）のタスク一覧から探し「存在しない」と拒否し続け、Reflectionが`stagnant`と判定してシステムをHALTさせた。BL-191で`_find_phase_containing_task`（task_idの所属フェーズを全フェーズ横断で探すヘルパー）は既に存在していたが、`redirect_backward`専用経路でしか使われていなかった。フェーズ解決ロジックをどう直すか。 |
| **決定理由** | `advances_to_phase_id`が省略され`advances_to_task_id`だけが返るケースは、今回の実データで8回連続発生しており、稀な例外ではなく通常運転で起こりうるパターンだと確認できた。「phase_idが無ければcurrent_phaseとみなす」という決め打ちは、同一フェーズ内遷移では偶然正しく動くため長らく見過ごされてきたが、フェーズをまたぐ遷移では原理的に常に失敗する構造的欠陥だった。既に同じ目的の全フェーズ探索ヘルパー（`_find_phase_containing_task`）が存在していたにもかかわらず配線されていなかった事実は、BL-205/D-179・BL-207/D-180・BL-209/D-182で繰り返し確認してきた「同じ規則・同じ解決策を複数の経路に個別に書く設計は、どれか1経路で更新・配線漏れが起きる」というこのプロジェクトの再発パターンの、また別のインスタンスである。 |
| 決定内容 | `_resolve_task_transition`のフェーズ解決順序を、①`advances_to_phase_id`が明示されていればそれを最優先、②省略時は`advances_to_task_id`から`_find_phase_containing_task`で全フェーズ横断探索、③それでも見つからない場合のみ`current_phase`へフォールバック、という優先順位に変更する。あわせて、探索で解決したフェーズが`current_phase`と異なる場合は、`advances_to_phase_id`の明示有無に関わらず`current_phase`を追従させる（`current_task_id`と`current_phase`の不整合を防ぐため）。 |
| 影響 | `cela_main.py`（`_resolve_task_transition`）、`tests/test_bl210_cross_phase_transition.py`。 |
| 関連 BL | [BL-210](back_log/issue_backlog.md#bl-210-_resolve_task_transitionがadvances_to_phase_id省略時にcurrent_phaseへ決め打ちしフェーズをまたぐ遷移を常に拒否する)、BL-191、BL-125、BL-176 |

---

### D-185: 遷移意図の回収は構造化フィールドを優先し、自然文からの推定は候補が一意に定まる場合に限る最終手段とする

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-11/0941`で、User AIがtask_4_2を承認しtask_4_3を明示指示、Detectorも`criteria_status:[true,true,true]`で追認したにもかかわらず、`call_decision_extractor`が`advances_to_task_id: null`を返し、さらに移行意図を表すDirectiveイベントも`phase_id`・`task_id`ともに空文字で、移行先が`topic`と`owned_variable_values`の自然文にしか存在しない形で返った。この抽出漏れを救うために導入されたBL-139の安全網は、Directiveの構造化`task_id`が非空であることを発火条件としていたため空振りし（実ログ中の補完メッセージ0件）、`current_task_id`がtask_4_2に固定されたまま空転した。安全網をどこまで広げるか。 |
| **決定理由** | LLMが構造化フィールドを空にしたまま情報を自然文側へ置くドリフトは、BL-206（`phase_id: ""`）に続く2例目であり、この運用モデルの反復傾向として扱うべき段階に来た。したがって「構造化フィールドが埋まっている」という前提に依存した安全網は、それ自体がもう一段の安全網を必要とする。一方で自然文からのtask_id推定は、差し戻し文や引継ぎ文が複数タスクへ言及するのが常態であるため、単純に「最初に見つかったものを採る」と誤った先読み切替を引き起こす——BL-176の未承認ゲートやBL-125の未解決issueゲートが守ろうとしている「承認されていないタスクへ勝手に進まない」という不変条件を、安全網自身が破壊しかねない。そこで、推定は実在task_idかつ離脱元を除いた候補が**一意に定まる場合に限る**フェイルクローズとし、曖昧なら補完せず従来どおり停止する。停滞は検知可能（Reflectionのstagnant判定）だが、誤った先読み切替は静かに状態を壊すため、両者を天秤にかければ後者を避ける方が損失が小さい。 |
| 決定内容 | 遷移意図の回収を3段構成とする。①`advances_to_task_id`がLLMから明示されていればそれを最優先（従来どおり）、②省略時はDirectiveの構造化`task_id`から補完（BL-139、従来どおり）、③それも空の場合に限り、Directiveの`topic`・`content`・`rationale`・`owned_variable_values`の自然文から計画に実在するtask_idを推定する（BL-211）。③は離脱元task_idを除外したうえで候補が一意のときだけ採用し、複数候補なら警告のみを出して補完しない。`status="Deferred"`の除外と`target_role == "user"`限定というBL-139の既存ガードは③にも継承する。 |
| 影響 | `cela_main.py`（`_infer_directive_target_task_ids`新設、`decision_extractor_node`のBL-139補完ブロック）、`tests/test_bl211_directive_task_id_inference.py`。 |
| 関連 BL | [BL-211](back_log/issue_backlog.md#bl-211-bl-139の遷移補完がdirectiveのtask_idが空文字の場合に空振りしタスク切替が永久に成立しない)、BL-139、BL-210、BL-206、BL-039 |

---

### D-186: Deliverableの「ホワイトボード済みか」の判定は、agreements側の文字列表現ではなくwhiteboard_draftsテーブルの実在を権威とする

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | `log/2026-08-11/1034`で、DetectorとUserがtask_4_2の承認撤回にaction_type=SUPERSEDE＋200字以下の短い無効化理由文（BL-062が想定した「ホワイトボードには触れない」用途）を使った結果、新しく「有効」になったDeliverable行のdecision_whatがその短い理由文そのものになり`WHITEBOARD:`プレフィックスを失った。後続のUPDATE(edits)は`old_content.startswith("WHITEBOARD:")`で「ホワイトボード済みか」を判定していたためFalseと誤判定し、短い理由文に対してExpertの実在するold_textを照合してしまい、editsが17回連続で失敗した。whiteboard_draftsテーブル自体には実データが無傷で残っていたにもかかわらず、判定ロジックが別のテーブル（agreements）の、しかも用途次第で信頼できなくなる文字列表現に依存していたことが原因である。この判定をどう直すか。 |
| **決定理由** | BL-131（`get_latest_whiteboard`はphase_idをWHERE句に含めずtask_id単独で検索する）・BL-206（`_find_active_deliverable_agreement`もtask_id単独で検索し、phase_id不一致は警告に留める）は、いずれも同じ教訓——「agreements側に記録された文字列（phase_idやdecision_whatの形式）は、LLMの出力揺れやSUPERSEDEの用途分岐によって容易に信頼できなくなるため、真に権威とすべきは実データを保持する側のテーブル（whiteboard_drafts）である」——を別の角度から確立していた。今回の`is_whiteboard`判定もまったく同じ構造の脆弱性であり、対症療法（SUPERSEDEの短文分岐で`content`にWHITEBOARD:ポインタを人工的に埋め込む等）ではなく、既に確立された設計方針を一貫して適用する方が、将来同種の経路（SUPERSEDE以外の新しいaction_typeや呼び出し元）で同じ症状が再発するのを防げる。 |
| 決定内容 | `_commit_agreement_from_tool`のUPDATE分岐における`is_whiteboard`判定を、`old_content.startswith("WHITEBOARD:")`から`get_latest_whiteboard(conn, run_id, phase_id, tid) is not None`へ変更する。SUPERSEDEの「短い理由文はホワイトボードに触れない」という既存の挙動（BL-062）自体は変更しない——変わるのは、その後のUPDATE(edits)が「ホワイトボード済みか」をどこで判定するかのみである。 |
| 影響 | `cela_main.py`（`_commit_agreement_from_tool`）、`tests/test_bl212_supersede_short_reason_orphans_whiteboard.py`。 |
| 関連 BL | [BL-212](back_log/issue_backlog.md#bl-212-supersedeの短い無効化理由文がactiveなdeliverable行のwhiteboardプレフィックスを失わせeditsを永久失敗させる)、BL-062、BL-080、BL-131、BL-206 |

---

### D-187: Deliverable行の`WHITEBOARD:`ポインタは、保護分岐で「維持」するのではなく毎回「再生成」する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-213の横断監査で、BL-212の修正（`is_whiteboard`の判定をwhiteboard_drafts直接参照へ変更）が不完全だったことが判明した。判定は直ったが、その判定を使う保護分岐の中身が`content = old_content`のままだったため、一度BL-212の短文行（WHITEBOARDプレフィックスを失った行）が生まれると、以降の全ての更新へ短文がコピーされ続け、`agreements`側は永久にポインタを取り戻せなかった。同型の問題が`decision_extractor_node`のフォールバック経路にも残っていた。保護分岐が何を書くべきかをどう決めるか。 |
| **決定理由** | 「既存の内容を維持する（`old_content`をそのままコピーする）」という発想は、`old_content`が常に正しいポインタであることを前提にしている。しかしBL-212が示した通り、その前提はSUPERSEDEの用途分岐ひとつで崩れる。一方、`is_whiteboard`が真であることは「whiteboard_draftsに(phase_id, task_id)の実体が存在する」ことと同値であり、**そのときポインタの正しい値は`WHITEBOARD:{phase_id}:{task_id}`であることが機械的に確定する**。ならば過去の値を引き継ぐ理由は無く、毎回再生成する方が単純かつ堅牢である。さらにこの選択には副次効果があり、**過去のrunで既に生まれてしまった汚染行が、次の更新で自動的に修復される**——修復用の一回限りのマイグレーションを書かずに済む。D-186（whiteboard_draftsを権威とする）を、判定だけでなく書き込む値にも一貫して適用したものと位置づけられる。 |
| 決定内容 | Deliverableの保護分岐（`_commit_agreement_from_tool`の`elif is_whiteboard:`と`decision_what`/`edits`いずれも無い`else`、および`decision_extractor_node`のフォールバック経路）では、whiteboard_draftsに実体が存在する場合、`old_content`の中身に依存せず`f"WHITEBOARD:{phase_id}:{task_id}"`を再生成して書き込む。実体が存在しない場合（＝まだホワイトボード化されていない短文Deliverable）は従来通り`old_content`を維持し、**存在しない実体を指すポインタは決して捏造しない**。フォールバック経路での判定は`entry_type == "Deliverable"`に限定する（非Deliverableへ広げると、同一task_idにホワイトボードがあるだけでDecision/Directiveの本文までポインタ文字列へ差し替わるため）。 |
| 影響 | `cela_main.py`（`_commit_agreement_from_tool`の2分岐、`decision_extractor_node`のフォールバック経路）、`tests/test_bl212_supersede_short_reason_orphans_whiteboard.py`。 |
| 関連 BL | [BL-212](back_log/issue_backlog.md#bl-212-supersedeの短い無効化理由文がactiveなdeliverable行のwhiteboardプレフィックスを失わせeditsを永久失敗させる)（追補）、[BL-213](back_log/issue_backlog.md#bl-213-agreements-decision_extractor-周辺の構造化フィールドの無条件信頼横断監査f1f7)（F2・F5）、BL-206、BL-131 |

---

### D-188: 統合時のDeliverable本文解決も whiteboard_drafts を権威とし、ポインタ形式でない行は「汚染」と「正当な短文」を実体の有無で区別する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-213のF1で、`integrator_node`が承認済みDeliverable行の`decision_what`を`FILE_PATH:`でも`WHITEBOARD:`でもないときそのまま最終統合文書へ出力していることが判明した。BL-212の短文汚染（承認撤回の理由文45〜105字）と組み合わさると、27KBの設計本文の代わりに「承認を撤回する」の1行がプロジェクト最終成果物へ載る。しかも従来の`else`分岐は正常系として扱われるため警告が一切出ず、run全体が無駄になったことに最後まで気づけない。D-187で書き込み側の汚染源は塞いだが、読み取り側をどう扱うか。 |
| **決定理由** | D-187で汚染源は塞いだものの、それは**これから書かれる行**にしか効かない。過去のrunで既に生まれた汚染行は`agreements`テーブルに残り続けるため、読み取り側にも保険が要る——特にF1は「実害が最大かつ発見が最も遅れる」欠陥であり、最終成果物が壊れていることに気づけないという性質上、フェイルセーフを二重に置く価値がある。一方で「ポインタ形式でなければ常に異常」と決めつけるのは誤りである。200字以下でホワイトボード化されなかった短文Deliverable（BL-180/H2の正当な経路）が実在し、その場合`decision_what`自体が実本文だからだ。両者を人間の判断や文字数のヒューリスティックで区別しようとすると必ず誤検知が出るが、**「そのtask_idにwhiteboard_draftsの実体があるか」という機械的な問いで完全に区別できる**——実体があるのに`decision_what`がポインタでないなら、それは論理的に汚染以外あり得ない。これはD-186（whiteboard_draftsを権威とする）をそのまま読み取り側へ適用したものである。 |
| 決定内容 | 統合時のDeliverable本文解決を`_resolve_deliverable_content_for_integration`へ切り出し、次の優先順位で解決する。①`FILE_PATH:`ならファイルを読む、②`WHITEBOARD:`ならポインタ内のphase_id/task_idで引き、失敗したらagreements行自身のtask_idで再試行する、③ポインタ形式でない場合、当該task_idにwhiteboard_draftsの実体が**あれば**汚染行と判断して実本文を復元し、**無ければ**未昇格の短文Deliverableとして`decision_what`をそのまま本文とする。復元時・ファイル欠損時・ホワイトボード欠損時はいずれもログへ警告を出力する（F1の核心は「警告が一切出ないこと」だった）。あわせて、要素不足のポインタ（例：`"WHITEBOARD:"`）が`split(":", 2)`の3要素直接アンパックで`ValueError`となりrun最終段の`integrator_node`ごと落としていた問題も、agreements行のphase_id/task_idへのフォールバックで解消する。 |
| 影響 | `cela_main.py`（`_resolve_deliverable_content_for_integration`新設、`integrator_node`）、`tests/test_bl213_f1_integrator_content_resolution.py`。 |
| 関連 BL | [BL-213](back_log/issue_backlog.md#bl-213-agreements-decision_extractor-周辺の構造化フィールドの無条件信頼横断監査f1f7)（F1）、[BL-212](back_log/issue_backlog.md#bl-212-supersedeの短い無効化理由文がactiveなdeliverable行のwhiteboardプレフィックスを失わせeditsを永久失敗させる)、BL-180、BL-131 |

---

### D-189: LLM出力の空文字は例外ではなく常態とみなし、フォールバックを書く前に後続処理への影響を全て追跡することをAGENTS.md §13として恒久ルール化する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-206・BL-210・BL-211・BL-212の4連続バグと、それらを受けたBL-213の横断監査により、この プロジェクトで繰り返し発生している障害の大半が「LLMが返す構造化フィールドが必ず期待した形で埋まっている」という前提に立った分岐と、その前提が崩れたときのフォールバック設計の甘さに起因すると判明した。ユーザーは「全体的にnullチェックが適当すぎる設計をしているわけですね」と本質を指摘したうえで、個別修正だけでなく**教訓としてAGENTS.mdおよび関連ドキュメントへ明文化する**ことを指示した。何をどのレベルのルールとして残すか。 |
| **決定理由** | 4件の障害はいずれも「発見された1経路だけを直す」形で個別に修正され、そのたびに別経路で同型の障害が再発した。原因はコードの欠陥そのものより、**設計時の思考手順が明文化されていなかったこと**にある——`.get(key, default)`が空文字を貫通するという言語仕様レベルの落とし穴も、フォールバック値が下流で何を引き起こすかを追跡する手順も、暗黙知のままだった。暗黙知はセッションをまたいで失われ、AIが主導する開発ではとくに失われやすい（AGENTS.md §4-9で「属人化はAIが決定に関与するほど複合的なリスクになる」と既に規定した問題の別形態である）。したがって、個別のBL修正や`decision_log.md`のD-xxx（特定の判断の記録）ではなく、**毎セッション読み込まれるAGENTS.mdの恒久ルール**として置くのが正しい層である。あわせて、単なる注意喚起（「空文字に気をつけよ」）では行動が変わらないため、①言語仕様の落とし穴の明示、②フォールバックを書く前に答えるべき5つの問い、③権威あるストアを優先する原則、④書き込み経路間の検証対称性、⑤クラス単位で直す規律、⑥マージ前チェックリスト、⑦実インシデント表、という**実行可能な手順**の形にした。特に②と⑦は、AIが「この場では動く」フォールバックを安易に書くことを構造的に抑止する。 |
| 決定内容 | AGENTS.mdへ新規セクション **§13「Defensive Handling of LLM-Produced Structured Data (CRITICAL)」** を追加する（既存§1〜§12の番号は変更せず末尾へ追加し、§5へ相互参照を張る）。骨子は次のとおり。**前提**：LLMはどのフィールドについても、それまで毎回正しく埋めていたとしても、いつでも空文字を返しうるし省略しうる。これは稀な例外ではなく常態である。同じ扱いを、JSONパース失敗時のフォールバック・リトライ層のスタブ・切り詰められたツール結果など、あらゆる欠損しうる境界を通った値へ適用する。**§13.1** `.get(k, default)`はキー欠落時にしかdefaultを使わない。空文字を通したくない箇所は`.get(k) or default`にする。**§13.2（本節の中核）** `""`・「現在の値」・既定enum・パース失敗時のスタブ、いずれのフォールバックを書く場合も、**その値の全消費者を追跡し、システムが静かに壊れず安全に劣化することを確認してから書く**。追跡時に答えるべき問いを5つ明示する（誰が後で読むか／各消費者で何が起きるか／失敗は可視か静かか／破損値は永続化されるか／より権威ある情報源はないか）。確信を持って答えられないならフォールバックを書かず、明示的に拒否するかユーザーへ確認する。**§13.3** 文字列の形から状態を判定せず、権威あるストアへ問う。derived表現を復元するときは前の値をコピーせず権威から再生成する（既存記録の自動修復になる）。**§13.4** 同じ状態への書き込み経路が複数あるなら、全経路で同じ不変条件を強制する。**§13.5** 同種の欠陥を見つけたら、同じ行・同じdict・同じ経路の兄弟フィールドまで検査し、クラス単位で直す。**§13.6** マージ前チェックリスト8項目（最後の項目は「修正をリバートすると実際に失敗する回帰テストを追加したか」）。**§13.7** 実インシデント表（BL-206/210/211/212/213）と横断監査へのリンク。 |
| 影響 | `AGENTS.md`（§13新設、§5へ相互参照追加）。以降の全セッションのコーディング規律に適用される。 |
| 関連 BL | [BL-213](back_log/issue_backlog.md#bl-213-agreements-decision_extractor-周辺の構造化フィールドの無条件信頼横断監査f1f7)、[BL-206](back_log/issue_backlog.md#bl-206-write_agreementのedits照合が実際には空のホワイトボード内容に対して行われ本来一致するはずのold_textが繰り返し不一致になる)、[BL-210](back_log/issue_backlog.md#bl-210-_resolve_task_transitionがadvances_to_phase_id省略時にcurrent_phaseへ決め打ちしフェーズをまたぐ遷移を常に拒否する)、[BL-211](back_log/issue_backlog.md#bl-211-bl-139の遷移補完がdirectiveのtask_idが空文字の場合に空振りしタスク切替が永久に成立しない)、[BL-212](back_log/issue_backlog.md#bl-212-supersedeの短い無効化理由文がactiveなdeliverable行のwhiteboardプレフィックスを失わせeditsを永久失敗させる) |

---

### D-190: 開発を通じて得た教訓を、AGENTS.md §14〜§18として「失敗の履歴が根拠として明示された規律」の形で恒久化する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | D-189でLLM出力の防御的取り扱いを§13として明文化した直後、ユーザーが「この開発を通して、他にagents.mdに書くべき教訓やインストラクションを調査してまとめ、追記してください」と、単発の教訓ではなく**開発全体からの体系的な抽出**を指示した。`decision_lineage.md`の147論点（うち明示的な**教訓**記述22件）、`decision_log.md`のD-001〜D-189、`issue_backlog.md`のBL-001〜BL-213、および運用メモを調査対象として、§13でカバーされない再発パターンを洗い出し、どこまでを恒久ルール化するかを決める。 |
| **決定理由** | 調査の結果、§13（LLM出力の空文字ドリフト）とは**独立した再発クラス**が複数存在することが確認できた。最大のものは「同じ規則が複数箇所に書かれ、どれかが更新漏れする」パターンで、これはD-163（督促集合と停滞集合の述語不一致）・D-169（抑止を両側に置く必要）・D-179（スキーマ説明とノードプロンプトの乖離）・D-182（要求経路が3つあり2つしか塞いでいなかった）・BL-207（プロンプト指示と機械ゲートの不一致）と、少なくとも5回、異なる文脈で繰り返されていた。次に多いのが診断の誤りで、表層的なパターン一致で原因を断定した結果、3回連続で異なる真因を推定し直した事例（BL-196→BL-197→D-169）がある。これらは§13と同様に「暗黙知のままではセッションをまたいで失われる」性質を持つ。**書く形式については、D-189で採った「実行可能な手順」の方針をさらに一歩進め、各規則に必ずそれを生んだ実インシデント（BL/D番号）を併記することにした**——抽象的な原則は読み飛ばされるが、「これを守らなかったときに実際に何が起きたか」が併記されていれば、規則の重みが具体的に伝わり、かつ後から規則の妥当性を検証し直せる（規則そのものが検証可能なlineageを持つ、というCELAの中核思想の自己適用でもある）。あわせて、これまでClaude固有の記憶にのみ保持していた運用知見（テスト実行のcadence、`pytest -k`の部分一致による誤除外、gitベースライン検証、コミット頻度）もAGENTS.mdへ移した——ユーザーはCline等の別AIツールにも独立レビューを依頼しており、AGENTS.mdは全ツールが読む唯一の共有規約層だからである。 |
| 決定内容 | AGENTS.mdへ§14〜§18を追加する（既存§1〜§13の番号は変更せず末尾へ追加し、§5へ相互参照を張る）。**§14 Grounding a Diagnosis in Evidence**：表層パターン一致は診断ではない／値や要求は「最初に生み出した主体」まで遡る／期待されるログが出ていないことは証拠である／チェックポイント復元はDBを巻き戻さない／稼働中のrunは動き続ける。**§15 Single Source of Truth for Rules and Invariants**：1つの規則は1箇所／ガードを完成と宣言する前に発火源を全列挙する（部分的防御は探索を止めるため無防備より危険）／機械的検証はエージェントの自己申告に優先する／消費経路の無い記録は機構ではない／ドリフトしうる閾値よりドリフトしない不変条件を選ぶ。**§16 Proposing, Reviewing, and Reporting Honestly**：ユーザーの提案であっても軽い代替案を検討してから実装する／レビュー指摘は実コードで再現してから受け入れる／わからないことはわからないと書く／過去の決定は原文を引用する（記憶で再構成しない）／大きな改修の前に「その作業は必要か」を問う／バグを直すことと同種のバグを防ぐ体制を作ることは別の作業であり後者を自ら提案する。**§17 Testing & Verification Discipline**：回帰テストは修正をリバートすると失敗しなければならない（複数箇所なら箇所ごとにリバート）／モックテスト通過は動作の証拠ではない／テスト実行cadenceと全件実行コマンド／`-k`に部分一致文字列を使わない／計算は必ず実行する。**§18 Working Tree, Git, and Live-Run Hygiene**：実装前にgitベースラインを検証する／マイルストーンで自発的にコミットを提案する／run状態の破壊的修正の前にバックアップと承認。 |
| 影響 | `AGENTS.md`（§14〜§18新設、§5へ相互参照追加）。以降の全セッション・全AIツールの作業規律に適用される。 |
| 関連 BL | [BL-213](back_log/issue_backlog.md#bl-213-agreements-decision_extractor-周辺の構造化フィールドの無条件信頼横断監査f1f7)、および§14〜§18が引用する全BL/D（BL-043・BL-091・BL-136・BL-145・BL-154・BL-161・BL-163・BL-168・BL-176・BL-179・BL-180・BL-181・BL-193・BL-196・BL-197・BL-206・BL-207・BL-210・BL-211、D-163・D-169・D-177・D-179・D-182・D-189） |

---

### D-191: decision_extractorのフォールバック経路にも検証層を置き、破棄の前にプロンプト追記による自己修正の機会を与える

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-213のF3で、`agreements`への書き込み経路が2本あり検証の厚みが6層（`write_agreement`ツール経路）と0層（`call_decision_extractor`→`decision_extractor_node`のフォールバック経路）という極端な非対称になっていることが判明した。BL-206（`phase_id`）とBL-211（`task_id`）で個別に直したのは、同じ行に並ぶ6フィールドのうち2つだけである。この経路をどう扱うか——調査記録§5では(a)検証層を追加／(b)`_write_agreement_impl`経由に統一／(c)読み取り専用へ縮退、の3案を提示していた。 |
| **決定理由** | 実測が選択を決めた。この経路は全ログ591ターン中271回（46%）発火し、実runのagreements 177行中44行（25%）を書いている**常用経路**である。したがって(c)（読み取り専用へ縮退）は決定記録の4分の1を失う——しかもこの経路が動くのは「LLMがツールを使わなかったターン」＝既に何かおかしいターンであり、**見えなくなると困る場面でちょうど見えなくなる**。(b)（ツール経路へ統一）は根本的だが、BL-146（current_task_id一致ゲート）とBL-169（ロール権限）が`proposed_by="User"`で他タスク向けに書く正当な抽出まで弾くため、影響範囲が大きすぎる。よって(a)を採る。不正項目の扱いについては、常に破棄すると`proposed_by`が空なだけの正当な記録まで失われ、常に正規化すると`entry_type=""`→`"Decision"`のような誤った分類の行がDBに入り**BL-206の孤児化と同じ結果**になる。したがって同一性に関わるフィールドのみ破棄するハイブリッドが妥当である（ユーザー選択）。さらに重要な点として、ユーザーの「破棄後は他のツール失敗時と同じくLLMの自己修正にゆだねる」という期待は**そのままでは成立しない**——`write_agreement`等のツール失敗は`{"success": False, "error": ...}`がツールループ内でモデルへ返り同一ターンで修正できるが、`call_decision_extractor`はツールではなく**ノード**であり、結果をモデルへ返すフィードバックchannelが存在しない。既存のBL-160リトライも同一プロンプトの再送でしかなく、何が悪かったかを一切伝えていなかった。破棄だけを実装すると情報が黙って消えるため、自己修正機構の新設をセットにする必要がある。 |
| 決定内容 | (a)を採用し、次の3点を実装する。**①自己修正**：`_query_and_parse_with_retry`へ`validator`フック（`(ok, llm_facing_message)`を返す）を追加し、検証不合格時は理由とあるべき出力をプロンプトへ追記して再問い合わせする。リトライを使い切った場合はパース自体は成功しているため`parse_failed=False`で最後の出力を返し、破棄／正規化の判断は呼び出し元へ委ねる（フェイルクローズの方針は呼び出し元ごとに異なるため）。**②ハイブリッドのフェイルクローズ**：`entry_type`／`action_type`／UPDATE時の`target_topic`が不正ならその項目を破棄、`status`／`topic`／`proposed_by`は既定値へ正規化して記録は残す。minorのみではvalidatorを不合格にしない（LLM呼び出しを浪費しないため）。**③警告文**：LLM向けには結果まで書く（「entry_typeが正しくないとDBの検索から永久に発見できない孤児レコードになる」）。人間向けには失われるものと回復手段を明記する（「この項目の内容は今回記録されません — 次ターン以降に再抽出されるか、write_agreementツールで直接記録する必要があります」）。なお`target_topic`はUPDATE時に**全entry_typeで必須**とする——ツール経路のBL-131ガードはDeliverableを除外しているが、あちらはDeliverableをphase_id/task_idで特定するのに対しこの経路はtopic+entry_typeの線形探索で特定するため、Deliverableでも`target_topic`が同一性の要だからである。 |
| 影響 | `cela_main.py`（`_query_and_parse_with_retry`へvalidator追加、`_check_extracted_event`／`_validate_extracted_events`／`_sanitize_extracted_events`新設、`call_decision_extractor`の配線）、`tests/test_bl213_f3_extractor_validation.py`、`tests/test_bl182_decision_extractor_no_deliverable_full_text.py`（スタブの引数追随）。 |
| 関連 BL | [BL-213](back_log/issue_backlog.md#bl-213-agreements-decision_extractor-周辺の構造化フィールドの無条件信頼横断監査f1f7)（F3）、[BL-206](back_log/issue_backlog.md#bl-206-write_agreementのedits照合が実際には空のホワイトボード内容に対して行われ本来一致するはずのold_textが繰り返し不一致になる)、[BL-211](back_log/issue_backlog.md#bl-211-bl-139の遷移補完がdirectiveのtask_idが空文字の場合に空振りしタスク切替が永久に成立しない)、BL-131、BL-146、BL-160、BL-169、D-189（AGENTS.md §13/§15.4） |

---

### D-192: 「現在のタスクは何か」の解決口を`_task_id_from`一本に集約し、生の`current_task_id`は「まだ遷移していない」を判定する箇所にのみ残す

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-214で、`current_task_id`の実効解決（BL-146の`_effective_current_task_id_from`＝`current_phase`先頭タスクへのフォールバック）が`write_agreement`のゲート経路にしか適用されておらず、BL-177/178の承認検証と`write_issue`のtask_id付与が各フェーズ先頭タスクで壊れていた。生の`state["current_task_id"]`を読む箇所は全35箇所ある。どこまでを実効解決へ寄せるか、そして機械的な一括置換をしてよいかを決める。 |
| **決定理由** | 一括置換は誤りである。`current_task_id`が空文字であることには**2つの異なる意味**があり、コードはそのどちらを問うているかで分かれる——(A)「現在どのタスクを実行中か」（空文字は答えになっていない。実効解決すべき）と(B)「まだ一度もタスク遷移が起きていないか」（空文字そのものが答え。実効解決すると情報が失われる）。全35箇所を1件ずつこの軸で分類したところ、28箇所が(A)、7箇所が(B)だった。(B)を実効解決へ寄せると、`_resolve_task_transition`の`departing_task_id`が初回遷移で「先頭タスクから離脱する」と誤認されBL-125/176ゲートが誤発火し、`_maybe_resume_forward_focus`のBUG-2検知（空文字であること自体を異常シグナルに使う）は永久に発火しなくなる。**[REJECTED]** 「`_resolve_task_transition`に初期値として先頭タスクを書き込ませれば全経路が生の値のままでよくなる」案は採らない。BL-024が書き手を単独に限定した設計意図（誰が現在タスクを動かしたか追跡可能にする）を壊し、かつ(B)の判定が不可能になるため。実装中に、`_effective_current_task_id_from`自身が**`current_phase`を持たない簡易stateで、明示的に設定済みの`current_task_id`を取りこぼしていた**ことが既存テスト4件の失敗により判明した。全経路の唯一の解決口へ昇格させる以上「既知の値を失う」ことは許されない（AGENTS.md §13.2 問2）ため、phase由来の解決が空のときに限り生の値へ退避する形へ修正した。順序はphase由来を先に保った——BL-146が確立した「`current_task_id`が`current_phase`の一覧に無ければ先頭タスクへ寄せる」挙動にBL-190の計画再構成が依存しているためである。 |
| 決定内容 | `_task_id_from(state)`を`_effective_current_task_id_from(state) or _CURRENT_TASK_ID`とし、TOOL_DISPATCH経由の全ツールが自動的に実効解決を得る形にする（最小の変更で最大の被覆）。(A)に分類した28箇所を実効解決へ変更し、(B)の7箇所は据え置いたうえで**すべてに`[BL-214][例外]`コメントで「なぜ生の値が正しいか」を明記する**——例外が無記述だと、次に横断監査する者が「直し漏れ」と誤認して壊すため。`_effective_current_task_id_from`は`_get_current_task(state).get("task_id", "") or state.get("current_task_id", "")`とする。あわせて`_is_task_completed`が空のtask_idで呼ばれた場合に警告を出す（従来は黙って`False`を返し、DBの中身に関わらず機能が無効化されていることが誰にも見えなかった）。 |
| 影響 | `cela_main.py`（`_task_id_from`／`_effective_current_task_id_from`／28箇所の呼び出し／7箇所の例外コメント／`_is_task_completed`の警告）、`tests/test_bl214_effective_task_id_resolution.py`（新規13件）、`tests/test_bl148_orchestrator_tool_loop.py`（実効アクセサへの追随）。 |
| 関連 BL | [BL-214](back_log/issue_backlog.md#bl-214-current_task_idの実効解決が一部経路で未適用で各フェーズ先頭タスクの承認検証とissueのtask_id付与が壊れる)、BL-146（導入元）、BL-024（書き手の限定）、BL-177・BL-178（壊れていた検証機構）、BL-190（計画再構成の依存先）、BL-191（BUG-2検知）、D-190（AGENTS.md §15.1/§15.2） |

---

### D-193: `write_issue`のtask_idはLLMの申告より現在タスクを優先する（`write_agreement`とは非対称にする）

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-214で`write_issue`が`args["task_id"]`を完全に無視し、実runの9件すべてのissueが`task_id=''`で保存されていたことが判明した。BL214基本設計§4.3では`write_agreement`（BL-040）と同型の`args.get("task_id") or task_id`＝**args優先**にすることを提案していた。「同じ規則が2つのツールで別々に実装され片方だけが堅牢」という§15.1の是正として自然に見えたが、実装後のリバート検証で再検討が必要になった。 |
| **決定理由** | args優先には**遷移ゲート回避の穴がある**。`write_issue`の`task_id`はBL-125の遷移ゲートが「離脱元タスクに未解決issueが残っているか」を判定する鍵であり、申告を無条件に採用すると**LLMが別タスクのtask_idを付けるだけで、自分の離脱元から未解決issueを外して先へ進める**。静かに成立し、もっともらしい結果を返すfail-openであり、AGENTS.md §13.2 問3が明確に禁じている型である。`write_agreement`の`task_id`は**書き込み先の識別子**でありゲートの鍵ではない——だからこそBL-040でargs優先が妥当だった。したがってこれは「規則の不統一」ではなく**役割の違いに由来する正当な非対称**であり、揃えること自体が誤りだった。なおこの穴は、§17.1のリバート検証で「S3をリバートしてもテストが落ちない」ことに気付いたのが発見契機である。リバート検証が回帰の担保だけでなく、**その修正が本当に必要か・正しい形か**を問い直す装置としても働いた。 |
| 決定内容 | `_write_issue_impl`のtask_id決定を3分岐にする。①申告値が実効値と一致→採用、②申告値が実効値と**不一致**→採用せず現在タスクで記録し「別タスクへ委ねたい場合は`action_type='DEFER'`と`defer_to_task_id`を使え」と警告（正規の手段へ誘導する）、③実効解決が**空**（＝実効アクセサの適用漏れが将来再発した場合）→申告値を採用（最後の砦。ただし計画に実在する場合のみ。実在しない申告は採用すればどのゲートからも参照されない迷子issueになるため拒否する）。これにより、D-192の一元化が将来また漏れても**LLMが明示していれば壊れない**という二重の防御を保ちつつ、ゲート回避は成立しない。 |
| 影響 | `cela_main.py`（`_write_issue_impl`）、`tests/test_bl214_effective_task_id_resolution.py`。 |
| 関連 BL | [BL-214](back_log/issue_backlog.md#bl-214-current_task_idの実効解決が一部経路で未適用で各フェーズ先頭タスクの承認検証とissueのtask_id付与が壊れる)、BL-040（args優先の先例。役割が違うため踏襲しない）、BL-125（遷移ゲート）、BL-136（DEFER）、D-192、D-190（AGENTS.md §13.2/§17.1） |

---

### D-194: 時刻ベースIDの採番を`_new_record_id`一箇所へ集約し、順序は`rowid`で取る

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-215（`agreements`等のidが`f"AG-{ミリ秒}"`で衝突し`ORDER BY id`の順序が不定になる）は、当初ユーザー判断で「実害はないので後回し」とされていた。しかしBL-214のインシデント再現テスト（初回タスクでDeliverableをApprovedにした直後に`_is_task_completed`が成功と判定すること）が**5回中3回失敗するflaky**になり、原因がまさにこのID衝突だった。BL-214の修正を検証できるようにするために必要となったため、実施可否と範囲を再判断する。 |
| **決定理由** | 「実害はない」という当初の見立ては、**実runでは重複IDが0件だった**という観測に基づいており正しかった。実LLMのレイテンシが連続書き込みを同一ミリ秒に収めないためである。しかしテスト環境ではLLM呼び出しが無く連続書き込みが同一ミリ秒に収まるため、**BL-214の回帰テストが恒久的にflakyになる**。flakyなテストは「失敗しても誰も驚かない」状態を作り、いずれ本物の回帰を隠す。したがって修正の動機は「実害の除去」ではなく「**BL-214の修正を検証可能にすること**」である。範囲については、§6.3の方針（agreementsの`ORDER BY rowid`＋uuidサフィックス）を2点広げた。**①採番の一元化**：`goal_escalations`（`ESC-`）だけが既にuuidサフィックスを持ち、`agreements`/`decisions`/`goal_shift_events`/`plan_drafts`/`goal_drafts`/`scheduling_decisions`/`deliverable_files`が素のミリ秒という状態そのものが、「同じ一意ID採番という規則がテーブルごとにバラバラ」＝§15.1の事例である。テーブル単位で潰すと次に追加されるテーブルで同じ欠陥が戻るため、**採番口を1つにする**形で潰した。**②`issue_log`の順序**：idが`uuid4`のため`ORDER BY id`は挿入順ではなく**実質ランダム順**を返していた。ミリ秒衝突とは症状が違うが「順序を持たない値で並べている」という同じ欠陥クラスであり、AGENTS.md §13.5（インスタンスではなくクラスを直す）に従い6箇所すべてを是正した。既存の重複行（実DB全体で1724行中188行）は遡及修正しない——SQLiteの暗黙rowidが真の挿入順を保持しているため、`ORDER BY rowid`にすれば**読み取り側が既存DBに対しても正しく動く**からである。 |
| 決定内容 | `_new_record_id(prefix)`（`f"{prefix}-{ミリ秒}-{uuid4.hex[:6]}"`）を新設し、`AG-`／`D-`／`GS-`／`PL-`／`ESC-`／`GD-`／`SCHED-`／`DF-`／`AG-MASTER-`のすべてをここへ寄せる。接頭辞は既存のログ表記・`citations`の`AG-xxx`参照との互換のため保つ。`agreements`／`decisions`／`issue_log`を引く全クエリの`ORDER BY id`を`ORDER BY rowid`へ変更する（スキーマ移行不要、`SELECT *`にrowidは含まれないため下流のdictキーにも影響しない——いずれも検証済み）。素のミリ秒採番が再導入されないよう、ソース走査による配線固定テストを置く。 |
| 影響 | `cela_main.py`（`_new_record_id`新設、9箇所の採番、`agreements`/`decisions`/`issue_log`の`ORDER BY` 9箇所）、`tests/test_bl215_record_id_uniqueness_and_ordering.py`（新規8件）、`tests/test_r4_smoke.py`（`max(rows, key=id)`→`rows[-1]`。idの文字列大小は挿入順を表さない）。 |
| 関連 BL | [BL-215](back_log/issue_backlog.md#bl-215-agreementsdecisions等のidがミリ秒生成で衝突しorder-by-idの順序とid参照が不定になる)、[BL-214](back_log/issue_backlog.md#bl-214-current_task_idの実効解決が一部経路で未適用で各フェーズ先頭タスクの承認検証とissueのtask_id付与が壊れる)（発見契機）、BL-084・BL-206・BL-212（`reversed(get_agreements_from_db(...))`経路）、D-190（AGENTS.md §13.5/§15.1/§17.1） |
---

### D-195: 実地調査が必要な暫定値は、DEFERで「後続タスクが解決する」と偽装せず、専用ツールで「人間にしか解決できない」と正直に宣言させ、既存のBL-125ゲートへそのまま乗せる

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが`task_1_1`の暫定値（免許自主返納者数、「市独自統計未公表、task_1_3でヒアリング実施」として`write_issue(DEFER)`で先送り）を見て、実地調査が必要な暫定値へフィードバックを与える機構が要ると指摘した。調査の結果、これは単なる機能不足ではなく、DEFER機構の誤用だと判明した——DEFERは「別のAIタスクが後で解決できる」ことを前提とした仕組みだが、task_1_3も同じAIが実行するため実地ヒアリングは原理的に実行不可能で、AIは「後で解決される」という体裁だけを整えた偽の解決計画を作っていた。あわせて、既存の`ask_user_question`（BL-130）が「User」役（実際は`generate_user_utterance`が演じる発注者AI）にしか届かず、実際の人間には一切届いていないことも判明した。 |
| **決定理由** | 実装の起点は「新しいゲート機構を作ること」ではなく「AIに正直な区別をさせること」だと判断した。DEFERの`defer_to_task_id`は実在するtask_idであることしか検証しておらず、その関連性チェック（受け皿タスクが本当に対応できるか）は`cela_main.py:3625-3630`で「LLM判断/キーワード一致はコスト・非決定性・誤検知が理由」として既に意図的に却下されている。この先例に従えば、新たな「人間にしか解決できない」という区別も、DEFER側に機械的な妥当性検証を追加する形では実装すべきではない——同じ理由（コスト・非決定性）がそのまま当てはまる。代わりに、新規ツール`flag_needs_human_input`に`defer_to_task_id`相当のパラメータを一切持たせず、「AIタスクへの先送り」と「人間への先送り」が同一issue上で混在する余地を構造で無くすことにした。この設計の直接の帰結として、**BL-125の遷移ゲート（`_get_blocking_issues_for_transition`）を1行も変更する必要がなくなった**——新ツールで起票したissueは`defer_to_task_id`が常に空のため、既存SQL（`status='escalated' AND defer_to_task_id IS NULL OR ''`）が`severity='major'`の場合に自然にタスク遷移をブロックし、人間が専用CLIで`status='resolved'`にすれば同じSQLから自然に外れる。新しい検証ロジックを足すのではなく、既存のゲートが正しく機能する条件（`defer_to_task_id`が空であること）を維持したまま、AIに嘘をつかせない設計へ倒したことで、ゲート自体の複雑性が増えないまま正しい挙動が手に入った。回答経路については、`docs/refs/`＋`read_goal_reference`（BL-199）という既存の「人間がファイルを置けばAIが自動的に拾う」経路が既に稼働していたが、ユーザーは「専用CLIで人間が直接書き込む」ことを明示的に選んだ——AIが再確認・再抽出する工程に依存せず、確実に伝わることを優先した判断である。あわせて「各ノードへ人間が回答したことを知らせる通知機構」の追加要望を受け、消費済みマーカーはstate側のフラグではなくDB列（`human_notice_delivered_at`）に持たせることにした。チェックポイント跨ぎでの状態ドリフトを避けるためであり、これはAGENTS.md §13.3（権威は常にDB、派生表現ではなく）の直接適用である。 |
| 決定内容 | ①Expert専用ツール`flag_needs_human_input`（`topic`/`variable_name`/`human_research_prompt`/`description`/`severity`を受け取り、`defer_to_task_id`相当のパラメータを持たない）を新設する。②`issue_log`へ`human_research_prompt`（非空＝フラグ）・`human_variable_name`（回答時に`upsert_verified_fact`へ渡す変数名。設計時に欠落し実装中に追加）・`human_notice_delivered_at`（一度だけ通知の消費済みマーカー）を追加する。③専用CLI`--pending-human-input`/`--answer-human-input`を新設し、後者は`upsert_verified_fact`で`confidence='confirmed'`・`citations=[{"type":"human_field_research",...}]`として確定値を書き込み、対応issueを`resolved`にする（自由記載コメントは既存の`resolution_note`列を再利用）。④`_build_human_input_answered_notice`を、既存のpin текст構築箇所（`_build_escalation_pin_text`等と同じ、`call_expert`/`call_detector`/`generate_user_utterance`の3関数の毎ターン呼び出し）へ追加し、resume専用フックにしない（runが動き続けたまま、別ターミナルでのCLI書き込みも次ターンで拾える）。⑤`citations`の`type`enumへ`"human_field_research"`を追加する（既存の`"user_input"`はUser AI役の発言を指し実際の人間ではないため、混同を避けるため流用しない）。 |
| 影響 | `cela_main.py`（`_ensure_issue_log_human_input_columns`、`FLAG_NEEDS_HUMAN_INPUT_TOOL`／`_flag_needs_human_input_tool_impl`、`TOOL_DISPATCH`配線、`call_expert`のツール一覧、`_flag_needs_human_input_report`／`_answer_human_input`／`_build_human_input_answered_notice`、argparseへの`--pending-human-input`/`--answer-human-input`、citations enum4箇所＋コメント、`WRITE_ISSUE_TOOL`説明文）、`tests/test_bl217_human_in_the_loop.py`（新規20件）。 |
| 関連 BL | [BL-217](back_log/issue_backlog.md#bl-217-実地調査が必要な暫定値へaiがdeferで誤魔化さず正直に人間しか解決できないと宣言し専用cliで人間が回答できるようにするhuman-in-the-loop)、BL-096（Expertへwrite_issueを直接与えない既存方針からの意図的な逸脱）、BL-130（`ask_user_question`が実は人間に届いていなかった発見）、BL-136（DEFERの関連性チェック却下の先例）、BL-125（無改修で機能した遷移ゲート）、BL-199（検討したが採らなかった間接経路）、D-189（AGENTS.md §13.3） |
---

### D-196: task_plannerの暫定係数とtask_plan_reviewerの承認時コメントを、新規ツール・新規権限なしで構造化記録に載せる

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが実run（`run_id=1786457890-3273d6dd`）を調査し「1日の需要8,500人という根拠が見つからない」と指摘した。調査の結果、この数値はtask_1_4が実際に導出したものではなく、task_plannerが計画分解の段階でピーク3時間の外挿という自己流の概算を行い、後続タスクのacceptance_criteriaへ「task_1_4で確定した」という体裁で先に埋め込んでいたことが判明した。task_plan_reviewerは`think`ツール呼び出しの中でこの数値を「derived number, need to check calculation」と自ら疑問視していたが、その指摘は`per_task_comments`としてplan_draftsの「レビュワーからの指摘」セクションへ書き込まれるのみで、`constraint_issue="none"`（承認）の場合はtask_plannerが差し戻し後に`read_plan_draft`で読み返す経路しか存在しないため、実行フェーズのExpert/Detector/User AIには一切届いていなかった（AGENTS.md §15.4: 消費経路のない記録）。ユーザーは当初、①task_plannerへ`upsert_verified_fact`ツールを追加、②task_plan_reviewerへ「差し戻すほどではないが後続タスクへ残すべき懸念」を書ける手段（write_issue等）を追加、という2方針を提案した。 |
| **決定理由** | 提案をそのまま実装する前にコードを精査したところ、両方とも見た目より軽い実装で足りることが判明した。①`upsert_verified_fact`はどのロールにも存在しない独立ツールで、実体は`write_agreement`の`confirmed_variables[]`パラメータ経由でのみ内部関数として呼ばれる（`cela_main.py:3430-3444`）。task_plannerは既に`write_agreement`を保有しており（BL-095、指示10で分解全体の判断根拠を記録する用途に既に使用）、`confirmed_variables`のvariable_name一致チェックは`current task`が無いケース（task_plannerには「現在のタスク」が無い）でも既存のガード（`cela_main.py:3363-3389`）に抵触しないことをコードで確認した。新規ツール追加ではなく既存指示の拡張で足りると判断した。②task_plan_reviewerへの`write_issue`付与は、`_check_issue_permission`（`cela_main.py:3019-3025`）を見るとDEFERは`user`ロールのみに限定されており、これはBL-136で「明示的な先送り判断はUser AIのみが行う」と確立した意図的な設計原則である。task_plan_reviewerにDEFER権限を与えることはこの原則を破る変更であり、AGENTS.md §7相当の重さを持つと判断し、より軽い代替を優先した（AGENTS.md §16.1: ユーザー提案でも軽い代替を提示する）。代替として、task_plan_reviewerが**既に**`per_task_comments`で書き込んでいる「レビュワーからの指摘」セクションは、単に自動注入されていないだけであり、BL-082が「先送り事項」セクションに対して確立済みの自動注入パターン（`_get_deferred_notes_text`→`call_expert`/`call_detector`/`generate_user_utterance`の3箇所）をそのまま横展開すれば、新規ツール・新規権限なしで消費経路の欠落だけを塞げると判断した。 |
| 決定内容 | ①task_plannerのプロンプト（指示6・指示10）を拡張し、acceptance_criteria/descriptionの計算で使った派生値・暫定係数のうち、いずれかのタスクのowns_variablesに対応するものは、同じ`write_agreement`呼び出しの`confirmed_variables`へ`confidence="provisional"`・`citations type="expert_calculation"`として登録するよう指示した（テキスト埋め込みのみではアンカリングリスクが残る旨も明記）。②`_get_reviewer_comments_text`を新設し、plan_draftsの「レビュワーからの指摘」セクションを`_get_deferred_notes_text`と同型の手順で抽出、`_build_task_scope_context`へ`reviewer_comments_text`として追加、`call_expert`/`call_detector`/`generate_user_utterance`の3箇所（BL-082と同じ配線）へ自動注入した。新規ツール・`ALLOWED_ISSUE_ACTIONS_BY_ROLE`への新規ロール追加のいずれも行っていない。 |
| 影響 | `cela_main.py`（`call_task_planner`プロンプト指示6・10、`_get_reviewer_comments_text`新設、`_build_task_scope_context`、`call_expert`/`call_detector`/`generate_user_utterance`の3箇所）、`tests/test_bl219_reviewer_comments_and_planner_provisional.py`（新規10件、うち1件は`write_issue`への新規権限付与が行われていないことの回帰防止テスト）。 |
| 関連 BL | BL-219、BL-082（先送り事項の自動注入の前例）、BL-087 Stage2（task_plan_reviewerのper_task_comments配線）、BL-095（task_plannerのwrite_agreement経路）、BL-136（DEFERはUser AIのみという既存原則、今回は変更しなかった） |
---

### D-197: scratch_concernsの最終出力前チェックは、新規フィールドを増やさず既存の懸念欄への導線を一元的な指示で繋ぐ

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | BL-219の調査で、task_plan_reviewerが`think`の`scratch_concerns`で「約8,500人/日は要検算」という懸念を追跡していたにもかかわらず、最終出力までにそれが構造化記録として一切外部化されなかったことが判明した。ユーザーは「thinkと`write_issue`の両方が使えるノードは最終出力前に整理してissue起票、使えないノードは最終出力で懸念を示す」という方針を指示した。`think`ツールを持つ呼び出し箇所は`call_task_planner`・`call_orchestrator`・`call_expert`（本体・light_system_prompt）・`call_detector`（2モード）・`call_resource_arbiter`・`call_facilitator`（2分岐）・`call_integrator`・`call_reviewer`・`generate_user_utterance`（Stage1-4＋特殊モード）・`call_goal_essence_analyst`・`call_task_plan_reviewer`の計16箇所に及ぶ。 |
| **決定理由** | 16箇所それぞれに新規の「懸念欄」を追加する案は検討したが、調査の結果、大半のノードには既に「気づき・懸念」を書ける出力フィールドが存在していた（`call_detector`の`observations`、`generate_user_utterance` Stage1の`domain_concerns`、Stage2の`remaining_concerns`、Stage3の`approval_reason`、`call_task_plan_reviewer`の`observations`、`call_goal_essence_analyst`の`feasibility_notes`、`call_resource_arbiter`の`rationale`、`call_integrator`の`details`、`call_reviewer`の`feedback`、`call_orchestrator`の`reason`）。新規フィールドを増やすことは、同じ目的の欄が2つ併存する重複（AGENTS.md §15.1）を生むだけだった。そこで、既存フィールドへの導線を一元的な指示文（共有ヘルパー）で繋ぐ方針とした。ヘルパーは`escalation_tools`（`write_issue`・`escalate_premise_concern`・`flag_needs_human_input`等、ノードが実際に持つ懸念専用ツール）の有無で分岐し、無ければ`final_output_field`名を直接指示する。これによりAGENTS.md §15.1（単一の場所で規則を管理）を満たしつつ、16箇所という広い適用範囲でも1関数を直せば文言が揃う。適用範囲については、「一部のノードだけに指示を入れると、指示を入れなかったノードで同じ欠陥（懸念の消失）が再現するだけ」という判断（AGENTS.md §15.2）から、`think`を持つ全ノードへ機械的に適用した（`seed_entities_from_goal`のみ、懸念概念が薄い最小限ノードとして意図的に除外）。実装中、`generate_user_utterance`の特殊モードへの挿入がBL-185の「差し戻し通知ブロックはtrailingの最後」という既存不変条件を破っていることをフルスイートで検出し、挿入位置を差し戻し通知ブロックの手前へ修正した——これは新しいルールを追加する際に既存の不変条件を機械的に確認する必要性を示す実例である。 |
| 決定内容 | `_scratch_concerns_closure_instruction(final_output_field, escalation_tools="")`を「BL-115共有プロンプト定型文」セクションへ新設し、thinkツールを持つ16箇所全てのプロンプト末尾（ツール一覧の直後、Return ONLY JSONの直前）へ挿入する。新規ツール・新規フィールドは一切追加しない。 |
| 影響 | `cela_main.py`（`_scratch_concerns_closure_instruction`新設、`call_task_planner`・`call_orchestrator`・`call_expert`・`call_detector`・`call_resource_arbiter`・`call_facilitator`・`call_integrator`・`call_reviewer`・`generate_user_utterance`・`call_goal_essence_analyst`・`call_task_plan_reviewer`の各プロンプト）、`tests/test_bl220_scratch_concerns_closure.py`（新規15件）。 |
| 関連 BL | BL-220、BL-219（同型の消費経路欠落）、BL-140（scratch_concernsの初出）、BL-185（差し戻し通知ブロックの位置不変条件、実装中に回帰を検出・修正） |
---

### D-198: web_fetchのダウンロード容量上限を8MB→50MBへ引き上げ、巨大文書はgrepで部分読みさせる

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが「大容量でもとりあえずDLし、markitdownで変換。grepで必要個所の前後を読めるようにしたい」と要望。調査の結果、変換後の全文は既に`write_cache`が切り詰めなしで保存済みだったが、①ダウンロード段階の`_MAX_FETCH_BYTES`（8MB）超過で全体が拒否される、②`read_reference_file`に本文全体を検索する機能が無く`keyword`はSource URL行専用、の2点が実際のボトルネックだった。`_MAX_FETCH_BYTES`はメモリ安全境界でありAGENTS.md §7の「重要な定数」に該当するため、新上限をユーザーへ確認した。 |
| **決定理由** | 上限を完全撤廃（無制限）にはしなかった——メモリ・変換時間の青天井なリスクを許容する変更は、ユーザーが「とりあえずDL」で意図した「実務上十分な大きさ」を超えて安全側の設計原則（DoS耐性）を犠牲にする。ユーザーに50MB/100MB/実質無制限の3択を提示し、50MBの選択を得た。50MBはダウンロード段階の上限に過ぎず、変換後の全文は既存通り`write_cache`で無制限に保存されるため、実質的な閲覧可能量はこの引き上げで制約されない。ただし上限を上げるだけでは、モデルが受け取れる分量（`_MAX_OUTPUT_CHARS`/`_MAX_READ_REFERENCE_CHARS`、いずれもトークン経済のための既存の切り詰め）とのギャップが広がるだけで実用にならないため、`read_reference_file`に`grep`（`grep -C`相当、マッチ行＋前後文脈のみ返す）を新設し、大容量文書でも必要箇所だけを低コストで読める経路を同時に用意した。ダウンロードの容量上限と、モデルが読む分量の上限は別の懸念（前者はサーバー側リソース、後者はトークン経済）であり、後者を先に解決しないまま前者だけ緩和すると「取得はできるが読めない」状態になる、という整理に基づく。 |
| 決定内容 | ①`_MAX_FETCH_BYTES`を8MB→50MBへ引き上げ、`_REQUEST_TIMEOUT_SECONDS`を10秒→30秒へ延長（大容量DLがタイムアウトしないため）。②`read_reference_file`に`grep`パラメータ（`path`必須）を追加し、`_grep_with_context`でキャッシュ全文からマッチ行＋前後3行を返す（隣接窓は統合、30件超は先頭30件のみ＋注記）。 |
| 影響 | `web_tools.py`（`_MAX_FETCH_BYTES`・`_REQUEST_TIMEOUT_SECONDS`・`_grep_with_context`新設・`read_reference_file_handler`）、`cela_main.py`（`READ_REFERENCE_FILE_TOOL`スキーマ）、`tests/test_bl184_web_tools.py`（新規8件）。 |
| 関連 BL | BL-221、BL-208（`_MAX_FETCH_BYTES`の前回改訂）、BL-216（キャッシュ候補のpreview、grepと相補的な「開かずに選ぶ」経路） |
---

### D-199: 人間の監査UXは、本文への注釈埋め込みではなく、DBを直接読む別ビュー（CLIレポート）で提供する

| 項目 | 内容 |
|------|------|
| 状態 | `decided` |
| 論点 | ユーザーが「成果物の数字・内容を5W1Hで検査できない、今はログをClaudeに解析させている」と課題提起し、「一文ずつmdの隠し文字で経緯注釈をつけまくるか」という案を自ら提示した。 |
| **決定理由** | 隠し文字による本文注釈は却下した。理由は、CELAが過去に繰り返し踏んできた「文字列一致・位置ベースの注釈が本文編集で追従できず腐る」という脆さ（BL-074/076/081/202の一連のインシデント）と全く同じ構造を持つためである——Expertがwhiteboardを`edits`（old_text/new_text）で差分編集するたびに、埋め込んだ注釈も手動で追従させる必要があり、ズレれば注釈自体が嘘をつく。一方、監査に必要な情報（誰が・いつ・どのタスクで・何を・なぜ・出典）は、`verified_facts`（reason/citations/confidence）と`agreements`（reason_why/citations）に既に構造化保存済みであり、本文とは独立している。ここから機械的に（LLM呼び出しなしで）別ビューとして取り出せば、本文の編集頻度に一切影響されず、常に正確である。「リアルタイムにできるか」という追加質問には、`cela.db`が既にWALモード（`get_db_connection`）で動作しており、run実行中でも別プロセスが読み取り専用で安全に同時アクセスできることを回答した。これはBL-217の`--pending-human-input`が既に実証済みのパターンであり、新たな並行性設計は不要だった。「常時更新される画面」は、CELA側に常駐プロセス・Webダッシュボードを持たせるのではなく、シェル側の`watch`等に委ねる方針でユーザーと合意した——CELA本体の責務を「正確な単発スナップショットを返すこと」に留め、監視の周期制御は呼び出し側に任せる、という役割分担である。 |
| 決定内容 | `_audit_report(conn, run_id, task_id="", phase_id="")`を新設し、`verified_facts`/`agreements`をtask_id優先・phase_idフォールバックで絞り込んで5W1H形式に整形する。CLIフラグ`--audit-report RUN_ID [--task-id T] [--phase-id P]`として公開し、BL-217と同じ「別プロセスがsqlite fileへ直接アクセスするだけ、LangGraphのstate/checkpointには触れない」設計に揃える。 |
| 影響 | `cela_main.py`（`_audit_report`新設、CLIフラグ追加、読み取り専用CLI分岐のstdout utf-8化）、`tests/test_bl222_audit_report.py`（新規9件）。 |
| 関連 BL | BL-222、BL-217（同型のCLI設計・WALモード活用の前例）、BL-074/076/081/202（本文注釈が却下された根拠となった脆さの実例群） |
---

### D-200: Expertへの`write_issue`直接付与は再検討せず、既存のdecision_extractor橋渡し機構（BL-154）自体の2つの欠落を修正する（BL-223）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-13 |
| 状態 | `decided`（実装完了） |
| 決定者 | t-momose（実ログの指摘、「Expertにwrite_issueを与えなかった穴では」という論点提起、修正方針の承認）、Claude Sonnet 5（調査・設計・実装）、独立レビュー（cline、Bug B修正案の欠陥を指摘） |
| **決定理由** | `log/2026-08-13/1411`で、Expertが成果物内で明示的に宣言した先送り（SLA待ち時間の解釈）が構造化記録に一切残らないことが判明した。ユーザーから「Expertに`write_issue`を与えなかった設計判断自体の穴では」との指摘があったが、調査の結果、D-124/BL-154が既にこの経路を「Expertは`write_issue`を持たない代わりに、`decision_extractor_node`が事後解析でissue_log/plan_draftsへ橋渡しする」形で手当て済みであると判明した。今回の実害は設計の欠落ではなく、この既存ブリッジ自体の実装バグ（後述）であり、Expertへの`write_issue`直接付与は、D-124が明示した「BL-025のロール分離思想（Detectorの独立監査とExpertの自己申告の混同）に反する」という却下理由を覆すことになるため再検討しなかった。ブリッジのバグは2つ独立して存在した：①`wrote_agreement_this_turn`（ターン単位のブール）が、Expertが同ターンで別件のwrite_agreementを呼んだだけで無関係な抽出項目まで一括スキップしていた、②`defer_to_task_id`が空文字（申し送り先が特定できない）の場合、plan_drafts追記だけでなくissue_log起票まで丸ごとスキップしていた。設計段階で、②の当初修正案（defer_to_task_idの真偽だけでissue_log起票を切り出す）が、独立レビュー（同一セッション内の別AI、cline）から既存テスト`test_unresolvable_target_task_id_skips_issue_log_creation`を破壊すると指摘された。実コードを検証した結果、`_get_blocking_issues_for_transition`のSQL（`defer_to_task_id IS NULL OR ''`）がdefer_to_task_idの実在性を検証せず値の有無だけで遷移ゲートを免除するため、非空だが解決不能（LLMが実在しないtask_idを出力した）issueを起票すると永久に解決されない抜け穴になることを確認し、この既存のfail-closed設計は維持する3分岐へ修正した。 |
| 決定内容 | ①`_LAST_WRITE_AGREEMENT_ITEMS`（成功したwrite_agreement呼び出しの`{entry_type, task_id}`一覧、`_LAST_WRITE_AGREEMENT_SUCCEEDED`と同型のquery_AI単位リセットパターン）を新設し、`LineageState`へ`expert_wrote_agreement_items`/`user_wrote_agreement_items`を追加。`decision_extractor_node`の判定を、ターン単位のブールから項目単位の`(entry_type, task_id)`一致判定へ置き換えた（topic文字列は直接呼び出しと独立抽出とで表記が一致する保証がないため使わない）。②`defer_to_task_id`の状態を「空文字（issue_logのみ起票、plan_draftsは対象タスク不明のためスキップ）」「解決可能（従来通り両方）」「非空・解決不能（無変更・fail-closed維持）」の3分岐に書き換えた。 |
| 影響 | `cela_main.py`（`_LAST_WRITE_AGREEMENT_ITEMS`新設・getter、`LineageState`拡張、`expert_node`/`generate_user_utterance`の書き込み箇所、`decision_extractor_node`の判定・分岐）。新規テスト`tests/test_bl223_decision_extractor_deferred_bridge.py`（7件）。既存テスト`tests/test_r3_smoke.py::test_r3b_t5_decision_extractor_skips_agreement_write_when_write_agreement_succeeded`が項目単位判定への変更で回帰したため、実運用の状態伝播（expert_nodeが`expert_wrote_agreement`と`expert_wrote_agreement_items`を同時にstateへ書く）に合わせて修正。フルオフラインスイート1306 passed / 5 deselected（`test_bl195`の1件は本BLと無関係な既存失敗）。 |
| 関連 BL | BL-223、[BL-154](back_log/issue_backlog.md#bl-154-decision_extractorのdirectivedeferred自動抽出をissue_logへも橋渡しする)、[BL-082](back_log/issue_backlog.md#bl-082-task_plannerの計画をホワイトボード化し先送り事項をタスク間で永続的に申し送りできるようにする)、[BL-096](back_log/issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)、D-124（Expertへ`write_issue`を与えない役割分離判断、本Dで再確認・維持） |
---

### D-201: 実装状況の一覧を要件定義書の付録B.1から`requirements_gap_map.md`へ移し、判定語彙に「名前だけ実装（⚠️）」「死蔵（🗑️）」を新設する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-13 |
| 状態 | `decided`（実施済み） |
| 決定者 | t-momose（「全体がその場しのぎの設計のパッチ当てになっていないか確認して」という点検指示、乖離マップ優先の選択）、Claude Sonnet 5（調査・判定語彙の設計・文書化。一次照合はExplore agent 3体、⚠️/🗑️判定はClaudeが実コードで再確認） |
| **決定理由** | BL-224の設計中に要件定義書を精読した結果、**実装状況の唯一の一覧である付録B.1がv26（2026-07-17）時点のスナップショットのまま陳腐化しており、「何が実装済みか」の判断材料として信用できない**ことが判明した。実際にF-3.1/3.2/3.8/3.9・F-5.1・F-6・F-7・F-8.3を「❌未実装」と表示し続ける一方、F-8.1を「✅実装済み」としていたが実体は名前だけの実装だった。**この誤表示は既に実害を出している**——AIが`agreements.depends_on`（要件§4.2が「DAG系譜」と明示的に定義した機構）を「たまたま未使用の列」と誤認し、BL-224の初版設計で「コメントを付けて放置」と書いた。同じ内容の表を要件定義書と別文書の2箇所に持てば必ず一方が陳腐化するため（AGENTS.md §15.1、付録B.1自身がその実例）、実装状況の正typeは1箇所に集約し、要件定義書は「何を作るべきか」のみを持つ形へ役割を分離した。あわせて、従来の3値（✅/🟡/❌）では今回の発見を表現できないことが判明したため2値を新設した——**⚠️「名前だけ実装」**（関数・テーブルは存在するが中身が要件を満たさず、読む人が実装済みと誤認する。3箇所実在）と**🗑️「死蔵」**（書かれるが誰も読まない。AGENTS.md §15.4）。この2カテゴリを可視化することが乖離マップの主目的である。 |
| 決定内容 | `docs/design/requirements_gap_map.md`を新設し、F-1〜F-22の全38サブID＋DBスキーマ§4.1〜4.9を実コードのみを根拠に照合（全判定に`file:line`証拠を必須、「未実装」は使用した検索語を明記）。要件定義書の付録B.1は表を削除しマップへの参照へ置き換え、付録B.2/B.3にも陳腐化の警告を追記した。 |
| 影響 | `docs/design/requirements_gap_map.md`（新規）、`docs/design/要件定義書_v35.md`（付録B.1を参照へ置換、B.2へ警告追記）。以降、実装状況の更新はマップ側へ行う。 |
| 関連 BL | BL-224（この調査の発端）、BL-225（⚠️/🗑️箇所への注記）、[BL-219](back_log/issue_backlog.md)、D-200 |

---

### D-202: 未実装要件をすべてBL化せず、実害を説明できるものだけ起票する

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-13 |
| 状態 | `decided` |
| 決定者 | Claude Sonnet 5（提案・適用） |
| **決定理由** | 乖離マップの結果、機能要件38サブIDのうち❌未実装が12件あった。しかしこれらを機械的にBL化すると、バックログが「いつか実装するかもしれない要件」で膨れ上がり、**本当に手を入れるべき箇所が埋もれる**。実装されていないこと自体が「その要件は今のCELAの用途に不要だった」という情報でもある——実際、F-9.1（sqlite-vec）とF-7.3（ロールバック）はコード側に意図的な不採用の記録があり、要件側が追従していないだけだった。したがって「実害を具体的に説明できるもの」だけを起票し、説明できないものはマップ上に「未実装だが現時点で実害の説明が無い」と明記して据え置く方針とした。据え置いた要件（F-9/F-5.3の経験のDNA伝承、F-10.4/10.6/10.7・F-22の平行世界探索・市場センシング、F-21のステークホルダー主観）はいずれも要件定義§1.1がCELAの差別化要因として掲げているものであり、**軽視ではなく「実害の観測待ち」という保留**である。 |
| 決定内容 | 起票したのはBL-225（⚠️/🗑️箇所への注記、実害＝BL-224初版設計の誤りが既に発生）とBL-226（申し送り9機構の一元化、実害＝BL-082/154/219/223の4世代にわたる同型再発）の2件。他はマップ§6.2へ優先度と保留理由を記載するに留めた。あわせて「意図的な不実装を要件定義書へ書き戻す」を低優先で起票候補に残した（次に読む人が「やり残し」と誤解して不要な作業を始めるのを防ぐため）。 |
| 影響 | `docs/design/requirements_gap_map.md` §6.2、`docs/design/back_log/issue_backlog.md`（BL-225・BL-226）。 |
| 関連 BL | BL-225、BL-226、BL-224 |

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

### D-203: A2（C3）の解決を「upsert境界への移動」とし、計画概算のfacts登録は別BL（BL-229）へ分離

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-14 |
| 状態 | `decided` |
| 決定者 | t-momose（「タスクプランナーやレビュワーにwrite_agreementを持たせる」という提案、および「計画・タスクは後続に大きな影響」という洞察）、Claude（実コード検証・設計反映） |
| **決定理由** | 独立レビューA2が指摘したC3の2欠陥（①`owns_variables`は`list[str]`でconfidenceフィールドなし＝スキーマ混同、②`task_plan_reviewer_node`は開始前1回のみ発火しその時点でfacts未書き込み＝タイミング誤り）は実コードで確認して正しい。ユーザーは「計画段階の概算・Web探索値をfacts登録すべき（後続への影響大）」と指摘したが、実コード検証の結果**task_planner(8243)・task_plan_reviewer(12035)は既に`WRITE_AGREEMENT_TOOL`を持つ**ため「write_agreementを持たせる」措置自体は不要。`verified_facts`を書かないのは**挙動（登録を指示するプロンプト）の欠落**であった。C3を`task_plan_reviewer_node`に置く設計は構造的に不可能なので、**C3を`upsert_verified_fact`(6719)の境界へ移動**（ノード非依存・`verified_facts.confidence`を読む）ことでA2を解決。同時に、ユーザーの「計画概算をfacts登録せよ」という挙動変更はBL-224スコープ外（§15.2経路増・§15.1共有ヘルパ介入・ユーザー合意要）と判断し、別BL（BL-229）へ分離した。境界方式のC3は将来planner/reviewerがfactsを書いても同じ`upsert_verified_fact`を通るため自動カバーする。 |
| 決定内容 | ①BL-224のC3を`task_plan_reviewer_node`ベースから`upsert_verified_fact`境界ベースへ書き直し（A2解決・スキーマ/タイミング誤り解消）。②計画段階の概算/Web探索値のfacts登録をBL-229として新規起票（設計未着手・BL-224のC3実装後に実施）。 |
| 影響 | `docs/design/back_log/BL-224/BL224_basic_design.md`（C3節書き直し・A2所見「解決済み」化・変更対象ファイル更新）、`docs/design/back_log/issue_backlog.md`（BL-229新規起票）。 |
| 関連 BL | BL-224（C3の所在）、BL-229（計画概算登録・別起票）、BL-219（8,500人問題＝本件の動機）、AGENTS.md §15.1（単一ソース・C3境界化の根拠）、§15.2（経路列挙・別BL分離の根拠） |

---

### D-204: BL-224 未決事項4件の承認（N=10・単独Rejected含括・3段階実装・BL-228分離維持）

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-14 |
| 状態 | `decided` |
| 決定者 | t-momose（4件の未決事項回答）、Claude（設計書・BL-228 への反映） |
| **決定理由** | 未決事項①最大探索深度: ユーザーが **N=10 で様子見**を承認（AGENTS.md §7 の重要定数変更として明示承認済み）。②単独 Rejected: 「含めないと rejected されず放置、または暗黙的に承認されたように見える」というユーザーの指摘どおり、系譜から落とさず可視に保つ。③実装分割: 2段階案を承認のうえ、**BL-228 を含めた3段階**へ拡張（BL-224 基盤→BL-224 消費深化→BL-228 統合）。④BL-228 分離: chat_history スパインを別 BL とする方針を維持。 |
| 決定内容 | ①最大探索深度 **N=10**（C1 Hydrate 表示は1エントリ3段）。実ドライランで要調整なら再承認。②単独棄却提案も系譜参加: 同一 topic の現行アクティブ合意 Y があれば `supersedes` エッジ `agreement:<棄却X>→agreement:<Y>` を張り、無い場合は `status='Rejected'`＋`⚠️[却下事項]` コンテキスト表示＋`trace_lineage`/C1 の topic 走査で `Rejected` を明示含枚（新 relation_type は追加せず3種維持・§15.1）。③BL-224＋BL-228 を合わせた **3段階実装**: Phase1=BL-224 基盤（スキーマ＋W1/W2/W3＋C2＋C5/trace_lineage）、Phase2=BL-224 消費深化（C1/C3/C4/W4）、Phase3=BL-228 統合（chat_history 活性化＋`turn:`/`issue:`/`whiteboard:`/`detector_review:` 拡張＋trace_lineage の `turn:` 受付）。④BL-228 は別 BL として維持、実装順序は BL-224 を Phase1-2 で先行・BL-228 を Phase3 で後続。 |
| 影響 | `docs/design/back_log/BL-224/BL224_basic_design.md`（未決事項→全件解決済み・3段階計画化・単独Rejected機構追記）、`docs/design/back_log/BL-228/BL228_basic_design.md`（未決事項5 実装順序解決済み化）。 |
| 関連 BL | BL-224（本件の主題）、BL-228（Phase3・relation_edges 共有基盤）、BL-229（計画概算登録・D-203 で分離済み）、AGENTS.md §7（N=10 は承認済み重要定数）、§15.1（単一ソース・relation_type3種維持の根拠）、§15.4（C5 なきは §15.4 抵触のため Phase1 必須） |

---

### D-205: BL-224 設計書への独立レビュー所見（N1−N6）の反映・6点の設計判断

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-14 |
| 状態 | `decided` |
| 決定者 | t-momose（レビュー提示＋N2・N4 の設計判断指示）、Claude（N1/N3/N5/N6 の反映＋実コード照合） |
| **決定理由** | 別モデル（cline）による独立レビューが「実装可能・ブロッカーなし」と結論しつつ、6つの軽微な点（N1−N6）を挙げた。AGENTS.md §16.2 に従い各所見を実コードで照合してから設計書へ反映。うち設計判断を要した2点は以下のとおり。N2（単独 Rejected の supersedes フック位置）: 実コード確認で **`decision_extractor_node` は Rejected 合意を `_commit_agreement_from_tool` を経由せず直接 `db_append_agreement`/`db_supersede_agreement` へ書く**（12890/12996/13014）ため、フックを `_commit_agreement_from_tool` の INSERT 直後に置くだけでは decision_extractor 経路の Rejected が零れる。よってフック位置は「`_commit_agreement_from_tool` INSERT 直後」としつつ、**`decision_extractor` の Rejected 分岐からも同一 `_link_supersession` を呼ぶ**よう配線する（W2 edit-wrapper とは別トリガー・ダブルレイヤー禁止）。N4（Phase 1 PR 順序）: スキーマ説明修正（`'42'`→`'AG-xxxx'`、2295-2306）は W3 の `relation_edges` 書き込み配線と**同一 PR/commit** に含める。別 PR に分けると一時的に「LLM が `'42'` を書き→検証 3367-3375 で弾かれ→W3 エッジが空」という、本 BL が直そうとしている §15.4 欠陥を自ら再現するため。 |
| 決定内容 | N1: 検証節の「再帰CTE」表記を「`_traverse_lineage`（Python 反復）」へ修正（M3/B7 方針と整合）。N2: 単独 Rejected の `supersedes` フック位置を `_commit_agreement_from_tool` INSERT 直後とし、ガード=`status=='Rejected'`＋現行アクティブ Y 実在、`_link_supersession(new_id=X, old_id=Y, reason=rationale)` を再利用、かつ decision_extractor 経路も同一ヘルパを呼ぶ（設計書 未決事項2 へ追記）。N3: `trace_lineage` の不明/他 run ref 応答仕様を追加（空リスト＋ヒント／未知プレフィックスは即時返却・§13.2/§15.3）。N4: スキーマ説明修正を W3 と同一変更セットへ（別 PR 禁止）。N5: C3 の `upsert_verified_fact` 内トランザクション境界を Phase 2 着手時に明示決定（二重コミット/競合を避ける）と留意追記。N6: B8 バックフィルを **BL-230** として別起票（既存 `agreements.depends_on` 列→`relation_edges`、マッピングは W3 と同一、過去 run も `trace_lineage` で辿れるように）。 |
| 影響 | `docs/design/back_log/BL-224/BL224_basic_design.md`（検証節 N1、未決事項2 N2、W3 節 N4、C5 節 N3、C3 節 N5、B8→BL-230 参照）、`docs/design/back_log/issue_backlog.md`（優先対応一覧＋Backlog 一覧に BL-230 追加）、本ファイル D-205 新規。 |
| 関連 BL | BL-224（本件）、BL-228（Phase3）、BL-230（N6 バックフィル）、AGENTS.md §13.2（空リスト fail-loud）、§15.3（機械的検証・未知プレフィックス即時返却）、§15.4（W3 スキーマ修正別 PR 分けは欠陥再現）、§16.2（レビュー所見は実コード照合後に反映） |

---

### D-206: BL-237 — think呼び出しを毎iteration必須化し、think呼び出し時は生reasoningの引き継ぎを構造化summaryへ差し替える

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-15 |
| 状態 | `superseded`（同日中、D-207により②のswap案のみ撤回。①③は有効なまま） |
| 決定者 | t-momose（Geminiによる「迷いトークンが文脈に乗ると抜け出せなくなる」という仮説の提示、往復コストを増やさない設計への訂正指示）、Claude（原因調査・実装） |
| **決定理由** | log/2026-08-15/1735・1954で、単一iteration内のreasoningチャンネルが同一結論を延々と再導出する生成崩壊が2回発生した。temperature統一・frequency/presence_penalty=0.3を既に適用した状態で再発したため、これらは原因として不十分と実証された（§14.1）。`_query_AI_live`のコードを確認したところ、thinkの呼び出し有無に関わらず、そのiterationの生reasoning全文（迷い・撤回を含む自然文）が無条件に次iterationへ引き継がれる設計になっており、ユーザーが提示した「迷いのトークンが文脈に乗ると同じ迷いを再生産する」という仮説と整合する具体的な機構だった。過去にBL-108→BL-110で「thinkをsummary付きで併用しない限りツール呼び出しを差し戻す」機械的強制が往復コスト過大で撤廃された経緯があるが（§16.4で確認）、ユーザーの訂正により、それは「think単独のための別iteration」を要求する設計だったからだと判明。現在は全ノードへ`TOOL_CALL_RULE`（同一応答内でツールをまとめて呼ぶ）が既に注入されているため、「他のツールを呼ぶ予定があるなら同一応答内でthinkもまとめて呼べ」という指示に留めれば、機械的な差し戻しを伴わず追加往復を生まない。 |
| 決定内容 | ①`THINK_TOOL`の`description`とプロンプト共有定数`_BL093_THINK_VALUE_PARAGRAPH`（8ノード共有、§15.1）を、「thinkは毎iteration必須（他のツール使用有無に関わらず、使うなら同一応答内でまとめて呼ぶ）」という趣旨へ書き換え。②`_query_AI_live`で、そのiterationにthinkのtool_callsが含まれていたかを機械的に記録し、含まれていれば生reasoningのsystemメッセージ引き継ぎを省略（既にtool結果として渡っている構造化summary`reasoning_log_so_far`のみに絞る）、含まれていなければ従来通り生reasoningを引き継ぐフォールバックとする。③強制は機械的な差し戻しではなくプロンプトレベルの必須化に留め、モデルが従わない場合の保険（`MAX_TOKENS_BY_ROLE`の頭打ち等）は別途検討事項として残す。 |
| 影響 | `cela_main.py`（`THINK_TOOL`定義、`_BL093_THINK_VALUE_PARAGRAPH`、`_query_AI_live`のツールループ）、新規`tests/test_bl237_think_mandatory_carryover.py`、既存`tests/test_bl093_d074_auto_reasoning_enforcement.py`の1テストを新挙動へ更新。 |
| 関連 BL | BL-237（本件）、BL-093/BL-108/BL-110/BL-111（reasoning自動引き継ぎ機構の変遷元）、BL-231（iterをまたいだ生成崩壊ガード。本件はiterをまたがない単一iteration内暴走であり別種の失敗としてBL-231とは独立に対処）、AGENTS.md §14.1（表面一致は診断ではない・再検証）、§16.4（過去の決定を読み直してから行動）、§17.1（リバートで失敗する回帰テスト） |

---

### D-207: BL-237 — think呼び出し時の生reasoning差し替え（D-206②）を撤回し、常に無条件で引き継ぐ設計へ戻す

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-15 |
| 状態 | `decided` |
| 決定者 | t-momose（情報損失リスクの指摘、「生reasoningの引き継ぎを省略しない」という明確な決定指示）、Claude（実装のロールバック） |
| **決定理由** | D-206②（thinkを呼んだiterationは生reasoningの代わりに構造化summaryのみを引き継ぐ）は、迷い・撤回の言い回しの伝播を抑える狙いだったが、think必須化（D-206①）と組み合わさると、web検索結果の統合過程・詳細な検討内容・最終出力の下書き・構造化出力の下書きなど、thinkのsummary（1-3文）には到底収まらない実質的な内容までiteration完了ごとに圧縮・破棄されてしまう。これは「モデルの推論内容そのものへの情報破壊的な介入」であり、当初の狙い（文脈を汚す言い回しの抑制）を大きく超える副作用だとユーザーが指摘し妥当と判断した。代替として、情報の中身に一切踏み込まない`MAX_TOKENS_BY_ROLE`の頭打ち（暴走の長さだけを制限する、内容の取捨選択はしない）の方が安全な手段として残る。 |
| 決定内容 | `_query_AI_live`の生reasoning引き継ぎ（system メッセージ追記）を、think呼び出しの有無に関わらず**常に無条件**で行う設計に戻す（D-206以前の挙動へ復元）。D-206①（think毎iteration必須化・同一応答内でのまとめ呼び出し）とD-206③（機械的強制は伴わない）はそのまま維持する。thinkは「生reasoningに加えて構造化decided/whyのチェックポイントも積む」純粋加算の機構という位置づけに整理し、`THINK_TOOL`のdescriptionと`_BL093_THINK_VALUE_PARAGRAPH`から「thinkの有無で引き継ぎ内容が変わる」という記述を削除。単一iteration内の生成崩壊そのものへの対処は、本決定によりBL-237の直接のスコープからは外れ、`MAX_TOKENS_BY_ROLE`の頭打ち（別BL/別承認、§7）に委ねる。 |
| 影響 | `cela_main.py`（`THINK_TOOL`のdescription、`_BL093_THINK_VALUE_PARAGRAPH`、`_query_AI_live`の`_think_called_this_iter`関連コードを削除）、`tests/test_bl237_think_mandatory_carryover.py`（swap前提のテストを、無条件引き継ぎを確認するテストへ差し替え）、`tests/test_bl093_d074_auto_reasoning_enforcement.py`（D-206②で変更した1テストの想定挙動を元に戻す）。フルオフラインスイート1372 passed / 1 deselected。 |
| 関連 BL | BL-237（本件、D-206の一部撤回）、BL-093/BL-108/BL-110/BL-111（reasoning自動引き継ぎ機構）、AGENTS.md §16.1（ユーザー自身の提案でも軽い代替案とのトレードオフを提示してから実装すべきだった——本来は実装前にこの情報損失リスクを提示すべき論点だった） |

---

### D-208: BL-238 — ホワイトボード改版フックから実行不能なtrace_lineage呼び出しを削除し、新規ツールは追加しない

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-15 |
| 状態 | `decided` |
| 決定者 | t-momose（ドライラン中の実地報告「系譜が0件」、新規ツール不要という判断の指摘）、Claude（原因調査・実装） |
| **決定理由** | ドライラン（log/2026-08-15/2149）で`trace_lineage(ref='whiteboard:...')`が常に`lineage: []`を返すことが実地で確認された。調査の結果、`relation_edges`に`whiteboard:` refを指すエッジを書き込むコード経路が一切存在せず、BL-228の改版フックが構造的に実行不能な指示をしていたと判明した。修正案として`diff_plan_draft_versions`（BL-092、plan_drafts専用）と同型の`diff_whiteboard_versions`ツール新設を検討したが、ユーザーの指摘により、①「同じ根本課題が繰り返される」検知は既に`issue_log.occurrence_count`の機械的エスカレーション（chat_history_windowに依存しない常時pin）が担っており重複する、②BL-092が解決した問題（差分を見ないと直されたか消されただけか分からない）はDetectorが差し戻しのたびに独立に全体を再監査する設計のためwhiteboard側には構造的に存在しない、と判明し、新規ツールは不要と判断した。 |
| 決定内容 | `_build_task_scope_context`のwhiteboard改版フック（version≥3で発火）から、実行不能な`trace_lineage(ref='whiteboard:...')`呼び出し指示を削除する。新規ツール（`diff_whiteboard_versions`等）は追加しない。バージョン数≧3というシグナル自体（既存データの副産物、追加コスト無し）は残し、「改版が重なっていること自体が空回りのサイン」という気づきから、直接escalate_premise_concern/write_issueへつなげる指示に縮小する。派生して、`call_reflection`にホワイトボード版数の可視性が無いという別の指摘（ユーザー）はBL-239として分離・記録し、実装は見送る（対象ノード・役割が異なるため）。 |
| 影響 | `cela_main.py`（`_build_task_scope_context`のwhiteboard改版フック文言）、`tests/test_bl228_chat_history_lineage.py`（該当テストを新挙動へ更新・リネーム）、`docs/design/back_log/issue_backlog.md`（BL-238 `done`・BL-239 `open`新規起票）。 |
| 関連 BL | BL-238（本件）、BL-239（派生・別issue）、BL-228（trace_lineage/改版フックの導入元）、BL-224（relation_edges基盤）、BL-092（diff_plan_draft_versionsの元ネタ、今回は不要と判断した比較対象）、AGENTS.md §15.4（出口の無い入口を作ってしまっていたケース）、§16.5（大きな実装に進む前に、そもそも必要かを問う） |

---

### D-209: BL-240 — Detectorの「情報不足を理由にmajorにしない」判定基準に、web_searchで確認できる事項の区別を追加

| 項目 | 内容 |
|------|------|
| 日付 | 2026-08-16 |
| 状態 | `decided` |
| 決定者 | t-momose（IDE選択での指摘「仮想シナリオ前提の文言が抜け穴になりうる」）、Claude（該当箇所の調査・実装） |
| **決定理由** | Detectorのドメイン妥当性レビュー判定基準は、web_searchの無い仮想シナリオ・ストレステスト時代に、未記載の詳細すべてを理由にした過剰なmajor判定を防ぐ目的で書かれた。しかし実世界シナリオ＋web_search前提の現在は、「シナリオに明記されていない」ことが必ずしも「調べようがない」ことを意味しない。既存のBL-188検証指示はExpertが主張した内容（citations付き）の裏取りに限定されており、Expertが何も言っていない欠落を能動的に確認する指示にはなっていなかった。一方、同じdomain_prompt内のBL-198（地理データ）箇所には既に「取得できない種類のデータに限定」という同種の区別があり、この判定基準ブロックだけがその区別を欠いていた（AGENTS.md §15.1: 同じ設計原則の横展開もれ）。 |
| 決定内容 | 判定基準ブロックに、「不明である」という判断自体を鵜呑みにする前に、それが本当に調べようがない事項か、read_goal_reference/read_reference_file/web_searchで確認できる事項かを区別し、後者は確認してから判定するよう一文追加する。確認してもなお不明・非公開の場合や、そもそも公的に確認しようのない事項は引き続きmajorの根拠にしない、という従来の免罪符は維持する（判定基準そのものの厳格化ではなく、BL-198と揃える横展開）。 |
| 影響 | `cela_main.py`（`call_detector`のdomain_prompt判定基準ブロック）。既存テスト`tests/test_bl134_unsupported_generalization_guard.py`は既存文言の存在確認のみのため回帰なし。 |
| 関連 BL | BL-240（本件）、BL-188（citations付き主張の裏取り、対象範囲が異なる）、BL-198（地理データにおける先例）、AGENTS.md §15.1（単一の設計原則をコードベース全体で一貫させる） |

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
