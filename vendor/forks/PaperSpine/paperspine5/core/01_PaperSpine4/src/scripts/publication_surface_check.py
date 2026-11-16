#!/usr/bin/env python3
"""Locate likely production notes in manuscript text; never edit the manuscript.

Legacy: publication_surface_check.py OUTPUT_DIR --markdown --write
Current: publication_surface_check.py --source current.tex current.docx --source current.pdf

PASS/ok means only that extraction succeeded and these heuristic rules did not
match. It is not semantic coverage, scientific review or submission readiness.
TeX supports literal input/include and simple zero-argument caption macros, not
arbitrary TeX execution. Inspect the rendered manuscript and retain human review.
"""

from __future__ import annotations

import argparse
import json
import posixpath
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import unquote
from xml.etree import ElementTree as ET

LIMITATIONS = (
    "Advisory heuristic only: no rule matches does not establish semantic coverage, "
    "scientific correctness or submission readiness. Retain human scientific review; "
    "inspect context before any correction. No manuscript text is deleted or changed.",
    "TeX extraction follows literal input/include and simple zero-argument macros, "
    "not arbitrary TeX expansion, class/package code or conditional execution. "
    "PDF text extraction is not OCR or visual review; DOCX locations are paragraphs, not rendered pages.",
    "DOCX scanning covers body paragraphs and section-referenced headers/footers. "
    "Footnotes/endnotes, unreferenced package parts, comments/metadata and image-only text are not scanned.",
)

