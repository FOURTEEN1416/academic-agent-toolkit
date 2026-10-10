# -*- coding: utf-8 -*-
"""docx 格式探针 — docx 路线收尾三查：页码域 / 身份泄漏 / 行距（+可选 PDF 层）

用法：
    python docx_format_probe.py <工作区根或 paper 目录>

定位规则（按序）：
    1) <arg>/paper/main.docx
    2) <arg>/main.docx
    3) <arg>/paper/ 下唯一 *.docx
    4) <arg> 下唯一 *.docx
    都找不到（或多个无法唯一定位）→ SKIP，退出码 2（不冒充通过）。

A 层（永远跑，zipfile 直读 docx 内部 XML，不依赖 soffice）：
    1) 页码域：word/footer*.xml 存在且含 PAGE 域指令；缺失=FAIL
       （页码应由 tools/docx_export.py 导出时补，探针只提示不代改）
    2) 身份泄漏：docProps/core.xml 的 creator/lastModifiedBy 与 word/document.xml
       剥标签后正文，扫「指导教师/学号/队号/中文姓名」显式特征模式；
       真实身份特征=FAIL，工具默认值（如 python-docx）=INFO
    3) 行距：styles.xml 正文行距与 1.38 比对（cumcmthesis.cls 实际倍率）；
       偏差只报 INFO 不 FAIL（分赛事行距差异留后续，不在此阻断）

B 层（仅 soffice 在 PATH 时跑）：临时目录转 PDF，pypdf 报页数与体积，>25MB=FAIL；
    soffice 缺席 → 打印 SKIP(转换不可用)，不影响 A 层退出码。

退出码：有 FAIL=1；干净=0；docx 缺席/无法唯一定位=2
判定纪律（学 leakage_audit.py）：宁可漏报不可误报——身份泄漏只认显式特征
（中文姓名标签/学号/队号模式），拼音或英文署名等灰色形态只 INFO 提示人工确认，
不当 FAIL。
"""
from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

TARGET_LINE_SPACING = 1.38          # cumcmthesis.cls 实际倍率
PDF_MAX_MB = 25.0

# docProps/core.xml 的工具默认署名白名单（小写比较）：仅工具默认值不算泄漏
_TOOL_DEFAULT_CREATORS = {
    "python-docx", "docx", "python-docx-user",
    "microsoft office user", "microsoft office", "microsoft word",
    "libreoffice", "openoffice", "libre", "openpyxl", "pandoc",
}

_CJK = re.compile(r"[\u4e00-\u9fff]")
# core.xml 署名位出现 6 位以上连续数字 → 学号/工号特征（白名单已排除工具默认值）
_NUMERIC_ID = re.compile(r"\d{6,}")

# word/document.xml 剥标签后的显式身份模式（标签+值形态，宁漏勿误不收裸姓名）
_LEAK_PATTERNS = [
    ("指导教师署名", re.compile(r"指导教师\s*[：:]\s*\S{1,24}")),
    ("学号署名", re.compile(r"学号\s*[：:]\s*\S{1,24}")),
    ("队号署名", re.compile(r"(?:参赛)?队(?:号|伍编号)\s*[：:]\s*\S{1,24}")),
    ("报名编号署名", re.compile(r"报名(?:号|编号)\s*[：:]\s*\S{1,24}")),
    ("中文姓名署名", re.compile(
        r"姓\s*名\s*[：:]\s*([\u4e00-\u9fff]{2,4})(?![\u4e00-\u9fff])")),
]

# PAGE 域两种 XML 形态：fldSimple 的 instr 属性 / fldChar+instrText
_PAGE_FIELD_RE = [
    re.compile(r'<w:fldSimple[^>]*w:instr="[^"]*PAGE'),
    re.compile(r"<w:instrText[^>]*>[^<]*\bPAGE\b"),
]


def _strip_tags(xml_text: str) -> str:
    """剥掉 XML 标签得可见文本：Word 可能把「指导教师」拆进多个 run，
    对原始 XML 跑正则会漏，先剥标签再扫。"""
    return re.sub(r"<[^>]+>", "", xml_text)


def _locate_docx(base: Path) -> tuple[Path | None, str]:
    """按定位规则找被检 docx。返回 (路径或None, 说明)。"""
    candidates = [
        base / "paper" / "main.docx",
        base / "main.docx",
    ]
    for c in candidates:
        if c.is_file():
            return c, str(c)
    # <arg>/paper/ 下唯一 *.docx
    paper_dir = base / "paper"
    if paper_dir.is_dir():
        found = sorted(paper_dir.glob("*.docx"))
        if len(found) == 1:
            return found[0], str(found[0])
        if len(found) > 1:
            names = "、".join(p.name for p in found)
            return None, f"paper/ 下有 {len(found)} 份 docx（{names}），无 main.docx，无法唯一定位"
    # <arg> 本身是 paper 目录（其下唯一 *.docx）
    found = sorted(base.glob("*.docx"))
    if len(found) == 1:
        return found[0], str(found[0])
    if len(found) > 1:
        names = "、".join(p.name for p in found)
        return None, f"目录下有 {len(found)} 份 docx（{names}），无法唯一定位"
    return None, "未找到任何 docx（查过 paper/main.docx、main.docx、paper/*.docx、*.docx）"


