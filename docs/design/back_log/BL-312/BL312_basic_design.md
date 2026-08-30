# BL-312: call_detectorのdomain_prompt/promptを静的先頭・動的末尾へ再構成（プロンプトキャッシュ効率化）

## Context

OpenRouterのプロンプトキャッシュヒット率低下（70%→65%）の報告を受け、直近のプロンプト変更
（BL-306/BL-307）を調査した。BL-307（`call_expert`）は無関係——`call_expert`はBL-178/
BL104_basic_design.mdで既に「実行中いつでも内容が同一の固定指示文は先頭にまとめ、ターン毎に
変わる動的データは末尾に配置する」というキャッシュ最適化の再構成を受けており、BL-307はその
静的セクションに正しく追加されていた。

一方`call_detector`の2つのプロンプト（`domain_prompt`＝ドメイン妥当性レビュー、`prompt`＝数値
監査）は、静的な指示ブロックと動的データ（決定事項DB・ゴール文・ホワイトボード等）が終始
入り混じった構造のままで、Expertが受けたのと同じ再構成を一度も受けていない。BL-278/292/188/
195/198/204等、過去の静的指示追加はすべてこの「動的ブロックの後ろ」に積み上がっており、
BL-306もその一つだった。Detectorは全タスクでdomain review＋numeric auditの2パスが毎回走る
最頻出ノードのため、この非効率が集計上のキャッシュヒット率に無視できない影響を与えていると
推定される。

事前調査（Explore agentによる`call_detector`全文12540-13400・`call_expert`11864-12539の
網羅的読解）で以下が判明した：

- `call_detector`は`messages`配列やchat_historyを持たず、`_query_and_parse_with_retry`
  （cela_main.py:7045）経由で`query_AI([{"role":"user","content": <1本の巨大文字列>}], ...)`
  （cela_main.py:7073）という**単一文字列**として送信される。したがって、この文字列の
  「先頭からどこまでが呼び出しごとに完全に同一か」がそのままキャッシュ可能長になる。
- `domain_prompt`（12876-13062）・`prompt`（13149-13300）とも、静的指示ブロックの中に
  「上記に🔒が付いている項目」「上記2つ」「上記DB」「上記ホワイトボードの本文から」等、
  直前の動的ブロックを指す**位置参照文**が複数箇所に存在する（詳細はSection 2参照）。単純な
  並べ替えではこれらの参照が壊れる。
- `call_expert`のlight_system_prompt（BL-178）は、まさに同じ問題に対して「位置参照文を
  “上記の”ではなく見出し名・BL番号で自己完結的に書き換える」ことで解決済みの前例がある
  （cela_main.py:12487-12491、12513-12525のコメント参照）。本BLも同じ技法を使う。
- `domain_role_instruction`（`domain_prompt`専用の役割別文言）は`review_mode=="goal_change"`
  分岐でのみ、旧ゴール文・新ゴール文を直接埋め込む＝動的になる（他2分岐は静的）。
  `role_specific_instruction`（`prompt`専用）は`target_role=="user"`分岐で`current_task_id`
  を直接埋め込む＝動的になる。いずれも「target_role単位でしか変わらない＝静的」という
  既存コメント（12874付近）の前提が一部の分岐で成立しておらず、誤って先頭に固定すると
  古いタスクID・ゴール文がキャッシュされたまま次ターンに漏れる危険がある。**両方とも
  動的末尾ゾーンへ retained**する（安全側に倒す）。

## Design principle

各プロンプトを「STATIC-TOP（呼び出しごとに完全に同一・常に先頭）」→「DYNAMIC-TAIL（state/DB
由来で毎回変わる・末尾に集約）」の2ブロックへ再構成する。位置参照文（「上記の」「上記2つ」等）は、
参照先の見出し名・BL番号を直接書く自己完結文へ書き換えた上でSTATIC-TOP側へ移動する（BL-178の
light_system_promptと同じ技法）。移動不可能な唯一の例外は"下記【R4】"という**前方**参照文で、
これは自己完結のままSTATIC-TOPへ移動できる（後述）。

## Section 1: `domain_prompt`の再構成（cela_main.py:12876-13062）

