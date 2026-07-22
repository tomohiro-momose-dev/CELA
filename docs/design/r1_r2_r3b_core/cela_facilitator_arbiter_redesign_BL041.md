# facilitator / Resource Arbiter 再設計 設計ドラフト（BL-041統合）

**ステータス:** ドラフト（未承認・未実装）
**対象BL:** [BL-041](../issue_backlog.md#bl-041-一度確定した決定例-車両台数を後続タスクの発見を根拠に再検討させる自動メカニズムが存在しないresource-arbiter機構が死んだコードパスになっている)（一度確定した決定を後続タスクの発見から再検討させる自動メカニズムの不在）、[BL-017](../issue_backlog.md#bl-017-差し戻しループ沼からの脱出機構ファシリテーターそもそも論への立ち返り)（facilitatorの当初設計意図との乖離）、[BL-005](../issue_backlog.md#bl-005-turn_countがappinvoke内で凍結され外側ターン表示上限が実態と乖離)（reflection/facilitatorの周期発火が実質的に凍結）
**関連決定:** [decision_lineage.md 論点42](../decision_lineage.md)
**関連要件:** 要件定義書_v35.md F-9/F-10（Phase 6以降のフル版、本設計はそのMVP先行縮小実装）

---

## 1. 背景・スコープ

論点42でユーザーが指摘した「木を見て森を見ず」問題（task_1.1が狭いスコープで車両台数を確定させ、後続タスクで予算不足が判明しても誰も再検討しない）に対し、以下3方向の解決策が提示された。

1. 暫定のリソース配分を先に検討するタスクを置く、または確定値の上書き＋タスク間すり合わせ機構
2. 初期制約は絶対、導出値はデフォルト暫定（`confidence="provisional"`）とし、後で変更の余地を残す
3. 無限議論を避け「何をしないか」を含めたエスカレーションを行う機構 — **facilitatorの役目**

うち2は既に実装済み（`cela_main.py`のExpertプロンプト・`WRITE_AGREEMENT_TOOL`スキーマ・`upsert_verified_fact`のデフォルト変更、2026-07-22）。本ドラフトは残る1・3、および同根の[BL-017](../issue_backlog.md)・[BL-005](../issue_backlog.md)・BL-041本体（`arbiter_node`が死んだコードパスである問題）をまとめて扱う。

**明示的にスコープ外とする事項（Phase 6以降・F-9/F-10フル版）:**
- MCTS-Fork（多分岐並行世界探索、F-10.6）
- Lessons Learned RAG（F-9）
- システム1/システム2の二重過程制御（F-10.1）
- UCB探索パラメータの動的ブースト（F-10.4）

本設計はBL-017が既に定義した「MVP先行縮小実装」路線を踏襲し、現行`facilitator_node`/`arbiter_node`/`reflection_node`という既存の3ノード構成を活かしたまま、**発火条件の修正**と**エスカレーション行動の具体化**に限定する。

---

## 2. 現状の実装（`cela_main.py`、2026-07-22時点でコードから確認した事実）

### 2.1 ノード構成とグラフ配線

| ノード | 発火条件 | 現在の実装 |
|---|---|---|
| `reflection_node` | ①`route_after_expert_decision`: `turn_count % reflection_interval == 0`（**BL-005によりturn_countが`app.invoke()`内で凍結、実質発火しない**）<br>②`route_after_expert_detector`: `expert_retry_count >= 3`（**こちらは正常に発火する**） | `call_reflection`でLLMに`discussion_status`（continuing/completed/stagnant）を判定させるのみ。是正行動は一切取らない |
| `facilitator_node` | `route_after_reflection`: `discussion_status=="stagnant"` または `drift_flag=True` の場合のみ | `call_facilitator`が「もう少し議論を深めてみては」という**穏やかな促し**を1つ生成し`chat_history`に追記するのみ。`facilitation_count>3`で強制halt |
| `arbiter_node` | `route_after_integrator`: Integrator完了後、`needs_revision_phases`が無い場合に必ず通過 | `check_global_constraint_overrun`が`state["global_constraints"]`を走査するが、**このリストへの書き込み箇所がtask_planner_nodeでの初期化（`[]`）以外に存在しない**ため常に空。結果、`arbiter_node`は常に`phases_to_revise=[]`で早期returnし、`call_resource_arbiter`（LLM呼び出し）自体に到達しない |

実ドライラン（`log/2026-07-21/2248`）全文検索で`[Resource Arbiter]`・`[facilitator]`・`[reflection]`・`phases_to_revise`が0件だったのは、上記のうち②（retry上限到達）が一度も発生しなかったこと、およびarbiterが常に空振りしていたことの両方が原因。

### 2.2 `arbiter_node`が本来意図していた位置づけ

グラフ上、`arbiter_node`は **Integrator（全タスク統合）の直後、Reviewer（最終レビュー）の直前** という、実は理にかなった位置に既に配線されている。つまり「全タスクの成果物が出揃った後、確定値同士の矛盾（予算超過等）を横断チェックする」というBL-041が求める機能の**器（グラフ構造）は既にある**。欠けているのは「クレームデータを集約する仕組み」と「実際に機能する調停ロジック」だけである。

---

## 3. 設計方針

### 3.1 A. `global_constraints`の実働化（BL-041本体）

**現状:** `agreements`テーブルには`resource_claims`列（JSON、`write_agreement`ツールのスキーマに既存）があるが、これを`state["global_constraints"]`へ集約する処理が存在しない。

**方針:** Integrator実行直前（`integrator_node`の冒頭、または専用の集約ステップとして`route_after_reflection`→`integrator`の間）に、その時点までの全`agreements`（`status != "Superseded"`）から`resource_claims`を集約し`state["global_constraints"]`を動的に構築する。

```python
# 擬似コード（integrator_nodeまたは専用ノード内）
def _aggregate_global_constraints(agreements: list[dict]) -> list[GlobalConstraint]:
    """resource_claimsを持つagreementsをname単位で集約し、GlobalConstraint配列を構築する。"""
    by_name: dict[str, dict] = {}
    for a in agreements:
        claims = json.loads(a.get("resource_claims") or "{}")
        for name, claim in claims.items():
            # claim = {"phase_id": ..., "value": ..., "total_cap": ...} を想定
            entry = by_name.setdefault(name, {"name": name, "claims": {}, "total_cap": None})
            entry["claims"][claim["phase_id"]] = claim["value"]
            entry["total_cap"] = claim.get("total_cap", entry["total_cap"])
    return [e for e in by_name.values() if e["total_cap"] is not None]
```

これにより`check_global_constraint_overrun`（既存実装、修正不要）が実際に機能するようになる。

**ただし要検討事項:** `resource_claims`をwrite_agreement呼び出し時にExpertが正しい粒度（`{変数名: {phase_id, value, total_cap}}`）で埋めてくれる保証がない。現状`WRITE_AGREEMENT_TOOL`のスキーマは`resource_claims: {"type": "object"}`という自由形式で、具体的なキー構造の指示がプロンプトに無い。本設計と合わせてスキーマとプロンプト指示を具体化する必要がある（§5「未決事項」参照）。

### 3.2 B. `call_resource_arbiter`のエスカレーション行動メニュー化

**現状:** `call_resource_arbiter`（`cela_main.py:2417`付近）はLLMに`phases_to_revise`（再考すべきphase_idのリスト）と`rationale`を出させるのみで、**具体的な選択肢を提示していない**。

**方針:** ユーザー提案（「車両のリース」「既存SaaS利用」「強制決定」）を一般化し、プロンプトに以下4種の具体的なエスカレーション行動を**段階的な順序**として明示する。上位3つ（Substitute/Descope/Force Decision）は同一の抽象度（今のゴール・制約は維持したまま、その枠内でのやりくり）で解決を試みる行動であり、すべて失敗して初めて第4段階（そもそも論）に昇華する。

| # | 行動 | 説明 | 対応する既存機構 |
|---|---|---|---|
| 1 | **代替案への切替（Substitute）** | より安価な代替手段（自社開発→既存SaaS、購入→リース等）へのピボットを提案 | `write_agreement`のSUPERSEDEで既存Decisionを置き換え |
| 2 | **スコープ縮小（Descope）** | 要求水準そのものを引き下げる代替案を提示（ユーザー承認必須） | `write_agreement`で新規Directiveを`status="Proposed"`提案、Userの承認待ち |
| 3 | **強制決定（Force Decision）** | 複数の代替案から機械的に最有力案を選び、Userに"decide-or-explain"（採用するか、明確な反証を出すか）を迫る | `phases_to_revise`＋Userへの強制エスカレーションメッセージ |
| 4 | **そもそも論への昇華（Escalate to First Principles）** | 1〜3が全て手詰まりの場合、「今のゴール・制約の前提自体が矛盾を生んでいる」と判断し、対立している前提（例:「車両は自治体保有」vs「初期予算1億円で全て賄う」）を**構造化して人間（User）に提示**し、判断を仰ぐ | 既存の`facilitation_count>3`時の強制halt処理を流用するが、「上限回数に達したので停止」という無内容な理由ではなく、対立構造そのものを`why`欄に明示した`Decision`をDBに残す |

`confidence="provisional"`（BL-041で実装済み）のverified_factsが超過の原因になっている場合は、まず**その値自体をSUPERSEDE対象の第一候補**として提示する（=「木を見て森を見ず」で決めた暫定値をすり合わせの起点にする、というユーザーの提案1に対応）。

**第4段階「そもそも論」の位置づけ（重要）:** これは要件定義書F-10.6（MCTS-Fork、多分岐並行世界探索）の**縮小版の入口**にあたる。F-10.6のフル実装（複数ブランチを実際にフォークして並行探索し、最良案を自動マージする）は本設計のスコープ外（Phase 6以降）のままとする。本設計が第4段階で行うのは「対立する前提を検出し、構造化して人間にSOSを出す」ところまでであり、その先の「実際に複数の解決ブランチを試してみる」判断・実行は人間（User）に委ねる。つまりBL-017が言う「ゴール抽象化・そもそも論への立ち返り」という当初設計意図のうち、**検出とエスカレーションの部分だけをMVPとして先行実装**し、並行探索・自動フォークの部分は据え置く。

### 3.3 C. facilitatorの周期発火修正とエスカレーション統合（BL-005/BL-017）

ユーザー補足：「facilitatorはもともと議論の膠着を緩和させる役目だったため、発火タイミングの調整が必要。reflectorの様に数ターン毎に様子を見させるなど」

**現状の発火経路の問題:**
- 経路①（`turn_count % reflection_interval`）はBL-005によりほぼ動かない。
- 経路②（`expert_retry_count>=3`）は同一タスク内の差し戻し限定であり、「複数タスクにまたがるリソース膠着」は検出できない。

**方針:**
1. BL-005の根本修正（`turn_count`を`app.invoke()`呼び出しをまたいで正しくインクリメントする、または外側ループのカウンタをstateに正しく反映する）を本設計の前提として先に対応する。
2. `reflection_node`の判定結果`discussion_status`に、既存の"stagnant"に加えて`arbiter_node`由来の「リソース超過が検出されたが未解決」という状態を合流させ、facilitatorが呼ばれる条件を「議論の停滞」だけでなく「リソース調停の必要性」にも拡張する。
3. `facilitator_node`が呼ぶ`call_facilitator`に、§3.2で定義した4段階のエスカレーション行動メニューを（Arbiterと共通のプロンプト部品として）持たせ、`facilitation_count`に応じて強さを変える。現行の「`facilitation_count>3`で問答無用にhalt」という一段階設計を、以下のように置き換える：

   | `facilitation_count` | 行動 |
   |---|---|
   | 1回目 | 穏やかな促し（現行の`call_facilitator`のまま） |
   | 2回目 | 段階1〜3（Substitute/Descope/Force Decision）を具体的に提示 |
   | 3回目 | 段階4（そもそも論への昇華）へ移行し、対立する前提を構造化してUserにSOSを出し、`halt`する |

   これにより、現行の「3回促してもダメなら無言で停止」から、「3回目には“なぜ止まったか”が対立する前提の言語化として`decisions`テーブルに残る」形に変わる。

---

## 4. 完了条件（実装着手時のたたき台）

- [ ] BL-005の根本修正（`turn_count`の正しい伝播）
- [ ] `WRITE_AGREEMENT_TOOL.resource_claims`のスキーマ具体化（`{変数名: {phase_id, value, total_cap}}`）とプロンプト指示追加
- [ ] `_aggregate_global_constraints`の実装と、Integrator直前での`state["global_constraints"]`構築
- [ ] `call_resource_arbiter`プロンプトへの3種エスカレーション行動メニュー追加
- [ ] `facilitator_node`の段階的エスカレーション（1-2回目は促し、3回目でメニュー提示）
- [ ] オフラインスモークテスト（`global_constraints`集約、arbiterの超過検出、facilitatorの段階制御）
- [ ] 実LLM再ドライランで、意図的に予算超過シナリオを仕込んだ場合にarbiter/facilitatorが実際に発火することを確認

---

## 5. 未決事項（ユーザー確認が必要）

1. **`resource_claims`のスキーマ具体化**は`WRITE_AGREEMENT_TOOL`という既存の重要インターフェースの変更であり、AGENTS.md §7（定数変更の事前承認）に該当する可能性がある。具体的なキー構造案（§3.1）でよいか要確認。
2. **§3.2「強制決定」の具体的な発動条件**（何回目のエスカレーションで、誰に対してどう強制するか）は今回まだ具体化していない。ユーザーの「予算の取り合いでいつまでも議論するか」という懸念に直接応える部分なので、次の設計サイクルで詰める必要がある。
3. **BL-005の根本修正の方式**（`turn_count`をどこでインクリメントし直すか）は本ドラフトの前提としているが、別途独立した設計・承認が必要。
4. **すり合わせタスクを最初に置く案**（ユーザー提案1の前半）は今回の設計に含めていない。task_plannerの出力スキーマ変更を伴うため、別途検討が必要か確認したい。
