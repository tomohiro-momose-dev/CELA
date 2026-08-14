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
`_write_agreement_impl`（実際は `_commit_agreement_from_tool` の内部、`confirmed_variables` ループ）で
`upsert_verified_fact`が成功するたびに、`agreement:<新しいagreement id>` → `fact:<variable_name>`
の`derived_from`エッジを**無条件・自動で**書く。「この値はどの決定が生んだか」＝5W1Hの
「誰が・なぜ」を値から引けるようにする骨格であり、LLMの記入に一切依存しない。
`write_entity_attribute`側も同様に`agreement:` → `entity:<id>:<attr>`を書く。ただし entity 側は
agreement id 引数を持たない（`upsert_entity_attribute` シグネチャ確認済み、M2）ため、親を
`task_id → phase_id → 計画センチネル`の順に探して結ぶブリッジ方式をとる（詳細は A1 解決策4・M2 を参照）。

### W2（機械的・骨格）: 新版 → 旧版（負の理由）
`db_supersede_agreement`は以下の呼び出し箇所から呼ばれる（行番号はドリフトするため関数名で引く、§16.2/独立レビューM5）:
- `write_agreement` の edits 経路 3箇所（UPDATE/SUPERSEDE ブランチ）— 置換先の新 id は同スコープで `_new_record_id("AG")` により確定するため、`_link_supersession(old, new, reason)` を直後に呼べる。
- `_resolve_directive_for_task` 内 1箇所 — 直後に新 id あり。
- `decision_extractor` の再抽出フォールバック 1箇所（`db_supersede_agreement(a["id"])` の直後に 12965 付近で新 id が生成される）。

呼び出し時点で置換先の新 id が未採番な箇所があるため、関数内の単一フックは取れない。
新規ヘルパー`_link_supersession(conn, run_id, old_agreement_id, new_agreement_id, reason)`を設け、
新 id が確定した直後に各箇所から明示的に呼ぶ。`reason`にはBL-050が既に`reason_why`へ要求している
「前の値から何故・どう変わったのか」をそのまま転記する（LLMに新たな説明義務を課さない）。
**全呼び出し箇所を個別に確認すること**（§15.2）。ただし **`decision_extractor` の再抽出フォールバック（12923 付近）は supersession エッジの対象外とする**——ここは `write_agreement` が使われなかった場合の安全網であり、生成される新 agreement は「同一 topic の再抽出」であって「旧版 `a["id"]` の意図的な差し替え」ではない。ここでエッジを張ると「再抽出」が「系譜上の差し替え」と誤表示され、chain が誤導される（独立レビューM1の勧告を採用）。1:1 の新旧対応が無い箇所（ゴール改定に伴う一括 Superseded 化等）も同様に呼ばない判断とし、その理由をコードコメントに残す。

### W3（LLM記入・既存引数の復活）: 判断 → 判断
`write_agreement`の既存引数`depends_on`（既にツールスキーマにあり、`cela_main.py:2295-2306`で
定義済み、書き込み時の存在検証も実装済み＝`3367-3375`）を、**`agreements`列への保存に加えて
`relation_edges`へも`depends_on`エッジとして流し込む**。これにより死蔵していた列が初めて消費される。

**マッピング（A4 解決策・独立レビューA4）**:
`depends_on` に LLM が書く値は**実際の agreement id そのもの**である。根拠:
- system prompt は各合意を `[AG-1765000000000-a1b2c3]` のように表示する（`cela_main.py:7578`
  `lines.append(f"[{agreement_id}] ...")`、`agreement_id = a.get("id")`）。
- id の実体は `_new_record_id("AG")` が `f"AG-{int(time.time()*1000)}-{uuid4().hex[:6]}"` を返す
  （`2210`）。
- 検証 `3367-3375` は `SELECT 1 FROM agreements WHERE id=? AND run_id=?` に `dep_id` を直接渡す
  ——つまり「`[AG-xxxx]` に表示された文字列をそのまま書け」が正解であり、検証もそれを期待する。

したがって **W3 の ref 変換は「`agreement:` プレフィックスを付けるだけ」** で翻訳表は不要:
`edge_ref = f"agreement:{dep_id}"`（dep_id は `3367-3375` を通過済みの実 id）。

**エッジの方向**（スキーマ定義「`to_ref` は `from_ref` を前提として成立する」に従う）:
新規合意 X が `depends_on=[Y]` を持つなら、Y が前提・X が依拠先なので
`from_ref=f"agreement:{Y}"`, `to_ref=f"agreement:{X}"`, `relation_type='depends_on'` の1本を書く。
これは A3 指定の C1「前提」行（後方 `depends_on` 走査で `from_ref` を得る）と整合する。

