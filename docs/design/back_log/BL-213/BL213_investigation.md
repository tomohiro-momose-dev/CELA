# BL-213 調査記録：agreements / decision_extractor 周辺における「構造化フィールドの無条件信頼」横断監査

作成日: 2026-08-11
対象コミット: `6a97f7f`（BL-212修正直後）
調査者: Claude（Sonnet 5 / Opus 5）
依頼者の指示: 「一度立ち止まって、『agreements/decision_extractor周りで構造化フィールドを無条件に信頼している箇所』を横断的に洗い出す」

---

## 1. 監査の動機

2026-08-10〜11の連続ドライランで、**同一の症状（タスクが進まない／編集が通らない）が毎回異なる原因で
4連続発生**した。

| BL | 症状 | 直接原因 | 信頼していた構造化フィールド |
|----|------|----------|------------------------------|
| BL-206 | edits失敗の連発 | Deliverable行の孤児化 | `item["phase_id"]`（空文字ドリフト）、`topic`のみでのsupersede対象特定 |
| BL-210 | task_3_2→task_4_0の遷移が毎回拒否 | フェーズ探索範囲の決め打ち | `transition["advances_to_phase_id"]`（null時のフォールバック先） |
| BL-211 | task_4_2→task_4_3の遷移が成立しない | BL-139安全網の空振り | `item["task_id"]`（空文字ドリフト） |
| BL-212 | edits失敗が17回連発 | WHITEBOARD:プレフィックスの喪失 | `old_content`の文字列形式 |

4件はいずれも個別のバグとして修正したが、**共通する構造**がある。

> LLMが返すJSONの特定フィールドが「必ず期待した形で埋まっている」という前提でコードが分岐し、
> その前提が崩れたときの防御が、たまたま踏んだ1経路にしか実装されていない。

本監査は、同じクラスの未発見バグを**踏む前に**洗い出すことを目的とする。

---

## 2. 監査手法

1. `cela_main.py` 全体に対し、以下4類型のパターンを機械的に抽出（Grep）
2. 抽出箇所を実際に読み、**空文字／欠落／誤値が来たときに何が起きるか**を追跡
3. 実ログ（`log/2026-08-11/0941`・`1034`）およびDB（`cela.db`）で、その入力が実際に発生しうるかを確認
4. 既存の防御（guard・fallback）がその経路に届いているかを確認

### 監査した脆弱性の4類型

| 類型 | パターン | 代表事例 |
|------|----------|----------|
| **A. 空文字が既定値を貫通** | `d.get("key", default)` はキー欠落時しかdefaultを使わない。`""` はそのまま採用される | BL-206、BL-211 |
| **B. 文字列形式から状態を判定** | `s.startswith("WHITEBOARD:")` 等、別テーブルの実データではなく文字列表現で状態を決める | BL-212 |
| **C. 探索範囲の決め打ち** | あるフィールドが欠けたとき、検索対象を「現在の何か」へ即フォールバックする | BL-210 |
| **D. 安全網の前提条件が厳しすぎる** | 抽出漏れを救うための代替経路が、別のフィールドが埋まっていることを要求している | BL-211 |

---

## 3. 構造的所見（最重要）

**`agreements`テーブルへの書き込み経路は2本あり、検証の厳しさが極端に非対称である。**

### 経路1: `write_agreement`ツール → `_write_agreement_impl` → `_commit_agreement_from_tool`

6層の検証を通る。

| # | 検証内容 | 場所 |
|---|----------|------|
| 1 | 必須フィールド（`action_type`/`status`/`topic`/`reason_why`/`entry_type`/`decision_what`）の**空文字を含む**不足チェック | `cela_main.py:3240`（`if not args.get(f)` の真偽判定なので `""` も弾く） |
| 2 | enum値チェック（`action_type`/`status`/`entry_type`） | `cela_main.py:3253-3261` |
| 3 | ロール別書き込み権限チェック | `cela_main.py:3264` |
| 4 | `depends_on`の参照整合性 | `cela_main.py:3269` |
| 5 | [BL-131] `task_id`実在チェック／[BL-146] `current_task_id`一致ゲート | `cela_main.py:3280-3308` |
| 6 | [BL-131] `target_topic`必須化（UPDATE/SUPERSEDE、非Deliverable） | `cela_main.py:3322` |

### 経路2: `call_decision_extractor` → `decision_extractor_node` のフォールバック書き込み

**検証は0層。**

