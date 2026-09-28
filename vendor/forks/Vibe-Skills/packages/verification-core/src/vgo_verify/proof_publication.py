from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence


PROOF_SCHEMA_VERSION = 1


def _utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _display_path(path: Path, repo_root: Path) -> str:
    resolved = path.resolve()
    try:
        return resolved.relative_to(repo_root.resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()


def _resolve_path(path: str | Path, repo_root: Path) -> Path:
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = repo_root / candidate
    return candidate.resolve()


def _artifact_digest(path: Path, repo_root: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"proof artifact does not exist: {path}")
    return {
        "path": _display_path(path, repo_root),
        "sha256": _sha256(path),
        "size_bytes": path.stat().st_size,
    }


def _command_artifact(path: Path, repo_root: Path) -> dict[str, Any]:
    if path.is_file():
        return _artifact_digest(path, repo_root)
    return {
        "path": _display_path(path, repo_root),
        "missing": True,
    }


def _resolve_commit_sha(repo_root: Path, explicit: str | None) -> str:
    candidate = str(explicit or os.environ.get("GITHUB_SHA") or "").strip()
    if candidate:
        return candidate
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    candidate = result.stdout.strip()
    if result.returncode != 0 or not candidate:
        raise ValueError("proof publication requires a commit SHA")
    return candidate


def _execution_environment(repo_root: Path) -> dict[str, str]:
    environment = {
        "platform": platform.platform(),
        "python_version": platform.python_version(),
        "python_implementation": platform.python_implementation(),
        "working_directory": repo_root.resolve().as_posix(),
    }
    for name in (
        "GITHUB_ACTIONS",
        "GITHUB_EVENT_NAME",
        "GITHUB_JOB",
        "GITHUB_REF",
        "GITHUB_REPOSITORY",
        "GITHUB_RUN_ATTEMPT",
        "GITHUB_RUN_ID",
        "GITHUB_WORKFLOW",
        "RUNNER_ARCH",
        "RUNNER_OS",
    ):
        value = str(os.environ.get(name) or "").strip()
        if value:
            environment[name.lower()] = value
    return environment


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def run_command(
    *,
    repo_root: str | Path,
    command: Sequence[str],
    output_path: str | Path,
    artifact_paths: Sequence[str | Path] = (),
    commit_sha: str | None = None,
    label: str | None = None,
) -> dict[str, Any]:
    root = Path(repo_root).resolve()
    argv = [str(item) for item in command]
    if not argv:
        raise ValueError("proof command must not be empty")
    proof_path = _resolve_path(output_path, root)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    stdout_path = proof_path.with_suffix(".stdout.log")
    stderr_path = proof_path.with_suffix(".stderr.log")

    completed = subprocess.run(
        argv,
        cwd=root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    stdout_path.write_bytes(completed.stdout)
    stderr_path.write_bytes(completed.stderr)
    if completed.stdout:
        sys.stdout.buffer.write(completed.stdout)
        sys.stdout.buffer.flush()
    if completed.stderr:
        sys.stderr.buffer.write(completed.stderr)
        sys.stderr.buffer.flush()

    declared_artifact_paths = [
        _resolve_path(path, root) for path in artifact_paths
    ]
    digest_paths = [*declared_artifact_paths, stdout_path, stderr_path]
    artifact_evidence = [
        _command_artifact(path, root)
        for path in dict.fromkeys(digest_paths)
    ]
    missing_artifact_count = sum(
        not path.is_file() for path in declared_artifact_paths
    )
    proof = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "proof_kind": "command",
        "generated_at": _utc_now(),
        "command": {
            "label": str(label or Path(argv[0]).name),
            "argv": argv,
            "display": subprocess.list2cmdline(argv),
        },
        "result": (
            "PASS"
            if completed.returncode == 0 and missing_artifact_count == 0
            else "FAIL"
        ),
        "exit_code": completed.returncode,
        "missing_artifact_count": missing_artifact_count,
        "commit_sha": _resolve_commit_sha(root, commit_sha),
        "environment": _execution_environment(root),
        "artifacts": artifact_evidence,
    }
    _write_json(proof_path, proof)
    return proof


def aggregate_proofs(
    *,
    repo_root: str | Path,
    proof_paths: Sequence[str | Path],
    output_directory: str | Path,
    artifact_paths: Sequence[str | Path] = (),
) -> dict[str, Path]:
    root = Path(repo_root).resolve()
    resolved_proof_paths = [_resolve_path(path, root) for path in proof_paths]
    if not resolved_proof_paths:
        raise ValueError("proof aggregation requires at least one command proof")
    proofs: list[dict[str, Any]] = []
    existing_proof_paths: list[Path] = []
    absent_proofs: list[str] = []
    for path in resolved_proof_paths:
        if not path.is_file():
            absent_proofs.append(_display_path(path, root))
            continue
        payload = json.loads(path.read_text(encoding="utf-8-sig"))
        if not isinstance(payload, dict) or payload.get("proof_kind") != "command":
            raise ValueError(f"unsupported command proof: {path}")
        proofs.append(payload)
        existing_proof_paths.append(path)
    if proofs:
        commit_shas = {
            str(proof.get("commit_sha") or "").strip() for proof in proofs
        }
        if "" in commit_shas or len(commit_shas) != 1:
            raise ValueError("all command proofs must identify the same commit SHA")
        commit_sha = next(iter(commit_shas))
    else:
        commit_sha = _resolve_commit_sha(root, None)

    aggregate_artifacts: list[dict[str, Any]] = [
        _artifact_digest(path, root) for path in existing_proof_paths
    ]
    aggregate_artifacts.extend(
        _command_artifact(_resolve_path(path, root), root) for path in artifact_paths
    )
    for proof in proofs:
        for artifact in proof.get("artifacts") or []:
            if isinstance(artifact, dict):
                aggregate_artifacts.append(dict(artifact))
    unique_artifacts: dict[tuple[str, str], dict[str, Any]] = {}
    missing_artifacts: dict[str, dict[str, Any]] = {
        path: {
            "path": path,
            "missing": True,
            "artifact_kind": "command_proof",
        }
        for path in absent_proofs
    }
    for artifact in aggregate_artifacts:
        if artifact.get("missing"):
            missing_artifacts[str(artifact.get("path") or "")] = artifact
            continue
        key = (str(artifact.get("path") or ""), str(artifact.get("sha256") or ""))
        unique_artifacts[key] = artifact

    overall_result = "PASS" if (
        proofs
        and not absent_proofs
        and not missing_artifacts
        and all(
            proof.get("result") == "PASS" and proof.get("exit_code") == 0
            for proof in proofs
        )
    ) else "FAIL"
    output_root = _resolve_path(output_directory, root)
    proof_bundle_path = output_root / "proof-bundle.json"
    current_state_json_path = output_root / "current-state.json"
    current_state_markdown_path = output_root / "current-state.md"
    proof_bundle = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "proof_kind": "bundle",
        "generated_at": _utc_now(),
        "result": overall_result,
        "commit_sha": commit_sha,
        "proofs": proofs,
        "absent_proofs": absent_proofs,
        "artifact_digests": list(unique_artifacts.values()),
        "missing_artifacts": list(missing_artifacts.values()),
    }
    _write_json(proof_bundle_path, proof_bundle)

    repository = str(os.environ.get("GITHUB_REPOSITORY") or "").strip()
    links = {}
    if repository:
        links = {
            "ci": f"https://github.com/{repository}/actions",
            "latest_release": f"https://github.com/{repository}/releases/latest",
        }
    current_state = {
        "schema_version": PROOF_SCHEMA_VERSION,
        "generated_at": _utc_now(),
        "result": overall_result,
        "commit_sha": commit_sha,
        "commands": [
            {
                "label": proof["command"]["label"],
                "result": proof["result"],
                "exit_code": proof["exit_code"],
            }
            for proof in proofs
        ],
        "absent_proofs": absent_proofs,
        "proof_bundle": _artifact_digest(proof_bundle_path, root),
        "links": links,
    }
    _write_json(current_state_json_path, current_state)
    markdown_lines = [
        "# Generated Current State",
        "",
        f"- Result: **{overall_result}**",
        f"- Commit: `{current_state['commit_sha']}`",
        f"- Generated: `{current_state['generated_at']}`",
        "",
        "## Commands",
        "",
    ]
    markdown_lines.extend(
        f"- `{item['label']}`: **{item['result']}** (exit `{item['exit_code']}`)"
        for item in current_state["commands"]
    )
    if absent_proofs:
        markdown_lines.extend(["", "## Missing Proofs", ""])
        markdown_lines.extend(f"- `{path}`" for path in absent_proofs)
    current_state_markdown_path.parent.mkdir(parents=True, exist_ok=True)
    current_state_markdown_path.write_text(
        "\n".join(markdown_lines) + "\n",
        encoding="utf-8",
    )
    return {
        "proof_bundle": proof_bundle_path,
        "current_state_json": current_state_json_path,
        "current_state_markdown": current_state_markdown_path,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Publish attributed Vibe-Skills proof")
    subparsers = parser.add_subparsers(dest="action", required=True)

    run_parser = subparsers.add_parser("run", help="Run a command and write proof")
    run_parser.add_argument("--repo-root", default=".")
    run_parser.add_argument("--output", required=True)
    run_parser.add_argument("--artifact", action="append", default=[])
    run_parser.add_argument("--commit-sha")
    run_parser.add_argument("--label")
    run_parser.add_argument("command", nargs=argparse.REMAINDER)

    aggregate_parser = subparsers.add_parser(
        "aggregate",
        help="Aggregate command proofs and generate current state",
    )
    aggregate_parser.add_argument("--repo-root", default=".")
    aggregate_parser.add_argument("--proof", action="append", required=True)
    aggregate_parser.add_argument("--artifact", action="append", default=[])
    aggregate_parser.add_argument("--output-directory", required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    if args.action == "run":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        proof = run_command(
            repo_root=args.repo_root,
            command=command,
            output_path=args.output,
            artifact_paths=args.artifact,
            commit_sha=args.commit_sha,
            label=args.label,
        )
        if proof["result"] == "PASS":
            return 0
        return int(proof["exit_code"] or 1)
    outputs = aggregate_proofs(
        repo_root=args.repo_root,
        proof_paths=args.proof,
        output_directory=args.output_directory,
        artifact_paths=args.artifact,
    )
    print(json.dumps({key: value.as_posix() for key, value in outputs.items()}))
    bundle = json.loads(outputs["proof_bundle"].read_text(encoding="utf-8"))
    return 0 if bundle.get("result") == "PASS" else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