# Match production assertions, not the words user/selection/workflow/review alone.
# Measured participant choices and ordinary AI disclosures are valid.
_SURFACE = r"(?:figures?|figs?\.?|captions?|manuscript|draft|figure\s+plan|motivation)"
_FIGURE_NUMBER = r"(?:S?\d+[a-z]?|REF)"
_FIGURE_NUMBERS = rf"{_FIGURE_NUMBER}(?:(?:\s*,\s*(?:and\s+)?|\s+(?:and|&)\s+|\s*[-–]\s*){_FIGURE_NUMBER})*"
PATTERNS = (
    ("inline audit tag", re.compile(r"\[(?:claim|evidence|source|numeric|method|outcome|result)\s*:\s*[SCNMOR]\d+[^\]]*\]", re.I)),
    ("workflow artifact name", re.compile(r"\b(?:writing_rationale_matrix|scientific_evidence_ledger|results_validation|reviewer_audit|claim_register)\.(?:md|json)\b", re.I)),
    ("audit identifier prose", re.compile(r"\b(?:claim|evidence|numeric|method|outcome|result)\s+ID\s*[:=]\s*[SCNMOR]\d+", re.I)),
    ("internal gate narration", re.compile(r"\b(?:artifact_check|progress_check|citation_bank_check|publication_surface_check)\.py\b", re.I)),
    ("user selection production narrative", re.compile(
        rf"(?<!\w){_SURFACE}(?!\w)[^.!?;。！？；]{{0,160}}?"
        r"\b(?:reflect|follow|use|incorporate|based\s+on|according\s+to|correspond\s+to)\s+(?:(?:the|on)\s+)*"
        r"(?:confirmed|saved|user[- ]confirmed|user[- ]saved)\s+(?:user(?:'s)?\s+)?(?:figure\s+)?(?:selections?|choices?)\b", re.I)),
    ("user adoption production narrative", re.compile(
        rf"(?<!\w){_SURFACE}(?!\w)[^.!?;。！？；]{{0,100}}?\b(?:adopted|approved|confirmed)\s+by\s+(?:the\s+)?user\b", re.I)),
    ("user selection web workspace narrative", re.compile(
        rf"(?<!\w){_SURFACE}(?!\w)(?:\s+{_FIGURE_NUMBERS})?\s+(?:use|uses|follow)\s+(?:the\s+)?versions?\s+"
        r"(?:accepted|confirmed|selected|saved)\s+in\s+(?:the\s+)?web\s+workspace\b", re.I)),
    ("export review production narrative", re.compile(
        r"\b(?:the\s+)?reviewer\s+has\s+(?:now\s+)?marked\s+(?:the\s+)?current\s+export\s+complete\b", re.I)),
    ("user selection status", re.compile(
        r"(?im)^\s*(?:confirmed|saved)\s+user\s+(?:figure\s+)?(?:selections?|choices?)\s*(?=[:：.。\n]|$)")),
    ("draft status production block", re.compile(
        r"(?im)^\s*(?:draft|review|delivery|production|manuscript\s+production)\s+status\s*(?=[:：.。\n]|$)|"
        r"(?:^|\n)\s*(?:草稿状态|草稿狀態|制稿状态|製稿狀態|生产状态|生產狀態|审阅状态|審閱狀態|交付状态|交付狀態)\s*(?=[:：.。\n]|$)")),
    ("review pending production status", re.compile(
        r"(?:^|\n|;)\s*(?:(?:independent|scientific|manuscript)\s+)?review\s*(?::\s*|is\s+)?pending\b|"
        r"(?:^|\n|[；;])\s*(?:独立审阅|獨立審閱|科学审阅|稿件审阅|审阅|審閱|审核|審核)\s*[:：]?\s*(?:待完成|待进行|待進行|待处理|待處理|尚未完成)|"
        r"(?:^|\n|[；;])\s*(?:待审阅|待審閱|待审核|待審核)\s*(?=[:：。；\n]|$)", re.I)),
    ("layout check production narrative", re.compile(
        r"\b(?:the\s+)?(?:layout|page\s+layout)\s+(?:(?:has\s+been|was|is)\s+)?visually\s+checked\b|"
        r"(?:版式|排版|布局|佈局)(?:已经|已經|已)?(?:完成)?(?:视觉|視覺|目视|目視)(?:检查|檢查|核查)|"
        r"(?:已|已经|已經)目视(?:检查|檢查)(?:版式|排版|布局|佈局)", re.I)),
    ("submission disclaimer production narrative", re.compile(
        r"\bno\s+submission(?:\s+or\s+publication)?\s+(?:is\s+)?implied\b|"
        r"(?:不代表|不意味着|不意味著|不表示|不暗示)(?:已经|已經|已)?(?:投稿|提交期刊)(?:或发表|或發表)?", re.I)),
    ("user selection production narrative (Chinese)", re.compile(
        r"(?:图(?:件|表|注)?|圖(?:件|表|注)?|正文|稿件|研究动机|研究動機)[^。！？；\n]{0,100}?"
        r"(?:(?:反映|体现|體現|采用|採用|依据|依據|根据|根據|遵循)(?:了)?(?:用户|用戶)(?:已经|已經|已)?(?:确认|確認|保存)的(?:选择|選擇|选图|選圖)|"
        r"(?:已经|已經|已)?(?:由|被)?(?:用户|用戶)(?:已经|已經|已)?(?:确认|確認|采用|採用|选定|選定))|"
        r"(?:用户|用戶)(?:已经|已經|已)(?:确认|確認|保存|选定|選定|采用|採用)(?:了|的)?(?:选图|選圖|图|圖|研究动机|研究動機|稿件)")),
)


@dataclass
class SurfaceResult:
    # Keep the legacy constructor and validate(output_dir) fields usable.
    files: list[str]
    ok: bool
    findings: list[str]
    matches: list[dict] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    limitations: list[str] = field(default_factory=lambda: list(LIMITATIONS))
    extractions: list[dict] = field(default_factory=list)


@dataclass
class _Text:
    value: str
    locations: list[tuple[str, str, int]]
    part: str | None = None

    def slice(self, start: int, end: int) -> _Text:
        return _Text(self.value[start:end], self.locations[start:end], self.part)


def _join(parts: list[_Text]) -> _Text:
    return _Text("".join(p.value for p in parts), [loc for p in parts for loc in p.locations], parts[0].part if parts else None)


def _located(text: str, path: str, kind: str = "line", number: int = 1, part: str | None = None) -> _Text:
    locations = []
    for char in text:
        locations.append((path, kind, number))
        if kind == "line" and char == "\n":
            number += 1
    return _Text(text, locations, part)


