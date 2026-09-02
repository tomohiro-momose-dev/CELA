# BL-336: Expertがentity DBを使わず一次資料の事実を毎回読み直す問題 — 設計

## Context

GAIAパイロット（1959年USDA脱水青果物等級規格）のドライランログ監査で、Expertがtask_1_1で読み解いた
44品目のUSDA規格リスト（品目名・1959年時点effective date）が、task_1_2・task_1_3で毎回ゼロから
読み直されていたことが判明した（issue_backlog.md BL-336として記録済み）。当初の仮説は「entity DB
（BL-204の`entities`/`entity_attributes`）へ記録せよという誘導がExpert向けプロンプトに欠けていた」
というものだった。

**設計着手にあたり実コードを再調査した結果、この診断は不正確だったことが判明した（AGENTS.md §16.3
に従い訂正する）。** BL-204の誘導は既に存在する——`register_entity`/`write_entity_attribute`ツールは
`_expert_tools`に配線済み（`cela_main.py:13627`）で、使用ガイダンス段落もExpertのsystem_prompt
（iter=1、`cela_main.py:13096-13118`）とlight_system_prompt（iter=2以降、`cela_main.py:13493-13504`）
の両方に既に存在する。にもかかわらず、task_1_1・task_1_2・task_1_3の3回の独立したExpert実行は
一度もこれらのツールを呼ばなかった。

**再調査で見つかった本当のギャップ（§15.1: 単一ソースの分裂）**: 同じBL-204ガイダンスがsystem_prompt
とlight_system_promptの2箇所に重複して存在するが、文言が食い違っている。

- full版（iter=1のみ、`13097`）: 「施設・場所・組織・路線・**制度**・サービス等、**種類は問いません**」
- light版（iter=2以降、`13494`、BL-025によりiter=2以降はこちらに差し替わる——ツールループの
  大半はこちらが有効）: 「施設・場所・組織・路線・サービス等」（**「制度」と「種類は問いません」が
  欠落**）

USDA等級規格（regulatory standard）は「制度」の一種と言えるが、その語がまさに抜け落ちている
light版だけがツールループの大半で有効だったため、3回とも「これはentityの対象では」と認識されな
かった可能性が高い。加えて、`register_entity`ツール自体の説明文（`1476`、常にAPIへ送られる、
promptの版に関わらず常時可視）の例示も「a place, organization, service, facility, route, product」
のみで、`read_entity`の説明文（`1567-1568`、既に"law"を含む）より狭い。

この訂正された診断に基づき、設計を2部構成にする：

## Part 1 — Expert側: ガイダンスの分裂を解消し、「複数品目×複数タスク」の具体的トリガーを追加

新規パラグラフを追加するのではなく、既存4箇所の文言を最小限直す（§15.1: 単一ソースへの回帰）：

1. **light_system_prompt（`cela_main.py:13493-13501`）を書き換え**、full版と同じ「制度」
   「種類は問いません」を含める。
2. **共有定数として新規追加**（Cline指摘P2-1、`_TRACE_LINEAGE_USAGE_PARAGRAPH`と同型のパターン）：
   `_ENTITY_MULTI_ITEM_TRIGGER_SENTENCE`という1文の定数を新設し、full/light両方のBL-204段落に
   埋め込む。単に「両版に同じ文をコピペする」のではなく単一の文字列定数を共有することで、
   今回診断した「同じ文言が2箇所に分裂し片方だけ更新漏れする」という同型の再発を構造的に防ぐ
   （§15.1）。内容：「特に、対象が複数（品目・地点・版など）にわたり、後続タスクが同じ事実を
   再度必要としうる場合は、python変数や成果物本文への埋め込みだけで済ませず、事物ごとに
   register_entity／write_entity_attributeで記録してください」という趣旨。GAIAパイロットで
   実際に起きた事象（同じ一次資料を複数タスクが都度読み直す）を具体的トリガーとして示す。
3. **`register_entity`のツール説明文（`cela_main.py:1476`）に例示を追加**：「a regulation,
   standard, or law」を既存の例示（place/organization/service/facility/route/product）に加え、
   `read_entity`の説明文（既に"law"を含む）と揃える。

## Part 2 — Detector側の保険（provisional代理登録、ユーザー提案）

Expertが登録を怠ったままDetectorの差し戻しに遭うと、`call_expert`は差し戻しのたびに
`messages = []`で組み立て直され（`cela_main.py:13347`）、前回の調査過程（read_reference_file/
web_search/web_fetchの生データ）は完全に失われる（BL-336記載の既存調査で確認済み）。この保険は、
Expertが一次資料の事実を列挙したのにentity DBへ一件も書かなかったパターンをDetectorが機械的に
検知し、confidence="provisional"で代理登録することで、差し戻し後もその事実を再利用可能にする。

