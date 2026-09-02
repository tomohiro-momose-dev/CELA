"""
BL-267: MemTrapBench（arXiv:2608.20202）が指摘する記憶誘発性の認知的罠への予防的プロンプトガード。

ユーザーが同論文を紹介し、直近3日分（2026-08-15〜17、計44ドライラン）の実データ調査で
実害は確認されなかったものの、「プロンプトで対策できる予防的処置はしておくに越したことはない」
と判断。CELAはD-207（Expert/Userの生reasoningを常時無条件で次iterationへ引き継ぐ設計）により
Trauma型の罠（過去の厳しい差し戻しの記憶が、後続の無関係なタスクで本来正しい手法を回避させる）
が発生しうる土壌を持つため、同論文の緩和策AdaptiveMemが提示する4リスク（タスク境界の変化・
戦略の過剰一般化・trauma由来の回避・安全前提の漏出）をCELAの語彙へ翻訳した共有プロンプト
ブロック`_MEMORY_TRAP_GUARD_PARAGRAPH`を新設し、`_USER_AI_ROLE_MANDATE`（BL-247）と同型の
パターンでcall_expert・generate_user_utteranceの計5箇所へ注入する。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-267、
docs/design/back_log/BL-267/BL267_investigation.md。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_memory_trap_guard_covers_four_adaptivemem_risks():
    """[BL-267本体] _MEMORY_TRAP_GUARD_PARAGRAPHが、AdaptiveMemの4リスク（タスク境界・
    戦略の過剰一般化・過去の否定的指摘の過剰回避・仮説的前提の混入）をCELAの語彙へ
    翻訳した形で含んでいること。"""
    text = cela_main._MEMORY_TRAP_GUARD_PARAGRAPH
    assert "タスク境界" in text
    assert "過剰一般化" in text
    assert "過去の否定的指摘" in text or "過剰回避" in text
    assert "仮説的前提" in text


def test_memory_trap_guard_preserves_d207_information_retention_intent():
    """[設計意図の確認] D-207が守ろうとした「情報保存」の趣旨を本ガード自体が損なわない
    よう、「記憶を無視してよいという意味ではない」という明示的な留保が入っていること。"""
    text = cela_main._MEMORY_TRAP_GUARD_PARAGRAPH
    assert "記憶を無視してよい" in text
    assert "真剣に受け止め" in text


def test_memory_trap_guard_wired_into_call_expert():
    """call_expertのソース内で_MEMORY_TRAP_GUARD_PARAGRAPHが参照されていること。"""
    source = inspect.getsource(cela_main.call_expert)
    assert source.count("_MEMORY_TRAP_GUARD_PARAGRAPH") >= 1


def test_memory_trap_guard_wired_into_all_four_user_ai_stages():
    """generate_user_utteranceのソース内で、_USER_AI_ROLE_MANDATEと同じ4箇所
    （Stage1レビュー・Stage3承認判断・Stage4の次タスク指示/現タスク修正指示の両分岐）から
    _MEMORY_TRAP_GUARD_PARAGRAPHが参照されていること（BL-247と同型のinspect.getsourceパターン）。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    assert source.count("_MEMORY_TRAP_GUARD_PARAGRAPH") == source.count("_USER_AI_ROLE_MANDATE")
    assert source.count("_MEMORY_TRAP_GUARD_PARAGRAPH") >= 4


def test_memory_trap_guard_not_forced_into_approval_recording_failed_branch():
    """[設計意図の確認] ApprovalRecordingFailed分岐（技術的待機メッセージ、Agent AIの
    成果物内容には一切言及・評価しないことが要件）には、_USER_AI_ROLE_MANDATEと同様に
    本ガードも混入させていないこと。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    idx = source.index('第3段で承認処理を試みましたが、システム側の技術的な理由で')
    branch_start = source.rindex("stage4_system_prompt = (", 0, idx)
    branch_end = source.index(")", idx)
    branch_text = source[branch_start:branch_end]
    assert "_MEMORY_TRAP_GUARD_PARAGRAPH" not in branch_text
