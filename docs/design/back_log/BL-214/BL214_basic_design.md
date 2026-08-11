# BL-214 基本設計：`current_task_id` の実効解決が一部経路で未適用（BL-146の適用漏れ）

作成日: 2026-08-11
対象コミット: `35554ac`（BL-213 F3修正後）
発見契機: `log/2026-08-11/2030`（nemotronによる新規ラン、run_id=`1786436794-a9d79ae6`）
ユーザーの報告: 「ツール使用に苦戦しているようです」＋ BL-177/178 の警告ログを引用

---

## 0. 調査経過の訂正（重要）

**初回の診断は誤りだった。** ユーザーへ最初に報告した「`agreements.id` のミリ秒衝突により
`ORDER BY id` の順序が不定になり、`_is_task_completed` が古い Superseded 行を最新と誤認していた」
という説明は、**この run では成立しない**。

- 合成テスト（LLMレイテンシなしで `write_agreement` を連続呼び出し）では確かに同一ミリ秒の
  ID衝突を再現でき、`_is_task_completed` が `False` を返した。
- しかし実 run（`1786436794-a9d79ae6`）の agreements を調べると、**この run 内の重複IDは0種類**。
  `task_1_1` の Deliverable 17行はすべて相異なるIDで、`ORDER BY id` と `ORDER BY rowid` の
  並びは完全に一致していた。

AGENTS.md §14.1（表層的なパターン一致は診断ではない／実データで裏を取る）の違反であり、
再現できた合成条件を実インシデントの説明として早合点した。真因は別にある（§2）。

ただし **ID衝突そのものは実在する独立した欠陥**であり、DB全体で
**1724行中188行（10.9%）、90種類のIDが重複**している。本設計では BL-215 として分離し、
§6 に調査結果を記録する。

---

## 1. 症状

`log/2026-08-11/2030` の task_1_1 で、User AI (Stage3: 統合承認判断) が

```
⚠️ [User AI Stage3] BL-177/BL-178: approval_status='Approved'ですが、
   Expertの成果物（Deliverable）自体がApproved相当へ更新されたことを確認できません（試行1/3）。
   …（試行2/3）…（試行3/3）
🚨 [User AI Stage3] BL-177: リトライを使い切っても承認記録の食い違いが解消しませんでした。
   ApprovalRecordingFailedとして扱います。
```

を3回連続で出し、`ApprovalRecordingFailed` へ落ちた。ユーザーからは「ツール使用に苦戦している」
ように見えていた。

**しかしモデルは苦戦していない。** ログとDBを突き合わせると、User AI は最終的に

```json
{"entry_type": "Deliverable", "action_type": "UPDATE", "status": "Approved",
 "task_id": "task_1_1", "topic": "人口統計・移動弱者実態の整理", "decision_what": "Approved", ...}
```

を送って `{'success': True}` を得ており、DB にも
`AG-1786448723677 / Deliverable / UPDATE / status='Approved' / task_id='task_1_1'` が
正しく記録されていた。**検証側が、モデルの正しい成功を認識できていなかった。**

---

## 2. 根本原因

### 2.1 直接原因

`generate_user_utterance` の Stage パイプライン先頭（`cela_main.py:10084`）が、
`_CURRENT_TASK_ID` へ **生の** `state["current_task_id"]` を代入している。

```python
_CURRENT_TASK_ID = state.get("current_task_id", "")     # ← 生の値
```

そして BL-177/178 の検証（`cela_main.py:10315`）がその値をそのまま使う。

```python
if get_last_write_agreement_succeeded() and _is_task_completed(_conn, state["run_id"], _CURRENT_TASK_ID):
    break
```

`_is_task_completed` は冒頭で `if not task_id: return False` を実行するため、
`_CURRENT_TASK_ID` が空文字なら **DBの中身に関わらず必ず False** を返す。

### 2.2 なぜ `state["current_task_id"]` が空だったのか

これは異常ではなく **仕様どおり**である。`current_task_id` の唯一の書き手は
`_resolve_task_transition`（BL-024）であり、**最初のタスク遷移が発生するまで空文字のまま**である。
今回の run は task_1_1（＝phase_1 の先頭タスク＝最初のタスク）を実行中で、まだ一度も遷移して
いなかった。

