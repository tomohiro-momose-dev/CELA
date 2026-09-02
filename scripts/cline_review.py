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
import threading
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
CLINE_GLOBAL_STATE_PATH = Path.home() / ".cline" / "data" / "globalState.json"
_WRITE_ACTIONS = ("editFiles", "editFilesExternally", "executeAllCommands")

# [BL-334] Freeze detection watches this task's own --json stdout stream, not
# process-level disk/network I/O counters. Two counter-based approaches were
# tried and rejected 2026-09-01: (1) the `cline` CLI subprocess's own I/O --
# it is a thin client that hands off to the hub daemon and barely moves
# itself, causing false "frozen" kills mid-review (observed at 328s and
# 900s+ while the hub was actively working); (2) the hub daemon's I/O -- hub
# is shared machine-wide across concurrent Claude Code sessions (AGENTS.md
# 19.2/19.3), so its counters reflect other sessions' work too, masking a
# genuinely frozen task. Watching this task's own stdout line arrivals is
# scoped to exactly this invocation and, per observed --json output, the
# provider streams `reasoning` content deltas token-by-token while "thinking"
# -- so genuine silence here should mean the provider truly stopped
# responding, not just "still computing".
_FREEZE_SILENCE_SECONDS = 300
_ACTIVITY_CHECK_INTERVAL_SECONDS = 10

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


def _drain_stream(pipe, buffer: list[str], activity: dict, lock: threading.Lock) -> None:
    """Continuously read a subprocess pipe into `buffer` on a background thread,
    stamping `activity["last"]` (monotonic time) on every line received.

    Without the background read, a Popen'd process whose stdout/stderr isn't
    being read can block on a full OS pipe buffer once its (JSON-lines,
    potentially large) output exceeds it. The activity stamp is what the
    freeze-detection loop in invoke_cline watches -- see [BL-334 FREEZE
    DETECTION] there for why this, rather than a process I/O counter, is the
    signal.
    """
    try:
        for line in iter(pipe.readline, ""):
            buffer.append(line)
            with lock:
                activity["last"] = time.monotonic()
    finally:
        pipe.close()


def invoke_cline(prompt: str, thinking: str = "high", timeout: int = 3600, model: str | None = None) -> str:
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

    [BL-334 FREEZE DETECTION] `timeout` is a hard safety-net ceiling, not the
    primary cutoff -- a fixed wall-clock timeout can't tell "still genuinely
    working on a heavy review" from "hung", and both were observed at 600s
    and 900s. Instead, this task's own --json stdout is watched: if no new
    line arrives for _FREEZE_SILENCE_SECONDS, the process is killed and
    treated as frozen. See the module-level comment above
    _FREEZE_SILENCE_SECONDS for why stdout-arrival was chosen over a process
    I/O counter (two counter-based approaches were tried and rejected first).
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
            proc = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                bufsize=1,
            )
        except OSError as exc:
            raise ClineReviewError(
                "cline CLI not found on PATH. Install with 'npm i -g cline' and "
                "authenticate with 'cline auth' first."
            ) from exc

        stdout_lines: list[str] = []
        stderr_lines: list[str] = []
        activity_lock = threading.Lock()
        activity = {"last": time.monotonic()}
        stdout_thread = threading.Thread(
            target=_drain_stream, args=(proc.stdout, stdout_lines, activity, activity_lock), daemon=True
        )
        stderr_thread = threading.Thread(
            target=_drain_stream, args=(proc.stderr, stderr_lines, activity, activity_lock), daemon=True
        )
        stdout_thread.start()
        stderr_thread.start()

        start = time.monotonic()
        killed_reason: str | None = None

        while proc.poll() is None:
            if time.monotonic() - start > timeout:
                proc.kill()
                killed_reason = f"cline CLI exceeded the {timeout}s safety-net timeout"
                break

            time.sleep(_ACTIVITY_CHECK_INTERVAL_SECONDS)

            with activity_lock:
                silence = time.monotonic() - activity["last"]
            if silence > _FREEZE_SILENCE_SECONDS:
                proc.kill()
                killed_reason = (
                    f"cline CLI appears frozen: no output for {_FREEZE_SILENCE_SECONDS}s"
                )
                break

        proc.wait(timeout=30)
        stdout_thread.join(timeout=10)
        stderr_thread.join(timeout=10)

        if killed_reason:
            raise ClineReviewError(killed_reason)

        full_stdout = "".join(stdout_lines)
        full_stderr = "".join(stderr_lines)

        if proc.returncode != 0:
            raise ClineReviewError(
                f"cline CLI exited with code {proc.returncode}:\n{full_stderr}"
            )

        review_text = None
        for line in full_stdout.splitlines():
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
                "cline CLI produced no run_result text; raw stdout:\n" + full_stdout
            )
        return review_text
    finally:
        if not hub_was_running:
            _hub_stop(cline_exe)


def run_cline_review(plan_path: Path, thinking: str = "high", timeout: int = 3600, model: str | None = None) -> str:
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
    parser.add_argument(
        "--timeout",
        type=int,
        default=3600,
        help="Safety-net timeout in seconds (default: 3600) -- I/O-silence freeze "
        "detection is the primary cutoff, see AGENTS.md 19.x",
    )
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
