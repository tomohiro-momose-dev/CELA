# BL-126/BL-130/BL-131 基本設計 レビュー結果

## レビュー対象
- `docs/design/back_log/BL-126/BL126_basic_design.md`（106行）
- `issue_backlog.md` BL-126/130/131エントリ
- `cela_main.py`（8055行）の関連コード

## 総評

設計の品質は高い。問題の切り分け（BL-086ツール群の実態調査、facilitator_nodeの実際の振る舞い、write_agreementのtask_id検証欠落）は正確で、根拠となるコード行番号も現状コードと整合している。実装順序の段階化（Stage A→B→C→D）も妥当。以下、抜け・バグ・気づきを列挙する。

---

## 1. LineageStateへの新規フィールド（設計§1）— 抜け・バグ

### 1.1 `essence_dialogue_active`の初期値未定義

設計書に「いずれも`LineageState`へ明示的に宣言必須」と書かれているが、フィールド宣言のみで初期値が未定義だと、LangGraphのTypedDictが`total=False`でない限りデフォルト値なしで参照エラーが起きる。現状の`LineageState`定義（3862行目）はTypedDictで、すべてのフィールドが必須（`total=True`がデフォルト）。BL-038の教訓（未宣言キーは伝播しない）は正しいが、宣言そのものが不足しているのではなく**デフォルト値の不在**がもう一つの問題。

**改善案**: `LineageState`の各フィールドに`total=False`を指定するか、初期state生成箇所（7835行目付近）で全フィールドにデフォルト値を明示する。設計書の「未宣言キーは伝播しない」に加え「TypedDictに`total=False`が必要か否か」の確認を追記すべき。

### 1.2 `essence_dialogue_active`と`escalation_active`の役割衝突

`essence_dialogue_active`（本質対話モード中フラグ、新規）とBL-096で既に存在する`escalation_active`（issue escalation中フラグ）は、どちらもFacilitator↔User AIの特殊モードを表すが、同時に`True`になる可能性がある。両フラグが同時ONの場合の優先順位（escalation解決後にessence dialogueに入るのか、essence dialogue中にescalationを発火させてよいのか）が未定義。

**改善案**: 状態遷移図または優先順位ルールを設計書に追記する。

### 1.3 `phases_superseded`の型が不完全

`phases_superseded: list[dict]`と定義されているが、具体スキーマが`{"task_id, reason, superseded_at_round, superseded_by_task_id}`という記述（設計§6）は白色化（ホワイトボード化）されたtask_idの追跡には有用だが、`phase_id`が含まれていない。task_idだけではフェーズを超えたsupersedeの追跡が不完全。

### 1.4 `pending_task_ids`の整合性リスク

Facilitator対話中に`pending_task_ids`として仮登録されたtask_idを、Task Plannerが正式採用/却下する仕組みは書かれているが、「Task Plannerが採用したtask_idが`pending_task_ids`に**存在しなかった場合**」のエラーハンドリングが未定義（Task Plannerが全く新規のtask_idを発明する可能性）。

---

## 2. 新規/変更ツール（設計§2）— 気づき

### 2.1 `PROPOSE_ESSENCE_DIALOGUE_TOOL`のスキーマ未記載

新規ツール名は挙がっているが、パラメータ・`description`・権限ロール（誰が呼べるか）が設計書に一切記載されていない。14パラメータを持つ`WRITE_AGREEMENT_TOOL`との整合性（例えば`PROPOSE_ESSENCE_DIALOGUE`は`WRITE_AGREEMENT`の特殊形として実装できないか）が検討されていない。

**改善案**: 低コスト実装として、`WRITE_AGREEMENT_TOOL`の`entry_type`に`"EssenceProposal"`を追加し、既存のagreementsテーブルをそのまま再利用する案を検討する（新規テーブル不要）。設計§4のgoal_draftsも同様の系統の変更。

### 2.2 `ask_user_question`（Expert用）のツール名が未確定

設計§2では「`ask_user_question`（Expert用、新規）」と書かれているが、命名規則が他ツール（`ESCAPATE_PREMISE_CONCERN_TOOL`等、スネークケース大文字）と統一されていない。また、`expert_consultation_mode`フラグと`expert_pending_question`文字列を同一ツールでセットする設計は妥当だが、**既存のDetector軽量パスとの分岐**がBL-126_basic_design.mdだけでなくBL-130との関連で重複定義されていないか確認が必要。

