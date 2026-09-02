# BL-337: integratorの承認ステータス取りこぼし＋未承認タスクの統合混入を防ぐ設計

## Context

GAIAパイロット完走後、ユーザーが最終統合要件定義書を「内容が中途半端」と指摘し、調査の結果、
`integrator_node`（`cela_main.py:19450`）のDeliverable抽出フィルタが`status == "Approved"`の
文字列完全一致のみで判定しており、CELAが既に持つ承認系ステータス集合
`RESOLVING_DELIVERABLE_STATUSES = {"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}`
（`cela_main.py:8881`）を使っていないことが判明した（AGENTS.md §15.1）。結果、正当に承認された
task_1_2（`Implicitly_Accepted`）が統合対象から漏れた（根本原因1・確定）。

加えて、task_1_3（FINAL ANSWER: 66%を含む最終回答）は通常タスクが経る4段階レビュー
（Stage1〜4、User AIによる承認）を一度も経ないまま`status="Proposed"`のまま統合対象から
完全に漏れていた（根本原因2）。issue_backlog.md記載時点では未確証だったが、本設計の調査で
機構を確認した：

**根本原因2の確定調査**: `route_after_expert_decision`（`cela_main.py:19890`）は、Expertの
ターンをDetectorが監査クリアした直後（`expert_decision_extractor`実行直後）、
`round_count % state["reflection_interval"] == 0`が成立すると、User AIの4段階レビュー
（`generate_user_utterance`経由、Stage1〜4はそこで実行される）を一切経由せず**直接
`reflection`ノードへ分岐する**。`reflection_interval`の既定値は3（`cela_main.py:20763`、Appconfigデフォルト）で、GAIAパイロットのような単一フェーズ・少数タスク構成の
プロジェクトでは、最後のタスクの完了直後に`round_count`がこの値の倍数に一致する確率が
構造的に高い（今回はまさにこれが起きた——ログ9457〜9918行目、Detector監査の直後に
`------ [reflection] が思考中 ------`）。reflection自身のLLM判定（`call_reflection`）も
独立して「目標達成」と判定してしまえば、そのままintegratorへ進み、User AIが一度も見て
いないDeliverableが最終統合の判断材料になる。これは「最後のタスクだから」という特別な
経路ではなく、**個別タスクの4段階承認フローと周期的reflectionという2つの独立した仕組みが
競合し、後者が前者を待たずに完了宣言できてしまう**構造的な穴であり、単一フェーズの短い
プロジェクトほど再現しやすい。

## 設計方針

根本原因2の「なぜtask_1_3がStage3をスキップしたか」という経路（周期的reflectionの
タイミング）そのものを塞ぐのではなく、**実際の被害が発生する場所（integrator）に
完全性ゲートを設ける**方針を採る。理由：
- 周期的reflectionは「定期的な進捗確認」として正当な設計であり、reflectionが`round_count`
  ベースで発火すること自体は変更しない（無闇に触ると他の既存フローに影響しうる）。
- reflection自身のLLM判定（「目標達成」）が誤って早期に完了宣言する経路は、routing条件
  だけでなくreflectionのLLM判断そのものにも依存しており、routing側だけを塞いでも
  reflectionが別の理由で同じ結論に達する可能性が残る。
- 実害が確定的に生じるのは「integratorが未承認のDeliverableを統合対象から静かに除外する
  （またはtask_1_3のように完全に無視する）」瞬間である。ここに一段のチェックを置けば、
  reflection側の判定経路・LLM判断のいずれが原因であっても、実害（不完全な最終文書）を
  確実に防げる。

## 修正1（根本原因1、確定・低リスク）

`integrator_node`のDeliverable抽出フィルタを、既存の単一ソース`RESOLVING_DELIVERABLE_STATUSES`
を使うよう修正する：

```python
deliverables = [a for a in get_agreements_from_db(_conn, _run_id)
                if a["entry_type"] == "Deliverable" and a["status"] in RESOLVING_DELIVERABLE_STATUSES]
```

## 修正2（根本原因2の被害防止、完全性ゲート）