### STATIC-TOP（元の相対順序を維持、書き換え箇所のみ★）

1. 12877-12887：役割定義・検算不要の説明・BL-300 python_repl注記
2. 12889-12904：判定基準（major/minor/none）
3. `_observations_block`／`_issue_carryover_prefix`（12905-12906、局所変数・引数なし）
4. `_bounded_deliberation_instruction('observationsに書いた懸念を…')`（12907、引数は固定文字列）
5. 12908-12922：BL-093think注記／BL-188 read_reference_file／BL-188根拠実在性チェック
6. `_missing_data_estimation_instruction(perspective='auditor')`／`_reasoning_reset_instruction('observations')`（12923-12924、引数は固定文字列）
7. 12925-12970：BL-195／BL-198・BL-257／BL-204・BL-205／BL-203／固定ツール一覧
8. `_THINK_TRAILER_SENTENCE`／`_build_decision_lineage_directive('"Rejected"…')`（12971-12972、引数は固定文字列）
9. ★12974-12976（BL-086🔒）を書き換えて移動：
   - 旧: `"【BL-086: 🔒Freeze済み項目の扱い】上記に🔒が付いている項目があれば…"`
   - 新: `"【BL-086: 🔒Freeze済み項目の扱い】後述の内容に🔒が付いている項目があれば…"`
   - 注：`domain_prompt`側は`_get_frozen_agreements_text`（見出しなし、`🔒 [id] topic: ...`の
     生行のみ）を使っており「【プロジェクトの合意・決定事項・検討状況DB】」という見出しは
     存在しない（それは`prompt`側の`agreements_text`のみが持つ見出し）。よって見出し名では
     なく🔒マーカー自体を指す（元の文言も元々見出しではなくマーカーを指していたため、
     実質的には「上記」→「後述の」の一語だけの変更で済む）。
10. ★12984-13035（BL-087/BL-266/BL-278・306/BL-279/BL-292の連鎖）を書き換えて移動：
    - BL-087（12984-12986）: `"上記【🎯 本質】に照らして"` → `"後述の【🎯 本質】に照らして"`
    - BL-266（12987-12997）: `"上記のドリフト検知（本質からの乖離）とは別に"` → `"[BL-087]のドリフト検知（本質からの乖離）とは別に"`
    - BL-278/306（12998-13020）: `"上記2つ（本質ドリフト・本質充足性）とは別の観点として"` → `"[BL-087]の本質ドリフト・[BL-266]の本質充足性、2つとは別の観点として"`
    - BL-279（13021-13024）: 「上記」なし、そのまま移動可
    - BL-292（13027-13035）: `"上記の選定妥当性チェックとは別に"` → `"[BL-278/306]の選定妥当性チェックとは別に"`
11. ★13038-13041（BL-076）を書き換えて移動：
    - 旧: `"上記ホワイトボードの本文から"`
    - 新: `"後述の【R4: 現在タスクの成果物・最新ホワイトボード】節の本文から"`
    - 見出し文言は`whiteboard_block`の実際の出力（cela_main.py:12585）と一字一句一致させた。
12. `_scratch_concerns_closure_instruction("observations", escalation_tools="write_issue")`（13060、引数は固定文字列）※現状DYNAMIC-TAILの最後にあるが、これも引数固定のため実質STATIC。位置はDYNAMIC-TAILの直前に維持（並び順の意味が変わらないため）。
13. 13061の`Return ONLY JSON: {...}`固定スキーマ ※そのまま末尾（出力形式指示は直前に置くのが自然なため据え置き）

### DYNAMIC-TAIL（元の相対順序を維持）

`domain_role_instruction`の埋め込み位置をここへ移動（理由：goal_change分岐が動的なため） →
`_get_frozen_agreements_text` → `_build_unaudited_facts_text` → `escalation_pin_block` →
`deferred_issue_pin_block` → `acknowledged_issue_pin_block` → `human_input_notice_block` →
`System Goal: {goal}` → `_get_goal_essence_text` → `【現在タスクのacceptance_criteria】
{criteria_text}` → `whiteboard_block` → `write_agreement_status_block` →
`deferred_notes_block` → `_get_task_focus_companion_text` → `_build_task_focus_state_text` →
`_build_task_focus_transition_notice` → BL-191注記（13047-13049、書き換え不要・そのまま） →
`pending_task_redirect`条件ブロック（13050-13058） → `【今回評価するターンのやり取り】
{history_text}`

