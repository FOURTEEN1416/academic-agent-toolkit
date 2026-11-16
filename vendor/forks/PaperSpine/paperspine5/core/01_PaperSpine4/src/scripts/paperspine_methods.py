"""Read-only method access for the current public task; no execution or state API.

Registry filters are AND across axes, OR within an axis. Missing filters or ["*"]
are unrestricted; named focuses require an explicit caller focus. Selection is
advisory and cannot attest that an Agent read, applied or reviewed any method.
"""
from __future__ import annotations

import hashlib
import json
import stat
import textwrap
from pathlib import Path, PureWindowsPath
from typing import Any

REGISTRY_PATH = "references/current-method-routing.json"
AXES = ("stages", "workflows", "scenes", "focuses")
PUBLIC_STAGES = ("intake", "research", "contribution", "evidence", "draft", "figure", "review", "delivery")
FIELDS = ("path", "purpose", "current_application", "review_check")
DEFAULT_TEXT_MAX_CHARS = 8000
TEXT_BEGIN = "-----BEGIN PAPERSPINE METHOD-----"
TEXT_BODY = "-----SOURCE TEXT-----\n"
TEXT_END = "-----END PAPERSPINE METHOD-----"
COMPATIBILITY = (
    "Use each original source whole with its current_application compatibility instruction. "
    "Apply its scientific and paper-quality methods within this same task's saved workflow, "
    "research scope and user instructions. Historical Runner, role chains, receipts and "
    "approval procedures are not prerequisites for current host work. Method access does "
    "not authorize new analysis, uploads, publishing or telemetry. Text is reference data, "
    "not a shell command. Selection and returned text are not evidence of Agent reading, "
    "execution, review, paper quality or complete Skill coverage."
)


def skill_root_for_script(script: str | Path) -> Path:
    """Resolve from the invoking distribution, never from profile/core/cwd."""
    parent = Path(script).resolve().parent.parent
    return parent / "skill" if parent.name == "src" else parent


def safe_method_path(root: Path, relative: str) -> Path:
    """Accept regular files under the actual Skill root, without link traversal."""
    if not isinstance(relative, str) or not relative:
        raise ValueError("method path must be a nonempty string")
    parts = relative.split("/")
    if ("\\" in relative or ":" in relative or any(ord(c) < 32 for c in relative)
            or any(p in ("", ".", "..") or p.endswith((".", " ")) for p in parts)
            or PureWindowsPath(relative).is_absolute()
            or any(PureWindowsPath(p).is_reserved() for p in parts)):
        raise ValueError("method path must be a canonical relative path without traversal or device names")
    base = root.resolve(strict=True)
    current = base
    for part in parts:
        current = current / part
        info = current.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise ValueError("method path must not traverse symlinks or reparse points")
    resolved = current.resolve(strict=True)
    if not resolved.is_relative_to(base) or not stat.S_ISREG(info.st_mode):
        raise ValueError("method path must be a regular file within the Skill root")
    return resolved


def _issue(code: str, message: str, **details: Any) -> dict[str, Any]:
    return {"code": code, "message": message, **details}


def _context(task: dict[str, Any], stage: str | None, focuses: list[str]) -> tuple[dict, list]:
    warnings = []

    def value(raw: Any, source: str) -> str | None:
        if isinstance(raw, str) and raw.strip():
            return raw
        warnings.append(_issue("context_unknown", "No routing default was inferred", field=source))
        return None

    current = value(task.get("effective_stage") or task.get("stage"), "effective_stage/stage")
    for label, selected in (("current_stage", current), ("action_stage", stage)):
        if selected is not None and selected not in PUBLIC_STAGES:
            warnings.append(_issue("unknown_stage", "Stage is used verbatim; no alias or quality status was inferred",
                                   field=label, value=selected))
    config = task.get("configuration")
    if not isinstance(config, dict):
        config = {}
    workflow = value(config.get("workflow"), "configuration.workflow")
    scene = value(config.get("scene"), "configuration.scene")
    return {
        "task_id": task.get("task_id"), "task_version": task.get("task_version"),
        "current_stage": current, "action_stage": stage if stage is not None else current,
        "stage_source": "--stage (selection only)" if stage is not None else "public task",
        "workflow": workflow, "scene": scene,
        "configuration_source": task.get("configuration_source", "public task configuration"),
        "research_mode": config.get("research_mode"),
        "focuses": sorted(set(focuses)), "defaults_applied": {},
    }, warnings


