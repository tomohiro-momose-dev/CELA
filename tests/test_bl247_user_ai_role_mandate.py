"""
BL-247: User AIの役割そのものを明文化する共通ブロック。

ユーザーが「ユーザーAIの役割は、目標、フェーズ、タスクの意図を読み取り、その意図と何を
具体化させるか、させなければならないかを考え、その手段と作業をエキスパートに指示をする。
それに基づき、レビューも行う。そのように動くようにプロンプトを修正、または追記」と指示。

BL-192/BL-246が「指示文の質」という戦術面（web_search義務化・思考プロセス明示・ツール一覧・
深堀り）を扱うのに対し、BL-247はその土台となる上位の役割認識——「acceptance_criteriaの
字面だけを検収するのではなく、目標・フェーズ・タスクの意図を自分で読み取り、何を具体化
すべきかを考えて指示・レビューする」——を、レビュー段（Stage1）・承認判断段（Stage3）・
次タスク指示段（Stage4、次タスク指示/現タスク修正指示の両分岐）に共通して明文化する。

issue確認段（Stage2、既存issueの状態整理という機械的な作業が主）と、技術的待機メッセージ
（ApprovalRecordingFailed、Agent AIの成果物内容には一切言及しないことが要件）には適用しない
（意図の読み取り・具体化の判断がそもそも不要または禁止されているため）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-247。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_role_mandate_constant_expresses_intent_reading_and_concretization():
    """[BL-247本体] _USER_AI_ROLE_MANDATEが、意図を読み取る・何を具体化すべきか考える・
    それに基づき指示とレビューを行う、という3要素を含んでいること。"""
    text = cela_main._USER_AI_ROLE_MANDATE
    assert "意図" in text
    assert "具体的にする" in text or "具体化" in text
    assert "指示" in text
    assert "レビュー" in text or "承認判断" in text


def test_role_mandate_wired_into_stage1_and_stage3_and_stage4():
    """generate_user_utteranceのソース内で、_USER_AI_ROLE_MANDATEが複数箇所
    （Stage1レビュー・Stage3承認判断・Stage4の次タスク指示/現タスク修正指示の両分岐）から
    参照されていること（BL-192と同型のinspect.getsourceパターン）。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    assert source.count("_USER_AI_ROLE_MANDATE") >= 4


def test_role_mandate_not_forced_into_approval_recording_failed_branch():
    """[設計意図の確認] ApprovalRecordingFailed分岐（技術的待機メッセージ、Agent AIの
    成果物内容には一切言及・評価しないことが要件）には、意図読み取り・具体化の判断を
    求める_USER_AI_ROLE_MANDATEを混入させていないこと。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    idx = source.index('第3段で承認処理を試みましたが、システム側の技術的な理由で')
    branch_start = source.rindex("stage4_system_prompt = (", 0, idx)
    branch_end = source.index(")", idx)
    branch_text = source[branch_start:branch_end]
    assert "_USER_AI_ROLE_MANDATE" not in branch_text
