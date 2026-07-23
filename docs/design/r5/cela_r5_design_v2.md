# R5 詳細設計書: 新規要件群（思考ログ監査 / Freeze / GoalShiftEvent）
# (Cognitive Experience Lineage-driven Agent System - Refactor R5)

> **目的**: 要件定義書の実証実験（付録A）から新たに生まれた要件（F-2.1拡張、F-3.7、F-8.3、GoalShiftEvent）を、R1〜R4完了後の既存プロトタイプに追加する。
> **最終更新**: 2026-07-23（v2本文は2026-07-17時点のまま維持し、それ以降に判明したBL-041/048/050/051/061等との整合を各節に★2026-07-23追記として反映）

**★2026-07-23追記（前提の更新）**: 本書v2の作成後、R5着手前のBL棚卸し（[issue_backlog.md](../issue_backlog.md)、[decision_lineage.md 論点57・58・59](../decision_lineage.md)）により、本書が前提としていた既存コードの一部が変化した。特に重要なのは、4節GoalShiftEventが依存する`arbiter_node`が、BL-041のMVP実装（D-042）により**実際に発火するようになった**こと（従来は`state["global_constraints"]`が常に空で死んだコードパスだった）。各節の該当箇所に個別の追記を残す。

---

## 0. 前提の確認：既存の二重防衛線（旧Phase 3相当）は新規設計不要

旧ロードマップv23のPhase 3「二重防衛線ガバナンスの本格化」は、既存プロトタイプの`call_detector`（`target_role`によるUser/Expert別チェック基準）として**既に実装・動作確認済み**である（要件定義書付録B参照、過去の運用ログ監査セッションで高精度を確認済み）。したがって本節は新規実装ではなく、以下2点の確認作業のみを行う。

1. R1（SQLite化）後も、`call_detector`のロジック自体（`role_specific_instruction`の分岐）が変わらず機能することの回帰テスト。
2. R2で追加した機械的検算ゲート（F-2.6）が、既存のrisk/constraint_issue判定と正しく併存すること（検算結果をDetectorのプロンプトにどう合流させるかは本書2節で設計する）。

**★2026-07-23追記**: `call_detector`はその後BL-049/BL-054（D-041）により、数値検算パス（本節が前提とする既存ロジック）とは独立した「ドメイン妥当性レビュー」パスが追加され、ドメイン監査→数値検算の順で2段構成に変わっている（判定は両パスのうち重い方を採用、統合ロジックは維持）。本節が言う「既存の二重防衛線」は現在もこの2段構成の中に生きているが、`role_specific_instruction`単体ではなく2パスそれぞれに分岐が存在する点は把握しておくこと。

---

## 1. F-2.1拡張：思考プロセス監査

### 1.1 現状の制約

既存の`query_AI`関数は`response.choices[0].message.content`のみを返しており、モデルの思考過程（reasoning/thinkingトークン）を個別に取得する構造がない。`reasoning_effort`パラメータは指定しているが、その内容を後段のDetectorに渡す経路が存在しない。

### 1.2 設計変更

```python
def query_AI_with_reasoning(messages: list[dict], client: OpenAI, model: str, label: str = "Unknown Node") -> dict:
    """
    既存のquery_AIを拡張し、reasoning_content（プロバイダがサポートする場合）と
    最終出力を分離して返す。
    """
    # ...既存のリトライ・エラーハンドリングロジックは流用...
    response = client.chat.completions.create(**create_kwargs)
    choice = response.choices[0]
    content = choice.message.content
    # OpenRouter経由のreasoning modelはmessage.reasoning等のフィールドを持つ場合がある
    reasoning = getattr(choice.message, "reasoning", None) or getattr(choice.message, "reasoning_content", None)
    return {
        "content": content if content is not None else "(APIから空の応答が返されました)",
        "internal_thought_process": reasoning or "(思考ログ取得不可)"
    }
```