**この問題は BL-146 が既に発見・解決している。** `_effective_current_task_id_from`
（`cela_main.py:4088`）の docstring がまさにそれを書いている。

> `state["current_task_id"]`は初回タスク進行中は空文字のままなので（唯一の書き手
> `_resolve_task_transition`が最初の遷移までまだ一度も発火していない）、生のcurrent_task_idを
> そのまま比較すると初回タスクの正当な書き込みまで全滅する。`_get_current_task`と同じ
> current_phase先頭タスクへのフォールバックを再利用する。

実測でも確認済み。

```
生の state['current_task_id']            : ''
_task_id_from(state)                    : ''
_effective_current_task_id_from(state)  : 'task_1_1'     ← 正しい値
```

### 2.3 これは AGENTS.md §15 の再発である

「現在のタスクは何か」という**同じ規則が2箇所以上に書かれ、片方だけが更新された**という、
AGENTS.md §15.1（One rule, one place）・§15.2（発火源を全列挙する）そのもののパターンである。

BL-146 は `write_agreement` の `current_task_id` ゲート経路を修正したが、
**同じ判断を必要とする他の経路（BL-177/178 の検証、`write_issue` の task_id 付与）へは
波及していなかった**。BL-213 の横断監査（§15 の成立契機）が `agreements` の書き込み経路
のみを対象としていたため、この経路は監査の網からも漏れていた。

---

## 3. 影響範囲（実測）

### 3.1 確認済みの実害①：BL-177/178 の検証が初回タスクで常に失敗する

`_CURRENT_TASK_ID` が空 → `_is_task_completed` が常に False → Stage3 が3回リトライして
`ApprovalRecordingFailed`。**各フェーズの先頭タスクで、正常な承認が必ず失敗する。**

Stage3 のリトライは 1回あたり LLM 呼び出し1回（今回は最大 iter=6 のツールループ付き）であり、
**3回分のトークンが毎回無駄になる**。さらに `ApprovalRecordingFailed` は Stage4 の分岐を
「承認記録失敗の待機メッセージ」へ倒すため、**承認済みのタスクが次へ進めない**。

### 3.2 確認済みの実害②：`write_issue` の `task_id` が空で記録される

`TOOL_DISPATCH["write_issue"]`（`cela_main.py:4259`）は `_task_id_from(state)` を渡している。
これも実効アクセサではないため空文字になる。

`_write_issue_impl` は `args["task_id"]` ではなく**この引数を使う**ため、
LLM が明示的に `"task_id": "task_1_1"` を送っていても**無視されて空文字が保存される**。

実 run の issue_log で確認：

```
write_issue 実行: {"topic": "license_surrender_rate_derivation", ..., "task_id": "task_1_1"}
→ 保存結果:      {'task_id': '', 'last_seen_task_id': '', 'phase_id': 'phase_1', ...}
```

**8件すべての issue が `task_id=''` / `last_seen_task_id=''` で記録されていた**
（`phase_id` は `_phase_id_from` が `current_phase` から取れるため正常）。

この破損は下流へ波及する。`task_id` を条件に使う機構が軒並み効かなくなる：

| 機構 | 参照 | 影響 |
|---|---|---|
| BL-125 タスク遷移ゲート | `_get_blocking_issues_for_transition(conn, run_id, departing_task_id)` | 離脱元タスクのissueとして検出されず、**未解決issueがあっても遷移を止められない** |
| BL-144 滞留追跡 / BL-096 再発カウント | `last_seen_task_id` | 滞留・再発の集計が壊れる |
| BL-145 issue駆動タスク再構成 | task_idごとの紐付け | 受け皿タスクの特定が不正確になる |
| BL-194 actionable集合 | `_get_actionable_escalated_issues(conn, run_id, current_task_id, ...)` | 現在タスクのissueを識別できない |

### 3.3 なぜ `write_agreement` は無事だったか（対比）

`_commit_agreement_from_tool` は

```python
tid = args.get("task_id") or task_id        # args優先、引数はフォールバック
```

としているため、LLM が明示指定していれば正しい値が入る（BL-040）。
`write_issue` にはこの `args` 優先のフォールバックが無い。**同じ「task_idをどう決めるか」という
規則が2つのツールで別々に実装されており、片方だけが堅牢**という、これも §15.1 の事例である。