`integrator_node`の冒頭（`deliverables`抽出の前）に、計画上の全タスクが承認済み
（resolvedステータスの）Deliverableを持つかを確認するチェックを追加する。判定には
既存のヘルパー`_find_active_deliverable_agreement(conn, run_id, phase_id, task_id)`
（`cela_main.py:4060`、task_idで一意にDeliverableを引く既存の正規ルート、Superseded以外の
最新版を返す）をそのまま再利用する：

```python
_pending_task_ids = []
_pending_phase_for_task = {}
for _phase in state.get("phases", []):
    _phase_id = _phase.get("phase_id", "")
    for _task in _phase.get("tasks", []):
        _task_id = _task.get("task_id", "")
        if not _task_id:
            # [Cline指摘M-2] _is_task_completed（cela_main.py:8896、BL-214）と同じ規律：
            # 計画上のタスクにtask_idが無いのは計画破損であり、黙ってcontinueせず可視化する
            # （AGENTS.md §13.2）。fail-closedの対象には含めない（正体不明なtask_idを
            # 差し戻し先にできないため）が、警告は必ず出す。
            print(f"  ⚠️ [integrator][BL-337] phase_id='{_phase_id}'に task_id を持たないタスクが"
                  f"あります。計画データの破損の可能性があるため確認してください。")
            continue
        _active = _find_active_deliverable_agreement(_conn, _run_id, _phase_id, _task_id)
        if not _active or _active.get("status") not in RESOLVING_DELIVERABLE_STATUSES:
            _pending_task_ids.append(_task_id)
            _pending_phase_for_task[_task_id] = _phase

# [Cline指摘C-1・最重要] 空でも必ず代入する。LangGraphのstate channelはノード間で値を
# 保持するため、「非空のときだけ書く」実装だと、1回目のゲート発火でセットした値が
# 2回目以降（今度は全タスク解消済み）の呼び出しでも読み取り側（route_after_integrator）に
# 残り続け、解消後も永遠にgenerate_user_utteranceへ差し戻され続けるライブロックになる
# （D-038と同型の教訓）。
state["pending_task_review_task_ids"] = _pending_task_ids

if _pending_task_ids:
    print(f"⚠️ [integrator] 未承認（User AIレビュー未完了）のタスクが残っています: "
          f"{_pending_task_ids}。統合せず、User AIのレビューへ差し戻します。")
    state["ready_for_review"] = False
    # [Cline指摘C-2] 差し戻し後にUser AIがどのタスクをレビューするかを明示的に指定する。
    # 未指定だとcurrent_task_id/current_phaseが指す別タスク（既に承認済みの可能性が高い）を
    # Stage3が再承認するだけになり、ゲートが解消されない。1ターンで1タスクというStage3の
    # 既存設計に合わせ、pending先頭の1件のみを対象にする——複数件が残っている場合は、
    # このタスクが承認されて再びintegratorに到達した次のゲート発火で、残りが順次処理される。
    _first_pending = _pending_task_ids[0]
    state["current_task_id"] = _first_pending
    state["current_phase"] = _pending_phase_for_task[_first_pending]
    # [Cline指摘C-3] 差し戻しサイクルに上限を設ける（reviewer_nodeのreview_count > 3と
    # 同じパターン、cela_main.py:19532/19573）。User AIが繰り返しRejectedを出す等で
    # ゲートが永遠に解消しないケースの安全弁。
    state["pending_task_review_count"] = state.get("pending_task_review_count", 0) + 1
    if state["pending_task_review_count"] > 3:
        print(f"🛑 [integrator][BL-337] 未承認タスクの差し戻し上限(3回)を超えました"
              f"（pending_task_review_count={state['pending_task_review_count']}）。"
              f"state['halt']=Trueで強制停止します。")
        state["halt"] = True
        db_append_decision(make_decision(
            "system", "強制停止(BL-337差し戻し上限超過)",
            f"未承認task_id={_pending_task_ids}の解消が3回の差し戻しでも完了しませんでした。"
        ), _conn, _run_id)
        return state
    db_append_decision(make_decision(
        "integrator", "統合差し戻し(未承認タスク残存・BL-337)",
        f"以下のtask_idはUser AIの承認（Stage1-4）を経ていないため統合を差し戻す: {_pending_task_ids}"
        f"（今回のレビュー対象: {_first_pending}、差し戻し{state['pending_task_review_count']}回目/3回）"
    ), _conn, _run_id)
    return state
else:
    # [Cline指摘C-1の副次発見] ゲート解消時はリトライカウンタもリセットする
    # （次に別のタスクが未承認になった際、カウントを1から数え直すため）。
    state["pending_task_review_count"] = 0
```

