#!/usr/bin/env python3
from __future__ import annotations

import json
import argparse
import math
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

try:
    from ._repo import resolve_repo_root as resolve_vco_repo_root
except ImportError:  # pragma: no cover - exercised by direct script invocation.
    from _repo import resolve_repo_root as resolve_vco_repo_root


class PolicyError(ValueError):
    """Raised when the test baseline policy is malformed."""


CONFIG_ERROR_EXIT_CODE = 2
RUNTIME_ERROR_EXIT_CODE = 1
LEGACY_POLICY_KEYS = {"classification", "risk_keywords"}
LEGACY_LAYER_KEYS = {
    "source_layer_id",
    "include_file_patterns",
    "exclude_file_patterns",
    "include_risk_tags",
    "exclude_risk_tags",
}
VALID_SELECTION_SCOPES = {"contract_support", "default_regression", "host_boundary", "touched_surface_only"}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_policy(path: Path) -> dict[str, Any]:
    policy = load_json(path)
    legacy_keys = sorted(key for key in LEGACY_POLICY_KEYS if key in policy)
    if legacy_keys:
        raise PolicyError(f"Policy uses retired classification keys: {', '.join(legacy_keys)}")

    layers = policy.get("layers")
    if not isinstance(layers, list) or not layers:
        raise PolicyError("Policy must define at least one layer")

    seen: set[str] = set()
    for layer in layers:
        if not isinstance(layer, dict):
            raise PolicyError("Layer entries must be objects")
        layer_id = str(layer.get("id") or "")
        if not layer_id:
            raise PolicyError("Layer id is required")
        if layer_id in seen:
            raise PolicyError(f"Duplicate layer id: {layer_id}")
        seen.add(layer_id)
        legacy_layer_keys = sorted(key for key in LEGACY_LAYER_KEYS if key in layer)
        if legacy_layer_keys:
            raise PolicyError(f"Layer {layer_id} uses retired keys: {', '.join(legacy_layer_keys)}")
        pytest_args = layer.get("pytest_args")
        if not isinstance(pytest_args, list) or not all(isinstance(item, str) and item for item in pytest_args):
            raise PolicyError(f"Layer {layer_id} must define non-empty pytest_args")
        selection_scope = str(layer.get("selection_scope") or "")
        if selection_scope and selection_scope not in VALID_SELECTION_SCOPES:
            raise PolicyError(f"Layer {layer_id} has unsupported selection_scope: {selection_scope}")

    defaults = policy.get("defaults")
    if not isinstance(defaults, dict):
        raise PolicyError("Policy defaults must be an object")
    if bool(defaults.get("external_network_allowed")):
        raise PolicyError("Default external network must remain disabled")
    return policy


def parse_collect_output(stdout: str) -> list[str]:
    nodes: list[str] = []
    for raw_line in stdout.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("<") or line.startswith("="):
            continue
        if "::" in line:
            nodes.append(line.replace("\\", "/"))
    return nodes


def layer_by_id(policy: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(layer["id"]): layer for layer in policy["layers"]}


def build_pytest_command(pytest_args: list[str], *, collect_only: bool = False, quiet: str = "-q") -> list[str]:
    command = [sys.executable, "-m", "pytest", *pytest_args]
    if collect_only:
        command.append("--collect-only")
    if quiet:
        command.append(quiet)
    return command


PYTEST_OPTIONS_WITH_VALUE = {
    "-c",
    "-k",
    "-m",
    "--basetemp",
    "--confcutdir",
    "--deselect",
    "--ignore",
    "--ignore-glob",
    "--rootdir",
}


def normalize_pytest_target(arg: str, repo_root: Path) -> str:
    if not arg or arg.startswith("-"):
        return ""
    selector_path = arg.split("::", 1)[0]
    candidate = Path(selector_path)
    if candidate.is_absolute():
        try:
            return candidate.relative_to(repo_root).as_posix()
        except ValueError:
            return candidate.as_posix()
    return candidate.as_posix()


