# 【第0部】調査の経緯と、私（Claude）による事実検証の結果

## 経緯

ユーザーが `log/2026-08-08/1514`（09:17–21:41、`facilitation_count > 5` で `halt`）をレビューし、
以下3点の調査を指示した：

1. `task_2_1` が自分の `acceptance_criteria` 外（車両台数・フリート実現可能性）まで背負い込み、
   本来存在しない矛盾を自作自演で解こうとしていた状態を、どうすれば克服できるか
2. User AI は1度気づいたのに、なぜそのままになってしまったのか
3. この部分は本来 Reflector と Facilitator が指摘・整理するのが筋なのに、なぜ議論が修正できなかったのか

## 私が実ログとコードから確定させた事実（設計の前提）

**事実1｜halt の引き金となった 20 件は、全件が triage 済みだった。**
`reflection_node` が「escalated行のうち20件…がユーザーノードを3回通過しても未解決のため、
discussion_statusを機械的にstagnantへ上書きしました」と記録した、その 20 topics を実ログから
抽出し、各々の `defer_to_task_id` を突き合わせた結果、**20件すべてに受け皿 task_id が設定済み**
であった。未 triage の issue は 1 件も無い。12 時間のランが、全件正しく triage 済みの一覧を
根拠に「停滞」と断罪されて停止した。

| topic | defer_to |
|---|---|
| phase2_legal_responsibility_insurance | task_4_2 |
| phase2_driver_recruitment_feasibility | task_2_2 |
| phase2_autonomous_demo_cost_monitoring | task_3_1 |
| phase2_call_center_operations | task_2_3 |
| phase2_budget_overrun_composite_service | task_5_1 |
| goal_revision_consistency_check_phase_1_task_1_1 | **task_2_1** |
| task1_3_budget_overrun_composite_service | **task_2_1** |
| phase2_integrated_technical_feasibility | task_3_1 |
| task2_1_ver10_core_reconciliation | task_5_1 |
| phase2_volunteer_sustainability | task_2_2 |
| phase2_demand_taxi_cost_model_risk | task_2_2 |
| phase2_type_approval_cost_underestimation | task_3_1 |
| goal_revision_consistency_check_phase_1_task_1_2 | **task_2_1** |
| phase2_reverse_engineered_numbers | task_5_1 |
| task2_1_vehicle_count_discrepancy | **task_2_1** |
| phase2_demand_satisfaction_roadmap | task_2_2 |
| task2_1_vehicle_count_contradiction | **task_2_1** |
| task1_3_demand_taxi_operating_cost_unrealistic | task_2_2 |
| phase2_subsidy_advertising_revenue_risk | task_5_2 |
| goal_revision_consistency_check_phase_1_task_1_3 | **task_2_1** |

**事実2｜うち 6 件は `task_2_1` 自身への先送り（自己先送り）だった。**
上表の太字 6 件。これらは「車両台数」「ゴール改定整合性」——まさに `task_2_1` を空転させた論点。
DEFER の実装（`_write_issue_impl`、`cela_main.py:2930-2936`）は受け皿 task_id の**実在**しか
検証せず、実行中のタスク自身への先送りを拒否しない。

**事実3｜`task_2_1` の acceptance_criteria に車両台数は含まれない。**
`task_2_1` の `acceptance_criteria` は3項目（需要マトリクス作成／生活必須移動の優先順位付け／
5サービスへの需要マッピング）、`owns_variables` は3つ（`od_matrix_by_segment` /
`essential_mobility_demand` / `service_demand_mapping`）のみ。車両台数と30分待ち制約の
実現可能性証明は `task_2_2` の責務であり、`task_2_2` の計画には**矛盾の無い解**が既に存在する
（乗合2台×8名＋デマンド2台×4名＝供給48人/時 vs 生活必須需要27人/時、余裕率78%）。
ゴールは既に2回改定され「複合モビリティ、レベル4は将来のゲート付きオプション」になっていた。
**ゴール改定は効いていた。ズレていたのは `task_2_1` が実際にやっていた作業の方**である。

**事実4｜User AI は正しく気づき、正しく行動していた。**
実ログの `think`：「現タスクの acceptance_criteria は需要モデリングとサービス需要マッピングで
あり、全費目のコスト積算は task_5_1 の責務である」と述べ、「task_2_1 で年間維持費と法的・安全
仕様まで完成させる」を `rejected`（理由：「タスクスコープ違反となり、後続タスクの依存順序を
崩す」）としている。そのうえで `write_issue(DEFER)` を実行した。**判断も行動も正しかった。**

**事実5｜`escalate_premise_concern` の呼び出しは全ラン通じて 0 回。**
これは怠慢ではない。`task_2_2` の計画が示すとおりゴール自体は整合していたため、
「ゴール文の前提そのものの矛盾」という発火条件に該当しなかった。加えてツール説明文自身が
「呼び出しても現在のタスクのスコープ外に踏み込む許可は得られません」と明記しており、
仮に呼んでも解決しない種類の問題だった。必要だったのはエスカレーションではなく「やめること」。

## Plan エージェントによる設計中に発見された、私の診断への補正3点（全て私が実コードで再検証済み）

**補正①｜BL-158 のゲートは既に Camp A（DEFER 済みを除外する側）だった。**
`cela_main.py:9913-9934` は `_get_blocking_issues_for_transition`（SQL に
`AND (defer_to_task_id IS NULL OR defer_to_task_id='')` を含む）を単一の判断源としている。
よって「User AI が毎ターン嘘の RESOLVE を強いられていた」という私の当初の説明は不正確で、
正しくは「**1回 DEFER すればその issue は恒久的にブロック集合から消え、以後ゲートは沈黙する**」。
この補正は設計上決定的である——**自己先送りを塞ぐと（拒否でも消費側無効化でも同じく）
BL-158 のゲートが毎ターン再発火する状態に戻る**ため、正直な出口（ACKNOWLEDGE）を
用意せずに塞ぐと、別経路で同じ halt を招く。要件3と要件5が不可分に結合していることの根拠。

**補正①-b（付随して発見した既存の抜け穴）**：`state["user_wrote_issue_resolution"]`
（`cela_main.py:9215`）は `get_last_write_issue_resolve_or_defer_succeeded()` の戻り値、すなわち
「そのターンで**何らかの** RESOLVE/DEFER が成功したか」という真偽値であり、**ブロック対象の
issue と紐づいていない**。無関係な issue を 1 件 RESOLVE するだけで BL-158 のゲートを黙らせ
られる。本 BL では修正対象外とするが、リスクとして記録する（§9-R? 参照）。

**補正②｜`_get_forced_escalated_issues_text` は `_get_escalated_issues` を呼んでいない。**
`cela_main.py:5102-5105` は自前で同じ SQL を再実行している。よって「Camp B のヘルパーを直せば
Camp A も直る」という関係にはなく、述語のコピーは **4 箇所**（`5106-5109` / `10043` /
`10643-10647` / BL-158 は `10043` の再利用）存在する。

**補正③｜`reflection_node` の内部不整合は「同一 `if` ブロック内」だった。**
`if _stale_escalated:`（`cela_main.py:10625`）の内側で、`10626` が `discussion_status="stagnant"`
を設定し、`10643` が `_formalizable_stale` に DEFER フィルタを適用している。
「停滞と断罪する集合」と「その停滞を是正するため計画へ渡す集合」が、同一関数の同一ブロックで
食い違っている。本 BL が確立すべき不変条件の最も直接的な違反例。

## 私（Claude）による、Plan エージェント設計 §7 への補正 —— 段階リリース推奨は成り立たない

Plan エージェントは §7 で「S1–S6 を第1弾（事故の再発防止として完結）、S7+S8 を第2弾」という
段階リリースを推奨し、S3 について「これ単体で本事故（halt）は再発しない」と記している。
ユーザーからの問い（「全体の稼働には S7,8 も必要と取れるが」）を受けて再検証した結果、
**この推奨は誤りである**。以下の理由により、S1–S6 だけでは今回の halt は防げない。

**根拠**：停滞判定のトリガー（`cela_main.py:10625`）は `if _stale_escalated:` であり、
**滞留が 1 件でもあれば** `discussion_status = "stagnant"` になる。S1–S6 適用後、
実ログの 20 件は次のように分かれる：

- **14 件**（他タスクへ正当に DEFER 済み）→ `_is_issue_effectively_deferred` が True →
  actionable から外れ、停滞にカウントされなくなる ✓
- **6 件**（`task_2_1` 自身への自己先送り）→ §2.1 の設計上、自己先送りは意図的に
  「先送りされていない」と判定される（`current_task_id` と一致すれば False を返す）→
  **actionable のまま残り、停滞判定を発火させ続ける**

したがって `stagnant` → facilitator → `facilitation_count` 枯渇 → `halt` の経路は
S1–S6 適用後もそのまま生きている。

**さらに、task_2_1 の空転（スコープ汚染）も 6 件分は解消しない**：
`task2_1_vehicle_count_contradiction` / `task2_1_vehicle_count_discrepancy` は自己先送りの
ため actionable 側に残り、S4（pin のトーン分離）を入れても **「⚠️要対応」のまま Expert の
プロンプトに刺さり続ける**。これらを本来あるべき `task_2_2` へ送り直させる唯一の経路が
**S8 の拒否メッセージ**（「この懸念が本当に別タスクの責務なら、その実在する task_id を
defer_to_task_id に指定して DEFER する」）であり、S8 を入れると BL-158 のゲートが再発火する
ため、正直な出口として **S7 が必須**になる（§3.3 の相互作用分析のとおり）。

