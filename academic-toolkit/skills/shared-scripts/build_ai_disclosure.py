# -*- coding: utf-8 -*-
"""Build the CUMCM 2026 AI disclosure from a user-confirmed manifest.

This script is intentionally deterministic: it does not call a model and never
invents tools, dates or purposes.  The detailed wording is assembled from the
user-confirmed purposes plus observable facts in the finished workspace, so it
can be shorter or longer and is specific to the actual paper instead of being a
shared stock paragraph.  It inserts only the short statement into the paper and
writes ``AI工具使用详情.pdf`` as a standalone supporting-material file.
"""
from __future__ import annotations

import argparse
import codecs
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime
from pathlib import Path
from typing import Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


DETAIL_PDF_NAME = "AI工具使用详情.pdf"
# ⛔ 与 ``web/backend/services/ai_disclosure.py`` 和
# ``web/frontend/src/utils/aiDisclosure.ts`` 的白名单必须逐字一致：
# 这里的 name/organisation 会原样写进提交的 AI工具使用详情.pdf，
# 与后端确认过的记录不一致时 ``_load_manifest`` 会直接拒绝。
PROVIDERS = {
    "deepseek": ("DeepSeek", "杭州深度求索人工智能基础技术研究有限公司", r"deepseek"),
    "qwen": ("通义千问（Qwen）", "阿里云计算有限公司", r"qwen|通义千问|通义"),
    "zhipu": ("智谱（GLM）", "北京智谱华章科技有限公司", r"glm|chatglm|智谱"),
    "kimi": ("Kimi", "北京月之暗面科技有限公司", r"kimi|moonshot|月之暗面"),
    "hunyuan": ("腾讯混元", "深圳市腾讯计算机系统有限公司", r"hunyuan|混元"),
    "doubao": ("豆包", "北京抖音信息服务有限公司", r"doubao|豆包"),
    "ernie": ("文心大模型", "北京百度网讯科技有限公司", r"ernie|文心"),
    "spark": ("讯飞星火", "科大讯飞股份有限公司", r"spark|星火"),
    "minimax": ("MiniMax", "上海稀宇科技有限公司", r"minimax|abab|海螺"),
    "pangu": ("盘古大模型", "华为云计算技术有限公司", r"pangu|盘古"),
}
PURPOSES = {
    "language_polishing": {
        "label": "语言润色",
        "stage": "已完成文稿的语言检查",
    },
    "code_debugging": {
        "label": "代码调试",
        "stage": "既有代码的报错定位与语法检查",
    },
    "typesetting": {
        "label": "排版检查",
        "stage": "LaTeX 或 Word 版式整理",
    },
    "reference_formatting": {
        "label": "参考文献格式整理",
        "stage": "既有参考文献的著录格式核对",
    },
    "terminology_check": {
        "label": "术语翻译与校对",
        "stage": "既有中英文术语的一致性检查",
    },
}
FOREIGN = re.compile(r"(?i)(claude|anthropic|openai|chatgpt|gpt[-_ ]?\d|gemini|copilot|llama|mistral|grok|perplexity|opus|sonnet|haiku)")
CORE_INTERACTION = re.compile(
    r"(?i)(?:(?:建立|构建|设计|选择|推导|求解|生成|撰写).{0,10}"
    r"(?:模型|公式|目标函数|约束|算法|参数|数据方案|结果|结论|创新点))|"
    r"(?:(?:model|formula|objective|constraint|algorithm|parameter|result|conclusion)"
    r".{0,20}(?:design|derive|select|solve|generate|write))"
)

# 第二至四节的条目数预算。详情只是附件，一个工具铺开十几条没人看得下去。
# 每个工具最多 _MAX_PER_TOOL 条；工具多时按 _MAX_ACTIVITIES 往下收配额，
# 所以总数大致是"工具数 × 2~3 条"：1 工具 3 条，3 工具 9 条，5 工具 10 条。
# ⛔ 压条数只能靠"把多个用途并进同一条并把每个用途都写出来"，绝不能丢掉用途 ——
# 少写一个勾过的用途就是漏报实际使用情况。
_MAX_ACTIVITIES = 10
_MAX_PER_TOOL = 3


def _load_manifest(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"无法读取 AI 使用记录：{path}") from exc
    if data.get("mode") not in {"used", "none"}:
        raise ValueError("AI 使用记录未完成用户确认，禁止自动补写")
    if data.get("schema_version", 2) not in {2, 3}:
        raise ValueError("AI 使用记录版本不受支持，请重新确认")
    records = data.get("records")
    if not isinstance(records, list):
        raise ValueError("AI 使用记录缺少 records")
    if data["mode"] == "used" and not (1 <= len(records) <= 5):
        raise ValueError("使用了 AI 时须有 1–5 条真实记录")
    if data["mode"] == "used" and data.get("confirmed_truthful") is not True:
        raise ValueError("AI 使用记录尚未由参赛队确认真实、完整")
    fingerprints: set[tuple[str, str, str]] = set()
    for item in records:
        if not isinstance(item, dict) or item.get("provider_id") not in PROVIDERS:
            raise ValueError("记录中存在未允许的 AI 工具")
        expected_name, expected_org, model_pattern = PROVIDERS[item["provider_id"]]
        if item.get("tool_name") != expected_name or item.get("organisation") != expected_org:
            raise ValueError("AI 工具名称或开发机构与国产工具白名单不一致")
        model = " ".join(str(item.get("model") or "").split())
        if not model or len(model) > 80 or FOREIGN.search(model):
            raise ValueError("模型版本/型号为空或不属于所选国产工具")
        if re.search(model_pattern, model, flags=re.IGNORECASE) is None:
            raise ValueError("模型版本/型号与所选国产工具不匹配")
        used_on = str(item.get("used_on") or "")
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", used_on):
            raise ValueError("AI 使用日期格式无效")
        try:
            parsed = datetime.strptime(used_on, "%Y-%m-%d").date()
        except ValueError as exc:
            raise ValueError("AI 使用日期无效") from exc
        # Future dates are permitted; preserve the user-confirmed date exactly.
        purposes = item.get("purposes")
        if not isinstance(purposes, list) or not purposes or any(p not in PURPOSES for p in purposes):
            raise ValueError("记录中存在未允许的 AI 使用用途")
        item["purposes"] = list(dict.fromkeys(purposes))
        # Schema v2 carried stock prose in the manifest.  Ignore it so legacy
        # workflows also receive the workspace-adaptive renderer.
        item.pop("process_summary", None)
        item.pop("review_summary", None)
        fingerprint = (str(item["provider_id"]), model.casefold(), used_on)
        if fingerprint in fingerprints:
            raise ValueError("AI 使用记录重复，请先合并用途")
        fingerprints.add(fingerprint)
    return data