### 2.3 `revise_goal`の`source=="essence_dialogue"`検証が未実装

「`new_text`が`old_text`を包含する（純粋追記）ことを検証する」と書かれているが、`_apply_text_edits`（現状cela_main.py:約9000行目付近）にこの包含検証ロジックが現状存在するか未確認。実装時に確実に追加すること。

---

## 3. グラフノード・ルーティング（設計§3）— 設計上のバグ

### 3.1 **新規ループエッジ`facilitator ⇄ generate_user_utterance`の既存ルーティングとの衝突（重要）**

設計§3は「`facilitator_node`をツールループ化し、**新規ループエッジ`facilitator ⇄ generate_user_utterance`**を追加」と述べている。現状の`route_after_facilitator`（7770行目）は以下の4分岐：
- `"halt"` → halt_nodeへ
- `"route_after_reflection"` → reflectionへ
- `"integrator"` → integratorへ
- `"generate_user_utterance"` → generate_user_utteranceへ

このうち`"generate_user_utterance"`分岐は既に存在し、FacilitatorからUser AIへ直接戻る経路も現状でも可能。設計書はこれを「既存のエッジ」と認識するのか「新規に追加するエッジ」と認識するのか曖昧。本設計の実質的な新規性は「Facilitatorがツールループ化されるため、`generate_user_utterance`→`facilitator`への逆方向エッジが新たに必要になる」という点にあるが、この逆方向エッジのルーティング条件が設計書に明記されていない。

**改善案**: 逆方向エッジのルーティング判定（`essence_dialogue_active == True`ならfacilitatorへ、そうでなければ別のノードへ）を明確に記述する。

### 3.2 `facilitator_node`のツールループ化と`facilitation_count>3`の関係

現状の`facilitator_node`（7288行目）は`facilitation_count += 1`した後、`facilitation_count > 3`なら`state["halt"] = True`をセットする。ツールループ化後もこのhalt制限が適用されると、Expert/User AIのような複数ツール呼び出しができるようになったFacilitatorが、1回のノード実行で複数ツールを呼び出そうとすると、1回目のツール結果を受け取った時点でhaltされるリスクがある。ツールループ内の1回のAPI応答はノード境界をまたがない（同一`_query_AI_live`内）ため、設計書の想定通りhaltは発生しないが、暗黙的な依存であり注意書きが必要。

### 3.3 `goal_revision_pending_review`→ Detector目標変更レビュー→`task_planner_node`の経路がDetectorの戻り値を無視している

設計§3は「承認後`plan_revision_reason`をセットしtask_planner_nodeへ」とあるが、Detectorの目標変更レビュー結果が`major`（却下）だった場合のルーティングが未定義。現状のDetectorは`major`を返すと差し戻しルートへ進むが、ゴール変更レビューモード（`review_mode="goal_change"`）ではUserへ差し戻すのか、Facilitatorへ戻すのか、そのまま通すのかが決まっていない。

---

## 4. goal_drafts（設計§4）— 既存コードとの整合性

### 4.1 `apply_goal_patch`関数が現状存在しない

設計書は「`apply_whiteboard_patch`/`apply_plan_patch`を直接テンプレートとする」と書いているが、実際のcela_main.pyで`apply_goal_patch`はgrepにヒットしなかった。新規追加が必要。同様に`get_latest_goal_draft`も存在しない。

### 4.2 `state["goal"]`の全9消費者の特定が不十分

設計§4は「`state["goal"]`は9箇所の消費者が毎ターン再埋め込みする」と書いているが、具体的な9箇所のリストは設計書にもissue_backlog.mdにも記載されていない。実装時に漏れなく特定し、コメントで列挙することが望ましい。

---

## 5. Detector目標変更レビューモード（設計§5）— 気づき

### 5.1 `review_mode`パラメータのデフォルト値

