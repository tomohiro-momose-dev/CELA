"""
BL-183: BL-181で実装した`route_after_user_decision`の機械的ガード（第2段防御）は、
`_resolve_task_transition`が立てる2種類のブロックフラグのうち
`task_transition_blocked_unapproved_task_id`（BL-176: 離脱先未承認ブロック）しか
チェックしておらず、BL-125本来の`task_transition_blocked_issue_topics`
（離脱先に未解決・未先送りのsevere issueが残っているブロック）を見落としていた。

このためBL-125が実際にブロックを発火させたにもかかわらず（`log/2026-08-06/0009`の
"🛑 [BL-125] 'task_5_2'に未解決・未先送りのsevere issueが1件存在するため、
'task_6_1'への遷移をブロックしました"）、route_after_user_decisionはこのフラグを
知らずにorchestratorへ進んでしまい、再開後（`log/2026-08-06/0751`）にOrchestrator/Expert
が独自にtask_6_1が現在タスクだと判断して作業を進めた結果、write_agreementの
task_id不一致ゲートに阻まれたExpertがtask_id='task_5_2'のままtask_6_1の内容を
誤登録した（BL-181と同型の事故の再発）。

対策: route_after_user_decisionの条件を`task_transition_blocked_unapproved_task_id`と
`task_transition_blocked_issue_topics`のORに拡張する。

参照: docs/design/back_log/issue_backlog.md BL-183、docs/design/decision_log.md D-152。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _route_after_user_decision_body() -> str:
    src = inspect.getsource(cela_main.build_graph)
    start = src.index("def route_after_user_decision(state: LineageState):")
    end = src.index("graph.add_conditional_edges(\n        \"user_decision_extractor\"", start)
    return src[start:end]


def test_route_after_user_decision_checks_both_block_flags():
    body = _route_after_user_decision_body()
    assert "task_transition_blocked_unapproved_task_id" in body
    assert "task_transition_blocked_issue_topics" in body


def test_route_after_user_decision_checks_severe_issue_flag_before_ready_for_review():
    body = _route_after_user_decision_body()
    block_idx = body.index("task_transition_blocked_issue_topics")
    ready_idx = body.index('"ready_for_review"')
    assert block_idx < ready_idx


def _extract_route_after_user_decision():
    """build_graph()内のネスト関数route_after_user_decisionを、グラフ構築を実行して
    実際に取り出す（closureをexecして呼び出し可能にする）。"""
    src = inspect.getsource(cela_main.build_graph)
    start = src.index("def route_after_user_decision(state: LineageState):")
    end = src.index("graph.add_conditional_edges(\n        \"user_decision_extractor\"", start)
    func_src = src[start:end]
    # インデントを除去してモジュールトップレベル関数として実行する
    lines = func_src.splitlines()
    dedented = "\n".join(line[4:] if line.startswith("    ") else line for line in lines)
    # [BL-236拡張] route_after_user_decisionはモジュールレベル関数_should_pause_for_humanも
    # 参照するようになったため、孤立実行用の名前空間へも注入する（LineageStateと同じ理由）。
    namespace: dict = {
        "LineageState": cela_main.LineageState,
        "_should_pause_for_human": cela_main._should_pause_for_human,
    }
    exec(compile(dedented, "<route_after_user_decision>", "exec"), namespace)
    return namespace["route_after_user_decision"]


def test_severe_issue_block_flag_routes_to_generate_user_utterance():
    route_after_user_decision = _extract_route_after_user_decision()
    state = {
        "halt": False,
        "task_transition_blocked_unapproved_task_id": "",
        "task_transition_blocked_issue_topics": ["task_5_3_分類数矛盾"],
        "ready_for_review": False,
    }
    assert route_after_user_decision(state) == "generate_user_utterance"


def test_no_block_flags_routes_to_orchestrator_as_before():
    route_after_user_decision = _extract_route_after_user_decision()
    state = {
        "halt": False,
        "task_transition_blocked_unapproved_task_id": "",
        "task_transition_blocked_issue_topics": [],
        "ready_for_review": False,
    }
    assert route_after_user_decision(state) == "orchestrator"
