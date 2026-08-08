本ファイルは2件のBL（BL-191・BL-192）の基本設計をまとめて扱う。どちらもUser AI Stage4
（`generate_user_utterance`）への変更が中心で、同一実装セッションで扱う想定のため1ファイルに
まとめた。BL-191は新規state/DB/ツールを伴う機構面の変更、BL-192はプロンプト文言のみの
追記（新規状態なし）。

**本プランのExitPlanMode承認対象はBL-191のみ**。BL-192はBL-191のような機構面の複雑さ
（状態機械・複数ノードにまたがる相互作用）を持たず、Stage4等のシステムプロンプトへの
文言追記のみで完結するため、BL-191のような重い検証サイクル（ユースケース通しトレース・
独立レビュー）を経る必要がないとユーザーが判断。**BL-192はExitPlanMode後、
issue_backlog.mdへ独立したBLとして直接起票する**（本ファイル内の設計内容をそのまま
起票文の元にする）。実装自体はBL-191と同じセッション・同じ箇所（Stage4）に触れるため
一緒に行う想定だが、設計承認のゲートとしてはBL-191のみを扱う。

実装時は、AGENTS.md §7に従い本ファイルのBL-191部分を要約せず原文のまま
`docs/design/back_log/BL-191/BL191_basic_design.md` として保存すること。

---

# BL-191（予定）: Stage4駆動の過去タスク一時フォーカス切替＋併記対象タスクの明示 基本設計

## Context

08-07〜08-08のストレステストログ（`log/2026-08-07/2355`、`log/2026-08-08/0906`）レビューで、
BL-186（ゴール改定時にtask_plannerが新フェーズを追加して過去タスクを再検証させる仕組み）の
限界が実地で顕在化した。ゴール改定・task_plan_reviewer主導の計画再構成が繰り返し起きると、
承認済み過去タスクの成果物・DB確定値がどんどん現ゴールと整合しなくなる一方、現行設計は
User AI/Expertのプロンプト含め「常に前進するだけ」の構造になっており、過去タスクは
`plan_revision_reason`経由でtask_plannerが新フェーズ（例: phase7以降）を追加して再検証させる
という、既存フェーズを一切書き換えない・追加専用のパターンしか持たない（BL-163/168/186）。
実ログでは、この「新フェーズが実際に到達される前にランが先へ進みすぎる」問題（BL-186の
`log/2026-08-06/1432`実例）や、「別ノードが別々の過去タスクの不整合を独立に気づき、
バラバラに発言して混乱する」問題が実際に発生した。

ユーザーはこの状況を受け、BL-186で一度「(a)過去タスクへ戻る新ルートを作る／(b)前進のみで
新フェーズを追加する」を検討し(b)を選んだ判断を、今回のストレステスト結果を踏まえて覆し、
**(a)実際にcurrent_task_idを過去タスクへ一時的に巻き戻す経路を新設する**ことを決定した
（ユーザー承認: 「実際に過去タスクへ巻き戻す経路を新設」）。

実装場所についてもユーザーから具体的な設計指針が出された：新規の独立ノードではなく、
**User AIの既存Stage4（`generate_user_utterance`内、「次タスクへ進むか現タスクを修正するか」を
判断する段階）を拡張してスケジューリング判断を行わせる**。理由（ユーザー発言、要約）:
「ユーザーが単に『task_x_xへ進んで』と指示すると、Detectorなど後続ノードが『task_y_yの
成果物も直さないと』と別々に呟き始め、みんなの認識がバラバラのまま混乱が起きる。それより、
Stage4という単一の意思決定点で『明示的に過去タスクtask_y_yへ戻る』か『task_x_xへ進みつつ、
task_y_yも遡って影響を受けているので同時に検討せよ、と明示する』かを一度に宣言する方が
根本的にスムーズ」。この新しいスケジュール専用ホワイトボードは、User AIの次タスク判断
（Stage4）にも見せることをユーザーが承認済み。

BL-190（`current_task_id`/`current_phase`不整合バグの修正、`docs/design/back_log/BL-190/
BL190_basic_design.md`に設計済み・**未実装**）とは別レイヤーの問題であり、両者は競合しない
（BL-190はtask_planner駆動の計画再構成時の`current_phase`再解決、本設計はStage4駆動の
意図的なフォーカス切替）。ただしバグ②対策がBL-190の実装箇所への追記を含むため、
BL-191 Phase 2はBL-190の実装完了を前提とする。

BL-191は先に3体のExploreエージェントによる既存メカニズムの棚卸し（SUPERSEDE、
BL-163/168/186カスケード、issue DEFER機構、Resource Arbiterの死んだ`phases_to_revise`、
facilitator/Resource Arbiter再設計の未実装ドラフト`docs/design/r1_r2_r3b_core/
cela_facilitator_arbiter_redesign_BL041.md`）と、1体のPlanエージェントによる詳細設計、
さらにユーザー主導のユースケース通しトレース（バグ①〜⑥を発見）と別AIによる独立レビュー
（うち妥当7件・偽陽性3件を検証）を経て本ドキュメントにまとめた。

---

# 【第1部】Planエージェントによる詳細設計（原文）

以下はPlanエージェントが出力した実装計画の原文である（AGENTS.md §7に従い要約しない）。
この後の【第2部】【第3部】で、ユースケーストレースと独立レビューによる修正を加えている。
**両者が矛盾する場合は第2部・第3部を正とする。**

## 0. 設計サマリ（9つの要件がどう組み合わさるか）

- Stage4（`generate_user_utterance`, `cela_main.py:7787`, Stage4ブロック`:8046-8129`）に
  新しい**構造化ツール**`schedule_task_focus`を、既存の`THINK_TOOL`と並べて追加する。
  これがユーザーの求める「単一の明示的なスケジューリング判断」であり、
  `call_decision_extractor`の自由文脈`advances_to_task_id`解析に頼らず
  機械可読な`decision_type`を生成する。
- 新しいブリッジグローバルパターン（`_LAST_GOAL_REVISION`/`get_last_goal_revision()`と同一）が
  ツール呼び出しサンドボックスから構造化ペイロードを`generate_user_utterance_node`（`:8563`）へ
  運び、そこで新しいone-shot state field `pending_task_redirect`へ格納する。
- `decision_extractor_node`（`:9484`）が`pending_task_redirect`を読み取り・消費し、
  `_resolve_task_transition`（`:9409`）へ新しい明示的パラメータとして渡す
  —— 自由文脈の`transition` dictへマージ**しない** —— これにより構造化経路と
  レガシー自由文脈経路が明確に分離され、構造化側が存在する場合はそちらが優先される。
- **後方リダイレクト**（`decision_type="redirect_backward"`）は、中断されるフォワードタスクを
  新しい`task_focus_stack`へpushし（v1では深さ1に固定）、`current_task_id`/`current_phase`を
  過去タスクへ移す —— BL-125/BL-176の離脱ゲートは意図的にバイパスする
  （これは*一時停止*であって*放棄*ではないため）。
- **復帰**は完全に機械的（LLM呼び出し不要）：新しいヘルパーを`decision_extractor_node`から
  `_resolve_task_transition`の直後に毎ターン実行し、スタックされたタスクのDeliverableが
  `_is_task_completed`（BL-167）に達したかを確認し、達していればスタックをpopして
  `current_task_id`を戻す —— BL-176と全く同じ完了判定基準を「完了したので戻る」シグナルとして
  再利用する。
- **ジョイントフォーカス**（`decision_type="joint_focus"`）は`current_task_id`に一切触れない。
  別の state field `task_focus_companion`をセットし、それを追加的に
  （`_get_deferred_notes_text`スタイルの注入パターンを再利用した新しいプロンプトブロックで）
  `call_expert`/`call_detector`/Stage1へ提示する。`_build_task_scope_context`の
  単一タスクスコーピングには一切触れない（BL-025の意図を保持）。
- 新しいDBテーブル`scheduling_drafts`を、`goal_drafts`のCRUD形状
  （`get_latest_goal_draft`/`apply_goal_patch`, `:1810-1838`）に1:1で倣って作るが、
  LLMが手書きするdiffテキストではなく構造化列を格納する（システムが合成するナラティブであり、
  LLMが編集する文書ではない —— §2の理由を参照）。これによりStage4はターンをまたいで
  過去のスケジューリング判断を読める永続的な履歴を持つ。
- `current_task_id`が正規に過去タスクと等しくなれば、**SUPERSEDEは不要** ——
  BL-146の既存のcurrent-task-idゲート（`:2511-2532`）がそれを現在のタスクとして認識し、
  通常の`UPDATE`を許可する。SUPERSEDE自体への変更は不要。
- BL-163/168の既存のminor severityフラグ付けが、初めて*実行可能な*入力になる
  （Stage4がフラグされたタスクへ即座にリダイレクトできる）—— BL-186の遅い
  「新フェーズがいつか再訪してくれることを願う」経路だけでなくなる。
  両経路とも保持し、異なるseverity/cadenceを担う（§7参照）。

## 1. 新規`LineageState`フィールド

`cela_main.py:5143`（`class LineageState(TypedDict)`）へ、既存のBL-125/176/190の
one-shot通知クラスタ（`:5181-5197`, つまり`plan_revision_issue_ids`の後）の直後に物理的に
配置し、新しいブロックが1つのまとまった「タスクフォーカス／スケジューリング」セクションとして
読めるようにする：

```python
# [BL-191] Stage4駆動の過去タスクへの一時的フォーカス切替（decision_type="redirect_backward"）で、
# 中断したフォワードタスクへ戻るための復帰ポインタスタック。要素: {"task_id", "phase_id"（監査用の
# 参考情報のみ、復帰時は必ずtask_idから_find_phase_containing_taskで再解決する — BL-190のフェーズ
# 再構成後もtask_idさえ残っていれば正しく復帰できるようにするため）, "reason", "pushed_at_round"}。
# v1は深さ1に固定（スタックに1件あるうちは新たなredirect_backwardを拒否する、schedule_task_focus
# 実装＋_apply_backward_redirectの二重チェック）。
task_focus_stack: list[dict]
# [BL-191] Stage4がdecision_type="joint_focus"で宣言した「現在の主タスクと合わせて今回考慮すべき
# 過去タスク」。current_task_id/current_phaseは変更しない（BL-025のスコープガードレール意図を
# 尊重し、Expert/Detectorへは追加のコンテキストとしてのみ注入する）。None＝未設定。
# shape: {"companion_task_id", "companion_phase_id", "primary_task_id", "reason", "declared_at_round"}
task_focus_companion: dict | None
# [BL-191] generate_user_utterance_node（Stage4のschedule_task_focusツール成功直後）が
# 一度だけ書き込み、decision_extractor_nodeが同ターン内で消費・Noneへリセットする1ショット
# ブリッジ。call_decision_extractorの自由文脈抽出（advances_to_task_id）とは独立した経路。
# shape: {"decision_type": "redirect_backward"|"joint_focus"|"clear_companion"|"force_resume",
#         "target_task_id", "companion_task_id", "reason"}
pending_task_redirect: dict | None
# [BL-191] redirect_backwardの累積発火回数（facilitation_count/plan_revision_countと同型の
# run単位カウンタ）。schedule_task_focusツールが上限（既定5）到達時に新規redirect_backwardを拒否する。
task_focus_redirect_count: int
# [BL-191] _apply_backward_redirectが発火した直後、次のExpert/User AIターンへ一度だけ
# 「一時的に過去タスクへ切り替わった」ことを明示する通知（task_reassigned_after_replan_notice
# と同型のone-shotパターン）。
task_focus_redirect_notice: str
# [BL-191] _maybe_resume_forward_focusが復帰を発火した直後、次のターンへ一度だけ
# 「中断していたフォワードタスクへ復帰した」ことを明示する通知。
task_focus_resume_notice: str
```

