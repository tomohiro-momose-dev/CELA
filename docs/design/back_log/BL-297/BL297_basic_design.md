# BL-297: 純粋テキスト生成（ツール呼び出しゼロ）に対するn-gram反復の機械的検出・強制打ち切り

## Context

本日発見した4件の生成崩壊（BL-293〜296）は全てプロンプトレベルの対策（打ち切り規定・満足化規定の追記）に留まっている。CELAには既にBL-231（`_recent_combined_hashes`、iteration間で同一出力が`_LOOP_GUARD_REPETITION_WINDOW=10`回連続したら強制終了）とBL-287（`_recent_tool_plan_sigs`、ツール呼び出し引数が`_TOOL_CALL_REPEAT_NUDGE_THRESHOLD=3`回連続一致で訂正ナッジ→強制終了の2段構え）という機械的な検出があるが、いずれも**iteration境界をまたいだ比較**であり、**単一のcompletion（1回のストリーミング応答）内で起きる反復には無力**（`cela_main.py:5890-5892`のBL-231自身のコメントが既に明記）。この弱点への対処として2026-08-15に`frequency_penalty`/`presence_penalty=0.3`（`cela_main.py:5887-5895`）が導入済みだが、これは確率的な抑制に過ぎず、本日観測した0649/1023/1313/1535の4件全てがこの対策が効いた状態で発生している——決定的な機械的バックストップが引き続き欠けている。

Explore調査により、CELAのLLM呼び出しは全て`stream=True`（`cela_main.py:5927`の`_query_AI_live`）で、reasoning（`💭思考`）とcontent（`💬発言`）の2種のdeltaを別々に蓄積・表示していることを確認した。**今回観測した4件の反復は全てreasoning側（`delta.reasoning`）で発生している**（例: 「💭 [Detector (Domain Review)] 思考（iter=2）」ラベル配下）。BL-231/287のチェックは`for chunk in stream:`ループが完全に終わった後（1回のcompletion全体が確定した後）にしか働かないため、9分半・15回以上反復するような単一completion内の暴走を、生成中にリアルタイムで検知して打ち切る機構が存在しない。

本BLは、ストリーミング中のreasoning/contentテキストに対しn-gram反復を機械的に検出し、閾値を超えたらストリームを強制的に打ち切る（`for chunk in stream:`を`break`し、既存の`finish_reason=="length"`パスと同型のValueErrorを送出して外側のAPIエラーリトライへ委ねる）バックストップを追加する。

**誤検知リスクの検討**: content側（最終JSON出力）は、大規模な計画JSON等で構造的に類似したキー・値パターンが複数タスクにわたって繰り返される可能性があるため、n-gram長を短くしすぎると誤検知するおそれがある。80文字程度の長さであれば、実際の値（task_id・説明文等）が毎回異なる限り誤検知しにくく、かつ実際に観測した崩壊（150字前後の段落がほぼ逐語的に反復）は確実に捕捉できる。この長さ・繰り返し回数・監視窓は AGENTS.md §7（重要定数、要承認）に該当するため、以下の設計をレビューの上で承認を求める。

## 設計

### 1. 新規クラス`_StreamRepetitionGuard`（n-gram反復検出）

`_bl231_norm_text`等の既存ヘルパー群（`cela_main.py:5898`付近）の近くに追加する。ストリーム1本（1回のcompletion、reasoning用・content用でそれぞれ1インスタンス）につき1つ生成し、chunkが届くたびに`.feed(text)`を呼ぶ。直近`window`文字だけを保持し、`check_interval`文字增えるごとに、`ngram_len`文字の部分文字列が`min_repeats`回以上出現していないかを調べる。

