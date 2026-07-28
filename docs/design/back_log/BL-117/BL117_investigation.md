# BL-117: 各ノードへのドメイン非依存な思考フレームワーク導入（Gemini提案の評価）

関連: [issue_backlog.md BL-117](../issue_backlog.md#bl-117-各ノードへのドメイン非依存な思考フレームワーク導入gemini提案の評価)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は評価時点（2026-07-28）のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## 背景

BL-114〜116（プロンプト整理のための3体のExploreエージェント調査）に続き、ユーザーがGeminiに依頼して作成した「各ノードに適したドメイン非依存の思考フレームワーク」提案表を持ち込み、評価を依頼した。BL-116（バス交通シナリオ特化例の一般化）で見つかった「具体例に頼った説明」を、名前の付いた抽象的な思考の型に置き換えることで解決しうるアプローチであり、BL-116と自然に接続する。

## Geminiの提案表（原文）

| ノード名 | 主な責務 | 推奨思考フレームワーク | フレームワーク選定の目的・思考モード |
| :--- | :--- | :--- | :--- |
| **Goal Essence Analyst**<br>`goal_essence_node` | 本質的な目的の言語化・前提の検証 | **デザイン思考**<br>＋ **5 Whys (なぜなぜ分析)** | 表層的な制約文言にとらわれず、「真に解決すべき本質的ニーズ」を深掘りし、前提の矛盾を洗い出すため。 |
| **Task Planner**<br>`call_task_planner` | 目標の構造分解・受入基準・依存定義 | **WBS (作業分解構成)**<br>＋ **MECE (漏れなく重複なく)** | 目標をフェーズとタスクへ段階的に分解し、変数所有権（owns_variables）や受入基準を体系化するため。 |
| **Task Plan Reviewer**<br>`task_plan_reviewer_node` | 実行前計画の事前監査・実行可能性チェック | **プレモータム分析 (Pre-Mortem)**<br>＋ **ボトルネック分析** | 「計画実行後に失敗した」と仮定し、実行前に潜む構造的穴・不整合・無理な仮定を批判的に検知するため。 |
| **Orchestrator**<br>`call_orchestrator` | タスクに応じた専門家の選定と観点提示 | **コンピテンシー評価**<br>＋ **コンテキスト・アサインメント** | タスクの特性を読み解き、最適なペルソナを定義した上で「そのタスク固有の着眼点（focus_guidance）」を与えるため。 |
| **Expert**<br>`call_expert` | 受入基準の達成・具体的な提案・計算 | **ReAct (Reason + Act)**<br>＋ **仮説検証サイクル** | 思考とツール実行（python_repl）を短サイクルで回し、確固たる数値的根拠を持った具体的な成果物を作るため。 |
| **Detector**<br>`call_detector` | 2段監査（ドメイン妥当性＋数値・ハルシネーション検知） | **悪魔の代弁者 (Devil's Advocate)**<br>＋ **ファクトチェック** | あえて懐疑的な立場を取り、「意図的なでっちあげ数値」や「現実世界での運用不整合」を厳格に暴くため。 |
| **Decision Extractor**<br>`call_decision_extractor` | 対話からの合意状態・確定変数の抽出 | **DST (Dialogue State Tracking)**<br>＋ **情報構造化** | 会話の自然言語から「合意ステータス（CREATE/UPDATE）」や「確定値」を誤判定なくSQLite構造データへ抽出するため。 |
| **Resource Arbiter**<br>`call_resource_arbiter` | 予算・リソース超過時の再配分裁定 | **トレードオフ分析**<br>＋ **MoSCoW分析** | 全体目標の制約内で、どのフェーズの成果を縮小し、どこへ配分すべきかの優先度（Must/Should/Could/Won't）を裁定するため。 |
| **Reflection**<br>`call_reflection` | マクロ視点での収束判定・でっちあげ・停滞監視 | **メタ認知 (Metacognition)**<br>＋ **鳥瞰（ちょうかん）思考** | 個別のやり取りから一歩引き、プロジェクト全体が目標に向かって収束しているか、堂々巡りがないかを俯瞰するため。 |
| **Facilitator**<br>`call_facilitator` | 議論が脱線・停滞した際の軌道修正 | **リフレーミング (Reframing)**<br>＋ **ORIDモデル** | 視野狭窄に陥ったAI同士に対し、問いの角度（枠組み）を変えて視座を引き上げ、本質的な議論へ連れ戻すため。 |
| **Integrator**<br>`call_integrator` | 全成果物の物理結合と横断不整合チェック | **システム思考 (Systems Thinking)**<br>＋ **クロス・インスペクション** | 結合された成果物全体をシステムとして捉え、タスク間・フェーズ間の前提条件や数値の矛盾を検知するため。 |
| **Reviewer (QA)**<br>`call_reviewer` | 最終成果物の品質判定・絶対目標適合チェック | **ゼロベース思考**<br>＋ **適合性評価 (QA検品)** | 過去のAI同士の妥協や合意を一度リセットし、「絶対目標（Goal）を完全に満たしているか」のみを冷徹に検品するため。 |
| **User AI**<br>`generate_user_utterance` | 発注者（PO）としての指示・レビュー・意思決定 | **OODAループ**<br>＋ **発注者統制思考** | Agentの提案を観察・評価（Observe/Orient）し、即座に承認・却下・軌道修正の意思決定（Decide/Act）を下すため。 |

## 評価（`cela_main.py`実装との突き合わせ）

凡例: ◎=実態とよく整合しそのまま採用可 / △=概ね妥当だが一部ギャップあり

| ノード | 評価 | 根拠 |
|---|---|---|
| Goal Essence Analyst | △ | `call_goal_essence_analyst`（cela_main.py:6358-6384）の実際の指示は2観点構成: (1) ゴール文の数値制約からのおおまかな実現可能性チェック（python_replでの概算、詳細検算はF-2.6の役目）、(2) 制約文言が本来仕えるべき「真に達成すべきこと」の言語化。Gemini提案（デザイン思考+5 Whys）は観点(2)には合うが、観点(1)（概算による実現可能性の壁打ち）をカバーする要素が提案に含まれていない。 |
| Task Planner | ◎ | `call_task_planner`（4183-4184行目docstring: "Decomposition of a high-level goal into structured, actionable phases and detailed tasks"）はフェーズ/タスク/依存関係(depends_on)/変数所有権(owns_variables)/受入基準(acceptance_criteria)への体系的分解を行っており、WBS+MECEと高い整合性。 |
| Task Plan Reviewer | ◎ | `call_task_plan_reviewer`（6518-6539行目）は実行前に4観点（曖昧表記/タスクの過不足/順序矛盾/条件明示）でレビューする実行前ゲートであり、「実行後に失敗したと仮定して事前に穴を探す」というプレモータムの精神と一致。 |
| Orchestrator | ◎ | `call_orchestrator`（4375-4377行目docstring）はタスク特性に応じた最適な専門家（ドメインエキスパート）の選定を担う。コンピテンシー評価+コンテキストアサインメントと一致。ただしBL-114（静的/動的順序バグ）はフレームワーク導入とは別問題として存在する。 |
| Expert | ◎ | `call_expert`はpython_replとの短サイクルの実行・検証を繰り返し、F-2.6機械的検算ゲートで根拠を固める設計であり、ReAct+仮説検証サイクルと高い整合性。 |
| Detector | ◎ | `call_detector`（4760-4762行目docstring）はドメイン妥当性審査と数値監査の2段構成で、安全リスク・制約遵守を評価する。悪魔の代弁者+ファクトチェックと一致。 |
| Decision Extractor | ◎ | `call_decision_extractor`（5228-5230行目docstring: "Extracting structured records of proposed decisions or evaluating user acceptance/rejection"）はCREATE/UPDATE判定・確定値抽出を担う。DST+情報構造化と高い整合性。 |
| Resource Arbiter | △ | `call_resource_arbiter`（5470-5514行目）の実際の指示は「優先度の低いフェーズの縮小」または「優先度の高いフェーズへの多め配分」という二択的な検討のみで、Must/Should/Could/Won'tの4段階分類（MoSCoW）は実装されていない。トレードオフ分析自体は良い一致だが、MoSCoWを導入するなら実質的な出力形式・判断軸の追加が必要。 |
| Reflection | ◎ | `call_reflection`（5566-5567行目docstring）はcompleted/stagnant/continuingの3値判定によるマクロな収束監査を担う。メタ認知+鳥瞰思考と一致。 |
| Facilitator | △ | `call_facilitator`（5706-5708行目docstring: "guiding prompt to help AI agents refocus discussions"）は議論の軌道修正を担うが、ORID（Objective/Reflective/Interpretive/Decisional）という具体的な4段階質問技法は実装されていない。リフレーミング自体は良い一致だが、ORIDを導入するなら実質的なプロンプト設計が必要。 |
| Integrator | ◎ | `call_integrator`（5775-5777行目docstring: "Cross-checking of merged project artifacts...to identify logical or numerical inconsistencies"）はタスク間・フェーズ間の矛盾検知を担う。システム思考+クロス・インスペクションと高い整合性。 |
| Reviewer (QA) | ◎ | `call_reviewer`（5834-5836行目docstring: "strictly enforcing adherence to defined goals"）は絶対目標適合のみを厳格に検品する。ゼロベース思考+適合性評価と一致。 |
| User AI | △ | `generate_user_utterance`は観察→評価→承認/却下/軌道修正の意思決定という流れ自体はOODAループと類似するが、「OODA」という軍事由来の意思決定サイクル名をそのままモデルへ提示することの実益は疑問。「発注者統制思考」というより実務的なラベルの方が効きそうという所感。 |

## 全体所感

1. **ラベル貼りのリスク**: フレームワーク名（「WBS」「ReAct」等）を書くだけでは効果が薄い。各フレームワークが「具体的にどう考えるか」の手順・チェックリストまで落とし込む必要がある。
2. **冗長化との衝突**: BL-116で「冗長な指示文」を問題視したばかりなので、1ノードにつき主軸フレームワーク1つ＋補助1つ程度に抑え、説明も簡潔にすべき。
3. △評価の4ノード（Goal Essence Analyst / Resource Arbiter / Facilitator / User AI）は名前を採用するだけでなく実質的な構造（出力形式・判断軸）の変更が伴うため、他の◎評価ノードより手間がかかる。
4. 全体としてGeminiの提案は各ノードの実際の役割とよく整合しており、BL-116（バス特化例の一般化）の受け皿として活用する価値がある。

## ユーザー判断

AskUserQuestionで確認した結果、「評価のみで一旦区切り、実装は別途スコープを決めてから着手する」を選択。本ファイルはその評価結果の記録であり、コード変更は行っていない。