def _check_page_field(zf: zipfile.ZipFile, results: list[tuple[str, str, str]]) -> None:
    """检查 1：页码域。results 元素 = (检查名, 级别, 消息)。"""
    footers = [n for n in zf.namelist()
               if re.fullmatch(r"word/footer\d*\.xml", n)]
    if not footers:
        results.append(("页码域", "FAIL",
                        "docx 内无 word/footer*.xml — 页脚缺席，页码应由 tools/docx_export.py "
                        "导出时补（否则打印稿无页码）"))
        return
    for name in footers:
        xml = zf.read(name).decode("utf-8", errors="replace")
        for pat in _PAGE_FIELD_RE:
            m = pat.search(xml)
            if m:
                results.append(("页码域", "PASS",
                                f"{name} 含 PAGE 域指令（{m.group(0)[:40]}…）"))
                return
    results.append(("页码域", "FAIL",
                    f"{', '.join(footers)} 存在但均无 PAGE 域指令 — 页码应由 "
                    "tools/docx_export.py 导出时补（fldSimple w:instr=\"PAGE\"）"))


def _check_core_identity(zf: zipfile.ZipFile, results: list[tuple[str, str, str]]) -> None:
    """检查 2a：docProps/core.xml 的 creator / lastModifiedBy。"""
    if "docProps/core.xml" not in zf.namelist():
        results.append(("身份泄漏", "INFO", "docx 内无 docProps/core.xml，跳过元数据署名检查"))
        return
    xml = zf.read("docProps/core.xml").decode("utf-8", errors="replace")
    for tag in ("dc:creator", "cp:lastModifiedBy"):
        m = re.search(rf"<{tag}>(.*?)</{tag}>", xml, re.DOTALL)
        val = (m.group(1) if m else "").strip()
        label = "creator" if tag == "dc:creator" else "lastModifiedBy"
        if not val:
            results.append(("身份泄漏", "PASS", f"core.xml {label} 为空，无署名泄漏"))
            continue
        if val.lower() in _TOOL_DEFAULT_CREATORS:
            results.append(("身份泄漏", "INFO",
                            f"core.xml {label}=\"{val}\" 为工具默认值，非真实身份"))
            continue
        if _CJK.search(val):
            results.append(("身份泄漏", "FAIL",
                            f"core.xml {label}=\"{val}\" 含中文姓名特征（竞赛匿名评审泄漏风险）"))
            continue
        if _NUMERIC_ID.search(val):
            results.append(("身份泄漏", "FAIL",
                            f"core.xml {label}=\"{val}\" 含长数字串（学号/工号特征）"))
            continue
        results.append(("身份泄漏", "INFO",
                        f"core.xml {label}=\"{val}\" 非工具默认值且无法静态判身份"
                        "（拼音/英文署名形态），请人工确认"))


def _check_body_identity(zf: zipfile.ZipFile, results: list[tuple[str, str, str]]) -> None:
    """检查 2b：word/document.xml 正文显式身份模式。"""
    if "word/document.xml" not in zf.namelist():
        results.append(("身份泄漏", "INFO", "docx 内无 word/document.xml，跳过正文身份扫描"))
        return
    text = _strip_tags(zf.read("word/document.xml").decode("utf-8", errors="replace"))
    hits = 0
    for label, pat in _LEAK_PATTERNS:
        m = pat.search(text)
        if m:
            hits += 1
            snippet = m.group(0)
            results.append(("身份泄漏", "FAIL",
                            f"正文检出{label}：\"{snippet[:40]}\"（匿名评审要求删净）"))
    if hits == 0:
        results.append(("身份泄漏", "INFO",
                        "正文未检出身份特征模式（指导教师/学号/队号/报名编号/中文姓名标签）"))


