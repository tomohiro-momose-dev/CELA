# BL-228 基本設計: 統一活動系譜（Unified Activity Lineage）— `chat_history` スパイン活性化 ＋ N/M 役割非対称要約 ＋ ターン内チューリン描画 ＋ Hydrate/trace の「本来の姿」統合

> **作成**: 2026-08-14（ユーザーとの対話中に設計。参考資料 `docs/refs/` の LDD/Lineage 研究が直接的な起源）
> **状態**: 設計完了・実装未着手（`open`）
> **保存根拠**: AGENTS.md §4.7（BL単位の設計は `docs/design/back_log/BL-xxx/` へ要約せず原文のまま保存）

---

## Context（なぜこの変更を行うか）

### 出発点 — CELA の原点は「判断の系譜」

ユーザーが提示した `docs/refs/` の参考資料（LDD README、hydrate-refresh-5-section-template.md、hydrate-index-expand-spec.md、lineage-human-intentic-spec.md、lineage-product-vision.md）は、CELA の設計哲学（AGENTS.md §4 の Decision Lineage）の**直接の起源**である。共通の筋:

- *"Git manages code lineage. LDD manages decision lineage."* — コードの系譜は Git が、決定の系譜は LDD が。
- Hydrate = 過去の決定系譜から文脈を再構築し、新しいチャットへ注入すること（**文脈移植**が本来の用途）。
- 参考資料の hydrate-refresh-5-section-template.md の **What/Why/Current/Open/Next の5節** が、CELA の F-8.2「Hydrate 5節」の正体。
- 参考資料の hydrate-index-expand-spec.md の **Zone A 生(N=10) / Zone B 可読(M=30) / Zone C 豊かな索引** の3段グラデーションが、ユーザーが提示した **N/M ティア要約** の原型。

### ユーザーの重要な補正（何度も繰り返された注意）

1. **5節テンプレートは「新規チャットへの文脈移植」用**。そのうち **Current/Open/Next は CELA では既にフェーズタスク・分解・User AI の進行管理・issue 等で代替されている**。だから BL-228 は 5節を再発明しない。
2. **「弱い部分」の指摘**: Open/Next のタスク進行は機械化されてきているが、**detector の差戻（rollback）が明確に登録されておらず、detector からの差戻文に基づいて User AI/Expert の思考で進捗が保たれている**。issue の open 消化も同様。この「detector 差戻 → 進行」の構造化こそが、BL-228 が解くべき本当の欠落。

### 実コード確認済みの事実（§14/§16.2: 証拠なき断言をしない）

| 観察 | 証拠（cela_main.py） | 意味 |
|------|----------------------|------|
| `chat_history` DB テーブルは**定義のみ・死蔵** | 5539行 `CREATE TABLE` のみ。INSERT/SELECT は 0件（grep で確認） | AGENTS.md §15.4「仕組みでない記録」の実例。活性化が本 BL の主目的 |
| 実会話は `state["chat_history"]`（in-memory LangGraph 状態） | 7241行 `chat_history: list[dict]`。8260/8708/11553/12231 等で多用 | 生会話バッファは checkpoint 状態 |
| 文脈は `chat_history_window=4` で**窓切り** | 14473行 `"chat_history_window": 4` | 直近4件しか文脈に残らない → 数ターン後は「調子」が失われる |
| 「raund」＝`round_count` | 7243行 `round_count: int  # generate_user_utterance_nodeへの再入場回数`。`turn_count` は凍結 | 発言ごとの単位は round_count |
| `whiteboard_drafts` は version 管理済み | 5524行（version INTEGER, content, author_role, edit_summary） | ターン内チューリン（detector の白紙編集）は**既に捕獲可能** |
| `issue_log` は構造化済みだが detector 差戻と弱結合 | 5607行（topic/raised_by/severity/status/acknowledged_until_round）。BL-194 が `acknowledged_until_round` を追加(5722) | issue は記録されるが、差戻との紐付けが「弱い」 |
| `goal_shift_events` は**実装済み** | 5554行 | ゴール移動監査は再発明しない |
| BL-227 は既に TOOL_CALL_RULE に割当済み | issue_backlog.md 7870行 | 本設計は **BL-228** とする（衝突回避） |

