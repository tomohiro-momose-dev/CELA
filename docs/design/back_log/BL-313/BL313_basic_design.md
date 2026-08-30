# BL-313: 先送り集中タスクにサブタスク分解を検討させる

## Context

task_5_1に`defer_to_task_id`が20件集中している（全て`severity='minor'`/`status='open'`、実DBで
確認済み）。**加えて実DBを再確認したところ、`task_3_2`と`task_5_5`も現在ちょうど閾値の5件で
オーバーロード状態にあり、合計3ターゲット・30issueが同時に集中している。** 既存のBL-233
（`_get_overloaded_defer_targets`、閾値5件、`cela_main.py:5005-5035`）は検知はしているが、
実ログでは123回警告を出すだけで何も是正していなかった。

ユーザーへ「既存のreplanパイプライン（BL-145）を活用する軽量案」を提案し選択されたが、Explore
agentによるBL-145の完全なトレースの結果、**当初の想定は誤りだったと判明した**：

- BL-233の保護効果（`_is_issue_effectively_deferred`）は`_get_escalated_issues()`
  （`status='escalated'`のみ）を経由する2箇所でしか効かない。
- BL-145の停滞判定チェーン（`reflection_node`, `cela_main.py:17375`〜）も**完全に同じ
  `_get_escalated_issues()`が起点**であり、`status='open'`の行はどんな条件でも
  `_formalizable_stale`（`reflection_node`内のローカル変数、17462行目。BL-233の
  docstringが指す「`_formalizable_stale`」という独立関数は実在しない）に到達しない。
- したがって「BL-233の対象をopenへ拡張する」だけでは**BL-145は一切反応しない**——
  task_5_1の20件は全件`status='open'`のため、これまでも今後も自然には拾われない。

一方、BL-145が使っている**土台の配線（`plan_revision_reason`状態フィールド→
`task_planner_node`の再発火ガード→`call_task_planner`の`revision_block`プロンプト注入→
事後の`_mark_issue_planned`による`status='planned'`化）は完全に汎用**で、「なぜ
`plan_revision_reason`が立ったか」を一切問わない（BL-186のゴール改定整合性チェック・
BL-126 Stage Dの本質対話収束も同じ土台を共有する既存の前例）。よって「BL-233拡張」ではなく
「**同じ土台へ新しいトリガー条件（BL-313）を追加する**」のが実際に機能する軽量案である。

**ユーザーによる独立レビュー（別AIツールによるコード・DB突合レビュー）を受け、以下の設計は
その指摘（A〜E、必須修正3件・明記推奨2件）を反映済み。各指摘は実コード再読・実DB再クエリで
裏取りした上で採用した。**

## 設計

### 新規トリガーの挿入位置（レビュー指摘C・厳密化）

`reflection_node`内、BL-145のstagnant判定ブロック全体（`if _stale_escalated:` 開始
17447行目〜終了17489行目、`elif`節17484-17488含む）の**外側**、つまり**17489行の直後・
17490行（`_was_escalation_active = state.get("escalation_active", False)`）の直前**に、
`if _stale_escalated:` と同じ関数本体インデントレベルで追加する。`if _stale_escalated:`の
**内側**に書いてはならない（内側だと滞留escalated issueが同時に存在する時しか評価されず、
BL-313が意図した「open issueの集中のみでも独立に発火する」動作にならない）。

### 新規トリガーのコード（レビュー指摘A・B反映済み）

