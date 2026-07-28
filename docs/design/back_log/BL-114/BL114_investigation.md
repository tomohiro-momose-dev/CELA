# BL-114: システム/ユーザープロンプトの使い分け・思考フレームワーク調査（生ログ）

関連: [issue_backlog.md BL-114](../issue_backlog.md#bl-114-call_orchestratorの静的動的順序がコード自身のbl-104コメントと矛盾している)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は調査時点（2026-07-28）のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## 調査目的

プロンプト整理の要否を検討する中で、Exploreエージェント（カテゴリA）に「全ノードのプロンプト構成（system/user役割の使い分け、静的/動的コンテキストの分離、思考フレームワークの有無）」を読み取り専用で調査させた。この文書はそのエージェントの報告をそのまま保存したもの（生ログ）。BL-113（THINK_TOOLスキーマ書き換え漏れ）はこの調査を含む3件の並行調査から派生した別のBLとして既に対応済み。本BL-114は、この調査で見つかった`call_orchestrator`固有の静的/動的順序バグを対象とする。

## エージェント報告（原文）

## Findings: Prompt Construction Audit of `cela_main.py`

**Universal mechanics (apply to every node):**
- `query_AI()` (line 2301) always runs messages through `_inject_japanese_output_directive` (line 2351), which prepends/patches a `system`-role message (`_JAPANESE_OUTPUT_DIRECTIVE`, line 2348) — so every node technically ends up with at least one system message, regardless of what the node itself constructs.
- The `THINK_TOOL` (line 954) is the actual "reasoning framework" mechanism: its description mandates a todo list, `action`/`decided`/`why`/`rejected_why` fields, and an enforced think-call-per-tool-call-response rule. Nearly all nodes reference it via boilerplate text ("BL-093: thinkツールで検討過程を残す...todoに確認すべき論点をリストアップ...action/decided/why").
- `_query_and_parse_with_retry` (line 2916) is the common wrapper for JSON-only nodes: it always sends a **single `role:"user"` message** (line 2928), no separate system message from the node itself.

**Per-function table:**

| Function (line) | System/User split | Static vs dynamic separation | Thinking framework |
|---|---|---|---|
| `call_task_planner` (4189) | No — single `user` message via retry wrapper | Static rules (1-11, numbered) precede dynamic `{goal}`/`{goal_essence_text}` at the very end (4302); clean, mostly append-only | Explicit numbered rule list + BL-093 todo/think instructions (line 4267) |
| `call_orchestrator` (4381) | No — single `user` message | Comment at 4406 claims BL-104 static-front/dynamic-back ordering, but `goal_context` (dynamic) is actually placed **first** (4412), before the static role-description text (4414-4427); dynamic `Task`/DB/history still appended at the end — ordering is inconsistent with its own stated design note | No numbered framework; free-form instructions only |
| `call_expert` (4453) | **Yes** — explicit `system` message + full `state["chat_history"]` as user/assistant turns (4693-4713) | Best-separated node: comments (4472-4479, 4574, 4675) explicitly document a static-prefix/dynamic-suffix design for prefix-cache hits; a separate `light_system_prompt` (4718) is swapped in after iter=1 to shrink the system block. A few sub-blocks (Detector rollback, escalation resume) are intentionally kept adjacent to their referents, breaking strict separation but by design | No numbered step list, but BL-093 think/todo boilerplate present (4744) |
| `call_detector` (4766) | No — two `_query_and_parse_with_retry` calls, each a single `user` message (domain_prompt at 4943, prompt at 5036) | Both prompts carry a BL-104 comment (4936-4942, 5028-5035) explicitly describing static-instructions-first/dynamic-last ordering, with named exceptions for position-referencing blocks kept adjacent | Explicit 2-pass structure (domain review, then numeric audit) plus "3-trial majority vote" procedure (5067) and BL-093 todo/think guidance |
| `call_decision_extractor` (5232) | No — single `user` message (5461) | Static/dynamic interleaved: `role_instruction` (branch-static per target_role) itself embeds dynamic `valid_task_ids_text`/`owns_variables_text` (5282, 5285); a large dead `prompt_old` block (5344-5403) is built but never used, duplicating the JSON schema; final `prompt` re-concatenates `role_instruction` + `common_rules` + dynamic topics/history — no BL-104 caching comment here, unlike most other nodes | No todo/think tool available to this node (not in a tool list); no explicit reasoning framework |
| `call_resource_arbiter` (5477) | No — single `user` message (5551) | Clean static-first/dynamic-last, per BL-104 comment (5486-5490) | BL-093 todo/think guidance (5507) |
| `call_reflection` (5572) | No — single `user` message (5701) | Explicitly **not** reordered: comment (5625-5629) states static/dynamic separation was deliberately skipped here because instructions reference preceding dynamic blocks ("上記の矛盾・懸念が" etc.); only the self-contained BL-093 blurb was hoisted | No think/python tool list for this node; no numbered framework, narrative instructions only |
| `call_facilitator` (5711) | No — single `user` message (5779) | Static role text + goal (near-static) first, dynamic `reflection_block`/`escalated_issues_block`/history last, per BL-104 comment (5749-5755) | No tool list; no think framework |
| `call_integrator` (5781) | No — single `user` message (5836) | Clean static-first/dynamic-last (BL-104 comment 5785-5788) | BL-093 todo/think guidance (5801) |
| `call_reviewer` (5840) | No — single `user` message via retry wrapper (5942) | Clean static-first (long QA checklist)/dynamic-last (goal, deliverable) per BL-104 comment (5844-5848) | BL-093 todo/think guidance (5907) |
| `generate_user_utterance` (5963) | **Yes** — explicit `system` message + chat history as user/assistant turns (6206-6220) | Same BL-104 pattern as `call_expert`: static role/stance/tooling instructions built up first, dynamic DB/timeline/current-task/escalation content appended from ~6071 onward, comment at 5977-5981 documents this and named exceptions | BL-093 todo/think guidance (6146) |
| `call_goal_essence_analyst` (6365) | No — single `user` message via retry wrapper | Small function; goal placed near top (6380) then static instructions follow — not strictly static-first, but low call-frequency (runs once) so no BL-104 comment/optimization attempted | Explicit "2 perspectives" framework (feasibility + essence) plus BL-093 todo/think guidance |
| `call_task_plan_reviewer` (6525) | No — single `user` message via retry wrapper | Clean static-first (4 numbered review criteria + BL-092/093/094/095 guidance)/dynamic-last (goal, `phases_json`) per BL-104 comment (6531-6538) | Explicit numbered 4-criteria review framework + BL-093 todo/think guidance |

**Cross-cutting observations:**
- Of the 13 node functions, only **`call_expert`** and **`generate_user_utterance`** use a genuine `system` + separate conversational turns structure; all other 11 pack everything (role description, rules, tool docs, dynamic state) into one `user`-role message string, then rely on `query_AI`'s post-hoc injection for the one system message that does exist (the Japanese-output directive).
- Most nodes (all except `call_decision_extractor`, `call_goal_essence_analyst`, `call_reflection`, `call_facilitator`) carry an explicit "BL-104" code comment documenting a deliberate static-instructions-first / dynamic-context-last convention aimed at prompt-prefix caching, with call_reflection explicitly opting out of it due to internal cross-references between dynamic blocks, and call_orchestrator's actual code contradicting its own stated convention.
- The closest thing to a "reasoning framework" is the shared `THINK_TOOL` (line 954) mandating todo-lists and `action/decided/why` fields, referenced by boilerplate text in most audit/planning nodes (task_planner, expert, detector, resource_arbiter, integrator, reviewer, generate_user_utterance, goal_essence_analyst, task_plan_reviewer) but **absent** from `call_decision_extractor`, `call_reflection`, `call_facilitator`, and `call_orchestrator`, which get no structured tool-based reasoning scaffold at all beyond prose instructions.

## この調査から派生したBL

- **BL-113**（`done`）: THINK_TOOLスキーマのMANDATORY文言書き換え漏れ（カテゴリBの調査と合流して対応済み）。
- **BL-114**（本ファイル、`open`）: `call_orchestrator`の静的/動的順序がコード自身のBL-104コメントと矛盾している点（上記表の該当行）。
- 参考情報（BL化はしていない）: `call_decision_extractor`/`call_reflection`/`call_facilitator`/`call_orchestrator`にはTHINK_TOOLベースの構造化思考フレームワークが無い。単発判定・抽出タスクという性質上BL-109で意図的に`tools=None`へ戻した経緯があるため、現時点では設計判断の結果であり不具合とは見なさない。
