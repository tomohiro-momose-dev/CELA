# BL-329: 計画再構成でtask_idが除去される際、承認済みDeliverableを機械的に保護する

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
正確に言い当てた。ライブランは停止済み。ユーザーからの指示：「根本を修正してください」。

## 根本原因（コード調査済み）

`task_planner_node`（cela_main.py:16404）の計画再構成分岐（`revision_reason`セット時、
16462行以降）で、以下の完全に機械的なPythonロジックが実行される：

```python
old_task_ids = {t["task_id"] for p in old_phases for t in p.get("tasks", [])}
new_task_ids = {t["task_id"] for p in phases for t in p.get("tasks", [])}
removed_task_ids = old_task_ids - new_task_ids
for tid in sorted(removed_task_ids):
    # ... write_agreement(SUPERSEDE, "タスク{tid}はラン途中の計画再構成により廃止されました。")
```

`phases`（新計画）は`call_task_planner`（LLM呼び出し）が生成する。**新計画に古いtask_idが
一つでも含まれなくなれば、このPythonループが無条件・無条件チェックなしでそのtask_idを
「廃止」として記録する**——対象task_idが承認済みDeliverableを持っているかどうかは一切
考慮されない。

`revision_reason`のプロンプト文言自体は「ただし分割が最善とは限りません...統合する判断も
可とします」とtask_plannerに一定の裁量を与えているが、これは**プロンプトによる期待に過ぎず
コード側で強制されていない**——実際、task_plannerは5対象中2件（task_5_2/task_5_5）で
既に承認済みだった成果物を丸ごと廃止する計画を提案し、それがそのまま無検証で実行された。
これはAGENTS.md §15.3（プロンプト任せにせずコード側を権威とする）に反する構造であり、
この機械的ループの箇所自体が今回のインシデントの直接原因である。

このループはBL-313専用ではなく、BL-126 Stage Cで導入された汎用の計画再構成インフラ
（BL-145の停滞トリガー・BL-315の申し送り放置トリガー等、`plan_revision_reason`を
セットする全ての経路が共通で通る）であるため、本修正は今後発生しうる同種のインシデントを
まとめて予防する。

## 設計

### 機械的ガード: 承認済みDeliverableを持つtask_idは自動廃止しない

**[Cline独立レビュー§19.1・必須修正1で発覚・修正済み]** 判定に使う「承認済み」ステータス
集合を独自にハードコード（`("Approved", "Approved_with_Conditions")`）せず、コードベースの
権威ある定義`RESOLVING_DELIVERABLE_STATUSES = {"Approved", "Approved_with_Conditions",
"Implicitly_Accepted"}`（cela_main.py:8467、BL-167の完了判定・BL-073のDirective自動解決・
BL-163の自動起票がすべて参照する共通定数）を再利用する。判定述語自体も、新規に
`_find_active_deliverable_agreement`の戻り値を直接判定するのではなく、既存の
`_is_task_completed(conn, run_id, task_id)`（cela_main.py:8470、`RESOLVING_DELIVERABLE_
STATUSES`を内部で使う既存関数）をそのまま真偽値ゲートとして再利用し、ログ・Directive
用の実際のstatus文字列だけを`_find_active_deliverable_agreement(conn, run_id, phase_id,
task_id)`（cela_main.py:3915、Superseded以外の最新Deliverable agreementを返す既存
ヘルパー）から取得する。これにより「独自集合を持つと将来ステータスが増えたときにガード
だけ取りこぼす」というAGENTS.md §15.1違反を避ける。

判定結果が真の場合、**廃止せず`tid`を`phases`へ機械的に復元する**。これによりAGENTS.md
§15.3（コード側を権威とする）に整合させる。

**[既知の限界・Cline指摘「中」で発覚]** `_is_task_completed`は「最新の非Superseded
Deliverableのstatus」だけを見るため、承認済み版の上にさらに再作業版（status=Proposed等）
が積まれているタスクではこのガードは効かず、従来通り廃止される。これは意図的なスコープ
限定であり、「過去に一度でもApprovedへ到達したtask_idは恒久的に保護する」という拡張は
別BLで検討する（そのような拡張は、正当に上書き・撤回されたはずの古いスコープが復活する
リスクとのトレードオフを要するため、本BLの範囲では扱わない）。廃止時のprintログは
引き続き出るため、無音の失敗（silent failure）ではない。