既存の`deliverables = [...]`（修正1の行）はこのチェックの**後**に続ける（正常時は
`_pending_task_ids`が空でこのブロックを素通りし、既存の挙動と完全に同じ）。

**[2回目Cline指摘・補強点1]** 本ゲートは「計画に含まれる全タスクは最終的にDeliverableを
産出する」ことを前提とする。計画再構成で削除されたタスクは`removed_task_ids`
（`cela_main.py:17229`付近）としてSupersede記録された上で`state["phases"]`自体から
除外されるため、本ゲートには残らず誤発火しない（確認済み）。ただし将来「タスクを
Deliverable産出なしに完了扱いする」機構が追加された場合、本ゲートはそれを誤って
「未承認」と判定し続け、3回の差し戻し後にhaltする。実装時、この前提をコード上の
コメントとして明記する。

**[2回目Cline指摘・補強点2]** `_find_active_deliverable_agreement`はBL-206修正により
phase_id不一致を警告のみ（照合条件には含めない）とする設計のため、本ゲートが
`_phase_id`（計画由来）と実際のDeliverable行のphase_idが食い違っていても判定は
破綻しない。この暗黙の依存関係を実装時にコメントで明示する。

### 追加修正: `needs_revision_phases`の同型の未クリアバグ（C-1検証中に発見、既存コード）

C-1の検証中、`integrator_node`の**既存の**矛盾検知分岐（`cela_main.py:19500`）に、全く
同じ未クリア問題が既に存在することを発見した：`state["needs_revision_phases"]`は矛盾検知時
（`if result.get("contradictions")`）にのみ代入され、矛盾なし（`else`）の成功分岐では一度も
`[]`へ戻されない。1回目のintegrator呼び出しで矛盾が見つかり`orchestrator`へ差し戻された後、
修正されて2回目の呼び出しで矛盾なしと判定されても、`state["needs_revision_phases"]`は
1回目の値を保持したままのため、`route_after_integrator`は矛盾解消後も`orchestrator`へ
差し戻し続ける（BL-337の新規フィールドと発生機構が同一）。BL-337で発見した以上、
AGENTS.md §13.5「Fix the class, not the instance」に従い、同じ`else`分岐で
`state["needs_revision_phases"] = []`も明示的にリセットする（1行追加、低リスク）。

### ルーティング: `orchestrator`ではなく`generate_user_utterance`へ差し戻す（重要な設計判断）

既存の`route_after_integrator`（`cela_main.py:19936`）には、矛盾検知時に`needs_revision_phases`
を見て`"orchestrator"`へ戻す分岐が既にある。**この既存分岐を completeness ゲートにも
流用しない。** 理由：`orchestrator`は`graph.add_edge("orchestrator", "expert")`で常に
Expertへ直行する（`cela_main.py:19820`付近）。もし未承認タスクの差し戻し先を
`orchestrator`にすると、Expertが**もう一度同じタスクをゼロから書き直す**（User AIは
まだ介在しない）。さらに悪いことに、`orchestrator → expert → expert_detector →
expert_decision_extractor → route_after_expert_decision`という経路は`generate_user_utterance`
（`round_count`をインクリメントする唯一の場所）を経由しないため、`round_count`が
不変のまま再び`route_after_expert_decision`の周期的reflection判定に到達し、**全く同じ
`round_count % reflection_interval == 0`の衝突が再発し、無限ループになりうる**。

正しい差し戻し先は`generate_user_utterance`である。これは既に多数の箇所（
`task_plan_reviewer`・`user_detector`・`expert_detector`のBL-130相談モード・
`expert_decision_extractor`の通常/BL-266経路など、`cela_main.py`内で9箇所以上）から
到達する、汎用的な「User AIのターンを開始する」再入場点として設計されている（新しい
predecessorを追加すること自体は既存パターンと整合）。ここを経由すれば`round_count`が
正しくインクリメントされ、次に周期的reflectionが発火するタイミングも自然にずれるため、
ループを構造的に回避できる。加えて、Expertに無駄な再作業をさせず、既に完成している
（が誰にもレビューされていない）Deliverableへ、本来あるべきUser AIの4段階レビューを
そのまま適用できる。

