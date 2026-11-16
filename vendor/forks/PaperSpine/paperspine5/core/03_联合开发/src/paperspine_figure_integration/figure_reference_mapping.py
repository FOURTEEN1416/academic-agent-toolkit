"""Executable PaperSpine reference-figure mapping and neutral-background gate.

The contract is intentionally stricter than JSON Schema alone: it closes the
cross-field hashes, panel coverage, current subject, selection, independent
review, and actual rendered background.  A valid object is evidence for local
figure readiness only; it never authorizes external publication or submission.
"""

from __future__ import annotations

import hashlib
import io
import json
from copy import deepcopy
from pathlib import Path
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator
from referencing import Registry, Resource


CONTRACTS = Path(__file__).resolve().parents[2] / "contracts"
AUTHORITY_TABLE = (Path(__file__).resolve().parents[3]
                   / "01_PaperSpine4/src/skill/references/figure-reference-mapping.md")
NATIVE_METHOD_VERSION = "paper-spine/references/figure-reference-mapping.md#1.0"
_AUTHORITY_FIELDS = (
    "authority_kind",
    "principal_id",
    "session_id",
    "run_id",
    "attestation_input_id",
    "authority_table_sha256",
)


class FigureReferenceMappingError(ValueError):
    """Raised when a mapping or background receipt cannot be proven current."""


def canonical_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        (
            json.dumps(
                dict(value),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
            + "\n"
        ).encode("utf-8")
    ).hexdigest()


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def figure_authority_table_sha256() -> str:
    """Return exact canonical PaperSpine method bytes (legacy field name retained)."""

    try:
        return _sha256(AUTHORITY_TABLE)
    except OSError as exc:
        raise FigureReferenceMappingError(
            "canonical PaperSpine figure method is unavailable"
        ) from exc


def _schema(name: str = "figure-reference-mapping.schema.json") -> dict[str, Any]:
    return json.loads(
        (CONTRACTS / name).read_text(encoding="utf-8")
    )


def _schema_validate(name: str, value: dict[str, Any]) -> None:
    mapping_schema = _schema()
    registry = Registry().with_resource(
        mapping_schema["$id"], Resource.from_contents(mapping_schema)
    )
    errors = sorted(
        Draft202012Validator(_schema(name), registry=registry).iter_errors(value),
        key=lambda item: [str(part) for part in item.path],
    )
    if not errors:
        return
    first = errors[0]
    location = ".".join(str(part) for part in first.path) or "$"
    raise FigureReferenceMappingError(f"figure mapping {location}: {first.message}")


def _revision(value: Any) -> str:
    return str(value) if isinstance(value, (str, int)) else ""


def _panel_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [
        str(item.get("panel_id") if isinstance(item, Mapping) else item)
        for item in value
    ]


def _artifact_hashes(items: Sequence[Mapping[str, Any] | None]) -> set[str]:
    return {
        str(item.get("sha256"))
        for item in items
        if isinstance(item, Mapping) and item.get("sha256")
    }


def _validate_bbox(value: Sequence[Any], path: str) -> None:
    x, y, width, height = (float(item) for item in value)
    if x + width > 1.0 + 1e-9 or y + height > 1.0 + 1e-9:
        raise FigureReferenceMappingError(
            f"{path} escapes normalized canvas: x+w and y+h must be <= 1"
        )


def validate_trusted_figure_master_receipt(
    receipt: Mapping[str, Any],
) -> dict[str, Any]:
    """Validate a host-channel receipt without pretending its self-hash creates trust.

    The caller is responsible for supplying this object only after binding it to
    the current host actor and an immutable attestation. ProductRunner does that
    before invoking the plan/mapping validators.
    """

    trusted = deepcopy(dict(receipt))
    _schema_validate("figure-master-authority-receipt.schema.json", trusted)
    supplied_hash = trusted.pop("receipt_sha256")
    if supplied_hash != canonical_sha256(trusted):
        raise FigureReferenceMappingError(
            "trusted figure Master authority receipt hash is invalid"
        )
    trusted["receipt_sha256"] = supplied_hash
    return trusted


