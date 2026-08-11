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
