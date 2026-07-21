# NPU-Context-Saver 参考メモ（議論用、未決定）

> **位置づけ:** このファイルは `decision_log.md`/`issue_backlog.md`/要件定義書のような正式なドキュメントではない。
> CELAの前身プロジェクト `C:\ai_work\NPU-Context-Saver`（VS Code拡張、LDD＝Lineage-Driven Development手法の実装）を読み、
> CELAの設計に使えそうだと判断した点を、**後で議論するための一時メモ**としてまとめたもの。
> ここに書かれている内容はまだ要件定義書には反映されておらず、採用するかどうかは未確定。
>
> 起点となった議論: [decision_lineage.md 論点38〜39](decision_lineage.md)（BL-036・BL-037、reason記載の薄さ・数値ドリフトの議論）

---

## 1. NPU-Context-SaverとCELAの関係

`C:\ai_work\NPU-Context-Saver` は、CELAの前身にあたる別プロジェクト（TypeScript製VS Code拡張、Cursor/Cline連携）。「LDD（Lineage-Driven Development）」という方法論の実装で、核心思想は：

> "Git manages code lineage. LDD manages decision lineage."
> （Gitはコードの系譜を管理する。LDDは決定の系譜を管理する。）

AI会話が長くなるとコンテキストが劣化・崩壊し、新しいチャットは毎回ゼロから始まる、という問題（Context Decay / Cold Start Problem）に対し、「会話ログを使い捨てにせず、意思決定を第一級の開発資産として構造化・継承する」ことを目指していた。CELAの要件定義書の思想（決定の系譜、正負の理由の資産化、Hydrate Refresh）は、この前身プロジェクトから直接受け継がれている。

**思想的な違い（2026-07-21の議論で確認済み）:** NPU-Context-Saverの最終目的は「**チャット間**でどう文脈を引き継ぐか」であり、1つの`hydrateContext.md`ファイルに情報を集約して次のチャットへ注入する設計。CELAでは、ステートレスモードで動くAI各役割の**最初のプロンプトに何を見せるか**という部分に相当する。ただしCELAはNPUと異なりSQLiteという構造化DBを最初から正本として持てる立場にあるため、「hydrate.md 1枚に全部詰め込む」というNPU側の設計（後述の通り実際に肥大化に悩んでいた）をそのまま輸入するのではなく、**「初期プロンプトには最小限＋地図（索引）だけを見せ、詳細はAI自身が能動的にDB/ファイルから引く」**という方向で応用するのが良い、という結論にひとまず達している（詳細は§4）。

---

## 2. 実際に動いていたもの（BACKLOG.mdでClosed、smoke test PASS済み）

| 項目 | NPU側の実装 | CELAとの関連 |
|------|------------|--------------|
| **RAG＋ピン＋トークン上限**（BL-023 closed） | `src/HydrateSelection.ts`。会話履歴の検索に時間減衰性を持たせつつ、重要ノード（`ARCH_DESIGN`等）はピン留めして減衰から除外。トークン予算に応じて選択数を自動調整。smoke testで実測（70/155ノード ~5.9k tok）確認済み | 昨日議論したF-8.4（時間減衰検索・決定/否決ターンの自動セイリエンス固定）のまさに実装本体。実証済みの設計として参照価値が高い |
| **Hydrate 5節合成**（BL-057〜059 closed） | `HydrateWhatWhyBuilder.ts` / `HydrateFiveSectionBuilder.ts` / `SegmentSynthesizer.ts`。What/Why/Current/Open/Nextの5節を、Segment（章）とDecisionPairから自動合成 | CELAの要件定義書F-8.2「Hydrate Refresh 5節プロトコル」の直接の原型 |
| **Freeze（神ノードピン）** | `is_frozen`フラグで重要ノードを履歴切り詰め対象から除外 | CELAのF-8.3と同一概念 |

---

## 3. 設計は緻密だが未実装だったもの（＝アイデアとして参考価値が高い）

これらはNPU-Context-Saver自身のBACKLOG.mdでも`Open`のまま（2026-06-16時点）で、**実証はされていない設計**である点に注意。

### 3.1 3段グラデーション（Zone A/B/C、BL-064）

出典: `docs/hydrate-index-expand-spec.md` v0.3

```text
tip ──────────────────────────────→ 古い
|←── Zone A: 直近N ──→|←── Zone B: N+1〜M ──→|← Zone C: M+1〜 ─→|
  生（全文）              Exchange可読              豊かな索引1行
```

