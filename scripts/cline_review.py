"""Send a design/plan document to the Cline CLI for an independent review.

Part of the Claude(plan) -> Cline(review) -> Claude(re-plan) workflow:
Claude Code drafts a plan, this script hands the plan file to Cline (a
separate agent/model, running non-interactively via its CLI) for review,
and prints Cline's review text so Claude Code can fold it back into the
plan without any manual copy/paste.

[SAFETY] Cline is invoked with --auto-approve true, but its local config
(~/.cline/data/globalState.json -> autoApprovalSettings.actions) is kept
with editFiles / editFilesExternally / executeAllCommands forced to false.
Only readFiles / readFilesExternally / executeSafeCommands / useMcp (and,
per an explicit user decision, useBrowser) stay auto-approved. This script
must never be used to grant Cline write access back -- it exists so a
*review* agent cannot silently mutate the repo it is reviewing.

~/.cline/data/globalState.json is a single machine-wide file shared by
every Cline CLI invocation on this machine, including other concurrent
Claude Code sessions. A concurrent session's own cline usage can reset it
to all-true (observed 2026-08-31, root cause not fully confirmed). To stay
safe regardless of what another process did to the file a moment ago,
_ensure_readonly_auto_approve() re-asserts the write-disabled subset on
every call, right before invoking the CLI.

Usage:
    python scripts/cline_review.py <plan_file> [--thinking LEVEL] [--timeout SECONDS] [--model MODEL_ID]

[BL-330 review session, 2026-09-01] --model is a one-off per-invocation override
(passed straight through as `cline -m <id>`) -- it does NOT touch the persistent
default model in ~/.cline/data/globalState.json. Added because the persistent
default model hit its daily free-tier quota mid-review; the user chose to retry
with a different model for this call rather than wait for the quota reset or
change the persistent default via `cline auth`.
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLINE_GLOBAL_STATE_PATH = Path.home() / ".cline" / "data" / "globalState.json"
_WRITE_ACTIONS = ("editFiles", "editFilesExternally", "executeAllCommands")

REVIEW_INSTRUCTION_TEMPLATE = (
    "{plan_path} を読み込んで、設計・実装計画としてレビューしてください。\n"
    "観点:\n"
    "1. 正確性・実現可能性（存在しないAPI/関数を前提にしていないか）\n"
    "2. 抜け漏れ・エッジケース\n"
    "3. 既存コード/アーキテクチャとの整合性\n"
    "4. 過剰設計になっていないか、もっとシンプルな案がないか\n"
    "指摘ごとに、該当箇所（見出し名または行の引用）と重大度（重大/中/軽微）を明記してください。\n"
    "あなたはレビューアです。ファイルの編集・作成・コマンド実行による変更は行わず、"
    "レビューコメントのテキストのみを返してください。"
)


class ClineReviewError(RuntimeError):
    """Raised when the Cline CLI cannot produce a usable review."""


def _ensure_readonly_auto_approve() -> None:
    """Force editFiles/editFilesExternally/executeAllCommands back to false.

    Best-effort, run immediately before every Cline invocation -- see the
    module docstring [SAFETY] note for why this file can drift back to
    all-true between calls. Silently gives up on any read/parse/write error
    rather than blocking the review: the next call will retry.
    """
    if not CLINE_GLOBAL_STATE_PATH.is_file():
        return
    try:
        with open(CLINE_GLOBAL_STATE_PATH, encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return

    actions = data.get("autoApprovalSettings", {}).get("actions")
    if not isinstance(actions, dict) or not any(actions.get(k) for k in _WRITE_ACTIONS):
        return

    for key in _WRITE_ACTIONS:
        actions[key] = False
    try:
        with open(CLINE_GLOBAL_STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False)
    except OSError:
        pass


def _hub_is_running(cline_exe: str) -> bool:
    """Check whether the Cline hub daemon for this workspace is already running."""
    try:
        proc = subprocess.run(
            [cline_exe, "hub", "status", "--cwd", str(REPO_ROOT)],
            capture_output=True, text=True, encoding="utf-8", timeout=15,
        )
    except (OSError, subprocess.TimeoutExpired):
        return False
    try:
        return bool(json.loads(proc.stdout).get("running"))
    except (json.JSONDecodeError, AttributeError):
        return False


def _hub_start(cline_exe: str) -> None:
    """Best-effort: start the hub daemon. Failure here just means the plain
    `cline ...` invocation below has to start it implicitly instead."""
    try:
        subprocess.run(
            [cline_exe, "hub", "start", "--cwd", str(REPO_ROOT)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def _hub_stop(cline_exe: str) -> None:
    """Best-effort: stop the hub daemon. Never raises -- a failed cleanup must
    not turn a successful review into a reported failure."""
    try:
        subprocess.run(
            [cline_exe, "hub", "stop", "--cwd", str(REPO_ROOT)],
            capture_output=True, text=True, encoding="utf-8", timeout=30,
        )
    except (OSError, subprocess.TimeoutExpired):
        pass


def invoke_cline(prompt: str, thinking: str = "high", timeout: int = 600, model: str | None = None) -> str:
    """Run the Cline CLI non-interactively with `prompt` and return its final answer text.

    [CONSTRAINT] Never pass -p/--plan here. Cline has its own plan/act mode; in
    plan mode it presents a plan and then stops, waiting for a human to approve
    switching to act mode -- combined with non-interactive invocation this hangs
    indefinitely (see AGENTS.md 19.3). Plain act-mode invocation is safe because
    write actions are already disabled per AGENTS.md 19.2.

    [LIFECYCLE] The hub daemon is started fresh for this call and stopped again
    afterward -- but only if this call is the one that started it. If the hub
    was already running (e.g. another concurrent Claude Code session is using
    it), it is left alone: shutting down a daemon another session depends on
    would break that session's in-flight work, which is worse than leaving an
    idle daemon running. See AGENTS.md 19.3.
    """
    _ensure_readonly_auto_approve()

    cline_exe = shutil.which("cline")
    if cline_exe is None:
        raise ClineReviewError(
            "cline CLI not found on PATH. Install with 'npm i -g cline' and "
            "authenticate with 'cline auth' first."
        )

    hub_was_running = _hub_is_running(cline_exe)
    if not hub_was_running:
        _hub_start(cline_exe)

    try:
        cmd = [
            cline_exe,
            "--json",
            "--auto-approve", "true",
            "--thinking", thinking,
            "-c", str(REPO_ROOT),
            "-t", str(timeout),
        ]
        if model:
            cmd += ["-m", model]
        cmd.append(prompt)

        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                encoding="utf-8",
                timeout=timeout + 30,
            )
        except FileNotFoundError as exc:
            raise ClineReviewError(
                "cline CLI not found on PATH. Install with 'npm i -g cline' and "
                "authenticate with 'cline auth' first."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ClineReviewError(f"cline CLI did not finish within {timeout + 30}s") from exc

        if proc.returncode != 0:
            raise ClineReviewError(
                f"cline CLI exited with code {proc.returncode}:\n{proc.stderr}"
            )

        review_text = None
        for line in proc.stdout.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "run_result":
                review_text = event.get("text")

        if not review_text:
            raise ClineReviewError(
                "cline CLI produced no run_result text; raw stdout:\n" + proc.stdout
            )
        return review_text
    finally:
        if not hub_was_running:
            _hub_stop(cline_exe)


def run_cline_review(plan_path: Path, thinking: str = "high", timeout: int = 600, model: str | None = None) -> str:
    """Send a single plan/design doc to Cline and return its review text."""
    if not plan_path.is_file():
        raise ClineReviewError(f"plan file not found: {plan_path}")

    prompt = REVIEW_INSTRUCTION_TEMPLATE.format(plan_path=plan_path)
    return invoke_cline(prompt, thinking=thinking, timeout=timeout, model=model)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_path", type=Path, help="Path to the plan/design markdown file to review")
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
        review = run_cline_review(args.plan_path, thinking=args.thinking, timeout=args.timeout, model=args.model)
    except ClineReviewError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(review)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
