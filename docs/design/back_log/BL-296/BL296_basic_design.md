# BL-296: 公表されていない値の推計に「1つの妥当な方法で確定させる」満足化規定を導入

## Context

`log/2026-08-28/1535`（Ctrl+Cで一時停止済み）で、Expert（task_1_1、免許返納累計件数）が「茅野市単位の累計は公式統計に存在しない」状況に直面し、iter=6の単一生成ターン内で9分半・15回以上、「長野県の構成比から按分推計する→仮定が重すぎるので却下→もっと誠実な方法があるはずと言い直す→運転経歴証明書は年間件数であって累計ではないと気づき振り出しに戻る」という同一サイクルを繰り返し、ツール呼び出しも出力確定も行わないまま停止した。

これはBL-293（役割の板挟み）・BL-294（マンデート値と検証結果の衝突）・BL-295（二択・三択の裁量判断に打ち切り規定が無い）のいずれとも異なる4つ目のパターン——「推計の精緻化に終わりが無い（完璧主義ループ）」。BL-295の3回多数決方式はカテゴリカルな結論の選択には合うが、「複数の推計手法のうちどれが最も誠実か」を無限に模索し続ける今回のケースには構造的に合わない（離散的なtrial1/2/3で多数決を取れる「結論」が無く、連続的に手法を洗練させ続ける失敗モードのため）。

ユーザーとの合意：公表されていない値を推計する一般的な実務手法（代理指標の比例配分・類似事例の転用・フェルミ推定的分解・レンジ/感度分析での提示・前提の明示的記録）のいずれか1つを選んだ時点で確定させ、「より誠実な方法」を探して再導出し続けないという満足化（satisficing）規定を追加する。ユーザーからは、Expertだけでなく**User AIとDetectorにも同種の必要性がある**との指摘があった。

Explore調査の結果、以下を確認した：
- `call_expert`の既存BL-041ブロック（`cela_main.py:11594-11609`、確定値と暫定値の区別）は、confidence選択をcross-task制約衝突／User承認の有無でしか判定しておらず、「そもそも公式統計が存在しない場合どうするか」には一切触れていない。
- `generate_user_utterance`には該当する指示が皆無（file全体で「公式統計」の文字列は0件）。
- `call_detector`もconfirmed/provisionalのラベル妥当性や引用の実在性はチェックするが（BL-094/BL-188、`cela_main.py:12609-12635`付近）、「推計手法そのものが妥当か」を評価する仕組みは存在しない。
- 3ロールに共通する既存の共有ブロックとして`_USER_AI_ROLE_MANDATE`（`cela_main.py:10802-10814`、Stage1/3/4横断でgenerate_user_utteranceに配線済み、BL-292が同じパターンで拡張した前例）が使える。

## 設計

### 1. 新規共有ヘルパー`_missing_data_estimation_instruction(perspective)`

`_bounded_deliberation_instruction`（BL-295、`cela_main.py:10658`付近）の近くに追加する。`perspective`引数で「自分が推計する側（producer）」と「他者の推計を審査・許可する側（auditor）」で結び文を切り替える（`_verification_throttle_warning`の`output_form`引数と同型のパターン）:

