"""
BL-304: BL-298の`_StreamRepetitionGuard`（ストリーム全体でngram出現回数を無制限に
累積カウントする方式）は近接性の制約を完全に撤廃していたため、log/2026-08-28の
2031・2049・2208で過検知（誤検知）を起こしていたことが実測で判明した修正。

ユーザー指摘（原文）: 「ngream検知ですが、ログを見た感じでは完全なループというより、
思考過程を過検知しているようにも見えます」

実際に該当ログを追跡した結果:
- 2208: 発火直前のreasoningを読むと、人口按分の妥当性・「6割」仮定の吟味・移動弱者推計
  など多角的に検討する正当な長い思考だった。ただし「escalation says the correct
  values are 65+ : 2,138, 75+ : 2,076」という80字超のアンカー文を、話の節目ごとに
  3回言い直していた（文字オフセット5,571/9,183/14,021、間隔3,612字・4,838字）。
  この間の本文はいずれも別内容（人口比較、仮定の吟味、次アクションの計画）。
- 2031・2049も同型のパターンだった（同じ「escalation says...」アンカー文を長い
  正当な検討の節目ごとに言い直していただけ）。
- 対照的に、既に真の生成崩壊と確認済みの1919（BL-298の発端、周期2159字）・2131
  （同一パラグラフがほぼ間隔ゼロで再出現）は、アンカー文の再出現が明確に近接していた。

各ログの実際のreasoning（iter初回試行の生テキスト、タイムスタンプ除去）をBL-298の
旧実装（近接性なし・純累積カウント）と本BL-304のプロトタイプ実装（近接ゲート付き）の
両方に通し、「新実装がその値以上のmax_gapで初めて発火する最小値」を計測した
（scratchpadのbl304_calibrate.pyで実測、値はcela_main.py内の_TEXT_REPETITION_MAX_GAPの
コメントにも記録）:
  - 1919（真の崩壊）: max_gap=2200で発火
  - 2131（真の崩壊）: max_gap=3400で発火
  - 2031（誤検知）  : max_gap=10000でも不発
  - 2049（誤検知）  : max_gap=6000で初めて発火
  - 2208（誤検知）  : max_gap=5000で初めて発火
真の崩壊を捉える下限(3400)と誤検知が始まる上限(5000)の間に安全域があるため、
中間の4000を採用した。

対応: `_StreamRepetitionGuard`に、各ngramの直近出現位置を記録し、次の出現までの
間隔が`_TEXT_REPETITION_MAX_GAP`（4000文字）を超えたら「連続反復」のカウントを
1にリセットする近接ゲートを追加した。間隔内で連続した出現のみをmin_repeats(3)回まで
数える。

本ファイルは実際のログ全文（数万字）を埋め込む代わりに、実測した間隔の値を使って
構造的に同型の合成テキスト（アンカーngram＋一意なfiller文）を組み立て、ガード単体の
挙動として検証する。実ログでの再現確認はscratchpadのcalibrationスクリプトで別途
実施済み（本ファイルはそれをテストとして固定化したもの）。

参照: BL-297/BL-298（発端）、AGENTS.md §17.1（revert検証済み）、
AGENTS.md §5.1（数値は必ずコード実行で算出、本docstringの数値もcalibrationスクリプト
の実行結果をそのまま転記）。実LLM API呼び出しは伴わない。
"""

import random

import cela_main


def _unique_filler(length: int, seed: int) -> str:
    """反復ngramと衝突しない、指定文字数の一意な合成テキストを生成する。"""
    rng = random.Random(seed)
    alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ 0123456789,."
    return "".join(rng.choice(alphabet) for _ in range(length))


_ANCHOR = "Q" * 80  # 反復検知対象の80字ngram（_TEXT_REPETITION_NGRAM_LENと同じ長さ）


def _build_stream(gaps):
    """アンカーngramを、指定した間隔（アンカー開始位置どうしの絶対距離＝ガードが
    `abs_pos - last`として比較する値）で並べた合成ストリームを返す。gapsは
    [アンカー1→2の開始位置間隔, アンカー2→3の開始位置間隔, ...]。各間隔は
    アンカー長（80）を差し引いた分だけ一意なfillerで埋める。"""
    parts = [_ANCHOR]
    for i, gap in enumerate(gaps):
        filler_len = gap - len(_ANCHOR)
        assert filler_len >= 0, "gapはアンカー長(80)以上である必要がある"
        parts.append(_unique_filler(filler_len, seed=1000 + i))
        parts.append(_ANCHOR)
    return "".join(parts)


def _feed_whole(guard, text, chunk_size=997):
    """任意のchunk境界でも検出結果が変わらないことを確認するため、半端なサイズで分割して
    feed()する（carryの境界処理を実運用に近い形で経由させる）。"""
    triggered = False
    for i in range(0, len(text), chunk_size):
        if guard.feed(text[i:i + chunk_size]):
            triggered = True
    return triggered


