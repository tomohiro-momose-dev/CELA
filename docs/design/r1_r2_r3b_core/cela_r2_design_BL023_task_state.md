# BL-023拡張設計書: フェーズ・タスク状態管理とスコープ制御の統合設計
# (Cognitive Experience Lineage-driven Agent System - R2 Hardening)

> **目的**: task_planner／User AI（`generate_user_utterance`）に起因するタスク粒度・スコープの肥大化（BL-023）を是正する。その前提として、CELA自身が今どのフェーズ・タスクを進行中かを構造的に把握できていない、という発見（BL-024）を解消し、あわせて本プロジェクト自身の統治構造（issue_backlog / decision_lineage / phase_gate / STATUS / traceability / 確定値の再利用）に相当する情報構造をエージェントのstateに持たせる。
> **前提**: R2（ツール呼び出し基盤・F-2.6検算ゲート）が実装済みであること。
> **スコープ外**: Phase B（BL-005: reflection/facilitatorの復旧）、R4差分パッチ（`whiteboard_drafts`）、F-9/F-10.x（Phase 6以降）。
> **最終更新**: 2026-07-20
> **関連**: [BL-023](../back_log/issue_backlog.md#bl-023-task_plannerの分解粒度が粗く複合タスクの検証コストが乗算的に増大する)、[BL-024](../back_log/issue_backlog.md#bl-024-current_phaseが初期化後フリーズしtask_id単位の状態追跡が存在しない)（新規）、[BL-018](../back_log/issue_backlog.md#bl-018-task_planner由来のタスク間依存関係が状態に構造化されておらず横断的な影響判断ができない)、[BL-015](../back_log/issue_backlog.md)、[D-020](../decision_log.md#d-020-bl-023の対応をphase-atask_planneruser-aiのスコープ是正phase-c予算カスケードの仮説化から着手しphase-bbl-005-reflectionfacilitator復旧は後回しにする)、[decision_lineage.md 論点21〜24](../decision_lineage.md)

---

## 1. 現状の問題

### 1.1 タスク粒度・スコープの肥大化（BL-023本体）

実ドライラン（`log/2026-07-19/2056/log_no_prompt.md:1517-1545`）で、task_planner側のtask_1.2の元記述（「予算制約の明文化」）自体は粒度として破綻していなかったにもかかわらず、`generate_user_utterance`（User AI）がExpertへの指示文で「車両台数の論理的算出」（本来task_1.1の依存項目）を自発的に追加し、初期費用6項目・年間ランニングコスト6項目・収支不等式と合わせて計4系統の独立検証可能な主張を1回の発話に束ねた。この結果、同一タスクへの差し戻しが3ラウンド以上発生し、各ラウンドでExpert 5〜8回・Detector 3〜7回の`python_repl`呼び出しが行われた。R4未実装（差分パッチなし、全文書き直し方式）と組み合わさり、検証コストが「間違いの数」ではなく「バンドルの大きさ」に比例して乗算されている。

### 1.2 フェーズ・タスク状態の追跡が存在しない（BL-024、本設計書での新発見）

BL-023 Phase A（「User AIの発話をtask_plannerが定義した**現在のタスク**のacceptance_criteriaの範囲に限定する」）を実現するには、システムが「今どのtask_idが進行中か」を構造的に把握している必要がある。しかし調査の結果、以下が判明した。

- `state["current_phase"]`は初期化時（`phases[0]`）に一度セットされるのみで（`cela_main.py:2300`）、以降どこからも更新されていない。**BL-005（`turn_count`凍結）と同型の「初期化後フリーズ」バグ**である。
- `task_id`単位の状態追跡は最初から存在しない。`current_task_summary`（`cela_main.py:2362`）はExpert出力の先頭200文字を切り詰めた表示用テキストであり、構造化IDではない。
- `decision_extractor`のプロンプト（`cela_main.py:1754`）は各抽出アイテムに`phase_id`をLLMに出力させているが、`decision_extractor_node`（`cela_main.py:2469-2470`）はDBへの書き込みに使うのみで、`state["current_phase"]`へは一切書き戻していない。
- `generate_user_utterance`側で`phase_id`/`task_id`/`user_utterance`を強制JSON出力させる設計が過去に試みられていたが（`cela_main.py:2154-2164`、コメントアウト済み）、無効化の理由は本プロジェクトのドキュメントに一切記録がない。**理由不明のため、この方式を復活させることはしない**（AGENTS.md「no guessing」原則）。

### 1.3 「issue_backlog相当」の先送り記録が存在しない

ログ上、Expertが「〇〇は次タスクで詳細化する」と明示的に先送りを宣言するケースが頻出する（例: task_1.1完了時の車両台数試算の先送り）。これはDetectorがBL-016の carve-out（「具体的に名指しした先送りはminor」）により正しく処理されているが、**先送りされた項目自体はどこにも構造化保存されない**。次のタスクの担当者（Expert/User AI）は、会話履歴の prose を読み返してしか「何が先送りされたか」を知ることができない。

### 1.4 「phase_gate相当」の完了条件が存在しない

`Phase`/Task（dict）には「このフェーズ・タスクが完了したとみなす条件」を表すフィールドが存在しない。完了判定はUser AIの自然文判断（および最終盤の`[PROJECT_COMPLETE]`宣言）に一任されている。

### 1.5 「traceability相当」の充足チェックが存在しない

各タスクにどのような検証項目があり、そのうちどれが確認済みかを追跡する仕組みがない。Detectorは毎ターン「今回の発言」だけを見て判定するため、タスク全体の充足状況は誰も構造的に保持していない。

### 1.6 確定数値の共有ストアが存在しない（BL-015と重複する領域）

車両台数のように複数タスクにまたがる数値について、「どのタスクが確定させた値か」「その値が何か」を機械的に参照する手段がない。結果として、下流タスク（task_1.2）が上流タスク（task_1.1）の確定値を**再導出**しようとし、これが1.1節のスコープ肥大化の一因になっている。

---

## 2. 新設計

### 2.1 データモデルの拡張

#### 2.1.1 `Task`型の新設（`cela_main.py`、`Phase`定義の直前に追加）

```python
class Task(TypedDict):
    task_id: str
    title: str
    description: str
    acceptance_criteria: list[str]   # 独立検証可能な主張を列挙。最大3個。超える場合はtask_planner側でタスクを分割する
    depends_on: list[str]            # 前提として使う他タスクのtask_id（空配列可）
    owns_variables: list[str]        # このタスクで初めて確定させる共有変数名（例: "vehicle_count"）。空配列可
    status: str                      # "pending" / "in_progress" / "completed" / "deferred"
```

#### 2.1.2 `Phase`型の拡張

```python
class Phase(TypedDict):
    phase_id: str
    title: str
    description: str
    allowed_abstraction_levels: list[str]
    focus_scope: str
    expected_time_axis: str
    tasks: list[Task]                # ★新規: BL-018/BL-023により正式にスキーマ化（従来は無型のdictキーとしてのみ存在）
    budget_hint: dict[str, float]     # ★新規（Phase C）: 例 {"初期導入予算": 30000000}。仮説であり絶対制約ではない（2.9節参照）
```

**設計判断の理由**: `tasks`は従来もJSON上には存在していた（`call_task_planner`の出力そのまま）が、`Phase`TypedDictに宣言がなく型として保証されていなかった（BL-018で指摘済みの事実）。今回`Task`型を正式に導入し、`acceptance_criteria`/`depends_on`/`owns_variables`/`status`を型レベルで保証する。

#### 2.1.3 `LineageState`の拡張

```python
class LineageState(TypedDict):
    ...(既存フィールドは変更なし)...
    current_task_id: str                    # ★新規: decision_extractor_nodeのみが書き込む（2.4節）
    verified_facts: dict[str, dict]         # ★新規: {"vehicle_count": {"value": 4, "unit": "台", "source_task_id": "task_1_1", "confirmed_at": 1737...}}
    task_criteria_status: dict[str, list[bool]]  # ★新規: {"task_1_2": [True, False, False]}（acceptance_criteriaのインデックス対応）
```

#### 2.1.4 `Agreement`型の拡張（issue_backlog相当の先送り記録）

```python
class Agreement(TypedDict):
    ...(既存フィールドは変更なし)...
    task_id: str          # ★新規: どのタスクに紐づく合意・成果物・先送りかを明示
    # status に新しい値 "Deferred" を追加（既存: Proposed/Approved/Approved_with_Conditions/Rejected/Implicitly_Accepted）
    # "Deferred" の場合、topic は先送りされた論点名、reason_why に「どのタスクで扱うか」を含める
```

#### 2.1.5 DBスキーマ変更（`init_db`）

```sql
-- 既存テーブルへのカラム追加（起動時に存在確認してから実行、下記2.1.6参照）
ALTER TABLE agreements ADD COLUMN task_id TEXT DEFAULT '';

-- 確定数値の共有ストア（BL-015が指す「一次情報の機械的再利用」の実体の一つ）
CREATE TABLE IF NOT EXISTS verified_facts (
    variable_name TEXT NOT NULL,
    value TEXT NOT NULL,
    unit TEXT DEFAULT '',
    source_task_id TEXT,
    source_phase_id TEXT,
    confirmed_by TEXT,          -- 例: "Expert:cost_optimizer"
    confirmed_at REAL,
    run_id TEXT NOT NULL,
    PRIMARY KEY (run_id, variable_name)
);
```

#### 2.1.6 マイグレーション方針

SQLiteは`ADD COLUMN IF NOT EXISTS`を持たないため、`init_db`内で`PRAGMA table_info(agreements)`を確認し、`task_id`列が存在しない場合のみ`ALTER TABLE`を実行する（既存の`cela.db`との後方互換のため）。

```python
def _ensure_agreements_task_id_column(conn: sqlite3.Connection) -> None:
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    if "task_id" not in cols:
        conn.execute("ALTER TABLE agreements ADD COLUMN task_id TEXT DEFAULT ''")
```

---

### 2.2 task_plannerのプロンプト拡張（`call_task_planner`）

`cela_main.py:1188-1236`のプロンプトに以下を追加する。

```
【重要・追加】
3. 各タスクには以下も必ず含めてください:
   - acceptance_criteria: このタスクで検証されるべき独立した主張を配列で列挙してください。
     **最大3個まで**とし、3個を超える場合はタスク自体を分割してください
     （例: 「車両台数の算出」「初期費用の内訳」「年間ランニングコストの内訳」「感度分析」を
     1タスクに束ねてはいけません。それぞれ独立したタスクにするか、密接に関連する場合でも
     acceptance_criteriaの数を3以内に抑える粒度まで分割してください）。
   - depends_on: このタスクが前提として使う他タスクのtask_idを配列で指定してください
     （前提がなければ空配列）。
   - owns_variables: このタスクで初めて確定させる共有変数名を配列で指定してください
     （例: "vehicle_count"）。同じ変数を必要とする他タスクは、depends_onでこのタスクを
     指定し、値を再導出せず参照する前提とします。
```

出力JSON例（`task_1_2`相当）:

```json
{
    "task_id": "task_1_2",
    "title": "予算制約の明文化",
    "description": "初期導入予算1億円、年間維持費上限3,000万円の枠組みを整理する",
    "acceptance_criteria": [
        "初期導入費用（上限1億円）の内訳を項目別に提示する",
        "年間ランニングコスト（上限3,000万円）の内訳を項目別に提示する"
    ],
    "depends_on": ["task_1_1"],
    "owns_variables": []
}
```

`fallback_phase`（`cela_main.py:1241-1255`）にも同様のフィールド（空配列・空文字）を追加し、スキーマの一貫性を保つ。

---

### 2.3 decision_extractorの拡張（フェーズ・タスク状態の一元管理、BL-024）

#### 2.3.1 唯一の書き手とする設計判断

`decision_extractor_node`を`state["current_phase"]`/`state["current_task_id"]`の**唯一の書き手**とする。理由:

1. `decision_extractor`は既に「会話をUser/Agentの構造化データに変換する」役割を担っており、User AIが「次のタスク（task_1.2）に移行する」と発言した瞬間を検知するのに最適な位置にいる（既存の`Directive`抽出パターン、`cela_main.py:1662`）。
2. 新規LLM呼び出しを追加せず、既存の抽出JSONスキーマにフィールドを追加するのみで済む。
3. 過去に無効化された`generate_user_utterance`側の強制JSON出力（1.2節）を復活させずに済む。

#### 2.3.2 プロンプト拡張（`call_decision_extractor`、`target_role == "user"`分岐）

出力JSONスキーマ（`cela_main.py:1742-1761`付近）に以下を追加する。

```
"advances_to_phase_id": "Userが明示的に次のフェーズへの移行を指示した場合のみそのphase_id。移行がなければnull",
"advances_to_task_id": "Userが明示的に次のタスクへの移行を指示した場合のみそのtask_id。移行がなければnull",
"target_task_id": "この発言が既存の特定タスクに関する場合のtask_id。分からなければ現在のtask_idのまま"
```

#### 2.3.3 機械的検証（`decision_extractor_node`内、書き込み前のフェイルクローズ）

```python
def _resolve_task_transition(state: LineageState, item: dict) -> None:
    """[CONSTRAINT] BL-024: current_phase/current_task_idの唯一の書き手。
    LLMが返したphase_id/task_idがtask_planner確定済みのphases/tasksに実在しない場合は
    書き込みを拒否し、直前の値を維持する（本プロジェクトのcheck_docs_consistency.pyが
    存在しないリンクを機械的に検出するのと同型のフェイルクローズ）。
    """
    next_phase_id = item.get("advances_to_phase_id")
    next_task_id = item.get("advances_to_task_id")
    if not next_phase_id and not next_task_id:
        return

    phase_lookup = {p["phase_id"]: p for p in state.get("phases", [])}
    target_phase = phase_lookup.get(next_phase_id) if next_phase_id else state.get("current_phase")
    if not target_phase:
        return  # 存在しないphase_idは無視（フェイルクローズ）

    if next_task_id:
        valid_task_ids = {t["task_id"] for t in target_phase.get("tasks", [])}
        if next_task_id not in valid_task_ids:
            return  # 存在しないtask_idは無視（フェイルクローズ）
        state["current_task_id"] = next_task_id

    if next_phase_id:
        state["current_phase"] = target_phase
```

`decision_extractor_node`のループ内（`cela_main.py:2460`以降）、各`item`の処理と並行してこの関数を呼ぶ。

---

### 2.4 acceptance_criteria充足チェック（traceability相当）

Detectorは既にBL-016のcarve-out（「先送り項目が名指しされていればminor」）判定のため、Expertの発言が現在タスクの要求項目のどれに応えているかを把握できる文脈を持っている。`call_detector`の出力スキーマ（`cela_main.py`の判定結果JSON）に以下を追加する。

```
"criteria_status": "現在タスクのacceptance_criteriaそれぞれについて、今回の発言で充足されたかを示すbool配列（順序はacceptance_criteriaと対応）"
```

`decision_extractor_node`（またはDetector呼び出し直後の`expert_detector`ノード）が`state["task_criteria_status"][current_task_id]`にこれを保存する。`generate_user_utterance`・`call_expert`のプロンプトにこのチェックリストを注入し、「残りcriteria: [...]」を明示することで、User AI・Expertの双方が現在タスクの充足状況をproseの記憶ではなく構造化データから参照できるようにする。

---

### 2.5 Agreementの"Deferred"ステータス（issue_backlog相当）

Expertが「〇〇は次タスクで扱う」のように明示的に先送りを宣言した場合、`decision_extractor`（Expert直後の`role_instruction`分岐、`cela_main.py:1584-1604`）に以下を追加する。

```
- Agentが「〇〇は次タスク（task_id）で扱う」のように明示的に先送りを宣言した場合、
  action_type: "CREATE", entry_type: "Directive", status: "Deferred" とし、
  content に先送りされた論点を、rationale にどのタスクで扱うかを記載してください。
```

`Agreement.task_id`（先送り元のタスク）と、`content`内に記載される「先送り先のtask_id」により、後続タスクのUser AI/Expertが「このタスクに先送りされた未解決事項」をDBから参照できるようになる（`_build_agreements_context_from_db`が`status == "Deferred"`のレコードを現在タスクのtask_idでフィルタして注入する拡張が必要）。

---

### 2.6 共有変数ストア（`verified_facts`、BL-015と接続）

Expertが`python_repl`で数値を確定させ、その値が該当タスクの`owns_variables`に含まれる場合、`decision_extractor`が抽出したDeliverable/Decisionの`content`から値を拾い、`verified_facts`テーブルにUPSERTする。下流タスク（`depends_on`でこのタスクを指定するタスク）のUser AI/Expertへのプロンプトには、この確定値を「既知の定数」として注入し、「この値は確定済みであり、再導出を指示・実行してはならない」と明記する。

```python
def upsert_verified_fact(conn, run_id: str, variable_name: str, value, unit: str,
                          source_task_id: str, source_phase_id: str, confirmed_by: str) -> None:
    conn.execute(
        "INSERT INTO verified_facts (run_id, variable_name, value, unit, source_task_id, "
        "source_phase_id, confirmed_by, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, variable_name) DO UPDATE SET value=excluded.value, "
        "unit=excluded.unit, source_task_id=excluded.source_task_id, "
        "confirmed_by=excluded.confirmed_by, confirmed_at=excluded.confirmed_at",
        (run_id, variable_name, str(value), unit, source_task_id, source_phase_id,
         confirmed_by, time.time())
    )
```

**設計判断の理由**: どの数値が「確定済みの共有変数」かは、task_plannerが宣言した`owns_variables`によって決まる（2.2節）。抽出自体はLLM（decision_extractor）が行うが、書き込み先のキー名は`owns_variables`に含まれるものに限定する検証を挟み、無関係な数値が誤って"確定値"として固定化されるのを防ぐ。

---

### 2.7 `generate_user_utterance`の再設計（本体のスコープ制御）

`cela_main.py:2118-2124`のペルソナ指示を、「質・厳密さへの非妥協性」と「スコープの広さへの非妥協性」に明確に分離する。

```python
system_prompt += (f"""
    🔥 【発注者としての絶対的なスタンス（質について）】
    あなたは妥協を許さないプロジェクトオーナーです。相手（Agent AI）が「制約が厳しい」
    「要件を満たせない」と泣き言を言ってきても、絶対に【絶対目標】のハードルを下げないでください。
    「制約緩和の検討」や「重要要件の放棄」を提案された場合は、それを却下し、
    『プロとして制約内に収めるための別の技術的アプローチや代替案を考え直せ』と厳しく突き返してください。

    📏 【指示のスコープについて（厳守・質への非妥協性とは別軸）】
    1回の指示で要求してよい内容は、以下の「現在のタスク」の acceptance_criteria の範囲に厳密に限定してください。
    範囲外の追加要求（他タスクの依存項目の前倒し要求、まだ指示していない後続タスクの内容の混入など）は、
    たとえ関連性が高く見えても行わないでください。それは次のタスクの役目です。

    【現在のタスク】
    {current_task_json}

    【この値は確定済みです。再導出を指示・要求しないでください】
    {verified_facts_for_dependencies_json}

    【現在のタスクで未充足の要求項目】
    {task_criteria_status_json}
""")
```

`current_task_json`は`state["current_task_id"]`を用いて`state["phases"]`から対応する`Task`を検索して注入する（`current_task_id`が未設定＝初回ターンの場合は最初のタスクを既定値とする）。`verified_facts_for_dependencies_json`は現在タスクの`depends_on`に含まれるタスクの`owns_variables`を`verified_facts`テーブルから引いたものに限定する。

---

### 2.8 Expert system promptの改修（フィージビリティのエスカレーション区別、Phase C）

`cela_main.py:1379-1384`に以下を追加する。

```
代替案を尽くした上で、それでもなお制約が構造的に非現実的だと誠実に判断した場合は、
検討した代替案とその却下理由を具体的に明示した上で、Resource Arbiterへの調停提起として
明確に扱ってください。これは、検討を尽くさない安易な「無理です」という思考停止とは
明確に区別されます。前者は正当な提起として扱われ、後者は制約放棄とみなされます。
```

### 2.9 予算のトップダウン・カスケード（Phase C）

`Phase.budget_hint`（2.1.2節）に、フェーズ確定時（`arbiter_node`または新設のヘルパー）が`global_constraints`から按分したサブ予算枠を設定する。これは`generate_user_utterance`・`call_expert`の両プロンプトに以下のように注入する。

```
【このフェーズの予算枠（参考値・仮説）】
{budget_hint_json}
上記はあくまで初期の按分仮説であり、絶対的な制約ではありません。
代替案を尽くした上でなお構造的に非現実的な場合は、2.8節の手続きに従い
Resource Arbiterへの調停提起として扱ってください。現場に無理な数字を押し付けて
辻褄合わせをさせることが目的ではありません。
```

**設計判断の理由（ユーザー指摘）**: 現実の（特に日本の）委託開発で頻発する「無理な予算枠を現場・委託先に押し付け、しわ寄せを後工程に送る」病理を、この機構が再現してはならない。そのため`budget_hint`は必ず「仮説」であることを明示し、Expertが誠実に非現実的と判断した場合の構造化エスカレーション経路（2.8節、2.10節）とセットで導入する。

### 2.10 `resource_arbiter`へのルーティング拡張

`arbiter_node`（`cela_main.py:2222-2241`）は現状`check_global_constraint_overrun`（事後の超過チェック）のみを起点とする。Expertが2.8節の手続きで構造的フィージビリティを提起した場合にも、Detectorの`major`（手抜き）による即時差し戻しではなく、`resource_arbiter`への調停として扱う分岐を追加する。詳細なルーティング設計（Detectorがどう「調停提起」と「制約放棄」を区別するか）はBL-017（差し戻しループ脱出機構）と合わせて設計するため、本設計書では入出力の接続点のみを定義し、判定ロジックの詳細はBL-017側に委譲する。

---

## 3. スコープ外

- **Phase B（BL-005: `turn_count`凍結、reflection/facilitator復旧）**: 森レベルの整合性チェックをreflection/facilitatorへ委譲する設計は、BL-005解消後に別途着手する。本設計書の2.3節（`current_task_id`の一元管理）はBL-005の`turn_count`凍結とは独立した別のフリーズバグ（BL-024）であり、BL-005の解消を待たずに着手できる。
- **R4差分パッチ（`whiteboard_drafts`）**: 全文書き直しコストの根本解消はR4のスコープであり、本設計書はR4未実装の前提のまま「束ねる主張の数を減らす」ことでコストを緩和する立場を取る。
- **F-9/F-10.x（Phase 6以降）**: 経験のDNA伝承・MCTS-Forkは対象外。

---

## 4. 完了条件・検証方法

| 項目 | 検証方法 | 成功条件 |
| :--- | :--- | :--- |
| task_planner出力スキーマ | オフライン: `call_task_planner`のフェイクレスポンスで`acceptance_criteria`/`depends_on`/`owns_variables`のパース・フォールバックを確認 | 新フィールドを含むJSONが`Task`型として正しく`state["phases"]`に格納される |
| current_phase/current_task_idの一元管理 | オフライン: 存在しないtask_id/phase_idを含む`decision_extractor`のフェイク出力に対し、`_resolve_task_transition`が書き込みを拒否することを確認 | 不正なIDでは状態が変化せず、正当なIDでのみ更新される |
| generate_user_utteranceのスコープ限定 | 実機: task_1.2相当のタスクで、Expertへの指示が現在タスクのacceptance_criteria範囲を超えないことを目視確認 | 他タスクの依存項目（例: 車両台数の再算出）が指示文に混入しない |
| 検証コストの削減 | 実機: 同種タスクでの差し戻しラウンド数・`python_repl`呼び出し回数を、本対応前（`log/2026-07-19/2056`）と対応後で比較 | ラウンド数・呼び出し回数が明確に減少すること |
| verified_factsの機能 | オフライン＋実機: task_1.1相当が`owns_variables`で確定させた値が、task_1.2相当のプロンプトに「確定済み」として注入されることを確認 | 下流タスクの指示文・Expert出力に、上流タスクで確定済みの値の再導出要求が出ないこと |
| 予算カスケードのエスカレーション | オフライン: Expertが構造的非現実性を提起するフェイクシナリオで、Detectorが`major`（手抜き）ではなく調停提起として分類することを確認 | 誠実なフィージビリティ提起がmajor差し戻しとして扱われない |
| 指標C計測 | `traceability.md`・`impl_Plan.md` R2.9 | 本設計書の対応完了後に着手（[D-020](../decision_log.md)） |

各項目の実装前に、本設計書をAGENTS.md §5.2のブループリントとしてユーザーへ提示し承認を得る。
