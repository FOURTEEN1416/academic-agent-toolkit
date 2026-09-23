#!/usr/bin/env node
/**
 * md_to_docx.js — Markdown → DOCX 转换器（中文学术格式）
 * 基于 docx.js 库，支持公式、三线表、自动编号、上标引用、参考文献。
 *
 * 用法：
 *   node md_to_docx.js --source paper.md --output paper.docx [--workspace .]
 */

'use strict';

const fs = require('fs');
const path = require('path');

const docx = require('docx');
const {
  Document, Packer,
  Paragraph, TextRun,
  Footer,
  PageNumber, AlignmentType, LineRuleType, HeadingLevel,
  BorderStyle, WidthType, ShadingType, VerticalAlign,
  ImageRun,
  Table, TableRow, TableCell, TableLayoutType,
  MathRun,
} = docx;
const DocxMath = docx.Math;

const { mathmlToDocxChildren } = require('./mathml-to-docx');
const temml = require('temml');

// 常量
const PAGE_W = 11906;
const PAGE_H = 16838;

const THICK = { style: BorderStyle.SINGLE, size: 12, color: '000000' };
const THIN  = { style: BorderStyle.SINGLE, size: 6,  color: '000000' };
const NONE  = { style: BorderStyle.NONE,   size: 0,  color: 'FFFFFF' };

let _chapter = 0;

// 默认样式参数（与 LaTeX cumcmthesis.cls 对标：A4, 25mm, 12pt SimSun, 1.5 倍行距, 2em 首行缩进）
const DEFAULT_PROFILE = {
  page: { margin_top_cm: 2.5, margin_bottom_cm: 2.5, margin_left_cm: 2.5, margin_right_cm: 2.5 },
  fonts: { chinese_heading: 'SimHei', chinese_body: 'SimSun', latin: 'Times New Roman', monospace: 'Consolas' },
  body: { font_size_pt: 12, line_spacing: 1.5, first_line_indent_chars: 2 },
  headings: { level1_pt: 16, level2_pt: 14, level3_pt: 12, level4_pt: 11, bold: true,
              level1_alignment: 'center', level2_alignment: 'left', level3_alignment: 'left' },
  table: { font_size_pt: 10.5, header_bold: true, top_border_pt: 1.5, header_border_pt: 0.75, bottom_border_pt: 1.5 },
  references: { hanging_indent_cm: 0.74, font_size_pt: 10.5 },
  abstract: { label_size_pt: 14, body_size_pt: 12, label_bold: true, label_alignment: 'center' },
  keywords: { label_size_pt: 12, label_bold: true, font: 'SimHei' },
  code_block: { font_size_pt: 9, line_spacing: 1.0, background_color: 'F5F5F5' },
};

let PROFILE = JSON.parse(JSON.stringify(DEFAULT_PROFILE));

// 辅助函数：pt → half-points（docx.js 用半磅作字号单位）
const pt2half = (pt) => Math.round(pt * 2);
// pt → twips（用于行距和字符间距）
const pt2twips = (pt) => Math.round(pt * 20);
// 行距倍数 → 240ths（AUTO 模式 line 字段单位 = 1/240 倍数，240=1.0 倍）
// ⛔ v1.4.3 修复：旧公式 `mul * baseSize * 20` 在 baseSize≠12 时把"倍数"算成绝对 twip，
// 配 LineRuleType.AUTO 时被 Word 解释为 (mul*baseSize*20)/240 = mul*baseSize/12 倍 → 标题行距巨大
// 新公式：忽略 baseSize（保留参数仅为向后兼容签名），统一返回 mul × 240
// 旧调用方影响（baseSize=12 不变；baseSize≠12 行距变小到正确值）：
//   body 12pt × 1.5 → 之前 360 / 改后 360 = 1.5 倍（不变）
//   h2 18pt × 1.5 → 之前 540 (2.25倍) / 改后 360 = 1.5 倍（修正）
//   code 9pt × 1.0 → 之前 180 (0.75倍) / 改后 240 = 1.0 倍（修正过紧）
//   refs 10.5pt × 1.25 → 之前 262 (1.09倍) / 改后 300 = 1.25 倍（修正过紧）
const lineMul = (mul, _baseSize) => Math.round(mul * 240);
// cm → twips
const cm2twips = (cm) => Math.round(cm * 567);

// 页面正文总宽（twips）：A4 21cm - 左右边距。按 PROFILE 实时算，替代写死的 CONTENT_W。
function contentWidthTwips() {
  const left = PROFILE.page.margin_left_cm != null ? PROFILE.page.margin_left_cm : 2.5;
  const right = PROFILE.page.margin_right_cm != null ? PROFILE.page.margin_right_cm : 2.5;
  return PAGE_W - cm2twips(left) - cm2twips(right);
}
// 栏数（默认 1）
function columnCount() {
  const n = parseInt(PROFILE.page.columns, 10);
  return Number.isFinite(n) && n >= 2 ? n : 1;
}
// 单栏可用宽（twips）：双栏时 = (正文宽 - 栏间距×(n-1)) / n；单栏时 = 正文宽。
// 表格/图片都缩到这个宽度，防止双栏下冲破栏界。
function colBodyWidthTwips() {
  const n = columnCount();
  const total = contentWidthTwips();
  if (n < 2) return total;
  const spacing = cm2twips(PROFILE.page.column_spacing_cm != null ? PROFILE.page.column_spacing_cm : 0.6);
  return global.Math.floor((total - spacing * (n - 1)) / n);
}
// 首行缩进（按字符数 × 字号，1 字 = 字号 pt × 20 twips/pt）
const firstLineTwips = (chars, sizePt) => Math.round(chars * sizePt * 20);

// 加载 profile JSON 并合并到全局 PROFILE
function loadProfile(profilePath) {
  if (!profilePath || !fs.existsSync(profilePath)) return;
  try {
    const data = JSON.parse(fs.readFileSync(profilePath, 'utf-8'));
    PROFILE = deepMerge(DEFAULT_PROFILE, data);
  } catch (e) {
    console.error('Failed to load profile:', e.message);
  }
}

function deepMerge(base, override) {
  const out = { ...base };
  for (const k of Object.keys(override)) {
    if (override[k] && typeof override[k] === 'object' && !Array.isArray(override[k])
        && base[k] && typeof base[k] === 'object' && !Array.isArray(base[k])) {
      out[k] = deepMerge(base[k], override[k]);
    } else {
      out[k] = override[k];
    }
  }
  return out;
}

