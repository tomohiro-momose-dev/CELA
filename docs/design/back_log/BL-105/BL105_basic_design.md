# BL-105/D-086 基本設計: 一時停止・再開をLangGraph公式checkpointer（SqliteSaver + thread_id）ベースへ移行する（Tier 1）

**関連:** [BL-105](../issue_backlog.md#bl-105-checkpointresume機構がentry_pointから全体再走行するため未応答のuser発言が二重に積まれるlanggraph本来のcheckpointertask未導入という設計ギャップ)、[D-086](../../decision_log.md#d-086-checkpointresume機構をlanggraph本来のcheckpointertaskベースへ移行するかbl-105)

**状態:** 実装完了（`done`）。範囲はTier 1（ノード境界での正しい再開）のみ。Tier 2（ノード内部の`@task`化、ツールループ途中でのCtrl+C対応）は将来ヒューマンインザループ機能を具体的に設計する際に改めて着手する方針（ユーザー承認済み、`docs/design/decision_lineage.md`参照）。

---

## Context

CELAのドライランは長時間化しやすく、Ctrl+Cでの一時停止→後日`--resume`での再開が常用されている。現行実装（`_save_checkpoint`/`_load_checkpoint`、`cela_main.py:206-224`）は自前のJSON checkpointで、`--resume`時は必ず`app.stream(state, stream_mode="values")`をグラフのentry_point（`goal_essence`、`graph.set_entry_point("goal_essence")`、`cela_main.py:9129`）から再実行する。`goal_essence`/`task_planner`/`task_plan_reviewer`は`goal_essence_done`/`plan_review_done`等のフラグでスキップされるが、直後の`generate_user_utterance_node`（`cela_main.py:7546`）には再入場ガードが無く無条件に`state["chat_history"]`へuser発言を追記するため、**ラウンド途中（Expertの応答前・Detectorの監査前等、どの段階でCtrl+Cしても）で一時停止したものを再開すると、必ず`generate_user_utterance_node`から再実行され、既にチェックポイントに含まれるuser発言に重複してもう1つuser発言が積まれる**（`⚠️ role連続を検出`警告として既知）。これはBL-105として`open`のまま設計検討だけ済んでいた案件で、D-086（`decision_log.md`）は`pending`のまま放置されていた。

今回、`log/2026-08-04/1123→1355→1435→1546→1548`という同一runが5つの異なる`log/`ディレクトリへ跨って何度もCtrl+C/`--resume`を繰り返した実例を追跡する中で、ユーザーから改めて「そろそろLangGraphの正式なチェックポイントを実装したい」と要望があった。

Context7で現行のLangGraph公式ドキュメント（`/websites/langchain_oss_python_langgraph`）を再確認し、`compile(checkpointer=...)` + `thread_id`ベースの再開（`graph.invoke(None, config)`/`graph.stream(None, config)`）は、entry_pointからの全体再走行ではなく**中断した直後のノードから**再開することを確認した。ただしノード**内部**（Expert/Detectorのツールループの途中）でのCtrl+Cには対応できず、そのノードは最初から再実行される（公式ドキュメントにも明記）。この「ノード内部の途中再開」（Tier 2、`@task`化）は、将来ヒューマンインザループ機能を具体的に設計する際に改めて着手することとし、**今回はTier 1（ノード境界での正しい再開）のみを実装する**（ユーザー承認済み）。

## 設計上の重要な確認事項（コード・LangGraph公式ドキュメント両方で裏取り済み）

1. **グラフは「1ラウンド＝1回のapp.stream()」ではない**。`route_after_expert_decision`/`route_after_reflection`/`route_after_facilitator`/`route_after_reviewer`（`cela_main.py:9267-9384`）を追うと、大半のラウンドは`generate_user_utterance`へ内部的にループバックし続け、`END`に到達するのは`reflection_interval`（既定3ラウンド）ごとの`reflection`、または`facilitator`/`reviewer`/`halt`経由のみ。つまり外側Pythonの`while current_turn <= max_turns:`（`cela_main.py:9522`）の1イテレーションが、実際には複数ラウンドをグラフ内部で消化してから戻ってくる。
2. **outer whileループの「ターン間」処理（`cela_main.py:9552-9591`）は完全に読み取り専用**（decisionsテーブルからの表示・`break`判定・`current_turn += 1`のみ、`state`を一切変更しない）。よって外側whileループの構造自体は変更不要——変更が必要なのは「`app.stream()`に何を入力するか」の1点のみ。
3. **`config`（`Appconfig`）は完全に静的**（`if __name__ == "__main__":`ブロック内、`cela_main.py:9657`の1箇所でのみ構築される、実行のたびに同一内容）。チェックポイントへ保存・復元する必要は無い（現行JSON checkpointは保存していたが、実質死んでいた冗長データだった）。
4. **`current_turn`は`state["turn_count"]`と毎イテレーション同期**（`cela_main.py:9532`）。再開時は`state.get("turn_count", 1)`から導出でき、別途持ち回る必要はない。
5. **`db_path`（cela.db本体）は既に`LineageState`のフィールド**（初期state構築の`"db_path": db_path`）。checkpointerが自動的に保存・復元する。
6. **`LineageState`で`Annotated`（reducer指定）を持つのは`goal: Annotated[str, _take_latest]`（`cela_main.py:4689`）のみ**で、`_take_latest(a, b)`は単純に`return b`（上書き、追記ではない）。他の全フィールドもデフォルトのLastValue（上書き）チャネル。これにより、**同一`thread_id`へ毎ターン完了済みのフルstate dictをそのまま入力として再投入する現行パターン**（`chat_history`等のリストが二重蓄積しない）は、checkpointer導入後も安全であることが確認できた。
7. **新規依存**：`langgraph`本体（1.2.9、導入済み）とは別に、`langgraph-checkpoint-sqlite`（`SqliteSaver`/`AsyncSqliteSaver`を提供）のインストールが必要（未導入、`pip show`で未検出）。`InMemorySaver`はプロセス再起動をまたげないため今回の用途（Ctrl+Cでプロセス終了後、後日`--resume`）には使えない。requirements-dev.txt以外に実行時依存を管理するファイルが存在しない現状を踏まえ、`requirements.txt`を新規作成し`langgraph-checkpoint-sqlite`を記載した上でインストールする。

## 実装内容

### 1. 依存関係追加
`requirements.txt`（新規）に`langgraph-checkpoint-sqlite`を追記し、`pip install -r requirements.txt`でインストール。

### 2. `cela_main.py`

- **削除**：`_save_checkpoint`/`_load_checkpoint`（`cela_main.py:206-224`）とその直前のコメントブロック（`一時停止・再開（チェックポイント）`セクション見出しごと）。合わせて、entry_pointに関する古いコメント（`cela_main.py:202-205`および`7735-7737`付近、「entry_pointはtask_planner固定」という既に事実と異なる記述）も削除・書き換える。
- **追加**：`from langgraph.checkpoint.sqlite import SqliteSaver`、`from langgraph.checkpoint.base import BaseCheckpointSaver`のimport。モジュール定数`CELA_CHECKPOINT_DB_PATH = "cela_checkpoints.db"`（`cela.db`と同じくリポジトリ直下、run跨ぎで単一ファイル。`thread_id == run_id`で一意に引けるため、`log/<timestamp>/`ディレクトリ跨ぎでcheckpointファイルを探し回る現状の混乱が解消される）。
- **`build_graph()`のシグネチャ変更**（`cela_main.py:9093`〜、`return`は`9388`）：`def build_graph(checkpointer: BaseCheckpointSaver | None = None):` とし、末尾を`return graph.compile(checkpointer=checkpointer)`に変更。デフォルト`None`により、既存4箇所のテスト呼び出し（`build_graph()`引数無し、トポロジー確認のみ）は無変更で動作する。
- **`run_ai_vs_ai_loop`の書き換え**（`cela_main.py:9394`〜）：
  - 引数`resume_from: str | None`を`resume_run_id: str | None`へ改名（意味が「JSONファイルパス」から「run_id文字列」に変わるため）。
  - 関数冒頭で`checkpointer_conn = sqlite3.connect(CELA_CHECKPOINT_DB_PATH, check_same_thread=False)` → `SqliteSaver(checkpointer_conn)` → `.setup()`（冪等）→ `app = build_graph(checkpointer=checkpointer)`。
  - LangGraphランタイム設定用の辞書は`runtime_config = {"configurable": {"thread_id": run_id}}`という**別名**で扱う（既存の`config: Appconfig`パラメータと名前が衝突するため、絶対に`config`という変数名を再利用しない）。
  - `resume_run_id`がある場合：`app.get_state(runtime_config)`で直近スナップショットを取得し、`snapshot.values`が空ならrun_id誤りとしてエラーメッセージを出して終了。取得できたら`state = snapshot.values`、`db_path = state["db_path"]`、`current_turn = state.get("turn_count", 1)`を復元。既存の「再開直後にhalt済みなら即終了」チェック（現行`cela_main.py:9424-9429`のロジック）はそのまま踏襲。`snapshot.next`が非空（＝ラウンド途中で止まっている、Ctrl+Cの大半のケース）なら、最初の`app.stream()`呼び出しへの入力を`None`にする（＝そのラウンドの続きから再開）。`snapshot.next`が空（＝ちょうどラウンド境界=END直後で止まっていた稀なケース）なら、通常の「新規ターン」としてフルstateをそのまま投入する。
  - `resume_run_id`が無い場合：現行通り新規`run_id`発行＋フルstate構築（`cela_main.py:9433-9502`の初期state辞書リテラルは内容無変更）。
  - 起動バナーに`🆔 run_id: {run_id}`を追加表示（現状はresume時にしか表示されないため、フレッシュ起動時にも必ず見せることで、後で`--resume`する際に必要な情報をユーザーが確実に把握できるようにする）。
  - outer whileループ本体：`app.stream(next_input, config=runtime_config, stream_mode="values")`という形に統一する（`next_input`は最初のイテレーションのみ上記の`None`/`state`分岐、2回目以降は常に直前の完了stateをフル投入——現行と同一パターン）。ループ内の手動`_save_checkpoint`呼び出しは削除（checkpointerが各ノード完了ごとに自動永続化するため不要）。
  - `KeyboardInterrupt`ハンドラを簡略化：手動保存は不要（既に完了済みノードまではcheckpointerが永続化済み）、メッセージのみ`python cela_main.py --resume {run_id}`形式に変更。
  - `try/finally`の再編成：`checkpointer_conn`のクローズを、既存の`_DB_CONN.close()`と同じ`finally`ブロックでカバーする（現行の「resume直後のhalt早期return」パスは`_DB_CONN`より前に発生するため、この早期returnでも`checkpointer_conn`が確実に閉じるよう、`try/finally`の開始位置をcheckpointer接続の直後まで前倒しする）。
- **CLI引数**（`cela_main.py:9601-9609`付近）：`--resume`の`metavar`を`RUN_ID`へ、ヘルプ文言を「起動時バナーに表示されるrun_idを指定して再開する」に変更。`__main__`末尾の呼び出しを`run_ai_vs_ai_loop(target_goal=TARGET_GOAL, config=config, resume_run_id=_cli_args.resume)`に変更。

### 3. `.gitignore`
`cela_checkpoints.db*`を追加（`-shm`/`-wal`/`-journal`等の付随ファイルもまとめてカバー）。

### 4. `tests/test_checkpoint_resume.py`の書き換え
- **削除**：`test_save_and_load_checkpoint_roundtrip`・`test_save_checkpoint_is_atomic_no_leftover_tmp_file`・`test_save_checkpoint_overwrites_previous_content`（対象関数が消滅するため）。
- **維持**：`test_task_planner_node_skips_replanning_when_phases_already_exist`（ストレージ方式と無関係な既存のノード冪等性ガード、無変更）。
- **新規追加**（実LLM呼び出し無し、CELAの実グラフではなく最小の合成グラフ2種で検証——ノードA/ノードB＋条件分岐ループ＋END、という同型パターン）：
  1. `test_resume_continues_from_next_pending_node_not_entry_point`：`app.stream()`のgeneratorを最後まで消費せず打ち切ってCtrl+C相当を模擬し、同じ`thread_id`へ`None`を渡すと、entry_pointからではなく中断直後から再開し、既に完了した処理が再実行されないことを検証する（本修正の核心となる回帰テスト）。
  2. `test_multi_turn_same_thread_id_after_completion_does_not_duplicate_list_fields`：CELAの外側whileループと同型（同一`thread_id`へ毎ターン、直前の完了stateをフルdictとして再投入）を模擬し、リスト系フィールドが二重蓄積しないことを検証する（`goal: Annotated[str, _take_latest]`が上書き方式である前提の裏付け）。
  3. `test_build_graph_accepts_checkpointer_and_defaults_to_none`：`cela_main.build_graph()`（引数無し）と`build_graph(checkpointer=None)`が同一トポロジーを返すことを確認し、既存4テスト（`test_bl087_stage2_task_plan_reviewer_node.py`・`test_bl087_stage3_4_goal_essence.py`・`test_bl126_stage_d_essence_dialogue.py`・`test_bl130_ask_user_question.py`、いずれも`build_graph()`をトポロジー確認のみに使用）との後方互換を保証する。
  4. `run_ai_vs_ai_loop`の分岐ロジック自体は、`cela_main.build_graph`をmonkeypatchして軽量スタブの疑似コンパイル済みグラフ（`.get_state`/`.stream`呼び出しを記録するだけ）を返させ、`resume_run_id="存在しないid"`でエラーメッセージを出して早期returnすること、`resume_run_id=None`（新規run）では`.get_state`が一切呼ばれないことを検証する（実グラフ・実LLM呼び出し無し）。

### 5. `tests/tools/db_checker.py`の追随修正
`extract_run_id_from_checkpoint`（`checkpoint.json`読み取り、廃止対象）を削除し、`cela.db`の`decisions`テーブルから最新`run_id`を取得する`extract_latest_run_id_from_db(db_path)`へ置き換える。`--log-dir`引数自体はホワイトボードファイル突き合わせという別用途があるため維持し、run_id自動検出のフォールバック元だけを差し替える。ヘルプ文言（「省略時は checkpoint.json から自動検出」）も更新する。

## 影響範囲
- `cela_main.py`：`run_ai_vs_ai_loop`・`build_graph`・CLI引数・`_save_checkpoint`/`_load_checkpoint`削除。他ノード関数（Expert/Detector/User AI等）は無変更——Tier 2（ノード内部の`@task`化）を含まないため。
- 既存の冪等性フラグ（`goal_essence_done`・`plan_review_done`等）は無変更で維持（「グラフが自然にENDへ到達し、次のPythonターンでフルstateを再投入する」通常パターンでは今後も必要）。
- テスト：`tests/test_checkpoint_resume.py`書き換え、`tests/tools/db_checker.py`小修正。他の既存テストへの影響は無い見込み（`build_graph()`呼び出し4箇所はデフォルト引数で後方互換）。

## 検証
1. `pip install -r requirements.txt`（新規`langgraph-checkpoint-sqlite`導入）。
2. `python -m py_compile cela_main.py`。
3. `pytest tests/test_checkpoint_resume.py -v`（新規4テスト含む）。
4. 影響を受けうる既存テスト（`test_bl087_stage2_task_plan_reviewer_node.py`・`test_bl087_stage3_4_goal_essence.py`・`test_bl126_stage_d_essence_dialogue.py`・`test_bl130_ask_user_question.py`）で無退行確認。
5. フルオフラインスイート`pytest tests/ -q --ignore=tests/test_f26_detection.py`。
6. **実ドライランでの手動確認**（オフラインテストでは代替不可）：短いゴールで`python cela_main.py`を起動→数ラウンド進めた後、ラウンド途中（Detector監査中など）でCtrl+C→起動バナーに表示された`run_id`で`python cela_main.py --resume <run_id>`→`chat_history`にuser発言の重複（role連続）が発生しないこと、および`cela_checkpoints.db`が1ファイルに保たれること（`log/`ディレクトリを跨がないこと）を目視確認する。

## ドキュメント
- `docs/design/back_log/issue_backlog.md`のBL-105を`open`→`done`へ更新。
- `docs/design/decision_log.md`のD-086（現状`pending`、決定理由・決定内容が未記入）を、候補B（Tier 1採用）で確定させ記入する。
- `docs/design/decision_lineage.md`に本セッションの経緯（ユーザーからのTier1/Tier2スコープ質問「将来HITL実装を見据えるとどちらが良いか」への回答含む）を新規論点として記録する。
- 実ドライランでの効果確認（Ctrl+C→resumeでの重複解消）は次回の長時間ドライラン待ちとする。

## スコープ外（Tier 2、将来課題）

ノード**内部**（Expert/Detectorの`_query_AI_live`ツールループの途中）でのCtrl+Cは、そのノードが最初から再実行される（LangGraph公式ドキュメントにも明記された既知の制約）。これはTier 1導入後も変わらない——今日と同じ挙動であり、新規の後退ではない。真に解消するには`@task`デコレータでノード内部の個々の呼び出しを個別checkpoint対象にする必要があるが、これは`interrupt()`ベースのヒューマンインザループ機能（例:「ゴール改定を承認する前に人間に確認させる」）を具体的に設計するタイミングで、そのゲートが実際にどのツール呼び出しの前に必要かに応じて着手する方が過剰設計を避けられると判断し、今回は見送った。
