# BL-224 基本設計: 判断の系譜（Decision Lineage）の実体化 — `relation_edges`による系譜グラフと時系列復元読み

> **作成**: 2026-08-13（Plan modeでの設計、Explore agent 1体・Plan agent 1体を併用）
> **状態**: 設計完了・実装未着手（`open`）
> **保存根拠**: AGENTS.md §4.7（BL単位の設計は`docs/design/back_log/BL-xxx/`へ要約せず原文のまま保存）

---

## Context（なぜこの変更を行うか）

### 発端

2026-08-13のセッションだけで、BL-219（task_plan_reviewerの指摘の消費経路欠落）・BL-220（thinkの
scratch_concernsの消費経路欠落）・BL-223（decision_extractorのDirective/Deferred橋渡しの消費経路
欠落）と、**「書き込み口はあるが消費経路が実装のたびにバラバラ・欠落する」同じ病気**が3回連続で
発生した。ユーザーはこれを「その場しのぎの継ぎはぎを重ねると境界での接続不良・取りこぼしが
増える」構造的リスクとして指摘し、再帰CTEを使った本格的な設計を選択した。

さらにユーザーは、当初AIが設計していた「事物の由来追跡」だけではCELAのコンセプトに届いていないと
指摘した——**「agreement、decisionなどDBで残している意思決定やその他の情報を漏れなく辿れて、
後続のAI、または人間が『なぜ今この方向で議論している？この値は、この手法は誰が、どうして採用
したのか？他はなぜ却下したのか？』というように、エージェント活動の中の情報を有機体的な
ネットワーク、系譜でつないで、思考の中で『なぜ？』という迷いを生まないようにすること」**。

### 要件定義書の再読で判明したこと（設計の前提が変わった）

`docs/design/要件定義書_v35.md`を読み直した結果、**本件は新機能の追加ではなく、要件定義が既に
定義済みでありながら実装が未消費・未完成のまま残っている系譜要件の実体化**であることが判明した。

**決定的な発見**: 要件定義書§4.2（`agreements`テーブル定義、「★V23判断系譜コア・スキーマ拡張」）は
`depends_on`列をこう定義している:

```sql
depends_on TEXT,  -- 依存する親Agreement IDのJSON配列 (DAG系譜)
```

つまり`agreements.depends_on`は「たまたま使われていない列」ではなく、**要件定義が「DAG系譜」と
名指しした、判断の系譜そのものの実装**である。それが実装では書き込み時の存在検証
（`cela_main.py:3367-3375`）にしか使われず、以後どこからも`SELECT`されない完全な死蔵状態にある
（AGENTS.md §15.4「誰も消費しない記録は仕組みではない」の、要件定義レベルでの実例）。

**関連する要件の実装状況（コードを実読して確認、付録B.1の記載は古い箇所があるため実コードを優先）:**

| 要件 | 内容 | 実装状況（実コード確認） |
|------|------|--------------------------|
| F-3.5 | DecisionPair（What/Why物理分離） | ✅ `decision_what`/`reason_why`列として実装済み |
| F-3.6 | 負の理由（Rejected）の徹底資産化 | ✅ `status='Rejected'`で永続化され、`_build_agreements_context`が`⚠️[却下事項]`＋理由付きでコンテキストへ含めている（`cela_main.py:7514-7515`） |
| F-8.2 | Hydrate 5節の「Why（判断系譜：正負の理由）」 | 🟡 正負とも同じ平坦なリストに並ぶのみ。**どの決定がどの決定を前提にしているかの接続は無い** |
| §4.2 | `depends_on`＝DAG系譜 | ❌ **書き込まれるのみ、一切消費されない（死蔵）** |
| F-8.4(2) | 時系列復元読み（「その論点がどう変遷して現在の結論に至ったか」を時系列のストーリーとして再構成） | ❌ 未実装。現状は`_find_prior_superseded`（`cela_main.py:7571-7584`）が**同一topic文字列・同一entry_typeのSuperseded行から直近1件だけ**を返す。①1ホップのみで変遷の連鎖をたどれない、②topic文字列一致に依存するためBL-084が既にDeliverableで問題化した「topic文字列ドリフト」に構造的に脆い |
| F-3.9 | 構造化ファクトストア（値・理由・出典） | ✅ `verified_facts`に`reason`/`citations`/`confidence`として実装済み |

つまり、**「点」（個々の判断・値とその理由）はほぼ揃っているが、「線」（それらをつなぐ系譜）が
無い**。ユーザーの言う「有機体的なネットワーク」が、要件定義では`depends_on`＝DAG系譜として
定義されていながら、実装では線が引かれないまま点が並んでいる状態である。

