#!/usr/bin/env python3
"""Trim the uniform background margin around a rendered diagram.

Image models paint the whole canvas of the requested aspect ratio, so a wide
flowchart on a 16:9 canvas arrives with an empty band above and below it. A
manuscript figure should be cropped to its content plus a small, even pad.

    python trim_margins.py figures/protocol.png            # in place, 3% pad
    python trim_margins.py in.png --out out.png --pad 2    # explicit output

Only near-background pixels are trimmed (default: within 12/255 of the corner
colour), so light grey boxes and thin lines survive. Prints the old and new
size; exits 0 without writing when nothing can be trimmed.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

try:
    from PIL import Image, ImageChops
except ImportError:  # pragma: no cover - the starter environment ships Pillow
    sys.stderr.write("Pillow is required: pip install pillow\n")
    sys.exit(2)


def content_box(image: Image.Image, tolerance: int) -> tuple[int, int, int, int] | None:
    rgb = image.convert("RGB")
    background = Image.new("RGB", rgb.size, rgb.getpixel((0, 0)))
    diff = ImageChops.difference(rgb, background).convert("L")
    # Pixels within `tolerance` of the corner colour count as background.
    mask = diff.point(lambda value: 255 if value > tolerance else 0)
    return mask.getbbox()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("path", type=Path)
    parser.add_argument("--out", type=Path, help="write here instead of in place")
    parser.add_argument("--pad", type=float, default=3.0, help="pad as a percent of the longer content side")
    parser.add_argument("--tolerance", type=int, default=12, help="background colour tolerance, 0-255")
    args = parser.parse_args()

    image = Image.open(args.path)
    box = content_box(image, args.tolerance)
    if box is None:
        print(f"{args.path}: no content found; left unchanged")
        return 0
    left, top, right, bottom = box
    pad = round(max(right - left, bottom - top) * args.pad / 100)
    crop = (max(0, left - pad), max(0, top - pad), min(image.width, right + pad), min(image.height, bottom + pad))
    if crop == (0, 0, image.width, image.height):
        print(f"{args.path}: already tight ({image.width}x{image.height}); left unchanged")
        return 0
    trimmed = image.crop(crop)
    out = args.out or args.path
    trimmed.save(out)
    print(f"{args.path}: {image.width}x{image.height} -> {trimmed.width}x{trimmed.height} written to {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
