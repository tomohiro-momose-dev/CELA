# BL-293investigation: decision_lineage_gap自動エスカレーションによる役割板挟み生成崩壊

## 発端

ユーザーが複数モデルでの反復ドライラン中、同一パターンの生成崩壊（同様な文節の反復）が複数の異なるモデルで再現することに気づき、「モデル固有の弱さではなくシステム側のプロンプト構成に原因がある可能性が高い」との仮説とともに調査を依頼した。

## 調査手順（§14準拠：システムの記録＝ログを直接確認）

1. `log/2026-08-28/0649/log_no_prompt.md`をtail確認。`⚠️ [Detector (Domain Review)] ツールループ内でmax_tokens超過により出力が打ち切られました（iter=2）`という警告の直前を読むと、以下の推論サイクルが一字一句に近い形で6回以上反復していた：

   1. 「自分の役割はドメイン妥当性レビューだ」
   2. 「User AIの主張する数値（53,500/17,199/32.1%）は検証すべきか？」
   3. 「→none/minorが妥当」
   4. 「でも待てよ、このエスカレーション（decision lineage gaps）を再考すると…」
   5. 「User AIがthinkに2件の分岐点を記録したがwrite_agreement(Decision)は0件だった」
   6. 「これは記録漏れの問題であってドメイン妥当性の問題ではない…いや自分の役目とは…」
   → 1へ戻る

2. `_bl231_plan_sig`/`_TOOL_CALL_REPEAT_NUDGE_THRESHOLD`（BL-231/287）はいずれも`tool_calls`の反復を検知対象とする。本件はツール呼び出しを一切伴わない純テキスト推論の反復であり、これらのガードは構造的に対象外（§14.3：期待されるログ行＝ガード発火メッセージが実際に存在しないことを確認）。

3. ログに現れた"decision lineage gaps"というキーワードから、コード側で該当する文言・機構を`grep`で逆引き。`_record_decision_lineage_gap_issue`（`cela_main.py:6696`、BL-283）が該当。severity="major"での自動起票 → 不変条件によりstatus="escalated"（`_write_issue_impl`の不変条件、D-079/D-080） → 既存の`escalation_pin`表示チャネル（BL-103）へ合流、という経路をコードから直接追跡した（推測ではなく`grep`と`Read`による実地確認）。

4. `_build_escalation_pin_text`（`cela_main.py:4920`）の実装を確認したところ、issueの`description`をそのままラベル付きで貼るだけで、「このエスカレーションが自分の職掌に該当しない場合の扱い」についての指示が一切無いことを確認した。

5. `call_detector`のdomain_prompt（Domain Reviewパスの役割定義）を確認したところ、スコープは「施設規模・要員配置・安全規制等のドメイン妥当性」に明確に限定されており、「User AIの記録漏れ」は管轄外であることを確認した。

## 結論

プロンプトが「エスカレーションには要対応」と「あなたの職掌はドメイン妥当性のみ」という両立しない2つの信号を同時に与えており、モデルが誠実に読めば読むほど矛盾に気づいて堂々巡りに陥る。これはモデルの弱さではなく指示設計の欠陥であり、複数モデルで再現したことと整合する。BL-283が「入口」（記録漏れの自動エスカレーション化）を作った際、「出口」（このタイプのエスカレーションを実際に誰が処理すべきか）の設計が漏れ、既存の汎用チャネルへ無条件で乗せられたことが原因（AGENTS.md §15.4）。

`decision_lineage_gap_{起こしたロール}_{task_id}`というトピック文字列自体が「起こした当人が自己解決すべき」という性質を既に体現していたにもかかわらず、この情報が表示フィルタに一切使われていなかった。

## 対応（軽量案を採用、モデルへの自己判断委任は不採用）

検討した2案：

1. **（不採用）domain_promptに「職掌外のエスカレーションは無視してよい」と一文追記する**: 実装コストは最小だが、モデルの自己判断に崩壊回避を委ねる点で、そもそも崩壊を引き起こした「自分で判断しようとして堂々巡りになる」構造に頼り直すことになり、根治にならない。
2. **（採用）機械的フィルタ**: `_build_escalation_pin_text`へ`caller_role`引数を追加し、`decision_lineage_gap_`接頭辞のトピックは呼び出し元自身が起こしたものだけを残す。他種のエスカレーションはフィルタ対象外。BL-266の`_BL266_ESSENCE_TOPIC_PREFIX`と同型のトピック接頭辞フィルタパターンを踏襲。

3呼び出し元（`call_expert`/`call_detector`/`generate_user_utterance`）は`_CURRENT_CALLER_ROLE`グローバルではなくリテラル文字列で役割名を渡す。調査中、`call_expert`では`escalation_pin`構築時点でこのグローバルがまだ前ノードの値のまま更新されていない場合があると判明したため（他2箇所は問題なかったが、3箇所とも統一してリテラル指定に揃えた——§13.5「個別事象でなくクラスごと直す」）。

## 総点検（ユーザー依頼、§13.5「クラスごと直す」の実践）

修正完了後、ユーザーから「他に役割を超えた矛盾した指示を提示し続けるパターンが無いかを総点検してください」と依頼を受けた。`call_*`関数群を機械的に走査し、3つ以上の異なる役割の関数から共通して呼ばれる「共有アンビエント注入ヘルパー」を列挙して1件ずつ精査した。

