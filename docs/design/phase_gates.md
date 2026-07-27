# Phase Exit Criteria（完了定義）— FEATURE_NAME

各 Phase の **Done** を誰が見ても同じ判断できるように定義する。

| ドキュメント | 役割 |
|-------------|------|
| 本書 | Phase / プロジェクト全体の完了判定 |
| `rN_*/` 各詳細設計書（[r0_planning/](r0_planning/) 等） | 実装詳細・How |
| [issue_backlog.md](../back_log/issue_backlog.md) | 残タスク（BL） |
| [要件定義書_v35.md](要件定義書_v35.md) | 要件マスター |

関連: [STATUS.md](STATUS.md) | [traceability.md](traceability.md) | [README.md](README.md)

---

## プロジェクト Close 条件

| # | 条件 | 検証方法 | 状態 |
|---|------|----------|------|
| G-1 | （記入: 受け入れ条件） | | ☐ |
| G-2 | （記入） | | ☐ |
| G-3 | [traceability.md](traceability.md) AC すべて達成 | | ☐ |
| G-4 | Phase 0〜N の Exit すべて達成 | 本書 | ☐ |

---

## Phase 0 — 方針・調査

**目的:** （記入）

| # | Exit 条件 | 状態 |
|---|-----------|------|
| P0-1 | （記入） | ☐ |
| P0-2 | 決定が [decision_log.md](decision_log.md) に記録されている | ☐ |

---

## Phase 1 — R1: SQLite永続化基盤

**目的:** 既存プロトタイプの`state["decisions"]`/`state["agreements"]`（Python list）をSQLiteへ置き換える。グラフ構造・ノード構成は変更しない。

**スコープ外:** ツール呼び出し・`write_agreement_tool`（R2/R3）、`whiteboard_drafts`書き込み（R4）

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P1-1 | 設計書が存在する | `cela_r1_r2_r3b_design_v7.md`, `cela_r1_impl_Plan.md` | ☑ |
| P1-2 | 実装が設計に沿う | 照合済み（DB層・LineageState・全ノードのDB経由化・system_prompt=[]バグ修正・Replayスタブ） | ☑ |
| P1-3 | 必須 BL が `done` または合意延期 | BL-001（R2着手前判断で延期合意）、BL-004（P3のため延期） | ☑（延期合意） |
| P1-4 | ドライラン / 試験合格（R1スコープ） | スモークテスト・構文チェックはPass（T-3, T-4）。実データによる**構造的一致**（list版⇔SQLite版、agreements/decisions件数・status分布・順序）はT-5でPass、BL-003 done | ☑ |

**Phase 1 Done = 上記すべて ☑**

**注記（[D-002](decision_log.md)、2026-07-18）**: 設計書§0の対応表は§5評価メトリクス（指標A・B・C）を元々「R1〜R3共通」と分類している。実データドライラン（T-5）で、F-2.6検算ゲート（Python REPL、R2実装）が無いことに起因する差し戻しが多発することが確認されたため、指標A・B・Cの本格的な実測比較はR2実装後に行う（BL-002、`blocked`）。これはR1固有のスコープ（SQLite永続化・グラフトポロジ維持）の検証を妨げるものではなく、P1-4はR1スコープの構造的検証（上記）をもって達成とする。指標A・B・Cの実測はPhase 2（R2）以降のExit条件として引き継ぐ。

---

## Phase 2 — R2: ツール呼び出し基盤・機械的検算ゲート

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P2-1 | F-2.6機械的検算ゲート（Python REPL）実装 | `cela_r1_r2_r3b_design_v7.md §3.5.3` | ☑ |
| P2-2 | 評価メトリクスA（却下案の回避率）・B（制約の維持率）・C（収束性とコストのトレードオフ、最低5試行）の実測比較（[BL-002](../back_log/issue_backlog.md)、[D-002](decision_log.md)） | `traceability.md` T-* | ☑（**D-002と同様の扱いでクローズ、2026-07-21・D-036**。指標D実測はT-7・T-8で完了。指標A・Bは全18タスク完走（T-10）で定性確認。指標Cは、BL-023適用前のベースライン試行を別途用意するコストが見合わないため実測を見送り、**R3a（自律的DB/ファイル読み取り、F-3.8/F-3.9）完了後の再ドライランへ振り替える**（[decision_log.md D-036](decision_log.md)）） |

