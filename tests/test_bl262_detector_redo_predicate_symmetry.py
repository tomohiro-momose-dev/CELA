"""
BL-262: 差し戻し判定の条件が、ルーティング側とpop-guard側で非対称になっており、
同一roleが連続するchat_historyが生成されていた問題。

実ドライラン（`log/2026-07-22/2320`等）で「⚠️ role連続を検出: index N,N = 'user'」の警告が
多数観測されていた。`_query_AI_live`（cela_main.py）はこれを検知して警告するだけで是正しない。

根本原因: Detectorの判定後に「発言者へ差し戻すか」を決めるルーティング
（`route_after_user_detector` / `route_after_expert_detector`）は
`constraint_issue == "major" または halt` を条件としていたが、差し戻すなら直前のNG発言を
chat_historyから取り消すpop-guard（`generate_user_utterance_node` / `expert_node`）は
`constraint_issue == "major"` しか見ていなかった。`risk`と`constraint_issue`はDetectorの
独立したフィールドであり、`risk="high"`（→`halt=True`）かつ`constraint_issue`がmajor以外という
経路が実在する。この経路ではルーティングが差し戻す一方でpop-guardが発火せず、取り消されない
ままのNG発言の後ろに新しい発言が積まれてrole連続になる。

副次的な問題: 4箇所すべてが`state.get("constraint_issue") in ("major")`と書かれていた。
`("major")`はタプルではなくただの文字列なので、これは部分文字列一致（`x in "major"`）になる。
`constraint_issue`はDBの既定値が空文字（`constraint_issue TEXT DEFAULT ''`）でLLMも空文字を
返しうるところ、`"" in "major"`はTrueであるため、「指摘なし」が差し戻し扱いされていた
（AGENTS.md §13.1 空文字トラップ）。

対策: 共有述語`_is_detector_redo_required(state)`へ4箇所すべてを集約し、判定を`== "major"`に
是正した（AGENTS.md §15.1「1つのルールは1箇所に」）。

参照: docs/design/back_log/issue_backlog.md BL-262。実LLM API呼び出しは伴わない。
"""

import inspect
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import cela_main  # noqa: E402


# --- 述語そのものの判定 ---

def test_major_constraint_issue_requires_redo():
    """constraint_issue='major'は従来どおり差し戻し対象であること。"""
    assert cela_main._is_detector_redo_required({"constraint_issue": "major"}) is True


def test_halt_alone_requires_redo():
    """[BL-262本体] risk=high由来のhalt=Trueは、constraint_issueがmajor以外でも差し戻し対象で
    あること。修正前はpop-guard側がこの条件を見ておらず、role連続の直接原因になっていた。"""
    assert cela_main._is_detector_redo_required({"constraint_issue": "none", "halt": True}) is True
    assert cela_main._is_detector_redo_required({"constraint_issue": "minor", "halt": True}) is True


def test_empty_constraint_issue_does_not_require_redo():
    """[BL-262 / AGENTS.md §13.1] 空文字は「指摘なし」であり差し戻し対象ではないこと。
    修正前の`in ("major")`は部分文字列一致だったため、空文字がTrueと判定されていた。"""
    assert cela_main._is_detector_redo_required({"constraint_issue": ""}) is False
    assert cela_main._is_detector_redo_required({"constraint_issue": "", "halt": False}) is False


def test_substring_of_major_does_not_require_redo():
    """`in ("major")`（部分文字列一致）への退行を検出する。'majo'等はmajorではない。"""
    for value in ("majo", "ajo", "r", "ma"):
        assert cela_main._is_detector_redo_required({"constraint_issue": value}) is False, value


def test_none_and_minor_do_not_require_redo():
    assert cela_main._is_detector_redo_required({"constraint_issue": "none"}) is False
    assert cela_main._is_detector_redo_required({"constraint_issue": "minor"}) is False


def test_missing_keys_do_not_crash():
    """stateにキーが無くてもTypeErrorにならないこと（`None in "major"`は例外を送出する）。"""
    assert cela_main._is_detector_redo_required({}) is False


# --- 4箇所が同一述語を使っているか（非対称の再発検出） ---

