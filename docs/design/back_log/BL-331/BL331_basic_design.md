# BL-331: task_id/phase_id識別のDAG化（Phase 1: 正本テーブル導入）

## Context

BL-330（直前に完了）の根本原因調査で、CELAには「task_id/phase_idが今現在実在するか」を検証できる
DBテーブルが1つも存在しないことが判明した。`Task`/`Phase`はPython TypedDict（`cela_main.py:10519`
`Task`、その少し上に`Phase`）としてLangGraph checkpoint内のJSON（`state["phases"]`）にしか
存在せず、`agreements`/`whiteboard_drafts`等に生えている`task_id`列は全て「そのタスクの成果物」
であって「タスクそのもの」ではない。「今どの成果物が生きているか」の特定は各テーブルごとに
バラバラな線形スキャン/`ORDER BY`慣習（`_find_active_deliverable_agreement`、`get_latest_whiteboard`
等）に依存しており、task_id自体の一意性はDBスキーマでは一切保証されていない。

BL-224（`relation_edges`、既に実装済み・コミット`ab119be`）は「判断の系譜（なぜ）」を扱う汎用DAG
エッジテーブルを導入したが、その設計時に`task:<task_id>`参照型は明示的に検討の上、却下されている
（`BL224_basic_design.md`より）：

> タスクは`state["phases"]`のJSON内にしか存在せず、実表の行として検証できない。検証不能な参照型を
> 混ぜることは、まさに`agreements.depends_on`が陥った「受理されるが意味を持たない」状態を新テーブル
> 内で再現することになる。

つまり`_resolve_ref_table`（`relation_edges`の唯一の書き込み/読み取りゲート、`cela_main.py:8027`）は
`task:`を検証する土台（`SELECT 1 FROM tasks WHERE ...`できる実表）が無いために対応できなかった。
BL-331 Phase 1は、この欠けていた「タスク/フェーズの正本（identity）」を実テーブルとして導入し、
`task:`/`phase:`参照をBL-224の既存インフラへ素直に追加することで埋める。

ユーザーはBL-224（なぜ／判断の系譜）とBL-331（今どれが正本か／識別）を明確に別レイヤーとして
扱うと決めている。BL-331は`relation_edges`を再利用・拡張する形を取り、独立したグラフ機構を
新設しない。

**本Phase 1で防げること/防げないこと（正直な効果範囲）**: BL-330の実インシデント自体
（Deliverable検索がtopic文字列一致でtask_idを見ていなかったバグ）は既に別修正済みで、本BLの
テーブル新設それ自体が同種バグを直接防ぐわけではない（そのバグは`agreements`検索ロジック内の
join-key規律の問題であり、タスクの実在確認とは別レイヤー）。本Phase 1が実際にもたらす効果は:
(1) `PRIMARY KEY (run_id, task_id)`/`(run_id, phase_id)`が、このスキーマで初めてtask_id/phase_id
一意性をDBレベルで保証する、(2) task_id/phase_idの実在・履歴（現在生きているか、いつ・なぜ
supersedeされたか）がSQLで直接問い合わせ可能になる（現状はDirectiveのtopic文字列をgrepする
しかない。**[Cline指摘L-1]** ただしこれは本BL適用（コード更新）以降のreplanからの履歴のみで、
稼働中runでも本BL適用前に発生したsupersede履歴は遡って埋まらない——バックフィル別BLとは別に、
この境界自体も明記する）、(3) 将来、成果物系テーブルへの書き込み時に「そのtask_idは本当に今の計画に実在するか」
を機械的に検証する土台になる（本Phase 1では未実施、将来BLの対象）。過大な期待を避けるため、
設計書・issue_backlog.mdにこの限定を明記する。

## 設計

### 1. 新規テーブル: `tasks` / `phases`