**結論**：S7 と S8 は「あれば望ましい追加機能」ではなく、**本 BL が事故を実際に解決するための
必須要素**である。§7 の「S3 単体で本事故は再発しない」という記述は、20 件のうち 14 件に
ついてのみ正しく、自己先送りの 6 件については誤りであるため、**実装時は §7 の段階リリース
推奨ではなく本節の判断（S1–S8 は因果的に結合しており分割の前提が成り立たない）に従うこと**。

なお S1–S6 が単独で持つ価値がゼロというわけではない：(a) 20 件中 14 件が Expert の
「要対応」pin から外れる（スコープ外ノイズの約 7 割削減）、(b) Reflection/Facilitator が
タスクスコープを見られるようになる（S5）、(c) 停滞判定の母集団が 14 件分だけ正しくなる。
ただし「効果はあるが事故そのものは再発し得る」中間状態であることを理解した上で選ぶこと。

## 既存テストへの影響（私が事前確認済み）

`tests/test_bl136_issue_visibility_and_transition_gate.py` のフィクスチャは
`current_task_id="task_1_1"` / `defer_to_task_id="task_1_2"` で統一されており、**自己先送りでは
ない**。よって S8（自己先送り拒否）を導入しても既存テストは赤くならない。
`test_bl158_*` / `test_bl167_*` も同様に実装時に要確認。

## ユーザー判断（2026-08-08）

- **実装スコープ：まず「設計書の保存のみ」を承認**。S1〜S8 の実装は別セッションで判断する
  （実装スコープの判断自体は、上記「段階リリース推奨は成り立たない」を踏まえ後日決定）。
- **定数承認（AGENTS.md §7）：`_BL194_ACK_TTL_ROUNDS = 3` / `_BL194_ACK_MAX_GRANTS = 2` を承認**
  （設計書の §5.3 の推奨値どおり。BL-144 の滞留閾値 3 ラウンドと揃え、「ACK は滞留カウントを
  ちょうど 1 周期分止める」という意味を持たせる。累計 2 回上限により最悪 6 ラウンドで必ず
  滞留判定へ復帰し、不死身化しない）。この承認は S7 実装時にそのまま有効とする。

---

# 【第1部】Plan エージェントによる基本設計（原文・要約なし）

以下は Plan エージェントが出力した設計の全文である（AGENTS.md §7 に従い一切要約しない）。

---

# BL-194 基本設計：`defer_to_task_id` の解釈不統一と自己先送りによる偽の停滞判定・強制停止

対象ファイル：`C:\ai_work\CELA\cela_main.py`（単一モノリス）
関連ログ：`log/2026-08-08/1514`（09:17–21:41、`facilitation_count > 5` で `halt`）
関連 BL：BL-096 / BL-103 / BL-123 / BL-125 / BL-136 / BL-144 / BL-145 / BL-158 / BL-167 / BL-170 / BL-191 / BL-192
関連 D：D-079 / D-080（severity↔status 不変条件）、D-127（BL-157 の例外）

---

## 0. 設計中に判明した、診断への補正・拡張

指示された診断は概ね実コードと一致していたが、実装計画に直接影響する差分が **3点** ある。これらは設計判断の前提として先に明示しておく。

### 補正①（重要）：BL-158 のゲートは「毎ターン必ず発火する」わけではない

診断は「BL-158 のゲート（`cela_main.py:9913`）は User AI が RESOLVE/DEFER を呼ばない限り毎ターン `major` にする」と述べているが、実コード（`cela_main.py:9913-9934`）は次の **論理積** で発火する：

1. `target_role == "user"`
2. `_get_blocking_issues_for_transition(conn, run_id, current_task_id)` が非空
   （＝ `status='escalated'` **かつ** `severity='major'` **かつ** `last_seen_task_id == current_task_id` **かつ** `defer_to_task_id` が空、の行が存在）
3. `state["user_wrote_issue_resolution"]` が False

つまり **BL-158 のゲートは既に Camp A（DEFER 済みを除外する側）に属している**。したがって、

- 「User AI が DEFER をゲート回避の逃げ道に使った」という因果は、**1回 DEFER すればその issue は恒久的に `_get_blocking_issues_for_transition` から消え、以後そのターンで何も呼ばなくてもゲートは沈黙する**、という形で成立する（毎ターン DEFER し続ける必要はない）。
- 逆に言えば、**自己先送りを消費側で「先送りされていない」と扱う（要件3の後者）だけで、BL-158 のゲートは即座に毎ターン再発火する状態に戻る**。これは要件3が指摘する「逃げ道の喪失」が、拒否（tool boundary）だけでなく **消費側での無効化でも同じ強度で発生する** ことを意味する。この点は設計上決定的であり、§5 の段階リリース判断の根拠になっている。
- また `state["user_wrote_issue_resolution"]`（`cela_main.py:9215`）は「そのターンで **何らかの** RESOLVE/DEFER が成功したか」の真偽値であり、**ブロック対象の issue と対応づいていない**。無関係な issue を1件 RESOLVE するだけでゲートを黙らせられる既存の抜け穴がある。本 BL ではこの抜け穴自体は修正対象外とするが（BL-158 の設計変更になり影響範囲が別物）、§9 のリスクとして記録する。

### 補正②：`_get_forced_escalated_issues_text` は `_get_escalated_issues` を呼んでいない

`cela_main.py:5102-5105` は `_get_escalated_issues` を呼ばず、**自前で同じ SQL を再実行**している。つまり「Camp B のヘルパーを直せば Camp A も直る」という単純な関係にはなく、Camp A 側にも同じ述語のコピーが存在する（フィルタの4重複：`5106-5109` / `10043` / `10643-10647` / BL-158 は `10043` の再利用）。共有ヘルパー化の対象は **4箇所** であって3箇所ではない。

### 補正③：Camp B の内部不整合は 30 行差ではなく「同一 `if` ブロック内」

`reflection_node` の `10609`（stagnant 判定に使う `_escalated_now`：無フィルタ）と `10643`（`_formalizable_stale`：フィルタあり）は、`if _stale_escalated:` という **同じ分岐の内側** に同居している。すなわち「停滞と断罪する集合」と「その停滞を是正するために計画へ渡す集合」が同一関数の同一ブロックで食い違っている。これは本 BL が確立すべき不変条件（§1）の最も直接的な違反例であり、修正の説得力の中核として扱う。

---

## 1. 本 BL が確立する不変条件（設計の背骨）

> **[BL-194 不変条件] 「督促する対象集合」と「滞留＝停滞として数える対象集合」は、常に同一の述語で決定されなければならない。**

今回の事故は、この2集合が乖離したことそのものである。

| | 督促（懲罰的経路） | 是正・免責（救済経路） |
|---|---|---|
| Camp A（フィルタあり） | BL-136 強制解決文、BL-158 機械的差し戻し、BL-125 遷移ゲート | BL-145 計画化 |
| Camp B（フィルタなし） | **BL-103 pin「要対応」**、**BL-096/144 停滞判定**、BL-096 facilitator 名指し | — |

20件全ての escalated issue が「受け皿あり」と triage 済みであったにもかかわらず、Camp B のみが 20件を「未対応」と数え続け、`discussion_status = "stagnant"` → facilitator → `facilitation_count > 5` → `halt` に至った。したがって本 BL の第一の仕事は **述語の単一化**（§2）であり、第二の仕事は **その述語が自己先送りを「先送りではない」と正しく判定すること**（§3）である。

---

## 2. Phase 1：述語の単一化（`_is_issue_effectively_deferred` / `_get_actionable_escalated_issues`）

### 2.1 新規ヘルパー（配置：`_get_escalated_issues`（`cela_main.py:3046`）の直後）

```python
def _is_issue_effectively_deferred(conn: sqlite3.Connection, run_id: str, issue: dict,
                                    current_task_id: str = "") -> bool:
    """[BL-194] 「この issue には、今このタスク以外の実効的な受け皿がある」と機械的に言えるか。

    [CONSTRAINT] BL-136 の DEFER は status を変えず defer_to_task_id だけを立てる設計のため、
    「受け皿があるか」の判定は列の有無ではなく述語で行う必要がある。従来その述語は
    _get_forced_escalated_issues_text(BL-136/167) / _get_blocking_issues_for_transition(BL-125) /
    _formalizable_stale(BL-145) の3箇所に別実装でコピーされ、_get_escalated_issues(BL-096)を
    使う側（BL-103 pin・BL-096/144 停滞判定・facilitator 名指し）には一切存在しなかった。
    log/2026-08-08/1514 で、全20件が triage 済み（全件 defer_to_task_id あり）であるにも
    かかわらず停滞判定だけが発火し 12 時間のランが halt した事故の直接原因（BL-194）。

    [REJECTED] status に新しい値（'deferred'）を導入して SQL 一発で表現する案は却下した。
    D-079/D-080 の「severity='major' ⇒ status='escalated'」不変条件と、_bump_issue_occurrence
    の再発昇格・_write_issue_impl 全分岐の `status != 'resolved'` 判定がこの不変条件に依存して
    おり、status 語彙の拡張は BL-096 系全体の再設計になるため（§8 参照）。
    """
    target = issue.get("defer_to_task_id") or ""
    if not target:
        return False
    # [BL-194] 自己先送り: 受け皿が「今まさに実行中のタスク」なら、先送りは何も先送りしていない。
    if current_task_id and target == current_task_id:
        return False
    # [BL-167] 受け皿タスクが既に完了済みなら、その受け皿は失効している（永久迷子の防止）。
    if _is_task_completed(conn, run_id, target):
        return False
    return True


def _get_actionable_escalated_issues(conn: sqlite3.Connection, run_id: str,
                                      current_task_id: str = "") -> list[dict]:
    """[BL-194] status='escalated' のうち、「今このタスクで実際に対応を迫るべき」行だけを返す。
    _get_escalated_issues（BL-096、生の全件）は、対応予定の有無を問わず全件を見せてよい
    用途（completed 判定の抑止・参考表示）に限って使い続けること。
    """
    return [
        r for r in _get_escalated_issues(conn, run_id)
        if not _is_issue_effectively_deferred(conn, run_id, r, current_task_id)
    ]
```

