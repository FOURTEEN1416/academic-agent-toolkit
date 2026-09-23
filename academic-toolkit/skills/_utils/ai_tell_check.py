#!/usr/bin/env python3
"""论文正文「AI 痕迹措辞」审计闸。

用法:
  python ai_tell_check.py                 # 在工作区根目录跑，自动找 paper/
  python ai_tell_check.py paper/main.md   # 指定文件
  python ai_tell_check.py --strict        # 空话套话也计入失败（默认只警告）

退出码: 0=干净  1=查出禁用语汇(必修)  2=没找到正文文件(跳过不阻塞)

⛔ 为什么需要这个闸：这类词是【内部工程/质检语汇】，从流水线提示词流进论文正文。
   实测 10 个真实工作区命中 442 次，「口径」单独 225 次——是所有 AI 痕迹里最密集的一类。
   人工通读会漏（单篇最高 96 次），必须机器扫。

⛔ 全标准库实现，与项目其它 tools 一致，不引第三方。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments

# ⛔ 强制 UTF-8 输出：Windows 控制台默认 GBK，重定向到文件后中文与 ❌ 变成 GBK 字节，
#    调用方用 grep 按 UTF-8 找就全落空（实测 writing_check.sh 因此只打印提示、丢了明细）。
#    在脚本内部解决，这样无论调用方有没有加 -X utf8 都正确。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ===== 硬拦项：工程/质检语汇（词 → 学术替代）=====
BANNED = {
    "口径": "定义 / 取法 / 计算方式 / 统计范围",
    "闭环": "反馈校正 / 迭代修正 / 反馈回路",
    "台账": "汇总表 / 一览表",
    "自检": "校验 / 一致性检验 / 复核",
    "对账": "核对 / 一致性检验",
    "兜底": "缺省处理 / 默认取值",
    "回填": "补充取值 / 反向代入",
    "上游": "前序 / 前一阶段",
    "下游": "后续 / 后一阶段",
    "链路": "传递路径 / 因果链 / 作用路径",
    "复用": "沿用 / 采用",
    "落地": "实现 / 完成",
    "打通": "贯通 / 衔接",
    "拉齐": "统一 / 一致化",
    "颗粒度": "粒度 / 精细程度 / 分辨率",
    "抓手": "（删改为具体说法）",
    "赋能": "（删改为具体说法）",
    "维度上": "在……方面",
    "修正项": "修正量 / 校正项",
    "约束验证": "（删去验收式标题；把有意义的余量自然写入结果讨论）",
    "约束校验": "可行性分析 / 容量余量 / 误差范围",
    "代码内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "代码中内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "程序中内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "内置断言": "（删去实现痕迹，直接陈述参数变化规律）",
    "可证伪断言": "敏感性分析 / 参数变化规律",
    "可证伪的有效性保证": "误差分析 / 参数变化规律 / 适用范围",
    "铁证": "证据 / 结果表明（优先直接陈述具体事实）",
    "降维失败": "近似偏差 / 模型偏离题意",
    "质量门": "（正文删除；仅保留内部报告）",
    "能力审计": "（正文删除；仅保留内部报告）",
    "能力项": "（正文删除；直接陈述模型、方法或结果）",
    "验收项": "（正文删除；直接陈述模型、方法或结果）",
    "能力验收": "（正文删除；仅保留内部报告）",
    "运行时断言": "（正文删除；直接陈述数学关系或数值现象）",
    "健康阈值": "阈值 / 判定界限（仅在确有数学含义时保留）",
    "审计报告": "（正文删除；仅保留内部报告）",
    "审计状态": "（正文删除；仅保留内部报告）",
    "审计项": "（正文删除；直接陈述检查对象）",
    "任务返修": "（正文删除；修改过程不得写入论文）",
    "返修记录": "（正文删除；修改过程不得写入论文）",
    "自动返修": "（正文删除；修改过程不得写入论文）",
    "工作流": "研究过程 / 建模步骤（仅在确有学术含义时改写）",
    "流水线": "处理过程 / 计算流程（仅在确有学术含义时改写）",
    "零越界": "未超过容量上限，并给出最大利用率或余量",
    "全流程校验": "（删去验收流程，直接陈述误差、余量或适用范围）",
    "constraint validation passed": "report the concrete feasibility margin or residual",
    "all checks passed": "remove the log-style statement and discuss only informative results",
    "built-in assertion": "state the observed parameter trend without implementation details",
    "audit passed": "remove the internal audit status",
    "quality gate": "remove from the paper; keep only in the internal report",
}

# ===== 硬拦项：内部标记 =====
MARK_PATTERNS = [
    (r"[⛔✅❌⚠]", "内部标记符号"),
    (r"\b(?:RESULTS|PARAMS_RAW|MODELING_REPORT|PROBLEM_ANALYSIS|AUDIT_REPORT|"
     r"COMPILE_REPORT|PAPER_MODELING_QUALITY_REPORT|CAPABILITY_AUDIT)\.md\b",
     "内部文件名"),
    (r"\bCAPABILITY_CHECKLIST(?:\.json)?\b", "内部文件名"),
    (r"\bMETHOD_CLAIMS\b", "内部标记"),
    (r"\bHC-\d+", "内部质检编号"),
    (r"\bP\d+[-_]C\d+(?:[-_]\d+)?\b", "内部能力编号"),
    (r"\b(?:Agent|Skill)(?:s|\b)", "智能体内部术语"),
    (r"\b(?:validate(?:_|\\_)constraints|validate(?:_|\\_)storage|monotonicity(?:_|\\_)check)\b",
     "内部检查函数名"),
    (r"\bok\s*=\s*true\b", "内部通过状态"),
    (r"(?:约束|程序|代码|断言|检查|自检).{0,12}(?:全部|均)(?:通过|成立)",
     "验收式通过结论"),
]

# ===== 仅警告项：空话套话 =====
SOFT = ["值得注意的是", "综上所述", "不难发现", "显而易见", "需要指出的是",
        "由此可见", "换言之", "具有重要的理论意义", "创新性地", "深入探讨"]

# ⛔ 只扫论文正文；报告/审计/清单类文件本就该用工程语汇，扫它们是误报
EXCLUDE_NAME = re.compile(
    r"REPORT|AUDIT|CHECK|TODO|PROFILE|LEDGER|MANIFEST|CHECKLIST|VERDICT"
    r"|ANALYSIS|PARAMS|RESULTS|CLAUDE|README|_writing_context", re.I)


def find_targets(args_paths):
    if args_paths:
        return [Path(p) for p in args_paths if Path(p).is_file()]
    # ⛔ 有 paper/ 就【只】扫 paper/，不要回落到根目录：
    #    根目录散落着 _format_reference.md、_s123.md 这类工作文件，
    #    它们本就该用工程语汇，扫了全是误报（实测踩到）。
    paper_mode = Path("paper").is_dir()
    if paper_mode and Path("paper/main.tex").is_file():
        return active_sources(Path("paper"))
    if paper_mode and Path("paper/main.md").is_file():
        return [Path("paper/main.md")]
    dirs = [Path("paper")] if paper_mode else [Path(".")]
    out = []
    for d in dirs:
        if not d.is_dir():
            continue
        for pat in ("*.md", "*.tex"):
            iterator = d.rglob(pat) if paper_mode else d.glob(pat)
            for f in sorted(iterator):
                # ⛔ 排除 _ 开头的临时/工作文件（_writing_context.md、_s123.md 等）
                # paper/ 内的 2_analysis.tex 等是合法正文，不得因文件名含 ANALYSIS 被误跳过。
                if f.name.startswith("_") or (not paper_mode and EXCLUDE_NAME.search(f.name)):
                    continue
                out.append(f)
    # 去重保序
    seen, uniq = set(), []
    for f in out:
        k = f.resolve()
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def strip_noscan(text: str) -> str:
    """挖掉不该扫的区域，避免误报：
    ⛔ 代码块/lstlisting（附录贴的代码里出现 self_check 之类是正常的）
    ⛔ 注释（LaTeX % 与 Markdown <!-- -->）
    用等长空白替换，保持行号与列号不变。
    """
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    # ⛔ 先挖【更长的围栏】：Markdown 允许 ```` 包裹 ```，若先挖 ``` 会把外层拆散，
    #    残留的内层内容被当成正文（对抗测试实测误报）。从 6 个反引号往下试。
    for n in range(6, 2, -1):
        f = "`" * n
        text = re.sub(re.escape(f) + r".*?" + re.escape(f), blank, text, flags=re.S)
    for n in range(6, 2, -1):
        f = "~" * n
        text = re.sub(re.escape(f) + r".*?" + re.escape(f), blank, text, flags=re.S)
    # 未闭合围栏：从起始处挖到文末（否则后面全被当正文，或反之）
    text = re.sub(r"(?m)^\s*(?:`{3,}|~{3,}).*\Z", blank, text, flags=re.S)
    text = re.sub(
        r"\\begin\{(?P<env>lstlisting|verbatim|minted)\}.*?"
        r"\\end\{(?P=env)\}",
        blank,
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\\verb\*?(?P<delim>[^A-Za-z0-9\s]).*?(?P=delim)",
        blank,
        text,
    )
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    # LaTeX 行注释：% 前面不是 \（\% 是转义百分号）
    text = re.sub(r"(?<!\\)%[^\n]*", blank, text)
    return text


def scan(path: Path):
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], []
    txt = strip_noscan(raw)
    lines = txt.split("\n")
    hard, marks, soft = [], [], []
    for i, ln in enumerate(lines, 1):
        for w, alt in BANNED.items():
            # ⛔ 同一行同一词出现多次时合并显示（×N），但计数按真实次数
            n = len(re.findall(re.escape(w), ln, flags=re.IGNORECASE))
            if n:
                hard.append((i, w, alt, ln.strip()[:70], n))
        for pat, kind in MARK_PATTERNS:
            found = re.findall(pat, ln)
            if found:
                marks.append((i, found[0], kind, ln.strip()[:70], len(found)))
        for w in SOFT:
            if w in ln:
                soft.append((i, w, ln.strip()[:70]))
    return hard, marks, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="要扫的文件；缺省自动找 paper/")
    ap.add_argument("--strict", action="store_true", help="空话套话也计入失败")
    ap.add_argument("--max-show", type=int, default=8, help="每类最多列几条")
    a = ap.parse_args()

    targets = find_targets(a.paths)
    if not targets:
        print("⚠ 未找到论文正文文件（paper/*.md 或 paper/sections/*.tex）— 跳过，不阻塞")
        sys.exit(2)

    tot_hard = tot_mark = tot_soft = 0
    wcount: dict[str, int] = {}
    print("=== AI 痕迹措辞审计 ===")
    print("扫描 %d 个正文文件（已排除代码块/注释/报告类文件）\n" % len(targets))

    for f in targets:
        hard, marks, soft = scan(f)
        if not (hard or marks or soft):
            continue
        print("--- %s ---" % f)
        for i, w, alt, ctx, n in hard[:a.max_show]:
            xn = ("×%d" % n) if n > 1 else ""
            print("  ❌ 第%d行 「%s」%s → 改为：%s" % (i, w, xn, alt))
            print("       %s" % ctx)
        if len(hard) > a.max_show:
            print("  … 另有 %d 行含禁用语汇" % (len(hard) - a.max_show))
        for i, sym, kind, ctx, n in marks[:a.max_show]:
            xn = ("×%d" % n) if n > 1 else ""
            print("  ❌ 第%d行 %s「%s」%s — 内部标记不得进正文" % (i, kind, sym, xn))
        if len(marks) > a.max_show:
            print("  … 另有 %d 行含内部标记" % (len(marks) - a.max_show))
        for i, w, ctx in soft[:3]:
            print("  ⚠ 第%d行 空话「%s」" % (i, w))
        print()
        tot_hard += sum(r[4] for r in hard)
        tot_mark += sum(r[4] for r in marks)
        tot_soft += len(soft)
        for r in hard:
            wcount[r[1]] = wcount.get(r[1], 0) + r[4]

    print("=== 汇总 ===")
    print("禁用语汇 %d 处 · 内部标记 %d 处 · 空话套话 %d 处（仅警告）"
          % (tot_hard, tot_mark, tot_soft))
    if wcount:
        top = sorted(wcount.items(), key=lambda kv: -kv[1])[:8]
        print("最多的词：" + "、".join("%s×%d" % (w, n) for w, n in top))

    fail = tot_hard + tot_mark + (tot_soft if a.strict else 0)
    if fail == 0:
        print("✅ PASS — 正文无 AI 痕迹措辞")
        sys.exit(0)
    print("\n⛔ 共 %d 处必修 — 逐条按替代说法改写，改完重跑本脚本。" % fail)
    print("   替代表见《shared-scripts/writing_rules.md》De-AI Polish 一节。")
    sys.exit(1)


if __name__ == "__main__":
    main()
