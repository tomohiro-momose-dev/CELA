# BL-264/BL-265 調査記録：LLM出力フォールバックのセンチネル化と、read-before-write機械的ゲートの設計検討

| 項目 | 内容 |
|------|------|
| 作成日 | 2026-08-24 |
| 対象コミット | `86522f9`（調査開始時点のHEAD。本調査自体はコード変更を行っていない） |
| 調査者 | Claude（Explore×2並列監査、Plan×1設計、および最終確認・Category C追加調査） |
| 依頼者の指示 | 「BLを作成し、調査開始」（設計相談セッションの結論として）。本ドキュメントは AGENTS.md §4-7 の規約に従い、BL-264・BL-265という2つのBL番号にまたがる調査・設計内容を要約せず全文保存する。両BLエントリから本ドキュメントへ、本ドキュメントから両BLエントリへ相互にクロスリンクする。 |

---

## §1 監査の動機

ユーザーとの設計相談セッションの中で、2つの独立した——しかし根は同じ「LLM出力／エージェント挙動をどこまで信頼するか」という問いに行き着く——論点が提起された。

**論点1（read-before-write）**：`write_agreement`（`whiteboard_drafts`の編集）や`revise_goal`（`goal_drafts`の編集）が使う`edits`（old_text/new_text方式の部分パッチ）は、これまでBL-080・BL-193・BL-211・BL-212・BL-261と繰り返し「LLMが既存テキストと完全一致させられず、結局全文置換にフォールバックして中身が消える／孤児化する／矛盾を残す」という同じ壊れ方をしてきた。ユーザーはこの議論の中で、Claude Code自身のEditツールが「対象ファイルをReadしていなければEditを拒否する」という機械的な制約を持っていることに言及し、同じ発想をCELAの編集系ツールにも適用できないか、と提起した。

**論点2（空文字の二重の意味）**：AGENTS.md §13はLLM出力の空文字ドリフト（BL-206/210/211/212）を根絶するための恒久ルールだが、`""`という値そのものは、このプロジェクトのコード中で「意図された正当な既定値」（例: `call_task_planner`の`revision_reason: str = ""`、「今回はラン途中の再構成ではない」という設計上の状態）としても広く使われている。ユーザーは「フォールバックである空文字と、正当な既定値としての空文字を、何か特殊な文字で区別できないか」と提起した。

依頼は「BLを作成し、調査開始」であり、以下の体制で調査を進めた。

1. 2本のExploreエージェントを並列起動——(A)「LLM出力を消費する箇所の`.get(key, default)`型フォールバックの棚卸し」、(B)「`whiteboard_drafts`/`plan_drafts`編集系ツールのread強制状況の棚卸し」。
2. 両監査の結果を受け、Planエージェントに設計を委任。Planエージェントは**着手前にコードへ立ち返って各発見を再検証**し、その過程で当初「最有力」とされていた発見の一部が既に別のBLで対応済みであることを発見した（§2.1参照）。
3. Plan結果をユーザーに提示し、BL番号の割り振り（単一BL vs 分割）についてAskUserQuestionで確認、「BL-264とBL-265に分割」を選択（性質の異なる2つの改修——データ整合性の話と制御フローの話——を1つのBLに束ねると、後者の論争解決を待って前者まで足止めされるため）。
4. プラン承認後、ユーザーがIDE選択（`cela_main.py:14728 state.get("current_phase", {})`）を通じて**非文字列型（dict/list）の空値フォールバック**という第3の論点を追加提起。これを「Category C」として調査に組み込んだ（§6）。

本ドキュメントはこの一連の調査・設計を全文保存する。**本ドキュメント作成時点でコード変更は一切行っていない**——`cela_main.py`等ソースファイルは今回のセッションで未変更であり、以下の「対応（提案）」はすべて設計提案であって実装済みの記述ではない。

---

## §2 監査手法

### §2.1 発見事項の到達可能性の再検証（追加した方法論ステップ）

当初の監査手法は、(A)「`.get(key, default)`パターンをLLM出力消費箇所からgrepし、下流の消費者を辿る」、(B)「`TOOL_DISPATCH`／編集系ハンドラの呼び出し連鎖をgrepし、readツールとの機械的な連携有無を確認する」の2本立てだった。

しかし監査(A)の結果をPlanエージェントが実装設計へ落とし込む段階で、コードへ立ち返って検証したところ、**当初「最も確信度が高い」と評価されていた発見の一部が、実は既に他のBLで対応済みであった**ことが判明した。具体的には、`decision_extractor_node`（cela_main.py:14949-14951）の`action_type`/`entry_type`/`status`フォールバックと、`_commit_agreement_from_tool`（cela_main.py:3404-3405, 3627）の同型フォールバックである（詳細は§5.1）。

