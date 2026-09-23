# -*- coding: utf-8 -*-
'''docx-precheck — Markdown 转 Word 前的完整质量校核

在 docx-export 步骤之前运行，做以下检查：

1. 文件存在性（致命）
2. 图表闭环（自动修复 PDF → PNG）
3. 引用闭环（上标 ↔ 参考文献）
4. 公式语法（$ 配对、$$ 配对、\\( \\) 配对）
5. LaTeX 残留检测
6. 表格格式
7. 标题层级
8. 字数统计

用法：
    python docx_precheck.py --source paper.md --workspace ./workspace
'''
from __future__ import annotations

import argparse
import logging
import re
import sys
from pathlib import Path

log = logging.getLogger(__name__)


class CheckReport:
    def __init__(self, source_md: Path):
        self.source_md = source_md
        self.fatal = []
        self.warnings = []
        self.fixed = []
        self.info = []
        self.stats = {}

    def add_fatal(self, msg: str):
        self.fatal.append(msg)

    def add_warn(self, msg: str):
        self.warnings.append(msg)

    def add_fixed(self, msg: str):
        self.fixed.append(msg)

    def add_info(self, msg: str):
        self.info.append(msg)

    def render(self) -> str:
        lines = ['# 文档质量校核报告（DOCX 导出前）', '']
        lines.append(f'**源文件**: `{self.source_md.name}`')
        lines.append(f'**致命错误**: {len(self.fatal)}')
        lines.append(f'**警告**: {len(self.warnings)}')
        lines.append(f'**自动修复**: {len(self.fixed)}')
        lines.append(f'**信息**: {len(self.info)}')
        lines.append('')
        if self.stats:
            lines.append('## 统计信息')
            for k, v in self.stats.items():
                lines.append(f'- {k}: {v}')
            lines.append('')
        if self.fatal:
            lines.append('## ❌ 致命错误（必须修复）')
            for m in self.fatal:
                lines.append(f'- {m}')
            lines.append('')
        if self.fixed:
            lines.append('## ✅ 自动修复')
            for m in self.fixed:
                lines.append(f'- {m}')
            lines.append('')
        if self.warnings:
            lines.append('## ⚠ 警告（建议修复）')
            for m in self.warnings:
                lines.append(f'- {m}')
            lines.append('')
        if self.info:
            lines.append('## ℹ 信息')
            for m in self.info:
                lines.append(f'- {m}')
            lines.append('')
        if not self.fatal and not self.warnings:
            lines.append('## 🎉 全部检查通过')
        return '\n'.join(lines)


def _read_md(path: Path) -> str:
    '''多编码 fallback 读 markdown。'''
    raw = path.read_bytes()
    for enc in ('utf-8', 'utf-8-sig', 'gbk', 'gb2312', 'gb18030', 'latin-1'):
        try:
            text = raw.decode(enc)
            text = text.replace('\r\n', '\n').replace('\r', '\n')
            return text
        except (UnicodeDecodeError, LookupError):
            continue
    raise ValueError(f'无法解码 {path}')


def check_file_existence(source_md: Path, report: CheckReport) -> bool:
    '''1. 文件存在性 — 致命检查。返回是否可以继续。'''
    if not source_md.exists():
        report.add_fatal(f'源文件不存在: {source_md}')
        return False
    size = source_md.stat().st_size
    if size < 100:
        report.add_fatal(f'源文件过小（{size} 字节），可能写入失败')
        return False
    report.stats['源文件大小'] = f'{size} 字节'
    return True


def check_figure_closure(content: str, workspace: Path, report: CheckReport) -> str:
    '''2. 图表闭环（自动修复 PDF→PNG）。返回可能被修改的 content。'''
    figures_dir = workspace / 'figures'

    refs = []
    for m in re.finditer('!\\[[^\\]]*\\]\\(([^)]+)\\)', content):
        path_clean = m.group(1).strip().split(' ')[0]
        refs.append((m.start(), m.group(0), path_clean))

    report.stats['正文图片引用'] = len(refs)

    existing_by_stem = {}
    if figures_dir.exists():
        for f in figures_dir.iterdir():
            if f.is_file() and f.suffix.lower() in ('.png', '.pdf', '.jpg', '.jpeg', '.gif', '.bmp'):
                existing_by_stem.setdefault(f.stem, []).append(f)
        report.stats['figures/ 中文件总数'] = sum(len(v) for v in existing_by_stem.values())
    elif refs:
        report.add_warn(f'workspace 没有 figures/ 目录，但正文有 {len(refs)} 处图片引用')

    missing = []
    pdf_only = []
    for _, _, ref_path in refs:
        ref_p = Path(ref_path)
        suffix = ref_p.suffix.lower()
        candidates = [workspace / ref_path, workspace / 'figures' / ref_p.name]
        found = next((p for p in candidates if p.exists()), None)
        if found is not None:
            continue
        stem_files = existing_by_stem.get(ref_p.stem, [])
        if not stem_files:
            missing.append(ref_path)
            continue
        if suffix in ('.png', '.jpg', '.jpeg'):
            pdf_files = [f for f in stem_files if f.suffix.lower() == '.pdf']
            if pdf_files:
                pdf_only.append((ref_path, pdf_files[0]))

    for ref_path, pdf_path in pdf_only:
        target_png = pdf_path.with_suffix('.png')
        if target_png.exists():
            report.add_info(f'图 `{ref_path}` 引用 PNG，找到同目录 PNG: `{target_png.name}`（无需转换）')
            continue
        ok = _convert_pdf_to_png(pdf_path, target_png, dpi=350)
        if ok:
            report.add_fixed(f'自动从 `{pdf_path.name}` 生成 `{target_png.name}` (350 DPI)')
        else:
            report.add_warn(
                f'图 `{ref_path}` 缺少 PNG，PDF 转换失败 — 导出时该图位置会显示占位符。请手动安装 `pip install pymupdf` 或重新生成 PNG'
            )

    if missing:
        report.add_warn(
            f'{len(missing)} 张图片引用的文件不存在（导出时显示占位符）: '
            + ', '.join(f'`{m}`' for m in missing[:5])
            + (' 等' if len(missing) > 5 else '')
        )

    referenced_stems = set()
    for _, _, ref_path in refs:
        referenced_stems.add(Path(ref_path).stem)

    for stem, files in existing_by_stem.items():
        if not stem.startswith('fig_'):
            continue
        if stem not in referenced_stems:
            report.add_warn(f'图 `{stem}` 存在于 figures/ 但正文未引用（可能遗漏嵌入）')

    return content


