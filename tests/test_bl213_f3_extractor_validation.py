"""
BL-213 F3: `agreements`テーブルへの書き込み経路は2本あるが、検証の厳しさが極端に非対称だった。

- 経路1（`write_agreement`ツール → `_write_agreement_impl`）：必須フィールドの空文字を含む不足
  チェック、enum検証、ロール権限、depends_on参照整合性、BL-131 task_id実在／BL-146
  current_task_id一致、BL-131 target_topic必須化の**6層**。
- 経路2（`call_decision_extractor` → `decision_extractor_node`のフォールバック）：LLMのJSONを
  **一切検証せず**そのままDBへ書く**0層**。

実測でこの経路は全ログ591ターン中271回（46%）発火し、実runのagreements 177行中44行（25%）を
書いていた。稀な例外どころか常用経路である。実害も既に出ており、BL-206修正前の期間に、
この経路由来の行17件が`phase_id=''`で記録されていた。BL-206（phase_id）とBL-211（task_id）で
個別に直したのは、同じ行に並んだ6フィールドのうち2つだけだった。

対応（AGENTS.md §15.4「同じ状態への書き込み経路が複数あるなら全経路で同じ不変条件を強制する」
の適用）：

1. **自己修正の付与**：`_query_and_parse_with_retry`に`validator`フックを追加。従来のリトライは
   パース失敗時に同一プロンプトをそのまま再送するだけで「何が悪かったか」をモデルへ伝えて
   いなかった（ツール呼び出しの失敗が`{"success": False, "error": ...}`としてツールループ内で
   モデルへ返り同一ターンで修正できるのとは対照的に、この経路はノード呼び出しなので
   フィードバックchannelが存在しない）。検証不合格時は理由とあるべき出力をプロンプトへ追記して
   再問い合わせする。
2. **ハイブリッドのフェイルクローズ**（ユーザー承認）：リトライを使い切ってなお不正な場合、
   同一性に関わるフィールド（entry_type / action_type / UPDATE時のtarget_topic）が不正なら
   その項目を破棄し、それ以外（status / topic / proposed_by）は既定値へ正規化して記録は残す。
3. **警告文**：LLM向け（なぜ不正か・どうすべきか）と人間向け（何を破棄/正規化し、その結果何が
   失われたか）の両方を出力する。

参照: docs/design/back_log/BL-213/BL213_investigation.md（F3）、issue_backlog.md BL-213、
decision_log.md D-191。実LLM API呼び出しは伴わない。
"""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _ok_item(**over):
    item = {
        "action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",
        "topic": "task_4_3運賃・住民負担配慮の設計着手指示", "content": "…", "rationale": "…",
        "proposed_by": "User", "phase_id": "phase_4", "task_id": "task_4_3",
    }
    item.update(over)
    return item


# ---------------------------------------------------------------------------
# 1. 検証（validator）— LLMへ返すメッセージ
# ---------------------------------------------------------------------------

def test_valid_payload_passes():
    ok, msg = cela_main._validate_extracted_events({"extracted_events": [_ok_item()]})
    assert ok is True
    assert msg == ""


def test_missing_extracted_events_key_is_not_an_error():
    """抽出0件のときキー自体を省略しうるため、正常扱いとすること（無用なリトライを起こさない）。"""
    ok, _ = cela_main._validate_extracted_events({"advances_to_task_id": None})
    assert ok is True


def test_empty_entry_type_is_fatal_and_explains_why_and_what_to_do():
    """[F3-a] 実インシデントで観測された空文字ドリフト。BL-206と同じ孤児化に至る第3の経路。"""
    ok, msg = cela_main._validate_extracted_events({"extracted_events": [_ok_item(entry_type="")]})
    assert ok is False
    assert "entry_type" in msg
    assert "孤児レコード" in msg, "なぜ不正なのか（結果として何が起きるか）が書かれていない"
    assert "Deliverable" in msg, "どうすべきか（許容値）が書かれていない"


def test_empty_action_type_is_fatal():
    ok, msg = cela_main._validate_extracted_events({"extracted_events": [_ok_item(action_type="")]})
    assert ok is False
    assert "action_type" in msg
    assert "CREATE" in msg and "UPDATE" in msg


