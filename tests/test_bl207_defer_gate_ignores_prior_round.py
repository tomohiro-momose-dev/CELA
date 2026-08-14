"""
BL-207: BL-181のDetectorプロンプト指示が、write_issue(DEFER)の実行済み判定を
「今回の発言内で対応されていなければ」という基準で行っていたため、既に前のラウンドで
正式にDEFER済み（defer_to_task_idが設定済み）のissueに対しても、承認・移行を試みる
たびに毎回majorで差し戻し続ける無限ループが発生した（`log/2026-08-10/2100`、
task_2_3→task_3_1の移行がラウンド31〜36以上にわたり繰り返し差し戻された）。

根本原因：write_issue(DEFER)は仕様上statusを'escalated'のまま変更せず、
defer_to_task_idだけを記録する（BL-136設計、cela_main.py:3471-3473）。実際の遷移を
ブロックする機械的ゲート（_get_blocking_issues_for_transition、BL-125/158）は
defer_to_task_idが設定済みのissueを正しく除外するが、Detector自身のLLM判定に
渡すBL-181のプロンプト指示だけがdefer_to_task_idを見ず、「今回の発言内で」の
RESOLVE/DEFER実行を要求しており、両者が矛盾していた。

対応：BL-181のプロンプト指示を、defer_to_task_idが（いつ設定されたかに関わらず）
既に設定済みであれば先送り済みとみなし、majorとしないよう修正した。

参照: docs/design/back_log/issue_backlog.md BL-207、BL-181、BL-125、BL-136。
実LLM API呼び出しは伴わない（プロンプト文言のソース検証のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _bl181_block_text() -> str:
    src = inspect.getsource(cela_main.call_detector)
    user_branch_idx = src.index('if target_role == "user":\n        role_specific_instruction')
    bl181_idx = src.index("BL-181", user_branch_idx)
    bl207_idx = src.index("BL-207", bl181_idx)
    # BL-181節の終わり（次の三重引用符閉じ）までを切り出す
    end_idx = src.index('""")', bl181_idx)
    return src[bl181_idx:end_idx], bl207_idx


def test_bl181_block_now_references_bl207_and_defer_to_task_id():
    block, _ = _bl181_block_text()
    assert "BL-207" in block
    assert "defer_to_task_id" in block


def test_bl181_block_explains_defer_does_not_clear_escalated_status():
    """[BL-207] statusが'escalated'のまま変わらないこと自体を先送り未対応の根拠にしない
    よう、その理由（write_issue(DEFER)の仕様）を明記していることを確認する。"""
    block, _ = _bl181_block_text()
    assert "escalated" in block
    assert "先送り済み" in block


def test_bl181_block_no_longer_requires_same_utterance_defer():
    """[BL-207] 旧文言「今回の発言内でそのissueが...対応されていなければ」は、既に
    defer_to_task_id設定済みのissueにも毎ラウンド再DEFERを要求してしまう無限ループの
    原因だった。この特定の文字列（今回の発言内で対応されていなければ、それだけで
    majorとする趣旨の文）が、defer_to_task_id確認の記述より前に単独で出てこないことを
    確認する。"""
    block, bl207_idx = _bl181_block_text()
    # 修正後の文言は「defer_to_task_idが未設定のまま残っている場合のみ」major、という
    # 条件が明示されていること（無条件に「今回の発言内」を要求する文言ではないこと）。
    assert "未設定のまま残っている" in block
    # BL-207の説明は、defer_to_task_id確認の指示より後（同じ段落内）に置かれていること。
    defer_check_idx = block.index("defer_to_task_id")
    assert bl207_idx > defer_check_idx - len(block)  # sanity: within same block


def test_bl181_block_still_defers_to_major_when_truly_unresolved():
    """[BL-207] 修正は「先送り済みなら通す」だけであり、defer_to_task_id未設定のまま
    残存するmajor/escalated issueがある場合に差し戻す本来の趣旨（BL-181）は維持する。"""
    block, _ = _bl181_block_text()
    assert "major" in block
    assert "RESOLVE" in block and "DEFER" in block
    assert "残存issueをRESOLVEまたはDEFERせよ" in block


def test_existing_bl181_source_assertions_still_hold():
    """既存テスト（test_bl181_task_transition_block_stops_orchestrator.py）が検証していた
    基本的な骨格（BL-181/read_issues/RESOLVE/DEFERがuserブランチ内にあること）が
    今回の修正で壊れていないことを確認する。"""
    src = inspect.getsource(cela_main.call_detector)
    assert "BL-181" in src
    assert "read_issues" in src
    assert "RESOLVE" in src and "DEFER" in src
    user_branch_idx = src.index('if target_role == "user":\n        role_specific_instruction')
    bl181_idx = src.index("BL-181")
    assert bl181_idx > user_branch_idx
