# BL-315: 受け皿（defer_to_task_id）が一度も割り当てられないopen issueをtask_plannerへ引き継ぐ

## Context

ユーザーから「提起レビューが滞っている」旨の指摘を受け実DB（run_id=1787890406-1e73a89d）を調査した
ところ、`status IN ('open','escalated')`のissueが**84件**（escalated/major 4件、open/minor 80件）
残留しており、うち**26件は`defer_to_task_id`が一度も設定されていない**ことを確認した。最古のissue
は2026-08-28 15:36作成（発見時点から約44.5時間未着手）。

**当初、私はこれを「read_issuesがtask_id列（起票元task）でしかフィルタできず、defer_to_task_id
未設定のissueは他タスクのUser AI Stage2から構造的に検索不能」という**検索不可視性**の問題として
説明したが、これは不正確だった。実際には`_build_open_issue_pin_text`（BL-136、cela_main.py:5214）
がstatus='open'の全行をtopic・description込みで毎ターンUser AI Stage2のプロンプト
（`timeline_str`/`stage_history_text`、cela_main.py:15123）へ参考情報として注入しており、
User AIはread_issuesを呼ばなくてもこれらの存在自体は見えている。

**真の原因**はBL-136の意図的な設計：escalated（major）行だけは`_get_forced_escalated_issues_text`
で「今回の発言で必ずRESOLVE/DEFERを呼べ」と強制するが、open（minor）行は「参考情報であり対応を
強制しない」（軽微な懸念を毎ターン強制すると本来のタスク進行を妨げるため、という意図的なトレード
オフ）。この結果、**一度も`defer_to_task_id`を割り当てられなかったopen issueは、誰からも能動的に
拾われない限り無期限に残り続ける**——「見えているのに誰も手を付けない」という状態であり、
BL-233（先送り先の過集中）と同じ「検知はしても是正しない」構造的欠落である。

ユーザーの指示：「先ほどの先送りタスク（BL-313）の様に、先送り不明のタスクが一定件数以上なら、
リフレクター経由でタスクプランナーに送る」——BL-313と全く同じ土台
（`plan_revision_reason`/`plan_revision_issue_ids`/`_mark_issue_planned`/
`task_planner_node`の再発火ガード/`call_task_planner`の`revision_block`注入）を再利用し、
「受け皿が過集中している」（BL-313）ではなく「受け皿が一度も割り当てられていない」ことを
トリガー条件とする、対になる新規BLとして設計する。

**独立レビュー（別AIツール、コード直接突合）を受けた修正**：初版はBL-313の土台をそのまま
流用したが、対象件数が26件（実DB）とBL-145/313の想定より一桁多く、無制限に一括
`plan_revision_issue_ids`へ積むと、task_plannerが実際には拾わなかったissueまで機械的に
`status='planned'`化され「組み込み済み」という偽の状態がUser AIへ表示され続ける問題が
指摘された（コードで裏付け確認済み）。処理件数の上限（古い順バッチ）とBL-145同型の
追跡可能性要求を追加している。

## 設計

### 新規ヘルパー（`_get_undeferred_open_issues`）

BL-313が`_get_open_issues(conn, run_id) + _get_escalated_issues(conn, run_id)`をPython側で
フィルタしているのと同じスタイルで、新規ヘルパーを`_get_open_issues`の直後（cela_main.py:5211
付近）に追加する：

```python
def _get_undeferred_open_issues(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """[BL-315] defer_to_task_idが一度も設定されていないstatus='open'（minor）行を返す。
    escalated行はBL-136の強制RESOLVE/DEFER督促（_get_forced_escalated_issues_text）が
    既に効いているため対象外——open行だけが「見えているのに誰も拾わない」構造的欠落を持つ。
    """
    return [i for i in _get_open_issues(conn, run_id) if not i.get("defer_to_task_id")]
```

escalated行を除外する理由：BL-136が既に強制督促しており（本当に機能しているかはBL-145の
stale判定が別途カバー）、対象を混ぜるとBL-313・BL-145との責務が重複する。

### 新規定数