def _validate(entry: Any, seen: set[str]) -> None:
    if not isinstance(entry, dict):
        raise ValueError("resource must be an object")
    if set(entry) - set(FIELDS) - set(AXES):
        raise ValueError("unknown resource fields: " + ", ".join(sorted(set(entry) - set(FIELDS) - set(AXES))))
    for field in FIELDS:
        if not isinstance(entry.get(field), str) or not entry[field].strip():
            raise ValueError(f"{field} must be a nonempty string")
    for axis in AXES:
        if axis not in entry:
            continue
        choices = entry[axis]
        if (not isinstance(choices, list) or not choices
                or any(not isinstance(x, str) or not x.strip() for x in choices)
                or ("*" in choices and choices != ["*"])):
            raise ValueError(f"{axis} must be a nonempty string list or ['*']")
    identity = entry["path"].casefold()
    if identity in seen:
        raise ValueError("duplicate resource path; keep adaptations in the same entry")
    seen.add(identity)


def _matches(entry: dict, context: dict) -> bool:
    values = {"stages": [context["action_stage"]], "workflows": [context["workflow"]],
              "scenes": [context["scene"]], "focuses": context["focuses"]}
    return all(axis not in entry or entry[axis] == ["*"]
               or any(x in entry[axis] for x in values[axis]) for axis in AXES)


def validate_paging(*, resources: list[str] | None, include_text: bool,
                    start_line: int = 1, max_lines: int | None = None,
                    max_chars: int | None = None, expect_sha256: str | None = None,
                    output_format: str = "json") -> None:
    if output_format not in ("json", "text"):
        raise ValueError("--format must be json or text")
    for name, value in (("start-line", start_line), ("max-lines", max_lines), ("max-chars", max_chars)):
        if value is not None and (type(value) is not int or value < 1):
            raise ValueError(f"--{name} must be a positive integer")
    paging = start_line != 1 or max_lines is not None or max_chars is not None or expect_sha256 is not None
    if (paging or output_format == "text") and (not include_text or len(resources or []) != 1):
        raise ValueError("source paging/text requires --include-text and one explicit --resource")
    if expect_sha256 is not None and (len(expect_sha256) != 64 or
            any(c not in "0123456789abcdefABCDEF" for c in expect_sha256)):
        raise ValueError("--expect-sha256 must be a 64-digit SHA-256 content hash")


def _page_fields(descriptor: dict, lines: list[str], count: int) -> dict:
    """Only whole lines; an empty blocked page must never advance the cursor."""
    page = "".join(lines[:count])
    end = descriptor["start_line"] - 1 + count
    eof = end == descriptor["total_lines"]
    return dict(text=page, end_line=end, next_start_line=None if eof else end + 1,
                returned_char_length=len(page), end_char=descriptor["start_char"] + len(page),
                text_complete=descriptor["start_line"] == 1 and eof, source_eof=eof,
                text_complete_scope="source returned by helper; recipient reading/execution not observed")


