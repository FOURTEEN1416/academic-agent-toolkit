"""Build a self-contained manual-review page for one FigMirror job."""

from __future__ import annotations

import html
import hashlib
import json
import shutil
from pathlib import Path
from time import time_ns
from typing import Any

from .config import load_config


def _read_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _candidate_lineage(
    candidate_dir: Path,
    candidate_id: str,
    *,
    required: bool,
    pipeline: str = "image_blueprint",
) -> dict[str, Any] | None:
    direct_vector = pipeline == "direct_vector"
    raster_first = pipeline == "high_resolution_raster"
    img2ppt = pipeline == "img2ppt_hybrid"
    path = candidate_dir / (
        "lineage_img2ppt_v1.json"
        if img2ppt
        else "lineage_raster_v1.json"
        if raster_first
        else "lineage_vector_v1.json"
        if direct_vector
        else "lineage_v3.json"
    )
    if not path.is_file():
        if required:
            raise ValueError(f"{candidate_dir}: {path.name} is required for isolated schematic conversion")
        return None
    lineage = _read_object(path)
    if str(lineage.get("candidate_id")) != candidate_id:
        raise ValueError(f"{path}: candidate_id does not match candidate folder")
    if img2ppt:
        if lineage.get("pipeline") != "img2ppt_hybrid":
            raise ValueError(f"{path}: pipeline must be img2ppt_hybrid")
        for collection in ("sources", "outputs"):
            records = lineage.get(collection)
            if not isinstance(records, list) or not records:
                raise ValueError(f"{path}: {collection} records are required")
            for record in records:
                if not isinstance(record, dict):
                    raise ValueError(f"{path}: every {collection} record must be an object")
                asset = Path(str(record.get("path") or ""))
                if not asset.is_absolute():
                    asset = candidate_dir / asset
                if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                    raise ValueError(f"{path}: an Img2PPT {collection} asset is missing or changed")
        replacements = lineage.get("real_replacements")
        if not isinstance(replacements, list) or not replacements:
            raise ValueError(f"{path}: at least one real replacement is required")
        return lineage
    if raster_first:
        expected_chain = ["reference", "master_composition", "tile_refinement", "programmatic_annotations", "raster_final"]
        if lineage.get("artifact_chain") != expected_chain:
            raise ValueError(f"{path}: artifact_chain must preserve reference→master→tiles→annotations→final raster")
        references = lineage.get("references", [])
        if not isinstance(references, list):
            raise ValueError(f"{path}: references must be a list")
        for record in references:
            if not isinstance(record, dict):
                raise ValueError(f"{path}: every reference record must be an object")
            asset = Path(str(record.get("resolved_path") or record.get("path") or ""))
            if not asset.is_absolute():
                asset = candidate_dir / asset
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: raster-schematic reference is missing or its sha256 does not match")
        for name in ("master_composition",):
            record = lineage.get(name)
            if not isinstance(record, dict):
                raise ValueError(f"{path}: {name} record is required")
            asset = Path(str(record.get("path") or ""))
            if not asset.is_absolute():
                asset = candidate_dir / asset
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: {name} asset is missing or its sha256 does not match")
        tile_refinement = lineage.get("tile_refinement")
        annotations = lineage.get("programmatic_annotations")
        raster_final = lineage.get("raster_final")
        if not all(isinstance(item, dict) for item in (tile_refinement, annotations, raster_final)):
            raise ValueError(f"{path}: tile_refinement, programmatic_annotations, and raster_final records are required")
        for record in tile_refinement.get("assets", []):
            asset = Path(str(record.get("path") or ""))
            if not asset.is_absolute():
                asset = candidate_dir / asset
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: a tile asset is missing or changed")
        for record in (annotations.get("source"), annotations.get("layer"), raster_final.get("png")):
            if not isinstance(record, dict):
                raise ValueError(f"{path}: annotation source/layer and final PNG are required")
            asset = Path(str(record.get("path") or ""))
            if not asset.is_absolute():
                asset = candidate_dir / asset
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: raster lineage asset is missing or changed")
        if lineage.get("ai_text_prohibited") is not True or lineage.get("programmatic_annotations_required") is not True:
            raise ValueError(f"{path}: raster lineage must prohibit AI text and require programmatic annotations")
        if lineage.get("vector_final_required") is not False:
            raise ValueError(f"{path}: raster lineage must not require a vector final")
        return lineage
    if direct_vector:
        expected_chain = ["reference", "blueprint_ir", "vector_blueprint", "render_feedback", "vector_final"]
        if lineage.get("artifact_chain") != expected_chain:
            raise ValueError(f"{path}: artifact_chain must preserve reference→IR→SVG→feedback→final SVG")
        for name in ("blueprint_ir", "vector_blueprint", "render_feedback", "vector_final"):
            record = lineage.get(name)
            if not isinstance(record, dict):
                raise ValueError(f"{path}: {name} record is required")
            asset = candidate_dir / str(record.get("path") or "")
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: {name} asset is missing or its sha256 does not match")
        references = lineage.get("references", [])
        if not isinstance(references, list):
            raise ValueError(f"{path}: references must be a list")
        for record in references:
            if not isinstance(record, dict):
                raise ValueError(f"{path}: every reference record must be an object")
            asset = Path(str(record.get("path") or ""))
            if not asset.is_file() or str(record.get("sha256") or "").upper() != _sha256(asset):
                raise ValueError(f"{path}: direct-vector reference is missing or its sha256 does not match")
        if lineage.get("blueprint_image_inputs") != [] or lineage.get("prior_blueprint_image_input") is not False:
            raise ValueError(f"{path}: direct-vector lineage must contain no raster blueprint image inputs")
        if lineage.get("semantic_fields_locked") is not True:
            raise ValueError(f"{path}: direct-vector lineage must lock semantic fields")
        return lineage
    chain = lineage.get("artifact_chain")
    if not isinstance(chain, list) or chain != ["reference", "blueprint", "geometry_ir", "vector", "overlay"]:
        raise ValueError(f"{path}: artifact_chain must preserve reference→blueprint→geometry_ir→vector→overlay")
    reference = lineage.get("reference")
    blueprint = lineage.get("blueprint")
    geometry = lineage.get("geometry_ir")
    vector_source = lineage.get("vector_source")
    vector = lineage.get("vector")
    if not all(isinstance(item, dict) for item in (reference, blueprint, geometry, vector_source, vector)):
        raise ValueError(f"{path}: reference, blueprint, geometry_ir, vector_source, and vector records are required")
    for name, record in (
        ("reference", reference),
        ("blueprint", blueprint),
        ("vector_source", vector_source),
        ("vector", vector),
    ):
        asset = candidate_dir / str(record.get("path") or "")
        if name == "reference":
            asset = (candidate_dir / str(record.get("path") or "")).resolve()
        if not asset.is_file():
            raise ValueError(f"{path}: {name} asset does not exist: {asset}")
        declared = str(record.get("sha256") or "").upper()
        actual = _sha256(asset)
        if declared != actual:
            raise ValueError(f"{path}: {name} sha256 does not match {asset}")
    geometry_path = candidate_dir / str(geometry.get("path") or "")
    if not geometry_path.is_file():
        raise ValueError(f"{path}: geometry_ir asset does not exist: {geometry_path}")
    geometry_record = _read_object(geometry_path)
    modules = geometry_record.get("modules")
    if not isinstance(modules, list) or not modules:
        raise ValueError(f"{geometry_path}: modules are required")
    expected_ids = [str(item.get("svg_id")) for item in modules if isinstance(item, dict) and item.get("svg_id")]
    svg_text = (candidate_dir / str(vector.get("path"))).read_text(encoding="utf-8")
    missing_ids = [module_id for module_id in expected_ids if f'id="{module_id}"' not in svg_text]
    if missing_ids:
        raise ValueError(f"{path}: vector is missing geometry-IR SVG module IDs: {missing_ids}")
    image_inputs = lineage.get("blueprint_image_inputs")
    if not isinstance(image_inputs, list) or len(image_inputs) != 1:
        raise ValueError(f"{path}: blueprint_image_inputs must contain exactly one reference")
    if str(image_inputs[0].get("role")) != "only_visual_reference":
        raise ValueError(f"{path}: the sole blueprint image input must have role only_visual_reference")
    if lineage.get("prior_blueprint_image_input") is not False:
        raise ValueError(f"{path}: prior_blueprint_image_input must be false")
    return lineage