- **Zone A**（既定N=10）: 生の全文（USER raw + AI raw）
- **Zone B**（既定M=30上限、トークン予算で自動縮小）: Decision/Reason/Evidence付きの読める要約（AI生テキストは含まない）
- **Zone C**（M+1以降）: **「豊かな索引」**1行。**IDのみの索引は禁止**、最低限トピック・ステータス・1行サマリを必須化：

  ```text
  | ex{id8} | {phase}/{authority}/{status} | nodes: {A_id8},{U_id8} | {1行サマリ} |
  ```

  サマリの優先順位: ①ユーザーの決定文の先頭40字 → ②AIのdecision/reason → ③hypothesis_decisionの先頭80字 → ④trigger先頭60字

- **ピン留め例外**: `ARCH_DESIGN`／`verbatim USER`／`DecisionPair`のproposal+bindingは、古くても最低Zone Bに昇格（索引だけに落とさない）

**CELAへの示唆:** 現状CELAの`_build_agreements_context`は「(ファイルに出力済み: path)」という素っ気ないポインタのみをDeliverableに対して表示している（BL-034参照）。これはNPUの用語で言えば「Zone Cなのに1行サマリすら持たない索引」に相当し、Zone Cの最低要件（トピック＋ステータス＋1行サマリ）を満たしていない。ここを引き上げるのがF-3.9の設計課題の一つになりうる。

### 3.2 6軸判断タクソノミ（Intent/Question/Decision/Reason/Evidence/Action、BL-063）

出典: `docs/lineage-human-intent-spec.md` §3.5〜3.6

| 軸 | 答える問い | 備考 |
|----|-----------|------|
| Intent | 何をしたいか | |
| Question | 未決の問い | |
| **Decision** | 何を選んだか（What） | |
| **Reason** | なぜそうしたか（Why） | |
| **Evidence** | 何が証明したか（Proof） | **実測・ログのみ。理由文の混入は禁止** |
| Action | 次に何をするか | |

**監査の読み順（厳守）:** Decision → Reason → Evidence。

NPU側の課題認識（原文ママの要約）:「`hypothesis_decision`（COMPASS）にDecision＋Reason＋却下案が混在している」「`evidence`に理由文が押し込まれがち」——これは**CELAのDetectorログで見つけた「reason_whyが薄い」症状（BL-037）とほぼ同じ課題認識**であり、興味深い一致。NPU側はこれをDecision/Reason/Evidenceの3フィールド分離という具体的なスキーマ変更で対処しようとしていた（実装は`open`のまま）。

**CELAへの示唆:** BL-037の解決策として、Agreement/verified_factsのスキーマに「evidence（実測・出典のみ）」を独立フィールドとして持たせ、`reason_why`とは明確に役割分担させる案がありうる。

### 3.3 DecisionPair（提案→判断のペア）

```typescript
interface DecisionPair {
  pair_id: string;
  proposal_snapshot_id: string;  // A（提案）
  binding_snapshot_id: string;   // U（判断・確定）
  chosen: string;
  rejected?: string[];
}
```

CELAの`action_type: CREATE/UPDATE`＋`status`より一段厳密に、「提案」と「確定」を別ノードとして明示的にリンクする構造。

### 3.4 Segmentモデル（`authority`・`confidence`・`superseded_by`）

```typescript
interface ThreadSegment {
  segment_kind: 'inquire' | 'propose' | 'decide' | 'implement' | 'manual_edit' | 'meta' | 'pipeline_incident';
  rejected?: string[];
  confidence: number;        // 0..1
  authority: 'proposed' | 'binding' | 'confirmed';  // confirmed = 人間承認
  superseded_by?: string;
}
```

**CELAへの示唆:** 2026-07-21の議論で出た「暫定値／確定値の区別」は、NPUではまさに`authority`フィールド（proposed/binding/confirmed）として既に実装設計されていた。さらに`confidence`という数値信頼度も持たせており、CELAのF-3.9で検討している「暫定/確定」の二値区分より一段リッチ。`superseded_by`はCELAの`status="Superseded"`より一歩進んで「何に上書きされたか」を明示的に参照できる。

### 3.5 GoalShiftEvent（目標ドリフト検知、BL-062）

出典: `docs/lineage-human-intent-spec.md` §9.2

```typescript
type GoalShiftKind =
  | 'scope_expand' | 'scope_narrow' | 'priority_reorder'
  | 'architecture_pivot' | 'constraint_hit' | 'silent_drift';
```

検知シグナル例（一部）:

| shift_kind | 典型シグナル |
|------------|--------------|
| scope_expand | Open BL集合増、新Phase節、segment intent拡張＋decide |
| silent_drift | binding無し・Open同じ・segment.intent距離↑ |