**`current_task_id` を引数にした理由（重要）**：自己先送りの判定は本来「DEFER を呼んだ時点の実行中タスク」との比較である。消費側で `defer_to_task_id == last_seen_task_id` という近似を使う案も検討したが、**BL-191 の `redirect_backward`（過去タスクへ意図的に戻る）と衝突する**。例えば task_3_1 実行中に発見された「task_2_1 の成果物が新ゴールと不整合」という issue を task_2_1 へ DEFER するのは正当な後方申し送りだが、その issue の `last_seen_task_id` が過去に task_2_1 だった場合、近似判定は誤って自己先送りと断定する。呼び出し側は全て `state` を持っており `current_task_id` を渡せるため、近似は不要（`_build_escalation_pin_text` の3呼び出し元も含めて全て `state` を保持していることを確認済み）。

### 2.2 既存4箇所の置換／据え置き

| # | 箇所 | 変更 | 理由 |
|---|------|------|------|
| A-1 | `_get_forced_escalated_issues_text`（`5090-5126`） | 自前 SQL＋フィルタ（`5102-5109`）を `_get_actionable_escalated_issues(conn, run_id, current_task_id)` へ置換。シグネチャに `current_task_id: str = ""` を追加し、呼び出し元（`generate_user_utterance`）から `state.get("current_task_id","")` を渡す | 述語の単一化。副次効果として **自己先送り issue が BL-136 の強制対象へ復帰する**（従来は「受け皿あり」扱いで永久に督促外だった） |
| A-2 | `_get_blocking_issues_for_transition`（`10032-10046`） | **SQL は据え置き**。ただし `exclude_acknowledged: bool = False` を Phase 3 で追加（§5） | BL-125 は「タスクから **離脱する** ときのゲート」であり、BL-167 の受け皿失効リバイバルを持ち込むと、完了済みタスクへ DEFER された issue が離脱を新たにブロックし始める。これは救済ではなく **新規のデッドロック**（§9-R2）。関心事が違うため統一しない、と明示的に決定する |
| A-3 | `_formalizable_stale`（`10643-10647`） | `_stale_escalated` 自体が既に actionable 済みになるため、フィルタ式を削除し `_formalizable_stale = _stale_escalated` へ簡約。BL-145/BL-167 のコメントは「フィルタは上流の `_get_actionable_escalated_issues` へ移動した」と書き換える | 補正③の内部不整合の解消。二重フィルタを残すと「上流が変わっても下流が古い述語を持つ」という同型事故の再発源になる |
| B-1 | `reflection_node` 停滞判定（`10609`） | `_get_escalated_issues` → `_get_actionable_escalated_issues(get_active_conn(), state["run_id"], state.get("current_task_id",""))` | **本事故の一次修正**。triage 済みの issue で停滞判定を発火させない |
| B-2 | `reflection_node` `escalation_active`（`10676`） | **据え置き（生の `_get_escalated_issues`）** | `escalation_active` は BL-096 の「エスカレーション解消の一度きり復帰通知」（`_build_escalation_resume_notice`）のトリガー。actionable に切り替えると **DEFER しただけで「解決しました、通常業務へ戻ってください」という虚偽の通知**が飛ぶ。意味が違うので変えない。`_escalated_now`（生）と `_actionable_escalated`（絞込）を別変数として明示的に併存させる |
| B-3 | `facilitator_node` の `escalated_issues_text`（`10761-10766`） | `_get_actionable_escalated_issues(...)` へ置換 | 「🚨 最優先で解消させてください」という最強トーンのブロック（`call_facilitator` `8151-8166`）へ供給される値であり、triage 済みを流し込むのは BL-194 不変条件の直接違反。空になった場合は `escalated_issues_block` 自体が消える既存分岐（`8167`）がそのまま働く |
| B-4 | `call_reflection` の `constraint_log_lines`（`7942-7946`） | **除外はせず、行に注記を付す**（§2.3） | 除外すると reflection が `completed` を宣言できてしまう（§9-R1） |
| B-5 | `_build_escalation_pin_text`（`3057-3072`） | actionable のみを返すよう変更＋`current_task_id` 引数追加。DEFER 済み分は §2.4 の新ヘルパーへ分離 | 「⚠️要対応」という見出しの意味を正しくする |

### 2.3 `call_reflection` を「除外」ではなく「注記」にする理由

`call_reflection` のプロンプト（`7976-7981`）は
「上記のいずれかに1件でも未解決の項目・矛盾・エスカレーション済み懸念が残っている場合、`discussion_status` を `"completed"` にしてはいけません」
と明記しており、この一覧は **停滞判定の材料であると同時に、完了宣言の抑止材料** という二重の役割を負っている。actionable のみに絞ると、DEFER 済み（＝未解決）の issue が20件あっても reflection が `completed` を宣言できる状態を作ってしまう。これは「絶対に halt しない方向への過剰修正」（要件2の警告そのもの）。

したがって `call_reflection` では **全件を出し続け、行ごとに状態を注記する**：

```python
# [BL-194] reflection の escalated 一覧は「停滞判定の材料」と「completed 宣言の抑止材料」を
# 兼ねている。DEFER 済み行を一覧から落とすと後者が壊れ（未解決なのに completed を宣言できる）、
# 落とさないと前者が壊れる（triage 済みで停滞と誤断）。両立させるため、一覧は全件のまま
# 残し、行ごとに「対応予定 task_id が確定済みか」を注記して役割を分離する。
# 機械的な stagnant 上書き（reflection_node）側は _get_actionable_escalated_issues を使う。
for i in escalated_issues:
    _defer_note = ""
    if _is_issue_effectively_deferred(_conn, state["run_id"], i, state.get("current_task_id", "")):
        _defer_note = (
            f"【対応予定 task_id={i['defer_to_task_id']} が確定済み。"
            "完了(completed)判定では未解決として扱うこと。ただし現在タスクでの停滞(stagnant)の"
            "根拠にはしないこと——対応する担当タスクが既に決まっているため】"
        )
    constraint_log_lines.append(
        f"- [issue_log topic={i['topic']}] {i['description']}（累積{i['occurrence_count']}回発生）{_defer_note}"
    )
```

### 2.4 BL-103 pin のトーン分離（`_build_deferred_issue_pin_text` 新設）

要件1の指摘どおり、DEFER 済み issue も **文脈としては見せ続けるべき**（担当が決まっている懸念の存在を Expert/Detector が知らないと重複起票が起きる）が、「要対応」ラベルは害である。`task2_1_vehicle_count_contradiction`（task_2_2 スコープ）が Expert のプロンプトへ毎ターン「要対応」として刺さり続けたことが、Expert が task_2_1 の中で車両台数を再導出し続けた直接の機械的原因だった。

`_build_planned_issue_pin_text`（BL-145、`3115-3129`）の非強制トーンを先例として、対になるヘルパーを新設する（配置：`_build_escalation_pin_text` の直後）：

```python
def _build_deferred_issue_pin_text(conn: sqlite3.Connection, run_id: str,
                                    current_task_id: str = "") -> str:
    """[BL-194] status='escalated' だが実効的な受け皿（別 task_id）が確定済みの行を、
    非強制トーンで参考提示する。BL-103 の pin は従来これらを「⚠️要対応」として毎ターン
    Expert/Detector/User AI へ刺し続けており、log/2026-08-08/1514 では task_2_2 スコープの
    車両台数 issue が task_2_1 実行中の Expert プロンプトへ数時間にわたり「要対応」として
    表示され続けた結果、Expert が現在タスクの acceptance_criteria に無い車両台数の再導出を
    繰り返した（Ver.1→Ver.41 の churn の機械的な引き金）。
    [CONSTRAINT] 文脈自体は落とさない（重複起票の防止）。落とすのは「今あなたが解決せよ」
    という強制トーンだけ、という BL-145 _build_planned_issue_pin_text と同じ設計。
    """
    deferred = [
        r for r in _get_escalated_issues(conn, run_id)
        if _is_issue_effectively_deferred(conn, run_id, r, current_task_id)
    ]
    if not deferred:
        return ""
    return "\n".join(
        f"- topic={i['topic']}: {i['description']}"
        f"（対応予定 task_id={i['defer_to_task_id']}。現在のタスクでこれを解決する必要はありません。"
        "現在タスクの acceptance_criteria に無い内容をこの懸念のために先取りしないでください）"
        for i in deferred
    )
```

注入は既存3箇所の直後に、既存の `open_issue_pin` / `planned_issue_pin` と完全に同じ形で追加する：

- `call_expert`（`6825-6831` 直後）：見出し `【📤 対応予定が確定済みの懸念（参考・現タスクでは対応不要、issue_log）】`
- `call_detector` Pass 1（`7278-7281`）：同見出し＋**Detector 専用の1文**
  「以下は担当タスクが別に確定している懸念です。**現在タスクの成果物にこれらが反映されていないことを理由に major と判定しないでください**（BL-194）。」
  — これは BL-123 が Detector に pin を導入した目的（他ロールが折り込み済みの懸念を知る）を保ちつつ、逆方向の誤用（スコープ外を理由とした差し戻し）を塞ぐ。今回のログで Detector の major 差し戻しが churn を再点火し続けた経路への直接の対処。
