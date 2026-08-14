"""
BL-209: Orchestratorのfocus_guidance（BL-078）に要求水準の上限が無く、タスクの
acceptance_criteriaを超える新規の作業要求を毎ラウンド積み増してしまう問題の是正。

`log/2026-08-11/0016`のtask_2_3で、Detector自身が受入基準3項目すべてを
criteria_status=[true, true, true]で充足済みと判定した後も、Orchestratorのfocus_guidanceが
「時間帯別に接続し」「複数シナリオで算定すること」「冬季は…再現可能にし」といった、
受入基準に一切書かれていない新規の成果物・分析・モデルを要求し続け、タスクが完了しない
空転が続いた。

BL-196（task_planner）・BL-197（User AI Stage3/4）で同種の「要求水準の青天井」は既に
塞いでいたが、Orchestratorのfocus_guidanceだけが素通しのまま残っていた（BL-078導入時に
このガードレールの観点が存在しなかったため）。

対応：call_orchestratorのプロンプトへ、focus_guidanceはacceptance_criteriaを達成しやすく
するための着眼点であり新しい要求項目を追加する場所ではない旨のガードレールを追加した。

参照: docs/design/back_log/issue_backlog.md BL-209、BL-196、BL-197、BL-078。
実LLM API呼び出しは伴わない（プロンプト文言のソース検証のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _orchestrator_src() -> str:
    return inspect.getsource(cela_main.call_orchestrator)


def test_orchestrator_has_bl209_guardrail():
    src = _orchestrator_src()
    assert "BL-209" in src, "call_orchestratorにBL-209のガードレールがありません"


def test_guardrail_names_acceptance_criteria_as_the_ceiling():
    """[BL-209] 「acceptance_criteriaを超えない」という上限そのものを明示していること。"""
    src = _orchestrator_src()
    idx = src.index("BL-209")
    block = src[idx:idx + 900]
    assert "acceptance_criteria" in block
    assert "超えない" in block or "超える" in block


def test_guardrail_forbids_adding_new_requirements():
    """[BL-209] 「新しい要求項目を追加する場所ではない」という禁止を明記していること。
    単に「簡潔に書け」といった強さの調整では、受入基準外の要求の積み増しは止まらない。"""
    src = _orchestrator_src()
    idx = src.index("BL-209")
    block = src[idx:idx + 900]
    assert "新しい要求項目" in block or "新規の作業指示" in block


def test_guardrail_is_placed_with_the_bl078_focus_guidance_instruction():
    """[BL-209] ガードレールはfocus_guidanceを指示しているBL-078ブロックの直後に置く
    （離れた位置に置くと、focus_guidanceを書く時点で参照されない恐れがあるため）。
    あわせて、BL-104/BL-114のプロンプトキャッシュ方針（固定指示文を先頭・動的内容を末尾）
    を壊していないこと＝動的ブロック（goal_context等）より前にあることも確認する。"""
    src = _orchestrator_src()
    bl078_idx = src.index("[BL-078]")
    bl209_idx = src.index("[BL-209")
    dynamic_idx = src.index("{goal_context}")
    assert bl078_idx < bl209_idx < dynamic_idx


def test_guardrail_cites_the_observed_failure_for_traceability():
    """[BL-209] 実ログの根拠を残す（本プロジェクトの「Why を書く」規律、AGENTS.md §6）。"""
    src = _orchestrator_src()
    idx = src.index("BL-209")
    block = src[idx:idx + 900]
    assert "0016" in block


def test_bl078_focus_guidance_instruction_itself_is_preserved():
    """[BL-209] ガードレール追加でBL-078本来の意図（着眼点を1〜3点出力させる）を
    壊していないことを確認する。"""
    src = _orchestrator_src()
    assert "focus_guidance" in src
    assert "1〜3点" in src
    assert '"focus_guidance"' in src  # 返却JSONスキーマ