6つすべてを`run_ai_vs_ai_loop`の初期stateディクショナリ（`cela_main.py:10550-10626`、
既存の`task_transition_blocked_unapproved_task_id`/`plan_revision_issue_ids`のエントリ
`:10580, :10618`の隣）へ登録する：
```python
"task_focus_stack": [],
"task_focus_companion": None,
"pending_task_redirect": None,
"task_focus_redirect_count": 0,
"task_focus_redirect_notice": "",
"task_focus_resume_notice": "",
```
（LangGraphは宣言されていないTypedDictキーをノード間で伝播しない —— BL-038の教訓、
`:5217-5220`のコメントで明示的に言及されている —— ため、`TypedDict`宣言*と*この
初期化ディクショナリ登録の**両方**が必要。どちらかが欠けると静かにBL-038クラスの
バグが再導入される。）

### なぜスタックか（単一ポインタではなく）
データ形状は将来の深さ>1への拡張をサポートするが、§8のガードレールが意図的に
スタックが既に非空の場合のpushを拒否し、*実効的な*v1の挙動を深さ1に制限する。
これにより、後で深さ制限を緩和する際にスキーマ移行は不要になり、
`_apply_backward_redirect`/`_schedule_task_focus_tool_impl`のガードを変更するだけで済む。

### `_get_current_task` / `_build_task_scope_context` —— 明示的に変更**しない**
どちらも（`:5513`, `:5546`）今日とまったく同じように`state["current_task_id"]`/
`state["current_phase"]`をキーにする。これが設計全体の要である：
`current_task_id`が正規にリダイレクト先の過去タスクを指すようになれば、
**既存のすべてのタスク単位スコープ機構（call_expertの`current_task_json`、
call_detectorの`acceptance_criteria`、BL-146のwrite_agreementゲート、
orchestratorの専門家選択、*次の*遷移に対するBL-176の離脱ゲート）が、
コード変更ゼロで自動的にそれに対して正しく動作する**。すべてこれら2つのフィールドを
既にキーにしているからである。真に新しいコードは(a)いつそれらのフィールドを書くかを
決める構造化決定機構と、(b)純粋に追加的な通知／companionコンテキスト注入だけである。

## 2. 新しい「スケジューリングホワイトボード」テーブル＋CRUD

### 設計上の選択：構造化列＋システム合成ナラティブ（LLMが手書きするdiffではなく）

ユーザーの提示は`goal_drafts`（run_idスコープ、バージョン管理、`_apply_text_edits`再利用）に
倣うことを求めた。調査の結果、`goal_drafts`/`_apply_text_edits`（`:4748-4816`）は、
LLMが単一の進化する文書（ゴール文）に対してClaude-Code-Editスタイルの`old_text`/`new_text`
diffで**手書きの**増分的な散文編集を行うために存在する。本質的に*構造化された、enum駆動の*
判断（`decision_type`, `target_task_id`, `companion_task_id`）に対してStage4にそのような
diffの作成を要求すると、ユーザーがこの判断について明示的に避けたがっている自由文脈の脆弱性
（BL-039のドット/アンダースコア正規化バグ）をまさに再導入することになる。

解決：`goal_drafts`の**ストレージ形状**（run_idスコープ、append-onlyバージョン管理行、
`get_latest_X`/`apply_X_patch`スタイルのCRUD命名）は維持しつつ、ツールの引数は構造化し、
人間可読の`content`ナラティブは書き込み時にそれらの構造化フィールドから*システムが*
（LLMではなく）合成する。これによりStage4は毎ターン参照できる可読なバージョン履歴を持ち
（「Stage4はスケジューリングホワイトボードの内容を見るべき」を満たす）、
一方で`_resolve_task_transition`は`target_task_id`を見つけるために散文を解析する必要が
一切ない —— ツール呼び出しの引数から直接得られる。

### スキーマ（`init_db`, `cela_main.py:4165`、既存の`goal_drafts`テーブル`:4160-4164`の直後へ追加）：

```sql
-- [BL-191] Stage4のschedule_task_focusツール呼び出しの構造化ログ兼版管理文書。goal_draftsと
-- 同型のrun_id単位append-onlyバージョニングだが、contentはLLMが手書きするdiffの結果ではなく、
-- decision_type/primary_task_id/companion_task_id/reasonからシステムが機械的に合成する
-- 監査可能な要約文（BL-039のドット/アンダースコア混同バグを避けるため、machine-readable
-- 列を主、contentは人間/LLMが読む副次的サマリーとして扱う）。
CREATE TABLE IF NOT EXISTS scheduling_drafts (
    draft_id TEXT, version INTEGER, content TEXT, author_role TEXT,
    decision_type TEXT NOT NULL, primary_task_id TEXT, primary_phase_id TEXT,
    companion_task_id TEXT, companion_phase_id TEXT, reason TEXT,
    timestamp REAL, run_id TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_scheduling_drafts_run ON scheduling_drafts(run_id);
```

これは（既存テーブルへの列追加ではなく）まったく新しいテーブルなので、通常の
`init_db`後の`_ensure_*_column`移行ヘルパー（例：`_ensure_issue_log_defer_column`,
`:4172-4181`）は**不要** —— `CREATE TABLE IF NOT EXISTS`は新規DBと既存DBの両方に対して
既に冪等であり、`goal_escalations`/`goal_essence`が追加されたときと同じである。

### CRUD関数（`get_latest_goal_draft`/`apply_goal_patch`, `cela_main.py:1810-1838`の近く、
あるいは新しい隣接ブロックへ配置 —— どちらも、DBヘルパーを厳密な近接性ではなく機能単位で
グループ化する既存のファイル構成と一貫している）：

```python
def get_latest_scheduling_decision(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """[BL-191] scheduling_draftsの最新1件を返す（get_latest_goal_draftのミラー）。"""
    row = conn.execute(
        "SELECT * FROM scheduling_drafts WHERE run_id=? ORDER BY version DESC LIMIT 1", (run_id,)
    ).fetchone()
    return dict(row) if row else None


def get_scheduling_decision_history(conn: sqlite3.Connection, run_id: str, limit: int = 5) -> list[dict]:
    """[BL-191] Stage4プロンプトへ表示する直近の過去のスケジューリング決定（新しい順）。"""
    rows = conn.execute(
        "SELECT * FROM scheduling_drafts WHERE run_id=? ORDER BY version DESC LIMIT ?", (run_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def record_scheduling_decision(conn: sqlite3.Connection, run_id: str, decision_type: str,
                                primary_task_id: str, primary_phase_id: str,
                                companion_task_id: str, companion_phase_id: str,
                                reason: str, author_role: str) -> int:
    """[BL-191] apply_goal_patchのミラー。contentはシステムが機械的に合成する（LLMにdiffを
    書かせない）。バージョンは常に加算のみ（削除しない、append-only）。"""
    latest = get_latest_scheduling_decision(conn, run_id)
    new_version = (latest["version"] + 1) if latest else 1
    content = (
        f"[v{new_version}] decision_type={decision_type} primary={primary_task_id} "
        f"companion={companion_task_id or '(なし)'} reason={reason}"
    )
    conn.execute(
        "INSERT INTO scheduling_drafts (draft_id, version, content, author_role, decision_type, "
        "primary_task_id, primary_phase_id, companion_task_id, companion_phase_id, reason, "
        "timestamp, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"SCHED-{int(time.time()*1000)}", new_version, content, author_role, decision_type,
         primary_task_id, primary_phase_id, companion_task_id, companion_phase_id, reason,
         time.time(), run_id)
    )
    print(f"  🗓️ [DB] scheduling_draftsへINSERT: version={new_version}, decision_type={decision_type}")
    return new_version
```

## 3. Stage4のプロンプト＋新しいツールスキーマ

### 新しいツールスキーマ（`WRITE_ISSUE_TOOL`/`WRITE_AGREEMENT_TOOL`の近く、
例えば`cela_main.py:777`の`WRITE_ISSUE_TOOL`の直後へ配置）：

```python
SCHEDULE_TASK_FOCUS_TOOL = {
    "type": "function",
    "function": {
        "name": "schedule_task_focus",
        "description": (
            "[BL-191] 通常の『次タスクへ進む』指示とは別に、過去の承認済みタスクの手戻り対応が"
            "必要になった場合に、そのスケジューリング判断を構造化して1回で明示するツール。"
            "任意呼び出し（通常通り前進するだけの場合は呼ぶ必要はない）。"
            "'redirect_backward': 今すぐ作業対象を過去タスクへ完全に切り替える（現在のフォワード"
            "タスクは一時中断し、対象task_idのDeliverableが再承認され次第、自動的に元へ戻ります）。"
            "深さ1固定（既に中断中のフォーカスがある間は使えません。force_resumeで先に解消してください）。"
            "'joint_focus': 現在のタスクは変更しないが、指定した過去task_idを『今回のターンで"
            "Expert/Detectorが併せて考慮すべき関連タスク』として明示する（current_task_idは動かない）。"
            "'clear_companion': joint_focusで設定した companion を解除する。"
            "'force_resume': redirect_backward中の過去タスクがまだ未解決でも、意図的に中断を"
            "打ち切りフォワードタスクへ強制的に復帰する（安全弁。対象task_idには自動的に"
            "整合性再確認issueが再起票されます）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "decision_type": {
                    "type": "string",
                    "enum": ["redirect_backward", "joint_focus", "clear_companion", "force_resume"]
                },
                "target_task_id": {
                    "type": "string",
                    "description": "redirect_backward時必須。切替先の過去task_id（既存のDeliverableを持つtask_idのみ有効）"
                },
                "companion_task_id": {
                    "type": "string",
                    "description": "joint_focus時必須。今回併せて考慮すべき過去task_id"
                },
                "reason": {"type": "string", "description": "この判断の理由（必須）"}
            },
            "required": ["decision_type", "reason"]
        }
    }
}
```

### ツール実装＋`TOOL_DISPATCH`登録

`TOOL_DISPATCH`（`cela_main.py:3092-3133`）へ、`write_agreement`エントリ（`:3099-3104`）が
既に`_phases_from`/`_effective_current_task_id_from`のようなヘルパーへ`state`を通している
のとまったく同じ規約に従って追加する：

```python
"schedule_task_focus": lambda args, state=None: _schedule_task_focus_tool_impl(
    args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, state
),
```

