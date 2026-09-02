# BL-329: 計画再構成が承認済みDeliverableを除去しないよう、生成時点で検証・自己修正させる

## Context

1633ログ（run_id=1787890406-1e73a89d）で`read_deliverable_file`の「該当するDeliverable
が見つかりませんでした」が24回連発しているとユーザーから報告があった。実DB調査の結果、
BL-313（先送り事項5件以上集中時のサブタスク分割トリガー）が同一ミリ秒でtask_5_1/task_5_2/
task_5_5/task_3_2/task_4_5の5タスクを一括SUPERSEDEし「ラン途中の計画再構成により廃止され
ました」と記録していたが、このうちtask_5_2（53件のagreements、最終Deliverable=Approved・
Ver.2・承認条件①②③消化完了）とtask_5_5（24件、最終Deliverable=Approved）は、分割前に
**既に承認済みだった完成成果物**を持っていた。分割後の`task_5_2_1`（タイトルが分割前の
task_5_2と同じ「待ち時間解析モデルの構築とSLA検証」）は`read_deliverable_file`で
`not_found`——承認済みの内容は旧task_id配下に取り残されたまま、新task_idへのリンクも
移行も一切行われていない。

ユーザーはこの状況を「タスクプランナーが再プランした際に、成果物と紐づけが切れた？」と
正確に言い当てた。ライブランは停止済み。

### 設計の経緯（重要）

当初案（Cline独立レビュー2回済み）は、`task_planner_node`が計画差分から除去対象task_idを
機械的に検出した**後**、承認済みDeliverableを持つものだけ計画へ黙って復元する、という
事後の機械的パッチだった。ユーザーはこれに対し「根本的には今は巨大なJSONを一括で書かせて
いるのが問題では。task_plannerにツールを用意して一つ一つ登録させ、再プラン時は保護対象
task_idを事前提示し、間違って変更したらDB登録時点で拒否してその場で考えさせられないか」と
より根本的な改善を提案した。さらに「depends_on等の紐づけチェックは、`check_docs_
consistency.py`のような仕組みを使えないか」とも問うた。

調査の結果、task_plannerの出力形式を「一括JSON」から「1タスクずつのツール呼び出し」へ
作り直す大改修をせずとも、既存の`_query_and_parse_with_retry`（cela_main.py:7252、
BL-213 F3で導入済み）が**まさにこの用途向けの`validator`フック**を既に持っていることが
判明した：「JSONとしては読めたが内容が意味的に不正」な場合、理由を差し戻しプロンプトへ
追記して同一呼び出し内でLLMに自己修正させる仕組みで、既存の使用例
（`_validate_extracted_events`、cela_main.py:14074）と全く同じパターンをtask_planner
向けに書くだけで、ユーザー提案の「その場で気づいて直す」という核心的な利点を、大改修
なしで実現できる。ユーザーはこの軽量案を承認した（「分かりました。設計してみて、cline
のレビューも仰ぎましょう」）。

## 根本原因（コード調査済み）

`task_planner_node`（cela_main.py:16404）の計画再構成分岐（`revision_reason`セット時、
16462行以降）は、`call_task_planner`が返した新`phases`と旧`phases`の差分
（`old_task_ids - new_task_ids`）を取り、消えたtask_idを無条件・無検証で「廃止」として
SUPERSEDEする：

```python
old_task_ids = {t["task_id"] for p in old_phases for t in p.get("tasks", [])}
new_task_ids = {t["task_id"] for p in phases for t in p.get("tasks", [])}
removed_task_ids = old_task_ids - new_task_ids
for tid in sorted(removed_task_ids):
    # ... write_agreement(SUPERSEDE, "タスク{tid}はラン途中の計画再構成により廃止されました。")
```

