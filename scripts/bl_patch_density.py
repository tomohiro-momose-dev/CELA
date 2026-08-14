"""BLパッチ密度の定点観測スクリプト（BL全史の洗い直し用、2026-08-13新設）。

`cela_main.py`のコメントに埋め込まれた`[BL-xxx]`参照を、それが書かれている関数単位で集計する。
1つの関数に何個の「異なるBL番号」がパッチを当ててきたかを数えることで、
**個々の修正は正しくても根本の構造が未解決のまま叩き続けられている場所**を機械的に特定する。

[CONSTRAINT] このスクリプトは使い捨てではなく定点観測用である。構造改善の前後で再実行し、
密度が実際に下がったかを測るために`scripts/`へ常設する（「直したつもり」を数字で検証する）。

判定の限界（正直に記録する）:
- 関数の帰属は`def`行からの単純な行範囲で決めており、ネストした関数やクラスメソッドは
  外側の関数へ寄せて数える。厳密なASTスコープ解析はしていない。
- BL番号がコメントに書かれていない修正は数えられない。よって本指標は「BL番号を書く運用が
  守られている範囲での下限値」であり、実際のパッチ回数はこれ以上である。
"""

from __future__ import annotations

import argparse
import ast
import collections
import pathlib
import re
import sys

if hasattr(sys.stdout, "reconfigure"):
    # Windowsコンソール（cp932）では出力中の日本語・絵文字でクラッシュするため（BL-222と同型）
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_BL_PATTERN = re.compile(r"BL-(\d{3})")


def _build_function_ranges(source: str) -> list[tuple[int, int, str]]:
    """各トップレベル関数の (開始行index, 終了行index, 関数名) を返す（0-based, 両端含む）。

    ネストした関数は独立させず外側の関数へ含める（トップレベルのdefのみを単位とする）ため、
    「この機構が何回叩かれたか」という粒度で数えられる。

    [CONSTRAINT] 行範囲はASTの`lineno`/`end_lineno`で厳密に取る。正規表現＋インデントの
    ヒューリスティックは、この実装で2度誤った——(1)「次のdefまで」方式では関数間の
    モジュールレベルコード（巨大なツールスキーマdict等）が直前の関数へ吸われ、
    `_run_python_repl`が976行・`list_entities_from_db`が311行を誤って抱えた。
    (2)「インデントが0に戻るまで」方式でも、本コードベースが多用する三重引用符の
    プロンプトテンプレート（本文が桁0から始まる）で関数が途中終了しうる。
    密度の数字自体が誤ると「どこを直すべきか」の判断を誤らせるため、推測の余地がない
    AST解析に統一する。
    """
    tree = ast.parse(source)
    ranges: list[tuple[int, int, str]] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            end = node.end_lineno if node.end_lineno is not None else node.lineno
            ranges.append((node.lineno - 1, end - 1, node.name))
        elif isinstance(node, ast.ClassDef):
            # クラス直下のメソッドも「叩かれた機構」の単位として個別に数える
            for sub in node.body:
                if isinstance(sub, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    end = sub.end_lineno if sub.end_lineno is not None else sub.lineno
                    ranges.append((sub.lineno - 1, end - 1, f"{node.name}.{sub.name}"))
    return ranges


def analyze(path: pathlib.Path) -> tuple[dict[str, set[str]], set[str], int]:
    source = path.read_text(encoding="utf-8")
    lines = source.splitlines()
    ranges = _build_function_ranges(source)
    per_function: dict[str, set[str]] = collections.defaultdict(set)
    all_bls: set[str] = set()

    # 関数の外（モジュールレベルの定数・スキーマ定義など）に書かれたBL参照も取りこぼさない
    covered = [False] * len(lines)
    for start, end, name in ranges:
        for i in range(start, end + 1):
            covered[i] = True
        for i in range(start, end + 1):
            for bl in _BL_PATTERN.findall(lines[i]):
                per_function[name].add(bl)
                all_bls.add(bl)
    for i, line in enumerate(lines):
        if not covered[i]:
            for bl in _BL_PATTERN.findall(line):
                per_function["(module level: 定数・スキーマ定義等)"].add(bl)
                all_bls.add(bl)
    return per_function, all_bls, len(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="BLパッチ密度の集計")
    parser.add_argument("--file", default="cela_main.py", help="解析対象のPythonファイル")
    parser.add_argument("--top", type=int, default=25, help="表示する上位件数")
    args = parser.parse_args()

    path = pathlib.Path(args.file)
    per_function, all_bls, total_lines = analyze(path)

    print(f"# BLパッチ密度: {path} （{total_lines}行、異なるBL番号 {len(all_bls)}個）\n")
    print(f"| 順位 | 関数 | 異なるBL数 | BL番号 |")
    print(f"|---|---|---|---|")
    ranked = sorted(per_function.items(), key=lambda kv: (-len(kv[1]), kv[0]))
    for rank, (name, bls) in enumerate(ranked[: args.top], start=1):
        bl_list = ", ".join(f"BL-{b}" for b in sorted(bls))
        print(f"| {rank} | `{name}` | **{len(bls)}** | {bl_list} |")

    print(f"\n合計: BL参照を持つ関数 {len(per_function)}個")
    hist = collections.Counter(len(bls) for bls in per_function.values())
    print("\n## 分布（1関数あたりの異なるBL数）\n")
    print("| 異なるBL数 | 該当関数数 |")
    print("|---|---|")
    for n in sorted(hist, reverse=True):
        print(f"| {n} | {hist[n]} |")


if __name__ == "__main__":
    main()
