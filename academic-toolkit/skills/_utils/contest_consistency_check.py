#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""contest_consistency_check.py — 竞赛论文六类一致性检查（单一实现，双副本同步）。

C-comp-2 收敛：本脚本合并 comp-compile-zh / paper-compile-zh（历史内联）中重复的
六类检查逻辑——数值一致性、太完美检测、数据源时间戳、正文长表格、元叙述泄露、
过度声称。阈值/词表/容差与原内联块逐项一致（见各 check 函数注释）。

用法：
  python contest_consistency_check.py [--paper paper] [--sections paper/sections]
      [--results figures/all_results.json] [--lang zh|en] [--mode latex|docx]
      [--only numeric,perfect,timestamp,longtable,meta,overclaim]
      [--skip numeric,timestamp]

退出码：0 = 无硬失败（advisory 不计入）；1 = 存在硬失败；3 = 输入缺失无法检查（unavailable，
不判通过也不判论文错——与 quality_gate_contract.md 的 GATE_UNAVAILABLE 口径一致）。

各技能正文只保留「何时跑 + 判据 + 修复动作」，检查逻辑以本文件为唯一真源。
"""
import argparse
import json
import os
import re
import sys

# ---------- 通用工具 ----------

def iter_sections(sections_dir, mode="latex"):
    """按语言/模式列出待检正文文件（跳过附录）。"""
    if not os.path.isdir(sections_dir):
        return []
    skip_pat = re.compile(r"appendix|附录|A_code", re.IGNORECASE)
    out = []
    for name in sorted(os.listdir(sections_dir)):
        path = os.path.join(sections_dir, name)
        if not os.path.isfile(path):
            continue
        if mode == "latex" and not name.endswith(".tex"):
            continue
        if skip_pat.search(name):
            continue
        out.append(path)
    return out


def read_text(path):
    with open(path, "r", encoding="utf-8", errors="ignore") as f:
        return f.read()


def flatten_numbers(obj, prefix=""):
    """提取 JSON 中所有有效数值（0.001<|v|<1e10，排除布尔）。"""
    nums = {}
    if isinstance(obj, dict):
        for k, v in obj.items():
            nums.update(flatten_numbers(v, f"{prefix}.{k}"))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            nums.update(flatten_numbers(v, f"{prefix}[{i}]"))
    elif isinstance(obj, (int, float)) and not isinstance(obj, bool):
        if 0.001 < abs(obj) < 1e10:
            nums[prefix] = obj
    return nums


def mtime(path):
    try:
        return os.path.getmtime(path)
    except OSError:
        return 0


# ---------- 六类检查 ----------

def check_numeric(sections_dir, results_path, lang):
    """#22 数值一致性：all_results.json 关键指标 vs 正文，1% 容差；>3 项缺失硬失败。"""
    if not os.path.isfile(results_path):
        return None, f"results 文件不存在（{results_path}），跳过数值一致性"
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            results = json.load(f)
    except (OSError, ValueError) as e:
        return None, f"results 文件不可解析（{e}），跳过数值一致性"
    json_nums = flatten_numbers(results)
    paper_nums = set()
    for path in iter_sections(sections_dir):
        text = read_text(path)
        # LaTeX 与 docx/markdown 通用：抓裸数字（不夹在字母/下标/花括号间）
        for m in re.finditer(r"(?<![a-zA-Z])(\d+\.?\d+)(?![a-zA-Z_{}])", text):
            try:
                paper_nums.add(float(m.group(1)))
            except ValueError:
                pass
    key_words = ["rmse", "r2", "accuracy", "f1", "objective", "optimal", "best"]
    missing = sum(
        1 for k, v in json_nums.items()
        if not any(abs(p - v) < abs(v) * 0.01 + 0.001 for p in paper_nums)
        and any(w in k.lower() for w in key_words)
    )
    if missing:
        detail = f"❌ {missing} 个关键指标在正文找不到（1% 容差）— 回正文补数值或核对来源"
        return (missing > 3), detail
    return False, "✅ 关键指标数值一致（正文可对账）"


