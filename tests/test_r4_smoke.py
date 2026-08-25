"""
R4（ホワイトボード差分パッチ化）完了条件のうち、実LLM API呼び出しを伴わないオフライン検証項目。

参照: docs/design/r4/cela_r4_design.md、docs/design/r4/cela_r4_impl_Plan.md。

実LLMドライランが必要な項目（design.md §3の完了条件: フェーズ間矛盾の早期発見率、
トークン消費比較）は本ファイルの対象外 — ドライラン実施後にtraceability.mdへ別途記録する。
"""

import os
import sys
import time
import uuid

import pytest
from langgraph.graph import StateGraph, END

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


@pytest.fixture()
def db_conn(tmp_path):
    """R1のSQLite基盤（module-levelシングルトン）をテスト用一時DBで初期化する。"""
    db_path = str(tmp_path / "test_r4.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    # [BL-131] write_agreementのtask_id実在チェックが、stateを渡さない旧来の
    # グローバル経由呼び出し（本ファイルの一貫した書き方）でも通るようにする。
    cela_main._CURRENT_PHASES = [
        {"phase_id": "phase_1", "tasks": [{"task_id": "task_1_1"}, {"task_id": "task_1_2"}]},
    ]
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_PHASES = []


# ===========================================================================
# whiteboard_drafts DBヘルパー（apply_whiteboard_patch / get_latest_whiteboard / rollback）
# ===========================================================================

def test_apply_and_get_latest_whiteboard_roundtrip(db_conn):
    """バージョンが1から始まり、書き込むたびに+1されること。"""
    conn, run_id = db_conn
    assert cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1") is None

    v1 = cela_main.apply_whiteboard_patch(conn, run_id, "phase_1", "task_1_1", "内容V1", "expert", "初版")
    assert v1 == 1
    latest = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest == {"version": 1, "content": "内容V1"}

    v2 = cela_main.apply_whiteboard_patch(conn, run_id, "phase_1", "task_1_1", "内容V2", "expert", "修正")
    assert v2 == 2
    latest2 = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert latest2 == {"version": 2, "content": "内容V2"}


# ===========================================================================
# _apply_text_edits（Claude Code Editツール方式の完全一致置換）
# ===========================================================================

def test_apply_text_edits_single_unique_match():
    content = "車両台数は4台とする。\n年間維持費は2,674万円である。"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "車両台数は4台とする。", "new_text": "車両台数は3台とする。"}
    ])
    assert err is None
    assert new_content == "車両台数は3台とする。\n年間維持費は2,674万円である。"


def test_apply_text_edits_not_found_returns_error_without_mutating():
    content = "車両台数は4台とする。"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "存在しないテキスト", "new_text": "X"}
    ])
    assert new_content is None
    assert err is not None and "見つかりません" in err


def test_apply_text_edits_ambiguous_match_without_replace_all_returns_error():
    content = "台数: 4台\n別の台数: 4台"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "4台", "new_text": "3台"}
    ])
    assert new_content is None
    assert err is not None and "一意に特定できません" in err


def test_apply_text_edits_replace_all_true_replaces_every_occurrence():
    content = "台数: 4台\n別の台数: 4台"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "4台", "new_text": "3台", "replace_all": True}
    ])
    assert err is None
    assert new_content == "台数: 3台\n別の台数: 3台"


def test_apply_text_edits_multiple_edits_applied_in_sequence():
    content = "A: 1\nB: 2\nC: 3"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "A: 1", "new_text": "A: 10"},
        {"old_text": "C: 3", "new_text": "C: 30"},
    ])
    assert err is None
    assert new_content == "A: 10\nB: 2\nC: 30"


def test_apply_text_edits_non_dict_edit_item_returns_error_without_crashing():
    """本番ドライランで、LLMが`edits`に{old_text,new_text}辞書ではなく生文字列を
    返したため`e.get("old_text", "")`が`AttributeError: 'str' object has no
    attribute 'get'`で未捕捉クラッシュし、run_ai_vs_ai_loop全体が停止した事故の再発防止。
    非dict要素はクラッシュではなくエラー文字列としてツール呼び出し元へ返し、
    ツールループ内で自己修正できるようにする。"""
    content = "車両台数は4台とする。"
    new_content, err = cela_main._apply_text_edits(content, ["車両台数は3台とする。"])
    assert new_content is None
    assert err is not None and "edits[0]" in err and "str" in err


