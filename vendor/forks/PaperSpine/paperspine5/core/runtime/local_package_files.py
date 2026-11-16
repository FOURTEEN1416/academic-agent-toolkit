"""Bounded local package inventory. Never executes TeX or editable figure code."""

from __future__ import annotations

import ast
import hashlib
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path, PurePosixPath


def bounded_path(root: Path, raw: str | Path, *, must_exist: bool = True) -> Path:
    for ancestor in (root, *root.parents):
        if ancestor.is_symlink() or (
            hasattr(ancestor, "is_junction") and ancestor.is_junction()
        ):
            raise ValueError(
                "J10 authorized package root contains a symlink/reparse point"
            )
    root = root.resolve()
    candidate = Path(raw)
    if not candidate.is_absolute():
        candidate = root / candidate
    # Check reparse/symlink ancestors before resolving (including Windows junctions).
    candidate = Path(os.path.abspath(candidate))
    try:
        relative = candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError("J10 package path escapes its authorized root") from exc
    probe = root
    for part in relative.parts:
        probe = probe / part
        if probe.is_symlink() or (
            hasattr(probe, "is_junction") and probe.is_junction()
        ):
            raise ValueError("J10 package path contains a symlink/reparse point")
    if must_exist and not candidate.is_file():
        raise ValueError(f"J10 package dependency is missing: {relative.as_posix()}")
    return candidate


def _tex_text(encoded: bytes) -> str:
    text = re.sub(r"(?<!\\)%[^\n]*", "", encoded.decode("utf-8"))
    return re.sub(r"\\iffalse\b.*?\\fi\b", "", text, flags=re.S)


