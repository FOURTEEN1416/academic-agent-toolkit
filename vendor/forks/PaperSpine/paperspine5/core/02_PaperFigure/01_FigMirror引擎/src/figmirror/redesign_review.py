"""Independent original-vs-redesign comparison and fail-safe selection."""

from __future__ import annotations

import hashlib
import io
import json
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import REDESIGN_DECISIONS, load_config


COMPARISON_CONTRACT_VERSION = "figmirror.redesign-comparison.v1"
FINAL_SIZE_COMPARISON_CONTRACT_VERSION = "figmirror.redesign-comparison.v2"
RUBRIC_DIMENSIONS = (
    "scientific_story",
    "data_truthfulness",
    "readability",
    "publication_fit",
    "editability_lineage",
)
SCIENTIFIC_DIMENSIONS = {"scientific_story", "data_truthfulness"}
DIMENSION_THRESHOLD = 75.0
VERDICTS = {"candidate_better", "tie", "current_better", "insufficient"}
CONCLUSIONS = {"strictly_better", "tie", "current_better", "insufficient"}


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest().upper()


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest().upper()


def _normalized_png(raw: bytes, target_width_px: int) -> bytes:
    from PIL import Image

    with Image.open(io.BytesIO(raw)) as opened:
        image = opened.convert("RGBA" if "A" in opened.getbands() else "RGB")
        if image.width != target_width_px:
            target_height = max(1, round(image.height * target_width_px / image.width))
            image = image.resize((target_width_px, target_height), Image.Resampling.LANCZOS)
        output = io.BytesIO()
        image.save(output, format="PNG", optimize=False, compress_level=6)
        return output.getvalue()


def _final_size_png(source: Path, context: dict[str, Any]) -> bytes:
    width_mm = context.get("physical_width_mm")
    dpi = context.get("render_dpi")
    if (
        isinstance(width_mm, bool)
        or not isinstance(width_mm, (int, float))
        or float(width_mm) <= 0
        or isinstance(dpi, bool)
        or not isinstance(dpi, int)
        or dpi < 72
    ):
        raise ValueError("final_size_context requires positive physical_width_mm and render_dpi >= 72")
    target_width_px = max(1, round(float(width_mm) / 25.4 * dpi))
    suffix = source.suffix.lower()
    if suffix in {".png", ".jpg", ".jpeg", ".tif", ".tiff", ".webp", ".bmp"}:
        return _normalized_png(source.read_bytes(), target_width_px)
    if suffix == ".svg":
        try:
            import cairosvg
        except ImportError as exc:  # pragma: no cover - environment-specific dependency
            raise ValueError("CairoSVG is required for final-size SVG review") from exc
        rendered = cairosvg.svg2png(url=str(source), output_width=target_width_px)
        return _normalized_png(rendered, target_width_px)
    if suffix == ".pdf":
        try:
            import fitz

            document = fitz.open(source)
            try:
                page = document[0]
                scale = target_width_px / page.rect.width
                rendered = page.get_pixmap(matrix=fitz.Matrix(scale, scale), alpha=False).tobytes(
                    "png"
                )
            finally:
                document.close()
            return _normalized_png(rendered, target_width_px)
        except ImportError:
            executable = shutil.which("pdftoppm")
            if executable is None:
                raise ValueError("PyMuPDF or pdftoppm is required for final-size PDF review")
            with tempfile.TemporaryDirectory(prefix="figmirror-final-size-") as tmp:
                prefix = Path(tmp) / "page"
                completed = subprocess.run(
                    [
                        executable,
                        "-f",
                        "1",
                        "-singlefile",
                        "-png",
                        "-r",
                        str(dpi),
                        str(source),
                        str(prefix),
                    ],
                    capture_output=True,
                    text=True,
                    check=False,
                )
                rendered_path = prefix.with_suffix(".png")
                if completed.returncode != 0 or not rendered_path.is_file():
                    raise ValueError("pdftoppm failed to render final-size PDF review")
                return _normalized_png(rendered_path.read_bytes(), target_width_px)
    raise ValueError(f"unsupported final-size review format: {source.suffix}")


def _canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _canonical_sha(value: Any) -> str:
    return hashlib.sha256(_canonical_bytes(value)).hexdigest().upper()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _comparison_dir(job: Path, figure_id: str) -> Path:
    return job / "review" / "comparisons" / figure_id


