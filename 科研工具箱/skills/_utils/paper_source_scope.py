"""Resolve the active, local LaTeX input tree without executing TeX.

Kept byte-identical in services/ and shared-scripts/ so encrypted standalone
checkers and the backend use the same scope (enforced by regression tests).
"""
from __future__ import annotations

import re
from pathlib import Path

_INPUT = re.compile(r"\\(?:input|include)(?![A-Za-z@])\s*(?:\{([^{}]+)\}|([^\s{}%]+))")
_LITERAL_SKIP = re.compile(
    r"\\begin\{(verbatim\*?|lstlisting|minted|comment)\}[\s\S]*?\\end\{\1\}"
    r"|\\iffalse\b[\s\S]*?\\fi\b", re.I,
)


def strip_comments(text: str) -> str:
    lines = []
    for line in _LITERAL_SKIP.sub("", text).splitlines():
        for m in re.finditer("%", line):
            prefix = line[:m.start()]
            if (len(prefix) - len(prefix.rstrip("\\"))) % 2 == 0:
                line = prefix
                break
        lines.append(line)
    return "\n".join(lines)


def active_sources(paper_dir: Path) -> list[Path]:
    """Main is authoritative; only pre-assembly drafts fall back to sections.

    Resolve inputs relative to the including file, then the TeX working
    directory; bound traversal to this workspace, detect cycles, ignore
    commented directives. Missing inputs remain the compiler's responsibility.
    """
    paper = Path(paper_dir).resolve()
    main = paper / "main.tex"
    if not main.is_file():
        return sorted((paper / "sections").rglob("*.tex"))
    root = paper.parent
    seen: set[Path] = set()
    result: list[Path] = []
    includeonly = re.search(r"\\includeonly\s*\{([^{}]*)\}", strip_comments(main.read_text(encoding="utf-8", errors="replace")))
    allowed = {s.strip().removesuffix(".tex") for s in includeonly.group(1).split(",")} if includeonly else None

    def visit(path: Path, depth: int = 0) -> None:
        path = path.resolve()
        if path in seen or not path.is_relative_to(root) or not path.is_file():
            return
        if depth > 100:
            raise ValueError("LaTeX input nesting exceeds 100 levels")
        seen.add(path)
        result.append(path)
        if len(result) > 2048:
            raise ValueError("LaTeX input tree exceeds 2048 files")
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for match in _INPUT.finditer(text):
            name = (match.group(1) or match.group(2)).strip()
            if any(c in name for c in ("\\", "#", "$")):
                continue  # macros need TeX; never guess another file
            if allowed is not None and match.group().startswith(r"\include") and name.removesuffix(".tex") not in allowed:
                continue
            rel = Path(name)
            if not rel.suffix:
                rel = rel.with_suffix(".tex")
            for base in (paper, path.parent, root):
                candidate = (base / rel).resolve()
                if candidate.is_relative_to(root) and candidate.is_file():
                    visit(candidate, depth + 1)
                    break

    visit(main)
    return result


def source_label(path: Path, paper_dir: Path) -> Path:
    """A diagnostic path, not permission to read outside the source tree."""
    path, paper = path.resolve(), paper_dir.resolve()
    if path.is_relative_to(paper):
        return path.relative_to(paper)
    if path.is_relative_to(paper.parent):
        return Path("..") / path.relative_to(paper.parent)
    raise ValueError("Source is outside the workspace")


class ExpandedSource:
    def __init__(self) -> None:
        self.text = ""
        self.parts: list[str] = []
        self.origins: list[tuple[int, Path, int]] = []
        self.size = 0

    def append(self, text: str, path: Path, line: int) -> None:
        if not text:
            return
        self.origins.append((self.size, path, line))
        self.parts.append(text)
        self.size += len(text)
        if self.size > 16 * 1024 * 1024:
            raise ValueError("Expanded LaTeX exceeds the 16 MiB checking budget")

    def location(self, offset: int, paper_dir: Path) -> str:
        from bisect import bisect_right
        index = bisect_right([item[0] for item in self.origins], offset) - 1
        start, path, line = self.origins[max(0, index)]
        line += self.text.count("\n", start, offset)
        return f"{source_label(path, paper_dir).as_posix()}:{line}"


def expanded_documents(paper_dir: Path) -> list[ExpandedSource]:
    """Inline active inputs for contextual checks, preserving source locations.

    Includes may occur more than once. Bound cycles, expansions and bytes; never
    execute TeX or read a file outside active_sources' workspace-bounded scope.
    """
    paper = paper_dir.resolve()
    sources = active_sources(paper)
    available = set(sources)
    main = paper / "main.tex"
    roots = [main] if main in available else sources
    texts = {p: strip_comments(p.read_text(encoding="utf-8", errors="replace")) for p in sources}
    only = re.search(r"\\includeonly\s*\{([^{}]*)\}", texts.get(main, ""))
    allowed = {n.strip().removesuffix(".tex") for n in only.group(1).split(",")} if only else None
    documents = []
    visits = 0

    def expand(path: Path, doc: ExpandedSource, stack: set[Path]) -> None:
        nonlocal visits
        if path in stack:
            return  # compiler/source gate owns cyclic input errors
        visits += 1
        if len(stack) > 100 or visits > 2048:
            raise ValueError("LaTeX input expansion exceeds checking budget")
        text = texts[path]
        pos = 0
        for match in _INPUT.finditer(text):
            doc.append(text[pos:match.start()], path, text.count("\n", 0, pos) + 1)
            name = (match.group(1) or match.group(2)).strip()
            target = None
            excluded = allowed is not None and match.group().startswith(r"\include") and name.removesuffix(".tex") not in allowed
            if not excluded and not any(c in name for c in ("\\", "#", "$")):
                rel = Path(name)
                if not rel.suffix:
                    rel = rel.with_suffix(".tex")
                for directory in (paper, path.parent, paper.parent):
                    candidate = (directory / rel).resolve()
                    if candidate in available:
                        target = candidate
                        break
            if target:
                expand(target, doc, stack | {path})
            elif not excluded:
                # Keep unknown inputs visible; do not pretend we checked them.
                doc.append(match.group(), path, text.count("\n", 0, match.start()) + 1)
            pos = match.end()
        doc.append(text[pos:], path, text.count("\n", 0, pos) + 1)

    for root in roots:
        doc = ExpandedSource()
        expand(root, doc, set())
        doc.text = "".join(doc.parts)
        doc.parts.clear()
        documents.append(doc)
    return documents



if __name__ == "__main__":
    import sys
    for source in active_sources(Path(sys.argv[1] if len(sys.argv) > 1 else "paper")):
        print(source.as_posix())
