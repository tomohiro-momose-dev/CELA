"""
BL-255: 実ドライラン（log/2026-08-16/2020、run_id=1786879248-754a2c00）で、User AI (Stage4)が
task_2_2承認直後にphase_3・phase_4を丸ごと飛ばしてtask_5_2→task_5_3→task_5_1へ進んだ。
task_5_1への指示文自体が「task_2_1、task_3_1、task_4_1の前提を引き継ぎ」と書きながら、
task_3_1・task_4_1は一度も実行されていなかった（write_agreement, entry_type=Deliverableの
全件を機械抽出して確認）。

ユーザーの指摘「ユーザーAIはプロンプトでタスク表を入れていますが、一番上なので、その後の
コンテキストに押し流されてしまっているかもしれません」を受けて調査した結果、原因は2つ：

1. stage4_system_prompt（実際のStage4呼び出しに使われる、system_prompt_leading/trailingとは
   別の独立したプロンプト）は、冒頭近くに巨大なphases_json（全フェーズ・全タスク）を埋め込み、
   その直後に_BL192_DIRECTIVE_QUALITY_BLOCK等の大量のテキストが積み上がる構成で、
   chat_historyより前に固定される。BL-178/BL-185が確立した「最重要情報はchat_historyより
   後ろ（プロンプト全体で最後）に置く」という設計原則がStage4のこの経路には適用されておらず、
   依存関係の判断材料が実質的に埋もれていた。
2. _resolve_task_transition（タスク遷移の唯一の書き手、BL-024）は、離脱元タスクの状態
   （BL-125: 未解決issue、BL-176: 未承認）しか検証しておらず、「これから進む先」の
   depends_onが実際に完了しているかは一度も検証していなかった。

対応（ユーザー承認、2件とも実装）:
1. _build_next_task_candidates_text: depends_onが全て完了している未着手タスクをPython側で
   確定的に算出し、chat_historyより後ろ（stage4_messagesの最後）に独立したsystemメッセージ
   として追加する。
2. _resolve_task_transition: 遷移先task_idのdepends_onが未完了の場合、BL-125/BL-176と同型の
   機械的ゲートで遷移をブロックする（task_transition_blocked_unmet_deps_task_id／
   task_transition_blocked_unmet_deps、_build_task_transition_blocked_noticeでの通知、
   route_after_user_decisionでのgenerate_user_utteranceへの差し戻しも含め、既存の
   BL-125/BL-176/BL-181/BL-183パターンを完全に踏襲）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-255。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl255.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""


def _mark_task_completed(run_id, phase_id, task_id):
    """テスト用: 指定task_idのDeliverableをApproved相当のstatusで記録する。"""
    cela_main._CURRENT_CALLER_ROLE = "expert"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Deliverable",
            "topic": f"{task_id} 成果物", "decision_what": f"{task_id}の成果物本文（十分な長さのテキストです。"
            "テスト用のダミー成果物ですが、ホワイトボード保護仕様に引っかからないよう200字を"
            "超える長さにしています。これでdecision_whatが短すぎることによる保護は発動しません。",
            "reason_why": "テスト用",
            "phase_id": phase_id, "task_id": task_id,
        },
        {"run_id": run_id, "phases": _PHASES, "current_task_id": task_id,
         "current_phase": {"phase_id": phase_id}},
    )
    assert result["success"] is True
    cela_main._CURRENT_CALLER_ROLE = "user"
    approve_result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "UPDATE", "status": "Approved", "entry_type": "Deliverable",
            "target_topic": f"{task_id} 成果物",
            "topic": f"{task_id} 成果物", "decision_what": "承認", "reason_why": "承認",
            "phase_id": phase_id, "task_id": task_id,
        },
        {"run_id": run_id, "phases": _PHASES, "current_task_id": task_id,
         "current_phase": {"phase_id": phase_id}},
    )
    assert approve_result["success"] is True


_PHASES = [
    {
        "phase_id": "phase_1",
        "tasks": [{"task_id": "task_1_1", "title": "前提整理", "depends_on": []}],
    },
    {
        "phase_id": "phase_2",
        "tasks": [{"task_id": "task_2_1", "title": "需要調査", "depends_on": ["task_1_1"]}],
    },
    {
        "phase_id": "phase_3",
        "tasks": [{"task_id": "task_3_1", "title": "経路調査", "depends_on": ["task_1_1"]}],
    },
    {
        "phase_id": "phase_5",
        "tasks": [
            {"task_id": "task_5_1", "title": "運行設計", "depends_on": ["task_2_1", "task_3_1"]},
            {"task_id": "task_5_2", "title": "運賃積算", "depends_on": ["task_2_1"]},
        ],
    },
]


def test_candidates_excludes_task_with_unmet_dependency(db_conn):
    """task_1_1のみ完了、task_2_1/task_3_1は未完了の状態では、それらに依存する
    task_5_1・task_5_2は候補に出ず、task_2_1・task_3_1自身（依存はtask_1_1のみで完了済み）
    だけが候補になること。"""
    conn, run_id = db_conn
    _mark_task_completed(run_id, "phase_1", "task_1_1")
    text = cela_main._build_next_task_candidates_text(conn, run_id, _PHASES)
    assert "task_2_1" in text
    assert "task_3_1" in text
    assert "task_5_1" not in text
    assert "task_5_2" not in text


def test_candidates_includes_task_once_all_dependencies_completed(db_conn):
    """task_1_1・task_2_1・task_3_1が完了すれば、task_5_1が候補に出ること
    （実ドライランで欠けていた検証そのもの）。"""
    conn, run_id = db_conn
    _mark_task_completed(run_id, "phase_1", "task_1_1")
    _mark_task_completed(run_id, "phase_2", "task_2_1")
    _mark_task_completed(run_id, "phase_3", "task_3_1")
    text = cela_main._build_next_task_candidates_text(conn, run_id, _PHASES)
    assert "task_5_1" in text
    assert "task_5_2" in text


def test_candidates_empty_message_when_nothing_ready(db_conn):
    conn, run_id = db_conn
    text = cela_main._build_next_task_candidates_text(conn, run_id, [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1", "title": "x", "depends_on": ["task_0_9"]}]}
    ])
    assert "ありません" in text


def test_resolve_task_transition_blocks_when_dependency_unmet(db_conn):
    """task_3_1が未完了のままtask_5_1へ遷移しようとすると、current_task_idが更新されず、
    ブロックフラグがセットされること（実ドライランで実際に起きた事故そのものの再現）。"""
    conn, run_id = db_conn
    _mark_task_completed(run_id, "phase_1", "task_1_1")
    _mark_task_completed(run_id, "phase_2", "task_2_1")
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_2_1",
        "current_phase": _PHASES[1],
        "task_transition_blocked_unmet_deps_task_id": "", "task_transition_blocked_unmet_deps": [],
    }
    cela_main._resolve_task_transition(state, {"advances_to_phase_id": "phase_5", "advances_to_task_id": "task_5_1"})
    assert state["current_task_id"] == "task_2_1"  # 更新されていない
    assert state["task_transition_blocked_unmet_deps_task_id"] == "task_5_1"
    assert "task_3_1" in state["task_transition_blocked_unmet_deps"]


def test_resolve_task_transition_allows_when_all_dependencies_met(db_conn):
    conn, run_id = db_conn
    _mark_task_completed(run_id, "phase_1", "task_1_1")
    _mark_task_completed(run_id, "phase_2", "task_2_1")
    _mark_task_completed(run_id, "phase_3", "task_3_1")
    state = {
        "run_id": run_id, "phases": _PHASES, "current_task_id": "task_3_1",
        "current_phase": _PHASES[2],
        "task_transition_blocked_unmet_deps_task_id": "", "task_transition_blocked_unmet_deps": [],
    }
    cela_main._resolve_task_transition(state, {"advances_to_phase_id": "phase_5", "advances_to_task_id": "task_5_1"})
    assert state["current_task_id"] == "task_5_1"
    assert state["task_transition_blocked_unmet_deps_task_id"] == ""


def test_blocked_notice_is_one_shot_and_mentions_unmet_deps():
    state = {
        "task_transition_blocked_unmet_deps_task_id": "task_5_1",
        "task_transition_blocked_unmet_deps": ["task_3_1", "task_4_1"],
    }
    notice = cela_main._build_task_transition_blocked_notice(state)
    assert "task_5_1" in notice
    assert "task_3_1" in notice
    assert "task_4_1" in notice
    assert "BL-255" in notice
    # one-shot: 消費後はフラグがクリアされる
    assert state["task_transition_blocked_unmet_deps_task_id"] == ""
    assert state["task_transition_blocked_unmet_deps"] == []
    assert cela_main._build_task_transition_blocked_notice(state) == ""


def test_route_after_user_decision_source_checks_unmet_deps_flag():
    """route_after_user_decisionのBL-181機械的差し戻しが、新しいブロック要因
    （task_transition_blocked_unmet_deps_task_id）も条件に含んでいること。"""
    src = inspect.getsource(cela_main)
    assert "task_transition_blocked_unmet_deps_task_id" in src
    idx = src.index("[BL-181]")
    nearby = src[idx: idx + 1200]
    assert "task_transition_blocked_unmet_deps_task_id" in nearby


def test_stage4_candidates_text_appended_after_chat_history():
    """[BL-255] stage4_messagesの構築順序で、_build_next_task_candidates_textの呼び出しが
    chat_historyのfor-appendループより後ろにあること（プロンプト全体で最後＝BL-178/BL-185と
    同型のrecency配置になっているかのソースレベル確認）。"""
    src = inspect.getsource(cela_main.generate_user_utterance)
    chat_history_loop_idx = src.index('stage4_messages.append({"role": _role, "content": msg["content"]})')
    candidates_call_idx = src.index("_build_next_task_candidates_text(")
    assert candidates_call_idx > chat_history_loop_idx


def test_stage4_candidates_appended_as_separate_system_message():
    src = inspect.getsource(cela_main.generate_user_utterance)
    idx = src.index("_build_next_task_candidates_text(")
    nearby = src[idx: idx + 300]
    assert 'stage4_messages.append({"role": "system"' in nearby
