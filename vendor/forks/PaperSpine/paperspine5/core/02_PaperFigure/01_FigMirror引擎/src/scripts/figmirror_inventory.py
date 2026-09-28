#!/usr/bin/env python3
"""Inventory figure assets and placements in a DOCX package.

FigMirror uses this inventory as the immutable source-side record before any
redraw or media replacement. The script is standard-library only and never
modifies the source document.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
import zipfile
from pathlib import Path, PurePosixPath
from xml.etree import ElementTree as ET


NS = {
    "a": "http://schemas.openxmlformats.org/drawingml/2006/main",
    "r": "http://schemas.openxmlformats.org/officeDocument/2006/relationships",
    "rel": "http://schemas.openxmlformats.org/package/2006/relationships",
    "w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main",
    "wp": "http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing",
}

EMU_PER_INCH = 914400


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inventory DOCX figure media, relationships, placements, dimensions, and hashes."
    )
    parser.add_argument("source_docx", help="Source .docx file; it is never modified.")
    parser.add_argument("--output-dir", default="paper_rewriting_output/figmirror")
    parser.add_argument(
        "--extract",
        action="store_true",
        help="Extract media assets into <output-dir>/source_media/.",
    )
    return parser.parse_args()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def png_metadata(data: bytes) -> tuple[int | None, int | None, float | None, float | None]:
    if len(data) < 24 or data[:8] != b"\x89PNG\r\n\x1a\n":
        return None, None, None, None
    width, height = struct.unpack(">II", data[16:24])
    dpi_x: float | None = None
    dpi_y: float | None = None
    offset = 8
    while offset + 12 <= len(data):
        length = struct.unpack(">I", data[offset : offset + 4])[0]
        chunk_type = data[offset + 4 : offset + 8]
        payload = data[offset + 8 : offset + 8 + length]
        if chunk_type == b"pHYs" and len(payload) == 9 and payload[8] == 1:
            ppm_x, ppm_y = struct.unpack(">II", payload[:8])
            dpi_x = round(ppm_x * 0.0254, 3)
            dpi_y = round(ppm_y * 0.0254, 3)
            break
        offset += 12 + length
    return width, height, dpi_x, dpi_y


def gif_metadata(data: bytes) -> tuple[int | None, int | None]:
    if len(data) >= 10 and data[:6] in {b"GIF87a", b"GIF89a"}:
        return struct.unpack("<HH", data[6:10])
    return None, None


def jpeg_metadata(data: bytes) -> tuple[int | None, int | None]:
    if len(data) < 4 or data[:2] != b"\xff\xd8":
        return None, None
    offset = 2
    sof_markers = {
        0xC0,
        0xC1,
        0xC2,
        0xC3,
        0xC5,
        0xC6,
        0xC7,
        0xC9,
        0xCA,
        0xCB,
        0xCD,
        0xCE,
        0xCF,
    }
    while offset + 4 <= len(data):
        if data[offset] != 0xFF:
            offset += 1
            continue
        marker = data[offset + 1]
        offset += 2
        if marker in {0xD8, 0xD9}:
            continue
        if offset + 2 > len(data):
            break
        length = struct.unpack(">H", data[offset : offset + 2])[0]
        if length < 2 or offset + length > len(data):
            break
        if marker in sof_markers and length >= 7:
            height, width = struct.unpack(">HH", data[offset + 3 : offset + 7])
            return width, height
        offset += length
    return None, None


def image_metadata(name: str, data: bytes) -> dict[str, object]:
    suffix = PurePosixPath(name).suffix.lower()
    width: int | None = None
    height: int | None = None
    dpi_x: float | None = None
    dpi_y: float | None = None
    if suffix == ".png":
        width, height, dpi_x, dpi_y = png_metadata(data)
    elif suffix in {".jpg", ".jpeg"}:
        width, height = jpeg_metadata(data)
    elif suffix == ".gif":
        width, height = gif_metadata(data)
    return {
        "format": suffix.lstrip(".") or "unknown",
        "width_pixels": width,
        "height_pixels": height,
        "dpi_x": dpi_x,
        "dpi_y": dpi_y,
    }


def relationship_target(target: str) -> str:
    posix = PurePosixPath(target.replace("\\", "/"))
    if str(posix).startswith("/"):
        parts = posix.parts[1:]
    else:
        parts = ("word", *posix.parts)
    clean: list[str] = []
    for part in parts:
        if part in {"", "."}:
            continue
        if part == "..":
            if clean:
                clean.pop()
            continue
        clean.append(part)
    return "/".join(clean)


def parse_relationships(package: zipfile.ZipFile) -> dict[str, str]:
    rel_path = "word/_rels/document.xml.rels"
    if rel_path not in package.namelist():
        return {}
    root = ET.fromstring(package.read(rel_path))
    mapping: dict[str, str] = {}
    for rel in root.findall("rel:Relationship", NS):
        rel_id = rel.attrib.get("Id", "")
        rel_type = rel.attrib.get("Type", "")
        target = rel.attrib.get("Target", "")
        if rel_id and target and rel_type.endswith("/image"):
            mapping[rel_id] = relationship_target(target)
    return mapping


def placement_records(package: zipfile.ZipFile, relationships: dict[str, str]) -> list[dict[str, object]]:
    document_path = "word/document.xml"
    if document_path not in package.namelist():
        return []
    root = ET.fromstring(package.read(document_path))
    placements: list[dict[str, object]] = []
    for drawing in root.findall(".//w:drawing", NS):
        extent = drawing.find(".//wp:extent", NS)
        doc_pr = drawing.find(".//wp:docPr", NS)
        cx = int(extent.attrib.get("cx", "0")) if extent is not None else 0
        cy = int(extent.attrib.get("cy", "0")) if extent is not None else 0
        for blip in drawing.findall(".//a:blip", NS):
            rel_id = blip.attrib.get(f"{{{NS['r']}}}embed", "")
            target = relationships.get(rel_id, "")
            if not target:
                continue
            placements.append(
                {
                    "placement_id": f"fig-{len(placements) + 1:03d}",
                    "relationship_id": rel_id,
                    "media_target": target,
                    "extent_emu": [cx, cy],
                    "physical_inches": [
                        round(cx / EMU_PER_INCH, 4) if cx else None,
                        round(cy / EMU_PER_INCH, 4) if cy else None,
                    ],
                    "doc_properties": {
                        "id": doc_pr.attrib.get("id") if doc_pr is not None else None,
                        "name": doc_pr.attrib.get("name") if doc_pr is not None else None,
                        "description": doc_pr.attrib.get("descr") if doc_pr is not None else None,
                        "title": doc_pr.attrib.get("title") if doc_pr is not None else None,
                    },
                }
            )
    return placements


def build_inventory(source: Path, output_dir: Path, extract: bool) -> dict[str, object]:
    if source.suffix.lower() != ".docx":
        raise ValueError("FigMirror DOCX inventory currently requires a .docx source file.")
    if not source.is_file():
        raise FileNotFoundError(source)
    if not zipfile.is_zipfile(source):
        raise ValueError(f"Not a readable DOCX/ZIP package: {source}")

    output_dir.mkdir(parents=True, exist_ok=True)
    extraction_dir = output_dir / "source_media"
    with zipfile.ZipFile(source) as package:
        names = package.namelist()
        if "word/document.xml" not in names:
            raise ValueError("DOCX package is missing word/document.xml")
        relationships = parse_relationships(package)
        placements = placement_records(package, relationships)
        referenced = {record["media_target"] for record in placements}
        media_targets = sorted(name for name in names if name.startswith("word/media/") and not name.endswith("/"))
        assets: list[dict[str, object]] = []
        for target in media_targets:
            data = package.read(target)
            record: dict[str, object] = {
                "media_target": target,
                "bytes": len(data),
                "sha256": sha256_bytes(data),
                "referenced_in_document": target in referenced,
                **image_metadata(target, data),
            }
            if extract:
                relative_parts = PurePosixPath(target).parts[2:]
                destination = extraction_dir.joinpath(*relative_parts)
                destination.parent.mkdir(parents=True, exist_ok=True)
                destination.write_bytes(data)
                record["extracted_path"] = str(destination.resolve())
            assets.append(record)

    return {
        "schema_version": "1.0",
        "inventory_type": "docx",
        "source_document": str(source.resolve()),
        "source_sha256": sha256_file(source),
        "media_assets": assets,
        "placements": placements,
        "unreferenced_media": sorted(
            str(record["media_target"])
            for record in assets
            if not bool(record["referenced_in_document"])
        ),
        "warnings": [],
    }


def to_markdown(inventory: dict[str, object]) -> str:
    assets = list(inventory.get("media_assets") or [])
    placements = list(inventory.get("placements") or [])
    lines = [
        "# FigMirror Figure Source Map",
        "",
        f"- Source document: `{inventory.get('source_document', '')}`",
        f"- Source SHA-256: `{inventory.get('source_sha256', '')}`",
        f"- Media assets: {len(assets)}",
        f"- Document placements: {len(placements)}",
        "",
        "## Media Assets",
        "",
        "| Target | Pixels | DPI | Bytes | SHA-256 | Referenced |",
        "|---|---:|---:|---:|---|---|",
    ]
    for asset in assets:
        pixels = f"{asset.get('width_pixels') or '?'} x {asset.get('height_pixels') or '?'}"
        dpi = f"{asset.get('dpi_x') or '?'} x {asset.get('dpi_y') or '?'}"
        lines.append(
            f"| `{asset.get('media_target', '')}` | {pixels} | {dpi} | {asset.get('bytes', 0)} | "
            f"`{asset.get('sha256', '')}` | {'yes' if asset.get('referenced_in_document') else 'no'} |"
        )
    lines.extend(
        [
            "",
            "## Placements",
            "",
            "| Placement | Relationship | Media target | Extent (EMU) | Physical size (in) |",
            "|---|---|---|---:|---:|",
        ]
    )
    for placement in placements:
        extent = placement.get("extent_emu") or []
        inches = placement.get("physical_inches") or []
        lines.append(
            f"| {placement.get('placement_id', '')} | `{placement.get('relationship_id', '')}` | "
            f"`{placement.get('media_target', '')}` | {extent} | {inches} |"
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    try:
        source = Path(args.source_docx)
        output_dir = Path(args.output_dir)
        inventory = build_inventory(source, output_dir, args.extract)
        json_path = output_dir / "figure_inventory.json"
        markdown_path = output_dir / "figure_source_map.md"
        json_path.write_text(json.dumps(inventory, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        markdown_path.write_text(to_markdown(inventory), encoding="utf-8")
    except (OSError, ValueError, ET.ParseError, zipfile.BadZipFile) as exc:
        print(f"FigMirror inventory failed: {exc}", file=sys.stderr)
        return 1
    print(f"Wrote {json_path}")
    print(f"Wrote {markdown_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
