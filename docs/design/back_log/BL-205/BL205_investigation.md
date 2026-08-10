# BL-205 調査記録：read_entityとread_verified_factの役割分担が伝わらず、無駄な探索呼び出しが繰り返される

> 正式なPlan Modeセッションではなく、ユーザー報告の実ログ調査による即時診断・実装。
> 関連: [BL-204](../BL-204/BL204_basic_design.md)、`docs/design/decision_log.md` D-179。

## 発端

BL-204で`read_entity`を8ノードへ展開した直後、ユーザーが`log/2026-08-10/1829`について
「read_entityとread_entityで混乱が生まれています」と報告。文言は乱れていたが、
実ログを調査した結果、意図は「read_entityとread_verified_factで混乱」であると
特定できた。

## 調査

ログを精査したところ、以下のパターンが4回発生していた：

1. モデルが「何か確認したい」と考える
2. `read_verified_fact`を空クエリで呼ぶ → `not_found`
3. さらに`read_entity`も`{"entity": "", "entity_type": ""}`（空）で呼ぶ → 名前一覧
   のみが返る（属性は含まれない）

User AI (Stage4)の思考ログに原因がそのまま現れていた：

> "I'm thinking we need to issue some instructions here. Maybe I could read the
> registry? I might need to use tools to read everything. **The developer
> mentioned that the source of truth requires using the `read_entity` function.**
> So, it seems like I should call the function to list all entities."

一方、正典名チェック自体は正常に機能していた。ゴール文から12件の事物
（JR中央本線、令和2年国勢調査、公立諏訪東京理科大学、組合立諏訪中央病院、茅野駅、
長野県茅野市 等）が正しく登録され、`unknown_entity`拒否は0件だった。つまり
BL-204の本来の目的（名称ハルシネーション防止）は損なわれておらず、問題は
「2つの事実ストアの役割分担が伝わっていない」ことに限定された。

## 根本原因

BL-204導入時に書いた誘導文（「レジストリが真実の源」）は、`read_entity`
（名前を持つ事物の属性専用）と`read_verified_fact`（どの事物にも属さない単独の値）
という2つのストアの境界を一切説明していなかった。加えて、`read_entity`を空引数で
呼んだ場合の返り値（名前一覧のみ、属性なし）が次に何をすべきかを示さないため、
空振りに気づきにくかった。

## 実装

1. `READ_ENTITY_TOOL`のスキーマ説明と`entity`パラメータの説明へ、
   `read_verified_fact`との境界を明記。
2. `_read_entity_handler`の一覧モード（entity未指定）の返り値へ`hint`を追加
   （1件以上登録済みの場合のみ。0件時は再試行の助けにならないため付けない）。
3. ここで一度実装を提示したが、ユーザーから「read_entityを使用するノードの
   プロンプト説明にも書かないと、見落とされます」と追加指摘を受けた。
   スキーマ説明1箇所への追記だけでは、実際に混乱が起きたUser AI Stage4のような
   プロンプト本文側の誘導文までは補強されないため、指摘は妥当と判断した。
4. `read_entity`を付与した全ノード（`call_expert`・`call_detector`のPass1/Pass2・
   `call_task_planner`・`call_task_plan_reviewer`・`call_reviewer`・
   `call_reflection`・`call_facilitator`・`generate_user_utterance`の4経路）
   それぞれのプロンプト本文へ、個別に境界説明を追記した。
   `read_verified_fact`を持たないノード（`call_reflection`・`call_facilitator`）
   には、「このパスにread_verified_factはありません」とその旨も明記し、
   存在しないツールへの誤誘導を避けた。Stage4（実際に混乱が発生した箇所）には
   特に具体的な言い回しで「entity=\"\"で『とりあえず全部見る』ために呼ばないで
   ください」と明記した。

## 教訓

BL-076/BL-193の事故（プロンプト内の相互矛盾が58回のedits失敗を招いた、BL-202/D-176）
と同様に、**ツールの使い方に関する情報は、スキーマ説明という「1箇所の正典」に
書いただけでは、実際にそれを使うノードのプロンプト本文まで自動的には伝播しない**。
本プロジェクトが一貫して「各ノードのプロンプト本文で毎回使えるツールを明示的に
列挙し直す」設計を採ってきたのは、この教訓の先取りだったと言える——BL-205は
その設計方針を新しいツール（read_entity）へ展開する際に、自分自身がその方針を
一時的に怠ったことで再発した事例である。