**検証の再利用**（§15.1 単一ソース・§15.4 非対称回避）:
新しい検証は書かず、`3367-3375` をそのまま「エッジ書き込みのゲート」として使う。`depends_on`
リストはこの検証を通過した実 id だけが残るので、W3 は検証済みリストから直接エッジを書く。
さらに `_write_relation_edge`（単一ゲート、A1 解決策1）が書き込み時に両 ref の実在を `EXISTS` で
再検証するため、二重に守られる。`agreements.depends_on` 列自体は後方互換で残す（既存行のデータ
を失わない）。

**スキーマ説明の修正（コード修正・W3 と同一変更セット）**: `cela_main.py:2295-2306` の `depends_on` 説明は
現在 *"use the bracketed number shown before each entry there, e.g. '[42]', ... -> depends_on: ['42']"*
と書かれているが、これは**実態（`AG-xxxx`）と食い違う古い記述**で、LLM が指示通り `'42'` を書くと
`3367-3375` 検証で弾かれる（§15.4 壊れた ref の懸念そのもの）。**この修正は W3 と同一の Phase 1
変更セット（同一 PR / 同一 commit）に必ず含める**（独立レビューN4・決定）。理由: スキーマ修正を
別 PR に分けると、(1) PR 間で一時的に「LLM が `'42'` を書き、検証 3367-3375 で弾かれる →
W3 の `agreement:{dep_id}` エッジが空になる」という壊れた状態が本番に露出し、(2) §15.4 の
「書き込み口はあるが ref が壊れて消費経路が繋がらない」というまさに本 BL が直そうとしている欠陥を
自ら再現してしまう。よって `'[42]' -> depends_on: ['42']` を
`'[AG-1765000000000-a1b2c3]' -> depends_on: ['AG-1765...-a1b2c3']` へ修正する箇所は、W3 の
`relation_edges` 書き込み配線と同じ変更としてレビュー・コミットする。

**B8 バックフィル**（後日別作業）: 既存 `agreements.depends_on` 列（実 id の配列）から同上の
`f"agreement:{dep_id}"` → `f"agreement:{self_id}"` エッジを生成する。マッピングは本 W3 と同一。

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
`_get_lineage_chain(conn, run_id, "agreement:<id>", max_depth)`（内部は `_traverse_lineage` の
`relation_type='supersedes'` ラッパー）によるエッジベースの**変遷の全連鎖**に置き換える。さらに
**「前提」行は別トラバーサル**で描く（A3 解決）。F-8.4(2)が要求する「その論点がどう変遷して現在の
結論に至ったか」と「何を前提としているか」を、時系列ストーリーとして提示する。表示例:

```
[AG-xxx] ✅[確定合意] 車両台数: 3台（理由: ...）
   └─ 系譜: 5台（棄却: 予算超過、task_4_1の試算で1.4倍）→ 4台（棄却: ピーク輸送力不足）→ 3台（現行）
   └─ 前提: [AG-yyy] 予算上限1,000万円 / fact:budget_cap
```

**A3（depends_on 後方エッジの設計・ブロッキング解消）**: 旧設計の `_get_lineage_chain` は
`relation_type='supersedes'` のみを返し、「前提」行のデータソースが無かった。これを解消する:
- **クエリ**: `_traverse_lineage(conn, run_id, start_ref=f"agreement:{id}", direction="backward",
  max_depth=max_depth, relation_types=['depends_on'])` で、この合意が `to_ref` となっている
  `depends_on` エッジの `from_ref`（＝前提となる agreement / fact / entity）を取得する。
  from_ref の種別に応じて解決表示: `agreement:<id>`→decision_what/reason_why、
  `fact:<name>`→value/reason/citations、`entity:<id>:<attr>`→value（§15.3: 実表から解決、存在しない
  ref は `EXISTS` でスキップ）。
- **描画分岐**: `_build_agreements_context` は各 agreement につき (1) supersedes 連鎖（既存・
  `_get_lineage_chain`）、(2) depends_on 前提（本追加・`_traverse_lineage(relation_types=['depends_on'])`）
  の2回呼び、前者を「系譜」行、後者を「前提」行として描く。`max_depth` は両者共通（トークン上限）。
- **単一ソース**: 前提は `relation_edges` からのみ読む（`agreements.depends_on` 列は W3 で relation_edges へ
  流し込まれるため、C1 は列を直接読まない）。W3 実装前の既存データは B8（backfill）で relation_edges へ
  投入され、そこで初めて「前提」行に出る（§15.1 単一ソース・§15.4 消費経路の前提）。
- **direction の扱い**: 前方（`depends_on` でこの合意を前提とする下流）は C1 表示には不要だが、
  C2（`_audit_report --ref`）の双方向系譜表示で再利用する（同じ `_traverse_lineage` を `direction="both"` で）。

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

### C3: アンカリング検出 — upsert 境界（ノード非依存・A2 解決）

