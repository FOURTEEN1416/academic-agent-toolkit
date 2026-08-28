#!/usr/bin/env python3
"""
AI味改写建议工具 v1.0
根据 anti_ai_detector.py 的检测结果，对文本中的 AI 味句子给出针对性改写建议。

设计依据（搜索调研）：
1. 62篇获奖论文基线：短句60-78%、被动语态<4.8%、连接词密度4.2-12.3‰、长句<7.7%
2. Lupynow/math-modeling-skills v1.4.0: 八类AI写作痕迹识别 + 真实感注入
3. 知识管理论坛2025: AI生成学术文本语言表达特征
4. writing-anti-ai skill: AI写作痕迹检测与修正

功能：
- 定位 AI 模板句（随着...的发展 / 综上所述 / 值得注意的是 等）
- 定位被动语态句（由...进行 / 被...所 等）
- 定位模板化连接词序列（首先/其次/再次/最后 连用）
- 定位超长句（>80字，AI 倾向）
- 输出逐句改写建议（规则引擎，确定性、可离线）
"""

import re
import sys
import json
from dataclasses import dataclass, field, asdict

# ============================================================
# 规则库
# ============================================================

# AI 模板开头 → 改写建议
TEMPLATE_PATTERNS = [
    {
        "pattern": r"随着[\u4e00-\u9fff]{2,20}的发展",
        "name": "万能开头「随着…的发展」",
        "advice": "删除或改为具体主体：『针对××问题』『在××场景下』，直接进入内容。示例：『随着人工智能技术的发展』→『针对图像分类任务』",
    },
    {
        "pattern": r"近年来[\u4e00-\u9fff]{2,15}日益",
        "name": "万能开头「近年来…日益」",
        "advice": "改为具体时间/数据：『2023年以来，××占比升至××%』，用事实替代空泛表述",
    },
    {
        "pattern": r"在[\u4e00-\u9fff]{2,15}(?:的大?)?背景下",
        "name": "空洞背景「在…背景下」",
        "advice": "删除或替换为具体约束：『在××约束下』『给定××条件』",
    },
    {
        "pattern": r"值得注意的是|需要指出的是|不难发现|显而易见",
        "name": "AI转折强调词",
        "advice": "删除或改为具体发现：『值得注意的是』→『实测表明』『对比发现』",
    },
    {
        "pattern": r"综上所述|总而言之|由此可见",
        "name": "AI总结词",
        "advice": "删除或改为结论句：『综上所述，本文方法有效』→『本文方法在××指标上较基准提升××%』",
    },
    {
        "pattern": r"具有(?:重要的)?(?:理论|实际|现实)(?:价值|意义)",
        "name": "AI价值升华",
        "advice": "删除或替换为可验证结果：『具有重要实际意义』→『在××数据集上达到××准确率』",
    },
    {
        "pattern": r"为[\u4e00-\u9fff]{2,15}(?:提供|奠定|开辟)[\u4e00-\u9fff]{2,10}(?:思路|基础|可能性|方向)",
        "name": "AI展望套话",
        "advice": "删除或改为具体后续工作：『为后续研究提供了新思路』→『下一步将引入××约束』",
    },
]

# 被动语态模式
PASSIVE_PATTERNS = [
    r"由[\u4e00-\u9fff]{0,8}(?:进行|组成|构成|决定|提出|负责|控制|确定|给定)",
    r"被[\u4e00-\u9fff]{1,6}(?:视为|看作|定义为|用于|所)",
    r"受到[\u4e00-\u9fff]{1,6}(?:影响|限制|约束)",
]

# 模板化连接词序列
SEQ_PATTERNS = [
    (r"首先[^。]{0,50}其次[^。]{0,50}(?:再次|然后)[^。]{0,50}最后", "首先/其次/再次/最后 四连"),
    (r"首先[^。]{0,60}其次[^。]{0,60}最后", "首先/其次/最后 三连"),
]

# 超长句阈值（字符）
LONG_SENT_THRESHOLD = 80


