"""
BL-087: task_plannerの曖昧表記禁止指示 + User AIの二重指示（再提出要求）バグ修正。

実LLMドライラン（log/2026-07-25/0935）レビューで、task_1_3のacceptance_criteriaの
"(12km区間)"という表記が「位置」か「長さ」か曖昧だったため、Expertが同一の誤読
（15%=2.175kmを12km全区間=82.8%と誤定義）を4回連続で繰り返し、V1→V9まで9版もの
無駄な往復が発生した。また、User AIの標準指示に「合意に達したら相手のAIに成果物の
出力を指示せよ」という無条件の文言があり、R4のホワイトボード方式で既に成果物が
Approved済みの場合でも同じ指示を繰り返すため、Expertが「既に提出済みなのに再度
出力を求められている」と戸惑う場面が生じていた。

対策として、(1) call_task_plannerのプロンプトに曖昧表記を避けるための明示指示を追加、
(2) generate_user_utteranceの標準指示に、未充足項目が無く成果物が既にホワイトボードに
存在する場合は再提出を求めないという条件分岐を追加した。

参照: docs/design/issue_backlog.md BL-087（前提の質を上げる一連の改善、Stage 1）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl087_task_planner_prompt_warns_against_ambiguous_ratio_vs_length_wording():
    """call_task_plannerのプロンプトに、比率/絶対値の取り違えを防ぐ注意書きが含まれること。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "曖昧な表記の禁止" in src
    assert "比率か絶対値か" in src


def test_bl087_task_planner_prompt_references_the_12km_15_percent_failure_example():
    """再発防止のため、実際に起きた15%/12km区間の誤読事例がNG例として埋め込まれていること。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "15%" in src
    assert "12km区間" in src


def test_bl087_generate_user_utterance_does_not_unconditionally_demand_resubmission():
    """generate_user_utteranceの標準指示が、未充足項目なし＋ホワイトボード存在時は
    再提出を求めない条件分岐を含むこと（二重指示バグの修正確認）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert "未充足の項目はありません" in src
    assert "再提出を重ねて指示しないでください" in src
