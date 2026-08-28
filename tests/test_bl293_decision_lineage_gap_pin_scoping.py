"""
BL-293: `decision_lineage_gap_*`エスカレーションが、それを解決できない他ロールへも
「⚠️要対応」として表示され、生成崩壊（thinking無限ループ→max_tokens打ち切り）を招いていた
問題への対応。

実ログ（log/2026-08-28/0649、Detector Domain Reviewパス）で、同じ推論サイクル
「このエスカレーション（User AIのDecision記録漏れ）はドメイン妥当性の話か？いや自分の
職掌ではない…でも要対応なので確認しないと…」を6回以上そのまま繰り返し、max_tokens超過で
出力が打ち切られる崩壊を確認した。複数の異なるモデルで同様の症状が再現していたことから、
モデル固有の弱さではなくプロンプト構造自体の欠陥と判断した。

根本原因: BL-283が、あるロールの`think`内の未確定分岐点をwrite_agreement(Decision)の
記録漏れとして検出すると、1回差し戻し後もなお不足する場合に`issue_log`へ
`severity="major"`（→`status="escalated"`）で自動起票する
（`_record_decision_lineage_gap_issue`、topic=`decision_lineage_gap_{起こしたロール}_{task_id}`）。
この自動起票issueは、既存の`escalation_pin`表示チャネル（BL-103、本来は`escalate_premise_concern`用の
汎用チャネル）へそのまま流れ込み、`call_expert`/`call_detector`（Domain Review）/
`generate_user_utterance`の3箇所すべてへ「⚠️要対応」として一律表示されていた。しかし
`decision_lineage_gap_*`は「記録漏れを起こした当人が次のターンで自己解決すべき」性質の
自己向け催促であり、それ以外のロール（特にDetectorのDomain Review、職掌がドメイン妥当性に
明確に限定されている）が見ても対応不能で、「要対応ラベル」と「自分の職掌外」という
両立しない2つの信号がプロンプト内で衝突し、判定不能な堂々巡りを引き起こしていた。

対応: `_build_escalation_pin_text`へ`caller_role`引数を追加し、`decision_lineage_gap_*`
トピックは呼び出し元自身が起こしたもの（トピック接頭辞が`caller_role`と一致するもの）
のみ残し、他ロール起因分はpinから除外するようにした。他の種類のエスカレーション
（`escalate_premise_concern`由来等）は従来通り無条件で全ロールへ表示される
（フィルタは`decision_lineage_gap_`接頭辞にのみ適用）。3つの呼び出し元
（call_expert/call_detector/generate_user_utterance）それぞれに、自身の役割名を
リテラルで明示的に渡す（`_CURRENT_CALLER_ROLE`グローバルは呼び出し箇所によって
まだ更新前の場合があるため、グローバル読み取りに依存しない）。

[総点検での追加発見] ユーザーから「終わったら、他に役割を超えた矛盾した指示を提示し続ける
パターンが無いかを総点検してください」と依頼を受け、`_get_actionable_escalated_issues`の
他の消費先を洗い出したところ、`_get_forced_escalated_issues_text`（BL-136、User AI向け）が
同じ`decision_lineage_gap_*`issueを、`_build_escalation_pin_text`よりさらに強い
「今回の発言内で必ずwrite_issue(RESOLVE/DEFER)を呼べ」という能動的な行為強制で表示していた
ことが判明した。他ロールが起こした記録漏れをこの経路で見た場合、是正手段
（write_agreement(Decision)を書く）を持たない相手に「必ず解決せよ」を強制することになり、
pin以上に深刻な板挟みを生みかねない。同じ`caller_role`フィルタパターンをこちらにも適用した。

参照: docs/design/back_log/issue_backlog.md BL-293、log/2026-08-28/0649/log_no_prompt.md。
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
    db_path = str(tmp_path / "test_bl293.db")
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


def _seed_decision_lineage_gap_issue(conn, run_id, role: str, task_id: str = "task_1_1") -> None:
    cela_main._write_issue_impl(
        {
            "action_type": "CREATE",
            "topic": f"decision_lineage_gap_{role}_{task_id}",
            "severity": "major",
            "description": f"[BL-283] {role}がthinkに記録した分岐点1件のうち、"
                            "差し戻し後もwrite_agreement(entry_type='Decision')が0件しか確認できませんでした。",
            "phase_id": "phase_1",
            "task_id": task_id,
        },
        conn, run_id, "decision_lineage_gap_auto", "phase_1", task_id,
    )


def _seed_premise_concern_issue(conn, run_id, task_id: str = "task_1_1") -> None:
    """decision_lineage_gap_以外の通常エスカレーション（従来通り全ロールに見えるべき対照群）。"""
    cela_main._write_issue_impl(
        {
            "action_type": "CREATE",
            "topic": "premise_concern_budget_cap",
            "severity": "major",
            "description": "予算上限の前提が本質と矛盾している疑い",
            "phase_id": "phase_1",
            "task_id": task_id,
        },
        conn, run_id, "user", "phase_1", task_id,
    )


# ---------------------------------------------------------------------------
# ソース確認
# ---------------------------------------------------------------------------

def test_build_escalation_pin_text_accepts_caller_role_param():
    sig = inspect.signature(cela_main._build_escalation_pin_text)
    assert "caller_role" in sig.parameters
    assert sig.parameters["caller_role"].default == ""


def test_call_sites_pass_explicit_role_literals():
    for fn, expected_role in (
        (cela_main.call_expert, '"expert"'),
        (cela_main.call_detector, '"detector"'),
        (cela_main.generate_user_utterance, '"user"'),
    ):
        src = inspect.getsource(fn)
        assert "_build_escalation_pin_text" in src
        idx = src.index("_build_escalation_pin_text")
        call_line = src[idx: idx + 250]
        assert f"caller_role={expected_role}" in call_line, (
            f"{fn.__name__}がcaller_role={expected_role}を明示的に渡していません"
        )


def test_filter_only_applies_to_decision_lineage_gap_prefix():
    src = inspect.getsource(cela_main._build_escalation_pin_text)
    assert 'startswith("decision_lineage_gap_")' in src


# ---------------------------------------------------------------------------
# 実行時の挙動確認
# ---------------------------------------------------------------------------

def test_own_role_gap_still_visible(db_conn):
    """自分自身が起こした記録漏れは、自分のcaller_roleでは引き続き見える
    （自己修復を促す唯一の経路のため、消してはいけない）。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "expert")

    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0, caller_role="expert")

    assert "decision_lineage_gap_expert_task_1_1" in pin