def _candidate_visual(candidate_dir: Path) -> Path:
    for name in ("figure.png", "preview.png", "figure.svg", "figure.pdf", "figure.tiff"):
        path = candidate_dir / name
        if path.is_file():
            return path
    report_path = candidate_dir / "authoring_report.json"
    if report_path.is_file():
        report = _read_object(report_path)
        exports = report.get("exports")
        if isinstance(exports, dict):
            for key in ("png", "svg", "pdf", "tiff"):
                raw = exports.get(key)
                if isinstance(raw, str):
                    path = candidate_dir / raw
                    if path.is_file():
                        return path
    raise ValueError(f"final candidate visual is missing: {candidate_dir}")


def _candidate_record(candidate_dir: Path, candidate_id: str, fallback_identity: str | None) -> dict[str, Any]:
    visual = _candidate_visual(candidate_dir)
    generation_path = candidate_dir / "generation_request.json"
    generation = _read_object(generation_path) if generation_path.is_file() else {}
    identity = str(generation.get("producer_identity") or fallback_identity or "UNASSIGNED").strip()
    generation_story = {
        "claim": generation.get("claim"),
        **{
            key: generation.get("story_contract", {}).get(key)
            for key in (
                "figure_role",
                "scientific_question",
                "intended_conclusion",
                "claim_boundary",
                "results_units",
                "hero_panel",
                "panels",
            )
            if isinstance(generation.get("story_contract"), dict)
            and key in generation.get("story_contract", {})
        },
    }
    record: dict[str, Any] = {
        "candidate_id": candidate_id,
        "source_path": str(visual.resolve()),
        "sha256": _sha256_file(visual),
        "bytes": visual.stat().st_size,
        "producer_identity": identity,
        "scientific_story_sha256": _canonical_sha(generation_story),
    }
    for name in ("candidate.json", "authoring_report.json", "generation_request.json"):
        path = candidate_dir / name
        if path.is_file():
            record[f"{name}_sha256"] = _sha256_file(path)
    return record


def _story_contract(figure: dict[str, Any]) -> dict[str, Any]:
    return {
        key: figure[key]
        for key in (
            "figure_role",
            "scientific_question",
            "claim",
            "intended_conclusion",
            "claim_boundary",
            "results_units",
            "hero_panel",
            "panels",
        )
        if key in figure
    }