さらに、点の側も3つの別々のIDスペースに分断されている——`agreements`（判断、id）、
`verified_facts`（スカラー変数、variable_name）、`entities`/`entity_attributes`（BL-204の固有名詞
レジストリ、entity_id+attr_name）。ユーザーが指摘した通り、`entity_relations`のような素朴な
テーブルでは`verified_facts`同士すら繋げない。**同じ汎用エッジテーブルのパターンを、どの
IDスペースの行も指せるように一般化する**必要がある。

### 本設計のゴール

「なぜ今この方向なのか」「この値・この手法は誰がどうして採用したのか」「他はなぜ却下されたのか」を、
**後続のAIも人間も、迷わず機械的にたどれる**ようにする。そのために:

1. 3つのIDスペースを横断する汎用エッジテーブル`relation_edges`を新設する
2. 死蔵している`agreements.depends_on`（＝要件定義の言うDAG系譜）を、このテーブルへ流し込んで
   **実際に消費される線へ復活させる**
3. 再帰CTEでN段の系譜を前方・後方の両方向にたどれるようにする
4. F-8.4(2)の時系列復元読みを、topic文字列一致ではなく**エッジに基づく確実な連鎖**として実装する
5. たどった結果を**AIが毎ターン見るHydrateコンテキスト**と**人間が見る監査レポート**の両方へ流す

---

## スキーマ

```sql
-- [BL-224] 判断・値・事物を横断する系譜（Lineage）グラフの辺。
-- 要件定義書§4.2がagreements.depends_onを「DAG系譜」と定義しながら、その実装が
-- 書き込み時の存在検証にしか使われず一切消費されていなかった（§15.4）ため、
-- 本テーブルへ流し込んで実際にたどれる線として復活させる。
-- agreements(id) / verified_facts(variable_name) / entity_attributes(entity_id, attr_name)は
-- それぞれ別のIDスペースを持つため、型プレフィックス付きの参照文字列で統一する。
CREATE TABLE IF NOT EXISTS relation_edges (
    id TEXT PRIMARY KEY,               -- "REL-xxx"（_new_record_id、BL-215の一元採番を使用）
    run_id TEXT NOT NULL,
    from_ref TEXT NOT NULL,            -- 上流（前提・旧版・入力）
    to_ref TEXT NOT NULL,              -- 下流（結論・新版・導出結果）
    relation_type TEXT NOT NULL,       -- depends_on | supersedes | derived_from
    reason TEXT NOT NULL DEFAULT '',   -- この線が引かれた理由（supersedesでは「なぜ旧案を棄却し新案を採ったか」）
    created_by TEXT NOT NULL,          -- caller_role（confirmed_by/proposed_byと同じ規約）
    created_at REAL NOT NULL,
    source_task_id TEXT DEFAULT '',
    source_phase_id TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_relation_edges_run_from ON relation_edges(run_id, from_ref);
CREATE INDEX IF NOT EXISTS idx_relation_edges_run_to ON relation_edges(run_id, to_ref);
```

### 参照方式（ref）

| プレフィックス | 指す先 | 存在検証 |
|----------------|--------|----------|
| `agreement:<id>` | `agreements.id` | ✅ 実表の行 |
| `fact:<variable_name>` | `verified_facts.variable_name` | ✅ 実表の行 |
| `entity:<entity_id>:<attr_name>` | `entity_attributes`の複合キー | ✅ 実表の行 |

- **裸の`entity:<entity_id>`は不可**: `entities`表は`canonical_name`/`entity_type`/`aliases`/`origin`
  のみで値を持たず（値を持つのは`entity_attributes`の各行）、「エンティティそのものを導出する」
  概念が実データ上存在しないため。BL-204の「属性ごとに出典と確度が付く」思想とも整合する。
- **`task:<task_id>`は不可**: タスクは`state["phases"]`のJSON内にしか存在せず、実表の行として
  検証できない。検証不能な参照型を混ぜることは、まさに`agreements.depends_on`が陥った
  「受理されるが意味を持たない」状態を新テーブル内で再現することになる。タスク粒度の依存は
  既存の`Task.depends_on`＋`_build_task_scope_context`（実際に動いている唯一の機構）のまま残す。

### 関係種別（relation_type）— 3種のみ

