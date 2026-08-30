# BL-318: schedule_task_focusへ`advance_task`を追加し、通常タスク遷移を構造化ツールで確定させる

## Context

ライブラン（run_id=1787890406-1e73a89d）で、BL-313（issue積み上がりによる自動サブタスク分割）が
task_3_2をtask_3_2_1/task_3_2_2へ分割する再計画を発火させた際、BL-190の「真の削除」分岐が
正しく`current_task_id`をクリアし、1回限りの復帰通知（`task_reassigned_after_replan_notice`）を
User AI Stage4のプロンプトへ注入した。User AIはその直後の発言で実際に後継タスク
（task_3_2_1/task_3_2_2）へ言及したが、**`current_task_id`は3時間以上（13:41:02〜16:56:23時点、
継続中）'task_1_1'（フォールバック値）のまま更新されず**、以後の全write_agreementが
BL-146ガードにより`task_id='task_1_1'`として誤帰属し続けた（実DB確認: 14件の誤帰属行）。

原因を`call_decision_extractor`（cela_main.py:13697-13700）まで追跡した。このプロンプトは
「Userが明示的に『次のタスクに移行する』と指示した場合のみ」`advances_to_task_id`を設定し、
「前のタスクへの言及や単なるレビューは移行に該当しません」と明示的に除外している。BL-190の
復帰通知に応えるUser AIの発言は「計画上はtask_3_2_1→task_3_2_2」のような**説明・レビュー調**に
なりやすく、この除外条件に該当してしまい抽出漏れが起きる。BL-139/BL-211の自然文フォールバック
（抽出済みDirectiveのtask_idからの補完）も、該当するDirectiveが生成されなければ空振りする。

ユーザーとの協議の結果、**decision_extractorの定性判断を置き換えるのではなく、その上位に
確定的な構造化シグナルを追加する**方針を採用する。BL-191の`schedule_task_focus`ツールと
`_resolve_task_transition`の`structured_redirect`優先ロジック（cela_main.py:16637-16648）は
既にこのパターン（構造化決定が自由文脈抽出より優先される）を実装済みであり、同じ枠組みに
新しい`decision_type="advance_task"`を追加するだけで実現できる。decision_extractorの自由文脈
抽出は退行防止のフォールバックとしてそのまま残す（AGENTS.md §16.1: 軽量な追加案を優先）。

本設計は独立レビュー（`docs/design/back_log/BL-318/BL318_review.md`として実装後に保存予定）を
一度受け、指摘済みの問題（下記C-1/I-1/I-2）を反映済み。

## 設計

### 1. ツールスキーマ拡張（`SCHEDULE_TASK_FOCUS_TOOL`, cela_main.py:1101-1142）

- `decision_type`のenumに`"advance_task"`を追加。
- `target_task_id`の説明を「redirect_backward時必須。切替先の過去task_id」から
  「redirect_backward/advance_task時必須。切替先のtask_id（advance_taskは既存Deliverable不要、
  未着手タスクも指定可）」へ更新。
- ツール全体の`description`から「通常の『次タスクへ進む』指示とは別に」の一文と、
  「任意呼び出し（通常通り前進するだけの場合は呼ぶ必要はない）」の一文を除去し、
  `advance_task`を通常の順方向遷移の**標準的な確定記録手段**として明記する（他decision_type
  は従来通り「過去タスクへの手戻り対応が必要な場合のみ」の任意呼び出しのまま）。
  【独立レビュー指摘I-1】Stage4プロンプト側で「必ず呼んでください」と案内しながらツール
  descriptionが「呼ぶ必要はない」と矛盾したままにならないよう、両者の文言を揃える。

### 2. `_schedule_task_focus_tool_impl`（cela_main.py:5511-5580）に新分岐を追加