```python
_MAX_TASK_FOCUS_REDIRECTS = 5  # [BL-191] facilitation_count(5)/plan_revision_count(5)と揃える

def _schedule_task_focus_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str,
                                    caller_role: str, state: dict | None) -> dict:
    """[BL-191] schedule_task_focusの実体。userロールのみ許可（Stage4は_CURRENT_CALLER_ROLE=
    "user"で動くため、facilitator等の別経路からの呼び出しは弾く）。"""
    if caller_role != "user":
        return {"success": False, "error": f"{caller_role}はschedule_task_focusを呼び出せません（userロールのみ許可）"}
    decision_type = args.get("decision_type")
    reason = args.get("reason", "")
    if decision_type not in ("redirect_backward", "joint_focus", "clear_companion", "force_resume") or not reason:
        return {"success": False, "error": "decision_type/reasonは必須です"}

    phases = _phases_from(state)
    current_task_id = _effective_current_task_id_from(state)
    current_phase_id = _phase_id_from(state)

    if decision_type == "redirect_backward":
        target_task_id = args.get("target_task_id", "")
        target = _find_task_by_id(phases, target_task_id)
        if not target:
            return {"success": False, "error": f"target_task_id '{target_task_id}' は計画に存在しません"}
        if target_task_id == current_task_id:
            return {"success": False, "error": "target_task_idは現在のタスクと同一です"}
        if not _find_active_deliverable_agreement(conn, run_id, _find_task_phase_id(phases, target_task_id), target_task_id):
            return {"success": False, "error": f"'{target_task_id}'にはまだDeliverableが存在しません（未着手タスクへはredirect_backwardではなく通常のタスク遷移を使ってください）"}
        if state and state.get("task_focus_stack"):
            return {"success": False, "error": "既に一時中断中のフォーカスがあります（深さ1固定）。force_resumeで先に解消してください"}
        if state and state.get("task_focus_redirect_count", 0) >= _MAX_TASK_FOCUS_REDIRECTS:
            return {"success": False, "error": f"redirect_backwardの上限（{_MAX_TASK_FOCUS_REDIRECTS}回/run）に達しました"}
        target_phase_id = _find_task_phase_id(phases, target_task_id)
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    "", "", reason, caller_role)
        global _LAST_SCHEDULING_DECISION
        _LAST_SCHEDULING_DECISION = {
            "decision_type": "redirect_backward", "target_task_id": target_task_id,
            "target_phase_id": target_phase_id, "reason": reason,
        }
        return {"success": True}

    if decision_type == "joint_focus":
        companion_task_id = args.get("companion_task_id", "")
        if not _find_task_by_id(phases, companion_task_id):
            return {"success": False, "error": f"companion_task_id '{companion_task_id}' は計画に存在しません"}
        if companion_task_id == current_task_id:
            return {"success": False, "error": "companion_task_idは現在のタスクと同一です"}
        companion_phase_id = _find_task_phase_id(phases, companion_task_id)
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    companion_task_id, companion_phase_id, reason, caller_role)
        global _LAST_SCHEDULING_DECISION
        _LAST_SCHEDULING_DECISION = {
            "decision_type": "joint_focus", "companion_task_id": companion_task_id,
            "companion_phase_id": companion_phase_id, "reason": reason,
        }
        return {"success": True}

    if decision_type in ("clear_companion", "force_resume"):
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    "", "", reason, caller_role)
        global _LAST_SCHEDULING_DECISION
        _LAST_SCHEDULING_DECISION = {"decision_type": decision_type, "reason": reason}
        return {"success": True}

    return {"success": False, "error": f"未知のdecision_type: {decision_type}"}
```

（`_find_task_phase_id`は`:9020-9032`で同じ目的のために既に使われているインラインパターンを
ミラーする小さな新ヘルパー —— まだ名前が付いていなければそのインラインループを名前付き
ヘルパーへ切り出す。grep確認の結果、現在そのようなヘルパーは単独では存在しないので追加する。）

### ブリッジグローバル＋getter（`_LAST_*`クラスタ, `cela_main.py:3170-3181`、
getterは`:3216-3236`へ配置）：

```python
# [BL-191] 直前のquery_AI呼び出しのツールループ内でschedule_task_focusが成功した場合の構造化決定。
# _LAST_GOAL_REVISIONと同型のブリッジパターン。
_LAST_SCHEDULING_DECISION: dict | None = None

def get_last_scheduling_decision() -> dict | None:
    return dict(_LAST_SCHEDULING_DECISION) if _LAST_SCHEDULING_DECISION else None
```

### Stage4のプロンプト変更（`generate_user_utterance`, `:8046-8095`）

1. Stage4のツールリストへツールを追加する。現在は`tools=[THINK_TOOL]`（`:8107`）。
   3つのStage4分岐（承認済み／却下／ApprovalRecordingFailed）すべてで
   `tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL]`へ変更する ——
   却下分岐でも許可する。「今回の提出は却下するが、同時に過去タスクもフラグする」は
   正当な組み合わせだからである。

2. `stage4_system_prompt`（既存の`_transition_notice`/`_escalation_resume_notice`と並んで
   `:8047-8048`で構築される）へ3つの新しいコンテキストブロックを追加する：
   - `_stale_past_tasks_text = _build_stale_past_tasks_text(_conn, state["run_id"])`
     —— BL-163が起票した、まだopenのminor整合性チェックissueをtask_id単位で提示する
     （新ヘルパー、§7）。
   - `_scheduling_history_text = _build_scheduling_history_text(_conn, state["run_id"])`
     —— `get_scheduling_decision_history`（直近5件）を短い行としてレンダリングし、
     Stage4がターンをまたいだ継続性を持てるようにする
     （「2ターン前にtask_2_3へリダイレクトした、まだ待機中」）。
   - `_task_focus_state_text = _build_task_focus_state_text(state)`
     —— 現在の`task_focus_stack`/`task_focus_companion`を明示的にレンダリングする
     （例：「現在task_2_3へ一時的にフォーカス中。復帰待ちの元タスク: task_4_1」
     あるいは「companion: task_1_2がtask_5_1と併記対象」）。

   これらを既存の`📊 [プロジェクト進行計画]`行（`:8057`）の後、`【承認理由（第3段）】`
   （`:8058`）の前に挿入し、`schedule_task_focus`をいつ呼ぶべきか vs. 通常の次タスク指示文を
   書くだけでよいかを説明する簡潔な指示文を添える。

3. Stage4は現在`content = query_AI(...)`を直接読んでいる（`_query_and_parse_with_retry`ではない）
   ため、自由文脈の戻り値に対するJSONスキーマ変更は不要 —— `schedule_task_focus`は
   Stage4の既存の自由文脈「次タスク指示」出力とは直交する、真に独立したツール呼び出しである。
   両方が同じStage4ターンで起こりうる（Stage4がツールを呼び、それでも通常の散文でExpertへ
   指示する。その散文は`advances_to_task_id`の自由文脈フォールバックが解析しようとする
   ものだが、§4により構造化決定が優先される）。

### `_absorb_stage_trackers`の配線（`:7824-7836`, `:7895/7941/8011/8108`）

初期ローカル（`:7824-7828`）へ`_stage_scheduling_decision = None`を追加し、
`_absorb_stage_trackers`（`:7830-7836`）の中へ
`_stage_scheduling_decision = _stage_scheduling_decision or get_last_scheduling_decision()`
を追加し、関数末尾で他のグローバルと並べて書き戻す（`:8123-8128`）：
```python
global _LAST_SCHEDULING_DECISION
_LAST_SCHEDULING_DECISION = _stage_scheduling_decision
```

### `generate_user_utterance_node`の配線（`:8563-8635`）

既存のgoal-revision処理ブロック（`:8587-8617`）の直後、
`state["last_essence_proposal"] = ...`（`:8618`）の前へ追加する：
```python
# [BL-191] Stage4がschedule_task_focusを呼んでいれば、構造化決定をdecision_extractor_nodeへ
# 一度だけ橋渡しする（call_decision_extractorの自由文脈抽出をバイパスする経路）。
_scheduling_decision = get_last_scheduling_decision()
if _scheduling_decision:
    state["pending_task_redirect"] = _scheduling_decision
    print(f"  🧭 [BL-191] Stage4がスケジューリング決定を行いました: {_scheduling_decision}")
```

## 4. `_resolve_task_transition` / `decision_extractor_node`の変更

### シグネチャ変更（`cela_main.py:9409`）

```python
def _resolve_task_transition(state: LineageState, transition: dict,
                              structured_redirect: dict | None = None) -> None:
```

既存の`if not next_phase_id and not next_task_id: return`ガード（`:9420-9421`）の**前**へ
構造化リダイレクト処理を挿入し、自由文脈抽出器が今ターン遷移を生成したかどうかに関わらず
常に実行されるようにする：

```python
    if structured_redirect:
        decision_type = structured_redirect.get("decision_type")
        if decision_type == "redirect_backward":
            _apply_backward_redirect(state, structured_redirect)
            return  # [BL-191] 構造化決定が今ターンの遷移を確定させる。以降の自由文脈抽出は無視する。
        if decision_type == "joint_focus":
            _apply_joint_focus(state, structured_redirect)
            # current_task_idは変更しないため、以下の既存の自由文脈遷移ロジックへそのまま続行する。
        elif decision_type == "clear_companion":
            state["task_focus_companion"] = None
        elif decision_type == "force_resume":
            _force_resume_forward_focus(state)
            return

    next_phase_id = transition.get("advances_to_phase_id")
    ... # 既存ロジック、無変更
```

### 新ヘルパー（`_resolve_task_transition`の直後、`decision_extractor_node`の前へ配置）

