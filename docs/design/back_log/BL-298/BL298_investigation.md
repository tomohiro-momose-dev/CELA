# BL-298 調査・設計記録: BL-297のwindow方式検出漏れの再設計と、検出時クラッシュの修正

日付: 2026-08-28
関連: BL-297, BL-122, BL-202, BL-231, BL-287, D-253

## 1. 経緯

BL-297（`_StreamRepetitionGuard`、ストリーミング中のreasoning/contentテキストに対する
n-gram反復の機械的検出）を実装・テスト・ドキュメント化した直後、同日のドライラン継続中に
2つの実害が連続して発見された。

1. **検出漏れ**: `log/2026-08-28/1919`で新たな生成崩壊が発生したが、`_StreamRepetitionGuard`が
   一度も発火しなかった。
2. **検出直後のクラッシュ**: 検出漏れを再設計で修正した直後の初回本番発火（`log/2026-08-28/1950`）で、
   ユーザーから「過検知です」との指摘を受けた。さらにその直後、同一の検出パターンが実際に
   本番ラン全体をクラッシュさせるトレースバックが提示された。

いずれもBL-297実装から数時間以内、同一のドライラン（`run_id=1787890406-1e73a89d`の再開）で
連続して発覚した。

## 2. 実害①: 検出漏れ（log/2026-08-28/1919）

### 2.1 症状

Expertがtask_1_1（茅野市の移動弱者推計）で、公式統計に存在しない「アプリ操作可能割合」という
値の推計方法を巡り、iter=2の単一completion内で約9分・約7万字にわたり同じ結論の言い換えを
繰り返した（[19:19:29]〜[19:28:23]）。BL-296で追加した`_missing_data_estimation_instruction`
（推計方法論の満足化規定）は`log_with_prompt.md`で確認した限りこの呼び出しのプロンプトに
実際に含まれていたが、それでも発生した——プロンプトによる助言は確率的にしか効かないことの
実例である。

より重大な問題として、BL-297で実装したばかりの`_StreamRepetitionGuard`が一度も発火しなかった。
幸い、このケースはモデルが自力でループを抜け出し、その後iter=3〜7で正常に前進（web_search→
python_replで検算→根拠・却下案付きでwrite_agreementにDecisionを2件登録）した。実害は
「約9分の生成の無駄」に留まったが、BL-297が本来検出すべきはずのパターンだった。

### 2.2 根本原因（実測で確認）

該当区間のreasoningストリーム（タイムスタンプのみ除去、文面は無加工）を、本番同一の定数
（ngram_len=80, min_repeats=3, window=3000, check_interval=300）で実際の
`_StreamRepetitionGuard`に再生させたところ、69,864文字全体を通じて一度も検出されなかった。

原因を数値で特定した。同一文（「スマホ所有率（65歳以上）：通信利用動向調査令和7年 利用率
ベース 75.6% を採用（保有と利用の差は小さいと仮定、または利用率を所有の近似とする）。全国
値であるため、茅野市固有の値ではない旨を明記。」）が **27回**、ほぼ正確に **2159文字周期**
（最大誤差1文字）で反復していた。

```
occurrences: 27
positions: [5052, 7211, 9370, 11529, ...]
gaps: [2159, 2159, 2159, 2159, ...]  # ほぼ全て2159、一部2158
```

min_repeats=3を満たすには、同じ80文字ngramの3回目の出現がバッファに同時に残る必要があり、
そのためには最低でも2周期分＝4318文字がwindow内に同時に存在しなければならない。しかし
window=3000のため、3回目が来る前に必ず1回目がバッファから追い出されてしまう構造になって
いた。つまりこの実装は「反復周期 ≤ window/(min_repeats-1) = 3000/2 = 1500文字」の反復しか
検出できない構造的欠陥を持っていた。

BL-297のオフラインテスト（`test_bl297_stream_repetition_guard.py`）は
`_COLLAPSE_PARAGRAPH * 4`という**間隔ゼロの直接連続反復**のみを検証しており、この「周期は
あるが間に別の文章（言い換えや検討の分岐）を挟む」現実の反復パターンでの弱点を見逃していた。
AGENTS.md §17.2「モックテスト合格は実効性の証拠ではない」の典型例である。

### 2.3 対応（ユーザー承認済み: 「進めてください」）

`_StreamRepetitionGuard`の内部実装を、window文字数だけを保持し`check_interval`ごとに
バッファ全体を再走査する方式から、chunk到着ごとにngram出現回数をストリーム全体で
インクリメンタルに積算する方式へ置き換えた。

