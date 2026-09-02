# BL-317: agreementsコンテキストを「現在タスク関連＋直近N件」へ有限化する

## Context

ユーザー指摘「agreementの内容をプロンプトに積んで提示していて肥大化している」を受け実測したところ、
現在のrun（run_id=1787890406-1e73a89d、現在停止中）で`_build_agreements_context_from_db`が
生成する文字列は**138,547文字（≈77,000トークン）**——DB全517件のうち、実際にプロンプトへ表示
されるのは`entry_type in (Decision, Deliverable)`かつ`status != Superseded`かつ
`entry_type != Directive`の**301件**（`_build_agreements_context`10473-10479行の表示フィルタで
確認、実測値）。これが**毎ターン・全5ノード呼び出し箇所すべて**（call_orchestrator, call_expert,
call_detector, generate_user_utteranceの2箇所）で無条件に丸ごと注入されている。
`get_agreements_from_db`はLIMIT無しの全件取得で、`_build_agreements_context`も件数を一切
間引かない（各行はdecision_what[:150]/reason_why[:100]/evidence[:100]等で個別には短縮されて
いるが、件数自体は無制限）。

対照的に、同じ「決定事項」を扱う`_build_hydrate_context`（**別テーブル`decisions`——ほぼ全
ノードが毎ターン書く軽量な「誰が・何を・なぜ」ログで、`agreements`の`entry_type="Decision"`
行とは無関係の独立したデータ）は既に`config["expert_history_window"]`（既定6）で直近N件へ
窓化済みであり、agreements側だけこの対称性が欠けている。この非対称自体は既存コード
（cela_main.py:15181-15184、BL-103）が明示的にコメントで指摘している。ランが進むほど単調に
肥大化し続け、コスト増（実測$7/run）・OpenRouterクレジット枯渇の一因になっている。

**当初「Freeze済み項目は件数無制限に含める」ことでウィンドウ外に落ちる重要事項を救済する設計を
想定したが、ユーザーの質問を受け実DBを調査した結果、`is_frozen=1`の行はDB全体で0件——Freeze
機構は事実上一度も定着した状態で使われていないことが判明した**（過去ログで`freeze_agreement`
の呼び出しは3回のみ確認でき、2回は`agreement_id`に無効な値を渡して失敗、1回は成功したが
そのrunのデータは現在のDBに残っていない）。この事実を踏まえ、単純な直近N件ウィンドウでは
なく、ユーザー選択の「現在タスク関連を優先」方式を採用する。

本設計は独立レビューを一度受け、指摘済みの問題（下記A〜J）を反映済み。

## 設計

### 関連性の定義

- **現在タスク自身のagreements**（`task_id`が現在の実効タスクIDと一致）: 件数無制限に含める。
- **現在タスクが計画上依存する（`depends_on`）タスクのagreements**: 件数無制限に含める
  （直接依存のみ、推移的依存の再帰探索はしない）。
- **上記に該当しない残り**（無関係タスクのagreements）: 実際に表示される（Decision/
  Deliverable・非Superseded・非Directive）行のうち、直近`_AGREEMENTS_CONTEXT_RECENCY_WINDOW`
  件（既定40）のみ含める。古い順に切り捨てる。

  【独立レビュー指摘A・最重要】当初案は生の行（Superseded/Directive等の表示除外対象も含む）
  に対して直近40件を数えていたが、実測したところ**直近40 raw行のうち実際に表示されるのは
  わずか23件**（Superseded 8・Directive 9混入）だった。「window=40」が意味と乖離するだけで
  なく、Superseded/Directiveがバーストするターンでは実効窓がさらに縮む再現性のない挙動になる。
  表示フィルタ述語を`_is_agreement_displayable`として`_build_agreements_context`と共有し、
  **表示対象に絞り込んでから**window件数を数える設計へ修正した（AGENTS.md §15.1: 同じ判定を
  2箇所に書かない）。

### 既知の限界（設計書への明記、対応はスコープ外）

- Freezeが実質機能していないため、「関連タスクでも直近ウィンドウでもないが実は今も重要」と
  いう古い決定はウィンドウ外に落ちるリスクが残る。エージェントは`read_agreement`の
  topic_keyword検索で能動的に探すことは可能（完全に不可視ではない）。Freeze機構自体を実際に
  機能させるのは別BLとしてissue_backlogに候補メモを残す。