**注記**: 使用プロバイダ（OpenRouter経由の`deepseek-v4-flash`）が思考ログを返すかは、実運用で個別に確認する必要がある。返さない場合、本節はモデル・プロバイダの選定と合わせて再検討が必要（未確定事項として3節に記載）。

### 1.3 Detectorへの思考ログ監査プロンプト追加

```python
# call_detector内、role_specific_instructionへの追加
thought_process_audit = f"""
【思考プロセス監査（★R5追加）】
以下はExpert/User AIの内部思考過程（internal_thought_process）です。
最終出力の内容だけでなく、この思考過程も確認してください。
- 「計算ツールを使っていないのに適当な数字を出している」
- 「都合の悪い制約から意図的に目を逸らして結論を急いでいる」
このようなAIの事後正当化（取り繕い）が見られる場合、重度のハルシネーションと
判定して強制差し戻し（major）としてください。

【重要な限界（要件定義書付録A.5より）】
ただし、思考ログ内で正しく検算していたとしても、それを読むあなた自身も
LLMである以上、暗算による検証には誤りのリスクが伴います。数値的主張の
妥当性は、本監査だけに依拠せず、必ずF-2.6の機械的検算ゲート（Python REPL
による再計算結果）と突き合わせて判断してください。

【Expert/User AIの思考過程】
{internal_thought_process}
"""
```

### 1.4 ★2026-07-23追記：軽量版の先行実装とBL-061の教訓

本節のフル実装（`query_AI_with_reasoning`による`internal_thought_process`の正式なキャプチャ・配線）はまだ着手していないが、同じ「AIの気づき・判断過程を後続ノードへ渡す」という目的の軽量な代替が既に2件実装され、実運用で価値を確認している。

- **BL-048**（D-040）: `call_reflection`に、`internal_thought_process`ではなく既存の`chat_history`と`decisions`テーブルの決定タイムラインのみを材料にした軽量版「でっちあげ監査」プロンプトを追加済み。実ドライラン（`log/2026-07-23/1656`）で、Expertの与条件無断変更を実際に検出できることを確認済み（[decision_lineage.md 論点57](../decision_lineage.md)）。
- **BL-051**: `call_detector`の出力に`observations`（気づき・懸念の自由記述）を追加し、`state["detector_observations_log"]`として蓄積、後続ノードのプロンプトへ直近3件を常時提示する仕組みを実装済み。本節が目指す「思考プロセスそのものの監査」ではなく「判定結果に現れなかった気づきの保存」という、より狭いスコープの対策だが、Detectorがconstraint_issueの単一判定に握り潰していた懸念を拾えるようになった。

**設計上の教訓（BL-061）**: 本節のフル実装時は「思考ログをどこかに保存する」だけでは不十分であることに注意する。BL-061では、`reflection_node`がreflectionの判定理由（`note`）を`decisions`テーブルへは保存していたにもかかわらず、それを実際に消費すべき`facilitator_node`へは配線されておらず（`call_facilitator`の`decisions`引数がプロンプト内で完全に未使用というデッドパラメータだった）、facilitatorが独自に（時に矛盾する）判断をしてしまうバグが実ドライランで発生した（[decision_lineage.md 論点59](../decision_lineage.md)、D-043）。修正はBL-038の教訓（`LineageState`に未宣言のキーはノード間で伝播しない）に従い、`last_reflection_note`を`LineageState`へ明示的に宣言し、消費側ノードのプロンプトへ直接埋め込む形で行った。本節で`internal_thought_process`を配線する際も、「どのノードが実際にこれを読むのか」を先に特定し、そのノードのプロンプト構築コードに明示的に埋め込まれていることを個別に確認すること（保存箇所の存在だけでは配線の保証にならない）。

---

## 2. F-3.7：思考ログの強制記録（★v2で対象テーブルを両方に修正：Cline/hy3レビュー指摘⑨への回答）

`internal_thought_process`列は、`decisions`テーブルと`agreements`テーブルの**両方**に、既にR1の時点でNULL許容カラムとして先行追加済みである（Phase1〜R3設計書v6 §2参照）。したがって本節で必要なのは`ALTER TABLE`ではなく、**両テーブルへの書き込みロジックの実装**のみである。