```python
class _StreamRepetitionGuard:
    def __init__(self, ngram_len=..., min_repeats=..., max_stream_chars=...):
        self._counts: dict[str, int] = {}
        self._carry = ""       # chunk境界をまたぐngram形成用の直近(ngram_len-1)文字
        self._total_chars = 0
        self._capped = False

    def feed(self, chunk: str) -> bool:
        if not chunk or self._capped:
            return False
        self._total_chars += len(chunk)
        if self._total_chars > self._max_stream_chars:
            self._capped = True   # メモリ安全弁のみ、検出感度には影響しない
            return False
        scan_text = self._carry + chunk
        triggered = False
        for i in range(len(scan_text) - self._ngram_len + 1):
            gram = scan_text[i:i + self._ngram_len]
            n = self._counts.get(gram, 0) + 1
            self._counts[gram] = n
            if n >= self._min_repeats:
                triggered = True
        self._carry = scan_text[-(self._ngram_len - 1):]
        return triggered
```

1回の`feed()`呼び出しのコストは新しく届いたchunk長にのみ比例し、過去分の再走査は発生しない
（旧実装のO(window×検査回数)ではなくO(総文字数×ngram_len)の1パス）。反復周期の長さに関係なく
検出できるようになった。

`window`/`check_interval`の代わりに、病的に長い単一completion（実機最大観測値、約7万字を
大きく上回るケース）に対するメモリ安全弁として新定数`_TEXT_REPETITION_MAX_STREAM_CHARS =
200_000`を追加した（AGENTS.md §7重要定数、ユーザー承認値）。これは検出用の窓ではなく、
上限を超えた場合に追跡を打ち切るだけの措置である。

`_query_AI_live`側の配線（`_StreamRepetitionGuard()`の無引数呼び出し4箇所、`.feed()`呼び出し
4箇所）はコンストラクタのデフォルト引数のみに依存しているため変更不要だった。

### 2.4 回帰テスト

`tests/test_bl298_incremental_repetition_detection.py`に、`log/2026-08-28/1919`から採取した
実測2159文字の1サイクル分をそのまま埋め込み（タイムスタンプのみ除去、文面は無加工、
`assert len(_ONE_CYCLE) == 2159`で採取の正確性を保証）、新実装が確実に検出することを確認する
回帰テストを追加した。AGENTS.md §17.1に従い、旧実装（window方式）へ一時的に戻して該当テストが
失敗することを確認した後、新実装へ復元した。

## 3. 実害②: 検出直後の本番クラッシュ（log/2026-08-28/1950）

### 3.1 症状（過検知の指摘）

再設計後の初回本番発火が`log/2026-08-28/1950`で観測された。ユーザーが該当箇所をレビューし
「過検知です」と指摘した。

該当箇所はDetector（Domain Review）が、NPA（警察庁）PDFの都道府県略称一覧（「北海道(計),
札幌, 函館, 旭川, ..., 潟, 新, 梨, 山, 野, 長, 岡, 静, 山, 富, 川, 石, 井, 福, 阜, 岐, 知, 愛,
重, 三, 賀, 滋, 都, 京, 阪, 大, 庫, ...」という低エントロピーな一文字略称の羅列）から、
「長野」に対応する列を特定するため、略称と都道府県名の対応関係を3回にわたり再確認していた
（[19:52:07]〜[19:52:22]）。

実際のreasoningストリームを再生して検証したところ、min_repeats=3を満たした80文字ngramは
「潟, 新, 梨, 山, 野, 長, 岡, 静, 山, 富, 川, 石, 井, 福, 阜, 岐, 知, 愛, 重, 三, 賀, 滋, 都,
京, 阪, 大, 庫」を含む一群で、3回の出現は以下だった。

1. [19:52:12] 初回の一覧確認（「So the order is:」）
2. [19:52:20]〜「Hmm, let me re-map. The prefecture list:」——1回目を疑い再確認
3. [19:52:20]直後——2回目の途中で強制打ち切り（3回目の出現の途中）

すなわちこれは、外部から取り込んだ低エントロピーな参照データ（多くの都道府県が同じ1文字
略称を共有するため、80文字窓が偶然一致しやすい）を、モデルが対応関係の確認のため複数回
参照し直していた**進行中の正当な分析作業**であり、BL-293〜297が対象とした「結論を変えずに
同じ主張を無為に繰り返す崩壊」とは性質が異なる。ユーザーの「過検知です」という評価は、
実測データと整合する。

