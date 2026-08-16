"""
BL-245: Detectorの「思考プロセス監査（R5）」が、target_role=="user"（User AI Stage3の
承認/却下判断そのものを監査する場合）にも、Expert向けに設計された「事後正当化が見られたら
強制差し戻し（major）」という指示を無条件に適用していた問題。

log/2026-08-16/1150（task_2_4_1、V1→V24でRejectedを8回繰り返す停滞）を機械的に調査した
ところ、同一のDetector応答内で以下の自己矛盾が複数回確認された:
  criteria_status=[true,true,true]（BL-023の受入基準チェックは全項目充足と自己申告）
  でありながら、"AIの思考過程では独立した確認や検証を行わず、ユーザーの再提出への自信を
  根拠に承認を急いでおり、思考プロセス監査上の重大な事後正当化に該当する" という理由で
  constraint_issue="major"としていた。

原因は、R5の思考プロセス監査文言（「計算ツールを使っていないのに適当な数字を出している」
「都合の悪い制約から目を逸らして結論を急いでいる」→ハルシネーション扱いで強制major）が、
target_roleに関わらず同一のまま適用されていたこと。この文言はExpertの数値的主張
（python_replを使わず適当な数字を出す等）を想定して設計されたもので、python_replを
持たないUser AI Stage3の承認判断（本質的に確信を持った言い切りになりやすい）へ適用すると、
正当な承認そのものが「結論を急いだハルシネーション」と機械的に誤判定されてしまう。

target_role=="user"の場合のみ、強制差し戻し指示を外し、reasoningを参考情報として提示する
に留め、判断はBL-023のcriteria_status等の構造化判定へ委ねるよう修正した。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-245。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_detector_source_branches_thought_audit_by_target_role():
    """[BL-245本体] call_detectorのソースに、target_role=="user"かどうかで
    thought_process_auditの文面を分岐させる処理が存在すること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert 'if target_role == "user":' in src
    assert "思考プロセス監査" in src
    assert "思考プロセス（参考情報）" in src


def test_forced_major_instruction_absent_when_target_role_is_user():
    """target_role=="user"向けの分岐には、「強制差し戻し（major）としてください」という
    Expert向けの強制指示が含まれていないこと（confident な承認言い回しをハルシネーション
    扱いしない）。"""
    src = inspect.getsource(cela_main.call_detector)
    user_branch_start = src.index('思考プロセス（参考情報）')
    user_branch = src[user_branch_start:user_branch_start + 700]
    assert "強制差し戻し（major）としてください" not in user_branch
    assert "確信を持った言い回しで承認している" in user_branch or "参考情報" in user_branch


def test_forced_major_instruction_still_present_for_expert_branch():
    """回帰確認: target_role!="user"（Expertの成果物監査）向けの強制差し戻し指示自体は
    維持されていること（R5導入時の数値ハルシネーション対策は変更しない）。"""
    src = inspect.getsource(cela_main.call_detector)
    expert_branch_start = src.index('思考プロセス監査（★R5追加）')
    expert_branch = src[expert_branch_start:expert_branch_start + 700]
    assert "強制差し戻し（major）としてください" in expert_branch
    assert "計算ツールを使っていないのに適当な数字を出している" in expert_branch


def test_reasoning_source_field_selection_unchanged():
    """回帰確認: target_role=="expert"ならexpert_last_reasoning、それ以外は
    user_last_reasoningを参照する既存の配線は変更していないこと（BL-245はR5指示文言の
    target_role分岐のみを対象とし、参照元フィールドの分岐自体はtest_r5_thought_log_
    freeze_goalshift.pyの既存テストが検証する範囲を変えない）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "expert_last_reasoning" in src
    assert "user_last_reasoning" in src
