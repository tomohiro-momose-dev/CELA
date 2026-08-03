# CELAアーキテクチャレビュー — 足りないもの・過剰なもの・情報の外部化

> **実施日**: 2026-08-03
> **実施者**: Cline (deepseek/deepseek-v4-flash)
> **目的**: バグチェック結果を踏まえ、CELAを一から設計する場合の視点で、不足・過剰・情報配置の最適化を提案する

---

## 1. 足りないもの（追加すべきノード・機能）

### 1.1 コンテキスト要約ノード（Context Summarizer Node）

**現状の問題**: `chat_history_window`（既定4）による固定窓のみで、それ以前のターンは単純に切り捨てられる。BL-068で指摘されたHydrate 3段グラデーション（直近Nターン生ログ＋それ以降を定期要約で積み上げる）が未実装のまま放置されている。`call_expert`には「5ターン毎に議論のサマリーを出力せよ」という指示が残っているが、この出力を捕捉・蓄積する実装が存在しない。

**提案**: `round_count`がNの倍数（例: 5）ごとに発火する`context_summarizer_node`を新設:
- 直近Nラウンドの`chat_history`を要約し、`state["conversation_summary"]`へ蓄積
- `call_expert`/`generate_user_utterance`のプロンプト構築時に、`chat_history_window`外のターンは生ログではなく`conversation_summary`で置き換え
- トークン消費をO(1)に抑えつつ、長期記憶を維持

**効果**: 長時間ドライランでのコンテキスト消失を防ぎ、後半フェーズで前半の決定事項を忘れる問題（BL-036の数値ドリフト等）を構造的に防止。

### 1.2 品質ゲートノード（Quality Gate Node）

**現状の問題**: フェーズ完了が暗黙的（`decision_extractor_node`の`_resolve_task_transition`によるtask遷移のみ）。BL-051/077で指摘された「issueリストの全項目closeをフェーズ完了条件にする」機構が未実装。BL-134で、escalated issueが未解決のまま次タスクへ進行してしまった実例がある。

**提案**: フェーズ最後のタスク完了時に発火する`quality_gate_node`を新設:
- 対象フェーズの全タスクの`acceptance_criteria`が`true`であることを確認
- 対象フェーズに関連する`issue_log`の`status='escalated'`行が0件であることを確認（または全て`defer_to_task_id`設定済み）
- 上記を満たさない場合はフェーズ完了を拒否し、残課題を`state["phase_blocker"]`へ記録
- 次のUser AIターンで「以下の課題が未解決のためフェーズを完了できません」と明示

**効果**: BL-125（タスク遷移ゲート）をフェーズ単位に拡張し、フェーズ横断的な品質保証を実現。

### 1.3 外部情報取り込みノード（External Information Ingestion Node）

**現状の問題**: CELAはゴール文と自身が生成した知識のみで運用され、外部情報（Web検索・文書読み込み・API呼び出し）を取り込む経路が存在しない。Expertが「車両単価2,500万円」のような例示的条件を疑えない（BL-055）一因は、市場価格等の外部参照値にアクセスできないため。

**提案**: `tools`に`web_search`/`read_url`を追加（将来的な拡張）:
- Expert/User AIが外部情報を参照して前提を検証できる
- Detectorが「この数値は現実的か」を外部データで裏付けられる
- ただし、サンドボックス制限（BL-007/058）と同じセキュリティ考量が必要

**注意**: これはMVP後の拡張候補であり、現状のサンドボックス設計との整合性を要する。

---

## 2. 過剰なもの（削除・統合すべきノード・機能）

### 2.1 Detectorの2パス構成の簡素化検討

**現状**: `call_detector`（493行）は「ドメイン妥当性レビュー」（第1段）＋「数値監査」（第2段）の2パス構成。BL-049/054で導入。各パスが独立したLLM呼び出しを行うため、DetectorのAPI呼び出しコストが実質2倍。