| ヘルパー | 消費先数 | 判定 |
|---|---|---|
| `_build_escalation_pin_text` | 3 | **要修正**（本BLの本体） |
| `_get_forced_escalated_issues_text`（`_get_actionable_escalated_issues`の別の消費先、helper列挙には現れないが同じデータソースを使うため個別に追跡） | 2（`generate_user_utterance`内） | **要修正**（さらに強い行為強制、同型フィルタを追加） |
| `_build_decision_lineage_directive` | 12 | 問題なし。「動作が分岐する場合」という条件付き文言で、branchが無い場合は自然に非該当と読める設計 |
| `_get_goal_essence_text` | 7 | 問題なし。受動的な参考情報の提示のみ、行動要求を含まない |
| `_build_task_focus_state_text` | 4 | 問題なし。現在状態の表示のみ、行動要求を含まない |
| `_build_stateless_architecture_primer` | 3 | 問題なし。仕組みの説明のみ |
| `_build_deferred_issue_pin_text` | 3 | 問題なし。BL-194で意図的に非強制トーンへ設計済み |
| `_build_acknowledged_issue_pin_text` | 3 | 問題なし。BL-194で意図的に前向きトーンへ設計済み |

`_get_forced_escalated_issues_text`（BL-136）は、`_get_actionable_escalated_issues`の戻り値をpinより強い「今回の発言内で必ずRESOLVE/DEFERを呼べ、理由なく放置することはできません」という文言で提示する。`decision_lineage_gap_*`issueがここに混入すると、是正手段（write_agreement(Decision)を書くこと）を持たない相手に「必ず解決せよ」を強制することになり、pin以上に深刻な板挟みを生みかねないと判断し、同じ`caller_role`フィルタを追加した（`generate_user_utterance`内の2箇所の呼び出し元へ`caller_role="user"`）。

なお、`_get_forced_escalated_issues_text`がwrite_issue(RESOLVE)だけで「実際にはwrite_agreement(Decision)を書かないまま記録漏れissueだけ閉じられる」抜け道を理論上持つ点にも気づいたが、これは今回の「役割の板挟みによる生成崩壊」とは別種の懸念（虚偽解決のリスク）のため、本BLのスコープ外として次回以降の検討に委ねる。

## 「自己解決」の前提そのものへのユーザー指摘

上記フィルタ修正の報告後、ユーザーから「`decision_lineage_gap_*`は起こした当人が自己解決すべき性質とのことだが、次ターンになったらそのロールは前のターンの自分の思考ログを見られないはずでは？本当に解決できるのか？」という指摘を受けた。

調査の結果、仕組みの骨格自体は正しい——`think`の生ログはツールループ終了と共に消えるが、`_record_decision_lineage_gap_issue`は消える**前**に`decided`/`rejected`をissue_log.descriptionへ書き写して永続化しており、次ターンの自己解決はこの永続化された記述を読む形で成立する（生の思考を思い出す必要が無い設計）。

ただしこの過程で、実装上の欠落が見つかった。同じ`pending`データを使う2つの整形関数のうち、`_build_decision_gap_correction_note`（同一ターン内の即時差し戻し）は`decided`/`why`/`rejected`/`rejected_why`の4フィールドを含めるのに対し、`_record_decision_lineage_gap_issue`（次ターン向けの永続化）は`decided`/`rejected`の2フィールドしか含めていなかった（AGENTS.md §15.1、同一データの2つのレンダラーが非対称）。`why`/`rejected_why`（決定理由・却下理由）が失われたまま次ターンへ渡ると、書き直されるDecisionもreason_whyの薄い形骸的な記録にしかならず、decision lineageの本来の目的を達成できない。ユーザー承認のもと、description構築へ`why`/`rejected_why`を追加して修正した。

## Critical Files

- `cela_main.py`: `_build_escalation_pin_text`（4920行、`caller_role`引数追加）＋3呼び出し箇所、`_get_forced_escalated_issues_text`（8365行、`caller_role`引数追加）＋2呼び出し箇所、`_record_decision_lineage_gap_issue`（description構築へwhy/rejected_why追加）
- `tests/test_bl293_decision_lineage_gap_pin_scoping.py`（新規16件）
- `tests/test_bl283_decision_lineage_gate.py`（追加2件）

## Verification

AGENTS.md §17.1（`cela_main.py`全体をgit stashで一時的に巻き戻し、新規16件中14件・追加2件中1件が失敗することを確認後、diffが完全一致することを確認して復元）。既存の`test_bl123_detector_escalation_pin.py`・`test_bl194_*`・`test_bl170_*`・`test_bl086_escalation_freeze_goal_revision.py`・`test_bl096_issue_log.py`・`test_bl144_escalated_issue_staleness_threshold.py`・`test_bl283_decision_lineage_gate.py`（計174件）・フルオフラインスイート1844 passed（既知のBL-269 4件のみ残存、新規失敗なし）。実LLM呼び出しでの効果確認（同種の崩壊が再発しないか、次ターンでの自己解決が実際に機能するか）は次回ドライラン待ち。

## 次回以降への申し送り

- `_get_forced_escalated_issues_text`の「write_issue(RESOLVE)のみで実質未解決のまま閉じられる」抜け道（上記参照、本BLのスコープ外として据え置き）。
- 過去に発見済みだがまだ`issue_backlog.md`未起票の1件（BL-291/292設計時のtask_planner/User AIによるentity命名の表記ゆれ問題、BL-292設計時の議論から派生）は、本セッションでは未着手のまま残っている。

参照: `tests/test_bl293_decision_lineage_gap_pin_scoping.py`、`log/2026-08-28/0649/log_no_prompt.md`、`docs/design/back_log/issue_backlog.md` BL-293、`docs/design/decision_log.md` D-248。
