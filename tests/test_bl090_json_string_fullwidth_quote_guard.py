"""
BL-090: goal_essence_analystの応答が、JSON文字列値の末尾を全角鉤括弧「」で
終えたためJSON構文の閉じ引用符(")が欠落し、パース失敗する事象を確認
（`log/2026-07-25/1913` L424、`⚠️ JSON判定パース失敗を検知。層2リトライ 1/2...`で
自己修復はしたが、根本原因はプロンプト側の未指示だった）。

再発防止として、call_goal_essence_analystのプロンプトに「JSON文字列値の末尾を
全角鉤括弧で終えない」旨の指示を追加した。層2リトライ（BL-089）が既にあるため
実害は軽微だったが、そもそもリトライ自体を減らすための予防指示。

参照: docs/design/issue_backlog.md BL-090、docs/design/decision_log.md D-066。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_goal_essence_analyst_has_fullwidth_quote_guard_instruction():
    src = inspect.getsource(cela_main.call_goal_essence_analyst)
    assert "全角鉤括弧" in src
    assert "末尾" in src
