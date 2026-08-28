#!/usr/bin/env python3
"""Stable Python entry point for the vendored CodeSucker core."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parent
CLI = ROOT / "codesucker-cli.mjs"
VENDOR = ROOT / "codesucker-core"
TSX_LOADER = VENDOR / "node_modules" / "tsx" / "dist" / "loader.mjs"
CONFIG_SCHEMA_VERSION = 1
CORE_VERSION = "0.4.4"
CORE_COMMIT = "b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def _safe_relative(path: Path, root: Path) -> str:
    return path.resolve().relative_to(root.resolve()).as_posix()


def _core_hash() -> str:
    digest = hashlib.sha256()
    for path in sorted((VENDOR / "packages" / "core" / "src").glob("*.ts")):
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()


def _output_hashes(workspace: Path) -> dict[str, str]:
    result = {}
    base = workspace / "source-materials"
    for path in sorted(item for item in base.rglob("*") if item.is_file()):
        if path.name == "SOURCE_MATERIALS_MANIFEST.json":
            continue
        result[path.relative_to(workspace).as_posix()] = sha256_file(path)
    return result


def _load_rules_version() -> str:
    version_path = VENDOR / "packages" / "core" / "src" / "version.ts"
    text = version_path.read_text(encoding="utf-8")
    match = re.search(r"RULES_VERSION\s*=\s*['\"]([^'\"]+)['\"]", text)
    if match:
        return match.group(1)
    raise RuntimeError("vendored CodeSucker rules version is unavailable")


def run_source_materials(
    config: dict[str, Any],
    workspace: Path,
    allow_legacy_fallback: bool = False,
) -> dict[str, Any]:
    """Run the standard backend and return its validated manifest payload."""
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    if not CLI.is_file() or not VENDOR.is_dir():
        raise RuntimeError("vendored CodeSucker core is incomplete")
    if not TSX_LOADER.is_file():
        raise RuntimeError("vendored TypeScript loader is missing; run npm install in tools/codesucker-core")

    config_path = workspace / "source-materials.config.json"
    config_payload = dict(config)
    config_payload.setdefault("sourceMode", "real")
    config_payload.setdefault("configSchemaVersion", CONFIG_SCHEMA_VERSION)
    config_payload.setdefault("rulesVersion", _load_rules_version())
    config_payload.setdefault("coreVersion", CORE_VERSION)
    config_payload.setdefault("coreCommit", CORE_COMMIT)
    config_path.write_text(json.dumps(config_payload, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    command = [
        "node", "--import", TSX_LOADER.as_uri(), str(CLI),
        "--config", str(config_path), "--workspace", str(workspace),
    ]
    completed = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    (workspace / "source-materials.stdout.log").write_text(completed.stdout, encoding="utf-8")
    (workspace / "source-materials.stderr.log").write_text(completed.stderr, encoding="utf-8")
    if completed.returncode != 0:
        if allow_legacy_fallback:
            raise RuntimeError("legacy fallback is intentionally explicit but not implemented by the standard bridge")
        raise RuntimeError(f"CodeSucker CLI failed with exit code {completed.returncode}: {completed.stderr.strip()}")
    try:
        cli_result = json.loads(completed.stdout.strip().splitlines()[-1])
    except (json.JSONDecodeError, IndexError) as exc:
        raise RuntimeError("CodeSucker CLI did not return a JSON result") from exc
    if cli_result.get("ok") is not True:
        raise RuntimeError("CodeSucker CLI returned ok=false")

    manifest_path = workspace / "source-materials" / "SOURCE_MATERIALS_MANIFEST.json"
    if not manifest_path.is_file():
        raise RuntimeError("CodeSucker CLI did not create SOURCE_MATERIALS_MANIFEST.json")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    # Validate manifest schema version matches core constant
    if manifest.get("schemaVersion") != 1:
        raise RuntimeError(f"unexpected manifest schemaVersion: {manifest.get('schemaVersion')}")
    if manifest.get("coreVersion") != CORE_VERSION:
        raise RuntimeError(f"manifest coreVersion mismatch: {manifest.get('coreVersion')}")
    if manifest.get("coreCommit") != CORE_COMMIT:
        raise RuntimeError(f"manifest coreCommit mismatch: {manifest.get('coreCommit')}")
    expected_rules_version = _load_rules_version()
    if manifest.get("rulesVersion") != expected_rules_version:
        raise RuntimeError(f"manifest rulesVersion mismatch: {manifest.get('rulesVersion')}")
    # The config file records provenance inputs for the bridge; the vendored CLI
    # owns the canonical manifest schema/rules/core fields. Keep both visible
    # without requiring the CLI to echo every bridge-only config key.
    manifest["configFile"] = _safe_relative(config_path, workspace)
    manifest["configSha256"] = sha256_file(config_path)
    manifest["coreSha256"] = _core_hash()
    manifest["outputSha256"] = _output_hashes(workspace)
    manifest["commands"] = [{"command": command, "exit_code": completed.returncode}]
    manifest["logs"] = ["source-materials.stdout.log", "source-materials.stderr.log"]
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Run vendored CodeSucker source-materials pipeline")
    parser.add_argument("--config", required=True)
    parser.add_argument("--workspace", required=True)
    parser.add_argument("--allow-legacy-fallback", action="store_true")
    args = parser.parse_args()
    config = json.loads(Path(args.config).read_text(encoding="utf-8"))
    result = run_source_materials(config, Path(args.workspace), args.allow_legacy_fallback)
    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