```python
if decision_type == "advance_task":
    target_task_id = args.get("target_task_id", "")
    target = _find_task_by_id(phases, target_task_id)
    if not target:
        return {"success": False, "error": f"target_task_id '{target_task_id}' は計画に存在しません"}
    # [BL-318][CONSTRAINT][独立レビュー指摘C-1] ここは関数冒頭(5530)の`current_task_id`
    # (=_effective_current_task_id_from(state)、current_phase先頭タスクへのフォールバック
    # 込み)ではなく、生のraw値を使う。BL-190リコンサイル直後はstate["current_task_id"]=""・
    # current_phase=phases[0]であり、_effective_current_task_id_fromはphases[0]の先頭
    # タスク(今回のインシデントで14件の誤帰属を起こした'task_1_1'そのもの)を返してしまう。
    # 実効値をここで使うと、(a)正当な後継タスクへのadvance_taskがフォールバック値と偶然
    # 一致した場合に「現在タスクと同一」と誤って拒否され、(b)scheduling_drafts.primary_task_id
    # にフォールバック値が実際の離脱元として記録される――BL-146/BL-211と同型の誤帰属を
    # このツール自身が再生産することになる。BL-214が_resolve_task_transition側で確立した
    # 「departing_task_idは生の値が正しい」規約をここでも踏襲する。
    _raw_current_task_id = state.get("current_task_id", "") if state else ""
    if target_task_id == _raw_current_task_id:
        return {"success": False, "error": "target_task_idは現在のタスクと同一です"}
    # [独立レビュー指摘M-2] redirect_backward中(task_focus_stack非空)にadvance_taskで
    # current_task_idを動かすと、一時中断中のフォワードタスクとの対応関係が壊れ、
    # _maybe_resume_forward_focusが誤ったタスクの完了判定で自動復帰してしまう。
    # redirect_backward自身の「深さ1固定」ガード(5544-5545)と同じ理由で拒否する。
    if state and state.get("task_focus_stack"):
        return {"success": False, "error": "既に一時中断中のフォーカスがあります。force_resumeで先に解消してからadvance_taskを呼んでください"}
    target_phase_id = _find_phase_id_for_task(phases, target_task_id)
    record_scheduling_decision(conn, run_id, decision_type, _raw_current_task_id, current_phase_id,
                                "", "", reason, caller_role)
    _LAST_SCHEDULING_DECISION = {
        "decision_type": "advance_task", "target_task_id": target_task_id,
        "target_phase_id": target_phase_id, "reason": reason,
    }
    return {"success": True}
```

redirect_backwardと異なり、既存Deliverableの存在チェックは行わない（自由文脈経路と同じく
未着手タスクへの通常遷移を許可するため）。`decision_type`のバリデーション行
（line 5526の`in (...)`タプル）にも`"advance_task"`を追加する。docstring（5513-5519）にも
advance_task分岐の説明を追記する（独立レビュー指摘M-3）。

### 3. `_resolve_task_transition`（cela_main.py:16622-16764）の分岐追加

現状、`structured_redirect`のredirect_backward/force_resumeは早期return、joint_focus/
clear_companionはcurrent_task_idを変更せず後続の自由文脈ロジック（`transition.get(...)`）へ
フォールスルーする。advance_taskは「後続ロジックへ流すが、next_phase_id/next_task_idの
"取得元"だけ構造化値に差し替える」形にする——これによりBL-125（未解決severe issue）・
BL-176（未承認Deliverable departing）・BL-255（未完了depends_on）の3ゲート、task_id正規化
（BL-039）、フェーズ横断探索（BL-210）を**一切複製せず**そのまま再利用できる（AGENTS.md §15.1）。
このゲート部分は既に生の`state.get("current_task_id", "")`をBL-214の規約通り使っており
（16697-16700、16720-16722）、BL-190リコンサイル直後（current_task_id=""）は空文字ゆえ
BL-125/176が自動的にスキップされる設計と確認済み（独立レビューでも検証済み）——advance_task
導入によりこの部分の挙動は変えない。

```python
if structured_redirect and structured_redirect.get("decision_type") == "advance_task":
    next_phase_id = structured_redirect.get("target_phase_id") or None
    next_task_id = structured_redirect.get("target_task_id")
    print(f"  🧭 [BL-318] schedule_task_focus(advance_task)による構造化遷移要求を優先します: "
          f"target_task_id='{next_task_id}'")
else:
    next_phase_id = transition.get("advances_to_phase_id")
    next_task_id = transition.get("advances_to_task_id")
```
（既存の`next_phase_id = transition.get(...)` 2行をこの分岐に置き換える。以降の行は無変更。）
【独立レビュー指摘M-1】advance_task経由でnext_task_idが空になることは
`_schedule_task_focus_tool_impl`側のバリデーションにより実質発生しないはずだが、その前提を
コメントで明記する（万一空で来た場合、既存の`if not next_phase_id and not next_task_id: return`
が無音no-opする現状の挙動は変えない）。

advance_taskがBL-125/176/255いずれかのゲートで拒否された場合も、「4. 通知経路」で新設する
Stage4専用の通知関数が既存の仕組みを再利用してそのまま一度だけ通知を返す。

### 4. BL-190復帰通知：専用消費経路への分離（独立レビュー指摘I-2、Critical相当）

