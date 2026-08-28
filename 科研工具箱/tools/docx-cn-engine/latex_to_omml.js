/**
 * latex_to_omml.js — 批量把 LaTeX 公式转成 OMML(<m:oMath>) XML 片段
 *
 * 复用竞赛公式链：temml(LaTeX→MathML) → mathmlToDocxChildren(→docx Math) →
 * 打包成一个临时 docx → 解 zip 取 word/document.xml → 顺序抽出每个 <m:oMath>。
 *
 * 用法：stdin 传 JSON 数组 [{ "latex": "...", "display": true|false }, ...]
 *       stdout 回 JSON 数组 [{ "ok": true, "omml": "<m:oMath …>…</m:oMath>" }, ...]
 * 单次进程只打包一次，公式一一对应输入顺序。
 */
'use strict';

const { Document, Packer, Paragraph, Math: DocxMath, MathRun } = require('docx');
const JSZip = require('jszip');
const temml = require('temml');
const { mathmlToDocxChildren } = require('./mathml-to-docx');

function readStdin() {
  return new Promise((resolve, reject) => {
    let buf = '';
    process.stdin.setEncoding('utf8');
    process.stdin.on('data', (d) => { buf += d; });
    process.stdin.on('end', () => resolve(buf));
    process.stdin.on('error', reject);
  });
}

// 从 mathmlToDocxChildren 的产物构造 DocxMath；失败回退为原文 MathRun
function buildMath(latex, display) {
  try {
    const mathml = temml.renderToString(latex, { displayMode: !!display, throwOnError: false });
    const kids = mathmlToDocxChildren(mathml);
    if (kids && kids.length) return new DocxMath({ children: kids });
  } catch (e) {
    // 落到下面回退
  }
  return new DocxMath({ children: [new MathRun(latex)] });
}

// 从 document.xml 顺序提取全部 <m:oMath>…</m:oMath>（含自闭合，极少见）
function extractOMath(xml) {
  const out = [];
  const re = /<m:oMath\b[\s\S]*?<\/m:oMath>/g;
  let m;
  while ((m = re.exec(xml)) !== null) out.push(m[0]);
  return out;
}

async function main() {
  const raw = await readStdin();
  let items;
  try {
    items = JSON.parse(raw);
    if (!Array.isArray(items)) throw new Error('输入不是数组');
  } catch (e) {
    process.stdout.write(JSON.stringify({ error: '输入 JSON 解析失败: ' + e.message }));
    process.exit(2);
    return;
  }

  // 每条公式独占一个段落，保证 document.xml 里 <m:oMath> 顺序 == 输入顺序
  const paragraphs = items.map((it) =>
    new Paragraph({ children: [buildMath(String(it.latex || ''), !!it.display)] })
  );
  const doc = new Document({ sections: [{ children: paragraphs.length ? paragraphs : [new Paragraph({})] }] });

  const buffer = await Packer.toBuffer(doc);
  const zip = await JSZip.loadAsync(buffer);
  const docXmlFile = zip.file('word/document.xml');
  if (!docXmlFile) {
    process.stdout.write(JSON.stringify({ error: '打包结果缺少 word/document.xml' }));
    process.exit(3);
    return;
  }
  const xml = await docXmlFile.async('string');
  const omaths = extractOMath(xml);

  const results = items.map((it, idx) => {
    const omml = omaths[idx];
    if (omml) return { ok: true, omml };
    return { ok: false, omml: '', latex: String(it.latex || '') };
  });
  process.stdout.write(JSON.stringify(results));
}

main().catch((e) => {
  process.stdout.write(JSON.stringify({ error: String(e && e.stack || e) }));
  process.exit(1);
});