```python
def _find_phase_containing_task(phases: list[dict], task_id: str) -> dict | None:
    """[BL-191] task_idを含むphaseオブジェクトそのものを返す（_find_task_by_idはtask本体を返すが、
    ここではcurrent_phaseへ丸ごと差し替えるためphase側が必要）。BL-190の
    _reconcile_current_phase_after_replanと同型の全フェーズ線形探索。"""
    for phase in phases:
        for t in phase.get("tasks", []):
            if t.get("task_id") == task_id:
                return phase
    return None


def _apply_backward_redirect(state: LineageState, redirect: dict) -> None:
    """[BL-191] schedule_task_focus(decision_type="redirect_backward")による構造化された
    過去タスクへの一時的フォーカス切替を適用する。[CONSTRAINT] BL-125/BL-176のdeparting-task
    ゲート（未解決severe issue・未承認Deliverable）は意図的に適用しない——これは「離脱」では
    なく「一時中断」であり、_maybe_resume_forward_focus経由で必ず元タスクへ復帰する前提のため
    （中断中のフォワードタスク自身の未解決issue/未承認状態は、復帰後に本来の遷移として改めて
    BL-125/176のチェックを受ける）。
    """
    target_task_id = redirect.get("target_task_id", "")
    target_phase = _find_phase_containing_task(state.get("phases", []), target_task_id)
    if not target_phase:
        print(f"  ⚠️ [BL-191] 存在しないtask_id '{target_task_id}' へのredirect_backward要求を無視しました。")
        return
    stack = state.get("task_focus_stack", [])
    if stack:
        print("  ⚠️ [BL-191] 既に一時中断中のフォーカスがあるため、二重のredirect_backwardを無視しました（ツール側の深さ1ガードのはずが漏れています）。")
        return
    current_task_id = state.get("current_task_id", "")
    current_phase = state.get("current_phase", {})
    stack.append({
        "task_id": current_task_id, "phase_id": current_phase.get("phase_id", ""),
        "reason": redirect.get("reason", ""), "pushed_at_round": state.get("round_count", 0),
    })
    state["task_focus_stack"] = stack
    state["current_task_id"] = target_task_id
    state["current_phase"] = target_phase
    state["task_focus_redirect_count"] = state.get("task_focus_redirect_count", 0) + 1
    state["task_focus_redirect_notice"] = (
        f"[BL-191] 発注者の判断により、作業対象を一時的に過去タスク'{target_task_id}'へ切り替えました"
        f"（理由: {redirect.get('reason', '')}）。このタスクの成果物が再承認され次第、"
        f"自動的に'{current_task_id}'へ復帰します。"
    )
    print(f"  ⏪ [BL-191] current_task_idを一時的に'{target_task_id}'へ切替えました（元: '{current_task_id}'、resume待ち）。")


def _apply_joint_focus(state: LineageState, redirect: dict) -> None:
    """[BL-191] schedule_task_focus(decision_type="joint_focus")の適用。current_task_id/
    current_phaseは変更しない（BL-025のスコープガードレール意図を尊重）。"""
    companion_task_id = redirect.get("companion_task_id", "")
    if not _find_phase_containing_task(state.get("phases", []), companion_task_id):
        print(f"  ⚠️ [BL-191] 存在しないtask_id '{companion_task_id}' へのjoint_focus要求を無視しました。")
        return
    state["task_focus_companion"] = {
        "companion_task_id": companion_task_id,
        "companion_phase_id": redirect.get("companion_phase_id", ""),
        "primary_task_id": state.get("current_task_id", ""),
        "reason": redirect.get("reason", ""),
        "declared_at_round": state.get("round_count", 0),
    }
    print(f"  🔗 [BL-191] task_focus_companionを設定しました: {companion_task_id}")


def _force_resume_forward_focus(state: LineageState) -> None:
    """[BL-191] schedule_task_focus(decision_type="force_resume")の適用。
    task_focus_stackが未完了のままでも強制的にポップし、元のフォワードタスクへ戻る安全弁。
    対象の過去タスクへは、放置されたまま失われないようBL-163と同型の軽微issueを再起票する。"""
    stack = state.get("task_focus_stack", [])
    if not stack:
        print("  ⚠️ [BL-191] force_resume要求を受けましたが、中断中のフォーカスがありません。")
        return
    abandoned_task_id = state.get("current_task_id", "")
    entry = stack[-1]
    resume_phase = _find_phase_containing_task(state.get("phases", []), entry["task_id"])
    state["task_focus_stack"] = stack[:-1]
    if not resume_phase:
        print(f"  ⚠️ [BL-191] 復帰先task_id '{entry['task_id']}'が計画に存在しません。スタックのみクリアします。")
        return
    state["current_task_id"] = entry["task_id"]
    state["current_phase"] = resume_phase
    state["task_focus_resume_notice"] = (
        f"[BL-191] 過去タスク'{abandoned_task_id}'は未解決のまま、意図的にフォーカスを"
        f"打ち切り'{entry['task_id']}'へ復帰しました。'{abandoned_task_id}'は整合性再確認issueとして"
        "再度記録されています。"
    )
    _write_issue_impl(
        {"action_type": "CREATE", "topic": f"task_focus_force_resume_unresolved_{abandoned_task_id}",
         "severity": "minor",
         "description": f"[BL-191] '{abandoned_task_id}'への一時フォーカスはforce_resumeにより未解決のまま打ち切られました。改めて対応が必要です。"},
        get_active_conn(), state["run_id"], "revise_goal_auto", "", abandoned_task_id,
    )
    print(f"  ⏩⚠️ [BL-191] force_resume: '{abandoned_task_id}'を未解決のまま'{entry['task_id']}'へ復帰しました。")


def _maybe_resume_forward_focus(state: LineageState, conn: sqlite3.Connection, run_id: str) -> None:
    """[BL-191] task_focus_stack末尾（中断中のフォワードタスク）が存在し、現在フォーカス中の
    過去タスクがApproved相当（BL-167の_is_task_completed）に達していれば、自動的にポップして
    current_task_id/current_phaseを復帰させる。LLM判断を経由しない機械的トリガー
    （BL-176の既存ゲート判定基準をそのまま再利用する）。
    """
    stack = state.get("task_focus_stack", [])
    if not stack:
        return
    focused_task_id = state.get("current_task_id", "")
    if not _is_task_completed(conn, run_id, focused_task_id):
        return
    entry = stack[-1]
    resume_phase = _find_phase_containing_task(state.get("phases", []), entry["task_id"])
    state["task_focus_stack"] = stack[:-1]
    if not resume_phase:
        print(f"  ⚠️ [BL-191] 復帰先task_id '{entry['task_id']}'が計画に存在しません（再構成で消失した可能性）。スタックのみクリアします。")
        return
    state["current_task_id"] = entry["task_id"]
    state["current_phase"] = resume_phase
    state["task_focus_resume_notice"] = (
        f"[BL-191] 一時中断していた過去タスク'{focused_task_id}'が再承認されたため、"
        f"'{entry['task_id']}'へ自動復帰しました。"
    )
    print(f"  ⏩ [BL-191] '{focused_task_id}'が承認済みになったため、中断していた'{entry['task_id']}'へ復帰しました。")


def _maybe_clear_resolved_companion(state: LineageState, conn: sqlite3.Connection, run_id: str) -> None:
    """[BL-191] joint_focusで設定されたcompanionが承認済みに達したら自動的にクリアする
    （_maybe_resume_forward_focusと同型の機械的トリガー）。"""
    companion = state.get("task_focus_companion")
    if not companion:
        return
    if _is_task_completed(conn, run_id, companion["companion_task_id"]):
        print(f"  ✅ [BL-191] companion task '{companion['companion_task_id']}'が解決済みのためtask_focus_companionをクリアしました。")
        state["task_focus_companion"] = None
```

### `decision_extractor_node`の呼び出し箇所の変更（`:9484-9729`）

1. 冒頭（`existing_topics`構築の前、つまり`:9490`付近）で、one-shotブリッジフィールドを消費する：
```python
_pending_redirect = state.get("pending_task_redirect")
state["pending_task_redirect"] = None  # [BL-191] one-shot consume
```
2. `_resolve_task_transition`の呼び出し（`:9723`）を以下へ変更する：
```python
_resolve_task_transition(state, transition, structured_redirect=_pending_redirect)
_maybe_resume_forward_focus(state, _conn, _run_id)
_maybe_clear_resolved_companion(state, _conn, _run_id)
```

### なぜこれがBL-190の`_reconcile_current_phase_after_replan`と衝突しないか

BL-190のヘルパーは異なるトリガー（`task_planner_node`、`phases`が新しく再構築されたときのみ）で
発火し、既に権威のある`current_task_id`から`current_phase`を*再導出*するだけ ——
*どの*タスクがcurrentであるべきかは決して決めない。我々の機構は`decision_extractor_node`
（BL-024のdocstring `:9410`に従う既存の唯一の書き手の場所）からのみ実行され、
`current_task_id`+`current_phase`を常に一緒に、原子的に変更するだけである。
両者はターン内で厳密に逐次的（`task_planner_node` → ... → `decision_extractor_node`）であり、
決して並行しないので二重書き込みの競合はない。両者が相互作用する唯一の箇所：
ラン途中の再計画（BL-190のパターン2/3）が`task_focus_stack`が非空の*間に*起きた場合、
`_maybe_resume_forward_focus`の`_find_phase_containing_task`は、保存された（古いかもしれない）
`phase_id`を信頼せず、*現在の*`state["phases"]`からスタックされたタスクのフェーズを新たに
再解決する —— これがスタックエントリの`phase_id`が「監査/ログ用のみ、実際の書き込みには
決して信頼しない」と文書化されている理由である。パターン3（スタックされたタスクが再計画で
文字通り削除された）は、スタックをクリアして警告を出すことで優雅に劣化し、
クラッシュしたりBL-190のバグクラスを静かに再導入したりするのではなく、BL-190自身の
パターン3の扱い（クリアしてLLMに再決定させる）をミラーする。

## 5. 復帰・前進のセマンティクス（項目5への具体的な回答）

- **セット**：`task_focus_stack`は`_apply_backward_redirect`でのみエントリを得る。
  これは`structured_redirect["decision_type"] == "redirect_backward"`のとき
  `_resolve_task_transition`から呼ばれる。
- **読み取り／トリガー**：`_maybe_resume_forward_focus`は、すべての
  `decision_extractor_node`呼び出しで無条件に呼ばれ（`user_decision_extractor`と
  `expert_decision_extractor`の両グラフノードが同じ関数を経由する）、
  `_is_task_completed(conn, run_id, current_task_id)`をチェックする ——
  BL-176が前進の離脱を判定するのに既に使っているのとまったく同じBL-167の基準である。
  リダイレクト先タスクに対するStage3の`write_agreement(Approved)`は*同じ*User AIターンの
  より早い段階で起きる（Stage3はStage4の前に実行され、両方が1回の
  `generate_user_utterance`呼び出しの中、`decision_extractor_node`が実行される前にある）
  ため、復帰は手戻りが承認されたまさにそのターンで発火できる —— 追加のラウンドトリップ
  レイテンシはない。
- **クリア**：`stack.pop()`はちょうど1回、`_maybe_resume_forward_focus`（自動）または
  `_force_resume_forward_focus`（手動のエスケープハッチ、§8）の中で起きる。
  他のどこでもクリアされない —— 他のコードパスは`task_focus_stack`に直接触れることを
  許されず、「誰がこのフィールドを書くか」を`current_task_id`の既存のBL-024不変条件と
  同じくらい狭く保つ。
- **両端での通知**：`task_focus_redirect_notice`（出て行くときにセット）と
  `task_focus_resume_notice`（戻ってくるときにセット）は、新しいプロンプト注入ヘルパー（§6）が
  消費するone-shotフィールド —— BL-190が`task_reassigned_after_replan_notice`に使うのと
  同じパターンである。

## 6. Detector/Expert側の統合

### 後方リダイレクトの場合：既存のタスク単位機構を再利用し、one-shotの「移動しました」通知だけを追加

`current_task_id`が正規に過去タスクと等しくなるため、`call_expert`（`:6034`）と
`call_detector`（`:6461`）は既に`_build_task_scope_context`/`_get_current_task`を通じて
プロンプト全体を正しいタスクの周りに構築する —— コアのタスクスコーピングロジックへの
変更はゼロで必要ない。唯一の新しい統合点は、なぜ突然古いタスクを見ているのかを
*彼らに*伝えることであり、それによりトーン／コメントが混乱して聞こえないようにする
（「待って、このタスクは既に完了してるんじゃないの？」）。

新ヘルパー（`_build_task_transition_blocked_notice`の近く, `:2954`へ配置）：
```python
def _build_task_focus_transition_notice(state: LineageState) -> str:
    """[BL-191] _apply_backward_redirect/_maybe_resume_forward_focus/_force_resume_forward_focusが
    直後に発火した場合、次のExpert/User AIターンへ一度だけ明示する通知
    （_build_task_transition_blocked_noticeと同じone-shot消費パターン、ただし別関心事のため
    別関数として独立させる——あちらはBL-125/176/190の「遷移をブロックした」通知、こちらは
    BL-191の「遷移を実際に行った/戻した」通知で意味が逆であり、混在させると読みにくくなる）。
    """
    redirect_notice = state.get("task_focus_redirect_notice")
    if redirect_notice:
        state["task_focus_redirect_notice"] = ""
        return f"\n【🧭 {redirect_notice}】\n"
    resume_notice = state.get("task_focus_resume_notice")
    if resume_notice:
        state["task_focus_resume_notice"] = ""
        return f"\n【🧭 {resume_notice}】\n"
    return ""
```

**3つ**の呼び出し箇所へ配線する（2つはUser AI向けの既存の
`_build_task_transition_blocked_notice`呼び出し箇所`:8047`と`:8389`、
3つ目は新規 —— `call_expert`も必要である。過去タスクの内容を実際にやり直すよう
求められるのはExpertだからである）：
- `generate_user_utterance` Stage4（`:8047`, `_transition_notice`と並べて）
- `generate_user_utterance`のもう一方（非Stage4パイプライン）の分岐（`:8389`）
- `call_expert`（`:6034`）、既存の`deferred_notes_block`構築（`:6237-6242`）と並べて挿入

### ジョイントフォーカスの場合：新しい追加ブロック、Expert/Detector/Stage1で再利用

新ヘルパー（`_get_deferred_notes_text`の近く, `:4612`へ配置）：
```python
def _get_task_focus_companion_text(state: LineageState) -> str:
    """[BL-191] task_focus_companionが設定されていれば、Expert/Detector/User AI Stage1へ
    追加のコンテキストとして注入するブロックを返す。BL-025のスコープガードレールは維持する
    （current_task_json等の「現在のタスク」定義自体は一切変更しない、あくまで並記情報）。
    """
    companion = state.get("task_focus_companion")
    if not companion:
        return ""
    return (
        f"🔗 【BL-191: 今回併せて考慮すべき関連タスク（あなたの担当タスクはあくまで現在のタスクのみです）】\n"
        f"task_id={companion['companion_task_id']}: {companion['reason']}\n"
        "このタスク自体の成果物を今すぐ書き換える必要はありません（それは発注者が別途"
        "redirect_backwardで正式に指示します）。ただし、現在のタスクの検討・監査において"
        "この関連タスクとの整合性を意識してください。\n"
    )
```

