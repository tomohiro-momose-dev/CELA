# BL-104: call_expertのphases_json→目次化＋read_project_planツール新設、プロンプトのキャッシュ効率改善（静的指示文の先頭集約）

関連: [issue_backlog.md BL-104](../issue_backlog.md#bl-104-call_expertのphases_json目次化read_project_planツール新設プロンプトのキャッシュ効率改善)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は設計時点のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## Context

BL-103完了後、実ドライラン`log/2026-07-27/1739`をユーザーとレビューする中で2つの関連する改善が持ち上がった。

### 1. `call_expert`の`phases_json`（全フェーズ・全タスクの完全なJSON、cela_main.py:4432）

DBから直接測定した結果、`phases_json`単体で13,361文字（6フェーズ構成の時点）あり、`call_expert`の1回の呼び出しにつき（tool loopのiter=1のみ、後述）無条件で注入されていた。一方、`call_expert`は`_build_task_scope_context`経由で既に`current_task_json`（自タスクのtitle/description/acceptance_criteria/depends_on/owns_variables）・`verified_facts_json`（依存タスクの確定値、Python側で`depends_on`→`owns_variables`を解決済み）・`deferred_notes_text`を受け取っており、Expertが機能的に必要とする情報は既に個別に届いている。BL-025（Expertが他タスクのowns_variables領域に踏み込んでしまう問題への対策）の経緯を踏まえると、全体計画を常時見せること自体がスコープ逸脱の誘因にもなり得る。

調査の結果、`light_system_prompt`への差し替え（BL-025②、cela_main.py:2734、`iteration == 1`時のみ差し替え）により、`phases_json`が実際にモデルへ見えるのは**tool loopのiter=1の1回のみ**（iter=2以降は`light_system_prompt`に差し替わり、`phases_json`を含まない）であることを確認済み。

**対応:** `phases_json`の常時全文表示をやめ、`phase_id`/`task_id`/`title`のみの軽量な目次（ToC）を常時表示に変更。全文の詳細が必要な場合は、新設の読み取り専用ツール`read_project_plan`で能動的に取得できるようにする（`user`（User AI）は本ツールの対象外、従来通り`generate_user_utterance`側では`phases_json`全文を維持——プロジェクトオーナーとして全体像の把握が本質的に必要なため）。

### 2. プロンプトキャッシュのヒット率低下（OpenRouter、40%→5%）

ユーザーから、BL-096前後の各種配線（write_issue/read_issues等）を境にOpenRouterのキャッシュヒット率が急落したとの報告があり、「ツール使用で情報が更新されたプロンプトが生まれ、キャッシュにヒットしなくなっているのでは。固定文字をプロンプトの上に集約すべきでは」との仮説が示された。

調査の結果、`call_expert`の`system_prompt`組み立て順は、変動する内容（`expert_name`・`turn_count`表示・`agreements_text`等）が冒頭2〜6番目に集中しており、分量として最大の固定指示文ブロック（🔥エージェントとしての行動原則・回答形式・F-2.6検算ゲート・重複検証禁止・ドメイン妥当性チェック・確定値/暫定値区別）はその**後ろ**に配置されていた。プレフィックスキャッシュ（OpenRouter含め大半のプロバイダは明示的な`cache_control`無しでも自動で行う）は「先頭から一致した部分」までしかヒットしないため、ターン数の表示が1つ変わる・`agreements_text`が1行増えるだけで、後続の（分量として最大の）固定ブロックも含めて丸ごとキャッシュミスになっていた。

これはユーザーの仮説（要因1）を裏付けるものだが、BL-096以降ツールループの反復回数自体が増えた（read_issues/read_verified_fact等の「まず確認してから」という指示の積み重ねにより、1ノード呼び出しあたり5〜10回以上のツール往復が一般化した）ことによる「新規（キャッシュ不可能）トークン比率の希薄化」（要因2）も併発している可能性が高いと考えられる。ただし40%→5%という急落幅の大きさからは、要因1（プレフィックス不一致）が主因である可能性が高いと判断した。要因2は構造の並び替えでは解消しない別種の問題であり、対応は見送る（tool loopの反復回数自体を減らす設計変更は本BLのスコープ外）。

**対応:** 固定の指示文をプロンプト冒頭に集約し、ターンごとに変わる動的内容（決定事項DB・現在タスク情報・ホワイトボード・hydrate_context等）を末尾に配置する構造に、`call_expert`を皮切りに順次並び替える。ユーザー指示により、他ノードへも同じ原則を順次展開する（本書では原則と`call_expert`の実装を確定し、他ノードは同じ原則に基づき別途・順次対応する）。

## 設計

### A. `read_project_plan`ツール新設

新規グローバル`_CURRENT_PHASES: list[dict] = []`を、既存の`_CURRENT_TASK_ID`等と同じパターンで追加する（tool handlerは`state`を直接参照できないため、呼び出しノードが呼び出し直前にモジュールグローバルへコピーする既存の設計を踏襲）。

```python
READ_PROJECT_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "read_project_plan",
        "description": (
            "Read the full project plan (all phases and tasks, including each task's "
            "description/acceptance_criteria/depends_on/owns_variables) -- the complete structure "
            "that only a lightweight table-of-contents (phase_id/task_id/title) is shown for by "
            "default. Call this only if the table-of-contents in the prompt is not enough context "
            "for your current task (e.g. you need to understand another task's exact requirements "
            "or dependency structure)."
            "[BL-093] You must also call `think` with a non-empty `summary` in this SAME response "
            "(not a separate later response), or none of this response's tool calls -- including "
            "this one -- will be executed."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}
```

`_read_project_plan_handler(args: dict) -> list`は`_CURRENT_PHASES`をそのまま返す薄いラッパー。`TOOL_DISPATCH["read_project_plan"]`に配線。

新規`_build_project_plan_toc(phases: list[dict]) -> str`（`phase_id`/`title`と`task_id`/`title`のみを箇条書きで整形、空なら"(まだフェーズ・タスク計画がありません)"）。

### B. `call_expert`の`phases_json`をToCへ置換

```python
system_prompt += (f"""
\n📊 [プロジェクト進行計画 目次]
Task Plannerが作成したフェーズとタスクの一覧（目次）を以下に示します。各タスクの詳細
（description・acceptance_criteria・depends_on・owns_variables）が必要な場合は、
read_project_planツールで全文を確認してください。\n
{project_plan_toc}\n\n
指示があったフェーズ、タスクに関しては、必ずこの計画を参照し、逸脱や矛盾がないよう思考してください\n
""")
```

`call_expert`冒頭で`global _CURRENT_PHASES; _CURRENT_PHASES = state.get("phases", [])`を設定。`tools=[...]`（heavy側・`light_system_prompt`の説明文言の両方）に`READ_PROJECT_PLAN_TOOL`/`read_project_plan`を追加。

`generate_user_utterance`（User AI）・`call_task_plan_reviewer`は現状維持（`phases_json`全文を継続表示）。

### C. `call_expert`のプロンプト構造をキャッシュ効率の良い順序へ並び替え

**原則:** 「実行中いつでも内容が同一である固定指示文」を冒頭にまとめ、「ターンごとに内容が変わる動的データ」を末尾（chat_historyへの引き渡し直前）に配置する。プロバイダの自動プレフィックスキャッシュを最大限活用するため。

並び替えにあたり、各ブロックが**他のブロックへの位置的参照**（「上記の」「以下に示す」等）を持つかを個別に確認した:
- 「⚠️【厳守事項】上記の【決定事項DB】は…」（cela_main.py:4453-4458）は`agreements_text`への位置的参照を持つため、`agreements_text`と共に動的末尾グループに残す（並び替えない）。
- 「🔥エージェントとしての行動原則」「📝回答形式について」「【F-2.6機械的検算ゲート】」「【同じ検証・計算を繰り返さない】」「【ドメイン妥当性チェック】」「🔀【確定値と暫定値の区別】」（cela_main.py:4465-4534, 4587-4598）はいずれも自己完結しており位置的参照を持たないため、**固定指示文グループへ移動可能**と確認した。
- 差し戻し時のみ表示される「⚠️【重要：Detectorからの差し戻し】」ブロック（cela_main.py:4609-4626）は「上記📋セクションに示されている現在のホワイトボードは…」とR4セクションへの参照を持つため、ホワイトボード表示ブロックの後という現状の相対位置を維持したまま動的グループに残す。

**新しい順序（`call_expert`）:**
1. `あなたは有能な{expert_name}の分野の専門家です。`（persona宣言。expert_name自体はタスクごとに変わるが、同一タスクのリトライ間では不変なため、これより後ろを完全固定にする効果は損なわれない）
2. 固定指示文グループ（上記で確認した6ブロック＋「5ターン毎に議論のサマリーを出力せよ」の1行、全て実行中不変）
3. goal＋goal_essence（`agent_has_guardrail`時のみ。revise_goal成立時以外は不変）
4. `expert_focus_guidance`（タスク選定時のOrchestrator助言）＋ プロジェクト進行計画目次（ToC、task_plannerの実行時のみ変化）
5. スコープガードレール導入文＋`current_task_json`／`verified_facts_json`／`remaining_criteria_text`（タスクごとに変化）
6. ホワイトボード（R4）／申し送り事項（BL-082）／エスカレーション状況（BL-086）
7. 差し戻し時のみ: Detectorからの差し戻しブロック
8. `escalation_resume_notice`（BL-096）
9. 「文脈の参考として…」導入文
10. **（最も変動が激しいため最後尾）** ターン数表示・終盤フェーズの追加指示・`agreements_text`＋DB自動管理の厳守事項
11. `is_stateless_mode`時: `hydrate_context`＋`escalation_pin`（BL-103）
12. `messages.append({"role": "system", ...})`、続けてchat_history

`light_system_prompt`（iter=2以降用）にも`READ_PROJECT_PLAN_TOOL`の説明を1文追加する。内容そのものの並び替えは不要（既に現在タスク情報のみに絞られた軽量版のため）。

### D. 他ノードへの横展開

`generate_user_utterance`・`call_detector`（両パス）・`call_orchestrator`・`call_resource_arbiter`・`call_integrator`・`call_reviewer`・`call_reflection`・`call_facilitator`・`call_task_planner`・`call_task_plan_reviewer`・`call_goal_essence_analyst`にも同じ原則（固定指示文を先頭、動的データを末尾）を適用する。ユーザー指示「他のノードも順次プロンプト順の整理を進めてください」に基づき、本BLでは`call_expert`を実装した上で、残りは同一BL内で優先度の高いノード（呼び出し頻度が高い`generate_user_utterance`・`call_detector`）から順次対応し、各ノードごとに`python -m py_compile`＋関連テストで検証しながら進める。低頻度ノード（`call_reflection`・`call_facilitator`・`call_task_planner`等）は必要に応じて後続で対応する。

## 完了条件 / 検証

1. `python -m py_compile cela_main.py`
2. 新規`tests/test_bl104_project_plan_toc_and_prompt_reorder.py`:
   - `_build_project_plan_toc`の整形（空/複数フェーズ・タスク）
   - `_read_project_plan_handler`が`_CURRENT_PHASES`をそのまま返すこと
   - `TOOL_DISPATCH`に`read_project_plan`が配線されていること
   - `call_expert`のソースに`phases_json`の全文ダンプが残っていないこと、`_build_project_plan_toc`と`READ_PROJECT_PLAN_TOOL`が含まれること
   - `call_expert`のソース上で、固定指示文（例:「エージェントとしての行動原則」）の出現位置が、動的内容（`agreements_text`のf-string挿入位置）より前であることを機械的に確認（`inspect.getsource`のインデックス比較）
3. 関連クラスタ回帰（`bl025 or bl075 or bl086 or bl091 or bl093 or bl094 or bl096 or bl101 or bl102 or bl103`）
4. `check_docs_consistency.py`
5. 実LLM再ドライランでの実際のキャッシュヒット率改善確認は次回待ち（OpenRouterのキャッシュ統計はダッシュボード側の集計のため、このセッションでは直接検証できない）。