### 3.2 症状（クラッシュ）

上記の過検知指摘の直後、ユーザーから実際のPythonトレースバックが提示された。

```
File "cela_main.py", line 18079, in run_ai_vs_ai_loop
  for step_state in app.stream(...):
...
File "cela_main.py", line 15928, in detector_node
  result = call_detector(...)
File "cela_main.py", line 12628, in call_detector
  domain_parsed, domain_parse_failed = _query_and_parse_with_retry(...)
File "cela_main.py", line 6793, in _query_and_parse_with_retry
  res = query_AI(...)
File "cela_main.py", line 5780, in query_AI
  content = _query_AI_live(...)
File "cela_main.py", line 6339, in _query_AI_live
  raise ValueError("Generation aborted due to detected text repetition (BL-297)")
ValueError: Generation aborted due to detected text repetition (BL-297)
```

BL-297検出が`run_ai_vs_ai_loop`全体を未捕捉例外でクラッシュさせていた。

### 3.3 根本原因（コードで確認）

BL-297実装時、検出時のraiseは既存の`finish_reason=="length"`用ValueErrorと**同型**で
実装していた（「既存のfinish_reason=="length"パスと同型のValueErrorを送出して外側のAPI
エラーリトライへ委ねる」という設計意図だった）。

しかしそのValueErrorは、`_query_AI_live`自身のコードコメント（D-009、BL-297実装当時の
既存コード）が明記する通り、意図的に外側の`except (APIError, APIConnectionError,
RateLimitError, APITimeoutError, json.JSONDecodeError, httpx.RemoteProtocolError,
httpx.TimeoutException, httpx.ReadError)`には含まれない：

> ValueErrorはAPIError系ではないため下記exceptに飲み込まれず、原因が伝播する。

つまり`finish_reason=="length"`のValueErrorは、**そもそも_query_AI_live内で捕捉・
リトライされる設計ではなく、意図的に外側へ伝播させてノード（引いてはノードを含む
`run_ai_vs_ai_loop`）を失敗させる**設計だった（D-009: 非収束・ロジックエラーは一時的な
API障害ではなく設計上の異常事態として即座に伝播させる方針）。上位層（
`_query_and_parse_with_retry`・`call_detector`）にもこのValueErrorを捕捉する経路は
存在しなかった。

BL-297はこの「finish_reason=="length"と同型」という設計判断を、性質の異なる自分の
シグナルにそのまま流用した点が誤りだった。`finish_reason=="length"`は同一promptを
再送しても再び切り詰められる可能性が高く、静かにリトライし続けるより伝播させて
失敗を明示する設計が妥当である。一方でn-gram反復は、確率的サンプリングの偏りに
起因する一過性の事象である可能性が高く（実際、上記3.1の過検知ケースは「たまたま
低エントロピーな参照データを3回引用した」という一回性の巡り合わせであり、同一
promptを再送すれば別の言葉選びになる可能性が高い）、同じ「伝播させて失敗させる」
扱いは不適切だった。

ユーザーは「検知したときはそのiterをやり直してほしい」と明示的に要求した。

### 3.4 対応（ユーザー指示に基づき実装）

検出時のraiseを、専用の新規例外クラス`_StreamRepetitionRetryError`（素の`Exception`
から派生、`ValueError`ではない——APIError系exceptタプルにも、`finish_reason=="length"`の
「意図的に伝播させる」設計にも誤って巻き込まれないようにするため）へ変更した。

```python
class _StreamRepetitionRetryError(Exception):
    """[BL-298] _StreamRepetitionGuardが反復を検知した際にraiseする内部シグナル。
    finish_reason=="length"用のValueError（D-009により意図的に外側へ伝播させ、
    ノードを失敗させる設計）とは異なり、反復はサンプリングの偏りに起因する一過性の
    事象である可能性が高いため、同一loop_messages・同一iteration番号のまま
    即座に再試行する（_query_AI_live内のwhile Trueループでのみ捕捉する）。
    """
```

`_query_AI_live`内の`while True`ループ自身に新設した`except _StreamRepetitionRetryError`
節でその場で捕捉する。BL-122のiteration_start保持機構——`loop_messages`/
`iteration_start`/`reasoning_parts_all`等が関数冒頭（`while True`の外）で初期化・保持
される既存の実証済み機構——にそのまま乗せることで、他のiterationの思考ログ・ツール
結果を一切失わず、失敗した「このiterationのAPI呼び出し」だけを即座に再試行する。

