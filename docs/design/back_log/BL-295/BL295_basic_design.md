# BL-295: 裁量判断の「打ち切り規定」を汎用ヘルパー化する（3回多数決方式の切り出しと横展開）

## Context

`log/2026-08-28/1313`で、Detector（Domain Review, Pass 1）がUser AIのtask_1_1指示をレビューする際、`constraint_issue=none`の判定自体は正しく完了させた直後、続く自由記述部分で「この気づき（observationsに書いた内容）はwrite_issueで後続タスクへ永続化すべき懸念か？」という**別の裁量判断**に入り、41秒間・単一の生成ターン内で「後続タスクにも影響する」⇔「いや今回のタスク内でExpertが対応できる」という同一の二択を30回以上往復し、ツール呼び出しも出力確定も行わないまま停止した（ユーザーがCtrl+Cで手動一時停止、`run_id=1787890406-1e73a89d`）。

調査の結果、`call_detector`のDomain Review（Pass 1, `domain_prompt`）にはBL-096（`observations`に書いた懸念をwrite_issueで永続化すべきか、`cela_main.py:12235-12244`）という裁量判断の指示はあるが、判断が割れた場合の打ち切り規定が一切ない。一方、同じ`call_detector`のPass 2（数値監査パス）には既に実証済みの**「判定のブレ防止（3回多数決方式）」**という構造化された打ち切り機構が存在する（`cela_main.py:12575-12580`：独立判定を3回だけ行い多数決を採用、3回に達したら再検討禁止）。ただしこれはconstraint_issueのmajor/minor境界判定にしかスコープされておらず、`call_detector`のPass 2にしか存在しない（file全体で`多数決`/`trial1`はこの1箇所のみとExplore調査で確認済み）。

ユーザーは、軽量な一文追加ではなく、この3回多数決方式を**汎用ヘルパーとして切り出し**、他の同種の裁量判断にも横展開する方針を承認した。追加のExplore調査により、同種の「裁量判断＋打ち切り規定の欠如」が以下2箇所にも見つかった：

1. **User AIのwrite_issue action_type選択**（RESOLVE/DEFER/ACKNOWLEDGE、`generate_user_utterance`のStage2懸念処理プロンプト`cela_main.py:14003-14032`）: `WRITE_ISSUE_TOOL`のスキーマ説明（`cela_main.py:864-868`）には3択を区別する判定基準はあるが、「本当に解決したと言えるか迷う」場合の打ち切り規定が無い。
2. **BL-292 `quantitative_sufficiency_concern`の非対称**（`call_detector`のdomain_prompt、`cela_main.py:12423-12430`）: 3行上にある姉妹フィールド`essence_sufficiency_concern`（BL-266）には「判断に迷う・確信が持てない場合はfalseのままにしてください」という明示的な既定値への逃げ道（`cela_main.py:12398-12400`）があるのに、`quantitative_sufficiency_concern`には同種の一文が無い。

他の裁量判断箇所（confidence確定/暫定の選択、escalate_premise_concern判断、task_plan_reviewerの10観点判定）は、いずれも既存の閉じた基準（既定値バイアス・客観的な回数閾値・`_verification_throttle_warning`＋独自の一文）を既に持っており、追加対応は不要と判断した（Explore調査で確認済み）。

## 設計

### 1. 3回多数決方式を汎用ヘルパーとして切り出す

`cela_main.py:12575-12580`の既存ブロックは変数参照を含まない独立した段落であり（`role_specific_instruction`等への依存なし）、そのまま関数化できる。新規関数を`_verification_throttle_warning`（`cela_main.py:10618`）の近くに追加する:

```python
def _bounded_deliberation_instruction(judgment_description: str) -> str:
    """[BL-295] 裁量判断（結論が割れうる二択・三択の判定）で無限に再検討し続ける生成崩壊
    （log/2026-08-28/1313等）を防ぐための、3回多数決方式の打ち切り規定。call_detector
    Pass 2のconstraint_issue判定向けに実証済みだった機構（cela_main.py:12575-12580時点）を
    judgment_descriptionでパラメータ化し、他の裁量判断箇所へも横展開できるようにした。
    """
    return (
        f"【判定のブレ防止（3回多数決方式）】{judgment_description}で"
        f"結論が変わったり迷ったりする場合、同じ論点を無限に再検討し続けないでください。"
        f"その論点について、独立した判定を意識的に3回だけ行い（1回目・2回目・3回目、それぞれ短く"
        f"「trial1: ...」のように結論だけ明記すればよく、毎回長い理由の再展開は不要です）、"
        f"3回のうち多数だった結論を最終的な判断として採用してください。"
        f"3回分の判定が出た時点で、それ以上の再検討・迷いは禁止します。\n\n"
    )
```

### 2. call_detector Pass 2: 既存ブロックをヘルパー呼び出しへ置換（既存挙動を維持）