注入箇所（すべて既存の`deferred_notes_block`スタイルのパターンを再利用する。
つまり呼び出しごとに1回計算し、既存の`deferred_notes_block`が既に現れる場所へ連結する）：
- `call_expert`（`:6237-6242`, `deferred_notes_text`と並べて、その後`:6513/6772/6933`で使用）
- `call_detector`（`:6510-6513`, 同じパターン）
- `generate_user_utterance` Stage1（`:7842-7845`, そのステージの既存の`deferred_notes_block`と並べて）

これはまさにユーザーが求めた「追加的／明示的なコンテキストであり、既存のスコーピングの
全面的な除去ではない」形である：`_build_task_scope_context`の`current_task`/
`current_task_json`/`acceptance_criteria`/`whiteboard_text`は完全に手つかずであり、
companionブロックは新しい、明確にラベル付けされた、別の段落である。

### リダイレクトの場合、`_build_stale_past_tasks_text`（Stage4限定の広いビュー、§3/§7）

新ヘルパー（`_get_forced_escalated_issues_text`の近く, `:4681`へ配置）。
ユーザーの明示的な「Stage4に特化したスコープ付き例外」の決定に従い、
意図的に`call_expert`/`call_detector`へは配線**しない** —— Stage4へのみ配線する：
```python
def _build_stale_past_tasks_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-191] BL-163が起票したseverity="minor"の整合性再確認issue（
    topic LIKE "goal_revision_consistency_check_%"）のうち、まだstatus='open'のものを
    task_id単位で一覧化する。BL-186が発見した「read_issuesがpull型のため誰にも見られない」
    問題への、Stage4限定の能動的サーフェシング（BL-186自体は無変更、並存させる。§7参照）。
    """
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='open' "
        "AND topic LIKE 'goal_revision_consistency_check_%' ORDER BY task_id, id",
        (run_id,)
    ).fetchall()
    if not rows:
        return ""
    lines = [f"- task_id={r['task_id']}: {r['description']}" for r in rows]
    return (
        "【🧭 BL-191/163: ゴール改定により整合性未確認のまま残っている過去タスク】\n"
        "これらは強制ではありませんが、必要と判断すればschedule_task_focus"
        "(decision_type=\"redirect_backward\")で今すぐ手戻り対応するか、"
        "joint_focusで現在のタスクと併せて考慮対象にできます。\n"
        + "\n".join(lines) + "\n"
    )
```

## 7. 既存機構との相互作用

| 機構 | 変更 | 理由 |
|---|---|---|
| **`write_agreement` SUPERSEDE**（`_commit_agreement_from_tool`, `_write_agreement_impl`のBL-146ゲート`:2511-2532`） | **コード変更なし。** | リダイレクトにより`current_task_id == task_y_y`となれば、`_effective_current_task_id_from(state)`（`:3074-3089`）は既に`task_y_y`を返すので、BL-146のゲート（`tid != effective_current_task_id`）は`action_type="UPDATE"`に対して通常どおり通過する。SUPERSEDEは、ターンを丸ごと消費するフォーカス切替に値しない軽量なタスク横断の修正のために、従来どおり利用可能なまま残る。 |
| **BL-163/168のフラグ付け**（`_revise_goal_tool_impl`, `:1944-2041`） | **コード変更なし。** | `goal_revision_consistency_check_*` minor issueの唯一の*ソース*として残る。新規：`_build_stale_past_tasks_text`（§6）がこれらを初めてStage4へ能動的にサーフェスし、BL-186が文書化したまさにそのギャップ（`log/2026-08-06/1432`、ランが既にphase 6を過ぎていたため到達不能だった13件のフラグ付きタスク）を、BL-163/168自体には触れずに埋める。 |
| **BL-186の`plan_revision_reason`経路**（`generate_user_utterance_node`, `:8604-8617`） | **並存、無変更。** | BL-186はすべての`revise_goal`成功時に無条件で発火し、Stage4がフラグされたissueに気づいて`redirect_backward`で対処するかどうかに関わらず、*新しい*再検証タスク／フェーズを強制する。これはユーザーが保持を求めた「Stage4が能動的に捕まえないものへの安全網」として正しい —— Stage4がフラグされたタスクに対して`schedule_task_focus`を一度も呼ばなくても、BL-186の追加専用の新フェーズ経路が最終的にそこへ到達する。優先度の衝突なし：BL-186は新しい前進フェーズを*追加*するだけで`current_task_id`に触れない。BL-191は`current_task_id`を*リダイレクト*するだけでフェーズを追加しない。 |
| **BL-145のsevere/escalated滞留issue経路**（`reflection_node`, `_formalizable_stale`） | **並存、無変更。** | `severity='major'`/`status='escalated'`のissueに対し、まったく異なるコードパス（`plan_revision_issue_ids` → `task_planner_node`）で動作し、この設計がStage4へサーフェスする`severity='minor'`のBL-163 issueとは重ならない。issueはmajor（BL-145の領分、新規タスク化を強制）かminor（BL-163の領分、今やStage4からリダイレクトの可能性も見える）のどちらかである。リダイレクト先タスクの手戻りが*それ自体*新しいmajor/escalated issueを生んだ場合、BL-145の既存機構が今日とまったく同じようにそれを拾う。`task_focus_stack`とは直交する。 |
| **`arbiter_node`/`phases_to_revise`** | **相互作用なし、スコープ外。** | BL-041ドラフトによれば依然として死んだコードパスであることを確認済み。この設計はそれを配線しようとしない（別BLになる。より完全な再設計はBL-041自身のドラフトを参照）。 |

## 8. リスク／安全ガードレール

1. **深さ上限 = 1**（`task_focus_stack`）：二重に強制する —— ツール実装層
   （`_schedule_task_focus_tool_impl`、スタックが非空ならLLMに見えるエラーで拒否）と、
   state書き込み層でもう一度防御的に（`_apply_backward_redirect`、非空スタックで
   どうにか到達した場合はログ警告付きで静かにno-opする —— 将来それを直接呼びうる
   コードパスに対するベルト＆サスペンダー）。
2. **回数上限**（`task_focus_redirect_count`, 既定5/run）：`facilitation_count`/
   `plan_revision_count`の既存の数値上限（`:9907-9913`, `:8777`）をミラーする。
   `facilitation_count`のハードな`state["halt"]=True`とは異なり、この上限を超えても
   *ツール*が`success:False`を返すだけである —— スケジューリングの利便機能のために
   ラン全体を停止させるのではなく、Stage4は`joint_focus`（依然として有用、
   `current_task_id`のリスクなし）へ劣化する。リダイレクトの濫用はファシリテーションの
   デッドロックより低severityなので、これはファシリテーターより意図的に柔らかい失敗モードである。
3. **ピンポン制限**：新しい`redirect_backward`はスタックが空の間しか受け付けられず、
   スタックは完了（`_maybe_resume_forward_focus`）または明示的な放棄（`force_resume`）でしか
   空にならないため、リダイレクトごとに「行って戻る」の完全な往復が必須の作業単位となる ——
   無限のA↔B↔A↔Bのフリップフロップは構造的に不可能であり、最悪ケースは
   `_MAX_TASK_FOCUS_REDIRECTS`回の逐次的な往復で、その後ツールが拒否し始める。
4. **行き詰まった後方手戻りのエスケープハッチ**（項目8の「リダイレクト先タスク自身の手戻りが
   BL-125/176でブロックされたらどうなるか」への直接の回答）：`decision_type="force_resume"`は、
   Stage4が未解決の後方フォーカスを明示的に放棄してフォワードタスクへ戻ることを許す。
   コストは(a)`scheduling_drafts`の監査証跡行と、(b)放棄されたタスクに対する新鮮なminorな
   `issue_log`エントリの自動再作成（BL-163が既に使っているのと同じ`revise_goal_auto`スタイルの
   内部ロール、`_check_issue_permission` `:2189`経由）であり、未解決の懸念が静かに失われる
   ことはない —— それは単に新しいBL-163スタイルのフラグ付きアイテムとなり、
   将来のターンで`_build_stale_past_tasks_text`が再サーフェスする。
5. **ネストは明示的に不許可、`joint_focus`は明示的に深さ上限の対象外**：`joint_focus`は
   `current_task_id`/`task_focus_stack`に決して触れないので、`redirect_backward`が現在
   アクティブかどうかに関わらず自由に宣言できる —— テストはこの組み合わせ
   （リダイレクトがアクティブ＋3つ目のタスクに対するjoint_focusの宣言）をカバーし、
   相互汚染がないことを確認すべきである。
6. **AGENTS.md §7の注記**：`SCHEDULE_TASK_FOCUS_TOOL`と`scheduling_drafts`テーブルは
   新しいインターフェース面であり、AGENTS.md:149がフラグする厳密な意味での「重要な定数」
   （バッファサイズ／タイムアウト／プロトコルマジック値）ではないが、ツールスキーマ自体は
   BL-041ドラフト自身の§5.1が事前確認のためにフラグしたまさにその種の「重要なインターフェース」
   である —— そのドラフトが`resource_claims`について推奨したのと同様に、実装前に
   ツールスキーマ（decision_type enum、フィールド名）についてユーザーの短い明示的な承認を推奨する。

## 9. 実装ファイルリスト、必要なテスト、段階的ロールアウト

### 触れるファイル
- `cela_main.py` —— 上記のすべての変更（stateフィールド、DBテーブル、CRUD、ツールスキーマ、
  `TOOL_DISPATCH`エントリ、ツール実装、`_resolve_task_transition` + 5つの新ヘルパー、
  `decision_extractor_node`、`generate_user_utterance`/`generate_user_utterance_node`の
  Stage4配線、`call_expert`/`call_detector`の注入箇所、`run_ai_vs_ai_loop`の初期化ディクショナリ）。
- `docs/design/back_log/BL-191/BL191_basic_design.md`（新規）—— リポジトリの慣例に従い、
  この計画の最終承認版をCELA自身のドキュメント形式で書き起こす
  （~150以上で実装されたすべてのBLは`BL-NNN_basic_design.md`を持つ、例：BL-190のもの）。
- `docs/design/back_log/issue_backlog.md` —— 実装後に新しい`| BL-191 | ... |`行を、
  この調査中に読んだBL-186/163/176行のまさに簡潔だが完全なナラティブスタイルに従って追加。
- `tests/`配下の新しいテストファイル、`test_bl176_task_transition_requires_approval.py`/
  `test_bl190_current_phase_reconcile_after_replan.py`の慣例に従う（フィクスチャベースの
  新しいsqlite DB、直接的な関数呼び出し、実LLM呼び出しなし ——
  `_query_and_parse_with_retry`/`query_AI`はオフラインテストでは行使されず、
  決定論的なPython側のロジックのみをテストする）。

### 推奨される新テストファイル（オフライン、LLM呼び出しなし）

1. **`tests/test_bl191_schedule_task_focus_tool.py`** —— `_schedule_task_focus_tool_impl`の
   単体テスト：非userロールに対する権限拒否；ターゲットにDeliverableがない場合の
   `redirect_backward`拒否；スタックが非空のときの拒否（深さ上限）；
   `_MAX_TASK_FOCUS_REDIRECTS`超過時の拒否；存在しない／自己companionに対する
   `joint_focus`拒否；成功パスが正しい`scheduling_drafts`行と正しい
   `_LAST_SCHEDULING_DECISION`の形を書くこと。
