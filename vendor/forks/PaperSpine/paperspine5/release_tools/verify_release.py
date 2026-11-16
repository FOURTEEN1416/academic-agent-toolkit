#!/usr/bin/env python3
"""Verify the public PaperSpine5 prerelease metadata and local source contract."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""): h.update(b)
    return h.hexdigest()
def main()->int:
    manifest=json.loads((ROOT/"website"/"downloads"/"manifest.json").read_text(encoding="utf-8"))
    assert manifest["product"]=="PaperSpine5"
    assert manifest["tag"]=="v"+manifest["version"]
    assert manifest["repository"]=="https://github.com/WUBING2023/PaperSpine"
    assert {x["kind"] for x in manifest["artifacts"]} == {
        "suite", "suite-linux-x86_64", "suite-macos-arm64", "suite-macos-x86_64"
    }
    checksum=(ROOT/"website"/"downloads"/"checksums.sha256").read_text(encoding="ascii")
    for item in manifest["artifacts"]:
        assert len(item["sha256"])==64 and item["bytes"]>0
        assert item["sha256"] in checksum and item["file"] in checksum
        assert item["download_url"].startswith("https://github.com/WUBING2023/PaperSpine/releases/download/")
    for path in [ROOT/"product-release.json",ROOT/"website"/"downloads"/"manifest.json",ROOT/"release"/manifest["tag"]/"manifest.json"]:
        text=path.read_text(encoding="utf-8")
        for forbidden in ("M:\\项目","C:\\Users\\Wubin","work_carbon_submission"): assert forbidden not in text
    print(json.dumps({"status":"PASS","version":manifest["version"],"artifacts":len(manifest["artifacts"]),"suite_bytes":next(x["bytes"] for x in manifest["artifacts"] if x["kind"]=="suite")},ensure_ascii=False))
    return 0
if __name__=="__main__": raise SystemExit(main())