これは、grepによる表面的なパターン一致だけでは「その値が実際にコンシューマへ到達するかどうか」までは分からないという、AGENTS.md §14.1「表面一致は診断ではない」の直接的な実演だった。そのため、監査手法に**第3のステップ**を追加した。

> **§2.1 到達可能性の再検証**：`.get(key, default)`のヒット1件ごとに、そのdictを生成した呼び出し元まで遡り、「この行に到達する時点で、値は既に上流で検証済みか」を確認する。検証済みであれば、そのフォールバックは「到達不能な防御的コード」であり、修正の優先度は低い（あるいは不要）。未検証であれば、そのフォールバックが実際の脆弱性である。

この訂正自体を含めて記録することが、本調査の誠実性にとって重要である——AGENTS.md §16.3「言えないことは言えないと言う」の精神に基づき、「当初の分析が誤っていた」ことを隠さず明記する。

### §2.2 grepパターン

- 監査(A): `\.get\(["\'][a-z_]+["\'],\s*["\']`、`or ""`、`or default`、`except.*JSONDecodeError`、`except Exception`、および`args.get(`／`tool_call`／`_commit_agreement_from_tool`／`_write_agreement_impl`との突き合わせ。
- 監査(B): `@tool`／`TOOL_DISPATCH`／`_apply_text_edits`／`apply_plan_patch`／`_commit_agreement_from_tool`／`write_agreement`／`apply_whiteboard_patch`の呼び出し連鎖、および読み取り側ツール（`get_latest_whiteboard`／`get_latest_plan_draft`／`read_deliverable_file`／`read_verified_fact`）の状態追跡有無。
- Category C（§6、後日追加）: `state\.get\("current_phase",\s*\{\}\)`および類似の非文字列型フォールバックパターン。

---

## §3 read-before-write：現状の欠落（BL-265のエビデンス）

### §3.1 編集系ツールの棚卸し

`whiteboard_drafts`／`plan_drafts`／`goal_drafts`という3つの版管理ストアのうち、**LLM向けの編集ツール（old_text/new_text方式のedits）を実際に持つのは`whiteboard_drafts`と`goal_drafts`の2つだけ**である。

| ツール | 対象ストア | schema定義 | handler連鎖 |
|---|---|---|---|
| `write_agreement`（`edits`パラメータ） | `whiteboard_drafts` | cela_main.py:2502-2529 | `_write_agreement_impl`(3666) → `_commit_agreement_from_tool`(3379) → edits分岐(3494-3526) → `_apply_text_edits`(7723) → `apply_whiteboard_patch`(7170) → `INSERT INTO whiteboard_drafts` |
| `revise_goal`（`edits`パラメータ） | `goal_drafts` | cela_main.py:2689-2700 | `_revise_goal_tool_impl`(2958) → `_apply_text_edits`(3005) → `apply_goal_patch`(2755) |
| （存在しない） | `plan_drafts` | — | `apply_plan_patch`(7241)は内部/システム起因の3経路（`_append_deferred_note_to_plan`、`_append_reviewer_comment_to_plan`、task_planner_nodeの全文スケルトン再生成）からのみ呼ばれ、LLM供給のold_text/new_textでは一切呼ばれない |

`plan_drafts`にLLM向け編集ツールが存在しないという事実は、当初の設計相談時点の前提（「フェーズ・タスク表ホワイトボード」も同型の脆弱性を持つはず、という会話上の推定）を訂正する。読み書きは`read_plan_draft`（読み取り専用、schema 1512）で完結しており、書き込みはPython側の全文再生成が担っている。

### §3.2 read-enforcement の現状：機械的なものは一切ない

`write_agreement`・`revise_goal`いずれの`edits`分岐にも、**「対応する読み取りツールが同一ターン内で呼ばれたか」を確認するコードは存在しない**。唯一の抑止力は、ツールのdescription文中のプローズ（cela_main.py:2511-2512：「必ず先にread_whiteboard_excerptを呼べ、old_textを記憶から再構成するな」）だけであり、AGENTS.md §15.3「プロンプトの注意喚起より機械的検証を優先せよ」に反する設計になっている。

`apply_whiteboard_patch`／`get_latest_whiteboard`のいずれも、書き込み内容・読み取り内容が非空であることをアサートしない。

### §3.3 読み取り側ツールの一覧

