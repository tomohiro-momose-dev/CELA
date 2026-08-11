"""
BL-213 F1: `integrator_node`が、承認済みDeliverable行の`decision_what`が`FILE_PATH:`でも
`WHITEBOARD:`でもない場合、その文字列を**そのまま最終統合文書へ出力**していた。

BL-212の短文汚染（承認撤回の理由文45〜105字がDeliverable行のdecision_whatに残る）と
組み合わさると、27KBの設計本文の代わりに「承認を撤回する」の1行がプロジェクト最終成果物
へ載る。しかも従来の`else`分岐は正常系として扱われるため**警告が一切出ず**、run全体が
無駄になったことに最後まで気づけない——という、実害が大きくかつ発見が最も遅れる欠陥だった。

BL-212/D-187で書き込み側の汚染源は塞いだが、過去のrunで既に生まれた汚染行に対する保険
として読み取り側にも防御を置く。D-186と同じくwhiteboard_draftsを権威とし、agreements側の
文字列表現は当てにしない。

ただし「ポインタ形式でなければ常に異常」とはしない。200字以下でホワイトボード化されな
かった短文Deliverable（BL-180/H2の正当な経路）が存在し、その場合`decision_what`自体が
実本文だからである。両者は「そのtask_idにwhiteboard_draftsの実体があるか」で機械的に
区別できる。

あわせて、`"WHITEBOARD:"`のような欠損したポインタで`split(":", 2)`の3要素アンパックが
ValueErrorとなり、run最終段の`integrator_node`ごと落ちる問題も修正した。

参照: docs/design/back_log/BL-213/BL213_investigation.md（F1）、
docs/design/back_log/issue_backlog.md BL-213・BL-212、docs/design/decision_log.md D-186・D-187。
実LLM API呼び出しは伴わない。
"""

import os
import sys
import time
import uuid

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    db_path = str(tmp_path / "test_bl213f1.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None


_REAL_BODY = "# task_4_2 停留所・予約・利用データ記録の設計\n\n" + ("実際の設計本文。" * 200)
_WITHDRAWAL_TEXT = (
    "task_4_2の承認およびtask_4_3への移行判断を明確に撤回し、task_4_2を修正再提出待ちの"
    "Rejectedとする。前回の承認は無効であり、修正版が再提出されるまでtask_4_3以降へ進めない。"
)


def _make_whiteboard(conn, run_id, phase_id="phase_4", task_id="task_4_2", content=_REAL_BODY):
    return cela_main.apply_whiteboard_patch(
        conn, run_id, phase_id, task_id, content, author_role="expert", edit_summary="初版"
    )


def _agreement(decision_what, phase_id="phase_4", task_id="task_4_2",
               topic="task_4_2 停留所・予約・利用データ記録の設計"):
    return {
        "id": "AG-TEST-000001", "entry_type": "Deliverable", "status": "Approved",
        "topic": topic, "decision_what": decision_what,
        "phase_id": phase_id, "task_id": task_id, "reason_why": "r",
    }


def _resolve(conn, run_id, agreement):
    return cela_main._resolve_deliverable_content_for_integration(conn, run_id, agreement)


# ---------------------------------------------------------------------------
# 1. 実インシデント（BL-212の短文汚染）からの復元
# ---------------------------------------------------------------------------

def test_short_withdrawal_text_is_replaced_by_real_whiteboard_body(db_conn):
    """実インシデント再現：撤回理由文がdecision_whatに残った承認済みDeliverableでも、
    whiteboard_draftsに実体があれば実本文が統合される。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id)

    result = _resolve(conn, run_id, _agreement(_WITHDRAWAL_TEXT))

    assert result == _REAL_BODY, "汚染された短文がそのまま最終文書へ載っている（BL-213 F1再発）"
    assert _WITHDRAWAL_TEXT not in result


def test_recovery_emits_a_visible_warning(db_conn, capsys):
    """[F1の核心] 従来はelse分岐が正常系扱いで警告が一切出なかった。復元時は必ず
    ログへ痕跡を残し、後からログを読めば汚染があったと分かるようにする。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id)

    _resolve(conn, run_id, _agreement(_WITHDRAWAL_TEXT))

    captured = capsys.readouterr().out
    assert "BL-213" in captured
    assert "task_4_2" in captured


# ---------------------------------------------------------------------------
# 2. 正当な短文Deliverableを壊さないこと（過剰検知の防止）
# ---------------------------------------------------------------------------

def test_unpromoted_short_deliverable_is_emitted_as_is(db_conn):
    """[REJECTED案の回帰] 200字以下でホワイトボード化されなかった短文Deliverable
    （BL-180/H2の正当な経路）は、decision_what自体が実本文なのでそのまま出力する。"""
    conn, run_id = db_conn
    # whiteboard_draftsは作らない
    short_body = "暫定メモ：本タスクは上流の確定待ちのため、現時点では方針のみを記録する。"

    result = _resolve(conn, run_id, _agreement(short_body))

    assert result == short_body


