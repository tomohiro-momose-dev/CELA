# R5 詳細設計書: 新規要件群（思考ログ監査 / Freeze / GoalShiftEvent）
# (Cognitive Experience Lineage-driven Agent System - Refactor R5)

> **目的**: 要件定義書の実証実験（付録A）から新たに生まれた要件（F-2.1拡張、F-3.7、F-8.3、GoalShiftEvent）を、R1〜R4完了後の既存プロトタイプに追加する。
> **最終更新**: 2026-07-23（v2本文は2026-07-17時点のまま維持し、それ以降に判明したBL-041/048/050/051/061等との整合を各節に★2026-07-23追記として反映）

**★2026-07-23追記（前提の更新）**: 本書v2の作成後、R5着手前のBL棚卸し（[issue_backlog.md](../back_log/issue_backlog.md)、[decision_lineage.md 論点57・58・59](../decision_lineage.md)）により、本書が前提としていた既存コードの一部が変化した。特に重要なのは、4節GoalShiftEventが依存する`arbiter_node`が、BL-041のMVP実装（D-042）により**実際に発火するようになった**こと（従来は`state["global_constraints"]`が常に空で死んだコードパスだった）。各節の該当箇所に個別の追記を残す。

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

**★2026-07-23追記（BL-050との関係）**: BL-050（`partial`）が、本節と隣接する「決定事項の変遷履歴の可視化」を先行して一部実装済み。`_build_agreements_context`に、同一topicの直前Superseded版の内容・`reason_why`を差分表示する仕組み、および現行行自身の`reason_why`表示を追加した（D-050関連コミット、`tests/test_bl041_bl050.py`）。あわせて`WRITE_AGREEMENT_TOOL.reason_why`とdecision_extractor抽出プロンプトに、UPDATE時は「前の値から何故変わったか」を明記するよう要求する文言を追加済み。ただしBL-050自身の完了条件3番目（`decision_extractor`の役割転換：抽出役→理由監査役）は、BL-037の既存の決定通り**本節（F-3.7）の実装に合わせて具体化する**方針のまま据え置かれている。F-3.7に着手する際は、この役割転換をあわせて設計すること（BL-050を読み直したうえで、思考ログの強制記録と理由監査役の両方を一体で設計するのが望ましい）。

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

**★2026-07-23追記（実装との乖離を修正）**: 本節が前提としていた`assemble_hydrate_context`という関数名・生SQLクエリ（`WHERE status IN (...) ORDER BY timestamp ASC`）は、現行コードには存在しない。実際に`【決定事項DB】`のコンテキストを組み立てているのは`cela_main.py`の`_build_agreements_context`（`agreements: list[Agreement]`を受け取り文字列化するPython関数）と、そのDB版ラッパー`_build_agreements_context_from_db`である。DB層（`get_agreements_from_db`）はrun_id一致の全行を素通しで取得するのみで、`status`によるSQL側の絞り込みは行っていない。絞り込み（`status != "Superseded"`かつ`entry_type != "Directive"`）は`_build_agreements_context`内のPythonリスト内包表記で行われている。以下の実装方針は、この実際の構造に合わせて更新したものであり、以下が本節の設計として有効な内容である。

```python
# 修正前（現行実装、cela_main.py::_build_agreements_context）:
decisions_and_deliverables = [
    a for a in agreements
    if a.get("entry_type", "Decision") in ("Decision", "Deliverable")
    and a.get("status") != "Superseded"
    and a.get("entry_type") != "Directive"
]
# → timestamp/挿入順のまま（is_frozenは考慮されない）

# 修正後（★R5、Freeze実装時）:
decisions_and_deliverables = [
    a for a in agreements
    if a.get("entry_type", "Decision") in ("Decision", "Deliverable")
    and a.get("status") != "Superseded"
    and a.get("entry_type") != "Directive"
]
decisions_and_deliverables.sort(key=lambda a: (not a.get("is_frozen"), a.get("timestamp", 0)))
# is_frozen=1の項目をFalse(0)扱いでソートキー先頭に、それ以外はtimestamp昇順のまま
```

SQL側でのフィルタ・ソートではなく、既存のPython側リスト処理にキーを1つ追加するだけで済む（SQLクエリの変更は不要）。

**設計判断の理由**: `chat_history_window`や`expert_history_window`によるトリミング（既存コードの`_build_hydrate_context`、decisions専用の別関数）は直近N件を対象とするため、古いFrozen項目が窓の外に押し出されるリスクがある。Frozen項目は件数を問わず常に全件をHydrateコンテキストに含める例外処理とする（この方針自体はv2から変更なし）。

**未決事項（追加）**: BL-050で`_build_agreements_context`に追加された「直前Superseded版の差分表示」機能との相互作用が未設計。Frozen（凍結）されたagreementがSUPERSEDEの対象になった場合（現状、`freeze_agreement`は`is_frozen`フラグを立てるのみで、SUPERSEDE自体を禁止するガードはどこにも存在しない）にどう扱うか（そもそもFreeze済み項目のSUPERSEDEを拒否すべきか、許可した上で旧Frozen版も差分表示に含めるか）は、F-8.3の実装着手時に別途設計判断が必要。

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