def prepare_redesign_comparisons(
    job_dir: str | Path,
    *,
    figure_ids: list[str] | tuple[str, ...] | None = None,
    write: bool = True,
) -> dict[str, Any]:
    """Create reviewer-facing blinded packages plus non-exported identity maps."""

    job = Path(job_dir).resolve()
    config = load_config(job / "figmirror.config.json")
    requested = set(figure_ids or [])
    outputs: list[dict[str, Any]] = []
    for figure in config["figures"]:
        figure_id = str(figure["figure_id"])
        if requested and figure_id not in requested:
            continue
        if figure.get("decision") not in REDESIGN_DECISIONS:
            outputs.append({"figure_id": figure_id, "status": "NOT_APPLICABLE", "mode": figure.get("decision")})
            continue
        current = Path(str(figure["current_figure"])).resolve()
        actual_current_hash = _sha256_file(current)
        if actual_current_hash != str(figure.get("current_figure_sha256") or "").upper():
            raise ValueError(f"{figure_id}: current_figure changed after configuration binding")
        candidate_ids = tuple("ABC"[: int(config["candidate_count"])])
        candidate_records = [
            _candidate_record(
                job / "candidates" / figure_id / candidate_id,
                candidate_id,
                str(figure.get("generator_identity") or "") or None,
            )
            for candidate_id in candidate_ids
        ]
        directory = _comparison_dir(job, figure_id)
        blind_dir = directory / "blind"
        final_size_context = figure.get("final_size_context")
        if final_size_context is not None and not isinstance(final_size_context, dict):
            raise ValueError(f"{figure_id}: final_size_context must be an object")
        contract_version = (
            FINAL_SIZE_COMPARISON_CONTRACT_VERSION
            if final_size_context is not None
            else COMPARISON_CONTRACT_VERSION
        )
        story = _story_contract(figure)
        story_sha = _canonical_sha(story)
        baseline_name = f"baseline{current.suffix.lower()}"
        baseline_destination = blind_dir / baseline_name
        baseline_render = (
            _final_size_png(current, final_size_context) if final_size_context is not None else None
        )
        baseline_render_name = "final-size/baseline.png"
        private_variants: dict[str, dict[str, Any]] = {}
        public_variants: list[dict[str, Any]] = []
        for record in candidate_records:
            artifact_id = f"variant-{_canonical_sha([figure_id, record['sha256']])[:12].lower()}"
            suffix = Path(str(record["source_path"])).suffix.lower()
            blind_name = f"{artifact_id}{suffix}"
            source_path = Path(str(record["source_path"]))
            render = (
                _final_size_png(source_path, final_size_context)
                if final_size_context is not None
                else None
            )
            final_size_name = f"final-size/{artifact_id}.png"
            public_variants.append(
                {
                    "artifact_id": artifact_id,
                    "path": f"blind/{blind_name}",
                    "sha256": record["sha256"],
                    "bytes": record["bytes"],
                    **(
                        {
                            "final_size_path": f"blind/{final_size_name}",
                            "final_size_render_sha256": _sha256_bytes(render),
                            "final_size_render_bytes": len(render),
                        }
                        if render is not None
                        else {}
                    ),
                }
            )
            private_variants[artifact_id] = {
                **record,
                "blind_path": str((blind_dir / blind_name).resolve()),
                **(
                    {
                        "final_size_render_path": str((blind_dir / final_size_name).resolve()),
                        "final_size_render_sha256": _sha256_bytes(render),
                    }
                    if render is not None
                    else {}
                ),
                "_final_size_render_bytes": render,
            }
        fixed_input = {
            "contract_version": contract_version,
            "figure_id": figure_id,
            "mode": figure["decision"],
            "scientific_story": story,
            "scientific_story_sha256": story_sha,
            **(
                {
                    "final_size_context": final_size_context,
                    "final_size_context_sha256": _canonical_sha(final_size_context),
                }
                if final_size_context is not None
                else {}
            ),
            "baseline": {
                "artifact_id": "baseline",
                "path": f"blind/{baseline_name}",
                "sha256": actual_current_hash,
                "bytes": current.stat().st_size,
                **(
                    {
                        "final_size_path": f"blind/{baseline_render_name}",
                        "final_size_render_sha256": _sha256_bytes(baseline_render),
                        "final_size_render_bytes": len(baseline_render),
                    }
                    if baseline_render is not None
                    else {}
                ),
            },
            "variants": public_variants,
            "rubric": {
                "dimensions": list(RUBRIC_DIMENSIONS),
                "minimum_candidate_score": DIMENSION_THRESHOLD,
                "scientific_regression_prohibited": sorted(SCIENTIFIC_DIMENSIONS),
                "verdicts": sorted(VERDICTS),
                "strict_rule": "A variant must meet every threshold, have no worse dimension, preserve scientific/data truth, improve at least one dimension, and receive a consistent strictly_better conclusion.",
            },
            "reviewer_instructions": [
                "Review every opaque variant against the baseline under the same scientific story.",
                "Do not infer generator identity from style or paths; generator metadata is intentionally absent.",
                "Return one comparison for every variant and identify a winner only when it is strictly better.",
                "A tie, insufficient evidence, scientific regression, or contradictory evidence must not select a variant.",
                *(
                    [
                        "Judge readability and publication fit from the anonymous final-size PNGs, not from development-canvas source files.",
                        "Treat any final-size context or render-hash mismatch as an invalid comparison input.",
                    ]
                    if final_size_context is not None
                    else []
                ),
            ],
        }
        fingerprint = _canonical_sha(fixed_input)
        request = {**fixed_input, "input_digest": fingerprint}
        private_map = {
            "contract_version": contract_version,
            "figure_id": figure_id,
            "input_digest": fingerprint,
            "baseline": {
                "source_path": str(current),
                "blind_path": str(baseline_destination.resolve()),
                "sha256": actual_current_hash,
                **(
                    {
                        "final_size_render_path": str(
                            (blind_dir / baseline_render_name).resolve()
                        ),
                        "final_size_render_sha256": _sha256_bytes(baseline_render),
                    }
                    if baseline_render is not None
                    else {}
                ),
            },
            "variants": {
                artifact_id: {
                    key: value
                    for key, value in record.items()
                    if key != "_final_size_render_bytes"
                }
                for artifact_id, record in private_variants.items()
            },
            **({"final_size_context": final_size_context} if final_size_context is not None else {}),
        }
        if write:
            blind_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(current, baseline_destination)
            if baseline_render is not None:
                final_path = blind_dir / baseline_render_name
                final_path.parent.mkdir(parents=True, exist_ok=True)
                final_path.write_bytes(baseline_render)
            for artifact_id, record in private_variants.items():
                shutil.copy2(Path(str(record["source_path"])), Path(str(record["blind_path"])))
                render_bytes = record.get("_final_size_render_bytes")
                if isinstance(render_bytes, bytes):
                    render_path = Path(str(record["final_size_render_path"]))
                    render_path.parent.mkdir(parents=True, exist_ok=True)
                    render_path.write_bytes(render_bytes)
            directory.mkdir(parents=True, exist_ok=True)
            (directory / "comparison_request.json").write_text(
                json.dumps(request, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (directory / "comparison_private_map.json").write_text(
                json.dumps(private_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        outputs.append(
            {
                "figure_id": figure_id,
                "status": "READY_FOR_INDEPENDENT_REVIEW",
                "input_digest": fingerprint,
                "comparison_request": str(directory / "comparison_request.json"),
                "reviewer_identity_blinded": True,
                "candidate_count": len(public_variants),
            }
        )
    return {
        "contract_version": COMPARISON_CONTRACT_VERSION,
        "status": "READY" if any(item["status"] == "READY_FOR_INDEPENDENT_REVIEW" for item in outputs) else "NOT_APPLICABLE",
        "figures": outputs,
    }


def _input_failures(request: dict[str, Any], private_map: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if request.get("contract_version") != private_map.get("contract_version"):
        failures.append("private_map_contract_version_mismatch")
    if request.get("input_digest") != private_map.get("input_digest"):
        failures.append("private_map_input_digest_mismatch")
    fixed = {key: value for key, value in request.items() if key != "input_digest"}
    if _canonical_sha(fixed) != request.get("input_digest"):
        failures.append("comparison_request_digest_mismatch")
    final_size_required = request.get("contract_version") == FINAL_SIZE_COMPARISON_CONTRACT_VERSION
    if final_size_required:
        context = request.get("final_size_context")
        if (
            not isinstance(context, dict)
            or context != private_map.get("final_size_context")
            or request.get("final_size_context_sha256") != _canonical_sha(context)
        ):
            failures.append("final_size_context_mismatch")
        public_baseline = request.get("baseline") or {}
        private_baseline = private_map.get("baseline") or {}
        if public_baseline.get("final_size_render_sha256") != private_baseline.get(
            "final_size_render_sha256"
        ):
            failures.append("baseline_final_size_render_hash_mismatch")
        public_variants = {
            item.get("artifact_id"): item
            for item in request.get("variants", [])
            if isinstance(item, dict) and item.get("artifact_id")
        }
        for artifact_id, record in (private_map.get("variants") or {}).items():
            if (public_variants.get(artifact_id) or {}).get(
                "final_size_render_sha256"
            ) != (record or {}).get("final_size_render_sha256"):
                failures.append("variant_final_size_render_hash_mismatch")
    records = [private_map.get("baseline"), *(private_map.get("variants") or {}).values()]
    for record in records:
        if not isinstance(record, dict):
            failures.append("comparison_private_map_incomplete")
            continue
        for key in ("source_path", "blind_path"):
            path = Path(str(record.get(key) or ""))
            if not path.is_file() or _sha256_file(path) != str(record.get("sha256") or "").upper():
                failures.append(f"input_hash_changed:{key}")
        if final_size_required:
            render_path = Path(str(record.get("final_size_render_path") or ""))
            if (
                not render_path.is_file()
                or _sha256_file(render_path)
                != str(record.get("final_size_render_sha256") or "").upper()
            ):
                failures.append("final_size_render_hash_changed")
    for record in (private_map.get("variants") or {}).values():
        if (
            not isinstance(record, dict)
            or record.get("scientific_story_sha256") != request.get("scientific_story_sha256")
        ):
            failures.append("candidate_scientific_story_mismatch")
    return failures


def _normalize_dimension(value: Any) -> tuple[dict[str, Any], list[str]]:
    failures: list[str] = []
    raw = value if isinstance(value, dict) else {}
    current_score = raw.get("current_score")
    candidate_score = raw.get("candidate_score")
    verdict = str(raw.get("verdict") or "insufficient")
    evidence = raw.get("evidence")
    if isinstance(current_score, bool) or not isinstance(current_score, (int, float)) or not 0 <= float(current_score) <= 100:
        failures.append("invalid_current_score")
        current_score = None
    if isinstance(candidate_score, bool) or not isinstance(candidate_score, (int, float)) or not 0 <= float(candidate_score) <= 100:
        failures.append("invalid_candidate_score")
        candidate_score = None
    if verdict not in VERDICTS:
        failures.append("invalid_verdict")
        verdict = "insufficient"
    if not isinstance(evidence, list) or not evidence or any(not isinstance(item, str) or not item.strip() for item in evidence):
        failures.append("missing_evidence")
        evidence = []
    if current_score is not None and candidate_score is not None:
        delta = float(candidate_score) - float(current_score)
        consistent = (
            (verdict == "candidate_better" and delta > 0)
            or (verdict == "tie" and delta == 0)
            or (verdict == "current_better" and delta < 0)
            or verdict == "insufficient"
        )
        if not consistent:
            failures.append("score_verdict_conflict")
    return {
        "current_score": float(current_score) if current_score is not None else None,
        "candidate_score": float(candidate_score) if candidate_score is not None else None,
        "verdict": verdict,
        "evidence": evidence,
        "threshold_met": candidate_score is not None and float(candidate_score) >= DIMENSION_THRESHOLD,
    }, failures


def _immutable_write(path: Path, receipt: dict[str, Any]) -> dict[str, Any]:
    if path.is_file():
        existing = _read_object(path)
        if _canonical_bytes(existing) != _canonical_bytes(receipt):
            raise ValueError(f"immutable comparison receipt already exists with different content: {path}")
        return existing
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return receipt


def record_redesign_comparison(
    job_dir: str | Path,
    figure_id: str,
    submission: str | Path | dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate an external reviewer submission and freeze a fail-safe receipt."""

    job = Path(job_dir).resolve()
    directory = _comparison_dir(job, figure_id)
    request_path = directory / "comparison_request.json"
    private_path = directory / "comparison_private_map.json"
    if not request_path.is_file() or not private_path.is_file():
        prepare_redesign_comparisons(job, figure_ids=[figure_id])
    request = _read_object(request_path)
    private_map = _read_object(private_path)
    if submission is None:
        raw: dict[str, Any] = {}
    elif isinstance(submission, dict):
        raw = submission
    else:
        raw = _read_object(Path(submission))

    failures = _input_failures(request, private_map)
    fallback_reason: str | None = None
    reviewer_raw = raw.get("reviewer") if isinstance(raw.get("reviewer"), dict) else {}
    reviewer_identity = str(reviewer_raw.get("identity") or "").strip()
    reviewer_role = str(reviewer_raw.get("role") or "").strip()
    producer_identities = {
        str(record.get("producer_identity") or "").strip()
        for record in (private_map.get("variants") or {}).values()
        if isinstance(record, dict)
    }
    producer_hashes = sorted(_canonical_sha(identity.casefold()) for identity in producer_identities if identity)
    if not raw:
        failures.append("reviewer_unavailable")
    if not reviewer_identity or reviewer_role != "independent_reviewer_agent":
        failures.append("reviewer_identity_or_role_missing")
    if not producer_identities or "UNASSIGNED" in producer_identities:
        failures.append("generator_identity_unverified")
    if reviewer_identity and reviewer_identity.casefold() in {identity.casefold() for identity in producer_identities}:
        failures.append("reviewer_generator_identity_conflict")
    if raw.get("input_digest") != request.get("input_digest"):
        failures.append("review_input_digest_mismatch")
    if raw and raw.get("contract_version") != request.get("contract_version"):
        failures.append("review_contract_version_mismatch")

    expected_artifacts = set((private_map.get("variants") or {}).keys())
    raw_comparisons = raw.get("comparisons") if isinstance(raw.get("comparisons"), dict) else {}
    normalized_comparisons: dict[str, Any] = {}
    for artifact_id in sorted(expected_artifacts):
        comparison = raw_comparisons.get(artifact_id) if isinstance(raw_comparisons.get(artifact_id), dict) else {}
        raw_dimensions = comparison.get("dimensions") if isinstance(comparison.get("dimensions"), dict) else {}
        dimensions: dict[str, Any] = {}
        comparison_failures: list[str] = []
        for dimension in RUBRIC_DIMENSIONS:
            normalized, dimension_failures = _normalize_dimension(raw_dimensions.get(dimension))
            dimensions[dimension] = normalized
            comparison_failures.extend(f"{dimension}:{item}" for item in dimension_failures)
        conclusion = str(comparison.get("conclusion") or "insufficient")
        if conclusion not in CONCLUSIONS:
            comparison_failures.append("invalid_conclusion")
            conclusion = "insufficient"
        normalized_comparisons[artifact_id] = {
            "dimensions": dimensions,
            "conclusion": conclusion,
            "failures": comparison_failures,
        }
    if set(raw_comparisons) != expected_artifacts:
        failures.append("candidate_suite_review_incomplete_or_unknown")

    winner_artifact = str(raw.get("winner_artifact") or "")
    suite_conclusion = str(raw.get("conclusion") or "insufficient")
    if suite_conclusion not in CONCLUSIONS:
        failures.append("invalid_suite_conclusion")
        suite_conclusion = "insufficient"
    winning_comparison = normalized_comparisons.get(winner_artifact)
    if suite_conclusion == "strictly_better":
        if winner_artifact not in expected_artifacts or not isinstance(winning_comparison, dict):
            failures.append("strict_conclusion_without_variant_winner")
        else:
            dimensions = winning_comparison["dimensions"]
            if winning_comparison["conclusion"] != "strictly_better":
                failures.append("suite_candidate_conclusion_conflict")
            if winning_comparison["failures"]:
                failures.append("winning_comparison_invalid")
            if any(not item["threshold_met"] for item in dimensions.values()):
                failures.append("core_dimension_below_threshold")
            if any(item["verdict"] in {"current_better", "insufficient"} for item in dimensions.values()):
                failures.append("candidate_dimension_regression_or_insufficient")
            if any(dimensions[name]["verdict"] in {"current_better", "insufficient"} for name in SCIENTIFIC_DIMENSIONS):
                failures.append("scientific_regression_or_uncertainty")
            if not any(item["verdict"] == "candidate_better" for item in dimensions.values()):
                failures.append("strict_superiority_not_demonstrated")
    else:
        winner_artifact = ""

    reviewed_at = str(raw.get("reviewed_at") or _now())
    try:
        parsed_review_time = datetime.fromisoformat(reviewed_at.replace("Z", "+00:00"))
        if parsed_review_time.tzinfo is None:
            raise ValueError("timezone is required")
    except ValueError:
        failures.append("invalid_review_timestamp")

    if failures:
        for priority in (
            "reviewer_generator_identity_conflict",
            "generator_identity_unverified",
            "input_hash_changed",
            "candidate_scientific_story_mismatch",
            "reviewer_unavailable",
            "review_input_digest_mismatch",
            "candidate_suite_review_incomplete_or_unknown",
            "scientific_regression_or_uncertainty",
            "candidate_dimension_regression_or_insufficient",
            "core_dimension_below_threshold",
            "strict_superiority_not_demonstrated",
            "suite_candidate_conclusion_conflict",
        ):
            match = next((item for item in failures if item.startswith(priority)), None)
            if match:
                fallback_reason = match
                break
        fallback_reason = fallback_reason or failures[0]
    elif suite_conclusion != "strictly_better":
        fallback_reason = f"candidate_not_strictly_better:{suite_conclusion}"

    selected_candidate: str | None = None
    winner: dict[str, Any]
    if fallback_reason is None and winner_artifact:
        selected_candidate = str(private_map["variants"][winner_artifact]["candidate_id"])
        winner = {"role": "candidate", "artifact_id": winner_artifact, "candidate_id": selected_candidate}
    else:
        winner = {"role": "current_figure", "artifact_id": "baseline", "candidate_id": "existing"}
    receipt = {
        "contract_version": request.get("contract_version"),
        "figure_id": figure_id,
        "mode": request.get("mode"),
        "reviewer": {
            "identity": reviewer_identity or None,
            "role": reviewer_role or "unavailable",
        },
        "producer_identity_hashes": producer_hashes,
        "input_digest": request.get("input_digest"),
        "input_hashes": {
            "scientific_story_sha256": request.get("scientific_story_sha256"),
            "baseline_sha256": request.get("baseline", {}).get("sha256"),
            "variant_sha256": {
                item["artifact_id"]: item["sha256"] for item in request.get("variants", []) if isinstance(item, dict)
            },
            **(
                {
                    "final_size_context_sha256": request.get(
                        "final_size_context_sha256"
                    ),
                    "baseline_final_size_render_sha256": request.get(
                        "baseline", {}
                    ).get("final_size_render_sha256"),
                    "variant_final_size_render_sha256": {
                        item["artifact_id"]: item["final_size_render_sha256"]
                        for item in request.get("variants", [])
                        if isinstance(item, dict) and item.get("final_size_render_sha256")
                    },
                }
                if request.get("contract_version")
                == FINAL_SIZE_COMPARISON_CONTRACT_VERSION
                else {}
            ),
        },
        "comparisons": normalized_comparisons,
        "suite_conclusion": suite_conclusion,
        "winner": winner,
        "automatic_selection": selected_candidate or "existing",
        "fallback_reason": fallback_reason,
        "validation": {
            "identity_separated": "reviewer_generator_identity_conflict" not in failures
            and "generator_identity_unverified" not in failures
            and bool(reviewer_identity),
            "input_hashes_unchanged": not any(item.startswith("input_hash_changed") for item in failures),
            "candidate_suite_complete": "candidate_suite_review_incomplete_or_unknown" not in failures,
            "final_size_context_bound": not any(
                item.startswith("final_size_") for item in failures
            )
            if request.get("contract_version") == FINAL_SIZE_COMPARISON_CONTRACT_VERSION
            else None,
            "strict_superiority": fallback_reason is None,
            "failures": failures,
        },
        "reviewed_at": reviewed_at,
    }
    receipt["receipt_sha256"] = _canonical_sha(receipt)
    return _immutable_write(directory / "comparison_receipt.json", receipt)


def comparison_selection(
    job_dir: str | Path,
    figure_id: str,
    *,
    write_missing_receipt: bool = False,
) -> dict[str, Any]:
    """Return the frozen candidate/original decision, failing safe to original."""

    job = Path(job_dir).resolve()
    directory = _comparison_dir(job, figure_id)
    receipt_path = directory / "comparison_receipt.json"
    if not receipt_path.is_file():
        prepare_redesign_comparisons(job, figure_ids=[figure_id])
        if write_missing_receipt:
            receipt = record_redesign_comparison(job, figure_id, None)
        else:
            return {
                "selection": "existing",
                "winner": "current_figure",
                "fallback_reason": "reviewer_unavailable",
                "receipt": None,
            }
    else:
        receipt = _read_object(receipt_path)
    request = _read_object(directory / "comparison_request.json")
    private_map = _read_object(directory / "comparison_private_map.json")
    changed = _input_failures(request, private_map)
    if changed:
        return {
            "selection": "existing",
            "winner": "current_figure",
            "fallback_reason": changed[0],
            "receipt": str(receipt_path),
        }
    allowed_candidates = {
        str(record.get("candidate_id"))
        for record in (private_map.get("variants") or {}).values()
        if isinstance(record, dict) and record.get("candidate_id")
    }
    selection = str(receipt.get("automatic_selection") or "existing")
    if receipt.get("fallback_reason") is not None or selection not in allowed_candidates:
        selection = "existing"
    return {
        "selection": selection,
        "winner": "candidate" if selection in allowed_candidates else "current_figure",
        "fallback_reason": receipt.get("fallback_reason"),
        "receipt": str(receipt_path),
        "receipt_sha256": receipt.get("receipt_sha256"),
    }