2. **`tests/test_bl191_backward_redirect_and_resume.py`** ——
   `_apply_backward_redirect`/`_maybe_resume_forward_focus`/`_force_resume_forward_focus`の
   単体テスト：pushがスタック+current_task_id/current_phaseを正しくセットすること；
   二重pushが警告付きでno-opすること；復帰が*フォーカス中の*（フォワードではない）タスクに
   対して`_is_task_completed`が真のときのみ発火すること；復帰がフェーズを新たに再解決すること
   （pushと復帰の間にBL-190スタイルのフェーズ再編成をシミュレートし、正しいフェーズが
   見つかることを確認）；スタックされたtask_idが`phases`にもう存在しないとき復帰が
   優雅にno-op+クリアすること（パターン3のアナログ）；`force_resume`が無条件でpopし
   フォローアップのminor issueを作ること。
3. **`tests/test_bl191_joint_focus_companion.py`** ——
   `_apply_joint_focus`/`_maybe_clear_resolved_companion`/`_get_task_focus_companion_text`の
   単体テスト：正しくセット／クリアされること；companionタスクが`_is_task_completed`に
   なったら自動クリアされること；テキスト注入ヘルパーが未設定時は空文字列を、
   設定時は正しいブロックを返すこと。
4. **`tests/test_bl191_decision_extractor_structured_redirect.py`** ——
   `decision_extractor_node`を直接呼ぶ統合スタイルのテスト（`test_bl176`の`_base_state`
   フィクスチャパターンをミラー）で、`state["pending_task_redirect"]`を事前に設定し、
   `call_decision_extractor`をモック／スタブして（既存のテストが自由文脈`transition`抽出を
   スタブするパターンを示している —— `test_bl139_transition_fallback_from_directive.py`を
   確認せよ）以下を確認する：構造化リダイレクトが競合する自由文脈`advances_to_task_id`より
   優先されること；`pending_task_redirect`が1ターン後に消費される（`None`にリセットされる）こと；
   `redirect_backward`中に離脱する（一時停止する）タスクに対してBL-125/176の離脱ゲートが
   *呼ばれない*こと（意図的なバイパスの回帰防止）。
5. **`tests/test_bl191_stale_past_tasks_and_scheduling_drafts.py`** ——
   `get_latest_scheduling_decision`/`get_scheduling_decision_history`/
   `record_scheduling_decision`のCRUD往復テスト（`goal_drafts`のテストカバレッジがあれば
   それをミラー、なければ`test_bl163`のDBフィクスチャスタイルに倣う）；
   `_build_stale_past_tasks_text`がBL-163でフラグされた行に対して期待されるグループ化された
   テキストを返し、openなものがないときは空文字列を返すこと。
6. **回帰パス**：既存の`test_bl125_*`, `test_bl176_*`, `test_bl146_*`, `test_bl167_*`,
   `test_bl190_*`スイートが無修正でグリーンのまま残ること —— これらは*通常の*前進遷移パス
   （`structured_redirect`なし）が1バイトも変わっていないことを検証する。
   `_resolve_task_transition`の新しいパラメータは`None`をデフォルトとし、
   新しい`if structured_redirect:`ブロックは不在時にはno-opだからである。

### 段階的ロールアウト（BL-186/187/188/189がそれぞれ独立して出荷可能なスライスとして
どうスコープされたかをミラー）

- **Phase 1（最小スライス、単独で価値を出荷）：** `joint_focus`/`clear_companion`のみ ——
  `task_focus_stack`なし、リダイレクトなし、復帰なし、`force_resume`なし。
  これだけでユーザーが述べた「混乱した同時のつぶやき」問題を*一般的な*ケースについて修正し
  （`current_task_id`に触れずにcompanionタスクをフラグする）、最も低リスクなスライスである
  （`current_task_id`のBL-024唯一の書き手不変条件に決して触れない）。含まれるもの：
  新しいstateフィールド`task_focus_companion`/`pending_task_redirect`
  （decision_typeは当面joint_focus/clear_companionに限定）、`scheduling_drafts`テーブル+CRUD、
  `SCHEDULE_TASK_FOCUS_TOOL`（2つが未配線でもスキーマは4つのenum値をすべて事前宣言して
  出荷できるが、このフェーズでは2つに削るのを推奨 —— Stage4が実装前に`redirect_backward`を
  試みるのを避けるため）、`_get_task_focus_companion_text` + 3つの注入箇所、
  `_build_stale_past_tasks_text`。
- **Phase 2：** `redirect_backward` + 機械的な`_maybe_resume_forward_focus`、深さ1上限、
  回数上限。これはよりリスクの高いスライス（`_resolve_task_transition`の既存パスの外で
  `current_task_id`に触れる）—— Phase 1のオフラインスイートと少なくとも1回の実LLM
  ドライランが`joint_focus`が一貫して振る舞うことを確認した後にのみ出荷する。
  CELAの確立された「オフライン先、その後ドライラン」検証の実践に従う
  （BL-186/163の「実ドライランでの効果確認は次回待ち」の注記を参照）。
- **Phase 3：** `force_resume`安全弁 —— Phase 2と一緒に、あるいはその少し後に出荷できる。
  実ドライランが「行き詰まった後方手戻り」シナリオが実際に到達可能であることを示したら
  （延期できるほど稀であることが判明するかもしれない）。
- **明示的に延期／この設計のスコープ外：**`arbiter_node`/`phases_to_revise`の配線
  （BL-041自身の未実装ドラフト）；`whiteboard_drafts`/SUPERSEDEへの変更；
  BL-145/163/168/186自体への変更。

---

### 実装のための重要ファイル

- `c:\ai_work\CELA\cela_main.py`（すべてのstate/DB/ツール/`_resolve_task_transition`/
  `decision_extractor_node`/Stage4の変更 —— 単一ファイルのモノリス）
- `c:\ai_work\CELA\docs\design\back_log\BL-190\BL190_basic_design.md`
  （クリーンに合成しなければならない；BL-190が先に着地して行番号がずれる場合に備え、
  実装時に再読すること）
- `c:\ai_work\CELA\docs\design\back_log\issue_backlog.md`
  （BL-163/168/176/186/190のエントリは、この設計が退行させてはならない権威ある挙動仕様）
- `c:\ai_work\CELA\docs\design\r1_r2_r3b_core\cela_facilitator_arbiter_redesign_BL041.md`
  （エスカレーションメニュースタイルのツール設計とAGENTS.md §7の事前承認注記の先例）
- `c:\ai_work\CELA\tests\test_bl176_task_transition_requires_approval.py`
  （新しいBL-191テストファイルのためのテストハーネス規約テンプレート）

---

# 【第2部】ユースケース通しトレースによる修正（バグ①〜⑥）

ユーザー指示により、以下の全経路を1ステップずつトレースして検証した結果、
第1部の設計に**6件のバグ・抜けを発見**したため、以下の修正を第1部に優先して適用する。

## バグ①【重大】早すぎる自動復帰

**問題**：第1部§5の復帰判定は`_is_task_completed`のみを条件にしているが、
**BL-163でフラグされた過去タスクはステータス上まだ`Approved`のまま残っている**
（BL-163は`issue_log`にminor issueを起票するだけで、agreementのstatusは一切変更しない）。
そのため、redirect直後・Expertが何も手を付けていない次の`decision_extractor_node`呼び出しの
時点で即座に「完了済み」と誤判定され、**redirectがその場で無効化される**。
これは`redirect_backward`機能そのものが実運用の典型ケースで機能しないことを意味する。

**対策**：`task_focus_stack`のエントリ形状を以下へ拡張する（第1部§1の形状を上書き）：

```python
{"task_id": str,          # 復帰先（中断されたフォワードタスク）
 "phase_id": str,         # 監査用参考のみ。復帰時は必ずtask_idから再解決する
 "reason": str,
 "pushed_at_round": int,  # 監査・デバッグ用途のみ（ロジックでは使わない）
 "focused_task_id": str,  # redirect先の過去task_id（復帰判定に使う）
 "baseline_agreement_id": str}  # redirect時点でのfocused_taskの最新Deliverable agreement_id
```

復帰条件を以下へ変更する：
```
_is_task_completed(focused_task_id)
かつ _find_active_deliverable_agreement(...)['id'] != baseline_agreement_id
```
（＝redirect後に実際に新しいDeliverableが作られ、それが承認された場合のみ復帰）。

`task_focus_companion`も同型の理由で`baseline_agreement_id`を持たせ、
`_maybe_clear_resolved_companion`も同じbaseline比較にする（バグ⑥）。

## バグ②【重大】BL-190のパターン3との相互作用で永久迷子

**問題**：redirect中にreflection→`plan_revision_reason`→task_planner再構成が起き、
その再構成が**現在フォーカス中の過去タスク自体**を消した場合、BL-190の
`_reconcile_current_phase_after_replan`は`current_task_id`を空文字列にクリアする。
すると`_maybe_resume_forward_focus`は`_is_task_completed("")`を評価し続けることになり
（恒久的にFalse）、`task_focus_stack`に積まれた元のフォワードタスクへ
**二度と復帰できなくなる**（BL-167と同型の永久迷子事故）。

**対策**：
1. BL-190の`_reconcile_current_phase_after_replan`のパターン3分岐（`current_task_id`を
   クリアする箇所）に、`task_focus_stack`が非空なら**その場で強制的にpopして復帰させる**
   処理を追加する（`_force_resume_forward_focus`を再利用し、理由を
   「計画再構成によりフォーカス中のタスクが消失したため」とする）。
2. あわせて`_maybe_resume_forward_focus`にも防御的に、
   「`current_task_id`が空、またはfocused_task_idが`state["phases"]`に存在しない場合は強制pop」
   の分岐を置く（二重の安全網）。**ただしこの分岐は既存の`if not stack: return`の後に置く**
   （スタックが空なら何もしない、が先）。

この相互作用はBL-190・BL-191のどちらの単体テストでも捕まらないため、
**両方をまたぐ結合テストを必須項目とする**。

## バグ③ Detectorがredirect状況を把握できない

**問題**：第1部§6は`_build_task_focus_transition_notice`（one-shot通知）をExpertには
注入するが、Detectorには注入していない。またone-shot通知だけでは、Detectorがredirect中の
2ターン目以降に「なぜ既に承認済みのはずのタスクが再提出されているのか」を見失う。

**対策**：`call_detector`（両パス）へ`_build_task_focus_state_text`（常設表示、
Stage4と同じヘルパーを再利用）を注入し、「このタスクは発注者の判断で一時的に再検討中で
あり、過去に承認済みであることを理由に差し戻さないこと。判断すべきは今回の再提出内容が
redirectの理由（reason）に応えているかである」という趣旨の指示を添える。

## バグ④ user_detectorがスケジューリング判断自体を監査できない

**問題**：Stage4が`schedule_task_focus`を呼んだターンでは、`user_detector`は
`_resolve_task_transition`が走る**前**に発火するため、現行設計では判断の存在自体を知らない。

**対策**：`state["pending_task_redirect"]`（このターンではまだ未消費）を`call_detector`の
target_role="user"向けコンテキストへ表示し、「この巻き戻し判断が妥当か（理由が具体的か、
対象task_idが本当に影響を受けているか）」も監査対象に含める。ただしBL-042の教訓に従い
機械的ゲートは追加せず、プロンプト誘導のみとする。

## バグ⑤ Reflection/Facilitatorが状況を把握できない

**問題**：どちらも現状`task_focus_stack`/`task_focus_companion`を見ておらず、
「既に承認済みのタスクが再度動いている」状況をでっちあげ監査・迎合監査・stagnant判定で
誤解する恐れがある（例：同じタスクが何度も再提出されるのを「膠着」と誤判定する）。

**対策**：`call_reflection`/`call_facilitator`へも`_build_task_focus_state_text`を注入し、
「フォーカス切替中の再作業は正常な手戻りであり、膠着ではない」旨を明示する。

## バグ⑥ joint_focusの早期クリア

バグ①と同型。`_maybe_clear_resolved_companion`もbaseline比較を導入する（上記①に統合）。

## 追加：`_build_task_focus_state_text`（第1部で言及されていたが詳細未定義）