| 種別 | 意味 | 由来する要件 |
|------|------|--------------|
| `depends_on` | `to_ref`は`from_ref`を前提として成立する判断・値 | 要件定義§4.2「DAG系譜」 |
| `supersedes` | `from_ref`（旧案・棄却）が`to_ref`（新案・採用）に置き換えられた。`reason`に負の理由 | F-3.6・F-8.2「正負の理由」 |
| `derived_from` | `to_ref`は`from_ref`から計算・仮定して導出された値 | F-3.9・BL-219（8,500人問題） |

グラフ走査上は3種とも同一に扱う（`relation_type IN (...)`で絞れる形にする）。種別を分けるのは
表示・説明のためであり、`confirms`/`contradicts`等の投機的な語彙は追加しない。

---

## 書き込み経路

**原則: LLMの協力に依存しない機械的な線を骨格とし、LLMが足す線は付加価値とする**（AGENTS.md
§15.3「機械的検証をエージェントの自己申告より優先する」）。LLMが`depends_on`を書き忘れても
系譜の骨格が途切れないようにする。

### W1（機械的・骨格）: 決定 → 値
`_commit_agreement_from_tool`の`confirmed_variables`ループ（`cela_main.py:3444-3458`）で
`upsert_verified_fact`が成功するたびに、`agreement:<新しいagreement id>` → `fact:<variable_name>`
の`derived_from`エッジを**無条件・自動で**書く。「この値はどの決定が生んだか」＝5W1Hの
「誰が・なぜ」を値から引けるようにする骨格であり、LLMの記入に一切依存しない。
`write_entity_attribute`側も同様に`agreement:` → `entity:<id>:<attr>`を書く。

### W2（機械的・骨格）: 新版 → 旧版（負の理由）
`db_supersede_agreement`は5箇所（`cela_main.py:3139, 3284, 3288, 5904, 12903`）から呼ばれるが、
呼び出し時点では置換先の新agreement idが未採番の箇所があるため、関数内の単一フックは取れない。
新規ヘルパー`_link_supersession(conn, run_id, old_agreement_id, new_agreement_id, reason)`を設け、
新idが確定した直後に各箇所から明示的に呼ぶ。`reason`にはBL-050が既に`reason_why`へ要求している
「前の値から何故・どう変わったのか」をそのまま転記する（LLMに新たな説明義務を課さない）。
**5箇所すべてを個別に確認すること**（§15.2）——ゴール改定に伴う一括Superseded化など1:1の新旧対応が
無い箇所は呼ばない判断でよいが、その理由をコードコメントに残す。

### W3（LLM記入・既存引数の復活）: 判断 → 判断
`write_agreement`の既存引数`depends_on`（既にツールスキーマにあり、`cela_main.py:2295-2306`で
「system promptの決定事項DBに表示されている`[42]`のような番号を入れよ」とLLMへ指示済み、
書き込み時の存在検証も実装済み）を、**`agreements`列への保存に加えて`relation_edges`へも
`depends_on`エッジとして流し込む**。これにより死蔵していた列が初めて消費される。
`agreements.depends_on`列自体は後方互換のため残す（既存行のデータを失わない）。

### W4（LLM記入・新規）: 値 → 値
`confirmed_variables[]`の各要素に任意項目`derived_from: list[str]`
（`"fact:<name>"` / `"entity:<id>:<attr>"`の配列）を追加し、`derived_from`エッジを書く。
BL-219の「8,500人がどの仮定から出たか」を構造化する経路。
無効な参照はfactの保存自体は失敗させず、エッジのみスキップして`warning`をツール結果へ返す
（既存の`protected_warning`と同じパターン、`cela_main.py:3460-3464`）。

---

## 消費経路（本設計の核心。ここが欠けると§15.4の4例目になる）

### C1: AIが毎ターン見る系譜 — `_build_agreements_context`の時系列復元読み（F-8.4(2)実装）

現状`_build_agreements_context`は各agreementの直後に`_find_prior_superseded`で**直近1件だけ**の
旧版を差分表示している（topic文字列一致、BL-084のドリフト問題に脆い）。これを
`_get_lineage_chain(conn, run_id, "agreement:<id>", max_depth)`によるエッジベースの
**変遷の全連鎖**に置き換える。F-8.4(2)が要求する「その論点がどう変遷して現在の結論に至ったか」を
時系列順のストーリーとして提示する。表示例:

```
[AG-xxx] ✅[確定合意] 車両台数: 3台（理由: ...）
   └─ 系譜: 5台（棄却: 予算超過、task_4_1の試算で1.4倍）→ 4台（棄却: ピーク輸送力不足）→ 3台（現行）
   └─ 前提: [AG-yyy] 予算上限1,000万円 / fact:budget_cap
```

