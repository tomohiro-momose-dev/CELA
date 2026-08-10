# BL-204 基本設計：実世界事物レジストリ（entities / entity_attributes）

> ユーザー提案「登場する事物をDBなどで構造的に管理しなければならない。既に確定したものを
> DBに書く仕組みはあるが、構造化されていない。webでいくらでも情報が取れる分、
> ハルシネーションリスクが跳ね上がった」を受けた設計。
> 関連: BL-184（web_search導入）、BL-188（citations）、BL-195（実データ化）、
> BL-198（地理API）、BL-199（事前収集参照データ）、BL-203（gsi_geocodeの誤用）。

---

## 1. Context（なぜ必要か）

BL-184でweb_searchを、BL-198で実地理APIを導入した結果、エージェントは現実世界の事物に
ついて大量の事実を取得できるようになった。しかし取得した事実を**事物単位で固定する器が
存在しない**ため、以下の事故が実ドライランで発生している。

### 1.1 事物の同一性が「事実」として管理されていない（BL-203の直接原因）

`log/2026-08-10/0901`で、ゴール文に`公立諏訪東京理科大学`と明記されているにもかかわらず、
Expertは記憶から「長野大学」（実在するが上田市の無関係な大学）と書き、学生数1,285人＋83人
というゴール文由来の数値だけをそのまま流用した。

**数値は`verified_facts`に保存されていたが、「公立諏訪東京理科大学」という名称そのものは
どこにも事実として登録されていなかった**。したがって名称がすり替わっても、それと矛盾する
対象が存在せず、機械的にも監査的にも検出できなかった。

### 1.2 属性ごとの出典・確度が失われる

現在、Expertは5拠点分の座標・標高・距離を`key_locations_matrix`という**1本の巨大な
文字列**として`verified_facts`の1行に格納している。`verified_facts`は行単位では
`reason` / `citations` / `confidence` / `source_task_id`という良い出典封筒を持っているが、
**その封筒が blob 全体に1つしか付かない**。

結果、「標高894.2m（GSI DEM実測）」と「学生数1,368人（web由来）」と「所要時間34.1分
（工学的仮定）」が、同一の`confidence`・同一の`citations`で並ぶ。BL-195〜BL-198が
一貫して守ろうとしてきた「実測値／二次情報／工学的仮定を分離して明記する」という線を、
保存形式そのものが表現できていない。

### 1.3 機械的な整合チェックができない

住所・座標・標高が同じ事物の**別々の属性**として保持されていれば、
「保存された住所を再ジオコーディングして、保存された座標と一致するか」という
**主観判断を挟まない検算**が可能になる。これはBL-203で発生した
「誤った場所の正しい実測値」をピンポイントで捕まえる。blob文字列のままでは不可能である。

### 1.4 毎ラウンド再導出している

`log/2026-08-09/2348`では諏訪中央病院855.7m・大学894.2mと**正しく取れていた**が、
翌朝の`log/2026-08-10/0901`は最初から取り直して1,239m・1,475mへ劣化した。
事物単位で引ける形になっていないため、確定済みの事実が実質的に再利用されていない。

---

## 2. 設計方針

### 2.1 中核となる考え方

**事物（entity）を一級市民にし、属性（attribute）を事物にぶら下げる。属性の出典封筒は
`verified_facts`の既存パターンをそのまま踏襲する。**

出典封筒を新規発明せず既存に揃えるのは、Expert/Detectorのプロンプトで既に浸透している
`confidence` / `citations` / `reason`の語彙を再利用でき、学習コストと不整合リスクを
最小化できるため（BL-076とBL-193が矛盾した事故のように、新しい語彙を足すこと自体が
将来の不整合の種になる）。

### 2.1.1 `confidence`と`citations.type`は直交する2軸である（Clineレビュー指摘・中1への対応）

初版では`confidence`を`confirmed | provisional | assumption`の3値とし、BL-195〜198の
「実測値／二次情報／工学的仮定を分離する」要求に応えようとしていた。しかしこれは
**上記2.1の方針に対する自己矛盾**であるとレビューで指摘された。実コードを確認した結果、
既存の`confidence` enumは`["confirmed", "provisional"]`の2値であり（`cela_main.py:1905`）、
`assumption`は確かに新語彙の追加だった。

さらに調査したところ、**「実測値／二次情報／工学的仮定」の区別は既に`citations.type`が
担っている**ことが分かった（`cela_main.py:1851`）：

```
citations.type ∈ {"web", "goal_text", "prior_agreement", "expert_calculation", "user_input", "document"}
```