def _sub(text: _Text, pattern: str, replacement: str = "") -> _Text:
    """Remove markup while preserving positions in the actual input, not a temp file."""
    parts, start = [], 0
    for match in re.finditer(pattern, text.value, re.S):
        parts.extend([text.slice(start, match.start()),
                      _Text(replacement, [text.locations[match.start()]] * len(replacement), text.part)])
        start = match.end()
    parts.append(text.slice(start, len(text.value)))
    return _join(parts)


def _group(text: str, start: int, opening: str = "{", closing: str = "}") -> tuple[int, int, int] | None:
    while start < len(text) and text[start].isspace():
        start += 1
    if start == len(text) or text[start] != opening:
        return None
    depth, pos = 1, start + 1
    while pos < len(text):
        if text[pos] == "\\":
            pos += 2
            continue
        if text[pos] == opening:
            depth += 1
        elif text[pos] == closing:
            depth -= 1
            if depth == 0:
                return start + 1, pos, pos + 1
        pos += 1
    raise ValueError(f"unclosed {opening}{closing} group")


class _Tex:
    """Small, non-executing reader. Never glob a workspace or open a .bib/.sty/.cls."""

    def __init__(self, result: SurfaceResult, root: Path):
        self.result, self.root = result, root.parent
        self.macros: dict[str, _Text] = {}
        self.includeonly: set[str] | None = None

    def read(self, path: Path, stack: tuple[Path, ...] = ()) -> _Text:
        path = path.resolve()
        if path in stack:
            raise ValueError(f"cyclic TeX include: {path}")
        if len(stack) >= 64:
            raise ValueError(f"TeX include depth exceeds 64: {path}")
        text = path.read_text(encoding="utf-8-sig")
        if str(path) not in self.result.files:
            self.result.files.append(str(path))
        # TeX comments consume the end-of-line too (escaped percent is visible).
        mapped = _located(text, str(path))
        parts, start, pos = [], 0, 0
        while pos < len(text):
            if text[pos] == "\\":
                pos += 2
            elif text[pos] == "%":
                parts.append(mapped.slice(start, pos))
                newline = text.find("\n", pos)
                pos = len(text) if newline == -1 else newline + 1
                start = pos
            else:
                pos += 1
        parts.append(mapped.slice(start, len(text)))
        return self.parse(_join(parts), path, (*stack, path))

    def parse(self, mapped: _Text, path: Path, stack: tuple[Path, ...], expanding: tuple[str, ...] = ()) -> _Text:
        text, parts, pos = mapped.value, [], 0
        while pos < len(text):
            if text[pos] != "\\":
                if text[pos] not in "{}":
                    parts.append(_Text(" " if text[pos] == "~" else text[pos], [mapped.locations[pos]]))
                pos += 1
                continue
            command = re.match(r"\\([a-zA-Z@]+\*?|.)", text[pos:], re.S)
            if not command:
                pos += 1
                continue
            name = command[1].rstrip("*")
            end = pos + command.end()
            group = _group(text, end)
            if name in {"begin", "end"} and group:
                env = text[group[0]:group[1]]
                if name == "end" and env == "document":
                    break
                if name == "begin" and env in {"thebibliography", "CSLReferences", "filecontents", "filecontents*", "comment"}:
                    stop = re.search(r"\\end\s*\{" + re.escape(env) + r"\}", text[group[2]:])
                    if not stop:
                        raise ValueError(f"unclosed {env} environment in {path}")
                    pos = group[2] + stop.end()
                else:
                    pos = group[2]
                continue
            if name in {"newcommand", "renewcommand", "providecommand"} and group:
                macro = text[group[0]:group[1]].lstrip("\\")
                body = _group(text, group[2])
                if body:
                    self.macros[macro] = mapped.slice(body[0], body[1])
                    pos = body[2]
                    continue
            if name == "includeonly" and group:
                self.includeonly = {v.strip() for v in text[group[0]:group[1]].split(",")}
                pos = group[2]
                continue
            if name in {"input", "include"}:
                literal = group or ((m.start(1) + end, m.end(1) + end, m.end() + end)
                                    if (m := re.match(r"\s*([^\s{}]+)", text[end:])) else None)
                if not literal:
                    raise ValueError(f"unresolved TeX {name} at {path}:{mapped.locations[pos][2]}")
                value = text[literal[0]:literal[1]].strip()
                if re.search(r"[\\#{}$]", value):
                    raise ValueError(f"non-literal TeX include at {path}:{mapped.locations[pos][2]}: {value}")
                child = Path(value)
                if child.suffix.lower() in {".bib", ".bbl"}:
                    pos = literal[2]
                    continue
                if child.suffix and child.suffix.lower() != ".tex":
                    raise ValueError(f"unsupported TeX include (expected .tex): {value}")
                if name != "include" or self.includeonly is None or value in self.includeonly or child.stem in self.includeonly:
                    if not child.suffix:
                        child = child.with_suffix(".tex")
                    # TeX resolves relative to the root compile directory; accept
                    # fragment-relative paths if that root path does not exist.
                    target = self.root / child
                    if not target.exists():
                        target = path.parent / child
                    parts.append(self.read(target, stack))
                pos = literal[2]
                continue
            if name in self.macros:
                if name in expanding or len(expanding) >= 64:
                    raise ValueError(f"recursive TeX macro {name} in {path}")
                parts.append(self.parse(self.macros[name], path, stack, (*expanding, name)))
                pos = end
                continue
            # Non-prose arguments: IDs, URLs, bibliography and rendering setup.
            if name in {"label", "ref", "pageref", "autoref", "cref", "Cref", "url", "href", "hyperlink",
                        "bibliography", "bibliographystyle", "addbibresource", "documentclass", "usepackage",
                        "includegraphics", "hypersetup", "setlength", "setcitestyle", "pagestyle"} or name.startswith("cite"):
                optional = _group(text, end, "[", "]")
                while optional:
                    end = optional[2]
                    optional = _group(text, end, "[", "]")
                group = _group(text, end)
                pos = group[2] if group else end
                if name in {"ref", "pageref", "autoref", "cref", "Cref"}:
                    parts.append(_Text("REF", [mapped.locations[end - 1]] * 3))
                continue
            if len(name) == 1:
                replacement = "\n" if name == "\\" else name if name in "%&_#$" else " "
                parts.append(_Text(replacement, [mapped.locations[pos]] * len(replacement)))
            pos = end
        return _join(parts)