def test_unpromoted_short_deliverable_emits_no_warning(db_conn, capsys):
    """正当な短文Deliverableに対して誤って警告を出さないこと（ログのノイズ化防止）。"""
    conn, run_id = db_conn
    _resolve(conn, run_id, _agreement("暫定メモ。"))

    assert "BL-213" not in capsys.readouterr().out


def test_other_task_whiteboard_does_not_leak_into_short_deliverable(db_conn):
    """別タスクにホワイトボードが存在しても、当該task_idに無ければ復元しないこと
    （他タスクの本文が紛れ込まない）。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id, task_id="task_4_1", content="task_4_1の本文")

    result = _resolve(conn, run_id, _agreement("task_4_2の暫定メモ。", task_id="task_4_2"))

    assert result == "task_4_2の暫定メモ。"


# ---------------------------------------------------------------------------
# 3. 非退行：従来から正常だった経路
# ---------------------------------------------------------------------------

def test_whiteboard_pointer_still_resolves(db_conn):
    """[非退行] 正常な`WHITEBOARD:`ポインタは従来通り最新版を返すこと。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id)

    result = _resolve(conn, run_id, _agreement("WHITEBOARD:phase_4:task_4_2"))

    assert result == _REAL_BODY


def test_whiteboard_pointer_returns_latest_version(db_conn):
    """[非退行] 複数バージョンがある場合は最新版を返すこと。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id, content="V1本文")
    _make_whiteboard(conn, run_id, content="V2本文")

    assert _resolve(conn, run_id, _agreement("WHITEBOARD:phase_4:task_4_2")) == "V2本文"


def test_file_path_pointer_still_resolves(db_conn, tmp_path):
    """[非退行] `FILE_PATH:`ポインタは従来通りファイルを読むこと。"""
    conn, run_id = db_conn
    f = tmp_path / "deliverable.md"
    f.write_text("ファイル由来の本文", encoding="utf-8")

    result = _resolve(conn, run_id, _agreement(f"FILE_PATH:{f}"))

    assert result == "ファイル由来の本文"


def test_missing_file_still_reports_not_found(db_conn, tmp_path):
    """[非退行] 参照先ファイルが無い場合は従来通り警告文字列を返すこと。"""
    conn, run_id = db_conn
    missing = str(tmp_path / "does_not_exist.md")

    result = _resolve(conn, run_id, _agreement(f"FILE_PATH:{missing}"))

    assert "ファイルが見つかりません" in result


def test_missing_whiteboard_still_reports_not_found(db_conn):
    """[非退行] ポインタはあるが実体が無い場合は従来通り警告文字列を返すこと
    （存在しない本文を捏造しない）。"""
    conn, run_id = db_conn

    result = _resolve(conn, run_id, _agreement("WHITEBOARD:phase_9:task_9_9",
                                               phase_id="phase_9", task_id="task_9_9"))

    assert "ホワイトボードが見つかりません" in result


# ---------------------------------------------------------------------------
# 4. 壊れたポインタでintegrator_nodeごと落ちないこと
# ---------------------------------------------------------------------------

def test_malformed_pointer_does_not_raise(db_conn):
    """[BL-213 F1] `"WHITEBOARD:"`のような要素不足のポインタは、従来3要素への
    直接アンパックでValueErrorとなりrun最終段のintegrator_nodeごと落としていた。
    agreements行自身のphase_id/task_idへフォールバックして復旧すること。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id)

    result = _resolve(conn, run_id, _agreement("WHITEBOARD:"))

    assert result == _REAL_BODY


def test_malformed_pointer_without_whiteboard_returns_warning_not_crash(db_conn):
    """要素不足のポインタかつ実体も無い場合でも、例外ではなく警告文字列を返すこと。"""
    conn, run_id = db_conn

    result = _resolve(conn, run_id, _agreement("WHITEBOARD:", task_id="task_9_9"))

    assert "ホワイトボードが見つかりません" in result


def test_pointer_with_wrong_task_id_falls_back_to_agreement_task_id(db_conn):
    """ポインタ内のtask_idが壊れていても、agreements行のtask_idで救えること。"""
    conn, run_id = db_conn
    _make_whiteboard(conn, run_id, task_id="task_4_2")

    result = _resolve(conn, run_id,
                      _agreement("WHITEBOARD:phase_4:task_XXXX", task_id="task_4_2"))

    assert result == _REAL_BODY


# ---------------------------------------------------------------------------
# 5. integrator_nodeへの配線
# ---------------------------------------------------------------------------

def test_integrator_node_uses_the_resolver():
    """テスト側が解決ヘルパを直接呼んでいるため、`integrator_node`本体が
    そのヘルパを使わなくなっても上記テストは通ってしまう。配線をソースレベルで固定する。"""
    import inspect
    src = inspect.getsource(cela_main.integrator_node)
    assert "_resolve_deliverable_content_for_integration" in src, (
        "integrator_nodeが解決ヘルパを経由しなくなっている（BL-213 F1再発）"
    )
    assert 'content_text = content_data' not in src, (
        "decision_whatを無検査で最終文書へ流す旧ロジックが復活している"
    )
