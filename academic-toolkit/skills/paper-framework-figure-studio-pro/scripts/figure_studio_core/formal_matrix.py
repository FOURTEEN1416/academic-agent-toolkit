"""Generic S4/S5 formal candidate matrix helpers for v3.2.15f.

The helpers are deliberately paper-agnostic. They do not assume a paper topic,
candidate id family, fixed page count, or fixed style count. Candidate coverage
is derived from S3-recorded user preference signals plus the style/treatment
slots that S4 declares for the second-round candidate matrix.

v3.2.15f two-candidate policy: S5 second-round/formal candidates have an
absolute public cap of ``MAX_SECOND_ROUND_CANDIDATES``. The default two
candidates are the complete formal set. If preferred-source × style coverage
cannot fit, S4 must repair/replan or redo the candidate brief before S5 handoff.
"""

from __future__ import annotations

from typing import Any, Iterable

from .constants import MAX_SECOND_ROUND_CANDIDATES

DEFAULT_VISUAL_TREATMENTS = [
    "Balanced overview",
    "Mechanism/detail refinement",
]


def _unique_nonempty(values: Iterable[Any] | None) -> list[str]:
    result: list[str] = []
    if not values:
        return result
    for value in values:
        text = str(value).strip()
        if text and text not in result:
            result.append(text)
    return result


def _effective_second_round_cap(max_count: int | None = None) -> int:
    """Return the active second-round cap, never above the skill cap."""
    cap = MAX_SECOND_ROUND_CANDIDATES
    if max_count is not None:
        if max_count < 1:
            raise ValueError("max_count must be >= 1")
        cap = min(cap, max_count)
    return cap


def normalize_style_slots(style_slots: Iterable[Any] | None) -> list[dict[str, str]]:
    """Normalize arbitrary S4 style/treatment slots.

    A slot may be a string or a dict containing style_id/style_label/label/name.
    The result preserves order and never assumes a fixed style vocabulary.
    """
    normalized: list[dict[str, str]] = []
    seen: set[str] = set()
    for index, slot in enumerate(style_slots or []):
        if isinstance(slot, dict):
            style_id = str(slot.get("style_id") or slot.get("id") or slot.get("name") or f"style-{index+1:02d}").strip()
            style_label = str(slot.get("style_label") or slot.get("label") or slot.get("name") or style_id).strip()
            treatment = str(slot.get("visual_treatment") or slot.get("treatment") or style_label).strip()
        else:
            style_id = str(slot).strip() or f"style-{index+1:02d}"
            style_label = style_id
            treatment = style_id
        if not style_id:
            style_id = f"style-{index+1:02d}"
        if style_id in seen:
            continue
        seen.add(style_id)
        normalized.append({"style_id": style_id, "style_label": style_label or style_id, "visual_treatment": treatment or style_id})
    return normalized


def formal_candidate_id(index: int, prefix: str = "F") -> str:
    return f"{prefix}{index:02d}"


