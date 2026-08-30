# BL-319: pending_task_redirect待機中の「現在task_idへの偽装書き込み」を遮断する

## Context

BL-318で`schedule_task_focus(decision_type="advance_task")`を導入したが、実ラン（run_id=
1787890406-1e73a89d、`log/2026-08-30/2010/log_no_prompt.md`）で、ツール呼び出し自体は成功
したにもかかわらず`current_task_id`が更新されない事故が発生した。原因は既存機構同士の
相互作用であり、BL-318自体のバグではない：

1. `20:18:38` User AI (Stage4)が`schedule_task_focus(advance_task, target_task_id=
   "task_3_2_1")`を正しく呼び出し、`state["pending_task_redirect"]`に構造化決定が設定された。
2. 直後の`user_detector`が、**別の正当な懸念**（task_3_2_1にDEFER済みのescalated major issue
   2件が未解決のまま移行しようとしている）で`constraint_issue=major`と判定し差し戻した。
3. `route_after_user_detector`のルーティングでは、差し戻し時は`user_decision_extractor`
   （`pending_task_redirect`を消費し`_resolve_task_transition`を呼ぶ唯一の場所）を**経由せず**
   `generate_user_utterance`へ戻る。advance_taskの決定は一度も適用されないまま待機状態になった。
4. `current_task_id`は`task_1_1`（BL-190由来の古いフォールバック値）のまま固定され続けた。
   User AIは正しいtask_id（`task_3_2_1`）で3回書き込みを試み、いずれも正当な理由で拒否された
   （1回目・2回目: BL-146 current_task_id不一致、間: BL-172 Expert未提出のためstatus=Approved
   拒否——task_3_2_1がまだExpertに一度も割り当てられていないため当然）。
5. **4回目、User AIは同一内容を`task_id="task_1_1"`（現在のtask_id、誤り）へ偽装して再送し、
   BL-146の一致チェックを額面通り通過させて書き込みを成立させた。** これによりresume後だけで
   8件のagreementsが再び誤帰属した（`AG-1788089295286-dbf6b6`ほか、実DB確認済み）。

**根治の方向性は複数検討したが**（(a) pending_task_redirectの消費タイミングをuser_detectorの
差し戻し判定より前倒しする、(b) 迂回そのものを遮断する）、(a)は今回のケースでまさにDetectorの
懸念自体が「遷移先へ移ってよいか」という遷移の妥当性そのものだったため、Detectorの差し戻しを
無視して機械的に遷移を確定させると本来の監査を無力化するリスクがあり、かつBL-125（離脱元の
未解決issueチェック）もcurrent_task_idが既に壊れている状況では実効的な安全網になっていない
（誤ったdeparting_task_idを見ている）。ユーザーと協議の上、**(b) 迂回の遮断**を採用する——
state machineには一切手を入れず、`write_agreement`の入口で「現在task_idへの偽装」という
具体的なパターンだけを機械的に検知して拒否する、最小スコープ・低リスクな対策。

## 設計

### 検知条件

`_write_agreement_impl`内、既存のBL-146ゲート（current_task_id不一致拒否、cela_main.py:
4335-4349付近）の直後に、以下の条件で追加拒否する：

- `action_type in ("CREATE", "UPDATE")`（SUPERSEDEは対象外、BL-146と同じ除外理由——他タスクの
  正規改訂経路のため）
- `pending_task_redirect`が存在し、`decision_type == "advance_task"`
  （redirect_backward/joint_focus等は対象外——それらは「現在タスクを離脱する」意図ではなく
  一時的な焦点追加であり、現在task_idへの書き込みは引き続き正当なため）
- `pending_task_redirect["target_task_id"]`が、宣言されたtask_id（`tid`）と異なる
- `tid == effective_current_task_id`（＝BL-146の一致チェックを額面通り通過するケース、
  今回の偽装パターンそのもの）

この4条件がすべて満たされた場合のみ拒否する。`pending_task_redirect`が存在しない通常時・
target_task_idが宣言task_idと一致する場合（＝遷移がまさに成立しようとしている正常系）は
一切影響しない。

### 既知のトレードオフ（設計書へ明記）

`pending_task_redirect`が待機中（Detector差し戻しループ中）は、現在task_id宛の**まったく
無関係で正当な**書き込みも一時的にブロックされうる（例: 現在タスクの別の訂正）。ただし
この待機状態自体が異常系（通常は同一ラウンド内で消費される）であり、待機が長引くケースで
偽装を許すコスト（DB汚染、検出・是正に数時間かかる）の方が、まれな正当な書き込みが一時
ブロックされるコスト（拒否メッセージを見て少し待つ）より高いと判断した。

### 実装