`call_decision_extractor`（`cela_main.py:9235-9239`）は、LLMの返した `parsed["extracted_events"]` を
**一切検証せずそのまま返す**。

```python
if isinstance(parsed, dict) and "extracted_events" in parsed:
    return parsed["extracted_events"], transition   # ← スキーマ検証・enum検証・空文字検証すべて無し
```

受け取った `decision_extractor_node`（`cela_main.py:12056-12064`）は、類型Aのパターンで
各フィールドを取り出し、そのまま `db_append_agreement` へ渡す。

```python
action_type = item.get("action_type", "CREATE")
entry_type  = item.get("entry_type", "Decision")     # ← "" が来たら "" のまま
status      = item.get("status", "Proposed")
topic       = item.get("topic", "Unknown Topic")
proposed_by = item.get("proposed_by", "Unknown")
defer_to_task_id = item.get("defer_to_task_id", "")
```

BL-206で `phase_id` を、BL-211で `task_id` を個別に `or` パターンへ直したが、
**同じ行に並んでいる他の5フィールドは類型Aのまま残っている。**

そして、この経路で書かれた行は経路1と同じ `agreements` テーブルに入り、
`_find_active_deliverable_agreement` / `integrator_node` / `_is_task_completed` など
**下流の全機構が同じ前提で読む**。

> **結論**：検証の厚みが経路によって6層と0層に分かれている限り、同じクラスのバグは
> 「まだ踏んでいない経路」で再発し続ける。これが4連続バグの構造的な原因である。

---

## 4. 発見事項

深刻度は「実害の大きさ × 発生条件の現実性」で判定した。

### F1【高】`integrator_node`が最終統合文書に成果物本文の代わりに短文を出力しうる

**場所**: `cela_main.py:12586-12601`

```python
content_data = d['decision_what']
if content_data.startswith("FILE_PATH:"):
    ...
elif content_data.startswith("WHITEBOARD:"):
    wb = get_latest_whiteboard(...)
    content_text = wb["content"] if wb else "(⚠️ホワイトボードが見つかりません...)"
else:
    content_text = content_data      # ← 短文がそのまま最終文書へ
```

**再現条件**: `entry_type='Deliverable'` かつ `status='Approved'` の行の `decision_what` が、
ポインタ（`WHITEBOARD:` / `FILE_PATH:`）ではない短い文字列になっている場合。

これは仮説ではなく、`log/2026-08-11/1034`で実際に発生した状態である。DBを直接確認したところ、
task_4_2のDeliverable系列に次の行が存在した（BL-212の残留）。

```
AG-1786411194396  proposed_by=detector  decision_what="task_4_2の承認維持・task_4_3移行の根拠となった承認済み成果物を無効化する。"（45字）
AG-1786411230279  proposed_by=user      decision_what="task_4_2の承認およびtask_4_3への移行判断を撤回し...Rejectedとする。"（62字）
AG-1786412167516  proposed_by=user      decision_what="task_4_2の承認およびtask_4_3への移行判断を明確に撤回し...task_4_3以降へ進めない。"（105字）
```

今回の3行は `status='Rejected'` だったため `integrator_node` の抽出条件
（`status == "Approved"`）から外れて実害には至っていない。しかし、これらの短文行が
「有効な最新Deliverable」として残った状態で次に承認が成立すると、後述F2の経路により
短文が伝播したまま `Approved` になりうる。

**影響**: プロジェクト全体の最終成果物である統合要件定義書に、27KBの設計本文の代わりに
**「承認を撤回する」という1行**が載る。しかも警告は一切出ない（`else`分岐は正常系として扱われる）。
実行全体が無駄になる種類の実害であり、かつ最後まで気づけない。

**推奨対応**: `else` 分岐を「異常」として扱う。`d['task_id']` から
`get_latest_whiteboard` を直接引き、存在すればそれを使う（BL-212で確立した
「whiteboard_draftsを権威とする」方針の適用）。どちらも取れない場合は
`content_text` に警告文を入れ、`print` でも明示する。

---

### F2【高】BL-212の修正が不完全：保護分岐が`WHITEBOARD:`ポインタを復元しない

**場所**: `cela_main.py:3152`、`cela_main.py:3175`（いずれも `_commit_agreement_from_tool` 内）

BL-212で `is_whiteboard` の**判定**は `whiteboard_drafts` の実在参照へ直した。しかし、
その判定を使う**保護分岐の中身**は手つかずのままである。

```python
elif is_whiteboard:
    content = old_content        # ← old_contentが短い理由文なら、短い理由文が伝播する
```

