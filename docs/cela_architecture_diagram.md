# CELA — ノード・アーキテクチャ図

```mermaid
graph TB

    %% =====================================================================
    %% スタイル定義
    %% =====================================================================
    classDef entry      fill:#1a1a2e,stroke:#e94560,stroke-width:3,color:#eee,font-weight:bold
    classDef planning   fill:#16213e,stroke:#0f3460,stroke-width:2,color:#a8d8ea,font-weight:bold
    classDef user       fill:#1b4332,stroke:#95d5b2,stroke-width:2,color:#d8f3dc,font-weight:bold
    classDef expert     fill:#4a1942,stroke:#c77dff,stroke-width:2,color:#e0aaff,font-weight:bold
    classDef extractor  fill:#3a2a1a,stroke:#e09f3e,stroke-width:2,color:#fcedda,font-weight:bold
    classDef detector   fill:#4a0000,stroke:#ff6b6b,stroke-width:2,color:#ffcccc,font-weight:bold
    classDef audit      fill:#2d2d2d,stroke:#adb5bd,stroke-width:2,color:#dee2e6,font-weight:bold
    classDef final      fill:#0b525b,stroke:#7b2cbf,stroke-width:3,color:#e0aaff,font-weight:bold
    classDef routing    fill:#222,stroke:#666,stroke-width:1,color:#999,font-style:italic

    %% =====================================================================
    %% ルーティング関数（判断ノード）
    %% =====================================================================
    R1[route_after_task_plan_reviewer]:::routing
    R2[route_after_user_detector]:::routing
    R3[route_after_user_decision]:::routing
    R4[route_after_expert_detector]:::routing
    R5[route_after_expert_decision]:::routing
    R6[route_after_reflection]:::routing
    R7[route_after_integrator]:::routing
    R8[route_after_arbiter]:::routing
    R9[route_after_facilitator]:::routing
    R10[route_after_reviewer]:::routing

    %% =====================================================================
    %% ノード定義（役割ごとにグループ化）
    %% =====================================================================

    subgraph Entry["🟥 エントリー（フェーズ0）"]
        GE[goal_essence_node<br/><small>目標の本質を壁打ち<br/>True Essence Analyst</small>]:::entry
        TP[task_planner_node<br/><small>目標→フェーズ・タスク分解<br/>Task Planner</small>]:::entry
        TPR[task_plan_reviewer_node<br/><small>計画実行前レビューゲート<br/>Task Plan Reviewer</small>]:::entry
    end

    subgraph Loop["🔄 メインループ（User ↔ Expert 対話）"]
        direction TB

        subgraph UserSide["🟢 User AI（発注者）側"]
            UU[generate_user_utterance_node<br/><small>User AI発言生成<br/>発注者ロール</small>]:::user
            UD[user_detector<br/><small>User発言監査<br/>Detector（共用）</small>]:::detector
            UE[user_decision_extractor<br/><small>User発言→合意抽出<br/>Decision Extractor（共用）</small>]:::extractor
        end

        subgraph ExpertSide["🟣 Expert AI（作業者）側"]
            ORC[orchestrator_node<br/><small>専門家選定<br/>Orchestrator</small>]:::expert
            EXP[expert_node<br/><small>専門家実行<br/>Expert</small>]:::expert
            ED[expert_detector<br/><small>Expert発言監査<br/>Detector（共用）</small>]:::detector
            EE[expert_decision_extractor<br/><small>Expert発言→合意抽出<br/>Decision Extractor（共用）</small>]:::extractor
        end
    end

    subgraph Audit["⚫ 内省・ファシリテーション"]
        REF[reflection_node<br/><small>包括監査・停滞検出<br/>Reflection</small>]:::audit
        FAC[facilitator_node<br/><small>軌道修正・視座提供<br/>Facilitator</small>]:::audit
    end

    subgraph FinalIntegration["🔷 最終統合・審査"]
        INT[integrator_node<br/><small>成果物物理結合<br/>Lineage付与＋矛盾検出</small>]:::final
        ARB[arbiter_node<br/><small>リソース超過調停<br/>Resource Arbiter</small>]:::final
        REV[reviewer_node<br/><small>QA最終審査<br/>Reviewer</small>]:::final
        HALT[halt_node<br/><small>システム停止</small>]:::final
    end

    %% =====================================================================
    %% エッジ接続
    %% =====================================================================

    %% --- エントリー ---
    GE --> TP
    TP --> TPR

    %% --- ルーティング: 計画レビュー結果 ---
    TPR --> R1
    R1 -- "phases 未確定<br/>（差し戻し）" --> TP
    R1 -- "phases 確定<br/>（承認）" --> UU

    %% --- User AI 側フロー ---
    UU --> UD
    UD --> R2
    R2 -- "major / halt（リトライ ≤3）" --> UU
    R2 -- "major / halt（リトライ >3）" --> REF
    R2 -- "none / minor" --> UE

    UE --> R3
    R3 -- halt --> HALT
    R3 -- ready_for_review --> INT
    R3 -- 通常指示 --> ORC

    %% --- Expert AI 側フロー ---
    ORC --> EXP
    EXP --> ED
    ED --> R4
    R4 -- "major / halt（リトライ ≤3）" --> EXP
    R4 -- "major / halt（リトライ >3）" --> REF
    R4 -- "none / minor" --> EE

    EE --> R5
    R5 -- halt --> HALT
    R5 -- "round % interval == 0" --> REF
    R5 -- 通常 --> UU

    %% --- 内省・ファシリテーション ---
    REF --> R6
    R6 -- halt --> HALT
    R6 -- ready_for_review --> INT
    R6 -- stagnant / drift --> FAC
    R6 -- completed --> INT
    R6 -- "continuing（end_turn）" --> END_REF[END]:::routing

    FAC --> R9
    R9 -- halt --> HALT
    R9 -- end_turn --> END_FAC[END]:::routing

    %% --- 最終統合 ---
    INT -.-> R7
    R7 -- needs_revision_phases --> ORC
    R7 -- normal --> ARB

    ARB -.-> R8
    R8 -- phases_to_revise --> ORC
    R8 -- normal --> REV

    REV -.-> R10
    R10 -- halt --> HALT
    R10 -- is_completed --> END_REV[END]:::routing
    R10 -- normal --> ORC

    HALT --> END_HALT[END]:::routing
```

