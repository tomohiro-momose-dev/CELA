"""
BL-246: User AI Stage4がExpertへ次タスクを指示する際、Expertが実際に使えるツールを一切
知らされないまま自由記述で指示文を書いており、地理データ実測ツール（gsi_geocode/
gsi_get_elevation/gsi_calc_distance_bearing/calc_road_route）が茅野市シナリオの
ある1本のrun全体（log/2026-08-16/1100〜1333、run_id=1786845632-22283a33）を通じて
一度も呼ばれていなかった問題。

ユーザーが「ユーザーAIにエキスパートが使用できるツールをまず認識させ、その上で、タスクに
応じてそれらのツールの使用の指示を明示するように」「作業中に出てきた事物についてもっと
深堀りするように」と明示的に指示。Expertは指示に従いたがる傾向があるため（ユーザー指摘）、
User AI Stage4が書く指示文自体の具体性を高める。

既存のBL-192（次タスク指示文の質を強化する共通ブロック、Stage4パス・非Stage4パス双方から
参照される）を拡張し、③Expertのツール一覧の周知と行動計画の明示、④ゴール文・既存成果物の
定性的な言及（「商業施設が複数点在」「小中学校」「冬季は冷え込む」等）を具体的な事物・数値へ
深堀りする指示、を追加した。あわせてExpert自身のプロンプトにも対になる深堀り指示（BL-246）を
追加した。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-246。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl192_block_mentions_expert_tool_awareness():
    """[BL-246本体] _BL192_DIRECTIVE_QUALITY_BLOCKが、Expertの主要ツール名を明示的に
    列挙していること（Stage4がツール名を指示文の中で名指しできるようにする）。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    for tool_name in (
        "web_search", "gsi_geocode", "calc_road_route",
        "register_entity", "write_entity_attribute", "python_repl",
    ):
        assert tool_name in text, f"{tool_name} が_BL192_DIRECTIVE_QUALITY_BLOCKに含まれていない"


def test_bl192_block_instructs_action_plan_before_instruction():
    """Stage4が指示文を書く前に、具体的な行動計画（何をどのツールで確認するか）を
    自問するよう促す文言が含まれていること。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "行動計画" in text
    assert "抽象的" in text


def test_bl192_block_instructs_deep_dive_on_qualitative_mentions():
    """ゴール文・既存成果物の定性的な言及（具体的な数・所在・数値を伴わない記述）を
    深堀りするよう促す文言と、代表的な例（商業施設・学校・気候）が含まれていること。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "定性的な言及" in text or "深堀り" in text
    assert "商業施設" in text
    assert "小中学校" in text
    assert "冷え込む" in text


def test_bl192_block_does_not_expand_acceptance_criteria_scope():
    """回帰確認: 深堀り指示を追加しても、acceptance_criteria達成に不要な要求まで
    際限なく求めないという既存の歯止め文言（BL-197と同じ考え方）が残っていること。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "acceptance_criteria達成に不要な" in text


def test_bl192_existing_points_still_present():
    """回帰確認: 既存の①②（web_search義務化・思考プロセス明示）の内容は維持されていること。"""
    text = cela_main._BL192_DIRECTIVE_QUALITY_BLOCK
    assert "web_search" in text
    assert 'type="web"' in text
    assert "もっともらしい" in text
    assert "思考プロセス" in text
    assert "task_focus_companion" in text


def test_expert_prompt_has_matching_deep_dive_instruction():
    """[BL-246] Expert自身の system prompt（call_expert）にも、対になる深堀り指示
    （BL-246）が追加されていること。Stage4側だけでなくExpert自身も、指示されなくても
    定性的な言及を深堀りする姿勢を持てるようにする。"""
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-246" in src
    assert "商業施設" in src
    assert "小中学校" in src


def test_bl192_directive_block_still_wired_into_generate_user_utterance():
    """回帰確認: 既存のBL-192配線（Stage4パス・非Stage4パス双方）が壊れていないこと。"""
    source = inspect.getsource(cela_main.generate_user_utterance)
    assert source.count("_BL192_DIRECTIVE_QUALITY_BLOCK") >= 2