# 学术术语保护表（这些词在学术语境下是正常用法，改写时不应动）
# 教训来源：humanize-chinese 机械替换把「研究」→「探究」「显著」→「可观」，造成语义漂移
PROTECTED_TERMS = [
    "模型", "算法", "求解", "优化", "约束", "目标函数", "决策变量", "参数",
    "收敛", "迭代", "鲁棒性", "灵敏度", "误差", "精度", "方差", "回归",
    "仿真", "验证", "假设", "定理", "推导", "证明", "数值实验",
    "本文", "问题一", "问题二", "摘要", "参考文献", "附录", "结论",
    "因此", "从而", "进而", "综上", "基于", "针对", "利用", "采用",
    "建立", "提出", "分析", "研究", "探讨", "阐述", "构建",
]

# 危险替换警示（改写时把 A 换成 B 属于语义漂移，应避免）
DANGEROUS_SWAPS = [
    ("显著", "可观"), ("研究", "探究"), ("验证", "佐证"),
    ("提升", "搞上去"), ("解决", "搞定"), ("重要的", "要紧的"),
]


@dataclass
class FixSuggestion:
    sentence: str
    issue_type: str
    issue_detail: str
    advice: str
    position: int = 0
    protected_terms: list = field(default_factory=list)  # 本句含有的受保护术语
    danger_swaps: list = field(default_factory=list)  # 本句需避免的危险替换


@dataclass
class DeAiResult:
    total_sentences: int
    issues_found: int
    suggestions: list
    summary: str
    protected_terms_hit: list = field(default_factory=list)
    aesthetic_guide: str = ""


