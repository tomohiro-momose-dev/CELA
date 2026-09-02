"""
BL-215: 時刻ベースのレコードIDがミリ秒粒度で衝突し、`ORDER BY id`の並びが不定になっていた。

`agreements` / `decisions` / `goal_shift_events` / `plan_drafts` のidは
`f"{prefix}-{int(time.time()*1000)}"` で採番されており、同一ミリ秒に2回採番すると**完全に同じid**
の行ができる。これらのテーブルにはPRIMARY KEYもUNIQUE制約も無いため重複INSERTが素通りする
（実DBで総行数1724 / 重複id種類90 / 重複に巻き込まれた行188 = 10.9%）。

実害:
1. **順序の不定性** — `get_agreements_from_db`は`ORDER BY id`で並べ、9箇所が`reversed(...)`で
   「最新の行」を取る。同一idのタイの並びはクエリプラン依存で不定であり、実際に
   CREATE(→Superseded)とUPDATE(Approved)が逆順に並び、`_is_task_completed`がSupersededの方を
   最新と誤認した（BL-214のインシデント再現テストが5回中3回失敗するflakyさとして観測）。
2. **UPDATEの増幅** — `db_supersede_agreement`/`freeze_agreement`は`WHERE id=?`で更新するため、
   重複idの全行を巻き込む。
3. **参照の曖昧化** — `depends_on`の参照整合性チェック、`freeze_agreement_id`、citationsの
   `AG-xxx`参照が一意に定まらない。

修正:
- 採番を`_new_record_id(prefix)`（ミリ秒＋uuid断片）へ一元化する。goal_escalations（ESC-）が
  既に採っていた方式に全テーブルを揃える（AGENTS.md §15.1）。
- 並び順を`ORDER BY rowid`（SQLiteの暗黙rowid＝真の挿入順）へ変更する。スキーマ移行不要で
  既存DBにもそのまま効くため、過去runの重複行は遡及修正しない。
- issue_logのidは`uuid4`のため`ORDER BY id`が実質ランダム順だった（同じ欠陥クラス）。
  こちらも`ORDER BY rowid`へ揃える。

参照: docs/design/back_log/BL-214/BL214_basic_design.md §6。実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_PHASES = [
    {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
]


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl215.db")
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


# --- 採番の一意性 -------------------------------------------------------------

def test_new_record_id_is_unique_within_the_same_millisecond():
    """ループで連続採番しても衝突しないこと（修正前は`AG-{ミリ秒}`が完全一致した）。"""
    ids = [cela_main._new_record_id("AG") for _ in range(2000)]
    assert len(set(ids)) == len(ids)


def test_new_record_id_keeps_the_prefix_and_millisecond_component():
    """既存のログ・参照表記（AG-xxx / D-xxx）との互換のため接頭辞は保つ。"""
    generated = cela_main._new_record_id("AG")
    assert generated.startswith("AG-")
    assert generated.split("-")[1].isdigit()


def test_no_bare_millisecond_id_generation_remains_in_source():
    """[AGENTS.md §15.1/§17.1] 採番口を`_new_record_id`単独に保つ配線固定。
    新しいテーブルが素の`f"X-{int(time.time()*1000)}"`で採番を再導入すると同じ欠陥が戻る。"""
    src_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "cela_main.py")
    with open(src_path, encoding="utf-8") as f:
        lines = f.readlines()
    offenders = [
        (i + 1, ln.strip()) for i, ln in enumerate(lines)
        if "int(time.time() * 1000)" in ln or "int(time.time()*1000)" in ln
    ]
    # 唯一許されるのは_new_record_id本体と、その説明コメント。
    offenders = [(n, t) for n, t in offenders if not t.startswith(("return f\"{prefix}", "`f\"{prefix}"))]
    assert offenders == [], f"素のミリ秒採番が残っています: {offenders}"


# --- 順序の決定性 -------------------------------------------------------------

def _insert_agreement(conn, run_id, agreement_id, status, topic="T", task_id="task_1_1"):
    conn.execute(
        "INSERT INTO agreements (id, run_id, timestamp, action_type, entry_type, status, topic, "
        "decision_what, reason_why, phase_id, task_id) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (agreement_id, run_id, time.time(), "CREATE", "Deliverable", status, topic, "c", "r",
         "phase_1", task_id),
    )
    conn.commit()


def test_agreements_are_returned_in_insertion_order_even_with_duplicate_ids(db_conn):
    """既存DBに残る重複idでも、rowid順なら真の挿入順が復元される（遡及修正が不要な理由）。"""
    conn, run_id = db_conn
    dup = "AG-1786448723677"
    _insert_agreement(conn, run_id, dup, "Superseded")
    _insert_agreement(conn, run_id, dup, "Approved")
    statuses = [a["status"] for a in cela_main.get_agreements_from_db(conn, run_id)]
    assert statuses == ["Superseded", "Approved"]


def test_is_task_completed_sees_the_latest_row_when_ids_collide(db_conn):
    """BL-214のインシデント再現テストがflakyだった直接原因。`reversed()`が最新を取れること。"""
    conn, run_id = db_conn
    dup = "AG-1786448723677"
    _insert_agreement(conn, run_id, dup, "Superseded")
    _insert_agreement(conn, run_id, dup, "Approved")
    assert cela_main._is_task_completed(conn, run_id, "task_1_1") is True


def test_write_agreement_create_then_update_is_deterministic(db_conn):
    """[flaky解消の本命] 実際のツール経路で連続書き込みしても、最新がApprovedと判定されること。
    修正前は同一ミリ秒に収まったときだけSupersededを最新と誤認して失敗していた。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "",
             "current_phase": _PHASES[0]}
    for _ in range(20):
        cela_main._CURRENT_CALLER_ROLE = "expert"
        cela_main.TOOL_DISPATCH["write_agreement"](
            {"action_type": "CREATE", "status": "Proposed", "topic": "T",
             "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
             "phase_id": "phase_1", "task_id": "task_1_1"}, state)
        cela_main._CURRENT_CALLER_ROLE = "user"
        cela_main.TOOL_DISPATCH["write_agreement"](
            {"action_type": "UPDATE", "status": "Approved", "topic": "T", "target_topic": "T",
             "decision_what": "Approved", "reason_why": "r", "entry_type": "Deliverable",
             "phase_id": "phase_1", "task_id": "task_1_1"}, state)
        assert cela_main._is_task_completed(conn, run_id, "task_1_1") is True


