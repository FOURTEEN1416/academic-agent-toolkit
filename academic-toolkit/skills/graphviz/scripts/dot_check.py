#!/usr/bin/env python3
"""dot_check — DOT 源静态检查 + Graphviz 渲染门禁（graphviz 技能自带，无第三方依赖）。

技能交付图件前的机检门禁：先把 DOT 源的常见错误拦在本机（不依赖 graphviz 也可跑
静态检查），再可选地真实渲染并核对结构化期望。设计对齐 diagram-design/scripts/self_check.py
的"技能自包含、随技能拷走即可用"惯例。

静态检查（--render 可选，默认仅静态）：
  - unterminated_string     引号不闭合（字符串吞掉后续语句）
  - unbalanced_braces       { } 不配对
  - unbalanced_brackets     [ ] 不配对
  - missing_graph_keyword   没有 digraph/graph 关键字
  - edge_operator_mismatch  有向图用 -- / 无向图用 ->（两类混用）
  - attr_then_edge          属性和边写在同一条语句（a[label="x"] -> b，graphviz 实测报错）
  - html_label_unquoted     HTML 标签裸写 label=<B>..</B>（新版 graphviz 实测报错；
                            应写 label="<...>" 或 label=<<...>>）
注记（不拦截）：cluster 命名疑似想画框但前缀不对。

渲染门禁（--render）：
  定位 dot（--dot > 环境变量 GRAPHVIZ_DOT > PATH > Program Files 标准安装位），
  渲染为 --format 指定格式；SVG 额外统计 class="node"/class="edge" 数量并与
  --expect JSON 核对（nodes/edges 精确匹配、must_contain/must_not_contain 文本）。

用法：
  python scripts/dot_check.py diagram.dot                     # 仅静态检查
  python scripts/dot_check.py diagram.dot --render            # 静态 + 渲染 SVG
  python scripts/dot_check.py diagram.dot --render --format pdf --out out.pdf
  python scripts/dot_check.py diagram.dot --render --expect expect.json
  python scripts/dot_check.py --lint-dir ../assets/templates  # 批量静态检查
  python scripts/dot_check.py --self-test                     # 内置用例 + 模板/示例自检

退出码：0=通过；1=检查未过；2=环境或用法错误（找不到 dot、文件缺失、expect 无效）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = SKILL_DIR / "assets" / "templates"
EXAMPLES_DIR = SKILL_DIR / "assets" / "examples"

NORMAL, STRING, HTML = 0, 1, 2


def _line_of(text: str, idx: int) -> int:
    return text.count("\n", 0, idx) + 1


def mask_source(text: str) -> tuple[str, list[dict], list[dict]]:
    """把字符串内部、注释、HTML 标签内部挖空，返回 (挖空文本, errors, notes)。

    挖空后引号字符本身保留（作为边界可见），其余内容替换为空格；
    下游正则检查因此不会命中字符串/注释/HTML 内部的 `->`、`[`、`]` 等字符。
    HTML-like 标签值（= <...>）整体挖空，并在扫描期判别"裸写 HTML"这一实测报错形态。
    """
    out: list[str] = []
    errors: list[dict] = []
    notes: list[dict] = []
    state = NORMAL
    block_depth = 0  # /* */ 嵌套深度
    i = 0
    n = len(text)
    at_line_start = True
    while i < n:
        ch = text[i]
        nxt = text[i + 1] if i + 1 < n else ""
        if state == NORMAL:
            if ch == "\n":
                at_line_start = True
                out.append(ch)
                i += 1
                continue
            if ch in " \t\r":
                out.append(ch)
                i += 1
                continue
            # 行首 # 注释（graphviz 口径：# 仅行首起注释作用）
            if at_line_start and ch == "#":
                while i < n and text[i] != "\n":
                    out.append(" " if text[i] != "\n" else "\n")
                    i += 1
                continue
            # 行注释与块注释
            if ch == "/" and nxt == "/":
                while i < n and text[i] != "\n":
                    out.append(" ")
                    i += 1
                continue
            if ch == "/" and nxt == "*":
                block_depth += 1
                out.append("  ")
                i += 2
                continue
            if block_depth > 0:
                if ch == "*" and nxt == "/":
                    block_depth -= 1
                    out.append("  ")
                    i += 2
                    continue
                out.append(" " if ch != "\n" else "\n")
                i += 1
                continue
            # 字符串
            if ch == '"':
                state = STRING
                out.append(ch)
                i += 1
                continue
            # HTML-like 标签值：紧跟 '='（允许空格）的 '<'
            if ch == "<":
                j = len(out) - 1
                while j >= 0 and out[j] in " \t\r\n":
                    j -= 1
                if j >= 0 and out[j] == "=":
                    # 判别裸写形态：< 后紧跟字母 = 实测语法错误（应引号或双尖括号包裹）
                    k = i + 1
                    while k < n and text[k] in " \t\r\n":
                        k += 1
                    if k < n and (text[k].isalpha() or text[k] == "/"):
                        errors.append({
                            "id": "html_label_unquoted",
                            "line": _line_of(text, i),
                            "message": "HTML 标签裸写 label=<标签>… 会被 graphviz 拒绝，"
                                       '应写成 label="<…>"（引号包裹）或 label=<<…>>（双尖括号）',
                        })
                    depth = 1
                    out.append(" ")
                    i += 1
                    while i < n and depth > 0:
                        c2 = text[i]
                        if c2 == "<":
                            depth += 1
                        elif c2 == ">":
                            depth -= 1
                        out.append(" " if c2 != "\n" else "\n")
                        i += 1
                    continue
                out.append(ch)
                i += 1
                continue
            at_line_start = False
            out.append(ch)
            i += 1
            continue
        if state == STRING:
            if ch == "\\":
                out.append("  ")
                i += 2
                continue
            if ch == '"':
                state = NORMAL
                out.append(ch)
                i += 1
                continue
            out.append(" " if ch != "\n" else "\n")
            i += 1
            continue
    if state == STRING:
        errors.append({
            "id": "unterminated_string",
            "line": _line_of(text, n - 1),
            "message": "引号不闭合：最后一个字符串到文件尾仍未找到配对的 \"",
        })
    return "".join(out), errors, notes


def _first_mismatch_line(masked: str, pattern: re.Pattern) -> int:
    m = pattern.search(masked)
    return _line_of(masked, m.start()) if m else -1


def lint_dot(text: str) -> tuple[list[dict], list[dict]]:
    """静态检查 DOT 源，返回 (errors, notes)。不依赖 graphviz 二进制。"""
    masked, errors, notes = mask_source(text)

    # 括号配对（在挖空文本上数，字符串/注释/HTML 内部的括号已不可见）
    for open_ch, close_ch, eid, label in (("{", "}", "unbalanced_braces", "花括号"),
                                          ("[", "]", "unbalanced_brackets", "方括号")):
        depth = 0
        bad_line = -1
        for idx, ch in enumerate(masked):
            if ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth < 0 and bad_line < 0:
                    bad_line = _line_of(masked, idx)
        if depth > 0 and bad_line < 0:
            bad_line = _line_of(masked, len(masked) - 1)
        if depth != 0:
            errors.append({
                "id": eid,
                "line": max(bad_line, 1),
                "message": f"{label}不配对（余额 {depth:+d}）：检查 {{}}/[] 是否成对、有无漏写或多写",
            })

    # 图类型：取 digraph/graph 中先出现者
    m_dig = re.search(r"\bdigraph\b", masked)
    m_und = re.search(r"\bgraph\b", masked)
    if not m_dig and not m_und:
        errors.append({
            "id": "missing_graph_keyword",
            "line": 1,
            "message": "未找到 digraph/graph 关键字：DOT 文件必须以 digraph 或 graph 开头",
        })
        return errors, notes
    directed = bool(m_dig and (not m_und or m_dig.start() < m_und.start()))

    # 边算子与图类型一致性（字符串/注释/HTML 内部的 -> -- 已挖空）
    op = "->" if directed else "--"
    other = "--" if directed else "->"
    m_bad = re.search(re.escape(other) + r"(?![->])", masked)
    if m_bad:
        errors.append({
            "id": "edge_operator_mismatch",
            "line": _line_of(masked, m_bad.start()),
            "message": f"{'有向图 digraph' if directed else '无向图 graph'} 里用了 '{other}'："
                       f"应使用 '{op}'（{'digraph 配 ->' if directed else 'graph 配 --'}，两者不可混用）",
        })

    # 属性和边写在同一条语句：a[label="x"] -> b（含 a -> b [x] -> c 链中挂属性，
    # 两者均被 graphviz 实测拒绝）；合法的边后挂属性是 a -> b [x]，] 后跟的是语句边界
    m_attr = re.search(r"\]\s*(?:->|--)", masked)
    if m_attr:
        errors.append({
            "id": "attr_then_edge",
            "line": _line_of(masked, m_attr.start()),
            "message": '属性和边写在同一条语句（如 a[label="x"] -> b）：'
                       "属性归属性语句（a [label=\"x\"];），边归边语句（a -> b;）",
        })

    # cluster 命名注记：名字含 cluster 但不以 cluster 开头 → 不画框
    for m in re.finditer(r"(?<![\w])subgraph\s+([A-Za-z_]\w*)", masked):
        name = m.group(1)
        if "cluster" in name.lower() and not name.lower().startswith("cluster"):
            notes.append({
                "id": "cluster_prefix_suspect",
                "line": _line_of(masked, m.start()),
                "message": f"subgraph {name}：名字含 cluster 但不以 cluster 开头，graphviz 不会画分组框",
            })
    return errors, notes


def find_dot(explicit: str | None = None) -> str | None:
    """定位 dot 可执行文件：显式参数 > GRAPHVIZ_DOT > PATH > Program Files 标准安装位。

    Windows 安装器默认不把 dot 加入 PATH（与 SKILL.md 提示一致），故补充标准安装位探测；
    一律经由环境变量与相对标准目录解析，不在脚本里写死机器相关盘符路径。
    """
    if explicit:
        return explicit if Path(explicit).is_file() else None
    env_override = os.environ.get("GRAPHVIZ_DOT")
    if env_override and Path(env_override).is_file():
        return env_override
    found = shutil.which("dot")
    if found:
        return found
    for var in ("ProgramFiles", "ProgramFiles(x86)", "ProgramW6432"):
        base = os.environ.get(var)
        if not base:
            continue
        cand = Path(base) / "Graphviz" / "bin" / ("dot.exe" if os.name == "nt" else "dot")
        if cand.is_file():
            return str(cand)
    return None


def _load_expect(path: Path | None, src: Path) -> tuple[dict | None, str | None]:
    if path is None:
        return None, None
    candidates = [path] if path.is_absolute() else [
        Path.cwd() / path,          # 相对当前工作目录
        src.parent / path,          # 相对 DOT 源所在目录
    ]
    p = next((c for c in candidates if c.is_file()), None)
    if p is None:
        return None, f"expect 文件不存在: {path}（尝试了 {', '.join(str(c) for c in candidates)}）"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        return None, f"expect 文件解析失败: {exc}"
    if not isinstance(data, dict):
        return None, "expect 文件顶层必须是 JSON 对象"
    return data, None


def render_check(dot_bin: str, src: Path, fmt: str, out: Path,
                 expect: dict | None) -> tuple[dict, list[dict]]:
    """真实渲染并核对结构化期望。返回 (render 结果, 附加 errors)。"""
    errors: list[dict] = []
    info: dict = {"ok": False, "format": fmt, "output": str(out), "dot": dot_bin}
    try:
        proc = subprocess.run(
            [dot_bin, f"-T{fmt}", str(src), "-o", str(out)],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180)
    except subprocess.TimeoutExpired:
        errors.append({"id": "render_failed", "line": 0,
                       "message": "渲染超时（>180s）：检查是否误用了大规模图布局引擎"})
        return info, errors
    except OSError as exc:
        errors.append({"id": "render_failed", "line": 0, "message": f"调用 dot 失败: {exc}"})
        return info, errors
    info["stderr"] = (proc.stderr or "").strip()[-400:]
    if proc.returncode != 0:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()
        detail = tail[-1] if tail else f"exit={proc.returncode}"
        errors.append({"id": "render_failed", "line": 0,
                       "message": f"渲染失败：{detail}（dot 退出码 {proc.returncode}）"})
        return info, errors
    if not out.is_file() or out.stat().st_size == 0:
        errors.append({"id": "render_empty", "line": 0,
                       "message": f"渲染产物缺失或为空: {out}"})
        return info, errors
    info["ok"] = True
    info["bytes"] = out.stat().st_size
    if fmt != "svg":
        return info, errors
    svg = out.read_text(encoding="utf-8", errors="replace")
    if "<svg" not in svg:
        errors.append({"id": "render_no_svg", "line": 0,
                       "message": "SVG 产物不含 <svg> 根元素，内容可能损坏"})
        return info, errors
    n_nodes = svg.count('class="node"')
    n_edges = svg.count('class="edge"')
    info["nodes"] = n_nodes
    info["edges"] = n_edges
    if expect:
        info["expect_failures"] = []
        if "nodes" in expect and expect["nodes"] != n_nodes:
            msg = f"节点数不符：期望 {expect['nodes']}，实际渲染 {n_nodes}"
            errors.append({"id": "expect_nodes_mismatch", "line": 0, "message": msg})
            info["expect_failures"].append(msg)
        if "edges" in expect and expect["edges"] != n_edges:
            msg = f"边数不符：期望 {expect['edges']}，实际渲染 {n_edges}"
            errors.append({"id": "expect_edges_mismatch", "line": 0, "message": msg})
            info["expect_failures"].append(msg)
        for needle in expect.get("must_contain", []):
            if needle not in svg:
                msg = f"SVG 中找不到期望文本: {needle!r}"
                errors.append({"id": "expect_missing_text", "line": 0, "message": msg})
                info["expect_failures"].append(msg)
        for needle in expect.get("must_not_contain", []):
            if needle in svg:
                msg = f"SVG 中出现了禁止文本: {needle!r}"
                errors.append({"id": "expect_forbidden_text", "line": 0, "message": msg})
                info["expect_failures"].append(msg)
    return info, errors


def check_file(path: Path, render: bool, fmt: str, out: Path | None,
               expect_path: Path | None, dot_bin: str | None) -> dict:
    report: dict = {"file": str(path), "errors": [], "notes": []}
    try:
        text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        report["errors"].append({"id": "unreadable_file", "line": 0,
                                 "message": f"文件不是有效 UTF-8: {exc}"})
        return report
    except OSError as exc:
        report["errors"].append({"id": "unreadable_file", "line": 0,
                                 "message": f"文件读取失败: {exc}"})
        return report
    errors, notes = lint_dot(text)
    report["errors"].extend(errors)
    report["notes"].extend(notes)
    if render and not report["errors"]:
        if not dot_bin:
            report["render"] = {"ok": False, "error": "dot_not_found"}
            report["errors"].append({
                "id": "dot_not_found", "line": 0,
                "message": "找不到 dot 可执行文件：请安装 Graphviz 或用 --dot/GRAPHVIZ_DOT 指定路径"})
            return report
        fmt_out = out if out is not None else path.with_suffix("." + fmt)
        expect, expect_err = _load_expect(expect_path, path)
        if expect_err:
            report["errors"].append({"id": "expect_file_error", "line": 0, "message": expect_err})
            return report
        info, r_errors = render_check(dot_bin, path, fmt, fmt_out, expect)
        report["render"] = info
        report["errors"].extend(r_errors)
    return report


# ---------------------------------------------------------------------------
# 内置自检用例：正向不误报，负向必拦截
# ---------------------------------------------------------------------------

GOOD_CASES = [
    ("minimal_digraph", 'digraph g { a -> b; }'),
    ("undirected", 'graph g { a -- b; }'),
    ("edge_attrs_after_edge", 'digraph g { a -> b [label="x", style=dashed]; }'),
    ("multiline_edge_attrs", 'digraph g {\n  a -> b\n  [label="x"];\n}'),
    ("html_label_quoted", 'digraph g { a [label="<B>bold</B>"]; }'),
    ("html_label_doubled", 'digraph g { a [label=<<B>bold</B>>]; }'),
    ("record_ports", 'digraph g { t [shape=record, label="<h> 任务|状态"]; r -> t:h; }'),
    ("cluster_and_rank", 'digraph g { subgraph cluster_c { label="组"; a; b; } '
                         '{ rank=same; a; b; } a -> b; }'),
]

BAD_CASES = [
    ("dash_in_digraph", 'digraph g { a -- b; }', "edge_operator_mismatch"),
    ("arrow_in_graph", 'graph g { a -> b; }', "edge_operator_mismatch"),
    ("attr_then_edge", 'digraph g { a [label="x"] -> b; }', "attr_then_edge"),
    ("unclosed_brace", 'digraph g { a -> b;', "unbalanced_braces"),
    ("unclosed_bracket", 'digraph g { a [label="x"; }', "unbalanced_brackets"),
    ("html_label_bare", 'digraph g { a [label=<B>x</B>]; }', "html_label_unquoted"),
    ("unterminated_string", 'digraph g { a [label="never closed]; }', "unterminated_string"),
    ("missing_keyword", '{ a -> b; }', "missing_graph_keyword"),
]


def self_test(dot_bin: str | None, render: bool) -> tuple[bool, list[str]]:
    """跑内置用例 + 全部模板 + 机检示例。返回 (全部通过, 失败摘要)。"""
    failures: list[str] = []
    for name, src in GOOD_CASES:
        errors, _ = lint_dot(src)
        if errors:
            failures.append(f"good/{name}: 误报 {[(e['id'], e['message']) for e in errors]}")
    for name, src, want in BAD_CASES:
        errors, _ = lint_dot(src)
        got = {e["id"] for e in errors}
        if want not in got:
            failures.append(f"bad/{name}: 期望 {want}，实际 {sorted(got) or '无错误'}")
    for tpl in sorted(TEMPLATES_DIR.glob("*.dot")):
        errors, _ = lint_dot(tpl.read_text(encoding="utf-8"))
        if errors:
            failures.append(f"template/{tpl.name}: {[(e['id'], e['message']) for e in errors]}")
    example = EXAMPLES_DIR / "pipeline_demo.dot"
    if example.is_file():
        expect_path = EXAMPLES_DIR / "pipeline_demo.checks.json"
        with tempfile.TemporaryDirectory() as td:
            out = Path(td) / "pipeline_demo.svg"
            rep = check_file(example, render, "svg", out, expect_path, dot_bin)
            for e in rep["errors"]:
                failures.append(f"example/{example.name}: {e['id']}: {e['message']}")
    for tpl in sorted(TEMPLATES_DIR.glob("*.dot")):
        if not render:
            break
        if not dot_bin:
            failures.append("render: 找不到 dot，无法完成渲染自检（--self-test --render 需 Graphviz）")
            break
        with tempfile.TemporaryDirectory() as td:
            info, r_errors = render_check(dot_bin, tpl, "svg", Path(td) / (tpl.stem + ".svg"), None)
            for e in r_errors:
                failures.append(f"template-render/{tpl.name}: {e['id']}: {e['message']}")
    return not failures, failures


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="DOT 静态检查 + Graphviz 渲染门禁（graphviz 技能自带）")
    parser.add_argument("file", nargs="?", help="要检查的 .dot 文件")
    parser.add_argument("--render", action="store_true", help="静态检查通过后真实渲染")
    parser.add_argument("--format", default="svg", choices=["svg", "png", "pdf"],
                        help="渲染格式（默认 svg）")
    parser.add_argument("--out", type=Path, default=None, help="渲染产物路径（默认与源同目录同名后缀）")
    parser.add_argument("--expect", type=Path, default=None,
                        help="结构化期望 JSON（nodes/edges/must_contain/must_not_contain）")
    parser.add_argument("--dot", default=None, help="dot 可执行文件路径（也可用环境变量 GRAPHVIZ_DOT）")
    parser.add_argument("--lint-dir", type=Path, default=None, help="批量静态检查目录下全部 .dot")
    parser.add_argument("--self-test", action="store_true", help="运行内置用例与模板/示例自检")
    parser.add_argument("--json", action="store_true", help="输出机读 JSON")
    args = parser.parse_args(argv)

    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    if args.self_test:
        dot_bin = find_dot(args.dot)
        ok, failures = self_test(dot_bin, render=args.render)
        if args.json:
            print(json.dumps({"self_test": ok, "failures": failures}, ensure_ascii=False, indent=2))
        else:
            print("dot_check 自检：通过" if ok else "dot_check 自检：失败")
            for f in failures:
                print(f"  FAIL {f}")
            if ok:
                print(f"  覆盖：lint 用例 {len(GOOD_CASES)}正/{len(BAD_CASES)}负、"
                      f"模板 {len(list(TEMPLATES_DIR.glob('*.dot')))} 个、"
                      f"机检示例 1 个{'（含实渲染）' if args.render and dot_bin else '（仅静态：未开 --render 或无 dot）'}")
        return 0 if ok else 1

    if args.lint_dir:
        if not args.lint_dir.is_dir():
            print(f"目录不存在: {args.lint_dir}", file=sys.stderr)
            return 2
        targets = sorted(args.lint_dir.glob("*.dot"))
        if not targets:
            print(f"目录中没有 .dot 文件: {args.lint_dir}", file=sys.stderr)
            return 2
        reports = [check_file(t, False, args.format, None, None, None) for t in targets]
        bad = [r for r in reports if r["errors"]]
        if args.json:
            print(json.dumps(reports, ensure_ascii=False, indent=2))
        else:
            for r in reports:
                mark = "FAIL" if r["errors"] else "PASS"
                print(f"[{mark}] {r['file']}")
                for e in r["errors"]:
                    print(f"    {e['id']}: L{e['line']} {e['message']}")
                for nt in r["notes"]:
                    print(f"    note: L{nt['line']} {nt['message']}")
            print(f"共 {len(reports)} 个文件，{len(bad)} 个未过")
        return 1 if bad else 0

    if not args.file:
        parser.print_usage(sys.stderr)
        print("缺少 .dot 文件；或使用 --self-test / --lint-dir", file=sys.stderr)
        return 2
    src = Path(args.file)
    if not src.is_file():
        print(f"文件不存在: {src}", file=sys.stderr)
        return 2
    dot_bin = find_dot(args.dot) if args.render else None
    report = check_file(src, args.render, args.format, args.out, args.expect, dot_bin)
    if args.render and report.get("render", {}).get("error") == "dot_not_found":
        # 环境问题单独成码，不与"检查未过"混同
        if args.json:
            print(json.dumps(report, ensure_ascii=False, indent=2))
        else:
            for e in report["errors"]:
                print(f"  {e['id']}: {e['message']}")
        return 2
    if args.json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        mark = "FAIL" if report["errors"] else "PASS"
        print(f"[{mark}] {report['file']}")
        for e in report["errors"]:
            line = f"L{e['line']} " if e.get("line") else ""
            print(f"    {e['id']}: {line}{e['message']}")
        for nt in report["notes"]:
            print(f"    note: L{nt['line']} {nt['message']}")
        r = report.get("render")
        if r and r.get("ok"):
            extra = f"，nodes={r.get('nodes')}, edges={r.get('edges')}" if "nodes" in r else ""
            print(f"    render: {r['format']} → {r['output']}（{r.get('bytes', 0)} 字节{extra}）")
    return 1 if report["errors"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