def _check_line_spacing(zf: zipfile.ZipFile, results: list[tuple[str, str, str]]) -> None:
    """检查 3：styles.xml 正文行距 vs 1.38。偏差只 INFO 不 FAIL。"""
    if "word/styles.xml" not in zf.namelist():
        results.append(("行距", "INFO", "docx 内无 word/styles.xml，行距无法静态读取"))
        return
    xml = zf.read("word/styles.xml").decode("utf-8", errors="replace")
    # 依次找：Normal 样式块 → docDefaults 块的 w:spacing@w:line
    scopes: list[tuple[str, str]] = []
    m = re.search(r'<w:style [^>]*w:styleId="Normal"[^>]*>.*?</w:style>', xml, re.DOTALL)
    if m:
        scopes.append(("Normal 样式", m.group(0)))
    m = re.search(r"<w:docDefaults>.*?</w:docDefaults>", xml, re.DOTALL)
    if m:
        scopes.append(("docDefaults", m.group(0)))
    for label, block in scopes:
        ms = re.search(r'<w:spacing[^>]*w:line="(\d+)"', block)
        if not ms:
            continue
        line_val = int(ms.group(1))
        mr = re.search(r'<w:spacing[^>]*w:lineRule="(\w+)"', block)
        rule = mr.group(1) if mr else "auto"
        if rule != "auto":
            results.append(("行距", "INFO",
                            f"styles.xml {label} 行距为固定值模式（lineRule={rule}，"
                            f"line={line_val} twip），非倍率，不与 {TARGET_LINE_SPACING} 比对"))
            return
        ratio = round(line_val / 240, 2)
        if abs(ratio - TARGET_LINE_SPACING) <= 0.02:
            results.append(("行距", "PASS",
                            f"styles.xml {label} 行距 {ratio}（目标 {TARGET_LINE_SPACING}，对齐 cumcmthesis.cls）"))
        else:
            results.append(("行距", "INFO",
                            f"styles.xml {label} 行距 {ratio}，目标 {TARGET_LINE_SPACING}（cumcmthesis.cls）"
                            f"，偏差 {round(ratio - TARGET_LINE_SPACING, 2)} — 仅提示不阻断（分赛事差异留后续）"))
        return
    results.append(("行距", "INFO",
                    f"styles.xml 未显式声明正文行距（行距可能设在段落级 pPr，属正常）— 目标 {TARGET_LINE_SPACING}"))


def _check_pdf_layer(docx_path: Path, results: list[tuple[str, str, str]]) -> None:
    """B 层：soffice 在 PATH 才跑；缺席打印 SKIP 不影响退出码。"""
    soffice = shutil.which("soffice")
    if not soffice:
        print("[PDF转换] SKIP(转换不可用)：未安装 LibreOffice，PDF 层检查缺席（不冒充通过）")
        return
    with tempfile.TemporaryDirectory() as td:
        out_dir = Path(td)
        try:
            proc = subprocess.run(
                [soffice, "--headless", "--convert-to", "pdf",
                 "--outdir", str(out_dir), str(docx_path)],
                capture_output=True, text=True, timeout=300,
            )
        except (OSError, subprocess.TimeoutExpired) as e:
            results.append(("PDF转换", "INFO", f"soffice 调用失败（{type(e).__name__}），PDF 层缺席，请人工转换核查"))
            return
        pdf = out_dir / (docx_path.stem + ".pdf")
        if proc.returncode != 0 or not pdf.is_file():
            results.append(("PDF转换", "INFO",
                            f"soffice 转换未产出 PDF（rc={proc.returncode}），PDF 层缺席，请人工核查"))
            return
        size_mb = round(pdf.stat().st_size / 1048576, 2)
        try:
            from pypdf import PdfReader
            pages = len(PdfReader(str(pdf)).pages)
        except Exception as e:  # pypdf 解析失败不伪造页数
            results.append(("PDF转换", "INFO",
                            f"PDF 已产出（{size_mb} MB）但页数解析失败（{type(e).__name__}），请人工核查"))
            return
        results.append(("PDF转换", "PASS", f"PDF 转换成功：{pages} 页，{size_mb} MB"))
        if size_mb > PDF_MAX_MB:
            results.append(("PDF转换", "FAIL",
                            f"PDF 体积 {size_mb} MB 超 {PDF_MAX_MB} MB 上限（图片未压缩，交稿系统可能拒收）"))


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法：python docx_format_probe.py <工作区根或 paper 目录>")
        return 2
    base = Path(argv[1])
    if not base.is_dir():
        print(f"[定位] SKIP：目录不存在：{base}（不冒充通过）")
        return 2
    docx_path, note = _locate_docx(base)
    if docx_path is None:
        print(f"[定位] SKIP：{note}（不冒充通过）")
        return 2
    print(f"=== docx 格式探针：{note} ===")
    results: list[tuple[str, str, str]] = []
    with zipfile.ZipFile(docx_path) as zf:
        _check_page_field(zf, results)
        _check_core_identity(zf, results)
        _check_body_identity(zf, results)
        _check_line_spacing(zf, results)
    _check_pdf_layer(docx_path, results)

    fail = 0
    for name, level, msg in results:
        print(f"[{name}] {level}: {msg}")
        if level == "FAIL":
            fail += 1
    if fail:
        print(f"=== 结果：{fail} 项 FAIL，退出码 1 ===")
        return 1
    print("=== 结果：无 FAIL，退出码 0 ===")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
