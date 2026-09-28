#!/usr/bin/env python3
"""Verify the committed PaperSpine5 release contract and public evidence."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
VERSION = "0.3.0-rc.1"
EXPECTED_CORE = "9eed412bf2a40b1e00787cd04de2adf696a662055ea31152ebc8f2899e2ba95f"
EXPECTED_ARTIFACTS = {
    "paperspine5-skill-0.3.0-rc.1.zip": (577038, "04cf4eefcf467054ab0c6da38bb5fc4cc264c8132efc8d4ccc23c03d0c44766d"),
    "paperspine5-codex-plugin-0.3.0-rc.1.zip": (589272, "a5c0553ace8c96e547e2d2e4ec1063c74bab06d78528b8b2db26eeb064875f87"),
    "paperspine5-claude-code-plugin-0.3.0-rc.1.zip": (591636, "ae181ce48e0168b9d3492dd0af3695ab00dad5a002cc8a7dcbe246c857424e29"),
    "dsh-paperspine5-0.3.0-rc.1.zip": (577009, "57495524d0f81f1b0ea24828e53546ce306a8733e96450528d064921c18c7655"),
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def core_digest(core: Path) -> tuple[str, int]:
    files = sorted(
        (
            path
            for path in core.rglob("*")
            if path.is_file()
            and "__pycache__" not in path.parts
            and ".pytest_cache" not in path.parts
            and path.suffix.lower() not in {".pyc", ".pyo"}
        ),
        key=lambda path: path.relative_to(core).as_posix(),
    )
    lines = [f"{sha256(path)}  {path.relative_to(core).as_posix()}\n" for path in files]
    return hashlib.sha256("".join(lines).encode("utf-8")).hexdigest(), len(files)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def main() -> int:
    manifest_path = ROOT / "website" / "downloads" / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    require(manifest["product"] == "PaperSpine5", "unexpected manifest product")
    require(manifest["version"] == VERSION, "unexpected manifest version")
    require(manifest["tag"] == f"v{VERSION}", "unexpected release tag")
    require(manifest["repository"] == "https://github.com/WUBING2023/PaperSpine", "canonical repository drift")
    require(manifest["core"]["sha256"] == EXPECTED_CORE, "manifest core digest drift")
    require(manifest["validation"] == {"status": "PASS", "checks": 43, "failed": []}, "validation evidence drift")

    artifacts = {item["file"]: item for item in manifest["artifacts"]}
    require(set(artifacts) == set(EXPECTED_ARTIFACTS), "artifact set drift")
    for name, (expected_bytes, expected_sha) in EXPECTED_ARTIFACTS.items():
        item = artifacts[name]
        require(item["bytes"] == expected_bytes, f"byte count drift: {name}")
        require(item["sha256"] == expected_sha, f"checksum drift: {name}")
        expected_url = f"https://github.com/WUBING2023/PaperSpine/releases/download/v{VERSION}/{name}"
        require(item["download_url"] == expected_url, f"download URL drift: {name}")

    digest, count = core_digest(ROOT / "paperspine5" / "core")
    require(count == 176, f"core file count drift: {count}")
    require(digest == EXPECTED_CORE, f"core digest drift: {digest}")

    public_files = [
        ROOT / "website" / "downloads" / "manifest.json",
        ROOT / "release" / f"v{VERSION}" / "manifest.json",
        ROOT / "release" / f"v{VERSION}" / "CORE-CONSISTENCY.json",
        ROOT / "release" / f"v{VERSION}" / "BUILD-VALIDATION-REPORT.md",
        ROOT / "release" / f"v{VERSION}" / "PUBLIC-RELEASE-EVIDENCE.json",
    ]
    forbidden = ("M:\\项目", "M:\\RBP", "C:\\Users\\Wubin", "work_carbon_submission")
    for path in public_files:
        text = path.read_text(encoding="utf-8")
        require(not any(marker in text for marker in forbidden), f"private marker in {path}")

    print(json.dumps({"status": "PASS", "core_files": count, "core_sha256": digest, "artifacts": 4, "checks": 43}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
