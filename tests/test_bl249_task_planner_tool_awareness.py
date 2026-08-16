"""
BL-249: task_planner（call_task_planner）のプロンプトに列挙されているツール一覧は
task_planner自身が使えるツール（python_repl・web_search等）のみで、task_plannerが
分解した各タスクを実際に実行するExpertが使える下流ツール（GIS一式・register_entity・
write_agreement等）には一切触れていなかった。

このため、task_plannerはacceptance_criteria/descriptionを書く際、Expertが実際に何を
具体的に調べられるかを踏まえられず、「web_searchで相場を調べよ」「GISツールで実距離を
算出せよ」といった具体的な作業をタスクへ書き込めなかった（AGENTS.md §15.4「入口はあるが
出口がない」と同型のパターン）。

既存の共有定数_EXPERT_TOOL_AWARENESS_BLOCK（BL-246でUser AI Stage4向けに導入済み）を
そのままcall_task_plannerのプロンプトにも挿入し、Expertの下流ツールを周知した上で、
ゴール文に無い事物・数値もweb検索等で調べられる旨を明示する。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-249。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_task_planner_prompt_mentions_expert_downstream_tools():
    """call_task_plannerのソースが、Expertの下流ツール一覧（_EXPERT_TOOL_AWARENESS_BLOCK）
    を実際に埋め込んでいること。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "_EXPERT_TOOL_AWARENESS_BLOCK" in src, (
        "call_task_plannerのプロンプトがExpertの下流ツール一覧を参照していない"
    )


def test_expert_tool_awareness_block_lists_key_tools():
    """共有ブロック自体が、GIS・エンティティ登録・web検索など主要な下流ツールを
    実際に列挙していること（BL-246で導入済みだが、依存関係の健全性として再確認）。"""
    text = cela_main._EXPERT_TOOL_AWARENESS_BLOCK
    for tool_name in ("web_search", "gsi_geocode", "register_entity", "write_agreement"):
        assert tool_name in text, f"{tool_name} が_EXPERT_TOOL_AWARENESS_BLOCKに含まれていない"


def test_task_planner_prompt_instructs_concrete_investigation_means():
    """BL-249の指示文が、「ゴール文に無い事物・数値でも調べられる」「acceptance_criteria/
    descriptionに具体的な調査手段を書け」という趣旨を含むこと。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-249" in src
    assert "ゴール文に書かれて" in src and "確定できない" in src


def test_task_planner_prompt_instructs_provisional_registration_on_scope_limit():
    """BL-250（範囲限定文言の併記ルール）がcall_task_planner側にも波及しており、
    「決定しない」旨の指示には暫定調査・提案を許可する一文を併記させる指示が
    含まれていること。"""
    src = inspect.getsource(cela_main.call_task_planner)
    assert "BL-250" in src
    assert "provisional" in src