// CLI 参数解析
function parseArgs() {
  const args = { source: null, output: null, workspace: null, profile: null };
  const argv = process.argv.slice(2);
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--source' || argv[i] === '-s') args.source = argv[++i];
    else if (argv[i] === '--output' || argv[i] === '-o') args.output = argv[++i];
    else if (argv[i] === '--workspace' || argv[i] === '-w') args.workspace = argv[++i];
    else if (argv[i] === '--profile' || argv[i] === '-p') args.profile = argv[++i];
  }
  if (!args.source || !args.output) {
    console.error('Usage: node md_to_docx.js --source <md> --output <docx> [--workspace <dir>] [--profile <json>]');
    process.exit(1);
  }
  args.workspace = args.workspace || path.dirname(args.source);
  return args;
}


// 清理行内 Markdown 标记 + 修正 LaTeX 风格引号 + ASCII 直引号 → 中文弯引号
function cleanInline(text) {
  return text
    // 先处理 LaTeX 风格的引号（在 inline code 之前，避免反引号被误处理）
    .replace(/``([^`'\n]+?)''/g, '\u201c$1\u201d')  // ``...'' → "..."
    .replace(/(^|[\s（(])`([^`'\n]+?)'(?=[\s，。、；：！？)）]|$)/g, '$1\u2018$2\u2019')  // `...' → '...'（避免误吞 inline code）
    .replace(/\*\*(.+?)\*\*/g, '$1')
    .replace(/__(.+?)__/g, '$1')
    .replace(/(?<!\*)\*(?!\*)([^*\n]+)\*(?!\*)/g, '$1')
    .replace(/`([^`]+)`/g, '$1')
    .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
    // ⛔ ASCII 直引号 → 中文弯引号 (仅在中文上下文)
    // 必须在去除 markdown 后做, 避免误改 [text](url) 里的引号
    // 启发式: 引号内或外侧 80 字符内有中文/中文标点 → 中文弯引号; 否则保留 ASCII (代码/英文)
    .replace(/"([^"\n]{1,500}?)"/g, function (match, inner) {
      // offset 处获取上下文判断
      var idx = arguments[arguments.length - 2];
      var src = arguments[arguments.length - 1];
      // 1. 引号内含中文/中文标点 → 转
      if (/[\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]/.test(inner)) {
        return '\u201c' + inner + '\u201d';
      }
      // 2. 引号外侧 ±60 字符有中文 → 转 (例如 '"abc"研究')
      var leftCtx = src.substring(Math.max(0, idx - 60), idx);
      var rightCtx = src.substring(idx + match.length, idx + match.length + 60);
      if (/[\u4e00-\u9fa5]/.test(leftCtx) || /[\u4e00-\u9fa5]/.test(rightCtx)) {
        return '\u201c' + inner + '\u201d';
      }
      return match;
    })
    // 单引号同理 (但要避免误改英文 it's / don't)
    .replace(/'([^'\n]{1,500}?)'/g, function (match, inner) {
      var idx = arguments[arguments.length - 2];
      var src = arguments[arguments.length - 1];
      if (/[\u4e00-\u9fa5\u3000-\u303f\uff00-\uffef]/.test(inner)) {
        return '\u2018' + inner + '\u2019';
      }
      var leftCtx = src.substring(Math.max(0, idx - 60), idx);
      var rightCtx = src.substring(idx + match.length, idx + match.length + 60);
      if (/[\u4e00-\u9fa5]/.test(leftCtx) || /[\u4e00-\u9fa5]/.test(rightCtx)) {
        return '\u2018' + inner + '\u2019';
      }
      return match;
    })
    .trim();
}

// 行内公式 + 上标引用解析
// textStyle: 可选，给纯文本 TextRun 应用的样式（字体/字号/加粗/颜色），公式 / 上标节点不受影响
function parseInlineWithMath(text, textStyle) {
  const parts = [];
  const ts = textStyle || {};
  // 支持四种公式定界符：
  //   $...$       （Markdown 风格行内）
  //   \(...\)     （LaTeX 原生行内）
  //   $$...$$     （Markdown 风格块级，单行）
  //   [n] / [1,2] / [1-3]  （上标引用，纯数字方括号）
  //   <sup>...</sup>       （HTML 上标）
  //   <sub>...</sub>       （HTML 下标）
  // 注意 \\(...\\) 在 JS 字符串里要写 \\\\(...
  const re = /(\$\$[^$\n]+\$\$)|(\$[^$\n]+\$)|(\\\([^)]+?\\\))|(\\\[[^\]]+?\\\])|(\[\d+(?:[,\-]\d+)*\])|(<sup>[\s\S]*?<\/sup>)|(<sub>[\s\S]*?<\/sub>)/gi;
  let lastIdx = 0;
  let m;

  const renderMath = (latex, displayMode) => {
    try {
      const mathml = temml.renderToString(latex, { displayMode, throwOnError: false });
      const kids = mathmlToDocxChildren(mathml);
      if (kids && kids.length) {
        return new DocxMath({ children: kids });
      }
      return new DocxMath({ children: [new MathRun(latex)] });
    } catch (e) {
      return new DocxMath({ children: [new MathRun(latex)] });
    }
  };

  const makeTextRun = (txt, extraStyle) => new TextRun({
    text: cleanInline(txt),
    color: '000000',
    ...ts,
    ...(extraStyle || {}),
  });

  while ((m = re.exec(text)) !== null) {
    if (m.index > lastIdx) {
      parts.push(makeTextRun(text.slice(lastIdx, m.index)));
    }
    if (m[1]) {
      // $$...$$ → 块公式（在行内还原成行内显示）
      parts.push(renderMath(m[1].slice(2, -2), false));
    } else if (m[2]) {
      // $...$ → 行内
      parts.push(renderMath(m[2].slice(1, -1), false));
    } else if (m[3]) {
      // \(...\) → 行内
      parts.push(renderMath(m[3].slice(2, -2), false));
    } else if (m[4]) {
      // \[...\] → 块（在行内显示）
      parts.push(renderMath(m[4].slice(2, -2), false));
    } else if (m[5]) {
      // 上标引用 [n] — 强制 superScript，但保留字体/字号
      parts.push(makeTextRun(m[5], { superScript: true }));
    } else if (m[6]) {
      // <sup>...</sup> HTML 上标 — 提取内部文本作为上标 (Claude 常输出 <sup>[2]</sup>)
      const _supInner = m[6].replace(/^<sup>/i, '').replace(/<\/sup>$/i, '');
      parts.push(makeTextRun(_supInner, { superScript: true }));
    } else if (m[7]) {
      // <sub>...</sub> HTML 下标
      const _subInner = m[7].replace(/^<sub>/i, '').replace(/<\/sub>$/i, '');
      parts.push(makeTextRun(_subInner, { subScript: true }));
    }
    lastIdx = m.index + m[0].length;
  }
  if (lastIdx < text.length) {
    parts.push(makeTextRun(text.slice(lastIdx)));
  }
  if (parts.length === 0) parts.push(makeTextRun(text));
  return parts;
}

function bodyPara(text) {
  const fontPt = PROFILE.body.font_size_pt;
  const lineMulValue = PROFILE.body.line_spacing;
  const indentChars = PROFILE.body.first_line_indent_chars;
  return new Paragraph({
    children: parseInlineWithMath(text),
    indent: { firstLine: firstLineTwips(indentChars, fontPt) },
    spacing: { line: lineMul(lineMulValue, fontPt), lineRule: LineRuleType.AUTO },
  });
}

// 摘要正文行内解析：把 **加粗** 段解析成 bold 的 run，其余段正常；
// 加粗段内部仍走 parseInlineWithMath（公式/上下标照常渲染，文本 run 叠加 bold）。
// 与 python 侧 _add_runs_with_inline_bold 对齐（同样的 .+? 非贪婪切分）。仅摘要正文用。
function parseAbstractInline(text) {
  const out = [];
  const parts = text.split(/(\*\*.+?\*\*)/);
  for (const seg of parts) {
    if (!seg) continue;
    const m = seg.match(/^\*\*(.+?)\*\*$/);
    if (m) {
      // 加粗段：textStyle 传 {bold:true}，makeTextRun 会把文本 run 设为加粗；公式 run 不受影响
      for (const child of parseInlineWithMath(m[1], { bold: true })) out.push(child);
    } else {
      for (const child of parseInlineWithMath(seg)) out.push(child);
    }
  }
  if (out.length === 0) {
    for (const child of parseInlineWithMath(text)) out.push(child);
  }
  return out;
}

// 摘要正文段落：段落格式与 bodyPara 完全一致（首行缩进/行距），仅 children 换成
// 支持 **加粗** 的 parseAbstractInline。用于竞赛摘要加粗关键方法名/关键结果数值。
function abstractBodyPara(text) {
  const fontPt = PROFILE.body.font_size_pt;
  const lineMulValue = PROFILE.body.line_spacing;
  const indentChars = PROFILE.body.first_line_indent_chars;
  return new Paragraph({
    children: parseAbstractInline(text),
    indent: { firstLine: firstLineTwips(indentChars, fontPt) },
    spacing: { line: lineMul(lineMulValue, fontPt), lineRule: LineRuleType.AUTO },
  });
}

function h1(text, isFirst) {
  _chapter++;
  const titleCfg = PROFILE.title || {};
  // 第一个 H1 用 title 样式（论文标题，居中、加粗），替代封面
  // 字号 / 行距 / 段前段后 都从 titleCfg 读，让各 profile 可控
  if (isFirst && titleCfg) {
    const sizePt = titleCfg.font_size_pt || 22;
    const align = titleCfg.alignment === 'left' ? AlignmentType.LEFT : AlignmentType.CENTER;
    // ⛔ 行距：用 240ths（AUTO 模式 line 字段单位 = 1/240 倍数，240=1.0倍）
    // 之前 lineMul(mul, sizePt) = mul*sizePt*20，在 22pt × 1.5 时返回 660 → Word 解释为 660/240 = 2.75 倍行距 → 标题两行间距巨大
    const lineSpacing = titleCfg.line_spacing || 1.15;
    const lineTwentieths = Math.round(lineSpacing * 240);
    // 段前段后：默认 12pt / 6pt（240/120 twip），原 480/360 让标题占用过大空间
    const spaceBeforeTwip = (titleCfg.space_before_pt != null ? titleCfg.space_before_pt : 12) * 20;
    const spaceAfterTwip = (titleCfg.space_after_pt != null ? titleCfg.space_after_pt : 6) * 20;
    return new Paragraph({
      heading: HeadingLevel.HEADING_1,
      indent: { firstLine: 0 },
      alignment: align,
      spacing: { before: spaceBeforeTwip, after: spaceAfterTwip, line: lineTwentieths, lineRule: LineRuleType.AUTO },
      children: [new TextRun({
        text: cleanInline(text),
        bold: titleCfg.bold !== false,
        font: { ascii: PROFILE.fonts.latin,
                eastAsia: titleCfg.font_family || PROFILE.fonts.chinese_heading,
                hAnsi: PROFILE.fonts.latin },
        size: pt2half(sizePt),
        color: '000000',
      })],
    });
  }
  const sizePt = PROFILE.headings.level1_pt;
  const align = PROFILE.headings.level1_alignment === 'left' ? AlignmentType.LEFT : AlignmentType.CENTER;
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    indent: { firstLine: 0 },
    alignment: align,
    spacing: { before: 240, after: 120, line: lineMul(PROFILE.body.line_spacing, sizePt), lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text), bold: !!PROFILE.headings.bold,
      font: { ascii: PROFILE.fonts.latin, eastAsia: PROFILE.fonts.chinese_heading, hAnsi: PROFILE.fonts.latin },
      size: pt2half(sizePt),
      color: '000000',
    })],
  });
}

function h2(text) {
  const sizePt = PROFILE.headings.level2_pt;
  const align = PROFILE.headings.level2_alignment === 'center' ? AlignmentType.CENTER : AlignmentType.LEFT;
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    indent: { firstLine: 0 },
    alignment: align,
    spacing: { before: 180, after: 90, line: lineMul(PROFILE.body.line_spacing, sizePt), lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text), bold: !!PROFILE.headings.bold,
      font: { ascii: PROFILE.fonts.latin, eastAsia: PROFILE.fonts.chinese_heading, hAnsi: PROFILE.fonts.latin },
      size: pt2half(sizePt),
      color: '000000',
    })],
  });
}

function h3(text) {
  const sizePt = PROFILE.headings.level3_pt;
  const align = PROFILE.headings.level3_alignment === 'center' ? AlignmentType.CENTER : AlignmentType.LEFT;
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    indent: { firstLine: 0 },
    alignment: align,
    spacing: { before: 120, after: 60, line: lineMul(PROFILE.body.line_spacing, sizePt), lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text), bold: !!PROFILE.headings.bold,
      font: { ascii: PROFILE.fonts.latin, eastAsia: PROFILE.fonts.chinese_heading, hAnsi: PROFILE.fonts.latin },
      size: pt2half(sizePt),
      color: '000000',
    })],
  });
}

// H4/H5/H6 共用样式
function h4(text) {
  const sizePt = PROFILE.headings.level4_pt || 11;
  return new Paragraph({
    heading: HeadingLevel.HEADING_4,
    indent: { firstLine: 0 },
    alignment: AlignmentType.LEFT,
    spacing: { before: 100, after: 50, line: lineMul(PROFILE.body.line_spacing, sizePt), lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text), bold: !!PROFILE.headings.bold,
      font: { ascii: PROFILE.fonts.latin, eastAsia: PROFILE.fonts.chinese_heading, hAnsi: PROFILE.fonts.latin },
      size: pt2half(sizePt),
      color: '000000',
    })],
  });
}

function threeLineTable(headers, rows) {
  const colCount = headers.length;
  // ⛔ 双栏时表宽必须锁到单栏栏宽，否则冲破栏界。colBodyWidthTwips 单栏=正文宽（无回归）。
  const tableW = colBodyWidthTwips();
  const colW = global.Math.floor(tableW / colCount);
  const colWidths = Array(colCount).fill(colW);
  colWidths[colCount - 1] = tableW - colW * (colCount - 1);

  const tableFontPt = PROFILE.table.font_size_pt;
  const headerBold = PROFILE.table.header_bold !== false;
  const topSize = Math.round(PROFILE.table.top_border_pt * 8);
  const headerSize = Math.round(PROFILE.table.header_border_pt * 8);
  const bottomSize = Math.round(PROFILE.table.bottom_border_pt * 8);
  const THICK_T = { style: BorderStyle.SINGLE, size: topSize, color: '000000' };
  const THIN_T = { style: BorderStyle.SINGLE, size: headerSize, color: '000000' };
  const BOTTOM_T = { style: BorderStyle.SINGLE, size: bottomSize, color: '000000' };

  const cellOf = (text, w, borders, bold = false) => {
    // ⛔ 用 parseInlineWithMath 让 cell 内的 $...$ 行内公式正确渲染为 OMML 数学
    const cellTextStyle = {
      bold,
      font: { eastAsia: PROFILE.fonts.chinese_body, ascii: PROFILE.fonts.latin, hAnsi: PROFILE.fonts.latin },
      size: pt2half(tableFontPt),
      color: '000000',
    };
    return new TableCell({
      width: { size: w, type: WidthType.DXA },
      borders,
      shading: { fill: 'FFFFFF', type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      children: [new Paragraph({
        alignment: AlignmentType.CENTER,
        indent: { firstLine: 0 },
        children: parseInlineWithMath(String(text), cellTextStyle),
      })],
    });
  };

  const headerRow = new TableRow({
    tableHeader: true,
    children: headers.map((h, i) =>
      cellOf(h, colWidths[i], { top: THICK_T, bottom: THIN_T, left: NONE, right: NONE }, headerBold)),
  });

  const bodyRows = rows.map((row, ri) => {
    const isLast = ri === rows.length - 1;
    return new TableRow({
      children: row.map((cell, i) =>
        cellOf(String(cell), colWidths[i], {
          top: NONE,
          bottom: isLast ? BOTTOM_T : NONE,
          left: NONE,
          right: NONE,
        })),
    });
  });

  return new Table({
    width: { size: tableW, type: WidthType.DXA },
    columnWidths: colWidths,
    layout: TableLayoutType.FIXED,  // 固定布局，否则 Word 忽略列宽按内容撑开、双栏下溢出
    rows: [headerRow, ...bodyRows],
  });
}

function blockFormula(latex, label) {
  // label：可选的公式编号字符串（已含括号），如 "(1)" 或 "(2.3)"
  const noBorders = {
    top: NONE, bottom: NONE, left: NONE, right: NONE,
    insideHorizontal: NONE, insideVertical: NONE,
  };
  let mathObj;
  try {
    const mathml = temml.renderToString(latex, { displayMode: true, throwOnError: false });
    const kids = mathmlToDocxChildren(mathml);
    mathObj = new DocxMath({ children: kids && kids.length ? kids : [new MathRun(latex)] });
  } catch (e) {
    mathObj = new DocxMath({ children: [new MathRun(latex)] });
  }
  // 三栏布局：占位 / 居中公式 / 右侧编号
  // 编号列宽度按是否有 label 调整：有则给 1100 twips（约 1.94cm），没有则窄一些
  const labelText = (label || '').trim();
  // 双栏时公式布局表也锁到栏宽；编号列在窄栏里压到 567，防三列挤爆
  const formulaW = colBodyWidthTwips();
  const narrow = formulaW < 6000;
  const rightW = labelText ? (narrow ? 567 : 1100) : (narrow ? 340 : 567);
  const leftW = narrow ? 200 : 567;
  const midW = formulaW - leftW - rightW;
  const bodyFontPt = PROFILE.body.font_size_pt;
  return new Table({
    width: { size: formulaW, type: WidthType.DXA },
    columnWidths: [leftW, midW, rightW],
    layout: TableLayoutType.FIXED,
    borders: noBorders,
    rows: [new TableRow({
      children: [
        new TableCell({
          width: { size: leftW, type: WidthType.DXA }, borders: noBorders,
          verticalAlign: VerticalAlign.CENTER,
          children: [new Paragraph({ indent: { firstLine: 0 }, children: [] })],
        }),
        new TableCell({
          width: { size: midW, type: WidthType.DXA }, borders: noBorders,
          verticalAlign: VerticalAlign.CENTER,
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            indent: { firstLine: 0 },
            children: [mathObj],
          })],
        }),
        new TableCell({
          width: { size: rightW, type: WidthType.DXA }, borders: noBorders,
          verticalAlign: VerticalAlign.CENTER,
          children: [new Paragraph({
            alignment: AlignmentType.RIGHT,
            indent: { firstLine: 0 },
            children: labelText
              ? [new TextRun({
                  text: labelText,
                  font: { ascii: PROFILE.fonts.latin, hAnsi: PROFILE.fonts.latin,
                          eastAsia: PROFILE.fonts.chinese_body },
                  size: pt2half(bodyFontPt),
                  color: '000000',
                })]
              : [],
          })],
        }),
      ],
    })],
  });
}

function imageOf(filepath, workspace) {
  let resolved = path.isAbsolute(filepath) ? filepath : path.join(workspace, filepath);
  if (!fs.existsSync(resolved)) {
    const alt = path.join(workspace, 'figures', path.basename(filepath));
    if (fs.existsSync(alt)) resolved = alt;
    else {
      // Markdown 引用 .png 但只有 .pdf：尝试找同名 PDF 并提示
      const ext0 = path.extname(filepath).toLowerCase();
      if (ext0 === '.png' || ext0 === '.jpg' || ext0 === '.jpeg') {
        const altPdf1 = filepath.replace(/\.(png|jpg|jpeg)$/i, '.pdf');
        const altPdf2 = path.join(workspace, altPdf1);
        const altPdf3 = path.join(workspace, 'figures', path.basename(altPdf1));
        for (const cand of [altPdf2, altPdf3, path.isAbsolute(altPdf1) ? altPdf1 : null]) {
          if (cand && fs.existsSync(cand)) {
            return new Paragraph({
              alignment: AlignmentType.CENTER,
              indent: { firstLine: 0 },
              children: [new TextRun({
                text: '[图片缺失 PNG，仅有 PDF: ' + filepath + ']',
                size: 20, color: '999999',
              })],
            });
          }
        }
      }
      return new Paragraph({
        alignment: AlignmentType.CENTER,
        indent: { firstLine: 0 },
        children: [new TextRun({
          text: '[image missing: ' + filepath + ']',
          size: 20, color: '999999',
        })],
      });
    }
  }
  const ext = path.extname(resolved).toLowerCase().replace('.', '');
  if (!['png', 'jpg', 'jpeg', 'gif', 'bmp'].includes(ext)) {
    // PDF 等不支持的格式：尝试找同名 PNG
    if (ext === 'pdf') {
      const altPng = resolved.replace(/\.pdf$/i, '.png');
      if (fs.existsSync(altPng)) {
        resolved = altPng;
      } else {
        return new Paragraph({
          alignment: AlignmentType.CENTER,
          indent: { firstLine: 0 },
          children: [new TextRun({
            text: '[PDF 图片无法嵌入 Word（需要 PNG）: ' + filepath + ']',
            size: 20, color: '999999',
          })],
        });
      }
    } else {
      return new Paragraph({
        alignment: AlignmentType.CENTER,
        indent: { firstLine: 0 },
        children: [new TextRun({
          text: '[unsupported image: ' + filepath + ']',
          size: 20, color: '999999',
        })],
      });
    }
  }
  try {
    const data = fs.readFileSync(resolved);
    const finalExt = path.extname(resolved).toLowerCase().replace('.', '');
    const imgType = finalExt === 'jpg' ? 'jpg' : finalExt;

    // 自适应尺寸：保持原始宽高比
    // - 小于 maxWidth 的图保持原尺寸（避免放大造成模糊）
    // - 大于 maxWidth 的图按比例缩到 maxWidth
    // - 高图（高 > 高度上限）按比例缩
    // maxWidth=576 px 对应约 15.2 cm（A4 页边距 2.5cm 后正文宽度 16cm）
    // ⛔ 双栏时图宽必须缩到栏宽内（twips→px: ×96/1440=÷15），减 4px 留余量；单栏时栏宽=正文宽，MAX_WIDTH 仍主导，无回归。
    const colMaxPx = global.Math.max(global.Math.floor(colBodyWidthTwips() / 15) - 4, 60);
    const MAX_WIDTH = global.Math.min(576, colMaxPx);
    const MAX_HEIGHT = 720;  // 约 19 cm，竖图防止超出页面
    let imgWidth, imgHeight;
    const dims = readImageDimensions(data, finalExt);
    if (dims && dims.width > 0 && dims.height > 0) {
      const ratio = dims.height / dims.width;
      if (dims.width > MAX_WIDTH) {
        // 大图：按比例缩到 MAX_WIDTH
        imgWidth = MAX_WIDTH;
        imgHeight = Math.round(MAX_WIDTH * ratio);
      } else {
        // 小图：保持原始像素，不放大
        imgWidth = dims.width;
        imgHeight = dims.height;
      }
      // 高度过大时再按比例缩
      if (imgHeight > MAX_HEIGHT) {
        const k = MAX_HEIGHT / imgHeight;
        imgHeight = MAX_HEIGHT;
        imgWidth = Math.round(imgWidth * k);
      }
    } else {
      // 无法读取尺寸：用一个保守的默认值（不强行 320 高）
      imgWidth = 480;
      imgHeight = 360;
    }

    return new Paragraph({
      alignment: AlignmentType.CENTER,
      indent: { firstLine: 0 },
      children: [new ImageRun({
        type: imgType,
        data,
        transformation: { width: imgWidth, height: imgHeight },
        altText: {
          title: path.basename(filepath),
          description: filepath,
          name: path.basename(filepath),
        },
      })],
    });
  } catch (e) {
    return new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [new TextRun({ text: '[image load failed: ' + filepath + ']', color: '999999' })],
    });
  }
}

// 从图片二进制数据读取实际尺寸（PNG/JPEG/GIF/BMP）
function readImageDimensions(buf, ext) {
  if (!buf || buf.length < 24) return null;
  ext = (ext || '').toLowerCase();

  if (ext === 'png' || (buf[0] === 0x89 && buf[1] === 0x50 && buf[2] === 0x4E && buf[3] === 0x47)) {
    // PNG: width = bytes 16-19, height = bytes 20-23 (big-endian)
    const width = buf.readUInt32BE(16);
    const height = buf.readUInt32BE(20);
    return { width, height };
  }

  if (ext === 'jpg' || ext === 'jpeg' || (buf[0] === 0xFF && buf[1] === 0xD8)) {
    // JPEG: 扫描 SOF0/SOF2 段 (0xFFC0 / 0xFFC2)
    let i = 2;
    while (i < buf.length - 8) {
      if (buf[i] !== 0xFF) { i++; continue; }
      const marker = buf[i + 1];
      if (marker >= 0xC0 && marker <= 0xCF && marker !== 0xC4 && marker !== 0xC8 && marker !== 0xCC) {
        // SOF marker: skip 5 bytes (length + precision), then read height(2) width(2)
        const height = buf.readUInt16BE(i + 5);
        const width = buf.readUInt16BE(i + 7);
        return { width, height };
      }
      // 跳过这个 segment：长度在 i+2..i+3
      const segLen = buf.readUInt16BE(i + 2);
      i += 2 + segLen;
    }
    return null;
  }

  if (ext === 'gif' || (buf[0] === 0x47 && buf[1] === 0x49 && buf[2] === 0x46)) {
    // GIF: width = bytes 6-7, height = bytes 8-9 (little-endian)
    const width = buf.readUInt16LE(6);
    const height = buf.readUInt16LE(8);
    return { width, height };
  }

  if (ext === 'bmp' || (buf[0] === 0x42 && buf[1] === 0x4D)) {
    // BMP: width = bytes 18-21, height = bytes 22-25 (little-endian)
    const width = buf.readUInt32LE(18);
    const height = buf.readUInt32LE(22);
    return { width, height };
  }

  return null;
}

function refEntry(text) {
  const refFontPt = PROFILE.references.font_size_pt;
  const hangCm = PROFILE.references.hanging_indent_cm;
  const hangTwips = cm2twips(hangCm);
  return new Paragraph({
    indent: { left: hangTwips, hanging: hangTwips, firstLine: 0 },
    spacing: { line: lineMul(1.25, refFontPt), lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text),
      font: { eastAsia: PROFILE.fonts.chinese_body, ascii: PROFILE.fonts.latin, hAnsi: PROFILE.fonts.latin },
      size: pt2half(refFontPt),
      color: '000000',
    })],
  });
}

// ⛔ 摘要标题（居中、加粗，对标 cumcmthesis.cls：\zihao{4}\bfseries 摘要）
function abstractHeading(text) {
  const labelSizePt = (PROFILE.abstract && PROFILE.abstract.label_size_pt) || 14;
  return new Paragraph({
    alignment: AlignmentType.CENTER,
    indent: { firstLine: 0 },
    spacing: { before: 240, after: 120, line: lineMul(PROFILE.body.line_spacing, labelSizePt),
               lineRule: LineRuleType.AUTO },
    children: [new TextRun({
      text: cleanInline(text),
      bold: PROFILE.abstract ? !!PROFILE.abstract.label_bold : true,
      font: { ascii: PROFILE.fonts.latin, eastAsia: PROFILE.fonts.chinese_heading,
              hAnsi: PROFILE.fonts.latin },
      size: pt2half(labelSizePt),
      color: '000000',
    })],
  });
}

// 关键词段落（黑体加粗标签 + 正文内容）
function keywordsPara(label, value) {
  const sizePt = (PROFILE.keywords && PROFILE.keywords.label_size_pt) || PROFILE.body.font_size_pt;
  const labelFont = (PROFILE.keywords && PROFILE.keywords.font) || PROFILE.fonts.chinese_heading;
  return new Paragraph({
    indent: { firstLine: firstLineTwips(PROFILE.body.first_line_indent_chars, sizePt) },
    spacing: { before: 120, after: 120,
               line: lineMul(PROFILE.body.line_spacing, sizePt), lineRule: LineRuleType.AUTO },
    children: [
      new TextRun({
        text: label,
        bold: PROFILE.keywords ? !!PROFILE.keywords.label_bold : true,
        font: { ascii: PROFILE.fonts.latin, eastAsia: labelFont, hAnsi: PROFILE.fonts.latin },
        size: pt2half(sizePt),
        color: '000000',
      }),
      ...parseInlineWithMath(value).map(node => {
        // 对纯 TextRun 重置字体，避免从 label 继承黑体
        if (node && node.constructor && node.constructor.name === 'TextRun') {
          // 已经是 TextRun，直接返回
          return node;
        }
        return node;
      }),
    ],
  });
}

// 解析并丢弃 YAML frontmatter（已不再渲染封面，但仍要把它从正文剥离避免被误当文本）
function parseFrontmatter(content) {
  const match = content.match(/^---\s*\r?\n([\s\S]*?)\r?\n---\s*\r?\n/);
  if (!match) return { meta: {}, body: content };
  const meta = {};
  for (const line of match[1].split(/\r?\n/)) {
    const m = line.match(/^([\w\-]+)\s*:\s*(.*)$/);
    if (m) {
      let v = m[2].trim();
      if ((v.startsWith('"') && v.endsWith('"')) ||
          (v.startsWith("'") && v.endsWith("'"))) {
        v = v.slice(1, -1);
      }
      meta[m[1]] = v;
    }
  }
  return { meta, body: content.slice(match[0].length) };
}


// Markdown 解析（行级状态机）
function parseMarkdown(content, workspace) {
  // ⛔ 解析并丢弃 frontmatter（封面已不再渲染，但要把它从正文剥离）
  const { body: _fmBody } = parseFrontmatter(content);
  content = _fmBody;
  // ⛔ 剥除 HTML 注释（如 <!-- label: tab:xxx --> 这种 markdown 没有原生 label
  // 由 stats_utils.py / paper-figure SKILL 注入的"软 label"，不应渲染到 Word）
  // 但要保护代码块内的 <!-- 不被误剥。先用占位符保护代码块，再剥注释，再还原。
  const _codeBlockProtect = [];
  content = content.replace(/```[\s\S]*?```/g, (m) => {
    _codeBlockProtect.push(m);
    return `\x00CODEBLK${_codeBlockProtect.length - 1}\x00`;
  });
  // 多行 HTML 注释（含 <!-- label: ... -->、<!-- 任意说明 -->）
  content = content.replace(/<!--[\s\S]*?-->/g, '');
  // 还原代码块（注释保留在代码块里，因为代码块是文档示例不是真注释）
  content = content.replace(/\x00CODEBLK(\d+)\x00/g, (_m, idx) => _codeBlockProtect[Number(idx)]);

  const lines = content.split(/\r?\n/);
  const elements = [];
  const bodyBuffer = [];
  let inCode = false;
  let codeBuffer = [];
  let inTable = false;
  let tableLines = [];
  let inReferences = false;
  // 摘要状态：在 ## 摘要 / ## Abstract 后置 true，下一个二级标题或 H1 重置
  let inAbstract = false;
  // 第一个 H1 用 title 样式（替代封面）
  let firstH1Seen = false;

  function flushBody() {
    if (bodyBuffer.length === 0) return;
    const text = bodyBuffer.join(' ');
    // ⛔ 关键词识别：**关键词**：内容 / **Keywords**: content / 关键词：内容
    const kwMatch = text.match(
      /^\*{0,2}(\u5173\u952E\u8BCD|\u5173\u952E\u5B57|Key\s*words|Keywords)\*{0,2}\s*[：:]\s*(.+)$/i
    );
    if (kwMatch) {
      const labelRaw = kwMatch[1];
      const value = kwMatch[2];
      // 标签统一为「关键词」/「Keywords」+ 中文冒号 / 半角冒号
      const isCn = /[\u4E00-\u9FA5]/.test(labelRaw);
      const labelOut = isCn ? '\u5173\u952E\u8BCD\uFF1A' : 'Keywords: ';
      elements.push(keywordsPara(labelOut, value));
      bodyBuffer.length = 0;
      return;
    }
    if (inReferences && /^\[\d+\]/.test(text)) {
      elements.push(refEntry(text));
      bodyBuffer.length = 0;
      return;
    }
    // ⛔ 摘要内自动分段：AI 写 markdown 时可能把"针对问题一... 针对问题二..."写在同一段
    // 不分行（违反每个子问题独立成段规范）。在摘要区内（inAbstract=true）扫描
    // "。针对问题X，" / ". For problem X," 模式，自动切成独立段输出。
    // ⛔ 严格限定 inAbstract 内才生效，正文里"针对问题 X 的方法..."这种句子不受影响。
    if (inAbstract) {
      // lookbehind 在句号后 + lookahead 找"针对问题/For problem"开头
      const segments = text.split(
        /(?<=[。.！!？?])\s*(?=(?:针对问题|For\s+problem|For\s+sub-problem)[\u4E00-\u9FA5A-Za-z0-9])/i
      );
      if (segments.length > 1) {
        for (const seg of segments) {
          const t = seg.trim();
          if (t) elements.push(abstractBodyPara(t));  // 摘要正文支持 **加粗**
        }
        bodyBuffer.length = 0;
        return;
      }
    }
    // 摘要正文（未按问题分段的单段）→ 加粗解析；普通正文 → bodyPara（不加粗）
    elements.push(inAbstract ? abstractBodyPara(text) : bodyPara(text));
    bodyBuffer.length = 0;
  }

  function flushTable() {
    if (tableLines.length === 0) { inTable = false; return; }
    const rows = [];
    for (const tl of tableLines) {
      const cells = tl.trim().replace(/^\||\|$/g, '').split('|').map(c => c.trim());
      if (cells.every(c => /^[-:]+$/.test(c))) continue;
      rows.push(cells);
    }
    if (rows.length >= 2) {
      const headers = rows[0];
      const dataRows = rows.slice(1);
      let maxCols = headers.length;
      for (const r of dataRows) {
        if (r.length > maxCols) maxCols = r.length;
      }
      const paddedHeaders = headers.concat(Array(maxCols - headers.length).fill(''));
      const paddedData = dataRows.map(r => r.concat(Array(maxCols - r.length).fill('')));
      elements.push(threeLineTable(paddedHeaders, paddedData));
    }
    tableLines = [];
    inTable = false;
  }

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    const stripped = line.trim();

    if (/^```/.test(stripped)) {
      if (inCode) {
        flushBody();
        // ⛔ 每行一个 paragraph：用单 TextRun 时 docx 不会把 \n 渲染成换行
        // 给段落加浅灰底色 (F5F5F5) 以视觉上分块
        const codeFontPt = PROFILE.code_block ? PROFILE.code_block.font_size_pt : 9;
        const codeBg = (PROFILE.code_block && PROFILE.code_block.background_color) || 'F5F5F5';
        for (const codeLine of codeBuffer) {
          // 保留原始缩进：把 tab 转 4 空格
          const expanded = codeLine.replace(/\t/g, '    ');
          elements.push(new Paragraph({
            indent: { firstLine: 0, left: 240 },
            spacing: { line: lineMul(1.0, codeFontPt), lineRule: LineRuleType.AUTO,
                       before: 0, after: 0 },
            shading: { type: ShadingType.CLEAR, color: 'auto', fill: codeBg },
            children: [new TextRun({
              text: expanded || ' ',  // 空行也要占一行
              font: { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: 'Consolas' },
              size: pt2half(codeFontPt),
              color: '000000',
            })],
          }));
        }
        codeBuffer = [];
        inCode = false;
      } else {
        flushBody();
        if (inTable) flushTable();
        inCode = true;
      }
      continue;
    }
    if (inCode) {
      codeBuffer.push(line);
      continue;
    }

    if (stripped.startsWith('$$')) {
      flushBody();
      // 单行：$$...$$ [可选编号 (1) 或 (2.3) 等]
      const single = stripped.match(/^\$\$(.+?)\$\$\s*(\(\d+(?:\.\d+)?\))?\s*$/);
      if (single) {
        let _slatex = single[1].trim();
        let _slabel = single[2] || '';
        // ⛔ 单行公式同样支持内嵌 \tag{...} 提取 (跟下面多行块一致)
        if (!_slabel) {
          const _stagMatch = _slatex.match(/\\tag\{([^}]+)\}/);
          if (_stagMatch) {
            _slabel = '(' + _stagMatch[1] + ')';
            _slatex = _slatex.replace(/\\tag\{[^}]+\}/, '').trim();
          }
        }
        elements.push(blockFormula(_slatex, _slabel));
        continue;
      }
      // 多行模式：当前行只能是 "$$"（开块标记），从下一行收集 LaTeX
      // 直到遇到结束行：trim 后形如 "$$"、"$$ (1)"、或末尾带 "$$"（如 "x = 0$$"）
      const buf = [];
      let blockLabel = '';
      const _isEndLine = (s) => {
        const t = s.trim();
        if (t === '$$') return true;
        // "$$ (1)" 形式
        if (/^\$\$\s*\(\d+(?:\.\d+)?\)\s*$/.test(t)) return true;
        // 内容行末尾闭合 "...latex... $$"（不带编号）
        if (t !== '$$' && t.endsWith('$$') && !t.startsWith('$$')) return true;
        return false;
      };
      i++;  // 跳过开块标记 "$$"
      while (i < lines.length && !_isEndLine(lines[i])) {
        buf.push(lines[i]);
        i++;
      }
      if (i < lines.length) {
        const endLine = lines[i].trim();
        // 解析结尾行可能附带的编号
        const endLabelMatch = endLine.match(/^\$\$\s*(\(\d+(?:\.\d+)?\))\s*$/);
        if (endLabelMatch) {
          blockLabel = endLabelMatch[1];
        } else if (endLine === '$$') {
          // 纯结束标记，不做处理
        } else if (endLine.endsWith('$$')) {
          // 内容行带末尾 $$：剥掉 $$ 加进 buf
          buf.push(endLine.replace(/\$\$$/, ''));
        }
      }
      let latex = buf.join('\n').trim();
      // 如果 LaTeX 内嵌 \tag{...}，提取出来作为编号
      if (!blockLabel) {
        const tagMatch = latex.match(/\\tag\{([^}]+)\}/);
        if (tagMatch) {
          blockLabel = '(' + tagMatch[1] + ')';
          latex = latex.replace(/\\tag\{[^}]+\}/, '').trim();
        }
      }
      if (latex) elements.push(blockFormula(latex, blockLabel));
      continue;
    }

    if (stripped.startsWith('|')) {
      flushBody();
      if (!inTable) { inTable = true; tableLines = []; }
      tableLines.push(stripped);
      continue;
    } else if (inTable) {
      flushTable();
    }

    if (!stripped) {
      flushBody();
      continue;
    }

    if (/^[-*_]{3,}$/.test(stripped)) {
      flushBody();
      continue;
    }

    const hMatch = stripped.match(/^(#{1,6})\s*(.+)$/);
    if (hMatch) {
      flushBody();
      const level = hMatch[1].length;
      const text = hMatch[2].trim();
      const norm = text.replace(/\s/g, '').toLowerCase();
      const isReferences = norm.indexOf('references') >= 0 || norm.indexOf('\u53C2\u8003\u6587\u732E') >= 0;
      // ⛔ 摘要识别：## 摘要 / ## Abstract / ## Summary（仅 level 2）
      const isAbstract = level === 2 && (
        norm === '\u6458\u8981' ||           // 摘要
        norm === 'abstract' ||
        norm === 'summary' ||                // MCM/ICM 惯例
        norm === 'summarysheet' ||           // MCM 'Summary Sheet' (space-stripped lowercase)
        norm.startsWith('\u6458\u8981(') ||  // 摘要(中文)
        norm.startsWith('\u6458\u8981\uff08')
      );
      if (level <= 2 && isReferences) {
        inReferences = true;
        inAbstract = false;
      } else if (level <= 2) {
        inReferences = false;
      }
      if (isAbstract) {
        // 用居中加粗的摘要标题样式
        elements.push(abstractHeading(text));
        inAbstract = true;
        continue;
      }
      // 离开摘要区：遇到任何非摘要的 H1/H2 标题
      if (level <= 2) {
        inAbstract = false;
      }
      if (level === 1) {
        const isFirst = !firstH1Seen;
        firstH1Seen = true;
        elements.push(h1(text, isFirst));
      }
      else if (level === 2) elements.push(h2(text));
      else if (level === 3) elements.push(h3(text));
      else elements.push(h4(text));
      continue;
    }

    const imgMatch = stripped.match(/^!\[([^\]]*)\]\(([^)]+)\)\s*$/);
    if (imgMatch) {
      flushBody();
      const alt = imgMatch[1];
      const ipath = imgMatch[2];
      elements.push(imageOf(ipath, workspace));
      if (alt && alt.trim()) {
        elements.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          indent: { firstLine: 0 },
          spacing: { before: 60, after: 120 },
          children: [new TextRun({
            text: cleanInline(alt),
            font: { eastAsia: 'SimSun' }, size: 21, bold: true,
            color: '000000',
          })],
        }));
      }
      continue;
    }

    const listMatch = stripped.match(/^([-*+]|\d+[.)])\s+(.+)$/);
    if (listMatch) {
      flushBody();
      const itemText = listMatch[2];
      const prefix = /\d/.test(listMatch[1]) ? listMatch[1] + ' ' : '\u2022 ';
      elements.push(new Paragraph({
        indent: { left: 480, firstLine: 0 },
        spacing: { line: 360, lineRule: LineRuleType.AUTO },
        children: [
          new TextRun({ text: prefix, color: '000000' }),
          ...parseInlineWithMath(itemText),
        ],
      }));
      continue;
    }

    bodyBuffer.push(stripped);
  }

  flushBody();
  if (inCode && codeBuffer.length) {
    // 同步主流程：每行一段，浅灰底色
    const codeFontPt = PROFILE.code_block ? PROFILE.code_block.font_size_pt : 9;
    const codeBg = (PROFILE.code_block && PROFILE.code_block.background_color) || 'F5F5F5';
    for (const codeLine of codeBuffer) {
      const expanded = codeLine.replace(/\t/g, '    ');
      elements.push(new Paragraph({
        indent: { firstLine: 0, left: 240 },
        spacing: { line: lineMul(1.0, codeFontPt), lineRule: LineRuleType.AUTO,
                   before: 0, after: 0 },
        shading: { type: ShadingType.CLEAR, color: 'auto', fill: codeBg },
        children: [new TextRun({
          text: expanded || ' ',
          font: { ascii: 'Consolas', hAnsi: 'Consolas', eastAsia: 'Consolas' },
          size: pt2half(codeFontPt),
          color: '000000',
        })],
      }));
    }
  }
  if (inTable) flushTable();

  return elements;
}