- 【独立レビュー指摘D】`current_task_id`が`current_phase`のタスク一覧に無い場合（BL-190型の
  再計画ドリフト）、`_get_current_task`はphases[0]の先頭タスクへフォールバックする（既存
  挙動）。この値がコンテキスト絞り込みの駆動に新たに使われるため、誤解決時は「間違った
  タスクの関連集合＋窓」が⚠️警告ログ以外に検知手段なく静かに選ばれる劣化モードとなる
  （BL-318のadvance_task導入で発生頻度は下がるが根絶はしない）。
- 【独立レビュー指摘J】`plan_review`/`macro_audit_round34`等、taskの`depends_on`に現れ得ない
  疑似task_id（facilitator/reflection由来のagreements）は、常に「無関係」バケットへ回り
  window落ちの対象になる。実害は小さい。
- **decisions側（`_build_hydrate_context`、BL-103で`expert_history_window`により既に窓化済み）
  には同種の「read_agreement」に相当する能動読み返しツールが存在しない**（`trace_lineage`は
  agreement/fact/entityのみが対象、`decisions`は非対応）。`decisions.internal_thought_process`
  には各ノードの生の思考過程が記録されており事後監査には価値があるが、ライブ実行中のエージェント
  自身がこれを能動的に読み返す実インシデントは確認されていない（`read_agreement`はBL-279で
  実インシデントを受けて作られた）。ユーザーと協議の上、今回は見送り・スコープ外とし、
  「decisions能動読み返しツールの要否」をissue_backlogへ候補メモとして残す
  （読み損ねによる実害が観測された場合に着手）。

### 実装

**新規ヘルパー**（`_build_agreements_context`の直前、cela_main.py:10466付近）:

```python
# [BL-317][AGENTS.md §7 承認済み] 関連タスク以外のagreementsを直近何件まで含めるか。
# Appconfig["agreements_context_recency_window"]として設定可能（decisions側の
# expert_history_windowと対称。既定40）。

def _is_agreement_displayable(a: dict) -> bool:
    """[BL-317][独立レビュー指摘A] _build_agreements_contextの表示フィルタと
    _select_relevant_agreementsの窓対象判定が同じ基準を使うための共有述語
    （AGENTS.md §15.1）。Decision/Deliverableのみ・Superseded除外・Directive除外。
    """
    return (
        a.get("entry_type", "Decision") in ("Decision", "Deliverable")
        and a.get("status") != "Superseded"
        and a.get("entry_type") != "Directive"
    )


def _select_relevant_agreements(agreements: list[dict], current_task_id: str,
                                 task_depends_on: list[str], window: int) -> list[dict]:
    """[BL-317] 現在タスク自身＋直接依存タスクのagreementsは無制限に残し、それ以外は
    「実際に表示される」行のうち直近window件のみ残す（独立レビュー指摘A）。
    current_task_idが未解決（空文字）の場合は絞り込まず全件返す（初回ターン等、
    フィルタ不能な状態での安全側デフォルト）。
    """
    if not current_task_id:
        return agreements
    relevant_task_ids = {current_task_id} | set(task_depends_on or [])
    relevant = [a for a in agreements if a.get("task_id") in relevant_task_ids]
    displayable_others = [
        a for a in agreements
        if a.get("task_id") not in relevant_task_ids and _is_agreement_displayable(a)
    ]
    others_kept = displayable_others[-window:] if window else displayable_others
    keep_ids = {a["id"] for a in relevant} | {a["id"] for a in others_kept}
    # 元のrowid順（get_agreements_from_dbの並び）を保った状態で返す
    return [a for a in agreements if a["id"] in keep_ids]
```

**`_build_agreements_context`の表示フィルタ**（10473-10479行）を共有述語へ差し替える:
```python
decisions_and_deliverables = [a for a in agreements if _is_agreement_displayable(a)]
```

**`_build_agreements_context_from_db`の変更**（cela_main.py:10766付近）——新規オプション引数を
追加し、未指定時は従来通り無制限（既存テスト2件が2引数のみで呼んでいるため後方互換を維持、
`tests/test_bl071_agreement_timestamp_crash.py:57`・`tests/test_bl224_phase2_lineage_
consumption.py:237`で確認済み）:

```python
def _build_agreements_context_from_db(conn: sqlite3.Connection, run_id: str,
                                       current_task_id: str = "",
                                       task_depends_on: list[str] | None = None,
                                       window: int = 40) -> str:
    agreements = get_agreements_from_db(conn, run_id)
    trimmed = False
    if current_task_id:
        _before = len(agreements)
        agreements = _select_relevant_agreements(agreements, current_task_id, task_depends_on or [], window)
        trimmed = len(agreements) < _before
        if trimmed:
            print(f"  ✂️ [BL-317] agreementsコンテキストを{_before}件→{len(agreements)}件へ絞り込みました"
                  f"（current_task_id={current_task_id}）。")
    text = _build_agreements_context(agreements, conn, run_id)
    if trimmed:
        # [BL-317][ユーザー指摘] 絞り込みが発生した場合、LLM自身にその事実を明示し、
        # ここに含まれない過去の合意・決定事項が必要な場合はread_agreementで能動的に
        # 確認するよう促す。登録済みなのに単に表示されず読み漏らす事故を防ぐため
        # （§13/§15.4: 入口〈write_agreement〉があっても出口〈参照〉が欠けると
        # 記録が実質死蔵する）。
        text += (
            f"\n\n【BL-317: このリストは全件ではありません】現在タスク（{current_task_id}）"
            "及びその直接依存タスクの事項は全件表示していますが、それ以外の過去の合意・決定・"
            f"成果物は直近{window}件のみに絞り込んでいます。ここに含まれていない過去の"
            "合意事項・成果物が必要になった場合は、必ずread_agreementツール"
            "（topic_keyword/task_id指定）で能動的に確認してください。\n"
        )
    return text
```

**共有depends_onヘルパー**（新規、cela_main.py:12691付近の既存コメントの直前）
【独立レビュー指摘C】既存の`call_detector`（12697行）は
`[d for d in (current_task.get("depends_on", []) or []) if d]`という防御的パターンを既に
使っている。同じロジックを新規呼び出し箇所へインラインで複製せず、共有ヘルパーへ抽出して
12697行側もこれを使うよう統一する（AGENTS.md §15.1）。空文字混入の実害は仮説ではない——
BL-318のデータ是正で`task_id=""`のagreement行を実際に1件作成済みであり、`depends_on`に
空文字が紛れ込むと無関係な行が誤って「関連」に混入する経路が現実に存在する。

```python
def _task_depends_on(task: dict) -> list[str]:
    """[BL-242/BL-317] taskのdepends_onを安全に取得する共有ヘルパー。None・欠落・
    空文字混入いずれでも安全に劣化する（AGENTS.md §13.1、独立レビュー指摘C）。"""
    return [d for d in (task.get("depends_on", []) or []) if d]
```

12697行目は`_current_task_depends_on = _task_depends_on(current_task)`へ置き換える。

**呼び出し元をまとめる新規ヘルパー**（cela_main.py:10771付近、`_build_agreements_context_
from_db`の直後）【独立レビュー指摘F】5箇所すべてが同じ3行パターンを複製するとD-179と同型の
取りこぼしリスクがあるため、1つのヘルパーへ統一する:

```python
def _build_agreements_context_for_state(conn: sqlite3.Connection, state: LineageState,
                                         config: "Appconfig | None" = None) -> str:
    """[BL-317] call_orchestrator/call_expert/call_detector/generate_user_utterance
    共通のagreementsコンテキスト取得パターンを1箇所へ集約する（独立レビュー指摘F）。"""
    current_task = _get_current_task(state)
    current_task_id = _effective_current_task_id_from(state)
    task_depends_on = _task_depends_on(current_task)
    window = (config or {}).get("agreements_context_recency_window", 40)
    return _build_agreements_context_from_db(conn, state["run_id"], current_task_id, task_depends_on, window)
```

**5箇所の呼び出し元**（現在の行番号: call_orchestrator:11806〈configあり〉,
call_expert:11944〈configあり〉, call_detector:12642〈configなし、既定window=40〉,
generate_user_utterance内:14741/15179〈configあり〉）を
`agreements_text = _build_agreements_context_for_state(_conn, state, config)`
（call_detectorのみ`config`引数省略、`get_active_conn()`を`_conn`代わりに使用）へ統一する。

**Appconfig拡張**（独立レビュー指摘G、decisions側の`expert_history_window`との対称性のため
モジュール定数ではなくAppconfigフィールドとする）:
- `Appconfig`TypedDict（cela_main.py:10421付近）へ`agreements_context_recency_window: int`を
  `expert_history_window`の直後に追加。
- デフォルト値辞書（cela_main.py:19179付近）へ`"agreements_context_recency_window": 40,`を追加
  （AGENTS.md §7承認済み・本設計内で確定）。

**BL-103コメントの更新**（cela_main.py:15181-15184）【独立レビュー指摘E】
「Expert側の窓付きhydrate_contextと非対称かつ長時間runで際限なく肥大化するリスクがあった」は
BL-317実装後は事実と異なるため、agreements側も窓化済みである旨に更新する。

### プロンプトキャッシュへの影響（独立レビュー指摘B、正直な記述への修正）