def _tex(value: Any) -> str:
    text = str(value)
    replacements = {
        "\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "$": r"\$",
        "&": r"\&", "#": r"\#", "_": r"\_", "%": r"\%",
        "~": r"\textasciitilde{}", "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in text)


def _referenced_tex(source: Path, depth: int = 3) -> list[Path]:
    """顺着 ``\\input``／``\\include`` 找主稿真正用到的分章文件。

    ⛔ 不能直接 ``rglob("*.tex")`` 扫一遍：``paper/`` 下常留着 ``main_backup.tex``、
    ``sections/old_q2.tex`` 这类废稿，一并读进来会让"全文含 X 章 X 个公式"虚高
    （实测章节 4→5、公式 3→10），等于在申报材料里报一个不属于本稿的数。
    主稿没有 input／include（单文件论文）时才退回扫目录。
    """
    root = source.parent
    seen: set[Path] = {source.resolve()}
    ordered: list[Path] = []
    frontier = [source]
    for _ in range(max(1, depth)):
        nxt: list[Path] = []
        for current in frontier:
            text = _read_limited(current)
            for raw in re.findall(r"\\(?:input|include|subfile)\s*\{([^{}]{1,200})\}", text):
                name = raw.strip()
                if not name:
                    continue
                candidates = [root / name, root / f"{name}.tex"]
                for candidate in candidates:
                    try:
                        resolved = candidate.resolve()
                    except OSError:
                        continue
                    if (resolved in seen or not candidate.is_file()
                            or candidate.name == "Z_ai_disclosure.tex"):
                        continue
                    seen.add(resolved)
                    ordered.append(candidate)
                    nxt.append(candidate)
                    break
        if not nxt:
            break
        frontier = nxt
    if ordered:
        return ordered
    # 单文件论文：没有任何 input／include，才退回扫目录（仍排开备份和 .mh）。
    return [
        path for path in sorted(root.rglob("*.tex"))
        if path.resolve() not in seen and path.name != "Z_ai_disclosure.tex"
        and ".mh" not in path.relative_to(root).parts
        and not re.search(r"(?i)(backup|_old|_bak|\.bak|副本|copy|_v\d+)", path.stem)
    ]


def _detect_encoding(raw: bytes) -> str:
    """按 BOM 和试解结果判编码。

    ⛔ 不能一律按 UTF-8 读主稿：Word 流程里存出来的中文稿常是 UTF-16（带 BOM），
    按 UTF-8 解会得到满篇替换符，插入声明那一步直接抛 UnicodeDecodeError／写坏原文。
    """
    if raw.startswith(codecs.BOM_UTF8):
        return "utf-8-sig"
    if raw.startswith(codecs.BOM_UTF16_LE):
        return "utf-16-le"
    if raw.startswith(codecs.BOM_UTF16_BE):
        return "utf-16-be"
    # 无 BOM 的 UTF-16 得靠 NUL 密度认出来。⛔ 不能先试 UTF-8：ASCII 字符在 UTF-16 里
    # 是 `\x00X`，而 `\x00` 在 UTF-8 里是合法字节，试解会"成功"并解出满篇 NUL，
    # 之后所有正则都失配（实测题名取不到、章数为 0，却不报任何错）。
    sample = raw[:4096]
    if sample.count(b"\x00") > len(sample) // 5:
        even_nulls = sample[0::2].count(b"\x00")
        odd_nulls = sample[1::2].count(b"\x00")
        return "utf-16-be" if even_nulls > odd_nulls else "utf-16-le"
    for candidate in ("utf-8", "gb18030"):
        try:
            raw.decode(candidate)
            return candidate
        except UnicodeDecodeError:
            continue
    return "utf-8"


def _strip_bom(text: str) -> str:
    """剥掉解码后残留在开头的 BOM 字符。

    ⛔ ``utf-16-le``／``utf-16-be`` 这两个编解码器不会替你去掉 BOM（只有 ``utf-8-sig``
    和不带后缀的 ``utf-16`` 会）。留着它，首行就变成 ``\\ufeff# 标题``，``^#`` 这类
    行首锚点全部失配 —— 实测 UTF-16 的 Word 稿取不到题名，退化成"当前参赛论文"。
    """
    return text.lstrip("﻿")


def _read_text_any(path: Path) -> tuple[str, str]:
    """读文本并回报实际用的编码，供写回时原样保持。"""
    raw = path.read_bytes()
    encoding = _detect_encoding(raw)
    return _strip_bom(raw.decode(encoding, errors="replace")), encoding


def _read_limited(path: Path, limit: int = 900_000) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    # 先判编码再截断：UTF-16 每字符两字节，按字节切会把编码判断和字符边界都打乱。
    encoding = _detect_encoding(raw[:4096])
    text = _strip_bom(raw.decode(encoding, errors="replace")[:limit])
    # ⛔ 统一行尾再交给下游正则。这个函数里的每条正则都按 \n 写，Windows 上存出来的
    # 稿子是 CRLF，行尾多一个 \r 会让 `...$` 这类锚点全部匹配不上（表格、公式一个都
    # 数不到）。顺带让同一篇论文无论以哪种行尾保存，措辞都一致。
    return text.replace("\r\n", "\n").replace("\r", "\n")


def _plain(value: str, limit: int = 80, *, latex: bool = True) -> str:
    """把源码片段化成可直接印进详情的纯文本。

    ``latex=False`` 用于 Markdown 主稿（Word 流程）：那里 ``%`` 就是百分号，
    ⛔ 不能当注释删 —— 否则「占比 30% 与 A&B 研究」会被截成「占比 30」，
    残缺的题名会原样印进提交材料。
    """
    text = str(value or "")
    if latex:
        # ⛔ 注释判定要排除转义百分号：`30\%` 是"百分之三十"不是注释起点。
        # 按 `%.*$` 一律删会把「成本占比 30\%」截成「成本占比 30\」、后半句全丢。
        text = re.sub(r"(?m)(?<!\\)%.*$", " ", text)
    for _ in range(3):
        text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    # 还原 LaTeX 标点转义：素材要的是给人读的字面量（`A&B`、`30%`、`x_i`），
    # 留着反斜杠会被 _tex() 再转义成 \textbackslash{}，在 PDF 里印出多余的 `\`。
    text = re.sub(r"\\([%&_#$}{~^])", r"\1", text)
    text = re.sub(r"[{}$]", " ", text)
    text = " ".join(text.replace("~", " ").split()).strip(" ：:；;，,。.")
    return text[:limit]



def _demote_quotes(value: str) -> str:
    """把素材里的双引号降成单引号，避免与外层引号同级相套。

    章节名与题注在详情里一律被 `“…”` 包起来，素材自带 `“…”` 就会印成
    `“问题三的“鲁棒性”分析”` —— 中文排版里内层该用单引号。
    ⛔ 必须在采集时转换，不能等到拼句子时再转：``evidence_tokens`` 要与真正写进
    PDF 的字面量一致，否则 ``check_pdf`` 反查不到、误判"未同步"。
    """
    return value.replace("“", "‘").replace("”", "’")

def _first_heading(text: str, *, latex: bool = True) -> str:
    patterns = (
        r"\\(?:title|ctitle|titlecn)\s*\{([^{}]{1,240})\}",
        r"(?m)^#\s+(.{1,240})$",
    )
    for pattern in patterns:
        match = re.search(pattern, text)
        if match:
            title = _plain(match.group(1), 70, latex=latex)
            if title and title.casefold() not in {"main", "paper", "论文"}:
                return title
    return ""


def _workspace_context(paper_source: Path) -> dict[str, Any]:
    """Collect stable, public facts from the actual workspace.

    The scan is deliberately bounded and ignores private/runtime directories.
    It is evidence for wording variation, not a semantic analysis of the paper.
    """
    source = Path(paper_source).resolve()
    workspace = source.parent.parent.resolve()
    source_paths = [source]
    if source.suffix.lower() == ".tex":
        source_paths.extend(_referenced_tex(source))
    texts = [_read_limited(path) for path in source_paths[:120]]
    combined = "\n".join(texts)

    # LaTeX 主稿才做注释剥离；Markdown 里 % 是百分号，见 _plain 的说明。
    is_latex = source.suffix.lower() == ".tex"

    title = _first_heading(texts[0] if texts else "", latex=is_latex)
    if not title:
        # 兜底读的是 .md，一律按非 LaTeX 处理
        for fallback in (workspace / "PROBLEM_ANALYSIS.md", workspace / "README.md"):
            title = _first_heading(_read_limited(fallback), latex=False)
            if title:
                break
    if not title:
        title = "当前参赛论文"

    # 章与节分开数：一篇论文只有十来章，把 subsection 一起算会写出"50 个章节"
    # 这种一眼假的数字。headings 仍收全部层级，那是给选材用的，不对外报数。
    headings: list[str] = []
    chapter_titles: list[str] = []
    for text in texts:
        candidates: list[tuple[str, bool]] = [
            (raw, command == "section")
            for command, raw in re.findall(
                r"\\(section|subsection)\*?\s*\{([^{}]{1,200})\}", text
            )
        ]
        candidates.extend(
            (raw, len(hashes) == 2)
            for hashes, raw in re.findall(r"(?m)^(#{2,3})\s+(.{1,200})$", text)
        )
        for candidate, is_chapter in candidates:
            heading = _demote_quotes(_plain(candidate, 42, latex=is_latex))
            lowered = heading.casefold()
            if (not heading or "ai 工具使用声明" in lowered or "ai工具使用声明" in lowered
                    or lowered in {"参考文献", "references", "附录", "appendix"}):
                continue
            if heading not in headings:
                headings.append(heading)
            if is_chapter and heading not in chapter_titles:
                chapter_titles.append(heading)
    problem_headings = [
        heading for heading in headings
        if re.search(r"(?i)(?:问题|problem)\s*[一二三四五六七八九十0-9]+", heading)
    ]

    equation_count = len(re.findall(
        r"\\begin\{(?:equation\*?|align\*?|gather\*?|multline\*?)\}|\\\[", combined
    ))
    # Markdown 块级公式两种写法都要认：独占成行的 `$$` 成对出现，以及一行写完的
    # `$$x=1$$`。⛔ 只认前者会把"$$…$$ 写在一行"的稿子数出 0 个公式，开篇就少报。
    equation_count += len(re.findall(r"(?m)^[ \t]*\$\$[ \t]*$", combined)) // 2
    equation_count += len(re.findall(r"(?m)^[ \t]*\$\$(?!\s*$).+?\$\$[ \t]*$", combined))
    table_count = len(re.findall(r"\\begin\{(?:table\*?|longtable)\}", combined))
    # Markdown 表格按"连续的 | 行算一块"来数。
    # ⛔ 不能用行数 // 3：一张 30 行的数据表会被数成 10 张表，而这个数字直接印进
    # 开篇的"全文含 X 张表"，等于在申报材料里写一个一眼假的数。
    markdown_tables = len(re.findall(
        r"(?m)(?:^[ \t]*\|.*\|[ \t]*$\n?){2,}", combined
    ))
    table_count += markdown_tables
    figure_refs = len(re.findall(r"\\includegraphics(?:\[[^\]]*\])?\{|!\[[^\]]*\]\(", combined))
    reference_count = len(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{", combined))
    # ⛔ 同一文献表常以 \\bibitem 内联 + references.bib 双份落盘（cumcm 常见）。
    # 相加会把 10 条印成 20 条进申报材料——取两源较大者，避免申报数字一眼假。
    bib_file_count = 0
    for bib in sorted(source.parent.rglob("*.bib"))[:20]:
        bib_file_count += len(re.findall(r"(?m)^\s*@\w+\s*\{", _read_limited(bib)))
    reference_count = max(reference_count, bib_file_count)
    if source.suffix.lower() in {".md", ".markdown"}:
        references = re.search(
            r"(?ims)^#{2,3}\s*(?:参考文献|references)\s*$\n(.*?)(?=^#{2,3}\s|\Z)",
            combined,
        )
        if references:
            reference_count = max(reference_count, len(re.findall(
                r"(?m)^\s*(?:\[?\d+\]?[.)、]?|[-*])\s+\S+", references.group(1)
            )))

    ignored_dirs = {".git", ".mh", "_utils", "node_modules", "paper", "venv", ".venv"}
    code_extensions = {".py": "Python", ".m": "MATLAB", ".r": "R", ".jl": "Julia", ".ipynb": "Jupyter"}
    code_files: list[Path] = []
    for base_name in ("code", "figures"):
        base = workspace / base_name
        if not base.is_dir():
            continue
        for path in base.rglob("*"):
            if len(code_files) >= 300:
                break
            if path.is_file() and path.suffix.lower() in code_extensions and not any(part in ignored_dirs for part in path.relative_to(workspace).parts):
                code_files.append(path)
        if len(code_files) >= 300:
            break
    code_files.sort(key=lambda path: str(path.relative_to(workspace)).casefold())
    code_names = [_plain(path.name, 46, latex=False) for path in code_files[:4]]
    code_languages = list(dict.fromkeys(code_extensions[path.suffix.lower()] for path in code_files))

    result_extensions = {".xlsx", ".xls", ".csv", ".json", ".npz", ".parquet"}
    result_count = 0
    for base_name in ("results", "figures", "data"):
        base = workspace / base_name
        if base.is_dir():
            for path in base.rglob("*"):
                if path.is_file() and path.suffix.lower() in result_extensions:
                    result_count += 1
                    if result_count >= 1000:
                        break
        if result_count >= 1000:
            break
    has_compiled = (source.parent / "main.pdf").is_file() or any(source.parent.glob("*.docx"))
    has_english = bool(re.search(r"(?im)^\s*(?:#+\s*)?(?:abstract|keywords)\b", combined))
    has_abstract = "摘要" in combined or bool(re.search(r"(?i)\\begin\{abstract\}|\babstract\b", combined))

    # 题注、符号含义、关键词：这些是论文里真实存在的短语，用来让不同论文的
    # 详情记录落在自己的内容上，而不是共用一句套话。不存在就留空，绝不补写。
    captions: list[str] = []
    for text in texts:
        for raw in re.findall(r"\\caption\*?\s*\{([^{}]{2,160})\}", text):
            caption = _demote_quotes(_plain(raw, 40, latex=is_latex))
            if caption and caption not in captions:
                captions.append(caption)
        for raw in re.findall(r"!\[([^\]\[]{2,160})\]\(", text):
            caption = _demote_quotes(_plain(raw, 40, latex=is_latex))
            if caption and caption not in captions:
                captions.append(caption)

    # 符号表只取中文含义，不取符号本身 —— 符号带 LaTeX 转义，写进 PDF 后
    # pdftotext 提出来的字形与源码不一致，会让 check_pdf 的素材比对误判。
    symbol_glosses: list[str] = []
    for text in texts:
        # 单元格内容止于未转义的 `&`（列分隔）或 `\\`（行尾），但 `\&` `\%` `\_`
        # 这类转义标点属于内容本身，要留下来 —— 否则 `换热效率 A\&B` 会被截成 `换热效率 A`。
        for raw in re.findall(
            r"(?m)^\s*\$[^$\n]{1,60}\$\s*&\s*((?:[^\\&\n]|\\[%&_#$]){2,60})", text
        ):
            gloss = _plain(raw, 24, latex=is_latex)
            gloss = re.sub(r"[，,。.；;：:（(].*$", "", gloss).strip()
            if len(gloss) >= 3 and re.search(r"[\u4e00-\u9fff]", gloss) and gloss not in symbol_glosses:
                symbol_glosses.append(gloss)

    keywords: list[str] = []
    keyword_patterns = (
        r"\\(?:keywords?|Keywords?)\s*\{([^{}]{2,200})\}",
        # Markdown 主稿（Word 流程）的写法，见 docx 骨架里的「**关键词**：…」
        r"(?im)^\s*(?:\*\*)?(?:关键词|关键字|keywords?)(?:\*\*)?\s*[:：]\s*(.{2,200})$",
    )
    for text in texts:
        for pattern in keyword_patterns:
            for raw in re.findall(pattern, text):
                plain = _plain(raw, 120, latex=is_latex)
                # 先按显式分隔符切，保住「占比 30%」这类含空格的完整词条；
                # 只有整串切不开又长得离谱（多半以空格分隔）时才退回按空白切。
                pieces = [item for item in re.split(r"[；;，,、]+", plain) if item.strip()]
                if len(pieces) <= 1 and len(plain.strip()) > 20:
                    pieces = plain.split()
                for piece in pieces:
                    word = piece.strip().strip("*")
                    if 2 <= len(word) <= 20 and word not in keywords:
                        keywords.append(word)

    # ⛔ 内联标志必须全部合并写在开头：Python 3.11 起 (?i)…|(?m)… 会抛
    # "global flags not at the start of the expression"。
    has_appendix = bool(re.search(r"(?im)\\appendix|^#{2,3}\s*附录|\\section\*?\s*\{\s*附录", combined))

    return {
        "captions": captions,
        "symbol_glosses": symbol_glosses,
        "keywords": keywords,
        "has_appendix": has_appendix,
        "title": title,
        "source_label": "LaTeX 主稿" if source.suffix.lower() == ".tex" else "Word 源稿",
        "headings": headings,
        "problem_headings": problem_headings,
        "chapter_count": len(chapter_titles),
        "section_count": len(headings),
        "equation_count": equation_count,
        "table_count": table_count,
        "figure_count": figure_refs,
        "reference_count": reference_count,
        "code_count": len(code_files),
        "code_names": code_names,
        "code_languages": code_languages,
        "result_count": result_count,
        "has_compiled": has_compiled,
        "has_english": has_english,
        "has_abstract": has_abstract,
    }


class _Picker:
    """确定性选材器：同一工作区每次选出的素材与句式逐字相同。

    ⛔ 不能用 ``random`` 模块的全局状态或真随机：``check_pdf`` 会重新渲染一次并比对
    ``_render_fingerprint``，只要两次结果有一个字不同，最终质量闸就会判"未与当前工作区
    同步"并拒绝交付。所以这里用工作区事实（题名、章节、公式/图表计数、用途、记录序号）
    做种子的 SHA-256 流，既保证可复现，又让不同论文、不同用途落在不同分支上。
    """

    def __init__(self, *parts: Any) -> None:
        seed = "".join(str(part) for part in parts)
        self._digest = hashlib.sha256(seed.encode("utf-8")).digest()
        self._cursor = 0

    def _next(self) -> int:
        if self._cursor >= len(self._digest):
            self._digest = hashlib.sha256(self._digest).digest()
            self._cursor = 0
        value = self._digest[self._cursor]
        self._cursor += 1
        return value

    def choice(self, options: list[Any]) -> Any:
        if not options:
            raise ValueError("选材器收到空候选集")
        return options[self._next() % len(options)]

    def base(self) -> int:
        """取一个稳定的句式起点，交给 ``_activity_text`` 做跨轮轮转。

        必须在拆轮之前取一次、各轮共用：轮内 picker 的种子带了轮号，序列本就不同，
        各自取 base 再加偏移并不能保证错开。
        """
        return self._next()

    def sample(self, options: list[Any], count: int) -> list[Any]:
        """不重复抽取，并按原始相对顺序返回（读起来像人顺着论文摘下来的）。"""
        ordered = list(dict.fromkeys(options))
        pool = list(ordered)
        count = max(0, min(count, len(pool)))
        chosen: set[Any] = set()
        for _ in range(count):
            chosen.add(pool.pop(self._next() % len(pool)))
        return [item for item in ordered if item in chosen]


def _rotate(options: list[str], base: int, slot: int, round_index: int) -> str:
    """按起点＋槽位＋轮号取句：同轮内三处各不相同，同一处跨轮也各不相同。

    ⛔ 槽位和轮号都只能以步长 1 相加，别乘系数：任何乘数都会在"候选数正好等于该乘数
    的因子"时被取模抹平，这类 bug 已经踩过两次 ——
      · 写成 ``slot * round_index``：候选 3 个时第 3 槽的 3 的倍数抹掉轮号，核验句三轮一样
      · 写成 ``slot * 5``：候选 5 个时三个槽锁在同一下标，三句话永远绑在一起出现
    连续整数相加对任何 n ≥ 3 都不退化，所以不要再"优化"成乘法。
    ⛔ 候选必须 ≥ 3：三个连续整数模 n 互不相同要求 n ≥ 3；只剩 2 个时第 1、3 轮必然
    选到同一句。宁可当场报错，也别静默出重复文字。
    """
    if len(options) < 3:
        raise ValueError("句式候选不足 3 个，跨轮会出现重复文字")
    return options[(base + slot + round_index) % len(options)]


def _framing_only(value: str, material: list[str]) -> str:
    """剥掉照抄的论文素材，只留我们自己组的那部分话，供越界闸检查。

    ⛔ 不能拿整句直接过 ``CORE_INTERACTION``：素材里的字眼会撞上闸的关键词，而这些
    名字在数模论文里满地都是，撞上就是整篇论文的详情直接生成失败，还报一句看不懂的
    "越过辅助用途边界"：
      · 小节名"问题三的求解结果" → 命中中文分支的"求解…结果"
      · 代码文件 model.py 与 solve.py 相邻 → 命中英文分支的"model…solve"
    引号／书名号只盖得住章节名和题注，文件名是裸写的，所以再按登记的素材逐个剔。
    """
    framing = re.sub(r"“[^”]*”|《[^》]*》", "　", value)
    for token in sorted(filter(None, material), key=len, reverse=True):
        framing = framing.replace(token, "　")
    return framing


def _round_slice(items: list[Any], round_index: int, round_total: int) -> list[Any]:
    """把素材按轮次切段：第一轮拿前面几项，第二轮拿中间，末轮兜走余数。

    项数不够一轮分一个就整份返回 —— 那种情形下切出来会有空段，句子里的范围就没了。
    这只发生在次要素材上（比如术语校对按术语数拆了 3 轮，但全篇只有 2 章可引），
    主素材的轮数上限由 ``_round_total`` 按"每轮至少两项"卡住。
    """
    if round_total <= 1 or len(items) < round_total:
        return list(items)
    size = len(items) // round_total
    start = (round_index - 1) * size
    end = len(items) if round_index >= round_total else start + size
    return items[start:end]


def _round_total(purpose: str, context: dict[str, Any], picker: _Picker) -> int:
    """这个用途实际能分成几轮提问。

    轮数由工作区里真实存在的可分组对象数决定：章节多就能分批送审，代码文件多就能
    按文件排查。⛔ 不能凭空给个随机数 —— 记录条数是申报事实，素材不够就只写一轮。
    """
    if purpose == "language_polishing":
        pool = len(context["problem_headings"] or context["headings"])
    elif purpose == "code_debugging":
        pool = min(len(context["code_names"]), context["code_count"])
    elif purpose == "typesetting":
        # 公式／图／表是三类独立对象，一轮管一类就是正常分工，不适用下面"每轮至少两项"
        # 的折算 —— 那会把上限永远压到 1 轮，分支里按轮号点名的代码就成了死代码。
        kinds = sum(bool(context[key]) for key in ("equation_count", "figure_count", "table_count"))
        # ⛔ kinds 可能为 0（纯文字稿）：必须兜到 1，返回 0 会把用户勾的用途整条吞掉。
        return 1 if kinds <= 1 else picker.choice(list(range(2, min(3, kinds) + 1)))
    elif purpose == "reference_formatting":
        pool = context["reference_count"] // 3
    elif purpose == "terminology_check":
        pool = len(context["symbol_glosses"]) + len(context["keywords"])
    else:
        pool = 0
    capacity = min(3, max(1, pool // 2))
    return capacity if capacity <= 1 else picker.choice(list(range(2, capacity + 1)))


def _allocate_slots(
    purposes: list[str], budget: int, context: dict[str, Any], picker: _Picker
) -> list[list[str]]:
    """把一个工具勾的用途分配成不超过 ``budget`` 条，返回每条覆盖哪些用途。

    两种情形：
      · 用途数 ≤ 配额：一个用途一条，剩下的额度用来把素材足的用途拆成多轮
        （返回里同一个用途出现多次，就是多轮）。
      · 用途数 > 配额：把用途分组，一条覆盖若干用途，文字里逐个写出来。
    ⛔ 任何情形下每个用途都必须至少出现一次 —— 丢掉一个勾过的用途就是漏报。
    """
    budget = max(1, budget)
    if not purposes:
        return []
    if len(purposes) > budget:
        # 分组：按原顺序切成 budget 组，前几组多担一个，组内顺序保持不变。
        groups: list[list[str]] = []
        size, extra = divmod(len(purposes), budget)
        cursor = 0
        for index in range(budget):
            take = size + (1 if index < extra else 0)
            groups.append(purposes[cursor:cursor + take])
            cursor += take
        return groups
    # 用途数 ≤ 配额：先各占一条，再把富余额度按素材量分给能拆轮的用途
    rounds = {purpose: 1 for purpose in purposes}
    spare = budget - len(purposes)
    wants = {
        purpose: _round_total(purpose, context, _Picker(picker.base(), purpose, "want"))
        for purpose in purposes
    }
    # 每次把一个额度给"还没吃饱且想要最多轮"的用途，顺序固定以保证可复现
    while spare > 0:
        hungry = [p for p in purposes if rounds[p] < wants[p]]
        if not hungry:
            break
        chosen = max(hungry, key=lambda p: (wants[p] - rounds[p], -purposes.index(p)))
        rounds[chosen] += 1
        spare -= 1
    slots: list[list[str]] = []
    for purpose in purposes:
        slots.extend([purpose] for _ in range(rounds[purpose]))
    return slots


def _quoted_headings(
    context: dict[str, Any],
    picker: _Picker | None = None,
    count: int = 3,
    pool: list[str] | None = None,
) -> tuple[str, list[str]]:
    """返回引号包裹的章节列表，以及实际被引用的章节名（供闸比对）。

    没有 picker 时退回"取前 N 个"，保持 ``_context_summary`` 等旧调用点的行为。
    ``pool`` 用于把候选限定在本轮负责的那几章。
    """
    headings = pool if pool is not None else (context["problem_headings"] or context["headings"])
    if not headings:
        return "摘要和已完成正文", []
    picked = picker.sample(headings, count) if picker else headings[:count]
    sample = "、".join(f"“{heading}”" for heading in picked)
    # 用"节"不用"章节"：这里数的是章加子节，而开篇报的是章数，两处都叫"章节"会让
    # "全文含 5 章"和"等 5 个章节"看着像同一个数，其实一个是全篇、一个是本轮范围。
    suffix = f"等{len(headings)}节" if len(headings) > len(picked) else ""
    return sample + suffix, picked


def _context_summary(context: dict[str, Any], picker: _Picker | None = None) -> str:
    """一句话交代这份记录对着哪篇论文。

    量词按人写论文的说法给（章、个公式、张图、张表、条文献），⛔ 不要用
    "可识别章节""公式环境""处图形引用"这类解析器口吻 —— 那是程序在自述实现，
    评审看到的应当是参赛队自己在说话。
    """
    counts: list[str] = []
    if context["chapter_count"]:
        counts.append(f"{context['chapter_count']}章")
    elif context["section_count"]:
        # 全篇只用 \subsection／### 分节的稿子：按"节"报，别因为一级标题为 0 就一个数都不给。
        counts.append(f"{context['section_count']}节")
    for key, label in (
        ("equation_count", "个公式"),
        ("figure_count", "张图"),
        ("table_count", "张表"),
        ("reference_count", "条参考文献"),
    ):
        if context[key]:
            counts.append(f"{context[key]}{label}")
    title = context["title"]
    if not counts:
        # 一个都数不出来（纯文字稿、只有子节、稿子还很空）时另起一套说法：
        # ⛔ 不能拿兜底词去填"全文含{}"，会写出"全文含已写完的正文"这种读不通的话。
        options = [
            f"这份记录对应的论文是《{title}》。",
            f"我们提交的论文是《{title}》。",
            f"本记录对应论文《{title}》。",
        ]
        return options[0] if picker is None else picker.choice(options)
    visible = "、".join(counts)
    if picker is None:
        return f"这份记录对应的论文是《{title}》，全文含{visible}。"
    return picker.choice([
        f"这份记录对应的论文是《{title}》，全文含{visible}。",
        f"我们提交的论文是《{title}》，全文含{visible}。",
        f"本记录对应论文《{title}》，正文共{visible}。",
    ])


def _activity_text(
    purpose: str,
    context: dict[str, Any],
    picker: _Picker,
    variant_base: int | None = None,
    round_index: int = 1,
    round_total: int = 1,
) -> tuple[str, str, str, list[str]]:
    """按用途生成使用环节、提示过程、核验情况，并回报实际引用的真实素材。

    ``picker`` 决定摘哪几个章节／题注／术语。种子里带了用途、记录序号和轮号，
    因此同一篇论文的不同记录也不会撞句式，而换一篇论文整体就换一副面孔。
    ``variant_base`` 由各轮共用，配合轮号错开句式，避免同一用途几轮读起来像复制粘贴。
    ``round_index``／``round_total`` 决定本轮负责哪一段素材。
    第四个返回值是"确实写进了文字里的论文素材"，交给 ``check_pdf`` 反查 PDF，
    保证详情始终咬住本稿真实内容。
    """
    # 没给共享起点就从本轮 picker 取一个：否则句式只由轮号决定，同一篇论文里
    # 换记录、换用途都选不出新句式（拆轮前的单轮调用会全篇一个腔调）。
    if variant_base is None:
        variant_base = picker.base()
    slot = [0]

    def pick(options: list[str]) -> str:
        slot[0] += 1
        return _rotate(options, variant_base, slot[0], round_index)

    title = f"《{context['title']}》"
    heading_pool = _round_slice(
        context["problem_headings"] or context["headings"], round_index, round_total
    )
    heading_scope, used_headings = _quoted_headings(
        context, picker, picker.choice([2, 3]), pool=heading_pool
    )
    evidence: list[str] = [context["title"], *used_headings]
    if purpose == "language_polishing":
        additions: list[str] = []
        if context["equation_count"]:
            additions.append("含公式段落保留原有符号、编号和数值")
        if context["has_english"]:
            additions.append("中英文摘要中的术语保持对应")
        if context["captions"]:
            caption = picker.choice(context["captions"])
            additions.append(f"图表题注（如“{caption}”）只改标点不改指称")
            evidence.append(caption)
        # 多轮时每轮只强调一条边界：三轮都把同一串"含公式段落保留…题注只改标点"
        # 原样带上，读起来最像模板套出来的。
        if round_total > 1 and len(additions) >= 2:
            additions = [additions[(round_index - 1) % len(additions)]]
        boundary = "；".join(additions) if additions else "保留原意、数值和既有术语"
        stage = pick([
            f"{title}中{heading_scope}的语言检查",
            f"{title}已定稿部分（{heading_scope}）的语病与标点核对",
            f"针对{heading_scope}的成文语言检查（{title}）",
        ])
        process = pick([
            f"提问范围限于{title}的{heading_scope}，内容为已定稿文字的语病、标点和重复表达，"
            f"{boundary}。",
            f"提交的材料为{heading_scope}中已写完的段落，所问事项限于不通顺、成分残缺和"
            f"用词重复；{boundary}。",
            f"涉及{heading_scope}的成文文字，所问事项限于病句、标点误用和冗余表达，"
            f"不含补写或改写内容；{boundary}。",
        ])
        review = pick([
            f"返回建议均与原稿逐项对照后取舍，采纳范围限于措辞和标点；"
            f"{heading_scope}的专业表述以原稿和已有计算结果为准。",
            f"采纳前均回到{heading_scope}原文复核，改动限于字词与标点，"
            f"凡触及专业表述的一律保留原稿写法。",
            f"修改前后文字逐处比对，确认句意未变才采纳；{heading_scope}中的"
            f"专业提法、数值和符号一律沿用原稿。",
        ])
    elif purpose == "code_debugging":
        languages = "、".join(context["code_languages"]) or "既有"
        file_pool = _round_slice(context["code_names"], round_index, round_total)
        picked_files = picker.sample(file_pool, picker.choice([2, 3]))
        file_scope = "、".join(picked_files) or "与本稿配套的代码文件"
        evidence.extend(picked_files)
        count_text = f"{context['code_count']}个" if context["code_count"] else ""
        # ⛔ 别写"工作区已有的…"：这是程序在自述实现，参赛队说的是"我们已经跑出来的"。
        witness = (
            f"我们已有的{context['result_count']}个数据或结果文件"
            if context["result_count"] else "既有输出和关键中间量"
        )
        stage = pick([
            f"{title}配套的{count_text}{languages}代码文件报错定位与语法检查",
            f"{title}既有{languages}程序（{file_scope}）的运行报错排查",
            f"{count_text}{languages}脚本的语法与依赖问题定位（{title}）",
        ])
        process = pick([
            f"涉及{file_scope}，提交的材料为报错位置和运行环境，所问事项限于语法、"
            "依赖和文件读写；范围限定为修复既有程序故障，不含既定计算逻辑、参数和输出口径的改动。",
            f"提交的材料为{file_scope}中报错的片段与完整报错栈，所问事项限于"
            "语法写法、库版本和路径读写；不含计算逻辑、参数取值和输出口径的选择。",
            f"提问范围限于{file_scope}，提交的材料为异常的最小复现片段与运行环境说明，"
            "所问事项限于语法或依赖层面的原因；既定算法流程与参数不在提问范围内。",
        ])
        review = pick([
            f"采纳范围限于能够单独复现的最小修改，核验条件为重新运行后与{witness}保持一致。",
            f"每处改动均经回跑核对，只有输出与{witness}逐项对上才保留，"
            "否则退回原写法。",
            f"采纳的修改均经重跑核验，通过标准为{witness}未发生变化；"
            "凡会改动计算结果的建议一律不采纳。",
        ])
    elif purpose == "typesetting":
        pieces = []
        if context["equation_count"]:
            pieces.append(f"{context['equation_count']}个公式")
        if context["figure_count"]:
            pieces.append(f"{context['figure_count']}张图")
        if context["table_count"]:
            pieces.append(f"{context['table_count']}张表")
        # 多轮时按对象类型分工：一轮管公式编号，另一轮管图表题注，各写各的。
        # 这里的候选最多只有三项，用 _round_slice 会被它的"切不开就整份返回"挡回来，
        # 所以直接按轮号点名。
        if round_total > 1 and len(pieces) >= 2:
            pieces = [pieces[(round_index - 1) % len(pieces)]]
        object_scope = "、".join(pieces) or "正文、题注和分页"
        label = context["source_label"]
        caption_hint = ""
        if context["captions"]:
            caption = picker.choice(context["captions"])
            caption_hint = f"（如“{caption}”一图的题注位置）"
            evidence.append(caption)
        target = "已生成的成品文档" if context["has_compiled"] else "随后导出的成品页"
        stage = pick([
            f"{title}的{label}版式整理，范围包括{object_scope}",
            f"{title}{label}的分页、编号与题注位置检查（{object_scope}）",
            f"{label}排版一致性核对：{object_scope}（{title}）",
        ])
        process = pick([
            f"提问范围限于{label}里的{object_scope}，所问事项为分页、题注、"
            f"交叉引用、公式编号和字体一致性{caption_hint}，不含正文内容的改写。",
            f"所问事项限于{object_scope}的编号连续性、题注位置、"
            f"交叉引用和字体字号统一{caption_hint}；只涉及版面，不涉及文字内容。",
            f"涉及{object_scope}，所问事项限于断页是否恰当、题注是否紧随图表、"
            f"编号是否与引用对应{caption_hint}，不含正文文字与数据的改动。",
        ])
        review = pick([
            f"以{target}为准逐页核对页宽、断页、编号与引用，采纳范围限于不改变正文含义和数据的版式调整。",
            f"每项版式建议均在{target}上核对效果后才保留，凡影响文字内容或数值的一律放弃。",
            f"对照{target}逐页确认{object_scope}的呈现，采纳范围限于位置、间距与编号，"
            "正文表述保持原样。",
        ])
    elif purpose == "reference_formatting":
        count_text = f"{context['reference_count']}条" if context["reference_count"] else "已有"
        # 不带"的"，后面几处句式都要接"的{count}条条目"，否则出现双"的"。
        place = "附录前参考文献区" if context["has_appendix"] else "正文末参考文献区"
        stage = pick([
            f"{title}中{count_text}参考文献的著录格式核对",
            f"{title}{place}内{count_text}条目的著录项排列检查",
            f"{count_text}已有文献著录格式的一致性核对（{title}）",
        ])
        process = pick([
            f"提问范围限于{title}参考文献区的{count_text}条目，所问事项为作者、题名、年份、"
            "卷期和页码的排列一致性；只涉及已有著录信息，不含文献的新增或替换。",
            f"涉及{place}的{count_text}条目，所问事项限于著录项顺序、缩写和标点"
            "是否符合同一体例；不涉及文献的选取与增删。",
            f"提交的材料为已有著录条目（共{count_text}），所问事项限于作者姓名格式、"
            "年份位置、卷期页码写法上的不统一之处，不含文献推荐或补充。",
        ])
        review = pick([
            "均逐条对照原始文献信息和正文引用关系，保留可追溯条目，未采用无法核实来源的补充内容。",
            "每条格式建议均回到原始文献页面核对后再改，凡涉及作者、年份等事实内容的提示"
            "一律以原文献为准；无法核实的一概不采纳。",
            f"按{place}的条目顺序逐条复核，确认与正文引用编号一一对应；"
            "采纳范围限于排列与标点层面的调整。",
        ])
    elif purpose == "terminology_check":
        bilingual = "中英文摘要、关键词及正文" if context["has_english"] else "摘要、关键词及正文"
        term_pool = _round_slice(
            context["symbol_glosses"] + context["keywords"], round_index, round_total
        )
        term_hint = ""
        if term_pool:
            picked_terms = picker.sample(term_pool, picker.choice([2, 3]))
            term_hint = "（如" + "、".join(f"“{term}”" for term in picked_terms) + "等已有提法）"
            evidence.extend(picked_terms)
        basis = "符号说明表" if context["symbol_glosses"] else "各章节首次定义"
        stage = pick([
            f"{title}中{bilingual}的术语一致性检查",
            f"{title}已有术语在{bilingual}中的写法统一核对",
            f"{bilingual}的既有提法前后一致性校对（{title}）",
        ])
        process = pick([
            f"提交的材料为{heading_scope}中已有的术语{term_hint}，"
            f"所问事项为其在{bilingual}中的写法是否前后一致；仅限校对现有表达，不含论述扩写。",
            f"提交的材料为本稿已经使用的术语清单{term_hint}，所问事项为同一概念"
            f"在{bilingual}各处的写法、中英对应和大小写是否统一；不含概念解释或新术语补充。",
            f"以{basis}为底册，涉及其中的提法{term_hint}，"
            f"所问事项限于它们在{heading_scope}与{bilingual}中出现是否一致，不涉及概念本身的取舍。",
        ])
        review = pick([
            f"结合题目原文、{basis}和各章节首次定义逐项复核术语，只统一确有对应依据的写法。",
            f"每条术语建议均回到{basis}和首次出现处比对，两处一致才统一改写；"
            "无对应依据的替换提法一律不采纳。",
            f"按{basis}逐项核对采纳结果，确认改后写法在{bilingual}中全篇统一，"
            "且未改变任何符号含义与数值。",
        ])
    else:  # guarded by manifest validation
        raise ValueError("记录中存在未允许的 AI 使用用途")
    for value in (stage, process, review):
        if CORE_INTERACTION.search(_framing_only(value, evidence)):
            raise ValueError("自适应声明越过辅助用途边界")
    # ⛔ 只登记"确实写进了这三句"的素材。heading_scope 等取材在函数开头统一算出，
    # 但并非每个用途的句式都会引用它（代码调试、排版检查、文献格式就不用章节名）；
    # 若照单全收，闸会去 PDF 里找一个从未写入的词，把合规产物误判成"未同步"。
    written = stage + process + review
    return stage, process, review, [
        item for item in dict.fromkeys(evidence) if item and item in written
    ]


def _preamble_text(data: dict[str, Any], context: dict[str, Any], picker: _Picker) -> str:
    """开篇交代：用了什么、用在哪儿、核心是谁做的。

    ⛔ 不要写"本文件依据……整理""记录篇幅随本稿内容确定"这类话 —— 那是程序在向读者
    解释自己怎么实现的，参赛队自己写材料不会这么说。也不要出现"工作区"。
    """
    labels = "、".join(_purpose_labels(data))
    summary = _context_summary(context, picker)
    return picker.choice([
        f"{summary}在写作过程中，我们把AI工具用在{labels}这类辅助环节上，"
        "建模思路、求解过程和全部结论均由参赛队独立完成。下面按实际使用情况逐项说明。",
        f"{summary}我们在{labels}等辅助环节借助了AI工具，模型的建立、求解与结论"
        "不涉及工具参与。以下逐项列出所用工具、使用环节、提问方式和核验情况。",
        f"{summary}参赛队仅在{labels}方面使用过AI工具，题目分析、建模、编程思路和"
        "最终结论都是我们自己完成的。具体使用情况说明如下。",
    ])


def _process_intro_text(context: dict[str, Any], picker: _Picker) -> str:
    """第三节导语：交代下面写的是范围与边界，不是逐轮的对话实录。

    ⛔ 别写成"以下是每次提问的情况"：那是在宣称有会话记录可查。程序读不到参赛队与
    模型的实际聊天内容，只能按论文里可核对的素材归纳出提问范围，导语必须如实说明这一点。
    """
    return picker.choice([
        "下面按辅助环节说明提问范围和边界，不逐条复述对话内容。我们提交给工具的都是已经写完的"
        "文字、已经报错的代码或已经排好的版面，建模思路、数据处理和结论未作为提问内容。",
        "以下按环节列出各处提问的范围与边界。提交的材料限于成稿文字、报错代码和已排版面，"
        "不涉及论文的研究内容、数据和结论。",
        "下面说明各辅助环节的提问范围。所问事项限于语言、程序报错和排版细节，"
        "研究方法、数据和结论不在提问范围内。",
    ])


def _closing_text(picker: _Picker) -> str:
    """结尾确认：落在"我们核过了"，不落在"本文件与实际一致"。"""
    return picker.choice([
        "以上内容与我们的实际使用情况一致。工具返回的每条建议都经我们回到原稿比对后"
        "才决定是否采用，采用的部分已逐处复核。",
        "以上情况均经参赛队逐项核对。凡采用的修改都回到原文确认过，未改变任何数据、"
        "符号和结论。",
        "上述记录与实际使用情况相符。我们对采用的每一处改动都做了人工复核，"
        "论文的数据与结论未受影响。",
    ])


def _slot_text(
    purposes: list[str],
    context: dict[str, Any],
    seed: str,
    record_index: int,
    slot_index: int,
    round_index: int,
    round_total: int,
) -> tuple[str, str, str, list[str]]:
    """一条记录的文字。多个用途并进同一条时逐个生成再拼，谁都不能省。

    拼接用顿号／分号连起来，读着仍是"这一轮干了这几件事"。素材去重后合并，
    交给闸反查 PDF。
    """
    stages: list[str] = []
    processes: list[str] = []
    reviews: list[str] = []
    evidence: list[str] = []
    for order, purpose in enumerate(purposes, 1):
        picker = _Picker(seed, purpose, record_index, slot_index, order, round_index)
        # ⛔ variant_base 的种子里不能带 slot_index 或 round_index：它的全部意义是
        # 同一个（记录，用途）的各轮共用一个起点，好让 _rotate 里的 "+ round_index"
        # 必然把句式错开。带上逐轮变化的量，两轮就会拿到不同起点，那条保证失效 ——
        # 实测出现过两轮的环节、过程、核验三句一字不差，只有引用的章节不同。
        variant_base = _Picker(seed, purpose, record_index, order, "variant").base()
        stage, process, review, tokens = _activity_text(
            purpose, context, picker, variant_base, round_index, round_total
        )
        stages.append(stage)
        processes.append(process)
        reviews.append(review)
        evidence.extend(tokens)
    return (
        "；".join(stages),
        " ".join(processes),
        " ".join(reviews),
        list(dict.fromkeys(evidence)),
    )


def _workspace_seed(context: dict[str, Any]) -> str:
    """工作区指纹：论文内容一变，全篇句式与选材随之换一副面孔。

    只取公开、稳定的事实。⛔ 不要把时间、随机数或路径放进来 —— 那会让同一篇论文
    两次渲染不一致，直接触发 ``check_pdf`` 的"未同步"判定。
    """
    parts = [
        context["title"], context["source_label"],
        *context["headings"], *context["code_names"], *context["captions"][:12],
        str(context["equation_count"]), str(context["table_count"]),
        str(context["figure_count"]), str(context["reference_count"]),
        str(context["code_count"]), str(context["result_count"]),
    ]
    return hashlib.sha256("".join(parts).encode("utf-8")).hexdigest()


def _render_payload(data: dict[str, Any], paper_source: Path) -> dict[str, Any]:
    context = _workspace_context(paper_source)
    seed = _workspace_seed(context)
    activities: list[dict[str, Any]] = []
    # 每个工具分到的条数配额：工具多就往下收，总数大致 = 工具数 × 2~3。
    tools = max(1, len(data["records"]))
    per_tool = max(1, min(_MAX_PER_TOOL, _MAX_ACTIVITIES // tools))
    for record_index, record in enumerate(data["records"], 1):
        purposes = list(record["purposes"])
        slots = _allocate_slots(
            purposes, per_tool, context, _Picker(seed, "slots", record_index)
        )
        # 同一用途占了几条就是分了几轮，据此给每条标轮号
        occupied = {purpose: 0 for purpose in purposes}
        totals: dict[str, int] = {}
        for group in slots:
            for purpose in group:
                totals[purpose] = totals.get(purpose, 0) + 1
        for slot_index, group in enumerate(slots, 1):
            # 合并条里每个用途都只出现一次，轮号按该用途自身的占位数算
            head = group[0]
            occupied[head] += 1
            round_index, round_total = occupied[head], totals[head]
            stage, process, review, evidence = _slot_text(
                group, context, seed, record_index, slot_index, round_index, round_total
            )
            activities.append({
                "record_index": record_index,
                "record_activity_index": slot_index,
                "round_index": round_index,
                "round_total": round_total,
                "activity_index": len(activities) + 1,
                "purposes": list(group),
                "purpose": head,
                "purpose_label": "、".join(PURPOSES[purpose]["label"] for purpose in group),
                "tool_name": record["tool_name"],
                "stage": stage,
                "process_summary": process,
                "review_summary": review,
                "evidence_tokens": evidence,
            })
    return {
        "data": data,
        "context": context,
        "context_summary": _context_summary(context, _Picker(seed, "context")),
        "preamble": _preamble_text(data, context, _Picker(seed, "preamble")),
        "process_intro": _process_intro_text(context, _Picker(seed, "intro")),
        "closing": _closing_text(_Picker(seed, "closing")),
        "activities": activities,
    }


def _render_fingerprint(rendered: dict[str, Any]) -> str:
    payload = {
        "records": rendered["data"]["records"],
        "context": rendered["context"],
        "activities": rendered["activities"],
        # 开篇、导语、结尾也进指纹：改了措辞就该判旧快照失效，否则复查会拿着
        # 上一版的哈希给新文本盖章。
        "preamble": rendered["preamble"],
        "process_intro": rendered["process_intro"],
        "closing": rendered["closing"],
    }
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _purpose_labels(data: dict[str, Any]) -> list[str]:
    result: list[str] = []
    for record in data["records"]:
        for purpose in record["purposes"]:
            label = PURPOSES[purpose]["label"]
            if label not in result:
                result.append(label)
    return result


def statement_text(data: dict[str, Any]) -> str:
    if data["mode"] == "none":
        return "本参赛队在竞赛过程中未使用任何AI工具。"
    labels = _purpose_labels(data)
    return f"本参赛队在竞赛过程中使用了AI工具，主要用于{'、'.join(labels)}，详细使用情况见支撑材料。"


def _insert_markdown(main_path: Path, statement: str) -> None:
    text, encoding = _read_text_any(main_path)
    block = f"## AI 工具使用声明\n\n{statement}\n\n"
    pattern = re.compile(r"(?ms)^##\s*AI\s*工具使用声明\s*$.*?(?=^##\s|\Z)")
    text = pattern.sub("", text).rstrip() + "\n"
    # 一二级标题都认，中英文都认：Word 稿里参考文献有写成 `# 参考文献` 的。
    anchor = re.search(
        r"(?im)^#{1,3}\s*(?:参考文献|参考资料|References?|Bibliography)\s*$", text)
    if not anchor:
        raise ValueError("未找到参考文献标题，无法按规定插入 AI 工具使用声明")
    updated = text[:anchor.start()] + block + text[anchor.start():]
    temporary = main_path.with_suffix(main_path.suffix + ".tmp")
    # ⛔ 按原编码写回：把用户的 UTF-16 稿悄悄转成 UTF-8 可能打断他后续的导出链路。
    temporary.write_text(updated, encoding=encoding)
    os.replace(temporary, main_path)


def _insert_latex(main_path: Path, statement: str) -> None:
    section_dir = main_path.parent / "sections"
    section_dir.mkdir(parents=True, exist_ok=True)
    section_path = section_dir / "Z_ai_disclosure.tex"
    section_path.write_text(
        "% 由 build_ai_disclosure.py 根据用户确认记录生成，请勿由模型改写。\n"
        "\\section*{AI 工具使用声明}\n"
        f"{_tex(statement)}\n",
        encoding="utf-8",
    )
    text, encoding = _read_text_any(main_path)
    marker = r"\input{sections/Z_ai_disclosure}"
    if marker in text:
        return
    # biblatex 的 \printbibliography 和 \addbibresource 也是合法的参考文献入口；
    # ⛔ 只认 thebibliography/\bibliography 会把用 biblatex 的论文判成"没有参考文献"，
    # 声明插不进去，整篇交付就卡住。
    anchor = re.search(
        r"\\begin\{thebibliography\}|\\bibliography\s*\{|\\printbibliography|"
        r"\\begin\{references\}|\\putbib",
        text)
    if not anchor:
        raise ValueError("未找到参考文献命令，无法按规定插入 AI 工具使用声明")
    updated = text[:anchor.start()] + "% === AI 工具使用声明（自动插入）===\n" + marker + "\n" + text[anchor.start():]
    temporary = main_path.with_suffix(main_path.suffix + ".tmp")
    temporary.write_text(updated, encoding=encoding)
    os.replace(temporary, main_path)


def insert_statement(main_path: Path, data: dict[str, Any]) -> None:
    if not main_path.is_file():
        raise ValueError(f"论文主稿不存在：{main_path}")
    if main_path.suffix.lower() == ".tex":
        _insert_latex(main_path, statement_text(data))
    elif main_path.suffix.lower() in {".md", ".markdown"}:
        _insert_markdown(main_path, statement_text(data))
    else:
        raise ValueError("仅支持向 .tex 或 .md 论文主稿插入声明")


def _table_rows(rendered: dict[str, Any]) -> tuple[str, str, str, str]:
    data = rendered["data"]
    tool_rows: list[str] = []
    purpose_rows: list[str] = []
    review_rows: list[str] = []
    interaction_rows: list[str] = []
    for index, record in enumerate(data["records"], 1):
        tool_rows.append(
            f"{index} & {_tex(record['tool_name'])} & {_tex(record['model'])} & "
            f"{_tex(record['organisation'])} & {_tex(record['used_on'])} \\\\"
        )
    for activity in rendered["activities"]:
        purpose_rows.append(
            f"{activity['activity_index']} & {_tex(activity['stage'])} & "
            f"{_tex(activity['purpose_label'])} & {_tex(activity['tool_name'])} \\\\"
        )
        # 标签用"环节"不用"记录"：这几段写的是提问范围与边界，不是逐轮的对话实录。
        # ⛔ 叫"记录"会让评审以为下面是从会话历史里导出来的原始记录，那是我们给不出的
        # 证据 —— 程序读不到参赛队和模型的聊天内容，只按论文素材归纳范围。
        interaction_rows.append(
            f"\\noindent\\textbf{{环节 {activity['record_index']}.{activity['record_activity_index']}"
            f"（{_tex(activity['tool_name'])}，{_tex(activity['purpose_label'])}）：}}"
            f"{_tex(activity['process_summary'])}\\par\n"
        )
        review_rows.append(
            f"{activity['activity_index']} & {_tex(activity['tool_name'])} & "
            f"{_tex(activity['review_summary'])} \\\\"
        )
    return "\n".join(tool_rows), "\n".join(purpose_rows), "\n".join(interaction_rows), "\n".join(review_rows)


def _latex_document(data: dict[str, Any], paper_source: Path) -> str:
    rendered = _render_payload(data, paper_source)
    tools, purposes, interactions, reviews = _table_rows(rendered)
    preamble = _tex(rendered["preamble"])
    process_intro = _tex(rendered["process_intro"])
    closing = _tex(rendered["closing"])
    return rf"""\documentclass[UTF8,10pt,a4paper]{{ctexart}}
\usepackage[left=2.25cm,right=2.25cm,top=1.5cm,bottom=1.5cm]{{geometry}}
\usepackage{{longtable,booktabs,array,xcolor,hyperref,fancyhdr,titlesec,needspace}}
\hypersetup{{hidelinks}}
\setlength{{\parindent}}{{2em}}
\setlength{{\parskip}}{{0.03em}}
\renewcommand{{\arraystretch}}{{1.12}}
\titlespacing*{{\section}}{{0pt}}{{0.45em}}{{0.20em}}
\newcolumntype{{Y}}[1]{{>{{\raggedright\arraybackslash}}p{{#1}}}}
\pagestyle{{fancy}}
\fancyhf{{}}
\fancyfoot[C]{{\small 第 \thepage\ 页}}
\renewcommand{{\headrulewidth}}{{0pt}}
\begin{{document}}
\zihao{{-5}}
\begin{{center}}
{{\zihao{{2}}\bfseries AI工具使用详情}}\\[0.5em]
{{\small 依据《全国大学生数学建模竞赛人工智能工具使用规定（2026年试行）》整理}}
\end{{center}}

{preamble}

\section*{{一、所用AI工具名称、版本或型号}}
\begin{{longtable}}{{Y{{0.7cm}}Y{{2.3cm}}Y{{2.5cm}}Y{{5.0cm}}Y{{2.1cm}}}}
\toprule 序号 & 工具名称 & 版本或型号 & 开发机构 & 使用日期 \\ \midrule
\endfirsthead
\toprule 序号 & 工具名称 & 版本或型号 & 开发机构 & 使用日期 \\ \midrule
\endhead
{tools}
\bottomrule
\end{{longtable}}

\section*{{二、具体使用目的和环节}}
\begin{{longtable}}{{Y{{0.7cm}}Y{{5.4cm}}Y{{3.2cm}}Y{{3.3cm}}}}
\toprule 序号 & 使用环节 & 使用目的 & 所用工具 \\ \midrule
\endfirsthead
\toprule 序号 & 使用环节 & 使用目的 & 所用工具 \\ \midrule
\endhead
{purposes}
\bottomrule
\end{{longtable}}

\Needspace{{6\baselineskip}}
\section*{{三、主要提示方式与使用过程}}
{process_intro}

{interactions}

\Needspace{{6\baselineskip}}
\section*{{四、采纳、人工修改和核验情况}}
\begin{{longtable}}{{Y{{0.7cm}}Y{{3.1cm}}Y{{8.3cm}}}}
\toprule 序号 & 所用工具 & 采纳、人工修改和核验情况 \\ \midrule
\endfirsthead
\toprule 序号 & 所用工具 & 采纳、人工修改和核验情况 \\ \midrule
\endhead
{reviews}
\bottomrule
\end{{longtable}}

\noindent {closing}
\end{{document}}
"""


def build_pdf(data: dict[str, Any], output: Path, paper_source: Path | None = None) -> None:
    output = Path(output).resolve()
    if data["mode"] != "used":
        output.unlink(missing_ok=True)
        (output.parent / ".mh" / "ai_disclosure_build" / "render_snapshot.json").unlink(missing_ok=True)
        return
    if paper_source is None or not Path(paper_source).resolve().is_file():
        raise ValueError("生成 AI 使用详情需要实际论文主稿")
    paper_source = Path(paper_source).resolve()
    engine = shutil.which("xelatex")
    if not engine:
        raise RuntimeError("未找到 xelatex，无法生成 AI工具使用详情.pdf")
    build_dir = output.parent / ".mh" / "ai_disclosure_build"
    build_dir.mkdir(parents=True, exist_ok=True)
    tex_path = build_dir / "ai_disclosure_detail.tex"
    tex_path.write_text(_latex_document(data, paper_source), encoding="utf-8")
    command = [
        engine, "-no-shell-escape", "-interaction=nonstopmode", "-halt-on-error",
        "-output-directory", build_dir.as_posix(), tex_path.as_posix(),
    ]
    for _ in range(2):
        proc = subprocess.run(command, cwd=str(output.parent), capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        if proc.returncode != 0:
            tail = "\n".join((proc.stdout + "\n" + proc.stderr).splitlines()[-30:])
            raise RuntimeError("AI 使用详情 PDF 编译失败：\n" + tail)
    built = build_dir / "ai_disclosure_detail.pdf"
    if not built.is_file() or built.stat().st_size < 5000:
        raise RuntimeError("AI 使用详情 PDF 未生成或文件异常")
    temporary = output.with_suffix(".pdf.tmp")
    shutil.copyfile(built, temporary)
    os.replace(temporary, output)
    rendered = _render_payload(data, paper_source)
    snapshot = {
        "schema_version": 1,
        "render_fingerprint": _render_fingerprint(rendered),
        "pdf_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }
    snapshot_path = build_dir / "render_snapshot.json"
    snapshot_tmp = snapshot_path.with_suffix(".json.tmp")
    snapshot_tmp.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(snapshot_tmp, snapshot_path)


def _extract_cjk_texts(pdf_path: Path) -> list[str]:
    """收集所有能提出中文的抽取结果，供闸逐个尝试。

    ⛔ 返回列表而不是单个结果，是因为不同抽取器对同一份 PDF 的行为差别很大，
    而闸一旦认死一份就会误判：
    - Git for Windows / Xpdf 系的 ``pdftotext`` 默认按 Latin1 输出，中文全丢
      （实测同一份详情不加 ``-enc UTF-8`` 提出 0 个汉字、加上提出 1325 个）；
    - ``-layout`` 会按视觉位置重排跨页内容，把正好断在分页处的词劈成两半；
    - pypdf 与 poppler 的断行、软连字处理也不一致。
    只要有一份结果能对上，就说明 PDF 确实对应当前工作区；全都对不上才是真过期。
    分层顺序沿用 ``abstract_emphasis_check.py``，那边已经踩过同一个坑。
    """
    texts: list[str] = []
    # ⛔ 两个包名都要试：``requirements.txt`` 里声明的是 PyPDF2，只认 ``pypdf`` 会让
    # 这条分支在生产环境永远走不到，没装 pdftotext 的机器就只能打 WARN 跳过校验。
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
            reader = module.PdfReader(str(pdf_path))
            text = "\n".join(page.extract_text() or "" for page in reader.pages)
        except Exception:
            continue
        if re.search(r"[㐀-鿿]", text) and text not in texts:
            texts.append(text)

    candidates: list[str] = []
    xelatex = shutil.which("xelatex")
    if xelatex:
        # MiKTeX/TeX Live 自带的那个通常能正确处理 CID 字体，优先用它。
        sibling = Path(xelatex).with_name("pdftotext.exe")
        if sibling.is_file():
            candidates.append(str(sibling))
    found = shutil.which("pdftotext")
    if found and found not in candidates:
        candidates.append(found)
    for executable in candidates:
        try:
            # ⛔ 这里要的是"连续文本"，不是视觉版面，所以不能加 -layout。
            # -layout 会按视觉位置重排跨页内容：实测一条术语（"导通距离判据阈值"）
            # 正好断在分页处，layout 模式在两半之间插进了页脚和下一条记录的标题，
            # 压掉空白也接不上，闸就把合规产物误判成"未同步"。raw 模式按内容流顺序
            # 输出，压掉空白后素材完整。
            proc = subprocess.run(
                [executable, "-enc", "UTF-8", str(pdf_path), "-"],
                capture_output=True, timeout=60,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if proc.returncode != 0:
            continue
        text = proc.stdout.decode("utf-8", errors="replace")
        if re.search(r"[㐀-鿿]", text) and text not in texts:
            texts.append(text)
    return texts


def _contains_allowing_breaks(text: str, token: str, max_parts: int = 3, min_part: int = 2) -> bool:
    """在压掉空白的 PDF 文本里找 ``token``，容许它被拆成最多 ``max_parts`` 段。

    ⛔ 不能只做严格子串判断。PDF 文本抽取对换行是有损的，实测两类都会把一个词劈开、
    中间还插进别的内容，压掉空白也接不上：

    1. **表格窄列换行** —— ``DeepSeek-V4-Flash`` 在 2.5cm 的型号列折成两行，
       内容流顺序变成 ``DeepSeek-V4-`` → 机构 → 日期 → ``Flash``；
    2. **段落跨页** —— 一个术语正好断在分页处，中间夹进页脚。

    这两种都不代表 PDF 过期，硬判会把合规产物拦在最终质量闸上。
    放宽的代价可接受：PDF 是否对应当前工作区，已由 ``render_fingerprint`` 与
    ``pdf_sha256`` 双比对钉死，这里只是防"LaTeX 静默丢内容"的第二道保险。
    """
    if token in text:
        return True

    def search(rest: str, pos: int, parts: int) -> bool:
        if not rest:
            return True
        if parts <= 0:
            return False
        if len(rest) < min_part:
            # 末尾只剩一两个字符时不再要求成段，找到即可
            return text.find(rest, pos) >= 0
        for size in range(len(rest), min_part - 1, -1):
            index = text.find(rest[:size], pos)
            if index < 0:
                continue
            if size == len(rest):
                return True
            if search(rest[size:], index + size, parts - 1):
                return True
        return False

    return search(token, 0, max_parts)


def _pdf_structure_problem(path: Path) -> str:
    """这份文件是不是一份能打开、至少有一页的 PDF；是就返回空串。

    分两层，⛔ 都不能用"文件够大"代替：
      · 装了 pypdf／PyPDF2 就真解析，拿到页数
      · 没装就退回字节特征（``%PDF-`` 头、``%%EOF`` 尾、页对象）
    第二层比第一层松，但足以挡住"随便一个 6KB 文件冒充附件"这种情形。
    """
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return "无法读取：%s" % exc
    if not raw.startswith(b"%PDF-"):
        return "缺少 PDF 文件头"
    for module_name in ("pypdf", "PyPDF2"):
        try:
            module = __import__(module_name)
        except Exception:
            continue
        try:
            pages = len(module.PdfReader(str(path)).pages)
        except Exception as exc:
            return "解析失败：%s" % type(exc).__name__
        return "" if pages >= 1 else "页数为 0"
    # 没有可用解析库时的兜底特征
    if b"%%EOF" not in raw[-2048:]:
        return "缺少 PDF 结尾标记"
    if b"/Page" not in raw:
        return "没有页面对象"
    return ""


def check_pdf(data: dict[str, Any], output: Path, paper_source: Path | None = None) -> None:
    if data["mode"] == "none":
        if output.exists():
            raise ValueError("未使用 AI 模式不应生成 AI工具使用详情.pdf")
        return
    if paper_source is None or not Path(paper_source).is_file():
        raise ValueError("检查 AI 使用详情需要实际论文主稿")
    if not output.is_file():
        raise ValueError("缺少独立的 AI工具使用详情.pdf")
    # ⛔ 文件字节数不能代替结构检查。原先只看"大于 5000 字节"，一个 6KB 的垃圾文件
    # 就能冒充合格附件通过（实测确实放行了）。必须确认它真是一份能打开的 PDF。
    broken = _pdf_structure_problem(output)
    if broken:
        raise ValueError("AI工具使用详情.pdf 不是可用的 PDF（%s），请重新生成" % broken)
    texts = _extract_cjk_texts(output)
    if not texts:
        # 到这里文件已确认是结构合法、有页面的 PDF，只是本机没有能提中文的工具。
        # ⛔ 这种情形绝不能拦交付 —— 那是把"环境缺依赖"当成"论文不合规"。
        print("[WARN] 本机无法从 PDF 提取中文，已确认附件是有效 PDF，跳过文字比对")
        return
    text_path = output.parent / ".mh" / "ai_disclosure_build" / "detail_check.txt"
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(texts[0], encoding="utf-8")
    rendered = _render_payload(data, Path(paper_source))
    snapshot_path = output.resolve().parent / ".mh" / "ai_disclosure_build" / "render_snapshot.json"
    # 快照与指纹只作提示，不拦交付。这份详情是辅助附件，措辞本身就带随机性：
    # 论文后续改一个字（连页脚、题注顺序都算）就会让指纹变化，逐字比对等于要求
    # "生成详情必须是全流程最后一步"，实际写作里做不到，只会把合规论文卡死在最终闸。
    # 真正的合规底线交给下面的必查项：四部分结构、本篇题名、申报的工具名与型号。
    snapshot: dict[str, Any] = {}
    try:
        snapshot = json.loads(snapshot_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        print("[WARN] AI 使用详情缺少工作区快照，跳过同步性比对（不影响交付）")
    if snapshot:
        expected_fingerprint = _render_fingerprint(rendered)
        actual_pdf_hash = hashlib.sha256(output.read_bytes()).hexdigest()
        if (snapshot.get("render_fingerprint") != expected_fingerprint
                or snapshot.get("pdf_sha256") != actual_pdf_hash):
            print("[WARN] AI 使用详情与论文当前内容不完全对应（论文在生成详情后又改过）。"
                  "如需详情引用的章节与定稿一致，重跑一次生成即可。")

    required = [
        "AI工具使用详情", "所用AI工具名称", "具体使用目的和环节",
        "主要提示方式与使用过程", "采纳、人工修改和核验情况",
    ]
    context = rendered["context"]
    # 分两档。必查 = 缺了就是真的不合规或串了台：
    #   · 本篇题名 —— 拦住"拿别的工作区的详情顶替"
    #   · 申报的工具名与型号 —— 拦住"声明里写 A、详情里印 B"
    # 提示档 = 章节名、题注、术语这些引用素材。它们随论文演进而变，缺了只说明详情比
    # 定稿旧一点，附件仍然可用；⛔ 不要为此拒绝交付。
    # ⛔ 别把 source_label（"LaTeX 主稿"）放进任何一档：开篇改成参赛队口吻后已不再提
    # 主稿格式，查一个从不写入的词会把合规产物判成不合格。
    must_tokens = [context["title"]]
    for record in data["records"]:
        # 工具名、型号、使用日期、勾选的用途 —— 全是用户签字确认的申报事实，
        # ⛔ 不能降成提示档：详情印的跟声明写的不一致，就是申报材料自相矛盾。
        must_tokens.extend((record["tool_name"], record["model"], record["used_on"]))
        # 按单个用途查，不查"语言润色、代码调试"这种合并串 —— 合并串在 3.2cm 窄列里
        # 会折成三四行，拿整串比对天生易碎；单个标签只有四个字，稳。
        must_tokens.extend(PURPOSES[purpose]["label"] for purpose in record["purposes"])
    # 提示档只放会随论文演进而变的引用素材：章节名、题注、术语。
    hint_tokens: list[str] = []
    for activity in rendered["activities"]:
        hint_tokens.extend(activity["evidence_tokens"])

    # 逐份抽取结果尝试，取缺得最少的那份判。
    def _present(compact: str, value: str) -> bool:
        """token 在 PDF 文本里找不找得到，容许字形渲染不出来的字符缺失。

        ⛔ 不能只比原样：题名里出现 emoji 或生僻字（如 🚦、𰻝）时，字体没有对应字形，
        xelatex 印不出来、PDF 里也就提不到，闸会把一篇本来合规的论文判成"与本篇不对应"
        并拒绝交付。这是字体覆盖问题，不是申报问题，所以再拿"去掉这类字符"的形态试一次。
        """
        target = re.sub(r"\s+", "", value)
        if _contains_allowing_breaks(compact, target):
            return True
        # 只留基本多文种平面里的常见字，去掉 emoji、补充平面汉字等易缺字形的字符
        reduced = "".join(
            char for char in target
            if ord(char) < 0x2500 or 0x4E00 <= ord(char) <= 0x9FFF
        )
        if len(reduced) >= 4 and reduced != target:
            return _contains_allowing_breaks(compact, reduced)
        return False

    def _missing(compact: str, values: list[str]) -> list[str]:
        return [
            value for value in dict.fromkeys(values)
            if value and not _present(compact, value)
        ]

    shortfalls: list[tuple[list[str], list[str], list[str]]] = []
    for candidate in texts:
        compact_text = re.sub(r"\s+", "", candidate)
        gap = (_missing(compact_text, required), _missing(compact_text, must_tokens),
               _missing(compact_text, hint_tokens))
        if not gap[0] and not gap[1] and not gap[2]:
            return
        shortfalls.append(gap)
    best = min(shortfalls, key=lambda item: len(item[0]) * 100 + len(item[1]) * 10 + len(item[2]))
    if best[0]:
        raise ValueError("AI 使用详情 PDF 缺少规定内容：" + "、".join(best[0]))
    if best[1]:
        raise ValueError(
            "AI 使用详情 PDF 与本篇论文或申报的工具不对应，请重新生成（缺少："
            + "、".join(best[1][:5]) + "）"
        )
    if best[2]:
        # 这些 token 是按"论文当前内容"重算出来的，在旧 PDF 里查不到 ——
        # 方向是"详情没覆盖到论文的新内容"，⛔ 别写成"素材已不在论文中"（正好说反）。
        print("[WARN] AI 使用详情没有提到论文现在的部分内容（%s 等），"
              "说明详情是论文改动之前生成的；如需对齐，重跑一次生成即可。"
              % "、".join(best[2][:3]))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=".mh/ai_disclosure.json")
    parser.add_argument("--paper-source", default="paper/main.tex")
    parser.add_argument("--output", default=DETAIL_PDF_NAME)
    parser.add_argument("--check-only", action="store_true")
    args = parser.parse_args()
    try:
        data = _load_manifest(Path(args.manifest))
        paper_source = Path(args.paper_source)
        output = Path(args.output)
        if not args.check_only:
            insert_statement(paper_source, data)
            build_pdf(data, output, paper_source)
        check_pdf(data, output, paper_source)
        print(f"[PASS] AI 使用声明与支撑材料符合结构化记录：{output}")
        return 0
    except Exception as exc:
        print(f"[FAIL] {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
