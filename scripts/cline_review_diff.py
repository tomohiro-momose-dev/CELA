"""Send a git diff (optionally alongside its plan doc) to the Cline CLI for
an independent implementation review.

Part of the Claude(plan) -> Cline(review) -> Claude(re-plan) workflow's
implementation-side counterpart: after Claude Code implements a plan, this
script captures `git diff` output, hands it (plus the plan file, if given)
to Cline for review, and prints Cline's review text so Claude Code can act
on it without manual copy/paste. See AGENTS.md 19 for the full workflow and
19.2/19.3 for the safety posture and known constraints shared with
scripts/cline_review.py.

Usage:
    python scripts/cline_review_diff.py [--range RANGE] [--path PATH ...] \
        [--plan PLAN_FILE ...] [--thinking LEVEL] [--timeout SECONDS]

Examples:
    # Review uncommitted changes (working tree vs HEAD)
    python scripts/cline_review_diff.py

    # Review a specific commit range, cross-checked against its plan doc
    python scripts/cline_review_diff.py --range main...HEAD \
        --plan docs/design/back_log/BL-321/BL321_basic_design.md

    # Review staged changes to one file only
    python scripts/cline_review_diff.py --range --staged --path web_tools.py
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from cline_review import ClineReviewError, REPO_ROOT, invoke_cline  # noqa: E402

DIFF_REVIEW_INSTRUCTION_TEMPLATE = (
    "{diff_path} に保存された git diff の出力を読み込んで、直近の実装差分をレビューしてください。\n"
    "{plan_clause}"
    "観点:\n"
    "1. plan との整合性（plan が示されている場合、要求に対する実装の過不足）\n"
    "2. バグ・エッジケースの見落とし・既存動作への悪影響\n"
    "3. 実装漏れ・未完了/半端な実装（TODOやプレースホルダの放置を含む）\n"
    "4. 既存コード/アーキテクチャとの重複・不整合\n"
    "指摘ごとに、該当ファイル名とdiff中の該当箇所を引用し、重大度（重大/中/軽微）を明記してください。\n"
    "あなたはレビューアです。ファイルの編集・作成・コマンド実行による変更は行わず、"
    "レビューコメントのテキストのみを返してください。"
)


def get_git_diff(diff_range: str | None, paths: list[str] | None) -> str:
    """Return the textual output of `git diff` for the given range/paths."""
    cmd = ["git", "diff"]
    if diff_range:
        cmd.append(diff_range)
    if paths:
        cmd.append("--")
        cmd.extend(paths)

    proc = subprocess.run(cmd, cwd=REPO_ROOT, capture_output=True, text=True, encoding="utf-8")
    if proc.returncode != 0:
        raise ClineReviewError(f"git diff failed (exit {proc.returncode}):\n{proc.stderr}")
    if not proc.stdout.strip():
        raise ClineReviewError(
            "git diff produced no output -- nothing to review for the given range/paths"
        )
    return proc.stdout


def run_cline_diff_review(
    diff_range: str | None,
    paths: list[str] | None,
    plan_paths: list[Path] | None,
    thinking: str = "high",
    timeout: int = 600,
    model: str | None = None,
) -> str:
    """Capture a git diff to a temp file and send it (plus optional plan docs) to Cline."""
    diff_text = get_git_diff(diff_range, paths)

    for plan_path in plan_paths or []:
        if not plan_path.is_file():
            raise ClineReviewError(f"plan file not found: {plan_path}")

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".diff", prefix="cline_review_", delete=False, encoding="utf-8"
    ) as f:
        f.write(diff_text)
        diff_path = Path(f.name)

    try:
        if plan_paths:
            plan_list = "、".join(str(p) for p in plan_paths)
            plan_clause = f"関連するplan/設計ドキュメント: {plan_list} も読み込み、実装がこのplanを満たしているか確認してください。\n"
        else:
            plan_clause = ""
        prompt = DIFF_REVIEW_INSTRUCTION_TEMPLATE.format(diff_path=diff_path, plan_clause=plan_clause)
        return invoke_cline(prompt, thinking=thinking, timeout=timeout, model=model)
    finally:
        diff_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--range",
        dest="diff_range",
        default=None,
        help="git diff range/args, e.g. 'HEAD~1', 'main...HEAD', '--staged' (default: working tree vs HEAD)",
    )
    parser.add_argument(
        "--path", dest="paths", action="append", help="limit the diff to this path (repeatable)"
    )
    parser.add_argument(
        "--plan",
        dest="plan_paths",
        type=Path,
        action="append",
        help="related plan/design doc to cross-check the diff against (repeatable)",
    )
    parser.add_argument(
        "--thinking",
        default="high",
        choices=["none", "low", "medium", "high", "xhigh"],
        help="Cline reasoning effort (default: high)",
    )
    parser.add_argument("--timeout", type=int, default=600, help="Timeout in seconds (default: 600)")
    parser.add_argument(
        "--model",
        default=None,
        help="One-off model override passed as `cline -m <id>` (default: cline's own persistent default)",
    )
    args = parser.parse_args()

    try:
        review = run_cline_diff_review(
            args.diff_range,
            args.paths,
            args.plan_paths,
            thinking=args.thinking,
            timeout=args.timeout,
            model=args.model,
        )
    except ClineReviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(review)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