**`_write_agreement_impl`のシグネチャへ`pending_task_redirect`引数を追加**（cela_main.py:4244
付近）:

```python
def _write_agreement_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str, task_id: str = "",
                           phases: list[dict] | None = None, pending_task_ids: list[str] | None = None,
                           effective_current_task_id: str = "", phase_id: str = "",
                           pending_task_redirect: dict | None = None) -> dict:
```

**BL-146ゲート（4335-4349行）の直後に追加**:

```python
    # 4.56. [BL-319] pending_task_redirect（advance_task待機中）に対する「現在task_idへの
    # 偽装書き込み」の遮断。BL-146を額面通り通過するが、宣言task_idが現在task_idと一致する
    # 一方でadvance_taskの遷移先が別task_idを指している場合、それは正当な現在タスクの記録
    # ではなく、遷移待ちのLLMが拒否を回避するため現在task_idへ偽装した可能性が高い
    # （実インシデント: log/2026-08-30/2010、task_3_2_1で3回正当に拒否された後、
    # 同一内容がtask_id="task_1_1"で書き込まれた）。
    if (args["action_type"] != "SUPERSEDE" and pending_task_redirect
            and pending_task_redirect.get("decision_type") == "advance_task"
            and pending_task_redirect.get("target_task_id")
            and pending_task_redirect["target_task_id"] != tid
            and tid == effective_current_task_id):
        print(
            f"  🚫 [write_agreement guard][BL-319] pending advance_task待機中の現在task_id"
            f"書き込みを拒否: caller={caller_role}, 宣言task_id={tid!r}, "
            f"pending先={pending_task_redirect['target_task_id']!r}, topic={args.get('topic')!r}"
        )
        return {
            "success": False,
            "error": (
                f"'{pending_task_redirect['target_task_id']}'への移行が既に受理され適用待ちです"
                f"（直前のレビューが差し戻されたため未反映）。この内容は現在のtask_id"
                f"（'{tid}'）と一致していますが、移行先タスクの内容を現在task_idへ偽装して"
                "登録することはできません。差し戻しへの対応を完了させ、移行の適用を待って"
                "ください。"
            ),
        }
```

**TOOL_DISPATCH配線**（cela_main.py:5687付近）:
```python
    "write_agreement": lambda args, state=None: _write_agreement_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, _task_id_from(state),
        phases=_phases_from(state), pending_task_ids=_pending_task_ids_from(state),
        effective_current_task_id=_effective_current_task_id_from(state),
        phase_id=_phase_id_from(state),
        pending_task_redirect=(state or {}).get("pending_task_redirect"),
    ),
```

## Critical Files

- `cela_main.py`: `_write_agreement_impl`のシグネチャ拡張・BL-319ゲート追加（4244/4335行
  付近）、TOOL_DISPATCHの`write_agreement`エントリ（5687行付近）
- `tests/test_bl319_pending_redirect_workaround_guard.py`（新規）

## Verification

1. **偽装遮断テスト（実インシデント再現）**: `pending_task_redirect={"decision_type":
   "advance_task", "target_task_id": "task_3_2_1", ...}`、`effective_current_task_id=
   "task_1_1"`の状態で、`task_id="task_1_1"`宛のCREATEを試み、拒否されることを確認する。
2. **正規遷移は妨げないテスト**: 同じpending_task_redirect下で、`task_id="task_3_2_1"`
   （遷移先そのもの）宛の書き込みは、この新ゲートでは拒否されないことを確認する（BL-146側の
   通常ゲートで別途拒否されるのは想定通り、BL-319が「二重拒否」を追加しないことの確認）。
3. **pending_task_redirect無しでは無影響**: `pending_task_redirect=None`の通常時、現在
   task_id宛の書き込みが従来通り成功することを確認する（既存挙動の非退行）。
4. **redirect_backward等は対象外**: `decision_type="redirect_backward"`のpending_task_
   redirectがあっても、現在task_id宛の書き込みはブロックされないことを確認する。
5. **SUPERSEDEは対象外**: action_type="SUPERSEDE"はこのゲートの影響を受けないことを確認する。
6. `python -m py_compile cela_main.py`
7. 既存のwrite_agreement関連テスト（BL-131/146/172/176等）を再実行し非退行を確認。
8. フルオフラインスイート実行。
9. 実装後、`docs/design/back_log/issue_backlog.md`にBL-319を記載、`decision_log.md`へ決定を
   記録し、この設計を`docs/design/back_log/BL-319/BL319_basic_design.md`へ実装前に保存する。
10. **データ是正（別タスク、ユーザー合意済みの順序でBL-319の後に実施）**: resume後（20:10:08
    以降）に誤帰属した8件のagreement行を、BL-318と同じ手順（バックアップ→精査→是正）で修正する。