def _validate_authority(
    value: Mapping[str, Any],
    *,
    expected_master_principal: str | None,
    expected_master_session: str | None,
    expected_authority_table_sha256: str | None,
    expected_master_run: str | None,
    expected_attestation_input_id: str | None,
    trusted_actor_receipt: Mapping[str, Any] | None,
) -> None:
    signed = {
        key: value.get(key)
        for key in _AUTHORITY_FIELDS
    }
    if value.get("provenance_sha256") != canonical_sha256(signed):
        raise FigureReferenceMappingError(
            "mapping_authority.provenance_sha256 does not bind the exact Master authority"
        )

    expected: dict[str, Any]
    if trusted_actor_receipt is not None:
        trusted = validate_trusted_figure_master_receipt(trusted_actor_receipt)
        expected = {key: trusted.get(key) for key in _AUTHORITY_FIELDS}
        for field, explicit in (
            ("principal_id", expected_master_principal),
            ("session_id", expected_master_session),
            ("run_id", expected_master_run),
            ("attestation_input_id", expected_attestation_input_id),
            ("authority_table_sha256", expected_authority_table_sha256),
        ):
            if explicit is not None and expected[field] != explicit:
                raise FigureReferenceMappingError(
                    f"trusted figure Master receipt conflicts with expected {field}"
                )
    else:
        if not all(
            isinstance(item, str) and item
            for item in (
                expected_master_principal,
                expected_master_session,
                expected_authority_table_sha256,
            )
        ):
            raise FigureReferenceMappingError(
                "figure Master authority requires a trusted actor receipt or explicit "
                "principal/session/authority-table expectations"
            )
        expected = {
            "authority_kind": "paperspine_master",
            "principal_id": expected_master_principal,
            "session_id": expected_master_session,
            "run_id": expected_master_run,
            "attestation_input_id": expected_attestation_input_id,
            "authority_table_sha256": expected_authority_table_sha256,
        }

    for field in _AUTHORITY_FIELDS:
        if expected.get(field) is not None and value.get(field) != expected[field]:
            raise FigureReferenceMappingError(
                f"mapping_authority.{field} is not the trusted Master authority"
            )


def _validate_subject(
    value: Mapping[str, Any], expected_subject: Mapping[str, Any] | None
) -> None:
    if expected_subject is None:
        return
    if value.get("task_id") != expected_subject.get("task_id"):
        raise FigureReferenceMappingError("mapping subject task_id is stale")
    expected_revision = expected_subject.get(
        "revision_id", expected_subject.get("runner_revision")
    )
    if _revision(value.get("runner_revision")) != _revision(expected_revision):
        raise FigureReferenceMappingError("mapping subject runner_revision is stale")
    expected_snapshot = expected_subject.get("material_snapshot_sha256")
    if expected_snapshot is not None:
        if value.get("material_snapshot_sha256") != expected_snapshot:
            raise FigureReferenceMappingError(
                "mapping subject material snapshot is stale"
            )
        return
    input_hashes = expected_subject.get("input_hashes")
    if isinstance(input_hashes, Mapping) and value.get(
        "material_snapshot_sha256"
    ) not in set(input_hashes.values()):
        raise FigureReferenceMappingError(
            "mapping material snapshot is absent from the immutable subject"
        )


def _validate_registered_assets(
    mapping: Mapping[str, Any], registered_artifacts: Mapping[str, str] | None
) -> None:
    if registered_artifacts is None:
        return
    assets = mapping["assets"]
    bindings = [
        mapping.get("plan_binding"),
        assets.get("current"),
        *assets["candidates"],
        assets["selected"],
        assets["publication"],
        assets["editable_source"],
    ]
    revision = _revision(mapping["subject"]["runner_revision"])
    for binding in bindings:
        if not isinstance(binding, Mapping):
            continue
        artifact_id = str(binding["artifact_id"])
        if registered_artifacts.get(artifact_id) != binding["sha256"]:
            raise FigureReferenceMappingError(
                f"mapping asset is not current in immutable subject: {artifact_id}"
            )
        # A final map is consumed at the plan's frozen revision, while J7
        # candidates may be registered during a later recovery revision.  The
        # binding is valid when it is no older than the frozen plan and no
        # newer than the current immutable subject; requiring equality would
        # reject the exact current J7 winner after a same-task redraw.
        if _revision(binding["revision_id"]) < revision:
            raise FigureReferenceMappingError(
                f"mapping asset revision is stale: {artifact_id}"
            )


