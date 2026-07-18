# Phase 1（R1: SQLite永続化基盤）ドライラン手順書

> **作成日**: 2026-07-18
> **対象BL**: [BL-002](../issue_backlog.md#bl-002-r1完了条件の実データabドライラン未実施)（本手順の主対象）、[BL-003](../issue_backlog.md#bl-003-recordreplayスタブの実llm応答による往復検証未実施)（本手順の7章で合わせて実施）
> **参照**: [cela_phase1_design_v7.md §5, §5.1](cela_phase1_design_v7.md), [cela_phase1_impl_Plan.md §7](cela_phase1_impl_Plan.md)
> **本書の位置づけ**: `AGENTS.md`のドキュメント規律に従い、本書には**手順・環境詳細のみ**を記載する。Pass/Fail結果サマリーは`../traceability.md`（T-*）へ、失敗・次の修正は`../issue_backlog.md`（BL-xxx）へ記録すること。本書自体には結果を書き込まない。

---

## 0. 前提：比較対象となる2つのコード状態

R1は「既存プロトタイプ（変更前）」と「リファクタリング後（SQLite版）」を**同一タスクで**走らせて比較する（設計書§5冒頭）。本リポジトリでは以下の2状態が対応する。

| 呼称 | Git上の実体 | 状態管理 | Record/Replayスタブ |
|------|------------|---------|---------------------|
| **list版ベースライン** | コミット `5ef0382`（`cela_main.py`、2026-07-17） | `state["decisions"]` / `state["agreements"]`（Pythonリスト） | **なし**（`query_AI`にREPLAY_MODE分岐が存在しない） |
| **SQLite版（R1）** | コミット `2133989`（`cela_main.py`、R1実装完了時点） | `db_append_*` / `get_*_from_db`（SQLite） | **あり**（`query_AI`にREPLAY_MODE=`off`/`record`/`replay`） |

**両バージョンともコミットハッシュで固定する**（本書作成後に作業ツリーの変更が`2133989`としてコミットされたため、当初の「作業ツリー（未コミット差分）」という参照は廃止した）。以後`cela_main.py`にさらに手が入っても、本ドライランの対象は上記2コミットのまま固定とし、必要なら再実行時に新しいコミットハッシュへ差し替える。

**重要な注意**: impl_Plan §6の「順序」規定（system_prompt修正→list版でRecord→SQLite版でReplay）を字面通り満たすには、list版側にもRecord機能が必要だが、コミット`5ef0382`にはRecord/Replay機構自体が存在しない（SQLite化と同じ作業で追加されたため）。したがって本手順では、**コミット`2133989`のRecord/Replay関連hunkだけをコミット`5ef0382`に適用した一時ブランチ（1.3節）**を用意する。幸い、`git diff 5ef0382 2133989 -- cela_main.py`で確認する限り、Record/Replay部分（`query_AI`ラッパー本体とモジュール冒頭の定数群）はSQLite永続化部分（`get_db_connection`以降）と完全に別のhunkに分かれているため、新規のロジック実装は一切不要で、既存hunkの抽出・適用のみで済む。

---

## 1. 事前準備

### 1.1 環境変数

`cela_main.py`は現行設定で`client_user` / `client_agent` / `client_auditor`のすべてが`client_openrouter`（OpenRouter経由）を使う（L205-212）。よって最低限必要な環境変数は以下。

```
DSEEK_V4_FLASH_USER_KEY=<OpenRouter APIキー>
```

（`GEMINI_API_KEY` / `GEMINI_API_KEY_AUDITOR`はコード起動時に未設定だと警告が出るが、現行の役割割り当て（L205-212）では実際には使用されないため、警告が出ても実行は継続してよい。）

### 1.2 依存パッケージ

```powershell
pip install langgraph openai
```

`sqlite3` / `uuid` / `hashlib` / `json` / `secrets` / `unittest`は標準ライブラリのため追加インストール不要。

### 1.3 「Record対応list版」一時ブランチの用意（git hunk適用方式）

`git diff 5ef0382 2133989 -- cela_main.py`で確認済みの通り、Record/Replay追加分は以下2つのhunkに完全に分離しており、SQLite永続化分（`get_db_connection`以降のhunk群）とは重ならない。したがって関数を手で書き写すのではなく、この2hunkだけを`5ef0382`に当てる。

```powershell
git branch phase1-dryrun-baseline 5ef0382
git worktree add ../CELA-baseline phase1-dryrun-baseline
git diff 5ef0382 2133989 -- cela_main.py > ..\record_replay_only.patch
```

`..\record_replay_only.patch`を開き、以下2つのhunkヘッダで始まる区間**だけ**を残して他のhunkをすべて削除する（テキストエディタでの手作業。件数は多くないため目視で十分）:

1. `@@ -12,6 +12,9 @@ import sys` — `sqlite3`/`uuid`/`hashlib`のimport追加（このうち`hashlib`のみRecordスタブに必要だが、未使用importが3行増えるだけで害はないため、hunク全体をそのまま残してよい。このブランチは検証後に破棄するため、AGENTS.mdの「無関係な清掃を混在させない」原則は適用対象外）。
2. `@@ -234,18 +237,105 @@ def get_max_tokens` — `REPLAY_MODE`定数・`reset_call_seq`・`_hash_messages_for_replay`・`_load_replay_fixtures`・`_save_replay_fixtures`・`query_AI`ラッパー・`_query_AI_live`への関数分割、この一連がRecord/Replayスタブの本体。

トリミング後、ベースラインの作業ツリーに適用する:

```powershell
cd ..\CELA-baseline
git apply ..\record_replay_only.patch
```

最後に、`run_ai_vs_ai_loop`関数の冒頭（`app = build_graph()`の直後あたり）に1行だけ手動で追加する（このhunkはSQLite初期化と混在しているため、パッチではなく直接編集する）:

```python
reset_call_seq()
```

`python -m py_compile cela_main.py`で構文確認する。

---

## 2. system_prompt=[]バグ修正の適用（impl_Plan §6準拠）

list版ベースライン（`../CELA-baseline`）に対し、`generate_user_utterance`内の`system_prompt = []`を`system_prompt = ""`に修正し、後続の`+=`を文字列連結に統一する。

**目的**: SQLite化とバグ修正の差分を切り分けるため、両バージョン（list版・SQLite版）に同じバグ修正済みの状態で比較を行う。現行のSQLite版（作業ツリー）は既にこの修正が適用済みであることを確認しておく（`grep -n "system_prompt = " cela_main.py`で該当箇所を確認）。

---

## 3. シナリオ（設計書§5.1準拠）

`cela_main.py`の`if __name__ == "__main__":`ブロック（L2811以降）に定義済みの過疎地域バスシナリオ（`TARGET_GOAL`）をそのまま使う。新規シナリオの作成は不要。

固定パラメータ（`config`、L2855-2865）:

```python
config: Appconfig = {
    "pattern": 4,
    "is_stateless_mode": True,
    "initial_max_turnval": 30,
    "reflection_interval": 3,
    "target_goal": TARGET_GOAL,
    "user_always_remember": True,
    "agent_has_guardrail": True,
    "chat_history_window": 4,
    "expert_history_window": 10,
}
```

list版・SQLite版の両方でこの`config`を変更せずに使うこと。ただし`initial_max_turnval=30`は実装時の仮のデフォルト値であり、**30ターン完走はBL-002の必須要件ではない**（[decision_log.md D-001](../decision_log.md)）。詳細は4章冒頭の注記を参照。

---

## 4. 実行手順（本体）

**終了条件について（[D-001](../decision_log.md)準拠）**: `is_completed`または`halt`による自然終了が理想だが、`agreements`/`decisions`が十分な件数取れていれば、30ターン未到達でも意図的に打ち切ってよい。ただし打ち切る位置は**`app.invoke()`の外側**（画面に次の「🔷 [Turn N]」が出た直後）に限る。`app.invoke()`の内部（差し戻しループの最中など）で強制終了すると、そのターンのfixtureが半端な状態になり、Step 4の構造的一致確認が阻害される。加えて、`turn_count`は`app.invoke()`1回の間凍結される既存挙動（[BL-005](../issue_backlog.md)）があるため、「外側ターンが少ない＝会話が浅い」とは限らない点に注意すること。

### Step 1: list版ベースライン Recordモード実行

```powershell
cd ..\CELA-baseline
$env:CELA_REPLAY_MODE = "record"
$env:CELA_REPLAY_FIXTURE_PATH = "..\CELA\artifacts\phase1_dryrun\fixtures.json"
$env:DSEEK_V4_FLASH_USER_KEY = "<APIキー>"
python cela_main.py
```

- 標準出力・ログ（`./log/`配下、`MultiLogger`が自動生成）を保存する。
- 実行完了後、`fixtures.json`に全ノードの`(label, call_seq)`キー付き応答が記録されていることを確認する。
- **kill（強制終了）試験（合格基準3、7.2節参照）はこのステップでは行わない**。list版は`state["decisions"]`/`state["agreements"]`がプロセスメモリ上のみのため、再起動後保持の検証対象外（SQLite版側でのみ実施）。

### Step 2: list版ベースラインの指標A・B測定用ログ抽出

- 指標B（制約の維持率）: 実行終了時点（自然終了 or D-001に基づく打ち切り）までの会話ログ・成果物から「予算1億円/年間維持費3,000万円」の制約が破綻していないかを目視確認する。`traceability.md`のT-*には、実際に到達した外側ターン数を明記し、30ターン完走を前提とした記述はしない。
- 指標A（却下案の回避率）は、単一プロセスの通し実行では「スレッド切断→新スレッドで再開」という状況が発生しないため、list版では**測定不可**（Hydrate機構がそもそも存在しないため）。指標Aの比較はSQLite版側のみで、Step 4後段の再開シナリオ（4.1節）で行う。

### Step 3: SQLite版（コミット`2133989`）Replayモード実行

```powershell
cd ..\CELA
git checkout 2133989 -- cela_main.py   # HEADが2133989以外に進んでいた場合のみ必要
$env:CELA_REPLAY_MODE = "replay"
$env:CELA_REPLAY_FIXTURE_PATH = "artifacts\phase1_dryrun\fixtures.json"
python cela_main.py
```

- `run_ai_vs_ai_loop`冒頭で`run_id`が新規発行されるが、`CELA_REPLAY_MODE=replay`のため実際のAPI呼び出しは発生せず、Step 1で記録したフィクスチャから応答を再生する。
- **キャッシュミス時は即例外で停止する**（`query_AI`の実装、現行 L298-303）。停止した場合はStep 1のフィクスチャが不足しているか、list版とSQLite版で`query_AI`の呼び出し順序が異なることを意味する。impl_Plan §10の注意点通り、まずフィクスチャのヒット率を疑うこと（DB化のバグと決めつけない）。
- 実行完了後、`cela.db`に記録された`run_id`を控える（ログ冒頭に出力される、または`sqlite3 cela.db "SELECT DISTINCT run_id FROM decisions ORDER BY rowid DESC LIMIT 1;"`で取得）。

### Step 4: 構造的一致の確認（合格基準1・2、impl_Plan §7.2）

```powershell
sqlite3 cela.db
.headers on
.mode column
SELECT count(*), status FROM agreements WHERE run_id='<Step3のrun_id>' GROUP BY status;
SELECT count(*) FROM decisions WHERE run_id='<Step3のrun_id>';
SELECT topic FROM agreements WHERE run_id='<Step3のrun_id>' ORDER BY id;
```

- list版ベースライン側は`state["decisions"]`/`state["agreements"]`をプロセス終了前に`json.dump`等で書き出しておく（現行list版にはダンプ処理がないため、`run_ai_vs_ai_loop`終端に一時的なデバッグ出力を追加してよい。これは検証専用の一時コードであり、恒久コードには含めない）。
- 件数・topic集合・status分布・登録順序（トピックの並び順）が両者で一致することを確認する（テキスト内容の完全一致は求めない。impl_Plan §7.2-4）。
- `_build_agreements_context_from_db(conn, run_id)`の出力と、list版の`_build_agreements_context(state["agreements"])`の出力を、Rejected/Approvedの含まれ方・順序の観点で比較する（合格基準2）。

### 4.1 指標A（却下案の回避率）専用の追加試験

構造的一致確認とは別に、指標Aは以下の追加手順で測定する（設計書§5「指標A」列準拠）。

1. SQLite版を通常実行（`CELA_REPLAY_MODE`未設定 or `off`）し、30ターンの途中でUserが明示的に案を却下する場面が発生するまで進める（過疎地域バスシナリオでは概算予算案が却下されるターンが該当しやすい）。
2. 却下が発生した`run_id`を記録した上で、プロセスを終了する。
3. 同じ`run_id`を使って`assemble_hydrate_context`相当の関数（現行は`_build_hydrate_context_from_db`+`_build_agreements_context_from_db`）を新規プロセスから呼び出し、却下済み案（`status='Rejected'`）がコンテキストに含まれることを確認する。
4. そのコンテキストを使って`expert`ノードに単発で再提案させ、却下済みの案を再度提案してこないことを確認する。

### Step 5: 再起動後保持の確認（合格基準3）

```powershell
# SQLite版実行中に強制終了（Ctrl+Cではなく別プロセスからkill、または実行中にタスクマネージャ等でプロセスをkill）
```

```powershell
sqlite3 cela.db "SELECT count(*) FROM agreements WHERE run_id='<killしたrun_id>';"
sqlite3 cela.db "SELECT count(*) FROM decisions  WHERE run_id='<killしたrun_id>';"
```

行数が0より大きければ合格（`isolation_level=None`の自動コミットにより、kill直前までのappendはすべてディスクに書かれている）。**レジューム（stateを復元してループを再開する処理）はR1の範囲外であり検証しない**（impl_Plan §7.2-3）。

---

## 5. 指標C（収束性とコストのトレードオフ）の測定

設計書§5.1の指標C手順に従い、list版・SQLite版それぞれで**最低5試行**、Step 1/Step 3と同様の手順を通常実行モード（`CELA_REPLAY_MODE=off`、実APIを都度呼ぶ）で繰り返す。

各試行で以下を記録する（`./log/`のログから抽出。ログディレクトリはタイムスタンプ付きで実行ごとに自動生成される）:

| 項目 | 抽出方法 |
|------|---------|
| 差し戻し回数 | ログ中の「差し戻し」文字列の出現回数（reviewer/detectorの差し戻し） |
| 完了までの総ターン数 | `run_ai_vs_ai_loop`終了時の`current_turn` |
| 総トークン消費量 | `_query_AI_live`呼び出し回数 × `max_tokens`設定、または各API応答の`usage`フィールドをログに追記して集計（現行コードは`usage`をログ出力していないため、集計する場合は一時的なデバッグ出力を追加する） |

5試行ずつの平均値をlist版・SQLite版で比較する。成功条件は設計書§5の指標C列を参照（総トークン消費の減少は成功条件としない点に注意）。

---

## 6. 指標D（数値矛盾の検出率）

指標Dは本書の対象外。設計書§5.1の定義通り`pytest`による専用フィクスチャ（`tests/test_f26_detection.py`、新規作成）で検証する方式であり、シナリオベースのドライランではない。別途のissue_backlogエントリとして扱う。

---

## 7. Record&Replayの往復検証（BL-003、impl_Plan §7.2合格基準1・2の本体）

本章はBL-003（list版ベースライン実行結果とSQLite版replay実行結果の構造的一致の回帰確認）を、上記4章の手順そのもので満たす。Step 1（list版Record）→Step 3（SQLite版Replay）→Step 4（構造的一致確認）が回帰確認の本体であり、BL-002とBL-003は同一の実行セットで同時に完了する。追加の実行は不要。

---

## 8. 実行後の後始末

```powershell
git worktree remove ../CELA-baseline
git branch -D phase1-dryrun-baseline
```

`cela.db`・`artifacts/phase1_dryrun/fixtures.json`・`./log/`配下の生ログは、`AGENTS.md`の「Raw logs」規定に従い、プロジェクト固有のログディレクトリ（`artifacts/`）にそのまま残置してよい。結果の要約のみを`../traceability.md`のT-*へ転記すること。

---

## 更新履歴

| 日付 | 内容 |
|------|------|
| 2026-07-18 | 初版作成（BL-002・BL-003対応） |
| 2026-07-18 | 初版作成後にSQLite版の作業ツリー差分がコミット`2133989`として確定したため、0章・1.3節・Step 3の参照を「作業ツリー」からコミットハッシュ固定に修正。1.3節をhunk手動移植方式からgit diff/apply方式に変更（コミット済みになったことでhunk抽出が可能になったため） |
| 2026-07-18 | 実データドライラン中に`turn_count`が`app.invoke()`内で凍結される既存挙動を発見（[BL-005](../issue_backlog.md)起票）。30ターン完走はBL-002の必須要件ではないことを[D-001](../decision_log.md)として決定し、3章・4章冒頭・Step 1・Step 2に終了条件（自然終了 or invoke外側での打ち切り）を反映 |
