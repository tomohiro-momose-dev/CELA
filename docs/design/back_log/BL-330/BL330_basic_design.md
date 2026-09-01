# BL-330: Deliverable旧レコード検索へBL-084のtask_id基準識別を適用（1917応急修正）

（§19.1 Cline独立レビュー実施済み・指摘反映済み。`scripts/cline_review.py`に`--model`一時
上書き引数を追加してデフォルトモデルの日次無料枠上限を回避、`deepseek/deepseek-v4-flash`で
実施。承認後は本計画を`docs/design/back_log/BL-330/BL330_basic_design.md`へ保存する。）

## Context

`log/2026-08-31/1917`（run_id=1787890406-1e73a89d、現在も稼働中の可能性あり）で、BL-125の
タスク遷移ブロックをユーザーが提示。DB実測（`cela.db`）の結果、以下のデータ破損を確認した：

- task_4_1のDeliverable行4件（初版CREATE＋UPDATE×2＋誤登録1件）が全て`status='Superseded'`
  となり、現在生きている行が0件（BL-176が正しく「未承認」としてブロックした直接原因）。
- 直近の誤登録行`AG-1788173804094-b6f773`は、topicが「task_4_2成果物（案）：OpEx人件費の
  積算...」であるにも関わらず`task_id`フィールドが`task_4_1`のまま書き込まれていた
  （発生源のターンは未特定）。
- 現在`status='Approved_with_Conditions'`の`AG-1788174245452-3d60bd`（`task_id='task_4_2'`、
  こちらは正しい）が、`decision_what='WHITEBOARD:phase_4:task_4_1'`——**task_4_1のホワイト
  ボードスロットを指すポインタ**を持ったまま生きている。`whiteboard_drafts`にtask_4_2用の
  行は一度も作られていない。

**根本原因**: `cela_main.py:17957-17964`（decision_extractorノード自身の直接書き込み
フォールバック経路。`write_agreement`ツール本体＝`_write_agreement_impl`とは別の書き込み口）
が、UPDATE/Approved_with_Conditions時の旧レコード特定を`a["topic"] == target_topic and
a.get("entry_type") == entry_type`のみで行っており、`task_id`を一切検証しない。topicが
偶然/誤って一致する別task_idの行を掴むと、そのままSuperseded化・ポインタ継承してしまう。

**この設計は既にBL-084で解決済みのはずだった**——調査の結果、`_write_agreement_impl`内の
同型3箇所（`cela_main.py:4041-4049`のSUPERSEDE分岐・`4098-4119`のUPDATE分岐・
`4241-4250`のsupersede実行分岐）は、いずれも`entry_type=="Deliverable"`の場合のみ
`_find_active_deliverable_agreement(conn, run_id, phase_id, task_id)`（BL-084、`cela_main.py:3915`、
task_id基準・phase_idはWHERE句に含めずBL-206でフェイルセーフ化済み）を使う分岐が既に入っており、
topic文字列一致はDecision/Directive限定という意図的な設計（コメント明記）。**decision_extractor
自身の直接書き込み経路（17957-17964）だけが、この3箇所と非対称にBL-084の保護を受けていな
かった**——AGENTS.md §13.4（同じ不変条件は全ての書き込み経路で対称に保つ）が想定する型の
欠落で、BL-206/210/211/212/329（§13.7）と同系譜の識別子不整合バグの6件目。

（当初「同型パターンが独立に5箇所存在する」と報告したが、上記3箇所は既にBL-084で保護済み・
`_find_prior_superseded`（`11012`、表示専用フォールバックで書き込みを伴わない）も低リスクと
判明したため訂正済み。実際の欠落は17957-17964の1箇所のみ。`decision_log.md` D-282・
`issue_backlog.md` BL-330節に訂正記録済み）。

なお、ユーザーはこの調査を受けて「タスクプランナー・phase/task_idをDAG型にして機械的な紐づけを
行う」という、より根本的な再設計の方向性に賛成しており（D-282）、その本体はBL-331として別途
設計する。本BL-330は、その方向性とは独立に**今すぐ必要な応急修正**（実データ破損の是正含む）
のみを対象とする。

### §19.1 Clineレビューで発覚した追加事実（実装前に必ず反映）

`scripts/cline_review.py`（`--model deepseek/deepseek-v4-flash`、無料枠上限に達したデフォルト
モデルの代替）による本計画のレビューで、コード修正部分（上記）は実コード3点照合で妥当と確認された
一方、**計画作成時点のDBスナップショットが古くなっていた**ことが判明した：

- **`AG-1788174791944-9e5eac`（task_id='task_4_1'、status='Approved_with_Conditions'、
  topicはtask_4_2のOpEx文言、`decision_what='WHITEBOARD:phase_4:task_4_1'`）が2026-08-31
  20:13:11に新規作成され、現在も生きている**（再クエリで確認済み）。これにより現在、
  **同一topic・同一entry_typeの生きている行が2件**（3d60bd=task_id task_4_2 / 9e5eac=
  task_id task_4_1）並存している。