設計判断（軽い代替の検討）：
- 案A（採用）: 承認済みtask_idを新計画へ機械的に復元し、廃止をブロックする。既存の
  「完全版Deliverableの上書きを保護する」既存パターン（BL-180/BL-261、`_commit_agreement_
  from_tool`のUPDATE分岐/全文置換ガード）と同じ設計哲学の踏襲であり、実装コストが低い。
  復元されたtask_id
  と、task_plannerが新設した類似スコープの新task_id（例: task_5_2_1）が並存しうるが、
  これは**データ消失より安全な失敗モード**（AGENTS.md §13.2: fail-safe > silently wrong）。
  重複が生じた場合は後続のReflector監査や人間判断で整理すればよく、承認済み成果物を
  二度と参照不能にすることに比べ実害は小さい。
- 案B（不採用）: task_plannerへの再構成そのものを差し戻す（エラーを返しリトライさせる）。
  1回の再構成で複数task_idが同時に処理されるため、1件の問題で再構成全体をブロックすると
  無限リトライや他の正当な変更まで巻き込むリスクがあり、案Aより重い。
- 案C（不採用）: 承認済み内容を新task_id（例: task_5_2→task_5_2_1）へ自動移行する。
  どの新task_idが「スコープを継承した後継」かをタイトル文字列等から推測する必要があり、
  誤った移行（無関係なtask_idへ承認済み内容が紛れ込む）の方がリスクが大きい
  （§13.2と同じ理由でヒューリスティックによる自動判定を避ける）。

### 実装

`task_planner_node`の`for tid in sorted(removed_task_ids):`ループ（cela_main.py:16470
付近）の先頭に判定を追加する。

```python
_conn = get_active_conn()
for tid in sorted(removed_task_ids):
    old_phase_id = _find_phase_id_for_task(old_phases, tid) or ""

    # [BL-329] 既に完了相当（RESOLVING_DELIVERABLE_STATUSES）のDeliverableを持つtask_idを、
    # 計画再構成が無条件に「廃止」扱いにして参照不能にしないための機械的ガード（1633ログの
    # 実インシデント：task_5_2/task_5_5が承認済み成果物ごと廃止され、read_deliverable_file
    # がnot_foundを返すようになっていた）。revision_reasonのプロンプト文言は既に「分割が
    # 最善とは限らない」とtask_plannerへ裁量を与えているが、プロンプトだけに頼らずコード側で
    # 強制する（AGENTS.md §15.3）。真偽値判定はBL-167の完了判定と同じ権威ある述語
    # `_is_task_completed`を再利用し（AGENTS.md §15.1：判定集合を独自に持たない）、ログ・
    # Directive用のstatus文字列だけ`_find_active_deliverable_agreement`から取得する。
    if _is_task_completed(_conn, state["run_id"], tid):
        _existing = _find_active_deliverable_agreement(_conn, state["run_id"], old_phase_id, tid)
        # [Cline独立レビュー§19.1・中で発覚] _is_task_completedがTrueでも、実装詳細が将来
        # ドリフトすれば_find_active_deliverable_agreementがNoneを返す可能性を理論上排除
        # できない（現行実装では両者は同じ最新行を指すため実際には起きないが、防御的に
        # 備える）。Noneでも復元という保護動作自体は実施する（fail-safe方向）。
        _existing_status = _existing.get("status") if _existing else "completed(RESOLVING_DELIVERABLE_STATUSES)"
        _old_task_obj = _find_task_by_id(old_phases, tid)
        _target_phase = next((p for p in phases if p.get("phase_id") == old_phase_id), None)
        if _target_phase is None:
            # [Cline指摘「小」] LLM生成phaseは将来追加フィールドを持ちうるため、最小構成の
            # 辞書を手組みするのではなく旧phaseオブジェクトを浅コピーし、tasksだけ
            # 復元対象に差し替える（将来phaseスキーマが増えても壊れない）。
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

    state.setdefault("phases_superseded", []).append({...})  # 既存のまま
    _write_agreement_impl({...})  # 既存のまま（廃止Directive）
    print(f"  🔀 [Task Planner] ...")  # 既存のまま
```

`phases`はこの時点でまだ`state["phases"] = phases`（16495行）へ代入される前のローカル
変数なので、ループ内での`phases.append(...)`/`tasks.append(...)`はそのまま最終計画へ
反映される。

**[既知の限界・Cline指摘「小」]** 復元されたphaseは`phases.append(...)`により配列の
**末尾**に追加される。実行順序は`depends_on`/`current_task_id`駆動でリスト順に依存しない
ため機能上は無害だが、task_plannerへ提示されるphases JSON上では完了済みフェーズが最後に
並ぶ見た目になる。また、復元されたtask（や他タスク）の`depends_on`が、正当に廃止された
別task_idを指したまま残る可能性がある——遷移検証はtask_idの実在確認のみを行うため
クラッシュはしないが、依存関係の意味的な整合までは保証しない。いずれも既知の限界として
記録するに留め、本BLでは対応しない。