def _copy_evidence(source: str | None, assets_dir: Path, stem: str, *, base_dir: Path | None = None) -> str | None:
    if not source:
        return None
    source_path = Path(source)
    if not source_path.is_absolute() and base_dir is not None:
        source_path = base_dir / source_path
    if not source_path.is_file():
        return None
    suffix = source_path.suffix.lower() or ".bin"
    destination = assets_dir / f"{stem}{suffix}"
    shutil.copy2(source_path, destination)
    return f"assets/{destination.name}?v={destination.stat().st_mtime_ns}"


def _write_reference_placeholder(assets_dir: Path, figure_id: str) -> str:
    destination = assets_dir / f"{figure_id}-reference-not-supplied.svg"
    safe_id = html.escape(figure_id)
    destination.write_text(
        """<svg xmlns="http://www.w3.org/2000/svg" width="960" height="540" viewBox="0 0 960 540">
<rect width="960" height="540" fill="#f4f7f8"/>
<rect x="36" y="36" width="888" height="468" rx="24" fill="#ffffff" stroke="#cbd6da" stroke-width="3" stroke-dasharray="12 10"/>
<text x="480" y="244" text-anchor="middle" font-family="Arial, sans-serif" font-size="34" font-weight="700" fill="#172027">No external reference supplied</text>
<text x="480" y="294" text-anchor="middle" font-family="Arial, sans-serif" font-size="22" fill="#55646b">This real-data case validates binding, generation, export, and review.</text>
<text x="480" y="342" text-anchor="middle" font-family="Arial, sans-serif" font-size="18" fill="#7b898f">"""
        + safe_id
        + """ · reference learning is marked not applicable</text>
</svg>
""",
        encoding="utf-8",
    )
    return f"assets/{destination.name}"