def collect_package_files(
    *,
    workspace: Path,
    run_root: Path,
    verified: dict,
    final_mappings: list,
) -> dict[str, tuple[Path, bytes, str]]:
    """Collect only active TeX references and immutable registered editable assets.

    An editable asset with local references may only use another registered
    auxiliary. Dynamic file reads are rejected rather than scanning private
    material folders or claiming that an incomplete source is self-contained.
    """
    workspace, run_root = workspace.resolve(), run_root.resolve()
    source = verified["source"][0]
    source_root = source.parent
    entries: dict[str, tuple[Path, bytes, str]] = {}
    folded: dict[str, str] = {}

    def add(name: str, path: Path, encoded: bytes, role: str) -> None:
        posix = PurePosixPath(name)
        if posix.is_absolute() or ".." in posix.parts or "\\" in name or ":" in name:
            raise ValueError("J10 unsafe archive member name")
        if name.casefold() in folded:
            old = entries[folded[name.casefold()]]
            if name != folded[name.casefold()] or old[:2] != (path, encoded):
                raise ValueError("J10 package member collision")
            return
        folded[name.casefold()] = name
        entries[name] = (path, encoded, role)

    add("manuscript/paper.pdf", *verified["pdf"], "pdf")
    add("manuscript/paper.docx", *verified["word"], "word")
    add(f"source/{source.name}", *verified["source"], "source")
    visited: set[Path] = set()
    source_files = {source: verified["source"][1]}
    include_only = re.search(
        r"\\includeonly\s*\{([^{}]*)\}", _tex_text(verified["source"][1])
    )
    include_names = (
        {v.strip() for v in include_only[1].split(",")} if include_only else None
    )

    def tex_visit(path: Path, encoded: bytes) -> None:
        if path in visited:
            return
        visited.add(path)
        text = _tex_text(encoded)
        # TeX inputs are normally relative to the main compilation directory;
        # a child-relative path is also accepted when it is unambiguous.
        matches = list(
            re.finditer(
                r"\\(includegraphics\*?|input|include|bibliography|bibliographystyle|addbibresource|documentclass|usepackage|RequirePackage)(?:\s*\[[^\]]*\])?\s*\{([^{}]+)\}",
                text,
            )
        )
        parsed = {match.start() for match in matches}
        for token in re.finditer(
            r"\\(?:includegraphics|input|include|bibliography|bibliographystyle|addbibresource|documentclass|usepackage|RequirePackage)\b",
            text,
        ):
            if token.start() not in parsed:
                raise ValueError(
                    f"J10 unsupported dynamic/unbraced TeX dependency: {token.group(0)}"
                )
        for match in matches:
            command, arguments = match.groups()
            for raw in arguments.split(","):
                raw = raw.strip()
                if (
                    command == "include"
                    and include_names is not None
                    and raw not in include_names
                ):
                    continue
                if not raw or "\\" in raw or "#" in raw:
                    raise ValueError(
                        "J10 cannot safely resolve a dynamic TeX dependency"
                    )
                package = command in {
                    "documentclass",
                    "usepackage",
                    "RequirePackage",
                    "bibliographystyle",
                }
                suffixes = {
                    "documentclass": (".cls",),
                    "usepackage": (".sty",),
                    "RequirePackage": (".sty",),
                    "bibliographystyle": (".bst",),
                    "input": (".tex",),
                    "include": (".tex",),
                    "bibliography": (".bib",),
                    "addbibresource": (".bib",),
                }.get(command, (".pdf", ".png", ".jpg", ".jpeg", ".eps", ".svg"))
                names = [raw] if Path(raw).suffix else [raw + ext for ext in suffixes]
                candidates = []
                for parent in dict.fromkeys((source_root, path.parent)):
                    for name in names:
                        candidate = bounded_path(
                            workspace, parent / name, must_exist=False
                        )
                        if candidate.is_file() and candidate not in candidates:
                            candidates.append(candidate)
                if (
                    not candidates
                    and package
                    and "/" not in raw
                    and not Path(raw).suffix
                ):
                    continue  # Installed TeX package, not a local dependency.
                if not candidates:
                    raise ValueError(f"J10 unresolved active TeX dependency: {raw}")
                if len(candidates) != 1:
                    raise ValueError(f"J10 ambiguous active TeX dependency: {raw}")
                dependency = bounded_path(workspace, candidates[0])
                content = dependency.read_bytes()
                source_files[dependency] = content
                if dependency.suffix.lower() in {".tex", ".sty", ".cls"}:
                    tex_visit(dependency, content)

    tex_visit(source, verified["source"][1])
    # Preserve ../shared references without copying an entire parent directory.
    # The archive root is the common ancestor of only the reached local files.
    common = Path(os.path.commonpath([str(path.parent) for path in source_files]))
    entries.pop(f"source/{source.name}")
    folded.pop(f"source/{source.name}".casefold())
    for path, content in source_files.items():
        add(
            "source/" + path.relative_to(common).as_posix(),
            path,
            content,
            "source" if path == source else "source-dependency",
        )

    allowed = {}
    main_ids = set()
    for item in final_mappings:
        envelope = item["envelope"]
        main_ids.add(envelope["mapping"]["assets"]["editable_source"]["artifact_id"])
        for auxiliary in envelope["auxiliaries"]:
            if auxiliary["role"] not in {"editable_source", "preview"}:
                continue
            path = bounded_path(run_root, auxiliary["path"])
            bounded_path(workspace, path)
            content = path.read_bytes()
            if (
                hashlib.sha256(content).hexdigest() != auxiliary["sha256"]
                or len(content) != auxiliary["size_bytes"]
            ):
                raise ValueError("J10 registered editable figure bytes changed")
            allowed[path] = (content, auxiliary["artifact_id"])
    if not main_ids.issubset({v[1] for v in allowed.values()}):
        raise ValueError("J10 accepted mapping editable source is not registered")
    pending = [path for path, (_, identity) in allowed.items() if identity in main_ids]
    visited_editors = set()
    while pending:
        path = pending.pop()
        if path in visited_editors:
            continue
        visited_editors.add(path)
        content, identity = allowed[path]
        references = []
        if path.suffix.lower() == ".svg":
            for node in ET.fromstring(content).iter():
                for key, value in node.attrib.items():
                    if key in {
                        "href",
                        "{http://www.w3.org/1999/xlink}href",
                    } and not value.startswith(("#", "data:")):
                        references.append(value)
        elif path.suffix.lower() == ".py":
            tree = ast.parse(content.decode("utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    function = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else ""
                    )
                    if function in {
                        "open",
                        "read_csv",
                        "read_json",
                        "read_excel",
                        "loadtxt",
                        "genfromtxt",
                    }:
                        if (
                            not node.args
                            or not isinstance(node.args[0], ast.Constant)
                            or not isinstance(node.args[0].value, str)
                        ):
                            raise ValueError(
                                "J10 editable source has an unresolved dynamic local file dependency"
                            )
                        # Write-only output paths are not dependencies.
                        if (
                            function == "open"
                            and len(node.args) > 1
                            and isinstance(node.args[1], ast.Constant)
                            and any(v in str(node.args[1].value) for v in "wax")
                        ):
                            continue
                        references.append(node.args[0].value)
        for raw in references:
            dependency = bounded_path(run_root, path.parent / raw)
            if dependency not in allowed:
                raise ValueError(
                    "J10 editable dependency is not an accepted registered auxiliary"
                )
            pending.append(dependency)
        add(
            "editable/" + path.relative_to(run_root).as_posix(),
            path,
            content,
            "editable-figure-source"
            if identity in main_ids
            else "editable-figure-dependency",
        )
    return entries


def verify_inventory_bytes(workspace: Path, entries: dict) -> None:
    for path, encoded, role in entries.values():
        if role == "local-readme":
            continue
        if bounded_path(workspace, path).read_bytes() != encoded:
            raise ValueError("J10 package source changed during preparation")