```python
def _build_task_focus_state_text(state: LineageState) -> str:
    """[BL-191] task_focus_stack/task_focus_companionの"現在の状態"を毎ターン明示的に
    描画する常設ステータス表示。state上に値があるだけではLLMのプロンプトには自動的に
    現れないため、明示描画が必須。one-shotの_build_task_focus_transition_noticeとは別物で、
    こちらはredirect_backward中は毎ターン繰り返し表示し続ける。
    """
```
注入先：Stage4、`call_detector`（両パス、バグ③）、`call_reflection`・`call_facilitator`
（バグ⑤）。`_build_stale_past_tasks_text`と`_build_scheduling_history_text`は
ユーザー承認済みの方針どおり**Stage4にのみ**注入する（Expert/Detectorには見せない）。
`_build_task_focus_state_text`だけは「今どういう状態か」を知らせるだけであり、
BL-025が防ごうとしている「他タスクのowns_variablesへの踏み込み」には当たらないため共有する。

## ユースケース通しトレース結果（修正後の想定挙動）

**ケースA: 正常な巻き戻し往復**
1. ゴール改定 → BL-163が過去タスクへminor issue起票（既存動作、無変更）
2. Stage4が`_build_stale_past_tasks_text`でそれを見る → `schedule_task_focus
   (redirect_backward, target=task_2_1)` 呼び出し ✅（新規、可視化あり）
3. 同ターンの`user_detector`：`pending_task_redirect`を見て判断の妥当性を監査 ✅（バグ④修正）
4. `user_decision_extractor`：構造化決定を消費 → `_apply_backward_redirect`でpush＋切替。
   `baseline_agreement_id`を記録 ✅（バグ①修正）。BL-125/176の離脱ゲートは意図的にバイパス
5. `orchestrator`：`current_task_id=task_2_1`を見て適切な専門家を選ぶ ✅（無変更で動作）
6. `expert`：`_get_current_task`がtask_2_1を返す＋one-shot通知で経緯を把握 ✅。
   `write_agreement(UPDATE, task_id="task_2_1")` はBL-146ガードを正常通過 ✅
7. `expert_detector`：`_build_task_focus_state_text`で「一時再検討中」を把握、過去に承認済み
   であることを理由に差し戻さない ✅（バグ③修正）
8. `expert_decision_extractor`：`_maybe_resume_forward_focus`は
   baseline比較で「新Deliverableはあるがまだ未承認」→ 復帰しない ✅（バグ①修正）
9. User AIへ復帰：Stage1-3でレビュー・承認（`_build_task_focus_state_text`で状況把握 ✅）
10. `user_decision_extractor`：baseline比較で「新Deliverableが承認された」→ 自動pop、
    `current_task_id`が元のフォワードタスクへ復帰、resume通知セット ✅
11. 次ターンのStage4：resume通知＋`_build_task_focus_state_text`（スタック空）を見て、
    通常の次タスク指示へ戻る ✅

**ケースB: 巻き戻し中にreflectionが発火** → `_build_task_focus_state_text`により
「手戻り中＝正常」と判定でき、膠着と誤判定しない ✅（バグ⑤修正）

**ケースC: 巻き戻し中にfacilitatorが発火** → 同上 ✅（バグ⑤修正）

**ケースD: 巻き戻し中にtask_plannerが発火（再構成）**
- フォーカス中タスクが新計画にも残っている場合 → BL-190が`current_phase`を追随、
  `_maybe_resume_forward_focus`は`_find_phase_containing_task`で毎回再解決するため無事 ✅
- **フォーカス中タスクが消えた場合** → BL-190のパターン3が`current_task_id`をクリア →
  以前は永久迷子だったが、バグ②対策で強制pop＋復帰 ✅
- **復帰先（スタック上のフォワードタスク）が消えた場合** → `_find_phase_containing_task`が
  Noneを返し、スタックのみクリア＋警告（BL-190のパターン3と同じ縮退）✅

**ケースE: 巻き戻し中にSUPERSEDEが飛ぶ** → SUPERSEDEはBL-146ガード対象外で元々どこからでも
呼べるため、`current_task_id`の状態に関わらず影響なし ✅（無変更）

**ケースF: joint_focus中にExpertが併記タスクを直そうとする**
→ `_get_task_focus_companion_text`に固定文言として
「併記対象タスク自体の成果物を修正する必要がある場合は`action_type='SUPERSEDE'`を使うこと
（現在のタスクではないため通常のUPDATEはBL-146ガードに拒否されます）」を含める
（ユーザー指摘：joint_focus中にExpertが併記タスクを直そうとしてUPDATEを使い、BL-146の
拒否エラーに戸惑う事故を未然に防ぐため）。`redirect_backward`側は`current_task_id`が
正規に過去タスクへ切り替わるため通常のUPDATEで問題なく、この注意は不要。✅

**ケースG: 巻き戻し先が行き詰まる（task_2_1自身に未解決issueが積み上がる）** →
`force_resume`で打ち切り可能、対象は新minor issueとして再記録 ✅

---

# 【第3部】独立レビュー（別AI）への対応

別AIによる設計レビューを受け、全指摘をコードと照合して検証した。
**妥当7件を反映、偽陽性3件を記録**する。

## 反映した指摘

### R-1【指摘4-1】`force_resume`をPhase 3からPhase 2へ前倒し

第1部§9では`force_resume`をPhase 3に置いていたが、`redirect_backward`だけを先に出すと、
巻き戻し先の過去タスク自身が未解決issueを抱えて再承認できなくなった場合に
**スタックから抜ける手段が一切なくなり、ランが恒久的に過去タスクへ張り付いたままになる**
（安全弁のないデッドロック）。安全弁は機能本体と同時にリリースするのが正しい。

**修正後のロールアウト**：
- **Phase 1**：`joint_focus`/`clear_companion`のみ（第1部§9と同じ）
- **Phase 2**：`redirect_backward` + `_maybe_resume_forward_focus` + **`force_resume`（同時必須）**。
  **BL-190の実装が前提**（バグ②対策がBL-190の実装箇所への追記を含むため）。
  現状BL-190は設計のみで未実装であることをコードで確認済み
  （`cela_main.py:8850-8852`は旧コード`state["current_phase"] = phases[0]`のまま）。
- Phase 3は廃止（Phase 2へ統合）。

### R-2【指摘6-1/6-2】ツール配線に必要な変更箇所の完全な列挙

`_LAST_GOAL_REVISION`と同型のブリッジグローバルパターンは、**6箇所すべて**を変更しないと
機能しない（`revise_goal`の既存実装を実際に追跡して確認）：

1. **ツールスキーマ定義**：`SCHEDULE_TASK_FOCUS_TOOL`（`WRITE_ISSUE_TOOL`近辺）
2. **`TOOL_DISPATCH`登録**（`cela_main.py:3092-3133`）
3. **ツールリストへの追加**：Stage4の`tools=[THINK_TOOL]`
   （`cela_main.py:8107`と`cela_main.py:8114`の**両方**、コードで確認済み）を
   `tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL]`へ。
   **あわせてStage4プロンプト末尾の固定文言「あなたが使えるツールはthinkのみです」
   （`cela_main.py:8093`付近）も更新必須**（矛盾したまま残るとLLMがツールを呼ばない）
4. **グローバル宣言＋リセット＋ツールハンドラ分岐**：
   - 宣言：`_LAST_SCHEDULING_DECISION: dict | None = None`（`_LAST_*`クラスタ内）
   - **リセット**：`cela_main.py:3284-3292`の`global`文と初期化ブロック
     （`_LAST_GOAL_REVISION = None`の隣）へ追加。
     **これを忘れると前回のquery_AI呼び出しの決定が次の呼び出しへ漏れる**
   - **ツールハンドラ分岐**：`cela_main.py:3752`付近の
     `elif tc.function.name == "revise_goal":`と同型の分岐を追加し、
     `result`の成功時に`_LAST_SCHEDULING_DECISION`へ詰める
   - getter：`get_last_scheduling_decision()`
5. **`_absorb_stage_trackers`への追加**（`cela_main.py:7830-7836`）：
   Stage1〜4は個別の`query_AI`呼び出しであり毎回グローバルがリセットされるため、
   既存の段階横断トラッカー集約へ
   `_stage_scheduling_decision = _stage_scheduling_decision or get_last_scheduling_decision()`
   を追加し、関数末尾で書き戻す。**これを忘れるとStage4の決定が
   `generate_user_utterance_node`に届かない**
6. **`generate_user_utterance_node`での橋渡し**（`cela_main.py:8591`付近）

**非Stage4 User AIパス（`cela_main.py:8484`）へのツール追加は行わない**：
このパスはessence_dialogue・Expert相談応答・差し戻し・終盤・初回ターン用であり、
いずれも「次タスクをどうするか」を決める場面ではないため、スケジューリングツールを
渡す必要はない（BL-192のプロンプト指示は逆に**両パスへ**入れる、後述）。

### R-3【指摘6-3】`target_role == "user"`ガードが必須

`decision_extractor_node`は`user_decision_extractor`と`expert_decision_extractor`の
**両方のグラフノードで共用**されている（`cela_main.py:10170`/`cela_main.py:10177`で
同一関数を2回登録）ことをコードで確認した。`pending_task_redirect`はUser AIのStage4が
設定するものなので、既存の`target_role`判定（`cela_main.py:9492-9497`）を使って
**`target_role == "user"`の場合のみ消費する**。

さらに、`user_detector`がmajor判定で`generate_user_utterance`へ差し戻した場合、
User AIが再発言してもツールを呼び直さない限り`_LAST_SCHEDULING_DECISION`はNoneのままなので、
`state["pending_task_redirect"]`には1回目の（撤回されたかもしれない）決定が残る。
この滞留を避けるため、**`generate_user_utterance_node`は毎回
`state["pending_task_redirect"]`を`get_last_scheduling_decision()`の結果で上書きする**
（Noneならクリアする）方式にし、「そのターンのUser AIが実際に呼んだ決定のみが有効」を保証する。
（第1部§3の`if _scheduling_decision:`条件付き代入を、無条件代入へ変更する。）

### R-4【指摘6-4】`structured_redirect`と`transition`の優先関係の明文化

`structured_redirect`が非Noneかつ`redirect_backward`/`force_resume`の場合、
**既存の`advances_to_task_id`/`advances_to_phase_id`（自由文脈抽出）は完全に無視される**
（構造化決定が優先、その場で`return`）。`joint_focus`/`clear_companion`の場合のみ
`current_task_id`を動かさないため、既存の自由文脈遷移ロジックへ処理を継続する。
（第1部§4のコードはこの通りに書かれているが、意図として明文化しておく。）

### R-5【指摘3-2】`task_focus_redirect_count`のリセット方針の明文化

このカウンタは**run単位の累積であり、pop時もリセットしない**
（`plan_revision_count`・`facilitation_count`と同じ設計）。
「1ランで巻き戻しは最大5往復まで」が意図であり、往復ごとにリセットすると無制限になり
上限の意味が失われるため。この非リセットは意図的な設計であることをコードコメントにも明記する。

### R-6【指摘6-6】`scheduling_drafts.content`合成の仕様

`goal_drafts`の`content`はLLMが直接書く文書だが、`scheduling_drafts`の`content`は
`record_scheduling_decision`内部で構造化列から機械合成する。合成フォーマットは
人間・LLM双方が読める1行形式とし、`decision_type`ごとに文面を変える
（例：`redirect_backward`なら「[v3] task_4_1を中断し、task_2_1へ一時的にフォーカスを
切り替えた。理由: ...」、`joint_focus`なら「[v4] task_5_1の作業中、task_1_2を併記検討対象に
指定した。理由: ...」）。構造化列（`decision_type`/`primary_task_id`/`companion_task_id`）が
常に正であり、`content`はあくまで表示用の副次的サマリー
（`_build_scheduling_history_text`がこれを読んでStage4へ提示する）。
テストでは4種の`decision_type`すべてについて、構造化列と`content`の内容が一致することを
確認する。