`review_mode: Literal["task_output", "goal_change"]`パラメータにデフォルト`"task_output"`を指定する方針は妥当。ただし、`call_detector`関数（4784行目）の引数リストが既に6個以上のパラメータを持っており、更に増やすと可読性が低下する。既存の`target_role`と同じキーワード引数方式でよいか、`kwargs`の棲み分けを決めておく。

### 5.2 目標変更モードの判断基準第4項目（「数値的最適性は評価しない」）のリスク

「新しい目標文の数値的な最適性そのものは評価しない」というガードレールは妥当だが、ユーザーが提起した懸念（BL-119）に書かれている通り、「過去のターンで登録済みの内容を今回success=0と誤判定しない」という罠と同根の問題がDetector側で発生するリスクがある。目標変更レビューモード導入時は、BL-119と同様の罠説明をプロンプトに追加することを推奨する。

---

## 6. Task Plannerのラン途中再構成（設計§6）— 設計上の課題

### 6.1 ガード緩和の多重発火リスク

ガードを`if (turn_count==1 and not phases) or state.get("plan_revision_reason")`に緩和すると、Task Plannerの再構成中に再度`plan_revision_reason`がセットされるケース（無限ループ）を防ぐため、設計書では「消費後は即クリア」としている。しかし現状の`plan_reviewer_feedback`クリアロジックが実際に動作しているか確認したところ、task_plan_reviewer_node（6708行目）ではクリアしているが、チェックポイント再開時・グラフノードの再実行時にクリア漏れが起きない保証はない。

**改善案**: `plan_revision_reason`のクリアをTask Plannerノードの先頭（ガード判定直後）に移動し、確実に1回のみ消費されるようにする。

### 6.2 SUPERSEDE監査証跡のwrite_agreementとの重複

設計§6で「該当task/phaseは`state["phases_superseded"]`へ記録し、`write_agreement(action_type="SUPERSEDE", ...)`で監査証跡を残す」とある。しかしBL-080の教訓として、`entry_type="Deliverable"`のSUPERSEDEは既に`apply_whiteboard_patch`でホワイトボードを更新するパスが存在する。Task Plannerのsupersedeが`entry_type`として何を指定するのか（DeliverableかDirectiveか新規エントリタイプか）が未定義。

---

## 7. Reflection迎合監査基準（設計§7）— 気づき

「判断基準ベースの新パラグラフ」を追加する方針はBL-119のトレンドに沿っており妥当。ただし、現状の`call_reflection`（5594行目）は出力パース失敗時のfallbackが`stagnant`固定であり（BL-120）、このfallback自体が単なる安全側フォールバックではなく実害を生んでいる。迎合監査基準を追加する前に、BL-120のパース失敗問題を修正するか、少なくとも依存関係を設計書に明記すべき。

---

## 8. 実装順序（設計§8）— 重要な依存関係の欠落

### 8.1 BL-131とBL-120/BL-121の依存

設計§8はBL-131を「最小・独立」として最初に着手するとしているが、`write_agreement`のtask_id検証は、Facilitatorが発明する`task_1_1_review`等の非正規task_idをブロックするために機能しなければならない。しかし現状の`_CURRENT_TASK_ID`はFacilitatorノードでは適切に設定される保証がない（BL-132でdetector_nodeの全履歴再出力が修正された後、次に確認すべきはfacilitatorノード内のtask_id設定の一貫性）。BL-131単独で着手可能という前提は、facilitatorのtask_id状態が常に正しいことを暗黙に仮定している。

### 8.2 BL-132がBL-126の前提

BL-132（detector_nodeの全履歴再出力バグ）はBL-126の「Detector目標変更レビューモード」に影響する。detector_nodeが全履歴を再出力し続ける限り、目標変更レビューが出力パースやプロンプト長の面で不安定になる。BL-132は`done`だが、BL-126のStage B着手前にBL-132適用後のドライランで安定性を確認すべき。

---

## 9. 未定義のエッジケース

### 9.1 Essence Dialogue中に他のノード（Reflection/Facilitator/Facilitator自身）が発火した場合

`essence_dialogue_active=True`の間に、外側のwhileループが`round_count % reflection_interval == 0`でReflectionを発火させようとした場合の挙動が未定義。Essence Dialogueを優先してReflectionをスキップするか、Essence Dialogueを中断してReflectionを先に通すか。

