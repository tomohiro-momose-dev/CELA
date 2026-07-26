"""
log_scanner.py — ログエラースキャナー

log_no_prompt.md（または log_with_prompt.md）をLLMを介さず走査し、
CELA自身が既に埋め込んでいる異常マーカーを漏れなく列挙する。

使い方:
    python tests/tools/log_scanner.py <log_no_prompt.md>
        [--json out.jsonl] [--min-severity warning]

設計書: tests/audit_tools_design.md §2
"""

from __future__ import annotations

import argparse
import re
import sys
from dataclasses import dataclass, field
from typing import Iterator

from audit_common import (
    CHECKS,
    Finding,
    CheckContext,
    output_findings,
    register,
    run_checks,
)


# ===========================================================================
# ログコンテキスト
# ===========================================================================

@dataclass
class LogContext:
    """ログファイル走査のためのコンテキスト。"""
    tool: str = "log_scanner"
    log_path: str = ""
    lines: list[str] = field(default_factory=list)
    # プリコンパイルした行単位の情報（高速化用）
    line_texts: list[str] = field(default_factory=list)

    @classmethod
    def from_file(cls, path: str) -> "LogContext":
        with open(path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        return cls(
            log_path=path,
            lines=list(enumerate(lines, start=1)),
            line_texts=lines,
        )


# ===========================================================================
# 個別チェック関数
# ===========================================================================

def _make_finding(
    check_id: str,
    severity: str,
    line_no: int,
    message: str,
    context: str = "",
    related_bl: str = "",
) -> Finding:
    return Finding(
        tool="log_scanner",
        check_id=check_id,
        severity=severity,
        location=f"L{line_no}",
        message=message,
        context=context,
        related_bl=related_bl,
    )


def _surrounding_context(lines: list[tuple[int, str]], line_no: int, radius: int = 3) -> str:
    """指定行の前後 radius 行を抜粋して返す。"""
    result: list[str] = []
    for ln, text in lines:
        if abs(ln - line_no) <= radius:
            result.append(f"L{ln}: {text.rstrip()}")
    return "\n".join(result)


def _get_line_text(line_no: int, ctx: LogContext) -> str:
    """1-based line_no に対応するテキストを返す。"""
    try:
        return ctx.line_texts[line_no - 1]
    except IndexError:
        return ""


# --- LOG-ROLE-REPEAT ---

@register("LOG-ROLE-REPEAT", severity="warning")
def check_role_repeat(ctx: LogContext) -> list[Finding]:
    """⚠️ .*role連続を検出"""
    pattern = re.compile(r"⚠️\s*.*role連続を検出")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-ROLE-REPEAT", "warning", line_no,
                "user/assistantのrole連続を検出（APIエラーの原因になりうる）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-FORCED-TEXT ---

@register("LOG-FORCED-TEXT", severity="info")
def check_forced_text(ctx: LogContext) -> list[Finding]:
    """⚠️ .*最終iteration.*ツールを外し"""
    pattern = re.compile(r"⚠️\s*.*最終iteration.*ツールを外し")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-FORCED-TEXT", "info", line_no,
                "ツールループが上限に達し、強制的にテキスト応答させた",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-MAX-TOKENS ---

@register("LOG-MAX-TOKENS", severity="critical")
def check_max_tokens(ctx: LogContext) -> list[Finding]:
    """⚠️ .*max_tokens超過により出力が打ち切られました"""
    pattern = re.compile(r"⚠️\s*.*max_tokens超過により出力が打ち切られました")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-MAX-TOKENS", "critical", line_no,
                "応答がmax_tokens超過で途中打ち切り（成果物が不完全な可能性）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-NO-REPL ---

@register("LOG-NO-REPL", severity="info")
def check_no_repl(ctx: LogContext) -> list[Finding]:
    """⚠️ .*python_replを一度も使わずに応答しました（F-2.6監査対象）"""
    pattern = re.compile(r"⚠️\s*.*python_replを一度も使わずに応答しました")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-NO-REPL", "info", line_no,
                "python_replを一度も使わずに応答（F-2.6監査対象）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="F-2.6",
            ))
    return findings


# --- LOG-UNKNOWN-TOOL ---

