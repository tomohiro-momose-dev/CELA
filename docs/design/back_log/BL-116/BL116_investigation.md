# BL-116: ドメイン特化表現・冗長性調査（生ログ）

関連: [issue_backlog.md BL-116](../issue_backlog.md#bl-116-プロンプトへのバス交通シナリオ特化例の埋め込みおよび冗長な指示文ゴミ文字混入)。

**[F] 行番号について:** 本書中の`cela_main.py:NNNN`表記は調査時点（2026-07-28）のもの。`cela_main.py`は頻繁に編集されるため、実装着手時に必ず現行ファイルと突き合わせて確認すること。

## 調査目的

CELAのノードプロンプトは本来ドメイン非依存であるべきだが、現在の過疎地バス交通シナリオでのドライラン実績から生まれた具体例・誘導表現が紛れ込んでいないか、また冗長な指示文がないかを、Exploreエージェント（カテゴリC）に読み取り専用で調査させた。この文書はそのエージェントの報告をそのまま保存したもの（生ログ）。

## エージェント報告（原文）

## Prompt Audit Findings — `cela_main.py`

### 1. Domain-specific leakage / leading language

**`call_task_planner`** (lines 4227‑4234, 4251‑4258)
- `"例: 「車両台数の算出」「初期費用の内訳」「年間ランニングコストの内訳」..."` and `owns_variables`（例: "vehicle_count"）` — transit-fleet examples baked into a generic decomposition rule.
- `"（例:「車両3台が上限」）...「新品購入の場合、車両単価2,500万円×初期予算1億円から3台が上限...」"` — a fully worked bus-procurement example used to illustrate a generic "derived value must carry its rationale" rule. Concern: leads the model toward vehicle/fleet-costing framing for any goal.

**`call_orchestrator`** (line 4416)
- `例: 「地域公共交通の需要予測専門家」「自動運転車両の安全基準アナリスト」のように...` — the only example expert titles given are transit-specific, biasing expert-title generation toward transit roles.

**`call_expert`** (lines 4504‑4505, 4734)
- `"（例：高齢者の移動手段確保という目的に対して、需要密度と矛盾する車両サイズを固定してしまう条件になっている等）"` — transit-specific illustration of "premise vs. true constraint."
- `"read_verified_factは...変数名やキーワード（例:「車両台数」「山間部」「通信不安定」）から確定値を検索できます"` (light_system_prompt) — same leakage repeated in the alternate/light prompt.

**`call_detector`** (lines 4883‑4884, 4891‑4894, 4948‑4950)
- Repeated non-numeric-issue examples: `"労働基準法上のシフト・休憩要件、物理的な運用可能性、予備・冗長性の欠如、安全規制等"` and `"そもそもの前提・設計（台数、人数配置、シフト、速度・距離の設定など）"` — vehicle/shift-scheduling framing baked into the generic "domain validity" audit instructions, appearing 3 times across the two detector prompts.

**`call_decision_extractor`** (lines 5366, 5409, and duplicated in dead `prompt_old` at 5357/5361)
- `例:「送料割引は割引適用前の金額で判定する」「車両は3台体制とする」` — a "vehicle fleet = 3 units" example hard-coded as the canonical illustration of a "Decision" entry type; appears twice (once in the actually-used `common_rules`, once in the unused `prompt_old`).

**`call_task_plan_reviewer`** (lines 6558‑6567) — most severe finding
- A large paragraph narrates a specific past incident using concrete transit numbers: `"山間部2km≒ルート全体13.33km"`, `"原文の12kmとの端数差"`, `"山間部12km＝ルート全体の15%"`, `"総ルート長80km"`. This is a verbatim war-story from the current bus-transit dry run embedded directly into the reviewer's standing instructions — the strongest example of scenario-specific leakage biasing the reviewer toward route-length/percentage reasoning regardless of the actual goal domain.

**`generate_user_utterance`** (lines 6049‑6050, 6053) — mirrors the same "labor law / shift / safety regulation" transit-style checklist seen in `call_expert`/`call_detector`, reinforcing the domain assumption across three different nodes (cross-node, noted for context).

### 2. Verbosity / redundant phrasing

- **`call_task_planner`** prompt body: lines 4213‑4346 (~130 lines, ~5,500 characters) for a single JSON-array request; includes an 11-item numbered instruction list, several of which (calc-repetition limits, `read_verified_fact` sync reminders, `write_agreement` rationale reminders) are near-verbatim copies of blocks that also appear in `call_expert`, `call_integrator`, `call_reviewer`, `call_resource_arbiter`, `call_goal_essence_analyst`, and `call_detector` (the "同じ検証・計算を繰り返さない" and "BL-093: thinkツールで検討過程を残す" paragraphs recur almost word-for-word in at least 8 different node prompts).
- **`call_expert`**: system_prompt assembled from ~15 `+=` blocks (lines 4480‑4691), roughly 200 lines / ~7,000 characters; a near-duplicate "light" version (`light_system_prompt`, lines 4718‑4755) restates the same scope/re-derivation/tool-list rules a second time within the same function call.
- **`call_detector`**: contains two large prompts (`domain_prompt` ~55 lines and `prompt` ~120 lines, lines 4943‑5156) built for a single call; both independently repeat the "気づき欄 (observations)" instruction, the tool-list disclaimer, and the BL-093 "think" explanation verbatim — redundant within the same function invocation, not just across nodes.
- **`call_decision_extractor`**: contains a fully dead code path — `prompt_old` (lines 5344‑5403, ~60 lines) is built but never passed to `query_AI` (only `prompt`, built later from `role_instruction` + `common_rules`, is used). This dead prompt duplicates `common_rules`' content almost exactly, doubling the redundant instruction text in the source even though it has no runtime effect.
- **`call_task_plan_reviewer`**: prompt spans lines 6539‑6638 (~100 lines, ~5,000 characters) with the domain-leakage BL-092 anecdote alone consuming ~10 lines for what could be a one-sentence rule ("don't demand fabricated absolute values when only ratios are given").
- **`generate_user_utterance`**: numerous stray literal `\n"` artifacts embedded inside f-strings (e.g. lines 5986‑6004, 6085‑6090) — leftover escaped quote characters from a prior formatting pass that get sent to the LLM as literal noise characters at line ends, adding clutter without semantic value.

## この調査から派生したBL

- **BL-116**（本ファイル、`open`）: 上記1・2節の内容全体（バス交通シナリオ特化例の埋め込み、冗長な指示文、`generate_user_utterance`のゴミ文字混入）を対象とする。
- 注記: `call_decision_extractor`の`prompt_old`デッドコードはBL-115（カテゴリB由来）とも重複して言及されている。デッドコード削除自体はBL-115側で対応する想定。
