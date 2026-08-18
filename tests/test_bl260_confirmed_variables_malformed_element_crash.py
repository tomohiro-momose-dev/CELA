"""
BL-260: 実ドライラン中に、task_plannerのwrite_agreement呼び出しがクラッシュしプロセス全体が
停止した。

トレースバック:
    File "cela_main.py", line 3782, in _write_agreement_impl
        var_name = cv.get("variable_name")
    AttributeError: 'str' object has no attribute 'get'

`confirmed_variables`はツールschema上`{variable_name, value, ...}`のオブジェクト配列を
要求するが（`WRITE_AGREEMENT_TOOL`の`confirmed_variables.items.type == "object"`）、LLMが
スキーマに反して文字列の配列（例: `["mountain_required_vehicle_count"]`）を返すことがあり、
`_write_agreement_impl`はその要素を無条件に`.get("variable_name")`していたため、
`AttributeError`がキャッチされずLangGraphのノード実行を貫通し、run_ai_vs_ai_loop全体が
未処理例外で終了した。

これはAGENTS.md §13（LLM出力は空文字だけでなく、スキーマに反した型・形状でも返り得る）が
想定する典型的な防御漏れだが、これまでのBL-258/259はverified_factsへ「間違った値」が
書き込まれる/書き込まれない問題であり、本件は初めて**プロセス全体のクラッシュ**という
より重大な帰結だった点で異なる。

修正: `_write_agreement_impl`の`confirmed_variables`ループ、および`_query_AI_live`の
write_agreement成功トラッキング（BL-259 W2で追加したconfirmed_variable_names収集）の
両方に`isinstance(cv, dict)`チェックを追加し、非dict要素は個別にスキップしてwarningへ
蓄積する（既存のderived_from無効ref・protected_warningと同じ「呼び出し自体は成功のまま
warningで次ターンへ促す」パターンを踏襲）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-260。
"""

import inspect
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_PHASES = [
    {
        "phase_id": "phase_1",
        "tasks": [
            {"task_id": "task_1_1", "title": "テストタスク", "depends_on": [],
             "owns_variables": ["mountain_required_vehicle_count"]},
        ],
    },
]


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl260.db")
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


def test_write_agreement_does_not_crash_on_string_confirmed_variables_element(db_conn):
    """実インシデントの再現: confirmed_variablesの要素が文字列（オブジェクトでない）でも
    AttributeErrorを送出せず、成功レスポンスを返すこと。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "task_planner"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Decision",
            "topic": "task_planner_phase_design",
            "decision_what": "テスト用の計画再構成決定。",
            "reason_why": "テスト用",
            "phase_id": "phase_1", "task_id": "task_1_1",
            # 実インシデントで観測された壊れた形状: オブジェクトではなく文字列の配列。
            "confirmed_variables": ["mountain_required_vehicle_count"],
        },
        {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
         "current_phase": {"phase_id": "phase_1"}},
    )
    assert result["success"] is True
    assert "warning" in result
    assert "オブジェクト形式" in result["warning"]


def test_malformed_element_does_not_pollute_verified_facts(db_conn):
    """不正な要素はverified_factsへ何も書き込まない（クラッシュを避けるだけでなく、
    ゴミデータも残さないことの確認）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "task_planner"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Decision",
            "topic": "task_planner_phase_design",
            "decision_what": "テスト用の計画再構成決定。",
            "reason_why": "テスト用",
            "phase_id": "phase_1", "task_id": "task_1_1",
            "confirmed_variables": ["mountain_required_vehicle_count"],
        },
        {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
         "current_phase": {"phase_id": "phase_1"}},
    )
    row = conn.execute(
        "SELECT * FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "mountain_required_vehicle_count"),
    ).fetchone()
    assert row is None


def test_valid_and_malformed_elements_can_coexist(db_conn):
    """正しい形式の要素と壊れた要素が混在していても、正しい方は保存され、
    壊れた方だけがスキップされること（全体失敗にしない）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "task_planner"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    result = cela_main.TOOL_DISPATCH["write_agreement"](
        {
            "action_type": "CREATE", "status": "Proposed", "entry_type": "Decision",
            "topic": "task_planner_phase_design",
            "decision_what": "テスト用の計画再構成決定。",
            "reason_why": "テスト用",
            "phase_id": "phase_1", "task_id": "task_1_1",
            "confirmed_variables": [
                {"variable_name": "mountain_required_vehicle_count", "value": "3", "confidence": "provisional"},
                "broken_string_element",
            ],
        },
        {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
         "current_phase": {"phase_id": "phase_1"}},
    )
    assert result["success"] is True
    assert "warning" in result
    row = conn.execute(
        "SELECT value FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "mountain_required_vehicle_count"),
    ).fetchone()
    assert row is not None
    assert row["value"] == "3"


def test_write_agreement_impl_source_has_isinstance_guard():
    src = inspect.getsource(cela_main._write_agreement_impl)
    assert "BL-260" in src
    assert "isinstance(cv, dict)" in src


def test_query_ai_live_confirmed_variable_names_also_guards_isinstance():
    """BL-259 W2で追加したconfirmed_variable_names収集も、同じ非dict要素で
    クラッシュしないよう同じガードを持つこと。"""
    src = inspect.getsource(cela_main._query_AI_live)
    idx = src.index("confirmed_variable_names")
    nearby = src[idx: idx + 400]
    assert "isinstance(cv, dict)" in nearby
