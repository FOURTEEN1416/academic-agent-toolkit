"""Typed final-map registration and revalidation, not another figure authority.

The immutable map/plan use their approved revision.  A Runner-owned envelope
binds them to the current consumption revision, build, accepted J7 winner and
actual binary bytes.  Staged HTML is opaque evidence, never executable UI.
"""

from __future__ import annotations

import hashlib
import json
import re
from copy import deepcopy
from pathlib import Path, PurePosixPath
from typing import Any

from .contracts import ContractError
from .figure_reference_mapping import (
    FigureReferenceMappingError,
    build_figure_background_receipt,
    canonical_sha256,
    figure_authority_table_sha256,
    project_figure_mapping_for_user,
    validate_figure_reference_mapping,
)
from .product_contracts import task_scoped_artifact_receipt_id
from .quality_readiness import canonical_sha256 as publication_sha256

CONTRACT = "paperspine5.figure-final-mapping-consumption"
ARTIFACT_TYPE = "figure.final-mapping"
REGISTRATION_CONTRACT = "paperspine5.figure-final-mapping-registration"
STAGING = PurePosixPath("runner/.staging/figure-final-mappings")
MAX_BYTES = 64 * 1024 * 1024
_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")
_SHA = re.compile(r"^[0-9a-f]{64}$")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ContractError("final mapping: " + message)