### 本設計のゴール

1. **死蔵 `chat_history` を活性化** — 全 append 点から DB へ書き、窓切り後も全文が残り系譜として辿れる。
2. **N/M 役割非対称要約** — 軽量/ローカル LLM へ委任し、トークン圧迫を抑えつつ「調子（どう一緒に考えていたか）」を保持。
3. **ターン内チューリン描画** — あるターンを起点に、detector の差戻を含む artifact 変化（agreement/entity/issue/whiteboard diff）を時系列で出す。
4. **Hydrate(C1) と trace(C5) を「本来の姿」に** — あるターン（AI の問い）を起点に過去文脈を能動取得。
5. **「弱い部分」の構造化** — detector 差戻を `is_rollback` フラグ＋`relation_edges` の `turn:` 外向きエッジとして系譜化し、進行が in-context 推論のみに依存する状態を解消。

---

## スキーマ

### chat_history テーブル拡張（既存 5539 を拡張）

```sql
-- [BL-228] 既存の死蔵 chat_history を活性化し、統一活動系譜のスパインとする。
-- 既存定義(id, turn, role, content, timestamp, run_id)に下記を追加。
-- turn = round_count（「raund」）。task_id/phase_id で artifact と結合。
-- summary_expert/summary_full は N/M 役割非対称ティア要約（軽量/ローカルLLM委任）の格納先。
-- is_rollback は detector 差戻の構造化（「弱い部分」の補強）。
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    turn INTEGER,                 -- = round_count（「raund」）
    task_id TEXT DEFAULT '',
    phase_id TEXT DEFAULT '',
    role TEXT,                    -- user / expert / detector / facilitator / ...
    content TEXT,                -- 生文（raw）
    summary_expert TEXT DEFAULT '',  -- 軽量/ローカルLLM要約（N/M ②で expert に使う）
    summary_full TEXT DEFAULT '',    -- さらに圧縮（N/M ③ >M ターン用）
    is_rollback INTEGER DEFAULT 0,  -- detector 差戻フラグ（1=差戻を含むターン）
    timestamp REAL
);
CREATE INDEX IF NOT EXISTS idx_chat_history_run_turn ON chat_history(run_id, turn);
CREATE INDEX IF NOT EXISTS idx_chat_history_run_task ON chat_history(run_id, task_id);
```

- ref 表記: `turn:{id}`（relation_edges 用。run_id スコープ内で一意）。

### relation_edges 拡張（BL-224 の基盤を再利用、§15.1 単一ソース）

BL-224 の `relation_edges`（`agreement:`/`fact:`/`entity:` の3プレフィックス）に以下を追加:

| プレフィックス | 指す先 | 存在検証 |
|----------------|--------|----------|
| `turn:<id>` | `chat_history.id` | ✅ 実表の行 |
| `issue:<topic>` | `issue_log.topic` | ✅ 実表の行 |
| `whiteboard:<phase_id>:<task_id>` | `whiteboard_drafts(phase_id, task_id)` の最新 version | ✅ 実表の行 |

主要な辺（すべて `run_id` スコープ）:

- `turn:<id>` → `agreement:<id>` / `fact:<name>` / `entity:<id>:<attr>` / `issue:<topic>` / `whiteboard:<phase>:<task>`
  — 「このターンで何が変わったか（または参照されたか）」
- `issue:<topic>` → `turn:<id>`
  — 「この issue が挙がった/消費されたターン」
- （BL-224 既存）`agreement:`/`fact:`/`entity:` 同士の `depends_on`/`supersedes`/`derived_from`

### 補足ソース（新設せず既存を活用）

- `whiteboard_drafts`（5524）: version 列でターン内チューリンを時系列取得。
- `issue_log`（5607）: 差戻との紐付け強化に利用。
- `goal_shift_events`（5554）: ゴール移動監査は既存。

