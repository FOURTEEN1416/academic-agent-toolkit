"""Self-locating launcher for the PaperSpine5 runtime, used by the DSH Bundle.

A DSH Bundle is linked into a profile from wherever it happens to live, so the
bundle must never record the machine that built it.  Cordis needs one absolute
path to start a stdio server, so ``configure_dsh.py`` fills the single
``__PAPERSPINE5_PACKAGE_ROOT__`` token at install time; every other path is
resolved here, from this file's own location.

Layouts this launcher accepts, in priority order:

  A. standard suite embedded at ``<bundle>/core``
       ``core/06_插件化/runtime/paperspine5_runtime.py`` and
       ``core/03_联合开发/src/paperspine_figure_integration/product_kernel.py``;
       the runtime project root is exactly ``<bundle>/core``.
  B. legacy embedded core
       ``core/runtime/paperspine5_runtime.py``; the project root is the bundle.
  C. repository checkout
       ``<checkout>/06_插件化/runtime/paperspine5_runtime.py``.

A bundled runtime always wins: ``PAPERSPINE5_PROJECT_ROOT`` is consulted only
when the bundle embeds no runtime, and once a runtime is selected this process
forces ``PAPERSPINE5_PROJECT_ROOT`` to the selected root so a stale inherited
value cannot leak into the runtime.
"""

from __future__ import annotations

import json
import os
import runpy
import sys
from pathlib import Path

# Installed suite roots are immutable, hash-verified release objects. Keep
# imports from dropping __pycache__ entries inside that object.
sys.dont_write_bytecode = True
os.environ["PYTHONDONTWRITEBYTECODE"] = "1"

# (label, runtime, kernel, project root relative to the candidate root).
LAYOUTS = (
    (
        "embedded standard suite",
        Path("core") / "06_插件化" / "runtime" / "paperspine5_runtime.py",
        Path("core") / "03_联合开发" / "src" / "paperspine_figure_integration" / "product_kernel.py",
        Path("core"),
    ),
    (
        "embedded core runtime",
        Path("core") / "runtime" / "paperspine5_runtime.py",
        Path("core") / "03_联合开发" / "src" / "paperspine_figure_integration" / "product_kernel.py",
        Path("."),
    ),
    (
        "repository checkout",
        Path("06_插件化") / "runtime" / "paperspine5_runtime.py",
        Path("03_联合开发") / "src" / "paperspine_figure_integration" / "product_kernel.py",
        Path("."),
    ),
)


def bundle_root() -> Path:
    return Path(__file__).resolve().parents[1]


def resolve(root: Path):
    """Return (runtime, project_root) if this root holds a complete runtime."""
    for _label, runtime_rel, kernel_rel, project_rel in LAYOUTS:
        runtime = root / runtime_rel
        if runtime.is_file() and (root / kernel_rel).is_file():
            return runtime, (root / project_rel).resolve()
    return None


def incomplete_bundle(root: Path) -> str | None:
    """Describe a bundled layout that is present but missing its kernel."""
    for label, runtime_rel, kernel_rel, _project_rel in LAYOUTS[:2]:
        runtime = root / runtime_rel
        if runtime.is_file() and not (root / kernel_rel).is_file():
            return f"{label} is incomplete: {runtime} exists but {root / kernel_rel} is missing"
    return None


def candidate_roots():
    root = bundle_root()
    # The bundle itself, then the checkout it may sit inside. Bounded on
    # purpose: walking every ancestor could bind an unrelated tree.
    yield root
    for parent in list(root.parents)[:4]:
        yield parent
    configured = os.environ.get("PAPERSPINE5_PROJECT_ROOT")
    if not configured:
        config = root / "config" / "local-project.json"
        if config.is_file():
            configured = json.loads(config.read_text(encoding="utf-8-sig")).get("project_root")
    if configured:
        yield Path(configured)


def project_root():
    tried: list[Path] = []

    root = bundle_root()
    found = resolve(root)
    if found:
        return found
    # A packaged bundle that carries a partial core/ is corrupt. Searching the
    # ancestors here could silently bind an unrelated checkout, so refuse.
    problem = incomplete_bundle(root)
    if (root / "core/suite-manifest.json").exists():
        problem = problem or "manifest is present but the runtime or kernel is missing"
    if problem:
        raise SystemExit(
            "PaperSpine5 bundled runtime is broken; refusing to bind another tree.\n"
            f"  bundle: {root}\n"
            f"  reason: {problem}\n"
            "Re-install the bundle, or remove the partial core/ directory."
        )
    tried.append(root.resolve())

    for parent in list(root.parents)[:4]:
        candidate = parent.resolve()
        if candidate in tried:
            continue
        tried.append(candidate)
        found = resolve(candidate)
        if found:
            return found

    configured = os.environ.get("PAPERSPINE5_PROJECT_ROOT")
    if not configured:
        config = root / "config" / "local-project.json"
        if config.is_file():
            try:
                configured = json.loads(config.read_text(encoding="utf-8-sig")).get("project_root")
            except (OSError, json.JSONDecodeError, AttributeError):
                configured = None
    if configured:
        try:
            candidate = Path(configured).expanduser().resolve()
        except OSError:
            candidate = None
        if candidate is not None:
            if candidate not in tried:
                tried.append(candidate)
            found = resolve(candidate)
            if found:
                return found

    listing = "\n".join(f"  - {path}" for path in tried)
    raise SystemExit(
        "PaperSpine5 runtime not found for this DSH Bundle.\n"
        "Looked in:\n"
        f"{listing}\n"
        "Re-run the bundle installer (install.ps1 / install.sh), or set\n"
        "PAPERSPINE5_PROJECT_ROOT to a checkout that contains\n"
        "06_插件化/runtime/paperspine5_runtime.py."
    )


def main() -> None:
    runtime, root = project_root()
    # Force, not setdefault: a stale inherited value must not override the root
    # this launcher actually selected.
    os.environ["PAPERSPINE5_PROJECT_ROOT"] = str(root)
    runtime_directory = str(runtime.parent)
    # runpy does not give the executed file normal script import semantics, so
    # keep sibling runtime modules importable when they load lazily.
    if runtime_directory not in sys.path:
        sys.path.insert(0, runtime_directory)
    sys.argv[0] = str(runtime)
    runpy.run_path(str(runtime), run_name="__main__")


if __name__ == "__main__":
    main()