def _convert_pdf_to_png(pdf_path: Path, out_png: Path, dpi: int = 300) -> bool:
    '''优先用 PyMuPDF (fitz)，回退到 pdf2image。

    DPI=300 是矢量图栅格化的合理下限（更低则中文字体明显模糊）。
    drawio 流程图/TikZ 架构图含小字时建议 350+。
    '''
    try:
        import fitz
        doc = fitz.open(str(pdf_path))
        if doc.page_count > 0:
            page = doc.load_page(0)
            scale = dpi / 72
            pix = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            pix.save(str(out_png))
            doc.close()
            return True
        doc.close()
    except Exception as e:
        log.debug('fitz failed for %s: %s', pdf_path.name, e)

    try:
        from pdf2image import convert_from_path
        images = convert_from_path(str(pdf_path), dpi=dpi, first_page=1, last_page=1)
        if images:
            images[0].save(str(out_png), 'PNG')
            return True
    except Exception as e:
        log.debug('pdf2image failed for %s: %s', pdf_path.name, e)

    return False


def check_citation_closure(content: str, report: CheckReport):
    '''3. 引用闭环（上标 ↔ 参考文献条目）。'''
    m = re.search(
        '(?m)^#{1,3}\\s*(?:参考文献|References)\\s*\\n(.*?)(?=\\n#{1,3}\\s|\\Z)',
        content, re.DOTALL | re.IGNORECASE,
    )
    ref_section = m.group(1) if m else ''

    ref_nums = set()
    for nm in re.finditer('(?m)^\\s*\\[(\\d+)\\]', ref_section):
        ref_nums.add(int(nm.group(1)))

    body = content[:m.start()] if m else content
    cite_nums = set()
    for cm in re.finditer('\\[(\\d+(?:[,\\-]\\s*\\d+)*)\\]', body):
        seg = cm.group(1).replace(' ', '')
        for token in seg.split(','):
            if '-' in token:
                a, b = token.split('-')
                try:
                    cite_nums.update(range(int(a), int(b) + 1))
                except ValueError:
                    continue
            else:
                try:
                    cite_nums.add(int(token))
                except ValueError:
                    continue

    report.stats['正文引用号'] = len(cite_nums)
    report.stats['参考文献条目'] = len(ref_nums)

    if not ref_section and cite_nums:
        report.add_warn(f'正文有 {len(cite_nums)} 个 [N] 引用但缺「参考文献」章节')
        return
    dangling = cite_nums - ref_nums
    unused = ref_nums - cite_nums
    if dangling:
        report.add_warn(f'{len(dangling)} 个悬空引用（无对应参考文献条目）: {sorted(dangling)[:10]}')
    if unused:
        report.add_info(f'{len(unused)} 条参考文献未被正文引用: {sorted(unused)[:10]}')
    return


def check_formula_syntax(content: str, report: CheckReport):
    '''4. 公式语法 — 检查定界符配对。'''
    code_block_re = re.compile('```.*?```', re.DOTALL)
    text_no_code = code_block_re.sub('', content)

    dd_count = len(re.findall('\\$\\$', text_no_code))
    if dd_count % 2 != 0:
        report.add_warn(f'$$ 块级公式定界符数量为奇数（{dd_count}），可能存在未闭合公式')
    else:
        report.stats['块公式数'] = dd_count // 2

    text_no_block = re.sub('\\$\\$[^$]*?\\$\\$', '', text_no_code, flags=re.DOTALL)
    text_no_block = re.sub('\\\\\\$', '', text_no_block)
    single_count = len(re.findall('\\$', text_no_block))
    if single_count % 2 != 0:
        report.add_warn(f'行内 $ 公式定界符数量为奇数（{single_count}），可能存在未闭合公式')
    else:
        report.stats['行内公式数（估）'] = single_count // 2

    open_paren = len(re.findall('\\\\\\(', text_no_code))
    close_paren = len(re.findall('\\\\\\)', text_no_code))
    if open_paren != close_paren:
        report.add_warn(f'\\( 和 \\) 数量不匹配（{open_paren} vs {close_paren}）')

    open_brack = len(re.findall('\\\\\\[', text_no_code))
    close_brack = len(re.findall('\\\\\\]', text_no_code))
    if open_brack != close_brack:
        report.add_warn(f'\\[ 和 \\] 数量不匹配（{open_brack} vs {close_brack}）')
        return
    return