def _versioned_candidate_asset(candidate_dir: Path, relative_url: str, filename: str) -> str:
    """Return a cache-busted candidate asset URL when the file exists."""

    path = candidate_dir / filename
    return f"{relative_url}?v={path.stat().st_mtime_ns}" if path.is_file() else relative_url


def _candidate_record(
    job: Path,
    figure_id: str,
    candidate_id: str,
    *,
    reference_assets: dict[str, Any] | None = None,
    assets_dir: Path | None = None,
    require_lineage: bool = False,
    schematic_pipeline: str = "image_blueprint",
) -> dict[str, Any]:
    candidate_dir = job / "candidates" / figure_id / candidate_id
    if not candidate_dir.is_dir() and (job / "candidates" / candidate_id / "candidate.json").is_file():
        candidate_dir = job / "candidates" / candidate_id
    manifest = _read_object(candidate_dir / "candidate.json")
    lineage = _candidate_lineage(
        candidate_dir,
        candidate_id,
        required=require_lineage,
        pipeline=schematic_pipeline,
    )
    panel_manifest = _read_object(candidate_dir / "panel_manifest.json")
    raw_panels = panel_manifest.get("panels", [])
    if not isinstance(raw_panels, list) or not 2 <= len(raw_panels) <= 4:
        raise ValueError(f"{candidate_dir}: panel_manifest.json must declare 2–4 panels")
    panels: list[dict[str, Any]] = []
    for panel in raw_panels:
        if not isinstance(panel, dict):
            raise ValueError(f"{candidate_dir}: every panel declaration must be an object")
        panel_id = str(panel.get("panel_id") or "")
        if not panel_id:
            raise ValueError(f"{candidate_dir}: panel_id is required")
        relative_root = f"../candidates/{figure_id}/{candidate_id}/panels/{panel_id}"
        raster_first = schematic_pipeline == "high_resolution_raster"
        panels.append(
            {
                "panel_id": panel_id,
                "title": str(panel.get("label") or panel_id),
                "preview": _versioned_candidate_asset(
                    candidate_dir, f"{relative_root}.png", f"panels/{panel_id}.png"
                ),
                "exports": {
                    "png": f"{relative_root}.png",
                    **({"tiff": f"{relative_root}.tiff", "pdf": f"{relative_root}.pdf"} if raster_first else {"svg": f"{relative_root}.svg", "pdf": f"{relative_root}.pdf"}),
                },
            }
        )
    limitations = manifest.get("visual_judge", {}).get("limitations", [])
    limitation = limitations[0] if isinstance(limitations, list) and limitations else ""
    title = str(manifest.get("title") or f"Candidate {candidate_id}")
    note = f"{title}。{limitation}" if limitation else title
    layouts = {2: "1x2", 3: "hero-top", 4: "2x2"}
    vector_preview_name = "figure.png" if schematic_pipeline == "img2ppt_hybrid" else "preview.png"
    vector_preview = _versioned_candidate_asset(
        candidate_dir,
        f"../candidates/{figure_id}/{candidate_id}/{vector_preview_name}",
        vector_preview_name,
    )
    review_views: list[dict[str, str]] = []
    default_blueprint = (
        "master_composition.png"
        if schematic_pipeline == "high_resolution_raster" and (candidate_dir / "master_composition.png").is_file()
        else "blueprint_preview.png"
        if (candidate_dir / "blueprint_preview.png").is_file()
        else "blueprint-v1.png"
    )
    blueprint_name = Path(str(manifest.get("blueprint") or default_blueprint)).name
    blueprint = candidate_dir / blueprint_name
    if blueprint.is_file():
        vector_first = blueprint_name == "blueprint_preview.png"
        raster_first = blueprint_name == "master_composition.png"
        review_views.append(
            {
                "key": "blueprint",
                "label": "AI 全局构图" if raster_first else "AI 矢量蓝图" if vector_first else "AI 视觉蓝图",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/{blueprint_name}",
                    blueprint_name,
                ),
                "note": (
                    "锁定对象位置、层级与阅读顺序的无文字全局母图；分块时只作为四块重绘的共享构图约束。"
                    if raster_first
                    else "由 blueprint.svg 渲染的反馈预览；SVG/IR 才是权威源，预览不参与反向追踪。"
                    if vector_first
                    else "用于确认构图、复杂度与视觉方向；不是最终可编辑导出文件。"
                ),
            }
        )
    region_assets: list[dict[str, Any]] = []
    canvas_preview_name = Path(str(manifest.get("canvas_preview") or "canvas-reconstruction.png")).name
    canvas_svg_name = Path(str(manifest.get("canvas_vector") or "canvas-reconstruction.svg")).name
    canvas_pdf_name = Path(str(manifest.get("canvas_pdf") or "canvas-reconstruction.pdf")).name
    canvas_preview_path = candidate_dir / canvas_preview_name
    canvas_svg_path = candidate_dir / canvas_svg_name
    canvas_pdf_path = candidate_dir / canvas_pdf_name
    canvas_manifest_path = candidate_dir / str(
        manifest.get("canvas_region_manifest") or "canvas_region_manifest.json"
    )
    canvas_review_path = candidate_dir / str(
        manifest.get("canvas_region_review") or "canvas-region-review.png"
    )
    if canvas_preview_path.is_file() and canvas_svg_path.is_file() and canvas_pdf_path.is_file():
        review_views.append(
            {
                "key": "canvas-vector",
                "label": "整图画布矢量重建",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/{canvas_preview_name}",
                    canvas_preview_name,
                ),
                "note": "在同一张蓝图画布中逐区域语义重建；不是独立模块拼接，SVG、PDF 与 PNG 完整导出对应此版本。",
            }
        )
    if canvas_review_path.is_file():
        review_views.append(
            {
                "key": "region-review",
                "label": "逐区域叠图审查",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/{canvas_review_path.name}",
                    canvas_review_path.name,
                ),
                "note": "蓝图、整图矢量和 50% 叠图并排；下方可进入每个锁定区域并分别导出。",
            }
        )
    if canvas_manifest_path.is_file():
        canvas_manifest = _read_object(canvas_manifest_path)
        raw_regions = canvas_manifest.get("regions", [])
        if isinstance(raw_regions, list):
            for raw in raw_regions:
                if not isinstance(raw, dict):
                    continue
                comparison = str(raw.get("comparison") or "").replace("\\", "/")
                exports = raw.get("exports") if isinstance(raw.get("exports"), dict) else {}
                comparison_path = candidate_dir / comparison
                if not comparison or not comparison_path.is_file():
                    continue
                region_assets.append(
                    {
                        "region_id": str(raw.get("region_id") or "region"),
                        "panel_id": raw.get("panel_id"),
                        "title": str(raw.get("title") or raw.get("region_id") or "Region"),
                        "comparison": _versioned_candidate_asset(
                            candidate_dir,
                            f"../candidates/{figure_id}/{candidate_id}/{comparison}",
                            comparison,
                        ),
                        "exports": {
                            key: f"../candidates/{figure_id}/{candidate_id}/{str(value).replace(chr(92), '/')}"
                            for key, value in exports.items()
                            if key in {"png", "svg", "pdf"}
                        },
                    }
                )
    module_assets: list[dict[str, str]] = []
    module_root = job / "ppt_modules"
    module_manifest_path = module_root / "module_manifest.json"
    module_sheet = module_root / f"module-review-{candidate_id}.png"
    if module_manifest_path.is_file() and module_sheet.is_file():
        module_manifest = _read_object(module_manifest_path)
        raw_module_slides = module_manifest.get("slides", [])
        if isinstance(raw_module_slides, list):
            for raw in raw_module_slides:
                if not isinstance(raw, dict) or str(raw.get("candidate")) != candidate_id:
                    continue
                svg_name = str(raw.get("svg") or "").replace("\\", "/")
                svg_path = module_root / svg_name
                if not svg_name or not svg_path.is_file():
                    continue
                module_assets.append(
                    {
                        "module_id": str(raw.get("module_id") or "module"),
                        "title": str(raw.get("title") or raw.get("module_id") or "Module"),
                        "svg": f"../ppt_modules/{svg_name}?v={svg_path.stat().st_mtime_ns}",
                    }
                )
        review_views.append(
            {
                "key": "ppt-modules",
                "label": "PPT 逐模块重建",
                "path": f"../ppt_modules/{module_sheet.name}?v={module_sheet.stat().st_mtime_ns}",
                "note": "每个模块由 PowerPoint 原生形状独立构建，并分别导出 SVG；点击下方模块可逐个放大审查。",
            }
        )
    dual_path = None
    dual_path_file = candidate_dir / str(manifest.get("dual_path_manifest") or "dual_path_manifest.json")
    if dual_path_file.is_file():
        dual_path = _read_object(dual_path_file)
        native = dual_path.get("native", {})
        native_preview_name = Path(str(native.get("preview") or "native-vector.png")).name
        if (candidate_dir / native_preview_name).is_file():
            review_views.append(
                {
                    "key": "native",
                    "label": "原生视觉矢量",
                    "path": _versioned_candidate_asset(
                        candidate_dir,
                        f"../candidates/{figure_id}/{candidate_id}/{native_preview_name}",
                        native_preview_name,
                    ),
                    "note": f"{dual_path.get('resolved_provider', 'native')} 生成的纯路径视觉层；文字与科学语义不可信，不会自动覆盖语义层。",
                }
            )
    if schematic_pipeline == "img2ppt_hybrid":
        source_image = candidate_dir / "source_image.png"
        if source_image.is_file():
            review_views.append(
                {
                    "key": "img2ppt-source",
                    "label": "转换前 AI 源图",
                    "path": _versioned_candidate_asset(candidate_dir, f"../candidates/{figure_id}/{candidate_id}/source_image.png", "source_image.png"),
                    "note": "只有 pre_conversion_review.json 全部通过后，才允许进入 Image-to-PPT 重建。",
                }
            )
        review_views.extend(
            [
                {
                    "key": "img2ppt-reconstruction",
                    "label": "可编辑语义重建",
                    "path": vector_preview,
                    "note": "文字、箭头、边框、节点和连接线均为原生 PowerPoint 对象。",
                },
                {
                    "key": "img2ppt-replacements",
                    "label": "真实图像替换",
                    "path": vector_preview,
                    "note": "仅声明的无文字复杂对象使用真实图像资产；禁止整页图片。",
                },
                {
                    "key": "img2ppt-final",
                    "label": "Img2PPT 混合成品",
                    "path": vector_preview,
                    "note": "PPTX 是可编辑交付源；PNG 是经真实替换后的渲染证据。",
                },
            ]
        )
    elif schematic_pipeline == "high_resolution_raster":
        stitched = candidate_dir / "stitched_base.png"
        annotations = candidate_dir / "annotation_layer.png"
        if stitched.is_file():
            review_views.append(
                {
                    "key": "raster-stitch",
                    "label": "高分辨率底图",
                    "path": _versioned_candidate_asset(candidate_dir, f"../candidates/{figure_id}/{candidate_id}/stitched_base.png", "stitched_base.png"),
                    "note": "单次高分辨率底图，或带重叠的 2×2 重绘拼接结果；不包含文字、箭头和边框。",
                }
            )
        if annotations.is_file():
            review_views.append(
                {
                    "key": "raster-annotations",
                    "label": "程序标注层",
                    "path": _versioned_candidate_asset(candidate_dir, f"../candidates/{figure_id}/{candidate_id}/annotation_layer.png", "annotation_layer.png"),
                    "note": "由可编辑 annotation_layout.json 在最终像素尺寸上生成的文字、箭头、边框、图例与数据调用层。",
                }
            )
        review_views.append(
            {
                "key": "raster-final",
                "label": "高分辨率栅格成品",
                "path": vector_preview,
                "note": "PNG/TIFF 为论文交付；文字和箭头仍可通过 annotation_layout.json 修改后重渲染。",
            }
        )
    else:
        review_views.append(
            {
                "key": "vector",
                "label": "可编辑矢量成品",
                "path": vector_preview,
                "note": "SVG、PDF、PNG 与分图导出均对应这一版本。",
            }
        )
    hybrid_name = Path(str(manifest.get("hybrid_preview") or "hybrid-vector.png")).name
    hybrid_path = candidate_dir / hybrid_name
    if hybrid_path.is_file():
        review_views.append(
            {
                "key": "hybrid",
                "label": "双路径分层成品",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/{hybrid_name}",
                    hybrid_name,
                ),
                "note": "语义层默认可见；原生视觉路径作为独立可编辑层保留，只有通过模块级门禁后才允许启用。",
            }
        )
    dual_review = candidate_dir / "dual-path-review.png"
    if dual_review.is_file():
        review_views.append(
            {
                "key": "dual-review",
                "label": "双路径三联审查",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/dual-path-review.png",
                    "dual-path-review.png",
                ),
                "note": "并排比较原生视觉矢量、科学语义矢量与分层融合结果。",
            }
        )
    overlay = candidate_dir / "overlay-review.png"
    if overlay.is_file():
        review_views.append(
            {
                "key": "overlay",
                "label": "蓝图—矢量叠图",
                "path": _versioned_candidate_asset(
                    candidate_dir,
                    f"../candidates/{figure_id}/{candidate_id}/overlay-review.png",
                    "overlay-review.png",
                ),
                "note": "用于检查结构继承与科学纠错，不作为论文导出文件。",
            }
        )
    reference = None
    raw_reference = (reference_assets or {}).get(candidate_id)
    if isinstance(raw_reference, list) and raw_reference and assets_dir is not None:
        first = raw_reference[0]
        if isinstance(first, str):
            first = {"path": first}
        if isinstance(first, dict):
            copied = _copy_evidence(
                str(first.get("path") or ""), assets_dir, f"{figure_id}-{candidate_id}-reference", base_dir=job
            )
            if copied:
                reference = {
                    "label": str(first.get("label") or f"Candidate {candidate_id} 参考图"),
                    "path": copied,
                    "note": str(first.get("note") or "仅迁移视觉与论证机制，不复制原论文数据和结论。"),
                }
                for key in (
                    "paper_title",
                    "venue",
                    "year",
                    "tier",
                    "figure_number",
                    "paper_url",
                    "doi_url",
                    "complete_figure",
                ):
                    if key in first:
                        reference[key] = first[key]
    default_review_view = (
        "raster-final"
        if any(item["key"] == "raster-final" for item in review_views)
        else "img2ppt-final"
        if any(item["key"] == "img2ppt-final" for item in review_views)
        else "canvas-vector"
        if any(item["key"] == "canvas-vector" for item in review_views)
        else "hybrid"
        if any(item["key"] == "hybrid" for item in review_views)
        else review_views[0]["key"]
    )
    return {
        "panel_count": len(panels),
        "layout": layouts[len(panels)],
        "title": title,
        "panel_ids": [panel["panel_id"] for panel in panels],
        "note": note,
        "panels": panels,
        "full_preview": (
            next((item["path"] for item in review_views if item["key"] == default_review_view), review_views[0]["path"])
        ),
        "vector_preview": vector_preview,
        "default_review_view": default_review_view,
        "review_views": review_views,
        "full_exports": (
            {
                "png": f"../candidates/{figure_id}/{candidate_id}/figure.png",
                "tiff": f"../candidates/{figure_id}/{candidate_id}/figure.tiff",
                "pdf": f"../candidates/{figure_id}/{candidate_id}/figure.pdf" if (candidate_dir / "figure.pdf").is_file() else None,
            }
            if schematic_pipeline == "high_resolution_raster"
            else {
                "pptx": f"../candidates/{figure_id}/{candidate_id}/figure.pptx",
                "png": f"../candidates/{figure_id}/{candidate_id}/figure.png",
                "pdf": f"../candidates/{figure_id}/{candidate_id}/figure.pdf" if (candidate_dir / "figure.pdf").is_file() else None,
            }
            if schematic_pipeline == "img2ppt_hybrid"
            else {
            "svg": (
                f"../candidates/{figure_id}/{candidate_id}/{canvas_svg_name}"
                if canvas_svg_path.is_file()
                else f"../candidates/{figure_id}/{candidate_id}/hybrid-vector.svg"
                if (candidate_dir / "hybrid-vector.svg").is_file()
                else f"../candidates/{figure_id}/{candidate_id}/figure.svg"
            ),
            "png": (
                f"../candidates/{figure_id}/{candidate_id}/{canvas_preview_name}"
                if canvas_preview_path.is_file()
                else f"../candidates/{figure_id}/{candidate_id}/hybrid-vector.png"
                if (candidate_dir / "hybrid-vector.png").is_file()
                else f"../candidates/{figure_id}/{candidate_id}/preview.png"
            ),
            "pdf": (
                f"../candidates/{figure_id}/{candidate_id}/{canvas_pdf_name}"
                if canvas_pdf_path.is_file()
                else f"../candidates/{figure_id}/{candidate_id}/hybrid-vector.pdf"
                if (candidate_dir / "hybrid-vector.pdf").is_file()
                else f"../candidates/{figure_id}/{candidate_id}/figure.pdf"
            ),
        }),
        "comparison_pdf": (
            f"../candidates/{figure_id}/{candidate_id}/review.pdf"
            if (candidate_dir / "review.pdf").is_file()
            else None
        ),
        "reference": reference,
        "lineage": lineage,
        "dual_path": dual_path,
        "module_assets": module_assets,
        "module_pptx": "../ppt_modules/CARBON_module_atlas.pptx" if module_assets else None,
        "region_assets": region_assets,
    }