@pytest.mark.parametrize("func_name", [
    "generate_user_utterance_node",
    "expert_node",
])
def test_pop_guards_use_shared_predicate(func_name):
    """pop-guard側が共有述語を呼んでいること。個別条件へ書き戻されたら失敗する。"""
    src = inspect.getsource(getattr(cela_main, func_name))
    assert "_is_detector_redo_required(state)" in src, f"{func_name}が共有述語を使っていない"
    assert 'in ("major")' not in src, f"{func_name}に部分文字列一致の判定が残っている"


def test_routers_use_shared_predicate():
    """ルーティング側2箇所が共有述語を呼んでいること。

    ルータは`build_graph`内のクロージャとして定義されているため、モジュールソース全体に対して
    定義位置を特定した上で本体を検査する。"""
    src = inspect.getsource(cela_main)
    for router in ("route_after_user_detector", "route_after_expert_detector"):
        idx = src.index(f"def {router}(state")
        body = src[idx: idx + 1200]
        assert "_is_detector_redo_required(state)" in body, f"{router}が共有述語を使っていない"
        assert 'in ("major")' not in body, f"{router}に部分文字列一致の判定が残っている"


def test_no_substring_major_check_remains_in_module():
    """モジュール全体に`in ("major")`形式の判定が残っていないこと（docstringの説明を除く）。"""
    src = inspect.getsource(cela_main)
    code_lines = [
        line for line in src.splitlines()
        if 'in ("major")' in line and not line.strip().startswith(("#", "[SAFETY]"))
        and "`in" not in line  # docstring内の解説行を除外
    ]
    assert code_lines == [], f"部分文字列一致の判定が残存: {code_lines}"


# --- pop-guardの実挙動（halt単独でも取り消されること） ---

def _make_state(constraint_issue: str, halt: bool) -> dict:
    return {
        "constraint_issue": constraint_issue,
        "halt": halt,
        "chat_history": [
            {"role": "assistant", "content": "Expertの発言"},
            {"role": "user", "content": "User AIのNG発言"},
        ],
        "user_retry_count": 0,
    }


def test_pop_guard_removes_ng_utterance_on_halt_only(monkeypatch):
    """[BL-262実インシデント再現] halt=True・constraint_issue='none'のとき、
    generate_user_utterance_nodeが直前のuser発言を取り消すこと。修正前は取り消されず、
    この後のappendでuser,userの連続が生まれていた。

    ノード本体はLLM呼び出しを含むため、pop-guard通過直後に打ち切る番兵例外で検証する。"""
    state = _make_state("none", halt=True)

    class _Sentinel(Exception):
        pass

    def _stop(*args, **kwargs):
        raise _Sentinel()

    # ノードは実行時グローバルの`config`を引数に渡すため、参照可能にしておく
    # （評価順の都合で、未定義のままだと番兵に到達する前にNameErrorになる）。
    monkeypatch.setattr(cela_main, "config", object(), raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", _stop)

    with pytest.raises(_Sentinel):
        cela_main.generate_user_utterance_node(state)

    assert len(state["chat_history"]) == 1, "halt単独でもNG発言が取り消されるはず"
    assert state["chat_history"][-1]["role"] == "assistant"
    assert state["user_retry_count"] == 1


def test_pop_guard_keeps_history_when_no_redo_required(monkeypatch):
    """[対照] 差し戻し不要（constraint_issue='none'・halt=False）なら履歴を触らないこと。"""
    state = _make_state("none", halt=False)

    class _Sentinel(Exception):
        pass

    def _stop(*args, **kwargs):
        raise _Sentinel()

    # ノードは実行時グローバルの`config`を引数に渡すため、参照可能にしておく
    # （評価順の都合で、未定義のままだと番兵に到達する前にNameErrorになる）。
    monkeypatch.setattr(cela_main, "config", object(), raising=False)
    monkeypatch.setattr(cela_main, "generate_user_utterance", _stop)

    with pytest.raises(_Sentinel):
        cela_main.generate_user_utterance_node(state)

    assert len(state["chat_history"]) == 2, "差し戻しでないなら履歴は保持されるはず"
    assert state["user_retry_count"] == 0
