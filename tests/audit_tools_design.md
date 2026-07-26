# ログ・DB監査ツール 設計書（v1）

## 0. 位置づけ

本ドキュメントは、CELAのドライランログおよびSQLite DB（`cela.db`）に対して**決定的（deterministic）に検出できる異常**を、LLMによる確率的なレビューより先に、機械的・全数チェックで洗い出すためのツール2本の設計書である。

### 背景（なぜ作るか）

2026-07-25のドライラン（`log/2026-07-25/1913`）を複数のAIセッションでレビューした結果、以下が判明した。

1. LLMによるログレビューは、実際には全文を読んでおらず、マーカー（`⚠️`, `major`判定等）でgrepしてヒットした周辺だけを読む形になりがちで、**マーカーの付いていない意味的な矛盾は読む回によって拾えたり拾えなかったりする**（確率的）。
2. 一方、CELA自身が既にログにラベル付けしている異常（`⚠️`警告、`major`判定、`[REPL Error]`等）や、DBの構造的な不変条件違反（例：承認されたはずの修正がwhiteboardファイルに反映されていない、同一タスクに対しSupersedeされていない`Deliverable`行が複数残る）は、**LLMを介さずスクリプトで100%の再現率で検出できる**。

したがって、監査コストを「LLMでなければ拾えない意味的な異常」だけに集中させるため、決定的に拾える部分を先にスクリプト化する。これが本設計書の目的であり、将来的なBL起票・チェック項目追加の土台とする。

### 適用範囲

- 対象ログ: `log/<date>/<time>/log_no_prompt.md`（および将来的に`log_with_prompt.md`）
- 対象DB: `cela.db`（`run_id`列で実行単位を区別する単一ファイル）
- 対象whiteboardファイル: `log/<date>/<time>/whiteboards/phase_<P>_task_<T>_V<N>.md`（`_write_whiteboard_to_file`が書き出す。`cela_main.py:2416`, `2433-2434`）

---

## 1. 共通設計方針

### 1.1 Findingスキーマ

両ツールとも、検出結果を以下の共通スキーマで出力する（将来、両者の結果をマージしたり、LLM意味検証パスの出力と統合できるようにするため）。

```python
class Finding(TypedDict):
    tool: str            # "log_scanner" | "db_checker"
    check_id: str        # 例: "LOG-MAJOR", "DB-GHOST-DELIVERABLE"
    severity: str         # "critical" | "warning" | "info"
    location: str         # ログなら "L12345"、DBなら "agreements.id=AG-..."
    message: str          # 人間可読の説明
    context: str          # 該当箇所の抜粋（ログなら前後数行、DBならレコードのJSON）
    related_bl: str       # 既知のBL番号があれば（例: "BL-062"）。無ければ空文字
```

### 1.2 出力形式

- 標準出力: 人間可読のMarkdownテーブル（severityごとにグルーピング）
- `--json <path>`: 上記Findingのリストをそのまま JSON Lines で書き出す（後続処理・LLM意味検証パスへの引き渡し用）
- 終了コード: `critical`が1件でもあれば非ゼロ終了（CI的な用途を見据える）

### 1.3 拡張の土台（ルールレジストリパターン）

両ツールとも、チェック項目を**個別関数として登録する小さなレジストリ**で管理し、新しいBLが見つかるたびに1関数追加するだけで拡張できるようにする。

```python
CHECKS: dict[str, Callable[[Context], list[Finding]]] = {}

def register(check_id: str, severity: str, related_bl: str = ""):
    def deco(fn):
        CHECKS[check_id] = fn
        return fn
    return deco

@register("LOG-MAJOR", severity="warning")
def check_major_judgements(ctx: LogContext) -> list[Finding]:
    ...
```

これにより「今回のようにDBの書き込み反映漏れが見つかった → 対応するチェック関数を1つ追加する」というBL駆動の拡張サイクルがそのままツールの成長サイクルになる。

---

## 2. Tool 1: ログエラースキャナー（`log_scanner.py`）

### 2.1 目的

`log_no_prompt.md`をLLMを介さず走査し、CELA自身が既に埋め込んでいる異常マーカーを漏れなく列挙する。

### 2.2 検出パターン一覧（`cela_main.py`実装の`print`呼び出しから実在確認済み）