class DeAiWriter:
    """AI味改写建议引擎"""

    def __init__(self, text: str):
        self.text = text
        self.sentences = self._split_full()

    def _split_full(self) -> list:
        """分割完整句，跳过代码块与表格行"""
        # 剔除代码块
        text = re.sub(r"```.*?```", " ", self.text, flags=re.DOTALL)
        # 剔除表格行（| a | b |）
        text = re.sub(r"^\s*\|.*\|\s*$", " ", text, flags=re.MULTILINE)
        parts = re.split(r"(?<=[。！？；])\s*|\n+", text)
        return [p.strip() for p in parts if p.strip() and len(p.strip()) > 1]

    def analyze(self) -> DeAiResult:
        suggestions = []
        pos = 0
        for sent in self.sentences:
            sent_start = self.text.find(sent, pos)
            # 本句受保护术语（改写时不得动）
            protected_hit = [t for t in PROTECTED_TERMS if t in sent]
            # 本句需避免的危险替换
            danger_hit = [f"{a}→{b}" for a, b in DANGEROUS_SWAPS if a in sent]
            for rule in TEMPLATE_PATTERNS:
                m = re.search(rule["pattern"], sent)
                if m:
                    suggestions.append(FixSuggestion(
                        sentence=sent[:60] + ("…" if len(sent) > 60 else ""),
                        issue_type="AI模板句",
                        issue_detail=f"命中「{rule['name']}」: {m.group(0)}",
                        advice=rule["advice"],
                        position=sent_start,
                        protected_terms=protected_hit,
                        danger_swaps=danger_hit,
                    ))
            for pat in PASSIVE_PATTERNS:
                m = re.search(pat, sent)
                if m:
                    suggestions.append(FixSuggestion(
                        sentence=sent[:60] + ("…" if len(sent) > 60 else ""),
                        issue_type="被动语态",
                        issue_detail=f"命中被动结构: {m.group(0)}",
                        advice="改为主动语态：『由本文提出』→『本文提出』『被用于求解』→『用于求解』",
                        position=sent_start,
                        protected_terms=protected_hit,
                        danger_swaps=danger_hit,
                    ))
            if len(sent) > LONG_SENT_THRESHOLD:
                suggestions.append(FixSuggestion(
                    sentence=sent[:60] + ("…" if len(sent) > 60 else ""),
                    issue_type="超长句",
                    issue_detail=f"句长 {len(sent)} 字（基线长句占比 <7.7%，阈值80字）",
                    advice="拆分为2-3个短句，保持人类写作的句长节奏：『A，B，C』→『A。B。C。』",
                    position=sent_start,
                    protected_terms=protected_hit,
                    danger_swaps=danger_hit,
                ))
            pos = sent_start + len(sent)

        # 跨句模板化连接词序列
        for pat, name in SEQ_PATTERNS:
            m = re.search(pat, self.text)
            if m:
                suggestions.append(FixSuggestion(
                    sentence=m.group(0)[:60] + "…",
                    issue_type="模板化序列",
                    issue_detail=f"命中 {name}",
                    advice="打散序列，用内容本身衔接：仅保留1-2个连接词，其余改为『接着』『另一组实验』等具体指代",
                    position=m.start(),
                ))

        # 去重（同句同类型只留一条）
        seen = set()
        uniq = []
        for s in suggestions:
            key = (s.sentence, s.issue_type)
            if key not in seen:
                seen.add(key)
                uniq.append(s)

        # 全文受保护术语汇总
        all_protected = sorted({t for t in PROTECTED_TERMS if t in self.text})

        aesthetic_guide = (
            "【改写审美守则】（防止『为降AI而制造新AI』）\n"
            "1. 只删除/调整AI痕迹，不替换语义：『显著』『研究』『验证』等学术词含义精确，禁止换成近义词\n"
            "   （危险替换示例：研究→探究、显著→可观、验证→佐证 均为语义漂移）。\n"
            "2. 学术术语（模型/算法/求解/本文/综上等）是数模论文的正常词汇，**不是**AI痕迹，不得删除。\n"
            "3. 改写后必须保持：数值不变、公式不变、句号边界完整、逻辑链完整。\n"
            "4. 宁愿保留少量AI味，也不要口语化降格（『要提醒的是』『总之』『搞』等禁止进入学术文本）。\n"
            "5. 改写后运行质量门禁复核：python tools/rewrite_quality_gate.py <原文> <改写后> \n"
            "6. 门禁未通过 → 回到人工修正，不得绕过。"
        )

        all_protected_hits = sorted({t for s in uniq for t in s.protected_terms})
        summary = (
            f"共 {len(self.sentences)} 句，发现 {len(uniq)} 处 AI 味问题。\n"
            f"按参考论文基线，目标：短句占比 54-82%、被动语态 <4.8%、连接词密度 4.2-12.3‰、长句 <7.7%。\n"
            f"问题句含学术术语：{all_protected_hits[:10] if all_protected_hits else '无（改写自由度较高）'}\n"
            f"注意：本工具只提供**改写方向**，不提供机械替换文本；"
            f"最终改写由人工完成并过质量门禁。"
        )
        return DeAiResult(
            total_sentences=len(self.sentences),
            issues_found=len(uniq),
            suggestions=[asdict(s) for s in uniq],
            summary=summary,
            protected_terms_hit=all_protected,
            aesthetic_guide=aesthetic_guide,
        )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="AI味改写建议工具 v1.0")
    parser.add_argument("input", help="输入文件路径或文本")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--output", help="输出文件路径")
    args = parser.parse_args()

    if os_path_is_file(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.input

    engine = DeAiWriter(text)
    result = engine.analyze()

    if args.json:
        out = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    else:
        lines = [result.summary, "", result.aesthetic_guide, ""]
        for i, s in enumerate(result.suggestions, 1):
            lines.append(f"[{i}] ({s['issue_type']}) {s['issue_detail']}")
            lines.append(f"    原文: {s['sentence']}")
            lines.append(f"    建议: {s['advice']}")
            if s.get("protected_terms"):
                lines.append(f"    注意: 本句含学术术语 {s['protected_terms']}，改写时不得替换/删除")
            if s.get("danger_swaps"):
                lines.append(f"    警告: 避免危险替换 {s['danger_swaps']}（语义漂移）")
            lines.append("")
        out = "\n".join(lines)

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"结果已保存到: {args.output}")
    else:
        print(out)


def os_path_is_file(p: str) -> bool:
    import os
    return os.path.isfile(p)


if __name__ == "__main__":
    main()