現状のagreements_textはrowid順append-onlyで、ターン間でプレフィックスが比較的安定する
（in-placeのstatus更新はあるが構造は保たれる）。**フィルタ導入後は、タスク遷移（current_
task_idが変わる瞬間）のたびにrelevant集合が作り変わり、ブロック全体のプレフィックスキャッシュ
がその位置から崩れる**——これは認めるべきコストである。同一タスク内の複数ラウンドでは
relevant集合が安定するため、タスクの継続期間が長いほど正味の影響は小さいと予想されるが、
実測していない。BL-312の教訓（キャッシュ計測を怠らない）を踏まえ、宿題（§Verification）に
実運用でのキャッシュヒット率確認を明記する。

## Critical Files

- `cela_main.py`: 新規ヘルパー`_is_agreement_displayable`・`_select_relevant_agreements`
  （10466行付近）、`_build_agreements_context`の表示フィルタ差し替え（10473-10479行）、
  `_build_agreements_context_from_db`のシグネチャ拡張（10766行付近）、新規
  `_build_agreements_context_for_state`（10771行付近）、新規`_task_depends_on`（12691行付近、
  12697行の置き換え含む）、5箇所の呼び出し元更新（11806, 11944, 12642, 14741, 15179）、
  `Appconfig`TypedDict拡張（10421行付近）、デフォルト値辞書（19179行付近）、BL-103コメント
  更新（15181-15184行）
- `tests/test_bl317_agreements_context_relevance_window.py`（新規）

## Verification

1. **関連タスク無制限テスト**: 現在タスクの`task_id`一致agreementsが、閾値を超える件数でも
   すべて残ることを確認。
2. **依存タスク無制限テスト**: `task_depends_on`に含まれるtask_idのagreementsもすべて残る
   ことを確認。
3. **窓は「表示対象」基準であることのテスト（独立レビュー指摘A・H）**: Superseded/Directive
   行が直近raw行の大半を占める状況を再現し、`_select_relevant_agreements`が生の直近window件
   ではなく「表示対象」の直近window件を残すことを確認する（当初案では通らない、リバートで
   落ちることを確認）。旧「重複排除テスト」（relevant/othersが定義上disjointで常にpassする
   空振りテストだった、独立レビュー指摘H）はこのテストへ置き換える。
4. **後方互換テスト**: `current_task_id=""`（未指定）では全件返る。
5. **depends_on防御テスト（独立レビュー指摘C）**: `depends_on`に空文字が混在していても、
   `task_id=""`のagreement行が誤って関連集合に混入しないことを確認する
   （BL-318で実際に作成した`task_id=""`行のパターンを模す）。
6. **実測サイズ縮小テスト**: 実DB相当のデータ量を用意し、フィルタ後の文字数が明確に縮小
   することを確認（フィルタ処理を無効化するとテストが失敗することを確認、§17.1）。
7. **絞り込み明示テスト（ユーザー指摘）**: 絞り込みが発生した場合、返り値の文字列に
   「このリストは全件ではありません」「read_agreementツール」への言及が含まれることを確認。
   絞り込みが発生しない場合（`current_task_id=""`や全件がwindow内に収まる場合）はこの注記が
   含まれないことも確認する。
8. `python -m py_compile cela_main.py`
9. 既存の`test_bl071_agreement_timestamp_crash.py`・`test_bl224_phase2_lineage_consumption.py`
   を再実行し非退行を確認。`call_detector`の`_task_depends_on`統一が既存の依存未読み込み警告
   （BL-242）の挙動を変えないことを確認。
10. フルオフラインスイート実行。
11. 実装後、`docs/design/back_log/issue_backlog.md`にBL-317を記載（Freeze機構自体の改修候補
    メモ・decisions能動読み返しツールの候補メモ・独立レビューの指摘対応も含む）、
    `decision_log.md`へ決定を記録し、この設計を`docs/design/back_log/BL-317/
    BL317_basic_design.md`・独立レビューを`BL317_review.md`へ実装前〜実装後に保存する。
12. **ライブラン適用**: 現在停止中のrun_id=1787890406-1e73a89dへ適用する場合、BL-318と同様
    ノードの継ぎ目を見計らって一時停止してから`--resume`する。
13. **実測確認（宿題）**: 適用後の実ランで、(a) agreements_textの文字数がどの程度縮小したか
    （目標: 現状138,547文字から大幅な削減）、(b) タスク遷移時のプロンプトキャッシュヒット率
    への影響（独立レビュー指摘B）、の両方を次回ドライラン時に確認する。