def test_apply_text_edits_non_dict_edit_item_among_valid_ones_returns_error():
    content = "A: 1\nB: 2"
    new_content, err = cela_main._apply_text_edits(content, [
        {"old_text": "A: 1", "new_text": "A: 10"},
        "B: 2",
    ])
    assert new_content is None
    assert err is not None and "edits[1]" in err


# ===========================================================================
# write_agreement経由のDeliverable CREATE/UPDATE（whiteboard統合）
# ===========================================================================

def test_write_agreement_deliverable_create_saves_to_whiteboard_v1(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    long_content = "X" * 300

    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4テスト成果物",
        "decision_what": long_content, "reason_why": "r", "entry_type": "Deliverable",
        "phase_id": "phase_1",
    })
    assert result["success"] is True

    row = conn.execute(
        "SELECT decision_what FROM agreements WHERE topic=? AND run_id=?",
        ("R4テスト成果物", run_id),
    ).fetchone()
    assert row["decision_what"] == "WHITEBOARD:phase_1:task_1_1"

    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert wb == {"version": 1, "content": long_content}


def test_write_agreement_deliverable_update_with_edits_applies_diff(db_conn):
    """write_agreementのUPDATE + editsが、現在の完全版に対し正しくマージされること
    （decision_whatを空にしてもeditsだけで成立すること）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"

    create_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4差分テスト",
        "decision_what": "車両台数は4台とする。" + "余白" * 100,
        "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })
    assert create_result["success"] is True
    # [BL-265] editsを使うUPDATEはread_whiteboard_excerptでの確認記録を要求する。
    cela_main._LAST_WHITEBOARD_READS.add("task_1_1")

    update_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Proposed", "topic": "R4差分テスト",
        "target_topic": "R4差分テスト", "phase_id": "phase_1",
        "reason_why": "リース案採用のため台数見直し", "entry_type": "Deliverable",
        "edits": [{"old_text": "車両台数は4台とする。", "new_text": "車両台数は3台とする。"}],
    })
    assert update_result["success"] is True, update_result

    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert wb["version"] == 2
    assert wb["content"].startswith("車両台数は3台とする。")
    assert "余白" in wb["content"], "editsで触れていない箇所が失われてはいけない"


def test_write_agreement_deliverable_update_with_bad_old_text_fails_without_writing(db_conn):
    """old_textが一致しない場合、DBに何も書き込まずエラーを返す（同一ツールループ内で
    Expertが修正・再試行できるようにするため）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"

    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4異常系テスト",
        "decision_what": "本文" * 150, "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })
    # [BL-265] editsを使うUPDATEはread_whiteboard_excerptでの確認記録を要求する。この
    # テストの主眼はold_text不一致時の挙動であり、read-before-write自体は満たしておく。
    cela_main._LAST_WHITEBOARD_READS.add("task_1_1")

    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Proposed", "topic": "R4異常系テスト",
        "target_topic": "R4異常系テスト", "phase_id": "phase_1",
        "reason_why": "r", "entry_type": "Deliverable",
        "edits": [{"old_text": "存在しない文字列XYZ", "new_text": "新しい内容"}],
    })
    assert result["success"] is False
    assert "見つかりません" in result["error"]

    # バージョンは進んでいない（V1のまま）こと、topicのagreementsも1件のまま（新規INSERTされていない）こと
    wb = cela_main.get_latest_whiteboard(conn, run_id, "phase_1", "task_1_1")
    assert wb["version"] == 1
    rows = conn.execute(
        "SELECT * FROM agreements WHERE topic=? AND run_id=?", ("R4異常系テスト", run_id)
    ).fetchall()
    assert len(rows) == 1, "old_text不一致で失敗した場合、DBに新規レコードが増えてはいけない"


