# BL-228 基本設計: 統一活動系譜（Unified Activity Lineage）— `chat_history` スパイン活性化 ＋ 単一閾値N要約（2密度） ＋ ターン内チューリン描画 ＋ Hydrate/trace の「本来の姿」統合

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
2. **単一閾値N要約（2密度）** — 軽量/ローカル LLM へ委任。≤Nラウンドは生文、>Nは要約。要約は「系譜一覧用1行（`summary_brief`）」と「会話ログ展開用（`summary_detail`）」の2密度。役割非対称は廃止（F-8.1 の人間vsAI前提がCELAには当てはまらず、BL-108 で窓方式は不安定と判定済み）。
3. **ターン内チューリン描画** — あるターンを起点に、detector の差戻を含む artifact 変化（agreement/entity/issue/whiteboard diff）を時系列で出す。
4. **Hydrate(C1) と trace(C5) を「本来の姿」に** — あるターン（AI の問い）を起点に過去文脈を能動取得。
5. **「弱い部分」の構造化** — detector 差戻を `is_rollback` フラグ＋`relation_edges` の `turn:` 外向きエッジとして系譜化し、進行が in-context 推論のみに依存する状態を解消。

---

### 先行BL調査：非対称圧縮の系譜（役割非対称を廃止する根拠）

ユーザーの指示「すべてAIでノードも多いから役割非対称圧縮の意味がない」を、過去のBLで裏付けた:

- **F-8.1 非対称メモリ圧縮**（要件定義書_v35 `:322`/`:789`、および `CHAT_HISTORY_WINDOW=4`）: この「非対称」の起源。**「User（人間）の入力こそ大事だから圧縮するな、他は圧縮」** という人間vsAIの前提に立っていた。`requirements_gap_map.md:256` はこれが未実装（⚠️）と判定済み。CELA は全ノードがAIなのでこの前提が崩れ、役割非対称は無意味になる。
- **BL-108**（issue_backlog `:3490`）: 「直近N iterは生・それより古いのは要約」という**窓方式を明示的に廃止**（「要約を廃止し単純な累積方式へ全面置換」）。境界の切り替え自体が毎iter不安定を生んでいたため。**教訓: 要約は書いたら不変（immutable）にし、毎ターン再派生させてはならない。**
- **D-070**（decision_log `:1042`）: ノード内スクラッチパッドの「decision_list/要約圧縮」を廃し全文上書き型へ。要約圧縮を退ける別の実例。
- **`CELA_architecture_review_2026-08-03.md:110`**: 「直近N件agreements生・それ以前要約」を `context_summarizer_node` で生成する提案。N窓の発想は繰り返し現れるが、要約は**専任の軽量LLM委任**で行うという点で本BLの方針と一致。

**結論**: 役割非対称（expertのみ圧縮）は廃止。単一閾値N（≤Nラウンドは生文、>Nは要約）に単純化。要約は**書き込み時に1回だけ生成（immutable）**し、再派生しない（BL-108の教訓）。

## スキーマ

### chat_history テーブル拡張（既存 5539 を拡張）