def pytest_arg_targets_repo_path(arg: str, repo_root: Path) -> bool:
    return bool(normalize_pytest_target(arg, repo_root))


def preserved_pytest_args_when_narrowing(pytest_args: list[str], repo_root: Path) -> list[str]:
    preserved: list[str] = []
    preserve_next = False
    for arg in pytest_args:
        if preserve_next:
            preserved.append(arg)
            preserve_next = False
            continue
        if arg.startswith("-"):
            preserved.append(arg)
            option_name = arg.split("=", 1)[0]
            if "=" not in arg and option_name in PYTEST_OPTIONS_WITH_VALUE:
                preserve_next = True
            continue
        if pytest_arg_targets_repo_path(arg, repo_root):
            continue
        preserved.append(arg)
    return preserved


def build_pytest_env(repo_root: Path, policy: dict[str, Any]) -> tuple[dict[str, str], str]:
    env = dict(os.environ)
    disable_env = str((policy.get("defaults") or {}).get("disable_network_env") or "VIBESKILLS_TEST_DISABLE_NETWORK")
    env[disable_env] = "1"
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["PYTHONPYCACHEPREFIX"] = str(repo_root / ".tmp" / "pycache")
    return env, disable_env


def build_collect_commands(policy: dict[str, Any]) -> list[dict[str, Any]]:
    quiet = str((policy.get("defaults") or {}).get("pytest_quiet_arg") or "-q")
    by_args: dict[tuple[str, ...], dict[str, Any]] = {}
    commands: list[dict[str, Any]] = []
    for layer in policy["layers"]:
        pytest_args = tuple(str(item) for item in layer["pytest_args"])
        if pytest_args not in by_args:
            item = {
                "source_layer_ids": [],
                "pytest_args": list(pytest_args),
                "command": build_pytest_command(list(pytest_args), collect_only=True, quiet=quiet),
                "timeout_seconds": int(
                    layer.get("timeout_seconds") or (policy.get("defaults") or {}).get("collect_timeout_seconds") or 180
                ),
            }
            by_args[pytest_args] = item
            commands.append(item)
        by_args[pytest_args]["source_layer_ids"].append(str(layer["id"]))
        by_args[pytest_args]["timeout_seconds"] = max(
            int(by_args[pytest_args]["timeout_seconds"]),
            int(layer.get("timeout_seconds") or (policy.get("defaults") or {}).get("collect_timeout_seconds") or 180),
        )
    return commands


def node_file(node_id: str) -> str:
    return node_id.split("::", 1)[0].replace("\\", "/")


def scan_file_risks(path: Path, policy: dict[str, Any]) -> list[str]:
    return []


def pytest_target_covers_file(pytest_arg: str, file_rel: str, repo_root: Path) -> bool:
    target = normalize_pytest_target(pytest_arg, repo_root)
    if not target:
        return False
    if target.endswith(".py"):
        return file_rel == target
    prefix = target.rstrip("/")
    return file_rel == prefix or file_rel.startswith(f"{prefix}/")


def layer_reason_for_file(layer: dict[str, Any], file_rel: str, repo_root: Path) -> str | None:
    for pytest_arg in layer.get("pytest_args") or []:
        if pytest_target_covers_file(str(pytest_arg), file_rel, repo_root):
            return f"pytest_target:{normalize_pytest_target(str(pytest_arg), repo_root)}"
    return None


def classify_node(node_id: str, repo_root: Path, policy: dict[str, Any]) -> dict[str, Any]:
    file_rel = node_file(node_id)
    for layer in policy["layers"]:
        reason = layer_reason_for_file(layer, file_rel, repo_root)
        if reason is None:
            continue
        return {
            "node_id": node_id,
            "file": file_rel,
            "layer_id": str(layer["id"]),
            "risk_tags": [],
            "reasons": [reason],
        }
    raise PolicyError(f"No policy layer targets {file_rel}")


