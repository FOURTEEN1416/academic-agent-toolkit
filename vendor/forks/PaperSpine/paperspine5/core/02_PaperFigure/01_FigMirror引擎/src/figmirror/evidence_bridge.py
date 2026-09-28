"""Aggregate-only evidence bridge from data studies to schematic figures.

The data-study pipeline owns statistics and provenance.  Schematic authoring
may consume a deliberately small, read-only bundle of aggregate facts, but it
must never receive row-level records or silently recompute the analysis.  This
module defines the file-oriented producer/consumer contract used by both
pipelines without merging their renderers.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import xml.etree.ElementTree as ET
from copy import deepcopy
from pathlib import Path
from typing import Any


EVIDENCE_BUNDLE_SCHEMA = "figmirror.data-evidence-bundle"
EVIDENCE_BUNDLE_VERSION = "0.1"
EVIDENCE_BINDING_SCHEMA = "figmirror.schematic-evidence-binding"
EVIDENCE_BINDING_VERSION = "0.1"
VALID_EVIDENCE_USES = {"schematic-label", "annotation", "sizing", "evidence-node"}


class EvidenceBridgeError(ValueError):
    """Raised when aggregate evidence cannot be safely published or bound."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise EvidenceBridgeError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise EvidenceBridgeError(f"JSON root must be an object: {path}")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _slug(value: object) -> str:
    source = str(value).strip().replace("%", "-pct").replace("#", "-abs").replace("+", "-plus")
    text = re.sub(r"[^A-Za-z0-9._-]+", "-", source).strip("-").lower()
    return text or hashlib.sha256(str(value).encode("utf-8")).hexdigest()[:12]


def _number(value: Any) -> float | int | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value


def _fact(
    fact_id: str,
    kind: str,
    subject: str,
    value: float | int,
    unit: str,
    display_text: str,
    source_pointer: str,
    *,
    direction: str | None = None,
) -> dict[str, Any]:
    record: dict[str, Any] = {
        "id": fact_id,
        "kind": kind,
        "subject": subject,
        "value": value,
        "unit": unit,
        "display_text": display_text,
        "source_pointer": source_pointer,
        "claim_scope": "descriptive",
        "allowed_uses": ["schematic-label", "annotation", "sizing", "evidence-node"],
    }
    if direction:
        record["direction"] = direction
    return record


