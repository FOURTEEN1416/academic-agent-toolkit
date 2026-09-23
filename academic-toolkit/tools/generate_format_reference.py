# -*- coding: utf-8 -*-
"""统一的「Markdown 格式自检对照表」生成器。

目的：给 `docx-format-check` skill 提供工作流相关的、人类可读的格式参考，
让 LLM 在自检时知道"标题字号该多少 / 章节怎么排 / 题注什么样 / 公式怎么编号"。

数据来源（按优先级 fallback）：
  1. 派生：从一份完整的 .docx 论文样本派生（最准，但需要样本）
     - 用 `derive_reference_from_docx.py` 实现，已有
  2. 内置：从 `tools/docx_style_profiles/*.json` 读样式参数 + 内置章节骨架
     - 这是兜底链路，覆盖所有工作流

输出：`reference_structure_<workflow>.md`（写到工作区根目录或固定位置）

用法：
    python generate_format_reference.py --workflow comp_cumcm --workspace . --out _reference_structure.md
    python generate_format_reference.py --workflow course_paper --workspace . --out _reference_structure.md
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Optional

# 本文件是 academic-toolkit/tools/generate_format_reference.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'

_PROFILE_BY_WORKFLOW = {'comp_cumcm': 'competition_zh.json',
 'comp_huawei': 'competition_zh.json',
 'comp_apmcm_zh': 'competition_zh.json',
 'comp_mathorcup': 'competition_zh.json',
 'comp_huazhong': 'competition_zh.json',
 'comp_huadong': 'competition_zh.json',
 'comp_wuyi': 'competition_zh.json',
 'comp_shuwei': 'competition_zh.json',
 'comp_zhongqing': 'competition_zh.json',
 'comp_yangtze': 'competition_zh.json',
 'comp_diangong': 'competition_zh.json',
 'comp_shenzhen': 'competition_zh.json',
 'comp_huashu': 'competition_zh.json',
 'comp_tianfu': 'competition_zh.json',
 'comp_liaoning': 'competition_zh.json',
 'comp_teddy': 'competition_zh.json',
 'comp_certcup': 'competition_zh.json',
 'comp_stats': 'competition_zh.json',
 'comp_mcm': 'competition_en.json',
 'comp_apmcm': 'competition_en.json',
 'comp_certcup_en': 'competition_en.json',
 'comp_shuwei_en': 'competition_en.json',
 'thesis_proposal': 'thesis_proposal.json',
 'literature_review': 'literature_review.json',
 'course_paper': 'course_paper.json',
 'course_report': 'course_report.json',
 'paper_writing': 'default_cn_thesis.json',
 'paper_writing_zh': 'default_cn_thesis.json',
 'paper_from_assets': 'default_cn_thesis.json',
 'full_pipeline': 'default_cn_thesis.json',
 'nature_writing': 'default_cn_thesis.json'}

_OUTLINE_BY_WORKFLOW = {'competition_zh': [(1, '论文题目'),
                    (2, '摘要'),
                    ('p', '**关键词**：xxx, yyy, zzz'),
                    (2, '一、问题重述（含问题背景与待解决的问题）'),
                    (2, '二、问题分析'),
                    (2, '三、模型假设与符号说明'),
                    (3, '3.1 模型假设'),
                    (3, '3.2 符号说明'),
                    (2, '四、模型建立与求解'),
                    (3, '4.1 问题一：xxx 模型'),
                    (3, '4.2 问题二：xxx 模型'),
                    (2, '五、模型评价（优缺点 / 推广 / 灵敏度）'),
                    (2, '参考文献'),
                    (2, '附录（可选）')],
 'competition_en': [(1, 'Paper Title'),
                    (2, 'Summary'),
                    ('p', '**Keywords**: xxx, yyy, zzz'),
                    (2, '1. Introduction'),
                    (3, '1.1 Background'),
                    (3, '1.2 Problem Restatement'),
                    (3, '1.3 Our Work'),
                    (2, '2. Assumptions and Notations'),
                    (2, '3. Model Construction'),
                    (3, '3.1 Model for Sub-problem 1'),
                    (3, '3.2 Model for Sub-problem 2'),
                    (2, '4. Results and Sensitivity Analysis'),
                    (2, '5. Strengths and Weaknesses'),
                    (2, 'References'),
                    (2, 'Appendix (optional)')],
 'thesis_proposal': [(1, '开题报告题目'),
                     (2, '一、研究背景与意义'),
                     (3, '1.1 研究背景'),
                     (3, '1.2 研究意义'),
                     (2, '二、国内外研究现状'),
                     (3, '2.1 国外研究现状'),
                     (3, '2.2 国内研究现状'),
                     (3, '2.3 研究述评'),
                     (2, '三、研究内容与目标'),
                     (3, '3.1 研究内容'),
                     (3, '3.2 研究目标'),
                     (3, '3.3 拟解决的关键问题'),
                     (2, '四、研究方法与技术路线'),
                     (2, '五、进度安排与预期成果'),
                     (2, '参考文献')],
 'literature_review': [(1, '文献综述题目'),
                       (2, '摘要'),
                       ('p', '**关键词**：xxx, yyy, zzz'),
                       (2, '一、引言'),
                       (2, '二、研究主题分类'),
                       (3, '2.1 主题 A：xxx'),
                       (3, '2.2 主题 B：xxx'),
                       (2, '三、方法对比'),
                       (2, '四、研究趋势与未来方向'),
                       (2, '五、结论'),
                       (2, '参考文献')],
 'course_paper': [(1, '课程论文题目'),
                  (2, '摘要'),
                  ('p', '**关键词**：xxx, yyy, zzz'),
                  (2, '一、引言'),
                  (2, '二、文献综述（可选）'),
                  (2, '三、研究方法'),
                  (2, '四、实验与分析'),
                  (2, '五、结论'),
                  (2, '参考文献')],
 'course_report': [(1, '课程报告题目'),
                   (2, '一、课程背景与学习目标'),
                   (2, '二、主要学习内容'),
                   (3, '2.1 模块/主题 A'),
                   (3, '2.2 模块/主题 B'),
                   (2, '三、实践与体会'),
                   (2, '四、收获与反思'),
                   (2, '五、改进建议'),
                   (2, '参考文献（如有）')],
 'default_cn_thesis': [(1, '论文题目'),
                       (2, '摘要'),
                       ('p', '**关键词**：xxx, yyy, zzz'),
                       (2, '一、引言'),
                       (2, '二、相关工作'),
                       (2, '三、方法'),
                       (2, '四、实验'),
                       (2, '五、结论'),
                       (2, '参考文献'),
                       (2, '附录（可选）')]}

_SUMMARY_BY_WORKFLOW = {'competition_zh': '数学建模竞赛中文论文（对标 cumcmthesis.cls）：A4 纸 25mm 边距，正文宋体小四 12pt 1.5 倍行距，章节用「一、二、三、」中文序号。',
 'competition_en': 'Mathematical Contest in Modeling (English): A4 paper, body 12pt double-line, sections '
                   'numbered with Arabic numerals.',
 'thesis_proposal': '研究生开题报告：A4 纸左 30mm 其余 25mm 边距，正文宋体小四 12pt 1.5 倍行距，含国内外研究现状/技术路线/进度安排。',
 'literature_review': '文献综述：A4 纸 25mm 边距，正文宋体小四 12pt 1.5 倍行距，按主题分类组织、突出方法对比与趋势分析。',
 'course_paper': '课程论文：A4 纸 25mm 边距，正文宋体小四 12pt 1.25 倍行距，结构精简（引言/方法/实验/结论），8000-15000 字。',
 'course_report': '课程报告：A4 纸 25mm 边距，正文宋体小四 12pt 1.25 倍行距，强调学习内容与体会，3000-8000 字。',
 'default_cn_thesis': '通用中文学术论文：A4 纸 25mm 边距，正文宋体小四 12pt 1.5 倍行距，章节结构灵活。'}



def _profiles_dir() -> Path:
    '''样式 profile 目录解析（2026-09-23 v2.0：原 tools/docx_style_profiles/ 已迁
    third_party/docx-style-profiles/，故按候选列表探测，兼容两种布局）。'''
    base = Path(__file__).resolve().parent
    candidates = [
        base / 'docx_style_profiles',
        base.parent / 'third_party' / 'docx-style-profiles',
    ]
    for c in candidates:
        if c.is_dir():
            return c
    return candidates[0]


def _load_profile(profile_name: str) -> dict[str, Any]:
    """从 tools/docx_style_profiles/<name> 加载 profile JSON"""
    p = _profiles_dir() / profile_name
    if not p.exists():
        raise FileNotFoundError(f'profile 不存在：{p}')
    return json.loads(p.read_text(encoding='utf-8'))


def _resolve_profile_and_outline_kind(workflow: str) -> tuple[str, str, dict[str, Any]]:
    """根据工作流名解析（profile 文件名, outline kind, profile dict）"""
    profile_name = _PROFILE_BY_WORKFLOW.get(workflow, 'default_cn_thesis.json')
    outline_kind = profile_name.replace('.json', '')
    try:
        profile = _load_profile(profile_name)
    except FileNotFoundError:
        profile = _load_profile('default_cn_thesis.json')
        outline_kind = 'default_cn_thesis'
    return profile_name, outline_kind, profile


def _outline_to_md(outline: list) -> str:
    """章节骨架 list 转 markdown 显示，给特殊语义加注释。

    每条是 (level, label)：
      - level 是整数 1-6 → markdown 标题层级
      - level 是 'p' → 普通段落（不加 #）
    """
    lines = []
    for level, label in outline:
        if level == 'p':
            lines.append(f'  {label}    ← ⚠ 普通段落（不是 heading），引擎自动用黑体加粗标签')
            continue
        prefix = '  ' * (level - 1) + '#' * level + ' '
        suffix = ''
        norm = label.strip().lower()
        if norm == '摘要' or norm == 'abstract' or norm == 'summary':
            suffix = '  ← ⚠ 自动居中加粗（引擎特殊路径，必须正好是「摘要」/「Abstract」/「Summary」）'
        lines.append(f'{prefix}{label}（H{level}）{suffix}')
    return '\n'.join(lines)


def build_reference_md(workflow: str, prefer_derived: Optional[Path] = None) -> str:
    """生成对照表 markdown。

    ⛔ 字段映射的真相（与渲染引擎实际行为一致）：
      - markdown `# X` (第一次出现) → `title.font_size_pt`，居中加粗（论文题目）
      - markdown `## 摘要` / `## Abstract` → 走特殊的 `abstract` 路径，居中加粗
      - markdown `## X`（其它） → `headings.level2_pt`，按 `level2_alignment` 对齐
      - markdown `### X` → `headings.level3_pt`
      - markdown `#### X` → `headings.level4_pt`（缺失则 fallback 上一级 -1pt）
      - `**关键词**：xxx` → 走 `keywordsPara`，黑体加粗标签
      注：`headings.level1_pt` 在正常论文里基本不被用到（# 只出现一次走 title），
          只有当用户写多个 # 时才会落到 level1_pt。

    Args:
        workflow: 工作流名（如 'comp_cumcm' / 'course_paper'）
        prefer_derived: 可选，已派生的 reference_paper_general.json 路径
                        ⛔ 派生 profile 不会覆盖工作流自己定义的字段，只补充缺失字段。
    """
    profile_name, outline_kind, profile = _resolve_profile_and_outline_kind(workflow)
    derived = None
    if prefer_derived and prefer_derived.exists():
        try:
            derived = json.loads(prefer_derived.read_text(encoding='utf-8'))
        except Exception:
            derived = None

    def _merge(workflow_dict: dict, derived_dict: Optional[dict], keys: list[str]) -> dict:
        out = dict(workflow_dict)
        if derived_dict:
            for k in keys:
                if k not in out and k in derived_dict:
                    out[k] = derived_dict[k]
        return out

    page = _merge(profile.get('page', {}), derived.get('page') if derived else None,
                  ['size', 'margin_top_cm', 'margin_bottom_cm', 'margin_left_cm', 'margin_right_cm'])
    headings = _merge(profile.get('headings', {}), derived.get('headings') if derived else None,
                      ['level1_pt', 'level2_pt', 'level3_pt', 'level4_pt', 'bold',
                       'level1_alignment', 'level2_alignment', 'level3_alignment'])
    title = _merge(profile.get('title', {}), derived.get('title') if derived else None,
                   ['font_size_pt', 'bold', 'alignment'])
    body = _merge(profile.get('body', {}), derived.get('body') if derived else None,
                  ['font_size_pt', 'line_spacing', 'first_line_indent_chars'])
    fonts = _merge(profile.get('fonts', {}), derived.get('fonts') if derived else None,
                   ['chinese_heading', 'chinese_body', 'latin', 'monospace'])
    abstract_cfg = profile.get('abstract', {})
    keywords_cfg = profile.get('keywords', {})
    table = profile.get('table', {})
    image = profile.get('image', {})
    refs = profile.get('references', {})
    title_size = title.get('font_size_pt', 18)
    title_align = title.get('alignment', 'center')
    abstract_size = abstract_cfg.get('label_size_pt', 14)
    abstract_align = abstract_cfg.get('label_alignment', 'center')
    h_for_md_h2 = headings.get('level2_pt', 14)
    h_for_md_h3 = headings.get('level3_pt', 12)
    h_for_md_h4 = headings.get('level4_pt', headings.get('level3_pt', 11))
    h_h2_align = headings.get('level2_alignment', 'left')
    h_h3_align = headings.get('level3_alignment', 'left')
    is_english = outline_kind == 'competition_en'
    abstract_label = 'Summary / Abstract' if is_english else '摘要 / Abstract'
    abstract_examples = '「Summary」/「Abstract」' if is_english else '「摘要」/「Abstract」/「Summary」'
    keywords_label = '**Keywords**' if is_english else '**关键词**'
    keywords_separator = ':' if is_english else '：'
    keywords_value_example = 'xxx, yyy, zzz'
    title_label = 'Paper Title' if is_english else '论文题目'
    section_h2_example = '## 1. Introduction / ## Method' if is_english else '## 一、问题重述 / ## 1 引言'
    section_h3_example = '### 1.1 Background' if is_english else '### 1.1 小节名'
    section_h4_example = '#### 1.1.1 ...' if is_english else '#### 1.1.1 子节名'
    outline = _OUTLINE_BY_WORKFLOW.get(outline_kind, _OUTLINE_BY_WORKFLOW['default_cn_thesis'])
    summary = _SUMMARY_BY_WORKFLOW.get(outline_kind, _SUMMARY_BY_WORKFLOW['default_cn_thesis'])
    derived_note = (f'（注：本规范的字号字体边距由实测自一份完整论文样本：`{derived.get("source")}`）\n'
                    if derived else '')
    md = ''.join([
        '# Markdown 格式自检对照表（',
        str(workflow),
        ' 工作流参考）\n\n> 此文件仅作为 docx-format-check 步骤的**自检对照参考**，不参与渲染、不当模板。\n> 具体格式要求由 docx-export 渲染引擎按 `',
        str(profile_name),
        '` 应用。\n',
        str(derived_note),
        '\n**核心规范摘要**：',
        str(summary),
        '\n\n## 一、页面与正文规范\n\n- 纸张：',
        str(page.get("size", "A4")),
        '\n- 页边距：上 ',
        str(page.get("margin_top_cm", 2.5)),
        ' cm / 下 ',
        str(page.get("margin_bottom_cm", 2.5)),
        ' cm / 左 ',
        str(page.get("margin_left_cm", 2.5)),
        ' cm / 右 ',
        str(page.get("margin_right_cm", 2.5)),
        ' cm\n- 正文字号：',
        str(body.get("font_size_pt", 12)),
        ' pt',
        str('' if is_english else '（中文小四号）'),
        '\n- 正文行距：',
        str(body.get("line_spacing", 1.5)),
        ' 倍\n- 首行缩进：',
        str(body.get("first_line_indent_chars", 2)),
        ' 个汉字字符宽度',
        str('（英文文档通常无首行缩进）' if is_english and body.get("first_line_indent_chars", 2) == 0 else ''),
        '\n- 中文正文字体：',
        str(fonts.get("chinese_body", "SimSun")),
        str('（仅中英混排时用）' if is_english else ''),
        '\n- 中文标题字体：',
        str(fonts.get("chinese_heading", "SimHei")),
        str('（仅中英混排时用）' if is_english else ''),
        '\n- 西文字体：',
        str(fonts.get("latin", "Times New Roman")),
        '\n- 等宽字体（代码）：',
        str(fonts.get("monospace", "Consolas")),
        '\n\n## 二、Markdown 标题层级与渲染映射\n\n| Markdown 写法 | 渲染字号(pt) | 加粗 | 对齐 | 用途 |\n|--------------|------------|------|------|------|\n| `# ',
        str(title_label),
        '` (整篇唯一) | ',
        str(title_size),
        ' | 是 | ',
        str(title_align),
        ' | 论文/报告题目（自动用 title 样式） |\n| `## ',
        str(abstract_label),
        '` | ',
        str(abstract_size),
        ' | 是 | ',
        str(abstract_align),
        ' | 摘要标题（引擎特殊路径） |\n| `',
        str(section_h2_example),
        '` | ',
        str(h_for_md_h2),
        ' | 是 | ',
        str(h_h2_align),
        ' | 一级章节 |\n| `',
        str(section_h3_example),
        '` | ',
        str(h_for_md_h3),
        ' | 是 | ',
        str(h_h3_align),
        ' | 二级小节 |\n| `',
        str(section_h4_example),
        '` | ',
        str(h_for_md_h4),
        ' | 是 | left | 三级子节（慎用） |\n\n⛔ **关键铁律**（按引擎实际行为）：\n\n1. **整篇论文 `#` 只用一次**（论文题目），所有正文章节从 `## ` 起步。如果你写了多个 `#` 标题，第二个开始就会按"二次 H1"渲染（落到 `level1_pt`，可能不是你想要的样式）。\n2. **`## 摘要` / `## Abstract` / `## Summary` 自动走特殊样式**（',
        str(abstract_size),
        'pt 居中加粗）— 这是引擎硬编码识别的，你不需要做任何特殊操作，但**摘要标题必须正好是 ',
        str(abstract_examples),
        '**，不要写成"摘要：" / "## 摘 要" / "## ABSTRACT"。\n3. **`',
        str(keywords_label),
        str(keywords_separator),
        str(keywords_value_example),
        '`** 也走特殊路径（黑体加粗标签 + 正文内容，独占一行段落）。**注意：本工作流的关键词标签字体是 ',
        str(keywords_cfg.get('font', 'SimHei') if keywords_cfg else 'SimHei'),
        '**，正文是 ',
        str(fonts.get("chinese_body", "SimSun")),
        '。\n4. **章节用 `#` 开头**，禁止 `- 章节名`（list 项 → 渲染成 "•"）。\n\n⛔ **铁律：标题必须用 `#` 开头**，禁止用 `- 章节名`（list 项）伪装标题，否则 docx 引擎会渲染成"• 章节名"。\n\n## 三、推荐章节骨架（仅供结构对照，不要照搬具体名称）\n\n按 `',
        str(workflow),
        '` 工作流的特点，建议骨架如下：\n\n```\n',
        str(_outline_to_md(outline)),
        '\n```\n\n⛔ **本骨架是"参考结构"不是"必须项"**：\n- 论文/报告应包含的核心模块在表里都列了\n- 具体章节名可以根据论文实际内容调整（"问题一/问题二" / "方法一/方法二" / 主题分类等）\n- H2 是一级章节；H3 是二级小节；H4 是三级子节\n- 不要为了凑骨架而强行填充空章节\n\n## 四、图/表注释规范\n\n⛔ **题注铁律**：\n- 图：`图 X：说明文字` 或 `图 X-Y：说明文字`（X 是章节号或全文流水号）\n- 表：`表 X：说明文字`\n- **题注独占一行**，紧跟在图/表的下面（图在题注下方，表在题注上方更规范，但 markdown 引擎都能识别）\n- ⛔ 不要写成 `- 图 X：xxx`（list 项 → 渲染出 "•"）\n- ⛔ 不要写成 `**图 X**：xxx`（加粗 + 冒号会被识别成正文加粗段）\n- 题注是图/表的灵魂，必须**简短具体**（不超过 30 字），点明这张图/表说明什么\n\n正确范式样例：\n\n```\n![](figures/fig_main.png)\n图 1：核心模型流程示意图\n\n| 列1 | 列2 |\n|---|---|\n| ... | ... |\n表 1：实验结果对比\n```\n\n## 五、公式编号规范\n\n⛔ **公式铁律**：\n- 块公式必须独占行：`$$ y = ax + b $$`\n- 编号必须**与公式同行**，不能写在下一行：\n  - 对：`$$ y = ax + b $$ (1)` 或 `$$ y = ax + b \\tag{1} $$`\n  - 错：`$$ y = ax + b $$\\n- (1)` （编号被渲染成 list bullet）\n- 全文按出现顺序连续编号 `(1)(2)(3)...`，不跳号、不重复\n- 行内公式用单 `$..$`：`$E=mc^2$`，**不用** `$$..$$`\n\n## 六、加粗使用规则\n\n⛔ **加粗使用规则**：\n- 关键词标签 `**关键词**：` 加粗\n- 假设/定理标签 `**假设一**：` `**定理 1**：` 加粗\n- 章节标题已自带加粗，不要再用 `**`\n- ⛔ 不要整段加粗（一段全是 `**...**`）\n- ⛔ 不要用加粗当强调，过多加粗反而稀释重点\n\n## 七、表格规范\n\n- 三线表样式：顶线 ',
        str(table.get("top_border_pt", 1.5)),
        ' pt + 表头线 ',
        str(table.get("header_border_pt", 0.75)),
        ' pt + 底线 ',
        str(table.get("bottom_border_pt", 1.5)),
        ' pt\n- 表头加粗：',
        str(table.get("header_bold", True)),
        '\n- 单元格对齐：',
        str(table.get("cell_alignment", "center")),
        '\n- 字号：',
        str(table.get("font_size_pt", 10.5)),
        ' pt（小五号）\n\n⛔ **Markdown 表格铁律**：\n- 用纯 Markdown 表格语法 `| ... | ... |`，**禁止** LaTeX `\\begin{tabular}`\n- 第二行必须是分隔行 `|---|---|...|`\n- 每行列数一致\n- 数据来源优先 `figures/TABLE_*.md`（已生成的真实数据），不要凭记忆手抄\n\n## 八、图片规范\n\n- 引用语法：`![图 X：图题](figures/fig_xxx.png)`\n- ⛔ 必须 `.png`，不能 `.pdf`（Word 不能嵌 PDF）\n- alt 文本同时作为图题（自动渲染）\n- 最大宽度：',
        str(image.get("max_width_cm", 14)),
        ' cm\n- 对齐：',
        str(image.get("alignment", "center")),
        '\n\n## 九、参考文献规范\n\n- 上标引用：`[1]` `[2,3]` `[4-6]`\n- 不要用 `\\cite{}` `\\ref{}`\n- 文献格式：`[1] 作者. 题名[J]. 期刊, 年, 卷(期): 页码.`\n- 行间距：悬挂缩进 ',
        str(refs.get("hanging_indent_cm", 0.74)),
        ' cm\n- 字号：',
        str(refs.get("font_size_pt", 10.5)),
        ' pt\n\n---\n\n## 自检清单\n\n按本对照表检查源 markdown 时，重点关注：\n\n1. ☐ 所有章节标题用 `#` 开头，没有 `- xxx` 伪标题\n2. ☐ 题注独占行，没有 `- ` 前缀\n3. ☐ 块公式编号与公式同行，没有独立的 `- (1)` 行\n4. ☐ Markdown 表格分隔行存在，每行列数一致\n5. ☐ 图片用 `.png`，不引用 `.pdf`\n6. ☐ 章节层级合理（H1 唯一，H2/H3/H4 按推荐骨架排布）\n7. ☐ 加粗只用在结构化标签（关键词/假设/定理），不滥用\n8. ☐ 没有 LaTeX 残留（`\\begin{}` `\\section{}` `\\cite{}`）\n',
    ])
    return md


def main():
    p = argparse.ArgumentParser(prog=PROG, description='生成「Markdown 格式自检对照表」给 docx-format-check skill')
    p.add_argument('--workflow', required=True,
                   help='工作流名（如 comp_cumcm / course_paper / thesis_proposal）')
    p.add_argument('--out', type=Path, required=True, help='输出 markdown 文件路径')
    p.add_argument('--derived', type=Path, default=None,
                   help='（可选）已派生的 reference_paper_general.json 路径（来自 derive_reference_from_docx.py）')
    args = p.parse_args()

    md = build_reference_md(args.workflow, prefer_derived=args.derived)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(md, encoding='utf-8')
    print(f'OK 写入 {args.out} ({args.out.stat().st_size} bytes)')


if __name__ == '__main__':
    main()
