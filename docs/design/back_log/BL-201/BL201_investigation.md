# BL-201 調査記録：--resumeしたrunのstateが、resume時点のconfig変更（呼び出し回数上限等）を一切反映しない

> 正式なPlan Modeセッションではなく、ユーザー報告直後のログ調査による即時診断・実装。
> 関連: [BL-197](../BL-197/BL197_investigation.md)（同種のチェックポイント/config分離問題の逆方向）、
> [BL-199](../BL-199/BL199_investigation.md)。

## 発端

BL-199/200の実装完了を報告した直後、ユーザーが「web_searchの呼び出し上限（30回/run）に
達しました。エラーになっています。50回に緩和しませんでしたか？」と報告。

## 調査

まず、ユーザーが見ているログが古い`log/2026-08-09/2222`（BL-199実装前のログ、既に調査・
対応済み）を再度参照しているだけではないかを疑い、`log/2026-08-09/`配下のディレクトリを
確認した。その結果、実際には新しいログディレクトリ`log/2026-08-09/2313`が生成されており
（IDEで開かれていた`2222`ではなく）、そこでも同じ`web_searchの呼び出し上限（30回/run）に
達しました`エラーが発生していることを`log_no_prompt.md:1026`で確認した。

現在実行中のPythonプロセス（`Get-CimInstance Win32_Process`で確認、開始時刻23:13:06）は
`cela_main.py`の最終更新時刻（23:07:53、BL-199/200実装完了時点）より後に起動しており、
コード自体は最新版のはずだった。ログの冒頭を確認したところ：

```
♻️ [Resume] run_id=1786246233-0d2e0184 から再開します（turn=5）。
```

このrun_idは、BL-197の投機的診断の過程で何度も再開してきた**同一のrun**であり、
BL-199実装より前から継続していた。

`run_ai_vs_ai_loop`のresume分岐（`cela_main.py`）を確認したところ、次の実装になっていた：

```python
snapshot = app.get_state(runtime_config)
...
state = snapshot.values  # チェックポイントの内容をそのままstateとして復元
db_path = state["db_path"]
```

LangGraphのチェックポイントには、run開始時点（このrunの場合はBL-199実装より前）に
`config`から`state`へコピーされた`max_web_search_calls: 30`がそのまま保存されており、
`state = snapshot.values`はこの値をそのまま復元するだけで、**現在の`config`引数
（コード側で30→50へ緩和済みの値）を一切参照していなかった**。そのため、コードを修正
しても、既に走っているrunを`--resume`する限り、古い上限値が使われ続けていた。

これはBL-197で発見した「チェックポイントの巻き戻しは会話状態のみを戻し、`cela.db`側の
成果物・issue_logは巻き戻らない」という問題の**逆方向**に相当する：BL-197では「古い
会話状態が新しい成果物を汚染する」方向だったが、本件は「新しいconfig（開発者の設定改善）
が古い会話状態のresumeに反映されない」方向である。いずれも、根底には「チェックポイントは
ある時点の会話状態のスナップショットであり、それ以外の“今の正しい設定”の情報源では
ない」という同じ性質がある。

## 実装

`run_ai_vs_ai_loop`のresume分岐、`state = snapshot.values`の直後に、以下4フィールドを
現在の`config`引数の値へ明示的に再同期する処理を追加した：

- `max_web_search_calls`
- `max_web_fetch_calls`
- `max_road_route_calls`
- `goal_reference_dir`

これらは会話の履歴（`chat_history`・ホワイトボード・issue_log等）ではなく実行時設定
であるため、resumeのたびに最新の`config`へ追従させるのが正しい。呼び出し済みカウンタ
自体（`web_search_call_count`等）は実際に消費済みの実績を表すため、リセットしない
（上限だけを緩和し、既に使った分はそのまま維持する）。

新規テスト`test_resume_refreshes_config_derived_limits_from_current_config`
（`tests/test_checkpoint_resume.py`）は、既存の`_FakeCompiledGraph`/`_FakeSnapshot`
スタブパターン（`test_run_ai_vs_ai_loop_reports_missing_run_id_and_returns`等で
確立済み）を再利用し、`halt=True`のstateをresumeすることでグラフ実行・DB接続を
発生させずに、4フィールドがconfigの新しい値へ更新されることのみを検証した。

## 運用上の注意

この修正はコード側のみであり、**既に起動済みのPythonプロセスには反映されない**。
`log/2026-08-09/2313`のrunを続ける場合は、一度プロセスを停止し、この修正を含む
コードで改めて`--resume`する必要がある。

## 教訓

BL-199/200のように「コードを直せば次の動作から改善される」という直感は、resumeという
「過去の状態を復元して継続する」実行モードの下では成立しない場合がある。config引数として
渡している値のうち、どれが「run開始時に一度だけ確定する会話の一部」で、どれが「実行の
たびに最新であるべき設定」かを区別し、後者はresume時に明示的に再同期する必要がある、
という設計上の教訓が得られた。同じ性質の見落としが将来また起きないよう、新しい
run-scoped設定値（呼び出し回数上限やディレクトリパス等）を追加する際は、この4フィールド
再同期リストへの追加を忘れないようにする必要がある。
