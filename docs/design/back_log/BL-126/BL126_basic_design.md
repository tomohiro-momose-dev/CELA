# BL-126/BL-130/BL-131 基本設計: 前提再交渉ワークフロー・Expert相談チャネル・task_id検証

**関連:** [BL-126](../issue_backlog.md#bl-126-bl-086の前提エスカレーションはexpertのリアクティブな経路に限定されておりfacilitatoruser-aiがゴール制約自体を能動的に問い直すプロアクティブな創造的議論モードが未設計), [BL-130](../issue_backlog.md#bl-130-expertが成果物を出さずにuser-aiへ質問相談できる双方向チャネルが未設計現状はuserexpertへの一方向指示のみ), [BL-131](../issue_backlog.md#bl-131-task_plannerの正式なフェーズタスク計画に存在しないtask_idtask_1_1_review等でwrite_agreementwhiteboardが作成されてしまう構造的リスク)、decision_lineage.md 論点76

**状態:** 設計完了・実装は未着手（コード変更は行っていない）

## Context

`log/2026-07-29/1322`ドライランのレビューで、Facilitatorが3件の根本的な実現不可能性（労基法上の人件費下限、予算の二重計上、受入基準自体が予算上限超過）を`escalate_premise_concern`で正式にエスカレーションしたにもかかわらず、その後Facilitatorが自由記述で提案した「制約見直し要求書」タスク（`task_1_1_review`）が、task_plannerの正式な計画に一度も登録されないまま、Expertによって244行・6バージョンの成果物として実行されてしまうという事象が観測された。

その後の`log/2026-07-29/1708`ドライランでも同型の現象が再現しており（`task_1_1_review`が11バージョンまで積み上がり、Reflectionが`stagnant`と正式判定した上でFacilitatorへ差し戻された）、本設計が対象とする問題が実際に繰り返し実害を生んでいることが確認されている。

ユーザーはこれを踏まえ、(a) Facilitator↔User AIが数ラウンド対話して方向性を模索→User承認（旧目標を残しつつ注釈追加、理由記載必須）→Detector確認→Task Planner再構成→正式タスク化、という順序立ったワークフロー（BL-126）、(b) Expertが成果物を出さずにUser AIへ質問・相談できる循環（BL-130）、を新たに設計したいと提起した。あわせて、`write_agreement`が`task_id`をtask_plannerの正式な計画（`state["phases"]`）と一切照合しておらず、任意のtask_idで成果物が作れてしまう構造的な穴（BL-131、今回の事象の直接原因）も発見された。

本設計は、既存コードの詳細調査（Explore agent）とPlan agentによる設計案を踏まえたもの。

## 前提となる現状のコード構造（調査済み）

- **BL-086ツール群**（`ESCALATE_PREMISE_CONCERN_TOOL`/`RESOLVE_PREMISE_CONCERN_TOOL`/`REVISE_GOAL_TOOL`/`FREEZE_AGREEMENT_TOOL`、cela_main.py:1366-1650）: `revise_goal`は`state["goal"]`を**全文上書き**する仕組み（`_apply_text_edits`によるold_text/new_text編集は行うが、goal自体のバージョン履歴テーブルは存在しない）。`FREEZE_AGREEMENT_TOOL`はD-045によりどのノードにも配線されていないデッドコード。**Facilitatorはツールを一切持たない**（自由記述のみ）。
- **`facilitator_node`**（:7285付近）: `route_after_reflection`からstagnant/drift判定でのみ発火。1回の呼び出し＝1メッセージで完結し、User AIとの往復ループは存在しない。`facilitation_count>3`でハード停止。
- **`task_planner_node`**（:6498付近）: `turn_count==1 and not phases`でのみ発火するガード。**ラン途中での計画全体の再構成経路は現状存在しない**（resource_arbiter/integratorの再計画フラグはorchestratorへ戻すのみで、task_plannerには戻らない）。
- **`write_agreement`**（`_write_agreement_impl`/`_commit_agreement_from_tool`）: `depends_on`のID存在チェックはあるが、**`task_id`/`phase_id`が`state["phases"]`に実在するかは一切チェックしていない**。これがBL-131の直接原因。
- **`round_count`**: `generate_user_utterance_node`（cela_main.py:6322付近）でのみ加算。Detector/Reflection/Facilitatorは含まれない（確認済み、新規カウンター不要）。

## 設計方針（ユーザー承認済みの決定事項）

- **Facilitatorは完全なツールループ化**（Expert/User AI同様、複数ツール呼び出し可能なノードにする）。自身で`escalate_premise_concern`等を呼べるようにする。これにより`_CURRENT_CALLER_ROLE`へ`"facilitator"`を追加し、`escalate_premise_concern`等の権限チェック（現在`expert`/`user`のみ許可）に`facilitator`を追加する必要がある。
- **目標（goal）の注釈は既存の`revise_goal`ツールを流用**する。新規ツールは作らない。`edits`パラメータについて、BL-126経由（`source=="essence_dialogue"`等の由来）の場合は`new_text`が`old_text`を包含する（純粋な追記）ことを検証するルールを追加し、「旧文を残しつつ注釈」を機械的に担保する。

## 1. `LineageState`への追加フィールド

| フィールド | 型 | 意味 |
|---|---|---|
| `essence_dialogue_active` | `bool` | Facilitator↔User AIの本質対話モード中フラグ |
| `essence_dialogue_round` | `int` | 本質対話の往復回数（`facilitation_count`とは別カウンタ、混同しない） |
| `essence_dialogue_max_rounds` | `int` | 本質対話の上限（具体値は実装時に確定、要ユーザー確認） |
| `pending_goal_revision` | `dict \| None` | 対話収束後、承認待ちの目標改定案（`proposal_id`/`annotation_text`/`reasoning`/`essence_dialogue_summary`） |
| `goal_revision_pending_review` | `bool` | Userが承認しDetectorの目標変更レビュー待ちの状態 |
| `pending_task_ids` | `list[str]` | Facilitatorの対話中に仮登録されたtask_id（Task Plannerが正式採用/却下するまでの許可リスト） |
| `expert_consultation_mode` | `bool` | Expertが「質問のみ・成果物なし」を宣言した今ターンのフラグ |
| `expert_pending_question` | `str` | Expertの質問文（User AIのプロンプトへ提示） |
| `plan_revision_reason` | `str` | ラン途中の計画再構成トリガー時の理由（`reviewer_feedback`と役割は別） |
| `phases_superseded` | `list[dict]` | 削除ではなく「supersede」された旧phase/taskの記録（`{task_id, reason, superseded_at_round, superseded_by_task_id}`） |

いずれも`LineageState`へ明示的に宣言必須（LangGraphは未宣言キーを伝播しない、BL-038の教訓）。

## 2. 新規/変更ツール

- **Facilitator用ツールリスト新設**: `[THINK_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, PROPOSE_ESSENCE_DIALOGUE_TOOL(新規)]`。`facilitator_node`をExpert/User AI同様のツールループ構造に変更。
- **`ask_user_question`（Expert用、新規）**: 「成果物を出さず質問する」ことを宣言するツール。`question_text`（必須）・`blocking_reason`（必須、acceptance_criteria遂行に本当に必要な理由）。呼ばれると`expert_consultation_mode=True`・`expert_pending_question`をセット。Expertの既存ツールリスト・`light_system_prompt`のツール一覧文言の両方に追加が必要（片方だけ更新すると齟齬が生まれる）。
- **`revise_goal`の拡張**: 既存の「Open escalationが前提」という制約に加え、`pending_goal_revision`（本質対話収束後の提案）からの発火も許可。`source=="essence_dialogue"`の場合、`new_text`が`old_text`を包含すること（純粋追記）を検証する。
- **BL-131**: 新規ツールは不要。`_write_agreement_impl`/`_commit_agreement_from_tool`内の検証ロジック追加のみ。

## 3. グラフノード・ルーティングの変更

- **BL-130（Expert相談チャネル）**: Expertノードが`expert_consultation_mode`/`expert_pending_question`を状態へ反映。`expert_detector_node`・`expert_decision_extractor`は`expert_consultation_mode`時に厳格な監査・抽出をスキップ（Detectorは軽量パス、Decision Extractorは何も抽出しない）。`route_after_expert_detector`/`route_after_expert_decision`に新分岐を追加し、`generate_user_utterance`へ直行させる。`generate_user_utterance_node`は`expert_pending_question`を検出しUser AIのプロンプトへ明示的に提示、消費後にフラグをリセット。
- **BL-126（本質対話ループ）**: `facilitator_node`をツールループ化し、`call_facilitator`の応答が`essence_dialogue_active`を制御。**新規ループエッジ`facilitator ⇄ generate_user_utterance`**（現状存在しない、本設計で最も構造変更が大きい部分）を追加し、`essence_dialogue_max_rounds`到達か収束（Facilitatorが`propose`相当のツール呼び出し）まで往復。収束後、User AIが`revise_goal`を呼び`pending_goal_revision`を適用→`goal_revision_pending_review=True`→Detectorの目標変更レビューモードへ→承認後`plan_revision_reason`をセットしtask_planner_nodeへ（ガード緩和）→再計画完了後、該当task_idを`pending_task_ids`から解除し正式タスク化。

## 4. 目標（goal）のバージョニング

`whiteboard_drafts`/`plan_drafts`と同型の**新規`goal_drafts`テーブル**を追加（`apply_whiteboard_patch`/`apply_plan_patch`を直接テンプレートとする）。`state["goal"]`は「現在有効な本文」を保持したまま（既存の参照元に影響を与えない）、`goal_drafts`が追記のみの版管理・全文履歴を担う。「旧文を残しつつ注釈」は、`revise_goal`が`new_content = old_content + "\n\n## [ANNOTATION vN] " + annotation + "\n理由: " + reasoning`という追記ルールで`apply_goal_patch`へ渡すことで実現する。

**[BL-132を踏まえた補足]**: `whiteboard_drafts`/`plan_drafts`は`(phase_id, task_id)`のみで版管理されており`topic`列を持たない。`goal_drafts`は単一の目標文書のみを扱うため本質的にこの問題は生じないが、実装時に誤って複数の異なる文書を`goal_drafts`の同一キーへ混在させないよう注意する（1708ログで`task_1_1_review`の`whiteboard_drafts`版チェーンに複数の異なる文書が混在し、Expertが繰り返し「初版作成」から書き直す混乱の一因になったことが示唆されており、同型の設計ミスを避ける）。

## 5. Detectorの「目標変更レビュー」モード

`call_detector`に`review_mode: Literal["task_output", "goal_change"]`パラメータを追加（デフォルト`"task_output"`、`goal_revision_pending_review`時のみ`"goal_change"`）。既存の`target_role`分岐（ドメイン/数値監査）とは直交する軸として追加し、既存パスには一切影響しない別プロンプト分岐とする。目標変更モードでの判断基準（罠の形で明記、D-094の設計原則に準拠）：
- 旧文が置換でなく追記として保持されているか
- 理由づけが提起された懸念の重大さに見合っているか
- 変更が提起された懸念の範囲内に収まっているか（スコープ逸脱がないか）
- **新しい目標文の数値的な最適性そのものは評価しない**（それは後続の通常タスク遂行で検証される）——過剰な監査は不要な差し戻しを招くため明示的に除外する

出力契約は既存の`{"risk":..., "constraint_issue":..., "comment":...}`と同型を維持。

## 6. Task Plannerのラン途中再構成

- ガード緩和: `if (turn_count==1 and not phases) or state.get("plan_revision_reason")`。消費後は`plan_revision_reason`を即クリア（`plan_reviewer_feedback`と同じパターン）。
- `call_task_planner`に`existing_phases`・`revision_reason`パラメータを追加。プロンプトで「関係ない既存タスクには触れず、影響を受けるタスクのみをsupersede/追加すること」を明示。
- **「削除ではなくsupersede」**: 該当task/phaseは`state["phases"]`から除去しつつ`state["phases_superseded"]`へ記録し、`write_agreement(action_type="SUPERSEDE", ...)`で監査証跡を残す（BL-092/BL-095の既存SUPERSEDE検知ロジックの延長として扱える）。`integrator_node`はsuperseded task_idの成果物を最終統合から除外するよう確認が必要。

## 7. Reflectionへの迎合（collusion）監査基準の追加

`call_reflection`のでっちあげ監査ブロック直後に、判断基準ベースの新パラグラフを追加する。譲歩・方針転換の回数を数えるのではなく「その転換の重大さに見合った理由づけがあるか」を問う形で記述する（本文はD-094の「判断基準と罠」トーンに合わせて日本語で作成、既存の`discussion_status`/`note`出力契約は変更しない）。

## 8. 実装順序（推奨）

1. **BL-131**（task_id検証＋`pending_task_ids`）: 最小・独立。ただしBL-126が後で使う許可リスト機構を最初から組み込んでおく（後からの手戻りを避けるため）。
2. **BL-130**（Expert相談チャネル）: BL-131と並行可能、独立性高い。
3. **BL-126 Stage A**（`goal_drafts`テーブルとバージョニング基盤のみ、対話ロジックなし）: 既存の反応的`revise_goal`経路にも先に適用し動作確認。
4. **BL-126 Stage B**（Detector目標変更レビューモード）: 既存の反応的経路で先に検証してから対話モードに繋げる。
5. **BL-126 Stage C**（Task Plannerのラン途中再構成、supersede機構）。
6. **BL-126 Stage D**（Facilitatorのツールループ化＋本質対話ループエッジ）: 最も規模が大きく新規性が高いため最後。
7. **Reflectionの迎合監査基準追加**: 依存関係なし、いつでも着手可能（早めが望ましい）。

## 残る要確認事項（実装着手前に確定させる）

- `essence_dialogue_max_rounds`の具体的な上限値
- 目標変更レビューモード（Detector）を既存の反応的`revise_goal`経路にも適用するか、新しいプロアクティブ経路のみに限定するか
- ラン途中再構成が`task_plan_reviewer_node`（既存の実行前ゲート）を通るか、スキップするか

## 検証方法

- 各Stageごとに`python -m py_compile cela_main.py`、既存オフラインスモークテスト（`test_r3_smoke.py`等）Pass。
- Stage単位で新規テストを追加（BL-131の検証ロジック、BL-130のconsultation modeルーティング、BL-126各Stageの状態遷移）。
- 実LLM再ドライランで、`task_1_1_review`のような計画外task_id発生が防止されること、Expertの相談ターンで成果物監査がスキップされること、本質対話→正式タスク化のフローが機能することを確認する（1708ログのような「同一task_idへの多文書混在」「stagnant判定後の未解決繰り返し」が解消されるかを重点確認）。
- `docs/design/back_log/issue_backlog.md`のBL-126/130/131を本設計完了済みとして更新、`python scripts/check_docs_consistency.py`で確認。