def _docx(path: Path) -> list[_Text]:
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
          "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships"}
    with zipfile.ZipFile(path) as archive:
        def read_part(member: str):
            try:
                return ET.fromstring(archive.read(member))
            except (KeyError, ET.ParseError) as exc:
                raise ValueError(f"DOCX part {member}: {exc}") from exc

        body = read_part("word/document.xml").find("w:body", ns)
        if body is None:
            raise ValueError("DOCX has no word/document.xml body")
        parts = {"word/document.xml": body}
        references = body.findall(".//w:sectPr/w:headerReference", ns) + body.findall(".//w:sectPr/w:footerReference", ns)
        if references:
            relationships = {node.get("Id"): node for node in read_part("word/_rels/document.xml.rels")}
            for reference in references:
                relation_id = reference.get(f"{{{ns['r']}}}id")
                relation = relationships.get(relation_id)
                kind = "header" if reference.tag.endswith("headerReference") else "footer"
                if relation is None or relation.get("Type", "").rsplit("/", 1)[-1] != kind:
                    raise ValueError(f"DOCX {kind} reference {relation_id}: missing or wrong relationship")
                target = unquote(relation.get("Target", ""))
                if relation.get("TargetMode") == "External" or not target or "\\" in target or ":" in target:
                    raise ValueError(f"DOCX {kind} reference {relation_id}: unsupported external/invalid target")
                member = posixpath.normpath(posixpath.join("word", target)).lstrip("/")
                if member == ".." or member.startswith("../"):
                    raise ValueError(f"DOCX {kind} reference {relation_id}: target escapes package")
                if member not in parts:
                    root = read_part(member)
                    if root.tag != f"{{{ns['w']}}}{'hdr' if kind == 'header' else 'ftr'}":
                        raise ValueError(f"DOCX part {member}: expected {kind} XML")
                    parts[member] = root
    units = []
    for member, root in parts.items():
        for number, paragraph in enumerate(root.findall(".//w:p", ns), 1):
            # Runs and field results are visible text; instructions/deleted text are not.
            text = "".join((node.text or "") if node.tag == f"{{{ns['w']}}}t" else " "
                           for node in paragraph.iter()
                           if node.tag in {f"{{{ns['w']}}}t", f"{{{ns['w']}}}tab", f"{{{ns['w']}}}br"})
            units.append(_located(text, str(path), "paragraph", number, member))
    return units


