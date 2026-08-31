---
description: Project agent rules — docs model, code comments, constants, niche-language refs
alwaysApply: true
---

# Agent Rules (Project Template)


## 1. Codebase Memory MCP

**MANDATORY: use Codebase Memory MCP graph tools FIRST — before reading files or making code changes.**

This rule applies to every request involving this codebase.

Always call `list_projects` first when you do not already know the project name, then use the `display_name` or exact `name` returned by that tool.

```json
// Step 0 — discover project names
mcp_codebase-memo_list_projects()

// Step 1 — use the project identifier returned above
mcp_codebase-memo_get_architecture({ "project": "<display_name>" })
```

### Workflow

1. Call `list_projects` to discover the correct project name.
2. Call `get_architecture(project)` to understand the codebase structure.
3. Use `search_graph` to find relevant symbols, `trace_call_path` for call chains.
4. Use `get_code_snippet` to read specific function implementations.
5. Only use `read_file` when you need exact raw content to edit a specific line.

### Available Tools (14 MCP tools)

**Indexing:**
- `index_repository(repo_path)` — Index a repository into the knowledge graph
- `list_projects` — List all indexed projects with node/edge counts
- `delete_project(project)` — Remove a project and all its graph data
- `index_status(project)` — Check indexing status

**Querying:**
- `search_graph(name_pattern, name_scope, label, file_pattern, exclude_file_pattern)` — Structured search by label, name/qualified_name, include/exclude file globs
- `trace_call_path(function_name, direction, depth)` — BFS call chain traversal
- `detect_changes(project)` — Map git diff to affected symbols + risk
- `query_graph(query)` — Execute Cypher-like graph queries (read-only)
- `get_graph_schema(project)` — Node/edge counts, relationship patterns
- `get_code_snippet(qualified_name)` — Read source code for a function
- `get_architecture(project)` — Codebase overview: languages, packages, routes, hotspots
- `search_code(pattern, project)` — Grep-like text search within indexed files
- `manage_adr(action)` — CRUD for Architecture Decision Records
- `ingest_traces(traces)` — Ingest runtime traces to validate HTTP edges

## 2. **Context7**: Before writing or investigating code that depends on an
  external library or framework, always check Context7 for the current
  documentation first. This is mandatory for libraries with frequent
  version-dependent changes (e.g. React, Next.js).

## 3.  **Sequential Thinking**: Use sequential-thinking to reason step-by-step
  before implementing in these cases:
  - Tasks involving architecture or design decisions
  - When multiple implementation approaches are plausible
  - Bugs whose root cause isn't obvious
  Do not use it for trivial fixes or typo-level changes

## 4. Documentation Model (Source of Truth)

**MANDATORY for every request that changes requirements, design, or implementation tasks.**

### Core rules

1. **Source of truth** for requirements and design is `docs/design`, **not** a GitHub Issue body (if any).
2. **Starting point** for a greenfield project: `docs/要件定義.md`.
3. **Before coding or design edits:** read `STATUS.md` → `要件定義.md` `cela_roadmap_vXX.md`→ `cela_phaseN_design_vX.md`->`cela_phase1_impl_Plan.md`->`issue_backlog.md` → `phase_gates.md` (and the relevant `phaseN/` doc).
4. **Layers must not mix:**
   - Requirements narrative → `要件定義.md`
   - How / constraints / tests → `phaseN/`
   - Implementation tasks / bugs → `issue_backlog.md` (BL-xxx)
   - Decisions (Why) → `decision_log.md` (D-xxx) — **`Reason for the decision` is mandatory** for every `decided` entry
   - Progress → `STATUS.md` / `phase_gates.md` / `traceability.md`
5. **When changing requirements or constraints:**
   1. Update `要件定義.md` and the relevant `cela_roadmap_vXX.md` and `phaseN/` doc.
   2. Record decisions in `decision_log.md` (why chosen + why alternatives rejected).
   3. Add implementation follow-ups to `issue_backlog.md` (BL), not into the requirements narrative.
   4. Sync any GitHub Issue **summary only at milestones** — not on every edit.