### 3.4 未確認だが同種のリスクがある箇所

生の `state.get("current_task_id", "")` を使っている箇所は他に多数ある（§5.4 で全件精査）。
特に以下は「空文字だと機能が黙って無効化される」タイプで、優先的な確認対象。

- `cela_main.py:8145 / 8151 / 8663 / 8673 / 10602 / 10609`：
  `_build_escalation_pin_text` / `_build_deferred_issue_pin_text`（ピン留めが効かなくなる）
- `cela_main.py:10179 / 10682`：`_get_forced_escalated_issues_text`
- `cela_main.py:9564`：`_is_issue_effectively_deferred`
- `cela_main.py:12545 / 12697`：reflection / facilitator の actionable issue 取得
- `cela_main.py:7829 / 8412 / 8433 / 10822 / 10833`：他ノードの `_CURRENT_TASK_ID` 設定

---

## 4. 設計方針

### 4.1 何を直すか（不変条件の一元化）

> **「現在のタスクは何か」という問いに答える方法は、システム内で1つだけとする。**
> それは `_effective_current_task_id_from(state)`（＝`current_task_id`、無ければ
> `current_phase` の先頭タスク）である。生の `state["current_task_id"]` を
> 「現在タスク」として扱う実装を残さない。

これは AGENTS.md §15.1（One rule, one place）と §15.3（機械的検証を権威とする）の直接適用であり、
新しい規則の発明ではなく **BL-146 が既に確立した規則を全経路へ行き渡らせる**作業である。

### 4.2 生の `current_task_id` を残してよい箇所（例外の明示）

すべてを機械的に置換してはならない。**「まだ遷移していない」ことを判定したい箇所**では
生の値が正しい。以下は例外として残し、その旨をコメントで明示する。

| 箇所 | 生の値でよい理由 |
|---|---|
| `_resolve_task_transition`（`cela_main.py:11946`） | `departing_task_id` は「実際に遷移が起きた履歴」を見る。初回は空でよい（BL-176 のゲートも `if departing_task_id and ...` で空を明示的に除外している） |
| `_effective_current_task_id_from` / `_get_current_task` 内部 | フォールバックの実装そのもの |
| `decision_extractor_node:12257`（`item.get("task_id") or state.get(...)`） | LLM の申告を優先し、state はフォールバック。BL-211 で確立した `or` パターン |

**[REJECTED]** 「`_resolve_task_transition` に初期値として先頭タスクを書き込ませる」案は採らない。
BL-024 が `current_task_id` の書き手を `_resolve_task_transition` 単独に限定した設計意図
（誰が現在タスクを動かしたか追跡可能にする）を壊し、かつ「まだ遷移していない」という
情報が失われて §4.2 の例外群が判定不能になるため。

### 4.3 `write_issue` の `task_id` 決定を `write_agreement` と揃える

`_write_issue_impl` 内で `args.get("task_id") or task_id` の優先順とし（BL-040 と同型）、
LLM の明示指定を尊重する。これにより、実効アクセサの適用漏れが将来再発しても
**LLM が明示していれば壊れない**という二重の防御になる。

### 4.4 沈黙させない

空文字が「正常系として素通り」したことが、この欠陥が長期間見逃された理由である
（AGENTS.md §13.2 問4）。実効アクセサでも解決できない場合（`phases` が空等）は
**警告を出す**。特に `_is_task_completed` は `task_id` が空で呼ばれた時点で異常なので、
黙って `False` を返さず警告する。

---

## 5. 実装計画

### 5.1 S1: 実効アクセサへの統一（`_task_id_from` の見直し）

`_task_id_from`（`cela_main.py:4072`）は現在

```python
def _task_id_from(state: dict | None) -> str:
    return state.get("current_task_id") or _CURRENT_TASK_ID if state else _CURRENT_TASK_ID
```

であり、TOOL_DISPATCH の複数ツール（`write_agreement` の第5引数、`write_issue`、他）が
これを「現在タスク」として使っている。**ここを実効解決へ寄せるのが最小の変更で最大の被覆**
となる。