def select_layer_files(
    collected_nodes: list[str],
    repo_root: Path,
    policy: dict[str, Any],
    layer_id: str,
) -> list[str]:
    layers = layer_by_id(policy)
    if layer_id not in layers:
        raise PolicyError(f"Unknown layer id: {layer_id}")

    files: set[str] = set()
    for node in collected_nodes:
        item = classify_node(node, repo_root, policy)
        if str(item["layer_id"]) == layer_id:
            files.add(str(item["file"]))
    return sorted(files)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def summarize_classified(classified: list[dict[str, Any]], policy: dict[str, Any]) -> tuple[dict[str, Any], dict[str, int]]:
    layers: dict[str, Any] = {
        str(layer["id"]): {
            "description": str(layer.get("description") or ""),
            "selection_scope": str(layer.get("selection_scope") or ""),
            "node_count": 0,
            "files": [],
            "risk_tags": [],
        }
        for layer in policy["layers"]
    }
    files_by_layer: dict[str, set[str]] = {layer_id: set() for layer_id in layers}

    for item in classified:
        layer_id = str(item["layer_id"])
        layers[layer_id]["node_count"] += 1
        files_by_layer[layer_id].add(str(item["file"]))

    for layer_id in layers:
        layers[layer_id]["files"] = sorted(files_by_layer[layer_id])
    return layers, {}


def build_artifact(
    *,
    repo_root: Path,
    policy_path: Path,
    policy: dict[str, Any],
    collected_nodes: list[str],
    collection_results: list[dict[str, Any]],
    run_result: dict[str, Any] | None,
) -> dict[str, Any]:
    classified = [classify_node(node, repo_root, policy) for node in collected_nodes]
    layers, risks = summarize_classified(classified, policy)
    return {
        "generated_at": utc_now(),
        "repo_root": str(repo_root),
        "policy_path": str(policy_path),
        "summary": {
            "total_nodes": len(collected_nodes),
            "layer_count": len(layers),
            "risk_tag_count": len(risks),
            "external_network_allowed": bool((policy.get("defaults") or {}).get("external_network_allowed")),
        },
        "collection_results": collection_results,
        "layers": layers,
        "risks": risks,
        "classified": classified,
        "run_result": run_result,
    }


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8", newline="\n")


def render_markdown(artifact: dict[str, Any]) -> str:
    lines = [
        "# Test Baseline Audit",
        "",
        f"- Generated At: `{artifact['generated_at']}`",
        f"- Total Nodes: `{artifact['summary']['total_nodes']}`",
        f"- External Network Allowed: `{artifact['summary']['external_network_allowed']}`",
        "",
        "## Layers",
        "",
    ]
    for layer_id, layer in artifact["layers"].items():
        lines.append(
            f"- `{layer_id}`: scope=`{layer['selection_scope'] or 'none'}` nodes=`{layer['node_count']}` files=`{len(layer['files'])}` risks=`{', '.join(layer['risk_tags']) or 'none'}`"
        )
    lines += ["", "## Risks", ""]
    if artifact["risks"]:
        for tag, count in artifact["risks"].items():
            lines.append(f"- `{tag}`: `{count}`")
    else:
        lines.append("- `none`: `0`")
    if artifact.get("run_result"):
        run_result = artifact["run_result"]
        lines += [
            "",
            "## Executed Layer",
            "",
            f"- Layer: `{run_result['layer_id']}`",
            f"- Exit Code: `{run_result['exit_code']}`",
            f"- Command: `{' '.join(run_result['command'])}`",
        ]
    return "\n".join(lines) + "\n"


def _artifact_names_from_policy(policy: dict[str, Any] | None = None) -> dict[str, str]:
    configured = (policy or {}).get("artifact_names") or {}
    names = {
        "json": "test-baseline-audit.json",
        "markdown": "test-baseline-audit.md",
    }
    if isinstance(configured, dict):
        for key in names:
            value = configured.get(key)
            if isinstance(value, str) and value.strip():
                names[key] = value.strip()
    return names


