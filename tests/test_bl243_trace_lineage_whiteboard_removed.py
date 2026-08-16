"""
BL-243: _TRACE_LINEAGE_USAGE_PARAGRAPH（Expert/User AI(Stage1/Stage3)/Detector等7箇所から
共有される、trace_lineageの使い方を説明する定型文）が、whiteboard:<phase_id>:<task_id>を
「経緯を辿るのに使える」refとして案内し続けていた問題。

BL-238はExpert向けの改版3回目発火ブロック（_build_task_scope_context）から
trace_lineage(whiteboard:...)呼び出し指示を削除したが、この共通段落は対象外だったため
残存していた。relation_edgesにwhiteboard: refを指すエッジを書く本番コード経路は
_write_relation_edgeの全4呼び出し箇所（agreement→agreement、agreement→fact、fact→ref、
detector_review→turn）のいずれにも存在しない。そのため、User AI Stage1/Stage3が実際に
この段落の指示に従いwhiteboard: refでtrace_lineageを呼んだ結果、書式が正しくても
（whiteboard:phase_2:task_2_2、log/2026-08-15/2149）系譜0件、書式を誤ると
（whiteboard:task_1_2、log/2026-08-16/1111）「該当refなし」になることを実ログで確認した。
書式の正誤に関わらず常に無駄打ちになる指示だったことになる。

BL-238と同じ結論（版歴を読む専用の消費経路は不要、issue_log.occurrence_countの機械的
エスカレーションが既に同じ役目を担っている）をこの共有段落にも適用し、whiteboard:への
言及を削除する。_resolve_ref_table/_write_relation_edgeの汎用whiteboard:分岐自体は
test_bl228_chat_history_lineage.pyが検証する既存の汎用機構であり、削除しない
（trace_lineageツール自体がwhiteboard: refを受け付けること自体は害がなく、単に
「使うよう積極的に案内する」ことをやめるだけ）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-243。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_usage_paragraph_no_longer_mentions_whiteboard_ref_format():
    """[BL-243本体] 共有段落からwhiteboard:<phase_id>:<task_id>というref書式の案内が
    消えていること（実際に呼んでも常にlineage=0件になる書式を案内し続けない）。"""
    paragraph = cela_main._TRACE_LINEAGE_USAGE_PARAGRAPH
    assert "whiteboard:" not in paragraph
    assert "ホワイトボードの版歴" not in paragraph


def test_usage_paragraph_still_mentions_working_ref_types():
    """回帰確認: 実際にrelation_edgesが書かれるref型（fact:/agreement:/turn:/issue:/
    detector_review:）の案内は引き続き残っていること。"""
    paragraph = cela_main._TRACE_LINEAGE_USAGE_PARAGRAPH
    assert "fact:<変数名>" in paragraph
    assert "turn:<chat_history.id" in paragraph
    assert "issue:<topic>" in paragraph
    assert "detector_review:<id>" in paragraph


def test_usage_paragraph_still_wired_into_expert_and_user_prompts():
    """回帰確認: BL-228の配線（Expert/User AIプロンプトへの実注入）自体は変更していないこと。"""
    src_expert = inspect.getsource(cela_main.call_expert)
    assert "trace_lineage" in src_expert
    src_user = inspect.getsource(cela_main.generate_user_utterance)
    assert "_TRACE_LINEAGE_USAGE_PARAGRAPH" in src_user


def test_whiteboard_ref_generic_mechanism_still_intact():
    """[§17.1後段/回帰] _resolve_ref_table・_write_relation_edgeのwhiteboard:分岐自体は
    削除していないこと（test_bl228_chat_history_lineage.pyが検証する汎用機構であり、
    今回の修正対象は「積極的に使うよう案内する文言」のみ）。"""
    src_resolve = inspect.getsource(cela_main._resolve_ref_table)
    assert "whiteboard:" in src_resolve
    src_handler = inspect.getsource(cela_main._trace_lineage_handler)
    assert "whiteboard:" in src_handler