```python
def _task_id_from(state: dict | None) -> str:
    """[BL-214] 「現在のタスク」の唯一の解決経路。生のcurrent_task_idは初回タスク進行中に
    空文字のままであり（BL-024: 唯一の書き手_resolve_task_transitionが最初の遷移まで発火
    しない）、それをそのまま使うと初回タスクで機能が黙って無効化される。
    BL-146が確立した_effective_current_task_id_from（current_phase先頭へのフォールバック）
    をここへ集約する。"""
    return _effective_current_task_id_from(state) or _CURRENT_TASK_ID
```

**[CONSTRAINT]** `_effective_current_task_id_from(None)` は既にグローバルフォールバックを
内包しているため、`state=None` の後方互換も維持される。

### 5.2 S2: Stage パイプラインの `_CURRENT_TASK_ID`

`cela_main.py:10084` を実効解決へ変更する。

```python
_CURRENT_TASK_ID = _effective_current_task_id_from(state)
```

同型の代入（`7829 / 8412 / 8433 / 10822 / 10833`）も同時に精査し、
「現在タスクとして使う」用途であれば同様に変更する（§5.4 の全件精査で確定させる）。

### 5.3 S3: `write_issue` の args 優先フォールバック

`_write_issue_impl` の CREATE 分岐で、`task_id` を
`args.get("task_id") or task_id` に統一する（`phase_id` も同様に確認）。

### 5.4 S4: 生 `current_task_id` の全件精査

§3.4 に挙げた箇所を1件ずつ「現在タスクとして使うのか／遷移履歴として使うのか」で分類し、
前者は S1 の統一により自動的に解決されるか、個別に修正する。**分類結果を表にして
本設計書へ追記する**（AGENTS.md §15.2：発火源を全列挙してから完了と宣言する）。

### 5.5 S5: 沈黙の解消

- `_is_task_completed`：`if not task_id:` の分岐で `print` による警告を追加。
- `_write_issue_impl`：`task_id` が最終的に空のまま CREATE する場合に警告。

---

## 6. 分離する欠陥：`agreements.id` のミリ秒衝突（BL-215 として起票）

§0 のとおり本インシデントの原因ではないが、調査の過程で**独立した実在の欠陥**として確認した。
BL-214 と混ぜず、別BLとして扱う。

### 6.1 事実

- ID生成は `f"AG-{int(time.time() * 1000)}"`（`cela_main.py:3213 / 5647 / 12358 / 12376`）。
  同一ミリ秒に2回呼ぶと**完全に同じIDの行ができる**。
- `agreements` テーブルに **PRIMARY KEY も UNIQUE 制約も無い**ため、重複INSERTが素通りする。
- 実DB全体で **総行数1724 / 重複ID種類90 / 重複に巻き込まれた行188（10.9%）**。3重複も8件存在。
- 同型の脆弱性が `decisions`（`D-`、`cela_main.py:10993`）、`goal_shift_events`（`GS-`、`5540`）、
  `plan_drafts`（`PL-`、`5795`）にもある。
- **対照的に `goal_escalations` は既に対策済み**：
  `f"ESC-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"`（`cela_main.py:2471`）。
  `issue_log` は `str(uuid.uuid4())`（`3495`）。つまり**同じ「一意IDの作り方」という規則が
  テーブルごとにバラバラ**であり、これも §15.1 の事例。

### 6.2 想定される実害（3種）

1. **順序の不定性**：`get_agreements_from_db` は `ORDER BY id`（`6394`）で最新順を再構成し、
   9箇所が `reversed(...)` で「最新の行」を取る。同一IDのタイの並びは**クエリプラン依存で不定**。
   実際、合成テストでは `ORDER BY id` が挿入順を**反転**させ、Superseded 行を最新と誤認させた。
2. **UPDATE の増幅**：`db_supersede_agreement` / `freeze_agreement` は
   `WHERE id=?` で更新するため、**重複IDの全行を巻き込む**。
3. **参照の曖昧化**：`depends_on` の参照整合性チェック、`freeze_agreement_id`、
   `citations` の `AG-xxx` 参照が一意に定まらない。

### 6.3 修正方針（案）

- **順序**：`ORDER BY id` → `ORDER BY rowid` へ変更。`agreements` は `WITHOUT ROWID` でも
  `INTEGER PRIMARY KEY` でもないため **SQLite の暗黙 rowid が真の挿入順を保持しており、
  スキーマ移行なしで既存DBにもそのまま効く**（検証済み）。`SELECT *` に rowid は
  含まれないため下流の dict キーにも影響しない（検証済み）。