def generate_formal_candidate_matrix(
    default_count: int = 2,
    visual_treatments: Iterable[str] | None = None,
    *,
    id_prefix: str = "F",
    selected_direction_count: int | None = None,
    preferred_first_round_candidate_ids: Iterable[Any] | None = None,
    style_families: Iterable[Any] | None = None,
    max_count: int | None = None,
) -> list[dict[str, Any]]:
    """Generate paper-agnostic S4 formal candidates.

    No paper-specific module names, datasets, claims, project paths, candidate
    ids, or image counts are encoded. For S5, however, v3.2.15f imposes a
    two-candidate cap through ``MAX_SECOND_ROUND_CANDIDATES``.
    """
    cap = _effective_second_round_cap(max_count)
    if default_count < 1:
        raise ValueError("default_count must be >= 1")
    if default_count > cap:
        raise ValueError(
            f"default_count={default_count} exceeds the S5 second-round cap={cap}; "
            "redo S4 candidate planning with at most the configured cap."
        )
    if preferred_first_round_candidate_ids:
        slots = normalize_style_slots(style_families) if style_families is not None else normalize_style_slots(visual_treatments or DEFAULT_VISUAL_TREATMENTS)
        rows = generate_preference_covered_formal_candidate_matrix(
            preferred_source_ids=preferred_first_round_candidate_ids,
            style_slots=slots,
            default_count=default_count,
            max_count=cap,
            filler_visual_treatments=visual_treatments,
            id_prefix=id_prefix,
            selected_direction_count=selected_direction_count,
        )
        report = preference_coverage_report(
            rows,
            preferred_source_ids=preferred_first_round_candidate_ids,
            style_slots=slots,
            max_count=cap,
        )
        if rows:
            rows[0]["preference_carryover_coverage_audit"] = report
        return rows

    treatments = list(visual_treatments or DEFAULT_VISUAL_TREATMENTS)
    if not treatments:
        treatments = DEFAULT_VISUAL_TREATMENTS
    candidates: list[dict[str, Any]] = []
    for i in range(default_count):
        candidates.append(
            {
                "candidate_id": formal_candidate_id(i + 1, id_prefix),
                "matrix_index": i + 1,
                "selected_direction_slot": (i % selected_direction_count) + 1 if selected_direction_count else None,
                "visual_treatment": treatments[i % len(treatments)],
                "paper_binding": "none_generic_treatment_only",
                "preference_coverage_role": "not_preference_led",
                "lineage_role": "direction_refinement_candidate",
                "source_first_round_candidate_id": None,
                "dominant_source_candidate_id": None,
                "s2_reference_source_candidate_ids": [],
                "style_id": None,
                "style_family": None,
                "second_round_candidate_cap": cap,
            }
        )
    return candidates


def required_preference_style_pairs(
    preferred_source_ids: Iterable[Any] | None,
    style_slots: Iterable[Any] | None,
) -> list[dict[str, str]]:
    """Return the required preference × style coverage pairs.

    If no explicit style slots are supplied, one generic selected-direction style
    slot is used so each preferred first-round source still receives at least one
    second-round local-essence candidate.
    """
    preferred = _unique_nonempty(preferred_source_ids)
    if not preferred:
        return []
    slots = normalize_style_slots(style_slots) or [
        {
            "style_id": "selected_direction_default",
            "style_label": "selected direction default",
            "visual_treatment": "Selected-direction local essence",
        }
    ]
    pairs: list[dict[str, str]] = []
    for source_id in preferred:
        for slot in slots:
            pairs.append({"source_first_round_candidate_id": source_id, **slot})
    return pairs


def generate_preference_covered_formal_candidate_matrix(
    *,
    preferred_source_ids: Iterable[Any] | None,
    style_slots: Iterable[Any] | None,
    default_count: int = 2,
    max_count: int | None = None,
    filler_visual_treatments: Iterable[str] | None = None,
    id_prefix: str = "F",
    selected_direction_count: int | None = None,
) -> list[dict[str, Any]]:
    """Generate an S5 matrix with mandatory preferred-source coverage.

    When S3 records user-preferred first-round candidate IDs, S4 must provide at
    least one second-round local-essence candidate led by each preferred source
    for each active S5 style/treatment slot. S4 may expand beyond the default
    count only up to the configured S5 second-round cap. If the required pair
    count exceeds that cap, this helper raises ``ValueError`` so S4 can repair
    the style-slot plan or redo before S5 handoff.
    """
    cap = _effective_second_round_cap(max_count)
    pairs = required_preference_style_pairs(preferred_source_ids, style_slots)
    if not pairs:
        return generate_formal_candidate_matrix(
            default_count=default_count,
            visual_treatments=filler_visual_treatments,
            id_prefix=id_prefix,
            selected_direction_count=selected_direction_count,
            max_count=cap,
        )
    if len(pairs) > cap:
        raise ValueError(
            f"required preference×style rows={len(pairs)} exceed the S5 second-round cap={cap}; "
            "redo S4 with a feasible two-candidate style-slot allocation or ask the user to narrow preferences/styles before S5."
        )
    if default_count < 1:
        raise ValueError("default_count must be >= 1")
    if default_count > cap:
        raise ValueError(
            f"default_count={default_count} exceeds the S5 second-round cap={cap}; "
            "redo S4 candidate planning with at most the configured cap."
        )
    total_count = max(default_count, len(pairs))
    rows: list[dict[str, Any]] = []
    for index, pair in enumerate(pairs, start=1):
        rows.append(
            {
                "candidate_id": formal_candidate_id(index, id_prefix),
                "matrix_index": index,
                "selected_direction_slot": (index - 1) % selected_direction_count + 1 if selected_direction_count else None,
                "visual_treatment": pair["visual_treatment"],
                "style_id": pair["style_id"],
                "style_label": pair["style_label"],
                "source_first_round_candidate_id": pair["source_first_round_candidate_id"],
                "dominant_source_candidate_id": pair["source_first_round_candidate_id"],
                "s2_reference_source_candidate_ids": [pair["source_first_round_candidate_id"]],
                "preference_coverage_role": "preferred_first_round_local_essence_lead",
                "lineage_role": "preference_led_local_essence_refinement",
                "style_family": pair["style_id"],
                "paper_binding": "source_first_round_candidate_is_visual_preference_signal_only",
                "second_round_candidate_cap": cap,
                "design_contract": (
                    "Lead with the local essence of the named first-round candidate while preserving the "
                    "S3 selected direction, source-grounded module semantics, and S4 prompt contract."
                ),
            }
        )
    filler_treatments = list(filler_visual_treatments or DEFAULT_VISUAL_TREATMENTS)
    if not filler_treatments:
        filler_treatments = DEFAULT_VISUAL_TREATMENTS
    while len(rows) < total_count:
        index = len(rows) + 1
        treatment = filler_treatments[(index - 1) % len(filler_treatments)]
        rows.append(
            {
                "candidate_id": formal_candidate_id(index, id_prefix),
                "matrix_index": index,
                "selected_direction_slot": (index - 1) % selected_direction_count + 1 if selected_direction_count else None,
                "visual_treatment": treatment,
                "style_id": None,
                "style_label": None,
                "source_first_round_candidate_id": None,
                "dominant_source_candidate_id": None,
                "s2_reference_source_candidate_ids": [],
                "preference_coverage_role": "non_preference_direction_synthesis",
                "lineage_role": "direction_refinement_candidate",
                "style_family": None,
                "paper_binding": "selected_direction_synthesis",
                "second_round_candidate_cap": cap,
            }
        )
    return rows