| check_id | マーカー（正規表現の元ネタ） | severity | 出典行 | 意味 |
|---|---|---|---|---|
| `LOG-ROLE-REPEAT` | `⚠️ .*role連続を検出` | warning | L1683 | メッセージ列でuser/assistantが連続、APIエラーの原因になりうる |
| `LOG-FORCED-TEXT` | `⚠️ .*最終iteration.*ツールを外し` | info | L1829 | ツールループが上限に達し、強制的にテキスト応答させた |
| `LOG-MAX-TOKENS` | `⚠️ .*max_tokens超過により出力が打ち切られました` | critical | L1878 | 応答が途中で切れた＝成果物が不完全な可能性 |
| `LOG-NO-REPL` | `⚠️ .*python_replを一度も使わずに応答しました（F-2.6監査対象）` | info | L1890 | 検算ゲートを素通りした（即異常ではないが要目視） |
| `LOG-UNKNOWN-TOOL` | `⚠️ .*未知のツール呼び出し` | critical | L1902 | モデルが存在しないツールを呼んだ |
| `LOG-TOOLARG-JSON-FAIL` | `⚠️ .*tool_call引数のJSONパース失敗` | critical | L1909 | ツール引数が壊れていた |
| `LOG-NONCONVERGENT` | `❌ .*ツールループが.*回を超えて非収束` | critical | L1995 | ツールループが上限に達しクラッシュ相当 |
| `LOG-JUDGE-JSON-RETRY` | `⚠️ .*JSON判定パース失敗を検知。層2リトライ` | warning | L2128 | 判定JSONの出力が壊れ、リトライが発生（今回のgoal_essence事例） |
| `LOG-EMPTY-RESPONSE` | `⚠️ .*空応答を検知。リトライ` | warning | L5058 | User AIが空応答を返しリトライした |
| `LOG-DELIVERABLE-CONFLICT` | `⚠️ .*成果物間に矛盾を検出しました` | critical | L6088 | Integratorが成果物間の矛盾を検出 |
| `LOG-ANNOTATE-FAILED` | `⚠️ \[Whiteboard Annotate Failed\]` | warning | （BL-074関連） | Detectorの指摘注釈がwhiteboardに挿入できなかった |
| `LOG-REPL-ERROR` | `→ \[REPL Error\]` | info | `_run_python_repl`実装 | サンドボックス制限（許可モジュール外import等）でpython_replが失敗 |
| `LOG-MAJOR-VERDICT` | `'constraint_issue': 'major'` または `constraint_issue.*major` | warning | Detector/Reviewer判定JSON | major判定そのもの（件数集計・後続追跡の起点として） |
| `LOG-SAME-MAJOR-REPEAT` | 同一`check_id`（task_id相当）で`LOG-MAJOR-VERDICT`が3回以上連続 | critical | 派生ルール | 同種の指摘が是正されずループしている兆候（今回のtask_2_1「40.5秒で通過」相当） |

`LOG-SAME-MAJOR-REPEAT`のみ単純な正規表現1本ではなく、`LOG-MAJOR-VERDICT`のヒット列をtask_id単位で集計し、同一task_idに対する`major`が閾値回数（既定3回）を超えたら発火する集計ルールとする。今回のdry-runで実際に見逃されかけた「堂々巡り」パターンを機械的に拾うための、本ツール最大の存在意義のひとつ。

### 2.3 明示的な非対応範囲（LLM意味検証パスに委譲）

以下は本ツールでは検出できない。将来のLLM意味検証パス（別モデル・別セッションでの多重スクリーニング）の対象として明記しておく。

- ラベル付けされていない意味的矛盾（例：「停車後40.5秒で通過する」という物理的にありえない記述そのもの）
- ゴール文にない数値の"それらしい"すり替え（ラベルは正常に見えるが意味が捏造されているケース）
- acceptance_criteriaのカバレッジが差し替えによって静かに失われるケース（今回発見した「消して解消」パターン）

### 2.4 CLIインターフェース（案）

```
python tests/tools/log_scanner.py <log_no_prompt.md> [--json out.jsonl] [--min-severity warning]
```

---

## 3. Tool 2: DB整合性チェッカー（`db_checker.py`）

### 3.1 目的

`cela.db`に対し、既知のBLインシデントから逆算した**構造的不変条件**をSQLで直接検査する。LLMのラベルに頼らず、スキーマそのものから矛盾を検出する。

### 3.2 対象テーブル（`cela_main.py` `init_db`実装より確認済み、L2163-2256）

`decisions` / `agreements`（`entry_type`, `status`, `topic`, `task_id`列あり） / `whiteboard_drafts`（`phase_id`, `task_id`, `version`, `content`） / `plan_drafts` / `chat_history` / `current_goal` / `verified_facts` / `goal_shift_events` / `goal_escalations` / `goal_essence`。すべて`run_id`で実行単位を区別する。

### 3.3 run_idの特定方法

`db_path`は複数runで共有される単一ファイル（既定`cela.db`）のため、対象ログフォルダから`run_id`を一意に特定する必要がある。`run_cela`関数は起動時に`log_dir`配下へ`checkpoint.json`を書き出す（`cela_main.py:6554`）ため、これに`run_id`が含まれている前提でそこから読み取る（`_load_checkpoint`実装を要確認・設計時点では未検証、実装時に要確認事項として残す）。checkpoint.jsonが存在しない/壊れている場合のフォールバックとして、ログファイル冒頭の`# Execution Log Started at:`のタイムスタンプと`agreements.timestamp`の近さでrun_idを推定する経路も用意する。