```sql
CREATE TABLE IF NOT EXISTS tasks (
    task_id      TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    phase_id     TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'superseded'
    superseded_reason TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (run_id, task_id)
);
CREATE INDEX IF NOT EXISTS idx_tasks_run_phase ON tasks(run_id, phase_id);
CREATE INDEX IF NOT EXISTS idx_tasks_run_status ON tasks(run_id, status);

CREATE TABLE IF NOT EXISTS phases (
    phase_id     TEXT NOT NULL,
    run_id       TEXT NOT NULL,
    title        TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'active',   -- 'active' | 'superseded'
    superseded_reason TEXT NOT NULL DEFAULT '',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    PRIMARY KEY (run_id, phase_id)
);
CREATE INDEX IF NOT EXISTS idx_phases_run_status ON phases(run_id, status);
```

**[Cline指摘H-1・反映済み]** 当初案は`tasks.depends_on`列（JSON監査コピー）を持っていたが、
これを読む消費経路が設計内のどこにも存在せず、AGENTS.md §15.4（入口を作ったら出口も作る、
本プロジェクト最大の失敗クラスBL-136/145/154/163/168と同型）に抵触するため**列自体を削除**した
（軽量案採用、§16.1）。split系譜の入力は`split_from`フィールド（§4）であり`depends_on`ではない。
タスク実行順序としての`depends_on`は従来通り`state["phases"]`のJSON内・BL-255の
`_resolve_task_transition`ゲートが権威のまま、本表では扱わない。

**`status`は完了判定ではない**: `tasks.status`/`phases.status`は「今の計画に実在するか」だけを
表す。「タスクが完了したか」は引き続き既存の`_is_task_completed`（`cela_main.py:8491`、agreements
のDeliverable状態から導出）が権威であり、本表はそれを置き換えない。コメントで明記する
（将来の設計者が混同しないよう、BL-206型の再発防止）。

**内容ではなく識別のみを保持**: `title`（デバッグ・監査用の可読性のみ）と`depends_on`（split系譜
エッジ書き込みと監査目的）以外、`Task`/`Phase`の全フィールドは複製しない。計画内容の正本は
引き続き`state["phases"]`のJSONのまま——本表を「計画のもう1つのコピー」にしてドリフト源を
増やさない（§15.1）。

### 2. 書き込み経路: `task_planner_node`での同期

**場所**: `task_planner_node`（`cela_main.py`、既存のBL-329 `removed_task_ids`復元/supersedeループの
直後、`state["phases"] = phases`確定後）。初回計画（`removed_task_ids`が空集合）でも無条件に呼ぶ。

BL-329が既に計算済みの「復元されたか／真にsupersedeされたか」の判定結果をそのまま再利用し、
判定ロジックを重複させない（§15.1）。phaseの生存判定も同様に、BL-329のタスク復元ループが
（フェーズ自体が消えていた場合に）フェーズを浅コピーで復元する既存挙動にただ乗りする形にし、
フェーズ用の独立した保護ロジックを新設しない——最終的な`phases`に登場するphase_idを"active"、
登場しなくなったphase_idを"superseded"とするだけで、既存のタスク復元ロジックが間接的に
フェーズも守る。