def _validate_reference_semantics(value: Mapping[str, Any]) -> set[str]:
    """Close reference IDs, panel coverage, bboxes, and reference usage."""

    figure = value["figure"]
    panel_ids = list(figure["panel_ids"])
    if value["scientific_story"]["hero_panel_id"] not in set(panel_ids):
        raise FigureReferenceMappingError(
            "scientific_story.hero_panel_id is not a current figure panel"
        )
    reference_panels: dict[tuple[str, str], Mapping[str, Any]] = {}
    reference_hashes: set[str] = set()
    reference_ids: set[str] = set()
    for reference_index, reference in enumerate(value["reference_assets"]):
        reference_id = reference["reference_id"]
        if reference_id in reference_ids:
            raise FigureReferenceMappingError(
                f"duplicate reference_id: {reference_id}"
            )
        reference_ids.add(reference_id)
        reference_hashes.add(reference["asset_sha256"])
        local_panel_ids: set[str] = set()
        for panel_index, panel in enumerate(reference["panels"]):
            panel_id = panel["panel_id"]
            if panel_id in local_panel_ids:
                raise FigureReferenceMappingError(
                    f"duplicate reference panel: {reference_id}/{panel_id}"
                )
            local_panel_ids.add(panel_id)
            _validate_bbox(
                panel["bbox_normalized"],
                f"reference_assets[{reference_index}].panels[{panel_index}].bbox_normalized",
            )
            reference_panels[(reference_id, panel_id)] = panel

    mapping_rows = value["domain_mappings"]
    mapped_current: set[str] = set()
    used_reference_ids: set[str] = set()
    row_ids: set[str] = set()
    for index, row in enumerate(mapping_rows):
        row_id = row["mapping_row_id"]
        if row_id in row_ids:
            raise FigureReferenceMappingError(f"duplicate mapping_row_id: {row_id}")
        row_ids.add(row_id)
        current_panel = row["current_panel_id"]
        if current_panel not in panel_ids:
            raise FigureReferenceMappingError(
                f"domain_mappings[{index}] targets an unknown current panel"
            )
        mapped_current.add(current_panel)
        if row["source_kind"] == "reference_panel":
            key = (row["reference_id"], row["reference_panel_id"])
            if key not in reference_panels:
                raise FigureReferenceMappingError(
                    f"domain_mappings[{index}] references an unknown reference panel"
                )
            used_reference_ids.add(row["reference_id"])
    if mapped_current != set(panel_ids):
        missing = sorted(set(panel_ids) - mapped_current)
        raise FigureReferenceMappingError(
            f"every current panel must be mapped; missing: {', '.join(missing)}"
        )
    if value["design_provenance"] == "reference_guided" and (
        used_reference_ids != reference_ids
    ):
        unused = sorted(reference_ids - used_reference_ids)
        raise FigureReferenceMappingError(
            f"every declared reference asset must contribute a mapped panel; unused: {', '.join(unused)}"
        )
    return reference_hashes


