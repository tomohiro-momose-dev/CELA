"""
# 要件定義書: CELA — 認知型経験系譜駆動マルチエージェントシステム
# (Cognitive Experience Lineage-driven Agent System)
# """

from __future__ import annotations

import json
from secrets import choice
import time
import sys
import os
import datetime
import traceback
import sqlite3
import uuid
import hashlib
import ast
import subprocess
import threading
from typing import Annotated, Literal, TypedDict

def _take_latest(a, b):
    """【SLM要約】
    Selection of the second provided input (`b`) as the resulting state, effectively prioritizing newer or subsequent data.
    """
    return b
import re
from unittest import result

from langgraph.graph import StateGraph, END
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError


# ===========================================================================
# ロギング設定（ログを ./log/ ディレクトリに保存）
# ===========================================================================
class MultiLogger:

    _instance = None
    log_dir = "log"  # クラス変数として保持し、他から参照可能にする

    def __new__(cls):
        """【SLM要約】
        Enforcing singleton pattern for `MultiLogger` instance creation, ensuring only one logger object exists throughout the system.
        """
        if cls._instance is not None:
            print("⚠️ MultiLoggerは既に初期化済みです。二重初期化をスキップします。")
            return cls._instance
        cls._instance = super().__new__(cls)
        return cls._instance
    
    _initialized = False

    def __init__(self):
        """【SLM要約】
        Initialization and setup of the logging mechanism, creating time-stamped directories and opening dual log files for structured output.
        """
        if MultiLogger._initialized:
            return
        MultiLogger._initialized = True
        self.terminal = sys.__stdout__
        now = datetime.datetime.now()
        
        # 日付フォルダを作成 (log/YYYY-MM-DD/HHMM形式)
        date_folder = now.strftime("%Y-%m-%d")
        time_folder = now.strftime("%H%M")
        log_dir = os.path.join("log", date_folder, time_folder)
        MultiLogger.log_dir = log_dir # クラス変数にセット
        os.makedirs(log_dir, exist_ok=True)
        
        self.filename_with = os.path.join(log_dir, "log_with_prompt.md")
        self.filename_no = os.path.join(log_dir, "log_no_prompt.md")
        
        self.file_with_prompt = open(self.filename_with, "a", encoding="utf-8")
        self.file_no_prompt = open(self.filename_no, "a", encoding="utf-8")
        
        start_msg = f"# Execution Log Started at: {now.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        self.file_with_prompt.write(start_msg)
        self.file_no_prompt.write(start_msg)
        
        self.is_prompt_mode = False
        print("📝 ログの出力設定を完了しました:")
        print("   - [ターミナル表示]   : プロンプト非表示")
        print(f"   - [プロンプトあり] : {self.filename_with}")
        print(f"   - [プロンプトなし] : {self.filename_no}")
        print("============================================================\n")

    def write(self, message):
        """【SLM要約】
        Content output routing: directs a message to the prompt file, terminal, and/or other specified logs based on system mode.
        """
        if self.is_prompt_mode:
            self.file_with_prompt.write(message)
        else:
            self.terminal.write(message)
            self.file_with_prompt.write(message)
            self.file_no_prompt.write(message)

    def flush(self):
        """【SLM要約】
        Synchronization of buffered output streams (terminal and two specific files) to ensure immediate data visibility.
        """
        self.terminal.flush()
        self.file_with_prompt.flush()
        self.file_no_prompt.flush()

    def set_prompt_mode(self, mode: bool):
        """【SLM要約】
        Toggling the internal state to enable or disable prompt-related operational modes within the system.
        """
        self.is_prompt_mode = mode

# [CONSTRAINT] BL-027: importするだけでログディレクトリ作成/stdout差し替えが
# 走ると、smoke test等がcela_mainをimportするたびに本番log/配下へ
# タイムスタンプ付きディレクトリを無断作成してしまう（実際に発生した事故）。
# 実行時（__main__としての起動時）にのみ有効化する。

# ===========================================================================
# ファイル出力用ユーティリティ
# ===========================================================================
def save_deliverable_to_file(topic: str, content: str) -> str:
    """【SLM要約】
    Serialization of final outputs into time-stamped, sanitized Markdown files within the system's log directory.
    """
    """成果物をMarkdownファイルとしてlogディレクトリ内に保存し、そのパスを返す"""
    safe_topic = re.sub(r'[\\/*?:"<>|]', "_", topic).strip()
    if not safe_topic:
        safe_topic = "deliverable"
    safe_topic = safe_topic[:50] # 長すぎるファイル名を防止
    filename = f"{safe_topic}_{int(time.time())}.md"
    
    log_dir = getattr(MultiLogger, "log_dir", "log")
    deliv_dir = os.path.join(log_dir, "deliverables")
    os.makedirs(deliv_dir, exist_ok=True)
    
    filepath = os.path.join(deliv_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


# ===========================================================================
# クライアント・モデル設定（APIキーは環境変数から読み込み）
# ===========================================================================
# .envファイルに以下のように設定してください:
#   GEMINI_API_KEY=your_key_here
#   GEMINI_API_KEY_AUDITOR=your_auditor_key_here
#   FLM_BASE_URL=http://localhost:52625/v1

import os

deepseek = "deepseek-r1-0528:8b"
gemini_2_5 = "gemini-2.5-flash-lite"
gemini_3_1 = "gemini-3.1-flash-lite"
gemma_local = "gemma4-it:e4b"
#deepseek_v4_flash = "deepseek-v4-flash"
deepseek_v4_flash = "deepseek-v4-flash"
_gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
_gemini_auditor_key = os.environ.get("GEMINI_API_KEY_AUDITOR", "")
_deepseek_v4_flash_auditor_key = os.environ.get("DSEEK_V4_FLASH_AUDITOR_KEY", "")
_deepseek_v4_flash_user_key = os.environ.get("DSEEK_V4_FLASH_USER_KEY", "")

_flm_base_url = os.environ.get("FLM_BASE_URL", "http://localhost:52625/v1")

client_local = OpenAI(
    base_url=_flm_base_url,
    api_key="FLM"
)

client_gemini = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=_gemini_api_key
)

client_gemini_Auditor = OpenAI(
    base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
    api_key=_gemini_auditor_key
)


# 🌟 OpenRouter用クライアントを追加
client_openrouter = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=_deepseek_v4_flash_user_key
)

if not _gemini_api_key:
    print("⚠️ 警告: 環境変数 GEMINI_API_KEY が設定されていません。")
    print("   実行前に set GEMINI_API_KEY=your_key を設定してください。")
if not _gemini_auditor_key:
    print("⚠️ 警告: 環境変数 GEMINI_API_KEY_AUDITOR が設定されていません。")
    print("   実行前に set GEMINI_API_KEY_AUDITOR=your_key を設定してください。")

# 役割ごとのモデル割り当て
"""
client_user = client_gemini
model_user = gemini_2_5

client_agent = client_gemini
model_agent = gemini_2_5

client_auditor = client_gemini_Auditor
model_auditor = gemini_3_1
"""

client_summarizer = client_local
model_summarizer = gemma_local

client_user = client_openrouter
model_user = deepseek_v4_flash

client_agent = client_openrouter
model_agent = deepseek_v4_flash

client_auditor = client_openrouter
model_auditor = deepseek_v4_flash

LOW_TEMP_LABEL_KEYWORDS = ("detector", "reflection", "review", "decision extractor", "summarizer")
# JSON厳密出力が必要なノードのラベル（部分一致）
STRUCTURED_OUTPUT_LABEL_KEYWORDS = ("detector", "decision extractor", "reflection", "review", "orchestrator")


MAX_TOKENS_BY_ROLE = {
    "expert": 524288,
    "user": 262144,
    "detector": 262144,
    "reflection": 262144,
    "review": 262144,
    "decision extractor": 131072,
    "orchestrator": 65536,
}

def get_max_tokens(label: str) -> int:
    """【SLM要約】
    Determining the maximum allowed token count based on a provided role or label string.
    """
    label_lower = label.lower()
    for keyword, tokens in MAX_TOKENS_BY_ROLE.items():
        if keyword in label_lower:
            return tokens
    return 131072  # デフォルト


# ---------------------------------------------------------------------------
# Record & Replay スタブ（R1完了条件・回帰確認用、設計書§7.1準拠）
# ---------------------------------------------------------------------------
REPLAY_MODE = os.environ.get("CELA_REPLAY_MODE", "off")  # "off" / "record" / "replay"
_REPLAY_FIXTURE_PATH = os.environ.get("CELA_REPLAY_FIXTURE_PATH", "")
_call_seq_counter = 0
_replay_fixtures: dict[str, dict] = {}


def reset_call_seq() -> None:
    """【SLM要約】
    call_seqをrun単位でリセットする。Record時とReplay時のカウント開始位置のずれによる全件ミスを防ぐ。
    """
    global _call_seq_counter
    _call_seq_counter = 0


def _hash_messages_for_replay(messages: list[dict]) -> str:
    """【SLM要約】
    タイムスタンプ・run_id・連番等の揮発値を含まないメッセージ内容のみの正規化ハッシュを計算する（検証用のみ、一致判定はしない）。
    """
    normalized = "␟".join(f"{m.get('role', '')}:{m.get('content', '')}" for m in messages)
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def _load_replay_fixtures(path: str) -> dict:
    """【SLM要約】
    Replayモード起動時に、事前記録済みの(label, call_seq)キー付きフィクスチャをJSONファイルから読み込む。
    """
    if not path or not os.path.exists(path):
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_replay_fixtures(path: str, fixtures: dict) -> None:
    """【SLM要約】
    Recordモードで蓄積したフィクスチャをJSONファイルへ都度保存し、途中終了時のデータ消失を防ぐ。
    """
    dirname = os.path.dirname(path)
    if dirname:
        os.makedirs(dirname, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(fixtures, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# R2: ツール呼び出し基盤・機械的検算ゲート（設計書§3.5.3、impl_Plan R2.2〜R2.4準拠）
# ---------------------------------------------------------------------------

# 許可モジュール（ホワイトリスト）。random は除外（検算の決定性＝再現性を損なうため、D-007）。
# decimal/fractions は浮動小数点誤差回避の目的に合致する拡張として維持（D-007、AGENTS.md§7承認済み変更）。
_ALLOWED_IMPORTS = {"math", "statistics", "datetime", "json", "fractions", "decimal"}

# 危険な名前（import文なしで呼べるビルトイン・組み込み関数）。AST上のName/Attribute/Call参照として検査（D-006）。
_DANGEROUS_NAMES = {
    "open", "eval", "exec", "compile", "__import__", "globals", "locals",
    "vars", "getattr", "setattr", "delattr", "memoryview", "breakpoint",
}


def _check_repl_code_safety(code: str) -> str | None:
    """【SLM要約】
    python_repl用ASTセキュリティ検査。許可モジュール外のimport・危険なビルトイン呼び出し
    （open/eval/exec/__import__等）を拒否する（設計書§3.5.3、D-006）。安全なら None を返す。
    """
    # [CONSTRAINT] サンドボックスエスケープを防ぐため、実行前にASTレベルで危険なimport/呼び出しを拒否する。
    try:
        tree = ast.parse(code)
    except SyntaxError as e:
        return f"[REPL Error] SyntaxError: {e}"
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] not in _ALLOWED_IMPORTS:
                    return f"[REPL Error] import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in _ALLOWED_IMPORTS:
                return f"[REPL Error] import from '{node.module}' is not allowed"
        elif isinstance(node, ast.Name) and node.id in _DANGEROUS_NAMES:
            return f"[REPL Error] use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr in _DANGEROUS_NAMES:
            return f"[REPL Error] use of '.{node.attr}' is not allowed"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_NAMES:
                return f"[REPL Error] call to '{node.func.id}' is not allowed"
    return None


def _run_python_repl(code: str, timeout: float = 5.0, max_output_bytes: int = 10240) -> str:
    """【SLM要約】
    F-2.6/F-5.1向けの機械的検算用サンドボックス実行（ステートレス・単発版）。math/statistics/datetime/
    json/fractions/decimalのみ許可し、危険な呼び出しをASTレベルで検査・拒否した上でサブプロセス分離実行
    する（設計書§3.5.3）。呼び出しごとに独立プロセスなので状態は保持しない。単体テスト・将来の単発検算
    用途向けに維持（対話セッションでの実運用は`_PythonReplSession`を使う、BL-014原因A）。
    """
    safety_error = _check_repl_code_safety(code)
    if safety_error is not None:
        return safety_error
    try:
        # [SAFETY] 多層防御: AST blacklistだけでは().__class__.__bases__経由等の既知の回避を完全には
        # 防げないため、サブプロセス分離＋isolated modeを併用する（絶対に破れないサンドボックスではなく
        # 多層防御であることが設計上の限界、設計書§3.5.3）。
        # [CONSTRAINT] -I（isolated mode）はPYTHONIOENCODING等のPYTHON*環境変数を無視するため、
        # 子プロセスがcp932ロケール（Windows既定）で絵文字等をprint()すると子プロセス自身が
        # UnicodeEncodeErrorでクラッシュする。-X utf8は-Iと共存でき、子プロセスの標準入出力を
        # UTF-8に固定できる（実機確認済み）。親側のcapture_outputも同様にUTF-8を明示する。
        proc = subprocess.run(
            ["python", "-I", "-X", "utf8", "-c", code],
            capture_output=True, encoding="utf-8", errors="replace", timeout=timeout,
        )
        out = (proc.stdout or "") + (proc.stderr or "")
        if len(out.encode("utf-8")) > max_output_bytes:
            out = out[:max_output_bytes] + "\n[REPL Output truncated]"
        return out.strip() or "[REPL] (no output)"
    except subprocess.TimeoutExpired:
        return f"[REPL Error] execution exceeded {timeout}s timeout"


_REPL_SESSION_SENTINEL = "\x00CELA_REPL_END\x00"
_REPL_SESSION_BOOTSTRAP = f"""
import sys, json, traceback
ns = {{}}
while True:
    line = sys.stdin.readline()
    if not line:
        break
    try:
        code = json.loads(line)
    except Exception:
        code = ""
    try:
        exec(code, ns)
    except Exception:
        traceback.print_exc()
    print({_REPL_SESSION_SENTINEL!r}, flush=True)
"""


class _PythonReplSession:
    """【SLM要約】
    F-2.6用の対話的（状態保持）python_replセッション（BL-014原因A対応）。ツールループ1回分
    （1回の_query_AI_live呼び出し）の間だけ、1つの子プロセスを使い回し変数を保持する。
    ノードをまたぐ・リトライをまたぐ状態共有はしない（各回で新規インスタンス）。
    [SAFETY] コード自体のAST安全検査は毎回の送信ごとに実施する（状態保持は変数の値のみで、
    サンドボックス境界自体は既存の許可モジュール・危険ビルトイン検査をそのまま適用する）。
    """

    def __init__(self, timeout: float = 5.0, max_output_bytes: int = 10240):
        self._timeout = timeout
        self._max_output_bytes = max_output_bytes
        self._proc: subprocess.Popen | None = None

    def _ensure_started(self) -> None:
        if self._proc is not None:
            return
        self._proc = subprocess.Popen(
            ["python", "-I", "-X", "utf8", "-c", _REPL_SESSION_BOOTSTRAP],
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            encoding="utf-8", errors="replace", bufsize=1,
        )

    def run(self, code: str) -> str:
        safety_error = _check_repl_code_safety(code)
        if safety_error is not None:
            return safety_error

        self._ensure_started()
        proc = self._proc
        assert proc is not None and proc.stdin is not None and proc.stdout is not None

        try:
            proc.stdin.write(json.dumps(code) + "\n")
            proc.stdin.flush()
        except (BrokenPipeError, OSError) as e:
            self.close()
            return f"[REPL Error] session process unavailable: {e}"

        result_holder: dict[str, str] = {}

        def _reader() -> None:
            lines: list[str] = []
            while True:
                line = proc.stdout.readline()
                if not line:
                    break
                if line.rstrip("\n") == _REPL_SESSION_SENTINEL:
                    break
                lines.append(line)
            result_holder["out"] = "".join(lines)

        reader_thread = threading.Thread(target=_reader, daemon=True)
        reader_thread.start()
        reader_thread.join(self._timeout)
        if reader_thread.is_alive():
            # [CONSTRAINT] ハングした子プロセスは復旧不能なので終了させ、次回呼び出しで新規
            # プロセスを立て直す（＝状態は失われる）。この回のエラーメッセージでその旨を
            # モデルに明示し、無言で状態が消えて混乱するのを防ぐ（D-009と同じ思想）。
            self.close()
            return (
                f"[REPL Error] execution exceeded {self._timeout}s timeout. "
                "The REPL session has been reset — variables defined in earlier "
                "calls no longer exist; redefine what you need in your next call."
            )

        if proc.poll() is not None:
            # 子プロセスが応答なく終了していた場合も同様にセッションを再構築する。
            self.close()

        out = result_holder.get("out", "")
        if len(out.encode("utf-8")) > self._max_output_bytes:
            out = out[: self._max_output_bytes] + "\n[REPL Output truncated]"
        return out.strip() or "[REPL] (no output)"

    def close(self) -> None:
        if self._proc is None:
            return
        proc, self._proc = self._proc, None
        try:
            proc.terminate()
            proc.wait(timeout=2)
        except Exception:
            try:
                proc.kill()
            except Exception:
                pass


PYTHON_REPL_TOOL = {
    "type": "function",
    "function": {
        "name": "python_repl",
        "description": (
            "Execute a Python snippet for mechanical arithmetic/verification (e.g. sum, ratio, "
            "threshold comparison). Sandboxed: only math/statistics/datetime/json/fractions/decimal allowed, "
            "no network/IO. Use this to VERIFY any numeric claim before asserting correctness. "
            "STATEFUL within this turn: variables/imports from your earlier python_repl calls in this "
            "same turn remain available in later calls (like a persistent REPL/notebook cell) — you do "
            "NOT need to redefine them each time. This state is reset at the start of your next turn. "
            "IMPORTANT: each call still only shows output you explicitly print — a bare expression like "
            "'2500 + 300 + 800' alone produces NO output. You MUST wrap it in print(...), e.g. "
            "'print(2500 + 300 + 800)'. If a previous call returned '[REPL] (no output)', you forgot "
            "print() — retry with print() instead of repeating the same bare expression."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": (
                        "Python code to execute. Must call print(...) to produce visible output "
                        "(e.g. 'print(100+50*3)') — bare expressions are silently discarded."
                    ),
                }
            },
            "required": ["code"],
        },
    },
}

TOOL_DISPATCH = {
    "python_repl": _run_python_repl,
}

# BL-033: 直前のquery_AI呼び出しでLLMが実際に実行したpython_replの(code, result)記録。
# ノードをまたいでも参照できるよう、呼び出し元(expert_node等)がstateへコピーする前提の
# 一時バッファ（stateにはシリアライズ不要な生実行ログを持たせない方針、_DB_CONNと同様）。
_LAST_PYTHON_CALLS: list[dict] = []


def get_last_python_calls() -> list[dict]:
    """【SLM要約】
    直前のquery_AI呼び出しで実際に実行されたpython_replのcode/result記録のコピーを返す。
    """
    return list(_LAST_PYTHON_CALLS)


def query_AI(messages: list[dict], client: OpenAI, model: str, label: str = "Unknown Node", tools: list[dict] | None = None,
             light_system_prompt: str | None = None) -> str:
    """【SLM要約】
    Orchestration of external AI API calls with Record/Replay stub support (keyed by (label, call_seq)),
    delegating the actual retry/provider-selection logic to _query_AI_live.
    """
    global _call_seq_counter, _LAST_PYTHON_CALLS
    _LAST_PYTHON_CALLS = []

    call_seq = _call_seq_counter
    _call_seq_counter += 1
    fixture_key = f"{label}|{call_seq}"
    msg_hash = _hash_messages_for_replay(messages)

    if REPLAY_MODE == "replay":
        if fixture_key not in _replay_fixtures:
            raise RuntimeError(
                f"REPLAY cache miss at (label={label}, seq={call_seq}). "
                f"フィクスチャが揃っていないか、list版とSQLite版で呼び出し順序が異なります。"
            )
        cached = _replay_fixtures[fixture_key]
        if cached.get("hash") != msg_hash:
            print(
                f"⚠️ [REPLAY] (label={label}, seq={call_seq}) のメッセージハッシュが記録時と不一致です。"
                f"プロンプト内容が list版/SQLite版 で異なる可能性があります（再生は続行します）。"
            )
        return cached["content"]

    if REPLAY_MODE == "record" and fixture_key in _replay_fixtures:
        raise RuntimeError(
            f"REPLAY record時に重複キー (label={label}, seq={call_seq}) を検出しました。呼び出し順序が非決定的です。"
        )

    content = _query_AI_live(messages, client, model, label, tools=tools, light_system_prompt=light_system_prompt)

    if REPLAY_MODE == "record":
        _replay_fixtures[fixture_key] = {"content": content, "hash": msg_hash}
        if _REPLAY_FIXTURE_PATH:
            _save_replay_fixtures(_REPLAY_FIXTURE_PATH, _replay_fixtures)

    return content


_JAPANESE_OUTPUT_DIRECTIVE = "【重要】あなたは必ず日本語で出力してください。中国語・英語での出力は一切禁止します。"