### 2.1 機械的トラッキング（新規、BL-033/BL-242と同型のパターンを踏襲）

- 新規グローバル `_LAST_ENTITY_WRITES: list[dict]`（`cela_main.py:6000`付近、`_LAST_PYTHON_CALLS`
  の隣）。
- `_register_entity_handler`・`_write_entity_attribute_handler`（`2316-2414`）の**真の成功パス
  のみ**（Cline指摘P2-2）で`_LAST_ENTITY_WRITES.append({"entity": ..., "attr_name": ...})`する。
  `register_entity`が`status="already_registered"`（`2335-2337`、既存事物への冪等な早期リターン）
  を返した場合は新規の書き込みではないため**appendしない**。appendするのは`status="registered"`
  （新規登録）および`write_entity_attribute`の`status="ok"`のみ（write_entity_attributeのみ
  attr_name分。register_entityは`{"entity": canonical_name, "attr_name": None}`のように区別する）。
- 新規ゲッター `get_last_entity_writes() -> list[dict]`（`6089-6096`付近、`get_last_deliverable_reads`
  と同じ書き方）。
- `query_AI()`のリセットブロック（`6226-6227`）に `_LAST_ENTITY_WRITES = []` を追加。
  **Cline指摘P3**: 同じ行にある巨大な`global`宣言文（`_call_seq_counter, _LAST_PYTHON_CALLS, ...`）
  にも`_LAST_ENTITY_WRITES`を追加し忘れないこと——宣言漏れは`NameError`か、意図しない別スコープの
  新規グローバル生成になる。

### 2.2 State配線

- `LineageState`（`11071-11072`付近）に `expert_last_entity_writes: list[dict]` を追加。
- Expertノードの状態コピー箇所（`17677-17680`、`expert_last_python_calls`/
  `expert_last_deliverable_reads`と同じ場所）に
  `state["expert_last_entity_writes"] = get_last_entity_writes()` を追加。
- 初期state辞書（`20102-20103`）に `"expert_last_entity_writes": []` を追加。

### 2.3 Detectorプロンプトへのブロック追加（`call_detector`、`13694`付近）

**Cline指摘P1-1（要反映）**: `python_calls_block`は実際には**数値監査用プロンプト（`14409`）
にのみ**補間されており、ドメインレビュー用プロンプト（`14051`付近、〜`14171`で完結）には
**補間されていない**（ドメインプロンプト内`14031`行の「python_calls_blockでの計算過程」という
言及は、既存の潜在的な不整合——本設計では触らない）。そのため`entity_writes_block`は
**ドメインレビュー用プロンプトへ明示的に補間する箇所を新設する**（2.4の指示パラグラフの直前に
配置）。トリガー判定の材料は「python_calls_block」ではなく、ドメインレビュープロンプトに
実際に見えている情報（whiteboard本文＝`whiteboard_block`、`history_text`等）とする。

**Cline指摘P1-3（要反映）**: `expert_last_entity_writes`はExpertノードのみが書くstateであり、
`call_detector`が`target_role="user"`（User AIターンの監査）で呼ばれた場合、前回Expertターンの
残骸（または空）が見えてしまい、「0件」という誤った信号になる。既存の`python_calls_block`にも
同型の陳腐化があるが（`13697`、target_role不問で読む）、BL-336の新規機構は「0件→代理登録の
実行」という能動的なツール呼び出しへ直結するため、誤誘発時の実害が大きい。
`target_role == "expert"`の場合のみブロックを生成・補間し、それ以外（`"user"`等）では
空文字列とする（既存コードの`13776`行の分岐パターンと同型）。

```python
entity_writes_block = ""
if target_role == "expert":
    entity_writes = state.get("expert_last_entity_writes", [])
    entity_writes_block = (
        f"【BL-336: 今回のExpertターンのentity DB書き込み】{len(entity_writes)}件: {entity_writes}\n"
        if entity_writes else
        "【BL-336: 今回のExpertターンはentity DBへの書き込みが0件でした】\n"
    )
```

### 2.4 Detectorへの指示パラグラフ（新規、ドメインレビュー用プロンプト内、`entity_writes_block`
補間箇所の直後に追加）

- `entity_writes_block`（`target_role == "expert"`の場合のみ非空）が0件で、かつ（ドメイン
  レビュープロンプトに実際に見えている）whiteboard本文・`history_text`に「複数の名前付き事物×
  属性」の列挙が見られる場合、これを登録漏れの可能性として扱う。