BL-233/313の`_DEFERRAL_PILEUP_THRESHOLD`（5、「過集中」の閾値）とは意味の異なる別概念
（「受け皿ゼロの累積」の閾値）のため、同じ値5を初期値としつつ独立した定数を新設する。

**[独立レビュー指摘・高1を反映]** 実DBで対象が26件確認されており、`plan_revision_issue_ids`に
無制限に積むと、task_plannerが実際には計画へ組み込んでいないissueまで`_mark_issue_planned`で
一括`status='planned'`化され、`_build_planned_issue_pin_text`が「task_id=Xに**組み込み済み**」
という偽の状態をUser AIへ毎ターン表示し続ける（26行分）。1回のトリガーで処理する件数に上限を
設け、残りは次回reflectionで段階的に処理する：

```python
# [BL-315][AGENTS.md §7 承認待ち] defer_to_task_idが一度も割り当てられないopen issueが
# この件数に達したら、task_plannerへ計画再構成の検討を促す。
_UNDEFERRED_OPEN_ISSUE_THRESHOLD = 5
# [BL-315][AGENTS.md §7 承認待ち][独立レビュー指摘・高1] 1回のトリガーで一括planned化する
# 上限。無制限に積むと、task_plannerが実際には拾わなかったissueまで機械的に「組み込み済み」
# 扱いになり偽の状態をUser AIへ表示し続けるため、古い順（_get_open_issuesのORDER BY rowid、
# BL-215）に上限件数だけを対象とし、残りは次回reflectionで再評価する。
_UNDEFERRED_OPEN_ISSUE_BATCH_CAP = 10
```

### `reflection_node`への新規トリガー追加

BL-313ブロックの直後（cela_main.py:17546、`_was_escalation_active = ...`の直前）に、同じ
関数本体インデントレベルで追加する。BL-145→BL-313→BL-315の順で発火し、いずれも
`plan_revision_reason`未設定の場合のみ発火する（first-write-wins、優先順位は既存の並び順が
そのまま反映される）：

```python
# [BL-315] 受け皿（defer_to_task_id）が一度も割り当てられないopen issueが溜まっている場合、
# task_plannerへ計画再構成の検討を促す。BL-136の強制督促（_get_forced_escalated_issues_text）
# はstatus='escalated'限定であり、open（minor）行は_build_open_issue_pin_textで毎ターン
# 参考表示されるのみで対応を強制されない（軽微な懸念を毎ターン強制すると本来のタスク進行を
# 妨げるという意図的なトレードオフ）。そのため受け皿が一度も割り当てられなかったopen issueは
# 誰からも能動的にクローズされず無期限に残り続ける（実DBで26件確認、最古は2026-08-28 15:36
# から約44.5時間未着手、2026-08-30時点）。BL-313と全く同じ土台（plan_revision_reason/
# plan_revision_issue_ids/_mark_issue_planned）を再利用し、トリガー条件だけをBL-313の
# 「受け皿への過集中」から「受け皿が一度も無い」へ変える。discussion_statusは上書きしない
# （BL-313と同じ理由：facilitation_countの猶予を消費させない）。
if not state.get("plan_revision_reason"):
    _bl315_undeferred = _get_undeferred_open_issues(get_active_conn(), state["run_id"])
    if len(_bl315_undeferred) >= _UNDEFERRED_OPEN_ISSUE_THRESHOLD:
        # [独立レビュー指摘・高1] 古い順（ORDER BY rowid）に上限件数だけを今回処理対象とする。
        # 残りは_get_undeferred_open_issuesのCOUNTに残り続けるため、次回reflectionで
        # 再評価される（段階的な消化、一括の偽planned化を避ける）。
        _bl315_batch = _bl315_undeferred[:_UNDEFERRED_OPEN_ISSUE_BATCH_CAP]
        _bl315_lines = [
            f"- topic={i['topic']}（起票元task_id={i.get('task_id') or '(不明)'}）: {i['description'][:80]}"
            for i in _bl315_batch
        ]
        state["plan_revision_reason"] = (
            f"[BL-315] 受け皿（defer_to_task_id）が一度も割り当てられていないopen issueが"
            f"{len(_bl315_undeferred)}件溜まっています（うち今回は古い順{len(_bl315_batch)}件を"
            "対象とします。残りは次回計画再構成で改めて引き継がれます）。これらは軽微な懸念として"
            "毎ターン参考表示はされていますが、対応が強制されないため誰からも能動的に拾われて"
            "いません。次の計画において、内容を精査した上で、既存タスクのacceptance_criteriaへ"
            "組み込む・専用の受け皿タスクを新設する等、いずれかの形で対応の道筋をつけることを"
            "検討してください（新規タスクである必要はなく、同じタスク内で同時に検討すべき内容なら"
            "そちらへ統合してください。各issue_idにつき最低1つのtask説明・acceptance_criteriaに"
            "対応するtopic文字列を明記し、後から追跡可能にしてください。【重要】ここで計画へ"
            "明示的に組み込まなかったissueも、システム側の記録整理上、機械的に'planned'状態へ"
            "遷移し、便宜上どこかのtask_idが対応予定として記録されます——これは実際の組み込みを"
            "意味しないため、本当に対応が必要な内容は必ず計画へ明示してください）:\n"
            + "\n".join(_bl315_lines)
        )
        state["plan_revision_issue_ids"] = [i["id"] for i in _bl315_batch]
        print(
            f"  📌 [BL-315] 受け皿未割り当てのopen issue{len(_bl315_undeferred)}件中{len(_bl315_batch)}件を"
            f"plan_revision_reasonとして次回計画再構成に引き継ぎました"
            f"（issue_ids={state['plan_revision_issue_ids']}）。"
        )
elif len(_get_undeferred_open_issues(get_active_conn(), state["run_id"])) >= _UNDEFERRED_OPEN_ISSUE_THRESHOLD:
    # [BL-315][§14.3] plan_revision_reasonが既に別要因（BL-145/BL-313等）でセット済みのため
    # 今回はスキップし、発火有無をログから追跡できるようにする（次回reflectionで再評価）。
    print(
        "  ⚠️ [BL-315] 受け皿未割り当てのopen issue集中を検知しましたが、plan_revision_reasonが"
        "既に別要因でセット済みのため今回はスキップします（次回reflectionで再評価）。"
    )
```