## ノード一覧

| # | ノード名 | グラフ上のラベル | 役割 | 使用される関数 |
|---|----------|------------------|------|----------------|
| 1 | `goal_essence_node` | 🟥 Entry | 目標の本質を壁打ち | `call_goal_essence_analyst()` |
| 2 | `task_planner_node` | 🟥 Entry | 目標→フェーズ・タスク分解 | `call_task_planner()` |
| 3 | `task_plan_reviewer_node` | 🟥 Entry | 計画実行前レビューゲート | `call_task_plan_reviewer()` |
| 4 | `generate_user_utterance_node` | 🟢 User | User AI発言生成（発注者役） | `generate_user_utterance()` |
| 5 | `user_detector` | 🔴 Detector | User発言の安全性・制約監査 | `detector_node()` / `call_detector()` |
| 6 | `user_decision_extractor` | 🟠 Extractor | User発言から合意・決定を抽出 | `decision_extractor_node()` / `call_decision_extractor()` |
| 7 | `orchestrator_node` | 🟣 Expert | タスクに最適な専門家を選定 | `call_orchestrator()` |
| 8 | `expert_node` | 🟣 Expert | 選定された専門家がタスクを実行 | `call_expert()` |
| 9 | `expert_detector` | 🔴 Detector | Expert提案の安全性・制約監査 | `detector_node()` / `call_detector()` |
| 10 | `expert_decision_extractor` | 🟠 Extractor | Expert発言から合意・決定を抽出 | `decision_extractor_node()` / `call_decision_extractor()` |
| 11 | `reflection_node` | ⚫ Audit | 包括監査（停滞・ドリフト・完了判定） | `call_reflection()` |
| 12 | `facilitator_node` | ⚫ Audit | 議論の軌道修正・視座提供 | `call_facilitator()` |
| 13 | `integrator_node` | 🔷 Final | 全成果物の物理結合＋矛盾検出 | `call_integrator()` + `verify_budget_arithmetic()` |
| 14 | `arbiter_node` | 🔷 Final | リソース超過時の再配分調停 | `call_resource_arbiter()` |
| 15 | `reviewer_node` | 🔷 Final | QA最終審査（passed / failed） | `call_reviewer()` |
| 16 | `halt_node` | 🔷 Final | 直ちにシステムを停止 | — |

