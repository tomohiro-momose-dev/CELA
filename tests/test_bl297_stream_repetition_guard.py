"""
BL-297: 純粋テキスト生成（ツール呼び出しゼロ）に対するn-gram反復の機械的検出・強制打ち切り。

本日発見した4件の生成崩壊（BL-293〜296）は全てプロンプトレベルの対策（打ち切り規定・満足化
規定の追記）に留まっていた。CELAには既にBL-231（iteration間で同一出力が10回連続したら
強制終了）とBL-287（ツール呼び出し引数が3回連続一致で訂正ナッジ→強制終了）という機械的検出が
あるが、いずれもcompletion完了後・iteration間の比較にしか働かず、log/2026-08-28の
0649/1023/1313/1535で実際に発生した「単一completion内でreasoningが9分半・15回以上反復する」
生成崩壊には無力だった（BL-231自身のコメントが既にこの弱点を明記している）。

本BLは、ストリーミング中に届くreasoning/contentのdeltaチャンクを`_StreamRepetitionGuard`で
監視し、ngram_len文字の部分文字列がmin_repeats回以上出現したら、`for chunk in stream:`ループを
強制的にbreakし、既存のfinish_reason=="length"パスと同型のValueErrorを送出して外側のAPIエラー
リトライ（node_redo_count）へ処理を委ねる。

[BL-298] 初版はwindow=3000文字の直近バッファのみを再走査する設計だったが、log/2026-08-28/1919の
実機崩壊（反復周期2159文字）を検出できなかったため、ストリーム全体でngram出現回数を
インクリメンタルに積算する設計に置き換わった。window/check_intervalの引数は廃止され、
`_StreamRepetitionGuard`のコンストラクタは`ngram_len`/`min_repeats`/`max_stream_chars`を取る。
本ファイルのテストはBL-298後の実装を対象とする（BL-298専用の回帰テストは
tests/test_bl298_incremental_repetition_detection.pyを参照）。

参照: docs/design/back_log/BL-297/BL297_basic_design.md、docs/design/back_log/BL-298/、BL-231、BL-287。
実LLM API呼び出しは伴わない（`_StreamRepetitionGuard`単体テストとソース配線確認のみ）。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# ---------------------------------------------------------------------------
# 1. _StreamRepetitionGuard 単体
# ---------------------------------------------------------------------------

_COLLAPSE_PARAGRAPH = (
    "実はこの懸念はtask_1_1の指示そのものの定義の狭さ。Expertがtask_1_1を実行する際に、"
    "指示通りに狭義で計算するか、あるいは非スマホ層も含めて計算するかはExpertの判断です。"
)


def test_detects_real_collapse_style_repetition():
    """実際の崩壊ログ（log/2026-08-28/1313）から採取したパターン: 同一段落が
    ほぼ逐語的に4回以上連続する場合、検出できること。"""
    guard = cela_main._StreamRepetitionGuard()
    collapsed_text = _COLLAPSE_PARAGRAPH * 4
    assert guard.feed(collapsed_text) is True


def test_does_not_false_positive_on_large_varied_json_like_text():
    """大規模な計画JSONに近い構造的テキスト（キー名・書式は共通だが、task_id・説明文等の
    値は毎回異なる）では、n-gram長80文字の設定では誤検知しないこと。"""
    guard = cela_main._StreamRepetitionGuard()
    tasks = []
    descriptions = [
        "人口・高齢化・免許返納動向の定量分析を実施する", "移動弱者層の推計を行う",
        "電話予約必須層の割合を算出する", "運行ルートの設計案を比較検討する",
        "車両台数と充電インフラの整備計画を策定する", "運賃体系の妥当性を検証する",
        "SLA達成率のシミュレーションを実施する", "冬季運行リスクの評価を行う",
        "段階的導入スケジュールを策定する", "実施体制と人員計画をまとめる",
    ]
    for i, desc in enumerate(descriptions, start=1):
        tasks.append(
            f'{{"task_id": "task_{i}_1", "description": "{desc}", '
            f'"acceptance_criteria": ["基準A_{i}", "基準B_{i}", "基準C_{i}"], '
            f'"depends_on": ["task_{i - 1}_1"], "owns_variables": ["var_{i}_a", "var_{i}_b"]}}'
        )
    json_like_text = "[\n" + ",\n".join(tasks) + "\n]"
    assert len(json_like_text) > 300  # check_intervalを跨ぐ量であることの前提確認
    assert guard.feed(json_like_text) is False


def test_below_min_repeats_does_not_trigger():
    """反復回数が閾値(3)未満（2回）では検出しないこと。"""
    guard = cela_main._StreamRepetitionGuard()
    text = _COLLAPSE_PARAGRAPH * 2
    assert guard.feed(text) is False


def test_detects_repetition_split_across_multiple_feed_calls():
    """[BL-298] 実際のストリーミングでは1回のfeed()呼び出しは数文字〜数十文字程度の
    小さなchunkであることが多い。ngram境界がchunk境界をまたいでも（carryにより）
    検出できること。"""
    guard = cela_main._StreamRepetitionGuard()
    collapsed_text = _COLLAPSE_PARAGRAPH * 4
    triggered = False
    for i in range(0, len(collapsed_text), 7):  # 7文字ずつの細切れchunkで供給
        if guard.feed(collapsed_text[i:i + 7]):
            triggered = True
            break
    assert triggered is True


def test_max_stream_chars_caps_tracking_without_crashing():
    """[BL-298] _TEXT_REPETITION_MAX_STREAM_CHARSを超えた分は追跡を打ち切り、
    メモリが無制限に増え続けないこと（例外を出さず安全にFalseを返し続けること）。"""
    guard = cela_main._StreamRepetitionGuard(max_stream_chars=500)
    guard.feed("x" * 10_000)
    assert guard._capped is True
    # capped後は例外を出さず、常にFalseを返す。
    assert guard.feed("y" * 100) is False


def test_feed_ignores_empty_chunk():
    guard = cela_main._StreamRepetitionGuard()
    assert guard.feed("") is False
    assert guard.feed(None) is False


# ---------------------------------------------------------------------------
# 2. _query_AI_live への配線確認
# ---------------------------------------------------------------------------

def test_query_ai_live_wires_repetition_guard_in_both_branches():
    src = inspect.getsource(cela_main._query_AI_live)
    # tools=None分岐・toolsループ分岐それぞれでreasoning用・content用ガードを生成するため計4回。
    assert src.count("_StreamRepetitionGuard()") == 4
    # 各ガードで.feed()が呼ばれる箇所（reasoning用2箇所・content用2箇所）。
    assert src.count(".feed(") == 4


def test_query_ai_live_raises_on_detected_repetition():
    src = inspect.getsource(cela_main._query_AI_live)
    # [BL-298] log/2026-08-28/1950で、finish_reason=="length"用のValueErrorをそのまま
    # 流用した結果、D-009の意図（ValueErrorは外側へ伝播させノードを失敗させる）どおりに
    # 本番ランがクラッシュする実害が発生した。以後は専用の_StreamRepetitionRetryErrorを
    # raiseし、同一関数内のwhile Trueループでその場で捕捉・同一iterationを再試行する。
    assert "_StreamRepetitionRetryError(" in src
    assert "except _StreamRepetitionRetryError as e:" in src
    # reasoning用・content用それぞれで検出時に立てるため、tools=None分岐・toolsループ分岐
    # 合わせて計4箇所（2分岐 x reasoning/content 2種）。
    assert src.count("_bl297_repetition_detected = True") == 4


def test_query_ai_live_logs_bl297_marker():
    src = inspect.getsource(cela_main._query_AI_live)
    assert "BL-297テキストストリーム反復ガード発動" in src
