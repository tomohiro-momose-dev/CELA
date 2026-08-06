"""
BL-166: `_build_agreements_context`のアイコン・ラベル判定が、Rejectされた成果物を
「✅承認済み」と表示してしまう。

`entry_type == "Deliverable"`の場合、旧ロジックは`icon = "📄" if status == "Proposed" else "✅"`
という二値判定で、`"Approved"`系だけでなく`"Rejected"`も無条件で✅にしていた（Decision/Directive
エントリには存在するRejected専用の分岐がDeliverableだけ欠けていた）。実ログ（`log/2026-08-04/1123`）
で、Rejectされたまま一度も承認されていないtask_1_3が「✅ [成果物]」として表示され続け、User AIが
「Completed and approved」と誤認したまま次タスクへ進もうとする実害を確認した。

参照: docs/design/back_log/issue_backlog.md BL-166、BL-062。実LLM API呼び出しは伴わない。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _deliverable(status: str, topic: str = "task_1_3 財務持続性モデル構築") -> dict:
    return {
        "id": "AG-1", "topic": topic, "entry_type": "Deliverable", "status": status,
        "decision_what": f"Rejecting the deliverable due to defects" if status == "Rejected" else "成果物本文",
        "reason_why": "", "timestamp": 1.0, "is_frozen": False,
    }


@pytest.mark.parametrize("status", ["Approved", "Approved_with_Conditions", "Implicitly_Accepted"])
def test_successful_deliverable_still_gets_check_icon(status):
    text = cela_main._build_agreements_context([_deliverable(status)])
    assert "✅[成果物]" in text


def test_proposed_deliverable_still_gets_document_icon():
    text = cela_main._build_agreements_context([_deliverable("Proposed")])
    assert "📄[成果物]" in text


def test_rejected_deliverable_no_longer_shows_check_icon():
    text = cela_main._build_agreements_context([_deliverable("Rejected")])
    assert "✅[成果物]" not in text
    assert "⚠️[却下成果物]" in text


def test_rejected_deliverable_content_and_check_icon_do_not_coexist_even_with_other_rows():
    """Rejectされた成果物と、他の正常な合意事項が同時に存在しても、それぞれ正しく表示されること。"""
    agreements = [
        _deliverable("Approved", topic="task_1_1の成果物"),
        _deliverable("Rejected", topic="task_1_3 財務持続性モデル構築"),
    ]
    text = cela_main._build_agreements_context(agreements)
    lines = text.split("\n")
    approved_line = next(l for l in lines if "task_1_1の成果物" in l)
    rejected_line = next(l for l in lines if "task_1_3 財務持続性モデル構築" in l)
    assert "✅[成果物]" in approved_line
    assert "⚠️[却下成果物]" in rejected_line