def test_other_role_gap_hidden_from_detector(db_conn):
    """【リバート検出】User AIが起こした記録漏れは、Detector（Domain Review）のpinからは
    除外されること。除外ロジックを削除すると失敗する。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "user")

    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0, caller_role="detector")

    assert pin == ""


def test_other_role_gap_hidden_from_expert(db_conn):
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "user")

    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0, caller_role="expert")

    assert pin == ""


def test_no_caller_role_shows_all(db_conn):
    """caller_role未指定（空文字、既定値）の場合は従来通り全件表示するフェイルセーフ。
    新しいパラメータを渡し忘れた既存の呼び出し元があっても挙動が変わらないようにする。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "user")

    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0)  # caller_role省略

    assert "decision_lineage_gap_user_task_1_1" in pin


def test_premise_concern_escalation_visible_to_all_roles_regardless_of_filter(db_conn):
    """[回帰防止] decision_lineage_gap_以外のエスカレーション（escalate_premise_concern等）は
    フィルタの対象外であり、caller_roleを渡しても渡さなくても全ロールに引き続き表示される。"""
    conn, run_id = db_conn
    _seed_premise_concern_issue(conn, run_id)

    for role in ("expert", "detector", "user", ""):
        pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0, caller_role=role)
        assert "premise_concern_budget_cap" in pin


def test_mixed_issues_partial_filter(db_conn):
    """decision_lineage_gap（他ロール起因、除外対象）とpremise_concern（対象外、常に表示）が
    同時に存在する場合、前者だけが正しく除外され後者は残ること。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "user")
    _seed_premise_concern_issue(conn, run_id)

    pin = cela_main._build_escalation_pin_text(conn, run_id, "task_1_1", 0, caller_role="detector")

    assert "decision_lineage_gap_user_task_1_1" not in pin
    assert "premise_concern_budget_cap" in pin


def test_call_expert_and_call_detector_and_generate_user_utterance_source_mentions_bl293():
    combined = (
        inspect.getsource(cela_main._build_escalation_pin_text)
    )
    assert "BL-293" in combined


# ---------------------------------------------------------------------------
# [総点検で発見・追加修正] _get_forced_escalated_issues_text（BL-136）にも同じ穴があった
# ---------------------------------------------------------------------------

def test_get_forced_escalated_issues_text_accepts_caller_role_param():
    sig = inspect.signature(cela_main._get_forced_escalated_issues_text)
    assert "caller_role" in sig.parameters
    assert sig.parameters["caller_role"].default == ""


def test_generate_user_utterance_passes_explicit_user_role_at_both_call_sites():
    src = inspect.getsource(cela_main.generate_user_utterance)
    occurrences = [
        src[m: m + 250]
        for m in (i for i in range(len(src)) if src.startswith("_get_forced_escalated_issues_text(", i))
    ]
    assert len(occurrences) == 2, "generate_user_utterance内の呼び出し箇所数が想定と異なります"
    for call_text in occurrences:
        assert 'caller_role="user"' in call_text


def test_forced_text_own_role_gap_still_visible(db_conn):
    """User AI自身が起こした記録漏れは、引き続き強制解決の対象として表示される。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "user")

    text = cela_main._get_forced_escalated_issues_text(conn, run_id, "task_1_1", 0, caller_role="user")

    assert "decision_lineage_gap_user_task_1_1" in text


def test_forced_text_other_role_gap_hidden_from_user(db_conn):
    """【リバート検出】Expertが起こした記録漏れは、User AI向けの強制解決文からは除外される
    （User AIにはExpertの代わりに決定を記録する術が無いため）。除外ロジックを削除すると失敗する。"""
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "expert")

    text = cela_main._get_forced_escalated_issues_text(conn, run_id, "task_1_1", 0, caller_role="user")

    assert text == ""


def test_forced_text_no_caller_role_shows_all(db_conn):
    conn, run_id = db_conn
    _seed_decision_lineage_gap_issue(conn, run_id, "expert")

    text = cela_main._get_forced_escalated_issues_text(conn, run_id, "task_1_1", 0)  # caller_role省略

    assert "decision_lineage_gap_expert_task_1_1" in text


def test_forced_text_premise_concern_unaffected_by_filter(db_conn):
    conn, run_id = db_conn
    _seed_premise_concern_issue(conn, run_id)

    text = cela_main._get_forced_escalated_issues_text(conn, run_id, "task_1_1", 0, caller_role="user")

    assert "premise_concern_budget_cap" in text