_LATEX_CMD_LIST = [
    'frac', 'sum', 'sqrt', 'prod', 'int', 'lim', 'log', 'ln', 'sin', 'cos', 'tan', 'tanh', 'sinh',
    'cosh', 'exp', 'min', 'max', 'argmax', 'argmin', 'sigma', 'Sigma', 'alpha', 'Alpha', 'beta',
    'Beta', 'gamma', 'Gamma', 'delta', 'Delta', 'epsilon', 'varepsilon', 'theta', 'Theta', 'vartheta',
    'iota', 'kappa', 'lambda', 'Lambda', 'mu', 'nu', 'xi', 'Xi', 'pi', 'Pi', 'rho', 'varrho', 'tau',
    'phi', 'Phi', 'varphi', 'psi', 'Psi', 'omega', 'Omega', 'chi', 'zeta', 'eta', 'partial', 'nabla',
    'infty', 'cdot', 'cdots', 'ldots', 'vdots', 'ddots', 'times', 'div', 'pm', 'mp', 'leq', 'geq',
    'neq', 'approx', 'equiv', 'propto', 'in', 'notin', 'subset', 'subseteq', 'supset', 'cup', 'cap',
    'forall', 'exists', 'to', 'rightarrow', 'leftarrow', 'Leftarrow', 'Rightarrow', 'Leftrightarrow',
    'mapsto', 'land', 'lor', 'wedge', 'vee', 'neg', 'quad', 'qquad', 'left', 'right', 'begin', 'end',
    'operatorname', 'mathbf', 'mathbb', 'mathcal', 'mathrm', 'mathit', 'text', 'hat', 'widehat',
    'tilde', 'widetilde', 'bar', 'overline', 'underline', 'dot', 'ddot', 'vec', 'odot', 'otimes',
    'oplus', 'circ', 'big', 'Big', 'bigg', 'Bigg', 'langle', 'rangle', 'lfloor', 'rfloor', 'binom',
    'matrix', 'pmatrix', 'bmatrix', 'vmatrix', 'cases', 'aligned',
]
_LATEX_CMD_RE = re.compile('\\\\(?:' + '|'.join(_LATEX_CMD_LIST) + ')\\b')
_MATH_STRUCT_RE = re.compile('[_^][{(]')


def normalize_block_math_delimiters(content: str, report: 'CheckReport') -> str:
    '''把"没有独占一行"的块级 $$ 规范成独立行（Pandoc 只把独行 $$ 当块公式起止）。

    真实高频错误（AI 改稿后）：开始的 $$ 被粘在中文句末，例如
        ...亮度偏离中性程度调节：$$ \\omega = \\mathrm{clip}(...)
    Pandoc 认不出这是块公式起始 → 从这里往后整段公式被原样当文本吐进 Word = 乱码。
    （注意：此时 $$ 数量是配对的/偶数，按"未闭合"检测不出来，必须按"是否独占行"来修。）

    修复：按出现顺序给 $$ 配对（第 1、3、5…个=开始，第 2、4…个=结束）：
      - 开始 $$：前面同行若有正文 → 前补空行；后面同行若紧跟公式 → 后补换行（让 $$ 独占一行）。
      - 结束 $$：前面同行若有公式 → 前补换行（公式独立、$$ 行首闭合）；后面的编号 (1) 等保留。
    代码块/行内代码内的 $$ 不处理。
    '''
    holds = []

    def _hold(m):
        holds.append(m.group(0))
        return '\x00%d\x00' % (len(holds) - 1)

    work = re.sub('```[\\s\\S]*?```', _hold, content)
    work = re.sub('`[^`\\n]+`', _hold, work)

    occ = [m.start() for m in re.finditer('(?<!\\\\)\\$\\$', work)]
    if len(occ) < 1:
        return content

    chars = list(work)
    fixes = 0
    for idx in range(len(occ) - 1, -1, -1):
        pos = occ[idx]
        is_open = idx % 2 == 0
        line_start = work.rfind('\n', 0, pos) + 1
        before_seg = work[line_start:pos]
        after_pos = pos + 2
        line_end = work.find('\n', after_pos)
        if line_end == -1:
            line_end = len(work)
        after_seg = work[after_pos:line_end]

        if is_open:
            if after_seg.strip() != '':
                chars.insert(after_pos, '\n')
            if before_seg.strip() != '':
                chars.insert(pos, '\n\n')
                fixes += 1
        elif before_seg.strip() != '':
            chars.insert(pos, '\n')
            fixes += 1

    work2 = ''.join(chars)
    work2 = re.sub('\\x00(\\d+)\\x00', lambda m: holds[int(m.group(1))], work2)

    if fixes > 0:
        report.add_fixed(f'规范 {fixes} 处未独占行的块级 $$（粘在正文里会让 Pandoc 认不出公式→Word 乱码）')
        return work2
    return content