`_build_task_transition_blocked_notice`（cela_main.py:5305-5345）は現在、**2箇所**から
one-shot消費されている：
- `14812`: Stage4（User AI）。`SCHEDULE_TASK_FOCUS_TOOL`を含むツールリストを持つ。
- `15267`: 差し戻し・本質対話・Expert相談応答・終盤・初回ターン用の別プロンプト経路
  （ツールリストは`15251-15254`、schedule_task_focusを**含まない**）。

再計画後の`task_reassigned_after_replan_notice`が偶然15267側のラウンドで先に消費されると、
「schedule_task_focusを呼んでください」という指示がツールを呼べないプロンプトへ注入され、
one-shot通知が無為に失われる（今回のインシデント自体がこのタイミングで起きた可能性がある）。

**対応**: `reassigned_notice`ブロック（5341-5345）を`_build_task_transition_blocked_notice`
から切り出し、専用関数`_build_task_reassigned_notice(state)`とする。呼び出しは**Stage4
（14812付近）のみ**とし、15267側では呼ばない（ツールを持たない経路では消費させず、
one-shotが必ずツール利用可能な場面まで温存されるようにする）。BL-125/176/255の3種の
ブロック通知（`_build_task_transition_blocked_notice`本体に残る）は従来通り両箇所で消費する
（これらはツール呼び出しを要求しない情報提供のみのため、分離不要）。

```python
def _build_task_reassigned_notice(state: LineageState) -> str:
    """[BL-190/BL-318][独立レビュー指摘I-2] task_reassigned_after_replan_noticeの消費を
    _build_task_transition_blocked_noticeから分離。schedule_task_focusツールを持たない
    プロンプト経路（cela_main.py:15267、差し戻し・本質対話等）でone-shotが無為に消費される
    のを防ぐため、ツールが利用可能なStage4呼び出し箇所からのみ呼ぶ。
    """
    reassigned_notice = state.get("task_reassigned_after_replan_notice")
    if not reassigned_notice:
        return ""
    state["task_reassigned_after_replan_notice"] = ""
    print(f"  📣 [BL-190] タスク再割当通知をLLMプロンプトへ注入します。")
    return f"\n【🛑 {reassigned_notice}】\n"
```

新しい通知文言（advance_taskツールの利用を明示）:
```python
state["task_reassigned_after_replan_notice"] = (
    f"[BL-190] 直前まで進行していたタスク'{current_task_id}'は、直前の計画再構成により"
    "廃止・統合されました。新しい計画（phases）を確認し、対応する新タスクへ改めて着手して"
    "ください。schedule_task_focusツールをdecision_type=\"advance_task\", "
    "target_task_id=\"（新タスクのID）\"で呼び、遷移を確実に記録してください（会話文だけでは"
    "遷移が記録されない場合があります）。"
)
```

Stage4のsystem prompt構築部（14812周辺、`{_transition_notice}`挿入箇所付近）に
`{_task_reassigned_notice}`（新関数の戻り値）を追記する。15267側は変更しない
（`_build_task_transition_blocked_notice`からreassigned_noticeブロックを除いた結果、
自動的にこの経路では注入されなくなる）。

### 5. Stage4プロンプトの案内更新（cela_main.py:14889-14891）

```python
f"\n【重要】あなたが使えるツールはthink・schedule_task_focus・read_entityです。"
f"次タスクへの移行を指示する際は、通常の指示文に加えて必ず"
f"schedule_task_focus(decision_type=\"advance_task\", target_task_id=\"...\")も呼び、"
f"遷移を確実に記録してください。過去タスクの手戻りが必要な場合は"
f"redirect_backward/joint_focusを使ってください。{_THINK_TRAILER_SENTENCE}\n"
```

decision_extractorの自由文脈抽出はフォールバックとして無変更のまま残す（advance_taskの
呼び忘れがあっても現状と同じ確率で救済される、退行なし）。

### 既知の限界（スコープ外）

- Expert側のタスク遷移意図表明経路（あれば）は対象外。Stage4（User AI）のみが
  `current_task_id`の実質的な決定者であるため（BL-024/BL-146前提）。
- LLMが新ツール呼び出しを忘れるケースは自由文脈フォールバックに頼るままであり、100%の
  保証にはならない（構造化シグナルは「確定的な代替経路の追加」であり「保証」ではない）。

## Critical Files