// 主入口
async function main() {
  const args = parseArgs();
  const sourcePath = path.resolve(args.source);
  const outputPath = path.resolve(args.output);
  const workspace = path.resolve(args.workspace);

  if (!fs.existsSync(sourcePath)) {
    console.error('Source file not found: ' + sourcePath);
    process.exit(1);
  }

  // 加载样式 profile（如果指定）
  if (args.profile) {
    loadProfile(path.resolve(args.profile));
  }

  const buf = fs.readFileSync(sourcePath);
  let content;
  for (const enc of ['utf-8', 'utf8', 'gbk', 'latin1']) {
    try {
      content = buf.toString(enc);
      break;
    } catch (e) {
      continue;
    }
  }
  if (!content) {
    console.error('Failed to decode source file');
    process.exit(2);
  }

  _chapter = 0;
  const elements = parseMarkdown(content, workspace);

  const doc = new Document({
    creator: 'MH Agent',
    title: path.basename(sourcePath, path.extname(sourcePath)),
    styles: {
      default: {
        document: {
          run: {
            font: {
              ascii: PROFILE.fonts.latin,
              hAnsi: PROFILE.fonts.latin,
              eastAsia: PROFILE.fonts.chinese_body,
            },
            size: pt2half(PROFILE.body.font_size_pt),
            color: '000000',
          },
          paragraph: {
            spacing: {
              line: lineMul(PROFILE.body.line_spacing, PROFILE.body.font_size_pt),
              lineRule: LineRuleType.AUTO,
            },
            indent: {
              firstLine: firstLineTwips(PROFILE.body.first_line_indent_chars, PROFILE.body.font_size_pt),
            },
          },
        },
        heading1: { run: { color: '000000' } },
        heading2: { run: { color: '000000' } },
        heading3: { run: { color: '000000' } },
        heading4: { run: { color: '000000' } },
        heading5: { run: { color: '000000' } },
        heading6: { run: { color: '000000' } },
      },
    },
    sections: [{
      properties: {
        page: {
          size: { width: PAGE_W, height: PAGE_H },
          margin: {
            top: cm2twips(PROFILE.page.margin_top_cm),
            right: cm2twips(PROFILE.page.margin_right_cm),
            bottom: cm2twips(PROFILE.page.margin_bottom_cm),
            left: cm2twips(PROFILE.page.margin_left_cm),
          },
        },
        // 双栏（期刊）：profile.page.columns>=2 时整篇正文分栏
        ...(columnCount() >= 2 ? {
          column: {
            count: columnCount(),
            space: cm2twips(PROFILE.page.column_spacing_cm != null ? PROFILE.page.column_spacing_cm : 0.6),
            equalWidth: true,
          },
        } : {}),
      },
      footers: {
        default: new Footer({
          children: [new Paragraph({
            alignment: AlignmentType.CENTER,
            indent: { firstLine: 0 },
            children: [new TextRun({ children: [PageNumber.CURRENT], color: '000000' })],
          })],
        }),
      },
      children: elements,
    }],
  });

  const buffer = await Packer.toBuffer(doc);
  fs.mkdirSync(path.dirname(outputPath), { recursive: true });
  fs.writeFileSync(outputPath, buffer);
  console.log('OK: DOCX exported: ' + outputPath + ' (' + buffer.length + ' bytes)');
}

main().catch(err => {
  console.error('Conversion failed:', err.message);
  console.error(err.stack);
  process.exit(3);
});