def preference_coverage_report(
    matrix_rows: Iterable[dict[str, Any]],
    *,
    preferred_source_ids: Iterable[Any] | None,
    style_slots: Iterable[Any] | None,
    max_count: int | None = None,
) -> dict[str, Any]:
    """Validate that a matrix satisfies preferred-source × style coverage and cap."""
    cap = _effective_second_round_cap(max_count)
    rows_list = [row for row in matrix_rows if isinstance(row, dict)]
    required_pairs = required_preference_style_pairs(preferred_source_ids, style_slots)
    required = {
        (pair["source_first_round_candidate_id"], pair["style_id"]): pair
        for pair in required_pairs
    }
    covered: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows_list:
        source_id = row.get("source_first_round_candidate_id") or row.get("dominant_source_candidate_id") or row.get("preference_source_candidate_id")
        style_id = row.get("style_id") or row.get("style_family") or row.get("style_slot_id")
        role = str(row.get("preference_coverage_role") or row.get("lineage_role") or "")
        if not source_id or not style_id:
            continue
        key = (str(source_id), str(style_id))
        if key in required and "local_essence" in role:
            covered[key] = row
    missing = [pair for key, pair in required.items() if key not in covered]
    over_candidate_cap = len(rows_list) > cap
    infeasible_required_pairs = len(required_pairs) > cap
    status = "PASS" if not missing and not over_candidate_cap and not infeasible_required_pairs else "FAIL"
    return {
        "schema_version": 2,
        "status": status,
        "redo_required": status != "PASS",
        "candidate_count": len(rows_list),
        "max_second_round_candidate_count": cap,
        "over_candidate_cap": over_candidate_cap,
        "required_pair_count": len(required_pairs),
        "covered_pair_count": len(covered),
        "missing_pair_count": len(missing),
        "infeasible_required_pairs": infeasible_required_pairs,
        "missing_pairs": missing,
        "cap_policy": "Second-round/S5 formal candidates must never exceed the configured two-candidate cap; repair/replan or redo S4 if coverage cannot fit.",
        "non_hardcoding_statement": "Coverage derives from S3-recorded preference ids and S4-declared style slots; no paper topic, project-specific ids, fixed page count, or domain terms are hard-coded. The only fixed count is the skill-level public S5 cap.",
    }