**注記（2026-07-19、本番ハードニング）**: P2-1のコード実装完了後、本番ドライランでBL-014（`python_repl`状態非保持による非収束）・BL-016（探索的タスクのツールループ非収束）・BL-019（reasoningパラメータ無効化）・BL-020（言語逸脱）・BL-022（OpenRouter壊れたレスポンスによる未捕捉クラッシュ）が発見・修正された（[STATUS.md](STATUS.md)、`decision_log.md` D-014〜D-019参照）。P2-1自体の判定に変更はないが、R3着手前の前提条件として位置づけていたBL-016が解消したことにより、**ロードマップ上はR3着手が可能な状態**（BL-005・BL-015・BL-017・BL-018・BL-021はR4着手時にまとめて対応する方針で合意済み、R3の非ブロッカー）。

**注記（2026-07-21、D-036・R2クローズ）**: T-10ドライランのレビューで発見したBL-035（フェーズ横断`verified_facts`参照不能）・BL-036（財務・需要数値ドリフト）・BL-037（`reason_why`の薄さ）は、いずれも「自律的読み取り」の欠落が根本原因であり、R2の指標C実測（P2-2）よりも先に着手すべき優先度が高いと判断した。したがってP2-2は指標A・Bの定性確認と指標D実測をもって構造的にクローズし、指標Cの定量実測はR3a完了後へ振り替える。R2はここで**Done**とする。

---

## Phase 3 — R3: 自律的DB読み取り・書き込みへの移行（D-036でR3a/R3bに再編）

**目的**: 旧来のR3（`write_agreement_tool`による自律書き込み）に加え、T-10で発見したBL-035/036/037の解消に必要な自律読み取り（F-3.8/F-3.9）をR3aとして先行実装する。

**スコープ外:** `whiteboard_drafts`書き込み・差分パッチ（R4）

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P3a-1 | F-3.8（自律的DB/ファイル読み取りツール）実装 | `cela_r1_r2_r3b_design_v7.md`（該当節追記予定）、`cela_r4_design.md`冒頭の前提注記 | ☑（2026-07-24確認: `READ_VERIFIED_FACT_TOOL`/`READ_DELIVERABLE_FILE_TOOL`と`_read_verified_fact_handler`/`_read_deliverable_file_handler`が実装済み、Expert/Detector/Reviewer/Arbiter/Integrator/User AI全員のtoolsに配線済み。STATUS.md「R3a/R3b実装完了」と整合） |
| P3a-2 | F-3.9（構造化ファクトストア、`{topic, value, reason, citations}`、confirmed/provisional区別）実装 | 同上 | ☑（2026-07-24確認: `verified_facts`テーブルに`reason`/`citations`/`confidence`列実装済み、`upsert_verified_fact`/`get_verified_facts_from_db`で読み書き確認） |
| P3a-3 | BL-035/BL-036/BL-037と同一構成での再ドライランを実施し、Phase 6最終統合での財務・需要数値ドリフトが解消されていること、Detectorの「根拠が不明」判定頻度が有意に減少していることを確認 | `traceability.md` T-* | ☐（未実施。BL-035/036/037は`issue_backlog.md`上も引き続き`open`のまま） |
| P3a-4 | 指標C（収束性とコストのトレードオフ、R2版とR3a版の比較、最低5試行）の実測比較 | `traceability.md` T-*（P2-2から振り替え） | ☐（未実施） |
| P3b-1 | `write_agreement_tool`（F-3.1・F-3.2）実装、`decision_extractor_node`を予備的セーフティネットへ格下げ | `cela_r1_r2_r3b_design_v7.md §3.2〜3.4.1` | ☑（2026-07-24確認: `WRITE_AGREEMENT_TOOL`/`_check_write_permission`/`_commit_agreement_from_tool`実装済み。decision_extractor_nodeは`wrote_agreement_this_turn`判定によりwrite_agreement未使用時のみ書き込む安全網へ格下げ済み、R3b §3.5.1） |
| P3b-2 | 指標A・E・F（自律書き込みカバレッジ80%以上、取りこぼし率20%以下等）の実測比較 | `traceability.md` T-* | ☐（未実施） |

**Phase 3 Done = P3a-1〜P3a-4、P3b-1〜P3b-2 すべて ☑**（**R3aが先に完了し次第、R3aのみでR4着手判断は行わない** — R4はR3a＋R3bの両方の完了を前提とする、`cela_r4_design.md`参照）。**2026-07-24時点: 実装系（P3a-1・P3a-2・P3b-1）は☑だが、測定・再検証系（P3a-3・P3a-4・P3b-2）は未実施のためPhase 3自体はまだDoneではない。**

---

## Phase 4 — R4: ホワイトボード差分パッチ化

**目的**: Deliverableの更新をファイル全文の再生成ではなく、`whiteboard_drafts`テーブルへの差分パッチ（Claude Code Editツール方式）で管理する。