def test_update_without_target_topic_is_fatal():
    """[F3-b] target_topicが空だとtopicへの暗黙フォールバックが効かず、更新対象を特定できない。
    ツール経路ではBL-131のガードが同じ問題を塞いでいる（経路間の不変条件の対称化）。"""
    ok, msg = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(action_type="UPDATE", target_topic="")]})
    assert ok is False
    assert "target_topic" in msg


def test_update_with_target_topic_passes():
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(action_type="UPDATE", target_topic="既存トピック")]})
    assert ok is True


def test_deliverable_update_also_requires_target_topic():
    """[CONSTRAINT] ツール経路のBL-131ガードはDeliverableを除外するが、あちらはDeliverableを
    phase_id/task_idで特定するのに対し、このフォールバック経路はtopic+entry_typeの線形探索で
    特定するため、Deliverableでもtarget_topicが同一性の要である。"""
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(entry_type="Deliverable", action_type="UPDATE", target_topic="")]})
    assert ok is False


def test_minor_only_problems_do_not_trigger_retry():
    """[コスト配慮] statusやproposed_byの欠落だけでLLM呼び出しを浪費しない（正規化に任せる）。"""
    ok, _ = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(status="", proposed_by="", topic="")]})
    assert ok is True


def test_non_list_extracted_events_is_fatal():
    ok, msg = cela_main._validate_extracted_events({"extracted_events": {"not": "a list"}})
    assert ok is False
    assert "配列" in msg


def test_message_identifies_which_item_failed():
    """複数項目のうちどれが不正かをLLMが特定できること。"""
    ok, msg = cela_main._validate_extracted_events(
        {"extracted_events": [_ok_item(), _ok_item(entry_type=""), _ok_item()]})
    assert ok is False
    assert "extracted_events[1]" in msg
    assert "extracted_events[0]" not in msg


# ---------------------------------------------------------------------------
# 2. 正規化・破棄（ハイブリッド方針）
# ---------------------------------------------------------------------------

def test_fatal_item_is_discarded_and_others_survive():
    events = [_ok_item(topic="残る1"), _ok_item(entry_type="", topic="消える"), _ok_item(topic="残る2")]
    clean = cela_main._sanitize_extracted_events(events)
    assert [c["topic"] for c in clean] == ["残る1", "残る2"]


def test_discard_log_explains_consequence(capsys):
    """人間向け警告に「なぜ破棄したか」と「その結果何が失われたか」が含まれること。"""
    cela_main._sanitize_extracted_events([_ok_item(entry_type="", topic="消える話題")])
    out = capsys.readouterr().out
    assert "破棄" in out
    assert "消える話題" in out
    assert "記録されません" in out, "失われるものが明示されていない"
    assert "write_agreement" in out, "どう回復すべきかが示されていない"


def test_minor_fields_are_normalized_not_discarded():
    clean = cela_main._sanitize_extracted_events([_ok_item(status="", topic="", proposed_by="")])
    assert len(clean) == 1
    assert clean[0]["status"] == "Proposed"
    assert clean[0]["topic"] == "Unknown Topic"
    assert clean[0]["proposed_by"] == "Unknown"


def test_normalization_warns_with_reason(capsys):
    cela_main._sanitize_extracted_events([_ok_item(status="なんとなく承認")])
    out = capsys.readouterr().out
    assert "正規化" in out
    assert "Proposed" in out


def test_sanitizer_does_not_mutate_input():
    """呼び出し元が元のdictを保持している場合に備え、破壊的変更をしないこと。"""
    original = _ok_item(status="")
    cela_main._sanitize_extracted_events([original])
    assert original["status"] == ""


def test_valid_payload_is_passed_through_unchanged():
    """[非退行] 正常な出力に対して正規化が余計な変更を加えないこと。"""
    item = _ok_item()
    clean = cela_main._sanitize_extracted_events([item])
    assert clean == [item]


def test_non_list_input_yields_empty_list(capsys):
    assert cela_main._sanitize_extracted_events({"not": "a list"}) == []
    assert "破棄" in capsys.readouterr().out


# ---------------------------------------------------------------------------
# 3. 自己修正リトライ（validatorフック）
# ---------------------------------------------------------------------------

def _fake_query_factory(responses):
    """query_AIの代わりに、呼ばれるたびにresponsesを順に返すスタブ。受け取ったpromptも記録する。"""
    seen = []

    def _fake(messages, client=None, model=None, label=None, tools=None, state=None, **kw):
        seen.append(messages[0]["content"])
        return responses[min(len(seen) - 1, len(responses) - 1)]

    return _fake, seen


