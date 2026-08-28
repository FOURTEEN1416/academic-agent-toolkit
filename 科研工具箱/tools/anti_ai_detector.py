#!/usr/bin/env python3
"""
反AI特征检测工具 v2.0
基于多维特征分析框架 + 62篇获奖论文基线校准，检测中文学术文本的AI生成特征。

v2.0 升级（2026-08-17）：
- 新增基线校准层：加载 baseline/human_paper_baseline.json（20篇OCR可用获奖论文量化特征）
- 新增 8 个统计特征：突发性Burstiness、句长分段分布、连接词密度、被动语态占比、
  段落CV、压缩比、字符熵、AI模板词
- 每个特征按"人类基线区间"打分：区间内=人类（低分），偏离=AI（高分）
- 输出增加 statistical_scores（逐特征偏离度）供可视化

参考文献：
1. 安彤等.基于多维特征分析的AI生成期刊论文内容识别与应对策略研究.知识管理论坛,2025
2. Tian et al. GPTZero: Towards Detecting AI-Generated Text via Zero-Shot
   Distinguishing with Common n-gram Analysis. 2023 (perplexity/burstiness)
3. Solidjonov.Detecting AI-generated academic language.AI Ethics,2026
4. Su et al.Research on AI-generated Chinese text detection.aimspress,2025
5. C-ReD: A Comprehensive Chinese Benchmark.ACL Findings,2026
6. 全国大学生数学建模竞赛论文格式规范（2026年修订稿）

作者：数模全流程套件
日期：2026-08-17
"""

import re
import math
import json
import os
import sys
import zlib
from collections import Counter
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass, field, asdict


# ============================================================
# 常量定义
# ============================================================

# 基线文件路径（套件内）
BASELINE_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "..", "baseline", "human_paper_baseline.json"
)

# AI 高频模板词（中文数模场景）
# 来源：综述调研 + moways00001(58种模式) + humanize-chinese(20+类别) + wb-deai-writing-pro(12维)
AI_TEMPLATE_PHRASES = [
    # ===== 万能开头（公式化开头，12维#6） =====
    "随着", "近年来", "在当今", "随着科技的", "随着时代的", "在信息技术飞速发展",
    "在当今竞争激烈的", "在经济全球化的大背景下", "随着科技的飞速发展",
    "在数字化转型的浪潮中", "面对日益复杂的", "在瞬息万变的", "站在历史的十字路口",
    # ===== 强调拐杖词（P2） =====
    "值得注意的是", "需要指出的是", "需要强调的是", "毫无疑问", "不可忽视的是",
    "令人瞩目的是", "引人深思的是", "耐人寻味的是", "显而易见", "众所周知",
    "不难发现", "由此可见",
    # ===== 过渡词堆砌（P3） =====
    "与此同时", "不仅如此", "更重要的是", "更为关键的是", "值得一提的是",
    "进一步来说", "在此基础上", "从另一个角度来看", "除此之外",
    # ===== 元评论（P5） =====
    "总而言之", "综上所述", "总的来说", "通过以上分析我们可以看出",
    "下面将详细阐述", "以下分别论述", "本文将从以下几个方面展开分析",
    # ===== 模糊归因（P4） =====
    "业内人士指出", "有关专家表示", "市场普遍认为", "相关研究表明", "分析人士认为",
    # ===== AI味价值升华（空洞升华） =====
    "具有重要意义", "具有重要的现实意义", "具有一定的参考价值",
    "为...提供了新的思路", "为...提供了有力支撑", "为...奠定了坚实基础",
    "赋能", "助力", "推动...发展", "促进...发展", "彰显", "凸显", "深化",
    "开创性", "革命性", "颠覆性", "划时代", "里程碑式", "史无前例",
    # ===== 空洞强调（修饰堆叠，12维#9） =====
    "全方位", "多维度", "深层次", "系统性", "高质量", "深度融合", "协同增效",
    "降本增效", "底层逻辑", "闭环", "颗粒度", "抓手", "生态", "沉淀", "复盘",
    # ===== 公式化结尾（12维#7） =====
    "未来可期", "让我们拭目以待", "相信在不久的将来", "必将迎来更加美好的",
    # ===== 空洞强调 =====
    "非常", "十分", "极其", "充分", "有效", "显著", "大幅", "全面提升",
]

