# BL-192: User AI Stage4の指示文を強化し、根拠不明な数値のweb_search義務化・期待される思考プロセスの明示を徹底する 基本設計

## Context

BL-191設計中（User AIのStage4に`schedule_task_focus`ツールを追加し、過去タスクへの手戻りを可能にする機構設計）、ユーザーから以下の追加要望が出た（原文）：

> 「ユーザーAIプロンプトにも、『過去タスクの洗い直しをする』とか『次のタスクと過去タスクは依存関係にあるから、過去タスクも同時に検討する』とか、agreementを書く際の注意（過去タスク書き換えにはSUPERSEDEが必要等）、『次タスクで根拠があいまやな数値・前提がある場合はまずweb検索で調べて『もっともらしさ』を排除する指示』など、単に『次はこれをやれ』ではなく、Expertへどういう思考で・どう行動してほしいかを網羅的に指示する部分も強化したい」

このうち「過去タスクを書き換える際のSUPERSEDE注意」はBL-191の`joint_focus`機能のcompanion表示ヘルパー（`_get_task_focus_companion_text`）へ直接組み込んだ（併記対象タスク自体を修正する場合は`action_type='SUPERSEDE'`が必要という固定文言）。

残る2点——**①根拠不明な数値・前提のweb_search義務化、②期待される思考プロセスの網羅的な明示——はBL-191のスケジューリング機構（`redirect_backward`/`joint_focus`）の有無に関わらず**Stage4の指示文全般に当てはまる独立した関心事**であるため、ユーザーとの合意により**BL-192として切り出した**。

BL-188が確立した「**プロンプト誘導のみ**（機械的な強制ゲートは追加しない）」という標準方針を踏襲し、**新規のstate・ツール・DBスキーマは一切不要**、Stage4のシステムプロンプトへの追記のみで完結する設計とした。

## 問題点（Gap）

### 2-1. Stage4の指示文は「what」だが「how（思考プロセス）」を指示しない

現状のStage4（`generate_user_utterance`内、L8498-8558）のシステムプロンプトは以下の観点で指示を与えるが、**根拠不明な数値の検証義務**と**思考プロセスの明示**という2点については指示が不足している：

- **何を指示するか（what）**: 次タスクへ進む / 現タスクを修正する / PROJECT_COMPLETE宣言
- **どうやって確認するか（how）**: Detectorによる数値監査の結果を信頼するよう指示（L8501-8517, L8061-8062）
- **欠落している**: 確定値のcitationsに`type="web"`の裏付けがなく場合のweb_search義務、思考プロセスの残し方

### 2-2. 非Stage4パスへの指示漏れ（独立レビュー指摘7-2）

`_is_normal_review_turn`（L7806）が`False`となる以下の場面では、Stage1-3-4の4段階パイプラインを**すべてスキップ**し、L8139以降の非Stage4パス（`system_prompt` + `system_prompt_trailing`）を直ちに使う：

- `constraint_issue == "major"`による差し戻しターン（BL-142/143）
- `essence_dialogue_active`（BL-126 Stage D）
- `expert_pending_question`（BL-130）
- 初回ターン（`turn_count == 1`）
- 終盤（`turn_count >= max_turns - 2`）

これらは**User AIが指示を出し直す重要な場面**であるにもかかわらず、Stage4にしかBL-12の指示ブロックを入れないと**全く適用されない**。特に**差し戻しターン**では、LLMが前回の矛盾を再検討する際にこそweb_searchでの検証が必要な場面が多い。

## 設計方針

### 3-1. 共通定数による文言の二重管理回避

Stage4と非Stage4パスの両方へ**同じ指示ブロック**を注入する。二重管理（2箇所に別々の文言を書く）は、片方を更新した時にもう片方を忘れるリスクを招けるため、**モジュール定数**として1箇所に定義する：

```python
# [BL-192] User AIがExpertへ次タスクを指示する際の指示文の質を強化する共通ブロック。
# BL-188が確立した「プロンプト誘導のみ（機械的な強制ゲートは追加しない）」という標準方針を
# 踏襲する（BL-042: Detectorの硬直判定によるトークン浪費事故の再発防止という設計判断）。
# Stage4（generate_user_utteranceの4段階パイプライン内、次タスク指示ステージ）と、
# 差し戻し・本質対話等でStage4をスキップする非Stage4パスの両方から参照する（文言の
# 二重管理を避けるため、モジュール定数として1箇所に定義する）。
```

### 3-2. BL-188「プロンプト誘導のみ」方針の踏襲

BL-188は「すべての情報にソース（citations）を明示させる」をテーマに、**プロンプトによる指示・誘導のみ**でLLMの行動をガイドする（機械的な強制ゲートは追加しない）という方針を確立した（decision_log.md D-142）。BL-192も同じく：

