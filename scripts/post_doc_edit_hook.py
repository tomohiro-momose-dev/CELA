"""PostToolUse hook: after Claude edits docs/design/*.md, lint and auto-commit.

Reads the Claude Code hook payload (tool_name/tool_input) from stdin. If the
edited file is under docs/design/ and is markdown, runs
scripts/check_docs_consistency.py; on success, stages and commits only
docs/design/ changes. On failure, the working tree is left dirty (nothing is
committed) and a systemMessage is emitted so the failure is visible instead
of silently skipped.

[CONSTRAINT] Scope is intentionally limited to `docs/design` — this hook
must never stage or commit source files (e.g. cela_main.py). That boundary
was an explicit user decision (D-014): auto-commit covers documentation
only, and push is never automated.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DOCS_DIR = REPO_ROOT / "docs" / "design"


def main() -> int:
    try:
        payload = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        return 0

    file_path = (
        payload.get("tool_input", {}).get("file_path")
        or payload.get("tool_response", {}).get("filePath")
        or ""
    )
    if not file_path:
        return 0

    candidate = Path(file_path.replace("\\", "/"))
    try:
        resolved = candidate.resolve()
    except OSError:
        return 0

    if DOCS_DIR not in resolved.parents or resolved.suffix != ".md":
        return 0

    lint = subprocess.run(
        [sys.executable, str(REPO_ROOT / "scripts" / "check_docs_consistency.py")],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if lint.returncode != 0:
        print(json.dumps({
            "systemMessage": (
                "docs/design の整合チェックに失敗したため自動コミットをスキップしました。"
                " scripts/check_docs_consistency.py を確認してください。"
            )
        }, ensure_ascii=False))
        return 0

    subprocess.run(["git", "add", "docs/design"], cwd=REPO_ROOT, check=False)
    diff = subprocess.run(
        ["git", "diff", "--cached", "--quiet", "--", "docs/design"],
        cwd=REPO_ROOT,
    )
    if diff.returncode == 0:
        return 0  # nothing staged under docs/design

    subprocess.run(
        ["git", "commit", "-q", "-m", "docs: auto-update docs/design (linted)"],
        cwd=REPO_ROOT,
        check=False,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
