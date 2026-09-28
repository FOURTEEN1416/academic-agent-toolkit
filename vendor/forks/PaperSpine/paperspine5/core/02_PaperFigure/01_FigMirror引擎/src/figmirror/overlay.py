"""Deterministic blueprint-to-vector comparison sheets for visual QA."""

from __future__ import annotations

from pathlib import Path
from typing import Any


def _fit_on_white(image: Any, size: tuple[int, int]) -> Any:
    from PIL import Image

    fitted = image.convert("RGB")
    fitted.thumbnail(size, Image.Resampling.LANCZOS)
    canvas = Image.new("RGB", size, "white")
    offset = ((size[0] - fitted.width) // 2, (size[1] - fitted.height) // 2)
    canvas.paste(fitted, offset)
    return canvas


def build_overlay_sheet(
    blueprint_path: str | Path,
    vector_preview_path: str | Path,
    output_path: str | Path,
    *,
    panel_size: tuple[int, int] = (1200, 800),
) -> dict[str, object]:
    """Create blueprint, vector, and 50% overlay panels on one QA sheet.

    The overlay is deliberately a diagnostic artifact, not a similarity score:
    generative blueprints may contain scientifically incorrect detail that the
    vector reconstruction is expected to replace.
    """

    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as exc:  # pragma: no cover - depends on runtime packaging
        raise ValueError("Pillow is required to build an overlay review sheet") from exc

    blueprint = Path(blueprint_path).resolve()
    vector = Path(vector_preview_path).resolve()
    output = Path(output_path).resolve()
    if not blueprint.is_file():
        raise ValueError(f"blueprint image not found: {blueprint}")
    if not vector.is_file():
        raise ValueError(f"vector preview not found: {vector}")
    if panel_size[0] < 320 or panel_size[1] < 240:
        raise ValueError("panel_size is too small for a useful overlay review")

    with Image.open(blueprint) as raw_blueprint, Image.open(vector) as raw_vector:
        blueprint_size = raw_blueprint.size
        vector_size = raw_vector.size
        left = _fit_on_white(raw_blueprint, panel_size)
        middle = _fit_on_white(raw_vector, panel_size)

    overlay = Image.blend(left, middle, 0.5)
    header = 74
    gap = 18
    sheet = Image.new(
        "RGB",
        (panel_size[0] * 3 + gap * 4, panel_size[1] + header + gap * 2),
        "#e9eef0",
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=22)
    labels = ("AI BLUEPRINT", "EDITABLE VECTOR", "50% STRUCTURE OVERLAY")
    panels = (left, middle, overlay)
    for index, (label, panel) in enumerate(zip(labels, panels, strict=True)):
        x = gap + index * (panel_size[0] + gap)
        draw.text((x, 22), label, fill="#18323a", font=font)
        sheet.paste(panel, (x, header))

    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output, format="PNG", optimize=True)
    return {
        "schema_version": "0.1",
        "status": "PASS",
        "blueprint": str(blueprint),
        "vector_preview": str(vector),
        "output": str(output),
        "blueprint_size": list(blueprint_size),
        "vector_preview_size": list(vector_size),
        "normalization_canvas": list(panel_size),
        "interpretation": "Diagnostic only; semantic corrections may intentionally differ from the blueprint.",
    }