- `generate_user_utterance`（`8911-8922` の並びの末尾）：同見出し

---

## 3. Phase 2：自己先送り（self-deferral）の扱い

### 3.1 事実確認

`_write_issue_impl` の DEFER 分岐（`2910-2954`）の検証は `defer_to_task_id` が `state["phases"]` 内に実在するか（`2930-2936`、`.`→`_` 正規化つき）のみ。**「今実行中のタスク自身」への先送りを一切拒否しない。** 実ログでは20件中6件が `task_2_1`（＝停滞していたタスク自身）へ先送りされていた。

自己先送りの帰結は完全に非対称である：

| 経路 | 種別 | 自己先送り時の挙動 |
|---|---|---|
| BL-136 強制解決文 | 是正 | **沈黙**（受け皿あり扱い） |
| BL-145 計画化 | 是正 | **沈黙**（受け皿あり扱い） |
| BL-125 遷移ゲート | 是正/安全 | **沈黙**（離脱を許可） |
| BL-158 機械的差し戻し | 是正 | **沈黙**（`_get_blocking_issues_for_transition` 経由） |
| BL-103 pin「要対応」 | 懲罰 | **毎ターン点灯** |
| BL-096/144 停滞判定 | 懲罰 | **カウント継続** |
| BL-096 facilitator 名指し | 懲罰 | **最優先で解消させろ、と点灯** |

**是正経路が全て沈黙し、懲罰経路だけが全て点灯する** ——これが「不死身かつ不可視だが懲罰的」な issue の正体であり、halt の直接原因。

### 3.2 結論：tool boundary で拒否する。ただし ACKNOWLEDGE（§5）と同時リリースする

**採用案：`_write_issue_impl` の DEFER 分岐で自己先送りを拒否する（`2936` の実在チェック直後に追加）。加えて、消費側（§2.1 の述語）でも「先送りされていない」と扱う（多重防御）。**

```python
        # [BL-194] 自己先送りの拒否。DEFER の意味は「今このタスクでは扱わない」であり、
        # 受け皿を実行中のタスク自身にすると何も先送りされない。にもかかわらず、
        # defer_to_task_id が立つという一点で BL-136/145/125/158 の是正経路が全て沈黙し、
        # BL-103 pin と BL-096/144 停滞判定という懲罰経路だけが点灯し続ける非対称状態
        # （＝解消不能かつ強制停止を招く issue）が生まれる。log/2026-08-08/1514 で
        # 20件中6件がこの状態にあり、12時間のランが halt した（BL-194）。
        # [REJECTED] 「受理するが消費側で先送り扱いしない」案も検討した。消費側の無効化
        # （_is_issue_effectively_deferred）は多重防御として実装するが、tool boundary で
        # 黙って受理すると User AI には成功として返り、次ターン以降なぜ督促が消えないのか
        # 説明がつかない（BL-151/BL-193 が確立した「失敗は理由つきで即座に返し、同ターン内で
        # 自己修復させる」原則に反する）。
        if canonical_defer_to_task_id == task_id:
            return {
                "success": False,
                "error": (
                    f"'{canonical_defer_to_task_id}' は現在あなたが実行中のタスク自身です。"
                    "自分自身への先送りはできません（何も先送りされないまま、システム上は"
                    "「対応予定あり」と扱われてしまうため）。次のいずれかを選んでください: "
                    "(1) この懸念が本当に別タスクの責務なら、その実在する task_id を"
                    "defer_to_task_id に指定して DEFER する。"
                    "(2) 現在タスクの acceptance_criteria の範囲で既に解消しているなら "
                    "RESOLVE する。"
                    "(3) 現在タスクの責務であり、今まさに対応中なら "
                    "write_issue(action_type=\"ACKNOWLEDGE\", topic=..., ack_reason=...) を"
                    "使ってください（一時的に督促を止めますが、タスク離脱時のゲートは"
                    "解除されません）。"
                ),
            }
```

### 3.3 「受理して無効化するだけ」案を単独採用しない理由（要件3の相互作用分析）

補正①のとおり、BL-158 のゲートは `_get_blocking_issues_for_transition`（Camp A）を単一の判断源としている。したがって：

- **拒否した場合**：その issue は `defer_to_task_id` が空のまま残る → BL-125/158 のブロック対象であり続ける → User AI は毎ターン、RESOLVE（嘘）か別タスクへの DEFER（誤配）を強いられる。
- **受理して消費側で無効化した場合**：`_is_issue_effectively_deferred` が False を返すが、`_get_blocking_issues_for_transition` は SQL レベルで `defer_to_task_id=''` を条件にしているため、**そのままでは BL-158 は沈黙し続ける**（＝事故が半分残る）。整合を取るために SQL 側も直せば、結果は拒否した場合と同一の圧力になる。

**つまり、どちらの案を選んでも「BL-158 の逃げ道が塞がる」という帰結は同じ**である。逃げ道を塞ぐこと自体は正しい（塞がなければ本 BL は事故を修正できない）が、塞いだ先に **正直な出口** が無ければ、User AI は嘘の RESOLVE か誤配の DEFER に追い込まれ、今回とは別経路で同じ halt に至る。実ログの User AI の `think` は既にこのジレンマを長文で自覚しており（「現タスクの acceptance_criteria は需要モデリングとサービス需要マッピングであり、全費目のコスト積算は task_5_1 の責務である」と正しく判断しながら、DEFER が all-or-nothing であるため部分的な先送りを表現できなかった）、**この不足は既に実証済みの設計欠陥**である。

したがって **§5 の ACKNOWLEDGE を Phase 2 と同一リリースに含めることを、本設計の必須条件とする**。片方だけの先行投入は行わない。

### 3.4 自己先送り issue は停滞にカウントすべきか（要件2への明示的な回答）

**カウントすべきである（＝ actionable 集合に含める）。**

理由は §1 の不変条件そのもの。自己先送り issue は §2 の修正後、BL-136 の強制解決文に復帰し、BL-103 pin では「要対応」側に残り、BL-125/158 のゲート対象にも戻る。**督促されるなら数えられる**のが正しい。ここだけ「督促するが数えない」にすると、今回とは鏡像の非対称（懲罰なしの永久滞留）を新たに作ることになる。

逆に、正当に他タスクへ DEFER された issue は督促されないので数えない。BL-167 の受け皿失効リバイバルはこの原則の系として自動的に保存される（受け皿が完了したら再び督促され、同時に再び数えられ始める）。`escalated_issue_first_seen_round`（`10610`）の掃除ロジック（`10622-10624`）は「actionable 一覧から消えた id は追跡辞書から削除する」という形で自然に働き、DEFER で一旦外れた issue が BL-167 で復活したときは **滞留カウントが 0 からやり直し** になる。これは意図した挙動である（受け皿が失効した瞬間から改めて3ラウンドの解決機会を与える。BL-144 が「3回はユーザーノードを通過させる＝実質的な解決機会」と定義した思想と一致する）。この点は既存コメント（`10620-10621`）に BL-194 の注記として追記する。

---

## 4. Phase 3-A：Reflection / Facilitator へのタスクスコープ注入

### 4.1 問題

`call_reflection`（`7902`）と `call_facilitator`（`8083`）は `_build_task_scope_context`（`6087`）を呼ばず、現在タスクの `acceptance_criteria` / `owns_variables` を一切受け取らない。両者が受け取るのは goal 全文、decision timeline、直近10件の chat、agreements、escalated issue の生ダンプ、そして BL-191 の `_build_task_focus_state_text`（`7992` / `8120`）だけである。

結果、「議論が漂流／停滞していないか」を判定するのが職掌の2ロールが、**「その懸念はそもそも現在タスクの守備範囲か」を問う手段を持たない**。実ログの Facilitator の `think` は「需要モデリングには7〜8台の車両が必要」と述べており、task_2_2 の問いを task_2_1 の義務として取り込んでいた。

### 4.2 採用案：新規の軽量ヘルパー `_build_current_task_scope_brief(state)`

`_build_task_scope_context` の再利用は **却下**する。理由：

- DB クエリを2本（`get_verified_facts_from_db`、`get_latest_whiteboard`）＋ `_get_deferred_notes_text` を実行し、**最大 50KB 超のホワイトボード全文**（BL-193 の実測）と R4 編集方針プロンプト（`write_agreement(edits=...)` の使い方、`read_whiteboard_excerpt` の推奨）を返す。両ロールとも `write_agreement` で Deliverable を書く権限を持たず、この指示は無意味。
- さらに Facilitator については **積極的に有害**：BL-170 は、具体的な数値 issue を読んだ Facilitator が自分の職掌（短い誘導メッセージ1本）を逸脱し、Expert の仕事（財務モデル再計算・Deliverable 再提出）を自分でやろうとして `python_repl`（未付与）の呼び出し計画を `think` で宣言し続け、`MAX_TOOL_ITER` を空費して無出力に終わった事故を記録している。そこへ成果物全文と編集手順を渡すのは同型事故の再現装置になる。

新規ヘルパー（配置：`_build_task_focus_state_text`（`4967`）の直後 — BL-191 の先例と同じ「state だけを読む常設ステータス表示」群にまとめる）：