```python
else:
    content = old_content        # ← 同上
```

**再現条件**: BL-212の短文SUPERSEDEが一度でも起きた後、同じtask_idに対して
edits未指定のUPDATE（＝承認コメント等、User AI/Detectorが日常的に行う操作）が来たとき。

このとき `is_whiteboard` は（BL-212修正により正しく）`True` になるが、
`old_content` は前段の短文であるため、新しい行にも短文がコピーされる。
**`agreements` 側は永久に `WHITEBOARD:` ポインタを取り戻せない。**

**影響**: F1の前提条件（Approved かつ 短文）を成立させる直接の経路。
また `_resolve_deliverable_pointer`（F6）経由の `read_deliverable_file` にも影響する。

**推奨対応**: `is_whiteboard` が真なら `content = f"WHITEBOARD:{phase_id}:{tid}"` を代入する。
`old_content` の中身に依存しない。BL-212の修正と完全に同じ思想であり、
**BL-212の修正漏れとして扱うのが正しい**（新規BLではなくBL-212の追補）。

---

### F3【高】`decision_extractor`フォールバック経路の空文字ドリフトが5フィールド分無防備

**場所**: `cela_main.py:12057-12064`、`cela_main.py:12117`

第3節で述べた通り、`phase_id`（BL-206修正済み）と `task_id`（BL-211で別途対処）以外の
フィールドは類型Aのまま。特に危険なのは次の2つ。

#### F3-a: `entry_type = item.get("entry_type", "Decision")`

`""` が来た場合の追跡：

1. `12100` / `12111` の `entry_type == "Deliverable"` 分岐がすべて素通り
2. `12126` の supersede対象探索が `a.get("entry_type") == ""` となり何も一致しない
3. `old_content = ""` のまま `12152` へ到達し、新しい行が `entry_type=""` で書かれる
4. その行は `_find_active_deliverable_agreement`（`entry_type=='Deliverable'` 必須）から
   **永久に不可視**になり、`integrator_node`（`entry_type == "Deliverable"` 必須）からも
   **最終文書に含まれない**

これはBL-206の孤児化とまったく同じ結末に至る、独立した第3の経路である。

#### F3-b: `target_topic = item.get("target_topic", topic)`

`""` が来ると `topic` へのフォールバックが効かず、`12126` の探索が空文字topicを探すことになる。
supersede対象が見つからず、`old_content=""` → 保護分岐（`12134`）も効かず、
新しい行が短文で書かれる。

なお**経路1では同じ問題が [BL-131] のガード（`cela_main.py:3322`）で塞がれている**
（`if not args.get("target_topic")` は空文字も弾く）。経路2にだけ穴が残っている、
第3節の非対称性の典型例。

**発生の現実性**: 同一runで同一モデルが既に `"phase_id": ""`（BL-206）と
`"task_id": ""`（BL-211）を出力している。`entry_type` や `target_topic` だけが
例外的に常に埋まると考える根拠はない。

**推奨対応**: `12057-12064` の6行を `or` パターンへ統一し、あわせて
`call_decision_extractor` の戻り値（`cela_main.py:9235`）に**最小限のスキーマ検証**を
追加する。enum外・空文字の項目は既定値へ正規化するか、その項目自体を破棄して
警告を出す（フェイルクローズ）。経路1の層1・層2（必須チェック＋enumチェック）に
相当する検証を経路2にも置く、という位置づけ。

---

### F4【中】BL-210の残穴：`advances_to_phase_id`が「非空だが誤り」の場合、横断探索がスキップされる

**場所**: `cela_main.py:11719`、`cela_main.py:11748`

```python
target_phase = phase_lookup.get(next_phase_id) if next_phase_id else None

if target_phase is None and next_task_id:      # ← next_phase_idが「正しく引けた」場合ここへ来ない
    target_phase = _find_phase_containing_task(...)
```

BL-210は `advances_to_phase_id` が **null のとき**の探索範囲を直した。しかし
`next_phase_id` が非空で、かつ `phase_lookup` に存在する値（例：現在フェーズの
`phase_3`）であれば `target_phase` は非Noneになり、**BL-210で追加した横断探索を通らない**。

その後 `11748` の `valid_task_ids` は `target_phase`（＝誤ったphase_3）のタスクのみを見るため、
`task_4_0` は `11755` で「存在しないtask_id」として拒否される。**BL-210修正前とまったく同じ症状**。