@register("LOG-UNKNOWN-TOOL", severity="critical")
def check_unknown_tool(ctx: LogContext) -> list[Finding]:
    """⚠️ .*未知のツール呼び出し"""
    pattern = re.compile(r"⚠️\s*.*未知のツール呼び出し")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-UNKNOWN-TOOL", "critical", line_no,
                "モデルが存在しないツールを呼び出した",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-TOOLARG-JSON-FAIL ---

@register("LOG-TOOLARG-JSON-FAIL", severity="critical")
def check_toolarg_json_fail(ctx: LogContext) -> list[Finding]:
    """⚠️ .*tool_call引数のJSONパース失敗"""
    pattern = re.compile(r"⚠️\s*.*tool_call引数のJSONパース失敗")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-TOOLARG-JSON-FAIL", "critical", line_no,
                "ツール引数のJSONパースに失敗（ツール呼び出しが破損）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-NONCONVERGENT ---

@register("LOG-NONCONVERGENT", severity="critical")
def check_nonconvergent(ctx: LogContext) -> list[Finding]:
    """❌ .*ツールループが.*回を超えて非収束"""
    pattern = re.compile(r"❌\s*.*ツールループが.*回を超えて非収束")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-NONCONVERGENT", "critical", line_no,
                "ツールループが上限に達し非収束（クラッシュ相当）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-JUDGE-JSON-RETRY ---

@register("LOG-JUDGE-JSON-RETRY", severity="warning")
def check_judge_json_retry(ctx: LogContext) -> list[Finding]:
    """⚠️ .*JSON判定パース失敗を検知。層2リトライ"""
    pattern = re.compile(r"⚠️\s*.*JSON判定パース失敗を検知。層2リトライ")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-JUDGE-JSON-RETRY", "warning", line_no,
                "判定JSONのパースに失敗し層2リトライが発生",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-EMPTY-RESPONSE ---

@register("LOG-EMPTY-RESPONSE", severity="warning")
def check_empty_response(ctx: LogContext) -> list[Finding]:
    """⚠️ .*空応答を検知。リトライ"""
    pattern = re.compile(r"⚠️\s*.*空応答を検知。リトライ")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-EMPTY-RESPONSE", "warning", line_no,
                "User AIが空応答を返しリトライした",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-DELIVERABLE-CONFLICT ---

@register("LOG-DELIVERABLE-CONFLICT", severity="critical")
def check_deliverable_conflict(ctx: LogContext) -> list[Finding]:
    """⚠️ .*成果物間に矛盾を検出しました"""
    pattern = re.compile(r"⚠️\s*.*成果物間に矛盾を検出しました")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-DELIVERABLE-CONFLICT", "critical", line_no,
                "Integratorが成果物間の矛盾を検出",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-ANNOTATE-FAILED ---

@register("LOG-ANNOTATE-FAILED", severity="warning")
def check_annotate_failed(ctx: LogContext) -> list[Finding]:
    r"""⚠️ \[Whiteboard Annotate Failed\]"""
    pattern = re.compile(r"⚠️\s*\[Whiteboard Annotate Failed\]")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-ANNOTATE-FAILED", "warning", line_no,
                "Detectorの指摘注釈がwhiteboardに挿入できなかった（BL-074関連）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="BL-074",
            ))
    return findings


# --- LOG-REPL-ERROR ---

@register("LOG-REPL-ERROR", severity="info")
def check_repl_error(ctx: LogContext) -> list[Finding]:
    r"""→ \[REPL Error\]"""
    pattern = re.compile(r"→\s*\[REPL Error\]")
    findings: list[Finding] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            findings.append(_make_finding(
                "LOG-REPL-ERROR", "info", line_no,
                "サンドボックス制限でpython_replが失敗（許可モジュール外import等）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="",
            ))
    return findings


# --- LOG-MAJOR-VERDICT ---

@register("LOG-MAJOR-VERDICT", severity="warning")
def check_major_verdict(ctx: LogContext) -> list[Finding]:
    """'constraint_issue': 'major' または "constraint_issue": "major" または constraint_issue.*major"""
    # 3パターン: シングルクォートJSON、ダブルクォートJSON、簡易表記
    pattern1 = re.compile(r"'constraint_issue'\s*:\s*'major'")
    pattern2 = re.compile(r'"constraint_issue"\s*:\s*"major"')
    pattern3 = re.compile(r"constraint_issue.*major")
    findings: list[Finding] = []
    seen_lines: set[int] = set()
    for line_no, text in ctx.lines:
        if line_no in seen_lines:
            continue
        if pattern1.search(text) or pattern2.search(text) or pattern3.search(text):
            seen_lines.add(line_no)
            findings.append(_make_finding(
                "LOG-MAJOR-VERDICT", "warning", line_no,
                "major判定を検出（件数集計・後続追跡の起点として）",
                _surrounding_context(ctx.lines, line_no),
                related_bl="BL-062",
            ))
    return findings