```python
def _sync_task_phase_identity(
    conn: sqlite3.Connection,
    run_id: str,
    phases: list[dict],
    old_phases: list[dict],
    superseded_task_ids: dict[str, tuple[str, str]],  # task_id -> (phase_id, reason)
    revision_reason: str,
) -> None:
    """[BL-331] state["phases"]（内容の正本）から tasks/phases テーブル（識別・実在の索引）を
    同期する。task_planner_node が re-plan のたびに phases 全体を再送出する契約に合わせ、
    本関数も全件 upsert（差分パッチではない）。BL-329が既に計算済みの
    removed_task_ids/復元対象/supersede対象をそのまま再利用し、判定ロジックを重複させない。
    """
    now = time.time()
    current_task_ids: set[str] = set()
    current_phase_ids: set[str] = set()
    for p in phases:
        phase_id = p.get("phase_id", "")
        if not phase_id:
            continue
        current_phase_ids.add(phase_id)
        conn.execute(
            """
            INSERT INTO phases (phase_id, run_id, title, status, superseded_reason, created_at, updated_at)
            VALUES (?, ?, ?, 'active', '', ?, ?)
            ON CONFLICT(run_id, phase_id) DO UPDATE SET
                title=excluded.title, status='active', superseded_reason='', updated_at=excluded.updated_at
            """,
            (phase_id, run_id, p.get("title", ""), now, now),
        )
        for t in p.get("tasks", []):
            tid = t.get("task_id")
            if not tid:
                continue
            current_task_ids.add(tid)
            conn.execute(
                """
                INSERT INTO tasks (task_id, run_id, phase_id, title, status,
                                    superseded_reason, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'active', '', ?, ?)
                ON CONFLICT(run_id, task_id) DO UPDATE SET
                    phase_id=excluded.phase_id, title=excluded.title, status='active',
                    superseded_reason='', updated_at=excluded.updated_at
                """,
                (tid, run_id, phase_id, t.get("title", ""), now, now),
            )

    # [M-1反映] 旧phasesにあり新phasesに登場しなくなったphase_idをsupersededへ。
    # taskと対称にsuperseded_reason（revision_reason）も記録する。
    old_phase_ids = {p.get("phase_id", "") for p in old_phases if p.get("phase_id")}
    for pid in old_phase_ids - current_phase_ids:
        conn.execute(
            "UPDATE phases SET status='superseded', superseded_reason=?, updated_at=? WHERE run_id=? AND phase_id=?",
            (revision_reason, now, run_id, pid),
        )

    # BL-329が既に判定済みの「真にsupersedeされたtask_id」を反映（復元されたものは
    # current_task_idsに含まれているため、この分岐に来ない＝上のupsertでactiveのまま）。
    for tid, (phase_id, reason) in superseded_task_ids.items():
        if tid in current_task_ids:
            continue
        conn.execute(
            "UPDATE tasks SET status='superseded', superseded_reason=?, updated_at=? WHERE run_id=? AND task_id=?",
            (reason, now, run_id, tid),
        )
        conn.execute(
            """
            INSERT INTO tasks (task_id, run_id, phase_id, title, status,
                                superseded_reason, created_at, updated_at)
            SELECT ?, ?, ?, '', 'superseded', ?, ?, ?
            WHERE NOT EXISTS (SELECT 1 FROM tasks WHERE run_id=? AND task_id=?)
            """,
            (tid, run_id, phase_id, reason, now, now, run_id, tid),
        )
    conn.commit()
```

呼び出し側（既存のBL-329ループを変更せず、その結果を`_superseded_for_tasks_table`へ蓄積するだけ）:

```python
_superseded_for_tasks_table: dict[str, tuple[str, str]] = {}
for tid in sorted(removed_task_ids):
    old_phase_id = _find_phase_id_for_task(old_phases, tid) or ""
    if tid not in _focused_task_ids and _is_task_completed(_conn, state["run_id"], tid):
        ...  # 既存のBL-329復元処理はそのまま
        continue
    ...  # 既存のBL-329 supersede書き込みはそのまま
    _superseded_for_tasks_table[tid] = (old_phase_id, revision_reason)

state["phases"] = phases
_sync_task_phase_identity(_conn, state["run_id"], phases, old_phases,
                           _superseded_for_tasks_table, revision_reason)
```

### 3. `task:<task_id>` / `phase:<phase_id>` 参照プレフィックスの追加

`_resolve_ref_table`（`cela_main.py:8027`）へ2分岐追加。**解決条件はステータス不問**
（ユーザー決定・既存の`agreement:`解決がstatus不問なのと一貫させる。これによりsupersede後の
タスク/フェーズも`trace_lineage`で履歴追跡できる——「今生きているか」を知りたい場合は
`tasks`/`phases`テーブルを直接引くか、`trace_lineage`結果の`detail`に含めるstatus表示で
判断させる）：

```python
if ref.startswith("task:"):
    tid = ref[len("task:"):]
    return query("SELECT 1 FROM tasks WHERE task_id=? AND run_id=?", (tid, run_id)).fetchone() is not None
if ref.startswith("phase:"):
    pid = ref[len("phase:"):]
    return query("SELECT 1 FROM phases WHERE phase_id=? AND run_id=?", (pid, run_id)).fetchone() is not None
```

