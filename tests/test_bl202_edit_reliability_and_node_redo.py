"""
BL-202: (A) サーバーエラー時のプレースホルダー応答によるラウンド空転の防止、
(B) ホワイトボードedits失敗の連鎖の解消。

log/2026-08-09/2348（run_id=1786246233-0d2e0184、task_1_1が20ラウンド以上Rejectedを
繰り返した回）の実測から、2つの独立した原因が判明した。

(A) `query_AI`がAPIリトライ（delays=[8,16,32,64,128]）を使い切ると
    `"(サーバー高負荷によるAPIエラー)"`という固定文字列を返しており、これがそのまま
    Expertの「発言」としてDetectorへ渡っていた。Detectorは当然「Agentの応答が
    『(サーバー高負荷によるAPIエラー)』のみで指示に一切応えていない」として却下するため、
    Expertが1文字も編集していないのにラウンドと版番号だけが消費されていた（20ラウンド中
    4回以上）。→ delays消尽後、loop_messages（それまでのreasoning・ツール結果の全履歴）を
    保持したままノードをやり直す。

(B) 同ログでedits失敗が58回発生し、その全てが`edits[0]`（＝最初の1件目で失敗し、後続の
    editsは一度も評価されていない）だった。原因は、Expertが節全体＋Detector注釈ブロックを
    巻き込んだ数千字規模のold_textを、read_whiteboard_excerptの窓（「…（中略）」
    「…（以下省略）」で切られている）の外まで記憶で補って再構成していたこと。
    さらに、プロンプト内でBL-076が「注釈行ごと含めて」old_textに入れるよう指示し、
    BL-193が「注釈ブロックを巻き込むな」と指示する**相互矛盾**が同時に存在していた。
    → BL-076側の指示をBL-193と整合させ、「読む→1箇所だけ直す」手順と、
    同一文言が複数箇所にある場合の探し方（見出しではなく文言そのものでkeyword検索）を明示する。

参照: docs/design/back_log/issue_backlog.md BL-202、BL-076、BL-193、BL-122。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# (A) サーバーエラー時のノードやり直し
# ---------------------------------------------------------------------------

def test_query_ai_retry_loop_allows_node_redo_after_delays_exhausted():
    """[BL-202] delays消尽後にプレースホルダーを即返さず、ノードやり直しの分岐を持つこと。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_MAX_NODE_REDO_ON_API_EXHAUSTION" in src
    assert "node_redo_count" in src
    # やり直し分岐が、プレースホルダーを返すelseより手前（elif）にあること
    redo_pos = src.index("elif node_redo_count < _MAX_NODE_REDO_ON_API_EXHAUSTION")
    placeholder_pos = src.index('return "(サーバー高負荷によるAPIエラー)"')
    assert redo_pos < placeholder_pos


def test_query_ai_node_redo_preserves_thought_log_not_reinitialized():
    """[BL-202] やり直しはloop_messages（思考ログ）を保持したまま行う。BL-122で
    loop_messages/iteration_startは関数冒頭（リトライループの外）で初期化される設計に
    なっており、やり直し分岐がそれらを再初期化していないことを確認する。"""
    src = inspect.getsource(cela_main._query_AI_live)
    redo_block = src[src.index("elif node_redo_count < _MAX_NODE_REDO_ON_API_EXHAUSTION"):
                     src.index('return "(サーバー高負荷によるAPIエラー)"')]
    # やり直し分岐の中で巻き戻すのはattemptカウンタのみ
    assert "attempt = 0" in redo_block
    assert "loop_messages = " not in redo_block
    assert "iteration_start = 1" not in redo_block


def test_query_ai_retry_loop_is_bounded():
    """[BL-202] やり直しは無制限ではなく、最終的にはプレースホルダーを返して抜ける。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert 'return "(サーバー高負荷によるAPIエラー)"' in src
    assert "node_redo_count += 1" in src


def test_daily_quota_path_still_bypasses_node_redo():
    """[BL-171] OpenRouter無料枠の日次上限は、やり直しても解消しないため即座に
    DailyQuotaExhaustedErrorへ逃がす経路が維持されていること（BL-202で壊していない）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    quota_pos = src.index("raise DailyQuotaExhaustedError")
    redo_pos = src.index("elif node_redo_count < _MAX_NODE_REDO_ON_API_EXHAUSTION")
    assert quota_pos < redo_pos


# ---------------------------------------------------------------------------
# (B-1) BL-076とBL-193の相互矛盾の解消
# ---------------------------------------------------------------------------