- **一意性**：ID生成を `goal_escalations` の既存先例に揃え、
  `f"AG-{int(time.time()*1000)}-{uuid.uuid4().hex[:6]}"` とする。
- **既存の重複行**：過去 run のデータであり、遡及修正はしない（rowid 順序修正で
  読み取り側は正しく動く）。

---

## 7. テスト計画

AGENTS.md §17.1 に従い、**各修正を個別にリバートすると対応するテストが実際に失敗すること**を
確認したうえで固定する。

`tests/test_bl214_effective_task_id_resolution.py`（新規）

| # | 検証内容 |
|---|---|
| 1 | **実インシデント再現**：`current_task_id=""` かつ `current_phase` 先頭が task_1_1 の state で、Deliverable を `status='Approved'` で UPDATE した直後に、BL-177/178 の検証が成功と判定されること |
| 2 | `_task_id_from(state)` が `current_task_id=""` のとき先頭タスクを返すこと |
| 3 | `_task_id_from(state)` が `current_task_id` 設定済みならその値を優先すること（非退行） |
| 4 | `write_issue` が `current_task_id=""` でも `args["task_id"]` を尊重して保存すること |
| 5 | `write_issue` が `args["task_id"]` 未指定なら実効解決値で保存すること |
| 6 | BL-125 遷移ゲートが、初回タスクで起票された issue を正しくブロック要因として検出すること（§3.2 の下流影響の回帰） |
| 7 | `_is_task_completed("")` が警告を出すこと（沈黙の解消） |
| 8 | **非退行**：`_resolve_task_transition` の `departing_task_id` は生の値のまま（初回遷移で BL-176 ゲートが誤発火しないこと） |
| 9 | **配線固定**：`generate_user_utterance` のソースに `_CURRENT_TASK_ID = state.get("current_task_id"` が残っていないこと（§17.1 の inspect パターン） |

既存テストへの影響確認（特に `test_bl146_*`、`test_bl176_*`、`test_bl125_*`、`test_bl096_*`）を
実施し、オフライン全スイートを通す。

---

## 8. 未決事項（ユーザー判断を仰ぐ）

1. **BL-215（ID衝突）を今回同時に実施するか、分離して後日にするか。**
   §6.3 の修正自体は小さいが、`ORDER BY id` → `ORDER BY rowid` は 9箇所の
   `reversed()` 経路すべての挙動に影響するため、テスト範囲は広い。
2. **§5.4 の全件精査の結果、変更対象が広がった場合の扱い。**
   S1（`_task_id_from` の一元化）だけで大半が解決する見込みだが、精査で
   「実効解決すべきなのに個別に生の値を読んでいる」箇所が多数見つかった場合、
   BL-214 のスコープに含めるか分割するかを再判断したい。
3. **現在進行中の run（`1786436794-a9d79ae6`）を止めて修正を適用するか。**
   この run は各フェーズの先頭タスクで必ず §3.1 の症状に当たるため、
   トークンを浪費し続ける。ただし nemotron のゴールエスカレーション観察が目的なら
   継続する価値もある。

---

## 9. 参照

- `docs/design/back_log/issue_backlog.md`: BL-146（`_effective_current_task_id_from` の導入元）、
  BL-024（`current_task_id` の書き手限定）、BL-177 / BL-178（本件で失敗した検証機構）、
  BL-040（`args` 優先フォールバックの先例）、BL-125 / BL-176 / BL-194（下流の影響先）、
  BL-213（横断監査、本件は監査対象外だった）
- `docs/design/decision_log.md`: D-189（AGENTS.md §13）、D-190（§14〜§18）
- `AGENTS.md`: §13.1（空文字が既定値を貫通）、§13.2（フォールバック前の下流追跡）、
  §14.1（表層一致は診断ではない）、§15.1（One rule, one place）、§15.2（発火源の全列挙）、
  §17.1（リバート検証）
- 実ログ: `log/2026-08-11/2030/log_no_prompt.md`
- 実DB: `cela.db`（run_id=`1786436794-a9d79ae6`）