これがユーザーの言う「後続のAIが『なぜ今この方向で議論しているのか』で迷わない」ための本体である。
トークン量が増えるため、**表示は`max_depth`と1エントリあたりの行数で上限を設ける**（既存の
`_find_prior_superseded`が「全履歴を出すとトークンコストが膨らむため直前版のみ」としていた判断を、
無制限に戻すのではなく上限付きで緩和する）。

### C2: 人間が見る系譜 — `_audit_report`の`--ref`拡張（BL-222/D-199の型を踏襲）

`_audit_report`（`cela_main.py:6825-6878`）に`--ref`フィルタを追加し、指定した
agreement/fact/entity属性について前方・後方の系譜を5W1Hフォーマットで表示する。
`ref`がagreementなら「なぜ採用され、何が棄却されたか」、factなら「どの決定が生み、何から導出され、
何がこれに依存しているか」。読み取り専用・LLM呼び出しなし・WALモードで実行中でも安全という
BL-222の型をそのまま使う。

### C3: アンカリング検出 — `task_plan_reviewer_node`（BL-219の消費経路を再利用）

`task_plan_reviewer_node`（`cela_main.py:12052`）で、レビュー対象タスクの`owns_variables`のうち
`confidence='provisional'`なものについて後方系譜をたどり、遡った先も`expert_calculation`だけを
根拠とする暫定値だった場合、**BL-219で配線済みの`per_task_comments` → `_get_reviewer_comments_text`
→ `_build_task_scope_context` → Expert/User AIプロンプト**という既存経路へ流す。新しい注入
ヘルパーは作らない（BL-219が作った線に、根拠を「その場の気づき」から「たどれるグラフ」へ
差し替えるだけ）。

### C4: 変更の前方伝播 — 上流が変わったら下流に印を付ける

`upsert_verified_fact`（`cela_main.py:6699`）・`upsert_entity_attribute`（`cela_main.py:7066`）は
それぞれの表への唯一のUPSERT経路である（確認済み）。両関数内で、既に取得済みの`_existing`
（`cela_main.py:6713-6716`）と比較して値が実際に変化した場合のみ`_get_forward_dependents`で下流を
たどり、各依存先の`reason`列へ**BL-168と同じ冪等プレフィックス**
（`cela_main.py:2839, 2850-2851`の`⚠️[BL-168: ...]`と同型、既に付いていればスキップ）を追記する。
新しい`is_stale`列は作らない（それ自体が第2の並行機構になる）。**呼び出し元ではなく関数内部で
フックする**ため、どの書き込み経路を通っても構造的に迂回できない（§15.3）。

`reason`列は`read_verified_fact`・`read_entity`・`_audit_report`・毎ターン注入される
`_build_task_scope_context`の`verified_facts_json`（`cela_main.py:7759-7760`）に既に表示されている
ため、**新しいプロンプト注入を追加しなくても既存の表示経路が可視化を兼ねる**。

---

## 再帰CTE設計

```sql
-- 後方（この結論は何に立脚しているか）。前方は from/to を入れ替えたミラー。
WITH RECURSIVE backward(ref, depth) AS (
    SELECT from_ref, 1 FROM relation_edges WHERE run_id = ? AND to_ref = ?
  UNION ALL
    SELECT e.from_ref, b.depth + 1
    FROM relation_edges e JOIN backward b ON e.to_ref = b.ref
    WHERE e.run_id = ? AND b.depth < :max_depth
)
SELECT DISTINCT ref, MIN(depth) AS depth FROM backward GROUP BY ref ORDER BY depth;
```

- 本コードベース初の再帰CTE（`WITH RECURSIVE`はコードベースに前例ゼロ、確認済み）。
- **サイクル対策**: SQLiteの再帰CTEにはサイクル検知が無い。`from_ref`/`to_ref`に任意文字列が
  入りうる以上、経路を文字列連結して`LIKE`で判定する方式は採らない。Python側で訪問済みrefの
  `set`を持ち1階層ずつ`conn.execute`する反復方式か、SQLiteのJSON関数で経路をJSON配列として
  持ち`json_each`で判定する方式のいずれかとする（実装時に可読性で選択してよい）。
- `_get_lineage_chain`（C1用、時系列順に整形）は`_get_backward_dependencies`の結果を
  `relation_type='supersedes'`に絞り`created_at`昇順に並べる薄いラッパーとする。

---

## 変更対象ファイル