**A2（ブロッキング）により書き直し**: 旧C3は `task_plan_reviewer_node` で `owns_variables` の
`confidence` を読んでいたが、(1) `owns_variables` は `list[str]`（変数名のみ、7181行）で confidence
フィールドは存在しない（スキーマ混同）、(2) `task_plan_reviewer_node`（12073付近）は実行開始前に1回
しか発火せず、その時点で `verified_facts` は未書き込み（タイミング誤り）。よって C3 を
**事実の正統な書き込み境界 `upsert_verified_fact`（6719）へ移動**する。

- **境界方式（ノード非依存）**: `upsert_verified_fact` は Expert(3451)・decision_extractor(12874/6790)・
  human-input(5744)・および**将来の task_planner/task_plan_reviewer**（両者とも既に `WRITE_AGREEMENT_TOOL`
  を持つ: 8243/12035）のすべての fact が通る単一入口。ここで捕捉すれば、どのノードが書いても
  provisional 値を拾える（§15.1 単一ソース・§15.3 機械的検証）。
- **捕捉条件**: `confidence='provisional'` で書かれた fact（スキーマ既定値、5682）。`owns_variables`
  ではなく **`verified_facts` の `confidence` 列**を読む（スキーマ混同解消）。
- **消費（段階1・軽量）**: その fact を `verified_facts_json`（毎ターン `_build_task_scope_context` で
  注入済み）へ「`[暫定]`」マーカ付きで表示するよう、表示ヘルパを1箇所修正するだけ。下流タスクが
  変数を読む際に自動で見える（新規注入経路不要、§15.4 既存消費経路再利用）。
- **消費（段階2・上流トラバーサル）**: `derived_from` エッジ確定**後**（W1/W4 コミット後）に
  `_traverse_lineage`（M3）で上流を辿り、根拠が `expert_calculation` のみで確定根拠の無い場合、
  BL-219 の `per_task_comments` → `_get_reviewer_comments_text` → `_build_task_scope_context` 経路で
  `source_task_id` へ「要検証: 根拠=推算のみ」を付与。新ヘルパーは作らない。
- **計画段階の概算登録は別BL**: 「task_planner/reviewer に重要な概算・Web探索値を
  `confidence='provisional'` で登録せよ」という挙動変更は **BL-224 のスコープ外**（§15.2 経路増・
  §15.1 共有ヘルパ介入・ユーザー合意要）。別 BL（計画概算の facts 登録）として起票し、クロスリンクする。
  本 C3 の境界方式はその別BLが実装されても自動でカバーする（同じ `upsert_verified_fact` を通るため）。
- **トランザクション境界の確定は Phase 2 着手時に行う（独立レビューN5・留意）**: C3 の `_traverse_lineage`
  呼び出しは `upsert_verified_fact` の**内部**に置く（§15.3 関数内フック）。ただし `upsert_verified_fact`
  は `plan_drafts` への内部 UPSERT を同一コネクション内で行う箇所があり、ここで `.commit()` を
  呼ぶ設計にすると、後続の C4（前方伝播）や C3 段階2（上流トラバーサル）の書き込みと**二重コミット
  ／トランザクション競合**を起こす恐れがある。Phase 2 着手時に (1) `upsert_verified_fact` 内の
  コミット境界を洗い出し、(2) `_traverse_lineage`／前方伝播の書き込みは **既存のトランザクション内**で
  行い、関数外の呼び出し元が責任を持って commit する設計にするか、(3) それが困難なら C3/C4 の
  フックを `upsert_verified_fact` の「戻り値確定後」の呼び出し元ラップに移すかを**明示に決定**する。
  本設計書は「関数内フック」を基本方針とするが、実装着手時のこの境界判定は Phase 2 の TODO として
  残す（§17 テストで二重コミット／競合を検証）。

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

- **トラバーサル実装（M3・B7確定）**: 上記再帰CTE スニペットは**実装しない**。理由: 本コードベースに
  前例ゼロ、かつ SQLite の再帰CTE にはサイクル検知が無く任意文字列 ref で経路を壊す恐れがある。
  代わりに **Python 反復トラバーサル（`visited` set によるサイクル安全）を単一実装**とし、
  ヘルパ `_traverse_lineage(conn, run_id, start_ref, direction, max_depth, relation_types=None)`
  として C5（trace_lineage ツール）・C1（Hydrate 表示）・C4（前方伝播）の3消費経路すべてが
  これを呼ぶ（§15.1 単一ソース）。上記 CTE はアルゴリズムの意図を示す参考スニペットに留める。
- `_get_backward_dependencies` / `_get_forward_dependents` / `_get_lineage_chain` はいずれも
  `_traverse_lineage` の薄いラッパーとする（`_get_lineage_chain` は `relation_type='supersedes'` に
  絞り `created_at` 昇順に並べる）。
- **run_id スコープ（M4）**: `relation_edges` は全クエリで `run_id` でパーティションされる。本 BL の
  系譜は **同一 run_id 内**に限定（クロス run 系譜は将来課題、`decision_log.md` へ記録）。ref は
  run 内ユニークな id（`agreements.id` / `verified_facts.variable_name` / `entity_attributes(entity_id,attr_name)`）を
  指す前提。`_traverse_lineage` も `run_id` を固定で絞る。