### 9.2 `essence_dialogue_max_rounds`到達後の収束失敗

上限到達時にFacilitatorの提案がUser AIに承認されず、`pending_goal_revision`もセットされなかった場合の挙動が未定義。単に`essence_dialogue_active=False`に戻して通常フローに復帰するのか、強制的に収束方向へ誘導するのか。

---

## 10. 設計書内の非対称性・古い前提

### 10.1 `FREEZE_AGREEMENT_TOOL`の記述がD-045の決定と矛盾

設計§Contextで「`FREEZE_AGREEMENT_TOOL`はD-045によりどのノードにも配線されていないデッドコード」と書かれているが、BL-086の実装で既にUser AIのツールリストに再配線済み（6256行目: `tools=[..., FREEZE_AGREEMENT_TOOL, ...]`）。設計書がBL-086の実装よりも前に書かれたことを示しているが、読者が現状コードと照合した際に混乱する。

### 10.2 `facilitation_count>3`のリセット

設計§Contextで「Facilitatorはツールを一切持たない（自由記述のみ）」と書かれているが、これは現状のコード（7288行目）の正確な記述。ただしBL-126の本質対話ループでFacilitatorがツールループ化された後、`facilitation_count`カウンタのリセットタイミングが設計書にない。Facilitatorのツールループ内で複数回`facilitator_node`が発火するため、現状の`facilitation_count>3 → halt`ロジックはEssence Dialogueの進行を途中で停止させる可能性がある。

---

## 11. 確認事項への回答（設計§「残る要確認事項」）

設計書は3つの確認事項を挙げている：

1. **`essence_dialogue_max_rounds`の具体的上限値**: P2優先度のBL-126としては**5回**を提案する。BL-087 Stage2のtask_plan_reviewer差し戻し上限2回という先例があり、対話モードはそれより多いリトライ予算が必要だが、過剰な上限はStagnant判定を遅らせる。

2. **目標変更レビューモードを既存の反応的`revise_goal`経路にも適用するか**: **適用すべき**（新しいプロアクティブ経路のみに限定しない）。適用しない場合、BL-086経由の`revise_goal`（現状の反応的経路）を通ったゴール変更がDetectorの監査を素通りする非対称が生じる。

3. **ラン途中再構成が`task_plan_reviewer_node`を通るかスキップするか**: **通すべき**（スキップしない）。ただし、Task Plannerの再構成後の計画がTask Plan Reviewerで再度差し戻される無限ループを防ぐため、**再構成のリビジョン番号をカウントし、上限（例: 2回）を超えた場合は差し戻し指摘が残っていても承認する**（task_plan_reviewer_nodeの既存差し戻し上限ロジックと同型）。

---

## 12. 全体的な改善提案

### 12.1 状態遷移図の欠如

BL-126の本質対話ループは複数の状態（`essence_dialogue_active`/`pending_goal_revision`/`goal_revision_pending_review`）が連鎖するため、Mermaid等の状態遷移図を設計書に追加することを推奨する。

### 12.2 BL-096との統合を設計書に明記

`issue_log`（BL-096）と`essence_dialogue`（BL-126）はどちらも「未解決のまま後続に引き継ぐ情報」であり、統合の余地がある。例えばEssence Dialogueで出た議論の一部は`issue_log`に書き込まれてもよい。現設計書では一切触れられていない。

---

## まとめ

| 分類 | 件数 | 重要度 |
|------|------|--------|
| **設計上のバグ（実装前に修正必須）** | 2件 (§3.1, §3.3) | 高 |
| **抜け（実装時に補完が必要）** | 5件 (§1.1, §1.2, §2.1, §6.1, §6.2) | 中〜高 |
| **気づき（実装時に参照）** | 7件 (§2.2, §4.1, §5.2, §7, §9.1, §9.2, §12.1) | 低〜中 |
| **確認事項への回答** | 3件 (§11) | - |

全体として設計の方向性は正しく、BL-126/BL-130/BL-131のスコープは実運用上の問題（`task_1_1_review`の際限ないバージョン積み上げ、Facilitatorのツール不在、task_id検証欠落）を的確に捉えている。上記の修正点を反映した上で、実装順序に従ってStage 1（BL-131）から着手可能。