- **これは17957-17964のfallback経路のバグではなく、`write_agreement`ツール本体（既に
  BL-084保護済みの正規経路）で発生した、別種の欠陥**。ログ確認（`log/2026-08-31/1917/
  log_no_prompt.md:2927`）の結果、User AI Stage3の`write_agreement`呼び出しが
  `task_id`引数を一切指定していなかった（`target_topic=""`のみ）。`_write_agreement_impl`の
  `tid = args.get("task_id") or task_id`（`cela_main.py:4034`付近）が、未指定時に
  **呼び出し元の現在タスクID（`current_task_id`）へ暗黙フォールバックする**設計のため、
  「まだtask_4_2へ遷移できていない（BL-176が20:04の破損のせいでブロックし続けている）」
  という当時のシステム状態がそのまま`tid='task_4_1'`として採用され、task_4_2の内容が
  task_4_1のtask_idで書き込まれた。§13.1（`.get(key, default)`型フォールバックの危険）と
  同型だが対象が`task_id`引数である点で新規。
- **本BL-330の修正はこの第2の経路を防がない**（`_write_agreement_impl`は既にBL-084保護
  済みで、`_find_active_deliverable_agreement(phase_id, tid='task_4_1')`が「task_4_1に
  アクティブな行なし」を正しく返した上で、新規行として素直に書き込んだだけ——lookup自体は
  正しく動作している。壊れているのは「task_id引数が未指定の場合のフォールバック先」）。
  **この限界を実装後の記録に明記し、`tid`フォールバックの是非は別途スコープ判断とする**
  （BL-331の設計対象に含めるか、新規BLを起票するかはユーザー判断）。
- **ラン状態の訂正**: ログ末尾（20:18:51）に`[PAUSE] Ctrl+C`が記録されており、稼働中ではなく
  **一時停止中**。ただしcheckpointは保持されており`--resume`で再開可能——実データ修正後に
  この run のcheckpointから再開すると、DB側の修正とLangGraph state側の内容が食い違う
  （§14.4）。実データ修正を行うなら、このrunは今後resumeしない（または再開前にuser と
  再合意する）ことを前提とする。
- 訂正: `decision_log.md`/`issue_backlog.md`のBL-330節は既に「1箇所のみ」に訂正済みだが、
  `issue_backlog.md`冒頭のサマリ表（357行目付近）に旧文言「5箇所」が残っているため、
  実装と同時に更新する。

## 設計

### コード修正（応急修正の本体）

`cela_main.py:17957-17964`を、`_write_agreement_impl`の3箇所と同じパターンへ揃える：

```python
if entry_type == "Deliverable":
    # [BL-330] BL-084と同じ理由（topicドリフト・誤task_id行への追従防止）で、この直接書き込み
    # フォールバック経路も_find_active_deliverable_agreement（task_id基準）へ揃える。
    # _write_agreement_impl側の同型3箇所（4041/4098/4241）は既にBL-084でこの分岐を持つが、
    # decision_extractorのこの経路だけ非対称に取り残されていた（AGENTS.md §13.4、
    # log/2026-08-31/1917で実害確認）。
    target_agreement = _find_active_deliverable_agreement(_conn, _run_id, phase_id, task_id)
    if target_agreement is not None:
        target_topic = target_agreement["topic"]  # BL-084同様、実体のtopicへ揃える（topicドリフト対策）
        old_content = target_agreement["decision_what"]
        db_supersede_agreement(target_agreement["id"], _conn, _run_id)
        if proposed_by == "Unknown" or not proposed_by:
            proposed_by = target_agreement.get("proposed_by", "Unknown")
else:
    # [BL-206] ...（既存コメント・ループはそのまま、非Deliverable限定で維持）
    for a in reversed(get_agreements_from_db(_conn, _run_id)):
        if (a["topic"] == target_topic and a.get("entry_type") == entry_type
                and a.get("status") != "Superseded"):
            old_content = a["decision_what"]
            db_supersede_agreement(a["id"], _conn, _run_id)
            if proposed_by == "Unknown" or not proposed_by:
                proposed_by = a.get("proposed_by", "Unknown")
            break
```

`target_topic`を実体の`topic`へ上書きする一行は`_write_agreement_impl`のUPDATE分岐
（`cela_main.py:4100`: `target_topic = target["topic"] if target else topic`）に倣ったもの。
`phase_id`・`task_id`・`_conn`・`_run_id`はこの関数スコープに既存（直後の17976/17987行で
同名変数を使用済み）。

### Critical Files

- `cela_main.py:17957-17964`（上記置換のみ、前後のBL-212/BL-038保護ロジック・以降の処理は無改修）
- `tests/test_bl330_deliverable_supersede_lookup_task_id_scoped.py`（新規）

### テスト方針（§17.1）

1. 単体: `entry_type="Deliverable"`のUPDATE/Approved_with_Conditions時、topicが同じで
   `task_id`が異なる2行が存在する状況で、正しい`task_id`の行だけがsupersede・
   old_content継承の対象になること（誤task_id行は無視される）を確認する再現テスト
   （1917の実インシデントの直接再現）。