def test_agreement_ids_from_the_tool_path_are_unique(db_conn):
    """UPDATEの増幅（`WHERE id=?`が重複行を巻き込む）と参照の曖昧化の根本を断つ。"""
    conn, run_id = db_conn
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "",
             "current_phase": _PHASES[0]}
    cela_main._CURRENT_CALLER_ROLE = "expert"
    for i in range(30):
        cela_main.TOOL_DISPATCH["write_agreement"](
            {"action_type": "CREATE", "status": "Proposed", "topic": f"T{i}",
             "decision_what": "X" * 500, "reason_why": "r", "entry_type": "Deliverable",
             "phase_id": "phase_1", "task_id": "task_1_1"}, state)
    ids = [r["id"] for r in conn.execute(
        "SELECT id FROM agreements WHERE run_id=?", (run_id,)).fetchall()]
    assert len(ids) == 30
    assert len(set(ids)) == 30


def test_issue_log_is_returned_in_creation_order(db_conn):
    """issue_logのidはuuid4であり、`ORDER BY id`は実質ランダム順だった。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "detector"
    state = {"run_id": run_id, "phases": _PHASES, "current_task_id": "task_1_1",
             "current_phase": _PHASES[0]}
    topics = [f"issue_{i:02d}" for i in range(15)]
    for t in topics:
        cela_main.TOOL_DISPATCH["write_issue"](
            {"action_type": "CREATE", "topic": t, "severity": "minor", "description": "d"}, state)
    rows = cela_main.get_issues_from_db(conn, run_id, list_all=True)
    assert [r["topic"] for r in rows] == topics