`route_after_integrator`に新分岐を追加する：

```python
def route_after_integrator(state: LineageState):
    if state.get("pending_task_review_task_ids"):
        print("\n[route_after_integrator]------ !!! BL-337: 未承認タスクが残っているため"
              "generate_user_utteranceへ差し戻します ------\n")
        return "generate_user_utterance"
    if state.get("needs_revision_phases"):
        print("\n[route_after_integrator]------ revisionが必要です ------\n")
        return "orchestrator"
    return "arbiter"

graph.add_conditional_edges(
    "integrator",
    route_after_integrator,
    {"orchestrator": "orchestrator", "arbiter": "arbiter", "generate_user_utterance": "generate_user_utterance"}
)
```

### state配線

- `LineageState`（`cela_main.py:11098`付近、`expert_last_entity_writes`の隣）に
  `pending_task_review_task_ids: list[str]`・`pending_task_review_count: int`を追加
  （`current_task_id`/`current_phase`は既存フィールドを流用、新規追加不要）。
- 初期state辞書（`cela_main.py:20176`付近）に`"pending_task_review_task_ids": []`・
  `"pending_task_review_count": 0`を追加。

### 既知の限界（M-1、Cline指摘・記録のみ・本BLでは対応しない）

完全性ゲートは`_find_active_deliverable_agreement`（Superseded行を明示的にスキップし、
その次の非Superseded行を返す）を使う。一方、既存の`_is_task_completed`
（`cela_main.py:8884`、BL-167）は`entry_type`とtask_idの一致のみで最初に見つかった行を
無条件に採用し、Superseded行をスキップしない。「あるtask_idの最新行がSupersededで、
かつその直後に新しい代替行が一度も書かれていない」という通常はほぼ起こらないケース
（write_agreementの正規経路では旧行のSuperseded化と新行の追加は同一呼び出し内で対になる）
に限り、両者は異なる判定を返しうる（`_is_task_completed`は「未完了」、
`_find_active_deliverable_agreement`はSupersededより古い、既に無効化されたはずの
Approved行を「有効」として返す）。本BLではこの既存の分岐を統合・修正しない
（スコープ外、`_is_task_completed`はBL-167のissue再構築ロジックが依存しており、
影響範囲の検証には別途調査が要る）。将来この既存の相違が実害を起こした場合に備え、
`decision_log.md`に両ヘルパーの所在と挙動差を記録する。

### 設計上のスコープ確認（意図的に変更しない点）

- 修正1で使う`deliverables`抽出自体（`get_agreements_from_db`全件スキャン＋ステータス
  フィルタ）は変更しない。完全性チェック（`_find_active_deliverable_agreement`を
  計画タスクごとに呼ぶ別ループ）とは独立した二段構えにする——`deliverables`を
  completenessチェックの結果から直接組み立て直す案も検討したが、それだと「現在の計画に
  存在しないtask_id（過去の計画再構成で切り離されたタスク等）」に紐づく正当なDeliverable
  が統合対象から漏れる可能性があり、既存の「全DB走査」という網羅性を意図せず狭めてしまう。
  最小変更の原則から、既存の全件走査ロジックはそのまま残す。
- `reflection`自体のLLM判定ロジックや、`route_after_expert_decision`の周期的reflection
  発火条件（`round_count % reflection_interval`）は変更しない——正当な定期監査の仕組みで
  あり、根本原因2への対処は「実害が生じる場所（integrator）で防ぐ」方針に一本化する。

## 未確定事項（要ユーザー判断、AGENTS.md §7: 新規定数）→ 承認済み（2026-09-02、提案通り）

- **差し戻し上限の値**: `reviewer_node`の既存precedent（`review_count > 3`）に合わせ
  **3回**（承認済み）。
- **上限到達時の挙動**: `reviewer_node`と同じ`state["halt"] = True`（hard halt、
  再開には`--resume`が必要、承認済み）。