`call_task_planner`（cela_main.py:11930）は`_query_and_parse_with_retry`で新`phases`を
生成するが、**`validator`引数を渡していない**——つまりLLMの出力に対する意味的な検証が
一切なく、「承認済みDeliverableを持つtask_idを消してよいか」「depends_onが実在する
task_idを指しているか」のいずれも、プロンプト文言（「分割が最善とは限りません」等）に
よる期待に過ぎず、コード側で強制されていない（AGENTS.md §15.3違反）。実際、task_plannerは
BL-313の5対象中2件（task_5_2/task_5_5）で承認済み成果物を丸ごと廃止する計画を提案し、
無検証で実行された。

このループ・この呼び出しはBL-313専用ではなく、BL-126 Stage Cで導入された汎用の計画再構成
インフラ（BL-145の停滞トリガー・BL-315の申し送り放置トリガー等が共通で通る）であり、
`call_task_planner`は初回計画・再構成どちらでも呼ばれるため、本修正は今後発生しうる
同種のインシデントをまとめて予防する。

## 設計

### 二段構え: 生成時点でのvalidator検証（一次防御）＋ 事後の機械的復元（保険）

**一次防御（新設）**: `call_task_planner`が`_query_and_parse_with_retry`へ`validator`を
渡すようにする。2つの独立した検証を1つの`validator`関数に合成する：

1. **depends_on整合性検証**（初回計画・再構成の両方で常時有効。ユーザー提案の
   `check_docs_consistency.py`的な「宣言と実体の双方向対応チェック」と同じ発想——
   BL番号の優先表↔詳細セクション対応チェックの代わりに、task_idのdepends_on↔実在tasksの
   対応をチェックする）:
   **[Cline独立レビューF3・F4で発覚・反映済み]** 同じ1回の走査で、(a) 同一task_idの重複
   登録（`new_task_ids`をsetにすると黙って握りつぶされる）と、(b) task_id自体が空/欠落
   しているタスク（cela_main.py:16466-16467の`t["task_id"]`直接参照がKeyErrorでクラッシュ
   する原因になる、§13.1: 身元フィールドの存在検証）も検出する。単一の検証機構に集約する
   （AGENTS.md §15.1）。
   ```python
   def _validate_task_plan_depends_on_integrity(phases) -> tuple[bool, str]:
       """[BL-329] 各タスクのtask_idが非空・重複無しであること、depends_onが同じphases内に
       実在するtask_idを指していることを検証する。_query_and_parse_with_retryのvalidator
       フック（BL-213 F3）として使う。
       """
       if not isinstance(phases, list):
           return True, ""
       all_tasks = [
           t for p in phases if isinstance(p, dict)
           for t in p.get("tasks", []) if isinstance(t, dict)
       ]
       problems: list[str] = []
       seen_ids: set[str] = set()
       for t in all_tasks:
           tid = t.get("task_id")
           if not tid:
               problems.append(f"- title={t.get('title')!r}のタスクにtask_idがありません（必須）。")
           elif tid in seen_ids:
               problems.append(f"- task_id={tid!r}が複数のタスクで重複しています。")
           else:
               seen_ids.add(tid)
       all_task_ids = {t.get("task_id") for t in all_tasks}
       problems += [
           f"- task_id={t.get('task_id')!r}のdepends_onに、存在しないtask_id {dep!r} が"
           f"指定されています。"
           for t in all_tasks
           for dep in (t.get("depends_on") or [])
           if dep not in all_task_ids
       ]
       if not problems:
           return True, ""
       return False, (
           "以下の不整合を修正し、JSON全体を出力し直してください:\n" + "\n".join(problems)
       )
   ```

2. **承認済みtask_id保護検証**（`revision_reason`が非空＝再構成時のみ有効）:
   ```python
   def _build_protected_task_id_validator(protected_task_ids: set[str]):
       """[BL-329] 再プラン時、既に完了相当（RESOLVING_DELIVERABLE_STATUSES）のDeliverable
       を持つtask_idが新しい計画から除去されていないかを検証するvalidatorを生成する。
       """
       def _validator(phases) -> tuple[bool, str]:
           if not isinstance(phases, list) or not protected_task_ids:
               return True, ""
           new_task_ids = {
               t.get("task_id") for p in phases if isinstance(p, dict)
               for t in p.get("tasks", []) if isinstance(t, dict)
           }
           missing = protected_task_ids - new_task_ids
           if not missing:
               return True, ""
           return False, (
               "以下のtask_idは既に承認済み（Approved/Approved_with_Conditions/"
               "Implicitly_Accepted）のDeliverableを持つため、計画から除去してはいけません。"
               "廃止・リネームせず、既存のまま維持するか、新しいtask_idを追加した上でこれらは"
               "変更せず残してください: " + "、".join(sorted(missing))
           )
       return _validator
   ```