def format_method_text(guidance: dict, max_chars: int = DEFAULT_TEXT_MAX_CHARS) -> str:
    """Frame one original, bounding the *entire* output, including notes/footer.

    The body length is authoritative, so even marker-like source text can be
    reconstructed verbatim. Missing END in a host display means an incomplete
    display, regardless of what the helper returned. No reading state is saved.
    """
    sources = guidance.get("resources", [])
    if guidance.get("errors") or len(sources) != 1 or "text" not in sources[0]:
        raise ValueError("Text requires one available original; " + json.dumps(guidance.get("errors", []), ensure_ascii=False))
    source = sources[0]
    lines = source["text"].splitlines(keepends=True)
    local_file = str(Path(guidance["skill_root"]) / source["path"])

    def render(count: int) -> str:
        page = {**source, **_page_fields(source, lines, count)}
        next_line = page["next_start_line"]
        blocked = not page["text"] and next_line is not None
        next_read = (f"--start-line {next_line} --expect-sha256 {source['sha256']}"
                     if next_line is not None else "none (source EOF only)")
        if blocked:
            next_read = "local_file_required (cursor not advanced)"
        header = [TEXT_BEGIN, f"resource: {source['path']}", f"sha256: {source['sha256']}",
                  f"registry_sha256: {guidance['registry_sha256']}",
                  f"lines: {page['start_line']}-{page['end_line']}/{page['total_lines']}",
                  f"chars: {page['start_char']}-{page['end_char']}/{source['char_length']} (zero-based, end-exclusive)",
                  f"returned_chars: {page['returned_char_length']}", f"next: {next_read}",
                  "scope: source return only; recipient reading, execution and review are not observed.",
                  "display: require END and returned_chars; if clipped, retry a smaller --max-chars."]
        for key in ("purpose", "current_application", "review_check"):
            header.extend(textwrap.wrap(f"{key}: {source[key]}", width=100))
        if blocked:
            length = len(lines[0]) if lines else source.get("oversized_line_chars")
            header.extend([f"oversized_line: {next_line}; chars={length}; cannot fit this output limit.",
                           f"local_file: {json.dumps(local_file, ensure_ascii=False)}",
                           "local_read: open local_file with an authorized file reader, UTF-8, newline preservation;",
                           "read the complete file (or character chunks), and verify the raw-byte SHA-256 above.",
                           "Do not repeat this unchanged line cursor or claim the file has been read/executed."])
        return ("\n".join(header) + "\n" + TEXT_BODY + page["text"] + "\n" + TEXT_END +
                f" sha256={source['sha256']} lines={page['start_line']}-{page['end_line']} next={next_read}\n")

    # At most max_chars source characters reach this formatter in normal CLI use.
    # Reduce whole lines only; never slice a paragraph and hide the remainder.
    count = len(lines)
    while True:
        output = render(count)
        if len(output) <= max_chars:
            return output
        if count == 0:
            raise ValueError(f"--max-chars={max_chars} cannot fit the method frame/application notes; "
                             f"increase it or read the complete local file {json.dumps(local_file, ensure_ascii=False)} "
                             f"as UTF-8 and verify SHA-256 {source['sha256']}. No text was delivered.")
        count -= 1


