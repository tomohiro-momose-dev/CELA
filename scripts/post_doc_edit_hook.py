"""PostToolUse hook: after docs/design/*.md is edited, lint and auto-commit.

Shared logic for two different harnesses, each with its own JSON contract:
  - Claude Code: payload has "tool_input"/"tool_response"; output (if any)
    is a {"systemMessage": ...} object, printed only on failure.
  - cline: payload has "postToolUse" (schema verified empirically via
    .clinerules/hooks/last_input.json, since docs.cline.bot did not render
    for WebFetch); output MUST always be a
    {"cancel": bool, "contextModification": str, "errorMessage": str}
    object, per .clinerules/hooks/PostToolUse.ps1's template contract.

If the edited file is under docs/design/ and is markdown, runs
scripts/check_docs_consistency.py; on success, stages and commits only
docs/design/ changes. On failure, the working tree is left dirty (nothing
is committed) and the failure is reported back through the calling
harness's own channel instead of being silently skipped.

[CONSTRAINT] Scope is intentionally limited to `docs/design` — this hook
must never stage or commit source files (e.g. cela_main.py). That boundary
was an explicit user decision: auto-commit covers documentation only, and
push is never automated.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "design"
CLINE_WRITE_TOOLS = {"write_to_file", "replace_in_file", "multi_apply_diff"}

CLINE_NOOP = {"cancel": False, "contextModification": "", "errorMessage": ""}


def extract_target_path(payload: dict) -> tuple[Path | None, str]:
    """Returns (resolved_path_or_None, harness) where harness is 'claude' or 'cline'."""
    if "postToolUse" in payload:
        ptu = payload["postToolUse"]
        if ptu.get("toolName") not in CLINE_WRITE_TOOLS:
            return None, "cline"
        rel_path = ptu.get("parameters", {}).get("path")
        roots = payload.get("workspaceRoots") or []
        if not rel_path or not roots:
            return None, "cline"
        candidate = Path(roots[0].replace("\\", "/")) / rel_path
        return candidate, "cline"

    file_path = (
        payload.get("tool_input", {}).get("file_path")
        or payload.get("tool_response", {}).get("filePath")
        or ""
    )
    if not file_path:
        return None, "claude"
    return Path(file_path.replace("\\", "/")), "claude"


def run_lint_and_commit() -> tuple[bool, str]:
    """Returns (success, message)."""
    lint = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_docs_consistency.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if lint.returncode != 0:
        return False, (
            "docs/design の整合チェックに失敗したため自動コミットをスキップしました。"
            " scripts/check_docs_consistency.py を確認してください。"
        )

    subprocess.run(["git", "add", "docs/design"], cwd=REPO_ROOT, check=False)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", "docs/design"],
        cwd=REPO_ROOT,
    )
    if diff.returncode == 0:
        return True, ""  # nothing staged under docs/design

    subprocess.run(
        ["git", "commit", "-q", "-m", "docs: auto-update docs/design (linted)"],
        cwd=REPO_ROOT,
        check=False,
    )
    return True, ""


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Harness is unknown before parsing, so stay silent rather than
        # guessing which JSON contract to satisfy.
        return 0

    candidate, harness = extract_target_path(payload)

    if candidate is None:
        if harness == "cline":
            print(json.dumps(CLINE_NOOP))
        return 0

    try:
        resolved = candidate.resolve()
    except OSError:
        if harness == "cline":
            print(json.dumps(CLINE_NOOP))
        return 0

    if DOCS_DIR not in resolved.parents or resolved.suffix != ".md":
        if harness == "cline":
            print(json.dumps(CLINE_NOOP))
        return 0

    ok, message = run_lint_and_commit()

    if harness == "cline":
        print(json.dumps({
            "cancel": False,
            "contextModification": "",
            "errorMessage": "" if ok else message,
        }, ensure_ascii=False))
        return 0

    # claude harness: silent on success, systemMessage only on failure
    if not ok:
        print(json.dumps({"systemMessage": message}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