### スコープ外（独立レビュー指摘・中3、設計書への明記のみ）

`_get_undeferred_open_issues`は`defer_to_task_id`の**列の有無**のみを見る（ユーザー指示
「一度も割り当てられない」の字義通りのスコープ）。しかし`_is_issue_effectively_deferred`
（BL-194、cela_main.py:5038）が指摘する通り、列の有無＝実効的な受け皿ありとは限らない
（自己先送り・受け皿タスクが完了済みで失効、等）。したがって、**defer_to_task_idは設定されて
いるが実効的には受け皿が失効しているopen issue**は本BLの対象外のまま残る。これはユーザーが
今回指示したスコープの外であり、BL-315では対応しない。後続の改善候補として
`issue_backlog.md`に短いメモ（BL-316候補: 「受け皿失効open issueの検知」）を残す。

### 既存インフラの再利用（変更不要、BL-313と同一）

- `task_planner_node`の`if is_initial or revision_reason:`ガードが次ターンで自動的に
  `call_task_planner`を再発火し、`revision_block`が`plan_revision_reason`をそのまま注入する。
- 事後処理の`_mark_issue_planned`が`plan_revision_issue_ids`の各issueを`status='planned'`へ
  遷移させ、`defer_to_task_id`を新計画の先頭task_idへ設定する。これにより：
  - `_get_undeferred_open_issues`のCOUNTから自然に除外される（`defer_to_task_id`が付くため）
    → 再発火の抑止（冪等性）が追加コードなしで成立する（BL-313と同型）。
  - 以後は`_build_planned_issue_pin_text`（BL-145）経由でUser AIへ「対応予定task_idあり、
    本当に解決したらRESOLVEしてください」という参考表示に切り替わる——「見えているが誰も拾わない」
    状態から「対応予定はついたが未検証」という、既存の枯れた状態遷移に合流する。
- task_planner自身が個々のissueを解決する必要はない。計画へ反映するかどうかの判断は委ねつつ、
  ブックキーピング（planned化・defer_to_task_id付与）は機械的に完了する——BL-313と同じ設計思想。