`expert_calculation`が工学的仮定・導出値を、`web`/`document`が二次情報を、`goal_text`が
与件を表す。したがって`assumption`は**冗長**であり、正当化するのではなく**削除**する。

本設計では以下の直交2軸として整理する。新しい語彙は一切追加しない。

| 軸 | フィールド | 値 | 意味 |
|---|---|---|---|
| **確定度** | `confidence` | `confirmed` / `provisional` | その値がどれだけ動かないか |
| **出所** | `citations[].type` | `web` / `goal_text` / `expert_calculation` 等 | その値がどこから来たか |

例：`confidence="provisional"` かつ `citations=[{"type":"expert_calculation"}]` が
「まだ他タスクと突き合わせていない工学的仮定」を表し、初版の`assumption`が意図していた
状態を過不足なく表現できる。

### 2.2 スキーマ

```sql
CREATE TABLE IF NOT EXISTS entities (
    run_id         TEXT NOT NULL,
    entity_id      TEXT NOT NULL,   -- 安定した内部ID（例: "suwa_central_hospital"）
    canonical_name TEXT NOT NULL,   -- 正典表記（ゴール文の表記をそのまま）
    entity_type    TEXT NOT NULL,   -- "place" | "organization" | "service" | ... 自由
    aliases        TEXT DEFAULT '[]',   -- JSON配列。表記ゆれ（「組合立諏訪中央病院」等）
    origin         TEXT NOT NULL,   -- "goal_text" | "discovered"
    created_by     TEXT,            -- 登録したロール
    created_at     REAL,
    PRIMARY KEY (run_id, entity_id)
);

CREATE TABLE IF NOT EXISTS entity_attributes (
    run_id          TEXT NOT NULL,
    entity_id       TEXT NOT NULL,
    attr_name       TEXT NOT NULL,   -- 自由（address / coordinates / elevation_m / ...）
    value           TEXT NOT NULL,
    unit            TEXT DEFAULT '',
    -- [2.1.1] verified_factsと同じ2値のみ。「工学的仮定」はcitations.type=expert_calculationで表す
    confidence      TEXT DEFAULT 'provisional',  -- confirmed | provisional
    citations       TEXT DEFAULT '[]',           -- verified_facts.citationsと同形式
    reason          TEXT DEFAULT '',             -- どう取得・導出したか
    source_task_id  TEXT,
    source_phase_id TEXT,
    -- [Clineレビュー中2] verified_factsの列名（confirmed_by/confirmed_at）へ揃える。
    -- 初版のrecorded_by/recorded_atは、2.1「既存語彙に揃える」方針に反する独自語彙だった。
    confirmed_by    TEXT,
    confirmed_at    REAL,
    PRIMARY KEY (run_id, entity_id, attr_name)
);
```

**属性名（`attr_name`）は完全に自由**とする（ユーザー提案どおり、対象や要件により
可変であるため）。一方、**属性の封筒（value/unit/confidence/citations/reason/source_task_id）
は必須**とする。構造化の価値は「属性名の統制」ではなく「1属性ごとに出典と確度が付くこと」
にあるためである。属性名まで事前定義しようとすると、ドメインごとにスキーマ設計が必要になり
汎用エージェントとして破綻する。

### 2.3 ゴール文からの初期登録と「正典名チェック」（本設計の中核）

**run開始時に、ゴール文に登場する事物を`origin='goal_text'`として初期登録する。**

このとき、抽出した`canonical_name`が**ゴール文中に文字列として実在すること**を機械的に
検証し、実在しないものは登録を拒否する。

- これは客観的な検査（部分一致）であり、LLMの主観判断を必要としない。
- **この1点だけで、BL-203の「長野大学」は`origin='goal_text'`としては登録され得ない。**
- ゴール文は`revise_goal`で改定され得るため、改定時に再検証する必要がある（後述の要確認事項）。

初期登録の実行主体は`task_planner`の前段に置く。理由は、タスク分解より前に
「この課題に登場する事物は何か」を確定させておくことで、`owns_variables`や
`acceptance_criteria`が事物を参照できるようになるため。

### 2.4 未登録の事物名を書けなくする（同一性ガード）

`write_entity_attribute`は、**既に登録済みのentity_idまたはalias**にしか属性を書けない。
未登録の名称が渡された場合は、`read_verified_fact`が既に採用している
**`did_you_mean`パターン**（`suggest_similar_verified_facts`、`cela_main.py:6032`）を
そのまま流用し、登録済み事物の候補を添えてエラーを返す。