```python
def _build_current_task_scope_brief(state: LineageState) -> str:
    """[BL-194] Reflection/Facilitator 向けの、現在タスクのスコープ最小要約。

    [REJECTED] _build_task_scope_context（BL-023/025）の再利用は却下した。あちらは
    DB クエリ2本と、実測 50KB 超になり得るホワイトボード全文＋R4 編集方針（write_agreement
    の edits の使い方）を返すが、Reflection/Facilitator は Deliverable を書く権限を持たず
    無意味であるうえ、Facilitator については BL-170（具体的 issue を読んだ Facilitator が
    Expert の仕事を自分でやろうとして MAX_TOOL_ITER を空費）の再現リスクを高める。
    ここでは state のみを読み、DB アクセスもホワイトボードも伴わない軽量版を返す。

    [BL-191] _build_task_focus_state_text と同じ「state 上の値はプロンプトに自動では
    現れないので明示描画する」パターン・同じ注入先（Reflection/Facilitator）に揃える。
    """
    task = _get_current_task(state)
    if not task:
        return ""
    criteria = task.get("acceptance_criteria", []) or []
    owns = task.get("owns_variables", []) or []
    lines = [
        f"task_id: {task.get('task_id','')}",
        f"目的: {task.get('description','')}",
        "acceptance_criteria（このタスクで満たすべき項目はこれが全てです）:",
        *[f"  - {c}" for c in criteria] or ["  (未定義)"],
        f"owns_variables（このタスクが確定させる変数はこれが全てです）: {owns or '(なし)'}",
    ]
    return "【🎯 BL-194: 現在のタスクのスコープ】\n" + "\n".join(lines) + "\n"
```

### 4.3 注入位置とガイダンス文（BL-042/BL-188 の「プロンプト誘導のみ」方針を踏襲）

**`call_reflection`**：`_build_task_focus_state_text(state)`（`7992`）と BL-191 の注意書き（`7993-7995`）の直後に追加。

```
{_build_current_task_scope_brief(state)}
[BL-194] 停滞(stagnant)判定の前に、必ず次を確認してください: 上で「未解決」として挙がっている
懸念のそれぞれが、上記の現在タスクの acceptance_criteria / owns_variables のどれかに対応して
いますか。どれにも対応しない懸念は、現在タスクで解決すべき問題ではありません（別タスクの責務、
または計画そのものへの指摘です）。その懸念が未解決であることだけを理由に stagnant と判定しないで
ください。代わりに note へ「この懸念は task_X_Y のスコープである」と明記してください——note は
Facilitator へそのまま引き継がれ（BL-061）、Facilitator が現在タスクで解決させようと誘導するのを
防ぐ唯一の経路です。
```

**`call_facilitator`**（通常モード分岐）：`escalated_issues_block` の直後、BL-170 のガードレール文（`8161-8165`）と隣接させる。

```
{_build_current_task_scope_brief(state) if state else ""}
[BL-194] 上の懸念のうち、現在タスクの acceptance_criteria / owns_variables のどれにも対応しない
ものについては、「現在のタスクで解決してください」という誘導を書かないでください。それは
現在の担当者に、担当外の解けない問題を押し付けることになります（実例: log/2026-08-08/1514 で、
需要セグメント定義のタスクに車両台数と待ち時間の実現可能性証明を求め続け、ホワイトボードが
Ver.41 まで空転しランが強制停止しました）。スコープ外だと判断した場合は、代わりに「その論点は
どのタスクの責務か」を整理させる方向の短いメッセージを書いてください。
```

**Essence Dialogue 分岐**（`8101-8123`）：`_build_task_focus_state_text(state)`（`8120`）の直後に `_build_current_task_scope_brief(state)` のみ追加（ガイダンス文は付けない。本質対話はスコープを意図的に超える場であり、抑制文は目的と衝突するため）。

**注意（テスト制約）**：`tests/test_bl093_think_tool_scratchpad.py` は `inspect.getsource(func)` に対してツール名リテラルや `"BL-093"` の存在を要求する（`cela_main.py:6162-6171` の CONSTRAINT コメント参照）。本変更はツール一覧文に触れないため影響しないが、`call_reflection` / `call_facilitator` のソース検査系テストが既存にないかを実装時に `grep` で確認すること。

---

## 5. Phase 3-B：第3の状態 `ACKNOWLEDGE`（採用。ただし status ではなく列で表現する）

### 5.1 判断：**採用する。ただし `issue_log.status` の語彙は増やさない。**

**status を増やす案は却下**する：

- D-079/D-080 の不変条件「`severity='major'` の行は常に `status='escalated'` を伴う」は、`_write_issue_impl` の CREATE（`2893-2894`）、`_bump_issue_occurrence`（`2816-2822`）、BL-125 ゲートの SQL（`10042`）、BL-096/136/145 の全 `_get_*_issues` ヘルパーが依存する中核不変条件。`major` の行を `escalated` 以外へ動かすと、`_get_escalated_issues` 系の全経路から **完全に不可視になり、BL-103 pin からも BL-125 ゲートからも消える** ——まさに要件5が警告する「BL-158 を無効化する万能の逃げ道」そのもの。
- `planned`（BL-145）は `_mark_issue_planned` という **非 LLM・内部専用**の遷移でのみ到達し、しかも `defer_to_task_id` に受け皿 task_id が同時に立つ（`3008-3010`）。LLM が自分の意思で到達できる status ではないため、先例として援用できない。

**採用する形：`status='escalated'` / `severity='major'` を保ったまま、TTL 付きの補助列を立てる。**

### 5.2 スキーマ（`_ensure_issue_log_defer_column`（`4483`）と同型のマイグレーション関数を新設し、`init_db` の `4480` 直後で呼ぶ）

```python
def _ensure_issue_log_acknowledge_columns(conn: sqlite3.Connection) -> None:
    """[BL-194] issue_log へ acknowledged_until_round / acknowledged_count /
    acknowledge_reason を追加する。status 語彙を増やさない（D-079/D-080 の
    severity='major' ⇒ status='escalated' 不変条件を壊さない）ための補助列。
    BL-136 の _ensure_issue_log_defer_column と同型の ALTER ベース冪等マイグレーション。"""
```

- `acknowledged_until_round INTEGER DEFAULT 0`
- `acknowledged_count INTEGER DEFAULT 0`
- `acknowledge_reason TEXT DEFAULT ''`

### 5.3 定数（**AGENTS.md §7 によりユーザーの事前承認が必要**。実装前に明示的に確認すること）

```python
_BL194_ACK_TTL_ROUNDS = 3     # ACKNOWLEDGE 1回あたりの猶予ラウンド数
_BL194_ACK_MAX_GRANTS = 2     # 同一 issue に対する ACKNOWLEDGE の累計上限
```

`3` を選ぶ根拠：BL-144 が「同じ escalated issue がユーザーノードを3回通過しても未解決なら滞留」と定義した閾値（`10618` の `>= 3`）と同一にすることで、「ACKNOWLEDGE は滞留カウントを **ちょうど1周期分** 止める」という明確な意味を与える。累計上限 `2` により、最悪でも 6 ラウンドで必ず滞留判定へ復帰し、不死身化しない。**この2つの数値は本設計の中で唯一「承認が必要な定数」であり、ユーザー承認が得られない場合は Phase 3-B 全体を保留し、§3.2 の自己先送り拒否も同時に保留する**（§3.3 の相互作用のため）。

**【2026-08-08 ユーザー承認済み】上記の推奨値どおり `_BL194_ACK_TTL_ROUNDS = 3` / `_BL194_ACK_MAX_GRANTS = 2` で承認された（本ファイル冒頭「ユーザー判断」参照）。**

### 5.4 ツール仕様

`WRITE_ISSUE_TOOL`（`722-777`）の `action_type` enum に `"ACKNOWLEDGE"` を追加し、`ack_reason`（ACKNOWLEDGE 時必須）を properties に追加。description に以下を追記：

> `[BL-194]` ACKNOWLEDGE は「この懸念は確かに現在のタスクの責務であり、今まさに対応中である」と表明するためのものです。RESOLVE（本当に解決した）でも DEFER（別のタスクの責務である）でもない、正直な第三の選択肢です。督促は一時的に止まりますが、**この懸念を未解決のまま次のタスクへ進むことはできません**（タスク離脱ゲートは解除されません）。猶予は有限で、同一 topic につき2回までです。

`_check_issue_permission`（`2388-2394`）：`"user": {"CREATE", "RESOLVE", "DEFER", "ACKNOWLEDGE"}`。他ロールは付与しない（BL-096 の「解決・先送りの判断は User AI＝発注者代理の職掌」という設計判断をそのまま踏襲）。

`_write_issue_impl` に ACKNOWLEDGE 分岐を追加（DEFER 分岐（`2954`）と RESOLVE（`2956`）の間）：

1. `existing` が無ければエラー。
2. `existing["status"] != "escalated"` ならエラー（「open/planned の懸念に ACKNOWLEDGE は不要です」）。
3. `existing["acknowledged_count"] >= _BL194_ACK_MAX_GRANTS` ならエラー：
   「この懸念は既に2回 ACKNOWLEDGE されています。3回目はできません。現在タスクで実際に解消して RESOLVE するか、別タスクの責務であることを認めて DEFER してください。このまま放置すると滞留として計画再構成の対象になります。」
4. 成功時：`acknowledged_until_round = state.get("round_count",0) + _BL194_ACK_TTL_ROUNDS`、`acknowledged_count += 1`、`acknowledge_reason = ack_reason`、`updated_at = now`。**`status` / `severity` / `defer_to_task_id` には一切触れない。**
5. 戻り値に残り猶予ラウンドと残り回数を含める（User AI が自分の残弾を把握できるように）。

**判定ヘルパー**（`_is_issue_effectively_deferred` の隣に配置）：

