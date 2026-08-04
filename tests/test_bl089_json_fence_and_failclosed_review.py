"""
BL-089: _safe_json_parseが複数の```json...```フェンスブロックを取り違えるバグの修正、
および、task_plan_reviewer等のJSON判定パース失敗時のフェイルクローズ化。

実ドライラン（`log/2026-07-25/1814`）で、task_planner出力が途中で切れて縮退計画
（fallback_phase）に落ちた上、task_plan_reviewerはこの縮退計画を正しく"major"と
判定したにもかかわらず、その応答が「### per_task_comments」セクションのプレビュー用
配列ブロックと「### 最終JSON出力」セクションの本物のオブジェクトブロックという、
2つの```json...```フェンスブロックで構成されていたため、_safe_json_parseが
両者を混線させて構文エラーとなり、fallback（constraint_issue="none"）に化けた。
結果、縮退計画がそのまま承認され、実行フェーズへ進んでしまった
（`log/2026-07-25/1814/whiteboards/`にphase_1_task_1_1のみが存在することで確認）。

対策:
1. _safe_json_parseは、複数のフェンスブロックがあれば**最後の**ブロックを採用する
   （モデルは「最終的な答え」を最後に書く慣習に従う）。
2. call_task_plan_reviewer/call_task_planner/call_goal_essence_analystを
   _query_and_parse_with_retry（層2リトライ、D-005）でラップし、単発のパース失敗で
   即座にfallbackへ落ちないようにする。
3. call_task_plan_reviewerは、リトライを使い切ってもなおパース失敗した場合、
   実行前ゲートという性質上、"none"（フェイルオープン=承認）ではなく"major"
   （フェイルクローズ=差し戻し）を返すようにする。

参照: docs/design/issue_backlog.md BL-089、docs/design/decision_log.md D-064。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl089_reflection.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""


def test_safe_json_parse_prefers_last_of_multiple_fenced_blocks():
    """`1814`ログの実際の失敗パターン: プレビュー用の小さな配列ブロックの後に、
    本物の完全なオブジェクトブロックが続く場合、後者が採用されること。"""
    raw = (
        "### per_task_comments\n\n"
        "```json\n"
        '[\n  {"task_id": "task_1_1", "comment": "preview comment"}\n]\n'
        "```\n\n---\n\n### 最終JSON出力\n\n"
        "```json\n"
        '{\n  "risk": "high",\n  "constraint_issue": "major",\n  "comment": "real comment",\n'
        '  "observations": "",\n  "per_task_comments": [{"task_id": "task_1_1", "comment": "preview comment"}]\n}\n'
        "```"
    )
    result = cela_main._safe_json_parse(raw, fallback={"risk": "low", "constraint_issue": "none"})
    assert result["constraint_issue"] == "major"
    assert result["comment"] == "real comment"


def test_safe_json_parse_single_fence_with_leading_prose_still_works():
    """複数フェンス対応を追加しても、フェンスが1つだけ（BL-088のケース）の回帰がないこと。"""
    raw = "それでは提示します。\n\n```json\n[{\"a\": 1}]\n```"
    result = cela_main._safe_json_parse(raw, fallback=[{"fallback": True}])
    assert result == [{"a": 1}]


def test_safe_json_parse_no_fence_falls_back_to_brace_bracket_heuristic():
    """フェンスが全く無い場合は、従来のbrace/bracket探索ロジックにフォールバックすること。"""
    raw = 'ここに説明文があります。{"risk": "low"}'
    result = cela_main._safe_json_parse(raw, fallback={"risk": "none"})
    assert result == {"risk": "low"}


def test_call_task_plan_reviewer_retries_on_parse_failure_then_succeeds(monkeypatch):
    """1回目がパース不能な応答でも、層2リトライで2回目の正常な応答を拾えること。"""
    calls = {"n": 0}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "壊れた応答（JSONではない）"
        return '{"risk": "low", "constraint_issue": "none", "comment": "", "observations": "", "per_task_comments": []}'

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_task_plan_reviewer([{"phase_id": "phase_1", "tasks": []}], "テスト目標")

    assert calls["n"] == 2
    assert result["constraint_issue"] == "none"


def test_call_task_plan_reviewer_fails_closed_to_major_after_exhausting_retries(monkeypatch):
    """[BL-089] 全リトライを使い切ってもパース不能な場合、"none"（フェイルオープン）
    ではなく"major"（フェイルクローズ）を返すこと。安全ゲートが誤って縮退計画を
    承認してしまう事態（`1814`ログで実際に発生）を防ぐ。"""
    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        return "常に壊れた応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_task_plan_reviewer([{"phase_id": "phase_1", "tasks": []}], "テスト目標")

    assert result["constraint_issue"] == "major"


def test_call_task_planner_retries_on_parse_failure_then_succeeds(monkeypatch):
    """call_task_plannerも層2リトライで単発のパース失敗を吸収できること。"""
    calls = {"n": 0}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "壊れた応答"
        return '[{"phase_id": "phase_1", "title": "t", "tasks": []}]'

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_task_planner("テスト目標")

    assert calls["n"] == 2
    assert result == [{"phase_id": "phase_1", "title": "t", "tasks": []}]


def test_call_task_planner_falls_back_to_degenerate_plan_after_exhausting_retries(monkeypatch):
    """全リトライを使い切った場合は、従来通りfallback_phase（縮退計画）を返すこと
    （task_plan_reviewer_nodeが後段でこれを検知しmajor判定する前提のため、
    call_task_planner自体はfail-closedにする必要はない）。"""
    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        return "常に壊れた応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_task_planner("テスト目標")

    assert result[0]["tasks"][0]["task_id"] == "task_1_1"
    assert result[0]["tasks"][0]["title"] == "初期タスク"


def test_call_goal_essence_analyst_retries_on_parse_failure_then_succeeds(monkeypatch):
    """call_goal_essence_analystも層2リトライで単発のパース失敗を吸収できること。"""
    calls = {"n": 0}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "壊れた応答"
        return '{"true_essence": "本質", "feasibility_notes": "問題なし"}'

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_goal_essence_analyst("テスト目標")

    assert calls["n"] == 2
    assert result == {"true_essence": "本質", "feasibility_notes": "問題なし"}


def _base_reflection_state(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "goal": "テスト目標",
        "chat_history": [],
        "constraint_issue_log": [],
        "round_count": 3,
        "reflection_interval": 3,
        "risk_register": [],
    }


def test_call_reflection_retries_on_parse_failure_then_succeeds(db_conn, monkeypatch):
    """[BL-120] call_reflectionも層2リトライで単発のパース失敗を吸収できること
    （従来は単発query_AI+_safe_json_parseで、1回の崩れが即座にstagnant判定に直結していた）。"""
    conn, run_id = db_conn
    calls = {"n": 0}

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        calls["n"] += 1
        if calls["n"] == 1:
            return "壊れた応答（JSONではない）"
        return '{"still_aligned": true, "discussion_status": "continuing", "note": "順調です"}'

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_reflection(_base_reflection_state(run_id), config={})

    assert calls["n"] == 2
    assert result["discussion_status"] == "continuing"


def test_call_reflection_fails_closed_to_stagnant_after_exhausting_retries(db_conn, monkeypatch):
    """[BL-120] 全リトライを使い切ってもパース不能な場合は、従来通りstagnantへ
    フェイルクローズすること（stagnant自体は安全側の判定として妥当。真の修正点は、
    1回の一時的なパース崩れだけで即座にこれへ落ちなくなったことの方）。"""
    conn, run_id = db_conn

    def fake_query_ai(messages, client, model, label, tools=None, light_system_prompt=None, state=None):
        return "常に壊れた応答"

    monkeypatch.setattr(cela_main, "query_AI", fake_query_ai)
    result = cela_main.call_reflection(_base_reflection_state(run_id), config={})

    assert result["discussion_status"] == "stagnant"
