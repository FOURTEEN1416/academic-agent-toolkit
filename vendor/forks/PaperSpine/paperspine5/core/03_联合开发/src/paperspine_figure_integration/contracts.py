"""Host-neutral contracts and safe path handling for PaperSpine × FigMirror."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
INTEGRATION_JOB_SCHEMA_VERSIONS = {"1.0", "1.1"}
HOSTS = {"codex", "claude-code", "dsh", "standalone-skill"}
FIGURE_KINDS = {"data", "schematic"}
FIGURE_DECISIONS = {"keep", "redesign", "improve", "create"}
SCIENTIFIC_IDENTITY_REPAIR = "scientific_identity_error"
SCIENTIFIC_IDENTITY_SURFACES = (
    "final_pixels",
    "editable_source",
    "caption",
    "body_contract",
    "lineage_receipt",
)
DOCUMENT_LAYOUT_MODES = {"single_column", "two_column"}
COLUMN_SPANS = {"one_column", "two_column_span"}
PUBLICATION_ROLES = {"main", "supplementary", "omit"}
AUTHOR_CONFIRMATION_STATUSES = {"confirmed", "pending", "not_required"}
REVIEW_DECISION_VERSION = "1.1"
STORY_FIELDS = {
    "figure_role",
    "scientific_question",
    "intended_conclusion",
    "claim_boundary",
    "results_units",
    "hero_panel",
    "panels",
}
REVIEW_MODES = {"auto", "manual"}
REVIEW_POINTS = {"final_only", "blueprint_and_final"}
FORMATS = {"pdf", "svg", "png"}
PANEL_ACTIONS = {"keep", "lock", "revise"}
PDF_ENGINES = {"auto", "latexmk", "xelatex", "pdflatex", "tectonic"}
WORD_ENGINES = {"auto", "pandoc"}
IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
LATEX_LABEL = re.compile(r"^fig:[A-Za-z0-9][A-Za-z0-9._:-]*$")


class ContractError(ValueError):
    """Raised when an integration artifact violates the public contract."""


def load_json(path: str | Path) -> dict[str, Any]:
    target = Path(path)
    try:
        value = json.loads(target.read_text(encoding="utf-8-sig"))
    except FileNotFoundError as exc:
        raise ContractError(f"JSON file does not exist: {target}") from exc
    except json.JSONDecodeError as exc:
        raise ContractError(f"invalid JSON in {target}: {exc}") from exc
    if not isinstance(value, dict):
        raise ContractError(f"JSON root must be an object: {target}")
    return value


def write_json_atomic(path: str | Path, payload: dict[str, Any]) -> Path:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(f".{target.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(target)
    return target


def _mapping(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ContractError(f"{field} must be an object")
    return dict(value)


def _text(value: Any, field: str, minimum: int = 1) -> str:
    if not isinstance(value, str) or len(value.strip()) < minimum:
        raise ContractError(f"{field} must contain at least {minimum} character(s)")
    return value.strip()


def _string_list(value: Any, field: str, *, allow_empty: bool = True) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item.strip() for item in value):
        raise ContractError(f"{field} must be a list of non-empty strings")
    if not allow_empty and not value:
        raise ContractError(f"{field} must not be empty")
    return [item.strip() for item in value]


def _scientific_identity(value: Any, field: str) -> dict[str, Any]:
    identity = _mapping(value, field)
    authority_status = identity.get("authority_status")
    if authority_status not in {"verified", "unresolved"}:
        raise ContractError(f"{field}.authority_status must be verified or unresolved")
    canonical_name = _text(identity.get("canonical_name"), f"{field}.canonical_name")
    authority_artifact = _text(
        identity.get("authority_artifact"), f"{field}.authority_artifact"
    )
    authority_locator = _text(
        identity.get("authority_locator"), f"{field}.authority_locator"
    )
    forbidden_names = _string_list(
        identity.get("forbidden_names", []), f"{field}.forbidden_names"
    )
    if canonical_name.casefold() in {name.casefold() for name in forbidden_names}:
        raise ContractError(f"{field}.canonical_name cannot also be forbidden")
    locked_surfaces = _string_list(
        identity.get("locked_surfaces", list(SCIENTIFIC_IDENTITY_SURFACES)),
        f"{field}.locked_surfaces",
        allow_empty=False,
    )
    if set(locked_surfaces) != set(SCIENTIFIC_IDENTITY_SURFACES) or len(locked_surfaces) != len(
        SCIENTIFIC_IDENTITY_SURFACES
    ):
        raise ContractError(
            f"{field}.locked_surfaces must cover exactly {list(SCIENTIFIC_IDENTITY_SURFACES)}"
        )
    return {
        **identity,
        "authority_status": authority_status,
        "canonical_name": canonical_name,
        "authority_artifact": authority_artifact,
        "authority_locator": authority_locator,
        "forbidden_names": forbidden_names,
        "locked_surfaces": list(SCIENTIFIC_IDENTITY_SURFACES),
    }


def _positive_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or float(value) <= 0:
        raise ContractError(f"{field} must be a positive number")
    return float(value)


def _layout_profile(value: Any) -> dict[str, Any]:
    profile = _mapping(value, "layout_profile")
    mode = profile.get("document_layout_mode")
    if mode not in DOCUMENT_LAYOUT_MODES:
        raise ContractError("layout_profile.document_layout_mode must be single_column or two_column")
    one_width = _positive_number(
        profile.get("one_column_width_mm"), "layout_profile.one_column_width_mm"
    )
    span_width = profile.get("two_column_span_width_mm")
    if mode == "two_column":
        span_width = _positive_number(
            span_width, "layout_profile.two_column_span_width_mm"
        )
        if span_width <= one_width:
            raise ContractError(
                "layout_profile.two_column_span_width_mm must exceed one_column_width_mm"
            )
    elif span_width is not None:
        raise ContractError(
            "single_column layout must not declare two_column_span_width_mm"
        )
    render_dpi = profile.get("render_dpi", 300)
    if isinstance(render_dpi, bool) or not isinstance(render_dpi, int) or render_dpi < 72:
        raise ContractError("layout_profile.render_dpi must be an integer >= 72")
    return {
        **profile,
        "document_layout_mode": mode,
        "one_column_width_mm": one_width,
        **(
            {"two_column_span_width_mm": float(span_width)}
            if span_width is not None
            else {}
        ),
        "render_dpi": render_dpi,
    }


def _claim_coverage(value: Any, field: str) -> dict[str, Any]:
    coverage = _mapping(value, field)
    essential = _string_list(
        coverage.get("essential_main_claim_ids", []),
        f"{field}.essential_main_claim_ids",
    )
    narrowed = _string_list(
        coverage.get("narrowed_claim_ids", []),
        f"{field}.narrowed_claim_ids",
    )
    for name, values in (
        ("essential_main_claim_ids", essential),
        ("narrowed_claim_ids", narrowed),
    ):
        if len(values) != len(set(values)) or any(not IDENTIFIER.fullmatch(item) for item in values):
            raise ContractError(f"{field}.{name} must contain unique safe claim identifiers")
    if not set(narrowed).issubset(essential):
        raise ContractError(f"{field}.narrowed_claim_ids must be declared essential main claims")

    raw_replacements = coverage.get("replacement_support", [])
    if not isinstance(raw_replacements, list):
        raise ContractError(f"{field}.replacement_support must be a list")
    replacements: list[dict[str, str]] = []
    replacement_pairs: set[tuple[str, str]] = set()
    for index, raw_replacement in enumerate(raw_replacements):
        replacement = _mapping(raw_replacement, f"{field}.replacement_support[{index}]")
        claim_id = _text(
            replacement.get("claim_id"), f"{field}.replacement_support[{index}].claim_id"
        )
        figure_id = _text(
            replacement.get("figure_id"), f"{field}.replacement_support[{index}].figure_id"
        )
        if not IDENTIFIER.fullmatch(claim_id) or not IDENTIFIER.fullmatch(figure_id):
            raise ContractError(f"{field}.replacement_support must use safe claim and figure IDs")
        if claim_id not in essential:
            raise ContractError(
                f"{field}.replacement_support claim {claim_id} is not an essential main claim"
            )
        pair = (claim_id, figure_id)
        if pair in replacement_pairs:
            raise ContractError(f"{field}.replacement_support entries must be unique")
        replacement_pairs.add(pair)
        replacements.append({"claim_id": claim_id, "figure_id": figure_id})

    confirmation = coverage.get(
        "author_confirmation_status", "pending" if narrowed else "not_required"
    )
    if confirmation not in AUTHOR_CONFIRMATION_STATUSES:
        raise ContractError(
            f"{field}.author_confirmation_status must be confirmed, pending, or not_required"
        )
    if narrowed and confirmation != "confirmed":
        raise ContractError(
            f"{field} is BLOCKED: narrowed essential claims require author_confirmation_status=confirmed"
        )
    if not narrowed and confirmation == "pending":
        raise ContractError(f"{field}.author_confirmation_status cannot be pending without narrowed claims")
    return {
        **coverage,
        "essential_main_claim_ids": essential,
        "replacement_support": replacements,
        "narrowed_claim_ids": narrowed,
        "author_confirmation_status": confirmation,
    }


def resolve_within(root: Path, value: str | Path, field: str, *, must_exist: bool = False) -> Path:
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise ContractError(f"{field} escapes project_root: {resolved}") from exc
    if must_exist and not resolved.exists():
        raise ContractError(f"{field} does not exist: {resolved}")
    return resolved


def load_integration_job(path: str | Path) -> dict[str, Any]:
    job_path = Path(path).resolve()
    raw = load_json(job_path)
    job_schema_version = raw.get("schema_version")
    if job_schema_version not in INTEGRATION_JOB_SCHEMA_VERSIONS:
        raise ContractError(
            f"integration job schema_version must be one of {sorted(INTEGRATION_JOB_SCHEMA_VERSIONS)}"
        )
    job_id = _text(raw.get("job_id"), "job_id")
    if not IDENTIFIER.fullmatch(job_id):
        raise ContractError("job_id must use letters, numbers, dots, underscores, or hyphens")
    host = raw.get("host", "codex")
    if host not in HOSTS:
        raise ContractError("host must be codex, claude-code, dsh, or standalone-skill")

    root_raw = _text(raw.get("project_root"), "project_root")
    root_candidate = Path(root_raw)
    project_root = (job_path.parent / root_candidate).resolve() if not root_candidate.is_absolute() else root_candidate.resolve()
    if not project_root.is_dir():
        raise ContractError(f"project_root does not exist: {project_root}")
    if job_schema_version == "1.1":
        core_raw = _text(raw.get("core_root"), "core_root")
        core_candidate = Path(core_raw)
        core_root = (
            (job_path.parent / core_candidate).resolve()
            if not core_candidate.is_absolute()
            else core_candidate.resolve()
        )
        if not core_root.is_dir():
            raise ContractError(f"core_root does not exist: {core_root}")
        if core_root == project_root or core_root in project_root.parents or project_root in core_root.parents:
            raise ContractError("schema 1.1 core_root and project_root must be separate non-overlapping roots")
    else:
        core_root = project_root

    paper = _mapping(raw.get("paper"), "paper")
    figure = _mapping(raw.get("figure"), "figure")
    assembly = _mapping(raw.get("assembly", {}), "assembly")
    manuscript = _mapping(raw.get("manuscript", {}), "manuscript")
    publication = _mapping(raw.get("publication", {}), "publication")
    workflow = _mapping(raw.get("workflow", {}), "workflow")

    paper_output = resolve_within(project_root, _text(paper.get("output_dir"), "paper.output_dir"), "paper.output_dir")
    progress_script = resolve_within(
        core_root,
        paper.get("progress_script", "01_PaperSpine4/src/scripts/progress_check.py"),
        "paper.progress_script",
        must_exist=True,
    )
    request_name = _text(paper.get("figure_requests", "figure_requests.json"), "paper.figure_requests")
    if Path(request_name).is_absolute() or ".." in Path(request_name).parts:
        raise ContractError("paper.figure_requests must be a safe path relative to paper.output_dir")
    required_artifacts = _string_list(
        paper.get(
            "required_artifacts",
            [
                "paper_spine_config.json",
                "confirmed_motivation.md",
                "confirmed_contribution.md",
                "section_blueprints.md",
            ],
        ),
        "paper.required_artifacts",
        allow_empty=False,
    )

    figure_job = resolve_within(project_root, _text(figure.get("job_dir"), "figure.job_dir"), "figure.job_dir")
    figmirror_cli = resolve_within(
        core_root,
        figure.get("figmirror_cli", "02_PaperFigure/01_FigMirror引擎/src/scripts/figmirror.py"),
        "figure.figmirror_cli",
        must_exist=True,
    )
    candidate_count = figure.get("candidate_count", 2)
    if isinstance(candidate_count, bool) or candidate_count not in {2, 3}:
        raise ContractError("figure.candidate_count must be 2 or 3")
    review_mode = figure.get("review_mode", "manual")
    if review_mode not in REVIEW_MODES:
        raise ContractError("figure.review_mode must be auto or manual")
    review_points = figure.get("review_points", "final_only")
    if review_points not in REVIEW_POINTS:
        raise ContractError("figure.review_points is unsupported")
    preferred_format = figure.get("preferred_format", "pdf")
    if preferred_format not in FORMATS:
        raise ContractError("figure.preferred_format must be pdf, svg, or png")
    fallback_formats = _string_list(figure.get("fallback_formats", ["svg", "png"]), "figure.fallback_formats")
    if any(item not in FORMATS for item in fallback_formats):
        raise ContractError("figure.fallback_formats contains an unsupported format")
    quality_profile = figure.get("quality_profile", "publication")
    if quality_profile not in {"prototype", "publication"}:
        raise ContractError("figure.quality_profile must be prototype or publication")
    require_candidate_lineage = figure.get("require_candidate_lineage", False)
    if not isinstance(require_candidate_lineage, bool):
        raise ContractError("figure.require_candidate_lineage must be a boolean")

    final_paper_dir = resolve_within(
        project_root,
        assembly.get("final_paper_dir", str((paper_output / "final_paper").relative_to(project_root))),
        "assembly.final_paper_dir",
    )
    main_tex_value = assembly.get("main_tex", str((final_paper_dir / "main.tex").relative_to(project_root)))
    main_tex = resolve_within(project_root, main_tex_value, "assembly.main_tex")
    inject_tex_markers = assembly.get("inject_tex_markers", True)
    require_tex_markers = assembly.get("require_tex_markers", False)
    if not isinstance(inject_tex_markers, bool) or not isinstance(require_tex_markers, bool):
        raise ContractError("assembly marker options must be booleans")

    source_file = resolve_within(
        project_root,
        manuscript.get("source_file", str(main_tex.relative_to(project_root))),
        "manuscript.source_file",
    )
    pdf_file = resolve_within(
        project_root,
        manuscript.get("pdf_file", str((final_paper_dir / "paper.pdf").relative_to(project_root))),
        "manuscript.pdf_file",
    )
    config_path = paper_output / "paper_spine_config.json"
    paper_config = load_json(config_path) if config_path.is_file() else {}
    default_word_name = "paper.zh.docx" if paper_config.get("output_language") == "zh" else "paper.docx"
    word_file = resolve_within(
        project_root,
        manuscript.get("word_file", str((final_paper_dir / default_word_name).relative_to(project_root))),
        "manuscript.word_file",
    )
    revision_dir = resolve_within(
        project_root,
        manuscript.get(
            "revision_dir",
            str((paper_output / "manuscript_revisions").relative_to(project_root)),
        ),
        "manuscript.revision_dir",
    )
    pdf_engine = manuscript.get("pdf_engine", "auto")
    word_engine = manuscript.get("word_engine", "auto")
    if pdf_engine not in PDF_ENGINES:
        raise ContractError("manuscript.pdf_engine is unsupported")
    if word_engine not in WORD_ENGINES:
        raise ContractError("manuscript.word_engine is unsupported")
    require_pdf = manuscript.get("require_pdf", True)
    require_word = manuscript.get("require_word", paper_config.get("word_output", "docx") != "none")
    if not isinstance(require_pdf, bool) or not isinstance(require_word, bool):
        raise ContractError("manuscript output requirements must be booleans")
    default_receipt_groups = {
        "profile": [paper_output / "style_profile.md"],
        "length": [paper_output / "artifact_check.md", paper_output / "publication_surface_check.md"],
        "visual": [paper_output / "visual_audit_manifest.json", paper_output / "visual_readiness_check.md"],
        "five_dimension": [
            paper_output / "scientific_evidence_check.md",
            paper_output / "visual_readiness_check.md",
            paper_output / "citation_bank_check.md",
            paper_output / "citation_quality_audit.md",
            paper_output / "metadata_readiness_check.md",
            paper_output / "latex_report.md",
            paper_output / "publication_surface_check.md",
        ],
    }
    raw_receipt_groups = manuscript.get("receipt_groups")
    if raw_receipt_groups is not None and not isinstance(raw_receipt_groups, dict):
        raise ContractError("manuscript.receipt_groups must be an object")
    receipt_groups: dict[str, list[str]] = {}
    for group, defaults in default_receipt_groups.items():
        declared = (raw_receipt_groups or {}).get(group, [str(path) for path in defaults])
        values = _string_list(declared, f"manuscript.receipt_groups.{group}", allow_empty=False)
        receipt_groups[group] = [
            str(resolve_within(project_root, value, f"manuscript.receipt_groups.{group}"))
            for value in values
        ]
    publication_script = resolve_within(
        core_root,
        publication.get("script", "01_PaperSpine4/src/scripts/publication_cycle.py"),
        "publication.script",
        must_exist=True,
    )
    publication_invocation_dir = resolve_within(
        project_root,
        publication.get(
            "invocation_dir",
            str((paper_output / "publication_cycle" / "invocations").relative_to(project_root)),
        ),
        "publication.invocation_dir",
    )
    publication_enabled = publication.get("enabled", True)
    if not isinstance(publication_enabled, bool):
        raise ContractError("publication.enabled must be a boolean")
    allow_auto_selection = workflow.get("allow_auto_selection", False)
    if not isinstance(allow_auto_selection, bool):
        raise ContractError("workflow.allow_auto_selection must be a boolean")

    normalized = deepcopy(raw)
    normalized.update({"schema_version": job_schema_version, "job_id": job_id, "host": host})
    normalized["project_root"] = str(project_root)
    normalized["core_root"] = str(core_root)
    normalized["job_file"] = str(job_path)
    normalized["state_file"] = str(job_path.with_name("integration_state.json"))
    normalized["paper"] = {
        **paper,
        "output_dir": str(paper_output),
        "progress_script": str(progress_script),
        "figure_requests": request_name,
        "required_artifacts": required_artifacts,
    }
    normalized["figure"] = {
        **figure,
        "job_dir": str(figure_job),
        "figmirror_cli": str(figmirror_cli),
        "candidate_count": candidate_count,
        "review_mode": review_mode,
        "review_points": review_points,
        "preferred_format": preferred_format,
        "fallback_formats": fallback_formats,
        "quality_profile": quality_profile,
        "require_candidate_lineage": require_candidate_lineage,
    }
    normalized["assembly"] = {
        **assembly,
        "final_paper_dir": str(final_paper_dir),
        "main_tex": str(main_tex),
        "inject_tex_markers": inject_tex_markers,
        "require_tex_markers": require_tex_markers,
    }
    normalized["manuscript"] = {
        **manuscript,
        "source_file": str(source_file),
        "pdf_file": str(pdf_file),
        "word_file": str(word_file),
        "revision_dir": str(revision_dir),
        "pdf_engine": pdf_engine,
        "word_engine": word_engine,
        "require_pdf": require_pdf,
        "require_word": require_word,
        "receipt_groups": receipt_groups,
    }
    normalized["publication"] = {
        **publication,
        "script": str(publication_script),
        "invocation_dir": str(publication_invocation_dir),
        "enabled": publication_enabled,
    }
    normalized["workflow"] = {**workflow, "allow_auto_selection": allow_auto_selection}
    return normalized


def validate_figure_requests(raw: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"figure request schema_version must be {SCHEMA_VERSION}")
    paper_id = _text(raw.get("paper_id"), "paper_id")
    layout_profile = _layout_profile(raw["layout_profile"]) if "layout_profile" in raw else None
    figures = raw.get("figures")
    if not isinstance(figures, list) or not figures:
        raise ContractError("figures must be a non-empty list")
    normalized_figures: list[dict[str, Any]] = []
    seen: set[str] = set()
    for index, value in enumerate(figures):
        item = _mapping(value, f"figures[{index}]")
        figure_id = _text(item.get("figure_id"), f"figures[{index}].figure_id")
        if not IDENTIFIER.fullmatch(figure_id) or figure_id in seen:
            raise ContractError("figure_id values must be unique safe identifiers")
        seen.add(figure_id)
        kind = item.get("figure_kind")
        if kind not in FIGURE_KINDS:
            raise ContractError(f"figures[{index}].figure_kind must be data or schematic")
        claim = _text(item.get("claim"), f"figures[{index}].claim", minimum=12)
        caption = _text(item.get("caption"), f"figures[{index}].caption", minimum=4)
        label = _text(item.get("label", f"fig:{figure_id}"), f"figures[{index}].label")
        if not LATEX_LABEL.fullmatch(label):
            raise ContractError(f"figures[{index}].label must begin with fig: and use safe characters")
        source_data = _string_list(item.get("source_data", []), f"figures[{index}].source_data")
        if kind == "data" and not source_data:
            raise ContractError(f"data figure {figure_id} requires source_data")
        data_evidence = _string_list(item.get("data_evidence", []), f"figures[{index}].data_evidence")
        if kind != "schematic" and data_evidence:
            raise ContractError(f"data_evidence is only valid for schematic figure {figure_id}")
        references = _string_list(item.get("reference_assets", []), f"figures[{index}].reference_assets")
        decision = item.get("decision", "create")
        if decision not in FIGURE_DECISIONS:
            raise ContractError(f"figures[{index}].decision must be keep, redesign, improve, or create")
        current_figure = item.get("current_figure")
        if decision in {"keep", "redesign", "improve"}:
            current_figure = _text(
                current_figure,
                f"figures[{index}].current_figure",
            )
        elif current_figure is not None:
            current_figure = _text(current_figure, f"figures[{index}].current_figure")
        current_figure_sha256 = item.get("current_figure_sha256")
        if current_figure_sha256 is not None:
            current_figure_sha256 = _text(
                current_figure_sha256, f"figures[{index}].current_figure_sha256"
            ).upper()
            if not re.fullmatch(r"[0-9A-F]{64}", current_figure_sha256):
                raise ContractError(f"figures[{index}].current_figure_sha256 must be SHA-256")
        repair_reasons = _string_list(
            item.get("repair_reasons", []), f"figures[{index}].repair_reasons"
        )
        if len(repair_reasons) != len(set(repair_reasons)) or any(
            not IDENTIFIER.fullmatch(reason) for reason in repair_reasons
        ):
            raise ContractError(
                f"figures[{index}].repair_reasons must be unique safe identifiers"
            )
        scientific_identity = (
            _scientific_identity(
                item.get("scientific_identity"), f"figures[{index}].scientific_identity"
            )
            if "scientific_identity" in item
            else None
        )
        if SCIENTIFIC_IDENTITY_REPAIR in repair_reasons:
            if decision not in {"redesign", "improve"}:
                raise ContractError(
                    f"figures[{index}] scientific identity repair requires decision=redesign or improve"
                )
            if scientific_identity is None:
                raise ContractError(
                    f"figures[{index}] scientific identity repair requires scientific_identity"
                )
            if scientific_identity["authority_status"] != "verified":
                raise ContractError(
                    f"figures[{index}] scientific identity repair is BLOCKED until authority_status=verified"
                )
            if not scientific_identity["forbidden_names"]:
                raise ContractError(
                    f"figures[{index}] scientific identity repair requires forbidden_names"
                )
        placement: dict[str, Any] | None = None
        final_size_context: dict[str, Any] | None = None
        if layout_profile is not None:
            raw_placement = _mapping(item.get("placement", {}), f"figures[{index}].placement")
            column_span = raw_placement.get("column_span", "one_column")
            if column_span not in COLUMN_SPANS:
                raise ContractError(
                    f"figures[{index}].placement.column_span must be one_column or two_column_span"
                )
            if (
                layout_profile["document_layout_mode"] == "single_column"
                and column_span != "one_column"
            ):
                raise ContractError(
                    f"figures[{index}] single_column documents permit only one_column figures"
                )
            physical_width_mm = (
                layout_profile["two_column_span_width_mm"]
                if column_span == "two_column_span"
                else layout_profile["one_column_width_mm"]
            )
            placement = {**raw_placement, "column_span": column_span}
            final_size_context = {
                "document_layout_mode": layout_profile["document_layout_mode"],
                "column_span": column_span,
                "physical_width_mm": physical_width_mm,
                "render_dpi": layout_profile["render_dpi"],
            }
        elif "placement" in item:
            raise ContractError(
                f"figures[{index}].placement requires a root layout_profile"
            )

        publication_role = item.get("publication_role", "main")
        if publication_role not in PUBLICATION_ROLES:
            raise ContractError(
                f"figures[{index}].publication_role must be main, supplementary, or omit"
            )
        editorial_rationale = item.get("editorial_rationale")
        claim_coverage: dict[str, Any]
        if publication_role == "main":
            editorial_rationale = _text(
                editorial_rationale or "Retained in the main article.",
                f"figures[{index}].editorial_rationale",
                minimum=8,
            )
            claim_coverage = _claim_coverage(
                item.get(
                    "claim_coverage",
                    {
                        "essential_main_claim_ids": [],
                        "replacement_support": [],
                        "narrowed_claim_ids": [],
                        "author_confirmation_status": "not_required",
                    },
                ),
                f"figures[{index}].claim_coverage",
            )
        else:
            editorial_rationale = _text(
                editorial_rationale,
                f"figures[{index}].editorial_rationale",
                minimum=12,
            )
            if "claim_coverage" not in item:
                raise ContractError(
                    f"figures[{index}] {publication_role} disposition requires claim_coverage"
                )
            claim_coverage = _claim_coverage(
                item["claim_coverage"], f"figures[{index}].claim_coverage"
            )
            covered_claims = {
                replacement["claim_id"] for replacement in claim_coverage["replacement_support"]
            } | set(claim_coverage["narrowed_claim_ids"])
            uncovered = sorted(
                set(claim_coverage["essential_main_claim_ids"]) - covered_claims
            )
            if uncovered:
                raise ContractError(
                    f"figures[{index}] is BLOCKED: essential main claims lack replacement support or confirmed narrowing: {uncovered}"
                )

        # The richer scientific-story contract is backward compatible with
        # earlier figure requests, but atomic: once one story field is present,
        # all fields must be supplied so downstream generation and prose do not
        # reason from a partial storyboard.
        story_present = any(field in item for field in STORY_FIELDS)
        story: dict[str, Any] = {}
        if story_present:
            missing_story = sorted(field for field in STORY_FIELDS if field not in item)
            if missing_story:
                raise ContractError(
                    f"figures[{index}] has a partial scientific-story contract; missing {missing_story}"
                )
            scientific_question = _text(
                item.get("scientific_question"), f"figures[{index}].scientific_question", minimum=8
            )
            intended_conclusion = _text(
                item.get("intended_conclusion"), f"figures[{index}].intended_conclusion", minimum=12
            )
            claim_boundary = _text(
                item.get("claim_boundary"), f"figures[{index}].claim_boundary", minimum=8
            )
            results_units = _string_list(item.get("results_units"), f"figures[{index}].results_units")
            if not results_units:
                raise ContractError(f"figures[{index}].results_units must not be empty")
            hero_panel = _text(item.get("hero_panel"), f"figures[{index}].hero_panel")
            raw_panels = item.get("panels")
            if not isinstance(raw_panels, list) or not raw_panels:
                raise ContractError(f"figures[{index}].panels must be a non-empty list")
            panels: list[dict[str, Any]] = []
            panel_ids: set[str] = set()
            for panel_index, raw_panel in enumerate(raw_panels):
                panel = _mapping(raw_panel, f"figures[{index}].panels[{panel_index}]")
                panel_id = _text(
                    panel.get("panel_id"), f"figures[{index}].panels[{panel_index}].panel_id"
                )
                if not IDENTIFIER.fullmatch(panel_id) or panel_id in panel_ids:
                    raise ContractError(
                        f"figures[{index}].panels panel_id values must be unique safe identifiers"
                    )
                panel_ids.add(panel_id)
                panels.append(
                    {
                        **panel,
                        "panel_id": panel_id,
                        "question": _text(
                            panel.get("question"),
                            f"figures[{index}].panels[{panel_index}].question",
                            minimum=4,
                        ),
                        "role": _text(
                            panel.get("role"), f"figures[{index}].panels[{panel_index}].role", minimum=3
                        ),
                        "evidence_anchor": _text(
                            panel.get("evidence_anchor"),
                            f"figures[{index}].panels[{panel_index}].evidence_anchor",
                            minimum=2,
                        ),
                        "intended_reading": _text(
                            panel.get("intended_reading"),
                            f"figures[{index}].panels[{panel_index}].intended_reading",
                            minimum=4,
                        ),
                    }
                )
            if hero_panel not in panel_ids:
                raise ContractError(f"figures[{index}].hero_panel must name one declared panel_id")
            story = {
                "scientific_question": scientific_question,
                "intended_conclusion": intended_conclusion,
                "claim_boundary": claim_boundary,
                "results_units": results_units,
                "hero_panel": hero_panel,
                "panels": panels,
            }
        normalized_figures.append(
            {
                **item,
                "figure_id": figure_id,
                "figure_kind": kind,
                "claim": claim,
                "caption": caption,
                "label": label,
                "source_data": source_data,
                "data_evidence": data_evidence,
                "reference_assets": references,
                "decision": decision,
                "repair_reasons": repair_reasons,
                **(
                    {"scientific_identity": scientific_identity}
                    if scientific_identity is not None
                    else {}
                ),
                **({"placement": placement} if placement is not None else {}),
                **(
                    {"final_size_context": final_size_context}
                    if final_size_context is not None
                    else {}
                ),
                "publication_role": publication_role,
                "editorial_rationale": editorial_rationale,
                "claim_coverage": claim_coverage,
                **({"current_figure": current_figure} if current_figure is not None else {}),
                **(
                    {"current_figure_sha256": current_figure_sha256}
                    if current_figure_sha256 is not None
                    else {}
                ),
                **story,
            }
        )
    normalized_by_id = {item["figure_id"]: item for item in normalized_figures}
    for item in normalized_figures:
        figure_id = item["figure_id"]
        for replacement in item["claim_coverage"]["replacement_support"]:
            replacement_id = replacement["figure_id"]
            if replacement_id == figure_id:
                raise ContractError(
                    f"{figure_id} cannot replace its own essential main-claim support after moving out of the main article"
                )
            target = normalized_by_id.get(replacement_id)
            if target is None:
                raise ContractError(
                    f"{figure_id} replacement_support references unknown figure {replacement_id}"
                )
            if target["publication_role"] != "main":
                raise ContractError(
                    f"{figure_id} replacement_support figure {replacement_id} must remain in the main article"
                )
    return {
        **raw,
        "schema_version": SCHEMA_VERSION,
        "paper_id": paper_id,
        **({"layout_profile": layout_profile} if layout_profile is not None else {}),
        "figures": normalized_figures,
    }


def validate_review_decision(raw: dict[str, Any], requests: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") not in {"0.5", "1.0", REVIEW_DECISION_VERSION}:
        raise ContractError("review decision schema_version must be 0.5, 1.0, or 1.1")
    if raw.get("project_id") != requests["paper_id"]:
        raise ContractError("review decision project_id does not match the paper")
    if raw.get("review_scope") != "all_figures":
        raise ContractError("review decision review_scope must be all_figures")
    if raw.get("status") != "confirmed":
        raise ContractError("review decision status must be confirmed")
    decisions = raw.get("figures")
    if not isinstance(decisions, list):
        raise ContractError("review decision figures must be a list")
    expected = {item["figure_id"] for item in requests["figures"]}
    received: set[str] = set()
    normalized: list[dict[str, Any]] = []
    for index, value in enumerate(decisions):
        item = _mapping(value, f"review.figures[{index}]")
        figure_id = _text(item.get("figure_id"), f"review.figures[{index}].figure_id")
        if figure_id not in expected or figure_id in received:
            raise ContractError(f"unexpected or duplicate review figure_id: {figure_id}")
        received.add(figure_id)
        candidate = _text(item.get("selected_candidate"), "selected_candidate")
        request = next(value for value in requests["figures"] if value["figure_id"] == figure_id)
        mode = request.get("decision")
        if not IDENTIFIER.fullmatch(candidate):
            raise ContractError(f"selected_candidate for {figure_id} must be a safe identifier")
        publication_role = request.get("publication_role", "main")
        if publication_role == "omit" and candidate != "omitted":
            raise ContractError(f"selected_candidate for omitted figure {figure_id} must be omitted")
        if publication_role != "omit" and candidate == "omitted":
            raise ContractError(f"selected_candidate for published figure {figure_id} cannot be omitted")
        if publication_role != "omit" and mode == "keep" and candidate != "existing":
            raise ContractError(f"selected_candidate for {figure_id} must be existing")
        if publication_role != "omit" and mode == "create" and candidate == "existing":
            raise ContractError(f"selected_candidate for {figure_id} must name a generated candidate")
        if mode not in {"keep", "create", "redesign", "improve"}:
            raise ContractError(f"figure decision mode is unsupported: {mode}")
        if item.get("confirmed") is not True:
            raise ContractError(f"figure {figure_id} is not confirmed")
        panel_decisions = item.get("panel_decisions", [])
        if not isinstance(panel_decisions, list):
            raise ContractError("panel_decisions must be a list")
        if candidate in {"existing", "omitted"} and panel_decisions:
            raise ContractError(
                "existing original and omitted selections must not carry generated panel decisions"
            )
        panel_ids: set[str] = set()
        for panel in panel_decisions:
            if not isinstance(panel, dict) or panel.get("action") not in PANEL_ACTIONS:
                raise ContractError("panel decision action must be keep, lock, or revise")
            panel_id = panel.get("panel_id")
            if not isinstance(panel_id, str) or not panel_id.strip() or panel_id in panel_ids:
                raise ContractError("panel decision IDs must be non-empty and unique per figure")
            panel_ids.add(panel_id)
        normalized.append({**item, "figure_id": figure_id, "selected_candidate": candidate})
    if received != expected:
        raise ContractError(f"review decision does not cover every figure: missing {sorted(expected - received)}")
    return {
        **raw,
        "schema_version": REVIEW_DECISION_VERSION,
        "project_id": requests["paper_id"],
        "figures": normalized,
    }