---

## 変更対象ファイル

- `cela_main.py`:
  - スキーマブロック（~5480-5670）へ`relation_edges`＋インデックス
  - `_write_relation_edge` / `_get_backward_dependencies` / `_get_forward_dependents` /
    `_get_lineage_chain` / `_link_supersession` 新設
  - `_write_agreement_impl`（実際は `_commit_agreement_from_tool` 内部、`confirmed_variables` ループ、W1・W3・W4の配線）
  - `write_entity_attribute`ハンドラ（W1・W4）
  - `db_supersede_agreement`呼び出し — `write_agreement`(edits 3箇所)・`_resolve_directive_for_task`(1箇所) へ`_link_supersession`（W2、§15.2で個別確認；decision_extractor フォールバックは除外・M1）
  - `upsert_verified_fact`・`upsert_entity_attribute`へ前方伝播フック（C4；entity は内部で task_id/phase_id ブリッジ・M2）
  - `_build_agreements_context`（~7451-7570）の`_find_prior_superseded`呼び出しを
    `_get_lineage_chain`へ置き換え（C1）
  - `_audit_report`（~6825）＋CLI引数へ`--ref`（C2）
  - `upsert_verified_fact`（6719）へ provisional 捕捉フック（C3・境界方式・A2解決；task_plan_reviewer_node は変更なし）
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

## 未決事項（ユーザー判断・全件解決済み → decision_log D-204）

1. **最大探索深度**: **N=10 で承認（AGENTS.md §7 明示承認・2026-08-14）**。様子見とし、実ドライランで
   トークン量／可読性のバランスを見て調整する。C1 の Hydrate 表示は1エントリにつき**3段**まで表示。
2. **単独の Rejected も系譜に含める（ユーザー判断・2026-08-14）**: 含めないと「rejected されず放置」
   または「暗黙的に承認されたように見える」ため、**単独棄却提案も系譜グラフに参加させる**。
   機構: (a) 棄却時に同一 topic の現行アクティブ合意 Y があれば `supersedes` エッジ
   `from_ref=agreement:<棄却X>` → `to_ref=agreement:<Y>` を張る（「X は Y に敗れた」＝系譜上の差し替えと
   同型）；(b) 現行合意が無い純粋単独棄却は to_ref を持てないためエッジは張らず、**`status='Rejected'`＋
   `⚠️[却下事項]` コンテキスト（既存・F-3.6 済）で常に表示**し、かつ `trace_lineage`／C1 が topic チェーンを
   走査する際に `Rejected` ステータスの合意を明示的に結果に含めることで「不可視」を防ぐ（新 relation_type は
   追加せず3種維持・§15.1）。
   **フック位置（独立レビューN2・決定）**: (a) の `supersedes` エッジを張るフックは
   **`_commit_agreement_from_tool` の `db_append_agreement` INSERT 直後**に置く（新 id を変数に
   捕捉してから）。新 id X と同一 topic/entry_type の現行アクティブ合意 Y を探し、存在すれば
   `_link_supersession(conn, run_id, old_agreement_id=Y, new_agreement_id=X, reason=rationale)`
   を呼び `from_ref=agreement:<X>` → `to_ref=agreement:<Y>` を書く。ガードは
   `status == 'Rejected'`（確定棄却のみ）＋「Y が実在する」の2条件。**これは W2（edit-wrapper の
   `supersede_agreement`）とは別のトリガー**であり、W2 の supersedes レイヤーを内側に重ねて
   ダブらせてはならない（W2 は「既存 Y を新 X に差し替える」編集経路、本フックは「棄却 X が現行 Y
   に敗れた」と記録する新規経路）。(c) **`decision_extractor_node` も同一ヘルパを呼ぶ**——実コード確認
   （12890/12996/13014）で、decision_extractor は Rejected 合意を `_commit_agreement_from_tool` を
   経由せず直接 `db_append_agreement`／`db_supersede_agreement` へ書くため、ここにフックを置かないと
   12923 等の経路で作られた Rejected が系譜から零れる。同じ `_link_supersession` 呼び出しを
   decision_extractor の Rejected 分岐（Y 探索＋ガード＝status=='Rejected'）からも行うよう W3 および
   C5 実装時に配線する（§15.4: 書き込み経路を増やすたび消費経路も確保）。
