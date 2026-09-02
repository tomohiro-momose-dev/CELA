# BL-294: confirmed_variables/entity属性の「定義監査」機構（誰が・いつ出典と照合したかの追跡）

## Context

`log/2026-08-28/1023`で発生していた生成崩壊（Expert task_1_1が同一の数値矛盾を単一の生成ターン内で35分超・堂々巡り）を根本原因まで遡ったところ、真因は「モデルの弱さ」ではなく`log/2026-08-27/2345`（2026-08-28 00:22:15、`call_task_planner` iter=26、`cela_main.py:15097`手前の`call_task_planner`定義=`cela_main.py:10651`）まで遡る**単一の誤登録**だった。

task_plannerはweb_search（クエリ「高齢者 運転免許 返納 率 長野県 統計 警察庁」）で得たkashikapedia.com記事を引用し、`nagano_license_surrender_rate_75plus=78.3%`を`confidence="confirmed"`としてverified_factsへ登録した（`upsert_verified_fact`、`cela_main.py:8700`）。しかし出典記事の78.3%は実際には「長野県の自主返納者**全体**のうち75歳以上が占める構成比」であり、task_plannerが変数名に込めた意味（75歳以上人口/免許保有者における返納**率**）とは別の統計だった。この誤登録が`confirmed`のままtask_1_1のdescription/acceptance_criteriaへ複数回埋め込まれ、以降の全てのtask_1_1再実行（BL-278/291/292ドライラン、8/28 0649・1023の生成崩壊）が偽の"確定値"を前提として引きずり続け、Expertが自ら発見する一次データ（保有率約60%）との矛盾を解決できず堂々巡りに陥っていた。

ユーザーとの合意事項（3点）:
1. task_plannerが（あるいはconfirmed_variablesを書く誰であれ）自分の検索意図（変数名の意味）と出典本文の実際の定義が一致するかを自己確認する。
2. task_plan_reviewer（実行開始前に1回だけ発火する計画レビューゲート、`cela_main.py:15097`）に、confirmed_variables/entity属性の**定義**が出典本文の実際の記述と一致しているかをweb_search/web_fetch/read_reference_fileで監査する観点を追加する。誰が監査したかを記録する。
3. タスク遂行中にExpert/User AIが既存の登録値に疑義を持ちDBを更新した場合、直後のDetectorがその更新差分を拾い、変更された値の定義を監査し、「Detectorが監査した」とDBに書き込む。

設計判断（ユーザー承認済み）: `verified_facts`/`entity_attributes`へ`audited_by`/`audited_at`列を追加するスキーマ変更で進める。既存の`confirmed_by`/`confirmed_at`（誰が値を書いたか）と対称な、構造化された「誰が値の定義を出典に照らして検証したか」の記録。BL-224/168のreason欄マーカー追記方式（累積・非消費型）は、今回は「監査されたら解消される」消費型の状態管理が必要なため不採用。

## 既存インフラの調査結果（Exploreエージェント2件＋直接確認、file:line根拠付き）

