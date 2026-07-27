# BL-096: 監査系ノードの軽微な指摘（observations/minor）を追跡するissue管理DBの新設

基本設計書 v3（最終版・実装対象）。v1→v2→v3の改訂理由は[D-079](../../decision_log.md#d-079-bl-096設計をv2に改訂read経由の再発カウント追加severitymajorstatusescalated不変条件topictask_idキー変更)・[D-080](../../decision_log.md#d-080-bl-096設計をv3に改訂重複検知キーをtopic単独に差し戻しreflectionfacilitatorへの機械的接続とエスカレーション解除通知を追加)参照。関連: [issue_backlog.md BL-096](../issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は設計時点のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## Context

BL-095完了後の棚卸しで、情報の抽出・保存・伝搬に関する2つの穴が見つかった：

1. Detectorの`observations`（軽微な気づき、BL-051）は`agreements`/`verified_facts`のどちらにも保存されず、`detector_observations_log`という状態リスト（DB非永続）に積まれるだけで、`_build_detector_observations_block`が直近3件しかプロンプトに戻さない。それより古い気づきは実質的に消滅する。
2. `constraint_issue`（Detectorの判定、none/minor/major）は`constraint_issue_log`という状態リストに積まれるが、`major`だけが`reflection`向けの`major_issues`テキストブロックとして読み出され、`minor`は記録されるだけで再監査・再浮上の保証がない。後続タスクで実は重大だったと判明しても、拾い上げる仕組みがない。

ユーザーは両者を「正式なissue管理DBの不在」という同じ根本原因として統合し、Detectorのobservationsと`minor`追跡漏れの両方をカバーする新設DB＋ツールの設計を依頼した（BL-096）。既存の`agreements`（決定の確定管理）・`verified_facts`（確定値のキャッシュ）とは役割を分け、本DBは「まだ解決していない懸念の追跡」に特化する。

### v2→v3の変更点（本改訂、最終）

v2は別AIレビュー（`BL096_design_review.md`）の指摘Aを採用し重複検知キーを`(topic, task_id)`にしたが、レビュー会話の中で**この変更がBL-096の目的そのものと矛盾する**ことが判明した：BL-096は「タスクをまたいで再発する懸念」を追跡するためのものなのに、`task_id`をキーに含めると別タスクでの再発が別行として扱われ、絶対にエスカレーションしなくなる。加えて、READ経由の再発カウント（v2で追加）は「別タスクの文脈で同じissueが再発見された」ことを検知する設計なので、CREATE側の検索キーに`task_id`が入っていると整合しない。この矛盾を解消し、以下を確定した（詳細な経緯は[D-080](../../decision_log.md#d-080-bl-096設計をv3に改訂重複検知キーをtopic単独に差し戻しreflectionfacilitatorへの機械的接続とエスカレーション解除通知を追加)）：

1. **重複検知キーを`topic`単独に差し戻す**（v1に戻す。`task_id`/`phase_id`はメタデータとして保持するのみ）。
2. **READ経由の再発カウント条件を厳格化**: `topic_keyword`と`task_id`の両方が明示的に指定され、かつヒット行の`status`がopen/escalated、かつ`last_seen_task_id`と異なる場合のみカウントする（詳細§4）。`list_all`や`task_id`単独・`phase_id`単独の閲覧はカウント対象外とし、「意図的にこの特定の懸念を確認した」場合のみ再発シグナルとして扱う。
3. **reflectionへの機械的接続**: `issue_log`に`status='escalated'`の行が1件でもあれば、reflectionの`discussion_status`をモデルの判定に関わらず機械的に`"stagnant"`へ上書きする（§5）。
4. **facilitatorへの構造化データ注入**: facilitatorにもreflectionと同じPython側の直接DB問い合わせでescalated issueの構造化情報（topic/description/occurrence_count）を渡し、facilitatorのプロンプトに「この具体的な懸念の解消を最優先事項として提示する」専用の指示ブロックを追加する（§5）。
5. **エスカレーション解除の明示的な復帰通知**: escalated issueが解決されゼロ件になった瞬間を検知し、次のExpert/User AI呼び出しのプロンプトに一度だけ「エスカレーションは解消された、通常のタスク遂行に戻ってよい」という復帰通知を機械的に注入する（§6）。

### ユーザーの追加指示（設計判断の根拠、v1〜v3共通）

- 再浮上（エスカレーション）は**累積回数しきい値**方式を採用する（時限方式ではなく）。モデルの判断に依存せず、Python側で機械的に重大度を引き上げる（BL-093/095と同じ「機械的強制」路線。BL-099が指摘した「thinkの最終的な実効性がモデル遵守に依存する」という弱点を、issue管理の文脈では作らないようにする）。
- 書き込み権限（`write_issue`ツール）は、最終的には監査系ノード全般に拡張する予定だが、**MVPではDetectorとUser AI（`generate_user_utterance`）の2ノードに限定**する。理由：(a) User AIがExpertへ出す訂正指示（訂正内容）自体を見落とし・忘却するリスクがあり、これもissue化する価値がある、(b) issueを実際に解決済みと判断してクローズする役目はUser AI（ユーザー側の代理）であるとユーザー自身が認識している。したがって`RESOLVE`アクションはUser AI限定、`CREATE`はDetector・User AI両方に許可する。

## 設計

### 1. 新規テーブル `issue_log`

`init_db`（`cela_main.py`内、既存の`agreements`/`verified_facts`/`plan_drafts`と同じ関数）に追加。既存テーブルと同じ`run_id`スコープ・インデックス設計を踏襲：

```sql
CREATE TABLE IF NOT EXISTS issue_log (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    topic TEXT NOT NULL,             -- 固定の検索可能な短い識別文字列（重複検知キー本体。write_agreementのtopic/target_topicと同じ規約）
    raised_by TEXT NOT NULL,         -- 'detector' or 'user'（自動バックアップ書き込みは 'detector_auto'）
    phase_id TEXT DEFAULT '',        -- メタデータ（識別キーには使わない）
    task_id TEXT DEFAULT '',         -- メタデータ（識別キーには使わない。最初に起票されたtask_id）
    severity TEXT NOT NULL DEFAULT 'minor',   -- 'minor' / 'major'
    status TEXT NOT NULL DEFAULT 'open',      -- 'open' / 'escalated' / 'resolved'（severity='major'はstatus='escalated'を必ず伴う不変条件、詳細§2）
    description TEXT NOT NULL,       -- 2000文字上限、超過分はトランケーション（詳細§2）
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    last_seen_task_id TEXT DEFAULT '',   -- 直近にこのissueを再発見/再発報告したtask_id（再発カウントの二重計上防止用、詳細§4）
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    resolved_by TEXT DEFAULT '',
    resolved_at REAL,
    resolution_note TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_issue_run_topic ON issue_log(run_id, topic);
CREATE INDEX IF NOT EXISTS idx_issue_run_status ON issue_log(run_id, status);
```

`agreements`・`verified_facts`（`_ensure_verified_facts_r3a_columns`マイグレーションパターン）と並べて`init_db`内に追加する。新規テーブルなのでマイグレーション関数は不要（`CREATE TABLE IF NOT EXISTS`のみ）。

**重複検知キー（v3で確定）**: `topic`単独。`task_id`/`phase_id`はメタデータとして保持するが識別には使わない。理由はv2→v3の変更点(1)を参照——BL-096は「タスクをまたいで再発する懸念」の追跡が目的であり、`task_id`をキーに含めると別タスクでの再発が検知できなくなるため。「AIがtopic文字列を微妙に変えて一致しなくなる」リスク（別AIレビュー指摘A自体の懸念）には、プロンプト指示（topicは一度決めたら固定し、`read_issues`で類似表現がないか事前確認する）で対応する。

### 2. `write_issue`ツール（CREATE = 起票・再発、RESOLVE = 解決）

新規`WRITE_ISSUE_TOOL`スキーマ（`WRITE_AGREEMENT_TOOL`と同じ形式で定義）：

```python
WRITE_ISSUE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_issue",
        "description": (
            "軽微な懸念・気づき・訂正指示を、後続タスクからも検索可能な形で記録する（issue_logテーブル）。"
            "同じtopicで再度CREATEすると自動的に「再発」として扱われ、累積回数が2回に達すると"
            "システムが自動的にseverity='major'・status='escalated'へ引き上げる（この昇格は"
            "モデルの判断に依存せず機械的に行われる。read_issuesでtopic_keywordとtask_idを指定して既存issueを"
            "再発見した場合も同様に再発カウントされるため、re-CREATEを省略しても再発の検知自体は失われない）。"
            "'topic'は一度決めたら変えない固定の短い識別文字列にすること（write_agreementのtopic/target_topicと"
            "同じ規約）。再登録する前に、まずread_issuesで似た表現の既存issueがないか確認すること。"
            "[BL-096] CREATEはdetector/user、RESOLVEはuserのみ許可。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ["CREATE", "RESOLVE"]},
                "topic": {"type": "string", "description": "固定の検索可能な識別文字列。既存issueの再発検知・解決に使う（一度決めたら変えないこと）"},
                "severity": {"type": "string", "enum": ["minor", "major"], "description": "CREATE時のみ有効。通常はminor"},
                "description": {"type": "string", "description": "CREATE時必須。何が問題か・何を訂正指示したか"},
                "phase_id": {"type": "string"},
                "task_id": {"type": "string"},
                "resolution_note": {"type": "string", "description": "RESOLVE時必須。どう解決したか"}
            },
            "required": ["action_type", "topic"]
        }
    }
}
```

`_write_issue_impl(args, conn, run_id, caller_role, phase_id, task_id)`（`_write_agreement_impl`と同じ構造で新設）：

1. `action_type`必須チェック・enum検証。
2. 権限チェック（新規`_check_issue_permission(args, caller_role)`、`_check_write_permission`と同型）：
   ```python
   ALLOWED_ISSUE_ACTIONS_BY_ROLE = {
       "detector": {"CREATE"},
       "user": {"CREATE", "RESOLVE"},
   }
   ```
3. `CREATE`の場合：
   - `description`必須。
   - `SELECT * FROM issue_log WHERE run_id=? AND topic=? AND status != 'resolved'`で既存行を検索（**キーは`topic`単独**）。
   - 既存行があれば「再発」として扱う：共通ヘルパー`_bump_issue_occurrence(conn, run_id, row, new_task_id=task_id)`を呼ぶ（§4で詳述、`occurrence_count += 1`・`last_seen_task_id`更新・閾値判定）。加えて`description`を追記（改行区切りで既存＋新規を連結）。**`description`の全長が2000文字を超えた場合、古い方を切り詰め末尾に`...(truncated, N occurrences)`を付加する**（`N`は`occurrence_count`）。`updated_at`更新。
   - 既存行がなければ新規INSERT（`status='open'`, `occurrence_count=1`, `last_seen_task_id=task_id`, `severity`は引数指定どおり、デフォルト`'minor'`。ただし引数`severity="major"`が明示された場合は不変条件により`status='escalated'`も同時設定）。
4. `RESOLVE`の場合：
   - `resolution_note`必須。
   - `SELECT * FROM issue_log WHERE run_id=? AND topic=? AND status != 'resolved'`で対象行を検索、無ければエラー。
   - 見つかれば`status='resolved'`, `resolved_by=caller_role`, `resolved_at=now`, `resolution_note`を設定。
   - **解除通知トリガー（§6）**: この`RESOLVE`によって`issue_log`の`status='escalated'`行が run_id全体で0件になった場合、`state["escalation_just_resolved"]`相当の通知フラグを立てる（ツールハンドラは`state`に直接触れないため、戻り値に`{"escalation_cleared": True}`を含め、呼び出し元ノードがこれを見てstateへ反映する）。
5. 戻り値は`{"success": True/False, ...}`（`_write_agreement_impl`と同じ形。RESOLVE成功時は追加で`escalation_cleared: bool`を含む）。

`TOOL_DISPATCH`に追加：
```python
"write_issue": lambda args: _write_issue_impl(
    args, get_active_conn(), _CURRENT_RUN_ID, _CURRENT_CALLER_ROLE, _CURRENT_PHASE_ID, _CURRENT_TASK_ID
),
```

### 3. `read_issues`ツール（読み取り、Detector/User AI向け）

`read_open_issues`（初期案）から改名。「openのものしか見えない」という誤解を避けるため。同様にDB問い合わせヘルパーも`get_issues_from_db`とする。

```python
READ_ISSUES_TOOL = {
    "type": "function",
    "function": {
        "name": "read_issues",
        "description": (
            "issue_logから懸念・訂正指示を検索する。topic_keyword/task_id/phase_idのいずれかを指定した場合、"
            "status（open/escalated/resolved）を問わず一致した行を返す（resolved行にはresolution_noteが含まれる"
            "ため、既に解決済みかどうかがその場で分かり、無駄な再登録を避けられる）。"
            "list_all=trueを指定した場合はフィルタを無視し、このrunの全issueを返す（issue整理・棚卸し専用。"
            "通常の重複確認にはtopic_keyword等のフィルタ検索を使うこと）。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic_keyword": {"type": "string", "description": "topic・descriptionの部分一致検索"},
                "task_id": {"type": "string"},
                "phase_id": {"type": "string"},
                "list_all": {"type": "boolean", "description": "true の場合、他のフィルタを無視してこのrunの全issueを返す（デフォルトfalse）"}
            }
        }
    }
}
```

`_read_issues_handler(args)`（`_read_verified_fact_handler`と同型）:

1. `list_all=true`なら他の引数を無視し、`run_id`に紐づく全行を返す（status問わず、再発カウントは発生しない）。
2. それ以外で`topic_keyword`/`task_id`/`phase_id`のいずれかが指定されていれば、`topic`と`description`列の両方に対するLIKE検索、および`task_id`/`phase_id`の完全一致を組み合わせて検索する。**status（resolvedを含む）で絞り込まない**（デフォルトで解決済みも含める）。
3. **再発見時の機械的再発カウント（§4で詳述）**: `topic_keyword`と`task_id`が両方とも指定されている場合のみ、ヒットした行のうち`status IN ('open','escalated')`かつ`last_seen_task_id`が今回の`task_id`と異なるものに対し`_bump_issue_occurrence`を呼ぶ。
4. 何も指定されず`list_all`もfalseなら`{"status": "error", "message": "topic_keyword/task_id/phase_idのいずれか、またはlist_all=trueを指定してください。"}`を返す。
5. 結果が空なら`{"status": "not_found", ...}`を返す。

新規`get_issues_from_db(conn, run_id, topic_keyword=None, task_id=None, phase_id=None, list_all=False)`ヘルパーを定義。

### 4. 再浮上（エスカレーション）トリガーの詳細仕様

**背景**: v1は`write_issue(CREATE)`の再呼び出しのみに依存していたが、AIが`read_issues`で既存issueを確認した際「登録済みだから再登録不要」と判断してCREATEを見送ると、再発シグナルが失われる。これに対処するため、CREATE経由・READ経由の二重トリガーとする。ただしREAD側は無条件にすると、無関係な広いキーワード検索が偶然ヒットしただけでもカウントされてしまう誤爆リスクがあるため、v3では条件を厳格化した。

共通ヘルパー`_bump_issue_occurrence(conn, run_id, row, new_task_id)`:
```python
occurrence_count = row["occurrence_count"] + 1
last_seen_task_id = new_task_id
if occurrence_count >= 2:
    severity = "major"
    status = "escalated"
else:
    severity = row["severity"]
    status = row["status"]
# UPDATE issue_log SET occurrence_count=?, last_seen_task_id=?, severity=?, status=?, updated_at=? WHERE id=?
```

**トリガー1: CREATE経由**（`write_issue(action_type="CREATE")`が既存`topic`にヒットした場合）
- 無条件に`_bump_issue_occurrence`を呼ぶ（`task_id`が前回と同じでも別でも関係ない）。
- 理由: CREATEはモデルが能動的に「このtopicをもう一度書く」と選んだ行為そのものが強いシグナルであり、同一タスク内での複数回の指摘も「解決されていない」という有効な情報のため、区別せずカウントする。

**トリガー2: READ経由**（`read_issues`呼び出し時）— 以下**4条件すべて**を満たした場合のみ`_bump_issue_occurrence`を呼ぶ：
1. `topic_keyword`が指定されており、かつその行の`topic`または`description`にマッチしている（`list_all`・`phase_id`単独・`task_id`単独の検索は対象外）。
2. `task_id`も同時に指定されている。
3. 指定された`task_id`が、その行の現在の`last_seen_task_id`と異なる。
4. その行の`status`が`open`または`escalated`（`resolved`は対象外）。

**除外される具体例:**
- `list_all=true`での棚卸し閲覧 → 対象外。
- `task_id`のみ指定（topic_keywordなし）→ 対象外（特定の懸念を狙った確認ではないため、そのtask_idに紐づく全issueが誤って一括カウントされるのを防ぐ）。
- 同じタスク内で同じ懸念を繰り返し`read_issues`する（BL-094の毎ターンiter=1チェック等）→ `task_id`が`last_seen_task_id`と同じなので対象外。
- 既に`resolved`の行にヒット → 対象外。

**具体シナリオ**: task_1でDetectorが懸念Xを`write_issue(CREATE)`（`occurrence_count=1`, open）。task_3でUser AIが`read_issues(topic_keyword="X", task_id="task_3")`を呼ぶ → 4条件を満たし`occurrence_count=2`に加算・自動的に`major`/`escalated`へ昇格。AIがここでCREATEを呼ばなくても、確認しただけでエスカレーションが発火する。

### 5. reflection・facilitatorへの機械的接続

**reflection（`call_reflection`/`reflection_node`）**:
1. 既存の`major_issues`抽出（`constraint_issue_log`から`severity=="major"`を抽出）に加え、Python側で`issue_log`の`status='escalated'`行を直接クエリし、`constraint_log_text`に統合する。
2. プロンプトの「未解決が残っていればdiscussion_statusをcompletedにしてはいけない」という既存指示の対象に、issue_log由来のescalated項目も明示的に含める。
3. **機械的上書き（新規、モデル遵守に依存しない保証）**: `call_reflection`の結果を`reflection_node`が受け取った直後、`issue_log`に`status='escalated'`の行が run_id全体で1件でも存在すれば、モデルが何を返したかに関わらず`state["discussion_status"] = "stagnant"`へ強制上書きする。既存の`route_after_reflection`は`discussion_status == "stagnant"`で`facilitator`へルーティングする実装なので、ルーティング側のコード変更は不要。

**facilitator（`call_facilitator`/`facilitator_node`）**:
1. `facilitator_node`でも同じ`issue_log`への直接DB問い合わせ（`status='escalated'`）を行い、`call_facilitator`に新しい引数`escalated_issues_text`として渡す（reflectionの`note`とは別の、topic/description/occurrence_countを機械的に整形したブロック。LLMツール呼び出しではなくPython側の直接注入とする点はreflectionと同じ設計哲学）。
2. `call_facilitator`のプロンプトに新しい節を追加：`escalated_issues_text`が空でない場合、既存の「抽象的に視座を上げて促す」トーンとは別に、**この具体的な懸念（topic・description）を名指しして、その解消を最優先事項として提示する**よう指示する。既存の「〇〇を直ちに決定してくださいという強制的な表現は避ける」という一般方針は、issue_log由来の具体的懸念に対しては適用しない（漠然とした停滞への対応と、特定済みの未解決issueへの対応をfacilitator内で区別させる）。

### 6. エスカレーション解除の復帰通知

**問題**: reflection/facilitatorはExpert/User AIの`current_task_id`等の作業状態そのものは破壊しない（`current_task_id`は`decision_extractor_node`のみが書き込む専有フィールドで、reflection/facilitatorは触れない）。しかしfacilitatorは「視座を上げて本質的な課題を問い直せ」という広い再考を促す設計のため、issueが解決された後もAI同士がその広い問い直しを続けてしまい、通常のタスク遂行にいつ戻ればよいか自力では判断しづらい。

**設計**:
1. `LineageState`に`escalation_active: bool`（デフォルト`False`）を追加。`issue_log`の`status='escalated'`行が run_id全体で1件でも存在する間は`True`。
2. 各ラウンドの冒頭（またはreflection/facilitator実行直後）で`issue_log`の`status='escalated'`件数を再チェックし、直前まで`True`だったものが`0`件になった瞬間を検知したら、`state["escalation_just_resolved_notice_pending"] = True`をセットし、`escalation_active`を`False`に戻す。
3. 次にExpert/User AIが呼ばれる際、`escalation_just_resolved_notice_pending`が`True`ならプロンプトに以下を一度だけ注入し、注入後にフラグを`False`に戻す（繰り返し表示しない）：
   > 【エスカレーション解消】直前まで提起されていた懸念は解決済みです。facilitatorの提起した論点への深掘りは終了し、通常のタスク遂行（現在のtask_id: `<current_task_id>`）に戻ってください。
4. どの懸念が解決されたかを`<topic>`として本文に含める（直近に`resolved`になった行から取得）。

### 7. 既存ログとの関係

`detector_observations_log`/`constraint_issue_log`（state内リスト）はそのまま残す。既存テストがこれらに依存しているため、置き換えではなく**並存**とする。`issue_log`テーブルは「複数ターンをまたいで確実に残したい懸念」専用の追加レイヤーであり、モデルが明示的に`write_issue`を呼ぶ主経路に加え、Python側自動バックアップ（下記）で最低限の記録を保証する。

**機械的バックアップ経路**: `detector_node`のPython側で、モデルが`write_issue`を呼ばなかった場合でも、`result["observations"]`が非空かつ一定長（例: 30文字）以上であれば、`raised_by="detector_auto"`・`topic=f"detector_observation_{task_id}"`（task単位で束ねる粗い集約。複数の異なる観察が同一topicに集約される粗さは許容し、モデル自身の`write_issue`が主経路であることに変わりはない）で自動的に`_write_issue_impl`相当のCREATEを試みる。モデルの判断を上書きするものではなく、モデルが呼ばなかった場合の保険（セーフティネット）に留める。

### 8. ノード配線まとめ

- **`call_detector`**: 既存`tools=[...]`（両パス）に`WRITE_ISSUE_TOOL`・`READ_ISSUES_TOOL`を追加。プロンプトにBL-096オリエンテーション（§2〜4の使い方）を追記。`detector_node`にPython側自動バックアップ書き込みを追加。
- **`generate_user_utterance`**: 既存`tools=[...]`に`WRITE_ISSUE_TOOL`・`READ_ISSUES_TOOL`を追加。プロンプトに、Expertへの訂正指示の記録・BL-094慣例に倣ったiter=1同期チェック・解決時の`RESOLVE`呼び出しを追記。
- **`reflection_node`**: `issue_log`の`status='escalated'`直接クエリ、`constraint_log_text`への統合、`discussion_status`の機械的上書き。
- **`facilitator_node`**: `issue_log`の`status='escalated'`直接クエリ、`call_facilitator`への構造化データ注入、専用指示ブロック。
- **エスカレーション解除通知**: `escalation_active`/`escalation_just_resolved_notice_pending`のstate管理、Expert/User AI呼び出し直前への一度きりの注入。

### 9. BL-100（エスカレーション根拠の構造化）との関係

BL-100（前提を疑った際の「疑った前提・疑った理由・代替仮説・期待される利点・採用に必要な追加情報」の5項目セット）は、本BL-096の`issue_log`とは別ツール（`escalate_premise_concern`、BL-086）が起点であり、対象範囲も異なる（BL-096＝Detector/User AIの軽微な懸念・訂正指示、BL-100＝ゴールの前提そのものへの疑義）。統合するかは別途BL-100の設計時に検討する。

## 対象ファイルまとめ

- `cela_main.py`:
  - `init_db`に`issue_log`のCREATE TABLE追加。
  - 新規`WRITE_ISSUE_TOOL`/`READ_ISSUES_TOOL`スキーマ定数。
  - 新規`_write_issue_impl`, `_check_issue_permission`, `_read_issues_handler`, `get_issues_from_db`, `_bump_issue_occurrence`, `_get_escalated_issues`（`status='escalated'`直接クエリの共通ヘルパー、reflection/facilitator両方から使う）。
  - `TOOL_DISPATCH`へ`write_issue`/`read_issues`追加。
  - `call_detector`・`generate_user_utterance`の`tools=[...]`拡張とプロンプト追記。`detector_node`にPython側自動バックアップ書き込みを追加。
  - `LineageState`に`escalation_active`/`escalation_just_resolved_notice_pending`フィールド追加。
  - `call_reflection`/`reflection_node`: `constraint_log_text`へのescalated issue統合、`discussion_status`の機械的上書き。
  - `call_facilitator`/`facilitator_node`: escalated issueの構造化注入、専用指示ブロック。
  - `call_expert`/`generate_user_utterance`（またはその手前の共通プロンプト構築箇所）: エスカレーション解除の復帰通知の一度きり注入。
- `tests/test_bl096_issue_log.py`（新規）: `_check_issue_permission`のロール×アクション直接検証、`_write_issue_impl`のCREATE/RESOLVE/再発時の累積回数・自動昇格ロジック（`topic`単独キー、`severity='major'⇒status='escalated'`不変条件、descriptionトランケーション）をDB経由で検証、`read_issues`のフィルタ挙動（resolved込みデフォルト・`list_all`・description LIKE検索）、READ経由の再発カウントの4条件（`topic_keyword`+`task_id`必須、`last_seen_task_id`比較、resolved除外）、`call_detector`/`generate_user_utterance`が両ツールを`tools=[...]`に渡していることの`inspect.getsource`確認、自動バックアップ書き込みの動作確認、reflectionの機械的上書き、facilitatorの構造化データ注入、エスカレーション解除通知の一度きり注入。
- `docs/design/back_log/issue_backlog.md`: BL-096の状態を本改訂内容で更新。
- `docs/design/decision_log.md`: D-080として、v2→v3の変更点とその理由を記録。

## Verification

1. `python -m py_compile cela_main.py`
2. `tests/test_bl096_issue_log.py`を新規追加し実行。
3. `pytest tests/ -q -k "bl093 or bl094 or bl095 or bl096 or bl087"`で関連クラスタの回帰確認、実装完了後に一度`pytest tests/ -q -k "not live"`をフルで実行。
4. `python scripts/check_docs_consistency.py`で文書間リンク整合性を確認。
5. コミットは実装完了後、ユーザーの明示的な指示を待つ。