**CELAへの示唆:** CELAの要件定義書F-22.4「GoalShiftEvent」は既にこの概念を継承しているが、具体的な検知シグナルの分類までは持っていない。将来、reflection/facilitator（BL-005）を再設計する際の参考になりうる。

### 3.6 ADR自動出力（BL-046）

`AI_Implement_log.md`の開発日記を`docs/adr/NNNN-*.md`へ自動分割。5大基準（Trigger/Decision/Evidence/Open/Next）→ Context/Decision/Consequences形式のADRへ変換。

**CELAへの示唆:** これは今回のセッション中、私（Claude）が`decision_log.md`に手作業で行っていること（D-001〜D-035の記録）の自動化に相当する。CELA自体の開発体制（AGENTS.md §4.9）にも将来応用できるかもしれない。

### 3.7 「Agentが能動的にexpandする」発動条件

出典: `docs/hydrate-index-expand-spec.md` §7.2

- Zone C索引のみでbinding/decideの根拠が不足しているとき
- ユーザーが過去の判断の根拠を質問したとき
- 5節のWhyに「詳細はnode xxx」とあるとき

**CELAへの示唆:** F-3.8（読み取りツール）に今欠けている「いつAIがツールを呼ぶべきか」という発動条件の具体例として使える。

---

## 4. 2026-07-21の議論で得た暫定結論（要件定義書には未反映）

1. **CELAはNPUの「hydrate.md 1枚に全部詰め込む」パターンをそのまま輸入しない。** NPU側もhydrateファイル自体がかなり肥大化していることが確認できる（`hydrateContext.debug.refresh.md`が211KB）。
2. **代わりに三層構造で考える案:**
   - **第1層（初期プロンプトに直接載せる）**: 直近の生の会話、現在タスク内の確定値。現状のCELAに近い。
   - **第2層（初期プロンプトには“地図”だけ載せる）**: 他にどんなトピックがあり、どう決まっていて、どこを見れば詳細が分かるか、という索引。NPUのZone C「豊かな索引」の考え方を参考に、`(ファイルに出力済み: path)`という素っ気ないポインタを「トピック＋ステータス＋Reason1行」まで引き上げる。ただし**中身そのものは載せない**。
   - **第3層（F-3.8/F-3.9のツール経由でのみ取得）**: 構造化ファクトストア（トピック→値・理由・引用元）、Deliverable本文。
3. **NPUの「N=10 / M=30」等の具体的な定数はそのまま流用しない。** NPUの1ターン＝チャットバブル（数十〜数百字）だが、CELAの1ターン＝Markdownレポート丸ごと（数千〜数万字）のことがあり、粒度がまったく違う。輸入するのは**設計思想（段階化・ピン留め例外・豊かな索引）**であり、数値はCELA自身のトークン特性から再チューニングが必要。

---

## 5. 今後の議論の切り口（未決）

- 3段グラデーション（Zone A/B/C）を、CELAの`chat_history`（生会話）とAgreement DB（`_build_agreements_context`）のどちらに、あるいは両方にどう適用するか。
- 第2層の「地図」を具体的にどんなフォーマットにするか（NPUのZone C索引行フォーマットを土台に、CELAのトピック粒度でどう変えるか）。
- Decision/Reason/Evidenceの3分離（BL-063相当）を、CELAのAgreementスキーマにどう反映するか（新規カラム追加か、reason_why内でのルール強化に留めるか）。
- `authority`（proposed/binding/confirmed）や`confidence`を、CELAの`status`enumにどこまで取り込むか。
- GoalShiftEvent（F-22.4）の検知シグナルを、BL-005（reflection/facilitator復旧）と合わせてどう具体化するか。
- これらをどの粒度でF-3.8/F-3.9/F-8.4に統合するか、あるいは新しいF番号を割り当てるか。

---

## 6. 参照元ファイル一覧（`C:\ai_work\NPU-Context-Saver`内）

| ファイル | 内容 |
|----------|------|
| `PROJECT_INDEX.md` | アーキテクチャ全体像、データモデル、コマンド一覧 |
| `BACKLOG.md` | Open/Closedタスク台帳（実装状況の一次情報） |
| `docs/Lineage-Driven Development (LDD) README.md` | LDD方法論のマニフェスト |
| `docs/hydrate-index-expand-spec.md` | 3段グラデーション（Zone A/B/C）仕様、BL-064 |
| `docs/lineage-human-intent-spec.md` | Human Intent抽出・6軸タクソノミ・DecisionPair・GoalShiftEvent仕様、BL-057〜062 |