def validate_data_evidence_bundle(raw: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a published aggregate evidence bundle."""

    if not isinstance(raw, dict):
        raise EvidenceBridgeError("evidence bundle root must be an object")
    bundle = dict(raw)
    if bundle.get("schema") != EVIDENCE_BUNDLE_SCHEMA:
        raise EvidenceBridgeError(f"evidence bundle schema must be {EVIDENCE_BUNDLE_SCHEMA}")
    if str(bundle.get("schema_version")) != EVIDENCE_BUNDLE_VERSION:
        raise EvidenceBridgeError(f"unsupported evidence bundle version: {bundle.get('schema_version')!r}")
    privacy = bundle.get("privacy")
    if not isinstance(privacy, dict) or privacy.get("aggregate_only") is not True:
        raise EvidenceBridgeError("evidence bundle must declare aggregate_only=true")
    if privacy.get("row_level_data_included") is not False:
        raise EvidenceBridgeError("evidence bundle must declare row_level_data_included=false")
    provenance = bundle.get("provenance")
    if not isinstance(provenance, dict):
        raise EvidenceBridgeError("evidence bundle requires provenance")
    profile_sha256 = str(provenance.get("profile_sha256") or "")
    if not re.fullmatch(r"[0-9A-Fa-f]{64}", profile_sha256):
        raise EvidenceBridgeError("evidence bundle requires a valid profile_sha256")
    scope = bundle.get("scope")
    if not isinstance(scope, dict) or not str(scope.get("statistical_unit") or "").strip():
        raise EvidenceBridgeError("evidence bundle requires scope.statistical_unit")
    if not isinstance(scope.get("rows"), int) or scope["rows"] <= 0:
        raise EvidenceBridgeError("evidence bundle requires a positive scope.rows")
    facts = bundle.get("facts")
    if not isinstance(facts, list) or not facts or len(facts) > 500:
        raise EvidenceBridgeError("evidence bundle requires 1-500 aggregate facts")
    ids: set[str] = set()
    normalized_facts: list[dict[str, Any]] = []
    for index, raw_fact in enumerate(facts):
        if not isinstance(raw_fact, dict):
            raise EvidenceBridgeError(f"facts[{index}] must be an object")
        item = dict(raw_fact)
        fact_id = str(item.get("id") or "").strip()
        if not fact_id or fact_id in ids:
            raise EvidenceBridgeError("evidence fact IDs must be non-empty and unique")
        ids.add(fact_id)
        if _number(item.get("value")) is None:
            raise EvidenceBridgeError(f"fact {fact_id} requires a numeric aggregate value")
        for field in ("kind", "subject", "unit", "display_text", "source_pointer"):
            if not str(item.get(field) or "").strip():
                raise EvidenceBridgeError(f"fact {fact_id} requires {field}")
        if item.get("claim_scope") != "descriptive":
            raise EvidenceBridgeError(f"fact {fact_id} must remain descriptive")
        allowed_uses = item.get("allowed_uses")
        if (
            not isinstance(allowed_uses, list)
            or not allowed_uses
            or any(not isinstance(value, str) or value not in VALID_EVIDENCE_USES for value in allowed_uses)
        ):
            raise EvidenceBridgeError(
                f"fact {fact_id} allowed_uses must be a non-empty subset of {sorted(VALID_EVIDENCE_USES)}"
            )
        item["allowed_uses"] = list(dict.fromkeys(allowed_uses))
        normalized_facts.append(item)
    limits = bundle.get("scientific_limits")
    if not isinstance(limits, list) or not limits or any(not isinstance(item, str) or not item.strip() for item in limits):
        raise EvidenceBridgeError("evidence bundle requires non-empty scientific_limits")
    bundle["facts"] = normalized_facts
    bundle["scientific_limits"] = [item.strip() for item in limits]
    return bundle


def load_data_evidence_bundle(path: str | Path) -> dict[str, Any]:
    """Load a validated aggregate evidence bundle."""

    return validate_data_evidence_bundle(_read_object(Path(path)))


def build_data_evidence_bundle(
    profile_path: str | Path,
    output_path: str | Path | None = None,
) -> dict[str, Any]:
    """Publish schematic-safe aggregate facts from a data-study profile."""

    profile_file = Path(profile_path).resolve()
    if not profile_file.is_file():
        raise FileNotFoundError(profile_file)
    profile = _read_object(profile_file)
    rows = profile.get("rows")
    statistical_unit = str(profile.get("statistical_unit") or "").strip()
    source = profile.get("source")
    if not isinstance(rows, int) or rows <= 0 or not statistical_unit:
        raise EvidenceBridgeError("data profile requires positive rows and statistical_unit")
    if not isinstance(source, dict) or not re.fullmatch(r"[0-9A-Fa-f]{64}", str(source.get("sha256") or "")):
        raise EvidenceBridgeError("data profile requires a hashed source record")

    facts: list[dict[str, Any]] = [
        _fact("dataset:rows", "dataset-size", "dataset", rows, "records", f"n={rows:,} records", "/rows")
    ]
    cohorts = profile.get("cohorts", [])
    if not isinstance(cohorts, list):
        raise EvidenceBridgeError("data profile cohorts must be a list")
    group_labels = {
        str(item.get("group")): str(item.get("display_label") or item.get("group"))
        for item in cohorts
        if isinstance(item, dict) and item.get("group")
    }
    for index, cohort in enumerate(cohorts):
        if not isinstance(cohort, dict):
            continue
        group = str(cohort.get("group") or cohort.get("display_label") or f"group-{index + 1}")
        label = str(cohort.get("display_label") or group)
        group_slug = _slug(label)
        count = _number(cohort.get("n"))
        if count is not None:
            facts.append(
                _fact(
                    f"cohort:{group_slug}:n",
                    "cohort-size",
                    label,
                    count,
                    "records",
                    f"{label}: n={int(count):,}",
                    f"/cohorts/{index}/n",
                )
            )
        age = _number(cohort.get("age_median_years"))
        if age is not None:
            facts.append(
                _fact(
                    f"cohort:{group_slug}:age-median",
                    "age-median",
                    label,
                    age,
                    "years",
                    f"{label}: median age {age:.1f} years",
                    f"/cohorts/{index}/age_median_years",
                )
            )

    metrics = profile.get("metrics", [])
    if not isinstance(metrics, list) or not metrics:
        raise EvidenceBridgeError("data profile requires a non-empty metrics list")
    for metric_index, metric in enumerate(metrics):
        if not isinstance(metric, dict):
            continue
        name = str(metric.get("metric") or f"metric-{metric_index + 1}")
        metric_slug = _slug(name)
        overall_rate = _number(metric.get("abnormal_rate"))
        if overall_rate is not None:
            facts.append(
                _fact(
                    f"metric:{metric_slug}:abnormal-rate",
                    "abnormal-rate",
                    name,
                    overall_rate,
                    "proportion",
                    f"{name}: {overall_rate * 100:.1f}% source-flagged abnormal",
                    f"/metrics/{metric_index}/abnormal_rate",
                )
            )
        per_group = metric.get("per_group", {})
        if isinstance(per_group, dict):
            for group_index, (group, values) in enumerate(per_group.items()):
                if not isinstance(values, dict):
                    continue
                group_label = group_labels.get(str(group), str(group))
                group_slug = _slug(group_label)
                group_rate = _number(values.get("abnormal_rate"))
                high_n = _number(values.get("high_n"))
                low_n = _number(values.get("low_n"))
                group_n = _number(values.get("n"))
                if group_rate is not None:
                    facts.append(
                        _fact(
                            f"metric:{metric_slug}:group:{group_slug}:abnormal-rate",
                            "group-abnormal-rate",
                            f"{name} · {group_label}",
                            group_rate,
                            "proportion",
                            f"{name} · {group_label}: {group_rate * 100:.1f}% source-flagged abnormal",
                            f"/metrics/{metric_index}/per_group/{group}/abnormal_rate",
                        )
                    )
                if group_n and high_n is not None and low_n is not None:
                    balance = (high_n - low_n) / group_n
                    direction = "higher" if balance > 0 else "lower" if balance < 0 else "balanced"
                    facts.append(
                        _fact(
                            f"metric:{metric_slug}:group:{group_slug}:flag-balance",
                            "source-flag-balance",
                            f"{name} · {group_label}",
                            balance,
                            "proportion-points",
                            f"{name} · {group_label}: {abs(balance) * 100:.1f} pp {direction}",
                            f"/metrics/{metric_index}/per_group/{group}",
                            direction=direction,
                        )
                    )
        tests = metric.get("tests", {})
        if isinstance(tests, dict):
            effect = _number(tests.get("cramers_v"))
            q_value = _number(tests.get("abnormality_chi_square_q"))
            if effect is not None:
                q_text = f", BH-FDR q={q_value:.3g}" if q_value is not None else ""
                facts.append(
                    _fact(
                        f"metric:{metric_slug}:association",
                        "group-association",
                        name,
                        effect,
                        "Cramer's V",
                        f"{name}: Cramer's V={effect:.3f}{q_text}",
                        f"/metrics/{metric_index}/tests/cramers_v",
                    )
                )

    schematic_facts = profile.get("schematic_facts", [])
    if not isinstance(schematic_facts, list):
        raise EvidenceBridgeError("data profile schematic_facts must be a list")
    known_fact_ids = {item["id"] for item in facts}
    for fact_index, raw_fact in enumerate(schematic_facts):
        if not isinstance(raw_fact, dict):
            raise EvidenceBridgeError(f"schematic_facts[{fact_index}] must be an object")
        fact_id = str(raw_fact.get("id") or "").strip()
        value = _number(raw_fact.get("value"))
        kind = str(raw_fact.get("kind") or "").strip()
        subject = str(raw_fact.get("subject") or "").strip()
        unit = str(raw_fact.get("unit") or "").strip()
        display_text = str(raw_fact.get("display_text") or "").strip()
        source_pointer = str(raw_fact.get("source_pointer") or f"/schematic_facts/{fact_index}/value").strip()
        if not fact_id or fact_id in known_fact_ids:
            raise EvidenceBridgeError("schematic_facts IDs must be non-empty and unique across the evidence bundle")
        if value is None or not all((kind, subject, unit, display_text, source_pointer)):
            raise EvidenceBridgeError(
                f"schematic_facts[{fact_index}] requires numeric value plus kind, subject, unit, display_text, and source_pointer"
            )
        item = _fact(
            fact_id,
            kind,
            subject,
            value,
            unit,
            display_text,
            source_pointer,
            direction=str(raw_fact.get("direction") or "").strip() or None,
        )
        if "allowed_uses" in raw_fact:
            allowed_uses = raw_fact["allowed_uses"]
            if (
                not isinstance(allowed_uses, list)
                or not allowed_uses
                or any(not isinstance(use, str) or use not in VALID_EVIDENCE_USES for use in allowed_uses)
            ):
                raise EvidenceBridgeError(
                    f"schematic_facts[{fact_index}].allowed_uses must be a non-empty subset of {sorted(VALID_EVIDENCE_USES)}"
                )
            item["allowed_uses"] = list(dict.fromkeys(allowed_uses))
        facts.append(item)
        known_fact_ids.add(fact_id)

    limits = profile.get("interpretation_limits", [])
    if not isinstance(limits, list) or not limits:
        raise EvidenceBridgeError("data profile requires interpretation_limits")
    bundle = {
        "schema": EVIDENCE_BUNDLE_SCHEMA,
        "schema_version": EVIDENCE_BUNDLE_VERSION,
        "producer": {"module": "figmirror.data_analysis", "domain": profile.get("domain")},
        "provenance": {
            "profile_path": str(profile_file),
            "profile_sha256": _sha256(profile_file),
            "source": source,
        },
        "scope": {
            "statistical_unit": statistical_unit,
            "rows": rows,
            "groups": list(profile.get("groups", [])),
            "metric_count": len(metrics),
            "schematic_fact_count": len(schematic_facts),
        },
        "privacy": {
            "aggregate_only": True,
            "row_level_data_included": False,
            "raw_source_path_exposed_for_provenance_only": True,
        },
        "scientific_limits": limits,
        "facts": facts,
    }
    validated = validate_data_evidence_bundle(bundle)
    target = Path(output_path).resolve() if output_path is not None else profile_file.with_name("schematic_evidence.json")
    _write_object(target, validated)
    return {
        "status": "PASS",
        "bundle": str(target),
        "fact_count": len(validated["facts"]),
        "aggregate_only": True,
        "source_profile_sha256": validated["provenance"]["profile_sha256"],
    }


def _normalize_presentation(raw_binding: dict[str, Any], index: int) -> tuple[str, dict[str, Any]]:
    raw_presentation = raw_binding.get("presentation", {})
    if raw_presentation is None:
        raw_presentation = {}
    if not isinstance(raw_presentation, dict):
        raise EvidenceBridgeError(f"bindings[{index}].presentation must be an object")
    target_field = str(raw_presentation.get("target_field") or "detail").strip()
    if target_field not in {"label", "detail"}:
        raise EvidenceBridgeError(f"bindings[{index}].presentation.target_field must be label or detail")
    separator = str(raw_presentation.get("separator") if "separator" in raw_presentation else "; ")
    prefix = str(raw_presentation.get("prefix") or "")
    suffix = str(raw_presentation.get("suffix") or "")
    max_lines = raw_presentation.get("max_lines", 8)
    if isinstance(max_lines, bool) or not isinstance(max_lines, int) or not 1 <= max_lines <= 12:
        raise EvidenceBridgeError(f"bindings[{index}].presentation.max_lines must be an integer from 1 to 12")
    if not separator or len(separator) > 20 or len(prefix) > 80 or len(suffix) > 80:
        raise EvidenceBridgeError(
            f"bindings[{index}].presentation separator/prefix/suffix exceed the safe text contract"
        )
    default_use = "schematic-label" if target_field == "label" else "annotation"
    use = str(raw_binding.get("use") or default_use).strip()
    if use not in VALID_EVIDENCE_USES:
        raise EvidenceBridgeError(f"bindings[{index}].use must be one of {sorted(VALID_EVIDENCE_USES)}")
    if target_field == "label" and use != "schematic-label":
        raise EvidenceBridgeError(f"bindings[{index}] label materialization requires use=schematic-label")
    if target_field == "detail" and use not in {"annotation", "evidence-node"}:
        raise EvidenceBridgeError(
            f"bindings[{index}] detail materialization requires use=annotation or evidence-node"
        )
    return use, {
        "target_field": target_field,
        "separator": separator,
        "prefix": prefix,
        "suffix": suffix,
        "max_lines": max_lines,
        "mode": "replace-with-exact-display-text",
    }


def _normalize_bindings(
    raw_bindings: Any,
    known_facts: dict[str, dict[str, Any]],
    *,
    known_nodes: set[str] | None = None,
) -> tuple[list[dict[str, Any]], set[str]]:
    if not isinstance(raw_bindings, list) or not raw_bindings:
        raise EvidenceBridgeError("schematic evidence mapping requires a non-empty bindings list")
    bindings: list[dict[str, Any]] = []
    selected: set[str] = set()
    targets: set[tuple[str, str]] = set()
    for index, raw_binding in enumerate(raw_bindings):
        if not isinstance(raw_binding, dict):
            raise EvidenceBridgeError(f"bindings[{index}] must be an object")
        node_id = str(raw_binding.get("node_id") or "").strip()
        fact_ids = raw_binding.get("fact_ids")
        if not node_id or not isinstance(fact_ids, list) or not fact_ids:
            raise EvidenceBridgeError(f"bindings[{index}] requires node_id and fact_ids")
        if known_nodes is not None and node_id not in known_nodes:
            raise EvidenceBridgeError(f"bindings[{index}] references unknown schematic node {node_id!r}")
        normalized_ids = [str(item).strip() for item in fact_ids]
        if len(normalized_ids) != len(set(normalized_ids)):
            raise EvidenceBridgeError(f"bindings[{index}] fact_ids must be unique")
        if any(not item or item not in known_facts for item in normalized_ids):
            unknown = sorted({item for item in normalized_ids if item not in known_facts})
            raise EvidenceBridgeError(f"bindings[{index}] references unknown fact IDs: {unknown}")
        use, presentation = _normalize_presentation(raw_binding, index)
        disallowed = [fact_id for fact_id in normalized_ids if use not in known_facts[fact_id]["allowed_uses"]]
        if disallowed:
            raise EvidenceBridgeError(f"bindings[{index}] use={use} is not allowed for facts: {disallowed}")
        target = (node_id, presentation["target_field"])
        if target in targets:
            raise EvidenceBridgeError(
                f"bindings[{index}] duplicates materialization target {node_id}.{presentation['target_field']}"
            )
        targets.add(target)
        selected.update(normalized_ids)
        bindings.append(
            {
                "node_id": node_id,
                "fact_ids": normalized_ids,
                "use": use,
                "presentation": presentation,
            }
        )
    return bindings, selected


def bind_schematic_evidence(
    candidate_dir: str | Path,
    bundle_path: str | Path,
    mapping: str | Path | dict[str, Any],
) -> dict[str, Any]:
    """Snapshot aggregate evidence and bind selected fact IDs to schematic nodes."""

    candidate = Path(candidate_dir).resolve()
    if not candidate.is_dir():
        raise FileNotFoundError(candidate)
    source_bundle = Path(bundle_path).resolve()
    bundle = load_data_evidence_bundle(source_bundle)
    raw_mapping = _read_object(Path(mapping)) if isinstance(mapping, (str, Path)) else dict(mapping)
    known_facts = {item["id"]: item for item in bundle["facts"]}
    known_nodes: set[str] | None = None
    for name in ("blueprint_ir.refined.json", "blueprint_ir.json", "figure_spec.json", "annotation_layout.json"):
        spec_path = candidate / name
        if spec_path.is_file():
            payload = _read_object(spec_path)
            raw_nodes = payload.get("annotations", []) if name == "annotation_layout.json" else payload.get("nodes", [])
            known_nodes = {
                str(item.get("id"))
                for item in raw_nodes
                if isinstance(item, dict) and item.get("id")
            }
            break
    bindings, selected = _normalize_bindings(
        raw_mapping.get("bindings"),
        known_facts,
        known_nodes=known_nodes,
    )

    snapshot = candidate / "data_evidence_bundle.json"
    if source_bundle != snapshot:
        shutil.copyfile(source_bundle, snapshot)
    binding = {
        "schema": EVIDENCE_BINDING_SCHEMA,
        "schema_version": EVIDENCE_BINDING_VERSION,
        "status": "PASS",
        "source_bundle": str(source_bundle),
        "bundle_snapshot": snapshot.name,
        "bundle_sha256": _sha256(snapshot),
        "aggregate_only": True,
        "materialization_policy": "exact-display-text",
        "bindings": bindings,
        "selected_facts": [known_facts[fact_id] for fact_id in sorted(selected)],
        "scientific_limits": bundle["scientific_limits"],
    }
    target = candidate / "schematic_evidence_binding.json"
    _write_object(target, binding)
    return {
        "status": "PASS",
        "binding": str(target),
        "bundle_snapshot": str(snapshot),
        "binding_count": len(bindings),
        "selected_fact_count": len(selected),
        "aggregate_only": True,
    }


def validate_schematic_evidence_binding(candidate_dir: str | Path, spec: dict[str, Any]) -> dict[str, Any]:
    """Validate a candidate-local evidence binding against its FigureSpec nodes."""

    candidate = Path(candidate_dir).resolve()
    binding_path = candidate / "schematic_evidence_binding.json"
    if not binding_path.is_file():
        return {"status": "NOT_APPLICABLE", "used": False, "binding_count": 0, "selected_facts": []}
    binding = _read_object(binding_path)
    if binding.get("schema") != EVIDENCE_BINDING_SCHEMA or str(binding.get("schema_version")) != EVIDENCE_BINDING_VERSION:
        raise EvidenceBridgeError("unsupported schematic evidence binding contract")
    if binding.get("aggregate_only") is not True:
        raise EvidenceBridgeError("schematic evidence binding must remain aggregate-only")
    snapshot = candidate / str(binding.get("bundle_snapshot") or "")
    if not snapshot.is_file() or _sha256(snapshot) != str(binding.get("bundle_sha256") or ""):
        raise EvidenceBridgeError("schematic evidence bundle snapshot is missing or changed")
    bundle = load_data_evidence_bundle(snapshot)
    known_facts = {item["id"]: item for item in bundle["facts"]}
    known_nodes = {str(item.get("id")) for item in spec.get("nodes", []) if isinstance(item, dict)}
    bindings, selected = _normalize_bindings(binding.get("bindings"), known_facts, known_nodes=known_nodes)
    selected_facts = [known_facts[fact_id] for fact_id in sorted(selected)]
    stored_facts = binding.get("selected_facts")
    if stored_facts != selected_facts:
        raise EvidenceBridgeError("schematic evidence binding selected_facts no longer match the bundle snapshot")
    return {
        "status": "PASS",
        "used": True,
        "binding_file": binding_path.name,
        "bundle_snapshot": snapshot.name,
        "bundle_sha256": binding["bundle_sha256"],
        "binding_count": len(bindings),
        "selected_fact_count": len(selected_facts),
        "bindings": bindings,
        "selected_facts": selected_facts,
        "scientific_limits": bundle["scientific_limits"],
        "aggregate_only": True,
    }


def materialize_schematic_evidence(
    candidate_dir: str | Path,
    spec: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Resolve bound facts into live FigureSpec text without recomputing or paraphrasing values."""

    resolved = deepcopy(spec)
    report = validate_schematic_evidence_binding(candidate_dir, resolved)
    if not report["used"]:
        return resolved, {**report, "materialized": False, "materialization_count": 0, "materializations": []}
    nodes = {str(item.get("id")): item for item in resolved.get("nodes", []) if isinstance(item, dict)}
    facts = {item["id"]: item for item in report["selected_facts"]}
    materializations: list[dict[str, Any]] = []
    for binding in report["bindings"]:
        presentation = binding["presentation"]
        target_field = presentation["target_field"]
        fact_text = presentation["separator"].join(facts[fact_id]["display_text"] for fact_id in binding["fact_ids"])
        rendered_text = f"{presentation['prefix']}{fact_text}{presentation['suffix']}"
        node = nodes[binding["node_id"]]
        before = str(node.get(target_field) or "")
        node[target_field] = rendered_text
        node[f"{target_field}_max_lines"] = presentation["max_lines"]
        materializations.append(
            {
                "node_id": binding["node_id"],
                "target_field": target_field,
                "use": binding["use"],
                "fact_ids": list(binding["fact_ids"]),
                "rendered_text": rendered_text,
                "changed": before != rendered_text,
            }
        )
    return resolved, {
        **report,
        "materialized": True,
        "materialization_policy": "exact-display-text",
        "materialization_count": len(materializations),
        "materializations": materializations,
    }


def validate_materialized_evidence_svg(svg_path: str | Path, evidence_report: dict[str, Any]) -> dict[str, Any]:
    """Prove that every materialized evidence string survived into live SVG text."""

    if not evidence_report.get("used"):
        return {"status": "NOT_APPLICABLE", "verified": True, "checked_binding_count": 0, "failures": []}
    path = Path(svg_path)
    if not path.is_file():
        raise FileNotFoundError(path)
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError as exc:
        raise EvidenceBridgeError(f"invalid SVG while validating materialized evidence: {exc}") from exc
    by_id = {str(element.get("id")): element for element in root.iter() if element.get("id")}
    failures: list[str] = []
    for item in evidence_report.get("materializations", []):
        node_id = str(item.get("node_id") or "")
        node = by_id.get(node_id)
        if node is None:
            failures.append(f"missing SVG node group: {node_id}")
            continue
        visible_raw = "".join(node.itertext())
        expected_raw = str(item.get("rendered_text") or "")
        visible = " ".join(" ".join(node.itertext()).split())
        expected = " ".join(expected_raw.split())
        visible_compact = re.sub(r"\s+", "", visible_raw)
        expected_compact = re.sub(r"\s+", "", expected_raw)
        if expected not in visible and expected_compact not in visible_compact:
            failures.append(f"materialized evidence text was clipped or changed in SVG node: {node_id}")
    return {
        "status": "PASS" if not failures else "FAIL",
        "verified": not failures,
        "checked_binding_count": len(evidence_report.get("materializations", [])),
        "failures": failures,
    }