- **web_search toolをUser AIに直接追加しない**（User AIはプロジェクトオーナーであり、Agent AI/Expert AIが実作業を行う）
- **User AIに「Expert AIにweb_searchを指示するよう」プロンプトで指示する**（Expert AIは既に`WEB_SEARCH_TOOL`をtool listに含んでいる：`call_expert` L6321, L6875, L7212, L7378, L9488）
- このため、BL-192は**新規state/DB/ツールスキーマを一切追加しない**

### 3-3. 2つの指示

#### ① 根拠不明な数値・前提のweb_search義務化

> そのタスクが依存する確定値（verified_facts/agreementsのcitations）に`type="web"`の裏付けがなく
> `expert_calculation`/`goal_text`のみの場合、指示文の中で「このタスクの前提となる
> ○○の数値はまだ一次情報での裏付けがないため、web_searchで検証してから進めること」と
> 具体的に名指しで指示してください。Expertが『もっともらしい』値を無検証のまま踏襲する
> ことを診容しないでください。

**設計判断**: `type="web"`のcitationsがある値は既に一次情報で裏付け済みとみなし、再検証は不要。`expert_calculation`（Expertが算出した値）や`goal_text`（ゴール文からの直接引用）のみの値は裏付けが一次情報に基づくものか不明確なため、**web_searchでの検証を義務付ける**。これにより、Expert AIが「もっともらしい」推測値を無検証で踏襲するハルシネーションを防ぐ。

#### ② 期待される思考プロセスの明示

> 成果物の完成条件（acceptance_criteria）を並べる
> だけでなく、どのような順序・観点で検討すべきかを明示してください。例：「まず◯◯の
> 実測/公的統計を確認し、次に△△との整合性を検算し、最後に□□の受入基準を満たすか
> 確認せよ」。直前のタスクや併記対象タスク（[BL-191] task_focus_companion）との
> 依存関係がある場合は、それらの確定値との整合性確認を思考プロセスの一部として
> 明記してください。

**設計判断**: acceptance_criteriaを単に並べるだけでは、Expert AIは論理的な検討順序をとらず、散発的な取り組みになる。**思考プロセスの順序・観点**を明示することで、体系的な検討を誘導する。BL-191の`joint_focus`機能（併記対象タスク）との整合性確認も思考プロセスの一部に含める。

## 実装箇所

### 4-1. 共通定数定義