`call_task_planner`側で両者を合成し呼び出す（**[Cline指摘F1・重要で発覚・反映済み]**
`call_task_planner`末尾の`_enforce_decision_lineage_json`（BL-283、cela_main.py:7415）が
「未記録Decisionがあれば1回だけJSON全体を再出力させる」差し戻しを行うが、その再出力は
従来`_query_and_parse_with_retry`の外側で行われ`_task_plan_validator`を一切通らない。
validator合格→BL-283再出力→depends_on不整合や保護task_id欠落を再導入、という経路が
現実にありうるため、`_enforce_decision_lineage_json`にも`validator`引数を追加し
（デフォルトNoneで他の全呼び出し元——detector×2/reflection/reviewer/goal_essence_
analyst/task_plan_reviewer——は非退行）、`call_task_planner`から同じ`_task_plan_validator`
を渡す。再出力がvalidator不合格の場合はfail-safe側に倒し、**validator合格済みの直前の
`parsed`を採用する**（BL-283の記録漏れ自体は`_record_decision_lineage_gap_issue`が
既にmajor issueとしてloudに起票済みのため、情報は失われない）：

```python
_protected_task_ids = set()
if revision_reason and state:
    _conn_guard = get_active_conn()
    # [Cline指摘F6・軽微] task_id数×agreements全件走査になるが、既存_is_task_completedの
    # 再利用によるAGENTS.md §15.1のメリット（判定ロジックの単一化）とのトレードオフとして
    # 許容する（現状のBL-313実インシデントの規模では実害なし）。
    _protected_task_ids = {
        t["task_id"] for p in (existing_phases or []) for t in p.get("tasks", [])
        if _is_task_completed(_conn_guard, state["run_id"], t["task_id"])
    }
_protected_validator = _build_protected_task_id_validator(_protected_task_ids)

def _task_plan_validator(phases) -> tuple[bool, str]:
    ok1, msg1 = _validate_task_plan_depends_on_integrity(phases)
    ok2, msg2 = _protected_validator(phases)
    if ok1 and ok2:
        return True, ""
    return False, "\n\n".join(m for m in (msg1, msg2) if m)

phases, parse_failed = _query_and_parse_with_retry(
    prompt, client=client_task_planner, model=model_task_planner, label="Task Planner",
    tools=_task_planner_tools, fallback=fallback_phase,
    state=state, validator=_task_plan_validator,
)
if not parse_failed:
    # [Cline指摘F1] BL-283差し戻し再出力にもvalidatorを適用する。
    phases = _enforce_decision_lineage_json(
        prompt, phases, client=client_task_planner, model=model_task_planner, label="Task Planner",
        tools=_task_planner_tools, state=state, validator=_task_plan_validator,
    )
```

`_enforce_decision_lineage_json`側の変更（既存シグネチャへ`validator`引数を追加するのみ、
他の呼び出し元は引数省略でデフォルトNone＝従来通りの挙動）:
```python
def _enforce_decision_lineage_json(
    prompt, parsed, client, model, label, tools, state,
    validator: "Callable[[dict], tuple[bool, str]] | None" = None,
):
    pending = _pending_decision_candidates()
    if not pending:
        return parsed
    # ...既存の retry_prompt 組み立て・query_AI 呼び出し・_safe_json_parse は変更なし...
    retried_parsed = _safe_json_parse(retried_res, fallback=parsed)
    retry_writes = sum(1 for item in _LAST_WRITE_AGREEMENT_ITEMS if item.get("entry_type") == "Decision")
    if retry_writes < len(pending):
        _record_decision_lineage_gap_issue(label, pending, retry_writes, state)
    # [BL-329/Cline指摘F1] BL-283再出力はvalidatorを経由していないため再適用する。
    if validator is not None:
        ok, _ = validator(retried_parsed)
        if not ok:
            print(f"  ⚠️ [{label}][BL-329] BL-283差し戻し再出力がvalidator不合格のため、"
                  f"validator合格済みの直前の出力を採用します（記録漏れ自体は別途issue化済み）。")
            return parsed
    return retried_parsed
```