| ツール | schema | handler |
|---|---|---|
| `read_deliverable_file` | cela_main.py:687 | `_read_deliverable_file_handler`(2125) |
| `read_whiteboard_excerpt`（Expert専用、BL-193で追加） | cela_main.py:1394 | `_read_whiteboard_excerpt_handler`(2231) |
| `verify_whiteboard_excerpt`（Detector専用、BL-079） | — | `_verify_whiteboard_excerpt_handler`(2195) |
| `read_plan_draft` | cela_main.py:1512 | `_read_plan_draft_handler`(1542) |
| `diff_plan_draft_versions` | cela_main.py:1439 | `_diff_plan_draft_versions_handler`(1468) |
| `read_verified_fact` | cela_main.py:655 | `_read_verified_fact_handler`(1839) |

Expertのツールロースターは、読み取りツールと`write_agreement`が**同一の`query_AI`呼び出し／ツールループの中に共存している**（cela_main.py:10782）。つまり「このターン内で先に読んだか」は、新規のプラミングを要しない、既に観測可能なシグナルである。

### §3.4 既存の読み取り追跡インフラ：narrow・advisory-only

`_LAST_DELIVERABLE_READ_TASK_IDS`（module global、cela_main.py:5069）は、`read_deliverable_file`が成功した`task_id`を記録する唯一の既存機構である。`_read_deliverable_file_handler`内（2167, 2189）で追記され、`query_AI`呼び出しごとにリセットされる（5188、＝「このターン」の粒度と一致）。`get_last_deliverable_reads()`(5079)を通じて`state["expert_last_deliverable_reads"]`へ橋渡しされる（フィールド宣言8766、セット14252、初期化16261）。

**唯一の消費先**はBL-242のDetector警告ブロック（cela_main.py:10873-10884）で、`_current_task_depends_on`のうち未読のtask_idを検出しDetectorへ提示する——advisory（警告のみ）であり、ツール呼び出しそのものを止めない。

この機構には、BL-265が必要とするものに対して以下のギャップがある。

- `read_deliverable_file`しか追跡しておらず、`read_whiteboard_excerpt`（`write_agreement`のedits分岐と直接対応する読み取りツール）は一切追跡していない。
- `task_id`のみを記録し、`phase_id`・バージョン・「返された内容が非空だったか」は記録していない。
- 別のロール（Detector）への事後警告であり、`write_agreement`実行時の前提条件チェックではない。

### §3.5 `goal_drafts`側の特殊事情

`revise_goal`のedits照合対象（`_apply_text_edits(_CURRENT_GOAL_TEXT, edits, ...)`、cela_main.py:3005）は`state["goal"]`そのものである。これはUser AIのプロンプトへほぼ常時（近静的なコンテキストとして）注入される性質の値であり、`whiteboard_drafts`のように「必要なときに`read_whiteboard_excerpt`で取りに行く」対象ではない。`read_goal_reference`（cela_main.py:1195）という類似名のツールが存在するが、これは外部参照文書用であって`goal_drafts`自体の読み取りツールではない。

つまり「専用の読み取りツール呼び出しが同一ターン内にあったか」という着眼点そのものが、`goal_drafts`にはそのままでは成立しない。BL-265の主対象は`whiteboard_drafts`（`read_whiteboard_excerpt` → `write_agreement`のedits）とし、`goal_drafts`側の扱いは設計時の未決事項として残す。

---

## §4 D-206/D-207/BL-242との関係：拒否された先例をどう乗り越えるか

これは本調査の核心的な論点である。BL-265が「機械的強制」を提案する以上、このプロジェクトが過去2回、同種の提案を明示的に検討し却下した経緯と正面から対峙しなければ、AGENTS.md §16.4「過去の決定を読み直してから行動する」に反することになる。

### §4.1 D-206/D-207：thinkツール必須化に付随する生reasoning差し替えの撤回

`decision_log.md:2888-2913`を原文で確認した。

- **D-206（2026-08-15、のち一部`superseded`）**：単一iteration内でreasoningチャンネルが同一結論を延々と再導出する生成崩壊が2回発生し（log/2026-08-15/1735・1954）、「迷いのトークンが文脈に乗ると同じ迷いを再生産する」という仮説に基づき、①thinkの毎iteration必須化、②**thinkを呼んだiterationでは生reasoning全文の代わりに構造化summaryのみを次iterationへ引き継ぐ**、③強制は機械的差し戻しではなくプロンプトレベルに留める、という3点を決定した。
- **D-207（同日）**：②を即日撤回。決定理由の原文：「D-206②は、迷い・撤回の言い回しの伝播を抑える狙いだったが、think必須化（D-206①）と組み合わさると、web検索結果の統合過程・詳細な検討内容・最終出力の下書き・構造化出力の下書きなど、thinkのsummary（1-3文）には到底収まらない実質的な内容までiteration完了ごとに圧縮・破棄されてしまう。これは『モデルの推論内容そのものへの情報破壊的な介入』であり、当初の狙い（文脈を汚す言い回しの抑制）を大きく超える副作用だとユーザーが指摘し妥当と判断した。」

