#!/usr/bin/env python3
"""Validate and assemble PaperSpine publication-cycle artifacts.

The script deliberately does not research journals, write scientific prose, or
submit to an external portal.  The PaperSpine Agent performs those judgment
tasks; this module makes the resulting target profile, delivery bundle,
rebuttal round, and journal-transfer delta reproducible and fail-closed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import zipfile
from dataclasses import asdict, dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
INTERFACE_VERSION = "1.0"
INTERFACE_REQUEST_CONTRACT = "paperspine.publication-cycle.invoke-request"
INTERFACE_RESULT_CONTRACT = "paperspine.publication-cycle.result"
FIVE_PART_KEYS = (
    "front_matter",
    "introduction",
    "methods_or_approach",
    "results_or_analysis",
    "discussion_and_conclusion",
)
SOURCE_AUTHORITIES = {"official", "published_corpus", "user_supplied", "inferred"}
PACKAGE_DISPOSITIONS = {"required", "conditional", "optional"}
CONDITION_STATES = {"applies", "not_applicable", "unresolved"}
REUSE_POLICIES = {"reuse_if_identical", "revalidate", "regenerate", "author_supply"}
PACKAGE_ITEM_STATES = {"ready", "needs_author", "not_applicable"}
FIT_VERDICTS = {"submit", "reshape", "redirect"}
DECISION_TYPES = {"minor_revision", "major_revision", "reject_and_resubmit"}
ISSUE_TYPES = {"major", "minor", "clarification", "format"}
RESPONSE_STRATEGIES = {"accept", "clarify", "defend", "experiment", "partial", "cannot_complete"}
REVALIDATION_DIMENSIONS = {"scientific_content", "visual", "citation", "metadata", "artifact"}
REVALIDATION_STATES = {"passed", "not_affected", "pending"}
REQUIRED_CONFIRMATIONS = {
    "target_selected",
    "author_identity_and_order",
    "declarations_approved",
    "exclusive_submission",
}
PLACEHOLDER_RE = re.compile(
    r"\[(?:(?i:NEEDS USER DATA|AUTHOR CONFIRMATION REQUIRED)|[A-Z][A-Z0-9 /._-]{2,})[^\]]*\]"
    r"|(?i:\bTODO\b)|\[\[|\]\]",
)
COMMENT_ID_RE = re.compile(r"^(?:E|R\d+)\.C\d+(?:\.\d+)?$")
RULE_COVERAGE_AREAS = (
    "title",
    "abstract",
    "body",
    "figures",
    "tables",
    "references",
    "attachments",
    "required_sections",
    "required_materials",
)
RULE_COVERAGE_STATES = {"known", "not_applicable", "pending"}
RULE_VERIFICATIONS = {"machine_verifiable", "needs_author_confirmation", "advisory"}
RULE_METRICS = {
    "word_count",
    "character_count",
    "page_count",
    "count",
    "required_sections",
    "required_material",
    "confirmation",
}
RULE_OPERATORS = {"max", "required"}
MANUSCRIPT_SCOPES = {
    "title",
    "abstract",
    "body",
    "full_text",
    "rendered_manuscript",
    "figures",
    "tables",
    "references",
}

PUBLIC_OPERATION_SPECS = {
    "profile_check": {
        "mode": "submission",
        "required_inputs": ["profile"],
        "required_outputs": [],
        "success_outcome": "PROFILE_VALID",
        "success_stage": "target_profile_ready",
    },
    "assemble": {
        "mode": "submission",
        "required_inputs": ["profile", "plan"],
        "required_outputs": ["directory"],
        "success_outcome": "BUNDLE_READY",
        "success_stage": "target_bundle_ready",
    },
    "rebuttal_check": {
        "mode": "revision",
        "required_inputs": ["review_round"],
        "required_outputs": [],
        "success_outcome": "REBUTTAL_VALID",
        "success_stage": "rebuttal_validated",
    },
    "rebuttal_render": {
        "mode": "revision",
        "required_inputs": ["review_round"],
        "required_outputs": ["directory"],
        "success_outcome": "REBUTTAL_READY",
        "success_stage": "rebuttal_materials_ready",
    },
    "transfer_plan": {
        "mode": "transfer",
        "required_inputs": ["origin_profile", "destination_profile", "transfer_request"],
        "required_outputs": ["directory"],
        "success_outcome": "READY_TO_REBUILD",
        "success_stage": "destination_rebuild_ready",
    },
}

PUBLIC_NEXT_ACTIONS = {
    "profile_check": {
        "owner": "paperspine_main_flow",
        "action": "apply_target_format_and_five_part_preferences_then_prepare_package_plan",
    },
    "assemble": {
        "owner": "user",
        "action": "review_bundle_and_separately_authorize_external_submission",
    },
    "rebuttal_check": {
        "owner": "publication_cycle",
        "action": "render_rebuttal_materials",
    },
    "rebuttal_render": {
        "owner": "paperspine_main_flow",
        "action": "assemble_revision_delivery_bundle_then_request_external_resubmission_authorization",
    },
    "transfer_plan": {
        "owner": "paperspine_main_flow",
        "action": "rebuild_destination_format_five_part_narrative_and_full_delivery_package",
    },
}


@dataclass
class AuditResult:
    kind: str
    subject: str
    findings: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return not self.findings

    def payload(self) -> dict[str, Any]:
        return asdict(self) | {"ok": self.ok, "status": "PASS" if self.ok else "BLOCKED"}


def load_json(path: Path) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"JSON file does not exist: {path}"
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, f"Cannot read JSON file {path}: {exc}"
    if not isinstance(data, dict):
        return {}, f"JSON root must be an object: {path}"
    return data, None


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def valid_iso_date(value: object) -> bool:
    try:
        date.fromisoformat(str(value))
    except ValueError:
        return False
    return True


def string_list(value: object) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def dedupe(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def resolve_from(base: Path, value: object) -> Path:
    path = Path(str(value))
    if not path.is_absolute():
        path = base / path
    return path.resolve()


def safe_output_path(root: Path, relative: object) -> Path | None:
    raw = Path(str(relative))
    if raw.is_absolute() or not str(raw).strip() or any(part == ".." for part in raw.parts):
        return None
    resolved = (root / raw).resolve()
    return resolved if is_relative_to(resolved, root.resolve()) else None


def verify_file_receipt(
    record: dict[str, Any],
    *,
    base: Path,
    project_root: Path,
    label: str,
    findings: list[str],
) -> Path | None:
    path_value = record.get("path")
    if not path_value:
        findings.append(f"{label} is missing path.")
        return None
    path = resolve_from(base, path_value)
    if not is_relative_to(path, project_root):
        findings.append(f"{label} escapes project_root: {path}")
        return None
    if not path.is_file():
        findings.append(f"{label} file does not exist: {path}")
        return None
    expected = str(record.get("sha256") or "").lower()
    actual = sha256_file(path)
    if not expected:
        findings.append(f"{label} is missing sha256.")
    elif expected != actual:
        findings.append(f"{label} sha256 mismatch: expected {expected}, actual {actual}.")
    return path


def referenced_source_ids(section: dict[str, Any], label: str, known: set[str], findings: list[str]) -> None:
    source_ids = string_list(section.get("source_ids"))
    if not source_ids:
        findings.append(f"{label} must cite at least one source_id.")
        return
    missing = [source_id for source_id in source_ids if source_id not in known]
    if missing:
        findings.append(f"{label} references unknown source_ids: {missing}")


def validate_compliance_contract(
    data: dict[str, Any],
    *,
    source_ids: set[str],
    official_source_ids: set[str],
    requirement_ids: set[str],
    findings: list[str],
    warnings: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    compliance = data.get("compliance")
    if not isinstance(compliance, dict):
        findings.append("compliance must be an object with coverage and rules.")
        return [], []

    coverage = compliance.get("coverage")
    if not isinstance(coverage, list):
        findings.append("compliance.coverage must be a list.")
        coverage = []
    coverage_map: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(coverage, start=1):
        label = f"compliance.coverage[{index}]"
        if not isinstance(entry, dict):
            findings.append(f"{label} must be an object.")
            continue
        area = str(entry.get("area") or "")
        if area not in RULE_COVERAGE_AREAS:
            findings.append(f"{label}.area must be one of {list(RULE_COVERAGE_AREAS)}.")
            continue
        if area in coverage_map:
            findings.append(f"Duplicate compliance coverage area: {area}")
            continue
        coverage_map[area] = entry
        status = str(entry.get("status") or "")
        if status not in RULE_COVERAGE_STATES:
            findings.append(f"{label}.status must be one of {sorted(RULE_COVERAGE_STATES)}.")
        referenced_source_ids(entry, label, source_ids, findings)
        if not official_source_ids.intersection(string_list(entry.get("source_ids"))):
            findings.append(f"{label} must cite an official source.")
        if not str(entry.get("source_locator") or "").strip():
            findings.append(f"{label}.source_locator is required; do not guess the rule.")
        if status == "pending":
            findings.append(
                f"Compliance coverage {area} is pending and blocks target readiness until the official rule is resolved."
            )
        if status == "not_applicable" and not str(entry.get("note") or "").strip():
            findings.append(f"{label}.note must explain the official not-applicable determination.")
    missing_areas = [area for area in RULE_COVERAGE_AREAS if area not in coverage_map]
    if missing_areas:
        findings.append(f"compliance.coverage is missing required areas: {missing_areas}")

    rules = compliance.get("rules")
    if not isinstance(rules, list):
        findings.append("compliance.rules must be a list.")
        rules = []
    rule_ids: set[str] = set()
    rules_by_area: dict[str, int] = {}
    for index, rule in enumerate(rules, start=1):
        label = f"compliance.rules[{index}]"
        if not isinstance(rule, dict):
            findings.append(f"{label} must be an object.")
            continue
        rule_id = str(rule.get("id") or "").strip()
        if not rule_id:
            findings.append(f"{label}.id is required.")
        elif rule_id in rule_ids:
            findings.append(f"Duplicate compliance rule id: {rule_id}")
        else:
            rule_ids.add(rule_id)
        area = str(rule.get("area") or "")
        if area not in RULE_COVERAGE_AREAS:
            findings.append(f"{label}.area must be one of {list(RULE_COVERAGE_AREAS)}.")
        else:
            rules_by_area[area] = rules_by_area.get(area, 0) + 1
            if str(coverage_map.get(area, {}).get("status")) != "known":
                findings.append(f"{label} requires compliance.coverage[{area}].status=known.")
        verification = str(rule.get("verification") or "")
        if verification not in RULE_VERIFICATIONS:
            findings.append(f"{label}.verification must be one of {sorted(RULE_VERIFICATIONS)}.")
        metric = str(rule.get("metric") or "")
        if metric not in RULE_METRICS:
            findings.append(f"{label}.metric must be one of {sorted(RULE_METRICS)}.")
        operator = str(rule.get("operator") or "")
        if operator not in RULE_OPERATORS:
            findings.append(f"{label}.operator must be one of {sorted(RULE_OPERATORS)}.")
        if not str(rule.get("unit") or "").strip():
            findings.append(f"{label}.unit is required.")
        referenced_source_ids(rule, label, source_ids, findings)
        if verification != "advisory" and not official_source_ids.intersection(string_list(rule.get("source_ids"))):
            findings.append(f"{label} is non-advisory and must cite an official source.")
        if not str(rule.get("source_locator") or "").strip():
            findings.append(f"{label}.source_locator is required.")
        if not str(rule.get("remediation") or "").strip():
            findings.append(f"{label}.remediation is required.")

        if metric in {"word_count", "character_count", "page_count", "count"}:
            if operator != "max":
                findings.append(f"{label} numeric metrics require operator=max.")
            limit = rule.get("limit")
            if not isinstance(limit, (int, float)) or isinstance(limit, bool) or limit < 0:
                findings.append(f"{label}.limit must be a non-negative number.")
            scope = str(rule.get("scope") or "")
            if scope not in MANUSCRIPT_SCOPES | {"attachments"}:
                findings.append(f"{label}.scope is invalid for a numeric metric: {scope}")
            if metric == "count" and scope not in {"figures", "tables", "references", "attachments"}:
                findings.append(
                    f"{label} metric=count is only valid for figures, tables, references, or attachments."
                )
            if metric in {"word_count", "character_count"} and scope not in {
                "title",
                "abstract",
                "body",
                "full_text",
            }:
                findings.append(
                    f"{label} metric={metric} requires title, abstract, body, or full_text scope."
                )
            if metric == "page_count" and scope != "rendered_manuscript":
                findings.append(f"{label} metric=page_count requires scope=rendered_manuscript.")
        elif metric in {"required_sections", "required_material"}:
            if operator != "required":
                findings.append(f"{label} requires operator=required.")
            required_values = string_list(rule.get("limit"))
            if not required_values:
                findings.append(f"{label}.limit must list required values.")
            if metric == "required_material":
                unknown = sorted(set(required_values) - requirement_ids)
                if unknown:
                    findings.append(f"{label} references unknown package requirement ids: {unknown}")
        elif metric == "confirmation":
            if verification != "needs_author_confirmation":
                findings.append(f"{label} confirmation metrics require verification=needs_author_confirmation.")
            if operator != "required":
                findings.append(f"{label} confirmation metrics require operator=required.")
            if not str(rule.get("confirmation_id") or "").strip():
                findings.append(f"{label}.confirmation_id is required.")

    for area, entry in coverage_map.items():
        if str(entry.get("status")) == "known" and rules_by_area.get(area, 0) == 0:
            findings.append(f"Compliance coverage {area} is known but has no structured rule.")
        if str(entry.get("status")) == "not_applicable" and rules_by_area.get(area, 0):
            warnings.append(f"Compliance coverage {area} is not_applicable but rules were supplied and ignored.")
    return coverage, [rule for rule in rules if isinstance(rule, dict)]


def validate_profile(path: Path) -> tuple[AuditResult, dict[str, Any]]:
    result = AuditResult("target_profile", str(path))
    data, error = load_json(path)
    if error:
        result.findings.append(error)
        return result, data

    if str(data.get("schema_version")) != SCHEMA_VERSION:
        result.findings.append(f"schema_version must be {SCHEMA_VERSION}.")

    target = data.get("target")
    if not isinstance(target, dict):
        result.findings.append("target must be an object.")
        target = {}
    for key in ("name", "article_type"):
        if not str(target.get(key) or "").strip():
            result.findings.append(f"target.{key} is required.")
    if not valid_iso_date(target.get("researched_at")):
        result.findings.append("target.researched_at must be an ISO date (YYYY-MM-DD).")

    sources = data.get("sources")
    if not isinstance(sources, list) or not sources:
        result.findings.append("sources must contain at least one evidence source.")
        sources = []
    source_ids: set[str] = set()
    official_source_ids: set[str] = set()
    official_count = 0
    for index, source in enumerate(sources, start=1):
        label = f"sources[{index}]"
        if not isinstance(source, dict):
            result.findings.append(f"{label} must be an object.")
            continue
        source_id = str(source.get("id") or "").strip()
        if not source_id:
            result.findings.append(f"{label}.id is required.")
        elif source_id in source_ids:
            result.findings.append(f"Duplicate source id: {source_id}")
        else:
            source_ids.add(source_id)
        authority = str(source.get("authority") or "").lower()
        if authority not in SOURCE_AUTHORITIES:
            result.findings.append(f"{label}.authority must be one of {sorted(SOURCE_AUTHORITIES)}.")
        if authority == "official":
            official_count += 1
            if source_id:
                official_source_ids.add(source_id)
        url = str(source.get("url") or "")
        if not url.startswith(("https://", "http://")):
            result.findings.append(f"{label}.url must be an HTTP(S) source URL.")
        if not valid_iso_date(source.get("checked_at")):
            result.findings.append(f"{label}.checked_at must be an ISO date.")
    if official_count == 0:
        result.findings.append("At least one official source is required for a target profile.")

    format_contract = data.get("format")
    if not isinstance(format_contract, dict):
        result.findings.append("format must be an object.")
        format_contract = {}
    if not string_list(format_contract.get("manuscript_formats")):
        result.findings.append("format.manuscript_formats must list at least one accepted format.")
    referenced_source_ids(format_contract, "format", source_ids, result.findings)

    preferences = data.get("five_part_preferences")
    if not isinstance(preferences, dict):
        result.findings.append("five_part_preferences must be an object.")
        preferences = {}
    extra_parts = sorted(set(preferences) - set(FIVE_PART_KEYS))
    if extra_parts:
        result.warnings.append(f"Non-canonical five-part preference keys are ignored by transfer diff: {extra_parts}")
    for key in FIVE_PART_KEYS:
        part = preferences.get(key)
        label = f"five_part_preferences.{key}"
        if not isinstance(part, dict):
            result.findings.append(f"{label} must be an object.")
            continue
        if not string_list(part.get("preferred_moves")):
            result.findings.append(f"{label}.preferred_moves must not be empty.")
        if not isinstance(part.get("evidence_expectations"), list):
            result.findings.append(f"{label}.evidence_expectations must be a list.")
        if not isinstance(part.get("avoid"), list):
            result.findings.append(f"{label}.avoid must be a list.")
        referenced_source_ids(part, label, source_ids, result.findings)

    requirements = data.get("package_requirements")
    if not isinstance(requirements, list) or not requirements:
        result.findings.append("package_requirements must contain at least one item.")
        requirements = []
    requirement_ids: set[str] = set()
    for index, requirement in enumerate(requirements, start=1):
        label = f"package_requirements[{index}]"
        if not isinstance(requirement, dict):
            result.findings.append(f"{label} must be an object.")
            continue
        requirement_id = str(requirement.get("id") or "").strip()
        if not requirement_id:
            result.findings.append(f"{label}.id is required.")
        elif requirement_id in requirement_ids:
            result.findings.append(f"Duplicate package requirement id: {requirement_id}")
        else:
            requirement_ids.add(requirement_id)
        disposition = str(requirement.get("disposition") or "")
        if disposition not in PACKAGE_DISPOSITIONS:
            result.findings.append(f"{label}.disposition must be one of {sorted(PACKAGE_DISPOSITIONS)}.")
        condition_state = str(requirement.get("condition_status") or "")
        if condition_state not in CONDITION_STATES:
            result.findings.append(f"{label}.condition_status must be one of {sorted(CONDITION_STATES)}.")
        if disposition == "required" and condition_state != "applies":
            result.findings.append(f"{label} is required and must have condition_status=applies.")
        if disposition == "conditional" and condition_state == "unresolved":
            result.warnings.append(f"{label} remains conditional-unresolved and will block bundle assembly.")
        extensions = string_list(requirement.get("accepted_extensions"))
        if not extensions:
            result.findings.append(f"{label}.accepted_extensions must not be empty.")
        elif any(not extension.startswith(".") for extension in extensions):
            result.findings.append(f"{label}.accepted_extensions values must begin with '.'.")
        reuse_policy = str(requirement.get("reuse_policy") or "")
        if reuse_policy not in REUSE_POLICIES:
            result.findings.append(f"{label}.reuse_policy must be one of {sorted(REUSE_POLICIES)}.")
        referenced_source_ids(requirement, label, source_ids, result.findings)

    coverage, compliance_rules = validate_compliance_contract(
        data,
        source_ids=source_ids,
        official_source_ids=official_source_ids,
        requirement_ids=requirement_ids,
        findings=result.findings,
        warnings=result.warnings,
    )
    legacy_limits = [
        ("format.word_limit", format_contract.get("word_limit"), "body", "word_count", "body"),
        ("format.page_limit", format_contract.get("page_limit"), "body", "page_count", "rendered_manuscript"),
        (
            "format.title.word_limit",
            format_contract.get("title", {}).get("word_limit") if isinstance(format_contract.get("title"), dict) else None,
            "title",
            "word_count",
            "title",
        ),
        (
            "format.abstract.word_limit",
            format_contract.get("abstract", {}).get("word_limit")
            if isinstance(format_contract.get("abstract"), dict)
            else None,
            "abstract",
            "word_count",
            "abstract",
        ),
        (
            "format.figures.max_count",
            format_contract.get("figures", {}).get("max_count")
            if isinstance(format_contract.get("figures"), dict)
            else None,
            "figures",
            "count",
            "figures",
        ),
        (
            "format.tables.max_count",
            format_contract.get("tables", {}).get("max_count")
            if isinstance(format_contract.get("tables"), dict)
            else None,
            "tables",
            "count",
            "tables",
        ),
        (
            "format.references.max_count",
            format_contract.get("references", {}).get("max_count")
            if isinstance(format_contract.get("references"), dict)
            else None,
            "references",
            "count",
            "references",
        ),
        (
            "format.attachments.max_count",
            format_contract.get("attachments", {}).get("max_count")
            if isinstance(format_contract.get("attachments"), dict)
            else None,
            "attachments",
            "count",
            "attachments",
        ),
    ]
    for label, limit, area, metric, scope in legacy_limits:
        if limit is None:
            continue
        matches = [
            rule
            for rule in compliance_rules
            if str(rule.get("area")) == area
            and str(rule.get("metric")) == metric
            and str(rule.get("scope")) == scope
            and rule.get("limit") == limit
            and str(rule.get("operator")) == "max"
        ]
        if not matches:
            result.findings.append(
                f"{label}={limit!r} must be mirrored exactly by a structured compliance rule."
            )

    result.findings = dedupe(result.findings)
    result.warnings = dedupe(result.warnings)
    result.details = {
        "target": target.get("name"),
        "profile_sha256": sha256_file(path),
        "source_count": len(sources),
        "official_source_count": official_count,
        "requirement_count": len(requirements),
        "compliance_coverage_count": len(coverage),
        "compliance_rule_count": len(compliance_rules),
    }
    return result, data


def extract_searchable_text(path: Path) -> str:
    if path.suffix.lower() in {".md", ".txt", ".tex", ".json", ".csv", ".tsv", ".xml"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if path.suffix.lower() == ".docx":
        try:
            with zipfile.ZipFile(path) as archive:
                document = archive.read("word/document.xml").decode("utf-8", errors="ignore")
        except (OSError, KeyError, zipfile.BadZipFile):
            return ""
        return re.sub(r"<[^>]+>", " ", document)
    return ""


def _word_count(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text, flags=re.UNICODE))


def _character_count(text: str) -> int:
    return len(re.sub(r"\s+", "", text))


def _tex_group(text: str, opening_index: int, opening: str = "{", closing: str = "}") -> tuple[str, int] | None:
    r"""Return one balanced TeX group and its exclusive end offset.

    Escaped delimiters (``\{``/``\}``) are content, while a delimiter after an
    escaped backslash (``\\{``) retains its structural meaning.
    """
    if opening_index >= len(text) or text[opening_index] != opening:
        return None
    depth = 0
    index = opening_index
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text) and text[index + 1] in {opening, closing, "\\"}:
            index += 2
            continue
        if char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return text[opening_index + 1 : index], index + 1
        index += 1
    return None


def _tex_macro_arguments(text: str, command: str) -> list[tuple[str, int, int]]:
    """Extract balanced mandatory arguments for a TeX command.

    Each tuple contains ``(argument, command_start, argument_end)``. Optional
    bracket groups and a starred command form are accepted so the helper can
    also parse section headings without single-line regular expressions.
    """
    arguments: list[tuple[str, int, int]] = []
    index = 0
    while index < len(text):
        command_start = text.find("\\", index)
        if command_start < 0:
            break
        preceding_slashes = 0
        cursor = command_start - 1
        while cursor >= 0 and text[cursor] == "\\":
            preceding_slashes += 1
            cursor -= 1
        if preceding_slashes % 2:
            index = command_start + 1
            continue
        name_end = command_start + 1
        while name_end < len(text) and (text[name_end].isalpha() or text[name_end] == "@"):
            name_end += 1
        if text[command_start + 1 : name_end] != command:
            index = max(name_end, command_start + 1)
            continue
        cursor = name_end
        if cursor < len(text) and text[cursor] == "*":
            cursor += 1
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        while cursor < len(text) and text[cursor] == "[":
            optional = _tex_group(text, cursor, "[", "]")
            if optional is None:
                break
            _, cursor = optional
            while cursor < len(text) and text[cursor].isspace():
                cursor += 1
        group = _tex_group(text, cursor)
        if group is None:
            index = max(cursor + 1, command_start + 1)
            continue
        argument, argument_end = group
        arguments.append((argument, command_start, argument_end))
        index = argument_end
    return arguments


def _without_spans(text: str, spans: list[tuple[int, int]]) -> str:
    for start, end in sorted(spans, reverse=True):
        text = text[:start] + " " + text[end:]
    return text


def _tex_abstract_from_section(text: str) -> tuple[str, tuple[int, int] | None]:
    sections = _tex_macro_arguments(text, "section")
    for index, (heading, start, end) in enumerate(sections):
        if _normalized_heading(_tex_plain(heading)) != "abstract":
            continue
        section_end = sections[index + 1][1] if index + 1 < len(sections) else len(text)
        return text[end:section_end], (start, section_end)
    return "", None


def _tex_plain(text: str) -> str:
    text = re.sub(r"(?m)(?<!\\)%.*$", " ", text)
    text = re.sub(r"\$\$.*?\$\$|\$.*?\$", " ", text, flags=re.DOTALL)
    text = re.sub(r"\\begin\{(?:figure\*?|table\*?)\}.*?\\end\{(?:figure\*?|table\*?)\}", " ", text, flags=re.DOTALL)
    for _ in range(4):
        text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?\{([^{}]*)\}", r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^\]]*\])?", " ", text)
    text = re.sub(r"[{}~]", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def _tex_metrics(path: Path, bibliography_paths: list[Path]) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    clean = re.sub(r"(?m)(?<!\\)%.*$", "", raw)
    title_arguments = _tex_macro_arguments(clean, "title")
    abstract_arguments = _tex_macro_arguments(clean, "abstract")
    abstract_match = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", clean, flags=re.DOTALL)
    section_abstract, _ = _tex_abstract_from_section(clean)
    title = _tex_plain(title_arguments[0][0]) if title_arguments else ""
    if abstract_arguments:
        abstract = _tex_plain(abstract_arguments[0][0])
    elif abstract_match:
        abstract = _tex_plain(abstract_match.group(1))
    else:
        abstract = _tex_plain(section_abstract)
    document_match = re.search(r"\\begin\{document\}(.*?)\\end\{document\}", clean, flags=re.DOTALL)
    document = document_match.group(1) if document_match else clean
    document = _without_spans(
        document,
        [(start, end) for _, start, end in _tex_macro_arguments(document, "abstract")],
    )
    document = re.sub(r"\\begin\{abstract\}.*?\\end\{abstract\}", " ", document, flags=re.DOTALL)
    _, document_abstract_section = _tex_abstract_from_section(document)
    if document_abstract_section:
        document = _without_spans(document, [document_abstract_section])
    document = re.sub(r"\\begin\{thebibliography\}.*?\\end\{thebibliography\}", " ", document, flags=re.DOTALL)
    body = _tex_plain(document)
    sections = [
        _tex_plain(item)
        for item, _, _ in _tex_macro_arguments(clean, "section")
    ]
    if abstract:
        sections.append("Abstract")
    reference_count = len(re.findall(r"\\bibitem(?:\[[^\]]*\])?\{", clean))
    for bib_path in bibliography_paths:
        if bib_path.is_file():
            reference_count += len(re.findall(r"(?m)^\s*@\w+\s*\{", bib_path.read_text(encoding="utf-8", errors="ignore")))
    return {
        "title": title,
        "abstract": abstract,
        "body": body,
        "full_text": " ".join(part for part in (title, abstract, body) if part),
        "sections": sections,
        "figures": len(re.findall(r"\\begin\{figure\*?\}", clean)),
        "tables": len(re.findall(r"\\begin\{table\*?\}", clean)),
        "references": reference_count,
        "counting_method": (
            "deterministic TeX plain-text extraction with balanced macro arguments; "
            "body excludes abstract, bibliography, figure and table content"
        ),
    }


def _markdown_metrics(path: Path) -> dict[str, Any]:
    raw = path.read_text(encoding="utf-8", errors="ignore")
    headings = re.findall(r"(?m)^#{1,6}\s+(.+?)\s*$", raw)
    title = headings[0] if headings else next((line.strip() for line in raw.splitlines() if line.strip()), "")
    abstract_match = re.search(
        r"(?ims)^#{1,6}\s+abstract\s*$\s*(.*?)(?=^#{1,6}\s+|\Z)", raw
    )
    abstract = abstract_match.group(1).strip() if abstract_match else ""
    body = raw
    if abstract_match:
        body = body[: abstract_match.start()] + body[abstract_match.end() :]
    body = re.sub(r"(?m)^#{1,6}\s+.*$", " ", body)
    reference_match = re.search(r"(?ims)^#{1,6}\s+references\s*$\s*(.*?)(?=^#{1,6}\s+|\Z)", raw)
    references = 0
    if reference_match:
        references = len(re.findall(r"(?m)^\s*(?:[-*]|\d+[.)])\s+", reference_match.group(1)))
    return {
        "title": title,
        "abstract": abstract,
        "body": re.sub(r"\s+", " ", body).strip(),
        "full_text": re.sub(r"\s+", " ", raw).strip(),
        "sections": headings,
        "figures": len(re.findall(r"!\[[^\]]*\]\([^\)]+\)", raw)),
        "tables": len(re.findall(r"(?m)^\s*\|(?:[^\n]*\|)+\s*$", raw)) // 2,
        "references": references,
        "counting_method": "deterministic Markdown heading/plain-text extraction",
    }


def manuscript_metrics(path: Path, bibliography_paths: list[Path]) -> tuple[dict[str, Any], str | None]:
    if not path.is_file():
        return {}, f"Compliance manuscript does not exist: {path}"
    suffix = path.suffix.lower()
    try:
        if suffix == ".tex":
            return _tex_metrics(path, bibliography_paths), None
        if suffix in {".md", ".txt"}:
            return _markdown_metrics(path), None
    except OSError as exc:
        return {}, f"Cannot read compliance manuscript {path}: {exc}"
    return {}, (
        f"Compliance manuscript format {suffix or '<none>'} is not deterministically analyzable; "
        "provide compliance_inputs.manuscript_path pointing to the current .tex, .md, or .txt source."
    )


def pdf_page_count(path: Path | None) -> tuple[int | None, str | None]:
    if path is None:
        return None, "No rendered PDF was supplied for the formal page-count rule."
    if not path.is_file() or path.suffix.lower() != ".pdf":
        return None, f"Rendered manuscript PDF is missing or not a .pdf file: {path}"
    try:
        from pypdf import PdfReader  # type: ignore[import-not-found]
    except ImportError:
        try:
            from PyPDF2 import PdfReader  # type: ignore[import-not-found,no-redef]
        except ImportError:
            return None, "Neither pypdf nor PyPDF2 is available for deterministic PDF page counting."
    try:
        return len(PdfReader(str(path)).pages), None
    except Exception as exc:  # pragma: no cover - parser-specific errors are fail-closed
        return None, f"Cannot count rendered PDF pages: {exc}"


def _normalized_heading(value: object) -> str:
    return re.sub(r"[^\w]+", " ", str(value or "").casefold()).strip()


def _rule_sources(rule: dict[str, Any], profile: dict[str, Any]) -> list[dict[str, str]]:
    wanted = set(string_list(rule.get("source_ids")))
    return [
        {"id": str(source.get("id") or ""), "url": str(source.get("url") or "")}
        for source in profile.get("sources", [])
        if isinstance(source, dict) and str(source.get("id") or "") in wanted
    ]


def _resolve_plan_context(
    plan_path: Path | None,
) -> tuple[dict[str, Any], Path | None, dict[str, str], set[str], list[Path], list[str]]:
    if plan_path is None:
        return {}, None, {}, set(), [], []
    plan, error = load_json(plan_path)
    if error:
        return {}, None, {}, set(), [], [error]
    base = plan_path.parent.resolve()
    project_root_value = plan.get("project_root")
    if not project_root_value:
        return plan, None, {}, set(), [], ["package plan project_root is required for final rule validation."]
    project_root = resolve_from(base, project_root_value)
    findings: list[str] = []
    if not project_root.is_dir():
        findings.append(f"package plan project_root does not exist: {project_root}")
    confirmations = {
        str(item.get("id")): str(item.get("status"))
        for item in plan.get("author_confirmations", [])
        if isinstance(item, dict) and item.get("id")
    }
    ready_materials: set[str] = set()
    for item in plan.get("items", []):
        if not isinstance(item, dict) or str(item.get("status")) != "ready":
            continue
        source = resolve_from(base, item.get("source_path"))
        if project_root.is_dir() and source.is_file() and is_relative_to(source, project_root):
            ready_materials.add(str(item.get("requirement_id") or ""))
    bibliography_paths: list[Path] = []
    inputs = plan.get("compliance_inputs")
    if not isinstance(inputs, dict):
        inputs = {}
    for raw in inputs.get("bibliography_paths", []) if isinstance(inputs.get("bibliography_paths"), list) else []:
        candidate = resolve_from(base, raw)
        if project_root.is_dir() and candidate.is_file() and is_relative_to(candidate, project_root):
            bibliography_paths.append(candidate)
        else:
            findings.append(f"compliance_inputs bibliography path is missing or outside project_root: {candidate}")
    return plan, project_root, confirmations, ready_materials, bibliography_paths, findings


def check_journal_rules(
    profile_path: Path,
    manuscript_path: Path,
    *,
    plan_path: Path | None = None,
    phase: str = "writing",
    rendered_pdf_path: Path | None = None,
) -> AuditResult:
    result = AuditResult("journal_rules", str(manuscript_path))
    if phase not in {"writing", "final"}:
        result.findings.append("phase must be writing or final.")
        return result
    profile_audit, profile = validate_profile(profile_path)
    result.findings.extend(profile_audit.findings)
    result.warnings.extend(profile_audit.warnings)
    plan, project_root, confirmations, ready_materials, bibliography_paths, plan_findings = _resolve_plan_context(
        plan_path
    )
    result.findings.extend(plan_findings if phase == "final" else [])
    if rendered_pdf_path is None and plan:
        inputs = plan.get("compliance_inputs") if isinstance(plan.get("compliance_inputs"), dict) else {}
        raw_pdf = inputs.get("rendered_pdf_path")
        if raw_pdf and plan_path is not None:
            rendered_pdf_path = resolve_from(plan_path.parent.resolve(), raw_pdf)
    if phase == "final" and rendered_pdf_path is not None and project_root is not None:
        if not is_relative_to(rendered_pdf_path.resolve(), project_root):
            result.findings.append(f"Rendered compliance PDF escapes project_root: {rendered_pdf_path}")
    manuscript = manuscript_path.resolve()
    if phase == "final":
        if plan_path is None:
            result.findings.append("Final journal-rule validation requires submission_package_plan.json.")
        elif project_root is not None and not is_relative_to(manuscript, project_root):
            result.findings.append(f"Compliance manuscript escapes project_root: {manuscript}")
    metrics, metrics_error = manuscript_metrics(manuscript, bibliography_paths)
    if metrics_error:
        result.findings.append(metrics_error)

    requirement_roles = {
        str(item.get("id") or ""): str(item.get("role") or "")
        for item in profile.get("package_requirements", [])
        if isinstance(item, dict)
    }
    attachment_count = len(
        [item for item in ready_materials if requirement_roles.get(item) not in {"main_manuscript", "blinded_manuscript"}]
    )
    rule_results: list[dict[str, Any]] = []
    rules = profile.get("compliance", {}).get("rules", []) if isinstance(profile.get("compliance"), dict) else []
    for rule in rules if isinstance(rules, list) else []:
        if not isinstance(rule, dict):
            continue
        verification = str(rule.get("verification") or "")
        metric = str(rule.get("metric") or "")
        scope = str(rule.get("scope") or "")
        observed: Any = None
        status = "pending"
        blocking = verification != "advisory"
        if phase == "writing" and (
            verification == "needs_author_confirmation" or metric in {"required_material"} or scope == "attachments"
        ):
            status = "deferred_to_final"
            blocking = False
        elif verification == "needs_author_confirmation":
            observed = confirmations.get(str(rule.get("confirmation_id") or ""), "missing")
            status = "pass" if observed == "confirmed" else "needs_author_confirmation"
        elif metric in {"word_count", "character_count", "page_count", "count"}:
            if scope == "attachments":
                observed = attachment_count
            elif metric == "page_count":
                observed, page_error = pdf_page_count(rendered_pdf_path)
                if page_error:
                    result.warnings.append(page_error)
            elif scope in {"figures", "tables", "references"}:
                observed = metrics.get(scope)
            else:
                text = metrics.get(scope)
                if isinstance(text, str):
                    if metric == "word_count":
                        observed = _word_count(text)
                    elif metric == "character_count":
                        observed = _character_count(text)
            if observed is not None:
                passed = observed <= rule.get("limit")
                status = "pass" if passed else "fail"
        elif metric == "required_sections":
            required = string_list(rule.get("limit"))
            present = {_normalized_heading(item) for item in metrics.get("sections", [])}
            missing = [item for item in required if _normalized_heading(item) not in present]
            observed = {"present": metrics.get("sections", []), "missing": missing}
            status = "pass" if not missing else "fail"
        elif metric == "required_material":
            required = string_list(rule.get("limit"))
            missing = [item for item in required if item not in ready_materials]
            observed = {"ready": sorted(ready_materials), "missing": missing}
            status = "pass" if not missing else "fail"

        if verification == "advisory":
            blocking = False
            status = f"advisory_{status}"
        remediation = str(rule.get("remediation") or "")
        record = {
            "id": str(rule.get("id") or ""),
            "area": str(rule.get("area") or ""),
            "verification": verification,
            "observed": observed,
            "limit": rule.get("limit"),
            "unit": str(rule.get("unit") or ""),
            "source": _rule_sources(rule, profile),
            "source_locator": str(rule.get("source_locator") or ""),
            "status": status,
            "blocking": blocking and status != "pass",
            "remediation": remediation,
        }
        rule_results.append(record)
        if record["blocking"]:
            result.findings.append(
                f"Journal rule {record['id']} is {status}: observed={observed!r}, "
                f"limit={record['limit']!r} {record['unit']}. Remediation: {remediation}"
            )
        elif verification == "advisory" and status != "advisory_pass":
            result.warnings.append(
                f"Advisory journal rule {record['id']} is {status}: observed={observed!r}, limit={record['limit']!r}."
            )

    result.findings = dedupe(result.findings)
    result.warnings = dedupe(result.warnings)
    result.details = {
        "phase": phase,
        "target": profile.get("target", {}).get("name"),
        "profile_sha256": sha256_file(profile_path) if profile_path.is_file() else None,
        "manuscript_path": str(manuscript),
        "manuscript_sha256": sha256_file(manuscript) if manuscript.is_file() else None,
        "counting_method": metrics.get("counting_method"),
        "rules": rule_results,
        "external_action_authorized": False,
    }
    return result


def journal_rules_markdown(result: AuditResult) -> str:
    lines = [
        "# Journal Rules Check",
        "",
        f"- Subject: `{result.subject}`",
        f"- Phase: {result.details.get('phase')}",
        f"- Status: {'PASS' if result.ok else 'BLOCKED'}",
        f"- Counting method: {result.details.get('counting_method') or 'unavailable'}",
        "- External action authorized: false",
        "",
        "| Rule | Area | Verification | Observed | Limit | Unit | Source | Status | Remediation |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for rule in result.details.get("rules", []):
        source = ", ".join(
            f"{item.get('id')} ({item.get('url')})" for item in rule.get("source", [])
        )
        lines.append(
            f"| {rule.get('id')} | {rule.get('area')} | {rule.get('verification')} | "
            f"{str(rule.get('observed')).replace('|', '/')} | {str(rule.get('limit')).replace('|', '/')} | "
            f"{rule.get('unit')} | {source.replace('|', '/')} | {rule.get('status')} | "
            f"{str(rule.get('remediation')).replace('|', '/')} |"
        )
    lines.extend(["", "## Blocking findings", ""])
    lines.extend(f"- {item}" for item in result.findings) if result.findings else lines.append("- None")
    lines.extend(["", "## Advisory findings", ""])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- None")
    return "\n".join(lines) + "\n"


def deterministic_zip(upload_root: Path, archive_path: Path) -> None:
    files = sorted(path for path in upload_root.rglob("*") if path.is_file())
    with zipfile.ZipFile(archive_path, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as archive:
        for path in files:
            relative = path.relative_to(upload_root).as_posix()
            info = zipfile.ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o100644 << 16
            archive.writestr(info, path.read_bytes())


def assemble_bundle(profile_path: Path, plan_path: Path, output_dir: Path) -> AuditResult:
    result = AuditResult("submission_bundle", str(output_dir))
    profile_audit, profile = validate_profile(profile_path)
    result.findings.extend(profile_audit.findings)
    result.warnings.extend(profile_audit.warnings)
    plan, error = load_json(plan_path)
    if error:
        result.findings.append(error)
        return result
    if str(plan.get("schema_version")) != SCHEMA_VERSION:
        result.findings.append(f"package plan schema_version must be {SCHEMA_VERSION}.")

    base = plan_path.parent.resolve()
    project_root_value = plan.get("project_root")
    if not project_root_value:
        result.findings.append("package plan project_root is required.")
        return result
    project_root = resolve_from(base, project_root_value)
    if not project_root.is_dir():
        result.findings.append(f"package plan project_root does not exist: {project_root}")
        return result
    output_dir = output_dir.resolve()
    if not is_relative_to(output_dir, project_root):
        result.findings.append(f"output_dir must stay within project_root: {output_dir}")
        return result
    if output_dir.exists() and any(output_dir.iterdir()):
        result.findings.append(f"output_dir is not empty; use a new immutable bundle directory: {output_dir}")
        return result

    compliance_inputs = plan.get("compliance_inputs")
    if not isinstance(compliance_inputs, dict):
        compliance_inputs = {}
    manuscript_value = compliance_inputs.get("manuscript_path")
    if not manuscript_value:
        rule_audit = AuditResult(
            "journal_rules",
            "<missing>",
            findings=[
                "submission_package_plan.compliance_inputs.manuscript_path is required for final journal-rule revalidation."
            ],
            details={"phase": "final", "rules": [], "external_action_authorized": False},
        )
    else:
        compliance_manuscript = resolve_from(base, manuscript_value)
        rule_audit = check_journal_rules(
            profile_path,
            compliance_manuscript,
            plan_path=plan_path,
            phase="final",
        )
    result.findings.extend(rule_audit.findings)
    result.warnings.extend(rule_audit.warnings)

    target_name = str(profile.get("target", {}).get("name") or "")
    if str(plan.get("target_name") or "") != target_name:
        result.findings.append("package plan target_name does not match the target profile.")
    expected_profile_hash = str(plan.get("target_profile_sha256") or "").lower()
    actual_profile_hash = sha256_file(profile_path)
    if expected_profile_hash != actual_profile_hash:
        result.findings.append(
            f"package plan target_profile_sha256 is stale: expected {expected_profile_hash or '<missing>'}, "
            f"actual {actual_profile_hash}."
        )

    confirmations = plan.get("author_confirmations")
    if not isinstance(confirmations, list):
        confirmations = []
        result.findings.append("package plan author_confirmations must be a list.")
    confirmation_map = {
        str(item.get("id")): str(item.get("status"))
        for item in confirmations
        if isinstance(item, dict) and item.get("id")
    }
    for confirmation_id in sorted(REQUIRED_CONFIRMATIONS):
        if confirmation_map.get(confirmation_id) != "confirmed":
            result.findings.append(f"Author confirmation is not complete: {confirmation_id}")

    requirements = profile.get("package_requirements") if isinstance(profile.get("package_requirements"), list) else []
    plan_items = plan.get("items")
    if not isinstance(plan_items, list):
        plan_items = []
        result.findings.append("package plan items must be a list.")
    item_map: dict[str, dict[str, Any]] = {}
    for index, item in enumerate(plan_items, start=1):
        if not isinstance(item, dict):
            result.findings.append(f"package plan items[{index}] must be an object.")
            continue
        requirement_id = str(item.get("requirement_id") or "")
        if not requirement_id:
            result.findings.append(f"package plan items[{index}].requirement_id is required.")
        elif requirement_id in item_map:
            result.findings.append(f"Duplicate package plan requirement_id: {requirement_id}")
        else:
            item_map[requirement_id] = item

    copy_jobs: list[tuple[Path, Path, dict[str, Any]]] = []
    pending_actions: list[str] = []
    forbidden_terms = string_list(plan.get("forbidden_target_terms"))
    known_requirement_ids = {str(item.get("id")) for item in requirements if isinstance(item, dict)}
    unknown_plan_ids = sorted(set(item_map) - known_requirement_ids)
    if unknown_plan_ids:
        result.findings.append(f"Package plan contains unknown requirement_ids: {unknown_plan_ids}")

    upload_root = output_dir / "upload"
    for requirement in requirements:
        if not isinstance(requirement, dict):
            continue
        requirement_id = str(requirement.get("id") or "")
        disposition = str(requirement.get("disposition") or "")
        condition_state = str(requirement.get("condition_status") or "")
        if disposition == "conditional" and condition_state == "unresolved":
            result.findings.append(f"Conditional package requirement is unresolved: {requirement_id}")
            pending_actions.append(requirement_id)
            continue
        applies = condition_state == "applies"
        if not applies:
            continue
        item = item_map.get(requirement_id)
        if item is None:
            message = f"No package-plan item for applicable requirement: {requirement_id}"
            if disposition in {"required", "conditional"}:
                result.findings.append(message)
                pending_actions.append(requirement_id)
            else:
                result.warnings.append(message)
            continue
        state = str(item.get("status") or "")
        if state not in PACKAGE_ITEM_STATES:
            result.findings.append(f"Package item {requirement_id} has invalid status: {state}")
            continue
        if state != "ready":
            message = f"Package item {requirement_id} is {state}."
            if disposition in {"required", "conditional"}:
                result.findings.append(message)
                pending_actions.append(requirement_id)
            else:
                result.warnings.append(message)
            continue

        source_value = item.get("source_path")
        if not source_value:
            result.findings.append(f"Package item {requirement_id} is ready but has no source_path.")
            continue
        source = resolve_from(base, source_value)
        if not is_relative_to(source, project_root):
            result.findings.append(f"Package item {requirement_id} source escapes project_root: {source}")
            continue
        if not source.is_file():
            result.findings.append(f"Package item {requirement_id} source does not exist: {source}")
            continue
        output_name = item.get("output_name") or source.name
        destination = safe_output_path(upload_root, output_name)
        if destination is None:
            result.findings.append(f"Package item {requirement_id} has unsafe output_name: {output_name}")
            continue
        accepted = {extension.lower() for extension in string_list(requirement.get("accepted_extensions"))}
        if source.suffix.lower() not in accepted:
            result.findings.append(
                f"Package item {requirement_id} has extension {source.suffix or '<none>'}; expected {sorted(accepted)}."
            )
            continue
        text = extract_searchable_text(source)
        placeholders = sorted(set(PLACEHOLDER_RE.findall(text))) if text else []
        if placeholders:
            result.findings.append(f"Package item {requirement_id} contains unresolved placeholders: {placeholders[:5]}")
        leaked_terms = [term for term in forbidden_terms if term.lower() in text.lower()] if text else []
        if leaked_terms:
            result.findings.append(f"Package item {requirement_id} contains old-target terms: {leaked_terms}")

        receipt_records = item.get("validation_receipts")
        if not isinstance(receipt_records, list) or not receipt_records:
            result.findings.append(f"Package item {requirement_id} has no validation_receipts.")
            receipt_records = []
        verified_receipts: list[dict[str, str]] = []
        for receipt_index, receipt in enumerate(receipt_records, start=1):
            if not isinstance(receipt, dict):
                result.findings.append(f"Package item {requirement_id} receipt {receipt_index} must be an object.")
                continue
            receipt_path = verify_file_receipt(
                receipt,
                base=base,
                project_root=project_root,
                label=f"Package item {requirement_id} receipt {receipt_index}",
                findings=result.findings,
            )
            if receipt_path:
                verified_receipts.append({"path": str(receipt_path), "sha256": sha256_file(receipt_path)})

        source_hash = sha256_file(source)
        entry = {
            "requirement_id": requirement_id,
            "role": requirement.get("role", "other"),
            "source_path": str(source),
            "source_sha256": source_hash,
            "output_path": destination.relative_to(output_dir).as_posix(),
            "transformation": str(item.get("transformation") or "copy"),
            "validation_receipts": verified_receipts,
        }
        copy_jobs.append((source, destination, entry))

    output_names = [str(destination).lower() for _, destination, _ in copy_jobs]
    if len(output_names) != len(set(output_names)):
        result.findings.append("Two package items resolve to the same output path.")

    output_dir.mkdir(parents=True, exist_ok=True)
    upload_root.mkdir(parents=True, exist_ok=True)
    copied_entries: list[dict[str, Any]] = []
    for source, destination, entry in copy_jobs:
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        copied = entry | {"output_sha256": sha256_file(destination), "size_bytes": destination.stat().st_size}
        copied_entries.append(copied)

    shutil.copy2(profile_path, output_dir / "target_profile.snapshot.json")
    shutil.copy2(plan_path, output_dir / "package_plan.snapshot.json")
    rules_json_path = output_dir / "journal_rules_final.json"
    rules_md_path = output_dir / "journal_rules_final.md"
    rules_json_path.write_text(
        json.dumps(rule_audit.payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    rules_md_path.write_text(journal_rules_markdown(rule_audit), encoding="utf-8")
    result.findings = dedupe(result.findings)
    result.warnings = dedupe(result.warnings)
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY" if result.ok else "BLOCKED",
        "target": target_name,
        "target_profile_sha256": actual_profile_hash,
        "package_plan_sha256": sha256_file(plan_path),
        "items": copied_entries,
        "pending_actions": dedupe(pending_actions),
        "warnings": result.warnings,
        "external_action_authorized": False,
        "journal_rules": {
            "status": "PASS" if rule_audit.ok else "BLOCKED",
            "json_path": rules_json_path.name,
            "json_sha256": sha256_file(rules_json_path),
            "markdown_path": rules_md_path.name,
            "markdown_sha256": sha256_file(rules_md_path),
            "rule_count": len(rule_audit.details.get("rules", [])),
        },
        "archive": None,
    }
    archive_path = output_dir / "submission_bundle.zip"
    if result.ok:
        deterministic_zip(upload_root, archive_path)
        archive_hash = sha256_file(archive_path)
        (output_dir / "submission_bundle.sha256").write_text(
            f"{archive_hash}  {archive_path.name}\n", encoding="utf-8"
        )
        manifest["archive"] = {
            "path": archive_path.name,
            "sha256": archive_hash,
            "size_bytes": archive_path.stat().st_size,
        }
    (output_dir / "bundle_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    result.details = manifest
    (output_dir / "bundle_manifest.md").write_text(bundle_manifest_markdown(manifest), encoding="utf-8")
    return result


def bundle_manifest_markdown(manifest: dict[str, Any]) -> str:
    lines = [
        "# Submission Bundle Manifest",
        "",
        f"- Target: {manifest.get('target')}",
        f"- Status: {manifest.get('status')}",
        f"- Target profile SHA-256: `{manifest.get('target_profile_sha256')}`",
        "",
        "## Upload Files",
        "",
        "| Requirement | Output | SHA-256 | Bytes |",
        "|---|---|---|---:|",
    ]
    for item in manifest.get("items", []):
        lines.append(
            f"| {item.get('requirement_id')} | `{item.get('output_path')}` | "
            f"`{item.get('output_sha256')}` | {item.get('size_bytes')} |"
        )
    if not manifest.get("items"):
        lines.append("| — | — | — | 0 |")
    lines.extend(["", "## Pending Author Actions", ""])
    pending = manifest.get("pending_actions") or []
    lines.extend(f"- {item}" for item in pending) if pending else lines.append("- None")
    rules = manifest.get("journal_rules") or {}
    lines.extend(
        [
            "",
            "## Journal Rules",
            "",
            f"- Status: {rules.get('status', 'BLOCKED')}",
            f"- Machine-readable receipt: `{rules.get('json_path')}` — `{rules.get('json_sha256')}`",
            f"- Human-readable receipt: `{rules.get('markdown_path')}` — `{rules.get('markdown_sha256')}`",
            f"- Rules evaluated: {rules.get('rule_count', 0)}",
        ]
    )
    lines.extend(["", "## Archive", ""])
    archive = manifest.get("archive")
    if archive:
        lines.append(f"- `{archive['path']}` — `{archive['sha256']}`")
    else:
        lines.append("- Not generated because the bundle is blocked.")
    return "\n".join(lines) + "\n"


def validate_review_round(path: Path) -> tuple[AuditResult, dict[str, Any]]:
    result = AuditResult("review_round", str(path))
    data, error = load_json(path)
    if error:
        result.findings.append(error)
        return result, data
    if str(data.get("schema_version")) != SCHEMA_VERSION:
        result.findings.append(f"schema_version must be {SCHEMA_VERSION}.")
    decision_type = str(data.get("decision_type") or "")
    if decision_type not in DECISION_TYPES:
        result.findings.append(f"decision_type must be one of {sorted(DECISION_TYPES)}.")
    round_number = data.get("round_number")
    if not isinstance(round_number, int) or round_number < 1:
        result.findings.append("round_number must be a positive integer.")
        round_number = 1
    if not str(data.get("round_id") or "").strip():
        result.findings.append("round_id is required.")
    if not str(data.get("cover_note") or "").strip():
        result.findings.append("cover_note is required and must be author-approved prose.")

    base = path.parent.resolve()
    project_root_value = data.get("project_root")
    if not project_root_value:
        result.findings.append("project_root is required.")
        return result, data
    project_root = resolve_from(base, project_root_value)
    if not project_root.is_dir():
        result.findings.append(f"project_root does not exist: {project_root}")
        return result, data

    source_files = data.get("source_decision_files")
    if not isinstance(source_files, list) or not source_files:
        result.findings.append("source_decision_files must contain the editor/reviewer source files.")
        source_files = []
    for index, record in enumerate(source_files, start=1):
        if not isinstance(record, dict):
            result.findings.append(f"source_decision_files[{index}] must be an object.")
            continue
        verify_file_receipt(
            record,
            base=base,
            project_root=project_root,
            label=f"source_decision_files[{index}]",
            findings=result.findings,
        )

    if round_number > 1:
        previous = data.get("previous_round")
        if not isinstance(previous, dict):
            result.findings.append("Multi-round rebuttal requires previous_round path and sha256.")
        else:
            verify_file_receipt(
                previous,
                base=base,
                project_root=project_root,
                label="previous_round",
                findings=result.findings,
            )

    comments = data.get("comments")
    if not isinstance(comments, list) or not comments:
        result.findings.append("comments must contain at least one atomic editor/reviewer issue.")
        comments = []
    comment_ids: set[str] = set()
    final_count = 0
    for index, comment in enumerate(comments, start=1):
        label = f"comments[{index}]"
        if not isinstance(comment, dict):
            result.findings.append(f"{label} must be an object.")
            continue
        comment_id = str(comment.get("id") or "")
        if not COMMENT_ID_RE.match(comment_id):
            result.findings.append(f"{label}.id must match E.C1, R1.C1, or an atomic child such as R1.C1.1.")
        elif comment_id in comment_ids:
            result.findings.append(f"Duplicate comment id: {comment_id}")
        else:
            comment_ids.add(comment_id)
        quote = str(comment.get("quoted_comment") or "").strip()
        if not quote:
            result.findings.append(f"{label}.quoted_comment is required.")
        expected_quote_hash = str(comment.get("quoted_comment_sha256") or "").lower()
        if expected_quote_hash != sha256_text(quote):
            result.findings.append(f"{label}.quoted_comment_sha256 does not match the preserved quote.")
        if not str(comment.get("atomic_issue") or "").strip():
            result.findings.append(f"{label}.atomic_issue is required.")
        if str(comment.get("issue_type") or "") not in ISSUE_TYPES:
            result.findings.append(f"{label}.issue_type must be one of {sorted(ISSUE_TYPES)}.")
        strategy = str(comment.get("strategy") or "")
        if strategy not in RESPONSE_STRATEGIES:
            result.findings.append(f"{label}.strategy must be one of {sorted(RESPONSE_STRATEGIES)}.")
        author_intent = comment.get("author_intent")
        if not isinstance(author_intent, dict) or str(author_intent.get("status") or "") != "confirmed":
            result.findings.append(f"{label}.author_intent must be explicitly confirmed.")
        elif not str(author_intent.get("position") or "").strip():
            result.findings.append(f"{label}.author_intent.position is required.")

        evidence = comment.get("evidence")
        if not isinstance(evidence, list):
            evidence = []
            result.findings.append(f"{label}.evidence must be a list.")
        evidence_ids: set[str] = set()
        has_new_result = False
        for evidence_index, item in enumerate(evidence, start=1):
            if not isinstance(item, dict):
                result.findings.append(f"{label}.evidence[{evidence_index}] must be an object.")
                continue
            evidence_id = str(item.get("id") or "")
            if not evidence_id:
                result.findings.append(f"{label}.evidence[{evidence_index}].id is required.")
            elif evidence_id in evidence_ids:
                result.findings.append(f"{label} has duplicate evidence id: {evidence_id}")
            else:
                evidence_ids.add(evidence_id)
            if str(item.get("verification_status") or "") != "verified":
                result.findings.append(f"{label}.evidence[{evidence_index}] is not verified.")
            if str(item.get("type") or "") in {"new_result", "new_analysis"}:
                has_new_result = True
        if strategy == "experiment" and not has_new_result:
            result.findings.append(f"{label} uses strategy=experiment but has no verified new_result/new_analysis evidence.")

        changes = comment.get("manuscript_changes")
        if not isinstance(changes, list):
            changes = []
            result.findings.append(f"{label}.manuscript_changes must be a list.")
        if strategy in {"accept", "clarify", "experiment", "partial"} and not changes:
            result.findings.append(f"{label} strategy {strategy} requires at least one locatable manuscript change.")
        for change_index, change in enumerate(changes, start=1):
            if not isinstance(change, dict):
                result.findings.append(f"{label}.manuscript_changes[{change_index}] must be an object.")
                continue
            if not str(change.get("locator") or "").strip():
                result.findings.append(f"{label}.manuscript_changes[{change_index}].locator is required.")
            if not str(change.get("summary") or "").strip():
                result.findings.append(f"{label}.manuscript_changes[{change_index}].summary is required.")
            if str(change.get("status") or "") != "verified":
                result.findings.append(f"{label}.manuscript_changes[{change_index}] is not verified.")
            unknown_evidence = sorted(set(string_list(change.get("evidence_ids"))) - evidence_ids)
            if unknown_evidence:
                result.findings.append(
                    f"{label}.manuscript_changes[{change_index}] references unknown evidence_ids: {unknown_evidence}"
                )

        response = comment.get("response")
        if not isinstance(response, dict):
            result.findings.append(f"{label}.response must be an object.")
            response = {}
        response_text = str(response.get("final_text") or "").strip()
        if str(response.get("status") or "") != "final":
            result.findings.append(f"{label}.response.status must be final.")
        elif not response_text:
            result.findings.append(f"{label}.response.final_text is required.")
        else:
            final_count += 1
        if PLACEHOLDER_RE.search(response_text):
            result.findings.append(f"{label}.response.final_text contains unresolved placeholders.")
        if strategy in {"defend", "cannot_complete"} and not str(comment.get("constraint_or_evidence") or "").strip():
            result.findings.append(f"{label} strategy {strategy} requires constraint_or_evidence.")

    revalidation = data.get("revalidation")
    if not isinstance(revalidation, list):
        revalidation = []
        result.findings.append("revalidation must be a list.")
    dimension_map: dict[str, dict[str, Any]] = {}
    for item in revalidation:
        if isinstance(item, dict) and item.get("dimension"):
            dimension_map[str(item["dimension"])] = item
    for dimension in sorted(REVALIDATION_DIMENSIONS):
        item = dimension_map.get(dimension)
        if item is None:
            result.findings.append(f"Missing revalidation dimension: {dimension}")
            continue
        status = str(item.get("status") or "")
        if status not in REVALIDATION_STATES:
            result.findings.append(f"Revalidation {dimension} has invalid status: {status}")
            continue
        if status == "pending":
            result.findings.append(f"Revalidation {dimension} is pending.")
        if decision_type in {"major_revision", "reject_and_resubmit"} and status != "passed":
            result.findings.append(f"{decision_type} requires revalidation {dimension}=passed.")
        if status == "passed":
            verify_file_receipt(
                item,
                base=base,
                project_root=project_root,
                label=f"revalidation {dimension}",
                findings=result.findings,
            )

    result.findings = dedupe(result.findings)
    result.warnings = dedupe(result.warnings)
    result.details = {
        "decision_type": decision_type,
        "round_number": round_number,
        "comment_count": len(comments),
        "final_response_count": final_count,
        "source_count": len(source_files),
    }
    return result, data


def pipe_cell(value: object) -> str:
    return re.sub(r"\s+", " ", str(value)).strip().replace("|", "\\|")


def render_rebuttal(review_path: Path, output_dir: Path) -> AuditResult:
    result, data = validate_review_round(review_path)
    result.kind = "rebuttal_package"
    result.subject = str(output_dir)
    if not result.ok:
        return result
    if output_dir.exists() and any(output_dir.iterdir()):
        result.findings.append(f"output_dir is not empty; use a new round directory: {output_dir}")
        return result
    output_dir.mkdir(parents=True, exist_ok=True)
    comments = data["comments"]

    extracted_lines = ["# Extracted Reviewer Comments", ""]
    matrix_lines = [
        "# Response Matrix",
        "",
        "| Comment ID | Reviewer | Original Comment | Issue Type | Required Action | Manuscript Change | Evidence | Response Draft | Status |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    letter_lines = ["# Response to the Editor and Reviewers", "", str(data["cover_note"]).strip(), ""]
    change_lines = [
        "# Revision Change Log",
        "",
        "Changes were applied to `final_paper/main.tex` or the canonical manuscript declared in the review-round contract.",
        "",
        "| Comment ID | Locator | Change | Evidence |",
        "|---|---|---|---|",
    ]
    for comment in comments:
        comment_id = str(comment["id"])
        reviewer = str(comment.get("reviewer") or "Reviewer")
        quote = str(comment["quoted_comment"]).strip()
        extracted_lines.extend([f"## {comment_id} — {reviewer}", "", quote, ""])
        changes = comment.get("manuscript_changes") or []
        change_summary = "; ".join(str(change.get("summary") or "") for change in changes) or "No manuscript change"
        locators = "; ".join(str(change.get("locator") or "") for change in changes) or "N/A"
        evidence_summary = "; ".join(str(item.get("id") or "") for item in comment.get("evidence") or []) or "Author rationale"
        response_text = str(comment["response"]["final_text"]).strip()
        matrix_lines.append(
            "| "
            + " | ".join(
                pipe_cell(value)
                for value in (
                    comment_id,
                    reviewer,
                    quote,
                    comment.get("issue_type"),
                    comment.get("strategy"),
                    f"{locators}: {change_summary}",
                    evidence_summary,
                    response_text,
                    "final",
                )
            )
            + " |"
        )
        letter_lines.extend(
            [
                f"## {comment_id} — {reviewer}",
                "",
                "> " + quote.replace("\n", "\n> "),
                "",
                "**Response:** " + response_text,
                "",
            ]
        )
        for change in changes:
            change_lines.append(
                "| "
                + " | ".join(
                    pipe_cell(value)
                    for value in (
                        comment_id,
                        change.get("locator"),
                        change.get("summary"),
                        ", ".join(string_list(change.get("evidence_ids"))) or "—",
                    )
                )
                + " |"
            )

    (output_dir / "reviewer_comments_extracted.md").write_text("\n".join(extracted_lines), encoding="utf-8")
    (output_dir / "response_matrix.md").write_text("\n".join(matrix_lines) + "\n", encoding="utf-8")
    (output_dir / "response_letter.md").write_text("\n".join(letter_lines), encoding="utf-8")
    (output_dir / "revision_change_log.md").write_text("\n".join(change_lines) + "\n", encoding="utf-8")
    shutil.copy2(review_path, output_dir / "review_round.snapshot.json")
    result.details |= {"output_files": sorted(path.name for path in output_dir.iterdir())}
    (output_dir / "rebuttal_check.md").write_text(audit_markdown(result), encoding="utf-8")
    return result


def profile_requirement_map(profile: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(item.get("id")): item
        for item in profile.get("package_requirements", [])
        if isinstance(item, dict) and item.get("id")
    }


def transfer_plan(
    origin_path: Path,
    destination_path: Path,
    request_path: Path,
    output_dir: Path,
) -> AuditResult:
    result = AuditResult("transfer_delta", str(output_dir))
    origin_audit, origin = validate_profile(origin_path)
    destination_audit, destination = validate_profile(destination_path)
    result.findings.extend(f"Origin profile: {item}" for item in origin_audit.findings)
    result.findings.extend(f"Destination profile: {item}" for item in destination_audit.findings)
    result.warnings.extend(f"Origin profile: {item}" for item in origin_audit.warnings)
    result.warnings.extend(f"Destination profile: {item}" for item in destination_audit.warnings)
    request, error = load_json(request_path)
    if error:
        result.findings.append(error)
        return result
    if str(request.get("schema_version")) != SCHEMA_VERSION:
        result.findings.append(f"transfer request schema_version must be {SCHEMA_VERSION}.")
    base = request_path.parent.resolve()
    project_root_value = request.get("project_root")
    if not project_root_value:
        result.findings.append("transfer request project_root is required.")
        return result
    project_root = resolve_from(base, project_root_value)
    if not project_root.is_dir():
        result.findings.append(f"transfer request project_root does not exist: {project_root}")
        return result
    output_dir = output_dir.resolve()
    if not is_relative_to(output_dir, project_root):
        result.findings.append(f"transfer output_dir must stay within project_root: {output_dir}")
        return result
    if output_dir.exists() and any(output_dir.iterdir()):
        result.findings.append(f"transfer output_dir is not empty: {output_dir}")
        return result

    origin_name = str(origin.get("target", {}).get("name") or "")
    destination_name = str(destination.get("target", {}).get("name") or "")
    if str(request.get("origin_target") or "") != origin_name:
        result.findings.append("transfer request origin_target does not match the origin profile.")
    if str(request.get("selected_target") or "") != destination_name:
        result.findings.append("transfer request selected_target does not match the destination profile.")
    if request.get("selected_target_confirmed") is not True:
        result.findings.append("selected_target_confirmed must be true before transfer planning.")

    user_preferences = request.get("user_preferences")
    required_preferences = {
        "must_haves",
        "nice_to_haves",
        "deal_breakers",
        "budget_or_access",
        "timing",
        "format_preferences",
    }
    if not isinstance(user_preferences, dict):
        result.findings.append("user_preferences must be an object.")
        user_preferences = {}
    missing_preferences = sorted(required_preferences - set(user_preferences))
    if missing_preferences:
        result.findings.append(f"user_preferences must explicitly record: {missing_preferences}")

    candidates = request.get("candidate_comparison")
    if not isinstance(candidates, list) or not candidates:
        result.findings.append("candidate_comparison must record the recommendation set.")
        candidates = []
    if len(candidates) < 2 and request.get("user_named_destination") is not True:
        result.findings.append("Recommend at least two contrasting candidates unless the user named the destination.")
    selected_candidates = [
        candidate for candidate in candidates
        if isinstance(candidate, dict) and str(candidate.get("target") or "") == destination_name
    ]
    if not selected_candidates:
        result.findings.append("candidate_comparison does not include the selected destination.")
    for index, candidate in enumerate(candidates, start=1):
        if not isinstance(candidate, dict):
            result.findings.append(f"candidate_comparison[{index}] must be an object.")
            continue
        if str(candidate.get("verdict") or "") not in FIT_VERDICTS:
            result.findings.append(f"candidate_comparison[{index}].verdict must be submit/reshape/redirect.")
        if not string_list(candidate.get("reasons")) or not string_list(candidate.get("tradeoffs")):
            result.findings.append(f"candidate_comparison[{index}] needs evidence-backed reasons and tradeoffs.")

    fit = request.get("fit_assessment")
    if not isinstance(fit, dict):
        fit = {}
        result.findings.append("fit_assessment must be an object.")
    verdict = str(fit.get("verdict") or "")
    if verdict not in FIT_VERDICTS:
        result.findings.append("fit_assessment.verdict must be submit/reshape/redirect.")
    if not string_list(fit.get("reasons")):
        result.findings.append("fit_assessment.reasons must explain the recommendation.")
    if verdict == "redirect":
        result.findings.append("Selected destination has verdict=redirect; choose another journal before rebuilding.")
    if verdict == "reshape" and (not string_list(fit.get("reshape_actions")) or fit.get("reshape_confirmed") is not True):
        result.findings.append("reshape verdict requires author-confirmed reshape_actions.")

    identity = request.get("paper_identity")
    if not isinstance(identity, dict):
        identity = {}
        result.findings.append("paper_identity must bind the canonical manuscript and contribution.")
    for key in ("canonical_manuscript", "confirmed_contribution"):
        record = identity.get(key)
        if not isinstance(record, dict):
            result.findings.append(f"paper_identity.{key} must contain path and sha256.")
            continue
        verify_file_receipt(
            record,
            base=base,
            project_root=project_root,
            label=f"paper_identity.{key}",
            findings=result.findings,
        )
    if not str(identity.get("claim_boundary") or "").strip():
        result.findings.append("paper_identity.claim_boundary is required.")
    if identity.get("confirmed") is not True:
        result.findings.append("paper_identity.confirmed must be true before transfer.")

    format_changes: list[dict[str, Any]] = []
    origin_format = origin.get("format") if isinstance(origin.get("format"), dict) else {}
    destination_format = destination.get("format") if isinstance(destination.get("format"), dict) else {}
    for key in sorted(set(origin_format) | set(destination_format)):
        if key == "source_ids":
            continue
        before = origin_format.get(key)
        after = destination_format.get(key)
        format_changes.append(
            {
                "field": key,
                "origin": before,
                "destination": after,
                "action": "rebuild" if before != after else "revalidate",
            }
        )

    five_part_changes: list[dict[str, Any]] = []
    origin_preferences = origin.get("five_part_preferences", {})
    destination_preferences = destination.get("five_part_preferences", {})
    for key in FIVE_PART_KEYS:
        five_part_changes.append(
            {
                "part": key,
                "origin": origin_preferences.get(key),
                "destination": destination_preferences.get(key),
                "action": "rebuild",
                "reason": "Destination-specific narrative preference is authoritative for transfer.",
            }
        )

    origin_requirements = profile_requirement_map(origin)
    package_changes: list[dict[str, Any]] = []
    for requirement_id, requirement in profile_requirement_map(destination).items():
        reuse_policy = str(requirement.get("reuse_policy") or "regenerate")
        if reuse_policy == "regenerate":
            action = "regenerate"
        elif reuse_policy == "author_supply":
            action = "request_from_author"
        elif requirement_id not in origin_requirements:
            action = "create_new"
        else:
            action = "revalidate"
        package_changes.append(
            {
                "requirement_id": requirement_id,
                "role": requirement.get("role", "other"),
                "action": action,
                "accepted_extensions": requirement.get("accepted_extensions", []),
                "condition_status": requirement.get("condition_status"),
            }
        )

    result.findings = dedupe(result.findings)
    result.warnings = dedupe(result.warnings)
    delta = {
        "schema_version": SCHEMA_VERSION,
        "status": "READY_TO_REBUILD" if result.ok else "BLOCKED",
        "origin_target": origin_name,
        "destination_target": destination_name,
        "origin_profile_sha256": sha256_file(origin_path),
        "destination_profile_sha256": sha256_file(destination_path),
        "transfer_request_sha256": sha256_file(request_path),
        "user_preferences": user_preferences,
        "fit_assessment": fit,
        "paper_identity": identity,
        "format_changes": format_changes,
        "five_part_changes": five_part_changes,
        "package_changes": package_changes,
        "required_next_steps": [
            "Rewrite from the canonical manuscript using the destination five-part preferences.",
            "Convert and render in the destination format without mutating the prior submission.",
            "Rebuild every destination package requirement according to its reuse policy.",
            "Run scientific, visual, citation, metadata, and artifact checks before bundle assembly.",
            "Create a new package plan and assemble an immutable destination bundle.",
        ],
    }
    result.details = delta
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "transfer_delta.json").write_text(
        json.dumps(delta, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "transfer_delta.md").write_text(transfer_delta_markdown(delta), encoding="utf-8")
    shutil.copy2(origin_path, output_dir / "origin_target_profile.snapshot.json")
    shutil.copy2(destination_path, output_dir / "destination_target_profile.snapshot.json")
    shutil.copy2(request_path, output_dir / "transfer_request.snapshot.json")
    return result


def transfer_delta_markdown(delta: dict[str, Any]) -> str:
    lines = [
        "# Journal Transfer Delta",
        "",
        f"- Origin: {delta.get('origin_target')}",
        f"- Destination: {delta.get('destination_target')}",
        f"- Status: {delta.get('status')}",
        f"- Fit verdict: {delta.get('fit_assessment', {}).get('verdict')}",
        "",
        "## Format Rebuild",
        "",
        "| Field | Action |",
        "|---|---|",
    ]
    for item in delta.get("format_changes", []):
        lines.append(f"| {item.get('field')} | {item.get('action')} |")
    lines.extend(["", "## Five-Part Narrative Rebuild", "", "| Part | Action |", "|---|---|"])
    for item in delta.get("five_part_changes", []):
        lines.append(f"| {item.get('part')} | {item.get('action')} |")
    lines.extend(["", "## Delivery-Package Rebuild", "", "| Requirement | Action |", "|---|---|"])
    for item in delta.get("package_changes", []):
        lines.append(f"| {item.get('requirement_id')} | {item.get('action')} |")
    lines.extend(["", "## Required Next Steps", ""])
    lines.extend(f"- {item}" for item in delta.get("required_next_steps", []))
    return "\n".join(lines) + "\n"


def audit_markdown(result: AuditResult) -> str:
    lines = [
        f"# {result.kind.replace('_', ' ').title()} Check",
        "",
        f"- Subject: `{result.subject}`",
        f"- Status: {'PASS' if result.ok else 'BLOCKED'}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {item}" for item in result.findings) if result.findings else lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- None")
    return "\n".join(lines) + "\n"


def public_interface_descriptor() -> dict[str, Any]:
    """Return the stable host-neutral publication-cycle interface descriptor."""

    operations = []
    for operation, spec in PUBLIC_OPERATION_SPECS.items():
        operations.append(
            {
                "id": operation,
                "mode": spec["mode"],
                "required_inputs": spec["required_inputs"],
                "required_outputs": spec["required_outputs"],
                "success_outcome": spec["success_outcome"],
                "success_stage": spec["success_stage"],
            }
        )
    return {
        "contract": "paperspine.publication-cycle.interface",
        "interface_version": INTERFACE_VERSION,
        "request_contract": INTERFACE_REQUEST_CONTRACT,
        "result_contract": INTERFACE_RESULT_CONTRACT,
        "transport": {
            "python": "invoke_publication_cycle(request_path)",
            "cli": "python scripts/publication_cycle.py invoke <request.json>",
            "describe_cli": "python scripts/publication_cycle.py describe",
        },
        "operations": operations,
        "flow": [
            {
                "order": 1,
                "stage": "canonical_paper_ready",
                "owner": "paperspine_main_flow",
                "meaning": "Canonical manuscript and five PaperSpine readiness dimensions are complete.",
            },
            {
                "order": 2,
                "stage": "target_profile_ready",
                "owner": "publication_cycle",
                "meaning": "Current official requirements and five-part venue preferences are validated.",
            },
            {
                "order": 3,
                "stage": "target_manuscript_and_materials_ready",
                "owner": "paperspine_main_flow",
                "meaning": "Format, five-part narrative, attachments, and author confirmations match the target.",
            },
            {
                "order": 4,
                "stage": "target_bundle_ready",
                "owner": "publication_cycle",
                "meaning": "Immutable READY manifest, upload ZIP, and SHA-256 receipt exist.",
            },
            {
                "order": 5,
                "stage": "external_submission",
                "owner": "user",
                "meaning": "Separate authorization is required; the interface never submits externally.",
            },
        ],
        "completion_rules": {
            "canonical_paper_complete_is_not_bundle_ready": True,
            "target_profile_requires_complete_official_rule_coverage": True,
            "writing_precheck_does_not_replace_final_bundle_revalidation": True,
            "transfer_delta_ready_requires_destination_rebuild": True,
            "rebuttal_ready_does_not_authorize_resubmission": True,
            "external_action_requires_separate_user_authorization": True,
        },
    }


def _authority_boundary() -> dict[str, bool]:
    return {
        "external_action_authorized": False,
        "may_infer_author_only_facts": False,
        "may_change_confirmed_scientific_identity": False,
        "may_accept_fees_or_licenses": False,
    }


def _public_result(
    *,
    request_path: Path,
    operation: str,
    result: AuditResult,
    input_receipts: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, Any]:
    spec = PUBLIC_OPERATION_SPECS.get(operation, {})
    normalized_operation = operation if operation in PUBLIC_OPERATION_SPECS else "unknown"
    ok = result.ok and bool(spec)
    next_action = (
        PUBLIC_NEXT_ACTIONS[operation]
        if ok
        else {
            "owner": "author_or_publication_cycle",
            "action": "resolve_blocking_findings_and_reinvoke",
        }
    )
    return {
        "contract": INTERFACE_RESULT_CONTRACT,
        "interface_version": INTERFACE_VERSION,
        "request_sha256": sha256_file(request_path) if request_path.is_file() else None,
        "operation": normalized_operation,
        "mode": spec.get("mode", "unknown"),
        "ok": ok,
        "outcome": spec.get("success_outcome") if ok else "BLOCKED",
        "stage": spec.get("success_stage") if ok else "blocked",
        "blocking_findings": result.findings,
        "warnings": result.warnings,
        "input_receipts": input_receipts,
        "artifacts": artifacts,
        "signals": {
            "operation_complete": ok,
            "submission_bundle_ready": ok and operation == "assemble",
            "rebuttal_materials_ready": ok and operation == "rebuttal_render",
            "destination_rebuild_ready": ok and operation == "transfer_plan",
            "external_action_authorized": False,
        },
        "next_action": next_action,
        "authority_boundary": _authority_boundary(),
        "audit": result.payload(),
    }


def _resolve_interface_path(
    *,
    request_path: Path,
    project_root: Path,
    value: object,
    label: str,
    must_be_file: bool,
    findings: list[str],
) -> Path | None:
    if not isinstance(value, str) or not value.strip():
        findings.append(f"{label} must be a non-empty path string.")
        return None
    candidate = resolve_from(request_path.parent, value)
    if not is_relative_to(candidate, project_root):
        findings.append(f"{label} escapes project_root: {candidate}")
        return None
    if must_be_file and not candidate.is_file():
        findings.append(f"{label} file does not exist: {candidate}")
        return None
    return candidate


def _validate_nested_project_root(contract_path: Path, outer_root: Path, label: str) -> str | None:
    contract, error = load_json(contract_path)
    if error:
        return error
    value = contract.get("project_root")
    if not value:
        return f"{label}.project_root is required."
    nested_root = resolve_from(contract_path.parent, value)
    if not is_relative_to(nested_root, outer_root):
        return f"{label}.project_root escapes invocation project_root: {nested_root}"
    return None


def _file_records(paths: list[tuple[str, Path]], project_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    seen: set[Path] = set()
    for role, path in paths:
        resolved = path.resolve()
        if resolved in seen or not resolved.is_file() or not is_relative_to(resolved, project_root):
            continue
        seen.add(resolved)
        records.append(
            {
                "role": role,
                "path": resolved.relative_to(project_root).as_posix(),
                "sha256": sha256_file(resolved),
                "size_bytes": resolved.stat().st_size,
            }
        )
    return records


def _output_records(output_dir: Path | None, project_root: Path) -> list[dict[str, Any]]:
    if output_dir is None or not output_dir.is_dir():
        return []
    return _file_records(
        [("generated_artifact", path) for path in sorted(output_dir.rglob("*")) if path.is_file()],
        project_root,
    )


def invoke_publication_cycle(request_path: str | Path) -> dict[str, Any]:
    """Execute one publication-cycle operation through a stable JSON envelope.

    All request paths are resolved relative to the invocation JSON and confined
    to its declared project_root.  Nested package/review/transfer contracts may
    narrow that root, but may not expand it.
    """

    path = Path(request_path).resolve()
    request, error = load_json(path)
    operation = str(request.get("operation") or "") if not error else ""
    findings: list[str] = [error] if error else []
    if not error and request.get("contract") != INTERFACE_REQUEST_CONTRACT:
        findings.append(f"contract must be {INTERFACE_REQUEST_CONTRACT}.")
    if not error and str(request.get("interface_version")) != INTERFACE_VERSION:
        findings.append(f"interface_version must be {INTERFACE_VERSION}.")
    if operation not in PUBLIC_OPERATION_SPECS:
        findings.append(f"operation must be one of {sorted(PUBLIC_OPERATION_SPECS)}.")

    project_root: Path | None = None
    if not error:
        root_value = request.get("project_root")
        if not isinstance(root_value, str) or not root_value.strip():
            findings.append("project_root must be a non-empty path string.")
        else:
            project_root = resolve_from(path.parent, root_value)
            if not project_root.is_dir():
                findings.append(f"project_root does not exist: {project_root}")
            elif not is_relative_to(path, project_root):
                findings.append(f"invocation request must stay within project_root: {path}")

    inputs = request.get("inputs") if isinstance(request.get("inputs"), dict) else {}
    outputs = request.get("outputs") if isinstance(request.get("outputs"), dict) else {}
    options = request.get("options") if isinstance(request.get("options"), dict) else {}
    if not isinstance(request.get("inputs"), dict):
        findings.append("inputs must be an object.")
    if request.get("outputs") is not None and not isinstance(request.get("outputs"), dict):
        findings.append("outputs must be an object when provided.")
    if request.get("options") is not None and not isinstance(request.get("options"), dict):
        findings.append("options must be an object when provided.")
    write_report = options.get("write_report", False)
    if not isinstance(write_report, bool):
        findings.append("options.write_report must be a boolean.")

    resolved_inputs: dict[str, Path] = {}
    output_dir: Path | None = None
    if project_root is not None and operation in PUBLIC_OPERATION_SPECS:
        spec = PUBLIC_OPERATION_SPECS[operation]
        for key in spec["required_inputs"]:
            candidate = _resolve_interface_path(
                request_path=path,
                project_root=project_root,
                value=inputs.get(key),
                label=f"inputs.{key}",
                must_be_file=True,
                findings=findings,
            )
            if candidate is not None:
                resolved_inputs[key] = candidate
        if spec["required_outputs"]:
            output_dir = _resolve_interface_path(
                request_path=path,
                project_root=project_root,
                value=outputs.get("directory"),
                label="outputs.directory",
                must_be_file=False,
                findings=findings,
            )

        nested_contracts = {
            "assemble": ("plan", "submission_package_plan"),
            "rebuttal_check": ("review_round", "review_round"),
            "rebuttal_render": ("review_round", "review_round"),
            "transfer_plan": ("transfer_request", "transfer_request"),
        }
        nested = nested_contracts.get(operation)
        if nested and nested[0] in resolved_inputs:
            nested_error = _validate_nested_project_root(resolved_inputs[nested[0]], project_root, nested[1])
            if nested_error:
                findings.append(nested_error)

    if findings or project_root is None:
        blocked = AuditResult("publication_cycle_interface", str(path), findings=dedupe(findings))
        return _public_result(
            request_path=path,
            operation=operation,
            result=blocked,
            input_receipts=[],
            artifacts=[],
        )

    input_receipts = _file_records(
        [(key, value) for key, value in sorted(resolved_inputs.items())],
        project_root,
    )
    produced: list[tuple[str, Path]] = []
    if operation == "profile_check":
        result, _ = validate_profile(resolved_inputs["profile"])
        if write_report:
            report = resolved_inputs["profile"].with_name("target_profile_check.md")
            report.write_text(audit_markdown(result), encoding="utf-8")
            produced.append(("target_profile_check", report))
    elif operation == "assemble":
        result = assemble_bundle(
            resolved_inputs["profile"],
            resolved_inputs["plan"],
            output_dir,
        )
    elif operation == "rebuttal_check":
        result, _ = validate_review_round(resolved_inputs["review_round"])
        if write_report:
            report = resolved_inputs["review_round"].with_name("rebuttal_check.md")
            report.write_text(audit_markdown(result), encoding="utf-8")
            produced.append(("rebuttal_check", report))
    elif operation == "rebuttal_render":
        result = render_rebuttal(resolved_inputs["review_round"], output_dir)
    else:
        result = transfer_plan(
            resolved_inputs["origin_profile"],
            resolved_inputs["destination_profile"],
            resolved_inputs["transfer_request"],
            output_dir,
        )

    artifacts = _file_records(produced, project_root) + _output_records(output_dir, project_root)
    return _public_result(
        request_path=path,
        operation=operation,
        result=result,
        input_receipts=input_receipts,
        artifacts=artifacts,
    )


def emit(result: AuditResult, *, json_output: bool, markdown_output: bool) -> None:
    if json_output:
        print(json.dumps(result.payload(), ensure_ascii=False, indent=2))
    if markdown_output or not json_output:
        print(audit_markdown(result), end="")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PaperSpine publication-cycle contracts and delivery assembly.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    describe = subparsers.add_parser("describe", help="Describe the stable host-neutral integration interface.")
    describe.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    invoke = subparsers.add_parser("invoke", help="Execute one operation from an invocation request JSON.")
    invoke.add_argument("request", type=Path)
    invoke.add_argument("--json", action="store_true", help=argparse.SUPPRESS)

    profile = subparsers.add_parser("profile-check", help="Validate publication_target_profile.json.")
    profile.add_argument("profile", type=Path)
    profile.add_argument("--json", action="store_true")
    profile.add_argument("--markdown", action="store_true")
    profile.add_argument("--write", action="store_true")

    rules = subparsers.add_parser(
        "rules-check",
        help="Precheck structured journal limits/requirements against a manuscript.",
    )
    rules.add_argument("profile", type=Path)
    rules.add_argument("manuscript", type=Path)
    rules.add_argument("--plan", type=Path)
    rules.add_argument("--rendered-pdf", type=Path)
    rules.add_argument("--phase", choices=("writing", "final"), default="writing")
    rules.add_argument("--json", action="store_true")
    rules.add_argument("--markdown", action="store_true")
    rules.add_argument("--write", action="store_true")

    assemble = subparsers.add_parser("assemble", help="Assemble an immutable target-specific upload bundle.")
    assemble.add_argument("profile", type=Path)
    assemble.add_argument("plan", type=Path)
    assemble.add_argument("output_dir", type=Path)
    assemble.add_argument("--json", action="store_true")
    assemble.add_argument("--markdown", action="store_true")

    rebuttal_check = subparsers.add_parser("rebuttal-check", help="Validate a machine-readable revision round.")
    rebuttal_check.add_argument("review_round", type=Path)
    rebuttal_check.add_argument("--json", action="store_true")
    rebuttal_check.add_argument("--markdown", action="store_true")
    rebuttal_check.add_argument("--write", action="store_true")

    rebuttal_render = subparsers.add_parser("rebuttal-render", help="Render a validated rebuttal package.")
    rebuttal_render.add_argument("review_round", type=Path)
    rebuttal_render.add_argument("output_dir", type=Path)
    rebuttal_render.add_argument("--json", action="store_true")
    rebuttal_render.add_argument("--markdown", action="store_true")

    transfer = subparsers.add_parser("transfer-plan", help="Create a target-to-target rebuild delta.")
    transfer.add_argument("origin_profile", type=Path)
    transfer.add_argument("destination_profile", type=Path)
    transfer.add_argument("request", type=Path)
    transfer.add_argument("output_dir", type=Path)
    transfer.add_argument("--json", action="store_true")
    transfer.add_argument("--markdown", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "describe":
        print(json.dumps(public_interface_descriptor(), ensure_ascii=False, indent=2))
        return 0
    if args.command == "invoke":
        payload = invoke_publication_cycle(args.request)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0 if payload["ok"] else 1
    if args.command == "profile-check":
        result, _ = validate_profile(args.profile.resolve())
        if args.write:
            args.profile.resolve().with_name("target_profile_check.md").write_text(
                audit_markdown(result), encoding="utf-8"
            )
    elif args.command == "rules-check":
        result = check_journal_rules(
            args.profile.resolve(),
            args.manuscript.resolve(),
            plan_path=args.plan.resolve() if args.plan else None,
            phase=args.phase,
            rendered_pdf_path=args.rendered_pdf.resolve() if args.rendered_pdf else None,
        )
        if args.write:
            stem = "journal_rules_precheck" if args.phase == "writing" else "journal_rules_final_preflight"
            report_dir = args.profile.resolve().parent
            (report_dir / f"{stem}.json").write_text(
                json.dumps(result.payload(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (report_dir / f"{stem}.md").write_text(journal_rules_markdown(result), encoding="utf-8")
    elif args.command == "assemble":
        result = assemble_bundle(args.profile.resolve(), args.plan.resolve(), args.output_dir.resolve())
    elif args.command == "rebuttal-check":
        result, _ = validate_review_round(args.review_round.resolve())
        if args.write:
            args.review_round.resolve().with_name("rebuttal_check.md").write_text(
                audit_markdown(result), encoding="utf-8"
            )
    elif args.command == "rebuttal-render":
        result = render_rebuttal(args.review_round.resolve(), args.output_dir.resolve())
    else:
        result = transfer_plan(
            args.origin_profile.resolve(),
            args.destination_profile.resolve(),
            args.request.resolve(),
            args.output_dir.resolve(),
        )
    if args.command == "rules-check":
        if args.json:
            print(json.dumps(result.payload(), ensure_ascii=False, indent=2))
        if args.markdown or not args.json:
            print(journal_rules_markdown(result), end="")
    else:
        emit(result, json_output=args.json, markdown_output=args.markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
