"""Deterministic, read-only material profiling for the Product Web host.

The academic worker is expected to interpret the science, but it must not be
the only component that notices an already populated manuscript, its figures,
or its bibliography.  This module derives a deliberately small structural
profile from the immutable ProductRunner material ledger.  It does not infer
domain claims or target rules.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from pathlib import Path, PurePosixPath
from typing import Any


PROFILE_CONTRACT = "paperspine5.host-material-profile"
PROFILE_SCHEMA_VERSION = "1.0"


def _canonical_sha256(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()


def _load_pointer(run_root: Path, pointer: Any) -> dict[str, Any]:
    if not isinstance(pointer, dict):
        raise ValueError("material profile requires a material inventory pointer")
    raw_path = pointer.get("path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("material inventory pointer path is missing")
    candidate = (run_root / raw_path).resolve()
    try:
        candidate.relative_to(run_root)
    except ValueError as exc:
        raise ValueError("material inventory pointer escapes the run root") from exc
    if not candidate.is_file():
        raise ValueError("material inventory pointer target does not exist")
    encoded = candidate.read_bytes()
    if (
        pointer.get("sha256") != hashlib.sha256(encoded).hexdigest()
        or pointer.get("size_bytes") != len(encoded)
    ):
        raise ValueError("material inventory pointer bytes changed")
    try:
        value = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("material inventory is not UTF-8 JSON") from exc
    if not isinstance(value, dict):
        raise ValueError("material inventory must contain an object")
    return value


def _read_ledger_object(
    run_root: Path, entry: dict[str, Any], *, text: bool = False
) -> bytes | str:
    raw_path = entry.get("object_path")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ValueError("material ledger entry has no immutable object path")
    candidate = (run_root / raw_path).resolve()
    try:
        candidate.relative_to(run_root)
    except ValueError as exc:
        raise ValueError("material object escapes the run root") from exc
    if not candidate.is_file():
        raise ValueError(f"material object does not exist: {entry.get('relative_path')}")
    encoded = candidate.read_bytes()
    if (
        entry.get("sha256") != hashlib.sha256(encoded).hexdigest()
        or entry.get("size_bytes") != len(encoded)
    ):
        raise ValueError(f"material object bytes changed: {entry.get('relative_path')}")
    if not text:
        return encoded
    try:
        return encoded.decode("utf-8")
    except UnicodeDecodeError:
        try:
            return encoded.decode("utf-8-sig")
        except UnicodeDecodeError as exc:
            raise ValueError(
                f"text material is not UTF-8: {entry.get('relative_path')}"
            ) from exc


def _without_tex_comments(text: str) -> str:
    return re.sub(r"(?m)(?<!\\)%.*$", "", text)


def _first_tex_value(text: str, command: str) -> str | None:
    match = re.search(
        rf"\\{command}(?:\[[^\]]*\])?\s*\{{([^{{}}]+)\}}",
        text,
        re.IGNORECASE,
    )
    return match.group(1).strip() if match else None


def _tex_values(text: str, command: str) -> list[str]:
    return [
        match.group(1).strip()
        for match in re.finditer(
            rf"\\{command}(?:\[[^\]]*\])?\s*\{{([^{{}}]+)\}}",
            text,
            re.IGNORECASE,
        )
        if match.group(1).strip()
    ]


def _section_names(text: str) -> list[str]:
    return [
        re.sub(r"\s+", " ", match.group(1)).strip()
        for match in re.finditer(
            r"\\(?:section|section\*|subsection|subsection\*)\s*\{([^{}]+)\}",
            text,
            re.IGNORECASE,
        )
    ]


def _bibtex_entry_inventory(text: str) -> dict[str, Any]:
    """Count reader-visible BibTeX records by unique citation key.

    BibTeX processors and Pandoc identify entries by citation key, so repeated
    definitions of the same key do not create additional rendered references.
    Keep the raw count and duplicate-key evidence for auditability while using
    the unique-key count for downstream surface-completeness gates.
    """

    keys = [
        match.group(1).strip()
        for match in re.finditer(
            r"(?mi)^\s*@(?!comment\b|string\b|preamble\b)[A-Za-z]+\s*[({]\s*([^,\s{}()]+)\s*,",
            text,
        )
        if match.group(1).strip()
    ]
    occurrences: dict[str, int] = {}
    for key in keys:
        occurrences[key] = occurrences.get(key, 0) + 1
    return {
        "entry_count": len(occurrences),
        "raw_entry_count": len(keys),
        "duplicate_keys": [
            {"key": key, "occurrence_count": count}
            for key, count in sorted(occurrences.items())
            if count > 1
        ],
    }


def _resolve_dependency(
    *,
    owner_path: str,
    token: str,
    entries_by_path: dict[str, dict[str, Any]],
    suffixes: tuple[str, ...],
) -> dict[str, Any] | None:
    cleaned = token.strip().replace("\\", "/")
    if not cleaned or "\\" in token:
        return None
    owner_parent = PurePosixPath(owner_path).parent
    raw = owner_parent / cleaned
    candidates = [raw]
    if not raw.suffix:
        candidates.extend(PurePosixPath(f"{raw}{suffix}") for suffix in suffixes)
    for candidate in candidates:
        normalized = candidate.as_posix()
        while normalized.startswith("./"):
            normalized = normalized[2:]
        entry = entries_by_path.get(normalized)
        if entry is not None:
            return entry
    root_candidates = [PurePosixPath(cleaned)]
    if not PurePosixPath(cleaned).suffix:
        root_candidates.extend(
            PurePosixPath(f"{cleaned}{suffix}") for suffix in suffixes
        )
    for candidate in root_candidates:
        entry = entries_by_path.get(candidate.as_posix())
        if entry is not None:
            return entry
    suffix_matches = [
        entry
        for relative_path, entry in entries_by_path.items()
        if any(
            relative_path == candidate.as_posix()
            or relative_path.endswith(f"/{candidate.as_posix()}")
            for candidate in root_candidates
        )
    ]
    if len(suffix_matches) == 1:
        return suffix_matches[0]
    return None


def _placeholder_categories(text: str) -> list[str]:
    patterns = {
        "author_identity": (
            r"(?i)\\author(?:\[[^\]]*\])?\s*\{\s*(?:author|first author|name|xxx|tbd)",
            r"(?i)\\affil\w*\s*\{[^{}]*(?:affiliation|institution|xxx|tbd)",
        ),
        "funding": (
            r"(?i)funding[^\n]{0,160}(?:grant number|xxx|tbd|placeholder|funder name)",
        ),
        "data_or_code_availability": (
            r"(?i)(?:data|code|weights)[^\n]{0,180}(?:repository|accession|url)[^\n]{0,80}(?:xxx|tbd|placeholder|insert)",
            r"(?i)https?://(?:example\.com|github\.com/[<{\[])",
            r"(?i)(?:availability|implementation)[^\n]{0,180}\[(?:url|repository)[^\]]*(?:add|insert|tbd)",
        ),
        "conflict_or_declaration": (
            r"(?i)(?:conflict|competing interest)[^\n]{0,120}(?:xxx|tbd|placeholder|insert)",
        ),
    }
    return sorted(
        category
        for category, expressions in patterns.items()
        if any(re.search(expression, text) for expression in expressions)
    )


def _tex_profile(
    entry: dict[str, Any],
    text: str,
    entries_by_path: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    visible = _without_tex_comments(text)
    relative_path = str(entry["relative_path"])
    sections = _section_names(visible)
    lowered_sections = " | ".join(sections).lower()
    title = _first_tex_value(visible, "title")
    document_class = _first_tex_value(visible, "documentclass")
    figure_tokens = _tex_values(visible, "includegraphics")
    bibliography_tokens = []
    for command in ("bibliography", "addbibresource"):
        bibliography_tokens.extend(_tex_values(visible, command))
    input_tokens = []
    for command in ("input", "include"):
        input_tokens.extend(_tex_values(visible, command))

    def dependencies(tokens: list[str], suffixes: tuple[str, ...]) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        seen: set[str] = set()
        for token in tokens:
            for item in token.split(","):
                dependency = _resolve_dependency(
                    owner_path=relative_path,
                    token=item,
                    entries_by_path=entries_by_path,
                    suffixes=suffixes,
                )
                source_id = dependency.get("source_id") if dependency else None
                key = str(source_id or item)
                if key in seen:
                    continue
                seen.add(key)
                result.append(
                    {
                        "token": item.strip(),
                        "source_id": source_id,
                        "relative_path": dependency.get("relative_path")
                        if dependency
                        else None,
                        "sha256": dependency.get("sha256") if dependency else None,
                        "resolved": dependency is not None,
                    }
                )
        return result

    figure_dependencies = dependencies(
        figure_tokens, (".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps")
    )
    bibliography_dependencies = dependencies(bibliography_tokens, (".bib",))
    input_dependencies = dependencies(input_tokens, (".tex",))
    path_lower = relative_path.lower()
    is_supplement = "supplement" in path_lower or "supporting" in path_lower
    has_abstract = bool(
        re.search(r"\\begin\s*\{abstract\}", visible, re.IGNORECASE)
        or re.search(r"\\abstract\s*\{", visible, re.IGNORECASE)
    )
    has_methods = bool(re.search(r"\bmethod", lowered_sections))
    has_results = bool(re.search(r"\bresults?\b|\bfindings?\b", lowered_sections))
    has_introduction = bool(re.search(r"\bintroduction\b|\bbackground\b", lowered_sections))
    score = sum(
        (
            2 if document_class else 0,
            2 if title else 0,
            2 if has_abstract else 0,
            1 if has_introduction else 0,
            2 if has_methods else 0,
            2 if has_results else 0,
            1 if figure_dependencies else 0,
            1 if bibliography_dependencies else 0,
        )
    )
    role = "tex_support"
    if is_supplement:
        role = "supplementary_manuscript_candidate"
    elif score >= 8:
        role = "primary_manuscript_candidate"
    elif document_class and title:
        role = "manuscript_fragment_candidate"
    return {
        "source_id": entry["source_id"],
        "relative_path": relative_path,
        "sha256": entry["sha256"],
        "size_bytes": entry["size_bytes"],
        "semantic_role": role,
        "candidate_score": score,
        "title": title,
        "document_class": document_class,
        "sections": sections,
        "has_abstract": has_abstract,
        "has_methods": has_methods,
        "has_results": has_results,
        "figure_dependencies": figure_dependencies,
        "bibliography_dependencies": bibliography_dependencies,
        "input_dependencies": input_dependencies,
        "placeholder_categories": _placeholder_categories(visible),
        "noncomment_character_count": len(visible.strip()),
        "noncomment_word_count": len(re.findall(r"\b[\w'-]+\b", visible)),
    }


def build_material_profile(
    task: dict[str, Any], snapshot: dict[str, Any]
) -> dict[str, Any]:
    """Build a hash-bound structural profile from current immutable materials."""

    run_root = Path(task["run_root"]).resolve()
    ledger = _load_pointer(run_root, snapshot.get("material_inventory"))
    raw_entries = ledger.get("entries")
    if not isinstance(raw_entries, list):
        raise ValueError("material inventory entries must be an array")
    entries = [copy.deepcopy(item) for item in raw_entries if isinstance(item, dict)]
    entries_by_path = {
        str(item.get("relative_path")): item
        for item in entries
        if isinstance(item.get("relative_path"), str)
    }
    tex_documents: list[dict[str, Any]] = []
    reference_libraries: list[dict[str, Any]] = []
    scientific_figures: list[dict[str, Any]] = []
    other_materials: list[dict[str, Any]] = []
    for entry in entries:
        relative_path = str(entry.get("relative_path") or "")
        suffix = Path(relative_path).suffix.lower()
        if suffix == ".tex":
            text = _read_ledger_object(run_root, entry, text=True)
            assert isinstance(text, str)
            tex_documents.append(_tex_profile(entry, text, entries_by_path))
        elif suffix == ".bib":
            text = _read_ledger_object(run_root, entry, text=True)
            assert isinstance(text, str)
            bibliography_inventory = _bibtex_entry_inventory(text)
            reference_libraries.append(
                {
                    "source_id": entry.get("source_id"),
                    "relative_path": relative_path,
                    "sha256": entry.get("sha256"),
                    "size_bytes": entry.get("size_bytes"),
                    "semantic_role": "reference_library",
                    **bibliography_inventory,
                }
            )
        elif suffix in {".pdf", ".png", ".jpg", ".jpeg", ".svg", ".eps"} and re.search(
            r"(?i)(?:^|[/\\])fig(?:ure)?[_ -]?\d+[a-z]?(?:\.[^.]+)?$",
            relative_path,
        ):
            _read_ledger_object(run_root, entry)
            scientific_figures.append(
                {
                    "source_id": entry.get("source_id"),
                    "relative_path": relative_path,
                    "sha256": entry.get("sha256"),
                    "size_bytes": entry.get("size_bytes"),
                    "semantic_role": "scientific_figure",
                }
            )
        else:
            other_materials.append(
                {
                    "source_id": entry.get("source_id"),
                    "relative_path": relative_path,
                    "sha256": entry.get("sha256"),
                    "size_bytes": entry.get("size_bytes"),
                    "semantic_role": "unclassified_support",
                }
            )

    primary = sorted(
        (
            item
            for item in tex_documents
            if item["semantic_role"] == "primary_manuscript_candidate"
        ),
        key=lambda item: (-item["candidate_score"], -item["size_bytes"], item["relative_path"]),
    )
    supplementary = sorted(
        (
            item
            for item in tex_documents
            if item["semantic_role"] == "supplementary_manuscript_candidate"
        ),
        key=lambda item: item["relative_path"],
    )

    main_figure_ids = [
        dependency["source_id"]
        for item in primary[:1]
        for dependency in item["figure_dependencies"]
        if dependency.get("source_id")
    ]
    supplementary_figure_ids = [
        dependency["source_id"]
        for item in supplementary
        for dependency in item["figure_dependencies"]
        if dependency.get("source_id")
    ]
    profile = {
        "contract": PROFILE_CONTRACT,
        "schema_version": PROFILE_SCHEMA_VERSION,
        "material_snapshot_sha256": ledger.get("snapshot_sha256"),
        "source_count": len(entries),
        "primary_manuscript_candidates": primary,
        "supplementary_manuscript_candidates": supplementary,
        "other_tex_documents": [
            item
            for item in tex_documents
            if item not in primary and item not in supplementary
        ],
        "reference_libraries": sorted(
            reference_libraries, key=lambda item: item["relative_path"]
        ),
        "scientific_figures": sorted(
            scientific_figures, key=lambda item: item["relative_path"]
        ),
        "main_manuscript_figure_source_ids": list(dict.fromkeys(main_figure_ids)),
        "supplementary_figure_source_ids": list(
            dict.fromkeys(supplementary_figure_ids)
        ),
        "other_materials": sorted(other_materials, key=lambda item: item["relative_path"]),
        "fail_closed": True,
        "external_action_authorized": False,
    }
    profile["profile_sha256"] = _canonical_sha256(profile)
    return profile


def load_material_bytes(
    task: dict[str, Any], snapshot: dict[str, Any], source_id: str
) -> bytes:
    """Return one current ledger object after path, size, and hash validation."""

    run_root = Path(task["run_root"]).resolve()
    ledger = _load_pointer(run_root, snapshot.get("material_inventory"))
    entry = next(
        (
            item
            for item in ledger.get("entries", [])
            if isinstance(item, dict) and item.get("source_id") == source_id
        ),
        None,
    )
    if entry is None:
        raise ValueError(f"material source is absent from current ledger: {source_id}")
    encoded = _read_ledger_object(run_root, entry)
    assert isinstance(encoded, bytes)
    return encoded
