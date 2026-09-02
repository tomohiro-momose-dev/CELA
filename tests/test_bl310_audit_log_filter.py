"""
BL-310: 監査ログフィルタ（`--audit-log`）の追加。

ユーザー要望（原文）: 「コマンドラインの監査ログをもっと充実させたい。現在のlog_no_prompt
ログから思考ログを除いたもの。ただし、db登録や参照状況は表示、オプションで各ノードの
thinkも表示。どうでしょうか？」

既存のlog_no_prompt.mdは、💭ストリーミング思考（実機では数千〜数万字に及ぶことがある、
BL-297〜305で繰り返し観測）と、write_agreement/write_issue等のDB登録・参照行が混在して
おり、後者だけを素早く追いたい場合の可読性が低かった。ライブ（ドライラン中にMultiLogger
へ3本目のストリームを追加）ではなく、既存ログを事後的にフィルタする軽量な方式を選択した
（実装がシンプルで壊れにくく、過去ログにも遡って使える。ユーザー承認: 「事後フィルタ
（Recommended）」を選択）。

除外対象は2種類（ユーザー承認: 「その理解で合っている」）:
1. 💭ストリーミング思考の生プローズ
2. thinkツールの呼び出し・結果（🔧 ... think 実行 + 直後の→結果）
それ以外（他の🔧ツール実行、DB登録・状態変化行、💬最終発言）は全て残す。
show_think=Trueでthinkツール呼び出しのみ復元する（💭は常に除外）。

実際のログ（log/2026-08-29/1147、log/2026-08-28/1919）に対して目視検証済み
（1919は45%の文字数削減、1147は12%——後者は元々reasoningの比率が低い内容だった
ため、削減率の低さ自体は不具合ではないことを個別に確認した）。

参照: BL-274/BL-309（既存の対話型CLI群と並ぶ、読み取り専用監査コマンド）。
実LLM API呼び出しは伴わない。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


def test_bl310_removes_single_line_reasoning_block():
    text = (
        "[10:00:00] 💭 [Detector] 思考（iter=1）:\n"
        "[10:00:00] これは思考の本文です。\n"
        "[10:00:01] 🔧 [Detector] read_agreement 実行（iter=1）: {\"task_id\": \"task_1_1\"}\n"
    )
    out = cela_main.filter_audit_log_text(text)
    assert "思考の本文" not in out
    assert "💭" not in out
    assert "read_agreement 実行" in out


def test_bl310_removes_multiline_reasoning_block_until_structural_marker():
    text = (
        "[10:00:00] 💭 [Detector] 思考（iter=1）:\n"
        "[10:00:00] 1行目の思考。\n"
        "\n"
        "[10:00:01] 2行目の思考、複数段落にわたる長いプローズ。\n"
        "[10:00:02] 3行目。まだ思考は続く。\n"
        "[10:00:03] 📝 [write_agreement] detectorがDecision（CREATE）を記録しました: topic=foo\n"
    )
    out = cela_main.filter_audit_log_text(text)
    for phrase in ("1行目の思考", "2行目の思考", "3行目。まだ思考は続く"):
        assert phrase not in out
    assert "📝 [write_agreement]" in out
    assert "topic=foo" in out


def test_bl310_removes_reasoning_block_terminated_by_eof():
    """[境界値] 思考ブロックの後に構造マーカー行が一切無くファイルが終わる場合も、
    正しく末尾まで除外されること（IndexErrorを起こさないことも含む）。"""
    text = (
        "[10:00:00] 💭 [Detector] 思考（iter=1）:\n"
        "[10:00:00] 最後まで思考のまま終わるログ。\n"
    )
    out = cela_main.filter_audit_log_text(text)
    assert "最後まで思考のまま終わる" not in out


def test_bl310_removes_think_tool_call_by_default():
    text = (
        '[10:00:00] 🔧 [Detector] think 実行（iter=1）: {"action": "整理", "summary": "要約"}\n'
        "→ {'reasoning_log_so_far': [...]}\n"
        "[10:00:00] \n"
        "[10:00:01] 🔧 [Detector] read_verified_fact 実行（iter=1）: {\"variable_name\": \"x\"}\n"
    )
    out = cela_main.filter_audit_log_text(text)
    assert "think 実行" not in out
    assert "reasoning_log_so_far" not in out
    assert "read_verified_fact 実行" in out


def test_bl310_show_think_true_restores_think_tool_call():
    text = (
        '[10:00:00] 🔧 [Detector] think 実行（iter=1）: {"action": "整理"}\n'
        "→ {'reasoning_log_so_far': [...]}\n"
    )
    out = cela_main.filter_audit_log_text(text, show_think=True)
    assert "think 実行" in out
    assert "reasoning_log_so_far" in out


def test_bl310_show_think_true_still_removes_streaming_reasoning():
    """[非退行] show_think=Trueでも、💭ストリーミング思考は常に除外されること
    （ユーザー指定: thinkツールのみ復元、生の思考ストリームは対象外）。"""
    text = (
        "[10:00:00] 💭 [Detector] 思考（iter=1）:\n"
        "[10:00:00] ストリーミング思考本文。\n"
        '[10:00:01] 🔧 [Detector] think 実行（iter=1）: {"action": "整理"}\n'
        "→ {'x': 1}\n"
    )
    out = cela_main.filter_audit_log_text(text, show_think=True)
    assert "ストリーミング思考本文" not in out
    assert "think 実行" in out


def test_bl310_preserves_non_think_tool_calls_and_db_lines_verbatim():
    text = (
        "[10:00:00] 🧰 [Detector] tools attached: ['python_repl', 'think']\n"
        '[10:00:01] 🔧 [Detector] python_repl 実行（iter=1）:\n'
        "x = 1 + 1\n"
        "print(x)\n"
        "[10:00:02]   📝 [write_agreement] detectorがDecision（CREATE）を記録しました: topic=bar\n"
        "[10:00:03] 💬 [Detector] 発言（iter=2）:\n"
        "[10:00:03] 最終的な回答テキストです。\n"
        "[10:00:04] ✅ ツールループ終了（iter=2, tool_calls=0）\n"
    )
    out = cela_main.filter_audit_log_text(text)
    assert out == text  # 思考・thinkが無いテキストは一切変更されないこと


def test_bl310_preserves_role_label_lines_as_structural():
    """[構造マーカーの確認] `[detector]`のような役割名だけの行（decisions INSERT表示の
    一部）は構造マーカーとして扱われ、思考ブロックを正しく終端させること。"""
    text = (
        "[10:00:00] 💭 [Detector] 思考（iter=1）:\n"
        "[10:00:00] 思考プローズ。\n"
        "[10:00:01] [detector]\n"
        "[10:00:01]   - what: risk=low\n"
    )
    out = cela_main.filter_audit_log_text(text)
    assert "思考プローズ" not in out
    assert "[detector]" in out
    assert "- what: risk=low" in out


def test_bl310_cli_flags_registered_and_dispatch_present():
    """[配線確認] --audit-log/--show-thinkがargparseへ登録され、filter_audit_log_textへ
    ディスパッチする分岐がソース上に存在すること。"""
    import inspect
    src = inspect.getsource(cela_main)
    assert '"--audit-log"' in src
    assert '"--show-think"' in src
    assert "_cli_args.audit_log:" in src
    assert "filter_audit_log_text(_log_text, show_think=_cli_args.show_think)" in src


def test_bl310_real_log_reduces_size_and_keeps_write_agreement_lines():
    """[実ログでの健全性確認] 本セッション中に実際に取得したログファイルに対して、
    (1) 出力が入力より短くなること（reasoning/thinkが実在すれば必ず何か削られる）、
    (2) write_agreementの実行ログは残っていること、を確認する。"""
    log_path = os.path.join("log", "2026-08-29", "1147", "log_no_prompt.md")
    if not os.path.isfile(log_path):
        import pytest
        pytest.skip("この開発環境固有の実ログが存在しないためスキップ")
    with open(log_path, encoding="utf-8") as f:
        text = f.read()
    out = cela_main.filter_audit_log_text(text)
    assert len(out) < len(text)
    assert "write_agreement 実行" in out
    assert "💭" not in out