**発生の現実性**: LLMが `advances_to_phase_id` に「現在のフェーズID」をそのまま
エコーバックするのは、`advances_to_task_id` だけ正しく次タスクを指すのと同程度に
ありふれた出力揺れである。実際、`call_decision_extractor` のプロンプト
（`cela_main.py:9203`）は `"phase_id": "現在のフェーズID"` と、
`extracted_events` 側について明示的に「現在の」と指示している。

**影響**: BL-210と同じ「タスク遷移が永久に成立せず、最終的にHALT」。

**推奨対応**: `next_task_id` が指定されている場合、`target_phase` が非Noneでも
そのフェーズに `next_task_id` が**含まれているかを先に確認**し、含まれていなければ
横断探索へ落とす。すなわち「明示された `phase_id` は候補であって確定ではない」
という扱いに変える（D-184の優先順位そのものは維持し、検証を1段挟む）。

---

### F5【中】`decision_extractor`フォールバック経路にBL-212同型の文字列判定が残存

**場所**: `cela_main.py:12134`

```python
if old_content.startswith("WHITEBOARD:"):
    content = old_content
    print("  🔒 [Whiteboard Protected] ... ホワイトボードポインタを保護し...")
```

BL-212で `_commit_agreement_from_tool` 側（経路1）の同型判定は直したが、
`decision_extractor_node` 側（経路2）は類型Bのまま。

**再現条件**: BL-212の短文行が「有効」な状態で、`write_agreement`が呼ばれなかったターン
（＝このフォールバック経路が動くターン）にDeliverableのUPDATEが抽出された場合。
`old_content` が短文なので保護が発火せず、`content = raw_content`（LLMの200字要約）で
上書きされる。この分岐のコメント（`12135-12139`）自身が
「versioned historyごとポインタが失われ、フル本文が孤立する」と警告している事故そのものが起きる。

**推奨対応**: F2と同じ。`get_latest_whiteboard(_conn, _run_id, phase_id, task_id) is not None`
で判定し、真なら `content = f"WHITEBOARD:{phase_id}:{task_id}"` を代入する。

---

### F6【低】`_resolve_deliverable_pointer`がSuperseded行を除外していない

**場所**: `cela_main.py:1926-1935`

```python
candidates = [
    a for a in agreements
    if a.get("entry_type") == "Deliverable"
    and (str(a.get("decision_what","")).startswith("FILE_PATH:") or ...startswith("WHITEBOARD:"))
    and (not task_id or a.get("task_id") == task_id)
    ...
]
best = max(candidates, key=lambda a: a.get("id", 0))
```

`status != "Superseded"` のフィルタが無い。`WHITEBOARD:` ポインタは結局 `task_id` から
最新版を引き直すため実害は小さいが、`FILE_PATH:` の場合は**アーカイブ済み・無効化済みの
古いファイル**を `read_deliverable_file` が返しうる。

なお本箇所は類型Bの判定（`startswith`）を**候補の絞り込み**に使っているため、
F2/F5とは逆に「短文行を自動的に除外する」方向に働いており、BL-212の状況下では
むしろ延命装置になっている。修正時はこの副作用に注意が必要。

**推奨対応**: 優先度は低い。F1/F2を直せば短文行自体が生まれなくなるため、
そのあとで `status` フィルタを追加するか判断する。

---

### F7【低】`_build_agreements_context`が`WHITEBOARD:`ポインタを生文字列のまま表示

**場所**: `cela_main.py:7036-7041`

```python
content_preview = a.get('decision_what', '')
if content_preview.startswith("FILE_PATH:"):
    content_preview = f"(ファイルに出力済み: {file_path})"
else:
    content_preview = content_preview[:150]
```

`FILE_PATH:` には親切なラベルが付くが、`WHITEBOARD:` は素通りして
`WHITEBOARD:phase_4:task_4_2` という生の内部表現がそのままLLMへ提示される。
機能上の実害はないが、LLMが「成果物の中身がこれだけ」と誤認する余地があり、
F1と同じ「ポインタと本文の混同」を助長する。

**推奨対応**: `WHITEBOARD:` にも `(ホワイトボードに記録済み: task_4_2 Ver.17)` のような
ラベルを付ける。低コストかつ低リスク。

---

## 5. まとめと推奨対応順序