## テスト方針（§17.1、既存の`route_after_*`テストパターンを踏襲）

`route_after_integrator`・`integrator_node`はいずれも`build_graph`内のネストされた関数/
`integrator_node`はトップレベル関数。`tests/test_bl266_essence_sufficiency_routing.py`が
確立した「`inspect.getsource(cela_main.build_graph)`から対象関数の`def`〜次の`def`（または
`graph.add_conditional_edges(...)`呼び出し）までを文字列スライスして検証する」パターンを
`route_after_integrator`にも適用する。

- `tests/test_bl337_integrator_completeness_gate.py`（新規）:
  1. **修正1の直接検証**: `state["phases"]`を空（完全性ゲートを無関係化）にし、DBに
     `status="Implicitly_Accepted"`のDeliverableのみを持つrunで`integrator_node`を呼び、
     統合対象に含まれること（Deliverable抽出フィルタの検証、実DB使用・`call_integrator`は
     monkeypatchで矛盾なし固定）。**[Cline指摘M-3]** 完全性ゲートが先に発火し統合処理まで
     到達できない事態を避けるため、`state["phases"]`を空にするか全タスクを解消済みにする
     ことを明記。
  2. **完全性ゲートの検証**: `state["phases"]`に2タスクを持つrunで、1つは`Approved`の
     Deliverable、もう1つは`Proposed`のまま（または存在しない）状態にして`integrator_node`
     を呼び、`state["pending_task_review_task_ids"]`に未承認task_idが入り、
     `state["current_task_id"]`/`state["current_phase"]`が未承認タスクを指すこと、
     統合ドキュメントが**生成されない**こと（`save_deliverable_to_file`・**[Cline指摘M-3]**
     `call_integrator`の両方が呼ばれないことをmonkeypatchで確認——ゲートは`call_integrator`
     呼び出しより前にreturnするため）。
  3. **正常系の非退行**: 全タスクが承認済みなら従来通り統合され、
     `state["pending_task_review_task_ids"] == []`・`state["pending_task_review_count"] == 0`
     であること。
  4. **[Cline指摘C-1] ゲート解消後のクリア確認**: 1回目の`integrator_node`呼び出しで
     `pending_task_review_task_ids`が非空になった状態を作った後、DB側を全タスク承認済みに
     変更して2回目の`integrator_node`呼び出しを行い、`state["pending_task_review_task_ids"]`
     が`[]`に戻ること・`pending_task_review_count`が`0`にリセットされること
     （空でも常に代入する実装の直接検証、revertすると失敗する）。
  5. **[Cline指摘C-3] 差し戻し上限の検証**: `pending_task_review_count`を3に初期化した状態で
     未承認タスクありのrunに対し`integrator_node`を呼び、`state["halt"] = True`になること。
  6. **[Cline指摘M-2] 空task_idの可視化確認**: `state["phases"]`にtask_idを持たないタスクを
     含め、`integrator_node`実行時に警告print相当のログが出ること（黙ってスキップされない
     ことの確認、printのcapsys検証または該当コードパスの存在証明）。
  7. **既存`needs_revision_phases`の同型バグ修正の検証**: 1回目の呼び出しで矛盾ありと
     判定させ`needs_revision_phases`を非空にした後、2回目の呼び出しで矛盾なしと判定させ、
     `state["needs_revision_phases"] == []`に戻ることを確認する。
  8. **ルーティング分岐の存在証明**（source-slice、既存BL-266パターン踏襲）:
     `route_after_integrator`の関数本体に`pending_task_review_task_ids`のチェックが
     `needs_revision_phases`のチェックより**前**にあること、対応する
     `graph.add_conditional_edges`の辞書に`"generate_user_utterance": "generate_user_utterance"`
     が含まれること。
  9. **§17.1リバート確認**: 修正1・完全性ゲート・C-1のクリア処理・C-2の
     current_task_id/current_phase設定・C-3の上限処理・ルーティング分岐、それぞれを
     個別にrevertし対応するテストが失敗することを確認した上で復元する。
- `python -m py_compile cela_main.py`
- 既存の`tests/test_bl213_f1_integrator_content_resolution.py`（**[Cline指摘M-3]**
  正しいファイル名）等、integrator関連の既存テストが非退行であることを確認。