`_query_and_parse_with_retry`は`validator`が不合格を返すと、その理由をプロンプトへ追記して
**同一呼び出し内で最大2回まで**LLMに自己修正させる（既存機構、変更不要）。リトライを
使い切っても不合格のままの場合は、最後の出力をそのまま返す（`parse_failed=False`）——
このケースへの対処が二次防御になる。

**[Cline指摘F2・推奨で発覚・反映済み]** 一次防御（validator）は`_query_and_parse_with_
retry`の`parsed is not fallback`分岐（JSONとして読めた場合）でしか呼ばれない
（cela_main.py:7281-7282）。再構成時にJSONパースが**全滅**すると、`fallback_phase`
（task_1_1のみの縮退計画）がそのまま返り、`removed_task_ids`＝旧計画の全task_idという
最悪ケースになる——一次防御は最初から機能せず、**二次防御（機械的復元）だけが承認済み
task_idを救う唯一の経路**になる。「一次防御が機能する限りこの分岐はほぼ発火しない」という
想定は、この経路を踏まえると不正確なため訂正する：**二次防御は「稀にしか発火しない保険」
ではなく、パース全滅という構造的に起こりうる経路では常にload-bearingになる**。
Verification 6（後述）はこのパース全滅シナリオを明示的にカバーする。

**二次防御（事後の機械的復元）**: 一次防御のretryを使い切った場合・JSONパースが全滅した
場合のいずれでも、なお承認済みtask_idが計画から欠けていれば、`task_planner_node`の
`removed_task_ids`ループ（16470付近）へ以下のガードを追加する（Cline独立レビュー2回で
確定済みの実装、指摘1〜7・F1〜F5すべて反映済み。**[Cline指摘F5で発覚]** 以前の版では
この実装詳細を「Critical Filesを参照」と省略していたが、AGENTS.md §4「要約しない」に
従い本文へ復刻する）:

```python
_conn = get_active_conn()
for tid in sorted(removed_task_ids):
    old_phase_id = _find_phase_id_for_task(old_phases, tid) or ""

    if _is_task_completed(_conn, state["run_id"], tid):
        _existing = _find_active_deliverable_agreement(_conn, state["run_id"], old_phase_id, tid)
        _existing_status = _existing.get("status") if _existing else "completed(RESOLVING_DELIVERABLE_STATUSES)"
        _old_task_obj = _find_task_by_id(old_phases, tid)
        # 復元先のphaseが新計画に既に存在する場合はそのtasks配列へ挿入し、
        # 存在しない場合（フェーズ自体が消えたエッジケース）は旧phaseオブジェクトを
        # 浅コピーした新規phaseエントリとして追加する——この分岐が実装の要（F5）。
        _target_phase = next((p for p in phases if p.get("phase_id") == old_phase_id), None)
        if _target_phase is None:
            _old_phase_obj = next((p for p in old_phases if p.get("phase_id") == old_phase_id), None)
            _target_phase = dict(_old_phase_obj) if _old_phase_obj else {"phase_id": old_phase_id, "title": old_phase_id}
            _target_phase["tasks"] = []
            phases.append(_target_phase)
        if _old_task_obj and not any(t.get("task_id") == tid for t in _target_phase.setdefault("tasks", [])):
            _target_phase["tasks"].append(_old_task_obj)
        print(
            f"  🛡️ [BL-329] task_id='{tid}'は承認済みDeliverable（status="
            f"'{_existing_status}'）を持つため、計画再構成による廃止を見送り"
            f"計画へ復元しました（理由: {revision_reason}）。"
        )
        _write_agreement_impl(
            {
                "action_type": "CREATE", "status": "Proposed", "entry_type": "Directive",
                "topic": f"task_plan_{tid}_restored_by_bl329", "task_id": tid, "phase_id": old_phase_id,
                "decision_what": (
                    f"task_id='{tid}'は計画再構成の対象でしたが、既にstatus="
                    f"'{_existing_status}'のDeliverableを持つため、廃止せず"
                    "計画に復元しました（BL-329：承認済み成果物の機械的保護）。"
                ),
                "reason_why": revision_reason,
            },
            _conn, state["run_id"], "task_planner", tid,
            phases=old_phases, pending_task_ids=state.get("pending_task_ids", []),
        )
        continue

    state.setdefault("phases_superseded", []).append({
        "task_id": tid, "phase_id": old_phase_id, "reason": revision_reason,
        "superseded_at_round": state.get("round_count", 0),
    })  # 既存のまま
    _write_agreement_impl({...})  # 既存のまま（廃止Directive）
    print(f"  🔀 [Task Planner] task_id='{tid}'（phase='{old_phase_id}'）をsupersedeしました（理由: {revision_reason}）。")  # 既存のまま
```