```python
def _is_issue_acknowledged_active(issue: dict, round_count: int) -> bool:
    """[BL-194] ACKNOWLEDGE の猶予が有効か。TTL を過ぎたら自動的に無効化される
    （新しい status を作らず列と round_count の比較だけで表現するため、
    「解除し忘れて不死身化する」経路が構造的に存在しない）。"""
    return int(issue.get("acknowledged_until_round") or 0) > round_count
```

**猶予の失効契機**（TTL 以外）：

- `RESOLVE`：行が `resolved` になるので自然消滅。
- `DEFER` 成功時：`acknowledged_until_round=0` へリセット（責務が別タスクへ移った以上、現在タスクでの「対応中」表明は無効）。DEFER の `UPDATE`（`2938-2941`）に列を追加。
- `_bump_issue_occurrence`（`2834-2838`）：**同じ topic が再度検出されたら `acknowledged_until_round=0` へリセット**。「対応中」と宣言した直後に同じ懸念が再検出されるのは、対応が実際には進んでいない証拠であるため。この1行が、ACKNOWLEDGE を「唱えるだけで無限に延命できる呪文」にしないための最重要ガードである。

### 5.5 各消費者の扱い（要件5が要求する対応表）

| 消費者 | BL | ACK 有効時の扱い | 理由 |
|---|---|---|---|
| `_get_forced_escalated_issues_text` | BL-136/167 | **抑制**（一覧から除く） | 「今回必ず RESOLVE か DEFER せよ」の督促を止めるのが ACK の目的そのもの |
| BL-158 機械的差し戻し（`9913`） | BL-158 | **抑制** | 同上。`_get_blocking_issues_for_transition(..., exclude_acknowledged=True)` としてこの呼び出し元でのみ有効化 |
| `_get_blocking_issues_for_transition` 本体（BL-125 遷移ゲート、`10041-10045`） | BL-125 | **抑制しない**（既定 `exclude_acknowledged=False`） | **ACK が万能の逃げ道になるのを防ぐ設計の要**。「今このタスクで対応中」と表明した以上、その懸念を未解決のままタスクを離脱することは論理的に許されない。督促は止まるが出口は閉じたまま |
| reflection 停滞判定（`10609`） | BL-096/144 | **抑制**（actionable から除く） | 対応中の懸念で停滞と断罪しない。TTL＋累計上限により最大6ラウンドで必ず復帰 |
| `_formalizable_stale`（BL-145 計画化） | BL-145 | 上流が抑制済みなので自動的に抑制 | 対応中のものを勝手にタスク化しない |
| `call_reflection` の一覧（`7942`） | BL-096 | **表示する**（注記付き：`【現在タスクで対応中（残りNラウンド）。completed 判定では未解決として扱うこと】`） | completed 抑止の役割を壊さない（§2.3 と同じ理由） |
| BL-103 pin（Expert / Detector / User AI） | BL-103/123 | **第3の見出しで表示**：`【🛠 現在のタスクで対応中の懸念（acknowledged、残りNラウンド）】` | 可視性は保ち、トーンだけ非懲罰にする。Expert には「これは現在タスクの責務であり、今回の成果物で対応が期待されている」という **前向きな** 指示になる（DEFER 済みの「対応不要」とは意味が逆であることを明示的に区別する） |
| facilitator 名指し（`10761`） | BL-096 | **抑制**（actionable から除く） | 「最優先で解消させろ」の再点火を止める |

実装上は `_get_actionable_escalated_issues` に `round_count: int | None = None` を追加し、`round_count is not None` のときのみ ACK 抑制を適用する（BL-125 のように round を持たない／持たせたくない呼び出し元との混線を防ぐ）。

---

## 6. Phase 4：DEFER のスコープ整合性チェック（要件6）

### 6.1 結論：**機械的ゲートは追加しない。プロンプト誘導＋「エコーバック」に留める。**

`task1_3_budget_overrun_composite_service`（予算超過）が `task_2_1`（需要セグメント定義）へ DEFER され、`_append_deferred_note_to_plan`（`2944-2948`）経由で task_2_1 の plan_draft に申し送りノートとして書き込まれた結果、スコープ外の予算・車両内容が task_2_1 に「正式に」貼り付いた——これは事実であり、対処は必要である。ただし対処手段の選択は慎重に行う。

**却下案①：LLM ジャッジによる整合性判定**
DEFER はドライラン中の User AI ターンで頻繁に呼ばれるホットパスであり、1回ごとに追加の LLM 呼び出しを挟むとレイテンシとコストが跳ね、かつ判定が非決定的になる。さらに致命的なのは、**誤判定が User AI の唯一の triage 手段をブロックする**点：本 BL は §3 で自己先送りという逃げ道を塞いでいるため、DEFER が偽陰性で拒否されると RESOLVE（嘘）以外の出口が消え、新種のデッドロックを生む。BL-042/BL-188 が確立した「プロンプト誘導のみ、機械的ゲートは追加しない」方針とも正面から衝突する。

**却下案②：キーワード重なりによる機械判定**
`acceptance_criteria` は日本語自由文であり、形態素解析器も導入していない（依存追加は AGENTS.md §5-1 の承認事項）。BL-074/BL-081/BL-193 が示したとおり、この種の「緩い文字列一致」は本プロジェクトで繰り返し誤判定の温床になってきた。恣意的な拒否は却下案①と同じデッドロックを招く。

### 6.2 採用案：DEFER 成功時に受け皿タスクのスコープを機械的にエコーバックする（非ブロッキング）

DEFER の戻り値（`2951-2954`）を拡張し、`state["phases"]` から引ける受け皿タスクの `acceptance_criteria` / `owns_variables` を **そのまま返す**。DB アクセスも LLM 呼び出しもゼロ（`task_id_to_task` は既に `2922-2928` で構築済み）。

```python
        _target_task = task_id_to_task.get(canonical_defer_to_task_id, {})
        return {
            "success": True,
            "message": f"'{canonical_defer_to_task_id}'への先送りとして記録しました",
            # [BL-194] スコープ整合性の機械的判定（LLM ジャッジ・キーワード一致）は却下した
            # （前者はホットパスでのコストと非決定性、後者は日本語自由文での誤判定。いずれも
            # 誤って拒否すると、自己先送りを塞いだ本 BL の下では User AI の triage 手段が
            # 消え新種のデッドロックになる）。代わりに受け皿タスクのスコープをそのまま
            # 返し、ミスマッチの判断はモデル自身に委ねる（BL-042/BL-188 の「プロンプト誘導
            # のみ」方針、および BL-151/BL-193 の「同ターン内で自己修復させる」原則に沿う）。
            "target_task_scope": {
                "task_id": canonical_defer_to_task_id,
                "description": _target_task.get("description", ""),
                "acceptance_criteria": _target_task.get("acceptance_criteria", []),
                "owns_variables": _target_task.get("owns_variables", []),
            },
            "scope_check_hint": (
                "上記が先送り先タスクのスコープです。この懸念がこれらのどれにも対応しない場合、"
                "そのタスクの担当者も同じように解けない問題を抱えることになります。"
                "より適切な task_id があれば、同じ topic で再度 DEFER し直してください"
                "（最新の DEFER が有効になります）。"
            ),
        }
```

併せて `WRITE_ISSUE_TOOL` の description（`735-738` の BL-136 段落）へ1文追記：

> `[BL-194]` DEFER 先は「その懸念に実際に対応できるタスク」を選んでください。受け皿タスクの acceptance_criteria / owns_variables が、この懸念の内容と対応している必要があります（対応していない先へ送ると、そのタスクの担当者に解けない問題を押し付けることになります）。判断に迷う場合は `read_project_plan` で各タスクのスコープを確認してから指定してください。

---

## 7. 実装順序（依存関係つき）

| # | 内容 | 依存 | 単独リリース可否 |
|---|---|---|---|
| **S1** | `_is_issue_effectively_deferred` / `_get_actionable_escalated_issues` 新設（`3046` 直後） | なし | — |
| **S2** | Camp A 3箇所の置換／据え置き決定（A-1・A-3 置換、A-2 据え置き＋コメント明記） | S1 | ✅ 挙動不変（自己先送りの復帰を除く） |
| **S3** | Camp B の置換：B-1（停滞判定）、B-3（facilitator）、B-4（reflection 注記）、B-2 は据え置き | S1 | ✅ **これ単体で本事故（halt）は再発しない** |
| **S4** | `_build_deferred_issue_pin_text` 新設＋`_build_escalation_pin_text` の actionable 化、3注入サイト（`6825` / `7278` / `8911`）更新 | S1 | ✅ |
| **S5** | `_build_current_task_scope_brief` 新設＋Reflection/Facilitator 3箇所へ注入（`7992` / `8120` / 通常モード） | なし | ✅ 独立 |
| **S6** | DEFER のスコープ・エコーバック（`2951`）＋ツール description 追記 | なし | ✅ 独立 |
| **S7** | ACKNOWLEDGE：スキーマ移行・定数（**要ユーザー承認**）・ツール拡張・`_write_issue_impl` 分岐・`_is_issue_acknowledged_active`・各消費者配線・`_bump_issue_occurrence` リセット・`_build_acknowledged_issue_pin_text` | S1 | ❌ |
| **S8** | 自己先送りの tool boundary 拒否（`2936` 直後） | **S7 必須** | ❌ （§3.3） |

**推奨リリース単位**：`S1–S6` を第1弾（事故の再発防止として完結し、既存挙動への破壊的変更を含まない）、`S7+S8` を第2弾（定数承認後、必ずセットで）。`S8` を `S7` より先に入れることは **禁止**する。