## Section 2: `prompt`（数値監査）の再構成（cela_main.py:13149-13300）

### STATIC-TOP

1. 13150-13168：役割定義／risk定義／constraint_issue定義／riskとconstraint_issueの独立性注記
2. 13172-13182：予算上限注記／検算注記／F-2.6ゲート／`_bounded_deliberation_instruction`・`_verification_throttle_warning`（引数固定）
3. `_observations_block`（13184）
4. 13185-13249：BL-079／BL-094／BL-093（`_BL093_THINK_VALUE_PARAGRAPH`）／`_issue_carryover_prefix`／BL-188×2／BL-195／BL-198・257／BL-204・205／BL-203／固定ツール一覧
5. `_THINK_TRAILER_SENTENCE`／`_build_decision_lineage_directive`（13250-13251、引数固定）
6. ★13267-13270（forward reference、書き換え不要）を移動：
   - `"…下記【R4: 現在タスクの成果物・最新ホワイトボード】節の内容のみを使用してください。"`
   - このまま自己完結（前方参照は見出し名を直接指しており位置に依存しないため書き換え不要）
7. ★13273-13278（BL-086🔒）を書き換えて移動：
   - `"上記DBで🔒アイコンが付いている項目は"` → `"後述の【プロジェクトの合意・決定事項・検討状況DB】で🔒アイコンが付いている項目は"`
8. ★13279-13284（BL-062）を書き換えて移動：
   - `"上記DB内の特定のtopic"` → `"後述の【プロジェクトの合意・決定事項・検討状況DB】内の特定のtopic"`
9. ★13287-13290（BL-076、`domain_prompt`と同一文言）を書き換えて移動：
   - `"上記ホワイトボードの本文から"` → `"後述の【R4: 現在タスクの成果物・最新ホワイトボード】節の本文から"`（項目6の前方参照文と同じ見出し名で統一）
10. `_scratch_concerns_closure_instruction(...)`（13298、引数固定）※DYNAMIC-TAIL直前に据え置き
11. `Return ONLY JSON: {...}`固定スキーマ（13299）※末尾に据え置き

### DYNAMIC-TAIL

`role_specific_instruction`・`thought_process_audit`の埋め込み位置をここへ移動（理由：両方とも
一部分岐で動的なため） → `System Goal: {goal}` → `_get_goal_essence_text` →
【BL-023】ラッパー文＋`{criteria_text}`（13256-13260、ラッパーとcriteria_textは1文として不可分
のためまとめて移動） → `domain_findings_block` → `python_calls_block` →
`deliverable_reads_block` → `write_agreement_status_block` → `Recent Decisions:
{recent_decitions}` → `【プロジェクトの合意・決定事項・検討状況DB】{agreements_text}` →
`whiteboard_block` → `deferred_notes_block` → `_get_task_focus_companion_text` →
`_build_task_focus_state_text` → `_build_task_focus_transition_notice` →
`【今回評価するターンのやり取り】{history_text}`

## Section 3: 実装上の注意点

- 書き換える文（9箇所）はいずれも「意味を変えず、参照方法だけを相対位置→見出し名/BL番号へ
  変更する」ことに厳密に限定する。判定基準・チェック内容の文言は一切変更しない。
- `_get_frozen_agreements_text`・`agreements_text`・`_get_goal_essence_text`・
  `whiteboard_block`が実際に出力する見出し文字列（「🎯 本質」「【プロジェクトの合意・決定事項・
  検討状況DB】」等）を実装前に確認し、書き換えた参照文の見出し名と一字一句一致させる。
- `domain_role_instruction`／`role_specific_instruction`をDYNAMIC-TAILへ移すことで、
  非goal_change／非user分岐（純粋静的な文言）もSTATIC-TOPの恩恵を受けられなくなる
  （安全側に倒すためのトレードオフとして許容、コメントで明記する）。
