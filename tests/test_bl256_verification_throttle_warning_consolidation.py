"""
BL-256（第1段の一部）: `cela_main.py`のモジュールレベル冗長プロンプト文の集約。

既存の共有ヘルパー`_verification_throttle_warning(example="")`は、docstringで
「call_integrator/call_reviewer/call_goal_essence_analystでbyte-identical、
call_resource_arbiterはタスク固有の例示句を挿入するのみ」と明記された上で正しく
4箇所から呼ばれていたが、実際には`call_expert`・`generate_user_utterance`・
`call_task_plan_reviewer`の3箇所が同じ「同じ検証・計算を繰り返さない」注意文の
手書きの近似テキストを持ったまま、このヘルパーへ移行されていなかった
（機械的grep・本文diffで確認）。

ヘルパーに`output_form`引数（既定"json"、"answer"＝call_expert、"utterance"＝
generate_user_utterance）を追加し、既定値の出力が既存4箇所向けの文面と完全に
byte-identicalであることを保った上で、残り3箇所を移行した。

- `call_expert`: output_form="answer"へ移行（「回答」向けの結び）。
- `generate_user_utterance`: output_form="utterance"へ移行（「発言」向けの結び）。
- `call_task_plan_reviewer`: f-string内で直接呼び出す形へ移行。ただしこのタスクは
  「python_replの呼び出し回数だけでなく思考の中での再検討も含む」「一度major/noneの
  判断がついた論点を蒸し返さない」という2文が元のテキストに固有で存在したため、
  ヘルパー呼び出しの直後に維持したまま残している（意味を落とさないための追加）。

実LLM API呼び出しは伴わない。参照: docs/design/back_log/issue_backlog.md BL-256。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


_GOLDEN_DEFAULT = (
    "【同じ検証・計算を繰り返さない（重要）】ツール呼び出しの回数には上限があります。同じ論点\n"
    "をpython_replで繰り返し再確認しないでください。各検証項目は2回程度の\n"
    "計算・確認で十分です。新しい数値や新しい論点が無いまま「念のため最終確認」を重ねると、\n"
    "JSON出力そのものを書く余地が無くなり、上限到達時に強制的に打ち切られたテキスト応答として\n"
    "JSONを一度に出力せざるを得なくなり、出力が途中で切れて構文エラーになるリスクがあります。\n"
    "必要な検証が終わったら、直ちに最終的なJSONオブジェクトの記述に移ってください。"
)

_GOLDEN_WITH_EXAMPLE = (
    "【同じ検証・計算を繰り返さない（重要）】ツール呼び出しの回数には上限があります。同じ論点\n"
    "（例:テスト例）をpython_replで繰り返し再確認しないでください。各検証項目は2回程度の\n"
    "計算・確認で十分です。新しい数値や新しい論点が無いまま「念のため最終確認」を重ねると、\n"
    "JSON出力そのものを書く余地が無くなり、上限到達時に強制的に打ち切られたテキスト応答として\n"
    "JSONを一度に出力せざるを得なくなり、出力が途中で切れて構文エラーになるリスクがあります。\n"
    "必要な検証が終わったら、直ちに最終的なJSONオブジェクトの記述に移ってください。"
)


def test_default_output_form_is_byte_identical_to_pre_bl256_text():
    """output_form未指定（既定"json"）の出力が、既存4呼び出し元（call_integrator/
    call_reviewer/call_goal_essence_analyst/call_resource_arbiter）が依存していた
    元の文面とbyte-identicalであること（後方互換性の保証）。"""
    assert cela_main._verification_throttle_warning() == _GOLDEN_DEFAULT
    assert cela_main._verification_throttle_warning(example="テスト例") == _GOLDEN_WITH_EXAMPLE


def test_output_form_answer_produces_answer_specific_tail():
    val = cela_main._verification_throttle_warning(output_form="answer")
    assert "実際の回答を書く余地が無くなり" in val
    assert "直ちに回答の記述に移ってください" in val
    assert "JSON" not in val


def test_output_form_utterance_produces_utterance_specific_tail():
    val = cela_main._verification_throttle_warning(output_form="utterance")
    assert "実際の発言を書く余地が無くなり" in val
    assert "直ちに発言の記述に移ってください" in val
    assert "JSON" not in val


def test_call_expert_migrated_to_shared_helper():
    src = inspect.getsource(cela_main.call_expert)
    assert '_verification_throttle_warning(' in src
    idx = src.index("_verification_throttle_warning(")
    nearby = src[idx: idx + 100]
    assert 'output_form="answer"' in nearby
    # 手書きの旧テキストが残っていないこと（移行漏れの再発防止）。
    assert "実際の回答を書く余地が" not in src


def test_generate_user_utterance_migrated_to_shared_helper():
    src = inspect.getsource(cela_main.generate_user_utterance)
    assert '_verification_throttle_warning(' in src
    idx = src.index("_verification_throttle_warning(")
    nearby = src[idx: idx + 100]
    assert 'output_form="utterance"' in nearby
    assert "実際の発言を書く余地が" not in src


def test_call_task_plan_reviewer_migrated_to_shared_helper():
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "_verification_throttle_warning(" in src
    # 手書きの旧テキストが残っていないこと。
    assert "JSON出力そのものを書く余地が無く" not in src


def test_call_task_plan_reviewer_preserves_reviewer_specific_sentences():
    """ヘルパー移行時に、レビュワー固有の2文（思考中の再検討も含む旨・major/noneの
    蒸し返し禁止）が失われていないこと。"""
    src = inspect.getsource(cela_main.call_task_plan_reviewer)
    assert "思考の中で同じ論点を何度も再検討することも含みます" in src
    assert "一度major/noneの判断がついた論点を、新しい情報が無いまま何度も蒸し返さないこと" in src
    # JSON単一ブロック指示（別懸念）も引き続き存在すること。
    assert "コードブロックを**1つだけ**書いてください" in src


def test_pre_existing_four_callers_unchanged():
    """先行して正しく移行済みだった4箇所が、今回の変更で巻き添えを受けていないこと
    （呼び出し自体が変わらず残っていることの確認）。"""
    for func_name in (
        "call_resource_arbiter", "call_integrator", "call_reviewer", "call_goal_essence_analyst",
    ):
        src = inspect.getsource(getattr(cela_main, func_name))
        assert "_verification_throttle_warning(" in src
