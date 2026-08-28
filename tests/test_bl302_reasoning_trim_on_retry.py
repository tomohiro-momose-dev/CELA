"""
BL-302: BL-298の反復検知リトライ発生時、失敗した試行のreasoningがreasoning_parts_all
（iterationをまたいで保持される、R5 F-2.1向けの全体蓄積バッファ）に残り続け、次の
試行のreasoningへそのまま継ぎ足されてしまっていたバグの修正。

ユーザー指摘（原文）: 「再試行時にiterをやり直す際、ループしている思考ログを積み上げて
ないですよね？」——コードを確認したところ、実際に積み上がっていた。`reasoning_parts_all`
はBL-122により`while True`の再試行をまたいで保持される設計だが、BL-297/298の反復ガード
発火（`_bl297_repetition_detected`）で`for chunk in stream:`をbreakする時点で、既に
反復した思考テキストが`reasoning_parts_all.append(delta_reasoning)`で追記済みだった。
このバッファは切り詰められないまま次の再試行のreasoningが続けて追記され、最終的に
`_LAST_REASONING_TEXT = "".join(reasoning_parts_all)`（成功時）へ全体が結合される。

これは`get_last_reasoning_text()`経由で以下へ伝播していた：
- `state["expert_last_reasoning"]` / `state["user_last_reasoning"]`（他ロールへの
  思考ログ提示、R5思考プロセス監査の原資）
- `_detector_thought`（constraint_issue="major"時）
- `_agreement_thought`（write_agreementがRejected時）

つまり、n-gram反復ガードが打ち切った崩壊テキスト（数千〜数万字の繰り返し）が、他の
ロールが読む監査対象の思考ログにそのまま混入する経路が実在した。BL-245（R5思考
プロセス監査の誤爆）と同種の実害を将来引き起こしかねない。

対応: `except _StreamRepetitionRetryError`で再試行する直前に、失敗した試行の開始位置
（`_reasoning_start_idx`、BL-093で導入済みの「このiteration分の切り出し」用インデックス）
まで`reasoning_parts_all`を切り詰める。tools=Noneブランチは`reasoning_parts_all`を
使わない（局所変数`reasoning_parts`が試行ごとに再初期化されるため無関係）ため、
`_reasoning_start_idx`が`None`のままなら切り詰め処理をスキップする。

参照: BL-297/298（発端）、BL-093/BL-122（reasoning_parts_all/iteration_startの設計）、
BL-245（R5思考プロセス監査の誤爆、同種の実害の先例）。
実LLM API呼び出しは伴わない（BL-231/BL-287と同型のモックストリーミングクライアント）。
"""

import json
from types import SimpleNamespace

import cela_main


# ---- モック OpenAI クライアント（ストリーミング互換、tests/test_bl231_loop_guard.pyと同型） ----

def _reasoning_only_chunk(text):
    return SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=text, content=None, tool_calls=None),
        finish_reason=None)])


def _final_answer_chunks(reasoning_text, content_text):
    """reasoningチャンク1つ＋content確定＋tool_callsなし（正常終了）のチャンク列。"""
    chunks = []
    if reasoning_text:
        chunks.append(_reasoning_only_chunk(reasoning_text))
    chunks.append(SimpleNamespace(choices=[SimpleNamespace(
        delta=SimpleNamespace(reasoning=None, content=content_text, tool_calls=None),
        finish_reason="stop")]))
    return chunks


class _FakeStream:
    def __init__(self, chunks):
        self._chunks = chunks

    def __iter__(self):
        return iter(self._chunks)


class _FakeCompletions:
    def __init__(self, factory, counter):
        self._factory = factory
        self._counter = counter

    def create(self, **kwargs):
        self._counter[0] += 1
        n = self._counter[0]
        return _FakeStream(self._factory(n))


class _FakeClient:
    def __init__(self, factory):
        self._counter = [0]
        self.base_url = "http://fake"  # openrouterでないこと（extra_bodyスキップ）
        self.chat = SimpleNamespace(completions=_FakeCompletions(factory, self._counter))