- 変更はcall_detector関数内の文字列組み立て順序のみ。ツール一覧・権限チェック・戻り値の
  構造・JSON出力スキーマ・呼び出しているLLM APIの引数は一切変更しない。

## Critical Files

- `cela_main.py`：`call_detector`関数（12540-13400付近）の`domain_prompt`（12876-13062）・
  `prompt`（13149-13300）の2つの文字列組み立てブロックのみを再構成。関数シグネチャ・
  呼び出し元・戻り値は変更しない。
- `tests/test_bl312_detector_prompt_cache_prefix.py`（新規）

## Verification

1. **プレフィックス不変性テスト（最重要・§17.1の反証可能な回帰テスト）**：
   `cela_main._query_and_parse_with_retry`をmonkeypatchして`prompt`引数を捕捉するスタブへ
   差し替え、同一`target_role`/`review_mode`だが動的内容（goal文・agreements・whiteboard等）
   が異なる2つの`state`で`call_detector`を呼び、2回分の`domain_prompt`/`prompt`それぞれで
   共通接頭辞（os.path.commonprefixに相当する文字列版）の長さを計測する。旧コードでこの
   共通接頭辞長を測定し、新コードでそれより有意に（目安：数千文字以上）伸びていることを
   確認する回帰テストを書く（`git stash`で新コードを一時的に戻すと接頭辞長が短くなる＝
   テストが失敗することを確認）。
2. **内容完全性テスト**：旧実装で最終的に埋め込まれていた全ての動的値（goal文の特定の一節、
   agreements_textの特定のtopic文字列、whiteboard_blockの特定の一節等）が、再構成後の
   `domain_prompt`/`prompt`にも（順序は変わっても）全て含まれていることを確認する
   （§13.5：クラスごと確認、一部の値だけ拾って安心しない）。
3. **位置参照文の見出し一致テスト**：書き換えた9箇所の文が、実際に参照する見出し文字列
   （`_get_frozen_agreements_text`等の出力冒頭）と一致するキーワードを含むことを確認する。
4. `python -m py_compile cela_main.py`
5. 既存のDetector関連テスト（`test_bl278`・`test_bl292`・`test_bl306`・`test_r5*`等、
   domain_prompt/promptの文言を`inspect.getsource`等で検証している既存テスト）を再実行し、
   文言変更（「上記」→見出し名）で既存の文字列一致アサーションが壊れていないか確認、
   壊れていれば新しい文言に合わせて更新する。
6. フルオフラインスイート実行（既知のBL-269系汚染以外に新規failが無いことを確認）。
7. **実LLM検証（§17.2：モックテストは動作の証明にならない）**：コード変更後、次回の
   ドライラン（またはユーザーの許可を得て短時間の実行）でDetectorの実際の判定挙動
   （BL-087/266/278/306/292の各チェック）が書き換え前と同等に機能していることを目視確認する。
   これはこのセッション内では実施せず、次回ドライラン時の宿題として`issue_backlog.md`に
   明記する（プロンプト文言変更は静的テストだけでは実際の判定品質への影響を検証しきれない
   ため）。
8. 実装後、`docs/design/back_log/issue_backlog.md`にBL-312を記載、`decision_log.md`へ
   決定を記録する。

## 実装結果（2026-08-30 追記）

計画通り実装し、コミット`af7719d`で確定済み。実測値：
- domain_prompt共通接頭辞: 6687字 → **9188字**
- numeric監査prompt共通接頭辞: 7177字 → **8278字**

テスト6件新規（`tests/test_bl312_detector_prompt_cache_prefix.py`）・既存3ファイル
（`test_bl104_project_plan_toc_and_prompt_reorder.py`・
`test_bl164_recent_decisions_no_raw_reasoning_leak.py`・
`test_bl306_selection_sufficiency_label_check.py`）の文言更新、§17.1のstash検証
（6件中4件が旧コードで正しく失敗）、フルスイート2010 passed / 0 failedで確認済み。
実LLM挙動への影響確認は次回ドライラン時の宿題として残存（issue_backlog.md BL-312参照）。

決定記録: `docs/design/decision_log.md` D-267。