# AI 典型句式（公式化开头/结尾模式）
AI_SENTENCE_PATTERNS = [
    r"随着.{2,20}的发展",
    r"随着.{2,20}的不断",
    r"近年来.{2,15}日益",
    r"在.{2,15}的背景下",
    r"在.{2,15}的大背景下",
    r"在.{2,15}的时代背景下",
    r"在当今.{2,15}(?:环境|时代)",
    r"综上所述.{2,30}",
    r"总而言之.{2,30}",
    r"相信在不久的将来.{2,20}",
    r"让我们拭目以待.{2,20}",
    r"作为.{2,15}的重要组成部分",
    r"面对日益.{2,15}的",
    r"不仅.{2,20}更.{2,20}还.{2,20}",  # 排比滥用（12维#8）
]

# 排比/三项式模式（12维#8）
TRIAD_PATTERNS = [
    r"不仅.{2,20}，?更.{2,20}，?还.{2,20}",
    r"既.{2,15}又.{2,15}更.{2,15}",
    r"第一.{0,30}第二.{0,30}第三.{0,30}",
    r"一方面.{0,30}另一方面.{0,30}",
]

# 虚假客观/模糊归因（12维#4）
FAKE_OBJECTIVITY = [
    "研究表明", "专家认为", "业内人士指出", "普遍认为", "众所周知",
    "数据表明", "调查显示", "统计显示", "不难发现",
]

# 观点无棱角（12维#12）
NEUTRAL_ESCAPE = ["各有利弊", "因人而异", "见仁见智", "众说纷纭", "仁者见仁", "视情况而定"]

# 中文停用词（高频功能词，用于熵计算过滤）
ZH_STOP = set("的了在是有和我人这中大为上个国不他时来用要会出也年对自其已过到子说产新就那她它很")

# 被动语态标志（中文，模式匹配避免"由"字误报）
PASSIVE_PATTERNS = [
    r"由[\u4e00-\u9fff]{0,8}(?:进行|组成|构成|决定|提出|负责|控制|确定|给定)",
    r"受到[\u4e00-\u9fff]{0,8}",
    r"遭到[\u4e00-\u9fff]{0,8}",
    r"予以[\u4e00-\u9fff]{0,8}",
    r"加以[\u4e00-\u9fff]{0,8}",
    r"被[\u4e00-\u9fff]{1,6}(?:为|了|到|用于|视为|看作|定义为|所)",
]

# 学术连接词（检测连接词密度）
CONNECTORS = [
    "通过", "基于", "针对", "由于", "首先", "因此", "以及", "对于",
    "最后", "同时", "所以", "其次", "从而", "但是", "关于", "而且",
    "进而", "或者", "如果", "因为", "此外", "另外", "综上", "尽管",
]


@dataclass
class StatScore:
    """统计特征评分"""
    name: str
    value: float
    human_range: Tuple[float, float]
    ai_likelihood: float  # 0-1 越高越像AI
    detail: str = ""


@dataclass
class DetectionResult:
    """检测结果 v2"""
    overall_score: float
    risk_level: str
    dimensions: List = field(default_factory=list)
    statistical_scores: List[StatScore] = field(default_factory=list)
    statistical_features: Dict = field(default_factory=dict)
    summary: str = ""
    suggestions: List[str] = field(default_factory=list)
    baseline_note: str = ""


