#!/usr/bin/env python3
"""Validate and calibrate evidence-grounded PaperSpine review contracts.

The LLM or human reviewer writes the review; this module enforces traceability.
It deliberately contains no provider SDK and never treats a failed search as a
negative result.  It also emits calibration recommendations without mutating a
reviewer registry.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
POLICIES = {"balanced", "strict"}
SEVERITIES = {"CRITICAL", "MAJOR", "MINOR", "OBSERVATION"}
DISPOSITIONS = {"open", "resolved", "advisory", "dismissed", "needs_author"}
TOOL_STATUSES = {"completed", "partial", "no_hit", "provider_failure", "not_started"}
EXTERNAL_STATUSES = {"verified", "retrieved", "partial", "no_hit", "provider_failure", "not_started"}
LITERATURE_CRITERIA = {"novelty", "positioning", "baseline", "historical_context", "citation_coverage"}
PRECISE_LOCATOR_RE = re.compile(
    r"(?:\bpage\s*\d+|\bp\.\s*\d+|\blines?\s*\d+|\bparagraph\s*\d+|"
    r"\bfig(?:ure)?\.?\s*[a-z]?\d+|\btable\s*[a-z]?\d+|\beq(?:uation)?\.?\s*\d+|"
    r"\bappendix\s*[a-z0-9]+|\bsupp(?:lement)?\.?\s*[a-z0-9]+|页\s*\d+|行\s*\d+|"
    r"段\s*\d+|图\s*\d+|表\s*\d+|附录\s*[a-z0-9一二三四五六七八九十]+)",
    re.IGNORECASE,
)
CORE_STRICT_ROLES = {"methods", "contribution", "clarity"}
DEFAULT_REGISTRY = [
    {"persona_id": "editor", "role": "editor", "activation": "always", "cost_class": "medium"},
    {"persona_id": "methods", "role": "methods", "activation": "strict", "cost_class": "medium"},
    {"persona_id": "contribution", "role": "contribution", "activation": "strict", "cost_class": "medium"},
    {"persona_id": "clarity", "role": "clarity", "activation": "strict", "cost_class": "medium"},
    {"persona_id": "literature", "role": "literature", "activation": "open_literature", "cost_class": "high"},
    {"persona_id": "historian", "role": "historian", "activation": "historical_context", "cost_class": "medium"},
    {"persona_id": "baseline_scout", "role": "baseline_scout", "activation": "baseline_trigger", "cost_class": "high"},
    {"persona_id": "fact_checker", "role": "fact_checker", "activation": "claim_trigger", "cost_class": "medium"},
    {"persona_id": "critic", "role": "critic", "activation": "cross_lane_findings", "cost_class": "medium"},
    {"persona_id": "judge", "role": "judge", "activation": "review_conflict", "cost_class": "medium"},
]


@dataclass
class ValidationResult:
    contract_path: str
    ok: bool = False
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    finding_count: int = 0
    grounded_finding_count: int = 0
    external_grounded_count: int = 0
    tool_receipt_count: int = 0
    telemetry_unavailable_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    wall_seconds: float = 0.0


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _int_nonnegative(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _number_nonnegative(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0


def _resolve_registry_path(output_dir: Path | None = None) -> Path | None:
    candidates: list[Path] = []
    if output_dir is not None:
        candidates.append(output_dir / "reviewer_persona_registry.json")
    here = Path(__file__).resolve()
    candidates.extend([
        here.parents[1] / "skill" / "references" / "reviewer-persona-registry.json",
        here.parent.parent / "references" / "reviewer-persona-registry.json",
    ])
    return next((path for path in candidates if path.is_file()), None)


def load_persona_registry(output_dir: Path | None = None) -> list[dict[str, Any]]:
    path = _resolve_registry_path(output_dir)
    if path is None:
        return list(DEFAULT_REGISTRY)
    try:
        payload = _load_json(path)
    except (OSError, json.JSONDecodeError):
        return list(DEFAULT_REGISTRY)
    personas = payload.get("personas") if isinstance(payload, dict) else None
    if not isinstance(personas, list) or not personas:
        return list(DEFAULT_REGISTRY)
    return [item for item in personas if isinstance(item, dict)]


def build_review_plan(config: dict[str, Any], output_dir: Path | None = None) -> dict[str, Any]:
    """Select reviewer lanes conservatively and make their cost ceiling explicit."""
    policy = "strict" if str(config.get("review_policy", "balanced")).lower() == "strict" else "balanced"
    scope = str(config.get("literature_scope", "auto")).lower()
    if scope == "auto":
        scope = "closed_corpus" if str(config.get("reference_mode", "")).lower() == "specified_paths" else "open_literature"
    special = " ".join(str(item) for item in config.get("special_requirements", [])).lower()
    claim_trigger = any(token in special for token in ("first", "best", "state-of-the-art", "general", "novel", "首次", "最佳", "普适", "新颖"))
    history_trigger = any(token in special for token in ("history", "historical", "trajectory", "lineage", "脉络", "历史", "演进"))
    baseline_trigger = any(token in special for token in ("baseline", "benchmark", "dataset gap", "closest work", "基线", "数据集", "最近工作"))

    selected: list[dict[str, Any]] = []
    conditional: list[dict[str, Any]] = []
    for persona in load_persona_registry(output_dir):
        activation = str(persona.get("activation", "conditional"))
        role = str(persona.get("role", ""))
        active = (
            role == "editor"
            or (policy == "strict" and role in CORE_STRICT_ROLES)
            or (scope == "open_literature" and activation == "open_literature")
            or (history_trigger and activation == "historical_context")
            or (baseline_trigger and activation == "baseline_trigger")
            or (claim_trigger and activation == "claim_trigger")
        )
        target = selected if active else conditional
        target.append({
            "persona_id": persona.get("persona_id", role),
            "role": role,
            "activation": activation,
            "cost_class": persona.get("cost_class", "medium"),
            "reason": (
                "core editorial synthesis" if role == "editor" else
                "strict independent review" if policy == "strict" and role in CORE_STRICT_ROLES else
                "open-literature positioning" if active and activation == "open_literature" else
                "historical-context trigger" if active and activation == "historical_context" else
                "baseline-gap trigger" if active and activation == "baseline_trigger" else
                "claim-triggered verification" if active else
                "activate only when its trigger is observed"
            ),
        })

    default_budget = {
        "max_input_tokens": 30000 if policy == "balanced" else 90000,
        "max_output_tokens": 10000 if policy == "balanced" else 30000,
        "max_wall_seconds": 1200 if policy == "balanced" else 3600,
        "max_search_queries": 8 if policy == "balanced" else 20,
        "max_pdf_annotations": 12 if policy == "balanced" else 30,
    }
    override = config.get("review_budget")
    if isinstance(override, dict):
        for key in default_budget:
            if _number_nonnegative(override.get(key)):
                default_budget[key] = override[key]
    return {
        "schema_version": SCHEMA_VERSION,
        "policy": policy,
        "literature_scope": scope,
        "selected_personas": selected,
        "conditional_personas": conditional,
        "budget_ceiling": default_budget,
        "stop_rules": [
            "stop retrieval when the declared coverage question is answered or the budget ceiling is reached",
            "provider_failure is degraded coverage, never no_hit",
            "a unique high-severity grounded finding survives clustering",
            "Judge activates only for material conflicts; Critic activates only across evidence lanes",
        ],
    }


def write_review_plan(output_dir: Path, manuscript_path: Path, config: dict[str, Any]) -> Path:
    plan = build_review_plan(config, output_dir)
    plan["manuscript"] = {
        "path": str(manuscript_path),
        "sha256": _sha256(manuscript_path),
    }
    target = output_dir / "review_prompts" / "review_plan.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(plan, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def _validate_tool_receipts(receipts: Any, result: ValidationResult) -> dict[str, dict[str, Any]]:
    if not isinstance(receipts, list):
        result.errors.append("tool_receipts must be a list.")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    for index, receipt in enumerate(receipts, start=1):
        prefix = f"tool_receipts[{index}]"
        if not isinstance(receipt, dict):
            result.errors.append(f"{prefix} must be an object.")
            continue
        receipt_id = receipt.get("receipt_id")
        if not _nonempty(receipt_id):
            result.errors.append(f"{prefix}.receipt_id is required.")
            continue
        if receipt_id in indexed:
            result.errors.append(f"Duplicate tool receipt id: {receipt_id}.")
            continue
        indexed[receipt_id] = receipt
        status = receipt.get("status")
        if status not in TOOL_STATUSES:
            result.errors.append(f"{prefix}.status must be one of {sorted(TOOL_STATUSES)}.")
        action = receipt.get("action")
        if not _nonempty(action):
            result.errors.append(f"{prefix}.action is required.")
        if action == "paper_search":
            if not _nonempty(receipt.get("query")) or not _nonempty(receipt.get("provider")):
                result.errors.append(f"{prefix} paper_search needs query and provider.")
            if status == "no_hit" and receipt.get("result_count") != 0:
                result.errors.append(f"{prefix} no_hit must record result_count=0.")
            if status == "provider_failure" and not _nonempty(receipt.get("error")):
                result.errors.append(f"{prefix} provider_failure must record an error.")
        if action in {"pdf_locate", "pdf_annotate", "manuscript_read"} and not _nonempty(receipt.get("target_locator")):
            result.errors.append(f"{prefix} {action} needs target_locator.")
        usage = receipt.get("usage", {})
        if usage is None:
            usage = {}
        if not isinstance(usage, dict):
            result.errors.append(f"{prefix}.usage must be an object.")
            continue
        telemetry_status = usage.get("telemetry_status")
        if telemetry_status not in {None, "measured", "unavailable"}:
            result.errors.append(
                f"{prefix}.usage.telemetry_status must be measured or unavailable."
            )
        elif telemetry_status == "unavailable":
            result.telemetry_unavailable_count += 1
            result.warnings.append(
                f"{prefix} usage telemetry is unavailable; zero values are not measured cost."
            )
        for key in ("input_tokens", "output_tokens"):
            value = usage.get(key, 0)
            if not _int_nonnegative(value):
                result.errors.append(f"{prefix}.usage.{key} must be a non-negative integer.")
            else:
                setattr(result, key, getattr(result, key) + value)
        wall = usage.get("wall_seconds", 0)
        if not _number_nonnegative(wall):
            result.errors.append(f"{prefix}.usage.wall_seconds must be non-negative.")
        else:
            result.wall_seconds += float(wall)
    result.tool_receipt_count = len(indexed)
    return indexed


def _validate_reviewers(reviewers: Any, policy: str, receipts: dict[str, dict[str, Any]], result: ValidationResult) -> dict[str, dict[str, Any]]:
    if not isinstance(reviewers, list) or not reviewers:
        result.errors.append("reviewers must contain at least one reviewer receipt.")
        return {}
    indexed: dict[str, dict[str, Any]] = {}
    roles: set[str] = set()
    for index, reviewer in enumerate(reviewers, start=1):
        prefix = f"reviewers[{index}]"
        if not isinstance(reviewer, dict):
            result.errors.append(f"{prefix} must be an object.")
            continue
        reviewer_id = reviewer.get("reviewer_id")
        if not _nonempty(reviewer_id) or reviewer_id in indexed:
            result.errors.append(f"{prefix}.reviewer_id must be non-empty and unique.")
            continue
        indexed[reviewer_id] = reviewer
        role = str(reviewer.get("role", ""))
        roles.add(role)
        if not _nonempty(reviewer.get("persona_id")) or not role:
            result.errors.append(f"{prefix} needs persona_id and role.")
        receipt_id = reviewer.get("receipt_id")
        if receipt_id not in receipts:
            result.errors.append(f"{prefix}.receipt_id does not resolve to tool_receipts.")
        if policy == "strict" and reviewer.get("independent_pass") is not True:
            result.errors.append(f"{prefix}.independent_pass must be true in strict mode.")
    if policy == "strict":
        missing = sorted(CORE_STRICT_ROLES - roles)
        if missing:
            result.errors.append("Strict review is missing independent core roles: " + ", ".join(missing) + ".")
    return indexed


def _validate_paper_evidence(
    evidence: Any,
    finding_prefix: str,
    manuscript_sha: str,
    receipts: dict[str, dict[str, Any]],
    result: ValidationResult,
) -> bool:
    if not isinstance(evidence, list) or not evidence:
        result.errors.append(f"{finding_prefix}.paper_evidence must contain at least one manuscript anchor.")
        return False
    valid = False
    for index, anchor in enumerate(evidence, start=1):
        prefix = f"{finding_prefix}.paper_evidence[{index}]"
        if not isinstance(anchor, dict):
            result.errors.append(f"{prefix} must be an object.")
            continue
        kind = anchor.get("kind")
        locator = anchor.get("locator")
        if kind not in {"quote", "figure", "table", "equation", "absence_scan"}:
            result.errors.append(f"{prefix}.kind is invalid.")
            continue
        if not _nonempty(locator) or not PRECISE_LOCATOR_RE.search(str(locator)):
            result.errors.append(f"{prefix}.locator must include a page, line, paragraph, figure, table, equation, supplement, or appendix coordinate.")
            continue
        if anchor.get("source_sha256") != manuscript_sha:
            result.errors.append(f"{prefix}.source_sha256 must match manuscript.sha256.")
            continue
        if kind == "absence_scan":
            if not _nonempty(anchor.get("search_scope")) or not isinstance(anchor.get("search_terms"), list) or not anchor.get("search_terms"):
                result.errors.append(f"{prefix} absence_scan needs search_scope and search_terms.")
                continue
            receipt_id = anchor.get("receipt_id")
            if receipt_id not in receipts:
                result.errors.append(f"{prefix}.receipt_id does not resolve to a manuscript scan receipt.")
                continue
        elif not _nonempty(anchor.get("quote")):
            result.errors.append(f"{prefix}.quote is required for a positive manuscript anchor.")
            continue
        valid = True
    return valid


def validate_contract(
    contract: dict[str, Any],
    *,
    contract_path: str = "(memory)",
    manuscript_path: Path | None = None,
) -> ValidationResult:
    result = ValidationResult(contract_path=contract_path)
    if contract.get("schema_version") != SCHEMA_VERSION:
        result.errors.append(f"schema_version must be {SCHEMA_VERSION}.")
    if not _nonempty(contract.get("review_id")):
        result.errors.append("review_id is required.")
    policy = str(contract.get("policy", ""))
    if policy not in POLICIES:
        result.errors.append("policy must be balanced or strict.")
    literature_scope = str(contract.get("literature_scope", ""))
    if literature_scope not in {"closed_corpus", "open_literature"}:
        result.errors.append("literature_scope must be closed_corpus or open_literature.")

    manuscript = contract.get("manuscript")
    if not isinstance(manuscript, dict):
        result.errors.append("manuscript must be an object with path and sha256.")
        manuscript = {}
    manuscript_sha = str(manuscript.get("sha256", ""))
    if not re.fullmatch(r"[0-9a-f]{64}", manuscript_sha):
        result.errors.append("manuscript.sha256 must be a lowercase SHA-256 digest.")
    if not _nonempty(manuscript.get("path")):
        result.errors.append("manuscript.path is required.")
    if manuscript_path is not None:
        if not manuscript_path.is_file():
            result.errors.append(f"Manuscript file not found: {manuscript_path}.")
        elif manuscript_sha and _sha256(manuscript_path) != manuscript_sha:
            result.errors.append("manuscript.sha256 does not match the supplied manuscript file.")

    receipts = _validate_tool_receipts(contract.get("tool_receipts"), result)
    reviewers = _validate_reviewers(contract.get("reviewers"), policy, receipts, result)
    findings = contract.get("findings")
    if not isinstance(findings, list):
        result.errors.append("findings must be a list.")
        findings = []
    # An independent pass may find no defect. Reviewer and manuscript receipts
    # still identify the scope; requiring a finding would manufacture objections.
    result.finding_count = len(findings)
    finding_ids: set[str] = set()
    unresolved_blockers: set[str] = set()

    for index, finding in enumerate(findings, start=1):
        prefix = f"findings[{index}]"
        if not isinstance(finding, dict):
            result.errors.append(f"{prefix} must be an object.")
            continue
        finding_id = finding.get("finding_id")
        if not _nonempty(finding_id) or finding_id in finding_ids:
            result.errors.append(f"{prefix}.finding_id must be non-empty and unique.")
            continue
        finding_ids.add(finding_id)
        reviewer_id = finding.get("reviewer_id")
        if reviewer_id not in reviewers:
            result.errors.append(f"{prefix}.reviewer_id does not resolve to reviewers.")
        severity = finding.get("severity")
        if severity not in SEVERITIES:
            result.errors.append(f"{prefix}.severity must be one of {sorted(SEVERITIES)}.")
        if not _nonempty(finding.get("criterion")) or not _nonempty(finding.get("summary")) or not _nonempty(finding.get("recommendation")):
            result.errors.append(f"{prefix} needs criterion, summary, and recommendation.")
        confidence = finding.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool) or not 0 <= confidence <= 1:
            result.errors.append(f"{prefix}.confidence must be between 0 and 1.")
        disposition = finding.get("disposition")
        if disposition not in DISPOSITIONS:
            result.errors.append(f"{prefix}.disposition must be one of {sorted(DISPOSITIONS)}.")
        if severity in {"CRITICAL", "MAJOR"} and disposition in {"open", "needs_author"}:
            unresolved_blockers.add(str(finding_id))

        grounded = _validate_paper_evidence(
            finding.get("paper_evidence"), prefix, manuscript_sha, receipts, result
        )
        if grounded:
            result.grounded_finding_count += 1

        receipt_ids = finding.get("tool_receipt_ids")
        if not isinstance(receipt_ids, list) or not receipt_ids:
            result.errors.append(f"{prefix}.tool_receipt_ids must contain the read/search/annotation trace used for the finding.")
        else:
            for receipt_id in receipt_ids:
                if receipt_id not in receipts:
                    result.errors.append(f"{prefix}.tool_receipt_ids contains unresolved id {receipt_id!r}.")

        external = finding.get("external_evidence", [])
        if not isinstance(external, list):
            result.errors.append(f"{prefix}.external_evidence must be a list.")
            external = []
        verified_external = 0
        for ext_index, item in enumerate(external, start=1):
            ext_prefix = f"{prefix}.external_evidence[{ext_index}]"
            if not isinstance(item, dict):
                result.errors.append(f"{ext_prefix} must be an object.")
                continue
            status = item.get("status")
            if status not in EXTERNAL_STATUSES:
                result.errors.append(f"{ext_prefix}.status is invalid.")
                continue
            if not _nonempty(item.get("provider")) or not _nonempty(item.get("query")):
                result.errors.append(f"{ext_prefix} needs provider and query.")
            if status in {"verified", "retrieved"}:
                if not (_nonempty(item.get("record_id")) or _nonempty(item.get("url"))):
                    result.errors.append(f"{ext_prefix} retrieved evidence needs record_id or url.")
                else:
                    verified_external += 1
            if status == "provider_failure" and not _nonempty(item.get("error")):
                result.errors.append(f"{ext_prefix} provider_failure needs error detail.")
        if verified_external:
            result.external_grounded_count += 1

        criterion = str(finding.get("criterion", "")).lower()
        if literature_scope == "open_literature" and criterion in LITERATURE_CRITERIA:
            if severity in {"CRITICAL", "MAJOR"} and verified_external == 0:
                result.errors.append(
                    f"{prefix} cannot hard-block on {criterion} without retrieved external evidence; "
                    "provider failure/no-hit is degraded coverage, not proof."
                )
            elif verified_external == 0 and disposition != "advisory":
                result.errors.append(f"{prefix} without retrieved external evidence must be advisory.")

    synthesis = contract.get("synthesis")
    if not isinstance(synthesis, dict):
        result.errors.append("synthesis must be an object.")
        synthesis = {}
    status = synthesis.get("status")
    if status not in {"PASS", "BLOCKED"}:
        result.errors.append("synthesis.status must be PASS or BLOCKED.")
    blocker_ids = synthesis.get("blocker_finding_ids", [])
    if not isinstance(blocker_ids, list):
        result.errors.append("synthesis.blocker_finding_ids must be a list.")
        blocker_ids = []
    for blocker_id in blocker_ids:
        if blocker_id not in finding_ids:
            result.errors.append(f"synthesis blocker id {blocker_id!r} does not resolve to a finding.")
    if status == "PASS" and unresolved_blockers:
        result.errors.append("PASS contradicts unresolved CRITICAL/MAJOR findings: " + ", ".join(sorted(unresolved_blockers)) + ".")
    if status == "BLOCKED" and not blocker_ids:
        result.errors.append("BLOCKED synthesis must identify blocker_finding_ids.")

    result.ok = not result.errors
    return result


def validate_file(contract_path: Path, manuscript_path: Path | None = None) -> ValidationResult:
    try:
        payload = _load_json(contract_path)
    except FileNotFoundError:
        return ValidationResult(str(contract_path), errors=[f"Contract file not found: {contract_path}."])
    except json.JSONDecodeError as exc:
        return ValidationResult(str(contract_path), errors=[f"Invalid JSON: {exc}."])
    if not isinstance(payload, dict):
        return ValidationResult(str(contract_path), errors=["Contract root must be an object."])
    return validate_contract(payload, contract_path=str(contract_path), manuscript_path=manuscript_path)


def validation_markdown(result: ValidationResult) -> str:
    lines = [
        "# Evidence-Grounded Review Check",
        "",
        f"- Contract: `{result.contract_path}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- Findings grounded in manuscript: {result.grounded_finding_count}/{result.finding_count}",
        f"- Findings with retrieved external evidence: {result.external_grounded_count}",
        f"- Tool receipts: {result.tool_receipt_count}",
        f"- Measured tokens (available receipts only): {result.input_tokens} input + {result.output_tokens} output",
        f"- Measured tool/agent wall time (available receipts only): {result.wall_seconds:.2f} seconds",
        f"- Receipts with unavailable telemetry: {result.telemetry_unavailable_count}",
        "",
        "## Errors",
        "",
    ]
    lines.extend(f"- {item}" for item in result.errors) if result.errors else lines.append("- None")
    lines.extend(["", "## Warnings", ""])
    lines.extend(f"- {item}" for item in result.warnings) if result.warnings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def _tokens(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+|[\u4e00-\u9fff]", text.lower()))


def _finding_text(finding: dict[str, Any]) -> str:
    return " ".join(str(finding.get(key, "")) for key in ("criterion", "summary", "recommendation"))


def _similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    a, b = _tokens(_finding_text(left)), _tokens(_finding_text(right))
    if not a or not b:
        return 0.0
    score = len(a & b) / len(a | b)
    if str(left.get("criterion", "")).lower() == str(right.get("criterion", "")).lower():
        score = min(1.0, score + 0.1)
    return score


def calibrate_reviews(ai_review: dict[str, Any], human_review: dict[str, Any], threshold: float = 0.45) -> dict[str, Any]:
    ai_findings = [item for item in ai_review.get("findings", []) if isinstance(item, dict)]
    human_findings = [item for item in human_review.get("findings", []) if isinstance(item, dict)]
    ai_by_id = {str(item.get("finding_id")): item for item in ai_findings if _nonempty(item.get("finding_id"))}
    used_ai: set[str] = set()
    alignments: list[dict[str, Any]] = []

    for human in human_findings:
        human_id = str(human.get("finding_id", ""))
        explicit = [str(item) for item in human.get("matching_ai_ids", []) if str(item) in ai_by_id]
        best_id = explicit[0] if explicit else ""
        best_score = 1.0 if best_id else 0.0
        method = "explicit" if best_id else "lexical"
        if not best_id:
            for ai_id, ai in ai_by_id.items():
                if ai_id in used_ai:
                    continue
                score = _similarity(human, ai)
                if score > best_score:
                    best_id, best_score = ai_id, score
        hit = bool(best_id) and best_score >= threshold
        if hit:
            used_ai.add(best_id)
        alignments.append({
            "human_finding_id": human_id,
            "ai_finding_id": best_id if hit else None,
            "score": round(best_score, 3),
            "verdict": "hit" if hit else "miss",
            "method": method,
            "requires_human_confirmation": method == "lexical",
        })

    n_human, n_ai = len(human_findings), len(ai_findings)
    n_hits = sum(item["verdict"] == "hit" for item in alignments)
    n_misses = n_human - n_hits
    false_ids = [ai_id for ai_id in ai_by_id if ai_id not in used_ai]
    precision = n_hits / n_ai if n_ai else 0.0
    recall = n_hits / n_human if n_human else 0.0
    f1 = (2 * precision * recall / (precision + recall)) if precision + recall else 0.0
    severity_weight = {"CRITICAL": 4, "MAJOR": 3, "MINOR": 2, "OBSERVATION": 1}
    human_by_id = {str(item.get("finding_id", "")): item for item in human_findings}
    weighted_total = sum(severity_weight.get(str(item.get("severity")), 1) for item in human_findings)
    weighted_hit = sum(
        severity_weight.get(str(human_by_id[item["human_finding_id"]].get("severity")), 1)
        for item in alignments if item["verdict"] == "hit" and item["human_finding_id"] in human_by_id
    )

    selected_personas = {str(item.get("persona_id")) for item in ai_review.get("reviewers", []) if isinstance(item, dict)}
    misses: list[dict[str, Any]] = []
    suggestions: list[dict[str, Any]] = []
    for alignment in alignments:
        if alignment["verdict"] != "miss":
            continue
        human = human_by_id.get(alignment["human_finding_id"], {})
        expected = str(human.get("expected_persona") or human.get("reviewer_role") or "")
        failure_mode = "prompt_failure" if expected and expected in selected_personas else "selection_failure" if expected else "uncategorized"
        miss = {
            "human_finding_id": alignment["human_finding_id"],
            "severity": human.get("severity"),
            "criterion": human.get("criterion"),
            "expected_persona": expected or None,
            "failure_mode": failure_mode,
        }
        misses.append(miss)
        suggestions.append({
            "type": "strengthen_persona_prompt" if failure_mode == "prompt_failure" else "selection_policy_adjustment",
            "target_persona": expected or None,
            "criterion": human.get("criterion"),
            "support": 1,
            "evidence_finding_ids": [alignment["human_finding_id"]],
        })

    persona_stats: list[dict[str, Any]] = []
    for reviewer in ai_review.get("reviewers", []):
        if not isinstance(reviewer, dict):
            continue
        reviewer_id = str(reviewer.get("reviewer_id", ""))
        emitted = [item for item in ai_findings if str(item.get("reviewer_id")) == reviewer_id]
        emitted_ids = {str(item.get("finding_id")) for item in emitted}
        helped = len(emitted_ids & used_ai)
        false_count = len(emitted_ids & set(false_ids))
        persona_stats.append({
            "reviewer_id": reviewer_id,
            "persona_id": reviewer.get("persona_id"),
            "comments_emitted": len(emitted),
            "human_issues_helped_catch": helped,
            "false_alarms": false_count,
            "noise_ratio": round(false_count / len(emitted), 3) if emitted else None,
        })

    return {
        "schema_version": SCHEMA_VERSION,
        "paper_id": ai_review.get("review_id") or human_review.get("review_id"),
        "method": "explicit-links-then-conservative-lexical-alignment",
        "alignment_threshold": threshold,
        "alignment_requires_human_confirmation": any(item["requires_human_confirmation"] for item in alignments),
        "metrics": {
            "n_human": n_human,
            "n_ai": n_ai,
            "n_hits": n_hits,
            "n_misses": n_misses,
            "n_false_alarms": len(false_ids),
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "severity_weighted_recall": round(weighted_hit / weighted_total, 3) if weighted_total else 0.0,
        },
        "alignments": alignments,
        "false_alarm_finding_ids": false_ids,
        "miss_attributions": misses,
        "persona_stats": persona_stats,
        "suggestions": suggestions,
        "automatic_registry_mutation": False,
    }


def aggregate_calibrations(deltas: Iterable[dict[str, Any]], min_support: int = 2) -> dict[str, Any]:
    groups: dict[tuple[str, str, str], dict[str, Any]] = {}
    papers: defaultdict[tuple[str, str, str], set[str]] = defaultdict(set)
    for delta in deltas:
        paper_id = str(delta.get("paper_id", "unknown"))
        for suggestion in delta.get("suggestions", []):
            if not isinstance(suggestion, dict):
                continue
            key = (
                str(suggestion.get("type", "")),
                str(suggestion.get("target_persona") or ""),
                str(suggestion.get("criterion") or ""),
            )
            papers[key].add(paper_id)
            groups.setdefault(key, {
                "type": key[0], "target_persona": key[1] or None,
                "criterion": key[2] or None, "supporting_papers": [],
            })
    adopted: list[dict[str, Any]] = []
    for key, item in groups.items():
        support = sorted(papers[key])
        if len(support) >= min_support:
            item["supporting_papers"] = support
            item["support"] = len(support)
            adopted.append(item)
    return {
        "schema_version": SCHEMA_VERSION,
        "min_support": min_support,
        "recommendations": sorted(adopted, key=lambda item: (-item["support"], str(item["type"]))),
        "automatic_registry_mutation": False,
        "note": "Recommendations require held-out evaluation and explicit adoption.",
    }


def _write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PaperSpine evidence-grounded review protocol.")
    sub = parser.add_subparsers(dest="command", required=True)
    validate = sub.add_parser("validate")
    validate.add_argument("contract")
    validate.add_argument("--manuscript")
    validate.add_argument("--markdown", action="store_true")
    validate.add_argument("--write", action="store_true")
    plan = sub.add_parser("plan")
    plan.add_argument("output_dir")
    plan.add_argument("--manuscript", required=True)
    calibrate = sub.add_parser("calibrate")
    calibrate.add_argument("ai_review")
    calibrate.add_argument("human_review")
    calibrate.add_argument("--threshold", type=float, default=0.45)
    calibrate.add_argument("--output", required=True)
    aggregate = sub.add_parser("aggregate")
    aggregate.add_argument("deltas", nargs="+")
    aggregate.add_argument("--min-support", type=int, default=2)
    aggregate.add_argument("--output", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if args.command == "validate":
        contract_path = Path(args.contract)
        result = validate_file(contract_path, Path(args.manuscript) if args.manuscript else None)
        markdown = validation_markdown(result)
        if args.write:
            target = contract_path.parent / "evidence_review_check.md"
            target.write_text(markdown, encoding="utf-8")
            print(f"Wrote {target}", file=sys.stderr)
        print(markdown if args.markdown or not args.write else json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return 0 if result.ok else 1
    if args.command == "plan":
        output_dir = Path(args.output_dir)
        config_path = output_dir / "paper_spine_config.json"
        config = _load_json(config_path) if config_path.is_file() else {}
        target = write_review_plan(output_dir, Path(args.manuscript), config if isinstance(config, dict) else {})
        print(target)
        return 0
    if args.command == "calibrate":
        payload = calibrate_reviews(_load_json(Path(args.ai_review)), _load_json(Path(args.human_review)), args.threshold)
        _write_json(Path(args.output), payload)
        print(args.output)
        return 0
    deltas = [_load_json(Path(path)) for path in args.deltas]
    payload = aggregate_calibrations(deltas, max(1, args.min_support))
    _write_json(Path(args.output), payload)
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