- `upsert_verified_fact`（`cela_main.py:8700-8739`）は既にUPSERT実装（`ON CONFLICT(run_id, variable_name) DO UPDATE`）。値が実際に変化した場合のみ`_mark_forward_dependents_stale`（下流の依存値へBL-224マーカーを伝播、`cela_main.py:8769-8792`）を呼ぶ。
- `entity_attributes`側にも対になる`upsert_entity_attribute`（`cela_main.py:9329-9360`）が存在し、同型のUPSERT＋変化検出時のみstale伝播（`cela_main.py:9355-9360`）を行っている。ただし`upsert_verified_fact`と違い、上書き時の`print`通知が無い非対称がある（今回のスコープ外、参考情報）。
- ref文字列の形式（`"fact:<variable_name>"` / `"entity:<entity_id>:<attr_name>"`）と、その実在検証ヘルパー`_resolve_ref_table`（`cela_main.py:7334-7388`）が既に存在し、`relation_edges`書き込み時に使われている。新規ツールもこの同じref形式と検証ヘルパーをそのまま再利用する（§15.1）。
- `call_detector`（`cela_main.py:11768`）は`_CURRENT_CALLER_ROLE="detector"`を関数冒頭（`11780-11781`）で設定しており、domain_prompt・ツールリスト構築より前なので、新規Detector権限ゲート付きツールに対するタイミング問題は無い（`call_expert`で見つかった同種の問題はここには無い）。
- `call_detector`のDomain Reviewパス（Pass 1、`domain_prompt`）は現在、`verified_facts`をプロンプトへ一切事前展開していない（`_build_task_scope_context`の呼び出しは`call_expert`・`generate_user_utterance`・`call_orchestrator`にはあるが`call_detector`には無い）。Pass 1が受け取るDB由来テキストは`_get_frozen_agreements_text`（frozen合意のみ、`cela_main.py:12194`、定義`8332-8349`）だけで、facts/entity属性はDetectorが`READ_VERIFIED_FACT_TOOL`/`READ_ENTITY_TOOL`を能動的に呼ばない限り見えない。→ 受動的なツール提供だけでは監査が実行される保証がないため（§15.3の教訓、BL-266/292と同じ理由）、「未監査のfact/属性」を機械的に抽出してdomain_promptへ直接埋め込む新規ヘルパーが必要。
- Domain Reviewのツールリスト`_detector_domain_tools`（`cela_main.py:12273`）には既に`READ_VERIFIED_FACT_TOOL`・`WRITE_AGREEMENT_TOOL`・`WRITE_ISSUE_TOOL`・`READ_ENTITY_TOOL`・`WEB_SEARCH_TOOL`・`WEB_FETCH_TOOL`・`READ_REFERENCE_FILE_TOOL`が含まれており、監査の実行自体に必要なツールは既に揃っている。新規に要るのは「監査結果（audited_by/audited_at）を書き込むツール」だけ。
- `task_plan_reviewer`のツールリスト`_task_plan_reviewer_tools`（`cela_main.py:15290`）も同様にweb_search/web_fetch/read_reference_file/read_entity/write_agreementを持つ。
- スキーマ移行の既存パターン: `_ensure_verified_facts_r3a_columns`（`cela_main.py:7212-7227`、呼び出し元`7099`）が`PRAGMA table_info`で列有無を確認してから`ALTER TABLE ... ADD COLUMN`する既存の安全な移行イディオムを提供している。新規列もこれに倣う。
- タスクスコープの決定ロジック: `_build_task_scope_context`（`cela_main.py:10229-10246`）の`dependency_variable_names`（現在タスクが`depends_on`する各タスクの`owns_variables`の和集合）が、既に確立された「このタスクに関連するfactの範囲」の定義。新規の「未監査fact抽出」もこの定義（＋現在タスク自身の`owns_variables`）を再利用してスコープを揃える。

## 設計

### 1. WRITE_AGREEMENT_TOOLの`confirmed_variables`スキーマ説明へ自己確認指示を追加（BL-291と同型：単一の共有箇所）

`confirmed_variables`はtask_planner専用ではなくWRITE_AGREEMENT_TOOL（`cela_main.py:2802`付近のスキーマ、ほぼ全ロールが使用）経由でどのロールからも書ける共有フィールドのため、BL-291がWEB_SEARCH_TOOLの共有descriptionに一般化ガードレールを足した前例（§15.1）に倣い、`confirmed_variables[].value`のdescription、または直近の`citations`説明（`cela_main.py:2829-2833`付近）に追記する:

> `[BL-294] confidence="confirmed"としてこの値を登録する前に、変数名が意味する定義（例:「返納率」なら分母は何か）と、citationsに挙げる出典本文が実際に述べている定義が一致するか確認してください。出典に「◯◯に占める割合（構成比）」等、検索意図と異なる定義が書かれている数値を、検索キーワードに近いという理由だけで確定値として転記しないこと。`

加えて、task_plannerは初期計画作成時に複数のweb_searchをまとめて実行し一括でconfirmed_variablesを登録する運用（本件の実際の発生パターン）のため、`call_task_planner`のプロンプト（`cela_main.py:10651`以降、既存のBL-204/BL-092系の指示がある付近）にも同旨の一文を重ねて明記する（BL-292が上流ノードへ拡張した際と同じ「共有箇所＋役割別の念押し」の二段構え）。

### 2. スキーマ変更: `verified_facts`/`entity_attributes`へ`audited_by`/`audited_at`列を追加

`_ensure_verified_facts_r3a_columns`（`cela_main.py:7212`）と同じ`PRAGMA table_info`ガード付き`ALTER TABLE ADD COLUMN`パターンで、新規関数`_ensure_audited_columns(conn)`を追加し、呼び出し元（`cela_main.py:7099`付近）に並べて呼ぶ:
```python
def _ensure_audited_columns(conn: sqlite3.Connection) -> None:
    for table in ("verified_facts", "entity_attributes"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()}
        if "audited_by" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN audited_by TEXT DEFAULT NULL")
        if "audited_at" not in cols:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN audited_at REAL DEFAULT NULL")
    conn.commit()
```