**検討事項**:
- 第1段（ドメイン妥当性）の指摘の多くが、第2段（数値監査）でも捕捉しうる
- ただしBL-054で「ドメイン先行」の効果が実証されているため、単純な統合は品質低下のリスクあり
- **提案**: 2パスを維持しつつ、第1段の結果を第2段に注入する現行設計を維持するが、`call_detector`関数自体を2つのサブ関数（`_build_domain_review_prompt`/`_build_numerical_audit_prompt`）に分割して可読性を向上させる（BL-150のリファクタリング候補）

### 2.2 複数のエスカレーション経路の統合検討

**現状**: 以下5つの経路が「懸念を上げる」という目的で重複:
1. `escalate_premise_concern`（BL-086）— 前提矛盾の提起
2. `write_issue`（BL-096）— 軽微な懸念の記録
3. `freeze_agreement`（R5）— 恒久ピン留め
4. `revise_goal`（BL-086）— ゴール改定
5. `ask_user_question`（BL-130）— Expert→User相談

**検討事項**:
- これらは目的が微妙に異なるため、完全な統合は困難
- しかし、AIモデルから見ると「どの経路を使うべきか」の判断が曖昧（BL-124で実証: どれも使われなかった）
- **提案**: `escalate_premise_concern`と`write_issue`の使い分けをプロンプトでより明確に指示。`freeze_agreement`は`revise_goal`のオプション機能に統合（単独使用の実例がほぼないため）

### 2.3 冗長な状態カウンタの統合

**現状**: 以下のカウンタが個別に管理されている:
- `turn_count`（BL-005、凍結、実質dead）
- `round_count`（BL-048、turn_countの代替）
- `facilitation_count`（halt用）
- `expert_retry_count` / `user_retry_count`（ルーティング用）
- `plan_reviewer_retry_count`（計画レビュー用）

**提案**: `turn_count`を廃止し（BL-005の根本修正）、`round_count`を唯一の進行カウンタとして使用。各種retry_countは`round_count`からの相対値として計算可能な場合が多い。

### 2.4 死んだスキーマの削除

以下はBL-065/067/068で「書き込まれるが読まれない」と判明済み。消費経路を設けるか削除するかの判断が必要:

| 要素 | 提案 |
|------|------|
| `chat_history`テーブル | 削除（インメモリ+LangGraph checkpointerで完結） |
| `current_goal`テーブル | 削除（`state["goal"]`で完結） |
| `current_task_summary` | 削除（BL-068で未実装と判明） |
| `internal_thought_process`列 | 消費経路を設ける（例: 次回同種判定時の参照材料）または削除 |
| `goal_shift_events`テーブル | 消費経路を設ける（例: Hydrateコンテキストへの表示）または削除 |
| `whiteboard_drafts.author_role`/`edit_summary` | `get_latest_whiteboard`で読み出すよう修正（BL-066） |

---

## 3. 情報の外部化・配置最適化

### 3.1 Goal Essence Textのキャッシュ化

**現状**: `_get_goal_essence_text`（fan_in=11）が11箇所から毎ターン呼ばれ、毎回DBクエリを実行。テキストは`goal_essence_node`実行後は不変（`revise_goal`成功時のみ変化）。

**提案**: `goal_essence_node`の実行結果を`state["goal_essence_text"]`へキャッシュし、11消費者はstateから読む。`revise_goal`成功時にキャッシュを無効化。DBクエリを11回/ターンから0回/ターンに削減。

### 3.2 Agreements Contextのページネーション

**現状**: `_build_agreements_context_from_db`が全agreementsを毎ターン読み込む。対話が進むほど件数が増加し、プロンプトサイズが肥大化。

**提案**: 直近N件（例: 15件）のagreementsを生で表示し、それ以前は「過去の決定事項（N件）: [topic一覧]」という要約形式に圧縮。要約は`context_summarizer_node`（1.1の提案）が生成・管理。

### 3.3 ツール説明文の外部化