def test_validation_failure_triggers_retry_with_reason_in_prompt(monkeypatch):
    """[F3の核心] 検証不合格時、次の問い合わせプロンプトへ「なぜ不正か・どうすべきか」が
    追記されること。これがツール失敗時の自己修正と等価な機構になる。"""
    bad = '{"extracted_events": [{"action_type": "CREATE", "entry_type": "", "status": "Proposed", "topic": "t", "content": "c", "proposed_by": "User"}]}'
    good = '{"extracted_events": [{"action_type": "CREATE", "entry_type": "Directive", "status": "Proposed", "topic": "t", "content": "c", "proposed_by": "User"}]}'
    fake, seen = _fake_query_factory([bad, good])
    monkeypatch.setattr(cela_main, "query_AI", fake)

    parsed, failed = cela_main._query_and_parse_with_retry(
        "BASE_PROMPT", client=None, model="m", label="Decision Extractor",
        tools=None, fallback={"extracted_events": []},
        validator=cela_main._validate_extracted_events,
    )

    assert failed is False
    assert parsed["extracted_events"][0]["entry_type"] == "Directive", "自己修正後の出力が採用されていない"
    assert len(seen) == 2, "検証不合格なのに再問い合わせしていない"
    assert "BASE_PROMPT" in seen[1], "元のプロンプトが失われている"
    assert "entry_type" in seen[1] and "孤児レコード" in seen[1], (
        "再問い合わせのプロンプトに不正の理由が含まれていない"
    )


def test_retry_exhaustion_returns_last_output_for_caller_policy(monkeypatch):
    """リトライを使い切っても、パース自体は成功しているので`parse_failed=False`で最後の出力を返す
    （破棄/正規化の判断は呼び出し元の方針に委ねる、という責務分離の確認）。"""
    bad = '{"extracted_events": [{"action_type": "CREATE", "entry_type": "", "status": "Proposed", "topic": "t", "proposed_by": "User"}]}'
    fake, seen = _fake_query_factory([bad])
    monkeypatch.setattr(cela_main, "query_AI", fake)

    parsed, failed = cela_main._query_and_parse_with_retry(
        "BASE_PROMPT", client=None, model="m", label="Decision Extractor",
        tools=None, fallback={"extracted_events": []},
        validator=cela_main._validate_extracted_events, max_retries=2,
    )

    assert failed is False
    assert len(seen) == 3, "max_retries=2 なら合計3回問い合わせるはず"
    assert parsed["extracted_events"][0]["entry_type"] == ""


def test_valid_first_response_does_not_retry(monkeypatch):
    """[非退行/コスト] 一発で正しい出力なら再問い合わせしないこと。"""
    good = '{"extracted_events": [{"action_type": "CREATE", "entry_type": "Directive", "status": "Proposed", "topic": "t", "content": "c", "proposed_by": "User"}]}'
    fake, seen = _fake_query_factory([good])
    monkeypatch.setattr(cela_main, "query_AI", fake)

    _, failed = cela_main._query_and_parse_with_retry(
        "BASE_PROMPT", client=None, model="m", label="L", tools=None,
        fallback={"extracted_events": []}, validator=cela_main._validate_extracted_events,
    )
    assert failed is False
    assert len(seen) == 1


def test_no_validator_preserves_original_behaviour(monkeypatch):
    """[非退行] validator未指定の既存呼び出し元（call_reflection等）の挙動が変わらないこと。"""
    good = '{"anything": 1}'
    fake, seen = _fake_query_factory([good])
    monkeypatch.setattr(cela_main, "query_AI", fake)

    parsed, failed = cela_main._query_and_parse_with_retry(
        "P", client=None, model="m", label="L", tools=None, fallback={"x": 0},
    )
    assert failed is False and parsed == {"anything": 1} and len(seen) == 1


def test_parse_failure_still_fails_closed(monkeypatch):
    """[非退行] BL-160のパース失敗リトライとフェイルクローズが壊れていないこと。"""
    fake, seen = _fake_query_factory(["not json at all"])
    monkeypatch.setattr(cela_main, "query_AI", fake)

    fallback = {"extracted_events": []}
    parsed, failed = cela_main._query_and_parse_with_retry(
        "P", client=None, model="m", label="L", tools=None, fallback=fallback,
        validator=cela_main._validate_extracted_events, max_retries=1,
    )
    assert failed is True
    assert parsed is fallback
    assert len(seen) == 2


