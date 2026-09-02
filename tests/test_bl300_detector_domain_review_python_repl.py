"""
BL-300: Detectorの「ドメイン妥当性レビュー」パスへのPYTHON_REPL_TOOL追加。

log/2026-08-28/2049で、DetectorがNPA（警察庁）PDFキャッシュから「長野」の免許返納実数を
探そうとしたがgrepが一貫してnot_foundを返し続けた。原因を実測したところ、該当PDFの
都道府県欄はフルネームではなく1〜3文字の略号コード（多くは1文字）で表現されており、
「長野」という文字列はキャッシュ全3550行中どこにも一切存在しなかった
（`grep -c "長野" web_cache/40d17513c6c29834.md` == 0）。grepでは原理的に位置特定
できないため、Detectorは代わりに略号リストと数値列を手作業で1件ずつ突合しようとし、
これが単一completion内での反復（BL-297/298のn-gram反復ガード発火）を招いた。

`call_detector`には数値監査パス（`_detector_numeric_tools`、python_repl付き）と
ドメイン妥当性レビューパス（`_detector_domain_tools`）の2段構成があり、BL-228で
後者は前者とほぼ同じツールを持つよう既に揃えられていたが、唯一`PYTHON_REPL_TOOL`
だけが欠けていた。python_replのサンドボックス（AST検査によるimportホワイトリスト、
`_ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "fractions",
"decimal", "itertools", "functools", "collections", "operator", "re"}`）は
文字列分割・リストインデックス等の組み込み操作には一切importを要求しないため、
「フラットなテキストを機械的に分割・位置特定する」という今回の用途に制約はない
（ユーザー確認済み）。

本BLは`_detector_domain_tools`へ`PYTHON_REPL_TOOL`を追加し、`domain_prompt`にも
「検算目的以外でのpython_repl使用（テキストの機械的な位置特定）は妨げない」旨を
明記した。既存の「Expertの計算を再検算する必要はない」という指示（Pass 1/Pass 2の
役割分担、意図的に維持）とは矛盾しないよう、文言を書き分けている。

【追記】ユーザーから、`PYTHON_REPL_TOOL`自体のグローバルな説明文（全ノード共通、
Expert・Detector両パスが参照する単一の定義）が「mechanical arithmetic/verification」
としか書かれておらず、テキストの機械的な位置特定という用途が案内されていない、との
指摘があった。加えて説明文中の許可モジュール一覧（"only math/statistics/datetime/
json/fractions/decimal allowed"）が、実際の`_ALLOWED_IMPORTS`（BL-058で追加された
itertools/functools/collections/operator/reを含む）に追従しておらず古いままだった
（BL-299と同型のスキーマ説明文ドリフト）。`PYTHON_REPL_TOOL`の説明文を、数値計算と
テキストの機械的な位置特定の両方を用途として明記し、許可モジュール一覧も実装に
合わせて修正した。他ノードへのpython_repl展開時は、この共通ツール説明文に加えて
各ノード個別のプロンプト側にも用途を書き分ける必要がある（ユーザー申し送り、
domain_promptで行ったのと同じパターン）。

参照: log/2026-08-28/2049/log_no_prompt.md、BL-228、BL-297/298（発端）、AGENTS.md §5.1。
実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def _call_detector_source() -> str:
    return inspect.getsource(cela_main.call_detector)


def test_detector_domain_tools_includes_python_repl_tool():
    """[BL-300本体] _detector_domain_toolsにPYTHON_REPL_TOOLが含まれること。"""
    src = _call_detector_source()
    idx = src.index("_detector_domain_tools = [")
    line_end = src.index("]", idx)
    tools_line = src[idx:line_end + 1]
    assert "PYTHON_REPL_TOOL" in tools_line


def test_detector_numeric_and_domain_tools_now_have_matching_python_repl_access():
    """[BL-228の意図の再確認] 数値監査パスとドメイン妥当性レビューパスの唯一の
    (python_repl以外の)差分はMARK_FACT_AUDITED_TOOLの有無のみであり続けること
    （BL-228が意図した「揃える」方針からの新たな乖離が無いことの確認）。"""
    src = _call_detector_source()

    domain_idx = src.index("_detector_domain_tools = [")
    domain_line = src[domain_idx:src.index("]", domain_idx) + 1]

    numeric_idx = src.index("_detector_numeric_tools = [")
    numeric_line = src[numeric_idx:src.index("]", numeric_idx) + 1]

    assert "PYTHON_REPL_TOOL" in domain_line
    assert "PYTHON_REPL_TOOL" in numeric_line
    assert "MARK_FACT_AUDITED_TOOL" in domain_line
    assert "MARK_FACT_AUDITED_TOOL" not in numeric_line


def test_domain_prompt_clarifies_python_repl_is_not_only_for_recalculation():
    """[BL-300] domain_promptが、「Expertの計算を再検算する必要はない」という既存指示と、
    「テキストの機械的な位置特定にはpython_replを使ってよい」という新指示の両方を
    含み、後者が前者を撤回するのではなく用途を書き分けていること。"""
    src = _call_detector_source()
    assert "Expertの計算をpython_replで再計算する必要はありません" in src
    assert "python_replは検算目的以外でも使ってよく" in src
    assert "分割・インデックス" in src


def test_python_repl_sandbox_allows_pure_string_list_operations_without_import():
    """[BL-300] ユーザー確認事項の裏付け: python_replのサンドボックス
    （_check_repl_code_safety）が、importを一切使わない文字列分割・リスト
    インデックス操作を許可すること（このBLで意図する用途に制約が無いことの確認）。"""
    code = (
        "text = 'a,b,c,d'\n"
        "parts = text.split(',')\n"
        "print(parts[2])\n"
    )
    assert cela_main._check_repl_code_safety(code) is None


def test_python_repl_sandbox_still_rejects_disallowed_imports():
    """[非退行] BL-300はimportホワイトリスト自体を拡張していないこと
    （文字列操作に不要な許可外importは引き続き拒否される）。"""
    code = "import os\nprint(os.getcwd())\n"
    result = cela_main._check_repl_code_safety(code)
    assert result is not None
    assert "not allowed" in result


def test_detector_domain_python_repl_calls_get_recorded_like_numeric_pass():
    """[非退行] python_repl呼び出しの記録機構（python_calls_log、BL-093/BL-045）は
    呼び出し元ラベルに依存しないこと（ドメイン妥当性レビューからの呼び出しも
    数値監査パスと同じ経路で記録されることの存在確認）。"""
    src = inspect.getsource(cela_main._query_AI_live)
    assert 'tc.function.name == "python_repl"' in src
    assert "python_calls_log.append(" in src


# ---------------------------------------------------------------------------
# 4. PYTHON_REPL_TOOL自体の説明文（全ノード共通、ユーザー申し送り事項）
# ---------------------------------------------------------------------------

def _python_repl_tool_description() -> str:
    return cela_main.PYTHON_REPL_TOOL["function"]["description"]


def test_python_repl_tool_description_mentions_text_parsing_use_case():
    """[BL-300追記] PYTHON_REPL_TOOLの説明文が、数値計算だけでなくテキストの
    機械的な分割・位置特定という用途も明記していること（従来は"mechanical
    arithmetic/verification"としか書かれておらず、この用途が案内されていなかった）。"""
    desc = _python_repl_tool_description()
    assert "arithmetic" in desc  # 既存の数値計算用途の案内は維持されていること
    assert "split" in desc.lower() or "index" in desc.lower()
    assert "not_found" in desc  # BL-299/300の実インシデント（grep失敗）に触れていること


def test_python_repl_tool_description_allowed_modules_match_actual_whitelist():
    """[BL-300追記] 説明文中の許可モジュール一覧が、実際の_ALLOWED_IMPORTSと
    一致していること（BL-058で追加されたitertools/functools/collections/operator/reが
    説明文から欠落していた、BL-299と同型のスキーマ説明文ドリフトの再発防止）。"""
    desc = _python_repl_tool_description()
    for module_name in cela_main._ALLOWED_IMPORTS:
        assert module_name in desc, f"{module_name}が説明文に含まれていない"


def test_python_repl_tool_description_still_instructs_print_usage():
    """[非退行] print()必須という既存の重要な注意書きが、今回の追記で失われていないこと。"""
    desc = _python_repl_tool_description()
    assert "print(" in desc
    assert "no output" in desc.lower()