DUMMY_TOOLS = [{"function": {"name": "bl302_test_tool"}}]

# 80文字の反復ngramを4回連続で並べた、確実にBL-297/298を発火させる崩壊テキスト
# （min_repeats=3・ngram_len=80の本番定数に対して十分な長さ・反復回数）。
_COLLAPSED_REASONING = ("Z" * 80) * 4


def _run(factory):
    client = _FakeClient(factory)
    result = cela_main._query_AI_live(
        messages=[{"role": "user", "content": "監査対象"}],
        client=client,
        model="fake",
        label="detector",
        tools=DUMMY_TOOLS,
        light_system_prompt=None,
        state=None,
    )
    return result, client._counter[0]


def test_bl302_failed_retry_reasoning_is_not_included_in_final_reasoning_text():
    """[BL-302本体] 1回目の試行が反復ガードで打ち切られ（BL-298が自動的に同一iterationを
    再試行し）、2回目の試行が正常終了した場合、最終的なreasoning_text
    （get_last_reasoning_text()）には1回目の崩壊テキストが一切含まれず、2回目の
    クリーンなreasoningのみが含まれること。"""
    def factory(n):
        if n == 1:
            # 反復ガードに検知される崩壊テキスト。streamは1チャンクで丸ごと届く想定でも
            # _StreamRepetitionGuard.feed()は正しく検知できる（インクリメンタル方式、BL-298）。
            return [_reasoning_only_chunk(_COLLAPSED_REASONING)]
        # 2回目（BL-298による同一iterationの自動再試行）: クリーンな思考→正常終了。
        return _final_answer_chunks("clean reasoning after retry", "final answer text")

    result, create_calls = _run(factory)

    assert result == "final answer text"
    assert create_calls == 2  # 1回目失敗＋2回目（1回の再試行）で正常終了

    reasoning_text = cela_main.get_last_reasoning_text()
    assert "clean reasoning after retry" in reasoning_text
    assert "Z" * 80 not in reasoning_text, (
        f"1回目の崩壊テキストが混入している: {reasoning_text!r}"
    )


def test_bl302_multiple_failed_retries_do_not_accumulate():
    """[BL-302] 複数回（2回）連続で反復ガードに引っかかった後に3回目で成功した場合も、
    1回目・2回目双方の崩壊テキストが最終reasoning_textに残らないこと。"""
    def factory(n):
        if n in (1, 2):
            return [_reasoning_only_chunk(_COLLAPSED_REASONING)]
        return _final_answer_chunks("clean reasoning after two retries", "final answer text 2")

    result, create_calls = _run(factory)

    assert result == "final answer text 2"
    assert create_calls == 3

    reasoning_text = cela_main.get_last_reasoning_text()
    assert "clean reasoning after two retries" in reasoning_text
    assert "Z" * 80 not in reasoning_text


def test_bl302_reasoning_start_idx_initialized_before_branching():
    """[BL-302配線確認] `_reasoning_start_idx`が関数冒頭（tools=None/toolsループの
    分岐より前）で`None`初期化されており、except節での切り詰めがtools=None分岐からの
    例外（同変数が未設定のまま）でUnboundLocalErrorを起こさないこと。"""
    import inspect
    src = inspect.getsource(cela_main._query_AI_live)
    init_idx = src.index("_reasoning_start_idx: int | None = None")
    del_idx = src.index("del reasoning_parts_all[_reasoning_start_idx:]")
    assert init_idx < del_idx


def test_bl302_trim_guarded_by_none_check():
    """[非退行] 切り詰め処理が`if _reasoning_start_idx is not None:`でガードされており、
    tools=None分岐（reasoning_parts_allを使わない）由来の例外では実行されないこと。"""
    import inspect
    src = inspect.getsource(cela_main._query_AI_live)
    assert "if _reasoning_start_idx is not None:" in src
