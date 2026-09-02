# BL-190: ラン途中の計画再構成後、current_task_id/current_phaseが不整合になる問題への対処 基本設計

## Context

`log/2026-08-07/2355`のレビュー中に発見した挙動。task_plan_reviewerが計画へ8件のmajor/medium
指摘を出し、task_plannerが計画全体を再構成した（`phase_7`を`phase_2`の位置へ移動、旧`phase_2`〜
`phase_6`を`phase_3`〜`phase_7`へ繰り下げ、新規`phase_8`を追加）。この直後から
`_get_current_task`（[cela_main.py:5513](../../../../cela_main.py#L5513)）が
`⚠️ current_task_id='task_2_1'がcurrent_phaseのタスク一覧に見つかりません。先頭タスク
'task_1_1'にフォールバックします。`という警告を繰り返し出し（同ログ内で12回）、User AIの
`write_agreement(action_type="UPDATE", task_id="task_2_1")`がBL-146ガードに拒否される事態が
実際に1回発生した（[cela_main.py:7788](../../../../cela_main.py#L7788)付近）。

このケースでは、エラーメッセージが`action_type="SUPERSEDE"`への切り替えを促し、User AIが
それに従って正常に処理を完了した（[cela_main.py:7817](../../../../cela_main.py#L7817)付近）ため、
実害（データ破損）には至らなかった。しかし根本原因は未解消のまま残っており、ユーザーへ報告した
ところ「これは予期していたが対処を考えていなかった。今、その時が来た。対処法を設計して」との
指示を受け、本ドキュメントを作成した。

## 根本原因

`task_planner_node`（[cela_main.py:8755](../../../../cela_main.py#L8755)）は、初回計画・
ラン途中の再構成（`revision_reason`が非空）のいずれの場合も、新しい`phases`配列を確定させた
直後に無条件で以下を実行する：

```python
if phases:
    state["current_phase"] = phases[0]
```

（[cela_main.py:8850-8852](../../../../cela_main.py#L8850-L8852)）

一方、`current_task_id`は「BL-024: `_resolve_task_transition`のみが書き手」という設計原則
（[cela_main.py:9409](../../../../cela_main.py#L9409)のdocstring参照）があり、
`task_planner_node`は`current_task_id`に一切触れない。

その結果、ラン途中の計画再構成で「先頭フェーズの内容」自体が変わる（＝旧`phase_2`の内容が
新`phase_3`へ移動する等）と、以下の不整合が生じる：

- `current_phase`は新`phases[0]`（新しい`phase_1`）に強制的に巻き戻される
- `current_task_id`は直前の値（例: `task_2_1`）のまま変わらない
- しかし`task_2_1`というtask_id文字列自体は新計画にも存在する（`task_plan_reviewer`が
  修正した計画は、既存task_idの文言・番号を極力保持したまま内容を修正する傾向があり、
  「どのphaseに属するか」だけが変わっている）
- `_get_current_task`は`current_phase.get("tasks", [])`の中だけを線形探索するため、
  `task_2_1`が実際には新しい`phase_3`配下に移動しているのに気づけず、フォールバックし続ける

これは、BL-176/BL-181/BL-183が対処した「既存プラン内でのタスク遷移ブロック」の問題とは
**別種**の問題である。BL-176/181/183は「同じ計画内で、承認されていない/未解決issueが残った
状態で次タスクへ進もうとする」ケースを扱うが、本件は「計画そのものが再構成され、フェーズの
構造・並び順が変わった」ケースであり、`_resolve_task_transition`の関与しない
`task_planner_node`側でのみ発生する。

## 影響範囲の分類

ラン途中の計画再構成（`revision_reason`が非空で`task_planner_node`が発火するケース）を、
新旧`phases`の差分パターンで分類すると3通りある：

1. **加算のみ**（BL-145/BL-186の典型パターン）：既存phase・taskは一切変更されず、新規phase
   （例: `phase_7`）が追加されるだけ。この場合、`current_task_id`が属するphaseの内容・
   phase_idともに変化しないため、`phases[0]`へのリセットは実質的に無害（元々`phase_1`が
   `current_phase`だった場合は一致する）。ただし`current_task_id`が`phase_1`以外
   （例: `phase_2`）のタスクを指していた場合は、加算のみのケースでも既に同じバグが起きうる。
2. **構造再編**（本件で実際に踏んだパターン）：task_plan_reviewerの指摘を受けてtask_planner
   が計画全体を作り直し、phaseの並び順・phase_idが変わるが、進行中のtask_idの文字列自体は
   新計画にも存在する（内容も引き継がれている）。
3. **真の削除・統合**：進行中のtask_idが新計画のどこにも存在しない（該当タスクが他タスクへ
   吸収された、スコープ自体がなくなった等）。

現状の実装は3パターンすべてで「無条件に`phases[0]`へリセットし、`current_task_id`は放置」
という同一の（誤った）処理をしており、パターン1で偶然当たっていた（`current_phase`が
たまたま`phase_1`だった)ケースだけが問題化していなかった。

## 設計方針

`_resolve_task_transition`が担う「BL-024: current_phase/current_task_idの唯一の書き手」
という原則は尊重しつつ、`task_planner_node`が新しい`phases`を確定させた**直後**に限り、
新`phases`全体を線形探索して`current_task_id`の実在場所を再解決する専用ヘルパーを追加する。
これは「唯一の書き手」原則への違反ではなく、`task_planner_node`が新しい`phases`配列という
外部入力を確定させたタイミングでの、その配列に対する`current_phase`の整合性再計算であり、
`_resolve_task_transition`が扱う「LLMの遷移意図から`current_task_id`を更新する」処理とは
別の関心事として整理する。

### 新規ヘルパー: `_reconcile_current_phase_after_replan`

`cela_main.py`内、`_get_current_task`のすぐ後ろに追加する。

```python
def _reconcile_current_phase_after_replan(state: LineageState, phases: list[dict]) -> None:
    """[BL-190] task_planner_nodeが新しいphases配列を確定させた直後に呼ぶ。
    current_task_id（BL-024の唯一の書き手は_resolve_task_transitionだが、値そのものは
    ここでは変更せず参照のみ）が新phases内のどこに属するかを再探索し、current_phaseを
    そのtask_idを含むphaseへ合わせる。

    [CONSTRAINT] 従来はcurrent_phaseを無条件にphases[0]へリセットしていたため、ラン途中の
    計画再構成でフェーズの並び順・phase_idが変わると（BL-186の加算のみのケースでは無害だが、
    task_plan_reviewer指摘によるフェーズ全体の再編では実際に発生した）、current_task_idが
    指すtaskが新phases[0]の中に存在せず、_get_current_taskが毎ターンフォールバック警告を出し、
    BL-146ガードが正当なwrite_agreement(UPDATE)まで拒否する事故があった
    （log/2026-08-07/2355で実見、SUPERSEDEへの切り替えで実害は回避されたが根本原因は未解消）。
    """
    current_task_id = state.get("current_task_id", "")
    if not current_task_id:
        # 初回計画（is_initial）、またはまだ一度もタスクに着手していない場合。
        # 従来通りphases[0]を採用する。
        state["current_phase"] = phases[0] if phases else {}
        return

    for phase in phases:
        for t in phase.get("tasks", []):
            if t.get("task_id") == current_task_id:
                if phase.get("phase_id") != state.get("current_phase", {}).get("phase_id"):
                    print(
                        f"  📍 [BL-190] current_task_id='{current_task_id}'の追跡のため、"
                        f"current_phaseを新phase_id='{phase.get('phase_id')}'へ更新しました"
                        f"（計画再構成によるフェーズ位置変更に追随）。"
                    )
                state["current_phase"] = phase
                return

    # current_task_idが新phasesのどこにも存在しない（真の削除・統合パターン）。
    # phases[0]へフォールバックし、current_task_idもクリアして_get_current_taskの
    # フォールバック警告が毎ターン出続ける状態を防ぐ。次のUser AIターンへ一度だけ
    # 通知し、新計画のどのタスクを引き継ぐべきかLLM自身に確認させる。
    print(
        f"  ⚠️ [BL-190] current_task_id='{current_task_id}'は計画再構成後の新しい計画に"
        f"存在しません（supersede済み）。current_phaseを先頭フェーズへ戻し、"
        f"current_task_idをクリアします。"
    )
    state["current_phase"] = phases[0] if phases else {}
    state["current_task_id"] = ""
    state["task_reassigned_after_replan_notice"] = (
        f"[BL-190] 直前まで進行していたタスク'{current_task_id}'は、直前の計画再構成により"
        "廃止・統合されました。新しい計画（phases）を確認し、対応する新タスクへ改めて着手して"
        "ください。"
    )
```

`task_planner_node`側の呼び出し箇所（[cela_main.py:8850-8852](../../../../cela_main.py#L8850-L8852)）を、

```python
if phases:
    state["current_phase"] = phases[0]
    print(f"  📍 [task_planner] current_phaseをphase_id={phases[0].get('phase_id')}に設定しました。")
```

から

```python
if phases:
    _reconcile_current_phase_after_replan(state, phases)
    print(f"  📍 [task_planner] current_phaseをphase_id={state['current_phase'].get('phase_id')}に設定しました。")
```

へ変更する。

### one-shot通知の配線

新規`LineageState`フィールド`task_reassigned_after_replan_notice: str`を追加する
（[cela_main.py:5187](../../../../cela_main.py#L5187)付近、`task_transition_blocked_unapproved_task_id`
の直後）。

`_build_task_transition_blocked_notice`（[cela_main.py:2954](../../../../cela_main.py#L2954)）は
既に「複数のone-shot通知フラグを順に確認し、最初に見つかったものを消費してテキストを返す」
という構造になっている（`task_transition_blocked_issue_topics`→
`task_transition_blocked_unapproved_task_id`の2段）。これに3段目として本件を追加し、
新しい関数を作らず・新しい呼び出し箇所も増やさずに済ませる（既存の2箇所、
[cela_main.py:8047](../../../../cela_main.py#L8047)と
[cela_main.py:8389](../../../../cela_main.py#L8389)、で自動的に拾われる）：

```python
    reassigned_notice = state.get("task_reassigned_after_replan_notice")
    if reassigned_notice:
        state["task_reassigned_after_replan_notice"] = ""
        print(f"  📣 [BL-190] タスク再割当通知をLLMプロンプトへ注入します。")
        return f"\n【🛑 {reassigned_notice}】\n"

    return ""
```

## 各パターンでの挙動確認（設計の妥当性）

- **パターン1（加算のみ、BL-145/BL-186）**：`current_task_id`が指すtaskは新旧で完全に
  同一のphaseオブジェクト（内容不変）に属し続けるため、ヘルパーは同じphaseを見つけて
  `current_phase`を上書きする（内容は変わらないが、phase_id一致のため通知ログも出ない）。
  従来との差分なし、非退行。
- **パターン2（構造再編、本件のバグ）**：ヘルパーが新しいphase_id配下から`task_2_1`を
  発見し、`current_phase`をそちらへ追随させる。`_get_current_task`のフォールバック警告が
  消え、BL-146ガードも正しく現在タスクとして認識するため、以後の`write_agreement(UPDATE)`
  が正常に通る。
- **パターン3（真の削除・統合）**：`current_task_id`をクリアし、次のUser AIターンへ
  「担当タスクが再編で消えた」ことを明示する。`_get_current_task`は`current_task_id`が
  空文字列になるため、素直に新`phases[0]`の先頭タスクを返す（既存の「未設定時のフォール
  バック」ロジックがそのまま使える、[cela_main.py:5519-5525](../../../../cela_main.py#L5519-L5525)）。
  ここで初めてUser AI側がLLM判断で「新計画のどのタスクを次に進めるべきか」を明示的に
  指示し直す必要があり、これは意図的な設計（機械的にどのタスクへ差し替えるべきかを
  推測させるより、LLMに再判断させる方が安全）。

## 実装ファイル

- `cela_main.py`：
  - `_reconcile_current_phase_after_replan`新設（`_get_current_task`の直後）。
  - `task_planner_node`の`if phases:`ブロックを新ヘルパー呼び出しへ変更
    （[cela_main.py:8850-8852](../../../../cela_main.py#L8850-L8852)）。
  - `LineageState`へ`task_reassigned_after_replan_notice: str`フィールド追加
    （[cela_main.py:5187](../../../../cela_main.py#L5187)付近）。
  - `_build_task_transition_blocked_notice`へ3段目のone-shot通知分岐を追加
    （[cela_main.py:2954](../../../../cela_main.py#L2954)）。
  - `run_ai_vs_ai_loop`の初期`LineageState`辞書構築箇所へ`"task_reassigned_after_replan_notice": ""`
    を追加。
- 新規テスト `tests/test_bl190_current_phase_reconcile_after_replan.py`：
  - `_reconcile_current_phase_after_replan`の単体テスト3件（パターン1〜3それぞれ、
    current_phase/current_task_id/通知フィールドの最終状態を検証）。
  - `current_task_id`が空文字列（初回計画）の場合は従来通り`phases[0]`になることの
    非退行確認1件。
  - `task_planner_node`をグラフ経由ではなく直接呼び出す統合テスト1〜2件
    （`state["phases"]`に旧計画、`state["current_task_id"]`にパターン2相当の値をセットし、
    `plan_revision_reason`付きで呼び出した結果、`current_phase`が新phase_idへ追随すること
    を実行時に確認）。
  - `_build_task_transition_blocked_notice`の3段目分岐の単体テスト2件
    （通知テキストが返り一度で消費されること、他の2フラグが優先されること）。
  - 既存のBL-125/145/163/176/181/183/186関連テストが無退行であることを確認。

## 検証方針

1. `python -m py_compile cela_main.py`
2. 新規テストがオフラインで全件通過。
3. 既存の関連テスト（BL-024/087/125/126/145/163/176/181/183/186系）が無改修で通ること。
4. フルオフラインスイート実行、無退行確認。
5. 可能であれば、`log/2026-08-07/2355`相当の状況（task_plan_reviewerによる全体再編）を
   再現するドライランで、`_get_current_task`のフォールバック警告が出なくなることを確認する
   （実ドライランでの効果確認は次回以降でよい）。

## 未決事項（ユーザー確認が必要）

- パターン1の「加算のみ」ケースでも、`current_task_id`が`phase_1`以外を指していた場合は
  今回のヘルパーが自動的に救済する。これは望ましい副次効果だが、念のため明記しておく。
- パターン3（真の削除・統合）で`current_task_id`をクリアした場合、`task_criteria_status`
  等、旧task_idに紐づく他のstateフィールド（達成基準の充足状況など）は今回のスコープでは
  クリアしない。孤立したエントリとして残るが、既存の`task_id`をキーにした辞書検索が
  ヒットしないだけで実害はないと判断した。将来、孤立エントリの掃除が必要になれば別BLとする。
