#!/usr/bin/env python3
"""Prepare and validate rendered-page plus figure-semantic visual receipts.

The script renders deterministically when Poppler is available. A multimodal
agent or human must then inspect every rendered page and figure and replace each
`pending` check in visual_audit_manifest.json with `pass` or `fail` plus notes.
The validator binds those receipts to current file hashes so stale inspection
cannot pass after the paper changes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

PAGE_CHECKS = ("title_author_header_bounds", "media_crop_box", "clipping", "blank_or_float_only", "readability")
FIGURE_CHECKS = (
    "method_names",
    "panel_labels",
    "baselines",
    "metrics",
    "datasets",
    "caption_text_alignment",
    "story_claim_alignment",
    "panel_role_alignment",
    "claim_boundary_respected",
)
INCLUDE_RE = re.compile(r"\\includegraphics(?:\[[^\]]*\])?\{([^}]+)\}")
FIGURE_ENV_RE = re.compile(r"\\begin\{figure\*?\}(.*?)\\end\{figure\*?\}", re.S)
CAPTION_RE = re.compile(r"\\caption\{(.*?)\}", re.S)
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")


@dataclass
class VisualResult:
    manifest: str
    ok: bool
    page_count: int
    figure_count: int
    findings: list[str]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare or validate PaperSpine visual audit receipts.")
    parser.add_argument("output_dir", nargs="?", default="paper_rewriting_output")
    parser.add_argument("--prepare", action="store_true", help="Render the final PDF/figures and create a pending audit manifest.")
    parser.add_argument("--dpi", type=int, default=144)
    parser.add_argument("--markdown", action="store_true")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--write", action="store_true")
    return parser.parse_args()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run(command: list[str]) -> tuple[int, str]:
    process = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    return process.returncode, (process.stdout + process.stderr).strip()


def _resolve_asset(final_dir: Path, raw: str) -> Path | None:
    candidate = (final_dir / raw).resolve()
    if candidate.suffix and candidate.is_file():
        return candidate
    for suffix in (".pdf", ".png", ".jpg", ".jpeg", ".svg"):
        with_suffix = Path(str(candidate) + suffix)
        if with_suffix.is_file():
            return with_suffix
    return None


def figure_inventory(tex_path: Path) -> list[dict]:
    if not tex_path.is_file():
        return []
    text = tex_path.read_text(encoding="utf-8", errors="ignore")
    figures: list[dict] = []
    covered: set[str] = set()
    for index, env in enumerate(FIGURE_ENV_RE.findall(text), 1):
        includes = INCLUDE_RE.findall(env)
        caption_match = CAPTION_RE.search(env)
        label_match = LABEL_RE.search(env)
        for raw in includes:
            asset = _resolve_asset(tex_path.parent, raw)
            asset_key = str(asset) if asset else raw
            covered.add(raw)
            figures.append({
                "figure_id": label_match.group(1) if label_match else f"figure-{index:03d}",
                "asset_raw": raw,
                "asset_path": str(asset) if asset else "",
                "caption": " ".join((caption_match.group(1) if caption_match else "").split()),
                "asset_key": asset_key,
            })
    for raw in INCLUDE_RE.findall(text):
        if raw in covered:
            continue
        asset = _resolve_asset(tex_path.parent, raw)
        figures.append({
            "figure_id": f"unscoped-{len(figures) + 1:03d}",
            "asset_raw": raw,
            "asset_path": str(asset) if asset else "",
            "caption": "",
            "asset_key": str(asset) if asset else raw,
        })
    return figures


def _figure_stories(output_dir: Path) -> dict[str, dict]:
    request_path = output_dir / "figure_requests.json"
    if not request_path.is_file():
        return {}
    try:
        data = json.loads(request_path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError):
        return {}
    stories: dict[str, dict] = {}
    for item in data.get("figures", []) if isinstance(data, dict) else []:
        if not isinstance(item, dict):
            continue
        figure_id = str(item.get("figure_id") or "").strip()
        label = str(item.get("label") or f"fig:{figure_id}").strip()
        if label:
            stories[label] = {
                key: item.get(key)
                for key in (
                    "claim",
                    "scientific_question",
                    "intended_conclusion",
                    "claim_boundary",
                    "results_units",
                    "hero_panel",
                    "panels",
                )
                if key in item
            }
    return stories


def _render_pdf(pdf_path: Path, prefix: Path, dpi: int, single: bool = False) -> tuple[list[Path], str]:
    renderer = shutil.which("pdftoppm")
    if not renderer:
        return [], "pdftoppm not found"
    prefix.parent.mkdir(parents=True, exist_ok=True)
    command = [renderer, "-png", "-r", str(dpi)]
    if single:
        command.append("-singlefile")
    command.extend([str(pdf_path), str(prefix)])
    rc, output = _run(command)
    if rc != 0:
        return [], output or f"pdftoppm exit {rc}"
    rendered = sorted(prefix.parent.glob(prefix.name + "*.png"))
    return rendered, ""


def prepare(output_dir: Path, dpi: int) -> tuple[Path, list[str]]:
    findings: list[str] = []
    final_dir = output_dir / "final_paper"
    pdf_path = final_dir / "paper.pdf"
    tex_path = final_dir / "main.tex"
    audit_dir = output_dir / "visual_audit"
    page_dir = audit_dir / "pages"
    figure_dir = audit_dir / "figures"
    page_dir.mkdir(parents=True, exist_ok=True)
    figure_dir.mkdir(parents=True, exist_ok=True)

    pages: list[dict] = []
    renderer_status = "pass"
    renderer_note = ""
    box_probe_status = "blocked"
    box_probe_note = "pdfinfo not run"
    if not pdf_path.is_file():
        renderer_status = "blocked"
        renderer_note = "final_paper/paper.pdf does not exist"
        findings.append(renderer_note)
    else:
        pdfinfo = shutil.which("pdfinfo")
        if pdfinfo:
            box_rc, box_output = _run([pdfinfo, "-box", str(pdf_path)])
            box_probe_status = "pass" if box_rc == 0 else "blocked"
            box_probe_note = box_output
            if box_rc != 0:
                findings.append(box_output or f"pdfinfo exit {box_rc}")
        else:
            box_probe_note = "pdfinfo not found"
            findings.append(box_probe_note)
        rendered, error = _render_pdf(pdf_path, page_dir / "page", dpi)
        if error or not rendered:
            renderer_status = "blocked"
            renderer_note = error or "no PDF pages were rendered"
            findings.append(renderer_note)
        for index, path in enumerate(rendered, 1):
            pages.append({
                "page": index,
                "render_path": str(path.relative_to(output_dir)),
                "render_sha256": sha256(path),
                "checks": {name: {"status": "pending", "note": ""} for name in PAGE_CHECKS},
                "status": "pending",
                "issues": [],
            })

    figures: list[dict] = []
    stories = _figure_stories(output_dir)
    for index, item in enumerate(figure_inventory(tex_path), 1):
        asset = Path(item["asset_path"]) if item["asset_path"] else None
        render_path = ""
        render_error = ""
        if asset is None or not asset.is_file():
            render_error = f"figure asset not found: {item['asset_raw']}"
        elif asset.suffix.lower() == ".pdf":
            rendered, render_error = _render_pdf(asset, figure_dir / f"figure-{index:03d}", dpi, single=True)
            if rendered:
                render_path = str(rendered[0].relative_to(output_dir))
        elif asset.suffix.lower() in {".png", ".jpg", ".jpeg"}:
            render_path = str(asset.relative_to(output_dir)) if asset.is_relative_to(output_dir) else str(asset)
        elif asset.suffix.lower() == ".svg":
            render_error = "SVG requires a host visual renderer; inspect the asset directly or render it to PNG before validation"
        figures.append({
            "figure_id": item["figure_id"],
            "asset_path": str(asset.relative_to(output_dir)) if asset and asset.is_relative_to(output_dir) else (str(asset) if asset else ""),
            "asset_sha256": sha256(asset) if asset and asset.is_file() else "",
            "render_path": render_path,
            "caption": item["caption"],
            "story_contract": stories.get(item["figure_id"], {}),
            "render_status": "pass" if render_path else "blocked",
            "render_note": render_error,
            "checks": {name: {"status": "pending", "note": ""} for name in FIGURE_CHECKS},
            "panels": [],
            "status": "pending",
            "issues": [],
        })
        if render_error:
            findings.append(render_error)

    manifest = {
        "schema_version": "1.0",
        "paper_pdf": str(pdf_path.relative_to(output_dir)) if pdf_path.is_file() else "final_paper/paper.pdf",
        "paper_pdf_sha256": sha256(pdf_path) if pdf_path.is_file() else "",
        "main_tex_sha256": sha256(tex_path) if tex_path.is_file() else "",
        "renderer": {
            "status": renderer_status,
            "note": renderer_note,
            "dpi": dpi,
            "box_probe_status": box_probe_status,
            "box_probe_note": box_probe_note,
        },
        "review": {"reviewer": "", "reviewer_type": "", "reviewed_at": "", "status": "pending"},
        "pages": pages,
        "figures": figures,
        "unresolved_conflicts": [],
    }
    manifest_path = output_dir / "visual_audit_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest_path, findings


def _check_receipt(name: str, checks: object, required: tuple[str, ...], findings: list[str]) -> None:
    if not isinstance(checks, dict):
        findings.append(f"{name} checks must be an object")
        return
    for check_name in required:
        value = checks.get(check_name)
        if not isinstance(value, dict) or str(value.get("status", "")).lower() != "pass":
            findings.append(f"{name}.{check_name} is not PASS")


def validate(output_dir: Path) -> VisualResult:
    path = output_dir / "visual_audit_manifest.json"
    findings: list[str] = []
    if not path.is_file():
        return VisualResult(str(path), False, 0, 0, ["visual_audit_manifest.json does not exist; run --prepare after final PDF compilation"])
    try:
        data = json.loads(path.read_text(encoding="utf-8-sig"))
    except (OSError, json.JSONDecodeError) as exc:
        return VisualResult(str(path), False, 0, 0, [f"invalid JSON: {exc}"])

    pdf_path = output_dir / str(data.get("paper_pdf") or "final_paper/paper.pdf")
    if not pdf_path.is_file():
        findings.append("bound paper PDF is missing")
    elif sha256(pdf_path) != str(data.get("paper_pdf_sha256") or ""):
        findings.append("paper PDF changed after visual inspection; prepare and inspect again")
    tex_path = output_dir / "final_paper" / "main.tex"
    if tex_path.is_file() and sha256(tex_path) != str(data.get("main_tex_sha256") or ""):
        findings.append("main.tex changed after visual inspection; prepare and inspect again")

    renderer = data.get("renderer", {})
    if not isinstance(renderer, dict) or str(renderer.get("status", "")).lower() != "pass":
        findings.append("full-page PDF rendering did not pass")
    elif str(renderer.get("box_probe_status", "")).lower() != "pass":
        findings.append("PDF MediaBox/CropBox probe did not pass")
    review = data.get("review", {})
    if not isinstance(review, dict) or str(review.get("status", "")).lower() != "pass":
        findings.append("overall visual review receipt is not PASS")
    elif not str(review.get("reviewer", "")).strip() or not str(review.get("reviewed_at", "")).strip():
        findings.append("visual review must record reviewer and reviewed_at")

    pages = data.get("pages", []) if isinstance(data.get("pages"), list) else []
    if not pages:
        findings.append("no rendered PDF pages are recorded")
    for page in pages:
        name = f"page {page.get('page', '?')}"
        render_path = output_dir / str(page.get("render_path") or "")
        if not render_path.is_file():
            findings.append(f"{name} render is missing")
        elif sha256(render_path) != str(page.get("render_sha256") or ""):
            findings.append(f"{name} render hash changed")
        _check_receipt(name, page.get("checks"), PAGE_CHECKS, findings)
        if str(page.get("status", "")).lower() != "pass":
            findings.append(f"{name} overall status is not PASS")
        if page.get("issues"):
            findings.append(f"{name} has unresolved issues")

    figures = data.get("figures", []) if isinstance(data.get("figures"), list) else []
    current_inventory = figure_inventory(tex_path)
    if len(figures) != len(current_inventory):
        findings.append(f"figure coverage mismatch: manifest has {len(figures)}, current TeX has {len(current_inventory)}")
    for figure in figures:
        name = f"figure {figure.get('figure_id', '?')}"
        asset_path = output_dir / str(figure.get("asset_path") or "")
        if not asset_path.is_file():
            findings.append(f"{name} asset is missing")
        elif not asset_path.resolve().is_relative_to(output_dir.resolve()):
            findings.append(f"{name} asset is outside paper_rewriting_output and is not portable")
        elif sha256(asset_path) != str(figure.get("asset_sha256") or ""):
            findings.append(f"{name} asset changed after inspection")
        if str(figure.get("render_status", "")).lower() != "pass":
            findings.append(f"{name} was not rendered for inspection")
        _check_receipt(name, figure.get("checks"), FIGURE_CHECKS, findings)
        if figure.get("story_contract"):
            panels = figure.get("panels")
            expected_panels = figure["story_contract"].get("panels", [])
            if expected_panels and not panels:
                findings.append(f"{name} has a story contract but no inspected panel receipts")
        if str(figure.get("status", "")).lower() != "pass":
            findings.append(f"{name} overall status is not PASS")
        if figure.get("issues"):
            findings.append(f"{name} has unresolved issues")

    conflicts = data.get("unresolved_conflicts", [])
    if conflicts:
        findings.append(f"{len(conflicts)} unresolved visual/semantic conflict(s) remain")
    return VisualResult(str(path), not findings, len(pages), len(figures), findings)


def to_markdown(result: VisualResult) -> str:
    lines = [
        "# Visual Readiness Check",
        "",
        f"- Manifest: `{result.manifest}`",
        f"- Status: {'PASS' if result.ok else 'FAIL'}",
        f"- PDF pages inspected: {result.page_count}",
        f"- Figures inspected: {result.figure_count}",
        "",
        "## Findings",
        "",
    ]
    lines.extend(f"- {finding}" for finding in result.findings) if result.findings else lines.append("- None")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    prepare_findings: list[str] = []
    if args.prepare:
        _manifest, prepare_findings = prepare(output_dir, args.dpi)
    result = validate(output_dir)
    if prepare_findings:
        result.findings[:0] = prepare_findings
        result.ok = False
    markdown = to_markdown(result)
    if args.write:
        (output_dir / "visual_readiness_check.md").write_text(markdown, encoding="utf-8")
    if args.json:
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
    if args.markdown or not args.json:
        print(markdown)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
