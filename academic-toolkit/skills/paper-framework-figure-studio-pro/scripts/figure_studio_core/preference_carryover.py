"""Generic first-round preference carryover helpers for v3.2.15f.

The functions in this module are deliberately paper-agnostic. They do not know
paper topics, project IDs, candidate counts, or fixed candidate IDs. They derive
preference coverage from S3 records, candidate rows, prompt-index rows, and
style-family metadata supplied by the current project run.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Iterable

from .constants import MAX_SECOND_ROUND_CANDIDATES

ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
DEFAULT_STYLE_FAMILY = "default_formal_candidate_style"
PREFERENCE_LINEAGE_ROLE = "preference_led_local_essence_refinement"


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    return [value]


def normalize_candidate_id(value: Any) -> str:
    text = str(value).strip()
    if not ID_RE.match(text):
        raise ValueError(f"unsafe or empty candidate id: {value!r}")
    return text


def normalize_style_family(value: Any) -> str:
    text = str(value).strip() if value is not None else ""
    if not text:
        text = DEFAULT_STYLE_FAMILY
    # Keep style names readable but filesystem/prompt-index safe enough for JSON.
    text = re.sub(r"\s+", "_", text)
    text = re.sub(r"[^A-Za-z0-9_.:/@+-]", "_", text)
    return text or DEFAULT_STYLE_FAMILY


def dedupe_preserve_order(values: Iterable[Any]) -> list[str]:
    result: list[str] = []
    for value in values:
        if value is None:
            continue
        try:
            text = normalize_candidate_id(value)
        except ValueError:
            continue
        if text not in result:
            result.append(text)
    return result


def extract_preferred_candidate_ids(*records: Any) -> list[str]:
    """Extract user-preferred first-round candidate IDs from generic records.

    Supported generic field names include:
    - user_preferred_first_round_candidate_ids
    - preferred_first_round_candidate_ids
    - user_preference_candidate_ids
    - preferred_candidate_ids
    - preference_signals.preferred_candidate_ids
    - user_preference_signal.candidate_ids

    This intentionally avoids looking for paper-specific words.
    """
    found: list[Any] = []

    def walk(value: Any) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                key_norm = str(key).lower()
                if key_norm in {
                    "user_preferred_first_round_candidate_ids",
                    "preferred_first_round_candidate_ids",
                    "user_preference_candidate_ids",
                    "preferred_candidate_ids",
                    "candidate_ids_preferred_by_user",
                }:
                    found.extend(_as_list(child))
                elif key_norm in {"preference_signals", "user_preference_signal", "user_preferences"}:
                    walk(child)
                else:
                    walk(child)
        elif isinstance(value, list):
            for child in value:
                walk(child)

    for record in records:
        walk(record)
    return dedupe_preserve_order(found)


def load_json(path: str | Path) -> Any:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def style_families_from_rows(rows: Iterable[dict[str, Any]], *, default: str = DEFAULT_STYLE_FAMILY) -> list[str]:
    """Derive active style families from candidate/prompt rows.

    Reads common generic fields only. If no style is declared, returns one
    default style family so preference coverage still applies once.
    """
    styles: list[str] = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        for field in ("style_family", "style_id", "surface_style", "visual_style", "visual_treatment"):
            if row.get(field):
                styles.append(normalize_style_family(row[field]))
                break
    if not styles:
        styles = [default]
    # Dedupe while preserving order.
    result: list[str] = []
    for style in styles:
        if style not in result:
            result.append(style)
    return result


def required_preference_pairs(preferred_candidate_ids: Iterable[str], style_families: Iterable[str]) -> list[dict[str, str]]:
    pairs: list[dict[str, str]] = []
    for pref in dedupe_preserve_order(preferred_candidate_ids):
        for style in [normalize_style_family(s) for s in style_families]:
            pairs.append({"dominant_source_candidate_id": pref, "style_family": style})
    return pairs


def row_satisfies_pair(row: dict[str, Any], pair: dict[str, str]) -> bool:
    if not isinstance(row, dict):
        return False
    role_values = {
        str(row.get("lineage_role") or ""),
        str(row.get("source_lineage_role") or ""),
        str(row.get("preference_coverage_role") or ""),
    }
    preference_led = (
        PREFERENCE_LINEAGE_ROLE in role_values
        or "preferred_first_round_local_essence_lead" in role_values
        or bool(row.get("preference_led_local_exemplar"))
        or bool(row.get("preference_carryover_required"))
    )
    dominant_values: list[str] = []
    for field in (
        "dominant_source_candidate_id",
        "dominant_first_round_candidate_id",
        "source_first_round_candidate_id",
        "preference_source_candidate_id",
        "source_lead",
        "lead_source_candidate_id",
    ):
        value = row.get(field)
        if value:
            dominant_values.append(str(value))
    for field in ("source_candidate_ids", "source_first_round_candidate_ids", "source_leads"):
        value = row.get(field)
        if isinstance(value, list):
            dominant_values.extend(str(v) for v in value if v)
    style = normalize_style_family(row.get("style_family") or row.get("style_id") or row.get("style_slot_id") or row.get("surface_style") or row.get("visual_style") or row.get("visual_treatment"))
    return (
        preference_led
        and pair["dominant_source_candidate_id"] in dominant_values
        and style == pair["style_family"]
    )


def preference_coverage_audit(
    rows: Iterable[dict[str, Any]],
    preferred_candidate_ids: Iterable[str] | None = None,
    style_families: Iterable[str] | None = None,
    *,
    max_second_round_candidates: int = MAX_SECOND_ROUND_CANDIDATES,
) -> dict[str, Any]:
    rows_list = [row for row in rows if isinstance(row, dict)]
    preferred = dedupe_preserve_order(preferred_candidate_ids or [])
    styles = [normalize_style_family(s) for s in (style_families or style_families_from_rows(rows_list))]
    pairs = required_preference_pairs(preferred, styles)
    satisfied: list[dict[str, str]] = []
    missing: list[dict[str, str]] = []
    for pair in pairs:
        match = next((row for row in rows_list if row_satisfies_pair(row, pair)), None)
        if match:
            satisfied.append({**pair, "candidate_id": str(match.get("candidate_id", ""))})
        else:
            missing.append(pair)
    over_candidate_cap = len(rows_list) > max_second_round_candidates
    infeasible_required_pairs = len(pairs) > max_second_round_candidates
    status = "PASS" if not missing and not over_candidate_cap and not infeasible_required_pairs else "FAIL"
    return {
        "schema_version": 2,
        "policy": "preferred-first-round-carryover-policy-v3215d-max2",
        "preferred_first_round_candidate_ids": preferred,
        "active_style_families": styles,
        "candidate_count": len(rows_list),
        "max_second_round_candidate_count": max_second_round_candidates,
        "over_candidate_cap": over_candidate_cap,
        "required_pair_count": len(pairs),
        "satisfied_pair_count": len(satisfied),
        "missing_pair_count": len(missing),
        "infeasible_required_pairs": infeasible_required_pairs,
        "satisfied_pairs": satisfied,
        "missing_pairs": missing,
        "status": status,
        "redo_required": status != "PASS",
        "cap_policy": "S5 second-round/formal candidate rows must never exceed the configured two-candidate cap; repair/replan or redo S4 if preference/style coverage cannot fit.",
        "non_hardcoding_statement": "Preference IDs and style families were derived from supplied records/rows; no project, paper, fixed ID list, page count, or file-name assumptions were used. The only fixed count is the skill-level public S5 cap of two.",
    }


def next_candidate_id(existing_rows: Iterable[dict[str, Any]], prefix: str = "F") -> str:
    max_num = 0
    pattern = re.compile(rf"^{re.escape(prefix)}(\d+)$")
    for row in existing_rows:
        cid = str(row.get("candidate_id", "")) if isinstance(row, dict) else ""
        m = pattern.match(cid)
        if m:
            max_num = max(max_num, int(m.group(1)))
    return f"{prefix}{max_num + 1:02d}"


def ensure_preference_carryover_rows(
    rows: Iterable[dict[str, Any]],
    preferred_candidate_ids: Iterable[str] | None = None,
    style_families: Iterable[str] | None = None,
    *,
    id_prefix: str = "F",
    max_second_round_candidates: int = MAX_SECOND_ROUND_CANDIDATES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return rows plus any missing preference-led local-refinement rows.

    Existing compliant rows are reused. Missing coverage pairs get appended with
    new generic candidate IDs. The caller can then fill prompt_path and
    target_image_path according to its normal prompt-index builder.
    """
    result = [dict(row) for row in rows if isinstance(row, dict)]
    preferred = dedupe_preserve_order(preferred_candidate_ids or [])
    if not preferred:
        audit = preference_coverage_audit(result, [], style_families or style_families_from_rows(result))
        audit["status"] = "PASS"
        audit["note"] = "No user-preferred first-round candidate IDs were recorded; no carryover rows required."
        return result, audit
    styles = [normalize_style_family(s) for s in (style_families or style_families_from_rows(result))]
    required_pairs = required_preference_pairs(preferred, styles)
    if len(required_pairs) > max_second_round_candidates:
        audit = preference_coverage_audit(
            result, preferred, styles, max_second_round_candidates=max_second_round_candidates
        )
        audit["status"] = "FAIL"
        audit["redo_required"] = True
        audit["reason"] = "preference_style_coverage_exceeds_second_round_cap"
        audit["instruction"] = "Redo S4 with a feasible active style-slot allocation or ask the user to narrow preferences/styles; never create more than the two S5 candidates."
        return result, audit
    for pair in required_pairs:
        if any(row_satisfies_pair(row, pair) for row in result):
            continue
        if len(result) >= max_second_round_candidates:
            break
        cid = next_candidate_id(result, id_prefix)
        result.append(
            {
                "candidate_id": cid,
                "matrix_index": len(result) + 1,
                "visual_treatment": f"Preference-led local essence refinement ({pair['style_family']})",
                "style_family": pair["style_family"],
                "lineage_role": PREFERENCE_LINEAGE_ROLE,
                "dominant_source_candidate_id": pair["dominant_source_candidate_id"],
                "paper_binding": "source_grounded_prompt_required_current_project_only",
                "preference_carryover_required": True,
            }
        )
    audit = preference_coverage_audit(result, preferred, styles, max_second_round_candidates=max_second_round_candidates)
    return result, audit