### なぜ「1タスクずつツール登録」ではなく「一括JSON＋validator」を選んだか

- 一括JSON生成をタスクごとのツール呼び出しへ分解する案は、ユーザー提案の「その場で気づいて
  直せる」という核心的な利点をより細粒度で実現できるが、`call_task_planner`の出力パイプ
  ライン全体（プロンプト構造・パース・フォールバック・plan_reviewerとの連携）を作り直す
  大改修になる。
- 一方、`validator`フックによる「一括生成→検証→不合格なら理由を添えて同一呼び出し内で
  再生成」は、**同じ「その場で気づいて直せる」性質を、既存の実証済み機構の再利用だけで
  実現できる**（BL-213 F3で既に本番運用されているパターン）。違いは「1タスクごとに
  即座に個別フィードバックを受ける」か「JSON全体を一度に評価され、まとめてフィードバックを
  受けて全体を再生成する」かだが、後者でも検証メッセージに問題のあるtask_idを具体的に
  列挙するため、モデルが必要な箇所だけを狙って修正することは可能。
- 将来、task_id保護やdepends_on整合以外にも検証したい意味的制約が増えた場合、この
  `validator`は関数を追加するだけで拡張できる（AGENTS.md §15.1: 単一の検証機構に集約）。

## Critical Files

- `cela_main.py`:
  - `call_task_planner`直前または内部（11930付近）: `_validate_task_plan_depends_on_
    integrity`・`_build_protected_task_id_validator`の2関数を新規追加。
  - `_enforce_decision_lineage_json`（7415付近）: `validator`引数を追加（デフォルトNone）。
    再出力取得後、非Noneならvalidatorを再適用し不合格ならvalidator合格済みの直前の
    `parsed`を返す（Cline指摘F1）。
  - `call_task_planner`（11930付近）: `_task_plan_validator`（2検証の合成）を組み立て、
    `_query_and_parse_with_retry`と`_enforce_decision_lineage_json`の両方へ`validator=`
    として渡す。
  - `task_planner_node`の`removed_task_ids`ループ（16470-16489付近）: 二次防御（機械的
    復元）を追加。判定は`_is_task_completed`（8470、`RESOLVING_DELIVERABLE_STATUSES`使用）
    を再利用し、`_find_active_deliverable_agreement`（3915）でログ用status文字列を取得、
    対象phase_idが新計画に無ければ旧phaseオブジェクトを浅コピーして復元する（詳細実装は
    「設計」節の二次防御コードブロック参照、Cline独立レビュー3回で確定済み）。
