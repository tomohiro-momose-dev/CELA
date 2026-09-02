"""
BL-305: BL-304で近接ゲートを導入した後も、log/2026-08-29/1003でDecision Extractor
（`tools=None`でJSON配列を直接出力する、現状唯一のノード）が過検知した修正。

ユーザー指摘（原文）: 「1003,1054ログ まだ、過検知な気がします」

追跡結果、1054（Expert）は真の崩壊（同一チェックリスト段落がほぼ間隔ゼロで3回再出現）
であり正しく検知されていたが、1003（Decision Extractor）はBL-304とは別の原因だった。
Decision Extractorは`extracted_events`というJSON配列を1回のcompletionで出力する。
配列の各要素は`proposed_by`（そのターンでは常に"Agent"）・`phase_id`/`task_id`
（そのターンの現在フェーズ/タスクに固定）・`owned_variable_values`（変数を持たない
要素では共通の"{}"）等、要素間で正当に完全一致するフィールドを複数含む。実測した
実ログの値をそのまま使った再現で共通部分文字列は約150字、content/rationaleも
意図的に一致させた最も敵対的な人工ケースでも239字までしか伸びなかった一方、
BL-297設計当初のコメントが示す通り、これまで観測された全ての真の生成崩壊は
reasoningチャンネルでのみ発生しており、content側の真の反復崩壊は実機で一件も
観測されていない。

ユーザー承認（「1の方が良いでは？？」＝content/reasoning別基準案を選択、
`tools=None`ノードでの無効化案は不採用）を受け、`_StreamRepetitionGuard`の
reasoning用インスタンスはngram_len=80のまま維持し、content用インスタンスのみ
`_TEXT_REPETITION_NGRAM_LEN_CONTENT`（400、実測した敵対的最悪ケース239字に
十分なマージンを持たせつつ、実際の生成崩壊の文字数（実測: 数千〜7万字級）とは
二桁小さい値）を使うよう分離した。

参照: BL-297（設計当初からのcontent側リスク認識）、BL-304（近接ゲート、別の原因）。
実LLM API呼び出しは伴わない。
"""

import cela_main


def _make_event(topic, entry_type="Decision", content="C", rationale="R", owned="{}"):
    """Decision Extractorの実際のプロンプト（cela_main.py内`extracted_events`スキーマ）
    と同型の1要素分のJSON断片を組み立てる。proposed_by/phase_id/task_id/
    defer_to_task_idは実運用上、同一ターンの複数要素間で正当に完全一致する。"""
    return (
        '    {\n'
        '      "action_type": "UPDATE",\n'
        f'      "entry_type": "{entry_type}",\n'
        f'      "target_topic": "{topic}",\n'
        '      "status": "Proposed",\n'
        f'      "content": "{content}",\n'
        f'      "rationale": "{rationale}",\n'
        '      "proposed_by": "Agent",\n'
        '      "phase_id": "",\n'
        '      "task_id": "task_1_1",\n'
        f'      "owned_variable_values": {owned},\n'
        '      "defer_to_task_id": ""\n'
        '    }'
    )


def _realistic_json_array(n=3):
    """実ログ（log/2026-08-29/1003）の実際の値を使った再現（content/rationale/
    target_topicのみ要素ごとに異なる、現実的なケース）。"""
    events = [
        _make_event("推計値: 茅野市免許返納累計(65歳以上)按分",
                     content="長野県実数2138件に基づき茅野市按分約58人へ修正。",
                     rationale="前値は全国合計413,330件を長野県値と誤読していたが、正しい値へ修正。誤読是正のため妥当。",
                     owned='{"license_surrender_count": "約58人"}'),
        _make_event("推計値: 移動弱者推定人数",
                     content="累計ベース25%で約43人へ修正。",
                     rationale="前値は誤読基数による約8,365人だったが、正しい基数により約43人へ修正。計算根拠修正のため妥当。",
                     owned='{"mobility_vulnerable_estimate": "約43人"}'),
        _make_event("task_1_1 定量分析レポート",
                     entry_type="Deliverable",
                     content="",
                     rationale="誤読修正に伴うレポート更新のため",
                     owned="{}"),
    ][:n]
    return ",\n".join(events)


