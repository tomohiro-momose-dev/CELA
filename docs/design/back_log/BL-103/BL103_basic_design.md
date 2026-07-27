# BL-103: hydrate/ノード間コンテキスト引き継ぎの改善

関連: [issue_backlog.md BL-103](../issue_backlog.md#bl-103-hydrateノード間コンテキスト引き継ぎの改善)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は設計時点のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## Context

`_build_hydrate_context`（decisions要約）と`chat_history`窓（生ログ）によるノード間コンテキスト引き継ぎについて、ユーザーから「これで十分か・合理的か」と相談があった。過去にユーザー自身が設計した`C:\ai_work\NPU-Context-Saver`のhydrate機構（`HydrationManager.ts`/`HydrateSelection.ts`/`HydrateFiveSectionBuilder.ts`等）を調査し、対比した。

### NPU-Context-Saverとの対比で判明したCELAの現状

- `_build_hydrate_context`（cela_main.py:3872）は`decisions`テーブルの直近`expert_history_window`件（既定6）を機械的にスライスし、`who`/`what`/`why`（100文字truncate）を1行ずつ並べるだけ。窓の外は要約すら残らず消える。
- チャット履歴は`chat_history_window`（既定4）ターンを生のまま渡すのみ。
- NPUは「直近K件は生テキスト、それ以遠は5フィールド要約」という2層構造＋pin（重要ノードは常時残す）＋Time-Aware RAG＋トークン予算による段階的間引きという設計だった。

### 対比結果とユーザーの判断

1. **トークン予算制御（NPUの`packMaxEstTokens`相当）**: NPUはローカルSLMのcontext枯渇対策として導入したものであり、CELAでは不要と判断（ユーザー確認済み）。導入しない。
2. **RAGによる古い関連情報の再浮上**: CELAは`read_verified_fact`/`read_deliverable_file`/`read_issues`等のプル型ツールを既に持っており、代替として機能しているため見送り（ユーザー確認済み）。導入しない。
3. **重要情報のpin（recencyに関係なく常時提示）**: 低コスト・高効果としてユーザー承認済み。BL-096で新設した`issue_log`のescalated行（＝CELAにおける「絶対に忘れてはいけない懸念」の正式な登録簿）を、hydrate_contextへ常時マージする形で実現する。
4. **issue_logのescalated行をcall_expert/generate_user_utteranceのambient contextにも注入するか**: facilitatorのフィードバックは`chat_history`末尾に追記されるだけ（cela_main.py:7130-7136）なので`chat_history_window`（既定4ターン）を過ぎると跡形もなく消える。ambient注入は毎ターンDBから最新状態を取得するため常に最新かつ消えない。「二重に言う」競合ではなく「facilitatorの発言が古くなって消えた後の穴を埋める」役割と判断し、ユーザーは**詳細込みで注入**を選択。
5. **ノード最終thinkの永続化によるNターン生ログ／それ以前要約という二層構造の質向上**: ユーザー提案。現状、`decisions`テーブルの`why`は生テキストの先頭100文字を機械的に切っただけの劣化版要約（cela_main.py:6650）であり、要約の質が低い。BL-093で全ノードに既に必須化されている`think`ツールの最終呼び出し内容（`decided`/`why`）を代わりに使うことで、要約の質を上げる。「要約を何件で切るか」は既存の`expert_history_window`（config、既定6）をそのまま使い、新規のトークン予算制御は導入しない。

### 調査中に発見した追加の実バグ／欠落（本タスクのスコープに含める）

- **User AIの発言が`decisions`/hydrate要約チャネルに一切記録されていない**: `generate_user_utterance_node`（cela_main.py:6161）は`make_decision`を一度も呼んでいない。Expertの発言は（弱いながらも）記録されるのに、User AIの指示・訂正は要約チャネルから完全に欠落しており非対称。
- **`generate_user_utterance`内の独自インラインタイムライン構築が無制限（unbounded）**: cela_main.py:5840-5849で`get_decisions_from_db(...)`の**全件**を毎ターン展開しており、`expert_history_window`のような窓が一切効いていない。Expert側の`_build_hydrate_context_from_db`は正しく窓を効かせているのに、User AI側だけ無制限に肥大化する非対称な実装になっている。`call_reflection`内の同種のインラインタイムライン（cela_main.py:5466付近）は、reflectionが「定期的な全履歴監査」という別の役割を持つため意図的な全件表示とみなし、**対象外**とする（変更しない）。

## 設計

対象ファイルは`cela_main.py`のみ。新規テーブル・スキーマ変更は無し（既存の`decisions.why`は自由テキストであり、既存の`issue_log`/`_get_escalated_issues`をそのまま再利用する）。

### A. `get_last_think_summary()`の新設

`get_last_reasoning_text()`（cela_main.py:2214）と全く同じ「呼び出し直後にモジュールグローバルをキャプチャする」パターンで併設する。

- `_THINK_REASONING_LOG`（BL-093のthinkスクラッチパッド、cela_main.py:1015）の最後のエントリを見て、`decided`が非空ならそれ＋`why`を連結、空なら`summary`にフォールバック、スクラッチパッドが空なら空文字を返す。
- 呼び出しノード関数（`expert_node`/`generate_user_utterance_node`等）の末尾、その回の`query_AI`呼び出し完了直後・次のノードの`_reset_think_scratchpad()`が走る前に呼ぶ（`get_last_reasoning_text()`/`get_last_python_calls()`と同じ呼び出しタイミング）。

### B. 各ノードの`make_decision`呼び出しを改善

1. `expert_node`（cela_main.py:6650）: `why=(output or "")[:100]` を `why=get_last_think_summary() or (output or "")[:150]` に変更。
2. `generate_user_utterance_node`（cela_main.py:6161、`state["chat_history"].append(...)`の直後）: 新規に`make_decision(who="user", what=f"Expertへの発言（ラウンド{state['round_count']}）", why=get_last_think_summary() or user_input[:150])`を追加し`db_append_decision`する。

### C. `generate_user_utterance`のインラインタイムラインを共通のhydrate_contextへ置き換え、escalation pinも統合

cela_main.py:5840-5864の独自インラインループ（無制限件数）を撤去し、`_build_hydrate_context_from_db(_conn, state["run_id"], config)`（既存、`expert_history_window`で正しく窓を効かせる）の呼び出しに置き換える。これによりB.2で追加されるUser AI自身の決定も含め、Expert側と同じ窓・同じ要約ロジックで一貫した挙動になる。

新規関数`_build_escalation_pin_text(conn, run_id) -> str`を追加（`facilitator_node`内の既存フォーマットロジック、cela_main.py:7117-7122の`_get_escalated_issues`整形処理を共通化）。

`call_expert`（cela_main.py:4602付近）と`generate_user_utterance`（上記置き換え後の呼び出し）の両方で、hydrate_context文字列の直後に連結する:

```python
hydrate_context = _build_hydrate_context_from_db(_conn, state["run_id"], config)
escalation_pin = _build_escalation_pin_text(_conn, state["run_id"])
if escalation_pin:
    hydrate_context += f"\n\n【⚠️エスカレーション中の懸念（要対応、issue_log）】\n{escalation_pin}"
```

`call_orchestrator`（4331）には追加しない（今回のスコープはcall_expert/generate_user_utteranceのみというユーザーの指定に従う。orchestratorは専門家選定のみ行うノードで対象外）。ラベルはfacilitatorの穏やかな促し文体とは明確に区別し、「機械的な状態表示」として読めるようにする。topic・description・累積回数・raised_byを含むフル情報を载せる（ユーザーが選択した「詳細込みで注入」）。

## 完了条件 / 検証

1. `python -m py_compile cela_main.py`
2. 新規`tests/test_bl103_hydrate_context_improvements.py`:
   - `get_last_think_summary()`: decided優先・summaryフォールバック・空スクラッチパッドで空文字、の3パターン
   - `expert_node`が改善された`why`で`make_decision`を呼ぶこと（`inspect.getsource`または`monkeypatch`経由）
   - `generate_user_utterance_node`が新たに`make_decision`/`db_append_decision`を呼ぶこと
   - `_build_escalation_pin_text`がescalated行を整形して返すこと、無ければ空文字
   - `generate_user_utterance`が独自インラインタイムラインではなく`_build_hydrate_context_from_db`を呼ぶこと（無制限成長バグの回帰防止）
   - `call_expert`/`generate_user_utterance`のプロンプトにescalation pinブロックが連結されること
3. 関連クラスタ回帰: `pytest tests/ -q -k "bl096 or bl093 or bl061"`
4. `python scripts/check_docs_consistency.py`
5. 実LLM再ドライランでの効果確認は次回待ち。