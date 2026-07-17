# Phase 6+ 予備設計書: Lessons Learned RAG（着手判断のための最小検討）
# (Cognitive Experience Lineage-driven Agent System)

> **位置づけ**: 本書はロードマップv24において「R1〜R5完了後、費用対効果を見て着手判断する」とされた保留フェーズの**予備検討**であり、実装設計書ではない。R1〜R5が完了し、実際にLessons Learned RAGへの需要（同種の失敗の再発）が確認された時点で、本書を正式な設計書に昇格させる。
> **最終更新**: 2026-07-17

---

## 1. 着手判断の前提条件

以下がすべて満たされない限り、本フェーズには着手しない（ロードマップv24 Phase 6+節より）。

1. R1〜R5が完了し、`agreements`（DecisionPair）による同一プロジェクト内での却下案回避（要件定義書付録A.3〜A.5で実証済みの現象）が、実運用でも確認できていること。
2. **プロジェクトを跨いだ**失敗の再発が、実際に問題として観測されていること（同一プロジェクト内の`agreements`参照だけでは対処できない課題であることの確認）。
3. `sqlite-vec`等のベクトル検索拡張の導入が、既存のSQLite運用（R1で導入したWALモード等）と技術的に両立することの事前確認。

---

## 2. スキーマ（要件定義書4.3より再掲、変更なし）

```sql
CREATE TABLE IF NOT EXISTS lessons_learned (
    lesson_id TEXT PRIMARY KEY,
    category TEXT NOT NULL,
    context_trigger TEXT,
    action_taken TEXT NOT NULL,
    negative_outcome TEXT NOT NULL,
    abstracted_wisdom TEXT NOT NULL,
    vector_embedding BLOB,
    context_boundary TEXT,
    created_at REAL NOT NULL
);
```

---

## 3. 未解決の実装方式（付録Aで指摘済みの課題）

要件定義書付録の初期レビューで指摘した通り、標準SQLite3にはネイティブのベクトル類似度検索機能がない。以下の2方式を比較検討する必要がある（本書では結論を出さず、着手判断時に再検討する）。

| 方式 | 概要 | 長所 | 短所 |
| :--- | :--- | :--- | :--- |
| A. `sqlite-vec`拡張の導入 | SQLite拡張モジュールとしてベクトル検索を追加 | SQL文内で完結、実装がシンプル | 拡張モジュールの追加インストールが必要、既存のWALモード運用との相性を要検証 |
| B. Python側での類似度計算 | `lessons_learned`はメタデータのみSQLiteに持ち、埋め込みベクトルはPython側でコサイン類似度計算 | 既存構成への追加コストが低い | 件数が増えた場合のスケーラビリティに懸念 |

**暫定方針**: 着手時点での`lessons_learned`の想定件数（数十〜数百件程度）であれば方式Bで十分な可能性が高く、方式Aは将来のスケール時に再検討する、という程度の暫定見解に留める。

---

## 4. 既存プロトタイプとの接続点（着手時に実装すべき箇所）

失敗が発生した際の構造化保存（F-5.3）は、既存の`reflection_node`が「discussion_status=stagnant」と判定した箇所、および`reviewer_node`が`passed=false`で差し戻した箇所が、最も自然なトリガー候補となる。

```python
def extract_lesson_on_failure(state: LineageState, failure_context: dict) -> dict:
    """
    stagnant判定 or reviewer差し戻し時に、[状況]→[とった手段]→[結果]→[教訓]
    の形式で構造化保存する候補ロジック（着手判断後に本実装）。
    """
    return {
        "category": failure_context.get("category", "unknown"),
        "context_trigger": json.dumps(state.get("global_constraints", [])),
        "action_taken": state.get("expert_output", "")[:500],
        "negative_outcome": failure_context.get("reasoning", ""),
        "abstracted_wisdom": None,  # 別途LLMによる抽象化が必要（未設計）
    }
```

**未設計事項**: `abstracted_wisdom`（抽象化された教訓）をどのモデルにどう生成させるかは、本書では検討していない。着手判断後、正式設計時に別途プロンプト設計が必要。

---

## 5. 本書のステータス

本書は着手判断のための予備検討に留まり、以下は意図的に未着手・未決定である。

- ベクトル検索方式（A/B）の最終決定
- `abstracted_wisdom`生成のプロンプト設計
- 事前枝刈り（F-9.2）の具体的な注入ロジック
- 評価メトリクス（別プロジェクトでの実際の失敗回避率の測定方法）

これらはR1〜R5完了後、本フェーズへの着手が正式に判断された時点で、Phase1〜R5の設計書と同水準の詳細設計に昇格させる。
