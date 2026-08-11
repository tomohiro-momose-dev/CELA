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
import unicodedata
import difflib
import math  # [BL-204] verify_entity_geoの座標乖離の概算に使用
import ast
import subprocess
import threading
from typing import Annotated, Literal, TypedDict
from pathlib import Path

def _take_latest(a, b):
    """【SLM要約】
    Selection of the second provided input (`b`) as the resulting state, effectively prioritizing newer or subsequent data.
    """
    return b
import re
from unittest import result

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.checkpoint.base import BaseCheckpointSaver
import httpx
from openai import OpenAI
from openai import APIError, APIConnectionError, RateLimitError, APITimeoutError

# [BL-184] cela_main.pyの肥大化を避けるため、web_search/web_fetch/read_reference_fileの
# Provider抽象化・SSRF検証・HTML抽出・キャッシュ管理・ハンドラ本体は独立モジュールへ切り出す
# （web_tools.py側はcela_main.pyを一切importしない、循環import回避）。
import geo_tools
import web_tools


# [BL-175] ログ・checkpoint双方の時刻表示を日本時間（JST、UTC+9）へ統一する。
# 実行環境のOSローカルタイムゾーン設定に依存せず、常に同じ時刻表示になるよう明示的に指定する。
JST = datetime.timezone(datetime.timedelta(hours=9), name="JST")


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
        # [BL-175] OSローカルタイムゾーンに依存せず常にJSTでログ時刻を記録する。
        now = datetime.datetime.now(JST)

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
        
        start_msg = f"# Execution Log Started at: {now.strftime('%Y-%m-%d %H:%M:%S')} JST\n\n"
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
        # [UX] ファイルはデフォルトでブロックバッファリングされ、ある程度書き込みが
        # 溜まらないとディスクに反映されない（ターミナル表示とログファイルの内容が
        # ずれて見える原因）。streamingの逐次printも含め毎回のwrite()直後にflushし、
        # ターミナル表示とほぼ同期させる（頻度は高いが、対話的なドライラン用途では
        # 性能より即時性を優先する）。
        if self.is_prompt_mode:
            self.file_with_prompt.write(message)
            self.file_with_prompt.flush()
        else:
            self.terminal.write(message)
            self.terminal.flush()
            self.file_with_prompt.write(message)
            self.file_with_prompt.flush()
            self.file_no_prompt.write(message)
            self.file_no_prompt.flush()

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
    Serialization of final outputs into versioned, sanitized Markdown files within the system's log directory.
    """
    """成果物をMarkdownファイルとしてlogディレクトリ内に保存し、そのパスを返す。
    ★修正（BL-040）: ファイル名をUnixタイムスタンプ付き（例: topic_1784643517.md）から
    `topic_V{n}.md`のバージョン連番方式に変更した。タイムスタンプはAIが事前に予測できず
    read_deliverable_fileの発見不能性の一因になっていたため、予測可能な連番にすることで
    (1)AIが最新版のファイル名を推測しやすくする、(2)旧版はdeliverables/old/へ退避し
    現行ディレクトリを最新版のみに保つ、の両方を狙う。バージョン番号はファイルシステム上の
    既存ファイル（deliverables/・deliverables/old/の両方）を走査して次の番号を採番する。
    """
    safe_topic = re.sub(r'[\\/*?:"<>|]', "_", topic).strip()
    if not safe_topic:
        safe_topic = "deliverable"
    safe_topic = safe_topic[:50] # 長すぎるファイル名を防止

    log_dir = getattr(MultiLogger, "log_dir", "log")
    deliv_dir = os.path.join(log_dir, "deliverables")
    old_dir = os.path.join(deliv_dir, "old")
    os.makedirs(deliv_dir, exist_ok=True)

    version_pattern = re.compile(rf"^{re.escape(safe_topic)}_V(\d+)\.md$")
    existing_versions = [0]
    for d in (deliv_dir, old_dir):
        if os.path.isdir(d):
            for name in os.listdir(d):
                m = version_pattern.match(name)
                if m:
                    existing_versions.append(int(m.group(1)))
    next_version = max(existing_versions) + 1

    filename = f"{safe_topic}_V{next_version}.md"
    filepath = os.path.join(deliv_dir, filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)
    return filepath


def _archive_old_deliverable_file(file_path: str) -> None:
    """[BL-040] Deliverableが新版に置き換わる際、旧版ファイルをdeliverables/old/へ退避する。
    旧版が既に存在しない・退避先に同名衝突がある等の異常はデータ損失を避けるため無視して継続する
    （成果物の整合性はDBのagreements.decision_whatが正であり、ファイルはあくまで補助資料のため）。
    """
    if not file_path or not os.path.isfile(file_path):
        return
    old_dir = os.path.join(os.path.dirname(file_path), "old")
    try:
        os.makedirs(old_dir, exist_ok=True)
        dest = os.path.join(old_dir, os.path.basename(file_path))
        if os.path.exists(dest):
            return
        os.replace(file_path, dest)
        print(f"  🗄️ [File Archived] 旧版を退避しました: {dest}")
    except OSError as e:
        print(f"  ⚠️ [File Archive Failed] 旧版の退避に失敗しました（無視して続行）: {e}")


# ===========================================================================
# 一時停止・再開（チェックポイント）
# ===========================================================================
# [BL-105/D-086 Tier1] 自前JSON checkpoint（_save_checkpoint/_load_checkpoint、--resume <path>）は
# 廃止し、LangGraph公式のcheckpointer（SqliteSaver）+ thread_id（==run_id）ベースの再開へ移行した。
# 旧方式は--resume時に必ずentry_point（goal_essence）からapp.stream()を再実行しており、
# generate_user_utterance_nodeに再入場ガードが無いため、ラウンド途中で一時停止したものを
# 再開すると必ずuser発言が二重に積まれる欠陥があった（BL-105）。SqliteSaverはノード完了ごとに
# 自動的に状態を永続化し、thread_idへNoneを入力してstream/invokeすることで「中断した直後の
# ノードから」再開できる（entry_pointの全体再走行にはならない）。checkpointer実体・resume分岐の
# 実装本体はrun_ai_vs_ai_loop（下部）を参照。設計の詳細はdocs/design/back_log/BL-105/
# BL105_basic_design.md。
#
# [CONSTRAINT] ノード**内部**（Expert/Detector等の_query_AI_liveツールループの途中）での
# Ctrl+Cには対応できない（LangGraph公式ドキュメントにも明記された制約）。そのノードは
# 中断前の内容を含めて最初から再実行される。これはTier1導入前後で変わらない既知の挙動であり、
# 新規の後退ではない。真に解消するにはノード内部を@taskへ分解するTier2が必要だが、今回は
# 意図的にスコープ外とした（将来ヒューマンインザループ機能を具体設計する際に着手する方針）。
CELA_CHECKPOINT_DB_PATH = "cela_checkpoints.db"


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
deepseek_v4_flash = "deepseek-v4-flash-0731"
nemotron_3_super = "nemotron-3-super-120b-a12b:free"
nemotron_3_ultra = "nemotron-3-ultra-550b-a55b:free"
gpt_5_6_luna = "gpt-5.6-luna"
ling_3_flash = "ling-3.0-flash:free"
laguna_S_2_1 ="laguna-s-2.1:free"
mimo_2_5 = "mimo-v2.5"
hy3 = "tencent/hy3"
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
model_user = laguna_S_2_1

# [BL-189] 従来はExpert/Orchestratorがclient_agent/model_agentを、Task Planner/Detector（両パス）/
# Decision Extractor/Resource Arbiter/Reflection/Facilitator/Integrator/Reviewer QA/
# Goal Essence Analyst/Task Plan Reviewerの計10ノードがclient_auditor/model_auditor1本を
# 共有していたため、ノード単位でモデルを使い分けたくても不可能だった。ここから下はノードごとに
# 個別の変数を持たせ、各query_AI呼び出し箇所（call_task_planner等）はそれぞれ専用の変数を参照する。
# デフォルトは全ノードとも従来通りnemotron_3_ultra/client_openrouterのままなので、挙動は変わらない。
# ノードごとに変えたい場合は、該当行のclient/model値だけを書き換えればよい。
client_orchestrator = client_openrouter
model_orchestrator = laguna_S_2_1

client_expert = client_openrouter
model_expert = nemotron_3_ultra

client_task_planner = client_openrouter
model_task_planner = nemotron_3_ultra

client_task_plan_reviewer = client_openrouter
model_task_plan_reviewer = nemotron_3_ultra

client_detector_domain = client_openrouter
model_detector_domain = nemotron_3_ultra # nemotron_3_ultra

client_detector_numeric = client_openrouter
model_detector_numeric = nemotron_3_ultra

client_decision_extractor = client_openrouter
model_decision_extractor = laguna_S_2_1

client_resource_arbiter = client_openrouter
model_resource_arbiter = laguna_S_2_1 #nemotron_3_ultra

client_reflection = client_openrouter
model_reflection = nemotron_3_ultra

client_facilitator = client_openrouter
model_facilitator = nemotron_3_ultra

client_integrator = client_openrouter
model_integrator = laguna_S_2_1 #nemotron_3_ultra

client_reviewer_qa = client_openrouter
model_reviewer_qa = laguna_S_2_1 #nemotron_3_ultra

client_goal_essence = client_openrouter
model_goal_essence = laguna_S_2_1 #nemotron_3_ultra

LOW_TEMP_LABEL_KEYWORDS = ("detector", "reflection", "review", "decision extractor", "summarizer")
# JSON厳密出力が必要なノードのラベル（部分一致）
STRUCTURED_OUTPUT_LABEL_KEYWORDS = ("detector", "decision extractor", "reflection", "review", "orchestrator")


MAX_TOKENS_BY_ROLE = {
    "expert": 100000,
    "user": 100000,
    "detector": 100000,
    "reflection": 100000,
    "review": 100000,
    "decision extractor": 100000,
    "orchestrator": 100000,
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
# itertools/functools/collections/operator/re はBL-058で追加（AGENTS.md§7承認済み変更）。
# いずれもI/O・ファイルシステム・OS・ネットワークアクセスを一切持たない純粋計算・データ構造
# ユーティリティであり、既存のサブプロセス分離＋AST危険呼び出し検査のサンドボックス境界を
# 拡張しない（組合せ探索的な検算でitertoolsが必要になった実機ドライラン、log/2026-07-23/1256）。
_ALLOWED_IMPORTS = {
    "math", "statistics", "datetime", "json", "fractions", "decimal",
    "itertools", "functools", "collections", "operator", "re",
}

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
                    print(f"  🚫 [python_repl safety] import '{alias.name}'を拒否しました（許可リスト外）。")
                    return f"[REPL Error] import of '{alias.name}' is not allowed"
        elif isinstance(node, ast.ImportFrom):
            if node.module and node.module.split(".")[0] not in _ALLOWED_IMPORTS:
                print(f"  🚫 [python_repl safety] import from '{node.module}'を拒否しました（許可リスト外）。")
                return f"[REPL Error] import from '{node.module}' is not allowed"
        elif isinstance(node, ast.Name) and node.id in _DANGEROUS_NAMES:
            print(f"  🚫 [python_repl safety] 危険な名前'{node.id}'の使用を拒否しました。")
            return f"[REPL Error] use of '{node.id}' is not allowed"
        elif isinstance(node, ast.Attribute) and node.attr in _DANGEROUS_NAMES:
            print(f"  🚫 [python_repl safety] 危険な属性'.{node.attr}'の使用を拒否しました。")
            return f"[REPL Error] use of '.{node.attr}' is not allowed"
        elif isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name) and node.func.id in _DANGEROUS_NAMES:
                print(f"  🚫 [python_repl safety] 危険な呼び出し'{node.func.id}(...)'を拒否しました。")
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
            print(f"  ⏱️ [python_repl] タイムアウト（{self._timeout}秒）のためREPLセッションを強制終了・リセットしました。")
            self.close()
            return (
                f"[REPL Error] execution exceeded {self._timeout}s timeout. "
                "The REPL session has been reset — variables defined in earlier "
                "calls no longer exist; redefine what you need in your next call."
            )

        if proc.poll() is not None:
            # 子プロセスが応答なく終了していた場合も同様にセッションを再構築する。
            print(f"  ⚠️ [python_repl] 子プロセスが予期せず終了しました（code={proc.poll()}）。セッションをリセットします。")
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
            "print() — retry with print() instead of repeating the same bare expression. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
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

# [F-3.8] R3a: 読み取り専用ツール定義
READ_VERIFIED_FACT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_verified_fact",
        "description": (
            "Search verified facts (confirmed values) across ALL phases. "
            "You can search by variable name (e.g. 'vehicle_count') or by topic keyword. "
            "Returns the value, reason, citations, and confidence level. "
            "Use this to access cross-phase dependencies that are not in your current phase's scope. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "variable_name": {
                    "type": "string",
                    "description": "Exact variable name to search for (e.g. 'vehicle_count', 'annual_operating_cost')"
                },
                "topic_keyword": {
                    "type": "string",
                    "description": "Topic keyword for fuzzy search (e.g. '車両', '予算', '需要')"
                }
            }
        }
    }
}

READ_DELIVERABLE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_deliverable_file",
        "description": (
            "Read a deliverable file for a previous task's output (for cross-phase integration). "
            "Deliverable filenames include an unpredictable timestamp suffix, so guessing "
            "file_path directly will usually fail with not_found. "
            "Prefer task_id or topic_keyword: the tool will look up the actual saved file path "
            "from the agreements database for you. Only pass file_path if you already have the "
            "exact path (e.g. copied verbatim from a 'FILE_PATH:...' value shown elsewhere). "
            "Returns the file content as text. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "task_id that produced the deliverable (e.g. 'task_1_1'). Preferred lookup method."
                },
                "topic_keyword": {
                    "type": "string",
                    "description": "Topic keyword for fuzzy search (e.g. '車両', '予算') if task_id is unknown."
                },
                "file_path": {
                    "type": "string",
                    "description": "Exact full path to the deliverable file, only if already known verbatim."
                }
            }
        }
    }
}

# [BL-096] 軽微な懸念・気づき・訂正指示を、複数ターン・複数タスクをまたいで検索可能な形で
# 記録するissue管理DB。agreements/verified_factsは「確定事項」の記録に対し、issue_logは
# 「まだ解決していない懸念の追跡」に特化する。MVPではdetector/userの2ロールのみ書き込み可能。
WRITE_ISSUE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_issue",
        "description": (
            "軽微な懸念・気づき・訂正指示を、後続タスクからも検索可能な形で記録する（issue_logテーブル）。"
            "同じtopicで再度CREATEすると自動的に「再発」として扱われ、累積回数が2回に達すると"
            "システムが自動的にseverity='major'・status='escalated'へ引き上げる（この昇格は"
            "モデルの判断に依存せず機械的に行われる。read_issuesでtopic_keywordとtask_idを指定して既存issueを"
            "再発見した場合も同様に再発カウントされるため、re-CREATEを省略しても再発の検知自体は失われない）。"
            "'topic'は一度決めたら変えない固定の短い識別文字列にすること（write_agreementのtopic/target_topicと"
            "同じ規約）。再登録する前に、まずread_issuesで似た表現の既存issueがないか確認すること。"
            "[BL-096] CREATEはdetector/user、RESOLVE/DEFERはuserのみ許可。"
            "[BL-136] severity='major'（escalated）の懸念は、今すぐ解決できない場合でも放置してはいけません。"
            "RESOLVEで解決するか、今このタスク・フェーズでは対応すべきでないと判断した場合はDEFERで"
            "対応を予定している具体的なdefer_to_task_id（実在するtask_id）を明示してください。"
            "理由もなく無期限に放置することはできません。"
            "[BL-194] DEFER先は「その懸念に実際に対応できるタスク」を選んでください。受け皿タスクの"
            "acceptance_criteria/owns_variablesが、この懸念の内容と対応している必要があります"
            "（対応していない先へ送ると、そのタスクの担当者に解けない問題を押し付けることになります）。"
            "判断に迷う場合はread_project_planで各タスクのスコープを確認してから指定してください。"
            "自分自身が実行中のタスクへのDEFERはできません（成立していないため拒否されます）。"
            "[BL-194] ACKNOWLEDGEは「この懸念は確かに現在のタスクの責務であり、今まさに対応中である」"
            "と表明するためのものです。RESOLVE（本当に解決した）でもDEFER（別のタスクの責務である）"
            "でもない、正直な第三の選択肢です。督促は一時的に止まりますが、この懸念を未解決のまま"
            "次のタスクへ進むことはできません（タスク離脱ゲートは解除されません）。猶予は有限で、"
            "同一topicにつき2回までです。"
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {"type": "string", "enum": ["CREATE", "RESOLVE", "DEFER", "ACKNOWLEDGE"]},
                "topic": {
                    "type": "string",
                    "description": "固定の検索可能な識別文字列。既存issueの再発検知・解決・先送りに使う（一度決めたら変えないこと）"
                },
                "severity": {
                    "type": "string", "enum": ["minor", "major"],
                    "description": "CREATE時のみ有効。通常はminor"
                },
                "description": {
                    "type": "string",
                    "description": "CREATE時必須。何が問題か・何を訂正指示したか"
                },
                "phase_id": {"type": "string"},
                "task_id": {"type": "string"},
                "resolution_note": {
                    "type": "string",
                    "description": "RESOLVE時必須。どう解決したか"
                },
                "defer_to_task_id": {
                    "type": "string",
                    "description": "DEFER時必須。この懸念への対応を予定している実在のtask_id（現在実行中のタスク自身は指定不可）"
                },
                "defer_reason": {
                    "type": "string",
                    "description": "DEFER時必須。なぜ今このタスクでは対応せず、指定したtask_idへ先送りするのか"
                },
                "ack_reason": {
                    "type": "string",
                    "description": "ACKNOWLEDGE時必須。なぜこの懸念が現在タスクの責務であり、今まさに対応中と言えるのか"
                }
            },
            "required": ["action_type", "topic"]
        }
    }
}

SCHEDULE_TASK_FOCUS_TOOL = {
    "type": "function",
    "function": {
        "name": "schedule_task_focus",
        "description": (
            "[BL-191] 通常の『次タスクへ進む』指示とは別に、過去の承認済みタスクの手戻り対応が"
            "必要になった場合に、そのスケジューリング判断を構造化して1回で明示するツール。"
            "任意呼び出し（通常通り前進するだけの場合は呼ぶ必要はない）。"
            "'redirect_backward': 今すぐ作業対象を過去タスクへ完全に切り替える（現在のフォワード"
            "タスクは一時中断し、対象task_idのDeliverableが再承認され次第、自動的に元へ戻ります）。"
            "深さ1固定（既に中断中のフォーカスがある間は使えません。force_resumeで先に解消してください）。"
            "'joint_focus': 現在のタスクは変更しないが、指定した過去task_idを『今回のターンで"
            "Expert/Detectorが併せて考慮すべき関連タスク』として明示する（current_task_idは動かない）。"
            "'clear_companion': joint_focusで設定した companion を解除する。"
            "'force_resume': redirect_backward中の過去タスクがまだ未解決でも、意図的に中断を"
            "打ち切りフォワードタスクへ強制的に復帰する（安全弁。対象task_idには自動的に"
            "整合性再確認issueが再起票されます）。"
            "[BL-191] このツールを呼んでも、Expertへの通常の作業指示文（次タスク指示）は"
            "別途書く必要があります。このツールはあくまでスケジューリング判断の記録であり、"
            "会話の代わりにはなりません。"
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "decision_type": {
                    "type": "string",
                    "enum": ["redirect_backward", "joint_focus", "clear_companion", "force_resume"]
                },
                "target_task_id": {
                    "type": "string",
                    "description": "redirect_backward時必須。切替先の過去task_id（既存のDeliverableを持つtask_idのみ有効）"
                },
                "companion_task_id": {
                    "type": "string",
                    "description": "joint_focus時必須。今回併せて考慮すべき過去task_id"
                },
                "reason": {"type": "string", "description": "この判断の理由（必須）"}
            },
            "required": ["decision_type", "reason"]
        }
    }
}

READ_ISSUES_TOOL = {
    "type": "function",
    "function": {
        "name": "read_issues",
        "description": (
            "issue_logから懸念・訂正指示を検索する。topic_keyword/task_id/phase_idのいずれかを指定した場合、"
            "status（open/escalated/resolved）を問わず一致した行を返す（resolved行にはresolution_noteが含まれる"
            "ため、既に解決済みかどうかがその場で分かり、無駄な再登録を避けられる）。"
            "list_all=trueを指定した場合はフィルタを無視し、このrunの全issueを返す（issue整理・棚卸し専用。"
            "通常の重複確認にはtopic_keyword等のフィルタ検索を使うこと）。"
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "topic_keyword": {"type": "string", "description": "topic・descriptionの部分一致検索"},
                "task_id": {"type": "string"},
                "phase_id": {"type": "string"},
                "list_all": {
                    "type": "boolean",
                    "description": "trueの場合、他のフィルタを無視してこのrunの全issueを返す（デフォルトfalse）"
                }
            }
        }
    }
}


# [BL-184] 現実世界の地理・費用相場等をグラウンディングするための3ツール。
# 設計: docs/design/back_log/BL-184/BL184_basic_design.md
WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the public web (real-world facts: geography, distances, prices, "
            "regulations, demographics, etc.) and get a list of {title, url, snippet} results. "
            "Does NOT fetch page bodies -- call web_fetch on a promising url for the full text. "
            "[BL-188] If you need a real-world fact you don't already know for certain, use this "
            "tool to find it rather than estimating/guessing from memory -- do not silently assume "
            "a plausible-sounding number. Before spending a new call here on a topic you may have "
            "already researched earlier in this run, try read_reference_file with a keyword first "
            "(it re-reads your own past web_fetch results and does not consume any call limit). "
            "[BL-188] Snippets alone are not sufficient evidence -- treat them critically: prefer "
            "results from authoritative primary sources (government/official statistics, primary "
            "datasets, official documentation) over blogs/aggregators/SEO content, and prefer recent "
            "results over stale ones when the fact is time-sensitive. For anything load-bearing, "
            "web_fetch the primary page rather than citing the snippet as-is. "
            "[BL-188] AVOID this anti-pattern: repeatedly calling web_search with ever-broader or "
            "differently-worded queries while never calling web_fetch. If a result already looks "
            "authoritative/relevant, web_fetch it BEFORE running another search -- one good page read "
            "in full is worth more than ten more snippets, and this also wastes your call budget. "
            "web_fetch now also extracts PDFs directly (common for government/municipal primary "
            "sources), so do not skip a promising .pdf result and search again instead. "
            "Run-scoped call limit applies (see error message if exceeded). "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Search query text."},
                "max_results": {"type": "integer", "description": "Max results to return (1-10, default 5)."},
            },
            "required": ["query"],
        },
    },
}

WEB_FETCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_fetch",
        "description": (
            "Fetch a URL (http/https only) and return its body converted to Markdown (headings, "
            "tables, and links preserved in place -- both HTML pages and PDF documents are "
            "supported, including tables in government/municipal PDF primary sources; truncated "
            "if very long). The result is automatically cached (keyed by URL, shared across ALL "
            "runs -- not just this one) for later re-reading via read_reference_file, so you can "
            "cite it. [BL-200] If a URL was already fetched in a previous run, this call returns "
            "the cached content immediately without consuming your call limit. "
            "[BL-188] Links appear inline as normal Markdown links [text](url) wherever they occur in "
            "the page -- use these to navigate from an index/landing page (e.g. a case-list or topic "
            "page) to the specific sub-page you actually need, instead of only relying on web_search. "
            "Follow at most 1-2 links deep per topic before deciding you have enough -- do not "
            "chain-follow links indefinitely (same run-scoped call limit applies to every web_fetch "
            "call regardless of whether it came from a search result or a link on a previously "
            "fetched page). "
            "[BL-188] Read the fetched content critically before treating it as fact -- check whether "
            "it is the primary/official source or a secondary summary, and whether it appears current. "
            "Redirects are NOT followed (fetch the redirect target url directly instead). "
            "Run-scoped call limit applies; cache hits do not consume the limit. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "Full URL to fetch (http:// or https://)."},
            },
            "required": ["url"],
        },
    },
}

READ_REFERENCE_FILE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_reference_file",
        "description": (
            "Read back a previously web_fetch-cached page, either by exact path (as returned/"
            "implied by web_fetch) or by keyword search over cached pages' source URLs (useful to "
            "re-locate the source behind a citation URL you saw earlier). [BL-200] The cache is "
            "keyed by URL and shared across ALL runs, not just this one -- a page fetched in a "
            "past run is readable here too. "
            "[BL-188] Does not consume the web_search/web_fetch run-scoped call limits -- prefer "
            "trying a keyword search here FIRST before calling web_search/web_fetch again for a "
            "topic that may already have been researched (by you or another role, in this run or "
            "a past one), to avoid redundant external calls. "
            "Read-only; cannot access anything outside the cache directory. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Exact cache filename if already known."},
                "keyword": {"type": "string", "description": "Keyword to search for in cached pages' source URLs."},
            },
        },
    },
}


# [BL-199] 開発者がAGENTS.md §9に従い事前収集した、ゴール固有の参照データ（docs/refs/<goal>/）
# をrun単位の呼び出し回数制限を消費せずに読む。web_searchより先に確認することで、既に
# キャッシュ済みの事実（施設住所・座標等）の再検索によるweb_search予算の浪費を防ぐ。
# 設計: docs/design/back_log/issue_backlog.md BL-199。
# [BL-204] 実世界事物レジストリのツール4本。
# 設計: docs/design/back_log/BL-204/BL204_basic_design.md
# 説明文はドメイン非依存の一般的表現で書く（ユーザー決定3。特定ゴール向けの記述を
# システム側プロンプトへ焼き付けないというBL-196で確立した規律）。
REGISTER_ENTITY_TOOL = {
    "type": "function",
    "function": {
        "name": "register_entity",
        "description": (
            "Register a real-world thing (a place, organization, service, facility, route, "
            "product ... anything with a proper name) that appears in this project but was NOT "
            "in the goal statement -- e.g. something you legitimately discovered via web_search. "
            "Things named in the goal statement are ALREADY registered at run start; do not "
            "re-register them. [BL-204] citations are REQUIRED here: if you are introducing a "
            "name that the goal statement does not contain, you must be able to say where you "
            "found it. Returns the entity_id to use with write_entity_attribute."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "canonical_name": {"type": "string", "description": "The thing's name, exactly as written in your source."},
                "entity_type": {"type": "string", "description": "Free-form category, e.g. 'place', 'organization', 'service', 'facility'."},
                "citations": {
                    "type": "array",
                    "description": "Where you found this thing. Same shape as write_agreement citations.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["web", "goal_text", "prior_agreement", "expert_calculation", "user_input", "document"]},
                            "detail": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["canonical_name", "entity_type", "citations"],
        },
    },
}

WRITE_ENTITY_ATTRIBUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "write_entity_attribute",
        "description": (
            "Record one fact about one registered thing (its address, a coordinate, a count, a "
            "capacity, a schedule ... attribute names are entirely up to you). [BL-204] This is "
            "the durable store for facts about named things -- prefer it over re-deriving the "
            "same fact every round, and over burying a table of facts inside prose. "
            "The thing must already be registered: goal-statement things are registered at run "
            "start, and anything else must go through register_entity first. If you pass a name "
            "that is not registered, this returns did_you_mean candidates -- that usually means "
            "you used a remembered or abbreviated name instead of the one in the goal statement. "
            "confidence is 'confirmed' or 'provisional' only; express 'this is an engineering "
            "assumption I derived' with citations type='expert_calculation', not with confidence."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The thing's registered name (use the goal statement's exact wording)."},
                "attr_name": {"type": "string", "description": "Free-form attribute name, e.g. 'address', 'coordinates', 'elevation_m'."},
                "value": {"type": "string", "description": "The value."},
                "unit": {"type": "string", "description": "Unit if applicable, e.g. 'm', '人'."},
                "confidence": {"type": "string", "enum": ["confirmed", "provisional"], "default": "provisional"},
                "reason": {"type": "string", "description": "How you obtained or derived this value."},
                "citations": {
                    "type": "array",
                    "description": "Sources. REQUIRED when confidence='confirmed'.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {"type": "string", "enum": ["web", "goal_text", "prior_agreement", "expert_calculation", "user_input", "document"]},
                            "detail": {"type": "string"},
                        },
                    },
                },
            },
            "required": ["entity", "attr_name", "value"],
        },
    },
}

READ_ENTITY_TOOL = {
    "type": "function",
    "function": {
        "name": "read_entity",
        "description": (
            "Read a registered thing together with ALL of its recorded attributes (each with its "
            "own source and confidence). [BL-204] Use this INSTEAD of reconstructing facts from "
            "memory or from the deliverable text -- the registry is the source of truth and the "
            "deliverable is the presentation of it. There is deliberately no attribute-name "
            "filter: you always get everything, so you never have to guess an attribute's exact "
            "spelling. "
            "[BL-205] This tool is for facts ABOUT A NAMED THING (a place, organization, "
            "facility, law, etc. -- something you could point at and give a proper name). It is "
            "NOT the same store as read_verified_fact, which holds standalone derived/global "
            "values that are not tied to any one named thing (a budget cap, a computed ratio, a "
            "vehicle count). If what you need is a specific value with no owning entity, use "
            "read_verified_fact instead -- calling this with entity='' to 'see everything' is "
            "rarely useful, since it returns names only, with no attributes attached (see "
            "'entity' param below). Look up an entity by its EXACT name first (you can list "
            "registered things by omitting 'entity', but that only gives names -- call again with "
            "a specific 'entity' to see its attributes)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The thing's registered name. Omit to list all registered things (names only, no attributes -- call again with a name to see its attributes)."},
                "entity_type": {"type": "string", "description": "When listing, optionally filter by category."},
            },
        },
    },
}

VERIFY_ENTITY_GEO_TOOL = {
    "type": "function",
    "function": {
        "name": "verify_entity_geo",
        "description": (
            "[BL-204] Audit check for things that have BOTH an 'address' and a 'coordinates' "
            "attribute: re-geocodes the stored address and reports how far it lands from the "
            "stored coordinates. Use it when a thing's elevation or distance looks off. "
            "A large gap means the stored coordinates are probably a district centroid rather "
            "than the actual place, which makes every elevation and distance derived from them a "
            "real measurement of the wrong location -- the hardest kind of error to spot, because "
            "the measurement itself is genuine. Returns not_applicable if the thing has no address."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "entity": {"type": "string", "description": "The thing's registered name."},
            },
            "required": ["entity"],
        },
    },
}

READ_GOAL_REFERENCE_TOOL = {
    "type": "function",
    "function": {
        "name": "read_goal_reference",
        "description": (
            "Read pre-collected reference data that a developer curated specifically for this "
            "goal (facts, addresses, figures gathered ahead of time and cached to disk). Does "
            "not consume the web_search/web_fetch run-scoped call limits. "
            "[BL-199/BL-200] This is step 1 of the lookup order for any fact about the goal's "
            "subject (addresses, coordinates, demographics, named facilities, etc.): "
            "1) read_goal_reference (this tool, developer-curated) -> 2) read_reference_file "
            "(the shared web_fetch cache, which now persists across runs too) -> 3) web_search "
            "(last resort, only if both return not_found/not_configured). This tool is separate "
            "from read_reference_file: this one holds developer-curated reference data, "
            "read_reference_file holds pages this or a past run actually fetched."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "path": {"type": "string", "description": "Exact relative path if already known (from a previous multiple_matches response)."},
                "keyword": {"type": "string", "description": "Keyword to search for in the reference data's content."},
            },
        },
    },
}


# [BL-198] 実在の公式・準公式APIで、標高・2点間の直線距離・住所ジオコーディング・道路距離を
# 実測値として取得する4ツール。BL-195〜197のプロンプト誘導（実測手段を義務付けない）を
# 補完し、「実測できるものは実測する」余地を広げる。設計: docs/design/back_log/issue_backlog.md BL-198。
GSI_GEOCODE_TOOL = {
    "type": "function",
    "function": {
        "name": "gsi_geocode",
        "description": (
            "Look up latitude/longitude candidates for a Japanese ADDRESS string, using the "
            "official Geospatial Information Authority of Japan (GSI) address search API "
            "(no API key required). Returns up to 5 {title, lat, lon, precision} candidates. Use "
            "this instead of guessing coordinates from memory or from a web_search snippet. "
            "[BL-203] CRITICAL: this is an ADDRESS geocoder, NOT a place/POI search. Facility "
            "names (hospitals, schools, stations) in your query are SILENTLY IGNORED -- querying "
            "'<district> <facility name>' returns exactly the same coordinates as '<district>' "
            "alone, namely the centroid of that district, which can be kilometres away and "
            "hundreds of metres different in elevation from the facility itself. You MUST pass a "
            "street address down to the banchi (e.g. '長野県茅野市豊平5000-1'), not a facility "
            "name. Look the address up first (read_goal_reference / read_reference_file / "
            "web_search) if you do not know it. Check the returned 'precision' field: 'point' "
            "means it resolved to an actual address point; 'area_centroid' means it only resolved "
            "to a district and the coordinates are NOT a specific place -- do not feed those into "
            "gsi_get_elevation or distance calculations, because the result would be a real "
            "measurement of the wrong location."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": (
                        "Japanese street address, down to the banchi if possible "
                        "(e.g. '長野県茅野市豊平5000-1'). NOT a facility name -- facility names are ignored."
                    ),
                },
            },
            "required": ["query"],
        },
    },
}

GSI_GET_ELEVATION_TOOL = {
    "type": "function",
    "function": {
        "name": "gsi_get_elevation",
        "description": (
            "Get the real measured elevation (meters) at a latitude/longitude point, using the "
            "official GSI elevation (DEM) API (no API key required). Returns {elevation_m, "
            "data_source}. Use this instead of estimating/guessing elevation, or citing an "
            "indirect web_search mention of elevation, when you already have coordinates "
            "(e.g. from gsi_geocode)."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat": {"type": "number", "description": "Latitude (decimal degrees)."},
                "lon": {"type": "number", "description": "Longitude (decimal degrees)."},
            },
            "required": ["lat", "lon"],
        },
    },
}

GSI_CALC_DISTANCE_BEARING_TOOL = {
    "type": "function",
    "function": {
        "name": "gsi_calc_distance_bearing",
        "description": (
            "Compute the geodesic (straight-line, as-the-crow-flies) distance and bearing "
            "between two latitude/longitude points, using the official GSI survey calculation "
            "API (no API key required). "
            "[IMPORTANT] This is a STRAIGHT-LINE distance, NOT a road distance -- it will "
            "understate actual travel distance, especially on winding mountain roads. Do not "
            "present this as road distance or travel time. If you need road distance/duration, "
            "use calc_road_route instead. This tool is appropriate for a defensible order-of-"
            "magnitude reference or when only straight-line distance is actually needed."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat1": {"type": "number", "description": "Latitude of point 1."},
                "lon1": {"type": "number", "description": "Longitude of point 1."},
                "lat2": {"type": "number", "description": "Latitude of point 2."},
                "lon2": {"type": "number", "description": "Longitude of point 2."},
            },
            "required": ["lat1", "lon1", "lat2", "lon2"],
        },
    },
}

CALC_ROAD_ROUTE_TOOL = {
    "type": "function",
    "function": {
        "name": "calc_road_route",
        "description": (
            "Compute the real road-network driving distance and travel time between two "
            "latitude/longitude points, using the OpenRouteService Directions API. Requires the "
            "CELA_ORS_API_KEY environment variable to be set (free registration at "
            "https://openrouteservice.org/dev/#/signup) -- if unset, this tool returns a "
            "configuration error explaining how to obtain a key; fall back to "
            "gsi_calc_distance_bearing (clearly labeled as straight-line) in that case. "
            "Run-scoped call limit applies (see error message if exceeded). Returns "
            "{road_distance_m, duration_s, profile}."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "lat1": {"type": "number", "description": "Latitude of the start point."},
                "lon1": {"type": "number", "description": "Longitude of the start point."},
                "lat2": {"type": "number", "description": "Latitude of the end point."},
                "lon2": {"type": "number", "description": "Longitude of the end point."},
                "profile": {
                    "type": "string",
                    "description": "Routing profile, e.g. 'driving-car' (default), 'foot-walking'.",
                },
            },
            "required": ["lat1", "lon1", "lat2", "lon2"],
        },
    },
}


# [BL-079] Detector専用。target_excerpt（ホワイトボードへの注釈挿入に使う一字一句引用）が
# 実際に一意一致するかを、JSON最終出力を書く前にツールループ内で確認できるようにする。
# 従来はdetector_nodeの事後処理でのみ判明し、一致失敗はサイレントに（Detector自身に一切
# フィードバックされないまま）握りつぶされていた（BL-074）。このツールで事前検証させることで、
# 同一ツールループ内でexcerptを調整・再試行できる。
VERIFY_WHITEBOARD_EXCERPT_TOOL = {
    "type": "function",
    "function": {
        "name": "verify_whiteboard_excerpt",
        "description": (
            "Check whether a candidate quote (for the JSON output's target_excerpt field) matches "
            "EXACTLY ONCE in the current task's latest whiteboard content, before you finalize your "
            "JSON. If it returns ok=false, adjust the excerpt (e.g. make it longer/more specific to "
            "become unique, or fix a mismatched character) and call this again -- do not just give up "
            "and leave target_excerpt as a guess. Call this once for your final candidate excerpt "
            "before writing the JSON output. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "excerpt": {
                    "type": "string",
                    "description": "Exact verbatim quote (1-2 sentences) from the whiteboard content you intend to use as target_excerpt."
                }
            },
            "required": ["excerpt"],
        },
    },
}


# [BL-193] Expert専用。write_agreement(edits=...)のold_textを組み立てる前に、編集したい
# 箇所の"現在の"実際の文字列だけをピンポイントで読めるようにする。1514ログ（task_2_1、
# 50KB超に育ったホワイトボード）で、Expertがプロンプトに一度提示された全文の記憶だけを
# 頼りにold_textを再構成し、Detector注釈の埋め込みなどで実際の内容と食い違ったまま
# 同じ大きな不一致を8回連続で繰り返した事故を受けて追加。verify_whiteboard_excerpt
# （BL-079、Detector専用・「一致するか検証のみ」）と判定ロジックは共通だが、目的が逆で
# こちらは「実際に一致した周辺の中身を読む」ことが主眼。
READ_WHITEBOARD_EXCERPT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_whiteboard_excerpt",
        "description": (
            "[BL-193] Before constructing old_text for write_agreement's edits parameter, use this to "
            "fetch ONLY the current actual text around a specific heading/keyword in the current "
            "task's whiteboard -- instead of relying on your memory of the full document shown "
            "earlier in this conversation, which may already be stale (e.g. after a Detector "
            "annotation was inserted). Your old_text MUST match the string this tool returns "
            "verbatim, not your recollection of the original prompt. If the keyword matches more "
            "than once, this returns the match count so you can pick a more specific keyword instead "
            "of guessing which occurrence you meant. "
            "[BL-202] The returned excerpt is a WINDOW around the match: a leading '…（中略）' or "
            "trailing '…（以下省略）' means text was cut off there and you cannot see it -- never "
            "extend your old_text into those cut-off regions from memory. "
            "[BL-202] Also use this to COUNT occurrences when you are told the same claim "
            "contradicts itself across several sections: search for the offending phrase itself "
            "(e.g. '通年運行可能'), not the section heading, and the match_count tells you how many "
            "places you still have to fix."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "keyword": {
                    "type": "string",
                    "description": "Heading or phrase to locate in the current whiteboard (e.g. '### 3.6 時間帯別'). Exact match is tried first, falling back to whitespace/markdown-normalized loose match."
                },
                "context_chars": {
                    "type": "integer",
                    "description": "Characters of context to include before/after the match (default 800, max 3000)."
                }
            },
            "required": ["keyword"],
        },
    },
}


# [BL-092] task_plan_reviewer専用。前ラウンドでmajor/minor判定した特定task_idの内容が、
# 次のラウンドで実際に検算・訂正されたのか、単に記述ごと削除・抽象化されて見えなくなった
# だけなのかを、LLMの主観的な印象ではなく機械的なdiffで確認できるようにする。task_planner_node
# は再生成のたびに全タスクのplan_draftsスケルトンをauthor_role="task_planner"で再投入するため
# （タスク自身の再生成品質確認とは無関係だが、副次的に版管理の役割も果たす）、直近2回分の
# task_planner版を単純比較すれば「前回指摘した具体的な数値・記述が今回どう変わったか」が分かる。
DIFF_PLAN_DRAFT_VERSIONS_TOOL = {
    "type": "function",
    "function": {
        "name": "diff_plan_draft_versions",
        "description": (
            "Get a mechanical line-by-line diff between the two most recent task_planner-authored "
            "versions of a given task_id's plan text. Use this BEFORE judging whether a previously "
            "flagged issue (major/minor from an earlier round) was actually fixed with a corrected "
            "value, versus merely deleted or reworded away with no equivalent replacement -- do not "
            "rely on your own memory/impression of what changed. Requires at least 2 task_planner "
            "rounds to exist for this task_id (fails gracefully with a reason if not). "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "task_id to diff across the two most recent task_planner rounds, e.g. 'task_2_2'."
                }
            },
            "required": ["task_id"],
        },
    },
}


def _diff_plan_draft_versions_handler(args: dict) -> dict:
    """[BL-092] diff_plan_draft_versionsツールの実体。同一task_idについて
    author_role='task_planner'の版を版番号順に取得し、直近2件の間の統一diff（difflib）を返す。
    書き込みは行わない読み取り専用ツール。
    """
    task_id = args.get("task_id", "")
    if not task_id:
        return {"ok": False, "reason": "task_idが空文字です"}
    if not _CURRENT_RUN_ID:
        return {"ok": False, "reason": "現在のrunが特定できませんでした"}
    conn = get_active_conn()
    rows = conn.execute(
        "SELECT version, content FROM plan_drafts "
        "WHERE run_id=? AND task_id=? AND author_role='task_planner' ORDER BY version ASC",
        (_CURRENT_RUN_ID, task_id)
    ).fetchall()
    if len(rows) < 2:
        return {
            "ok": False,
            "reason": (
                f"task_id='{task_id}'にtask_planner由来の版が{len(rows)}件しかありません"
                "（差分を出すには2件以上必要です。まだ1回しか計画生成されていないか、task_idが誤りです）"
            ),
        }
    prev, latest = rows[-2], rows[-1]
    diff_lines = list(difflib.unified_diff(
        prev["content"].splitlines(), latest["content"].splitlines(),
        fromfile=f"round(version={prev['version']})", tofile=f"round(version={latest['version']})",
        lineterm="",
    ))
    diff_text = "\n".join(diff_lines)
    return {
        "ok": True,
        "prev_version": prev["version"],
        "latest_version": latest["version"],
        "diff": diff_text[:8000] if diff_text else "(前回と完全に同一内容で、差分はありません)",
    }


# [BL-101] task_planner向け。「フェーズ・タスク表」ホワイトボード（plan_drafts）の最新版を
# 直接読む読み取り専用ツール。差し戻しを受けての再分解時、task_plan_reviewerが書き込んだ
# 「レビュワーからの指摘（要修正）」セクション（BL-087 Stage2）を含む最新の記述内容を確認せず
# 全フェーズ・全タスクを一から作り直してしまう問題（実ドライラン log/2026-07-27/1438 で確認）
# への対策。
READ_PLAN_DRAFT_TOOL = {
    "type": "function",
    "function": {
        "name": "read_plan_draft",
        "description": (
            "Read the latest version of the 'phase/task table' whiteboard (plan_drafts) for a "
            "given task_id -- this is the actual persisted document you (task_planner) wrote last "
            "time, including any '## レビュワーからの指摘（要修正）' section task_plan_reviewer has "
            "appended directly to that task. When revising after a rejection, call this for every "
            "task_id that received a specific reviewer comment BEFORE deciding what to change -- do "
            "not reconstruct the whole plan from the goal text and the feedback summary alone; keep "
            "tasks/phases that were not flagged unchanged. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "task_id": {
                    "type": "string",
                    "description": "task_id whose current whiteboard content you want to read, e.g. 'task_2_2'."
                }
            },
            "required": ["task_id"],
        },
    },
}


def _read_plan_draft_handler(args: dict) -> dict:
    """[BL-101] read_plan_draftツールの実体。get_latest_plan_draft_by_task_idの薄いラッパー。
    task_planner自身の再分解プロンプトに、フェーズ・タスク表ホワイトボードの最新版
    （task_plan_reviewerの個別指摘込み）を能動的に確認させるためのツール。
    """
    task_id = args.get("task_id", "")
    if not task_id:
        return {"status": "error", "message": "task_idを指定してください。"}
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    draft = get_latest_plan_draft_by_task_id(conn, run_id, task_id)
    if not draft:
        return {"status": "not_found", "message": f"task_id='{task_id}'のplan_draftが見つかりませんでした。"}
    return draft


READ_PROJECT_PLAN_TOOL = {
    "type": "function",
    "function": {
        "name": "read_project_plan",
        "description": (
            "Read the full project plan (all phases and tasks, including each task's "
            "description/acceptance_criteria/depends_on/owns_variables) -- the complete structure "
            "that only a lightweight table-of-contents (phase_id/task_id/title) is shown for by "
            "default. Call this only if the table-of-contents in the prompt is not enough context "
            "for your current task (e.g. you need to understand another task's exact requirements "
            "or dependency structure). "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {"type": "object", "properties": {}},
    },
}


def _read_project_plan_handler(args: dict) -> list:
    """[BL-104] read_project_planツールの実体。呼び出しノード（call_expert）が事前に
    _CURRENT_PHASESへコピーしたstate["phases"]をそのまま返す薄いラッパー。
    """
    return list(_CURRENT_PHASES)


def _build_project_plan_toc(phases: list[dict]) -> str:
    """[BL-104] call_expertの常時表示用に、全フェーズ・全タスクのphase_id/task_id/titleのみを
    箇条書きの目次（table of contents）として整形する。descriptionやacceptance_criteria等の
    詳細はread_project_planツールで能動的に取得させる（BL-025のスコープガードレールの趣旨とも
    整合し、常時表示するphases_json全文（13,000字超）に比べ大幅に軽量）。
    """
    lines = []
    for phase in phases:
        lines.append(f"- [{phase.get('phase_id', '?')}] {phase.get('title', '?')}")
        for task in phase.get("tasks", []):
            lines.append(f"  - [{task.get('task_id', '?')}] {task.get('title', '?')}")
    return "\n".join(lines) if lines else "(まだフェーズ・タスク計画がありません)"


# [BL-093] 全ノード共通のツールループ（_query_AI_live）はモデルのreasoning（chain-of-thought
# 生文章）を_StreamMessageでNone固定にして捨てており、次iterationでモデルは前回のtool_calls/
# tool結果という骨組みだけから理由を再構築している。このツールに理由づけ（action/decided/why/
# rejected/rejected_why）を書かせ、tool結果として即座に蓄積済み全履歴を返すことで、消える
# reasoningチャネルから残るtool_callsチャネルへ理由づけを退避させる。todo/issues/notesは、
# 複数回のpython_repl呼び出しを跨ぐ長いツールループ（Detector数値監査・task_planner・
# task_plan_reviewer）で何を確認済みか・何が未解決かを機械的に追跡させるための可変メモ。
# `summary`は自動reasoningダイジェスト（_query_AI_live）専用のフィールド。thinkを呼ぶかどうかを
# モデルの任意判断に委ねると、大半のiterationでreasoningが結局失われることが判明したため
# （ユーザー指摘）、ツール呼び出しを含む全iterationでthink+非空summaryを機械的に必須化する
# （_query_AI_live側の強制ロジック、このツール定義側では`required`に含めるのみ）。
THINK_TOOL = {
    "type": "function",
    "function": {
        "name": "think",
        "description": (
            "Optionally record your reasoning, decisions, and a running todo/issue list here. "
            "[BL-113] Your raw reasoning is automatically captured every iteration regardless of "
            "whether you call this tool (native reasoning capture, accumulated append-only per "
            "BL-108/BL-111) -- calling `think` is not required to preserve reasoning across "
            "iterations. Its remaining value is structured articulation: explicitly stating what "
            "you decided, why, and what alternative you rejected and why, plus maintaining a "
            "running todo/issue list across iterations. "
            "On your first call, it's useful to list your initial todo breakdown. "
            "You do not need to track the iteration number yourself; it is stamped automatically."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "What you are thinking about / trying to do in this step. Required every call."
                },
                "summary": {
                    "type": "string",
                    "description": (
                        "A concise 1-3 sentence summary of what you worked on and concluded this "
                        "step. Required whenever you call `think`. This summary persists alongside "
                        "your raw reasoning (BL-108/BL-111: nothing is summarized away or aged out), "
                        "so make it self-contained enough to be understood on its own."
                    )
                },
                "decided": {
                    "type": "string",
                    "description": "What you decided in this step, if anything."
                },
                "why": {
                    "type": "string",
                    "description": "The reason for the decision. Required if 'decided' is given."
                },
                "rejected": {
                    "type": "string",
                    "description": "An alternative you considered but rejected, if any."
                },
                "rejected_why": {
                    "type": "string",
                    "description": "Why you rejected it. Required if 'rejected' is given."
                },
                "todo": {
                    "type": "array",
                    "description": (
                        "The FULL current todo list (not a diff). Include this only when it "
                        "changes (new item added, or an item's status flips); omitting it means "
                        "it is unchanged since your last call."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "status": {"type": "string", "enum": ["open", "closed"]}
                        },
                        "required": ["item", "status"]
                    }
                },
                "scratch_concerns": {
                    "type": "array",
                    "description": (
                        "[BL-140] The FULL current list of concerns you are tracking WITHIN this "
                        "single tool-call loop only (not a diff). Same omit-if-unchanged rule as "
                        "todo. This is NOT the persistent issue_log and is NOT visible to future "
                        "turns or other roles -- it is discarded the moment this tool-call loop "
                        "ends. If a concern should survive beyond this step (so it can be tracked, "
                        "resolved, or handed off across turns), call the separate `write_issue` "
                        "tool instead; do not rely on this field for that."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "item": {"type": "string"},
                            "status": {"type": "string", "enum": ["open", "closed"]}
                        },
                        "required": ["item", "status"]
                    }
                },
                "notes": {
                    "type": "string",
                    "description": (
                        "A new free-form note to append. This is append-only -- it never "
                        "replaces or deletes previous notes, so you don't need to restate old ones."
                    )
                }
            },
            "required": ["action", "summary"]
        }
    }
}

# [BL-093] thinkツール専用のスクラッチパッド状態。1ノード呼び出し（query_AIの1回の
# ツールループ）中だけ生きる想定で、DB/stateいずれにも永続化しない。呼び出しノード側
# （call_detector数値監査パス/call_task_planner/call_task_plan_reviewer）で開始時にリセットする。
_CURRENT_TOOL_LOOP_ITERATION: int = 0
_THINK_REASONING_LOG: list[dict] = []
_THINK_TODO: list[dict] = []
_THINK_SCRATCH_CONCERNS: list[dict] = []
_THINK_NOTES: list[str] = []


def _reset_think_scratchpad() -> None:
    """[BL-093] リセットを忘れると前のノード呼び出しのtodo/scratch_concerns/notesが漏れ込むため、
    thinkツールを付与する各ノード関数の呼び出し開始時に必ず呼ぶ。
    """
    global _CURRENT_TOOL_LOOP_ITERATION, _THINK_REASONING_LOG, _THINK_TODO, _THINK_SCRATCH_CONCERNS, _THINK_NOTES
    _CURRENT_TOOL_LOOP_ITERATION = 0
    _THINK_REASONING_LOG = []
    _THINK_TODO = []
    _THINK_SCRATCH_CONCERNS = []
    _THINK_NOTES = []


def _think_handler(args: dict) -> dict:
    """[BL-093] thinkツールの実体。reasoningは追記専用ログに、todo/scratch_concernsは変更時のみ
    全体を差し替え、notesは追記専用リストに保持する。iter番号はモデルの自己申告に頼らず
    _CURRENT_TOOL_LOOP_ITERATION（_query_AI_liveが機械的に更新）から取る。永続化はせず、
    ツールループ終了と同時に消える。`summary`の非空チェック（think+summary必須の機械的強制）は
    ここではなく_query_AI_live側で行う（ここは単に受け取った値を保存するだけ）。
    [BL-140] `scratch_concerns`は元々`issues`という名前だったが、実ドライランで`write_issue`
    （DBへ永続化されターンをまたいでUser/Expertへ表示される）と混同され、モデルがここへ
    懸念を書いて満足し`write_issue`を呼ばずに終わる（＝懸念がツールループ終了と同時に
    消える）実例が観測された。名前を改め、消える一時メモであることを明示した。
    """
    global _THINK_TODO, _THINK_SCRATCH_CONCERNS
    entry = {
        "iter": _CURRENT_TOOL_LOOP_ITERATION,
        "action": args.get("action", ""),
        "summary": args.get("summary", ""),
        "decided": args.get("decided", ""),
        "why": args.get("why", ""),
        "rejected": args.get("rejected", ""),
        "rejected_why": args.get("rejected_why", ""),
    }
    _THINK_REASONING_LOG.append(entry)
    if "todo" in args:
        _THINK_TODO = args["todo"]
    if "scratch_concerns" in args:
        _THINK_SCRATCH_CONCERNS = args["scratch_concerns"]
    note = args.get("notes", "")
    if note:
        _THINK_NOTES.append(note)
    return {
        "reasoning_log_so_far": _THINK_REASONING_LOG,
        "current_todo": _THINK_TODO,
        "current_scratch_concerns": _THINK_SCRATCH_CONCERNS,
        "notes_so_far": _THINK_NOTES,
    }


def _read_verified_fact_handler(args: dict) -> dict | list:
    """[F-3.8] verified_facts読み取りツールのハンドラ。TOOL_DISPATCH経由で呼び出される。
    conn/run_idはモジュールレベル変数から取得する（_DB_CONN/_CURRENT_RUN_ID）。
    ★修正（レビュー指摘H1、二重JSONエンコード対応）: _query_AI_liveのツールループ末尾が
    全ツール結果を無条件でjson.dumps()するため、ハンドラ自身はjson.dumps済み文字列ではなく
    生のPythonオブジェクト（dict/list）を返す。ここでjson.dumpsすると、末尾で再度
    json.dumpsされ「JSON文字列を表すJSON文字列」という二重エスケープになりLLMに渡ってしまう。
    """
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    variable_name = args.get("variable_name")
    topic_keyword = args.get("topic_keyword")
    results = get_verified_facts_from_db(
        conn, run_id,
        variable_names=[variable_name] if variable_name else None,
        topic=topic_keyword,
    )
    # [BL-187] フレーズ全体一致がnot_foundだった場合、トークン分割OR検索へ緩和する
    # （variable_name指定時は対象外。variable_nameは一意識別子であり曖昧化させない）。
    if not results and topic_keyword and not variable_name:
        tokens = _tokenize_topic_keyword(topic_keyword)
        if len(tokens) > 1:
            results = get_verified_facts_from_db_any_token(conn, run_id, tokens)
            if results:
                print(f"  🔎 [BL-187] read_verified_fact: フレーズ全体一致は無かったが、"
                      f"トークン分割OR検索で{len(results)}件ヒットしました（tokens={tokens}）。")
    if not results:
        suggestions = suggest_similar_verified_facts(conn, run_id, variable_name or topic_keyword or "")
        message = "該当する確定値が見つかりませんでした。"
        if suggestions:
            message += f" もしかして次のvariable_nameではありませんか: {', '.join(suggestions)}"
        return {"status": "not_found", "message": message, "did_you_mean": suggestions}
    return results


# ---------------------------------------------------------------------------
# [BL-204] 実世界事物レジストリのツールハンドラ
# ---------------------------------------------------------------------------

def _register_entity_handler(args: dict, state: dict | None = None) -> dict:
    """[BL-204] `register_entity`ハンドラ。ゴール文に無い事物（web_search等で正当に
    発見したもの）を`origin='discovered'`として登録する。
    [CONSTRAINT] alias引数は持たない。モデルが自由にaliasを追加できると、未登録名を拒否する
    同一性ガードがそこから抜けるため（設計書§2.4、Clineレビュー指摘・軽4）。"""
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    canonical_name = (args.get("canonical_name") or "").strip()
    entity_type = (args.get("entity_type") or "").strip() or "unknown"
    citations = args.get("citations") or []
    if not canonical_name:
        return {"status": "error", "message": "canonical_nameは必須です。"}
    # [BL-204] discovered事物は出典必須。ゴール文に無い名前を持ち込む以上、
    # どこで見つけたのかを示せない登録は認めない（BL-188のcitations方針と同じ考え方）。
    if not citations:
        return {"status": "error",
                "message": "ゴール文に無い事物を登録するには、citations（出典）が必須です。"
                           "web_search/web_fetch/read_goal_reference等で確認した出典を添えてください。"}
    existing = resolve_entity(conn, run_id, canonical_name)
    if existing:
        return {"status": "already_registered", "entity_id": existing["entity_id"],
                "canonical_name": existing["canonical_name"], "origin": existing["origin"]}
    try:
        entity_id = register_entity_in_db(conn, run_id, canonical_name, entity_type,
                                          origin="discovered", created_by=_CURRENT_CALLER_ROLE)
    except ValueError as e:
        return {"status": "error", "message": str(e)}
    print(f"  🗂️ [BL-204] 事物を登録しました（discovered）: {canonical_name}（{entity_type}）")
    return {"status": "registered", "entity_id": entity_id, "origin": "discovered"}


def _write_entity_attribute_handler(args: dict, state: dict | None = None) -> dict:
    """[BL-204] `write_entity_attribute`ハンドラ。未登録の事物名は`did_you_mean`付きで
    拒否する（`_read_verified_fact_handler`の返却形式に揃える）。これが
    log/2026-08-10/0901の「長野大学」を止める同一性ガードの実体。"""
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    name = (args.get("entity") or "").strip()
    attr_name = (args.get("attr_name") or "").strip()
    if not name or not attr_name:
        return {"status": "error", "message": "entityとattr_nameは必須です。"}
    if "value" not in args:
        return {"status": "error", "message": "valueは必須です。"}

    ent = resolve_entity(conn, run_id, name)
    if not ent:
        suggestions = suggest_similar_entities(conn, run_id, name)
        return {
            "status": "unknown_entity",
            "message": f"'{name}' はこの課題に登録された事物ではありません。"
                       f"ゴール文に登場する事物はrun開始時に登録済みです。"
                       f"ゴール文の表記をそのまま使ってください。"
                       f"web_search等で新たに発見した事物であれば、先にregister_entityで"
                       f"出典付きで登録してください。",
            "did_you_mean": suggestions,
        }

    confidence = (args.get("confidence") or "provisional").strip()
    if confidence not in _ENTITY_CONFIDENCE_VALUES:
        return {"status": "error",
                "message": f"confidenceは{list(_ENTITY_CONFIDENCE_VALUES)}のいずれかです。"
                           f"工学的仮定・導出値であることは、confidenceではなく"
                           f"citationsのtype=\"expert_calculation\"で表してください。"}
    citations = args.get("citations") or []
    # [BL-204] confirmedを名乗るなら出典が要る（BL-041「暫定値を確定扱いにしない」の延長）。
    if confidence == "confirmed" and not citations:
        return {"status": "error",
                "message": "confidence=\"confirmed\"にはcitations（出典）が必須です。"
                           "出典を示せない場合はconfidence=\"provisional\"にしてください。"}

    is_new_attr = upsert_entity_attribute(
        conn, run_id, ent["entity_id"], attr_name, args.get("value"),
        args.get("unit", "") or "", confidence, citations, args.get("reason", "") or "",
        _task_id_from(state), _phase_id_from(state), _CURRENT_CALLER_ROLE,
    )
    result = {"status": "ok", "entity_id": ent["entity_id"],
              "canonical_name": ent["canonical_name"], "attr_name": attr_name}
    if is_new_attr:
        # [BL-204] 新しい属性名を作ったときだけ既存一覧を返し、表記ゆれによる
        # 重複作成（coordinates と coordinate が併存する等）に気づけるようにする
        # （設計書§2.4、Clineレビュー指摘・軽3）。
        existing_names = [
            r["attr_name"] for r in conn.execute(
                "SELECT attr_name FROM entity_attributes WHERE run_id=? AND entity_id=? "
                "ORDER BY attr_name", (run_id, ent["entity_id"])
            ).fetchall()
        ]
        result["created_new_attribute"] = True
        result["all_attribute_names"] = existing_names
        result["note"] = ("新しい属性名を作成しました。同じ意味の属性が別名で既に存在しないか、"
                          "all_attribute_namesを確認してください。")
    return result


def _read_entity_handler(args: dict, state: dict | None = None) -> dict:
    """[BL-204] `read_entity`ハンドラ。事物と**全属性**を返す。
    [CONSTRAINT] attr_name指定の絞り込みは提供しない。属性名が完全に自由である以上、
    読み取り側で名前を推測させると表記ゆれで空振りするため、推測が発生しない形にする
    （設計書§2.4、Clineレビュー指摘・軽3）。
    [BL-205] log/2026-08-10/1829で、read_entityとread_verified_factの役割分担が伝わらず、
    モデルが「何か確認したい」→空引数で一覧取得→属性が無く空振り、という探索的だが
    非効率な呼び出しを繰り返す事例が複数回観測された（User AI Stage4の思考ログ
    「The developer mentioned that the source of truth requires using the read_entity
    function. So it seems like I should call the function to list all entities.」）。
    一覧モード（entity未指定）の返り値へ、次に取るべき行動のヒントを添えて誘導する。"""
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    name = (args.get("entity") or "").strip()
    if not name:
        entities = list_entities_from_db(conn, run_id, (args.get("entity_type") or "").strip())
        result = {"entities": entities}
        if entities:
            result["hint"] = (
                "これは名前の一覧のみです（属性は含まれません）。特定の事物について値が"
                "必要な場合は、read_entity(entity=\"<上記のcanonical_nameのいずれか>\")で"
                "再度呼んでください。対象がどの事物にも属さない単独の値（予算上限・比率等）の"
                "場合は、read_entityではなくread_verified_factを使ってください。"
            )
        return result
    ent = resolve_entity(conn, run_id, name)
    if not ent:
        return {"status": "not_found",
                "message": f"'{name}' はこの課題に登録された事物ではありません。",
                "did_you_mean": suggest_similar_entities(conn, run_id, name)}
    full = get_entity_with_attributes(conn, run_id, ent["entity_id"])
    return full or {"status": "not_found", "message": "属性の取得に失敗しました。"}


def _verify_entity_geo_handler(args: dict, state: dict | None = None) -> dict:
    """[BL-204] `verify_entity_geo`ハンドラ（Detector向け）。事物に保存された住所を
    再ジオコーディングし、保存座標と突き合わせる。BL-203で追加した`precision`と併用し、
    「誤った場所の正しい実測値」（大字の代表点を施設の位置として採用した状態）を
    機械的に検出する。住所と座標の両方を持つ事物にのみ適用できる。"""
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    name = (args.get("entity") or "").strip()
    if not name:
        return {"status": "error", "message": "entityは必須です。"}
    ent = resolve_entity(conn, run_id, name)
    if not ent:
        return {"status": "not_found",
                "message": f"'{name}' はこの課題に登録された事物ではありません。",
                "did_you_mean": suggest_similar_entities(conn, run_id, name)}
    full = get_entity_with_attributes(conn, run_id, ent["entity_id"]) or {}
    attrs = {a["attr_name"]: a["value"] for a in full.get("attributes", [])}

    address = ""
    for key in ("address", "住所"):
        if attrs.get(key):
            address = attrs[key]
            break
    if not address:
        return {"status": "not_applicable",
                "message": "この事物には住所（address）属性が無いため、座標の照合はできません。"}

    geo = geo_tools.gsi_geocode_handler({"query": address}, state or {}, _tool_config(state))
    if "results" not in geo or not geo["results"]:
        return {"status": "error", "message": f"住所の再ジオコーディングに失敗しました: {geo}"}
    top = geo["results"][0]
    out = {
        "status": "checked", "entity": ent["canonical_name"], "address": address,
        "geocoded": {"title": top.get("title"), "lat": top.get("lat"), "lon": top.get("lon"),
                     "precision": top.get("precision")},
    }
    if "warning" in geo:
        out["warning"] = geo["warning"]

    stored = attrs.get("coordinates") or attrs.get("座標") or ""
    if not stored:
        out["note"] = ("この事物にはcoordinates属性が無いため比較できませんでした。"
                       "上記geocodedの結果を座標として記録できます。")
        return out
    # 保存座標は "35.99, 138.15" のような自由書式なので、数値2つを機械的に取り出す
    nums = re.findall(r"-?\d+\.?\d*", str(stored))
    if len(nums) < 2:
        out["note"] = f"保存されたcoordinates（{stored}）から緯度経度を読み取れませんでした。"
        return out
    try:
        s_lat, s_lon = float(nums[0]), float(nums[1])
    except ValueError:
        out["note"] = f"保存されたcoordinates（{stored}）を数値化できませんでした。"
        return out
    # 緯度1度≒111km。概算で十分（乖離が数km規模かどうかを見たいだけ）。
    dlat_km = abs(s_lat - float(top["lat"])) * 111.0
    dlon_km = abs(s_lon - float(top["lon"])) * 111.0 * math.cos(math.radians(s_lat))
    gap_km = math.hypot(dlat_km, dlon_km)
    out["stored_coordinates"] = {"lat": s_lat, "lon": s_lon}
    out["gap_km"] = round(gap_km, 3)
    if gap_km > 1.0:
        out["verdict"] = "mismatch"
        out["message"] = (
            f"保存座標と、保存住所を引き直した座標が約{gap_km:.1f}km離れています。"
            f"保存座標が施設の位置ではなく区画の代表点である可能性が高く、"
            f"この座標から得た標高・距離は「誤った場所の正しい実測値」になっている恐れがあります。"
        )
    else:
        out["verdict"] = "consistent"
    return out


def _resolve_deliverable_pointer(task_id: str, topic_keyword: str) -> str | None:
    """[BL-040/R4] `read_deliverable_file`のtask_id/topic_keyword検索用ヘルパー。
    Deliverableのファイル名はトピック文字列＋Unixタイムスタンプ（またはR4のWHITEBOARD:ポインタ）
    で決まり、AIが事前に予測できないため、agreements DBに記録された`FILE_PATH:...`/`WHITEBOARD:...`
    ポインタ（生の値）を逆引きする。同一task_id/topicで複数件ある場合は最新（id最大）を優先する。
    """
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    agreements = get_agreements_from_db(conn, run_id)
    candidates = [
        a for a in agreements
        if a.get("entry_type") == "Deliverable"
        and (str(a.get("decision_what", "")).startswith("FILE_PATH:") or str(a.get("decision_what", "")).startswith("WHITEBOARD:"))
        and (not task_id or a.get("task_id") == task_id)
        and (not topic_keyword or topic_keyword in str(a.get("topic", "")))
    ]
    if not candidates:
        return None
    best = max(candidates, key=lambda a: a.get("id", 0))
    return best["decision_what"]


def _read_deliverable_file_handler(args: dict, state: dict | None = None) -> dict | str:
    """[F-3.8] Deliverableファイル読み取りツールのハンドラ。
    ★修正（レビュー指摘③）: pathlib.Path.resolve()によるディレクトリ包含チェックで
    Windowsパス区切り・パストラバーサル防止の両方を対応する。
    ★修正（レビュー指摘H1、二重JSONエンコード対応）: エラー/not_found時はjson.dumps済み
    文字列ではなく生のdictを返す（理由は_read_verified_fact_handlerのコメント参照）。
    成功時のファイル内容（プレーン文字列）は元々二重エンコードの問題がないためそのまま。
    ★修正（BL-040）: 実ドライランでfile_path直接指定が約68%の割合でnot_foundになっていた
    （タイムスタンプ付きファイル名をAIが予測できないため）。task_id/topic_keywordによる
    DB逆引きを優先させ、file_pathは既に正確なパスが分かっている場合のみのフォールバックとする。
    ★修正（R4）: 逆引き先がWHITEBOARD:ポインタの場合はファイルI/Oではなくwhiteboard_draftsの
    最新版を直接返す。呼び出し側（Detector/Expert/User）はFILE_PATH方式かWHITEBOARD方式かを
    意識せず、task_id/topic_keywordだけで読めるようにする。
    [BL-147] task_id指定時は`write_agreement`（BL-131）と同型の実在チェックを先に行う。
    従来は未検証のままfile_path併用時に素通りしていた（存在しないtask_id＋正しいfile_pathを
    同時指定すると、task_idが実質無視されてfile_path側でそのまま読めてしまう抜け道）。
    実在する他タスクの成果物を参照読みする用途（本来の目的）は制限しない。
    """
    task_id = args.get("task_id", "")
    topic_keyword = args.get("topic_keyword", "")
    file_path = args.get("file_path", "")
    if task_id:
        task_obj = _find_task_by_id(_phases_from(state) or [], task_id)
        if task_obj is None and task_id not in (_pending_task_ids_from(state) or []):
            print(f"  ⚠️ [read_deliverable_file] task_id '{task_id}' はtask_plannerの正式な計画に存在しません。")
            return {
                "status": "error",
                "message": (
                    f"task_id '{task_id}' はtask_plannerの正式な計画に存在しません。"
                    "read_project_planで正しいtask_idを確認してください。"
                ),
            }
    if task_id or topic_keyword:
        resolved = _resolve_deliverable_pointer(task_id, topic_keyword)
        if resolved and resolved.startswith("WHITEBOARD:"):
            _, wb_phase_id, wb_task_id = resolved.split(":", 2)
            wb = get_latest_whiteboard(get_active_conn(), _CURRENT_RUN_ID, wb_phase_id, wb_task_id)
            if wb:
                return wb["content"][:10000]
            print(f"  ⚠️ [read_deliverable_file] ホワイトボードが見つかりません: phase={wb_phase_id}, task={wb_task_id}")
            return {"status": "not_found", "message": f"ホワイトボードが見つかりません: phase={wb_phase_id}, task={wb_task_id}"}
        elif resolved and resolved.startswith("FILE_PATH:"):
            file_path = resolved[len("FILE_PATH:"):]
        elif not file_path:
            print(f"  ⚠️ [read_deliverable_file] task_id={task_id!r} topic_keyword={topic_keyword!r} に該当するDeliverableが見つかりませんでした。")
            return {"status": "not_found", "message": f"task_id={task_id!r} topic_keyword={topic_keyword!r} に該当するDeliverableが見つかりませんでした。"}
    if not file_path:
        return {"status": "error", "message": "task_id、topic_keyword、file_pathのいずれかを指定してください。"}
    base_dir = Path("log").resolve()
    try:
        resolved = Path(file_path).resolve()
        resolved.relative_to(base_dir)
    except ValueError:
        return {"status": "error", "message": "logディレクトリ外へのアクセスは禁止されています。"}
    if not resolved.exists() or not resolved.is_file():
        return {"status": "not_found", "message": f"ファイルが見つかりません: {file_path}"}
    try:
        content = resolved.read_text(encoding="utf-8")
        return content[:10000]  # 大量出力防止
    except Exception as e:
        return {"status": "error", "message": str(e)}


def _verify_whiteboard_excerpt_handler(args: dict) -> dict:
    """[BL-079] Detectorが最終JSON出力のtarget_excerptを確定する前に、その引用が現在の
    ホワイトボード本文で一意に一致するかを事前確認できるツール。実際の注釈挿入
    （_annotate_whiteboard_with_detector_comment）と同じ完全一致→正規化緩い一致の
    2段判定ロジックを流用し、ここで「一致する」と確認できたexcerptは事後処理でも
    確実に一致する（挿入自体はdecision_id確定後のdetector_node側で行うため、ここでは
    書き込みは行わずvalidateのみ）。
    """
    excerpt = args.get("excerpt", "")
    if not excerpt:
        return {"ok": False, "reason": "excerptが空文字です"}
    if not _CURRENT_TASK_ID or not _CURRENT_PHASE_ID:
        return {"ok": False, "reason": "現在のタスク/フェーズが特定できませんでした"}
    latest = get_latest_whiteboard(get_active_conn(), _CURRENT_RUN_ID, _CURRENT_PHASE_ID, _CURRENT_TASK_ID)
    if not latest:
        return {"ok": False, "reason": "現在のタスクのホワイトボードが存在しません"}
    content = latest["content"]
    exact_count = content.count(excerpt)
    if exact_count == 1:
        return {"ok": True, "match_type": "exact"}
    norm_content, _ = _normalize_for_loose_match(content)
    norm_excerpt, _ = _normalize_for_loose_match(excerpt)
    loose_count = norm_content.count(norm_excerpt) if norm_excerpt else 0
    if loose_count == 1:
        return {"ok": True, "match_type": "loose"}
    if exact_count == 0:
        reason = f"完全一致0件・正規化後（改行/空白/太字記法/全角半角を無視）の緩い一致も{loose_count}件でした。もっと正確に、または一意になるよう長めに引用し直してください。"
    else:
        reason = f"完全一致が{exact_count}件（一意でない）で、正規化後緩い一致も{loose_count}件でした。前後の文脈を含めて一意に特定できる長さまで引用を伸ばしてください。"
    return {"ok": False, "reason": reason, "exact_count": exact_count, "loose_count": loose_count}


_WHITEBOARD_EXCERPT_DEFAULT_CONTEXT_CHARS = 800  # [BL-193]
_WHITEBOARD_EXCERPT_MAX_CONTEXT_CHARS = 3000  # [BL-193] プロンプト肥大化防止の上限


def _read_whiteboard_excerpt_handler(args: dict, state: dict | None = None) -> dict:
    """[BL-193] write_agreement(edits=...)のold_textを組み立てる前に、Expertが編集対象箇所の
    "現在の"実際の文字列だけをピンポイントで確認できるツール。1514ログ（task_2_1、50KB超の
    ホワイトボード）で、Expertがプロンプトに一度提示された全文の記憶を頼りにold_textを
    再構成し、Detector注釈の埋め込み等で実際の内容と食い違ったまま同じ大きな不一致を
    8回連続で繰り返した事故を受けて追加した。verify_whiteboard_excerpt（BL-079、Detector専用）
    と同じ完全一致→正規化緩い一致の判定を流用するが、あちらは「検証のみ」、こちらは
    「一致した周辺の実際の中身を返す」点が異なる。current_task_id/current_phaseはstate経由で
    取得する（call_expertは_CURRENT_PHASE_IDグローバルを更新しないため、_effective_current_task_id_from/
    _phase_id_fromのstate優先パスに頼る必要がある）。
    """
    keyword = args.get("keyword", "")
    if not keyword:
        return {"ok": False, "reason": "keywordが空文字です"}
    task_id = _effective_current_task_id_from(state)
    phase_id = _phase_id_from(state)
    if not task_id or not phase_id:
        return {"ok": False, "reason": "現在のタスク/フェーズが特定できませんでした"}
    latest = get_latest_whiteboard(get_active_conn(), _run_id_from(state), phase_id, task_id)
    if not latest:
        return {"ok": False, "reason": "現在のタスクのホワイトボードが存在しません"}
    content = latest["content"]

    raw_context_chars = args.get("context_chars") or _WHITEBOARD_EXCERPT_DEFAULT_CONTEXT_CHARS
    try:
        context_chars = max(1, min(int(raw_context_chars), _WHITEBOARD_EXCERPT_MAX_CONTEXT_CHARS))
    except (TypeError, ValueError):
        context_chars = _WHITEBOARD_EXCERPT_DEFAULT_CONTEXT_CHARS

    exact_spans: list[tuple[int, int]] = []
    search_start = 0
    while True:
        pos = content.find(keyword, search_start)
        if pos == -1:
            break
        exact_spans.append((pos, pos + len(keyword) - 1))
        search_start = pos + 1
    match_type = "exact"
    spans = exact_spans
    if len(spans) != 1:
        loose_spans = _find_loose_match_spans(content, keyword)
        if len(loose_spans) == 1:
            match_type = "loose"
            spans = loose_spans
        elif not spans:
            spans = loose_spans
            match_type = "loose"

    if not spans:
        return {
            "ok": False,
            "reason": f"keyword '{keyword}' は現在のホワイトボード内容に見つかりませんでした（完全一致0件・緩い一致0件）。",
            "match_count": 0,
        }
    if len(spans) > 1:
        return {
            "ok": False,
            "reason": (
                f"keyword '{keyword}' は{len(spans)}箇所に一致し一意に特定できません。"
                "より長く一意になる語句（例：見出し全文や前後の固有の文言を含める）で再度指定してください。"
            ),
            "match_count": len(spans),
        }
    start, end = spans[0]
    window_start = max(0, start - context_chars)
    window_end = min(len(content), end + 1 + context_chars)
    prefix = "…（中略）" if window_start > 0 else ""
    suffix = "…（以下省略）" if window_end < len(content) else ""
    return {
        "ok": True,
        "match_type": match_type,
        "version": latest["version"],
        "excerpt": prefix + content[window_start:window_end] + suffix,
    }


# R3a/R3b共通: ツールハンドラのモジュールレベル変数（LangGraphの単一プロセス同期実行前提）
_CURRENT_RUN_ID: str = ""
_CURRENT_CALLER_ROLE: str = ""  # R3b: write_agreementの権限チェック用
_CURRENT_TASK_ID: str = ""      # R3b: confirmed_variablesのsource_task_id用
_CURRENT_PHASE_ID: str = ""     # [BL-079] verify_whiteboard_excerptツールのget_latest_whiteboard参照用
_CURRENT_GOAL_TEXT: str = ""    # [BL-086] revise_goalが編集対象とする現在のgoal本文
_CURRENT_PHASES: list = []      # [BL-104] read_project_planツールが返すstate["phases"]のコピー

# [F-3.1] R3b: 書き込みツール定義
WRITE_AGREEMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "write_agreement",
        "description": (
            "Save a decision, directive, or deliverable to the agreements database. "
            "Always separate What (decision_what) and Why (reason_why). "
            "For numeric claims, include Python REPL verification results in evidence (F-2.6). "
            "[BL-188] Whenever a claim (this entry, or a confirmed_variables entry) is grounded in "
            "something outside your own reasoning -- a web page, the goal text, a prior agreement, "
            "the user's own words -- state that source in 'citations' (top-level) or "
            "confirmed_variables[].citations, rather than leaving it implicit. Prefer authoritative "
            "primary sources over secondary summaries, and prefer up-to-date sources over stale ones, "
            "when multiple are available (cite the more authoritative/recent one, or both if they "
            "disagree). Treat web_search results critically -- a single snippet is not proof; "
            "cross-check surprising or load-bearing numbers against a second source or web_fetch the "
            "primary page before citing it as settled. "
            "Expert can only use status='Proposed'. "
            "User AI can use all statuses. "
            "Detector/Reviewer/Arbiter/Integrator can only use status='Rejected'. "
            "[BL-095] task_planner/goal_essence_analyst can only use status='Proposed' (to record "
            "their own planning/essence-analysis rationale as entry_type='Decision', queryable later "
            "via read_verified_fact/read_deliverable_file). task_plan_reviewer can only use "
            "status='Rejected' (same audit role as Detector/Reviewer). "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "action_type": {
                    "type": "string",
                    "enum": ["CREATE", "UPDATE", "SUPERSEDE"]
                },
                "status": {
                    "type": "string",
                    "enum": ["Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"]
                },
                "topic": {"type": "string", "description": "Brief heading"},
                "decision_what": {
                    "type": "string",
                    "description": (
                        "What was decided/proposed. For entry_type='Deliverable' UPDATE, you may omit this "
                        "(or leave it empty) if you provide 'edits' instead — see 'edits' below."
                    )
                },
                "reason_why": {
                    "type": "string",
                    "description": (
                        "Why adopted or rejected. [BL-050] For UPDATE/SUPERSEDE: must explicitly state what "
                        "changed from the previous value and why (not just why the new value itself is valid) "
                        "-- e.g. '3->2 because task_4_1 found budget insufficient for 3', not just '2 is enough'."
                    )
                },
                "evidence": {"type": "string", "description": "Objective evidence (F-2.6: include Python REPL results for numeric claims)"},
                "citations": {
                    "type": "array",
                    "description": (
                        "[BL-188] Optional. Sources this whole entry (decision_what/reason_why) is "
                        "grounded in, if any (e.g. a web page you fetched, a goal text quote, a prior "
                        "agreements-DB entry, the user's own statement). Omit if this is your own "
                        "reasoning/judgement with no external source."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "type": {
                                "type": "string",
                                "enum": ["web", "goal_text", "prior_agreement", "expert_calculation", "user_input", "document"],
                            },
                            "detail": {"type": "string", "description": "URL (for 'web'), quoted text, agreement id, or a short description of the source."},
                        },
                        "required": ["type", "detail"],
                    },
                },
                "entry_type": {
                    "type": "string",
                    "enum": ["Decision", "Directive", "Deliverable"]
                },
                "phase_id": {"type": "string"},
                "task_id": {"type": "string"},
                "depends_on": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Optional. IDs of EXISTING entries in the 【決定事項DB】(agreements DB) shown in your "
                        "system prompt that this entry builds on — use the bracketed number shown before each "
                        "entry there, e.g. '[42] ...' -> depends_on: ['42']. Do NOT put task_id values here "
                        "(e.g. 'task_1_1') — that is a different concept (the task plan's own depends_on) and "
                        "will be rejected since no such agreements-DB row exists. Omit this field entirely if "
                        "you have no specific prior agreements-DB entry to cite."
                    ),
                },
                "resource_claims": {
                    "type": "object",
                    "description": (
                        "[BL-041] Optional. Only for entries that consume a shared, capped resource "
                        "(e.g. budget, vehicle count) that could conflict with other phases' claims. "
                        "Shape: {\"<constraint name>\": {\"phase_id\": \"<this phase's id>\", "
                        "\"value\": <amount this phase is claiming>, \"total_cap\": <the absolute upper limit "
                        "for this constraint, same across all phases claiming it>}}. Omit entirely if this "
                        "entry does not claim a capped shared resource."
                    )
                },
                "target_topic": {"type": "string", "description": "For UPDATE: the topic to update"},
                "confirmed_variables": {
                    "type": "array",
                    "description": (
                        "Optional. [F-3.9] If this decision confirms one or more values that belong to the "
                        "current task's owns_variables, list them here. Each entry is saved to the structured "
                        "fact store (verified_facts) with its reason and confidence, independent of whether "
                        "decision_extractor_node runs this turn. confidence='provisional' is a fully legitimate "
                        "value — it means 'proceeded with this value for now', not 'this is unverified/wrong'. "
                        "[BL-041] Default to 'provisional' unless this value is an absolute constraint given "
                        "directly in the goal, or the User has explicitly approved it as final."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "variable_name": {"type": "string", "description": "Must match one of the current task's owns_variables"},
                            "value": {"type": "string"},
                            "unit": {"type": "string", "default": ""},
                            "confidence": {"type": "string", "enum": ["confirmed", "provisional"], "default": "provisional"},
                            "citations": {
                                "type": "array",
                                "description": (
                                    "[BL-188] Optional. Source(s) for this specific value, same shape as "
                                    "the top-level 'citations' field. If omitted, this entry's topic is "
                                    "recorded as a fallback (weak signal only -- prefer supplying a real source)."
                                ),
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {"type": "string", "enum": ["web", "goal_text", "prior_agreement", "expert_calculation", "user_input", "document"]},
                                        "detail": {"type": "string"},
                                    },
                                    "required": ["type", "detail"],
                                },
                            },
                        },
                        "required": ["variable_name", "value"]
                    }
                },
                "edits": {
                    "type": "array",
                    "description": (
                        "[R4] For entry_type='Deliverable', action_type='UPDATE' only. Instead of restating "
                        "the full document in decision_what, provide targeted text replacements against the "
                        "CURRENT whiteboard version. Each old_text must match "
                        "exactly (and uniquely, unless replace_all=true) in the current content, or this call "
                        "fails with an error you can fix and retry in the same turn. Do not use this for the "
                        "very first version of a deliverable (use decision_what with action_type='CREATE'). "
                        "[BL-202] Call read_whiteboard_excerpt FIRST to get the exact current text -- never "
                        "reconstruct old_text from memory or from the snapshot in your system prompt, which "
                        "may be stale. Keep each old_text as SHORT as possible (just the line(s) you are "
                        "actually changing, not a whole section), and fix ONE place per call rather than "
                        "batching many replacements: if any single old_text mismatches, the entire edits "
                        "array is rejected and no change is applied. Never include a "
                        "'> [Detector指摘 #...]' annotation block inside an old_text that also covers body "
                        "text -- remove such annotations as their own separate, small edits entry."
                    ),
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_text": {"type": "string", "description": "Exact text to find in the current whiteboard version"},
                            "new_text": {"type": "string", "description": "Replacement text"},
                            "replace_all": {"type": "boolean", "default": False, "description": "Replace every occurrence instead of requiring a unique match"}
                        },
                        "required": ["old_text", "new_text"]
                    }
                }
            },
            "required": ["action_type", "status", "topic", "reason_why", "entry_type"]
        }
    }
}


# [R5 F-8.3] Freeze専用ツール。WRITE_AGREEMENT_TOOL（既に14パラメータで複雑）を汚さない
# 独立した小さなツールとして追加する。「絶対に覆してはならない決定」への恒久ピン留めであり、
# unfreeze機構は設けない（D-044、AGENTS.md§7準拠）。
# ★D-045で一時休止: 検証手段のないまま恒久ピン留めするFreezeより、BL-062（Detectorの誤ったmajor
# 判定がApprovedを覆せず永続化する矛盾）の解消を優先する判断により、User AIのtoolsから外し
# 呼び出し不能にした（本体・is_frozenガード・表示ロジックは削除せず温存、再開時はtools配線を戻すのみ）。
FREEZE_AGREEMENT_TOOL = {
    "type": "function",
    "function": {
        "name": "freeze_agreement",
        "description": (
            "[R5 F-8.3] Permanently pin an existing agreement so it can never be superseded or "
            "updated again. Use only for decisions that must never be reversed (e.g. absolute "
            "budget/constraint values explicitly finalized by the human). This is irreversible "
            "-- there is no unfreeze. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "agreement_id": {
                    "type": "string",
                    "description": "The bracketed ID shown before the agreement in your system prompt, e.g. '[42] ...' -> '42'.",
                },
                "reason": {"type": "string", "description": "Why this decision must be permanently pinned."},
            },
            "required": ["agreement_id", "reason"],
        },
    },
}


def freeze_agreement(conn: sqlite3.Connection, run_id: str, agreement_id: str, reason: str) -> dict:
    """【SLM要約】
    [R5 F-8.3] 指定されたagreementのis_frozenを1に更新し、Freeze自体を監査ログ（decisions）として記録する。
    """
    cur = conn.execute(
        "UPDATE agreements SET is_frozen = 1 WHERE id = ? AND run_id = ?", (agreement_id, run_id)
    )
    if cur.rowcount == 0:
        return {"success": False, "error": f"agreement_id '{agreement_id}' が見つかりません"}
    print(f"  🧊 [Freeze] agreement_id={agreement_id}をFreeze（永久ピン留め）しました。理由: {reason}")
    decision = make_decision(
        who="system_freeze",
        what=f"Agreement {agreement_id} をFreeze（永久ピン留め）",
        why=reason,
    )
    db_append_decision(decision, conn, run_id)
    return {"success": True, "agreement_id": agreement_id}


def _freeze_agreement_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str) -> dict:
    """[R5 F-8.3] freeze_agreementツールの実体。userロールのみ許可（D-044）。"""
    if caller_role != "user":
        return {"success": False, "error": f"{caller_role}はfreeze_agreementを呼び出せません（userロールのみ許可）"}
    agreement_id = args.get("agreement_id", "")
    reason = args.get("reason", "")
    if not agreement_id:
        return {"success": False, "error": "agreement_idは必須です"}
    return freeze_agreement(conn, run_id, agreement_id, reason)


# ===========================================================================
# [BL-086] 前提エスカレーション経路: Expert/User AIが「ゴールの文言上の制約が
# 真の目的（例: 高齢者の移動手段の確保）と矛盾しているのでは」と気づいた場合に、
# BL-025のスコープガードレール（他タスクへの越権禁止）を一切緩めずに、その懸念を
# 構造化して提起し、User AI（発注者役）に却下/承認を判断させる。承認する場合は
# state["goal"]自体を改定し、対応するAgreementをFreezeして、次のDetector監査で
# 同じ論点が無限に再燃するのを防ぐ（BL-062のDetector独立判断とFreezeを両立させる）。
# ===========================================================================
ESCALATE_PREMISE_CONCERN_TOOL = {
    "type": "function",
    "function": {
        "name": "escalate_premise_concern",
        "description": (
            "[BL-086] Raise a narrow, structured concern that a goal's literal constraint/premise "
            "conflicts with the true underlying need it was meant to serve (e.g. a budget cap forcing "
            "a vehicle-size choice that contradicts the service model's own domain logic). This is NOT "
            "a general 'I can't meet this constraint' complaint, and it does NOT grant permission to act "
            "outside your current task's scope or write anything else. It only creates a record for the "
            "User (project owner) to review and decide. You must still complete your current task's "
            "literal acceptance_criteria this turn -- raising this concern is not license to skip them. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "concern_summary": {"type": "string", "description": "One-sentence label for this concern."},
                "implicated_constraint": {"type": "string", "description": "The exact constraint/premise text (quote from the goal or an existing agreement's topic) whose literal framing is in question."},
                "why_conflicts_with_true_need": {"type": "string", "description": "Concretely explain the domain contradiction: why satisfying this constraint literally works against the actual underlying need it exists to serve."},
                "suggested_reframe": {"type": "string", "description": "A concrete alternative framing/premise or constraint value you believe would better serve the true underlying need."},
                "phase_id": {"type": "string", "description": "Optional. Current phase_id."},
                "task_id": {"type": "string", "description": "Optional. Current task_id."},
            },
            "required": ["concern_summary", "implicated_constraint", "why_conflicts_with_true_need", "suggested_reframe"],
        },
    },
}

RESOLVE_PREMISE_CONCERN_TOOL = {
    "type": "function",
    "function": {
        "name": "resolve_premise_concern",
        "description": (
            "[BL-086] Reject an open escalation (raised via escalate_premise_concern): the constraint "
            "stands as-is. Use this when, after consideration, you judge the literal framing is correct "
            "and should not change. Do not call this to accept a reframe -- use revise_goal for that. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "escalation_id": {"type": "string", "description": "The escalation_id shown in your system prompt's Open escalations list."},
                "reason": {"type": "string", "description": "Why the constraint stands; this is shown back so the same concern isn't re-raised without new grounds."},
            },
            "required": ["escalation_id", "reason"],
        },
    },
}

REVISE_GOAL_TOOL = {
    "type": "function",
    "function": {
        "name": "revise_goal",
        "description": (
            "[BL-086] Accept an open escalation: revise the project goal's text to correct the flagged "
            "premise, and (recommended) permanently freeze the agreement that embodies the accepted "
            "exception so Detector does not re-litigate it. If the exception is not yet recorded as an "
            "agreement, call write_agreement first (status='Approved') in this same turn, then call "
            "revise_goal with its id as freeze_agreement_id. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "escalation_id": {"type": "string", "description": "The escalation_id this revision resolves."},
                "edits": {
                    "type": "array",
                    "description": "Targeted text replacements against the CURRENT goal text shown in your system prompt (same mechanism as write_agreement Deliverable edits). Each old_text must match exactly (or uniquely) in the current goal text.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "old_text": {"type": "string"},
                            "new_text": {"type": "string"},
                        },
                        "required": ["old_text", "new_text"],
                    },
                },
                "reason_why": {"type": "string", "description": "Why you are accepting this reframe -- must explain the true underlying need being served."},
                "freeze_agreement_id": {"type": "string", "description": "Optional. The bracketed agreement ID for the Decision/Deliverable embodying this accepted exception. If given, it is frozen (is_frozen=1) as part of this same call."},
            },
            "required": ["escalation_id", "edits", "reason_why"],
        },
    },
}


def db_create_goal_escalation(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
                               raised_by_role: str, concern_summary: str, implicated_constraint: str,
                               why_conflicts: str, suggested_reframe: str) -> str:
    """[BL-086] goal_escalationsへOpen状態で1行INSERTし、escalation_idを返す。"""
    escalation_id = f"ESC-{int(time.time() * 1000)}-{uuid.uuid4().hex[:6]}"
    conn.execute(
        "INSERT INTO goal_escalations (escalation_id, run_id, phase_id, task_id, raised_by_role, "
        "concern_summary, implicated_constraint, why_conflicts, suggested_reframe, status, created_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (escalation_id, run_id, phase_id, task_id, raised_by_role, concern_summary,
         implicated_constraint, why_conflicts, suggested_reframe, "Open", time.time())
    )
    print(f"  🚩 [DB] goal_escalationsへINSERT: escalation_id={escalation_id}, raised_by={raised_by_role}, "
          f"phase={phase_id}, task={task_id}, status=Open")
    return escalation_id


def get_goal_escalation(conn: sqlite3.Connection, run_id: str, escalation_id: str) -> dict | None:
    """[BL-086] 指定escalation_idの1行を返す（存在しなければNone）。"""
    row = conn.execute(
        "SELECT * FROM goal_escalations WHERE escalation_id=? AND run_id=?", (escalation_id, run_id)
    ).fetchone()
    return dict(row) if row else None


def get_open_goal_escalations(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """[BL-086] status='Open'の全エスカレーションを提起順に返す。"""
    rows = conn.execute(
        "SELECT * FROM goal_escalations WHERE run_id=? AND status='Open' ORDER BY created_at ASC", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_latest_goal_draft(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """[BL-126 Stage A] get_latest_whiteboard/get_latest_plan_draftのミラー。goalは
    run_idにつき単一の文書のため、task_id/phase_idは持たずrun_id単独で最新版を検索する。
    存在しなければNone（＝まだ一度もrevise_goal等で版が作られていない状態）。
    """
    row = conn.execute(
        "SELECT version, content FROM goal_drafts WHERE run_id=? ORDER BY version DESC LIMIT 1",
        (run_id,)
    ).fetchone()
    return {"version": row["version"], "content": row["content"]} if row else None


def apply_goal_patch(conn: sqlite3.Connection, run_id: str, new_content: str,
                      author_role: str, edit_summary: str) -> int:
    """[BL-126 Stage A] apply_whiteboard_patch/apply_plan_patchのミラー。現在の最新バージョンを
    取得し、new_contentを新バージョンとしてINSERTする（削除は行わずバージョンを積み増す）。
    呼び出し元（_revise_goal_tool_impl等）が「旧文を残しつつ注釈」の追記ルールに従って
    new_contentを組み立てる責任を持つ（この関数自体は追記かどうかを検証しない）。
    """
    latest = get_latest_goal_draft(conn, run_id)
    new_version = (latest["version"] + 1) if latest else 1
    conn.execute(
        "INSERT INTO goal_drafts (draft_id, version, content, author_role, edit_summary, timestamp, run_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        (f"GD-{int(time.time()*1000)}", new_version, new_content, author_role, edit_summary, time.time(), run_id)
    )
    print(f"  📝 [DB] goal_draftsへINSERT: version={new_version}, author={author_role}, "
          f"edit_summary={str(edit_summary)[:60]}")
    return new_version


def get_latest_scheduling_decision(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """[BL-191] scheduling_draftsの最新1件を返す（get_latest_goal_draftのミラー）。"""
    row = conn.execute(
        "SELECT * FROM scheduling_drafts WHERE run_id=? ORDER BY version DESC LIMIT 1", (run_id,)
    ).fetchone()
    return dict(row) if row else None


def get_scheduling_decision_history(conn: sqlite3.Connection, run_id: str, limit: int = 5) -> list[dict]:
    """[BL-191] Stage4プロンプトへ表示する直近の過去のスケジューリング決定（新しい順）。"""
    rows = conn.execute(
        "SELECT * FROM scheduling_drafts WHERE run_id=? ORDER BY version DESC LIMIT ?", (run_id, limit)
    ).fetchall()
    return [dict(r) for r in rows]


def record_scheduling_decision(conn: sqlite3.Connection, run_id: str, decision_type: str,
                                primary_task_id: str, primary_phase_id: str,
                                companion_task_id: str, companion_phase_id: str,
                                reason: str, author_role: str) -> int:
    """[BL-191] apply_goal_patchのミラー。contentはLLMが手書きするdiffではなく、
    decision_type/primary_task_id/companion_task_id/reasonからシステムが機械的に合成する
    （BL-039のドット/アンダースコア混同バグを避けるため、machine-readable列を主、contentは
    人間/LLMが読む副次的サマリーとして扱う）。バージョンは常に加算のみ（append-only）。"""
    latest = get_latest_scheduling_decision(conn, run_id)
    new_version = (latest["version"] + 1) if latest else 1
    content = (
        f"[v{new_version}] decision_type={decision_type} primary={primary_task_id} "
        f"companion={companion_task_id or '(なし)'} reason={reason}"
    )
    conn.execute(
        "INSERT INTO scheduling_drafts (draft_id, version, content, author_role, decision_type, "
        "primary_task_id, primary_phase_id, companion_task_id, companion_phase_id, reason, "
        "timestamp, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
        (f"SCHED-{int(time.time()*1000)}", new_version, content, author_role, decision_type,
         primary_task_id, primary_phase_id, companion_task_id, companion_phase_id, reason,
         time.time(), run_id)
    )
    print(f"  🗓️ [DB] scheduling_draftsへINSERT: version={new_version}, decision_type={decision_type}")
    return new_version


def _escalate_premise_concern_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str,
                                         caller_role: str, task_id: str) -> dict:
    """[BL-086] escalate_premise_concernの実体。expert/user/facilitatorロールのみ許可
    （detectorや他の監査ロールは対象外——このチャネルは「提起」専用でExpert/User/Facilitatorの
    対話に属する懸念のためのもの）。[BL-126 Stage D] facilitatorはツールループ化により、
    本質対話モードでこの懸念提起を自ら能動的に行えるようになった。"""
    if caller_role not in ("expert", "user", "facilitator"):
        return {"success": False, "error": f"{caller_role}はescalate_premise_concernを呼び出せません"}
    required = ["concern_summary", "implicated_constraint", "why_conflicts_with_true_need", "suggested_reframe"]
    missing = [f for f in required if not args.get(f)]
    if missing:
        print(f"  🚫 [escalate_premise_concern guard] 必須フィールド不足を拒否: caller={caller_role}, missing={missing}")
        return {"success": False, "error": f"必須フィールドが不足: {missing}"}
    escalation_id = db_create_goal_escalation(
        conn, run_id, args.get("phase_id", ""), args.get("task_id") or task_id, caller_role,
        args["concern_summary"], args["implicated_constraint"],
        args["why_conflicts_with_true_need"], args["suggested_reframe"],
    )
    print(f"  🚨 [BL-086] {caller_role}が前提エスカレーションを提起しました（escalation_id={escalation_id}）: {args['concern_summary']}")
    return {"success": True, "escalation_id": escalation_id}


def _resolve_premise_concern_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str) -> dict:
    """[BL-086] resolve_premise_concern（却下）の実体。userロールのみ許可。"""
    if caller_role != "user":
        return {"success": False, "error": f"{caller_role}はresolve_premise_concernを呼び出せません（userロールのみ許可）"}
    escalation_id = args.get("escalation_id", "")
    reason = args.get("reason", "")
    if not escalation_id or not reason:
        return {"success": False, "error": "escalation_id/reasonは必須です"}
    row = get_goal_escalation(conn, run_id, escalation_id)
    if row is None:
        return {"success": False, "error": f"escalation_id '{escalation_id}' が見つかりません"}
    if row["status"] != "Open":
        return {"success": False, "error": f"escalation_id '{escalation_id}' は既にstatus='{row['status']}'です"}
    conn.execute(
        "UPDATE goal_escalations SET status='Rejected', resolution_reason=?, resolved_at=? "
        "WHERE escalation_id=? AND run_id=?",
        (reason, time.time(), escalation_id, run_id)
    )
    print(f"  ❌ [BL-086] エスカレーション{escalation_id}を却下しました（制約は現状維持）。理由: {reason}")
    decision = make_decision(who="user", what=f"エスカレーション{escalation_id}を却下（制約は現状維持）", why=reason)
    db_append_decision(decision, conn, run_id)
    return {"success": True, "escalation_id": escalation_id}


def _revise_goal_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str) -> dict:
    """[BL-086] revise_goal（承認・ゴール改定）の実体。userロールのみ許可。
    DB側の副作用（escalation status更新／freeze／goal_shift_events／decision）はここで完結させ、
    LangGraph state["goal"]への反映のみを、呼び出し元ノードが戻り値経由で行う
    （_LAST_GOAL_REVISIONブリッジ、ツールハンドラはstateへ直接触れられないため）。
    """
    if caller_role != "user":
        return {"success": False, "error": f"{caller_role}はrevise_goalを呼び出せません（userロールのみ許可）"}
    escalation_id = args.get("escalation_id", "")
    edits = args.get("edits") or []
    reason_why = args.get("reason_why", "")
    freeze_agreement_id = args.get("freeze_agreement_id", "")
    if not escalation_id or not edits or not reason_why:
        return {"success": False, "error": "escalation_id/edits/reason_whyは必須です"}

    row = get_goal_escalation(conn, run_id, escalation_id)
    if row is None:
        return {"success": False, "error": f"escalation_id '{escalation_id}' が見つかりません"}
    if row["status"] != "Open":
        return {"success": False, "error": f"escalation_id '{escalation_id}' は既にstatus='{row['status']}'として解決済みです"}

    new_content, err = _apply_text_edits(_CURRENT_GOAL_TEXT, edits, content_label="現在のゴール文")
    if err:
        return {"success": False, "error": err}

    # [BL-126 Stage A] state["goal"]自体は従来通り「現在有効な本文」を保持するのみだが、
    # 全文履歴をgoal_draftsへも記録する（whiteboard_drafts/plan_draftsと同型のappend-only
    # バージョニング）。既存の反応的revise_goal経路にも先行して適用し、Stage D以降の
    # Essence Dialogue収束フロー着手前に動作確認しておく（design.md §8実装順序）。
    apply_goal_patch(conn, run_id, new_content, author_role="user",
                      edit_summary=f"Escalation {escalation_id} 承認による改定")
    print(f"  ✏️ [BL-086] revise_goal: escalation_id={escalation_id}承認によりゴール文を改定しました。")

    if freeze_agreement_id:
        freeze_result = freeze_agreement(conn, run_id, freeze_agreement_id,
                                          reason=f"[Escalation {escalation_id} accepted] {reason_why}")
        if not freeze_result.get("success"):
            return {"success": False, "error": f"freeze失敗: {freeze_result.get('error')}"}

    conn.execute(
        "UPDATE goal_escalations SET status='Accepted', resolution_reason=?, resolved_agreement_id=?, resolved_at=? "
        "WHERE escalation_id=? AND run_id=?",
        (reason_why, freeze_agreement_id or "", time.time(), escalation_id, run_id)
    )
    shift = {
        "shift_kind": "premise_revision",
        "from_goal_state": _CURRENT_GOAL_TEXT,
        "to_goal_state": new_content,
        "reason_why": reason_why,
        "evidence": f"Escalation {escalation_id}: {row['concern_summary']}",
        "triggered_by": "Escalation_Resolution",
        "triggering_agreement_id": freeze_agreement_id or "",
    }
    db_append_goal_shift_event(shift, conn, run_id)
    decision = make_decision(who="user", what=f"ゴール制約を改定（Escalation {escalation_id} 承認）", why=reason_why)
    db_append_decision(decision, conn, run_id)

    # [BL-163] ゴール改定成功時、既に承認済みの過去タスクは旧ゴールの前提で成果物が
    # 作られているため、新ゴールとの整合性を再確認すべき対象として機械的に起票する。
    # 全面リスタートではなく、既存のSUPERSEDE改訂・issue解決フローに乗せて前進しながら
    # 修正する設計（ユーザー判断）。severity="minor"（open）に留め、BL-136の強制
    # RESOLVE/DEFER（major/escalated対象）は発動させない——無関係な現在タスク遂行中に
    # 毎ターン催促されるのを避けるため。
    _seen_tasks: set[tuple[str, str]] = set()
    _flagged: list[tuple[str, str]] = []
    for a in reversed(get_agreements_from_db(conn, run_id)):
        if a.get("entry_type") != "Deliverable":
            continue
        key = (a.get("phase_id", ""), a.get("task_id", ""))
        if not key[1] or key in _seen_tasks:
            continue
        _seen_tasks.add(key)
        if a.get("status") in RESOLVING_DELIVERABLE_STATUSES:
            _flagged.append(key)
    # [BL-186] BL-163が起票したissueは意図的にseverity="minor"のまま据え置かれ、BL-136/BL-145の
    # 強制解決ルート（major/escalated専用）には乗らない。read_issuesはpull型ツールであり、
    # LLMが自発的に呼ばない限りどのプロンプトにも自動注入されないため（Reflection/Integratorも
    # 見ていない）、この13件が誰にも参照されないまま放置されるリスクが実ドライラン
    # （`log/2026-08-06/1432`、phase6/task_6_1＝計画上の最終タスクで発生、通常のタスク遷移では
    # phase1-5へ戻る経路が無い）で確認された。BL-145（滞留escalated issueをplan_revision_reason
    # 経由でtask_plannerへ強制引き継ぐ既存の仕組み）と同型の配線を、ここでも使う。
    _flagged_issue_ids: list[str] = []
    for _phase_id, _task_id in _flagged:
        _issue_result = _write_issue_impl(
            {
                "action_type": "CREATE",
                "topic": f"goal_revision_consistency_check_{_phase_id}_{_task_id}",
                "severity": "minor",
                "description": (
                    f"ゴール改定（Escalation {escalation_id}承認、理由: {reason_why}）により、"
                    "このタスクの成果物は旧ゴール文の前提に基づいています。新ゴールとの整合性を"
                    "再確認してください。"
                ),
            },
            conn, run_id, "revise_goal_auto", _phase_id, _task_id,
        )
        if isinstance(_issue_result, dict) and _issue_result.get("success") and _issue_result.get("id"):
            _flagged_issue_ids.append(_issue_result["id"])
    if _flagged:
        print(f"  🧭 [BL-163] ゴール改定に伴い、承認済み過去タスク{len(_flagged)}件へ整合性再確認issueを起票しました: {[t for _, t in _flagged]}")

    # [BL-186] plan_revision_reason/plan_revision_issue_idsを組み立てる。呼び出し元
    # ノード（generate_user_utterance_node）が_LAST_GOAL_REVISION経由で受け取り、
    # BL-145と同じ配線でtask_plannerを強制的に再発火させる（新規task/phaseの追加を促す）。
    _plan_revision_reason = ""
    if _flagged:
        _reason_lines = [
            f"- phase_id={_phase_id}, task_id={_task_id}, "
            f"topic=goal_revision_consistency_check_{_phase_id}_{_task_id}"
            + (f", issue_id={_issue_id}" if _issue_id else "")
            for (_phase_id, _task_id), _issue_id in zip(_flagged, _flagged_issue_ids + [""] * (len(_flagged) - len(_flagged_issue_ids)))
        ]
        _plan_revision_reason = (
            f"[BL-186] ゴール改定（Escalation {escalation_id}承認、理由: {reason_why}）により、"
            "以下の承認済み過去タスクは新ゴールとの整合性が未確認です。新規フェーズ（例: "
            "phase7以降）として、各タスクの成果物が新ゴールの制約を満たすか再検証し、必要な"
            "修正を行うタスクを計画に追加してください。既存フェーズの内容は書き換えないで"
            "ください（無関係な既存タスクへの影響を避けるため）:\n"
            + "\n".join(_reason_lines)
        )

    # [BL-168] BL-163はagreements（成果物）のみを対象にしており、verified_facts（read_verified_fact
    # で参照される「確定済みの定数」ストア）は対象外だった。upsert_verified_factは(run_id,
    # variable_name)のUPSERT方式で、該当変数が再度upsert_verified_factされない限り、ゴール改定で
    # 前提が変わったことを示す仕組みが一切なく永久に「現在の確定値」として返り続ける。実ログで、
    # ゴール改定前にtask_1_1が確定したmax_vehicle_count='2'等が、改定後も無警告で後続ノードに
    # 供給され続けていたことを確認した。BL-163が既に列挙した_flagged（影響を受ける過去タスク）を
    # そのまま再利用し、該当task_idをsource_task_idに持つverified_facts行のreasonへ警告を付記する
    # （valueは過去の事実として正しいため改変しない）。
    if _flagged:
        _stale_marker = "⚠️[BL-168: ゴール改定後未確認] "
        _flagged_task_ids = sorted({t for _, t in _flagged})
        _placeholders = ",".join("?" for _ in _flagged_task_ids)
        _fact_rows = conn.execute(
            f"SELECT variable_name, source_task_id, reason FROM verified_facts "
            f"WHERE run_id=? AND source_task_id IN ({_placeholders})",
            (run_id, *_flagged_task_ids),
        ).fetchall()
        _marked_count = 0
        for _row in _fact_rows:
            _old_reason = _row["reason"] or ""
            if _old_reason.startswith(_stale_marker):
                continue  # 既にマーキング済み（同一runで複数回ゴール改定された場合の重複防止）
            _new_reason = (
                f"{_stale_marker}このtask_id（{_row['source_task_id']}）の確定値はゴール改定"
                f"（Escalation {escalation_id}）前の前提に基づいています。無条件に信頼せず、"
                f"整合性を再確認してください。\n{_old_reason}"
            )
            conn.execute(
                "UPDATE verified_facts SET reason=? WHERE run_id=? AND variable_name=?",
                (_new_reason, run_id, _row["variable_name"]),
            )
            _marked_count += 1
        if _marked_count:
            print(f"  🧭 [BL-168] ゴール改定に伴い、承認済み過去タスクのverified_facts {_marked_count}件へ整合性未確認の警告を付記しました。")

        # [BL-204] entity_attributesもverified_factsと同じ性質（UPSERTで上書きされない限り
        # 「現在の確定値」として返り続ける）を持つため、BL-168と同じ扱いを適用する。
        # 新しい扱いを発明せず先例へ揃える（設計書§6決定4）。valueは過去の事実として
        # 正しいので改変せず、reasonへ警告を付記するだけに留めるのも同じ。
        _attr_rows = conn.execute(
            f"SELECT entity_id, attr_name, source_task_id, reason FROM entity_attributes "
            f"WHERE run_id=? AND source_task_id IN ({_placeholders})",
            (run_id, *_flagged_task_ids),
        ).fetchall()
        _marked_attrs = 0
        for _row in _attr_rows:
            _old_reason = _row["reason"] or ""
            if _old_reason.startswith(_stale_marker):
                continue
            _new_reason = (
                f"{_stale_marker}このtask_id（{_row['source_task_id']}）で記録した属性は"
                f"ゴール改定（Escalation {escalation_id}）前の前提に基づいています。"
                f"無条件に信頼せず、整合性を再確認してください。\n{_old_reason}"
            )
            conn.execute(
                "UPDATE entity_attributes SET reason=? WHERE run_id=? AND entity_id=? AND attr_name=?",
                (_new_reason, run_id, _row["entity_id"], _row["attr_name"]),
            )
            _marked_attrs += 1
        if _marked_attrs:
            print(f"  🧭 [BL-204] ゴール改定に伴い、entity_attributes {_marked_attrs}件へ整合性未確認の警告を付記しました。")

    return {
        "success": True, "escalation_id": escalation_id,
        "new_goal_text": new_content, "old_goal_text": _CURRENT_GOAL_TEXT,
        "frozen_agreement_id": freeze_agreement_id or None,
        "plan_revision_reason": _plan_revision_reason,
        "plan_revision_issue_ids": _flagged_issue_ids,
    }


# ===========================================================================
# [BL-130] Expert相談チャネル: Expertが成果物を出さずにUser AIへ質問できる
# 双方向チャネル。従来はUser→Expertへの一方向指示のみで、Expertが疑問点を
# 抱えたまま見切り発車で成果物を作らざるを得なかった（BL126_basic_design.md §2参照）。
# ===========================================================================
ASK_USER_QUESTION_TOOL = {
    "type": "function",
    "function": {
        "name": "ask_user_question",
        "description": (
            "[BL-130] Declare that this turn is a QUESTION to the User (project owner), not a "
            "deliverable. Use this when you genuinely cannot proceed with the current task's "
            "acceptance_criteria without the User's direction (e.g. an ambiguous requirement, a "
            "choice between materially different approaches that only the project owner can "
            "decide). This is NOT a substitute for escalate_premise_concern (goal-text premise "
            "conflicts) and NOT a way to avoid producing a deliverable when you actually have "
            "enough information to proceed -- calling this skips the usual detector/decision-"
            "extractor audit for this turn, so use it only when a real blocking question exists. "
            "[BL-110] Optionally call `think` (with a `summary`) alongside this or any other tool call "
            "to record your reasoning -- it is no longer required, and other tool calls are no "
            "longer rejected for omitting it."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "question_text": {"type": "string", "description": "The question to put to the User (project owner)."},
                "blocking_reason": {"type": "string", "description": "Why you cannot proceed with this task's acceptance_criteria without an answer."},
            },
            "required": ["question_text", "blocking_reason"],
        },
    },
}


def _ask_user_question_tool_impl(args: dict, caller_role: str) -> dict:
    """[BL-130] ask_user_questionの実体。expertロールのみ許可。DB書き込みは行わず、
    _LAST_ASK_USER_QUESTIONへ質問内容を記録するのみ（get_last_ask_user_questionブリッジ、
    _LAST_GOAL_REVISION等と同じパターン。expert_node が戻り値経由でstateへ反映する）。
    """
    if caller_role != "expert":
        return {"success": False, "error": f"{caller_role}はask_user_questionを呼び出せません（expertロールのみ許可）"}
    question_text = args.get("question_text", "")
    blocking_reason = args.get("blocking_reason", "")
    if not question_text or not blocking_reason:
        return {"success": False, "error": "question_text/blocking_reasonは必須です"}
    global _LAST_ASK_USER_QUESTION
    _LAST_ASK_USER_QUESTION = {"question_text": question_text, "blocking_reason": blocking_reason}
    return {"success": True, "question_text": question_text}


def _check_write_permission(args: dict, caller_role: str, conn: sqlite3.Connection | None = None,
                             run_id: str = "", task_id: str = "", phase_id: str = "") -> str | None:
    """[F-3.2] 権限チェック: ロール×status許可表を全組み合わせで判定する。
    ExpertはProposedのみ、User AIは全status、Detector/Reviewer/Arbiter/IntegratorはRejectedのみ。
    [BL-095] task_planner/goal_essence_analystはExpert同様、自らの計画・本質分析の判断根拠を
    Proposed（提案・未承認）としてのみ記録できる（後続のtask_plan_reviewer/実行がこれを覆しうる
    ため、Approvedを名乗らせない）。task_plan_reviewerはDetector/Reviewer等と同じ監査役として
    Rejectedのみ許可し、既存のBL-062 SUPERSEDEパターン（誤りと判定した既存記録をRejectedで
    無効化する）を踏襲する。
    [BL-172] `conn`/`run_id`/`task_id`/`phase_id`は「承認対象のDeliverableが実在するか」の
    DB照会に使う任意引数（`_write_agreement_impl`からのみ渡される）。`conn`を渡さない既存の
    純粋呼び出し（テスト等）では、この照会を伴う分岐はスキップされ従来通りの挙動を維持する。
    """
    ALLOWED_STATUS_BY_ROLE = {
        "expert": {"Proposed"},
        "user": {"Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"},
        "detector": {"Rejected"},
        "reviewer": {"Rejected"},
        "arbiter": {"Rejected"},
        "integrator": {"Rejected"},
        "task_planner": {"Proposed"},
        "goal_essence_analyst": {"Proposed"},
        "task_plan_reviewer": {"Rejected"},
        # [BL-126 Stage D] Facilitatorは本質対話の開始提起（entry_type="EssenceProposal"）を
        # Proposedとしてのみ記録できる（task_planner/goal_essence_analystと同型：最終承認は
        # 発注者であるUser AIの役目であり、Facilitator自身がApprovedを名乗ることはない）。
        "facilitator": {"Proposed"},
    }
    status = args.get("status")
    allowed = ALLOWED_STATUS_BY_ROLE.get(caller_role, set())
    if status not in allowed:
        print(f"  🚫 [write_agreement permission] {caller_role}によるstatus='{status}'の書き込みを拒否しました（許可: {sorted(allowed)}）。")
        return f"{caller_role}はstatus='{status}'を書き込めません（許可: {sorted(allowed)}）"

    # [BL-169] Userは成果物のレビュー・承認・却下役であり、entry_type="Deliverable"の新規作成
    # （action_type="CREATE"）はExpertの役目。ここを塞がないと、User自身が成果物を執筆し
    # 自ら承認まで完結でき、Expert↔Detectorの査読ループを丸ごと迂回できてしまう
    # （実ログ`log/2026-08-04/1548`で観測、Reflectionが"collusion"と判定したstagnation原因の一つ）。
    # UPDATE/SUPERSEDE（既存Deliverableへのstatus変更・訂正指示）は従来通り許可する。
    if caller_role == "user" and args.get("entry_type") == "Deliverable" and args.get("action_type") == "CREATE":
        print("  🚫 [write_agreement permission][BL-169] userによるentry_type='Deliverable'のCREATEを拒否しました（成果物の新規作成はExpertの役目です）。")
        return "userはentry_type='Deliverable'をaction_type='CREATE'で新規作成できません（成果物の作成はExpertへ指示してください）"

    # [BL-172] BL-169はentry_type="Deliverable"のCREATEのみを塞いでいたが、実ドライラン
    # （`log/2026-08-04/2316`）で、userがそれを拒否された直後、全く同じ内容のままentry_typeだけ
    # "Decision"へ変えて再送し、そのまま通ってしまう回避策が観測された。BL-169自体は正しく
    # 機能したが、「userがExpertの仕事を代行して完了を宣言する」という根本行動は防げていなかった。
    # ホワイトボードファイル書き出し（apply_whiteboard_patch）はentry_type="Deliverable"の時
    # にしか発火しないため、この回避策ではホワイトボード.mdが一切生成されないまま、タスクだけが
    # Approved扱いになってDBに残っていた（ユーザー報告）。
    # 正当なUserの承認は、常に「既存（Expert作成）のDeliverableをUPDATEでApproved等へ変更する」
    # 形を取り、CREATEで承認系statusのエントリを新規に持ち込む正規の使い方は（entry_typeを
    # 問わず）存在しない。そこでentry_type単位の判定ではなく、「承認しようとしているtask_idに
    # Expert作成のDeliverableが実在するか」で一般化する。
    if (conn is not None and caller_role == "user" and args.get("action_type") == "CREATE"
            and args.get("status") in RESOLVING_DELIVERABLE_STATUSES):
        effective_task_id = args.get("task_id") or task_id
        effective_phase_id = args.get("phase_id") or phase_id
        if effective_task_id and _find_active_deliverable_agreement(conn, run_id, effective_phase_id, effective_task_id) is None:
            print(
                f"  🚫 [write_agreement permission][BL-172] userによるtask_id='{effective_task_id}'への"
                f"CREATE（status='{args.get('status')}'）を拒否しました（Expert作成のDeliverableがまだ存在しません）。"
            )
            return (
                f"task_id='{effective_task_id}'にはExpert作成のDeliverableがまだ存在しないため、"
                f"userはstatus='{args.get('status')}'で新規承認を作成できません（Expertへ成果物の提出を指示してください）"
            )

    return None


def _check_issue_permission(args: dict, caller_role: str) -> str | None:
    """[BL-096] write_issueの権限チェック。MVPではdetectorはCREATEのみ、userはCREATE/RESOLVE/DEFER
    全て許可する。issueを実際に解決済み・先送り済みと判断する役目はUser AI（ユーザー側の代理）である
    という設計判断（ユーザー指摘）による。Reviewer/Arbiter/Integratorへの拡張は将来課題。
    [BL-136] DEFERはRESOLVEと同じくuserのみ許可（明示的な先送り判断もユーザー側の代理が行う）。
    [BL-154] decision_extractor_autoはdecision_extractor_nodeのPython側自動起票専用（Expert/Userが
    「〇〇は次タスクで扱う」と宣言した際、agreements Directive/Deferredと同時にissue_logへも橋渡し
    する）。Expert自身にwrite_issueツールを新規付与するのではなく、既存の自動抽出経路にPython側で
    相乗りさせるための内部専用ロール——LLMツール呼び出し経路からは到達不能（WRITE_ISSUE_TOOLの
    スキーマ自体は無変更）。
    """
    ALLOWED_ISSUE_ACTIONS_BY_ROLE = {
        "detector": {"CREATE"},
        "user": {"CREATE", "RESOLVE", "DEFER", "ACKNOWLEDGE"},  # [BL-194] ACKNOWLEDGEもuserのみ許可
        "detector_auto": {"CREATE"},  # [BL-096] detector_nodeのPython側自動バックアップ書き込み専用
        "decision_extractor_auto": {"CREATE"},  # [BL-154] decision_extractor_nodeのPython側自動起票専用
        "revise_goal_auto": {"CREATE"},  # [BL-163] revise_goal成功時のPython側自動起票専用
    }
    action_type = args.get("action_type")
    allowed = ALLOWED_ISSUE_ACTIONS_BY_ROLE.get(caller_role, set())
    if action_type not in allowed:
        print(f"  🚫 [write_issue permission] {caller_role}によるaction_type='{action_type}'の実行を拒否しました（許可: {sorted(allowed)}）。")
        return f"{caller_role}はaction_type='{action_type}'のwrite_issueを実行できません（許可: {sorted(allowed)}）"
    return None


def _find_active_deliverable_agreement(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str) -> dict | None:
    """[BL-084] entry_type="Deliverable"のagreementを、topic文字列ではなくtask_idで一意に
    識別する（whiteboard_draftsと同じ識別子）。BL-074で発覚した「Expertが呼び出しごとに
    topicの言い回しを変え、target_topic省略時のフォールバック（=自分自身のtopic）が既存行と
    一致せずold_content/supersede対象を見失う」問題は、target_excerptの緩い一致（BL-081）を
    いくら強化しても直らない（比較対象のbase_contentがそもそも空文字になるため）。1459ドライラン
    で同一task_2_4に対しUPDATE呼び出しごとにtopicが変化し（"...確率論的リスク反映版"→
    "...結論部の数値整合性修正"→"...確率論的リスク反映・修正版"）、2回とも`edits`が
    「完全一致0件・緩い一致も0件」で失敗する実害を確認した。

    ★修正（BL-206）: 従来は`phase_id`も完全一致条件に含めていたため、呼び出し元が渡す
    phase_idが（decision_extractor_node側のフォールバック欠陥等により）空文字や別値へ
    ドリフトすると、実在するアクティブなDeliverableを発見できずtarget=None・
    old_content=""のまま以降のeditsが必ず0件一致で失敗し続けていた（実ログでentry_type
    ドリフトと合わせ計3タスクで確認）。`get_latest_whiteboard`（BL-131）が既に採用している
    「task_idはrun_id内で一意という規約を前提に、phase_idはWHERE句に含めず、食い違いが
    あれば警告のみ行う」という同じ設計へ揃え、phase_idドリフトがあっても孤児化しないよう
    フェイルセーフ化する。
    """
    for a in reversed(get_agreements_from_db(conn, run_id)):
        if (a.get("entry_type") == "Deliverable" and a.get("task_id") == task_id
                and a.get("status") != "Superseded"):
            if phase_id and a.get("phase_id") and a.get("phase_id") != phase_id:
                print(f"  ⚠️ [Deliverable phase_id不一致] task_id='{task_id}'の既存Deliverableは"
                      f"phase_id='{a.get('phase_id')}'で保存されていますが、今回'{phase_id}'が"
                      f"渡されました。task_idの命名規約により正しい版として扱いますが、"
                      f"呼び出し元の引数を確認してください。")
            return a
    return None


def _commit_agreement_from_tool(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str, task_id: str = "", phase_id: str = "") -> tuple[str | None, str | None]:
    """[F-3.1] write_agreementツールからDBへagreementをコミットする。
    action_type=SUPERSEDEの場合は既存レコードをSupersededに更新する。
    戻り値: (error, protected_warning)のタプル。errorが非Noneなら失敗（呼び出し元
    _write_agreement_implはDBに何もコミットせずこのメッセージをそのままLLMへのエラーとして返す）。
    成功時はerror=None。protected_warningは、呼び出し自体は成功したがホワイトボード本体への
    実際の反映が「保護」によりスキップされた場合（BL-127）に、その旨を呼び出し元へ伝える
    ための非エラーの警告文字列（通常はNone）。

    [BL-127] 従来は戻り値がNone一択のため、「保護によりホワイトボード未反映のままDB上は
    成功扱い」というケースと「実際に反映された成功」が呼び出し元・LLMの双方から区別できず、
    Expertが「修正が正常に適用された」と誤って自己申告する実インシデントが発生していた
    （実際にはホワイトボード本文に旧値が残存）。

    ★修正（R4）: per-taskのDeliverableはファイル保存（save_deliverable_to_file、旧H2/BL-040対応）
    ではなく、whiteboard_drafts（バージョン管理済みDB格納）へ移行した。ExpertはCREATE時に
    decision_whatで初版を送り、以降のUPDATEはedits（old_text/new_text）で差分のみ送れる。
    save_deliverable_to_file/_archive_old_deliverable_fileは、1回限りで版管理が不要な
    integrator_nodeの最終統合文書向けにそのまま残す（本関数では使わない）。

    ★修正（BL-040）: agreements.task_id列は従来args.get("task_id")のみに依存していたが、
    WRITE_AGREEMENT_TOOLのスキーマ上task_idは任意項目でありLLMが省略することが多いため、
    read_deliverable_fileのtask_idによる逆引き（_resolve_deliverable_file_path）が機能しない
    ケースが多かった。_CURRENT_TASK_IDから伝播されるtask_id引数をフォールバックとして使う。
    """
    action_type = args.get("action_type", "CREATE")
    entry_type = args.get("entry_type", "Decision")
    topic = args.get("topic", "")
    raw_content = args.get("decision_what", "")
    # [BL-161] 従来はargsにphase_idが無ければ空文字のまま（フォールバックなし）だった。
    # tidと異なりphase_idには呼び出し元からのフォールバックが一切なかったため、Expertが
    # write_agreementのUPDATE呼び出しでphase_idを省略すると_find_active_deliverable_agreement
    # が空文字と一致するレコードを見つけられずtarget=None・old_content=""のまま、以降の
    # editsが必ず0件一致で失敗し続けていた（実ログで11回連続失敗を確認）。tidと同じ
    # パターンでフォールバックを追加する。
    phase_id = args.get("phase_id") or phase_id
    if not args.get("phase_id") and phase_id:
        print(f"  ℹ️ [write_agreement] phase_id省略を検知、呼び出し元の現在フェーズ'{phase_id}'へフォールバックしました（BL-161）。")
    tid = args.get("task_id") or task_id
    # [BL-127] ホワイトボードへの実反映がスキップされた（保護された）場合の非エラー警告。
    protected_warning: str | None = None

    if action_type == "SUPERSEDE":
        # [BL-084] Deliverableはtopic文字列ドリフトの影響を受けるため(phase_id, task_id)で識別する。
        # Decision/Directiveは従来通りtopicベース（BL-084のスコープ外、影響範囲を限定）。
        if entry_type == "Deliverable":
            target = _find_active_deliverable_agreement(conn, run_id, phase_id, tid)
        else:
            target_topic = args.get("target_topic", topic)
            target = next(
                (a for a in reversed(get_agreements_from_db(conn, run_id))
                 if a["topic"] == target_topic and a.get("status") != "Superseded"),
                None,
            )
        if target is not None:
            # [R5 F-8.3/D-044] Freeze済み（is_frozen=1）のagreementは恒久ピン留めのため、
            # SUPERSEDEを拒否する（unfreeze機構は設けない設計）。
            if target.get("is_frozen"):
                print(f"  🧊🚫 [Freeze] topic '{target['topic']}'（agreement_id={target['id']}）はFreeze済みのためSUPERSEDEを拒否しました。")
                return f"topic '{target['topic']}' はFreeze済みのため変更できません（agreement_id={target['id']}）", None
            db_supersede_agreement(target["id"], conn, run_id)
        # [BL-080] 以前はここで`return None`しており、旧レコードのstatus変更のみで処理が終わっていた。
        # ExpertがDeliverableの全文置換のためSUPERSEDE+decision_what（全文）を送っても、その内容は
        # 完全に破棄され、ホワイトボードには一切反映されないまま「成功」を返す実質何もしない
        # ツール呼び出しになっていた（1319ドライランで発覚、Expertがこれを「システムの反映
        # タイミング問題」と誤って自己正当化するハルシネーションループの真因だった）。
        # BL-062のDetectorによる無効化用途（短い理由文のみ、ホワイトボードには触れない）との
        # 後方互換は、下記のlen(raw_content) > 200の閾値（CREATE/UPDATE全文置換と同一基準）で
        # 保つ。ここではreturnせず、CREATE/UPDATE共通のホワイトボード保存・agreements行INSERT
        # 処理へ続ける。

    depends_on_val = json.dumps(args.get("depends_on", []), ensure_ascii=False) if isinstance(args.get("depends_on"), (list, dict)) else (args.get("depends_on") or "[]")
    resource_claims_val = json.dumps(args.get("resource_claims", {}), ensure_ascii=False) if isinstance(args.get("resource_claims"), (list, dict)) else (args.get("resource_claims") or "{}")

    # [R4] Deliverableのホワイトボード保存
    global _LAST_WHITEBOARD_EDIT
    content = raw_content
    if entry_type == "Deliverable" and action_type in ("CREATE", "SUPERSEDE") and len(raw_content) > 200:
        edit_summary = "初版作成" if action_type == "CREATE" else (args.get("reason_why", "") or "SUPERSEDEによる全文置換")
        v = apply_whiteboard_patch(conn, run_id, phase_id, tid, raw_content, author_role=caller_role, edit_summary=edit_summary)
        _LAST_WHITEBOARD_EDIT = {"phase_id": phase_id, "task_id": tid, "version": v}
        content = f"WHITEBOARD:{phase_id}:{tid}"
        if action_type == "CREATE":
            print(f"  📋 [Whiteboard] write_agreement経由の成果物 '{topic}' をwhiteboard_drafts Ver.1として保存しました（phase={phase_id}, task={tid}）。")
        else:
            print(f"  📋 [Whiteboard] write_agreement(SUPERSEDE)経由で '{topic}' の全文をwhiteboard_drafts Ver.{v}として保存しました（phase={phase_id}, task={tid}）。")

    if action_type == "UPDATE":
        # [BL-084] SUPERSEDE分岐と同じ理由でDeliverableのみ(phase_id, task_id)で識別する。
        if entry_type == "Deliverable":
            target = _find_active_deliverable_agreement(conn, run_id, phase_id, tid)
            target_topic = target["topic"] if target else topic
            old_content = ""
            if target is not None:
                # [R5 F-8.3/D-044] Freeze済みのagreementはUPDATEも拒否する（SUPERSEDEと同様）。
                if target.get("is_frozen"):
                    print(f"  🧊🚫 [Freeze] topic '{target_topic}'（agreement_id={target['id']}）はFreeze済みのためUPDATEを拒否しました。")
                    return f"topic '{target_topic}' はFreeze済みのため変更できません（agreement_id={target['id']}）", None
                old_content = target["decision_what"]
        else:
            target = None
            target_topic = args.get("target_topic", topic)
            old_content = ""
            for a in reversed(get_agreements_from_db(conn, run_id)):
                if a["topic"] == target_topic and a.get("status") != "Superseded":
                    # [R5 F-8.3/D-044] Freeze済みのagreementはUPDATEも拒否する（SUPERSEDEと同様）。
                    if a.get("is_frozen"):
                        print(f"  🧊🚫 [Freeze] topic '{target_topic}'（agreement_id={a['id']}）はFreeze済みのためUPDATEを拒否しました。")
                        return f"topic '{target_topic}' はFreeze済みのため変更できません（agreement_id={a['id']}）", None
                    old_content = a["decision_what"]
                    break
        if entry_type == "Deliverable":
            edits = args.get("edits")
            # [BL-212] 従来はold_content（直前の「有効」なagreements行のdecision_what）が
            # "WHITEBOARD:"で始まるかどうかで判定していたが、action_type=SUPERSEDEにBL-062の
            # 「ホワイトボードには触れない短い無効化理由文」（raw_content<=200字）が渡されると、
            # 下のSUPERSEDE分岐（本関数冒頭）はapply_whiteboard_patchを呼ばずcontent=raw_content
            # のまま新しい「有効」行を作る。結果、次にこのUPDATEへ来たときのold_contentはその短い
            # 理由文そのものであり、WHITEBOARD:プレフィックスを失っている。is_whiteboard=Falseと
            # 誤判定されるため、base_content=old_content（短い理由文）に対してExpertの実際の
            # ホワイトボード引用（whiteboard_drafts側には無傷で残っている）を照合してしまい、
            # editsが必ず0件一致で失敗し続ける（実インシデント: log/2026-08-11/1034、
            # write_agreement(edits=...)が17回連続失敗）。BL-131・BL-206と同じ設計方針
            # （task_idを権威とし、agreements側の文字列表現は当てにしない）に揃え、
            # whiteboard_draftsに実際にバージョンが存在するかどうかを直接判定する。
            is_whiteboard = get_latest_whiteboard(conn, run_id, phase_id, tid) is not None
            if edits:
                # editsが指定された場合、ホワイトボード済みならその最新版、未昇格の短文ならold_content自体を
                # 編集対象のベースとする（どちらの場合も編集後はwhiteboard_draftsへ格納・昇格させる）。
                if is_whiteboard:
                    latest = get_latest_whiteboard(conn, run_id, phase_id, tid)
                    base_content = latest["content"] if latest else None
                else:
                    base_content = old_content
                if base_content is None:
                    return f"更新対象のホワイトボード（phase={phase_id}, task={tid}）が見つかりません。", None
                merged, err = _apply_text_edits(base_content, edits)
                if err:
                    return err, None
                v = apply_whiteboard_patch(conn, run_id, phase_id, tid, merged, author_role=caller_role,
                                            edit_summary=args.get("reason_why", ""))
                _LAST_WHITEBOARD_EDIT = {"phase_id": phase_id, "task_id": tid, "version": v}
                content = f"WHITEBOARD:{phase_id}:{tid}"
                print(f"  📋 [Whiteboard] write_agreement経由で '{target_topic}' に{len(edits)}件の差分を適用しました（phase={phase_id}, task={tid}）。")
            elif raw_content:
                # edits未指定・全文が渡された場合は全文置換の抜け道として扱う。
                # [BL-180] ただし、entry_type="Deliverable"の内容執筆はBL-169によりexpertのみに
                # 限定されている（user/detector等は承認・却下しかできない）。したがってis_whiteboard
                # （既に完全版が存在する）状態でexpert以外がedits未指定のdecision_whatを送るのは、
                # 常に「承認/却下コメント」であり正当な全文置換の用途がない。200字という長さの閾値
                # だけで判定すると、承認理由を詳しく書いただけのUser AI（Stage3）が既存の完全版を
                # 丸ごと消し飛ばす事故が実際に発生した（`log/2026-08-05/1639`、task_1_2のV1詳細仕様書
                # が3行の承認コメントへ全置換された）。expert以外は文字数によらず常に保護する。
                if len(raw_content) > 200 and (caller_role == "expert" or not is_whiteboard):
                    v = apply_whiteboard_patch(conn, run_id, phase_id, tid, raw_content, author_role=caller_role,
                                                edit_summary=args.get("reason_why", ""))
                    _LAST_WHITEBOARD_EDIT = {"phase_id": phase_id, "task_id": tid, "version": v}
                    content = f"WHITEBOARD:{phase_id}:{tid}"
                    print(f"  📋 [Whiteboard] write_agreement経由で '{target_topic}' の全文を新バージョンとして保存しました（phase={phase_id}, task={tid}）。")
                elif is_whiteboard:
                    # [H2踏襲] 既にホワイトボード化済みの完全版に対し、200文字以下の短い要約が
                    # 送られてきた場合、または200字を超えていてもexpert以外からの更新の場合は
                    # 「承認/却下コメント」等とみなし、既存の完全版を上書きしない（BL-180）。
                    # [BL-212追補] 従来は`content = old_content`としていたが、old_content自体が
                    # BL-212の短い無効化理由文（WHITEBOARDプレフィックスを失った行）である場合、
                    # その短文が新しい行へコピーされ、agreements側は二度とポインタを取り戻せない
                    # （汚染が世代を越えて伝播する）。is_whiteboardが真ならwhiteboard_draftsに
                    # 実体が存在することは確定しているため、old_contentの中身に依存せず正典の
                    # ポインタを再生成する。これによりBL-212の残留行は次の更新で自動的に修復される。
                    content = f"WHITEBOARD:{phase_id}:{tid}"
                    # [BL-127] 従来はprint()のみでLLMへは一切伝わらず、ホワイトボード本体が
                    # 実際には更新されていないのに「成功」と返るためExpertが誤って自己申告する
                    # 実インシデントが発生していた。呼び出し元へ返す警告として明示する。
                    if len(raw_content) > 200:
                        protected_warning = (
                            f"⚠️ '{target_topic}'への更新は反映されませんでした：あなた（{caller_role}）"
                            f"はentry_type='Deliverable'の本文を執筆する権限がないため、edits未指定の"
                            f"decision_whatは文字数によらず既存の完全版（ホワイトボード）を上書きしない"
                            f"保護仕様が適用されました。ホワイトボード本文を変更したい場合はeditsパラメータ"
                            f"（old_text/new_text）を指定してください。"
                        )
                    else:
                        protected_warning = (
                            f"⚠️ '{target_topic}'への更新は反映されませんでした：edits未指定で"
                            f"decision_whatが200字以下の短文だったため、既存の完全版（ホワイトボード）"
                            f"を上書きしない保護仕様が適用されました。実際にホワイトボード本文を"
                            f"変更したい場合は、editsパラメータ（old_text/new_text）を指定するか、"
                            f"200字を超える全文をdecision_whatに渡してください。"
                        )
                    print(f"  🔒 [Whiteboard Protected] '{target_topic}' への更新（caller_role={caller_role}）が既存の完全版を上書きしないよう保護しました。")
                # 200文字以下かつ未昇格ならそのまま短文としてagreementsに保持（content=raw_contentのまま）
            else:
                # [BL-212追補] 上のelif分岐と同じ理由でポインタを再生成する。ここはis_whiteboardが
                # 偽（＝まだホワイトボード化されていない短文Deliverable）の場合もあるため、
                # 真の場合のみポインタへ差し替え、偽なら従来通りold_contentを維持する。
                content = f"WHITEBOARD:{phase_id}:{tid}" if is_whiteboard else old_content
                protected_warning = (
                    f"⚠️ '{target_topic}'への更新は反映されませんでした：decision_what/editsの"
                    f"いずれも指定がなく実質的な変更内容がなかったため、既存バージョンを維持しました。"
                )
                print(f"  🔒 [Whiteboard Protected] '{target_topic}' への実質的な変更がなかったため、既存バージョンを維持しました。")
        # ここでようやく旧レコードをSuperseded化（上記のedits検証失敗時はここに到達せず、旧レコードは温存される）
        # [BL-084] Deliverableは冒頭で解決済みのtarget（(phase_id, task_id)識別）をそのまま使う。
        if entry_type == "Deliverable":
            if target is not None:
                db_supersede_agreement(target["id"], conn, run_id)
        else:
            for a in reversed(get_agreements_from_db(conn, run_id)):
                if a["topic"] == target_topic and a.get("status") != "Superseded":
                    db_supersede_agreement(a["id"], conn, run_id)
                    break

    # [R5 F-3.7] トークンコスト抑制のため全件記録はせず、status='Rejected'の場合のみ
    # 直前呼び出しのreasoningをスナップショット保存する。
    _agreement_thought = get_last_reasoning_text() if args.get("status") == "Rejected" else None
    # [BL-188] citations（引用元: {"type": "web"/"goal_text"/"prior_agreement"/"expert_calculation"/
    # "user_input"/"document", "detail": "URLや説明文"}のリスト）。プロンプト誘導のみで強制はしない
    # （Detector等での機械的ゲートは設けない）ため、未指定なら空配列のまま。
    citations_val = json.dumps(args.get("citations", []) or [], ensure_ascii=False)
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, "
        "evidence, is_frozen, internal_thought_process, citations, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            f"AG-{int(time.time() * 1000)}", action_type, args.get("status", "Proposed"),
            topic, content, args.get("reason_why", ""),
            caller_role, entry_type,
            phase_id, tid,
            depends_on_val, resource_claims_val, time.time(),
            args.get("evidence", ""), 0, _agreement_thought, citations_val, run_id
        )
    )
    print(f"  📝 [write_agreement] {caller_role}が{entry_type}（{action_type}, status={args.get('status', 'Proposed')}）を記録しました: topic={topic}")
    # [BL-073] Deliverableが承認された場合、対応するtask_idのDirectiveをApprovedへ解決する。
    if entry_type == "Deliverable" and args.get("status") in RESOLVING_DELIVERABLE_STATUSES:
        _resolve_directive_for_task(conn, run_id, tid, phase_id, resolved_by=caller_role)
    return None, protected_warning


def _write_agreement_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str, task_id: str = "",
                           phases: list[dict] | None = None, pending_task_ids: list[str] | None = None,
                           effective_current_task_id: str = "", phase_id: str = "") -> dict:
    """[F-3.2] write_agreement_toolの実体。バリデーション→権限チェック→SQLiteコミット→確定値反映

    ★修正（レビュー指摘H1、二重JSONエンコード対応）: 生のdictを返す。json.dumps済み文字列を
    返すと、_query_AI_liveのツールループ末尾で再度json.dumpsされ二重エンコードになるため
    （理由は_read_verified_fact_handlerのコメント参照）。

    [BL-131] `phases`/`pending_task_ids`はTOOL_DISPATCH経由でstate["phases"]/
    state["pending_task_ids"]から渡される（BL-131/TOOL_DISPATCH state化）。task_planner
    正式計画に存在しないtask_idでの成果物作成（`log/2026-07-29/1322`・`1708`で観測された
    `task_1_1_review`事故）を防ぐための実在チェックに使う。
    """
    # 1. 構造チェック
    # [R4] entry_type=Deliverable かつ action_type=UPDATE で edits が指定されている場合、
    # decision_what（全文）は省略可能（old_text/new_textによる差分置換で代替するため）。
    uses_edits = args.get("entry_type") == "Deliverable" and args.get("action_type") == "UPDATE" and args.get("edits")
    required = ["action_type", "status", "topic", "reason_why", "entry_type"]
    if not uses_edits:
        required.append("decision_what")
    missing = [f for f in required if not args.get(f)]
    if missing:
        print(f"  🚫 [write_agreement guard] 必須フィールド不足を拒否: caller={caller_role}, missing={missing}, topic={args.get('topic')!r}")
        return {"success": False, "error": f"必須フィールドが不足: {missing}"}

    # 2. enum値チェック
    valid_actions = {"CREATE", "UPDATE", "SUPERSEDE"}
    valid_statuses = {"Proposed", "Approved", "Approved_with_Conditions", "Rejected", "Implicitly_Accepted"}
    # [BL-126 Stage D/§2.1] "EssenceProposal"はFacilitatorが本質対話の開始/収束確定を提起する
    # ための専用entry_type。新規ツールは起こさず、既存のagreementsテーブル・権限チェックの
    # 枠組みをそのまま再利用する（topic/reason_why/evidenceが「何を・なぜ本質から問い直すか」に
    # 転用できる）。
    valid_entries = {"Decision", "Directive", "Deliverable", "EssenceProposal"}
    if args["action_type"] not in valid_actions:
        print(f"  🚫 [write_agreement guard] 不正なaction_typeを拒否: caller={caller_role}, action_type={args['action_type']!r}")
        return {"success": False, "error": f"不正なaction_type: {args['action_type']}"}
    if args["status"] not in valid_statuses:
        print(f"  🚫 [write_agreement guard] 不正なstatusを拒否: caller={caller_role}, status={args['status']!r}")
        return {"success": False, "error": f"不正なstatus: {args['status']}"}
    if args["entry_type"] not in valid_entries:
        print(f"  🚫 [write_agreement guard] 不正なentry_typeを拒否: caller={caller_role}, entry_type={args['entry_type']!r}")
        return {"success": False, "error": f"不正なentry_type: {args['entry_type']}"}

    # 3. 権限チェック
    perm_error = _check_write_permission(args, caller_role, conn=conn, run_id=run_id, task_id=task_id, phase_id=phase_id)
    if perm_error:
        return {"success": False, "error": perm_error}

    # 4. depends_onリレーション整合性チェック
    if args.get("depends_on"):
        for dep_id in args["depends_on"]:
            exists = conn.execute(
                "SELECT 1 FROM agreements WHERE id=? AND run_id=?", (dep_id, run_id)
            ).fetchone()
            if not exists:
                print(f"  🚫 [write_agreement guard] 存在しないdepends_on IDを拒否: caller={caller_role}, dep_id={dep_id}, topic={args.get('topic')!r}")
                return {"success": False, "error": f"depends_onに存在しないID: {dep_id}"}

    # 4.5. [BL-131] task_id実在チェック。entry_type='Decision'（ゴール直下の一般的な合意事項）は
    # タスクに紐づかない全体決定もありうるため対象外とする。
    if args["entry_type"] in ("Directive", "Deliverable"):
        tid = args.get("task_id") or task_id
        if not tid:
            print(f"  🚫 [write_agreement guard] task_id未指定を拒否: caller={caller_role}, entry_type={args['entry_type']}, topic={args.get('topic')!r}")
            return {"success": False, "error": "entry_type='Directive'/'Deliverable'にはtask_idが必須です"}
        task_obj = _find_task_by_id(phases or [], tid)
        if task_obj is None and tid not in (pending_task_ids or []):
            print(f"  🚫 [write_agreement guard][BL-131] 存在しないtask_idを拒否: caller={caller_role}, task_id={tid!r}, topic={args.get('topic')!r}")
            return {
                "success": False,
                "error": (
                    f"task_id '{tid}' はtask_plannerの正式な計画に存在しません。"
                    "既存のtask_idを使うか、正式なタスク化を経てください。"
                ),
            }

        # 4.55. [BL-146] current_task_idゲート。BL-125のタスク遷移ブロック中でも、
        # write_agreementがtask_id実在チェック（4.5）しか行わないため、任意の他タスクへ
        # 実際にDeliverableを書き込めてしまっていた（`log/2026-08-02/0832`で実害確認、
        # BL-125で足止めされたcurrent_task_id以外への"phantom progress"）。SUPERSEDEは
        # 他タスクの内容を正規に改訂する既存の正当な経路（BL-062/080/084）のため対象外。
        # effective_current_task_idが空（current_phase/phasesを持たない簡易呼び出し）の
        # 場合はフェイルオープンでゲートをスキップする。
        if (args["action_type"] != "SUPERSEDE" and effective_current_task_id
                and tid != effective_current_task_id):
            print(
                f"  🚫 [write_agreement guard][BL-146] current_task_id不一致を拒否: caller={caller_role}, "
                f"要求task_id={tid!r}, current_task_id={effective_current_task_id!r}, action={args['action_type']}, "
                f"topic={args.get('topic')!r}"
            )
            return {
                "success": False,
                "error": (
                    f"task_id '{tid}' は現在のタスク（'{effective_current_task_id}'）と一致しません。"
                    "write_agreementのCREATE/UPDATEで書き込めるのは現在進行中のタスクの内容のみです。"
                    "他タスクの内容を改訂・訂正する場合はaction_type='SUPERSEDE'を使ってください。"
                ),
            }

    # 4.6. [BL-131] target_topic必須化。UPDATE/SUPERSEDEでtarget_topic省略時にtopic（今回の新しい
    # 値）へ暗黙フォールバックすると、既存topicの検索に失敗し実質的な空振り更新になる
    # （Deliverableは既にBL-084でphase_id/task_idベースに切り替え済みのため対象外）。
    if args["action_type"] in ("UPDATE", "SUPERSEDE") and args["entry_type"] != "Deliverable":
        if not args.get("target_topic"):
            print(f"  🚫 [write_agreement guard][BL-131] target_topic未指定を拒否: caller={caller_role}, action={args['action_type']}, entry_type={args['entry_type']}, topic={args.get('topic')!r}")
            return {
                "success": False,
                "error": f"action_type='{args['action_type']}'にはtarget_topicが必須です（更新対象のtopicを明示してください）",
            }

    # 5. コミット
    commit_error, protected_warning = _commit_agreement_from_tool(args, conn, run_id, caller_role, task_id, phase_id)
    if commit_error:
        return {"success": False, "error": commit_error}

    # [BL-126 Stage D] entry_type="EssenceProposal"が成功した場合、facilitator_node/
    # generate_user_utterance_nodeが本質対話のstate遷移に使えるよう記録する
    # （_LAST_GOAL_REVISIONと同じブリッジパターン）。
    if args["entry_type"] == "EssenceProposal":
        global _LAST_ESSENCE_PROPOSAL
        _LAST_ESSENCE_PROPOSAL = {
            "topic": args.get("topic", ""), "status": args.get("status", ""),
            "action_type": args.get("action_type", ""), "reason_why": args.get("reason_why", ""),
        }

    # 6. confirmed_variablesをverified_factsへ反映
    for cv in args.get("confirmed_variables", []) or []:
        var_name = cv.get("variable_name")
        if not var_name:
            continue
        # [BL-188] cvがcitationsを供給していればそれを使う（プロンプト誘導のみ、強制はしない）。
        # 未指定時はtopic文字列へのフォールバックを維持する（旧挙動との後方互換、弱いシグナルとして扱う）。
        upsert_verified_fact(
            conn, run_id, var_name, cv.get("value"), unit=cv.get("unit", ""),
            source_task_id=task_id, source_phase_id=args.get("phase_id", ""),
            confirmed_by=caller_role,
            reason=args.get("reason_why", ""),
            citations=cv.get("citations") or [args.get("topic", "")],
            confidence=cv.get("confidence", "provisional"),
        )

    # [BL-127] protected_warningが設定されている場合、DB上のagreement行自体は正常に
    # コミットされたが、ホワイトボード本体への実反映は保護によりスキップされている。
    # successはTrueのまま維持し（呼び出し自体は失敗していないため）、warningフィールドで
    # 呼び出し元（Expert/User AI）に明示し、次のターンで再試行を促す。
    if protected_warning:
        return {"success": True, "message": "DB update successful", "warning": protected_warning}
    return {"success": True, "message": "DB update successful"}


_ISSUE_DESCRIPTION_MAX_LEN = 2000


def _truncate_issue_description(description: str, occurrence_count: int) -> str:
    """[BL-096] descriptionが再発のたびに追記され無制限に肥大化するのを防ぐ。
    上限を超えた場合、古い方（先頭）を切り詰め、直近の内容を優先して残す。
    """
    if len(description) <= _ISSUE_DESCRIPTION_MAX_LEN:
        return description
    suffix = f"\n...(truncated, {occurrence_count} occurrences)"
    keep = max(_ISSUE_DESCRIPTION_MAX_LEN - len(suffix), 0)
    return description[-keep:] + suffix


def _bump_issue_occurrence(conn: sqlite3.Connection, run_id: str, row: dict, new_task_id: str) -> int:
    """[BL-096] CREATE経由・READ経由で共有する再発カウント＋閾値昇格ロジック。
    occurrence_count>=2になった時点で、呼び出し側の判断に依存せず機械的に
    severity='major'・status='escalated'へ昇格する不変条件を強制する（D-079/D-080）。
    戻り値は更新後のoccurrence_count。
    [BL-157/D-127] ただしraised_by='detector_auto'（BL-096の汎用catch-allバックアップ、
    detector_nodeがcurrent_task_id単位で機械的にCREATEする）は例外とする。current_task_idは
    実際の会話の主題より遅れて更新されるため、無関係な指摘が同一バケツへ混入して見せかけの
    再発になり得る（実ドライラン`log/2026-08-03/2233`で確認：task_1_1のバケツへtask_1_2に
    ついての無関係な指摘が混入しoccurrence_count=2でmajor/escalated化していた）。この例外は
    detector_auto起票行にのみ適用し、他ロール（detector/user）の既存挙動は変更しない。
    """
    occurrence_count = row["occurrence_count"] + 1
    will_escalate = occurrence_count >= 2 and row["raised_by"] != "detector_auto"
    if will_escalate:
        severity = "major"
        status = "escalated"
    else:
        severity = row["severity"]
        status = row["status"]
    print(
        f"  🔁 [BL-096] issue再発カウント: topic={row['topic']}, raised_by={row['raised_by']}, "
        f"occurrence_count {row['occurrence_count']}→{occurrence_count}"
    )
    if occurrence_count >= 2 and not will_escalate:
        print(
            f"  🔕 [BL-157] raised_by='detector_auto'のため、occurrence_count={occurrence_count}でも"
            f"major/escalated化を抑制しました（severity='{row['severity']}'のまま維持）。"
        )
    elif will_escalate and row["severity"] != "major":
        print("  ⬆️ [BL-096] occurrence_count>=2のため機械的にseverity=major, status=escalatedへ昇格しました。")
    # [BL-194] 同じtopicが再検出された時点でACKNOWLEDGEの猶予を即時失効させる。「対応中」と
    # 宣言した直後に同じ懸念が再検出されるのは、対応が実際には進んでいない証拠であるため。
    # これが無いと、ACKNOWLEDGEは「唱えるだけで督促を無限に止められる呪文」になってしまう
    # （TTL・累計上限と並ぶ、万能の逃げ道化を防ぐガードの一つ）。
    if int(row.get("acknowledged_until_round") or 0) > 0:
        print(f"  🔓 [BL-194] topic={row['topic']}が再検出されたためACKNOWLEDGEの猶予を失効させました。")
    conn.execute(
        "UPDATE issue_log SET occurrence_count=?, last_seen_task_id=?, severity=?, status=?, "
        "acknowledged_until_round=0, updated_at=? WHERE id=? AND run_id=?",
        (occurrence_count, new_task_id, severity, status, time.time(), row["id"], run_id)
    )
    return occurrence_count


def _write_issue_impl(args: dict, conn: sqlite3.Connection, run_id: str, caller_role: str,
                       phase_id: str = "", task_id: str = "", state: dict | None = None) -> dict:
    """[BL-096] write_issue_toolの実体。CREATE=起票・再発、RESOLVE=解決、DEFER=明示的な先送り（BL-136）。
    重複検知キーはtopic単独（D-080。task_id/phase_idはメタデータのみで識別には使わない。
    タスク横断の再発検知というBL-096の目的自体と矛盾するため、(topic, task_id)キー案は撤回した）。
    """
    action_type = args.get("action_type")
    if action_type not in ("CREATE", "RESOLVE", "DEFER", "ACKNOWLEDGE"):
        return {"success": False, "error": f"不正なaction_type: {action_type}"}

    topic = args.get("topic")
    if not topic:
        return {"success": False, "error": "topicは必須です"}

    perm_error = _check_issue_permission(args, caller_role)
    if perm_error:
        return {"success": False, "error": perm_error}

    existing_row = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND topic=? AND status != 'resolved'",
        (run_id, topic)
    ).fetchone()
    existing = dict(existing_row) if existing_row else None
    now = time.time()

    if action_type == "CREATE":
        description = args.get("description")
        if not description:
            return {"success": False, "error": "description（CREATE時必須）が指定されていません"}
        if existing:
            occurrence_count = _bump_issue_occurrence(conn, run_id, existing, new_task_id=task_id)
            combined_description = _truncate_issue_description(
                existing["description"] + "\n---\n" + description, occurrence_count
            )
            # [BL-154] decision_extractor_auto専用: 同一topicが別のtask_idへ再度Deferredされた場合、
            # 「直近の申し送り宣言が最新の意図」としてdefer_to_task_idを上書きする（write_agreementの
            # UPDATEが最新版で古い版を置き換えるのと同じ「最新が勝つ」思想）。他ロールのCREATEは
            # defer_to_task_idを渡さないため、この分岐は既存行の値をそのまま温存する（無変更）。
            new_defer_to_task_id = existing.get("defer_to_task_id", "")
            if caller_role == "decision_extractor_auto":
                candidate_defer_to_task_id = args.get("defer_to_task_id")
                if candidate_defer_to_task_id:
                    new_defer_to_task_id = candidate_defer_to_task_id
            conn.execute(
                "UPDATE issue_log SET description=?, defer_to_task_id=?, updated_at=? WHERE id=? AND run_id=?",
                (combined_description, new_defer_to_task_id, now, existing["id"], run_id)
            )
            return {"success": True, "message": "再発として記録しました", "occurrence_count": occurrence_count}
        severity = args.get("severity", "minor")
        if severity not in ("minor", "major"):
            return {"success": False, "error": f"不正なseverity: {severity}"}
        # [BL-096 レビューB] severity='major'の行は常にstatus='escalated'を伴う不変条件
        status = "escalated" if severity == "major" else "open"
        # [BL-154] decision_extractor_auto専用: 起票と同時に申し送り先task_idが既知の場合、DEFERの
        # 二段階操作を経ずに初回作成時点でdefer_to_task_idを設定する（他ロールでは常に空文字のまま、
        # 既存のCREATE→DEFER二段階フローを変更しない）。
        defer_to_task_id_value = args.get("defer_to_task_id", "") if caller_role == "decision_extractor_auto" else ""
        issue_id = str(uuid.uuid4())
        conn.execute(
            "INSERT INTO issue_log (id, run_id, topic, raised_by, phase_id, task_id, severity, status, "
            "description, occurrence_count, last_seen_task_id, defer_to_task_id, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?, ?, ?)",
            (issue_id, run_id, topic, caller_role, phase_id, task_id, severity, status,
             description, task_id, defer_to_task_id_value, now, now)
        )
        print(f"  🆕 [write_issue] {caller_role}が新規issueを起票しました: topic={topic}, severity={severity}, status={status}, id={issue_id}")
        return {"success": True, "message": "新規issueを起票しました", "id": issue_id}

    if action_type == "DEFER":
        # [BL-136] BL-082の申し送り（Directive/status=Deferred/defer_to_task_id）と同じ思想を
        # issue_logにも導入。statusは変更せず(open/escalatedのまま)、対応予定のtask_idだけを記録する。
        defer_to_task_id = args.get("defer_to_task_id")
        defer_reason = args.get("defer_reason")
        if not defer_to_task_id:
            return {"success": False, "error": "defer_to_task_id（DEFER時必須）が指定されていません"}
        if not defer_reason:
            return {"success": False, "error": "defer_reason（DEFER時必須）が指定されていません"}
        if not existing:
            return {"success": False, "error": f"topic='{topic}'に該当する未解決issueが見つかりません"}

        task_id_to_phase_id: dict[str, str] = {}
        task_id_to_task: dict[str, dict] = {}
        if state:
            for _phase in state.get("phases", []):
                for _t in _phase.get("tasks", []):
                    task_id_to_phase_id[_t["task_id"]] = _phase["phase_id"]
                    task_id_to_task[_t["task_id"]] = _t

        normalized_defer_to_task_id = defer_to_task_id.replace(".", "_")
        if defer_to_task_id in task_id_to_phase_id:
            canonical_defer_to_task_id = defer_to_task_id
        elif normalized_defer_to_task_id in task_id_to_phase_id:
            canonical_defer_to_task_id = normalized_defer_to_task_id
        else:
            return {"success": False, "error": f"存在しないtask_id '{defer_to_task_id}' への先送りは無効です"}

        # [BL-194/S8] 自己先送りの拒否。DEFERの意味は「今このタスクでは扱わない」であり、
        # 受け皿を実行中のタスク自身にすると何も先送りされない。にもかかわらず、
        # defer_to_task_idが立つという一点でBL-136/145/125/158の是正経路が全て沈黙し、
        # BL-103 pinとBL-096/144停滞判定という懲罰経路だけが点灯し続ける非対称状態
        # （＝解消不能かつ強制停止を招くissue）が生まれる。log/2026-08-08/1514で
        # 20件中6件がこの状態にあり、12時間のランがhaltした（BL-194 D-164）。
        # [REJECTED] 「受理するが消費側で先送り扱いしない」案も検討した。消費側の無効化
        # （_is_issue_effectively_deferred）は多重防御として実装済みだが、tool boundaryで
        # 黙って受理するとUser AIには成功として返り、次ターン以降なぜ督促が消えないのか
        # 説明がつかない（BL-151/BL-193が確立した「失敗は理由つきで即座に返し、同ターン内で
        # 自己修復させる」原則に反する）。
        if canonical_defer_to_task_id == task_id:
            return {
                "success": False,
                "error": (
                    f"'{canonical_defer_to_task_id}' は現在あなたが実行中のタスク自身です。"
                    "自分自身への先送りはできません（何も先送りされないまま、システム上は"
                    "「対応予定あり」と扱われてしまうため）。次のいずれかを選んでください: "
                    "(1) この懸念が本当に別タスクの責務なら、その実在するtask_idを"
                    "defer_to_task_idに指定してDEFERする。"
                    "(2) 現在タスクのacceptance_criteriaの範囲で既に解消しているなら "
                    "RESOLVEする。"
                    "(3) 現在タスクの責務であり、今まさに対応中なら "
                    "write_issue(action_type=\"ACKNOWLEDGE\", topic=..., ack_reason=...) を"
                    "使ってください（一時的に督促を止めますが、タスク離脱時のゲートは"
                    "解除されません）。"
                ),
            }

        conn.execute(
            "UPDATE issue_log SET defer_to_task_id=?, acknowledged_until_round=0, updated_at=? "
            "WHERE id=? AND run_id=?",
            (canonical_defer_to_task_id, now, existing["id"], run_id)
        )
        print(f"  📤 [write_issue] {caller_role}がtopic={topic}を'{canonical_defer_to_task_id}'へDEFERしました: {defer_reason}")
        target_phase_id = task_id_to_phase_id[canonical_defer_to_task_id]
        _plan_note_appended = _append_deferred_note_to_plan(
            conn, run_id, target_phase_id, canonical_defer_to_task_id,
            note_text=f"[issue_log: {topic}] {defer_reason}\n{existing['description']}",
            source_task_id=task_id, task_for_skeleton=task_id_to_task.get(canonical_defer_to_task_id),
        )
        if not _plan_note_appended:
            print(f"  ⚠️ [write_issue DEFER] plan_draftsへの申し送り追記に失敗しました（issue_logのdefer_to_task_id自体は更新済み）。")
        # [BL-194/S6] スコープ整合性の機械的判定（LLMジャッジ・キーワード一致）は却下した
        # （前者はホットパスでのコストと非決定性、後者は日本語自由文での誤判定。いずれも
        # 誤って拒否すると、自己先送りを塞いだ本BLの下ではUser AIのtriage手段が消え
        # 新種のデッドロックになる）。代わりに受け皿タスクのスコープをそのまま返し、
        # ミスマッチの判断はモデル自身に委ねる（BL-042/BL-188の「プロンプト誘導のみ」方針、
        # およびBL-151/BL-193の「同ターン内で自己修復させる」原則に沿う）。
        _target_task = task_id_to_task.get(canonical_defer_to_task_id, {})
        return {
            "success": True,
            "message": f"'{canonical_defer_to_task_id}'への先送りとして記録しました",
            "target_task_scope": {
                "task_id": canonical_defer_to_task_id,
                "description": _target_task.get("description", ""),
                "acceptance_criteria": _target_task.get("acceptance_criteria", []),
                "owns_variables": _target_task.get("owns_variables", []),
            },
            "scope_check_hint": (
                "上記が先送り先タスクのスコープです。この懸念がこれらのどれにも対応しない場合、"
                "そのタスクの担当者も同じように解けない問題を抱えることになります。"
                "より適切なtask_idがあれば、同じtopicで再度DEFERし直してください"
                "（最新のDEFERが有効になります）。"
            ),
        }

    if action_type == "ACKNOWLEDGE":
        # [BL-194/D-165] 「現在タスクの責務であり、今まさに対応中である」という正直な
        # 第三の選択肢。RESOLVE（本当に解決した）でもDEFER（別タスクの責務である）でもない。
        # statusは一切変更しない（D-079/D-080の不変条件を保護するため、TTL付き補助列のみ更新）。
        ack_reason = args.get("ack_reason")
        if not ack_reason:
            return {"success": False, "error": "ack_reason（ACKNOWLEDGE時必須）が指定されていません"}
        if not existing:
            return {"success": False, "error": f"topic='{topic}'に該当する未解決issueが見つかりません"}
        if existing["status"] != "escalated":
            return {"success": False, "error": f"topic='{topic}'はstatus='{existing['status']}'です。ACKNOWLEDGEはstatus='escalated'の懸念にのみ使えます。"}
        if int(existing.get("acknowledged_count") or 0) >= _BL194_ACK_MAX_GRANTS:
            return {
                "success": False,
                "error": (
                    f"この懸念は既に{_BL194_ACK_MAX_GRANTS}回ACKNOWLEDGEされています。"
                    f"{_BL194_ACK_MAX_GRANTS + 1}回目はできません。現在タスクで実際に解消してRESOLVEするか、"
                    "別タスクの責務であることを認めてDEFERしてください。このまま放置すると滞留として"
                    "計画再構成の対象になります。"
                ),
            }
        round_count = state.get("round_count", 0) if state else 0
        new_count = int(existing.get("acknowledged_count") or 0) + 1
        new_until_round = round_count + _BL194_ACK_TTL_ROUNDS
        conn.execute(
            "UPDATE issue_log SET acknowledged_until_round=?, acknowledged_count=?, "
            "acknowledge_reason=?, updated_at=? WHERE id=? AND run_id=?",
            (new_until_round, new_count, ack_reason, now, existing["id"], run_id)
        )
        print(f"  🛠 [write_issue] {caller_role}がtopic={topic}をACKNOWLEDGEしました（{new_count}/{_BL194_ACK_MAX_GRANTS}回目、"
              f"round={round_count}〜{new_until_round}まで有効）: {ack_reason}")
        return {
            "success": True,
            "message": f"対応中として記録しました（残り猶予{_BL194_ACK_TTL_ROUNDS}ラウンド、"
                       f"残り{_BL194_ACK_MAX_GRANTS - new_count}回）",
            "acknowledged_until_round": new_until_round,
            "remaining_grants": _BL194_ACK_MAX_GRANTS - new_count,
        }

    # RESOLVE
    resolution_note = args.get("resolution_note")
    if not resolution_note:
        return {"success": False, "error": "resolution_note（RESOLVE時必須）が指定されていません"}
    if not existing:
        return {"success": False, "error": f"topic='{topic}'に該当する未解決issueが見つかりません"}
    conn.execute(
        "UPDATE issue_log SET status='resolved', resolved_by=?, resolved_at=?, resolution_note=? "
        "WHERE id=? AND run_id=?",
        (caller_role, now, resolution_note, existing["id"], run_id)
    )
    remaining_escalated = conn.execute(
        "SELECT COUNT(*) FROM issue_log WHERE run_id=? AND status='escalated'", (run_id,)
    ).fetchone()[0]
    print(f"  ✅ [write_issue] {caller_role}がtopic={topic}を解決しました: {resolution_note}（残りescalated={remaining_escalated}件）")
    return {
        "success": True, "message": "issueを解決済みにしました",
        "escalation_cleared": remaining_escalated == 0,
    }


def _mark_issue_planned(conn: sqlite3.Connection, run_id: str, issue_id: str,
                         embedded_task_ids: list[str]) -> bool:
    """[BL-145] task_planner_nodeが、issue駆動のラン途中計画再構成成功直後に、吸収した
    issue_log行を'planned'（計画済み、resolvedではない）へ遷移させる非LLMゲート・非tool
    経由の内部ヘルパー。task_plannerが計画へ組み込んだからといって「本当に解決した」とは
    限らない（実際にタスクへ着手し内容が検証されて初めて解決といえる）ため、statusは
    'resolved'ではなく'planned'とし、resolved/resolved_by/resolution_noteは触れない
    （真の解決時のためにuser roleの既存write_issue(RESOLVE)経路のために温存する）。

    defer_to_task_idを埋め込み先task_idの記録に転用する（BL-136のDEFERと同じ「今このissueの
    面倒を見ているtask_id」という意味で、reflection_node側の除外フィルタ（既にdefer_to_task_id
    が設定済みのissueはBL-145のタスク化対象から除外する）により、同一issueが同時にDEFER先と
    planned先を両方持つことはない）。複数taskへ跨って組み込まれた場合も単一task_id（先頭）の
    みを記録する（DEFER同様、単一ターゲットの制約を踏襲）。

    'planned'は_write_issue_implのCREATE/DEFER/RESOLVEがいずれも判定条件とする
    `status != 'resolved'`を満たすため、以降も既存のCREATE経由の再発検知（occurrence_count>=2で
    機械的にseverity=major・status=escalatedへ戻る）・DEFER経由のさらなる先送りが
    コード変更なしでそのまま機能する。

    冪等: 対象行が見つからない（既にresolved等）場合はFalseを返す（チェックポイント再開時の
    二重発火を安全に無視するため）。
    """
    existing = conn.execute(
        "SELECT id FROM issue_log WHERE run_id=? AND id=? AND status != 'resolved'", (run_id, issue_id)
    ).fetchone()
    if not existing or not embedded_task_ids:
        print(f"  🔕 [DB] issue_logをplanned化スキップ: issue_id={issue_id}, "
              f"existing={bool(existing)}, embedded_task_ids={embedded_task_ids}（既にresolved等のため冪等スキップ）")
        return False
    conn.execute(
        "UPDATE issue_log SET status='planned', defer_to_task_id=?, updated_at=? WHERE id=? AND run_id=?",
        (embedded_task_ids[0], time.time(), issue_id, run_id)
    )
    print(f"  📌 [DB] issue_logをplanned化: issue_id={issue_id}, defer_to_task_id={embedded_task_ids[0]}")
    return True


def get_issues_from_db(conn: sqlite3.Connection, run_id: str, topic_keyword: str | None = None,
                        task_id: str | None = None, phase_id: str | None = None,
                        list_all: bool = False) -> list[dict]:
    """[BL-096] issue_logの検索ヘルパー。get_verified_facts_from_dbと同じ
    keyword/exact-match検索パターンを踏襲する。list_all=Trueの場合は他の引数を無視し、
    このrunの全issue（status不問）を返す。
    """
    if list_all:
        rows = conn.execute(
            "SELECT * FROM issue_log WHERE run_id=? ORDER BY id", (run_id,)
        ).fetchall()
        return [dict(r) for r in rows]

    conditions = ["run_id=?"]
    params: list = [run_id]
    if topic_keyword:
        conditions.append("(topic LIKE ? OR description LIKE ?)")
        like_pattern = f"%{topic_keyword}%"
        params.extend([like_pattern, like_pattern])
    if task_id:
        conditions.append("task_id=?")
        params.append(task_id)
    if phase_id:
        conditions.append("phase_id=?")
        params.append(phase_id)
    rows = conn.execute(
        f"SELECT * FROM issue_log WHERE {' AND '.join(conditions)} ORDER BY id", tuple(params)
    ).fetchall()
    return [dict(r) for r in rows]


def _get_escalated_issues(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """[BL-096] reflection/facilitatorが共有する、status='escalated'行の直接DB問い合わせ。
    LLMツール呼び出しではなくPython側の直接クエリとすることで、モデルのツール呼び出し
    判断に依存せずエスカレーション済み懸念を必ず取得できるようにする（BL-099対策）。
    """
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='escalated' ORDER BY id", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _is_issue_effectively_deferred(conn: sqlite3.Connection, run_id: str, issue: dict,
                                    current_task_id: str = "") -> bool:
    """[BL-194] 「この issue には、今このタスク以外の実効的な受け皿がある」と機械的に言えるか。

    [CONSTRAINT] BL-136のDEFERはstatusを変えずdefer_to_task_idだけを立てる設計のため、
    「受け皿があるか」の判定は列の有無ではなく述語で行う必要がある。従来その述語は
    _get_forced_escalated_issues_text(BL-136/167) / _get_blocking_issues_for_transition(BL-125) /
    _formalizable_stale(BL-145)の3箇所に別実装でコピーされ、_get_escalated_issues(BL-096)を
    使う側（BL-103 pin・BL-096/144停滞判定・facilitator名指し）には一切存在しなかった。
    log/2026-08-08/1514で、全20件がtriage済み（全件defer_to_task_idあり）であるにも
    かかわらず停滞判定だけが発火し12時間のランがhaltした事故の直接原因（BL-194）。

    [REJECTED] statusに新しい値（'deferred'）を導入してSQL一発で表現する案は却下した。
    D-079/D-080の「severity='major' ⇒ status='escalated'」不変条件と、_bump_issue_occurrence
    の再発昇格・_write_issue_impl全分岐のstatus判定がこの不変条件に依存しており、status
    語彙の拡張はBL-096系全体の再設計になるため。
    """
    target = issue.get("defer_to_task_id") or ""
    if not target:
        return False
    # [BL-194] 自己先送り: 受け皿が「今まさに実行中のタスク」なら、先送りは何も先送りしていない。
    # current_task_idを引数化しているのは、BL-191のredirect_backward（過去タスクへの意図的な
    # 巻き戻し）中に issue["last_seen_task_id"] だけで近似すると誤判定するため
    # （task_3_1実行中に発見した「task_2_1が新ゴールと不整合」というissueをtask_2_1へDEFER
    # するのは正当な後方申し送りだが、last_seen_task_idが過去にtask_2_1だと自己先送りに
    # 誤認しかねない）。呼び出し元は全てstateを保持しているためcurrent_task_idを渡せる。
    if current_task_id and target == current_task_id:
        return False
    # [BL-167] 受け皿タスクが既に完了済みなら、その受け皿は失効している（永久迷子の防止）。
    if _is_task_completed(conn, run_id, target):
        return False
    return True


_BL194_ACK_TTL_ROUNDS = 3  # [BL-194][AGENTS.md §7 承認済み] ACKNOWLEDGE1回あたりの猶予ラウンド数。
# BL-144の3ラウンド滞留閾値と揃え、「ACKは滞留カウントをちょうど1周期分止める」という
# 明確な意味を持たせる（D-165）。
_BL194_ACK_MAX_GRANTS = 2  # [BL-194][AGENTS.md §7 承認済み] 同一issueへのACKNOWLEDGE累計上限。
# これにより最悪でも6ラウンドで必ず滞留判定へ復帰し、不死身化しない（D-165）。


def _is_issue_acknowledged_active(issue: dict, round_count: int) -> bool:
    """[BL-194] ACKNOWLEDGEの猶予が有効か。TTLを過ぎたら自動的に無効化される
    （新しいstatusを作らず列とround_countの比較だけで表現するため、
    「解除し忘れて不死身化する」経路が構造的に存在しない）。"""
    return int(issue.get("acknowledged_until_round") or 0) > round_count


def _get_actionable_escalated_issues(conn: sqlite3.Connection, run_id: str,
                                      current_task_id: str = "",
                                      round_count: int | None = None) -> list[dict]:
    """[BL-194] status='escalated'のうち、「今このタスクで実際に対応を迫るべき」行だけを返す。
    _get_escalated_issues（BL-096、生の全件）は、対応予定の有無を問わず全件を見せてよい
    用途（escalation_activeの一度きり復帰通知、reflectionのcompleted判定抑止一覧）に
    限って使い続けること——この2用途をactionableへ切り替えると、DEFER/ACK済みでも
    未解決であるはずのissueに対して「解決した」「completed可」という虚偽の判定を
    許してしまう（BL-194設計書§9-R1参照）。
    round_countを渡した場合のみACKNOWLEDGE中のissueも追加で除外する（BL-125のように
    roundを持たない／持たせたくない呼び出し元との混線を防ぐため、既定Noneでは
    ACK抑制を行わない——ACK有効中の懸念は別途_build_acknowledged_issue_pin_textで
    「対応中」として可視化されるため、督促からの除外であって不可視化ではない）。
    """
    result = [
        r for r in _get_escalated_issues(conn, run_id)
        if not _is_issue_effectively_deferred(conn, run_id, r, current_task_id)
    ]
    if round_count is not None:
        result = [r for r in result if not _is_issue_acknowledged_active(r, round_count)]
    return result


def _build_escalation_pin_text(conn: sqlite3.Connection, run_id: str, current_task_id: str = "",
                                round_count: int = 0) -> str:
    """[BL-103] issue_logのescalated行を、recency（chat_history_window/expert_history_window）
    に関係なく常時hydrate_contextへ差し込むための整形テキストを返す（無ければ空文字）。
    facilitatorのフィードバックはchat_history末尾に追記されるだけで窓を過ぎると消えるため
    （facilitator_node）、本関数はそれとは別に、call_expert/generate_user_utteranceの
    ambient contextへ「facilitatorの発言が消えた後の穴埋め」として毎ターン注入する用途。
    フォーマットはfacilitator_nodeのescalated_issues_text組み立てと同一にする。
    [BL-194] 生の全件ではなくactionable集合（triage済みを除いた集合）のみを返す。
    「⚠️要対応」という見出し（呼び出し元）の意味を正しくするため——DEFER済み分は
    _build_deferred_issue_pin_textへ、ACKNOWLEDGE中の分は_build_acknowledged_issue_pin_text
    へそれぞれ分離し、いずれも非「要対応」の別トーンで表示する。
    """
    escalated = _get_actionable_escalated_issues(conn, run_id, current_task_id, round_count=round_count)
    if not escalated:
        return ""
    return "\n".join(
        f"- topic={i['topic']}: {i['description']}（累積{i['occurrence_count']}回発生、"
        f"raised_by={i['raised_by']}）"
        for i in escalated
    )


def _build_deferred_issue_pin_text(conn: sqlite3.Connection, run_id: str,
                                    current_task_id: str = "") -> str:
    """[BL-194] status='escalated'だが実効的な受け皿（別task_id）が確定済みの行を、
    非強制トーンで参考提示する。BL-103のpinは従来これらを「⚠️要対応」として毎ターン
    Expert/Detector/User AIへ刺し続けており、log/2026-08-08/1514ではtask_2_2スコープの
    車両台数issueがtask_2_1実行中のExpertプロンプトへ数時間にわたり「要対応」として
    表示され続けた結果、Expertが現在タスクのacceptance_criteriaに無い車両台数の再導出を
    繰り返した（Ver.1→Ver.41のchurnの機械的な引き金）。
    [CONSTRAINT] 文脈自体は落とさない（重複起票の防止）。落とすのは「今あなたが解決せよ」
    という強制トーンだけ、というBL-145 _build_planned_issue_pin_textと同じ設計。
    """
    deferred = [
        r for r in _get_escalated_issues(conn, run_id)
        if _is_issue_effectively_deferred(conn, run_id, r, current_task_id)
    ]
    if not deferred:
        return ""
    return "\n".join(
        f"- topic={i['topic']}: {i['description']}"
        f"（対応予定task_id={i['defer_to_task_id']}。現在のタスクでこれを解決する必要はありません。"
        "現在タスクのacceptance_criteriaに無い内容をこの懸念のために先取りしないでください）"
        for i in deferred
    )


def _build_acknowledged_issue_pin_text(conn: sqlite3.Connection, run_id: str, round_count: int) -> str:
    """[BL-194] ACKNOWLEDGE中（現在タスクの責務であり対応中と表明済み）の懸念を、
    DEFER済み（対応不要）とは意味が逆の前向きなトーンで表示する。可視性は保ちつつ、
    「⚠️要対応」（_build_escalation_pin_text）からは除外されるため、督促の二重化を避ける。
    """
    rows = [
        r for r in _get_escalated_issues(conn, run_id)
        if _is_issue_acknowledged_active(r, round_count)
    ]
    if not rows:
        return ""
    return "\n".join(
        f"- topic={i['topic']}: {i['description']}"
        f"（対応中と表明済み、残り{int(i.get('acknowledged_until_round') or 0) - round_count}ラウンド。"
        "これは現在タスクの責務であり、今回の成果物で対応が期待されています）"
        for i in rows
    )


def _get_open_issues(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """[BL-136] status='open'（severity='minor'、再発2回未満）行の直接DB問い合わせ。
    _get_escalated_issuesと同型だが、escalated化する前のminor懸念を可視化する用途
    （従来はread_issuesを能動的に呼ばない限り一切見えなかった）。
    """
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='open' ORDER BY id", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _build_open_issue_pin_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-136] issue_logのopen（minor）行を毎ターン参考情報として差し込むための整形テキスト。
    escalated行（_build_escalation_pin_text、対応必須）とは異なり、こちらはあくまで参考情報
    であり対応を強制しない（見出しの絵文字・トーンで区別する）。
    [BL-154] decision_extractor_auto経由で生まれた行は誕生時点からdefer_to_task_idが設定済み
    のため、既に対応予定task_idが決まっていることを表示に反映する（BL-145の
    _build_planned_issue_pin_textと同型のパターン）。defer_to_task_id無しの既存行は従来通り。
    """
    open_issues = _get_open_issues(conn, run_id)
    if not open_issues:
        return ""
    lines = []
    for i in open_issues:
        defer_note = f"、対応予定task_id={i['defer_to_task_id']}" if i.get("defer_to_task_id") else ""
        lines.append(f"- topic={i['topic']}: {i['description']}（raised_by={i['raised_by']}{defer_note}）")
    return "\n".join(lines)


def _get_planned_issues(conn: sqlite3.Connection, run_id: str) -> list[dict]:
    """[BL-145] status='planned'（Reflectorの正当性監査によりtask_planner_nodeが計画へ
    組み込んだが、まだ真に解決したとは確認されていない）行の直接DB問い合わせ。
    _get_open_issues/_get_escalated_issuesと同型。
    """
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='planned' ORDER BY id", (run_id,)
    ).fetchall()
    return [dict(r) for r in rows]


def _build_planned_issue_pin_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-145] issue_logのplanned行を毎ターン参考情報として差し込むための整形テキスト。
    BL-136の強制解決文言（escalated行、対応必須）とは異なり、こちらは非強制の参考情報
    ——既に対応予定のtask_idへ組み込み済みであり、今すぐの対応を無理強いすると差し戻し
    ループ等のデッドロック化を招くリスクがあるため（ユーザー指摘）。対応するtask_idの
    作業が実際に済み、内容が検証できた時点でwrite_issue(RESOLVE)するようUser AIへ促す。
    """
    planned_issues = _get_planned_issues(conn, run_id)
    if not planned_issues:
        return ""
    return "\n".join(
        f"- topic={i['topic']}: {i['description']}（task_id={i['defer_to_task_id']}に組み込み済み。"
        f"本当に解決されたか確認できたらwrite_issue(RESOLVE)してください）"
        for i in planned_issues
    )


def _build_escalation_resume_notice(state: LineageState) -> str:
    """[BL-096] エスカレーション解消の直後、次にExpert/User AIが呼ばれる際、一度だけ
    「facilitatorの提起した論点への深掘りは終了し、通常のタスク遂行に戻ってよい」という
    復帰通知を返す。current_task_id等の作業状態はreflection/facilitatorに一切破壊されない
    （decision_extractor_nodeのみが書き込む専有フィールド）が、facilitatorが開く「広い
    問い直しモード」からAI自身が自力で抜け出す明示的な合図がないため、この通知で補う
    （ユーザー指摘、D-080）。呼び出し後はフラグをFalseに戻し、以後は注入されない。
    """
    if not state.get("escalation_just_resolved_notice_pending"):
        return ""
    state["escalation_just_resolved_notice_pending"] = False
    current_task_id = state.get("current_task_id", "")
    _conn = get_active_conn()
    _recent_resolved = _conn.execute(
        "SELECT topic FROM issue_log WHERE run_id=? AND status='resolved' ORDER BY resolved_at DESC LIMIT 1",
        (state["run_id"],)
    ).fetchone()
    topic_text = _recent_resolved[0] if _recent_resolved else "(不明)"
    print(f"  📣 [BL-096] エスカレーション解消の復帰通知をLLMプロンプトへ注入します（issue: {topic_text}、current_task_id: {current_task_id}）。")
    return (
        f"\n【BL-096: エスカレーション解消】直前まで提起されていた懸念（issue: {topic_text}）は"
        f"解決済みです。facilitatorの提起した論点への深掘りは終了し、通常のタスク遂行"
        f"（現在のtask_id: {current_task_id}）に戻ってください。\n"
    )


def _build_task_transition_blocked_notice(state: LineageState) -> str:
    """[BL-125] _resolve_task_transitionが未解決・未先送りのsevere issueによりタスク遷移を
    ブロックした直後、次のUser AI呼び出しで一度だけ「なぜ遷移が起きなかったか」を明示する
    通知を返す。_build_escalation_resume_noticeと同じ「one-shot注入して消費後クリア」
    パターンを踏襲する。
    [BL-176] 離脱先task_idが未承認（Approved相当のDeliverable不在）でブロックされた場合も
    同じone-shotパターンで通知する。両ブロック要因は_resolve_task_transition内で排他的に
    しか発生しない（先に判定された方でreturnする）ため、両方が同時にセットされることはない。
    """
    topics = state.get("task_transition_blocked_issue_topics")
    if topics:
        state["task_transition_blocked_issue_topics"] = []
        current_task_id = state.get("current_task_id", "")
        topics_text = "、".join(topics)
        print(f"  📣 [BL-125] タスク遷移ブロック通知をLLMプロンプトへ注入します（current_task_id: {current_task_id}、issues: {topics_text}）。")
        return (
            f"\n【🛑 BL-125: タスク遷移をブロックしました】直前の発言は次タスクへの移行として"
            f"解釈されましたが、現在のtask_id（{current_task_id}）に未解決・未先送りの重大issue"
            f"（{topics_text}）が残っているため、移行を見送りました。"
            "write_issue(action_type=\"RESOLVE\", ...)で解決するか、write_issue(action_type=\"DEFER\", "
            "defer_to_task_id=\"...\", ...)で対応予定のtaskを明示してから、改めて次タスクへの移行を"
            "指示してください。\n"
        )

    unapproved_task_id = state.get("task_transition_blocked_unapproved_task_id")
    if unapproved_task_id:
        state["task_transition_blocked_unapproved_task_id"] = ""
        print(f"  📣 [BL-176] タスク遷移ブロック通知をLLMプロンプトへ注入します（未承認task_id: {unapproved_task_id}）。")
        return (
            f"\n【🛑 BL-176: タスク遷移をブロックしました】直前の発言は次タスクへの移行として"
            f"解釈されましたが、現在のtask_id（{unapproved_task_id}）にはまだExpertからの"
            "承認済み（Approved相当）のDeliverableが存在しないため、移行を見送りました。"
            "まず現タスクの成果物をレビューし、write_agreementで承認する（未提出ならExpertへ"
            "提出を指示する）まで、次タスクへの移行指示は行わないでください。\n"
        )

    reassigned_notice = state.get("task_reassigned_after_replan_notice")
    if reassigned_notice:
        state["task_reassigned_after_replan_notice"] = ""
        print(f"  📣 [BL-190] タスク再割当通知をLLMプロンプトへ注入します。")
        return f"\n【🛑 {reassigned_notice}】\n"

    return ""


def _read_issues_handler(args: dict) -> dict | list:
    """[BL-096] read_issuesツールのハンドラ。TOOL_DISPATCH経由で呼び出される。
    デフォルトでresolved行も返す（既に解決済みかどうかをその場で確認でき、無駄な
    再登録を避けられるようにするため。ユーザー指摘）。
    READ経由の再発カウントは、topic_keywordとtask_idの両方が明示的に指定された場合のみ、
    open/escalatedの行に対してのみ行う（誤爆防止のための厳格化、D-080）。
    """
    conn = get_active_conn()
    run_id = _CURRENT_RUN_ID
    topic_keyword = args.get("topic_keyword")
    task_id = args.get("task_id")
    phase_id = args.get("phase_id")
    list_all = bool(args.get("list_all", False))

    if not list_all and not topic_keyword and not task_id and not phase_id:
        return {"status": "error", "message": "topic_keyword/task_id/phase_idのいずれか、またはlist_all=trueを指定してください。"}

    # [BL-096] topic_keywordが指定されている場合、task_idは検索フィルタ（行のtask_id列との
    # 完全一致）には使わない。これはタスク横断の再発検知が目的のため、別task_idで起票された
    # 同じ懸念も見つける必要があるからである（重複検知キーがtopic単独であることと対応、D-080）。
    # このときtask_idは、以下の再発カウント判定における「呼び出し元の現在task_id」として扱う。
    search_task_id_filter = None if topic_keyword else task_id
    results = get_issues_from_db(
        conn, run_id, topic_keyword=topic_keyword, task_id=search_task_id_filter,
        phase_id=phase_id, list_all=list_all
    )

    if not list_all and topic_keyword and task_id:
        for row in results:
            if row["status"] in ("open", "escalated") and row["last_seen_task_id"] != task_id:
                _raised_by = row["raised_by"]
                new_occurrence_count = _bump_issue_occurrence(conn, run_id, row, new_task_id=task_id)
                # 呼び出し元へ返す結果にも、たった今適用した昇格を反映する
                row["occurrence_count"] = new_occurrence_count
                row["last_seen_task_id"] = task_id
                # [BL-157] _bump_issue_occurrence内のDB更新と同じ例外条件をミラーする。
                # ここを合わせないと、LLMへ返すこの場限りの表示だけがDBの実体（minor/open）と
                # 食い違ったまま（severity=major/status=escalated）見えてしまう。
                if new_occurrence_count >= 2 and _raised_by != "detector_auto":
                    row["severity"] = "major"
                    row["status"] = "escalated"
                    print(
                        f"  ⬆️ [BL-096] read_issues経由: topic={row['topic']}のoccurrence_countが"
                        f"{new_occurrence_count}に達したため、返却値もmajor/escalated表示にしました。"
                    )
                elif new_occurrence_count >= 2:
                    print(
                        f"  🔕 [BL-157] read_issues経由: topic={row['topic']}はraised_by='detector_auto'の"
                        f"ため、occurrence_count={new_occurrence_count}でも返却値をmajor/escalated化しません。"
                    )

    if not results:
        return {"status": "not_found", "message": "該当するissueが見つかりませんでした。"}
    return results


# [BL-131/TOOL_DISPATCH state化] 全ハンドラは`(args, state)`の2引数で統一する。
# `_query_AI_live`のツールループが常に`handler(args, state)`の形で呼び出すため、
# stateを使わないハンドラも第2引数を受け取って無視する薄いラムダでラップする。
# state経由の値を優先しつつ、state未指定（None）の呼び出し元との後方互換のため
# 既存の`_CURRENT_*`グローバルへのフォールバックを残す（BL-099の完全解消は別スコープ）。
def _run_id_from(state: dict | None) -> str:
    return state.get("run_id") or _CURRENT_RUN_ID if state else _CURRENT_RUN_ID


def _task_id_from(state: dict | None) -> str:
    return state.get("current_task_id") or _CURRENT_TASK_ID if state else _CURRENT_TASK_ID


def _phase_id_from(state: dict | None) -> str:
    return (state.get("current_phase", {}) or {}).get("phase_id") or _CURRENT_PHASE_ID if state else _CURRENT_PHASE_ID


def _phases_from(state: dict | None) -> list[dict]:
    return state.get("phases", []) if state else list(_CURRENT_PHASES)


def _pending_task_ids_from(state: dict | None) -> list[str]:
    return state.get("pending_task_ids", []) if state else []


def _effective_current_task_id_from(state: dict | None) -> str:
    """[BL-146] BL-125のタスク遷移ゲートが実際に参照する「実効上の現在タスクid」。
    `state["current_task_id"]`は初回タスク進行中は空文字のままなので（唯一の書き手
    `_resolve_task_transition`が最初の遷移までまだ一度も発火していない）、生のcurrent_task_idを
    そのまま比較すると初回タスクの正当な書き込みまで全滅する。`_get_current_task`と同じ
    current_phase先頭タスクへのフォールバックを再利用する。
    """
    if state:
        return _get_current_task(state).get("task_id", "")
    if _CURRENT_TASK_ID:
        return _CURRENT_TASK_ID
    for phase in _CURRENT_PHASES:
        if phase.get("phase_id") == _CURRENT_PHASE_ID:
            tasks = phase.get("tasks", [])
            return tasks[0].get("task_id", "") if tasks else ""
    return ""


_MAX_TASK_FOCUS_REDIRECTS = 5  # [BL-191] facilitation_count(5)/plan_revision_count(5)と揃える

# [BL-191] 直前のquery_AI呼び出しのツールループ内でschedule_task_focusが成功した場合の構造化決定。
# _LAST_GOAL_REVISIONと同型のブリッジパターン。
_LAST_SCHEDULING_DECISION: dict | None = None


def get_last_scheduling_decision() -> dict | None:
    return dict(_LAST_SCHEDULING_DECISION) if _LAST_SCHEDULING_DECISION else None


def _schedule_task_focus_tool_impl(args: dict, conn: sqlite3.Connection, run_id: str,
                                    caller_role: str, state: dict | None) -> dict:
    """[BL-191] schedule_task_focusの実体。userロールのみ許可（Stage4は_CURRENT_CALLER_ROLE=
    "user"で動くため、facilitator等の別経路からの呼び出しは弾く）。
    [BUG-1対策] redirect_backward/joint_focus双方でredirect/宣言時点の最新Deliverable
    agreement_idを`baseline_agreement_id`として記録する。復帰／companion自動クリアの判定は
    このbaselineとの比較で行う（`_is_task_completed`単独では、BL-163でフラグされただけで
    ステータスがApprovedのまま残っている過去タスクにredirectした直後、Expertが何も手を
    付けていない時点で即座に「完了済み」と誤判定してしまうため）。
    """
    global _LAST_SCHEDULING_DECISION
    if caller_role != "user":
        return {"success": False, "error": f"{caller_role}はschedule_task_focusを呼び出せません（userロールのみ許可）"}
    decision_type = args.get("decision_type")
    reason = args.get("reason", "")
    if decision_type not in ("redirect_backward", "joint_focus", "clear_companion", "force_resume") or not reason:
        return {"success": False, "error": "decision_type/reasonは必須です"}

    phases = _phases_from(state)
    current_task_id = _effective_current_task_id_from(state)
    current_phase_id = _phase_id_from(state)

    if decision_type == "redirect_backward":
        target_task_id = args.get("target_task_id", "")
        target = _find_task_by_id(phases, target_task_id)
        if not target:
            return {"success": False, "error": f"target_task_id '{target_task_id}' は計画に存在しません"}
        if target_task_id == current_task_id:
            return {"success": False, "error": "target_task_idは現在のタスクと同一です"}
        target_phase_id = _find_phase_id_for_task(phases, target_task_id)
        baseline_agreement = _find_active_deliverable_agreement(conn, run_id, target_phase_id, target_task_id)
        if not baseline_agreement:
            return {"success": False, "error": f"'{target_task_id}'にはまだDeliverableが存在しません（未着手タスクへはredirect_backwardではなく通常のタスク遷移を使ってください）"}
        if state and state.get("task_focus_stack"):
            return {"success": False, "error": "既に一時中断中のフォーカスがあります（深さ1固定）。force_resumeで先に解消してください"}
        if state and state.get("task_focus_redirect_count", 0) >= _MAX_TASK_FOCUS_REDIRECTS:
            return {"success": False, "error": f"redirect_backwardの上限（{_MAX_TASK_FOCUS_REDIRECTS}回/run）に達しました"}
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    "", "", reason, caller_role)
        _LAST_SCHEDULING_DECISION = {
            "decision_type": "redirect_backward", "target_task_id": target_task_id,
            "target_phase_id": target_phase_id, "reason": reason,
            "baseline_agreement_id": baseline_agreement.get("id", ""),
        }
        return {"success": True}

    if decision_type == "joint_focus":
        companion_task_id = args.get("companion_task_id", "")
        if not _find_task_by_id(phases, companion_task_id):
            return {"success": False, "error": f"companion_task_id '{companion_task_id}' は計画に存在しません"}
        if companion_task_id == current_task_id:
            return {"success": False, "error": "companion_task_idは現在のタスクと同一です"}
        companion_phase_id = _find_phase_id_for_task(phases, companion_task_id)
        baseline_agreement = _find_active_deliverable_agreement(conn, run_id, companion_phase_id, companion_task_id)
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    companion_task_id, companion_phase_id, reason, caller_role)
        _LAST_SCHEDULING_DECISION = {
            "decision_type": "joint_focus", "companion_task_id": companion_task_id,
            "companion_phase_id": companion_phase_id, "reason": reason,
            "baseline_agreement_id": baseline_agreement.get("id", "") if baseline_agreement else "",
        }
        return {"success": True}

    if decision_type in ("clear_companion", "force_resume"):
        record_scheduling_decision(conn, run_id, decision_type, current_task_id, current_phase_id,
                                    "", "", reason, caller_role)
        _LAST_SCHEDULING_DECISION = {"decision_type": decision_type, "reason": reason}
        return {"success": True}

    return {"success": False, "error": f"未知のdecision_type: {decision_type}"}


# [BL-201→BL-203] 呼び出し回数上限・参照ディレクトリのような「会話の履歴ではなく実行時設定」を、
# チェックポイントに保存された古い値ではなく常に現在のAppConfigから供給するための上書き辞書。
#
# BL-201は「resume時にローカルのstateを書き換える」実装だったが、ラウンド途中で中断したrunでは
# `app.stream(None, ...)`が呼ばれ、そのローカルstateがLangGraphへ渡らないため一切効かなかった
# （log/2026-08-10/0901で、web_searchが50ではなく30、calc_road_routeが30ではなく20のまま動作）。
# これらの値を実際に読むのはツールハンドラの`config`引数だけなので、ここで注入すれば
# LangGraphのチェックポイント意味論（中断中のpending tasks）に一切触れずに済む。
# カウンタ側（web_search_call_count等）はrunの実消費実績なのでstateに置いたまま上書きしない。
_RUNTIME_TOOL_LIMITS: dict = {}

_RUNTIME_TOOL_LIMIT_KEYS = (
    "max_web_search_calls",
    "max_web_fetch_calls",
    "max_road_route_calls",
    "goal_reference_dir",
)


def _resume_config_overrides_from(config: dict) -> dict:
    """[BL-203] AppConfigから実行時設定4フィールドを取り出す（既定値はLineageState初期化と同値）。"""
    return {
        "max_web_search_calls": config.get("max_web_search_calls", 30),
        "max_web_fetch_calls": config.get("max_web_fetch_calls", 30),
        "max_road_route_calls": config.get("max_road_route_calls", 30),
        "goal_reference_dir": config.get("goal_reference_dir", ""),
    }


def set_runtime_tool_limits(config: dict) -> None:
    """[BL-203] run開始時（新規・resumeとも）に呼び、以後のツール呼び出しへ現在のconfigの
    実行時設定を供給する。"""
    global _RUNTIME_TOOL_LIMITS
    _RUNTIME_TOOL_LIMITS = _resume_config_overrides_from(config)


def _tool_config(state: dict | None) -> dict:
    """[BL-203] ツールハンドラへ渡す`config`引数。stateの内容（カウンタ・run_id等）を土台に、
    実行時設定だけを現在のAppConfig由来の値で上書きした**新しい辞書**を返す。
    [CONSTRAINT] 返り値はコピーなので、ハンドラがここへ書き込んでもstateには反映されない。
    カウンタを加算するハンドラには必ず本物の`state`を`state`引数として渡すこと。"""
    return {**(state or {}), **_RUNTIME_TOOL_LIMITS}


TOOL_DISPATCH = {
    "python_repl": lambda args, state=None: _run_python_repl(args),
    "read_verified_fact": lambda args, state=None: _read_verified_fact_handler(args),
    "read_deliverable_file": lambda args, state=None: _read_deliverable_file_handler(args, state),
    "verify_whiteboard_excerpt": lambda args, state=None: _verify_whiteboard_excerpt_handler(args),
    "read_whiteboard_excerpt": lambda args, state=None: _read_whiteboard_excerpt_handler(args, state),
    "diff_plan_draft_versions": lambda args, state=None: _diff_plan_draft_versions_handler(args),
    "think": lambda args, state=None: _think_handler(args),
    "write_agreement": lambda args, state=None: _write_agreement_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, _task_id_from(state),
        phases=_phases_from(state), pending_task_ids=_pending_task_ids_from(state),
        effective_current_task_id=_effective_current_task_id_from(state),
        phase_id=_phase_id_from(state)
    ),
    "freeze_agreement": lambda args, state=None: _freeze_agreement_tool_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE
    ),
    "escalate_premise_concern": lambda args, state=None: _escalate_premise_concern_tool_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, _task_id_from(state)
    ),
    "resolve_premise_concern": lambda args, state=None: _resolve_premise_concern_tool_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE
    ),
    "revise_goal": lambda args, state=None: _revise_goal_tool_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE
    ),
    "write_issue": lambda args, state=None: _write_issue_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, _phase_id_from(state), _task_id_from(state),
        state=state
    ),
    "schedule_task_focus": lambda args, state=None: _schedule_task_focus_tool_impl(
        args, get_active_conn(), _run_id_from(state), _CURRENT_CALLER_ROLE, state
    ),
    "read_issues": lambda args, state=None: _read_issues_handler(args),
    "read_plan_draft": lambda args, state=None: _read_plan_draft_handler(args),
    "read_project_plan": lambda args, state=None: _read_project_plan_handler(args),
    "ask_user_question": lambda args, state=None: _ask_user_question_tool_impl(args, _CURRENT_CALLER_ROLE),
    # [BL-184] web_search/web_fetchの呼び出し回数上限（max_web_search_calls/max_web_fetch_calls）は
    # AppConfigからrun開始時にLineageStateへコピーされ、state自体に載っている（run_ai_vs_ai_loop
    # 初期化ブロック参照）。TOOL_DISPATCH統一シグネチャは(args, state)の2引数しか渡さないため、
    # web_tools側の`config`引数にもstateをそのまま渡す（state/configを分離運搬する新しい配線を
    # 増やさず、既存のmax_turns等と同じ「state自身に上限値を持たせる」パターンを踏襲する）。
    "web_search": lambda args, state=None: web_tools.web_search_handler(args, state or {}, _tool_config(state)),
    "web_fetch": lambda args, state=None: web_tools.web_fetch_handler(args, state or {}, _tool_config(state)),
    "read_reference_file": lambda args, state=None: web_tools.read_reference_file_handler(args, state or {}),
    "read_goal_reference": lambda args, state=None: web_tools.read_goal_reference_handler(args, _tool_config(state)),
    # [BL-204] 実世界事物レジストリ。conn/run_idはモジュールレベル変数から取得するため
    # （_read_verified_fact_handler等と同じ）、stateはtask_id/phase_idの解決にのみ使う。
    "register_entity": lambda args, state=None: _register_entity_handler(args, state),
    "write_entity_attribute": lambda args, state=None: _write_entity_attribute_handler(args, state),
    "read_entity": lambda args, state=None: _read_entity_handler(args, state),
    "verify_entity_geo": lambda args, state=None: _verify_entity_geo_handler(args, state),
    # [BL-198] 地理データ実測ツール。web_search/web_fetchと同型に、stateをstate/config兼用で渡す。
    "gsi_geocode": lambda args, state=None: geo_tools.gsi_geocode_handler(args, state or {}, _tool_config(state)),
    "gsi_get_elevation": lambda args, state=None: geo_tools.gsi_get_elevation_handler(args, state or {}, _tool_config(state)),
    "gsi_calc_distance_bearing": lambda args, state=None: geo_tools.gsi_calc_distance_bearing_handler(args, state or {}, _tool_config(state)),
    "calc_road_route": lambda args, state=None: geo_tools.calc_road_route_handler(args, state or {}, _tool_config(state)),
}

# BL-033: 直前のquery_AI呼び出しでLLMが実際に実行したpython_replの(code, result)記録。
# ノードをまたいでも参照できるよう、呼び出し元(expert_node等)がstateへコピーする前提の
# 一時バッファ（stateにはシリアライズ不要な生実行ログを持たせない方針、_DB_CONNと同様）。
_LAST_PYTHON_CALLS: list[dict] = []

# [R3b §3.5.1] 直前のquery_AI呼び出しのツールループ内でwrite_agreementが
# 1回でも成功したか（success=Trueで返ったか）を記録するフラグ。
# decision_extractor_node側で「write_agreementが呼ばれたターンか」を
# 判定するための機構（expert_node/generate_user_utterance_nodeが
# stateへコピーする）。query_AI()呼び出しごとにリセットされる。
_LAST_WRITE_AGREEMENT_SUCCEEDED: bool = False

# [BL-158] 直前のquery_AI呼び出しのツールループ内でwrite_issue(RESOLVE/DEFER)が
# 1回でも成功したか（success=Trueで返ったか）を記録するフラグ。_LAST_WRITE_AGREEMENT_SUCCEEDED
# と同型のパターン。detector_nodeがUser AIのターンを機械的に差し戻すかどうかの判定に使う
# （generate_user_utterance_nodeがstateへコピーする）。query_AI()呼び出しごとにリセットされる。
_LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED: bool = False

# [R4] 直前のquery_AI呼び出しのツールループ内でwhiteboard_draftsに新バージョンが
# 書き込まれた場合、その{phase_id, task_id, version}を記録する（BL-033の
# _LAST_PYTHON_CALLSと同じ「LangGraph単一プロセス同期実行前提」パターン）。
# Detectorがmajor判定を出した場合、expert_nodeの差し戻し処理からロールバックするために使う。
_LAST_WHITEBOARD_EDIT: dict | None = None

# [R5 F-2.1] 直前のquery_AI呼び出しでモデルが出力したreasoning（思考過程）の全文。
# 従来はstreaming中に💭表示で印字するのみで保存されずに破棄されていた（プロバイダが
# reasoningを返さない場合は空文字のまま）。_LAST_PYTHON_CALLSと同じパターンで、
# 呼び出し元（expert_node等）がstateへコピーする前提の一時バッファ。
_LAST_REASONING_TEXT: str = ""

# [BL-086] 直前のquery_AI呼び出しのツールループ内でrevise_goalが成功した場合、
# その{new_goal_text, old_goal_text, escalation_id}を記録する。DB側の副作用
# （freeze/goal_shift_events/escalation status更新）は_revise_goal_tool_impl内で
# 完結済みであり、ここで運ぶのはLangGraph state["goal"]への反映に必要な情報のみ。
# query_AI()呼び出しごとにリセットされる（_LAST_WRITE_AGREEMENT_SUCCEEDEDと同型）。
_LAST_GOAL_REVISION: dict | None = None

# [BL-126 Stage D] 直前のquery_AI呼び出しのツールループ内でwrite_agreement
# (entry_type="EssenceProposal")が成功した場合、その{topic, status, action_type, reason_why}を
# 記録する（_LAST_GOAL_REVISIONと同じパターン）。facilitator_node/generate_user_utterance_node
# が戻り値経由でessence_dialogue_active等のstate遷移に使う。
_LAST_ESSENCE_PROPOSAL: dict | None = None

# [BL-130] 直前のquery_AI呼び出しのツールループ内でask_user_questionが呼ばれた場合、
# その{question_text, blocking_reason}を記録する（_LAST_GOAL_REVISIONと同じパターン）。
# expert_nodeが戻り値経由でstate["expert_consultation_mode"]/["expert_pending_question"]へ反映する。
_LAST_ASK_USER_QUESTION: dict | None = None


def get_last_python_calls() -> list[dict]:
    """【SLM要約】
    直前のquery_AI呼び出しで実際に実行されたpython_replのcode/result記録のコピーを返す。
    """
    return list(_LAST_PYTHON_CALLS)


def get_last_write_agreement_succeeded() -> bool:
    """【SLM要約】
    [R3b §3.5.1] 直前のquery_AI呼び出しのツールループ内で、write_agreementが
    1回でも成功したか（success=Trueで返ったか）を返す。
    decision_extractor_nodeの条件分岐で使用する。
    """
    return _LAST_WRITE_AGREEMENT_SUCCEEDED


def get_last_write_issue_resolve_or_defer_succeeded() -> bool:
    """【SLM要約】
    [BL-158] 直前のquery_AI呼び出しのツールループ内で、write_issue(action_type="RESOLVE"
    または"DEFER")が1回でも成功したかを返す。detector_nodeの機械的差し戻し判定で使用する。
    """
    return _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED


def get_last_whiteboard_edit() -> dict | None:
    """【SLM要約】
    [R4] 直前のquery_AI呼び出しのツールループ内でwhiteboard_draftsに新バージョンが
    書き込まれた場合、その{phase_id, task_id, version}を返す。ロールバック判定に使う。
    """
    return dict(_LAST_WHITEBOARD_EDIT) if _LAST_WHITEBOARD_EDIT else None


def get_last_goal_revision() -> dict | None:
    """[BL-086] 直前のquery_AI呼び出しのツールループ内でrevise_goalが成功した場合、
    その{new_goal_text, old_goal_text, escalation_id}を返す。
    generate_user_utterance_nodeがstate["goal"]へ反映するために使う。
    """
    return dict(_LAST_GOAL_REVISION) if _LAST_GOAL_REVISION else None


def get_last_ask_user_question() -> dict | None:
    """[BL-130] 直前のquery_AI呼び出しのツールループ内でask_user_questionが成功した場合、
    その{question_text, blocking_reason}を返す。expert_nodeがstateへ反映するために使う。
    """
    return dict(_LAST_ASK_USER_QUESTION) if _LAST_ASK_USER_QUESTION else None


def get_last_essence_proposal() -> dict | None:
    """[BL-126 Stage D] 直前のquery_AI呼び出しのツールループ内でwrite_agreement
    (entry_type="EssenceProposal")が成功した場合、その内容を返す。
    """
    return dict(_LAST_ESSENCE_PROPOSAL) if _LAST_ESSENCE_PROPOSAL else None


def get_last_reasoning_text() -> str:
    """【SLM要約】
    [R5 F-2.1] 直前のquery_AI呼び出しでモデルが出力したreasoning（思考過程）の全文を返す。
    プロバイダがreasoningを返さない場合は空文字列。
    """
    return _LAST_REASONING_TEXT


def get_last_think_summary() -> str:
    """[BL-103] 直前のノード呼び出し（_reset_think_scratchpad()〜次のノードの
    _reset_think_scratchpad()まで）でモデルがthinkツールに書き残した最後のエントリから、
    decisions.whyに使える一文要約を作って返す。生テキストの先頭を機械的に切るだけの
    劣化版要約（旧: (output or "")[:100]）の代わりに、BL-093で全ノードに既に必須化されて
    いるthinkの`decided`/`why`（無ければ`summary`）を使う。thinkが一度も呼ばれていない
    場合は空文字を返す（呼び出し元は従来通りのフォールバックを行う）。
    """
    if not _THINK_REASONING_LOG:
        return ""
    last = _THINK_REASONING_LOG[-1]
    decided = last.get("decided", "")
    why = last.get("why", "")
    if decided:
        return f"{decided}（{why}）" if why else decided
    return last.get("summary", "")


class DailyQuotaExhaustedError(RuntimeError):
    """[BL-171] OpenRouter無料枠の日次上限（例: "free-models-per-day-high-balance"）に達した
    ことを示す。X-RateLimit-Resetは翌日固定のタイムスタンプであり、指数バックオフでの
    リトライ（8〜128秒）や層2リトライを繰り返しても日付が変わるまで解消しない。query_AIの
    リトライループはこの状態を検知した時点で即座にこの例外を送出し、通常のAPIエラー
    リトライ（一時的な障害向け）を打ち切って、run_ai_vs_ai_loopまで伝播させる
    （実ドライラン`log/2026-08-04/2344`で、無意味なリトライ→JSON解析失敗→フェイルクローズ
    (major)が延々と繰り返され、その偽のmajor判定がDetector等の判断に混入して進行が
    破壊される実害を確認した）。
    """


def query_AI(messages: list[dict], client: OpenAI, model: str, label: str = "Unknown Node", tools: list[dict] | None = None,
             light_system_prompt: str | None = None, state: dict | None = None) -> str:
    """【SLM要約】
    Orchestration of external AI API calls with Record/Replay stub support (keyed by (label, call_seq)),
    delegating the actual retry/provider-selection logic to _query_AI_live.
    [BL-131/TOOL_DISPATCH state化] `state`は_query_AI_liveへそのまま透過する（レコード/リプレイの
    キャッシュキーには影響しない）。
    """
    global _call_seq_counter, _LAST_PYTHON_CALLS, _LAST_WRITE_AGREEMENT_SUCCEEDED, _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED, _LAST_WHITEBOARD_EDIT, _LAST_REASONING_TEXT, _LAST_GOAL_REVISION, _LAST_ASK_USER_QUESTION, _LAST_ESSENCE_PROPOSAL, _LAST_SCHEDULING_DECISION
    _LAST_PYTHON_CALLS = []
    _LAST_WRITE_AGREEMENT_SUCCEEDED = False
    _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED = False
    _LAST_WHITEBOARD_EDIT = None
    _LAST_REASONING_TEXT = ""
    _LAST_GOAL_REVISION = None
    _LAST_ASK_USER_QUESTION = None
    _LAST_ESSENCE_PROPOSAL = None
    _LAST_SCHEDULING_DECISION = None  # [BL-191]

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

    content = _query_AI_live(messages, client, model, label, tools=tools, light_system_prompt=light_system_prompt, state=state)

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


class _StreamToolCallFunction:
    """[UX] streamモードのツール呼び出しループ用: 分割されて届くfunction.name/argumentsの
    断片を蓄積した後、非streaming版のresponse.choices[0].message.tool_calls[i].functionと
    同じインターフェース（.name/.arguments属性）で下流コードに渡すための軽量ラッパー。"""
    def __init__(self, name: str, arguments: str):
        self.name = name
        self.arguments = arguments


class _StreamToolCall:
    """[UX] 上記と同様、tool_calls[i]（.id/.function）の非streaming版インターフェースを再現する。"""
    def __init__(self, tc_id: str | None, name: str, arguments: str):
        self.id = tc_id
        self.type = "function"
        self.function = _StreamToolCallFunction(name, arguments)


class _StreamMessage:
    """[UX] streamモードで蓄積したcontent/tool_callsを、非streaming版のchoice.messageと
    同じインターフェース（.content/.tool_calls/.model_dump()）で下流コードに渡すための
    軽量ラッパー。reasoningは既にstream中にprint済みのためNone固定でよい。"""
    def __init__(self, content: str | None, tool_calls: list[_StreamToolCall] | None):
        self.content = content
        self.tool_calls = tool_calls
        self.reasoning = None

    def model_dump(self) -> dict:
        d: dict = {"role": "assistant", "content": self.content}
        if self.tool_calls:
            d["tool_calls"] = [
                {"id": tc.id, "type": "function",
                 "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
                for tc in self.tool_calls
            ]
        return d


def _query_AI_live(messages: list[dict], client: OpenAI, model: str, label: str = "Unknown Node", tools: list[dict] | None = None,
                    light_system_prompt: str | None = None, state: dict | None = None) -> str:
    """【SLM要約】
    Orchestration of external AI API calls, managing retries, dynamic parameter tuning (temperature, JSON mode), and provider selection based on the requested task label.
    tools付与時はツール呼び出しループ（R2.3、query_AI集約方式、D-008）をリトライブロック内側で実行する（D-004）。
    [BL-131/TOOL_DISPATCH state化] 呼び出し元ノードが`state`を渡した場合、ツール実行時に
    `TOOL_DISPATCH`のハンドラへそのまま受け渡す（`_CURRENT_RUN_ID`等のグローバル経由に
    頼らず、write_agreement等が`state["phases"]`等を直接参照できるようにするため）。
    `state`を渡さない呼び出し元（tools不要のノード等）は`None`のままでよい。
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
    # [BL-202] delaysを全て使い切った後、"(サーバー高負荷によるAPIエラー)"というプレース
    # ホルダーを「そのノードの回答」として下流へ流す前に、ノード自体をやり直す回数。
    # log/2026-08-09/2348では、この文字列がExpertの発言としてDetectorへ渡り、Detectorが
    # 「Agentの応答が『(サーバー高負荷によるAPIエラー)』のみで指示に一切応えていない」として
    # 却下する、というラウンドの空転が20ラウンド中4回以上発生した（Expertは1文字も編集して
    # いないのに版番号とラウンドだけが消費される）。やり直しはloop_messages（それまでの
    # reasoning・ツール結果の全履歴）を保持したまま行うため、思考ログは失われない。
    _MAX_NODE_REDO_ON_API_EXHAUSTION = 2
    # [BL-202] ノードやり直し前の追加クールダウン。delaysの最終値（128秒）を待ってなお
    # 全滅している状況のため、即座に再突入せず一段長く待つ。
    _NODE_REDO_COOLDOWN_SECONDS = 180

    provider_preferences = {
        "provider": {
            "order": ["Fireworks", "nextbit/fp8", "novita/fp8", "parasail/fp8","siliconflow/fp8"],
            "allow_fallbacks": False # リストのプロバイダーが全滅した場合は他を使う
        }
    }

    # [BL-107] provider.order固定とOpenRouterのsticky routing（session_idベース）は
    # 公式ドキュメントにより併用不可（provider.orderを手動指定するとsticky routingは
    # 無効化される）。BL-093でほぼ全ノードがtoolsループ経由になった結果、ループ内の
    # 連続リクエスト間でキャッシュが一切効かない（プレフィックスキャッシュはsticky routing
    # 前提のため）ことが判明し、session_idへの切り替えを実験する。速度面で問題が出た場合に
    # ワンライン（Falseに戻すだけ）でprovider.order固定に戻せるよう、切り替えをフラグ化する。
    _USE_STICKY_SESSION_ROUTING = True

    # [BL-122] tools付きツールループの進捗（loop_messages/python_calls_log/reasoning_parts_all/
    # iteration位置）は、外側のAPIエラーリトライ（for attempt）をまたいで保持する。従来はこれらが
    # `for attempt`の`try`ブロック内で初期化されていたため、リトライのたびに丸ごと破棄され
    # iteration=1から再スタートしていた（NVIDIA Nemotron 3 Ultra使用時にAPIエラー頻度が上がり
    # 実害が拡大したことで発覚）。tools無し単発呼び出し経路はcross-iteration状態を持たないため
    # 影響なく、この初期化は変更しない。
    loop_messages: list[dict] = list(messages)
    tool_calls_used = 0
    python_calls_log: list[dict] = []  # BL-033: 実行したpython_replのcode/resultを蓄積
    reasoning_parts_all: list[str] = []  # [R5 F-2.1] 全iterationのreasoningを蓄積
    iteration_start = 1  # [BL-122] APIエラーで再試行する際、同じiteration番号から再開する

    # [BL-202] 従来は`for attempt in range(len(delays) + 1)`だったが、delays消尽後の
    # 「ノードやり直し」（loop_messagesを保持したままattemptカウンタだけ巻き戻す）を
    # 表現するためwhileへ変更した。成功時は本体内のreturnで関数を抜けるため、この
    # ループを正常に抜ける経路は存在しない（例外処理側でのみreturn/継続を決める）。
    # ループ本体は一切変更していない（attemptは例外処理ブロック内でしか参照されない）。
    attempt = 0
    node_redo_count = 0
    while True:
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
            if label_lower in ("user ai", "decision extractor", "orchestrator", "facilitator"):
                # [BL-109] orchestrator/facilitatorはBL-093以前と同じくtools=None（think無し）に
                # 戻したが、reasoning_effort_levelは元々`elif tools is not None`経由でしか付与
                # されていなかったため、明示的にlabelへ追加しないとtools=None化の副作用として
                # サイレントにreasoningが無効化されてしまう（実装時に発見・修正）。
                reasoning_effort_level = "medium"
            elif label_lower == "reflection" or label_lower == "review" or label_lower == "detector" or label_lower == "except":
                reasoning_effort_level = "high"
            elif tools is not None:
                reasoning_effort_level = "medium"

            create_kwargs["max_tokens"] = get_max_tokens(label_lower)
            # 🌟 【追加部分】OpenRouter使用時のみ、高速プロバイダーを強制指定する
            if "openrouter" in str(client.base_url):
                if _USE_STICKY_SESSION_ROUTING:
                    # [BL-107] provider.orderを外し、run_id+labelで安定したsession_idを渡す。
                    # 同一ノード種別・同一runの連続リクエスト（＝tools loopの各iteration）が
                    # 同じバックエンドへ固定され、プレフィックスキャッシュが機能する前提を満たす。
                    extra_body = {
                            "session_id": f"{_CURRENT_RUN_ID}-{label_lower}",
                        
                            #"provider":{
                            #     "order": ["deepinfra/fp4", "novita/fp8", "deepseek/fp8"],          
                            #            "allow_fallbacks": False # 全滅した場合は空いている他プロバイダーへ迂回
                            #}
                        
                    }
                else:
                    extra_body = {
                        "provider": {
                            # 推論速度が速いプロバイダーを左から順に優先して接続させる
                            #"order": ["venice/fp8", "novita/fp8", "xiaomi/fp8", "baidu/fp8", "fireworks", "streamlake/fp8", "novita/fp8" ],
                            #"order": ["fireworks","novita/fp8", "siliconflow/fp8" ,"parasail/fp8"],
                            #"order": ["deepinfra/fp4", "deepseek/fp8", "gmicloud/fp8", "baseten/fp8"],
                            #"order":  ["xiaomi/fp8"], 
                            "order": ["tencent/fp8"],
                            #"order": ["gmicloud/fp8","deepseek/fp8","alibaba/fp8","novita/fp8"],
                                                      
                            "allow_fallbacks": False # 全滅した場合は空いている他プロバイダーへ迂回
                        }
                    }
                if reasoning_effort_level is not None:
                    extra_body["reasoning"] = {"effort": reasoning_effort_level}
                create_kwargs["extra_body"] = extra_body

            if tools is None:
                # [UX] task_planner等、体感的な待ち時間が長いノード向けにストリーミング描画する。
                # 「思考が進んでいる感」を得る目的のみで、リトライ・エラー処理のロジックは
                # 非ストリーミング版と同一（finish_reason=="length"検出、例外は外側のexceptで捕捉）。
                create_kwargs["stream"] = True
                response_stream = client.chat.completions.create(**create_kwargs)
                reasoning_parts: list[str] = []
                content_parts: list[str] = []
                reasoning_started = False
                content_started = False
                finish_reason = None
                for chunk in response_stream:
                    if not chunk.choices:
                        continue
                    delta = chunk.choices[0].delta
                    finish_reason = chunk.choices[0].finish_reason or finish_reason
                    delta_reasoning = getattr(delta, "reasoning", None)
                    if delta_reasoning:
                        if not reasoning_started:
                            print(f"💭 [{label}] 思考:\n", end="", flush=True)
                            reasoning_started = True
                        print(delta_reasoning, end="", flush=True)
                        reasoning_parts.append(delta_reasoning)
                    if delta.content:
                        if not content_started:
                            if reasoning_started:
                                print()  # 思考ブロックとの区切り改行
                            content_started = True
                        print(delta.content, end="", flush=True)
                        content_parts.append(delta.content)
                if reasoning_started or content_started:
                    print()
                if finish_reason == "length":
                    print(f" [{label_lower}] ⚠️ max_tokens超過により出力が打ち切られました")
                    raise ValueError("Output truncated due to max_tokens limit")
                global _LAST_REASONING_TEXT
                _LAST_REASONING_TEXT = "".join(reasoning_parts)
                content = "".join(content_parts)
                # [BL-160] モデルが最終回答をcontentではなくreasoningチャンネルへ丸ごと
                # 出力し終える事例（0807ドライランで3/3再現、finish_reason=="length"
                # ではないため打ち切りではなく自発的な終了）が確認された。この時点で
                # 上のlengthチェックは通過済みのため、reasoning全文を代替contentとして
                # 安全に採用できる（_safe_json_parseは説明文+JSON混在に既に対応済み）。
                if not content and _LAST_REASONING_TEXT:
                    print(f"⚠️ [{label}] contentチャンネルが空でしたが、reasoningチャンネルに出力を検知したため代替として使用します（BL-160）。")
                    content = _LAST_REASONING_TEXT
                return content if content else "(APIから空の応答が返されました)"

            # --- R2.3: ツール呼び出しループ（query_AI集約方式、D-008準拠） ---
            # [CONSTRAINT] 既存try/exceptリトライブロックの内側で回す（D-004）。1回のcreate()が
            # 一時的なAPI障害で失敗した場合、loop_messagesごと破棄し最初からやり直す
            # （リトライ粒度が粗いことは許容済み、BL-009）。
            # [CONSTRAINT] MAX_TOOL_ITERは「ツール呼び出しの往復回数」の上限であり、全回がtool_calls
            # を返すと最終テキスト回答を送る余地が残らず非収束になる（実機ドライランで確認、BL-014）。
            # ユーザー承認によりAGENTS.md §7準拠で5→10へ変更。挙動を見て今後絞る可能性あり。
            # ユーザー承認によりAGENTS.md §7準拠で10→15へ変更（BL-028）。1タスク自身の範囲内の
            # 検算だけでも上限に迫るケースが実ドライランで確認されたため、まずクラッシュ回避を優先。
            # ユーザー承認によりAGENTS.md §7準拠で15→20へ変更（BL-093/D-071）。thinkツール導入で
            # 単独呼び出し（他ツールとバンドルしない軽量な思考単位）を許容する方針としたため、
            # 既にiter=15（旧上限ぎりぎり）に達した実績のあるtask_plan_reviewer等で予算超過が
            # 現実的になった。ReAct本来の「思考・作業を短く切って繰り返す」設計を優先し引き上げ。
            # ユーザー承認によりAGENTS.md §7準拠で20→30へ変更（BL-155/D-125）。task_plan_reviewerの
            # 差し戻し後、task_plannerが差戻し対象タスクの内容を1件ずつ把握し直す過程でiter=20に
            # 迫りツール呼び出し上限に抵触するケースが実ドライランで観測されたため引き上げ。
            MAX_TOOL_ITER = 50
            # [BL-122] loop_messages/tool_calls_used/python_calls_log/reasoning_parts_allは
            # 関数冒頭（forattemptループの外）で初期化済みのものをそのまま使う。ここで再初期化
            # すると、APIエラーによるリトライのたびに全iterationの進捗が失われてしまう。
            create_kwargs["messages"] = loop_messages
            create_kwargs["stream"] = True  # [UX] ツールループもstreamingで「思考中」感を出す
            # [BL-093/D-074] モデルがthinkツールを呼ぶかどうかに一切依存せず、reasoningの
            # 引き継ぎをシステム側で自動化する。当初は「古いiterは機械的に文字数で切り詰め」を
            # 検討したが、reasoning本文はiterによっては数百〜千字を超え（実ドライラン
            # `log/2026-07-26/1535`で確認）、単純な先頭/末尾切り詰めでは実質的な情報が失われる
            # （ユーザー指摘）。そこで「ツール呼び出しを含む全iterationはthinkをsummary付きで
            # 併用することを機械的に必須化」した（この強制自体はBL-110で撤廃済み、下記参照）。
            # [BL-106→BL-108→BL-111] reasoningの引き継ぎ方式は3段階の変遷を経ている。当初
            # （index 1固定差し替え→窓方式で要約）はいずれも「1つのメッセージを毎iter書き換える」
            # 構造だったため、そのメッセージの位置に関わらず、書き換えるたびにそれ以降のメッセージ
            # 全部の絶対位置がずれてプレフィックスキャッシュが毎iterミスしていた（BL-108時点でも
            # 「常に末尾に付け直す」だけでは、新規tool呼び出しメッセージが必ずdigestの手前に追加
            # されるため、次のリクエストでdigestの旧位置に別のメッセージが来ることになり同じ問題が
            # 残っていた。Gemini指摘、cela_main.py全文を提示しての第三者レビューで発覚）。最終的に、
            # 既存メッセージは一切書き換え・削除・移動せず、iterationごとの生reasoningを独立した
            # 新規メッセージとして末尾に追記するだけ（真の単調増加）に統一した。窓・要約・digest
            # オブジェクト追跡のための変数は不要になったため撤去済み。
            # [CONSTRAINT] BL-014原因A: python_replは1回のツールループの間だけ状態を保持する
            # 対話セッションとする（ノード・リトライをまたいだ状態共有はしない、毎回新規生成）。
            # try/finallyで、成功・非収束・例外いずれの終了経路でも子プロセスを確実に終了させる。
            repl_session = _PythonReplSession()
            try:
                for iteration in range(iteration_start, MAX_TOOL_ITER + 1):
                    # [BL-122] このiterationのAPI呼び出しが例外で失敗し外側のfor attemptが
                    # リトライされた場合、for iterationは`iteration_start`から再開する。ここで
                    # 都度更新することで、再開時に同じiteration番号からやり直せる（1から
                    # 再スタートしない、かつ既に成功したiterationを重複実行しない）。
                    iteration_start = iteration
                    # [CONSTRAINT] BL-060: BL-016/BL-056bの「残り回数」通知はあくまで依頼であり、
                    # モデルが最終許容iterationでもツール呼び出し（例: write_agreement）を選んでしまうと
                    # 次のiterationが存在せずそのまま非収束クラッシュする事例が実機ドライランで確認された
                    # （log/2026-07-23/1453、iter=15でwrite_agreement成功直後にクラッシュ）。
                    # 最終iterationのみ`tools`を外し、API側の構造としてツール呼び出しを不可能にすることで
                    # 必ずテキスト最終応答が返る（クラッシュしない）ことを保証する。
                    # [BL-093] thinkツールのreasoning_log/python_repl生ログにiter番号を機械的に
                    # 刻むため、ループ本体で唯一グローバルにこの値を公開する（モデルの自己申告に
                    # 頼らない。ループ制御フロー自体は変更しない最小限の追加）。
                    global _CURRENT_TOOL_LOOP_ITERATION
                    _CURRENT_TOOL_LOOP_ITERATION = iteration
                    call_kwargs = create_kwargs
                    if iteration == MAX_TOOL_ITER and "tools" in create_kwargs:
                        call_kwargs = {k: v for k, v in create_kwargs.items() if k != "tools"}
                        print(f"⚠️ [{label}] 最終iteration（{iteration}）のためツールを外し、テキスト最終応答を強制します")
                    # [UX] stream=Trueで届くchunkを、reasoning/content/tool_callsの3種に分けて
                    # リアルタイム描画しつつ蓄積する。tool_callsは複数の呼び出しがindex単位で
                    # 断片的に届く（id/function.name/function.argumentsがそれぞれ複数chunkに
                    # またがることがある）ため、indexごとに文字列連結して復元する。
                    stream = client.chat.completions.create(**call_kwargs)
                    _reasoning_start_idx = len(reasoning_parts_all)  # [BL-093] このiter分の切り出し用
                    content_parts: list[str] = []
                    reasoning_started = False
                    content_started = False
                    finish_reason = None
                    tool_call_accum: dict[int, dict] = {}
                    for chunk in stream:
                        if not chunk.choices:
                            continue
                        delta = chunk.choices[0].delta
                        finish_reason = chunk.choices[0].finish_reason or finish_reason
                        delta_reasoning = getattr(delta, "reasoning", None)
                        if delta_reasoning:
                            if not reasoning_started:
                                print(f"💭 [{label}] 思考（iter={iteration}）:\n", end="", flush=True)
                                reasoning_started = True
                            print(delta_reasoning, end="", flush=True)
                            reasoning_parts_all.append(delta_reasoning)
                        if delta.content:
                            if not content_started:
                                if reasoning_started:
                                    print()  # 思考ブロックとの区切り改行
                                print(f"💬 [{label}] 発言（iter={iteration}）:\n", end="", flush=True)
                                content_started = True
                            print(delta.content, end="", flush=True)
                            content_parts.append(delta.content)
                        if getattr(delta, "tool_calls", None):
                            for tc_delta in delta.tool_calls:
                                entry = tool_call_accum.setdefault(
                                    tc_delta.index, {"id": None, "name": "", "arguments": ""}
                                )
                                if tc_delta.id:
                                    entry["id"] = tc_delta.id
                                if tc_delta.function:
                                    if tc_delta.function.name:
                                        entry["name"] += tc_delta.function.name
                                    if tc_delta.function.arguments:
                                        entry["arguments"] += tc_delta.function.arguments
                    if reasoning_started or content_started:
                        print()

                    # [CONSTRAINT] max_tokens超過によるtool_call引数の途中切れをここで検出する（D-009）。
                    # ValueErrorはAPIError系ではないため下記exceptに飲み込まれず、原因が伝播する。
                    if finish_reason == "length":
                        print(f"⚠️ [{label}] ツールループ内でmax_tokens超過により出力が打ち切られました（iter={iteration}）")
                        raise ValueError("Tool call output truncated due to max_tokens limit")

                    tool_calls_list = [
                        _StreamToolCall(entry["id"], entry["name"], entry["arguments"])
                        for _, entry in sorted(tool_call_accum.items())
                    ] if tool_call_accum else None
                    msg = _StreamMessage("".join(content_parts) or None, tool_calls_list)

                    if not getattr(msg, "tool_calls", None):
                        print(f"✅ [{label}] ツールループ終了（iter={iteration}, tool_calls使用={tool_calls_used}回）")
                        if tool_calls_used == 0:
                            print(f"⚠️ [{label}] python_replを一度も使わずに応答しました（F-2.6監査対象）")
                        global _LAST_PYTHON_CALLS
                        _LAST_PYTHON_CALLS = python_calls_log
                        _LAST_REASONING_TEXT = "".join(reasoning_parts_all)
                        content = msg.content
                        # [BL-160] tools=None分岐と同型の欠陥：最終iterationがcontent空・
                        # reasoning非空のまま終了するケースへの対処。過去iterationの無関係な
                        # 思考が混ざらないよう、_reasoning_start_idx（BL-093でdigest切り出し用に
                        # 導入済み）で「このiterationだけ」のreasoningに絞って代替採用する。
                        if not content:
                            _final_iter_reasoning = "".join(reasoning_parts_all[_reasoning_start_idx:])
                            if _final_iter_reasoning:
                                print(f"⚠️ [{label}] 最終回答のcontentチャンネルが空でしたが、このiterationのreasoningチャンネルに出力を検知したため代替として使用します（BL-160）。")
                                content = _final_iter_reasoning
                        return content if content else "(APIから空の応答が返されました)"
                    loop_messages.append(msg.model_dump())

                    # [BL-093/D-074→BL-110] 当初はthinkをsummary付きで併用しない限りツール呼び出しを
                    # 一切実行せず差し戻す機械的強制を行っていたが、BL-108でネイティブのreasoning
                    # （delta.reasoning）が毎iter無条件にdigestへ蓄積されるようになったため、think有無に
                    # 関わらずreasoningの引き継ぎ自体は既に成立している。強制が本来解決していた問題が
                    # 解消された一方、差し戻し自体は実コスト（往復回数・トークン消費）としてこのセッション中
                    # 何度も観測されたため、ユーザー指示によりthinkツール自体は残しつつ強制（差し戻し）のみ
                    # 撤廃し、任意呼び出しに戻す。
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
                                # [BL-093] iter番号を機械的に記録（thinkツールのreasoning_logと
                                # 同じ「モデルの自己申告に頼らない」方針）。
                                python_calls_log.append({"code": args.get("code", ""), "result": result, "iteration": iteration})
                                # [BL-045] ループが正常終了する前（例: 次iterationでのAPIエラー例外）に
                                # 途中終了しても、実際に行われた検算の記録がBL-033のフェイルクローズ判定から
                                # 失われないよう、実行のたびに即時反映する（正常終了時のみの更新だと、
                                # write_agreement成功後にAPIエラーで打ち切られた場合、検算済みなのに
                                # 「python_repl未使用」と誤判定されホワイトボードが誤ロールバックされる：
                                # log/2026-07-22/2217で実機確認）。
                                _LAST_PYTHON_CALLS = python_calls_log
                                print(f"🔧 [{label}] python_repl 実行（iter={iteration}）:\n{args.get('code','')}\n→ {result}\n")
                            else:
                                # [CONSTRAINT] R3: python_repl以外のツール（read_verified_fact,
                                # read_deliverable_file, write_agreement等）は構造化された
                                # args辞書（dict）を受け取るため、辞書全体を渡す。
                                # 旧: handler(args.get("code","")) → 新: handler(args)
                                # [BL-131/TOOL_DISPATCH state化] さらに`state`も渡す。stateを
                                # 使わないハンドラはTOOL_DISPATCH側のラムダで無視する。
                                result = handler(args, state)
                                # [R3b §3.5.1] write_agreementが成功したらフラグをセット
                                # ★修正（レビュー指摘H1）: resultは生dict（json.dumps済み文字列ではない）
                                # なので、_safe_json_parseで再パースせず直接判定できる。
                                if tc.function.name == "write_agreement":
                                    if isinstance(result, dict) and result.get("success"):
                                        global _LAST_WRITE_AGREEMENT_SUCCEEDED
                                        _LAST_WRITE_AGREEMENT_SUCCEEDED = True
                                elif tc.function.name == "revise_goal":
                                    # [BL-086] revise_goalはツールハンドラ内でLangGraph stateに
                                    # 触れられないため、成功時の新旧goalテキストをここで
                                    # _LAST_GOAL_REVISIONへ橋渡しし、呼び出し元ノード
                                    # （generate_user_utterance_node）がstate["goal"]へ反映する。
                                    if isinstance(result, dict) and result.get("success"):
                                        global _LAST_GOAL_REVISION
                                        _LAST_GOAL_REVISION = {
                                            "new_goal_text": result.get("new_goal_text"),
                                            "old_goal_text": result.get("old_goal_text"),
                                            "escalation_id": result.get("escalation_id"),
                                            # [BL-186] 過去タスク再検証の強制plan_revision引き継ぎ用。
                                            "plan_revision_reason": result.get("plan_revision_reason") or "",
                                            "plan_revision_issue_ids": result.get("plan_revision_issue_ids") or [],
                                        }
                                elif tc.function.name == "write_issue":
                                    # [BL-158] detector_nodeがUser AIのターンを機械的に差し戻すか
                                    # 判定するため、RESOLVE/DEFERの成功をここで記録する
                                    # （_LAST_WRITE_AGREEMENT_SUCCEEDEDと同型のパターン）。
                                    if isinstance(result, dict) and result.get("success") and args.get("action_type") in ("RESOLVE", "DEFER"):
                                        global _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED
                                        _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED = True
                                        print(f"  ✅ [BL-158] write_issue({args.get('action_type')})成功を記録しました（今回のターンの機械的差し戻し判定に使用）。")
                                print(f"🔧 [{label}] {tc.function.name} 実行（iter={iteration}）: {json.dumps(args, ensure_ascii=False)}\n→ {result}\n")

                        loop_messages.append({
                            "role": "tool", "tool_call_id": tc.id,
                            "content": json.dumps(result, ensure_ascii=False),
                        })

                    # [BL-093/BL-111] 自動reasoningダイジェスト。当初（BL-108）は毎iter「全iterぶんを
                    # 1メッセージに再結合し、古いdigestを取り除いて末尾に付け直す」方式だったが、これは
                    # 新規のtool呼び出しメッセージが必ずdigestの手前に追加された後にdigestが再度末尾へ
                    # 移動するため、直前のリクエストでdigestが占めていた位置に次のリクエストでは別の
                    # メッセージ（新規tool呼び出し）が来ることになり、そこから後ろ全体が毎iterプレフィックス
                    # 不一致になっていた（Gemini指摘、cela_main.py全文を提示しての第三者レビューで発覚。
                    # 「一度追加したメッセージは二度と変更・削除・移動しない」という単調増加の条件を
                    # 満たせていなかった）。対策として、全iterを1メッセージに再結合するのをやめ、
                    # 「そのiterationの生reasoningだけ」を独立した新規メッセージとして末尾に追記し、
                    # 以後は一切触れない（既存メッセージの削除・移動をしない）方式に変更する。
                    _this_iter_reasoning = "".join(reasoning_parts_all[_reasoning_start_idx:])
                    if _this_iter_reasoning:
                        loop_messages.append({
                            "role": "system",
                            "content": f"【BL-093: iter {iteration} の思考ログ（自動保存）】\n{_this_iter_reasoning}",
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
                    # [CONSTRAINT] BL-016/BL-056b: モデルは自分が残りあと何回ツールを呼べるか知らないため、
                    # 検算を続けられる余地が残っていると誤認したままMAX_TOOL_ITERを使い切り、
                    # テキスト最終回答を一度も返せずに非収束クラッシュする事例が実機ドライランで確認された
                    # （組合せ最適化的なタスクでiter=9に妥当な結論が出ていたのにiter=10で無駄な再検算をした事例）。
                    # 残り回数が僅少になった時点で明示的に知らせ、次の応答で打ち切るよう促す。
                    # [BL-056b] しきい値を「残り2回」から「残り3回」に前倒し。組合せ最適化的に
                    # 長時間探索するタスク（例: 複数の代替案を数値検討する場合）では「残り2回」の
                    # 通知では長い最終回答（成果物の書き出し含む）を書き切る前に上限を超えて
                    # 非収束クラッシュする事例が実機ドライランで確認された（log/2026-07-23/1256）。
                    remaining_iters = MAX_TOOL_ITER - iteration
                    if 0 < remaining_iters <= 3:
                        if remaining_iters == 1:
                            notice = (
                                f"[SYSTEM NOTICE] ツール呼び出しの残り回数はあと{remaining_iters}回です。"
                                f"これ以上ツールを呼ばず、次の応答で必ずテキストのみの最終回答（成果物含む）を"
                                f"出力してください。中断すると非収束エラーになり、この応答自体が失われます。"
                            )
                        else:
                            notice = (
                                f"[SYSTEM NOTICE] ツール呼び出しの残り回数はあと{remaining_iters}回です。"
                                f"検算がすでに完了しているなら、次の応答はツールを呼ばずテキストで最終回答を出力してください。"
                                f"まだ検算が必要な場合も、残り{remaining_iters}回以内に収まるよう要点を絞ってください。"
                            )
                        loop_messages.append({"role": "user", "content": notice})
                        print(f"  ⏳ [{label}] ツール呼び出し残り回数が僅少です（残り{remaining_iters}回、iter={iteration}）。SYSTEM NOTICEを注入しました。")
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
        # [CONSTRAINT] BL-059: BL-022と同種の問題。streamingレスポンス受信中にプロバイダ側が
        # 接続を切ると、openai SDKでラップされる前の生のhttpx.RemoteProtocolError
        # （"peer closed connection without sending complete message body"）がそのまま
        # 送出され、絞り込んだ例外タプルに含まれず未捕捉のままプロセス全体をクラッシュさせていた
        # （実機ドライランで確認、log/2026-07-23）。これも一時的な接続障害でありロジックエラーでは
        # ないため、リトライ対象に追加する。
        # [CONSTRAINT] BL-072: BL-059と同種。streaming受信中の`httpx.ReadTimeout`も同様に
        # openai SDKの`APITimeoutError`へラップされず生のまま送出され未捕捉クラッシュしていた
        # （実機ドライランで確認）。個別の派生例外を都度追加するのではなく、`ReadTimeout`/
        # `ConnectTimeout`/`WriteTimeout`/`PoolTimeout`をすべて包含する親クラス
        # `httpx.TimeoutException`を追加し、同種の未捕捉タイムアウトの再発を防ぐ。
        # [CONSTRAINT] BL-083: BL-059/BL-072と同型の再発。streaming受信中に相手ホストから
        # 強制切断される（Windows WinError 10054）と、生の`httpx.ReadError`
        # （`httpcore.ReadError`由来）が送出され、絞り込んだexceptタプルに含まれず
        # 未捕捉クラッシュしていた（実機ドライラン`log/2026-07-24/1459`、BL-081修正後の
        # 通常運転中に発生。BL-082以降のロジックとは無関係な純粋なネットワーク層の欠落）。
        # 一時的な接続断でありロジックエラーではないため、リトライ対象に追加する。
        except (APIError, APIConnectionError, RateLimitError, APITimeoutError, json.JSONDecodeError, httpx.RemoteProtocolError, httpx.TimeoutException, httpx.ReadError) as e:

            # [BL-171] OpenRouter無料枠の日次上限は指数バックオフでのリトライでは解消しない
            # （X-RateLimit-Resetが翌日固定のタイムスタンプ）。他の一時的なAPIエラーと同じ
            # リトライ経路に乗せると、実ドライラン`log/2026-08-04/2344`のように無意味な
            # リトライ→JSON解析失敗→フェイルクローズ(major)を延々と繰り返し、その偽の
            # major判定がDetector等の判断へ混入して進行が破壊される。このパターンだけは
            # リトライせず即座に検知し、Ctrl+Cと同じ一時停止経路へ逃がす。
            if isinstance(e, RateLimitError) and "per-day" in str(e):
                print(f"\n🚨 [{label}] OpenRouter無料枠の日次上限に達しました。リトライせず一時停止します: {e}")
                raise DailyQuotaExhaustedError(str(e)) from e

            if attempt < len(delays):
                # [BL-046] 中間リトライは従来何も表示せずtime.sleepするだけだったため、
                # tools付きツールループの途中で発生した場合にloop_messages/python_calls_logが
                # サイレントに破棄されiter=1へ巻き戻る（BL-009の既知の粗いリトライ粒度、当時の
                # 実際の挙動）様子がユーザーから見て「iterが同じループに見える」謎の挙動になって
                # いた（log/2026-07-22/2300で実機確認）。可視化のためリトライ発生自体をログ出力する。
                # [BL-122] その後loop_messages/iteration_start等が関数冒頭（forattemptループの外）で
                # 保持されるようになり、実際にはiter=1へは巻き戻らなくなった（BL-156でログ文言を追従）。
                # [BL-156] BL-122以前は本当にiter=1へ巻き戻っていたためこの文言だったが、
                # 現在はloop_messages/iteration_startが関数冒頭で保持されリトライを跨いで
                # 生き残るため、実際にやり直されるのは失敗した「このiterationのAPI呼び出し」
                # 1回分のみ（過去iterationの思考ログ・tool結果は失われない）。表示文言が
                # 古い挙動の説明のまま実装と食い違っていたため修正。
                print(
                    f"\n🔄 [{label}] 一時的なAPIエラー、{delays[attempt]}秒後にこのiterationの"
                    f"API呼び出しをやり直します（attempt {attempt + 1}/{len(delays) + 1}）: {e}"
                )
                time.sleep(delays[attempt])
                attempt += 1
            elif node_redo_count < _MAX_NODE_REDO_ON_API_EXHAUSTION:
                # [BL-202] delaysを使い切ってもなお失敗。ここでプレースホルダー文字列を返すと、
                # それが「このノードの回答」として下流（Detector等）へ流れ、実質的に何も
                # 作業していないラウンドが1回消費される。loop_messages（それまでのreasoning・
                # ツール結果）は関数冒頭で初期化されattemptをまたいで保持されているため、
                # attemptカウンタだけ巻き戻せば「思考ログを重ねたままノードをやり直す」形になる。
                node_redo_count += 1
                print(
                    f"\n♻️ [{label}] APIリトライを全て使い切りました。これまでの思考ログ"
                    f"（{len(loop_messages)}メッセージ・iteration {iteration_start}まで）を保持したまま、"
                    f"{_NODE_REDO_COOLDOWN_SECONDS}秒後にノードをやり直します"
                    f"（node redo {node_redo_count}/{_MAX_NODE_REDO_ON_API_EXHAUSTION}）: {e}"
                )
                time.sleep(_NODE_REDO_COOLDOWN_SECONDS)
                attempt = 0
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
    # [BL-089] 従来は「先頭が```で始まるか」だけを見ており、(a)説明文の後に1つだけ
    # フェンスが来るケース（BL-088、先頭判定に引っかからず素通りしていた）、(b)モデルが
    # 「下書き（一部フィールドのプレビュー）」→「### 最終JSON出力」のように**複数の
    # ```json...```ブロック**を続けて出すケース（実ドライラン`log/2026-07-25/1814`で
    # 確認、task_plan_reviewerが正しく"major"と判定したのに、1つ目の小さな配列ブロックと
    # 2つ目の完全なオブジェクトブロックが混線して構文エラーとなり、fallback
    # （constraint_issue="none"）に化けて縮退計画がそのまま承認・実行されてしまった）
    # のいずれも取りこぼしていた。正規表現で全フェンスブロックを検出し、**最後の**
    # ブロック（モデルが「最終的な答え」を最後に書く慣習に従う）を優先的に採用する。
    cleaned = raw.strip()
    fence_matches = list(re.finditer(r"```(?:json)?\s*\n?(.*?)```", cleaned, re.DOTALL))
    if fence_matches:
        cleaned = fence_matches[-1].group(1).strip()
    elif cleaned.startswith("```"):
        cleaned = cleaned.removeprefix("```json").removeprefix("```").strip()
        idx = cleaned.find("```")
        if idx != -1:
            cleaned = cleaned[:idx].strip()
    # 段階2: 先頭が `{` や `[` でない場合、最初の { または [ を探す
    # [BL-088] 従来はbrace_idxが見つかれば常にそちらを優先しており、トップレベルが配列
    # （例: call_task_plannerのfallbackはlist）かつ、コードフェンス前に説明文が付く場合
    # （例:「それでは、フェーズ分解を提示します。\n\n```json\n[{...}]」）、実際には
    # bracket_idxの方が先に現れるのに、その手前の`[`を読み飛ばして`{`から開始してしまい、
    # 有効なJSON配列が構文エラーとなりfallback（縮退した1タスク計画）に化けるバグがあった
    # （実ドライラン`log/2026-07-25/1642`で2回連続再現、task_plan_reviewerの差し戻し
    # リトライ上限を無駄撃ちさせた）。`{`/`[`のどちらが先に現れるかで判定する。
    if cleaned and cleaned[0] not in ("{", "["):
        brace_idx = cleaned.find("{")
        bracket_idx = cleaned.find("[")
        candidates = [i for i in (brace_idx, bracket_idx) if i != -1]
        start = min(candidates) if candidates else -1
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
    tools: list[dict] | None, fallback: dict, max_retries: int = 2, state: dict | None = None,
) -> tuple[dict, bool]:
    """【SLM要約】
    D-005: ツール付与によりuse_json_mode=Falseとなるノード向けの層2リトライ。
    _safe_json_parseがfallback（同一オブジェクト）をそのまま返した場合をパース失敗とみなし、
    ノード呼び出し自体を再試行する（既存のAPI呼び出し失敗リトライ＝層1とは独立）。
    戻り値: (parsed_or_fallback, parse_failed)。parse_failed=Trueは上限を使い切ったことを示す
    （呼び出し元でフェイルクローズ処理を行うこと）。
    [BL-131/TOOL_DISPATCH state化] `state`はquery_AIへそのまま透過する。
    """
    for attempt in range(max_retries + 1):
        res = query_AI([{"role": "user", "content": prompt}], client=client, model=model, label=label, tools=tools, state=state)
        parsed = _safe_json_parse(res, fallback=fallback)
        if parsed is not fallback:
            return parsed, False
        # [BL-133] パース失敗のたびに生レスポンスの先頭を残す。フェイルクローズ(major)が
        # 「モデルの誤判定」なのか「JSONを一切出力できていない」（例: ツールループが
        # 最終テキストを一度も生成しないままMAX_TOOL_ITERへ達した等）なのかは、原因を
        # 見ないと切り分けられない（2026-07-30、test_detector_no_false_positive_within_capの
        # 3/3再現でこの区別ができず記録のみに留まった反省）。
        _res_preview = (res or "")[:300]
        print(f"⚠️ [{label}] JSON判定パース失敗を検知（生レスポンス冒頭300字: {_res_preview!r}）。層2リトライ {attempt + 1}/{max_retries}...")
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
        id TEXT, action_type TEXT, status TEXT, topic TEXT,
        decision_what TEXT DEFAULT '', reason_why TEXT DEFAULT '',
        proposed_by TEXT, entry_type TEXT, phase_id TEXT,
        depends_on TEXT, resource_claims TEXT, timestamp REAL,
        evidence TEXT, is_frozen INTEGER DEFAULT 0, internal_thought_process TEXT,
        citations TEXT DEFAULT '[]',
        run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_agreements_run_topic ON agreements(run_id, topic);
    CREATE INDEX IF NOT EXISTS idx_agreements_run_status ON agreements(run_id, status);

    CREATE TABLE IF NOT EXISTS whiteboard_drafts (
        draft_id TEXT, phase_id TEXT NOT NULL, task_id TEXT NOT NULL, version INTEGER,
        content TEXT, author_role TEXT, edit_summary TEXT, timestamp REAL, run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_wb_run ON whiteboard_drafts(run_id, phase_id, task_id);

    -- [BL-082] task_plannerの計画をwhiteboard_draftsと同型の版管理文書として永続化する。
    -- 別テーブルにするのは、whiteboard_drafts（Deliverable用、BL-080/081で修正したばかり）の
    -- キー空間に別用途を混在させるリスクを避けるため。
    CREATE TABLE IF NOT EXISTS plan_drafts (
        draft_id TEXT, phase_id TEXT NOT NULL, task_id TEXT NOT NULL, version INTEGER,
        content TEXT, author_role TEXT, edit_summary TEXT, timestamp REAL, run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_plan_run ON plan_drafts(run_id, phase_id, task_id);

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

    CREATE TABLE IF NOT EXISTS goal_shift_events (
        shift_id TEXT PRIMARY KEY,
        timestamp REAL NOT NULL,
        shift_kind TEXT NOT NULL,
        from_goal_state TEXT NOT NULL,
        to_goal_state TEXT NOT NULL,
        reason_why TEXT NOT NULL,
        evidence TEXT,
        triggered_by TEXT NOT NULL,
        triggering_agreement_id TEXT,
        run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_goal_shift_kind ON goal_shift_events(shift_kind);
    CREATE INDEX IF NOT EXISTS idx_goal_shift_timestamp ON goal_shift_events(timestamp);
    CREATE INDEX IF NOT EXISTS idx_goal_shift_run ON goal_shift_events(run_id);

    -- [BL-086] Expert/User AIが「ゴールの文言上の制約が真の目的と矛盾しているのでは」と
    -- 構造化した形でフラグを立てるエスカレーション記録。plan_drafts（版管理文書）とは異なり
    -- 単発の意思決定レコードのため専用テーブルとする。
    CREATE TABLE IF NOT EXISTS goal_escalations (
        escalation_id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        phase_id TEXT,
        task_id TEXT,
        raised_by_role TEXT NOT NULL,
        concern_summary TEXT NOT NULL,
        implicated_constraint TEXT NOT NULL,
        why_conflicts TEXT NOT NULL,
        suggested_reframe TEXT NOT NULL,
        status TEXT NOT NULL DEFAULT 'Open',
        resolution_reason TEXT,
        resolved_agreement_id TEXT,
        created_at REAL NOT NULL,
        resolved_at REAL
    );
    CREATE INDEX IF NOT EXISTS idx_goal_escalations_run_status ON goal_escalations(run_id, status);

    -- [BL-087 Stage3] task_planner分解より前に1回だけ行う「本質フェーズ」の結果。
    -- BL-086のgoal_escalations（走行中に前提矛盾に気づいた際の事後エスカレーション）とは
    -- 独立・併存する事前予防機構。run_idにつき1行のみ（goal_essence_nodeが冪等ガードで保証）。
    CREATE TABLE IF NOT EXISTS goal_essence (
        run_id TEXT PRIMARY KEY,
        true_essence TEXT NOT NULL,
        feasibility_notes TEXT,
        created_at REAL NOT NULL
    );

    -- [BL-096] Detector/User AIの軽微な懸念・訂正指示を、複数ターン・複数タスクをまたいで
    -- 追跡するための永続層。agreements/verified_factsとは異なり「まだ解決していない懸念」に
    -- 特化する。重複検知キーはtopic単独（task_id/phase_idはメタデータのみ）:
    -- BL-096の目的自体が「タスク横断の再発検知」であり、task_idをキーに含めると
    -- 別タスクでの再発が別行として扱われ、原理的にエスカレーションしなくなるため
    -- （設計時にD-080で発見・訂正）。
    CREATE TABLE IF NOT EXISTS issue_log (
        id TEXT PRIMARY KEY,
        run_id TEXT NOT NULL,
        topic TEXT NOT NULL,
        raised_by TEXT NOT NULL,
        phase_id TEXT DEFAULT '',
        task_id TEXT DEFAULT '',
        severity TEXT NOT NULL DEFAULT 'minor',
        status TEXT NOT NULL DEFAULT 'open',
        description TEXT NOT NULL,
        occurrence_count INTEGER NOT NULL DEFAULT 1,
        last_seen_task_id TEXT DEFAULT '',
        created_at REAL NOT NULL,
        updated_at REAL NOT NULL,
        resolved_by TEXT DEFAULT '',
        resolved_at REAL,
        resolution_note TEXT DEFAULT ''
    );
    CREATE INDEX IF NOT EXISTS idx_issue_run_topic ON issue_log(run_id, topic);
    CREATE INDEX IF NOT EXISTS idx_issue_run_status ON issue_log(run_id, status);

    -- [BL-126 Stage A] state["goal"]の全文履歴を版管理する（whiteboard_drafts/plan_draftsと
    -- 同型のappend-onlyバージョニング）。goalはrun_idにつき単一の文書であり複数task_idを
    -- 持たないため、phase_id/task_idは持たずrun_id単独で最新版を検索する
    -- （BL-131のtask_id単独検索とは異なる問題設定であり、混同しないこと）。
    CREATE TABLE IF NOT EXISTS goal_drafts (
        draft_id TEXT, version INTEGER, content TEXT, author_role TEXT,
        edit_summary TEXT, timestamp REAL, run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_goal_drafts_run ON goal_drafts(run_id);

    -- [BL-191] Stage4のschedule_task_focusツール呼び出しの構造化ログ兼版管理文書。goal_draftsと
    -- 同型のrun_id単位append-onlyバージョニングだが、contentはLLMが手書きするdiffの結果ではなく、
    -- decision_type/primary_task_id/companion_task_id/reasonからシステムが機械的に合成する
    -- 監査可能な要約文（BL-039のドット/アンダースコア混同バグを避けるため、machine-readable
    -- 列を主、contentは人間/LLMが読む副次的サマリーとして扱う）。
    CREATE TABLE IF NOT EXISTS scheduling_drafts (
        draft_id TEXT, version INTEGER, content TEXT, author_role TEXT,
        decision_type TEXT NOT NULL, primary_task_id TEXT, primary_phase_id TEXT,
        companion_task_id TEXT, companion_phase_id TEXT, reason TEXT,
        timestamp REAL, run_id TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_scheduling_drafts_run ON scheduling_drafts(run_id);

    -- [BL-204] 実世界事物レジストリ。verified_factsが「変数名→値」の平坦なストアなのに対し、
    -- こちらは「名前を持つ実世界の事物」を一級市民として保持する。log/2026-08-10/0901で、
    -- ゴール文に`公立諏訪東京理科大学`とあるのにExpertが記憶から「長野大学」（実在するが
    -- 無関係な大学）と書き、ゴール文由来の学生数だけを流用する事故が起きた。数値は
    -- verified_factsにあったが**名称そのものが事実として登録されていなかった**ため、
    -- すり替わりを検出する対象が存在しなかったことが原因。
    -- 設計: docs/design/back_log/BL-204/BL204_basic_design.md
    CREATE TABLE IF NOT EXISTS entities (
        run_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        canonical_name TEXT NOT NULL,   -- 正典表記（ゴール文の表記をそのまま）
        entity_type TEXT NOT NULL,      -- "place"/"organization"/"service"等、自由
        aliases TEXT DEFAULT '[]',      -- [BL-204] v1はゴール文初期登録のみが設定する
        origin TEXT NOT NULL,           -- "goal_text" | "discovered"
        created_by TEXT, created_at REAL,
        PRIMARY KEY (run_id, entity_id)
    );
    CREATE INDEX IF NOT EXISTS idx_entities_run ON entities(run_id);

    -- [BL-204] 事物の属性。attr_nameは完全に自由（対象・要件により可変）だが、出典封筒
    -- （value/unit/confidence/citations/reason/source_task_id）は必須とする。構造化の価値は
    -- 属性名の統制ではなく「1属性ごとに出典と確度が付くこと」にあるため。
    -- [CONSTRAINT] confidenceはverified_factsと同じ confirmed|provisional の2値のみ。
    -- 「工学的仮定」は citations[].type="expert_calculation" で表す（確定度と出所は直交する
    -- 2軸であり、confidenceへassumptionを足すのは語彙の二重化になる。BL204設計書§2.1.1）。
    CREATE TABLE IF NOT EXISTS entity_attributes (
        run_id TEXT NOT NULL,
        entity_id TEXT NOT NULL,
        attr_name TEXT NOT NULL,
        value TEXT NOT NULL,
        unit TEXT DEFAULT '',
        confidence TEXT DEFAULT 'provisional',
        citations TEXT DEFAULT '[]',
        reason TEXT DEFAULT '',
        source_task_id TEXT, source_phase_id TEXT,
        confirmed_by TEXT, confirmed_at REAL,
        PRIMARY KEY (run_id, entity_id, attr_name)
    );
    CREATE INDEX IF NOT EXISTS idx_entity_attributes_run ON entity_attributes(run_id, entity_id);
    """)
    _ensure_agreements_task_id_column(conn)
    _ensure_agreements_citations_column(conn)
    _ensure_verified_facts_r3a_columns(conn)
    _ensure_issue_log_defer_column(conn)
    _ensure_issue_log_acknowledge_columns(conn)


def _ensure_issue_log_defer_column(conn: sqlite3.Connection) -> None:
    """[BL-136] issue_logへdefer_to_task_id列を追加する。BL-082の「申し送り」
    （entry_type=Directive, status=Deferred, defer_to_task_id）と同じ思想を
    issue_logにも導入し、「今すぐ解決」と「明示的に将来のtaskへ先送り」の
    二択をUser AIに与える（強制解決一辺倒による無期限ブロックを避けるため）。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    if "defer_to_task_id" not in cols:
        print("  🛠️ [schema migration] issue_logへdefer_to_task_id列を追加します（BL-136）。")
        conn.execute("ALTER TABLE issue_log ADD COLUMN defer_to_task_id TEXT DEFAULT ''")
        conn.commit()


def _ensure_issue_log_acknowledge_columns(conn: sqlite3.Connection) -> None:
    """[BL-194] issue_logへacknowledged_until_round/acknowledged_count/acknowledge_reasonを
    追加する。RESOLVE（本当に解決した）でもDEFER（別タスクの責務である）でもない、第3の
    正直な選択肢——「現在タスクの責務であり、今まさに対応中である」——を表現するための補助列。
    statusの語彙は増やさない（D-079/D-080の`severity='major' ⇒ status='escalated'`不変条件を
    BL-096系全経路が依存しており、拡張すると全経路から不可視になりBL-158を無効化する万能の
    逃げ道になってしまうため。D-165参照）。BL-136の_ensure_issue_log_defer_columnと同型の
    ALTERベース冪等マイグレーション。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(issue_log)").fetchall()}
    if "acknowledged_until_round" not in cols:
        print("  🛠️ [schema migration] issue_logへACKNOWLEDGE用の3列を追加します（BL-194）。")
        conn.execute("ALTER TABLE issue_log ADD COLUMN acknowledged_until_round INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE issue_log ADD COLUMN acknowledged_count INTEGER DEFAULT 0")
        conn.execute("ALTER TABLE issue_log ADD COLUMN acknowledge_reason TEXT DEFAULT ''")
        conn.commit()


def _ensure_agreements_task_id_column(conn: sqlite3.Connection) -> None:
    """[CONSTRAINT] BL-023/BL-024: SQLiteはADD COLUMN IF NOT EXISTSを持たないため、
    既存DB（cela.db）との後方互換のため存在確認してから追加する。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    if "task_id" not in cols:
        print("  🛠️ [schema migration] agreementsへtask_id列を追加します（BL-023/BL-024）。")
        conn.execute("ALTER TABLE agreements ADD COLUMN task_id TEXT DEFAULT ''")
        conn.commit()


def _ensure_agreements_citations_column(conn: sqlite3.Connection) -> None:
    """[BL-188] agreementsへcitations列（引用元JSON配列）を追加する。既存の
    verified_facts.citations（F-3.9/R3a）はentry_type='Decision'等（confirmed_variables経由の
    構造化ファクトのみ）に限られていたが、Decision/Deliverable本体そのものには構造化された
    ソース欄が一切存在しなかった（自由記述のevidence列のみ）。
    _ensure_agreements_task_id_columnと同型のマイグレーションパターン。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(agreements)").fetchall()}
    if "citations" not in cols:
        print("  🛠️ [schema migration] agreementsへcitations列を追加します（BL-188）。")
        conn.execute("ALTER TABLE agreements ADD COLUMN citations TEXT DEFAULT '[]'")
        conn.commit()


def _ensure_verified_facts_r3a_columns(conn: sqlite3.Connection) -> None:
    """[F-3.9] R3a: verified_factsテーブルに構造化ファクトストア用の列を追加する。
    reason（理由）、citations（引用元JSON）、confidence（confirmed/provisional）。
    SQLiteのALTER TABLE ADD COLUMNはIF NOT EXISTSを持たないため、
    PRAGMA table_infoで既存列を確認してから追加する。"""
    cols = {row[1] for row in conn.execute("PRAGMA table_info(verified_facts)").fetchall()}
    if "reason" not in cols:
        print("  🛠️ [schema migration] verified_factsへreason列を追加します（F-3.9/R3a）。")
        conn.execute("ALTER TABLE verified_facts ADD COLUMN reason TEXT DEFAULT ''")
    if "citations" not in cols:
        print("  🛠️ [schema migration] verified_factsへcitations列を追加します（F-3.9/R3a）。")
        conn.execute("ALTER TABLE verified_facts ADD COLUMN citations TEXT DEFAULT '[]'")
    if "confidence" not in cols:
        print("  🛠️ [schema migration] verified_factsへconfidence列を追加します（F-3.9/R3a）。")
        conn.execute("ALTER TABLE verified_facts ADD COLUMN confidence TEXT DEFAULT 'confirmed'")
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
    print(f"  📌 [DB] decisionsへINSERT: id={d.get('id')}, who={d.get('who')}, "
          f"what={str(d.get('what'))[:60]}")


def db_append_goal_shift_event(shift: dict, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    [R5 GoalShiftEvent] detect_goal_shiftが返したイベントをgoal_shift_eventsテーブルへコミットする。
    """
    conn.execute(
        "INSERT INTO goal_shift_events (shift_id, timestamp, shift_kind, from_goal_state, to_goal_state, "
        "reason_why, evidence, triggered_by, triggering_agreement_id, run_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            f"GS-{int(time.time() * 1000)}", time.time(), shift.get("shift_kind"),
            shift.get("from_goal_state"), shift.get("to_goal_state"), shift.get("reason_why"),
            shift.get("evidence"), shift.get("triggered_by"), shift.get("triggering_agreement_id"),
            run_id,
        )
    )
    print(f"  🔄 [DB] goal_shift_eventsへINSERT: shift_kind={shift.get('shift_kind')}, "
          f"triggered_by={shift.get('triggered_by')}")


def db_save_goal_essence(conn: sqlite3.Connection, run_id: str, true_essence: str, feasibility_notes: str) -> None:
    """[BL-087 Stage3] goal_essence_nodeが1回だけ書き込む。run_idにつき1行のみの想定
    （呼び出し側のgoal_essence_doneガードで保証、ここではINSERT OR REPLACEで冪等にしておく）。
    """
    conn.execute(
        "INSERT OR REPLACE INTO goal_essence (run_id, true_essence, feasibility_notes, created_at) VALUES (?,?,?,?)",
        (run_id, true_essence, feasibility_notes, time.time())
    )
    print(f"  🎯 [DB] goal_essenceへINSERT OR REPLACE: run_id={run_id}")


def get_goal_essence(conn: sqlite3.Connection, run_id: str) -> dict | None:
    """[BL-087 Stage3] 保存済みの本質フェーズ結果を取得する。未生成ならNone。"""
    row = conn.execute("SELECT * FROM goal_essence WHERE run_id=?", (run_id,)).fetchone()
    return dict(row) if row else None


def _get_goal_essence_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-087 Stage3] 全ノードのシステムプロンプトへ、ゴール本文と並べて常時注入するための
    整形済みテキスト。未生成（本質フェーズ未実行）の場合は空文字を返す。
    """
    essence = get_goal_essence(conn, run_id)
    if not essence:
        return ""
    return (
        "【🎯 本質（プロジェクト開始時の壁打ちで言語化した、真に達成すべきこと）】\n"
        f"{essence['true_essence']}\n"
        + (f"【実現可能性メモ】\n{essence['feasibility_notes']}\n" if essence.get('feasibility_notes') else "")
    )


def db_append_agreement(a: dict, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    Agreementレコードをagreementsテーブルへ即時コミットする（state["agreements"].appendの置換先）。
    BL-001によりAgreementは decision_what/reason_why をネイティブに保持するため、エイリアス変換は行わない。
    """
    depends_on_val = json.dumps(a.get("depends_on", []), ensure_ascii=False) if isinstance(a.get("depends_on"), (list, dict)) else (a.get("depends_on") or "[]")
    resource_claims_val = json.dumps(a.get("resource_claims", {}), ensure_ascii=False) if isinstance(a.get("resource_claims"), (list, dict)) else (a.get("resource_claims") or "{}")
    citations_val = json.dumps(a.get("citations", []) or [], ensure_ascii=False)
    conn.execute(
        "INSERT INTO agreements (id, action_type, status, topic, decision_what, reason_why, proposed_by, "
        "entry_type, phase_id, task_id, depends_on, resource_claims, timestamp, "
        "evidence, is_frozen, internal_thought_process, citations, run_id) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (a.get("id"), a.get("action_type"), a.get("status"), a.get("topic"),
         a.get("decision_what", ""), a.get("reason_why", ""), a.get("proposed_by"), a.get("entry_type"),
         a.get("phase_id"), a.get("task_id", ""),
         depends_on_val, resource_claims_val, a.get("timestamp"), None, 0, None, citations_val, run_id)
    )
    print(f"  📋 [DB] agreementsへINSERT: id={a.get('id')}, action={a.get('action_type')}, "
          f"status={a.get('status')}, topic={str(a.get('topic'))[:60]}")


def db_supersede_agreement(agreement_id: str, conn: sqlite3.Connection, run_id: str) -> None:
    """【SLM要約】
    既存agreementレコードを、リスト内ミューテーションではなくUPDATE差分でstatus='Superseded'へ遷移させる。
    """
    conn.execute(
        "UPDATE agreements SET status='Superseded' WHERE id=? AND run_id=?",
        (agreement_id, run_id)
    )
    print(f"  ♻️ [DB] agreementsをSuperseded化: id={agreement_id}")


# [BL-073] Deliverableが承認された際、対応するtask_idのDirective（Userの指示）がstatus='Proposed'の
# ままDBに永久固定される問題への対処。従来はDirective自体を後から遷移させる経路が一切なく、
# reflection_nodeの「未解決」抽出（agreements.status=="Proposed"の全件、entry_type不問）に
# 既に履行済みの指示がノイズとして出続け、実ドライランでReflectionが毎回「なぜProposedのままか」
# の自問自答を強いられていた（根本原因未解消のため放置すると将来的に誤判定を誘発しうる）。
RESOLVING_DELIVERABLE_STATUSES = {"Approved", "Approved_with_Conditions", "Implicitly_Accepted"}


def _is_task_completed(conn: sqlite3.Connection, run_id: str, task_id: str) -> bool:
    """[BL-167] 指定task_idの最新Deliverableが完了相当（RESOLVING_DELIVERABLE_STATUSES）かを判定する。
    BL-145の滞留issue再構築フィルタが「defer_to_task_id設定済み＝受け皿タスクが存在する」ことだけを
    見て、その受け皿タスクが既に完了済みかどうかを一切検証していなかったため、受け皿タスクが完了
    してもissueが解決されないまま(defer_to_task_idが過去に一度でも設定された事実だけで)恒久的に
    タスク再構築の対象から除外され続ける「永久迷子」issueを生んでいた（実ログで確認、BL-167）。
    """
    if not task_id:
        return False
    for a in reversed(get_agreements_from_db(conn, run_id)):
        if a.get("entry_type") != "Deliverable" or a.get("task_id") != task_id:
            continue
        return a.get("status") in RESOLVING_DELIVERABLE_STATUSES
    return False


def _resolve_directive_for_task(conn: sqlite3.Connection, run_id: str, task_id: str, phase_id: str, resolved_by: str) -> None:
    """[BL-073] task_idに対応するentry_type='Directive'かつstatus='Proposed'の最新agreementを
    'Approved'へ遷移させ、指示が実際に履行されたことをDB上で表現する。該当が無ければ何もしない。
    """
    if not task_id:
        return
    for a in reversed(get_agreements_from_db(conn, run_id)):
        if a.get("entry_type") == "Directive" and a.get("task_id") == task_id and a.get("status") == "Proposed":
            db_supersede_agreement(a["id"], conn, run_id)
            resolved: Agreement = {
                "id": f"AG-{int(time.time() * 1000)}", "timestamp": time.time(),
                "action_type": "UPDATE", "entry_type": "Directive", "status": "Approved",
                "topic": a["topic"], "decision_what": a.get("decision_what", ""),
                "reason_why": f"対応するタスク（{task_id}）の成果物が承認されたため、指示は履行済みとして自動解決（BL-073）。",
                "proposed_by": a.get("proposed_by", "Unknown"), "phase_id": phase_id or a.get("phase_id", ""),
                "task_id": task_id, "depends_on": [], "resource_claims": {},
            }
            db_append_agreement(resolved, conn, run_id)
            print(f"  ✅ [Directive Resolved] '{a['topic']}' をApprovedへ遷移しました（{task_id}の成果物承認に伴う自動解決、BL-073）。")
            break


# ===========================================================================
# [R4] whiteboard_drafts: ホワイトボード差分パッチ化
# ===========================================================================

def get_latest_whiteboard(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str) -> dict | None:
    """[R4] 指定task_idの最新バージョンの{version, content}を返す。存在しなければNone。
    [BL-131] task_idはrun_id内で一意という命名規約を前提に、phase_idはWHERE句に含めず
    task_id単独で検索する（get_latest_plan_draft_by_task_idと同じ設計）。呼び出し元が
    誤ったphase_idを渡しても「該当なし」と誤判定してバージョンが1から再スタートする
    事故（1708ログのtask_1_1_reviewで観測）を防ぐ。呼び出し元が渡したphase_idと実際に
    保存されているphase_idが食い違う場合は、計画ミス・引数ミスの兆候として警告のみ行う。
    """
    row = conn.execute(
        "SELECT version, content, phase_id AS stored_phase_id FROM whiteboard_drafts "
        "WHERE run_id=? AND task_id=? ORDER BY version DESC LIMIT 1",
        (run_id, task_id)
    ).fetchone()
    if row is None:
        return None
    if phase_id and row["stored_phase_id"] and row["stored_phase_id"] != phase_id:
        print(f"  ⚠️ [Whiteboard phase_id不一致] task_id='{task_id}'の既存版はphase_id="
              f"'{row['stored_phase_id']}'で保存されていますが、今回'{phase_id}'が渡されました。"
              f"task_idの命名規約により正しい版として扱いますが、呼び出し元の引数を確認してください。")
    return {"version": row["version"], "content": row["content"]}


def _write_whiteboard_to_file(phase_id: str, task_id: str, version: int, content: str,
                               author_role: str, edit_summary: str) -> str | None:
    """[BL-085] apply_whiteboard_patchでDBへ新バージョンを保存するたびに、sqliteクエリなしで
    中身を確認・diffできるようMarkdownファイルへも書き出す（ユーザー要望）。DBが正であり、
    ここでの失敗は握りつぶして継続する（save_deliverable_to_fileと同じくベストエフォートの
    補助資料という位置づけ）。バージョンごとに個別ファイルとして残す（DB側のappend-only
    バージョニングと同じ扱い、上書きしない）。

    [CONSTRAINT] BL-027と同じ理由で、MultiLoggerが実際に初期化されている（＝実行時の
    ドライラン中である）場合のみ書き出す。BL-080〜BL-084のテストはtmp_path上のDBに対し
    apply_whiteboard_patchを大量に呼ぶため、無条件で書き出すと本番log/配下を
    テスト実行のたびに汚染してしまう。
    """
    if getattr(MultiLogger, "_instance", None) is None:
        return None
    safe_phase = re.sub(r'[\\/*?:"<>|]', "_", phase_id).strip() or "phase"
    safe_task = re.sub(r'[\\/*?:"<>|]', "_", task_id).strip() or "task"
    log_dir = getattr(MultiLogger, "log_dir", "log")
    wb_dir = os.path.join(log_dir, "whiteboards")
    try:
        os.makedirs(wb_dir, exist_ok=True)
        filepath = os.path.join(wb_dir, f"{safe_phase}_{safe_task}_V{version}.md")
        header = (
            f"<!-- phase_id={phase_id} task_id={task_id} version={version} "
            f"author_role={author_role} edit_summary={edit_summary} -->\n\n"
        )
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(header + content)
        return filepath
    except OSError as e:
        print(f"  ⚠️ [Whiteboard File Write Failed] ファイル書き出しに失敗しました（無視して続行）: {e}")
        return None


def apply_whiteboard_patch(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
                            new_content: str, author_role: str, edit_summary: str) -> int:
    """[R4] 現在の最新バージョンを取得し、new_contentを新バージョンとしてINSERTする。
    削除は行わずバージョンを積み増す方式（cela_r4_design.md §2.2、N-2のトレーサビリティ原則に従う）。
    ★修正（BL-085）: DB保存に加え、_write_whiteboard_to_fileでMarkdownファイルへも書き出す。
    """
    latest = get_latest_whiteboard(conn, run_id, phase_id, task_id)
    new_version = (latest["version"] + 1) if latest else 1
    conn.execute(
        "INSERT INTO whiteboard_drafts (draft_id, phase_id, task_id, version, content, author_role, edit_summary, timestamp, run_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (f"DF-{int(time.time()*1000)}", phase_id, task_id, new_version, new_content, author_role, edit_summary, time.time(), run_id)
    )
    _write_whiteboard_to_file(phase_id, task_id, new_version, new_content, author_role, edit_summary)
    print(f"  📄 [whiteboard_drafts] task_id={task_id}をVer.{new_version}に更新しました（author={author_role}）: {edit_summary}")
    return new_version


# ===========================================================================
# [BL-082] plan_drafts: task_plannerの計画のホワイトボード化（先送り事項の申し送り）
# ===========================================================================

_PLAN_DEFERRED_HEADING = "## 先送り事項（他タスクからの申し送り）"
_PLAN_DEFERRED_PLACEHOLDER = "(まだありません)"
_PLAN_DEFERRED_HEADING_RE = re.compile(r"(?m)^## 先送り事項（他タスクからの申し送り）\s*$")

# [BL-087 Stage2改善] task_plan_reviewer_nodeの指摘をplan_draftsへ書き込むための第二セクション。
# 「先送り事項」（他タスクからの申し送り、decision_extractor由来）とは別の見出しにするのは、
# 出所（他タスクからの申し送り vs 実行前レビューの指摘）を読み手が混同しないようにするため。
_PLAN_REVIEW_HEADING = "## レビュワーからの指摘（要修正）"
_PLAN_REVIEW_PLACEHOLDER = "(まだありません)"
_PLAN_REVIEW_HEADING_RE = re.compile(r"(?m)^## レビュワーからの指摘（要修正）\s*$")


def get_latest_plan_draft(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str) -> dict | None:
    """[BL-082] get_latest_whiteboardの完全なミラー。指定task_idの最新バージョンの
    {version, content}を返す。存在しなければNone。
    [BL-131] get_latest_whiteboardと同様、task_id単独で検索する（phase_idは食い違い検知のみ）。
    """
    row = conn.execute(
        "SELECT version, content, phase_id AS stored_phase_id FROM plan_drafts "
        "WHERE run_id=? AND task_id=? ORDER BY version DESC LIMIT 1",
        (run_id, task_id)
    ).fetchone()
    if row is None:
        return None
    if phase_id and row["stored_phase_id"] and row["stored_phase_id"] != phase_id:
        print(f"  ⚠️ [Plan Draft phase_id不一致] task_id='{task_id}'の既存版はphase_id="
              f"'{row['stored_phase_id']}'で保存されていますが、今回'{phase_id}'が渡されました。")
    return {"version": row["version"], "content": row["content"]}


def get_latest_plan_draft_by_task_id(conn: sqlite3.Connection, run_id: str, task_id: str) -> dict | None:
    """[BL-101] task_planner向け。task_plannerは特定のphase_idに紐づく実行文脈を持たず全フェーズを
    横断して扱うため、get_latest_plan_draftと異なりphase_id指定を要求しない。task_idはこのシステムの
    命名規約上run_id内で一意（例: "task_2_3"）であることを前提に、phase_idを問わず検索する。
    複数のphase_idにまたがって同名task_idが存在する事故を検知できるよう、該当行が2件以上の
    異なるphase_idにまたがる場合はNoneではなく最新版を返しつつ、呼び出し側のログで気づけるよう
    phase_idも結果に含める。"""
    row = conn.execute(
        "SELECT phase_id, version, content FROM plan_drafts "
        "WHERE run_id=? AND task_id=? ORDER BY version DESC LIMIT 1",
        (run_id, task_id)
    ).fetchone()
    return {"phase_id": row["phase_id"], "version": row["version"], "content": row["content"]} if row else None


def apply_plan_patch(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
                      new_content: str, author_role: str, edit_summary: str) -> int:
    """[BL-082] apply_whiteboard_patchの完全なミラー。現在の最新バージョンを取得し、
    new_contentを新バージョンとしてINSERTする（削除は行わずバージョンを積み増す）。"""
    latest = get_latest_plan_draft(conn, run_id, phase_id, task_id)
    new_version = (latest["version"] + 1) if latest else 1
    conn.execute(
        "INSERT INTO plan_drafts (draft_id, phase_id, task_id, version, content, author_role, edit_summary, timestamp, run_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (f"PL-{int(time.time()*1000)}", phase_id, task_id, new_version, new_content, author_role, edit_summary, time.time(), run_id)
    )
    print(f"  📄 [plan_drafts] task_id={task_id}をVer.{new_version}に更新しました（author={author_role}）: {edit_summary}")
    return new_version


def _render_plan_skeleton(task: dict) -> str:
    """[BL-082] タスク計画のプレースホルダ骨格文書を生成する。見出し文字列は固定・既知のため、
    後続の追記・抽出処理は正規表現によるヒューリスティックなクォート照合（BL-074/076/081で
    対応が必要だった脆さ）を一切必要としない。"""
    acceptance_criteria = task.get("acceptance_criteria", [])
    depends_on = task.get("depends_on", [])
    owns_variables = task.get("owns_variables", [])
    criteria_text = "\n".join(f"- {c}" for c in acceptance_criteria) or "- (なし)"
    depends_text = "\n".join(f"- {d}" for d in depends_on) or "- (なし)"
    owns_text = "\n".join(f"- {v}" for v in owns_variables) or "- (なし)"
    return (
        f"# {task.get('task_id', '')}: {task.get('title', '')}\n\n"
        f"## 概要\n{task.get('description', '')}\n\n"
        f"## 受入基準 (acceptance_criteria)\n{criteria_text}\n\n"
        f"## 依存タスク (depends_on)\n{depends_text}\n\n"
        f"## 確定すべき変数 (owns_variables)\n{owns_text}\n\n"
        f"{_PLAN_DEFERRED_HEADING}\n{_PLAN_DEFERRED_PLACEHOLDER}\n\n"
        f"{_PLAN_REVIEW_HEADING}\n{_PLAN_REVIEW_PLACEHOLDER}\n"
    )


def _append_deferred_note_to_plan(
    conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
    note_text: str, source_task_id: str, task_for_skeleton: dict | None
) -> bool:
    """[BL-082] 対象task_idの計画文書（plan_drafts）の「先送り事項」セクションへ、
    他タスクからの申し送りを追記する。文書が未生成（遅延シード）の場合は
    task_for_skeletonから骨格文書を生成した上で追記する。

    見出しの検索は行アンカー付き正規表現を使う（タスクのtitle/descriptionはLLM生成の
    自由文であり、偶然`## 先送り事項...`という部分文字列を含む可能性を排除するため）。
    追記位置は見出し直後に固定し、「次の見出しまでを探す」ロジックは使わない
    （note_text自体がLLM生成の自由文であり、偶然`\\n## `を含んだ場合に境界判定を
    誤るリスクを構造的に排除するため）。
    """
    latest = get_latest_plan_draft(conn, run_id, phase_id, task_id)
    if latest:
        content = latest["content"]
    elif task_for_skeleton:
        content = _render_plan_skeleton(task_for_skeleton)
    else:
        print(f"  ⚠️ [先送り事項追記失敗] task_id={task_id}のplan_draftが存在せず、骨格生成用のtask情報もありません。")
        return False

    match = _PLAN_DEFERRED_HEADING_RE.search(content)
    if not match:
        print(f"  ⚠️ [先送り事項追記失敗] task_id={task_id}のplan_draftに「先送り事項」見出しが見つかりません。")
        return False

    insert_at = match.end() + 1  # 見出し行の改行の直後
    remainder = content[insert_at:]
    bullet = f"- 【{source_task_id}より】{note_text}"
    if remainder.startswith(_PLAN_DEFERRED_PLACEHOLDER):
        new_remainder = bullet + remainder[len(_PLAN_DEFERRED_PLACEHOLDER):]
    else:
        new_remainder = bullet + "\n" + remainder
    new_content = content[:insert_at] + new_remainder

    apply_plan_patch(
        conn, run_id, phase_id, task_id, new_content,
        author_role="decision_extractor", edit_summary=f"[先送り事項] {note_text[:60]}"
    )
    return True


def _append_reviewer_comment_to_plan(
    conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
    comment_text: str, task_for_skeleton: dict | None
) -> bool:
    """[BL-087 Stage2改善] _append_deferred_note_to_planの完全なミラー。対象がtask_id単位で
    確実にマッチするため（Detectorのwhiteboard注釈のような文中excerpt一致は使わない。
    LLM生成の自由文に対する引用文字列マッチングの脆さはBL-074/076で既知の問題）、
    task_plan_reviewerの指摘を「レビュワーからの指摘（要修正）」セクションへ追記する。
    """
    latest = get_latest_plan_draft(conn, run_id, phase_id, task_id)
    if latest:
        content = latest["content"]
    elif task_for_skeleton:
        content = _render_plan_skeleton(task_for_skeleton)
    else:
        print(f"  ⚠️ [レビュワー指摘追記失敗] task_id={task_id}のplan_draftが存在せず、骨格生成用のtask情報もありません。")
        return False

    match = _PLAN_REVIEW_HEADING_RE.search(content)
    if not match:
        print(f"  ⚠️ [レビュワー指摘追記失敗] task_id={task_id}のplan_draftに「レビュワーからの指摘」見出しが見つかりません。")
        return False

    insert_at = match.end() + 1  # 見出し行の改行の直後
    remainder = content[insert_at:]
    bullet = f"- {comment_text}"
    if remainder.startswith(_PLAN_REVIEW_PLACEHOLDER):
        new_remainder = bullet + remainder[len(_PLAN_REVIEW_PLACEHOLDER):]
    else:
        new_remainder = bullet + "\n" + remainder
    new_content = content[:insert_at] + new_remainder

    apply_plan_patch(
        conn, run_id, phase_id, task_id, new_content,
        author_role="task_plan_reviewer", edit_summary=f"[レビュワー指摘] {comment_text[:60]}"
    )
    return True


def _get_deferred_notes_text(conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str) -> str:
    """[BL-082] 指定task_idの計画文書から「先送り事項」セクションの内容を抽出し、
    プロンプト埋め込み用のテキストを返す。文書が存在しない・プレースホルダのままの
    場合は空文字を返す（トークン消費を避けるため、「先送り事項はありません」という
    定型文は毎ターン出力しない）。
    """
    if not task_id:
        return ""
    latest = get_latest_plan_draft(conn, run_id, phase_id, task_id)
    if not latest:
        return ""
    content = latest["content"]
    match = _PLAN_DEFERRED_HEADING_RE.search(content)
    if not match:
        return ""
    # [BL-087 Stage2改善] 「レビュワーからの指摘」セクションが後続に追加されたため、
    # 末尾までではなく次の見出し（もしあれば）の直前までに範囲を限定する。
    next_heading = _PLAN_REVIEW_HEADING_RE.search(content, match.end())
    section_end = next_heading.start() if next_heading else len(content)
    section = content[match.end():section_end].strip()
    if not section or section == _PLAN_DEFERRED_PLACEHOLDER:
        return ""
    return f"【他タスクからの申し送り事項（先送り、要確認）】\n{section}\n"


def _get_task_focus_companion_text(state: LineageState) -> str:
    """[BL-191] task_focus_companionが設定されていれば、Expert/Detector/User AI Stage1へ
    追加のコンテキストとして注入するブロックを返す。BL-025のスコープガードレールは維持する
    （current_task_json等の「現在のタスク」定義自体は一切変更しない、あくまで並記情報）。
    """
    companion = state.get("task_focus_companion")
    if not companion:
        return ""
    return (
        f"🔗 【BL-191: 今回併せて考慮すべき関連タスク（あなたの担当タスクはあくまで現在のタスクのみです）】\n"
        f"task_id={companion['companion_task_id']}: {companion['reason']}\n"
        "このタスク自体の成果物を今すぐ書き換える必要はありません（それは発注者が別途"
        "redirect_backwardで正式に指示します）。ただし、現在のタスクの検討・監査において"
        "この関連タスクとの整合性を意識してください。もしこのタスクの成果物自体を修正する"
        "必要がある場合は、action_type='SUPERSEDE'を使ってください（現在のタスクではないため"
        "通常のUPDATEはBL-146ガードに拒否されます）。\n"
    )


def _build_task_focus_state_text(state: LineageState) -> str:
    """[BL-191] task_focus_stack/task_focus_companionの"現在の状態"を毎ターン明示的に
    描画する常設ステータス表示。state上に値があるだけではLLMのプロンプトには自動的に
    現れないため、明示描画が必須。one-shotの_build_task_focus_transition_noticeとは別物で、
    こちらはredirect_backward中は毎ターン繰り返し表示し続ける（Stage4・Detector・Reflection・
    Facilitatorへ注入し、意図的な手戻り中であることを一貫して伝える）。
    """
    lines = []
    stack = state.get("task_focus_stack") or []
    if stack:
        entry = stack[-1]
        lines.append(
            f"現在task_id='{state.get('current_task_id', '')}'（過去タスク）へ一時的にフォーカス中"
            f"（理由: {entry.get('reason', '')}）。復帰待ちの元タスク: '{entry.get('task_id', '')}'。"
        )
    companion = state.get("task_focus_companion")
    if companion:
        lines.append(
            f"companion: task_id='{companion.get('companion_task_id', '')}'が現在のタスク"
            f"'{companion.get('primary_task_id', '')}'と併記対象（理由: {companion.get('reason', '')}）。"
        )
    if not lines:
        return ""
    return "【🧭 BL-191: 現在のタスクフォーカス状況】\n" + "\n".join(lines) + "\n"


def _build_current_task_scope_brief(state: LineageState) -> str:
    """[BL-194] Reflection/Facilitator向けの、現在タスクのスコープ最小要約。

    [REJECTED] _build_task_scope_context（BL-023/025）の再利用は却下した。あちらは
    DBクエリ2本と、実測50KB超になり得るホワイトボード全文＋R4編集方針（write_agreement
    のeditsの使い方）を返すが、Reflection/Facilitatorはdeliverableを書く権限を持たず
    無意味であるうえ、Facilitatorについては BL-170（具体的issueを読んだFacilitatorが
    Expertの仕事を自分でやろうとしてMAX_TOOL_ITERを空費）の再現リスクを高める。
    ここではstateのみを読み、DBアクセスもホワイトボードも伴わない軽量版を返す。

    [BL-191] _build_task_focus_state_textと同じ「state上の値はプロンプトに自動では
    現れないので明示描画する」パターン・同じ注入先（Reflection/Facilitator）に揃える。

    log/2026-08-08/1514で、Reflection/Facilitatorがこのスコープを一切見ておらず、
    task_2_1のacceptance_criteria外（task_2_2の責務である車両台数・フリート実現可能性）
    の懸念を現タスクの義務であるかのように扱い続けた（Facilitator自身のthinkログにも
    「需要モデリングには7〜8台の車両が必要」とtask_2_2の問いを取り込んだ記述がある）。
    """
    task = _get_current_task(state)
    if not task:
        return ""
    criteria = task.get("acceptance_criteria", []) or []
    owns = task.get("owns_variables", []) or []
    lines = [
        f"task_id: {task.get('task_id','')}",
        f"目的: {task.get('description','')}",
        "acceptance_criteria（このタスクで満たすべき項目はこれが全てです）:",
        *([f"  - {c}" for c in criteria] or ["  (未定義)"]),
        f"owns_variables（このタスクが確定させる変数はこれが全てです）: {owns or '(なし)'}",
    ]
    return "【🎯 BL-194: 現在のタスクのスコープ】\n" + "\n".join(lines) + "\n"


def _build_task_focus_transition_notice(state: LineageState) -> str:
    """[BL-191] _apply_backward_redirect/_maybe_resume_forward_focus/_force_resume_forward_focusが
    直後に発火した場合、次のExpert/User AIターンへ一度だけ明示する通知
    （_build_task_transition_blocked_noticeと同じone-shot消費パターン、ただし別関心事のため
    別関数として独立させる——あちらはBL-125/176/190の「遷移をブロックした」通知、こちらは
    BL-191の「遷移を実際に行った/戻した」通知で意味が逆であり、混在させると読みにくくなる）。
    """
    redirect_notice = state.get("task_focus_redirect_notice")
    if redirect_notice:
        state["task_focus_redirect_notice"] = ""
        print(f"  📣 [BL-191] タスクフォーカス切替通知をLLMプロンプトへ注入します。")
        return f"\n【🧭 {redirect_notice}】\n"
    resume_notice = state.get("task_focus_resume_notice")
    if resume_notice:
        state["task_focus_resume_notice"] = ""
        print(f"  📣 [BL-191] タスクフォーカス復帰通知をLLMプロンプトへ注入します。")
        return f"\n【🧭 {resume_notice}】\n"
    return ""


def _build_stale_past_tasks_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-191] BL-163が起票したseverity="minor"の整合性再確認issue（
    topic LIKE "goal_revision_consistency_check_%"）のうち、まだstatus='open'のものを
    task_id単位で一覧化する。BL-186が発見した「read_issuesがpull型のため誰にも見られない」
    問題への、Stage4限定の能動的サーフェシング（BL-186自体は無変更、並存させる）。
    """
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='open' "
        "AND topic LIKE 'goal_revision_consistency_check_%' ORDER BY task_id, id",
        (run_id,)
    ).fetchall()
    if not rows:
        return ""
    lines = [f"- task_id={r['task_id']}: {r['description']}" for r in rows]
    return (
        "【🧭 BL-191/163: ゴール改定により整合性未確認のまま残っている過去タスク】\n"
        "これらは強制ではありませんが、必要と判断すればschedule_task_focus"
        "(decision_type=\"redirect_backward\")で今すぐ手戻り対応するか、"
        "joint_focusで現在のタスクと併せて考慮対象にできます。\n"
        + "\n".join(lines) + "\n"
    )


def _build_scheduling_history_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-191] scheduling_draftsの直近5件をStage4向けに短い行としてレンダリングし、
    ターンをまたいだ継続性を持たせる（「2ターン前にtask_2_3へリダイレクトした」等）。"""
    rows = get_scheduling_decision_history(conn, run_id, limit=5)
    if not rows:
        return ""
    lines = [r["content"] for r in reversed(rows)]
    return "【🗓️ BL-191: 直近のスケジューリング決定履歴】\n" + "\n".join(lines) + "\n"


def _get_frozen_agreements_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-086] Freeze済み（is_frozen=1）項目のみを抽出した軽量テキスト。Detectorの
    ドメイン妥当性レビューパス（従来agreements_textを一切受け取っていなかった）に、
    トークンコストを抑えたまま「これは既に審議済みの意図的な例外」というシグナルだけを
    渡すためのヘルパー（agreements_text全体を渡すと項目数に比例してコストが増える）。
    """
    rows = conn.execute(
        "SELECT * FROM agreements WHERE run_id=? AND is_frozen=1 AND status != 'Superseded' ORDER BY id", (run_id,)
    ).fetchall()
    if not rows:
        return ""
    lines = [
        f"🔒 [{r['id']}] {r['topic']}: {(r['decision_what'] or '')[:150]}"
        f"（Freeze理由: {(r['reason_why'] or '')[:100]}）"
        for r in rows
    ]
    return "【🔒 Freeze済み（人間の発注者が審議の上で承認した恒久的な例外）】\n" + "\n".join(lines) + "\n"


def _get_open_escalations_text(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-086] User AI向け: 未解決エスカレーション一覧。今回の発言で必ず
    resolve_premise_concern（却下）かrevise_goal（承認）のどちらかを呼んで解決させる
    （先送りループの防止、BL-082の申し送りとは異なり滞留させてはならない）。
    """
    open_escalations = get_open_goal_escalations(conn, run_id)
    if not open_escalations:
        return ""
    lines = [
        f"[{e['escalation_id']}] (raised by {e['raised_by_role']}) 懸念: {e['concern_summary']}\n"
        f"  該当する制約/前提: {e['implicated_constraint']}\n"
        f"  なぜ真の目的と矛盾するか: {e['why_conflicts']}\n"
        f"  提案されている再定義: {e['suggested_reframe']}"
        for e in open_escalations
    ]
    return (
        "【⚠️ BL-086: 未解決のエスカレーション（今回必ず判断してください）】\n"
        "以下は、Expert/あなた自身が「ゴールの文言上の制約が、本来満たすべき真の目的と矛盾している"
        "のではないか」と判断し、あなた（発注者）の判断を仰ぐために構造化された形でフラグを立てた"
        "懸念です。却下する場合はresolve_premise_concernツールを、承認しゴールを改定する場合は"
        "revise_goalツールを呼び出してください（判断を先送りせず、今回の発言内で必ず解決してください）。\n\n"
        + "\n\n".join(lines) + "\n"
    )


def _get_forced_escalated_issues_text(conn: sqlite3.Connection, run_id: str,
                                       current_task_id: str = "", round_count: int = 0) -> str:
    """[BL-136] User AI向け: issue_logのstatus='escalated'かつ未先送り（defer_to_task_id=''）行を、
    _get_open_escalations_text（BL-086）と同じトーンの強制解決文言で提示する。従来の
    _build_escalation_pin_textは「要対応」というラベルのみで具体的な行動を強制していなかった
    （BL-134の実例で0/7件しか解決されなかった原因の一つ）。write_issueのRESOLVE/DEFERどちらかを
    今回の発言で必ず呼ぶよう明示し、defer_to_task_id設定済みの行（既に対応予定が明示された
    ものはBL-082同様のスケジュール調整として許容する）はここでは対象外とする。
    [BL-167] ただしdefer_to_task_idの受け皿タスクが既に完了（RESOLVING_DELIVERABLE_STATUSES）して
    いるのにissueが未解決のままの場合、その受け皿は事実上失効しており、defer_to_task_idが
    設定済みという理由だけで対象外にし続けると永久にUser AIへ提示されない「永久迷子」issueに
    なる（BL-145の同型フィルタで実ログ確認済み）。受け皿タスクが完了済みの行は対象に含める。
    [BL-194] フィルタ述語を_is_issue_effectively_deferredへ委譲した（自前SQLフィルタを廃止）。
    自己先送り（defer_to_task_id==current_task_id）は「先送りされていない」扱いとなり本文の
    強制対象へ復帰する——従来は「受け皿あり」として永久に督促外だった6件（log/2026-08-08/1514）
    がここで初めて督促されるようになる。
    """
    # [BL-194] round_countを渡しACKNOWLEDGE中のissueも督促対象から除外する
    # （ACKの目的そのもの：「今回必ずRESOLVE/DEFERせよ」という督促を一時的に止める）。
    rows = _get_actionable_escalated_issues(conn, run_id, current_task_id, round_count=round_count)
    if not rows:
        return ""
    lines = [
        f"- topic={r['topic']}: {r['description']}（累積{r['occurrence_count']}回発生、"
        f"raised_by={r['raised_by']}）"
        for r in rows
    ]
    return (
        "【⚠️ BL-136: 未解決の重大issue（今回必ず対応してください）】\n"
        "以下は、繰り返し検出されたか、あなた自身が重大と判断して起票した未解決の懸念です。"
        "write_issue(action_type=\"RESOLVE\", topic=\"...\", resolution_note=\"...\")で解決するか、"
        "今このタスク・フェーズで対応すべきでないと判断した場合はwrite_issue(action_type=\"DEFER\", "
        "topic=\"...\", defer_to_task_id=\"<対応予定の実在task_id>\", defer_reason=\"...\")で対応予定を"
        "明示してください（判断を先送りせず、今回の発言内で必ずどちらかを呼んでください。理由なく"
        "放置することはできません）。\n\n"
        + "\n".join(lines) + "\n"
    )


def _get_escalation_status_text_for_expert(conn: sqlite3.Connection, run_id: str) -> str:
    """[BL-086] Expert向け: Open/Rejectedの状況のみ提示し、同じ懸念の重複再提起を防ぐ。
    Acceptedは提示しない（state["goal"]自体が既に改定後の文言になっており、call_expertは
    毎ターンstate["goal"]を再埋め込みするため二重に伝える必要がない）。
    """
    rows = conn.execute(
        "SELECT * FROM goal_escalations WHERE run_id=? AND status IN ('Open','Rejected') ORDER BY created_at ASC",
        (run_id,)
    ).fetchall()
    if not rows:
        return ""
    lines = []
    for r in rows:
        if r["status"] == "Open":
            lines.append(f"[{r['escalation_id']}] (判断待ち・未解決) 懸念: {r['concern_summary']} — 同じ懸念を重複して提起しないでください。")
        else:
            lines.append(f"[{r['escalation_id']}] (却下済み) 懸念: {r['concern_summary']} — 却下理由: {r['resolution_reason']}")
    return "【BL-086: これまでのエスカレーション状況】\n" + "\n".join(lines) + "\n"


# [BL-075/D-047] rollback_whiteboard（F-7.3）は撤廃した。「1つ前のバージョンは健全」という
# 前提が常には成り立たず、既に修正済みの問題を無警告で再導入する実害が確認されたため。
# 詳細は expert_node のコメント・decision_log.md D-047参照。


_TEXT_EDIT_SNIPPET_MAX_CHARS = 400  # [BL-151] 不一致時プレビューの上限（プロンプト肥大化を抑制）
_EDIT_SNIPPET_MIN_MATCH_SIZE = 20  # [BL-193] この文字数未満の最長一致は「無関係」とみなし先頭スニペットへフォールバック


def _nearest_content_snippet(content: str, old_text: str, max_chars: int = _TEXT_EDIT_SNIPPET_MAX_CHARS) -> str:
    """[BL-193] old_text不一致エラーで見せるスニペットを、常に文書先頭固定ではなく、
    old_textとcontentの間の最長共通部分（difflib.SequenceMatcher）周辺へ差し替える。

    BL-151は「実際の格納内容を見せれば同ターン内で自己修復できる」という設計だったが、
    スニペットが常にcontent[:max_chars]（文書先頭）固定だったため、数十KB規模のホワイト
    ボード（1514ログ、task_2_1）で編集対象が先頭から遠い節にある場合、スニペットが一度も
    その節の実際の中身を見せず、BL-151の自己修復が機能しないまま同じ不一致を繰り返す事故が
    発生した（同一old_textでの8連続失敗）。old_textとの最長一致箇所の周辺を見せることで、
    対象箇所がどこにあっても実際の現在の文言が見えるようにする。

    old_textがcontentとほぼ無関係（有意な共通部分がない）な場合は、BL-151の元の挙動
    （文書先頭のスニペット）にフォールバックする——完全に無関係なold_textに対しては
    「近傍」という概念自体が意味を持たないため。
    """
    matcher = difflib.SequenceMatcher(None, content, old_text, autojunk=False)
    match = matcher.find_longest_match(0, len(content), 0, len(old_text))
    if match.size < _EDIT_SNIPPET_MIN_MATCH_SIZE:
        snippet = content[:max_chars]
        return snippet + ("…（以下省略）" if len(content) > max_chars else "")
    half = max_chars // 2
    window_start = max(0, match.a - half)
    window_end = min(len(content), match.a + match.size + half)
    prefix = "…（中略）" if window_start > 0 else ""
    suffix = "…（以下省略）" if window_end < len(content) else ""
    return prefix + content[window_start:window_end] + suffix


def _apply_text_edits(
    current_content: str, edits: list[dict], content_label: str = "現在のホワイトボード内容"
) -> tuple[str | None, str | None]:
    """[R4/BL-081] Claude Code Editツールと同じ方式のテキスト置換。各editの
    {old_text, new_text, replace_all}をcurrent_contentに対しまず完全一致検索→置換する。

    ★修正（BL-081）: 完全一致が0件、または複数件でreplace_all未指定の場合、以前は即座に
    エラーを返していた。1319ドライラン（log/2026-07-24/1319）で、Markdownテーブル行頭の
    全角スペース・パイプ記号の有無だけでold_textが一致せず、ExpertがSUPERSEDEによる全文
    置換（BL-080で判明した別の欠陥）へ迂回する原因になっていたことが判明。BL-074/D-050で
    確立した正規化（改行・空白・太字記法・全角半角、加えて本修正でテーブル区切り|も対象に
    追加）による緩い一致（`_find_loose_match_spans`）へのフォールバックを追加し、Expert自身の
    主たる編集手段であるeditsがその場で成功する確率を高める。それでも一意に定まらない場合の
    みエラーを返す（Expertが同ターン内のツールループで修正・再試行できるよう、原因を具体的に
    伝える）。全edit成功時のみ(新content, None)を返す。

    ★修正（BL-151）: exact_count==0の場合、従来はold_textが不一致だった事実のみを返し、
    実際の格納内容を一切見せていなかった。08-03/1110ドライランで、revise_goalのold_textが
    プロンプト表示専用の装飾（生成側が挿入する絵文字プレフィックス等、_CURRENT_GOAL_TEXTには
    含まれない）を含んでいたケースで、モデルが同じ誤った引用を9回以上（最終的にはBL-056bの
    残り回数通知で打ち切られるまで）再試行し続け、一度も自己修復できなかった事例が確認された。
    エラーメッセージにcontent_labelの実際の内容の先頭スニペットを含めることで、表示用装飾と
    格納内容の乖離といった原因不明なケースでも、モデルが同ターン内で実際の文言を見て自己修復
    できるようにする（content_labelは呼び出し元ごとに「現在のゴール文」等へ差し替え可能）。

    ★修正（BL-193）: BL-151のスニペットは常に文書先頭固定だったため、編集対象が先頭から遠い
    大規模文書（数十KB規模のホワイトボード）では機能しなかった。`_nearest_content_snippet`で
    old_textとの最長一致箇所の周辺を見せる方式に変更した（詳細は同関数のdocstring参照）。
    """
    content = current_content
    for i, e in enumerate(edits):
        if not isinstance(e, dict):
            return None, (
                f"edits[{i}]: old_text/new_textを持つオブジェクト（辞書）である必要がありますが、"
                f"{type(e).__name__}型の値が渡されました。"
            )
        old_text = e.get("old_text", "")
        new_text = e.get("new_text", "")
        replace_all = bool(e.get("replace_all", False))
        if not old_text:
            return None, f"edits[{i}]: old_textが空です。"

        exact_count = content.count(old_text)
        if exact_count == 1 or (exact_count > 1 and replace_all):
            content = content.replace(old_text, new_text) if replace_all else content.replace(old_text, new_text, 1)
            continue

        loose_spans = _find_loose_match_spans(content, old_text)
        if len(loose_spans) == 1 or (len(loose_spans) > 1 and replace_all):
            if replace_all:
                for start, end in sorted(loose_spans, reverse=True):
                    content = content[:start] + new_text + content[end + 1:]
            else:
                start, end = loose_spans[0]
                content = content[:start] + new_text + content[end + 1:]
            continue

        if exact_count == 0:
            snippet = _nearest_content_snippet(content, old_text)
            print(f"  ⚠️ [edits失敗] edits[{i}]: old_textが{content_label}に見つかりませんでした（緩い一致{len(loose_spans)}件）。")
            return None, (
                f"edits[{i}]: old_textが{content_label}に見つかりませんでした"
                f"（正規化後の緩い一致も{len(loose_spans)}件でした）。一字一句正確な引用か確認してください。\n"
                # [BL-202] log/2026-08-09/2348で、同一ターン内に20回連続で同じ不一致を
                # 繰り返す事例が観測された。原因は、節全体＋Detector注釈を含む数千字規模の
                # old_textを、read_whiteboard_excerptの窓（…（中略）/…（以下省略）で
                # 切られている）の外まで記憶で補って再構成していたこと。「正確に引用しろ」と
                # 繰り返すだけでは同じ失敗を繰り返すため、次に取るべき具体的な行動を示す。
                f"【次に取るべき手順】(1) このold_textは{len(old_text)}文字あります。"
                f"節全体やDetector注釈ブロックを巻き込んでいる場合、実際に書き換える行だけに"
                f"絞ってください（短いほど成功します）。(2) read_whiteboard_excerptで対象箇所の"
                f"現在の文字列を取得し、その戻り値からコピーしてold_textを作ってください。"
                # [BL-202] ここで抜粋の省略マーカーを完全な形（先頭の三点リーダ付き）で書くと、
                # 「スニペット自体が切り詰められていないこと」を検証するBL-151のテストと
                # 文字列が衝突するため、マーカーの括弧部分のみを引用する。
                f"戻り値の先頭が「（中略）」、末尾が「（以下省略）」となっている場合、"
                f"その先は見えていないのでold_textに含めないでください。"
                f"(3) 複数箇所を一度に直そうとせず、1箇所ずつwrite_agreementを呼んでください。\n"
                f"【参考：{content_label}のうち、あなたのold_textに最も近い実際の内容】\n{snippet}"
            )
        print(f"  ⚠️ [edits失敗] edits[{i}]: old_textが{content_label}内で{exact_count}箇所に一致し一意に特定できません（緩い一致{len(loose_spans)}件）。")
        return None, (
            f"edits[{i}]: old_textが{exact_count}箇所に一致し、一意に特定できません"
            f"（正規化後の緩い一致も{len(loose_spans)}件）。replace_all=trueにするか、より長い一意な文脈を含めてください。"
        )
    return content, None


# [BL-076] Detectorのmajor指摘を、プロンプト注入（毎ターン再構成され消える一時情報）だけでなく
# ホワイトボード本文に永続的な注釈として書き込む（Word/PDFのコメント機能に相当）。差し戻された
# Expertは、指摘箇所が本文中に埋め込まれているため見落としようがなく、修正時にeditsで注釈ごと
# 書き換えることで自然に「解決済みコメントの削除」が行われる。案A（grep容易なタグ）と
# 案B（視認性の高いMarkdown引用）のハイブリッド形式を採用（ユーザー承認、D-048）。
_DETECTOR_COMMENT_TEMPLATE = (
    "\n> 🔴 **[Detector指摘 #{decision_id}]**: {comment}\n"
    "> （この注釈は指摘箇所を修正すると同時に削除してください）\n"
)


def _normalize_for_loose_match(s: str) -> tuple[str, list[int]]:
    """[BL-074/BL-081] 完全一致依存の脆さ（topic文字列ドリフト・target_excerpt・edits old_text
    に共通する根本課題）への対策。改行・空白の揺れ、Markdown太字記法（**）・テーブル区切り（|）、
    全角/半角の違いを吸収した正規化文字列を作り、正規化後の各文字が元の文字列の何文字目由来かを
    示すindex_mapを併せて返す（マッチ位置を元の文字列へ逆写像するため）。

    ★修正（BL-081）: 全角スペース（\\u3000）等の空白類似文字は、まずNFKC正規化してから
    空白判定する（判定前に正規化しないと、全角スペースが半角スペース1文字として結果に残り、
    「半角スペースは除去・全角スペースは残る」という非対称な不一致が生じるバグがあった）。
    """
    norm_chars: list[str] = []
    index_map: list[int] = []
    for i, ch in enumerate(s):
        norm_ch = unicodedata.normalize("NFKC", ch)
        if len(norm_ch) != 1:
            norm_ch = ch
        if norm_ch.isspace() or norm_ch in "*|":
            continue
        norm_chars.append(norm_ch)
        index_map.append(i)
    return "".join(norm_chars), index_map


def _find_loose_match_spans(content: str, old_text: str) -> list[tuple[int, int]]:
    """[BL-081] old_textを`_normalize_for_loose_match`で正規化した緩い一致で検索し、
    content上の元の文字位置における(開始, 終了・両端含む)のスパンを出現順・非重複で返す。
    old_textが空、または正規化後に空になる場合は空リストを返す。
    """
    norm_content, index_map = _normalize_for_loose_match(content)
    norm_old_text, _ = _normalize_for_loose_match(old_text)
    if not norm_old_text:
        return []
    spans: list[tuple[int, int]] = []
    search_start = 0
    while True:
        pos = norm_content.find(norm_old_text, search_start)
        if pos == -1:
            break
        end = pos + len(norm_old_text) - 1
        spans.append((index_map[pos], index_map[end]))
        search_start = end + 1
    return spans


def _annotate_whiteboard_with_detector_comment(
    conn: sqlite3.Connection, run_id: str, phase_id: str, task_id: str,
    target_excerpt: str, comment: str, decision_id: str
) -> tuple[bool, str]:
    """[BL-076/BL-074] target_excerptがホワイトボード内で一意に一致すればその直後に注釈を挿入する。
    まず完全一致を試み、0件または複数件で失敗した場合は正規化（改行・空白・太字記法・全角半角）
    した緩い一致にフォールバックする。それでも一意に特定できない場合は挿入を諦める。
    戻り値は(成功可否, 理由文字列) — 呼び出し元が失敗理由（0件一致/複数件一致等）を
    ログへ出せるようにし、以前はサイレントに失敗していた問題（BL-074調査で発覚）を解消する。
    """
    latest = get_latest_whiteboard(conn, run_id, phase_id, task_id)
    if not latest:
        return False, "ホワイトボードが存在しません"
    content = latest["content"]
    annotation = _DETECTOR_COMMENT_TEMPLATE.format(decision_id=decision_id, comment=comment)
    if not target_excerpt:
        return False, "target_excerptが空文字でした"

    exact_count = content.count(target_excerpt)
    if exact_count == 1:
        new_content = content.replace(target_excerpt, target_excerpt + annotation, 1)
    else:
        norm_content, index_map = _normalize_for_loose_match(content)
        norm_excerpt, _ = _normalize_for_loose_match(target_excerpt)
        loose_count = norm_content.count(norm_excerpt) if norm_excerpt else 0
        if not norm_excerpt or loose_count != 1:
            reason = (
                f"完全一致0件・正規化後緩い一致も{loose_count}件でした"
                if exact_count == 0 else
                f"完全一致が{exact_count}件（一意でない）で、正規化後緩い一致も{loose_count}件でした"
            )
            return False, reason
        norm_start = norm_content.find(norm_excerpt)
        norm_end = norm_start + len(norm_excerpt) - 1
        orig_end = index_map[norm_end]
        new_content = content[: orig_end + 1] + annotation + content[orig_end + 1 :]

    apply_whiteboard_patch(
        conn, run_id, phase_id, task_id, new_content,
        author_role="system_detector_annotation",
        edit_summary=f"[Detector注釈] {comment[:80]}"
    )
    return True, "完全一致で挿入" if exact_count == 1 else "正規化後の緩い一致で挿入"


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
                          unit: str, source_task_id: str, source_phase_id: str, confirmed_by: str,
                          reason: str = "", citations: list | None = None,
                          confidence: str = "provisional") -> None:
    """[F-3.9] 構造化ファクトストア: {topic, value, reason, citations, confidence} を保存する。
    BL-023 2.6節: owns_variablesで宣言された共有変数の確定値を保存する。
    下流タスクはこの値を再導出せず、確定済みの定数として参照する前提。
    ★R3a拡張: reason/citations/confidenceを追加。暂定(provisional)値も正当な理由として保存し、
    後の再検討トリガーとして機能させる（F-3.9、D-035）。
    ★修正（BL-041）: デフォルトを"confirmed"から"provisional"に変更。呼び出し元が明示的に
    confidenceを指定しない限り「木を見て森を見ず」の暫定値を確定扱いにしてしまう安全性の
    問題があったため（decision_extractor_nodeのowned_variable_values安全網パスが該当）。
    """
    citations_json = json.dumps(citations or [], ensure_ascii=False)
    _existing = conn.execute(
        "SELECT value, confidence FROM verified_facts WHERE run_id=? AND variable_name=?",
        (run_id, variable_name)
    ).fetchone()
    conn.execute(
        "INSERT INTO verified_facts (run_id, variable_name, value, unit, source_task_id, "
        "source_phase_id, confirmed_by, confirmed_at, reason, citations, confidence) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(run_id, variable_name) DO UPDATE SET value=excluded.value, "
        "unit=excluded.unit, source_task_id=excluded.source_task_id, "
        "source_phase_id=excluded.source_phase_id, confirmed_by=excluded.confirmed_by, "
        "confirmed_at=excluded.confirmed_at, reason=excluded.reason, "
        "citations=excluded.citations, confidence=excluded.confidence",
        (run_id, variable_name, str(value), unit, source_task_id, source_phase_id,
         confirmed_by, time.time(), reason, citations_json, confidence)
    )
    if _existing is not None:
        print(f"  🔄 [verified_facts] {variable_name}を上書きしました: {_existing['value']}({_existing['confidence']}) → {value}({confidence})、by={confirmed_by}")
    else:
        print(f"  🔒 [verified_facts] {variable_name}={value}{unit}（{confidence}）をby={confirmed_by}で保存しました。")


def get_verified_facts_from_db(conn: sqlite3.Connection, run_id: str,
                                variable_names: list[str] | None = None,
                                topic: str | None = None) -> list[dict]:
    """[F-3.9] 構造化ファクトストアから検索する。
    variable_namesで絞り込み、またはtopicキーワードでLIKE検索を行う。
    どちらも未指定の場合は全件返す。
    ★R3a拡張: トピック検索機能を追加。read_verified_factツールから呼び出される。
    """
    if topic:
        # [BL-053] variable_nameは英語スネークケース識別子（例: vehicle_count）だが、
        # topic_keywordはAIが渡す日本語の説明的キーワード（例: 予算・オペレーター）が
        # ほとんどのため、variable_nameだけを検索対象にすると構造的にほぼ一致しない。
        # 日本語理由文が入るreason列も検索対象に加える。
        like_pattern = f"%{topic}%"
        rows = conn.execute(
            "SELECT * FROM verified_facts WHERE run_id=? AND (variable_name LIKE ? OR reason LIKE ?)",
            (run_id, like_pattern, like_pattern)
        ).fetchall()
    elif variable_names:
        if not variable_names:
            return []
        placeholders = ",".join("?" for _ in variable_names)
        rows = conn.execute(
            f"SELECT * FROM verified_facts WHERE run_id=? AND variable_name IN ({placeholders})",
            (run_id, *variable_names)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM verified_facts WHERE run_id=?",
            (run_id,)
        ).fetchall()
    return [dict(r) for r in rows]


# [BL-187] topic_keywordの語順・言い回しが保存済みの文言と完全一致しないと
# get_verified_facts_from_db(topic=...)のLIKE検索がnot_foundになる問題への対応。
# 空白・日本語区切り記号でトークン分割し、まず既存のフレーズ全体一致を試みた後、
# ヒットしなければ「いずれかのトークンを含む」というOR検索へ緩和する。
_TOPIC_TOKEN_SPLIT_RE = re.compile(r"[\s・、,，/／|｜]+")


def _tokenize_topic_keyword(text: str) -> list[str]:
    """[BL-187] topic_keywordを検索用トークンへ分割する。1文字トークン（助詞の混入等で
    ノイズになりやすい）は除外する。"""
    if not text:
        return []
    return [t for t in _TOPIC_TOKEN_SPLIT_RE.split(text) if len(t) >= 2]


def get_verified_facts_from_db_any_token(conn: sqlite3.Connection, run_id: str,
                                          tokens: list[str]) -> list[dict]:
    """[BL-187] トークンのいずれかがvariable_name/reasonに含まれる行をOR検索する。
    get_verified_facts_from_db(topic=...)のフレーズ全体一致がnot_foundだった場合の
    第2段階として使う。"""
    if not tokens:
        return []
    conditions = []
    params: list[str] = [run_id]
    for t in tokens:
        conditions.append("(variable_name LIKE ? OR reason LIKE ?)")
        like_pattern = f"%{t}%"
        params.extend([like_pattern, like_pattern])
    rows = conn.execute(
        f"SELECT * FROM verified_facts WHERE run_id=? AND ({' OR '.join(conditions)})",
        params,
    ).fetchall()
    return [dict(r) for r in rows]


def suggest_similar_verified_facts(conn: sqlite3.Connection, run_id: str, query: str,
                                    limit: int = 3) -> list[str]:
    """[BL-187] トークンOR検索でも見つからない場合の最終フォールバック。このrunの
    variable_name（`_`分割語）とreason（トピック分割と同じトークナイザ）から語彙を作り、
    difflib.get_close_matches で近似一致するvariable_nameを提示する（新規依存なし、
    embeddingベースのRAGは今回導入しない——AGENTS.md依存追加最小化方針、規模もrunあたり
    数十件程度でオーバーエンジニアリングになるため）。
    """
    if not query:
        return []
    rows = conn.execute(
        "SELECT variable_name, reason FROM verified_facts WHERE run_id=?", (run_id,)
    ).fetchall()
    if not rows:
        return []
    word_to_vars: dict[str, set[str]] = {}
    for r in rows:
        vname = r["variable_name"]
        words = set(w for w in vname.split("_") if w) | set(_tokenize_topic_keyword(r["reason"] or ""))
        for w in words:
            word_to_vars.setdefault(w, set()).add(vname)
    query_tokens = _tokenize_topic_keyword(query) or [query]
    matched_vars: list[str] = []
    for qt in query_tokens:
        close = difflib.get_close_matches(qt, word_to_vars.keys(), n=limit, cutoff=0.5)
        for c in close:
            for v in sorted(word_to_vars[c]):
                if v not in matched_vars:
                    matched_vars.append(v)
    return matched_vars[:limit]


# ---------------------------------------------------------------------------
# [BL-204] 実世界事物レジストリ（entities / entity_attributes）
# 設計: docs/design/back_log/BL-204/BL204_basic_design.md
# ---------------------------------------------------------------------------

# [BL-204] confidenceはverified_factsと同じ2値のみ（設計書§2.1.1）。「工学的仮定」は
# citations[].type="expert_calculation"で表す——確定度（どれだけ動かないか）と出所
# （どこから来たか）は直交する2軸であり、confidenceへassumptionを足すと語彙が二重化する。
_ENTITY_CONFIDENCE_VALUES = ("confirmed", "provisional")


def _entity_id_from_name(canonical_name: str) -> str:
    """[BL-204] 正典名から安定した内部IDを作る。日本語名は英数字化できないため、
    「名前のハッシュ」ではなく正規化した名前そのものをIDに使う（DBのPRIMARY KEYとしては
    十分で、ログに出たときに人間が読めるという利点がある）。空白・記号のみ落とす。"""
    return re.sub(r"[\s　]+", "", canonical_name).strip()


def register_entity_in_db(conn: sqlite3.Connection, run_id: str, canonical_name: str,
                          entity_type: str, origin: str, created_by: str,
                          aliases: list[str] | None = None) -> str:
    """[BL-204] 事物を登録し entity_id を返す。既存なら上書きせずそのまま返す（冪等）。
    [CONSTRAINT] aliasesを設定してよいのはゴール文初期登録（origin='goal_text'）のみ。
    モデルからのalias入力を受け付けると、未登録名を拒否する同一性ガードがそこから
    抜けてしまうため（設計書§2.4、Clineレビュー指摘・軽4）。"""
    entity_id = _entity_id_from_name(canonical_name)
    if not entity_id:
        raise ValueError("canonical_nameが空です。")
    existing = conn.execute(
        "SELECT entity_id FROM entities WHERE run_id=? AND entity_id=?", (run_id, entity_id)
    ).fetchone()
    if existing:
        return entity_id
    conn.execute(
        "INSERT INTO entities (run_id, entity_id, canonical_name, entity_type, aliases, "
        "origin, created_by, created_at) VALUES (?,?,?,?,?,?,?,?)",
        (run_id, entity_id, canonical_name, entity_type,
         json.dumps(aliases or [], ensure_ascii=False), origin, created_by, time.time()),
    )
    conn.commit()
    return entity_id


def resolve_entity(conn: sqlite3.Connection, run_id: str, name_or_id: str) -> dict | None:
    """[BL-204] entity_id・正典名・aliasのいずれかで事物を引く。見つからなければNone。"""
    key = _entity_id_from_name(name_or_id)
    row = conn.execute(
        "SELECT * FROM entities WHERE run_id=? AND (entity_id=? OR canonical_name=?)",
        (run_id, key, name_or_id),
    ).fetchone()
    if row:
        return dict(row)
    # aliasは件数が少ない（runあたり数十件）ため素直に走査する
    for r in conn.execute("SELECT * FROM entities WHERE run_id=?", (run_id,)).fetchall():
        try:
            aliases = json.loads(r["aliases"] or "[]")
        except json.JSONDecodeError:
            aliases = []
        if name_or_id in aliases or key in [_entity_id_from_name(a) for a in aliases]:
            return dict(r)
    return None


def suggest_similar_entities(conn: sqlite3.Connection, run_id: str, query: str,
                             limit: int = 3) -> list[str]:
    """[BL-204] 未登録名が渡されたときに正典名の候補を提示する。
    `suggest_similar_verified_facts`（BL-187）と同じ`difflib.get_close_matches`方式を
    踏襲する（同関数はverified_factsテーブル固定のため直接は流用できない）。
    新規依存は追加しない。"""
    if not query:
        return []
    rows = conn.execute(
        "SELECT canonical_name FROM entities WHERE run_id=?", (run_id,)
    ).fetchall()
    names = [r["canonical_name"] for r in rows]
    if not names:
        return []
    close = difflib.get_close_matches(query, names, n=limit, cutoff=0.4)
    if close:
        return close
    # 近似一致が無い場合でも、登録済み一覧そのものを提示した方がモデルは復帰しやすい
    return names[:limit]


def upsert_entity_attribute(conn: sqlite3.Connection, run_id: str, entity_id: str,
                            attr_name: str, value, unit: str, confidence: str,
                            citations: list | None, reason: str,
                            source_task_id: str, source_phase_id: str,
                            confirmed_by: str) -> bool:
    """[BL-204] 属性を保存し、「新規属性名だったか」を返す（Trueなら新規作成）。
    返り値を使って、呼び出し元が既存属性名一覧をレスポンスへ添える
    （属性名の表記ゆれによる重複作成を抑止する。設計書§2.4、Clineレビュー指摘・軽3）。"""
    existing = conn.execute(
        "SELECT attr_name FROM entity_attributes WHERE run_id=? AND entity_id=? AND attr_name=?",
        (run_id, entity_id, attr_name),
    ).fetchone()
    conn.execute(
        "INSERT INTO entity_attributes (run_id, entity_id, attr_name, value, unit, confidence, "
        "citations, reason, source_task_id, source_phase_id, confirmed_by, confirmed_at) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?,?) "
        "ON CONFLICT(run_id, entity_id, attr_name) DO UPDATE SET value=excluded.value, "
        "unit=excluded.unit, confidence=excluded.confidence, citations=excluded.citations, "
        "reason=excluded.reason, source_task_id=excluded.source_task_id, "
        "source_phase_id=excluded.source_phase_id, confirmed_by=excluded.confirmed_by, "
        "confirmed_at=excluded.confirmed_at",
        (run_id, entity_id, attr_name, str(value), unit, confidence,
         json.dumps(citations or [], ensure_ascii=False), reason,
         source_task_id, source_phase_id, confirmed_by, time.time()),
    )
    conn.commit()
    return existing is None


def get_entity_with_attributes(conn: sqlite3.Connection, run_id: str, entity_id: str) -> dict | None:
    """[BL-204] 事物と**全属性**を返す。attr_name指定の絞り込みは提供しない——属性名が
    完全に自由である以上、読み取り側で名前を推測させると表記ゆれで空振りするため、
    そもそも推測が発生しない形にする（設計書§2.4）。1事物あたり数〜十数属性で
    全件返してもコストは無視できる。"""
    ent = conn.execute(
        "SELECT * FROM entities WHERE run_id=? AND entity_id=?", (run_id, entity_id)
    ).fetchone()
    if not ent:
        return None
    result = dict(ent)
    try:
        result["aliases"] = json.loads(result.get("aliases") or "[]")
    except json.JSONDecodeError:
        result["aliases"] = []
    attrs = conn.execute(
        "SELECT * FROM entity_attributes WHERE run_id=? AND entity_id=? ORDER BY attr_name",
        (run_id, entity_id),
    ).fetchall()
    result["attributes"] = []
    for a in attrs:
        d = dict(a)
        try:
            d["citations"] = json.loads(d.get("citations") or "[]")
        except json.JSONDecodeError:
            d["citations"] = []
        result["attributes"].append(d)
    return result


def list_entities_from_db(conn: sqlite3.Connection, run_id: str,
                          entity_type: str = "") -> list[dict]:
    """[BL-204] 事物の一覧（属性は含めない軽量版）。"""
    if entity_type:
        rows = conn.execute(
            "SELECT entity_id, canonical_name, entity_type, origin FROM entities "
            "WHERE run_id=? AND entity_type=? ORDER BY canonical_name", (run_id, entity_type)
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT entity_id, canonical_name, entity_type, origin FROM entities "
            "WHERE run_id=? ORDER BY canonical_name", (run_id,)
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
    internal_thought_process: str  # [R5 F-3.7]

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
    action_type: str
    status: str
    topic: str
    decision_what: str
    reason_why: str
    proposed_by: str
    resource_claims: dict[str, float]  # 追加: {"初期導入予算": 75000000}

    depends_on: list[str]   #"Decision"（合意・結論） / "Directive"（指示・タスク発行） / "Deliverable"（成果物本体）
    entry_type: str
    phase_id: str
    task_id: str   # BL-023/BL-024: どのタスクに紐づく合意・成果物・先送りか
    # statusに"Deferred"を追加（既存: Proposed/Approved/Approved_with_Conditions/Rejected/Implicitly_Accepted）
    # "Deferred"の場合、topicは先送りされた論点名、reason_whyに「どのタスクで扱うか」を含める
    citations: list[dict]  # [BL-188] 引用元: [{"type": "web"/"goal_text"/"prior_agreement"/
                            # "expert_calculation"/"user_input"/"document", "detail": "..."}]

class RiskRegister(TypedDict):
    """致命的リスクの専用台帳"""
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
    round_count: int  # [BL-005対応] turn_countはグラフ内部ループで凍結するため、
                       # generate_user_utterance_nodeへの再入場回数を数える別カウンタ。
                       # reflection_intervalの発火判定はこちらを使う。
    max_turns: int
    reflection_interval: int
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
    # [BL-051軽量版] Detectorがminor/major判定に至らずとも思考過程で気づいた懸念・観察を
    # 自由記述で蓄積するログ。constraint_issue_logと異なりnoneの回でも記録し、
    # 後続ノード（User AI/Expert）のプロンプトに毎回参考情報として提示する。
    detector_observations_log: list[dict]
    # [BL-096] issue_logにstatus='escalated'の行が1件でも存在する間True。エスカレーションが
    # 解消された（0件に戻った）瞬間を検知するために使う。
    escalation_active: bool
    # [BL-096] エスカレーション解消の直後、次のExpert/User AI呼び出しで一度だけ復帰通知を
    # 注入するためのフラグ。注入後はFalseに戻す。
    escalation_just_resolved_notice_pending: bool
    # [BL-125] _resolve_task_transitionが未解決・未先送りのsevere issueによりタスク遷移を
    # ブロックした場合、そのtopic一覧を次のUser AIターンへ一度だけ通知するためのフラグ。
    task_transition_blocked_issue_topics: list[str]
    # [BL-176] _resolve_task_transitionが離脱先task_idの未承認（Approved相当のDeliverable
    # 不在）によりタスク遷移をブロックした場合、そのtask_idを次のUser AIターンへ一度だけ
    # 通知するためのフラグ。空文字列は未設定を意味する。
    task_transition_blocked_unapproved_task_id: str
    # [BL-144] reflection_nodeがBL-096の機械的stagnant上書きを「escalated issueが1件でも
    # 存在すれば無条件」から「同じescalated issueがユーザーノードを3回通過しても未解決」へ
    # 絞るための滞留追跡。issue_log行id -> 初めてescalated状態で観測したround_countの辞書。
    escalated_issue_first_seen_round: dict[str, int]
    # [BL-145] plan_revision_reasonがissue駆動（Reflectorの正当性監査によるBL-144滞留issueの
    # タスク化）である場合のみ非空となる、対象issue_log行idのリスト。task_planner_nodeが
    # plan_revision_reasonの消費と同じタイミングで読み取り・クリアし、計画再構成成功後に
    # これらのissueをplanned状態へ遷移させる際に使う。plan_revision_reasonと常に対で
    # セット・クリアする不変条件を維持すること。
    plan_revision_issue_ids: list[str]
    # [BL-190] _reconcile_current_phase_after_replanが「計画再構成後、current_task_idが新計画
    # のどこにも存在しない」と判定した場合、次のUser AIターンへ一度だけ通知するためのフラグ。
    task_reassigned_after_replan_notice: str
    # [BL-191] Stage4駆動の過去タスクへの一時的フォーカス切替（decision_type="redirect_backward"）で、
    # 中断したフォワードタスクへ戻るための復帰ポインタスタック。要素: {"task_id", "phase_id"（監査用の
    # 参考情報のみ、復帰時は必ずtask_idから_find_phase_containing_taskで再解決する）, "reason",
    # "pushed_at_round", "focused_task_id", "baseline_agreement_id"}。v1は深さ1に固定。
    task_focus_stack: list[dict]
    # [BL-191] Stage4がdecision_type="joint_focus"で宣言した「現在の主タスクと合わせて今回考慮すべき
    # 過去タスク」。current_task_id/current_phaseは変更しない（BL-025のスコープガードレール意図を
    # 尊重し、Expert/Detectorへは追加のコンテキストとしてのみ注入する）。None＝未設定。
    # shape: {"companion_task_id", "companion_phase_id", "primary_task_id", "reason",
    #         "declared_at_round", "baseline_agreement_id"}
    task_focus_companion: dict | None
    # [BL-191] generate_user_utterance_node（Stage4のschedule_task_focusツール成功直後）が
    # 一度だけ書き込み、decision_extractor_nodeが同ターン内で消費・Noneへリセットする1ショット
    # ブリッジ。call_decision_extractorの自由文脈抽出（advances_to_task_id）とは独立した経路。
    pending_task_redirect: dict | None
    # [BL-191] redirect_backwardの累積発火回数（facilitation_count/plan_revision_countと同型の
    # run単位カウンタ、popしてもリセットしない）。schedule_task_focusツールが上限到達時に
    # 新規redirect_backwardを拒否する。
    task_focus_redirect_count: int
    # [BL-191] _apply_backward_redirectが発火した直後、次のExpert/User AIターンへ一度だけ
    # 「一時的に過去タスクへ切り替わった」ことを明示する通知。
    task_focus_redirect_notice: str
    # [BL-191] _maybe_resume_forward_focus/_force_resume_forward_focusが復帰を発火した直後、
    # 次のターンへ一度だけ「中断していたフォワードタスクへ復帰した」ことを明示する通知。
    task_focus_resume_notice: str
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
    # [R5 F-2.1] 直前Expert/User AI呼び出しのreasoning（思考過程）全文。Detectorの思考プロセス監査に使う。
    expert_last_reasoning: str
    user_last_reasoning: str
    # [BL-078] Orchestratorが専門家選定時に考えた「このタスクで特に注意すべき観点」。
    # 従来は選定理由（reason）としてログにのみ残り、Expertへは伝わっていなかった。
    expert_focus_guidance: str
    # [BL-038] LangGraphはTypedDictスキーマに宣言されていないキーをノード間で伝播しない
    # （未宣言キーへの書き込みは次ノードに渡る前に消える）。expert_wrote_agreement/
    # user_wrote_agreement/expert_last_whiteboard_editはR3b/R4で導入されて以来ここへの
    # 追加が漏れており、値が常にFalse/None扱いになる実運用バグの原因だった。
    expert_wrote_agreement: bool
    user_wrote_agreement: bool
    # [BL-184] web_search/web_fetchのrun単位の累積呼び出し回数。TOOL_DISPATCHのハンドラが
    # 直接インクリメントする（_LAST_PYTHON_CALLS等と異なり、state自体が単一の真実源）。
    web_search_call_count: int
    web_fetch_call_count: int
    # [BL-184] AppConfigのmax_web_search_calls/max_web_fetch_callsをrun開始時にコピーしたもの
    # （max_turns/reflection_intervalと同じ「Appconfig→LineageStateへ複製」パターン）。
    # TOOL_DISPATCHのweb_search/web_fetchハンドラは(args, state)の2引数しか受け取らないため、
    # 上限値をstate自身に持たせることで、config専用の新しい配線を増やさずに済ませる。
    max_web_search_calls: int
    max_web_fetch_calls: int
    # [BL-198] calc_road_route（OpenRouteService、無料枠API）のrun単位の累積呼び出し回数と
    # 上限。web_search/web_fetchと同型（GSI系3ツールはAPIキー不要かつ軽量なため専用の上限は
    # 設けず、MAX_TOOL_ITERによるツールループ全体の上限に委ねる）。
    road_route_call_count: int
    max_road_route_calls: int
    # [BL-199] read_goal_referenceのベースディレクトリ（AppConfigからrun開始時にコピー）。
    # 未設定（空文字列）の場合、read_goal_referenceはnot_configuredを返しweb_searchへ委ねる。
    goal_reference_dir: str
    # [BL-158] 今回のUser AIターンでwrite_issue(RESOLVE/DEFER)が成功したか。detector_nodeが
    # 未解決の重大issueを残したままの前進を機械的に差し戻すかどうかの判定に使う。
    user_wrote_issue_resolution: bool
    expert_last_whiteboard_edit: dict | None
    # [BL-061] reflectionが検出した具体的な停滞・ドリフト理由（call_reflectionのnote）。
    # facilitator_nodeがなぜ自分が呼ばれたかを把握できるよう、reflection_nodeが都度上書きする。
    last_reflection_note: str
    # [BL-087 Stage2] task_planner_node直後に1回だけ発火するtask_plan_reviewer_nodeの状態。
    # plan_review_doneはチェックポイント再開時に毎回レビューし直さないためのガード
    # （task_planner_nodeのturn_count==1ガードと同じ理由）。
    plan_review_done: bool
    plan_reviewer_retry_count: int
    plan_reviewer_feedback: str  # 差し戻し時の指摘事項。task_planner再生成プロンプトに注入される。
    # [BL-087 Stage3] task_planner分解より前に1回だけ行う「本質フェーズ」の冪等ガード。
    goal_essence_done: bool
    # [BL-131] Facilitator↔User対話中などに仮登録されたtask_id（BL-126のTask Planner
    # 正式採用/却下フローが実装されるまでの許可リスト）。write_agreementのtask_id実在
    # チェックで、task_plannerの正式計画(phases)に無くてもここに含まれていれば許可する。
    pending_task_ids: list[str]
    # [BL-130] Expertがask_user_questionを呼んだ今ターンのフラグ。expert_nodeがセットし、
    # generate_user_utterance_node（User AIが質問に回答した直後）で消費・リセットする。
    # 有効な間は expert_detector/expert_decision_extractor の厳格な監査・抽出をスキップする。
    expert_consultation_mode: bool
    expert_pending_question: str
    # [BL-135] ask_user_questionの必須パラメータblocking_reason（Expertがなぜブロックされて
    # いるか）。expert_pending_questionと寿命・消費/リセットのタイミングは同じ。
    expert_blocking_reason: str
    # [BL-126 Stage B] revise_goalが今ターン成功した直後にTrueとなる、次のuser_detectorに
    # review_mode="goal_change"を使わせるための単発フラグ。generate_user_utterance_nodeが
    # セットし、detector_nodeが消費・リセットする（expert_consultation_modeと同型のライフサイクル）。
    goal_revision_pending_review: bool
    # [BL-162] goal_revision_pending_review=Trueの間だけ有効な、改定前のゴール文。
    # review_mode="goal_change"監査の判定基準1「旧文が置換ではなく追記として保持されているか」を
    # 評価するために必要だが、従来はgenerate_user_utterance_nodeが_LAST_GOAL_REVISIONから
    # new_goal_textだけをstate["goal"]へ反映しold_goal_textを一切保存していなかったため、
    # Detectorが読める手段が存在しなかった（read_verified_fact/read_deliverable_fileを
    # 計5回試して全てnot_foundになる実害をログで確認）。
    goal_revision_old_text: str
    # [BL-126 Stage C] ラン途中でのtask_planner再構成トリガー。task_planner_nodeのガード判定
    # 直後（消費「後」ではなく先頭）でクリアする（plan_reviewer_feedbackとは異なる箇所——
    # チェックポイント再開時の多重発火を避けるため、design.md §6/v2修正）。
    plan_revision_reason: str
    # [BL-126 Stage C] ラン途中再構成の発生回数。plan_reviewer_retry_countと同型の上限（5回、
    # ユーザーが手動で2から変更）で、
    # 超えた場合はtask_plan_reviewerの差し戻し指摘が残っていても計画を承認して進行する。
    plan_revision_count: int
    # [BL-126 Stage C] ラン途中再構成で「削除」ではなく「supersede」されたタスクの記録
    # （task_id/phase_id/reason/superseded_at_round）。監査証跡はwrite_agreement
    # （entry_type="Directive", action_type="SUPERSEDE"）としても別途記録される。
    phases_superseded: list[dict]
    # [BL-126 Stage D] Facilitator↔User AIの本質対話（Essence Dialogue）モード制御フィールド群。
    essence_dialogue_active: bool  # 対話モード中フラグ。Trueの間、generate_user_utteranceの
    # 直後はuser_detectorではなくfacilitatorへ戻る（既存の通常監査をスキップする）。
    essence_dialogue_round: int  # 対話の往復回数（facilitation_countとは別カウンタ）。
    essence_dialogue_max_rounds: int  # 対話の上限（5、design.md §11確定回答）。
    essence_dialogue_topic: str  # Facilitatorが提起したEssenceProposalのtopic（収束判定に使う）。
    # [BL-126 Stage D] 直前のquery_AI呼び出しでwrite_agreement(entry_type="EssenceProposal")が
    # 成功していれば、その内容（get_last_essence_proposal）をノード関数がここへ書き写す
    # （ツールハンドラはstateへ直接触れられないため、他のブリッジ変数と同じパターン）。
    last_essence_proposal: dict | None

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
    # [BL-184] web_search/web_fetchのrun単位の呼び出し回数上限（ユーザー確定値: 各30回/run）。
    max_web_search_calls: int
    max_web_fetch_calls: int
    # [BL-198] calc_road_route（OpenRouteService無料枠）のrun単位の呼び出し回数上限。
    max_road_route_calls: int
    # [BL-199] read_goal_referenceが読む、開発者事前収集の参照データディレクトリ
    # （例: "docs/refs/chino_city"）。未指定なら空文字列扱いでツールは無効化される。
    goal_reference_dir: str


  
    

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
        # [BL-064] reason_missingは書き込まれるのみで表示に一切反映されていなかったため追加。
        missing_flag = " ⚠️理由未記載" if d.get("reason_missing") else ""
        lines.append(f"- [{d['who']}] {d['what']}（理由: {why_short}）{missing_flag}")
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

    # [R5 F-8.3] Freeze済み（is_frozen=1）の項目を先頭に配置する。chat_history_window等の
    # トリミングでFrozen項目が窓の外へ押し出されないよう、常に確実にコンテキスト上位へ含める。
    decisions_and_deliverables.sort(key=lambda a: (not a.get("is_frozen"), a.get("timestamp") or 0))

    lines = []
    for a in decisions_and_deliverables:
        status = a.get("status", "Proposed")
        entry_type = a.get("entry_type", "Decision")

        # LLMが勝手に topic の先頭に "[合意]" や "[決定]" を付けて抽出するのを防ぐ
        raw_topic = a.get('topic', 'Unknown Topic')
        clean_topic = re.sub(r'^\[.*?\]\s*', '', raw_topic)

        # 1. アイコンの判定（成果物は専用アイコンを使用。Freeze済みは🔒を最優先）
        # [BL-166] 以前はDeliverableの場合`"📄" if status == "Proposed" else "✅"`という二値判定で、
        # Approved/Approved_with_Conditions/Implicitly_Acceptedだけでなく"Rejected"も無条件で✅に
        # なっていた（Decision/Directive分岐にはRejectedをelse節の⚠️へ落とす保護があるのに、
        # Deliverable分岐だけこの保護が欠けていた）。実ログでRejectされたDeliverableが「✅ [成果物]」
        # のまま表示され続け、User AIが誤って「承認済み」と誤認する実害を確認したため、
        # 成功系ステータス（RESOLVING_DELIVERABLE_STATUSES）とそれ以外を明示的に分ける。
        if a.get("is_frozen"):
            icon = "🔒"
        elif entry_type == "Deliverable":
            if status == "Proposed":
                icon = "📄"
            elif status in RESOLVING_DELIVERABLE_STATUSES:
                icon = "✅"
            else:
                icon = "⚠️"
        elif status == "Approved":
            icon = "✅"
        elif status == "Proposed":
            icon = "🤔"
        else:
            icon = "⚠️"

        # 2. ラベル（テキスト）の動的判定
        if entry_type == "Deliverable":
            # [BL-166] Decision/Directiveにはあった却下時の専用ラベルがDeliverableには
            # 存在せず、Rejectされていても常に"[成果物]"と表示されていた。
            type_label = "[却下成果物]" if status == "Rejected" else "[成果物]"
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

        # [R3b対応] LLMがdepends_onにどのagreements.idを指定すればよいか本文中から読み取れるようidを追記
        # [BL-050] reason_whyも表示する。UPDATE/SUPERSEDE時はここに「前の値から何故変わったか」が
        # 書かれる想定（WRITE_AGREEMENT_TOOLのreason_why説明文で要求）。
        agreement_id = a.get('id', '?')
        reason_preview = (a.get('reason_why') or '')[:100]
        reason_suffix = f"（理由: {reason_preview}）" if reason_preview else ""
        # [BL-064] evidenceは書き込まれるのみで表示に一切反映されていなかったため追加。
        evidence_preview = (a.get('evidence') or '')[:100]
        evidence_suffix = f"（根拠: {evidence_preview}）" if evidence_preview else ""
        # [BL-188] citationsもevidenceと同じく表示へ反映する（書き込まれるのみで表示に一切
        # 反映されない状態は、evidence自身がBL-064で一度経験済みの同型の失敗パターン）。
        citations_raw = a.get('citations')
        if isinstance(citations_raw, str):
            try:
                citations_list = json.loads(citations_raw) if citations_raw else []
            except json.JSONDecodeError:
                citations_list = []
        else:
            citations_list = citations_raw or []
        if isinstance(citations_list, list) and citations_list:
            citation_strs = []
            for c in citations_list[:3]:
                if isinstance(c, dict):
                    citation_strs.append(f"{c.get('type', '?')}:{str(c.get('detail', ''))[:60]}")
                else:
                    citation_strs.append(str(c)[:60])
            citations_suffix = f"（出典: {'; '.join(citation_strs)}）"
        else:
            citations_suffix = ""
        lines.append(f"[{agreement_id}] {icon}{type_label} {clean_topic}: {content_preview}{reason_suffix}{evidence_suffix}{citations_suffix}")

        # [BL-050] 直近1件のSuperseded版（同一topic・同一entry_type）を差分として1行追記。
        # 全履歴を出すとトークンコストが膨らむため、直前版のみに絞る。
        prior = _find_prior_superseded(agreements, raw_topic, entry_type)
        if prior is not None:
            old_what = (prior.get("decision_what") or "")[:80]
            old_why = (prior.get("reason_why") or "")[:80]
            lines.append(f"　└ (前版 Superseded): {old_what} — 当時の理由: {old_why}")

    return "\n".join(lines)


def _find_prior_superseded(agreements: list[Agreement], topic: str, entry_type: str) -> Agreement | None:
    """[BL-050] 同一topic・entry_typeを持つSuperseded行のうち、timestampが最も新しい1件を返す。
    現行（非Superseded）行はstatusフィルタだけで既に除外されるため、idによる除外は行わない
    （AG-IDはミリ秒タイムスタンプ由来で、高速連続書き込み時に現行行と旧版行のIDが衝突しうるため、
    idベースの除外は誤って正当な旧版を取りこぼす）。"""
    candidates = [
        a for a in agreements
        if a.get("topic") == topic
        and a.get("entry_type", "Decision") == entry_type
        and a.get("status") == "Superseded"
    ]
    if not candidates:
        return None
    return max(candidates, key=lambda a: a.get("timestamp") or 0)


def _aggregate_global_constraints(agreements: list[Agreement]) -> list["GlobalConstraint"]:
    """[BL-041] resource_claims（{name: {phase_id, value, total_cap}}構造）を持つagreements
    （Superseded除く）をname単位で集約し、GlobalConstraint配列を構築する。
    旧形式（平坦な{name: 数値}）や壊れたJSONは静かにスキップする（混在期間の後方互換）。
    """
    by_name: dict[str, dict] = {}
    for a in agreements:
        if a.get("status") == "Superseded":
            continue
        try:
            claims = json.loads(a.get("resource_claims") or "{}")
        except (json.JSONDecodeError, TypeError):
            print(f"  ⚠️ [_aggregate_global_constraints] agreement id={a.get('id')}のresource_claimsがJSONとして不正なため、制約集計からスキップしました。")
            continue
        if not isinstance(claims, dict):
            print(f"  ⚠️ [_aggregate_global_constraints] agreement id={a.get('id')}のresource_claimsが旧形式（非dict）のため、制約集計からスキップしました。")
            continue
        for name, claim in claims.items():
            if not isinstance(claim, dict):
                continue
            entry = by_name.setdefault(name, {"name": name, "unit": "", "claims": {}, "total_cap": None})
            phase_key = claim.get("phase_id") or a.get("phase_id") or "unknown"
            if "value" in claim:
                entry["claims"][phase_key] = claim["value"]
            if claim.get("total_cap") is not None:
                entry["total_cap"] = claim["total_cap"]
    return [e for e in by_name.values() if e["total_cap"] is not None]


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
    if current_task_id and tasks:
        print(f"  ⚠️ [_get_current_task] current_task_id='{current_task_id}'がcurrent_phaseのタスク一覧に見つかりません。先頭タスク'{tasks[0].get('task_id')}'にフォールバックします。")
    return tasks[0] if tasks else {}


def _reconcile_current_phase_after_replan(state: LineageState, phases: list[dict]) -> None:
    """[BL-190] task_planner_nodeが新しいphases配列を確定させた直後に呼ぶ。
    current_task_id（BL-024の唯一の書き手は_resolve_task_transitionだが、値そのものは
    ここでは変更せず参照のみ）が新phases内のどこに属するかを再探索し、current_phaseを
    そのtask_idを含むphaseへ合わせる。

    [CONSTRAINT] 従来はcurrent_phaseを無条件にphases[0]へリセットしていたため、ラン途中の
    計画再構成でフェーズの並び順・phase_idが変わると（BL-186の加算のみのケースでは無害だが、
    task_plan_reviewer指摘によるフェーズ全体の再編では実際に発生した）、current_task_idが
    指すtaskが新phases[0]の中に存在せず、_get_current_taskが毎ターンフォールバック警告を出し、
    BL-146ガードが正当なwrite_agreement(UPDATE)まで拒否する事故があった
    （log/2026-08-07/2355で実見、SUPERSEDEへの切り替えで実害は回避されたが根本原因は未解消）。
    """
    current_task_id = state.get("current_task_id", "")
    if not current_task_id:
        # 初回計画（is_initial）、またはまだ一度もタスクに着手していない場合。
        # 従来通りphases[0]を採用する。
        state["current_phase"] = phases[0] if phases else {}
        return

    for phase in phases:
        for t in phase.get("tasks", []):
            if t.get("task_id") == current_task_id:
                if phase.get("phase_id") != state.get("current_phase", {}).get("phase_id"):
                    print(
                        f"  📍 [BL-190] current_task_id='{current_task_id}'の追跡のため、"
                        f"current_phaseを新phase_id='{phase.get('phase_id')}'へ更新しました"
                        f"（計画再構成によるフェーズ位置変更に追随）。"
                    )
                state["current_phase"] = phase
                return

    # current_task_idが新phasesのどこにも存在しない（真の削除・統合パターン）。
    # [BL-191バグ②対策] task_focus_stackが非空（＝現在Stage4のredirect_backwardで一時的に
    # フォーカス中の過去タスクが、今回の計画再構成で消失した）場合、単純にcurrent_task_idを
    # クリアするとtask_focus_stackに積まれた元のフォワードタスクへ二度と復帰できなくなる
    # （BL-167と同型の永久迷子）。この場合はforce_resumeと同じ経路で強制的に元のフォワード
    # タスクへ復帰させる。
    if state.get("task_focus_stack"):
        print(
            f"  ⚠️ [BL-190/191] current_task_id='{current_task_id}'（redirect_backwardで"
            "一時フォーカス中）は計画再構成により消失しました。中断中のフォワードタスクへ"
            "強制的に復帰します。"
        )
        _force_resume_forward_focus(state)
        # [CONSTRAINT] _force_resume_forward_focusの復帰先（スタック上のフォワードタスク）
        # 自体も新計画から消えている場合、resume_phaseが見つからずスタックのみクリアされ
        # current_task_id/current_phaseは古いまま変更されない（フォーカス中タスク・復帰先の
        # 両方が消えた二重消失パターン）。この場合は下の「真の削除・統合」処理へフォール
        # スルーさせ、current_task_idを確実にクリアする（無効なtask_idを指したまま
        # 残り続ける事故を防ぐ）。
        if not _find_phase_containing_task(phases, state.get("current_task_id", "")):
            pass  # フォールスルー
        else:
            return

    # phases[0]へフォールバックし、current_task_idもクリアして_get_current_taskの
    # フォールバック警告が毎ターン出続ける状態を防ぐ。次のUser AIターンへ一度だけ
    # 通知し、新計画のどのタスクを引き継ぐべきかLLM自身に確認させる。
    print(
        f"  ⚠️ [BL-190] current_task_id='{current_task_id}'は計画再構成後の新しい計画に"
        f"存在しません（supersede済み）。current_phaseを先頭フェーズへ戻し、"
        f"current_task_idをクリアします。"
    )
    state["current_phase"] = phases[0] if phases else {}
    state["current_task_id"] = ""
    state["task_reassigned_after_replan_notice"] = (
        f"[BL-190] 直前まで進行していたタスク'{current_task_id}'は、直前の計画再構成により"
        "廃止・統合されました。新しい計画（phases）を確認し、対応する新タスクへ改めて着手して"
        "ください。"
    )


def _build_detector_observations_block(state: LineageState, limit: int = 3) -> str:
    """[BL-051軽量版] Detectorがconstraint_issueの判定に至らずとも書き残した気づき・懸念
    （detector_observations_log）を、User AI/Expertのプロンプトへ参考情報として毎ターン
    提示するためのヘルパー。差し戻し時のみ表示されるconstraint_issue_logと異なり、
    noneの回の気づきも失われず後続ノードに引き継がれる。
    """
    log = state.get("detector_observations_log", [])
    if not log:
        return ""
    recent = log[-limit:]
    entries_text = "\n".join(f"- (turn{e['turn']} / {e['target_role']}) {e['observations']}" for e in recent)
    return (
        f"\n【Detectorが気づいた点（参考情報、判定を左右するものではありません）】\n{entries_text}\n"
        f"重大な指摘ではないため差し戻しにはなっていませんが、内容として無視してよいとは限りません。"
        f"必要に応じて考慮してください。\n"
    )


def _build_task_scope_context(state: LineageState, conn: sqlite3.Connection) -> dict:
    """[CONSTRAINT] BL-023/BL-025: 現在タスクのスコープ情報（acceptance_criteria・依存タスクの確定値・
    未充足項目）を`generate_user_utterance`と`call_expert`の両方で共有するためのヘルパー。
    """
    current_task = _get_current_task(state)
    current_task_json = json.dumps(current_task, ensure_ascii=False, indent=2) if current_task else "(タスク未確定)"

    depends_on_task_ids = current_task.get("depends_on", [])
    dependency_variable_names: list[str] = []
    # [BL-035修正] 全フェーズを走査して依存タスクのowns_variablesを解決する。
    # 従来はstate["current_phase"]["tasks"]のみを走査しており、フェーズ横断の
    # depends_on参照（例: task_6_3→task_2_1）が構造的に解決不能だった。
    for phase in state.get("phases", []):
        for t in phase.get("tasks", []):
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

    # [R4] 現在タスクの最新ホワイトボード版（Deliverableの差分パッチ化対象）。
    # 存在すれば、Expertは全文を書き直さずwrite_agreementのeditsで変更箇所のみ送れることを示す。
    current_phase_id = state.get("current_phase", {}).get("phase_id", "")
    current_task_id = current_task.get("task_id", "")
    whiteboard = get_latest_whiteboard(conn, state["run_id"], current_phase_id, current_task_id) if current_task_id else None
    if whiteboard:
        whiteboard_text = (
            f"【現在のホワイトボード Ver.{whiteboard['version']}（このタスクの成果物の最新版）】\n"
            f"{whiteboard['content']}\n\n"
            "【R4: 編集方針】上記を修正する場合、全文を書き直す必要はありません。write_agreementツールを"
            "action_type='UPDATE', entry_type='Deliverable'で呼び、editsパラメータに"
            "変更箇所のold_text/new_textのみを指定してください（old_textは上記本文と一字一句一致させること）。"
            "大幅な構成変更の場合のみ、decision_whatに全文を渡してください。\n"
            "【BL-193: old_textは最小限に】old_textには変更したい箇所そのものだけを含め、"
            "無関係な前後（特にDetector指摘の注釈「> 🔴 [Detector指摘 #...]」ブロック全体など）を"
            "巻き込んで1つの巨大なold_textにしないでください。注釈の削除が必要な場合は、"
            "本文修正とは別のeditsの要素として、注釈のブロックだけを対象にした短いold_textで"
            "個別に削除してください。1つのeditsが大きいほど、一字一句の不一致で全体が失敗する"
            "リスクが上がります。\n"
            "【BL-202: 編集は「読む→1箇所だけ直す」を繰り返す（厳守）】このプロンプトに表示された"
            "本文は生成時点のスナップショットであり、Detector注釈の挿入等で既に変わっている"
            "可能性があります。したがって、次の手順を必ず守ってください。\n"
            "  (1) old_textを組み立てる前に、**必ず**read_whiteboard_excerptツールで対象箇所の"
            "「現在の」実際の文字列を確認する（記憶や上記スナップショットからold_textを"
            "再構成しない）。\n"
            "  (2) 1回のwrite_agreementで文書中の何箇所も一度に書き換えようとせず、"
            "**1箇所ずつ**修正する。修正箇所が複数ある場合は、(1)→(2)を修正箇所の数だけ"
            "繰り返してください（ツール呼び出しの往復は十分に確保されています）。一度に"
            "詰め込むほど、1つの不一致でedits全体が巻き戻り、結局やり直しになります。\n"
            "  (3) old_textは、その箇所を一意に特定できる**最短の文字列**にする。"
            "見出しから節の末尾までを丸ごと引用するのではなく、実際に書き換える行だけを"
            "引用してください。read_whiteboard_excerptの結果に「…（中略）」「…（以下省略）」が"
            "含まれている場合、その部分は**あなたに見えていない**ので、絶対にold_textへ"
            "含めないでください（見えていない範囲を記憶で補うことが不一致の最大の原因です）。\n"
            "【BL-202: 同じ記述が複数箇所にある場合】Detectorやユーザーから「複数のセクションで"
            "矛盾している」と指摘された場合（例：4B-1・5A-1・6Aで同じ断定が繰り返されている）、"
            "セクション見出しではなく**問題の文言そのもの**（例：「通年運行可能」）を"
            "keywordにしてread_whiteboard_excerptを呼び、一致件数を確認してください。"
            "複数箇所に存在することが分かったら、1箇所だけ直して終わりにせず、"
            "全ての箇所を（1箇所ずつ、または同一文言ならreplace_all=trueで）修正してください。"
            "1箇所だけ直すと、残った箇所が次のラウンドで再び矛盾として差し戻されます。"
        )
    else:
        whiteboard_text = "(このタスクの成果物はまだホワイトボードに存在しません。初版はwrite_agreementのdecision_whatに全文を渡してください)"

    # [BL-082] 他タスクから本タスクへ申し送られた先送り事項（plan_drafts）。無ければ空文字。
    deferred_notes_text = _get_deferred_notes_text(conn, state["run_id"], current_phase_id, current_task_id)

    return {
        "current_task": current_task,
        "current_task_json": current_task_json,
        "verified_facts_json": verified_facts_json,
        "remaining_criteria_text": remaining_criteria_text,
        "whiteboard_text": whiteboard_text,
        "deferred_notes_text": deferred_notes_text,
    }


# ============================================================================
# [BL-115] 共有プロンプト定型文
# 複数のプロンプト構築関数（call_task_planner/call_expert/call_detector/
# call_resource_arbiter/call_integrator/call_reviewer/generate_user_utterance/
# call_goal_essence_analyst/call_task_plan_reviewer）に、think任意呼び出し説明・
# BL-094同期説明・検証回数抑制注意書きがほぼ同一の文面で重複して埋め込まれていた
# （2026-07-28調査、BL-115）。ここに共通部分のみを集約する。
#
# [CONSTRAINT] tests/test_bl093_think_tool_scratchpad.pyのtest_node_prompt_names_
# its_own_tools_alongside_thinkは、9関数それぞれのinspect.getsource(func)自体に
# 「あなたが使えるツールは...」という文言と各ツール名のリテラル文字列が含まれることを
# 要求している。そのためツール一覧文はヘルパーへ集約せず、各呼び出し元にインラインの
# ままにし、末尾の定型文（_THINK_TRAILER_SENTENCE）のみをここで共有化する。
# 同様に、test_call_detector/call_task_planner/call_task_plan_reviewer_wires_think_
# tool_and_instructionは"BL-093" in inspect.getsource(func)を要求するため、
# _BL093_THINK_VALUE_PARAGRAPHを使う箇所には呼び出し元に`# [BL-093]`等のリテラル
# コメントを併記すること。
# ============================================================================

_BL093_THINK_VALUE_PARAGRAPH = (
    "自然に考えた理由づけの生文章は、thinkを使わなければ次のiterationには引き継がれません\n"
    "（tool_callsの記録だけが残ります）。thinkを呼ぶと、その理由づけ（action/decided/why、\n"
    "却下案があればrejected/rejected_why）は次回以降のtool結果として全履歴ごと返され、雪だるま式に\n"
    "引き継がれます。まずtodoに確認すべき論点をリストアップしてください。他のツール呼び出しと\n"
    "同一の応答内でまとめて呼んでも、単独で呼んでも構いません。"
)

def _verification_throttle_warning(example: str = "") -> str:
    """【SLM要約】
    「同じ検証・計算を繰り返さない」注意書き（call_integrator/call_reviewer/
    call_goal_essence_analystでbyte-identical、call_resource_arbiterはタスク固有の
    例示句を挿入するのみ）を共通化したテンプレート。
    """
    example_clause = f"（例:{example}）" if example else ""
    return (
        f"【同じ検証・計算を繰り返さない（重要）】ツール呼び出しの回数には上限があります。同じ論点\n"
        f"{example_clause}をpython_replで繰り返し再確認しないでください。各検証項目は2回程度の\n"
        "計算・確認で十分です。新しい数値や新しい論点が無いまま「念のため最終確認」を重ねると、\n"
        "JSON出力そのものを書く余地が無くなり、上限到達時に強制的に打ち切られたテキスト応答として\n"
        "JSONを一度に出力せざるを得なくなり、出力が途中で切れて構文エラーになるリスクがあります。\n"
        "必要な検証が終わったら、直ちに最終的なJSONオブジェクトの記述に移ってください。"
    )

def _build_retry_situation_label(state: LineageState, retry_count: int, max_retries: int = 3) -> str:
    """[BL-143] Detectorのmajor差し戻しプロンプトには、従来は指摘文（constraint_issue_logの
    直近1件）だけが載っており、「これが何回目の差し戻しか」「前回と同じ指摘が繰り返されて
    いるのか」がPython側で計算済みなのにプロンプトへは渡っていなかった（user_retry_count/
    expert_retry_countはルーティング判定にのみ使われ、LLMからは見えなかった）。BL-142で見た
    「Userが同じ承認を言い回しを変えて繰り返す」空回りは、この現在地情報の欠如が一因と考え、
    差し戻しプロンプトの冒頭に機械的な現在地サマリーを追加する。

    retry_countは呼び出し時点で既に加算済みの値（expert_node/generate_user_utterance_nodeが
    call_expert/generate_user_utterance呼び出し前にインクリメントする）であるため、そのまま
    「今回が何回目の差し戻しか」として使える。
    """
    log = state.get("constraint_issue_log", [])
    remaining = max(0, max_retries - retry_count)
    lines = [
        f"【現在地】これはこの論点に対する{retry_count}回目の差し戻しです"
        f"（あと{remaining}回、同じ論点で差し戻されると強制的にレビュー（reflection）へ回されます）。"
    ]
    # retry_count>=2のときのみ、直近2件が同一の差し戻し連鎖に属することが保証される
    # （constraint_issue_logはminor/major判定時のみ追記され、この連鎖の外側の判定が
    # 割り込むことはない）。retry_count==1では比較対象がまだ連鎖内に無いためスキップする。
    if retry_count >= 2 and len(log) >= 2:
        current_comment = log[-1].get("comment", "")
        prev_comment = log[-2].get("comment", "")
        similarity = difflib.SequenceMatcher(None, current_comment, prev_comment).ratio()
        if similarity >= 0.6:
            lines.append(
                "⚠️ 前回の指摘とほぼ同じ内容が繰り返されています。前回の対応では実質的に解消できて"
                "いません。同じ対応を言い回しを変えて繰り返すのではなく、指摘されている根本原因"
                "（数値・前提そのもの）に着手してください。"
            )
    return "\n".join(lines) + "\n"


_THINK_TRAILER_SENTENCE = (
    "think以外のいずれかを呼ぶ場合、必要に応じて同じ応答内でthink（summary付き）を呼んで"
    "検討過程を書き残しても構いません。"
)

# [BL-192] User AIがExpertへ次タスクを指示する際の指示文の質を強化する共通ブロック。
# BL-188が確立した「プロンプト誘導のみ（機械的な強制ゲートは追加しない）」という標準方針を
# 踏襲する（BL-042: Detectorの硬直判定によるトークン浪費事故の再発防止という設計判断）。
# Stage4（generate_user_utteranceの4段階パイプライン内、次タスク指示ステージ）と、
# 差し戻し・本質対話等でStage4をスキップする非Stage4パスの両方から参照する（文言の
# 二重管理を避けるため、モジュール定数として1箇所に定義する）。
_BL192_DIRECTIVE_QUALITY_BLOCK = (
    "\n[BL-192] 次タスクの指示を書く際は、以下2点を徹底してください：\n"
    "①【根拠不明な数値・前提のweb_search義務化】そのタスクが依存する確定値"
    "（verified_facts/agreementsのcitations）に`type=\"web\"`の裏付けがなく"
    "`expert_calculation`/`goal_text`のみの場合、指示文の中で「このタスクの前提となる"
    "◯◯の数値はまだ一次情報での裏付けがないため、web_searchで検証してから進めること」と"
    "具体的に名指しで指示してください。Expertが『もっともらしい』値を無検証のまま踏襲する"
    "ことを許容しないでください。\n"
    "②【期待される思考プロセスの明示】成果物の完成条件（acceptance_criteria）を並べる"
    "だけでなく、どのような順序・観点で検討すべきかを明示してください。例：「まず◯◯の"
    "実測/公的統計を確認し、次に△△との整合性を検算し、最後に□□の受入基準を満たすか"
    "確認せよ」。直前のタスクや併記対象タスク（[BL-191] task_focus_companion）との"
    "依存関係がある場合は、それらの確定値との整合性確認を思考プロセスの一部として"
    "明記してください。\n"
)
# [BL-115] BL-094（read_verified_fact/read_deliverable_fileでの既存確定値との同期説明）は
# 当初パラメータ化ヘルパーへの集約を試みたが、tests/test_bl094_read_tool_orientation.pyが
# 各関数自身のinspect.getsource()に"BL-094"/"read_verified_fact"/"read_deliverable_file"/
# "iter=1で"のリテラル文字列が含まれることを要求しており、ヘルパー化すると呼び出し元の
# ソースからこれらの文字列が消えてテストが壊れるため、共有化を見送り各関数に literal のまま
# 残した（call_task_planner/call_resource_arbiterで一度試みて実際に検証済み）。


def call_task_planner(goal: str, reviewer_feedback: str = "", goal_essence_text: str = "", state: dict | None = None,
                       existing_phases: list[dict] | None = None, revision_reason: str = "") -> list[dict]:
    """【SLM要約】
    Decomposition of a high-level goal into structured, actionable phases and detailed tasks by querying an AI planner.
It serves as the initial planning layer for breaking down complex objectives across the system.
    [BL-126 Stage C] revision_reason（ラン途中再構成トリガー時のみ非空）が与えられた場合、
    existing_phasesを提示した上で「無関係な既存タスクには一切触れず、影響を受けるタスクの
    みをsupersede/追加すること」を明示する固定指示ブロックを冒頭指示グループの直後に挿入する
    （§13.2のモード切替設計）。
    """
    revision_block = (
        f"""
    【重要: ラン途中での計画再構成（BL-126 Stage C）】
    これは初回の計画立案ではありません。以下の既存計画（existing_phases）が既に実行中であり、
    以下の理由（revision_reason）により、影響を受けるタスクのみを見直す必要が生じました。
    無関係な既存のフェーズ・タスクの内容は絶対に書き換えないでください（既に進行中の作業を
    無用に混乱させます）。影響を受けるタスクのみ、新しい内容へ置き換えるか、必要なら新規タスクを
    追加してください。返す最終的なJSON配列には、既存のまま維持するタスクも含め、再構成後の
    フェーズ・タスク全体を過不足なく含めてください（この配列に含まれなかった既存task_idは、
    再構成により廃止されたものとして扱われます）。

    ■ 再構成の理由（revision_reason）:
    {revision_reason}

    ■ 既存計画（existing_phases、再構成前）:
    {json.dumps(existing_phases or [], ensure_ascii=False, indent=2)}
    """
        if revision_reason else ""
    )

    reviewer_feedback_block = (
        f"""
    【重要: 前回の計画案への差し戻し（BL-087 Stage2）】
    前回生成した計画案は、実行開始前のレビューで以下の指摘を受け差し戻されました。
    今回は必ずこの指摘を踏まえて再分解してください。
    {reviewer_feedback}

    [BL-101: read_plan_draftで前回のホワイトボードを確認してから再分解する（重要）]
    上記の指摘に`[task_id]`が付いている項目については、いきなりゴール文から作り直すのではなく、
    まずread_plan_draft(task_id="...")で、そのtask_idの「フェーズ・タスク表」ホワイトボード
    （plan_drafts）の最新版を読んでください。これはあなた自身が前回書いた記述そのものであり、
    task_plan_reviewerが「## レビュワーからの指摘（要修正）」として直接書き込んだ個別指摘も
    含まれています。指摘されていないフェーズ・タスクは、内容を維持し不必要に書き換えないで
    ください（差し戻し圧力で無関係な部分まで丸ごと作り直すと、既に妥当だった設計を壊し、
    新たな矛盾を生むリスクがあります）。
    """
        if reviewer_feedback else ""
    )

    prompt = f"""
    {revision_block}
    {reviewer_feedback_block}
    以下の目標を、独立して議論・検証可能な「フェーズ」に分解し、
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
         （例: 「〈数量Xの算出〉」「〈初期費用の内訳〉」「〈年間ランニングコストの内訳〉」
         「〈感度分析〉」を1タスクに束ねてはいけません。それぞれ独立したタスクにするか、
         密接に関連する場合でもacceptance_criteriaの数を3以内に抑える粒度まで分割してください）。
       - depends_on: このタスクが前提として使う他タスクのtask_idを配列で指定してください
         （前提がなければ空配列）。
       - owns_variables: このタスクで初めて確定させる共有変数名を配列で指定してください
         （例: "unit_count"）。同じ変数を必要とする他タスクは、depends_onでこのタスクを
         指定し、値を再導出せず参照する前提とします（前提がなければ空配列）。
    4. 【曖昧な表記の禁止（重要）】acceptance_criteriaやdescriptionに数量・比率・長さ・面積・
       人数などを書く際は、どの指標（比率か絶対値か、何に対する割合か）を指しているのかを
       一意に確定できる表現にしてください。特に、括弧書きなどの補足情報が本文の数値制約と
       異なる指標に見える場合（例: 本文で「全体の約15%」という比率が示されているのに、
       別の記述で「(〈12単位〉相当)」という絶対値を括弧内の補足情報として併記すると、AIが
       「その〈12単位〉全体が15%に該当する対象である」と誤読し、比率の基準を取り違える恐れが
       あります）、両者の関係を明記するか、誤読を招く併記を避けてください。曖昧さが残る場合は
       description内で「これは位置を示す情報であり長さの定義ではない」等、解釈を一意に
       固定する注記を必ず加えてください。
    5. 【暗算禁止】ゴール文中の数値制約から比率・分割・単位換算などの計算が必要な場合
       （例：総面積に対する比率から距離を求める、総予算から購入可能台数の上限を見積もる等）、
       暗算で済ませず python_repl ツールで実際に計算してから、その結果をacceptance_criteria/
       descriptionの記述に反映してください。この計画分解はプロジェクト全体で最も上流の
       判断であり、ここでの暗算・計算ミスはタスク4.の曖昧表記防止と同様、後続の全タスクへ
       そのまま伝播するハルシネーションリスクとなります。
    6. 【派生値には根拠条件を併記（重要）】比率や制約から計算・仮定した派生値（ゴール文に
       直接の記載がない数値、例:「〈リソースX〉3個が上限」）をacceptance_criteria/owns_variablesに
       書く際は、結論の数値だけでなく、その根拠となる前提条件を必ず併記してください
       （例:「〈調達方式A〉の場合、単価Y×総予算Zから3個が上限（〈調達方式B〉等の
       代替手段がある場合はこの限りではない）」）。条件を欠いた断定は、後続のAIが
       それを唯一絶対の制約と誤読し、代替案の検討余地を失わせる原因になります。また、
       ゴール文自体が与えていない絶対値（例: 比率の分母となる総量そのもの）を、無理に
       一意の数値として確定させないでください。判断に迷う場合は「不明である」旨を
       description内に明記するに留め、根拠のない数値を作り出さないこと。
    7. 【おなじ思考・計算・検証は各回2回まで、繰り返し確認しない（重要）】ツール呼び出しの回数には上限が
       あります。同じ内容（例:「acceptance_criteriaが3個以内か」「depends_onの整合性」）を
       python_replで繰り返し再確認しないでください。各検証項目は2回計算・確認できれば十分です。
       新しい数値や新しい論点が無いまま「念のため最終確認」を重ねると、JSON出力そのものを
       書く余地が無くなり、上限到達時に強制的に打ち切られたテキスト応答としてJSONを一度に
       出力せざるを得なくなり、大規模な計画では出力が途中で切れて構文エラーになるリスクが
       あります。必要な数値計算がすべて終わったら、それ以上の確認は行わず、直ちに最終的な
       JSON配列の記述に移ってください。
    8. 【BL-093: thinkツールで検討過程を残す】このタスク分解は複数回のpython_repl呼び出しを
       跨ぐことが多く、{_BL093_THINK_VALUE_PARAGRAPH}
    9. [BL-094: read_verified_fact/read_deliverable_fileで既存の確定値と同期する]
       read_verified_factは全フェーズ・全タスク横断で、変数名やキーワードから既に確定した
       値（値・理由・引用元・confidence）を検索できます。read_deliverable_fileは過去タスクの
       成果物全文（前提込み）を読めます。特に差し戻し（reviewer_feedback）を受けての再分解
       時は、Goal Essence Analystや前回のタスク実行が既に何らかの値（総量の仮定等）を
       確定・仮定していないかread_verified_factで確認してから再分解してください。ゴール文に
       ない数値を自分で仮定する前に必ずこの確認を行い、既存の確定値と矛盾する新しい仮定を
       勝手に作らないこと。【最低限、iter=1で一度は、関連しそうなキーワードでread_verified_fact
       を呼び、他ノードが既に確定・仮定した値と同期してから分解を始めてください】。
    10. [BL-095: write_agreementで分解の判断根拠を書き残す] 最終的なJSON配列を出力する前に、
       write_agreement（entry_type="Decision", status="Proposed", action_type="CREATE"）を
       1回呼び、なぜこのフェーズ構成・タスク分割にしたか（フェーズ数、各フェーズのfocus_scope/
       expected_time_axisの選定理由、特に判断が分かれた依存関係やタスク粒度の決定）を
       decision_what/reason_whyとして記録してください。topicは「task_planner_phase_design」
       のようにread_verified_fact/read_deliverable_fileで後から検索しやすい固定的な文字列に
       してください。task_id/phase_idは特定の1タスクに紐づかないため省略して構いません。
       これにより、後続のExpertやUser AIが「なぜこの分解になっているのか」を
       read_deliverable_fileで遡って確認できるようになります（現状はJSON構造だけが伝わり、
       設計意図・却下した代替案は誰にも参照できず失われています）。
    11. [BL-101: read_plan_draftで「フェーズ・タスク表」ホワイトボードを確認する] 差し戻しを
       受けての再分解時は、冒頭の指摘欄で指示した通り、指摘のあったtask_idについて必ず
       read_plan_draft(task_id="...")を呼び、あなた自身が前回書いた記述とtask_plan_reviewerの
       個別指摘を確認してから、その部分だけを修正してください。指摘のないフェーズ・タスクを
       ゴール文から作り直す必要はありません。
    12. [BL-188: web_search/web_fetch/read_reference_fileで現実世界の制約を検証する] あなた自身の
       学習知識から導き出した判断も、必ずしも正確であるとは限らず、最新の情勢（法令・相場・規制等）
       を反映しているとも限りません。ゴール文の前提（地理・距離・費用相場・法規制等）が現実的に
       成立するか自分の知識だけで判断がつかない場合は、記憶からの推測で済ませず、必ずweb_search
       で信頼できる一次情報を確認・裏取りしてください。既にこのrun内で調べた可能性がある
       話題については、新規にweb_search/web_fetchを呼ぶ前にread_reference_file（keyword検索、
       呼び出し回数上限を消費しない）で既存のキャッシュを先に確認してください。web検索結果は
       鵜呑みにせず、一次ソース（公的統計・公式文書等）を優先し、二次的な要約より信頼性の高い
       情報を採用してください。この分解で採用した数値・前提のうち外部情報に基づくものは、
       write_agreementのcitations（type="web"等）で追跡可能な出典として明示してください。
       [BL-204] read_entityで、この課題に登場する事物について既に登録済みの事実を確認できます
       （何が既知で何が未確認かを踏まえてタスクを分解する際に役立ちます）。
       [BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値（予算上限等）は
       read_verified_factを使い、read_entityをentity未指定の「とりあえず一覧」目的で
       多用しないでください。
       【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
       read_plan_draft・write_agreement・web_search・web_fetch・read_reference_file・
       read_entity・think
       です。{_THINK_TRAILER_SENTENCE}
    13. [BL-196: 実行環境に無い専用処理能力の行使をacceptance_criteriaに要求しない] acceptance_criteria/
       descriptionに「実測データの収集・抽出・生成」を書く際は、Expertが実際に使えるツール
       （python_repl・web_search・web_fetch・read_reference_file等）で到達可能な水準に
       留めてください。python_replはmath/statistics等の許可リストのみのサンドボックスで
       許可外モジュールのimport・ファイル読み込みは一切できず、web_fetchもtext/*と
       application/pdfのみ対応です。専用の解析・変換ツール、特殊形式のデータ処理、実測機器
       による現地計測などが無ければ原理的に満たせない要求は、たとえそのドメインにおいて
       理想的な精度であっても課さないでください。acceptance_criteriaは、ゴール文で与えられた
       背景データ・web_searchで確認できる公的な二次情報・そこから導出した合理的な仮定
       （仮定である旨を明記）の組み合わせで満たせる水準にしてください。ゴール文に既にある
       数値データ（人口統計等）で確立されている「実測値と計画仮定を分離して明記する」という
       扱いを、他の種類のデータにも同じ基準で適用してください。

    ■ 目標: {goal}
    {goal_essence_text}

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

    # [BL-089] 層2リトライ（_query_and_parse_with_retry、D-005）でラップする。単発のパース失敗で
    # 即座に縮退計画（fallback_phase）へ落ちると、実際には正しく分解されたプランが1回の
    # フェンス構文の乱れだけで握りつぶされる（実ドライラン`log/2026-07-25/1814`で確認）。
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "task_planner"  # [BL-095]
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    phases, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_task_planner, model=model_task_planner, label="Task Planner",
        tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_PLAN_DRAFT_TOOL, WRITE_AGREEMENT_TOOL, WEB_SEARCH_TOOL, WEB_FETCH_TOOL, READ_REFERENCE_FILE_TOOL, READ_ENTITY_TOOL, THINK_TOOL], fallback=fallback_phase,
        state=state,
    )
    if parse_failed:
        print("🚨 [Task Planner] JSON分解結果の取得に失敗しました。縮退計画にフォールバックします。")
    return phases

def call_orchestrator(state: LineageState, config: Appconfig ) -> dict:
    """【SLM要約】
    Construction of a comprehensive prompt by aggregating system state (goals, agreements, history) and user input to direct an LLM in selecting the most appropriate domain expert for task execution.
    """
    _conn = get_active_conn()
    goal_context = (
        f"Goal: {state['goal']}\n{_get_goal_essence_text(_conn, state['run_id'])}"
        if config["agent_has_guardrail"] else "(自由にアシストしてください。)\n"
    )

    recent_history = state["chat_history"][-config["chat_history_window"]:]
    recent_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])
    if not recent_text:
        recent_text = "(まだ履歴はありません)"

    agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])
    print(f"【プロジェクトの合意・決定事項・検討状況DB】\n {agreements_text} \n\n")

    # [BL-148] read_project_plan/read_deliverable_fileのハンドラはstateを直接参照できず
    # このグローバルしか見ないため、call_expert等と同じくノード呼び出し分をコピーする。
    global _CURRENT_PHASES
    _CURRENT_PHASES = state.get("phases", [])
    project_plan_toc = _build_project_plan_toc(_CURRENT_PHASES)

    # [BL-148] Orchestratorがcurrent_task_id/計画/issue状況を一切参照できず、対話の生テキストだけで
    # 専門家選定をしていたため、`current_task_id`がBL-125で他タスクへブロックされていても対話が
    # そのタスクへ漂うとそちらへ専門家選定が引っ張られ、後続ノード（Expert/Detector）へ渡る
    # current_task_id由来の構造化情報と矛盾する事態が実ドライラン（`log/2026-08-02/0832`）で
    # 発生していた（Detector自身が「プロンプトのバグだと思う」と自己申告）。
    scope_ctx = _build_task_scope_context(state, _conn)
    current_task_context = (
        f"【現在のタスク（current_task_id={state.get('current_task_id', '')!r}）】\n"
        f"{scope_ctx['current_task_json']}\n"
        f"【このタスクの未充足の要求項目】\n{scope_ctx['remaining_criteria_text']}\n"
        f"【プロジェクト計画目次（詳細はread_project_planツールで確認可）】\n{project_plan_toc}\n"
    )

    if config["is_stateless_mode"]:
        hydrate_context = _build_hydrate_context_from_db(_conn, state["run_id"], config)
        history_text = f"【過去のシステム判断ログ】\n {hydrate_context} \n\n【直近の対話文脈】\n{recent_text}"
    else:
        all_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in state["chat_history"]])
        history_text = f"【これまでの全対話文脈】\n{all_text}" if all_text else "(まだ履歴はありません)"

    # [BL-104/BL-114] プロンプトキャッシュのヒット率向上のため、固定指示文（役割説明・BL-078の
    # 説明）を先頭に配置し、ターンごとに変わる動的な内容（goal_context・user_input・決定事項DB・
    # 対話履歴）は末尾に配置する。JSON形式の指示は、動的ブロックの後に続く短い固定末尾として
    # 残す（call_task_plan_reviewer等、他ノードでも同じ配置を採用しており、一度キャッシュの
    # 連続プレフィックスが動的ブロックで途切れた後は、末尾の短い固定文を先頭側へ動かしても
    # キャッシュヒット率上の利益はないため）。位置的参照（「上記」「後述」）を持つブロックは
    # このプロンプトには存在しないため、全ブロックを自由に並び替えている。
    # [BL-114] 以前はgoal_context（動的）が先頭に来ており、このコメントが謳う
    # 「固定指示文を先頭・動的内容を末尾」という方針とコードが矛盾していた（実態調査で発覚）。
    prompt = (
        f"""
        Taskを遂行するために最も適した専門家の肩書き（役職名）を、固定リストから選ぶのではなく、
        このタスクの内容に即して自由に生成してください。\n
        例: 「〈対象領域〉の需要予測専門家」「〈対象システム〉の安全基準アナリスト」のように、
        タスクの実態に即した具体的な肩書きにしてください（漠然とした「アシスタント」等は避ける）。\n
        \n
        回答は簡潔で論理的にせよ\n
        \n
        [BL-078] 専門家を選ぶ過程で、あなたはこのタスクの内容・過去の経緯を踏まえて既にある程度
        考えているはずです。その考察を'focus_guidance'として明示的に出力してください。これは
        専門家を選んだ理由（'reason'）とは別物で、選ばれた専門家AIがこのタスクに実際に着手する際に
        「具体的にどんな観点で検討すべきか」「特に見落としやすい落とし穴は何か」を、このタスク固有の
        内容に即して1〜3点、実行可能な指示として書いてください（一般論・当たり前の心構えは不要）。
        該当する具体的な観点がなければ空文字でよい。\n
        \n
        [BL-209: focus_guidanceはacceptance_criteriaを超えない] focus_guidanceは、下記
        【このタスクの未充足の要求項目】（acceptance_criteria）を**達成しやすくするための着眼点**で
        あり、**新しい要求項目を追加する場所ではありません**。acceptance_criteriaに書かれていない
        成果物・分析・モデル（時間帯別シミュレーション、複数シナリオの感度分析、状態遷移モデル、
        追加の判定軸等）を新たに義務付けないでください。「〜も算定すること」「〜を再現可能にすること」
        のような、受入基準に無い新規の作業指示を書くと、Expertは受入基準を満たしても承認されない
        水準まで作業を広げ続け、タスクが完了しなくなります（実際に`log/2026-08-11/0016`の
        task_2_3で、受入基準3項目が充足済みと判定された後もfocus_guidanceが受入基準に無い
        要求を積み増し、空転が続いた）。既に受入基準を満たしている項目について、さらに高い水準を
        求める必要はありません。書くべきなのは「その受入基準を満たすうえで、この課題では特に
        どこを見落としやすいか」です。\n
        \n
        {goal_context}\n
        \n
        Task(ユーザーAIの指示): {state["user_input"]}\n
        \n
        {current_task_context}\n
        \n
        【プロジェクトの合意・決定事項・検討状況DB】
        {agreements_text}\n
        \n
        {history_text}\n
        \n
        【重要】上記の対話文脈がどのタスクについて話しているように読めても、専門家選定・focus_guidanceは
        必ず【現在のタスク】欄のcurrent_task_idを基準にしてください。\n
        【重要】あなたが使えるツールはread_project_plan・read_deliverable_file・read_verified_fact・
        thinkです。{_THINK_TRAILER_SENTENCE}\n
        \n
        Return ONLY JSON: {{"expert": "（生成した専門家の肩書き）", "reason": "...", "focus_guidance": "（このタスク固有の着眼点・注意点、無ければ空文字）"}}'
        """
    )
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "orchestrator"
    _CURRENT_TASK_ID = state.get("current_task_id", "")
    _reset_think_scratchpad()  # [BL-093]
    # [BL-148] 単発JSON応答からツールループへ変更。current_task_context（プロンプト埋め込み）に
    # 加え、詳細確認用の読み取り専用ツールを付与する。Orchestratorの出力は専門家選定メタデータ
    # のみで状態を変更しないため、write_agreement等の書き込み系ツールは意図的に与えない
    # （`_check_write_permission`のロール表にも"orchestrator"は存在しない）。
    res = query_AI(
        [{"role": "user", "content": prompt}], client=client_orchestrator, model=model_orchestrator, label="Orchestrator",
        tools=[READ_PROJECT_PLAN_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_VERIFIED_FACT_TOOL, THINK_TOOL],
        state=state,
    )
    _orchestrator_fallback = {"expert": "", "reason": "", "focus_guidance": ""}
    parsed = _safe_json_parse(res, fallback=_orchestrator_fallback)
    if parsed is _orchestrator_fallback:
        print(f"⚠️ [Orchestrator] JSON解析に失敗しました（生レスポンス冒頭300字: {(res or '')[:300]!r}）。専門家名は空フォールバックになります。")

    # [CONSTRAINT] BL-018当時、専門家名を固定16種の配列に絞っていたが、call_expert/グラフのどちらも
    # 具体的な専門家名で分岐しておらず（プロンプトへの埋め込みラベルとして使われるのみ）、
    # 固定リストは無用な足かせだった（ログ上、リストのどれにも綺麗に当てはまらないタスクで
    # 選定に無駄な思考コストが生じていた）。専門家ごとの個別ノード構造が必要になった時点で
    # 再度制約を設ける方針とし、それまでは自由記述とする。空・空白のみの場合のみフォールバックする。
    expert = (parsed.get("expert") or "").strip()
    if not expert:
        print("  ⚠️ [Orchestrator] 専門家名が空文字だったため、汎用フォールバック「プロジェクト全般アドバイザー」を使用します。")
        expert = "プロジェクト全般アドバイザー"
    return {"expert": expert, "reason": parsed.get("reason", ""), "focus_guidance": (parsed.get("focus_guidance") or "").strip()}


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
    # [BL-104] read_project_planツールが参照するグローバルへ、このノード呼び出し分のみコピーする
    # （tool handlerはstateを直接参照できないため、_CURRENT_TASK_ID等と同じパターンを踏襲）。
    global _CURRENT_PHASES
    _CURRENT_PHASES = state.get("phases", [])
    project_plan_toc = _build_project_plan_toc(_CURRENT_PHASES)

    # [BL-104] プロンプトキャッシュ（OpenRouter含め大半のプロバイダが自動で行うプレフィックス
    # キャッシュ）のヒット率を上げるため、実行中いつでも内容が同一の固定指示文を先頭にまとめ、
    # ターンごとに変わる動的データ（決定事項DB・現在タスク情報・ホワイトボード等）は末尾（chat_history
    # への引き渡し直前）に配置する。各ブロックの移動前に「上記の」等の位置的参照が無いことを
    # 個別に確認済み（詳細はBL104_basic_design.md）。「⚠️【厳守事項】上記の【決定事項DB】は…」と
    # 「⚠️【重要：Detectorからの差し戻し】上記📋セクションに示されている…」の2ブロックは、それぞれ
    # agreements_text／ホワイトボード表示への位置的参照を持つため、この並び替えの対象外とし、
    # 元の相対位置（参照先の直後）を維持する。
    system_prompt = f"あなたは有能な{expert_name}の分野の専門家です。\n"

    system_prompt += f"\n5ターン毎に議論のサマリーを出力せよ。数値などは消さず明示的に示すこと。\n"

    system_prompt += (f"""
       \n🔥 【エージェントとしての行動原則】\n
        あなたはプロフェッショナルとして、制約（予算・時間・性能・規模など）の壁に直面しても、\n
        安易に「制約の緩和」や「要件の放棄（一部機能の省略など）」を提案しないでください。\n
        制約が厳しい場合こそ、最新の技術動向、代替アプローチ、リソースの再配分、設計の見直しなど、\n
        抜本的でクリエイティブな「代替案」を絞り出し、絶対目標の枠内に収める努力を最後まで諦めないでください。\n
        \n
        【制約と条件の切り分け（重要）】\n
        ゴール文には、動かせない「真の制約」（例：総予算の上限、法規制、安全基準）と、\n
        議論の前提として例示的に与えられているだけの「見直し可能な条件」（例：特定の調達方法を\n
        前提にした単価、特定の運用パターンの例示的な数値）が、区別なく並記されていることがあります。\n
        検討の結果、与えられた条件のままでは制約を同時に満たす解が存在しないと分かった場合、\n
        思考停止で条件を鵜呑みにせず、まず「これは動かせない真の制約か、それとも見直し可能な\n
        前提条件か」を都度見極めてください。後者だと判断できる場合は、その前提自体を疑い、\n
        代替の前提（例：調達方法の変更、仕様の見直し、運用方式の変更）を提案してください。\n
        ただし、真の制約（総予算・法規制・安全基準等）そのものの緩和・放棄は認められません。\n
        \n
        【重要：ゴール自体の文言が真の制約と矛盾していると気づいた場合（escalate_premise_concernツール）】\n
        上記の見極めの結果、問題が「あなたの提案の作り方」ではなく「ゴール文に書かれた制約や前提\n
        そのものの文言」にあり、その文言通りに満たそうとすると、その制約が本来仕えるべき真の目的\n
        （例：ゴールの対象者・受益者の実質的な便益に対して、手段の制約（規模・数量・稼働条件等）が\n
        矛盾して固定されている等）とかえって矛盾してしまう、と具体的な根拠を持って判断した場合は、\n
        escalate_premise_concern ツールを呼び出してください。これは以下の点で他の対応と異なります：\n
        ・「制約が厳しくて達成できない」という一般的な泣き言・言い訳としては絶対に使わないこと。\n
        　あくまで「ゴールの文言そのものの矛盾」に限定した、狭く構造化された懸念提起です。\n
        ・呼び出しても現在のタスクのスコープ外に踏み込む許可は得られません。今回のタスクの\n
        　acceptance_criteriaは呼び出し後も必ずこのターン中に通常通り満たしてください。\n
        ・判断はUser（発注者）に委ねられます。承認/却下されるまでは、ゴール文はまだ改定されて\n
        　いないものとして、現行の制約に従って作業を続けてください。\n
        ・同じ懸念を重複して提起しないでください（未解決・却下済みの状況は下記に表示されます）。\n
        \n
        【重要：成果物ではなくUserへの質問が必要な場合（ask_user_questionツール、BL-130）】\n
        現在のタスクのacceptance_criteriaを満たすのに本当に必要な情報が欠けており、あなた自身の\n
        判断だけでは前進できない（例：要求が曖昧で複数の解釈があり、方向性の選択はUser（発注者）\n
        にしか決められない）場合は、ask_user_question ツールを呼び出してください。これは：\n
        ・escalate_premise_concern（ゴール文の制約と真の目的の矛盾）とは別物です。単なる情報不足・\n
        　方向性の確認にはこちらを使ってください。\n
        ・成果物を出す代わりにこのツールを呼ぶと、そのターンは通常の監査（Detector）・意思抽出\n
        　（Decision Extractor）がスキップされ、あなたの質問がそのままUserへ提示されます。\n
        ・十分な情報があるのに単に確認のためだけに使うと、成果物の提出が遅れます。本当に前進\n
        　できない場合にのみ使用してください。\n
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

    system_prompt += (
        "\n【BL-188: 学習知識を無検証で断定しない（必須）】\n"
        "あなた自身の学習知識から導き出した回答や思考も、必ずしも正確であるとは限らず、"
        "最新の情勢（法令・相場・規制等）を反映しているとも限りません。ゴール文に直接記載の"
        "ない数値・相場・法令・規制等（例：人件費単価、法令の条文番号、業界標準）を提示する際は、"
        "記憶だけで断定せず、web_searchで信頼できる一次情報（公的統計・公式文書等）を確認・"
        "裏取りしてください。ただしweb_searchはいきなり呼ばず、[BL-199/BL-200] "
        "①read_goal_reference（開発者がこのゴール用に事前収集した参照データ）"
        "→②read_reference_file（web_fetchキャッシュ。URLキーで全run共有され、過去のrunで"
        "取得済みのページも読めます）→③web_search、の順に確認してください。①②はいずれも"
        "呼び出し回数上限を消費しません。確認した内容は、write_agreementのcitations（type=\"web\", detail=<URL>等）で"
        "追跡可能な出典として明示してください。"
        "【最低限】今回の成果物がゴール文にない数値（単価・相場・法定基準値等）を新たに"
        "前提として置く場合、confirmed_variablesのcitationsを`expert_calculation`のみで済ませず、"
        "その主要な前提について最低1回はweb_searchを呼んでから確定値・暫定値を書いてください。"
        "web_searchが実際にエラーになった（例：APIキー未設定）場合を除き、検索せずに独自の"
        "「相場」「一般的な値」を断定して成果物の土台に使わないこと。\n"
    )

    system_prompt += (
        "\n【BL-195: web由来の実例数値をそのまま転記しない】\n"
        "web_searchで、この課題と類似の実在事例（同種のデマンド交通・自動運転バス等の運行"
        "サービス）を発見した場合、その具体的な運行本数・車両台数・運賃・人員体制等の数値を、"
        "検証や再計算なしにそのまま成果物へ転記しないでください。実例はあくまで「このような"
        "設計が現実的に成立し得るか」という妥当性チェックの参考情報として扱い、成果物の数値は"
        "必ず本課題固有の制約（予算・需要マトリクス・距離・SLA）とpython_replでの計算から"
        "独自に導出してください。転記した場合、citationsにtype=\"web\"を付けるだけでは"
        "不十分です——confirmed_variablesのreason_whyに、その数値を本課題の制約からどう"
        "導出したか（計算式・入力値）を必ず明記してください。実例の数値と独自算出の結果が"
        "たまたま近い値になること自体は問題ではありませんが、算出過程を示さず実例の値を"
        "そのまま使うことは認められません。\n"
    )

    system_prompt += (
        "\n【BL-204: 課題に登場する事物の事実はレジストリで管理する】\n"
        "この課題に登場する事物（固有の名前を持つ実世界の対象——施設・場所・組織・路線・"
        "制度・サービス等、種類は問いません）についての事実は、read_entity／"
        "write_entity_attributeで読み書きしてください。**レジストリが真実の源であり、"
        "成果物本文はその提示**です。事物の事実を、記憶や成果物本文からの再構成で"
        "組み立てないでください（同じ事実を毎ラウンド取り直して、前回より劣化した値に"
        "置き換わる事故が実際に起きています）。\n"
        "1. 事実を書く前に、まずread_entityでその事物に既に何が記録されているかを確認する。\n"
        "2. 判明した事実はwrite_entity_attributeで記録する。属性名は自由ですが、"
        "**値には必ずcitations（出典）とconfidenceを添えてください**。"
        "confidenceは\"confirmed\"（他タスクと突き合わせても動かない）と\"provisional\"の2値です。"
        "「自分で導出した工学的仮定である」ことは、confidenceではなく"
        "citationsのtype=\"expert_calculation\"で表してください（確定度と出所は別の軸です）。\n"
        "[BL-205: read_entityとread_verified_factの使い分け] read_entityは**名前を持つ事物**"
        "（施設・場所・組織等）の属性専用です。予算上限や比率のような、どの事物にも属さない"
        "単独の値はread_verified_factを使ってください。read_entityをentity未指定で呼んでも"
        "名前の一覧しか返らず属性は含まれません——「とりあえず全部見る」目的では使わず、"
        "確認したい事物の名前が分かっている場合にentity指定で呼んでください。\n"
        "3. **事物の名称は、ゴール文に書かれた表記をそのまま使ってください。**"
        "記憶による言い換え・略称・類似名を使わないでください。ゴール文に登場する事物は"
        "run開始時に登録済みであり、未登録の名前を渡すと候補付きで差し戻されます。"
        "ゴール文に無い事物をweb_search等で新たに発見した場合のみ、register_entityで"
        "出典を添えて登録してください。\n"
    )

    system_prompt += (
        "\n【BL-198: 実測できる地理データは実測する】\n"
        "地点の標高、2点間の直線距離、住所の緯度経度、道路距離・所要時間は、専用ツール"
        "（gsi_geocode→gsi_get_elevation／gsi_calc_distance_bearing／calc_road_route）で"
        "実際に取得できます。これらを記憶からの推測やweb_searchスニペットの間接的な言及で"
        "代用せず、専用ツールの実測値を使ってください（住所しか分からない場合は、まず"
        "gsi_geocodeで緯度経度を得てから他のツールへ渡します）。\n"
        "[BL-203: gsi_geocodeには必ず「番地までの住所」を渡す] gsi_geocodeは住所ジオコーダで"
        "あり、施設検索ではありません。施設名（病院名・学校名・駅名等）を入れても**完全に無視**"
        "され、住所部分だけで解決されます（「◯◯町 △△病院」と「◯◯町」は同じ座標を返します）。"
        "大字止まりで解決すると、返るのはその区画の代表点であり、区画が山側へ広がる地域では"
        "施設の実位置と数km・標高で数百m離れます。その座標をgsi_get_elevationや距離計算へ渡すと、"
        "**誤った場所の正しい実測値**という最も気づきにくい誤りになります。したがって、"
        "拠点の座標が必要な場合は、まずread_goal_reference／read_reference_file／web_searchで"
        "その施設の番地までの住所を確認し、住所そのものをqueryに指定してください。"
        "返却されたprecisionが\"area_centroid\"の場合、その座標を施設の位置として使わず、"
        "位置未確認として扱ってください（\"point\"なら地点まで解決できています）。"
        "また、拠点の名称はゴール文に書かれた表記をそのまま使い、記憶で別名・類似名に"
        "言い換えないでください。\n"
        "ただしgsi_calc_distance_bearing"
        "が返すのは直線距離であり道路距離ではありません——山間部の道路では実際の距離・所要時間を"
        "大きく過小評価します。道路距離・所要時間が必要な場合はcalc_road_routeを使い、直線距離を"
        "道路距離として提示しないでください。なお、これらのツールで取得できない種類のデータ"
        "（例：道路区間単位の積雪・凍結の実測記録）まで実測値で揃えようとする必要はありません。"
        "取得できない項目は、公的情報の定性的な参照と、根拠を明記した工学的仮定（仮定である旨を"
        "明記）で扱ってください。\n"
    )

    system_prompt += (
        "\n【同じ検証・計算を繰り返さない（重要）】\n"
        "ツール呼び出しの回数には上限があります。同じ論点（例:「この数値は制約を満たすか」）を"
        "python_replで繰り返し再確認しないでください。各検証項目は2回計算・確認できれば十分です。"
        "新しい数値や新しい論点が無いまま「念のため最終確認」を重ねると、実際の回答を書く余地が"
        "無くなり、上限到達時に強制的に打ち切られたテキスト応答とせざるを得なくなります"
        "（大規模な成果物では応答が途中で切れて後工程に支障が出るリスクがあります）。必要な検算が"
        "すべて終わったら、それ以上の確認は行わず、直ちに回答の記述に移ってください。\n"
    )

    system_prompt += (
        "\n【ドメイン妥当性チェック（★検算とは別の観点、必須）】\n"
        "検算（python_repl）はあくまで「数式が正しいか」しか保証しません。数式の辻褄を合わせるために、"
        "元データに根拠のない内訳・仮定をその場ででっち上げていないか（例：制約を満たすよう逆算した"
        "都合の良い数値分割）を必ず自問してください。また、数値が正しくても現実世界で本当に成立するか"
        "（労働基準法上のシフト・休憩要件、物理的な運用可能性、予備・冗長性の欠如、安全規制等）を、"
        "検算とは独立した観点として最後に必ず確認してください。制約が厳しく数式上は帳尻が合わせられても"
        "現実には成立しない場合は、そのことを隠さず明示的に指摘・報告してください。\n"
    )

    system_prompt += (
        "\n【罠：部分的な要件の無根拠な拡大解釈（BL-134）】\n"
        "「最低N名」「常時M台」のような部分的な要件を、時間帯・範囲・対象等の条件を明示"
        "せずに拡大解釈して確定値化していないか自問してください。特に、ゴール文が稼働時間・対象"
        "範囲等を明示的に区切っている場合（例：特定の時間帯に限定され、それ以外は"
        "「対象外」と明記されている等）、要件を無条件に24時間・全期間・全範囲へ一般化するのは"
        "典型的な罠です（実例：「最低N名」という要件を、ゴール文が明示する稼働時間帯を無視して"
        "24時間365日体制と解釈し、本来不要な人件費を確定値として計上してしまった）。拡大解釈する"
        "場合は、その根拠となるゴール文中の具体的な記述を明示してください。根拠がゴール文に無い場合、"
        "その値をconfirmed_variablesのconfidence=\"confirmed\"として扱わず、\"provisional\"とした上で、"
        "解釈の分かれ目（例：「常駐」が稼働時間帯限定か終日か）をwrite_issueで明示的に記録してください。\n"
    )

    # [BL-041] 「木を見て森を見ず」対策: 狭いタスクスコープ内で導出した数値が、
    # 実は他タスクの制約と衝突する可能性を残したまま無条件に確定値として扱われ、
    # 後から発覚しても誰も再検討しない（Expertはスコープガードレールで他タスクに
    # 踏み込めず、write_agreementのSUPERSEDEも自発的には使われない）問題への対応。
    # ゴールで与えられた絶対制約と、タスク内で導出した暫定値を区別させ、
    # write_agreementのconfirmed_variables.confidenceで機械可読に記録させる。
    system_prompt += (f"""
    \n🔀 【確定値と暫定値の区別（重要）】\n
    ゴールで直接与えられた絶対的な制約（例:「予算上限1億円」「上限3,000万円」）はconfidence判断の対象外です。\n
    一方、あなたがこのタスクの範囲内で導出した数値（例：数量、内訳金額）は、他タスクの制約と
    まだ突き合わせが済んでいない可能性があるため、原則として\n
    write_agreementのconfirmed_variablesでは confidence="provisional" として記録してください。\n
    confidence="confirmed" にしてよいのは、この数値がプロジェクト全体を通じて他のどのタスクの
    制約からも影響を受けないと明確に判断できる場合、またはUserが明示的にこの値を最終確定と
    承認した場合に限ります。\n
    暫定値は後続タスクで矛盾が判明した際に再検討される前提の値であり、暫定として記録すること自体は
    後退ではありません。\n
    """)

    # ここから先は実行中に変化する動的な内容。[BL-178] ユーザー指定順（視座は上から下、
    # 文脈は過去から現在）で提示するため、system_promptを先頭システムメッセージ用
    # （system_prompt_leading）と末尾システムメッセージ用（system_prompt_trailing）の
    # 2つに分けて組み立てる。system_prompt内でテキスト位置をどう並べても、messages配列は
    # [system, ...chat_history]という構造上chat_history側が常に物理的に後ろへ来るため、
    # 「差し戻し情報を本当に最後に読ませる」にはchat_historyより後ろへ新規メッセージを
    # 追加する必要がある（実ログlog/2026-08-05/1049で、末尾のchat_historyが無関係な話題で
    # 占められ差し戻し指摘が埋もれていたことを確認、詳細はBL178_basic_design.md）。
    #
    # leading: 絶対的な行動指針（ゴール＋本質）→プロジェクト計画目次→直近の会話への導入。
    # trailing（chat_historyより後ろ）: 決定事項DB→Detectorの気づき→申し送り→エスカレーション
    # 状況→エスカレーション再開通知→現在のタスクのスコープ→ホワイトボード→Orchestratorの
    # 着眼点→制限時間→厳守事項→Detectorからの差し戻し（最後）。
    system_prompt_leading = system_prompt
    system_prompt_trailing = ""

    # [BL-078] Orchestratorが専門家選定時に考察した、このタスク固有の着眼点・注意点。
    expert_focus_guidance = state.get("expert_focus_guidance", "")

    if agent_has_guardrail:
        system_prompt_leading += f"\n【あなたの絶対的な行動指針】\n👉 {state['goal']}\n"
        system_prompt_leading += f"\n{_get_goal_essence_text(_conn, state['run_id'])}\n"

    # [BL-104] 全フェーズ・全タスクの完全なJSON（phases_json）は、read_verified_fact/
    # read_deliverable_fileと機能的にほぼ重複する上、BL-025のスコープガードレールの趣旨
    # （他タスクのowns_variables領域に踏み込ませない）とも逆行するため、常時表示は
    # phase_id/task_id/titleのみの軽量な目次（ToC）にとどめ、詳細が必要な場合のみ
    # read_project_planツールで能動的に取得させる。
    system_prompt_leading += (f"""
    \n📊 [プロジェクト進行計画 目次]
    Task Plannerが作成したフェーズとタスクの一覧（目次）を以下に示します。各タスクの詳細
    （description・acceptance_criteria・depends_on・owns_variables）が必要な場合は、
    read_project_planツールで全文を確認してください。\n
    {project_plan_toc}\n\n
    指示があったフェーズ、タスクに関しては、必ずこの計画を参照し、逸脱や矛盾がないよう思考してください\n
    \n
    """)

    # BL-025: Expertが他タスクのowns_variables領域まで踏み込むことを防ぐスコープガードレール
    # （current_task_json等はtrailing側で使用するが、deferred_notes_textが先に必要なため
    # ここで一括取得する）。
    _scope_ctx = _build_task_scope_context(state, _conn)
    current_task_json = _scope_ctx["current_task_json"]
    verified_facts_json = _scope_ctx["verified_facts_json"]
    remaining_criteria_text = _scope_ctx["remaining_criteria_text"]
    whiteboard_text = _scope_ctx["whiteboard_text"]
    deferred_notes_text = _scope_ctx["deferred_notes_text"]
    _escalation_status_text = _get_escalation_status_text_for_expert(_conn, state["run_id"])
    # 履歴からは消えた「前回の自分のNG発言」をStateから復元して突きつける
    previous_output = state.get("expert_output", "(取得不可)")

    if is_stateless_mode:
        hydrate_context = _build_hydrate_context_from_db(_conn, state["run_id"], config)
        # [BL-103] facilitatorのエスカレーション名指しはchat_history末尾に追記されるだけで
        # chat_history_windowを過ぎると跡形もなく消える。issue_logのescalated行を毎ターン
        # DBから直接注入することで、その「発言が消えた後の穴」を埋める（recencyに関係ない pin）。
        escalation_pin = _build_escalation_pin_text(_conn, state["run_id"], state.get("current_task_id", ""), state.get("round_count", 0))
        if escalation_pin:
            hydrate_context += f"\n\n【⚠️エスカレーション中の懸念（要対応、issue_log）】\n{escalation_pin}"
        # [BL-194] DEFER済み（別タスクへの受け皿が確定済み）の懸念は、非強制トーンで
        # 別見出しに分離する。「要対応」側に混ぜたままだと、現タスクのacceptance_criteria
        # に無い懸念をExpertが先取りして再導出し続ける事故（log/2026-08-08/1514）を招く。
        deferred_issue_pin = _build_deferred_issue_pin_text(_conn, state["run_id"], state.get("current_task_id", ""))
        if deferred_issue_pin:
            hydrate_context += f"\n\n【📤 対応予定が確定済みの懸念（参考・現タスクでは対応不要、issue_log）】\n{deferred_issue_pin}"
        # [BL-194] ACKNOWLEDGE中（現在タスクの責務であり対応中）の懸念も前向きなトーンで表示する。
        acknowledged_issue_pin = _build_acknowledged_issue_pin_text(_conn, state["run_id"], state.get("round_count", 0))
        if acknowledged_issue_pin:
            hydrate_context += f"\n\n【🛠 現在のタスクで対応中の懸念（issue_log）】\n{acknowledged_issue_pin}"
        # [BL-136] status='open'（minor）行も参考情報として可視化する（従来はescalated行のみ）。
        open_issue_pin = _build_open_issue_pin_text(_conn, state["run_id"])
        if open_issue_pin:
            hydrate_context += f"\n\n【ℹ️ 未解決の軽微な懸念（参考、issue_log）】\n{open_issue_pin}"
        # [BL-178] 過去の圧縮ログは「これから直近の会話を示す」という次の導入文より前に置き、
        # 「直近の会話です」という予告の直後には実際に直近のraw chat_historyが来るようにする。
        system_prompt_leading += f"\n【過去の会話を圧縮したシステム判断ログ】\n{hydrate_context}\n"

    system_prompt_leading += (f"""
    \n文脈の参考として以下に直近の会話を示します
    [-----以下は直近の会話です-----]\n
    """)

    messages = []
    if is_stateless_mode:
        messages.append({"role": "system", "content": system_prompt_leading})
        recent_history = state["chat_history"][-chat_history_window:]
        for msg in recent_history:
            messages.append(msg)
        #messages.append({"role": "user", "content": user_input})
    else:
        messages.append({"role": "system", "content": system_prompt_leading})
        for msg in state["chat_history"]:
            messages.append(msg)
        #messages.append({"role": "user", "content": user_input})

    # [BL-178] ここから先（system_prompt_trailing）はmessages配列の最後（chat_historyより
    # 後ろ）へ独立したsystemメッセージとして追加する。決定事項DB・厳守事項・差し戻し情報という
    # 「直近の是正内容」を、chat_historyの内容に関わらず必ず最後に読ませるための構成。
    system_prompt_trailing += f"\n【プロジェクトの合意・決定事項・検討状況DB（遵守必須）】\n{agreements_text}\n\n"

    system_prompt_trailing += _build_detector_observations_block(state)

    if deferred_notes_text:
        system_prompt_trailing += f"\n📌 【BL-082: 他タスクからの申し送り事項（先送り）】\n{deferred_notes_text}\n"

    # [BL-191] joint_focusで併記対象に指定された過去タスクがあれば追加コンテキストとして注入
    # （current_task_json等の「現在のタスク」定義自体は変更しない、BL-025のスコープガードレール
    # 意図を維持）。redirect_backwardで実際にフォーカスが切り替わった直後の一度きり通知も併記。
    system_prompt_trailing += _get_task_focus_companion_text(state)
    system_prompt_trailing += _build_task_focus_transition_notice(state)

    # [BL-086] これまでに提起したエスカレーションの状況（Open/Rejectedのみ）を提示し、
    # 同じ懸念の重複再提起を防ぐ。Acceptedはstate["goal"]自体が既に改定済みのため
    # ここでは表示しない（毎ターン再埋め込みされるgoal本文が既に反映済み）。
    if _escalation_status_text:
        system_prompt_trailing += f"\n{_escalation_status_text}\n"

    system_prompt_trailing += _build_escalation_resume_notice(state)  # [BL-096]

    system_prompt_trailing += (f"""
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

    system_prompt_trailing += f"\n📋 【R4: 成果物の差分編集】\n{whiteboard_text}\n"

    # [BL-078] Orchestratorが専門家選定時に考察した、このタスク固有の着眼点・注意点。
    # Detectorの「観点を変えるだけで仕事ぶりが変わる」効果と同じ発想で、Expertの思考を
    # 個々のタスクの実態に最適化する狙い（従来はOrchestratorの選定理由としてログに残るのみで、
    # Expertには一切伝わっていなかった）。
    if expert_focus_guidance:
        system_prompt_trailing += f"\n🎯 【このタスクで特に注意すべき観点（Orchestratorより）】\n{expert_focus_guidance}\n"

    system_prompt_trailing += f"\n⏳ 【制限時間】: 全 {max_turns} ターン中、現在は **{turn_count} ターン目** です。\n"
    if turn_count >= max_turns - 2:
        system_prompt_trailing += "🚨 【超重要・最終盤】これが最後の回答です。これまでの議論と『決定事項DB』の内容をすべて網羅し、集大成としての成果物を出力してください。\n"
    elif turn_count > max_turns * 0.5:
        system_prompt_trailing += "⚠️ 【議論の後半戦】新しい案の提示は控えてください。これまでの決定事項を具体化し、ドキュメント化にフォーカスしてください。\n"

    # 【追加】Agent AIの越権行為（勝手なDB更新）を禁止する
    system_prompt_trailing += (
        "⚠️ 【厳守事項】\n"
        "上記の【決定事項DB】はシステム側で自動管理されます。\n"
        "あなたの回答内に「決定事項DB」のブロックを自分で書いたり、勝手に「✅ 決定事項」と宣言したりしないでください。\n"
        "あなたはあくまでUserに『提案・報告』を行う立場です。\n"
    )

    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        # [BL-075/D-047] 以前はロールバックでホワイトボードを2版前へ戻した上で「新しい提案を
        # 作成してください」と指示していたが、これは全文書き直しを誘発し、既に修正済みだった
        # 問題を無警告で再導入する原因になっていた（rollback_whiteboard撤廃と対）。
        # 現在はホワイトボードの内容をそのまま保持し（📋セクション参照）、Detectorの指摘箇所を
        # write_agreementのedits（old_text/new_text）で部分修正することを基本方針とする。
        # [BL-143] 何回目の差し戻しか・前回と同じ指摘の繰り返しかを機械的に要約し先頭へ提示する。
        # [BL-178] このブロックはsystem_prompt_trailingの最後（＝messages配列全体でも最後）
        # に配置する。「上記📋セクション」（whiteboard_text）は同じsystem_prompt_trailing内で
        # 既に前段に存在するため、位置的参照は成立する。
        _retry_label = _build_retry_situation_label(state, state.get("expert_retry_count", 0))
        system_prompt_trailing += f"""
            \n{_retry_label}
            \n⚠️ 【重要：Detectorからの差し戻し】\n
            あなたの前回の発言は、倫理違反、矛盾、リソース超過や制約違反などの重大な矛盾が検知されDetector（監査システム）により差し戻されました。\n
            ▼ 【却下されたあなたの前回の提案（※チャット履歴からは削除済）】\n
            {previous_output}\n\n
            [Detectorからの指摘事項（要修正箇所）]\n
            {state.get('constraint_issue_log', [])[-1:]} \n\n
            【対応方針（重要）】\n
            上記📋セクションに示されている現在のホワイトボードは、あなたの前回の提案の内容のままです（ロールバックされていません）。\n
            [BL-076] 該当箇所には「> 🔴 **[Detector指摘 #...]**: ...」という注釈が本文中に直接埋め込まれている場合があります。\n
            まずこの注釈を探し、指摘箇所を特定してください（見つからない場合は上記の指摘事項テキストから該当箇所を判断してください）。\n
            [BL-202] write_agreementのedits（old_text/new_text）で該当箇所のみを部分修正してください。\n
            このとき、**本文の修正と注釈の削除は必ず別々のeditsの要素に分けてください**。1つのold_textに\n
            「本文＋注釈ブロック全体」をまとめて入れると、old_textが数千字規模になり一字一句の再現に失敗して\n
            edits全体が却下されます（log/2026-08-09/2348で同一ターン内20回連続の不一致を実測）。\n
            注釈の削除は、「> 🔴 **[Detector指摘 #<ID>]**:」で始まるそのブロックだけを対象にした\n
            独立したeditsの要素として行ってください。修正の影響が他の箇所（関連する数値・前提）にも\n
            及ぶ場合は、その範囲も併せて見直し、必要であればdecision_whatによる全文更新（SUPERSEDE）を使ってください。\n
            既に正しく確定していた他の記述内容（例：以前のDetector指摘で修正済みの箇所）を、今回とは無関係な\n
            理由で元に戻さないよう特に注意してください。\n
            必ず、矛盾の内容とその理由を明示し、どのタスク・フェーズに影響があるかを具体的に指摘してください。\n
        """

    # [BL-178] system_prompt_trailingをchat_historyより後ろへ独立したsystemメッセージとして
    # 追加する。複数のrole:"system"メッセージを会話途中・末尾に挿入すること自体はBL-093の
    # 自動reasoningダイジェストで既に実績のあるパターン（新規リスクではない）。
    messages.append({"role": "system", "content": system_prompt_trailing})

    # BL-025 ②: ツールループの自問自答フェーズ（iter=2以降）では、全フェーズ・全DB agreementsを含む
    # 巨大なsystem_promptではなく、現在タスクの情報のみに絞った軽量版に差し替える。
    # [BL-178] 「視座は上から下、文脈は過去から現在」の順に並び替え、厳守事項・差し戻し情報の
    # 2ブロックを新規追加する（従来は`_query_AI_live`がloop_messages[0]をこの文字列で丸ごと
    # 置換するため、iter=2以降は差し戻し情報が完全にコンテキストから消えていた）。ただし
    # light_system_promptはloop_messages[0]への一度きりの置換に過ぎず、それ以降積み上がる
    # tool呼び出し履歴の位置には影響しないため、iter=3以降まで含めた「真に最後」はこの並び替え
    # だけでは達成できない（既知の限界、詳細はBL178_basic_design.md）。
    light_system_prompt = (
        f"あなたは有能な{expert_name}の分野の専門家です。\n\n"
        + f"【現在のタスク】\n{current_task_json}\n\n"
        f"【この値は確定済みです。再導出しないでください】\n{verified_facts_json}\n\n"
        f"【未充足の要求項目】\n{remaining_criteria_text}\n\n"
        + (f"🎯 【このタスクで特に注意すべき観点（Orchestratorより）】\n{expert_focus_guidance}\n\n" if expert_focus_guidance else "")
        + "他タスクのowns_variablesに該当する内容は新たに算出・提案しないでください。\n"
        "[BL-041] ゴールで直接与えられた絶対制約以外で、このタスク内で導出した数値は、"
        "write_agreementのconfirmed_variablesでconfidence=\"provisional\"として記録してください"
        "（他タスクの制約とまだ突き合わせが済んでいないため）。\n"
        "【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・"
        "read_project_plan・write_agreement・escalate_premise_concern・ask_user_question・"
        "web_search・web_fetch・read_reference_file・read_goal_reference・register_entity・write_entity_attribute・read_entity・gsi_geocode・"
        "gsi_get_elevation・gsi_calc_distance_bearing・calc_road_route・thinkです。\n"
        "[BL-204: 課題に登場する事物の事実はレジストリで管理する] 固有の名前を持つ実世界の"
        "対象（施設・場所・組織・路線・サービス等）についての事実は、read_entityで確認し"
        "write_entity_attributeで記録してください。レジストリが真実の源であり、成果物本文は"
        "その提示です。記憶や本文からの再構成で事実を組み立てないでください。値には必ず"
        "citations（出典）とconfidence（confirmed/provisional の2値）を添えてください"
        "——工学的仮定であることはcitationsのtype=\"expert_calculation\"で表します。"
        "**事物の名称はゴール文の表記をそのまま使い**、記憶による言い換え・略称を使わないで"
        "ください（未登録の名前は候補付きで差し戻されます）。ゴール文に無い事物を新たに"
        "発見した場合のみ、register_entityで出典を添えて登録してください。\n"
        "[BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値は"
        "read_verified_factを使い、read_entityをentity未指定の「一覧確認」目的で"
        "多用しないでください（一覧は名前のみで属性を含みません）。\n"
        "[BL-198: 実測できる地理データは実測する] 地点の標高、2点間の直線距離、住所の緯度経度、"
        "道路距離・所要時間は、上記の専用ツール（gsi_geocode→gsi_get_elevation／"
        "gsi_calc_distance_bearing／calc_road_route）で実際に取得できます。これらを推測したり、"
        "web_searchのスニペットからの間接的な言及で代用したりせず、専用ツールの実測値を使って"
        "ください。ただしgsi_calc_distance_bearingが返すのは直線距離であり道路距離ではありません"
        "——道路距離・所要時間が必要な場合はcalc_road_routeを使い、直線距離を道路距離として"
        "提示しないでください。なお、これらのツールで取得できない種類のデータ（例：道路区間単位の"
        "積雪・凍結の実測記録）まで実測値で揃えようとする必要はありません。取得できない項目は"
        "公的情報の定性的な参照と、根拠を明記した工学的仮定で扱ってください。\n"
        "[BL-203: gsi_geocodeには必ず「番地までの住所」を渡す] gsi_geocodeは住所ジオコーダで"
        "あり施設検索ではありません。施設名を入れても無視され、大字止まりで解決するとその区画の"
        "代表点が返ります（施設の実位置と数km・標高で数百m離れることがあります）。その座標を"
        "gsi_get_elevationや距離計算へ渡すと「誤った場所の正しい実測値」になります。番地までの"
        "住所を先に確認してからqueryに指定し、返却precisionが\"area_centroid\"なら施設の位置と"
        "して使わないでください。拠点名はゴール文の表記をそのまま使い、記憶で言い換えないこと。\n"
        "[BL-188] あなた自身の学習知識から導き出した回答や思考も、必ずしも正確であるとは限らず、"
        "最新の情勢（法令・相場・規制等）を反映しているとも限りません。ゴール文にない現実世界の"
        "事実（地理・費用相場・法規制等）が必要な場合は、記憶からの推測で済ませず、必ずweb_search"
        "で信頼できる一次情報を確認・裏取りしてください。ただしweb_searchはいきなり呼ばず、"
        "[BL-199/BL-200] ①read_goal_reference（開発者がこのゴール用に事前収集した参照データ）"
        "→②read_reference_file（web_fetchキャッシュ。URLキーで全run共有され、過去のrunで"
        "取得済みのページも読めます。keyword検索可）→③web_search、の順に確認してください。"
        "①②はいずれも呼び出し回数上限を消費しません。web検索結果は鵜呑みにせず一次ソース（公的統計・"
        "公式文書等）を優先し、確定値・暫定値としてconfirmed_variablesに書く際はcitations"
        "（type=\"web\", detail=<URL>等）で追跡可能な出典を明示してください。"
        "【最低限】ゴール文にない数値（単価・相場・法定基準値等）を新たに前提として置く場合、"
        "citationsを`expert_calculation`のみで済ませず、その主要な前提について最低1回は"
        "web_searchを呼んでから確定値・暫定値を書いてください。\n"
        "[BL-195: web由来の実例数値をそのまま転記しない] web_searchで、この課題と類似の実在"
        "事例（同種のデマンド交通・自動運転バス等の運行サービス）を発見した場合、その具体的な"
        "運行本数・車両台数・運賃・人員体制等の数値を、検証や再計算なしにそのまま成果物へ転記"
        "しないでください。実例はあくまで「このような設計が現実的に成立し得るか」という妥当性"
        "チェックの参考情報として扱い、成果物の数値は必ず本課題固有の制約（予算・需要マトリクス・"
        "距離・SLA）とpython_replでの計算から独自に導出してください。転記した場合、citationsに"
        "type=\"web\"を付けるだけでは不十分です——confirmed_variablesのreason_whyに、その数値を"
        "本課題の制約からどう導出したか（計算式・入力値）を必ず明記してください。実例の数値と"
        "独自算出の結果がたまたま近い値になること自体は問題ではありませんが、算出過程を示さず"
        "実例の値をそのまま使うことは認められません。\n"
        "[BL-086] ゴール文の制約そのものが真の目的と矛盾していると具体的根拠を持って判断した場合のみ、"
        "escalate_premise_concernツールで懸念を提起できます（一般的な泣き言としては使用不可、"
        "今回のacceptance_criteriaは提起後も通常通り満たすこと）。\n"
        "[BL-130] 情報不足・方向性の選択などUserにしか決められない事情で本当に前進できない場合のみ、"
        "ask_user_questionツールで質問できます（成果物の代わりにこのツールを呼ぶと、そのターンの"
        "監査・意思抽出はスキップされます。単なる確認のための多用は避けてください）。\n"
        "[BL-094: read_verified_fact/read_deliverable_fileで過去の決定と同期する] 上記【この値は"
        "確定済みです】は現在タスクに関連する確定値の一部にすぎません。read_verified_factは全"
        "フェーズ・全タスクを横断して、変数名やキーワード（例:「数量」「対象範囲」「不確定要素」）"
        "から確定値（値・理由・引用元・confidence）を検索できます。read_deliverable_fileは過去タスク"
        "の成果物全文（数値だけでなく、それがどんな前提・議論を経て確定したかという文脈）をtask_idや"
        "キーワードで読めます。[BL-104] read_project_planでは全フェーズ・全タスクの詳細"
        "（description・acceptance_criteria・depends_on・owns_variables）を確認できます。"
        "【最低限、iter=1で一度は、このタスクに関連しそうなキーワードで"
        "read_verified_factを呼び、他タスクで既に確定・仮定された値が無いか確認してから作業を"
        "始めてください】。確認せずに自分で新しい数値を仮定すると、他タスクの確定値と矛盾する"
        "リスクがあります。思考の途中で「これは他タスクで既に扱われていたかもしれない」という"
        "気づきがあれば、その都度これらのツールで確認し、独自の仮定で上書きしないでください。\n"
        "[BL-093] thinkツールで検討過程を残せます。自然に考えた理由づけの生文章は、thinkを使わ"
        "なければ次のiterationには引き継がれません（tool_callsの記録だけが残ります）。thinkを"
        "呼ぶと、その理由づけは次回以降のtool結果として全履歴ごと返され、雪だるま式に引き継がれ"
        "ます。todoに確認すべき論点をリストアップし、action/decided/why（却下案があれば"
        "rejected/rejected_why）を書いてください。他ツールと同一応答内でまとめて呼んでも単独で"
        "呼んでも構いません。" + _THINK_TRAILER_SENTENCE + "\n"
        "数値的根拠は python_repl ツールで検算し、暗算での提示は禁止します。\n"
        # [BL-178] 厳守事項（新規）。フル版の文言「上記の【決定事項DB】は…」は、軽量版には
        # 決定事項DBブロック自体が存在しないため、位置的参照の無い独立文へ書き換える。
        "⚠️ 【厳守事項】決定事項DBはシステム側で自動管理されます。あなたの回答内でDBのブロックを"
        "自分で書いたり、勝手に「決定事項」と宣言したりしないでください。あなたはあくまでUserに"
        "『提案・報告』を行う立場です。\n"
        f"\n[R4] {whiteboard_text}\n"
    )
    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        # [BL-178] Detectorからの差し戻し情報（新規）。フル版と異なりprevious_output全文は
        # 再掲しない（軽量版の「軽量」という目的に反するため。iter=2以降はExpert自身が今回の
        # 応答を推敲中であり、「何を直すべきか」の要点があれば足りる。ホワイトボード本文は
        # 直前で既に提示済みのため[BL-076]インライン注釈との突き合わせも可能）。
        light_system_prompt += (
            f"\n{_retry_label}\n"
            "⚠️ 【重要：Detectorからの差し戻し】あなたの前回の発言はDetectorにより差し戻されました。"
            f"[Detectorからの指摘事項（要修正箇所）]\n{state.get('constraint_issue_log', [])[-1:]}\n"
            "上記のホワイトボード本文には「> 🔴 **[Detector指摘 #...]**」という注釈が埋め込まれて"
            "いる場合があります。まずこの注釈を探し、write_agreementのedits（old_text/new_text）で"
            "該当箇所のみを部分修正してください。\n"
            "[BL-202] このとき、本文の修正と注釈の削除は必ず別々のeditsの要素に分けてください。"
            "1つのold_textに「本文＋注釈ブロック全体」をまとめて入れると、old_textが数千字規模になり"
            "一字一句の再現に失敗してedits全体が却下されます。注釈の削除は、"
            "「> 🔴 **[Detector指摘 #<ID>]**:」で始まるそのブロックだけを対象にした独立した"
            "editsの要素として行ってください。\n"
        )

    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "expert"
    _CURRENT_TASK_ID = state.get("current_task_id", "")
    _reset_think_scratchpad()  # [BL-093]
    return query_AI(messages, client=client_expert, model=model_expert, label=f"Expert:{expert_name}",
                     tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, READ_WHITEBOARD_EXCERPT_TOOL, READ_PROJECT_PLAN_TOOL, WRITE_AGREEMENT_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, ASK_USER_QUESTION_TOOL, WEB_SEARCH_TOOL, WEB_FETCH_TOOL, READ_REFERENCE_FILE_TOOL, READ_GOAL_REFERENCE_TOOL, REGISTER_ENTITY_TOOL, WRITE_ENTITY_ATTRIBUTE_TOOL, READ_ENTITY_TOOL, GSI_GEOCODE_TOOL, GSI_GET_ELEVATION_TOOL, GSI_CALC_DISTANCE_BEARING_TOOL, CALC_ROAD_ROUTE_TOOL, THINK_TOOL], light_system_prompt=light_system_prompt, state=state)


#def call_detector(goal: str, user_input: str, expert_output: str, decisions: list[Decision], current_phase: dict) -> dict:
def call_detector(state: LineageState, target_role: str, review_mode: str = "task_output") -> dict:
    """【SLM要約】
    Determining the rigor of auditing criteria based on whether the input is a user instruction/review or an agent proposal, then using an LLM to assess both safety risks and constraint adherence in the conversation history.
    [BL-126 Stage B] review_mode="goal_change"（state["goal_revision_pending_review"]時のみ）は、
    第1段（ドメイン妥当性レビュー）のdomain_role_instructionだけを専用の判断基準に差し替える
    直交した軸（§13.1: 切替のトリガーは1つの明確なフラグの読み取りのみ）。第2段の数値監査パス
    等、既存のロジックには一切影響しない。
    """
    # [BL-096] write_issue等の権限チェックはグローバルの_CURRENT_CALLER_ROLEに依存するため、
    # 第1段（ドメイン妥当性レビュー）が実行される前にここで設定する必要がある。
    # 従来はここが未設定のまま第1段が走り、直前ノード（例: expert）のroleが漏れて
    # write_issue(CREATE)が誤って権限エラーになる実バグがあった（ドライラン2026-07-27/1551で検出）。
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID, _CURRENT_PHASE_ID
    _CURRENT_CALLER_ROLE = "detector"
    _CURRENT_TASK_ID = state.get("current_task_id", "")
    _CURRENT_PHASE_ID = state.get("current_phase", {}).get("phase_id", "")

    # [BL-164] 従来はSELECT *の生行（internal_thought_process列込み、数千字規模）をそのままJSON化
    # していたため、既にsupersede済みのホワイトボード版への一字一句引用がinternal_thought_process
    # 内に残ったまま次のDetectorへ渡り、それを最新内容と誤認してverify_whiteboard_excerptを
    # 無駄打ちし続けMAX_TOOL_ITERを浪費する実害を確認した（同一run内で2回再現）。
    # thought_process_audit（本ターンのExpert/User AI自身の思考過程を専用に監査する別ブロック）
    # と役割が重複する上に本質的にsupersede非対応なため、who/what/whyの要約のみに絞る。
    _recent_decisions_raw = get_decisions_from_db(get_active_conn(), state["run_id"])[-2:]
    recent_decitions = json.dumps(
        [{"who": d.get("who", ""), "what": d.get("what", ""), "why": d.get("why", "")} for d in _recent_decisions_raw],
        ensure_ascii=False,
    )
    # [BL-062] Detectorがmajor判定を出した際、対象のtopicをtarget_topicとしてSUPERSEDEできるよう、
    # 既存の【決定事項DB】（topic名・ID）を提示する。従来はDetectorに一切見えておらず、
    # write_agreementの権限（status='Rejected'）はあってもtarget_topicを指定する材料がなかった。
    agreements_text = _build_agreements_context_from_db(get_active_conn(), state["run_id"])
    recent_history = state["chat_history"][-2:]
    history_text = "\n".join([f"{'[User]' if m['role']=='user' else '[AI]'}\n {m['content']}" for m in recent_history])
    goal = state["goal"]
    current_task = _get_current_task(state)
    acceptance_criteria = current_task.get("acceptance_criteria", [])
    criteria_text = "\n".join(f"{i}. {c}" for i, c in enumerate(acceptance_criteria)) or "(現在のタスクにacceptance_criteriaが定義されていません)"

    # [R4] Deliverableが差分パッチ化されている場合、直近の会話（差分の要約のみ）だけでは
    # 編集後の完全な内容を検証できないため、現在タスクの最新ホワイトボード版を提示する。
    _current_phase_id = state.get("current_phase", {}).get("phase_id", "")
    _current_task_id = current_task.get("task_id", "")
    _whiteboard = get_latest_whiteboard(get_active_conn(), state["run_id"], _current_phase_id, _current_task_id) if _current_task_id else None
    whiteboard_block = (
        f"【R4: 現在タスクの成果物・最新ホワイトボード Ver.{_whiteboard['version']}（編集後の完全版）】\n{_whiteboard['content']}\n\n"
        if _whiteboard else ""
    )

    # [BL-082] 他タスクから本タスクへの申し送り事項。「既に先送り済みの論点はmajorにしない」
    # という以下の緩和ロジックが、直近2ターンの会話窓だけに依存せず判断できるようにする。
    _deferred_notes = _get_deferred_notes_text(get_active_conn(), state["run_id"], _current_phase_id, _current_task_id)
    deferred_notes_block = f"{_deferred_notes}\n" if _deferred_notes else ""

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

    # [BL-091] 今回評価対象のターンで、write_agreementが実際に成功したかどうかをDetectorに
    # 明示する。最終iterationでツールが強制的に外された際、モデルが独自のツール呼び出し風の
    # 疑似構文（例: DeepSeek系の<｜DSML｜...｜>疑似XML）をそのまま平文で出力することがあり、
    # これは実際には一切実行されていないにもかかわらず、更新が完了したかのような説得力のある
    # 文面になりうる（実ドライラン log/2026-07-25/1913 で確認。Detectorがこれを鵜呑みにし
    # 「物理的矛盾は解消される」と誤って承認、Decision Extractorも虚偽のUPDATEをDBに記録した）。
    _wrote_agreement_this_turn = state.get(
        "user_wrote_agreement" if target_role == "user" else "expert_wrote_agreement", False
    )
    write_agreement_status_block = (
        f"【BL-091: 今回のターンのwrite_agreement実行結果】write_agreementの呼び出しは"
        + ("少なくとも1回成功しました。\n" if _wrote_agreement_this_turn else
           "今回のターンでは一度も成功していません。\n"
           "[BL-119: 罠] これはあくまで「今回のターン内」の話であり、過去のターンで既に登録済みの"
           "場合はこれが0でも正常です。相手が「更新した」「登録した」と主張していたら、まず【R4: 現在"
           "タスクの成果物・最新ホワイトボード】や既存のDecision/Agreementの内容を実際に確認し、"
           "主張されている内容と一致するかで判定してください。内容が一致するなら、それは過去のターン"
           "で既に反映済みという正常な状態であり、虚偽ではありません。今回success=0という理由だけで"
           "即constraint_issue=\"major\"にせず、必要ならread_deliverable_fileで過去の登録内容を確認"
           "してから判断してください。内容を確認した上でなお主張と食い違う場合のみ"
           "constraint_issue=\"major\"としてください（ツール呼び出し失敗の見落とし、または虚偽の"
           "完了報告です）。\n")
    )

    # [R5 F-2.1] Expert/User AIのreasoning（思考過程）を提示し、最終出力だけでなく思考過程自体も
    # 監査対象にする。プロバイダがreasoningを返さない場合は「(思考ログ取得不可)」を表示する。
    _reasoning_source = state.get("expert_last_reasoning" if target_role == "expert" else "user_last_reasoning", "")
    thought_process_audit = f"""
【思考プロセス監査（★R5追加）】
以下はExpert/User AIの内部思考過程（internal_thought_process）です。
最終出力の内容だけでなく、この思考過程も確認してください。
- 「計算ツールを使っていないのに適当な数字を出している」
- 「都合の悪い制約から意図的に目を逸らして結論を急いでいる」
このようなAIの事後正当化（取り繕い）が見られる場合、重度のハルシネーションと
判定して強制差し戻し（major）としてください。

【重要な限界】ただし、思考ログ内で正しく検算していたとしても、それを読むあなた自身も
LLMである以上、暗算による検証には誤りのリスクが伴います。数値的主張の妥当性は、
本監査だけに依拠せず、必ず上記のBL-033機械的検算記録と突き合わせて判断してください。

【Expert/User AIの思考過程】
{_reasoning_source or "(思考ログ取得不可)"}
"""

# [BL-049/BL-054] 検算（数値監査）とは別視点のドメイン妥当性レビュー用instruction。
    # F-2.6検算ゲート導入以降、role_specific_instructionが「検算結果」を主なmajorトリガーに
    # しているため、Detectorの注意力が数値の辻褄合わせに強く誘導され、法規制・物理的運用可能性
    # 等の非数値的な論点（法定のシフト・休憩要件、予備設備の欠如等）が見落とされる事故が実機
    # ドライランで確認された（log/2026-07-22/2336）。数値監査パスとは別のLLM呼び出しとして
    # ドメイン妥当性レビューを独立実行し、両者の判定を統合する（2段構成、D-041）。
    # [BL-054] さらに、ドメインレビューを検算より先に実行する順序へ変更した。検算を先に
    # 済ませてしまうと「数値は合っている」という結果に引きずられ、そもそもの前提・設計
    # （設備・人員の規模・配置等）が現実的かというドメイン評価が後手になり軽視されやすいため、
    # 前提・設計そのものの妥当性確認を最初に行う（ユーザー指摘、2026-07-23）。
    if review_mode == "goal_change":
        # [BL-126 Stage B/§5] revise_goal（反応的経路・Essence Dialogue収束後の双方）による
        # ゴール文改定そのものを評価する専用モード。通常の成果物レビューとは判断基準が異なるため、
        # domain_role_instructionのみをこの4項目に完全に差し替える（§13.3: 排他的なelif分岐）。
        # [BL-162] 判定基準1（旧文の包含確認）にはold_goal_text自体が必要。従来はここに埋め込まず
        # Detector自身にread_verified_fact等での探索を委ねていたが、旧ゴール文を読める経路が
        # どこにも存在しなかったため必ず空振りしていた（実ログで5回連続not_found確認）。
        # generate_user_utterance_nodeが橋渡しするstate["goal_revision_old_text"]を直接埋め込む。
        _old_goal_text = state.get("goal_revision_old_text", "") or "(旧ゴール文を取得できませんでした)"
        domain_role_instruction = (
            "評価対象：User(発注者)によるゴール文の改定（revise_goalツール経由）。"
            "これは通常の成果物レビューではありません。以下の判断基準でのみ評価してください：\n"
            f"【改定前のゴール文（旧文）】\n{_old_goal_text}\n\n"
            f"【改定後のゴール文（新文、System Goalとして下記にも再掲）】\n{goal}\n\n"
            "1. 旧文が置換ではなく追記として保持されているか（上記の新文の中に、上記の旧文の内容が"
            "包含されているか。旧文を探すためのツール呼び出しは不要です、上記に既に提示済みです）。\n"
            "2. 理由づけ（reason_why）が、提起された懸念の重大さに見合っているか。\n"
            "3. 変更が提起された懸念の範囲内に収まっているか（無関係な制約まで書き換えていないか、"
            "スコープ逸脱がないか）。\n"
            "4. 新しいゴール文の数値的な最適性そのものは評価しないでください"
            "（それは後続の通常タスク遂行の中で検証されます）。過剰な監査は不要な差し戻しを"
            "招くため、この観点は明示的に評価対象から除外します。\n"
            "[罠] 今回の監査対象はこの直近の改定のみです。改定後の文言が過去の別の合意事項と"
            "重複・関連していても、それ自体は正常であり問題ではありません。"
        )
    elif target_role == "user":
        domain_role_instruction = (
            "評価対象：User(発注者)の発言。数値の検算は既に別プロセス（数値監査）で完了しています。"
            "あなたはそれとは別の視点で、Userが承認・指示しようとしている計画に、"
            "数式としては辻褄が合っていても現実世界では成立しないドメイン的な問題"
            "（法定の休憩・シフト要件、物理的な運用可能性、予備・冗長性の欠如、"
            "安全規制等）が残っていないかを確認してください。"
            "Userがそれを見落として安易に承認・指示している場合はmajorとしてください。"
        )
    else:
        domain_role_instruction = (
            "評価対象：Agent(作業者)の発言。数値の検算は既に別プロセス（数値監査）で完了しています。"
            "あなたはそれとは別の視点で、Agentの提案の前提・結論が現実世界で本当に成立するか"
            "（物理的な実現可能性、法定の労働・安全法規制、予備・冗長性の欠如、安全性の運用面）を"
            "評価してください。数式の辻褄を合わせるためだけに、元データに根拠のない内訳・仮定を"
            "その場ででっち上げていないか（例：制約を満たすよう逆算した都合の良い数値分割）も、"
            "特に注意して確認してください。"
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
                「発注者としてのレビュー不足（妥協）」とみなし、**容赦なく major を出力し、Userに対して『承認を取り消し、Agentに厳しく修正を要求せよ』と差し戻してください。**\n\n
            3. 【BL-181: 次タスクへの移行時の宿題残し】: Userが次のタスクへの移行を指示している場合、read_issuesで現在のタスク（{_current_task_id}）に紐づく\n
                severity='major'またはstatus='escalated'のissueが残っていないか確認してください。\n
                残っている場合、read_issuesが返す各issueのdefer_to_task_id列を確認してください。**defer_to_task_idが既に\n
                何らかのtask_idへ設定済みであれば、それが今回の発言より前のラウンドで記録されたものであっても、\n
                正式に先送り済みとみなし、このissueを理由にmajorとしないでください**（write_issue(DEFER)は仕様上statusを\n
                'escalated'のまま変更しないため、defer_to_task_idの有無だけが「先送り済みか」の判断材料です。[BL-207]\n
                「今回の発言内で対応されていなければ」という基準は、既に先送り済みのissueにも毎回のラウンドで再度DEFERの\n
                実行を要求してしまい、正しく先送りされているのに無限に差し戻し続ける不具合の原因でした）。\n
                defer_to_task_idが未設定のまま残っているissueがある場合のみ、\n
                「現タスクの重大な懸念を未解決のまま次タスクへ進めようとしている」とみなし、**major を出力し、\n
                『次タスクへ進む前に、残存issueをRESOLVEまたはDEFERせよ』と差し戻してください。**\n
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



    # [BL-115] domain_prompt（ドメイン妥当性レビュー）とprompt（数値監査）は同一関数内で
    # 別々に構築される2つのプロンプトだが、気づき欄・issue引き継ぎの説明が重複していたため、
    # 完全に同一の部分だけをローカル変数に集約する（関数外の共有定数と違い、この関数内
    # 限定の重複のため、モジュールレベルではなくローカルに留める）。
    _observations_block = (
        "【BL-051軽量版: 気づき欄】constraint_issueの判定（none/minor/major）には至らないが、"
        "思考の過程で気になった点・将来的なリスクの芽・引っかかった前提などがあれば、"
        "'observations'に自由記述で書き残してください（無ければ空文字でよい）。"
        "これは判定を左右するものではなく、後続の議論のために参考情報として引き継がれます。\n\n"
    )
    _issue_carryover_prefix = (
        "[BL-096: write_issue/read_issuesで軽微な懸念を後続タスクへ引き継ぐ] 'observations'に書く"
        "内容のうち、今回のターンだけでなく後続タスクでも参照されるべきと判断した懸念は、"
        "write_issue(action_type=\"CREATE\", topic=\"<固定の識別文字列>\", severity=\"minor\", "
        "description=\"...\")を呼んで永続化してください。既に同じ懸念を起票済みかもしれない場合は、"
        "先にread_issuesで確認してください（解決済みならresolution_noteが見えるので再登録は不要です）。"
        "[BL-140] thinkツールのscratch_concernsは、このツール呼び出しループの中だけで消える"
        "一時メモであり、後続タスクへは一切引き継がれません。持ち越したい懸念をscratch_concerns"
        "に書くだけで満足せず、必ずwrite_issueで記録してください。"
    )

    # [BL-123] Detectorはcall_expert/generate_user_utteranceと異なり、issue_logのescalated行
    # （BL-103のpin）を一切受け取っておらず、他ロールが既に折り込み済みの懸念を知らないまま
    # 独立に判定してしまっていた。ドメイン妥当性レビュー（前提・実現可能性等）と意味的に
    # 最も親和性が高いためPass 1にのみ注入する（Pass 2は算術検算に専念する設計のため対象外）。
    escalation_pin = _build_escalation_pin_text(get_active_conn(), state["run_id"], state.get("current_task_id", ""), state.get("round_count", 0))
    escalation_pin_block = (
        f"【⚠️エスカレーション中の懸念（要対応、issue_log）】\n{escalation_pin}\n\n" if escalation_pin else ""
    )
    # [BL-194] DEFER済み（別タスクへの受け皿が確定済み）の懸念は非強制トーンで分離する。
    # Detector専用の1文を添える：担当タスクが別に確定している懸念を理由にmajor判定しない
    # こと——BL-123がpinを導入した目的（他ロールが折り込み済みの懸念を知る）は保ちつつ、
    # 逆方向の誤用（スコープ外を理由とした差し戻し）を塞ぐ。log/2026-08-08/1514で、
    # task_2_2スコープの車両台数issueを理由にDetectorがtask_2_1をmajor差し戻しし続けた
    # churnの再点火経路への直接の対処。
    deferred_issue_pin = _build_deferred_issue_pin_text(get_active_conn(), state["run_id"], state.get("current_task_id", ""))
    deferred_issue_pin_block = (
        f"【📤 対応予定が確定済みの懸念（参考・現タスクでは対応不要、issue_log）】\n{deferred_issue_pin}\n"
        "以下は担当タスクが別に確定している懸念です。現在タスクの成果物にこれらが反映されていない"
        "ことを理由にmajorと判定しないでください（BL-194）。\n\n"
        if deferred_issue_pin else ""
    )
    # [BL-194] ACKNOWLEDGE中（現在タスクの責務であり対応中）の懸念も前向きなトーンで表示する。
    acknowledged_issue_pin = _build_acknowledged_issue_pin_text(get_active_conn(), state["run_id"], state.get("round_count", 0))
    acknowledged_issue_pin_block = (
        f"【🛠 現在のタスクで対応中の懸念（issue_log）】\n{acknowledged_issue_pin}\n\n" if acknowledged_issue_pin else ""
    )

    # [BL-054] 第1段: ドメイン妥当性レビューを検算より先に実行する。
    # 検算を先に済ませると「数値は合っている」という結果に引きずられ、そもそもの前提・設計
    # （設備・人員の規模・配置等）が現実的かというドメイン評価が後手・軽視されやすいため、まず前提・
    # 設計そのものの妥当性を検算とは無関係に確認する（ユーザー指摘、2026-07-23）。
    # この時点では数値監査パスはまだ実行していないため、その結果には言及しない。
    # [BL-104] プロンプトキャッシュのヒット率向上のため、実行中いつでも内容が同一の固定指示文
    # （判定基準・気づき欄/write_issue/think/ツール一覧の説明）を先頭付近にまとめ、ターンごとに
    # 変わる動的な内容（Freeze状況・現在タスク・ホワイトボード・今回評価するやり取り本文）は
    # 末尾側に配置する（call_expert/generate_user_utteranceと同じ原則）。「上記ホワイトボードの
    # 本文から」という位置的参照を持つBL-076ブロックのみ、whiteboard_blockの直後という相対位置を
    # 維持し並び替えの対象外とする。domain_role_instructionはtarget_role単位でしか変わらない
    # （ターンごとには変わらない）ため、固定指示文グループの直後に配置する。
    domain_prompt = (
        f"あなたはプロジェクトにおける議論の「ドメイン妥当性レビュー」担当監査人です。\n"
        f"あなたの役割は数値の検算（計算が合っているか）ではありません。数値の機械的検算は"
        f"この後、別の監査パスで独立して行われるため、ここでは検算する必要はありません"
        f"（結果に明らかな違和感がある場合を除き、python_replでの再計算は不要です）。\n"
        f"まず最初に、そもそもの前提・設計（設備・人員の規模、シフト、速度・距離の設定など）"
        f"自体に現実世界で無理がないかを確認してください。検算で数式のつじつまが合っていても、"
        f"前提そのものが現実的に成立しなければ意味がありません。\n\n"
        f"{domain_role_instruction}\n\n"
        f"【判定基準（重要：情報不足を理由にmajorにしないこと）】\n"
        f"- major: 与えられた情報だけから、具体的かつ明白なドメイン上の矛盾・違反が特定できる場合のみ"
        f"（例：明記された労働時間・人数から法定休憩が物理的に取得不可能と計算できる、"
        f"明記された速度・距離から制約が数式上どうやっても満たせないのに満たしたと偽装している、等）。\n"
        f"- minor: 明白な矛盾とまでは言えないが、内訳・前提の説明が薄く今後の精査が望ましい場合、"
        f"または軽微な懸念にとどまる場合。\n"
        f"- none: 矛盾・懸念なし。\n"
        f"シナリオに明記されていない詳細（例：具体的な人数構成、勤務シフトの詳細）が不明であること"
        f"自体は、それだけでは矛盾ではありません。**「情報が不足していて確認できない」ことをmajorの"
        f"根拠にしてはいけません**。majorにする場合は、与えられた情報の範囲内で矛盾を具体的に指摘できる"
        f"ことが必須です。\n\n"
        f"{_observations_block}"
        f"{_issue_carryover_prefix}\n\n"
        f"【BL-093】必要であれば、thinkツールで検討過程を書き残しても構いません。\n\n"
        f"[BL-188] Expertの主張がcitations（引用元）付きでweb由来の情報を根拠にしている場合、"
        f"read_reference_fileでそのキャッシュ本文を確認し、実際に主張と一致しているか（数値の"
        f"改変・拡大解釈がないか）を検証できます。\n\n"
        f"[BL-188] 【根拠の実在性チェック（重要）】数値・相場・法令・規制等の主張について、"
        f"内部の計算整合性だけでなく「その前提数値自体が現実の値として妥当か」も監査してください。"
        f"citationsが`expert_calculation`や`prior_agreement`のみで、外部の一次情報（`type=\"web\"`）"
        f"による裏付けが一切ない主張のうち、あなた自身の知識でも真偽の確信が持てないもの"
        f"（例：人件費相場、法定基準値、業界標準）があれば、web_searchで実際に調べて検証して"
        f"ください（Expertと同じくweb_fetchで一次資料を直接確認できます）。ただしweb_searchは"
        f"いきなり呼ばず、[BL-199/BL-200] ①read_goal_reference（開発者事前収集の参照データ）"
        f"→②read_reference_file（web_fetchキャッシュ。URLキーで全run共有、過去のrunで取得済みの"
        f"ページも読めます）→③web_search、の順に確認し、無駄な重複呼び出しを避けてください"
        f"（①②は呼び出し回数上限を消費しません）。検証の結果、前提数値が実態と乖離していると判明した場合は、それ自体を"
        f"constraint_issueの根拠にしてください（自己参照のみの前提を鵜呑みにしないこと）。\n\n"
        f"[BL-195: 実例からの無derivation転記チェック] Agentの主張がcitations type=\"web\"で"
        f"実在の類似事例（デマンド交通・自動運転バス等の運行サービス）を出典としている場合、"
        f"その数値が本課題固有の制約（予算・需要データ・距離・SLA）から独自に導出された形跡が"
        f"あるか（reason_why・python_calls_blockでの計算過程）を確認してください。導出過程を"
        f"示さず実例の数値をそのまま転記しているだけの場合は、それ自体をminor以上の指摘対象に"
        f"してください（「実例のcitationsはあるが、本課題の制約からの再計算過程が示されていない」"
        f"のように具体的に指摘すること）。\n\n"
        f"[BL-198: 地理データの主張は専用ツールで検算できる] Agentが提示した標高・2点間の距離・"
        f"緯度経度・道路距離は、gsi_geocode／gsi_get_elevation／gsi_calc_distance_bearing／"
        f"calc_road_routeで実際に取得して照合できます。値が大きく食い違う場合や、実測できるはず"
        f"の値が推測値・web検索スニペットからの間接的な引用に留まっている場合は指摘対象です。"
        f"特に、直線距離（gsi_calc_distance_bearing）を道路距離として提示していないかを確認して"
        f"ください。ただし、これらのツールで取得できない種類のデータ（例：道路区間単位の積雪・"
        f"凍結の実測記録）が実測値で示されていないことを理由にmajorとしないでください——それらは"
        f"公的情報の定性的な参照と、根拠を明記した工学的仮定で扱われていれば妥当です。\n\n"
        f"[BL-204: 成果物の事実をレジストリと突き合わせる] この課題に登場する事物"
        f"（固有の名前を持つ実世界の対象）についての事実は、read_entityでレジストリの記録を"
        f"取得できます。成果物本文に書かれた値がレジストリの記録と食い違っていないか、"
        f"レジストリに無い事実が根拠なく本文へ現れていないかを確認してください。"
        f"特に、**ゴール文に登場しない事物名が成果物に現れている場合**は重点確認対象です"
        f"（記憶による言い換えで、実在するが無関係な対象の情報を引き込んでいる恐れがあります）。"
        f"また、住所と座標の両方が記録されている事物は、verify_entity_geoで住所を引き直して"
        f"座標の妥当性を検算できます。\n"
        f"[BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値の検算は"
        f"read_verified_factを使ってください。\n\n"
        f"[BL-203: 拠点の名称と座標の由来を確認する] 実測値は「正しい場所を測った」場合にのみ"
        f"正しく、誤った座標を測れば「誤った場所の正しい実測値」になります。これは推測値より"
        f"気づきにくいため、次の2点を重点確認してください。①**拠点の名称がゴール文の表記と"
        f"一致しているか**（記憶による別名・類似名への言い換えは、実在する別の施設の情報を"
        f"引き込む原因になります）。②**座標がその施設の住所から得られたものか**"
        f"（gsi_geocodeは住所ジオコーダで施設名を無視するため、「◯◯町 △△病院」で引くと"
        f"大字の代表点が返ります。標高が周辺の市街地と不自然に食い違う拠点があれば、"
        f"番地までの住所でgsi_geocodeを引き直して照合してください）。\n\n"
        f"【重要】あなたが使えるツールはread_verified_fact・read_deliverable_file・"
        f"write_agreement・verify_whiteboard_excerpt・write_issue・read_issues・"
        f"web_search・web_fetch・read_reference_file・read_goal_reference・read_entity・verify_entity_geo・gsi_geocode・"
        f"gsi_get_elevation・gsi_calc_distance_bearing・calc_road_route・thinkです。"
        f"{_THINK_TRAILER_SENTENCE}\n\n"
        f"{_get_frozen_agreements_text(get_active_conn(), state['run_id'])}"
        f"【BL-086: 🔒Freeze済み項目の扱い】上記に🔒が付いている項目があれば、それは人間の発注者が"
        f"既に審議の上で承認した意図的な例外です。同じ論点をmajor/minorの根拠にしないでください"
        f"（ただし別の新しい問題点はこれまで通り厳格に評価してください）。\n\n"
        f"{escalation_pin_block}"
        f"{deferred_issue_pin_block}"
        f"{acknowledged_issue_pin_block}"
        f"System Goal: {goal}\n"
        f"{_get_goal_essence_text(get_active_conn(), state['run_id'])}\n"
        f"[BL-087 Stage4] 上記【🎯 本質】に照らして、数値・条件設定自体は妥当でも本質から"
        f"乖離していないか（手段の細部の帳尻合わせに終始し、本来達成すべきことを見失っていないか）"
        f"も確認してください。乖離があればconstraint_issueをminor以上に引き上げる根拠にできます。\n\n"
        f"【現在タスクのacceptance_criteria】\n{criteria_text}\n\n"
        f"{whiteboard_block}"
        f"【BL-076: 指摘箇所の引用】constraint_issueがminor/majorの場合、上記ホワイトボードの本文から、"
        f"指摘対象の箇所を一字一句そのまま（改変・要約せず）1〜2文だけ引用し'target_excerpt'に"
        f"入れてください（ホワイトボードへの注釈挿入に機械的に使うため、正確な引用が必須です）。"
        f"noneの場合や、ホワイトボードが存在せず引用できない場合は空文字にしてください。\n\n"
        f"{write_agreement_status_block}\n"
        f"{deferred_notes_block}"
        f"{_get_task_focus_companion_text(state)}"
        f"{_build_task_focus_state_text(state)}"
        f"{_build_task_focus_transition_notice(state)}"
        f"[BL-191] このタスクが発注者の判断で一時的に再検討中（フォーカス切替中）である場合、"
        f"過去に承認済みであったことを理由に差し戻さないでください。判断すべきは、今回の"
        f"再提出内容が切替の理由（reason）に応えているかどうかです。\n"
        + (
            f"[BL-191/バグ④対策] 発注者が今回のターンでschedule_task_focusを呼び、"
            f"decision_type={state.get('pending_task_redirect', {}).get('decision_type', '')}, "
            f"reason={state.get('pending_task_redirect', {}).get('reason', '')}"
            f" というスケジューリング判断を行いました（まだ適用前）。この判断自体が妥当か"
            f"（理由が具体的か、対象タスクが本当に影響を受けているか）も判定の一部としてください。"
            f"ただしこれは監査対象の一部であり、機械的にmajor/minorを強制するものではありません。\n"
            if target_role == "user" and state.get("pending_task_redirect") else ""
        )
        + f"【今回評価するターンのやり取り】\n{history_text}\n\n"
        f'Return ONLY JSON: {{"constraint_issue": "none/minor/major", "comment": "ドメイン妥当性レビューの判定理由", "target_excerpt": "指摘対象のホワイトボード本文からの一字一句引用(無ければ空文字)", "observations": "気づき・懸念（自由記述、無ければ空文字）"}}'
    )
    _reset_think_scratchpad()  # [BL-093]
    domain_parsed, domain_parse_failed = _query_and_parse_with_retry(
        domain_prompt, client=client_detector_domain, model=model_detector_domain, label="Detector (Domain Review)",
        tools=[READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, VERIFY_WHITEBOARD_EXCERPT_TOOL, WRITE_ISSUE_TOOL, READ_ISSUES_TOOL, WEB_SEARCH_TOOL, WEB_FETCH_TOOL, READ_REFERENCE_FILE_TOOL, READ_GOAL_REFERENCE_TOOL, READ_ENTITY_TOOL, VERIFY_ENTITY_GEO_TOOL, GSI_GEOCODE_TOOL, GSI_GET_ELEVATION_TOOL, GSI_CALC_DISTANCE_BEARING_TOOL, CALC_ROAD_ROUTE_TOOL, THINK_TOOL],
        fallback={"constraint_issue": "none", "comment": "", "target_excerpt": "", "observations": ""},
        state=state,
    )
    if domain_parse_failed:
        print("🚨 [Detector] ドメイン妥当性レビューのJSON判定取得に失敗しました。フェイルクローズ(major)します。")
        domain_constraint_issue = "major"
        domain_comment = "(ドメイン妥当性レビューのJSON解析失敗のためフェイルクローズしました)"
        domain_target_excerpt = ""
        domain_observations = ""
    else:
        print(f"【Detectorの判定結果(JSONパース後・ドメイン妥当性レビュー)】\n{domain_parsed}\n")
        domain_constraint_issue = domain_parsed.get("constraint_issue", "none")
        if domain_constraint_issue not in ("none", "minor", "major"):
            domain_constraint_issue = "none"
        domain_comment = domain_parsed.get("comment", "")
        domain_target_excerpt = domain_parsed.get("target_excerpt", "") or ""
        domain_observations = domain_parsed.get("observations", "") or ""

    # [BL-054] 第2段: 数値監査（検算）パス。先に実施したドメイン妥当性レビューの結果を
    # 提示し、前提そのものに既に指摘があるかを踏まえた上で検算させる。
    domain_findings_block = (
        f"【先行して実施したドメイン妥当性レビューの結果】constraint_issue={domain_constraint_issue}, "
        f"comment={domain_comment}\n"
        f"この前提・設計の妥当性レビュー結果を踏まえた上で、以下の数値の機械的検算を行ってください。"
        f"レビューで前提自体に矛盾が指摘されている場合、その前提を鵜呑みにした検算だけで"
        f"none/minorとせず、関連する数値評価にもその点を反映してください。\n\n"
    )

    # [BL-104] プロンプトキャッシュのヒット率向上のため、domain_promptと同じ原則で並び替える:
    # 固定指示文（軸1/軸2の定義・役割別指示・検算ゲート・判定ブレ防止・気づき欄/BL-079/BL-094/
    # BL-093/BL-096/ツール一覧の説明）を先頭、ゴール文（実行中はほぼ不変）をその次、タスク単位
    # でしか変わらないacceptance_criteriaをその次、ターンごとに変わる動的な内容（ドメインレビュー
    # 結果・python_repl記録・write_agreement結果・思考過程監査・決定事項DB・ホワイトボード・
    # 申し送り事項・今回の対話本文）を末尾に配置する。「上記の」「上記DB」「上記ホワイトボードの
    # 本文から」という位置的参照を持つthought_process_audit（BL-033連携）・BL-086・BL-062・
    # BL-076の各ブロックのみ、参照先の直後という相対位置を維持し並び替えの対象外とする。
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

        f"【判定のブレ防止（3回多数決方式）】constraint_issueの判定（特にminorとmajorの境界）で"
        f"結論が変わったり迷ったりする場合、同じ論点を無限に再検討し続けないでください。"
        f"その論点について、独立した判定を意識的に3回だけ行い（1回目・2回目・3回目、それぞれ短く"
        f"「trial1: minor」のように結論だけ明記すればよく、毎回長い理由の再展開は不要です）、"
        f"3回のうち多数だった結論を最終的なconstraint_issueとして採用してください。"
        f"3回分の判定が出た時点で、それ以上の再検討・迷いは禁止します。\n\n"
        f"【同じ計算を繰り返さない（重要）】上記の判定ブレ防止とは別に、同一の数値検算"
        f"（例:「この合計は制約内か」）をpython_replで何度も繰り返さないでください。"
        f"各検算は2回程度で十分です。ツール呼び出しの回数には上限があり、新しい論点が無いまま"
        f"「念のため再確認」を重ねると、上限到達時に強制的に打ち切られたテキスト応答としてJSONを"
        f"一度に出力せざるを得なくなり、出力が途中で切れるリスクがあります。\n\n"

        f"{_observations_block}"
        f"【BL-079: 引用前に必ずverify_whiteboard_excerptで検証】target_excerptを確定する前に、"
        f"必ずverify_whiteboard_excerptツールでその引用が一意に一致するか確認してください。"
        f"ok=falseが返った場合は、そのままにせず、示された件数（完全一致/緩い一致）を参考に"
        f"引用を長く・具体的にする等調整して再度呼び出し、一意に一致することを確認してから"
        f"JSONに書いてください（一致しないtarget_excerptは、ホワイトボードへの注釈挿入が"
        f"サイレントに失敗する原因になります）。\n\n"
        f"[BL-094: read_verified_fact/read_deliverable_fileで数値の出所を追跡する] Agentが提示した"
        f"数値が、ゴール文に直接書かれた値なのか、Agent自身がどこかで仮定した派生値なのかを"
        f"見分けるには、read_verified_factで当該変数名・キーワードを検索し、他タスクで既に"
        f"確定した値・その理由・引用元と実際に一致しているか確認してください。一致しない、"
        f"または確定値が存在しないのにAgentが「確定済み」であるかのように断定している場合は、"
        f"それ自体が要指摘です。read_deliverable_fileでは、その確定値がどんな前提・議論を経て"
        f"導出されたか（他ノード自身の仮定を「出典」として自己引用していないか等）まで遡って"
        f"確認できます。【最低限、iter=1で一度は、今回の発言に含まれる主要な数値についてread_"
        f"verified_factで確認し、ゴール文にない数値が無根拠に確定値として扱われていないかを"
        f"チェックしてから判定を進めてください】。\n\n"
        f"【BL-093: thinkツールで検討過程を残す】この数値監査は複数回のpython_repl呼び出しを"
        f"跨ぐことが多く、{_BL093_THINK_VALUE_PARAGRAPH}\n\n"
        f"{_issue_carryover_prefix}"
        f"constraint_issue=\"major\"の場合も、既存のSUPERSEDE指示に加え、任意でwrite_issueを呼び"
        f"監査証跡を残して構いません（必須ではありません）。\n\n"
        f"[BL-188] 検算対象の数値がcitations（引用元）付きでweb由来の情報を根拠にしている場合、"
        f"read_reference_fileでそのキャッシュ本文を確認し、実際に主張と一致しているか（数値の"
        f"改変・拡大解釈がないか）を検証できます。\n\n"
        f"[BL-188] 【根拠の実在性チェック（重要）】python_replでの検算はあくまで「式が正しいか」"
        f"しか保証しません。式に投入されている前提数値（単価・相場・法定基準値等）自体が"
        f"citations=`expert_calculation`のみ（外部の一次情報`type=\"web\"`による裏付けなし）で、"
        f"かつあなた自身の知識でも真偽の確信が持てない場合は、web_searchで実際に調べて検証して"
        f"ください（web_fetchで一次資料を直接確認できます）。ただしweb_searchはいきなり呼ばず、"
        f"[BL-199/BL-200] ①read_goal_reference（開発者事前収集の参照データ）→②read_reference_file"
        f"（web_fetchキャッシュ。URLキーで全run共有、過去のrunで取得済みのページも読めます）"
        f"→③web_search、の順に確認してください（①②は呼び出し回数上限を消費しません）。"
        f"検算が内部整合的でも、前提数値が実態と乖離していれば、それ自体をconstraint_issueの根拠にしてください。\n\n"
        f"[BL-195: 実例からの無derivation転記チェック] 検算対象の数値がcitations type=\"web\"で"
        f"実在の類似事例を出典としている場合、python_replでの検算が「実例の数値を式に代入して"
        f"一致を確認しているだけ」なのか、「本課題固有の入力値（予算・需要データ・距離等）から"
        f"独立にその数値を導出しているか」を区別してください。前者（実例の値のコピーの検算に"
        f"すぎない）の場合は、独自導出がなされていない旨をconstraint_issueの根拠にしてください。\n\n"
        f"[BL-198: 地理データの数値は専用ツールで実測照合する] 検算対象に標高・2点間の距離・"
        f"緯度経度・道路距離が含まれる場合、python_replでの式の検算だけでなく、gsi_geocode／"
        f"gsi_get_elevation／gsi_calc_distance_bearing／calc_road_routeで実測値を取得し、"
        f"Agentが式へ投入した前提数値そのものが実態と合っているかを照合してください。特に、"
        f"直線距離（gsi_calc_distance_bearing）を道路距離として使っていないかは重点確認項目です"
        f"（山間部では道路距離が直線距離を大きく上回るため、所要時間・SLA判定が楽観側へ歪みます）。\n\n"
        f"[BL-204: 検算対象の前提値をレジストリと突き合わせる] 式へ投入されている前提値が、"
        f"事物についての事実である場合（施設の位置・規模・数量等）、read_entityでレジストリの"
        f"記録と一致しているかを確認してください。レジストリの記録と食い違う値、あるいは"
        f"レジストリに存在しない事物名が使われている場合は、それ自体をconstraint_issueの"
        f"根拠にしてください。住所と座標を持つ事物はverify_entity_geoで検算できます。\n"
        f"[BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値の検算は"
        f"read_verified_factを使ってください。\n\n"
        f"[BL-203: 座標そのものの妥当性を疑う] 実測値は「正しい場所を測った」場合にのみ正しく、"
        f"誤った座標を測れば「誤った場所の正しい実測値」になります。gsi_geocodeは住所ジオコーダで"
        f"あり施設名を無視するため、施設名で引くと大字の代表点（実位置と数km・標高で数百m違う）が"
        f"返ります。拠点の標高が周辺の市街地と不自然に食い違う場合、拠点名がゴール文の表記と"
        f"一致しているかを確認し、番地までの住所でgsi_geocodeを引き直して座標を照合してください。\n\n"
        f"【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・"
        f"write_agreement・verify_whiteboard_excerpt・write_issue・read_issues・"
        f"web_search・web_fetch・read_reference_file・read_goal_reference・read_entity・verify_entity_geo・gsi_geocode・"
        f"gsi_get_elevation・gsi_calc_distance_bearing・calc_road_route・thinkです。"
        f"{_THINK_TRAILER_SENTENCE}\n\n"

        f"System Goal: {goal}\n"
        f"{_get_goal_essence_text(get_active_conn(), state['run_id'])}\n"

        f"【BL-023: 現在タスクのacceptance_criteria充足チェック】\n"
        f"以下は現在のタスクで検証されるべき独立した主張の一覧です（インデックス0始まり）。\n"
        f"{criteria_text}\n"
        f"今回のAgentの発言が、それぞれの項目に応えている（充足している）かをbool配列で判定してください。\n"
        f"配列の長さ・順序は上記の一覧と対応させてください。\n\n"

        f"{domain_findings_block}"
        f"{python_calls_block}\n"
        f"{write_agreement_status_block}\n"
        f"{thought_process_audit}\n"
        f"【注意】直近の決定事項は状況把握のための参考情報であり、ここに含まれる引用（whyの内容等）は"
        f"執筆時点のホワイトボード内容である可能性があり、既に上書き・改訂されている場合があります。"
        f"target_excerptやverify_whiteboard_excerptの根拠には、必ず下記【R4: 現在タスクの成果物・"
        f"最新ホワイトボード】節の内容のみを使用してください。\n"
        f"Recent Decisions（参考程度）: {recent_decitions}\n\n"
        f"【プロジェクトの合意・決定事項・検討状況DB】\n{agreements_text}\n\n"
        f"【BL-086: 🔒Freeze済み項目の扱い】上記DBで🔒アイコンが付いている項目は、既に人間の発注者"
        f"（User）が審議の上で承認した意図的な例外です。同じ論点を理由に再度major判定やSUPERSEDEの"
        f"対象にしないでください（unfreeze機構は存在せず、Freeze済みへのSUPERSEDE/UPDATEはツール"
        f"呼び出し自体がエラーになります）。ただし、Freezeされていない別の新しい問題点はこれまで通り"
        f"厳格に評価してください。🔒項目について致命的ではない懸念がある場合は、constraint_issueを"
        f"上げず'observations'欄に留めてください。\n\n"
        f"【BL-062: 既存Agreementの無効化】constraint_issue=\"major\"と判定し、その原因が上記DB内の"
        f"特定のtopic（例：既にApprovedとして記録されている数値や決定）にある場合、commentに書くだけで"
        f"終わらせず、write_agreementツールをaction_type=\"SUPERSEDE\", status=\"Rejected\", "
        f"target_topic=\"<上記DBのtopic文字列そのまま>\", reason_why=\"<何が誤りでなぜ無効化するか>\" "
        f"として呼び出し、DB上のその記録を実際に無効化してください。そうしないと、あなたが誤りと判定した"
        f"内容が「承認済み」としてDBに残り続け、後続タスクや最終統合が誤って参照してしまいます。\n\n"

        f"{whiteboard_block}"
        f"【BL-076: 指摘箇所の引用】constraint_issueがminor/majorの場合、上記ホワイトボードの本文から、"
        f"指摘対象の箇所を一字一句そのまま（改変・要約せず）1〜2文だけ引用し'target_excerpt'に"
        f"入れてください（ホワイトボードへの注釈挿入に機械的に使うため、正確な引用が必須です）。"
        f"noneの場合や、ホワイトボードが存在せず引用できない場合は空文字にしてください。\n\n"
        f"{deferred_notes_block}"
        f"{_get_task_focus_companion_text(state)}"
        f"{_build_task_focus_state_text(state)}"
        f"{_build_task_focus_transition_notice(state)}"

        f"【今回評価するターンのやり取り】\n"
        f"{history_text}\n"
        f'Return ONLY JSON: {{"risk": "low/medium/high", "constraint_issue": "none/minor/major", "comment": "判定理由", "criteria_status": [true/false, ...], "target_excerpt": "指摘対象のホワイトボード本文からの一字一句引用（無ければ空文字）", "observations": "気づき・懸念（自由記述、無ければ空文字）"}}'
    )
    _reset_think_scratchpad()  # [BL-093]
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_detector_numeric, model=model_detector_numeric, label="Detector",
        tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, VERIFY_WHITEBOARD_EXCERPT_TOOL, WRITE_ISSUE_TOOL, READ_ISSUES_TOOL, WEB_SEARCH_TOOL, WEB_FETCH_TOOL, READ_REFERENCE_FILE_TOOL, READ_GOAL_REFERENCE_TOOL, READ_ENTITY_TOOL, VERIFY_ENTITY_GEO_TOOL, GSI_GEOCODE_TOOL, GSI_GET_ELEVATION_TOOL, GSI_CALC_DISTANCE_BEARING_TOOL, CALC_ROAD_ROUTE_TOOL, THINK_TOOL], fallback={"risk": "low", "constraint_issue": "none", "comment": "", "criteria_status": [], "target_excerpt": "", "observations": ""},
        state=state,
    )
    if parse_failed:
        # [SAFETY] D-005: 層2リトライを使い切った場合はフェイルオープン（none）ではなくフェイルクローズ（major）に倒す。
        # F-2.6検算ゲート導入の目的（暗算を信用しない）と、判定データ欠落時のフェイルオープンは相容れないため。
        print("🚨 [Detector] 層2リトライを使い切ってもJSON判定を取得できませんでした。フェイルクローズ(major)します。")
        return {"risk": "low", "constraint_issue": "major", "comment": "(判定JSON解析失敗のためフェイルクローズしました)", "criteria_status": [], "target_excerpt": domain_target_excerpt, "observations": domain_observations}
    print(f"【Detectorの判定結果(JSONパース後・数値監査パス)】\n{parsed}\n")
    risk = parsed.get("risk", "low")
    if risk not in ("low", "medium", "high"):
        risk = "low"
    numeric_constraint_issue = parsed.get("constraint_issue", "none")
    if numeric_constraint_issue not in ("none", "minor", "major"):
        numeric_constraint_issue = "none"
    numeric_comment = parsed.get("comment", "")
    numeric_target_excerpt = parsed.get("target_excerpt", "") or ""
    numeric_observations = parsed.get("observations", "") or ""
    criteria_status = parsed.get("criteria_status", [])
    if not isinstance(criteria_status, list):
        criteria_status = []

    # 統合: 数値監査・ドメイン妥当性レビューのうち、より重篤な判定を採用する。
    _severity_order = {"none": 0, "minor": 1, "major": 2}
    constraint_issue = max(
        (numeric_constraint_issue, domain_constraint_issue),
        key=lambda v: _severity_order[v],
    )
    print(f"  🔀 [Detector] 判定統合: constraint_issue={constraint_issue}（ドメイン={domain_constraint_issue}, 数値={numeric_constraint_issue}）")
    comment_parts = [f"【ドメイン妥当性レビュー】{domain_comment}"]
    if numeric_comment:
        comment_parts.append(f"【数値監査】{numeric_comment}")
    comment = "\n".join(comment_parts)

    # [BL-076] ホワイトボードへの注釈挿入に使うtarget_excerptは、実際に採用された
    # constraint_issueの重篤度を出した側のパスの引用を優先する（両方あればドメイン優先）。
    if _severity_order[domain_constraint_issue] >= _severity_order[numeric_constraint_issue]:
        target_excerpt = domain_target_excerpt or numeric_target_excerpt
    else:
        target_excerpt = numeric_target_excerpt or domain_target_excerpt

    # [BL-079] ドメイン妥当性レビューはverify_whiteboard_excerptを持たない（BL-093でthinkのみ
    # 追加、excerpt検証ツールは数値監査パス専用のまま）ため、一致しないtarget_excerptをそのまま
    # 出力しうる。severityより優先して選ばれた側の引用が
    # 実際にはホワイトボードと一致しない場合、もう一方のパスの引用が一致するならそちらへ
    # 差し替える（実際に注釈を挿入できることを優先する、プログラム側の最後の砦）。
    def _excerpt_matches_uniquely(excerpt: str) -> bool:
        if not excerpt or not _whiteboard:
            return False
        content = _whiteboard["content"]
        if content.count(excerpt) == 1:
            return True
        norm_content, _ = _normalize_for_loose_match(content)
        norm_excerpt, _ = _normalize_for_loose_match(excerpt)
        return bool(norm_excerpt) and norm_content.count(norm_excerpt) == 1

    if target_excerpt and not _excerpt_matches_uniquely(target_excerpt):
        _fallback_excerpt = numeric_target_excerpt if target_excerpt == domain_target_excerpt else domain_target_excerpt
        if _fallback_excerpt and _excerpt_matches_uniquely(_fallback_excerpt):
            print("  🔁 [Detector] BL-076: 優先パスのtarget_excerptがホワイトボードと一意に一致しなかったため、もう一方のパスの引用へ差し替えました。")
            target_excerpt = _fallback_excerpt
        else:
            print("  ⚠️ [Detector] BL-076: どちらのパスのtarget_excerptもホワイトボードと一意に一致しません。注釈挿入は失敗する見込みです。")

    # [BL-051軽量版] 両パスの気づき欄を統合。severityとは独立に、非空であれば毎回蓄積対象とする。
    observations_parts = []
    if domain_observations:
        observations_parts.append(f"【ドメイン】{domain_observations}")
    if numeric_observations:
        observations_parts.append(f"【数値】{numeric_observations}")
    observations = "\n".join(observations_parts)

    return {
        "risk": risk, "constraint_issue": constraint_issue, "comment": comment,
        "criteria_status": criteria_status, "target_excerpt": target_excerpt, "observations": observations,
    }

def call_decision_extractor(chat_history: list[dict], existing_topics: list[str], target_role: str,
                             owns_variables: list[str] | None = None,
                             valid_task_ids: list[str] | None = None) -> tuple[list[dict], dict]:
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
    valid_task_ids_text = (
        "\n".join(f"- {tid}" for tid in valid_task_ids)
        if valid_task_ids else "(タスク一覧が取得できませんでした)"
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
        
        - "Deliverable": 成果物の提示があったことの検出のみ。[BL-182] write_agreementが既に呼ばれた
          ターンではこの抽出結果自体がまるごと破棄されるため、200字以内の簡潔な要約で構いません
          （全文を複製しないでください）。write_agreementが呼ばれていなかった場合の保険としては、
          contentが短い場合Agentの発言全文が自動的に使われるため、content自体の全文保持は不要です。\n
        - "Decision": 今回Agentが提案した新たなルールや計算結果\n

        【重要】既存トピック一覧にある話題をAgentが「修正・更新」して再提示してきた場合でも、\n
        システム上は新しい成果物として上書きするため `action_type: "UPDATE"`, `status: "Proposed"` としてください。

        【BL-023/BL-082: 先送りの検出】Agentが「〇〇は次タスク（task_id）で扱う」「〇〇は別途詳細化する」のように
        既存トピックとは別の新しい論点を明示的に先送りした場合、`action_type: "CREATE"`, `entry_type: "Directive"`,
        `status: "Deferred"` として抽出してください。`content` には先送りされた論点、`rationale` にはどのタスクで
        扱うかを記載し、加えて`defer_to_task_id`にその**申し送り先のtask_id**を必ず設定してください（下記の
        task_id一覧から一字一句そのままコピー）。申し送り先が特定できない場合は空文字にしてください。
        {valid_task_ids_text}

        【BL-023: 共有変数の確定値検出】現在のタスクが確定させるべき共有変数（owns_variables）は以下の通りです:
        {owns_variables_text}
        Agentが今回、これらの変数のいずれかについて具体的な数値を確定させた場合（python_replでの検算結果を含む）、
        `owned_variable_values` に {{変数名: 値}} の形で出力してください。該当がなければ空オブジェクト `{{}}` としてください。

        【BL-029/BL-182: owned_variable_valuesはcontentと目的が異なります】
        `content`（Deliverable本体）は上記の通り簡潔な要約で構いませんが、`owned_variable_values`は
        それとは別に、他タスクが`depends_on`を通じてこの値を参照する際に読む、ごく簡潔な要約
        （確定した結論・数値・根拠の要点のみ）にしてください。
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

            【BL-023/BL-082: 先送りの検出】Userが「〇〇は次タスク（task_id）で扱う」「〇〇は別途詳細化する」
            「本タスクの範囲を超える」のように、既存トピックとは別の新しい論点を明示的に先送りした場合、
            `action_type: "CREATE"`, `entry_type: "Directive"`, `status: "Deferred"` として抽出してください。
            `content` には先送りされた論点、`rationale` にはどのタスクで扱うかを記載し、加えて
            `defer_to_task_id`にその**申し送り先のtask_id**を必ず設定してください（下記のtask_id一覧から
            一字一句そのままコピー）。申し送り先が特定できない場合は空文字にしてください。

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

            【BL-024: フェーズ・タスク遷移の検出】Userが「次のタスクに移行する」のように
            明示的に次のフェーズ・タスクへの移行を指示した場合のみ、トップレベルの`advances_to_phase_id`/
            `advances_to_task_id`にその移行先のIDを設定してください。移行の指示がない場合は両方とも
            `null`にしてください（前のタスクへの言及や単なるレビューは移行に該当しません）。

            【BL-039: task_idは以下の一覧から一字一句そのままコピーしてください】
            会話文中で「task_1.1」のようにドット区切りで言及されていても、`advances_to_task_id`には
            必ず下記一覧のアンダースコア区切り表記をそのまま使ってください（一覧にない表記は無効として扱われます）。
            {valid_task_ids_text}
        """

    # 🌟 2. 両者に適用する共通ルール（ご提示いただいた部分）
    common_rules = """
    【重要】抽出した項目の属性を、必ず以下の entry_type のいずれかに分類してください。
    - "Decision": 両者の間で実質的に合意・確定した結論、ルール、数値、判断基準。
      例:「割引は適用前の金額で判定する」「〈リソースX〉は3個体制とする」
    - "Directive": 一方から他方への、次にやるべきことの指示・依頼・タスク発行。
      例:「次はテストケースを作成してください」「予算内訳を見直してください」
    - "Deliverable": 成果物そのもの（仕様書・計画書等のドキュメント本文）。
      ※タスクごとに作成される「詳細仕様書」や「計画書」などのまとまった出力は必ずこれに分類してください。
      
    🚨 【成果物抽出に関する絶対ルール】 🚨
    1. [BL-182] CREATE(新規作成)時: content は200字以内の簡潔な要約で構いません。全文を複製する必要は
       ありません（write_agreement経由で既に登録済みの場合はこの抽出結果自体が破棄され、未登録の場合は
       Agentの発言全文が別途自動的に使われるため、content自体に全文を保持する意味がありません）。
    2. UPDATE(更新)時: Userが「承認」「条件付き承認」「却下」などの評価をしただけで、AI側から新しい成果物本文の提示がない場合、content は【必ず空文字 ""】にせよ。「承認された」などの短い説明文を絶対に入れないこと。

    [BL-050] action_type="UPDATE"（既存topicの値を変更する）の場合、rationale には
    「新しい値が何故妥当か」だけでなく「前の値から何故・どう変わったのか」を必ず明記してください。
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
            "content": "提案内容(Deliverableは200字以内の要約でよい。DeliverableのUPDATE時は必ず空文字に)",
            "rationale": "抽出または判定の理由",
            "proposed_by": "Agent または User",
            "phase_id": "現在のフェーズID",
            "task_id": "現在のタスクID（分からなければ空文字）",
            "owned_variable_values": {{"変数名": "値（該当なければ空オブジェクト{{}}）"}},
            "defer_to_task_id": "status=Deferredの場合のみ、申し送り先のtask_id（それ以外は空文字）"
            }}
        ],
        "advances_to_phase_id": "Userが明示的に次のフェーズへの移行を指示した場合のみそのphase_id。なければnull",
        "advances_to_task_id": "Userが明示的に次のタスクへの移行を指示した場合のみそのtask_id。なければnull"
        }}
    """


    _reset_think_scratchpad()  # [BL-093]
    # [BL-160] 従来は_safe_json_parseへの単発呼び出しでリトライが一切なく、reasoningチャンネル
    # への出力漏れ（修正済み）以外の純粋なAPI不調・出力崩れでも即座にそのターンの抽出が
    # 全損していた（call_reflection等の他ノードは既に_query_and_parse_with_retryで保護済み）。
    # 同水準の層2リトライ保護を追加する。
    _decision_extractor_fallback = {"extracted_events": []}
    parsed, _decision_extractor_parse_failed = _query_and_parse_with_retry(
        prompt, client=client_decision_extractor, model=model_decision_extractor, label="Decision Extractor",
        tools=None, fallback=_decision_extractor_fallback,
    )
    if _decision_extractor_parse_failed:
        print("⚠️ [Decision Extractor] 層2リトライも失敗。このターンのDecision/Directive/Deliverable抽出は全て失われます。")

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

def call_resource_arbiter(goal: str, overrun: dict, phases_info: list[dict], goal_essence_text: str = "", state: dict | None = None) -> dict:
    """【SLM要約】
    Delegation of resource reallocation decisions to an AI arbiter based on overall system goals and current phase allocations when constraints are exceeded.
    """
    phases_text = "\n".join(
        f"- {p['phase_id']}（{p['title']}）: 現在の取り分 {overrun['claiming_phases'].get(p['phase_id'], 0)}"
        for p in phases_info
    )

    # [BL-104] プロンプトキャッシュのヒット率向上のため、固定指示文（役割説明・検算ゲート・
    # BL-093/BL-094・ツール一覧・ゴール変容検知・JSON形式の指示）を先頭付近にまとめ、呼び出し
    # ごとに変わる動的な内容（overrun詳細・各フェーズの配分）は末尾に配置する。位置的参照
    # （「上記」「後述」）を持つブロックはこのプロンプトには存在しないため、全ブロックを
    # 自由に並び替えている。
    prompt = f"""
    あなたはプロジェクト全体の意思決定者です。
    各フェーズの目標達成への重要度・必須度を評価し、超過分を解消するための
    再配分案を提示してください。次のいずれか、または組み合わせを検討してください:
    - 優先度の低いフェーズの成果を縮小・簡素化する
    - 優先度の高いフェーズに資源を多く配分し直す

    【F-2.6 機械的検算ゲート（必須）】予算超過判定は python_repl ツールで機械的に合計・比較してから行うこと。

    {_verification_throttle_warning(example="「この再配分案は上限内に収まるか」")}

    【BL-093: thinkツールで検討過程を残す】{_BL093_THINK_VALUE_PARAGRAPH}
    [BL-094: read_verified_fact/read_deliverable_fileで既存の配分・決定と同期する]
    read_verified_factは全フェーズ・全タスク横断で、変数名やキーワードから確定値（値・理由・
    引用元・confidence）を検索できます。read_deliverable_fileは過去タスクの成果物全文（その値が
    どんな前提で確定したか）を読めます。【最低限、iter=1で一度は、このリソースや関係するフェーズに
    ついてread_verified_factで確認し、既に確定している配分・前提が無いか
    同期してから再配分案を検討してください】。確認せずに独自の前提で再配分すると、既存の
    確定事項と矛盾するリスクがあります。
    【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
    write_agreement・thinkです。{_THINK_TRAILER_SENTENCE}

    【ゴール変容の検知（★R5 GoalShiftEvent）】
    提示する再配分案が、当初の絶対制約（このリソースのtotal_cap自体）を
    変更する必要があると判断した場合、requires_goal_constraint_change: true を
    含めて返答してください。単なるフェーズ間の配分見直し（total_capは維持）で
    あれば false としてください。

    ■ 絶対目標: {goal}
    {goal_essence_text}

    リソース「{overrun['constraint']}」が、上限{overrun['cap']}に対し合計{overrun['claimed']}と、
    {overrun['over_by']}超過しています。

    ■ 競合している各フェーズの現在の配分:
    {phases_text}

    Return ONLY JSON:
    {{
        "priority_ranking": ["phase_id順に重要な順"],
        "new_allocation": {{"phase_id": new_amount, ...}},
        "phases_to_revise": ["再検討が必要なphase_idのリスト"],
        "rationale": "判断理由",
        "requires_goal_constraint_change": true または false
    }}
    """
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "arbiter"
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    res = query_AI([{"role": "user", "content": prompt}], client=client_resource_arbiter, model=model_resource_arbiter, label="Resource Arbiter", tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, THINK_TOOL], state=state)
    _arbiter_fallback = {}
    parsed = _safe_json_parse(res, fallback=_arbiter_fallback)
    if parsed is _arbiter_fallback:
        print(f"⚠️ [Resource Arbiter] JSON解析に失敗しました（生レスポンス冒頭300字: {(res or '')[:300]!r}）。resource_arbiter_nodeは「再検討不要」として扱います。")
    return parsed


def detect_goal_shift(state: "LineageState", arbiter_result: dict) -> dict | None:
    """【SLM要約】
    [R5 GoalShiftEvent] arbiter_nodeの再配分案が、当初のcurrent_goalのabsolute_constraints自体を
    変更するレベルに達した場合（例: 予算上限そのものの見直しが提案された場合）、
    GoalShiftEventとして記録すべきイベントdictを返す。該当しなければNone。
    """
    if arbiter_result.get("requires_goal_constraint_change"):
        return {
            "shift_kind": "constraint_hit",
            "from_goal_state": json.dumps(state.get("global_constraints", []), ensure_ascii=False),
            "to_goal_state": json.dumps(arbiter_result.get("new_allocation", {}), ensure_ascii=False),
            "reason_why": arbiter_result.get("rationale", ""),
            "triggered_by": "Arbiter_Resource_Overrun",
        }
    return None


def call_reflection(state: LineageState, config: Appconfig) -> dict:
    """【SLM要約】
    Generation of a comprehensive audit prompt synthesizing past decisions, agreements, chat history, and risks to determine the overall project discussion status (completed, stagnant, or continuing).
    """
    
    _conn = get_active_conn()
    decisions = get_decisions_from_db(_conn, state["run_id"])
    agreements = get_agreements_from_db(_conn, state["run_id"])
    chat_history = state["chat_history"]
    # [BL-056] reflectionの発火判定自体はBL-048でround_countベースに切り替え済みだが、
    # プロンプト内の表示が凍結したままのturn_count（BL-005）だったため、
    # 「全30ターン中1ターン目のまま」という表示とAI自身の混乱を招いていた。
    # 発火条件と表示の基準を一致させるため、ここもround_countに揃える。
    round_count = state.get("round_count", 0)
    reflection_interval = state.get("reflection_interval", 3)
    constraint_issue_log = state["constraint_issue_log"]
    risk_register = state.get("risk_register",[])

    timeline = []
    for i, d in enumerate(decisions):
        why_short = (d["why"] + "…") if len(d.get("why", "")) > 60 else d.get("why", "")
        ts_val = d.get("timestamp", 0)
        # [BL-175] ログのタイムスタンプ（JST）と同期させる。
        ts = datetime.datetime.fromtimestamp(ts_val, JST).strftime("%H:%M:%S") if ts_val else "??:??:??"
        timeline.append(f"└ [{ts}] [{d.get('who','?')}] No.{i+1}: {d.get('what','?')} | 理由: {why_short}")
    timeline_str = "\n".join(timeline) if timeline else "(意思決定のログはありません)"

    print(f"\n\n{'='*60}")
    print(f"\n---timeline_str---\n {timeline_str}")
    print(f"\n\n{'='*60}")

    agreements_text = _build_agreements_context(agreements)
    recent_history = chat_history[-10:]
    history_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])

    major_issues = [i for i in constraint_issue_log if i.get("severity") == "major"]
    constraint_log_lines = [f"- [Turn {i['turn']}] {i['comment']}" for i in major_issues[-10:]]

    # [BL-096] issue_logのstatus='escalated'行も、Python側の直接DB問い合わせでここに統合する
    # （モデルのツール呼び出し判断に依存せず、必ずreflectionへ届ける）。
    # [BL-194] この一覧は「停滞判定の材料」と「completed宣言の抑止材料」を兼ねている。
    # DEFER/ACK済み行を一覧から落とすと後者が壊れ（未解決なのにcompletedを宣言できる）、
    # 落とさないと前者が壊れる（triage済みで停滞と誤断）。両立させるため一覧は全件のまま
    # 残し、行ごとに「対応予定task_idが確定済みか」を注記して役割を分離する。機械的な
    # stagnant上書き（reflection_node）側は_get_actionable_escalated_issuesを使う（B-1で対応済み）。
    escalated_issues = _get_escalated_issues(_conn, state["run_id"])
    for i in escalated_issues:
        _defer_note = ""
        if _is_issue_effectively_deferred(_conn, state["run_id"], i, state.get("current_task_id", "")):
            _defer_note = (
                f"【対応予定task_id={i['defer_to_task_id']}が確定済み。"
                "完了(completed)判定では未解決として扱うこと。ただし現在タスクでの停滞(stagnant)の"
                "根拠にはしないこと——対応する担当タスクが既に決まっているため】"
            )
        elif _is_issue_acknowledged_active(i, round_count):
            _defer_note = (
                f"【現在タスクで対応中と表明済み（残り{int(i.get('acknowledged_until_round') or 0) - round_count}"
                "ラウンド）。完了(completed)判定では未解決として扱うこと。ただし現在タスクでの"
                "停滞(stagnant)の根拠にはしないこと——既に対応中であるため】"
            )
        constraint_log_lines.append(
            f"- [issue_log topic={i['topic']}] {i['description']}（累積{i['occurrence_count']}回発生）{_defer_note}"
        )

    constraint_log_text = "\n".join(constraint_log_lines) if constraint_log_lines else "(なし)"

    # ドメイン固有キーワードに頼らず、Proposedのまま残っている項目を全件提示する
    unresolved_critical = [a for a in agreements if a["status"] == "Proposed"]
    unresolved_text = "\n".join(
        f"- {a['topic']}: {a.get('decision_what', '')[:80]}" for a in unresolved_critical
    ) or "(なし)"
    
    # [BL-104] このプロンプトは「上記の矛盾・懸念が」「上記のいずれかに」「上記の直近の会話の
    # 流れとタイムラインを」のように、直前の動的ブロック（unresolved_text/constraint_log_text/
    # timeline_str/history_text）を直接参照する指示文が多段に連鎖しており、固定指示文と動的
    # データを機械的に分離すると参照関係が壊れる。そのため他ノードのような全面的な並び替えは
    # 行わず、完全に自己完結しているBL-093の説明のみ先頭の固定ブロックへ移動するに留める。
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

    ■ 単発監査人(detector)が過去に検知した「数値・論理・成果物欠落の重大な矛盾(major)」の履歴、
    および[BL-096] issue_logに記録され累積再発によりエスカレーション（escalated）された懸念:
    {constraint_log_text}
    上記の矛盾・欠落・エスカレーション済み懸念が、その後の議論やDBで実際に解消されているか確認してください。

    上記のいずれかに1件でも未解決の項目・矛盾・エスカレーション済み懸念が残っている場合、
    discussion_statusを"completed" にしてはいけません。"continuing" または "stagnant" としてください。
    
    特に、ゴールの文中で要求されている「成果物の種類」（例: 仕様書、テストケース、計画書、設計図等、
    ゴール文に明記されているもの）が、実際にすべて提出されているかを最優先で確認してください。
    一部だけが完成し、残りが「次回作成予定」のまま終わっている場合は "completed" にしないでください。

    ■ 当初の絶対ゴール: 👉 {state['goal']}
    {_get_goal_essence_text(_conn, state['run_id'])}
    ■ 【決定事項DB】（これまでに確定した要件）:\n{agreements_text}
    ■ これまでのシステム判断のタイムライン:\n{timeline_str}
    ■ 直近の実際の会話の流れ:\n{history_text}
    {_build_task_focus_state_text(state)}
    [BL-191] 上記のタスクフォーカス状況が「一時的に過去タスクへフォーカス中」等を示している場合、
    それは発注者の意図的な手戻り対応です。同じタスクが繰り返し再提出されているように見えても、
    それだけを理由にstagnant（膠着）や迎合と判定しないでください。

    {_build_current_task_scope_brief(state)}
    [BL-194] 停滞(stagnant)判定の前に、必ず次を確認してください: 上で「未解決」として挙がっている
    懸念のそれぞれが、上記の現在タスクのacceptance_criteria/owns_variablesのどれかに対応して
    いますか。どれにも対応しない懸念は、現在タスクで解決すべき問題ではありません（別タスクの責務、
    または計画そのものへの指摘です）。その懸念が未解決であることだけを理由にstagnantと判定しないで
    ください。代わりにnoteへ「この懸念はtask_X_Yのスコープである」と明記してください——noteは
    Facilitatorへそのまま引き継がれ（BL-061）、Facilitatorが現在タスクで解決させようと誘導するのを
    防ぐ唯一の経路です。

    【でっちあげ監査（★R5 F-2.1、cela_r5_design_v2.md §1.3）】
    上記の直近の会話の流れとタイムラインを俯瞰し、単発のDetectorでは見逃されがちな
    以下のパターンがないか確認してください。
    - 制約（時間・距離・予算等）が数式的に満たせないはずなのに、根拠のない前提や内訳
      （例: 「複数の区間に分割・按分すれば辻褄が合う」のような、元データにない都合の良い数値）を
      その場ででっち上げて帳尻を合わせている。
    - 都合の悪い制約に触れず、結論だけ急いで確定させようとしている。
    - Detector自身が「本当にこの前提は妥当か？」と一度疑いながらも、
      根拠のない推測で自己納得して通してしまっている。
    このようなパターンが見つかった場合、discussion_statusを"stagnant"とし、noteに
    どの発言・どの数値がでっちあげと判断したか、具体的に指摘してください
    （単に「進んでいない」という理由でのstagnant判定と区別できるようにするため）。

    【迎合（collusion）監査（BL-126 §7）】
    上記のでっちあげ監査とは別の観点として、User AIとAgent AIの間で「安易な譲歩・方針転換」が
    起きていないかも確認してください。判定基準は方針転換の**回数**ではありません
    （複数回の方針転換自体は、正当な理由があれば健全な議論の証拠でもあります）。
    問うべきは「その転換の重大さに見合った理由づけがあるか」です:
    - 制約や要件を緩める・変更する方針転換なのに、理由づけが「相手がそう言ったから」
      「その方が楽だから」等、転換の重大さに見合わない薄いものである。
    - Userが本来もっと厳しく問い詰めるべき提案（予算超過・要件未達等）に対して、
      具体的な検証や反論なしに安易に同意・承認している。
    - Agentが、User側の圧力や催促を理由に、根拠のある自らの分析結果を十分な検証なしに
      撤回している。
    このようなパターンが見つかった場合、discussion_statusを"stagnant"とし、noteにどの転換が
    どのように理由不足だったかを具体的に指摘してください。逆に、転換の理由づけが具体的で
    重大さに見合っている場合は、それを理由にstagnantとしないでください（正当な議論の進展を
    迎合と誤認しないため）。

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

       ⏳ 現在は **ラウンド{round_count}**（{reflection_interval}ラウンドごとに本監査を実施）です。
       ※「ターン」は内部のやり取り往復の途中で足踏みすることがあるため、ここでは代わりに
       「ラウンド」（発注者Userの発言サイクルの周回数）を進行状況の目安として用いています。

       [BL-188] 上記の矛盾・懸念がweb由来のcitations（引用元URL）に基づく主張に関わる場合、
       read_reference_fileでそのキャッシュ本文を確認し、実際に主張と一致しているかを検証できます
       （新規のweb検索・取得はこのパスでは行いません）。
       [BL-204] この課題に登場する事物についての事実はread_entityで確認できます。停滞・矛盾の
       判断が特定の事物の主張に関わる場合、レジストリの記録と食い違っていないか確認してください。
       [BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値はここでは
       扱いません（このパスにread_verified_factはありません）。
       【重要】あなたが使えるツールはread_reference_file・read_entityです。

        Return ONLY JSON in the exact format below:
        {{
            "still_aligned": true/false,
            "discussion_status": "continuing" or "completed" or "stagnant",
            "note": "分析理由（矛盾・欠落の解消状況について必ず言及すること）"
        }}

    """

    # [BL-120] 従来は単発のquery_AI+_safe_json_parseで、1回のJSONパース失敗が即座に
    # discussion_status="stagnant"へ直結していた。これは「安全側フォールバック」のつもりが、
    # 一時的なパース崩れ（複数```jsonブロックの混線等、BL-089で他ノードにも確認済みの現象）
    # だけでfacilitatorへの差し戻しを誘発する実害を生んでいた（1420ログで確認）。
    # BL-089の層2リトライ（_query_and_parse_with_retry）を適用し、真にパースし続けられない
    # 場合にのみ、従来通りstagnantへフェイルクローズする（stagnant自体は「安全側は差し戻し」
    # という方針として引き続き妥当なため、フォールバック値そのものは変更しない）。
    _reset_think_scratchpad()  # [BL-093]
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_reflection, model=model_reflection, label="Reflection",
        # [BL-184] BL-109でtools=None（単発判定、think無し）にした方針は維持しつつ、
        # ユーザー指示により滞留issueの根拠（citations由来URL）をReflectorが自ら検証できるよう
        # read_reference_fileのみ追加する（新規の外部通信は発生させない、既存キャッシュの参照専用）。
        # [BL-204] read_entityも同じ理由（読み取り専用・外部通信なし・呼び出し予算を消費しない）
        # で追加する。
        tools=[READ_REFERENCE_FILE_TOOL, READ_ENTITY_TOOL],
        fallback={"still_aligned": False, "discussion_status": "stagnant", "note": "Parse error."},
        state=state,
    )
    if parse_failed:
        print("🚨 [Reflection] JSON判定の取得に失敗しました。安全のためフェイルクローズ(stagnant)します。")
    aligned_val = parsed.get("still_aligned", True)

    return {
        "still_aligned": str(aligned_val).lower() == "true" if isinstance(aligned_val, str) else bool(aligned_val),
        "discussion_status": parsed.get("discussion_status", "continuing"),
        "note": parsed.get("note", ""),
    }

def call_facilitator(goal: str, chat_history: list[dict], reflection_note: str = "", goal_essence_text: str = "",
                      escalated_issues_text: str = "", essence_dialogue_active: bool = False,
                      state: dict | None = None) -> str:
    """【SLM要約】
    Generates a guiding prompt to help AI agents refocus discussions on key unresolved issues toward achieving the overall system goal.
    [BL-126 Stage D] ツールループ化（THINK_TOOL/ESCALATE_PREMISE_CONCERN_TOOL/WRITE_AGREEMENT_TOOL）。
    Facilitator自身がescalate_premise_concernで懸念を提起したり、write_agreement
    (entry_type="EssenceProposal")で本質対話の開始・収束確定を提起できるようになった。
    essence_dialogue_active時は、通常の「議論への介入」モードとは別の、対話継続専用の
    固定文面に切り替える（§13.1: 切替のトリガーは1つの明確なフラグの読み取りのみ）。
    """
    recent_history = chat_history[-10:]
    history_text = "\n".join([f"{'User' if m['role']=='user' else 'AI'}: {m['content']}" for m in recent_history])

    if essence_dialogue_active:
        # [BL-126 Stage D/§13.2] Essence Dialogue継続モード。通常モードの
        # reflection_block（呼ばれた理由の再提示）・escalated_issues_blockは、既に対話中で
        # 自明なため省略する。
        prompt = f"""
    あなたはAI同士の議論をサポートする優秀な「ファシリテーター」です。
    これは本質対話（Essence Dialogue）の続きです。あなたは既に、目標の前提・制約の文言が
    真の目的と矛盾しているのではという懸念を提起し、User AIと数ラウンドにわたり対話しています。

    直近のUser AIの応答を踏まえ、以下のいずれかを行ってください：
    1. まだ論点が定まっていない、またはUserの応答に更なる検討の余地がある場合は、
       さらに問い直す・掘り下げるメッセージを1つ作成してください。
    2. 対話を通じて方向性が固まった、またはUserが既に明確な結論を示した場合は、
       write_agreement(entry_type="EssenceProposal", status="Proposed", action_type="CREATE",
       topic="essence_dialogue_<簡潔な識別子>", decision_what="<結論の要約>",
       reason_why="<なぜこの結論に至ったか>")を呼び、本質対話の結論を確定提案として記録して
       ください（この提案はUser AIが承認するまで正式な合意にはなりません）。

    [BL-204] この課題に登場する事物についての事実はread_entityで確認できます。
    [BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値はここでは
    扱いません（このパスにread_verified_factはありません）。

    【重要】あなたが使えるツールはthink・escalate_premise_concern・write_agreement・
    read_reference_file・read_entityです。

    ■ プロジェクトの目標(Goal): {goal}
    {goal_essence_text}
    {_build_task_focus_state_text(state) if state else ""}
    {_build_current_task_scope_brief(state) if state else ""}
    ■ 直近の会話:
    {history_text}
    """
    else:
        # [BL-061] facilitatorはreflectionの"stagnant"/drift判定を契機に呼ばれるが、従来は
        # なぜ呼ばれたか（具体的にどの論点が未解決か）を一切知らされず、直近10件のchat_history
        # のみから独自に状況を再判定していた。その結果、reflectionが「でっちあげ数値・与条件違反」
        # を明確に指摘していても、facilitatorが「膠着していない」と独立に判断し、無関係な軽微な
        # 論点だけを穏やかに促す食い違ったメッセージを出す事例が実ドライランで確認された
        # （log/2026-07-23/1656）。reflectionの判定理由をそのまま提示し、これを出発点として
        # 扱わせることで、この食い違いを防ぐ。
        reflection_block = (
            f"■ あなたが呼ばれた理由（直前のReflection監査の判定）:\n{reflection_note}\n"
            if reflection_note else
            "■ あなたが呼ばれた理由（直前のReflection監査の判定）: (特筆すべき懸念なし。周期的な確認です)\n"
        )

        # [BL-096] issue_logのescalated行はPython側の直接DB問い合わせで機械的に注入する
        # （reflectionのnoteに言及があるとは限らないため、この経路だけは常に保証する）。
        # 漠然とした停滞への対応（上記の抽象的な促し）とは別に、具体的な懸念を名指しして
        # その解消を最優先事項として提示する専用の指示を追加する。
        # [BL-170] escalated_issues_textはDetector等が指摘した具体的な数値issueの生テキストで
        # あり、財務モデルの誤り等、内容自体がいかにも「自分で計算し直すべき課題」に読める。
        # 実際に`log/2026-08-04/1435`で、この具体的な数値issue（オペレーター人員体制の労基法
        # 違反計算）を読んだFacilitatorが、自分の職掌（短い誘導メッセージを1つ書くこと）を
        # 逸脱してExpertの仕事（財務モデル全体の再計算・Deliverable再提出）を自分でやるべきだと
        # 誤認し、python_repl（このノードには意図的に付与されていない）を呼ぶ計画をthinkで
        # 宣言し続けるだけの空回りに陥り、MAX_TOOL_ITER予算を丸ごと空費して無出力に終わった
        # （BL-170）。「これは誘導メッセージの材料であり、あなた自身が解決する課題ではない」旨を
        # 明示するガードレール文を追加し、role境界の踏み越えを防ぐ。
        escalated_issues_block = (
            f"""
    🚨 【具体的に特定済みの未解決issue（最優先で解消させてください）】
    以下は、繰り返し発見・報告されたためシステムが機械的にエスカレーションした具体的な懸念です。
    これらは漠然とした停滞ではなく、特定済みの問題です。上記の「抽象的に視座を上げて促す」
    という一般方針とは別に、この懸念を名指しして、その解消を最優先事項として明確に提示して
    ください（「〇〇を直ちに決定してください」という直接的な表現を避けるべきなのは、漠然とした
    停滞への対応の場合のみです。ここでは具体的に何を解消すべきかをはっきり伝えてください）:
    {escalated_issues_text}

    [BL-170] 【重要】上記はあくまで、あなたが書く誘導メッセージの材料（背景情報）です。
    あなた自身がこの数値を再計算・修正したり、代わりに成果物を作成・提出することは
    あなたの役目ではありません（それはExpert/Userの役目です）。あなたにはpython_replの
    ような検算ツールも、Deliverable新規作成の権限も与えられていません。この懸念そのものを
    自分で解決しようとせず、AI達へ的確に提示する短いメッセージの作成に専念してください。
    """
            if escalated_issues_text else ""
        )

        # [BL-104] プロンプトキャッシュのヒット率向上のため、固定指示文（役割説明・BL-093の説明）を
        # 先頭にまとめ、ゴール文（実行中はほぼ不変）をその次、ターンごとに変わる動的な内容
        # （reflectionの判定理由・エスカレーション済み懸念・直近の会話）は末尾に配置する。
        # 「※あなたが呼ばれた理由（下記）は」というreflection_blockへの前方参照、および
        # escalated_issues_block内の「上記の『抽象的に視座を上げて促す』という一般方針」という
        # 冒頭の役割説明パラグラフへの後方参照は、両方とも冒頭の固定指示文グループが動的ブロックより
        # 前に来ることを要求しているだけであり、この並び替え後の順序で引き続き成立する。
        # [BL-126 Stage D] Facilitator自身が、目標の前提・制約の文言が真の目的と矛盾していると
        # 判断した場合はescalate_premise_concernで能動的に懸念を提起できる旨を追加。
        prompt = f"""
    あなたはAI同士の議論をサポートする優秀な「ファシリテーター」です。
    現在、AI同士の議論が目標(Goal)から脱線しそうになっているか、同じ論点で少し停滞しているようです。\n

    彼らが再び目標に向かって、自律的かつ建設的な議論を進められるように、
    議論の焦点となるべき「未決着の論点」や「次に深掘りすべきテーマ」を優しく提示するメッセージを1つ作成してください。\n
    また、議論が膠着状態である時は、視座を上げ目標と、制約、条件、AI同士の議論を見渡し、そもそも目標が達成しようとしている本質的な課題は何か
    その課題を解決するための手段は他にないのか、AI（ユーザーとエージェント/エキスパート）は視野が狭くなっていないか、
    また、守らなければならない制約と、見直し可能な条件は何かという視点で思考してください。

    ※以上の事から「〇〇について直ちに決定してください」といった強制的な表現は避け、AI達の視野狭窄を解き、本質的な課題解決の視座と発想、思考を与える
    ようアドバイスしてください。
    ※あなたが呼ばれた理由（下記）は必ず最優先の出発点として扱ってください。自分で独自に「膠着していない」等と再判定し、
    その理由を無視・軽視することは避けてください。

    【BL-126: ゴールの前提そのものに疑義がある場合】議論が停滞している真因が、個々のAIの
    詰めの甘さではなく「ゴール文に書かれた制約・前提そのものが真の目的と矛盾している」ことに
    あると具体的な根拠を持って判断した場合、escalate_premise_concernツールで懸念を提起して
    ください（一般的な「厳しい」という感想では使わないこと。狭く構造化された懸念に限定）。

    [BL-188] 上記のescalated_issuesや直近の会話がweb由来のcitations（引用元URL）に基づく
    主張に関わる場合、read_reference_fileでそのキャッシュ本文を確認できます（新規のweb検索・
    取得はこのノードでは行いません）。
    [BL-204] この課題に登場する事物についての事実はread_entityで確認できます。
    [BL-205] read_entityは名前を持つ事物専用です。対象を持たない単独の値はここでは
    扱いません（このパスにread_verified_factはありません）。
    【重要】あなたが使えるツールはthink・escalate_premise_concern・write_agreement・
    read_reference_file・read_entityです。

    ■ プロジェクトの目標(Goal): {goal}
    {goal_essence_text}
    {reflection_block}
    {escalated_issues_block}
    {_build_task_focus_state_text(state) if state else ""}
    {_build_current_task_scope_brief(state) if state else ""}
    [BL-194] 上の懸念のうち、現在タスクのacceptance_criteria/owns_variablesのどれにも対応しない
    ものについては、「現在のタスクで解決してください」という誘導を書かないでください。それは
    現在の担当者に、担当外の解けない問題を押し付けることになります（実例: log/2026-08-08/1514で、
    需要セグメント定義のタスクに車両台数と待ち時間の実現可能性証明を求め続け、ホワイトボードが
    Ver.41まで空転しランが強制停止しました）。スコープ外だと判断した場合は、代わりに「その論点は
    どのタスクの責務か」を整理させる方向の短いメッセージを書いてください。
    ■ 直近の会話:
    {history_text}
    """

    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "facilitator"
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    return query_AI(
        [{"role": "user", "content": prompt}], client=client_facilitator, model=model_facilitator, label="Facilitator",
        tools=[THINK_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, WRITE_AGREEMENT_TOOL, READ_REFERENCE_FILE_TOOL, READ_ENTITY_TOOL], state=state,
    )

def call_integrator(goal: str, merged_text: str, goal_essence_text: str = "", state: dict | None = None) -> dict:
    """【SLM要約】
    Cross-checking of merged project artifacts against a defined goal to identify logical or numerical inconsistencies between tasks and phases.
    """
    # [BL-104] プロンプトキャッシュのヒット率向上のため、固定指示文（役割説明・検算繰り返し
    # 禁止・BL-093/BL-094・ツール一覧の説明）を先頭にまとめ、ゴール文（実行中はほぼ不変）を
    # その次、呼び出しごとに変わる統合要件定義書本体は末尾に配置する。位置的参照（「上記」
    # 「後述」）を持つブロックはこのプロンプトには存在しないため、全ブロックを自由に並び替えている。
    prompt = f"""
    あなたはプロジェクトの統合監査人（Integrator）です。
    各タスクで作成された個別の成果物を物理的に結合した以下の「統合要件定義書」を読み、
    フェーズ間やタスク間で論理的・数値的な矛盾が生じていないか横断チェックしてください。

    {_verification_throttle_warning()}

    【BL-093: thinkツールで検討過程を残す】{_BL093_THINK_VALUE_PARAGRAPH}
    [BL-094: read_verified_fact/read_deliverable_fileで数値の出所を横断確認する]
    統合文書内の各数値が、複数タスクで整合しているように見えても、実際には別々の前提から
    独立に導出された「たまたま似た数値」である場合があります（例: 同じ量を指すはずの数値が
    タスクごとに違う仮定で計算されていた等）。read_verified_factで主要な変数を検索し、"confirmed_"
    variables"の理由・引用元を突き合わせることで、見かけ上一致していても前提が食い違っている
    ケースを検出できます。read_deliverable_fileでは、その数値がどのタスクでどんな前提のもと
    確定したかを遡って確認できます。【最低限、iter=1で一度は、統合文書中の主要な数値について
    read_verified_factで確認し、複数タスクにまたがる数値の前提が実際に一致しているかを
    チェックしてから矛盾判定を行ってください】。\n
    【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
    write_agreement・thinkです。{_THINK_TRAILER_SENTENCE}

    ■ 絶対目標: {goal}
    {goal_essence_text}

    ■ 統合要件定義書:
    {merged_text}

    Return ONLY JSON:
    {{
        "contradictions": true/false,
        "affected_phases": ["矛盾が発生しているphase_idのリスト"],
        "details": "矛盾の具体的な内容と理由"
    }}
    """
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "integrator"
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    res = query_AI([{"role": "user", "content": prompt}], client=client_integrator, model=model_integrator, label="Integrator", tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, THINK_TOOL], state=state)
    _integrator_fallback = {"contradictions": False, "affected_phases": [], "details": ""}
    parsed = _safe_json_parse(res, fallback=_integrator_fallback)
    if parsed is _integrator_fallback:
        print(f"⚠️ [Integrator] JSON解析に失敗しました（生レスポンス冒頭300字: {(res or '')[:300]!r}）。「矛盾なし」として扱われ、パイプラインは完了へ進みます。")
    return parsed


def call_reviewer(goal: str, deliverable_text: str, goal_essence_text: str = "", state: dict | None = None) -> dict:
    """【SLM要約】
    Delegation of artifact validation to an AI QA reviewer, strictly enforcing adherence to defined goals against delivered documentation.
    """
    # [BL-104] プロンプトキャッシュのヒット率向上のため、固定指示文（QA責任者としての各種
    # チェック指示・検算ゲート・BL-093/BL-094・ツール一覧の説明）を先頭にまとめ、ゴール文
    # （実行中はほぼ不変）をその次、呼び出しごとに変わる最終成果物本体は末尾に配置する。
    # 位置的参照（「上記」「後述」）を持つブロックはこのプロンプトには存在しないため、
    # 全ブロックを自由に並び替えている。
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

    {_verification_throttle_warning()}

    【BL-093: thinkツールで検討過程を残す】{_BL093_THINK_VALUE_PARAGRAPH}
    [BL-094: read_verified_fact/read_deliverable_fileで最終成果物の数値根拠を追跡する]
    最終成果物中の数値がゴール文の直接記載か、それとも途中のどこかのタスクで仮定された派生値かを
    read_verified_factで検索し確認してください。確定値の理由・引用元が「他ノード自身の推測」を
    自己引用しているだけで、実質的な根拠がゴール文にまで遡れない場合は、それ自体を要指摘として
    扱ってください。read_deliverable_fileで元タスクの成果物本文まで遡れば、その前提が明示されて
    いたか（仮定として書かれていたか、無条件の確定事項として書かれていたか）を確認できます。
    【最低限、iter=1で一度は、成果物中の主要な数値についてread_verified_factで確認してから
    判定を進めてください】。\n
    [BL-204] 成果物が特定の事物についての主張を含む場合、read_entityでレジストリの記録と
    突き合わせて確認できます。[BL-205] read_entityは名前を持つ事物専用です。対象を持たない
    単独の値（予算上限等）はread_verified_factを使ってください。
    【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
    write_agreement・read_entity・thinkです。{_THINK_TRAILER_SENTENCE}

    ■ 達成すべき【絶対目標(Goal)】:
    {goal}
    {goal_essence_text}

    ■ ★最終成果物として登録されている内容（最重要・必ずこれを精査せよ）:
    {deliverable_text}

    Return ONLY JSON:
    {{
        "passed": true/false,
        "feedback": "差し戻す場合の具体的な修正指示（目標との乖離を厳しく指摘すること）",
        "reasoning": "判定の根拠（成果物のどの部分が目標に達していないのか、要求された成果物のうち何が欠落しているのかを具体的に明示すること）"
    }}
    """
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "reviewer"
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_reviewer_qa, model=model_reviewer_qa, label="Reviewer QA",
        tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, READ_ENTITY_TOOL, THINK_TOOL], fallback={"passed": False, "feedback": "JSONフォーマットエラーのため差し戻します。"},
        state=state,
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

    # [BL-177] 通常の「Expertの成果物をUserがレビューする」ターンのみ、Detectorの2段監査パス
    # （BL-049/BL-054）と同型の段階化パイプラインへ分岐する。本質対話（BL-126）・Expert相談
    # 応答（BL-130）・差し戻し再送（BL-142/143）・終盤のPROJECT_COMPLETE宣言・初回ターンは
    # 対象外とし、既存の単発呼び出し（このifブロックの後に続く現行コード）をそのまま使う
    # （docs/design/back_log/BL-177/BL177_basic_design.md「スコープ」節）。
    _is_normal_review_turn = (
        bool(state["chat_history"])
        and not state.get("essence_dialogue_active")
        and not state.get("expert_pending_question")
        and not (state.get("drift_flag") or state.get("constraint_issue") in ["major"])
        and turn_count < max_turns - 2
    )
    if _is_normal_review_turn:
        global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID, _CURRENT_GOAL_TEXT, _CURRENT_PHASE_ID
        _CURRENT_CALLER_ROLE = "user"
        _CURRENT_TASK_ID = state.get("current_task_id", "")
        _CURRENT_PHASE_ID = state.get("current_phase", {}).get("phase_id", "")
        _CURRENT_GOAL_TEXT = user_goal

        # [BL-177 制約2] query_AI()は呼び出しごとにターン単位トラッカー（_LAST_WRITE_AGREEMENT_
        # SUCCEEDED等）をリセットする。4回query_AIを呼ぶため、各ステージ後にローカルへOR/後勝ちで
        # 集約し、関数末尾でグローバルへ書き戻す（generate_user_utterance_nodeの既存の読み取り
        # コードを変更せずに済ませるため）。
        _stage_wrote_agreement = False
        _stage_wrote_issue_resolution = False
        _stage_reasoning_text = ""
        _stage_goal_revision = None
        _stage_essence_proposal = None
        _stage_scheduling_decision = None  # [BL-191]

        def _absorb_stage_trackers():
            nonlocal _stage_wrote_agreement, _stage_wrote_issue_resolution, _stage_reasoning_text, _stage_goal_revision, _stage_essence_proposal, _stage_scheduling_decision
            _stage_wrote_agreement = _stage_wrote_agreement or get_last_write_agreement_succeeded()
            _stage_wrote_issue_resolution = _stage_wrote_issue_resolution or get_last_write_issue_resolve_or_defer_succeeded()
            _stage_reasoning_text = get_last_reasoning_text() or _stage_reasoning_text
            _stage_goal_revision = get_last_goal_revision() or _stage_goal_revision
            _stage_essence_proposal = get_last_essence_proposal() or _stage_essence_proposal
            # [BL-191] Stage4がschedule_task_focusを呼んでいれば、query_AI呼び出しごとにリセット
            # される_LAST_SCHEDULING_DECISIONを、他の_stage_*トラッカーと同じOR/後勝ちパターンで
            # 集約する。
            _stage_scheduling_decision = get_last_scheduling_decision() or _stage_scheduling_decision

        _scope_ctx = _build_task_scope_context(state, _conn)
        current_task_json = _scope_ctx["current_task_json"]
        verified_facts_json = _scope_ctx["verified_facts_json"]
        remaining_criteria_text = _scope_ctx["remaining_criteria_text"]
        deferred_notes_block = (
            "📌 【BL-082: 他タスクからの申し送り事項（先送り）】\n" + _scope_ctx["deferred_notes_text"] + "\n"
            if _scope_ctx["deferred_notes_text"] else ""
        )
        recent_history = state["chat_history"][-2:]
        stage_history_text = "\n".join(
            f"{'[あなた（発注者）の直前の発言]' if m['role'] == 'user' else '[Agent AIの直前の発言]'}\n{m['content']}"
            for m in recent_history
        )
        goal_essence_text = _get_goal_essence_text(_conn, state["run_id"])

        # ===== Stage 1: レビュー（ドメイン妥当性、read-only） =====
        review_prompt = (
            f"あなたは目標達成のプロジェクトオーナー（発注者）です。相手のAgent AIが提出した最新の"
            f"成果物を、これから4段階に分けてレビューします。今回はこの第1段（ドメイン妥当性レビュー）"
            f"のみを担当してください。承認判断・issueの記録・次の指示は後続の別ステージで行うため、"
            f"ここでは行わないでください。\n\n"
            f"【絶対目標】{user_goal}\n"
            f"{goal_essence_text}\n"
            f"【検算とドメインレビューの役割分担】数値の機械的検算（合計・比率・閾値比較等）は既に"
            f"Detector（監査システム）がpython_replで独立して実行済みです。あなたが同じ検算を"
            f"繰り返す必要はなく、その検算結果を信頼してよいものとします。代わりに、Detectorの"
            f"数値監査だけでは拾えない「ドメイン的な妥当性」に重きを置いてレビューしてください:\n"
            f"- その前提・計画は現実世界で本当に成立するか（法定の休憩・シフト要件、"
            f"物理的な運用可能性、予備・冗長性の欠如、安全規制等）。\n"
            f"- 数式としては辻褄が合っていても、現実の運用としては無理がある内訳・仮定をその場で"
            f"でっち上げていないか。\n"
            f"- [BL-134] 「最低N名」のような部分的な要件を、ゴール文が明示する時間帯・範囲等の"
            f"条件を無視して無条件に拡大解釈していないか。拡大解釈の根拠がゴール文中に無いのに"
            f"confidence=\"confirmed\"として確定されている値があれば指摘してください。\n"
            f"計算結果そのものに強い違和感がある場合に限り、あなた自身もpython_replで検算して"
            f"ください（毎回のルーティンとして再検算する必要はありません）。\n\n"
            f"【現在のタスク】\n{current_task_json}\n"
            f"【この値は確定済みです。再導出を指示・要求しないでください】\n{verified_facts_json}\n"
            f"【現在のタスクで未充足の要求項目】\n{remaining_criteria_text}\n"
            f"[R4] {_scope_ctx['whiteboard_text']}\n"
            f"{deferred_notes_block}"
            f"[BL-094: read_verified_fact/read_deliverable_fileで既存の決定と同期する] 数値の出所が"
            f"ゴール文の直接記載か、Agent自身の派生仮定かを見分けるため、必要に応じてこれらのツールで"
            f"確認してください。\n\n"
            f"[BL-204] Agentの主張が特定の事物についてのものである場合、read_entityでレジストリの"
            f"記録と突き合わせて確認できます。[BL-205] read_entityは名前を持つ事物専用です。"
            f"対象を持たない単独の値はread_verified_factを使ってください。\n\n"
            f"【今回レビューする直近のやり取り】\n{stage_history_text}\n\n"
            f"【重要】あなたが使えるツールはread_verified_fact・read_deliverable_file・python_repl・"
            f"read_entity・thinkです。{_THINK_TRAILER_SENTENCE}\n"
            f'Return ONLY JSON: {{"domain_concerns": "ドメイン妥当性上の懸念（無ければ空文字）", '
            f'"scope_compliant": true/false, "review_comment": "レビューの要点（次段へ引き継ぐ短い要約）"}}'
        )
        _reset_think_scratchpad()
        review_parsed, review_parse_failed = _query_and_parse_with_retry(
            review_prompt, client=client_user, model=model_user, label="User AI (Stage1: レビュー)",
            tools=[READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, PYTHON_REPL_TOOL, READ_ENTITY_TOOL, THINK_TOOL],
            fallback={"domain_concerns": "", "scope_compliant": True, "review_comment": ""},
            state=state,
        )
        _absorb_stage_trackers()
        if review_parse_failed:
            review_comment = "(Stage1レビューのJSON解析に失敗したため、要約なしで次段へ進みます)"
        else:
            review_comment = review_parsed.get("review_comment", "") or review_parsed.get("domain_concerns", "")

        # ===== Stage 2: issue確認 =====
        _open_escalations_text = _get_open_escalations_text(_conn, state["run_id"])
        _forced_escalated_issues_text = _get_forced_escalated_issues_text(_conn, state["run_id"], state.get("current_task_id", ""), state.get("round_count", 0))
        issue_prompt = (
            f"あなたは目標達成のプロジェクトオーナー（発注者）です。これは4段階レビューの第2段"
            f"（issue確認）です。第1段のレビュー結果を踏まえ、issue_logの未解決事項を確認・整理して"
            f"ください。承認判断や次の指示はまだ行わないでください。\n\n"
            f"【第1段（レビュー）の結果】{review_comment}\n\n"
            f"[BL-096: write_issue/read_issuesで軽微な懸念・訂正指示を引き継ぐ] Expertへ訂正指示を"
            f"出す際、それが後続タスクでも忘れてはならない指示であれば、write_issue(action_type="
            f"\"CREATE\", topic=\"<固定の識別文字列>\", description=\"Expertへの訂正指示: ...\")で"
            f"記録してください。【最低限、read_issuesを一度は呼び、過去に起票した未解決issueが"
            f"このタスクの範囲に関係しないか確認してください】。Expertの回答がその懸念を解消して"
            f"いれば、write_issue(action_type=\"RESOLVE\", topic=\"...\", resolution_note=\"...\")"
            f"で明示的にクローズしてください（issueをクローズする役目はあなたです）。\n"
            f"{_open_escalations_text}\n"
            f"{_forced_escalated_issues_text}\n"
            f"【重要：ゴール自体の文言と真の目的が矛盾していると気づいた場合の3ツール】\n"
            f"・escalate_premise_concern: ゴール文の制約・前提の文言が真の目的と矛盾していると"
            f"具体的根拠を持って判断した場合、自ら懸念を提起できます。\n"
            f"・resolve_premise_concern: 未解決のエスカレーションについて、検討の結果やはり文言"
            f"通りが正しいと判断した場合、却下してください。\n"
            f"・revise_goal: 未解決のエスカレーションを承認する場合に、ゴール文自体を該当箇所だけ"
            f"改定してください。承認する例外を体現するAgreementがあれば、freeze_agreement_idで"
            f"同時にFreezeしてください。\n\n"
            f"【今回レビューする直近のやり取り】\n{stage_history_text}\n\n"
            f"【重要】あなたが使えるツールはread_issues・write_issue・escalate_premise_concern・"
            f"resolve_premise_concern・revise_goal・freeze_agreement・thinkです。"
            f"{_THINK_TRAILER_SENTENCE}\n"
            f'Return ONLY JSON: {{"issues_handled": true/false, "remaining_concerns": '
            f'"未解決のまま残る懸念（無ければ空文字、次段へ引き継ぐ）"}}'
        )
        _reset_think_scratchpad()
        issue_parsed, issue_parse_failed = _query_and_parse_with_retry(
            issue_prompt, client=client_user, model=model_user, label="User AI (Stage2: issue確認)",
            tools=[READ_ISSUES_TOOL, WRITE_ISSUE_TOOL, ESCALATE_PREMISE_CONCERN_TOOL,
                   RESOLVE_PREMISE_CONCERN_TOOL, REVISE_GOAL_TOOL, FREEZE_AGREEMENT_TOOL, THINK_TOOL],
            fallback={"issues_handled": True, "remaining_concerns": ""},
            state=state,
        )
        _absorb_stage_trackers()
        remaining_concerns = "" if issue_parse_failed else (issue_parsed.get("remaining_concerns", "") or "")

        # ===== Stage 3: 統合承認判断（write_agreementを単独所有） =====
        agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])
        # [BL-178フォローアップ] 承認先のtarget_topicを明示的に注入する。従来はこの指定が無く、
        # LLMが「統合承認判断」という別トピックのDecisionエントリを新規CREATEしてしまい
        # （Expertの成果物＝entry_type="Deliverable"自体はProposedのまま更新されず）、
        # BL-176のゲート（_is_task_completedがentry_type="Deliverable"の最新行のみ判定）を
        # 永久に満たせずタスク遷移がブロックされ続ける実害が実ドライラン
        # （log/2026-08-05/1542, 1556）で確認された。BL-172のD-142が既に確立していた
        # 「正当な承認は既存Deliverableへのaction_type="UPDATE"」という規約をStage3にも
        # 明示的に持ち込む。
        _deliverable_agreement = _find_active_deliverable_agreement(
            _conn, state["run_id"], _CURRENT_PHASE_ID, _CURRENT_TASK_ID,
        )
        _deliverable_topic = _deliverable_agreement["topic"] if _deliverable_agreement else ""
        approval_prompt_base = (
            f"あなたは目標達成のプロジェクトオーナー（発注者）です。これは4段階レビューの第3段"
            f"（統合承認判断）です。第1段（レビュー）・第2段（issue確認）の結果を踏まえ、"
            f"Agent AIの成果物を承認するかどうかだけを判断してください。次タスクへの指示はまだ"
            f"行わないでください（後続の第4段で行います）。\n\n"
            f"【第1段（レビュー）の結果】{review_comment}\n"
            f"【第2段（issue確認）の結果】issues_handled等の対応済み、残存懸念: {remaining_concerns or '(なし)'}\n\n"
            f"🔥 【発注者としての絶対的なスタンス】あなたは妥協を許さないプロジェクトオーナーです。"
            f"相手が「制約が厳しい」「要件を満たせない」と泣き言を言ってきても、絶対に【絶対目標】の"
            f"ハードルを下げないでください。ただし、緩和を求めているのが「動かせない真の制約」なのか"
            f"「議論の前提として例示的に与えられているだけの見直し可能な条件」なのかは見極めてください。\n\n"
            f"[BL-197: 承認基準はacceptance_criteriaを超えない] 上記の妥協なきスタンスは、絶対目標の"
            f"ハードな数値制約（予算・SLA等）を安易に緩めないという意味であり、そのタスク自身の"
            f"【現在のタスクで未充足の要求項目】（acceptance_criteria）を超える独自の検証水準や、"
            f"特定のデータ取得手段・ソフトウェア・ファイル形式を新たに義務付けてよいという意味では"
            f"ありません。未充足の要求項目が既に満たされていれば承認してください。第2段でAgent AIが"
            f"正当にDEFERした懸念（別タスクの責務として先送りされたもの）を、このタスクの未解決懸念"
            f"として承認却下の理由にしないでください。\n\n"
            f"【絶対目標】{user_goal}\n"
            f"{goal_essence_text}\n"
            f"【現在のタスクで未充足の要求項目】\n{remaining_criteria_text}\n"
            f"[R4] {_scope_ctx['whiteboard_text']}\n\n"
            f"【プロジェクトの合意・決定事項・検討状況DB】\n{agreements_text}\n\n"
            f"承認する場合は、必ずwrite_agreementツールを呼び出して確定してください（status="
            f"\"Approved\"または条件付きなら\"Approved_with_Conditions\"）。"
            + (
                f"【重要・厳守】承認はAgentの成果物（Deliverable）自体を更新することで記録して"
                f"ください: action_type=\"UPDATE\", entry_type=\"Deliverable\", "
                f"target_topic=\"{_deliverable_topic}\"（この文字列をそのまま指定）。"
                f"承認判断を新しいDecisionエントリとして別途CREATEしてはいけません——それでは"
                f"Agentの成果物自体がProposedのまま更新されず、次タスクへ進めなくなります。"
                f"decision_whatは短い承認コメントで構いません（全文を書き写す必要はありません。"
                f"あなたが書く承認コメントが成果物本文を上書きすることはありません）。成果物本文"
                f"自体の内容を変更・追記したい場合は、decision_whatではなくeditsパラメータ"
                f"（old_text/new_text）を使ってください。\n"
                if _deliverable_topic else ""
            )
            + f"承認しない場合は"
            f"write_agreementを呼ばず、approval_status=\"Rejected\"としてください。まだ判断材料が"
            f"不足している場合はapproval_status=\"Pending\"としてください。\n\n"
            f"[BL-204] 承認を保留・却下する前に、read_entityでこの課題の事物について既に登録済みの"
            f"事実を確認してください。既に確認できる事実をAgentへ再要求するのは避けてください。"
            f"[BL-205] read_entityは名前を持つ事物専用です。entity未指定で「とりあえず一覧」を"
            f"見る目的では使わないでください（一覧は名前のみで属性を含みません）。\n\n"
            f"【今回レビューする直近のやり取り】\n{stage_history_text}\n\n"
            f"【重要】あなたが使えるツールはwrite_agreement・read_entity・thinkです。{_THINK_TRAILER_SENTENCE}\n"
            f'Return ONLY JSON: {{"approval_status": "Approved/Approved_with_Conditions/Rejected/Pending", '
            f'"approval_reason": "承認・却下・保留の理由"}}'
        )
        # [BL-177] LLMの自己申告（approval_status）とツール呼び出し結果（get_last_write_agreement_
        # succeeded）の食い違いは、Stage4のLLMにではなくここでPythonコードが機械的に判定する
        # （BL-091/BL-176と同じ「自己申告を信用しない」原則）。食い違えばStage3自体を訂正指示付きで
        # 最大2回まで再試行し、Stage4へは進めない。使い切っても解消しなければApprovalRecordingFailed
        # という専用ラベルでStage4へ渡す（design: BL177_basic_design.md Stage3節）。
        _approval_mismatch_notice = ""
        approval_status = "Pending"
        approval_reason = ""
        for _approval_attempt in range(3):
            _reset_think_scratchpad()
            approval_parsed, approval_parse_failed = _query_and_parse_with_retry(
                approval_prompt_base + _approval_mismatch_notice, client=client_user, model=model_user,
                label="User AI (Stage3: 統合承認判断)", tools=[WRITE_AGREEMENT_TOOL, READ_ENTITY_TOOL, THINK_TOOL],
                fallback={"approval_status": "Pending", "approval_reason": ""}, state=state,
            )
            _absorb_stage_trackers()
            if approval_parse_failed:
                approval_status = "Pending"
                approval_reason = "(承認判断のJSON解析に失敗しました)"
                break
            approval_status = approval_parsed.get("approval_status", "Pending")
            if approval_status not in RESOLVING_DELIVERABLE_STATUSES | {"Rejected", "Pending"}:
                approval_status = "Pending"
            approval_reason = approval_parsed.get("approval_reason", "")
            if approval_status not in RESOLVING_DELIVERABLE_STATUSES:
                break  # Rejected/Pendingはwrite_agreement成功の自己申告を伴わないため対象外
            # [BL-178フォローアップ] get_last_write_agreement_succeeded()は「write_agreementが
            # 何かしら成功したか」しか見ておらず、Stage3のLLMがtarget_topicを誤り「統合承認判断」
            # という別のDecisionエントリをCREATEしてしまうケース（実ドライランで確認）を検知
            # できない。_is_task_completed（BL-167、BL-176のゲートと同一の判定基準）を併用し、
            # 「Expertの成果物（Deliverable）自体が実際にResolving相当へ更新されたか」まで
            # 機械的に確認する。
            if get_last_write_agreement_succeeded() and _is_task_completed(_conn, state["run_id"], _CURRENT_TASK_ID):
                break  # 自己申告とツール呼び出し結果（Deliverable自体の更新）が一致
            print(
                f"  ⚠️ [User AI Stage3] BL-177/BL-178: approval_status='{approval_status}'ですが、"
                f"Expertの成果物（Deliverable）自体がApproved相当へ更新されたことを確認できません"
                f"（試行{_approval_attempt + 1}/3）。"
            )
            _approval_mismatch_notice = (
                "\n\n【訂正指示】あなたは前回approval_status=\"" + approval_status + "\"と回答しましたが、"
                "Agentの成果物（Deliverable）自体が承認済みへ更新されたことを確認できませんでした。"
                "write_agreementを呼ぶ際、action_type=\"UPDATE\", entry_type=\"Deliverable\", "
                "target_topic=\"" + _deliverable_topic + "\"（この文字列をそのまま指定）で、"
                "新しいDecisionエントリではなくAgentの成果物自体を更新してください。\n"
            )
        else:
            print("  🚨 [User AI Stage3] BL-177: リトライを使い切っても承認記録の食い違いが解消しませんでした。ApprovalRecordingFailedとして扱います。")
            approval_status = "ApprovalRecordingFailed"

        # ===== Stage 4: 次タスク指示 / 現タスク修正指示 / 承認記録失敗の待機メッセージ =====
        _transition_notice = _build_task_transition_blocked_notice(state)  # [BL-125/BL-176/BL-190]
        _escalation_resume_notice = _build_escalation_resume_notice(state)  # [BL-096]
        _task_focus_transition_notice = _build_task_focus_transition_notice(state)  # [BL-191]
        _task_focus_state_text = _build_task_focus_state_text(state)  # [BL-191]
        if approval_status in RESOLVING_DELIVERABLE_STATUSES:
            _stale_past_tasks_text = _build_stale_past_tasks_text(_conn, state["run_id"])  # [BL-191]
            _scheduling_history_text = _build_scheduling_history_text(_conn, state["run_id"])  # [BL-191]
            stage4_system_prompt = (
                f"あなたは目標達成のプロジェクトオーナー（発注者）です。これは4段階レビューの"
                f"第4段（最終段）です。第3段で成果物の承認（{approval_status}）が確定しました。"
                f"あなたの役割は、Task Plannerが作成した計画に従い、Agent AIへ**1度に1つずつ**"
                f"次のタスクを指示することです（一気に複数指示すると相手が混乱するため厳禁）。\n\n"
                f"【絶対目標】{user_goal}\n"
                f"{goal_essence_text}\n"
                f"📊 [プロジェクト進行計画]\n{json.dumps(state.get('phases', []), ensure_ascii=False, indent=2)}\n\n"
                f"{_task_focus_state_text}"
                f"{_stale_past_tasks_text}"
                f"{_scheduling_history_text}"
                f"[BL-191] 過去の承認済みタスクの手戻りが必要だと判断した場合は、通常の次タスク"
                f"指示文とは別に、schedule_task_focusツールで明示的にスケジューリング判断を"
                f"記録してください。'redirect_backward'で今すぐ過去タスクへ完全に切り替えるか、"
                f"'joint_focus'で現在のタスクを進めつつ過去タスクを併記対象として明示するかを"
                f"選べます。schedule_task_focusを呼んでも、Expertへの通常の次タスク指示文は"
                f"別途必ず書いてください（このツールは指示文の代わりにはなりません）。\n"
                f"【承認理由（第3段）】{approval_reason}\n"
                f"{_escalation_resume_notice}"
                f"{_transition_notice}"
                f"{_task_focus_transition_notice}"
                f"{_BL192_DIRECTIVE_QUALITY_BLOCK}"
                f"【同じ検証・計算を繰り返さない】必要な確認は既に前段で完了しています。ここでは"
                f"次タスクへの具体的な指示文を簡潔に書いてください。\n"
            )
            if turn_count >= max_turns - 4:
                stage4_system_prompt += (
                    "🚨 【終盤】計画された全タスクの成果物が出揃っていれば、"
                    "『すべてのタスクが完了したため、プロジェクトを完了とする。[PROJECT_COMPLETE]』"
                    "と宣言してください。相手に最終報告書の作成を指示しないでください"
                    "（統合はIntegratorが行います）。\n"
                )
        elif approval_status == "ApprovalRecordingFailed":
            stage4_system_prompt = (
                f"あなたは目標達成のプロジェクトオーナー（発注者）です。これは4段階レビューの"
                f"第4段（最終段）です。第3段で承認処理を試みましたが、システム側の技術的な理由で"
                f"承認の記録が完了しませんでした（Agent AIの成果物の内容自体に問題があったわけでは"
                f"ありません）。Agent AIの成果物内容には一切言及・評価しないでください。"
                f"「承認手続きの確認中のため、少し待ってほしい」という趣旨の短い待機メッセージのみを"
                f"書いてください。存在しない欠陥や修正点をでっち上げないでください。\n"
            )
        else:
            stage4_system_prompt = (
                f"あなたは目標達成のプロジェクトオーナー（発注者）です。これは4段階レビューの"
                f"第4段（最終段）です。第3段の判断（{approval_status}）により、今回は承認せず、"
                f"Agent AIへ現タスクの修正指示を出します。\n\n"
                f"【絶対目標】{user_goal}\n"
                f"{goal_essence_text}\n"
                f"【却下・保留の理由（第3段）】{approval_reason}\n"
                f"【第1段（レビュー）の結果】{review_comment}\n"
                f"【第2段（issue確認）で残った懸念】{remaining_concerns or '(なし)'}\n\n"
                f"矛盾の内容とその理由を明示し、Agent AIが成果物のどこをどう直すべきか具体的に"
                f"示した修正指示を出してください。次タスクへの移行はまだ指示しないでください。\n"
                f"[BL-197: 過剰な手段の指定を避ける] 修正指示は、そのタスクのacceptance_criteriaを"
                f"満たすために必要な内容に留めてください。特定のデータ取得元・ファイル形式・解析"
                f"ソフトウェア（例：特定の地図データ配布元、特定のGISツール等）を新たに義務付けたり、"
                f"取得日時・ハッシュ値等の記録項目を追加で要求したりしないでください。Agent AIが"
                f"選んだ実現手段が要求項目を満たしているかどうかで判断し、手段そのものを指定しない"
                f"でください。\n"
                f"[BL-204] 修正指示を出す前に、read_entityでこの課題の事物について既に登録済みの"
                f"事実を確認してください。既に確認できる事実の再取得を修正指示に含めないでください。\n"
                f"[BL-205] read_entityは名前を持つ事物専用のツールです。entity=\"\"で「とりあえず"
                f"全部見る」ために呼ばないでください——それでは名前の一覧しか返らず、属性は"
                f"含まれません。確認したい事物の名前が分かっている場合にのみ、entity指定で"
                f"呼んでください。\n"
            )
        stage4_system_prompt += (
            f"\n【重要】あなたが使えるツールはthink・schedule_task_focus（[BL-191]過去タスクの"
            f"手戻りが必要な場合のみ）・read_entityです。{_THINK_TRAILER_SENTENCE}\n"
        )
        _reset_think_scratchpad()
        stage4_messages = [{"role": "system", "content": stage4_system_prompt}]
        if is_stateless_mode:
            _recent = state["chat_history"][-config["chat_history_window"]:] if state["chat_history"] else []
        else:
            _recent = state["chat_history"]
        for msg in _recent:
            _role = "assistant" if msg["role"] == "user" else "user"
            stage4_messages.append({"role": _role, "content": msg["content"]})

        content = query_AI(stage4_messages, client=client_user, model=model_user, label="User AI (Stage4)",
                            tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL, READ_ENTITY_TOOL], state=state)
        _absorb_stage_trackers()
        if content is None or content.strip() == "" or content == "(APIから空の応答が返されました)":
            for _retry in range(3):
                print(f"⚠️ [User AI Stage4] 空応答を検知。リトライ {_retry + 1}/3...")
                _reset_think_scratchpad()
                content = query_AI(stage4_messages, client=client_user, model=model_user, label="User AI (Stage4)",
                                    tools=[THINK_TOOL, SCHEDULE_TASK_FOCUS_TOOL, READ_ENTITY_TOOL], state=state)
                _absorb_stage_trackers()
                if content and content.strip() and content != "(APIから空の応答が返されました)":
                    break
            else:
                raise RuntimeError("User AI(Stage4)の応答取得に3回連続で失敗しました。実行を中断します。")

        # [BL-177 制約2] 集約したトラッカーをグローバルへ書き戻す（generate_user_utterance_nodeの
        # 既存の読み取りコードは無変更で正しく動作する）。
        global _LAST_WRITE_AGREEMENT_SUCCEEDED, _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED, _LAST_REASONING_TEXT, _LAST_GOAL_REVISION, _LAST_ESSENCE_PROPOSAL, _LAST_SCHEDULING_DECISION
        _LAST_WRITE_AGREEMENT_SUCCEEDED = _stage_wrote_agreement
        _LAST_WRITE_ISSUE_RESOLVE_OR_DEFER_SUCCEEDED = _stage_wrote_issue_resolution
        _LAST_REASONING_TEXT = _stage_reasoning_text
        _LAST_GOAL_REVISION = _stage_goal_revision
        _LAST_ESSENCE_PROPOSAL = _stage_essence_proposal
        _LAST_SCHEDULING_DECISION = _stage_scheduling_decision  # [BL-191]
        return content

    # [BL-104] プロンプトキャッシュのヒット率向上のため、内容が変わらない固定の指示文を
    # 先頭付近にまとめ、ターンごとに変わる動的な内容（決定事項DB・直近の行動タイムライン・
    # 現在タスク情報等）は末尾側に配置する（call_expertと同じ原則、詳細はBL104_basic_design.md）。
    # ただし「後述の【現在のタスクで未充足の要求項目】」「上記の【この値は確定済みです】」等、
    # 他ブロックへの位置的参照を持つ箇所は、参照先との相対位置を崩さないよう並び替えの対象外とする。
    # [BL-185] さらに、動的な内容の中でも「決定事項DB・タスク情報」等の状況説明と、
    # 「差し戻し通知・最終盤指示」等の直近の是正内容は区別し、後者をchat_historyより後ろへ
    # 独立したsystemメッセージ（system_prompt_trailing）として配置する（詳細は下記コメント）。
    system_prompt = ""

    if user_always_remembers or state["turn_count"] == 1:
        system_prompt = (f"""
            あなたは目標を達成するための優秀な【プロジェクトオーナー（発注者）】です。\n
            相手のAIはあなたのアシスタントであり、作業を行う実務担当者です。\n
            あなたの【絶対目標】は以下の通りです:\n
            👉 {user_goal}\n\
            \n
            {_get_goal_essence_text(_conn, state["run_id"])}\n
            【厳守事項】\n
            ・あなたは「指示を出す側」です。「承知いたしました」「お手伝いします」のようなアシスタント的発言は絶対に行わないでください。\n
            ・相手に作業を要求し、出てきた提案を要点を簡潔にレビューしてフィードバックを与えてください。\n
            ・【現在の決定事項・検討状況DB】に「🤔 検討中」の項目がある場合、その論点についてあなたから見解や方向性を提示し、議論をリードしてください。\n
            ・各タスクの議論がまとまり合意に達したら、必ず相手のAIに対して『このタスク単体の成果物（詳細仕様書や計画書）』を出力するように指示してください。\n
            　ただし、後述の【現在のタスクで未充足の要求項目】が「(未充足の項目はありません)」であり、\n
            　かつ【R4: 現在のホワイトボード】に既にこのタスクの成果物が存在する場合は、その成果物は\n
            　既に提出・承認済みです。同じ内容の再提出を重ねて指示しないでください（相手のAIが\n
            　「既に提出したのに何を出力すればよいのか」と混乱する原因になります）。この場合は\n
            　次のタスクへ議論を進めるか、真に追加で必要な修正点がある場合のみ、その点を具体的に\n
            　指摘してください。\n
            ・口調は論理的でスマートで紳士に徹してください。冗長な表現は避け、簡潔に論理的に回答してください。\n
            ・冗長な挨拶、感謝の言葉は不要です\n\n
            """
        )
    else:
        system_prompt = f"あなたは目標を達成するためにエージェントAIをリードする[発注者]です。\n"

    system_prompt += (f"""
        \n🔥 【発注者としての絶対的なスタンス（質について）】\n
         あなたは妥協を許さないプロジェクトオーナーです。相手（Agent AI）が「制約が厳しい」
        「要件を満たせない」と泣き言を言ってきても、絶対に【絶対目標】のハードルを下げないでください。\n
        「制約緩和の検討」や「重要要件の放棄」を提案された場合は、それを却下し、
        『プロとして制約内に収めるための別の技術的アプローチや代替案を考え直せ』と厳しく突き返してください。\n
        \n
        【制約と条件の切り分け（重要）】\n
        ただし、却下する前に、相手が緩和を求めているのが「動かせない真の制約」（総予算の上限、\n
        法規制、安全基準等）なのか、それとも「議論の前提として例示的に与えられているだけの\n
        見直し可能な条件」（特定の調達方法を前提にした単価、特定の運用パターンの例示的な数値等）\n
        なのかを、あなた自身も都度見極めてください。ゴール文にはこの2種類が区別なく並記されている\n
        ことがあります。後者だと判断できる場合は、思考停止で却下するのではなく、その前提自体を\n
        見直す代替案（調達方法の変更、仕様の見直し等）を相手に検討させる指示に切り替えてください。\n
         <あなたの発話や指示の根拠や参考にした情報、思考過程を示してください。>\n
        \n
        【重要：ゴール自体の文言と真の目的が矛盾していると発注者自身が気づいた場合の3ツール】\n
        あなたは以下の3つのツールを使える立場にあります（Agent AI側からの提起分の解決だけでなく、\n
        あなた自身が矛盾に気づいた場合の起点にもなります）：\n
        ・escalate_premise_concern: あなた自身がゴール文の制約・前提の文言が真の目的と矛盾している\n
        　と具体的根拠を持って判断した場合、自ら懸念を提起できます（一般的な「厳しい」という\n
        　感想では使わないこと。狭く構造化された懸念に限定）。\n
        ・resolve_premise_concern: 未解決のエスカレーション（下記に表示される場合があります）に\n
        　ついて、検討の結果やはり文言通りが正しいと判断した場合、却下してください。\n
        ・revise_goal: 未解決のエスカレーションを承認する場合に、ゴール文自体を該当箇所だけ改定\n
        　してください。承認する例外を体現するAgreementがあれば、freeze_agreement_idで同時に\n
        　Freezeし、Detectorが同じ論点を無限に再審議し続けることを防いでください。\n
        ・freeze_agreement: エスカレーションとは無関係に、これ以上覆されるべきでないと判断した\n
        　確定事項（人間として最終決定した絶対的な数値等）を単独で永久ピン留めする際にも使えます\n
        　（Freezeは取り消せないため、真に恒久化すべき場合のみ使用）。\n
    """)

    system_prompt += (
        "\n【検算とドメインレビューの役割分担】\n"
        "Expertの提案に含まれる数値の機械的な検算（合計・比率・閾値比較等）は、"
        "既にDetector（監査システム）がpython_replで独立して実行済みです。"
        "あなたが同じ検算をもう一度繰り返す必要はなく、その検算結果を信頼してよいものとします。\n"
        "その代わり、あなたはプロジェクトオーナーとして、Detectorの数値監査だけでは拾えない"
        "「ドメイン的な妥当性」に重きを置いてレビューしてください:\n"
        "- その前提・計画は現実世界で本当に成立するか（法定の休憩・シフト要件、"
        "物理的な運用可能性、予備・冗長性の欠如、安全規制等）。\n"
        "- 数式としては辻褄が合っていても、現実の運用としては無理がある内訳・仮定を"
        "その場ででっち上げていないか。\n"
        "- [BL-134] 「最低N名」のような部分的な要件を、ゴール文が明示する時間帯・範囲等の"
        "条件を無視して無条件に拡大解釈（例：特定時間帯限定の要件を24時間・全期間へ一般化）して"
        "いないか。拡大解釈の根拠がゴール文中に無いのにconfidence=\"confirmed\"として確定されて"
        "いる値があれば、その場で指摘してください。\n"
        "計算結果そのものに強い違和感がある場合に限り、あなた自身も python_repl で検算してください"
        "（毎回のルーティンとして再検算する必要はありません）。\n"
        "[BL-087 Stage4] さらに、上記の【🎯 本質】に照らして、Expertの提案の数値・条件設定が"
        "本質から乖離していないかも確認してください。数式・ドメイン的妥当性の両方で問題が無くても、"
        "本質に照らして違和感がある場合（例: 本質が「実質的な利便性の確保」なのに、手段の細部の"
        "帳尻合わせに終始し本質を見失っている等）は、その点を具体的に指摘してください。疑義のある"
        "数値は、python_replでの検算に加え、あなた自身の判断でも根拠を問い直してください。\n"
    )

    system_prompt += (
        "\n【同じ検証・計算を繰り返さない（重要）】\n"
        "ツール呼び出しの回数には上限があります。同じ論点をpython_replで繰り返し再確認しないで"
        "ください。各検証項目は2回程度の計算・確認で十分です。新しい数値や新しい論点が無いまま"
        "「念のため再確認」を重ねると、実際の発言を書く余地が無くなり、上限到達時に強制的に"
        "打ち切られたテキスト応答とせざるを得なくなります。必要な検算が終わったら、それ以上の"
        "確認は行わず、直ちに発言の記述に移ってください。\n"
    )

    # [§13.2/§13.3] 3モードは排他（同時に複数立たない前提）。elif連鎖で必ずどれか1つの
    # 固定文面だけが選ばれるようにする（複数モードの文面を混ぜるとキャッシュ安定性・可読性が
    # 失われるため）。切替トリガーはそれぞれ1つの明確なフラグの読み取りのみ（§13.1）。
    if state.get("essence_dialogue_active"):
        # [BL-126 Stage D/§13.2] Essence Dialogue応答モード: Facilitatorが本質対話を開始し、
        # ゴールの前提・制約の文言そのものについて対話している。通常の成果物レビューではなく、
        # Facilitatorの直近の問いかけに応答することが目的。
        system_prompt += (
            "\n🧭 【BL-126: 本質対話（Essence Dialogue）応答モード】\n"
            "これは通常のタスク成果物レビューではありません。ファシリテーターが、ゴールの前提・"
            "制約の文言が真の目的と矛盾しているのではという懸念を提起し、あなた（発注者）との"
            "対話を通じて方向性を模索しています。\n"
            f"現在の提起（topic）: {state.get('essence_dialogue_topic', '')}\n"
            "直近のファシリテーターの発言（chat_history末尾）に応答してください。まだ検討の余地が"
            "あればさらに議論を深め、方向性に納得できた場合は"
            "write_agreement(entry_type=\"EssenceProposal\", status=\"Approved\", "
            "action_type=\"UPDATE\", target_topic=\"" + state.get('essence_dialogue_topic', '') + "\", "
            "topic=\"" + state.get('essence_dialogue_topic', '') + "\", decision_what=\"承認します\", "
            "reason_why=\"<承認理由>\")を呼んで確定承認してください（この承認により、後続の"
            "計画再構成がトリガーされます）。承認しない場合は、その理由を明示した上で議論を"
            "続けてください。\n"
        )
    elif state.get("expert_pending_question"):
        # [BL-130/§13.2] Expert相談応答モード: Agent AIが今ターン成果物ではなく質問を投げてきた
        # 場合、通常の成果物レビュー文面ではなく、質問への回答のみを求める固定文面に切り替える。
        system_prompt += (
            "\n🗨️ 【BL-130: Agent AIからの相談（成果物ではありません）】\n"
            f"Agent AIは今回、成果物を提出せず質問を投げかけています。\n質問: {state['expert_pending_question']}\n"
            f"理由: {state.get('expert_blocking_reason', '')}\n"
            "これは通常のタスク成果物レビューではありません。write_agreementの呼び出しやタスク進行の"
            "判断は不要です。この質問にのみ、明確かつ簡潔に回答してください。\n"
        )

    # ここから先は実行中に変化する動的な内容。[BL-185] ユーザー指定順（視座は上から下、
    # 文脈は過去から現在）で提示するため、system_promptを先頭システムメッセージ用
    # （system_prompt_leading）と末尾システムメッセージ用（system_prompt_trailing）の
    # 2つに分けて組み立てる。system_prompt内でテキスト位置をどう並べても、messages配列は
    # [system, ...chat_history]という構造上chat_history側が常に物理的に後ろへ来るため、
    # 「差し戻し情報を本当に最後に読ませる」にはchat_historyより後ろへ新規メッセージを
    # 追加する必要がある（BL-178でcall_expertに導入した構成と同型。実ログ
    # log/2026-08-06/1149で、差し戻し直後のUser AIがchat_history末尾（Expertの完了報告）に
    # 引きずられ、削除されたはずの「前回の完了宣言」をそのまま繰り返した実害を確認、
    # 詳細はBL185_basic_design.md）。
    system_prompt_leading = system_prompt
    system_prompt_trailing = ""

    _conn = get_active_conn()
    agreements_text = _build_agreements_context_from_db(_conn, state["run_id"])

    # [BL-103] 従来はget_decisions_from_dbの全件を毎ターン無制限に展開しており、Expert側の
    # 窓付きhydrate_context（expert_history_windowでスライス）と非対称かつ長時間runで
    # 際限なく肥大化するリスクがあった。Expertと同じ共通ヘルパーに統一し、issue_logの
    # escalated行（recencyに関係ない pin）も併せて注入する。
    timeline_str = _build_hydrate_context_from_db(_conn, state["run_id"], config)
    escalation_pin = _build_escalation_pin_text(_conn, state["run_id"], state.get("current_task_id", ""), state.get("round_count", 0))
    if escalation_pin:
        timeline_str += f"\n\n【⚠️エスカレーション中の懸念（要対応、issue_log）】\n{escalation_pin}"
    # [BL-194] DEFER済み（別タスクへの受け皿が確定済み）の懸念は非強制トーンで別見出しに
    # 分離する。log/2026-08-08/1514で、task_2_1自身への自己先送り6件がここでも「要対応」
    # 側に混入し続け、User AIが同じ懸念を繰り返し督促され続けていた（DEFERの実効性が
    # 消えていた事故の一部）。
    deferred_issue_pin = _build_deferred_issue_pin_text(_conn, state["run_id"], state.get("current_task_id", ""))
    if deferred_issue_pin:
        timeline_str += f"\n\n【📤 対応予定が確定済みの懸念（参考・現タスクでは対応不要、issue_log）】\n{deferred_issue_pin}"
    # [BL-194] ACKNOWLEDGE中（現在タスクの責務であり対応中）の懸念も前向きなトーンで表示する。
    acknowledged_issue_pin = _build_acknowledged_issue_pin_text(_conn, state["run_id"], state.get("round_count", 0))
    if acknowledged_issue_pin:
        timeline_str += f"\n\n【🛠 現在のタスクで対応中の懸念（issue_log）】\n{acknowledged_issue_pin}"
    # [BL-136] status='open'（minor）行も参考情報として可視化する（従来はescalated行のみ）。
    open_issue_pin = _build_open_issue_pin_text(_conn, state["run_id"])
    if open_issue_pin:
        timeline_str += f"\n\n【ℹ️ 未解決の軽微な懸念（参考、issue_log）】\n{open_issue_pin}"
    # [BL-145] status='planned'（Reflectorの正当性監査によりtask_plannerが計画へ組み込んだ
    # issue）も参考情報として可視化する。対応を強制しない（デッドロック回避）。
    planned_issue_pin = _build_planned_issue_pin_text(_conn, state["run_id"])
    if planned_issue_pin:
        timeline_str += f"\n\n【📋 計画済みissue（参考、対応task_idあり、issue_log）】\n{planned_issue_pin}"

    system_prompt_trailing += (f"""
        \n現在までの決定事項・検討状況DB】\n
        {agreements_text}\n\n
        【直近の各役割の行動、評価、その理由リスト】\n
        {timeline_str}\n\n
    """)

    phases_json = json.dumps(state.get("phases", []), ensure_ascii=False, indent=2)

    # BL-023: 現在タスクの範囲・依存確定値・充足状況を明示し、指示のスコープを限定する
    _scope_ctx = _build_task_scope_context(state, _conn)
    current_task_json = _scope_ctx["current_task_json"]
    verified_facts_json = _scope_ctx["verified_facts_json"]
    remaining_criteria_text = _scope_ctx["remaining_criteria_text"]

    #Task Plannerが作成したフェーズとタスクを明示する
    system_prompt_trailing += (f"""
        \n📊 [プロジェクト進行計画]
        目標達成への道しるべとして、Task Plannerが作成したフェーズとタスクの一覧を以下に示します。\n
        {phases_json}\n\n

        あなたの役割は、上記の計画に従ってエージェントAIに**1度に1つずつ**タスクを指示し、成果物をレビューして着実に進捗させることです。\n
        （※一気に複数のタスクを指示すると相手が混乱するため、絶対に避けてください）\n

        📏 【指示のスコープについて（厳守・質への非妥協性とは別軸、BL-023）】\n
        1回の指示で要求してよい内容は、以下の「現在のタスク」の acceptance_criteria の範囲に厳密に限定してください。\n
        範囲外の追加要求（他タスクの依存項目の前倒し要求、まだ指示していない後続タスクの内容の混入など）は、\n
        たとえ関連性が高く見えても行わないでください。それは次のタスクの役目です。\n
        [BL-197: 手段の過剰な指定を避ける] 同様に、acceptance_criteriaの文言（「マトリクス化し確定する」\n
        「地図上に明示する」等）を、特定のデータ取得元・専用ソフトウェア・ファイル形式・検証ログの\n
        提出まで義務付けてよいという意味に拡大解釈しないでください。要求項目が満たされているかどうかは\n
        提示された結論の妥当性で判断し、Agent AIが選んだ実現手段（一次資料の参照・web_searchでの\n
        確認・工学的仮定の明記等）を、より厳格な手段への置き換えを理由に不足として扱わないでください。\n

        【現在のタスク】\n
        {current_task_json}\n

        【この値は確定済みです。再導出を指示・要求しないでください】\n
        {verified_facts_json}\n

        【現在のタスクで未充足の要求項目（これ以外を新たに追加要求しないこと）】\n
        {remaining_criteria_text}\n

        [R4] {_scope_ctx["whiteboard_text"]}\n

        {"📌 【BL-082: 他タスクからの申し送り事項（先送り）】" + chr(10) + _scope_ctx["deferred_notes_text"] if _scope_ctx["deferred_notes_text"] else ""}
    """)

    # [BL-086] Expert/自分自身が提起した未解決エスカレーションがあれば、今回の発言で
    # 必ずresolve_premise_concern（却下）かrevise_goal（承認・ゴール改定）で解決させる。
    _open_escalations_text = _get_open_escalations_text(_conn, state["run_id"])
    if _open_escalations_text:
        system_prompt_trailing += f"\n{_open_escalations_text}\n"

    # [BL-136] issue_logのescalated行（未先送り）についても、BL-086と同様に今回の発言で
    # 必ずRESOLVEかDEFERを呼ばせる（従来は受動的なpinのみで強制力がなかった）。
    _forced_escalated_issues_text = _get_forced_escalated_issues_text(_conn, state["run_id"], state.get("current_task_id", ""), state.get("round_count", 0))
    if _forced_escalated_issues_text:
        system_prompt_trailing += f"\n{_forced_escalated_issues_text}\n"

    system_prompt_trailing += _build_detector_observations_block(state)

    system_prompt_trailing += (
        "\n[BL-094: read_verified_fact/read_deliverable_fileで既存の決定と同期する]\n"
        "上記の【この値は確定済みです】は現在タスクに関連する確定値の一部にすぎません。"
        "read_verified_factは全フェーズ・全タスクを横断して、変数名やキーワードから確定値"
        "（値・理由・引用元・confidence）を検索できます。read_deliverable_fileは過去タスクの"
        "成果物全文（その値がどんな前提・議論を経て確定したか）を読めます。【最低限、iter=1で"
        "一度は、現在のタスクや直近のAgentの発言に関連しそうなキーワードでread_verified_fact"
        "を呼び、他タスクで既に確定・仮定された値と食い違う指示を出そうとしていないか確認して"
        "ください】。思考中に「これは前のタスクで既に決まっていたはずでは」という疑問が浮かんだ"
        "場合も、その都度これらのツールで確認してください。\n"
        "\n【BL-093: thinkツールで検討過程を残す】" + _BL093_THINK_VALUE_PARAGRAPH + "\n"
        "\n[BL-096: write_issue/read_issuesで軽微な懸念・訂正指示を引き継ぐ]\n"
        "Expertへ訂正指示を出す際、それが後続タスクでも忘れてはならない指示であれば、"
        "write_issue(action_type=\"CREATE\", topic=\"<固定の識別文字列>\", "
        "description=\"Expertへの訂正指示: ...\")で記録してください。【最低限、iter=1で一度は"
        "read_issuesを呼び、自分（またはDetector）が過去に起票した未解決issueがこのタスクの"
        "範囲に関係しないか確認してください】。Expertの回答がその懸念を解消していれば、"
        "write_issue(action_type=\"RESOLVE\", topic=\"...\", resolution_note=\"...\")で"
        "明示的にクローズしてください（issueをクローズする役目はあなたです）。"
        "[BL-140] 直前のthinkツールのscratch_concernsは、このツール呼び出しループの中だけで"
        "消える一時メモであり、後続タスクへは一切引き継がれません。持ち越したい懸念を"
        "scratch_concernsに書くだけで満足せず、必ずwrite_issueで記録してください。\n"
        "[BL-204] 判断が特定の事物についての主張に関わる場合、read_entityでレジストリの記録と"
        "突き合わせて確認できます。[BL-205] read_entityは名前を持つ事物専用です。対象を持たない"
        "単独の値（予算上限等）はread_verified_factを使い、read_entityをentity未指定の"
        "「一覧確認」目的で多用しないでください。\n"
        "【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・"
        "write_agreement・escalate_premise_concern・resolve_premise_concern・revise_goal・"
        "freeze_agreement・write_issue・read_issues・read_entity・thinkです。"
        + _THINK_TRAILER_SENTENCE + "\n"
    )

    previous_user_input = state.get("user_input", "(取得不可)")

    # [BL-185] エスカレーション再開通知・タスク遷移ブロック通知は、決定事項DB等と同じ
    # 「状況説明」寄りの情報のため、差し戻し・最終盤指示より前（trailing内の中盤）に置く。
    system_prompt_trailing += _build_escalation_resume_notice(state)  # [BL-096]
    system_prompt_trailing += _build_task_transition_blocked_notice(state)  # [BL-125/BL-190]
    system_prompt_trailing += _build_task_focus_transition_notice(state)  # [BL-191]
    # [BL-192/独立レビュー指摘7-2] このパスは差し戻し（constraint_issue=="major"）・本質対話・
    # Expert相談応答・終盤・初回ターン用であり、Stage4をスキップするため、Stage4側にのみ
    # 指示を入れるとこれらの重要な場面でBL-192の指示（web_search義務化・思考プロセス明示）が
    # 一切適用されなくなる。共通定数を参照し文言の二重管理を避ける。
    system_prompt_trailing += _BL192_DIRECTIVE_QUALITY_BLOCK

    #system_prompt_trailing += f"""
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

    if state["turn_count"] >= max_turns - 2:
        system_prompt_trailing += f"""
            🚨 【最終盤の超重要指示】\n
            これまでの議論で、計画されたすべてのタスクが完了し、それぞれのタスクの「成果物」が提出されているか確認してください。\n
            すべてのタスクの個別成果物が出揃い、内容に問題がなければ、**『すべてのタスクが完了したため、プロジェクトを完了とする。[PROJECT_COMPLETE]』** と明確に宣言して議論を締めくくってください。\n
            ※注意：相手のAIに『これまでの議論をすべてまとめた最終報告書を作成せよ』とは**絶対に指示しないでください**。統合はシステムの別機能（Integrator）が行います。\n
            [BL-185] ただし、今回Detectorからの差し戻し（下記に表示されている場合）があれば、\n
            その指摘への対応を最優先してください。差し戻しを無視して拙速にプロジェクト完了を\n
            宣言することは禁止です。\n
        """

    # [BL-185] 差し戻し通知（drift_flag/constraint_issue="major"）は、system_prompt_trailingの
    # 最後（＝messages配列全体でも最後）に配置する。BL-178でcall_expertに導入したのと同じ
    # 「最も直近の是正内容を、chat_historyの内容やそれより前のtrailing内テキストに関わらず
    # 必ず最後に読ませる」構成（実ログlog/2026-08-06/1149で、差し戻し直後のUser AIが
    # 🚨最終盤の超重要指示（当時は差し戻し通知の直後に配置）や、chat_history末尾のExpertの
    # 完了報告に引きずられ、削除されたはずの「前回の完了宣言」をそのまま繰り返した実害を確認）。
    if state.get("drift_flag") or state.get("constraint_issue") in ["major"]:
        # [BL-143] 何回目の差し戻しか・前回と同じ指摘の繰り返しかを機械的に要約し先頭へ提示する。
        _retry_label = _build_retry_situation_label(state, state.get("user_retry_count", 0))
        system_prompt_trailing += f"""
            \n{_retry_label}
            \n⚠️ 【重要】\n
            あなたの前回の発言は、倫理違反、矛盾、リソース超過や制約違反などの重大な矛盾が検知されDetector（監査システム）により差し戻されました。\n
            ▼ 【却下されたあなたの前回の発話（※チャット履歴からは削除済）】\n
            {previous_user_input}\n\n
            以下の指摘事項を踏まえ、より洗練された回答をしてください：\n
            {state.get('constraint_issue_log', [])[-1:]} \n\n
            上記の「自身の過去の発言」と「指摘事項」を熟読し、発言内容を修正して再出力してください。\n
            必ず、矛盾の内容とその理由を明示し、どのタスク・フェーズに影響があるかを具体的に指摘した上で、エージェントAIに正しい方向への修正を厳しく要求してください。\n
            [BL-142] 【最重要】却下された前回の発話が成果物の「承認」「次タスクへの移行」だった場合、\n
            言い回しを変えただけの同じ承認を繰り返すことは禁止です。承認を明確に撤回し\n
            （write_agreement action_type="UPDATE", status="Rejected"で上書きしてください）、\n
            指摘された矛盾点をAgent AIが成果物のどこをどう直すべきか具体的に示した修正指示を\n
            出してください。次タスクへの移行は、Agent AIが修正版を再提出し、あなたが指摘事項の\n
            解消を確認できてから改めて行ってください。\n
            [BL-185] 【最優先】上記の🚨最終盤の超重要指示（表示されている場合）よりもこの差し戻し\n
            対応を優先してください。差し戻された内容をそのまま繰り返したり、完了宣言で押し切ろうと\n
            したりすることは絶対に禁止です。\n
            """

    # [BL-185] system_prompt_trailingをchat_historyより後ろへ独立したsystemメッセージとして
    # 追加する（BL-178でcall_expertに導入したのと同型のパターン）。
    # --- 3. メッセージ履歴の構築 ---
    messages = [{"role": "system", "content": system_prompt_leading}]

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

    # [BL-185] system_prompt_trailing（決定事項DB・エスカレーション通知・最終盤指示・
    # 差し戻し通知を含む「直近の是正内容」）をchat_historyより後ろへ独立したsystemメッセージ
    # として追加する。複数のrole:"system"メッセージを会話途中・末尾に挿入すること自体は
    # BL-093/BL-178で既に実績のあるパターン（新規リスクではない）。
    messages.append({"role": "system", "content": system_prompt_trailing})

    # [BL-177] globalは関数冒頭（_is_normal_review_turn分岐内）で宣言済みのため再宣言不要。
    _CURRENT_CALLER_ROLE = "user"
    _CURRENT_TASK_ID = state.get("current_task_id", "")
    _CURRENT_PHASE_ID = state.get("current_phase", {}).get("phase_id", "")  # [BL-096] write_issueのphase_id用
    _CURRENT_GOAL_TEXT = user_goal  # [BL-086] revise_goalの編集対象
    _reset_think_scratchpad()  # [BL-093]
    content = query_AI(messages, client=client_user, model=model_user, label="User AI", tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, RESOLVE_PREMISE_CONCERN_TOOL, REVISE_GOAL_TOOL, FREEZE_AGREEMENT_TOOL, WRITE_ISSUE_TOOL, READ_ISSUES_TOOL, READ_ENTITY_TOOL, THINK_TOOL], state=state)

    if content is None or content.strip() == "" or content == "(APIから空の応答が返されました)":
        for retry in range(3):
            print(f"⚠️ [User AI] 空応答を検知。リトライ {retry+1}/3...")
            # global宣言は既に上の行で完了しているため再宣言不要
            _CURRENT_CALLER_ROLE = "user"
            _CURRENT_TASK_ID = state.get("current_task_id", "")
            _CURRENT_PHASE_ID = state.get("current_phase", {}).get("phase_id", "")
            _CURRENT_GOAL_TEXT = user_goal
            _reset_think_scratchpad()  # [BL-093]
            content = query_AI(messages, client=client_user, model=model_user, label="User AI", tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, ESCALATE_PREMISE_CONCERN_TOOL, RESOLVE_PREMISE_CONCERN_TOOL, REVISE_GOAL_TOOL, FREEZE_AGREEMENT_TOOL, WRITE_ISSUE_TOOL, READ_ISSUES_TOOL, READ_ENTITY_TOOL, THINK_TOOL], state=state)
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
    # [BL-041] global_constraintsはこれまでどこにも実データが書き込まれず常に空だったため
    # 常に空振りしていた。ここでagreements DBから毎回動的に再集約し、実データを反映させる。
    state["global_constraints"] = _aggregate_global_constraints(
        get_agreements_from_db(get_active_conn(), state["run_id"])
    )
    overruns = check_global_constraint_overrun(state)
    if not overruns:
        state["phases_to_revise"] = []
        return state

    overrun = overruns[0]
    print(f"\n⚖️ [Arbiter] リソース超過を検出しました: {overrun.get('constraint', '?')}。call_resource_arbiterで再配分案を検討します。")
    result = call_resource_arbiter(
        state["goal"], overrun, state["phases"],
        goal_essence_text=_get_goal_essence_text(get_active_conn(), state["run_id"]),
        state=state,
    )

    state["phases_to_revise"] = result.get("phases_to_revise", [])
    print(f"  ⚖️ [Arbiter] 再検討対象phases: {state['phases_to_revise']}")
    decision = make_decision(
        who="arbiter",
        what=f"リソース超過調停: {overrun['constraint']}",
        why=result.get("rationale", "再配分案を提示")
    )
    db_append_decision(decision, get_active_conn(), state["run_id"])

    # [R5 GoalShiftEvent] 再配分案が絶対制約自体の変更を要求している場合、ゴール変容として記録する。
    shift = detect_goal_shift(state, result)
    if shift is not None:
        print(f"  🔀 [Arbiter] GoalShiftEventを記録しました: {shift.get('shift_kind', '?')}")
        db_append_goal_shift_event(shift, get_active_conn(), state["run_id"])

    return state

# ---------------------------------------------------------------------------
# 4. ノード定義
# ---------------------------------------------------------------------------

def generate_user_utterance_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Generates the user's next utterance based on system state, managing conversation history and retries following constraint violations.
    """
    print("\n[generate_user_utterance]------ ユーザーAIが思考中 ------\n")
    # [BL-005対応] このノードへの再入場= 1ラウンドの開始（BL-044で確認済みのラウンド定義）。
    # turn_count（グラフ内部ループで凍結し得る、BL-005）に依存せず、ここで確実に加算する。
    state["round_count"] = state.get("round_count", 0) + 1
    # 🌟 追加: 差し戻しループの場合、前回エラーになった発言を履歴から削除（履歴汚染とAPIエラーを防止）
    if state.get("constraint_issue") in ("major"):
        if state["chat_history"] and state["chat_history"][-1]["role"] == "user":
            state["chat_history"].pop()
            state["user_retry_count"] += 1
            print("♻️ [User AI] 差し戻しのため、直前のNG発言を履歴から取り消しました。")
    else:
        state["user_retry_count"] = 0
    
    user_input = generate_user_utterance(state, config)
    # [R3b §3.5.1] 今ターンでwrite_agreementが1回でも成功したかをstateに保存
    state["user_wrote_agreement"] = get_last_write_agreement_succeeded()
    # [BL-158] 今ターンでwrite_issue(RESOLVE/DEFER)が1回でも成功したかをstateに保存
    state["user_wrote_issue_resolution"] = get_last_write_issue_resolve_or_defer_succeeded()
    # [R5 F-2.1] User AIのreasoningを、次のDetectorが思考プロセス監査に使えるようstateへ保存する。
    state["user_last_reasoning"] = get_last_reasoning_text()
    # [BL-086] revise_goalが今ターン成功していれば、state["goal"]をここで改定する。
    # state["goal"]は9箇所の呼び出し元が毎ターン再埋め込みするため、この1箇所の代入だけで
    # 次ターン以降すべての消費者（call_expert/call_detector/call_resource_arbiter等）へ
    # 自動的に伝播する（個別配線不要）。
    _goal_revision = get_last_goal_revision()
    if _goal_revision:
        state["goal"] = _goal_revision["new_goal_text"]
        # [BL-162] old_goal_textも橋渡しする。従来はnew_goal_textのみstate["goal"]へ反映され
        # old_goal_textはここで捨てられていたため、次のgoal_change監査Detectorが「旧文が
        # 保持されているか」を確認する手段を一切持たなかった（read_verified_fact等で計5回
        # 探して全てnot_found）。
        state["goal_revision_old_text"] = _goal_revision.get("old_goal_text") or ""
        print(f"🧭 [BL-086] Escalation {_goal_revision['escalation_id']} 承認によりgoalを改定しました。")
        # [BL-126 Stage B] 次のuser_detectorに、通常の成果物監査ではなくreview_mode="goal_change"
        # （§5の4判断基準）を使わせる。反応的revise_goal経路にも既存パスを変えずに適用できる
        # （detector_node/route_after_user_detectorの既存ロジックは一切変更不要）。
        state["goal_revision_pending_review"] = True
        # [BL-186] ゴール改定で影響を受けた過去タスクの再検証を、BL-145と同型の配線で
        # task_plannerへ強制的に引き継ぐ（次ターンのgoal_essence→task_planner再入場時に
        # 自動的に消費される、BL-126 Stage C）。他要因（task_plan_reviewerの差し戻し等）が
        # 既にplan_revision_reasonをセット済みの場合は上書きしない。
        _new_plan_revision_reason = _goal_revision.get("plan_revision_reason") or ""
        if _new_plan_revision_reason:
            if not state.get("plan_revision_reason"):
                state["plan_revision_reason"] = _new_plan_revision_reason
                state["plan_revision_issue_ids"] = _goal_revision.get("plan_revision_issue_ids") or []
                print(f"  🧭 [BL-186] ゴール改定に伴い、過去タスクの再検証をplan_revision_reasonとして"
                      f"task_plannerへ強制的に引き継ぎました（{len(state['plan_revision_issue_ids'])}件）。")
            else:
                print("  ⚠️ [BL-186] plan_revision_reasonが既に別要因でセット済みのため、"
                      "今回は次回reflectionでの再評価に譲ります。")
    # [BL-126 Stage D] 今ターンでwrite_agreement(entry_type="EssenceProposal")が成功していれば
    # stateへ橋渡しする（facilitator_nodeがこのターンでの収束判定に使う。ツールハンドラは
    # stateへ直接触れられないため、他のブリッジ変数と同じパターン）。
    state["last_essence_proposal"] = get_last_essence_proposal()
    # [BL-191] Stage4がschedule_task_focusを呼んでいれば、構造化決定をdecision_extractor_nodeへ
    # 一度だけ橋渡しする（call_decision_extractorの自由文脈抽出をバイパスする経路）。
    # [独立レビュー指摘6-3] 無条件で毎ターン上書きする（条件付き代入にすると、user_detectorが
    # major判定で差し戻した後にUser AIがツールを呼び直さなかった場合、前回ターンの
    # （撤回されたかもしれない）決定がpending_task_redirectに残留してしまう）。
    _scheduling_decision = get_last_scheduling_decision()
    state["pending_task_redirect"] = _scheduling_decision
    if _scheduling_decision:
        print(f"  🧭 [BL-191] Stage4がスケジューリング決定を行いました: {_scheduling_decision}")
    print(f"\n>>> 👤 User AIの発言:\n{user_input}")
    state["user_input"] = user_input
    state["chat_history"].append({"role": "user", "content": state["user_input"]})
    # [BL-103] 従来User AIの発言はdecisions/hydrate要約チャネルに一切記録されておらず、
    # Expertの発言（弱いながらも記録される）と非対称だった。ここで初めて記録する。
    decision = make_decision(who="user", what=f"Expertへの発言（ラウンド{state['round_count']}）",
                              why=get_last_think_summary() or user_input[:150])
    db_append_decision(decision, get_active_conn(), state["run_id"])
    # [BL-130] Expert相談への回答をUser AIが今まさに生成し終えたところなので、ここで消費・リセット
    # する（次のuser_detectorは通常の監査対象=このUserの発言であり、相談モードではないため）。
    state["expert_consultation_mode"] = False
    state["expert_pending_question"] = ""
    state["expert_blocking_reason"] = ""
    return state

def make_decision(who: str, what: str, why: str | None, internal_thought_process: str | None = None) -> Decision:
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
        # [R5 F-3.7] トークンコスト抑制のため全件記録はせず、呼び出し元が意図的に渡した場合のみ
        # スナップショット保存する（Detector major判定・Reflection stagnant判定時のみ）。
        "internal_thought_process": internal_thought_process or "(記録なし)",
    }

def call_goal_essence_analyst(goal: str, state: dict | None = None) -> dict:
    """[BL-087 Stage3] task_planner分解より前に1回だけ呼ばれる「本質フェーズ」の実体。
    ゴールの文言をそのまま鵜呑みにする前に、(1) 明示された数値・制約からの大まかな
    実現可能性の壁打ち（詳細な検算はF-2.6の役目であり、ここでは大まかなオーダー感の
    把握に留めるが、暗算によるハルシネーションを避けるためpython_replでの機械計算を
    使わせる）、(2) 文言上の制約が本来仕えるべき「真に達成すべきこと」の言語化、の
    2点を行う。結果はgoal_essenceテーブルに保存され、以後全ノードのプロンプトへゴール本文と
    並べて常時注入される（BL-086のescalate_premise_concernは走行中に矛盾に気づいた際の
    事後エスカレーションであり、本フェーズはその手前の事前予防として独立・併存する）。
    """
    prompt = f"""
    あなたは、プロジェクト開始前に発注者と行う「壁打ち」を担当する、経験豊富なコンサルタントです。
    以下の絶対目標を鵜呑みにしてそのままタスク分解する前に、2つの観点で一度立ち止まって
    検討してください。

    ■ 絶対目標: {goal}

    【観点1: 大まかな実現可能性の壁打ち】
    ゴール文に明示されている数値制約（予算、台数、人数、時間等）から、大まかな見積もりで
    実現可能性の見立てを行ってください。詳細な検算は後続の各タスクの役目なので、ここでは
    「一見して無理筋に見える組み合わせ」がないかのオーダー感の確認に留めてください
    （例: 「予算上限からすると設備の絶対数はごく少数に限られるが、要求されている需要規模は
    その少数の設備では到底さばききれない可能性が高い」といった見立て）。
    【重要】この大まかな見積もりであっても、暗算で数値を出さず、必ず python_repl ツールで
    計算してください（大まかな見立てとはいえ、この本質フェーズはプロジェクト全体で最も
    上流の判断であり、ここでの暗算・計算ミスは後続の全タスクに伝播するハルシネーション
    リスクとなるため）。

    【観点2: 目標の本質の言語化】
    ゴール文に列挙されている個々の制約・条件は、あくまで「本来解決すべき本質的な課題」を
    実現するための手段・例示に過ぎない可能性があります。この目標が本当に達成しようとしている
    本質的な課題は何か（例: 特定の手段そのものではなく、対象となる受益者・利用者にとっての
    実質的な便益・安全性の確保等）を、ゴール文の個々の制約から一段抽象化して言語化してください。
    これは今後、個々のタスクが「手段の遂行」に没頭するあまり本質を見失った場合に立ち返る
    基準として、プロジェクト全体を通じて参照され続けます。

    {_verification_throttle_warning()}

    【JSON文字列内で全角鉤括弧を使う際の注意（重要）】文字列値の中で強調のために「」や『』を
    使うのは構いませんが、文字列値の**末尾**を「」や『』で終えないでください。全角の閉じ鉤括弧
    （」や』）のすぐ後にJSON構文上の閉じ引用符(")を書くのを忘れ、構文エラーになる事故が実際に
    発生しています。文の最後に強調を置きたい場合は、鉤括弧で挟むのではなく地の文のまま書くか、
    強調部分を文の途中に置き、文字列値の最後の文字は句点「。」などの通常の文字にしてください。

    【BL-093: thinkツールで検討過程を残す】{_BL093_THINK_VALUE_PARAGRAPH}
    [BL-094: read_verified_fact/read_deliverable_fileで既存の確定値の有無を確認する]
    read_verified_factは全フェーズ・全タスク横断で既に確定した値を、read_deliverable_file
    は過去タスクの成果物全文を検索できます。あなたは通常このプロジェクトの最初期に1回だけ
    呼ばれるため、多くの場合まだ何も確定していません（該当なしという結果もそれ自体が
    正しい確認結果です）。もし何らかの理由で既に確定値・過去の成果物が存在する場合は、
    それを無視して独自に矛盾する仮定を置かないよう、iter=1で一度read_verified_factを
    呼んで確認してください。
    [BL-095: write_agreementで検討過程を残す（任意）] true_essence/feasibility_notesの2フィールド
    に収まらない検討過程（他に考えたが採用しなかった本質の言語化案とその却下理由等）があれば、
    write_agreement（entry_type="Decision", status="Proposed", action_type="CREATE",
    topic="goal_essence_analysis"）で任意に記録できます。true_essence/feasibility_notes自体は
    既にgoal_essenceテーブルに保存され全ノードへ常時注入されるため、これは必須ではありません。
    【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
    write_agreement・thinkです。{_THINK_TRAILER_SENTENCE}

    Return ONLY JSON: {{"true_essence": "（本質の言語化、2〜4文程度）",
    "feasibility_notes": "（大まかな実現可能性の見立て、無理筋に見える組み合わせがあれば
    具体的に指摘。特に懸念がなければその旨を簡潔に）"}}
    """
    # [BL-089] 層2リトライ（_query_and_parse_with_retry、D-005）でラップする。本質フェーズは
    # 全ノードへ常時注入される最上流の判断であり、単発のパース失敗でgoalそのままの
    # フォールバックに落ちると本質フェーズの意味が失われる。
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "goal_essence_analyst"  # [BL-095]
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_goal_essence, model=model_goal_essence, label="Goal Essence Analyst",
        tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, WRITE_AGREEMENT_TOOL, THINK_TOOL],
        fallback={"true_essence": goal, "feasibility_notes": "(JSONパース失敗のため見立てなし)"},
        state=state,
    )
    if parse_failed:
        print("🚨 [Goal Essence Analyst] JSON結果の取得に失敗しました。ゴール文そのままにフォールバックします。")
    return parsed


def seed_entities_from_goal(goal: str, run_id: str, state: dict | None = None) -> dict:
    """[BL-204] ゴール文に登場する事物をレジストリへ初期登録する。

    **本設計の中核**は、抽出結果をそのまま信用せず、`canonical_name`が**ゴール文中に
    文字列として実在すること**を機械的に検証する点にある。この部分一致判定は客観的で
    LLMの主観を必要とせず、これ1つで`log/2026-08-10/0901`の「長野大学」
    （ゴール文には`公立諏訪東京理科大学`とあるのにExpertが記憶から書いた実在の別大学）は
    `origin='goal_text'`としては登録され得なくなる。

    抽出そのものはLLMに任せる（ゴール文の書式は課題ごとに自由であり、機械的な固有表現
    抽出は形態素解析器等の新規依存を必要とするため。AGENTS.md依存追加最小化方針）。
    抽出が漏れても、Expertが`register_entity`で`origin='discovered'`として補える。
    """
    conn = get_active_conn()
    # [BL-204] 冪等ガード。resumeや計画再構成で再入場しても再抽出しない（LLM呼び出しの
    # 節約と二重登録の防止。task_plan_reviewer_nodeのplan_review_done等と同型の考え方）。
    already = conn.execute(
        "SELECT COUNT(*) AS c FROM entities WHERE run_id=? AND origin='goal_text'", (run_id,)
    ).fetchone()
    if already and already["c"] > 0:
        return {"registered": [], "rejected": [], "skipped": True}

    prompt = f"""
    以下の絶対目標の本文に登場する「事物」（固有の名前を持つ実世界の対象）を洗い出してください。

    ■ 絶対目標:
    {goal}

    【抽出の指針】
    - 対象は、固有の名前を持つ実世界の対象です。施設・場所・組織・団体・路線・制度・
      サービス・製品など、種類は問いません。
    - 一般名詞（「高齢者」「市街地」「バス」等の総称）は対象外です。固有の名前を持つものだけを
      挙げてください。
    - **名称は、ゴール文に書かれている表記をそのまま、一字一句変えずに写してください。**
      省略形・通称・あなたの記憶による言い換えを使わないでください。ゴール文の表記と
      1文字でも異なる名称は、この後の機械的な照合で棄却されます。
    - entity_typeは分類の目安です（place / organization / service / facility / route など、
      適切と思う語を自由に付けてください）。

    Return ONLY JSON:
    {{"entities": [{{"canonical_name": "（ゴール文中の表記のまま）", "entity_type": "（分類）"}}]}}
    """
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "entity_registrar"
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_task_planner, model=model_task_planner,
        label="Entity Registrar (BL-204)", tools=[THINK_TOOL],
        fallback={"entities": []}, state=state,
    )
    if parse_failed:
        print("🚨 [BL-204] 事物抽出のJSON取得に失敗しました。初期登録をスキップします"
              "（Expertがregister_entityで補えるため、runは継続します）。")
        return {"registered": [], "rejected": [], "skipped": False}

    registered: list[str] = []
    rejected: list[str] = []
    for e in (parsed.get("entities") or []):
        if not isinstance(e, dict):
            continue
        name = (e.get("canonical_name") or "").strip()
        etype = (e.get("entity_type") or "unknown").strip() or "unknown"
        if not name:
            continue
        # [BL-204][SAFETY] 正典名チェック。ゴール文に実在しない名称は登録しない。
        if name not in goal:
            rejected.append(name)
            continue
        try:
            register_entity_in_db(conn, run_id, name, etype, origin="goal_text",
                                  created_by="entity_registrar")
            registered.append(name)
        except ValueError:
            rejected.append(name)

    if registered:
        print(f"  🗂️ [BL-204] ゴール文から事物を{len(registered)}件登録しました: {registered}")
    if rejected:
        print(f"  ⛔ [BL-204] ゴール文に実在しない名称のため登録を棄却しました: {rejected}")
    return {"registered": registered, "rejected": rejected, "skipped": False}


def goal_essence_node(state: LineageState) -> LineageState:
    """[BL-087 Stage3] グラフの新しいentry_point。task_planner_nodeより前に1回だけ発火し、
    本質フェーズの結果をgoal_essenceテーブルへ保存する。goal_essence_doneはチェックポイント
    再開・毎ターンの再入場で再発火しないための冪等ガード（task_plan_reviewer_nodeの
    plan_review_doneと同型）。
    """
    if state.get("goal_essence_done"):
        return state

    print("\n------ [goal_essence] が目標の本質を壁打ち中 ------\n")
    result = call_goal_essence_analyst(state["goal"], state=state)
    print(f"\n[goal_essence] 結果: {result}\n")

    db_save_goal_essence(get_active_conn(), state["run_id"], result.get("true_essence", ""), result.get("feasibility_notes", ""))
    state["goal_essence_done"] = True
    decision = make_decision("goal_essence", "目標の本質を言語化", result.get("feasibility_notes", ""))
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state


def task_planner_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Initial planning and decomposition of the overall system goal into sequential phases and executable tasks.
Sets the starting phase for subsequent execution steps within the lineage state.
    [BL-126 Stage C] ガードを緩和し、`plan_revision_reason`がセットされている場合はラン途中でも
    再発火する（既存の初回計画パス自体は変更しない）。
    """
    is_initial = state["turn_count"] == 1 and not state.get("phases")
    revision_reason = state.get("plan_revision_reason", "")
    revision_issue_ids = state.get("plan_revision_issue_ids", [])

    # [BL-105] グラフのentry_pointはgoal_essence固定であり、外側whileループが完了済みの
    # threadへフルstateを再投入するたびに（次ターン開始時、通常の多ターンパターン）、この
    # ノードを毎回必ず通る。turn_count==1だけを見ると計画を毎回再生成してしまうため、
    # phases未確定の場合のみ実処理する。
    if is_initial or revision_reason:
        if revision_reason:
            # [BL-126 Stage C/v2修正] 消費「後」ではなくガード判定直後（先頭）でクリアする。
            # チェックポイント再開時、クリア前に中断されると再開時に同じ理由が残り多重発火する
            # リスクがあるため（plan_reviewer_feedbackとは異なる箇所でクリアする理由）。
            state["plan_revision_reason"] = ""
            state["plan_revision_issue_ids"] = []
            state["plan_revision_count"] = state.get("plan_revision_count", 0) + 1
            print(f"""
                  \n------ [task_planner] が思考中 ------\n
                  \n------- ラン途中の計画再構成（第{state['plan_revision_count']}回、理由: {revision_reason}） -------\n
                  """)
        else:
            print("""
                  \n------ [task_planner] が思考中 ------\n
                  \n------- 最初にゴール達成への道筋を、フェーズとタスクに分解して計画を立てます -------\n
                  """)

        # [BL-087 Stage2] task_plan_reviewer_nodeが差し戻した際の指摘事項があれば反映する。
        reviewer_feedback = state.get("plan_reviewer_feedback", "")
        # [BL-087 Stage3] goal_essence_nodeがtask_planner直前に発火するため、ここで既に
        # 保存済みの本質テキストを取得できる（ユーザー指摘：注入漏れ、9消費者リストは
        # BL-086由来でtask_planner/task_plan_reviewerは含まれていなかった）。
        goal_essence_text = _get_goal_essence_text(get_active_conn(), state["run_id"])

        # [BL-204] タスク分解より前に、ゴール文に登場する事物をレジストリへ初期登録する。
        # ここに置くのは、acceptance_criteria/owns_variablesが事物を参照できるようにするため。
        # 専用ノードを新設せずtask_planner内で行うのはユーザー判断（設計書§6決定1）——
        # BL-201/BL-203で「resume経路だけ挙動が違う」事故を続けて経験しており、
        # build_graphのトポロジーを触らない方が再発リスクが低いため。
        # seed_entities_from_goal自身が冪等ガードを持つので、計画再構成で再入場しても
        # 再抽出しない。
        seed_entities_from_goal(state["goal"], state["run_id"], state=state)
        old_phases = state.get("phases", []) if revision_reason else []
        phases = call_task_planner(
            state["goal"], reviewer_feedback=reviewer_feedback, goal_essence_text=goal_essence_text, state=state,
            existing_phases=old_phases, revision_reason=revision_reason,
        )
        print(f"\n------ 完了 ------\n")

        phases_json = json.dumps(phases, ensure_ascii=False, indent=2)
        print(f"\n[task_planner] フェーズとタスクの分解結果:\n{phases_json}\n\n")

        if revision_reason:
            # [BL-126 Stage C/§6] 「削除ではなくsupersede」: 新しい計画に含まれなくなった
            # 既存task_idを、削除ではなくphases_supersededへ記録し、write_agreement
            # (entry_type="Directive", action_type="SUPERSEDE")で監査証跡を残す。
            old_task_ids = {t["task_id"] for p in old_phases for t in p.get("tasks", [])}
            new_task_ids = {t["task_id"] for p in phases for t in p.get("tasks", [])}
            removed_task_ids = old_task_ids - new_task_ids
            _conn = get_active_conn()
            for tid in sorted(removed_task_ids):
                old_phase_id = _find_phase_id_for_task(old_phases, tid) or ""
                state.setdefault("phases_superseded", []).append({
                    "task_id": tid, "phase_id": old_phase_id, "reason": revision_reason,
                    "superseded_at_round": state.get("round_count", 0),
                })
                # [BL-095] task_plannerロールはstatus="Proposed"のみ許可（自らの計画判断は
                # 未承認の提案としてのみ記録できる、他ロールのように直接Rejectedを名乗れない）。
                _write_agreement_impl(
                    {
                        "action_type": "SUPERSEDE", "status": "Proposed", "entry_type": "Directive",
                        "topic": f"task_plan_{tid}", "target_topic": f"task_plan_{tid}",
                        "task_id": tid, "phase_id": old_phase_id,
                        "decision_what": f"タスク{tid}はラン途中の計画再構成により廃止されました。",
                        "reason_why": revision_reason,
                    },
                    _conn, state["run_id"], "task_planner", tid,
                    phases=old_phases, pending_task_ids=state.get("pending_task_ids", []),
                )
                print(f"  🔀 [Task Planner] task_id='{tid}'（phase='{old_phase_id}'）をsupersedeしました（理由: {revision_reason}）。")
            # [BL-126 Stage C/§11(3)] ラン途中再構成後の計画もtask_plan_reviewer_nodeを
            # スキップせず通す（既存の実行前ゲートを再利用、plan_reviewer_retry_countとは
            # 独立にplan_revision_countで上限管理する）。
            state["plan_review_done"] = False

        state["phases"] = phases
        if revision_issue_ids:
            # [BL-145] Reflectorのissue formalizationが引き金だった場合、対象issue_log行を
            # 'planned'状態へ遷移させる（resolvedにはしない。真の解決確認はuser roleが
            # 別途write_issue(RESOLVE)で行う）。
            _new_task_ids = sorted({t["task_id"] for p in phases for t in p.get("tasks", [])})
            for _issue_id in revision_issue_ids:
                _planned = _mark_issue_planned(get_active_conn(), state["run_id"], _issue_id,
                                                embedded_task_ids=_new_task_ids)
                if _planned:
                    print(f"  📋 [BL-145] issue_id='{_issue_id}'をplanned状態にし、計画再構成へ組み込みました。")
                else:
                    print(f"  ⚠️ [BL-145] issue_id='{_issue_id}'は対象外でした（既にresolved等、冪等スキップ）。")
        if phases:
            _reconcile_current_phase_after_replan(state, phases)
            print(f"  📍 [task_planner] current_phaseをphase_id={state['current_phase'].get('phase_id')}に設定しました。")
        # [BL-087 Stage2改善] task_plan_reviewer_nodeが動く前に、全タスク分のplan_draftsスケルトンを
        # 事前生成しておく（従来は_append_deferred_note_to_plan経由の遅延生成のみだったため、
        # レビュー時点では何も存在せず、レビュワーが指摘を書き込む先がなかった）。
        _conn = get_active_conn()
        for _phase in phases:
            for _task in _phase.get("tasks", []):
                apply_plan_patch(
                    _conn, state["run_id"], _phase.get("phase_id", ""), _task.get("task_id", ""),
                    _render_plan_skeleton(_task), author_role="task_planner", edit_summary="初期計画生成"
                )
        state["global_constraints"] = []
        state["plan_reviewer_feedback"] = ""  # 消費済みのためクリア
        decision = make_decision(
            "task_planner", f"プロジェクトを {len(phases)} フェーズに分解",
            "初期計画策定" if not revision_reason else f"ラン途中の計画再構成: {revision_reason}",
        )
        print(f"[task_planner]  プロジェクトを {len(phases)} フェーズに分解 初期計画策定)")
        db_append_decision(decision, get_active_conn(), state["run_id"])
    print("\n------ [task_planner] をパス ------\n")
    return state


def call_task_plan_reviewer(phases: list[dict], goal: str, goal_essence_text: str = "", state: dict | None = None) -> dict:
    """[BL-087 Stage2] task_planner_node直後に1回だけ呼ばれ、生成されたフェーズ・タスク
    計画全体を実行開始前にレビューする。Detector同等のJSON形式（risk/constraint_issue/
    comment）で返す実行前ゲート。
    """
    phases_json = json.dumps(phases, ensure_ascii=False, indent=2)
    # [BL-104] プロンプトキャッシュのヒット率向上のため、固定指示文（レビュー観点1-4・曖昧さと
    # 捏造要求の混同注意・BL-092/BL-093/BL-094/BL-095・ツール一覧の説明）を先頭にまとめ、
    # ゴール文（実行中はほぼ不変）をその次、呼び出しごとに変わる生成された計画本体
    # （phases_json）は末尾に配置する。冒頭の「以下は…計画です」はphases_jsonへの前方参照
    # だが、単に「この後どこかにphases_jsonが登場する」ことだけを要求しており、直後の隣接を
    # 要求していないため、静的グループを先に置いてもこの前方参照は成立する。BL-092内の
    # 「上記の通り」は同じ静的グループ内の曖昧さ混同注意ブロックを指しており、両ブロックの
    # 相対順序を維持しているため引き続き成立する。
    prompt = f"""
    以下は、絶対目標を分解して生成された「フェーズ・タスク計画」です。実行を開始する前に、
    この計画自体の質をレビューしてください（個々のタスクの中身の是非ではなく、計画の構造
    そのものが後工程で無駄な手戻りを生まないかを見てください）。

    以下の観点でレビューしてください（1つに偏らず、4つとも同等以上に重視すること。実際に
    後工程で最も高くつく手戻りは、数値の端数不一致よりも「タスクの欠落」や「順序矛盾」から
    生じることが多いため、数値の細かい不整合ばかりを追いかけて2・3・4を見落とさないこと）:
    1. 曖昧な表記: 各タスクのacceptance_criteria/descriptionに、AIが読み違えるような曖昧な
       数量・比率・位置の表記がないか（例: 比率と絶対値が並記され、どちらが基準か不明瞭等）。
    2. タスクの過不足: 絶対目標の達成に対して、明らかに欠けているタスク、または不要に
       重複・過剰なタスクがないか。
    3. 順序の妥当性: depends_onで示される依存関係が、フェーズ・タスクの記載順序と矛盾して
       いないか（前提となるタスクが後のフェーズに配置されている等）。
    4. 条件の明示: 比率や制約から計算・仮定した派生値（本文に直接の記載がない数値）が、
       前提条件（例: 新品購入かリース等の代替を除くか等）を伴わずに絶対制約として断定されて
       いないか。「◯◯が上限」のような断定は、その根拠となる条件と一緒に書かれているべきです。

    【重要: 曖昧さの指摘とゴール文にない数値の捏造要求を混同しない】
    ゴール文（絶対目標）自体が与えていない絶対値（例: 総量そのもの）を、taskに無理やり
    確定させるよう差し戻してはいけません。以前のレビューで「〈部分X〉2単位≒全体の13.33%」と
    いう、task_planner自身が注記付きで示した推定値（原文の「約12%」との端数差はごくわずか）を
    「矛盾」としてmajor判定した結果、再生成されたtask_plannerが「〈部分X〉＝全体の15%」という
    原文からは読み取れない解釈で「総量100単位」という、原文にない数値をでっち上げてしまった
    実例があります。これは、Reviewerが絶対値の確定を強く求めすぎたことがハルシネーションを
    誘発した典型例です。ゴール文に絶対値の記載がなく、比率同士の整合性程度に留まる疑義であれば、
    「不明である旨をdescriptionに明記させる」という軽い修正指示に留め、具体的な数値を
    逆算・断定させる差し戻しをしないでください。

    重大な問題（このまま実行すると手戻りがほぼ確実な曖昧表記・タスク欠落・順序矛盾・条件欠落）
    がある場合のみ constraint_issue="major" としてください。軽微な改善余地はobservationsに
    記載するに留め、"none"としてください（実行前の1回きりのゲートであり、些末な指摘で何度も
    差し戻すと非効率です）。

    【BL-092: 「検証せず削除して解消」を見抜く（重要）】このタスクを以前のラウンドでも
    レビューし、特定のtask_idに具体的な指摘（数値の根拠不明・矛盾など）をした記憶がある場合、
    今回そのtask_idの記述がどう変わったかを、あなたの記憶や印象だけで判断しないでください。
    実際には、指摘された数値・記述が検算により訂正されたのではなく、該当するタスクの記述
    自体が丸ごと削除されたり、別の抽象的な内容に差し替えられて矛盾が見えなくなっただけ、
    ということが実際に起きています（reviewerの差し戻し圧力に対しtask_plannerが数値の
    訂正ではなく記述の削除・抽象化で「解消」を図る抜け道）。以前指摘したtask_idについては
    diff_plan_draft_versionsツールで前回との機械的な差分を確認し、指摘した論点が実際に
    「数値が訂正された」のか「関連する記述ごと消えた」のかを区別してから判断してください。
    後者（検証せず消しただけ）の場合、それ自体を新たな指摘としてcommentに明記してください。
    曖昧な表記（例: 比率と絶対値の並記）が実際に矛盾を生むかどうか判断に迷う場合は、暗算で
    決めつけず python_repl ツールで実際に数値を計算し確認してください（例: 「全体の15%」と
    「〈部分X〉2単位」が本当に整合するか等、この計画レビュー自体がプロジェクト全体で最も
    上流の判断であり、ここでの暗算・計算ミスは後続の全タスクに伝播します）。ただし、計算で
    「ゴール文に絶対値の記載がない」ことが判明した場合は、上記の通り数値の捏造要求はしないこと。

    【同じ検証・計算を繰り返さない（重要）】ツール呼び出しの回数には上限があります。同じ論点
    （例: 特定のタスクのacceptance_criteriaが曖昧かどうか、既に確認した数値の整合性）を
    python_replや思考の中で何度も再検討・再計算しないでください。各論点は2回程度の確認・計算で
    十分です。一度major/noneの判断がついた論点を、新しい情報が無いまま何度も蒸し返さないこと。
    新しい論点が無いまま「もう一度よく考えよう」を繰り返すと、JSON出力そのものを書く余地が無く
    なり、上限到達時に強制的に打ち切られたテキスト応答としてJSONを一度に出力せざるを得なくなり、
    大規模な計画では出力が途中で切れて構文エラーになるリスクがあります。また、最終回答は
    ```json ... ``` のコードブロックを**1つだけ**書いてください（下書き・プレビューとして
    別のJSONブロックを先に書き、その後で「最終的な」ブロックを別途書く、という2段構成には
    しないこと。複数のJSONブロックが混在すると機械的な抽出に失敗し、あなたの判定が正しく
    伝わらない事故が実際に発生しています）。必要な検証が終わったら、直ちに最終的な
    JSONオブジェクトを1つだけ記述してください。

    【BL-093: thinkツールで検討過程を残す】このレビューは複数回のpython_repl/
    diff_plan_draft_versions呼び出しを跨ぐことが多く、自然に考えた理由づけの生文章は、think
    を使わなければ次のiterationには引き継がれません（tool_callsの記録だけが残ります）。think
    を呼ぶと、その理由づけは次回以降のtool結果として全履歴ごと返され、雪だるま式に引き継がれ
    ます。まずtodoに確認すべきtask_idや論点をリストアップしてから、各論点の検討時にaction/
    decided/why（却下案があればrejected/rejected_why）を書いてください。他のツール呼び出しと
    同一の応答内でまとめて呼んでも、単独で呼んでも構いません。
    [BL-094: read_verified_fact/read_deliverable_fileで数値の出所を確認する]
    計画中の各タスクが前提とする数値（比率から逆算した絶対値等）が、ゴール文の直接記載か、
    それとも他ノード（Goal Essence Analyst等）が既にどこかで仮定・確定した値かを見分けるには、
    read_verified_factで該当する変数名・キーワードを検索し、その理由・引用元を確認してください。
    「出典」として引用されている値が、実は他ノード自身の推測にすぎない場合（真にゴール文まで
    遡れない場合）は、それ自体を要指摘としてください。read_deliverable_fileでは、その値が
    どのタスクでどんな前提のもと確定したかを遡って確認できます。【最低限、iter=1で一度は、
    計画中の主要な派生値についてread_verified_factで確認してから判定を進めてください】。
    [BL-095: task_plannerの判断根拠が誤っている場合はSUPERSEDEする]
    read_deliverable_file（task_planner_phase_design）でtask_plannerが記録した分解の判断根拠を
    確認した際、その根拠自体に誤り（存在しない前提を根拠にしている等）があり、それが今回の
    constraint_issue="major"判定の理由になっている場合は、write_agreement（action_type=
    "SUPERSEDE", status="Rejected", target_topic="task_planner_phase_design", reason_why=
    "<何が誤りか>"）でその記録を無効化してください（既存のBL-062と同型のパターンです）。
    そうしないと、誤った判断根拠が「記録済み」として残り続け、後続タスクが誤ってそれを参照します。
    [BL-188: web_search/web_fetch/read_reference_fileで現実世界の妥当性を検証する] あなた自身の
    学習知識から導き出した判断も、必ずしも正確であるとは限らず、最新の情勢（法令・相場・規制等）
    を反映しているとも限りません。計画中の前提（地理・距離・費用相場・法規制等）が現実的に成立
    するか自分の知識だけで判断がつかない場合は、記憶からの推測で済ませず、必ずweb_searchで
    信頼できる一次情報を確認・裏取りしてください。既にこのrun内で調べた可能性がある話題は、
    新規にweb_search/web_fetchを呼ぶ前にread_reference_file（keyword検索、呼び出し回数上限を
    消費しない）で先に確認してください。web検索結果は鵜呑みにせず一次ソースを優先してください。
    計画中の主張がcitations（引用元）付きでweb由来の情報を根拠にしている場合は、
    read_reference_fileでそのキャッシュ本文を確認し、実際に主張と一致しているか検証できます。
    [BL-204] 計画中の主張が特定の事物についてのものである場合、read_entityでレジストリの
    記録と突き合わせて確認できます。[BL-205] read_entityは名前を持つ事物専用です。
    対象を持たない単独の値はread_verified_factを使ってください。
    【重要】あなたが使えるツールはpython_repl・read_verified_fact・read_deliverable_file・
    diff_plan_draft_versions・write_agreement・web_search・web_fetch・read_reference_file・
    read_entity・thinkです。{_THINK_TRAILER_SENTENCE}

    ■ 絶対目標: {goal}
    {goal_essence_text}
    ■ 生成された計画:
    {phases_json}

    Return ONLY JSON: {{"risk": "low"/"medium"/"high", "constraint_issue": "none"/"major",
    "comment": "（majorの場合、task_plannerへの差し戻し指摘。具体的な修正指示にすること）",
    "observations": "（軽微な気づき、無ければ空文字）",
    "per_task_comments": [{{"task_id": "該当タスクのtask_id", "comment": "そのタスク固有の指摘（フェーズ・タスク表のホワイトボードに直接書き込まれます）"}}]
    （majorでもnoneでも、タスク固有の指摘があればここに列挙してください。無ければ空配列 []）}}
    """
    # [BL-089] 単発のquery_AI+_safe_json_parseではなく層2リトライ（_query_and_parse_with_retry、
    # D-005）でラップする。パース失敗時にconstraint_issue="none"へ静かにフェイルオープンすると、
    # レビュワーが実際には"major"と正しく判定していても握りつぶされ、縮退計画がそのまま
    # 承認・実行されてしまう（実ドライラン`log/2026-07-25/1814`で確認：複数の```json
    # ブロックが混線して構文エラーとなり、"major"判定が"none"にすり替わった）。
    global _CURRENT_CALLER_ROLE, _CURRENT_TASK_ID
    _CURRENT_CALLER_ROLE = "task_plan_reviewer"  # [BL-095]
    _CURRENT_TASK_ID = ""
    _reset_think_scratchpad()  # [BL-093]
    parsed, parse_failed = _query_and_parse_with_retry(
        prompt, client=client_task_plan_reviewer, model=model_task_plan_reviewer, label="Task Plan Reviewer",
        tools=[PYTHON_REPL_TOOL, READ_VERIFIED_FACT_TOOL, READ_DELIVERABLE_FILE_TOOL, DIFF_PLAN_DRAFT_VERSIONS_TOOL, WRITE_AGREEMENT_TOOL, WEB_SEARCH_TOOL, WEB_FETCH_TOOL, READ_REFERENCE_FILE_TOOL, READ_ENTITY_TOOL, THINK_TOOL],
        fallback={"risk": "low", "constraint_issue": "none", "comment": "(JSONパース失敗のためnone扱い)",
                  "observations": "", "per_task_comments": []},
        state=state,
    )
    if parse_failed:
        print("🚨 [Task Plan Reviewer] JSON判定の取得に失敗しました。安全のためフェイルクローズ(major)します。")
        return {
            "risk": "high", "constraint_issue": "major",
            "comment": "(レビューのJSON解析に失敗したため、安全のため差し戻します。計画内容自体に問題があったとは限りません)",
            "observations": "", "per_task_comments": [],
        }
    return parsed


def _find_phase_id_for_task(phases: list[dict], task_id: str) -> str:
    """[BL-087 Stage2改善] phases配列から指定task_idを含むphase_idを探す。
    見つからなければ空文字を返す（plan_drafts注釈はphase_id/task_id両方をキーにするため）。
    """
    for phase in phases:
        for task in phase.get("tasks", []):
            if task.get("task_id") == task_id:
                return phase.get("phase_id", "")
    return ""


def _find_task_by_id(phases: list[dict], task_id: str) -> dict | None:
    """[BL-087 Stage2改善] phases配列から指定task_idのタスク本体を探す。task_planner_nodeの
    事前シードが何らかの理由で欠けていた場合でも、_append_reviewer_comment_to_planが
    骨格文書を自前で生成できるようtask_for_skeletonとして渡すために使う。"""
    for phase in phases:
        for task in phase.get("tasks", []):
            if task.get("task_id") == task_id:
                return task
    return None


def task_plan_reviewer_node(state: LineageState) -> LineageState:
    """[BL-087 Stage2] task_planner_node直後、実行が始まる前に1回だけ発火する計画レビュー
    ゲート。majorと判定された場合はphasesをクリアしてtask_plannerへ差し戻す（最大5回まで、
    ユーザーが2026-08-07に手動で2から変更。
    上限到達後は指摘が残っていても計画を承認して進行する）。plan_review_doneはチェックポイント
    再開時に毎回レビューし直さないためのガード（task_planner_nodeのturn_count==1ガードと同型）。
    """
    if state.get("plan_review_done") or not state.get("phases"):
        return state

    print("\n------ [task_plan_reviewer] が初期計画をレビュー中 ------\n")
    result = call_task_plan_reviewer(
        state["phases"], state["goal"],
        goal_essence_text=_get_goal_essence_text(get_active_conn(), state["run_id"]),
        state=state,
    )
    print(f"\n[task_plan_reviewer] 判定: {result}\n")

    # [BL-087 Stage2改善] タスク固有の指摘を、plan_drafts（フェーズ・タスク表のホワイトボード）
    # へ直接書き込む。task_idキーで対象を特定するため、Detector注釈のような文中excerpt一致
    # （BL-074/076既知の脆さ）は使わない。phasesをクリアする前に実行する必要がある
    # （クリア後はどのphase_idに属していたか分からなくなるため）。
    per_task_comments = result.get("per_task_comments", []) or []
    _conn = get_active_conn()
    feedback_parts = [result.get("comment", "")] if result.get("comment") else []
    for item in per_task_comments:
        task_id = item.get("task_id", "")
        comment = item.get("comment", "")
        if not task_id or not comment:
            continue
        phase_id = _find_phase_id_for_task(state["phases"], task_id)
        if phase_id:
            task_for_skeleton = _find_task_by_id(state["phases"], task_id)
            _comment_appended = _append_reviewer_comment_to_plan(_conn, state["run_id"], phase_id, task_id, comment, task_for_skeleton)
            if _comment_appended:
                print(f"  📝 [task_plan_reviewer] レビュー指摘をtask_id={task_id}の計画文書へ追記しました。")
            else:
                print(f"  ⚠️ [task_plan_reviewer] task_id={task_id}へのレビュー指摘追記に失敗しました（対象文書または見出しが見つかりません）。")
        feedback_parts.append(f"[{task_id}] {comment}")
    combined_feedback = "\n".join(feedback_parts)

    retry_count = state.get("plan_reviewer_retry_count", 0)
    if result.get("constraint_issue") == "major" and retry_count < 5:
        state["plan_reviewer_retry_count"] = retry_count + 1
        state["plan_reviewer_feedback"] = combined_feedback
        state["phases"] = []  # task_planner_nodeの`not state.get("phases")`ガードにより再生成される
        # [BL-126 Stage C/§11(3)] turn_count==1の初回計画パスは上記phases=[]だけで
        # task_planner_nodeの`not phases`ガードにより再発火するが、ラン途中の再構成
        # （turn_count!=1）ではこのガードが効かないため、plan_revision_reasonを再セットして
        # 新設のガード（design.md §6）経由で再発火させる。上限（5回、ユーザーが手動で2から
        # 変更）は既存のplan_reviewer_retry_countのロジックをそのまま再利用する（新しい上限は
        # 設けない）。
        if state.get("turn_count", 1) != 1:
            state["plan_revision_reason"] = combined_feedback or "task_plan_reviewerによる差し戻し"
        decision = make_decision("task_plan_reviewer", "初期計画を差し戻し", result.get("comment", ""))
    else:
        state["plan_review_done"] = True
        decision = make_decision(
            "task_plan_reviewer", "初期計画を承認",
            result.get("comment") or "レビュー完了、重大な問題なし"
        )
    db_append_decision(decision, get_active_conn(), state["run_id"])
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
    # [BL-078] Orchestratorが専門家選定時に考えたタスク固有の着眼点・注意点をExpertへ引き継ぐ。
    state["expert_focus_guidance"] = result.get("focus_guidance", "")
    if state["expert_focus_guidance"]:
        print(f"  🎯 [Focus Guidance] {state['expert_focus_guidance']}")
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
        # [BL-075/D-047] F-7.3のwhiteboardロールバックは撤廃した。ロールバックは常に「1つ前の
        # バージョンが健全」という前提だったが、major判定が毎回別の新しい懸念を指摘するケースでは
        # rows[1]が過去に別件でmajor判定された版であることがあり、機械的に2版前へ戻すことで
        # 既に修正済みだった問題（例: 有給休暇日数の労基法違反修正）を無警告で再導入していた
        # （実ドライランで確認）。現在はホワイトボードの最新内容をそのまま保持し、Expertが
        # Detectorの指摘箇所のみを差分編集（部分修正）で直す方針とする（call_expertのプロンプト参照）。
        state["expert_last_whiteboard_edit"] = None
    else:
        state["expert_retry_count"] = 0

    output = call_expert(
        expert_name=state["selected_expert"],
        state=state,
        config=config
    )
    # BL-033: Expertが実際に実行したpython_replのcode/resultを、次のDetectorが参照できるようstateへ保存する。
    state["expert_last_python_calls"] = get_last_python_calls()
    # [R5 F-2.1] Expertのreasoningを、次のDetectorが思考プロセス監査に使えるようstateへ保存する。
    state["expert_last_reasoning"] = get_last_reasoning_text()
    # [R3b §3.5.1] 今ターンでwrite_agreementが1回でも成功したかをstateに保存
    state["expert_wrote_agreement"] = get_last_write_agreement_succeeded()
    # [DEBUG][BL-038調査用/2026-07-22] expert_node内でセットした直後の値を確認する一時計装。
    print(f"[DEBUG] expert_node: get_last_write_agreement_succeeded()={state['expert_wrote_agreement']!r}")
    # [R4] 今ターンでwhiteboard_draftsに新バージョンが書き込まれた場合、次ターンのロールバック
    # 判定のためstateへ保存する（_LAST_WHITEBOARD_EDITはquery_AI呼び出しごとにリセットされるため）。
    state["expert_last_whiteboard_edit"] = get_last_whiteboard_edit()
    # [BL-130] 今ターンでask_user_questionが呼ばれた場合、成果物レビューではなく相談ターンとして
    # 扱う。次のDetector/Decision Extractorがこのフラグを見て監査・抽出をスキップする
    # （消費・リセットはgenerate_user_utterance_node、Userが回答した直後に行う）。
    _ask_q = get_last_ask_user_question()
    state["expert_consultation_mode"] = bool(_ask_q)
    state["expert_pending_question"] = _ask_q["question_text"] if _ask_q else ""
    state["expert_blocking_reason"] = _ask_q["blocking_reason"] if _ask_q else ""
    if _ask_q:
        print(f"  🗨️ [BL-130] Expertがask_user_questionを呼びました。expert_consultation_mode=Trueにします: {_ask_q['question_text']}")
    print(f"\n------ 完了 ------")
    # [BL-103] why=生テキスト先頭100文字の機械的truncationは劣化版要約だったため、
    # BL-093で既に必須化されているthinkの最終decided/why（無ければsummary）に置き換える。
    decision = make_decision(who=f"expert:{state['selected_expert']}", what="タスクを実行",
                              why=get_last_think_summary() or (output or "")[:150])
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

    # [BL-130] Expertが今ターンask_user_question（成果物ではなく質問）を呼んだ場合、
    # 監査対象の成果物が存在しないため、LLM呼び出しを伴う通常監査はスキップし軽量パスで
    # constraint_issue="none"を返す。BL-033の検算フェイルクローズもこの軽量パスには適用しない
    # （質問ターンに数値検算を要求するのは筋違いのため）。
    if target_role == "assistant" and state.get("expert_consultation_mode"):
        print("🗨️ [Detector] BL-130: Expert相談ターン（質問のみ・成果物なし）のため、詳細監査をスキップし軽量パスを適用します。")
        result = {"risk": "low", "constraint_issue": "none", "comment": "(BL-130) Expert相談ターンのため詳細監査をスキップしました。", "observations": ""}
    else:
        # [BL-126 Stage B] 直前のUser AIのターンでrevise_goalが成功していれば、通常の成果物
        # 監査ではなくreview_mode="goal_change"（§5の4判断基準）を使う。単発フラグのため、
        # 消費後は必ずリセットする（次ターン以降の通常監査に引き継がない）。
        review_mode = "goal_change" if state.get("goal_revision_pending_review") else "task_output"
        if review_mode == "goal_change":
            print("🧭 [Detector] BL-126 Stage B: 直前のrevise_goalをreview_mode=\"goal_change\"で監査します。")
            state["goal_revision_pending_review"] = False
        result = call_detector(state=state, target_role=target_role, review_mode=review_mode)

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

        # [BL-158] BL-136のソフトな強制文言（_get_forced_escalated_issues_text）だけでは、
        # User AIが無視し得ることが実ドライラン（log/2026-08-03/2233）で判明した。BL-125の
        # 実ゲートと完全に同一の_get_blocking_issues_for_transitionを単一の判断源として
        # 再利用し、call_detectorのLLM判定に依存しない機械的な差し戻しを追加する。
        # ブロック対象issueが残っている限り、前進を試みる発言かどうかに関わらず毎ターン
        # 発火する（BL-136の強制文言自体が無条件であることと整合）。
        if target_role == "user":
            _blocking_issues = _get_blocking_issues_for_transition(
                get_active_conn(), state["run_id"], state.get("current_task_id", "")
            )
            print(
                f"  🔎 [BL-158] 現在タスク'{state.get('current_task_id', '')}'のブロック対象issueチェック: "
                f"{len(_blocking_issues)}件検出、今回のwrite_issue(RESOLVE/DEFER)成功="
                f"{state.get('user_wrote_issue_resolution', False)}"
            )
            if _blocking_issues and not state.get("user_wrote_issue_resolution", False):
                _topics = ", ".join(i["topic"] for i in _blocking_issues)
                print(
                    f"  🛑 [Detector] BL-158: 未解決・未先送りのescalated issue（{_topics}）が残っており、"
                    f"今回のターンでwrite_issue(RESOLVE/DEFER)が呼ばれていないため、機械的にmajorとします。"
                )
                result["constraint_issue"] = "major"
                result["comment"] = (
                    f"(BL-158機械的差し戻し) 現在のタスク（{state.get('current_task_id', '')}）に"
                    f"未解決・未先送りの重大issue（{_topics}）が残っています。write_issue(RESOLVE)"
                    "で解決するか、write_issue(DEFER)で対応予定task_idを明示してください。 "
                    + result.get("comment", "")
                )

    print(f"\n------ 完了 ------")
    print(
        f"【Detectorの判定内容】risk={result['risk']}, constraint_issue={result['constraint_issue']}\n"
        f"comment: {result['comment']}\n"
        f"observations（気づき・懸念、参考情報）: {result.get('observations', '') or '(なし)'}\n"
    )
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

    # [BL-051軽量版] constraint_issueの判定に関わらず、Detectorが自由記述で書き残した
    # 気づき・懸念を蓄積する。noneの回でも記録される点がconstraint_issue_logと異なる。
    observations = result.get("observations", "")
    if observations:
        state.setdefault("detector_observations_log", []).append({
            "turn": state["turn_count"],
            "target_role": target_role,
            "observations": observations,
        })

    # [BL-096] モデルが明示的にwrite_issueを呼ばなかった場合の機械的バックアップ書き込み。
    # observationsが十分な長さの場合、task単位のtopicでissue_logへのCREATEを自動的に試みる
    # （モデルの判断を上書きするものではなく、呼ばなかった場合の保険に留める）。
    if observations and len(observations) >= 30:
        _bl096_phase_id = state.get("current_phase", {}).get("phase_id", "")
        _bl096_topic = f"detector_observation_{current_task_id}" if current_task_id else "detector_observation_no_task"
        _write_issue_impl(
            {
                "action_type": "CREATE", "topic": _bl096_topic, "severity": "minor",
                "description": observations, "phase_id": _bl096_phase_id, "task_id": current_task_id,
            },
            get_active_conn(), state["run_id"], "detector_auto", _bl096_phase_id, current_task_id,
        )
        print(f"  🗂️ [BL-096] Detectorのobservations（{len(observations)}字）を機械的バックアップとしてissue_logへ自動起票しました: topic={_bl096_topic}")

    if result["risk"] == "high":
        print("🛑 [Detector] risk=highを検出しました。state['halt']=Trueで緊急停止します。")
        state["halt"] = True
    elif result["risk"] == "medium":
        state["medium_risk_streak"] = state.get("medium_risk_streak", 0) + 1
        print(f"  ⚠️ [Detector] risk=medium（連続{state['medium_risk_streak']}回）")
        if state["medium_risk_streak"] >= 3:
            print("  🚩 [Detector] risk=mediumが3回連続したため、state['drift_flag']=Trueにします。")
            state["drift_flag"] = True
    else:
        state["medium_risk_streak"] = 0

    # [R5 F-3.7] トークンコスト抑制のため、major判定時のみ思考ログをスナップショット保存する。
    _detector_thought = get_last_reasoning_text() if result["constraint_issue"] == "major" else None
    decision = make_decision(
        who="detector",
        what=f"risk={result['risk']}, constraint_issue={result['constraint_issue']}",
        why=result["comment"],
        internal_thought_process=_detector_thought,
    )
    _conn = get_active_conn()
    db_append_decision(decision, _conn, state["run_id"])

    # [BL-076] Expertの成果物（ホワイトボード）に対するmajor判定の場合、指摘をプロンプト注入
    # だけでなくホワイトボード本文にも永続的な注釈として埋め込む。target_excerptがホワイトボード内で
    # 一意に特定できない場合は挿入しない（誤った位置への注釈でExpertを混乱させないため）。
    if result["constraint_issue"] == "major" and target_role == "assistant":
        _phase_id_for_annotation = state.get("current_phase", {}).get("phase_id", "")
        if current_task_id and _phase_id_for_annotation:
            annotated, _annotate_reason = _annotate_whiteboard_with_detector_comment(
                _conn, state["run_id"], _phase_id_for_annotation, current_task_id,
                target_excerpt=result.get("target_excerpt", ""), comment=result["comment"],
                decision_id=decision["id"],
            )
            if annotated:
                print(f"  🔴 [Whiteboard Annotated] Detector指摘をホワイトボードに注釈として埋め込みました（{_annotate_reason}、decision_id={decision['id']}）。")
            else:
                print(f"  ⚠️ [Whiteboard Annotate Failed] 注釈の埋め込みに失敗しました（{_annotate_reason}、decision_id={decision['id']}）。BL-074参照。")

    # [BL-132] 従来は`get_decisions_from_db(...)[1:]`で全run分の決定履歴を丸ごと
    # 再取得・再出力しており（変数名は"this_turn_decisions"だが実際は「run開始2件目以降
    # 全部」）、detector_nodeが呼ばれるたび（user_detector/expert_detector両方が同じ
    # 関数を指す）に過去の全決定が毎回重複して出力され続けていた（ログ肥大化・O(n^2)化、
    # かつBL-128の「同一検算コメントが繰り返し出現」の一因）。この関数はこの呼び出し1回分の
    # 決定（`decision`）を既に手元に持っているため、DB再取得はせずそれだけを出力する。
    print(f"  [{decision['who']}]")
    print(f"    - what: {decision['what']}")
    print(f"    - why: {decision['why']}")

    return state

def _get_blocking_issues_for_transition(conn: sqlite3.Connection, run_id: str, departing_task_id: str,
                                         exclude_acknowledged: bool = False, round_count: int = 0) -> list[dict]:
    """[BL-125] departing_task_idから離脱する際にタスク遷移をブロックすべき未解決issueを取得する。
    severity='major'（D-079/D-080の不変条件によりstatus='escalated'を伴う）かつ、
    最後にこのtaskで検出された（last_seen_task_id一致）ものだけを対象とする。
    BL-136のDEFER（defer_to_task_idが設定済み）で既に明示的に先送りされたものは対象外とし、
    「今すぐ解決」と「明示的に将来のtaskへ先送り」のどちらかが済んでいれば遷移を許可する。

    [BL-194 CONSTRAINT] このSQLは意図的にBL-194の共有述語（_is_issue_effectively_deferred/
    _get_actionable_escalated_issues）へ統一しない。理由: (1) BL-167の受け皿失効リバイバル
    （defer先タスク完了時にDEFERを無効化する）をここへ持ち込むと、完了済みタスクへDEFERされた
    issueが離脱ゲートに復活し、現在タスクの担当者が解けないissueでタスクを出られなくなる
    新規デッドロックを招く（BL-194設計書§9-R2）。(2) BL-125の遷移ゲートは督促（是正を促す）
    ではなく安全装置（未解決のまま離脱させない）という異なる関心事であり、BL-194不変条件
    「督促集合と滞留集合は同一述語で決定する」の明示的な例外として据え置く（D-163参照）。
    exclude_acknowledged=Trueの場合のみACKNOWLEDGE中（BL-194 §5、S7）のissueを追加除外する
    ——BL-158の機械的差し戻し（督促経路）だけがこの引数を使い、本体（離脱ゲート）は
    既定Falseのまま抑制しない。「今対応中」と表明しても未解決のまま離脱することは許さない、
    というACKNOWLEDGEの設計上の要（万能の逃げ道にしないための歯止め）。
    """
    if not departing_task_id:
        return []
    rows = conn.execute(
        "SELECT * FROM issue_log WHERE run_id=? AND status='escalated' AND severity='major' "
        "AND last_seen_task_id=? AND (defer_to_task_id IS NULL OR defer_to_task_id='') ORDER BY id",
        (run_id, departing_task_id)
    ).fetchall()
    result = [dict(r) for r in rows]
    if exclude_acknowledged:
        result = [r for r in result if not _is_issue_acknowledged_active(r, round_count)]
    return result


def _resolve_task_transition(state: LineageState, transition: dict,
                              structured_redirect: dict | None = None) -> None:
    """[CONSTRAINT] BL-024: current_phase/current_task_idの唯一の書き手。
    LLMが返したphase_id/task_idがtask_planner確定済みのphases/tasksに実在しない場合は
    書き込みを拒否し、直前の値を維持する（check_docs_consistency.pyが存在しないリンクを
    機械的に検出するのと同型のフェイルクローズ）。
    [BL-125] さらに、離脱しようとしているtaskに未解決・未先送りのsevere issueが残っている場合も
    同様に遷移を拒否する（BL-134の実例: severity=major・status=escalatedのissueが未解決のまま
    task_1_1→task_1_2の遷移が起きてしまった問題への対応）。
    [BL-191] `structured_redirect`（Stage4のschedule_task_focusツールが構造化して渡す決定）が
    非Noneの場合、call_decision_extractorの自由文脈`advances_to_task_id`抽出より優先される。
    `redirect_backward`/`force_resume`はここでcurrent_task_id/current_phaseを確定させその場で
    returnする（以降の自由文脈抽出ロジックは無視）。`joint_focus`/`clear_companion`は
    current_task_idを変更しないため、適用後も既存の自由文脈遷移ロジックへそのまま処理を続ける。
    """
    if structured_redirect:
        decision_type = structured_redirect.get("decision_type")
        if decision_type == "redirect_backward":
            _apply_backward_redirect(state, structured_redirect)
            return
        if decision_type == "joint_focus":
            _apply_joint_focus(state, structured_redirect)
        elif decision_type == "clear_companion":
            state["task_focus_companion"] = None
        elif decision_type == "force_resume":
            _force_resume_forward_focus(state)
            return

    next_phase_id = transition.get("advances_to_phase_id")
    next_task_id = transition.get("advances_to_task_id")
    if not next_phase_id and not next_task_id:
        return

    phase_lookup = {p["phase_id"]: p for p in state.get("phases", [])}
    target_phase = phase_lookup.get(next_phase_id) if next_phase_id else None

    # [BL-210] next_phase_idが省略された場合、従来はstate["current_phase"]へ即決め打ちして
    # いたため、フェーズをまたぐtask遷移（例: phase_3のtask_3_2からphase_4のtask_4_0）を
    # call_decision_extractorがadvances_to_task_idだけ正しく抽出しadvances_to_phase_idを
    # nullのまま返すと、探索対象がcurrent_phase（phase_3）に固定され、task_4_0はそこに
    # 存在しないため「存在しないtask_id」として毎ターン拒否され続ける事故が発生した
    # （実ドライラン`log/2026-08-11/0118`で8回連続、最終的にReflectionがこれを
    # 「切替拒否の反復＝実質的な停滞」と判定しHALTした）。next_task_idの所属フェーズを
    # 全フェーズ横断で探す（BL-191の_find_phase_containing_taskを流用、正規化前後の両方で
    # 試す）。それでも見つからなければ、従来通りcurrent_phaseへフォールバックする
    # （phase_idのみの遷移要求等、既存の挙動を壊さないため）。
    if target_phase is None and next_task_id:
        normalized_next_task_id = next_task_id.replace(".", "_")
        target_phase = (
            _find_phase_containing_task(state.get("phases", []), next_task_id)
            or _find_phase_containing_task(state.get("phases", []), normalized_next_task_id)
        )
    if target_phase is None:
        target_phase = state.get("current_phase")
    if not target_phase:
        print(f"  ⚠️ [decision_extractor] 存在しないphase_id '{next_phase_id}' への遷移要求を無視しました。")
        return

    if next_task_id:
        # [BL-039] LLMはtask_idを「task_1.1」のようなドット区切りで返すことがあるが、
        # task_planner確定済みのtask_idは「task_1_1」のアンダースコア区切りで統一されている。
        # 正規化なしで単純一致比較すると常に不一致となり、current_task_idが永久に
        # フォールバック値のまま更新されない（実ドライランで全遷移が失敗する事故を確認済み）。
        valid_task_ids = {t["task_id"] for t in target_phase.get("tasks", [])}
        normalized_next_task_id = next_task_id.replace(".", "_")
        if next_task_id in valid_task_ids:
            canonical_task_id = next_task_id
        elif normalized_next_task_id in valid_task_ids:
            canonical_task_id = normalized_next_task_id
        else:
            print(f"  ⚠️ [decision_extractor] 存在しないtask_id '{next_task_id}' への遷移要求を無視しました。")
            return

        # [BL-125] 離脱しようとしているtaskに未解決・未先送りのsevere issueが残っている場合は
        # 遷移を拒否する（BL-134の再発防止。defer_to_task_idで明示的に先送り済みのものは許容する）。
        departing_task_id = state.get("current_task_id", "")
        if canonical_task_id != departing_task_id:
            blocking_issues = _get_blocking_issues_for_transition(
                get_active_conn(), state["run_id"], departing_task_id
            )
            if blocking_issues:
                topics = [i["topic"] for i in blocking_issues]
                print(
                    f"  🛑 [BL-125] '{departing_task_id}'に未解決・未先送りのsevere issueが"
                    f"{len(blocking_issues)}件存在するため、'{canonical_task_id}'への遷移をブロックしました: {topics}"
                )
                state["task_transition_blocked_issue_topics"] = topics
                return

            # [BL-176] 離脱しようとしているtaskがまだ承認済み（Approved相当のDeliverable）で
            # ない場合も遷移を拒否する。write_agreementによる承認の成否（即時DBコミット＋事後の
            # Detector監査）と、この関数への入力advances_to_task_id（decision_extractorが会話文
            # から自由文脈で抽出する遷移意図）は完全に独立した経路であり、Userが1発言で「現タスク
            # の承認」と「次タスクへの指示」を同時に述べても両者の整合性は保証されない。BL-125と
            # 同型の機械的ゲートとして、承認未成立のままcurrent_task_idが先走ることを防ぐ。
            # departing_task_idが空（まだ一度もタスクに着手していない最初の遷移）の場合は、
            # そもそも承認すべき前任taskが存在しないため対象外とする。
            if departing_task_id and not _is_task_completed(get_active_conn(), state["run_id"], departing_task_id):
                print(
                    f"  🛑 [BL-176] '{departing_task_id}'はまだ承認済み（Approved相当）の"
                    f"Deliverableが存在しないため、'{canonical_task_id}'への遷移をブロックしました。"
                )
                state["task_transition_blocked_unapproved_task_id"] = departing_task_id
                return

        state["current_task_id"] = canonical_task_id
        print(f"  ➡️ [decision_extractor] current_task_id を '{canonical_task_id}' に更新しました。")

    # [BL-210] next_phase_idが明示されていなくても、next_task_idの全フェーズ横断探索で
    # current_phaseと異なるフェーズが見つかった場合はcurrent_phaseも追従させる
    # （そうしないとcurrent_task_idだけが新フェーズを指し、current_phaseは旧フェーズの
    # ままという不整合状態になる）。
    resolved_phase_id = target_phase.get("phase_id") if target_phase else None
    if resolved_phase_id and resolved_phase_id != (state.get("current_phase") or {}).get("phase_id"):
        state["current_phase"] = target_phase
        print(f"  ➡️ [decision_extractor] current_phase を '{resolved_phase_id}' に更新しました。")


def _find_phase_containing_task(phases: list[dict], task_id: str) -> dict | None:
    """[BL-191] task_idを含むphaseオブジェクトそのものを返す（_find_task_by_idはtask本体を返すが、
    ここではcurrent_phaseへ丸ごと差し替えるためphase側が必要、_find_phase_id_for_taskはphase_idの
    文字列のみを返す）。BL-190の_reconcile_current_phase_after_replanと同型の全フェーズ線形探索。"""
    for phase in phases:
        for t in phase.get("tasks", []):
            if t.get("task_id") == task_id:
                return phase
    return None


def _infer_directive_target_task_ids(item: dict, task_id_to_phase_id: dict) -> set[str]:
    """[BL-211] Directiveイベントの構造化フィールド`task_id`が空文字のまま返された場合に、
    同じイベントの自然文側（topic/content/rationale）とowned_variable_valuesから移行先task_idを
    推定する。

    [CONSTRAINT] 推定結果は計画に実在するtask_idのみに限定する（task_id_to_phase_idに存在する
    ものだけを返す）。LLMが自然文中で言及しただけの架空タスクを遷移先に昇格させないため。

    [REJECTED] 「最初に見つかったtask_idを採用する」案は、差し戻し文が「task_4_3ではなく
    task_4_2の修正を先に」のように複数タスクへ言及するケースで誤った先読み切替を起こすため
    採用しない。呼び出し側が候補が1件のときだけ補完するフェイルクローズ方針を取れるよう、
    ここでは候補集合をそのまま返す。
    """
    haystack = " ".join(
        str(v) for v in (
            item.get("topic", ""), item.get("content", ""), item.get("rationale", ""),
            *(item.get("owned_variable_values") or {}).values(),
        ) if v
    )
    candidates = set()
    # BL-039と同様、会話文中のドット区切り表記（task_4.3）もアンダースコア表記へ正規化する。
    for raw in re.findall(r"task[_\s]?\d+[_.]\d+", haystack, flags=re.IGNORECASE):
        normalized = re.sub(r"[\s.]", "_", raw.strip().lower())
        if normalized in task_id_to_phase_id:
            candidates.add(normalized)
    return candidates


def _apply_backward_redirect(state: LineageState, redirect: dict) -> None:
    """[BL-191] schedule_task_focus(decision_type="redirect_backward")による構造化された
    過去タスクへの一時的フォーカス切替を適用する。[CONSTRAINT] BL-125/BL-176のdeparting-task
    ゲート（未解決severe issue・未承認Deliverable）は意図的に適用しない——これは「離脱」では
    なく「一時中断」であり、_maybe_resume_forward_focus経由で必ず元タスクへ復帰する前提のため
    （中断中のフォワードタスク自身の未解決issue/未承認状態は、復帰後に本来の遷移として改めて
    BL-125/176のチェックを受ける）。
    """
    target_task_id = redirect.get("target_task_id", "")
    target_phase = _find_phase_containing_task(state.get("phases", []), target_task_id)
    if not target_phase:
        print(f"  ⚠️ [BL-191] 存在しないtask_id '{target_task_id}' へのredirect_backward要求を無視しました。")
        return
    stack = state.get("task_focus_stack", [])
    if stack:
        print("  ⚠️ [BL-191] 既に一時中断中のフォーカスがあるため、二重のredirect_backwardを無視しました（ツール側の深さ1ガードのはずが漏れています）。")
        return
    current_task_id = state.get("current_task_id", "")
    current_phase = state.get("current_phase", {})
    stack.append({
        "task_id": current_task_id, "phase_id": current_phase.get("phase_id", ""),
        "reason": redirect.get("reason", ""), "pushed_at_round": state.get("round_count", 0),
        "focused_task_id": target_task_id,
        "baseline_agreement_id": redirect.get("baseline_agreement_id", ""),
    })
    state["task_focus_stack"] = stack
    state["current_task_id"] = target_task_id
    state["current_phase"] = target_phase
    state["task_focus_redirect_count"] = state.get("task_focus_redirect_count", 0) + 1
    state["task_focus_redirect_notice"] = (
        f"[BL-191] 発注者の判断により、作業対象を一時的に過去タスク'{target_task_id}'へ切り替えました"
        f"（理由: {redirect.get('reason', '')}）。このタスクの成果物が再承認され次第、"
        f"自動的に'{current_task_id}'へ復帰します。"
    )
    print(f"  ⏪ [BL-191] current_task_idを一時的に'{target_task_id}'へ切替えました（元: '{current_task_id}'、resume待ち）。")


def _apply_joint_focus(state: LineageState, redirect: dict) -> None:
    """[BL-191] schedule_task_focus(decision_type="joint_focus")の適用。current_task_id/
    current_phaseは変更しない（BL-025のスコープガードレール意図を尊重）。"""
    companion_task_id = redirect.get("companion_task_id", "")
    if not _find_phase_containing_task(state.get("phases", []), companion_task_id):
        print(f"  ⚠️ [BL-191] 存在しないtask_id '{companion_task_id}' へのjoint_focus要求を無視しました。")
        return
    state["task_focus_companion"] = {
        "companion_task_id": companion_task_id,
        "companion_phase_id": redirect.get("companion_phase_id", ""),
        "primary_task_id": state.get("current_task_id", ""),
        "reason": redirect.get("reason", ""),
        "declared_at_round": state.get("round_count", 0),
        "baseline_agreement_id": redirect.get("baseline_agreement_id", ""),
    }
    print(f"  🔗 [BL-191] task_focus_companionを設定しました: {companion_task_id}")


def _force_resume_forward_focus(state: LineageState) -> None:
    """[BL-191] schedule_task_focus(decision_type="force_resume")の適用。
    task_focus_stackが未完了のままでも強制的にポップし、元のフォワードタスクへ戻る安全弁。
    対象の過去タスクへは、放置されたまま失われないようBL-163と同型の軽微issueを再起票する。"""
    stack = state.get("task_focus_stack", [])
    if not stack:
        print("  ⚠️ [BL-191] force_resume要求を受けましたが、中断中のフォーカスがありません。")
        return
    abandoned_task_id = state.get("current_task_id", "")
    entry = stack[-1]
    resume_phase = _find_phase_containing_task(state.get("phases", []), entry["task_id"])
    state["task_focus_stack"] = stack[:-1]
    if not resume_phase:
        print(f"  ⚠️ [BL-191] 復帰先task_id '{entry['task_id']}'が計画に存在しません。スタックのみクリアします。")
        return
    state["current_task_id"] = entry["task_id"]
    state["current_phase"] = resume_phase
    state["task_focus_resume_notice"] = (
        f"[BL-191] 過去タスク'{abandoned_task_id}'は未解決のまま、意図的にフォーカスを"
        f"打ち切り'{entry['task_id']}'へ復帰しました。'{abandoned_task_id}'は整合性再確認issueとして"
        "再度記録されています。"
    )
    if abandoned_task_id:
        _write_issue_impl(
            {"action_type": "CREATE", "topic": f"task_focus_force_resume_unresolved_{abandoned_task_id}",
             "severity": "minor",
             "description": f"[BL-191] '{abandoned_task_id}'への一時フォーカスはforce_resumeにより未解決のまま打ち切られました。改めて対応が必要です。"},
            get_active_conn(), state["run_id"], "revise_goal_auto", "", abandoned_task_id,
        )
    print(f"  ⏩⚠️ [BL-191] force_resume: '{abandoned_task_id}'を未解決のまま'{entry['task_id']}'へ復帰しました。")


def _maybe_resume_forward_focus(state: LineageState, conn: sqlite3.Connection, run_id: str) -> None:
    """[BL-191] task_focus_stack末尾（中断中のフォワードタスク）が存在し、現在フォーカス中の
    過去タスクの成果物がredirect時点（baseline_agreement_id）から更新され、かつApproved相当
    （BL-167のis_task_completed）に達していれば、自動的にポップしてcurrent_task_id/
    current_phaseを復帰させる。LLM判断を経由しない機械的トリガー。

    [BUG-1対策] `_is_task_completed`だけを条件にすると、BL-163でフラグされた過去タスクは
    ステータス上まだApprovedのまま残っているため、redirect直後・Expertが何も手を付けていない
    次の呼び出しの時点で即座に「完了済み」と誤判定し、redirectがその場で無効化されてしまう。
    baseline_agreement_idと現在の最新Deliverable agreement_idを比較し、実際に新しい成果物が
    承認された場合のみ復帰する。
    [BUG-2対策] task_focus_stackが非空なのにcurrent_task_idが空文字列（BL-190のパターン3で
    フォーカス中タスク自体が計画再構成により消失しクリアされた場合）は、_is_task_completed("")
    が恒久的にFalseを返すため、通常の完了待ちでは永久にスタックが残ってしまう。この場合は
    force_resumeと同じロジックで強制的に復帰させる（防御的な二重の安全網。主たる対策は
    _reconcile_current_phase_after_replan側に実装済み）。
    """
    stack = state.get("task_focus_stack", [])
    if not stack:
        return
    focused_task_id = state.get("current_task_id", "")
    if not focused_task_id:
        print("  ⚠️ [BL-191] task_focus_stackが非空のままcurrent_task_idが空になっています"
              "（計画再構成でフォーカス中タスクが消失した可能性）。強制的に復帰します。")
        _force_resume_forward_focus(state)
        return
    entry = stack[-1]
    if not _is_task_completed(conn, run_id, focused_task_id):
        return
    baseline_agreement_id = entry.get("baseline_agreement_id", "")
    current_agreement = _find_active_deliverable_agreement(
        conn, run_id, _find_phase_id_for_task(state.get("phases", []), focused_task_id), focused_task_id
    )
    current_agreement_id = current_agreement.get("id", "") if current_agreement else ""
    if current_agreement_id == baseline_agreement_id:
        # redirect時点から成果物が更新されていない（BL-163でフラグされただけの、まだ着手前の
        # 過去タスク等）。まだ「手戻りが完了した」とは言えないため復帰しない。
        return
    resume_phase = _find_phase_containing_task(state.get("phases", []), entry["task_id"])
    state["task_focus_stack"] = stack[:-1]
    if not resume_phase:
        print(f"  ⚠️ [BL-191] 復帰先task_id '{entry['task_id']}'が計画に存在しません（再構成で消失した可能性）。スタックのみクリアします。")
        return
    state["current_task_id"] = entry["task_id"]
    state["current_phase"] = resume_phase
    state["task_focus_resume_notice"] = (
        f"[BL-191] 一時中断していた過去タスク'{focused_task_id}'が再承認されたため、"
        f"'{entry['task_id']}'へ自動復帰しました。"
    )
    print(f"  ⏩ [BL-191] '{focused_task_id}'が承認済みになったため、中断していた'{entry['task_id']}'へ復帰しました。")


def _maybe_clear_resolved_companion(state: LineageState, conn: sqlite3.Connection, run_id: str) -> None:
    """[BL-191] joint_focusで設定されたcompanionが、宣言時点（baseline_agreement_id）から
    実際に更新されApproved相当に達したら自動的にクリアする（_maybe_resume_forward_focusと
    同型のbaseline比較つき機械的トリガー、BUG-1と同型の早期クリア防止）。"""
    companion = state.get("task_focus_companion")
    if not companion:
        return
    companion_task_id = companion["companion_task_id"]
    if not _is_task_completed(conn, run_id, companion_task_id):
        return
    baseline_agreement_id = companion.get("baseline_agreement_id", "")
    current_agreement = _find_active_deliverable_agreement(
        conn, run_id, _find_phase_id_for_task(state.get("phases", []), companion_task_id), companion_task_id
    )
    current_agreement_id = current_agreement.get("id", "") if current_agreement else ""
    if current_agreement_id == baseline_agreement_id:
        return
    print(f"  ✅ [BL-191] companion task '{companion_task_id}'が解決済みのためtask_focus_companionをクリアしました。")
    state["task_focus_companion"] = None


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

    # [BL-191] pending_task_redirectはUser AIのStage4が設定するものであり、
    # decision_extractor_nodeはuser_decision_extractor/expert_decision_extractorの両方の
    # グラフノードで共用されているため、target_role=="user"の場合のみ消費する
    # （独立レビュー指摘6-3。expert_decision_extractor側で誤って消費してしまうと、Expertの
    # ターンで意図せずredirect/joint_focusが適用されてしまう）。
    _pending_redirect = None
    if target_role == "user":
        _pending_redirect = state.get("pending_task_redirect")
        state["pending_task_redirect"] = None  # [BL-191] one-shot consume

    existing_topics = list({a["topic"] for a in get_agreements_from_db(_conn, _run_id) if a.get("status") != "Superseded"})
    current_task_for_extraction = _get_current_task(state)
    owns_variables = current_task_for_extraction.get("owns_variables", [])
    # [BL-039] 全フェーズのtask_idをLLMに提示し、正しい表記でのコピーを促す。
    valid_task_ids = [t["task_id"] for phase in state.get("phases", []) for t in phase.get("tasks", [])]
    # [BL-082] 先送り事項の申し送り先task_idからphase_id・Taskディクショナリを逆引きするための
    # マップ（_resolve_task_transitionのphase_lookupと同じ、全フェーズ一巡のパターン）。
    task_id_to_phase_id: dict[str, str] = {}
    task_id_to_task: dict[str, dict] = {}
    for _phase in state.get("phases", []):
        for _t in _phase.get("tasks", []):
            task_id_to_phase_id[_t["task_id"]] = _phase["phase_id"]
            task_id_to_task[_t["task_id"]] = _t
    extracted_items, transition = call_decision_extractor(state["chat_history"], existing_topics, target_role, owns_variables, valid_task_ids)
    print(f"\n------ 完了 ------")

    # [R3b §3.5.1] 今ターンでwrite_agreementが1回でも成功したかをstateから取得
    wrote_agreement_this_turn = (
        state.get("expert_wrote_agreement", False) if target_role == "expert"
        else state.get("user_wrote_agreement", False)
    )
    # [DEBUG][BL-038調査用/2026-07-22] wrote_agreement_this_turnがなぜFalse評価されるか切り分けるための一時計装。
    print(
        f"[DEBUG] decision_extractor target_role={target_role!r} "
        f"expert_wrote_agreement={state.get('expert_wrote_agreement')!r} "
        f"user_wrote_agreement={state.get('user_wrote_agreement')!r} "
        f"-> wrote_agreement_this_turn={wrote_agreement_this_turn!r}"
    )

    for item in extracted_items:
        action_type = item.get("action_type", "CREATE")
        entry_type = item.get("entry_type", "Decision")
        status = item.get("status", "Proposed")
        topic = item.get("topic", "Unknown Topic")
        raw_content = item.get("content", "")
        rationale = item.get("rationale", "No reason provided")
        proposed_by = item.get("proposed_by", "Unknown")
        defer_to_task_id = item.get("defer_to_task_id", "")
        
        current_phase = state.get("current_phase", {})
        # [BL-206] dict.get(key, default)はキーが欠落した時しかdefaultを使わないため、
        # LLMが"phase_id": ""（空文字）を返すとそのまま採用されていた。tid（1行下）と同じ
        # `or`パターンへ揃える（BL-161がwrite_agreement経路で修正した同型のバグ）。
        phase_id = item.get("phase_id") or current_phase.get("phase_id", "unknown")
        task_id = item.get("task_id") or state.get("current_task_id", "")
        depends_on = item.get("depends_on", [])
        resource_claims = item.get("resource_claims", {})

        # BL-023 2.6節: owns_variablesに含まれる変数のみをverified_factsへ確定保存する
        # ★R3b §3.5.1: write_agreement呼び出し有無に関わらず毎ターン無条件実行
        owned_variable_values = item.get("owned_variable_values", {})
        if isinstance(owned_variable_values, dict):
            for var_name, var_value in owned_variable_values.items():
                if var_name in owns_variables:
                    upsert_verified_fact(
                        _conn, _run_id, var_name, var_value, unit="",
                        source_task_id=task_id, source_phase_id=phase_id,
                        confirmed_by=proposed_by
                        # [BL-041] confidence未指定→デフォルトのprovisionalで保存される。
                        # このパスはwrite_agreementのconfirmed_variables指定漏れの保険であり、
                        # Expert自身がconfidenceを判断した経路ではないため安全側に倒す。
                    )
                    print(f"  🔒 [verified_facts] '{var_name}' = {var_value} を暫定値(provisional)として保存しました（source: {task_id}）。")

        # ★R3b §3.5.1: write_agreementが呼ばれたターンはdecision_extractor_nodeによる
        # Agreement書き込み（db_append_agreement/db_supersede_agreement）をスキップする。
        # write_agreementが既にagreementsとverified_factsの両方を更新しているため、
        # 二重書き込みを防止する。verified_factsへの保存（上記のowned_variable_values→
        # upsert_verified_fact）はwrite_agreementのconfirmed_variables指定漏れの保険
        # として、write_agreement呼び出し有無に関わらず毎ターン無条件実行する。
        if not wrote_agreement_this_turn:
            # ===== 成果物のファイル書き出し処理 (バックアップ処理付き) =====
            content = "" # 初期化
            if entry_type == "Deliverable" and action_type == "CREATE":
                if len(raw_content) > 200:
                    content_to_save = raw_content
                else:
                    content_to_save = state.get("expert_output", "")
                if content_to_save:
                    filepath = save_deliverable_to_file(topic, content_to_save)
                    content = f"FILE_PATH:{filepath}"
                    print(f"  📁 [File Saved] 成果物 '{topic}' をファイルに保存しました: {filepath}")
                else:
                    content = raw_content
            elif entry_type == "Deliverable" and action_type == "UPDATE":
                 content = raw_content
            else:
                content = raw_content

            if action_type == "UPDATE" or status == "Approved_with_Conditions":
                target_topic = item.get("target_topic", topic)
                old_content = ""
                # [BL-206] entry_type不一致（例: 却下がentry_type='Decision'として抽出された）でも
                # topicが一致するだけでこのループがDeliverable行をsuperseded化してしまい、
                # _find_active_deliverable_agreement（entry_type='Deliverable'必須）が二度と
                # 発見できない識別子で置き換わる「孤児化」バグの原因になっていた（実ログで
                # edits失敗が空文字への照合として観測された、log/2026-08-11/0016で確定）。
                # supersede対象は同じentry_typeの行に限定する。
                for a in reversed(get_agreements_from_db(_conn, _run_id)):
                    if (a["topic"] == target_topic and a.get("entry_type") == entry_type
                            and a.get("status") != "Superseded"):
                        old_content = a["decision_what"]
                        db_supersede_agreement(a["id"], _conn, _run_id)
                        if proposed_by == "Unknown" or not proposed_by:
                            proposed_by = a.get("proposed_by", "Unknown")
                        break
                        
                # [BL-212追補/F5] 従来はold_contentの文字列プレフィックスだけで「ホワイトボード
                # 済みか」を判定していたため、BL-212の短い無効化理由文がold_contentに入っていると
                # 保護が発火せず、下の`content = raw_content`（LLMの200字要約）で上書きされ、
                # 直下のコメントが警告している「フル本文の孤立」がまさに起きる。
                # entry_typeがDeliverableの場合に限り、whiteboard_draftsの実在を直接確認する
                # （非Deliverableにこの判定を広げると、同じtask_idにホワイトボードがあるだけで
                # Decision/Directiveの本文までポインタ文字列へ差し替わってしまうため限定する）。
                _wb_recoverable = (
                    entry_type == "Deliverable"
                    and not old_content.startswith(("WHITEBOARD:", "FILE_PATH:"))
                    and get_latest_whiteboard(_conn, _run_id, phase_id, task_id) is not None
                )
                if old_content.startswith("WHITEBOARD:"):
                    # [BL-038/R4] このフォールバック経路（write_agreement未使用時の安全網）には、
                    # ホワイトボードへ差分パッチを当てる手段がない。プレーンテキストで無条件に
                    # 上書きすると、versioned historyごとポインタが失われ、フル本文が孤立する
                    # （実ドライランで観測: agreements行がSupersededになり短い要約文で置換された事故）。
                    # 正しい更新経路は write_agreement の edits であり、ここでは常に保護する。
                    content = old_content
                    print(f"  🔒 [Whiteboard Protected] 成果物 '{target_topic}' のホワイトボードポインタを保護し、次ターンへ引き継ぎました（フォールバック経路からの上書きを禁止）。")
                elif _wb_recoverable:
                    content = f"WHITEBOARD:{phase_id}:{task_id}"
                    print(f"  🔧 [BL-212] 成果物 '{target_topic}' のagreements行がホワイトボードポインタを失っていたため、whiteboard_drafts（task_id={task_id}）の実在を確認してポインタを復元しました。")
                elif old_content.startswith("FILE_PATH:"):
                    if not content or (not content.startswith("FILE_PATH:") and len(content) < 200):
                        content = old_content
                        print(f"  🔒 [File Protected] 成果物 '{target_topic}' のファイルパスを保護し、次ターンへ引き継ぎました。")
                    elif not content.startswith("FILE_PATH:") and len(content) >= 200:
                        _archive_old_deliverable_file(old_content[len("FILE_PATH:"):])
                        filepath = save_deliverable_to_file(target_topic, content)
                        content = f"FILE_PATH:{filepath}"
                        print(f"  📁 [File Updated] 成果物 '{target_topic}' の修正版を新しいファイルに保存しました: {filepath}")
                
                new_content = content if content else old_content
                if not new_content:
                    new_content = "(状態のみ更新)"
                
                agreement: Agreement = {
                    "id": f"AG-{int(time.time() * 1000)}", "timestamp": time.time(),
                    "action_type": "UPDATE", "entry_type": entry_type, "status": status,
                    "topic": target_topic, "decision_what": new_content, "reason_why": rationale,
                    "proposed_by": proposed_by, "phase_id": phase_id, "task_id": task_id,
                    "depends_on": depends_on, "resource_claims": resource_claims
                }
                db_append_agreement(agreement, _conn, _run_id)
                decision_log = make_decision(
                    who="decision_extractor",
                    what=f"合意更新[{status}]: {target_topic}",
                    why=f"[{proposed_by}] {rationale}"
                )
                db_append_decision(decision_log, _conn, _run_id)
                # [BL-073] Deliverableが承認された場合、対応するtask_idのDirectiveをApprovedへ解決する。
                if entry_type == "Deliverable" and status in RESOLVING_DELIVERABLE_STATUSES:
                    _resolve_directive_for_task(_conn, _run_id, task_id, phase_id, resolved_by=proposed_by)
            else:
                agreement: Agreement = {
                    "id": f"AG-{int(time.time() * 1000)}", "timestamp": time.time(),
                    "action_type": action_type, "entry_type": entry_type, "status": status,
                    "topic": topic, "decision_what": content, "reason_why": rationale,
                    "proposed_by": proposed_by, "phase_id": phase_id, "task_id": task_id,
                    "depends_on": depends_on, "resource_claims": resource_claims
                }
                db_append_agreement(agreement, _conn, _run_id)
                decision_log = make_decision(
                    who="decision_extractor",
                    what=f"新規抽出[{status}]: {topic}",
                    why=f"[{proposed_by}] {rationale}"
                )
                db_append_decision(decision_log, _conn, _run_id)
                # [BL-082] 先送り（entry_type=Directive, status=Deferred）の場合、agreements DBへの
                # 記録（監査履歴として温存）に加えて、申し送り先task_idの計画文書（plan_drafts）へも
                # 追記する。_build_agreements_contextはDirectiveを無条件除外するため、この文書経由の
                # 申し送りが後続タスクに実際に届く唯一の経路。target_task_idが解決できない場合は
                # 警告ログのみでスキップ（フェイルクローズ）。
                # ★依存関係の注意: この分岐は`if not wrote_agreement_this_turn:`（上記）の内側にある。
                # write_agreementツールは現状status="Deferred"を受け付けないため実害はないが、将来
                # ツール側にDeferredが追加された場合、この分岐がスキップされうる点に留意すること。
                if entry_type == "Directive" and status == "Deferred" and defer_to_task_id:
                    target_phase_id = task_id_to_phase_id.get(defer_to_task_id)
                    if target_phase_id:
                        _plan_note_appended = _append_deferred_note_to_plan(
                            _conn, _run_id, target_phase_id, defer_to_task_id,
                            note_text=raw_content or rationale, source_task_id=task_id,
                            task_for_skeleton=task_id_to_task.get(defer_to_task_id),
                        )
                        if _plan_note_appended:
                            print(f"  📌 [Deferred] '{topic}' を{defer_to_task_id}の計画文書へ申し送りました。")
                        else:
                            print(f"  ⚠️ [Deferred] '{topic}' の{defer_to_task_id}計画文書への申し送りに失敗しました（対象文書または見出しが見つかりません）。")
                        # [BL-154] plan_draftsへの申し送りと同時に、issue_log側にもseverity='minor'/
                        # status='open'で起票し、defer_to_task_idを初回作成時点から設定する。これにより
                        # Expert自身が発言で宣言した先送り（write_issueツールへの直接アクセスを持たない）
                        # も、BL-125の遷移ゲート・BL-144の滞留追跡・BL-145のissue駆動タスク明示化から
                        # 見える対象になる。target_roleによるゲーティングはしない（Expert/User双方の
                        # 抽出ブランチが同じ先送り検出指示を持つため、一律に適用する）。
                        _write_issue_impl(
                            {
                                "action_type": "CREATE", "topic": topic, "severity": "minor",
                                "description": raw_content or rationale,
                                "phase_id": phase_id, "task_id": task_id,
                                "defer_to_task_id": defer_to_task_id,
                            },
                            _conn, _run_id, "decision_extractor_auto", phase_id, task_id,
                        )
                        print(f"  🗂️ [BL-154] '{topic}' をissue_logにも自動記録しました（defer_to_task_id={defer_to_task_id}）。")
                    else:
                        print(f"  ⚠️ [Deferred] 申し送り先task_id '{defer_to_task_id}' が解決できず、計画文書への追記をスキップしました。")

            print(f"\n  📝 [Extract] {agreement['action_type']} - {agreement['entry_type']}: {agreement['topic']}")
            print(f"     ├ Status: {agreement['status']} | By: {agreement['proposed_by']}")
            print(f"     ├ Meta  : Phase={agreement['phase_id']}")
            print(f"     ├ Reason: {agreement['reason_why']}")
        else:
            print(f"  ⏭️ [decision_extractor] write_agreementが呼ばれたため、ExtractからAgreement書き込みをスキップしました（topic: {topic}）")

    # [BL-139] transition.advances_to_task_idはcall_decision_extractorの単一LLM呼び出しの
    # 大きなJSON出力内の一項目に過ぎず、実運用でUserが「次タスクtask_2_1への着手指示」を
    # 明示していても、抽出漏れでnullのまま返るケースが確認された（実インシデント: 該当ターンで
    # entry_type="Directive"のCREATEイベント自体はtask_2_1向けに正しく抽出されているのに、
    # トップレベルのadvances_to_task_idだけがnullで、current_task_idが永久に更新されなかった）。
    # 抽出済みイベントの中に現在タスクと異なる有効なtask_idを持つDirectiveがあれば、それを
    # 遷移意図の代替シグナルとして採用する（BL-096の自動起票と同型の安全網）。
    # status="Deferred"（BL-082の明示的先送り）は「今は移行しない」という意思表示のため除外する。
    if target_role == "user" and not transition.get("advances_to_task_id"):
        departing_task_id = state.get("current_task_id", "")
        # [BL-211] BL-139の補完はDirectiveの構造化フィールドtask_idが埋まっていることを前提と
        # していたが、`log/2026-08-11/0941`のtask_4_2→task_4_3で、advances_to_task_idがnull
        # かつDirective側もphase_id/task_idともに空文字で返され（移行先はtopicと
        # owned_variable_values.対象タスクの自然文にしか存在しなかった）、安全網が二重に外れて
        # 切替が永久に成立しなくなる事故が起きた。そこで、構造化フィールドによる補完（第1段）を
        # 優先しつつ、それが空振りした場合のみ自然文からの推定（第2段）へフォールバックする。
        # 第2段は候補が一意に定まるときだけ採用するフェイルクローズとし、複数タスクへ言及する
        # 差し戻し文で誤った先読み切替が起きないようにする。
        _fallback_candidates: set[str] = set()
        for item in extracted_items:
            if item.get("entry_type") != "Directive" or item.get("status") == "Deferred":
                continue
            candidate_task_id = item.get("task_id")
            if (
                candidate_task_id
                and candidate_task_id in task_id_to_phase_id
                and candidate_task_id != departing_task_id
            ):
                transition["advances_to_task_id"] = candidate_task_id
                transition["advances_to_phase_id"] = task_id_to_phase_id[candidate_task_id]
                print(
                    f"  🔁 [BL-139] transitionのadvances_to_task_idが未設定だったため、"
                    f"抽出されたDirective（task_id='{candidate_task_id}'）から遷移意図を補完しました。"
                )
                break
            if not candidate_task_id:
                _fallback_candidates |= {
                    t for t in _infer_directive_target_task_ids(item, task_id_to_phase_id)
                    if t != departing_task_id
                }
        else:
            if len(_fallback_candidates) == 1:
                inferred_task_id = _fallback_candidates.pop()
                transition["advances_to_task_id"] = inferred_task_id
                transition["advances_to_phase_id"] = task_id_to_phase_id[inferred_task_id]
                print(
                    f"  🔁 [BL-211] Directiveのtask_idが空だったため、自然文から移行先"
                    f"（task_id='{inferred_task_id}'）を推定して遷移意図を補完しました。"
                )
            elif len(_fallback_candidates) > 1:
                print(
                    f"  ⚠️ [BL-211] Directiveのtask_idが空で、自然文から複数の移行先候補"
                    f"（{sorted(_fallback_candidates)}）が見つかったため、誤った先読み切替を避けて"
                    f"補完を見送りました。"
                )

    _resolve_task_transition(state, transition, structured_redirect=_pending_redirect)
    _maybe_resume_forward_focus(state, _conn, _run_id)
    _maybe_clear_resolved_companion(state, _conn, _run_id)

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

    # [BL-096/BL-144] 当初はissue_logにstatus='escalated'の行が1件でもあれば、モデルの判定に
    # 関わらずdiscussion_statusを機械的に"stagnant"へ上書きしていた（BL-099対策：モデル遵守に
    # 依存しない）。しかし実ドライラン（log/2026-08-02/0832）で、reflection自身が"continuing"
    # （健全な進捗中）と判定した回まで無条件でstagnant上書きされ、facilitation_countの貴重な
    # 猶予（既定3回）を消費してしまう実害が確認された。BL-136導入後もwrite_issueのRESOLVE/DEFER
    # がほぼ呼ばれない現状では、escalated行の「存在」だけを見ると常に発火してしまうため、
    # 「同じescalated issueがユーザーノードを3回通過しても未解決のまま」という滞留を条件に
    # 絞る（ユーザーには毎ターンBL-136の強制解決プロンプトが表示されるため、3回は実質的な
    # 解決機会を与えたことになる）。
    # [BL-194] _escalated_now（生の全件）はこの直後の escalation_active 判定でのみ使う
    # （B-2：意図的に据え置き。DEFER/ACK済みでもエスカレーションが「存在する」事実自体は
    # 変わらないため、actionableへ絞ると「解決しました」という虚偽の復帰通知が飛ぶ）。
    # 停滞トリガーの母集合は _actionable_escalated（triage済みを除いた集合）を使う——
    # log/2026-08-08/1514で、全20件がDEFER済みだったにもかかわらずここが無フィルタだった
    # ため機械的にstagnantへ上書きされhaltした事故の一次修正（BL-194）。
    _escalated_now = _get_escalated_issues(get_active_conn(), state["run_id"])
    _actionable_escalated = _get_actionable_escalated_issues(
        get_active_conn(), state["run_id"], state.get("current_task_id", ""),
        round_count=state.get("round_count", 0),
    )
    _escalated_first_seen = state.setdefault("escalated_issue_first_seen_round", {})
    _current_round = state.get("round_count", 0)
    _stale_escalated = []
    _current_escalated_ids = set()
    for _issue in _actionable_escalated:
        _iid = _issue["id"]
        _current_escalated_ids.add(_iid)
        _first_round = _escalated_first_seen.setdefault(_iid, _current_round)
        if _current_round - _first_round >= 3:
            _stale_escalated.append(_issue)
    # 解決・先送り済みで既にescalated一覧から消えたissueは滞留追跡からも削除する
    # （再度escalatedになった場合は新規の滞留として扱う）。
    for _iid in list(_escalated_first_seen.keys()):
        if _iid not in _current_escalated_ids:
            del _escalated_first_seen[_iid]
    if _stale_escalated:
        state["discussion_status"] = "stagnant"
        _stale_topics = [i["topic"] for i in _stale_escalated]
        print(
            f"  🔴 [BL-096/BL-144] issue_logのescalated行のうち{len(_stale_escalated)}件"
            f"（{_stale_topics}）がユーザーノードを3回通過しても未解決のため、"
            f"discussion_statusを機械的にstagnantへ上書きしました。"
        )
        # [BL-145/BL-194] _stale_escalatedは既に_actionable_escalated（受け皿なし・自己先送り・
        # 受け皿失効のいずれかに該当する行のみ）から絞り込まれているため、正当にDEFER済みの
        # issueはそもそもこの時点で混入しない。以前はここでBL-136/167と同じフィルタ式を
        # 独立に再実装しており（4箇所目の重複コピー）、上流の述語が変わっても下流が古いままに
        # なる同型事故のリスクがあった（BL-194設計書「補正③」参照：停滞と断罪する集合と
        # 是正のため計画へ渡す集合が同一ifブロック内で食い違っていた）。フィルタは上流の
        # _get_actionable_escalated_issuesへ一元化したため、ここでは単純に代入するのみ。
        _formalizable_stale = _stale_escalated
        if _formalizable_stale and not state.get("plan_revision_reason"):
            _reason_lines = [
                f"- topic={i['topic']}: {i['description']}（累積{i['occurrence_count']}回発生、"
                f"raised_by={i['raised_by']}、issue_id={i['id']}）"
                for i in _formalizable_stale
            ]
            state["plan_revision_reason"] = (
                "[BL-145] 以下のescalated issueは、ユーザーノードを3回通過しても未解決のまま"
                "滞留しており（Reflectorによる正当性監査済み）、Detector/Reflector側では"
                "対応しきれません。それぞれを新規task、または既存taskのdescription/"
                "acceptance_criteriaへの明示的な組み込みとして計画へ反映してください（新規"
                "タスクである必要はなく、同じタスク内で同時に検討すべき内容ならそちらへ統合して"
                "ください。各issue_idにつき最低1つのtask説明・acceptance_criteriaに対応する"
                "topic文字列を明記し、後から追跡可能にしてください）:\n"
                + "\n".join(_reason_lines)
            )
            state["plan_revision_issue_ids"] = [i["id"] for i in _formalizable_stale]
            print(
                f"  📌 [BL-145] {len(_formalizable_stale)}件の滞留issueをplan_revision_reason"
                f"として次回計画再構成に引き継ぎました（issue_ids={state['plan_revision_issue_ids']}）。"
            )
        elif _formalizable_stale:
            print(
                "  ⚠️ [BL-145] plan_revision_reasonが既に別要因でセット済みのため、"
                "今回のissue formalizationはスキップします（次回reflectionで再評価）。"
            )

    _was_escalation_active = state.get("escalation_active", False)
    state["escalation_active"] = bool(_escalated_now)
    if _was_escalation_active and not state["escalation_active"]:
        # [BL-096] エスカレーションが解消された瞬間。次のExpert/User AI呼び出しで
        # 一度だけ復帰通知を注入する。
        state["escalation_just_resolved_notice_pending"] = True

    # [BL-061] facilitatorがこのreflectionの判定理由を参照できるよう保存する。
    # 従来はdecisionsテーブルのwhy列にしか残らず、facilitator_nodeに渡っていなかった。
    state["last_reflection_note"] = result.get("note", "")
    stop_reason_label = "継続中"
    if (result["discussion_status"] == "stagnant") or (not result["still_aligned"]):
        state["drift_flag"] = True
        stop_reason_label = "ゴール・ドリフト（目標逸脱）を検出"
    elif result["discussion_status"] == "stagnant":
        stop_reason_label = "議論の停滞を検出"
    elif result["discussion_status"] == "completed":
        stop_reason_label = "目標達成（完了）申告を検出"

    # [R5 F-3.7] トークンコスト抑制のため、stagnant判定時のみ思考ログをスナップショット保存する。
    _reflection_thought = get_last_reasoning_text() if result["discussion_status"] == "stagnant" else None
    decision = make_decision(
        who="reflection",
        what=f"内省監査実行: aligned={result['still_aligned']}, status={result['discussion_status']}",
        why=f"【判定: {stop_reason_label}】 {result['note']}",
        internal_thought_process=_reflection_thought,
    )
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state

def facilitator_node(state: LineageState) -> LineageState:
    """【SLM要約】
    Manages the discussion flow by periodically consulting a facilitator to guide conversation towards goals, enforcing a maximum iteration limit to prevent infinite loops.
    [BL-126 Stage D] Essence Dialogue（本質対話）の開始・往復・収束/タイムアウトを管理する。
    収束判定はこの関数の先頭で行う（LLM呼び出し前）: 直前のUser AIのターンで
    write_agreement(entry_type="EssenceProposal", status="Approved")が検知されていれば、
    対話を収束させplan_revision_reasonをセットしTask Plannerへ引き継ぐ（Stage Cとの接続点）。
    """
    if state.get("essence_dialogue_active"):
        # [design.md §3.1「収束後の離脱条件」] Facilitator自身のwrite_agreementではなく、
        # generate_user_utterance_nodeが直前のUser AIのターンからstateへ橋渡しした
        # last_essence_proposalを見る（Userの承認はUser AI自身のquery_AI呼び出しで起きるため）。
        _pending = state.get("last_essence_proposal")
        if _pending and _pending.get("topic") == state.get("essence_dialogue_topic") and _pending.get("status") == "Approved":
            if state.get("plan_revision_reason"):
                # [BL-145] plan_revision_reasonが既に別要因（reflectionのissue formalization等）
                # で使用中。現状のグラフトポロジではreflection→facilitatorの経路に入る時点で
                # essence_dialogue_activeは必ずFalseのためこの分岐へは到達しないはずだが、
                # 将来のグラフ変更に対する防御として上書きを避け、本質対話の収束処理は
                # 次回のfacilitator呼び出しへ持ち越す（essence_dialogue_active等は変更しない）。
                print("\n------ [facilitator] plan_revision_reasonが使用中のため、本質対話の収束処理を次回に持ち越します ------\n")
                return state
            print("\n------ [facilitator] 本質対話が収束しました（Userが承認） ------\n")
            reason = _pending.get("reason_why") or f"Essence Dialogue収束（topic={_pending['topic']}）"
            state["plan_revision_reason"] = reason
            state["essence_dialogue_active"] = False
            state["essence_dialogue_round"] = 0
            state["essence_dialogue_topic"] = ""
            state["last_essence_proposal"] = None
            decision = make_decision("facilitator", "本質対話が収束（Userが承認）", reason)
            db_append_decision(decision, get_active_conn(), state["run_id"])
            return state
        if state.get("essence_dialogue_round", 0) >= state.get("essence_dialogue_max_rounds", 5):
            print("\n------ [facilitator] 本質対話が上限ラウンドに到達しました（未収束のため通常フローへ復帰） ------\n")
            state["essence_dialogue_active"] = False
            state["essence_dialogue_round"] = 0
            state["essence_dialogue_topic"] = ""
            decision = make_decision("facilitator", "本質対話が上限ラウンドに到達（未収束）", "通常フローへ復帰")
            db_append_decision(decision, get_active_conn(), state["run_id"])
            return state

    # [BL-126 Stage D/§3.2] Essence Dialogue中の往復はfacilitation_countを消費しない
    # （意図的な合意形成プロセスであり、議論の停滞・逸脱の兆候ではないため）。
    if not state.get("essence_dialogue_active"):
        state["facilitation_count"] += 1
        if state["facilitation_count"] > 5:
            print(f"🛑 [Facilitator] facilitation_countが上限(5回)を超えた（{state['facilitation_count']}回目）ため、state['halt']=Trueで強制停止します。")
            state["halt"] = True
            decision = make_decision("system", "強制停止", "ファシリテーションの上限回数(5回)を超えても議論が改善されませんでした。")
            db_append_decision(decision, get_active_conn(), state["run_id"])
            return state

    print(f"\n------ [facilitator] が思考中 ------")
    # [BL-096] reflectionと同じくPython側の直接DB問い合わせでescalated issueを取得し、
    # facilitatorのプロンプトに構造化データとして注入する（LLMツール呼び出しには依存しない）。
    # [BL-194] 生の_get_escalated_issuesではなくactionable集合を使う。triage済み（DEFER先が
    # 確定している）issueを「🚨最優先で解消させてください」という最強トーンのブロックへ
    # 流し込むのはBL-194不変条件の直接違反であり、log/2026-08-08/1514ではFacilitator自身が
    # 「need車両7〜8台」とtask_2_2の責務をtask_2_1の義務として誤って取り込む原因になっていた。
    _conn = get_active_conn()
    _escalated_for_facilitator = _get_actionable_escalated_issues(
        _conn, state["run_id"], state.get("current_task_id", ""),
        round_count=state.get("round_count", 0),
    )
    escalated_issues_text = "\n".join(
        f"- topic={i['topic']}: {i['description']}（累積{i['occurrence_count']}回発生、"
        f"raised_by={i['raised_by']}）"
        for i in _escalated_for_facilitator
    )
    feedback = call_facilitator(
        state["goal"], state["chat_history"], state.get("last_reflection_note", ""),
        goal_essence_text=_get_goal_essence_text(_conn, state["run_id"]),
        escalated_issues_text=escalated_issues_text,
        essence_dialogue_active=state.get("essence_dialogue_active", False),
        state=state,
    )
    print(f"\n------ 完了 ------")

    # [BL-126 Stage D] 今回のFacilitatorの応答でEssenceProposalが新規提起された場合、
    # 本質対話モードへ入る（既に対話中なら、topicを最新の提起へ更新した上でラウンドを進める）。
    _proposal = get_last_essence_proposal()
    if _proposal and _proposal.get("action_type") == "CREATE" and _proposal.get("status") == "Proposed":
        state["essence_dialogue_active"] = True
        state["essence_dialogue_round"] = state.get("essence_dialogue_round", 0) + 1
        state["essence_dialogue_topic"] = _proposal["topic"]
        print(f"  💬 [Facilitator] Essence Dialogueを開始/更新しました: topic={_proposal['topic']}（round={state['essence_dialogue_round']}）")
    elif state.get("essence_dialogue_active"):
        state["essence_dialogue_round"] = state.get("essence_dialogue_round", 0) + 1
        print(f"  💬 [Facilitator] Essence Dialogue継続中: round={state['essence_dialogue_round']}")

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
        # ===== ファイル/ホワイトボードから内容を読み込む =====
        content_data = d['decision_what']
        if content_data.startswith("FILE_PATH:"):
            filepath = content_data.split("FILE_PATH:")[1]
            if os.path.exists(filepath):
                with open(filepath, "r", encoding="utf-8") as f:
                    content_text = f.read()
            else:
                content_text = f"(⚠️ファイルが見つかりません: {filepath})"
        elif content_data.startswith("WHITEBOARD:"):
            # [R4] "WHITEBOARD:{phase_id}:{task_id}"（phase_idが空文字の場合もあるためmaxsplit=2で分割）
            _, wb_phase_id, wb_task_id = content_data.split(":", 2)
            wb = get_latest_whiteboard(_conn, _run_id, wb_phase_id, wb_task_id)
            content_text = wb["content"] if wb else f"(⚠️ホワイトボードが見つかりません: phase={wb_phase_id}, task={wb_task_id})"
        else:
            content_text = content_data
        # ==========================================

        master_document.append(f"## {d['topic']}\n")
        master_document.append(f"{content_text}\n")
        
        # Lineage (意思決定の由来) データの挿入
        master_document.append("\n### 💡 意思決定の由来 (Decision Lineage)\n")
        master_document.append(f"- **合意ID**: `{d['id']}`")
        master_document.append(f"- **検討の背景と根拠**: {d.get('reason_why', '記載なし')}")
        if d.get("resource_claims"):
            master_document.append(f"- **関連リソース・制約**: {json.dumps(d['resource_claims'], ensure_ascii=False)}")
        master_document.append("\n---\n")
    
    final_text = "\n".join(master_document)
    
    # 統合したテキストをLLMに渡し、矛盾がないか最終チェックさせる
    result = call_integrator(
        state["goal"], final_text,
        goal_essence_text=_get_goal_essence_text(get_active_conn(), state["run_id"]),
        state=state,
    )
    
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
            "id": f"AG-MASTER-{int(time.time() * 1000)}", "timestamp": time.time(),
            "action_type": "CREATE",
            "entry_type": "Deliverable",
            "status": "Proposed", # Reviewerの審査待ち
            "topic": "★最終統合要件定義書（Lineage完全版）",
            "decision_what": f"FILE_PATH:{master_filepath}", # パスを保存
            "reason_why": "全タスクの承認済み成果物を自動結合",
            "proposed_by": "System Integrator",
            "phase_id": "All",
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
    result = call_reviewer(
        state["goal"], master_doc,
        goal_essence_text=_get_goal_essence_text(get_active_conn(), state["run_id"]),
        state=state,
    )
    print(f"\n------ 完了 ------")
    if arithmetic_warnings:
        result["passed"] = False
        result["feedback"] = (result.get("feedback", "") + 
            "\n【機械検算による警告】\n" + "\n".join(arithmetic_warnings))
    
    if result["passed"]:
        state["is_completed"] = True
        print("✅ [Reviewer] QA審査を通過しました。state['is_completed']=Trueにします。")
        decision = make_decision("reviewer", "最終成果物の承認 (Passed)", result.get("reasoning", "QA審査を通過しました。"))
        db_append_decision(decision, _conn, _run_id)
    else:
        if state["review_count"] > 3:
            print(f"🛑 [Reviewer] QA差し戻し上限(3回)を超えた（review_count={state['review_count']}）ため、state['halt']=Trueで強制停止します。")
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
    print(f"\n🛑🛑🛑 [Halt] システムを完全停止します（turn_count={state.get('turn_count', '?')}）。詳細は直前の停止理由を参照してください。")
    decision = make_decision(who="system", what="処理を完全停止", why="条件を満たしたためシステムをHaltします。")
    db_append_decision(decision, get_active_conn(), state["run_id"])
    return state


# ---------------------------------------------------------------------------
# 5. 分岐ロジック & グラフ構築
# ---------------------------------------------------------------------------

def build_graph(checkpointer: BaseCheckpointSaver | None = None):
    """【SLM要約】
    Construction of the core state machine graph, defining all processing nodes (e.g., planners, detectors, experts) and their execution flow within the system.
    [BL-105] checkpointerを渡すとLangGraph公式のノード境界チェックポイント（SqliteSaver等）が
    有効になる。省略時（None）は従来通りチェックポイント無しでコンパイルされ、既存のトポロジー
    確認専用テスト（build_graph()を引数無しで呼ぶもの）はそのまま動作する。
    """
    graph = StateGraph(LineageState)
# 1. ノードの登録（★関数は同じものを使い回し、名前で役割を分ける）
    graph.add_node("goal_essence", goal_essence_node)
    graph.add_node("task_planner", task_planner_node)
    graph.add_node("task_plan_reviewer", task_plan_reviewer_node)
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
    graph.set_entry_point("goal_essence")
    graph.add_edge("goal_essence", "task_planner")
    graph.add_edge("task_planner", "task_plan_reviewer")

    # [BL-087 Stage2] task_plan_reviewerがmajor判定でphasesをクリアした場合はtask_plannerへ
    # 差し戻し、そうでなければ（承認 or 差し戻し上限到達）通常のフローへ進む。
    def route_after_task_plan_reviewer(state: LineageState):
        """【SLM要約】
        Routes back to task_planner for regeneration when the plan reviewer clears phases
        (major issue, retry budget remaining), otherwise proceeds to generate_user_utterance.
        """
        if not state.get("phases"):
            print("\n[route_after_task_plan_reviewer]------ major判定によりphasesがクリアされたため、task_plannerへ差し戻します ------\n")
            return "task_planner"
        return "generate_user_utterance"

    graph.add_conditional_edges(
        "task_plan_reviewer",
        route_after_task_plan_reviewer,
        {"task_planner": "task_planner", "generate_user_utterance": "generate_user_utterance"},
    )
    # [BL-126 Stage D/§3.1] essence_dialogue_active中は、User AIの発言がDetectorの通常監査を
    # スキップして直接facilitatorへ戻る（対話モードの往復）。既存の通常フロー（user_detector経由）
    # には一切影響しない、単一フラグの読み取りによる分岐（§13.1と同じ設計原則）。
    def route_after_generate_user_utterance(state: LineageState):
        """【SLM要約】
        Routes to facilitator while an Essence Dialogue is active (skipping the normal
        detector audit), otherwise proceeds to the normal user_detector path.
        """
        if state.get("essence_dialogue_active"):
            print("\n[route_after_generate_user_utterance]------ BL-126: 本質対話継続中のためfacilitatorへ戻ります ------\n")
            return "facilitator"
        return "user_detector"

    graph.add_conditional_edges(
        "generate_user_utterance", route_after_generate_user_utterance,
        {"user_detector": "user_detector", "facilitator": "facilitator"},
    )

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

        # [BL-181] 第2段（機械的な最終防衛線）: BL-125が今回のターンでタスク遷移をブロックした
        # （current_task_idは更新されていない）にもかかわらず、Orchestrator/Expertが会話文脈
        # （Userが既に発言した次タスクの指示）だけを頼りに先走ってしまう事故が実際に発生した
        # （`log/2026-08-05/1833`、task_4_1の未解決major issueを残したままtask_4_2の成果物が
        # 生成され、write_agreementのtask_id不一致ゲートに阻まれてtask_idを誤登録する回避策を
        # Expertが取ってしまった）。第1段（user_detectorのドメイン監査）で捕捉できなかった場合の
        # 保険として、ここでPython側のみで機械的に差し戻す（LLMを再度介在させない）。
        # [BL-183] _resolve_task_transitionのブロック要因はtask_transition_blocked_unapproved_task_id
        # （BL-176: 離脱先未承認）とtask_transition_blocked_issue_topics（BL-125本来: 未解決severe
        # issue）の2種類が排他的に立ちうる。当初はBL-176側のみをチェックしており、BL-125本来の
        # ブロック（`log/2026-08-06/0009`→`0751`で実際に再発、task_6_1の成果物がtask_id='task_5_2'
        # として誤登録された）を素通りさせてしまっていたため、両方をチェックする。
        if state.get("task_transition_blocked_unapproved_task_id") or state.get("task_transition_blocked_issue_topics"):
            print("\n[route_after_user_decision]------ !!! BL-125によりタスク遷移がブロックされたため、Orchestratorへは進めずUser AIへ差し戻します !!! ------\n")
            return "generate_user_utterance"

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
            "orchestrator": "orchestrator",
            "generate_user_utterance": "generate_user_utterance",
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
        # [BL-130] Expert相談ターン（成果物ではなく質問）は、監査が軽量パス済みで抽出対象の
        # 成果物も存在しないため、expert_decision_extractorを経由せず直接User AIへ渡す。
        if state.get("expert_consultation_mode"):
            print("\n[route_after_expert_detector]------ BL-130: Expert相談ターンのためgenerate_user_utteranceへ直行します ------\n")
            return "generate_user_utterance"
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
        {
            "expert": "expert", "expert_decision_extractor": "expert_decision_extractor",
            "reflection": "reflection", "generate_user_utterance": "generate_user_utterance",
        }
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
        # [BL-005対応] turn_countはグラフ内部ループ（route_after_expert_decisionが
        # generate_user_utteranceへ戻り続ける限り）で凍結し得るため、代わりに
        # generate_user_utterance_nodeで加算されるround_countを使う。
        round_count = state.get("round_count", 0)
        if round_count > 0 and round_count % state["reflection_interval"] == 0:
            print(f"\n[route_after_expert_decision]------ リフレクションのタイミングになりました（round={round_count}） ------\n")
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
    return graph.compile(checkpointer=checkpointer)

# ---------------------------------------------------------------------------
# 6. AI vs AI 実行用ループ
# ---------------------------------------------------------------------------

def run_ai_vs_ai_loop(target_goal: str, config: Appconfig, db_path: str = "cela.db", resume_run_id: str | None = None,
                       checkpoint_id: str | None = None):
    """【SLM要約】
    Orchestration of an iterative, goal-driven dialogue loop where multiple AIs collaborate to refine a solution based on predefined constraints and state management.
    SQLite接続（run単位のシングルトン）を初期化し、ループ終了時に必ずクローズする（R1、設計書§3.6.1準拠）。
    [BL-105/D-086 Tier1] resume_run_idに過去のrun_id（==LangGraphのthread_id）を渡すと、
    CELA_CHECKPOINT_DB_PATHへSqliteSaverが自動永続化した状態から再開する（新規run_idは発行しない）。
    entry_pointからの全体再走行ではなく、中断した直後のノードから再開する（app.stream(None, ...)）。
    [BL-174] checkpoint_idを併せて渡すと、そのthreadの「最新」ではなく、指定した過去の
    checkpoint（`--list-checkpoints`で一覧表示できる、ノード完了ごとに自動保存されている
    LangGraph公式のスナップショットの1つ）から再開する（LangGraph公式のtime travel/replay。
    それ以降のノードだけが実行し直され、それより前のノードは再実行されない）。これは新しい
    分岐（LangGraphの言葉で言えばそのcheckpointを親とする新規checkpoint列）を作ることに
    相当し、元の「その後の履歴」は上書きされず、checkpoint_id指定で個別に参照可能なまま
    checkpointer DBに残り続ける（gitのbranchに近い挙動）。
    """
    global _DB_CONN
    if checkpoint_id and not resume_run_id:
        print("🚨 --checkpoint-idは--resume（run_id）と併用してください。")
        return

    checkpointer_conn = sqlite3.connect(CELA_CHECKPOINT_DB_PATH, check_same_thread=False)
    checkpointer = SqliteSaver(checkpointer_conn)
    checkpointer.setup()  # 冪等（CREATE TABLE IF NOT EXISTS相当）
    app = build_graph(checkpointer=checkpointer)

    reset_call_seq()
    if REPLAY_MODE == "replay":
        _replay_fixtures.update(_load_replay_fixtures(_REPLAY_FIXTURE_PATH))
    elif REPLAY_MODE == "record" and _REPLAY_FIXTURE_PATH and os.path.exists(_REPLAY_FIXTURE_PATH):
        # 強制終了後の再起動はrun全体を最初から再実行するため、前回分をマージせず退避してから新規に記録する
        backup_path = f"{_REPLAY_FIXTURE_PATH}.bak-{int(time.time())}"
        os.replace(_REPLAY_FIXTURE_PATH, backup_path)
        print(f"⚠️ [RECORD] 既存のfixtureファイルを {backup_path} に退避しました（前回記録の上書き消失を防止）。")

    _DB_CONN = None
    try:
        # [BL-105] LangGraphランタイム設定は`config`（Appconfig、関数引数）と名前が衝突するため
        # 必ず`runtime_config`という別名を使う。
        # [BL-203] 新規run・resumeを問わず、実行時設定（呼び出し回数上限・参照ディレクトリ）は
        # 常に現在のAppConfigから供給する。チェックポイントに保存された古い値は使わない。
        set_runtime_tool_limits(config)

        pending_resume_drain = False
        if resume_run_id:
            run_id = resume_run_id
            runtime_config = {"configurable": {"thread_id": run_id}}
            if checkpoint_id:
                runtime_config["configurable"]["checkpoint_id"] = checkpoint_id
            snapshot = app.get_state(runtime_config)
            if not snapshot.values:
                target_desc = f"checkpoint_id={checkpoint_id}" if checkpoint_id else "最新のチェックポイント"
                print(f"🚨 [Resume] run_id={run_id}（{target_desc}）が見つかりませんでした（{CELA_CHECKPOINT_DB_PATH}）。--list-checkpoints {run_id} で一覧を確認してください。")
                return
            state = snapshot.values
            # [BL-201] チェックポイントから復元したstateは、resume時点のconfig引数を一切
            # 反映しない（run開始時にconfigからコピーした値がそのまま固定される）。呼び出し
            # 回数の上限・参照ディレクトリのような「会話の履歴ではなく実行時設定」の値は、
            # resumeのたびに現在のconfigから再同期しないと、コード側でmax_web_search_calls等を
            # 変更してもresume済みのrunには一切反映されない（log/2026-08-09/2313で実機確認：
            # BL-199で30→50へ緩和した後もresumeしたrunがweb_searchの呼び出し上限（30回/run）に
            # 達しましたを返し続けていた）。会話状態（chat_history/whiteboard等）は上書きせず、
            # この4フィールドのみ現在のconfigの値へ差し替える。カウンタ自体（web_search_call_count
            # 等）はそのrunで実際に消費済みの実績のためリセットしない。
            # [BL-203] BL-201の当初実装はここでローカルの`state`を書き換えるだけだったが、
            # それでは**ラウンド途中で中断したrunには一切効かない**ことが
            # log/2026-08-10/0901で判明した（web_searchが50ではなく30、calc_road_routeが
            # 30ではなく20のまま動いていた）。原因は、snapshot.nextが非空の場合に
            # `app.stream(None, ...)`を呼ぶ経路（pending_resume_drain、Ctrl+C中断の大半）
            # では、このローカル`state`がLangGraphへ一切渡らず、グラフはチェックポイントに
            # 保存された古い値で再開するため。
            # [REJECTED] app.update_state()でチェックポイントへ書き戻す案は、中断中の
            # pending tasksを乱してresume自体を壊すリスクがあるため採らない。実行時設定を
            # 実際に読むのはツールハンドラの`config`引数だけ（_apply_runtime_tool_limits参照）
            # なので、そこへ注入する方が影響範囲が閉じている。
            state.update(_resume_config_overrides_from(config))
            db_path = state["db_path"]
            current_turn = state.get("turn_count", 1)
            if checkpoint_id:
                print(f"♻️ [Resume] run_id={run_id} をcheckpoint_id={checkpoint_id}から再開します（turn={current_turn}）。")
            else:
                print(f"♻️ [Resume] run_id={run_id} から再開します（turn={current_turn}）。")
            # [BL-121] チェックポイントが「既にhalt済み」の状態を保存していた場合
            # （haltを引き起こした要因の直後に保存された等）、これまでは外側whileループの
            # while条件（current_turn<=max_turns）しかチェックしておらず、halt済みの状態を
            # そのままapp.stream()へ再投入して処理を継続してしまう経路が存在した。
            # 再開直後にhaltを明示チェックし、既にhalt済みならここで停止する。
            if state.get("halt"):
                print(f"\n🚨 [Resume/HALT] 再開したチェックポイントは既にhalt済みでした。 (ステータス: {state.get('discussion_status')})")
                print("============================================================")
                print("🏁 評価ループが終了しました。（再開時点で既にhalt済み）")
                print("============================================================")
                return
            # [BL-105] snapshot.nextが非空＝ラウンド途中（Ctrl+Cの大半のケース）で止まっている。
            # まずNone入力でそのラウンドの続きをEND（またはhalt）まで走らせる必要がある。
            # snapshot.nextが空＝ちょうどラウンド境界（END直後）で止まっていた稀なケースは、
            # 通常の「新規ターン」としてフルstateを投入すればよい。
            pending_resume_drain = bool(snapshot.next)
        else:
            run_id = f"{int(time.time())}-{uuid.uuid4().hex[:8]}"
            runtime_config = {"configurable": {"thread_id": run_id}}
            current_turn = 1
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
                "round_count": 0,
                "max_turns":  config["initial_max_turnval"],
                "reflection_interval": config["reflection_interval"],
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
                "detector_observations_log": [],
                "escalation_active": False,
                "escalation_just_resolved_notice_pending": False,
                "task_transition_blocked_issue_topics": [],
                "task_transition_blocked_unapproved_task_id": "",
                "escalated_issue_first_seen_round": {},
                "web_search_call_count": 0,
                "web_fetch_call_count": 0,
                "max_web_search_calls": config.get("max_web_search_calls", 30),
                "max_web_fetch_calls": config.get("max_web_fetch_calls", 30),
                "road_route_call_count": 0,
                "max_road_route_calls": config.get("max_road_route_calls", 30),
                "goal_reference_dir": config.get("goal_reference_dir", ""),
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
                "expert_last_reasoning": "",
                "user_last_reasoning": "",
                "risk_register": [],
                "needs_revision_phases": [],
                "phases_to_revise": [],
                "last_reflection_note": "",
                "plan_review_done": False,
                "plan_reviewer_retry_count": 0,
                "plan_reviewer_feedback": "",
                "goal_essence_done": False,
                "pending_task_ids": [],
                "expert_consultation_mode": False,
                "expert_pending_question": "",
                "expert_blocking_reason": "",
                "goal_revision_pending_review": False,
                "plan_revision_reason": "",
                "plan_revision_issue_ids": [],
                "plan_revision_count": 0,
                "phases_superseded": [],
                "task_reassigned_after_replan_notice": "",
                "task_focus_stack": [],
                "task_focus_companion": None,
                "pending_task_redirect": None,
                "task_focus_redirect_count": 0,
                "task_focus_redirect_notice": "",
                "task_focus_resume_notice": "",
                "essence_dialogue_active": False,
                "essence_dialogue_round": 0,
                "essence_dialogue_max_rounds": 5,
                "essence_dialogue_topic": "",
                "last_essence_proposal": None,
            }

        global _CURRENT_RUN_ID
        _CURRENT_RUN_ID = run_id
        _DB_CONN = get_db_connection(db_path)
        init_db(_DB_CONN)

        mode_str = "【ステートレス（決定事項DBによる知識永続化）】" if config["is_stateless_mode"] else "【ステートフル（生ログ全蓄積）】"

        # [BL-105] 最初のapp.stream()呼び出しのみ、再開でラウンド途中から続ける場合はNone
        # （中断した直後のノードから再開）、それ以外（新規runの初回、または境界で止まっていた
        # 再開）はフルstateを投入する。2回目以降のイテレーションは常にフルstateを投入する
        # （既存の「完了済みstateをそのまま次ターンへ再投入する」パターンと同一）。
        next_input = None if pending_resume_drain else state

        print("============================================================")
        print(f"🚀 Lineage Orchestrator: シナリオ検証  - DB+QAレビュー＆介入強化版")
        print(f"⚙️ 実行モード: {mode_str}")
        print(f"🆔 run_id: {run_id}")
        print(f"🎯 共通目標:\n{target_goal}")
        print(f"⏳ 初期設定ターン数: {config["initial_max_turnval"]} ターン制限")
        print(f"⏸️  Ctrl+Cでいつでも一時停止できます（再開: python cela_main.py --resume {run_id}）")
        print("============================================================")

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
            # [BL-105] LangGraph公式のcheckpointer（SqliteSaver）がノード完了ごとに自動で状態を
            # 永続化するため、手動でのcheckpoint保存は不要。Ctrl+C時は、これまでに完了済みの
            # ノードまではcheckpointerに既に保存されているため、追加の保存操作なしで安全に
            # 一時停止できる。
            try:
                for step_state in app.stream(next_input, config=runtime_config, stream_mode="values"):
                    state = step_state
            except KeyboardInterrupt:
                print("\n\n⏸️ [PAUSE] Ctrl+Cを検知し、ドライランを一時停止しました。")
                print(f"    直前の状態はLangGraph checkpointer（run_id={run_id}）に自動保存済みです。")
                print(f"    再開するには: python cela_main.py --resume {run_id}")
                return
            except DailyQuotaExhaustedError as e:
                # [BL-171] KeyboardInterruptと同じ一時停止経路。checkpointerは完了済みノードまで
                # 既に保存済みのため、追加の保存操作なしで安全に一時停止できる。
                print("\n\n⏸️ [PAUSE] OpenRouter無料枠の日次上限に達したため、ドライランを一時停止しました。")
                print(f"    詳細: {e}")
                print(f"    直前の状態はLangGraph checkpointer（run_id={run_id}）に自動保存済みです。")
                print("    無料枠は日次リセット（X-RateLimit-Reset）まで回復しません。クレジット購入で即時解消することもできます。")
                print(f"    再開するには: python cela_main.py --resume {run_id}")
                return

            # [BL-105] 以降は常にフルstateを入力として渡す（既存の多ターンパターンと同型。
            # 完了済みthreadへフルstateを再投入すると__start__からの新規runとして扱われる）。
            next_input = state

            # [BL-174] checkpoint_id指定での再開は最初のapp.stream()呼び出しのみに適用する。
            # 固定したconfigurable.checkpoint_idを次イテレーション以降も使い続けると、毎ターン
            # 同じ過去の分岐点から再度フォークしてしまい前進しない。最初の1回でLangGraphが
            # その分岐点を親とする新しいcheckpoint列を書き込んだ後は、thread_idのみのconfigへ
            # 切り替え、以降は（既存の多ターンパターンと同じく）その新しい分岐の最新checkpointを
            # 自然にたどらせる。
            if "checkpoint_id" in runtime_config["configurable"]:
                runtime_config = {"configurable": {"thread_id": run_id}}

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
                    # [Tier 10] 従来ここがトリプルクォート文字列リテラルのままprint()に渡されておらず、
                    # orchestrator/decision_extractor以外（expert/detector/user/task_planner/arbiter/
                    # reflection等）の決定がこのターン一切コンソールへ出力されていなかった（死にコード）。
                    print(f"  [{d['who']}] {d['what']} ({d['why']})")
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
        else:
            # [Tier 9] whileの条件不成立（current_turn > max_turns）で自然終了した場合、
            # is_completed/haltいずれのbreakも通っていない＝ターン予算を使い切った終了である。
            if not state.get("is_completed") and not state.get("halt"):
                print(f"\n⏰ [TURN BUDGET EXHAUSTED] max_turns={state['max_turns']}に達しましたが、完了(is_completed)も停止(halt)も成立しないまま終了しました。")

        print("\n============================================================")
        print(f"🏁 評価ループが終了しました。 {mode_str})")
        print("============================================================")
    finally:
        if _DB_CONN is not None:
            _DB_CONN.close()
            _DB_CONN = None
        checkpointer_conn.close()


def list_checkpoints(run_id: str) -> None:
    """[BL-174] `--list-checkpoints RUN_ID`向け。LangGraph公式のcheckpointerが各ノード完了
    （superstep）ごとに自動保存しているスナップショット履歴を、`app.get_state_history()`
    （新しい順で返る）で取得し、古い順（`git log --reverse`相当、実行の時系列通りに上から
    下へ読める順）に並べ替えてgitのlogに近い一覧として表示する。ai_vs_ai_loop本体は
    一切実行しない、純粋な閲覧用ユーティリティ。
    """
    checkpointer_conn = sqlite3.connect(CELA_CHECKPOINT_DB_PATH, check_same_thread=False)
    try:
        checkpointer = SqliteSaver(checkpointer_conn)
        checkpointer.setup()
        app = build_graph(checkpointer=checkpointer)
        # get_state_historyは新しい順で返るため、時系列通り（古い順）に読めるよう反転する。
        history = list(reversed(list(app.get_state_history({"configurable": {"thread_id": run_id}}))))
        if not history:
            print(f"🚨 run_id={run_id} のチェックポイントが見つかりませんでした（{CELA_CHECKPOINT_DB_PATH}）。")
            return
        print(f"📜 [Checkpoints] run_id={run_id} の履歴（古い順、全{len(history)}件）:")
        print("=" * 110)
        for snap in history:
            checkpoint_id = snap.config["configurable"]["checkpoint_id"]
            step = snap.metadata.get("step") if snap.metadata else None
            writes = (snap.metadata.get("writes") or {}) if snap.metadata else {}
            completed_nodes = ", ".join(writes.keys()) if writes else "(初期状態)"
            next_nodes = ", ".join(snap.next) if snap.next else "(完了/END)"
            turn_count = snap.values.get("turn_count") if snap.values else None
            current_task_id = (snap.values.get("current_task_id") or "(未着手)") if snap.values else "?"
            # [BL-175] LangGraphのcreated_atはUTCのISO文字列（例: "...+00:00"）で固定のため、
            # ログ側の時刻表示（JST）と同期させるためここでJSTへ変換する。checkpoint自体の
            # 保存形式（UTC）は変更しない、表示のみの変換。
            created_at_jst = datetime.datetime.fromisoformat(snap.created_at).astimezone(JST).strftime("%Y-%m-%d %H:%M:%S")
            print(
                f"  step={step!s:<4} {created_at_jst} JST | 完了: {completed_nodes:<24} | 次: {next_nodes:<24} "
                f"| turn={turn_count} task={current_task_id} | checkpoint_id={checkpoint_id}"
            )
        print("=" * 110)
        print(f"再開するには: python cela_main.py --resume {run_id} --checkpoint-id <checkpoint_id>（省略時は最新から再開）")
    finally:
        checkpointer_conn.close()


if __name__ == "__main__":
    # [BL-105] --resume <run_id> で一時停止したドライランを再開できる。
    import argparse
    _cli_parser = argparse.ArgumentParser(description="CELA Lineage Orchestrator")
    _cli_parser.add_argument(
        "--resume", metavar="RUN_ID", default=None,
        help="Ctrl+Cで一時停止した際に起動時バナーへ表示されたrun_idを指定して再開する。",
    )
    # [BL-174] ノード完了ごとに自動保存されているLangGraph公式のcheckpoint履歴を一覧表示・
    # 任意の過去checkpointから再開できるようにする（time travel/replay）。
    _cli_parser.add_argument(
        "--list-checkpoints", metavar="RUN_ID", default=None,
        help="指定run_idのcheckpoint履歴（ノードごとのスナップショット一覧）をgit log風に表示して終了する。",
    )
    _cli_parser.add_argument(
        "--checkpoint-id", metavar="CHECKPOINT_ID", default=None,
        help="--resumeと併用し、--list-checkpointsで確認したcheckpoint_idを指定して、"
             "threadの最新状態ではなくその時点から再開する（省略時は従来通り最新から再開）。",
    )
    _cli_args = _cli_parser.parse_args()

    if _cli_args.list_checkpoints:
        # [BL-174] 純粋な閲覧用コマンドのため、ai_vs_ai_loop本体もMultiLoggerによる
        # log/<日付>/<時刻>/ ディレクトリ作成も一切行わず、素のstdoutへ表示してすぐ終了する。
        list_checkpoints(_cli_args.list_checkpoints)
        sys.exit(0)

    # カスタムロガーを標準出力に設定（importのみでは発火させない。BL-027）
    sys.stdout = MultiLogger()

    TARGET_GOAL = (f"""
# 課題：長野県茅野市における自動運転バス導入計画の策定

以下の背景・地理データ・制約条件に基づき、長野県茅野市における「自動運転バス導入計画書」を作成してください。

---

## 1. 背景と地域データ（公的統計準拠）

### (1) 社会・交通背景
- 人口・世帯: 総人口 56,400人（令和2年国勢調査、2020年10月1日時点）。高齢化率30.7%（65歳以上 約17,300人）。
- 参考として、令和5年1月時点の推計人口は55,657人まで減少しており、人口減少と高齢化が同時に進行している。
- 私立から2018年に公立化した理工系大学（公立諏訪東京理科大学）の学生 約1,368人（学部・大学院合計、2025年5月時点）。
- 既存交通の状況: 令和4年（2022年）10月1日、市内の定時定路線バス13路線が利用者減少・採算悪化を理由に廃止された。
- 現在、市内に定時定路線での路線バス運行は存在しない。
- 移動弱者の急増: 近年、高齢ドライバーの運転免許返納件数が急増。通院や日常の買い物が困難な「移動難民」の増加が深刻な社会問題となっている。
- デジタルリテラシー: 65歳以上のスマートフォン所有率は約65%に達するが、アプリによる配車予約操作を問題なく行える高齢者は全体の15%程度にとどまり、7割以上の高齢者が電話予約等に頼らざるを得ない。

### (2) 地理・インフラ環境（中心駅からのアクセス）
- 総面積: 約266.41 km²
- 地形・標高:
  - 【市街地平坦部】：JR中央本線 茅野駅（標高789m）を中心とした諏訪盆地南部の半径 5km 圏内。平坦〜緩勾配（平均時速 40km/h 想定）。
  - 【山間登坂・高原部】：駅（中心部）から 5km を超えると急勾配に入り、10km〜20km 圏内に標高 1,000m〜1,500m 級の集落・別荘地が散在（代表例：蓼科高原、標高1,150〜1,800m、駅から自動車で約30〜35分。平均時速 25km/h 想定。冬季は積雪・路面凍結）。
- 主要拠点と中心駅（茅野駅）からのアクセス:
  1. 【交通結節点】JR中央本線 茅野駅（標高789m）
  2. 【行政】茅野市役所（標高801m、日本の市役所の中で最も標高が高い）：駅東口から徒歩約8分（約600m）
  3. 【基幹病院】組合立諏訪中央病院（高齢者の目的地首位）：駅から自動車で約10分（路線バスで約15分、徒歩約34分）
  4. 【文教】公立諏訪東京理科大学キャンパス（学生約1,368人、朝夕の通学集中）：市内に立地
  5. 【山間集落】東部山間集落群（駅より東〜北東へ 約10km〜14km / 標高1,000〜1,100m）
  6. 【高原別荘地・集落】蓼科高原（駅から自動車で約30〜35分 / 標高1,150〜1,800m）

---

## 2. 絶対制約条件（ハード制約）

1. 【財務制約】
   - 初期構築・車両導入費（CapEx）の公的補助総額は「上限 1億円以内」。
   - 年間の市からの赤字補填補助金（OpEx）は「年間 4,000万円以内」を絶対厳守（1円でも超える計画は議会で否決される）。
   - 利用者運賃は1乗車数百円程度の住民負担に配慮した設定とし、運賃収入を試算すること。
2. 【サービスレベル（SLA）】
   - ピーク帯（午前8:00〜11:00の通院・買い物、朝の通学）の需要を破綻なく捌くこと。
   - 予約から乗車までの最大待ち時間は、市街地（5km圏内）で20分以内、山間部（5km超）で30分以内とする。
   - 電話予約等の非アプリ予約受入体制および人件費を計上すること。
3. 【法規制・労働・気象】
   - 運行時間帯: 7:30〜19:30（12時間運行）。
   - 労働基準法（交代制勤務・法定休憩・時間外労働規制）および遠隔監視オペレーター・乗務員配置基準の厳格な順守。
   - 冬季（12月〜3月）の標高1,000m超エリアにおける積雪・凍結時の安全運行基準（運休条件等）の明記。

---

## 2.5 実例の参照について

本市には既存の代替交通サービスの実例が存在する可能性がある。web_searchでそうした実例を発見すること自体は制約されない。
ただし、実例の運行本数・車両台数・運賃・人員体制等の具体的な運用数値をそのまま本計画の数値として転記してはならない。
実例は「このような設計が現実的に成立し得るか」という妥当性の参考にのみ使用し、本計画の数値は必ず上記1・2で与えられた本課題固有の制約（予算・需要データ・距離・SLA）から独自に算出すること。

---

## 3. 指示

上記の背景および制約条件をすべて踏まえ、長野県茅野市における「自動運転バス導入計画書」を作成してください。"
    """)

    config : Appconfig = {
        "pattern":  4,
        "is_stateless_mode": True,
        "initial_max_turnval": 30,
        "reflection_interval": 3,
        "target_goal": TARGET_GOAL,
        "user_always_remember": True,
        "agent_has_guardrail" : True,
        "chat_history_window": 4,
        "expert_history_window": 6,
        # [BL-199] log/2026-08-09/2222で、read_goal_reference未導入だった当時のExpertが
        # docs/refs/chino_city/chino_city_data.mdに既にある施設住所・座標を知らずweb_searchで
        # 再検索し、30回/runの上限を使い果たしていたことが判明。read_goal_reference導入後も、
        # 参照データに無い項目（施設の郵便番号住所等）は正当にweb_searchが必要になるため、
        # 上限自体も30→50へ緩和する（ユーザー承認済み、AGENTS.md §7）。
        "max_web_search_calls": 100,
        "max_web_fetch_calls": 100,
        "max_road_route_calls": 100,
        "goal_reference_dir": "docs/refs/chino_city",
    }

    run_ai_vs_ai_loop(
        target_goal=TARGET_GOAL,
        config= config,
        resume_run_id=_cli_args.resume,
        checkpoint_id=_cli_args.checkpoint_id,
    )