```python
# [BL-313] 先送りが特定タスクへ集中している場合、サブタスク分解の検討をtask_plannerへ
# 促す。BL-233は検知のみで、BL-145の停滞トリガーはstatus='escalated'限定のため、
# status='open'のminor issueの集中（task_5_1で20件・task_3_2/task_5_5で各5件、
# 2026-08-30時点で確認）には一切反応しなかった。BL-145と同じ土台（plan_revision_reason/
# plan_revision_issue_ids/_mark_issue_planned）を再利用し、新しいトリガー条件だけを
# 追加する。discussion_statusはstagnantへ上書きしない（BL-145と異なり「滞留」ではなく
# 「受け皿の構造的な偏り」を扱うため、facilitation_countの猶予を消費させない）。
if not state.get("plan_revision_reason"):
    _overloaded_targets = _get_overloaded_defer_targets(get_active_conn(), state["run_id"])
    if _overloaded_targets:
        _piled_issues = [
            i for i in (
                _get_open_issues(get_active_conn(), state["run_id"])
                + _get_escalated_issues(get_active_conn(), state["run_id"])
            )
            if i.get("defer_to_task_id") in _overloaded_targets
        ]
        if _piled_issues:
            _by_target: dict[str, list[dict]] = {}
            for i in _piled_issues:
                _by_target.setdefault(i["defer_to_task_id"], []).append(i)
            _reason_lines = [
                f"- task_id={_target}: {len(_items)}件の先送り事項が集中（例: "
                + "、".join(i["topic"] for i in _items[:8])
                + ("…" if len(_items) > 8 else "") + "）"
                for _target, _items in _by_target.items()
            ]
            state["plan_revision_reason"] = (
                "[BL-313] 以下のtask_idへ、他タスクからの先送り事項（defer_to_task_id）が"
                f"{_DEFERRAL_PILEUP_THRESHOLD}件以上集中しています。1つのタスクのまま実行すると"
                "内容過多で実行が破綻するか、重要な検証（感度分析等）が形だけの通過になる"
                "おそれがあります。対象タスクを番号付きサブタスク（例: task_5_1_1,"
                "task_5_1_2, ...）へ分割することを検討してください（本来のacceptance_"
                "criteriaを担うサブタスクと、先送り事項の検証を担うサブタスクを分ける等）。"
                "ただし分割が最善とは限りません——内容を精査した上で、既存タスクへ整理して"
                "統合する判断も可とします:\n" + "\n".join(_reason_lines)
            )
            state["plan_revision_issue_ids"] = [i["id"] for i in _piled_issues]
            print(
                f"  📌 [BL-313] {len(_piled_issues)}件の先送り集中（対象task_id="
                f"{sorted(_by_target.keys())}）をplan_revision_reasonとして"
                f"次回計画再構成に引き継ぎました（issue_ids={state['plan_revision_issue_ids']}）。"
            )
    elif state.get("plan_revision_reason") and _overloaded_targets:
        # 到達しない分岐だが§14.3対策として明示：plan_revision_reasonが既に別要因
        # （BL-145/BL-186/BL-126 Stage D）でセット済みの場合はBL-313を今回スキップし、
        # 次回reflectionで再評価する（BL-145のelint節17484-17488と同じ扱い）。
        pass
```

（`elif`分岐は擬似コードであり、実装時は`if not state.get("plan_revision_reason"):`の
外側で「スキップした」旨のprintを出す形に整理する。§14.3：発火有無をログから機械的に
追跡できることが目的であり、分岐の書き方自体は実装時の裁量とする。）

### 既存インフラの再利用（変更不要）

- `task_planner_node`（`cela_main.py:15780`〜）の`if is_initial or revision_reason:`
  ガードが次ターンで自動的に`call_task_planner`を再発火する。
- `call_task_planner`の`revision_block`（`11406-11424`）が`plan_revision_reason`を
  そのままプロンプトへ注入する（BL-313専用の文言変更は不要、汎用の埋め込み口をそのまま使う）。
- `task_planner_node`の事後処理（`15872-15883`）が`plan_revision_issue_ids`の各IDを
  `_mark_issue_planned`で`status='planned'`へ遷移させる。**`status='planned'`は
  `_get_overloaded_defer_targets`のCOUNTクエリ（`status IN ('open','escalated')`のみ）
  から自然に除外される**ため、再発火の抑止（冪等性）が追加コードなしで成立する。

### 既知の限界（レビュー指摘D・明記のみ、修正はスコープ外）

`_mark_issue_planned`（4918-4953）は`embedded_task_ids[0]`——呼び出し元（15876）が
`sorted({t["task_id"] for p in phases for t in p.get("tasks", [])})`で作る**新計画全体の
アルファベット順先頭task_id**——をplanned化した各issueの新しい`defer_to_task_id`として
書き込む。これはBL-145にも既に存在する挙動だが、BL-313は一度に最大30件をplanned化するため
影響範囲が拡大する。結果として`_build_planned_issue_pin_text`（5253-5257）が「task_id=
（無関係な先頭task_id）に組み込み済み、RESOLVEしてください」とUser AIへ誤誘導し得る。

**この点への「安易な修正」は禁止**：`embedded_task_ids`を空リストにすると`_mark_issue_planned`
がFalseを返しplanned化されず、閾値が下がらないまま毎ラウンド再発火するループになる。本BLの
スコープでは、この限界を設計上の既知事項として受け入れ、実LLM確認（宿題、後述）でpin textの
実際の影響を目視確認するに留める。真の是正（「どのissueがどの新サブタスクに実際に吸収されたか」
をtask_planner自身に対応させる等）は別BLとして切り出す。

### 一回性の限界（明記のみ）

task_plannerが分割を選ばず現状維持を選択した場合でも、対象issueは全てplanned化され、
pileup検知は当該issueに対しては二度と発火しない（`status='planned'`のため）。既存の緩和策
（`_write_issue_impl`のCREATE経由再発検知：`occurrence_count>=2`で機械的に`severity='major'`・
`status='escalated'`へ復帰、4933-4936；`_build_planned_issue_pin_text`がUser AIへRESOLVE
検討を促す）がそのままBL-313にも適用されるため、コード変更なしで再燃の芽は残る。

