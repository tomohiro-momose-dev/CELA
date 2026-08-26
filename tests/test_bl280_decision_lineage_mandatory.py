"""
BL-280: entry_type="Decision"の使い分け基準がツールスキーマにもプロンプトにも定義されておらず、
Decisionが実質使われていなかった問題（全agreementsの23%を占めるが「A案でなくB案を選んだ理由」
という粒度の記述は実質ゼロ件）。BL-277（複数候補からの絞り込み記録の強制化）の根本原因として
特定された。

対応:
1. `WRITE_AGREEMENT_TOOL`の`entry_type`/`reason_why`descriptionを具体化（BL-277）。
2. 共有ヘルパー`_build_decision_lineage_directive`を新設し、「誰かの発言・判断で以降の動作が
   分岐する場合は必ずwrite_agreement(entry_type="Decision")で記録する」という指示を、全12ノード
   （call_expert, call_task_planner, call_goal_essence_analyst, call_task_plan_reviewer,
   call_detector[2段], call_reviewer, call_resource_arbiter, call_integrator, call_facilitator,
   generate_user_utterance, call_orchestrator, call_reflection）へ単一の真実源として配線した
   （AGENTS.md §15.1）。
3. 監査系ロール（Detector/Reviewer/Arbiter/Integrator/task_plan_reviewer/Reflection）が「問題なし
   と判断した」という肯定的所見を記録できるよう、新status値"Reviewed"を追加した（承認Approved系は
   引き続きUser AI専用、既存の権限分離は維持）。
4. 従来write_agreementを意図的に持たなかったOrchestrator（BL-148設計）・Reflectionへも、
   意思決定系譜の記録用にWRITE_AGREEMENT_TOOLとALLOWED_STATUS_BY_ROLEのエントリを追加した。
   Reflectionは`_CURRENT_CALLER_ROLE`を明示的に設定していなかったバグ（BL-096と同型）も修正した。
5. `decisions`テーブル（`make_decision`/`db_append_decision`、Python側が無条件に記録する床）は
   置き換えず維持する。agreements(entry_type="Decision")はその上に重ねるAIが能動的に書く濃い層。

`call_decision_extractor`（tools=None、単発JSON抽出でツールループ自体を持たない）は対象外
（構造的な違いがあり、対応するにはツールループへの変更が必要なため本改修の範囲外）。

参照: docs/design/back_log/issue_backlog.md BL-277, BL-278, BL-279, BL-280。
実LLM API呼び出しは伴わない。
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
    db_path = str(tmp_path / "test_bl280.db")
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


# ---------------------------------------------------------------------------
# 1. 共有ディレクティブヘルパー
# ---------------------------------------------------------------------------

def test_build_decision_lineage_directive_uses_mandatory_language():
    """[BL-280] 「望ましい」ではなく「必ず」という必須の言い回しであること
    （BL-095との対比——原則を書くだけでは実行されない、という調査結果を踏まえた要求）。"""
    text = cela_main._build_decision_lineage_directive('"Proposed"')
    assert "必ず" in text
    assert "望ましい" not in text
    assert 'write_agreement(entry_type="Decision"' in text


def test_build_decision_lineage_directive_embeds_status_hint():
    text = cela_main._build_decision_lineage_directive('"Rejected"または"Reviewed"')
    assert '"Rejected"または"Reviewed"' in text


# ---------------------------------------------------------------------------
# 2. 全12ノードへの配線確認（ソース検査）
# ---------------------------------------------------------------------------

_TARGET_NODES = [
    "call_expert", "call_task_planner", "call_goal_essence_analyst",
    "call_task_plan_reviewer", "call_detector", "call_reviewer",
    "call_resource_arbiter", "call_integrator", "call_facilitator",
    "generate_user_utterance", "call_orchestrator", "call_reflection",
]


@pytest.mark.parametrize("func_name", _TARGET_NODES)
def test_node_wires_decision_lineage_directive(func_name):
    """[BL-280] 対象12ノードそれぞれのソースに、共有ヘルパー呼び出しが存在すること。
    単一箇所（_build_decision_lineage_directive自体）を全ノードが呼ぶことで、
    文言のドリフト（AGENTS.md §15.1）を防ぐ設計になっている。"""
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "_build_decision_lineage_directive" in src, (
        f"{func_name}は_build_decision_lineage_directiveを呼んでいません"
    )


def test_call_detector_wires_directive_in_both_passes():
    """[BL-280] call_detectorはドメイン妥当性レビュー・数値監査の2段構成であり、
    片方だけだと監査経路により素通りする（BL-204の既存テストと同型の懸念）。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("_build_decision_lineage_directive") >= 2


def test_call_facilitator_wires_directive_in_both_branches():
    """[BL-280] call_facilitatorは本質対話中/通常時の2分岐があり、両方に配線されていること。"""
    src = inspect.getsource(cela_main.call_facilitator)
    assert src.count("_build_decision_lineage_directive") >= 2