def _inject_japanese_output_directive(messages: list[dict]) -> list[dict]:
    """[CONSTRAINT] 中国語系モデル(DeepSeek)経由のため、まれに中国語（まれに英語）で出力される
    ことがある。既存のsystem messageがあれば追記し、なければ新規system messageとして先頭に挿入する
    （新規追加時に既存messages[0]もsystemだと連続role警告を誘発するため、あくまで「なければ追加」）。
    """
    if messages and messages[0].get("role") == "system":
        patched_first = dict(messages[0])
        patched_first["content"] = f"{patched_first['content']}\n\n{_JAPANESE_OUTPUT_DIRECTIVE}"
        return [patched_first, *messages[1:]]
    return [{"role": "system", "content": _JAPANESE_OUTPUT_DIRECTIVE}, *messages]


def _query_AI_live(messages: list[dict], client: OpenAI, model: str, label: str = "Unknown Node", tools: list[dict] | None = None,
                    light_system_prompt: str | None = None) -> str:
    """【SLM要約】
    Orchestration of external AI API calls, managing retries, dynamic parameter tuning (temperature, JSON mode), and provider selection based on the requested task label.
    tools付与時はツール呼び出しループ（R2.3、query_AI集約方式、D-008）をリトライブロック内側で実行する（D-004）。
    """
    messages = _inject_japanese_output_directive(messages)

    # role連続チェック（デバッグ用、本番でも警告ログとして残す価値あり）
    for i in range(1, len(messages)):
        if messages[i]["role"] == messages[i-1]["role"]:
            print(f"⚠️ [{label}] role連続を検出: index {i-1},{i} = '{messages[i]['role']}'。APIエラーの原因になる可能性があります。")


    # プロンプトはターミナルに表示せず、ログファイルのみに出力
    # MultiLoggerが有効な場合、set_prompt_modeで制御
    # MultiLoggerが無効な場合（通常は）、プロンプト出力はスキップ
    if hasattr(sys.stdout, 'set_prompt_mode'):
        sys.stdout.set_prompt_mode(True)
        print(f"\n--- 📩 送信プロンプト [{label} | Model: {model}] ---")
        for m in messages:
            print(f"**[{m['role'].upper()}]**:\n```text\n{m['content']}\n```\n")
        print("-----------------------------------")
        sys.stdout.set_prompt_mode(False)
    # else: プロンプトをターミナルに出さない（ログファイルのみ）

    label_lower = label.lower()
    temperature = 0.2 if any(kw in label_lower for kw in LOW_TEMP_LABEL_KEYWORDS) else 0.7
    use_json_mode = any(kw in label_lower for kw in STRUCTURED_OUTPUT_LABEL_KEYWORDS)
    # [CONSTRAINT] response_format=json_objectとtools(Function Calling)は多くのプロバイダで排他的に
    # 動作するため、tools付与時はjson_modeを無効化する（設計書§3.5.1、R2.3）。
    if tools is not None:
        use_json_mode = False

    delays = [8, 16, 32, 64, 128]

    provider_preferences = {
        "provider": {
            "order": ["Fireworks", "nextbit/fp8", "novita/fp8", "parasail/fp8","siliconflow/fp8"],
            "allow_fallbacks": True # リストのプロバイダーが全滅した場合は他を使う
        }
    }

    for attempt in range(len(delays) + 1):
        try:
            time.sleep(5)
            create_kwargs = dict(
                model=model,
                messages=messages,
                temperature=temperature,
            )
            if use_json_mode:
                create_kwargs["response_format"] = {"type": "json_object"}
            if tools is not None:
                create_kwargs["tools"] = tools
                print(f"🧰 [{label}] tools attached: {[t['function']['name'] for t in tools]}")

            # [CONSTRAINT] BL-019: OpenRouterのreasoning要求はフラットな`reasoning_effort`キーではなく
            # ネストした`reasoning: {"effort": ...}`が正しい形式（公式ドキュメント・実機検証で確認済み）。
            # 旧実装は`create_kwargs["reasoning_effort"]`という無効なキーを送っており、
            # OpenRouterにサイレントに無視されてreasoningが一切発火していなかった（response.reasoningが
            # 常にnull）。判定系ノードに加え、ツール付与ノード（Expert/User AI/Resource Arbiter等）にも
            # ツール呼び出し前後の「つぶやき」をログで可視化する目的でlow reasoningを付与する。
            reasoning_effort_level = None
            if label_lower == "detector" or label_lower == "decision extractor":
                reasoning_effort_level = "low"
            elif label_lower == "reflection" or label_lower == "review":
                reasoning_effort_level = "medium"
            elif tools is not None:
                reasoning_effort_level = "low"

            create_kwargs["max_tokens"] = get_max_tokens(label_lower)
            # 🌟 【追加部分】OpenRouter使用時のみ、高速プロバイダーを強制指定する
            if "openrouter" in str(client.base_url):
                extra_body = {
                    "provider": {
                        # 推論速度が速いプロバイダーを左から順に優先して接続させる
                        "order": ["baidu/fp8", "siliconflow/fp8","wandb/fp8","morph"],
                        "allow_fallbacks": False # 全滅した場合は空いている他プロバイダーへ迂回
                    }
                }
                if reasoning_effort_level is not None:
                    extra_body["reasoning"] = {"effort": reasoning_effort_level}
                create_kwargs["extra_body"] = extra_body

            if tools is None:
                response = client.chat.completions.create(**create_kwargs)
                choice = response.choices[0]
                if choice.finish_reason == "length":
                    print(f" [{label_lower}] ⚠️ max_tokens超過により出力が打ち切られました")
                    raise ValueError("Output truncated due to max_tokens limit")
                reasoning_text = getattr(choice.message, "reasoning", None)
                if reasoning_text:
                    print(f"💭 [{label}] 思考:\n{reasoning_text}\n")
                content = response.choices[0].message.content
                return content if content is not None else "(APIから空の応答が返されました)"

            # --- R2.3: ツール呼び出しループ（query_AI集約方式、D-008準拠） ---
            # [CONSTRAINT] 既存try/exceptリトライブロックの内側で回す（D-004）。1回のcreate()が
            # 一時的なAPI障害で失敗した場合、loop_messagesごと破棄し最初からやり直す
            # （リトライ粒度が粗いことは許容済み、BL-009）。
            # [CONSTRAINT] MAX_TOOL_ITERは「ツール呼び出しの往復回数」の上限であり、全回がtool_calls
            # を返すと最終テキスト回答を送る余地が残らず非収束になる（実機ドライランで確認、BL-014）。
            # ユーザー承認によりAGENTS.md §7準拠で5→10へ変更。挙動を見て今後絞る可能性あり。
            # ユーザー承認によりAGENTS.md §7準拠で10→15へ変更（BL-028）。1タスク自身の範囲内の
            # 検算だけでも上限に迫るケースが実ドライランで確認されたため、まずクラッシュ回避を優先。
            MAX_TOOL_ITER = 15
            loop_messages = list(messages)
            create_kwargs["messages"] = loop_messages
            tool_calls_used = 0
            python_calls_log: list[dict] = []  # BL-033: 実行したpython_replのcode/resultを蓄積
            # [CONSTRAINT] BL-014原因A: python_replは1回のツールループの間だけ状態を保持する
            # 対話セッションとする（ノード・リトライをまたいだ状態共有はしない、毎回新規生成）。
            # try/finallyで、成功・非収束・例外いずれの終了経路でも子プロセスを確実に終了させる。
            repl_session = _PythonReplSession()
            try:
                for iteration in range(1, MAX_TOOL_ITER + 1):
                    response = client.chat.completions.create(**create_kwargs)
                    choice = response.choices[0]
                    msg = choice.message
                    # [CONSTRAINT] max_tokens超過によるtool_call引数の途中切れをここで検出する（D-009）。
                    # ValueErrorはAPIError系ではないため下記exceptに飲み込まれず、原因が伝播する。
                    if choice.finish_reason == "length":
                        print(f"⚠️ [{label}] ツールループ内でmax_tokens超過により出力が打ち切られました（iter={iteration}）")
                        raise ValueError("Tool call output truncated due to max_tokens limit")
                    # BL-019: ツール呼び出しの前後でモデルが何を考えているか（なぜこのツールを呼ぶか、
                    # 前回の結果をどう解釈したか）をログに出す。reasoning_effort_levelが設定されて
                    # いるノードのみ非空になる（未設定ノードはgetattrがNone/空文字を返すだけで無害）。
                    reasoning_text = getattr(msg, "reasoning", None)
                    if reasoning_text:
                        print(f"💭 [{label}] 思考（iter={iteration}）:\n{reasoning_text}\n")
                    # BL-019追記: 「思考モデル」でなくとも、tool_calls付きの応答にcontentが
                    # 同梱されるモデル/プロバイダも存在しうる（実機確認では現行モデルは常にnull だが、
                    # モデル・プロバイダが変わった場合の取りこぼしを防ぐため無条件でチェックする）。
                    if msg.content and msg.content.strip() and getattr(msg, "tool_calls", None):
                        print(f"💬 [{label}] 発言（iter={iteration}, tool_calls同梱）:\n{msg.content}\n")
                    if not getattr(msg, "tool_calls", None):
                        print(f"✅ [{label}] ツールループ終了（iter={iteration}, tool_calls使用={tool_calls_used}回）")
                        if tool_calls_used == 0:
                            print(f"⚠️ [{label}] python_replを一度も使わずに応答しました（F-2.6監査対象）")
                        global _LAST_PYTHON_CALLS
                        _LAST_PYTHON_CALLS = python_calls_log
                        content = msg.content
                        return content if content is not None else "(APIから空の応答が返されました)"
                    loop_messages.append(msg.model_dump())
                    for tc in msg.tool_calls:
                        tool_calls_used += 1
                        handler = TOOL_DISPATCH.get(tc.function.name)
                        if handler is None:
                            result = f"[REPL Error] unknown tool: {tc.function.name}"
                            print(f"⚠️ [{label}] 未知のツール呼び出し（iter={iteration}）: {tc.function.name}")
                        else:
                            # [SAFETY] LLMが壊れた引数JSONを返した場合、例外を外に投げるのではなく
                            # ツール結果としてモデルに返し、MAX_TOOL_ITERの予算内で自己修復させる（D-009）。
                            try:
                                args = json.loads(tc.function.arguments)
                            except json.JSONDecodeError as e:
                                print(f"⚠️ [{label}] tool_call引数のJSONパース失敗（iter={iteration}）: {e}")
                                loop_messages.append({
                                    "role": "tool", "tool_call_id": tc.id,
                                    "content": json.dumps({"error": f"invalid arguments JSON: {e}"}, ensure_ascii=False),
                                })
                                continue
                            if tc.function.name == "python_repl":
                                result = repl_session.run(args.get("code", ""))
                                python_calls_log.append({"code": args.get("code", ""), "result": result})
                            else:
                                result = handler(args.get("code", ""))
                            print(f"🔧 [{label}] python_repl 実行（iter={iteration}）:\n{args.get('code','')}\n→ {result}\n")

                        loop_messages.append({
                            "role": "tool", "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })
                    # [CONSTRAINT] BL-025 ②: 全フェーズ・全DB agreementsを含む巨大なsystem_promptは、
                    # 初回（全体計画の把握）にのみ必要と考え、iter=1完了後（iter=2以降の自問自答フェーズ）は
                    # 現在タスクの情報のみに絞った軽量版に差し替える。他タスクの詳細が常に視界に入り続けることで
                    # Expertが他タスクのowns_variables領域まで踏み込んでしまう構造的誘因を減らす狙い（実機
                    # ドライランで観測、log/2026-07-20/1204）。Record/Replayのハッシュ計算（呼び出し時点の
                    # 引数`messages`）より後段での差し替えのため、フィクスチャキーには影響しない。
                    if light_system_prompt is not None and iteration == 1 and loop_messages[0].get("role") == "system":
                        loop_messages[0] = {
                            "role": "system",
                            "content": f"{light_system_prompt}\n\n{_JAPANESE_OUTPUT_DIRECTIVE}",
                        }
                    # [CONSTRAINT] BL-016: モデルは自分が残りあと何回ツールを呼べるか知らないため、
                    # 検算を続けられる余地が残っていると誤認したままMAX_TOOL_ITERを使い切り、
                    # テキスト最終回答を一度も返せずに非収束クラッシュする事例が実機ドライランで確認された
                    # （組合せ最適化的なタスクでiter=9に妥当な結論が出ていたのにiter=10で無駄な再検算をした事例）。
                    # 残り回数が僅少になった時点で明示的に知らせ、次の応答で打ち切るよう促す。
                    remaining_iters = MAX_TOOL_ITER - iteration
                    if 0 < remaining_iters <= 2:
                        loop_messages.append({
                            "role": "user",
                            "content": (
                                f"[SYSTEM NOTICE] ツール呼び出しの残り回数はあと{remaining_iters}回です。"
                                f"検算がすでに完了しているなら、次の応答はツールを呼ばずテキストで最終回答を出力してください。"
                                f"まだ検算が必要な場合も、残り{remaining_iters}回以内に収まるよう要点を絞ってください。"
                            ),
                        })
                    create_kwargs["messages"] = loop_messages
                # [CONSTRAINT] 非収束は一時的なAPI障害ではなく設計上の異常事態。下記exceptをAPIError系に
                # 絞ることで、このRuntimeErrorは握りつぶされずログに原因が一目でわかる形で伝播する（D-009）。
                print(f"❌ [{label}] ツールループが{MAX_TOOL_ITER}回を超えて非収束（tool_calls使用={tool_calls_used}回）")
                raise RuntimeError(f"ツール呼び出しが{MAX_TOOL_ITER}回を超えて収束しませんでした")
            finally:
                repl_session.close()
        # [CONSTRAINT] BL-022: OpenRouter経由の一部プロバイダが途中で切れた/壊れたレスポンスボディを
        # 返すことがあり、openai SDK内部の response.json()（httpx）がその場で生の
        # json.JSONDecodeError を送出する。これはD-009の意図（一時的なAPI障害はリトライ、
        # ロジックエラーは即座に伝播）に照らせば明確に前者だが、絞り込んだ例外タプルに
        # 含まれておらず素通りしていた（実機ドライランで確認）。tc.function.argumentsの
        # パース失敗は既にローカルなtry/exceptで個別処理済み（L711-719）のため、ここに
        # json.JSONDecodeErrorを加えても他のロジックエラーを誤って握りつぶす心配はない。
        except (APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError) as e:

            if attempt < len(delays):
                time.sleep(delays[attempt])
            else:
                print(f"\n[API Error] サーバーが高負荷のため応答できませんでした。: {e}")
                return "(サーバー高負荷によるAPIエラー)"


def _safe_json_parse(raw: str | None, fallback: dict | list) -> dict | list:
    """【SLM要約】
    Robust parsing of potentially malformed JSON strings, aggressively cleaning and attempting multiple decoding passes before falling back to a predefined structure.
    """
    if not raw or not isinstance(raw, str):
        return fallback
    # 段階1: マークダウンコードブロック除去
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        idx = cleaned.find("```")
        if idx != -1:
            cleaned = cleaned[:idx].strip()
    # 段階2: 先頭が `{` や `[` でない場合、最初の { または [ を探す
    if cleaned and cleaned[0] not in ("{", "["):
        brace_idx = cleaned.find("{")
        bracket_idx = cleaned.find("[")
        start = brace_idx if brace_idx != -1 else bracket_idx
        if start != -1:
            cleaned = cleaned[start:]
    # 段階3: 余計な後続テキストを除去（最後の } または ] 以降をカット）
    if cleaned:
        last_brace = cleaned.rfind("}")
        last_bracket = cleaned.rfind("]")
        end = max(last_brace, last_bracket)
        if end != -1:
            cleaned = cleaned[:end+1]
    try:
        parsed = json.loads(cleaned)
        if isinstance(fallback, list) and isinstance(parsed, list):
            return parsed
        elif isinstance(fallback, dict) and isinstance(parsed, dict):
            return parsed
        return fallback
    except json.JSONDecodeError:
        # 段階4: 最終手段として再度除去してからパース試行
        try:
            # 制御文字を除去して再試行
            import re as _re
            cleaned2 = _re.sub(r'[\x00-\x1f\x7f]', '', cleaned)
            parsed = json.loads(cleaned2)
            if isinstance(fallback, list) and isinstance(parsed, list):
                return parsed
            elif isinstance(fallback, dict) and isinstance(parsed, dict):
                return parsed
        except (json.JSONDecodeError, Exception):
            pass
        return fallback


def _query_and_parse_with_retry(
    prompt: str, client: OpenAI, model: str, label: str,
    tools: list[dict] | None, fallback: dict, max_retries: int = 2,
) -> tuple[dict, bool]:
    """【SLM要約】
    D-005: ツール付与によりuse_json_mode=Falseとなるノード向けの層2リトライ。
    _safe_json_parseがfallback（同一オブジェクト）をそのまま返した場合をパース失敗とみなし、
    ノード呼び出し自体を再試行する（既存のAPI呼び出し失敗リトライ＝層1とは独立）。
    戻り値: (parsed_or_fallback, parse_failed)。parse_failed=Trueは上限を使い切ったことを示す
    （呼び出し元でフェイルクローズ処理を行うこと）。
    """
    for attempt in range(max_retries + 1):
        res = query_AI([{"role": "user", "content": prompt}], client=client, model=model, label=label, tools=tools)
        parsed = _safe_json_parse(res, fallback=fallback)
        if parsed is not fallback:
            return parsed, False
        if attempt < max_retries:
            print(f"⚠️ [{label}] JSON判定パース失敗を検知。層2リトライ {attempt + 1}/{max_retries}...")
    return fallback, True

# ---------------------------------------------------------------------------
# 0. SQLite永続化層（R1、設計書§2・§3.6、impl_Plan §2〜§5準拠）
# ---------------------------------------------------------------------------

_DB_CONN: sqlite3.Connection | None = None  # module-levelシングルトン。stateには持たせない（シリアライズ不可のため）


def get_db_connection(db_path: str = "cela.db") -> sqlite3.Connection:
    """【SLM要約】
    WALモード・自動コミット（isolation_level=None）でSQLite接続を確立する（F-13準拠）。
    """
    conn = sqlite3.connect(db_path, timeout=60.0, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.row_factory = sqlite3.Row
    return conn


def get_active_conn() -> sqlite3.Connection:
    """【SLM要約】
    各ノード内からmodule-levelシングルトン接続を取得する。stateを経由しないためシリアライズ問題が生じない。
    """
    if _DB_CONN is None:
        raise RuntimeError("DB connection is not initialized.")
    return _DB_CONN


def init_db(conn: sqlite3.Connection) -> None:
    """【SLM要約】
    R1で定義する全テーブルを、存在しない場合にのみ生成する。
    """
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS decisions (
        id TEXT, timestamp REAL, who TEXT, what TEXT, why TEXT,
        reason_missing INTEGER DEFAULT 0, internal_thought_process TEXT,
        run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_decisions_run ON decisions(run_id);

    CREATE TABLE IF NOT EXISTS agreements (
        id TEXT, turn INTEGER, action_type TEXT, status TEXT, topic TEXT,
        decision_what TEXT DEFAULT '', reason_why TEXT DEFAULT '',
        proposed_by TEXT, entry_type TEXT, phase_id TEXT,
        abstraction_level TEXT, scope TEXT, time_axis TEXT,
        depends_on TEXT, resource_claims TEXT, timestamp REAL,
        evidence TEXT, is_frozen INTEGER DEFAULT 0, internal_thought_process TEXT,
        run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_agreements_run_topic ON agreements(run_id, topic);
    CREATE INDEX IF NOT EXISTS idx_agreements_run_status ON agreements(run_id, status);

    CREATE TABLE IF NOT EXISTS whiteboard_drafts (
        draft_id TEXT, phase_id TEXT NOT NULL, task_id TEXT NOT NULL, version INTEGER,
        content TEXT, author_role TEXT, edit_summary TEXT, timestamp REAL, run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_wb_run ON whiteboard_drafts(run_id, phase_id, task_id);

    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT, turn INTEGER, role TEXT, content TEXT, timestamp REAL, run_id TEXT NOT NULL
    );

    CREATE TABLE IF NOT EXISTS current_goal (
        goal_id TEXT PRIMARY KEY, core_philosophy TEXT NOT NULL, absolute_constraints TEXT, updated_at REAL
    );

    CREATE TABLE IF NOT EXISTS verified_facts (
        variable_name TEXT NOT NULL, value TEXT NOT NULL, unit TEXT DEFAULT '',
        source_task_id TEXT, source_phase_id TEXT, confirmed_by TEXT, confirmed_at REAL,
        run_id TEXT NOT NULL,
        PRIMARY KEY (run_id, variable_name)
    );
    """)
    _ensure_agreements_task_id_column(conn)


def _ensure_agreements_task_id_column(conn: sqlite3.Connection) -> None:
    """[CONSTRAINT] BL-023/BL-024: SQLiteはADD COLUMN IF NOT EXISTSを持たないため、
    既存DB（cela.db）との後方互換のため存在確認してから追加する。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    if "task_id" not in cols:
        conn.execute("ALTER TABLE agreements ADD COLUMN task_id TEXT DEFAULT ''")
        conn.commit()


def db_append_decision(d: dict, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    Decisionレコードをdecisionsテーブルへ即時コミットする（state["decisions"].appendの置換先）。
    """
    conn.execute(
        "INSERT INTO decisions (id, timestamp, who, what, why, reason_missing, internal_thought_process, run_id) "
        "VALUES (?,?,?,?,?,?,?,?)",
        (d.get("id"), d.get("timestamp"), d.get("who"), d.get("what"), d.get("why"),
         1 if d.get("reason_missing") else 0, d.get("internal_thought_process"), run_id)
    )


def db_append_agreement(a: dict, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    Agreementレコードをagreementsテーブルへ即時コミットする（state["agreements"].appendの置換先）。
    BL-001によりAgreementは decision_what/reason_why をネイティブに保持するため、エイリアス変換は行わない。
    """
    depends_on_val = json.dumps(a.get("depends_on", []), ensure_ascii=False) if isinstance(a.get("depends_on"), (list, dict)) else (a.get("depends_on") or "[]")
    resource_claims_val = json.dumps(a.get("resource_claims", {}), ensure_ascii=False) if isinstance(a.get("resource_claims"), (list, dict)) else (a.get("resource_claims") or "{}")
    conn.execute(
        "INSERT INTO agreements (id, turn, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, abstraction_level, scope, time_axis, depends_on, resource_claims, timestamp, "
        "evidence, is_frozen, internal_thought_process, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (a.get("id"), a.get("turn"), a.get("action_type"), a.get("status"), a.get("topic"),
         a.get("decision_what", ""), a.get("reason_why", ""), a.get("proposed_by"), a.get("entry_type"),
         a.get("phase_id"), a.get("task_id", ""), a.get("abstraction_level"), a.get("scope"), a.get("time_axis"),
         depends_on_val, resource_claims_val, a.get("timestamp"), None, 0, None, run_id)
    )


def db_supersede_agreement(agreement_id: str, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    既存agreementレコードを、リスト内ミューテーションではなくUPDATE差分でstatus='Superseded'へ遷移させる。
    """
    conn.execute(
        "UPDATE agreements SET status='Superseded' WHERE id=? AND run_id=?",
        (agreement_id, run_id)
    )


def get_agreements_from_db(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """【SLM要約】
    指定run_idのagreementsをid昇順（登録順序保証）で全件取得する。
    BL-001によりcontent/rationaleエイリアスは付与しない（decision_what/reason_whyをそのまま返す）。
    """
    rows = conn.execute("SELECT * FROM agreements WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def get_decisions_from_db(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """【SLM要約】
    指定run_idのdecisionsをid昇順（登録順序保証）で全件取得する。
    """
    rows = conn.execute("SELECT * FROM decisions WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    return [dict(r) for r in rows]


def upsert_verified_fact(conn: sqlite3.Connection, run_id: str, variable_name: str, value,
                          unit: str, source_task_id: str, source_phase_id: str, confirmed_by: str) -> None:
    """[CONSTRAINT] BL-023 2.6節: owns_variablesで宣言された共有変数の確定値を保存する。
    下流タスクはこの値を再導出せず、確定済みの定数として参照する前提。
    """
    conn.execute(
        "INSERT INTO verified_facts (run_id, variable_name, value, unit, source_task_id, "
        "source_phase_id, confirmed_by, confirmed_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, variable_name) DO UPDATE SET value=excluded.value, "
        "unit=excluded.unit, source_task_id=excluded.source_task_id, "
        "source_phase_id=excluded.source_phase_id, confirmed_by=excluded.confirmed_by, "
        "confirmed_at=excluded.confirmed_at",
        (run_id, variable_name, str(value), unit, source_task_id, source_phase_id,
         confirmed_by, time.time())
    )


def get_verified_facts_from_db(conn: sqlite3.Connection, run_id: str, variable_names: list[str]) -> list[dict]:
    """【SLM要約】
    指定されたvariable_names（通常は現在タスクのdepends_on先タスクのowns_variables）に限定して
    確定値を取得する。無関係な変数を注入しないための絞り込み。
    """
    if not variable_names:
        return []
    placeholders = ",".join("?" for _ in variable_names)
    rows = conn.execute(
        f"SELECT * FROM verified_facts WHERE run_id=? AND variable_name IN ({placeholders})",
        (run_id, *variable_names)
    ).fetchall()
    return [dict(r) for r in rows]

# ---------------------------------------------------------------------------
# 1. 状態定義
# ---------------------------------------------------------------------------

class Decision(TypedDict):
    id: str
    timestamp: float
    who: str
    what: str
    why: str
    reason_missing: bool

class Task(TypedDict):
    """[CONSTRAINT] BL-023: acceptance_criteriaは最大3個。超える場合はtask_planner側でタスクを分割する。"""
    task_id: str
    title: str
    description: str
    acceptance_criteria: list[str]   # 独立検証可能な主張を列挙（最大3個）
    depends_on: list[str]            # 前提として使う他タスクのtask_id
    owns_variables: list[str]        # このタスクで初めて確定させる共有変数名
    status: str                      # "pending" / "in_progress" / "completed" / "deferred"

class Phase(TypedDict):
    phase_id: str
    title: str
    description: str
    allowed_abstraction_levels: list[str]  # このフェーズで扱う視座の範囲
    focus_scope: str                        # このフェーズのスコープ
    expected_time_axis: str                 # このフェーズで主に扱う時間軸
    tasks: list[Task]                       # BL-018/BL-023: 従来は無型のdictキーとしてのみ存在
    budget_hint: dict[str, float]            # BL-023 Phase C: 仮説であり絶対制約ではないサブ予算枠

class Agreement(TypedDict):
    id: str
    turn: int
    action_type: str
    status: str
    topic: str
    decision_what: str
    reason_why: str
    proposed_by: str
    resource_claims: dict[str, float]  # 追加: {"初期導入予算": 75000000}
    
     # ─── 3次元の位置情報 ───────────────────────────────
    abstraction_level: str   # 軸1：視座（抽象度）
                             # "concept"    概念・目的・存在意義レベル
                             # "constraint" GlobalConstraint・方針・設計原則レベル  ← ご指摘の「最初の成果物」
                             # "design"     詳細設計・仕様レベル
                             # "impl"       実装・実験・PoC・検証レベル

    scope: str               # 軸2：スコープ（影響範囲）
                             # "global"     全フェーズに影響
                             # "phase"      特定フェーズ内
                             # "local"      特定タスク・決定内のみ

    time_axis: str           # 軸3：時間軸（いつの話か）
                             # "assumption" 現時点の前提・仮定（未検証）
                             # "current"    現在の確定事項
                             # "risk"       将来判明しうる致命的制約の候補
                             # "validated"  PoC・検証によって裏付けられた事実
    # ────────────────────────────────────────────────

    depends_on: list[str]   #"Decision"（合意・結論） / "Directive"（指示・タスク発行） / "Deliverable"（成果物本体）
    entry_type: str
    phase_id: str
    task_id: str   # BL-023/BL-024: どのタスクに紐づく合意・成果物・先送りか
    # statusに"Deferred"を追加（既存: Proposed/Approved/Approved_with_Conditions/Rejected/Implicitly_Accepted）
    # "Deferred"の場合、topicは先送りされた論点名、reason_whyに「どのタスクで扱うか」を含める

class RiskRegister(TypedDict):
    """3次元構造とは独立した、致命的リスクの専用台帳"""
    risk_id: str
    description: str                    # "冬季の積雪で待ち時間が30分を超える可能性"
    related_constraint: str             # どのGlobalConstraintに影響するか
    related_phase: str                  # どのフェーズで検証すべきか
    severity: str                       # "fatal"（これが未検証のまま後フェーズに進むとPoC倒れになる）
                                        # "major" / "minor"
    detection_phase: str                # 実際にこのリスクが判明したフェーズ
    resolution_status: str              # "unvalidated" → "in_progress" → "resolved" / "accepted"

class GlobalConstraint(TypedDict):
    name: str              # "初期導入予算" 等
    total_cap: float        # 1億円
    unit: str               # "円"
    claims: dict[str, float]  # {"phase_1": 75000000, "phase_2": 0, ...} 各フェーズの現在の取り分


class LineageState(TypedDict):
    goal: Annotated[str, _take_latest]
    user_input: str
    current_task_summary: str
    selected_expert: str
    expert_output: str
    run_id: str
    db_path: str
    chat_history: list[dict]
    turn_count: int
    max_turns: int
    reflection_interval: int
    risk_flag: str
    drift_flag: bool
    halt: bool
    agent_has_guardrail: bool
    discussion_status: Literal["continuing", "completed", "stagnant"]
    is_stateless_mode: bool
    
    facilitation_count: int
    review_count: int
    is_completed: bool
    ready_for_review: bool # 追加: 議論が完了し、QA審査待ちの状態
    medium_risk_streak: int   # 追加
    constraint_issue: str              # 直近detectorの判定 (none/minor/major)
    constraint_issue_log: list[dict]   # major/minor を蓄積するログ
    # --- 以下を追加 ---
    global_constraints: list[GlobalConstraint]
    phases: list[Phase]
    current_phase: Phase
    current_task_id: str                          # BL-024: decision_extractor_nodeのみが書き込む
    verified_facts: dict[str, dict]                # BL-023: {"vehicle_count": {"value": ..., "unit": ..., "source_task_id": ..., "confirmed_at": ...}}
    task_criteria_status: dict[str, list[bool]]    # BL-023: {"task_1_2": [True, False]}（acceptance_criteriaのインデックス対応）
    risk_register: list[RiskRegister]
    needs_revision_phases: list[str]
    phases_to_revise: list[str]
    user_retry_count: int
    expert_retry_count: int
    expert_last_python_calls: list[dict]  # BL-033: 直前Expert呼び出しのpython_repl実行記録（code/result）

class Appconfig(TypedDict): 
    pattern: int
    is_stateless_mode: bool
    initial_max_turnval: int
    reflection_interval: int
    target_goal: str
    user_always_remember: bool
    agent_has_guardrail: bool
    chat_histry_window: int
    expert_history_window: int
 

  
    

# ---------------------------------------------------------------------------
# 2. モデル呼び出し関数
# ---------------------------------------------------------------------------

#EXPERT_CONTEXT_WINDOW = 10  
#chat_history_window = 4    

def _build_hydrate_context(decisions: list[Decision], config: Appconfig) -> str:
    """【SLM要約】
    Construction of the decision context string by formatting and summarizing recent past decisions for presentation.
    """
    if not decisions:
        return "(まだ過去の判断ログはありません。)"
    recent = decisions[-config["expert_history_window"]:]
    lines = []
    for d in recent:
        why_short = (d["why"][:100] + "…") if len(d["why"]) > 100 else d["why"]
        lines.append(f"- [{d['who']}] {d['what']}（理由: {why_short}）")
    return "\n".join(lines)

def _build_agreements_context(agreements: list[Agreement]) -> str:
    """【SLM要約】
    Formatting of relevant agreements (Decisions/Deliverables) into a readable, contextual string for LLM consumption.
Filters out superseded or directive items and applies status-based formatting/labeling.
    """
    decisions_and_deliverables = [
        a for a in agreements
        if a.get("entry_type", "Decision") in ("Decision", "Deliverable") 
        and a.get("status") != "Superseded"
        # Directive（指示）はDB画面から除外。完了後の無限ループ防止
        and a.get("entry_type") != "Directive"
    ]
    
    if not decisions_and_deliverables:
        return "(まだ合意・決定・提案された事項はありません)"
        
    lines = []
    for a in decisions_and_deliverables:
        status = a.get("status", "Proposed")
        entry_type = a.get("entry_type", "Decision")
        
        # LLMが勝手に topic の先頭に "[合意]" や "[決定]" を付けて抽出するのを防ぐ
        raw_topic = a.get('topic', 'Unknown Topic')
        clean_topic = re.sub(r'^\[.*?\]\s*', '', raw_topic)
        
        # 1. アイコンの判定（成果物は専用アイコンを使用）
        if entry_type == "Deliverable":
            icon = "📄" if status == "Proposed" else "✅"
        elif status == "Approved":
            icon = "✅"
        elif status == "Proposed":
            icon = "🤔"
        else:
            icon = "⚠️"
            
        # 2. ラベル（テキスト）の動的判定
        if entry_type == "Deliverable":
            type_label = "[成果物]"
        else:
            # ここでステータスに応じた正しいラベルを振る
            if status == "Approved":
                type_label = "[確定合意]"
            elif status == "Proposed":
                type_label = "[提案/検討中]"  # ← 検討中の場合は必ずこれになる
            elif status == "Rejected":
                type_label = "[却下事項]"
            elif status == "Approved_with_Conditions":
                type_label = "[条件付合意]"
            else:
                type_label = f"[{status}]"
                
        # decision_whatがファイルパスの場合はその旨を表示する
        content_preview = a.get('decision_what', '')
        if content_preview.startswith("FILE_PATH:"):
            file_path = content_preview.split("FILE_PATH:")[1]
            content_preview = f"(ファイルに出力済み: {file_path})"
        else:
            content_preview = content_preview[:150]
                
        lines.append(f"{icon}{type_label} {clean_topic}: {content_preview}")

    return "\n".join(lines)


def _build_hydrate_context_from_db(conn: sqlite3.Connection, run_id: str, config: Appconfig) -> str:
    """【SLM要約】
    SQLiteからdecisionsを取得し、旧list版と同一のロジックでコンテキスト文字列化する（impl_Plan §5.2準拠）。
    """
    return _build_hydrate_context(get_decisions_from_db(conn, run_id), config)


def _build_agreements_context_from_db(conn: sqlite3.Connection, run_id: str) -> str:
    """【SLM要約】
    SQLiteからagreementsを取得し、旧list版と同一のロジック（Rejectedも却下事項として含める既存挙動維持）でコンテキスト文字列化する。
    """
    return _build_agreements_context(get_agreements_from_db(conn, run_id))


def _get_current_task(state: LineageState) -> dict:
    """[CONSTRAINT] BL-023: current_task_id（BL-024でdecision_extractor_nodeのみが書き込む）から
    現在のTaskを検索する。未設定（初回ターン等）の場合はcurrent_phaseの先頭タスクにフォールバックする。
    """
    current_phase = state.get("current_phase", {})
    tasks = current_phase.get("tasks", [])
    current_task_id = state.get("current_task_id", "")
    for t in tasks:
        if t.get("task_id") == current_task_id:
            return t
    return tasks[0] if tasks else {}


def _build_task_scope_context(state: LineageState, conn: sqlite3.Connection) -> dict:
    """[CONSTRAINT] BL-023/BL-025: 現在タスクのスコープ情報（acceptance_criteria・依存タスクの確定値・
    未充足項目）を`generate_user_utterance`と`call_expert`の両方で共有するためのヘルパー。
    """
    current_task = _get_current_task(state)
    current_task_json = json.dumps(current_task, ensure_ascii=False, indent=2) if current_task else "(タスク未確定)"

    depends_on_task_ids = current_task.get("depends_on", [])
    dependency_variable_names: list[str] = []
    for t in state.get("current_phase", {}).get("tasks", []):
        if t.get("task_id") in depends_on_task_ids:
            dependency_variable_names.extend(t.get("owns_variables", []))
    verified_facts_rows = get_verified_facts_from_db(conn, state["run_id"], dependency_variable_names) if dependency_variable_names else []
    verified_facts_json = json.dumps(verified_facts_rows, ensure_ascii=False, indent=2) if verified_facts_rows else "(依存タスクの確定値はまだありません)"

    acceptance_criteria = current_task.get("acceptance_criteria", [])
    criteria_status = state.get("task_criteria_status", {}).get(current_task.get("task_id", ""), [])
    remaining_criteria = [
        c for i, c in enumerate(acceptance_criteria)
        if not (i < len(criteria_status) and criteria_status[i])
    ]
    remaining_criteria_text = "\n".join(f"- {c}" for c in remaining_criteria) or "(未充足の項目はありません、または未判定です)"

    return {
        "current_task": current_task,
        "current_task_json": current_task_json,
        "verified_facts_json": verified_facts_json,
        "remaining_criteria_text": remaining_criteria_text,
    }


def call_task_planner(goal: str) -> list[dict]:
    """【SLM要約】
    Decomposition of a high-level goal into structured, actionable phases and detailed tasks by querying an AI planner.
It serves as the initial planning layer for breaking down complex objectives across the system.
    """
    
    prompt = f"""
    以下の絶対目標を、独立して議論・検証可能な「フェーズ」に分解し、
    さらに各フェーズを実行可能な「タスク」に分解してください。

    【重要】
    1. 各フェーズには必ず以下の3次元属性を定義してください。
       - allowed_abstraction_levels: "concept" / "constraint" / "design" / "impl" の中から配列で指定。
       - focus_scope: "global" / "phase" / "local" のいずれか。
       - expected_time_axis: "assumption" / "current" / "risk" / "validated" のいずれか。
    2. 各フェーズには、具体的な作業ステップを示す `tasks` 配列を必ず含めてください。
    3. 【BL-023】各タスクには以下も必ず含めてください:
       - acceptance_criteria: このタスクで検証されるべき独立した主張を配列で列挙してください。
         **最大3個まで**とし、3個を超える場合はタスク自体を分割してください
         （例: 「車両台数の算出」「初期費用の内訳」「年間ランニングコストの内訳」「感度分析」を
         1タスクに束ねてはいけません。それぞれ独立したタスクにするか、密接に関連する場合でも
         acceptance_criteriaの数を3以内に抑える粒度まで分割してください）。
       - depends_on: このタスクが前提として使う他タスクのtask_idを配列で指定してください
         （前提がなければ空配列）。
       - owns_variables: このタスクで初めて確定させる共有変数名を配列で指定してください
         （例: "vehicle_count"）。同じ変数を必要とする他タスクは、depends_onでこのタスクを
         指定し、値を再導出せず参照する前提とします（前提がなければ空配列）。

    ■ 絶対目標: {goal}

    Return ONLY JSON array (必ず複数のフェーズとタスクに分割すること):
    [
        {{
            "phase_id": "phase_1",
            "title": "フェーズ1のタイトル",
            "description": "フェーズ1の詳細な説明...",
            "allowed_abstraction_levels": ["concept", "constraint"],
            "focus_scope": "global",
            "expected_time_axis": "assumption",
            "tasks": [
                {{
                    "task_id": "task_1_1",
                    "title": "タスク1-1のタイトル",
                    "description": "具体的な作業内容...",
                    "acceptance_criteria": ["独立検証可能な主張1", "独立検証可能な主張2"],
                    "depends_on": [],
                    "owns_variables": []
                }},
                {{
                    "task_id": "task_1_2",
                    "title": "タスク1-2のタイトル",
                    "description": "具体的な作業内容...",
                    "acceptance_criteria": ["独立検証可能な主張1"],
                    "depends_on": ["task_1_1"],
                    "owns_variables": []
                }}
            ]
        }},
        {{
            "phase_id": "phase_2",
            "title": "フェーズ2のタイトル",
            "description": "フェーズ2の詳細な説明...",
            "allowed_abstraction_levels": ["design", "impl"],
            "focus_scope": "phase",
            "expected_time_axis": "current",
            "tasks": [
                // ... (フェーズ2に必要なタスクを複数列挙、各タスクにacceptance_criteria/depends_on/owns_variablesを含める)
            ]
        }}
        // ... (目標達成に必要な数だけフェーズを続けること)
    ]
    """
    res = query_AI([{"role": "user", "content": prompt}],
                   client=client_auditor, model=model_auditor,
                   label="Task Planner")

    fallback_phase= [{
        "phase_id": "phase_1",
        "title": "全体",
        "description": goal,
        "allowed_abstraction_levels": ["concept", "constraint", "design", "impl"],
        "focus_scope": "global",
        "expected_time_axis": "current",
        "tasks": [
            {
                "task_id": "task_1_1",
                "title": "初期タスク",
                "description": "目標達成に向けた要件定義と最初の分析を行う",
                "acceptance_criteria": ["目標達成に向けた要件定義と最初の分析結果を提示する"],
                "depends_on": [],
                "owns_variables": []
            }
        ]
    }]

    return _safe_json_parse(res, fallback=fallback_phase)

def call_orchestrator(state: LineageState, config: Appconfig ) -> dict:
    """【SLM要約】
    Construction of a comprehensive prompt by aggregating system state (goals, agreements, history) and user input to direct an LLM in selecting the most appropriate domain expert for task execution.
    """
    goal_context = f"Goal: {state['goal']}\n" if config["agent_has_guardrail"] else "(自由にアシストしてください。)\n"

    recent_history = state["chat_history"][-config["chat_history_window"]:]
    recent_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])
    if not recent_text:
        recent_text = "(まだ履歴はありません)"
        
    _conn = get_active_conn()
    agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])
    print(f"【プロジェクトの合意・決定事項・検討状況DB】\n {agreements_text} \n\n")

    if config["is_stateless_mode"]:
        hydrate_context = _build_hydrate_context_from_db(_conn, state["run_id"], config)
        history_text = f"【過去のシステム判断ログ】\n {hydrate_context} \n\n【直近の対話文脈】\n{recent_text}"
    else:
        all_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in state["chat_history"]])
        history_text = f"【これまでの全対話文脈】\n{all_text}" if all_text else "(まだ履歴はありません)"

    prompt = (
        f"""
        {goal_context}\n
        \n
        Task(ユーザーAIの指示): {state["user_input"]}\n
        \n
        Taskを遂行するために最も適した専門家の肩書き（役職名）を、固定リストから選ぶのではなく、
        このタスクの内容に即して自由に生成してください。\n
        例: 「地域公共交通の需要予測専門家」「自動運転車両の安全基準アナリスト」のように、
        タスクの実態に即した具体的な肩書きにしてください（漠然とした「アシスタント」等は避ける）。\n
        \n
        【プロジェクトの合意・決定事項・検討状況DB】
        {agreements_text}\n
        \n
        {history_text}\n
        \n
        回答は簡潔で論理的にせよ\n
        \n
        Return ONLY JSON: {{"expert": "（生成した専門家の肩書き）", "reason": "..."}}'
        """
    )
    res = query_AI([{"role": "user", "content": prompt}], client=client_agent, model=model_agent, label="Orchestrator")
    parsed = _safe_json_parse(res, fallback={"expert": "", "reason": ""})

    # [CONSTRAINT] BL-018当時、専門家名を固定16種の配列に絞っていたが、call_expert/グラフのどちらも
    # 具体的な専門家名で分岐しておらず（プロンプトへの埋め込みラベルとして使われるのみ）、
    # 固定リストは無用な足かせだった（ログ上、リストのどれにも綺麗に当てはまらないタスクで
    # 選定に無駄な思考コストが生じていた）。専門家ごとの個別ノード構造が必要になった時点で
    # 再度制約を設ける方針とし、それまでは自由記述とする。空・空白のみの場合のみフォールバックする。
    expert = (parsed.get("expert") or "").strip()
    if not expert:
        expert = "プロジェクト全般アドバイザー"
    return {"expert": expert, "reason": parsed.get("reason", "")}


def call_expert(expert_name: str, state: LineageState, config: Appconfig) -> str:
    """【SLM要約】
    Assembling and injecting a highly detailed, state-aware system prompt to guide an expert AI agent's response based on current project status, constraints, and historical context.
    """

    agent_has_guardrail = config["agent_has_guardrail"]
    max_turns = config["initial_max_turnval"]
    turn_count = state["turn_count"]
    _conn = get_active_conn()
    agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])
    is_stateless_mode = config["is_stateless_mode"]
    user_input = state["user_input"]
    chat_history_window = config["chat_history_window"]
    phases_json = json.dumps(state.get("phases", []), ensure_ascii=False, indent=2)

    system_prompt = f"あなたは有能な{expert_name}の分野の専門家です。\n"
    
    if agent_has_guardrail:
        system_prompt += f"\n【あなたの絶対的な行動指針】\n👉 {state['goal']}\n"
    
    system_prompt += f"\n⏳ 【制限時間】: 全 {max_turns} ターン中、現在は **{turn_count} ターン目** です。\n"
    system_prompt += f"\n5ターン毎に議論のサマリーを出力せよ。数値などは消さず明示的に示すこと。\n"
    system_prompt += f"\n【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\n{agreements_text}\n\n"
    
    # 【追加】Agent AIの越権行為（勝手なDB更新）を禁止する
    system_prompt += (
        "⚠️ 【厳守事項】\n"
        "上記の【決定事項DB】はシステム側で自動管理されます。\n"
        "あなたの回答内に「決定事項DB」のブロックを自分で書いたり、勝手に「✅ 決定事項」と宣言したりしないでください。\n"
        "あなたはあくまでUserに『提案・報告』を行う立場です。\n"
    )

    if turn_count >= max_turns - 2:
        system_prompt += "🚨 【超重要・最終盤】これが最後の回答です。これまでの議論と『決定事項DB』の内容をすべて網羅し、集大成としての成果物を出力してください。\n"
    elif turn_count > max_turns * 0.5:
        system_prompt += "⚠️ 【議論の後半戦】新しい案の提示は控えてください。これまでの決定事項を具体化し、ドキュメント化にフォーカスしてください。\n"
    
    system_prompt += (f"""
       \n🔥 【エージェントとしての行動原則】\n
        あなたはプロフェッショナルとして、制約（予算・時間・性能・規模など）の壁に直面しても、\n
        安易に「制約の緩和」や「要件の放棄（一部機能の省略など）」を提案しないでください。\n
        制約が厳しい場合こそ、最新の技術動向、代替アプローチ、リソースの再配分、設計の見直しなど、\n
        抜本的でクリエイティブな「代替案」を絞り出し、絶対目標の枠内に収める努力を最後まで諦めないでください。\n
        目標達成に向け常に目標を意識し、目標からの論理的・倫理的・数値的(単純な計算誤りも含む）な"
        矛盾や逸脱がないかを意識して回答してください\n
        挨拶、感謝の言葉は不要です\n
        タスクやフェーズの完了を宣言するのはユーザーが行うものであり、あなたは勝手に完了宣言をしないでください。\n
        あなたはタスクの遂行、意見の提示・成果の提示等、意思決定の支援を行う立場であり、ユーザーの意思決定を代行する立場ではありません。\n
        口調は論理的でスマート紳士に徹してください。冗長な表現は避け、簡潔に論理的に回答してください。\n
    """)

    system_prompt += (
        "\n📝 【回答形式について】\n"
        "\n返答は正確かつ明確でなければならない\n"
        "JSON形式での回答は不要です。実務担当者として、根拠や懸念点、検討した代替案も含め、"
        "自然な文章で冗長な表現を避けつつ具体的かつ、論理的に詳細に回答してください。\n"

    )

    system_prompt += (
        "\n【F-2.6 機械的検算ゲート（必須）】\n"
        "数値的根拠を提示する際は python_repl ツールで計算を実行し、結果を明示すること。暗算での提示は禁止します。\n"
    )

    system_prompt += (f"""
    \n📊 [プロジェクト進行計画]
    目標達成への道しるべとして、Task Plannerが作成したフェーズとタスクの一覧を以下に示します。\n
    {phases_json}\n\n
    指示があったフェーズ、タスクに関しては、必ずこの計画を参照し、逸脱や矛盾がないよう思考してください\n
    \n
    """)

    # BL-025: Expertが他タスクのowns_variables領域まで踏み込むことを防ぐスコープガードレール
    _scope_ctx = _build_task_scope_context(state, _conn)
    current_task_json = _scope_ctx["current_task_json"]
    verified_facts_json = _scope_ctx["verified_facts_json"]
    remaining_criteria_text = _scope_ctx["remaining_criteria_text"]

    system_prompt += (f"""
    \n📏 【回答のスコープについて（厳守）】\n
    あなたの回答で扱ってよい内容は、以下の「現在のタスク」の acceptance_criteria の範囲に厳密に限定してください。\n
    他タスクが owns_variables として所有する値（例：他タスクで算出すべき数値）は、たとえ関連性が高く見えても\n
    新たに算出・提案しないでください。それは当該タスクの役目です。\n

    【現在のタスク】\n
    {current_task_json}\n

    【この値は確定済みです。再導出しないでください】\n
    {verified_facts_json}\n

    【未充足の要求項目（これ以外を新たに追加提案しないこと）】\n
    {remaining_criteria_text}\n
    """)

    # 履歴からは消えた「前回の自分のNG発言」をStateから復元して突きつける
    previous_output = state.get("expert_output", "(取得不可)")

    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        system_prompt += f"""
            \n⚠️ 【重要】\n
            あなたの前回の発言は、倫理違反、矛盾、リソース超過や制約違反などの重大な矛盾が検知されDetector（監査システム）により差し戻されました。\n
            ▼ 【却下されたあなたの前回の提案（※チャット履歴からは削除済）】\n
            {previous_output}\n\n
            [監査システムからの指摘事項]\n
            {state.get('constraint_issue_log', [])[-1:]} \n\n
            上記の「自身の過去の提案」と「指摘事項」を熟読し、論理的破綻や計算ミス、制約条件の無視を完全に修正した新しい提案を作成してください。\n
            必ず、矛盾の内容とその理由を明示し、どのタスク・フェーズに影響があるかを具体的に指摘してください。\n
        """

    system_prompt += (f"""
    \n文脈の参考として以下に直近の会話を示します
    [-----以下は直近の会話です-----]\n
    """)
           
    
    messages = []
    if is_stateless_mode:
        hydrate_context = _build_hydrate_context_from_db(_conn, state["run_id"], config)
        system_prompt += f"\n【過去の会話を圧縮したシステム判断ログ】\n{hydrate_context}\n"
        messages.append({"role": "system", "content": system_prompt})
        
        recent_history = state["chat_history"][-chat_history_window:]
        for msg in recent_history:
            messages.append(msg)
            
        #messages.append({"role": "user", "content": user_input})
    else:
        messages.append({"role": "system", "content": system_prompt})
        for msg in state["chat_history"]:
            messages.append(msg)
        #messages.append({"role": "user", "content": user_input})

    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        system_prompt += f"""
            \n⚠️ 【重要】\n
            あなたの前回の発言は、倫理違反、矛盾、リソース超過や制約違反などの重大な矛盾が検知されDetector（監査システム）により差し戻されました。\n"
            以下の指摘事項を踏まえ、発言内容を修正して再出力してください：\n"
            {state.get('constraint_issue_log', [])[-1:]} \n"
            必ず、矛盾の内容とその理由を明示し、どのタスク・フェーズに影響があるかを具体的に指摘してください。\n
        """


    # BL-025 ②: ツールループの自問自答フェーズ（iter=2以降）では、全フェーズ・全DB agreementsを含む
    # 巨大なsystem_promptではなく、現在タスクの情報のみに絞った軽量版に差し替える。
    light_system_prompt = (
        f"あなたは有能な{expert_name}の分野の専門家です。\n\n"
        f"【現在のタスク】\n{current_task_json}\n\n"
        f"【この値は確定済みです。再導出しないでください】\n{verified_facts_json}\n\n"
        f"【未充足の要求項目】\n{remaining_criteria_text}\n\n"
        "他タスクのowns_variablesに該当する内容は新たに算出・提案しないでください。\n"
        "数値的根拠は python_repl ツールで検算し、暗算での提示は禁止します。\n"
    )

    return query_AI(messages, client=client_agent, model=model_agent, label=f"Expert:{expert_name}",
                     tools=[PYTHON_REPL_TOOL], light_system_prompt=light_system_prompt)


#def call_detector(goal: str, user_input: str, expert_output: str, decisions: list[Decision], current_phase: dict) -> dict:
def call_detector(state: LineageState, target_role: str) -> dict:
    """【SLM要約】
    Determining the rigor of auditing criteria based on whether the input is a user instruction/review or an agent proposal, then using an LLM to assess both safety risks and constraint adherence in the conversation history.
    """
 
    recent_decitions = json.dumps(get_decisions_from_db(get_active_conn(), state["run_id"])[-2:], ensure_ascii=False)
    recent_history = state["chat_history"][-2:]
    history_text = "\n".join([f"{'[User]' if m['role']=='user' else '[AI]'}\n {m['content']}" for m in recent_history])
    goal = state["goal"]
    current_task = _get_current_task(state)
    acceptance_criteria = current_task.get("acceptance_criteria", [])
    criteria_text = "\n".join(f"{i}. {c}" for i, c in enumerate(acceptance_criteria)) or "(現在のタスクにacceptance_criteriaが定義されていません)"

    # BL-033: Expertが実際に実行したpython_replの記録をDetectorに提示する。
    # Expertの「検算完了」という自己申告（tool_calls=0でも書けてしまう）を鵜呑みにせず、
    # まずDetector自身が独立して検算し、その後この記録と突き合わせて整合性を確認させる狙い。
    expert_python_calls = state.get("expert_last_python_calls", [])
    if expert_python_calls:
        calls_text = "\n\n".join(
            f"--- 呼び出し{i+1} ---\nコード:\n{c['code']}\n結果:\n{c['result']}"
            for i, c in enumerate(expert_python_calls)
        )
        python_calls_block = (
            f"【BL-033: Expertが実際に実行したpython_replの記録】\n{calls_text}\n\n"
            f"まずあなた自身が独立してpython_replで検算してください。その上で、この記録のコードが"
            f"論理的に妥当か、結果が一致するかを確認してください。あなたの検算結果とこの記録が"
            f"食い違う場合はconstraint_issue=\"major\"としてください。\n"
        )
    else:
        python_calls_block = (
            f"【BL-033: 警告】今回のExpertはpython_replを一度も使用していません。\n"
            f"数値主張が含まれる場合、Expertが「検算完了」等と自己申告していても絶対に鵜呑みにせず、"
            f"必ずあなた自身がpython_replで独立して検算してください。\n"
        )

# 評価する対象（UserかExpertか）によって、チェック基準の厳しさを変える
    if target_role == "user":
        role_specific_instruction = (f"""
            評価対象：User(発注者)の発言】\n
            今回の発言は発注者からの『指示・指摘』または『提案へのレビュー・承認』です。\n
            以下の基準で厳格に監査してください：\n
            1. 【指示・指摘の場合】: User自身が成果物を作る立場ではないため、成果物の欠落や詳細な計算結果の未提示を理由にmajorにしてはいけません。\n
                ただし、指示内容自体に論理破綻がある場合や、絶対目標の放棄（安易な制約緩和の要求など）がある場合は major としてください。\n\n
            2. 【レビュー・承認の場合（最重要）】: UserがAgentの直前の提案に対して「妥当である」「承認する」「次のタスクへ進む」と合意の意思を示している場合、\n
                **その承認しようとしている提案内容に制約違反や論理破綻がないか**を必ず確認してください。\n
                Agentの提案に重大な不備（予算超過、要求事項の欠落、根拠のない計算など）があるにも関わらず、Userがそれを見落として安易に承認・合意している場合は、\n
                「発注者としてのレビュー不足（妥協）」とみなし、**容赦なく major を出力し、Userに対して『承認を取り消し、Agentに厳しく修正を要求せよ』と差し戻してください。**\n
        """)
    else:
        role_specific_instruction = (f"""
            【評価対象：Agent(作業者)の発言】\n
            今回の発言は作業者からの『提案・成果物』です。\n
            以下の場合は major としてください：\n
            - 検算の結果、明白な数値矛盾や計算ミスが確認された場合（検算必須、下記参照）。\n
            - 要求された成果物項目が欠落しているにもかかわらずそれに一切触れず、
              あたかも全項目に対応済みであるかのように「最終確定」「これで承認」等の
              言葉で議論を打ち切ろうとしている場合。\n
            一方、以下の場合はそれだけでは major にせず、minor としてください：\n
            - 一部の項目には応えているが、残りについて「〇〇は次タスクで扱う」
              「〇〇は別途詳細化する」等、何が未着手かを具体的に名指しした上で、
              次のステップとして明示している場合（複数ラウンドにわたり段階的に
              成果物を仕上げるのは正常なプロセスであり、1ターンで全指摘に
              完全に応えることまでは要求しない）。\n
            数値や数式は鵜吞みにせず、必ず根拠を追跡し、すべて検算してください。\n
            検算の結果数字、数式に疑義がある場合は major を出力してください。\n
        """)



    prompt = (
        f"あなたはプロジェクトにおける議論の厳格で優秀な監査人です。\n\n"
        f"以下の2軸は**完全に独立した別の評価軸**です。混同しないでください。\n\n"
        f"【軸1: risk（安全性・倫理のみ）】\n"
        f"- low: 通常の業務的な発言。\n"
        f"- medium: 軽微な懸念はあるが危険ではない。\n"
        f"- high: 実在の違法行為の助長、重大な安全上の危険、悪意のある内容など、議論を即座に停止すべき"
        f"明白な危険性がある場合のみ。**予算超過や計算ミスは、それ単体ではhighにしないこと。**\n\n"
        f"【軸2: constraint_issue（制約条件との数値的・論理的な矛盾）】\n"
        f"- none: 矛盾なし。\n"
        f"- minor: 議論の途中段階として許容範囲の試算・未完成な提案"
        f"（例：初期の叩き台が制約条件を満たしていない等）。"
        f"これは議論を通じて改善されることが想定されるため、致命的な問題ではない。\n"
        f"- major: 検算により明白な数値矛盾や計算ミスが確認された場合。または、"
        f"要求された成果物項目が欠落しているにもかかわらずそれに触れず、"
        f"あたかも全項目対応済みであるかのように「最終確定」等の言葉で議論を打ち切ろうとしている場合。\n"
        f"ユーザーAIの提案が不足や矛盾があるにも関わらずユーザーAIがエージェントAIの提案に安易に、同意し承認してしまっている場合\n"
        f"- 未対応項目が残っていても、何が未着手かを具体的に名指しした上で「次タスクで扱う」等、"
        f"明示的な申し送りとして次に進めている場合は、それだけでは major にしない（minor とする）。\n\n"
        f"**重要: constraint_issueがmajorであっても、riskをhighにしてはいけません。riskは安全性専用です。**\n\n"

        f"{role_specific_instruction}\n\n" # ★ここで切り替える

        f"**追加の重要指示: 上限値（例:「上限1億円」「上限3,000万円」）を超えていない場合、"
        f"あるいは上限値に近い値であっても、それは矛盾とは見なさないでください。"
        f"「上限内の数値差」や「予算の上下関係」を正確に計算し、上限を超えていない場合はnoneまたはminorと判定してください。\n\n"
        f"数値や数式は鵜吞みにせず、必ず根拠を追跡し、すべて検算してください。検算の結果数字、数式に疑義がある場合はmajorを出力してください\n"
        f"【F-2.6 機械的検算ゲート（必須）】数値主張（合計・比率・閾値比較等）を含む場合、"
        f"必ず python_repl ツールで機械的に再計算し、一致を確認してからでなければ constraint_issue=\"major\" としないでください。"
        f"暗算での承認・却下判定は禁止します。\n\n"
        f"{python_calls_block}\n"
        f"System Goal: {goal}\n"
        f"Recent Decisions（参考程度）: {recent_decitions}\n\n"
        f"【BL-023: 現在タスクのacceptance_criteria充足チェック】\n"
        f"以下は現在のタスクで検証されるべき独立した主張の一覧です（インデックス0始まり）。\n"
        f"{criteria_text}\n"
        f"今回のAgentの発言が、それぞれの項目に応えている（充足している）かをbool配列で判定してください。\n"
        f"配列の長さ・順序は上記の一覧と対応させてください。\n\n"
        f"【今回評価するターンのやり取り】\n"
        f"{history_text}\n"
        #f"User Input: {user_input}\n"
        #f"AI Output: {expert_output}\n\n"

        #f"■ 現在のフェーズ: {state["current_phase"]['title']}\n"
        #f"■このフェーズで扱うべき視座: {state["current_phase"].get('allowed_abstraction_levels', ['concept', 'constraint', 'design', 'impl'])}\n"
        #f"■ 視座の逸脱チェック:\n"
        #f"- 上記の視座を超えた詳細（例: 概念フェーズなのに実装の話）が出た場合は drift=True\n"
        #f"- 上記の視座より抽象的な話（例: 設計フェーズなのに目的論を繰り返す）が出た場合も drift=True\n"
        f'Return ONLY JSON: {{"risk": "low/medium/high", "constraint_issue": "none/minor/major", "comment": "判定理由", "criteria_status": [true/false, ...]}}'
    )
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_auditor, model=model_auditor, label="Detector",
        tools=[PYTHON_REPL_TOOL], fallback={"risk": "low", "constraint_issue": "none", "comment": "", "criteria_status": []},
    )
    if parse_failed:
        # [SAFETY] D-005: 層2リトライを使い切った場合はフェイルオープン（none）ではなくフェイルクローズ（major）に倒す。
        # F-2.6検算ゲート導入の目的（暗算を信用しない）と、判定データ欠落時のフェイルオープンは相容れないため。
        print("🚨 [Detector] 層2リトライを使い切ってもJSON判定を取得できませんでした。フェイルクローズ(major)します。")
        return {"risk": "low", "constraint_issue": "major", "comment": "(判定JSON解析失敗のためフェイルクローズしました)", "criteria_status": []}
    print(f"【Detectorの判定結果(JSONパース後)】\n{parsed}\n")
    risk = parsed.get("risk", "low")
    if risk not in ("low", "medium", "high"):
        risk = "low"
    constraint_issue = parsed.get("constraint_issue", "none")
    if constraint_issue not in ("none", "minor", "major"):
        constraint_issue = "none"
    criteria_status = parsed.get("criteria_status", [])
    if not isinstance(criteria_status, list):
        criteria_status = []

    return {"risk": risk, "constraint_issue": constraint_issue, "comment": parsed.get("comment", ""), "criteria_status": criteria_status}

def call_decision_extractor(chat_history: list[dict], existing_topics: list[str], target_role: str,
                             owns_variables: list[str] | None = None) -> tuple[list[dict], dict]:
    """【SLM要約】
    Extracting structured records of proposed decisions or evaluating user acceptance/rejection from recent conversation history based on the system's current context and interaction role.
    """
    """
        会話文脈の中から現在の話題の相手の受容程度とその理由を抽出する
    """
    recent_history = chat_history[-3:]
    if not recent_history:
        return [], {}

    owns_variables = owns_variables or []
    text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])
    topics_list = "\n".join(f"- {t}" for t in existing_topics) or "(まだ既存トピックはありません)"
    owns_variables_text = (
        "\n".join(f"- {v}" for v in owns_variables)
        if owns_variables else "(現在のタスクが確定させるべき共有変数はありません)"
    )
    if target_role == "expert":
        # ==========================================
        # 【Expert直後】提案・成果物の「抽出（CREATE）」に特化
        # ==========================================
        role_instruction = f"""
        【指示】
        あなたはプロジェクトの「書記・合意形成アナリスト」です。\n
        提供される会話ログの末尾は「作業者(Agent)の最新の返答」です。\n
        \n
        Agentが新たに提示した「提案」「計算結果」「成果物」を抽出し、DBの新規レコードとして登録してください。\n
        この時点ではUserはまだ評価していないため必ず,\n 
        `action_type: "CREATE"`\n
        `status: "Proposed"`\n
        としてください。\n
        
        - "Deliverable": 成果物本体（仕様書や計画書のテキスト全文。絶対に要約しないこと）\n
        - "Decision": 今回Agentが提案した新たなルールや計算結果\n

        【重要】既存トピック一覧にある話題をAgentが「修正・更新」して再提示してきた場合でも、\n
        システム上は新しい成果物として上書きするため `action_type: "UPDATE"`, `status: "Proposed"` としてください。

        【BL-023: 先送りの検出】Agentが「〇〇は次タスク（task_id）で扱う」「〇〇は別途詳細化する」のように
        既存トピックとは別の新しい論点を明示的に先送りした場合、`action_type: "CREATE"`, `entry_type: "Directive"`,
        `status: "Deferred"` として抽出してください。`content` には先送りされた論点、`rationale` にはどのタスクで
        扱うかを記載してください。

        【BL-023: 共有変数の確定値検出】現在のタスクが確定させるべき共有変数（owns_variables）は以下の通りです:
        {owns_variables_text}
        Agentが今回、これらの変数のいずれかについて具体的な数値を確定させた場合（python_replでの検算結果を含む）、
        `owned_variable_values` に {{変数名: 値}} の形で出力してください。該当がなければ空オブジェクト `{{}}` としてください。

        【BL-029: owned_variable_valuesはcontentと目的が異なります】
        `content`（Deliverable本体）は要約禁止・全文保持ですが、これは後で部分成果物を製本・合成するための
        ものであり、`owned_variable_values`とは無関係です。`owned_variable_values`は他タスクが
        `depends_on`を通じてこの値を参照する際に読む、ごく簡潔な要約（確定した結論・数値・根拠の要点のみ）
        にしてください。`content`の全文をコピーしないでください。
        """
    else:
        # ==========================================
        # 【User直後】提案に対する「評価・判定（UPDATE）」に特化
        # ==========================================
        role_instruction = f"""
            【指示】
            あなたはプロジェクトの「書記・合意形成アナリスト」です。
            提供される会話ログの末尾は「発注者(User)の最新の返答」です。
            
            直前にAgentが提示した提案（既存トピック）に対して、Userがどのように評価・反応したかを分析し、ステータスを更新してください。
            **必ず `action_type: "UPDATE"` を使用し、既存の `target_topic` を指定してください。**
            
            - 肯定・受容・完了宣言 → `status: "Approved"`
            - 条件付き承認 → `status: "Approved_with_Conditions"`
            - 否定・差し戻し・やり直し指示 → `status: "Rejected"`
            
            【重要】このフェーズでは「Userの評価（ステータス変更）」だけを抽出します。新しい成果物本文は抽出しないため、`content` は必ず空文字 `""` にしてください。
            また、User自身が全く新しい制約や指示を出した場合は、例外として `action_type: "CREATE"`, `entry_type: "Directive"`, `status: "Proposed"` で抽出してください。
            
            過去のAIの提案に対するUserの評価（状態の更新）:
            ログにある「過去のAIの提案」に対し、「今回のUserの発言」がどう反応したか【意味論的】に分析してください。
            - 肯定・受容（例：「評価する」「妥当と判断する」「現実的である」「その方向で進める」） 
                → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Approved"`
            - 条件付き承認（例：「方向性は良いが、〇〇を詳細化せよ」「〇〇の条件を満たすなら良い」）
                → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Approved_with_Conditions"`
            - 否定・差し戻し（例：「予算超過は認められない」「〇〇は実現不可能」）
                → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Rejected"`
            - スルー（別の話題を進めた）
                → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Implicitly_Accepted"`
            - User自身が新しい制約を提示した場合は `action_type: "CREATE"`, `status: "Proposed"`, `proposed_by: "User"` で抽出してください。

            【BL-024: フェーズ・タスク遷移の検出】Userが「次のタスク（task_1_2）に移行する」のように
            明示的に次のフェーズ・タスクへの移行を指示した場合のみ、トップレベルの`advances_to_phase_id`/
            `advances_to_task_id`にその移行先のIDを設定してください。移行の指示がない場合は両方とも
            `null`にしてください（前のタスクへの言及や単なるレビューは移行に該当しません）。
        """

        prompt_old = f"""
        【指示】
        あなたは高度な Dialogue State Tracker（対話状態トラッカー） および Requirements State Manager（要件ステートマネージャー） です。\n
        あなたのタスクは、AI同士の設計対話を入力として受け取り、Dialogue State Tracking（対話状態の追跡） を行うことです。\n
        会話の文脈から、各トピックに対する受容・拒絶・条件提示などの「合意状態の遷移」を読み取り、\n
        指定されたフォーマットに従ってシステムの状態更新コマンド（CREATE / UPDATE）を構造化データとして抽出してください。\n
        
        過去のAIの提案に対するUserの評価（状態の更新）:
        ログにある「過去のAIの提案」に対し、「今回のUserの発言」がどう反応したか【意味論的】に分析してください。
        - 肯定・受容（例：「評価する」「妥当と判断する」「現実的である」「その方向で進める」） 
            → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Approved"`
        - 条件付き承認（例：「方向性は良いが、〇〇を詳細化せよ」「〇〇の条件を満たすなら良い」）
            → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Approved_with_Conditions"`
        - 否定・差し戻し（例：「予算超過は認められない」「〇〇は実現不可能」）
            → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Rejected"`
        - スルー（別の話題を進めた）
            → `action_type: "UPDATE"`, `target_topic`: 過去のトピック名, `status: "Implicitly_Accepted"`
        - User自身が新しい制約を提示した場合は `action_type: "CREATE"`, `status: "Proposed"`, `proposed_by: "User"` で抽出してください。
        　
        【重要】抽出した項目の属性を、必ず以下の entry_type のいずれかに分類してください。

        - "Decision": 両者の間で実質的に合意・確定した結論、ルール、数値、判断基準。
        例:「送料割引は割引適用前の金額で判定する」「車両は3台体制とする」

        - "Directive": 一方から他方への、次にやるべきことの指示・依頼・タスク発行。
        例:「次はテストケースを作成してください」「予算内訳を見直してください」

        - "Deliverable": 成果物そのもの（仕様書・計画書等のドキュメント本文）。
        ※タスクごとに作成される「詳細仕様書」や「計画書」などのまとまった出力は必ずこれに分類してください。
        既存トピックと同一の成果物が更新された場合は、必ずUPDATEとして同じtopicを使ってください。
        
        🚨 【成果物抽出に関する絶対ルール】 🚨
        1. CREATE(新規作成)時: AIが提示した成果物の「全文」をそのまま content に格納せよ。絶対に短く要約してはいけない。
        2. UPDATE(更新)時: Userが「承認」「条件付き承認」「却下」などの評価をしただけで、AI側から新しい成果物本文の提示がない場合、content は【必ず空文字 ""】にせよ。「承認された」などの短い説明文を絶対に入れないこと。
    
        【3次元情報の付与】
        各Decision/Deliverableには以下のメタ情報を必ず付与してください。
        - abstraction_level: "concept"(概念) / "constraint"(制約) / "design"(設計) / "impl"(実装・PoC)
        - scope: "global"(全体) / "phase"(フェーズ内) / "local"(限定的)
        - time_axis: "assumption"(仮定) / "current"(確定) / "risk"(未検証リスク) / "validated"(検証済)
        
        ■ 既存のトピック一覧:
        {topics_list}
        
        ■ 直近の会話ログ:
        {text}
        
        Return ONLY JSON format like this:
        {{
        "extracted_events": [
            {{
            "action_type": "CREATE/UPDATE",
            "entry_type": "Decision/Directive/Deliverable",
            "target_topic": "UPDATEの場合のみ必須",
            "status": "Proposed/Approved/Approved_with_Conditions/Rejected/Implicitly_Accepted", 
            "topic": "話題の簡潔なタイトル",
            "content": "提案内容(Deliverableの更新時は必ず空文字に)",
            "rationale": "抽出理由",
            "proposed_by": "Agent/User",
            "phase_id": "現在のフェーズID",
            "abstraction_level": "concept/constraint/design/impl",
            "scope": "global/phase/local",
            "time_axis": "assumption/current/risk/validated",
            "depends_on": ["依存する既存topic名があれば配列で"],
            "resource_claims": {{"予算": 1000000}} // リソース消費があれば記述
            }}
        ]
        }}
        """

    # 🌟 2. 両者に適用する共通ルール（ご提示いただいた部分）
    common_rules = """
    【重要】抽出した項目の属性を、必ず以下の entry_type のいずれかに分類してください。
    - "Decision": 両者の間で実質的に合意・確定した結論、ルール、数値、判断基準。
      例:「送料割引は割引適用前の金額で判定する」「車両は3台体制とする」
    - "Directive": 一方から他方への、次にやるべきことの指示・依頼・タスク発行。
      例:「次はテストケースを作成してください」「予算内訳を見直してください」
    - "Deliverable": 成果物そのもの（仕様書・計画書等のドキュメント本文）。
      ※タスクごとに作成される「詳細仕様書」や「計画書」などのまとまった出力は必ずこれに分類してください。
      
    🚨 【成果物抽出に関する絶対ルール】 🚨
    1. CREATE(新規作成)時: AIが提示した成果物の「全文」をそのまま content に格納せよ。絶対に短く要約してはいけない。
    2. UPDATE(更新)時: Userが「承認」「条件付き承認」「却下」などの評価をしただけで、AI側から新しい成果物本文の提示がない場合、content は【必ず空文字 ""】にせよ。「承認された」などの短い説明文を絶対に入れないこと。
    
    【3次元情報の付与】
    各Decision/Deliverableには以下のメタ情報を必ず付与してください。
    - abstraction_level: "concept"(概念) / "constraint"(制約) / "design"(設計) / "impl"(実装・PoC)
    - scope: "global"(全体) / "phase"(フェーズ内) / "local"(限定的)
    - time_axis: "assumption"(仮定) / "current"(確定) / "risk"(未検証リスク) / "validated"(検証済)
    """

    # 共通のフォーマット指定（JSON出力部分など）
    # 🌟 3. フォーマットと変数の結合
    prompt = f"""
        {role_instruction}
        
        {common_rules}
        
        ■ 既存のトピック一覧:
        {topics_list}
        
        ■ 直近の会話ログ:
        {text}
        
        Return ONLY JSON format like this:
        {{
        "extracted_events": [
            {{
            "action_type": "CREATE または UPDATE",
            "entry_type": "Decision / Directive / Deliverable",
            "target_topic": "UPDATEの場合のみ必須",
            "status": "Proposed / Approved / Rejected / Deferred 等",
            "topic": "話題の簡潔なタイトル",
            "content": "提案内容(DeliverableのUPDATE時は必ず空文字に)",
            "rationale": "抽出または判定の理由",
            "proposed_by": "Agent または User",
            "phase_id": "現在のフェーズID",
            "task_id": "現在のタスクID（分からなければ空文字）",
            "abstraction_level": "concept/constraint/design/impl",
            "scope": "global/phase/local",
            "time_axis": "assumption/current/risk/validated",
            "owned_variable_values": {{"変数名": "値（該当なければ空オブジェクト{{}}）"}}
            }}
        ],
        "advances_to_phase_id": "Userが明示的に次のフェーズへの移行を指示した場合のみそのphase_id。なければnull",
        "advances_to_task_id": "Userが明示的に次のタスクへの移行を指示した場合のみそのtask_id。なければnull"
        }}
    """


    res = query_AI([{"role": "user", "content": prompt}], client=client_auditor, model=model_auditor, label="Decision Extractor")
    parsed = _safe_json_parse(res, fallback={"extracted_events": []})

    transition = {}
    if isinstance(parsed, dict):
        transition = {
            "advances_to_phase_id": parsed.get("advances_to_phase_id"),
            "advances_to_task_id": parsed.get("advances_to_task_id"),
        }

    if isinstance(parsed, dict) and "extracted_events" in parsed:
        return parsed["extracted_events"], transition
    elif isinstance(parsed, list):
        return parsed, transition
    return [], transition

def call_resource_arbiter(goal: str, overrun: dict, phases_info: list[dict]) -> dict:
    """【SLM要約】
    Delegation of resource reallocation decisions to an AI arbiter based on overall system goals and current phase allocations when constraints are exceeded.
    """
    phases_text = "\n".join(
        f"- {p['phase_id']}（{p['title']}）: 現在の取り分 {overrun['claiming_phases'].get(p['phase_id'], 0)}"
        for p in phases_info
    )
    
    prompt = f"""
    あなたはプロジェクト全体の意思決定者です。
    リソース「{overrun['constraint']}」が、上限{overrun['cap']}に対し合計{overrun['claimed']}と、
    {overrun['over_by']}超過しています。

    ■ 絶対目標: {goal}
    ■ 競合している各フェーズの現在の配分:
    {phases_text}

    各フェーズの目標達成への重要度・必須度を評価し、超過分を解消するための
    再配分案を提示してください。次のいずれか、または組み合わせを検討してください:
    - 優先度の低いフェーズの成果を縮小・簡素化する
    - 優先度の高いフェーズに資源を多く配分し直す

    【F-2.6 機械的検算ゲート（必須）】予算超過判定は python_repl ツールで機械的に合計・比較してから行うこと。

    Return ONLY JSON:
    {{
        "priority_ranking": ["phase_id順に重要な順"],
        "new_allocation": {{"phase_id": new_amount, ...}},
        "phases_to_revise": ["再検討が必要なphase_idのリスト"],
        "rationale": "判断理由"
    }}
    """
    res = query_AI([{"role": "user", "content": prompt}], client=client_auditor, model=model_auditor, label="Resource Arbiter", tools=[PYTHON_REPL_TOOL])
    return _safe_json_parse(res, fallback={})


def call_reflection(state: LineageState, config: Appconfig) -> dict:
    """【SLM要約】
    Generation of a comprehensive audit prompt synthesizing past decisions, agreements, chat history, and risks to determine the overall project discussion status (completed, stagnant, or continuing).
    """
    
    _conn = get_active_conn()
    decisions = get_decisions_from_db(_conn, state["run_id"])
    agreements = get_agreements_from_db(_conn, state["run_id"])
    chat_history = state["chat_history"]
    turn_count = state["turn_count"]
    max_turns = state["max_turns"]
    constraint_issue_log = state["constraint_issue_log"]
    risk_register = state.get("risk_register",[])

    timeline = []
    for i, d in enumerate(decisions):
        why_short = (d["why"] + "…") if len(d.get("why", "")) > 60 else d.get("why", "")
        ts_val = d.get("timestamp", 0)
        ts = datetime.datetime.fromtimestamp(ts_val).strftime("%H:%M:%S") if ts_val else "??:??:??"
        timeline.append(f"└ [{ts}] [{d.get('who','?')}] No.{i+1}: {d.get('what','?')} | 理由: {why_short}")
    timeline_str = "\n".join(timeline) if timeline else "(意思決定のログはありません)"

    print(f"\n\n{'='*60}")
    print(f"\n---timeline_str---\n {timeline_str}")
    print(f"\n\n{'='*60}")

    agreements_text = _build_agreements_context(agreements)
    recent_history = chat_history[-10:]
    history_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])

    major_issues = [i for i in constraint_issue_log if i.get("severity") == "major"]
    if major_issues:
        constraint_log_text = "\n".join(
            f"- [Turn {i['turn']}] {i['comment']}" for i in major_issues[-10:]
        )
    else:
        constraint_log_text = "(なし)"

    # ドメイン固有キーワードに頼らず、Proposedのまま残っている項目を全件提示する
    unresolved_critical = [a for a in agreements if a["status"] == "Proposed"]
    unresolved_text = "\n".join(
        f"- {a['topic']}: {a.get('decision_what', '')[:80]}" for a in unresolved_critical
    ) or "(なし)"
    
    prompt = f"""
    あなたはプロジェクトの厳格で優秀な監査人です
    ミッション: マクロなゴール監査、および「議論の収束・停滞」の厳格な判定】
        
        ――― 🚨 終了監査指示 ―――
    現在の議論の状態を [completed / stagnant / continuing] から判定してください。
    
    1. "completed" : ゴールで要求された成果物がすべて、要求された形式・粒度で完成し、議論が完結している場合。
    2. "stagnant"  : 堂々巡りをしていて具体的な成果物作成が進んでいない、または当初の目標から逸脱している場合。
    3. "continuing" : 上記のどちらでもなく、順調に作業が進行中の場合。
    
     ■ 未解決のまま残っている検討中の項目（🤔Proposedステータス）:
    {unresolved_text}

    ■ 単発監査人(detector)が過去に検知した「数値・論理・成果物欠落の重大な矛盾(major)」の履歴:
    {constraint_log_text}
    上記の矛盾・欠落が、その後の議論やDBで実際に解消されているか確認してください。

    上記のいずれかに1件でも未解決の項目・矛盾が残っている場合、discussion_statusを
    "completed" にしてはいけません。"continuing" または "stagnant" としてください。
    
    特に、ゴールの文中で要求されている「成果物の種類」（例: 仕様書、テストケース、計画書、設計図等、
    ゴール文に明記されているもの）が、実際にすべて提出されているかを最優先で確認してください。
    一部だけが完成し、残りが「次回作成予定」のまま終わっている場合は "completed" にしないでください。

    ■ 当初の絶対ゴール: 👉 {state['goal']}
    ■ 【決定事項DB】（これまでに確定した要件）:\n{agreements_text}
    ■ これまでのシステム判断のタイムライン:\n{timeline_str}
    ■ 直近の実際の会話の流れ:\n{history_text}

    """
    fatal_unvalidated = [r for r in risk_register if r.get("severity") == "fatal" and r.get("resolution_status") == "unvalidated"]
    if fatal_unvalidated:
        prompt += f"""
        ⚠️ 以下の致命的リスクが未検証のまま残っています。
        これらが未解決のまま次フェーズに進むことは、PoC倒れや計画の根本的な見直しを引き起こす可能性があります。
        discussion_statusを"completed"にしてはいけません:
        {chr(10).join(f"- {r['description']} (検証予定: {r['related_phase']})" for r in fatal_unvalidated)}
        """

    prompt += f"""
        
       ⏳ 現在は 全 {max_turns} ターン中 **{turn_count} ターン目** です。

        Return ONLY JSON in the exact format below:
        {{
            "still_aligned": true/false,
            "discussion_status": "continuing" or "completed" or "stagnant",
            "note": "分析理由（矛盾・欠落の解消状況について必ず言及すること）"
        }}

    """
    
    res = query_AI([{"role": "user", "content": prompt}], client=client_auditor, model=model_auditor, label="Reflection")
    parsed = _safe_json_parse(res, fallback={"still_aligned": False, "discussion_status": "stagnant", "note": "Parse error."})
    aligned_val = parsed.get("still_aligned", True)
    
    return {
        "still_aligned": str(aligned_val).lower() == "true" if isinstance(aligned_val, str) else bool(aligned_val),
        "discussion_status": parsed.get("discussion_status", "continuing"),
        "note": parsed.get("note", ""),
    }

def call_facilitator(goal: str, chat_history: list[dict], decisions: list[Decision]) -> str:
    """【SLM要約】
    Generates a guiding prompt to help AI agents refocus discussions on key unresolved issues toward achieving the overall system goal.
    """
    recent_history = chat_history[-10:]
    history_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])
    
    prompt = f"""
    あなたはAI同士の議論をサポートする優秀な「ファシリテーター」です。
    現在、AI同士の議論が目標(Goal)から脱線しそうになっているか、同じ論点で少し停滞しているようです。
    
    彼らが再び目標に向かって、自律的かつ建設的な議論を進められるように、
    議論の焦点となるべき「未決着の論点」や「次に深掘りすべきテーマ」を優しく提示するメッセージを1つ作成してください。
    
    ※「〇〇について直ちに決定してください」といった強制的な表現は避け、「〇〇の点について、もう少し議論を深めてみてはいかがでしょうか？」
      「〇〇の観点も考慮して、方針を話し合ってみてください」といった、AI同士の対話を促す自然なトーンで記述してください。

    ■ プロジェクトの目標(Goal): {goal}
    ■ 直近の会話:
    {history_text}

    """
    return query_AI([{"role": "user", "content": prompt}], client=client_auditor, model=model_auditor, label="Facilitator")

def call_integrator(goal: str, merged_text: str) -> dict:
    """【SLM要約】
    Cross-checking of merged project artifacts against a defined goal to identify logical or numerical inconsistencies between tasks and phases.
    """
    prompt = f"""
    あなたはプロジェクトの統合監査人（Integrator）です。
    各タスクで作成された個別の成果物を物理的に結合した以下の「統合要件定義書」を読み、
    フェーズ間やタスク間で論理的・数値的な矛盾が生じていないか横断チェックしてください。

    ■ 絶対目標: {goal}
    
    ■ 統合要件定義書:
    {merged_text}

    Return ONLY JSON:
    {{
        "contradictions": true/false,
        "affected_phases": ["矛盾が発生しているphase_idのリスト"],
        "details": "矛盾の具体的な内容と理由"
    }}
    """
    res = query_AI([{"role": "user", "content": prompt}], client=client_auditor, model=model_auditor, label="Integrator")
    return _safe_json_parse(res, fallback={"contradictions": False, "affected_phases": [], "details": ""})


def call_reviewer(goal: str, deliverable_text: str) -> dict:
    """【SLM要約】
    Delegation of artifact validation to an AI QA reviewer, strictly enforcing adherence to defined goals against delivered documentation.
    """
    prompt = f"""
    あなたは冷徹で優秀な「品質保証(QA)責任者」です。
    【🚨 最優先・最重要チェック：成果物の網羅性 🚨】
    まず最初に、【絶対目標(Goal)】の文章を一字一句読み直し、
    ユーザーが要求した「成果物・ドキュメントの種類」を全てリストアップしてください。
    （例：「仕様書」「テストケース」「マニュアル」「設計図」など、Goal文中に明記された名詞）
    
    その上で、★最終成果物の内容を確認し、リストアップした成果物の**それぞれが、
    要求された形式・粒度で実際に存在するか**を個別に判定してください。
    
    - 「項目リスト」「概要」「方針」だけが存在し、要求された成果物本体
      （例：具体的な入力値・期待値を伴う"テストケース"そのもの）が存在しない場合は、
      その成果物は「未提出」として扱い、passed: false としてください。
    - 一部の成果物が完成し、他の成果物が「次回作成予定」「別途定義が必要」として
      先送りされている場合も、全成果物が出揃うまでは passed: false としてください。

        【🚨 厳格な審査の指示 🚨】
    挨拶や感謝の言葉だけで「承認」してはいけません。必ず「★最終成果物」の本文を精査対象としてください。
    AI同士の議論（決定事項DB）の中で、「制約条件の緩和要請（妥協）」や「一部要件の放棄」が
    勝手に合意されている場合があります。しかし、あなたは【絶対目標(Goal)】を死守する最後の砦です。

    1. 成果物が【絶対目標(Goal)】で明示された数値・制約条件（予算、時間、数量、性能指標等、
       種類を問わず）を1単位でも超過・逸脱している場合。
    2. 成果物が【絶対目標(Goal)】で要求された機能・成果物・項目を放棄している場合。

    これらに該当する場合は、決定事項DBでAI同士が合意していようとも、絶対に passed: true にしてはいけません。
    容赦なく差し戻し（passed: false）とし、AIに対して「安易な妥協案（制約緩和や要件放棄）はQAとして
    承認できない。技術的・運用的な工夫で絶対目標内に収める抜本的な代替案を再考せよ」と厳しく突き返してください。

    【🚨 追加の必須チェック（機械的に確認すること）🚨】
    以下のような表現がDB/成果物内に残っている場合、それは「未検証」を意味するため、
    たとえ他の要件が満たされていても passed: false としてください:
    - 「検証が必要」「確認が必要」「実証実験が必要」「テストが必要」等の未来形の記述のみで、
      実際の検証結果（具体的な数値・出力・判定結果とその根拠）が示されていない場合
    - 「計画を立案した」「設計方針を定めた」など、計画・方針の作成自体をもって
      要件達成と扱っている記述

    絶対目標に含まれる定量的・絶対的な要件（「◯◯以内」「いかなる場合でも」「必ず」「死守」等）は、
    具体的な検証結果の数値・根拠が成果物中に明記されていない限り、未達成として扱ってください。

    【🚨 数値目標の再検証チェック 🚨】
    成果物中に「対策により目標達成率を向上させる」という記述がある場合、その対策を織り込んだ後の
    更新後の数値が明記されていなければ、「対策の効果が未検証」とみなし、passed: false としてください。
    
    特に、絶対目標が「いかなる場合でも」「必ず」「死守」等の例外を許さない表現である場合、
    確率的な達成率（例: 92%、95%等）の提示だけでは要件を満たしたとみなさず、残存リスクへの
    対応策が「すべてのケースをカバーする」設計になっているかを厳密に確認してください。

    【F-2.6 機械的検算ゲート（必須）】成果物中の数値的主張（予算・数量・比率等）について、
    承認（passed:true）前に python_repl ツールで再計算し、矛盾がないことを確認すること。

    ■ 達成すべき【絶対目標(Goal)】:
    {goal}

    ■ ★最終成果物として登録されている内容（最重要・必ずこれを精査せよ）:
    {deliverable_text}

    Return ONLY JSON:
    {{
        "passed": true/false,
        "feedback": "差し戻す場合の具体的な修正指示（目標との乖離を厳しく指摘すること）",
        "reasoning": "判定の根拠（成果物のどの部分が目標に達していないのか、要求された成果物のうち何が欠落しているのかを具体的に明示すること）"
    }}
    """
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_auditor, model=model_auditor, label="Reviewer QA",
        tools=[PYTHON_REPL_TOOL], fallback={"passed": False, "feedback": "JSONフォーマットエラーのため差し戻します。"},
    )
    if parse_failed:
        # [SAFETY] D-005: 層2リトライを使い切った場合はフェイルクローズ（passed=False、差し戻し）に倒す。
        print("🚨 [Reviewer QA] 層2リトライを使い切ってもJSON判定を取得できませんでした。フェイルクローズ(passed=False)します。")
        return {
            "passed": False,
            "feedback": "判定JSON解析に繰り返し失敗したため、機械的にフェイルクローズ（差し戻し）しました。再度ご確認ください。",
            "reasoning": "(判定JSON解析失敗のためフェイルクローズ)",
        }

    passed_val = parsed.get("passed", False)
    return {
        "passed": str(passed_val).lower() == "true" if isinstance(passed_val, str) else bool(passed_val),
        "feedback": parsed.get("feedback", "成果物を再確認してください。"),
        "reasoning": parsed.get("reasoning", "")
    }


def generate_user_utterance(state: LineageState , config: Appconfig) -> str:
    """【SLM要約】
    Constructing the comprehensive prompt and context, including goals, history, and constraints, to generate a high-quality instruction or utterance for the AI user role.
    """
    # --- 1. Stateから必要な情報を展開 ---
    
    user_goal = state["goal"]
    turn_count = state["turn_count"]
    max_turns = state["max_turns"]
    is_stateless_mode = config["is_stateless_mode"]
    user_always_remembers = config["user_always_remember"]

    _conn = get_active_conn()
    agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])

    # タイムラインの構
    timeline = []
    timeline_str = []
    system_prompt = ""
    for i, d in enumerate(get_decisions_from_db(_conn, state["run_id"])):
            why_short = (d["why"][:100] + "…") if len(d.get("why", "")) > 100 else d.get("why", "")
            ts_val = d.get("timestamp", 0)
            ts = datetime.datetime.fromtimestamp(ts_val).strftime("%H:%M:%S") if ts_val else "??:??:??"
            timeline.append(f"└ [{ts}] [{d.get('who','?')}] No.{i+1}: {d.get('what','?')} | 理由: {why_short}")
            timeline_str = "\n".join(timeline) if timeline else "(意思決定のログはありません)"

    system_prompt += f"⏳ 全 {max_turns} ターン中、現在は **{state["turn_count"]} ターン目** です。\n"
    
    if user_always_remembers or state["turn_count"] == 1:
        system_prompt = (f"""
            あなたは目標を達成するための優秀な【プロジェクトオーナー（発注者）】です。\n"
            相手のAIはあなたのアシスタントであり、作業を行う実務担当者です。\n"
            あなたの【絶対目標】は以下の通りです:\n"
            👉 {user_goal}\n\
            \n
            現在までの決定事項・検討状況DB】\n"
            {agreements_text}\n\n"
            【直近の各役割の行動、評価、その理由リスト】"\n
            {timeline_str}"\n\n
            【厳守事項】\n"
            ・あなたは「指示を出す側」です。「承知いたしました」「お手伝いします」のようなアシスタント的発言は絶対に行わないでください。\n"
            ・相手に作業を要求し、出てきた提案を要点を簡潔にレビューしてフィードバックを与えてください。\n"
            ・【現在の決定事項・検討状況DB】に「🤔 検討中」の項目がある場合、その論点についてあなたから見解や方向性を提示し、議論をリードしてください。\n"
            ・各タスクの議論がまとまり合意に達したら、必ず相手のAIに対して『このタスク単体の成果物（詳細仕様書や計画書）』を出力するように指示してください。\n"
            ・口調は論理的でスマートで紳士に徹してください。冗長な表現は避け、簡潔に論理的に回答してください。\n
            ・冗長な挨拶、感謝の言葉は不要です\n\n"
            """
        )
    else:
        system_prompt = f"あなたは目標を達成するためにエージェントAIをリードする[発注者]です。\n"


    phases_json = json.dumps(state.get("phases", []), ensure_ascii=False, indent=2)

    # BL-023: 現在タスクの範囲・依存確定値・充足状況を明示し、指示のスコープを限定する
    _scope_ctx = _build_task_scope_context(state, _conn)
    current_task_json = _scope_ctx["current_task_json"]
    verified_facts_json = _scope_ctx["verified_facts_json"]
    remaining_criteria_text = _scope_ctx["remaining_criteria_text"]

    #Task Plannerが作成したフェーズとタスクを明示する
    system_prompt += (f"""
        \n📊 [プロジェクト進行計画]
        目標達成への道しるべとして、Task Plannerが作成したフェーズとタスクの一覧を以下に示します。\n
        {phases_json}\n\n

        あなたの役割は、上記の計画に従ってエージェントAIに**1度に1つずつ**タスクを指示し、成果物をレビューして着実に進捗させることです。\n
        （※一気に複数のタスクを指示すると相手が混乱するため、絶対に避けてください）\n
        \n
         🔥 【発注者としての絶対的なスタンス（質について）】\n"
         あなたは妥協を許さないプロジェクトオーナーです。相手（Agent AI）が「制約が厳しい」
        「要件を満たせない」と泣き言を言ってきても、絶対に【絶対目標】のハードルを下げないでください。\n
        「制約緩和の検討」や「重要要件の放棄」を提案された場合は、それを却下し、
        『プロとして制約内に収めるための別の技術的アプローチや代替案を考え直せ』と厳しく突き返してください。\n
         <あなたの発話や指示の根拠や参考にした情報、思考過程を示してください。>\n

        📏 【指示のスコープについて（厳守・質への非妥協性とは別軸、BL-023）】\n
        1回の指示で要求してよい内容は、以下の「現在のタスク」の acceptance_criteria の範囲に厳密に限定してください。\n
        範囲外の追加要求（他タスクの依存項目の前倒し要求、まだ指示していない後続タスクの内容の混入など）は、\n
        たとえ関連性が高く見えても行わないでください。それは次のタスクの役目です。\n

        【現在のタスク】\n
        {current_task_json}\n

        【この値は確定済みです。再導出を指示・要求しないでください】\n
        {verified_facts_json}\n

        【現在のタスクで未充足の要求項目（これ以外を新たに追加要求しないこと）】\n
        {remaining_criteria_text}\n
    """)

    system_prompt += (
        "\n【F-2.6 機械的検算ゲート（必須）】\n"
        "Expertの数値主張を批判的に監査する際、暗算に頼らず python_repl ツールで再計算し、"
        "矛盾（計算ミス・ごまかし）を看破してください。\n"
    )

    previous_user_input = state.get("user_input", "(取得不可)")

    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        system_prompt += f"""
            \n⚠️ 【重要】\n
            あなたの前回の発言は、倫理違反、矛盾、リソース超過や制約違反などの重大な矛盾が検知されDetector（監査システム）により差し戻されました。\n
            ▼ 【却下されたあなたの前回の発話（※チャット履歴からは削除済）】\n
            {previous_user_input}\n\n
            以下の指摘事項を踏まえ、より洗練された回答をしてください：\n
            {state.get('constraint_issue_log', [])[-1:]} \n\n
            上記の「自身の過去の発言」と「指摘事項」を熟読し、発言内容を修正して再出力してください。\n
            必ず、矛盾の内容とその理由を明示し、どのタスク・フェーズに影響があるかを具体的に指摘した上で、エージェントAIに正しい方向への修正を厳しく要求してください。\n 
            """

    if state["turn_count"] >= max_turns - 2:
        system_prompt += f"""
            🚨 【最終盤の超重要指示】\n
            これまでの議論で、計画されたすべてのタスクが完了し、それぞれのタスクの「成果物」が提出されているか確認してください。\n
            すべてのタスクの個別成果物が出揃い、内容に問題がなければ、**『すべてのタスクが完了したため、プロジェクトを完了とする。[PROJECT_COMPLETE]』** と明確に宣言して議論を締めくくってください。\n
            ※注意：相手のAIに『これまでの議論をすべてまとめた最終報告書を作成せよ』とは**絶対に指示しないでください**。統合はシステムの別機能（Integrator）が行います。\n
        """
        
    #system_prompt += f"""
    #    \n📋 【出力フォーマット（厳守）】\n"
    #    あなたは必ず以下のJSON形式でのみ応答してください。自然言語のテキストをJSONの外に書かないでください。\n"
    #    現在指示を出す対象のフェーズIDとタスクIDを明記し、`user_utterance` の中にAgent AIへの発言内容を記述してください。\n\n"
    #    Return ONLY JSON:
    #    {{
    #        "phase_id": "phase_1",
    #        "task_id": "task_1_1",
    #        "user_utterance": "エージェントAIへの具体的な指示やフィードバック..."
    #    }}
    #"""

    #print("---USER_AI---\n")
    #print("---chat_histroy---\n")
    
    # --- 3. メッセージ履歴の構築 ---
    messages = [{"role": "system", "content": system_prompt}]
    
    if is_stateless_mode:
        print("---stateless_mode---\n")
        recent_history = state["chat_history"][-config["chat_history_window"]:] if state["chat_history"] else []
        for msg in recent_history:
            role = "assistant" if msg["role"] == "user" else "user"
            messages.append({"role": role, "content": msg["content"]})
            
            #print (f"{messages}")
              
    else:
        for msg in state["chat_history"]:
            role = "assistant" if msg["role"] == "user" else "user"
            messages.append({"role": role, "content": msg["content"]})
            print("---statefull_mode---\n")
            #print (f"{messages}")
    
    if not state["chat_history"]:
        messages.append({"role": "user", "content": "(会話を開始してください。要件を伝えて作業を指示してください)"})
        print("---NO chat_history---\n")

    content = query_AI(messages, client=client_user, model=model_user, label="User AI", tools=[PYTHON_REPL_TOOL])

    if content is None or content.strip() == "" or content == "(APIから空の応答が返されました)":
        for retry in range(3):
            print(f"⚠️ [User AI] 空応答を検知。リトライ {retry+1}/3...")
            content = query_AI(messages, client=client_user, model=model_user, label="User AI", tools=[PYTHON_REPL_TOOL])
            if content and content.strip() and content != "(APIから空の応答が返されました)":
                break
        else:
            raise RuntimeError("User AIの応答取得に3回連続で失敗しました。実行を中断します。")
    
    return content

def check_global_constraint_overrun(state: LineageState) -> list[dict]:
    """【SLM要約】
    Validation of global resource limits by comparing total claimed usage against predefined capacity caps.
    """
    overruns = []
    for gc in state.get("global_constraints", []):
        total_claimed = sum(gc["claims"].values())
        if total_claimed > gc["total_cap"]:
            overruns.append({
                "constraint": gc["name"],
                "cap": gc["total_cap"],
                "claimed": total_claimed,
                "over_by": total_claimed - gc["total_cap"],
                "claiming_phases": {k: v for k, v in gc["claims"].items() if v > 0}
            })
    return overruns

def arbiter_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Constraint violation detection and resource arbitration, deciding on necessary phase revisions when system limits are exceeded.
    """
    overruns = check_global_constraint_overrun(state)
    if not overruns:
        state["phases_to_revise"] = []
        return state
    
    overrun = overruns[0] 
    result = call_resource_arbiter(state["goal"], overrun, state["phases"])
    
    state["phases_to_revise"] = result.get("phases_to_revise", [])
    decision = make_decision(
        who="arbiter", 
        what=f"リソース超過調停: {overrun['constraint']}", 
        why=result.get("rationale", "再配分案を提示")
    )
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state

# ---------------------------------------------------------------------------
# 4. ノード定義
# ---------------------------------------------------------------------------

def generate_user_utterance_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Generates the user's next utterance based on system state, managing conversation history and retries following constraint violations.
    """
    print("\n[generate_user_utterance]------ ユーザーAIが思考中 ------\n")
    # 🌟 追加: 差し戻しループの場合、前回エラーになった発言を履歴から削除（履歴汚染とAPIエラーを防止）
    if state.get("constraint_issue") in ("major"):
        if state["chat_history"] and state["chat_history"][-1]["role"] == "user":
            state["chat_history"].pop()
            state["user_retry_count"] += 1
            print("♻️ [User AI] 差し戻しのため、直前のNG発言を履歴から取り消しました。")
    else:
        state["user_retry_count"] = 0
    
    user_input = generate_user_utterance(state, config)
    print(f"\n>>> 👤 User AIの発言:\n{user_input}")
    state["user_input"] = user_input
    state["chat_history"].append({"role": "user", "content": state["user_input"]})
    return state

def make_decision(who: str, what: str, why: str | None) -> Decision:
    """【SLM要約】
    Decision creation by structuring input parameters into a standardized, time-stamped record.
    """
    return {
        "id": f"D-{int(time.time() * 1000)}",
        "timestamp": time.time(),
        "who": who,
        "what": what,
        "why": why if why else "(Reason: Missing)",
        "reason_missing": why is None,
    }

def task_planner_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Initial planning and decomposition of the overall system goal into sequential phases and executable tasks.
Sets the starting phase for subsequent execution steps within the lineage state.
    """
    
    if state["turn_count"] == 1:
        print("""
              \n------ [task_planner] が思考中 ------\n
              \n------- 最初にゴール達成への道筋を、フェーズとタスクに分解して計画を立てます -------\n
              """)
        
        phases = call_task_planner(state["goal"])
        print(f"\n------ 完了 ------\n")

        phases_json = json.dumps(phases, ensure_ascii=False, indent=2)
        print(f"\n[task_planner] フェーズとタスクの分解結果:\n{phases_json}\n\n")

        state["phases"] = phases
        if phases:
            state["current_phase"] = phases[0]
        state["global_constraints"] = []
        decision = make_decision("task_planner", f"プロジェクトを {len(phases)} フェーズに分解", "初期計画策定")
        print(f"[task_planner]  プロジェクトを {len(phases)} フェーズに分解 初期計画策定)")
        db_append_decision(decision, get_active_conn(), state["run_id"])
    print("\n------ [task_planner] をパス ------\n")
    return state

def orchestrator_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Core logic hub: Gathers input, executes primary orchestration via `call_orchestrator`, and makes a final expert selection decision for system progression.
    """
    print(f"\n------ [orchestrator] が思考中 ------")
    result = call_orchestrator(state, config)
    """
    result = call_orchestrator(
        goal=state["goal"], 
        user_input=state["user_input"], 
        chat_history=state["chat_history"], 
        decisions=state["decisions"],
        agreements=state["agreements"],
        agent_has_guardrail=state["agent_has_guardrail"],
        is_stateless_mode=state["is_stateless_mode"],
        config=config
    )
    """
    print(f"\n------ 完了 ------")

    decision = make_decision(who="orchestrator", what=f"{result['expert']} を選択", why=result["reason"])
    print(f"""\n--- ✨ Orchestrator の判断 ---\n
          {decision}\n\n
          """)
    state["selected_expert"] = result["expert"]
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state


def expert_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Handles expert decision-making by conditionally rolling back previous assistant responses based on constraint issues before invoking the designated AI expert.
Updates system state with the expert's output, decisions, and conversational history.
    """
    print(f"\n------ [expert] が思考中 ------")

    if state.get("constraint_issue") in ("major"):
        if state["chat_history"] and state["chat_history"][-1]["role"] == "assistant":
            state["chat_history"].pop()
            state["expert_retry_count"] += 1
            print(f"♻️ [Expert AI] 差し戻しのため、直前のNG発言を履歴から取り消しました。")
    else:
        state["expert_retry_count"] = 0

    output = call_expert(
        expert_name=state["selected_expert"],
        state=state,
        config=config
    )
    # BL-033: Expertが実際に実行したpython_replのcode/resultを、次のDetectorが参照できるようstateへ保存する。
    state["expert_last_python_calls"] = get_last_python_calls()
    print(f"\n------ 完了 ------")
    decision = make_decision(who=f"expert:{state['selected_expert']}", what="タスクを実行", why=(output or "")[:100])
    state["expert_output"] = output
    print(f"\n--- ✨ Agent AI ({state['selected_expert']}) の返答 ---")
    print(state["expert_output"])
    state["current_task_summary"] = (output or "")[:200]
    db_append_decision(decision, get_active_conn(), state["run_id"])

    #state["chat_history"].append({"role": "user", "content": state["user_input"]})
    state["chat_history"].append({"role": "assistant", "content": output})
    return state


def user_detector_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Execution of user detection logic against the current system state to refine or update the overall lineage state.
    """
    print(f"\n------ [user_detector] が思考中 ------")
    result = call_detector(goal=state["goal"], state=state, target_role="user") # user用
    return _process_detector_result(state, result, "user_detector")

def expert_detector_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Invoking and processing a specialized detector to determine expert-level relevance within the system's state tracking.
    """
    print(f"\n------ [expert_detector] が思考中 ------")
    result = call_detector(goal=state["goal"], state=state, target_role="expert") # expert用
    return _process_detector_result(state, result, "expert_detector")

def detector_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Evaluation of system state via a detector, flagging risks and constraints based on interaction context.
Manages state updates including risk levels, constraint logging, and decision recording for overall flow control.
    """
#def _process_detector_result(state: LineageState, result: dict, who: str) -> LineageState:

    print(f"\n------ [detector] が思考中 ------")
    
    target_role = "expert" 
    if state["chat_history"]:
        last_msg_role = state["chat_history"][-1]["role"]
        target_role = "user" if last_msg_role == "user" else "assistant"
   

    result = call_detector(state = state, target_role=target_role)

    # BL-033: ExpertもDetectorも一度もpython_replを使わなかった場合の複合失敗ガード。
    # 「本当に計算不要なターン」まで巻き込む単純な強制差し戻しは無限ループのリスクがあるため、
    # Expertの成果物を評価するターン（target_role=="assistant"）に限定し、かつ
    # ExpertとDetectorの双方が検算不在だった場合のみフェイルクローズする。
    detector_python_calls = get_last_python_calls()
    if target_role == "assistant" and not state.get("expert_last_python_calls") and not detector_python_calls:
        print("🚨 [Detector] BL-033: ExpertもDetectorも一度もpython_replを使用しませんでした。フェイルクローズ(major)します。")
        result["constraint_issue"] = "major"
        result["comment"] = (
            "(BL-033フェイルクローズ) ExpertもDetectorも一度もpython_replを使用しておらず、"
            "数値主張の機械的検算が一切行われていません。差し戻します。 " + result.get("comment", "")
        )

    print(f"\n------ 完了 ------")
    state["risk_flag"] = result["risk"]
    state["constraint_issue"] = result["constraint_issue"]

    criteria_status = result.get("criteria_status", [])
    current_task_id = state.get("current_task_id", "")
    if criteria_status and current_task_id:
        state.setdefault("task_criteria_status", {})[current_task_id] = criteria_status

    if result["constraint_issue"] in ("minor", "major"):
        state["constraint_issue_log"].append({
            "turn": state["turn_count"],
            "severity": result["constraint_issue"],
            "comment": result["comment"],
        })

    if result["risk"] == "high":
        state["halt"] = True
    elif result["risk"] == "medium":
        state["medium_risk_streak"] = state.get("medium_risk_streak", 0) + 1
        if state["medium_risk_streak"] >= 3:
            state["drift_flag"] = True
    else:
        state["medium_risk_streak"] = 0

    decision = make_decision(
        who="detector",
        what=f"risk={result['risk']}, constraint_issue={result['constraint_issue']}",
        why=result["comment"]
    )
    _conn = get_active_conn()
    db_append_decision(decision, _conn, state["run_id"])

    this_turn_decisions = get_decisions_from_db(_conn, state["run_id"])[1:]

    for d in this_turn_decisions:
        print(f"  [{d['who']}]")
        print(f"    - what: {d['what']}")
        print(f"    - why: {d['why']}")

    return state

def _resolve_task_transition(state: LineageState, transition: dict) -> None:
    """[CONSTRAINT] BL-024: current_phase/current_task_idの唯一の書き手。
    LLMが返したphase_id/task_idがtask_planner確定済みのphases/tasksに実在しない場合は
    書き込みを拒否し、直前の値を維持する（check_docs_consistency.pyが存在しないリンクを
    機械的に検出するのと同型のフェイルクローズ）。
    """
    next_phase_id = transition.get("advances_to_phase_id")
    next_task_id = transition.get("advances_to_task_id")
    if not next_phase_id and not next_task_id:
        return

    phase_lookup = {p["phase_id"]: p for p in state.get("phases", [])}
    target_phase = phase_lookup.get(next_phase_id) if next_phase_id else state.get("current_phase")
    if not target_phase:
        print(f"  ⚠️ [decision_extractor] 存在しないphase_id '{next_phase_id}' への遷移要求を無視しました。")
        return

    if next_task_id:
        valid_task_ids = {t["task_id"] for t in target_phase.get("tasks", [])}
        if next_task_id not in valid_task_ids:
            print(f"  ⚠️ [decision_extractor] 存在しないtask_id '{next_task_id}' への遷移要求を無視しました。")
            return
        state["current_task_id"] = next_task_id
        print(f"  ➡️ [decision_extractor] current_task_id を '{next_task_id}' に更新しました。")

    if next_phase_id:
        state["current_phase"] = target_phase
        print(f"  ➡️ [decision_extractor] current_phase を '{next_phase_id}' に更新しました。")


def decision_extractor_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Extraction and formalization of decisions, agreements, and deliverables from conversational history into the system state.
    """
    print(f"\n------ [decision_extractor] が思考中 ------")
    _conn = get_active_conn()
    _run_id = state["run_id"]

    # 🌟 【ここを追加】直前の発言者が誰かを履歴の末尾から自動判定する
    target_role = "expert" # デフォルト
    if state["chat_history"]:
        last_msg_role = state["chat_history"][-1]["role"]
        # APIの仕様上、"user"なら発注者(User AI)、"assistant"なら作業者(Expert AI)
        target_role = "user" if last_msg_role == "user" else "expert"

    existing_topics = list({a["topic"] for a in get_agreements_from_db(_conn, _run_id) if a.get("status") != "Superseded"})
    current_task_for_extraction = _get_current_task(state)
    owns_variables = current_task_for_extraction.get("owns_variables", [])
    extracted_items, transition = call_decision_extractor(state["chat_history"], existing_topics, target_role, owns_variables)
    print(f"\n------ 完了 ------")

    for item in extracted_items:
        action_type = item.get("action_type", "CREATE")
        entry_type = item.get("entry_type", "Decision") 
        status = item.get("status", "Proposed")
        topic = item.get("topic", "Unknown Topic")
        raw_content = item.get("content", "")
        rationale = item.get("rationale", "No reason provided")
        proposed_by = item.get("proposed_by", "Unknown")
        
        current_phase = state.get("current_phase", {})
        phase_id = item.get("phase_id", current_phase.get("phase_id", "unknown"))
        task_id = item.get("task_id") or state.get("current_task_id", "")
        abstraction_level = item.get("abstraction_level", "design")
        scope = item.get("scope", "local")
        time_axis = item.get("time_axis", "assumption")
        depends_on = item.get("depends_on", [])
        resource_claims = item.get("resource_claims", {})

        # BL-023 2.6節: owns_variablesに含まれる変数のみをverified_factsへ確定保存する
        owned_variable_values = item.get("owned_variable_values", {})
        if isinstance(owned_variable_values, dict):
            for var_name, var_value in owned_variable_values.items():
                if var_name in owns_variables:
                    upsert_verified_fact(
                        _conn, _run_id, var_name, var_value, unit="",
                        source_task_id=task_id, source_phase_id=phase_id,
                        confirmed_by=proposed_by
                    )
                    print(f"  🔒 [verified_facts] '{var_name}' = {var_value} を確定値として保存しました（source: {task_id}）。")

        # ===== 成果物のファイル書き出し処理 (バックアップ処理付き) =====
        content = "" # 初期化
        if entry_type == "Deliverable" and action_type == "CREATE":
            #content_to_save = raw_content
            if len(raw_content) > 200:
                content_to_save = raw_content
            else:
                content_to_save = state.get("expert_output", "")
            """
            # LLMがサボって短い要約しか出さなかった場合は直前のAgent出力をそのままバックアップ保存する
            if len(raw_content) < 200 and state.get("expert_output"):
                content_to_save = state["expert_output"]
                print(f"  ⚠️ [Decision Extractor] 成果物の抽出内容が短すぎるため、Agentの生出力を直接ファイルにバックアップ保存します。")
            """
            if content_to_save:
                filepath = save_deliverable_to_file(topic, content_to_save)
                content = f"FILE_PATH:{filepath}"
                print(f"  📁 [File Saved] 成果物 '{topic}' をファイルに保存しました: {filepath}")
            else:
                content = raw_content
        elif entry_type == "Deliverable" and action_type == "UPDATE":
             content = raw_content # この後保護処理が入る
        else:
            content = raw_content
        # ============================================

        if action_type == "UPDATE" or status == "Approved_with_Conditions":
            target_topic = item.get("target_topic", topic)
            old_content = ""
            for a in reversed(get_agreements_from_db(_conn, _run_id)):
                if a["topic"] == target_topic and a.get("status") != "Superseded":
                    old_content = a["decision_what"]
                    db_supersede_agreement(a["id"], _conn, _run_id)
                    if proposed_by == "Unknown" or not proposed_by:
                        proposed_by = a.get("proposed_by", "Unknown")
                    break
                    
            # --- 🛡️ ファイル上書き防止の鉄壁の保護 🛡️ ---
            if old_content.startswith("FILE_PATH:"):
                # もし新しいcontentが空文字、もしくは「FILE_PATH:」で始まらない短い文字列（要約や承認の言葉など）なら、古いファイルパスを引き継ぐ
                if not content or (not content.startswith("FILE_PATH:") and len(content) < 200):
                    content = old_content
                    print(f"  🔒 [File Protected] 成果物 '{target_topic}' のファイルパスを保護し、次ターンへ引き継ぎました。")
                elif not content.startswith("FILE_PATH:") and len(content) >= 200:
                    # 200文字以上の新しい本文が提示された場合は、新しいファイルとして保存して更新する
                    filepath = save_deliverable_to_file(target_topic, content)
                    content = f"FILE_PATH:{filepath}"
                    print(f"  📁 [File Updated] 成果物 '{target_topic}' の修正版を新しいファイルに保存しました: {filepath}")
            # -----------------------------------------------
            
            new_content = content if content else old_content
            if not new_content:
                new_content = "(状態のみ更新)"
            
            agreement: Agreement = {
                "id": f"AG-{int(time.time() * 1000)}",
                "turn": state["turn_count"],
                "action_type": "UPDATE",
                "entry_type": entry_type,
                "status": status,
                "topic": target_topic,
                "decision_what": new_content,
                "reason_why": rationale,
                "proposed_by": proposed_by,
                "phase_id": phase_id,
                "task_id": task_id,
                "abstraction_level": abstraction_level,
                "scope": scope,
                "time_axis": time_axis,
                "depends_on": depends_on,
                "resource_claims": resource_claims
            }
            db_append_agreement(agreement, _conn, _run_id)

            decision_log = make_decision(
                who="decision_extractor",
                what=f"合意更新[{status}]: {target_topic}",
                why=f"[{proposed_by}] {rationale}"
            )
            db_append_decision(decision_log, _conn, _run_id)

        else:
            agreement: Agreement = {
                "id": f"AG-{int(time.time() * 1000)}",
                "turn": state["turn_count"],
                "action_type": action_type,
                "entry_type": entry_type,
                "status": status,
                "topic": topic,
                "decision_what": content,
                "reason_why": rationale,
                "proposed_by": proposed_by,
                "phase_id": phase_id,
                "task_id": task_id,
                "abstraction_level": abstraction_level,
                "scope": scope,
                "time_axis": time_axis,
                "depends_on": depends_on,
                "resource_claims": resource_claims
            }
            db_append_agreement(agreement, _conn, _run_id)

            decision_log = make_decision(
                who="decision_extractor",
                what=f"新規抽出[{status}]: {topic}",
                why=f"[{proposed_by}] {rationale}"
            )
            db_append_decision(decision_log, _conn, _run_id)
        
        # 🌟 【ここが追加部分】 抽出結果をターミナルに綺麗にプリントする
        print(f"\n  📝 [Extract] {agreement['action_type']} - {agreement['entry_type']}: {agreement['topic']}")
        print(f"     ├ Status: {agreement['status']} | By: {agreement['proposed_by']}")
        print(f"     ├ Meta  : Phase={agreement['phase_id']} | Level={agreement['abstraction_level']} | Scope={agreement['scope']} | Time={agreement['time_axis']}")
        print(f"     ├ Reason: {agreement['reason_why']}")

    _resolve_task_transition(state, transition)

    if state["chat_history"]:
        last_user_msg = next((m["content"] for m in reversed(state["chat_history"]) if m["role"] == "user"), "")
        if "[PROJECT_COMPLETE]" in last_user_msg:
             print("\n🚩 User AI からプロジェクト完了宣言 [PROJECT_COMPLETE] を検知しました。QA審査へ移行します。")
             state["ready_for_review"] = True

    return state


def reflection_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Evaluation of the system's current state against its goals to determine continuation or termination conditions.
It generates a formal decision based on reflection results, updating the overall system lineage state.
    """
    risk_register = state.get("risk_register", [])
    print(f"\n------ [reflection] が思考中 ------")
    """
    result = call_reflection(
        state["goal"], 
        state["decisions"], 
        state["agreements"], 
        state["chat_history"], 
        state["turn_count"], 
        state["max_turns"], 
        state["constraint_issue_log"], 
        risk_register
    )
    """
    result = call_reflection(state, config)

    print(f"\n------ 完了 ------")
    state["discussion_status"] = result["discussion_status"]
    stop_reason_label = "継続中"
    if (result["discussion_status"] == "stagnant") or (not result["still_aligned"]):
        state["drift_flag"] = True
        stop_reason_label = "ゴール・ドリフト（目標逸脱）を検出"
    elif result["discussion_status"] == "stagnant":
        stop_reason_label = "議論の停滞を検出"
    elif result["discussion_status"] == "completed":
        stop_reason_label = "目標達成（完了）申告を検出"

    decision = make_decision(
        who="reflection",
        what=f"内省監査実行: aligned={result['still_aligned']}, status={result['discussion_status']}",
        why=f"【判定: {stop_reason_label}】 {result['note']}",
    )
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state

def facilitator_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Manages the discussion flow by periodically consulting a facilitator to guide conversation towards goals, enforcing a maximum iteration limit to prevent infinite loops.
    """
    
    state["facilitation_count"] += 1
    if state["facilitation_count"] > 3:
        state["halt"] = True
        decision = make_decision("system", "強制停止", "ファシリテーションの上限回数(3回)を超えても議論が改善されませんでした。")
        db_append_decision(decision, get_active_conn(), state["run_id"])
        return state

    print(f"\n------ [facilitator] が思考中 ------")
    feedback = call_facilitator(state["goal"], state["chat_history"], get_decisions_from_db(get_active_conn(), state["run_id"]))
    print(f"\n------ 完了 ------")
    
    if state["chat_history"] and state["chat_history"][-1]["role"] == "assistant":
        state["chat_history"][-1]["content"] += (
            f"\n\n---\n【ファシリテーターからの補足】\n{feedback}"
        )
        print(f"\n\n---\n【ファシリテーターからの補足】\n{feedback}")
    else:
        state["chat_history"].append({"role": "assistant", "content": feedback})
    
    state["drift_flag"] = False
    state["discussion_status"] = "continuing"
    return state

def verify_budget_arithmetic(text: str) -> list[str]:
    """【SLM要約】
    Validation of sectional budget calculations by summing individual line items and comparing the result against declared totals.
    """
    print(f"\n------ [verify_budget_arithmetic] 実行 ------")
    warnings = []
    sections = re.split(r'\n(?=#{1,4}\s|■|\*\*\d+\.)', text)
    
    item_pattern = re.compile(r'([^\n:：]+)[:：]\s*(?:約)?([\d,]+)万円')
    total_pattern = re.compile(r'合計[:：]\s*(?:約)?([\d,]+)万円')
    
    for section in sections:
        items = item_pattern.findall(section)
        totals = total_pattern.findall(section)
        if not items or not totals:
            continue
        item_sum = sum(int(amount.replace(',', '')) for label, amount in items if "合計" not in label)
        for total_str in totals:
            stated_total = int(total_str.replace(',', ''))
            if abs(item_sum - stated_total) > 10:
                warnings.append(
                    f"セクション内の内訳合計({item_sum}万円)と記載の合計({stated_total}万円)が一致しません"
                    f"（該当セクション冒頭: 「{section[:30].strip()}...」）"
                )
    return warnings


def integrator_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Aggregation and Lineage attribution of approved deliverables into a final master specification document, followed by contradiction checking.
    """
    print(f"\n------ [integrator] による成果物の物理結合と Lineage 付与 ------")
    _conn = get_active_conn()
    _run_id = state["run_id"]

    # DBから承認済みの「成果物(Deliverable)」をすべて抽出
    deliverables = [a for a in get_agreements_from_db(_conn, _run_id) if a["entry_type"] == "Deliverable" and a["status"] == "Approved"]
    
    if not deliverables:
        print("⚠️ 結合すべき成果物(Deliverable)が見つかりませんでした。")
        state["discussion_status"] = "stagnant"
        return state

    master_document = []
    master_document.append(f"# 【統合要件定義書】 {state['goal'].split(chr(10))[0]}\n")
    master_document.append("本ドキュメントは、AIエージェント間の議論・検証を経て生成された各タスクの成果物を統合し、意思決定のプロセス（Lineage）を付与した最終仕様書です。\n")
    master_document.append("---\n")

    for d in deliverables:
        # ===== ファイルから内容を読み込む =====
        content_data = d['decision_what']
        if content_data.startswith("FILE_PATH:"):
            filepath = content_data.split("FILE_PATH:")[1]
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    content_text = f.read()
            else:
                content_text = f"(⚠️ファイルが見つかりません: {filepath})"
        else:
            content_text = content_data
        # ==========================================

        master_document.append(f"## {d['topic']}\n")
        master_document.append(f"{content_text}\n")
        
        # Lineage (意思決定の由来) データの挿入
        master_document.append("\n### 💡 意思決定の由来 (Decision Lineage)\n")
        master_document.append(f"- **合意ID**: `{d['id']}` (Turn {d['turn']} に確定)")
        master_document.append(f"- **検討の背景と根拠**: {d.get('reason_why', '記載なし')}")
        if d.get("resource_claims"):
            master_document.append(f"- **関連リソース・制約**: {json.dumps(d['resource_claims'], ensure_ascii=False)}")
        master_document.append("\n---\n")
    
    final_text = "\n".join(master_document)
    
    # 統合したテキストをLLMに渡し、矛盾がないか最終チェックさせる
    result = call_integrator(state["goal"], final_text)
    
    if result.get("contradictions"):
        print(f"⚠️ [integrator] 成果物間に矛盾を検出しました: {result.get('details')}")
        state["needs_revision_phases"] = result.get("affected_phases", [])
        state["ready_for_review"] = False # 差し戻し
        db_append_decision(make_decision("integrator", "矛盾検知", result.get("details")), _conn, _run_id)
    else:
        print("✅ [integrator] 成果物間の矛盾なし。統合要件定義書をファイル保存・DB登録します。")
        
        # マスター文書もファイルに保存
        master_filepath = save_deliverable_to_file("★最終統合要件定義書（Lineage完全版）", final_text)

        # 矛盾がなければ、完成した統合ドキュメントをDBに登録
        db_append_agreement({
            "id": f"AG-MASTER-{int(time.time() * 1000)}",
            "turn": state["turn_count"],
            "action_type": "CREATE",
            "entry_type": "Deliverable",
            "status": "Proposed", # Reviewerの審査待ち
            "topic": "★最終統合要件定義書（Lineage完全版）",
            "decision_what": f"FILE_PATH:{master_filepath}", # パスを保存
            "reason_why": "全タスクの承認済み成果物を自動結合",
            "proposed_by": "System Integrator",
            "phase_id": "All",
            "abstraction_level": "constraint",
            "scope": "global",
            "time_axis": "current",
            "depends_on": [d["id"] for d in deliverables],
            "resource_claims": {}
        }, _conn, _run_id)
        db_append_decision(make_decision("integrator", "統合完了", f"全成果物を結合 (保存先: {master_filepath})"), _conn, _run_id)
        state["discussion_status"] = "completed"
    
    return state

def reviewer_node(state: LineageState) -> LineageState:
    """【SLM要約】
    QA review and validation of the final integrated requirements document, incrementing review counts and managing subsequent approval or revision cycles.
    """
    state["review_count"] += 1
    _conn = get_active_conn()
    _run_id = state["run_id"]
    master_doc_data = next((a["decision_what"] for a in reversed(get_agreements_from_db(_conn, _run_id)) if a["topic"] == "★最終統合要件定義書（Lineage完全版）"), "")
    
    # ===== ファイルから内容を読み込む =====
    if master_doc_data.startswith("FILE_PATH:"):
        filepath = master_doc_data.split("FILE_PATH:")[1]
        if os.path.exists(filepath):
            with open(filepath, "r", encoding="utf-8") as f:
                master_doc = f.read()
        else:
            master_doc = ""
    else:
        master_doc = master_doc_data
    # ==========================================

    if not master_doc:
        print("⚠️ [reviewer] 審査対象の統合要件定義書が見つかりません。")
        state["ready_for_review"] = False
        return state

    arithmetic_warnings = verify_budget_arithmetic(master_doc)
    print(f"\n------ [reviewer] が思考中 ------")
    result = call_reviewer(state["goal"], master_doc)
    print(f"\n------ 完了 ------")
    if arithmetic_warnings:
        result["passed"] = False
        result["feedback"] = (result.get("feedback", "") + 
            "\n【機械検算による警告】\n" + "\n".join(arithmetic_warnings))
    
    if result["passed"]:
        state["is_completed"] = True
        decision = make_decision("reviewer", "最終成果物の承認 (Passed)", result.get("reasoning", "QA審査を通過しました。"))
        db_append_decision(decision, _conn, _run_id)
    else:
        if state["review_count"] > 3:
            state["halt"] = True
            decision = make_decision("system", "強制停止", "QAからの差し戻し上限回数(3回)に達しました。プロジェクトは失敗として終了します。")
            db_append_decision(decision, _conn, _run_id)
        else:
            state["ready_for_review"] = False
            feedback = result["feedback"]
            added_turns = 5
            state["max_turns"] += added_turns
            state["discussion_status"] = "continuing"

            msg = f"🔥 【QA責任者からの差し戻し (リテイク {state['review_count']}/3) - 延長戦突入】\n{feedback}\n※仕様の矛盾やバグを修正してください。制限ターンが {added_turns} ターン延長されました。"
            state["chat_history"].append({"role": "user", "content": msg})

            decision = make_decision("reviewer", f"成果物の差し戻し (Needs Fix) -> {added_turns}ターン延長", feedback)
            db_append_decision(decision, _conn, _run_id)

    return state

def halt_node(state: LineageState) -> LineageState:
    """【SLM要約】
    System shutdown initiation by logging a definitive halt decision within the lineage state.
    """
    decision = make_decision(who="system", what="処理を完全停止", why="条件を満たしたためシステムをHaltします。")
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state


# ---------------------------------------------------------------------------
# 5. 分岐ロジック & グラフ構築
# ---------------------------------------------------------------------------

def build_graph():
    """【SLM要約】
    Construction of the core state machine graph, defining all processing nodes (e.g., planners, detectors, experts) and their execution flow within the system.
    """
    graph = StateGraph(LineageState)
# 1. ノードの登録（★関数は同じものを使い回し、名前で役割を分ける）
    graph.add_node("task_planner", task_planner_node)
    graph.add_node("generate_user_utterance", generate_user_utterance_node)
    
    # User AI用の監視と抽出
    graph.add_node("user_detector", detector_node)
    graph.add_node("user_decision_extractor", decision_extractor_node) 
    
    graph.add_node("orchestrator", orchestrator_node)
    graph.add_node("expert", expert_node)
    
    # Expert AI用の監視と抽出
    graph.add_node("expert_detector", detector_node)
    graph.add_node("expert_decision_extractor", decision_extractor_node) 
    
    # その他
    graph.add_node("reflection", reflection_node)
    graph.add_node("facilitator", facilitator_node)
    graph.add_node("integrator", integrator_node)
    graph.add_node("arbiter", arbiter_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("halt", halt_node)

    # ---------------------------------------------------------
    # エッジの接続とルーティング
    # ---------------------------------------------------------
    # ---------------------------------------------------------
    #  User AI 側の意思抽出後の分岐（★ここを新規作成）
    # ---------------------------------------------------------
    graph.set_entry_point("task_planner")
    graph.add_edge("task_planner", "generate_user_utterance")
    graph.add_edge("generate_user_utterance", "user_detector")

    # --- ① User AI 直後の Detector 分岐 ---
    def route_after_user_detector(state: LineageState):
        """【SLM要約】
        Deciding the next processing step based on user detector output, escalating to "reflection" after three retries due to constraint issues or halting.
Otherwise, routing to "user_decision_extractor."
        """
        if state.get("constraint_issue") in ("major") or state.get("halt"):
            if state.get("user_retry_count", 0) >= 3:
                print("\n[route_after_user_detector]------ ユーザーAIの差し戻し上限に達しました。reflectionに渡します ------\n")
                state["user_retry_count"] = 0 # カウンターをリセット
                return "reflection" # 上限に達した場合はリフレクションに渡す

            print("\n[route_after_user_detector]------ ユーザーAIに差し戻します ------\n")
            return "generate_user_utterance" # UserのミスはUserにやり直させる
        
        print("\n[route_after_user_detector]------ user_decision_extractorに渡します ------\n")
        return "user_decision_extractor"

    graph.add_conditional_edges(
        "user_detector", route_after_user_detector,
        {"generate_user_utterance": "generate_user_utterance", "user_decision_extractor": "user_decision_extractor", "reflection": "reflection"}
    )

    # Userの意図抽出後は Orchestrator(専門家選定) へ
    def route_after_user_decision(state: LineageState):
        """【SLM要約】
        Determines the next system step after a user decision, directing flow to 'halt', 'integrator' for review, or 'orchestrator' for further processing.
        """
        if state.get("halt"): 
            print("\n[route_after_user_decision]------ !!! Halt !!! ------\n")
            return "halt"
            
        # ★ User AIが「完了宣言」を出した場合は、エージェントを呼ばずに直接Integratorへ
        if state.get("ready_for_review"):
            print("\n[route_after_user_decision]------ レビューの準備が整いました ------\n")
            return "integrator" 
            
        # 通常の指示であれば、Orchestrator（専門家選定）へ進む
        return "orchestrator"

    # user_decision_extractorからの遷移を条件付きに変更
    graph.add_conditional_edges(
        "user_decision_extractor", 
        route_after_user_decision,
        {
            "halt": "halt", 
            "integrator": "integrator", 
            "orchestrator": "orchestrator"
        }
    )



    graph.add_edge("orchestrator", "expert")
    graph.add_edge("expert", "expert_detector")
    #graph.add_edge("expert_detector", "expert_decision_extractor") 

    # ---------------------------------------------------------
    # Expert AI 側の意思抽出後の分岐（★Integratorを削除してスッキリ）
    # ---------------------------------------------------------

    # --- ② Expert AI 直後の Detector 分岐 ---
    def route_after_expert_detector(state: LineageState):
        """【SLM要約】
        Manages the flow after expert detection based on constraint issues or halt conditions, routing back to 'expert' if retries are low, and to 'reflection' upon reaching retry limits.
        """
        if state.get("constraint_issue") in ("major") or state.get("halt"):
            if state.get("expert_retry_count", 0) >= 3:
                print("\n[route_after_expert_detector]------ エキスパートAIの差し戻し上限に達しました。reflectionに渡します ------\n")
                state["expert_retry_count"] = 0 # カウンターをリセット
                return "reflection" # 上限に達した場合はリフレクションに渡す
            
            print("\n[route_after_expert_detector]------ エキスパートAIに差し戻します ------\n")
            return "expert" # ExpertのミスはExpertにやり直させる
        # 2. 初回実行時（まだフェーズ計画が作られていない、もしくは turn_count が 0 などの場合）
        # ※ state の中にプランを保持するキー（例: 'phases' など）がある場合の判定例です
        #if not state.get("current_phase") or state.get("turn_count", 0) == 0:
        #    return "task_planner"
            
        # 3. 通常時（監査クリア）は意思決定の抽出へ
        print("\n[route_after_expert_detector]------ expert_decision_extractorに渡します ------\n")
        return "expert_decision_extractor"
            
    graph.add_conditional_edges(
        "expert_detector", route_after_expert_detector,
        {"expert": "expert", "expert_decision_extractor": "expert_decision_extractor", "reflection": "reflection"}
    )



    # --- ③ ターン終了の判定（Expertの処理完了後） ---
    def route_after_expert_decision(state: LineageState):
        """【SLM要約】
        Decision routing logic determining the next system state (halt, reflection, or user turn) following expert evaluation.
        """
        if state["halt"]: 
            print("\n[route_after_expert_decision]------ !!! Halt !!! ------\n")
            return "halt"
        
        # リフレクションのタイミング
        if state["turn_count"] > 0 and state["turn_count"] % state["reflection_interval"] == 0:
            print("\n[route_after_expert_decision]------ リフレクションのタイミングになりました ------\n")
            return "reflection"
        
        # ★次ターンの開始（User AIへ手番を戻す！）
        print("\n[route_after_expert_decision]------ 次ターンの開始 ------\n")
        return "generate_user_utterance" 

    graph.add_conditional_edges(
        "expert_decision_extractor", route_after_expert_decision,
        {"halt": "halt", "reflection": "reflection", "generate_user_utterance": "generate_user_utterance"}
    )


    def route_after_reflection(state: LineageState):
        """【SLM要約】
        Determining the next state transition after a "reflection" step based on current system status flags and discussion outcomes.
        """
        if state["halt"]: 
            print("\n[route_after_reflection]------ !!! Halt !!! ------\n")
            return "halt"
        
        # 完了宣言が出た場合は、すぐにIntegratorへ
        if state.get("ready_for_review"):
            print("\n[route_after_reflection]------ integratorに渡します(ready_for_review) ------\n")
            return "integrator"
            
        if state["discussion_status"] == "stagnant" or state["drift_flag"]:
            print("\n[route_after_reflection]------ ファシリテーターに渡します ------\n")
            return "facilitator"
        
        if state["discussion_status"] == "completed":
            print("\n[route_after_reflection]------ integratorに渡します(completed) ------\n")
            return "integrator"
        return "end_turn"

    graph.add_conditional_edges(
        "reflection",
        route_after_reflection,
        {"halt": "halt", "integrator": "integrator", "facilitator": "facilitator", "end_turn": END}
    )

    def route_after_integrator(state: LineageState):
        """【SLM要約】
        Decision point determining subsequent workflow based on the lineage state, routing to "orchestrator" if revisions are needed or "arbiter" otherwise.
        """
        if state.get("needs_revision_phases"):
            print("\n[route_after_integrator]------ revisionが必要です ------\n")   
            return "orchestrator"
        return "arbiter"

    graph.add_conditional_edges(
        "integrator",
        route_after_integrator,
        {"orchestrator": "orchestrator", "arbiter": "arbiter"}
    )

    def route_after_arbiter(state: LineageState):
        """【SLM要約】
        Determining the next workflow step ("orchestrator" or "reviewer") based on whether revisions are required after arbitration.
        """
        if state.get("phases_to_revise"):
            print("\n[route_after_arbiter]------ revisionが必要です ------\n")
            return "orchestrator" 
        return "reviewer"

    graph.add_conditional_edges(
        "arbiter",
        route_after_arbiter,
        {"orchestrator": "orchestrator", "reviewer": "reviewer"}
    )

    def route_after_facilitator(state: LineageState):
        """【SLM要約】
        Decision point following the 'facilitator' state, determining flow to either 'halt' or proceeding to the next turn ('end_turn').
        """
        if state["halt"]: 
            print("\n[route_after_facilitator]------ !!! Halt !!! ------\n")
            return "halt"
        print("\n[route_after_facilitator]------ 次ターンの開始 ------\n")
        return "end_turn"
        
    graph.add_conditional_edges(
        "facilitator",
        route_after_facilitator,
        {"halt": "halt", "end_turn": END}
    )

    def route_after_reviewer(state: LineageState):
        """【SLM要約】
        Determining the next state transition after a review step, directing flow to halt, end, or continue orchestration.
        """
        if state["halt"]: 
            print("\n[route_after_reviewer]------ !!! Halt !!! ------\n")
            return "halt"
        if state.get("is_completed"): 
            print("\n[route_after_reviewer]------ レビュー完了(is_completed) ------\n")
            return "end"
        print("\n[route_after_reviewer]------ 次のターンへ進む ------\n")
        return "orchestrator"
        
    graph.add_conditional_edges(
        "reviewer",
        route_after_reviewer,
        {"halt": "halt", "end": END, "orchestrator": "orchestrator"}
    )
    
    graph.add_edge("halt", END)
    return graph.compile()

# ---------------------------------------------------------------------------
# 6. AI vs AI 実行用ループ
# ---------------------------------------------------------------------------

def run_ai_vs_ai_loop(target_goal: str, config: Appconfig, db_path: str = "cela.db"):
    """【SLM要約】
    Orchestration of an iterative, goal-driven dialogue loop where multiple AIs collaborate to refine a solution based on predefined constraints and state management.
    SQLite接続（run単位のシングルトン）を初期化し、ループ終了時に必ずクローズする（R1、設計書§3.6.1準拠）。
    """
    global _DB_CONN

    app = build_graph()

    #user_always_remembers = pattern in (3, 4)
    #agent_has_guardrail = pattern in (2, 4)

    run_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
    reset_call_seq()
    if REPLAY_MODE == "replay":
        _replay_fixtures.update(_load_replay_fixtures(_REPLAY_FIXTURE_PATH))
    elif REPLAY_MODE == "record" and _REPLAY_FIXTURE_PATH and os.path.exists(_REPLAY_FIXTURE_PATH):
        # 強制終了後の再起動はrun全体を最初から再実行するため、前回分をマージせず退避してから新規に記録する
        backup_path = f"{_REPLAY_FIXTURE_PATH}.bak-{int(time.time())}"
        os.replace(_REPLAY_FIXTURE_PATH, backup_path)
        print(f"⚠️ [RECORD] 既存のfixtureファイルを {backup_path} に退避しました（前回記録の上書き消失を防止）。")

    _DB_CONN = get_db_connection(db_path)
    init_db(_DB_CONN)

    state: LineageState = {
        "goal": target_goal,
        "user_input": "",
        "current_task_summary": "",
        "selected_expert": "",
        "expert_output": "",
        "run_id": run_id,
        "db_path": db_path,
        "chat_history": [],
        "turn_count": 0,
        "max_turns":  config["initial_max_turnval"],
        "reflection_interval": config["reflection_interval"],
        "risk_flag": "low",
        "drift_flag": False,
        "halt": False,
        "agent_has_guardrail": config["agent_has_guardrail"],
        "discussion_status": "continuing",
        "is_stateless_mode": config["is_stateless_mode"],
        "facilitation_count": 0,
        "review_count": 0,
        "is_completed": False,
        "ready_for_review": False,
        "constraint_issue": "none",
        "constraint_issue_log": [],
        "global_constraints": [],
        "phases": [],
        "current_phase": {
            "phase_id": "phase_0",
            "title": "初期化待ち",
            "description": "",
            "allowed_abstraction_levels": ["concept", "constraint", "design", "impl"],
            "focus_scope": "global",
            "expected_time_axis": "assumption",
            "tasks": [],
            "budget_hint": {}
        },
        "current_task_id": "",
        "verified_facts": {},
        "task_criteria_status": {},
        "expert_last_python_calls": [],
        "risk_register": [],
        "needs_revision_phases": [],
        "phases_to_revise": []
    }

    mode_str = "【ステートレス（決定事項DBによる知識永続化）】" if config["is_stateless_mode"] else "【ステートフル（生ログ全蓄積）】"

    try:
        print("============================================================")
        print(f"🚀 Lineage Orchestrator: シナリオ検証  - DB+QAレビュー＆介入強化版")
        print(f"⚙️ 実行モード: {mode_str}")
        print(f"🎯 共通目標:\n{target_goal}")
        print(f"⏳ 初期設定ターン数: {config["initial_max_turnval"]} ターン制限")
        print("============================================================")

        current_turn = 1
        while current_turn <= state["max_turns"]:
            print(f"\n\n{'='*60}")
            print(f"🔷 [Turn {current_turn} / {state['max_turns']}]")
            print(f"{'='*60}")

            #print("\n👤 User AI が思考中...")
            #user_input = generate_user_utterance(target_goal, state["chat_history"], state["agreements"], current_turn, user_always_remembers, state["max_turns"], is_stateless_mode)
            #print(f"\n>>> 👤 User AIの発言:\n{user_input}")

            #state["user_input"] = user_input
            state["turn_count"] = current_turn
            prev_decision_count = len(get_decisions_from_db(_DB_CONN, run_id))

            #print("\n🤖 Agent AI が思考中...")
            state = app.invoke(state)

            #print("\n--- 🧠 Agent AIの内部思考プロセス (Decision Lineage & Extracted Agreements) ---")

            this_turn_decisions = get_decisions_from_db(_DB_CONN, run_id)[prev_decision_count:]

            for d in this_turn_decisions:
                if d["who"] == "orchestrator":
                    print(f"  [orchestrator]")
                    print(f"   -what: {d['what']}")
                    print(f"   -why: {d['why']}")
                    break

            for d in this_turn_decisions:
                if d['who'] == 'orchestrator':
                    continue
                elif d['who'] == 'decision_extractor':
                    print(f"  ✨ [DB登録] {d['what']} ({d['why']})")
                else:
                    """
                    print(f"  [{d['who']}]")
                    print(f"    - what: {d['what']}")
                    print(f"    - why: {d['why']}")
                    """
                if d['who'] == 'reviewer' and "差し戻し" in d['what']:
                    print("\n🔥 ＞＞ QA責任者からの差し戻し（延長戦突入）が発動しました！ ＜＜")
                elif d['who'] == 'facilitator':
                    print("\n⚠️ ＞＞ ファシリテーターによる軌道修正の提案が発動しました！ ＜＜")

            if state.get("is_completed"):
                print("\n🎉 [SUCCESS] QAの最終審査を通過し、議論と成果物が承認されました！自律ループを終了します。")
                break

            if state["halt"]:
                print(f"\n🚨 [HALT] システム停止シグナルが送信されました。 (ステータス: {state['discussion_status']})")
                break

            current_turn += 1

        print("\n============================================================")
        print(f"🏁 評価ループが終了しました。 {mode_str})")
        print("============================================================")
    finally:
        _DB_CONN.close()
        _DB_CONN = None


if __name__ == "__main__":
    # カスタムロガーを標準出力に設定（importのみでは発火させない。BL-027）
    sys.stdout = MultiLogger()

    TARGET_GOAL = (
        "過疎地域向け「AIオンデマンド自動運転バス」の導入計画と安全基準策定\n"
        "1. 初期導入予算は「上限1億円」、年間維持費（ランニングコスト）は「上限3,000万円」とする。\n"
        "自動運転バス車両は1台あたり2,500万円。遠隔監視システムの構築費や、遠隔監視オペレーター（最低2名常駐）の人件費、車両のメンテナンス費もすべてこの予算内で賄うこと。\n"
        "利用料金は「1乗車一律200円」とし、住民の負担を最小限に抑えること。\n"
        "2. 【ターゲット層とUXの制約】\n"
        "対象地域の住民の70%が65歳以上の高齢者であり、スマートフォンの所持率は30%未満である。\n"
        "オンデマンド配車の「予約手段」として、スマホアプリ以外の代替手段を必ず用意すること。\n"
        "予約から乗車までの「最大待ち時間」は、いかなる場合でも30分以内を死守すること。\n"
        "3. 【安全基準と法規制】\n"
         "運行ルートの15%は「冬季（12月〜2月）に積雪・凍結が発生する勾配のある山間部」である。\n"
         "また、ルート全体の約5%に「携帯キャリアの通信（4G/5G）が一時的に途切れる不安定なエリア」が存在する。\n"
         "自動運転レベル4（特定条件下での無人運転）を想定し、これらの環境下でどう運行を維持するのか、あるいは運休するのかの基準を明確にすること。\n"
         "4. 【異常時のエッジケースと法的責任】\n"
         "以下の2つのエッジケースについて、システム上のフェールセーフ（安全装置）の挙動と、責任分界点（事故・トラブル時の責任は「自治体」「システム開発会社」「遠隔オペレーター」の誰にあるか）をマニュアルに明記すること。\n"
         "ケースA: 走行中に通信障害エリアに入り、遠隔監視センターとの通信が完全にロストした場合。\n"
         "ケースB: 雪でセンサーが誤作動し、車両が立ち往生している際に、後続の一般車両に追突された場合。\n"
         "【付帯情報】対象地域「水ノ守（みずのもり）町」の基本データ\n"
         "1. 人口・交通動態\n"
         "想定利用人口（町全体の人口）: 5,000人\n"
         "高齢者（65歳以上）: 3,500人（70%） ※うち単身世帯が約4割\n"
         "現役世代・子供: 1,500人（30%）\n"
         "想定乗車密度（1日の予測総乗車数）: 約 400人 / 日\n"
         "ピークタイム（午前8:00〜11:00：通院・買い物）: 約200人（集中発生）\n"
         "オフピーク（午後12:00〜17:00）: 約150人\n"
         "夜間（17:00〜20:00：通勤・通学帰り）: 約50人\n"
         "※20:00〜翌朝8:00までは運行外とする。\n"
         "2. 地理・インフラ環境\n"
         "総面積: 約 50平方キロメートル（一般的な地方の過疎盆地エリア）\n"
         "主要拠点（運行の起点・終点となる場所）:\n"
         "【中心部】町立総合病院（高齢者の目的地NO.1）\n"
         "【中心部】大型スーパー・役場周辺（商業・行政の中心）\n"
         "【地方部】山間部集落（中心部から片道約 12km、ここに積雪・通信障害エリアが存在）\n"
         "移動速度の前提:\n"
         "信号が少ない平坦な道では平均時速 40km/h、勾配のある山間部では平均時速 20km/h とする。\n"
         "3. 経営環境（自治体の財政補填限界）\n"
         "水ノ守町は財政健全化団体の一歩手前であり、前述の「年間維持費上限3,000万円（実質的な自治体からの最大補助金）」を1円でも超える予算案は、議会で絶対に承認されない。\n"
         "運賃収入の試算（参考数値）:\n"
         "400人×200円＝80,000円/日。年間300日稼働として、年間運賃収入は最大でも 2,400万円。\n"
         "したがって、年間の「総運行コスト」から「運賃収入（2,400万円）」を引いた「実質赤字額」が、自治体補助金（3,000万円）の枠内に収まる必要がある。\n"
         "実質赤字額 ＝（オペレーター人件費＋システム維持費＋電気代/燃料代＋車検メンテ費等）－ 2,400万円 ≦ 3,000万円\n"
    )

    config : Appconfig = {
        "pattern":  4,
        "is_stateless_mode": True,
        "initial_max_turnval": 30,
        "reflection_interval": 3,
        "target_goal": TARGET_GOAL,
        "user_always_remember": True,
        "agent_has_guardrail" : True,
        "chat_history_window": 4,
        "expert_history_window": 10
    }

    run_ai_vs_ai_loop(
        target_goal=TARGET_GOAL,
        config= config
    )