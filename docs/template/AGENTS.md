---
description: Project agent rules — docs model, code comments, constants, niche-language refs
alwaysApply: true
---

# Agent Rules (Project Template)

Copy this file to the **repository root** as `AGENTS.md`.  
Replace `FEATURE_NAME` with the real feature directory name under `docs/design/`.

---

## 1. Documentation Model (Source of Truth)

**MANDATORY for every request that changes requirements, design, or implementation tasks.**

### Core rules

1. **Source of truth** for requirements and design is `docs/design/FEATURE_NAME/`, **not** a GitHub Issue body (if any).
2. **Starting point** for a greenfield project: `docs/design/FEATURE_NAME/要件定義.md`.
3. **Before coding or design edits:** read `STATUS.md` → `要件定義.md` → `issue_backlog.md` → `phase_gates.md` (and the relevant `phaseN/` doc).
4. **Layers must not mix:**
   - Requirements narrative → `要件定義.md`
   - How / constraints / tests → `phaseN/`
   - Implementation tasks / bugs → `issue_backlog.md` (BL-xxx)
   - Decisions (Why) → `decision_log.md` (D-xxx) — **`決定理由` is mandatory** for every `decided` entry
   - Progress → `STATUS.md` / `phase_gates.md` / `traceability.md`
5. **When changing requirements or constraints:**
   1. Update `要件定義.md` and the relevant `phaseN/` doc.
   2. Record decisions in `decision_log.md` (why chosen + why alternatives rejected).
   3. Add implementation follow-ups to `issue_backlog.md` (BL), not into the requirements narrative.
   4. Sync any GitHub Issue **summary only at milestones** — not on every edit.
6. **End of each implementation turn:** append remaining work, edge cases, and known issues to `issue_backlog.md` as BL-xxx.

**Index:** `docs/design/FEATURE_NAME/README.md`

| Layer | File / location | Role |
|-------|-----------------|------|
| Requirements start / working master | `要件定義.md` | Background, tasks, acceptance criteria |
| Phase design | `phaseN/` | How, constraints, tests |
| Implementation tasks | `issue_backlog.md` | BL-xxx bugs and open items |
| Decisions (why) | `decision_log.md` | Mandatory rationale |
| Progress | `STATUS.md`, `phase_gates.md`, `traceability.md` | Where we are / Done / coverage |
| Optional epic entry | GitHub Issue (short) | Link to docs only |

Optional GitHub Issue: summary + link to `docs/design/FEATURE_NAME/README.md` only. Do **not** treat Issue comments as the requirements master.

---

## 2. Code Comments — "Why" Over "What"

- Never write comments that only paraphrase syntax.
- Comments must explain **intent, constraints, rejected alternatives**.
- Update adjacent comments when code changes (**no stale comments**).
- Prefer tags for critical notes: `[CONSTRAINT]`, `[SAFETY]`, `[REJECTED]`.

Module / class / function docs should describe purpose and non-obvious assumptions.

---

## 3. Constant Modifications (Strict Control)

- **Prior approval required** before changing critical constants (buffer sizes, array lengths, timeouts, protocol magic values, etc.).
- State the reason and obtain **explicit written approval** from the user.
- Do **not** change these unilaterally.

---

## 4. Issue & Backlog Management

- Implementation leftovers → `docs/design/FEATURE_NAME/issue_backlog.md` as BL-xxx.
- Do **not** dump implementation bugs into `要件定義.md`.
- Review findings → BL entries; freeze detailed review archives under `phaseN/` if needed.

---

## 5. Minor / Niche Languages — Official Reference First

When writing or modifying code in a **minor or niche language** (vendor DSL, macros, uncommon scripting, etc.):

1. **Before naming APIs/commands:** fetch the **official reference** (web search / fetch) — not memory alone.
2. **Cache locally:** save excerpts under `docs/refs/<tool>/` with source URL and fetch date.
3. **Reuse the cache** on later turns unless the API is unclear or the manual may have changed.
4. **Sync design docs** that name commands/APIs against the cached reference before coding.

Prefer well-supported host languages (e.g. Python, C#) for tooling when a niche language repeatedly causes hallucination or validation cost.

---

## 6. Test / Dry-run Notes Placement

| Content | Where |
|---------|--------|
| Pass/fail summary | `traceability.md` (T-*) |
| Failures / next fixes | `issue_backlog.md` (BL-*) |
| Procedure / environment detail | `phaseN/phaseN_dryrun.md` (create when needed) |
| Raw logs | project-specific log directory (e.g. `artifacts/`, `drive/`) |

---

## 7. Writing the Summary (generated code)

Place a short purpose comment / docstring immediately before generated functions, classes, or non-trivial blocks, appropriate to the language.

---

## Optional: Codebase Memory MCP

If this repository uses Codebase Memory MCP, call `list_projects` then `get_architecture` **before** broad code exploration. Otherwise skip this section.
