# 先行研究・関連事例とCELAの独自性

CELAの技術ブログ執筆に向けて、関連する先行研究・実装事例と、それに対する
CELA自身の立ち位置（何が既知のパターンの適用で、何が具体的に独自と言えるか）を
正直に整理したメモ。`docs/blog_topics.md`の各お題を書く際、先行研究への
言及・引用のベースとして使う。

**方針:** ここに挙げる論文・URLはすべてWebSearchで実在を確認済み（タイトル・著者・
arXiv ID等）。生成AIの知識だけに頼った未検証の引用は含めない（AGENTS.md §9「未検証の
一次情報を断定しない」方針に準拠）。ただし各論文の詳細な主張の要約は検索結果の要約に
基づくものであり、精読して確認したものではない点に留意。

---

## 1. 先行研究・関連事例

### 1.1 マルチエージェント協調・役割分担型フレームワーク

CELAの「Task Planner→Orchestrator→Expert→User AI→Detector→Reflection」という
役割分担・グラフ構造は、以下の既存フレームワークと同系統のパターンである。

- **MetaGPT** (Hong et al., 2023, arXiv:2308.00352, ICLR 2024採択)
  プロダクトマネージャー・アーキテクト・エンジニア・QA等の役割を持つエージェントが、
  標準化されたドキュメント（SOP: Standard Operating Procedures）を介して協調し
  ソフトウェア成果物を生成するフレームワーク。「役割ごとに専門化したエージェントが
  構造化された中間成果物を介して協調する」という設計思想がCELAと極めて近い。
  https://arxiv.org/abs/2308.00352

- **AutoGen** (Wu et al., 2023, Microsoft Research, arXiv:2308.08155)
  複数のconversableなエージェント（LLM・人間・ツールの組み合わせ）が対話を通じて
  タスクを遂行するフレームワーク。GroupChatパターンにおける「critic」役はCELAの
  Detectorに近い。
  https://arxiv.org/abs/2308.08155

- **LangGraph（本プロジェクトの実装基盤）**
  公式ドキュメント・チュートリアルに"reflection agent"・"corrective RAG"等、
  生成→批評→再生成のループパターンが例として提供されている。CELAはこのループを
  「User AI⇔Expert AI⇔Detector⇔Reflection」という交渉ドメイン向けに具体化したもの。

### 1.2 内省・振り返り（Reflection）による自己改善

- **Reflexion** (Shinn et al., 2023, NeurIPS 2023, arXiv:2303.11366)
  タスク失敗時のフィードバックを言語的に内省し、エピソード記憶に蓄積することで
  次の試行の意思決定を改善するフレームワーク。CELAの`reflection_node`（周期的に
  議論全体を俯瞰し`stagnant`/`completed`/`continuing`を判定する仕組み）は、
  この「内省を明示的なノードとして挟む」という発想と重なる。ただしReflexionは
  「同じタスクの再試行間での学習」が主眼であり、CELAの用途（進行中の交渉の
  ゴール逸脱検出）とは適用対象がやや異なる。
  https://arxiv.org/abs/2303.11366

### 1.3 長期記憶・意味的事実の抽出