def validate_figure_reference_plan(
    plan: Mapping[str, Any],
    *,
    expected_subject: Mapping[str, Any] | None = None,
    expected_figure: Mapping[str, Any] | None = None,
    registered_artifacts: Mapping[str, str] | None = None,
    expected_master_principal: str | None = None,
    expected_master_session: str | None = None,
    expected_authority_table_sha256: str | None = None,
    expected_master_run: str | None = None,
    expected_attestation_input_id: str | None = None,
    trusted_actor_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate a Master-owned plan against authority supplied out of band."""

    value = deepcopy(dict(plan))
    _schema_validate("figure-reference-plan.schema.json", value)
    supplied_hash = value.pop("plan_sha256")
    if supplied_hash != canonical_sha256(value):
        raise FigureReferenceMappingError(
            "plan_sha256 does not bind the exact pre-execution plan"
        )
    value["plan_sha256"] = supplied_hash
    _validate_authority(
        value["mapping_authority"],
        expected_master_principal=expected_master_principal,
        expected_master_session=expected_master_session,
        expected_authority_table_sha256=expected_authority_table_sha256,
        expected_master_run=expected_master_run,
        expected_attestation_input_id=expected_attestation_input_id,
        trusted_actor_receipt=trusted_actor_receipt,
    )
    _validate_subject(value["subject"], expected_subject)
    _validate_reference_semantics(value)
    if expected_figure is not None:
        figure = value["figure"]
        if figure["figure_id"] != expected_figure.get("figure_id"):
            raise FigureReferenceMappingError("reference plan figure_id does not match J7")
        if set(figure["panel_ids"]) != set(
            _panel_ids(expected_figure.get("panels"))
        ):
            raise FigureReferenceMappingError("reference plan panel set does not match J7")
        expected_producer = expected_figure.get("producer_id")
        if expected_producer and figure["producer_id"] != expected_producer:
            raise FigureReferenceMappingError(
                "reference plan producer does not match J7 producer"
            )
    if registered_artifacts is not None:
        for reference in value["reference_assets"]:
            for identifier, hash_field in (
                (reference["source_id"], "source_content_sha256"),
                (reference["asset_id"], "asset_sha256"),
                (reference["preview_artifact_id"], "preview_sha256"),
            ):
                if registered_artifacts.get(identifier) != reference[hash_field]:
                    raise FigureReferenceMappingError(
                        f"reference plan input is not current in immutable subject: {identifier}"
                    )
    return value


def validate_figure_reference_mapping(
    mapping: Mapping[str, Any],
    *,
    expected_subject: Mapping[str, Any] | None = None,
    expected_figure: Mapping[str, Any] | None = None,
    registered_artifacts: Mapping[str, str] | None = None,
    expected_plan: Mapping[str, Any] | None = None,
    expected_plan_artifact_id: str | None = None,
    expected_master_principal: str | None = None,
    expected_master_session: str | None = None,
    expected_authority_table_sha256: str | None = None,
    expected_master_run: str | None = None,
    expected_attestation_input_id: str | None = None,
    trusted_actor_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and return a defensive copy of one closed mapping receipt."""

    value = deepcopy(dict(mapping))
    _schema_validate("figure-reference-mapping.schema.json", value)

    supplied_hash = value.pop("mapping_sha256")
    if supplied_hash != canonical_sha256(value):
        raise FigureReferenceMappingError(
            "mapping_sha256 does not bind the exact mapping object"
        )
    value["mapping_sha256"] = supplied_hash
    _validate_authority(
        value["mapping_authority"],
        expected_master_principal=expected_master_principal,
        expected_master_session=expected_master_session,
        expected_authority_table_sha256=expected_authority_table_sha256,
        expected_master_run=expected_master_run,
        expected_attestation_input_id=expected_attestation_input_id,
        trusted_actor_receipt=trusted_actor_receipt,
    )
    _validate_subject(value["subject"], expected_subject)

    if expected_plan is not None:
        plan = validate_figure_reference_plan(
            expected_plan,
            expected_subject=expected_subject,
            expected_figure=expected_figure,
            registered_artifacts=registered_artifacts,
            expected_master_principal=expected_master_principal,
            expected_master_session=expected_master_session,
            expected_authority_table_sha256=expected_authority_table_sha256,
            expected_master_run=expected_master_run,
            expected_attestation_input_id=expected_attestation_input_id,
            trusted_actor_receipt=trusted_actor_receipt,
        )
        plan_binding = value["plan_binding"]
        if expected_plan_artifact_id and plan_binding[
            "artifact_id"
        ] != expected_plan_artifact_id:
            raise FigureReferenceMappingError(
                "final mapping plan binding uses the wrong artifact ID"
            )
        plan_binding_revision = _revision(plan_binding["revision_id"])
        plan_subject_revision = _revision(value["subject"]["runner_revision"])
        if (
            plan_binding["sha256"] != plan["plan_sha256"]
            or plan_binding_revision < plan_subject_revision
        ):
            raise FigureReferenceMappingError(
                "final mapping does not bind the exact current reference plan"
            )
        for key in (
            "mapping_id",
            "mapping_authority",
            "subject",
            "figure",
            "design_provenance",
            "reference_assets",
            "scientific_story",
            "domain_mappings",
            "grammar_reuse_justification",
        ):
            if value.get(key) != plan.get(key):
                raise FigureReferenceMappingError(
                    f"final mapping changed frozen reference plan field: {key}"
                )
        if value.get("original_design_rationale") != plan.get(
            "original_design_rationale"
        ):
            raise FigureReferenceMappingError(
                "final mapping changed frozen original design rationale"
            )

    figure = value["figure"]
    panel_ids = list(figure["panel_ids"])
    if expected_figure is not None:
        if figure["figure_id"] != expected_figure.get("figure_id"):
            raise FigureReferenceMappingError("mapping figure_id does not match J7")
        if set(panel_ids) != set(_panel_ids(expected_figure.get("panels"))):
            raise FigureReferenceMappingError("mapping panel set does not match J7")
        expected_producer = expected_figure.get("producer_id")
        if expected_producer and figure["producer_id"] != expected_producer:
            raise FigureReferenceMappingError(
                "mapping producer does not match J7 producer"
            )
        expected_current = expected_figure.get("current_asset")
        mapped_current = value["assets"].get("current")
        if isinstance(expected_current, Mapping):
            if not isinstance(mapped_current, Mapping) or {
                key: mapped_current.get(key) for key in ("artifact_id", "sha256")
            } != {
                key: expected_current.get(key) for key in ("artifact_id", "sha256")
            }:
                raise FigureReferenceMappingError(
                    "mapping current asset does not match J7"
                )
        expected_candidates = expected_figure.get("candidate_assets")
        if isinstance(expected_candidates, list):
            expected_candidate_bindings = {
                (str(item.get("artifact_id")), str(item.get("sha256")))
                for item in expected_candidates
                if isinstance(item, Mapping)
            }
            mapped_candidate_bindings = {
                (str(item.get("artifact_id")), str(item.get("sha256")))
                for item in value["assets"]["candidates"]
            }
            if mapped_candidate_bindings != expected_candidate_bindings:
                raise FigureReferenceMappingError(
                    "mapping candidate assets do not match J7"
                )
        comparison = expected_figure.get("independent_comparison")
        if isinstance(comparison, Mapping) and value["assets"]["selected"][
            "sha256"
        ] != comparison.get("selected_sha256"):
            raise FigureReferenceMappingError(
                "mapping selected asset does not match the J7 comparison winner"
            )

    reference_hashes = _validate_reference_semantics(value)

    assets = value["assets"]
    candidates = list(assets["candidates"])
    candidate_hashes = _artifact_hashes(candidates)
    current_hashes = _artifact_hashes([assets.get("current")])
    selectable_hashes = candidate_hashes | current_hashes
    if assets["selected"]["sha256"] not in selectable_hashes:
        raise FigureReferenceMappingError(
            "selected asset is neither the declared current asset nor a candidate"
        )
    if assets["publication"]["sha256"] != assets["selected"]["sha256"]:
        raise FigureReferenceMappingError(
            "publication asset hash must equal the independently selected asset hash"
        )
    if candidates and len(candidate_hashes) != len(candidates):
        raise FigureReferenceMappingError("candidate asset hashes must be unique")
    _validate_registered_assets(value, registered_artifacts)

    background = value["background"]
    unsigned_background = {
        key: item for key, item in background.items() if key != "receipt_sha256"
    }
    if background["receipt_sha256"] != canonical_sha256(unsigned_background):
        raise FigureReferenceMappingError(
            "background.receipt_sha256 does not bind the exact background receipt"
        )
    if background["asset_sha256"] != assets["publication"]["sha256"]:
        raise FigureReferenceMappingError(
            "background receipt does not bind the exact publication asset"
        )
    background_panel_ids = [item["region_id"] for item in background["panels"]]
    if set(background_panel_ids) != set(panel_ids) or len(background_panel_ids) != len(
        panel_ids
    ):
        raise FigureReferenceMappingError(
            "background receipt must cover every current panel exactly once"
        )
    _validate_bbox(background["canvas"]["bbox_normalized"], "background.canvas")
    for family in ("axes", "panels"):
        for index, region in enumerate(background[family]):
            _validate_bbox(
                region["bbox_normalized"], f"background.{family}[{index}]"
            )

    review = value["independent_review"]
    producer_ids = set(review["producer_ids"])
    if figure["producer_id"] not in producer_ids:
        raise FigureReferenceMappingError(
            "independent review must declare the figure producer"
        )
    if review["reviewer_id"] in producer_ids or review["reviewer_id"] == figure[
        "producer_id"
    ]:
        raise FigureReferenceMappingError(
            "independent review reviewer aliases a producer"
        )
    if set(review["reviewed_reference_hashes"]) != reference_hashes:
        raise FigureReferenceMappingError(
            "independent review must cover every exact reference asset"
        )
    required_asset_hashes = _artifact_hashes(
        [
            assets.get("current"),
            *candidates,
            assets["selected"],
            assets["publication"],
            assets["editable_source"],
        ]
    )
    if set(review["reviewed_asset_hashes"]) != required_asset_hashes:
        raise FigureReferenceMappingError(
            "independent review must cover current, candidates, selected, publication, and editable source"
        )
    if review["selected_sha256"] != assets["selected"]["sha256"]:
        raise FigureReferenceMappingError(
            "independent review selected hash does not match assets.selected"
        )

    side_by_side = value["side_by_side"]
    left = side_by_side["left"]
    right_preview = side_by_side["right"]["preview"]
    if right_preview["source_asset_sha256"] != assets["publication"]["sha256"]:
        raise FigureReferenceMappingError(
            "side-by-side right preview does not bind the publication asset"
        )
    references_by_id = {
        item["reference_id"]: item for item in value["reference_assets"]
    }
    if left["kind"] == "reference_asset":
        reference = references_by_id.get(left["reference_id"])
        if (
            reference is None
            or left["preview"]["source_asset_sha256"]
            != reference["asset_sha256"]
        ):
            raise FigureReferenceMappingError(
                "side-by-side left preview does not bind its exact reference asset"
            )
    elif left["kind"] == "original_asset":
        current = assets.get("current")
        if (
            not isinstance(current, Mapping)
            or left["preview"]["source_asset_sha256"] != current["sha256"]
        ):
            raise FigureReferenceMappingError(
                "side-by-side original preview does not bind assets.current"
            )
    if registered_artifacts is not None:
        previews = [right_preview]
        if isinstance(left.get("preview"), Mapping):
            previews.append(left["preview"])
        for preview in previews:
            if registered_artifacts.get(preview["preview_artifact_id"]) != preview[
                "preview_sha256"
            ]:
                raise FigureReferenceMappingError(
                    "side-by-side preview is absent or stale in the immutable subject"
                )
        if registered_artifacts.get(side_by_side["surface_artifact_id"]) != side_by_side[
            "surface_sha256"
        ]:
            raise FigureReferenceMappingError(
                "side-by-side comparison surface is absent or stale in the immutable subject"
            )
    return value


def _render_rgba(path: Path):
    try:
        from PIL import Image
    except ImportError as exc:  # pragma: no cover - dependency gate
        raise FigureReferenceMappingError(
            "neutral-background probing requires Pillow"
        ) from exc

    suffix = path.suffix.lower()
    if suffix == ".svg":
        try:
            import cairosvg
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise FigureReferenceMappingError(
                "SVG background probing requires CairoSVG"
            ) from exc
        encoded = cairosvg.svg2png(bytestring=path.read_bytes())
        return Image.open(io.BytesIO(encoded)).convert("RGBA"), "svg_structure_and_pixel_probe"
    if suffix == ".pdf":
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - dependency gate
            raise FigureReferenceMappingError(
                "PDF background probing requires PyMuPDF"
            ) from exc
        document = fitz.open(path)
        try:
            if document.page_count != 1:
                raise FigureReferenceMappingError(
                    "figure PDF background probe requires exactly one page"
                )
            page = document[0]
            scale = min(4.0, max(1.0, 1600.0 / max(float(page.rect.width), 1.0)))
            pixmap = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False)
            image = Image.frombytes("RGB", [pixmap.width, pixmap.height], pixmap.samples)
            return image.convert("RGBA"), "pdf_render_and_pixel_probe"
        finally:
            document.close()
    try:
        return Image.open(path).convert("RGBA"), "pixel_connected_background"
    except OSError as exc:
        raise FigureReferenceMappingError(f"unsupported or unreadable figure: {path}") from exc


