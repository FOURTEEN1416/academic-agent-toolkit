# -*- coding: utf-8 -*-
"""paper_data_check — 论文数据真实性自检辅助（PDF 与 DOCX 通用）

设计原则：
    引擎层不做语义判断（哪个数字"应该"来自 JSON、哪个是论文叙述里自然出现的，
    机器算法判断不准，会大量假阳性）。
    引擎只做两件事：
    1. 准备「数据原料清单」（PAPER_DATA_CHECKLIST.md）— 把 JSON 全数据 +
       TABLE_*.tex|md 全文贴在一起给 Claude 看
    2. 确定性硬规则检查（LaTeX 表格残留、Markdown 残留）— 这两类是格式问题，
       不依赖语义

    数据真实性的判断与修复完全交给 Claude：
    - Claude 读 PAPER_DATA_CHECKLIST.md（数据原料）
    - Claude 读论文（main.md / sections/*.tex）
    - Claude 自己判断：论文里出现的数字哪些应该核对、哪些是叙述里的自然数字
    - Claude 自己修：以 JSON 为准，禁止反向操作
    - Claude 修完后在论文末尾写 `<!-- DATA_CHECK_PASSED -->`（DOCX）
      或 `% DATA_CHECK_PASSED`（PDF）标记已自检

CLI：
    python paper_data_check.py --mode docx --workspace ./workspace
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import re
import sys
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# 本文件是 academic-toolkit/tools/paper_data_check.pyc 的等源重建（原真码只在 pyc 里）。
# 为与 pyc 基准 stdout 逐字节一致，argparse 的 prog 固定为经 .pyc 启动时的名字。
PROG = Path(sys.argv[0]).stem + '.pyc'


class DataCheckReport:
    def __init__(self, mode: str, sources: list[Path]):
        self.mode = mode
        self.sources = sources
        self.fatal = []
        self.warn = []
        self.info = []
        self.checklist_md = ''
        self.need_self_check = False
        self.passed_marker_found = False
        self.stats = {}

    def add_fatal(self, msg: str):
        self.fatal.append(msg)

    def add_warn(self, msg: str):
        self.warn.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def has_fatal(self) -> bool:
        return bool(self.fatal)

    def render_summary(self) -> str:
        parts = []
        if self.fatal:
            parts.append(f'{len(self.fatal)} 致命')
        if self.warn:
            parts.append(f'{len(self.warn)} 警告')
        if self.passed_marker_found:
            parts.append('Claude 已自检')
        elif self.need_self_check:
            parts.append('待 Claude 自检')
        return ' / '.join(parts) if parts else '无问题'


def _strip_for_residue_scan(content: str, mode: str) -> str:
    text = re.sub('```[\\s\\S]*?```', '', content)
    text = re.sub('`[^`\\n]+`', '', text)
    if mode == 'docx':
        text = re.sub('\\$\\$[\\s\\S]*?\\$\\$', '', text)
        text = re.sub('\\$[^\\n$]+?\\$', '', text)
        text = re.sub('<!--[\\s\\S]*?-->', '', text)
    else:
        text = re.sub('\\$\\$[\\s\\S]*?\\$\\$', '', text)
        text = re.sub('\\$[^\\n$]+?\\$', '', text)
        text = re.sub('\\\\\\([\\s\\S]*?\\\\\\)', '', text)
        text = re.sub('\\\\\\[[\\s\\S]*?\\\\\\]', '', text)
        text = re.sub('\\\\begin\\{equation\\*?\\}[\\s\\S]*?\\\\end\\{equation\\*?\\}', '', text)
        text = re.sub('\\\\begin\\{align\\*?\\}[\\s\\S]*?\\\\end\\{align\\*?\\}', '', text)
        text = re.sub('(?m)(?<!\\\\)%.*$', '', text)
    return text


def check_latex_table_residue_in_md(content: str, report: DataCheckReport):
    """DOCX 模式：markdown 不应有 LaTeX 表格代码（确定性硬规则 → fatal）。"""
    text = _strip_for_residue_scan(content, 'docx')
    patterns = [
        ('\\\\begin\\{tabular\\}', '\\begin{tabular}'),
        ('\\\\end\\{tabular\\}', '\\end{tabular}'),
        ('\\\\begin\\{table\\*?\\}', '\\begin{table}'),
        ('\\\\begin\\{longtable\\}', '\\begin{longtable}'),
        ('\\\\toprule', '\\toprule'),
        ('\\\\midrule', '\\midrule'),
        ('\\\\bottomrule', '\\bottomrule'),
        ('\\\\input\\{[^}]*figures/TABLE_[^}]+\\}', '\\input{figures/TABLE_*.tex}'),
        ('\\\\input\\{figures/[^}]*\\.tex\\}', '\\input{figures/*.tex}'),
    ]
    found = []
    for pat, name in patterns:
        cnt = len(re.findall(pat, text))
        if cnt > 0:
            found.append((name, cnt))
    if found:
        residue_lines = [f'`{name}` × {cnt}' for name, cnt in found]
        report.add_fatal(
            'Markdown 中残留 LaTeX 表格代码（Word 不会渲染）：\n'
            + '\n'.join(f'    - {ln}' for ln in residue_lines)
            + '\n  → 修复：替换为 Markdown 三线表 `| 表头 |\\n|---|---|\\n| 数据 |`，或 `cat figures/TABLE_*.md`（paper-figure 已自动生成 Markdown 版本）。')
        return


def check_markdown_residue_in_tex(content: str, report: DataCheckReport):
    """PDF 模式：.tex 不应有 markdown 表格语法（warn，不阻塞）。"""
    text = _strip_for_residue_scan(content, 'pdf')
    found = []
    if re.search('(?m)^\\s*\\|[\\s\\-:|]+\\|\\s*$', text):
        found.append('Markdown 表格分隔行 `|---|---|`（应改为 booktabs `\\toprule`+`\\midrule`+`\\bottomrule`）')
    if re.search('(?m)^#{1,6}\\s+\\S', text):
        found.append('Markdown 标题（`#`/`##`）应改为 `\\section{}`/`\\subsection{}`')
    if found:
        report.add_warn('LaTeX 中残留 Markdown 语法：' + '; '.join(found) + '  → 这些语法 LaTeX 不解析，会丢失格式。')
        return


def _flatten_json(obj: Any, prefix: str = '', out: list[tuple[str, Any]] | None = None) -> list[tuple[str, Any]]:
    if out is None:
        out = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            _flatten_json(v, f'{prefix}.{k}' if prefix else str(k), out)
    elif isinstance(obj, list):
        if len(obj) <= 5:
            for i, v in enumerate(obj):
                _flatten_json(v, f'{prefix}[{i}]', out)
        else:
            for i in (0, 1, 2, len(obj) - 1):
                _flatten_json(obj[i], f'{prefix}[{i}]', out)
            out.append((f'{prefix}[...]', f'<{len(obj) - 4} 项省略>'))
    elif obj is None:
        return out
    elif isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return out
    else:
        out.append((prefix, obj))
    return out


def _format_value(v: Any) -> str:
    if isinstance(v, float):
        if abs(v) >= 1000 or 0 < abs(v) < 0.01:
            return f'{v:.4g}'
        return f'{v:g}'
    if isinstance(v, str):
        return f'`{v[:60]}`' if len(v) <= 60 else f'`{v[:55]}...`'
    return str(v)


def build_data_checklist(workspace: Path, mode: str) -> tuple[str, int]:
    """构建给 Claude 的数据原料清单（含 JSON 全数据 + TABLE 文件全文）。

    返回 (markdown 内容, 数据条目数)。
    """
    figures_dir = workspace / 'figures'
    json_sources = []
    seen = set()
    if figures_dir.exists():
        for c in ('all_results.json',):
            if c not in seen:
                seen.add(c)
                p = figures_dir / c
                if p.exists():
                    try:
                        json_sources.append((p, json.loads(p.read_text(encoding='utf-8'))))
                    except Exception as e:
                        log.warning('无法解析 %s: %s', p, e)
        for f in sorted(figures_dir.glob('*_results.json')):
            if f.name in seen:
                continue
            seen.add(f.name)
            try:
                json_sources.append((f, json.loads(f.read_text(encoding='utf-8'))))
            except Exception as e:
                log.warning('无法解析 %s: %s', f, e)
    for c in ('results.json',):
        wp = workspace / c
        if wp.exists() and c not in seen:
            seen.add(c)
            try:
                json_sources.append((wp, json.loads(wp.read_text(encoding='utf-8'))))
            except Exception as e:
                log.warning('无法解析 %s: %s', wp, e)
    for f in sorted(workspace.glob('results_*.json')):
        if f.name in seen:
            continue
        seen.add(f.name)
        try:
            json_sources.append((f, json.loads(f.read_text(encoding='utf-8'))))
        except Exception as e:
            log.warning('无法解析 %s: %s', f, e)

    all_entries = []
    for jp, data in json_sources:
        for kp, v in _flatten_json(data):
            all_entries.append((jp.name, kp, v))

    table_files = []
    if figures_dir.exists():
        table_files = sorted(figures_dir.glob('TABLE_*.tex')) + sorted(figures_dir.glob('TABLE_*.md'))

    if not all_entries and not table_files:
        return ('', 0)

    lines = [
        '# 论文数据真实性核对清单（数据原料）',
        '',
        f'**模式**: {mode.upper()}',
    ]
    if json_sources:
        lines.append(f'**JSON 源**: {", ".join(p.name for p, _ in json_sources)}')
        lines.append(f'**JSON 数据条目**: {len(all_entries)}')
    if table_files:
        lines.append(f'**已生成的 TABLE 文件**: {len(table_files)} 个')
    lines.append('')
    lines.append('---')
    lines.append('')

    if mode == 'docx':
        embed_hint = '`cat figures/TABLE_*.md >> paper/main.md` 直接嵌入'
        passed_marker = '<!-- DATA_CHECK_PASSED -->'
    else:
        embed_hint = '`\\input{figures/TABLE_*.tex}` 引入'
        passed_marker = '% DATA_CHECK_PASSED'

    lines += [
        '## 自检步骤（请你按以下顺序执行）',
        '',
        '**重要原则**：本工作区的实验/分析阶段已经把所有真实数据存到 `figures/*.json`，',
        '并由 paper-figure 步骤渲染成 `figures/TABLE_*.tex|md`。',
        '**论文中所有「数据性」数字（实验结果、统计量、对比指标、最优解等）必须来自这些文件**。',
        '',
        '### 第 1 步：识别论文中的「数据性数字」',
        '',
        '打开你的论文文件，逐章扫描：',
        '',
        '- ✅ **需要核对的**：表格里的所有单元格数字、正文里引用实验结果的数字（如 "RMSE 达到 0.023"、"准确率 94%"、"最优解 295.83"、"R² 为 0.94"）',
        '- ⏭️ **不需要核对的**（叙述里自然出现的数字）：',
        '    - 章节编号、列号、引用 [1][2,3]、图编号「图 3-1」',
        '    - 年份「2024 年」、日期「3 月 5 日」',
        '    - 公式中的常数（在 `$...$` 或 `$$...$$` 内）',
        '    - 算法描述里的步骤数「分 5 步」',
        '    - 文献综述里别人论文的数字',
        '',
        '### 第 2 步：对每个「数据性数字」核对',
        '',
        '对照下方的 JSON 数据清单和 TABLE 文件全文：',
        '',
        '1. **能在数据清单/TABLE 文件里找到完全一致的数字** → ✅ 真实，跳过',
        '2. **数据清单里有但论文写错了**（如 RMSE 真实是 0.023，论文写的 0.999） → 改正文，**禁止反向操作**（禁止改 JSON）',
        '3. **数据清单里没有这个数字** → 两种可能：',
        '   - **AI 编造**（最常见）→ 删除该说法或从清单中找正确数据补充',
        '   - **从其他来源算出来的合理派生量**（如百分比 = 子集/总数 ×100）→ 检查派生公式是否合理',
        '',
        '### 第 3 步：表格优先用预生成的 TABLE 文件',
        '',
        f'如果论文里手抄了表格内容，**优先改成** {embed_hint}（已经从 JSON 渲染好，不会出错）。',
        '',
        '### 第 4 步：自检完成后，在论文末尾追加自证标记',
        '',
        '修完所有问题后，在论文文件**末尾**添加一行注释：',
        '',
        '```',
        f'{passed_marker}',
        '```',
        '',
        '下一轮检查看到此标记会跳过自检循环。',
        '',
        '**判断原则**：',
        '- 以 JSON 为准修论文，禁止反向修 JSON',
        '- 不必把 JSON 中的每个数字都搬到论文里——只关心论文里出现的数字是否真实',
        '- 不确定某个数字是不是数据 → 当成数据核对一遍，确认能找到来源就行',
        '',
        '---',
        '',
    ]

    if all_entries:
        lines.append('## JSON 真实数据清单')
        lines.append('')
        by_file = {}
        for fn, kp, v in all_entries:
            by_file.setdefault(fn, []).append((kp, v))
        for fn, entries in by_file.items():
            lines.append(f'### `{fn}`（{len(entries)} 条）')
            lines.append('')
            lines.append('| 数据路径 | 数值 |')
            lines.append('|---|---|')
            for kp, v in entries:
                kp_safe = kp.replace('|', '\\|')
                lines.append(f'| `{kp_safe}` | {_format_value(v)} |')
            lines.append('')

    if table_files:
        lines.append('---')
        lines.append('')
        lines.append('## 已生成的 TABLE 文件（论文应直接嵌入这些表，不要自己手抄）')
        lines.append('')
        for tf in table_files:
            try:
                text = tf.read_text(encoding='utf-8', errors='replace')
            except Exception as e:
                lines.append(f'### `figures/{tf.name}` — 读取失败：{e}')
                continue
            lang = 'latex' if tf.suffix == '.tex' else 'markdown'
            lines.append(f'### `figures/{tf.name}` ({tf.stat().st_size} 字节)')
            lines.append('')
            lines.append(f'```{lang}')
            tf_lines = text.split('\n')
            if len(tf_lines) > 200:
                lines.extend(tf_lines[:100])
                lines.append(f'... [中间 {len(tf_lines) - 200} 行省略] ...')
                lines.extend(tf_lines[-100:])
            else:
                lines.append(text.rstrip())
            lines.append('```')
            lines.append('')

    return ('\n'.join(lines), len(all_entries))


_PASSED_MARKER_DOCX = '<!-- DATA_CHECK_PASSED -->'
_PASSED_MARKER_PDF = '% DATA_CHECK_PASSED'


def find_sources(workspace: Path, mode: str) -> list[Path]:
    if mode == 'docx':
        candidates = [
            'paper/main.md', 'PROPOSAL.md', 'LITERATURE_REVIEW.md',
            'COURSE_PAPER.md', 'COURSE_REPORT.md', 'REPORT.md',
        ]
        for c in candidates:
            p = workspace / c
            if p.exists() and p.stat().st_size > 100:
                return [p]
        return []
    sections = workspace / 'paper' / 'sections'
    if sections.exists():
        tex_files = sorted(sections.glob('*.tex'))
        if tex_files:
            return tex_files
    main = workspace / 'paper' / 'main.tex'
    if main.exists():
        return [main]
    return []


def _safe_read(p: Path) -> str:
    raw = p.read_bytes()
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin-1'):
        try:
            return raw.decode(enc).replace('\r\n', '\n').replace('\r', '\n')
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode('utf-8', errors='replace')


def has_passed_marker(content: str, mode: str) -> bool:
    """检测论文末尾是否有 Claude 写的自证标记。"""
    marker = _PASSED_MARKER_DOCX if mode == 'docx' else _PASSED_MARKER_PDF
    return marker in content


def run_check(workspace: Path, mode: str) -> DataCheckReport:
    """运行确定性硬规则检查 + 准备数据清单 + 检测自证标记。"""
    sources = find_sources(workspace, mode)
    report = DataCheckReport(mode, sources)

    if not sources:
        report.add_info('未找到待核对的源文件，跳过')
        return report

    contents = []
    for src in sources:
        try:
            contents.append(_safe_read(src))
        except Exception as e:
            report.add_warn(f'读取 {src} 失败：{e}')
    if not contents:
        report.add_warn('所有源文件读取失败')
        return report
    full_content = '\n\n'.join(contents)
    report.stats['源文件数'] = len(sources)
    report.stats['总字符数'] = len(full_content)

    if mode == 'docx':
        check_latex_table_residue_in_md(full_content, report)
    else:
        check_markdown_residue_in_tex(full_content, report)

    report.passed_marker_found = has_passed_marker(full_content, mode)

    has_data_files = (
        any((workspace / 'figures').glob('*.json'))
        or any((workspace / 'figures').glob('TABLE_*'))
        or (workspace / 'results.json').exists()
        or any(workspace.glob('results_*.json'))
    )

    if has_data_files:
        checklist_md, n_entries = build_data_checklist(workspace, mode)
        if checklist_md:
            report.checklist_md = checklist_md
            report.stats['数据条目数'] = n_entries
            try:
                (workspace / 'PAPER_DATA_CHECKLIST.md').write_text(checklist_md, encoding='utf-8')
            except Exception as e:
                log.warning('无法写 PAPER_DATA_CHECKLIST.md: %s', e)
            if not report.passed_marker_found:
                report.need_self_check = True
        else:
            report.add_info('figures/ 中无 JSON 也无 TABLE — 跳过自检')
    else:
        report.add_info('无 figures/*.json 或 TABLE_* — 无数据需要核对')

    try:
        (workspace / 'PAPER_DATA_CHECK_REPORT.md').write_text(_render_report(report), encoding='utf-8')
    except Exception as e:
        log.warning('无法写报告文件：%s', e)

    return report


def _render_report(report: DataCheckReport) -> str:
    lines = [
        f'# 论文数据真实性核对报告（{report.mode.upper()} 模式）',
        '',
        f'**核对源**: {", ".join(s.name for s in report.sources) or "(无)"}',
        f'**摘要**: {report.render_summary()}',
        '',
    ]
    if report.stats:
        lines.append('## 统计')
        for k, v in report.stats.items():
            lines.append(f'- {k}: {v}')
        lines.append('')
    if report.fatal:
        lines.append('## ❌ 致命（确定性硬规则违反）')
        for m in report.fatal:
            lines.append(f'- {m}')
        lines.append('')
    if report.warn:
        lines.append('## ⚠ 警告')
        for m in report.warn:
            lines.append(f'- {m}')
        lines.append('')
    if report.info:
        lines.append('## ℹ 信息')
        for m in report.info:
            lines.append(f'- {m}')
        lines.append('')
    if report.passed_marker_found:
        lines.append('## ✅ 已通过 Claude 自检')
        lines.append('')
        lines.append(f'论文中含 `{_PASSED_MARKER_DOCX if report.mode == "docx" else _PASSED_MARKER_PDF}` 标记。')
    elif report.need_self_check:
        lines.append('## 🔄 待 Claude 自检')
        lines.append('')
        lines.append('数据原料已写入 `PAPER_DATA_CHECKLIST.md`，等待 Claude 读清单 + 论文进行自检修复。')
    return '\n'.join(lines)


class TableCheckReport:
    """paper-figure 步骤后的检查报告。

    与 DataCheckReport 类似但范围不同：只检查 figures/TABLE_*.tex|md。
    """
    def __init__(self):
        self.fatal = []
        self.warn = []
        self.info = []
        self.checklist_md = ''
        self.need_self_check = False
        self.passed_marker_found = False
        self.stats = {}
        self.table_files = []

    def has_fatal(self) -> bool:
        return bool(self.fatal)

    def render_summary(self) -> str:
        parts = []
        if self.fatal:
            parts.append(f'{len(self.fatal)} 致命')
        if self.warn:
            parts.append(f'{len(self.warn)} 警告')
        if self.passed_marker_found:
            parts.append('Claude 已自检')
        elif self.need_self_check:
            parts.append('待 Claude 自检 TABLE')
        return ' / '.join(parts) if parts else '无 TABLE 文件，跳过'


_TABLE_PASSED_MARKER_FILE = 'TABLE_DATA_CHECK_PASSED.txt'


def has_table_passed_marker(workspace: Path) -> bool:
    """检测 paper-figure 步骤是否写过自证标记文件。"""
    marker = workspace / 'figures' / _TABLE_PASSED_MARKER_FILE
    return marker.exists()


def build_table_checklist(workspace: Path, json_sources: list[tuple[Path, Any]], table_files: list[Path]) -> str:
    """构建 TABLE-vs-JSON 核对清单（paper-figure 步骤用）。

    与论文清单的区别：聚焦在「TABLE 数字应该 100% 来自 JSON」这条铁律。
    """
    if not json_sources or not table_files:
        return ''

    all_entries = []
    for jp, data in json_sources:
        for kp, v in _flatten_json(data):
            all_entries.append((jp.name, kp, v))

    lines = [
        '# TABLE 数据真实性核对清单（paper-figure 步骤）',
        '',
        f'**JSON 源**: {", ".join(p.name for p, _ in json_sources)}',
        f'**JSON 数据条目**: {len(all_entries)}',
        f'**TABLE 文件**: {len(table_files)} 个',
        '',
        '---',
        '',
        '## 核心规则',
        '',
        '**`figures/TABLE_*.tex|md` 中的所有数字必须 100% 来自 `figures/*.json`。**',
        '',
        'paper-figure 步骤的设计是从 JSON 数据**渲染**出 TABLE 文件',
        '（用 `_utils/stats_utils.py` 的 `regression_table()` / `descriptive_table()` 等函数，',
        '或者读 JSON 后用 Python 脚本生成）。',
        '',
        '**TABLE 中出现 JSON 没有的数字 = 编造**，必须用真实 JSON 数据重新生成对应表格。',
        '',
        '---',
        '',
        '## 自检步骤',
        '',
        '1. **逐个打开 figures/TABLE_*.tex|md**，识别每个表格里的数字单元格',
        '2. **对每个数字**，对照下方 JSON 数据清单：',
        '   - ✅ 能精确匹配（含合理的精度截断如 `0.94` ↔ `0.93724`）→ 真实',
        '   - ❌ 在 JSON 里找不到 → **编造**：必须删除该 TABLE 文件，',
        '     用真实 JSON 数据重新生成（推荐：`python3 -c "from _utils.stats_utils import descriptive_table; ..."`）',
        '3. **跳过非数据型数字**：列号 `(1)(2)(3)`、列宽 `width=10cm`、LaTeX 字号 `\\zihao{5}` 等格式标记中的数字',
        '4. **修完所有 TABLE 后**，写自证标记：',
        '',
        '   ```bash',
        f'   touch figures/{_TABLE_PASSED_MARKER_FILE}',
        '   ```',
        '',
        '   下一轮检查看到此标记会跳过自检循环。',
        '',
        '**禁止**：禁止改 JSON 让数字"对得上"、禁止编造解释、禁止保留疑似编造的 TABLE。',
        '',
        '**特别提示**：如果 JSON 中确实没有支撑某张表所需的数据（比如表格规划里有「数据集统计特征」但 JSON 只存了模型对比结果），说明 paper-analysis 步骤遗漏了该数据。应该：(a) 删除这张表 + 改写论文规划中关于这张表的引用；或 (b) 临时跑一段 Python 从原始数据重算并补到 JSON，再生成 TABLE。**不能**直接保留编造的数字。',
        '',
        '---',
        '',
        '## TABLE 文件全文',
        '',
    ]
    for tf in table_files:
        try:
            text = tf.read_text(encoding='utf-8', errors='replace')
        except Exception:
            continue
        lang = 'latex' if tf.suffix == '.tex' else 'markdown'
        lines.append(f'### `figures/{tf.name}` ({tf.stat().st_size} 字节)')
        lines.append('')
        lines.append(f'```{lang}')
        tf_lines = text.split('\n')
        if len(tf_lines) > 200:
            lines.extend(tf_lines[:100])
            lines.append(f'... [中间 {len(tf_lines) - 200} 行省略] ...')
            lines.extend(tf_lines[-100:])
        else:
            lines.append(text.rstrip())
        lines.append('```')
        lines.append('')

    lines += ['---', '', '## JSON 真实数据完整清单', '']
    by_file = {}
    for fn, kp, v in all_entries:
        by_file.setdefault(fn, []).append((kp, v))
    for fn, entries in by_file.items():
        lines.append(f'### `{fn}`（{len(entries)} 条）')
        lines.append('')
        lines.append('| 数据路径 | 数值 |')
        lines.append('|---|---|')
        for kp, v in entries:
            kp_safe = kp.replace('|', '\\|')
            lines.append(f'| `{kp_safe}` | {_format_value(v)} |')
        lines.append('')

    return '\n'.join(lines)


def run_table_check(workspace: Path) -> TableCheckReport:
    """paper-figure 步骤完成后调用：核对 TABLE 文件是否都来自 JSON。

    与 run_check (论文级) 互为补充：
    - run_table_check：paper-figure 后跑，检查表格本身
    - run_check：写作步骤后跑，检查论文 + 嵌入的表格

    这样可以从源头拦截「TABLE 编造 → 写作 cat 进去 → 数字错的论文」的链路。
    """
    report = TableCheckReport()

    figs = workspace / 'figures'
    if not figs.is_dir():
        report.info.append('无 figures/ 目录，跳过 TABLE 核对')
        return report

    table_files = sorted(figs.glob('TABLE_*.tex')) + sorted(figs.glob('TABLE_*.md'))
    if not table_files:
        report.info.append('无 figures/TABLE_*.tex|md 文件，跳过 TABLE 核对')
        return report
    report.table_files = table_files
    report.stats['TABLE 文件数'] = len(table_files)

    json_sources = []
    seen = set()
    for c in ('all_results.json',):
        if c not in seen:
            seen.add(c)
            p = figs / c
            if p.exists():
                try:
                    json_sources.append((p, json.loads(p.read_text(encoding='utf-8'))))
                except Exception as e:
                    log.warning('无法解析 %s: %s', p, e)
    for f in sorted(figs.glob('*_results.json')):
        if f.name in seen:
            continue
        seen.add(f.name)
        try:
            json_sources.append((f, json.loads(f.read_text(encoding='utf-8'))))
        except Exception as e:
            log.warning('无法解析 %s: %s', f, e)
    for c in ('results.json',):
        wp = workspace / c
        if wp.exists() and c not in seen:
            seen.add(c)
            try:
                json_sources.append((wp, json.loads(wp.read_text(encoding='utf-8'))))
            except Exception as e:
                log.warning('无法解析 %s: %s', wp, e)
    for f in sorted(workspace.glob('results_*.json')):
        if f.name in seen:
            continue
        seen.add(f.name)
        try:
            json_sources.append((f, json.loads(f.read_text(encoding='utf-8'))))
        except Exception as e:
            log.warning('无法解析 %s: %s', f, e)

    if not json_sources:
        report.warn.append(
            f'有 {len(table_files)} 个 TABLE 文件但**没有 figures/*.json**，'
            '无法核对真实性 — 请先确认 paper-analysis 步骤是否产出了 JSON 结果文件')
        return report

    report.stats['JSON 文件数'] = len(json_sources)

    report.passed_marker_found = has_table_passed_marker(workspace)

    checklist = build_table_checklist(workspace, json_sources, table_files)
    if checklist:
        report.checklist_md = checklist
        try:
            (workspace / 'TABLE_DATA_CHECKLIST.md').write_text(checklist, encoding='utf-8')
        except Exception as e:
            log.warning('无法写 TABLE_DATA_CHECKLIST.md: %s', e)
        if not report.passed_marker_found:
            report.need_self_check = True

    try:
        (workspace / 'TABLE_DATA_CHECK_REPORT.md').write_text(_render_table_report(report), encoding='utf-8')
    except Exception as e:
        log.warning('无法写 TABLE_DATA_CHECK_REPORT.md: %s', e)

    return report


def _render_table_report(report: TableCheckReport) -> str:
    lines = [
        '# TABLE 数据真实性核对报告',
        '',
        f'**TABLE 文件数**: {len(report.table_files)}',
        f'**摘要**: {report.render_summary()}',
        '',
    ]
    if report.stats:
        lines.append('## 统计')
        for k, v in report.stats.items():
            lines.append(f'- {k}: {v}')
        lines.append('')
    if report.fatal:
        lines.append('## ❌ 致命')
        for m in report.fatal:
            lines.append(f'- {m}')
        lines.append('')
    if report.warn:
        lines.append('## ⚠ 警告')
        for m in report.warn:
            lines.append(f'- {m}')
        lines.append('')
    if report.info:
        lines.append('## ℹ 信息')
        for m in report.info:
            lines.append(f'- {m}')
        lines.append('')
    if report.passed_marker_found:
        lines.append('## ✅ 已通过 Claude 自检')
        lines.append('')
        lines.append(f'`figures/{_TABLE_PASSED_MARKER_FILE}` 已存在。')
    elif report.need_self_check:
        lines.append('## 🔄 待 Claude 自检')
        lines.append('')
        lines.append('数据原料已写入 `TABLE_DATA_CHECKLIST.md`。')
    return '\n'.join(lines)


def main():
    parser = argparse.ArgumentParser(prog=PROG, description='论文数据真实性核对（PDF/DOCX/TABLE 通用）')
    parser.add_argument('--mode', choices=['docx', 'pdf', 'table'], required=True,
                        help='docx/pdf：写作后扫论文；table：paper-figure 后扫 TABLE 文件')
    parser.add_argument('--workspace', '-w', type=Path, required=True)
    parser.add_argument('--quiet', '-q', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO,
                        format='%(levelname)s: %(message)s')

    if args.mode == 'table':
        t_report = run_table_check(args.workspace)
        if not args.quiet:
            print(_render_table_report(t_report))
        print(f'\n报告: {args.workspace}/TABLE_DATA_CHECK_REPORT.md')
        if t_report.need_self_check:
            print(f'清单: {args.workspace}/TABLE_DATA_CHECKLIST.md')
        sys.exit(1 if t_report.has_fatal() else 0)

    report = run_check(args.workspace, mode=args.mode)
    if not args.quiet:
        print(_render_report(report))
    print(f'\n报告: {args.workspace}/PAPER_DATA_CHECK_REPORT.md')
    if report.need_self_check:
        print(f'清单: {args.workspace}/PAPER_DATA_CHECKLIST.md')
    sys.exit(1 if report.has_fatal() else 0)


if __name__ == '__main__':
    main()