def fix_unclosed_block_math(content: str, report: 'CheckReport') -> str:
    '''修复未闭合 / 跨多行未闭合的 $$ 块公式（AI 改稿后高频错误，会让 Word 整段乱码）。

    典型错误：
        $$ \\omega = \\mathrm{clip}(...)        ← 开了 $$ 但本行没闭合
        \\gamma = \\mathrm{clip}(...)           ← 又一个公式
        其中 ...正文... ![图](figures/x.png)    ← 之前的 $$ 一直没闭合，把正文/图片全吞成公式

    修复：状态机逐行跟踪 $$ 配对；在"块内"遇到明显正文行（空行/中文开头/图片/标题/表格/列表）时，
         在该行之前补一个 $$ 闭合；文末仍未闭合则末尾补 $$。代码块(``` ```)内不处理。
    保守：只在遇到强正文信号时闭合，其余保持块内，尽量不误闭合真公式。
    '''
    lines = content.split('\n')
    out = []
    in_fence = False
    in_math = False
    fixes = 0

    def _is_text_line(s: str) -> bool:
        t = s.strip()
        if t == '':
            return True
        if t.startswith(('![', '#', '|', '>', '<!--', '```')):
            return True
        if re.match('^(\\d+\\.|[-*+])\\s', t):
            return True
        if '一' <= t[0] <= '鿿':
            return True
        return False

    for raw in lines:
        if raw.strip().startswith('```'):
            if in_math:
                out.append('$$')
                in_math = False
                fixes += 1
            in_fence = not in_fence
            out.append(raw)
            continue
        if in_fence:
            out.append(raw)
            continue
        dd = raw.count('$$')
        if in_math:
            if _is_text_line(raw):
                out.append('$$')
                in_math = False
                fixes += 1
                out.append(raw)
                if dd % 2 == 1:
                    in_math = True
                continue
            out.append(raw)
            if dd % 2 == 1:
                in_math = False
            continue
        out.append(raw)
        if dd % 2 == 1:
            in_math = True
    if in_math:
        out.append('$$')
        fixes += 1
    if fixes > 0:
        report.add_fixed(f'修复 {fixes} 处未闭合的 $$ 块公式（防止吞掉后续正文/图片导致 Word 乱码）')
        return '\n'.join(out)
    return content


def auto_wrap_bare_formulas(content: str, report: CheckReport) -> str:
    '''⛔ 自动修复"裸 LaTeX 公式"（AI 写作时未用 $$...$$ 包裹的常见错误）。

    示例：
        前： MA_t^{(k)} = \\frac{1}{k} \\sum_{i=0}^{k-1} P_{t-i} (1)
        后： $$
             MA_t^{(k)} = \\frac{1}{k} \\sum_{i=0}^{k-1} P_{t-i} \\tag{1}
             $$

    这能确保：
    - markdown_to_docx 通过 $$...$$ 识别为 Word 公式（OMML）
    - 前端 markdown 预览通过 KaTeX 渲染
    - 不破坏已经正确写的 $...$ / $$...$$
    '''
    protections = []

    def protect(pattern: str, content: str, marker: str, flags: int = 0) -> str:
        def repl(m: 're.Match') -> str:
            protections.append((marker + str(len(protections)), m.group(0)))
            return '\x00' + protections[-1][0] + '\x00'
        return re.sub(pattern, repl, content, flags=flags)

    text = content
    text = protect('```[\\s\\S]*?```', text, 'CODE')
    text = protect('`[^`\\n]+`', text, 'INLC')
    text = protect('\\$\\$[\\s\\S]*?\\$\\$', text, 'BLOCK')
    text = protect('\\$[^\\n$]+?\\$', text, 'INLINE')

    paragraphs = re.split('(\\n\\s*\\n)', text)
    fix_count = 0
    for i in range(0, len(paragraphs), 2):
        para = paragraphs[i]
        trimmed = para.strip()
        if not trimmed:
            continue
        if re.match('^(\\||>|<)', trimmed):
            continue
        if '\x00CODE' in para:
            continue
        lines = para.split('\n')
        line_groups = []
        for line in lines:
            t = line.strip()
            is_special = False
            if re.match('^#{1,6}\\s', t):
                if len(t) <= 200 and not _LATEX_CMD_RE.search(t) and not re.search('[_^]\\{', t):
                    is_special = True
            elif re.match('^(>\\s|<|\\||[-*+]\\s|\\d+\\.\\s)', t):
                is_special = True
            new_type = 'special' if is_special else 'normal'
            if line_groups and line_groups[-1][0] == new_type:
                line_groups[-1][1].append(line)
            else:
                line_groups.append((new_type, [line]))
        new_groups = []
        para_changed = False
        for grp_type, grp_lines in line_groups:
            sub = '\n'.join(grp_lines)
            if grp_type == 'special':
                new_groups.append(sub)
            else:
                new_sub, n = _wrap_formulas_in_paragraph(sub)
                new_groups.append(new_sub)
                if n > 0:
                    para_changed = True
                    fix_count += n
        if para_changed:
            paragraphs[i] = '\n\n'.join(new_groups)
    text = ''.join(paragraphs)

    def restore(m: 're.Match') -> str:
        marker = m.group(1)
        for mm, original in protections:
            if mm == marker:
                return original
        return m.group(0)

    text = re.sub('\\x00(CODE\\d+|INLC\\d+|BLOCK\\d+|INLINE\\d+)\\x00', restore, text)

    if fix_count > 0:
        report.add_fixed(f'自动包裹 {fix_count} 个裸 LaTeX 公式（用 `$$...$$` 包裹，避免 docx/预览渲染失败）')
    return text