- `cela_main.py`:
  - スキーマブロック（~5480-5670）へ`relation_edges`＋インデックス
  - `_write_relation_edge` / `_get_backward_dependencies` / `_get_forward_dependents` /
    `_get_lineage_chain` / `_link_supersession` 新設
  - `_commit_agreement_from_tool`（~3444-3458、W1・W3・W4の配線）
  - `write_entity_attribute`ハンドラ（~1821、W1・W4）
  - `db_supersede_agreement`呼び出し5箇所（~3139, 3284, 3288, 5904, 12903）へ`_link_supersession`（W2、§15.2で個別確認）
  - `upsert_verified_fact`（~6699）・`upsert_entity_attribute`（~7066）へ前方伝播フック（C4）
  - `_build_agreements_context`（~7451-7570）の`_find_prior_superseded`呼び出しを
    `_get_lineage_chain`へ置き換え（C1）
  - `_audit_report`（~6825）＋CLI引数へ`--ref`（C2）
  - `task_plan_reviewer_node`（~12052）へ後方系譜チェック（C3）
  - `WRITE_AGREEMENT_TOOL`の`confirmed_variables`スキーマへ`derived_from`、および`depends_on`の
    説明文へ「ここに書いた依存は系譜として後続のAIがたどれる」旨を追記（~2295-2306）
  - task_planner/Expertのプロンプト（~8068、~8467）へ`derived_from`記入を促す一文を
    **共有ヘルパー1本**から両方へ流す（§15.1、文言の二重管理を作らない）
- `tests/test_bl224_relation_edges.py`（新規）
- `docs/design/back_log/issue_backlog.md`: BL-224として起票
- `docs/design/decision_log.md`: 新規D。①`agreements.depends_on`を「放置」ではなく
  「relation_edgesへ流し込んで復活」とした理由（要件定義§4.2がDAG系譜と定義しているため）、
  ②`task:`参照型を採らない理由、③D-196との関係（置き換えではなく、立案時のみ・一度きりだった
  対策を恒久的にたどれる形へ一般化）、④BL-168のstaleness marker方式を再利用し新列を作らない理由
- `docs/design/decision_lineage.md`（論点160想定）: 本設計に至った対話の経緯

---

## 未決事項（ユーザー判断）

1. **最大探索深度**: 10を提案（新規の重要定数のためAGENTS.md §7により明示承認が必要）。
   あわせてC1のHydrate表示で1エントリあたり何段まで見せるか（3段程度を提案）。
2. **置換を伴わない単独のRejected**: 本設計の`supersedes`エッジは「旧案が新案に置き換えられた」
   1:1の対応がある場合を対象とする。代案が無いまま却下されただけの提案は、既に
   `status='Rejected'`＋`reason_why`として保存され`⚠️[却下事項]`でコンテキストにも出ている
   （F-3.6は満たされている）ためエッジは張らない設計とした。これで足りるか確認したい。
3. **実装の分割**: スキーマ＋書き込み4経路＋消費4経路と規模が大きい。「スキーマ＋W1/W2/W3
   （機械的骨格）＋C2（監査レポート）」を先に入れて実ドライランで系譜が実際に繋がることを
   確認してから、C1（Hydrate表示、トークン量への影響が最大）・C3・C4・W4を追加する2段階を推奨。

---

## 検証

- `python -m py_compile cela_main.py`
- 再帰CTEはLLM不要のためDB直結ユニットテスト（線形4-5ノード＋分岐＋意図的サイクル1件＋
  深度上限到達）で正しさを検証
- 系譜の実体テスト: あるtopicをCREATE→UPDATE→UPDATEと変遷させ、`_get_lineage_chain`が
  **3世代すべてを時系列順に**返すこと
- 機械的骨格テスト: LLMが`depends_on`/`derived_from`を一切書かなくても、W1（決定→値）と
  W2（新版→旧版）だけで系譜が繋がること
- 書き込み4経路・消費4経路を**個別に**リバートし、対応テストの失敗を確認（AGENTS.md §17.1）
- フルオフラインスイート
- 実LLMでの最小ドライラン（AGENTS.md §17.2）: (a) 実際のツール呼び出しでエッジが書かれる、
  (b) 提案を置き換えるシナリオで`--audit-report --ref agreement:<id>`が棄却された旧案と負の理由を
  表示する、(c) 上流値の変更で下流の`reason`に陳腐化マーカーが付く、(d) C1導入後はHydrate
  コンテキストに変遷の連鎖が現れ、トークン量が許容範囲に収まること