**スコープ外:** 思考プロセス監査・Freeze・GoalShiftEvent（R5）

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P4-1 | `whiteboard_drafts`のCRUD（`get_latest_whiteboard`/`apply_whiteboard_patch`）・`_apply_text_edits`実装 | `cela_r4_design.md`、`tests/test_r4_smoke.py` | ☑ |
| P4-2 | `WRITE_AGREEMENT_TOOL`への`edits`パラメータ追加、Deliverable主経路のwhiteboard方式への全面移行 | 同上 | ☑ |
| P4-3 | ~~ロールバック機構（F-7.3、Detectorのmajor判定と連携）~~ → **BL-075/D-047（2026-07-24）で撤廃**。「1つ前のバージョンは健全」という前提が実運用で成立せず、修正済み問題を無警告で再導入するバグが実ドライランで確認されたため、部分修正誘導プロンプトへ置き換え | `tests/test_bl075_no_whiteboard_rollback.py` | ☑（撤廃により対応不要） |
| P4-4 | オフラインスモークテスト合格 | `tests/test_r4_smoke.py`（14件）＋`test_r3_smoke.py`更新分、計64件Pass | ☑ |
| P4-5 | 実LLM再ドライランでのA/Bテスト（トークン消費・矛盾の早期発見率・ロールバック正確性） | `traceability.md` T-*（未記入） | ☐（未実施） |

**Phase 4 Done = P4-1〜P4-5 すべて ☑**（2026-07-24時点: 実装系P4-1〜P4-4は☑、P4-5は未実施のためPhase 4自体はまだDoneではない）

---

## Phase 5 — R5: 思考プロセス監査／F-3.7思考ログ強制記録／F-8.3 Freeze／GoalShiftEvent

**目的**: `cela_r5_design_v2.md`が定義する新規要件群（要件定義書の実証実験・付録Aから生まれた要件）を実装する。

| # | Exit 条件 | 検証方法 | 状態 |
|---|-----------|----------|------|
| P5-1 | F-2.1拡張（`_query_AI_live`のreasoning捕捉、Detectorへの思考プロセス監査ブロック）実装 | `cela_r5_design_v2.md` §1、`tests/test_r5_thought_log_freeze_goalshift.py` | ☑ |
| P5-2 | F-3.7（`internal_thought_process`の限定記録: Detector major・Reflection stagnant・agreements Rejected時のみ）実装 | 同上 §2 | ☑ |
| P5-3 | F-8.3 Freeze（専用ツール、`user`ロール限定、SUPERSEDE/UPDATEガード）実装 | 同上 §3、D-044 | ☑（**2026-07-24、D-045によりFreezeは一時休止中** — 本体・ガード・表示ロジックは温存、User AIのtoolsからは除去） |
| P5-4 | GoalShiftEvent（`goal_shift_events`テーブル、`detect_goal_shift`、`arbiter_node`配線）実装 | 同上 §4 | ☑（書き込みのみ。読み出し・Hydrate表示への反映はBL-065として分離、未着手） |
| P5-5 | BL-062（Detectorのmajor判定が既存Approved agreementを構造的に無効化できない問題）の解消 | `tests/test_bl062_detector_supersede.py` | ☑（**Detector限定**。Reviewer/Arbiter/Integratorへの拡張はBL-070として分離、未着手） |
| P5-6 | オフラインスモークテスト合格 | `tests/test_r5_thought_log_freeze_goalshift.py`（14件）＋`test_bl062_detector_supersede.py`（4件）含め計100件Pass、`python -m py_compile`合格 | ☑ |
| P5-7 | 実LLM再ドライランでの効果確認（Detector SUPERSEDEの実発火、Freeze不使用の確認、GoalShiftEventの実発火、思考プロセス監査の実効性） | `traceability.md` T-*（未記入） | ☐（未実施） |

**Phase 5 Done = P5-1〜P5-7 すべて ☑**（2026-07-24時点: 実装・オフライン検証系P5-1〜P5-6は☑、P5-7は未実施のためPhase 5自体はまだDoneではない。BL-065〜070は本Phaseの後続課題として`open`のまま`issue_backlog.md`に記録）

---

## サインオフ

| Phase | 完了日 | 判定者 | 備考 |
|-------|--------|--------|------|
| Phase 0 | | | |
| Phase 1 | 2026-07-18 | t-momose | P1-1〜P1-4すべて☑。指標A・B・C実測はD-002によりP2-2へ引き継ぎ済み |
| Phase 2 | 2026-07-21 | t-momose | P2-1・P2-2すべて☑。指標Cの実測はD-036によりP3a-4へ引き継ぎ済み |
| Project Close | | | |