def check_perfect(results_path):
    """#22.5 太完美检测：>0.999/零误差/完美显著/提升>10 倍 —— 只提示不阻断（advisory）。"""
    if not os.path.isfile(results_path):
        return None, f"results 文件不存在（{results_path}），跳过太完美检测"
    try:
        with open(results_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError) as e:
        return None, f"results 文件不可解析（{e}），跳过太完美检测"
    suspicious = []

    def check_one(name, val):
        if not isinstance(val, (int, float)) or isinstance(val, bool):
            return
        key = name.lower()
        if any(w in key for w in ["r2", "r_squared", "accuracy", "acc", "precision", "recall", "f1", "auc"]) and val > 0.999:
            suspicious.append(f"{name}={val:.4f} 过于完美（>0.999）")
        if any(w in key for w in ["rmse", "mae", "mse", "loss"]) and val == 0:
            suspicious.append(f"{name}=0 完美误差")
        if ("p_value" in key or "pvalue" in key) and val == 0:
            suspicious.append(f"{name}=0 完美显著")
        if any(w in key for w in ["improvement", "speedup", "gain", "提升"]) and val > 10:
            suspicious.append(f"{name}={val} 提升过大（{val * 100:.0f}%）")

    def walk(obj, path=""):
        if isinstance(obj, dict):
            for k, v in obj.items():
                walk(v, f"{path}.{k}")
        elif isinstance(obj, list):
            for i, v in enumerate(obj):
                walk(v, f"{path}[{i}]")
        else:
            check_one(path, obj)

    walk(data)
    if suspicious:
        lines = [f"🚩 {len(suspicious)} 处可疑的完美结果（可能过拟合或数值编造，advisory 不阻断）："]
        lines += [f"    {s}" for s in suspicious[:5]]
        lines.append("    需在论文中说明合理性，或回到 comp-code 检查数据泄漏")
        return False, "\n".join(lines)
    return False, "✅ 数值合理性通过（无可疑完美值）"


def check_timestamp(results_path, figures_dir):
    """#22.7 数据源时间戳：PDF 图比 results JSON 旧 >60s → 图表可能用了旧数据（硬失败）。"""
    if not os.path.isfile(results_path):
        return None, f"results 文件不存在（{results_path}），跳过时间戳检查"
    if not os.path.isdir(figures_dir):
        return None, f"figures 目录不存在（{figures_dir}），跳过时间戳检查"
    json_time = mtime(results_path)
    stale = []
    for name in sorted(os.listdir(figures_dir)):
        if not name.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(figures_dir, name)
        pdf_time = mtime(pdf_path)
        if json_time > pdf_time and (json_time - pdf_time) > 60:
            stale.append(name)
    if stale:
        lines = [f"❌ {len(stale)} 张图表可能使用了旧数据（results JSON 更新后图表未重新生成）："]
        lines += [f"    ⚠ {n} 比 results 旧 — 图表数据可能过期" for n in stale]
        lines.append("    → 重跑 paper-figure 步骤更新图表")
        return True, "\n".join(lines)
    return False, "✅ 数据源时间戳一致"


def check_longtable(sections_dir, mode="latex", max_rows=12):
    """#22.8 正文长表格：tabular/longtable 数据行 >12 行应截断（前3+后3+省略），完整版放附录。"""
    findings = []
    for path in iter_sections(sections_dir, mode):
        content = read_text(path)
        if mode == "docx":
            # markdown 管道表：按连续表格块数行
            lines = content.split("\n")
            run = 0
            for ln in lines:
                if ln.strip().startswith("|") and ln.strip().endswith("|"):
                    run += 1
                else:
                    if run > max_rows + 1:  # 含表头分隔行
                        findings.append(f"{os.path.basename(path)}: markdown 表约 {run - 2} 行（>{max_rows}）")
                    run = 0
        else:
            for env in ["tabular", "longtable", "tabular*"]:
                pattern = r"\\begin\{" + env + r"[*]?\}.*?\\end\{" + env + r"[*]?\}"
                for match in re.finditer(pattern, content, re.DOTALL):
                    table_text = match.group()
                    row_count = table_text.count("\\\\") - table_text.count("\\hline") // 2
                    if row_count > max_rows:
                        findings.append(f"{os.path.basename(path)}: {env} 有 {row_count} 行（>{max_rows}）")
    if findings:
        lines = [f"❌ {len(findings)} 处正文长表格（>{12 if max_rows==12 else max_rows} 行，应截断前3+后3+省略，完整版放附录）："]
        lines += [f"    ❌ {f}" for f in findings]
        return True, "\n".join(lines)
    return False, "✅ 正文无超长表格"