# Compatibility helpers used by figure_studio_preference_carryover_guard.py
def read_json(path: str | Path) -> Any:
    return load_json(path)


def preference_ids_from_sources(paths: Iterable[str | Path]) -> list[str]:
    records: list[Any] = []
    for path in paths:
        p = Path(path)
        if p.is_file():
            try:
                records.append(load_json(p))
            except Exception:
                continue
    return extract_preferred_candidate_ids(*records)


def parse_markdown_table(path: str | Path) -> list[dict[str, Any]]:
    text = Path(path).read_text(encoding="utf-8")
    rows: list[dict[str, Any]] = []
    lines = [line.strip() for line in text.splitlines() if line.strip().startswith("|") and line.strip().endswith("|")]
    if len(lines) < 2:
        return rows
    header = [cell.strip() for cell in lines[0].strip("|").split("|")]
    for line in lines[2:]:
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        if len(cells) != len(header):
            continue
        rows.append({header[i]: cells[i] for i in range(len(header))})
    return rows


def _rows_from_prompt_index(prompt_index: Any) -> list[dict[str, Any]]:
    if isinstance(prompt_index, list):
        return [row for row in prompt_index if isinstance(row, dict)]
    if isinstance(prompt_index, dict):
        rows = prompt_index.get("candidates") or prompt_index.get("rows") or prompt_index.get("formal_candidates")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
        cmap = prompt_index.get("candidate_map")
        if isinstance(cmap, dict):
            return [row for row in cmap.values() if isinstance(row, dict)]
    return []


def validate_preference_carryover(
    prompt_index: Any,
    preferred_candidate_ids: Iterable[str] | None = None,
    *,
    prompt_root: str | Path | None = None,
    matrix_rows: Iterable[dict[str, Any]] | None = None,
    max_second_round_candidates: int = MAX_SECOND_ROUND_CANDIDATES,
) -> dict[str, Any]:
    rows = list(matrix_rows or []) + _rows_from_prompt_index(prompt_index)
    styles = style_families_from_rows(rows)
    report = preference_coverage_audit(
        rows, preferred_candidate_ids or [], styles, max_second_round_candidates=max_second_round_candidates
    )
    report["prompt_row_count"] = len(_rows_from_prompt_index(prompt_index))
    report["matrix_row_count"] = len(list(matrix_rows or []))
    report["prompt_root"] = str(prompt_root) if prompt_root is not None else None
    return report