# ---------------------------------------------------------------------------
# 4. `call_decision_extractor` を通した振る舞い（配線が外れると落ちること）
# ---------------------------------------------------------------------------

def _call_extractor(monkeypatch, responses):
    fake, seen = _fake_query_factory(responses)
    monkeypatch.setattr(cela_main, "query_AI", fake)
    monkeypatch.setattr(cela_main, "_reset_think_scratchpad", lambda: None, raising=False)
    items, transition = cela_main.call_decision_extractor(
        [{"role": "user", "content": "task_4_3を指示します。"}], ["既存トピック"], "user",
    )
    return items, transition, seen


def test_end_to_end_bad_item_is_discarded_after_retries(monkeypatch):
    """[振る舞い] entry_typeが空のまま自己修正に失敗した項目は、呼び出し元へ渡らないこと。
    `_sanitize_extracted_events`の配線が外れるとここが落ちる。"""
    bad = ('{"extracted_events": [{"action_type": "CREATE", "entry_type": "", "status": "Proposed",'
           ' "topic": "壊れた項目", "proposed_by": "User"}], "advances_to_task_id": null}')
    items, _, _ = _call_extractor(monkeypatch, [bad])

    assert items == [], f"不正な項目がそのまま呼び出し元へ流れた（BL-213 F3再発）: {items}"


def test_end_to_end_self_correction_recovers_the_item(monkeypatch):
    """[振る舞い] 1回目が不正でも、理由を伝えた再問い合わせで正しい出力が得られれば採用されること。
    `validator`の配線が外れると、1回目の不正な出力がそのまま採用され（entry_type=""）ここが落ちる。"""
    bad = ('{"extracted_events": [{"action_type": "CREATE", "entry_type": "", "status": "Proposed",'
           ' "topic": "task_4_3着手指示", "content": "c", "proposed_by": "User"}]}')
    good = ('{"extracted_events": [{"action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",'
            ' "topic": "task_4_3着手指示", "content": "c", "proposed_by": "User"}]}')
    items, _, seen = _call_extractor(monkeypatch, [bad, good])

    assert len(items) == 1, f"自己修正後の項目が採用されていない: {items}"
    assert items[0]["entry_type"] == "Directive"
    assert len(seen) == 2, "検証不合格なのに再問い合わせしていない"


def test_end_to_end_minor_problems_are_normalized_not_dropped(monkeypatch):
    """[振る舞い] 軽微な欠落は記録を失わずに正規化されること。"""
    payload = ('{"extracted_events": [{"action_type": "CREATE", "entry_type": "Directive", "status": "",'
               ' "topic": "t", "content": "c", "proposed_by": ""}]}')
    items, _, seen = _call_extractor(monkeypatch, [payload])

    assert len(items) == 1
    assert items[0]["status"] == "Proposed"
    assert items[0]["proposed_by"] == "Unknown"
    assert len(seen) == 1, "minorのみでリトライを浪費している"


def test_end_to_end_valid_payload_untouched(monkeypatch):
    """[非退行] 正常な出力はそのまま通り、transitionも従来通り取り出せること。"""
    payload = ('{"extracted_events": [{"action_type": "CREATE", "entry_type": "Directive", "status": "Proposed",'
               ' "topic": "t", "content": "c", "proposed_by": "User"}],'
               ' "advances_to_phase_id": null, "advances_to_task_id": "task_4_3"}')
    items, transition, seen = _call_extractor(monkeypatch, [payload])

    assert len(items) == 1 and items[0]["topic"] == "t"
    assert transition["advances_to_task_id"] == "task_4_3"
    assert len(seen) == 1


def test_call_decision_extractor_is_wired_to_validator_and_sanitizer():
    """テストが検証・正規化ヘルパを直接呼んでいるため、本体が経由しなくなっても上記は通る。
    配線をソースレベルで固定する。"""
    import inspect
    src = inspect.getsource(cela_main.call_decision_extractor)
    assert "validator=_validate_extracted_events" in src, (
        "call_decision_extractorが自己修正バリデータを渡していない（BL-213 F3再発）"
    )
    assert "_sanitize_extracted_events" in src, (
        "call_decision_extractorが正規化を経由していない（未検証の項目がDBへ流れる）"
    )
    assert "return parsed[\"extracted_events\"], transition" not in src, (
        "検証を通さず生のextracted_eventsを返す旧コードが復活している"
    )