### 3.4 チェック項目一覧

| check_id | 内容 | SQLの骨子 | severity | related_bl |
|---|---|---|---|---|
| `DB-GHOST-DELIVERABLE` | 同一`(run_id, phase_id, task_id)`の`entry_type='Deliverable'`行のうち、`status != 'Superseded'`が2件以上残っている | `agreements`を`(phase_id, task_id)`でGROUP BYし`status != 'Superseded'`件数を数える | critical | BL-073/074/084 |
| `DB-WRITEBACK-MISMATCH` | `whiteboard_drafts`の最新versionの`content`と、対応する`log/whiteboards/phase_P_task_T_V<version>.md`ファイルの内容が一致しない | DBの`content`とファイル読み込み結果を文字列比較 | critical | 今回発見（write-back未反映バグ） |
| `DB-MAJOR-WITHOUT-SUPERSEDE` | `constraint_issue='major'`かつ対象がDB内の既存topicに起因すると`comment`から推定できるのに、直後に`action_type='SUPERSEDE'`の行が続いていない | `agreements`を`timestamp`順に見て、major判定相当の記録直後にSUPERSEDE行があるかを確認（ヒューリスティック、誤検知はwarning止まりとする） | warning | BL-062 |
| `DB-ORPHAN-PROPOSED-DIRECTIVE` | `entry_type='Directive'`が`status='Proposed'`のまま、対応タスクが完了（後続phaseに進行）している | `agreements`と`phases`進行状況の突合 | warning | BL-073 |
| `DB-GOAL-SHIFT-UNCONSUMED` | `goal_shift_events`に記録があるが、それを消費した形跡（対応する`agreements`更新等）が後続に存在しない | `goal_shift_events.timestamp`以降の`agreements`を確認 | info | BL-065（"書きっぱなし"問題） |
| `DB-VERIFIED-FACT-STALE` | `verified_facts`の値が、対応する`agreements`がSupersededになった後も更新されていない | `verified_facts.source_task_id`と`agreements`のstatusを突合 | warning | 派生（BL-062関連） |
| `DB-DEPENDS-ON-CYCLE` | `agreements`の`depends_on`が前方参照（未来のtaskに依存）になっている、または循環している | `depends_on`をパースしてタスク順序と突合 | warning | 今回のtask_3_3/3_4指摘相当 |

### 3.5 CLIインターフェース（案）

```
python tests/tools/db_checker.py --db cela.db --run-id <run_id> [--log-dir log/2026-07-25/1913] [--json out.jsonl]
```

`--log-dir`は`DB-WRITEBACK-MISMATCH`のファイル突合に使う（省略時はこのチェックのみスキップ）。

---

## 4. 実装方針・優先順位（次のステップ）

1. `tests/tools/`配下に`log_scanner.py` / `db_checker.py` / `audit_common.py`（Finding定義・レジストリ）を新設
2. まず`log_scanner.py`の表2.2にある高確度のマーカーチェックから実装（正規表現ベースで実装コストが低く、誤検知リスクも低いため）
3. `LOG-SAME-MAJOR-REPEAT`（集計ルール）は今回の「堂々巡り」実例の再現テストとして`tests/test_log_scanner_same_major_repeat.py`を用意し、`log/2026-07-25/1913/log_no_prompt.md`の該当区間を最小化したfixtureで固定する
4. `db_checker.py`は`DB-GHOST-DELIVERABLE`と`DB-WRITEBACK-MISMATCH`（今回実際に踏んだ2つのバグクラス）を最優先で実装し、他のチェックは順次追加
5. 両ツールとも、既存の`scripts/check_docs_consistency.py`と同様にCIから呼べる形（非ゼロ終了コード）を維持する

## 5. 未確定事項（実装時に要確認）

- `checkpoint.json`の実際のスキーマ（`run_id`キーの有無・位置）は本設計書執筆時点で未検証。`_load_checkpoint`の実装を実装着手時に確認すること。
- `DB-MAJOR-WITHOUT-SUPERSEDE`はcomment文字列からのヒューリスティック推定に依存するため誤検知率が読めない。実装後、既存ログ（2026-07-24/0647、2026-07-25/1913等）で試走し、閾値・判定条件を調整する前提とする。
- 本ツールの結果をLLM意味検証パス（別セッションでのスクリーニング）にどう引き渡すか（例：Findingの`context`をプロンプトに埋め込み、「この箇所を重点的に見よ」と誘導する）は本設計書のスコープ外。次フェーズの検討課題とする。