**D-206/D-207が拒否したものの本質**：モデル自身が生成した推論内容（reasoning）を、次のターンへ引き継ぐ際に圧縮・破棄するという、**情報破壊的な介入**である。対象は「モデルの思考の中身」そのものだった。

BL-265が提案するゲートはこれと性質が異なる。ゲートが検査するのは「モデルが何を考えたか」ではなく、「特定のツール呼び出し（`read_whiteboard_excerpt`）が、特定の対象（同じtask_id/phase_idのwhiteboard）に対して、`write_agreement`のedits呼び出しより先に、実際にあったか」という、**モデルの内部状態に一切踏み込まない構造的な事実**である。何かを圧縮・破棄することもない。D-207の拒否理由はBL-265には適用されない。

### §4.2 D-211/BL-242：依存タスク未読の検知は警告に留める

`decision_log.md:2958-2969`、`issue_backlog.md:8167-8189`（BL-242本文）を原文で確認した。

- **経緯**：BL-241の対応後、ユーザーが「依存タスクを読んでいなければ機械的に検知してDetectorに示すか、あるいはターンを強制続行して必ず読ませるべきでは」と提案。
- **決定理由の原文**：「後者（機械的強制）は、同日中に実装・撤回したthink必須化の機械的強制（D-206②→D-207で撤回）と同型のコスト構造——往復回数・トークン消費の増加、形だけの遵守（read_deliverable_fileを呼ぶだけ呼んで中身を活かさない）のリスク——を持つと判断した。前者（機械的検知＋Detectorへの警告）は、既存のBL-033（Expertがpython_replを一度も使わなかった場合にDetectorへ警告し独立検算を促す仕組み）と全く同型のパターンで実装リスクが低く、ターンを止めないためコスト増も無い。まず軽い方（警告）を実装し、それだけでは実効性が不足すると実ドライランで確認されてから重い方（強制）を検討する、という順序で合意した。」
- **実装**：`_read_deliverable_file_handler`が成功した読み取りを記録し、`call_detector`が`depends_on`との差分（未読のtask_id）をDetectorへ警告として提示する。**`constraint_issue`を機械的に上書きする処理は持たず、Detector自身の判断に委ねる。ターンの強制差し戻しは実装しない。**

**D-211/BL-242が拒否したものの本質**：「依存する複数タスクの成果物を、すべて意味的に理解した上で作業しているか」という、**広範な意味論的完全性のチェック**である。この種のチェックは原理的に検知不能——`read_deliverable_file`を呼ぶだけ呼んで中身を活かさない「形だけの遵守」を機械的に見分ける方法がない——という指摘が、機械的強制を却下した直接の理由だった。

BL-265が提案するゲートはこれとも性質が異なる。ゲートが問うのは「Expertが依存タスクの内容を理解したか」ではなく、「今まさに書き換えようとしているtask_idのwhiteboardを、今回のedits呼び出しより前に、少なくとも一度読んだか」という、**単一ターン・単一対象に閉じた、意味理解を一切要求しない事実確認**である。D-211/BL-242と同様に「読んだが活かしていない」ケースを検知することはできないが、BL-265はそもそもそれを目指していない——目指すのは「読んでもいない対象のold_textを記憶や憶測で捏造する」という、BL-206/212で実際に発生した**より下位の、構造的に検知可能な失敗モード**の根絶である。

### §4.3 「なぜ今か」への誠実な回答

D-211は「まず軽い方（警告）を実装し、それだけでは実効性が不足すると実ドライランで確認されてから重い方（強制）を検討する」という順序で合意していた。この「警告では不足すると確認された」というトリガー条件が、今回すでに満たされているかを検証する必要がある。

**結論：満たされていない。** BL-206（2026-08-10頃）・BL-210・BL-211・BL-212・BL-213（いずれも2026-08-10〜11）は、すべてBL-242（2026-08-16）よりも**前**のインシデントである。これらはBL-242の警告メカニズム（依存タスク横断の未読検知）が実際に運用された後に、それでも読み取り漏れが再発した、という証拠には**ならない**。これらは別の問題——「同一編集内でのold_textの不一致」（BL-080/193/211/212）や「構造化フィールドの空文字ドリフト」（BL-206/210/211）——の証拠であり、BL-242が対象とする「依存タスク横断の未読」とは異なる失敗モードである。

したがって、本調査は「D-211のwarn-onlyは既に実ドライランで不足すると証明された」という主張には**依拠しない**。その主張は事実に反する。本調査がBL-265を提案する根拠は、あくまで§4.1・§4.2で論じた**「モデルの内部状態や意味理解には踏み込まない、構造的な事実確認に限定したゲート」という、D-206/D-207・D-211/BL-242が拒否したものとは性質の異なる、より狭いスコープの提案である**という一点のみである。

