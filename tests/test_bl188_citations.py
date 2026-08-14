"""
BL-188: `citations`（引用元）を全ての情報に明示させる。

ユーザーから「数字などの確定値・暫定値だけでなく、基本的にすべての情報にソースを明示させたい。
情報は可能な限り最新かつ公的な一次ソースを参照させ、web検索結果も批判的思考で評価させたい」
との要望があった。調査の結果、`verified_facts.citations`（F-3.9/R3a）は既にDB列として
存在するが、`_write_agreement_impl`内で実際には`[args.get("topic", "")]`というプレースホルダ
（そのDecisionのtopic文字列そのもの）が機械的に入るだけで、`WRITE_AGREEMENT_TOOL`の
`confirmed_variables`スキーマにはLLMがcitationsを渡すフィールド自体が存在しなかった。加えて
`agreements`テーブル（Decision/Deliverable本体）には構造化されたソース欄が一切なく、自由記述の
`evidence`（F-2.6、主にpython_repl検算結果用）のみだった。

ユーザー確認の上（強制力はDetectorのminor判定等には組み込まず、プロンプト誘導のみ。適用範囲は
confirmed_variablesに加えagreementsテーブル本体にも新規citations列を追加）、以下を実装した:
- `agreements`テーブルへ`citations TEXT DEFAULT '[]'`列を追加（`_ensure_agreements_citations_column`、
  既存の`_ensure_agreements_task_id_column`と同型のマイグレーションパターン）。
- `WRITE_AGREEMENT_TOOL`スキーマへ、トップレベル`citations`パラメータと
  `confirmed_variables[].citations`サブフィールドを追加し、LLMが実際に引用元
  （type: web/goal_text/prior_agreement/expert_calculation/user_input/document, detail: 文字列）を
  渡せるようにした。
- `_commit_agreement_from_tool`が`args["citations"]`をagreementsテーブルへ永続化。
- `confirmed_variables[].citations`が指定されていればそれを`verified_facts.citations`へ使い、
  未指定時は従来通りtopic文字列へフォールバックする（後方互換、弱いシグナルとして扱う）。
- `_build_agreements_context`にcitations表示（evidence_suffixと同型のcitations_suffix、
  BL-064で一度経験済みの「書き込まれるのみで表示に反映されない」失敗パターンの再発防止）。

参照: docs/design/back_log/issue_backlog.md BL-188、decision_log.md D-159。
実LLM API呼び出しは伴わない。
"""

import json
import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl188.db")
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


# ---------------------------------------------------------------------------
# schema migration
# ---------------------------------------------------------------------------

def test_agreements_table_has_citations_column(db_conn):
    conn, _ = db_conn
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    assert "citations" in cols


def test_ensure_agreements_citations_column_migrates_existing_db(tmp_path):
    """既存DB（citations列が無い状態）に対して後から呼んでも安全に列追加できること。"""
    db_path = str(tmp_path / "legacy.db")
    conn = cela_main.get_db_connection(db_path)
    conn.executescript(
        "CREATE TABLE agreements (id TEXT, action_type TEXT, status TEXT, topic TEXT, "
        "decision_what TEXT, reason_why TEXT, proposed_by TEXT, entry_type TEXT, phase_id TEXT, "
        "task_id TEXT, depends_on TEXT, resource_claims TEXT, timestamp REAL, evidence TEXT, "
        "is_frozen INTEGER, internal_thought_process TEXT, run_id TEXT);"
    )
    cela_main._ensure_agreements_citations_column(conn)
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    assert "citations" in cols
    conn.close()


# ---------------------------------------------------------------------------
# _write_agreement_impl: top-level citations persisted to agreements table
# ---------------------------------------------------------------------------

def test_write_agreement_persists_top_level_citations(db_conn):
    conn, run_id = db_conn
    args = {
        "action_type": "CREATE",
        "status": "Approved",
        "topic": "運賃設定の根拠",
        "decision_what": "運賃を200円/回とする",
        "reason_why": "近隣自治体の類似コミュニティバスの相場を参照",
        "entry_type": "Decision",
        "citations": [
            {"type": "web", "detail": "https://example.city.jp/bus/fare"},
            {"type": "goal_text", "detail": "「運賃は近隣相場を参考にする」"},
        ],
    }
    result = cela_main._write_agreement_impl(args, conn, run_id, caller_role="user")
    assert result.get("success") is True

    row = conn.execute(
        "SELECT citations FROM agreements WHERE run_id=? AND topic=?", (run_id, "運賃設定の根拠")
    ).fetchone()
    assert row is not None
    stored = json.loads(row["citations"])
    assert stored == args["citations"]