- 該当する場合、Detector自身が`register_entity`（未登録なら）→`write_entity_attribute`で
  代理登録する。**confidenceは常に`"provisional"`固定**——プロンプト指示に加えて§2.6の
  ハンドラ側の機械的強制も併用する（§15.3: 自己申告に頼らない）。`reason`には
  「Detectorが今回のExpertターンの出力から代理登録（BL-336保険機構）」等、代理登録である旨を
  必ず明記する。
- **Cline指摘P2-3（要反映）**: `register_entity`は出典なしのdiscovered事物登録を拒否する
  （`2330-2333`）。指示パラグラフに「whiteboard本文・history_text等で確認した出典を
  citationsに必ず添えること」を明記する——これが無いと代理登録がエラーで失敗し、保険が
  空振りする。
- これはベストエフォートの保険であり、必須のブロッキングゲートではない。0件であること自体を
  constraint_issueの根拠にしない。**Cline指摘P2-4（要反映）**: 品目数が多い場合（GAIAパイロット
  相当で品目×2ツール≈80回超）、Detectorのツール呼び出し予算（`MAX_TOOL_ITER`）を圧迫し監査
  本業や最終JSON出力ができなくなるおそれがある。指示パラグラフに「監査本業を優先し、残りの
  ツール呼び出し予算の範囲内で、後続タスクが再利用しそうな事物から優先的に登録する」旨の
  優先付け文言を含める。部分的な登録で構わず、網羅できなかったこと自体をExpertへの追加指摘
  対象にしない。

### 2.5 ツール配線

- `_detector_domain_tools`（`cela_main.py:14174`）に`REGISTER_ENTITY_TOOL`・
  `WRITE_ENTITY_ATTRIBUTE_TOOL`を追加。
- ドメインレビューのツール一覧テキスト（`14069-14073`）にも両ツール名を追記。
- ハンドラ側の権限チェックは確認済み（`_register_entity_handler`/`_write_entity_attribute_handler`
  は`_CURRENT_CALLER_ROLE`にロール固有の制限を持たず、`created_by`として記録するのみ——
  Detectorロールからの呼び出しをブロックする既存コードはない）。

### 2.6 ハンドラ側でのconfidence機械的強制（新規、Cline指摘P1-2、要反映）

`_write_entity_attribute_handler`（`2373-2391`）は`confidence`引数をそのまま受け入れており、
Detectorが出典を添えれば`confirmed`でも成功してしまう（プロンプト指示のみでは§15.3
「自己申告に頼らない」に反する）。`_CURRENT_CALLER_ROLE == "detector"`の場合、
`args.get("confidence")`の値に関わらず`confidence`を`"provisional"`へ強制的に上書きする
（`confirmed`を拒否してエラーにするのではなく、静かにprovisionalへ落とす——保険機構が
エラーで頓挫するより、確実に何かが記録される方を優先する設計判断。**要ユーザー承認**、
未確定事項参照）。

#### 既知の限界（Cline指摘P3、対応不要・記録のみ）

`_enforce_decision_lineage_freetext`（BL-283、`7527-7551`付近）がリトライで`query_AI`を
再呼び出しすると、`_LAST_ENTITY_WRITES`を含む`_LAST_*`系グローバルはリセットされ、
expert_nodeが最終的に読む値はリトライ分のみになる（`_LAST_PYTHON_CALLS`など既存の全`_LAST_*`
機構が共有する既知の限界であり、本設計固有の新規問題ではない）。誤って「0件」と判定されて
代理登録が走った場合でも、`already_registered`/upsertにより冪等なため実害はない。本設計では
対応せず、既知の限界として記録するに留める。

## 未確定事項（要ユーザー判断）→ すべてユーザー承認済み（2026-09-02、提案通り）

- Detectorの代理登録を、通常のドメインレビュー（`_detector_domain_tools`）のみに適用するか、
  数値監査パス（`_detector_numeric_tools`）にも広げるか。数値監査は計算値の検算が主眼であり、
  名前付き事物の事実とは性質が異なるため、**ドメインレビューのみへの適用**（承認済み）。
- Detector 1ターンあたりの代理登録件数に上限を設けるか（AGENTS.md §7の新規定数扱い）。品目数が
  多いGAIAパイロットのようなケースでツール呼び出し予算を圧迫しないための保護。**明示的な上限は
  設けず、Detector自身のツール呼び出し予算内でベストエフォートに任せる**（他のDetector機構と
  同様、既存のMAX_TOOL_ITER等の枠組み内で自然に制約される、承認済み）。