def _pdf_text(text: str | None, path: Path, number: int) -> _Text:
    if not text or not text.strip():
        raise ValueError(f"PDF page {number}: no extractable text; image-only/blank page requires inspection, not PASS")
    return _located(text, str(path), "page", number)


def _pdf(path: Path) -> tuple[list[_Text], str]:
    try:
        from pypdf import PdfReader
    except ImportError:
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError as exc:
                raise ValueError("PDF extraction requires pypdf or PyMuPDF (pymupdf/fitz); dependencies unavailable (not checked)") from exc
        with fitz.open(path) as document:
            if document.needs_pass:
                raise ValueError("encrypted PDF cannot be checked without decryption") from None
            if not len(document):
                raise ValueError("PDF has no pages") from None
            units = []
            for number, page in enumerate(document, 1):
                try:
                    text = page.get_text("text")
                except Exception as exc:
                    raise ValueError(f"PDF page {number}: text extraction failed: {exc}") from exc
                units.append(_pdf_text(text, path, number))
        return units, "PyMuPDF"
    reader = PdfReader(path)
    if reader.is_encrypted:
        raise ValueError("encrypted PDF cannot be checked without decryption")
    if not reader.pages:
        raise ValueError("PDF has no pages")
    units = []
    for number, page in enumerate(reader.pages, 1):
        try:
            text = page.extract_text()
        except Exception as exc:
            raise ValueError(f"PDF page {number}: text extraction failed: {exc}") from exc
        units.append(_pdf_text(text, path, number))
    return units, "pypdf"


def _scan(unit: _Text, result: SurfaceResult) -> None:
    # Normalize common whitespace and harmless inline emphasis.
    unit = _sub(unit, r"[*\x60]+|\u00ad")
    unit = _sub(unit, r"(?<!\w)_{1,2}(?=\S)|(?<=\S)_{1,2}(?!\w)")
    unit = _sub(unit, r"(?m)^[ \t]*(?:#{1,6}|[-+>])\s+", "")
    unit = _sub(unit, r"[^\S\n]+", " ")
    for label, pattern in PATTERNS:
        for match in pattern.finditer(unit.value):
            if label.startswith(("user selection", "user adoption")):
                # A figure can report saved/confirmed choices *as study data*.
                # Restrict this exemption to explicit participant/interaction
                # context in the same sentence, never an entire HCI document.
                before = re.split(r"[.!?。！？\n]", unit.value[:match.start()])[-1]
                after = re.split(r"[.!?。！？\n]", unit.value[match.end():])[0]
                context = before + match[0] + after
                if re.search(r"\b(?:participants?|respondents?|experimental\s+task|interaction\s+logs?|clickstream|usability\s+study)\b|"
                             r"(?:受试者|受試者|参与者|參與者|交互日志|交互日誌|可用性实验|可用性實驗)", context, re.I):
                    continue
            offset = match.start() + len(match[0]) - len(match[0].lstrip())
            path, kind, number = unit.locations[offset]
            excerpt = re.sub(r"\s+", " ", match[0]).strip()[:240]
            item = {"path": path, kind: number, "rule": label, "excerpt": excerpt}
            if unit.part:
                item["part"] = unit.part
            if item not in result.matches:
                result.matches.append(item)
                location = f"{path}:{number}" if kind == "line" else f"{path}: {kind} {number}"
                if unit.part:
                    location += f" ({unit.part})"
                result.findings.append(f"{location}: {label}; inspect context ({excerpt})")