### §4.4 結論（設計提案、未決定）

上記の論証を踏まえた本調査の推奨は、**`whiteboard_drafts`に限定した、構造的事実確認のみのゲート**である。D-211の「まず軽い方から」という慎重な進め方の精神も踏まえ、以下の2案を並記し、ユーザーの判断を仰ぐ。

- **案A（機械的拒否）**：`_write_agreement_impl`に、対象task_idへの`read_whiteboard_excerpt`成功記録が同一ターン内に無ければeditsを拒否する検証ステップを追加する。
- **案B（段階導入・BL-242型の警告強化から開始）**：まずBL-242と同型の「未実行を検出してDetectorへ警告」を実装し、実ドライランで案Aへ進む必要性を測定してから、必要であれば機械的拒否へ格上げする。

本調査はいずれか一方を「決定」として推すものではない——ここは§4.1〜§4.3の論証を材料に、ユーザー自身が判断すべき論点として明示的に残す。

---

## §5 空文字の二重の意味：センチネル値のエビデンス（BL-264）

### §5.1 訂正：B1・B2は既に対応済みだった

当初の監査(A)が「最も確信度が高い」と評価した2件は、§2.1の到達可能性再検証により、いずれも**既に対応済み**と判明した。

**B1（訂正：対応済み）** — `decision_extractor_node`（cela_main.py:14949-14951）:

```python
action_type = item.get("action_type", "CREATE")
entry_type = item.get("entry_type", "Decision")
status = item.get("status", "Proposed")
```

`call_decision_extractor`（cela_main.py:11667）が返す`extracted_events`は、`decision_extractor_node`のこの行に到達する**前**に`_sanitize_extracted_events`/`_check_extracted_event`（cela_main.py:11544-11662、コメントに`[BL-213 F3]`と明記）を経由している。`entry_type`/`action_type`/`target_topic`が不正・空文字であれば項目ごと破棄（fatal）、`status`/`topic`/`proposed_by`が不正・空文字であれば`⚠️ [BL-213]`ログ付きで正規化（minor）される。BL-213 F3は`issue_backlog.md:7181`の状態セルで`done`（2026-08-11）と確認済み。**この行に到達する時点で、値は既に検証済みである。**

**B2（訂正：対応済み）** — `_commit_agreement_from_tool`（cela_main.py:3404-3405, 3627）:

```python
action_type = args.get("action_type", "CREATE")
entry_type = args.get("entry_type", "Decision")
...
status = args.get("status", "Proposed")  # 3627
```

`_commit_agreement_from_tool`の唯一の呼び出し元`_write_agreement_impl`（cela_main.py:3666、実際の必須フィールドチェックは3687-3690付近）は、呼び出し前に`if not args.get(f)`（空文字を正しく弾く）による必須フィールドチェックと、`args["action_type"] not in valid_actions`等のenum検証を既に行っている。**到達不能な防御的コードである。**

この訂正自体が、AGENTS.md §14.1「表面一致は診断ではない」の実演である——`grep`一致件数の多さや「同じ構造」という見た目だけで確信度を主張せず、必ず消費側まで遡って検証しなければならない。

### §5.2 B3：主エビデンス — `schedule_task_focus`の`baseline_agreement_id`

B1・B2が既に手当て済みだったことにより、本調査の主エビデンスはB3——`schedule_task_focus`の`baseline_agreement_id`——に絞られる。

`_apply_backward_redirect`（cela_main.py:14733）・`_apply_joint_focus`（cela_main.py:14760）:

```python
"baseline_agreement_id": redirect.get("baseline_agreement_id", ""),
```

兄弟フィールドである`target_task_id`（14718）・`companion_task_id`（14750）は、同じツール呼び出しの引数でありながら`_find_phase_containing_task`によって存在検証されている——存在しないtask_idであれば`⚠️`ログを出して処理を中断する（14720-14722, 14751-14752）。これに対し`baseline_agreement_id`は**無検証のまま**保存される。

下流の消費箇所、`_maybe_resume_forward_focus`（cela_main.py:14832-14837）:

```python
baseline_agreement_id = entry.get("baseline_agreement_id", "")
current_agreement = _find_active_deliverable_agreement(
    conn, run_id, _find_phase_id_for_task(state.get("phases", []), focused_task_id), focused_task_id
)
current_agreement_id = current_agreement.get("id", "") if current_agreement else ""
if current_agreement_id == baseline_agreement_id:
    return  # まだ変化なし、復帰しない
```

`_maybe_clear_resolved_companion`（14865-14870）も同型の比較を行う。