## ルーティング判断一覧

| 判断関数 | 出発ノード | 分岐先候補 | 判定条件 |
|----------|-----------|------------|----------|
| `route_after_task_plan_reviewer` | `task_plan_reviewer` | `task_planner` / `generate_user_utterance` | phases クリア(major)なら差し戻し、確定なら次へ |
| `route_after_user_detector` | `user_detector` | `generate_user_utterance` / `user_decision_extractor` / `reflection` | major→リトライ≤3は差し戻し、>3は内省へ。none/minorは抽出へ |
| `route_after_user_decision` | `user_decision_extractor` | `halt` / `integrator` / `orchestrator` | halt最優先→ready_for_review(完了宣言)は統合へ→通常は専門家選定へ |
| `route_after_expert_detector` | `expert_detector` | `expert` / `expert_decision_extractor` / `reflection` | major→リトライ≤3は差し戻し、>3は内省へ。none/minorは抽出へ |
| `route_after_expert_decision` | `expert_decision_extractor` | `halt` / `reflection` / `generate_user_utterance` | halt最優先→roundがintervalで割り切れれば内省→通常はUser AIへ |
| `route_after_reflection` | `reflection` | `halt` / `facilitator` / `integrator` / END | halt最優先→ready_for_review→stagnant→completed→終了 |
| `route_after_integrator` | `integrator` | `orchestrator` / `arbiter` | 改訂必要なら専門家選定へ戻る、正常なら調停へ |
| `route_after_arbiter` | `arbiter` | `orchestrator` / `reviewer` | 再配分が必要なら専門家選定へ戻る、完了ならQA審査へ |
| `route_after_facilitator` | `facilitator` | `halt` / END | halt→停止、通常は終了（次のラウンドへ） |
| `route_after_reviewer` | `reviewer` | `halt` / END / `orchestrator` | halt→停止、passed→完了、failed→修正のため専門家選定へ |

## 主要な処理の流れ（サマリー）

```mermaid
sequenceDiagram
    participant GE as Goal Essence
    participant TP as Task Planner
    participant TPR as Task Plan Reviewer
    participant UU as User AI
    participant ORC as Orchestrator
    participant EXP as Expert AI
    participant DET as Detector
    participant EE as Decision Extractor
    participant REF as Reflection
    participant INT as Integrator
    participant REV as Reviewer

    GE->>TP: 本質分析完了
    TP->>TPR: 計画生成
    TPR->>TPR: レビュー(major→差し戻し)
    TPR->>UU: 承認
    loop 対話ループ
        UU->>DET: 発言
        DET->>UU: major差し戻し or 通過
        DET->>EE: 抽出
        EE->>ORC: 合意記録
        ORC->>EXP: 専門家選定
        EXP->>DET: 提案
        DET->>EXP: major差し戻し or 通過
        DET->>EE: 抽出
        EE->>REF: round終了判定
        REF->>UU: 継続 or 停滞→Facilitator
    end
    UU->>INT: 完了宣言
    INT->>REV: 統合成果物
    REV->>REV: passed/failed判定
```

## 備考

- **Detector**・**Decision Extractor** は1つの関数（`detector_node` / `decision_extractor_node`）を使い回しており、グラフ上のエイリアス（`user_detector`, `expert_detector`, `user_decision_extractor`, `expert_decision_extractor`）で役割を区別している。
- **Detector**は2段構成: (1)ドメイン妥当性レビュー（前提・設計の現実性）→ (2)数値監査（F-2.6 python_repl検算）。統合時に重篤な方を採用。
- **Reflection**は呼び出し契機が3つある: (a) `route_after_user_detector`でUserが3回差し戻された場合、(b) `route_after_expert_detector`でExpertが3回差し戻された場合、(c) `route_after_expert_decision`で定期監査（round_count % interval == 0）。
- **route_after_facilitator**・**route_after_reflection** の「end_turn」と「END」は、グラフを1回で完了（`app.invoke()`）させる場合は `END`、`app.stream()` で複数回呼ぶ場合は外部ループが state を保持したまま次のイテレーションを開始する。