def _pixel_background(pixel: Sequence[int]) -> str | None:
    red, green, blue, alpha = (int(item) for item in pixel)
    if alpha == 0:
        return "transparent"
    if alpha == 255 and red == green == blue == 255:
        return "pure_white"
    return None


def _probe_region(image: Any, bbox: Sequence[float], path: str) -> str:
    width, height = image.size
    x, y, box_width, box_height = (float(item) for item in bbox)
    left = max(0, min(width - 1, int(round(x * width))))
    top = max(0, min(height - 1, int(round(y * height))))
    right = max(left + 1, min(width, int(round((x + box_width) * width))))
    bottom = max(top + 1, min(height, int(round((y + box_height) * height))))
    region_width = right - left
    region_height = bottom - top
    band = max(1, min(6, int(round(min(region_width, region_height) * 0.02))))
    pixels: list[Sequence[int]] = []
    for yy in range(top, bottom):
        for xx in range(left, right):
            if (
                xx < left + band
                or xx >= right - band
                or yy < top + band
                or yy >= bottom - band
            ):
                pixels.append(image.getpixel((xx, yy)))
    classifications = [_pixel_background(pixel) for pixel in pixels]
    allowed = [item for item in classifications if item is not None]
    ratio = len(allowed) / max(len(classifications), 1)
    if ratio < 0.97:
        raise FigureReferenceMappingError(
            f"{path} has a colored background band ({ratio:.1%} exact transparent/white)"
        )
    transparent = sum(item == "transparent" for item in allowed)
    white = sum(item == "pure_white" for item in allowed)
    return "transparent" if transparent > white else "pure_white"