def test_write_agreement_defaults_citations_to_empty_list_when_omitted(db_conn):
    conn, run_id = db_conn
    args = {
        "action_type": "CREATE",
        "status": "Approved",
        "topic": "特に外部根拠のない判断",
        "decision_what": "内部方針として採用する",
        "reason_why": "チームの合意",
        "entry_type": "Decision",
    }
    result = cela_main._write_agreement_impl(args, conn, run_id, caller_role="user")
    assert result.get("success") is True

    row = conn.execute(
        "SELECT citations FROM agreements WHERE run_id=? AND topic=?",
        (run_id, "特に外部根拠のない判断"),
    ).fetchone()
    assert json.loads(row["citations"]) == []


# ---------------------------------------------------------------------------
# confirmed_variables[].citations -> verified_facts.citations
# ---------------------------------------------------------------------------

def test_confirmed_variable_citations_used_when_provided(db_conn):
    conn, run_id = db_conn
    args = {
        "action_type": "CREATE",
        "status": "Proposed",
        "topic": "車両台数の確定",
        "decision_what": "車両台数を3台とする",
        "reason_why": "需要予測に基づく",
        "entry_type": "Decision",
        "confirmed_variables": [
            {
                "variable_name": "vehicle_count",
                "value": "3",
                "unit": "台",
                "confidence": "provisional",
                "citations": [{"type": "expert_calculation", "detail": "python_replでの需要試算"}],
            }
        ],
    }
    result = cela_main._write_agreement_impl(args, conn, run_id, caller_role="expert", task_id="task_1_1")
    assert result.get("success") is True

    row = conn.execute(
        "SELECT citations FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "vehicle_count"),
    ).fetchone()
    stored = json.loads(row["citations"])
    assert stored == [{"type": "expert_calculation", "detail": "python_replでの需要試算"}]


def test_confirmed_variable_citations_fallback_to_topic_when_omitted(db_conn):
    """[後方互換] citations未指定時は、旧挙動（topic文字列を弱いシグナルとして使う）を維持する。"""
    conn, run_id = db_conn
    args = {
        "action_type": "CREATE",
        "status": "Proposed",
        "topic": "拠点数の確定",
        "decision_what": "拠点数を2箇所とする",
        "reason_why": "地理的バランス",
        "entry_type": "Decision",
        "confirmed_variables": [
            {"variable_name": "hub_count", "value": "2", "unit": "箇所", "confidence": "provisional"}
        ],
    }
    result = cela_main._write_agreement_impl(args, conn, run_id, caller_role="expert", task_id="task_1_1")
    assert result.get("success") is True

    row = conn.execute(
        "SELECT citations FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, "hub_count"),
    ).fetchone()
    assert json.loads(row["citations"]) == ["拠点数の確定"]


# ---------------------------------------------------------------------------
# _build_agreements_context: citations displayed back to LLM-facing context
# ---------------------------------------------------------------------------

def test_build_agreements_context_shows_citations():
    agreements = [
        {
            "id": "AG-1", "action_type": "CREATE", "status": "Approved", "topic": "運賃設定",
            "decision_what": "200円とする", "reason_why": "近隣相場", "entry_type": "Decision",
            "citations": json.dumps([{"type": "web", "detail": "https://example.city.jp/bus/fare"}], ensure_ascii=False),
            "timestamp": time.time(),
        }
    ]
    text = cela_main._build_agreements_context(agreements)
    assert "出典" in text
    assert "web:" in text
    assert "example.city.jp" in text


def test_build_agreements_context_omits_citations_suffix_when_empty():
    agreements = [
        {
            "id": "AG-2", "action_type": "CREATE", "status": "Approved", "topic": "内部方針",
            "decision_what": "採用する", "reason_why": "合意", "entry_type": "Decision",
            "citations": "[]",
            "timestamp": time.time(),
        }
    ]
    text = cela_main._build_agreements_context(agreements)
    assert "出典" not in text


def test_build_agreements_context_tolerates_malformed_citations_json():
    """DBの生データが壊れていても（想定外の値でも）表示関数がクラッシュしないこと。"""
    agreements = [
        {
            "id": "AG-3", "action_type": "CREATE", "status": "Approved", "topic": "壊れたcitations",
            "decision_what": "採用する", "reason_why": "合意", "entry_type": "Decision",
            "citations": "not valid json",
            "timestamp": time.time(),
        }
    ]
    text = cela_main._build_agreements_context(agreements)
    assert "壊れたcitations" in text
