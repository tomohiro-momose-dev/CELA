"""
db_checker.py — DB整合性チェッカー

cela.db に対し、既知のBLインシデントから逆算した構造的不変条件をSQLで直接検査する。
LLMのラベルに頼らず、スキーマそのものから矛盾を検出する。

使い方:
    python tests/tools/db_checker.py --db cela.db --run-id <run_id>
        [--log-dir log/2026-07-25/1913] [--json out.jsonl] [--min-severity warning]

設計書: tests/audit_tools_design.md §3
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audit_common import (
    CHECKS,
    Finding,
    CheckContext,
    output_findings,
    register,
    run_checks,
)


# ===========================================================================
# DBコンテキスト
# ===========================================================================

@dataclass
class DbContext:
    """DB検査のためのコンテキスト。"""
    tool: str = "db_checker"
    db_path: str = ""
    run_id: str = ""
    log_dir: str = ""  # whiteboardファイル突合用（省略可）
    conn: sqlite3.Connection | None = None

    @classmethod
    def from_args(cls, db_path: str, run_id: str, log_dir: str = "") -> "DbContext":
        conn = sqlite3.connect(db_path)
        conn.row_factory = sqlite3.Row
        return cls(
            db_path=db_path,
            run_id=run_id,
            log_dir=log_dir,
            conn=conn,
        )

    def close(self) -> None:
        if self.conn:
            self.conn.close()

    def execute(self, sql: str, params: tuple = ()) -> list[sqlite3.Row]:
        if self.conn is None:
            raise RuntimeError("DB接続がありません")
        return self.conn.execute(sql, params).fetchall()


# ===========================================================================
# ユーティリティ
# ===========================================================================

def _make_finding(
    check_id: str,
    severity: str,
    location: str,
    message: str,
    context: str = "",
    related_bl: str = "",
) -> Finding:
    return Finding(
        tool="db_checker",
        check_id=check_id,
        severity=severity,
        location=location,
        message=message,
        context=context,
        related_bl=related_bl,
    )


def _row_to_json(row: sqlite3.Row) -> str:
    """sqlite3.Row を JSON 文字列に変換する。"""
    return json.dumps(dict(row), ensure_ascii=False, default=str)


# ===========================================================================
# run_id の特定（cela.db からの抽出）
# ===========================================================================

def extract_latest_run_id_from_db(db_path: str) -> str | None:
    """[BL-105] cela.dbのdecisionsテーブルから最新timestampのrun_idを取得する。

    自前JSON checkpoint（checkpoint.json）はBL-105/D-086でLangGraph公式のcheckpointer
    （cela_checkpoints.db）へ置き換えられ廃止されたため、run_id自動検出の情報源をDB本体へ
    切り替えた。
    """
    if not os.path.exists(db_path):
        return None
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT run_id FROM decisions ORDER BY timestamp DESC LIMIT 1").fetchone()
        return row[0] if row else None
    except sqlite3.OperationalError:
        return None
    finally:
        conn.close()


def extract_run_id_from_log_header(log_path: str) -> str | None:
    """ログファイル冒頭のタイムスタンプから run_id を推定する（フォールバック）。

    実際の run_id は UUID 形式のため、タイムスタンプのみでは一意特定できない。
    この関数はあくまでフォールバックであり、正確な run_id は cela.db から取得するか、
    ユーザーが --run-id で明示指定する必要がある。
    """
    # この関数は設計書 §3.3 のフォールバック経路として用意するが、
    # 現状では実用的な推定は困難なため None を返す。
    # 実装時に改善可能。
    return None


# ===========================================================================
# チェック関数
# ===========================================================================

# --- DB-GHOST-DELIVERABLE ---

@register("DB-GHOST-DELIVERABLE", severity="critical", related_bl="BL-073/074/084")
def check_ghost_deliverable(ctx: DbContext) -> list[Finding]:
    """同一 (run_id, phase_id, task_id) の entry_type='Deliverable' 行のうち、
    status != 'Superseded' が2件以上残っている。"""
    rows = ctx.execute("""
        SELECT id, phase_id, task_id, status, entry_type, topic, timestamp
        FROM agreements
        WHERE run_id = ? AND entry_type = 'Deliverable'
        ORDER BY phase_id, task_id, timestamp
    """, (ctx.run_id,))

    # (phase_id, task_id) でグループ化
    groups: dict[tuple[str, str], list[sqlite3.Row]] = {}
    for row in rows:
        key = (row["phase_id"] or "", row["task_id"] or "")
        groups.setdefault(key, []).append(row)

    findings: list[Finding] = []
    for (phase_id, task_id), group_rows in groups.items():
        non_superseded = [r for r in group_rows if r["status"] != "Superseded"]
        if len(non_superseded) >= 2:
            # 最新のものを除いて全てゴースト
            latest = max(non_superseded, key=lambda r: r["timestamp"] or 0)
            ghosts = [r for r in non_superseded if r["id"] != latest["id"]]
            for g in ghosts:
                findings.append(_make_finding(
                    "DB-GHOST-DELIVERABLE", "critical",
                    f"agreements.id={g['id']}",
                    f"Deliverable '{g.get('topic', '')}' (phase={phase_id}, task={task_id}) が "
                    f"status='{g['status']}' のまま残っている（Supersede されていないゴースト）",
                    _row_to_json(g),
                    related_bl="BL-073/074/084",
                ))
    return findings


# --- DB-WRITEBACK-MISMATCH ---

@register("DB-WRITEBACK-MISMATCH", severity="critical")
def check_writeback_mismatch(ctx: DbContext) -> list[Finding]:
    """whiteboard_drafts の最新 version の content と、
    対応する whiteboard ファイルの内容が一致しない。"""
    if not ctx.log_dir:
        return []  # log_dir 未指定時はスキップ

    rows = ctx.execute("""
        SELECT wb.*
        FROM whiteboard_drafts wb
        INNER JOIN (
            SELECT phase_id, task_id, MAX(version) AS max_ver
            FROM whiteboard_drafts
            WHERE run_id = ?
            GROUP BY phase_id, task_id
        ) latest
        ON wb.phase_id = latest.phase_id
        AND wb.task_id = latest.task_id
        AND wb.version = latest.max_ver
        WHERE wb.run_id = ?
    """, (ctx.run_id, ctx.run_id))

    findings: list[Finding] = []
    for row in rows:
        phase_id = row["phase_id"]
        task_id = row["task_id"]
        version = row["version"]
        db_content = row["content"] or ""

        # ファイルパスの推定: log/<date>/<time>/whiteboards/phase_P_task_T_V<N>.md
        # log_dir は log/<date>/<time> を想定
        whiteboards_dir = os.path.join(ctx.log_dir, "whiteboards")
        if not os.path.isdir(whiteboards_dir):
            # フォールバック: 親ディレクトリの whiteboards
            whiteboards_dir = os.path.join(os.path.dirname(ctx.log_dir), "whiteboards") if ctx.log_dir else ""
            if not os.path.isdir(whiteboards_dir):
                continue

        # ファイル名パターン: phase_{phase_id}_task_{task_id}_V{version}.md
        # phase_id が "phase_1" の場合、ファイル名は "phase_1_task_..." となる
        file_basename = f"{phase_id}_task_{task_id}_V{version}.md"
        file_path = os.path.join(whiteboards_dir, file_basename)

        if not os.path.exists(file_path):
            # 別のパターンも試す: phase_id が "1" のみの場合
            alt_basename = f"phase_{phase_id}_task_{task_id}_V{version}.md"
            alt_path = os.path.join(whiteboards_dir, alt_basename)
            if os.path.exists(alt_path):
                file_path = alt_path
            else:
                findings.append(_make_finding(
                    "DB-WRITEBACK-MISMATCH", "warning",
                    f"whiteboard_drafts.(phase={phase_id}, task={task_id}, V={version})",
                    f"対応するwhiteboardファイルが見つかりません: {file_basename}",
                    f"探索ディレクトリ: {whiteboards_dir}",
                    related_bl="",
                ))
                continue

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
        except (OSError, UnicodeDecodeError) as e:
            findings.append(_make_finding(
                "DB-WRITEBACK-MISMATCH", "warning",
                f"whiteboard_drafts.(phase={phase_id}, task={task_id}, V={version})",
                f"whiteboardファイル読み込みエラー: {e}",
                str(e),
                related_bl="",
            ))
            continue

        # 内容比較（前後の空白を除去して比較）
        db_stripped = db_content.strip()
        file_stripped = file_content.strip()
        if db_stripped != file_stripped:
            # 差分の先頭部分を context に含める
            diff_preview = _compute_diff_preview(db_stripped, file_stripped, max_chars=200)
            findings.append(_make_finding(
                "DB-WRITEBACK-MISMATCH", "critical",
                f"whiteboard_drafts.(phase={phase_id}, task={task_id}, V={version}) vs {file_path}",
                f"DBのwhiteboard_drafts.content とファイル内容が一致しない（write-back未反映バグ）",
                diff_preview,
                related_bl="",
            ))
    return findings


def _compute_diff_preview(db_content: str, file_content: str, max_chars: int = 200) -> str:
    """DBとファイルの内容の差分プレビューを生成する。"""
    # 単純に先頭の異なる位置を探す
    min_len = min(len(db_content), len(file_content))
    diff_pos = 0
    for i in range(min_len):
        if db_content[i] != file_content[i]:
            diff_pos = i
            break
    else:
        diff_pos = min_len

    start = max(0, diff_pos - 50)
    preview = (
        f"--- DB content (offset {start}) ---\n"
        f"{db_content[start:start + max_chars]}\n"
        f"--- File content (offset {start}) ---\n"
        f"{file_content[start:start + max_chars]}\n"
        f"--- 最初の差分位置: {diff_pos} ---"
    )
    return preview


# --- DB-MAJOR-WITHOUT-SUPERSEDE ---

@register("DB-MAJOR-WITHOUT-SUPERSEDE", severity="warning", related_bl="BL-062")
def check_major_without_supersede(ctx: DbContext) -> list[Finding]:
    """constraint_issue='major' かつ対象がDB内の既存topicに起因すると推定できるのに、
    直後に action_type='SUPERSEDE' の行が続いていない。"""
    rows = ctx.execute("""
        SELECT id, action_type, status, topic, entry_type, phase_id, task_id,
               decision_what, reason_why, timestamp
        FROM agreements
        WHERE run_id = ?
        ORDER BY timestamp
    """, (ctx.run_id,))

    findings: list[Finding] = []
    # major 判定の推定: decision_what または reason_why に "major" を含む行を探す
    major_rows: list[sqlite3.Row] = []
    for row in rows:
        what = (row["decision_what"] or "").lower()
        why = (row["reason_why"] or "").lower()
        if "major" in what or "major" in why:
            major_rows.append(row)

    # 各 major 行の直後に SUPERSEDE があるか確認
    for i, major_row in enumerate(major_rows):
        major_ts = major_row["timestamp"] or 0
        # 同じ run_id 内で、major_row の timestamp 以降の SUPERSEDE を探す
        supersede_rows = ctx.execute("""
            SELECT id, action_type, topic, phase_id, task_id, timestamp
            FROM agreements
            WHERE run_id = ? AND action_type = 'SUPERSEDE' AND timestamp >= ?
            ORDER BY timestamp
            LIMIT 5
        """, (ctx.run_id, major_ts))

        supersede_found = False
        for s_row in supersede_rows:
            # 同一 phase/task に対する SUPERSEDE か確認
            if (s_row["phase_id"] == major_row["phase_id"] and
                    s_row["task_id"] == major_row["task_id"]):
                supersede_found = True
                break

        if not supersede_found:
            findings.append(_make_finding(
                "DB-MAJOR-WITHOUT-SUPERSEDE", "warning",
                f"agreements.id={major_row['id']}",
                f"major判定（topic='{major_row.get('topic', '')}'）の直後に "
                f"同一phase/taskに対するSUPERSEDEが見つからない",
                _row_to_json(major_row),
                related_bl="BL-062",
            ))
    return findings


# --- DB-ORPHAN-PROPOSED-DIRECTIVE ---

@register("DB-ORPHAN-PROPOSED-DIRECTIVE", severity="warning", related_bl="BL-073")
def check_orphan_proposed_directive(ctx: DbContext) -> list[Finding]:
    """entry_type='Directive' が status='Proposed' のまま、対応タスクが完了している。"""
    rows = ctx.execute("""
        SELECT id, action_type, status, topic, entry_type, phase_id, task_id, timestamp
        FROM agreements
        WHERE run_id = ? AND entry_type = 'Directive' AND status = 'Proposed'
        ORDER BY phase_id, task_id
    """, (ctx.run_id,))

    # 進行中の phase 一覧を取得（agreements から推定）
    completed_phases = ctx.execute("""
        SELECT DISTINCT phase_id
        FROM agreements
        WHERE run_id = ? AND entry_type = 'Deliverable' AND status = 'Superseded'
    """, (ctx.run_id,))
    completed_phase_ids = {r["phase_id"] for r in completed_phases}

    findings: list[Finding] = []
    for row in rows:
        phase_id = row["phase_id"] or ""
        task_id = row["task_id"] or ""
        # この Directive の phase が完了しているか
        if phase_id in completed_phase_ids:
            findings.append(_make_finding(
                "DB-ORPHAN-PROPOSED-DIRECTIVE", "warning",
                f"agreements.id={row['id']}",
                f"Directive '{row.get('topic', '')}' (phase={phase_id}, task={task_id}) が "
                f"status='Proposed' のまま、対応phaseは完了している",
                _row_to_json(row),
                related_bl="BL-073",
            ))
    return findings


# --- DB-GOAL-SHIFT-UNCONSUMED ---

@register("DB-GOAL-SHIFT-UNCONSUMED", severity="info", related_bl="BL-065")
def check_goal_shift_unconsumed(ctx: DbContext) -> list[Finding]:
    """goal_shift_events に記録があるが、それを消費した形跡が後続 agreements に存在しない。"""
    shifts = ctx.execute("""
        SELECT shift_id, timestamp, shift_kind, from_goal_state, to_goal_state, reason_why
        FROM goal_shift_events
        WHERE run_id = ?
        ORDER BY timestamp
    """, (ctx.run_id,))

    findings: list[Finding] = []
    for shift in shifts:
        shift_ts = shift["timestamp"] or 0
        # シフト以降の agreements を確認
        subsequent = ctx.execute("""
            SELECT COUNT(*) AS cnt
            FROM agreements
            WHERE run_id = ? AND timestamp > ?
        """, (ctx.run_id, shift_ts))
        count = subsequent[0]["cnt"] if subsequent else 0

        if count == 0:
            # シフト後に1件もagreementがない → 消費されていない可能性
            findings.append(_make_finding(
                "DB-GOAL-SHIFT-UNCONSUMED", "info",
                f"goal_shift_events.shift_id={shift['shift_id']}",
                f"goal_shift '{shift['shift_kind']}' 以降にagreementsが存在しない（書きっぱなし問題）",
                _row_to_json(shift),
                related_bl="BL-065",
            ))
    return findings


# --- DB-VERIFIED-FACT-STALE ---

@register("DB-VERIFIED-FACT-STALE", severity="warning")
def check_verified_fact_stale(ctx: DbContext) -> list[Finding]:
    """verified_facts の値が、対応する agreements が Superseded になった後も更新されていない。"""
    facts = ctx.execute("""
        SELECT variable_name, value, unit, source_task_id, source_phase_id, confirmed_at
        FROM verified_facts
        WHERE run_id = ?
    """, (ctx.run_id,))

    findings: list[Finding] = []
    for fact in facts:
        source_task = fact["source_task_id"] or ""
        source_phase = fact["source_phase_id"] or ""
        if not source_task and not source_phase:
            continue

        # 対応する Deliverable が Superseded されているか確認
        superseded = ctx.execute("""
            SELECT COUNT(*) AS cnt
            FROM agreements
            WHERE run_id = ? AND entry_type = 'Deliverable'
              AND phase_id = ? AND task_id = ? AND status = 'Superseded'
        """, (ctx.run_id, source_phase, source_task))

        if superseded and superseded[0]["cnt"] > 0:
            # ソースが Superseded されているのに verified_facts が残っている
            # 最新の verified_facts が Superseded より後か確認
            latest_agreement = ctx.execute("""
                SELECT MAX(timestamp) AS max_ts
                FROM agreements
                WHERE run_id = ? AND entry_type = 'Deliverable'
                  AND phase_id = ? AND task_id = ?
            """, (ctx.run_id, source_phase, source_task))
            latest_ts = latest_agreement[0]["max_ts"] if latest_agreement else 0
            fact_ts = fact["confirmed_at"] or 0

            if fact_ts < latest_ts:
                findings.append(_make_finding(
                    "DB-VERIFIED-FACT-STALE", "warning",
                    f"verified_facts.variable_name={fact['variable_name']}",
                    f"verified_facts '{fact['variable_name']}={fact['value']}' のソース "
                    f"(phase={source_phase}, task={source_task}) が Superseded されているが、"
                    f"値が更新されていない",
                    _row_to_json(fact),
                    related_bl="BL-062",
                ))
    return findings


# --- DB-DEPENDS-ON-CYCLE ---

@register("DB-DEPENDS-ON-CYCLE", severity="warning")
def check_depends_on_cycle(ctx: DbContext) -> list[Finding]:
    """agreements の depends_on が前方参照（未来のtaskに依存）になっている、または循環している。"""
    rows = ctx.execute("""
        SELECT id, phase_id, task_id, depends_on, topic
        FROM agreements
        WHERE run_id = ? AND depends_on IS NOT NULL AND depends_on != ''
    """, (ctx.run_id,))

    # タスクの順序マップ: (phase_id, task_id) -> 出現順
    all_tasks = ctx.execute("""
        SELECT DISTINCT phase_id, task_id, MIN(timestamp) AS first_seen
        FROM agreements
        WHERE run_id = ? AND phase_id IS NOT NULL AND task_id IS NOT NULL
        GROUP BY phase_id, task_id
        ORDER BY first_seen
    """, (ctx.run_id,))
    task_order: dict[tuple[str, str], int] = {}
    for idx, row in enumerate(all_tasks):
        task_order[(row["phase_id"] or "", row["task_id"] or "")] = idx

    findings: list[Finding] = []
    for row in rows:
        depends_on_raw = row["depends_on"] or ""
        # depends_on のパース: カンマ区切り、または JSON 配列
        dep_ids = _parse_depends_on(depends_on_raw)
        current_key = (row["phase_id"] or "", row["task_id"] or "")
        current_order = task_order.get(current_key, -1)

        for dep_id in dep_ids:
            # dep_id が "phase_X_task_Y" 形式かどうか
            dep_parsed = _parse_dep_id(dep_id)
            if dep_parsed:
                dep_key = dep_parsed
                dep_order = task_order.get(dep_key, -1)
                if dep_order > current_order:
                    # 前方参照（未来のタスクに依存）
                    findings.append(_make_finding(
                        "DB-DEPENDS-ON-CYCLE", "warning",
                        f"agreements.id={row['id']}",
                        f"depends_on '{dep_id}' が前方参照（未来のタスク）になっている",
                        f"current: {current_key}, depends_on: {dep_key}",
                        related_bl="",
                    ))
                elif dep_order == current_order and dep_key == current_key:
                    # 自己参照
                    findings.append(_make_finding(
                        "DB-DEPENDS-ON-CYCLE", "warning",
                        f"agreements.id={row['id']}",
                        f"depends_on が自己参照になっている: {dep_id}",
                        _row_to_json(row),
                        related_bl="",
                    ))
    return findings


def _parse_depends_on(raw: str) -> list[str]:
    """depends_on 文字列をパースして依存IDのリストを返す。"""
    raw = raw.strip()
    if not raw:
        return []
    # JSON 配列の場合
    if raw.startswith("["):
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass
    # カンマ区切りの場合
    return [d.strip() for d in raw.split(",") if d.strip()]


def _parse_dep_id(dep_id: str) -> tuple[str, str] | None:
    """依存IDを (phase_id, task_id) にパースする。

    対応形式:
        - "phase_1_task_2_1" -> ("phase_1", "task_2_1")
        - "phase_1/task_2_1" -> ("phase_1", "task_2_1")
        - "1_2_1" -> ("phase_1", "task_2_1")  [数値のみの場合]
    """
    # phase_X_task_Y 形式
    m = re.match(r"phase_(\d+(?:_\d+)*)_task_(\d+(?:_\d+)*)", dep_id)
    if m:
        return (f"phase_{m.group(1)}", f"task_{m.group(2)}")

    # phase_X/task_Y 形式
    m = re.match(r"phase_(\d+(?:_\d+)*)/task_(\d+(?:_\d+)*)", dep_id)
    if m:
        return (f"phase_{m.group(1)}", f"task_{m.group(2)}")

    # 数値のみ（例: "1_2_1" -> phase_1, task_2_1）
    m = re.match(r"(\d+)_(\d+(?:_\d+)*)", dep_id)
    if m:
        return (f"phase_{m.group(1)}", f"task_{m.group(2)}")

    return None


# ===========================================================================
# CLIエントリポイント
# ===========================================================================

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="CELA DB（cela.db）の整合性を検査する",
    )
    parser.add_argument(
        "--db", dest="db_path", default="cela.db",
        help="cela.db のパス（既定: cela.db）",
    )
    parser.add_argument(
        "--run-id", dest="run_id", default=None,
        help="検査対象の run_id（省略時は cela.db の最新レコードから自動検出）",
    )
    parser.add_argument(
        "--log-dir", dest="log_dir", default="",
        help="ログディレクトリ（例: log/2026-07-25/1913）。"
             "DB-WRITEBACK-MISMATCH のファイル突合に使う。省略時はこのチェックのみスキップ。",
    )
    parser.add_argument(
        "--json", dest="json_path", default=None,
        help="JSON Lines出力先ファイルパス",
    )
    parser.add_argument(
        "--min-severity", dest="min_severity",
        default="info", choices=["critical", "warning", "info"],
        help="出力する最低severity（既定: info = 全て出力）",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    # run_id の解決
    run_id = args.run_id
    if not run_id:
        run_id = extract_latest_run_id_from_db(args.db_path)
    if not run_id:
        print("エラー: run_id を指定するか、cela.db に既存の decisions レコードが必要です。",
              file=sys.stderr)
        return 2

    ctx = DbContext.from_args(args.db_path, run_id, log_dir=args.log_dir)
    try:
        findings = run_checks(ctx, min_severity=args.min_severity)
        return output_findings(findings, json_path=args.json_path, min_severity=args.min_severity)
    finally:
        ctx.close()


if __name__ == "__main__":
    sys.exit(main())