### R-7【指摘6-5】`call_reflection`/`call_facilitator`への注入箇所の具体化

第2部バグ⑤で追加した`_build_task_focus_state_text`の注入箇所を具体的に指定する：
- `call_reflection`：プロンプトのf-string組み立て箇所（`cela_main.py:7364`付近）で、
  `_build_agreements_context`の直後（＝プロジェクト全体状況を提示している箇所の隣）
- `call_facilitator`：`essence_dialogue_active`分岐・通常分岐の両方で、
  BL-188で追加したツール列挙ブロックの直前
- `call_detector`：既存の`deferred_notes_text`と並べて（`cela_main.py:6510-6513`）

## 偽陽性（コードと照合して否定、同じ誤読を繰り返さないための記録）

- **【指摘3-1】「`_apply_backward_redirect`が`current_phase`を更新しない」**：
  第1部§4のコードは`state["current_phase"] = target_phase`を明示的に含んでいる。
  指摘は設計書の読み落とし。
- **【指摘4-2】「`current_task_id==""`で誤popするリスク」**：
  `_maybe_resume_forward_focus`は冒頭で`if not stack: return`する。
  スタックが空なら何も起きず、スタックが非空で`current_task_id`が空の場合にpopするのは
  **バグ②対策の意図通りの動作**（永久迷子の防止）。ただし第2部バグ②の記述で
  「既存の`if not stack: return`の後に置く」ことを明示した。
- **【指摘9】「`_find_phase_id_for_task`が既に同等機能を持つ」**：
  コード確認の結果、`_find_phase_id_for_task`（`cela_main.py:9024`）は`str`（phase_id）を、
  `_find_task_by_id`（`cela_main.py:9035`）はタスク本体を返す。
  `state["current_phase"]`への代入には**フェーズ辞書そのもの**が必要なため、
  `_find_phase_containing_task`は新規に必要。ただし命名の一貫性の観点から、
  この3関数は隣接配置し、docstringで相互参照させる。

## 追加テスト項目（第1部§9のリストへ追加）

7. **`_build_task_focus_state_text`往復確認**：`redirect_backward`適用直後の`state`を
   `expert_decision_extractor`相当（`_maybe_resume_forward_focus`が完了条件未達で
   no-opする状態）まで模擬的に進めても`task_focus_stack`の中身が変わらないこと、
   `_build_task_focus_state_text`がその状態を正しくレンダリングすること、
   新Deliverableが承認されると次の`decision_extractor_node`呼び出しで
   自動的にpopされ、テキストも「復帰済み」側に変わることを確認する。
8. **【バグ①回帰テスト】早期復帰の防止**：redirect先が既に`Approved`状態のまま
   （BL-163でフラグされただけでstatusは未変更＝実運用の典型ケース）の状態で
   `redirect_backward`し、Expertがまだ何も提出していない時点で
   `_maybe_resume_forward_focus`を呼んでも**復帰しない**こと。その後、新しい
   Deliverableを作って承認して初めて復帰することを確認する。
9. **【バグ②回帰テスト】BL-190との結合**：`redirect_backward`中に、フォーカス中の
   task_idを含まない新`phases`で`task_planner_node`（BL-190のパターン3経路）を走らせ、
   `task_focus_stack`が永久に残らず強制popで復帰することを確認する。復帰先も同時に
   消えた場合はスタックのみクリアされ警告が出ることも確認。**この2機構をまたぐ結合
   テストは必須**（単体テストでは捕まらないため）。
10. **【バグ③④⑤回帰テスト】各ノードへの状況共有**：`call_detector`（両パス）・
    `call_reflection`・`call_facilitator`のプロンプト組み立て結果に
    `_build_task_focus_state_text`の内容が含まれること、`user_detector`向けに
    `pending_task_redirect`が表示されることをソース/実行の両面で確認。
11. **【バグ⑥回帰テスト】companionの早期クリア防止**：宣言時点で既にcompleted状態の
    companionを`joint_focus`し、`_maybe_clear_resolved_companion`が即座にクリアしない
    こと（baseline比較が効いていること）を確認。
12. **【R-2回帰テスト】ツール配線の完全性**：`_LAST_SCHEDULING_DECISION`が
    `_query_AI_live`のリセット対象に含まれること、Stage4のツールリストに
    `SCHEDULE_TASK_FOCUS_TOOL`が含まれること、Stage4プロンプトに
    「使えるツールはthinkのみ」という矛盾した文言が残っていないことをソース確認する。
13. **【R-3回帰テスト】`target_role`ガード**：`expert_decision_extractor`相当の
    呼び出し（`target_role == "expert"`）では`pending_task_redirect`が消費されないこと、
    User AIが再発言時にツールを呼ばなかった場合`pending_task_redirect`がクリアされること。

## 未決事項（ユーザー確認推奨）

- `SCHEDULE_TASK_FOCUS_TOOL`のスキーマ（`decision_type` enum・フィールド名）は、
  BL-041ドラフトが`resource_claims`について推奨していたのと同様、AGENTS.md §7の「重要な
  インターフェース変更」に近い性質があるため、実装着手前に最終スキーマの一言承認を推奨。
- Phase分割（Phase 1 → Phase 2）の順で進めるか、一括実装するか。
- BL-190を先に実装するか（Phase 2の前提）。

## 検証方針

1. `python -m py_compile cela_main.py`
2. 新規テスト（1〜13）がオフラインで全件通過
3. 既存の関連テスト（BL-024/125/145/146/163/167/168/176/186/190系）が無改修で通ること
4. フルオフラインスイート実行、無退行確認
5. Phase 1完了後、実ドライランで`joint_focus`が実際にDetector/Expertの発言の一貫性を
   改善するか確認。Phase 2完了後、`redirect_backward`→`_maybe_resume_forward_focus`の
   往復が実ログで正しく機能するか確認（次回以降でよい）

---

# BL-192（予定）: User AI Stage4の指示文を強化し、根拠不明な数値のweb_search義務化・
期待される思考プロセスの明示を徹底する

## Context

BL-191の設計中、ユーザーから追加の要望が出た（原文）：「ユーザーAIプロンプトにも、
『過去タスクの洗い直しをする』とか『次のタスクと過去タスクは依存関係にあるから、過去タスクも
同時に検討せよ』とか、agreementを書くときの注意、例えば過去タスクを書き換える時はSUPERSEDEに
しないと、書き換えできないとか、次タスクでは根拠があいまいな数値や前提・条件があるからまずは
web検索を用いて情報をしらべて、『もっともらしさ』を排除しろとか、次のタスクのこれをやれ、
だけではなくて、網羅的にエキスパートAIにどういう思考で、どう行動してほしいかをユーザーAIが
指示する部分も強化したい」。

このうち「過去タスクを書き換える際のSUPERSEDE注意」はBL-191の`joint_focus`機能に直接
組み込んだ（第2部ケースF参照）。残る2点——①根拠不明な数値・前提のweb_search義務化、
②期待される思考プロセスの網羅的な明示——はBL-191のスケジューリング機構（redirect_backward/
joint_focus）の有無に関わらずStage4の指示文全般に当てはまる独立した関心事であり、
**別BL（BL-192）として切り出す**（ユーザーへの提案・合意事項）。BL-191と同じ箇所
（Stage4）に触れる実装のため、実装タイミングはBL-191と合わせて行う想定。

## 設計方針

新規の状態・ツール・DBスキーマは不要。BL-188が既に確立した「プロンプト誘導のみ（機械的な
強制ゲートは追加しない）」という標準方針（Detectorの硬直判定によるトークン浪費事故＝BL-042
の再発防止という設計判断）をそのまま踏襲し、Stage4のシステムプロンプト
（`generate_user_utterance`、`cela_main.py:8046-8095`付近）へ指示ブロックを追加するのみ。
BL-094の「【最低限】」型ソフト必須パターン、BL-188の「学習知識を無検証で断定しない」型
検索義務パターンをそのまま再利用する。

### 1. 根拠不明な数値・前提のweb_search義務化

Stage4のプロンプトへ以下の趣旨を追加する：

> 次タスクの指示を書く際、そのタスクが依存する確定値（verified_facts/agreementsの
> citations）に`type="web"`の裏付けがなく`expert_calculation`/`goal_text`のみの場合、
> 指示文の中で「このタスクの前提となる◯◯の数値はまだ一次情報での裏付けがないため、
> web_searchで検証してから進めること」と具体的に名指しで指示すること。Expertが
> 『もっともらしい』値を無検証のまま踏襲することを許容しない。

実装時に、Stage4が`_build_agreements_context_from_db`（BL-188のcitations表示を含む、
`type="web"`裏付けの有無を判別可能）を受け取っているかを該当箇所を再読して確認する
（Stage3では受け取っていることを確認済み。Stage4も同じなら追加のコンテキスト注入は不要）。

### 2. 期待される思考プロセスの網羅的な明示

Stage4の指示文が「次はtask_x_xをやれ」という成果物名の羅列に留まらないよう、以下を追加：

> 次タスクの指示は、成果物の完成条件（acceptance_criteria）を並べるだけでなく、
> どのような順序・観点で検討すべきかを明示すること。例：「まず◯◯の実測/公的統計を確認し、
> 次に△△との整合性を検算し、最後に□□の受入基準を満たすか確認せよ」。特に、直前のタスクや
> 併記対象タスク（task_focus_companion）との依存関係がある場合は、それらの確定値との
> 整合性確認を思考プロセスの一部として明記すること。

### 3.【独立レビュー指摘7-2対応】非Stage4 User AIパスにも同じ指示を入れる

当初「Stage4のプロンプト1箇所のみ」としていたが、コード確認の結果、User AIには
**Stage4を通らない別パス**（`cela_main.py:8484`）が存在し、以下の場合にそちらが
実行されることを確認した：essence_dialogue中／Expert相談への応答／
**`constraint_issue == "major"`による差し戻し**／終盤ターン／初回ターン。

特に**差し戻しターン**は、User AIが指示を出し直す重要な場面であるにもかかわらず、
Stage3/Stage4をスキップするため、BL-192の指示（根拠不明値のweb_search義務化・思考プロセス
明示）が一切適用されない。これは実害があるため、**両パスへ同じ指示ブロックを注入する**。

実装上は、指示文を`_BL192_DIRECTIVE_QUALITY_BLOCK`のようなモジュール定数として1箇所に
定義し、Stage4側（`cela_main.py:8093`付近の3分岐共通の`+=`箇所）と
非Stage4側（`system_prompt_trailing`、BL-185の並び順設計に従い末尾寄り）の両方から
参照する（文言の二重管理を避けるため）。

## 実装ファイル

- `cela_main.py`：Stage4のシステムプロンプト＋非Stage4 User AIパスの`system_prompt_trailing`
  （計2箇所、共通定数を参照）への追記のみ。新規関数・新規state・新規DBスキーマなし。
- 新規テスト `tests/test_bl192_stage4_directive_quality.py`：Stage4プロンプトのソース確認
  （web_search義務化・思考プロセス明示の文言が含まれること）、**非Stage4パスにも同じ
  定数が注入されていることの確認（独立レビュー指摘7-2の回帰防止）**、既存BL-177/178/185
  関連のStage4テストが無退行であること。

## 検証方針

1. `python -m py_compile cela_main.py`
2. 新規テスト・既存Stage4関連テストが無退行
3. 実ドライランで、Stage4の指示文に実際にweb_search名指し・思考プロセスの明示が
   現れるか確認（プロンプト誘導のみのため、効果測定は次回以降のドライランで行う）