```
{"status": "unknown_entity",
 "message": "'長野大学' は本課題に登録された事物ではありません。",
 "did_you_mean": ["公立諏訪東京理科大学", "組合立諏訪中央病院"],
 "hint": "ゴール文に登場する事物はrun開始時に登録済みです。新しい事物を追加する場合は
          register_entity を明示的に呼び、出典を添えてください。"}
```

新規事物の登録自体は禁止しない（web_searchで正当に発見した事物はある）。ただし
`origin='discovered'`として明確に区別し、`citations`必須とする。**禁止ではなく区別**に
留めるのは、機械的な全面禁止がBL-158型のデッドロック（唯一の出力手段が塞がれる）を
招くという、このプロジェクトが繰り返し確認してきた教訓による。

### 2.5 地理属性の自動整合チェック

`address`と`coordinates`の両方を持つ事物に対し、
**保存された住所を再ジオコーディングして保存座標と一致するか**を検証する
`verify_entity_geo`ツールを設ける（Detector向け）。

BL-203で導入した`precision`フィールドと組み合わせ、以下を機械的に判定できる：

- 保存座標が`area_centroid`由来（＝大字の代表点）である
- 保存住所を引き直すと`point`で解決でき、かつ座標が数km離れている

→ **「誤った場所の正しい実測値」をピンポイントで検出できる。**

自動実行ではなくDetectorが呼ぶツールとするのは、GSI APIへの負荷（1秒スロットリング）と、
全属性への機械的強制がBL-042/BL-188/BL-194の「プロンプト誘導のみ」標準方針から
外れるためである。

### 2.6 `verified_facts`との棲み分け（置き換えではなく併存）

| 保存先 | 対象 | 例 |
|---|---|---|
| `entity_attributes` | **名前を持つ実世界の事物**についての事実 | 諏訪中央病院の住所・座標・標高 |
| `verified_facts` | 事物に属さない大域スカラー・導出値 | CapEx上限1億円、高齢化率30.7%、必要車両台数 |

`verified_facts`を置き換えない。予算上限のような「どの事物の属性でもない値」を無理に
事物へ押し込むと不自然なモデルになるためである。既存の`read_verified_fact`の挙動も変えない。

### 2.7 ホワイトボードとの関係

- **レジストリ＝真実の源（source of truth）**、**ホワイトボード＝人間向けの提示**。
- Expertは拠点マトリクスを記憶からではなく`read_entity`の結果から組み立てる。
- Detectorはホワイトボード上の数値をレジストリと突き合わせられる（現在は突き合わせ先が
  存在しない）。

これはBL-202で扱った「編集のたびに古い記述が復活する」問題の緩和にも効く。
本文が唯一の保存先である限り、部分編集の失敗＝データの損失だが、レジストリがあれば
本文が壊れても再生成できる。

---

## 3. 却下した代替案

| 案 | 却下理由 |
|---|---|
| `verified_facts`の`value`をJSON構造化するだけ（新テーブルなし） | 属性ごとの出典・確度・所有タスクを列として持てず、1.2の問題が解決しない。またSQLで「この事物の属性一覧」を引けず、1.4の再利用も改善しない |
| 属性名も型も事前定義したスキーマ（`places`テーブル等） | ドメインごとにスキーマ設計が必要になり、汎用エージェントとして破綻する。ユーザー提案の「属性は対象や要件によりいくらでも可変」という要件に反する |
| 事物の登録をLLM判断のみに委ね、正典名チェックを設けない | 構造化しただけでハルシネーションは素通りする（器を変えても中身の検証にならない）。2.3の部分一致チェックは客観的かつ低コストで、BL-203の事故を実際に止められる |
| 未登録事物への書き込みを全面禁止 | web_searchで正当に発見した事物を書けなくなり、BL-158型のデッドロックを招く。`origin`で区別する方が安全 |
| ゴール文からの抽出を廃し、開発者が`docs/refs/`へ手書き | 抽出のハルシネーションは無くなるが、ゴールを変えるたびに手作業が発生し、CELAの汎用性を損なう。2.3の機械チェックがあれば抽出でも十分な精度が得られる |

---

## 4. スコープ境界（v1でやらないこと）

このプロジェクトは、足した機構が次の不整合を生むパターンを既に経験している
（BL-076「注釈を含めろ」とBL-193「注釈を含めるな」がプロンプト内で矛盾したまま
58回のedits失敗を生んだ事故）。したがってv1は以下を**やらない**。

