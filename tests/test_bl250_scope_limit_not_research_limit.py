"""
BL-250:「このタスクでは正式な◯◯を決定しないでください」のような、タスクの範囲を絞る
ためのdescription/acceptance_criteria文言を、Expertが「調べる必要もない」と読み違え、
一次情報の裏付けなしにその項目を単に「未確定」のまま放置して後続タスクへ丸投げする
事故が実際に観測された（茅野市自動運転バスシナリオ、log/2026-08-16/1443・1512：
task_2_2が明示的にBL-192①で車両価格等のweb_search検証を名指しされていたにもかかわらず、
`web_search`は一度も呼ばれず、「正式費用は未確定」のままGate項目として登録されて完了した）。

ユーザー指摘：「全体に"正式"という言葉に引っ張られている気がします。モデルの性質なのか、
決定する事を躊躇しています」。ただし調査の結果、cela_main.py側の固定プロンプト文言に
「正式」という単語自体は11箇所あるが、そのほとんどはtask_plannerの正式計画（登録済み
phases）と草案を区別する構造的な用語であり、決定回避とは無関係と判明した。実際に
決定回避を招いていたのは、task_planner（LLM）自身が生成したタスク記述内の「正式な◯◯を
決定しないでください」という範囲限定の言い回しである。したがって「正式」という単語の
全体置換ではなく、範囲限定を書く箇所（task_planner・User AI Stage4・Expert自身）すべてに
「決定しない≠調べない」を明示する一文を追加する、より的を絞った対処とした。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-250。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl192_block_clarifies_scope_limit_is_not_research_limit():
    """User AI Stage4が次タスク指示を書く際に参照する_BL192_DIRECTIVE_QUALITY_BLOCKに、
    「決定しない」＝「調べない」ではないという原則⑤が含まれていること。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "BL-250" in text
    assert "provisional" in text


def test_expert_prompt_clarifies_scope_limit_is_not_research_limit():
    """call_expertのソースにも、対になるBL-250の原則（範囲外と書かれていても調査自体は
    行い、provisionalで登録せよという指示）が含まれていること。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-250" in src
    assert "provisional" in src


def test_task_planner_prompt_clarifies_scope_limit_is_not_research_limit():
    """call_task_plannerのソースにも同じ原則が含まれ、範囲限定文言を書く際に
    調査許可の一文を併記させる指示があること（BL-249と同じ挿入箇所）。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-250" in src


def test_scope_limit_clarification_present_in_all_three_locations():
    """3箇所すべてに同じ原則が行き渡っていること（AGENTS.md §15.2:
    「条件を発生させ得る全ての経路を列挙し尽くす」の確認）。"""
    locations = {
        "task_planner": inspect.getsource(cela_main.call_task_planner),
        "user_ai_stage4": cela_main._BL192_DIRECTIVE_QUALITY_BLOCK,
        "expert": inspect.getsource(cela_main.call_expert),
    }
    missing = [name for name, src in locations.items() if "BL-250" not in src]
    assert not missing, f"BL-250の原則が欠落している箇所: {missing}"
