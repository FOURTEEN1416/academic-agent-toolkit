#!/usr/bin/env python3
"""Reusable release check for host-specific absolute path leakage.

The scanner is intentionally paper-agnostic. It accepts either a release
package directory or a zip file and reports file/path strings that look like
local build-machine paths, local tool-install paths, sandbox/runtime paths, or Python cache artifacts that can embed build paths.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import zipfile
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Iterable

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

@dataclass
class Finding:
    path: str
    pattern_id: str
    excerpt: str

def _frag(*parts: str) -> str:
    return "".join(parts)

def suspicious_patterns() -> list[tuple[str, re.Pattern[bytes]]]:
    # Build guarded literal strings from fragments so the release package does
    # not itself contain the exact local-path examples that it is designed to catch.
    win_users = rb"[A-Za-z]:[/\\]Users[/\\][^\s\"'<>|]+"
    unix_users = re.escape(_frag("/", "Users", "/").encode()) + rb"[^\s\"'<>|]+"
    unix_home = re.escape(_frag("/", "home", "/").encode()) + rb"[^\s\"'<>|]+"
    sandbox = re.escape(_frag("/", "mnt", "/", "data").encode()) + rb"(?:[/\\][^\s\"'<>|]+)?"
    sandbox_link = re.escape(_frag("sandbox:", "/", "mnt", "/", "data").encode()) + rb"(?:[/\\][^\s\"'<>|]+)?"
    codex_skill = re.escape(_frag(".", "codex", "/", "skills").encode())
    codex_skill_b = re.escape(_frag(".", "codex", "\\", "skills").encode())
    return [
        ("windows_user_path", re.compile(win_users)),
        ("unix_user_path", re.compile(unix_users)),
        ("unix_home_path", re.compile(unix_home)),
        ("sandbox_runtime_path", re.compile(sandbox)),
        ("sandbox_link_path", re.compile(sandbox_link)),
        ("local_codex_skill_path_posix", re.compile(codex_skill)),
        ("local_codex_skill_path_windows", re.compile(codex_skill_b)),
    ]

def suspicious_text_markers() -> list[str]:
    return [
        "璁" + "捐",
        "棰" + "濆",
        "濂" + "戜害",
        "濂" + "戟害",
        "濂" + "戠害",
        "鍥" + "炲",
        "涓" + "嬩竴",
        "\u95ff",
        "\u59ab",
        "\u9420",
        "绗" + "",
        "鎵" + "ц",
        "\ufffd",
    ]

def is_text_marker_target(name: str) -> bool:
    suffix = Path(name).suffix.lower()
    return suffix in {".md", ".py", ".json", ".yaml", ".yml", ".txt"}

def iter_targets(target: Path) -> Iterable[tuple[str, bytes]]:
    if target.is_dir():
        for path in sorted(target.rglob("*")):
            if not path.is_file():
                continue
            rel = path.relative_to(target).as_posix()
            # Ignore nested release archives in a working tree, but do not ignore Python caches:
            # .pyc files can embed build-machine paths and must fail release checks.
            if rel.endswith('.zip'):
                continue
            yield rel, path.read_bytes()
    elif target.is_file() and target.suffix.lower() == ".zip":
        with zipfile.ZipFile(target) as zf:
            for info in sorted(zf.infolist(), key=lambda x: x.filename):
                if info.is_dir():
                    continue
                name = info.filename
                yield name, zf.read(info)
    else:
        raise ValueError(f"target must be a directory or .zip file: {target}")

def excerpt(raw: bytes, start: int, end: int, width: int = 96) -> str:
    lo = max(0, start - width // 2)
    hi = min(len(raw), end + width // 2)
    text = raw[lo:hi].decode("utf-8", errors="replace")
    return " ".join(text.split())[:240]

def clean_python_caches(target: Path) -> dict[str, int]:
    """Remove __pycache__ directories and .pyc files from a release staging directory."""
    if not target.is_dir():
        raise ValueError("clean-caches requires a directory target, not a zip file")
    removed_files = 0
    removed_dirs = 0
    for pyc in sorted(target.rglob("*.pyc")):
        try:
            pyc.unlink()
            removed_files += 1
        except FileNotFoundError:
            pass
    # Remove deepest cache directories first.
    dirs = sorted([p for p in target.rglob("__pycache__") if p.is_dir()], key=lambda p: len(p.parts), reverse=True)
    for d in dirs:
        try:
            for child in d.rglob("*"):
                if child.is_file():
                    child.unlink(missing_ok=True)
            d.rmdir()
            removed_dirs += 1
        except Exception:
            # Best-effort cleanup; scan will still fail if anything remains.
            pass
    return {"removed_pyc_files": removed_files, "removed_pycache_dirs": removed_dirs}

def scan(target: Path) -> list[Finding]:
    patterns = suspicious_patterns()
    findings: list[Finding] = []
    for name, raw in iter_targets(target):
        if "__pycache__" in name or name.endswith(".pyc"):
            findings.append(Finding(name, "python_cache_artifact", "Python cache artifact must not be included in release packages because it can embed build-machine paths."))
            continue
        for pattern_id, pattern in patterns:
            for match in pattern.finditer(raw):
                # Avoid reporting the scanner's own pattern-construction source.
                if name.endswith("figure_studio_release_check_paths.py"):
                    continue
                findings.append(Finding(name, pattern_id, excerpt(raw, match.start(), match.end())))
        if is_text_marker_target(name) and not name.endswith("figure_studio_release_check_paths.py"):
            text = raw.decode("utf-8", errors="replace")
            for marker in suspicious_text_markers():
                if marker in text:
                    findings.append(Finding(name, "encoding_mojibake_marker", f"Possible mojibake marker remains: {marker}"))
                    break
    return findings

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    p_scan = sub.add_parser("scan")
    p_scan.add_argument("--target", required=True)
    p_scan.add_argument("--json-output")
    p_scan.add_argument("--fail-on-match", action="store_true")
    p_clean = sub.add_parser("clean-caches", help="remove __pycache__/ and *.pyc from a release staging directory")
    p_clean.add_argument("--target", required=True)
    p_clean.add_argument("--json-output")
    args = parser.parse_args(argv)

    if args.command == "clean-caches":
        payload = {"target": args.target, **clean_python_caches(Path(args.target))}
        if args.json_output:
            Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_output).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if args.command == "scan":
        findings = scan(Path(args.target))
        payload = {"target": args.target, "finding_count": len(findings), "findings": [asdict(f) for f in findings]}
        if args.json_output:
            Path(args.json_output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.json_output).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        if findings and args.fail_on_match:
            return 2
        return 0
    return 1

if __name__ == "__main__":
    raise SystemExit(main())