**[Cline指摘H-2・反映済み]** 同じref語彙を列挙している箇所は`_LINEAGE_REF_PREFIXES`
（`8446`）・`TRACE_LINEAGE_TOOL`description（`8387-8419`）・`_resolve_ref_line`（`10100`）の
3箇所だけでなく、以下も含め計7箇所ある（§15.2: 発生源の全経路列挙）。全て`"task:"`/`"phase:"`を
追加する：
- `8444`: `"ref は必須です（agreement:<id> / fact:<name> / entity:<entity_id>:<attr_name>）。"`
- `8450`: `"未知の ref プレフィックスです。agreement:/fact:/entity:/turn:/issue:/whiteboard:/detector_review: のいずれかで指定してください。"`
- `10174`: `_resolve_ref_line`のフォールスルー文言（同種の一覧文言）
- `11598`: **`_TRACE_LINEAGE_USAGE_PARAGRAPH`（複数プロンプトへ注入される共有段落、13049/14501/
  15040/15171/15336/15462/15976の7箇所で参照）**。ここを更新しなければAIが`task:`/`phase:`参照を
  指定できることを一切学習できず、「実装したのにAIが使わない」状態になる——最重要。

`_resolve_ref_line`（`10100`）へは`task:`/`phase:`の人間可読行の生成分岐
（例: `f"[task:{tid}] {title}（phase={phase_id}, status={status}）"`）を追加。

**[Cline指摘L-3・反映済み]** `phase:`参照はP1では解決のみでエッジ書込経路を持たない
（split_fromはtask単位のみ）。したがって`trace_lineage(ref="phase:phase_1")`は実在確認は
できるがlineageは常に`[]`になる。この仕様をコメント・ツールdescriptionに明記し、AIが
誤って「phaseの系譜が辿れる」と期待しないようにする。

### 4. タスク分割の系譜: `split_from`フィールド + 新規`split_from` relation_type

AGENTS.md §15.5（「ドリフトしうる閾値より、ドリフトしない不変条件を優先する」）に従い、
task_idの命名規則（`task_5_2` → `task_5_2_1`）からの文字列推測ではなく、LLMに明示宣言させる。

`Task` TypedDict（`cela_main.py:10519`）へ1フィールド追加:
```python
class Task(TypedDict):
    ...
    split_from: str   # [BL-331] このタスクが既存タスクの分割で生まれた場合、分割元のtask_id。
                       # 分割でなければ空文字。
```

`call_task_planner`のプロンプト（BL-313分割トリガーの案内箇所付近）へ、`split_from`を設定する
よう指示する一文を追加。

**[Cline指摘H-3・反映済み]** `_validate_task_plan_depends_on_integrity`（`11957`）は現状
`(phases)`のみを引数に取り`old_phases`にアクセスできない。以下のようにシグネチャを拡張する：

```python
def _validate_task_plan_depends_on_integrity(
    phases_candidate, existing_phases: list[dict] | None = None,
) -> tuple[bool, str]:
    ...
    # [BL-331] split_fromの検証。existing_phasesが空（＝初回計画）の場合、
    # split_fromが非空のタスクは全て不正とする——分割対象は既存タスクに限る
    # （BL-313の分割トリガー自体が既存タスクへの申し送り集中を契機とするため）。
    # 同一リビジョン内で新規に生まれたtask_id同士のネスト分割（新規タスクを
    # さらに分割元に指定すること）も不正とする——split_fromはold_phasesに実在する
    # task_idのみを指してよい。
```

配線は`call_task_planner`内の合成クロージャ`_task_plan_validator`（`12348-12353`、
`_query_and_parse_with_retry`/`_enforce_decision_lineage_json`の両方から共通で呼ばれている
ため配線は1箇所で足りる）で`existing_phases=existing_phases`を渡すよう変更する
（既存のvalidatorリトライ機構にそのまま乗せる、新しいゲート種別を作らない）。

**[Cline指摘M-2への回答]** 「phasesテーブルを今回作る」「task:参照はstatus不問で解決」
「split_fromは新規relation_type」「バックフィルは別BLへ分離」の4点は、本Plan mode内で
AskUserQuestionにより実際にユーザーへ提示・確認済みの決定である（Clineは会話ログを見えない
ため確認できなかったのは妥当な指摘）。承認後、`decision_log.md`に新規D-xxxとして記録し、
あわせて`decision_lineage.md`にも対話の経緯（4択それぞれの提示・選択理由）を記録する
（AGENTS.md §4.9のチェックリストに`decision_lineage.md`が抜けていた点もあわせて反映）。