3. **実装の分割（承認済み・BL-224＋BL-228 を合わせた3段階）**: 規模が大きいため3段階とし、BL-228 を
   第3段階へ統合する（ユーザー判断・2026-08-14）。
   - **Phase 1（BL-224 基盤）**: スキーマ（`relation_edges`＋インデックス）＋ W1/W2/W3（機械的骨格）＋
     C2（`_audit_report --ref`）＋ **C5（`trace_lineage` ツール）**。実ドライランで系譜が AI からも人間からも
     たどれることを確認。**C5 が無いと書いたエッジが AI から辿れず §15.4 に抵触**するため第1段階に必須。
   - **Phase 2（BL-224 消費の深化）**: C1（Hydrate 系譜表示・トークン量影響最大で後回し）・C3（upsert 境界
     アンカリング）・C4（前方伝播ステイルネス）・W4（fact の `derived_from`）。
   - **Phase 3（BL-228 統合）**: `chat_history` 活性化（死蔵→正本）＋ ref プレフィックス拡張
     （`turn:`/`issue:`/`whiteboard:`/`detector_review:`）＋ `trace_lineage` の `turn:` 受付＋ C1/C4 の
     再利用。BL-224 の `relation_edges` を単一基盤として共有（§15.1）。
   ※W2 のエッジ対象は独立レビューM1により **write_agreement(edits 3箇所) ＋ `_resolve_directive_for_task`(1箇所) の計4箇所**に絞り、
   decision_extractor フォールバック(12923) は除外。トラバーサルは M3 により `_traverse_lineage`（Python 反復・visited set）に単一化。
4. **`chat_history` スパイン＋Hydrate 統合は別 BL へ分割**: ユーザー判断により、本 BL-224 は
   **決定・値・事物の系譜（agreement/fact/entity の `relation_edges`）** に専念し、`chat_history`
   の DB 活性化・N/M 役割非対称要約・ターン内チューリン描画・「本来の Hydrate/trace」統合は
   **[BL-228](../BL-228/BL228_basic_design.md)** へ分離した。BL-228 は本 BL の `relation_edges`
   を基盤とし、ref プレフィックスを `turn:`/`issue:`/`whiteboard:` まで拡張する。両者は `run_id`
   スコープで同一グラフに参加する設計（§15.1 単一ソース: `relation_edges` は1箇所の実装）。

---

## 検証

- `python -m py_compile cela_main.py`
- 再帰CTEスニペットは実装しない（M3・B7）。トラバーサルは `_traverse_lineage`（Python 反復・
  visited set）であるため、DB直結ユニットテスト（線形4-5ノード＋分岐＋意図的サイクル1件＋
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

---

## 独立レビュー所見（hy3, 2026-08-13）

別モデル（claude opus）が作成した本設計書を、hy3 が実コード（`cela_main.py`）に対して各主張を
逐一照合してレビューした。骨格（汎用エッジテーブル・3 ref プレフィックス・3 関係種別・§15.4 の
「死蔵 depends_on を復活」という動機）は正しいが、実装に着手すると詰まる／誤動作する抜けと論理
バグが複数あった。以下、A1 は議論により解決済み（設計書へ反映）、**A2〜A5・B5〜B7 は設計で解決済み**
（各節へ反映）、**B8（backfill）のみ実装着手時に別途検討する遅延課題**として残る。

### 検証済みで正しかった点（実コード確認）

- `db_supersede_agreement`（実際は 5875、doc は誤って 5904 等と記載）は status を `'Superseded'`
  へ flip するだけで新 id は作らない — 設計の前提通り。
- コードベースに `WITH RECURSIVE` は存在せず「初の再帰CTE」は真。
- `_find_prior_superseded` の呼び出し元は `_build_agreements_context` 内の 1 箇所（実際は 7582）のみ
  — C1 置換は安全。
- `db_supersede_agreement` の呼び出しは 5 箇所（数は合っているが、実際の行番号は doc と ~+20 ズレ）。
- 5924（`_resolve_directive_for_task`）では supersede 直後に `resolved_id = _new_record_id("AG")` で
  新 id が採番される — W2 の好例。

### A1: W1 の新 agreement id 引き回し — 【解決済み・本ファイルへ反映】

**問題**: 設計書は W1 を「`_commit_agreement_from_tool` の confirmed_variables ループ（3444-3458）」
としていたが、実際にはそのループは `_write_agreement_impl`（3444-3458）にあり、
`_commit_agreement_from_tool` は 3315 で `(None, protected_warning)` を返して終わる。新 agreement id
は同関数の 3303（`_new_record_id("AG")`）で局所生成されるだけで**外部に出ない**。よって
`agreement:<新id>` → `fact:` エッジを書くための id がどこにも存在しなかった。また entity 側も
`upsert_entity_attribute`（実際は 7086）は agreement id 引数を持たない。

**解決策（合意済み）**:

1. `_commit_agreement_from_tool` の戻り値を `(None, protected_warning)` →
   `(agreement_id, protected_warning)` へ変更。全パスで INSERT が1回行われるため返すべき id は
   常に1つ；未生成パスは `None` を返すようガード。