`upsert_verified_fact`（`8700`）と`upsert_entity_attribute`（`9329`）のUPSERT文へ、値が変わった場合のみ`audited_by`/`audited_at`をNULLへ戻すCASE式を追加する（同一UPSERT文内で完結させ、Python側の分岐を増やさない）:
```sql
audited_by = CASE WHEN excluded.value != verified_facts.value THEN NULL ELSE verified_facts.audited_by END,
audited_at = CASE WHEN excluded.value != verified_facts.value THEN NULL ELSE verified_facts.audited_at END
```
（entity_attributesも同型。初回INSERT時はaudited_by/audited_atをVALUES句に含めず、列のNULLデフォルトに任せる。）

### 3. 新規ツール `mark_fact_audited`（task_plan_reviewer・Detectorの両方が使用、単一のゲート）

`ref`（`"fact:<variable_name>"` / `"entity:<entity_id>:<attr_name>"`、既存のBL-224 ref形式を再利用）、`audit_result`（enum `"confirmed_correct"` / `"corrected"`）、`reason`（string, required）を受け取る。実装:
1. `_resolve_ref_table`（`cela_main.py:7334`）でref実在を検証（存在しなければエラー）。
2. `ref`のprefixに応じ`verified_facts`または`entity_attributes`の該当行へ`audited_by=<caller_role>, audited_at=time.time()`をUPDATE。
3. `audit_result="corrected"`の場合、呼び出し元は**この呼び出しより前に**`write_agreement`(confirmed_variables再登録)または`write_entity_attribute`で実際の値を訂正しておくことをツールdescriptionで明記する（このツール自体は値を書き換えない、監査済みマークの単一責務に留める＝§15.1）。

`_task_plan_reviewer_tools`（`15290`）・`_detector_domain_tools`（`12273`）の両方へ追加。`caller_role`はツール実装内で`_CURRENT_CALLER_ROLE`（"task_plan_reviewer"または"detector"、いずれも関数冒頭で設定済みなのでタイミング問題なし）から取得し、それ以外のロールからの呼び出しは拒否する（他のロール限定ツールと同じ権限チェックパターンを踏襲、例: `flag_needs_human_input`のexpertのみ許可、`cela_main.py:4660`の`caller_role`チェックを参考にする）。

### 4. task_plan_reviewerへ10番目のレビュー観点を追加（`cela_main.py:15125-15177`の既存9観点の直後）

> `10. [BL-294] 定義監査: task_plannerがconfirmed_variablesとして登録した数値・read_entityで確認できるentity属性について、その変数名/属性名が意味する定義と、citationsに挙げられた出典本文の実際の記述が一致しているか、web_search/web_fetch/read_reference_fileで検証してください。一致していれば mark_fact_audited(audit_result="confirmed_correct") で監査済みを記録してください。定義が食い違う場合（例：「◯◯に占める割合」を「◯◯率」として登録している等）、write_agreement（action_type="SUPERSEDE"）で該当のconfirmed_variablesを正しい値へ訂正し、その上でmark_fact_audited(audit_result="corrected")を呼んでください。`

これは初回の計画レビュー時点でtask_plannerが一括登録した全confirmed_variables/entity属性が対象（スコープは run 全体、one-shotゲートのため絞り込み不要）。

### 5. call_detectorのDomain Review（Pass 1, `domain_prompt`）へ「未監査fact/属性」の機械的抽出と監査指示を追加

新規ヘルパー`_build_unaudited_facts_text(conn, run_id, task_id, phases)`を追加し、`_get_frozen_agreements_text`と同様に`domain_prompt`構築時（`cela_main.py:12194`付近）に埋め込む。スコープは`_build_task_scope_context`の`dependency_variable_names`ロジック（`10236-10244`）を再利用し、「現在タスク自身のowns_variables」∪「依存タスクのowns_variables」に属する変数名のうち`audited_by IS NULL`のものだけを抽出する（run全体を毎回見せない）。entity_attributesも`source_task_id=current_task_id AND audited_by IS NULL`で同様に抽出する。

```
【BL-294: 未監査の確定値】以下は、このタスクに関連するconfirmed_variables/entity属性のうち、
まだ誰にも定義監査（出典が実際に述べている定義と一致するかの確認）を受けていないものです。
該当があれば、web_search/web_fetch/read_reference_fileでcitationsの出典本文を確認し、
定義が一致していればmark_fact_audited(audit_result="confirmed_correct")で記録してください。
不一致（例：構成比を率として登録している等）を発見した場合、write_agreementで値を訂正した上で
mark_fact_audited(audit_result="corrected")を呼んでください。
{unaudited_facts_list}
```
該当が0件の場合はこのブロック自体を省略する（空リストを毎回見せてトークンを浪費しない）。

