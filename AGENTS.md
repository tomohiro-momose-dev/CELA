---
description: Project agent rules — MCP workflow, Code Modification & Implementation Guidelines, minor-language references
alwaysApply: true
---

## Codebase Memory MCP

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

## Code Modification & Implementation Guidelines

### **1\. Core Mandate: "Why" Over "What"**

You must **NEVER** write comments that simply paraphrase the syntax or describe *what* the code is doing. The code itself explains the "What". Your comments must explain the **"Why"**—the intent, the architectural decisions, the physical constraints, and the alternative solutions that were rejected.

* **Do not write:** \# Open the serial port (This is obvious from the code).  
* **Do write:** \# Configure timeout=0 (non-blocking) to prevent the background thread from blocking the GUI event loop if the device goes offline (This explains the engineering decision).

### **2\. Documenting Hierarchy**

You must structure your comments at three levels of granularity:

#### **A. Module-Level Docstring (The File Header)**

Every single file must start with a module-level docstring containing the "worldview" of the file. This must be written before any imports.  
Include the following sections:

* **\[Purpose\]**: What is the ultimate business/technical goal of this file?  
* **\[System & Communication Spec\]**: What external systems, hardware, or APIs does this interact with? What are their specifications?  
* **\[Core Constraints & Why\]**: What are the critical, uncompromisable design decisions (e.g., multi-threading, memory limits) and *why* were they made?

#### **B. Class & Function Docstrings**

Before class definitions or function bodies, write a docstring focusing on **Design Intent**.

* Explain what problem this function solves in the grand scheme.  
* Describe any non-obvious side effects.  
* Highlight any specific assumptions about the input state.

#### **C. Inline Comments (Use Sparingly)**

Only use inline comments for:

* **Magic numbers**: Explain *why* that specific value is used (e.g., hardware buffer limits).  
* **Workarounds/Hacks**: Explain *why* a seemingly sub-optimal approach was used (e.g., bypassing a known hardware bug).  
* **Interlock/Safety Logic**: Explain *why* certain UI elements are disabled or locked.

### **3\. Reference Examples for AI Writing**

| Comment Type | ❌ BAD (What) | GOOD (Why / Intent) |
| :---- | :---- | :---- |
| **I/O & Hardware** | self.ser.write(b"EOF") *(Obvious syntax paraphrase)* | \# Send "EOF" packet to signal the end of the binary stream so the device FS can close the file handler. |
| **Threading** | with self.buffer\_lock: *(Describes the syntax)* | \# Guard self.rx\_buffer with a mutex to prevent race conditions between the Receiver and Automation threads. |
| **Performance** | self.rx\_buffer \= self.rx\_buffer\[length:\] *(Describes array slicing)* | \# Silently discard (drain) the readback payload from memory to prevent Tkinter rendering lag or OOM crashes. |
| **User Interface** | self.btn\_start.config(state=tk.DISABLED) *(Obvious UI action)* | \# Interlock safety: Lock the start button to prevent duplicate triggers and command stream corruption. |

### **4\. The "Zero Stale Comments" Policy**

* When you modify, optimize, or rewrite any block of code, you **MUST** review all adjacent comments.  
* If the code's behavior changes, you must immediately update the comments to ensure they remain 100% truthful.  
* If a comment no longer aligns with the updated code, rewrite it immediately. **A stale comment is worse than no comment at all.**

### **5\. Metadata Tags for High-Attention Warnings**

When documenting critical constraints that other developers (or future AI runs) must not touch, prefix your inline comments with these standardized tags:

* \# \[CONSTRAINT\]: Hard limits imposed by hardware, OS, or third-party APIs.  
* \# \[SAFETY\]: Logic preventing physical hazards, user data loss, or UI freezes.  
* \# \[REJECTED\]: Explains *why* an alternative, seemingly better solution failed during testing.


### **6. Constant Modifications (Strict Control)**
* **Prior Approval Required:** BEFORE modifying any critical constants—including but not limited to **buffer sizes, array lengths, and timeout values**—you must explicitly state the reason for the proposed change and **obtain explicit, written approval from the user**.
* **DO NOT** alter these configuration values unilaterally without prior consent.

### **7. Issue & Backlog Management**
* **Task Handover:** At the end of each implementation step, if there are any remaining unimplemented features, edge cases, or known issues, you must append them to `docs/design/<feature_name>/issue_backlog.md` as BL-xxx entries.
* This backlog must be structured clearly so that the next implementation turn can pick up remaining work.
* **Do not** treat GitHub Issue #1 as the detailed requirements master. Follow the documentation model in `docs/design/<feature_name>/README.md`.

## MAC Address Feature — Documentation Model (`docs/design/mac_addr_impl(<feature_name>)/`)

| Layer | File / location | Role |
|-------|-----------------|------|
| Epic entry | GitHub Issue #1 | Summary, completion criteria, link to docs |
| Requirements integration | `issue#1 mac_address_setting_and_storage.md` | **Working master during design** — update when refining requirements with the user |
| Phase design | `phaseN/` | How, constraints, tests per phase |
| Implementation tasks | `issue_backlog.md` | BL-xxx bugs, open items, not requirements |
| Decisions (why) | `decision_log.md` | Record after resolving BL "undecided" items |
| Progress | `STATUS.md`, `phase_gates.md`, `traceability.md` | PM artifacts |

**When changing requirements or constraints:**
1. Update `issue#1 ...md` and the relevant `phaseN/` doc.
2. Record decisions in `decision_log.md`. **`決定理由` is mandatory** for every `decided` entry — include why this option was chosen and why alternatives were rejected.
3. Add implementation follow-ups to `issue_backlog.md` (BL), not into the issue#1 narrative.
4. Sync GitHub Issue #1 summary only at milestones — not on every edit.

**Index:** `docs/design/mac_addr_impl(<feature_name>)/README.md`

## Minor / Niche Languages — Official Reference First

When writing or modifying code in a **minor or niche language** the model is not confident about (e.g. TeraTerm TTL `*.ttl`, Mbed-specific macros, vendor DSLs):

1. **Before implementation or design that names APIs/commands:** use **web search** (or fetch) against the **official reference** — not memory, not project docs alone.
2. **Cache locally:** save the relevant official excerpts under `docs/refs/<tool>/` (command syntax, examples, version notes). Record source URL and fetch date in that file.
3. **Reuse the cache:** on later turns, read the local file in `docs/refs/` first instead of re-fetching the same pages unless the API is unclear or the manual may have changed.
4. **Sync project docs:** if design docs (`decision_log.md`, `phaseN/`, `issue_backlog.md`) name a command/API, verify it against the cached reference before coding.

## Autocomplete & Inline Comment Generation Rules (CRITICAL)

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

### 3. Quick-Start Metadata Triggers
Train your suggestions to proactively offer metadata tags (`[CONSTRAINT]`, `[SAFETY]`, `[REJECTED]`) as autocompletion options as soon as the user types `# [`.
"""
## Note

**This repo — shipment host tool:** Primary is Python [`drive/mac_config_writer.py`](drive/mac_config_writer.py) ([D-010](docs/design/mac_addr_impl(<feature_name>)/decision_log.md)). Prefer Python/C# for new host-side factory tooling over niche macro languages.

**This repo — TeraTerm TTL (archive only):** see `docs/refs/teraterm/`. Shipment macros are **not** the source of truth after D-010. If editing `*.ttl` for reference, still follow the official-reference cache rules above (`logmsg` does not exist; use `logopen`/`logwrite`/`logclose`).

