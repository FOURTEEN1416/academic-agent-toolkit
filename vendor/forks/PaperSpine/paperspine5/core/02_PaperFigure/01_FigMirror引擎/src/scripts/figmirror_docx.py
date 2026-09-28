#!/usr/bin/env python3
"""Replace selected DOCX media while proving all other package bytes unchanged."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from figmirror_inventory import image_metadata, sha256_bytes, sha256_file


@dataclass(frozen=True)
class Replacement:
    target: str
    source: Path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Replace DOCX word/media entries without changing document XML, styles, anchors, or extents."
    )
    parser.add_argument("source_docx")
    parser.add_argument("output_docx")
    parser.add_argument(
        "--replace",
        action="append",
        required=True,
        metavar="PACKAGE_TARGET=IMAGE_FILE",
        help="Example: --replace word/media/image1.png=figures/rebuilt/word_image1.png",
    )
    parser.add_argument("--report", help="Optional JSON preservation report path.")
    parser.add_argument(
        "--max-aspect-drift",
        type=float,
        default=0.01,
        help="Maximum relative source-vs-replacement aspect-ratio drift (default: 0.01).",
    )
    parser.add_argument(
        "--allow-aspect-drift",
        action="store_true",
        help="Allow aspect-ratio drift; Word will retain the old drawing extent and may stretch the image.",
    )
    return parser.parse_args()


def parse_replacements(values: list[str]) -> list[Replacement]:
    replacements: list[Replacement] = []
    seen: set[str] = set()
    for raw in values:
        if "=" not in raw:
            raise ValueError(f"Invalid --replace value (missing '='): {raw}")
        target_raw, source_raw = raw.split("=", 1)
        target = str(PurePosixPath(target_raw.strip().replace("\\", "/")))
        source = Path(source_raw.strip())
        if not target.startswith("word/media/") or target.endswith("/") or ".." in PurePosixPath(target).parts:
            raise ValueError(f"Replacement target must be a safe word/media entry: {target}")
        if target in seen:
            raise ValueError(f"Duplicate replacement target: {target}")
        if not source.is_file():
            raise FileNotFoundError(source)
        if source.suffix.lower() != PurePosixPath(target).suffix.lower():
            raise ValueError(
                f"Replacement extension must match the package target: {source.suffix} vs {PurePosixPath(target).suffix}"
            )
        replacements.append(Replacement(target=target, source=source))
        seen.add(target)
    return replacements


def aspect_ratio(metadata: dict[str, object]) -> float | None:
    width = metadata.get("width_pixels")
    height = metadata.get("height_pixels")
    if isinstance(width, int) and isinstance(height, int) and width > 0 and height > 0:
        return width / height
    return None


def validate_aspect(
    target: str,
    original_data: bytes,
    replacement_data: bytes,
    max_drift: float,
    allow_drift: bool,
) -> dict[str, object]:
    original = image_metadata(target, original_data)
    replacement = image_metadata(target, replacement_data)
    original_ratio = aspect_ratio(original)
    replacement_ratio = aspect_ratio(replacement)
    drift: float | None = None
    if original_ratio and replacement_ratio:
        drift = abs(replacement_ratio - original_ratio) / original_ratio
    if drift is not None and drift > max_drift and not allow_drift:
        raise ValueError(
            f"Aspect ratio drift for {target} is {drift:.4f}, above {max_drift:.4f}; "
            "redraw to the original aspect or pass --allow-aspect-drift."
        )
    return {
        "original_image": original,
        "replacement_image": replacement,
        "aspect_ratio_drift": round(drift, 6) if drift is not None else None,
        "aspect_ratio_within_limit": drift is None or drift <= max_drift,
    }


def clone_zip_info(info: zipfile.ZipInfo) -> zipfile.ZipInfo:
    cloned = zipfile.ZipInfo(info.filename, date_time=info.date_time)
    cloned.compress_type = info.compress_type
    cloned.comment = info.comment
    cloned.extra = info.extra
    cloned.create_system = info.create_system
    cloned.create_version = info.create_version
    cloned.extract_version = info.extract_version
    cloned.flag_bits = info.flag_bits
    cloned.volume = info.volume
    cloned.internal_attr = info.internal_attr
    cloned.external_attr = info.external_attr
    return cloned


def package_hashes(path: Path) -> dict[str, str]:
    with zipfile.ZipFile(path) as package:
        return {info.filename: sha256_bytes(package.read(info.filename)) for info in package.infolist()}


def replace_docx(
    source: Path,
    output: Path,
    replacements: list[Replacement],
    max_aspect_drift: float,
    allow_aspect_drift: bool,
) -> dict[str, object]:
    if source.resolve() == output.resolve():
        raise ValueError("Refusing in-place replacement; choose a separate output DOCX.")
    if not zipfile.is_zipfile(source):
        raise ValueError(f"Not a readable DOCX/ZIP package: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)

    by_target = {replacement.target: replacement for replacement in replacements}
    replacement_reports: list[dict[str, object]] = []
    source_hashes = package_hashes(source)
    with zipfile.ZipFile(source) as source_zip:
        names = source_zip.namelist()
        if len(names) != len(set(names)):
            raise ValueError("Source DOCX contains duplicate ZIP entries; safe replacement is ambiguous.")
        missing = sorted(set(by_target) - set(names))
        if missing:
            raise ValueError(f"Replacement target(s) missing from source DOCX: {', '.join(missing)}")

        fd, temp_name = tempfile.mkstemp(prefix=f".{output.stem}.figmirror-", suffix=".docx", dir=output.parent)
        os.close(fd)
        temp_path = Path(temp_name)
        try:
            with zipfile.ZipFile(temp_path, "w") as output_zip:
                output_zip.comment = source_zip.comment
                for info in source_zip.infolist():
                    original_data = source_zip.read(info.filename)
                    data = original_data
                    if info.filename in by_target:
                        replacement = by_target[info.filename]
                        data = replacement.source.read_bytes()
                        aspect = validate_aspect(
                            info.filename,
                            original_data,
                            data,
                            max_aspect_drift,
                            allow_aspect_drift,
                        )
                        replacement_reports.append(
                            {
                                "target": info.filename,
                                "replacement_source": str(replacement.source.resolve()),
                                "original_sha256": sha256_bytes(original_data),
                                "replacement_sha256": sha256_bytes(data),
                                "original_bytes": len(original_data),
                                "replacement_bytes": len(data),
                                **aspect,
                            }
                        )
                    output_zip.writestr(clone_zip_info(info), data)
            with zipfile.ZipFile(temp_path) as test_zip:
                bad_entry = test_zip.testzip()
                if bad_entry:
                    raise ValueError(f"Output DOCX failed CRC verification at {bad_entry}")
            temp_path.replace(output)
        finally:
            if temp_path.exists():
                temp_path.unlink()

    output_hashes = package_hashes(output)
    changed_entries = sorted(name for name in source_hashes if source_hashes[name] != output_hashes.get(name))
    expected_changed = sorted(by_target)
    if changed_entries != expected_changed:
        raise ValueError(
            "Preservation verification failed; changed entries were "
            f"{changed_entries}, expected only {expected_changed}."
        )
    if set(source_hashes) != set(output_hashes):
        raise ValueError("Preservation verification failed; ZIP entry set changed.")

    return {
        "schema_version": "1.0",
        "status": "PASS",
        "source_docx": str(source.resolve()),
        "output_docx": str(output.resolve()),
        "source_sha256": sha256_file(source),
        "output_sha256": sha256_file(output),
        "entry_count": len(source_hashes),
        "changed_entries": changed_entries,
        "unchanged_entries_verified": len(source_hashes) - len(changed_entries),
        "document_xml_preserved": source_hashes.get("word/document.xml") == output_hashes.get("word/document.xml"),
        "styles_xml_preserved": source_hashes.get("word/styles.xml") == output_hashes.get("word/styles.xml"),
        "relationships_preserved": source_hashes.get("word/_rels/document.xml.rels")
        == output_hashes.get("word/_rels/document.xml.rels"),
        "replacements": replacement_reports,
    }


def main() -> int:
    args = parse_args()
    try:
        replacements = parse_replacements(args.replace)
        report = replace_docx(
            Path(args.source_docx),
            Path(args.output_docx),
            replacements,
            max_aspect_drift=max(0.0, args.max_aspect_drift),
            allow_aspect_drift=args.allow_aspect_drift,
        )
        if args.report:
            report_path = Path(args.report)
            report_path.parent.mkdir(parents=True, exist_ok=True)
            report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    except (OSError, ValueError, zipfile.BadZipFile) as exc:
        print(f"FigMirror DOCX replacement failed: {exc}")
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