**【2026-08-08 私（Claude）による訂正】この「推奨リリース単位」は誤りである。詳細は本ファイル冒頭
【第0部】「Plan エージェント設計 §7 への補正」を参照。要旨：S1–S6 だけでは実ログ 20 件中 6 件
（自己先送り分）が actionable のまま残り、`stagnant` → `halt` の経路が再発し得る。実装時は
本節の表・依存関係はそのまま参照してよいが、「S1–S6 を第1弾として単独リリースする」という
判断は採用しないこと。**

---

## 8. 既存 BL との相互作用（要件どおり全件）

- **BL-096（issue_log / `_get_escalated_issues` / 停滞の機械的上書き）**：`_get_escalated_issues` 自体は削除も変更もしない。「生の全件が要る用途」（`escalation_active`、reflection の completed 抑止一覧）は残り続けるため。BL-096 の「モデルのツール呼び出し判断に依存せず Python 側で必ず届ける」という思想（`3047-3050`）は保たれる——変わるのは *何を* 届けるかの述語だけ。
- **BL-103（escalation pin）**：pin の存在意義（recency 窓の外でも懸念を保持する）は維持。「要対応」見出しの対象を actionable に絞り、DEFER 済みは新見出しへ分離、ACK 済みは第3見出しへ分離。**文脈は一切失われない**（3見出しの和集合＝従来の pin 集合）。
- **BL-123（Detector Pass 1 への pin 注入）**：注入自体は維持。Pass 2（算術検算）が対象外である設計も維持。追加するのは「担当タスクが別に確定している懸念を理由に major と判定しない」という1文で、BL-123 の目的（他ロールが折り込み済みの懸念を知る）と矛盾せず、その逆方向の誤用のみを塞ぐ。
- **BL-125（遷移ゲート）**：SQL・セマンティクス完全据え置き。BL-167 のリバイバルも ACK 抑制も持ち込まない。据え置きの理由をコード上のコメントとして明文化する（「離脱ゲートは救済経路ではなく安全装置であり、督促集合とは別の関心事である」）。これは §1 の不変条件の **例外** であり、例外である旨を明示的に記録する。
- **BL-136（DEFER の導入・強制解決文）**：DEFER の中核設計（status を変えず `defer_to_task_id` だけ立てる）は維持。変わるのは「`defer_to_task_id` が立っている＝受け皿がある」という **素朴な読み替えを述語へ格上げ** した点のみ。BL-136 の「今このタスク・フェーズで対応すべきでないと判断した場合」という DEFER の定義文（`5121`、ツール description `736-737`）は、ACKNOWLEDGE の追加によって初めて **反対側の選択肢を持つ** ことになり、定義が実効的になる。
- **BL-144（滞留3ラウンド閾値）**：閾値 `3`（`10618`）は変更しない（AGENTS.md §7 の対象定数でもある）。変えるのは母集合のみ。`_BL194_ACK_TTL_ROUNDS = 3` を同じ値に揃えることで両者の意味が接続される。
- **BL-145（issue 駆動の計画化）**：`_formalizable_stale` のフィルタは上流へ移動（重複除去）。副作用として **自己先送り issue が計画化の対象に入る**——これは望ましい：「現在タスクの責務のはずだが acceptance_criteria に無い」懸念こそ、task_planner が計画へ正しく配置し直すべき対象である。ただし今回のログのように一度に6件が `plan_revision_reason` へ流れ込むと大規模な再計画を誘発するリスクがある（§9-R4）。
- **BL-158（機械的差し戻し）**：判断源が `_get_blocking_issues_for_transition` である構造は維持。ACK 用の `exclude_acknowledged=True` をこの呼び出し元にのみ付与する。補正①のとおり本ゲートは既に Camp A であり、本 BL は BL-158 を **弱めない**（自己先送りを塞ぐことでむしろ強まる）。強まった分の正直な出口として ACKNOWLEDGE を用意する、という関係。
- **BL-167（受け皿失効リバイバル）**：`_is_issue_effectively_deferred` の中に `_is_task_completed` 判定として **そのまま保存**。要件2が求める「過剰修正への歯止め」はこの1行が担う。加えて、リバイバル時に滞留カウントが 0 からやり直しになる挙動を BL-194 の注記として明文化。
- **BL-191（`_build_task_focus_state_text`）**：注入先・注入形式の先例として全面的に踏襲。`_build_current_task_scope_brief` は同じ「state のみを読む常設ステータス表示」群に配置し、同じ2ロールへ同じ位置で注入する。BL-191 が `redirect_backward` で `current_task_id` を過去タスクへ動かすため、`_build_current_task_scope_brief` と自己先送り判定は自動的に「巻き戻し先タスク」を基準に動く——これは正しい（巻き戻し中は、その過去タスクが「今のタスク」である）。
- **BL-192**：Stage4 のプロンプト文言にのみ触れる BL であり、本 BL の変更点（`generate_user_utterance` の `timeline_str` 組み立て部と `_get_forced_escalated_issues_text` の引数）とは行が重ならない。競合なし。
- **D-079/D-080（severity↔status 不変条件）**：本 BL は **`status` にも `severity` にも一切書き込まない**。ACKNOWLEDGE も DEFER 同様 status を変えず、補助列のみを更新する。この不変条件を守ることが、`status='acknowledged'` 案を却下した唯一かつ十分な理由である。
- **D-127（BL-157 の `detector_auto` 例外）**：`_bump_issue_occurrence` に ACK リセットの1行を足すが、`detector_auto` の昇格抑制ロジック（`2816`）には触れない。なお `detector_auto` 起票行は昇格しないため `escalated` にならず、本 BL の actionable 判定には元々乗らない。

---

## 9. リスクとガードレール

**R1｜Reflection が `completed` を宣言してしまう過剰修正**
DEFER/ACK 済み issue を reflection の一覧から落とすと、未解決のまま完了宣言できる。
→ **対処**：`call_reflection` の一覧は全件維持し、行注記のみ（§2.3 / §5.5）。機械的な停滞上書きだけを actionable に絞る。この「一覧は全件・機械判定は絞込」という非対称は意図的であり、コメントに明記する。

**R2｜BL-125 に BL-167 のリバイバルを持ち込んだ場合の新規デッドロック**
完了済みタスクへ DEFER された issue が離脱ゲートに復活すると、現在タスクの担当者が解けない issue でタスクを出られなくなる。
→ **対処**：A-2 を明示的に据え置き、理由をコードコメント化。統一の誘惑に対する明文の禁止事項とする。

**R3｜ACKNOWLEDGE が万能の逃げ道になる**
→ **対処（4重）**：(a) BL-125 離脱ゲートは解除しない、(b) TTL 3ラウンド、(c) 累計2回上限、(d) 同 topic の再検出（`_bump_issue_occurrence`）で即時失効。加えて Camp B の pin には残り続けるため、可視性も失われない。

**R4｜自己先送り issue が一斉に BL-145 の計画化へ流れ込む**
実ログのケースでは6件が同時に `plan_revision_reason` へ入り、大規模な計画再構成 → BL-190/BL-191 の `current_task_id` 不整合経路を刺激し得る。
→ **対処**：本 BL では件数上限を **追加しない**（新機構を増やさない方針）。ただし `plan_revision_reason` 生成時のログに件数を出す既存 print（`10665-10668`）を確認し、ドライランで件数を観測する。5件超が常態化するなら別 BL として上限設計を起票する。

**R5｜自己先送り拒否により User AI が RESOLVE を濫用する（嘘の解決）**
ACKNOWLEDGE があってもモデルが RESOLVE を選ぶ可能性は残る。
→ **対処**：拒否メッセージ（§3.2）で3択を明示し、ACKNOWLEDGE を「正直な選択肢」として言語化する。加えて RESOLVE 後に同じ topic が再検出されれば `_bump_issue_occurrence` により再度 escalated へ戻る既存機構（BL-096）が働くため、嘘の RESOLVE は永続しない。

**R6｜"never halt" への傾斜**
本 BL は停滞判定の母集合を縮小する方向の変更が多い。
→ **対処**：halt へ至る経路は複数残る：(a) 未 triage の escalated が3ラウンド滞留、(b) BL-167 の受け皿失効リバイバル、(c) 自己先送りの actionable 復帰（本 BL で **新たに増える** 経路）、(d) ACK の TTL/回数切れ、(e) reflection 自身の LLM 判定（でっちあげ監査・迎合監査は無変更）、(f) `max_turns`。むしろ (c) により、これまで停滞として数えられていなかった一部の issue が正しく数えられるようになる。

**R7｜`current_task_id` が空のとき**
初回ターンや BL-190 のクリア経路では `current_task_id` が空になり得る。`_is_issue_effectively_deferred` は `current_task_id` が空なら自己先送り判定をスキップする（＝ BL-167 判定のみ）ため、従来挙動へ安全に縮退する。`_build_current_task_scope_brief` は `_get_current_task` が空 dict を返したら空文字を返す（BL-191 のヘルパーと同じフェイルソフト）。

**R8｜チェックポイント再開との整合**
`escalated_issue_first_seen_round` は `state` に保持され checkpoint に載る。母集合が変わることで再開直後に一部 id が辞書から掃除されるが、掃除ロジック（`10622-10624`）は id 集合の差分で動くため冪等であり、再開時の異常は生じない。`acknowledged_until_round` は DB 側に持つため、state 復元とは独立に正しく失効する（これも「state ではなく DB 列」を選んだ理由の一つ）。

---

## 10. テスト計画

### 10.1 新規ファイル：`tests/test_bl194_deferred_issue_consistency.py`