---

## 書き込み経路（入口・AGENTS.md §15.4）

**原則: LLM の記入に依存しない機械的な骨格を先に**（§15.3）。

### W1: chat_history への書き込み（死蔵→活性化）

`state["chat_history"]` の**全 append 点**からフックして DB へ書く。§15.2「発生経路をすべて列挙」:

- `11553` `state["chat_history"].append({"role": "user", "content": state["user_input"]})`
- `12231` `state["chat_history"].append({"role": "assistant", "content": output})`
- `13371` `state["chat_history"].append({"role": "assistant", "content": feedback})`（facilitator）
- `13607` `state["chat_history"].append({"role": "user", "content": msg})`
- その他の append 点（grep `state["chat_history"].append` で全件洗い出し、各々から書く）

書く内容: `run_id, turn=round_count, task_id, phase_id, role, content, timestamp`。
要約（summary_expert/summary_full）は**非同期・遅延バッチ**で軽量/ローカル LLM に委任生成（コンテキスト圧迫回避）。

### W2: detector 差戻の構造化（「弱い部分」の補強）

Detector が rollback/major/minor を返して再ループする際:
1. 当該 `chat_history` 行に `is_rollback=1` を立てる。
2. そのターンを `relation_edges` で関連 artifact へ結ぶ:
   - `turn:<id>` → `agreement:<id>`（差戻で棄却/修正された合意）
   - `turn:<id>` → `whiteboard:<phase>:<task>`（差戻で編集された白紙 version）
   - `turn:<id>` → `issue:<topic>`（差戻で顕在化/消費された issue）
3. これにより「detector が何を差し戻し、何が変わり、進行がどう保たれたか」が系譜として残り、User AI/Expert の in-context 推論のみに依存しない。

### W3: 要約委任（軽量/ローカル LLM）

- 生文（content）はそのまま保持。要約は軽量モデル/ローカル LLM へ。
- N/M は新規重要定数（§7 承認要）。既定値提案: **N=10, M=30**（参考資料の Zone A/B から。但し CELA の `chat_history_window=4` とは別次元——窓は live コンテキスト用、N/M は Hydrate/recall 用）。

---

## 消費経路（出口・AGENTS.md §15.4）

### C1: Hydrate — あるターン（AI の問い）を起点に過去文脈を能動再構成

当該ターンの raw/summary（N/M 役割非対称ティア）＋ そのターンで変化した artifact（agreement/entity/issue/whiteboard diff）を描画。**5節（What/Why/Current/Open/Next）は再発明せず、CELA 既存のフェーズタスク/issue 等へ委ねる**（ユーザー指示）。Hydrate には「系譜 ＋ ターン内チューリン」だけを載せる。

### C2: `_audit_report --ref turn:<id>`（BL-224 の C2 を `turn:` へ拡張）

指定ターンとその関連 artifact を 5W1H で再構成（BL-222 の型を踏襲、読み取り専用）。

### C3: `trace_lineage` が `turn:<id>` も受け取る（BL-224 の C5）

そのターン ＋ 隣接ターン ＋ 関連 artifact（agreement/fact/entity/issue/whiteboard）を返す。これが「問いを起点に能動取得」の出口。

### C4: ターン内チューリン描画

あるターンを起点に、`whiteboard_drafts` の version 列（task_id 一致）と `relation_edges` の `turn:` 外向きエッジを時系列順に出す → detector の差戻の「揺れ」が可視化される。

---

## N/M 役割非対称ティア（要約ポリシー）

ユーザー確定の定義（距離 d = 現在ターン − 対象ターン）:

| 帯 | 範囲 | 出力 |
|----|------|------|
| ① | d ≤ N（直近） | 全役割 → **生文**（content） |
| ② | N < d ≤ M | **expert 役割のみ → summary_expert（圧縮）**。他の役割は生文 |
| ③ | d > M | 全役割 → **summary_full**（両方圧縮） |

