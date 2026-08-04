"""
BL-134 候補(a): Expertがゴール文にない「24時間365日」監視前提を無根拠に確定値化した
実インシデントを受け、部分的な要件（「最低N名常駐」等）を時間帯・範囲等の条件を無視して
拡大解釈することを避けるための罠（ピットフォール）注記をcall_expert/generate_user_utterance
双方のプロンプトへ追加した。

D-094が確立した「マインドセット／目的別行動オプション／罠」の3層モデルに則り、
①拡大解釈する際は根拠となるゴール文中の記述を明示すること、②根拠が無い場合は
confidence="provisional"として扱いwrite_issueで記録することを求める。

候補(b)（issue_logの可視性・強制力強化、タスク遷移ゲート）はBL-125/BL-136で対応済み。
候補(c)（Detectorのconstraint_issue判定基準の見直し）は、call_detectorのドメイン妥当性
レビューが意図的に「情報不足のみを理由にmajorにしない」という設計（BL-012/BL-133の
非退行テストが保証する誤検知抑制と表裏一体）であることを確認した上で、見直し不要と判断した
（記録のみ、コード変更なし）。

参照: docs/design/back_log/issue_backlog.md BL-134。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_call_expert_has_unsupported_generalization_pitfall():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-134" in src
    assert "拡大解釈" in src
    assert "provisional" in src


def test_generate_user_utterance_has_unsupported_generalization_checklist_item():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "BL-134" in src
    assert "拡大解釈" in src


def test_call_detector_domain_review_criteria_unchanged_by_design():
    """[BL-134候補(c)、記録のみ] call_detectorのドメイン妥当性レビューは、情報不足のみを
    理由にconstraint_issue="major"にしない設計を意図的に維持している（BL-012/BL-133の
    誤検知抑制と表裏一体のため、この非退行テストで変更されていないことを明示的に確認する）。
    """
    src = inspect.getsource(cela_main.call_detector)
    assert "情報が不足していて確認できない" in src
    assert "majorの" in src and "根拠にしてはいけません" in src