`cela_main.py:12575-12580`を`_bounded_deliberation_instruction("constraint_issueの判定（特にminorとmajorの境界）")`の呼び出しへ置換する（`judgment_description`の文言を既存テキストと一致させ、実質的な文面変化を最小化する）。

直後の`cela_main.py:12581-12585`（`_verification_throttle_warning`とほぼ重複する手書きブロック、§15.1違反）は、`_verification_throttle_warning(example="「この合計は制約内か」")`の呼び出しへ置換する。Explore調査により、既存の手書き文面とヘルパーのデフォルト（output_form="json"）出力にはわずかな文言差（「検証」の有無、末尾の「直ちに...移ってください」の有無等）があると判明しているため、**実装時にこの2ブロックの厳密な文字列に依存するテスト（例: `test_bl0XX_*.py`でこの範囲のsource文字列を`assert`しているもの）が無いかgrepで確認してから置換する**（あれば文言変更に追随させる）。

### 3. call_detector Pass 1（domain_prompt）: BL-096のwrite_issue永続化判断へ適用（診断されたバグ本体の修正）

`_issue_carryover_prefix`が`domain_prompt`へ埋め込まれる箇所（`cela_main.py:12315`付近、`_observations_block`の直後）に、新規ヘルパー呼び出しを追加する:

```python
f"{_bounded_deliberation_instruction('observationsに書いた懸念をwrite_issueで永続化すべきかの判断')}"
```

### 4. generate_user_utterance: write_issueのRESOLVE/DEFER/ACKNOWLEDGE選択へ適用

`cela_main.py:14003-14032`のStage2懸念処理プロンプト内、既存のRESOLVE手順説明の後に、新規ヘルパー呼び出しを追加する:

```python
f"{_bounded_deliberation_instruction('write_issueでRESOLVE/DEFER/ACKNOWLEDGEのいずれを選ぶべきかの判断')}"
```

### 5. BL-292 quantitative_sufficiency_concernの非対称を解消（軽量修正）

`cela_main.py:12423-12430`（quantitative_sufficiency_concernの指示）へ、姉妹フィールド`essence_sufficiency_concern`の既存文言（`cela_main.py:12398-12400`「判断に迷う・確信が持てない場合はfalseのままにしてください」）と同型の一文を追加する。こちらは3回多数決方式ではなく、姉妹フィールドと同じ「既定値（false）への逃げ道」パターンを踏襲する（真偽フラグには自然な安全側デフォルトがあるため、3回多数決という重い機構より軽量で一貫性が高い）。

## Critical Files

- `cela_main.py`:
  - `_bounded_deliberation_instruction`（新規関数、`_verification_throttle_warning`＝`10618`行の近くに追加）
  - `call_detector`のPass 2（`12575-12585`行付近）: 既存ブロックをヘルパー呼び出し2つへ置換
  - `call_detector`のdomain_prompt（Pass 1、`12315`行付近）: 新規ヘルパー呼び出しを追加
  - `generate_user_utterance`（`14003-14032`行付近）: 新規ヘルパー呼び出しを追加
  - `call_detector`のdomain_prompt（`12423-12430`行付近）: quantitative_sufficiency_concernへ既定値文言を追加
- `tests/test_bl295_bounded_deliberation.py`（新規）: `_bounded_deliberation_instruction`の出力内容確認（judgment_descriptionの埋め込み、3回多数決の核心文言を含むこと）、Pass 2が新ヘルパー呼び出しへ置換されていることの`inspect.getsource`確認（既存の3回多数決文言・trial1文言が引き続き含まれること＝非退行）、Pass 1のdomain_promptにヘルパー呼び出しが追加されていることの確認、generate_user_utteranceへの追加確認、quantitative_sufficiency_concernの既定値文言追加確認、§17.1

## Verification

1. `python -m py_compile cela_main.py`
2. 新規テストファイルを実行し全件成功を確認
3. Pass 2の既存文言に依存するテストが無いか事前にgrep確認し、あれば追随修正（§13.5要領、他BLでの「9→10」カウント更新と同型）
4. 既存の関連テスト（`test_bl266_essence_sufficiency_detector.py`、`test_bl292_quantitative_sufficiency_check.py`、Detector・User AI関連の既存テスト）を再実行し非退行を確認
5. AGENTS.md §17.1（各追加箇所を個別にリバートし対応テストが失敗することを確認後、復元）
6. フルオフラインスイートを実行し、既知のBL-269（4件）以外に新規失敗が無いことを確認
7. 実装後、`docs/design/back_log/issue_backlog.md`にBL-295を`done`化し記載、`decision_log.md`へ決定を記録
8. プロンプト文言の追加であり実LLM呼び出しでの効果確認が必要——次回ドライラン時に、①Pass 1のwrite_issue永続化判断で同種の堂々巡りが再発しないか、②Pass 2の既存3回多数決方式の挙動が維持されているか、③User AIのRESOLVE/DEFER/ACKNOWLEDGE選択で同種の堂々巡りが無いか、をログで確認することを次回宿題として記録する。