2. `_write_agreement_impl` で `new_agreement_id, protected_warning = _commit_agreement_from_tool(...)`
   と捕捉し、confirmed_variables ループ内で `upsert_verified_fact` 成功後に
   `_write_relation_edge(conn, run_id, from_ref=f"agreement:{new_agreement_id}",
   to_ref=f"fact:{var_name}", relation_type="derived_from", ...)` を書く（LLM 非依存・骨格）。
3. `_write_relation_edge` を**単一検証ゲート**（§15.1）にする：from/to 両 ref が実テーブル
   （`agreements`/`verified_facts`/`entity_attributes`）に実在しない限り書き込みを拒否し warning を
   返す。消費側も `EXISTS` で未解決 ref をスキップ。→ `agreement:None` などの不良 ref は
   構造的に書かれない（§13/§15.3）。
4. **entity 側**: `upsert_entity_attribute` 内で `agreement:` → `entity:{id}:{attr}` エッジを書く。
   親 agreement の概念が無いため、タイムスタンプ推論は §13.3/§15.3 の lossy 推論 anti-pattern として
   不採用とし、**task_id → phase_id → 計画センチネル** の順に agreement を探して結ぶ
   （`agreements` も task_id/phase_id を保持、確認済み）。最新の非 Superseded agreement 1件に限定。
   **task_id が空でもスキップせず** phase_id で結ぶこと——計画時（タスクプラン段階）に生成される
   グローバル制約等は task_id 空・phase_id のみであり、ここで落とすと「出所不明」が再発する
   （過去ランの実害）。両方空ならセンチネルでタグ付けし追跡可能性を保持（エッジは結ばないが
   事実は失われない）。
   **タイミング（M2 確定）**: ブリッジは `upsert_entity_attribute` が実際の書き込み（INSERT/ON CONFLICT UPDATE）を
   `conn.commit()` する直前に、関数**内部**で実行する（§15.3: 呼び出し元に関わらず構造的に迂回不可）。
   この時点で `source_task_id` / `source_phase_id` は既に確定しているため、その値で agreement を探す。
   見つからなかった場合のみセンチネルタグ（例 `"plan:sentinel"`）を `created_by`/理由に付与し、エッジは
   結ばない（孤立 entity 属性として `read_entity` 等からは検索にひっかかる）。

**孤立 fact の検索性（確認済み）**: `verified_facts` は `relation_edges` とは別の
ソース・オブ・トゥルース。エッジは追加であり置換ではないため、agreement に紐づかない fact も
`read_verified_fact` / `_audit_report --ref` / `_build_task_scope_context` で常に検索にひっかかる
（親無き root として残る）。前方トラバーサルで orphan に到達させたい場合は上記 task_id/phase_id
ブリッジが補う。

### 未解決課題（実装前に設計で解決または方針確定すること）

- **A2: C3 のスキーマ混同＋タイミング誤り — 【解決済み・設計書 C3 節を書き直し】**
  `owns_variables` は `list[str]`（変数名のみ、7181行）であり `confidence` フィールドは存在しない
  （スキーマ混同、確定）。さらに `task_plan_reviewer_node`（12073付近）は**実行開始前に1回だけ**発火し、
  その時点では `verified_facts` は未書き込み（タイミング誤り、確定）。よって C3 を
  **`upsert_verified_fact`（6719）の境界へ移動**し、(1) `owns_variables` ではなく `verified_facts.confidence`
  を読む、(2) ノード非依存（Expert/decision_extractor/human-input/将来のplanner・reviewer すべてが通る
  単一入口）とした。捕捉は `confidence='provisional'` の表示強調（段階1）＋任意の上流トラバーサル
  （段階2、BL-219 経路再利用）。**計画段階の概算を facts として登録する挙動変更は別 BL に分離**
  （本 BL スコープ外、§15.2/§15.1/ユーザー合意要）。

- **A3: C1「前提（depends_on）」行のデータソース欠如 — 【解決済み・C1節へ設計追記】**
  表示例には「系譜（supersedes）」と「前提（depends_on）」の両方が描かれていたが、旧 `_get_lineage_chain`
  は `relation_type='supersedes'` のみを返し「前提」行のデータソースが無かった（ブロッキング、確定）。
  これを解消: C1 は各 agreement につき (1) `_get_lineage_chain`（supersedes 連鎖＝「系譜」行）、
  (2) `_traverse_lineage(relation_types=['depends_on'], direction="backward")`（＝「前提」行）の2回呼び、
  depends_on 後方エッジを from_ref の種別（agreement/fact/entity）で解決表示する。前提は `relation_edges`
  からのみ読み（agreements.depends_on 列は W3 で流し込み）、B8 backfill で既存データも対象。同一の
  `_traverse_lineage`（M3 単一実装）を `relation_types` で絞るだけで済む。