def check_meta(sections_dir, mode="latex", extra_names=None):
    """#24 元叙述泄露：内部文件名出现在正文（硬失败）。docx 模式扫 main.md。"""
    internal = ["RESULTS.md", "AGENTS.md", "MODELING_REPORT", "PROBLEM_ANALYSIS", "latex_includes"]
    if extra_names:
        internal += list(extra_names)
    leaks = 0
    scan_targets = []
    if mode == "docx":
        # docx：正文是单文件 main.md
        base = os.path.dirname(sections_dir.rstrip("/\\")) if sections_dir else "."
        main_md = os.path.join(os.path.dirname(sections_dir) or ".", "main.md")
        scan_targets = [main_md] if os.path.isfile(main_md) else []
    else:
        scan_targets = iter_sections(sections_dir, mode)
    for path in scan_targets:
        text = read_text(path)
        pattern = "|".join(re.escape(w) for w in internal)
        leaks += len(re.findall(pattern, text, re.IGNORECASE))
    if leaks:
        return True, f"❌ {leaks} 处元叙述泄露（内部文件名出现在正文：{', '.join(internal)}）— 删除或改写"
    return False, "✅ 无元叙述泄露"


def check_overclaim(sections_dir, mode="latex", lang="zh"):
    """#25 过度声称：绝对化措辞计数 —— 只提示不阻断（advisory，建议温和化）。"""
    words_zh = ["首次提出", "首次发现", "完美", "最优的", "无可比拟", "前所未有", "开创性", "革命性"]
    words_en = ["first ever", "perfect", "unprecedented", "revolutionary", "groundbreaking", "state-of-the-art"]
    words = words_zh if lang == "zh" else words_en
    count = 0
    hits = []
    for path in iter_sections(sections_dir, mode):
        text = read_text(path)
        for w in words:
            c = text.count(w)
            if c:
                count += c
                hits.append(f"{os.path.basename(path)}: {w} ×{c}")
    if count:
        lines = [f"⚠ {count} 处过度声称措辞（advisory 不阻断，建议温和化）："]
        lines += [f"    {h}" for h in hits[:8]]
        return False, "\n".join(lines)
    return False, "✅ 无过度声称措辞"


CHECKS = ["numeric", "perfect", "timestamp", "longtable", "meta", "overclaim"]


def main(argv=None):
    ap = argparse.ArgumentParser(description="竞赛论文六类一致性检查（comp 簇共享单一实现）")
    ap.add_argument("--paper", default="paper", help="论文目录（含 sections/ 或 main.md）")
    ap.add_argument("--sections", default=None, help="正文目录，默认 <paper>/sections")
    ap.add_argument("--results", default=None, help="结果 JSON，默认 figures/all_results.json")
    ap.add_argument("--figures", default="figures", help="图表目录（时间戳检查用）")
    ap.add_argument("--lang", default="zh", choices=["zh", "en"], help="过度声称词表语言")
    ap.add_argument("--mode", default="latex", choices=["latex", "docx"], help="正文形态（决定扫描方式）")
    ap.add_argument("--max-table-rows", type=int, default=12, help="正文表格行数上限")
    ap.add_argument("--only", default="", help="只跑这些检查（逗号分隔）")
    ap.add_argument("--skip", default="", help="跳过这些检查（逗号分隔）")
    args = ap.parse_args(argv)

    sections = args.sections or os.path.join(args.paper, "sections")
    results = args.results or os.path.join(args.figures, "all_results.json")
    only = {s.strip() for s in args.only.split(",") if s.strip()}
    skip = {s.strip() for s in args.skip.split(",") if s.strip()}
    todo = [c for c in CHECKS if (not only or c in only) and c not in skip]

    hard_fail = 0
    unavailable = 0
    for name in todo:
        if name == "numeric":
            fail, msg = check_numeric(sections, results, args.lang)
        elif name == "perfect":
            fail, msg = check_perfect(results)
        elif name == "timestamp":
            fail, msg = check_timestamp(results, args.figures)
        elif name == "longtable":
            fail, msg = check_longtable(sections, args.mode, args.max_table_rows)
        elif name == "meta":
            fail, msg = check_meta(sections, args.mode)
        elif name == "overclaim":
            fail, msg = check_overclaim(sections, args.mode, args.lang)
        else:
            continue
        print(f"[{name}] {msg}")
        if fail is None:
            unavailable += 1
        elif fail:
            hard_fail += 1

    if hard_fail:
        print(f"\n❌ contest_consistency_check: {hard_fail} 项硬失败（必修）")
        return 1
    if unavailable == len(todo):
        print("\n⚠ contest_consistency_check: 全部检查因输入缺失跳过（unavailable，不判通过）")
        return 3
    print("\n✅ contest_consistency_check: 无硬失败")
    return 0


if __name__ == "__main__":
    sys.exit(main())