def test_detector_annotation_guidance_no_longer_tells_expert_to_bundle_annotation():
    """[BL-202] 「注釈行ごと含めて」old_textに入れるという旧BL-076の指示は、
    BL-193の「注釈ブロックを巻き込むな」と正面から矛盾しており、2348ログの
    edits失敗58件の直接の引き金だった。この文言が残っていないこと。"""
    src_expert = inspect.getsource(cela_main.call_expert)
    assert "注釈行ごと含めて" not in src_expert
    assert "注釈行ごと該当箇所のみを部分修正" not in src_expert


def test_detector_annotation_guidance_now_requires_separate_edits_entry():
    """[BL-202] 差し戻し時の指示が、本文修正と注釈削除を別々のeditsへ分けるよう
    求めていること（フルsystem_prompt側・light_system_prompt側の両方）。"""
    src_expert = inspect.getsource(cela_main.call_expert)
    # フルsystem_prompt側・light_system_prompt側の2箇所とも修正されていること
    assert src_expert.count("別々のeditsの要素に分けて") >= 2


# ---------------------------------------------------------------------------
# (B-2) 「読む→1箇所ずつ直す」手順と、複数箇所の探し方
# ---------------------------------------------------------------------------

def test_edit_policy_mandates_read_before_edit():
    """[BL-202] read_whiteboard_excerptの使用が「推奨」ではなく必須として書かれていること。"""
    src = inspect.getsource(cela_main._build_task_scope_context)
    assert "BL-202" in src
    assert "**必ず**read_whiteboard_excerpt" in src


def test_edit_policy_mandates_one_place_at_a_time():
    src = inspect.getsource(cela_main._build_task_scope_context)
    assert "**1箇所ずつ**" in src


def test_edit_policy_warns_against_extending_old_text_into_elided_regions():
    """[BL-202] 抜粋の「…（中略）」「…（以下省略）」の先は見えていないため、
    そこを記憶で補ってold_textに含めないよう明示していること（不一致の最大要因）。"""
    src = inspect.getsource(cela_main._build_task_scope_context)
    assert "（中略）" in src and "以下省略" in src


def test_edit_policy_tells_how_to_find_all_occurrences_of_a_contradiction():
    """[BL-202] 複数セクションでの矛盾を指摘された場合、見出しではなく問題の文言自体を
    keywordにして一致件数を確認し、全箇所を直すよう指示していること。"""
    src = inspect.getsource(cela_main._build_task_scope_context)
    assert "問題の文言そのもの" in src
    assert "replace_all=true" in src


# ---------------------------------------------------------------------------
# (B-3) ツールスキーマ・失敗時エラーメッセージ
# ---------------------------------------------------------------------------

def test_write_agreement_edits_schema_mentions_read_first_and_one_at_a_time():
    desc = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]["edits"]["description"]
    assert "BL-202" in desc
    assert "read_whiteboard_excerpt FIRST" in desc
    assert "ONE place per call" in desc


def test_read_whiteboard_excerpt_schema_mentions_window_elision_and_counting():
    desc = cela_main.READ_WHITEBOARD_EXCERPT_TOOL["function"]["description"]
    assert "BL-202" in desc
    assert "（中略）" in desc
    assert "match_count" in desc


def test_apply_text_edits_mismatch_error_gives_actionable_next_steps():
    """[BL-202] 2348ログでは同一ターン内に20回連続で同じ不一致を繰り返した。
    「正確に引用しろ」だけでなく、old_textの実長と具体的な次の手順を返すこと。"""
    content = "あ" * 5000 + "\n### 4B-1. 市街地平坦部\n本文\n" + "い" * 5000
    old_text = "### 4B-1. 市街地平坦部\n本文\n> 🔴 **[Detector指摘 #D-1]**: 存在しない注釈\n"
    merged, err = cela_main._apply_text_edits(content, [{"old_text": old_text, "new_text": "x"}])
    assert merged is None
    assert "次に取るべき手順" in err
    assert str(len(old_text)) in err  # old_textの実文字数を提示している
    assert "read_whiteboard_excerpt" in err
    assert "1箇所ずつ" in err


def test_apply_text_edits_still_succeeds_on_a_small_exact_old_text():
    """[BL-202] 追加した誘導文はエラー経路のみで、正常な部分置換の挙動は変えていない。"""
    content = "あ" * 100 + "\n### 見出し\n結論：通年運行可能。\n" + "い" * 100
    merged, err = cela_main._apply_text_edits(
        content, [{"old_text": "結論：通年運行可能。", "new_text": "結論：通年運行可否は未確定。"}]
    )
    assert err is None
    assert "結論：通年運行可否は未確定。" in merged
    assert "通年運行可能。" not in merged