- **A4: W3 の depends_on→`agreement:<id>` マッピング【解決済み】**
  **真因**: スキーマ説明（`cela_main.py:2295-2306`）が「`[42]` のような括弧番号」と指示しているが、
  これは実態と食い違う古い記述。`_new_record_id("AG")`（`2210`）は `AG-{ミリ秒}-{uuid}` を返し、
  system prompt はそれをそのまま `[AG-xxxx]` 表示する（`7578`）。検証 `3367-3375` も `id=?` に
  `dep_id` を直接渡すため、LLM が表示通り `AG-xxxx` を書けば通る。つまり depends_on に書く値は
  **実 id そのもの**であり、W3 の ref 変換は `f"agreement:{dep_id}"` の単純プレフィックスで済む
  （翻訳表不要）。
  **決定**: (1) マッピングは `agreement:{dep_id}` プレフィックス、方向は `from_ref=前提(Y)`→
  `to_ref=依拠先(X)`・`relation_type='depends_on'`（スキーマ定義に準拠、A3 の C1「前提」行と整合）；
  (2) 検証は `3367-3375` をそのままゲートとして**再利用**（新規検証は書かず、§15.1 単一ソース）し、
  `_write_relation_edge` の `EXISTS` 再検証が二重の守りとなる； (3) `2295-2306` の説明を
  `'[42]' -> ['42']` から `'[AG-xxxx]' -> ['AG-xxxx']` へ修正し、壊れた ref の懸念（§15.4）を
  根本から塞ぐ（コード修正、§8 未着手）。詳細は「### W3（LLM記入・既存引数の復活）」節へ反映済み。
  B8 バックフィルも同一マッピングを使用。

- **A5 / C5: `trace_lineage` ツール（AI オンデマンド消費経路）の欠如（ブロッキング・最重要）**
  現状の消費経路は C1（自動・agreement のみ・深度限定・オンデマンド不可）・C2（`_audit_report` は
  **CLI 専用**、`--audit-report` 引数 14339/14391、**AI ツールとして未公開**）・C3/C4（特定用途）のみ。
  **「AI が fact X や entity Y に興味を持った → 辿る」という経路が存在しない**。これはまさに BL-224
  の出発点だった「書き込み口はあるが消費経路が欠けている」（§15.4）の再発。W1-W4 でエッジを書いても
  AI から辿れなければ点と線は繋がらない。
  **新ツール `trace_lineage(ref, direction="both", max_depth=10)` を消費経路 C5 として追加する**。
  ref は `agreement:<id>` / `fact:<variable_name>` / `entity:<entity_id>:<attr_name>`。内部で再帰的に
  edges をたどり各 ref を**解決して内容も添える**（agreement なら decision_what/reason_why、fact なら
  value/reason、entity なら value）。読み取り専用・LLM 呼び出しなし（C2 と同型）・全ノードから呼べる。
  ref 記法はツール schema ＋ 共有ヘルパー1本（§15.1）で全ノードへ注入。サイクル安全は A7 の
  Python 反復＋訪問済み set を用いる。
  **不明・他 run ref の応答仕様（独立レビューN3・決定）**: trace_lineage は**呼び出し元 run の
  run_id スコープで検索**する（M4・§15.1 単一スコープ）。(a) ref が `relation_edges` に1件も
  存在しない、または他 run の ref であった場合は、**空リスト `[]` を返し**、ヒント
  `「現在の run 内に該当 ref はありません（検索スコープ run_id=...）。trace_lineage は取得対象 run
  の run_id スコープで検索します」` を `result` に含める（fail-loud・§13.2: 空リストは「該当なし」
  と明示し、存在しない ref を LLM が勝手に補完して「暗黙的に承認済み」と誤認するのを防ぐ）；(b) ref
  のプレフィックス自体が未知（`agreement:`/`fact:`/`entity:` 以外）の場合は `result` に
  `「未知の ref プレフィックスです。agreement:/fact:/entity: のいずれかで指定してください」` を
  返す（検証は `_traverse_lineage` 入口で行い、未知プレフィックスは走査せず即時返却・§15.3 機械的検証）。

- **B5: C4 が BL-168 のプレフィックスを「そのまま再利用」は誤り**
  BL-168 のマーカーは「⚠️[BL-168: **ゴール改定後未確認**]」（2839）でトリガーは「ゴール改定」。
  C4 の前方伝播は「上流値の変更」という別トリガー。同じ文字列を使うと (a) 監査レポートを読む人に
  誤った理由を提示し、(b) BL-168 のスキップ判定（`startswith` 同一文字列、2850）と C4 の判定が
  **相互に食い合う**（片方がもう片方を「既マーク済み」と誤認）。別の冪等プレフィックス
  （例 `⚠️[BL-224: 上流変更で要再確認]`）を定義すること。

