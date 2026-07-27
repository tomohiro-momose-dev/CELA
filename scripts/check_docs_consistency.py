"""Static consistency linter for docs/design (AGENTS.md documentation model).

Checks (intentionally narrow — structural integrity only, not prose):
  1. Every markdown link that points at another file under docs/design
     resolves to an existing file.
  2. Every '#anchor' in such a link resolves to an actual heading in the
     target file, using an approximation of GitHub's heading-to-anchor
     slug algorithm (lowercase, strip punctuation, spaces -> hyphens).
  3. Every 'decided' entry in decision_log.md has a non-empty 決定理由
     (AGENTS.md §4: "reason for the decision is mandatory").
  4. Every BL-xxx row in issue_backlog.md's summary table has a matching
     '### BL-xxx' detail section, and vice versa.

[CONSTRAINT] Does not parse fenced code blocks separately, so a code
sample containing literal '[x](y)' text could produce a false positive.
Not handled because none of the current docs trigger this; revisit only
if it starts producing noise.

Usage: python scripts/check_docs_consistency.py
Exit code is non-zero if any problem is found (CI / pre-commit friendly).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

DOCS_DIR = Path(__file__).resolve().parent.parent / "docs" / "design"

LINK_RE = re.compile(r"\[[^\]]*\]\(([^)]+)\)")
HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$", re.MULTILINE)
BL_HEADING_RE = re.compile(r"^###\s+(BL-\d+):", re.MULTILINE)
BL_TABLE_ROW_RE = re.compile(r"^\|\s*(BL-\d+)\s*\|", re.MULTILINE)
D_BLOCK_RE = re.compile(r"^###\s+(D-\d+):.*?(?=^###\s+D-\d+:|\Z)", re.MULTILINE | re.DOTALL)
STATE_ROW_RE = re.compile(r"\|\s*状態\s*\|\s*`?(\w+)`?\s*\|")
REASON_ROW_RE = re.compile(r"\|\s*\*\*決定理由\*\*\s*\|\s*(.+?)\s*\|")


def slugify(heading: str) -> str:
    """Approximate GitHub's heading-to-anchor algorithm (unicode-aware)."""
    text = heading.strip().lower()
    text = re.sub(r"[^\w\s\-]", "", text)
    text = re.sub(r"\s+", "-", text)
    return text


def collect_headings(text: str) -> set[str]:
    return {slugify(m.group(2)) for m in HEADING_RE.finditer(text)}


def check_links(problems: list[str]) -> None:
    md_files = sorted(DOCS_DIR.rglob("*.md"))
    heading_cache: dict[Path, set[str]] = {}

    def headings_of(path: Path) -> set[str]:
        if path not in heading_cache:
            heading_cache[path] = collect_headings(path.read_text(encoding="utf-8"))
        return heading_cache[path]

    for md_file in md_files:
        text = md_file.read_text(encoding="utf-8")
        for match in LINK_RE.finditer(text):
            target = match.group(1)
            if target.startswith(("http://", "https://", "mailto:")):
                continue
            file_part, _, anchor = target.partition("#")
            if file_part:
                target_path = (md_file.parent / file_part).resolve()
                if not target_path.exists():
                    problems.append(f"{md_file}: リンク先ファイルが存在しません: {target}")
                    continue
            else:
                target_path = md_file
            if anchor and target_path.suffix == ".md" and target_path.exists():
                if anchor not in headings_of(target_path):
                    problems.append(
                        f"{md_file}: アンカーが見つかりません: {target} (in {target_path.name})"
                    )


def check_decision_reasons(problems: list[str]) -> None:
    path = DOCS_DIR / "decision_log.md"
    text = path.read_text(encoding="utf-8")
    for m in D_BLOCK_RE.finditer(text):
        d_id = m.group(1)
        block = m.group(0)
        state_m = STATE_ROW_RE.search(block)
        reason_m = REASON_ROW_RE.search(block)
        if state_m and state_m.group(1) == "decided":
            reason = reason_m.group(1).strip() if reason_m else ""
            if not reason or reason.startswith("**（"):
                problems.append(f"decision_log.md: {d_id} は decided だが決定理由が空です")


def check_bl_table_vs_sections(problems: list[str]) -> None:
    path = DOCS_DIR / "back_log" / "issue_backlog.md"
    text = path.read_text(encoding="utf-8")
    table_ids = set(BL_TABLE_ROW_RE.findall(text))
    section_ids = set(BL_HEADING_RE.findall(text))
    for bl_id in sorted(table_ids - section_ids):
        problems.append(f"issue_backlog.md: 優先対応一覧に{bl_id}があるが詳細セクションがありません")
    for bl_id in sorted(section_ids - table_ids):
        problems.append(f"issue_backlog.md: 詳細セクションに{bl_id}があるが優先対応一覧に行がありません")


def main() -> int:
    problems: list[str] = []
    check_links(problems)
    check_decision_reasons(problems)
    check_bl_table_vs_sections(problems)

    if problems:
        print(f"[NG] {len(problems)}件の不整合が見つかりました:\n")
        for p in problems:
            print(f"  - {p}")
        return 1

    print("[OK] docs/design の相互リンク・必須項目に不整合はありません")
    return 0


if __name__ == "__main__":
    sys.exit(main())
