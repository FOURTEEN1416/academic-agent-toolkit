#!/usr/bin/env python3
"""
改写质量门禁 v1.0（审美护栏）
对任何"降AI改写"工具的输出做质量审查，防止机械改写杜撰新痕迹、破坏语义与文体。

背景（2026-08-17 实证）：
humanize-chinese 的机械替换会引入新问题——"显著进展"→"可观进展"（语义漂移）、
"值得注意的是"→"要提醒的是"（学术语境破坏）、"进展…进展"（新痕迹）、句号→逗号（句法破坏）。
本工具为改写输出提供 4 维护栏：语义保持 / 句法完整 / 新痕迹检测 / 术语与文体保护。

设计理念：
- 检测规则借鉴社区（moways00001 58模式 / humanize-chinese 20+类别），但改写质量由本门禁把关
- "站巨人肩膀上"：识别用规则，改写得审美；机械替换一律需要人工复核
- 纯 Python 无依赖，确定性输出

用法：
python tools/rewrite_quality_gate.py <原文件> <改写后文件> --json
"""

import re
import json
import sys
import os
from dataclasses import dataclass, field, asdict
from typing import List

# ============================================================
# 学术术语保护表（这些词在学术语境下是正常用法，改写时不应动）
# ============================================================
ACADEMIC_TERMS = [
    "模型", "算法", "求解", "优化", "约束", "目标函数", "决策变量", "参数",
    "收敛", "迭代", "鲁棒性", "灵敏度", "误差", "精度", "方差", "回归",
    "仿真", "验证", "假设", "定理", "引理", "推导", "证明", "数值实验",
    "本文", "问题一", "问题二", "摘要", "参考文献", "附录", "结论",
    "因此", "从而", "进而", "综上", "基于", "针对", "利用", "采用",
    "建立", "提出", "分析", "研究", "探讨", "阐述", "构建", "求解",
]

# 危险替换模式：学术书面词被替换为口语/怪词的"降级替换"（检测改写后文本）
DANGEROUS_DOWNGRADES = [
    (r"要提醒的是", "『要提醒的是』是口语化提醒语，学术语境应保留『值得注意的是』或直接陈述"),
    (r"总之[,，]", "『总之』过于口语，学术语境『综上所述/综上』更合适"),
    (r"说白了", "『说白了』严重口语化，学术论文禁用"),
    (r"说白了就是", "同上"),
    (r"搞[一了]?[定好]?", "『搞』为口语动词，学术论文应改用『进行/完成/实现』"),
    (r"啥[，,。]?", "『啥』口语化，应为『什么』或删去"),
    (r"挺[好大快]的", "『挺…的』口语化程度词"),
    (r"蛮[好大快]的", "『蛮…的』口语化程度词"),
    (r"超[级快好强]", "『超…』网语化程度词"),
    (r"简直", "『简直』口语化，学术语境慎用"),
    (r"真的[很非常]", "『真的很/真的非常』口语化强调"),
]

# 语义漂移高风险对（改写时可能把 A 换成 B 造成语义改变）
# 格式: (原词, 危险替换词) —— 改写后出现这些替换需警告
# 注意：仅收录"含义不等价"的明确漂移对；多义词（模型/框架、分析/研究等）不收录，避免误报合理改写
SEMANTIC_DRIFT_PAIRS = [
    ("显著", "可观"), ("显著", "巨大"),
    ("研究", "探究"), ("研究", "研讨"),
    ("分析", "琢磨"),
    ("验证", "佐证"),
    ("提升", "搞上去"), ("优化", "弄好"),
    ("有效的", "好使的"), ("重要", "要紧"),
    ("贡献", "功劳"), ("解决", "搞定"),
    ("展现", "露脸"), ("建立", "搭起"),
    ("包含", "装进"), ("支撑", "撑住"),
    ("提出", "抛出"), ("采用", "拿来用"),
    ("精度", "准头"), ("数据", "数字"),
]

# 新痕迹检测：改写后出现的高频词重复（同一实义词在短距离内重复）
REPEAT_DISTANCE = 40  # 字符


@dataclass
class GateIssue:
    kind: str  # semantic / syntax / new_ai / register
    severity: str  # warn / error
    detail: str
    location: str = ""


