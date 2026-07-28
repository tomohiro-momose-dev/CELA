# BL-115: ツールschemaとプロンプト本文の重複調査（生ログ）

関連: [issue_backlog.md BL-115](../issue_backlog.md#bl-115-ノードプロンプト間の重複ボイラープレートおよびcall_decision_extractorの未使用デッドコードprompt_old)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は調査時点（2026-07-28）のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## 調査目的

プロンプト整理の要否を検討する中で、Exploreエージェント（カテゴリB）に「全ツールschemaの`description`とノードプロンプト本文との重複、およびノードプロンプト間の重複ボイラープレート」を読み取り専用で調査させた。この文書はそのエージェントの報告をそのまま保存したもの（生ログ）。調査中に発見したTHINK_TOOLスキーマの書き換え漏れはBL-113として別途対応済み。本BL-115は、それ以外の残存する重複ボイラープレートとデッドコードを対象とする。

## エージェント報告（原文）

Now I have enough to write the report.

### 1. Catalog of `*_TOOL` schema dicts

| Tool | Definition (file:line) | Description summary |
|---|---|---|
| PYTHON_REPL_TOOL | 564-597 | Sandboxed python for numeric verification; stateful within turn; must use `print()`. |
| READ_VERIFIED_FACT_TOOL | 600-627 | Search cross-phase verified facts by variable/topic. |
| READ_DELIVERABLE_FILE_TOOL | 629-663 | Read a previous task's deliverable file by task_id/topic. |
| WRITE_ISSUE_TOOL | 668-711 | Log/resolve minor concerns in issue_log; auto-escalates on 2nd recurrence. |
| READ_ISSUES_TOOL | 713-740 | Search/list issue_log entries. |
| VERIFY_WHITEBOARD_EXCERPT_TOOL | 748-774 | Detector-only: check a quote matches whiteboard exactly once before using as target_excerpt. |
| DIFF_PLAN_DRAFT_VERSIONS_TOOL | 783-809 | task_plan_reviewer-only: mechanical diff between last 2 task_planner plan versions. |
| READ_PLAN_DRAFT_TOOL | 856-883 | task_planner-only: read latest plan_draft whiteboard incl. reviewer comments. |
| READ_PROJECT_PLAN_TOOL | 902-919 | Read full phase/task plan detail beyond the TOC shown by default. |
| THINK_TOOL | 954-1050 | Scratchpad: action/summary/decided/why/rejected/todo/issues/notes. (BL-113で書き換え済み: 当時はMANDATORY文言が残存していたが対応済み) |
| WRITE_AGREEMENT_TOOL | 1238-1361 | Save decision/directive/deliverable to agreements DB; role-based status restrictions. |
| FREEZE_AGREEMENT_TOOL | 1370-1395 | Permanently pin an agreement (user-only; currently unwired per D-045 comment). |
| ESCALATE_PREMISE_CONCERN_TOOL | 1435-1464 | Raise narrow goal-premise conflict concern. |
| RESOLVE_PREMISE_CONCERN_TOOL | 1466-1487 | Reject an open escalation. |
| REVISE_GOAL_TOOL | 1489-~1520 | Accept escalation, revise goal text, optionally freeze. |

### 2. Redundant "think" tool-usage boilerplate (schema vs. prompts)

Every one of the 14 non-THINK tools carries the identical schema-level sentence (verbatim except tool name context):
`"[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call to record your reasoning -- it is no longer required, and other tool calls are no longer rejected for omitting it."`
at lines: 579-581, 609-611, 641-643, 681-683, 723-725, 759-761, 794-796, 868-870, 913-915, 1253-1255, 1379-1381, 1447-1449, 1474-1476, 1499- (14 occurrences).

Separately, **10 node-prompt locations** re-explain "you may also call think" via a `【重要】あなたが使えるツールは...think です...think以外のいずれかを呼ぶ場合、必要に応じて同じ応答内でthink（summary付き）を呼んでも構いません` boilerplate that lists the exact tool set available to that node and restates the same optional-think guidance already in each tool's schema description:
4298-4300 (call_task_planner), 4750-4751 (call_expert), 4973-4974 (call_facilitator area), 5113-5114 (call_detector), 5519-5520 (call_resource_arbiter), 5815-5816 (call_reviewer), 5920-5921 (call_reflection? — near line 5920), 6160-6162 (call_task_plan_reviewer/detector block), 6431-6432 (call_goal_essence_analyst), 6624-6625 (call_task_plan_reviewer). This is a 10-location duplicate of tool-availability + optional-think phrasing (all correctly softened, matching BL-110 wording — no stale mandatory language found in these 10 prompt copies).

### 3. Other near-verbatim duplicated blocks across multiple node prompts

| Duplicated block (paraphrase) | Locations (count) |
|---|---|
| "[BL-094] read_verified_fact/read_deliverable_file — cross-phase sync with confirmed values" explainer paragraph | 4274, 4732, 5089, 5512, 5806, 6137, 6419, 6609 (8 places) |
| "Don't repeatedly re-verify the same point with python_repl; 2 checks are enough" throttle note | 4261, 4538, 5501, 5795, 5901, 6402 (6 places, near-identical Japanese wording, 2 slightly reworded variants "2回計算で十分/2回程度で十分") |
| "Use python_repl for numeric grounds; mental arithmetic is prohibited" (暗算禁止/禁止します) | 4244, 4532, 4725, 5064-5065, 5498, plus similar at 5898/6369/6584 (~8 places) |
| write_agreement/write_issue confirmed_variables `confidence="provisional"` default-guidance note | 4566, 4727 (2+ places, similar wording) |
| BL-093 "think tool lets you preserve reasoning across iterations" prose paragraph in node prompts themselves (separate from schema) | 4267, 4744, 4972, 5099, 5507, 5801, 5907, 6146, 6414, 6602 (10 places) — this duplicates THINK_TOOL's own description content across ~10 node prompts |

### 4. Leftover BL-093 mandatory-think language（発見当時の記録。BL-113で対応済み）

**Found a real leftover.** THINK_TOOL's schema `description` field (cela_main.py:963-971) still contains the full old mandatory-enforcement text:
> `"MANDATORY RULE (enforced mechanically, not a suggestion): EVERY SINGLE response you send that contains ANY tool call ... MUST include a think call with a non-empty summary IN THAT SAME RESPONSE ... If you call e.g. python_repl without think+summary in that same response, NONE of that response's tool calls ... will be executed ..."`

This directly contradicts the code comment at line 2574/2680-2681 stating the mechanical rejection was abolished in BL-110, and contradicts the 14 `[BL-110] Optionally call think...it is no longer required` sentences added to the *other* tool schemas. The `THINK_TOOL` schema itself was apparently missed when BL-110 rewrote the other 14 tools — it still tells the model tool calls will be rejected without `think+summary`, which is false given the actual `_query_AI_live` loop logic (lines 2675-2681) that now runs think as fully optional. Additionally, `"required": ["action", "summary"]` (line 1047) still hard-requires `summary` whenever `think` itself is invoked (this part is arguably a separate, intentional constraint on the think call's own parameters, not the mandatory-every-turn rule, but combined with the stale description text it reinforces the false "mandatory" framing).

No other stray `MANDATORY`/hard-mandatory-think phrasing was found elsewhere in the 8018-line file — all other BL-093/BL-110 references are historical code comments (correctly noting the rule was abolished) or the already-softened `[BL-110] Optionally call think` sentences.

**[追記]** この項目（THINK_TOOLスキーマ自体の書き換え漏れ）はBL-113として別途起票・実装済み（`done`）。本BL-115のスコープは上記2・3節の残存する重複ボイラープレート、およびデッドコード（下記）。

## デッドコード・自己重複（この調査で追加確認した内容）

- `call_decision_extractor`（cela_main.py:5232）内の`prompt_old`ブロック（5344-5403行目、約60行）は`query_AI`へ渡されず未使用。実際に使われる`common_rules`と内容がほぼ重複しているため削除候補。
- `call_expert`は`system_prompt`（初回iter用）と`light_system_prompt`（iter=2以降用）の2つを同一関数内に持ち、いずれも同様のスコープ・再導出・ツール一覧ルールを含む。
- `call_detector`は1回の呼び出しで`domain_prompt`（ドメインレビュー用）と`prompt`（数値監査用）という2つの大きいプロンプトを構築するが、両方が「気づき欄」指示・ツール一覧の免責事項・BL-093のthink説明を独立してほぼ同一文言で保持している。

## この調査から派生したBL

- **BL-113**（`done`）: THINK_TOOLスキーマのMANDATORY文言書き換え漏れ。
- **BL-115**（本ファイル、`open`）: 上記2・3節の重複ボイラープレート群、および`prompt_old`デッドコード・`call_expert`/`call_detector`の自己重複。