def _adversarial_json_array(n=3):
    """content/rationaleも意図的に一致させ、target_topicのみ相違させる最も敵対的な
    人工ケース（実測で共通部分文字列が最大239字まで伸びることを確認済み）。"""
    events = [_make_event(f"topic{i}") for i in range(n)]
    return ",\n".join(events)


def test_bl305_realistic_decision_extractor_json_not_flagged_by_content_guard():
    """[BL-305本体] 実ログの値を使った現実的な再現が、content用ガード
    （ngram_len=_TEXT_REPETITION_NGRAM_LEN_CONTENT）では誤検知されないこと。"""
    text = _realistic_json_array()
    guard = cela_main._StreamRepetitionGuard(ngram_len=cela_main._TEXT_REPETITION_NGRAM_LEN_CONTENT)
    assert not guard.feed(text)


def test_bl305_adversarial_json_not_flagged_by_content_guard():
    """[BL-305本体] content/rationaleも共通化した最も敵対的な人工ケース
    （実測上限239字）も、content用ガードでは誤検知されないこと。"""
    text = _adversarial_json_array()
    guard = cela_main._StreamRepetitionGuard(ngram_len=cela_main._TEXT_REPETITION_NGRAM_LEN_CONTENT)
    assert not guard.feed(text)


def test_bl305_realistic_json_would_have_been_flagged_by_old_reasoning_ngram_len():
    """[根本原因の再現] 同じ現実的なJSONが、reasoning用の従来ngram_len=80では
    実際に誤検知されていたこと（BL-305適用前の状態の再現、退行防止の対照）。"""
    text = _realistic_json_array()
    guard = cela_main._StreamRepetitionGuard(ngram_len=80)
    assert guard.feed(text)


def test_bl305_genuine_periodic_collapse_still_detected_by_content_guard():
    """[非退行] content側であっても、真の生成崩壊（同一文が間隔ゼロで多数回反復）は
    引き続き検出できること。ngram_lenを400へ伸ばしても、十分な反復回数があれば
    周期性により検出は成立する。"""
    unit = "これは同じ文の繰り返しです。全く進展がありません。"
    text = unit * 30  # 400字のngramウィンドウが複数回一致するだけの反復量を確保
    guard = cela_main._StreamRepetitionGuard(ngram_len=cela_main._TEXT_REPETITION_NGRAM_LEN_CONTENT)
    assert guard.feed(text)


def test_bl305_reasoning_ngram_len_unchanged():
    """[非退行] reasoning側のngram長はBL-305で変更されていないこと
    （真の崩壊はこれまで全てreasoningチャンネルで観測されており、感度を落とす理由がない）。"""
    assert cela_main._TEXT_REPETITION_NGRAM_LEN == 80


def test_bl305_content_ngram_len_has_margin_over_measured_adversarial_worst_case():
    """[定数の健全性] _TEXT_REPETITION_NGRAM_LEN_CONTENTが、実測した敵対的最悪ケース
    （239字）に対して十分なマージンを持っていること。値そのもの（400）に固定するの
    ではなく、実測の安全域から外れるような将来の変更を検知する。"""
    assert cela_main._TEXT_REPETITION_NGRAM_LEN_CONTENT > 239 + 50


def test_bl305_wiring_content_guard_uses_content_constant():
    """[配線確認] _query_AI_liveの2箇所（tools=None分岐・toolsループ分岐）とも、
    content用ガードの生成時に_TEXT_REPETITION_NGRAM_LEN_CONTENTを渡していること。"""
    import inspect
    src = inspect.getsource(cela_main._query_AI_live)
    count = src.count(
        "_bl297_content_guard = _StreamRepetitionGuard(ngram_len=_TEXT_REPETITION_NGRAM_LEN_CONTENT)"
    )
    assert count == 2, f"content用ガードの配線箇所数が想定と異なる: {count}"


def test_bl305_wiring_reasoning_guard_uses_default_ngram_len():
    """[配線確認] reasoning用ガードは引数無し（デフォルトのngram_len=80）で
    生成され続けていること。"""
    import inspect
    src = inspect.getsource(cela_main._query_AI_live)
    count = src.count("_bl297_reasoning_guard = _StreamRepetitionGuard()")
    assert count == 2, f"reasoning用ガードの配線箇所数が想定と異なる: {count}"