- **§2.6のconfidence機械的強制の是非（Cline指摘P1-2）**: `_CURRENT_CALLER_ROLE == "detector"`の
  場合に`confidence`を常に`"provisional"`へ強制すると、Detectorが仮にExpertの主張を独立検証
  できた場合（例: web_searchで自ら裏取りした場合）でも一律provisionalへ落ちるトレードオフが
  ある。§15.3の先例（BL-179/180、D-177：機械的検証がプロンプト指示より優先されるべき）に従い、
  **機械的強制を採用**（承認済み）。

## テスト方針（§17.1）

- `tests/test_bl336_entity_writes_tracking.py`（新規）: `_register_entity_handler`/
  `_write_entity_attribute_handler`呼び出しで`_LAST_ENTITY_WRITES`が正しく積まれること、
  `get_last_entity_writes()`が正しく返すこと、`query_AI()`呼び出しでリセットされること。
- `tests/test_bl336_detector_entity_insurance.py`（新規）: `_detector_domain_tools`に
  `register_entity`/`write_entity_attribute`が含まれること、Detectorロール
  （`_CURRENT_CALLER_ROLE="detector"`）から両ハンドラを呼んでも権限エラーにならないこと。
  加えてCline指摘§6の3件を追加：
  - detectorロールで`confidence="confirmed"`＋citations付きで`write_entity_attribute`を
    呼んでも、記録される値は`"provisional"`になること（§2.6の機械的強制の直接検証）。
  - `target_role="user"`でのDetector呼び出し時、`entity_writes_block`がプロンプトに含まれない
    （空文字列である）こと（P1-3の検証）。
  - `register_entity`が`status="already_registered"`を返すケースで`_LAST_ENTITY_WRITES`に
    appendされないこと（P2-2の検証）。
- `tests/test_bl204_entity_registry.py`の既存テストが非退行であることを確認。
- light_system_prompt/system_prompt文言変更は、既存の文字列アサーションテスト
  （BL-204関連の言及チェックがあれば）に影響しないか確認。
- 各項目を個別にrevertし、対応するテストが失敗することを確認した上で復元する。
- `python -m py_compile cela_main.py`
- 既存の narrow test set（変更箇所に対応するテスト）を実行、その後フルオフラインスイート。

## Critical Files

- `cela_main.py`:
  - ツール説明文: `1471-1554`（register_entity/write_entity_attribute）、`1556-1586`（read_entity）
  - ハンドラ: `2316-2414`（`_register_entity_handler`/`_write_entity_attribute_handler`、
    §2.6のconfidence機械的強制もここに追加）
  - 新規グローバル・ゲッター: `6000`付近、`6089-6096`付近
  - `query_AI()`リセット: `6226-6227`（globalリスト・実代入の両方に追加、Cline指摘P3）
  - `LineageState`: `11071-11072`付近
  - Expert system_prompt（full）: `13096-13118`
  - Expert light_system_prompt: `13493-13504`
  - 新規共有定数`_ENTITY_MULTI_ITEM_TRIGGER_SENTENCE`: `_TRACE_LINEAGE_USAGE_PARAGRAPH`
    （`11994`付近）と同じ並びに追加
  - `call_detector`: ドメインレビュー用プロンプト内`entity_writes_block`補間箇所（新設、
    `14051`付近のBL-204段落の隣）、ツール一覧テキスト（`14069-14073`）、
    `_detector_domain_tools`（`14174`）——**python_calls_blockが数値監査プロンプト
    （`14409`）専用でドメインレビューには補間されていない点に注意（P1-1）**
  - Expertノード状態コピー: `17677-17680`
  - 初期state辞書: `20102-20103`
- `tests/test_bl204_entity_registry.py`（既存、参照パターン）
- 新規テスト2ファイル（上記）
- `docs/design/back_log/BL-336/BL336_basic_design.md`（本ファイル）
- `docs/design/back_log/issue_backlog.md`（BL-336節を`open`→設計完了の記録に更新）

## 独立レビュー（AGENTS.md §19.1、Cline CLI・glm-5.3-flash・2026-09-02）

計画の全行番号参照を実コードと1行単位で照合し、正確性は非常に高いと評価された。P1指摘3件
（python_calls_blockがドメインレビューに補間されない事実誤認／confidence強制のプロンプト依存／
target_role="user"時のstale data）はいずれも実コードで再現確認の上、本設計へ反映済み。P2推奨
4件（共有定数化／append条件の明確化／citations必須の明記／ツール予算の優先付け）も反映済み。
P3（BL-283リトライ時の`_LAST_*`リセットという既存の限界）は「既知の限界」として記録するに留めた。

## 実装後の手順

- AGENTS.md §19.4（diff-based独立レビュー）を実施し、指摘を実コードで検証の上反映。
- `issue_backlog.md`のBL-336節を更新（本設計の内容・訂正された診断を反映）。
