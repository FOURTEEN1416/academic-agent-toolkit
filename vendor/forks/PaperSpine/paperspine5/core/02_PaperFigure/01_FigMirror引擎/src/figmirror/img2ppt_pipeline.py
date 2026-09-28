"""Strict AI-image to editable PowerPoint hybrid workflow.

The source image is a visual draft, not the publication artifact. Img2PPT
reconstructs text, connectors, frames, and regular nodes as native PowerPoint
objects, then embeds only declared, text-free complex visual assets.
"""

from __future__ import annotations

import json
import zipfile
from pathlib import Path
from typing import Any, Iterable
from xml.etree import ElementTree as ET

from PIL import Image

from .data import sha256_file

IMG2PPT_PIPELINE = "img2ppt_hybrid"
PRE_REVIEW_KEYS = (
    "scientific_content_verified",
    "object_inventory_complete",
    "topology_verified",
    "labels_verified",
    "reference_layout_learned_not_copied",
    "ai_text_errors_absent",
    "source_resolution_sufficient",
    "replacement_inventory_complete",
)
POST_REVIEW_KEYS = (
    "scientific_structure_preserved",
    "editable_structure_preserved",
    "real_assets_replaced",
    "replacement_crops_correct",
    "no_image_covers_editable_text",
    "no_unresolved_placeholders",
    "final_render_legible",
)