```python
# decisions側（システム内部の判断ログ全般）
def make_decision(who: str, what: str, why: str | None, 
                   internal_thought_process: str | None = None) -> Decision:
    return {
        "id": f"D-{int(time.time() * 1000)}",
        "timestamp": time.time(),
        "who": who,
        "what": what,
        "why": why if why else "(Reason: Missing)",
        "reason_missing": why is None,
        "internal_thought_process": internal_thought_process or "(記録なし)",
    }

# agreements側（write_agreement_toolによる自律書き込み時）
# write_agreement_toolの引数（Phase1〜R3設計書v6 §3.2）に、思考ログを渡す経路を追加する。
# ツール呼び出し元（Expert/User AI等）が、直前の思考過程（reasoning_content等）を
# 自動的にツール引数へ埋め込む形とし、AI自身が明示的に指定する必要はない
# （システム側でツール呼び出しの前後関係から自動収集する）。
def write_agreement_tool_impl_with_thought(raw_args: dict, internal_thought_process: str | None,
                                             db_connection) -> dict:
    raw_args["internal_thought_process"] = internal_thought_process or "(記録なし)"
    return write_agreement_tool_impl(raw_args, db_connection)  # 既存のバリデーション・コミット処理を流用
```

**運用方針**: 全ての`decisions`/`agreements`レコードに思考ログを保存すると容量・トークンコストが肥大化するため、要件定義書付録A.6での議論を踏まえ、**Detectorが差し戻した際、Reflectionが停滞と判定した際、およびRejected判定が下された際にのみ**思考ログをスナップショット保存する限定運用とする（全件保存はN-3のトークン消費効率改善という非機能要件と矛盾するため）。

---

## 3. F-8.3：Freeze機能

### 3.1 スキーマ

R3で導入済みの`agreements`テーブルに、既に`is_frozen`カラムが存在する（Phase1設計書v2の2節参照）。本節ではその**運用ロジック**を設計する。

### 3.2 Freeze設定のトリガー

```python
def freeze_agreement(db_connection, agreement_id: str, reason: str):
    """
    人間、またはシステム（Arbiter等）が「絶対に覆してはならない決定」に
    フラグを立てる。
    """
    db_connection.execute(
        "UPDATE agreements SET is_frozen = 1 WHERE id = ?", (agreement_id,)
    )
    # Freeze自体も監査ログとして記録
    decision = make_decision(
        who="system_freeze", 
        what=f"Agreement {agreement_id} をFreeze（永久ピン留め）", 
        why=reason
    )
    # decisionsテーブルへ保存
```

### 3.3 Hydrateアセンブルへの反映

`assemble_hydrate_context`（R1〜R3設計書4.1節）のクエリを以下のように修正する。

```python
# 修正前（R1〜R3設計書）:
# "SELECT status, topic, decision_what, reason_why, evidence FROM agreements 
#  WHERE status IN ('Approved', 'Rejected') ORDER BY timestamp ASC"

# 修正後（★R5）:
agreements = db_connection.execute(
    "SELECT status, topic, decision_what, reason_why, evidence, is_frozen FROM agreements "
    "WHERE status IN ('Approved', 'Rejected') "
    "ORDER BY is_frozen DESC, timestamp ASC"  # Frozen項目を先頭に配置し、確実にコンテキストへ含める
)
```

**設計判断の理由**: `chat_history_window`や`expert_history_window`によるトリミング（既存コードの`_build_hydrate_context`）は直近N件を対象とするため、古いFrozen項目が窓の外に押し出されるリスクがある。Frozen項目は件数を問わず常に全件をHydrateコンテキストに含める例外処理とする。

---

## 4. GoalShiftEvent：ゴール変容監査

### 4.1 スキーマ（要件定義書付録より再掲）