```python
def _missing_data_estimation_instruction(perspective: str = "producer") -> str:
    """[BL-296] 公表されていない値の推計で「より誠実な方法」を無限に探し続ける完璧主義
    ループ（log/2026-08-28/1535: Expertが9分半・15回以上同一の推計サイクルを繰り返し
    停止）を防ぐための、実務標準の推計手法一覧と満足化（satisficing）規定。
    perspective="producer"（Expert等、自ら推計する側）は「1つ選んだら確定させ、探索を
    打ち切れ」、perspective="auditor"（User AI/Detector等、他者の推計を審査する側）は
    「文書化された妥当な手法を理由なく差し戻すな」という逆方向の指示になる。
    """
    methods = (
        "・代理指標の比例配分（より広域の公表統計を、既知の按分係数で対象へ配分する）\n"
        "・類似事例の転用（統計が公表されている類似の対象を近似値として使う）\n"
        "・フェルミ推定的分解（未知の値を、個別に推定しやすい複数要素の積・商に分解する）\n"
        "・レンジ（感度分析）での提示（単一の点推定ではなく、前提を変えた場合の低位・"
        "中位・高位の幅で示す）\n"
        "・前提の明示的記録（使った基礎統計・按分係数・仮定を出典として残す）\n"
    )
    if perspective == "auditor":
        action = (
            "相手が上記いずれかの方法を使い、前提（基礎統計・按分係数・仮定）を明記した"
            "上でconfidence=\"provisional\"として値を確定させている場合、それだけを理由に"
            "差し戻したり、より正確なデータの再提出を求めたりしないでください。指摘すべきは、"
            "手法自体が不合理（無関係な代理指標を使っている等）か、前提が明記されていない"
            "場合に限ります。指示を書く際も、これらの方法のいずれかで済ませてよいことを"
            "明記してください。\n\n"
        )
    else:
        action = (
            "1つの方法を選び前提を明記できた時点で確定させてください。それ以上"
            "「もっと誠実な方法があるはず」と再導出し続けないでください。\n\n"
        )
    return (
        "【公表されていない値の推計方法（重要）】求められている数値がどの一次情報源にも"
        "直接は公表されていない場合の一般的な推計方法は次の通りです。\n"
        f"{methods}"
        f"{action}"
    )
```

### 2. call_expert: BL-041ブロックへ`perspective="producer"`を適用

`cela_main.py:11594-11609`のBL-041ブロック（`{_scratch_concerns_closure_instruction(...)}`の直前）へ挿入する。

### 3. `_USER_AI_ROLE_MANDATE`へ`perspective="auditor"`を適用

`cela_main.py:10802-10814`（BL-292が同じ構造で追記した前例のすぐ後）へ追加する。Stage1（レビュー）・Stage4（指示作成）双方に自動配線されるため、単一箇所への追加でUser AIの「Expertの推計を審査する場面」と「Expertへ指示を書く場面」の両方をカバーする。

### 4. call_detector: Domain Reviewへ`perspective="auditor"`を適用

`cela_main.py:12609-12635`付近（BL-094/BL-188の出所追跡チェックの近く）へ追加する。

## Critical Files

- `cela_main.py`:
  - `_missing_data_estimation_instruction`（新規関数、`_bounded_deliberation_instruction`＝`10658`付近に追加）
  - `call_expert`のBL-041ブロック（`11594-11609`行付近）: producer視点で追加
  - `_USER_AI_ROLE_MANDATE`（`10802-10814`行付近）: auditor視点で追加
  - `call_detector`のdomain_prompt（`12609-12635`行付近）: auditor視点で追加
- `tests/test_bl296_missing_data_estimation.py`（新規）: `_missing_data_estimation_instruction`のperspective別出力確認（producer/auditorで結び文が異なること、5手法が両方に含まれること）、call_expertへの追加確認（`inspect.getsource`）、`_USER_AI_ROLE_MANDATE`への追加確認（定数の中身を直接確認）、call_detectorへの追加確認、§17.1

## Verification

1. `python -m py_compile cela_main.py`
2. 新規テストファイルを実行し全件成功を確認
3. 既存の関連テスト（BL-041/BL-292/BL-295関連、call_expert・generate_user_utterance・call_detector関連の既存テスト）を再実行し非退行を確認
4. AGENTS.md §17.1（各追加箇所を個別にリバートし対応テストが失敗することを確認後、復元）
5. フルオフラインスイートを実行し、既知のBL-269（4件）以外に新規失敗が無いことを確認
6. 実装後、`docs/design/back_log/issue_backlog.md`にBL-296を`done`化し記載、`decision_log.md`へ決定を記録
7. プロンプト文言の追加であり実LLM呼び出しでの効果確認が必要——次回ドライラン時に、①Expertが公式統計の無い値に直面した際、1つの手法を選んで確定できるか、②User AIがExpertの文書化された推計を不当に差し戻さないか、③Detectorが同様の推計をmajorとして誤って差し戻さないか、をログで確認することを次回宿題として記録する。
8. 現在一時停止中のrun（`log/2026-08-28/1535`）を`--resume`するか打ち切るかは、この実装とは別にユーザー判断待ち。
