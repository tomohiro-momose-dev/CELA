"""
BL-088: _safe_json_parseが、コードフェンス前に説明文が付いたJSON配列を
誤ってfallbackへ落としてしまうバグの修正。

実ドライラン（`log/2026-07-25/1642`）で、task_plannerが「それでは、フェーズ分解を
提示します。\n\n```json\n[...]\n```」のように、コードフェンスの前に一言添えた
応答を返した際、生成された5〜6フェーズの正しい計画が握りつぶされ、
call_task_plannerのfallback_phase（縮退した1タスクのみの計画）に化けていた。

原因は_safe_json_parseの段階2（先頭が`{`/`[`でない場合に開始位置を探すロジック）が、
`{`が見つかりさえすれば、それが`[`より後にあっても常に`{`を優先していたこと。
トップレベルが配列（`[{...}, {...}]`）の場合、本来の開始位置である`[`より先に
最初のオブジェクトの`{`を検出してしまい、`[`を読み飛ばした結果、構文的に不正な
JSON（`{...}, {...}]`）になりjson.loadsが失敗、fallbackへ落ちていた。
このバグはtask_plan_reviewer_node（BL-087 Stage2）の差し戻しリトライ予算を
2回とも無駄撃ちさせ、3回目（最終・強制承認）でも再現していれば縮退計画が
そのまま本番の最終計画として承認されるところだった。

参照: docs/design/issue_backlog.md BL-088、docs/design/decision_log.md D-062。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_safe_json_parse_extracts_array_when_prose_precedes_fenced_code_block():
    """`1642`ログの実際の失敗パターン（コードフェンス直前に一文が付き、トップレベルが
    配列）を再現し、fallbackへ落ちずに正しくパースされること。"""
    raw = (
        "それでは、フェーズ分解を提示します。\n\n"
        "```json\n"
        "[\n"
        '    {"phase_id": "phase_1", "title": "前提整理", "tasks": []},\n'
        '    {"phase_id": "phase_2", "title": "運行設計", "tasks": []}\n'
        "]\n"
        "```"
    )
    result = cela_main._safe_json_parse(raw, fallback=[{"fallback": True}])
    assert result == [
        {"phase_id": "phase_1", "title": "前提整理", "tasks": []},
        {"phase_id": "phase_2", "title": "運行設計", "tasks": []},
    ]


def test_safe_json_parse_still_prefers_brace_when_object_genuinely_comes_first():
    """トップレベルがオブジェクトで、かつ本文中に`[`を含む配列値がある通常のケース
    （例: Detector系のfallbackはdict）では、従来通り`{`から正しく開始できること
    （今回の修正がmin()判定に変わっても、この既存ケースを壊さない回帰確認）。"""
    raw = 'ここに説明文があります。\n{"risk": "low", "observations": ["a", "b"]}'
    result = cela_main._safe_json_parse(raw, fallback={"risk": "none"})
    assert result == {"risk": "low", "observations": ["a", "b"]}


def test_safe_json_parse_falls_back_when_neither_brace_nor_bracket_present():
    """`{`も`[`も一切含まれない完全な非JSON応答では、例外を出さずfallbackを返すこと。"""
    result = cela_main._safe_json_parse("すみません、うまく生成できませんでした。", fallback={"x": 1})
    assert result == {"x": 1}