- `tests/test_bl329_task_plan_validator_and_deliverable_protection.py`（新規）

## Verification

### 一次防御（validator）

1. `_validate_task_plan_depends_on_integrity`単体テスト: 全depends_onが実在するtask_idを
   指す正常系（合格）、存在しないtask_idを指す異常系（不合格・該当task_id/depends_on値が
   エラーメッセージに列挙される）、depends_on空配列（合格）、phasesが空リスト（合格）。
2. `_build_protected_task_id_validator`単体テスト: 保護対象task_idが新計画に存在する
   （合格）、欠けている（不合格・欠落task_idがエラーメッセージに列挙される）、保護対象
   集合が空（常に合格、初回計画相当の非退行確認）。
3. `call_task_planner`統合テスト: `query_AI`をモンキーパッチし、1回目の応答が保護対象
   task_idを欠いたJSON、2回目（自己修正後）の応答が正しいJSONを返すシナリオで、最終的に
   2回目の内容が採用されること（validator retryが実際に機能することの確認）。
4. 同様に、depends_on不整合を1回目で出し2回目で自己修正するシナリオも確認する。
5. リトライを使い切っても不合格のままの場合、`parse_failed=False`で最後の出力がそのまま
   返ること（既存`_query_and_parse_with_retry`の挙動の非退行確認）。
6. **[Cline指摘F1]** `_enforce_decision_lineage_json`統合テスト: BL-283差し戻し
   （未記録Decision）が発生し、その再出力がvalidator不合格（保護task_id欠落 or
   depends_on不整合）の場合、再出力ではなく**validator合格済みの直前の`parsed`**が
   採用されること。再出力がvalidator合格ならその再出力が採用されること（両方確認）。

### 二次防御（機械的復元、フォールバック経路）

7. `task_planner_node`を`call_task_planner`をモンキーパッチした状態で直接呼び、
   validatorが機能しなかった場合を模したシナリオ（新計画が保護対象task_idを欠いたまま
   返る）で、(a) 承認済みDeliverable付きtask_idは`phases`へ復元され`phases_superseded`
   には記録されないこと、(b) Deliverableなしtask_idは従来通り廃止されること、を確認する。
   `seed_entities_from_goal`もスタブ化すること（実LLM呼び出し回避）。
8. `Approved_with_Conditions`・`Implicitly_Accepted`いずれのステータスでも復元されること。
9. 復元対象のphase_idが新計画に存在しない場合、旧phaseオブジェクトを浅コピーした新規
   phaseエントリとして追加されること。
10. 復元後、`read_deliverable_file(task_id=tid)`が承認済み内容を正しく返すこと
    （1633ログの実インシデントの直接的な再発防止確認）。
11. 復元されたtask_idについて監査用Directiveが記録されること。
12. **[Cline指摘F2・重要]** パース全滅シナリオ: `call_task_planner`をモンキーパッチし
    `parse_failed=True`（`fallback_phase`採用）を模した状態で`task_planner_node`を呼び、
    一次防御が一切機能しなかった場合でも、二次防御だけで承認済みtask_idが計画から
    失われないことを確認する（このシナリオでは二次防御が「稀な保険」ではなく「唯一の
    防衛線」であることの実証）。

### 共通

13. AGENTS.md §17.1に従い、(a) validator引数を渡す変更（`call_task_planner`・
    `_enforce_decision_lineage_json`双方）、(b) 二次防御の機械的復元、それぞれを個別に
    一時的にrevertし、対応するテストが失敗することを確認した上で復元する。
14. `python -m py_compile cela_main.py`。
15. 影響範囲テスト: 既存のtask_planner_node関連テスト（BL-126 Stage C・BL-145・BL-313・
    BL-315）・BL-213関連（`_query_and_parse_with_retry`/`validator`機構の非退行）・
    `_enforce_decision_lineage_json`の他の呼び出し元（detector×2/reflection/reviewer/
    goal_essence_analyst/task_plan_reviewer、`validator`省略時デフォルトNoneで非退行）
    を再実行し確認。
