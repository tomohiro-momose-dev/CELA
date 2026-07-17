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


## 2. Documentation Model (Source of Truth)

**MANDATORY for every request that changes requirements, design, or implementation tasks.**

### Core rules

1. **Source of truth** for requirements and design is `docs/design`, **not** a GitHub Issue body (if any).
2. **Starting point** for a greenfield project: `docs/要件定義.md`.
3. **Before coding or design edits:** read `STATUS.md` → `要件定義.md` `cela_roadmap_vXX.md`→ `issue_backlog.md` → `phase_gates.md` (and the relevant `phaseN/` doc).
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
   
## 3 Coding, Thinking Analysing
1. **Calculations** 
　　In principle, LLMs are incapable of performing calculations. 
    Whenever a task requires calculation—whether based on premises, constraints, code comments, or numerical values ​​embedded in the code—the model must invariably invoke a Python tool, generate mechanical calculation code, and perform both the calculation and verification, even for simple operations like addition.

2. **Grounded Architecture & Verification**
   - **No Guessing/Fabricating:** NEVER assume or guess the existence of any API, library, or framework feature. Use official, up-to-date syntax. If you are unsure of a function signature or version-specific API, stop and ask the user or verify it using search/read tools first.
   - **Controlled Dependencies:** Do not arbitrarily import uninstalled packages. When a new library/dependency is required:
     1. Propose the specific package and explain why it is necessary.
     2. Ask for user approval, OR explicitly add it to the package configuration file (e.g., package.json, requirements.txt, go.mod) and run the install command before importing it in your code.

3. **Design Before Implementation (For New Features)**
   - **Blueprint First:** Before creating new files or writing large blocks of new code, briefly present your plan:
     1. Proposed file structure and where the new code fits.
     2. Key architectural choices (e.g., state management, design patterns).
     3. Integration points with the existing code (if any).
   - **Style Consistency:** Follow the existing project's directory structure, naming conventions, and coding style.

4.  **Code Quality & Completeness**
    - **No Lazy Placeholders:** Never use placeholders like `// ... existing code ...` or `// TODO: implement` inside modified or newly created files. Always output complete, fully functional, and syntactically valid code blocks.
  
5.  **Communication Preference**
    - **Language:** Always explain your plans, logic, and reasoning in Japanese. Keep the actual code, variables, and technical terms in English.

**Index:** `docs/design/README.md`

| Layer | File / location | Role |
|-------|-----------------|------|
| Requirements start / working master | `要件定義.md` | Background, tasks, acceptance criteria |
| Phase design | `phaseN/` | How, constraints, tests |
| Implementation tasks | `issue_backlog.md` | BL-xxx bugs and open items |
| Decisions (why) | `decision_log.md` | Mandatory rationale |
| Progress | `STATUS.md`, `phase_gates.md`, `traceability.md` | Where we are / Done / coverage |
| Optional epic entry | GitHub Issue (short) | Link to docs only |

Optional GitHub Issue: summary + link to `docs/design/README.md` only. Do **not** treat Issue comments as the requirements master.

---

## 3. Code Comments — "Why" Over "What"

- Never write comments that only paraphrase syntax.
- Comments must explain **intent, constraints, rejected alternatives**.
- Update adjacent comments when code changes (**no stale comments**).
- Prefer tags for critical notes: `[CONSTRAINT]`, `[SAFETY]`, `[REJECTED]`.

Module / class / function docs should describe purpose and non-obvious assumptions.

---

## 4. Constant Modifications (Strict Control)

- **Prior approval required** before changing critical constants (buffer sizes, array lengths, timeouts, protocol magic values, etc.).
- State the reason and obtain **explicit written approval** from the user.
- Do **not** change these unilaterally.

---

## 5. Issue & Backlog Management

- Implementation leftovers → `docs/design/issue_backlog.md` as BL-xxx.
- Do **not** dump implementation bugs into `要件定義.md`.
- Review findings → BL entries; freeze detailed review archives under `phaseN/` if needed.

---

## 6. Minor / Niche Languages — Official Reference First

When writing or modifying code in a **minor or niche language** (vendor DSL, macros, uncommon scripting, etc.):

1. **Before naming APIs/commands:** fetch the **official reference** (web search / fetch) — not memory alone.
2. **Cache locally:** save excerpts under `docs/refs/<tool>/` with source URL and fetch date.
3. **Reuse the cache** on later turns unless the API is unclear or the manual may have changed.
4. **Sync design docs** that name commands/APIs against the cached reference before coding.

Prefer well-supported host languages (e.g. Python, C#) for tooling when a niche language repeatedly causes hallucination or validation cost.

---

## 7. Test / Dry-run Notes Placement

| Content | Where |
|---------|--------|
| Pass/fail summary | `traceability.md` (T-*) |
| Failures / next fixes | `issue_backlog.md` (BL-*) |
| Procedure / environment detail | `phaseN/phaseN_dryrun.md` (create when needed) |
| Raw logs | project-specific log directory (e.g. `artifacts/`, `drive/`) |

---

## 8. Writing the Summary (generated code)

Place a short purpose comment / docstring immediately before generated functions, classes, or non-trivial blocks, appropriate to the language.

## 9. Autocomplete & Inline Comment Generation Rules (CRITICAL)

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