```python
# cela_main.py:6081-6095
_BL192_DIRECTIVE_QUALITY_BLOCK = (
    "\n[BL-192] 次タスクの指示を書く際は、以下2点を徹底してください：\n"
    "①【根拠不明な数値・前提のweb_search義務化】そのタスクが依存する確定値"
    "（verified_facts/agreementsのcitations）に`type=\"web\"`の裏付けがなく"
    "`expert_calculation`/`goal_text`のみの場合、指示文の中で「このタスクの前提となる"
    "◯◯の数値はまだ一次情報での裏付けがないため、web_searchで検証してから進めること」と"
    "具体的に名指しで指示してください。Expertが『もっともらしい』値を無検証のまま踏襲する"
    "ことを許容しないでください。\n"
    "②【期待される思考プロセスの明示】成果物の完成条件（acceptance_criteria）を並べる"
    "だけでなく、どのような順序・観点で検討すべきかを明示してください。例：「まず◯◯の"
    "実測/公的統計を確認し、次に△△との整合性を検算し、最後に□□の受入基準を満たすか"
    "確認せよ」。直前のタスクや併記対象タスク（[BL-191] task_focus_companion）との"
    "依存関係がある場合は、それらの確定値との整合性確認を思考プロセスの一部として"
    "明記してください。\n"
)
```

**定義場所**: `_THINK_TRAILER_SENTENCE`（L6070）の直後、`_get_open_escalations_text`の定義開始（L6096）の前。他のプロンプト部品定数（`_THINK_TRAILER_SENTENCE`, `_BL093_THINK_VALUE_PARAGRAPH`等）と隣に配置し、関連性を明示する。

### 4-2. Stage4への注入

```python
# cela_main.py:8522
# stage4_system_promptの構築内（承認済み分岐、L8501-8525）
f"{_task_focus_transition_notice}"       # L8521
f"{_BL192_DIRECTIVE_QUALITY_BLOCK}"      # L8522 ← 注入
f"【同じ検証・計算を繰り返さない】..."     # L8523
```

**注入タイミング**: `current_phase`/`current_task_id`の不整合ブロック（`_build_task_transition_blocked_notice`）とBL-191の`task_focus_transition_notice`の後、「同じ検証・計算を繰り返さない」指示の前。BL-192の2つの指示（web_search義務・思考プロセス）は、**指示を出す前の準備**なので、指示内容（「次タスクへの具体的な指示文を簡潔に書いてください」）より前に配置。

**Stage4のtools**: `tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL]`（L8570, L8577）。`WEB_SEARCH_TOOL`は含まない（User AIは指示を出す側であり、Expert AIがweb_searchを実行する）。

### 4-3. 非Stage4パスへの注入

```python
# cela_main.py:8855-8859
# system_prompt_trailingの構築内
system_prompt_trailing += _build_escalation_resume_notice(state)       # L8852 [BL-096]
system_prompt_trailing += _build_task_transition_blocked_notice(state)  # L8853 [BL-125/BL-176/BL-190]
system_prompt_trailing += _build_task_focus_transition_notice(state)   # L8854 [BL-191]
# [BL-192/独立レビュー指摘7-2] このパスは差し戻し（constraint_issue=="major")・本質対話・
# Expert相談応答・終盤・初回ターン用であり、Stage4をスキップするため、Stage4側にのみ
# 指示を入れるとこれらの重要な場面でBL-192の指示（web_search義務化・思考プロセス明示）が
# 一切適用されなくなる。共通定数を参照し文言の二重管理を避ける。
system_prompt_trailing += _BL192_DIRECTIVE_QUALITY_BLOCK                        # L8859 ← 注入
```

**注入タイミング**: BL-191の`_build_task_focus_transition_notice`（L8854）の後、BL-185の差し戻し通知（L8893 `if state.get("drift_flag")`ブロック）の前。`system_prompt_trailing`の末尾に来るため、chat_historyの直後（BL-185の設計による、messages配列の最後に配置）、User AIの最後の指示として読まれる。

**非Stage4のtools**: `[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, RESOLVE_PREMISE_CONCERN_TOOL, REVISE_GOAL_TOOL, FREEZE_AGREEMENT_TOOL, WRITE_ISSUE_TOOL, READ_ISSUES_TOOL, THINK_TOOL]`（L8954, L8965）。`WEB_SEARCH_TOOL`は含まない。

### 4-4. toolsリストへのWEB_SEARCH_TOOL追加は不要

BL-192の指示は**User AIに Expert AIへweb_searchを指示する**内容であり、User AI自身がweb_searchを呼ぶ必要はない。Expert AIの`call_expert`（L6321, L6875, L7212, L7378, L9488）は既に`WEB_SEARCH_TOOL`をtools listに含んでいる。したがって、BL-192は**工具的な変更を一切伴わず、プロンプト文言の追記のみ**で完結する。

## 設計上の意思決定

| 決定 | 内容 | 理由 | 関連D-xxx |
|------|------|------|-----------|
| BL-192をBL-191から分離 | 独立したBLとして起票 | BL-191は状態機械・複数ノード間の相互作用を伴う複雑な機構面。BL-192はプロンプト文言のみの軽量な変更。ExitPlanModeの承認対象から除外し、BL-191の実装後の付随的作業として扱う | D-142（BL-188プロンプト誘導方針） |
| 共通定数方式 | `_BL192_DIRECTIVE_QUALITY_BLOCK`を1箇所に定義し両パスで参照 | 非Stage4パスの存在に気づかずStage4のみに指示を入れると、差し戻しターン等重要な場面で指示が適用されない（独立レビュー指摘7-2） | — |
| User AIへのWEB_SEARCH_TOOL追加なし | 指示による間接的なweb_search促進のみ | BL-188「プロンプト誘導のみ」方針。User AIは指示を出す側、Expert AIが実行する。Expert AIは既にWEB_SEARCH_TOOLを保持 | D-142（BL-188） |
| `_BL192_DIRECTIVE_QUALITY_BLOCK`の2つの指示の結合 | web_search義務化と思考プロセス明示を1ブロックに | 両者は「次タスクをどうするか」というStage4の本質に関する指示であり、分離すると片方を更新した時に他方も更新するのを忘れるリスク | — |
| Stage4注入位置 | `_task_focus_transition_notice`の後、「同じ検証・計算を繰り返さない」の前 | BL-191のスケジューリング指示（companion/巻き戻し）情報の後、実際の指示内容より前に配置することで、指示する前の「準備」として自然な順序 | — |

## 依存関係

- **BL-190**（前提）: `_reconcile_current_phase_after_replan` — Stage4の`current_phase`/`current_task_id`整合を保証。BL-192はこの整合状態の上で指示を出す。
- **BL-191**（同時）: `schedule_task_focus`ツール、`_build_task_focus_transition_notice` — BL-192の指令ブロックはBL-191のcompanion表示と連携（L6093: `task_focus_companion`言及）
- **BL-188**（方針）: citations/web_search基盤 — `verified_facts`のcitationsに`type="web"`フィールドが存在することを前提
- **BL-185**（構造）: `system_prompt_trailing`の配置設計 — BL-192は`system_prompt_trailing`の末尾に注入され、chat_historyの直後に配置される
- **BL-093**（思考残痕）: thinkツールの使用指示 — BL-192の②はBL-093の「検討過程を記録」方針に対する補足

## 実装ファイル

### cela_main.py

| 変更箇所 | 内容 | 行番号（実装後） |
|----------|------|-----------------|
| L6081-6095 | `_BL192_DIRECTIVE_QUALITY_BLOCK` 定数定義（新規） | :6081 |
| L8522 | Stage4 `stage4_system_prompt`へ注入 | :8522 |
| L8859 | 非Stage4 `system_prompt_trailing`へ注入 | :8859 |

### 該当しない（変更なし）

- `LineageState` — 新規フィールド不要
- `TOOL_DISPATCH` — 新規ツール登録不要（BL-184/BL-188で既に`web_search`登録済み）
- `init_db` — 新規テーブル不要
- `run_ai_vs_ai_loop`初期state — 新規フィールド不要

## テスト

### 新規テスト: `tests/test_bl192_stage4_directive_quality.py`（4件）

| テスト名 | 検証内容 |
|----------|----------|
| `test_directive_quality_block_mentions_web_search_obligation` | 定数テキストに`web_search`, `type="web"`, `もっともらしい`が含まれる |
| `test_directive_quality_block_mentions_thinking_process` | 定数テキストに`acceptance_criteria`, `思考プロセス`, `task_focus_companion`が含まれる |
| `test_generate_user_utterance_source_references_directive_block` | `generate_user_utterance`ソースコード内で`_BL192_DIRECTIVE_QUALITY_BLOCK`が参照されている（`inspect.getsource`パターン） |
| `test_directive_block_referenced_at_both_stage4_and_non_stage4_paths` | **回帰防止**: `generate_user_utterance`ソース内で`_BL192_DIRECTIVE_QUALITY_BLOCK`が**2箇所以上**参照されている（Stage4 + 非Stage4の両方） |

### 既存テスト無退行確認

- `tests/test_bl177_user_ai_staging.py` — User AI staging関連
- `tests/test_bl185_user_ai_prompt_reorder.py` — system_prompt_trailing並び順
- `tests/test_bl188_citations.py` — citations基盤
- オフライン全テストスイート825件（BL-190/191/192実装時に確認済み）

## 検証方針

1. `python -m py_compile cela_main.py`
2. `python -m pytest tests/test_bl192_stage4_directive_quality.py -v`
3. 関連既存テスト無退行: `python -m pytest tests/test_bl177_user_ai_staging.py tests/test_bl185_user_ai_prompt_reorder.py tests/test_bl188_citations.py -v`
4. フルオフラインスイート: `python -m pytest tests/ -v`

## 未決事項 / 留意事項

1. **Stage4へのWEB_SEARCH_TOOL追加**: BL-192の設計方針としてUser AIがweb_searchを直接呼ばないが、将来的にBL-191の`schedule_task_focus`と同様にStage4でweb_searchが必要なユースケースが出現した場合、Stage4の`tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL]`へ`WEB_SEARCH_TOOL`を追加する検討が必要。現時点では不要。

2. **BL-192の指示ブロックの文言微調整**: 現段階ではユーザーレビューに基づく文言確定済み。今後のドライランで「指示が冗長すぎる」や「web_search指示が伝わりにくい」等のフィードバックがあれば、共通定数の文のみの修正で対応可能（両パスに自動反映）。

3. **BL-191設計書内のBL-192セクション**: BL-191の設計書（`docs/design/back_log/BL-191/BL191_basic_design.md`）内にBL-192セクションが「予定」として記載されている。本設計書がBL-191設計書内のBL-192セクションを**正式な実装済み設計**へ更新する。両ファイルの整合性は`scripts/check_docs_consistency.py`で監査。

## 関連BL

| BL番号 | 関係 | 説明 |
|--------|------|------|
| BL-190 | 前提 | `current_phase`/`current_task_id`不整合問題への対処 |
| BL-191 | 同時実装 | Stage4駆動の過去タスク一時フォーカス切替 |
| BL-188 | 方針 | citations/web_search基盤、「プロンプト誘導のみ」方針 |
| BL-185 | 構造 | `system_prompt_trailing`の配置設計（BL-192は末尾注入） |
| BL-093 | 思考残痕 | thinkツールで検討過程を残す指示（BL-192②の基盤） |
| BL-094 | 検証指示 | read_verified_fact/read_deliverable_fileでの同期確認（BL-192①の補完） |