## Critical Files

- `cela_main.py`: `task_planner_node`（16404付近）の`removed_task_ids`ループ
  （16470-16489付近）へBL-329ガードを追加。新規ヘルパー関数は不要（既存の
  `_is_task_completed`/`_find_active_deliverable_agreement`/`_find_phase_id_for_task`/
  `_find_task_by_id`を再利用）。
- `tests/test_bl329_approved_deliverable_survives_replan.py`（新規）

## Verification

1. 単体的な統合テスト: `task_planner_node`を`call_task_planner`をモンキーパッチした状態で
   直接呼び、旧計画にtask_5_2（Approved Deliverable付き）とtask_5_1（Deliverableなし）を
   含め、新計画（モック）がどちらも含まない場合に、(a) task_5_2は`phases`へ復元され
   `phases_superseded`には記録されないこと、(b) task_5_1は従来通り`phases_superseded`へ
   記録され廃止Directiveが書かれること、を確認する。**[Cline指摘「小」]**
   `test_bl126_stage_c_task_planner_reconfiguration.py`と同様、`seed_entities_from_goal`も
   スタブ化すること（未スタブだと実LLM呼び出しへ落ち、日次クォータ枯渇時にテストが壊れる）。
2. `Approved_with_Conditions`・`Implicitly_Accepted`いずれのステータスでも同様に復元される
   こと（**Cline指摘「必須1」反映**：`RESOLVING_DELIVERABLE_STATUSES`の全メンバーを網羅
   確認、Approvedのみを特別扱いしていないことの確認）。
3. `Proposed`/`Superseded`等、`RESOLVING_DELIVERABLE_STATUSES`に含まれないDeliverableを
   持つtask_idは従来通り廃止されること（非退行）。
4. 復元対象のphase_idが新計画に一つも存在しない場合（フェーズ自体が消えたエッジケース）、
   旧phaseオブジェクトを浅コピーした新規phaseエントリ（title等の追加フィールドを保持）
   として`phases`へ追加されること。
5. 復元後、`read_deliverable_file(task_id=tid)`が承認済み内容を正しく返すことを
   （`_resolve_deliverable_pointer`経由で）確認する（1633ログのnot_found実インシデントの
   直接的な再発防止確認）。
6. 復元されたtask_idについて監査用Directive（`topic=f"task_plan_{tid}_restored_by_bl329"`）
   が記録されること。
7. AGENTS.md §17.1に従い、BL-329ガード（`if _is_task_completed(...)`分岐）を一時的に
   revertし、上記1・5のテストが失敗する（廃止されてしまう／not_foundに戻る）ことを確認した
   上で復元する。
8. `python -m py_compile cela_main.py`。
9. 影響範囲テスト: 既存のtask_planner_node関連テスト（BL-126 Stage C・BL-145・BL-313・
   BL-315関連）を再実行し非退行確認。
10. フルオフラインスイート実行。
11. 実装前に`docs/design/back_log/issue_backlog.md`へBL-329を起票。
12. **[Cline指摘「必須2」反映]** 実装着手前に、本設計書を
    `docs/design/back_log/BL-329/BL329_basic_design.md`へ保存し、`scripts/cline_review.py`
    による§19.1独立レビューを実行、指摘を実コードで検証の上反映してから実装に入る
    （AGENTS.md §19の順序強制は非自明な変更に例外を認めていない——「小規模だから」は
    §19.1省略の理由にならない）。
13. 実装後、Cline CLIによる独立レビュー（AGENTS.md §19.4 diff-based）を実施し、指摘を
    実コードで検証の上反映する。
14. `decision_log.md`・`decision_lineage.md`へ記録する（設計書自体は手順12で実装前に
    保存済み）。

## スコープ外・対応しないこと

- 既に発生してしまったtask_5_2/task_5_5の孤立データ（現run_id=1787890406-1e73a89d、
  ラン停止済み）の是正は、本BLのスコープに含めない。コード修正の承認とは別に、必要であれば
  AGENTS.md §18.3（バックアップ・スコープ明示・承認）に従って別途相談する。
- 承認済み成果物と新task_idの重複（例: task_5_2とtask_5_2_1が両方存在し得る）を自動で
  検知・統合する機能は今回追加しない。将来必要になれば別BLとして起票する。