```python
except _StreamRepetitionRetryError as e:
    if _bl298_repetition_redo_count < _BL298_REPETITION_MAX_REDOS:
        _bl298_repetition_redo_count += 1
        print(f"\n🔁 [{label}] BL-298: n-gram反復検知によりこのiterationの"
              f"API呼び出しをやり直します（{_bl298_repetition_redo_count}/"
              f"{_BL298_REPETITION_MAX_REDOS}回目）: {e}")
        time.sleep(_BL298_REPETITION_REDO_COOLDOWN_SECONDS)
    else:
        print(f"\n❌ [{label}] BL-298: 再試行が上限に達しました。"
              f"プレースホルダーで隠さずエラーを伝播します。")
        raise
```

API過負荷用の`node_redo_count`／指数バックオフ（`delays=[8,16,32,64,128]`秒）／180秒
クールダウン（`_NODE_REDO_COOLDOWN_SECONDS`）とは意図的に別の予算・別のクールダウンとした
（新定数`_BL298_REPETITION_MAX_REDOS = 3`、`_BL298_REPETITION_REDO_COOLDOWN_SECONDS = 3`秒、
AGENTS.md §7重要定数）。反復検知はインフラ過負荷ではなくサンプリングのばらつきが原因であり、
数十秒〜数分の待機は無意味な時間浪費になるためである。

再試行上限（3回）に到達した場合は、BL-202の教訓——delays消尽後に
「(サーバー高負荷によるAPIエラー)」というプレースホルダー文字列を返し、それが下流の
Detector等へ「実際の回答」として誤読され、無意味なラウンド消費を繰り返した過去事故——を
踏まえ、同じ隠蔽策を流用せず、元の例外をそのまま`raise`で再送出する（新しい例外に
握り替えない、文字列を返さない、AGENTS.md §13.2「フォールバックは失敗を大声で示すこと」）。

### 3.5 回帰テスト

`tests/test_bl298_incremental_repetition_detection.py`に7件追加：
- 旧ValueError文言がもう送出されないことの確認
- 検出時に専用例外クラス`_StreamRepetitionRetryError`を2箇所（tools=None分岐・
  toolsループ分岐）でraiseすることの確認
- 同クラスが`ValueError`のサブクラスではないことの確認
- `node_redo_count`/`_NODE_REDO_COOLDOWN_SECONDS`とは別の予算・クールダウンであることの確認
- 再試行上限到達時にプレースホルダー文字列を返さず`raise`で再送出することの確認

AGENTS.md §17.1に従い、旧実装（`raise ValueError(...)`のまま）へ一時的に戻して該当7件が
失敗することを確認した後、新実装へ復元した。

## 4. 検証まとめ

- `tests/test_bl298_incremental_repetition_detection.py`: 新規19件（検出漏れ修正9件＋
  クラッシュ修正7件＋非退行3件）
- `tests/test_bl297_stream_repetition_guard.py`: 新設計へ追従（window/check_interval依存の
  2テストを`_carry`境界越え検出テスト・メモリ安全弁テストへ置換）
- AGENTS.md §17.1: 両実害についてそれぞれ個別にリバート確認済み
- `tests/test_bl231_loop_guard.py`・`tests/test_bl287_tool_repeat_nudge.py`: 非退行確認済み
  （計28件、BL-298関連4ファイル合計）
- フルオフラインスイート: 1915 passed（既知のBL-269汚染4件のみ、新規失敗なし）

## 5. 残課題（本BLの対応範囲外として次回検討）

n-gram反復検出そのものの誤検知率——min_repeats=3という閾値が、今回のような低エントロピーな
構造的テキスト（一文字略称の羅列等）の正当な再参照に対して依然として敏感すぎないか——は
本BLでは対応しなかった。実測データ上、真の崩壊は15〜27回以上の反復であるのに対し、今回の
過検知は3回で発火しており、閾値を例えば5〜6回程度へ引き上げる余地があると考えられる。

ただし本BLの対応（検出時に即座に同一iterationを再試行する設計）により、仮に同種の誤検知が
今後も発生してもクラッシュには至らず「1回分の余分な再試行（数秒＋1回のAPI呼び出し）」で
済むようになったため、緊急性は大幅に下がっている。次回ドライランでの追加発火状況を見て、
ユーザーと再検討する。