ハーネスは `tests/test_bl191_task_focus_scheduling.py` / `tests/test_bl167_defer_to_task_id_completed_target.py` に完全準拠：モジュール docstring（BL 番号・背景・「実 LLM API 呼び出しは伴わない」の明記）、`sys.path.insert`、`import cela_main`、`tmp_path` ベースの `db_conn` フィクスチャ（`get_db_connection` → `init_db` → `_DB_CONN`/`_CURRENT_RUN_ID` 差し込み → `finally` で復旧）、`_insert_deliverable` ヘルパー（BL-167 のものを踏襲、`_is_task_completed` を成立させるため）。

**A. 述語 `_is_issue_effectively_deferred`（6件）**
1. `defer_to_task_id` 空 → False
2. 別タスクへ先送り・受け皿未完了 → True
3. 別タスクへ先送り・受け皿完了済み（Approved Deliverable を投入）→ False（BL-167 保存）
4. `current_task_id` と一致（自己先送り）→ False
5. `current_task_id` が空文字のとき、自己先送りでも BL-167 判定のみに縮退 → True
6. `Approved_with_Conditions` / `Implicitly_Accepted` でも受け皿完了扱い

**B. `_get_actionable_escalated_issues`（3件）**
7. 混在3件（未先送り／他タスク先送り／自己先送り）→ 未先送りと自己先送りの2件が返る
8. `status='open'`/`'planned'`/`'resolved'` は返らない
9. 全件が正当に先送り済み → 空リスト（**本事故の直接回帰テスト**）

**C. 停滞判定（`reflection_node` の該当ブロック相当、4件）**
10. 全件先送り済みで4ラウンド経過 → `discussion_status` が `stagnant` に上書きされない（**halt 再発防止の中核**）
11. 未先送り1件が3ラウンド滞留 → `stagnant` へ上書きされる（BL-144 保存）
12. 受け皿完了後にリバイバルし、その後3ラウンド滞留 → `stagnant`（BL-167 保存）
13. 自己先送り1件が3ラウンド滞留 → `stagnant`（§3.4 の明示的な設計判断の固定）
※ `reflection_node` 全体を呼ぶと `call_reflection`（LLM）に到達するため、`call_reflection` を `monkeypatch` で固定 dict を返すスタブへ差し替える（既存スイートの手法を実装時に確認して合わせる。困難な場合は該当ブロックを純関数ヘルパーへ切り出して直接テストする — 切り出しは §7 の S3 に含める）。

**D. pin のトーン分離（4件）**
14. `_build_escalation_pin_text` が DEFER 済みを含まない
15. `_build_deferred_issue_pin_text` が DEFER 済みのみを含み、文字列に「対応不要」相当の非強制文言と `defer_to_task_id` を含む
16. 両者の和集合が従来の `_get_escalated_issues` 集合と一致（**文脈が失われていないことの保証**）
17. `inspect.getsource(cela_main.call_detector)` に BL-194 の Detector 向けガード文が含まれる（BL-123 の配線テストと同型）

**E. スコープ注入（4件）**
18. `_build_current_task_scope_brief` が `acceptance_criteria` と `owns_variables` を含む
19. タスク未確定時は空文字
20. `inspect.getsource(cela_main.call_reflection)` に `_build_current_task_scope_brief` と "BL-194" が含まれる
21. `inspect.getsource(cela_main.call_facilitator)` について同上（通常モード・Essence モード双方）
22. `_build_current_task_scope_brief` が DB 接続を引数に取らない＝ホワイトボード全文を含まないことの確認（`whiteboard_drafts` に巨大文字列を入れても戻り値長が一定以下）

**F. DEFER のスコープ・エコーバック（2件）**
23. DEFER 成功時の戻り値に `target_task_scope.acceptance_criteria` / `owns_variables` が含まれる
24. 受け皿タスクが `phases` にあるが `acceptance_criteria` 未定義でもクラッシュしない

### 10.2 新規ファイル：`tests/test_bl194_issue_acknowledge.py`（S7/S8 と同時）

25. マイグレーション冪等性（`init_db` 2回で `PRAGMA table_info` に3列、重複エラーなし）
26. 自己先送りが `success=False` で拒否され、エラー文に `ACKNOWLEDGE` の語を含む
27. 拒否時に DB の `defer_to_task_id` が **書き換わっていない**
28. 拒否時に `_append_deferred_note_to_plan` が呼ばれていない（plan_drafts が汚染されない）
29. ACKNOWLEDGE 成功で `status='escalated'` / `severity='major'` が **不変**（D-079/D-080 の回帰テスト）
30. ACKNOWLEDGE 有効中は `_get_forced_escalated_issues_text` に出ない
31. ACKNOWLEDGE 有効中でも `_get_blocking_issues_for_transition`（既定引数）は返す（＝離脱ゲートは閉じたまま。**逃げ道化の防止テスト**）
32. `exclude_acknowledged=True` では返らない（BL-158 の抑制）
33. TTL 経過後（`round_count` を進める）に督促・停滞判定へ復帰
34. 3回目の ACKNOWLEDGE が拒否され、エラー文が RESOLVE/DEFER を案内
35. ACK 中に同 topic を CREATE（再発）すると `acknowledged_until_round` が 0 にリセットされる
36. DEFER 成功時に `acknowledged_until_round` が 0 にリセットされる
37. `open` 状態の issue への ACKNOWLEDGE が拒否される
38. `user` 以外のロール（`detector` / `detector_auto` / `decision_extractor_auto` / `revise_goal_auto`）の ACKNOWLEDGE が権限拒否される

### 10.3 グリーン維持が必須の既存スイート

`tests/test_bl096_issue_log.py`、`test_bl103_hydrate_context_improvements.py`、`test_bl123_detector_escalation_pin.py`、`test_bl136_issue_visibility_and_transition_gate.py`、`test_bl144_escalated_issue_staleness_threshold.py`、`test_bl145_issue_driven_plan_formalization.py`、`test_bl154_decision_extractor_issue_log_bridge.py`、`test_bl157_detector_auto_occurrence_exemption.py`、`test_bl158_detector_rejects_premature_advancement.py`、`test_bl167_defer_to_task_id_completed_target.py`、`test_bl186_*`、`test_bl191_task_focus_scheduling.py`、`test_bl192_stage4_directive_quality.py`。

**特に注意すべき退行点**：
- `test_bl136_*` / `test_bl158_*` は「DEFER すればゲートが沈黙する」ことを検証している可能性が高い。そのフィクスチャで `defer_to_task_id` が **偶然 `current_task_id` と同一** に設定されていると、S8 導入で赤くなる。その場合はフィクスチャを別 task_id へ修正し、修正理由を BL-194 のコメントとして残す（テスト側の期待値を弱めるのではなく、フィクスチャが表現していた状況が実は自己先送りだった、と読み替える）。
- `test_bl144_*` は無フィルタの母集合を前提にしている可能性がある。actionable への切替で期待値の更新が必要になり得る。

**リリース判定基準**：`python -m py_compile cela_main.py` 合格、オフライン全スイート（現行 841 件＋新規約 38 件）Pass、`scripts/check_docs_consistency.py` 合格。

---

## 11. ドキュメント更新（AGENTS.md §4 に基づく必須作業）

- `docs/design/back_log/BL-194/BL194_basic_design.md`：本文書を **要約せず逐語** 保存。
- `docs/design/back_log/issue_backlog.md`：一覧表に `BL-194 | 高 | cela_main.py（...） | ... | P1` を追加し、詳細セクション `### BL-194: ...` を追記。関連 BL（096/103/123/125/136/144/145/158/167/191）へ相互リンク。
- `docs/design/decision_log.md`：以下の D エントリを新規起票（`Reason for the decision` 必須）。
  - 「督促集合と滞留集合を同一述語で決定する（BL-194 不変条件）。ただし BL-125 離脱ゲートは安全装置として明示的に例外とする」
  - 「自己先送りを tool boundary で拒否し、その代償として ACKNOWLEDGE を同時導入する（片方のみのリリースを禁止する）」
  - 「第3の issue 状態を `status` ではなく TTL 付き補助列で表現する（D-079/D-080 の不変条件保護）」
  - 「DEFER のスコープ整合性は機械判定せず、受け皿スコープのエコーバックに留める」
- `docs/design/decision_lineage.md`：本セッションの対話（ログ `1514` のレビュー、補正①〜③の発見、要件3と要件5の相互依存の特定）を1エントリとして記録。AI 発の提案（不変条件の定式化、ACKNOWLEDGE を列で表現する案、BL-125 を例外とする判断）は AI 発として明示的に帰属させる。
- `docs/design/traceability.md`：新規テスト2ファイルを T-* として登録。
- **`_BL194_ACK_TTL_ROUNDS` / `_BL194_ACK_MAX_GRANTS` は AGENTS.md §7 の対象定数**。実装着手前にユーザーへ値と根拠を提示し、書面での承認を得ること。承認前に S7/S8 を実装してはならない。

**【2026-08-08 承認済み】上記の定数承認は完了した（`_BL194_ACK_TTL_ROUNDS=3` / `_BL194_ACK_MAX_GRANTS=2`）。**

---

### Critical Files for Implementation
- C:\ai_work\CELA\cela_main.py
- C:\ai_work\CELA\docs\design\back_log\issue_backlog.md
- C:\ai_work\CELA\docs\design\decision_log.md
- C:\ai_work\CELA\tests\test_bl167_defer_to_task_id_completed_target.py
- C:\ai_work\CELA\tests\test_bl191_task_focus_scheduling.py