**成立するシナリオ**：LLMが`schedule_task_focus`呼び出し時に`baseline_agreement_id`を省略し（異常）、redirect時点でこのtask_idに現在アクティブなDeliverable agreementが存在しない（`current_agreement`が`None`）場合、`baseline_agreement_id`（異常により空文字）と`current_agreement_id`（正当な理由で空文字）という**2つの独立した経路で生じた空文字が、意味なく一致する**。結果、`_maybe_resume_forward_focus`/`_maybe_clear_resolved_companion`は「まだ成果物が更新されていない」と誤判定し、自動復帰・自動解消の機構が**無期限にブロックされる**。しかも同じ関数内の他の分岐（`resume_phase`が見つからない場合等）が使っている`⚠️`ログが、この分岐には一切無い——異常が発生していることに誰も気づけない。

これはBL-206/210/211/212と全く同じ「空文字が既定値を貫通する」構造だが、まだ実インシデントとして観測されてはいない**構造的リスク**である。

---

## §6 非文字列型フォールバックの追加監査（Category C）

ユーザーがIDE選択（cela_main.py:14728 `state.get("current_phase", {})`）を通じて指摘した通り、当初の監査(A)は文字列型の`""`フォールバックのみを対象としており、`{}`/`[]`のような非文字列型の空値フォールバックは検索対象に含まれていなかった。この見落としを追加調査した。

### §6.1 このパターンの特殊性

`state.get("current_phase", {})`は、これまで整理したCategory A（意図的な既定値）・Category B（LLM出力由来の異常フォールバック）のどちらとも異なる。`current_phase`はLLM出力ではなく、Python側の自コードが管理する内部state値である。しかも実際に`{}`が正当な値として代入される設計上の状態が存在する（`_reconcile_current_phase_after_replan`、cela_main.py:9263, 9310: `state["current_phase"] = phases[0] if phases else {}`、「まだphasesが確定していない」を意味する）。したがって`.get("current_phase", {})`という書き方だけを見て「危険」と決めつけることはできない——**呼び出し箇所ごとに、その時点でcurrent_phaseが本当に`{}`でありうるかを個別に判定する必要がある**。

これは§5.1のB1/B2訂正と同じ方法論（表面的なパターン一致ではなく、実行文脈まで遡って判定する）の再適用である。

### §6.2 grep結果と個別判定（18箇所）

`state\.get\("current_phase",\s*\{\}\)`は`cela_main.py`全体で18箇所ヒットする（`_phase_id_from`内の亜種を含めると19箇所）。個別に読み込み、以下の3群に分類した。

**健全群（意図が明文化され、警告ログも整備済み）**:

- `_get_current_task`（cela_main.py:9224-9240）：`current_phase = state.get("current_phase", {})`から`tasks = current_phase.get("tasks", [])`を取り出す。`current_task_id`がtasksに見つからない場合は明示的な`⚠️ [_get_current_task]`ログとフォールバックが実装されている。docstringが「BL-023」「BL-214」を明記し設計意図が追跡可能。
- `_reconcile_current_phase_after_replan`（cela_main.py:9243-9316）：`state["current_phase"]`そのものを再確定する関数であり、循環依存を避けるため意図的に生の値を扱う（コメントで明記：「この関数はcurrent_phaseそのものを決め直す側であり、実効解決はcurrent_phaseに依存するため（循環する）」）。フェーズ再構成時のミスマッチを検知して`⚠️ [BL-190]`ログを出す分岐が既に実装されている。BL-190/BL-191のインシデント対応から生まれた、極めて丁寧な設計。
- `_force_resume_forward_focus`／`_maybe_resume_forward_focus`（cela_main.py:14765-14852）：`current_task_id`（`current_phase`ではない）の生値を扱う理由が`[BL-214][例外]`コメントで明記され、「空文字であること自体を異常シグナルとして使っている」という設計意図が追跡可能。

**低リスク群（ロギング/コンテキストスレッディング用途）**:

以下は`current_phase.get("phase_id", "")`を、Detector/UserAIノードのグローバルコンテキスト変数（`_CURRENT_PHASE_ID`）や、`_write_chat_history_row`の`phase_id`カラムへ渡すためだけに使っている：cela_main.py:10801, 10827, 12557, 13362, 13373, 13546, 14290, 14409, 14431, 14469, 15515, 15757（計12箇所）。これらが実際に空文字へフォールバックしても、影響は「そのchat_historyの行やDetectorの参照文脈がどのphase_idに属するか分からなくなる」というトレーサビリティの劣化に留まり、制御フロー（承認判定・遷移判定・agreement書き込み）を直接歪めるものではない。優先度は低いが、`_write_chat_history_row`のデータ品質という観点では次点候補として記録する。