- `cela_main.py`: `SCHEDULE_TASK_FOCUS_TOOL`（1101-1142）、`_schedule_task_focus_tool_impl`
  （5511-5580、decision_typeバリデーション行・docstring含む）、`_build_task_transition_
  blocked_notice`からのreassigned_notice分離＋新設`_build_task_reassigned_notice`
  （5305-5345周辺）、`_resolve_task_transition`（16622-16764）、
  `_reconcile_current_phase_after_replan`のnotice文言（10812-10816）、Stage4の
  system_prompt構築部（14812・14889-14891周辺、新関数呼び出し追加）
- `tests/test_bl318_advance_task_structured_transition.py`（新規、既存の
  `test_bl191_task_focus_scheduling.py`・`test_bl176_task_transition_requires_approval.py`・
  `test_bl255_task_transition_dependency_gate.py`の構造を踏襲）

## Verification

1. **正常系**: advance_task(target_task_id=有効な未着手/既着手task_id)で`current_task_id`/
   `current_phase`が正しく更新されることを確認。
2. **存在しないtask_id**: エラーを返し状態変更なしを確認。
3. **現在タスクと同一**: エラーを返すことを確認（生のcurrent_task_idとの比較であることも
   テストで担保する。下記8番と併せて確認）。
4. **BL-125連携**: departing taskに未解決severe issueがある状態でadvance_taskを呼び、
   自由文脈経路と同じく遷移がブロックされ`task_transition_blocked_issue_topics`が設定される
   ことを確認（ゲート再利用の証拠）。
5. **BL-176連携**: departing taskが未承認の状態でブロックされることを確認。
6. **BL-255連携**: target taskのdepends_onが未完了の状態でブロックされることを確認。
7. **優先順位**: `transition.get("advances_to_task_id")`（自由文脈側）とstructured_redirectの
   advance_taskが同時に異なる値を持つ場合、structured_redirect側が優先されることを確認
   （既存`test_structured_redirect_takes_priority_over_freetext_transition`
   〈test_bl191_task_focus_scheduling.py:437〉のミラーとして書ける）。
8. **BL-190再現テスト（C-1の回帰確認込み）**: `_reconcile_current_phase_after_replan`で
   current_task_idがクリアされphases[0]先頭タスクへフォールバックした状態から、
   `schedule_task_focus(decision_type="advance_task", target_task_id="task_3_2_1")`を呼び、
   (a) 正しくcurrent_task_id="task_3_2_1"へ遷移すること、(b) `scheduling_drafts`の
   `primary_task_id`が空文字（フォールバック値ではなく生のraw値）で記録されること、
   (c) target_task_idがたまたまフォールバック値（phases[0]先頭タスク）と一致するケースでも
   誤って「現在タスクと同一」拒否されないこと、を確認する。
9. **task_focus_stack競合（M-2）**: redirect_backward中（task_focus_stack非空）に
   advance_taskを呼ぶとエラーになり状態変更されないことを確認。
10. **通知の経路分離（I-2）**: `task_reassigned_after_replan_notice`が設定された状態で、
    15267側のプロンプト構築関数を呼んでも通知が消費されない（フラグが残ったまま）ことと、
    Stage4側の新関数を呼ぶとone-shotで消費されることの両方を確認。
11. **後方互換**: 既存のredirect_backward/joint_focus/clear_companion/force_resumeの動作・
    `test_bl191_task_focus_scheduling.py`全体、`test_bl190_current_phase_reconcile_after_
    replan.py`（通知文言"廃止・統合"のアサート箇所含む）が無変更で通ることを確認（M-4）。
12. `python -m py_compile cela_main.py`
13. 影響範囲の既存テスト（BL-125/176/190/191/255関連）を再実行し非退行を確認、その後
    フルオフラインスイート実行。
14. 実装後、`docs/design/back_log/issue_backlog.md`にBL-318を記載、`decision_log.md`へ決定
    （追加方式を選んだ理由・decision_extractor温存の判断根拠）を記録し、この設計を
    `docs/design/back_log/BL-318/BL318_basic_design.md`へ、独立レビューの指摘・対応を
    `BL318_review.md`へ、ユーザーとの協議の経緯（decision_extractor置換案→追加案への
    合意に至った対話）を`decision_lineage.md`へそれぞれ実装前〜実装後に保存する
    （AGENTS.md §4.9）。
15. **ライブラン適用時**: 現在停止中のrun_id=1787890406-1e73a89dへ適用する場合、まず既に
    誤帰属した14件のagreement行の是正方針をユーザーと別途合意してから再開する（本BLの
    スコープはコード修正のみで、既存データの是正は含まない）。
