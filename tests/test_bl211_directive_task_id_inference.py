"""
BL-211: BL-139の「advances_to_task_idがnullでも、抽出済みDirectiveのtask_idから遷移意図を
補完する」安全網は、Directiveの構造化フィールド`task_id`が埋まっていることを前提としていた。

`log/2026-08-11/0941`のtask_4_2→task_4_3で、User AIが明示的にtask_4_2を承認しtask_4_3を
指示し、Detectorも criteria_status=[true,true,true] / risk=low で追認したにもかかわらず、
`call_decision_extractor`が

    "advances_to_phase_id": null, "advances_to_task_id": null

を返し、かつ移行意図を表すDirectiveイベントも

    {"entry_type": "Directive", "topic": "task_4_3運賃・住民負担配慮の設計着手指示",
     "phase_id": "", "task_id": "",
     "owned_variable_values": {"対象タスク": "task_4_3", ...}}

と、移行先がtopicとowned_variable_valuesの自然文にしか存在しない形で返された。その結果
BL-139の補完条件（candidate_task_idが非空）を満たさず安全網が二重に外れ、current_task_idが
task_4_2に固定されたままExpertが「実行コンテキストがtask_4_2のまま」と応答し続ける
無限ループに陥った（実ログ中にBL-139の補完メッセージは0件）。

対応：Directiveのtask_idが空の場合に限り、topic/content/rationale/owned_variable_valuesの
自然文からtask_idを推定する第2段フォールバックを追加した。計画に実在するtask_idのみを候補と
し、候補が一意に定まるときだけ補完するフェイルクローズとする（複数タスクへ言及する差し戻し文
での誤った先読み切替を防ぐため）。

参照: docs/design/back_log/issue_backlog.md BL-211、BL-139、BL-210、BL-039。
実LLM API呼び出しは伴わない。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_TASK_ID_TO_PHASE_ID = {
    "task_4_1": "phase_4",
    "task_4_2": "phase_4",
    "task_4_3": "phase_4",
    "task_5_2": "phase_5",
    "task_5_3": "phase_5",
}


# ---------------------------------------------------------------------------
# 1. 推定ヘルパ単体
# ---------------------------------------------------------------------------

def test_infers_task_id_from_topic_and_owned_variable_values():
    """実インシデントの再現：移行先がtopicとowned_variable_valuesにしか存在しないケース。"""
    item = {
        "entry_type": "Directive",
        "topic": "task_4_3運賃・住民負担配慮の設計着手指示",
        "content": "公的な一次情報を確認したうえで、住民負担に配慮した運賃制度を設計する。",
        "rationale": "Userがtask_4_2承認後の新たな作業内容として指示したため。",
        "task_id": "",
        "owned_variable_values": {"対象タスク": "task_4_3"},
    }
    assert cela_main._infer_directive_target_task_ids(item, _TASK_ID_TO_PHASE_ID) == {
        "task_4_2", "task_4_3"
    }


def test_infers_dotted_notation_task_id():
    """[BL-039併存確認] ドット区切り表記（task_4.3）も正規化して認識すること。"""
    item = {"topic": "task_4.3の着手指示", "content": "", "rationale": "",
            "owned_variable_values": {}}
    assert cela_main._infer_directive_target_task_ids(item, _TASK_ID_TO_PHASE_ID) == {"task_4_3"}


def test_ignores_task_ids_not_present_in_plan():
    """[CONSTRAINT] 計画に実在しないtask_idは候補にしないこと（架空タスクへの遷移防止）。"""
    item = {"topic": "task_9_9の着手指示", "content": "", "rationale": "",
            "owned_variable_values": {}}
    assert cela_main._infer_directive_target_task_ids(item, _TASK_ID_TO_PHASE_ID) == set()


# ---------------------------------------------------------------------------
# 2. 補完ロジック本体（decision_extractor_nodeの該当ブロックを再現）
# ---------------------------------------------------------------------------

def _apply_fallback(transition: dict, extracted_items: list[dict], departing_task_id: str,
                    target_role: str = "user") -> dict:
    """decision_extractor_node内のBL-139/BL-211補完ブロックと同一の条件分岐。
    node全体はLLM呼び出しとDBを伴うため、補完ロジックのみを同型で検証する。"""
    if target_role == "user" and not transition.get("advances_to_task_id"):
        fallback_candidates: set[str] = set()
        for item in extracted_items:
            if item.get("entry_type") != "Directive" or item.get("status") == "Deferred":
                continue
            candidate_task_id = item.get("task_id")
            if (candidate_task_id and candidate_task_id in _TASK_ID_TO_PHASE_ID
                    and candidate_task_id != departing_task_id):
                transition["advances_to_task_id"] = candidate_task_id
                transition["advances_to_phase_id"] = _TASK_ID_TO_PHASE_ID[candidate_task_id]
                break
            if not candidate_task_id:
                fallback_candidates |= {
                    t for t in cela_main._infer_directive_target_task_ids(
                        item, _TASK_ID_TO_PHASE_ID)
                    if t != departing_task_id
                }
        else:
            if len(fallback_candidates) == 1:
                inferred = fallback_candidates.pop()
                transition["advances_to_task_id"] = inferred
                transition["advances_to_phase_id"] = _TASK_ID_TO_PHASE_ID[inferred]
    return transition


def test_incident_reproduction_empty_task_id_directive_now_resolves():
    """実インシデント再現：task_4_2離脱中、Directiveのtask_idが空でもtask_4_3へ補完されること。
    離脱元task_4_2は候補から除外されるため、候補は一意にtask_4_3へ定まる。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Decision", "status": "Approved", "topic": "task_4_2修正版の承認",
         "task_id": "task_4_2", "owned_variable_values": {}},
        {"entry_type": "Directive", "status": "Proposed",
         "topic": "task_4_3運賃・住民負担配慮の設計着手指示",
         "content": "住民負担に配慮した運賃制度、減免、運賃記録を設計する。",
         "rationale": "Userがtask_4_2承認後の作業として明示指示したため。",
         "phase_id": "", "task_id": "",
         "owned_variable_values": {"対象タスク": "task_4_3"}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] == "task_4_3", "BL-211の自然文フォールバックが機能していない"
    assert result["advances_to_phase_id"] == "phase_4"