def _wrap_formulas_in_paragraph(para: str) -> tuple[str, int]:
    '''段内识别公式岛屿，wrap 成 $$...$$ 独立段。返回(新段, 修复数量)。'''
    text = para
    formulas = []
    MAX_ITER = 30
    for _ in range(MAX_ITER):
        seed_re = re.compile('\\\\(?:' + '|'.join(_LATEX_CMD_LIST) + ')\\b|[A-Za-z]_\\{|[A-Za-z]\\^\\{')
        seed = seed_re.search(text)
        if not seed:
            break
        start = seed.start()
        end = seed.end()

        formula_char_re = re.compile(
            "[A-Za-z0-9_^{}\\[\\]\\\\=+\\-*/.,;:|()<>!?\\s'\u2018\u2019\u201C\u201D\u00b1\u00d7\u00f7]"
        )
        while start > 0:
            ch = text[start - 1]
            if not formula_char_re.match(ch):
                break
            if ch == '\x00':
                break
            if ch in '，。；！？':
                break
            start -= 1
        while start < end and text[start].isspace():
            start += 1

        brace_depth = 0
        while end < len(text):
            ch = text[end]
            if '一' <= ch <= '鿿':
                if brace_depth > 0:
                    end += 1
                    continue
                break
            if ch == '\x00':
                break
            if ch == '#':
                break
            if ch == '\n':
                rest = text[end + 1:].split('\n')[0] if end + 1 < len(text) else ''
                if any('一' <= c <= '鿿' for c in rest) and brace_depth == 0:
                    break
                if (brace_depth == 0 and not _LATEX_CMD_RE.search(rest)
                        and not _MATH_STRUCT_RE.search(rest) and '\\' not in rest):
                    break
            if ch == '{':
                brace_depth += 1
            elif ch == '}':
                brace_depth = max(0, brace_depth - 1)
            if ch == '(' and brace_depth == 0:
                m = re.match('\\((\\d+(?:\\.\\d+)?)\\)', text[end:])
                if m:
                    after_end = end + len(m.group(0))
                    after_ch = text[after_end] if after_end < len(text) else ''
                    if (after_ch in ('', '\n', ' ') or '一' <= after_ch <= '鿿'
                            or after_ch.isalpha() or after_ch == '\\'):
                        end = after_end
                        break
            end += 1
        while end > start and text[end - 1].isspace():
            end -= 1

        formula_text = text[start:end]
        if not _LATEX_CMD_RE.search(formula_text) and not _MATH_STRUCT_RE.search(formula_text):
            text = text[:start] + '\x01' + text[start + 1:]
            continue

        formula = formula_text
        number = ''
        m = re.match('^(.*?)\\s*(\\((?:\\d+(?:\\.\\d+)?|\\w)\\))\\s*$', formula)
        if m:
            formula = m.group(1).strip()
            number = m.group(2)
        formula = formula.strip()
        if not formula:
            text = text[:start] + '\x01' + text[start + 1:]
            continue
        formulas.append((formula, number))
        placeholder = '\x00FORMULA' + str(len(formulas) - 1) + '\x00'
        text = text[:start] + placeholder + text[end:]

    text = text.replace('\x01', '')
    if not formulas:
        return para, 0

    segments = []
    last = 0
    for m in re.finditer('\\x00FORMULA(\\d+)\\x00', text):
        before = text[last:m.start()]
        if before.strip():
            segments.append(('text', before, ''))
        f, n = formulas[int(m.group(1))]
        segments.append(('formula', f, n))
        last = m.end()
    tail = text[last:]
    if tail.strip():
        segments.append(('text', tail, ''))

    parts = []
    for typ, c, n in segments:
        if typ == 'text':
            parts.append(c.strip())
        elif n:
            tag = n.strip('()')
            parts.append(f'$$\n{c} \\tag{{{tag}}}\n$$')
        else:
            parts.append(f'$$\n{c}\n$$')

    return '\n\n'.join(p for p in parts if p), len(formulas)


def check_latex_residue(content: str, report: CheckReport):
    '''5. LaTeX 残留检测（docx 模式下不应有）。'''
    code_block_re = re.compile('```.*?```', re.DOTALL)
    text_no_code = code_block_re.sub('', content)
    inline_code_re = re.compile('`[^`\\n]+`')
    text_no_code = inline_code_re.sub('', text_no_code)

    fatal_patterns = [
        ('\\\\documentclass', '\\documentclass'),
        ('\\\\begin\\{document\\}', '\\begin{document}'),
        ('\\\\end\\{document\\}', '\\end{document}'),
        ('\\\\maketitle', '\\maketitle'),
    ]
    for pat, name in fatal_patterns:
        if re.search(pat, text_no_code):
            report.add_fatal(f'残留 LaTeX 命令 `{name}`（docx 模式下应使用 Markdown 语法）')

    warn_patterns = [
        ('\\\\section\\{[^}]*\\}', '\\section{}'),
        ('\\\\subsection\\{[^}]*\\}', '\\subsection{}'),
        ('\\\\subsubsection\\{[^}]*\\}', '\\subsubsection{}'),
        ('\\\\begin\\{(equation|align|figure|table|tabular|itemize|enumerate)\\}', '\\begin{...}'),
        ('\\\\end\\{(equation|align|figure|table|tabular|itemize|enumerate)\\}', '\\end{...}'),
        ('\\\\includegraphics', '\\includegraphics'),
        ('\\\\cite\\{', '\\cite{}'),
        ('\\\\ref\\{', '\\ref{}'),
        ('\\\\label\\{', '\\label{}'),
        ('\\\\caption\\{', '\\caption{}'),
    ]
    found_warn = {}
    for pat, name in warn_patterns:
        cnt = len(re.findall(pat, text_no_code))
        if cnt > 0:
            found_warn[name] = cnt
    for name, cnt in found_warn.items():
        report.add_warn(f'{cnt} 处残留 LaTeX 标记 `{name}`（docx 转换可能不完整）')
    return