**要対応群（本調査で新たに特定した2箇所）**:

1. **`_apply_backward_redirect`（cela_main.py:14710-14744）**: `current_phase = state.get("current_phase", {})`（14728）の結果を、`stack.append({..., "phase_id": current_phase.get("phase_id", ""), ...})`という形で**`task_focus_stack`という永続的な制御構造へ書き込んでいる**（14730）。`_apply_backward_redirect`が呼ばれる時点は、`schedule_task_focus`ツールが実際に呼ばれたターンであり、`_reconcile_current_phase_after_replan`によって`current_phase`は既に何らかの実在フェーズへ設定されているはずのタイミングである。もしこの時点で`current_phase`が真に`{}`（またはキー自体が欠落）であるなら、それは「フェーズ未確定」という正当な理由ではなく、**state管理の初期化・伝播自体が壊れている**という、より深刻な異常を意味する。しかもこの分岐には、同じ関数の他の`⚠️`ログとは異なり、**警告が一切無い**。これはBL-024（current_phaseの初期化後フリーズ）と同系統の再発リスクである。
2. **`_phase_id_from`（cela_main.py:4773-4774）**:
   ```python
   def _phase_id_from(state: dict | None) -> str:
       return (state.get("current_phase", {}) or {}).get("phase_id") or _CURRENT_PHASE_ID if state else _CURRENT_PHASE_ID
   ```
   この関数は`TOOL_DISPATCH`（cela_main.py:4938-4974）内で、`write_agreement`（4950）・`write_issue`（4965）・`flag_needs_human_input`（4969）の**`phase_id`引数を供給する経路そのもの**である。`state.get("current_phase", {})`が空になり、かつモジュールglobalの`_CURRENT_PHASE_ID`も空文字であれば、`_phase_id_from`自体が空文字を返す。これは`_write_agreement_impl`が持つBL-161の防御（`args.get("phase_id") or phase_id`という"or"パターン、cela_main.py:3417-3419）における**フォールバック値そのもの**であり、この二段目のフォールバックが静かに汚染されると、BL-161の防御自体が意味を失う——**フォールバックのフォールバックが腐っている**という、二次的だが見落としやすいリスクである。

### §6.3 Category Cの結論

18箇所のうち16箇所は健全（意図が明文化済み、または低リスクなロギング用途）であり、実際に対応を要するのは2箇所（`_apply_backward_redirect`、`_phase_id_from`）に絞られる。これはB1/B2の訂正と同じ構図——横断的なgrepヒットの大部分は既に安全であり、本当に危険な箇所はごく少数に絞り込まれる——であり、AGENTS.md §14.1の教訓が2度目に実演された形になる。

---

## §7 設計上の帰結：3つのパターンの使い分け

これまでの調査で、`""`/`{}`/`[]`ドリフト対策として、既存コードには実質**3つの異なるパターン**が存在する（うち1つは既に確立済み）。どれを使うべきかは、フィールドの値域の性質と、値の出所（LLM出力か内部stateか）で決まる。

**パターン1（enum値フィールド、確立済み・新規実装不要）**：`status`/`action_type`/`entry_type`のような、有限の許容集合を持つLLM出力由来フィールドには、BL-213 F3が既に確立した「fatalなら項目ごと破棄・minorならログ付きで正規化」というハイブリッド検証を適用する。この時点で既に`decision_extractor`のフォールバック経路・`write_agreement`ツール経路の双方で機能している。**新規のセンチネル値は不要**——enumの外側の値そのものが既に異常の目印になっているため。

**パターン2（ID参照・自由記述フィールド、LLM出力由来、新規センチネルが必要）**：`baseline_agreement_id`のような、正当な値域自体が空文字を含みうる（または閉じた集合を持たない）フィールドには、enumの外側判定が使えない。ここに限り、新規の専用センチネル定数を導入し、「LLM出力の欠落・不正によってこの値が代入された」ことを構造的に区別可能にする。設計素案：

```python
# cela_main.pyのモジュールレベル定数群（既存の_CURRENT_*globalと同じ並びを想定）
_LLM_FALLBACK_SENTINEL = "￼__CELA_LLM_FIELD_MISSING__￼"  # 通常のLLM出力に出現しない制御文字で挟む
```

`==`比較・ログ出力・DB行のいずれで見ても一目でわかるマーカーとし、`if value == _LLM_FALLBACK_SENTINEL:`で明示的に検知・ログ出力（fail-closed、§13.2）する。既存の意図的な空文字既定値（`revision_reason=""`等）は一切変更しない——このセンチネルは「LLM出力を消費した結果、値が欠落していた」という文脈にのみ使う。