```python
# [BL-297] AGENTS.md §7 重要定数（要承認）: BL-231のfrequency/presence_penalty=0.3が
# 確率的抑制に過ぎず、log/2026-08-28の0649/1023/1313/1535で単一completion内の
# reasoning反復による生成崩壊が実機で再発したことを受け、決定的な機械的バックストップを追加する。
_TEXT_REPETITION_NGRAM_LEN = 80       # 実際の崩壊（150字前後の段落反復）を確実に捉えつつ、
                                       # JSON出力中の構造的な短い繰り返し（キー名等）を誤検知しない長さ。
_TEXT_REPETITION_MIN_REPEATS = 3      # BL-287のnudge閾値(3)と揃える。
_TEXT_REPETITION_WINDOW = 3000        # 監視する直近テキスト量（文字）。
_TEXT_REPETITION_CHECK_INTERVAL = 300 # 何文字増えるごとに検査するか（毎chunkでの検査を避け負荷を抑制）。


class _StreamRepetitionGuard:
    """[BL-297] ストリーミング中のreasoning/contentテキストに対するn-gram反復の
    機械的検出。BL-231/287はcompletion完了後・iteration間の比較にしか働かないため、
    単一completion内で反復し続ける生成崩壊（log/2026-08-28/1313等、9分半・15回以上
    ツール呼び出しゼロで反復）を検知できなかった。このクラスはchunk受信のたびに
    .feed()を呼ぶことで、生成の途中でも反復を検知できるようにする。
    """
    def __init__(self, ngram_len: int = _TEXT_REPETITION_NGRAM_LEN,
                 min_repeats: int = _TEXT_REPETITION_MIN_REPEATS,
                 window: int = _TEXT_REPETITION_WINDOW,
                 check_interval: int = _TEXT_REPETITION_CHECK_INTERVAL) -> None:
        self._ngram_len = ngram_len
        self._min_repeats = min_repeats
        self._window = window
        self._check_interval = check_interval
        self._buffer = ""
        self._since_last_check = 0

    def feed(self, chunk: str) -> bool:
        """新しいテキストを追加し、反復を検出したらTrueを返す（呼び出し側はストリームをbreakする）。"""
        self._buffer += chunk
        if len(self._buffer) > self._window:
            self._buffer = self._buffer[-self._window:]
        self._since_last_check += len(chunk)
        if self._since_last_check < self._check_interval:
            return False
        self._since_last_check = 0
        return self._has_repetition()

    def _has_repetition(self) -> bool:
        if len(self._buffer) < self._ngram_len * self._min_repeats:
            return False
        seen: dict[str, int] = {}
        for i in range(len(self._buffer) - self._ngram_len + 1):
            gram = self._buffer[i:i + self._ngram_len]
            n = seen.get(gram, 0) + 1
            if n >= self._min_repeats:
                return True
            seen[gram] = n
        return False
```

### 2. `_query_AI_live`の4箇所のstreamingループへ配線

`tools is None`分岐（`cela_main.py:6085-6114`）とtoolsループ分岐（`cela_main.py:6201-6241`）それぞれで、reasoning用・content用の`_StreamRepetitionGuard`を1つずつ生成し、対応する`delta_reasoning`/`delta.content`受信箇所で`.feed()`を呼ぶ。Trueが返ったら、`for chunk in stream:`を`break`し、`finish_reason == "length"`の既存パス（`cela_main.py:6117-6119`および`6245-6247`）と同型の`raise ValueError(...)`を送出して外側の`while True`（APIエラーリトライ、`node_redo_count`）へ処理を委ねる（新しいリトライ経路は作らず、既存の実証済み経路を再利用する）。検出時は`print(f"🛑 [{label}] BL-297テキストストリーム反復ガード発動: ...")`でBL-231/287と同じ体裁のログを残す。

## Critical Files

- `cela_main.py`:
  - `_StreamRepetitionGuard`クラス＋4定数（新規、`_bl231_norm_text`等＝`5898`行付近に追加）
  - `_query_AI_live`の`tools is None`分岐（`6085-6119`行付近）: reasoning/content用ガード2つを配線
  - `_query_AI_live`のtoolsループ分岐（`6201-6247`行付近）: reasoning/content用ガード2つを配線
- `tests/test_bl297_stream_repetition_guard.py`（新規）: `_StreamRepetitionGuard`単体（①実際の崩壊ログから採取した反復パターンで検出できること、②大規模JSON計画に近い構造的テキスト——task_id等の値は毎回変える——で誤検知しないこと、③閾値未満の反復では検出しないこと、④check_intervalによる検査間引きの確認）、`_query_AI_live`への配線確認（`inspect.getsource`でクラス参照・4箇所の`.feed()`呼び出しを確認）、§17.1

## Verification

1. `python -m py_compile cela_main.py`
2. 新規テストファイルを実行し全件成功を確認（特に誤検知しないことの確認テストを重視）
3. 既存の関連テスト（BL-231/287のループガード関連テスト）を再実行し非退行を確認
4. AGENTS.md §17.1（追加箇所を個別にリバートし対応テストが失敗することを確認後、復元）
5. フルオフラインスイートを実行し、既知のBL-269（4件）以外に新規失敗が無いことを確認
6. 実装後、`docs/design/back_log/issue_backlog.md`にBL-297を`done`化し記載、`decision_log.md`へ決定を記録（AGENTS.md §7の重要定数として、ngram_len=80/min_repeats=3/window=3000/check_interval=300の採用理由を明記）
7. これは生成の途中経過（ストリーミングチャンク）に依存する機構であり、オフラインテストではモックのchunk列でしか検証できない。実LLM呼び出しでの効果確認——①実際の崩壊時に生成が早期に打ち切られトークン・時間の浪費が防げるか、②通常の長い正当な生成（大規模JSON計画等）を誤って打ち切らないか——は次回ドライラン待ちとして次回宿題に記録する。
8. 現在一時停止中のrun（`log/2026-08-28/1535`）を`--resume`するか打ち切るかは、この実装とは別にユーザー判断待ち。