**relation_typeはユーザー決定により新規`split_from`を追加**（既存の`depends_on`/`supersedes`/
`derived_from`とは意味的に区別する。`relation_edges.relation_type`はDBレベルのCHECK制約を
持たない自由なTEXT列のため、スキーマ変更は不要——ドキュメント・コメント上の語彙拡張のみ）。

**[Cline指摘L-2・反映済み]** 「3種類」と記載している箇所は最低限以下を更新する：
`cela_main.py:7738`（`relation_edges`のDDL直上コメント）・`cela_main.py:8023`
（`_resolve_ref_table`付近のモジュールコメント）・`docs/design/back_log/BL-224/BL224_basic_design.md:118`。
あわせて同設計書L113-116の「`task:`は実表がなく検証不能なので不可」という却下記載は、本BLで
`tasks`実表が導入され前提が変わるため、「BL-331により`tasks`実表が導入され、この却下は
解消された」旨の追記注記を入れる（古い却下理由が今も有効であるかのように読めてしまうのを防ぐ）。

書き込みは`_sync_task_phase_identity`の後、**別ループとして**実施する（子task_idの行より先に
親task_idの行がコミット済みである必要があるため、同一ループ内での順序依存を避ける）：

```python
for p in phases:
    for t in p.get("tasks", []):
        parent = t.get("split_from")
        if parent:
            _write_relation_edge(
                _conn, run_id,
                from_ref=f"task:{parent}", to_ref=f"task:{t['task_id']}",
                relation_type="split_from",
                reason=f"task_id='{t['task_id']}'はtask_id='{parent}'の分割により生成されました（BL-313split トリガー）。",
                created_by="task_planner",
                source_task_id=t["task_id"], source_phase_id=p.get("phase_id", ""),
            )
```

### スコープ外（本BLでは対応しない）

- **バックフィル**（既存run群への遡及登録）: ユーザー決定によりBL-230前例に倣い別BLへ分離。
  稼働中のrunは次回task_plannerの再計画時に自然に埋まる。完全に終了した過去runのみ遡及登録が
  必要——別BLとして`agreements`テーブルからの近似復元スクリプトを検討する。
- **Decision/Directiveのtopic文字列一致によるsupersede**（BL-084が意図的にスコープ外とした
  設計、複数Decisionが1タスクに存在しうるため「1タスク1正本」前提が成り立たない）は対象外。
- **`_write_agreement_impl`の`tid = args.get("task_id") or task_id`暗黙フォールバック**
  （BL-330の第2の識別子不整合経路）は本BLの対象外。DAG構造の話ではなく引数バリデーションの話
  であり、別途小さな修正として検討する。
- **task_planner出力を「1タスクずつのツール呼び出し」へ作り直す改修**はBL-329で既に検討・
  不採用済み（大改修になる一方、validatorフックで同等の効果が得られるため）。本BLでも再提案しない。
- **成果物系テーブルへの書き込み時に`tasks`テーブルとのFK的な整合性チェックを追加する**
  （例: 存在しないtask_idへのDeliverable書き込みを拒否する）ことは、本Phase 1の効果範囲の
  節で述べた通り「将来可能になる」だけで、本BLでは実施しない。

## テスト方針（§17.1）

新規`tests/test_bl331_tasks_phases_identity.py`:

1. スキーマ作成: `init_db`が`tasks`/`phases`をPK制約付きで作成し、`(run_id, task_id)`/
   `(run_id, phase_id)`の重複INSERTが`sqlite3.IntegrityError`になること。
2. 初回計画で両テーブルが埋まること（`status='active'`）。
3. 再計画・BL-329によりtaskが復元されるケース: `tasks`側も`status='active'`のまま
   （supersededにならない）こと。
4. 再計画・taskが真にsupersedeされるケース: `status='superseded'`・`superseded_reason`が
   revision_reasonと一致すること。
