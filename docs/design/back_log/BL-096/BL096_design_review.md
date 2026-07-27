# BL-096 設計書レビュー

レビュー日: 2026-07-27
レビュー対象: `docs/back_log/BL-096/BL096_basic_design.md`

---

## 総評

全体として問題の特定・解決策・対象範囲が明確で、実装準備は整っている。BL-093/095/099 の知見（機械的強制とモデル判断の棲み分け）を適切に反映している。以下、修正を推奨する項目を重要度順に列挙する。

---

## 1. 修正推奨（高優先度）

### B: 初回 `severity='major'` で起票されたissueが reflection に届かない

**問題**: 自動昇格ロジックは `occurrence_count >= 2` でのみ `severity='major'` かつ `status='escalated'` に引き上げる。しかし Detector が最初から `severity='major'` で CREATE した場合、`occurrence_count=1` のまま `status='open'` で留まり、reflection 側の `status='escalated'` のみを拾うクエリでは取得されない。

**修正案**: reflection の issue_log 問い合わせ条件を以下に変更する:
```python
# 現行案:
WHERE status = 'escalated'

# 修正案:
WHERE status = 'escalated' OR (severity = 'major' AND status = 'open')
```

または、`severity='major'` で初回 CREATE された時点で `status` も `'escalated'` に設定するルールを追加する。

---

## 2. 修正推奨（中優先度）

### A: `topic` を重複検知キーにすることの脆さ

**問題**: `write_agreement` 周りで BL-053/BL-084 で同じ問題（AI が topic 文字列を微妙に変える）に悩まされ、Deliverable では `(phase_id, task_id)` による識別に移行した。issue_log でも同様の問題が発生する可能性が高い。

**修正案**: 重複検知は `topic` 単独ではなく `(topic, phase_id, task_id)` の3列で行う。`_resolve_deliverable_pointer` (BL-084) と同じパターンを踏襲する。

### D: モデルが `write_issue` を呼ばないリスクへの対策

**問題**: 設計書は「並存とする」と述べているが、`observations` / `constraint_issue_log` と `issue_log` の使い分け基準がモデルの判断に完全に委ねられている。BL-093 のような機械的強制がないため、MVP で本当に `write_issue` が使われるかは不確実。

**修正案（設計書への追記を推奨）**: `detector_node` の Python 側で、`observations` が非空かつ一定長以上の場合に自動的に `write_issue` 相当の INSERT を試みる「機械的バックアップ」パスを追加することを検討する。モデルが自発的に `write_issue` を呼ばなかった場合の補助に留め、モデルの判断を上書きしない。

---

## 3. 修正推奨（低優先度）

### C: 再発時の `description` 追記が無限に伸びる

**問題**: 再発のたびに `description` に改行区切りで追記すると、多数回再発した場合に無制限に肥大化する。`agreements` の `decision_what` に対する `content[:10000]` 相当の安全弁がない。

**修正案**: 追記時に `description` の全長が 2000 文字を超えた場合、古い方を切り詰め、末尾に `...(truncated, N occurrences)` を付加するトランケーション規則を明記する。

### G: `topic_keyword` 検索が狭い

**問題**: `topic` は「固定の短い識別文字列」であるため、`topic` のみの部分一致検索ではユーザビリティが低い。`_read_verified_fact_handler`（BL-053）で `reason` 列も検索対象に追加した前例がある。

**修正案**: `description` 列も `topic` と同様に LIKE 検索対象に含める。

### E: ファイルパスの誤記

**問題**: `docs/back_log/` というパスが使われているが、正規のパスは `docs/design/`。`issue_backlog.md` へのリンクも同様。

**修正案**: 全パスを `docs/design/` に統一する。

### F: 行番号が古い可能性

**問題**: 設計書内の行番号（例: `cela_main.py:5026-5032`）は現在のファイル内容と合致しているか確認が必要。`cela_main.py` は頻繁に編集される。

**修正案**: 実装時に必ず現行ファイルと突き合わせ、行番号を更新する。

---

## 4. 特に評価できる点

1. **再発検知＋機械的エスカレーション**: BL-099 が指摘した「モデル遵守への依存」を回避する機械的強制の経路を確立できている。
2. **書き込み権限の段階的拡張**: MVP は detector/user 限定とし、RESOLVE は User AI 限定とした判断は、BL-086（前提エスカレーションの解決）の設計と一貫性がある。
3. **reflection への伝達を Python 側の直接 DB 問い合わせ**: ツールループの非収束リスクを回避する堅実な判断。

---

## 5. まとめ

| # | 重要度 | 項目 | 対応 |
|---|--------|------|------|
| B | **高** | 初回 major が reflection に届かない | クエリ条件に `(severity='major' AND status='open')` を追加 |
| A | 中 | topic 重複検知の脆さ | `(topic, phase_id, task_id)` の3列で検知 |
| D | 中 | モデルが write_issue を呼ばないリスク | 機械的バックアップパスの検討を明記 |
| C | 低 | description の無制限肥大 | 2000文字トランケーションルールを追加 |
| G | 低 | topic_keyword 検索が狭い | description も LIKE 検索対象に追加 |
| E | 低 | ファイルパス誤記 | `docs/design/` に統一 |
| F | 低 | 行番号が古い可能性 | 実装時に現行ファイルと要突合せ |

**B は reflection での取得漏れに直結するため、実装前に必ず修正することを推奨する。**