"""
BL-312: call_detectorのdomain_prompt/promptを静的先頭・動的末尾へ再構成し、
プロンプトキャッシュの実効ヒット率を改善する。

ユーザー報告: OpenRouterのプロンプトキャッシュヒット率が70%台→65%程度へ低下した。調査の
結果、直近のBL-306/BL-307自体は無関係だったが、call_detectorのdomain_prompt/prompt
（数値監査）が、call_expert（BL-178/BL-104で「固定指示文は先頭・動的データは末尾」に
再構成済み）と異なり、一度もその再構成を受けておらず、静的な指示ブロック（BL-086/087/
266/278・306/279/292/076/062）が決定事項DB・ゴール文・本質・ホワイトボード等の動的
ブロックの"後ろ"に挟まったままだったことが判明した。Detectorは全タスクでdomain review＋
numeric auditの2パスが毎回走る最頻出ノードであり、静的指示を追加するたび（BL-306等）に
キャッシュされない領域が広がる構造だった。

対応: 位置参照文（「上記の」「上記2つ」「上記DB」「上記ホワイトボードの本文から」等、
計11箇所）を見出し名・BL番号での自己完結文（「後述の…」「[BL-087]の…」等）へ書き換えた
上で、該当する静的指示ブロックをすべて先頭（STATIC-TOP）へ移動し、state/DB由来の動的
ブロックを末尾（DYNAMIC-TAIL）へ集約した（BL-178のlight_system_promptと同じ技法）。
domain_role_instruction（review_mode=="goal_change"分岐でのみ動的）・
role_specific_instruction（target_role=="user"分岐でのみ動的）は、安全側に倒して
DYNAMIC-TAILへ配置した。thought_process_auditは自身の内部に「上記のBL-023
criteria_status判定」「上記のBL-033機械的検算記録」という後方参照を持つため、
criteria_text・python_calls_blockより後という現在の相対位置を変えていない。

参照: BL-104/BL-178（call_expertの先行実装）、docs/design/back_log/BL-312/。
実LLM API呼び出しは伴わない（_query_and_parse_with_retryをmonkeypatchしてプロンプト
文字列そのものを捕捉・検証する）。
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
    db_path = str(tmp_path / "test_bl312.db")
    conn = cela_main.get_db_connection(db_path)
    cela_main.init_db(conn)
    cela_main._DB_CONN = conn
    run_id = f"test-{int(time.time())}-{uuid.uuid4().hex[:8]}"
    cela_main._CURRENT_RUN_ID = run_id
    cela_main._CURRENT_TASK_ID = ""
    cela_main._CURRENT_PHASE_ID = ""
    try:
        yield conn, run_id
    finally:
        conn.close()
        cela_main._DB_CONN = None
        cela_main._CURRENT_RUN_ID = ""
        cela_main._CURRENT_CALLER_ROLE = ""
        cela_main._CURRENT_TASK_ID = ""
        cela_main._CURRENT_PHASE_ID = ""


def _install_capturing_retry(monkeypatch, captured: dict):
    """[test_bl292流用] _query_and_parse_with_retryへ渡された生のprompt文字列を
    labelごとに捕捉するスタブへ差し替える（実LLM呼び出しは発生しない）。"""
    def _fake(prompt, client, model, label, tools, fallback, max_retries=2, state=None):
        captured[label] = prompt
        return dict(fallback), False
    monkeypatch.setattr(cela_main, "_query_and_parse_with_retry", _fake)


def _state_for(run_id: str, goal_text: str, user_content: str,
               task_id: str = "task_1_1", phase_id: str = "phase_1") -> dict:
    return {
        "run_id": run_id,
        "goal": goal_text,
        "chat_history": [{"role": "user", "content": user_content}],
        "current_phase": {
            "phase_id": phase_id,
            "tasks": [{"task_id": task_id, "title": "t", "acceptance_criteria": ["AC1を満たす", "AC2を満たす"]}],
        },
        "current_task_id": task_id,
    }


def _capture_prompts(conn, run_id: str, monkeypatch, goal_text: str, user_content: str) -> dict:
    captured: dict = {}
    _install_capturing_retry(monkeypatch, captured)
    cela_main._CURRENT_CALLER_ROLE = "expert"
    cela_main.call_detector(_state_for(run_id, goal_text, user_content), target_role="expert")
    return captured


def test_bl312_static_prefix_is_stable_across_differing_dynamic_content(db_conn, monkeypatch):
    """[最重要・§17.1の反証可能な回帰テスト] target_role/review_modeが同じでも、ゴール文・
    決定事項DB・ホワイトボードといった動的内容が異なる2回の呼び出しで、domain_prompt/
    promptそれぞれの共通接頭辞（≒プロンプトキャッシュの実効ヒット長）が十分に長いこと
    （BL-312適用前はこの手前で動的ブロックが挟まるため接頭辞が数百字程度で途切れていた）。
    """
    conn, run_id = db_conn

    # 1回目: 短いゴール文・素の状態（Freeze済みagreementなし）
    captured1 = _capture_prompts(conn, run_id, monkeypatch, "テストゴールA", "発言A")
    domain1 = captured1["Detector (Domain Review)"]
    numeric1 = captured1["Detector"]

    # 2回目: 全く異なる長さ・内容のゴール文＋DBへagreement（Freeze済み）/whiteboardを
    # 追加してから呼ぶ。Freeze済みagreementは_get_frozen_agreements_text（BL-086が
    # 旧コードで隣接していた動的ブロック）の出力を実際に変化させる（""→非空）ため、
    # 早い段階の動的ブロックが空文字で一致してしまい判別力を失う、という落とし穴を回避する。
    # [BL-172回避] status="Approved"等（RESOLVING_DELIVERABLE_STATUSES）はBL-172ガード
    # （Expert作成のDeliverable実在チェック）の対象になりうるため、対象外の"Proposed"を使う。
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Proposed", "topic": "予算上限の確定",
        "decision_what": "予算上限は1億2000万円としてBで確定した", "reason_why": "承認",
        "entry_type": "Decision",
    })
    frozen_id = cela_main.get_agreements_from_db(conn, run_id)[-1]["id"]
    cela_main.TOOL_DISPATCH["freeze_agreement"]({"agreement_id": frozen_id, "reason": "テスト用Freeze"})
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        new_content="# task_1_1の成果物（第2版、内容は全く異なる）\n詳細な試算結果...",
        author_role="expert", edit_summary="B版",
    )
    captured2 = _capture_prompts(
        conn, run_id, monkeypatch,
        "全く別の、はるかに長いゴール文です。" * 5,
        "発言B、内容も長さも1回目とは全く異なるものにする。" * 3,
    )
    domain2 = captured2["Detector (Domain Review)"]
    numeric2 = captured2["Detector"]

    domain_prefix_len = len(os.path.commonprefix([domain1, domain2]))
    numeric_prefix_len = len(os.path.commonprefix([numeric1, numeric2]))

    # 実測値（本シナリオ、target_role="expert"）: BL-312適用前は_get_frozen_agreements_text
    # の差分で接頭辞が途切れ domain=6687字/numeric=7177字。適用後はBL-086/087/266/278・
    # 306/279/292/076がSTATIC-TOPへ移動したため domain=9188字/numeric=8278字まで伸びる。
    # しきい値は両者の中間に設定し、git stashでの反証確認（旧コードでは必ず下回る）込み。
    assert domain_prefix_len > 8000, f"domain_promptの共通接頭辞が短すぎる: {domain_prefix_len}字"
    assert numeric_prefix_len > 7700, f"promptの共通接頭辞が短すぎる: {numeric_prefix_len}字"


def test_bl312_dynamic_content_still_fully_present(db_conn, monkeypatch):
    """[内容完全性] 再構成後もdomain_prompt/promptの両方に、ゴール文・決定事項DB・
    ホワイトボード本文・今回のやり取り本文が全て（順序が変わっただけで）含まれていること。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "一意な合意事項トピック名XYZ123",
        "decision_what": "内容", "reason_why": "理由", "entry_type": "Decision",
    })
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        new_content="一意なホワイトボード本文マーカーABC789",
        author_role="expert", edit_summary="初版",
    )
    captured = _capture_prompts(conn, run_id, monkeypatch, "一意なゴール文マーカーGOAL456", "一意な発言マーカーUTTER999")
    domain_prompt = captured["Detector (Domain Review)"]
    numeric_prompt = captured["Detector"]

    for marker in ("一意なゴール文マーカーGOAL456", "一意なホワイトボード本文マーカーABC789", "一意な発言マーカーUTTER999"):
        assert marker in domain_prompt, f"domain_promptに{marker!r}が見当たらない"
        assert marker in numeric_prompt, f"promptに{marker!r}が見当たらない"
    # agreements_text（決定事項DB全文）はdomain_promptには渡されない設計（frozen分のみ）ため
    # numeric_promptのみで確認する。
    assert "一意な合意事項トピック名XYZ123" in numeric_prompt