def _bytes(value: Any) -> bytes:
    return (
        json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def validate_registration(value: Any) -> dict[str, Any]:
    _require(
        isinstance(value, dict)
        and set(value)
        == {
            "contract",
            "schema_version",
            "mapping",
            "auxiliaries",
            "external_action_authorized",
        },
        "registration contains unknown or missing fields",
    )
    _require(
        value["contract"] == REGISTRATION_CONTRACT
        and value["schema_version"] == "1.0"
        and value["external_action_authorized"] is False,
        "invalid registration contract",
    )
    _require(
        isinstance(value["mapping"], dict), "mapping must be an existing typed mapping"
    )
    items = value["auxiliaries"]
    _require(
        isinstance(items, list) and len(items) <= 8,
        "at most eight scoped auxiliaries are allowed",
    )
    ids = set()
    for item in items:
        _require(
            isinstance(item, dict)
            and set(item)
            == {"artifact_id", "role", "staged_relative_path", "sha256", "size_bytes"},
            "invalid auxiliary fields",
        )
        _require(
            isinstance(item["artifact_id"], str)
            and bool(_ID.fullmatch(item["artifact_id"]))
            and item["artifact_id"] not in ids,
            "invalid or duplicate auxiliary ID",
        )
        ids.add(item["artifact_id"])
        _require(
            item["role"] in {"editable_source", "comparison_surface", "preview"},
            "invalid auxiliary role",
        )
        path = item["staged_relative_path"]
        _require(
            isinstance(path, str)
            and len(path) <= 512
            and "\\" not in path
            and ":" not in path,
            "auxiliary path must be a bounded POSIX-relative path",
        )
        relative = PurePosixPath(path)
        _require(
            not relative.is_absolute()
            and ".." not in relative.parts
            and relative.parts[: len(STAGING.parts)] == STAGING.parts
            and relative != STAGING,
            "auxiliary path must stay in the final-mapping staging subtree",
        )
        _require(
            isinstance(item["sha256"], str) and bool(_SHA.fullmatch(item["sha256"])),
            "invalid auxiliary SHA",
        )
        _require(
            type(item["size_bytes"]) is int and 0 < item["size_bytes"] <= MAX_BYTES,
            "invalid auxiliary size",
        )
    _require(
        sum(item["size_bytes"] for item in items) <= MAX_BYTES,
        "auxiliary total exceeds 64 MiB",
    )
    return deepcopy(value)


def consumption_sha256(value: dict[str, Any]) -> str:
    return canonical_sha256(
        {k: v for k, v in value.items() if k != "consumption_sha256"}
    )


def validate_envelope(value: Any) -> dict[str, Any]:
    _require(
        isinstance(value, dict)
        and set(value) - {"successor_revalidation"}
        == {
            "contract",
            "schema_version",
            "mapping",
            "registration_subject",
            "consumption_subject",
            "validation_build_id",
            "plan_generation",
            "accepted_j7",
            "auxiliaries",
            "external_action_authorized",
            "consumption_sha256",
        },
        "invalid consumption envelope fields",
    )
    _require(
        value["contract"] == CONTRACT
        and value["schema_version"] == "1.0"
        and value["external_action_authorized"] is False,
        "invalid consumption envelope",
    )
    _require(
        value["consumption_sha256"] == consumption_sha256(value),
        "consumption self-hash changed",
    )
    mapping = value["mapping"]
    _require(
        isinstance(mapping, dict)
        and mapping.get("contract") == "paperspine5.figure-reference-mapping"
        and mapping.get("mapping_sha256")
        == canonical_sha256(
            {k: v for k, v in mapping.items() if k != "mapping_sha256"}
        ),
        "mapping semantic self-hash changed",
    )
    for field in ("registration_subject", "consumption_subject"):
        subject = value[field]
        _require(
            isinstance(subject, dict)
            and set(subject) == {"task_id", "revision_id", "material_snapshot_sha256"}
            and isinstance(subject["revision_id"], str)
            and subject["revision_id"].isdigit(),
            "invalid envelope subject",
        )
        _require(
            subject["task_id"] == mapping["subject"]["task_id"]
            and subject["material_snapshot_sha256"]
            == mapping["subject"]["material_snapshot_sha256"],
            "envelope changed task/material subject",
        )
    _require(
        int(value["registration_subject"]["revision_id"])
        <= int(value["consumption_subject"]["revision_id"]),
        "consumption precedes registration",
    )
    if "successor_revalidation" in value:
        proof = value["successor_revalidation"]
        _require(
            isinstance(proof, dict)
            and set(proof)
            == {
                "subject",
                "predecessor_receipt",
                "manuscript_head_receipt",
                "manuscript_head_sha256",
                "accepted_consumption",
                "migration_receipts",
                "current_method_sha256",
            }
            and set(proof["subject"])
            == {"task_id", "run_id", "revision_id", "material_snapshot_sha256"}
            and proof["subject"]["task_id"] == value["consumption_subject"]["task_id"]
            and proof["subject"]["material_snapshot_sha256"]
            == value["consumption_subject"]["material_snapshot_sha256"]
            and int(proof["subject"]["revision_id"])
            <= int(value["consumption_subject"]["revision_id"])
            and isinstance(proof["migration_receipts"], list)
            and bool(proof["migration_receipts"])
            and proof["migration_receipts"][0]["target_build_id"]
            == value["validation_build_id"]
            and isinstance(proof["current_method_sha256"], str)
            and bool(_SHA.fullmatch(proof["current_method_sha256"])),
            "invalid successor revalidation proof",
        )
    return value


def _context(runner: Any, task: dict[str, Any], actor: Any) -> dict[str, Any]:
    state = runner._runner_state(task)
    views = runner.kernel.list_artifacts(
        task["task_id"], subject_revision=task["revision"]
    )
    fresh = {}
    for view in views:
        if view.get("freshness") != "fresh":
            continue
        receipt = view.get("receipt", {})
        artifact_id = receipt.get("artifact_id")
        _require(artifact_id not in fresh, "ambiguous fresh artifact ID")
        fresh[artifact_id] = view
    if state["stage"] in {"awaiting_package", "awaiting_canonical", "awaiting_review"}:
        for artifact_id in ("publication.figure-intent", "publication.manuscript-head"):
            accepted_view = runner._accepted_academic_view(task, artifact_id)
            if accepted_view is not None:
                fresh[artifact_id] = accepted_view
    base = runner._read_academic_base_artifacts(
        task, state.get("academic_base_artifacts")
    )
    # J7 figure objects use the semantic candidate IDs while the immutable
    # Runner registry stores the corresponding input-manifest receipt IDs.
    # Expose a verified semantic alias here so final-mapping validation can
    # reopen the exact current/candidate evidence instead of treating a valid
    # J7 winner as missing.  The alias points to the already fresh receipt and
    # never creates a second artifact or changes its hash.
    for view in list(fresh.values()):
        receipt = view.get("receipt", {}) if isinstance(view, dict) else {}
        metadata = receipt.get("metadata", {}) if isinstance(receipt, dict) else {}
        semantic_id = metadata.get("semantic_artifact_id")
        if isinstance(semantic_id, str) and semantic_id not in fresh:
            fresh[semantic_id] = view
    receipt = fresh.get("materials.source-ledger", {}).get("receipt")
    _require(
        isinstance(receipt, dict)
        and receipt.get("sha256")
        == (state.get("material_inventory") or {}).get("sha256"),
        "current material ledger is missing",
    )
    bridge = runner._successor_receipt_bridge(
        task, receipt, artifact_type="materials.source-ledger"
    )
    inventory = runner._read_inventory_receipt(
        task,
        receipt,
        task["revision"],
        build_id=(bridge or {}).get("source_build_id"),
        runner_version=(bridge or {}).get("source_runner_version"),
    )
    authority = runner._trusted_figure_master_receipt(
        task=task,
        actor=actor or {},
        current_stage=state["stage"],
        persisted_base_artifacts=base,
        effective_base_artifacts=base,
    )
    _require(authority is not None, "persisted Master authority missing")
    # This existing safe-preview resolver reopens each reference through its
    # current material capability and verifies bytes/media; ledger hashes alone
    # are not a substitute for accessible exact references.
    runner._figure_reference_workspace_context(task["task_id"], actor=actor)
    review = runner._figure_review_projection(task, state.get("academic_inputs"), views)
    _require(
        isinstance(review, dict),
        "current persisted accepted J7 and independent comparison required",
    )
    cumulative = runner._read_academic_inputs(task, state.get("academic_inputs"))
    raw_figures = cumulative["stage_inputs"]["awaiting_figure_intent"]["intent"][
        "figures"
    ]
    accepted = fresh["publication.figure-intent"]["payload"]
    hashes = {key: view["receipt"]["sha256"] for key, view in fresh.items()}
    for entry in inventory["entries"]:
        hashes[entry["source_id"]] = entry["sha256"]
        hashes["source:" + entry["source_id"]] = entry["sha256"]
    return {
        "state": state,
        "fresh": fresh,
        "base": base,
        "inventory": inventory,
        "authority": authority,
        "raw_figures": raw_figures,
        "accepted": accepted,
        "hashes": hashes,
        "successor_source_build": (bridge or {}).get("source_build_id"),
        "successor_migrations": (bridge or {}).get("verified_migrations", []),
    }


def _read_bound(
    runner: Any, task: dict[str, Any], item: dict[str, Any]
) -> tuple[Path, bytes]:
    root = Path(task["run_root"]).resolve()
    path = Path(item["path"])
    if not path.is_absolute():
        path = root / path
    path = runner._validate_candidate_file_path(root, path, required_root=root)
    _require(
        0 < item["size_bytes"] <= MAX_BYTES
        and path.stat().st_size == item["size_bytes"],
        "bound file size changed",
    )
    content = path.read_bytes()
    _require(
        len(content) == item["size_bytes"] and _digest(content) == item["sha256"],
        "bound file bytes changed",
    )
    runner._validate_candidate_file_path(root, path, required_root=root)
    return path, content


def _auxiliary_media(path: Path, role: str, content: bytes) -> str:
    from .product_runner import _verified_figure_candidate_media_type

    media = _verified_figure_candidate_media_type(path, content)
    if role == "preview":
        _require(media is not None, "preview must have valid PNG/JPEG/SVG bytes")
        return media
    if role == "comparison_surface" and path.suffix.lower() == ".pdf":
        _require(content.startswith(b"%PDF-"), "comparison PDF magic mismatch")
        return "application/pdf"
    if role == "comparison_surface" and media:
        return media
    allowed = {
        "editable_source": {".py", ".r", ".svg", ".json", ".ipynb", ".txt", ".m"},
        "comparison_surface": {".html"},
    }
    _require(
        path.suffix.lower() in allowed.get(role, set()),
        "auxiliary extension is not allowed for role",
    )
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise ContractError(
            "final mapping: source/surface must contain UTF-8 text"
        ) from exc
    _require("\0" not in text, "source/surface contains binary NUL")
    if path.suffix.lower() in {".json", ".ipynb"}:
        try:
            json.loads(text)
        except ValueError as exc:
            raise ContractError("final mapping: auxiliary JSON malformed") from exc
    if path.suffix.lower() == ".svg":
        _require(media is not None, "editable SVG magic mismatch")
    # Deliberately NOT text/html. The content is not served by the image endpoint.
    return "application/octet-stream"


def _validate_mapping(
    runner: Any,
    task: dict[str, Any],
    context: dict[str, Any],
    mapping: dict[str, Any],
    auxiliaries: list[dict[str, Any]],
) -> tuple[dict[str, Any], list[dict[str, Any]], dict[str, Any]]:
    figure_id = mapping.get("figure", {}).get("figure_id")
    raw = next(
        (v for v in context["raw_figures"] if v.get("figure_id") == figure_id), None
    )
    accepted = next(
        (v for v in context["accepted"]["figures"] if v.get("figure_id") == figure_id),
        None,
    )
    _require(
        isinstance(raw, dict) and isinstance(accepted, dict),
        "figure is not accepted by current J7",
    )
    plan_binding = accepted.get("reference_plan_binding", {})
    plan_id = plan_binding.get("artifact_id")
    plan = context["base"].get(plan_id)
    _require(
        isinstance(plan, dict)
        and plan.get("plan_sha256") == plan_binding.get("sha256"),
        "exact approved plan unavailable",
    )
    plan_revision = str(plan["subject"]["runner_revision"])
    _require(
        int(plan_revision) <= task["revision"],
        "approved plan comes from a future revision",
    )
    expected = deepcopy(raw)
    binaries = []
    semantic_to_binary = {}
    hashes = dict(context["hashes"])
    for role, items in (
        ("current_asset", [raw.get("current_asset")]),
        ("candidate_assets", raw.get("candidate_assets", [])),
    ):
        converted = []
        for asset in items:
            if asset is None:
                continue
            artifact_id = asset["artifact_id"]
            view = context["fresh"].get(artifact_id)
            _require(
                isinstance(view, dict),
                "selected/current/candidate has no fresh binary receipt",
            )
            receipt = view["receipt"]
            metadata = receipt.get("metadata", {})
            _require(
                metadata.get("product_build_id") == runner.expected_build_id
                or (
                    metadata.get("product_build_id")
                    in {v["source_build_id"] for v in context["successor_migrations"]}
                ),
                "binary comes from another build without a verified formal successor bridge",
            )
            if role == "candidate_assets":
                manifest = context["base"].get(artifact_id)
                _require(
                    receipt["artifact_type"] == "figure.candidate-image"
                    and isinstance(manifest, dict),
                    "candidate is not a promoted typed binary",
                )
                manifest_semantic_sha256 = canonical_sha256(manifest)
                # A same-task J7 recovery may republish the verified manifest
                # under its semantic artifact ID while the promoted binary
                # receipt still carries the predecessor registration's input
                # hash.  The manifest, selected semantic hash, bound bytes,
                # plan, and material snapshot remain the authoritative chain;
                # do not make a duplicate legacy receipt hash a new content
                # gate.
                metadata_semantic_sha256 = metadata.get("input_artifact_sha256")
                _require(
                    manifest_semantic_sha256 == asset["sha256"]
                    and (
                        metadata_semantic_sha256 == manifest_semantic_sha256
                        or (
                            isinstance(metadata_semantic_sha256, str)
                            and isinstance(manifest.get("artifact_id"), str)
                            and manifest.get("artifact_id") == artifact_id
                            and manifest.get("external_action_authorized") is False
                        )
                    ),
                    "candidate JSON semantic hash mismatch",
                )
                _require(
                    manifest.get("sha256") == receipt["sha256"]
                    and manifest.get("artifact_id") == artifact_id,
                    "candidate JSON does not bind registered PNG bytes",
                )
                _require(
                    metadata.get("figure_id") == figure_id
                    and metadata.get("reference_plan_artifact_id") == plan_id
                    and metadata.get("reference_plan_sha256") == plan["plan_sha256"]
                    # Recovery can re-register the same immutable candidate at
                    # a later Runner revision while its semantic manifest keeps
                    # the original registration revision. Figure, plan, bytes,
                    # and material snapshot remain the binding checks.
                    and int(plan_revision) <= int(metadata.get("registered_revision", -1)) <= task["revision"]
                    and metadata.get("material_snapshot_sha256")
                    == context["inventory"]["snapshot_sha256"],
                    "candidate registration subject/plan mismatch",
                )
            else:
                _require(
                    asset["sha256"] == receipt["sha256"],
                    "original asset byte binding mismatch",
                )
            # J7's current_asset may be the immutable Runner input manifest
            # for the active manuscript figure rather than a promoted image
            # receipt.  It is still a valid semantic comparison baseline, but
            # it must not be re-read as if its JSON bytes were publication
            # media. Candidate assets and the selected publication asset keep
            # the strict image-byte verification below.
            if (
                role == "current_asset"
                and receipt.get("artifact_type") == "runner.academic-base-input"
            ):
                semantic_to_binary[asset["sha256"]] = receipt["sha256"]
                hashes[artifact_id] = receipt["sha256"]
                converted.append(
                    {
                        "artifact_id": artifact_id,
                        "sha256": receipt["sha256"],
                        "revision_id": plan_revision,
                    }
                )
                continue
            path, content = _read_bound(runner, task, receipt)
            from .product_runner import _verified_figure_candidate_media_type

            _require(
                _verified_figure_candidate_media_type(path, content) is not None,
                "candidate image media mismatch",
            )
            semantic_to_binary[asset["sha256"]] = receipt["sha256"]
            hashes[artifact_id] = receipt["sha256"]
            binaries.append(receipt)
            converted.append(
                {
                    "artifact_id": artifact_id,
                    "sha256": receipt["sha256"],
                    "revision_id": plan_revision,
                }
            )
        expected[role] = (
            converted
            if role == "candidate_assets"
            else (converted[0] if converted else None)
        )
    comparison = raw.get("independent_comparison")
    _require(
        isinstance(comparison, dict) and comparison.get("status") == "PASS",
        "persisted independent comparison missing",
    )
    selected_semantic = accepted.get("selected_asset", {}).get("sha256")
    _require(
        selected_semantic == comparison.get("selected_sha256")
        and selected_semantic in semantic_to_binary,
        "persisted winner differs from candidate manifest namespace",
    )
    selected_binary = semantic_to_binary[selected_semantic]
    expected["independent_comparison"] = {
        **comparison,
        "selected_sha256": selected_binary,
    }
    final_review = mapping.get("independent_review", {})
    for field in ("reviewer_id", "decision"):
        _require(
            final_review.get(field) == comparison.get(field),
            "mapping cannot replace persisted independent " + field,
        )
    _require(
        set(comparison.get("reviewed_asset_hashes", [])) == set(semantic_to_binary),
        "persisted review does not cover every accepted candidate",
    )
    _require(
        comparison.get("reviewer_id")
        not in {raw.get("producer_id"), *comparison.get("producer_ids", [])},
        "reviewer is a producer",
    )
    # Each auxiliary is explicitly scoped by the existing mapping, never a hash-map override.
    roles = {
        mapping.get("assets", {})
        .get("editable_source", {})
        .get("artifact_id"): "editable_source",
        mapping.get("side_by_side", {}).get(
            "surface_artifact_id"
        ): "comparison_surface",
    }
    for side in ("left", "right"):
        preview = mapping.get("side_by_side", {}).get(side, {}).get("preview", {})
        if preview:
            roles.setdefault(preview.get("preview_artifact_id"), "preview")
    for auxiliary in auxiliaries:
        _require(
            roles.get(auxiliary["artifact_id"]) == auxiliary["role"],
            "auxiliary does not belong to this mapping",
        )
        _require(
            auxiliary["artifact_id"] not in hashes,
            "auxiliary cannot override a registered artifact",
        )
        path, content = _read_bound(runner, task, auxiliary)
        _require(
            _auxiliary_media(path, auxiliary["role"], content)
            == auxiliary["media_type"],
            "auxiliary media changed",
        )
        hashes[auxiliary["artifact_id"]] = auxiliary["sha256"]
    hashes[plan_id] = plan["plan_sha256"]
    try:
        # J7 keeps the candidate manifest's semantic hash (the value users
        # select), while the final-map validator also needs the promoted
        # image-byte hash for background and immutable-receipt checks.  Build
        # a private validation projection that translates only those asset
        # bindings to their verified binary hashes; the persisted mapping and
        # user-facing selection remain semantic and are never rewritten.
        validation_mapping = deepcopy(mapping)
        validation_assets = validation_mapping.get("assets", {})
        if isinstance(validation_assets, dict):
            for key in ("candidates",):
                values = validation_assets.get(key)
                if isinstance(values, list):
                    for item in values:
                        if isinstance(item, dict) and item.get("sha256") in semantic_to_binary:
                            item["sha256"] = semantic_to_binary[item["sha256"]]
            for key in ("selected", "publication"):
                item = validation_assets.get(key)
                if isinstance(item, dict) and item.get("sha256") in semantic_to_binary:
                    item["sha256"] = semantic_to_binary[item["sha256"]]
        validation_review = validation_mapping.get("independent_review")
        if isinstance(validation_review, dict):
            validation_review["reviewed_asset_hashes"] = [
                semantic_to_binary.get(value, value)
                for value in validation_review.get("reviewed_asset_hashes", [])
            ]
            validation_review["selected_sha256"] = semantic_to_binary.get(
                validation_review.get("selected_sha256"),
                validation_review.get("selected_sha256"),
            )
        validation_side_by_side = validation_mapping.get("side_by_side")
        if isinstance(validation_side_by_side, dict):
            right = validation_side_by_side.get("right")
            if isinstance(right, dict) and isinstance(right.get("preview"), dict):
                preview = right["preview"]
                preview["source_asset_sha256"] = semantic_to_binary.get(
                    preview.get("source_asset_sha256"), preview.get("source_asset_sha256")
                )
                preview["preview_sha256"] = semantic_to_binary.get(
                    preview.get("preview_sha256"), preview.get("preview_sha256")
                )
        validation_background = validation_mapping.get("background")
        if isinstance(validation_background, dict):
            publication_sha = validation_assets.get("publication", {}).get("sha256") if isinstance(validation_assets.get("publication"), dict) else None
            if publication_sha:
                validation_background["asset_sha256"] = publication_sha
                validation_background.pop("receipt_sha256", None)
                validation_background["receipt_sha256"] = canonical_sha256(validation_background)
        validation_mapping.pop("mapping_sha256", None)
        validation_mapping["mapping_sha256"] = canonical_sha256(validation_mapping)
        validate_figure_reference_mapping(
            validation_mapping,
            expected_subject=plan["subject"],
            expected_figure=expected,
            expected_plan=plan,
            expected_plan_artifact_id=plan_id,
            registered_artifacts=hashes,
            trusted_actor_receipt=context["authority"],
        )
        selected_receipt = next(
            v
            for v in binaries
            if v["artifact_id"] == mapping["assets"]["publication"]["artifact_id"]
        )
        path, _ = _read_bound(runner, task, selected_receipt)
        background = mapping["background"]
        actual = build_figure_background_receipt(
            path,
            canvas_bbox=background["canvas"]["bbox_normalized"],
            axes=background["axes"],
            panels=background["panels"],
            publication_surface=True,
            axes_not_applicable=background["axes_inventory"]["status"]
            == "not_applicable",
        )
        _require(
            actual == background, "actual publication background differs from receipt"
        )
    except (FigureReferenceMappingError, StopIteration) as exc:
        raise ContractError("final mapping: " + str(exc)) from exc
    bridge = {
        "figure_id": figure_id,
        "frozen_plan": deepcopy(mapping["plan_binding"]),
        "mapping_sha256": mapping["mapping_sha256"],
        "background_receipt_sha256": mapping["background"]["receipt_sha256"],
        "accepted_candidate_manifest_sha256": selected_semantic,
        "publication_binary_sha256": selected_binary,
        "comparison_sha256": canonical_sha256(comparison),
        "persisted_comparison": deepcopy(comparison),
    }
    generation = {
        "revision_id": plan_revision,
        "plan_sha256": plan["plan_sha256"],
        "candidate_registration_build_ids": sorted(
            {
                v.get("metadata", {}).get(
                    "generation_product_build_id",
                    v.get("metadata", {}).get("product_build_id", ""),
                )
                for v in binaries
            }
        ),
    }
    return bridge, binaries, generation


def _receipt(
    runner: Any,
    task: dict[str, Any],
    envelope: dict[str, Any],
    *,
    revision: int,
    command_id: str,
) -> dict[str, Any]:
    content = _bytes(envelope)
    sha = _digest(content)
    artifact_id = (
        "figure-final-mapping."
        + hashlib.sha256(
            (
                envelope["mapping"]["figure"]["figure_id"]
                + "\0"
                + runner.expected_build_id
            ).encode()
        ).hexdigest()[:32]
    )
    relative = Path("runner/figure-mappings") / (sha + ".json")
    _publish_bound(runner, task, relative, content, command_id=command_id)
    return {
        "contract": "paperspine5.artifact-receipt",
        "schema_version": "1.0",
        "receipt_id": task_scoped_artifact_receipt_id(
            task_id=task["task_id"],
            revision_id=revision,
            artifact_id=artifact_id,
            artifact_type=ARTIFACT_TYPE,
            content_sha256=sha,
        ),
        "artifact_id": artifact_id,
        "artifact_type": ARTIFACT_TYPE,
        "path": relative.as_posix(),
        "sha256": sha,
        "size_bytes": len(content),
        "subject": {
            "task_id": task["task_id"],
            "revision_id": str(revision),
            "input_hashes": {
                "materials.source-ledger": envelope["consumption_subject"][
                    "material_snapshot_sha256"
                ],
                envelope["mapping"]["plan_binding"]["artifact_id"]: envelope["mapping"][
                    "plan_binding"
                ]["sha256"],
            },
        },
        "authority": {
            "kind": "runtime-evidence-input",
            "producer_id": "paperspine5.product-runner.final-mapping",
        },
        "metadata": {
            "figure_id": envelope["mapping"]["figure"]["figure_id"],
            "asset_role": "final_mapping",
            "product_build_id": runner.expected_build_id,
            "semantic_hash_kind": "figure-final-mapping-v1",
            "semantic_sha256": envelope["mapping"]["mapping_sha256"],
            "consumption_sha256": envelope["consumption_sha256"],
        },
        "external_action_authorized": False,
    }


def _publish_bound(
    runner: Any,
    task: dict[str, Any],
    relative: Path,
    content: bytes,
    *,
    command_id: str,
) -> None:
    """Check both destination and internal staging ancestors before any writes."""
    from .product_kernel import _is_link_or_reparse

    root = Path(task["run_root"]).resolve()
    paths = (
        relative,
        Path("runner/.staging")
        / hashlib.sha256(command_id.encode("utf-8")).hexdigest(),
    )
    for candidate in paths:
        _require(
            not candidate.is_absolute() and ".." not in candidate.parts,
            "publish path escapes run root",
        )
        cursor = root
        for part in candidate.parts:
            cursor = cursor / part
            _require(
                not cursor.is_symlink()
                and not (cursor.exists() and _is_link_or_reparse(cursor)),
                "publish path contains a link or reparse point",
            )
        _require(cursor.resolve().is_relative_to(root), "publish path escapes run root")
    runner._publish_bytes(task, relative, content, command_id=command_id)
    _read_bound(
        runner,
        task,
        {
            "path": relative.as_posix(),
            "sha256": _digest(content),
            "size_bytes": len(content),
        },
    )


def _sealed_members(
    runner: Any, task: dict[str, Any], migration: dict[str, Any]
) -> set[str]:
    """Verify the append-only ledger prefix sealed by an accepted migration."""
    identity = migration["source"]["identity"]
    count = identity["artifact_count"]
    views = runner.kernel.list_artifacts(task["task_id"])
    _require(
        type(count) is int and 0 < count <= len(views), "invalid sealed artifact count"
    )
    # Kernel orders newest first (recorded_at, rowid). Registrations only append.
    receipts = [v["receipt"] for v in views[-count:]]
    descriptors = [
        {
            "receipt_id": r.get("receipt_id"),
            "artifact_id": r.get("artifact_id"),
            "artifact_type": r.get("artifact_type"),
            "revision_id": r.get("subject", {}).get("revision_id"),
            "sha256": r.get("sha256"),
        }
        for r in receipts
    ]
    descriptors.sort(
        key=lambda v: (
            str(v["revision_id"]),
            str(v["artifact_id"]),
            str(v["receipt_id"]),
        )
    )
    _require(
        _digest(_bytes(descriptors)) == identity["artifact_set_sha256"],
        "sealed predecessor artifact membership changed",
    )
    return {r["receipt_id"] for r in receipts}


def _post_j8_predecessor(
    runner: Any, task: dict[str, Any], context: dict[str, Any], request: dict[str, Any]
) -> tuple[dict[str, Any], dict[str, Any]]:
    migrations = context["successor_migrations"]
    _require(
        bool(migrations), "post-J8 revalidation requires sealed formal successor proof"
    )
    head_view = context["fresh"].get("publication.manuscript-head", {})
    head = head_view.get("payload", {})
    _require(
        head.get("contract") == "paperspine5.manuscript-head"
        and head.get("status") == "PASS"
        and head.get("external_action_authorized") is False
        and head.get("subject", {}).get("task_id") == task["task_id"]
        and head_view == runner._accepted_academic_view(task, "publication.manuscript-head")
        and head.get("head_sha256")
        == publication_sha256({k: v for k, v in head.items() if k != "head_sha256"}),
        "current accepted canonical head unavailable",
    )
    groups: dict[str, list[dict[str, Any]]] = {}
    for view in runner.kernel.list_artifacts(
        task["task_id"], subject_revision=task["revision"], artifact_type=ARTIFACT_TYPE
    ):
        build = view["receipt"].get("metadata", {}).get("product_build_id")
        if build in {v["source_build_id"] for v in migrations}:
            groups.setdefault(build, []).append(view)
    matches = []
    expected_figures = {v["figure_id"] for v in context["accepted"]["figures"]}
    for build, views in groups.items():
        if any(v["freshness"] != "fresh" for v in views):
            continue
        envelopes = [validate_envelope(v["payload"]) for v in views]
        if (
            len(envelopes) != len(expected_figures)
            or {v["mapping"]["figure"]["figure_id"] for v in envelopes}
            != expected_figures
        ):
            continue
        # Accepted transactions insert promoted maps in collection order; the
        # Kernel read order reverses that insertion order. Reconstruct the exact
        # context hashed by the current head, never a newly chosen sort order.
        consumed = {
            "policy": "required-for-every-new-j8",
            "build_id": build,
            "bindings": [v["accepted_j7"] for v in reversed(envelopes)],
        }
        preserved = (
            envelopes[0].get("successor_revalidation", {}).get("accepted_consumption")
        )
        if preserved is not None and publication_sha256(preserved) == head.get("final_mapping_consumption_sha256") and all(
            v.get("successor_revalidation", {}).get("accepted_consumption") == preserved
            for v in envelopes
        ):
            consumed = preserved
        if publication_sha256(consumed) == head.get("final_mapping_consumption_sha256"):
            matches.append((build, views, consumed))
    _require(
        bool(matches),
        "no unique predecessor mapping set consumed by current canonical head",
    )
    # Revalidation may already have occurred at an intermediate successor.
    # Choose its closest sealed source, not an arbitrary older PASS.
    ranks = {v["source_build_id"]: i for i, v in enumerate(migrations)}
    build, views, consumed = min(matches, key=lambda v: ranks[v[0]])
    figure_id = request["mapping"].get("figure", {}).get("figure_id")
    selected = [
        v for v in views if v["payload"]["mapping"]["figure"]["figure_id"] == figure_id
    ]
    _require(len(selected) == 1, "post-J8 cannot first-register a figure")
    prior = selected[0]
    envelope = prior["payload"]
    _require(
        envelope["mapping"] == request["mapping"]
        and envelope["validation_build_id"] == build
        and envelope["consumption_subject"]["revision_id"] == str(task["revision"])
        and int(envelope["registration_subject"]["revision_id"]) < task["revision"],
        "post-J8 cannot change an accepted mapping or its consumption subject",
    )
    migration_pin = next(v for v in migrations if v["source_build_id"] == build)
    migration = runner.kernel.get_migration_receipt(
        task["task_id"], migration_pin["migration_id"]
    )
    members = _sealed_members(runner, task, migration)
    _require(
        all(v["receipt"]["receipt_id"] in members for v in views)
        and head_view["receipt"]["receipt_id"] in members,
        "mapping/head were not members of the sealed predecessor ledger",
    )
    proof = {
        "subject": {
            "task_id": task["task_id"],
            "run_id": task["active_run_id"],
            "revision_id": str(task["revision"]),
            "material_snapshot_sha256": context["inventory"]["snapshot_sha256"],
        },
        "predecessor_receipt": deepcopy(prior["receipt"]),
        "manuscript_head_receipt": deepcopy(head_view["receipt"]),
        "manuscript_head_sha256": head["head_sha256"],
        "accepted_consumption": consumed,
        "migration_receipts": deepcopy(migrations),
        "current_method_sha256": figure_authority_table_sha256(),
    }
    return envelope, proof


def legacy_method_is_accepted(
    runner: Any, task: dict[str, Any], authority_sha: str
) -> bool:
    """Only retained, head-bound post-J8 science may carry a historical method hash.

    This does not validate a final figure or grant current PASS. The collector
    still requires a new current-build receipt and reruns the native pixel gate.
    """
    stage = runner._runner_state(task)["stage"]
    user_request = task.get("state", {}).get("user_revision_request", {})
    previous = user_request.get("previous_delivery", {})
    current_authority = runner._runner_state(task).get("academic_base_artifacts", {}).get("figure-master-authority", {})
    previous_authority = previous.get("academic_base_artifacts", {}).get("figure-master-authority", {})
    if (user_request.get("origin") == "user_feedback" and user_request.get("scope") in {"manuscript", "figures"}
            and previous.get("active_run_id") == task.get("active_run_id") and current_authority
            and all(current_authority.get(k) == previous_authority.get(k) for k in ("artifact_id", "artifact_type", "sha256", "size_bytes"))):
        previous = user_request["previous_delivery"]
        envelopes = user_request.get("retained_figure_history", [])
        if envelopes and all(item.get("validation_build_id") == runner.expected_build_id for item in envelopes):
            root = Path(task["run_root"]).resolve()
            head_pointer = previous["academic_artifacts"]["publication.manuscript-head"]
            for raw in envelopes:
                envelope = validate_envelope(raw)
                proof = envelope.get("successor_revalidation", {})
                receipt = proof.get("manuscript_head_receipt", {})
                if (envelope["validation_build_id"] != runner.expected_build_id
                        or proof.get("current_method_sha256") != figure_authority_table_sha256()
                        or envelope["mapping"]["mapping_authority"]["authority_table_sha256"] != authority_sha
                        or any(receipt.get(k) != head_pointer.get(k) for k in ("artifact_id", "artifact_type", "sha256", "size_bytes"))
                        or (root / str(receipt.get("path", ""))).resolve() != (root / head_pointer["path"]).resolve()):
                    return False
                _verify_revalidation_history(runner, task, envelope)
            return True
    if stage not in {
        "awaiting_review",
        "awaiting_package",
        "target_package_ready",
    }:
        return False
    views = runner.kernel.list_artifacts(
        task["task_id"], subject_revision=task["revision"]
    )
    fresh = {v["receipt"]["artifact_id"]: v for v in views if v["freshness"] == "fresh"}
    if runner._runner_state(task)["stage"] == "awaiting_package":
        for artifact_id in ("publication.figure-intent", "publication.manuscript-head"):
            accepted_view = runner._accepted_academic_view(task, artifact_id)
            if accepted_view is not None:
                fresh[artifact_id] = accepted_view
    head = fresh.get("publication.manuscript-head", {}).get("payload", {})
    accepted = fresh.get("publication.figure-intent", {}).get("payload", {})
    figures = {v["figure_id"] for v in accepted.get("figures", [])}
    maps = [
        v
        for v in views
        if v["freshness"] == "fresh" and v["receipt"]["artifact_type"] == ARTIFACT_TYPE
    ]
    current = [
        v
        for v in maps
        if v["receipt"].get("metadata", {}).get("product_build_id")
        == runner.expected_build_id
    ]
    if (
        current
        and {v["payload"]["mapping"]["figure"]["figure_id"] for v in current} == figures
    ):
        for view in current:
            envelope = validate_envelope(view["payload"])
            proof = envelope.get("successor_revalidation", {})
            if (
                proof.get("current_method_sha256") != figure_authority_table_sha256()
                or envelope["mapping"]["mapping_authority"]["authority_table_sha256"]
                != authority_sha
                or publication_sha256(proof.get("accepted_consumption"))
                != head.get("final_mapping_consumption_sha256")
            ):
                return False
            _verify_revalidation_history(runner, task, envelope)
        return True
    # A completed task can undergo a normal same-revision successor too. Permit
    # only sealed historical reading here, never current-build mapping PASS or
    # another registration/J10. The collector still rejects old-build receipts.
    if stage == "target_package_ready":
        readiness = runner.kernel.get_readiness(task["task_id"])
        if readiness.get("status") != "fresh" or readiness.get("delivery_ready") is not True:
            return False
    inventory = fresh.get("materials.source-ledger", {}).get("receipt")
    if not maps or not inventory:
        return False
    bridge = runner._successor_receipt_bridge(
        task, inventory, artifact_type="materials.source-ledger"
    )
    context = {
        "fresh": fresh,
        "accepted": accepted,
        "successor_migrations": (bridge or {}).get("verified_migrations", []),
        "inventory": {
            "snapshot_sha256": inventory["metadata"]["material_snapshot_sha256"]
        },
    }
    seen = set()
    for view in maps:
        mapping = view["payload"]["mapping"]
        if mapping["figure"]["figure_id"] in seen:
            continue
        prior, _ = _post_j8_predecessor(runner, task, context, {"mapping": mapping})
        if stage == "target_package_ready":
            _verify_revalidation_history(runner, task, prior)
        if (
            prior["mapping"]["mapping_authority"]["authority_table_sha256"]
            != authority_sha
        ):
            return False
        seen.add(mapping["figure"]["figure_id"])
    return bool(figures) and seen == figures


def _verify_revalidation_history(
    runner: Any, task: dict[str, Any], envelope: dict[str, Any]
) -> None:
    """A promoted current-build wrapper must retain its immutable proof bytes."""
    proof = envelope.get("successor_revalidation")
    if proof is None:
        return
    _require(
        proof["subject"]["run_id"] == task["active_run_id"], "revalidation run changed"
    )
    bound = []
    for key in ("predecessor_receipt", "manuscript_head_receipt"):
        receipt = proof[key]
        views = runner.kernel.list_artifacts(
            task["task_id"], subject_revision=int(receipt["subject"]["revision_id"])
        )
        _require(
            any(v["receipt"] == receipt and v["freshness"] == "fresh" for v in views),
            "revalidation history is not exact ledger-backed evidence",
        )
        _, content = _read_bound(runner, task, receipt)
        bound.append(json.loads(content))
    prior, head = bound
    validate_envelope(prior)
    _require(
        prior["mapping"] == envelope["mapping"]
        and prior["accepted_j7"] == envelope["accepted_j7"]
        and prior["plan_generation"] == envelope["plan_generation"]
        and prior["auxiliaries"] == envelope["auxiliaries"]
        and head["head_sha256"] == proof["manuscript_head_sha256"]
        and head["final_mapping_consumption_sha256"]
        == publication_sha256(proof["accepted_consumption"]),
        "revalidation changed accepted history",
    )
    for pin in proof["migration_receipts"]:
        migration = runner.kernel.get_migration_receipt(
            task["task_id"], pin["migration_id"]
        )
        _require(
            isinstance(migration, dict)
            and migration.get("receipt_sha256")
            == pin["receipt_sha256"]
            == canonical_sha256(
                {k: v for k, v in migration.items() if k != "receipt_sha256"}
            )
            and migration["task_id"] == task["task_id"]
            and migration["active_run_id"] == task["active_run_id"]
            and str(migration["revision"]) == proof["subject"]["revision_id"]
            and migration["source"]["build_id"] == pin["source_build_id"]
            and migration["target"]["build_id"] == pin["target_build_id"],
            "revalidation migration history changed",
        )


def register_final_mapping(
    runner: Any,
    task_id: str,
    registration: Any,
    *,
    command_id: str,
    expected_revision: int,
    writer_id: str,
    actor: Any = None,
) -> dict[str, Any]:
    request = validate_registration(registration)
    _require(
        isinstance(command_id, str)
        and bool(command_id)
        and isinstance(writer_id, str)
        and bool(writer_id),
        "command/writer required",
    )
    task = runner._task_for_mutation(task_id, expected_revision)
    stage = runner._runner_state(task)["stage"]
    _require(
        stage in {"awaiting_canonical", "awaiting_review", "awaiting_package"},
        "registration requires J8 or post-J8 successor revalidation at J9/J10",
    )
    _require(
        actor is None
        or (
            isinstance(actor, dict)
            and isinstance(actor.get("actor_id"), str)
            and actor.get("surface")
            in {
                "codex",
                "claude-code",
                "dsh",
                "standalone-skill",
                "web",
                "mcp",
                "cli",
                "system",
            }
        ),
        "invalid transport actor; actor cannot supply mapping authority",
    )
    context = _context(runner, task, actor)
    prior, proof = (
        (None, None)
        if stage == "awaiting_canonical"
        else _post_j8_predecessor(runner, task, context, request)
    )
    root = Path(task["run_root"]).resolve()
    auxiliaries = []
    for item in request["auxiliaries"]:
        path = runner._validate_candidate_file_path(
            root,
            root / item["staged_relative_path"],
            required_root=root / Path(STAGING),
        )
        _, content = _read_bound(runner, task, {**item, "path": str(path)})
        media = _auxiliary_media(path, item["role"], content)
        auxiliaries.append(
            {
                "artifact_id": item["artifact_id"],
                "role": item["role"],
                "path": path.relative_to(root).as_posix(),
                "sha256": item["sha256"],
                "size_bytes": item["size_bytes"],
                "media_type": media,
            }
        )
    if prior is not None:
        fields = ("artifact_id", "role", "sha256", "size_bytes", "media_type")

        def signature(items):
            return sorted(tuple(v[k] for k in fields) for v in items)

        _require(
            signature(auxiliaries) == signature(prior["auxiliaries"]),
            "post-J8 cannot change accepted auxiliary bytes or roles",
        )
        # Reopen immutable stored bytes as well as the submitted staging files.
        auxiliaries = deepcopy(prior["auxiliaries"])
    bridge, _, generation = _validate_mapping(
        runner, task, context, request["mapping"], auxiliaries
    )
    if prior is not None:
        _require(
            bridge == prior["accepted_j7"] and generation == prior["plan_generation"],
            "post-J8 accepted J7/generation changed",
        )
    # Validate first. Failed semantic/background checks never publish attachments.
    for item in auxiliaries if prior is None else []:
        path, content = _read_bound(runner, task, item)
        relative = Path("runner/figure-mapping-attachments") / (
            item["sha256"] + path.suffix.lower()
        )
        _publish_bound(runner, task, relative, content, command_id=command_id)
        item["path"] = relative.as_posix()
    subject = {
        "task_id": task_id,
        "revision_id": str(expected_revision),
        "material_snapshot_sha256": context["inventory"]["snapshot_sha256"],
    }
    envelope = {
        "contract": CONTRACT,
        "schema_version": "1.0",
        "mapping": request["mapping"],
        "registration_subject": deepcopy(prior["registration_subject"])
        if prior is not None
        else subject,
        "consumption_subject": deepcopy(subject),
        "validation_build_id": runner.expected_build_id,
        "plan_generation": generation,
        "accepted_j7": bridge,
        "auxiliaries": auxiliaries,
        "external_action_authorized": False,
    }
    if proof is not None:
        envelope["successor_revalidation"] = proof
    envelope["consumption_sha256"] = consumption_sha256(envelope)
    validate_envelope(envelope)
    _verify_revalidation_history(runner, task, envelope)
    receipt = _receipt(
        runner, task, envelope, revision=expected_revision, command_id=command_id
    )
    result = runner.kernel.record_artifact(
        task_id,
        receipt,
        expected_revision=expected_revision,
        command_id=command_id,
        writer_id=writer_id,
        runner_registration=runner._handler_registrations["runner.issue.answer"],
    )
    return {
        "contract": "paperspine5.figure-final-mapping-registration-result",
        "schema_version": "1.0",
        "task_id": task_id,
        "revision": expected_revision,
        "stage": stage,
        "registration_applied": True,
        "academic_revision_advanced": False,
        "command_result": result,
        "artifact_receipt": result["receipt"],
        "mapping_sha256": request["mapping"]["mapping_sha256"],
        "consumption_sha256": envelope["consumption_sha256"],
        "external_action_authorized": False,
    }


def collect_final_mappings(
    runner: Any, task: dict[str, Any], *, actor: Any = None
) -> list[dict[str, Any]]:
    views = runner.kernel.list_artifacts(
        task["task_id"], subject_revision=task["revision"], artifact_type=ARTIFACT_TYPE
    )
    if not views:
        return []
    active = [
        view
        for view in views
        if view.get("receipt", {}).get("metadata", {}).get("product_build_id")
        == runner.expected_build_id
    ]
    _require(
        bool(active),
        "build changed; use formal successor and re-register/revalidate the unchanged approved plan",
    )
    outdated_figures = {
        view.get("receipt", {}).get("metadata", {}).get("figure_id") for view in views
    }
    active_figures = {
        view.get("receipt", {}).get("metadata", {}).get("figure_id") for view in active
    }
    _require(
        outdated_figures == active_figures,
        "some figures still require current-build final-map re-registration",
    )
    context = _context(runner, task, actor)
    result = []
    for view in active:
        _require(view.get("freshness") == "fresh", "registered mapping bytes are stale")
        envelope = validate_envelope(view["payload"])
        _verify_revalidation_history(runner, task, envelope)
        if envelope.get("successor_revalidation") is not None:
            _require(
                envelope["successor_revalidation"]["current_method_sha256"]
                == figure_authority_table_sha256(),
                "current PaperSpine method changed after revalidation",
            )
        _require(
            envelope["validation_build_id"] == runner.expected_build_id,
            "build changed; use formal successor and re-register/revalidate the unchanged approved plan",
        )
        _require(
            envelope["consumption_subject"]["revision_id"] == str(task["revision"]),
            "consumption revision stale",
        )
        bridge, binaries, generation = _validate_mapping(
            runner, task, context, envelope["mapping"], envelope["auxiliaries"]
        )
        _require(
            bridge == envelope["accepted_j7"]
            and generation == envelope["plan_generation"],
            "accepted J7/generation changed",
        )
        result.append(
            {
                "envelope": deepcopy(envelope),
                "receipt": view["receipt"],
                "binaries": binaries,
            }
        )
    return result


def completed_mappings_for_revision(runner: Any, task: dict[str, Any]) -> list[dict[str, Any]]:
    """Revalidate the sealed last delivery for explicit manuscript-only revision.

    No first registration, new assets or reviewer replacement: only the already
    head-consumed mapping can enter the normal J8 path again. Pixel and byte
    checks run in this build before any new receipt is published by the command.
    """
    _require(runner._runner_state(task)["stage"] == "target_package_ready",
             "revision figure carry requires the completed local package")
    views = runner.kernel.list_artifacts(task["task_id"], subject_revision=task["revision"], artifact_type=ARTIFACT_TYPE)
    if not views or all(view["receipt"]["metadata"].get("product_build_id") == runner.expected_build_id for view in views):
        return collect_final_mappings(runner, task)
    context = _context(runner, task, None)
    result = []
    for figure in context["accepted"]["figures"]:
        candidates = [v for v in views if v["payload"]["mapping"]["figure"]["figure_id"] == figure["figure_id"]]
        _require(bool(candidates), "completed figure mapping missing")
        prior, proof = _post_j8_predecessor(runner, task, context, {"mapping": candidates[0]["payload"]["mapping"]})
        bridge, binaries, generation = _validate_mapping(runner, task, context, prior["mapping"], prior["auxiliaries"])
        _require(bridge == prior["accepted_j7"] and generation == prior["plan_generation"], "completed figure evidence changed")
        envelope = deepcopy(prior)
        envelope.update(validation_build_id=runner.expected_build_id, successor_revalidation=proof)
        envelope["consumption_sha256"] = consumption_sha256(envelope)
        validate_envelope(envelope)
        _verify_revalidation_history(runner, task, envelope)
        result.append({"envelope": envelope, "binaries": binaries})
    return result


def promote_final_mappings(
    runner: Any,
    task: dict[str, Any],
    items: list[dict[str, Any]],
    *,
    revision: int,
    command_id: str,
) -> list[dict[str, Any]]:
    receipts = []
    binaries = {}
    for item in items:
        envelope = deepcopy(item["envelope"])
        envelope["consumption_subject"]["revision_id"] = str(revision)
        envelope["consumption_sha256"] = consumption_sha256(envelope)
        receipts.append(
            _receipt(runner, task, envelope, revision=revision, command_id=command_id)
        )
        binaries.update({r["artifact_id"]: r for r in item["binaries"]})
    for receipt in binaries.values():
        value = deepcopy(receipt)
        value.pop("recorded_at", None)
        value["subject"]["revision_id"] = str(revision)
        value["metadata"].setdefault(
            "generation_product_build_id", value["metadata"].get("product_build_id")
        )
        value["metadata"]["product_build_id"] = runner.expected_build_id
        value["receipt_id"] = task_scoped_artifact_receipt_id(
            task_id=task["task_id"],
            revision_id=revision,
            artifact_id=value["artifact_id"],
            artifact_type=value["artifact_type"],
            content_sha256=value["sha256"],
        )
        receipts.append(value)
    return receipts


def safe_projection(
    item: dict[str, Any], plan_projection: dict[str, Any], authority: dict[str, Any]
) -> dict[str, Any]:
    envelope = item["envelope"]
    projected = project_figure_mapping_for_user(
        envelope["mapping"], trusted_actor_receipt=authority
    )
    comparison = envelope["accepted_j7"]["persisted_comparison"]
    # Reuse the already safe/verified reference descriptor projection. Never expose
    # raw mapping authority, session, staging path, auxiliary HTML, or raw contracts.
    return {
        **deepcopy(plan_projection),
        "mapping_status": "REGISTERED_VALIDATED",
        "mapping_sha256": envelope["mapping"]["mapping_sha256"],
        "background": deepcopy(projected["background"]),
        "independent_review": {
            "status": comparison["status"],
            "decision": comparison["decision"],
            "rationale": comparison.get("rationale")
            or "当前任务 J7 已接受的独立比较；最终映射不重新选择胜者。",
        },
        "publication_asset": {
            k: envelope["mapping"]["assets"]["publication"][k]
            for k in ("artifact_id", "sha256")
        },
        "browser_visual_acceptance": "not_claimed",
        "external_action_authorized": False,
    }