def validate(output_dir: Path | None = None, sources: list[Path] | tuple[Path, ...] | None = None) -> SurfaceResult:
    """Check explicit sources, or the three legacy candidates if sources is None.

    Explicit paths replace discovery; absent/unsupported/unreadable inputs fail
    visibly, even if another source is clean. Only --write writes a report.
    """
    result = SurfaceResult([], False, [])
    if sources is None:
        output_dir = Path(output_dir or "paper_rewriting_output")
        final_dir = output_dir / "final_paper"
        sources = [p for p in (final_dir / "main.tex", final_dir / "paper.md", output_dir / "final_paper.md") if p.is_file()]
    if not sources:
        result.errors.append("no final manuscript source was found; specify --source for the current manuscript")
    for path in dict.fromkeys(Path(p).resolve() for p in sources):
        try:
            if path.suffix.lower() not in {".tex", ".md", ".docx", ".pdf"}:
                raise ValueError("unsupported manuscript format; use .tex/.md/.docx/.pdf")
            if not path.is_file():
                raise ValueError("manuscript source does not exist or is not a file")
            if path.suffix.lower() == ".tex":
                units = [_Tex(result, path).read(path)]
                extractor = "literal TeX and zero-argument macros"
            elif path.suffix.lower() == ".md":
                units = [_sub(_located(path.read_text(encoding="utf-8-sig"), str(path)), r"<!--.*?-->")]
                extractor = "UTF-8 Markdown"
            elif path.suffix.lower() == ".docx":
                units = _docx(path)
                extractor = "stdlib XML: body and section-referenced headers/footers"
            else:
                units, extractor = _pdf(path)
            if str(path) not in result.files:
                result.files.append(str(path))
            if not any(u.value.strip() for u in units):
                raise ValueError("no manuscript text was extracted")
            result.extractions.append({"path": str(path), "extractor": extractor, "text_units": len(units)})
            for unit in units:
                _scan(unit, result)
        except Exception as exc:
            # A corrupt optional-parser input must never look like a clean paper.
            result.errors.append(f"{path}: extraction incomplete: {type(exc).__name__}: {exc}")
    result.findings.extend(result.errors)
    result.ok = not result.findings
    return result


def parse_args(argv=None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--source", type=Path, nargs="+", action="extend",
                        help="Current .tex/.md/.docx/.pdf files; repeatable; replaces legacy path discovery.")
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true", help="Write only the report under OUTPUT_DIR; never edit sources.")
    return parser.parse_args(argv)


def to_markdown(result: SurfaceResult) -> str:
    meaning = "no heuristic rule matches" if result.ok else "extraction incomplete" if result.errors else "potential production text; review context"
    lines = ["# Publication Surface Check", "", f"- Status: {'PASS' if result.ok else 'FAIL'} ({meaning})",
             f"- Manuscript source files read: {len(result.files)}", "", *result.limitations,
             "", "## Sources", "", *(f"- {path}" for path in result.files), "", "## Findings", ""]
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- No rule matches; human scientific review remains required.")
    return "\n".join([*lines, ""])


def main(argv=None) -> int:
    args = parse_args(argv)
    output_dir = Path(args.output_dir)
    result = validate(output_dir, sources=args.source)
    markdown = to_markdown(result)
    if args.write:
        output_dir.mkdir(parents=True, exist_ok=True)
        report = output_dir / "publication_surface_check.md"
        manuscript_paths = {*result.files, *(str(path.resolve()) for path in (args.source or []))}
        if str(report.resolve()) in manuscript_paths:
            raise ValueError("report path would overwrite a manuscript source")
        report.write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
