#!/usr/bin/env python3
"""Bind this DSH Bundle to the directory it was installed into.

Cordis needs one absolute path to start a stdio server, so the bundle carries
the token ``__PAPERSPINE5_PACKAGE_ROOT__`` instead of a baked-in path.  This
script is the only place that token is resolved, and it is idempotent: running
it again after the bundle has been moved re-points every path this bundle owns
instead of refusing or leaving a stale value behind.

Layouts, in priority order:

* standard suite embedded at ``<bundle>/core`` -- the suite root holds
  ``06_插件化/runtime/paperspine5_runtime.py`` and
  ``03_联合开发/src/paperspine_figure_integration/product_kernel.py``.  The
  runtime project root is exactly ``<bundle>/core`` and the interpreter is the
  bundled one named by ``core/suite-manifest.json`` (or, when the manifest does
  not name one, by ``core/runtime_vendor/requirements.lock.json``).  A checkout
  is never consulted for a packaged suite.
* legacy embedded core -- ``<bundle>/core/runtime/paperspine5_runtime.py``; the
  project root is the bundle itself and the interpreter falls back to ``python``.
* development checkout -- ``<checkout>/06_插件化/runtime/paperspine5_runtime.py``;
  the project root is the checkout and the interpreter falls back to ``python``.

Usage:  python configure_dsh.py [--package-root <dir>] [--project-root <dir>]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path, PurePosixPath
from typing import NoReturn

TOKEN = "__PAPERSPINE5_PACKAGE_ROOT__"
PROJECT_TOKEN = "__PAPERSPINE5_PROJECT_ROOT__"
LAUNCHER_REL = "scripts/paperspine5_mcp.py"
SUITE_DIR = "core"
PYTHON_FALLBACK = "python"

# (runtime, kernel) for each supported layout, relative to its own root.
RUNTIME_REL = Path("06_插件化") / "runtime" / "paperspine5_runtime.py"
KERNEL_REL = (
    Path("03_联合开发") / "src" / "paperspine_figure_integration" / "product_kernel.py"
)
SUITE_RUNTIME_REL = Path(SUITE_DIR) / RUNTIME_REL
SUITE_KERNEL_REL = Path(SUITE_DIR) / KERNEL_REL
LEGACY_RUNTIME_REL = Path(SUITE_DIR) / "runtime" / "paperspine5_runtime.py"
LEGACY_KERNEL_REL = Path(SUITE_DIR) / KERNEL_REL


def fail(message: str) -> NoReturn:
    """Abort with a readable reason and a non-zero exit status."""
    raise SystemExit(message)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Bind a DSH Bundle to its install root.")
    parser.add_argument("--package-root", default=str(Path(__file__).resolve().parent))
    parser.add_argument(
        "--project-root",
        default="",
        help="Checkout holding the runtime, for bundles that do not embed core/. "
        "Ignored when the bundle embeds a standard suite or a legacy core/.",
    )
    return parser.parse_args()


def detect_layout(root: Path):
    """Return ``(kind, project_root)`` when ``root`` holds a complete runtime."""
    if (root / SUITE_RUNTIME_REL).is_file() and (root / SUITE_KERNEL_REL).is_file():
        return "suite", root / SUITE_DIR
    if (root / LEGACY_RUNTIME_REL).is_file() and (root / LEGACY_KERNEL_REL).is_file():
        return "legacy", root
    if (root / RUNTIME_REL).is_file() and (root / KERNEL_REL).is_file():
        return "repository", root
    return None


def locate_checkout(start: Path):
    """Find a checkout containing the runtime, from ``start`` upwards."""
    for candidate in [start, *list(start.parents)[:5]]:
        found = detect_layout(candidate)
        if found is not None:
            return found
    return None


def read_json_object(path: Path, label: str) -> dict:
    try:
        text = path.read_text(encoding="utf-8-sig")
    except OSError as exc:
        fail(f"{label} is unreadable: {path} ({exc})")
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        fail(f"{label} is not valid JSON: {path} ({exc})")
    if not isinstance(value, dict):
        fail(f"{label} must contain a JSON object: {path}")
    return value


def _declared_executable(value, label: str):
    """Return a declared interpreter string, ``None`` when it is absent."""
    if value is None:
        return None
    if not isinstance(value, str) or not value.strip():
        fail(f"{label} must be a non-empty relative path string, got {value!r}")
    return value


def suite_python_executable(suite: Path) -> str:
    """Choose the bundled interpreter named by the suite manifest or its lock."""
    manifest_path = suite / "suite-manifest.json"
    lock_path = suite / "runtime_vendor" / "requirements.lock.json"

    manifest_value = None
    if manifest_path.is_file():
        manifest = read_json_object(manifest_path, "suite manifest")
        runtime = manifest.get("runtime")
        if runtime is not None:
            if not isinstance(runtime, dict):
                fail(f"suite manifest runtime metadata must be an object: {manifest_path}")
            manifest_value = _declared_executable(
                runtime.get("python_executable"),
                "suite manifest runtime.python_executable",
            )

    lock_value = None
    if lock_path.is_file():
        lock = read_json_object(lock_path, "suite runtime lock")
        lock_value = _declared_executable(
            lock.get("python_executable"), "suite runtime lock python_executable"
        )

    if manifest_value is None and lock_value is None:
        fail(
            "the embedded suite does not declare a bundled interpreter.\n"
            f"  suite:  {suite}\n"
            f"  looked: {manifest_path}\n"
            f"          {lock_path}"
        )
    if manifest_value is not None and lock_value is not None and manifest_value != lock_value:
        fail(
            "suite manifest and runtime lock disagree about python_executable.\n"
            f"  manifest: {manifest_value!r}\n"
            f"  lock:     {lock_value!r}"
        )
    return manifest_value if manifest_value is not None else lock_value


def resolve_suite_executable(suite: Path, raw: str) -> Path:
    """Require a relative, contained, existing interpreter inside the suite."""
    if not isinstance(raw, str) or not raw.strip():
        fail(f"suite runtime python_executable must be a non-empty string, got {raw!r}")
    candidate = raw.replace("\\", "/")
    if re.match(r"^[A-Za-z]:", candidate) or candidate.startswith("//"):
        fail(f"suite runtime python_executable must be relative, not absolute: {raw!r}")
    pure = PurePosixPath(candidate)
    if pure.is_absolute() or not pure.parts or ".." in pure.parts:
        fail(f"suite runtime python_executable must stay inside the suite: {raw!r}")
    if pure.as_posix() != candidate:
        fail(f"suite runtime python_executable is not a canonical relative path: {raw!r}")
    target = (suite / Path(*pure.parts)).resolve()
    try:
        target.relative_to(suite.resolve())
    except ValueError:
        fail(f"suite runtime python_executable escapes the suite root: {raw!r}")
    if not target.is_file():
        fail(
            "suite runtime python_executable does not exist.\n"
            f"  declared: {raw!r}\n"
            f"  resolved: {target}"
        )
    return target


def quote_yaml(value: str) -> str:
    """Single-quote a YAML scalar, doubling apostrophes as YAML requires."""
    return "'" + value.replace("'", "''") + "'"


def unquote_yaml(value: str) -> str:
    """Undo :func:`quote_yaml` (and a simple double-quoted scalar)."""
    value = value.strip()
    if len(value) >= 2 and value[0] == "'" and value[-1] == "'":
        return value[1:-1].replace("''", "'")
    if len(value) >= 2 and value[0] == '"' and value[-1] == '"':
        return value[1:-1].replace('\\"', '"').replace("\\\\", "\\")
    return value


def render_scalar(value: str) -> str:
    """Keep the bare ``python`` fallback, quote every real path."""
    if value == PYTHON_FALLBACK:
        return PYTHON_FALLBACK
    return quote_yaml(value)


_ID_LINE = re.compile(r"^(?P<indent>\s*)-\s*id:\s*mcp-paperspine5\s*$")
_LIST_ITEM = re.compile(r"^(?P<indent>\s*)-\s")
_LAUNCHER_ITEM = re.compile(r"^(?P<prefix>\s*-\s+)(?P<value>.*?)(?P<trail>\s*)$")
_KEY = re.compile(
    r"^(?P<indent>\s*)(?P<key>[A-Za-z_][A-Za-z0-9_-]*):(?P<gap>\s*)"
    r"(?P<value>.*?)(?P<trail>\s*)$"
)


def _mcp_region(lines: list[str]) -> tuple[int, int]:
    """Return the half-open line range of the mcp-paperspine5 server entry."""
    start = None
    indent = 0
    for index, line in enumerate(lines):
        match = _ID_LINE.match(line)
        if match:
            start = index
            indent = len(match.group("indent"))
            break
    if start is None:
        fail("cordis.patch.yml does not declare the mcp-paperspine5 server")
    end = len(lines)
    for index in range(start + 1, len(lines)):
        item = _LIST_ITEM.match(lines[index])
        if item and len(item.group("indent")) <= indent:
            end = index
            break
    return start, end


def configure_patch(text: str, *, bundle: str, project: str, command: str) -> str:
    """Re-point the four bindings this bundle owns; leave everything else."""
    lines = text.splitlines()
    start, end = _mcp_region(lines)
    launcher_path = f"{bundle}/{LAUNCHER_REL}"
    seen = {"command": False, "cwd": False, "project": False, "launcher": False}

    for index in range(start + 1, end):
        line = lines[index]

        item = _LAUNCHER_ITEM.match(line)
        if item and not seen["launcher"]:
            if unquote_yaml(item.group("value")).replace("\\", "/").endswith(LAUNCHER_REL):
                lines[index] = (
                    item.group("prefix") + quote_yaml(launcher_path) + item.group("trail")
                )
                seen["launcher"] = True
                continue

        key = _KEY.match(line)
        if key is None:
            continue
        name = key.group("key")
        prefix = key.group("indent") + name + ":" + key.group("gap")
        if name == "command" and not seen["command"]:
            lines[index] = prefix + render_scalar(command) + key.group("trail")
            seen["command"] = True
        elif name == "cwd" and not seen["cwd"]:
            lines[index] = prefix + quote_yaml(bundle) + key.group("trail")
            seen["cwd"] = True
        elif name == "PAPERSPINE5_PROJECT_ROOT" and not seen["project"]:
            lines[index] = prefix + quote_yaml(project) + key.group("trail")
            seen["project"] = True

    missing = [name for name, found in seen.items() if not found]
    if missing:
        fail(
            "cordis.patch.yml is missing bindings that configure_dsh.py must own: "
            + ", ".join(sorted(missing))
            + ".\n"
            "Restore the mcp-paperspine5 server block from the released bundle."
        )

    rendered = "\n".join(lines)
    if text.endswith("\n"):
        rendered += "\n"
    # Defensive: a template variant may carry the tokens outside the four
    # fields above; no token may survive configuration.
    rendered = rendered.replace(TOKEN, bundle).replace(PROJECT_TOKEN, project)

    if quote_yaml(bundle) not in rendered:
        fail(
            "could not bind the DSH patch to this package root.\n"
            f"  expected root: {bundle}\n"
            "Re-extract the bundle, or restore the "
            f"{TOKEN} token in cordis.patch.yml."
        )
    if quote_yaml(project) not in rendered:
        fail(
            "could not bind the DSH patch to this project root.\n"
            f"  expected root: {project}\n"
            f"Restore the {PROJECT_TOKEN} token in cordis.patch.yml."
        )
    if TOKEN in rendered or PROJECT_TOKEN in rendered:
        fail("cordis.patch.yml still carries an unresolved PaperSpine5 token")
    return rendered


def configure_skill_provider(text: str, project: Path, kind: str) -> str:
    # A single isolated provider exposes the canonical Skill without copying it.
    skill_root = project / ("standalone" if kind == "suite" else "01_PaperSpine4/src")
    if kind == "legacy":
        skill_root = project / "core/01_PaperSpine4/src"
    lines = text.splitlines()
    provider = False
    for index, line in enumerate(lines):
        if line.strip() == "- id: paperspine5-skills":
            provider = True
        elif provider and line.strip().startswith("bundledSkillDir:"):
            prefix = line[:len(line) - len(line.lstrip())] + "bundledSkillDir: "
            lines[index] = prefix + quote_yaml(skill_root.as_posix())
            return "\n".join(lines) + "\n"
    # Historical MCP-only fixtures remain configurable; current builds include it.
    return text


def configure_adapter(adapter: dict, *, bundle: str, project: str, command: str) -> dict:
    """Replace every absolute value the adapter records, including args."""
    launcher_path = f"{bundle}/{LAUNCHER_REL}"
    args = adapter.get("args")
    if not isinstance(args, list):
        args = []
    rebuilt: list = []
    replaced = False
    for item in args:
        if isinstance(item, str) and (
            TOKEN in item or item.replace("\\", "/").endswith(LAUNCHER_REL)
        ):
            rebuilt.append(launcher_path)
            replaced = True
        else:
            rebuilt.append(item)
    if not replaced:
        rebuilt = ["-B", launcher_path, "mcp"]

    adapter["command"] = command
    adapter["args"] = rebuilt
    adapter["package_root"] = bundle
    adapter["project_root"] = project
    if "cwd" in adapter:
        adapter["cwd"] = bundle
    return adapter


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parse_args()
    bundle = Path(args.package_root).expanduser().resolve()

    launcher = bundle / LAUNCHER_REL
    if not launcher.is_file():
        fail(f"DSH launcher is missing: {launcher}")

    layout = detect_layout(bundle)
    command = PYTHON_FALLBACK
    if (bundle / "core/suite-manifest.json").exists() and (not layout or layout[0] != "suite"):
        fail("Embedded suite is incomplete; re-extract the complete DSH package.")
    if layout is not None and layout[0] == "suite":
        kind = "suite"
        suite = bundle / SUITE_DIR
        declared = suite_python_executable(suite)
        interpreter = resolve_suite_executable(suite, declared)
        project = (bundle / SUITE_DIR).resolve()
        command = interpreter.as_posix()
    elif layout is not None:
        kind, project = layout
    else:
        if args.project_root:
            explicit = Path(args.project_root).expanduser().resolve()
            found = locate_checkout(explicit)
            if found is None:
                fail(f"--project-root does not hold a PaperSpine5 runtime: {explicit}")
            kind, project = found
        else:
            found = locate_checkout(bundle)
            if found is None:
                fail(
                    "This bundle does not embed core/ and no PaperSpine5 checkout was found.\n"
                    f"  bundle: {bundle}\n"
                    "Pass --project-root <checkout> (the installer does this for you), or "
                    "install a packaged bundle that ships its own core/."
                )
            kind, project = found

    bundle_posix = bundle.as_posix()
    project_posix = Path(project).as_posix()

    patch_path = bundle / "cordis.patch.yml"
    if not patch_path.is_file():
        fail(f"DSH patch is missing: {patch_path}")
    adapter_path = bundle / "adapter.json"
    if not adapter_path.is_file():
        fail(f"DSH adapter is missing: {adapter_path}")

    # Compute both rewrites before writing either one, so a malformed input
    # leaves the bundle exactly as it was found.
    patch_text = patch_path.read_text(encoding="utf-8")
    adapter = read_json_object(adapter_path, "DSH adapter")
    patch_text = configure_patch(
        patch_text, bundle=bundle_posix, project=project_posix, command=command
    )
    patch_text = configure_skill_provider(patch_text, Path(project), kind)
    adapter = configure_adapter(
        adapter, bundle=bundle_posix, project=project_posix, command=command
    )

    patch_path.write_text(patch_text, encoding="utf-8", newline="\n")
    adapter_path.write_text(
        json.dumps(adapter, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    print(
        json.dumps(
            {
                "status": "CONFIGURED",
                "layout": kind,
                "package_root": bundle_posix,
                "project_root": project_posix,
                "command": command,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
