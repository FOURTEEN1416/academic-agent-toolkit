"""Host-neutral contracts and safe path handling for PaperSpine × FigMirror."""

from __future__ import annotations

import json
import os
import re
from copy import deepcopy
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
HOSTS = {"codex", "claude-code", "dsh", "standalone-skill"}
FIGURE_KINDS = {"data", "schematic"}
FIGURE_DECISIONS = {"keep", "redesign", "create"}
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
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"schema_version must be {SCHEMA_VERSION}")
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

    paper = _mapping(raw.get("paper"), "paper")
    figure = _mapping(raw.get("figure"), "figure")
    assembly = _mapping(raw.get("assembly", {}), "assembly")
    publication = _mapping(raw.get("publication", {}), "publication")
    workflow = _mapping(raw.get("workflow", {}), "workflow")

    paper_output = resolve_within(project_root, _text(paper.get("output_dir"), "paper.output_dir"), "paper.output_dir")
    progress_script = resolve_within(
        project_root,
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
        project_root,
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
    publication_script = resolve_within(
        project_root,
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
    normalized.update({"schema_version": SCHEMA_VERSION, "job_id": job_id, "host": host})
    normalized["project_root"] = str(project_root)
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
            raise ContractError(f"figures[{index}].decision must be keep, redesign, or create")
        current_figure = item.get("current_figure")
        if decision in {"keep", "redesign"}:
            current_figure = _text(
                current_figure,
                f"figures[{index}].current_figure",
            )
        elif current_figure is not None:
            current_figure = _text(current_figure, f"figures[{index}].current_figure")

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
                **({"current_figure": current_figure} if current_figure is not None else {}),
                **story,
            }
        )
    return {**raw, "schema_version": SCHEMA_VERSION, "paper_id": paper_id, "figures": normalized_figures}


def validate_review_decision(raw: dict[str, Any], requests: dict[str, Any]) -> dict[str, Any]:
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ContractError(f"review decision schema_version must be {SCHEMA_VERSION}")
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
        allowed = {"existing"} if request.get("decision") == "keep" else {"A", "B", "C"}
        if candidate not in allowed:
            expected_candidate = "existing" if request.get("decision") == "keep" else "A, B, or C"
            raise ContractError(
                f"selected_candidate for {figure_id} must be {expected_candidate}"
            )
        if item.get("confirmed") is not True:
            raise ContractError(f"figure {figure_id} is not confirmed")
        panel_decisions = item.get("panel_decisions", [])
        if not isinstance(panel_decisions, list):
            raise ContractError("panel_decisions must be a list")
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
    return {**raw, "schema_version": SCHEMA_VERSION, "project_id": requests["paper_id"], "figures": normalized}