**ピン例外（参考資料の pin メカニズム流用）**: binding/decision/verbatim 相当の部分は役割に関わらず Zone B 以上に昇格（索引に落とさない）。つまり expert の**探索的推論のみ**を②で圧縮し、expert の** binding 決定は残す**——「expert を早く圧縮したい」と「binding 決定は落とすな」の両立。

---

## checkpoint 方針（§14.4 ＋ 参考資料）

- `state["chat_history"]` は LangGraph checkpoint（graph 状態）＝**輸送**。cela.db の `chat_history` テーブル＝**正本（SoT）**。
- checkpoint からの復元は LangGraph 任せ。クエリは db の chat_history のみに対して。**混ぜない**（参考資料「展開の正本は Lineage DB、ネイティブ履歴に依存しない」に合致。AGENTS.md §14.4「checkpoint restore は DB を巻き戻さない」とも整合）。
- 書き込み時フックで checkpoint の append を db へ反映（db が SoT）。

---

## run_id の扱い（補正）

- `run_id` は**ドライラン全体を識別するスコープキー**（現状維持、手を触れない）。
- 発言ごとのIDは `chat_history.id`（autoincrement）＋ `turn=round_count`（「raund」）。

---

## 変更対象ファイル

- `cela_main.py`:
  - `chat_history` テーブル拡張（task_id/phase_id/summary_expert/summary_full/is_rollback 列追加: ALTER TABLE または再 CREATE）
  - `state["chat_history"]` の全 append 点からの書き込みフック（W1、§15.2 で全経路列挙）
  - detector 差戻の構造化（W2: is_rollback フラグ ＋ relation_edges `turn:` 外向きエッジ）
  - `relation_edges` へ `turn:`/`issue:`/`whiteboard:` プレフィックス追加（BL-224 の helper を拡張）
  - Hydrate 描画（C1）＋ `trace_lineage` の `turn:` 受付（BL-224 C5）＋ `_audit_report --ref turn:`（BL-224 C2）
  - 要約委任（軽量/ローカル LLM、非同期バッチ）
- `docs/design/back_log/BL-228/BL228_basic_design.md`（本ファイル）
- `docs/design/back_log/issue_backlog.md`: BL-228 起票
- `docs/design/back_log/BL-224/BL224_basic_design.md`: 未決事項へ「chat_history スパイン＋Hydrate 統合は BL-228 へ分割」とクロスリンク
- `tests/test_bl228_unified_activity_lineage.py`（新規）

---

## 未決事項（ユーザー判断）

1. **N/M 既定値**（N=10, M=30 を提案、AGENTS.md §7 承認要 — 新規重要定数）。
2. **要約委任の軽量/ローカル LLM の具体選定**（コスト・オフライン要件）。
3. **要約実行タイミング**（append 毎？ 非同期バッチ？ コンテキスト圧迫時？）。
4. **detector 差戻の構造化粒度**（`is_rollback` フラグのみ vs 専用 `rollback_events` テーブル）。
5. **BL-228 と BL-224 の実装順序**（relation_edges 基盤が先か、chat_history 活性化が先か）。

---

## 検証

- `python -m py_compile cela_main.py`
- **死蔵→活性化**: ドライラン後 `SELECT COUNT(*) FROM chat_history` が 0 でなくなる（出口なしの記録が仕組みになる）。
- **N/M ティア**: >M ターン生成し、①≤N は content、②N<≤M は expert のみ summary_expert、③>M は summary_full が返ることを確認。
- **ターン内チューリン**: detector 差戻を含む run で `relation_edges` の `turn:` 外向きエッジと `whiteboard_drafts` version が時系列で出る。
- **係数回帰（§17.1）**: W1/W2/W3 を個別にリバートし、対応テスト失敗を確認。
- **C1/C3/C5**: 実 LLM ドライランで、あるターンを起点に過去文脈（生文/要約/関連 artifact）が能動取得できる。
- **フルオフラインスイート**（§17.3）。