def build_figure_background_receipt(
    asset_path: str | Path,
    *,
    canvas_bbox: Sequence[float] = (0.0, 0.0, 1.0, 1.0),
    axes: Sequence[Mapping[str, Any]] = (),
    panels: Sequence[Mapping[str, Any]],
    publication_surface: bool = False,
    axes_not_applicable: bool = False,
) -> dict[str, Any]:
    """Render and probe one figure, returning a hash-bound PASS receipt.

    Each axes/panel entry requires ``region_id`` and ``bbox_normalized``.  The
    probe checks the inward border band of every declared region.  Semantic
    marks may be colored inside the region; a colored canvas/panel fill fails.
    """

    path = Path(asset_path).resolve()
    if not path.is_file():
        raise FigureReferenceMappingError(f"figure asset is missing: {path}")
    image, method = _render_rgba(path)

    def receipt_region(region_id: str, bbox: Sequence[float], label: str) -> dict[str, Any]:
        _validate_bbox(bbox, label)
        detected = _probe_region(image, bbox, label)
        if publication_surface and detected != "pure_white":
            raise FigureReferenceMappingError(
                f"{label} publication surface must render on exact pure white"
            )
        return {
            "region_id": region_id,
            "bbox_normalized": [float(item) for item in bbox],
            "detected_background": detected,
            "status": "PASS",
        }

    canvas = receipt_region("canvas", canvas_bbox, "canvas")
    axes_receipts = [
        receipt_region(
            str(item["region_id"]),
            item["bbox_normalized"],
            f"axes[{index}]",
        )
        for index, item in enumerate(axes)
    ]
    panel_receipts = [
        receipt_region(
            str(item["region_id"]),
            item["bbox_normalized"],
            f"panels[{index}]",
        )
        for index, item in enumerate(panels)
    ]
    if not panel_receipts:
        raise FigureReferenceMappingError(
            "background receipt requires at least one current panel"
        )
    receipt = {
        "policy": "transparent_master_white_publication",
        "probe_method": method,
        "probe_version": "paperspine-neutral-background/1.0",
        "probe_render_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
        "asset_sha256": _sha256(path),
        "canvas": canvas,
        "axes_inventory": {
            "status": "not_applicable" if axes_not_applicable else "complete"
        },
        "axes": axes_receipts,
        "panels": panel_receipts,
        "semantic_fill_allowed": True,
        "final_surface_status": "PASS",
    }
    receipt["receipt_sha256"] = canonical_sha256(receipt)
    return receipt


