"""
BL-142: User AIの「承認・次タスクへの移行」発言がDetectorにmajor判定された場合、
User AIが承認を撤回してExpertへ修正指示を出す代わりに、言い回しを変えただけの同じ承認を
繰り返す実例が`log/2026-08-01/2329`で観測された（route_after_user_detectorはUser AI自身
（generate_user_utterance）へ差し戻す設計だが、Userが指摘を踏まえて承認を撤回せず、
実質同じ承認文を5ラウンド言い換えるだけで空回りし、その間ホワイトボードの根本的な数値矛盾
（M-07の倍率不一致等）には一切手が入らなかった）。

対策: generate_user_utteranceのmajor判定時プロンプトへ、却下された発話が「承認」だった場合は
write_agreement(status="Rejected")で明示的に撤回し、Agent AIへ具体的な修正指示を出すことを
求める一文を追加した。

参照: docs/design/back_log/issue_backlog.md BL-142。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_generate_user_utterance_instructs_retracting_approval_on_major():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "BL-142" in src
    assert "撤回" in src
    assert 'status="Rejected"' in src


def test_generate_user_utterance_major_block_still_present():
    """既存のBL-142以前からの差し戻しプロンプト（却下理由の提示・再出力指示）が
    誤って壊されていないこと。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "却下されたあなたの前回の発話" in src
    assert "constraint_issue_log" in src