def test_bl312_rewritten_references_match_actual_headings(db_conn, monkeypatch):
    """[見出し一致] 書き換えた自己完結文が指す見出し文字列が、実際にホワイトボード・
    決定事項DBの出力見出しと一字一句一致していること（参照先を見失わないための保証）。"""
    conn, run_id = db_conn
    cela_main._CURRENT_CALLER_ROLE = "user"
    cela_main.TOOL_DISPATCH["write_agreement"]({
        "action_type": "CREATE", "status": "Approved", "topic": "t",
        "decision_what": "d", "reason_why": "r", "entry_type": "Decision",
    })
    cela_main.apply_whiteboard_patch(
        conn, run_id, "phase_1", "task_1_1",
        new_content="本文", author_role="expert", edit_summary="初版",
    )
    captured = _capture_prompts(conn, run_id, monkeypatch, "ゴール文", "発言")
    domain_prompt = captured["Detector (Domain Review)"]
    numeric_prompt = captured["Detector"]

    # BL-076: whiteboard_blockの実際の見出しは「【R4: 現在タスクの成果物・最新ホワイトボード
    # Ver.N（編集後の完全版）】」。自己完結文側の見出し名がこの実出力に含まれることを確認する。
    assert "【R4: 現在タスクの成果物・最新ホワイトボード" in domain_prompt
    assert domain_prompt.count("【R4: 現在タスクの成果物・最新ホワイトボード") >= 2  # 参照文＋実見出し
    assert numeric_prompt.count("【R4: 現在タスクの成果物・最新ホワイトボード") >= 2

    # BL-086/BL-062: agreements_textの実際の見出しは
    # 「【プロジェクトの合意・決定事項・検討状況DB】」（numeric_promptのみが持つ）。
    assert numeric_prompt.count("【プロジェクトの合意・決定事項・検討状況DB】") >= 2  # 参照文2箇所＋実見出し