def build_review(job_dir: str | Path, *, template_dir: str | Path | None = None) -> dict[str, Any]:
    """Materialize ``review/`` from job configuration and finalized candidates."""

    job = Path(job_dir).resolve()
    config = load_config(job / "figmirror.config.json")
    template = Path(template_dir).resolve() if template_dir else Path(__file__).resolve().parents[2] / "figmirror" / "review-template"
    review_dir = job / "review"
    assets_dir = review_dir / "assets"
    assets_dir.mkdir(parents=True, exist_ok=True)
    for name in ("index.html", "styles.css", "app.js"):
        source = template / name
        if not source.is_file():
            raise ValueError(f"review template file is missing: {source}")
        shutil.copy2(source, review_dir / name)

    index_path = review_dir / "index.html"
    index_text = index_path.read_text(encoding="utf-8")
    build_token = time_ns()
    index_text = index_text.replace('href="styles.css"', f'href="styles.css?v={build_token}"')
    index_text = index_text.replace('src="review-data.js"', f'src="review-data.js?v={build_token}"')
    index_text = index_text.replace('src="app.js"', f'src="app.js?v={build_token}"')
    index_path.write_text(index_text, encoding="utf-8")

    figures: list[dict[str, Any]] = []
    for index, figure in enumerate(config["figures"], start=1):
        figure_id = str(figure["figure_id"])
        reference_path = _copy_evidence(
            figure["reference_assets"][0] if figure["reference_assets"] else None,
            assets_dir,
            f"{figure_id}-reference",
            base_dir=job,
        )
        reference_supplied = reference_path is not None
        if not reference_path:
            reference_path = _write_reference_placeholder(assets_dir, figure_id)
        existing_path = _copy_evidence(
            figure.get("current_figure"), assets_dir, f"{figure_id}-existing", base_dir=job
        )
        candidate_references = figure.get("candidate_reference_assets")
        conversion = config.get("schematic_conversion", {})
        require_lineage = bool(
            figure["figure_kind"] == "schematic" and conversion.get("require_candidate_lineage")
        )
        configured_ids = tuple("ABC"[: int(config["candidate_count"])])
        available_ids = tuple(
            candidate_id
            for candidate_id in ("A", "B", "C")
            if (job / "candidates" / figure_id / candidate_id / "candidate.json").is_file()
            or (job / "candidates" / candidate_id / "candidate.json").is_file()
        )
        # The configured candidate count is authoritative for the review UI.
        # Older candidate folders may remain for provenance, but must not silently
        # re-enter an A/B run merely because they still exist on disk.
        configured_available_ids = tuple(candidate_id for candidate_id in configured_ids if candidate_id in available_ids)
        candidate_ids = configured_available_ids or available_ids or configured_ids
        candidates = {
            candidate_id: _candidate_record(
                job,
                figure_id,
                candidate_id,
                reference_assets=candidate_references if isinstance(candidate_references, dict) else None,
                assets_dir=assets_dir,
                require_lineage=require_lineage,
                schematic_pipeline=str(figure.get("schematic_pipeline") or "image_blueprint"),
            )
            for candidate_id in candidate_ids
        }
        if require_lineage:
            reference_hashes = [
                str(reference["sha256"]).upper()
                for candidate_id in candidate_ids
                for reference in [candidates[candidate_id]["lineage"].get("reference")]
                if isinstance(reference, dict) and reference.get("sha256")
            ]
            if len(reference_hashes) != len(set(reference_hashes)):
                raise ValueError(f"{figure_id}: schematic candidates must not share the same visual reference")
            required_views = set(conversion.get("required_review_views", []))
            for candidate_id in candidate_ids:
                available_views = {item["key"] for item in candidates[candidate_id]["review_views"]}
                missing = required_views - ({"reference"} | available_views)
                if missing:
                    raise ValueError(f"{figure_id}/{candidate_id}: missing required review views: {sorted(missing)}")
        first_panels = candidates[candidate_ids[0]]["panels"]
        original = None
        if existing_path:
            original = {
                "label": "已有图 · 升级前",
                "path": existing_path,
                "note": "来自原项目，作为内容、图位和改进基线。",
            }
            original_metadata = figure.get("current_figure_metadata")
            if isinstance(original_metadata, dict):
                original.update(original_metadata)
                original["path"] = existing_path
        figures.append(
            {
                "figure_id": figure_id,
                "number": f"{index:02d}",
                "kind": "数据图" if figure["figure_kind"] == "data" else "示意图",
                "claim": figure["claim"],
                "reference": {
                    "label": "论文参考图" if reference_supplied else "论文参考图 · 本案例未提供",
                    "path": reference_path,
                    "note": "仅学习表达机制，禁止复制数值和结论。" if reference_supplied else "本案例不进行外部参考学习；相似度与参考学习标为不适用。",
                },
                "original": original,
                "current": None,
                "panel_pool": first_panels,
                "candidates": candidates,
            }
        )

    data: dict[str, Any] = {
        "schema_version": "0.4",
        "project_id": config["project_id"],
        "workflow_settings": {
            "candidate_count": config["candidate_count"],
            "review_points": config["review_points"],
            "available_candidate_count": max(len(figure["candidates"]) for figure in figures),
        },
        "figures": figures,
        "batch_comparison_pdf": (
            str(config.get("batch_review_export")).replace("\\", "/").removeprefix("review/")
            if config.get("batch_review_export")
            and (job / str(config.get("batch_review_export"))).is_file()
            else None
        ),
        "initial_decisions": {
            figure["figure_id"]: {"selected_candidate": next(iter(figure["candidates"])), "confirmed": False, "notes": ""} for figure in figures
        },
    }
    (review_dir / "review-data.json").write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (review_dir / "review-data.js").write_text(
        "window.FIGMIRROR_REVIEW_DATA = " + json.dumps(data, ensure_ascii=False, indent=2) + ";\n",
        encoding="utf-8",
    )
    return {
        "schema_version": "0.4",
        "status": "PASS",
        "project_id": config["project_id"],
        "figure_count": len(figures),
        "review_dir": str(review_dir),
        "index": str(review_dir / "index.html"),
        "review_data": str(review_dir / "review-data.json"),
    }