def project_figure_mapping_for_user(
    mapping: Mapping[str, Any],
    *,
    expected_master_principal: str | None = None,
    expected_master_session: str | None = None,
    expected_authority_table_sha256: str | None = None,
    trusted_actor_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Return the safe business view; omit machine authority and local paths."""

    value = validate_figure_reference_mapping(
        mapping,
        expected_master_principal=expected_master_principal,
        expected_master_session=expected_master_session,
        expected_authority_table_sha256=expected_authority_table_sha256,
        trusted_actor_receipt=trusted_actor_receipt,
    )
    references = []
    for reference in value["reference_assets"]:
        references.append(
            {
                "reference_id": reference["reference_id"],
                "source_id": reference["source_id"],
                "source_locator": reference["source_locator"],
                "figure_locator": reference["figure_locator"],
                "preview_artifact_id": reference["preview_artifact_id"],
                "preview_sha256": reference["preview_sha256"],
                "preview_media_type": reference["preview_media_type"],
                "asset_sha256": reference["asset_sha256"],
                "asset_sha256_short": reference["asset_sha256"][:12],
                "panels": [
                    {
                        key: panel[key]
                        for key in (
                            "panel_id",
                            "bbox_normalized",
                            "layout_role",
                            "mark_type",
                            "encodings",
                            "visual_hierarchy",
                            "reading_order",
                            "transferable_features",
                            "prohibited_transfer",
                        )
                    }
                    for panel in reference["panels"]
                ],
            }
        )
    return {
        "mapping_id": value["mapping_id"],
        "mapping_status": value["verification"]["status"],
        "figure": deepcopy(value["figure"]),
        "design_provenance": value["design_provenance"],
        "original_design_rationale": value.get("original_design_rationale"),
        "references": references,
        "scientific_story": deepcopy(value["scientific_story"]),
        "domain_mappings": deepcopy(value["domain_mappings"]),
        "grammar_reuse_justification": value.get("grammar_reuse_justification"),
        "selected_asset": {
            "artifact_id": value["assets"]["selected"]["artifact_id"],
            "sha256": value["assets"]["selected"]["sha256"],
        },
        "publication_asset": {
            "artifact_id": value["assets"]["publication"]["artifact_id"],
            "sha256": value["assets"]["publication"]["sha256"],
        },
        "side_by_side": deepcopy(value["side_by_side"]),
        "background": {
            "policy": value["background"]["policy"],
            "status": value["background"]["final_surface_status"],
            "canvas": value["background"]["canvas"]["detected_background"],
            "axes": [item["status"] for item in value["background"]["axes"]],
            "panels": [item["status"] for item in value["background"]["panels"]],
        },
        "independent_review": {
            "status": value["independent_review"]["status"],
            "decision": value["independent_review"]["decision"],
            "rationale": value["independent_review"]["rationale"],
        },
        "external_action_authorized": False,
    }


def project_figure_plan_for_user(
    plan: Mapping[str, Any],
    *,
    expected_master_principal: str | None = None,
    expected_master_session: str | None = None,
    expected_authority_table_sha256: str | None = None,
    trusted_actor_receipt: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Project a verified pre-execution plan without its machine authority."""

    value = validate_figure_reference_plan(
        plan,
        expected_master_principal=expected_master_principal,
        expected_master_session=expected_master_session,
        expected_authority_table_sha256=expected_authority_table_sha256,
        trusted_actor_receipt=trusted_actor_receipt,
    )
    return {
        "mapping_id": value["mapping_id"],
        "plan_status": "PASS",
        "figure": deepcopy(value["figure"]),
        "design_provenance": value["design_provenance"],
        "original_design_rationale": value.get("original_design_rationale"),
        "references": [
            {
                "reference_id": reference["reference_id"],
                "source_id": reference["source_id"],
                "source_locator": reference["source_locator"],
                "figure_locator": reference["figure_locator"],
                "asset_sha256": reference["asset_sha256"],
                "asset_sha256_short": reference["asset_sha256"][:12],
                "preview_artifact_id": reference["preview_artifact_id"],
                "preview_sha256": reference["preview_sha256"],
                "preview_media_type": reference["preview_media_type"],
                "panels": deepcopy(reference["panels"]),
            }
            for reference in value["reference_assets"]
        ],
        "scientific_story": deepcopy(value["scientific_story"]),
        "domain_mappings": deepcopy(value["domain_mappings"]),
        "grammar_reuse_justification": value.get("grammar_reuse_justification"),
        "external_action_authorized": False,
    }