```sql
-- [BL-228] 既存の死蔵 chat_history を活性化し、統一活動系譜のスパインとする。
-- 既存定義(id, turn, role, content, timestamp, run_id)に下記を追加。
-- turn = round_count（「raund」）。task_id/phase_id で artifact と結合。
-- summary_brief/summary_detail は単一閾値N要約（軽量/ローカルLLM委任）の格納先。2密度:
--   summary_brief  = 系譜一覧（値の連鎖リスト）に出す1行要約
--   summary_detail = 会話ログ展開時に出す要約（より高密度）
-- ≤Nラウンドは content(生文) をそのまま出し、>Nラウンドは要約を出す（§単一閾値N要約ポリシー）。
-- is_rollback は detector 差戻の構造化（「弱い部分」の補強）。
CREATE TABLE IF NOT EXISTS chat_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    turn INTEGER,                 -- = round_count（「raund」）
    task_id TEXT DEFAULT '',
    phase_id TEXT DEFAULT '',
    role TEXT,                    -- user / expert / detector / facilitator / ...
    content TEXT,                -- 生文（raw）
    summary_brief TEXT DEFAULT '',   -- 系譜一覧用1行要約（軽量/ローカルLLM委任・immutable）
    summary_detail TEXT DEFAULT '',  -- 会話ログ展開用要約（より高密度、同委任・immutable）
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

### detector_reviews テーブル（新規・ユーザー承認済み）

Detector の評決（rollback/major/minor）を構造化して永続化する。**agreements には混ぜず専用表**（セマンティクス汚染を避ける。agreements は「合意」、detector_reviews は「ゲートの評決」で別種）。従来は `state["detector_observations_log"]`（in-memory）にのみ存在し DB に Persist されていなかった（§15.4 の死蔵/揮発）。`relation_edges` の `detector_review:<id>` で chat_history の該当 turn と結ぶ（W2）。

```sql
-- [BL-228] Detector 評決の構造化永続（§15.4: 従来は in-memory のみで死蔵/揮発）。
-- agreements には混ぜず専用表（セマンティクス汚染回避）。relation_edges の
-- `detector_review:<id>` で chat_history の該当 turn と結ぶ。
CREATE TABLE IF NOT EXISTS detector_reviews (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    turn_id INTEGER,                 -- chat_history.id（該当する発言/差戻しターン）
    task_id TEXT DEFAULT '',
    phase_id TEXT DEFAULT '',
    risk TEXT DEFAULT '',            -- low/none/...
    constraint_issue TEXT DEFAULT '',-- none/minor/major
    comment TEXT DEFAULT '',         -- Detector の評決コメント（長文）
    criteria_status_json TEXT DEFAULT '', -- [true,true,false] 等
    target_excerpt TEXT DEFAULT '',
    observations TEXT DEFAULT '',
    created_at REAL
);
CREATE INDEX IF NOT EXISTS idx_detector_reviews_run_turn ON detector_reviews(run_id, turn_id);
```

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

### C1: Hydrate（on-demand 走査）— ある値/artifact を起点に系譜を能動再構成

**消費層の正体は「毎ターンの自動注入」ではない**（既存のプロンプト注入＝直近数ターン生ログ＋decision/issue が既に担っているため、再注入は冗長）。AI が「この10%はどこから？」と疑問を持った時に**ツールとして能動呼び出し**するのが本番の消費経路。

- 走査キーは**変数/artifact 名（キーワード）**（例: `高齢者外出率`、`凍結`）。距離ではなく名前で系譜を掘る。
- 各ヒット = `(task_id, round, 値, by, way, citation, summary_brief, detector_review?)` のイベント列を時系列表示。
- 値を書き換えたターンには、それを強いた `detector_review` への `relation_edges` エッジを張り、rollback 文脈を確実に取得（「次の2ターンを無条件表示」の代わり）。
- **on-demand deep-dive は距離に関わらず全生文**を出す（参考資料の lineage-expand / pin例外）。N要約は audit レポート等の軽量表示にのみ適用。
- **5節（What/Why/Current/Open/Next）は再発明せず**、CELA 既存のフェーズタスク/issue 等へ委ねる（ユーザー指示）。

### C2: `_audit_report --ref turn:<id>`（BL-224 の C2 を `turn:` へ拡張）

指定ターンとその関連 artifact を 5W1H で再構成（BL-222 の型を踏襲、読み取り専用）。

### C3: `trace_lineage` が `turn:<id>` も受け取る（BL-224 の C5）

そのターン ＋ 隣接ターン ＋ 関連 artifact（agreement/fact/entity/issue/whiteboard）を返す。これが「問いを起点に能動取得」の出口。

### C4: ターン内チューリン描画

あるターンを起点に、`whiteboard_drafts` の version 列（task_id 一致）と `relation_edges` の `turn:` 外向きエッジを時系列順に出す → detector の差戻の「揺れ」が可視化される。

---

### C5（追加）: ゴール条件陳腐化の検知 — Reflector / Facilitator の活用

系譜から「ゴール条件として登録された値（例: 凍結エリア＝標高1000m以上）が、のちのタスクで別の基準（気温ベース）へすり替わり陳腐化している」ことが可視化される。このシグナルは **Reflector / Facilitator ノードも消費**し、ゴール条件そのものの妥当性を見直す経路へ流すべき（BL-126 のプロアクティブ目標問い直しと接続）。

## 単一閾値N要約ポリシー（2密度・immutable）

役割非対称圧縮は廃止（F-8.1 の人間vsAI前提がCELAには当てはまらない。先行BL調査参照）。
単一の閾値 N のみ:

| 帯 | 範囲（距離 d = 現在ラウンド − 対象ラウンド） | 出力 |
|----|----------------------------------------------|------|
| ① | d ≤ N（直近） | **生文**（content）をそのまま |
| ② | d > N | **要約**を出す（下記2密度） |

**2密度の要約**（どちらも軽量/ローカルLLM委任、append 時に1回生成して不変）:
- `summary_brief`: 系譜一覧（値の連鎖リスト）に出す**1行要約**。各イベントの `task_id / round / 値 / by / way / citation` と併せて1行で示す。
- `summary_detail`: あるターンの会話ログを**展開**した時に出す要約。brief より高密度（そのターンで何が議論されたかの要点）。

**immutable の原則（BL-108 の教訓）**: 要約は append 時に1回だけ生成し、以降は再派生しない。境界 d=N の切り替えで毎ターン要約を作り直すと不安定になる（BL-108）。既存の `content`（生文）は常に DB に残り、要約未完了時は生文で fallback 表示（§13.2）。

**N の値**: ユーザー指示で N=3 程度（run 全体30ターン上限に対して十分小）。audit レポート等で古いノードを圧縮表示するための閾値。on-demand deep-dive は距離に関わらず全生文（C1）。

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
5. **BL-228 と BL-224 の実装順序【解決済み】**: BL-224 を **Phase 1-2 で先行**、BL-228 を **Phase 3 で後続**（2026-08-14 ユーザー判断）。関係: `relation_edges` を単一基盤として BL-228 が拡張（ref プレフィックス追加）するため、基盤側（BL-224）を先に確立するのが構造的に正しい。BL-224 設計書の「未決事項3」に3段階計画を記載。

---

## 検証

- `python -m py_compile cela_main.py`
- **死蔵→活性化**: ドライラン後 `SELECT COUNT(*) FROM chat_history` が 0 でなくなる（出口なしの記録が仕組みになる）。
- **N/M ティア**: >M ターン生成し、①≤N は content、②N<≤M は expert のみ summary_expert、③>M は summary_full が返ることを確認。
- **ターン内チューリン**: detector 差戻を含む run で `relation_edges` の `turn:` 外向きエッジと `whiteboard_drafts` version が時系列で出る。
- **係数回帰（§17.1）**: W1/W2/W3 を個別にリバートし、対応テスト失敗を確認。
- **C1/C3/C5**: 実 LLM ドライランで、あるターンを起点に過去文脈（生文/要約/関連 artifact）が能動取得できる。
- **フルオフラインスイート**（§17.3）。