- `verified_facts`からのデータ移行（併存させる）
- 事物間の関係（`distance_between`等）のモデル化 — 区間の距離は当面ホワイトボードと
  `verified_facts`のまま。関係のモデル化は事物が安定してから
- 属性の履歴（版管理）— 上書きのみ。`agreements`が既に決定履歴を持つ
- タスクスコープ（`owns_variables`）との自動突き合わせ — Detectorのプロンプト誘導に留める
- Expert以外のノード（Facilitator/Reflection等）への書き込み権限 — 読み取りのみ

---

## 5. 実装計画

### 5.1 新規ツール（3本）

| ツール | 権限 | 用途 |
|---|---|---|
| `register_entity` | Expert | 新規事物の登録（`origin='discovered'`、citations必須） |
| `write_entity_attribute` | Expert | 属性の記録・更新。未登録名は`did_you_mean`付きで拒否 |
| `read_entity` | Expert / Detector | 事物と全属性の取得。`entity_type`での一覧も可 |
| `verify_entity_geo` | Detector | 住所↔座標の整合を再ジオコーディングで検算（2.5） |

**懸念**：Expertの現在のツール数は17本で、3〜4本追加すると20本を超える。
プロンプトのツール一覧文も4箇所（Expert2経路・Detector2パス）で更新が必要になる。
`register_entity`を`write_entity_attribute`の`allow_new_entity=true`フラグへ畳んで
2本に減らす案もある（要確認事項2）。

### 5.2 実装順序

1. スキーマ2テーブル＋マイグレーション（既存の`_ensure_*_columns`パターンに準拠）
2. ゴール文からの初期登録ノード（正典名の部分一致チェック込み）
3. ツール3〜4本と`TOOL_DISPATCH`配線
4. Expert/Detectorのプロンプト（ツール一覧文4箇所＋利用方針）
5. テスト
6. `docs/design`更新（issue_backlog / decision_log / decision_lineage）

### 5.3 テスト計画

- 正典名チェック：ゴール文に無い名称は`origin='goal_text'`で登録できない
  （「長野大学」の実データで回帰テスト化）
- 同一性ガード：未登録名への属性書き込みが`did_you_mean`付きで拒否される
- 出典封筒：`citations`未指定の`confirmed`は拒否、または`provisional`へ降格
- `verify_entity_geo`：`area_centroid`由来の座標と住所再解決の乖離を検出する
  （BL-203の実データ＝豊平の代表点1,475m vs 番地指定894.2m で回帰テスト化）
- 併存：`verified_facts`の既存挙動が変わらないこと
- 配線：Expert2経路・Detector2パスへのツール付与

---

## 6. 要確認事項（実装前にユーザー判断が必要）

1. **ゴール文からの初期登録を、どのタイミング・どのノードで行うか。**
   本設計は`task_planner`の前段に新規ノードを置く案だが、既存グラフのトポロジーを
   変えることになる。`task_planner`の中で行う（新規ノードを作らない）案もある。

2. **ツール本数**：`register_entity`を独立させるか、`write_entity_attribute`の
   フラグへ畳んで2本に抑えるか。独立させる方が意図が明示的だが、ツール一覧が長くなる。

3. **`revise_goal`でゴール文が改定されたときの再検証**。改定により正典名が変わった／
   消えた事物をどう扱うか（BL-168が`verified_facts`へ「整合性未確認」警告を付記する
   先例を持つ。同じ扱いにするのが自然と考える）。

4. **適用範囲**：v1を「place型の事物」に絞るか、最初から全事物型を許すか。
   スキーマ上は`entity_type`が自由なので絞る必要はないが、プロンプトでの誘導を
   地理に絞る方が検証しやすい。

---

## 7. 期待される効果と、効果を測る観点

- **BL-203の再発防止**：「長野大学」は正典名チェックで登録できず、仮に
  `origin='discovered'`で登録されても`verify_entity_geo`で住所↔座標の乖離が出る。
- **BL-195の強化**：実例の運用数値をそのまま転記した場合、属性単位で
  `citations type="web"`かつ`reason`に導出過程が無いことが機械的に見える。
- **再導出コストの削減**：2348で取れていた値が0901で失われた事象（1.4）が起きなくなる。
- **測り方**：次回以降のドライランで、①拠点の標高・座標が前ラウンドから劣化しないこと、
  ②ゴール文に無い施設名が成果物へ出現しないこと、③`web_search`の消費回数が
  同一事実の再検索で膨らまないこと（BL-199/BL-200と同じ観点）。
