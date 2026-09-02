"""
BL-298: _StreamRepetitionGuard（BL-297）のwindow方式が持っていた検出漏れの修正。

log/2026-08-28/1919で新たな生成崩壊（task_1_1のExpertが「アプリ操作可能割合」という
公表統計の存在しない値の推計方法を巡ってiter=2の単一completion内で約9分・約7万字
ループする）を発見した際、BL-297で実装済みのはずの`_StreamRepetitionGuard`が一度も
発火していないことが判明した。

実際のログのreasoningストリームを本番同一の定数（ngram_len=80, min_repeats=3,
window=3000, check_interval=300）で再生したところ、同一文が27回・ほぼ正確に2159文字
周期で反復していたにもかかわらず、一度も検出されなかった。原因を計算で特定した：
min_repeats=3回目の出現が直近windowバッファに同時に残るには2周期分＝4318文字が
必要だが、window=3000ではその前に1回目の出現がバッファから追い出されてしまう。
つまりBL-297初版は「反復周期 <= window/(min_repeats-1) = 1500文字」の反復しか
検出できない構造的欠陥を持っていた。BL-297自身のオフラインテストは
`_COLLAPSE_PARAGRAPH * 4`という間隔ゼロの直接連続反復のみを検証しており、
この「周期はあるが間に別の文章を挟む」現実の反復パターンでの弱点を見逃していた
（AGENTS.md §17.2「モックテスト合格は実効性の証拠ではない」の典型例）。

BL-298はwindowによる直近バッファ方式を廃し、chunk到着ごとにngram出現回数を
ストリーム全体でインクリメンタルに積算する方式に置き換えた。本ファイルの前半は、
実際に検出漏れを起こした反復パターン（周期2159文字・27回反復）を再現し、
新しい実装がそれを確実に検出できることを確認する回帰テストである。

【第2の実害・修正（同日、log/2026-08-28/1950）】BL-297初版は検出時に
`raise ValueError("Generation aborted due to detected text repetition (BL-297)")`を
finish_reason=="length"用の既存ValueErrorと同型で送出していたが、そのValueErrorは
D-009の意図的設計（"ValueErrorはAPIError系ではないため下記exceptに飲み込まれず、
原因が伝播する"、`_query_AI_live`のコード自身のコメント）により、`_query_and_parse_
with_retry`層でも`call_detector`層でも一切捕捉されず`run_ai_vs_ai_loop`まで伝播して
本番ラン全体をクラッシュさせた（実機トレースバックで確認）。finish_reason=="length"は
同一promptを再送しても再び切り詰められる可能性が高く「伝播させて失敗を明示する」設計が
妥当だが、n-gram反復はサンプリングの偏りに起因する一過性の事象である可能性が高く、
ユーザーからも「検知したときはそのiterをやり直してほしい」と明示された。そのため
検出時のraiseを専用の`_StreamRepetitionRetryError`に変更し、`_query_AI_live`内の
`while True`ループ自身がその場で捕捉して、BL-122のiteration_start保持機構に乗せた
即時・短期の再試行（最大`_BL298_REPETITION_MAX_REDOS`回、`node_redo_count`が使う
API過負荷用の指数バックオフ/180秒クールダウンとは別予算・別クールダウン）を行うように
修正した。再試行を使い切った場合は、BL-202が教訓とした「プレースホルダー文字列を
下流へ実回答として流してしまう」事故を繰り返さないよう、元の例外をそのまま再raiseする
（`raise`のみ、握りつぶさない）。

参照: docs/design/back_log/BL-298/、BL-297、AGENTS.md §13/§17.1/§17.2。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# log/2026-08-28/1919/log_no_prompt.md（iter=2のreasoningストリーム）から、実際に27回
# 反復した1サイクル分をそのまま採取した（タイムスタンプのみ除去、文面は無加工）。
# 実測長は2159文字で、この1サイクルがBL-297初版のwindow=3000バッファでは
# 検出をすり抜けた実物である。
_ONE_CYCLE = (
    "スマホ所有率（65歳以上）：通信利用動向調査令和7年 利用率ベース 75.6% を採用"
    "（保有と利用の差は小さいと仮定、または利用率を所有の近似とする）。全国値である"
    "ため、茅野市固有の値ではない旨を明記。\n\n"
    "2. アプリ操作可能割合：一次統計なし。代理指標として、スマホ利用率（75.6%）を"
    "「アプリ操作可能の上限」とし、実際の操作可能率は不明。したがって、課題の"
    "「スマホ所有率 − アプリ操作可能割合」の差分は、アプリ操作可能割合をスマホ所有率"
    "以下の不明値とするため、直接算出不可。\n\n"
    "この場合、どうするか。\n\n"
    "現実的な解：\n"
    "- アプリ操作可能割合の代理指標として、スマホ利用率そのものを「アプリ操作可能と"
    "みなせる層」の近似とし、差分（スマホ所有 − アプリ操作可能）を「0」または"
    "「スマホ所有者のうち操作不安層」として扱うのは不適切。\n\n"
    "別の解：\n"
    "- 電話予約必須層の真の規模は「1 - アプリ操作可能割合」である。アプリ操作可能割合の"
    "代理として、スマホ利用率（75.6%）を上限とし、実際はこれより低い。したがって、"
    "電話予約必須層は「少なくとも 1 - 75.6% = 24.4%（スマホ非所有者）」であり、これに"
    "スマホ所有者のうち操作不能層を加えるとさらに大きくなる。\n\n"
    "つまり、電話予約必須層の「下限値」は 24.4%（スマホ非所有者のみ）、「上限値」は "
    "100% - アプリ操作可能率（不明）。\n\n"
    "課題の指示「スマホ所有率 − アプリ操作可能割合」は、アプリ操作可能割合を"
    "「スマホ所有者のうちの割合」ではなく「全体のうちの割合」とすれば、これは"
    "「スマホを持っているがアプリ操作できない層」= 電話予約必須の「追加分」。真の"
    "電話予約必須層 = スマホ非所有者(24.4%) + この差分。\n\n"
    "アプリ操作可能割合が不明なので、この差分も算出できない。\n\n"
    "結論として、私の判断：\n"
    "- アプリ操作可能割合の一次統計が存在しないため、この値を確定できないことを"
    "明示する。\n"
    "- ただし、電話予約必須層の「下限（スマホ非所有者）」は 1 - スマホ所有率 = 24.4% "
    "として算出可能。\n"
    "- そして、Orchestratorの指摘通り、真の電話予約必須層はこれより大きく、"
    "「スマホ所有率 − アプリ操作可能割合」の差分を加えたもの。\n\n"
    "ここで、アプリ操作可能割合の代理指標を何にするか。\n\n"
    "私の提案：アプリ操作可能割合の代理として、スマホ利用率（75.6%）を「アプリ操作"
    "可能の近似上限」とし、実際の操作可能率はこれより低いと仮定。しかし具体的な数値が"
    "出せない。\n\n"
    "より実務的な判断：課題の指示に従い、まずは「スマホ所有率 − アプリ操作可能割合」の"
    "形で差分を提示するが、アプリ操作可能割合の一次統計が存在しないため、これを"
    "「provisional」な推計値（例：スマホ利用率をそのままアプリ操作可能とみなす保守的"
    "仮定、または操作不安層を一定割合差し引く）として扱う。\n\n"
    "いや、待て。もっと慎重に。\n\n"
    "Detectorの懸念③：「アプリ操作可能割合は『通信利用動向調査』に直接の年齢別・操作"
    "能力別統計が無い可能性があり、代理指標（利用率等）での推計前提を明記する必要が"
    "ある」\n\n"
    "つまり、Detectorも「代理指標で推計し、前提を明記する」ことを推奨している。完全に"
    "取得不可能というわけではない。\n\n"
    "では、代理指標をどうするか。\n\n"
    "通信利用動向調査には「インターネットの利用状況」があり、年齢階層別に「インター"
    "ネットを利用している者の割合」がある。また「インターネットの利用機器」として"
    "スマホの利用率がある。\n\n"
    "「アプリ操作可能」の最も近い代理指標は「スマートフォンを利用してインターネットを"
    "利用している者の割合」か、あるいは「スマホ利用率」そのもの。\n\n"
    "私の判断：アプリ操作可能割合の代理指標として、スマホ利用率（65歳以上 75.6%、"
    "令和7年）を採用する。ただし、これは「スマホを使ってインターネット等を利用している"
    "層」であり、実際の「アプリ操作可能」層はこれより狭い（スマホを持っているが操作に"
    "不安がある層を含む）可能性があるため、これを「アプリ操作可能の上限近似」として"
    "扱う。\n\n"
    "そして、課題の「スマホ所有率 − アプリ操作可能割合」の差分は、両者が同じ値"
    "（75.6%）になってしまうため、差分 = 0 となる。これは意味がない。\n\n"
    "ここで、定義の再考：\n"
    "- スマホ所有率：65歳以上のうちスマホを「所有」している割合。通信利用動向調査の"
    "「保有者の割合」は個人ベースで80.5%（全体）、年齢階層別の保有率は明示されていない"
    "が、利用率（75.6% for 65+）に近い。\n"
    "- アプリ操作可能割合：65歳以上のうち、スマホアプリを実際に操作できる割合。\n\n"
    "両者を明確に分けると、所有率 > アプリ操作可能率 となるはず。\n\n"
    "しかし、通信利用動向調査の「保有」と「利用」のデータは、65歳以上については"
    "「利用率 75.6%」しか明確な数値がない（NICTまとめ）。保有率の年齢別内訳はPDFに"
    "あればあるが、スニペットには「個人の保有割合 80.5%（全体）」としか出ていない。\n\n"
    "ここで、私の最終判断：\n\n"
    "1. "
)
assert len(_ONE_CYCLE) == 2159, (
    "log/2026-08-28/1919から採取した実測周期(2159文字)と一致しない。"
    f"実際の長さ={len(_ONE_CYCLE)}"
)


def test_bl297_original_window_math_could_not_have_caught_this_period():
    """[検算] BL-297初版の検出上限はwindow/(min_repeats-1)=3000/2=1500文字だった。
    実機で観測された周期(2159文字)がそれを上回っていたことを明示的に確認する
    （このテストはBL-297初版の欠陥を数値で裏付けるためのものであり、現行実装には依存しない）。"""
    original_window = 3000
    original_min_repeats = 3
    detection_ceiling = original_window / (original_min_repeats - 1)
    real_observed_period = 2159
    assert real_observed_period > detection_ceiling


def test_incremental_guard_detects_real_world_cycle_period():
    """[BL-298] 周期2159文字（間に約2000文字の別文章を挟む）で3回反復する
    現実的なパターンを、新しいインクリメンタル方式の`_StreamRepetitionGuard`が
    検出できること。"""
    guard = cela_main._StreamRepetitionGuard()
    collapsed_text = _ONE_CYCLE * 4
    assert guard.feed(collapsed_text) is True


def test_incremental_guard_detects_when_fed_in_small_streaming_chunks():
    """[BL-298] 実際のAPIストリーミングに近い小さなchunk単位（十数文字ずつ）で
    供給しても、周期の長い反復を検出できること。"""
    guard = cela_main._StreamRepetitionGuard()
    collapsed_text = _ONE_CYCLE * 4
    triggered = False
    for i in range(0, len(collapsed_text), 15):
        if guard.feed(collapsed_text[i:i + 15]):
            triggered = True
            break
    assert triggered is True


def test_incremental_guard_does_not_false_positive_before_third_cycle():
    """反復が2回分（min_repeats未満）しか無い場合は、周期が長くても誤検知しないこと。"""
    guard = cela_main._StreamRepetitionGuard()
    text = _ONE_CYCLE * 2
    assert guard.feed(text) is False


def test_incremental_guard_still_rejects_large_varied_json_like_text():
    """[非退行] BL-297の誤検知回避テスト（構造は共通だが値が毎回異なる大規模JSON）が、
    インクリメンタル方式でも引き続き誤検知しないこと。"""
    guard = cela_main._StreamRepetitionGuard()
    descriptions = [
        "人口・高齢化・免許返納動向の定量分析を実施する", "移動弱者層の推計を行う",
        "電話予約必須層の割合を算出する", "運行ルートの設計案を比較検討する",
        "車両台数と充電インフラの整備計画を策定する", "運賃体系の妥当性を検証する",
        "SLA達成率のシミュレーションを実施する", "冬季運行リスクの評価を行う",
        "段階的導入スケジュールを策定する", "実施体制と人員計画をまとめる",
    ]
    tasks = [
        f'{{"task_id": "task_{i}_1", "description": "{desc}", '
        f'"acceptance_criteria": ["基準A_{i}", "基準B_{i}", "基準C_{i}"], '
        f'"depends_on": ["task_{i - 1}_1"], "owns_variables": ["var_{i}_a", "var_{i}_b"]}}'
        for i, desc in enumerate(descriptions, start=1)
    ]
    json_like_text = "[\n" + ",\n".join(tasks) + "\n]"
    assert guard.feed(json_like_text) is False


def test_query_ai_live_constructs_guard_without_window_or_check_interval_args():
    """[BL-298] _query_AI_liveの配線は無引数コンストラクタ呼び出し
    (`_StreamRepetitionGuard()`)のままであり、廃止したwindow/check_interval引数を
    明示的に渡していないこと（デフォルト値のみに依存する設計であることの確認）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_StreamRepetitionGuard(window=" not in src
    assert "_StreamRepetitionGuard(check_interval=" not in src


# ---------------------------------------------------------------------------
# 3. 検出時の「そのiterationだけをやり直す」再試行（log/2026-08-28/1950の実害修正）
# ---------------------------------------------------------------------------

def test_repetition_no_longer_raises_the_uncaught_value_error():
    """[BL-298] log/2026-08-28/1950で本番ランをクラッシュさせた
    'Generation aborted due to detected text repetition (BL-297)' という文言のValueErrorは
    もう送出されないこと（D-009によりAPIError系exceptに含まれず、
    call_detector等どの層でも捕捉されずに伝播していた）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "Generation aborted due to detected text repetition (BL-297)" not in src


def test_repetition_raises_dedicated_retry_error_class():
    """[BL-298] 検出時は専用の_StreamRepetitionRetryErrorをraiseし、
    同一関数内のwhile Trueループ自身がその場で捕捉すること
    （reasoning用・content用、tools=None分岐・toolsループ分岐の計2箇所）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert src.count("raise _StreamRepetitionRetryError(") == 2
    assert src.count("except _StreamRepetitionRetryError as e:") == 1


def test_retry_error_class_is_a_plain_exception_not_value_error():
    """[BL-298] _StreamRepetitionRetryErrorはfinish_reason=='length'用のValueError
    （D-009により意図的に外側へ伝播させノードを失敗させる設計）とは別系統であり、
    APIError系exceptタプルに誤って巻き込まれないよう素のExceptionから派生すること。"""
    assert issubclass(cela_main._StreamRepetitionRetryError, Exception)
    assert not issubclass(cela_main._StreamRepetitionRetryError, ValueError)


def test_retry_uses_dedicated_budget_separate_from_node_redo_count():
    """[BL-298] 反復検知の再試行はAPI過負荷用のnode_redo_count/delays（指数バックオフ・
    180秒クールダウン）とは別の予算・別のクールダウンを持つこと（サンプリングのばらつきが
    原因であり、インフラ過負荷ではないため）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert "_bl298_repetition_redo_count" in src
    assert "_BL298_REPETITION_MAX_REDOS" in src
    assert "_BL298_REPETITION_REDO_COOLDOWN_SECONDS" in src
    # node_redo_count用の180秒クールダウン(_NODE_REDO_COOLDOWN_SECONDS、_query_AI_live内の
    # ローカル変数のためモジュール属性としては参照不可)を反復検知の再試行に
    # 流用していないこと。モジュールレベル定数の値そのもので確認する。
    assert cela_main._BL298_REPETITION_REDO_COOLDOWN_SECONDS < 180


def test_retry_exhaustion_re_raises_instead_of_returning_placeholder():
    """[BL-298] BL-202は「サーバー高負荷プレースホルダー文字列が下流に実回答として
    誤読された」事故の教訓から生まれた。反復検知の再試行を使い切った場合も、
    同じ過ちを繰り返さずプレースホルダーを返さず、元の例外をそのまま再raiseすること
    （'raise'のみで新しい例外に握り替えたり文字列を返したりしないこと）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    # _StreamRepetitionRetryError用のexcept節は関数内の最後のexcept節（関数末尾）なので、
    # そこから関数終端までを、この例外専用のブロックとして切り出す。
    except_block_start = src.index("except _StreamRepetitionRetryError as e:")
    block = src[except_block_start:]
    assert "raise" in block
    assert "(サーバー高負荷によるAPIエラー)" not in block
