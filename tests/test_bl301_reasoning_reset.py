"""
BL-301: データの定義・解釈を巡る堂々巡りを、observationsへの記録と即時打ち切りで解消する。

log/2026-08-28/2131で、Detector（Domain Review）がNPA月別PDFの「累計」列の定義
（令和7年の年次合計か、2005年の制度開始からの通算累計か）を確定できず、「実際の
データ行を読んで確認しよう」と書きながら一度もその読み取りを実行せずに、ほぼ同じ
不確実性の分析（「NPAの文書は2種類ある…年次PDFの方は…552,381…あれ変だな…」）を
iter=8の単一completion内で繰り返し、BL-297/298のn-gram反復ガードが発火した
（幸いBL-298の改善により約12,000字で早期発火し、以前の1919/2031のような7万字級の
暴走にはならなかったが、3回の再試行も同一の構造的原因で失敗しクラッシュした）。

既存の打ち切り規定はいずれもこのパターンを直接カバーしていなかった：
- BL-295（`_bounded_deliberation_instruction`）: カテゴリカルな結論（trial1/2/3の
  多数決）が取れる二択・三択判断向け。
- BL-296（`_missing_data_estimation_instruction`）: データがどの一次情報源にも
  公表されていない場合の推計手法の満足化向け。
今回はデータ自体は存在し引用もされているが、その定義・解釈自体を確定できずに
同じ検討を繰り返すという、別種のパターンだった。

ユーザー指示（原文）: 「write_issueの前にまずthinkのobservationsに書いてiterを終了し、
思考をリセットするように指示して」。本BLは新規ヘルパー`_reasoning_reset_instruction`を
追加し、`call_detector`のドメイン妥当性レビューパス（`domain_prompt`）へ、BL-188の
根拠検証ブロック・BL-296の推計満足化規定の直後に配線した。write_issueへの即時
エスカレーションではなく、まず最終出力の`observations`フィールドへ作業仮説と残る
不確実性を記録し、その場で応答を打ち切らせる（＝次のiterationは巨大な単一completionの
続きではなく新しい生成として始まる）よう指示する。

参照: log/2026-08-28/2131/log_no_prompt.md、BL-295、BL-296、BL-297/298（発端）。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_reasoning_reset_instruction_mentions_repetition_trigger():
    """[BL-301本体] 「同じ検討を繰り返していることに気づいたら」という発火条件が
    明記されていること。"""
    text = cela_main._reasoning_reset_instruction("observations")
    assert "堂々巡り" in text or "繰り返して" in text


def test_reasoning_reset_instruction_writes_to_given_field_before_write_issue():
    """[BL-301本体] ユーザー指示どおり、①指定フィールド（observations）へ先に書き、
    ②write_issueは今この場では呼ばない（ターンを跨いでも未解決な場合の後段判断）、
    という順序が明記されていること。"""
    text = cela_main._reasoning_reset_instruction("observations")
    assert "observations" in text
    assert "write_issue" in text
    # write_issueは「この場では呼ばず、永続化するより前にまずobservationsへ書く」という
    # 位置づけであること（即時エスカレーションではないことの明記）。
    assert "呼ばない" in text or "この場では" in text


def test_reasoning_reset_instruction_field_name_is_parameterized():
    """[BL-301本体] 呼び出し元ロールごとに異なる最終出力フィールド名（call_detectorは
    'observations'）をパラメータとして受け取れること（他ロールへの将来的な横展開を
    見据えた既存ヘルパー群と同型のパターン）。"""
    text_a = cela_main._reasoning_reset_instruction("observations")
    text_b = cela_main._reasoning_reset_instruction("comment")
    assert "observations" in text_a
    assert "comment" in text_b
    assert "observations" not in text_b


def test_call_detector_wires_reasoning_reset_after_missing_data_instruction():
    """[BL-301配線確認] call_detectorのdomain_promptで、BL-296の推計満足化規定
    （auditor視点）の直後にBL-301の打ち切り規定が続くこと（両方とも「Detectorが
    Expertの主張を審査する際の堂々巡り」を防ぐ目的で隣接して配置されている）。"""
    src = inspect.getsource(cela_main.call_detector)
    anchor = "_missing_data_estimation_instruction(perspective='auditor')"
    reset_call = "_reasoning_reset_instruction('observations')"
    assert anchor in src
    assert reset_call in src
    assert src.index(anchor) < src.index(reset_call)


def test_reasoning_reset_instruction_does_not_collide_with_bl295_or_bl296():
    """[非退行] BL-301のヘルパーが、BL-295/296の既存ヘルパーのテキストと
    衝突・重複しないこと（別々の打ち切り規定として共存できることの確認）。"""
    reset_text = cela_main._reasoning_reset_instruction("observations")
    bounded_text = cela_main._bounded_deliberation_instruction("テスト用の判断")
    estimation_text = cela_main._missing_data_estimation_instruction(perspective="auditor")
    assert "3回多数決" not in reset_text
    assert "堂々巡り" not in bounded_text
    assert "堂々巡り" not in estimation_text