def test_write_agreement_deliverable_create_without_phase_task_id_still_short_circuits_gracefully(db_conn):
    """decision_whatが必須チェックを免除されるのはUPDATE+Deliverable+edits指定時のみであること
    （CREATE時にdecision_whatを省略したら通常通りエラーになること）。"""
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4必須チェックテスト",
        "reason_why": "r", "entry_type": "Deliverable",
    })
    assert result["success"] is False
    assert "decision_what" in result["error"]


# ===========================================================================
# BL-038/R4: decision_extractorフォールバック経路のWHITEBOARDポインタ保護
# ===========================================================================

def test_decision_extractor_fallback_protects_whiteboard_pointer_from_plaintext_overwrite(db_conn, monkeypatch):
    """実ドライランで観測された事故の再現: write_agreementで既にWHITEBOARD:ポインタが
    保存されているtopicに対し、decision_extractorのフォールバック経路（write_agreement
    未検出時の安全網）がプレーンな短文でUPDATEしようとしても、ポインタが保護され
    Supersededにならないこと。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"

    create_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "水ノ守町 分析レポート",
        "decision_what": "フル本文" * 100, "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })
    assert create_result["success"] is True

    canned_items = [{
        "action_type": "UPDATE", "entry_type": "Deliverable", "status": "Proposed",
        "target_topic": "水ノ守町 分析レポート", "topic": "水ノ守町 分析レポート",
        "content": "タスク完了しました、という短い完了報告文のみ（フル本文ではない）",
        "rationale": "理由", "proposed_by": "expert", "owned_variable_values": {},
    }]
    monkeypatch.setattr(cela_main, "call_decision_extractor", lambda *a, **k: (canned_items, {}))

    state = {
        "run_id": run_id, "turn_count": 1,
        "chat_history": [{"role": "assistant", "content": "expertの発言"}],
        "current_phase": {"phase_id": "phase_1", "tasks": [
            {"task_id": "task_1_1", "owns_variables": [], "acceptance_criteria": []}
        ]},
        "current_task_id": "task_1_1",
        "phases": [{"phase_id": "phase_1", "tasks": [
            {"task_id": "task_1_1", "owns_variables": [], "acceptance_criteria": []}
        ]}],
        "expert_wrote_agreement": False,  # ガードが機能しなかった場合（BL-038）を模擬
    }
    cela_main.decision_extractor_node(state)

    rows = [a for a in cela_main.get_agreements_from_db(conn, run_id) if a["topic"] == "水ノ守町 分析レポート"]
    # [BL-215] idは`AG-{ミリ秒}-{uuid断片}`となり、文字列の大小は挿入順を表さない
    # （そもそも修正前もミリ秒衝突時は同値で最大が定まらなかった）。
    # get_agreements_from_dbはrowid昇順＝真の挿入順を返すため、末尾が最新である。
    latest = rows[-1]
    assert latest["decision_what"] == "WHITEBOARD:phase_1:task_1_1", (
        "decision_extractorのフォールバック経路がWHITEBOARDポインタをプレーンテキストで"
        "上書きしてしまった（実ドライランで観測した事故の再発）"
    )
    assert latest["status"] != "Superseded"


# ===========================================================================
# integrator_node / read_deliverable_file のWHITEBOARD:ポインタ解決
# ===========================================================================

def test_read_deliverable_file_resolves_whiteboard_pointer_by_task_id(db_conn):
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main._CURRENT_TASK_ID = "task_1_1"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4読み取りテスト",
        "decision_what": "Z" * 300, "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })

    content = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"task_id": "task_1_1"})
    assert isinstance(content, str) and content.startswith("Z" * 10)

    content_by_topic = cela_main.TOOL_DISPATCH["read_deliverable_file"]({"topic_keyword": "R4読み取り"})
    assert isinstance(content_by_topic, str) and content_by_topic.startswith("Z" * 10)


# ===========================================================================
# BL-038: LangGraphの未宣言キー伝播バグ（実グラフ経由での回帰テスト）
# ===========================================================================

def test_lineage_state_propagates_wrote_agreement_flag_through_real_graph():
    """BL-038根本原因の固定化: expert_wrote_agreement/user_wrote_agreement/
    expert_last_whiteboard_editはLineageState(TypedDict)に宣言されていないと、
    LangGraphがノード間で値を伝播しない（未宣言キーへの書き込みは次ノードに渡る前に
    消える）。decision_extractor_node等をPython関数として直接呼ぶ既存のオフライン
    テストはLangGraphのチャネル機構を経由しないため、この種の回帰を検出できない。
    本テストは実際にcela_main.LineageStateをスキーマとしたStateGraphを組み、
    app.invoke()経由でノードをまたいでも値が生き残ることを検証する（実LLM呼び出しなし）。
    """
    def node_a(state):
        state["expert_wrote_agreement"] = True
        state["user_wrote_agreement"] = True
        state["expert_last_whiteboard_edit"] = {"phase_id": "phase_1", "task_id": "task_1_1", "version": 2}
        return state

    def node_b(state):
        # decision_extractor_node/expert_nodeが読む際と同じ取得方法
        assert state.get("expert_wrote_agreement", False) is True, (
            "expert_wrote_agreementがLineageStateに宣言されておらずノード間で消失した"
            "（BL-038の再発）"
        )
        assert state.get("user_wrote_agreement", False) is True
        assert state.get("expert_last_whiteboard_edit") == {
            "phase_id": "phase_1", "task_id": "task_1_1", "version": 2
        }
        return state

    graph = StateGraph(cela_main.LineageState)
    graph.add_node("a", node_a)
    graph.add_node("b", node_b)
    graph.add_edge("a", "b")
    graph.add_edge("b", END)
    graph.set_entry_point("a")
    app = graph.compile()

    result = app.invoke({"run_id": "test", "chat_history": [], "turn_count": 1})
    assert result.get("expert_wrote_agreement") is True
    assert result.get("expert_last_whiteboard_edit") == {
        "phase_id": "phase_1", "task_id": "task_1_1", "version": 2
    }


def test_integrator_node_reads_whiteboard_pointer(db_conn, monkeypatch):
    """integrator_nodeがWHITEBOARD:ポインタを正しく読み込み、統合文書に反映すること
    （FILE_PATH:の既存の読み込み分岐と対）。call_integrator（実LLM呼び出し）はモックする。"""
    conn, run_id = db_conn
    cela_main._CURRENT_TASK_ID = "task_1_1"
    marker_text = "これは統合されるべきWHITEBOARD本文マーカーです"
    # [BL-169] entry_type='Deliverable'のCREATEはExpertのみ許可（userは不可）になったため、
    # Expertが新規作成した上でUserが承認する2段階の現実的なフローで成果物を用意する。
    cela_main._CURRENT_CALLER_ROLE = "expert"
    create_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "R4統合テスト成果物",
        "decision_what": marker_text + "。" * 200,
        "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })
    assert create_result["success"] is True

    cela_main._CURRENT_CALLER_ROLE = "user"
    approve_result = cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "UPDATE", "status": "Approved", "topic": "R4統合テスト成果物",
        "decision_what": marker_text + "。" * 200,
        "reason_why": "r", "entry_type": "Deliverable", "phase_id": "phase_1",
    })
    assert approve_result["success"] is True

    captured = {}

    def fake_call_integrator(goal, merged_text, **kwargs):
        captured["merged_text"] = merged_text
        return {"contradictions": False}

    monkeypatch.setattr(cela_main, "call_integrator", fake_call_integrator)

    state = {"run_id": run_id, "goal": "テストゴール\n詳細", "turn_count": 1}
    try:
        cela_main.integrator_node(state)
        assert marker_text in captured.get("merged_text", ""), (
            "integrator_nodeがWHITEBOARD:ポインタの内容を統合文書に反映できていない"
        )
    finally:
        # integrator_nodeは最終統合文書をsave_deliverable_to_fileでファイル保存する（対象外の既存機構）ため後始末
        rows = conn.execute(
            "SELECT decision_what FROM agreements WHERE run_id=? AND topic LIKE '%最終統合要件定義書%'",
            (run_id,)
        ).fetchall()
        for r in rows:
            dw = r["decision_what"]
            if dw.startswith("FILE_PATH:"):
                p = dw[len("FILE_PATH:"):]
                if os.path.exists(p):
                    os.remove(p)