**パターン3（内部state由来、到達不能なはずの異常経路、loud failure化）**：`current_phase`/`_phase_id_from`のような、LLM出力ではなく自分自身のstate管理契約に依存するフィールドには、センチネル値ではなく**loud failure**を適用する。目的が異なるため——パターン2は「値を区別可能にする」ことが目的だが、パターン3は「そもそも到達したら即座に気づけるようにする」ことが目的である。`{}`/`[]`への静かなフォールバックを、最低限の`⚠️`ログ、必要であればassertion／例外へ置き換える設計を、`_apply_backward_redirect`と`_phase_id_from`の2箇所を対象に個別検討する。

---

## §8 まとめと推奨対応順序

| # | 発見 | severity | 対応方針 |
|---|---|---|---|
| B1 | `decision_extractor_node`のenum空文字フォールバック | — | **対応不要**（BL-213 F3で既にdone、到達不能） |
| B2 | `_commit_agreement_from_tool`のenum空文字フォールバック | — | **対応不要**（`_write_agreement_impl`で既に検証済み、到達不能） |
| B3 | `schedule_task_focus`の`baseline_agreement_id` | 中（未発現の構造的リスク） | BL-264パターン2（センチネル値）の第一適用候補 |
| C-1 | `_apply_backward_redirect`の`current_phase`フォールバック | 中（未発現、control-flow影響） | BL-264パターン3（loud failure化）の適用候補 |
| C-2 | `_phase_id_from`の二段フォールバック | 低〜中（BL-161防御の二次的弱体化） | BL-264パターン3（loud failure化）の適用候補 |
| C-低リスク群 | chat_history等のロギング用途12箇所 | 低 | 次回優先度づけの材料として記録するに留める、本BLでは対応を確約しない |
| BL-265本体 | `write_agreement`/`revise_goal`のread-before-write | — | §4.4案A/Bのいずれかをユーザーが選択後、設計・実装 |

**推奨する着手順序**：BL-264（センチネル値・loud failure化）はD-206/D-207/BL-242との論争を持たず、独立して低リスクに着手できる。BL-265（read-before-writeゲート）は§4の論証をユーザーが是認してから着手すべきであり、この論証を経ずに実装へ進むことは、AGENTS.md §16.1「ユーザー自身の提案であっても軽い代替案とのトレードオフを提示してから実装すべき」という、D-207自身が引用する教訓の再侵犯になる。

---

## §9 監査で「問題なし」と確認した箇所

再調査のコスト削減のため、健全と確認済みの箇所を記録する。

- `_check_extracted_event`/`_sanitize_extracted_events`（cela_main.py:11544-11662、BL-213 F3）：`decision_extractor`が返す`extracted_events`のenum値フィールドを、fatalなら破棄・minorなら正規化する形で既に検証している。
- `_write_agreement_impl`の必須フィールド・enum検証（cela_main.py:3687-3708付近、BL-131等の先行実装）：`write_agreement`ツールの`args`に対し、`_commit_agreement_from_tool`へ渡る前に空文字を含む必須チェックとenum検証を既に行っている。
- `_get_current_task`／`_reconcile_current_phase_after_replan`（cela_main.py:9224-9316、BL-023/BL-190/BL-191/BL-214）：`current_phase`/`current_task_id`の非同期・不整合ケースを明示的なコメントと警告ログで丁寧に扱っている、Category Cにおける参考実装。
- `_orchestrator_fallback`（cela_main.py:10137-10151、`call_orchestrator`）：`(parsed.get("expert") or "").strip()`のうえで`if not expert:`により実質的な既定値へ置換し`⚠️`ログを出す、パターン2の先例として参考になる良い実装。

---

## §10 参照

- `issue_backlog.md`：BL-024, BL-080, BL-131, BL-139, BL-161, BL-190, BL-191, BL-193, BL-206, BL-210, BL-211, BL-212, BL-213（および調査記録`BL213_investigation.md`）, BL-214, BL-215, BL-241, BL-242, BL-261, BL-264, BL-265
- `decision_log.md`：D-161, D-184, D-185, D-186, D-189, D-190, D-206, D-207, D-211
- `AGENTS.md`：§13（LLM出力の防御的処理）、§14.1（表面一致は診断ではない）、§15.1（1ルール1箇所）、§15.3（機械的検証の優先）、§16.1（軽い代替案の提示）、§16.3（言えないことは言えないと言う）、§16.4（過去の決定の再読）
- 本調査を構成した2本のExploreエージェント監査結果、およびPlanエージェントによる設計・再検証は、いずれもこのセッションの対話ログに残る（別ファイルとしては保存していない）。本ドキュメントはそれらの内容を統合・整理した最終版である。