### 優先順位・相互排他性

- BL-145（stale escalated）→ BL-313（受け皿への過集中）→ BL-315（受け皿ゼロ）の順で評価され、
  いずれもfirst-write-winsで`plan_revision_reason`を確保する。
- BL-313とBL-315は対象issueが構造的に排他（BL-313は`defer_to_task_id`が設定済みかつ過集中
  ターゲットに属する行、BL-315は`defer_to_task_id`が未設定の行）であり、二重処理は起きない。

## Critical Files

- `cela_main.py`：`_get_open_issues`直後への新規ヘルパー追加（5211行付近）、BL-233の定数定義
  近辺への新規定数追加（5005行付近）、`reflection_node`のBL-313ブロック直後への新規トリガー
  追加（17546行付近）
- `tests/test_bl315_undeferred_issue_backlog_trigger.py`（新規）

## Verification

1. **トリガー条件テスト**：`defer_to_task_id`未設定のopen issueを閾値ちょうど・閾値未満・
   閾値超過の境界値で作成し、`state["plan_revision_reason"]`に`"[BL-315]"`と対象topicが
   含まれること、`plan_revision_issue_ids`に該当issueのIDが入ることを確認する。
2. **除外条件テスト**：(a) escalated行はdefer_to_task_id未設定でもカウントされないこと、
   (b) defer_to_task_idが設定済み（過集中でなくても）のopen行はカウントされないことを確認する。
3. **`''`明示テスト【独立レビュー指摘・中4】**：DB既定値が`None`ではなく`''`
   （cela_main.py:4903/4666、CREATE時の明示的な空文字格納）であることを踏まえ、
   `not i.get("defer_to_task_id")`が`''`行を正しくカウントすることを個別assertする。
4. **バッチ上限テスト【独立レビュー指摘・高1】**：`_UNDEFERRED_OPEN_ISSUE_BATCH_CAP`（10）を
   超える件数（例: 26件相当）を作成した場合、`plan_revision_issue_ids`が上限件数のみを含み
   （古い順＝`rowid`順であること）、reason文言に総数と「今回は古い順N件」の両方が含まれる
   ことを確認する。
5. **discussion_statusを変更しないことの確認**。
6. **優先順位テスト**：BL-145/BL-313が同一ラウンドで先に`plan_revision_reason`を確保している
   場合、BL-315はスキップしログを出すこと（§14.3）。BL-313とBL-315が同時に条件を満たす場合、
   コード順序通りBL-313が勝つことを確認する。
7. **冪等性テスト**：`_mark_issue_planned`適用後、対象issue（バッチ処理分）が
   `_get_undeferred_open_issues`のCOUNTから自然に外れ、残り（バッチ外）は依然カウントされる
   ことを確認する（§17.1: 動線コードを無効化するとテストが正しく失敗することを確認）。
   あわせて`_build_planned_issue_pin_text`の行数が対象件数（バッチ上限以下）に収まることを
   確認する【独立レビュー指摘・中4】。
8. `python -m py_compile cela_main.py`
9. 既存のBL-145/BL-233/BL-313関連テストを再実行し非退行を確認。
10. フルオフラインスイート実行。
11. 実装後、`docs/design/back_log/issue_backlog.md`にBL-315を記載（BL-316候補メモも併記）、
    `decision_log.md`へ決定を記録し、この設計を
    `docs/design/back_log/BL-315/BL315_basic_design.md`へ実装前に保存する。
12. **ライブラン適用**：現在Turn 8進行中のrun_id=1787890406-1e73a89dへ適用する場合、前回
    （BL-314のweb_search上限緩和）と同様に、ノードの継ぎ目（役割切り替え直後・ツール呼び出し前）
    を見計らって一時停止してから`--resume`する。
13. **実LLM確認（宿題）**：task_plannerが実際にどう応答するか（専用の受け皿タスクを新設するか、
    既存タスクへ振り分けるか、無視してバッチ分がplanned化だけ機械的に進むか）は静的テストでは
    検証できないため、次回reflection到達時の目視確認を宿題とする。