- **B6: W2 の `_link_supersession` 散在（§15.2）— 【部分修正・独立レビューM1で事実誤認を訂正】**
  独立レビューが実コードで再照合した結果、私（hy3）の「12923（Integrator パス）では新 id が
  スコープ内に存在しない」は**事実誤認**であった。`db_supersede_agreement(a["id"])` の直後に
  同じ UPDATE ブロック内（12965 付近）で `_new_record_id("AG")` により新 id が生成され
  `db_append_agreement` で保存される。したがって新 id は捕捉可能。
  **ただし設計上の結論は「12923 パスは supersession エッジの対象外」とする**（独立レビューM1の勧告を採用）。
  理由: ここは `write_agreement` 未使用時の再抽出フォールバックであり、作られる新 agreement は
  「同一 topic の再抽出」＝ lineage 上の「差し替え」ではない。ここでエッジを張ると chain が誤導される。
  よって W2 のエッジ対象は **`write_agreement` の edits 3箇所 ＋ `_resolve_directive_for_task` 1箇所**
  の計4箇所とし、12923 は明示的に除外（その旨をコードコメントへ残す）。BL-226 の散在警告への対応は
  単一ラッパー `supersede_agreement(old_id, new_id, reason)`（flip＋edge 書き込み一括）を採用し、
  `write_agreement` 内の3箇所をそのラッパーに集中させる。

- **B7: 再帰CTE のサイクル対策 — 【解決済み・M3で確定】**
  再帰CTE は**採用しない**と決定（本コードベース前例ゼロ＋サイクル検知欠如）。替わりに
  **訪問済み set を持つ Python 反復トラバーサル `_traverse_lineage` を単一実装**とし、C5/C1/C4 が
  すべてこれを呼ぶ（詳細は「再帰CTE設計」節を参照）。実装者の裁量には残さない。

- **B8: 既存 `depends_on` 行の移行（backfill）が無い**
  BL-224 前の agreements は既に `depends_on` を保持しているが、それらのエッジは `relation_edges` に
  入らない。進行中／過去 run の系譜が不完全になる。一回性の backfill スクリプトを検討すること。

- **C（ドキュメント精度）: 行番号ドリフト — 【解決済み・M5で反映】**
  実測で以下を確定：`db_supersede_agreement` 呼び出しは write_agreement(edits 3箇所)・
  `_resolve_directive_for_task`(1箇所)・decision_extractor フォールバック(12923) の計5箇所；
  `upsert_verified_fact` は 6719、`upsert_entity_attribute` は 7086、`_audit_report` は 6845、
  `task_plan_reviewer_node` は 12072。本文の W1/W2 は関数名参照へ書き換え済み（行番号のシステム的
  ズレを避けるため §16.2 に従う）。C4 の根拠 `verified_facts_json` の行は Detector コンテキスト
  return であり誤引用だったが、C4 は既存表示経路（`reason` 列）を再利用する方針でその箇所に依存しない。

### 総評

アーキテクチャの方向性は正しく、要件定義§4.2 の「DAG系譜」を死蔵から復活させる動機も適切。
A1 の解決策（戻り値変更＋ループ内エッジ＋`_write_relation_edge` 単一検証ゲート＋entity は
task_id/phase_id ブリッジ）を骨格として採用する。独自レビュー（hy3）の課題はすべて解決済み:
**A2**（C3 を upsert 境界へ移動＋計画概算 facts 登録は別 BL-229 へ分離）・**A3**（depends_on 後方
エッジを C1「前提」行として設計）・**A4**（W3 マッピング＝`agreement:{dep_id}` 単純プレフィックス＋
`3367-3375` 検証の再利用＋`2295-2306` 説明の実 id 化で壊れた ref を根本解決）・**A5/C5**
（`trace_lineage` ツール新設）・**B5**（別冪等プレフィックス `⚠️[BL-224: 上流変更で要再確認]`）。
**独立レビュー（M1–M5）も全文を実コードで再照合の上反映済み**:
- M1 → B6 の事実誤認を訂正しつつ、12923 フォールバックをエッジ除外と確定（W2 は計4箇所）。
- M2 → entity ブリッジの「タイミング」を `upsert_entity_attribute` 内部・commit 直前に確定。
- M3 → トラバーサルを `_traverse_lineage`（Python 反復・visited set）単一実装に確定（再帰CTE は不採用）。
- M4 → `run_id` スコープを設計書へ明記（系譜は同一 run_id 内、クロス run は将来課題）。
- M5 → 本文の行番号参照を関数名参照へ書き換え（ドリフト回避、§16.2）。

実装は「スキーマ＋W1/W2/W3（骨格）＋C2（CLI）＋**C5（trace_lineage）**」
を先に入れ、実ドライランで系譜が AI からも人間からもたどれることを確認してから、C1（Hydrate 表示）・
C3・C4・W4 を追加する2段階を推奨（C5 が無いと書いたエッジが AI から辿れず §15.4 に抵触するため第1段階に含める）。
独立レビュー・独自レビュー双方の課題は設計で解決済み。残るのは (1) 未決事項1（最大探索深度定数・
§7 ユーザー承認）、(2) B8（backfill・実装着手時に別途検討の遅延課題）。いずれもブロッカーではない。