**★2026-07-23追記（前提の刷新）**: 本節v2執筆時点（2026-07-17）では、`arbiter_node`は`state["global_constraints"]`が常に空リストのまま（実データを集約する処理自体が存在しなかった）だったため、**一度も発火し得ない死んだコードパス**だった（BL-041、実ドライラン全文検索で`[Resource Arbiter]`0件を確認済み）。R5着手前のBL棚卸しでこれを解消し（BL-041 MVP実装、D-042）、`arbiter_node`は現在、`agreements.resource_claims`から動的に集約された実データに基づき実際に発火する（`tests/test_bl041_bl050.py`のオフラインテストで超過検出→`call_resource_arbiter`到達を確認済み。実ドライランでの発火自体はまだ未確認）。

このMVP実装にあわせて`resource_claims`のスキーマも変更されている（D-042）。旧形式`{"予算": 1000000}`（平坦な`{名前: 数値}`）から、`{"予算": {"phase_id": "task_1_1", "value": 60000000, "total_cap": 100000000}}`という入れ子構造に具体化された。本節4.1のGoalShiftEventスキーマにある`from_goal_state`/`to_goal_state`（`state["global_constraints"]`のJSON化）は、この新スキーマを前提に実装すること。

以下、v2執筆時点の記述（GlobalConstraint超過時の再配分案を提示する箇所は、ゴールそのものの変容（ピボット）ではなく、フェーズ間の資源再配分に留まるという整理）は現在も有効である。GoalShiftEventが実際に発火すべきは以下のようなケースである。

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

**未確定事項**: 現状の`call_resource_arbiter`のプロンプト・戻り値スキーマには`requires_goal_constraint_change`に相当するフィールドがない。本フィールドを追加するプロンプト変更が必要（4.3節参照）。★2026-07-23追記: `arbiter_node`自体の発火（4.2節参照、BL-041 MVP実装）は解消済みのため、GoalShiftEvent実装における残る未確定事項は実質この1点（`requires_goal_constraint_change`フィールド追加）と、4.1節の`goal_shift_events`テーブル自体の新規作成・`detect_goal_shift`の配線のみになった。

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

**★2026-07-23追記（実装完了）**: 本節が挙げていた1.2節・4.2〜4.3節の追加実装は、[cela_r5_impl_Plan.md](cela_r5_impl_Plan.md)に基づき実装完了した（BL-063、D-044）。`_query_AI_live`のreasoning捕捉（`get_last_reasoning_text()`）、`call_detector`への思考プロセス監査ブロック配線、`make_decision`のinternal_thought_process限定記録（F-3.7）、`freeze_agreement`/`FREEZE_AGREEMENT_TOOL`（F-8.3、userロール限定）、`goal_shift_events`テーブル・`requires_goal_constraint_change`・`detect_goal_shift`（GoalShiftEvent）を実装。新規`tests/test_r5_thought_log_freeze_goalshift.py`（14件）含めオフラインスモークテスト計96件Pass。実LLM再ドライランでの効果確認（Detectorの思考プロセス監査の実際の発火、Freeze運用、GoalShiftEventの実発火）は次回待ち。

- ~~1.2節：使用プロバイダが思考ログ（reasoning_content相当）を返すかどうかの実機確認が必要。~~ → 実装完了（コードとしては`getattr(delta, "reasoning", None)`で対応済み。プロバイダが返さない場合は「(思考ログ取得不可)」表示にフォールバックする設計のため、機能停止はしない。実際にreasoningが返るかの実機確認は次回ドライラン待ち）。
- ~~4.2〜4.3節：`call_resource_arbiter`の戻り値スキーマ拡張（`requires_goal_constraint_change`）の追加実装が必要。~~ → 実装完了。`arbiter_node`自体が発火しないという根本的な前提の欠落はBL-041 MVP実装（D-042）で既に解消済みで、本フィールド追加と`goal_shift_events`テーブル・`detect_goal_shift`もBL-063で実装完了。
- 5節：思考内エージェント化ループは本フェーズでは実装しない設計検証のみ（変更なし、引き続き対象外）。

**★2026-07-23追記（BL-041の残スコープとの切り分け）**: BL-041の既存ドラフト（[cela_facilitator_arbiter_redesign_BL041.md](../r1_r2_r3b_core/cela_facilitator_arbiter_redesign_BL041.md)）が提案する4段階エスカレーションメニュー（Substitute/Descope/Force Decision/そもそも論への昇華）・facilitatorの3段階制御再設計・BL-005の`turn_count`根本修正は、R5着手前のMVP実装ではスコープ外として明示的に見送られている（[decision_lineage.md 論点58](../decision_lineage.md)）。これらはGoalShiftEvent（本書4節）の実装には必須ではないが、ドラフト§3.2の「そもそも論への昇華」（stage 4）はGoalShiftEventの`shift_kind="architecture_pivot"`/`"silent_drift"`と概念的に重なる。両ドキュメントが将来的に乖離しないよう、GoalShiftEvent実装時にはドラフト§3.2を必ず参照し、二重設計にならないよう注意すること。
- BL-061（facilitatorがreflectionの判定理由を受け取れなかったバグ）も、1.4節に記載の通り本書1節（F-2.1）実装時の設計上の教訓として参照すること。