@dataclass
class GateResult:
    passed: bool
    score: int  # 0-100 改写质量分
    issues: List[GateIssue] = field(default_factory=list)
    summary: str = ""
    checks: dict = field(default_factory=dict)


class RewriteQualityGate:
    """改写质量门禁"""

    def __init__(self, original: str, rewritten: str):
        self.orig = original
        self.new = rewritten
        self.issues: List[GateIssue] = []

    def _zh(self, text: str) -> List[str]:
        return re.findall(r"[\u4e00-\u9fff]+", text)

    # ---------- 1. 语义保持 ----------
    def check_semantic_preservation(self) -> dict:
        """检查：数值、关键学术词、专有名词是否保留"""
        problems = []
        # 数值保留（数字+单位）
        orig_nums = set(re.findall(r"\d+(?:\.\d+)?(?:%|％|万|亿|km|m|kg)?", self.orig))
        new_nums = set(re.findall(r"\d+(?:\.\d+)?(?:%|％|万|亿|km|m|kg)?", self.new))
        missing_nums = orig_nums - new_nums
        if missing_nums:
            problems.append(f"数值丢失: {sorted(missing_nums)[:5]}")
        # 学术术语保留
        orig_terms = set(t for t in ACADEMIC_TERMS if t in self.orig)
        new_terms = set(t for t in ACADEMIC_TERMS if t in self.new)
        missing_terms = orig_terms - new_terms
        if missing_terms:
            problems.append(f"术语丢失/被替换: {sorted(missing_terms)[:6]}")
        # 语义漂移对检测（仅当危险词在原文中不存在、改写后新增时报警——避免误报原文共现词）
        for orig_w, danger_w in SEMANTIC_DRIFT_PAIRS:
            if (orig_w in self.orig and danger_w in self.new
                    and danger_w not in self.orig):
                problems.append(f"疑似语义漂移: 『{orig_w}』→『{danger_w}』")
                self.issues.append(GateIssue("semantic", "error",
                                             f"语义漂移: 『{orig_w}』被替换为『{danger_w}』（含义不等价）"))
        if not problems:
            self.issues.append(GateIssue("semantic", "warn", "语义保持良好"))
        return {"problems": problems, "ok": not problems}

    # ---------- 2. 句法完整 ----------
    def check_syntax_integrity(self) -> dict:
        """检查：句子边界完整性、括号配对、明显残缺"""
        problems = []
        # 句号→逗号破坏（原句号处被改成逗号且未合理断句）
        # 简单检查：结尾标点完整性
        o_end = self.orig.rstrip()
        n_end = self.new.rstrip()
        if o_end and o_end[-1] in "。！？" and n_end and n_end[-1] not in "。！？":
            problems.append(f"结尾标点由『{o_end[-1]}』变为『{n_end[-1]}』，句法不完整")
            self.issues.append(GateIssue("syntax", "warn", "结尾句号丢失，句法不完整"))
        # 括号配对
        for op, cl in [("(", ")"), ("【", "】"), ("[", "]")]:
            if self.new.count(op) != self.new.count(cl):
                problems.append(f"括号不配对: {op}{cl}")
                self.issues.append(GateIssue("syntax", "error", f"括号不配对 {op}{cl}"))
        # 空块/残缺（连续两个逗号、句号后无内容）
        if re.search(r"，[，、]", self.new):
            problems.append("连续标点（，[，、]）疑似拼接残缺")
            self.issues.append(GateIssue("syntax", "warn", "连续标点，疑似拼接残缺"))
        if not problems:
            self.issues.append(GateIssue("syntax", "warn", "句法完整"))
        return {"problems": problems, "ok": not problems}

    # ---------- 3. 新痕迹检测 ----------
    def check_new_traces(self) -> dict:
        """检查：改写后是否引入新AI痕迹（词汇重复、口语化降级、语义重复）"""
        problems = []
        # 危险降级替换
        for pattern, desc in DANGEROUS_DOWNGRADES:
            m = re.search(pattern, self.new)
            if m:
                problems.append(desc)
                self.issues.append(GateIssue("new_ai", "error", desc))
        # 同句词汇重复（40字内同一实词≥2次）
        zh_words = re.findall(r"[\u4e00-\u9fff]{2,4}", self.new)
        for i, w in enumerate(zh_words):
            if w in ("我们", "可以", "进行", "一个", "这个", "以及", "通过"):
                continue
            window = zh_words[i + 1:i + 8]
            if window.count(w) >= 2:
                problems.append(f"短距离词汇重复: 『{w}』")
                self.issues.append(GateIssue("new_ai", "warn",
                                             f"短距离词汇重复『{w}』（机械替换常见新痕迹）"))
                break
        if not problems:
            self.issues.append(GateIssue("new_ai", "warn", "未引入新痕迹"))
        return {"problems": problems, "ok": not problems}

    # ---------- 4. 文体保护 ----------
    def check_register(self) -> dict:
        """检查：学术/正式文体是否被口语化破坏"""
        problems = []
        # 口语化词
        colloquial = ["说白了", "反正", "挺", "蛮", "超", "搞", "弄", "咱们",
                      "咱", "咋", "啥", "呗", "啦", "呀", "哦", "嗯", "哈"]
        for w in colloquial:
            if w in self.new:
                problems.append(f"口语化词『{w}』进入学术文本")
                self.issues.append(GateIssue("register", "error",
                                             f"口语化词『{w}』进入学术文本，破坏文体"))
        # 网络语
        internet = ["yyds", "绝绝子", "栓Q", "emo", "破防", "内卷", "躺平", "逆袭"]
        for w in internet:
            if w in self.new:
                problems.append(f"网络流行语『{w}』进入文本")
                self.issues.append(GateIssue("register", "error", f"网络流行语『{w}』"))
        # 感叹/口号式
        if re.search(r"[！!]{2,}", self.new):
            problems.append("连续感叹号，口号式表达")
            self.issues.append(GateIssue("register", "warn", "连续感叹号，口号式表达"))
        if not problems:
            self.issues.append(GateIssue("register", "warn", "文体保持"))
        return {"problems": problems, "ok": not problems}

    # ---------- 综合 ----------
    def evaluate(self) -> GateResult:
        c1 = self.check_semantic_preservation()
        c2 = self.check_syntax_integrity()
        c3 = self.check_new_traces()
        c4 = self.check_register()

        # 计分：每维 25 分起扣
        score = 100
        for check in [c1, c2, c3, c4]:
            if check["problems"]:
                score -= len(check["problems"]) * 8
        score = max(0, score)

        # 门禁判定：error 级问题 → 不通过；score < 60 → 不通过
        errors = [i for i in self.issues if i.severity == "error"]
        passed = score >= 60 and not errors

        summary_lines = [
            f"改写质量门禁评分: {score}/100",
            f"语义保持: {'✓' if not c1['problems'] else '✗ ' + '; '.join(c1['problems'][:3])}",
            f"句法完整: {'✓' if not c2['problems'] else '✗ ' + '; '.join(c2['problems'][:3])}",
            f"新痕迹检测: {'✓' if not c3['problems'] else '✗ ' + '; '.join(c3['problems'][:3])}",
            f"文体保护: {'✓' if not c4['problems'] else '✗ ' + '; '.join(c4['problems'][:3])}",
            f"结论: {'通过，可提交人工终审' if passed else '不通过，需人工修正'}",
            "提示: 机械替换工具（如 humanize-chinese）的输出必须过此门禁；",
            "      任何『为了降AI而牺牲语义/文体』的改写都应被拒绝。",
        ]
        return GateResult(
            passed=passed,
            score=score,
            issues=self.issues,
            summary="\n".join(summary_lines),
            checks={"semantic": c1, "syntax": c2, "new_traces": c3, "register": c4},
        )


def main():
    import argparse
    parser = argparse.ArgumentParser(description="改写质量门禁 v1.0（审美护栏）")
    parser.add_argument("original", help="原文件路径")
    parser.add_argument("rewritten", help="改写后文件路径")
    parser.add_argument("--json", action="store_true", help="JSON输出")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    with open(args.original, "r", encoding="utf-8") as f:
        orig = f.read()
    with open(args.rewritten, "r", encoding="utf-8") as f:
        new = f.read()

    gate = RewriteQualityGate(orig, new)
    result = gate.evaluate()

    if args.json:
        out = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    else:
        out = result.summary
        for i in result.issues:
            if i.severity == "error":
                out += f"\n  [error] {i.detail}"

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"结果已保存到: {args.output}")
    else:
        print(out)

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
