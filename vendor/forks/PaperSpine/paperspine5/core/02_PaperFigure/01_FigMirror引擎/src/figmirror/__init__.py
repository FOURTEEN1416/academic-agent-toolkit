"""FigMirror VNext core primitives.

The package is intentionally small and file-oriented so it can later be
embedded in PaperSpine without turning the writing workflow into a web app.
"""

from .config import ConfigError, load_config, validate_config
from .data_analysis import DataStudyError, render_data_study
from .evidence_bridge import (
    EvidenceBridgeError,
    bind_schematic_evidence,
    build_data_evidence_bundle,
    load_data_evidence_bundle,
    materialize_schematic_evidence,
    validate_data_evidence_bundle,
    validate_materialized_evidence_svg,
    validate_schematic_evidence_binding,
)
from .figure_spec import LayoutAudit, layout_figure_spec, render_figure_spec, validate_figure_spec
from .generation import finalize_agent_candidate, plan_agent_generation
from .img2ppt_pipeline import (
    assemble_img2ppt_candidate,
    audit_img2ppt_pptx,
    finalize_img2ppt_candidate,
    prepare_img2ppt_candidate,
)
from .overlay import build_overlay_sheet
from .panels import export_panels
from .ranking import rank_job
from .review import build_review
from .review_server import resolve_review_target, serve_review
from .raster_schematic import (
    assemble_raster_schematic,
    export_raster_panels,
    finalize_raster_candidate,
    prepare_raster_schematic,
)
from .svg import SvgAudit, audit_svg, render_scene
from .vector_blueprint import apply_vector_feedback, build_vector_blueprint, write_vector_lineage
from .vectorization import build_dual_path_vector, build_selective_vector_assets

__all__ = [
    "ConfigError",
    "DataStudyError",
    "EvidenceBridgeError",
    "LayoutAudit",
    "SvgAudit",
    "audit_svg",
    "audit_img2ppt_pptx",
    "apply_vector_feedback",
    "assemble_img2ppt_candidate",
    "assemble_raster_schematic",
    "build_review",
    "build_overlay_sheet",
    "build_dual_path_vector",
    "build_data_evidence_bundle",
    "build_selective_vector_assets",
    "build_vector_blueprint",
    "bind_schematic_evidence",
    "export_panels",
    "export_raster_panels",
    "finalize_agent_candidate",
    "finalize_img2ppt_candidate",
    "finalize_raster_candidate",
    "load_config",
    "load_data_evidence_bundle",
    "materialize_schematic_evidence",
    "layout_figure_spec",
    "plan_agent_generation",
    "prepare_raster_schematic",
    "prepare_img2ppt_candidate",
    "rank_job",
    "render_data_study",
    "render_scene",
    "render_figure_spec",
    "resolve_review_target",
    "serve_review",
    "validate_config",
    "validate_data_evidence_bundle",
    "validate_materialized_evidence_svg",
    "validate_figure_spec",
    "validate_schematic_evidence_binding",
    "write_vector_lineage",
]