# ===========================================================================
# 集計ルール: LOG-SAME-MAJOR-REPEAT（設計書 §2.2 末尾）
# ===========================================================================

@register("LOG-SAME-MAJOR-REPEAT", severity="critical")
def check_same_major_repeat(ctx: LogContext) -> list[Finding]:
    """同一task_idに対するmajor判定が閾値回数（既定3回）を超えたら発火。

    LOG-MAJOR-VERDICTのヒット行からtask_idを推定し、同一task_idに対する
    major判定の連続出現回数をカウントする。
    """
    # major判定行の収集（check_major_verdictと同様のパターン）
    pattern = re.compile(r"(?:'constraint_issue'\s*:\s*'major'|constraint_issue.*major)")
    major_lines: list[int] = []
    for line_no, text in ctx.lines:
        if pattern.search(text):
            major_lines.append(line_no)

    if len(major_lines) < 3:
        return []

    # task_id の推定: major判定行の前後10行以内から task_id を探す
    task_pattern = re.compile(r"(?:task_id|task_id_name)\s*[:=]\s*['\"]?([\w_]+)['\"]?")
    fallback_task_pattern = re.compile(r"(?:phase|task)\s*[#_]?\s*(\d+(?:_\d+)?)")

    task_id_counts: dict[str, list[int]] = {}
    for ln in major_lines:
        # 前後10行からtask_idを抽出
        task_id = None
        for scan_ln, scan_text in ctx.lines:
            if abs(scan_ln - ln) > 10:
                continue
            m = task_pattern.search(scan_text)
            if m:
                task_id = m.group(1)
                break
        # フォールバック: phase/task パターン
        if task_id is None:
            for scan_ln, scan_text in ctx.lines:
                if abs(scan_ln - ln) > 10:
                    continue
                m = fallback_task_pattern.search(scan_text)
                if m:
                    task_id = f"task_{m.group(1)}"
                    break
        if task_id is None:
            task_id = "__unknown__"
        task_id_counts.setdefault(task_id, []).append(ln)

    findings: list[Finding] = []
    THRESHOLD = 3
    for task_id, lines in task_id_counts.items():
        if len(lines) >= THRESHOLD:
            # 連続性の確認: 間に関係のないmajor判定が挟まっていないか
            # ここでは単純に同じtask_idへのmajor判定が閾値以上あれば警告する
            sorted_lines = sorted(lines)
            first, last = sorted_lines[0], sorted_lines[-1]
            gap_lines = last - first + 1
            density = len(sorted_lines) / gap_lines if gap_lines > 0 else 1.0
            context = _surrounding_context(ctx.lines, sorted_lines[0], radius=5)
            context += "\n...\n"
            context += _surrounding_context(ctx.lines, sorted_lines[-1], radius=5)

            msg = (
                f"同一task_id（{task_id}）に対するmajor判定が{len(lines)}回検出された"
                f"（閾値{THRESHOLD}回超過、密度{density:.0%}）。"
                f"同種指摘が是正されずループしている可能性。"
            )
            findings.append(_make_finding(
                "LOG-SAME-MAJOR-REPEAT", "critical", first,
                msg,
                context,
                related_bl="",
            ))
    return findings


# ===========================================================================
# CLIエントリポイント
# ===========================================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CELAログファイルから異常マーカーを走査する",
    )
    parser.add_argument(
        "log_path",
        help="log_no_prompt.md（または log_with_prompt.md）のパス",
    )
    parser.add_argument(
        "--json",
        dest="json_path",
        default=None,
        help="JSON Lines出力先ファイルパス",
    )
    parser.add_argument(
        "--min-severity",
        dest="min_severity",
        default="info",
        choices=["critical", "warning", "info"],
        help="出力する最低severity（既定: info = 全て出力）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ctx = LogContext.from_file(args.log_path)
    findings = run_checks(ctx, min_severity=args.min_severity)
    return output_findings(findings, json_path=args.json_path, min_severity=args.min_severity)


if __name__ == "__main__":
    sys.exit(main())