# ---------------------------------------------------------------------------
# 3. 新status値"Reviewed"の配線確認
# ---------------------------------------------------------------------------

def test_reviewed_status_in_schema_enum():
    enum = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["status"]["enum"]
    assert "Reviewed" in enum


def test_reviewed_status_in_valid_statuses_source():
    """[BL-280] `_write_agreement_impl`内のvalid_statusesにも"Reviewed"が含まれること
    （ツールスキーマのenumと実装側のバリデーション集合は独立しており、両方の更新が必要）。"""
    src = inspect.getsource(cela_main._write_agreement_impl)
    assert '"Reviewed"' in src


# ---------------------------------------------------------------------------
# 4. ALLOWED_STATUS_BY_ROLE / 機能テスト（TOOL_DISPATCH経由のend-to-end）
# ---------------------------------------------------------------------------

def test_orchestrator_can_write_proposed_decision(db_conn):
    """[BL-280] Orchestratorは新たにwrite_agreement(status="Proposed")が使えること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "orchestrator"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "topic": "expert_selection_rationale",
            "decision_what": "専門家Xを選定", "reason_why": "Yという理由でZより適任と判断",
            "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


def test_orchestrator_cannot_write_rejected(db_conn):
    """[BL-280] OrchestratorにRejectedは許可されていない（ALLOWED_STATUS_BY_ROLE["orchestrator"]
    ={"Proposed"}のみ、§17.1: この行を削除・拡張すると本テストが失敗することを個別に確認済み）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "orchestrator"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Rejected", "topic": "x",
            "decision_what": "x", "reason_why": "x", "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is False


def test_detector_can_write_reviewed_status(db_conn):
    """[BL-280] Detectorは新設のstatus="Reviewed"で「問題なしと判断した」所見を記録できる
    （変更前はRejected限定で、この呼び出しは常に拒否されていた）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Reviewed", "topic": "domain_review_finding",
            "decision_what": "商業施設3件の選定は妥当と判断", "reason_why": "受益者ニーズに照らし十分",
            "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


def test_reflection_can_write_reviewed_status(db_conn):
    """[BL-280] Reflectionはdetector等と同じ監査ロールとして扱う（ユーザー指示）。
    従来はALLOWED_STATUS_BY_ROLEにキー自体が無く、write_agreement自体も持たなかった。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "reflection"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Reviewed", "topic": "stagnation_check",
            "decision_what": "議論は継続中と判断", "reason_why": "未解決の矛盾なし",
            "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


def test_reflection_can_write_rejected_status(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "reflection"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Rejected", "topic": "stagnation_check_2",
            "decision_what": "x", "reason_why": "未解決のissueが残存",
            "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


def test_reflection_cannot_write_approved_status(db_conn):
    """[BL-280] Reflectionに承認（Approved系）権限は与えない——最終承認はUser AI専用という
    既存の権限分離方針（3269行のコメント）を維持する。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "reflection"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Approved", "topic": "x",
            "decision_what": "x", "reason_why": "x", "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is False


def test_user_still_unaffected_by_reviewed_addition(db_conn):
    """[BL-280] Userロールの許可集合（全status）は変更していないことの回帰確認。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Approved", "topic": "x",
            "decision_what": "x", "reason_why": "x", "entry_type": "Decision",
        },
        {"run_id": run_id},
    )
    assert result["success"] is True


# ---------------------------------------------------------------------------
# 5. Reflectionのcaller_role明示設定（BL-096と同型のバグ修正）
# ---------------------------------------------------------------------------

def test_call_reflection_sets_caller_role_explicitly():
    """[BL-280] `_CURRENT_CALLER_ROLE`を明示的に設定していないと、write_agreementの権限
    チェックが直前ノードのroleに基づいてしまう（BL-096コメント参照、detectorで過去に実際に
    発生した事故と同型）。"""
    src = inspect.getsource(cela_main.call_reflection)
    assert '_CURRENT_CALLER_ROLE = "reflection"' in src


def test_call_reflection_has_write_agreement_tool():
    src = inspect.getsource(cela_main.call_reflection)
    assert "WRITE_AGREEMENT_TOOL" in src


# ---------------------------------------------------------------------------
# 6. call_decision_extractorは対象外（構造的な違いによる明示的な除外の確認）
# ---------------------------------------------------------------------------

def test_call_decision_extractor_not_wired():
    """[BL-280] tools=Noneの単発JSON抽出でツールループ自体を持たないため対象外。
    誤って配線されていないことのみ確認する（将来ツールループ化された場合はこのテストを
    更新し、対象に含めること）。"""
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert "_build_decision_lineage_directive" not in src
    assert "tools=None" in src or "tools = None" in src
