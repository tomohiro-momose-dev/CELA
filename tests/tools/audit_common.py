"""
audit_common.py — 監査ツール共通モジュール

Finding型定義・チェックレジストリ・出力ユーティリティを提供する。

使い方:
    from audit_common import Finding, register, CHECKS, CheckContext, run_checks, output_findings
"""

from __future__ import annotations

import json
import sys
from typing import Callable, TypedDict


# ===========================================================================
# Finding スキーマ（設計書 §1.1）
# ===========================================================================

class Finding(TypedDict):
    """監査ツール共通の検出結果スキーマ。"""
    tool: str            # "log_scanner" | "db_checker"
    check_id: str        # 例: "LOG-MAJOR", "DB-GHOST-DELIVERABLE"
    severity: str        # "critical" | "warning" | "info"
    location: str        # ログなら "L12345"、DBなら "agreements.id=AG-..."
    message: str         # 人間可読の説明
    context: str         # 該当箇所の抜粋（ログなら前後数行、DBならレコードのJSON）
    related_bl: str      # 既知のBL番号があれば（例: "BL-062"）。無ければ空文字


# ===========================================================================
# チェックレジストリ（設計書 §1.3）
# ===========================================================================

# 各チェック関数の型: Context を受け取り list[Finding] を返す
# Context はツール固有の型でもよいが、共通インターフェースとして TypedDict を束縛する
# "log_scanner" と "db_checker" で Context 型が異なるため、Any として扱う
from typing import Any
CheckContext = Any

CHECKS: dict[str, Callable[[CheckContext], list[Finding]]] = {}


def register(
    check_id: str,
    severity: str = "warning",
    related_bl: str = "",
) -> Callable[[Callable[[CheckContext], list[Finding]]], Callable[[CheckContext], list[Finding]]]:
    """チェック関数をレジストリに登録するデコレータ。

    例:
        @register("LOG-MAJOR", severity="warning", related_bl="BL-062")
        def check_major_judgements(ctx: LogContext) -> list[Finding]:
            ...
    """
    def deco(fn: Callable[[CheckContext], list[Finding]]) -> Callable[[CheckContext], list[Finding]]:
        CHECKS[check_id] = fn
        return fn
    return deco


# ===========================================================================
# チェック実行・出力ユーティリティ
# ===========================================================================

def run_checks(ctx: CheckContext, min_severity: str = "info") -> list[Finding]:
    """登録済みの全チェックを実行し、結果を1つのリストにまとめて返す。

    min_severity で指定した重要度以上の finding のみを返す。
    優先順位: critical > warning > info
    """
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    min_order = severity_order.get(min_severity, 2)

    all_findings: list[Finding] = []
    for check_id, check_fn in CHECKS.items():
        try:
            findings = check_fn(ctx)
            for f in findings:
                f["check_id"] = check_id  # デコレータから check_id が伝播しない場合の保険
            all_findings.extend(findings)
        except Exception as e:
            all_findings.append(Finding(
                tool=ctx.get("tool", "unknown") if isinstance(ctx, dict) else "unknown",
                check_id=check_id,
                severity="warning",
                location="N/A",
                message=f"チェック関数 {check_id} の実行中に例外: {e}",
                context="",
                related_bl="",
            ))

    # severity フィルタ
    filtered = [f for f in all_findings if severity_order.get(f["severity"], 2) >= min_order]
    return filtered


def output_findings(
    findings: list[Finding],
    json_path: str | None = None,
    min_severity: str = "info",
) -> int:
    """Finding リストを標準出力（Markdownテーブル）およびJSON Linesに出力する。

    Returns:
        終了コード。critical が1件でもあれば非ゼロ（1）を返す。
    """
    # severity フィルタ（run_checks で既にフィルタ済みだが、念のため）
    severity_order = {"critical": 0, "warning": 1, "info": 2}
    min_order = severity_order.get(min_severity, 2)
    # finding が既にフィルタ済みの場合はそのまま使う
    # 念のためここでもフィルタを適用するが、run_checks と結果が一致するはず
    filtered = [f for f in findings if severity_order.get(f["severity"], 2) >= min_order]

    # severity グループごとにソート
    group_order = {"critical": 0, "warning": 1, "info": 2}
    filtered.sort(key=lambda f: (group_order.get(f["severity"], 99), f["check_id"]))

    # --- 標準出力（Markdownテーブル） ---
    if filtered:
        print("\n## 監査結果\n")

        for sev in ("critical", "warning", "info"):
            group = [f for f in filtered if f["severity"] == sev]
            if not group:
                continue
            label = {"critical": "🔴 CRITICAL", "warning": "🟡 WARNING", "info": "🔵 INFO"}[sev]
            print(f"### {label}\n")
            print(f"| check_id | location | message | related_bl |")
            print(f"|----------|----------|---------|------------|")
            for f in group:
                bl = f.get("related_bl", "") or ""
                ctx_preview = f.get("context", "")[:60].replace("\n", " ")
                print(f"| {f['check_id']} | {f['location']} | {f['message']} | {bl} |")
            print()
            # context は別ブロックで表示
            for f in group:
                if f.get("context"):
                    print(f"<details><summary>📎 {f['check_id']} @ {f['location']} のコンテキスト</summary>\n")
                    print(f"```\n{f['context']}\n```\n</details>\n")
    else:
        print("## 監査結果\n\n該当する finding はありません。\n")

    # --- JSON Lines 出力 ---
    if json_path:
        with open(json_path, "w", encoding="utf-8") as f:
            for finding in filtered:
                f.write(json.dumps(finding, ensure_ascii=False) + "\n")
        print(f"✅ JSON Lines 出力: {json_path}")

    # 終了コード
    has_critical = any(f["severity"] == "critical" for f in filtered)
    return 1 if has_critical else 0


def severity_wheel(severity: str) -> str:
    """severity 文字列のバリデーション。"""
    if severity not in ("critical", "warning", "info"):
        raise ValueError(f"不明な severity: {severity!r}")
    return severity