def check_table_format(content: str, report: CheckReport):
    '''6. Markdown 表格格式（每行列数一致 + 必须有分隔行）。'''
    lines = content.split('\n')
    in_table = False
    table_lines = []
    table_count = 0
    issues = []

    def _validate_table(rows: list[tuple[int, str]]) -> str | None:
        if len(rows) < 2:
            return f'第 {rows[0][0]} 行起的表格行数不足（需要表头 + 分隔行 + 数据行）'
        sep_row = rows[1][1]
        if not re.match('^\\s*\\|[\\s\\-:|]+\\|\\s*$', sep_row):
            return f'第 {rows[1][0]} 行不是合法分隔行（需要 `|---|---|` 形式）'
        col_counts = []
        for line_no, ln in rows:
            cells = [c for c in ln.strip().strip('|').split('|')]
            col_counts.append(len(cells))
        if len(set(col_counts)) > 1:
            return f'第 {rows[0][0]} 行起的表格列数不一致：{col_counts}'
        return None

    for i, line in enumerate(lines, 1):
        if line.strip().startswith('|'):
            if not in_table:
                in_table = True
                table_lines = []
            table_lines.append((i, line))
            continue
        if in_table:
            table_count += 1
            err = _validate_table(table_lines)
            if err:
                issues.append(err)
            in_table = False
            table_lines = []
    if in_table:
        table_count += 1
        err = _validate_table(table_lines)
        if err:
            issues.append(err)

    report.stats['Markdown 表格数'] = table_count
    for err in issues:
        report.add_warn(err)
    return


def check_heading_levels(content: str, report: CheckReport):
    '''7. 标题层级（不跳级）。'''
    code_block_re = re.compile('```.*?```', re.DOTALL)
    text_no_code = code_block_re.sub('', content)
    headings = []
    for i, line in enumerate(text_no_code.split('\n'), 1):
        m = re.match('^(#{1,6})\\s+(.+)$', line)
        if m:
            headings.append((i, len(m.group(1)), m.group(2).strip()))
    if not headings:
        return
    levels = [h[1] for h in headings]
    report.stats['标题数'] = len(headings)
    report.stats['最高级别'] = f'H{min(levels)}'
    report.stats['最低级别'] = f'H{max(levels)}'

    prev = 0
    for line_no, level, title in headings:
        if prev > 0 and level > prev + 1:
            report.add_warn(
                f'第 {line_no} 行 H{level} 标题「{title[:25]}」从 H{prev} 跳级（建议中间加 H{prev + 1}）'
            )
        prev = level
    return


def check_word_count(content: str, report: CheckReport, target: int | None = None):
    '''8. 字数统计（去除图片、引用、代码块）。'''
    text = re.sub('```.*?```', '', content, flags=re.DOTALL)
    text = re.sub('!\\[[^\\]]*\\]\\([^)]+\\)', '', text)
    text = re.sub('\\[[\\d,\\-\\s]+\\]', '', text)
    text = re.sub('\\[([^\\]]+)\\]\\([^)]+\\)', '\\1', text)
    text = re.sub('\\s+', '', text)
    char_count = len(text)
    report.stats['正文字数（去除图片/引用/代码）'] = char_count
    if target:
        low = int(target * 0.8)
        high = int(target * 1.2)
        if char_count < low:
            report.add_warn(f'字数 {char_count} 低于目标 {target} 的 80%（< {low}）')
            return
        if char_count > high:
            report.add_warn(f'字数 {char_count} 高于目标 {target} 的 120%（> {high}）')
            return
        report.add_info(f'字数 {char_count} 在目标范围 [{low}, {high}] 内')
    return


def check_markdown_noise(content: str, report: CheckReport):
    '''9. 残留 Markdown 噪声（过多 ** 加粗等）。'''
    code_block_re = re.compile('```.*?```', re.DOTALL)
    text = code_block_re.sub('', content)
    bold_count = len(re.findall('\\*\\*[^*\\n]+\\*\\*', text))
    if bold_count > 30:
        report.add_info(f'正文中 {bold_count} 处 **加粗**，过多可能影响阅读体验')
        return
    return