def test_bl312_no_dangling_backward_reference_words_in_static_top(db_conn, monkeypatch):
    """[退行防止] STATIC-TOPへ移動したはずの指示文に、書き換え漏れの「上記」「下記」が
    残っていないこと（BL-306選定妥当性チェックの元々の判定基準文言等、無関係な既存の
    「上記」は対象外——BL-312で実際に移動した8箇所の書き換え結果のみをピンポイントで確認する）。
    """
    conn, run_id = db_conn
    captured = _capture_prompts(conn, run_id, monkeypatch, "ゴール文", "発言")
    domain_prompt = captured["Detector (Domain Review)"]
    numeric_prompt = captured["Detector"]

    for old_phrase in (
        "上記に🔒が付いている項目",
        "上記【🎯 本質】に照らして",
        "上記のドリフト検知",
        "上記2つ（本質ドリフト・本質充足性）",
        "その基準が上記【🎯 本質】",
        "上記の選定妥当性チェック",
        "上記ホワイトボードの本文から",
    ):
        assert old_phrase not in domain_prompt, f"domain_promptに書き換え漏れの旧表現が残存: {old_phrase!r}"

    for old_phrase in (
        "上記DBで🔒アイコン",
        "その原因が上記DB内の",
        "<上記DBのtopic文字列そのまま>",
        "上記ホワイトボードの本文から",
        "検算必須、下記参照",
    ):
        assert old_phrase not in numeric_prompt, f"promptに書き換え漏れの旧表現が残存: {old_phrase!r}"


def test_bl312_thought_process_audit_stays_after_its_own_backward_references():
    """[非退行] thought_process_auditは自身の内部に「上記のBL-023 criteria_status判定」
    「上記のBL-033機械的検算記録」という後方参照を持つため、criteria_text（BL-023）・
    python_calls_block（BL-033）より後という相対位置を移動していないこと。"""
    src = inspect.getsource(cela_main.call_detector)
    start = src.index("以下の2軸は**完全に独立した別の評価軸**です")
    criteria_idx = src.index("{criteria_text}\\n", start)
    python_calls_idx = src.index('f"{python_calls_block}\\n"', start)
    thought_audit_idx = src.index('f"{thought_process_audit}\\n"', start)
    assert criteria_idx < thought_audit_idx
    assert python_calls_idx < thought_audit_idx


def test_bl312_static_top_dynamic_tail_markers_present_in_source():
    """[配線確認] BL-312のSTATIC-TOP/DYNAMIC-TAILの境界コメントがdomain_prompt・prompt
    それぞれに1回ずつ存在し、STATIC-TOPのコメントがDYNAMIC-TAILのコメントより前にあること。"""
    src = inspect.getsource(cela_main.call_detector)
    assert src.count("=== STATIC-TOP") == 2
    assert src.count("=== DYNAMIC-TAIL") == 2
    domain_static = src.index("=== STATIC-TOP")
    domain_dynamic = src.index("=== DYNAMIC-TAIL")
    assert domain_static < domain_dynamic
    numeric_static = src.index("=== STATIC-TOP", domain_dynamic + 1)
    numeric_dynamic = src.index("=== DYNAMIC-TAIL", numeric_static)
    assert domain_dynamic < numeric_static < numeric_dynamic