def test_multiple_candidates_are_not_completed_failclosed():
    """[フェイルクローズ] 自然文から複数の移行先候補が出た場合は補完しないこと
    （誤った先読み切替の防止）。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Directive", "status": "Proposed",
         "topic": "引継ぎ指示",
         "content": "運賃はtask_5_2へ、感度分析はtask_5_3へ引き継ぐこと。",
         "rationale": "", "task_id": "", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] is None, "候補が複数あるのに補完してしまった"


def test_departing_task_only_mention_does_not_trigger_transition():
    """離脱元task_idにしか言及していないDirectiveでは、自己遷移を起こさないこと。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Directive", "status": "Proposed",
         "topic": "task_4_2成果物の限定修正指示",
         "content": "task_4_2の6項目を修正すること。", "rationale": "",
         "task_id": "", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] is None


def test_node_actually_wires_the_fallback():
    """`_apply_fallback`はnode内の分岐を再現した写しであるため、本体側の配線が失われても
    上記テストは通ってしまう。実際に`decision_extractor_node`が推定ヘルパを呼んでいることを
    ソースレベルで固定する（BL-209等で用いたプロンプト配置検証と同型の防護）。"""
    import inspect
    src = inspect.getsource(cela_main.decision_extractor_node)
    assert "_infer_directive_target_task_ids" in src, (
        "decision_extractor_nodeからBL-211のフォールバック呼び出しが失われている"
    )
    assert "BL-211" in src


# ---------------------------------------------------------------------------
# 3. 非退行確認
# ---------------------------------------------------------------------------

def test_bl139_structured_task_id_still_takes_precedence():
    """[非退行] Directiveのtask_idが埋まっている従来のケースでは、BL-139の第1段補完が
    そのまま働き、自然文推定へは降りないこと。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Directive", "status": "Proposed", "topic": "task_4_3着手指示",
         "content": "", "rationale": "", "task_id": "task_4_3", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] == "task_4_3"
    assert result["advances_to_phase_id"] == "phase_4"


def test_deferred_directive_still_excluded():
    """[非退行] status='Deferred'（BL-082の明示的先送り）は「今は移行しない」意思表示のため、
    自然文推定の対象にもしないこと。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Directive", "status": "Deferred", "topic": "task_4_3への先送り",
         "content": "", "rationale": "", "task_id": "", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] is None


def test_explicit_advances_to_task_id_is_never_overwritten():
    """[非退行] LLMがadvances_to_task_idを明示している場合、補完ロジックは一切介入しないこと。"""
    transition = {"advances_to_phase_id": "phase_4", "advances_to_task_id": "task_4_3"}
    items = [
        {"entry_type": "Directive", "status": "Proposed", "topic": "task_5_2引継ぎ",
         "content": "", "rationale": "", "task_id": "", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2")

    assert result["advances_to_task_id"] == "task_4_3"


def test_expert_role_is_not_subject_to_completion():
    """[非退行] BL-139/BL-211の補完はtarget_role='user'のみが対象であること
    （Expert側の抽出で勝手にタスクが進まないこと）。"""
    transition = {"advances_to_phase_id": None, "advances_to_task_id": None}
    items = [
        {"entry_type": "Directive", "status": "Proposed", "topic": "task_4_3着手指示",
         "content": "", "rationale": "", "task_id": "", "owned_variable_values": {}},
    ]
    result = _apply_fallback(transition, items, departing_task_id="task_4_2",
                             target_role="expert")

    assert result["advances_to_task_id"] is None