- フルオフラインスイート実行。

## Critical Files

- `cela_main.py`:
  - `RESOLVING_DELIVERABLE_STATUSES`定義: `8881`（変更なし、参照するのみ）
  - `_find_active_deliverable_agreement`: `4060`（変更なし、再利用するのみ）
  - `integrator_node`: `19450`（修正1・完全性ゲート追加の本体）
  - `route_after_integrator`・`graph.add_conditional_edges("integrator", ...)`: `19936-19949`
    （新分岐追加）
  - `LineageState`: `11098`付近（フィールド追加）
  - 初期state辞書: `20176`付近（フィールド追加）
- `tests/test_bl337_integrator_completeness_gate.py`（新規）
- `docs/design/back_log/BL-337/BL337_basic_design.md`（本ファイル）
- `docs/design/back_log/issue_backlog.md`（BL-337節を`open`→実装完了の記録に更新）

## 独立レビュー（AGENTS.md §19.1、Cline CLI・glm-5.3-flash・2026-09-02、2回実施）

1回目レビューで実装前に必須の指摘3件（C-1: state未クリアによるライブロック、C-2:
current_task_id未指定によるレビュー対象タスクの取り違え、C-3: 差し戻しサイクルの上限欠如）
と推奨改善3件（M-1: `_is_task_completed`との判定差異、M-2: 空task_idの黙殺、M-3: テスト
設計の補正）を検出し、全件を実コードで再現確認の上、本設計へ反映済み。C-1の検証過程で、
既存コードの`needs_revision_phases`にも同型の未クリアバグが実在することを独立に発見し、
§13.5「Fix the class, not the instance」に従い同時修正することとした。2回目レビュー
（反映後の再検証）では軽微な補強点2件（前提の明記、BL-206フェイルセーフへの依存の明示）
のみで、両方とも本設計へ反映済み。「承認推奨（条件付き・軽微な補強点2件）」との評価。

## 実装後diffレビュー（AGENTS.md §19.4、Cline CLI・glm-5.3-flash・2026-09-02）

実装後の差分レビューで**重大な配線バグを1件発見・即日修正**：`route_after_integrator`が
`state.get("halt")`を一切チェックしておらず、差し戻し上限超過時にintegrator_nodeが
`state["halt"]=True`を設定してもpending_task_review_task_idsが非空のままのため、
`route_after_integrator`は先に`pending_task_review_task_ids`の条件に一致し
`"generate_user_utterance"`を返してしまい、実際にはhaltノードへ到達しない
fail-open（ログ上は「🛑 強制停止します」と出るのに実際には差し戻しが続く）だった。
この欠陥はC-3の安全弁を実装した本diffが新規に持ち込んだもので、他の`route_after_*`
関数（`route_after_user_decision`等）が先頭で`if state.get("halt"): return "halt"`を
見る既存規約を、`route_after_integrator`へ移植する際に見落としていた。修正は
`route_after_integrator`の先頭にhaltチェックを追加し、`graph.add_conditional_edges`の
マップへ`"halt": "halt"`を追加（`tests/test_bl337_integrator_completeness_gate.py::
test_route_after_integrator_checks_halt_before_pending`で検証、§17.1リバート確認済み）。

その他、要確認事項として2点（ドライランでの観察を推奨、実装は妥当と判断）：
① 差し戻し先（`generate_user_utterance`）が実際にpending先頭タスクのStage1-4レビューを
トリガーするかは、User AI側のターゲット選択ロジックに依存しており静的検証の範囲外——
初回ライブドライランで「差し戻し→承認→ゲート解消」の一連が回ることをログで確認する。
② 「計画上の全タスクは最終的にDeliverableを産出する」前提が崩れる変更が将来入った場合、
本ゲートは3回差し戻し後にhaltする（既に設計書に明記済みの限界）。

その他の主要な主張（BL-336実装の非退行確認含む）はすべて実コードと照合済みで問題なし。
新規3ファイル計27テスト全パス。

## 実装後の手順

- ~~AGENTS.md §19.4（diff-based独立レビュー）を実施し、指摘を実コードで検証の上反映。~~ 完了
- `issue_backlog.md`のBL-337節を更新。完了