def write_artifacts(
    repo_root: Path,
    artifact: dict[str, Any],
    output_directory: str | None = None,
    *,
    policy: dict[str, Any] | None = None,
) -> dict[str, str]:
    output_root = Path(output_directory) if output_directory else repo_root / "outputs" / "verify"
    names = _artifact_names_from_policy(policy)
    json_path = output_root / names["json"]
    md_path = output_root / names["markdown"]
    write_text(json_path, json.dumps(artifact, ensure_ascii=False, indent=2) + "\n")
    write_text(md_path, render_markdown(artifact))
    return {"json": str(json_path), "markdown": str(md_path)}


def resolve_repo_root(start: Path) -> Path:
    return resolve_vco_repo_root(start)


def run_collect_commands(
    repo_root: Path, policy: dict[str, Any], runner=subprocess.run
) -> tuple[list[str], list[dict[str, Any]]]:
    nodes: list[str] = []
    results: list[dict[str, Any]] = []
    env, _disable_env = build_pytest_env(repo_root, policy)
    for item in build_collect_commands(policy):
        try:
            completed = runner(
                item["command"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=item["timeout_seconds"],
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = getattr(exc, "stdout", None)
            if stdout is None:
                stdout = getattr(exc, "output", None)
            stderr = getattr(exc, "stderr", None)
            detail_parts = [
                f"pytest collection timed out for {item['pytest_args']}",
                f"after {item['timeout_seconds']}s",
                f"layers={item['source_layer_ids']}",
            ]
            if stdout:
                detail_parts.append(f"stdout={stdout}")
            if stderr:
                detail_parts.append(f"stderr={stderr}")
            raise RuntimeError("; ".join(detail_parts)) from exc
        parsed_nodes = parse_collect_output(completed.stdout)
        nodes.extend(parsed_nodes)
        results.append(
            {
                "source_layer_ids": item["source_layer_ids"],
                "command": item["command"],
                "exit_code": int(completed.returncode),
                "node_count": len(parsed_nodes),
                "stderr": completed.stderr,
            }
        )
        if int(completed.returncode) != 0:
            raise RuntimeError(f"pytest collection failed for {item['pytest_args']} with exit code {completed.returncode}")
    return sorted(set(nodes)), results


def build_run_layer_command(
    policy: dict[str, Any],
    layer_id: str,
    *,
    repo_root: Path | None = None,
    collected_nodes: list[str] | None = None,
) -> list[str]:
    layers = layer_by_id(policy)
    if layer_id not in layers:
        raise PolicyError(f"Unknown layer id: {layer_id}")
    quiet = str((policy.get("defaults") or {}).get("pytest_quiet_arg") or "-q")

    pytest_args = list(layers[layer_id]["pytest_args"])
    if collected_nodes is not None:
        if repo_root is None:
            raise PolicyError("repo_root is required when collected_nodes are provided")
        selected_files = select_layer_files(collected_nodes, repo_root, policy, layer_id)
        if not selected_files:
            raise PolicyError(f"No collected tests matched layer id: {layer_id}")
        pytest_args = [*preserved_pytest_args_when_narrowing(pytest_args, repo_root), *selected_files]

    return build_pytest_command(pytest_args, quiet=quiet)


def run_layer(
    repo_root: Path,
    policy: dict[str, Any],
    layer_id: str,
    *,
    collected_nodes: list[str] | None = None,
    runner=subprocess.run,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    layers = layer_by_id(policy)
    if layer_id not in layers:
        raise PolicyError(f"Unknown layer id: {layer_id}")

    selected_files: list[str] = []
    if collected_nodes is not None:
        selected_files = select_layer_files(collected_nodes, repo_root, policy, layer_id)
    layer = layers[layer_id]
    if selected_files and str(layer.get("run_strategy") or "") == "file_serial":
        return run_layer_file_serial(repo_root, policy, layer_id, selected_files, runner=runner, progress=progress)
    command = build_run_layer_command(policy, layer_id, repo_root=repo_root, collected_nodes=collected_nodes)
    env, disable_env = build_pytest_env(repo_root, policy)
    timeout_seconds = int(layer.get("timeout_seconds") or 300)
    try:
        completed = runner(
            command,
            cwd=repo_root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "layer_id": layer_id,
            "command": command,
            "exit_code": 124,
            "stdout": timeout_stream_to_text(getattr(exc, "stdout", None) or getattr(exc, "output", None)),
            "stderr": timeout_stream_to_text(getattr(exc, "stderr", None)),
            "disable_network_env": disable_env,
            "selected_files": selected_files,
            "selected_file_count": len(selected_files),
            "timeout_seconds": timeout_seconds,
        }
    return {
        "layer_id": layer_id,
        "command": command,
        "exit_code": int(completed.returncode),
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "disable_network_env": disable_env,
        "selected_files": selected_files,
        "selected_file_count": len(selected_files),
    }


def timeout_stream_to_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    return str(value)


def run_layer_file_serial(
    repo_root: Path,
    policy: dict[str, Any],
    layer_id: str,
    selected_files: list[str],
    *,
    runner=subprocess.run,
    progress: Callable[[str], None] | None = None,
) -> dict[str, Any]:
    quiet = str((policy.get("defaults") or {}).get("pytest_quiet_arg") or "-q")
    env, disable_env = build_pytest_env(repo_root, policy)
    layer = layer_by_id(policy)[layer_id]
    layer_timeout = int(layer.get("timeout_seconds") or 300)
    per_file_timeout = int(layer.get("per_file_timeout_seconds") or layer.get("timeout_seconds") or 300)
    file_results: list[dict[str, Any]] = []
    stdout_chunks: list[str] = [f"[INFO] run_strategy=file_serial selected_files={len(selected_files)}"]
    stderr_chunks: list[str] = []
    exit_code = 0
    layer_started = time.monotonic()

    for file_rel in selected_files:
        layer_elapsed = time.monotonic() - layer_started
        if layer_elapsed >= layer_timeout:
            exit_code = 124
            progress_line = (
                f"[FILE] {file_rel} exit_code=124 status=layer_timeout_before_file "
                f"seconds={layer_elapsed:.1f} timeout_seconds={layer_timeout}"
            )
            stdout_chunks.append(progress_line)
            if progress:
                progress(progress_line)
            break

        file_timeout = min(per_file_timeout, max(1, math.ceil(layer_timeout - layer_elapsed)))
        command = build_pytest_command([file_rel], quiet=quiet)
        started = time.monotonic()
        if progress:
            progress(f"[INFO] start_file {file_rel}")
        try:
            completed = runner(
                command,
                cwd=repo_root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=file_timeout,
                env=env,
            )
            elapsed = time.monotonic() - started
            file_exit_code = int(completed.returncode)
            result = {
                "file": file_rel,
                "command": command,
                "exit_code": file_exit_code,
                "status": "passed" if file_exit_code == 0 else "failed",
                "seconds": round(elapsed, 3),
                "stdout": completed.stdout,
                "stderr": completed.stderr,
            }
            file_results.append(result)
            progress_line = f"[FILE] {file_rel} exit_code={file_exit_code} seconds={elapsed:.1f}"
            stdout_chunks.append(progress_line)
            if progress:
                progress(progress_line)
            if completed.stdout:
                stdout_chunks.append(completed.stdout)
            if completed.stderr:
                stderr_chunks.append(completed.stderr)
            if file_exit_code != 0:
                exit_code = file_exit_code
                break
        except subprocess.TimeoutExpired as exc:
            elapsed = time.monotonic() - started
            stdout_text = timeout_stream_to_text(getattr(exc, "stdout", None) or getattr(exc, "output", None))
            stderr_text = timeout_stream_to_text(getattr(exc, "stderr", None))
            result = {
                "file": file_rel,
                "command": command,
                "exit_code": 124,
                "status": "timeout",
                "seconds": round(elapsed, 3),
                "timeout_seconds": file_timeout,
                "stdout": stdout_text,
                "stderr": stderr_text,
            }
            file_results.append(result)
            progress_line = f"[FILE] {file_rel} exit_code=124 status=timeout seconds={elapsed:.1f}"
            stdout_chunks.append(progress_line)
            if progress:
                progress(progress_line)
            if stdout_text:
                stdout_chunks.append(stdout_text)
            if stderr_text:
                stderr_chunks.append(stderr_text)
            exit_code = 124
            break

    return {
        "layer_id": layer_id,
        "command": [sys.executable, "-m", "pytest", "<file_serial>", quiet],
        "exit_code": exit_code,
        "stdout": "\n".join(chunk for chunk in stdout_chunks if chunk),
        "stderr": "\n".join(chunk for chunk in stderr_chunks if chunk),
        "disable_network_env": disable_env,
        "selected_files": selected_files,
        "selected_file_count": len(selected_files),
        "run_strategy": "file_serial",
        "timeout_seconds": layer_timeout,
        "per_file_timeout_seconds": per_file_timeout,
        "file_results": file_results,
    }


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Collect, classify, and optionally run Vibe-Skills test baseline layers.")
    parser.add_argument("--policy", default="config/test-baseline-policy.json")
    parser.add_argument("--collect-only", action="store_true", help="Collect and classify tests without executing a layer.")
    parser.add_argument(
        "--run-layer",
        help="Policy layer id to execute. Validated after the policy file is loaded.",
    )
    parser.add_argument("--write-artifacts", action="store_true")
    parser.add_argument("--output-directory")
    return parser.parse_args(argv)


def _print_cli_error(message: str) -> None:
    print(f"[ERROR] {message}", file=sys.stderr)


def main(argv: list[str] | None = None, runner=subprocess.run) -> int:
    try:
        args = parse_args(argv or sys.argv[1:])
        repo_root = resolve_repo_root(Path(__file__))
        policy_path = (repo_root / args.policy).resolve()
        if not policy_path.exists():
            raise PolicyError(f"Policy file not found: {policy_path}")
        policy = load_policy(policy_path)
        collected_nodes, collection_results = run_collect_commands(repo_root, policy, runner=runner)
        run_result = None
        if args.run_layer and not args.collect_only:
            def print_progress(message: str) -> None:
                print(message, flush=True)

            run_result = run_layer(
                repo_root,
                policy,
                args.run_layer,
                collected_nodes=collected_nodes,
                runner=runner,
                progress=print_progress,
            )
        artifact = build_artifact(
            repo_root=repo_root,
            policy_path=policy_path,
            policy=policy,
            collected_nodes=collected_nodes,
            collection_results=collection_results,
            run_result=run_result,
        )
        if args.write_artifacts:
            write_artifacts(repo_root, artifact, args.output_directory, policy=policy)
        print(
            f"[INFO] total_nodes={artifact['summary']['total_nodes']} "
            f"layers={artifact['summary']['layer_count']} "
            f"risks={artifact['summary']['risk_tag_count']}"
        )
        if run_result is not None:
            print(f"[INFO] run_layer={run_result['layer_id']} exit_code={run_result['exit_code']}")
            return int(run_result["exit_code"])
        return 0
    except (PolicyError, json.JSONDecodeError) as exc:
        _print_cli_error(str(exc))
        return CONFIG_ERROR_EXIT_CODE
    except (RuntimeError, OSError) as exc:
        _print_cli_error(str(exc))
        return RUNTIME_ERROR_EXIT_CODE


if __name__ == "__main__":
    raise SystemExit(main())