5. phaseが丸ごと消える再計画: `phases`側が`superseded`になること。フェーズ内タスクの復元により
   フェーズも実質的に生き残るケース（BL-329の浅コピー復元）で`phases`側も`active`のままである
   ことの確認。
6. `tasks`行が一度も存在しないtask_idがいきなりsupersede対象になるエッジケース（fallback_phase等）
   で、合成行が作られること。
7. `task:`/`phase:`参照の`_resolve_ref_table`解決: activeでもsupersededでも解決できる
   （存在しないIDのみFalse）こと。
8. `trace_lineage`で`task:`参照のbackward/forwardが機能すること。
9. `split_from`により`relation_type='split_from'`のエッジが1本書かれること（親task_idが
   `_sync_task_phase_identity`で先にコミットされてから書かれる順序であること）。
10. `split_from`が存在しないtask_idを指す場合、`_validate_task_plan_depends_on_integrity`の
    拡張がvalidatorリトライで検出すること。
11. **[Cline指摘M-3・追加]** 再活性化: replan Nでsupersededになったtask/phaseが、replan N+1で
    再登場した場合に`status='active'`へ戻り`superseded_reason`がクリアされること（「一度
    supersededになったら戻らない」という固定観念のバグを検出）。
12. **[Cline指摘M-3・追加]** resume冪等性: checkpoint再開で`task_planner_node`が再実行されても
    `tasks`/`phases`テーブルに重複行・不整合が生じないこと（`INSERT ... ON CONFLICT DO UPDATE`
    のupsert性質そのものの確認）。
13. **[Cline指摘M-3・追加]** `_resolve_ref_line`の`task:`/`phase:`レンダリング（C2監査レポート・
    trace_lineage AI表示で使われる人間可読行の形式）。
14. **[Cline指摘M-3・追加]** `split_from`のvalidatorと初期計画（`existing_phases`空）のケース
    （H-3で確定した不変条件のテスト、項目10と対）。
15. 各項目を個別にrevertし、対応するテストが失敗することを確認した上で復元する（§17.1）。
16. `python -m py_compile cela_main.py`。既存のBL-224/228/329関連テスト非退行確認。
17. フルオフラインスイート実行。

## Critical Files

- `cela_main.py`:
  - `init_db`付近: `tasks`/`phases`のCREATE TABLE + インデックス。
  - `task_planner_node`: `_sync_task_phase_identity`新設・呼び出し・split_fromエッジ書き込みループ。
  - `_resolve_ref_table`・`_LINEAGE_REF_PREFIXES`・`TRACE_LINEAGE_TOOL`description・
    `_resolve_ref_line`・`8444`/`8450`/`10174`のエラーメッセージ・`_TRACE_LINEAGE_USAGE_PARAGRAPH`
    （`11598`、7箇所のプロンプトから共有参照）: `task:`/`phase:`分岐・語彙追加（計7箇所、
    Cline指摘H-2）。
  - `Task` TypedDict・`call_task_planner`のプロンプト: `split_from`フィールド追加。
  - `_validate_task_plan_depends_on_integrity`（シグネチャに`existing_phases`追加）・
    `_task_plan_validator`クロージャ（`12348-12353`）: `split_from`検証拡張（Cline指摘H-3）。
- `tests/test_bl331_tasks_phases_identity.py`（新規）
- `docs/design/back_log/BL-331/BL331_basic_design.md`（本計画を保存）
- `docs/design/back_log/BL-224/BL224_basic_design.md`（L113-116へ「BL-331で解消」注記、
  L118の「3種類」表記更新）
- `docs/design/decision_log.md`（新規D-xxx: phasesテーブル・task:参照のstatus不問解決・
  split_from新設タイプ・バックフィル分離の4点の決定理由を記録）
- `docs/design/decision_lineage.md`（4点の対話経緯を記録、Cline指摘M-2）

## 実装後の手順

- AGENTS.md §19.4（diff-based独立レビュー）を実施し、指摘を実コードで検証の上反映。
- `issue_backlog.md`（BL-331節を`open`→`done`、バックフィル用の新規BL番号を起票）を更新。