P = "http://schemas.openxmlformats.org/presentationml/2006/main"
A = "http://schemas.openxmlformats.org/drawingml/2006/main"
NS = {"p": P, "a": A}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _write_object(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _request(candidate: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    request = _read_object(candidate / "generation_request.json")
    architecture = request.get("architecture_contract")
    if request.get("figure_kind") != "schematic" or not isinstance(architecture, dict):
        raise ValueError("Img2PPT preparation requires a schematic generation request")
    if architecture.get("pipeline") != IMG2PPT_PIPELINE:
        raise ValueError("generation_request.json is not configured for img2ppt_hybrid")
    contract = request.get("img2ppt_contract")
    if not isinstance(contract, dict):
        raise ValueError("generation_request.json requires img2ppt_contract")
    return request, contract


def _require_review(path: Path, keys: Iterable[str], label: str) -> dict[str, Any]:
    review = _read_object(path)
    if str(review.get("status") or "").strip().upper() != "PASS":
        raise ValueError(f"{label} status must be PASS")
    for key in keys:
        if review.get(key) is not True:
            raise ValueError(f"{label} must confirm {key}")
    return review


def _blank_review(keys: Iterable[str]) -> dict[str, Any]:
    return {
        "schema_version": "0.1",
        "status": "PENDING",
        **{key: False for key in keys},
        "findings": [],
        "reviewer": None,
    }


def prepare_img2ppt_candidate(candidate_dir: str | Path) -> dict[str, Any]:
    """Write the conversion plan and blocking review templates."""

    candidate = Path(candidate_dir).resolve()
    request, contract = _request(candidate)
    plan = {
        "schema_version": "0.1",
        "status": "READY",
        "pipeline": IMG2PPT_PIPELINE,
        "candidate_id": request.get("candidate_id"),
        "figure_id": request.get("figure_id"),
        "stages": [
            "strict_pre_conversion_review",
            "semantic_powerpoint_reconstruction",
            "declared_real_asset_replacement",
            "machine_pptx_audit",
            "strict_post_conversion_review",
        ],
        "source": "source_image.png",
        "semantic_spec": "reconstruction_spec.json",
        "replacement_manifest": "replacement_manifest.json",
        "required_outputs": ["figure.pptx", "figure.png"],
        "hard_rules": {
            "full_slide_image_prohibited": bool(contract["prohibit_full_slide_image"]),
            "editable_text_required": bool(contract["require_editable_text"]),
            "editable_connectors_required": bool(contract["require_editable_connectors"]),
            "minimum_real_replacements": int(contract["minimum_real_replacements"]),
            "image_assets_must_contain_text": False,
        },
    }
    _write_object(candidate / "img2ppt_plan.json", plan)
    for name, keys in (
        ("pre_conversion_review.json", PRE_REVIEW_KEYS),
        ("post_conversion_review.json", POST_REVIEW_KEYS),
    ):
        path = candidate / name
        if not path.is_file():
            _write_object(path, _blank_review(keys))
    replacement = candidate / "replacement_manifest.json"
    if not replacement.is_file():
        _write_object(
            replacement,
            {
                "schema_version": "0.1",
                "pipeline": IMG2PPT_PIPELINE,
                "replacements": [],
                "rule": "Each entry must be approved, candidate-local, text-free, hashed, and embedded as a picture object.",
            },
        )
    return plan


def _xfrm_bbox(element: ET.Element) -> tuple[int, int, int, int] | None:
    xfrm = element.find(".//a:xfrm", NS)
    if xfrm is None:
        return None
    off = xfrm.find("a:off", NS)
    ext = xfrm.find("a:ext", NS)
    if off is None or ext is None:
        return None
    return tuple(int(node) for node in (off.get("x", "0"), off.get("y", "0"), ext.get("cx", "0"), ext.get("cy", "0")))


def audit_img2ppt_pptx(pptx_path: str | Path) -> dict[str, Any]:
    """Audit native objects and reject full-slide-picture pseudo-editability."""

    pptx = Path(pptx_path)
    failures: list[str] = []
    slides: list[dict[str, Any]] = []
    media_hashes: dict[str, str] = {}
    with zipfile.ZipFile(pptx) as archive:
        presentation = ET.fromstring(archive.read("ppt/presentation.xml"))
        size = presentation.find("p:sldSz", NS)
        slide_w = int(size.get("cx", "0")) if size is not None else 0
        slide_h = int(size.get("cy", "0")) if size is not None else 0
        slide_names = sorted(
            name for name in archive.namelist() if name.startswith("ppt/slides/slide") and name.endswith(".xml")
        )
        for name in slide_names:
            root = ET.fromstring(archive.read(name))
            text_values = [
                "".join((node.text or "") for node in shape.findall(".//a:t", NS)).strip()
                for shape in root.findall(".//p:sp", NS)
            ]
            text_values = [value for value in text_values if value]
            text_shapes = sum(1 for sp in root.findall(".//p:sp", NS) if any((t.text or "").strip() for t in sp.findall(".//a:t", NS)))
            shape_count = len(root.findall(".//p:sp", NS))
            native_line_shapes = sum(
                1
                for shape in root.findall(".//p:sp", NS)
                if (shape.find(".//a:prstGeom", NS) is not None)
                and shape.find(".//a:prstGeom", NS).get("prst") == "line"
            )
            connector_count = len(root.findall(".//p:cxnSp", NS)) + native_line_shapes
            pictures: list[dict[str, Any]] = []
            for picture in root.findall(".//p:pic", NS):
                props = picture.find("p:nvPicPr/p:cNvPr", NS)
                bbox = _xfrm_bbox(picture)
                area_ratio = 0.0
                if bbox and slide_w > 0 and slide_h > 0:
                    area_ratio = (bbox[2] * bbox[3]) / (slide_w * slide_h)
                pictures.append(
                    {
                        "name": props.get("name", "") if props is not None else "",
                        "description": props.get("descr", "") if props is not None else "",
                        "bbox_emu": list(bbox) if bbox else None,
                        "slide_area_ratio": round(area_ratio, 5),
                    }
                )
            slides.append(
                {
                    "path": name,
                    "native_shape_count": shape_count,
                    "editable_text_shape_count": text_shapes,
                    "connector_count": connector_count,
                    "picture_count": len(pictures),
                    "editable_text_values": text_values,
                    "pictures": pictures,
                }
            )
        for name in archive.namelist():
            if name.startswith("ppt/media/") and not name.endswith("/"):
                import hashlib

                media_hashes[name] = hashlib.sha256(archive.read(name)).hexdigest()

    totals = {
        "native_shape_count": sum(item["native_shape_count"] for item in slides),
        "editable_text_shape_count": sum(item["editable_text_shape_count"] for item in slides),
        "connector_count": sum(item["connector_count"] for item in slides),
        "picture_count": sum(item["picture_count"] for item in slides),
    }
    if totals["editable_text_shape_count"] <= 0:
        failures.append("PPTX contains no editable text shapes")
    if totals["connector_count"] <= 0:
        failures.append("PPTX contains no native connectors")
    if any(pic["slide_area_ratio"] >= 0.95 for slide in slides for pic in slide["pictures"]):
        failures.append("PPTX contains a picture covering at least 95% of a slide")
    return {
        "status": "FAIL" if failures else "PASS",
        "failures": failures,
        "slide_size_emu": [slide_w, slide_h],
        "totals": totals,
        "slides": slides,
        "media_sha256": media_hashes,
    }


def assemble_img2ppt_candidate(candidate_dir: str | Path) -> dict[str, Any]:
    """Validate the pre-review, genuine replacements, and editable PPTX."""

    candidate = Path(candidate_dir).resolve()
    request, contract = _request(candidate)
    _require_review(candidate / "pre_conversion_review.json", PRE_REVIEW_KEYS, "pre_conversion_review.json")
    source = candidate / "source_image.png"
    if not source.is_file():
        raise ValueError("Img2PPT candidate requires source_image.png")
    with Image.open(source) as image:
        width, height = image.size
    if width < int(contract["source_image_min_width_px"]) or height < int(contract["source_image_min_height_px"]):
        raise ValueError(f"source_image.png is too small: {width}x{height}")
    for name in ("reconstruction_spec.json", "replacement_manifest.json", "figure.pptx", "figure.png"):
        if not (candidate / name).is_file():
            raise ValueError(f"Img2PPT candidate requires {name}")

    manifest = _read_object(candidate / "replacement_manifest.json")
    replacements = manifest.get("replacements")
    if not isinstance(replacements, list):
        raise ValueError("replacement_manifest.json replacements must be a list")
    failures: list[str] = []
    declared_hashes: list[str] = []
    for index, entry in enumerate(replacements):
        if not isinstance(entry, dict):
            failures.append(f"replacement {index} must be an object")
            continue
        if entry.get("approved") is not True or entry.get("contains_text") is not False:
            failures.append(f"replacement {index} must be approved and text-free")
        raw_path = str(entry.get("asset") or "")
        asset = (candidate / raw_path).resolve()
        try:
            asset.relative_to(candidate)
        except ValueError:
            failures.append(f"replacement {index} is outside the candidate directory")
            continue
        if not asset.is_file():
            failures.append(f"replacement {index} asset is missing: {raw_path}")
            continue
        digest = sha256_file(asset)
        if entry.get("sha256") != digest:
            failures.append(f"replacement {index} SHA-256 does not match")
        declared_hashes.append(digest)
    if len(replacements) < int(contract["minimum_real_replacements"]):
        failures.append("not enough genuine image replacements were declared")

    pptx_audit = audit_img2ppt_pptx(candidate / "figure.pptx")
    failures.extend(pptx_audit["failures"])
    if pptx_audit["totals"]["picture_count"] < int(contract["minimum_real_replacements"]):
        failures.append("PPTX does not contain the required real image objects")
    embedded_hashes = set(pptx_audit["media_sha256"].values())
    missing_hashes = [digest for digest in declared_hashes if digest not in embedded_hashes]
    if missing_hashes:
        failures.append("one or more declared replacement assets are not embedded byte-for-byte in the PPTX")

    evidence_contract = request.get("data_evidence_consumer_contract")
    evidence_result: dict[str, Any] | None = None
    if isinstance(evidence_contract, dict) and evidence_contract.get("available") is True:
        bundle_path = candidate / str(evidence_contract.get("bundle_file") or "data_evidence_bundle.json")
        binding_path = candidate / str(evidence_contract.get("binding_file") or "schematic_evidence_binding.json")
        if not bundle_path.is_file() or not binding_path.is_file():
            failures.append("Img2PPT data evidence requires candidate-local bundle and binding files")
        else:
            bundle = _read_object(bundle_path)
            binding = _read_object(binding_path)
            if bundle.get("privacy", {}).get("aggregate_only") is not True or bundle.get("privacy", {}).get("row_level_data_included") is not False:
                failures.append("Img2PPT data evidence must remain aggregate-only")
            if str(binding.get("bundle_sha256") or "").lower() != sha256_file(bundle_path).lower():
                failures.append("Img2PPT data evidence bundle hash does not match its binding")
            selected = binding.get("selected_facts")
            if not isinstance(selected, list) or not selected:
                failures.append("Img2PPT data evidence binding requires selected_facts")
                selected = []
            visible_text = "\n".join(
                value for slide in pptx_audit["slides"] for value in slide.get("editable_text_values", [])
            )
            missing_text = [
                str(fact.get("display_text") or "")
                for fact in selected
                if isinstance(fact, dict)
                and str(fact.get("display_text") or "").strip()
                and str(fact.get("display_text")) not in visible_text
            ]
            if missing_text:
                failures.append("one or more aggregate evidence display_text values are absent from native PPT text")
            evidence_result = {
                "selected_fact_count": len(selected),
                "visible_fact_count": len(selected) - len(missing_text),
                "aggregate_only": True,
            }

    qa = {
        "schema_version": "0.1",
        "status": "FAIL" if failures else "PASS",
        "pipeline": IMG2PPT_PIPELINE,
        "failures": failures,
        "source_dimensions_px": [width, height],
        "replacement_count": len(replacements),
        "data_evidence": evidence_result,
        "pptx_audit": pptx_audit,
    }
    _write_object(candidate / "img2ppt_qa.json", qa)
    if failures:
        raise ValueError("Img2PPT QA failed: " + "; ".join(failures))

    sources = [source, candidate / "reconstruction_spec.json", candidate / "replacement_manifest.json"]
    lineage = {
        "schema_version": "0.1",
        "pipeline": IMG2PPT_PIPELINE,
        "candidate_id": request.get("candidate_id"),
        "sources": [
            {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in sources
        ],
        "outputs": [
            {"path": str(path.resolve()), "sha256": sha256_file(path), "bytes": path.stat().st_size}
            for path in (candidate / "figure.pptx", candidate / "figure.png")
        ],
        "real_replacements": replacements,
    }
    _write_object(candidate / "lineage_img2ppt_v1.json", lineage)
    _write_object(
        candidate / "img2ppt_manifest.json",
        {
            "schema_version": "0.1",
            "status": "PASS",
            "pipeline": IMG2PPT_PIPELINE,
            "pptx": "figure.pptx",
            "png": "figure.png",
            "source_image": "source_image.png",
            "replacement_manifest": "replacement_manifest.json",
            "qa": "img2ppt_qa.json",
            "lineage": "lineage_img2ppt_v1.json",
        },
    )
    return qa


def finalize_img2ppt_candidate(
    candidate_dir: str | Path,
    request: dict[str, Any] | None = None,
    process_paths: list[Path] | None = None,
    *,
    formats: Iterable[str] = ("pptx", "png"),
) -> dict[str, Any]:
    """Finalize only after machine QA and the strict post-conversion review."""

    candidate = Path(candidate_dir).resolve()
    requested = tuple(dict.fromkeys(str(item).lower() for item in formats))
    if not requested or set(requested) - {"pptx", "png", "pdf"}:
        raise ValueError("Img2PPT formats must be a non-empty subset of pptx,png,pdf")
    qa = assemble_img2ppt_candidate(candidate)
    _require_review(candidate / "post_conversion_review.json", POST_REVIEW_KEYS, "post_conversion_review.json")
    exports: dict[str, str] = {}
    for fmt in requested:
        path = candidate / f"figure.{fmt}"
        if path.is_file():
            exports[fmt] = str(path.resolve())
        elif fmt != "pdf":
            raise ValueError(f"Img2PPT candidate requires figure.{fmt}")
    payload = {
        "schema_version": "0.4",
        "status": "PASS",
        "candidate_id": (request or {}).get("candidate_id"),
        "figure_id": (request or {}).get("figure_id"),
        "figure_kind": "schematic",
        "generation_mode": "agent_native_img2ppt",
        "rendering_mode": "editable-pptx-with-declared-real-image-assets",
        "pptx_audit": qa["pptx_audit"],
        "exports": exports,
        "lineage": "lineage_img2ppt_v1.json",
        "next_gate": "candidate scoring and final review",
    }
    _write_object(candidate / "authoring_report.json", payload)
    return payload