**現状**: 15個のツールスキーマ（`*_TOOL`辞書）の`description`がPython辞書リテラルとして`cela_main.py`に埋め込まれている。BL-113/115で説明文の修正が頻発し、そのたびにPythonコードを編集している。

**提案**: ツール説明文をYAML/JSONファイル（例: `config/tool_descriptions.yaml`）に外部化し、`cela_main.py`は起動時に読み込む。これにより:
- プロンプトエンジニアリングとコードロジックの分離
- 非開発者によるプロンプト調整が可能
- ファイルサイズの削減（BL-098/118のファイル分割の前提）

### 3.4 プロンプトテンプレートの外部化

**現状**: 各`call_*`関数内でプロンプトがPython f-string/文字列結合で構築されている。BL-104/115/116でプロンプトの並び替え・重複統合・ドメイン特化例の一般化を行うたびに、Pythonコードを直接編集している。

**提案**: プロンプトテンプレートをJinja2等のテンプレートエンジンで外部化（例: `templates/expert_prompt.j2`）。動的変数（`goal`/`agreements_text`/`current_task_json`等）はテンプレート変数として注入。これにより:
- プロンプトの構造変更がコード変更不要
- プロンプトの差分管理が容易
- BL-104の「静的先頭・動的末尾」原則がテンプレート構造として明示的

### 3.5 User AI/task_plan_reviewerへのphases_json全文注入の見直し

**現状**: BL-104で`call_expert`は`phases_json`全文（13,000+文字）をToC＋`read_project_plan`ツールに置き換えたが、`generate_user_utterance`（User AI）と`call_task_plan_reviewer`は全体像の把握が本質的に必要として`phases_json`全文を維持している。

**検討事項**:
- User AIは全体像を把握すべきだが、毎ターン13,000文字を送る必要があるか。`read_project_plan`ツールで能動的に取得する方式ではだめか。
- task_plan_reviewerは計画レビューが役割なので全文は必要だが、差分のみでレビューできる場合はdiffツール（BL-092）で代替可能。

**提案**: User AIも`call_expert`と同様にToC＋`read_project_plan`ツール方式に移行し、`phases_json`全文の常時注入を廃止。ただし、User AIの役割上、全体像を頻繁に参照する可能性が高いため、プロンプトで「iter=1で必ず`read_project_plan`を呼んで全体像を把握すること」を指示。

---

## 4. 各ノードへの情報表示の最適化

### 4.1 不要・過剰な情報の削減

| ノード | 現在の過剰な情報 | 提案 |
|--------|-----------------|------|
| `call_expert` (light_system_prompt) | `current_task_json`/`verified_facts_json`/`remaining_criteria_text`/`whiteboard_text`/`deferred_notes_text`の全てを維持 | iter=2以降は`whiteboard_text`と直近のDetector指摘のみに絞る（他はiter=1で把握済み） |
| `call_reflection` | 全decisionsのタイムライン（無制限） | 直近N件＋古い分は要約（1.1のContext Summarizerが生成） |
| `call_detector` (write_agreement_status_block) | success=True時も「success=1, 正常」と表示 | success=True時はブロック自体を省略（トークン節約） |
| `generate_user_utterance` | `phases_json`全文（13,000+文字） | ToC＋`read_project_plan`ツールに置き換え（3.5の提案） |

### 4.2 不足している情報の追加

| ノード | 不足している情報 | 提案 |
|--------|-----------------|------|
| `call_detector` | escalated issueの一覧（BL-123） | `_build_escalation_pin_text`を注入（**1行追加**） |
| `call_detector` | open（minor）issueの一覧 | `_build_open_issue_pin_text`を注入（BL-136でExpert/User AIには注入済み、Detectorには未注入） |
| `call_expert` | 差し戻し回数・前回との類似度（BL-143で追加済み） | ✅ 対応済み |
| `generate_user_utterance` | Expertの`blocking_reason`（BL-135） | `state["expert_blocking_reason"]`を追加して埋め込み |
| 全ノード | 「確定値」と「推定値」のラベル（BL-097） | プロンプトで出所ラベルの強制を指示（未実装） |

