#!/usr/bin/env python3
"""Validate S0 semantic precision contracts for paper-framework-figure-studio-pro.

The guard is paper-neutral. It does not encode a target method, role name,
dataset, domain, or candidate id. It checks that S0 did not leave high-risk
figure directives as vague prose and that repeated roles/conditions have a
concrete visual realization contract before S1/S4 prompt preparation.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

POLICY_ID = "s0-semantic-precision-and-role-variation-lock-v3215f"
DEFAULT_REPORT = "outputs/S0-paper-foundation/paper-foundation-report.md"
DEFAULT_RISK_REGISTER = "outputs/S0-paper-foundation/framework-figure-risk-register.md"
DEFAULT_CONTRACT = "outputs/S0-paper-foundation/s0-semantic-precision-contract.json"

REQUIRED_TOP_LEVEL_FIELDS = [
    "ambiguous_directive_normalization",
    "actor_or_condition_variation_matrix",
    "role_visual_realization_contract",
    "process_instance_budget",
    "forbidden_misimplementation_locks",
    "downstream_s1_s4_carry_forward",
]

REQUIRED_NORMALIZATION_FIELDS = [
    "source_phrase",
    "source_evidence_anchor",
    "concrete_meaning",
    "visual_safe_instruction",
    "forbidden_interpretations",
    "downstream_fields",
]

REQUIRED_VARIATION_FIELDS = [
    "entity_family",
    "source_evidence_anchor",
    "same_canonical_workflow",
    "distinct_operations",
    "visual_representation",
    "full_flow_repetition_allowed",
]

ALLOWED_VISUAL_REPRESENTATIONS = {
    "representative_shared_flow",
    "branch_only_where_distinct",
    "parallel_lanes_required",
    "comparison_lanes_required",
    "topology_or_context_inset_only",
    "caption_only",
}

# These are generic high-risk cue patterns rather than paper examples. They
# intentionally mix English and Chinese because the workflow is bilingual.
HIGH_RISK_DIRECTIVE_PATTERNS = [
    r"preserv(?:e|ing)\s+[^\n\.]{0,40}(role|actor|condition|client|agent|modality|mode|domain|task|instance|difference|heterogeneity)",
    r"show\s+(each|different|multiple|all)\s+[^\n\.]{0,40}(role|actor|client|agent|condition|modality|mode|domain|task|instance)",
    r"highlight\s+[^\n\.]{0,40}(difference|heterogeneity|diversity|variation|role|actor|condition)",
    r"distinguish\s+[^\n\.]{0,40}(role|actor|condition|client|agent|mode|domain|task|instance)",
    r"reflect\s+[^\n\.]{0,40}(interaction|collaboration|difference|heterogeneity|role|actor)",
    r"保留[^。\n]{0,24}(角色|主体|客户端|参与方|条件|模式|差异|异质)",
    r"保持[^。\n]{0,24}(角色|主体|客户端|参与方|条件|模式|差异|异质)",
    r"区分[^。\n]{0,24}(角色|主体|客户端|参与方|条件|模式|差异|异质)",
    r"体现[^。\n]{0,24}(角色|主体|客户端|参与方|条件|模式|差异|异质|交互|协作)",
    r"展示(每个|不同|多个|所有)?[^。\n]{0,24}(角色|主体|客户端|参与方|条件|模式|差异|异质)",
]

HIGH_RISK_DIRECTIVE_RE = [re.compile(p, re.I) for p in HIGH_RISK_DIRECTIVE_PATTERNS]
SHARED_REPRESENTATIONS = {"representative_shared_flow", "topology_or_context_inset_only", "caption_only"}


@dataclass
class Finding:
    level: str
    category: str
    message: str
    path: str | None = None
    index: int | None = None


def read_text(path: Path) -> str:
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8-sig", errors="replace")


def load_json_file(path: Path, findings: list[Finding]) -> dict[str, Any] | None:
    if not path.is_file():
        findings.append(Finding("ERROR", "missing_contract", f"missing required S0 semantic precision contract: {path.as_posix()}", str(path)))
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        findings.append(Finding("ERROR", "invalid_json", f"contract is not valid JSON: {exc}", str(path)))
        return None


def excerpt(text: str, start: int, end: int, width: int = 100) -> str:
    lo = max(0, start - width // 2)
    hi = min(len(text), end + width // 2)
    return " ".join(text[lo:hi].split())[:220]


def find_high_risk_directives(text: str) -> list[str]:
    hits: list[str] = []
    seen: set[str] = set()
    for pattern in HIGH_RISK_DIRECTIVE_RE:
        for match in pattern.finditer(text):
            item = excerpt(text, match.start(), match.end())
            if item not in seen:
                seen.add(item)
                hits.append(item)
    return hits


def is_nonempty(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict, tuple, set)):
        return len(value) > 0
    return True


def as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        # Accept dict keyed by id/name for author convenience.
        return list(value.values())
    return []


def truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "yes", "y", "1", "allowed", "source_supported"}
    if isinstance(value, (int, float)):
        return bool(value)
    return False


def falsy(value: Any) -> bool:
    if isinstance(value, bool):
        return not value
    if isinstance(value, str):
        return value.strip().lower() in {"false", "no", "n", "0", "forbidden", "not_allowed", "disallowed"}
    if isinstance(value, (int, float)):
        return not bool(value)
    return False


def validate_normalization(contract: dict[str, Any], findings: list[Finding], contract_path: str) -> None:
    rows = as_list(contract.get("ambiguous_directive_normalization"))
    if not rows:
        findings.append(Finding("ERROR", "empty_normalization", "ambiguous_directive_normalization must contain at least one row or an explicit no-high-risk-directives record", contract_path))
        return
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", "normalization_row_type", "normalization row must be an object", contract_path, idx))
            continue
        for field in REQUIRED_NORMALIZATION_FIELDS:
            if not is_nonempty(row.get(field)):
                findings.append(Finding("ERROR", "normalization_missing_field", f"normalization row missing {field}", contract_path, idx))
        forbidden = row.get("forbidden_interpretations")
        if isinstance(forbidden, str):
            forbidden_items = [forbidden]
        else:
            forbidden_items = as_list(forbidden)
        if not forbidden_items:
            findings.append(Finding("ERROR", "missing_negative_lock", "normalization row must include at least one forbidden interpretation", contract_path, idx))
        visual = str(row.get("visual_safe_instruction", ""))
        if len(visual.strip()) < 16:
            findings.append(Finding("ERROR", "visual_instruction_too_short", "visual_safe_instruction is too short to guide downstream drawing safely", contract_path, idx))


def validate_variation_matrix(contract: dict[str, Any], findings: list[Finding], contract_path: str) -> None:
    rows = as_list(contract.get("actor_or_condition_variation_matrix"))
    if not rows:
        findings.append(Finding("ERROR", "empty_variation_matrix", "actor_or_condition_variation_matrix must contain repeated-role/condition decisions or an explicit no-repeated-entity record", contract_path))
        return
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", "variation_row_type", "variation row must be an object", contract_path, idx))
            continue
        for field in REQUIRED_VARIATION_FIELDS:
            if field not in row or (field != "distinct_operations" and not is_nonempty(row.get(field))):
                findings.append(Finding("ERROR", "variation_missing_field", f"variation row missing {field}", contract_path, idx))
        representation = row.get("visual_representation")
        if representation not in ALLOWED_VISUAL_REPRESENTATIONS:
            findings.append(
                Finding(
                    "ERROR",
                    "invalid_visual_representation",
                    f"visual_representation must be one of {sorted(ALLOWED_VISUAL_REPRESENTATIONS)}, not {representation!r}",
                    contract_path,
                    idx,
                )
            )
        same_workflow = truthy(row.get("same_canonical_workflow"))
        full_repetition = truthy(row.get("full_flow_repetition_allowed"))
        if same_workflow and full_repetition:
            findings.append(
                Finding(
                    "ERROR",
                    "shared_workflow_allows_full_duplication",
                    "same_canonical_workflow is true but full_flow_repetition_allowed is also true; shared workflows must not become one full pipeline per role unless the representation is repaired with source evidence",
                    contract_path,
                    idx,
                )
            )
        if representation in SHARED_REPRESENTATIONS and not falsy(row.get("full_flow_repetition_allowed")):
            findings.append(
                Finding(
                    "ERROR",
                    "shared_representation_missing_duplicate_flow_ban",
                    f"{representation} requires full_flow_repetition_allowed=false",
                    contract_path,
                    idx,
                )
            )


def validate_realization_contract(contract: dict[str, Any], findings: list[Finding], contract_path: str) -> None:
    rows = as_list(contract.get("role_visual_realization_contract"))
    if not rows:
        findings.append(Finding("ERROR", "empty_role_realization_contract", "role_visual_realization_contract must not be empty", contract_path))
        return
    for idx, row in enumerate(rows):
        if not isinstance(row, dict):
            findings.append(Finding("ERROR", "realization_row_type", "role realization row must be an object", contract_path, idx))
            continue
        positive = row.get("positive_visual_instruction") or row.get("visual_safe_instruction") or row.get("representation_instruction")
        negative = row.get("negative_visual_instruction") or row.get("forbidden_interpretations") or row.get("forbidden_misimplementation")
        if not is_nonempty(positive):
            findings.append(Finding("ERROR", "missing_positive_visual_instruction", "role realization row needs a positive visual instruction", contract_path, idx))
        if not is_nonempty(negative):
            findings.append(Finding("ERROR", "missing_negative_visual_instruction", "role realization row needs a negative/forbidden instruction", contract_path, idx))


def validate_process_budget(contract: dict[str, Any], findings: list[Finding], contract_path: str) -> None:
    budget = contract.get("process_instance_budget")
    if not isinstance(budget, dict):
        findings.append(Finding("ERROR", "invalid_process_instance_budget", "process_instance_budget must be an object", contract_path))
        return
    canonical_count = budget.get("default_canonical_process_count") or budget.get("canonical_process_count")
    if canonical_count is None:
        findings.append(Finding("ERROR", "missing_canonical_process_count", "process_instance_budget must state the default canonical process count", contract_path))
    full_instances = budget.get("allowed_full_process_instances", [])
    if truthy(budget.get("full_flow_repetition_allowed_by_default")):
        findings.append(Finding("ERROR", "full_flow_duplication_default_enabled", "full-flow repetition must not be allowed by default", contract_path))
    if full_instances and isinstance(full_instances, list):
        for idx, item in enumerate(full_instances):
            if isinstance(item, dict) and not is_nonempty(item.get("source_evidence_anchor")):
                findings.append(Finding("ERROR", "full_instance_missing_evidence", "allowed full-process instance must cite source evidence", contract_path, idx))


def validate_contract(contract: dict[str, Any] | None, findings: list[Finding], contract_path: str) -> None:
    if contract is None:
        return
    if contract.get("policy_id") not in {POLICY_ID, None}:
        findings.append(Finding("WARN", "unexpected_policy_id", f"unexpected policy_id: {contract.get('policy_id')!r}", contract_path))
    for field in REQUIRED_TOP_LEVEL_FIELDS:
        if field not in contract or not is_nonempty(contract.get(field)):
            findings.append(Finding("ERROR", "missing_top_level_field", f"contract missing required field: {field}", contract_path))
    validate_normalization(contract, findings, contract_path)
    validate_variation_matrix(contract, findings, contract_path)
    validate_realization_contract(contract, findings, contract_path)
    validate_process_budget(contract, findings, contract_path)
    locks = contract.get("forbidden_misimplementation_locks")
    if not is_nonempty(locks):
        findings.append(Finding("ERROR", "missing_forbidden_locks", "forbidden_misimplementation_locks must not be empty", contract_path))
    carry = contract.get("downstream_s1_s4_carry_forward")
    if not is_nonempty(carry):
        findings.append(Finding("ERROR", "missing_downstream_carry_forward", "downstream_s1_s4_carry_forward must not be empty", contract_path))


def contract_mentions_high_risk_source(contract: dict[str, Any] | None, hit: str) -> bool:
    if not contract:
        return False
    lowered = json.dumps(contract, ensure_ascii=False).lower()
    # Require only a meaningful fragment to avoid brittle exact matching.
    tokens = re.findall(r"[A-Za-z\u4e00-\u9fff]{2,}", hit.lower())
    score = sum(1 for token in tokens if token in lowered)
    return score >= max(1, min(3, len(tokens) // 3))


def scan_text_for_unresolved_vagueness(report_text: str, risk_text: str, contract: dict[str, Any] | None, findings: list[Finding]) -> None:
    combined = report_text + "\n" + risk_text
    hits = find_high_risk_directives(combined)
    for hit in hits:
        if not contract_mentions_high_risk_source(contract, hit):
            findings.append(
                Finding(
                    "ERROR",
                    "unresolved_high_risk_directive",
                    "high-risk vague directive appears in S0 text but is not covered by the semantic precision contract: " + hit,
                    None,
                )
            )


def resolve_path(run_dir: Path | None, explicit: str | None, default_rel: str) -> Path:
    if explicit:
        path = Path(explicit)
        if path.is_absolute() or run_dir is None:
            return path
        return run_dir / path
    if run_dir is None:
        return Path(default_rel)
    return run_dir / default_rel


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", help="Project run directory containing outputs/S0-paper-foundation")
    parser.add_argument("--report", help="Path to paper-foundation-report.md; relative to --run-dir when provided")
    parser.add_argument("--risk-register", help="Path to framework-figure-risk-register.md; relative to --run-dir when provided")
    parser.add_argument("--contract", help="Path to s0-semantic-precision-contract.json; relative to --run-dir when provided")
    parser.add_argument("--json-output")
    parser.add_argument("--fail-on-error", action="store_true")
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).resolve() if args.run_dir else None
    report_path = resolve_path(run_dir, args.report, DEFAULT_REPORT)
    risk_path = resolve_path(run_dir, args.risk_register, DEFAULT_RISK_REGISTER)
    contract_path = resolve_path(run_dir, args.contract, DEFAULT_CONTRACT)

    findings: list[Finding] = []
    report_text = read_text(report_path)
    risk_text = read_text(risk_path)
    if not report_text:
        findings.append(Finding("ERROR", "missing_report", f"missing or empty S0 report: {report_path.as_posix()}", str(report_path)))
    contract = load_json_file(contract_path, findings)
    validate_contract(contract, findings, str(contract_path))
    scan_text_for_unresolved_vagueness(report_text, risk_text, contract, findings)

    error_count = sum(1 for f in findings if f.level == "ERROR")
    report = {
        "schema_version": 1,
        "policy_id": POLICY_ID,
        "report_path": str(report_path),
        "risk_register_path": str(risk_path),
        "contract_path": str(contract_path),
        "finding_count": len(findings),
        "error_count": error_count,
        "findings": [asdict(f) for f in findings],
        "verdict": "PASS" if error_count == 0 else "FAIL",
        "non_hardcoding_guard": "The guard uses generic vague-directive patterns and schema checks; it contains no paper-specific roles, methods, edges, datasets, or candidate ids.",
    }
    if args.json_output:
        out = Path(args.json_output)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if args.fail_on_error and error_count:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