16. フルオフラインスイート実行。
17. **[Cline指摘F7]** 実装前に`docs/design/back_log/issue_backlog.md`へBL-329を起票する
    （現時点で未起票）。
18. 実装前に、本設計書を`docs/design/back_log/BL-329/BL329_basic_design.md`へ保存し、
    `scripts/cline_review.py`による§19.1独立レビューを実行、指摘を実コードで検証の上
    反映してから実装に入る。
19. 実装後、Cline CLIによる独立レビュー（AGENTS.md §19.4 diff-based）を実施し、指摘を
    実コードで検証の上反映する。
20. `decision_log.md`・`decision_lineage.md`へ記録する。

## スコープ外・対応しないこと

- 既に発生してしまったtask_5_2/task_5_5の孤立データ（現run_id=1787890406-1e73a89d、
  ラン停止済み）の是正は、本BLのスコープに含めない。コード修正の承認とは別に、必要であれば
  AGENTS.md §18.3（バックアップ・スコープ明示・承認）に従って別途相談する。
- task_planner出力形式を一括JSONから1タスクずつのツール呼び出しへ作り直す改修は、
  ユーザー提案として検討したが、`validator`フックで同等の効果が既存機構の再利用だけで
  得られるため今回は不採用とした。将来、より細粒度な即時フィードバックが必要になれば
  別BLとして再検討する。
- 承認済み成果物と新task_idの重複（例: task_5_2とtask_5_2_1が両方存在し得る）を自動で
  検知・統合する機能は今回追加しない。

## 実装後に発覚した追加の設計判断（フルオフラインスイート実行時に発見）

Cline実装後diffレビュー（§19.4、`--path cela_main.py --path tests/...`）は限定的な影響範囲
テスト（BL-126/283/213系122件）のみを対象にしており全件検出できなかったが、フルオフライン
スイート実行で`tests/test_bl191_task_focus_scheduling.py`の2件が回帰した。原因はBL-191
（`schedule_task_focus`のredirect_backward）との設計上の衝突: BL-191は既にApproved済みの
過去タスクへ一時的にフォーカスを戻し、その後`_reconcile_current_phase_after_replan`
（本ループの後で実行される）が「フォーカス中task_idが新計画から消えた」ことを検知して
強制的にfocus_stackをクリアしフォワードタスクへ復帰する設計だった。BL-329がこの
「消えるべきtask_id」まで機械的に計画へ復元すると、BL-191のreconcile分岐が発火しなくなる。

対応: `state.get("task_focus_stack", [])`の各エントリの`focused_task_id`をBL-329の保護対象
から除外し（`tid not in _focused_task_ids and _is_task_completed(...)`という条件へ変更）、
BL-191が既に「一時的に消えうる」と認識しているtask_idについては既存のBL-191側reconcile処理
に委ねることにした。新規回帰テスト`test_bl329_does_not_block_bl191_focus_vanish_
reconciliation`を追加し、AGENTS.md §17.1に従いこの除外条件を一時的にrevertして3件
（新規1件＋既存2件）が失敗することを確認した上で復元した。

この経緯自体が、AGENTS.md §17.3（フルオフラインスイートはマイルストーン前に必須）と
§19.4（diffレビューは実コードの一部しか見ない）の限界を示す実例——**影響範囲を絞った
レビュー・テストだけでは検出できない他機構との相互作用は、フルスイートでしか捕まらない
ことがある**——として記録する。

Cline実装後diffレビュー（§19.4）自体は承認（マージ可）判定で、軽微な指摘3件（F1: 
`_enforce_decision_lineage_json`のdocstringが「validator合格済みの直前のparsed」と過大に
保証していた実際は不合格の可能性もある、F2: 保護task_id収集で`t["task_id"]`直接索引を
`t.get("task_id")`へ、F3: エラーメッセージのステータス列挙を`RESOLVING_DELIVERABLE_
STATUSES`から導出しドリフトを防ぐ）を受け、いずれも実コードで検証の上反映した。
