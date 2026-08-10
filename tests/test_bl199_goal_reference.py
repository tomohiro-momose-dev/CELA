"""
BL-199: read_goal_reference（web_tools.py）の単体テストと、cela_main.pyへの配線確認。

背景: log/2026-08-09/2222で、Expertがdocs/refs/chino_city/chino_city_data.mdに既に
キャッシュ済みの施設住所・座標をweb_searchで再検索し、run単位の呼び出し上限（30回）を
使い果たしていたことが判明した。read_reference_fileはweb_cache/<run_id>/専用で
docs/refs/を読めないため、既存ツールでは代替できなかった。

参照: docs/design/back_log/issue_backlog.md BL-199、BL-184（read_reference_fileの先例）、
BL-198（geo_tools.pyの配線確認パターン）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402
import web_tools  # noqa: E402


# ---------------------------------------------------------------------------
# 1. read_goal_reference_handler
# ---------------------------------------------------------------------------

def test_read_goal_reference_not_configured_when_dir_missing_from_state():
    result = web_tools.read_goal_reference_handler({"keyword": "茅野駅"}, {})
    assert result["status"] == "not_configured"


def test_read_goal_reference_not_found_when_dir_does_not_exist(tmp_path):
    state = {"goal_reference_dir": str(tmp_path / "does_not_exist")}
    result = web_tools.read_goal_reference_handler({"keyword": "茅野駅"}, state)
    assert result["status"] == "not_found"


def test_read_goal_reference_by_path_success(tmp_path):
    (tmp_path / "data.md").write_text("茅野駅の標高は789mです。", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"path": "data.md"}, state)
    assert "789m" in result


def test_read_goal_reference_path_traversal_rejected(tmp_path):
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"path": "../../etc/passwd"}, state)
    assert result["status"] == "error"


def test_read_goal_reference_by_keyword_single_match(tmp_path):
    (tmp_path / "data.md").write_text("茅野駅: 緯度35.994124 経度138.152337", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"keyword": "茅野駅"}, state)
    assert "35.994124" in result


def test_read_goal_reference_by_keyword_multiple_matches(tmp_path):
    (tmp_path / "a.md").write_text("茅野駅の情報A", encoding="utf-8")
    (tmp_path / "b.md").write_text("茅野駅の情報B", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"keyword": "茅野駅"}, state)
    assert result["status"] == "multiple_matches"
    assert len(result["candidates"]) == 2


def test_read_goal_reference_by_keyword_searches_subdirectories(tmp_path):
    """[BL-199] docs/refsは<goal>/<sub>.mdのようにサブディレクトリを持ち得るため、
    rglobで再帰的に検索する（read_reference_fileのglobは1階層のみで足りるのと異なる）。"""
    sub = tmp_path / "sub"
    sub.mkdir()
    (sub / "nested.md").write_text("蓼科湖の標高は約1250mです。", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"keyword": "蓼科湖"}, state)
    assert "1250m" in result


def test_read_goal_reference_not_found_on_no_keyword_match(tmp_path):
    (tmp_path / "data.md").write_text("無関係な内容", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({"keyword": "存在しない語"}, state)
    assert result["status"] == "not_found"
    assert "web_search" in result["message"]


def test_read_goal_reference_no_args_returns_error(tmp_path):
    state = {"goal_reference_dir": str(tmp_path)}
    result = web_tools.read_goal_reference_handler({}, state)
    assert result["status"] == "error"


def test_read_goal_reference_does_not_consume_web_search_budget(tmp_path):
    """[BL-199] web_search/web_fetchと異なり、call_countを一切インクリメントしない
    （run_scoped call limitの対象外であることのAPI契約確認）。"""
    (tmp_path / "data.md").write_text("茅野駅の標高は789mです。", encoding="utf-8")
    state = {"goal_reference_dir": str(tmp_path), "web_search_call_count": 0}
    web_tools.read_goal_reference_handler({"keyword": "茅野駅"}, state)
    assert state["web_search_call_count"] == 0


# ---------------------------------------------------------------------------
# 2. cela_main.pyへの配線確認
# ---------------------------------------------------------------------------

def test_read_goal_reference_registered_in_tool_dispatch():
    assert "read_goal_reference" in cela_main.TOOL_DISPATCH


def test_read_goal_reference_attached_to_call_expert():
    src = inspect.getsource(cela_main.call_expert)
    assert "READ_GOAL_REFERENCE_TOOL" in src


def test_read_goal_reference_attached_to_call_detector_both_passes():
    """[BL-199] Detectorはドメイン妥当性（Pass1）・数値監査（Pass2）の2パス構成であり、
    どちらのツール一覧にも載っている必要がある（BL-198と同型の配線確認）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("READ_GOAL_REFERENCE_TOOL") >= 2


def test_call_expert_guidance_tells_to_check_goal_reference_before_web_search():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-199" in src
    assert "read_goal_reference" in src


def test_call_detector_guidance_mentions_bl199():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-199") >= 2


def test_goal_reference_dir_wired_into_state_and_config():
    src = inspect.getsource(cela_main)
    assert "goal_reference_dir" in src


def test_max_web_search_calls_relaxed_beyond_original_30():
    """[BL-199] ユーザー承認（AGENTS.md §7）により30から緩和。log/2026-08-09/2222で
    read_goal_reference未導入時に30回で枯渇したことへの安全弁。
    具体値はドライランの実績に応じてユーザーが調整するため（50→100等）、
    特定の数値ではなく「元の30より緩和されている」ことだけを固定する。"""
    import re
    src = inspect.getsource(cela_main)
    m = re.search(r'"max_web_search_calls":\s*(\d+),', src.rsplit("config : Appconfig", 1)[-1])
    assert m, "実行時configにmax_web_search_callsが見つかりません"
    assert int(m.group(1)) > 30


# ---------------------------------------------------------------------------
# 3. BL-200: 3段階の参照優先順位（refs → web_cache → web_search）がプロンプトに
#    明記されていること。web_cache自体がrunをまたいで永続化されたことは
#    test_bl184_web_tools.pyのtest_cache_file_path_is_shared_across_runs等で検証済み。
# ---------------------------------------------------------------------------

def test_call_expert_guidance_states_three_step_lookup_order():
    src = inspect.getsource(cela_main.call_expert)
    assert "BL-199/BL-200" in src
    assert "①read_goal_reference" in src
    assert "②read_reference_file" in src
    assert "③web_search" in src


def test_call_detector_guidance_states_three_step_lookup_order_both_passes():
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("BL-199/BL-200") >= 2
    assert src.count("①read_goal_reference") >= 2


def test_read_goal_reference_tool_description_states_lookup_order():
    assert "BL-199/BL-200" in cela_main.READ_GOAL_REFERENCE_TOOL["function"]["description"]