def check_html_comment_residue(content: str, report: CheckReport) -> str:
    '''⛔ 检查并自动剥除 HTML 注释残留（如 <!-- label: tab:xxx -->）。

    背景：
    - stats_utils.py / paper-figure SKILL.md / course_docx_table_md.md 教 AI 在表格下面写
      `<!-- label: tab:model_perf -->` 作为软 label（markdown 没原生 label，留作回查）
    - 这种注释 docx 引擎可能不剥离，会原样渲染到 Word 里，看起来非常 AI
    - md_to_docx.js 现在也会剥（治本），但这里再加一道防线（确保 Python 侧的 precheck 输出
      也是干净的，给写作步骤的 docx-format-check 看到的不是带注释的版本）

    本函数自动剥除所有 `<!-- ... -->` 注释（保护代码块内的不动），并给出统计 warning。
    '''
    protections = []

    def _protect(m: 're.Match') -> str:
        protections.append(m.group(0))
        return '\x00CODEBLK' + str(len(protections) - 1) + '\x00'

    text = re.sub('```[\\s\\S]*?```', _protect, content)
    text = re.sub('(?<!`)`[^`\\n]+?`(?!`)', _protect, text)

    matches = re.findall('<!--[\\s\\S]*?-->', text)
    if matches:
        label_count = sum(1 for m in matches if re.search('<!--\\s*label\\s*:', m, re.I))
        other_count = len(matches) - label_count
        text = re.sub('<!--[\\s\\S]*?-->', '', text)
        text = re.sub('\\n{3,}', '\n\n', text)

    def _restore(m: 're.Match') -> str:
        idx = int(m.group(1))
        return protections[idx] if idx < len(protections) else m.group(0)

    new_content = re.sub('\\x00CODEBLK(\\d+)\\x00', _restore, text)

    if matches:
        if label_count > 0 and other_count > 0:
            msg = (
                f'自动剥除 {len(matches)} 处 HTML 注释（{label_count} 处 `<!-- label: ... -->` '
                f'软 label + {other_count} 处其他）— Word 里不应出现'
            )
        elif label_count > 0:
            msg = f'自动剥除 {label_count} 处 `<!-- label: tab:xxx -->` 软 label 注释 — Word 里不应出现，应只在源 md 内部使用'
        else:
            msg = f'自动剥除 {other_count} 处 HTML 注释（Word 里不应出现）'
        report.add_fixed(msg)

    return new_content


_LATEX_TABLE_PATTERNS = (
    ('\\\\begin\\{tabular\\}', '\\begin{tabular}'),
    ('\\\\end\\{tabular\\}', '\\end{tabular}'),
    ('\\\\begin\\{table\\*?\\}', '\\begin{table}'),
    ('\\\\begin\\{longtable\\}', '\\begin{longtable}'),
    ('\\\\toprule', '\\toprule'),
    ('\\\\midrule', '\\midrule'),
    ('\\\\bottomrule', '\\bottomrule'),
    ('\\\\input\\{[^}]*figures/TABLE_[^}]+\\}', '\\input{figures/TABLE_*.tex}'),
    ('\\\\input\\{figures/[^}]*\\.tex\\}', '\\input{figures/*.tex}'),
)


def check_latex_table_residue(content: str, report: CheckReport):
    '''检测正文中残留的 LaTeX 表格代码 — Word 不会渲染，必须 fatal 后让 AI 重写。'''
    text = re.sub('```[\\s\\S]*?```', '', content)
    text = re.sub('`[^`\\n]+`', '', text)
    text = re.sub('\\$\\$[\\s\\S]*?\\$\\$', '', text)
    text = re.sub('\\$[^\\n$]+?\\$', '', text)

    found = []
    for pat, name in _LATEX_TABLE_PATTERNS:
        cnt = len(re.findall(pat, text))
        if cnt > 0:
            found.append((name, cnt))

    if found:
        detail_lines = ['正文中残留 LaTeX 表格代码（Word 不会渲染成表格，必须改写为 Markdown 三线表）：']
        for name, cnt in found:
            detail_lines.append(f'  - `{name}` × {cnt}')
        detail_lines.append('')
        detail_lines.append('修复方法：')
        detail_lines.append('  1. 找到对应的 `figures/TABLE_*.md`（paper-figure 步骤已自动生成 Markdown 版本）')
        detail_lines.append('  2. 把 LaTeX 表格代码替换为 `cat figures/TABLE_xxx.md` 的内容')
        detail_lines.append('  3. 或手写 Markdown 三线表（| 表头 |\\n|---|---|\\n| 数据 |）')
        report.add_fatal('\n'.join(detail_lines))
    return