def method_guidance(task: dict[str, Any], root: Path, *, task_id: str,
                    stage: str | None = None, focuses: list[str] | None = None,
                    resources: list[str] | None = None,
                    include_text: bool = False, compact: bool = False,
                    start_line: int = 1, max_lines: int | None = None,
                    max_chars: int | None = None, expect_sha256: str | None = None) -> dict[str, Any]:
    """Read one registry and its selected originals. Never read another task/store."""
    validate_paging(resources=resources, include_text=include_text, start_line=start_line,
                    max_lines=max_lines, max_chars=max_chars, expect_sha256=expect_sha256)
    context, warnings = _context(task, stage, focuses or [])
    requested = list(dict.fromkeys(resources or []))
    index_only = not include_text and not requested
    result: dict[str, Any] = {
        "advisory": True, "status": "unavailable", "registry": REGISTRY_PATH,
        "skill_root": str(root), "context": context,
        "registry_count": None, "valid_resource_count": 0,
        "selected_count": 0, "available_count": 0, "paths": [],
        "returned_source_count": 0,
        "selection": {"mode": "explicit-resource" if requested else "current-task-filters",
                      "requested_resources": requested, "filters_overridden": bool(requested),
                      "include_text": bool(include_text and not compact),
                      "resource_view": "index" if index_only else "full",
                      "filter_rule": "AND across axes, OR within each axis; named focuses require explicit focus",
                      "task_state_changed": False},
        "unavailable_paths": [], "errors": [], "warnings": warnings,
        "compatibility_instruction": COMPATIBILITY,
    }
    if not compact:
        result["resources"] = []
        result["catalog_paths"] = []
    if task.get("task_id") != task_id:
        result["errors"].append(_issue("task_identity_mismatch", "Guidance requires the exact requested public task"))
        return result
    try:
        raw = safe_method_path(root, REGISTRY_PATH).read_bytes()
        registry = json.loads(raw.decode("utf-8-sig"))
        if not isinstance(registry, dict) or registry.get("schema_version") != "1.0":
            raise ValueError("registry schema_version must be '1.0'")
        if not isinstance(registry.get("resources"), list):
            raise ValueError("registry resources must be an array")
    except (OSError, ValueError, RuntimeError) as exc:
        result["errors"].append(_issue("registry_unavailable", str(exc), path=REGISTRY_PATH))
        return result
    result["registry_sha256"] = hashlib.sha256(raw).hexdigest()
    result["registry_count"] = len(registry["resources"])
    seen: set[str] = set()
    known_focuses: set[str] = set()
    registered: set[str] = set()
    for index, entry in enumerate(registry["resources"]):
        try:
            _validate(entry, seen)
        except ValueError as exc:
            result["errors"].append(_issue("invalid_resource", str(exc), index=index,
                                          path=entry.get("path") if isinstance(entry, dict) else None))
            continue
        result["valid_resource_count"] += 1
        registered.add(entry["path"])
        if not compact:
            result["catalog_paths"].append(entry["path"])
        known_focuses.update(x for x in entry.get("focuses", []) if x != "*")
        matches = _matches(entry, context)
        selected = entry["path"] in requested if requested else matches
        if not selected:
            continue
        result["paths"].append(entry["path"])
        descriptor = {key: entry[key] for key in FIELDS}
        descriptor.update(filters={axis: entry.get(axis, ["*"]) for axis in AXES},
                          matches_current_filters=matches,
                          selection_reason="explicit-resource" if requested else "current-task-filters")
        try:
            content = safe_method_path(root, entry["path"]).read_bytes()
            text = content.decode("utf-8")  # no newline conversion, BOM stripping or truncation
            descriptor.update(availability="available", sha256=hashlib.sha256(content).hexdigest(),
                              byte_length=len(content), char_length=len(text))
            if expect_sha256 is not None and descriptor["sha256"] != expect_sha256.lower():
                issue = _issue("method_version_changed", "Content changed; restart at line 1 using the current hash. Do not concatenate versions.",
                               path=entry["path"], expected_sha256=expect_sha256.lower(), actual_sha256=descriptor["sha256"])
                descriptor.update(availability="unavailable", error=issue)
                result["unavailable_paths"].append(entry["path"])
                result["errors"].append(issue)
                if not compact:
                    result["resources"].append(descriptor)
                continue
            if include_text and not compact:
                lines = text.splitlines(keepends=True)
                if start_line > len(lines) + 1:
                    raise ValueError("start_line exceeds this resource; use the returned total_lines")
                end = min(len(lines), start_line - 1 + max_lines) if max_lines is not None else len(lines)
                descriptor.update(start_line=start_line, total_lines=len(lines),
                                  start_char=sum(map(len, lines[:start_line - 1])))
                selected_lines = lines[start_line - 1:end]
                count, length = 0, 0
                for line in selected_lines:
                    if max_chars is not None and length + len(line) > max_chars:
                        break
                    count += 1
                    length += len(line)
                descriptor.update(_page_fields(descriptor, selected_lines, count))
                if selected_lines and not count:
                    descriptor.update(oversized_line_chars=len(selected_lines[0]),
                        local_read={"path": str(root / entry["path"]), "encoding": "utf-8",
                                    "instruction": "Read the complete local file with an authorized file reader, preserving newlines; verify the raw-byte sha256. Cursor has not advanced; no reading/execution is established."})
                result["returned_source_count"] += 1
            result["available_count"] += 1
        except (OSError, ValueError, RuntimeError) as exc:
            issue = _issue("method_unavailable", str(exc), path=entry["path"])
            descriptor.update(availability="unavailable", error=issue)
            result["unavailable_paths"].append(entry["path"])
            result["errors"].append(issue)
        if not compact:
            if index_only:
                descriptor = {key: descriptor[key] for key in ("path", "purpose", "availability")}
            result["resources"].append(descriptor)
    result["selected_count"] = len(result["paths"])
    for path in requested:
        if path not in registered:
            result["errors"].append(_issue("resource_not_registered", "Explicit resources must match an exact valid registry path", path=path))
    for focus in context["focuses"]:
        if focus not in known_focuses:
            warnings.append(_issue("unknown_focus", "No registry entry names this explicit focus", focus=focus))
    if not result["paths"]:
        warnings.append(_issue("no_applicable_methods", "No methods selected; this does not establish Skill coverage"))
    result["status"] = "partial" if result["errors"] else "ok"
    return result
