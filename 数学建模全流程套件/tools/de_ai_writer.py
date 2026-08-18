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


@dataclass
class FixSuggestion:
    sentence: str
    issue_type: str
    issue_detail: str
    advice: str
    position: int = 0


@dataclass
class DeAiResult:
    total_sentences: int
    issues_found: int
    suggestions: list
    summary: str


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
            for rule in TEMPLATE_PATTERNS:
                m = re.search(rule["pattern"], sent)
                if m:
                    suggestions.append(FixSuggestion(
                        sentence=sent[:60] + ("…" if len(sent) > 60 else ""),
                        issue_type="AI模板句",
                        issue_detail=f"命中「{rule['name']}」: {m.group(0)}",
                        advice=rule["advice"],
                        position=sent_start,
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
                    ))
            if len(sent) > LONG_SENT_THRESHOLD:
                suggestions.append(FixSuggestion(
                    sentence=sent[:60] + ("…" if len(sent) > 60 else ""),
                    issue_type="超长句",
                    issue_detail=f"句长 {len(sent)} 字（基线长句占比 <7.7%，阈值80字）",
                    advice="拆分为2-3个短句，保持人类写作的句长节奏：『A，B，C』→『A。B。C。』",
                    position=sent_start,
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

        summary = (
            f"共 {len(self.sentences)} 句，发现 {len(uniq)} 处 AI 味问题。\n"
            f"按参考论文基线，目标：短句占比 54-82%、被动语态 <4.8%、连接词密度 4.2-12.3‰、长句 <7.7%。\n"
            f"建议逐条人工改写，改写后可运行 tools/anti_ai_detector.py 复查。"
        )
        return DeAiResult(
            total_sentences=len(self.sentences),
            issues_found=len(uniq),
            suggestions=[asdict(s) for s in uniq],
            summary=summary,
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
        lines = [result.summary, ""]
        for i, s in enumerate(result.suggestions, 1):
            lines.append(f"[{i}] ({s['issue_type']}) {s['issue_detail']}")
            lines.append(f"    原文: {s['sentence']}")
            lines.append(f"    建议: {s['advice']}")
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
