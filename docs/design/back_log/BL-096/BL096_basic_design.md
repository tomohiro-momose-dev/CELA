# BL-096: 監査系ノードの軽微な指摘（observations/minor）を追跡するissue管理DBの新設

基本設計書 v2（別AIレビュー[BL096_design_review.md](BL096_design_review.md)・ユーザー追加指摘を反映して改訂）。関連: [issue_backlog.md BL-096](../issue_backlog.md#bl-096-監査系ノードの軽微な指摘observationsminorを追跡するissue管理dbの新設)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は設計時点のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## Context

BL-095完了後の棚卸しで、情報の抽出・保存・伝搬に関する2つの穴が見つかった：

1. Detectorの`observations`（軽微な気づき、BL-051）は`agreements`/`verified_facts`のどちらにも保存されず、`detector_observations_log`という状態リスト（DB非永続）に積まれるだけで、`_build_detector_observations_block`が直近3件しかプロンプトに戻さない（`cela_main.py:3627-3640`）。それより古い気づきは実質的に消滅する。
2. `constraint_issue`（Detectorの判定、none/minor/major）は`constraint_issue_log`という状態リストに積まれるが（`cela_main.py:6228-6233`）、`major`だけが`reflection`向けの`major_issues`テキストブロックとして読み出され（`cela_main.py:5026-5032`）、`minor`は記録されるだけで再監査・再浮上の保証がない。後続タスクで実は重大だったと判明しても、拾い上げる仕組みがない。

ユーザーは両者を「正式なissue管理DBの不在」という同じ根本原因として統合し、Detectorのobservationsと`minor`追跡漏れの両方をカバーする新設DB＋ツールの設計を依頼した（BL-096）。既存の`agreements`（決定の確定管理）・`verified_facts`（確定値のキャッシュ）とは役割を分け、本DBは「まだ解決していない懸念の追跡」に特化する。

### v1からの主な変更点（本改訂）

- **再登録忌避リスクへの対処**: v1は「累積回数しきい値」によるエスカレーションを、`write_issue(CREATE)`の再呼び出し回数だけに依存させていた。しかしAIが`read_issues`で既存issueの存在を確認した際、「もう登録済みだから再登録は不要」と合理的に判断してCREATEを見送ってしまうと、まさにエスカレーションに必要な再発シグナルが失われる。これに対処するため、**「読み取りで再発見された」こと自体も機械的な再発カウントの対象**とする（詳細は§3）。
- **READ側の既定動作をユーザー指摘で変更**: `read_open_issues`（v1）→`read_issues`（本改訂）に改名し、解決済みissueもデフォルトで検索結果に含める（同じ懸念を抱いたAIが「既に解決済み」と分かれば無駄な再登録を避けられる）。全件を無条件に見たい場合のみ明示的な`list_all`スイッチを使う設計に変更。
- **別AIレビューの高優先度指摘（B）を反映**: `severity='major'`は常に`status='escalated'`を伴う不変条件とし、reflection側のクエリを単純化。
- **別AIレビューの中優先度指摘（A・D）を反映**: 重複検知キーを`topic`単独から`(topic, task_id)`に変更、モデルが`write_issue`を呼ばない場合の機械的バックアップ経路を追加。
- **別AIレビューの低優先度指摘（C・G）を反映**: `description`の肥大防止トランケーション、`description`列もLIKE検索対象に追加。

ユーザーの追加指示（設計判断の根拠）：
- 再浮上（エスカレーション）は**累積回数しきい値**方式を採用する（時限方式ではなく）。モデルの判断に依存せず、Python側で機械的に重大度を引き上げる（BL-093/095と同じ「機械的強制」路線。BL-099が指摘した「thinkの最終的な実効性がモデル遵守に依存する」という弱点を、issue管理の文脈では作らないようにする）。
- 書き込み権限（`write_issue`ツール）は、最終的には監査系ノード全般に拡張する予定だが、**MVPではDetectorとUser AI（`generate_user_utterance`）の2ノードに限定**する。理由：(a) User AIがExpertへ出す訂正指示（訂正内容）自体を見落とし・忘却するリスクがあり、これもissue化する価値がある、(b) issueを実際に解決済みと判断してクローズする役目はUser AI（ユーザー側の代理）であるとユーザー自身が認識している。したがって`RESOLVE`アクションはUser AI限定、`CREATE`はDetector・User AI両方に許可する。

## 設計

### 1. 新規テーブル `issue_log`

`init_db`（`cela_main.py`内、既存の`agreements`/`verified_facts`/`plan_drafts`と同じ関数）に追加。既存テーブルと同じ`run_id`スコープ・インデックス設計を踏襲：

```sql
CREATE TABLE IF NOT EXISTS issue_log (
    id TEXT PRIMARY KEY,
    run_id TEXT NOT NULL,
    topic TEXT NOT NULL,             -- 固定の検索可能な短い識別文字列（write_agreementのtopic/target_topicと同じ規約）
    raised_by TEXT NOT NULL,         -- 'detector' or 'user'（自動バックアップ書き込みは 'detector_auto'）
    phase_id TEXT DEFAULT '',
    task_id TEXT DEFAULT '',
    severity TEXT NOT NULL DEFAULT 'minor',   -- 'minor' / 'major'
    status TEXT NOT NULL DEFAULT 'open',      -- 'open' / 'escalated' / 'resolved'（severity='major'はstatus='escalated'を必ず伴う不変条件、詳細§2）
    description TEXT NOT NULL,       -- 2000文字上限、超過分はトランケーション（詳細§2）
    occurrence_count INTEGER NOT NULL DEFAULT 1,
    last_seen_task_id TEXT DEFAULT '',   -- 直近にこのissueを再発見/再発報告したtask_id（再発カウントの二重計上防止用、詳細§3）
    created_at REAL NOT NULL,
    updated_at REAL NOT NULL,
    resolved_by TEXT DEFAULT '',
    resolved_at REAL,
    resolution_note TEXT DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_issue_run_topic_task ON issue_log(run_id, topic, task_id);
CREATE INDEX IF NOT EXISTS idx_issue_run_status ON issue_log(run_id, status);
```

`agreements`（`cela_main.py:2536`）・`verified_facts`（`cela_main.py:2570`、`_ensure_verified_facts_r3a_columns`マイグレーションパターン）と並べて`init_db`内に追加する。新規テーブルなのでマイグレーション関数は不要（`CREATE TABLE IF NOT EXISTS`のみ）。

**重複検知キーの変更（レビューA反映）**: `write_agreement`周りでBL-053/BL-084が「AIがtopic文字列を微妙に変える」問題に悩まされ、Deliverableでは`(phase_id, task_id)`による識別に移行した前例を踏襲し、`issue_log`の既存行検索は`topic`単独ではなく**`(topic, task_id)`の2列**で行う（`task_id`が空文字のissueは`task_id=''`同士でのみ一致）。

### 2. `write_issue`ツール（CREATE = 起票・再発、RESOLVE = 解決）

新規`WRITE_ISSUE_TOOL`スキーマ（`WRITE_AGREEMENT_TOOL`, `cela_main.py:1068`と同じ形式で定義）：

```python
WRITE_ISSUE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_issue",
        "description": (
            "軽微な懸念・気づき・訂正指示を、後続タスクからも検索可能な形で記録する（issue_logテーブル）。"
            "同じ(topic, task_id)で再度CREATEすると自動的に「再発」として扱われ、累積回数が2回に達すると"
            "システムが自動的にseverity='major'・status='escalated'へ引き上げる（この昇格は"
            "モデルの判断に依存せず機械的に行われる。read_issuesで既存issueを再発見した場合も同様に"
            "再発カウントされるため、re-CREATEを省略しても再発の検知自体は失われない）。"
            "'topic'は固定の短い識別文字列にすること（write_agreementのtopic/target_topicと同じ規約）。"
            "[BL-096] CREATEはdetector/user、RESOLVEはuserのみ許可。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ["CREATE", "RESOLVE"]},
                "topic": {"type": "string", "description": "固定の検索可能な識別文字列。既存issueの再発検知・解決に使う"},
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

`_write_issue_impl(args, conn, run_id, caller_role, phase_id, task_id)`（`_write_agreement_impl`, `cela_main.py:1692`と同じ構造で新設）：

1. `action_type`必須チェック・enum検証。
2. 権限チェック（新規`_check_issue_permission(args, caller_role)`、`_check_write_permission`, `cela_main.py:1487`と同型）：
   ```python
   ALLOWED_ISSUE_ACTIONS_BY_ROLE = {
       "detector": {"CREATE"},
       "user": {"CREATE", "RESOLVE"},
   }
   ```
3. `CREATE`の場合：
   - `description`必須。
   - `SELECT * FROM issue_log WHERE run_id=? AND topic=? AND task_id=? AND status != 'resolved'`で既存行を検索（**キーは`(topic, task_id)`**、レビューA反映）。
   - 既存行があれば「再発」として扱う：`occurrence_count += 1`、`last_seen_task_id`を今回の`task_id`で更新、`description`は追記（改行区切りで既存＋新規を連結）。**`description`の全長が2000文字を超えた場合、古い方を切り詰め末尾に`...(truncated, N occurrences)`を付加する**（レビューC反映、`N`は`occurrence_count`）。`updated_at`更新。
   - **`occurrence_count >= 2`になった時点で機械的に`severity='major'`へ上書き**（呼び出し側が指定した`severity`引数は無視し、Python側の閾値判定を優先する）。
   - 既存行がなければ新規INSERT（`status='open'`, `occurrence_count=1`, `last_seen_task_id=task_id`, `severity`は引数指定どおり、デフォルト`'minor'`）。
   - **不変条件（レビューB反映）: `severity='major'`になった行は、その同じ操作の中で必ず`status='escalated'`も設定する。** これは(a)閾値到達による自動昇格、(b)呼び出し側が最初から`severity="major"`を指定したCREATE、の両方に適用する。これによりreflection側のクエリは単純に`WHERE status='escalated'`だけで全major issueを取得できる（v1では`occurrence_count>=2`昇格時にしか`status='escalated'`を設定せず、初回`major`指定のissueがreflectionに届かない欠陥があった。設計時に発見・修正）。
4. `RESOLVE`の場合：
   - `resolution_note`必須。
   - `SELECT * FROM issue_log WHERE run_id=? AND topic=? AND task_id=? AND status != 'resolved'`で対象行を検索、無ければエラー。
   - 見つかれば`status='resolved'`, `resolved_by=caller_role`, `resolved_at=now`, `resolution_note`を設定。
5. 戻り値は`{"success": True/False, ...}`（`_write_agreement_impl`と同じ形）。

`TOOL_DISPATCH`（`cela_main.py:1757`）に追加：
```python
"write_issue": lambda args: _write_issue_impl(
    args, get_active_conn(), _CURRENT_RUN_ID, _CURRENT_CALLER_ROLE, _CURRENT_PHASE_ID, _CURRENT_TASK_ID
),
```

### 3. `read_issues`ツール（読み取り、Detector/User AI向け）※v1の`read_open_issues`から改名

**改名理由（ユーザー指摘）**: `read_open_issues`という名前は「openのものしか見えない」という誤解を招く。実際には解決済みもデフォルトで返す設計（後述）に変更したため、`read_issues`にする。同様にDB問い合わせヘルパー`get_open_issues_from_db`（v1）も`get_issues_from_db`に改名する。

`READ_VERIFIED_FACT_TOOL`（`cela_main.py:600`）と`get_verified_facts_from_db`（`cela_main.py:3262`）と同じ「keyword/exact-match検索パターン」を踏襲：

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

`_read_issues_handler(args)`（`_read_verified_fact_handler`, `cela_main.py:938`と同型）:

1. `list_all=true`なら他の引数を無視し、`run_id`に紐づく全行を返す（status問わず）。
2. それ以外で`topic_keyword`/`task_id`/`phase_id`のいずれかが指定されていれば、`topic`と**`description`列（レビューG反映）**の両方に対するLIKE検索、および`task_id`/`phase_id`の完全一致を組み合わせて検索する。**status（resolvedを含む）で絞り込まない**（v1の`include_resolved`引数は廃止。デフォルトで解決済みも含める）。
3. **再発見時の機械的再発カウント（§4で詳述）**: 検索が`status IN ('open','escalated')`の行にヒットし、かつヒット行の`last_seen_task_id`が今回の呼び出し元`task_id`（`_CURRENT_TASK_ID`）と異なる場合、`occurrence_count += 1`・`last_seen_task_id`を更新し、`occurrence_count >= 2`なら`severity='major'`・`status='escalated'`へ昇格する（`write_issue(CREATE)`の再発ロジックと同じ閾値判定を共有する内部ヘルパー`_bump_issue_occurrence(conn, run_id, issue_row, new_task_id)`に括り出す）。
4. 何も指定されず`list_all`もfalseなら`{"status": "error", "message": "topic_keyword/task_id/phase_idのいずれか、またはlist_all=trueを指定してください。"}`を返す。
5. 結果が空なら`{"status": "not_found", ...}`を返す（既存パターン踏襲）。

新規`get_issues_from_db(conn, run_id, topic_keyword=None, task_id=None, phase_id=None, list_all=False)`ヘルパーを`get_verified_facts_from_db`（`cela_main.py:3262`）と並べて定義。

### 4. 再浮上（エスカレーション）トリガーの二重化 ── AIの「再登録見送り」対策

**問題（ユーザー指摘）**: v1の設計では、累積回数のインクリメントが`write_issue(CREATE)`の再呼び出しにのみ依存していた。しかしAIが`read_issues`で「既にこのissueは登録済みだ」と分かった場合、合理的な判断として「重複登録は避けるべき」と考えCREATEを呼ばない可能性が高い。そうなると、まさに「同じ懸念が繰り返し発見されている」という最も重要なシグナルが失われ、エスカレーションが機械的に発火しなくなる。

**解決策**: 再発カウントのトリガーを**CREATE経由**と**READ経由**の2系統にする。

1. **CREATE経由**（既存、§2）: 同じ`(topic, task_id)`で`write_issue(CREATE)`が再度呼ばれた場合。
2. **READ経由**（新規）: `read_issues`のフィルタ検索が既存のopen/escalated行にヒットし、かつ`last_seen_task_id`が今回の`task_id`と異なる場合（＝「前回とは別のタスク文脈で、同じ懸念が再び持ち上がった」ことを意味する）。

両方とも同じ`occurrence_count`列・同じ閾値（`>=2`で`major`/`escalated`）を共有する。これにより、AIが「もう登録されているから」とCREATEを見送っても、その懸念を確認する行為（read_issues呼び出し）自体が再発の証拠として機械的に記録され続け、エスカレーションが機能する。

**二重計上の防止**: `last_seen_task_id`との比較により、同一task_id内での複数回の`read_issues`呼び出し（同じノードが同じタスク内で何度もツールループを回す、BL-094の慣例で毎ターンiter=1に読む等）では再発とみなさず、`occurrence_count`は増加しない。異なる`task_id`から到達して初めて「新しい文脈での再発見」としてカウントする。

### 5. ノード配線

- **`call_detector`**（`cela_main.py:4232`、両パスの`tools=[...]`。既存4583行の`tools=`リストに`WRITE_ISSUE_TOOL`・`READ_ISSUES_TOOL`を追加。もう一方のパス（ドメイン妥当性）にも`tools=`があれば同様に追加）。
  - `_CURRENT_CALLER_ROLE = "detector"`は既存のまま（既に設定済み、`cela_main.py:4576-4578`）。
  - プロンプト追記（BL-096オリエンテーション）：`observations`やseverity判定で「今回のターンだけでなく後続タスクでも参照されるべき」と判断した懸念は、`write_issue(action_type="CREATE", topic=<固定識別文字列>, severity="minor", description=...)`を呼んで永続化すること。既に同じ懸念を起票済みかもしれない場合は先に`read_issues`で確認すること（解決済みならresolution_noteが見えるので再登録は不要）。`constraint_issue="major"`の場合も、既存のSUPERSEDE指示（BL-062）に加えて任意で`write_issue`を呼び監査証跡を残してよい（必須ではない）。
  - **機械的バックアップ経路（レビューD反映）**: `detector_node`のPython側で、モデルが`write_issue`を呼ばなかった場合でも、`result["observations"]`が非空かつ一定長（例: 30文字）以上であれば、`raised_by="detector_auto"`・`topic=f"detector_observation_{task_id}"`（task単位で束ねる、複数の異なる観察が同一topicに集約される粗さは許容し、モデル自身の`write_issue`が主経路であることに変わりはない）で自動的に`_write_issue_impl`相当のCREATEを試みる。これはモデルの判断を上書きするものではなく、モデルが呼ばなかった場合の保険（セーフティネット）に留める。

- **`generate_user_utterance`**（User AI、`cela_main.py:5589`付近）。既存`tools=[...]`に`WRITE_ISSUE_TOOL`・`READ_ISSUES_TOOL`を追加。`_CURRENT_CALLER_ROLE = "user"`は既存のまま。
  - プロンプト追記：Expertへ訂正指示を出す際、それが後続タスクでも忘れてはならない指示であれば`write_issue(CREATE, topic=..., description="Expertへの訂正指示: ...")`で記録すること。BL-094の慣例に倣い、最低限iter=1で`read_issues`を呼び、自分（またはDetector）が過去に起票した未解決issueがこのタスクの範囲に関係しないか確認し、Expertの回答がそれを解消していれば`write_issue(RESOLVE, topic=..., resolution_note=...)`で明示的にクローズすること。

- **`reflection_node`**（または同等のreflectionプロンプト構築箇所、`cela_main.py:5026`付近の`major_issues`抽出ロジック）。**LLMツールとしてではなく、Python側の直接DB問い合わせ**として`status='escalated'`の`issue_log`行を取得し（§2の不変条件により、これだけで初回major指定・閾値到達による自動昇格の両方を網羅する）、既存の`constraint_log_text`（`major_issues`のみを整形したテキスト）に統合する。これにより「累積2回でエスカレーションされたが誰も見ていない懸念」を、モデルのツール呼び出し判断に依存せず必ずreflectionへ届ける（BL-099が指摘した「モデル遵守への依存」を、この経路では発生させない設計）。

### 6. 既存ログとの関係

`detector_observations_log`/`constraint_issue_log`（state内リスト）はそのまま残す。既存テストがこれらに依存しているため、置き換えではなく**並存**とする。`issue_log`テーブルは「複数ターンをまたいで確実に残したい懸念」専用の追加レイヤーであり、モデルが明示的に`write_issue`を呼ぶ主経路に加え、§5のPython側自動バックアップで最低限の記録を保証する。ただし**一度記録された後の重大度昇格（occurrence_count>=2 → major/escalated、CREATE経由・READ経由の両方）と、reflectionへの到達は完全に機械的**とする。

### 7. BL-100（エスカレーション根拠の構造化）との関係

BL-100（前提を疑った際の「疑った前提・疑った理由・代替仮説・期待される利点・採用に必要な追加情報」の5項目セット）は、本BL-096の`issue_log`とは別ツール（`escalate_premise_concern`、BL-086）が起点であり、対象範囲も異なる（BL-096＝Detector/User AIの軽微な懸念・訂正指示、BL-100＝ゴールの前提そのものへの疑義）。統合するかは別途BL-100の設計時に検討する（本設計では`issue_log`のスキーマを`resolution_note`等汎用的に保ち、将来の統合を妨げない形にとどめる）。

## 対象ファイルまとめ

- `cela_main.py`:
  - `init_db`（または該当するテーブル作成関数）に`issue_log`のCREATE TABLE追加。
  - 新規`WRITE_ISSUE_TOOL`/`READ_ISSUES_TOOL`スキーマ定数。
  - 新規`_write_issue_impl`, `_check_issue_permission`, `_read_issues_handler`, `get_issues_from_db`, `_bump_issue_occurrence`（CREATE経由・READ経由で共有する再発カウント＋閾値昇格ロジック）。
  - `TOOL_DISPATCH`へ`write_issue`/`read_issues`追加。
  - `call_detector`・`generate_user_utterance`の`tools=[...]`拡張とプロンプト追記。`detector_node`にPython側自動バックアップ書き込みを追加。
  - reflection構築ロジック（`major_issues`抽出箇所）に`status='escalated'`のDB問い合わせ追加。
- `tests/test_bl096_issue_log.py`（新規）: `_check_issue_permission`のロール×アクション直接検証、`_write_issue_impl`のCREATE/RESOLVE/再発時の累積回数・自動昇格ロジック（`(topic, task_id)`キー、`severity='major'⇒status='escalated'`不変条件、descriptionトランケーション）をDB経由で検証、`read_issues`のフィルタ挙動（resolved込みデフォルト・`list_all`・description LIKE検索）、READ経由の再発カウント（`last_seen_task_id`比較による二重計上防止を含む）、`call_detector`/`generate_user_utterance`が両ツールを`tools=[...]`に渡していることの`inspect.getsource`確認、自動バックアップ書き込みの動作確認、reflection側のエスカレーション済みissue取得ロジックの確認。
- `docs/design/back_log/issue_backlog.md`: BL-096の状態を本改訂内容で更新。
- `docs/design/decision_log.md`: 新規D番号で、v1からの主要変更点（READ経由の再発カウント追加、`severity=major⇒status=escalated`不変条件、`(topic, task_id)`キー変更）とその理由を記録。

## Verification

1. `python -m py_compile cela_main.py`
2. `tests/test_bl096_issue_log.py`を新規追加し実行。
3. `pytest tests/ -q -k "bl093 or bl094 or bl095 or bl096 or bl087"`で関連クラスタの回帰確認、実装完了後に一度`pytest tests/ -q -k "not live"`をフルで実行。
4. `python scripts/check_docs_consistency.py`で文書間リンク整合性を確認。
5. コミットは実装完了後、ユーザーの明示的な指示を待つ。
