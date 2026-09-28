"""Profile-driven one-click domain deployment.

A *domain profile* is a single YAML file in ``researchclaw/domains/profiles/``
(or a user override directory) that describes everything the pipeline needs
to specialize for one research domain — prompt guidance, code-generation
hints, detection keywords, and now **deployment defaults** such as
``experiment.mode``, ``export.target_conference``, Docker image, pip
packages, etc.

This module turns a profile id into:

* a filesystem path (``resolve_profile_path``)
* a list of deployable profiles for the CLI (``list_deployable_profiles``)
* a config-dict overlay merged under the user's ``config.yaml``
  (``apply_profile_defaults``)

Design rules:

1. **User always wins.** Profile values only fill keys the user left unset.
2. **Zero regression.** If the user omits ``--profile`` and leaves
   ``project.profile: ""``, nothing changes anywhere in the pipeline.
3. **Extensible.** Users drop ``~/.researchclaw/profiles/<id>.yaml`` or
   ``./profiles/<id>.yaml`` to add new domains without editing the package.
4. **Single source of truth.** The YAML schema extends the existing
   :class:`~researchclaw.domains.detector.DomainProfile` keys; no separate
   preset format.
"""

from __future__ import annotations

import copy
import logging
import os
from pathlib import Path
from typing import Any

import yaml

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Profile discovery
# ---------------------------------------------------------------------------

_PACKAGE_PROFILES_DIR = Path(__file__).parent / "profiles"


def profile_search_dirs(extra_dirs: list[Path] | None = None) -> list[Path]:
    """Return the ordered list of directories to search for profile YAMLs.

    Precedence (first hit wins): explicit ``extra_dirs`` →
    ``./profiles/`` (project-local) → ``~/.researchclaw/profiles/``
    (user-wide) → the bundled ``researchclaw/domains/profiles/``.

    Override the user dir by setting ``RESEARCHCLAW_PROFILES_DIR`` in the
    environment.
    """
    dirs: list[Path] = []
    if extra_dirs:
        dirs.extend(Path(d).expanduser().resolve() for d in extra_dirs)

    project_local = Path.cwd() / "profiles"
    if project_local.is_dir():
        dirs.append(project_local)

    env_override = os.environ.get("RESEARCHCLAW_PROFILES_DIR", "").strip()
    if env_override:
        user_dir = Path(env_override).expanduser().resolve()
    else:
        user_dir = Path.home() / ".researchclaw" / "profiles"
    if user_dir.is_dir():
        dirs.append(user_dir)

    if _PACKAGE_PROFILES_DIR.is_dir():
        dirs.append(_PACKAGE_PROFILES_DIR)

    # De-duplicate while preserving order.
    seen: set[Path] = set()
    unique: list[Path] = []
    for d in dirs:
        if d not in seen:
            seen.add(d)
            unique.append(d)
    return unique


def resolve_profile_path(
    profile_id: str,
    *,
    extra_dirs: list[Path] | None = None,
) -> Path | None:
    """Return the filesystem path of ``<profile_id>.yaml`` or ``None``."""
    pid = (profile_id or "").strip()
    if not pid:
        return None
    # Profile ids cannot contain path separators — prevents traversal.
    if "/" in pid or "\\" in pid or pid.startswith("."):
        return None
    for directory in profile_search_dirs(extra_dirs):
        candidate = directory / f"{pid}.yaml"
        if candidate.is_file():
            return candidate
    return None