### 優先順位（明記のみ）

BL-313をBL-145ブロックの直後に置くことで、同一ラウンドで両方の条件が満たされた場合は
BL-145が先に`plan_revision_reason`を確保する（first-write-wins）。エスカレーション済み・
3ラウンド滞留という緊急度の高いBL-145を優先するのは意図的に妥当な順序であり、BL-313は
次ラウンドで再評価される。

### task_id命名の安全性（確認済み）

task_idはコードベース全体で単純な文字列集合一致（`cela_main.py:16664-16672`ほか）で扱われ、
アンダースコア区切りの段数に依存したロジックは存在しない。`task_5_1_1`のような3段のIDは
既存コードに影響しない。

### 副次的な修正：ログ表示の帰属修正（軽微・レビューで行番号訂正済み）

`task_planner_node`の事後処理のうち、`print`が`"[BL-145]"`を決め打ちしている箇所は
**15881・15883の2箇所のみ**（15873/15878/15880/15882はコメント・if文・関数呼び出し行で
print自体ではない）。この事後処理コードは既にBL-186・BL-126 Stage Dとも共有されている
汎用パスであり、BL-313もこれに乗るため、決め打ちラベルを`"[計画再構成]"`のような汎用文言へ
変更する（AGENTS.md 9章decision lineageの精神：どのBLが何を引き起こしたか正確に残す）。
`_mark_issue_planned`内部の`print`（4945-4946、4952）は既に`[DB]`という汎用ラベルのため
変更不要。

## Critical Files

- `cela_main.py`：`reflection_node`（17489行の直後・17490行の前、関数本体レベルへ新規
  トリガー追加）、`task_planner_node`の`print`文2箇所（15881・15883、ラベル汎用化のみ・
  ロジック不変）
- `tests/test_bl313_deferral_pileup_subtask_split_trigger.py`（新規）

## Verification

1. **トリガー条件テスト**：`_get_open_issues`が返すissueの`defer_to_task_id`を同一task_idへ
   5件以上（閾値ちょうど・閾値未満・閾値超過の境界値）設定したDBで検証し、
   `state["plan_revision_reason"]`に`"[BL-313]"`と対象task_idが含まれること、
   `plan_revision_issue_ids`にpiled issueの全IDが入ることを確認する。
2. **複数ターゲット同時発火テスト（レビュー指摘E）**：実DBで確認された実例
   （task_3_2=5件・task_5_1=20件・task_5_5=5件が同時にオーバーロード）を模した状態で、
   3ターゲット・計30件が`_by_target`で正しくグルーピングされ、`plan_revision_reason`に
   3ターゲット全ての行が含まれ、`plan_revision_issue_ids`に30件全てのIDが入ることを確認する。
3. **discussion_statusを変更しないことの確認**：BL-313発火時に`state["discussion_status"]`が
   （BL-145のように）`"stagnant"`へ上書きされないことを確認する。
4. **非発火条件テスト**：閾値未満では発火しないこと、`plan_revision_reason`が既に
   （BL-145等により）設定済みの場合は上書きしないこと（first-write-wins）、スキップ時に
   ログが出ること（§14.3）。
5. **status='planned'による自然な冪等性テスト**：`_mark_issue_planned`適用後、同じissueが
   `_get_overloaded_defer_targets`のCOUNTに含まれなくなり、再度閾値を割ることを確認する
   （§17.1: この動線を担うコードを一時的に無効化すると、テストが正しく失敗することを確認）。
6. `python -m py_compile cela_main.py`
7. 既存のBL-145/BL-233関連テストを再実行し非退行を確認（特にreflection_nodeのstagnant
   判定・plan_revision_reasonのfirst-write-wins挙動）。
8. フルオフラインスイート実行。
9. 実装後、`docs/design/back_log/issue_backlog.md`にBL-313を記載、`decision_log.md`へ
   決定を記録し、**この設計をdocs/design/back_log/BL-313/BL313_basic_design.mdへ
   実装前に保存する**（Plan modeの一時ファイルはセッション終了で失われるため）。
10. **実LLM確認（宿題）**：実際にtask_5_1のようなケースでtask_plannerがどう応答するか
    （素直にサブタスク分割するか、無視して既存タスクへ押し込むか）、また
    `_mark_issue_planned`のdefer_to_task_id上書きによるpin textの誤誘導が実害を
    起こすかは静的テストでは検証できない。次回ドライラン時に目視確認することを
    次回宿題とする。