### 4.3 情報の鮮度管理

**現状の問題**: すべてのコンテキストが毎ターン「最新」をDBから再取得する設計だが、一部の情報はターン内で不変であり、再取得は無駄。

**提案**: 情報の鮮度に応じた3層管理:
1. **不変（run内で変わらない）**: `goal`/`goal_essence_text`/`phases`（`plan_revision_reason`時以外）→ `state`にキャッシュ、DBクエリ不要
2. **ターン内で変わる**: `current_task_id`/`agreements`/`whiteboard` → 毎ターンDBから取得（現状通り）
3. **ターン内で複数回変わる**: `chat_history`/`constraint_issue_log` → `state`のインメモリで管理（現状通り）

---

## 5. ノード追加・削除のサマリー

### 追加すべきノード

| ノード | 発火タイミング | 役割 | 対応BL |
|--------|---------------|------|--------|
| `context_summarizer_node` | `round_count % 5 == 0` | 古いchat_historyの要約蓄積 | BL-068 |
| `quality_gate_node` | フェーズ最後のタスク完了時 | acceptance_criteria + issue解決の確認 | BL-051/077/134 |

### 統合・削除すべきノード

| ノード | 提案 | 理由 |
|--------|------|------|
| `halt_node` | 外側ループのフラグチェックに置き換え | BL-121でhaltが機能しない問題、専用ノードの必要性が低い |
| `arbiter_node` | `reflection_node`へ統合検討 | 両者とも「メタレベル監視」が役割、発火条件の設計が未完了（BL-041） |

### 維持すべきノード（変更不要）

| ノード | 理由 |
|--------|------|
| `goal_essence_node` | プロジェクト開始時の本質分析、BL-087 Stage3で実装済み |
| `task_planner_node` | 計画分解、BL-087/126で拡張済み |
| `task_plan_reviewer_node` | 計画レビュー、BL-087 Stage2で実装済み |
| `generate_user_utterance_node` | User AI、中核ノード |
| `orchestrator_node` | 専門家選定、BL-148でツールループ化済み |
| `expert_node` | Expert実行、中核ノード |
| `detector_node` | 監査、BL-049/054で2パス化済み |
| `decision_extractor_node` | 決定抽出、BL-139でフォールバック追加済み |
| `reflection_node` | 周期監査、BL-048/144で改善済み |
| `facilitator_node` | 調停、BL-126 Stage Dでツールループ化済み |
| `integrator_node` | フェーズ横断統合、BL-035/036で課題指摘済みだが役割自体は必要 |
| `reviewer_node` | 最終レビュー、役割明確 |

---

## 6. 優先順位

### 即効性（1行〜数行修正）

1. **BL-123**: `call_detector`に`_build_escalation_pin_text`を注入 — 1行追加
2. **BL-135**: `expert_blocking_reason`を`generate_user_utterance`に埋め込み — 数行追加

### 短期（プロンプト修正レベル）

3. **BL-149**: `_safe_json_parse`のフォールバック戦略ロギング追加
4. **3.1**: Goal Essence Textのキャッシュ化（`state["goal_essence_text"]`）
5. **4.1**: `write_agreement_status_block`のsuccess=True時省略
6. **4.1**: `call_reflection`のタイムライン窓付き化

### 中期（新規ノード・構造変更）

7. **1.1**: `context_summarizer_node`新設（BL-068の解決）
8. **1.2**: `quality_gate_node`新設（BL-051/077の解決）
9. **2.3**: `turn_count`廃止、`round_count`へ一本化（BL-005の根本修正）
10. **2.4**: 死んだスキーマの削除（BL-065/067/068の解決）

### 長期（アーキテクチャ再構成）

11. **3.3/3.4**: ツール説明文・プロンプトテンプレートの外部化
12. **BL-098/118**: ファイル分割（BL-150のリファクタリングを先行）
13. **1.3**: 外部情報取り込みノード（MVP後の拡張）