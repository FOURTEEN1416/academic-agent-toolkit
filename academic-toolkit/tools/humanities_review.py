# -*- coding: utf-8 -*-
"""文本评估规则引擎（人文社科论文质检）

⛔ 本文件改编自开源项目 humanities-thesis-skill（作者 @ganzhi-black, MIT License,
   https://github.com/ganzhi-black/humanities-thesis-skill）的 scripts/lib/review_rules.py，
   规则逻辑原样复用，仅调整术语表加载路径并补充 CLI 入口。MIT 署名见
   skills/shared-scripts/NOTICE-humanities.md。

用确定性规则（正则匹配、术语表比对、格式模板检查）对生成的论文文本
进行校验。不依赖模型判断——模型自己检查自己等于没检查。

每条规则返回一个 Issue 对象，包含位置、严重程度和修改建议。

用法（CLI）：
    python humanities_review.py paper.md                  # 文本报告
    python humanities_review.py paper.md --format json    # JSON（供 Agent 解析）
    python humanities_review.py paper.md --severity error # 只看错误级
"""
from __future__ import annotations

import re
import os
import logging
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# 本文件是 academic-toolkit/tools/humanities_review.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = os.path.basename(os.sys.argv[0]).rsplit('.', 1)[0] + '.pyc'


class Severity(str, Enum):
    ERROR = 'error'
    WARNING = 'warning'
    INFO = 'info'


@dataclass
class Issue:
    rule: str
    severity: Severity
    message: str
    line: int = 0
    context: str = ''
    suggestion: str = ''

    def to_dict(self) -> dict:
        return {
            'rule': self.rule,
            'severity': self.severity.value,
            'message': self.message,
            'line': self.line,
            'context': self.context[:100] if self.context else '',
            'suggestion': self.suggestion,
        }


def check_fabricated_references(text: str) -> list[Issue]:
    """检测可能编造的文献引用"""
    issues = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        vague_cite = re.findall('(有学者|有研究者|有人|据研究)(指出|认为|发现|表明|提出)', line)
        for match in vague_cite:
            issues.append(Issue(rule='R1-01', severity=Severity.ERROR,
                                message='模糊引用：使用了「有学者指出」类表述但未给出具体文献',
                                line=i, context=line.strip()[:80],
                                suggestion='替换为具体的作者名+出处，或删除这个引用'))
        if '[待补充' in line or '[待查证' in line:
            issues.append(Issue(rule='R1-02', severity=Severity.INFO,
                                message='发现待补充占位符，提交前需要补充具体信息',
                                line=i, context=line.strip()[:80]))
        year_matches = re.findall('[（(]\\s*((?:19|20)\\d{2})\\s*[)）]', line)
        for year_str in year_matches:
            year = int(year_str)
            if year > 2026:
                issues.append(Issue(rule='R1-03', severity=Severity.ERROR,
                                    message=f'引用年份 {year} 超过当前年份，可能是编造的',
                                    line=i, context=line.strip()[:80]))
    return issues