| # | 深刻度 | 概要 | 推奨扱い |
|---|--------|------|----------|
| F1 | 高 | 最終統合文書に短文が載る | 新規BL |
| F2 | 高 | BL-212の修正漏れ（ポインタ復元） | **BL-212の追補** |
| F3 | 高 | 経路2の空文字ドリフト5フィールド＋スキーマ検証欠如 | 新規BL |
| F4 | 中 | BL-210の残穴（誤phase_id時） | **BL-210の追補** |
| F5 | 中 | 経路2にBL-212同型の文字列判定が残存 | **BL-212の追補**（F2と同時） |
| F6 | 低 | Superseded行が逆引き候補に混入 | 保留（F1/F2の後に再評価） |
| F7 | 低 | WHITEBOARD:ポインタの表示ラベル欠如 | 低リスク、ついでに実施 |

### 推奨する着手順

1. **F2 + F5**（BL-212追補）— 短文行が「生まれ続ける／伝播し続ける」大元を止める。
   これを先に止めないと、他を直しても汚染データが増え続ける。
2. **F1** — 既に汚染された状態でも最終文書が壊れないようにする（防御的）。
   F2の後でも、過去のrunで既に生まれた短文行に対する保険として必要。
3. **F3** — 経路2の検証層を追加する。最も設計判断を要するため、F2/F1で
   即応した後に落ち着いて設計する。
4. **F4** — 遷移の残穴。独立しているのでいつでもよい。
5. **F7**（ついで）→ **F6**（再評価）

### 設計上の提言

個別修正に加えて、**経路2（`decision_extractor`フォールバック）の位置づけそのものを
再考する価値がある**。この経路は「`write_agreement`が呼ばれなかったターンの安全網」として
導入されたが、現状では**検証を一切通さずに本番テーブルへ書き込む第2の正規経路**になっている。

選択肢は3つ考えられる。

- **(a) 検証層を追加して対称にする** — F3の推奨対応。改修量は中程度。
- **(b) 経路2の書き込みを`_write_agreement_impl`経由に統一する** — 根本的だが影響範囲が大きい。
  経路2は `caller_role='decision_extractor'` という特殊ロールで、BL-146/BL-169等の
  ロール別ゲートと衝突する可能性があり、慎重な設計が必要。
- **(c) 経路2を読み取り専用（issue起票・verified_facts保存のみ）へ縮退させる** —
  BL-139/BL-211の遷移補完のように「agreementsを書かない副作用」だけを残す。
  最も安全だが、`write_agreement`未使用ターンの成果物記録が失われる副作用の評価が必要。

本監査では判断材料の提示に留め、選択はユーザーに委ねる。

---

## 6. 監査で「問題なし」と確認した箇所

誤解を避けるため、疑って調べた結果**健全だった**箇所も記録する。

| 箇所 | 確認内容 |
|------|----------|
| `_write_agreement_impl` の必須チェック（`cela_main.py:3240`） | `if not args.get(f)` の真偽判定のため空文字も正しく弾く。類型Aの穴は無い |
| `_write_issue_impl` の `severity`（`cela_main.py:3477`） | `.get("severity","minor")` だが直後にenum検証があり空文字は弾かれる |
| `_write_issue_impl` の `defer_to_task_id`（`cela_main.py:3467-3471`） | すべて真偽判定（`if candidate_defer_to_task_id:`）で空文字を正しく扱っている |
| `get_latest_whiteboard`（`cela_main.py:5620`） | BL-131によりtask_id単独検索。phase_id不一致は警告のみ。健全 |
| `_find_active_deliverable_agreement`（`cela_main.py:2978`） | BL-206によりtask_id単独検索へ修正済み。健全 |
| `_is_task_completed`（`cela_main.py:5592`） | 最新Deliverable行のstatusのみを見る。BL-212の短文行が最新の場合は`Rejected`となりゲートが閉じる＝フェイルクローズ側。健全 |
| `_resolve_task_transition` の BL-125 / BL-176 ゲート | F4の経路（誤phase_id）でも、遷移が拒否される側に倒れるためゲート自体は迂回されない |

---

## 7. 参照

- `docs/design/back_log/issue_backlog.md`: BL-206、BL-210、BL-211、BL-212、BL-139、BL-131、BL-084、BL-062、BL-080
- `docs/design/decision_log.md`: D-183（識別はtask_id単独）、D-184（フェーズ解決の優先順位）、D-185（遷移意図の回収）、D-186（whiteboard_draftsを権威とする）
- 実ログ: `log/2026-08-11/0941`、`log/2026-08-11/1034`
- 実DB: `cela.db`（run_id=`1786337594-17df8ff3`）