def load_profile_yaml(
    profile_id: str,
    *,
    extra_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Load a profile YAML into a plain dict. Raises FileNotFoundError."""
    path = resolve_profile_path(profile_id, extra_dirs=extra_dirs)
    if path is None:
        raise FileNotFoundError(
            f"Domain profile '{profile_id}' not found. Search paths: "
            + ", ".join(str(p) for p in profile_search_dirs(extra_dirs))
        )
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(
            f"Profile {path} must be a YAML mapping, got {type(data).__name__}"
        )
    return data


def list_deployable_profiles(
    *,
    extra_dirs: list[Path] | None = None,
) -> list[dict[str, Any]]:
    """Return a list of profile descriptors for ``researchclaw profile list``.

    Each entry contains ``profile_id``, ``display_name``,
    ``preferred_experiment_mode``, ``preferred_target_conference``, and
    ``source_dir``. Profiles found closer to the user (project / env dir)
    shadow bundled ones with the same id.
    """
    seen: dict[str, dict[str, Any]] = {}
    for directory in profile_search_dirs(extra_dirs):
        for yaml_path in sorted(directory.glob("*.yaml")):
            pid = yaml_path.stem
            if pid.startswith("_") or pid in seen:
                continue
            try:
                with yaml_path.open(encoding="utf-8") as fh:
                    data = yaml.safe_load(fh) or {}
            except Exception:  # noqa: BLE001
                logger.warning("Could not parse profile %s", yaml_path, exc_info=True)
                continue
            if not isinstance(data, dict):
                continue
            seen[pid] = {
                "profile_id": data.get("domain_id", pid),
                "display_name": data.get(
                    "display_name", pid.replace("_", " ").title()
                ),
                "preferred_experiment_mode": data.get(
                    "preferred_experiment_mode", ""
                ),
                "preferred_target_conference": data.get(
                    "preferred_target_conference", ""
                ),
                "preferred_project_mode": data.get("preferred_project_mode", ""),
                "source_dir": str(directory),
            }
    return sorted(seen.values(), key=lambda e: e["profile_id"])


# ---------------------------------------------------------------------------
# Profile → config overlay mapping
# ---------------------------------------------------------------------------

# Maps profile top-level keys to dotted config paths.  Only listed keys are
# considered "deployment" fields; everything else in the profile (prompt
# guidance, detection keywords, etc.) is consumed elsewhere via the
# DomainProfile + PromptAdapter layers and should not touch config.yaml.
_SCALAR_FIELD_MAP: dict[str, str] = {
    "preferred_experiment_mode": "experiment.mode",
    "preferred_project_mode": "project.mode",
    "preferred_target_conference": "export.target_conference",
    "default_time_budget_sec": "experiment.time_budget_sec",
    "default_max_iterations": "experiment.max_iterations",
    "default_metric_key": "experiment.metric_key",
    "default_metric_direction": "experiment.metric_direction",
    "docker_image": "experiment.docker.image",
    "gpu_required": "experiment.docker.gpu_enabled",
}

# Sequence fields: the whole list lands at the given dotted path if unset.
_SEQUENCE_FIELD_MAP: dict[str, str] = {
    "pip_packages": "experiment.docker.pip_pre_install",
}

# Nested-block fields: entire sub-dicts (e.g. collider_agent, agentic,
# figure_agent) replace the corresponding sub-config only where the user
# has not set anything.
_NESTED_BLOCK_FIELDS: tuple[str, ...] = (
    "collider_agent",
    "agentic",
    "figure_agent",
    "code_agent",
    "cli_agent",
    "benchmark_agent",
    "repair",
)


# ---------------------------------------------------------------------------
# Deep merge (user wins)
# ---------------------------------------------------------------------------


def _deep_merge_user_wins(
    base: Any,
    overlay: Any,
) -> Any:
    """Return ``base`` with keys from ``overlay`` filled in.

    Semantics:
    * If both are dicts, recurse; user keys stay, overlay keys fill the gaps.
    * If ``base`` is a non-None / non-empty-string scalar or a non-empty
      list, keep the user value. Only when ``base`` is missing / blank does
      the overlay value take effect.
    """
    if isinstance(base, dict) and isinstance(overlay, dict):
        merged = dict(base)
        for key, overlay_val in overlay.items():
            if key not in merged:
                merged[key] = copy.deepcopy(overlay_val)
            else:
                merged[key] = _deep_merge_user_wins(merged[key], overlay_val)
        return merged
    # Scalars / lists: user wins unless they left the slot blank.
    if base is None:
        return copy.deepcopy(overlay)
    if isinstance(base, str) and not base.strip():
        return copy.deepcopy(overlay)
    if isinstance(base, (list, tuple)) and len(base) == 0:
        return copy.deepcopy(overlay)
    return base


def _set_by_path(data: dict[str, Any], dotted: str, value: Any) -> None:
    """Set ``data[a][b][c] = value`` creating dicts along the way."""
    parts = dotted.split(".")
    cur: dict[str, Any] = data
    for part in parts[:-1]:
        nxt = cur.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cur[part] = nxt
        cur = nxt
    cur[parts[-1]] = value


def _get_by_path(data: dict[str, Any], dotted: str) -> Any:
    cur: Any = data
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _is_unset(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, str) and not value.strip():
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    return False


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def apply_profile_defaults(
    config_data: dict[str, Any],
    profile_id: str,
    *,
    extra_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Return a new config dict with the profile's deployment defaults merged in.

    The profile is *advisory*: every key the user has already set in
    ``config.yaml`` stays untouched.  The profile only fills blanks.

    Parameters
    ----------
    config_data:
        The raw dict parsed from ``config.yaml``.
    profile_id:
        Profile id, e.g. ``"hep_ph"`` or ``"ml_vision"``.

    Raises
    ------
    FileNotFoundError
        If the profile id is unknown.
    """
    profile = load_profile_yaml(profile_id, extra_dirs=extra_dirs)
    result: dict[str, Any] = copy.deepcopy(config_data) if config_data else {}

    # 1. Scalar fields — straight copy to a dotted path, user wins.
    for src_key, dotted in _SCALAR_FIELD_MAP.items():
        if src_key not in profile:
            continue
        overlay_val = profile[src_key]
        if overlay_val is None:
            continue
        if _is_unset(_get_by_path(result, dotted)):
            _set_by_path(result, dotted, copy.deepcopy(overlay_val))

    # 2. Sequence fields — whole list lands at the path if unset.
    for src_key, dotted in _SEQUENCE_FIELD_MAP.items():
        if src_key not in profile:
            continue
        overlay_val = profile[src_key]
        if not isinstance(overlay_val, (list, tuple)):
            continue
        if _is_unset(_get_by_path(result, dotted)):
            _set_by_path(result, dotted, list(overlay_val))

    # 3. Nested experiment sub-blocks (collider_agent, agentic, ...).
    experiment_section = result.get("experiment")
    if not isinstance(experiment_section, dict):
        experiment_section = {}
        result["experiment"] = experiment_section

    for nested_key in _NESTED_BLOCK_FIELDS:
        overlay_block = profile.get(nested_key)
        if not isinstance(overlay_block, dict):
            continue
        user_block = experiment_section.get(nested_key)
        if not isinstance(user_block, dict):
            user_block = {}
        experiment_section[nested_key] = _deep_merge_user_wins(
            user_block, overlay_block
        )

    # 4. Top-level nested blocks (memory, skills, ...) — only the ones the
    #    profile explicitly mentions. Rare, but lets a profile preload a
    #    memory/skills config if desired.
    for top_key in ("memory", "skills", "web_search", "quality_assessor"):
        overlay_block = profile.get(top_key)
        if not isinstance(overlay_block, dict):
            continue
        user_block = result.get(top_key)
        if not isinstance(user_block, dict):
            user_block = {}
        result[top_key] = _deep_merge_user_wins(user_block, overlay_block)

    # 5. Echo the chosen profile into project.profile so downstream code
    #    (pipeline adapters, report header) can see what was deployed.
    project_section = result.get("project")
    if not isinstance(project_section, dict):
        project_section = {}
        result["project"] = project_section
    project_section["profile"] = str(profile_id).strip()

    logger.info(
        "Applied profile '%s' deployment defaults (source: %s)",
        profile_id,
        resolve_profile_path(profile_id, extra_dirs=extra_dirs),
    )
    return result


def describe_profile(
    profile_id: str,
    *,
    extra_dirs: list[Path] | None = None,
) -> dict[str, Any]:
    """Return a small descriptor used by the CLI's ``profile show`` output."""
    profile = load_profile_yaml(profile_id, extra_dirs=extra_dirs)
    path = resolve_profile_path(profile_id, extra_dirs=extra_dirs)
    return {
        "profile_id": profile.get("domain_id", profile_id),
        "display_name": profile.get("display_name", profile_id),
        "source_path": str(path) if path else "",
        "preferred_experiment_mode": profile.get("preferred_experiment_mode", ""),
        "preferred_target_conference": profile.get(
            "preferred_target_conference", ""
        ),
        "preferred_project_mode": profile.get("preferred_project_mode", ""),
        "docker_image": profile.get("docker_image", ""),
        "gpu_required": profile.get("gpu_required", False),
        "pip_packages": profile.get("pip_packages", []),
    }


# ---------------------------------------------------------------------------
# Autocomplete vocabularies — sourced from the live registries so the CLI
# wizard and (future) UI always see the real list of valid values, never a
# stale hand-maintained list.
# ---------------------------------------------------------------------------


def _experiment_modes() -> list[str]:
    try:
        from researchclaw.config import EXPERIMENT_MODES

        return sorted(EXPERIMENT_MODES)
    except Exception:  # noqa: BLE001
        return [
            "simulated", "sandbox", "docker", "ssh_remote",
            "colab_drive", "agentic", "collider_agent",
        ]


def _project_modes() -> list[str]:
    try:
        from researchclaw.config import PROJECT_MODES

        return sorted(PROJECT_MODES)
    except Exception:  # noqa: BLE001
        return ["docs-first", "semi-auto", "full-auto"]


def _conference_venues() -> list[str]:
    try:
        from researchclaw.templates.conference import list_conferences

        return list_conferences()
    except Exception:  # noqa: BLE001
        return [
            "neurips_2025", "icml_2026", "iclr_2026",
            "jhep", "prd", "prl", "prx", "epjc", "generic",
        ]


_PARADIGMS: list[str] = [
    "comparison",
    "convergence",
    "progressive_spec",
    "simulation",
    "ablation_study",
]

_METRIC_DIRECTIONS: list[str] = ["maximize", "minimize"]

_METRIC_TYPES: list[str] = [
    "scalar",
    "table",
    "convergence",
    "learning_curve",
    "confusion",
    "structured",
    "pareto",
]

_PARENT_DOMAINS: list[str] = [
    "ml",
    "physics",
    "hep_ph",
    "chemistry",
    "biology",
    "economics",
    "mathematics",
    "neuroscience",
    "security",
    "robotics",
    "engineering",
]

# Curated pip/core-library suggestions, grouped by parent domain. Used by
# the CLI wizard to offer a numbered pick-list. Users can always add free-
# form entries that aren't on the menu.
_LIBRARY_MENU: dict[str, list[str]] = {
    "ml": [
        "numpy", "scipy", "pandas", "scikit-learn", "matplotlib",
        "torch", "torchvision", "transformers", "datasets", "accelerate",
        "lightning", "einops", "tqdm", "wandb", "tensorboard",
        "xgboost", "lightgbm", "jax", "flax", "optax",
    ],
    "physics": [
        "numpy", "scipy", "matplotlib", "sympy", "jax", "jax-md",
        "fenics", "openmm", "ase", "mpi4py",
    ],
    "hep_ph": [
        "numpy", "scipy", "matplotlib", "iminuit", "uproot",
        "pyhepmc", "awkward", "lhapdf", "particle", "vector",
    ],
    "chemistry": [
        "numpy", "scipy", "rdkit", "pyscf", "openbabel", "ase",
        "mdtraj", "openmm", "matplotlib",
    ],
    "biology": [
        "numpy", "scipy", "pandas", "biopython", "pysam",
        "scanpy", "anndata", "mne", "nilearn", "matplotlib",
    ],
    "economics": [
        "numpy", "scipy", "pandas", "statsmodels", "linearmodels",
        "matplotlib", "seaborn",
    ],
    "mathematics": [
        "numpy", "scipy", "sympy", "matplotlib", "mpmath",
        "cvxpy", "pulp",
    ],
    "neuroscience": [
        "numpy", "scipy", "matplotlib", "brian2", "neo",
        "nilearn", "mne", "scikit-learn",
    ],
    "security": [
        "numpy", "scipy", "pandas", "scikit-learn",
        "scapy", "yara-python", "matplotlib",
    ],
    "robotics": [
        "numpy", "scipy", "matplotlib",
        "mujoco", "pybullet", "gymnasium", "stable-baselines3",
    ],
    "engineering": [
        "numpy", "scipy", "matplotlib", "pandas",
        "control", "scikit-learn",
    ],
    "generic": [
        "numpy", "scipy", "matplotlib", "pandas", "scikit-learn",
    ],
}

_KEYWORD_MENU: dict[str, list[str]] = {
    "ml": [
        "deep learning", "neural network", "representation learning",
        "self-supervised", "transfer learning", "benchmark",
    ],
    "hep_ph": [
        "dark matter", "beyond standard model", "collider phenomenology",
        "effective field theory", "exclusion limits", "relic density",
        "simplified model", "direct detection",
    ],
    "physics": [
        "numerical simulation", "molecular dynamics",
        "partial differential equation", "conservation law",
    ],
    "chemistry": [
        "density functional theory", "molecular property", "cheminformatics",
    ],
    "biology": [
        "single cell", "genomics", "proteomics", "bioinformatics",
    ],
    "economics": [
        "causal inference", "instrumental variable", "difference-in-difference",
    ],
    "mathematics": [
        "convergence analysis", "optimization", "numerical methods",
    ],
    "neuroscience": [
        "spiking neural network", "functional connectivity", "neural decoding",
    ],
    "security": [
        "intrusion detection", "anomaly detection", "malware analysis",
    ],
    "robotics": [
        "manipulation", "locomotion", "policy learning",
    ],
    "engineering": [
        "control system", "design optimization",
    ],
    "generic": [
        "computational methods",
    ],
}

# Default Docker images shipped with ResearchClaw.  Users can always type
# a custom image tag in the wizard.
_DOCKER_IMAGE_MENU: list[str] = [
    "researchclaw/sandbox-generic:latest",
    "researchclaw/sandbox-ml:latest",
    "researchclaw/experiment:latest",
    "python:3.11-slim",
    "nvidia/cuda:12.1.0-runtime-ubuntu22.04",
]


def schema_vocabularies() -> dict[str, Any]:
    """Return every autocomplete vocabulary used by the profile builder.

    Stable structure — safe to serialise as JSON for a future web UI.
    Values come from live registries where possible (experiment modes,
    conferences) so this never drifts out of sync with the actual code.
    """
    return {
        "experiment_modes": _experiment_modes(),
        "project_modes": _project_modes(),
        "target_conferences": _conference_venues(),
        "paradigms": list(_PARADIGMS),
        "metric_directions": list(_METRIC_DIRECTIONS),
        "metric_types": list(_METRIC_TYPES),
        "parent_domains": list(_PARENT_DOMAINS),
        "docker_images": list(_DOCKER_IMAGE_MENU),
        "libraries_by_parent": {k: list(v) for k, v in _LIBRARY_MENU.items()},
        "keywords_by_parent": {k: list(v) for k, v in _KEYWORD_MENU.items()},
    }


def library_suggestions(parent_domain: str) -> list[str]:
    """Curated pip/core-library suggestions for a parent domain."""
    return list(_LIBRARY_MENU.get(parent_domain, _LIBRARY_MENU["generic"]))


def keyword_suggestions(parent_domain: str) -> list[str]:
    """Paper keyword suggestions for a parent domain."""
    return list(_KEYWORD_MENU.get(parent_domain, _KEYWORD_MENU["generic"]))


# ---------------------------------------------------------------------------
# Profile id + data validation
# ---------------------------------------------------------------------------

import re as _re  # noqa: E402  (kept local to emphasise use-site)

_ID_RE = _re.compile(r"^[a-z][a-z0-9_]{1,62}$")


def validate_profile_id(profile_id: str) -> str | None:
    """Return an error message, or ``None`` if the id is valid.

    Rules: lowercase letters / digits / underscore; 2–63 chars; starts with
    a letter. Mirrors what the filesystem and YAML can safely hold.
    """
    if not profile_id:
        return "profile id must not be empty"
    if profile_id != profile_id.strip():
        return "profile id must not contain leading/trailing whitespace"
    if "/" in profile_id or "\\" in profile_id or profile_id.startswith("."):
        return "profile id must not contain path separators"
    if not _ID_RE.match(profile_id):
        return (
            "profile id must be 2–63 chars, start with a lowercase letter, "
            "and contain only lowercase letters / digits / underscores"
        )
    return None


def validate_profile_data(data: dict[str, Any]) -> list[str]:
    """Cross-check a profile dict against the live vocabularies.

    Returns a list of human-readable error strings.  Empty list ⇒ valid.
    """
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["profile data must be a mapping"]

    pid = data.get("domain_id", "")
    if not isinstance(pid, str) or validate_profile_id(pid):
        errors.append(
            f"domain_id invalid: "
            f"{validate_profile_id(pid if isinstance(pid, str) else '')}"
        )

    display = data.get("display_name", "")
    if not isinstance(display, str) or not display.strip():
        errors.append("display_name must be a non-empty string")

    vocab = schema_vocabularies()

    parent = data.get("parent_domain", "")
    if parent and parent not in vocab["parent_domains"]:
        errors.append(
            f"parent_domain '{parent}' is unusual — known values: "
            + ", ".join(vocab["parent_domains"])
        )

    mode = data.get("preferred_experiment_mode", "")
    if mode and mode not in vocab["experiment_modes"]:
        errors.append(
            f"preferred_experiment_mode '{mode}' invalid. "
            f"Choose from: {', '.join(vocab['experiment_modes'])}"
        )

    pmode = data.get("preferred_project_mode", "")
    if pmode and pmode not in vocab["project_modes"]:
        errors.append(
            f"preferred_project_mode '{pmode}' invalid. "
            f"Choose from: {', '.join(vocab['project_modes'])}"
        )

    venue = data.get("preferred_target_conference", "")
    if venue and venue not in vocab["target_conferences"]:
        errors.append(
            f"preferred_target_conference '{venue}' invalid. "
            f"Known: {', '.join(vocab['target_conferences'])}"
        )

    paradigm = data.get("experiment_paradigm", "")
    if paradigm and paradigm not in vocab["paradigms"]:
        errors.append(
            f"experiment_paradigm '{paradigm}' invalid. "
            f"Choose from: {', '.join(vocab['paradigms'])}"
        )

    direction = data.get("default_metric_direction", "")
    if direction and direction not in vocab["metric_directions"]:
        errors.append(
            f"default_metric_direction '{direction}' invalid. "
            "Choose from: minimize, maximize"
        )

    for key in ("pip_packages", "core_libraries", "paper_keywords"):
        val = data.get(key)
        if val is None:
            continue
        if not isinstance(val, list):
            errors.append(f"{key} must be a list of strings")
            continue
        for entry in val:
            if not isinstance(entry, str) or not entry.strip():
                errors.append(f"{key} has a non-string / empty entry")
                break

    for key in ("default_time_budget_sec", "default_max_iterations"):
        val = data.get(key)
        if val in (None, 0, ""):
            continue
        try:
            if int(val) < 0:
                errors.append(f"{key} must be >= 0")
        except (TypeError, ValueError):
            errors.append(f"{key} must be an integer")

    return errors


# ---------------------------------------------------------------------------
# Writable directories + create/delete
# ---------------------------------------------------------------------------


def default_user_profile_dir() -> Path:
    """The user-writable directory where new profiles should land.

    Honors ``RESEARCHCLAW_PROFILES_DIR`` if set, else
    ``~/.researchclaw/profiles/``.
    """
    env = os.environ.get("RESEARCHCLAW_PROFILES_DIR", "").strip()
    if env:
        return Path(env).expanduser().resolve()
    return (Path.home() / ".researchclaw" / "profiles").resolve()


def writable_profile_dirs() -> list[Path]:
    """Dirs the CLI may write new profiles into (in preference order)."""
    project_local = (Path.cwd() / "profiles").resolve()
    user_dir = default_user_profile_dir()
    # Don't dedupe — list distinct candidates.  Caller picks one.
    return [user_dir, project_local]


def is_package_profile(profile_id: str) -> bool:
    """True if the given id resolves to a bundled (read-only) profile."""
    path = resolve_profile_path(profile_id)
    if path is None:
        return False
    try:
        path.resolve().relative_to(_PACKAGE_PROFILES_DIR.resolve())
        return True
    except ValueError:
        return False


def _yaml_list(items: list[str], indent: int = 2) -> str:
    if not items:
        return " []"
    pad = " " * indent
    return "\n" + "\n".join(f"{pad}- {item}" for item in items)


def scaffold_profile_yaml(spec: dict[str, Any]) -> str:
    """Render a profile YAML string with rich inline comments.

    Every field includes an ``# e.g.`` hint + the set of accepted values so
    someone reopening the file months later knows exactly what to type.
    Only non-empty values are written into live YAML keys; empty ones stay
    as commented hints the user can uncomment later.
    """
    v = schema_vocabularies()

    pid = spec.get("domain_id", "my_domain")
    display = spec.get("display_name", pid.replace("_", " ").title())
    parent = spec.get("parent_domain", "")
    paradigm = spec.get("experiment_paradigm", "comparison")
    mode = spec.get("preferred_experiment_mode", "")
    pmode = spec.get("preferred_project_mode", "")
    venue = spec.get("preferred_target_conference", "")
    tbudget = int(spec.get("default_time_budget_sec", 0) or 0)
    max_iter = int(spec.get("default_max_iterations", 0) or 0)
    metric_key = spec.get("default_metric_key", "")
    metric_dir = spec.get("default_metric_direction", "")
    docker_image = spec.get("docker_image", "")
    gpu_required = bool(spec.get("gpu_required", False))
    pip_packages = list(spec.get("pip_packages") or [])
    core_libs = list(spec.get("core_libraries") or [])
    keywords = list(spec.get("paper_keywords") or [])
    entry_point = spec.get("entry_point", "main.py")

    # Commented-out placeholder lines let the user discover every option
    # without cluttering the live config.
    def _opt(key: str, value: Any, choices_hint: str = "") -> str:
        hint = f"    # options: {choices_hint}" if choices_hint else ""
        if value in (None, "", 0):
            return f"# {key}:{hint}"
        return f"{key}: {value}{hint}"

    return f"""\
# Domain profile: {display}
# Generated by `researchclaw profile create`.
#
# This file is a domain blueprint.  Dropping it into one of the profile
# search directories makes `--profile {pid}` deployable immediately.
#
# Search order (first hit wins):
#   ./profiles/                       — project-local
#   $RESEARCHCLAW_PROFILES_DIR         — explicit override
#   ~/.researchclaw/profiles/          — user-wide default
#   researchclaw/domains/profiles/     — bundled defaults
#
# Every key below is optional unless marked REQUIRED.  Profile defaults
# only fill *blank* slots in config.yaml — the user's config always wins.

# ── Identity ──────────────────────────────────────────────────────────────
domain_id: {pid}                    # REQUIRED — lowercase, matches filename stem
display_name: {display}             # REQUIRED — human-readable
parent_domain: {parent or '""'}     # e.g. {", ".join(v["parent_domains"])}

# ── Deployment defaults ───────────────────────────────────────────────────
# Only values that are NON-empty get applied at deploy time; comment out to
# defer to config.yaml / built-in defaults.
{_opt("preferred_experiment_mode", mode, " | ".join(v["experiment_modes"]))}
{_opt("preferred_project_mode", pmode, " | ".join(v["project_modes"]))}
{_opt("preferred_target_conference", venue, " | ".join(v["target_conferences"]))}
{_opt("default_time_budget_sec", tbudget or '', "integer seconds; e.g. 1800, 7200")}
{_opt("default_max_iterations", max_iter or '', "integer; e.g. 3, 5, 10")}
{_opt("default_metric_key", metric_key, "free-form; e.g. accuracy, f1, exclusion_95cl")}
{_opt("default_metric_direction", metric_dir, " | ".join(v["metric_directions"]))}
{_opt("docker_image", docker_image, "e.g. " + ", ".join(v["docker_images"][:3]))}
{"gpu_required: true" if gpu_required else "# gpu_required: false   # true | false"}

# Pip packages pre-installed in the sandbox container at deploy time.
pip_packages:{_yaml_list(pip_packages)}

# ── Domain characterization ──────────────────────────────────────────────
experiment_paradigm: {paradigm}   # options: {" | ".join(v["paradigms"])}

condition_terminology:
  baseline: baseline            # e.g. "baseline", "SM prediction", "existing bound"
  proposed: proposed method     # e.g. "proposed method", "BSM signal", "new algorithm"
  variant: ablation             # e.g. "ablation", "model variation"
  input: dataset                # e.g. "dataset", "process", "observation"
  metric: primary metric        # e.g. "accuracy/loss", "cross section", "p-value"

typical_file_structure:
  config.py: "Experiment configuration"
  data.py:   "Data loading / generation"
  methods.py: "Method implementations"
  main.py:   "Entry point: setup → run → evaluate → report"

entry_point: {entry_point}

core_libraries:{_yaml_list(core_libs)}

metric_types:
  - scalar          # options: {" | ".join(v["metric_types"])}

standard_baselines: []
evaluation_protocol: ""
statistical_tests:
  - paired_t_test

output_formats:
  - latex_table
figure_types:
  - line_plot
  - bar_chart

github_search_terms: []
paper_keywords:{_yaml_list(keywords)}

# ── Prompt guidance blocks ───────────────────────────────────────────────
# These strings are appended to stage prompts when this profile is active.
# Empty blocks are ignored.
compute_budget_guidance: |
  # Describe typical compute budgets / hardware constraints for this domain.

dataset_guidance: |
  # Describe canonical datasets / how experiments typically source inputs.

hp_reporting_guidance: |
  # How hyperparameters or model parameters should be reported.

code_generation_hints: |
  # Domain-specific coding guidelines and anti-patterns.

result_analysis_hints: |
  # How to interpret, plot, and compare results in this domain.
"""


def create_profile(
    spec: dict[str, Any],
    *,
    target_dir: Path | None = None,
    force: bool = False,
) -> Path:
    """Write a new profile YAML to disk.

    Parameters
    ----------
    spec:
        A dict at minimum containing ``domain_id``.  Passed through
        :func:`validate_profile_data`; raises ``ValueError`` on errors.
    target_dir:
        Directory to write into. Defaults to :func:`default_user_profile_dir`
        so the user-wide location is auto-created on first use.
    force:
        If ``True``, overwrite an existing file with the same id.

    Returns
    -------
    Path
        The written file.
    """
    pid = str(spec.get("domain_id", "")).strip()
    err = validate_profile_id(pid)
    if err:
        raise ValueError(f"Invalid profile id: {err}")

    errors = validate_profile_data(spec)
    if errors:
        raise ValueError("Invalid profile data:\n  - " + "\n  - ".join(errors))

    if target_dir is None:
        target_dir = default_user_profile_dir()
    target_dir = Path(target_dir).expanduser().resolve()
    target_dir.mkdir(parents=True, exist_ok=True)

    # Detect collisions: first the literal target path (so --target-dir
    # outside the normal search paths still gets checked), then any search
    # path so the user doesn't accidentally shadow a bundled profile.
    target_path = target_dir / f"{pid}.yaml"
    if target_path.exists() and not force:
        raise FileExistsError(
            f"Profile '{pid}' already exists at {target_path}. "
            "Pass force=True to overwrite."
        )
    existing = resolve_profile_path(pid)
    if (
        existing is not None
        and not force
        and existing.resolve() != target_path.resolve()
    ):
        # Collision with a bundled / earlier-priority profile.
        raise FileExistsError(
            f"Profile id '{pid}' already exists at {existing}. "
            "Either pick a different id, or pass force=True to write a "
            f"shadowing copy at {target_path}."
        )

    # Strip None/empty entries before scaffolding so the rendered YAML
    # stays clean.
    cleaned = {k: v for k, v in spec.items() if v not in (None, "", [])}
    cleaned["domain_id"] = pid
    target_path.write_text(scaffold_profile_yaml(cleaned), encoding="utf-8")
    logger.info("Created profile '%s' at %s", pid, target_path)
    return target_path


def delete_profile(profile_id: str) -> Path:
    """Delete a user-written profile. Refuses to touch bundled profiles.

    Returns the deleted path on success; raises on error.
    """
    err = validate_profile_id(profile_id)
    if err:
        raise ValueError(err)
    path = resolve_profile_path(profile_id)
    if path is None:
        raise FileNotFoundError(f"Profile '{profile_id}' not found")
    pkg_root = _PACKAGE_PROFILES_DIR.resolve()
    try:
        path.resolve().relative_to(pkg_root)
        raise PermissionError(
            f"Refusing to delete bundled profile at {path}. "
            "To hide it, add a shadowing profile in "
            f"{default_user_profile_dir()} or ./profiles/."
        )
    except ValueError:
        pass  # not under package dir — safe to delete
    path.unlink()
    return path


__all__ = [
    "apply_profile_defaults",
    "create_profile",
    "default_user_profile_dir",
    "delete_profile",
    "describe_profile",
    "is_package_profile",
    "keyword_suggestions",
    "library_suggestions",
    "list_deployable_profiles",
    "load_profile_yaml",
    "profile_search_dirs",
    "resolve_profile_path",
    "scaffold_profile_yaml",
    "schema_vocabularies",
    "validate_profile_data",
    "validate_profile_id",
    "writable_profile_dirs",
]