def check_unsupported_claims(text: str) -> list[Issue]:
    """检测过度断言：缺少限定词的绝对化表述"""
    issues = []
    lines = text.split('\n')
    absolute_patterns = [
        ('毫无疑问', '建议改为「可以认为」或「有理由认为」'),
        ('众所周知', '建议改为「学界普遍认为」并附引用'),
        ('不言而喻', '学术论文中应当明确论证，而非诉诸不言而喻'),
        ('显而易见', '建议改为「从以上分析可以看出」'),
        ('必然', '建议改为「很可能」或「在很大程度上」，除非有充分论证'),
        ('完全(?:是|证明了|说明了)', '建议加入限定词，避免绝对化'),
        ('无可辩驳', '学术论文中应避免此类修辞'),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, suggestion in absolute_patterns:
            if re.search(pattern, line):
                issues.append(Issue(rule='R3-01', severity=Severity.WARNING,
                                    message=f'过度断言：使用了「{re.search(pattern, line).group()}」',
                                    line=i, context=line.strip()[:80], suggestion=suggestion))
    return issues


def _load_terminology_map() -> dict[str, list[str]]:
    """从术语对照表加载中文→英文映射"""
    term_map = {}
    _here = os.path.dirname(os.path.abspath(__file__))
    _candidates = [
        os.path.join(os.getcwd(), '_utils', 'humanities-terminology-bilingual.md'),
        os.path.join(_here, '..', 'skills', 'shared-scripts', 'humanities-terminology-bilingual.md'),
        os.path.join(_here, 'humanities-terminology-bilingual.md'),
        os.path.join(_here, '..', '..', 'references', 'terminology-bilingual.md'),
    ]
    term_file = next((p for p in _candidates if os.path.isfile(p)), None)
    if not term_file:
        return term_map
    try:
        with open(term_file, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if not line.startswith('|') or line.startswith('|---'):
                    continue
                cols = [c.strip() for c in line.split('|')]
                cols = [c for c in cols if c]
                if len(cols) >= 2:
                    zh = cols[0]
                    for term in re.split('[/／]', zh):
                        term = term.strip()
                        if term and len(term) >= 2 and term not in ('中文', '说明'):
                            term_map[term] = cols[1:]
    except OSError:
        pass
    return term_map


def check_terminology_consistency(text: str) -> list[Issue]:
    """检查术语使用是否一致"""
    issues = []
    term_map = _load_terminology_map()
    if not term_map:
        return issues

    synonym_groups = [
        ['赤裸生命', '裸命', '裸生命'],
        ['灵晕', '灵韵', '灵光'],
        ['延异', '延差', '分延'],
        ['规训', '训诫', '纪律'],
        ['操演性', '述行性', '展演性'],
        ['话语', '论述'],
        ['异托邦', '异质空间', '异质地方'],
        ['解域化', '去疆域化', '去辖域化'],
        ['询唤', '质询', '召唤'],
        ['主体化', '主体建构', '主体构成'],
    ]

    for group in synonym_groups:
        found_terms = []
        found_lines = {}
        lines = text.split('\n')
        for i, line in enumerate(lines, 1):
            for term in group:
                if term in line:
                    if term not in found_terms:
                        found_terms.append(term)
                    found_lines.setdefault(term, []).append(i)
        if len(found_terms) > 1:
            locations = '; '.join(
                f'「{t}」(第{",".join(str(l) for l in found_lines[t][:3])}行)' for t in found_terms)
            issues.append(Issue(rule='T-01', severity=Severity.WARNING,
                                message='术语不一致：同一概念使用了多个译名',
                                context=locations,
                                suggestion=f'建议统一使用「{found_terms[0]}」，或在首次出现时注明不同译法'))
    return issues


def check_citation_format(text: str) -> list[Issue]:
    """检查引注格式常见问题"""
    issues = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        if re.match('^[①②③④⑤⑥⑦⑧⑨⑩]\\s*$', line.strip()):
            issues.append(Issue(rule='F-01', severity=Severity.ERROR,
                                message='空脚注：脚注编号后没有内容',
                                line=i, context=line.strip()))
        if re.search('^\\[\\d+\\]\\s+\\S', line) and not re.search('\\[[MJDCNPS](?:/OL)?\\]', line):
            issues.append(Issue(rule='F-02', severity=Severity.WARNING,
                                message='参考文献条目可能缺少文献类型标识（如 [M] [J] [D]）',
                                line=i, context=line.strip()[:80],
                                suggestion='GB/T 7714 要求标注 [M]专著 [J]期刊 [D]学位论文 等'))
        is_ref_line = bool(re.match('^\\s*\\[\\d+\\]', line) or re.match('^\\s*[①②③④⑤⑥⑦⑧⑨⑩]', line))
        if not is_ref_line:
            line_no_parens = re.sub('[（(][^）)]*[）)]', '', line)
            if re.search('[\\u4e00-\\u9fff][,.;:?!]', line_no_parens):
                issues.append(Issue(rule='F-03', severity=Severity.WARNING,
                                    message='中文语境中使用了英文标点',
                                    line=i, context=line.strip()[:80],
                                    suggestion='中文语境应使用全角标点（，。；：？！）'))
    return issues


def check_heading_consistency(text: str) -> list[Issue]:
    """检查标题编号体系是否一致"""
    issues = []
    lines = text.split('\n')
    has_chinese_heading = False
    has_number_heading = False
    for line in lines:
        stripped = line.strip()
        if re.match('^第[一二三四五六七八九十]+[章节]', stripped):
            has_chinese_heading = True
        if re.match('^\\d+(\\.\\d+)*\\s+\\S', stripped):
            has_number_heading = True
    if has_chinese_heading and has_number_heading:
        issues.append(Issue(rule='F-04', severity=Severity.WARNING,
                            message='标题编号体系混用：同时使用了「第X章」和数字编号',
                            suggestion='选择一种体系并全文统一'))
    return issues


def check_register(text: str) -> list[Issue]:
    """检查学术语体问题"""
    issues = []
    lines = text.split('\n')
    informal_patterns = [
        ('其实', '学术论文中一般不用「其实」，建议改为「实际上」或直接陈述'),
        ('说白了', '过于口语化，建议删除或改为学术表述'),
        ('大家都知道', '建议改为「学界普遍认为」并附引用'),
        ('很明显', '建议用具体论证替代「很明显」'),
        ('当然了', '建议改为「诚然」或「固然」'),
        ('这个问题很有意思', '建议直接说明问题的学术意义'),
        ('笔者觉得', '建议改为「笔者认为」或「本文认为」'),
        ('总之就是', '建议改为「综上所述」或「概言之」'),
    ]
    for i, line in enumerate(lines, 1):
        for pattern, suggestion in informal_patterns:
            if re.search(pattern, line):
                issues.append(Issue(rule='S-01', severity=Severity.WARNING,
                                    message=f'语体问题：使用了口语化表述「{re.search(pattern, line).group()}」',
                                    line=i, context=line.strip()[:80], suggestion=suggestion))
    return issues


def check_self_reference(text: str) -> list[Issue]:
    """检查自称用法是否统一"""
    issues = []
    lines = text.split('\n')
    refs_found = {}
    for i, line in enumerate(lines, 1):
        for ref in ('笔者', '本文', '本研究', '我们'):
            if ref in line:
                refs_found.setdefault(ref, []).append(i)
        if re.search('我(?:认为|以为|将|的|在本|试图|倾向于|主张|发现)', line):
            refs_found.setdefault('我', []).append(i)
    if len(refs_found) > 2:
        terms = ', '.join(f'「{k}」' for k in refs_found)
        issues.append(Issue(rule='S-02', severity=Severity.WARNING,
                            message=f'自称用法不统一：同时使用了 {terms}',
                            suggestion='建议全文统一使用「本文」或「笔者」'))
    return issues


def check_structure(text: str) -> list[Issue]:
    """检查论文基本结构要素是否完整"""
    issues = []
    checks = [
        ('摘要', '摘\\s*要|Abstract', '论文缺少摘要'),
        ('关键词', '关键词|Keywords', '论文缺少关键词'),
        ('参考文献', '参考文献|References|Bibliography', '论文缺少参考文献'),
    ]
    for name, pattern, msg in checks:
        if not re.search(pattern, text):
            issues.append(Issue(rule='ST-01', severity=Severity.INFO,
                                message=msg,
                                suggestion=f'检查是否遗漏了{name}部分'))

    intro_section = ''
    lines = text.split('\n')
    in_intro = False
    for line in lines:
        if re.search('引言|绪论|导论|Introduction', line):
            in_intro = True
            continue
        if in_intro:
            if re.match('^(第[一二三]|[一二三]、|\\d+[\\s.])', line.strip()):
                break
            intro_section += line + '\n'
    if intro_section:
        thesis_indicators = [
            '本文论证', '本文认为', '本文试图', '本文旨在',
            '本研究认为', '笔者认为', '本文的核心论点',
        ]
        has_thesis = any(ind in intro_section for ind in thesis_indicators)
        if not has_thesis:
            issues.append(Issue(rule='ST-02', severity=Severity.WARNING,
                                message='引言中未发现明确的论点句',
                                suggestion='引言末尾应有一句明确的论点陈述（如「本文论证……」）'))
    return issues


_CONNECTORS = {
    '但', '却', '不过', '但是', '反之', '因为', '因此', '所以', '故而', '然而',
    '由于', '相反', '而且', '虽然', '之所以', '换言之', '正因为', '这表明', '这说明',
    '进一步', '不仅如此', '与之不同', '也就是说', '具体而言', '另一方面', '尽管如此',
    '由此出发', '相比之下', '这意味着', '在此基础上', '更重要的是', '之所以这样说',
    '从中可以看出', '值得注意的是', '更为关键的是', '这一点可以从', '可见', '由此可见',
}

_LISTING_SIGNALS = [
    '^同时[,，]', '^此外[,，]', '^另外[,，]', '^还有[,，]',
    '^也[,，]', '^并且[,，]', '^以及',
]


def check_argumentation_logic(text: str) -> list[Issue]:
    """检测论证逻辑断裂：句间/段间/章节间缺乏论证连接"""
    issues = []
    lines = text.split('\n')

    para_lines = []
    paragraphs = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            if para_lines:
                paragraphs.append(para_lines[:])
                para_lines.clear()
            continue
        if re.match('^(#|>|\\[|第[一二三四五六七八九十]+|[\\d]+\\.)', stripped):
            if para_lines:
                paragraphs.append(para_lines[:])
                para_lines.clear()
            continue
        para_lines.append((i, stripped))
    if para_lines:
        paragraphs.append(para_lines[:])

    for para in paragraphs:
        if len(para) < 4:
            continue
        sentences = []
        for line_no, line_text in para:
            for sent in re.split('[。！？]', line_text):
                sent = sent.strip()
                if len(sent) > 5:
                    sentences.append((line_no, sent))
        if len(sentences) < 4:
            continue
        consecutive_no_connector = 0
        max_streak = 0
        streak_start_line = 0
        for line_no, sent in sentences:
            has_connector = any(c in sent for c in _CONNECTORS)
            if has_connector:
                consecutive_no_connector = 0
                continue
            if consecutive_no_connector == 0:
                streak_start_line = line_no
            consecutive_no_connector += 1
            max_streak = max(max_streak, consecutive_no_connector)
        if max_streak >= 4:
            issues.append(Issue(rule='L-01', severity=Severity.WARNING,
                                message=f'段落中连续 {max_streak} 句缺少论证连接（第{streak_start_line}行附近）',
                                line=streak_start_line,
                                context=para[0][1][:60] + '...',
                                suggestion='检查这些句子之间是否缺少因果、转折、递进等逻辑关系。如果是在罗列观察，考虑用「这意味着……」「之所以……是因为……」等表述补充论证'))

    listing_streak = 0
    listing_start_line = 0
    for para in paragraphs:
        if not para:
            continue
        first_sent = para[0][1]
        is_listing = any(re.match(p, first_sent) for p in _LISTING_SIGNALS)
        if is_listing:
            if listing_streak == 0:
                listing_start_line = para[0][0]
            listing_streak += 1
        else:
            if listing_streak >= 3:
                issues.append(Issue(rule='L-02', severity=Severity.WARNING,
                                    message=f'连续 {listing_streak} 个段落以并列词开头（第{listing_start_line}行起）',
                                    line=listing_start_line,
                                    suggestion='并列结构适合罗列现象，但学术论文需要递进论证。考虑将这些段落重组为「提出观察→分析原因→得出推论」的递进结构'))
            listing_streak = 0
    if listing_streak >= 3:
        issues.append(Issue(rule='L-02', severity=Severity.WARNING,
                            message=f'连续 {listing_streak} 个段落以并列词开头（第{listing_start_line}行起）',
                            line=listing_start_line,
                            suggestion='并列结构适合罗列现象，但学术论文需要递进论证。考虑将这些段落重组为「提出观察→分析原因→得出推论」的递进结构'))

    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped:
            continue
        ends_with_quote = bool(re.search('[""」』][\\s。]*$', stripped))
        if ends_with_quote:
            next_content = ''
            for j in range(i, min(i + 3, len(lines))):
                nl = lines[j].strip() if j < len(lines) else ''
                if nl:
                    next_content = nl
                    break
            if next_content:
                starts_new_topic = bool(re.match('^(此外|同时|另外|与此同时|除此之外|值得一提的是|[「『])', next_content))
                if starts_new_topic:
                    issues.append(Issue(rule='L-03', severity=Severity.WARNING,
                                        message='引文后可能缺少分析：引用结束后直接跳到了新话题',
                                        line=i, context=stripped[:60],
                                        suggestion='引文之后应紧跟对引文的分析——这段引文说明了什么？它如何支撑你的论点？'))

    chapter_heading_lines = []
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if re.match('^(第[一二三四五六七八九十]+[章节]|#{1,3}\\s+\\d)', stripped):
            chapter_heading_lines.append(i)
    for idx, heading_line in enumerate(chapter_heading_lines):
        if idx == 0:
            continue
        first_para_start = ''
        for j in range(heading_line, min(heading_line + 5, len(lines))):
            if j < len(lines):
                nl = lines[j - 1].strip()
                if nl and not re.match('^(第|#|\\d+\\.)', nl):
                    first_para_start = nl
                    break
        if first_para_start:
            bad_starts = ['^[A-Z\\u4e00-\\u9fff]+（.*?）是', '^在\\d{4}年', '^关于.{2,6}的研究']
            for pattern in bad_starts:
                if re.match(pattern, first_para_start):
                    issues.append(Issue(rule='L-04', severity=Severity.INFO,
                                        message='章节开头可能缺少与上一章的逻辑衔接',
                                        line=heading_line, context=first_para_start[:60],
                                        suggestion='章节开头建议从上一章留下的问题或张力切入，而不是直接从背景介绍或理论定义开始'))
                    break
    return issues


def check_argumentation_depth(text: str) -> list[Issue]:
    """深层论证检查：预设前提未论证、因果链跳跃、叙述淹没论点、结尾堆砌"""
    issues = []
    lines = text.split('\n')
    for i, line in enumerate(lines, 1):
        stripped = line.strip()
        if not stripped or len(stripped) < 10:
            continue
        causal_premise_patterns = [
            ('(由于|因为|鉴于)(.{4,30})(并非|不是|并不|并未|未必是|绝非)', '前提中的否定性判断'),
            ('(由于|因为|鉴于)(.{2,15})(所认为的|所谓的|所理解的)', '前提中嵌入了主观判断'),
        ]
        for pattern, desc in causal_premise_patterns:
            m = re.search(pattern, stripped)
            if m:
                context_window = stripped[max(0, m.start() - 20):m.end() + 40]
                has_citation = bool(re.search('[①②③④⑤⑥⑦⑧⑨⑩]|\\[\\d+\\]|（.*?\\d{4}.*?）', context_window))
                if not has_citation:
                    issues.append(Issue(rule='L-05', severity=Severity.WARNING,
                                        message=f'因果前提可能未论证：{desc}，但未见引用或论证支撑',
                                        line=i, context=stripped[:80],
                                        suggestion='「由于/因为」引导的前提如果包含价值判断，需要先论证这个前提成立，再用它推导结论'))
                break
        sentences = re.split('[。！？]', stripped)
        for sent in sentences:
            sent = sent.strip()
            if len(sent) < 100:
                continue
            narrative_verbs = len(re.findall('(?:发生|出现|建立|成立|颁布|发动|开始|结束|到达|返回|出版|发表|签署|宣布|任命|组建|迁移|抵达|爆发|写道|记载|描述|讲述|描绘|记录|引述|转述|复述|设置|进入|离开|逃离|攻打|占领|投降|撤退)', sent))
            analytic_verbs = len(re.findall('(?:表明|说明|揭示|意味着|体现|反映|证明|论证|暗示|可见|因此|由此|换言之|之所以|正因为|由此可见|呈现出|构成了|指向了|折射出|回应了|挑战了|颠覆了)', sent))
            if narrative_verbs >= 4 and analytic_verbs == 0:
                issues.append(Issue(rule='L-06', severity=Severity.INFO,
                                    message='长句中叙述成分可能过多，缺少分析性表述',
                                    line=i, context=sent[:80] + '...',
                                    suggestion='考虑将叙事部分压缩，或在叙述后立即跟上分析（这意味着什么？为什么这个细节重要？）'))
        summary_starters = ['由此可见', '综上所述', '综上', '总之', '概言之', '可见']
        for starter in summary_starters:
            if starter in stripped:
                idx = stripped.index(starter)
                after_summary = stripped[idx:]
                enumeration_match = re.findall('[、]', after_summary)
                if len(enumeration_match) >= 4:
                    issues.append(Issue(rule='L-07', severity=Severity.WARNING,
                                        message=f'总结句中堆砌了 {len(enumeration_match) + 1} 个以上并列概念',
                                        line=i, context=after_summary[:80],
                                        suggestion='总结不应引入前文未充分展开的新概念。检查这些并列项是否都在前文得到了论证——如果没有，要么删去，要么补充论证'))
                break
        intensity_words = re.findall('(显然|极其|无疑|毋庸置疑|不言自明|必然地|确凿无疑)', stripped)
        for word in intensity_words:
            word_idx = stripped.index(word)
            surrounding = stripped[max(0, word_idx - 60):word_idx + 60]
            evidence_markers = len(re.findall('(不仅|而且|第一|第二|首先|其次|一方面|另一方面|例如|比如|根据|据)', surrounding))
            if evidence_markers < 2:
                issues.append(Issue(rule='L-08', severity=Severity.WARNING,
                                    message=f'强断言「{word}」附近未见充分的论据支撑',
                                    line=i, context=surrounding.strip()[:80],
                                    suggestion=f'「{word}」暗示结论不证自明，但学术论文中应当展示推理过程。建议删去强度词，或补充多重论据'))
    return issues


ALL_CHECKS = [
    check_fabricated_references,
    check_unsupported_claims,
    check_terminology_consistency,
    check_citation_format,
    check_heading_consistency,
    check_register,
    check_self_reference,
    check_structure,
    check_argumentation_logic,
    check_argumentation_depth,
]


def run_all_checks(text: str) -> list[Issue]:
    """执行所有检查规则，返回按严重程度排序的问题列表"""
    issues = []
    for check_fn in ALL_CHECKS:
        try:
            issues.extend(check_fn(text))
        except Exception as e:
            logger.warning('Review rule %s failed: %s', check_fn.__name__, e)

    severity_order = {Severity.ERROR: 0, Severity.WARNING: 1, Severity.INFO: 2}
    issues.sort(key=lambda x: (severity_order.get(x.severity, 9), x.line))
    return issues


import argparse
import sys
import json


def _read_input(path: str) -> str:
    if path == '-':
        return sys.stdin.read()
    with open(path, 'r', encoding='utf-8') as f:
        return f.read()


def review(text: str, min_severity: str = 'info') -> list:
    """评估文本，返回问题列表（供 Agent 以模块方式调用）。"""
    issues = run_all_checks(text)
    severity_order = {'error': 0, 'warning': 1, 'info': 2}
    threshold = severity_order.get(min_severity, 2)
    return [i for i in issues if severity_order.get(i.severity.value, 2) <= threshold]


def _render_text(issues: list, text: str) -> str:
    if not issues:
        return '✓ 未发现问题。\n'
    ec = sum(1 for i in issues if i.severity == Severity.ERROR)
    wc = sum(1 for i in issues if i.severity == Severity.WARNING)
    ic = sum(1 for i in issues if i.severity == Severity.INFO)
    lines = [
        f'评估完成：{ec} 个错误 / {wc} 个警告 / {ic} 个提示',
        f'文本总行数：{len(text.splitlines())}',
        '',
    ]
    icon = {Severity.INFO: 'ℹ [提示]', Severity.WARNING: '⚠ [警告]', Severity.ERROR: '✗ [错误]'}
    for it in issues:
        loc = f'第{it.line}行' if it.line else ''
        lines.append(f"{icon.get(it.severity, '?')} {it.rule} {loc}")
        lines.append(f'  {it.message}')
        if it.context:
            lines.append(f'  上下文：{it.context}')
        if it.suggestion:
            lines.append(f'  建议：{it.suggestion}')
        lines.append('')
    return '\n'.join(lines)


def _render_json(issues: list) -> str:
    return json.dumps({
        'total': len(issues),
        'errors': sum(1 for i in issues if i.severity == Severity.ERROR),
        'warnings': sum(1 for i in issues if i.severity == Severity.WARNING),
        'info': sum(1 for i in issues if i.severity == Severity.INFO),
        'issues': [i.to_dict() for i in issues],
    }, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='人文社科论文文本评估工具')
    parser.add_argument('input', help='待评估文件路径，或 - 表示 stdin')
    parser.add_argument('--format', choices=['text', 'json'], default='text', help='输出格式')
    parser.add_argument('--severity', choices=['error', 'warning', 'info'], default='info', help='最低显示级别')
    args = parser.parse_args()

    text = _read_input(args.input)
    issues = review(text, min_severity=args.severity)
    print(_render_json(issues) if args.format == 'json' else _render_text(issues, text))


if __name__ == '__main__':
    main()