6. **End of each implementation turn:** append remaining work, edge cases, and known issues to `issue_backlog.md` as BL-xxx.
7. **Implemention Plan**
  When creating an implementation plan in Plan mode, first save the plan data as `cela_phaseN_impl_Plan.md` in `/docs/design/phaseN` (N is Phase number) (do not summarize it under any circumstances).
   - **BL-scoped plans/investigations**: When a Plan-mode design or an Explore/Plan-agent investigation is scoped to one or a small cluster of specific BL-xxx items (rather than a whole phase), save it under `docs/design/back_log/BL-xxx/` instead (create the folder for the lowest/primary BL number in the cluster if it doesn't exist). Naming follows existing precedent: `BL{xxx}_basic_design.md` for a design produced via Plan mode (Explore + Plan agents), `BL{xxx}_investigation.md` for research/root-cause findings without a full design, `BL{xxx}_review.md` for an independent review of an existing design doc. When one design/investigation spans multiple BL numbers (e.g. `BL{xxx}_{yyy}_basic_design.md`), file it under the lowest BL number's folder and cross-link every covered BL from both `issue_backlog.md` and the doc itself. Do not summarize or omit content — save the plan/investigation verbatim, the same as the phase-level rule above. Reference existing examples: `docs/design/back_log/BL-126/BL126_basic_design.md`, `docs/design/back_log/BL-114/BL114_investigation.md`.
8. **Prohibition of unauthorized actions** 
   Not autonomously perform implementation actions unless instructed by the user.
9. **Decision Lineage (dialogue-level rationale)** — mirrors CELA's own core philosophy (Lineage-driven) in how the project itself is developed:
   - Record the **dialogue** behind non-trivial decisions — not just the final ruling — in `decision_lineage.md`, one entry per review/discussion session.
   - `decision_lineage.md` is a narrative companion to `decision_log.md`, not a replacement: `decision_log.md` keeps the concise, canonical `D-xxx` ruling (reason kept to 1-3 sentences); `decision_lineage.md` holds the fuller back-and-forth that produced it — who raised each point, who decided (explicitly attribute AI-originated proposals as such, even when the AI's reasoning is what ultimately won), and the causal wording ("because / so that / therefore") connecting fact to decision. Cross-link both directions via `D-xxx` / `BL-xxx` IDs.
   - **Why this rule exists:** thin "why" records cause knowledge silos and tacit, person-dependent understanding (属人化) — a risk that compounds as AI takes a growing role in decisions. Preserving who argued what and why, including the AI's own reasoning trail, is treated as load-bearing, not optional documentation.

## 5. Coding, Thinking Analysing
1. **Calculations** 
　　In principle, LLMs are incapable of performing calculations. 
    Whenever a task requires calculation—whether based on premises, constraints, code comments, or numerical values ​​embedded in the code—the model must invariably invoke a Python tool, generate mechanical calculation code, and perform both the calculation and verification, even for simple operations like addition.

1. **Grounded Architecture & Verification**
   - **No Guessing/Fabricating:** NEVER assume or guess the existence of any API, library, or framework feature. Use official, up-to-date syntax. If you are unsure of a function signature or version-specific API, stop and ask the user or verify it using search/read tools first.
   - **Controlled Dependencies:** Do not arbitrarily import uninstalled packages. When a new library/dependency is required:
     1. Propose the specific package and explain why it is necessary.
     2. Ask for user approval, OR explicitly add it to the package configuration file (e.g., package.json, requirements.txt, go.mod) and run the install command before importing it in your code.

2. **Design Before Implementation (For New Features)**
   - **Blueprint First:** Before creating new files or writing large blocks of new code, briefly present your plan:
     1. Proposed file structure and where the new code fits.
     2. Key architectural choices (e.g., state management, design patterns).
     3. Integration points with the existing code (if any).
   - **Style Consistency:** Follow the existing project's directory structure, naming conventions, and coding style.

3.  **Code Quality & Completeness**
    - **No Lazy Placeholders:** Never use placeholders like `// ... existing code ...` or `// TODO: implement` inside modified or newly created files. Always output complete, fully functional, and syntactically valid code blocks.
  
4.  **Communication Preference**
    - **Language:** Always explain your plans, logic, and reasoning in Japanese. Keep the actual code, variables, and technical terms in English.

5.  **Consuming LLM Output / Designing Fallbacks**
    - Any code that reads LLM-produced JSON, or that falls back to `""` / a "current" value / a stub object (e.g. after a JSON parse error), is governed by **§13**. Read it before writing the fallback, not after the incident.

6.  **Sections §13–§18 are the distilled failure history of this project**
    - §13 defensive handling of LLM output · §14 grounding a diagnosis in evidence · §15 single source of truth for rules · §16 proposing/reviewing/reporting · §17 testing discipline · §18 git and live-run hygiene.
    - Every rule there was written after a real defect, and each cites the BL/D that produced it. When a task touches one of those areas, read the section **before** acting — these were added precisely because the same mistakes recurred when the reasoning stayed implicit.

**Index:** `docs/design/README.md`

| Layer | File / location | Role |
|-------|-----------------|------|
| Requirements start / working master | `要件定義.md` | Background, tasks, acceptance criteria |
| Phase design | `phaseN/` | How, constraints, tests |
| Implementation tasks | `issue_backlog.md` | BL-xxx bugs and open items |
| Decisions (why) | `decision_log.md` | Mandatory rationale |
| Decision dialogue (fuller why, who argued/decided) | `decision_lineage.md` | Narrative trail behind D-xxx rulings, cross-linked by ID |
| Progress | `STATUS.md`, `phase_gates.md`, `traceability.md` | Where we are / Done / coverage |
| Optional epic entry | GitHub Issue (short) | Link to docs only |

Optional GitHub Issue: summary + link to `docs/design/README.md` only. Do **not** treat Issue comments as the requirements master.

---

## 6. Code Comments — "Why" Over "What"

- Never write comments that only paraphrase syntax.
- Comments must explain **intent, constraints, rejected alternatives**.
- Update adjacent comments when code changes (**no stale comments**).
- Prefer tags for critical notes: `[CONSTRAINT]`, `[SAFETY]`, `[REJECTED]`.

Module / class / function docs should describe purpose and non-obvious assumptions.

---

## 7. Constant Modifications (Strict Control)

- **Prior approval required** before changing critical constants (buffer sizes, array lengths, timeouts, protocol magic values, etc.).
- State the reason and obtain **explicit written approval** from the user.
- Do **not** change these unilaterally.

---

## 8. Issue & Backlog Management

- Implementation leftovers → `docs/design/issue_backlog.md` as BL-xxx.
- Do **not** dump implementation bugs into `要件定義.md`.
- Review findings → BL entries; freeze detailed review archives under `phaseN/` if needed.

---

## 9. Minor / Niche Languages — Official Reference First

When writing or modifying code in a **minor or niche language** (vendor DSL, macros, uncommon scripting, etc.):

1. **Before naming APIs/commands:** fetch the **official reference** (web search / fetch) — not memory alone.
2. **Cache locally:** save excerpts under `docs/refs/<tool>/` with source URL and fetch date.
3. **Reuse the cache** on later turns unless the API is unclear or the manual may have changed.
4. **Sync design docs** that name commands/APIs against the cached reference before coding.

Prefer well-supported host languages (e.g. Python, C#) for tooling when a niche language repeatedly causes hallucination or validation cost.

---

## 10. Test / Dry-run Notes Placement

| Content | Where |
|---------|--------|
| Pass/fail summary | `traceability.md` (T-*) |
| Failures / next fixes | `issue_backlog.md` (BL-*) |
| Procedure / environment detail | `phaseN/phaseN_dryrun.md` (create when needed) |
| Raw logs | project-specific log directory (e.g. `artifacts/`, `drive/`) |

---

## 11. Writing the Summary (generated code)

Place a short purpose comment / docstring immediately before generated functions, classes, or non-trivial blocks, appropriate to the language.

## 12. Autocomplete & Inline Comment Generation Rules (CRITICAL)

This section strictly governs **Autocomplete, Inline Suggestions (Cursor Tab), and Copilot Ghost Text**. 

### 1. Trigger Conditions & Behaviors
Whenever the user types a comment delimiter (e.g., `#`, `//`, `/*`, `"""`) or requests inline documentation generation, you must adhere to the following rules:

* **Strictly English Only:** All autocompleted comments, docstrings, and hints MUST be generated in **English** (for maximum clarity and model performance).
* **Predict & Complete the "Why":** NEVER autocomplete trivial descriptions of the syntax (e.g., do not suggest `# open port` when the user types `#`). Instead, predict the technical intent, constraint, or safety hazard (e.g., suggest `# Configure non-blocking mode to keep UI responsive`).
* **Infer from Context:** Dynamically analyze the surrounding code, variable locks, thread states, or class properties to predict the specific engineering decision, and put that explanation into the ghost text.

### 2. Autocomplete Suggestion Patterns (Few-Shot Examples)
When the user types the prefix on the left, you must autocomplete with the semantic style on the right:

* **User types:** `# ` (inside a loop/critical section)
  * **AI autocompletes:** `# Limit polling rate to 10ms to reduce CPU overhead to <1% without losing UART bytes`
* **User types:** `# [SAFETY] `
  * **AI autocompletes:** `# Lock self.rx_buffer to prevent race conditions with the async receiver thread`
* **User types:** `# [CONSTRAINT] `
  * **AI autocompletes:** `# Device firmware only accepts b'\\r\\n' endings; raw write() without endings will hang the parser`
* **User types:** `def wait_and_drain_bytes(self, length, timeout_sec):` -> (presses Enter and types `# `)
  * **AI autocompletes:** `# Discard binary payload from buffer silently to prevent Tkinter rendering lag or memory exhaustion`

---

## 13. Defensive Handling of LLM-Produced Structured Data (CRITICAL)

**Premise: an LLM can return an empty string — or omit a field entirely — for any field, at any
time, including fields it filled correctly on every previous turn.** This is not a rare edge case;
it is normal, recurring model behavior. Treat every field of every LLM-produced JSON object as
*optionally absent and optionally empty*, regardless of what the prompt instructed.

The same applies to any value that reaches your code through a lossy boundary: a JSON parser that
fell back to a default object on a parse error, a retry layer that returned a stub, a tool result
that was truncated. **Anything that can arrive as `""` will eventually arrive as `""`.**

### 13.1 The empty-string trap (`.get(key, default)`)

`d.get("key", default)` falls back **only when the key is absent**. `{"key": ""}` yields `""`,
not the default. This single misunderstanding is the direct cause of multiple production incidents
in this project.

```python
phase_id = item.get("phase_id", current_phase_id)   # BAD:  "" survives and poisons downstream
phase_id = item.get("phase_id") or current_phase_id  # GOOD: "" is treated as missing
```

Apply the same scrutiny to truthiness checks used as guards. `if not args.get(f)` correctly rejects
`""`; `if f not in args` does not.

### 13.2 Investigate downstream before writing ANY fallback

**This is the core rule of this section.** Before you write a fallback — to `""`, to a "current"
value (`current_phase`, `current_task_id`, ...), to a default enum member, or to a stub object on a
parse failure — you must **trace what the fallback value does to every consumer of that value**, and
confirm the system degrades safely rather than breaking silently.

Concretely, answer these before committing the fallback:

1. **Who reads this value later?** Grep for every consumer — including other modules, DB columns
   written from it, and prompts built from it. A fallback is not local; it propagates.
2. **What happens at each consumer when the value is the fallback?** Walk each branch. Does an
   `if x == "Deliverable"` become permanently false? Does a lookup silently match zero rows? Does a
   record become invisible to a later query that filters on that column?
3. **Is the failure loud or silent?** A fallback that produces a visible error is acceptable. A
   fallback that produces a *plausible-looking but wrong* result is not — it is worse than a crash,
   because nobody will notice. Prefer fail-closed (refuse and log) over fail-open (proceed with a
   guessed value).
4. **Can the corrupted value persist?** If the fallback value is written to a database, file, or
   conversation history, the damage outlives the turn and can propagate to future turns. Persisted
   state deserves stricter validation than transient state.
5. **Does a more authoritative source exist?** See §13.3.

If you cannot answer 1–4 with confidence, **do not add the fallback**. Ask the user, or make the
code reject the input explicitly.

### 13.3 Prefer the authoritative store over a derived representation

When a value can be checked against the system of record, check the system of record — do not infer
state from a string's shape or from a field that a lossy path may have overwritten.

```python
is_promoted = old_content.startswith("WHITEBOARD:")            # BAD:  depends on a string form
is_promoted = get_latest_whiteboard(conn, run_id, ...) is not None  # GOOD: asks the real table
```

Likewise, when restoring such a derived representation, **regenerate it from the authority rather
than copying the previous value forward** — copying propagates corruption across generations, while
regenerating repairs already-corrupted records on the next write.

### 13.4 Keep validation symmetric across all write paths

If the same table/state can be written through more than one path, **every path must enforce the
same invariants**. A heavily validated path plus an unvalidated "fallback" path is not a safety net;
it is a second, unguarded front door. Whenever you add or discover a second write path, either route
it through the existing validation or replicate the equivalent checks — and record which choice you
made and why in `decision_log.md`.

### 13.5 Fix the class, not the instance

When a defect of this kind is found, **do not stop at the field that triggered it**. Inspect the
sibling fields on the same line, the same dict, and the same code path — they almost certainly share
the flaw. Then check whether the identical pattern exists on other paths. Fixing one field at a time
guarantees the same bug returns from a route you have not walked yet.

### 13.6 Checklist before merging code that consumes LLM output

- [ ] Every `.get(k, default)` on LLM-derived data reviewed; switched to `.get(k) or default` where `""` must not survive
- [ ] Enum-valued fields validated against their allowed set (empty string rejected)
- [ ] Identity/lookup fields (ids, keys) validated for existence before use, not merely for non-`None`
- [ ] Downstream consumers of each fallback value traced and confirmed safe (§13.2)
- [ ] No state decision made from a string prefix/format when an authoritative store is reachable (§13.3)
- [ ] All write paths to the same state enforce the same invariants (§13.4)
- [ ] Failure mode is loud (error/log), never a silently plausible wrong value
- [ ] Regression test added that **fails when the fix is reverted** (revert it and confirm)

### 13.7 Reference incidents

These are the real defects this section was distilled from. Read them before designing a new
fallback; the full cross-cutting audit is in `docs/design/back_log/BL-213/BL213_investigation.md`.

| BL | Trusted field | What broke |
|----|---------------|------------|
| BL-206 | `item["phase_id"]` (empty-string drift) | Deliverable records orphaned; every subsequent edit failed against an empty base |
| BL-210 | `advances_to_phase_id` (null → "current" fallback) | Cross-phase task transitions rejected forever; run halted |
| BL-211 | `item["task_id"]` (empty-string drift) | Transition safety net silently never fired; task switch never completed |
| BL-212 | `old_content` string prefix | Whiteboard pointer lost; 17 consecutive edit failures |
| BL-213 | (cross-cutting audit) | Validation asymmetry between two write paths identified as the structural root cause of all of the above |
---

## 14. Grounding a Diagnosis in Evidence (Investigation Discipline)

Most wrong fixes in this project came from a diagnosis that *looked* right, not from a bad fix.
Before you name a root cause, satisfy the following.

### 14.1 A surface pattern match is not a diagnosis

A new symptom that resembles a known BL is **not** that BL until proven. Confirm against the
system of record — the database, the raw log, the actual file on disk — not against the narrative
in the log or a prior BL write-up.

- `log/2026-08-11/0016` produced edit failures that looked exactly like BL-193. Querying `cela.db`
  showed the failing `old_text` was present verbatim, which ruled BL-193 out and led to BL-206's
  real cause. Had the resemblance been accepted, the wrong mechanism would have been "fixed".
- A third-party AI's investigation of BL-206 was checked line-by-line against the real tool-call
  arguments in the log and turned out to describe an already-fixed bug (BL-161) that was not in
  play. **Never implement a review finding — from a human, another AI, or yourself — without
  reproducing its evidence in the current code and data.**

### 14.2 Trace a value or requirement back to whoever first produced it

When something wrong appears in the output, find **the first agent/turn that introduced it**, not
the last one that carried it. A single symptom (over-strict acceptance criteria) was attributed to
three different producers across three attempts because the search stopped at whoever most recently
mentioned it (BL-196 → BL-197 → D-169). Read backwards through the log until you reach the origin.

### 14.3 The absence of an expected log line is evidence

Two root causes (BL-211, and the BL-210 vs BL-211 distinction) were isolated by noticing that a
message which *should* have been printed was missing — a rejection log that never appeared, a
safety-net notice that fired zero times. When diagnosing, ask explicitly: "if my hypothesis were
true, which log line would exist?" Then grep for it and count the hits.

### 14.4 Checkpoint restore does not roll back the database

LangGraph checkpoint resume restores conversation/graph state only. `cela.db` (agreements,
whiteboards, issues, verified facts) is **not** rewound. When resuming from a checkpoint to
reproduce or recover, inspect and if necessary correct the DB rows explicitly — see §18.3 for the
safety protocol.

### 14.5 A live run keeps moving

When investigating a dry-run that is still executing, re-read the tail of the log (and re-check the
file mtime) rather than reasoning from a single snapshot. Several findings depended on noticing
that the failure was *still recurring right now*.

---

## 15. Single Source of Truth for Rules and Invariants

The most frequently recurring defect class in this project — distinct from §13 — is **the same rule
expressed in more than one place, with one copy left un-updated**.

### 15.1 One rule, one place

If a rule, threshold, predicate, or gate exists in two locations (two prompts, a prompt and a
mechanical check, two nodes, two write paths), it *will* drift. Prefer a single shared predicate or
helper that both sites call. When duplication is genuinely unavoidable, record in `decision_log.md`
where every copy lives, and update them together.

Real instances: prompt text and mechanical gate disagreeing about whether an issue was deferred
(BL-207); the "nag" set and the "count as stalled" set using different predicates (D-163); an
acceptance-ceiling rule present on two of three request-producing paths (D-182); a tool's role
description present in the schema but absent from the node prompts that actually use it (D-179).

### 15.2 Enumerate every path that can produce the condition

Before declaring a guard complete, **list every source that can trigger what you are guarding
against**, and verify the guard covers all of them. "The most reasonable-looking place" is usually
not the only place.

- Over-strict requirements could originate from `task_planner`, from User AI, *and* from
  `focus_guidance`; fixing the first two left the third wide open (D-182).
- Unachievable acceptance criteria needed suppression on both the producing side and the reviewing
  side; either alone was insufficient (D-169).
- A transition guard checked only one of two mutually exclusive block flags, and the tests
  inherited the same blind spot — producing a false sense of protection (BL-181 follow-up).

**Partial protection is more dangerous than none, because it stops the search.**

### 15.3 Prefer mechanical verification over an agent's self-report

Where a fact can be checked in code, check it in code. Do not accept an agent's claim that it
performed an action, satisfied a constraint, or updated a record. When a mechanical check and a
prompt instruction both express a rule, the mechanical check is authoritative and the prompt must be
written to agree with it (BL-091/176/179/180, D-177).

Corollary: do not re-introduce an LLM into a mechanical last line of defence.

### 15.4 入り口を考えたら必ず出口（消費経路）も考えろ — a record with no consumer is not a mechanism

本プロジェクトでは繰り返し、「記録を作るだけで、それを読む出口（消費経路）を忘れた」ために、
仕組みが何もしないまま終わることが起きた（BL-136/145/154/163/168 の連鎖）。

**鉄則: 入口（書き込み口）を考えるときは、必ず出口（消費経路・出靴）も同時に考える。**
レコードや機構を追加するときは、同じ変更の中でその消費経路を設計・実装せよ——プッシュ
（強制的に読ませる）か、具体的なコード経路が常に読むプル（demonstrable pull）のかたちで。
それができない場合は、「監査のみ（audit-only）」であることを明示せよ。

**フォールバックの経路を確認せよ**: フォールバック（None / 空文字 / スキップ / デフォルト値への
巻き戻し等）を設ける際は、そのフォールバックが**どの経路で・なぜ発生するか**を特定せよ。
例：タスクプラン段階（頭のタスクプランナー）では `task_id` が付かない。このフォールバックによって、
入口や出口が塞がれないか（= 記録が欠損して後続ノードが「出所不明」になる等）を確認せよ。
これは §13（LLM 出力の空文字等の扱い）とも連動する。

**エッジケースは設計で潰せ**: 正常系・準正常系（quasi-normal：境界値や部分的な入力など、一見
正常だが推敲を要するケース）・異常系の3区分でテストを想定し、実装前の設計段階でエッジケースを
潰しておくこと。詳細は §17（テスト規律）も参照。

### 15.5 Prefer an invariant that cannot drift over a threshold that can

When a behaviour depends on a magic boundary (a character count, a version number), ask whether a
structural property (a role, a table's existence, a type) expresses the same intent. A protection
keyed on "≤200 characters" caused a regression whose fix was to key it on caller role instead
(BL-179/180). Thresholds silently stop matching reality; structural properties do not.

---

## 16. Proposing, Reviewing, and Reporting Honestly

### 16.1 Do not implement a proposal — including the user's — without weighing lighter alternatives

When the user proposes a solution, evaluate whether its weight matches the problem, and present a
lighter alternative with trade-offs before implementing. Then let the user decide. This has
repeatedly produced better outcomes than compliance (RAG/embedding → simpler retrieval; browser
automation → lighter fetch strategy; a new task-transition backroute → reuse of existing wiring).
Presenting an alternative is not refusal — always state a recommendation and leave the final call
to the user.

### 16.2 Verify review findings against the code before accepting them

Findings from an independent review (another AI, a subagent, a fresh session) are input, not
instruction. Reproduce each claim against the current source and data. Accept, reject, or
**re-frame** each one explicitly, and say which you did. Two review findings were correct in
substance but pointed at the wrong cause, and the right response was to remove the underlying
design inconsistency rather than apply the suggested patch.

Conversely, for high-stakes review of this system's own behaviour, proactively tell the user when
an independent reviewer (fresh session or different model) would be more reliable than continuing
in the current context — a long session accumulates continuity bias, which is precisely the failure
mode CELA's own Detector architecture exists to counter.

### 16.3 Say what you do not know

If the root cause is not established, file the BL with the cause marked unknown and describe
exactly what was ruled out and how. Do not manufacture a plausible cause to close the item. An
honestly-`open` BL-206 was more useful than a confident wrong attribution would have been.

Report outcomes as they are: if tests fail, show the output; if a step was skipped, say so; if a
previous fix of yours turns out to be incomplete, surface it yourself before being asked.

### 16.4 Re-read the source before acting on an earlier decision

After context compaction, or across turns, do not reconstruct a previously-agreed specification from
memory of its principles — quote the design document or the user's own message verbatim. A
reconstructed ordering that was principle-correct still diverged from what the user had already
fixed (BL-179 planning incident).

### 16.5 Ask whether the work is needed before optimising how it is done

When facing a large refactor to fix a symptom, first ask whether the problematic step is required at
all on this path. One planned large migration (BL-043) was avoided entirely by noticing that the
duplication it was meant to make safe was unnecessary to begin with.

### 16.6 Fixing a bug and preventing its class are different tasks

After a defect class has been identified (§13/§15), do not move straight to the next fix. Propose
whether the lesson should be institutionalised — as a shared helper, a test, or a rule in this file
— and where it belongs among the documentation layers of §4. This escalation was requested by the
user rather than offered by the AI (D-189); treat that as a standing prompt to offer it.

---

## 17. Testing & Verification Discipline

### 17.1 A regression test must fail when the fix is reverted

For every bug fix, revert the fix in a scratch copy, run the new test, and confirm it fails. Then
restore and confirm it passes. If the fix touches several places, **revert each place separately** —
this proves each part is independently necessary and catches tests that only appear to cover the
defect.

Where a test must reproduce node-internal branching rather than call it directly, additionally
assert via `inspect.getsource` that the production code still contains the wiring — otherwise the
test keeps passing after the real code path is removed.

### 17.2 Passing mocked tests is not evidence that it works

Unit tests with mocks verify your code's shape, not the external world's behaviour. For anything
touching an external service, format, or model, perform a real end-to-end check before reporting
completion. A scraping integration passed all mocked tests and was blocked immediately in practice
— discovered only because a live check was run before declaring it done.

### 17.3 Test-run cadence

- After each code edit: `python -m py_compile <file>` plus **only** the offline tests covering the
  change.
- At milestones / before commit: the full offline suite.
- `tests/test_f26_detection.py` makes live LLM calls, and one test in
  `tests/test_bl168_verified_facts_stale_after_goal_revision.py` is timing-flaky. A failure in those
  alone is not necessarily a regression — rerun in isolation before investigating.

Full offline suite:

```
python -m pytest tests/ -q \
  --deselect tests/test_bl168_verified_facts_stale_after_goal_revision.py::test_revise_goal_marking_is_idempotent_on_repeated_revision \
  -k "not test_f26_detection"
```

### 17.4 Never use bare substrings in `-k` exclusion filters

`pytest -k` matches substrings. `-k "not live"` silently deselects every test whose name contains
`deliverable` (de**live**rable), which hid newly added tests behind an unchanged pass count for an
entire session. Use `--deselect <file>::<test>` or `--ignore <file>` for exclusions. **Before
trusting a "full suite passed" report, confirm the deselected count is what you expect.**

### 17.5 Calculations must be executed, not reasoned

Restating §5.1 because it is easy to violate: any arithmetic — however trivial, and including
numbers taken from constraints, comments, or logs — must be computed by running code, never by
inference.

---

## 18. Working Tree, Git, and Live-Run Hygiene

### 18.1 Verify the git baseline before implementing

Before starting implementation, run `git log --oneline -20` and compare it against what
`docs/design/STATUS.md` / `issue_backlog.md` claim **and** against the working-tree files. A
coherent-looking agreement between the docs and the working tree is not proof that either matches
`HEAD` — this project's own dry-run procedure uses `git checkout <sha> -- <file>`, which leaves the
tree stale relative to `HEAD` without moving it. An entire phase was once re-implemented on top of a
reverted snapshot because this check was skipped. If a mismatch is found, stop and ask before
writing code.

### 18.2 Commit at milestones without waiting to be reminded

Proactively propose committing when a BL reaches `done`, a design phase completes, or work shifts to
a substantially different area. Stage specific files rather than `-A`, review what is staged, and
surface anything unexpected in `git status` before committing. Do not push without separate explicit
permission.

Note that `docs/design/**` is auto-committed by a background hook; source and test files are not,
and must be committed explicitly.

### 18.3 Back up before any destructive correction of run state

Before deleting or rewriting rows in `cela.db`, or discarding uncommitted work, back up the target,
state the exact scope (row counts, file list) to the user, and obtain approval. Prefer official APIs
(LangGraph state updates) over raw SQL when correcting a live run.

---

## 19. Independent Design Review via Cline CLI (Plan -> Cline Review -> Re-plan)

For non-trivial plans (a Plan-mode design, a `docs/design/back_log/BL-xxx/BLxxx_basic_design.md`,
or a phase-level `cela_phaseN_design_vX.md`), get an independent review from Cline — a separate
agent/model running non-interactively via its CLI — and fold its findings into the plan **before
calling `ExitPlanMode`**. This operationalizes §16.2 (verify review findings against the code) with
a review source that has no continuity bias from this session.

This is a two-part gate, not one: §19.1 covers reviewing the plan before implementing, §19.4
covers reviewing the diff after implementing. **They are independent obligations.** A change with
no plan doc still owes the diff a review (§19.4) — plan-mode usage is not the trigger for either
half, non-triviality is.

**Sequencing is mandatory, not advisory (established 2026-08-31 after a violation):** `ExitPlanMode`
is what hands the plan to the user for approval. If the Cline review happens *after* `ExitPlanMode`
is called, the user is being asked to approve a plan that was never actually reviewed — Cline's
findings, however good, arrive too late to shape what the user is looking at. Never call
`ExitPlanMode` for a non-trivial plan without having already run §19.1's review and folded the
surviving findings in. If you notice you are about to call `ExitPlanMode` and have not yet run the
review, stop, run it, revise the plan, and only then call `ExitPlanMode`.

### 19.1 How to invoke it

```
python scripts/cline_review.py <path-to-plan.md> [--thinking none|low|medium|high|xhigh] [--timeout SECONDS]
```

Default `--thinking` is `high` (per user decision 2026-08-31 — plan/implementation review benefits
from more reasoning effort than the default `medium`).

The script prints Cline's review text to stdout (nothing else). Read it, verify each claim against
the actual code/docs per §16.2, and fold what survives verification back into the plan — do not
paste the review to the user unfiltered and do not treat it as authoritative. Do this before
calling `ExitPlanMode` (see the sequencing note above), not after.

`--timeout` is the budget given to the `cline` CLI itself (`-t`); the Python subprocess call waits
`--timeout + 30`s before giving up, so a slow review surfaces as a `cline CLI exited`/`did not
finish` error rather than a silent hang — no extra margin needs to be added by the caller.

### 19.2 Safety posture (do not change without user approval)

Cline is invoked with `--auto-approve true`, but its local config
(`~/.cline/data/globalState.json` -> `autoApprovalSettings.actions`) is kept with `editFiles`,
`editFilesExternally`, and `executeAllCommands` forced to `false`. `readFiles`, `readFilesExternally`,
`executeSafeCommands`/`useMcp`, and (per user decision 2026-08-31) `useBrowser` stay auto-approved.
This makes Cline unable to mutate the repo it is reviewing *through its dedicated file-edit
tools* — `editFiles`/`editFilesExternally`/`executeAllCommands` are forced off, so it cannot
open-and-save a file or run an arbitrary/unrestricted command. It is not, however, strictly
read-only: `executeSafeCommands` stays auto-approved (needed for the valuable case of Cline
actually running Python to verify its own review claims — this caught real edge-case bugs in
2026-08-31's BL-326/327 reviews), and a "safe" shell command can itself write files (observed in
practice: Cline wrote two disposable verification scripts under `artifacts/` via a shell
one-liner during a review, with `editFiles` confirmed still `false` at the time). Treat this as
"cannot edit tracked files through its own tools, but *can* write scratch files via shell" rather
than "never writes anything" — check `git status` after any Cline review invocation and clean up
or inspect anything unexpected before trusting the working tree, per §16.2. Revisited and kept
as-is (accepted trade-off, favoring the execution-verification value) 2026-08-31; see
`decision_lineage.md` 論点170/171 for the fuller discussion. Both `scripts/cline_review.py` and
`scripts/cline_review_diff.py` (§19.4) share this config and must never be changed to grant
edit/execute-all write-back access without an explicit, separate user decision recorded in
`decision_log.md`.

**Self-enforcing, because the config can drift.** `~/.cline/data/globalState.json` is one
machine-wide file shared by *every* Cline CLI invocation on the machine, including other, unrelated
Claude Code sessions running concurrently against this or another repo. On 2026-08-31 this file was
found reset to all-`true` (write actions included) partway through a session, with a concurrent
session's own Cline usage as the likely but not fully confirmed cause. Because the file cannot be
trusted to stay as last set, `cline_review.py`'s `_ensure_readonly_auto_approve()` re-asserts
`editFiles`/`editFilesExternally`/`executeAllCommands` = `false` immediately before every single
Cline invocation (both scripts call it, since `cline_review_diff.py` goes through
`cline_review.invoke_cline`). Do not remove this call, and do not assume the file's on-disk state
reflects what was last configured — re-read it if reasoning about current safety posture.

If another Claude Code session is running Cline reviews against this repo at the same time, treat
that as a real possibility, not a hypothetical — check `cline history --json` (look at `status`,
`source`, and `cwd`/`prompt`) before assuming a stray file or an unexpected auto-approve value came
from this session's own actions.

### 19.3 Known constraints (established 2026-08-31, do not rediscover by trial and error)

- **Never pass `-p`/`--plan` to the `cline` CLI in this workflow.** Cline has its own plan/act mode;
  in plan mode it presents a plan and then stops, waiting for a human to approve switching to act
  mode. Combined with non-interactive/headless invocation this hangs indefinitely (observed: a task
  sat unanswered for 7+ minutes before being force-terminated by Cline's own stale-session
  reconciler). Plain act-mode invocation (no `-p`) is what `scripts/cline_review.py` uses, and is
  safe here because write actions are already disabled per §19.2.
- The Cline CLI and the Cline VS Code extension share one local hub daemon per workspace
  (`ws://127.0.0.1:<port>`, `cline hub status`). A CLI task can therefore surface inside the VS Code
  extension's chat UI for the same workspace.
- `-z`/`--zen` (documented as "run in the background hub") timed out with `zen_error` on CLI v3.0.60
  and is not a working workaround for the above — do not rely on it without re-verifying against a
  newer CLI version first.
- The CLI resolves to `cline.cmd` on Windows via npm global install; a plain
  `subprocess.run(["cline", ...])` fails to find it. Resolve the real path with `shutil.which("cline")`
  first (already done in `scripts/cline_review.py`).
- Auth is a device-code flow (`cline auth --provider cline`, prints a URL + code); it requires a
  human to complete the login in a browser and cannot be scripted further.

### 19.4 Implementation review (diff-based)

Run this after implementing *any* non-trivial change — this is the "Cline(review)" step for
implementation, not just design. **Whether the change went through Plan mode / has a plan doc is
not the criterion for whether to run this step.** A fix that felt too small to write a plan for is
not, by itself, a reason to skip the review — the criterion is whether the diff is worth a second
pair of eyes, and Cline is free (this provider's cost is $0), so the honest default is to run it
whenever there is a non-trivial diff, plan or no plan. Skip only for genuinely trivial edits (typo
fixes, comment-only changes, pure formatting, doc-only wording tweaks). This was established
2026-08-31 after a plan-less small fix was implemented and committed without a Cline review because
the absence of a plan was (wrongly) treated as the absence of an obligation to review — do not
repeat that reasoning.

```
python scripts/cline_review_diff.py [--range RANGE] [--path PATH ...] [--plan PLAN_FILE ...] \
    [--thinking LEVEL] [--timeout SECONDS]
```

- `--range` is passed straight to `git diff` (e.g. `HEAD~1`, `main...HEAD`, `--staged`); omitted,
  it reviews the working tree against `HEAD` (uncommitted changes — the common case right after
  implementing).
- `--path` restricts the diff to specific files/dirs (repeatable).
- `--plan` names the plan/design doc(s) this implementation is supposed to satisfy (repeatable);
  when given, Cline is asked to check the diff against the plan for gaps, not just for bugs in
  isolation. Omit it when there is no plan doc for the change.
- The diff is written to a temp file (outside the repo) and Cline is pointed at that file rather
  than having the diff text pasted into the prompt — keeps the invocation working for diffs of any
  size and avoids shell-escaping the diff content. This relies on `readFilesExternally: true`
  staying enabled per §19.2.
- Same output contract as §19.1: review text on stdout only, verify each claim against the actual
  diff/code per §16.2 before acting on it, and don't accept it as authoritative.
- `git diff` with no changes in range/paths raises an error (nothing to review) instead of calling
  Cline with an empty diff.