これにより、Expert/User AIが既存registered値に疑義を持ちwrite_agreement/write_entity_attributeで更新した場合（既存機構、新規ツール不要）、その変更で`audited_by`がNULLへリセットされ（本設計②）、**直後のDetector呼び出しのDomain Reviewが自動的にこの変更を検知して監査する**（ユーザーの合意事項3を満たす）。

## Critical Files

- `cela_main.py`:
  - `_ensure_audited_columns`（新規関数、`_ensure_verified_facts_r3a_columns`＝`7212`の隣に追加、呼び出しは`7099`付近）
  - `upsert_verified_fact`（`8700-8739`）: UPSERT文のSET句へCASE式追加
  - `upsert_entity_attribute`（`9329-9360`）: 同様にCASE式追加
  - `MARK_FACT_AUDITED_TOOL`（新規ツール定義、他のツール定義群と同じ箇所、例えば`WRITE_ISSUE_TOOL`＝`837`付近）＋`_mark_fact_audited_handler`（新規実装関数、`_resolve_ref_table`＝`7334`を再利用）
  - `_task_plan_reviewer_tools`（`15290`）・`_detector_domain_tools`（`12273`）へ新規ツールを追加
  - `call_task_plan_reviewer`のプロンプト（`15125-15177`の9観点の直後）へ観点10を追加
  - `_build_unaudited_facts_text`（新規ヘルパー、`_get_frozen_agreements_text`＝`8332`の近くに追加）
  - `call_detector`のdomain_prompt構築（`12104`〜`12250`付近、`12194`の`_get_frozen_agreements_text`呼び出しの隣）へ新規ヘルパー呼び出しを追加
  - `WRITE_AGREEMENT_TOOL`の`confirmed_variables`スキーマ説明（`2802-2833`付近）＋`call_task_planner`（`10651`以降）へBL-294自己確認指示を追加
- `tests/test_bl294_definitional_audit.py`（新規）: スキーマ移行（既存DB相当のconn fixtureで`_ensure_audited_columns`実行→列存在確認）、`upsert_verified_fact`/`upsert_entity_attribute`のCASE式（値変化時のみaudited_by/atがNULLへリセットされる／値が同じ再書き込みでは保持される、の両方をテスト）、`mark_fact_audited`のref検証・権限チェック・DB書き込み、`_build_unaudited_facts_text`のスコープ絞り込み（依存タスクのowns_variablesのみ抽出・監査済みは除外・0件時は空文字）、task_plan_reviewer/call_detectorのプロンプトへ新観点/新ヘルパーが実際に挿入されていることの`inspect.getsource`確認、§17.1（各追加箇所を個別にリバートしテストが失敗することを確認）

## Verification

1. `python -m py_compile cela_main.py`
2. 新規テストファイルを実行し全件成功を確認
3. 既存の関連テスト（`test_bl224_*`系、`test_bl204_*`系、`test_bl278_domain_review_selection_check.py`、`test_bl266_*`、entity_attributes/verified_facts関連の既存テスト）を再実行し非退行を確認
4. AGENTS.md §17.1（各追加ブロックを個別にリバートし対応テストが失敗することを確認後、復元）
5. フルオフラインスイートを実行し、既知のBL-269（4件）以外に新規失敗が無いことを確認
6. 実装後、`docs/design/back_log/issue_backlog.md`にBL-294を`done`化し記載、`decision_log.md`へ決定を記録（スキーマ変更の理由、reason欄マーカー方式を採らなかった理由を明記）
7. これらはプロンプト文言＋新規ツールであり実LLM呼び出しでの効果確認が必要——次回ドライラン時に、①task_plan_reviewerが初期confirmed_variablesの定義監査を実際に行うか、②Detectorが未監査facts一覧を見て実際にmark_fact_auditedを呼ぶか、③今回の78.3%相当の定義不一致が実際に捕捉されるか、をログで確認することを次回宿題として記録する。
8. 現在実行中のドライラン（`log/2026-08-28/1023`、プロセスID 21040/22856）のcela.dbに残る誤った`nagano_license_surrender_rate_75plus=78.3%（confirmed）`は、この機構の実装とは別に、§18.3のバックアップ手順に従って手動訂正または実行の打ち切りが必要（ユーザー判断待ち、本プランのスコープ外）。
