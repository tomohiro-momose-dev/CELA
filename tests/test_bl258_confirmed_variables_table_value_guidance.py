"""
BL-258: `write_agreement`の`confirmed_variables`パラメータの説明に、これが`verified_facts`
へ書き込む唯一の経路であることと、表形式の値もJSON文字列としてこの経路で確定できることが
明記されていなかった。

実ドライラン（`log/2026-08-17/0757`、run_id=1786921069-6bb4a6a5）のtask_3_1_authorityで、
Expertが`authority_requirement_register`/`insurance_responsibility_boundary`という約32件の
構造化レコードを「登録」しようとしたが、`confirmed_variables`を一度も呼ばず、代わりに
`write_agreement`のtopic/decision_what経由で通常のagreementsレコードを作成しただけだった。
そのため`verified_facts`には何も書き込まれず、Detectorが`read_verified_fact`/`read_entity`
で独立確認するたびにnot_foundとなり、15回のDetector差し戻しサイクル（約63分）が発生した
（BL-258投稿時点のissue_backlog.md参照）。

Expert自身の思考ログにも「variable names versus entitiesの混同」を認識している記述があり、
32件という表形式の値がconfirmed_variablesの1変数=1スカラー値という形状に素直に収まらない
ことが、書き込みを避けて見慣れたagreementsテキストへ逃げた一因と考えられる。

対応として、confirmed_variablesの説明に、(1) verified_factsへの唯一の書き込み経路である
こと、(2) 表形式の値もJSON文字列としてこの経路で確定できることを明記した（ドキュメントのみの
修正であり、実LLM API呼び出しは伴わない）。参照: docs/design/back_log/issue_backlog.md BL-258。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _confirmed_variables_description() -> str:
    props = cela_main.WRITE_AGREEMENT_TOOL["function"]["parameters"]["properties"]
    return props["confirmed_variables"]["description"]


def test_confirmed_variables_description_mentions_bl258():
    desc = _confirmed_variables_description()
    assert "BL-258" in desc


def test_confirmed_variables_description_states_it_is_the_only_write_path():
    desc = _confirmed_variables_description()
    assert "ONLY path" in desc
    assert "verified_facts" in desc


def test_confirmed_variables_description_warns_agreement_text_alone_does_not_register():
    desc = _confirmed_variables_description()
    assert "does NOT register" in desc
    assert "not_found" in desc


def test_confirmed_variables_description_explains_json_serialized_table_value():
    desc = _confirmed_variables_description()
    assert "JSON string" in desc
    assert "table" in desc.lower() or "list" in desc.lower()