class AntiAIDetector:
    """反AI特征检测器 v2"""

    def __init__(self, text: str, language: str = "zh", baseline: Optional[dict] = None):
        self.text = text
        self.language = language
        self.baseline = baseline or self._load_baseline()
        self.sentences = self._split_sentences()
        self.paragraphs = [p.strip() for p in text.split("\n") if p.strip()]

    # ---------- 基础 ----------
    def _load_baseline(self) -> dict:
        if os.path.exists(BASELINE_PATH):
            try:
                with open(BASELINE_PATH, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _split_sentences(self) -> List[str]:
        """分割分句（含逗号，供突发性使用）"""
        if self.language == "zh":
            parts = re.split(r"[。！？；，、：\n]+", self.text)
        else:
            parts = re.split(r"[.!?,\n]+", self.text)
        return [p.strip() for p in parts if p.strip()]

    def _split_full_sentences(self) -> List[str]:
        """分割完整句（仅句号级，与参考论文基线同粒度）"""
        if self.language == "zh":
            parts = re.split(r"[。！？；\n]+", self.text)
        else:
            parts = re.split(r"[.!?\n]+", self.text)
        return [p.strip() for p in parts if p.strip()]

    def _zh_chars(self) -> int:
        return len(re.findall(r"[\u4e00-\u9fff]", self.text))

    def _conf_discount(self, n_min: int) -> float:
        """短文本置信度折扣：字数不足时统计层评分打折"""
        zh = self._zh_chars()
        if zh >= n_min:
            return 1.0
        return max(0.3, zh / n_min)

    def _feat(self, key: str) -> Optional[dict]:
        return self.baseline.get("features", {}).get(key)

    # ============================================================
    # 统计特征层（v2 新增，基线校准）
    # ============================================================

    def stat_burstiness(self) -> StatScore:
        """突发性：分句长度 CV。人类写作突发性高（CV大），AI文本句长均匀（CV小）"""
        if len(self.sentences) < 5:
            return StatScore("突发性Burstiness", 0, (0, 0), 0.0, "分句太少，无法评估")
        lens = [len(s) for s in self.sentences]
        mean = sum(lens) / len(lens)
        std = math.sqrt(sum((l - mean) ** 2 for l in lens) / len(lens))
        cv = std / mean if mean > 0 else 0
        # 分句（含逗号）CV 经验值：人类 0.60-1.10；AI 0.30-0.60
        if cv < 0.45:
            lik = min(1.0, 0.4 + (0.45 - cv) / 0.25 * 0.6)
            detail = f"分句CV={cv:.3f}，过于均匀，疑AI"
        elif cv < 0.60:
            lik = 0.35
            detail = f"分句CV={cv:.3f}，介于人类与AI之间"
        else:
            lik = max(0.0, (1.10 - cv) / 0.5 * 0.35)
            detail = f"分句CV={cv:.3f}，符合人类突发性特征"
        lik = round(lik * self._conf_discount(300), 3)
        return StatScore("突发性Burstiness", round(cv, 3), (0.60, 1.10), lik, detail)

    def stat_sentence_distribution(self) -> StatScore:
        """句长分段分布（句号级，与基线同粒度）：短<20 / 中20-50 / 长>50 占比 vs 基线区间"""
        full_sents = self._split_full_sentences()
        if len(full_sents) < 5:
            return StatScore("句长分布", 0, (0, 0), 0.0, "完整句太少")
        lens = [len(s) for s in full_sents]
        n = len(lens)
        short_pct = sum(1 for l in lens if l < 20) / n * 100
        mid_pct = sum(1 for l in lens if 20 <= l <= 50) / n * 100
        long_pct = sum(1 for l in lens if l > 50) / n * 100
        # 基线区间
        base_short = self._feat("short_sent_pct") or {"min": 54.4, "max": 82.3, "mean": 67.2}
        base_mid = self._feat("mid_sent_pct") or {"min": 17.4, "max": 42.3, "mean": 31.0}
        base_long = self._feat("long_sent_pct") or {"min": 0.0, "max": 7.7, "mean": 1.8}
        # 评分：短句占比偏离基线均值越远越像AI；长句>10%强烈疑AI
        range_short = max(base_short["max"] - base_short["min"], 1)
        range_mid = max(base_mid["max"] - base_mid["min"], 1)
        dev_short = abs(short_pct - base_short["mean"]) / range_short
        dev_mid = abs(mid_pct - base_mid["mean"]) / range_mid
        lik = min(1.0, max(dev_short, dev_mid) * 1.2)
        if long_pct > 10:
            lik = max(lik, min(1.0, 0.5 + (long_pct - 10) / 20 * 0.5))
        lik = round(lik * self._conf_discount(300), 3)
        detail = f"短句{short_pct:.1f}%/中句{mid_pct:.1f}%/长句{long_pct:.1f}%（基线 {base_short['mean']}%/{base_mid['mean']}%/{base_long['mean']}%）"
        return StatScore("句长分布", round(short_pct, 1), (base_short["min"], base_short["max"]),
                         lik, detail)

    def stat_connector_density(self) -> StatScore:
        """连接词密度（每千中文字符）vs 基线 4.2-12.3‰，短文本折扣"""
        chinese_chars = self._zh_chars()
        if chinese_chars < 100:
            return StatScore("连接词密度", 0, (0, 0), 0.0, "中文字符太少")
        cnt = sum(len(re.findall(re.escape(c), self.text)) for c in CONNECTORS)
        density = cnt * 1000 / chinese_chars
        base = self._feat("connector_density_per_1000") or {"mean": 8.74, "max": 12.3, "min": 4.2}
        if density > base["max"]:
            lik = min(1.0, 0.4 + (density - base["max"]) / 8 * 0.6)
            detail = f"连接词密度{density:.1f}‰，超出基线上限{base['max']}‰，疑AI"
        elif density < base["min"]:
            lik = 0.1
            detail = f"连接词密度{density:.1f}‰，低于基线下限{base['min']}‰"
        else:
            lik = 0.15
            detail = f"连接词密度{density:.1f}‰，在基线区间内"
        lik = round(lik * self._conf_discount(300), 3)
        return StatScore("连接词密度", round(density, 2), (base["min"], base["max"]), lik, detail)

    def stat_passive_voice(self) -> StatScore:
        """被动语态占比 vs 基线 0.2-4.8%（模式匹配，按句数归一化）"""
        if not self.sentences:
            return StatScore("被动语态", 0, (0, 0), 0.0, "无句子")
        cnt = sum(len(re.findall(p, self.text)) for p in PASSIVE_PATTERNS)
        pct = cnt / len(self.sentences) * 100
        base = self._feat("passive_pct") or {"mean": 1.36, "max": 4.8, "min": 0.2}
        if pct > base["max"]:
            lik = min(1.0, 0.4 + (pct - base["max"]) / 10 * 0.6)
            detail = f"被动语态{pct:.1f}%，超出基线上限{base['max']}%，疑AI"
        elif pct < base["min"]:
            lik = 0.05
            detail = f"被动语态{pct:.1f}%，低于基线下限"
        else:
            lik = 0.1
            detail = f"被动语态{pct:.1f}%，在基线区间内"
        lik = round(lik * self._conf_discount(300), 3)
        return StatScore("被动语态", round(pct, 2), (base["min"], base["max"]), lik, detail)

    def stat_paragraph_cv(self) -> StatScore:
        """段落长度 CV vs 基线（人类段落长短不一）"""
        if len(self.paragraphs) < 4:
            return StatScore("段落CV", 0, (0, 0), 0.0, "段落太少")
        lens = [len(p) for p in self.paragraphs]
        mean = sum(lens) / len(lens)
        if mean == 0:
            return StatScore("段落CV", 0, (0, 0), 0.0, "空段落")
        std = math.sqrt(sum((l - mean) ** 2 for l in lens) / len(lens))
        cv = std / mean
        if cv < 0.3:
            lik = min(1.0, 0.5 + (0.3 - cv) / 0.2 * 0.5)
            detail = f"段落CV={cv:.3f}，结构过于均匀，疑AI"
        elif cv < 0.5:
            lik = 0.3
            detail = f"段落CV={cv:.3f}，稍显均匀"
        else:
            lik = max(0.0, (1.0 - cv) / 0.5 * 0.3)
            detail = f"段落CV={cv:.3f}，符合人类段落节奏"
        return StatScore("段落CV", round(cv, 3), (0.5, 1.0), round(lik, 3), detail)

    def stat_compressibility(self) -> StatScore:
        """压缩比：zlib 压缩后大小/原文大小。AI文本词汇重复多→更可压缩"""
        if len(self.text) < 200:
            return StatScore("压缩比", 0, (0, 0), 0.0, "文本太短")
        raw = self.text.encode("utf-8")
        compressed = zlib.compress(raw)
        ratio = len(compressed) / len(raw)
        # 中文文本经验值：人类学术文本 0.55-0.75；AI 文本 0.40-0.58
        if ratio < 0.45:
            lik = min(1.0, 0.4 + (0.45 - ratio) / 0.1 * 0.6)
            detail = f"压缩比{ratio:.3f}，高度可压缩，疑AI（词汇重复多）"
        elif ratio < 0.58:
            lik = 0.35
            detail = f"压缩比{ratio:.3f}，介于人类与AI之间"
        else:
            lik = 0.1
            detail = f"压缩比{ratio:.3f}，符合人类词汇多样性"
        return StatScore("压缩比", round(ratio, 3), (0.58, 0.78), round(lik, 3), detail)

    def stat_entropy(self) -> StatScore:
        """字符熵（长文本条件特征）：<1000字时不可靠返回中性，≥1000字按 bigram 熵评估"""
        chars = re.findall(r"[\u4e00-\u9fff]", self.text)
        n = len(chars)
        if n < 1000:
            return StatScore("字符熵", 0, (0, 0), 0.15,
                             f"仅{n}字，短文本熵不可靠，中性分")
        bigrams = [chars[i] + chars[i + 1] for i in range(n - 1)]
        if not bigrams:
            return StatScore("字符熵", 0, (0, 0), 0.15, "无bigram")
        counter = Counter(bigrams)
        m = len(bigrams)
        entropy = -sum((c / m) * math.log2(c / m) for c in counter.values())
        # 2000字级中文 bigram 熵经验值：人类 9.6-10.2；AI 9.0-9.6
        if entropy < 9.0:
            lik = min(1.0, 0.4 + (9.0 - entropy) / 0.6 * 0.6)
            detail = f"bigram熵{entropy:.2f}bits，词汇选择集中，疑AI"
        elif entropy < 9.6:
            lik = 0.35
            detail = f"bigram熵{entropy:.2f}bits，介于两者之间"
        else:
            lik = 0.08
            detail = f"bigram熵{entropy:.2f}bits，符合人类词汇多样性"
        return StatScore("字符熵", round(entropy, 3), (9.6, 10.2), round(lik, 3), detail)

    def stat_ai_template(self) -> StatScore:
        """AI 模板词/句式命中数"""
        hits = []
        for phrase in AI_TEMPLATE_PHRASES:
            cnt = self.text.count(phrase)
            if cnt > 0:
                hits.append((phrase, cnt))
        for pattern in AI_SENTENCE_PATTERNS:
            found = re.findall(pattern, self.text)
            if found:
                hits.append((pattern[:12], len(found)))
        total = sum(c for _, c in hits)
        # AI模板词为逐词计数证据，不受文本长度折扣影响
        # 经验：人类论文 0-3 个；AI 文本 >8 个
        if total >= 8:
            lik = min(1.0, 0.55 + (total - 8) / 12 * 0.45)
            detail = f"命中 {total} 个AI模板词/句式: {[h[0] for h in hits[:5]]}"
        elif total >= 5:
            lik = 0.55
            detail = f"命中 {total} 个AI模板词/句式: {[h[0] for h in hits[:5]]}"
        elif total >= 3:
            lik = 0.3
            detail = f"命中 {total} 个AI模板词/句式: {[h[0] for h in hits[:3]]}"
        elif total >= 1:
            lik = 0.12
            detail = f"命中 {total} 个AI模板词/句式: {[h[0] for h in hits[:3]]}"
        else:
            lik = 0.0
            detail = "未命中AI模板词"
        return StatScore("AI模板词", float(total), (0, 3), round(lik, 3), detail)

    # ============================================================
    # 8维度框架层（保留 v1，评分校准到基线）
    # ============================================================

    def check_language(self) -> Dict:
        """语言表达：被动语态+元话语+句长变化+AI句式+排比+虚假客观（12维融合）"""
        evidence, suggestions = [], []
        # 元话语密度
        meta_markers = ["本文", "本研究", "本论文", "笔者", "我们", "作者",
                        "需要指出的是", "值得注意的是", "如前所述", "具体而言", "换言之"]
        meta_cnt = sum(self.text.count(m) for m in meta_markers)
        meta_density = meta_cnt / max(len(self.sentences), 1)
        score = 0.0
        if meta_density > 0.45:
            evidence.append(f"元话语密度偏高 ({meta_density:.2f}/句)")
            score += 0.2
        # 模糊限定词
        hedges = ["可能", "或许", "大概", "似乎", "一定程度上", "一般来说", "通常情况下"]
        hedge_cnt = sum(self.text.count(h) for h in hedges)
        if hedge_cnt / max(len(self.sentences), 1) > 0.25:
            evidence.append(f"模糊限定词偏多 ({hedge_cnt}处)")
            score += 0.15
        # AI典型句式
        pat_cnt = sum(len(re.findall(p, self.text)) for p in AI_SENTENCE_PATTERNS)
        if pat_cnt > 3:
            evidence.append(f"发现 {pat_cnt} 处AI典型句式开头")
            score += 0.3
        elif pat_cnt > 0:
            score += 0.1
        # 排比/三项式滥用（12维#8）
        triad_cnt = sum(len(re.findall(p, self.text)) for p in TRIAD_PATTERNS)
        if triad_cnt > 2:
            evidence.append(f"排比/三项式结构 {triad_cnt} 处，机械对仗")
            score += 0.2
        elif triad_cnt > 0:
            score += 0.08
        # 虚假客观/模糊归因（12维#4）
        fake_cnt = sum(self.text.count(f) for f in FAKE_OBJECTIVITY)
        if fake_cnt > 3:
            evidence.append(f"模糊归因/虚假客观表述 {fake_cnt} 处（如「研究表明」无出处）")
            score += 0.2
        # 观点无棱角（12维#12）
        neutral_cnt = sum(self.text.count(n) for n in NEUTRAL_ESCAPE)
        if neutral_cnt > 2:
            evidence.append(f"和稀泥式表述 {neutral_cnt} 处（「各有利弊」等）")
            score += 0.15
        # 公式化结尾（12维#7）
        ending_cnt = sum(self.text.count(e) for e in ["未来可期", "拭目以待", "相信在不久的将来", "必将迎来"])
        if ending_cnt > 0:
            evidence.append(f"公式化结尾 {ending_cnt} 处")
            score += 0.15
        # 结合统计层的被动语态
        passive_score = self.stat_passive_voice()
        if passive_score.ai_likelihood > 0.4:
            evidence.append(passive_score.detail)
            score += 0.15
        score = max(0, min(1, score))
        if score > 0.4:
            suggestions.append("减少被动语态与元话语堆砌")
            suggestions.append("打破AI典型句式开头（如「随着…的发展」）")
            suggestions.append("删除无出处的「研究表明/专家认为」，排比只留最强一组")
        return {"name": "语言表达", "name_en": "Language", "score": round(score, 3),
                "confidence": 0.78, "evidence": evidence, "suggestions": suggestions}

    def check_structure(self) -> Dict:
        """结构框架：段落CV+标题规整度"""
        evidence, suggestions = [], []
        score = 0.0
        cv = self.stat_paragraph_cv()
        if cv.ai_likelihood > 0.5:
            evidence.append(cv.detail)
            score += 0.3
        headings = re.findall(r"^[一二三四五六七八九十]+[、.]\s*.+$", self.text, re.MULTILINE)
        if len(headings) > 12:
            evidence.append(f"章节标题过多 ({len(headings)}个)，结构过于规整")
            score += 0.2
        # 段落长度分布
        if self.paragraphs:
            lens = [len(p) for p in self.paragraphs]
            mean = sum(lens) / len(lens)
            if mean > 600 and len(self.paragraphs) < 8:
                evidence.append("段落过少且过长，AI分段特征")
                score += 0.2
        score = max(0, min(1, score))
        if score > 0.3:
            suggestions.append("调整段落长度，形成人类写作的长短节奏")
        return {"name": "结构框架", "name_en": "Structure", "score": round(score, 3),
                "confidence": 0.65, "evidence": evidence, "suggestions": suggestions}

    def check_logic(self) -> Dict:
        """逻辑关系：连接词密度校准"""
        evidence, suggestions = [], []
        score = 0.0
        conn = self.stat_connector_density()
        if conn.ai_likelihood > 0.4:
            evidence.append(conn.detail)
            score += 0.3
        # 模板化连接词序列（首先…其次…再次…最后）
        seq = re.findall(r"首先.{0,20}其次.{0,20}再次.{0,20}最后", self.text)
        if seq:
            evidence.append(f"发现 {len(seq)} 处「首先/其次/再次/最后」模板化序列")
            score += 0.3
        # 因果对缺乏（连接词多但逻辑松散）
        causal = re.findall(r"因为.{0,30}所以|由于.{0,30}因此|如果.{0,30}那么", self.text)
        conn_cnt = sum(len(re.findall(re.escape(c), self.text)) for c in CONNECTORS)
        if conn_cnt > 40 and len(causal) < 2:
            evidence.append("连接词多但显式因果结构少，逻辑松散")
            score += 0.2
        score = max(0, min(1, score))
        if score > 0.3:
            suggestions.append("减少模板化连接词序列，用内容本身衔接")
        return {"name": "逻辑关系", "name_en": "Logic", "score": round(score, 3),
                "confidence": 0.68, "evidence": evidence, "suggestions": suggestions}

    def check_citations(self) -> Dict:
        """引文特征"""
        evidence, suggestions = [], []
        score = 0.0
        citations = re.findall(r"\[[\d,\s]+\]", self.text)
        ref_sections = re.findall(r"参考文献|references|bibliography", self.text, re.IGNORECASE)
        if len(citations) == 0 and len(ref_sections) == 0:
            evidence.append("未发现标准引用标记")
            score += 0.3
        consecutive = re.findall(r"\[\d+\]\[\d+\]\[\d+\]", self.text)
        if consecutive:
            evidence.append(f"连续引用 {len(consecutive)} 处，疑似AI堆砌引用")
            score += 0.4
        score = max(0, min(1, score))
        if score > 0.5:
            suggestions.append("补充规范参考文献，删除无对应条目的引用")
        return {"name": "引文特征", "name_en": "Citations", "score": round(score, 3),
                "confidence": 0.7, "evidence": evidence, "suggestions": suggestions}

    def check_data(self) -> Dict:
        """数据特征"""
        evidence, suggestions = [], []
        score = 0.0
        numbers = re.findall(r"\d+\.?\d*", self.text)
        density = len(numbers) / max(len(self.text), 1)
        if density < 0.004:
            evidence.append(f"数字密度过低 ({density:.4f})")
            score += 0.2
        data_sources = re.findall(r"数据来源|数据来自|data source|数据集|样本量|样本数|实验数据", self.text, re.IGNORECASE)
        if not data_sources:
            evidence.append("未发现数据来源描述")
            score += 0.25
        percentages = re.findall(r"\d+\.?\d*%", self.text)
        if not percentages:
            evidence.append("缺乏具体数值结果（百分比等）")
            score += 0.2
        score = max(0, min(1, score))
        if score > 0.4:
            suggestions.append("补充数据来源、样本量与具体数值结果")
        return {"name": "数据特征", "name_en": "Data", "score": round(score, 3),
                "confidence": 0.62, "evidence": evidence, "suggestions": suggestions}

    def check_viewpoints(self) -> Dict:
        """观点结论"""
        evidence, suggestions = [], []
        score = 0.0
        purpose = re.findall(r"本文.{0,10}(?:旨在|目的|研究|探讨|分析|解决|提出)", self.text)
        if not purpose:
            evidence.append("未发现明确研究目的陈述")
            score += 0.2
        absolute = re.findall(r"证明了|证实了|彻底|完全解决了|最优化", self.text)
        if len(absolute) > 2:
            evidence.append(f"发现 {len(absolute)} 处绝对化表述")
            score += 0.25
        limitations = re.findall(r"局限性|不足|有待|需要进一步|未来研究", self.text)
        if not limitations:
            evidence.append("未发现研究局限性讨论")
            score += 0.2
        score = max(0, min(1, score))
        if score > 0.4:
            suggestions.append("增加研究局限性与未来展望讨论")
        return {"name": "观点结论", "name_en": "Viewpoints", "score": round(score, 3),
                "confidence": 0.65, "evidence": evidence, "suggestions": suggestions}

    def check_concepts(self) -> Dict:
        """概念阐释"""
        evidence, suggestions = [], []
        score = 0.0
        formulas = re.findall(r"[=$∑∫∂√±∞≈≠≤≥Σ∏]", self.text)
        var_defs = re.findall(r"(?:其中|式中|这里).{0,15}(?:表示|代表|为|是)", self.text)
        if formulas and not var_defs:
            evidence.append("有公式但缺乏变量定义")
            score += 0.3
        explanations = re.findall(r"(?:所谓|即|是指|定义为|指的是)", self.text)
        if not explanations:
            evidence.append("关键概念缺乏定义性说明")
            score += 0.15
        score = max(0, min(1, score))
        if score > 0.3:
            suggestions.append("为公式变量提供「其中…表示…」说明")
        return {"name": "概念阐释", "name_en": "Concepts", "score": round(score, 3),
                "confidence": 0.6, "evidence": evidence, "suggestions": suggestions}

    def check_consistency(self) -> Dict:
        """内容一致性"""
        evidence, suggestions = [], []
        score = 0.0
        # 术语重复定义检测
        defs = re.findall(r"(?:所谓|即|定义为|含义是)", self.text)
        if len(defs) > 4:
            evidence.append(f"术语定义出现 {len(defs)} 次，疑似重复定义")
            score += 0.2
        # 数字引用一致性（同一数字前后不一致——基础检查）
        nums = [n for n in re.findall(r"\d{2,4}\.\d+", self.text)]
        if len(nums) > 5:
            dup = {n: c for n, c in Counter(nums).items() if c > 1}
            if len(dup) > 3:
                evidence.append(f"多个数值重复出现 {list(dup.keys())[:3]}，需核对一致性")
                score += 0.2
        score = max(0, min(1, score))
        return {"name": "内容一致性", "name_en": "Consistency", "score": round(score, 3),
                "confidence": 0.5, "evidence": evidence, "suggestions": suggestions}

    # ============================================================
    # 综合检测
    # ============================================================

    def detect(self) -> DetectionResult:
        # 统计特征层
        stat_scores = [
            self.stat_burstiness(),
            self.stat_sentence_distribution(),
            self.stat_connector_density(),
            self.stat_passive_voice(),
            self.stat_paragraph_cv(),
            self.stat_compressibility(),
            self.stat_entropy(),
            self.stat_ai_template(),
        ]

        # 8维度框架层
        dimensions = [
            self.check_citations(),
            self.check_data(),
            self.check_viewpoints(),
            self.check_structure(),
            self.check_logic(),
            self.check_consistency(),
            self.check_concepts(),
            self.check_language(),
        ]

        # 统计特征 → 常规特征（JSON 序列化）
        stat_scores_plain = [
            {
                "name": s.name, "value": s.value,
                "human_range": [s.human_range[0], s.human_range[1]],
                "ai_likelihood": s.ai_likelihood, "detail": s.detail,
            }
            for s in stat_scores
        ]

        # 综合评分：维度层 60% + 统计层 40%
        dim_weights = {"Citations": 0.08, "Data": 0.10, "Viewpoints": 0.11, "Structure": 0.11,
                       "Logic": 0.12, "Consistency": 0.08, "Concepts": 0.10, "Language": 0.30}
        dim_score = sum(d["score"] * dim_weights.get(d["name_en"], 0.12) for d in dimensions)
        stat_score = sum(s.ai_likelihood for s in stat_scores) / len(stat_scores) if stat_scores else 0

        overall = 0.6 * dim_score + 0.4 * stat_score
        overall = max(0, min(1, overall))

        if overall < 0.25:
            risk = "low"
        elif overall < 0.40:
            risk = "medium"
        elif overall < 0.60:
            risk = "high"
        else:
            risk = "critical"

        # 建议汇总（按统计层 ai_likelihood 排序取前4）
        suggestions = []
        for s in sorted(stat_scores, key=lambda x: x.ai_likelihood, reverse=True):
            if s.ai_likelihood >= 0.4:
                suggestions.append(f"[{s.name}] {s.detail}")
        for d in dimensions:
            if d["score"] > 0.4:
                suggestions.extend(d["suggestions"][:1])

        # 摘要
        risk_cn = {"low": "低风险", "medium": "中等风险", "high": "高风险", "critical": "极高风险"}
        worst = max(stat_scores, key=lambda s: s.ai_likelihood)
        summary = (
            f"反AI特征检测摘要 v2\n{'='*56}\n"
            f"综合风险: {risk_cn[risk]} ({overall:.2%})\n"
            f"统计特征层: {stat_score:.2%} | 维度层: {dim_score:.2%}\n"
            f"最可疑特征: {worst.name} ({worst.detail})\n\n"
            f"统计特征对比:\n"
        )
        for s in stat_scores:
            bar = "█" * int(s.ai_likelihood * 20) + "░" * (20 - int(s.ai_likelihood * 20))
            summary += f"  {s.name:12s} {bar} {s.ai_likelihood:.2%}\n"

        baseline_note = ""
        if self.baseline:
            n = self.baseline.get("paper_count", 20)
            baseline_note = f"基线: {n} 篇获奖论文量化特征校准 (baseline/human_paper_baseline.json)"

        return DetectionResult(
            overall_score=round(overall, 4),
            risk_level=risk,
            dimensions=dimensions,
            statistical_scores=stat_scores_plain,
            statistical_features=self._extract_features(),
            summary=summary,
            suggestions=suggestions[:6],
            baseline_note=baseline_note,
        )

    def _extract_features(self) -> Dict:
        feats = {}
        feats["total_chars"] = len(self.text)
        feats["chinese_chars"] = len(re.findall(r"[\u4e00-\u9fff]", self.text))
        feats["english_words"] = len(re.findall(r"[a-zA-Z]+", self.text))
        feats["sentence_count"] = len(self.sentences)
        feats["paragraph_count"] = len(self.paragraphs)
        feats["comma_count"] = self.text.count("，")
        feats["period_count"] = self.text.count("。")
        feats["semicolon_count"] = self.text.count("；")
        feats["dunhao_count"] = self.text.count("、")
        feats["formula_count"] = len(re.findall(r"[=$∑∫∂√±∞≈≠≤≥Σ∏]", self.text))
        feats["reference_count"] = len(re.findall(r"\[\d+\]", self.text))
        return feats


def main():
    import argparse

    parser = argparse.ArgumentParser(description="反AI特征检测工具 v2.0（基线校准版）")
    parser.add_argument("input", help="输入文件路径或文本")
    parser.add_argument("--lang", default="zh", choices=["zh", "en"], help="语言 (default: zh)")
    parser.add_argument("--json", action="store_true", help="输出JSON格式")
    parser.add_argument("--output", help="输出文件路径")
    parser.add_argument("--no-baseline", action="store_true", help="不使用基线校准")

    args = parser.parse_args()

    if os.path.isfile(args.input):
        with open(args.input, "r", encoding="utf-8") as f:
            text = f.read()
    else:
        text = args.input

    baseline = None if args.no_baseline else None  # 默认自动加载
    detector = AntiAIDetector(text, args.lang, baseline=baseline)
    result = detector.detect()

    if args.json:
        out = json.dumps(asdict(result), ensure_ascii=False, indent=2)
    else:
        out = result.summary

    if args.output:
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(out)
        print(f"结果已保存到: {args.output}")
    else:
        print(out)

    return result


if __name__ == "__main__":
    main()