def check_figure_caption_quality(content: str, report: CheckReport) -> str:
    '''⛔ 图题（alt 文字）质量检查 + 自动修复

    问题来源：AI 在 markdown 里写 `![图 X 巨长说明含 $Q_t$ 公式](path)` 时：
    - LaTeX 模式 `\\caption{}` 会渲染公式 → PDF 看着没事
    - Word 模式 alt 走纯文本路径 → `$Q_t$` 原样出现，看着非常 AI

    本函数做两件事：
    1. **自动剥公式**：把 caption 里的 `$...$` 行内公式整体删除（替换成空），写回 content
    2. **超长警告**：caption 超过 30 个中文字符时给 warn，提示移到正文

    返回（可能修改过的）content。

    边缘情况处理：
    - 跳过代码块（``` ... ```）和行内代码（`...`）里的图题示例（避免错改文档示例）
    - 同时剥除 `$$...$$` 块公式语法（AI 偶尔在 alt 里误写）
    - 转义美元符号 `\\$` 不当作公式
    - 空 alt / 只含空格的 alt 安全处理
    '''
    fixed_count = 0
    formula_alts = []
    long_alts = []
    protections = []

    def _protect(m: 're.Match') -> str:
        protections.append(m.group(0))
        return '\x00CODE' + str(len(protections) - 1) + '\x00'

    text = re.sub('```[\\s\\S]*?```', _protect, content)
    text = re.sub('(?<!`)`[^`\\n]+?`(?!`)', _protect, text)

    pattern = re.compile('!\\[([^\\]]*)\\]\\(([^)]+)\\)')

    long_alts.clear()
    fixed_count = 0
    formula_alts.clear()

    def _process(m: 're.Match') -> str:
        nonlocal fixed_count
        alt_raw = m.group(1)
        path_part = m.group(2)
        new_alt = alt_raw

        block_re = re.compile('(?<!\\\\)\\$\\$[^$\\n]*?(?<!\\\\)\\$\\$')
        if block_re.search(new_alt):
            formula_alts.append(alt_raw[:60])
            new_alt = block_re.sub('', new_alt)

        formula_re = re.compile('(?<!\\\\)\\$[^$\\n]+?(?<!\\\\)\\$')
        if formula_re.search(new_alt):
            if alt_raw[:60] not in formula_alts:
                formula_alts.append(alt_raw[:60])
            new_alt = formula_re.sub('', new_alt)

        new_alt = re.sub('(?<!\\\\)\\$+', '', new_alt)
        new_alt = re.sub('\\s{2,}', ' ', new_alt)
        new_alt = re.sub('(?:与\\s|和\\s|及\\s)$', '', new_alt.strip())
        new_alt = new_alt.strip(' ：:，,;；')

        char_len = len(new_alt)
        if char_len > 30:
            long_alts.append((new_alt[:60], char_len))
        if new_alt != alt_raw:
            fixed_count += 1
        return f'![{new_alt}]({path_part})'

    text = pattern.sub(_process, text)

    def _restore(m: 're.Match') -> str:
        idx = int(m.group(1))
        return protections[idx] if idx < len(protections) else m.group(0)

    new_content = re.sub('\\x00CODE(\\d+)\\x00', _restore, text)

    if formula_alts:
        report.add_fixed(
            f'自动从 {len(formula_alts)} 个图题中剥除了行内公式 `$...$`（Word 不渲染图题里的公式）：'
            + '\n'.join(f'    - `{a}...`' for a in formula_alts[:5])
        )
    if long_alts:
        details = '\n'.join(f'    - {alt}（{n} 字）' for alt, n in long_alts[:5])
        report.add_warn(
            f'{len(long_alts)} 个图题超过 30 字符（建议 ≤15）。详细描述应放在正文段落，图题保留为短标签：\n{details}'
        )

    return new_content


def run_precheck(source_md: Path, workspace: Path | None = None, word_count_target: int | None = None) -> CheckReport:
    if workspace is None:
        workspace = source_md.parent
    report = CheckReport(source_md)

    if not check_file_existence(source_md, report):
        return report

    try:
        content = _read_md(source_md)
    except ValueError as e:
        report.add_fatal(str(e))
        return report

    # 自动修复：块级 $$ 规范化 / 未闭合 $$ / 裸公式包裹
    content = normalize_block_math_delimiters(content, report)
    content = fix_unclosed_block_math(content, report)
    fixed_content = auto_wrap_bare_formulas(content, report)
    content = fixed_content

    # 图表闭环（自动修复 PDF→PNG）+ 图题质量 + HTML 注释剥除
    content = check_figure_closure(content, workspace, report)
    content = check_figure_caption_quality(content, report)
    content = check_html_comment_residue(content, report)

    content_changed = content != _read_md_safe(source_md)

    # 只读检查
    check_citation_closure(content, report)
    check_formula_syntax(content, report)
    check_latex_residue(content, report)
    check_latex_table_residue(content, report)
    check_table_format(content, report)
    check_heading_levels(content, report)
    check_word_count(content, report, word_count_target)
    check_markdown_noise(content, report)

    if content_changed:
        try:
            with open(source_md, 'w', encoding='utf-8', newline='\n') as _wf:
                _wf.write(content)
            report.add_info(f'已将修复后的内容写回 `{source_md.name}`')
        except Exception as e:
            report.add_warn(f'修复内容写回失败：{e}（docx 导出将仍按原内容进行）')

    return report


def _read_md_safe(path: Path) -> str:
    '''安全读取 .md（用于检测内容变化）。'''
    try:
        return path.read_text(encoding='utf-8')
    except Exception:
        return ''


def main():
    parser = argparse.ArgumentParser(description='DOCX 导出前的 Markdown 质量校核')
    parser.add_argument('--source', '-s', type=Path, required=True, help='源 Markdown 文件')
    parser.add_argument('--workspace', '-w', type=Path, default=None, help='工作区根目录')
    parser.add_argument('--report', '-r', type=Path, default=None, help='校核报告输出路径（默认在源文件同目录的 QUALITY_REPORT.md）')
    parser.add_argument('--word-count', type=int, default=None, help='目标字数（用于范围检查）')
    parser.add_argument('--fail-on-fatal', action='store_true', default=True, help='存在致命错误时退出码非零（默认开启）')
    parser.add_argument('--no-fail-on-fatal', dest='fail_on_fatal', action='store_false')
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')

    workspace = args.workspace or args.source.parent
    report = run_precheck(args.source, workspace, args.word_count)
    report_path = args.report or workspace / 'QUALITY_REPORT.md'
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report.render(), encoding='utf-8')

    print(
        f'✓ 校核完成 — 致命:{len(report.fatal)} / 警告:{len(report.warnings)}'
        f' / 修复:{len(report.fixed)} / 信息:{len(report.info)}'
    )
    print(f'  详细报告: {report_path}')

    if report.fatal and args.fail_on_fatal:
        sys.exit(2)
    sys.exit(0)


if __name__ == '__main__':
    main()