def test_bl304_tight_periodic_repeat_still_detected():
    """[非退行] 間隔ゼロの直接連続反復（従来のBL-231/298テストと同型）は、
    近接ゲート導入後も引き続き検出できること。"""
    text = _ANCHOR * 4
    guard = cela_main._StreamRepetitionGuard()
    assert _feed_whole(guard, text)


def test_bl304_1919_style_period_still_detected():
    """[非退行] BL-298の発端である1919の実測周期2159字（アンカー文の間隔）は、
    デフォルトのmax_gap=4000より十分小さいため、引き続き検出できること。"""
    text = _build_stream(gaps=[2159, 2159])
    guard = cela_main._StreamRepetitionGuard()
    assert _feed_whole(guard, text)


def test_bl304_2131_style_gap_still_detected():
    """[非退行] 真の崩壊と確認済みの2131で実測した最小検出間隔3400字は、
    デフォルトのmax_gap=4000以内のため、引き続き検出できること。"""
    text = _build_stream(gaps=[3400, 3400])
    guard = cela_main._StreamRepetitionGuard()
    assert _feed_whole(guard, text)


def test_bl304_2208_style_sparse_restatement_not_detected():
    """[BL-304本体] 過検知と確認済みの2208で実測した間隔（3,612字・4,838字）を
    模した合成ストリームは、デフォルトのmax_gap=4000ではどちらの間隔もmax_gapを
    超えるため、連続反復とみなされず誤検知しないこと。"""
    text = _build_stream(gaps=[3612, 4838])
    guard = cela_main._StreamRepetitionGuard()
    assert not _feed_whole(guard, text)


def test_bl304_2049_style_sparse_restatement_not_detected():
    """[BL-304本体] 過検知と確認済みの2049は、実測でmax_gap=6000にならないと
    発火しなかった（＝5000台までは誤検知しない）。デフォルトのmax_gap=4000で
    誤検知しないことを、同程度の間隔を持つ合成ストリームで確認する。"""
    text = _build_stream(gaps=[5900, 5900])
    guard = cela_main._StreamRepetitionGuard()
    assert not _feed_whole(guard, text)


def test_bl304_gap_exactly_at_threshold_counts_as_continuous():
    """[境界値] 間隔がmax_gapちょうど（境界含む、<=判定）の場合は連続反復とみなし、
    3回連続で検出されること。"""
    max_gap = cela_main._TEXT_REPETITION_MAX_GAP
    text = _build_stream(gaps=[max_gap, max_gap])
    guard = cela_main._StreamRepetitionGuard()
    assert _feed_whole(guard, text)


def test_bl304_gap_one_over_threshold_resets_streak():
    """[境界値] 間隔がmax_gapを1字でも超えると連続反復カウント(streak)が1にリセット
    され、その後さらに2回（リセット後のoccurrence込みで合計3回）近接して出現しない
    限り検出されないこと。

    occurrence列: pos0(streak=1) → +100→pos100(streak=2, 近接) →
    +max_gap+1→pos(4101)(streak=1へリセット、間隔超過) → +100→(streak=2, 近接) →
    +100→(streak=3, 近接、ここで検出)。
    リセット直後の2回（streak=2まで）では届かないことと、3回目でようやく届くことの
    両方を確認する。"""
    max_gap = cela_main._TEXT_REPETITION_MAX_GAP
    # リセット後がstreak=2止まり（4occurrence構成）ではmin_repeats=3に届かず未検出のはず。
    text_not_yet = _build_stream(gaps=[100, max_gap + 1, 100])
    guard = cela_main._StreamRepetitionGuard()
    assert not _feed_whole(guard, text_not_yet)

    # リセット後にさらに1回近接させ5occurrence構成にすれば、streakが2→3に届き検出されるはず。
    text_triggers = _build_stream(gaps=[100, max_gap + 1, 100, 100])
    guard2 = cela_main._StreamRepetitionGuard()
    assert _feed_whole(guard2, text_triggers)


def test_bl304_max_gap_constant_within_calibrated_safe_window():
    """[定数の健全性] 実測した安全域（真の崩壊を捉える下限3400 < 安全域 < 誤検知が
    始まる上限5000）の範囲内に_TEXT_REPETITION_MAX_GAPが収まっていること。
    値そのもの（4000）に固定するのではなく、実測で確認済みの安全域から外れる
    ような将来の変更を検知する。"""
    assert 3400 < cela_main._TEXT_REPETITION_MAX_GAP < 5000


def test_bl304_wiring_guard_constructor_uses_max_gap_constant():
    """[配線確認] _StreamRepetitionGuardのデフォルト引数が_TEXT_REPETITION_MAX_GAPを
    参照しており、_query_AI_live側の呼び出し（引数省略）がこの定数を使うこと。"""
    import inspect
    sig = inspect.signature(cela_main._StreamRepetitionGuard.__init__)
    default = sig.parameters["max_gap"].default
    assert default == cela_main._TEXT_REPETITION_MAX_GAP
