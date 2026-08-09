# BL-200 調査記録：web_cacheがrun単位で分離されており、別runで既に取得済みのページも無駄に再取得していた

> 正式なPlan Modeセッションではなく、BL-199報告直後のユーザーからの追加指示による
> 即時実装。関連: [BL-184](../BL-184/)、[BL-199](../BL-199/BL199_investigation.md)。

## 発端

BL-199（`read_goal_reference`の新設）の実装完了を報告した際、ユーザーが
「web_cacheももったいないので、runが変わっても永続的に読めるようにして」
「プロンプト指示はrefs探索→web_cache探索→webサーチの順で手元資料を生かせるように」
と追加指示。

## 調査

BL-184で実装された`web_tools.py`の`cache_file_path(run_id, url)`は、
`web_cache/<run_id>/<sha256(url)[:16]>.md`というrun単位のディレクトリ構造でweb_fetch
結果をキャッシュしていた。`read_reference_file_handler`のベースディレクトリも
`Path(WEB_CACHE_DIR) / run_id`に限定されており、あるrunでweb_fetch済みのURLでも、
別のrunからは`read_reference_file`で参照できず、`web_fetch`を再実行してrun単位の
呼び出し回数を消費する構造になっていた。

同一URLの取得コスト（呼び出し回数消費・応答待ち）はrunをまたいでも変わらないため、
このrun単位の分離は無駄なコストを毎回リセットしているだけだった。BL-199で新設した
`read_goal_reference`（開発者が事前収集した静的参照データ）とは性質が異なり、
`web_cache`はエージェント自身がrun中に集めた一次資料であり、後続のrunにとっても
等しく有用な情報である。

## 実装

1. `cache_file_path`から`run_id`引数を除去し、`web_cache/<sha256(url)[:16]>.md`
   （URLキーの全run共有）へ変更した。`web_fetch_handler`のキャッシュヒット判定・
   `read_reference_file_handler`のベースディレクトリの両方から`run_id`スコープを外した。
2. `WEB_FETCH_TOOL`/`READ_REFERENCE_FILE_TOOL`のツール説明文を、キャッシュがURLキーの
   全run共有であることを明記するよう更新した。
3. **参照優先順位のプロンプト統合**：ユーザー指示の「refs探索→web_cache探索→web
   サーチ」という順序に従い、従来2つの独立したパラグラフだった「web_searchの前に
   read_reference_fileを確認」（BL-188由来）と「web_searchの前にread_goal_reference
   を確認」（BL-199で追加したばかりのもの）を、「①read_goal_reference→
   ②read_reference_file→③web_search」という単一の3段階順序へ統合し、`[BL-199/BL-200]`
   として明記した。Expert（system_prompt・light_system_prompt両方）・Detector
   （Pass1・Pass2両方）・`READ_GOAL_REFERENCE_TOOL`のツール説明文の計5箇所に反映した。

具体的な実装詳細・テスト結果は`docs/design/back_log/issue_backlog.md` BL-200セクション
を参照。

## 教訓

BL-199を実装した直後、同じ会話の中でユーザーから「web_cacheも同様の無駄がある」と
指摘された。BL-199は「開発者が事前に用意した参照データへのアクセス経路が無い」という
問題に対処したが、「エージェント自身が集めた情報がrunをまたいで失われる」という構造的に
似た別の無駄には気づいていなかった。1つの無駄（web_search予算の浪費）を修正する際、
同根の別の無駄（web_fetch予算の浪費、run単位のキャッシュ分離）が近くに潜んでいないか
確認する視点が抜けていた。