2. 非Deliverable（Decision/Directive）は従来通りtopic一致のみで動作すること（非退行）。
3. `entry_type="Deliverable"`で対象task_idにアクティブな行が存在しない場合
   （実質的な初回相当）、`old_content=""`のまま従来と同じに振る舞うこと。
4. `target_topic`が実体の`topic`へ揃うこと（呼び出し元が渡した`target_topic`と実際の
   agreement行のtopicがドリフトしているケース）。
5. 修正箇所を一時的にrevertし、テスト1が失敗することを確認した上で復元する（§17.1）。
6. `python -m py_compile cela_main.py`。
7. 影響範囲テスト（BL-084/BL-206/BL-212/BL-038関連の既存テスト）を再実行し非退行確認。
8. フルオフラインスイート実行。

### 実装後の手順

- AGENTS.md §19.4（diff-based独立レビュー）を実施し、指摘を実コードで検証の上反映。
- `decision_log.md`・`issue_backlog.md`（BL-330節）を実装結果で更新（`open`→`done`）。

## 1917実データの是正（§18.3: バックアップ・スコープ明示・承認）

コード修正だけでは、**既に壊れてしまった今回のrun（run_id=1787890406-1e73a89d）のデータは
直らない**。ユーザーの「1は実施」にはこの実データ修正も含むと理解しているが、Clineレビューで
判明した`9e5eac`（上記）を含めて改訂したスコープを、実行前に最終確認したい：

1. **ラン状態（訂正済み）**: 現在は**PAUSE中**（20:18:51 Ctrl+C）。稼働中ではないため即座に
   停止する必要はないが、**このrunのcheckpointは今後resumeしない**ことを前提に作業する
   （resumeするとLangGraph state側とDB修正後の内容が食い違う、§14.4）。resumeしない方針で
   よいか確認したい。
2. **バックアップ**: `cela.db`を`cela.db.bak-bl330-<timestamp>`としてコピーしてから作業する。
3. **修正内容（改訂案、9e5eac対応込み）**:
   - `AG-1788174245452-3d60bd`（task_id='task_4_2'、正しいtask_id）: `decision_what`を
     `WHITEBOARD:phase_4:task_4_1`から`WHITEBOARD:phase_4:task_4_2`へ修正。
   - `AG-1788174791944-9e5eac`（task_id='task_4_1'だが内容はtask_4_2のOpEx、実質的に
     3d60bdの重複）: `status`を`Superseded`へ変更し、生きている行から除外する（同一
     topic・同一entry_typeの重複アクティブ行を解消）。
   - `whiteboard_drafts`にphase_4/task_4_2の新規行（content=`deliverables/task_4_2
     成果物（案）：OpEx人件費の積算..._V1.md`ファイルの内容）を作成する。
   - task_4_1: 直近の正当な版（誤登録される直前の状態、`whiteboard_drafts`のphase_4/task_4_1
     v1＝CapEx内容を指す）を`status='Proposed'`で復活させ、`decision_what='WHITEBOARD:phase_4:task_4_1'`
     の生きている行を1件作る（ユーザーのレビュー対象として復元。既にUser AIが19:56頃から
     レビューしていた内容と一致）。
4. 上記の具体的なSQL/手順は実装フェーズで提示し、実行前に最終確認を仰ぐ。
5. **今回の限界（明記）**: この是正は今回発生した具体的な破損（1917run固有）を直すものであり、
   `_write_agreement_impl`の`tid`暗黙フォールバック自体（20:13の第2経路の根本原因）は
   直さない。同じ状況（未承認タスクへ遷移できないままtask_idを省略してwrite_agreementが
   呼ばれる）が別のrunで再発する可能性は残る——これはBL-330のスコープ外として、別途
   ユーザーと相談する。

この節はコード修正（上記）と独立して実施可否を判断できる。コード修正のみを先に進め、
実データ修正は上記1の確認後に別途進める、という順序も可能。

## 保存先

実装前に、本計画書を`docs/design/back_log/BL-330/BL330_basic_design.md`として保存する
（AGENTS.md §4.7、Clineレビュー指摘D）。

---

## 実装後の追記（2026-09-01）

- コード修正・テスト4件・§19.1/§19.4 Clineレビューはすべて完了（`issue_backlog.md` BL-330節、
  `decision_log.md` D-283参照）。
- 1917の実データ是正は、DB前方修正案（3d60bdポインタ修正・9e5eac supersede・task_4_1行復元、
  run以後resume不可）と、checkpoint巻き戻し案（BL-174の`--checkpoint-id`、step=424・
  checkpoint_id=`1f1a52a2-e16e-64b9-81a8-20cabb45f620`・19:53:20が破損直前の最終クリーン点、
  ただしtask_4_2のレビュー〜承認〜task_4_5_1指示がすべてやり直しになる）の2案を提示したが、
  ユーザーが「BL-331でタスクのDAG化をするので、このrunの修正はこれ以上不要」と判断し、
  どちらも実施せず見送り。run_id=1787890406-1e73a89dは破損したままPAUSE状態で凍結される。