- **Generative Agents: Interactive Simulacra of Human Behavior**
  (Park et al., 2023, UIST'23, arXiv:2304.03442)
  生成AIエージェントが観察（observation）を記憶ストリームに蓄積し、定期的に
  高次の内省（reflection）へ要約し、後の意思決定で検索・参照するアーキテクチャ。
  CELAの`agreements`/`decisions`/`verified_facts`DBは、この「生ログではなく
  意味的な事実として抽出・構造化する」という発想の、交渉・合意形成ドメインに
  特化した具体化と位置づけられる。
  https://arxiv.org/abs/2304.03442

- **MemGPT: Towards LLMs as Operating Systems**
  (Packer et al., 2023, arXiv:2310.08560)
  OSの階層的メモリ管理に着想を得て、LLMの限られたコンテキスト窓の外側に
  仮想的なメモリ階層（コンテキストの出し入れ）を持たせる設計。CELAの
  「毎回ステートレスに呼び出し、DBから文脈を再構成する」設計とは目的は近いが
  実装アプローチ（仮想メモリ管理 vs 構造化DBからの都度クエリ）は異なる。
  https://arxiv.org/abs/2310.08560

### 1.4 ツール使用・推論と行動の統合

- **ReAct: Synergizing Reasoning and Acting in Language Models**
  (Yao et al., 2022, arXiv:2210.03629)
  推論トレースと行動（外部ツール・APIの呼び出し）を交互に生成させることで
  ハルシネーションを抑える手法。CELAのpython_replツールループ（F-2.6検算ゲート）
  はこのReAct的パターンの具体的な適用例。
  https://arxiv.org/abs/2210.03629

- **Self-Consistency Improves Chain of Thought Reasoning**
  (Wang et al., 2022, arXiv:2203.11171)
  複数の推論パスをサンプリングし多数決で最終回答を選ぶ手法。Detectorの
  「3回多数決方式」（constraint_issue判定をブレさせず3回試行して多数決を取る）は
  この発想の簡易版と位置づけられる。
  https://arxiv.org/abs/2203.11171

### 1.5 討論・審査によるAIの検証

- **AI Safety via Debate** (Irving, Christiano, Amodei, 2018, arXiv:1805.00899)
  2つのAIが対立する主張を持って討論し、人間（あるいは別のAI）の審判がどちらが
  正しいかを判定するという、AIの出力を検証可能にするための枠組み。CELAの
  User AI⇔Expert AI⇔Detectorという「主張・反論・審査」の三者構造は、この
  討論による検証という発想と重なる部分がある。
  https://arxiv.org/abs/1805.00899

### 1.6 人間向けの意思決定記録の慣習

- **Architecture Decision Records (ADR)**
  (Michael Nygard, "Documenting Architecture Decisions", 2011-11-15,
  Cognitect blog。原型は同氏の著書『Release It!』2007年版に遡る)
  ソフトウェアのアーキテクチャ決定を「決定内容」だけでなく「背景・理由」込みで
  短いドキュメントとして残す実務慣行。CELA自身の開発プロセス（本プロジェクトの
  `decision_log.md`/`decision_lineage.md`）が明確にこの慣行を踏襲しており、
  さらにそれをAI同士のシミュレーテッド交渉（`decision_extractor`による
  `agreements`テーブルへの理由付き記録）にも入れ子で適用している点がCELA固有。
  https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions

---

## 2. CELAの独自性（具体的に主張できる点）

上記の先行研究と比べたとき、CELAが「新しいアーキテクチャの発明」と主張できる部分は
薄い。一方で、以下は先行研究の単純な適用に留まらない、具体的で検証可能な独自性・
知見だと言える。

### 2.1 監査パスの「軸の分離」だけでなく「実行順序」自体が結果を左右するという発見
F-2.6検算ゲート導入によるトンネルビジョン問題（数値の正誤にすべての注意が
引き寄せられ非数値的懸念が見落とされる）を、Detectorの「数値監査パス」と
「ドメイン妥当性レビューパス」への分離で解消した（BL-049）。ここまでは
Self-Consistency的な「複数の評価軸を独立させる」発想の応用に留まるが、
CELAはさらに踏み込み、「検算を先に行うと『数値は合っている』という結果に
評価者の注意が引きずられ、ドメイン評価が後手に回る」ことを実ドライランで
観測し、実行順序をドメイン監査→数値検算へ逆転させた（BL-054）。
「評価軸の独立性」だけでなく「評価の順序が結果を左右する」という点まで
具体的に検証した事例は、先行研究では明示的に見当たらない。

### 2.2 「真の制約」と「見直し可能な条件」を明示的に区別させるプロンプト設計
ゴール記述に「動かせない制約」と「議論の前提として与えられた例示的な条件」が
区別なく混在していたため、AIがどちらも同様に「動かせないもの」として扱い、
思考が硬直する現象を観測した（BL-055）。「制約と条件を都度見極めよ」という
一般化した指示を与えたところ、AIが自発的に前提（車両の調達方法等）を疑い、
代替案を検討し始める変化が実際に確認できた。この「ゴール記述の曖昧さが
AIの思考をどう歪めるか」という具体的な観察と、その修正が実際に機能したという
実証は、一般的な「プロンプトは明確に書け」という助言より一段具体的な知見である。

### 2.3 人間向けの意思決定記録規律を、AI同士の対話に入れ子で適用したこと
ADRのような「Whyを残す」規律は通常、人間（開発チーム）向けの実務慣行である。
CELAはこの規律を、開発プロセス自体（`decision_log.md`/`decision_lineage.md`）
だけでなく、シミュレーテッドされたAI同士の交渉（`decision_extractor`が
User AI/Expert AIの発言から決定と理由を抽出し、`Proposed→Approved/Rejected/
Superseded`という状態遷移込みで構造化するagreements DB）にも再帰的に適用している。
Generative Agentsのmemory streamより一段厳格な、状態遷移込みのスキーマを
交渉ドメインに特化して設計した点は具体的な差分と言える。ただし「抽出された
理由の質そのものを監査する」機構（BL-050）はまだ実装できておらず、この点は
現時点でCELAの実装が理論に追いついていない箇所として正直に書くべきである。

### 2.4 ホワイトボード差分パッチ方式（Claude Code自身の編集方式の転用）
LLM同士の成果物更新において、行番号やunified diff形式をモデルに要求せず、
`old_text`の完全一致検索→`new_text`置換という、Claude Code自身のファイル編集
ツールと同じ方式を採用した（R4設計、論点43）。この着想は「LLMエージェント開発
ツール自身が採用している手法を、LLM間の成果物更新にそのまま転用する」という
具体的で再現可能な工学的判断であり、先行研究に同型の記述は見当たらない
（ただしdiff形式でのpatch適用自体はソフトウェア工学一般では既知の手法であり、
「LLMへの提示方法として何が信頼性が高いか」という一点に絞った工夫である）。

### 2.5 意図的に「解けない制約」を与えた実験デザイン
構想初期にGeminiとの壁打ちで発案された「あえて無理な制約を与えてAIがどう
格闘するか観察する」という実験デザイン自体は、既存研究の技術的新規性という
より観察手法・実験デザインとしての価値である。「制約が数学的に両立しない」
という状況下で、AIが「でっちあげて帳尻を合わせる」段階から「矛盾を認めて
前提の見直しを提案する」段階へ、監査機構の強化と共にどう変化したかを実際の
ログで追跡できたことは、上記2.1・2.2の知見を生み出す土台になった。

---

## 3. 正直な位置づけ（まとめ）

- **システムアーキテクチャとしての新規性は低い。** Planner/Executor/Critic/
  Reflectorという多エージェント協調ループ、DBによる長期記憶、ツール使用ループは
  いずれも既存研究・既存フレームワーク（MetaGPT/AutoGen/LangGraph/Generative
  Agents/Reflexion/ReAct）に類例がある。
- **一部は既存機能の再実装（車輪の再発明）である。** 一時停止・再開のための
  独自JSON checkpoint実装は、LangGraph自身が提供する`checkpointer`
  （`SqliteSaver`等、スレッド単位のグラフ状態永続化）で代替できた可能性が高い。
  https://docs.langchain.com/oss/python/langgraph/persistence
- **具体的で再現可能な価値は、プロンプト設計・運用上の知見と、実クラッシュ・
  実ログに基づく検証済みの観察にある。** 「検算とドメイン監査の実行順序」
  「制約と条件の区別」「AI同士の対話への意思決定記録規律の入れ子適用」
  「ホワイトボード差分パッチの発想源」は、いずれも一般論の域を出て具体的な
  実験・実装・観察に裏付けられている。
- ブログとして書く際は、**「新しいアーキテクチャの提案」ではなく「既知のパターンを
  本気で長時間・無理な制約で運用した結果、何が壊れ、何を学んだかの実録」**
  という誠実な切り口を取るのが妥当。

---

## 参照リンク一覧

- Generative Agents: https://arxiv.org/abs/2304.03442
- MetaGPT: https://arxiv.org/abs/2308.00352
- AutoGen: https://arxiv.org/abs/2308.08155
- Reflexion: https://arxiv.org/abs/2303.11366
- AI Safety via Debate: https://arxiv.org/abs/1805.00899
- ReAct: https://arxiv.org/abs/2210.03629
- Self-Consistency: https://arxiv.org/abs/2203.11171
- MemGPT: https://arxiv.org/abs/2310.08560
- Architecture Decision Records (Nygard, 2011): https://cognitect.com/blog/2011/11/15/documenting-architecture-decisions
- LangGraph Persistence（checkpointer）: https://docs.langchain.com/oss/python/langgraph/persistence
