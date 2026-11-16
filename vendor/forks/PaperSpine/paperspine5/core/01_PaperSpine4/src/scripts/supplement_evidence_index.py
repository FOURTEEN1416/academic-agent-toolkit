#!/usr/bin/env python3
"""Fail-closed checker for main-text, supplement, and upload-package links."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "1.0"
KINDS = {"figure", "table", "data", "method", "note"}
SEMANTIC_STATES = {"pass", "blocked"}
INVENTORY_STATES = {"ready", "needs_author", "not_applicable"}
SHA256_RE = re.compile(r"^[0-9A-Fa-f]{64}$")


class SupplementIndexError(ValueError):
    """Raised when the index itself is structurally unusable."""


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _safe_path(root: Path, raw: Any, label: str, blockers: list[str]) -> Path | None:
    if not isinstance(raw, str) or not raw.strip():
        blockers.append(f"{label}: path is required")
        return None
    candidate = (root / raw).resolve() if not Path(raw).is_absolute() else Path(raw).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        blockers.append(f"{label}: path escapes package_root: {raw}")
        return None
    if not candidate.is_file():
        blockers.append(f"{label}: file does not exist: {raw}")
        return None
    return candidate


def _file_entry(
    root: Path, entry: Any, label: str, blockers: list[str]
) -> Path | None:
    if not isinstance(entry, dict):
        blockers.append(f"{label}: file entry must be an object")
        return None
    path = _safe_path(root, entry.get("path"), label, blockers)
    expected = str(entry.get("sha256") or "")
    if not SHA256_RE.fullmatch(expected):
        blockers.append(f"{label}: sha256 must contain 64 hexadecimal characters")
    elif path is not None:
        observed = _sha256(path)
        if observed != expected.upper():
            blockers.append(f"{label}: sha256 mismatch; expected {expected.upper()}, observed {observed}")
    return path


def _text(path: Path | None, label: str, blockers: list[str]) -> str:
    if path is None:
        return ""
    try:
        return path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        blockers.append(f"{label}: expected UTF-8 text")
        return ""


def check_index(payload: dict[str, Any], index_path: Path) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SupplementIndexError("index must be a JSON object")
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SupplementIndexError(f"schema_version must be {SCHEMA_VERSION}")
    raw_root = payload.get("package_root", ".")
    if not isinstance(raw_root, str):
        raise SupplementIndexError("package_root must be a string")
    root = ((index_path.parent / raw_root).resolve() if not Path(raw_root).is_absolute() else Path(raw_root).resolve())
    if not root.is_dir():
        raise SupplementIndexError(f"package_root is not a directory: {root}")

    blockers: list[str] = []
    warnings: list[str] = []
    main_path = _file_entry(root, payload.get("main_manuscript"), "main_manuscript", blockers)
    supplement_path = _file_entry(
        root, payload.get("supplementary_material"), "supplementary_material", blockers
    )
    main_text = _text(main_path, "main_manuscript", blockers)
    supplement_text = _text(supplement_path, "supplementary_material", blockers)

    raw_claims = payload.get("claims")
    if not isinstance(raw_claims, list) or not raw_claims:
        blockers.append("claims: at least one claim is required")
        raw_claims = []
    claims: dict[str, dict[str, Any]] = {}
    for index, claim in enumerate(raw_claims):
        label = f"claims[{index}]"
        if not isinstance(claim, dict):
            blockers.append(f"{label}: must be an object")
            continue
        claim_id = str(claim.get("claim_id") or "")
        if not claim_id or claim_id in claims:
            blockers.append(f"{label}: claim_id must be non-empty and unique")
            continue
        locator = str(claim.get("main_text_locator") or "")
        if not locator:
            blockers.append(f"{label}: main_text_locator is required")
        elif locator not in main_text:
            blockers.append(f"{label}: main_text_locator not found: {locator}")
        claims[claim_id] = claim

    raw_items = payload.get("items")
    if not isinstance(raw_items, list) or not raw_items:
        blockers.append("items: at least one supplementary evidence item is required")
        raw_items = []
    item_ids: set[str] = set()
    covered_claims: set[str] = set()
    item_results: list[dict[str, Any]] = []
    for index, item in enumerate(raw_items):
        label = f"items[{index}]"
        before = len(blockers)
        if not isinstance(item, dict):
            blockers.append(f"{label}: must be an object")
            continue
        supplement_id = str(item.get("supplement_id") or "")
        if not supplement_id or supplement_id in item_ids:
            blockers.append(f"{label}: supplement_id must be non-empty and unique")
        else:
            item_ids.add(supplement_id)
        if item.get("kind") not in KINDS:
            blockers.append(f"{label}: kind must be one of {sorted(KINDS)}")
        if not str(item.get("scientific_role") or "").strip():
            blockers.append(f"{label}: scientific_role is required")

        supported = item.get("supported_claim_ids")
        if not isinstance(supported, list) or not supported:
            blockers.append(f"{label}: supported_claim_ids must be non-empty")
            supported = []
        for claim_id in supported:
            if claim_id not in claims:
                blockers.append(f"{label}: unknown supported claim: {claim_id}")
            else:
                covered_claims.add(claim_id)

        main_locators = item.get("main_text_locators")
        if not isinstance(main_locators, list) or not main_locators:
            blockers.append(f"{label}: main_text_locators must be non-empty")
        else:
            for locator in main_locators:
                if not isinstance(locator, str) or locator not in main_text:
                    blockers.append(f"{label}: main-text locator not found: {locator}")

        supplement_locators = item.get("supplement_locators")
        if not isinstance(supplement_locators, list) or not supplement_locators:
            blockers.append(f"{label}: supplement_locators must be non-empty")
        else:
            for locator in supplement_locators:
                if not isinstance(locator, str) or locator not in supplement_text:
                    blockers.append(f"{label}: supplement locator not found: {locator}")

        _file_entry(root, item.get("publication_asset"), f"{label}.publication_asset", blockers)
        _file_entry(root, item.get("upload_artifact"), f"{label}.upload_artifact", blockers)
        semantic = item.get("semantic_validation")
        if not isinstance(semantic, dict):
            blockers.append(f"{label}: semantic_validation is required")
        else:
            state = semantic.get("status")
            if state not in SEMANTIC_STATES:
                blockers.append(f"{label}: semantic_validation.status must be pass or blocked")
            elif state != "pass":
                blockers.append(f"{label}: semantic validation is blocked")
            for key in ("rendered_surface_summary", "caption_summary"):
                if not str(semantic.get(key) or "").strip():
                    blockers.append(f"{label}: semantic_validation.{key} is required")
            _file_entry(
                root,
                semantic.get("review_receipt"),
                f"{label}.semantic_validation.review_receipt",
                blockers,
            )
        item_results.append(
            {
                "supplement_id": supplement_id,
                "valid": len(blockers) == before,
                "supported_claim_ids": list(supported),
            }
        )

    for claim_id, claim in claims.items():
        if claim.get("requires_supplement") is True and claim_id not in covered_claims:
            blockers.append(f"claims.{claim_id}: requires supplementary support but no item links to it")

    evidence_blocker_count = len(blockers)
    inventory_complete = True
    raw_inventory = payload.get("submission_inventory", [])
    if not isinstance(raw_inventory, list):
        blockers.append("submission_inventory: must be an array")
        raw_inventory = []
    inventory_ids: set[str] = set()
    for index, entry in enumerate(raw_inventory):
        label = f"submission_inventory[{index}]"
        if not isinstance(entry, dict):
            blockers.append(f"{label}: must be an object")
            inventory_complete = False
            continue
        item_id = str(entry.get("item_id") or "")
        if not item_id or item_id in inventory_ids:
            blockers.append(f"{label}: item_id must be non-empty and unique")
            inventory_complete = False
        else:
            inventory_ids.add(item_id)
        state = entry.get("state")
        required = entry.get("required") is True
        if state not in INVENTORY_STATES:
            blockers.append(f"{label}: invalid state")
            inventory_complete = False
        elif required and state == "needs_author":
            blockers.append(f"{label} ({item_id}): required item still needs author input")
            inventory_complete = False
        elif required and state == "not_applicable":
            justification = str(entry.get("justification") or "").strip()
            if len(justification) < 12:
                blockers.append(f"{label}: required not_applicable item needs a specific justification")
                inventory_complete = False
        elif state == "ready":
            if _file_entry(root, entry.get("artifact"), f"{label}.artifact", blockers) is None:
                inventory_complete = False

    if not raw_inventory:
        warnings.append("submission_inventory is empty; supplementary evidence can pass, but package completeness was not assessed")

    evidence_blockers = blockers[:evidence_blocker_count]
    inventory_blockers = blockers[evidence_blocker_count:]

    return {
        "schema_version": SCHEMA_VERSION,
        "status": "PASS" if not blockers else "BLOCKED",
        "package_root": str(root),
        "signals": {
            "supplement_evidence_index_valid": not evidence_blockers,
            "submission_inventory_complete": inventory_complete and bool(raw_inventory),
            "external_submission_ready": False,
        },
        "item_results": item_results,
        "evidence_blockers": evidence_blockers,
        "inventory_blockers": inventory_blockers,
        "blockers": blockers,
        "warnings": warnings,
        "completion_boundary": "A valid local index does not establish author approval or authorize external submission.",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("index", type=Path)
    parser.add_argument("--write-report", type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    index_path = args.index.resolve()
    payload = json.loads(index_path.read_text(encoding="utf-8"))
    report = check_index(payload, index_path)
    rendered = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    if args.write_report:
        args.write_report.parent.mkdir(parents=True, exist_ok=True)
        args.write_report.write_text(rendered, encoding="utf-8")
    print(rendered, end="")
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
