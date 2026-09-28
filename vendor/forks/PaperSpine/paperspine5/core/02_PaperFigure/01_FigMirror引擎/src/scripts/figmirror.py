#!/usr/bin/env python3
"""Command-line entry point for the standalone FigMirror VNext core."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1]
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from figmirror import (  # noqa: E402
    apply_vector_feedback,
    assemble_img2ppt_candidate,
    assemble_raster_schematic,
    audit_svg,
    bind_schematic_evidence,
    build_data_evidence_bundle,
    build_overlay_sheet,
    build_dual_path_vector,
    build_selective_vector_assets,
    build_vector_blueprint,
    build_review,
    export_panels,
    finalize_agent_candidate,
    load_config,
    plan_agent_generation,
    prepare_img2ppt_candidate,
    prepare_raster_schematic,
    rank_job,
    render_data_study,
    render_figure_spec,
    render_scene,
    serve_review,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="FigMirror VNext: traceable scientific figure workflow")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate-config", help="Validate and normalize figmirror.config.json")
    validate.add_argument("config")

    render = subparsers.add_parser("render-schematic", help="Render semantic scene JSON to editable SVG")
    render.add_argument("scene")
    render.add_argument("output")

    render_spec = subparsers.add_parser("render-figure-spec", help="Layout, route, audit, and render a semantic FigureSpec")
    render_spec.add_argument("spec")
    render_spec.add_argument("output")
    render_spec.add_argument("--layout-report")
    render_spec.add_argument("--panel-manifest")
    render_spec.add_argument("--allow-raster", action="store_true")

    audit = subparsers.add_parser("audit-svg", help="Audit SVG editability and safety")
    audit.add_argument("svg")
    audit.add_argument("--allow-raster", action="store_true")
    audit.add_argument("--require-text", action="store_true")

    rank = subparsers.add_parser("rank", help="Rank configured A/B or A/B/C candidates and conservatively auto-select")
    rank.add_argument("job_dir")

    build = subparsers.add_parser("build-review", help="Build the manual batch-review page from finalized candidates")
    build.add_argument("job_dir")

    plan = subparsers.add_parser("plan-agent", help="Create the configured two or three agent-native authoring requests")
    plan.add_argument("job_dir")

    finalize = subparsers.add_parser("finalize-candidate", help="Finalize one agent-authored candidate")
    finalize.add_argument("candidate_dir")
    finalize.add_argument(
        "--formats",
        default="auto",
        help="Comma-separated formats; auto selects svg,png,pdf for vector/data and png,tiff,pdf for raster schematics",
    )
    finalize.add_argument("--dpi", type=int, default=300)

    panels = subparsers.add_parser("export-panels", help="Export 2-4 declared panels as SVG, PNG, and PDF")
    panels.add_argument("source_svg")
    panels.add_argument("panel_manifest")
    panels.add_argument("output_dir")
    panels.add_argument("--formats", default="svg,png,pdf", help="Comma-separated subset of svg,png,pdf")
    panels.add_argument("--dpi", type=int, default=300)
    panels.add_argument("--allow-raster", action="store_true")

    overlay = subparsers.add_parser("build-overlay", help="Build a blueprint/vector/overlay visual-QA sheet")
    overlay.add_argument("blueprint")
    overlay.add_argument("vector_preview")
    overlay.add_argument("output")

    dual = subparsers.add_parser("dual-vectorize", help="Build native, semantic, and layered-hybrid SVG paths")
    dual.add_argument("job_dir")
    dual.add_argument("figure_id")
    dual.add_argument("candidate_id")
    dual.add_argument("--provider", choices=("auto", "recraft", "vtracer"), default="auto")
    dual.add_argument("--strength", type=float, default=0.18)

    prepare_vector = subparsers.add_parser(
        "prepare-vector-blueprint",
        help="Render blueprint IR directly to editable SVG and prepare visual feedback",
    )
    prepare_vector.add_argument("candidate_dir")
    prepare_vector.add_argument("--ir", help="Optional IR path; defaults to refined blueprint_ir, blueprint_ir, then figure_spec")
    prepare_vector.add_argument("--preview-width", type=int, default=1800)

    prepare_raster = subparsers.add_parser(
        "prepare-raster-schematic",
        help="Lock high-resolution pixels/PPI and prepare a single-pass or overlapping 2x2 raster plan",
    )
    prepare_raster.add_argument("candidate_dir")

    assemble_raster = subparsers.add_parser(
        "assemble-raster-schematic",
        help="Stitch optional redraw tiles and rasterize programmatic text/arrows/frames at final resolution",
    )
    assemble_raster.add_argument("candidate_dir")

    prepare_img2ppt = subparsers.add_parser(
        "prepare-img2ppt",
        help="Create strict review and real-replacement gates for an Img2PPT candidate",
    )
    prepare_img2ppt.add_argument("candidate_dir")

    assemble_img2ppt = subparsers.add_parser(
        "assemble-img2ppt",
        help="Audit native PPT objects and verify declared genuine image replacements",
    )
    assemble_img2ppt.add_argument("candidate_dir")

    apply_feedback = subparsers.add_parser(
        "apply-vector-feedback",
        help="Apply a constrained visual-feedback patch without changing scientific semantics",
    )
    apply_feedback.add_argument("candidate_dir")
    apply_feedback.add_argument("feedback")

    selective = subparsers.add_parser(
        "vectorize-regions",
        help="Vectorize only approved organic regions as optional FigureSpec assets",
    )
    selective.add_argument("job_dir")
    selective.add_argument("figure_id")
    selective.add_argument("candidate_id")
    selective.add_argument("region_manifest")
    selective.add_argument("--provider", choices=("auto", "recraft", "vtracer"), default="auto")

    review = subparsers.add_parser("serve-review", help="Serve one review job on loopback for safe downloads")
    review.add_argument("root", help="FigMirror job root; only this directory is served")
    review.add_argument("--index", default="review/index.html")
    review.add_argument("--port", type=int, default=0)
    review.add_argument("--open", action="store_true")

    data_study = subparsers.add_parser(
        "render-data-study",
        help="Profile a tabular research dataset and render an aggregate, traceable data figure",
    )
    data_study.add_argument("source")
    data_study.add_argument("output_dir")
    data_study.add_argument("--domain", choices=("clinical-cbc",), default="clinical-cbc")
    data_study.add_argument("--sheet")
    data_study.add_argument("--group-column", default="患者类别")
    data_study.add_argument("--sex-column", default="性别")
    data_study.add_argument("--age-column", default="年龄")
    data_study.add_argument("--diagnosis-column", default="临床诊断")
    data_study.add_argument("--metadata-columns", type=int, default=5)
    data_study.add_argument("--group-order", help="Comma-separated source labels in display order")
    data_study.add_argument("--hero-metric", default="WBC")
    data_study.add_argument("--title", default="Care-setting patterns in routine complete blood counts")
    data_study.add_argument("--dpi", type=int, default=300)

    export_evidence = subparsers.add_parser(
        "export-data-evidence",
        help="Publish an aggregate-only evidence bundle for schematic consumers",
    )
    export_evidence.add_argument("data_profile")
    export_evidence.add_argument("output", nargs="?")

    bind_evidence = subparsers.add_parser(
        "bind-schematic-evidence",
        help="Bind selected aggregate fact IDs to nodes in a schematic candidate",
    )
    bind_evidence.add_argument("candidate_dir")
    bind_evidence.add_argument("bundle")
    bind_evidence.add_argument("mapping")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        if args.command == "validate-config":
            result = load_config(args.config)
        elif args.command == "render-schematic":
            scene = json.loads(Path(args.scene).read_text(encoding="utf-8-sig"))
            output = render_scene(scene, args.output)
            result = audit_svg(output, require_text=False).to_dict()
        elif args.command == "render-figure-spec":
            spec_path = Path(args.spec)
            spec = json.loads(spec_path.read_text(encoding="utf-8-sig"))
            result = render_figure_spec(
                spec,
                args.output,
                layout_report=args.layout_report,
                panel_manifest=args.panel_manifest,
                asset_root=spec_path.parent,
                allow_raster=args.allow_raster,
            )
        elif args.command == "audit-svg":
            result = audit_svg(args.svg, allow_raster=args.allow_raster, require_text=args.require_text).to_dict()
        elif args.command == "rank":
            result = rank_job(args.job_dir)
        elif args.command == "build-review":
            result = build_review(args.job_dir)
        elif args.command == "plan-agent":
            result = plan_agent_generation(args.job_dir)
        elif args.command == "finalize-candidate":
            formats = None if args.formats.strip().lower() == "auto" else [item.strip() for item in args.formats.split(",") if item.strip()]
            result = finalize_agent_candidate(args.candidate_dir, formats=formats, dpi=args.dpi)
        elif args.command == "export-panels":
            formats = [item.strip() for item in args.formats.split(",") if item.strip()]
            result = export_panels(
                args.source_svg,
                args.panel_manifest,
                args.output_dir,
                formats=formats,
                dpi=args.dpi,
                allow_raster=args.allow_raster,
            )
        elif args.command == "build-overlay":
            result = build_overlay_sheet(args.blueprint, args.vector_preview, args.output)
        elif args.command == "dual-vectorize":
            result = build_dual_path_vector(
                args.job_dir,
                args.figure_id,
                args.candidate_id,
                provider=args.provider,
                strength=args.strength,
            )
        elif args.command == "prepare-vector-blueprint":
            result = build_vector_blueprint(
                args.candidate_dir,
                ir=args.ir,
                preview_width=args.preview_width,
            )
        elif args.command == "prepare-raster-schematic":
            result = prepare_raster_schematic(args.candidate_dir)
        elif args.command == "assemble-raster-schematic":
            result = assemble_raster_schematic(args.candidate_dir)
        elif args.command == "prepare-img2ppt":
            result = prepare_img2ppt_candidate(args.candidate_dir)
        elif args.command == "assemble-img2ppt":
            result = assemble_img2ppt_candidate(args.candidate_dir)
        elif args.command == "apply-vector-feedback":
            result = apply_vector_feedback(args.candidate_dir, args.feedback)
        elif args.command == "vectorize-regions":
            result = build_selective_vector_assets(
                args.job_dir,
                args.figure_id,
                args.candidate_id,
                args.region_manifest,
                provider=args.provider,
            )
        elif args.command == "render-data-study":
            group_order = [item.strip() for item in args.group_order.split(",") if item.strip()] if args.group_order else None
            result = render_data_study(
                args.source,
                args.output_dir,
                domain=args.domain,
                sheet_name=args.sheet,
                group_column=args.group_column,
                sex_column=args.sex_column,
                age_column=args.age_column,
                diagnosis_column=args.diagnosis_column,
                metadata_columns=args.metadata_columns,
                group_order=group_order,
                hero_metric=args.hero_metric,
                title=args.title,
                dpi=args.dpi,
            )
        elif args.command == "export-data-evidence":
            result = build_data_evidence_bundle(args.data_profile, args.output)
        elif args.command == "bind-schematic-evidence":
            result = bind_schematic_evidence(args.candidate_dir, args.bundle, args.mapping)
        elif args.command == "serve-review":
            serve_review(args.root, index=args.index, port=args.port, open_browser=args.open)
            return 0
        else:  # pragma: no cover
            raise ValueError(f"unsupported command: {args.command}")
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FigMirror failed: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if str(result.get("status", "PASS")).upper() != "FAIL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