```sql
CREATE TABLE IF NOT EXISTS goal_shift_events (
    shift_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    shift_kind TEXT NOT NULL,          -- scope_expand / narrow / architecture_pivot / constraint_hit / silent_drift
    from_goal_state TEXT NOT NULL,
    to_goal_state TEXT NOT NULL,
    reason_why TEXT NOT NULL,
    evidence TEXT,
    triggered_by TEXT NOT NULL,        -- MCTS_Fork_Result / Human_Override / OpportunityScout
    triggering_agreement_id TEXT
);
CREATE INDEX IF NOT EXISTS idx_goal_shift_kind ON goal_shift_events(shift_kind);
CREATE INDEX IF NOT EXISTS idx_goal_shift_timestamp ON goal_shift_events(timestamp);
```

### 4.2 既存プロトタイプでの発火ポイント

現状の`arbiter_node`（`call_resource_arbiter`）が、GlobalConstraint超過時の再配分案を提示する箇所は、ゴールそのものの変容（ピボット）ではなく、フェーズ間の資源再配分に留まる。GoalShiftEventが実際に発火すべきは以下のようなケースである。

```python
def detect_goal_shift(state: LineageState, arbiter_result: dict) -> dict | None:
    """
    arbiter_nodeの再配分案が、当初のcurrent_goalのabsolute_constraints自体を
    変更するレベルに達した場合（例: 予算上限そのものの見直しが提案された場合）、
    GoalShiftEventとして記録する。
    """
    if arbiter_result.get("requires_goal_constraint_change"):
        return {
            "shift_kind": "constraint_hit",
            "from_goal_state": json.dumps(state["global_constraints"]),
            "to_goal_state": json.dumps(arbiter_result["new_allocation"]),
            "reason_why": arbiter_result.get("rationale", ""),
            "triggered_by": "Arbiter_Resource_Overrun",
        }
    return None
```

**未確定事項**: 現状の`call_resource_arbiter`のプロンプト・戻り値スキーマには`requires_goal_constraint_change`に相当するフィールドがない。本フィールドを追加するプロンプト変更が必要（4.3節参照）。

### 4.3 `call_resource_arbiter`への追加指示

```
【ゴール変容の検知（★R5追加）】
提示する再配分案が、当初の絶対制約（GlobalConstraintのtotal_cap自体）を
変更する必要があると判断した場合、requires_goal_constraint_change: true を
含めて返答してください。単なるフェーズ間の配分見直し（total_capは維持）で
あれば false としてください。
```

---

## 5. F-5.5（思考内エージェント化ループ）：設計検証のみ

ロードマップv24の方針通り、本フェーズでは実装せず、設計検証のみ行う。

### 5.1 検証すべき前提

1. 使用プロバイダ（OpenRouter経由の`deepseek-v4-flash`）が、思考プロセスの途中で明示的に打ち切り可能な形式（例: マーカー文字列の検出によるストリーミング打ち切り）をサポートするか。
2. 情報収集フェーズ（軽量モデル）から最終出力フェーズ（中堅モデル）への引き継ぎ時、プロンプトサイズがどの程度になるか（既存の`MAX_TOKENS_BY_ROLE`設計との整合）。

### 5.2 実装判断の基準

要件定義書N-6（検証精度とトークンコストのトレードオフ）に基づき、以下を満たす場合のみR6以降で実装着手を検討する。

- R2（F-2.6検算ゲート）のトークンコスト増加（実測値：約4.5倍）を上回るコスト増加が見込まれないこと。
- 単一モデルでの思考ログ監査（本書1節）だけでは不十分な誤り検出パターンが、実運用ログで確認されること。

---

## 未確定事項まとめ

- 1.2節：使用プロバイダが思考ログ（reasoning_content相当）を返すかどうかの実機確認が必要。
- 4.2〜4.3節：`call_resource_arbiter`の戻り値スキーマ拡張（`requires_goal_constraint_change`）の追加実装が必要。
- 5節：思考内エージェント化ループは本フェーズでは実装しない設計検証のみ。
