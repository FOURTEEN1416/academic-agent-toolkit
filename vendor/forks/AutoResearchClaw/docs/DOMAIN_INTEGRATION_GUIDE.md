# Domain Integration Guide

> Audience: domain experts (chemistry, neuroscience, biology, materials, …) who already have a curated set of prompts and want to plug their domain into AutoResearchClaw end-to-end.
> Working example throughout: the existing **`hep_ph`** integration (ColliderAgent + JHEP).

## 1. Elevator Summary

AutoResearchClaw runs a **fixed 23-stage research pipeline** (topic init → literature → hypothesis → experiment design → code generation → execution → analysis → paper draft → review → revision → export). The pipeline runner, gates, evaluators, LLM dispatch, and the experiment-config plumbing are **domain-agnostic**. To integrate a new domain you do not modify any of that. You add a small **plug-in surface** consisting of (at minimum) a profile YAML and a detector keyword tuple, and (at most) a new prompt bank, an adapter class, an experiment-mode sandbox, and a LaTeX template. The selected domain id flows through `PromptManager(domain=...)`, `get_adapter(...)`, and (optionally) `create_sandbox(config.mode == "<id>_agent")`. Every other stage handler reads the same generic API and never needs to know your domain exists.

## 2. Architecture (5 Layers)

```
   ┌─────────────────────────────────────────────────────────────────┐
   │  USER:  --profile <id>   OR   topic auto-detected by keywords    │
   └─────────────────────────────┬────────────────────────────────────┘
                                 │
                                 ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 1 — Profile YAML (declarative metadata)                        │
 │   researchclaw/domains/profiles/<id>.yaml                            │
 │   • preferred_experiment_mode, preferred_target_conference           │
 │   • condition_terminology, typical_file_structure, baselines, …     │
 │   Loaded by: researchclaw.domains.detector.load_all_profiles()       │
 │   Consumed by: deploy.py (defaults), DomainProfile fields everywhere │
 └─────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 2 — Prompt Adapter (per-stage block overlay, Python class)     │
 │   researchclaw/domains/adapters/<id>.py                              │
 │   class <Id>PromptAdapter(PromptAdapter):                            │
 │       get_code_generation_blocks(ctx)  -> PromptBlocks(...)          │
 │       get_experiment_design_blocks(ctx) -> PromptBlocks(...)         │
 │       get_result_analysis_blocks(ctx)   -> PromptBlocks(...)         │
 │       get_export_publish_blocks(ctx)    -> preferred_template, …    │
 │   Registered in: prompt_adapter.py:_build_adapter_registry           │
 └─────────────────────────────────┬────────────────────────────────────┘
                                   │  (optional — only if narrative
                                   │   prose differs from ML defaults)
                                   ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 3 — Prompt Bank (full STAGES dict, Python module)              │
 │   researchclaw/prompts/<id>.py                                       │
 │   STAGES = { "topic_init": {...}, ..., "export_publish": {...} }     │
 │   DEBATE_ROLES_HYPOTHESIS, DEBATE_ROLES_ANALYSIS                     │
 │   Loaded by: prompts/manager.py:_load_bank(domain)                   │
 │   MUST share stage keys + placeholders with prompts/ml.py            │
 │   (parity test in tests/test_prompt_bank_parity.py enforces this)    │
 └─────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 4 — Detector Keyword Rule (auto-routing)                       │
 │   researchclaw/domains/detector.py:_KEYWORD_RULES (lines ~245-351)   │
 │   ([... keyword phrases ...], "<id>")                                │
 │   Most-specific-first: HEP rule comes BEFORE generic "particle       │
 │   physics" so dark-matter topics route to hep_ph not physics_*       │
 └─────────────────────────────────┬────────────────────────────────────┘
                                   │
                                   ▼ (optional, only when domain wraps
                                     an external Claude-Code subagent)
 ┌──────────────────────────────────────────────────────────────────────┐
 │ LAYER 5 — Experiment Mode + Sandbox + LaTeX Template                 │
 │   researchclaw/config.py: EXPERIMENT_MODES set + <Id>AgentConfig      │
 │   researchclaw/experiment/<id>_agent_sandbox.py: SandboxProtocol     │
 │   researchclaw/experiment/factory.py: dispatch in create_sandbox()    │
 │   researchclaw/templates/conference.py: LaTeX template registry     │
 │   Hep example: collider_agent / ColliderAgentConfig / JHEP          │
 └──────────────────────────────────────────────────────────────────────┘
```

The narrow interface is intentional. Stages 0–23 of the pipeline runner stay generic; the only stage code that knows your domain exists is the prompt manager (which returns a `RenderedPrompt`) and — if you add Layer 5 — the sandbox factory.

## 3. The 7-File Checklist

When adding a new domain, every place that may need touching, in order:

| # | File | Action | Mandatory? |
|---|---|---|---|
| 1 | `researchclaw/domains/profiles/<id>.yaml` | **CREATE** — declarative metadata, deploy defaults | yes |
| 2 | `researchclaw/domains/adapters/<id>.py` | **CREATE** — `<Id>PromptAdapter` subclass | yes |
| 3 | `researchclaw/domains/adapters/__init__.py` **or** `researchclaw/domains/prompt_adapter.py:_build_adapter_registry` (lines 276–328) | **REGISTER** — add lazy import + prefix mapping | yes |
| 4 | `researchclaw/prompts/<id>.py` | **CREATE** — full `STAGES` dict + debate roles | only if you need stage-level prose forks (otherwise the ML bank is reused) |
| 5 | `researchclaw/prompts/manager.py:_load_bank` (lines 74–92) | **REGISTER** — `elif domain == "<id>": from researchclaw.prompts import <id> as _bank` | only if you added file 4 |
| 6 | `researchclaw/prompts/manager.py:SUPPORTED_DOMAINS` (line 31) | **APPEND** — add `"<id>"` to the tuple | only if you added file 4 |
| 7 | `researchclaw/domains/detector.py:_KEYWORD_RULES` (lines 245–351) | **APPEND** — `(["kw1", "kw2", ...], "<id>")` tuple | yes (otherwise auto-routing won't find you) |
| 8 (opt) | `researchclaw/config.py:EXPERIMENT_MODES` (lines 98–106) + new `<Id>AgentConfig` dataclass + `_parse_<id>_agent_config` | **APPEND** | only if Layer 5 |
| 9 (opt) | `researchclaw/experiment/<id>_agent_sandbox.py` | **CREATE** mirroring `collider_agent_sandbox.py` | only if Layer 5 |
| 10 (opt) | `researchclaw/experiment/factory.py:create_sandbox` (around line 85) | **APPEND** `if config.mode == "<id>_agent": ...` | only if Layer 5 |
| 11 (opt) | `researchclaw/templates/conference.py` | **APPEND** template entry + registry alias | only if you have a domain-native LaTeX style |

For the simplest possible new domain (e.g. plain Python analysis), files 1, 2, 3, 7 are enough. The full HEP integration uses all 11.

## 4. Profile YAML Skeleton

Modeled on `researchclaw/domains/profiles/hep_ph.yaml`. Every field carries a comment naming where it is consumed.

```yaml
# ── Identity ──────────────────────────────────────────────────────────────
domain_id: my_domain                # MUST equal the filename stem; used as
                                    #   the registry key in prompt_adapter,
                                    #   manager.py, factory.py, etc.
display_name: My Domain Name        # Human-readable; surfaces in prompts
                                    #   via DomainProfile.display_name
parent_domain: my_domain            # Free-form taxonomy parent; used by
                                    #   evaluator/grouping logic only

# ── Deployment defaults ───────────────────────────────────────────────────
# Consumed by researchclaw.domains.deploy when this profile is selected.
# Each key is applied only if the user's config.yaml leaves the slot blank.
preferred_experiment_mode: sandbox          # → experiment.mode (one of
                                            #   EXPERIMENT_MODES in config.py:98)
preferred_project_mode: full-auto           # → project.mode (PROJECT_MODES)
preferred_target_conference: neurips        # → export.target_conference
default_time_budget_sec: 1800               # → experiment.time_budget_sec
default_max_iterations: 5                   # → experiment.max_iterations
default_metric_key: primary_metric          # → experiment.metric_key
default_metric_direction: maximize          # → experiment.metric_direction

# ── Optional: external-agent block (mirrors collider_agent: in hep_ph.yaml)
# Only set this if you added a LAYER 5 sandbox + EXPERIMENT_MODE.
# my_domain_agent:
#   timeout_sec: 3600
#   max_turns: 100
#   install_skills: true
#   extra_args:
#     - "--dangerously-skip-permissions"

# ── Experiment paradigm ───────────────────────────────────────────────────
experiment_paradigm: simulation     # one of: simulation, convergence,
                                    #   progressive_spec, benchmark, …
                                    # GenericPromptAdapter switches default
                                    #   code-gen blurbs based on this value
                                    #   (see prompt_adapter.py:204-235)

# ── Domain vocabulary mapping (drives prompt phrasing) ────────────────────
condition_terminology:              # Used by GenericPromptAdapter to
                                    #   render experiment-design context.
                                    #   HEP example: "BSM model" instead
                                    #   of "method", "exclusion limit"
                                    #   instead of "accuracy".
  baseline: existing literature baseline / control measurement
  proposed: new method or model under test
  variant: parameter / hyperparameter variation
  input: dataset / sample / system being studied
  metric: primary success quantity for this domain

# ── Code-gen file scaffold (consumed by adapter.get_blueprint_context) ────
typical_file_structure:             # Renders into the blueprint prompt
                                    #   as a Recommended File Structure
                                    #   block (see prompt_adapter.py:94-97)
  model.py: "Core algorithm or model definition"
  analysis.py: "Run experiments and gather statistics"
  main.py: "Entry point: orchestrate model + analysis + report"

entry_point: main.py                # Documented as the main script the
                                    #   sandbox runner will invoke

core_libraries:                     # Listed in blueprint prompt and used
                                    #   by GenericPromptAdapter as the
                                    #   "Core libraries: ..." line.
  - numpy
  - scipy
  - matplotlib

docker_image: researchclaw/sandbox-generic:latest   # Consumed by deploy.py
gpu_required: false                                  # Consumed by deploy.py

pip_packages:                       # Auto-installed in sandbox / Docker
  - numpy
  - scipy
  - matplotlib

# ── Result shape ──────────────────────────────────────────────────────────
metric_types:                       # Drives output_format_guidance in the
                                    #   GenericPromptAdapter
                                    #   (see prompt_adapter.py:252-267).
                                    #   Allowed: scalar, table, structured,
                                    #   convergence
  - scalar
  - structured

standard_baselines:                 # Surfaces in experiment_design context
                                    #   via GenericPromptAdapter:170-178.
  - first canonical baseline name (with citation tag)
  - second baseline
  - …

evaluation_protocol: >              # Multi-line prose; injected into the
                                    #   experiment_design stage as part of
                                    #   the rendered context.
  Free-form description of how a successful experiment is measured: what
  is computed, what is compared against, what is the success criterion.

statistical_tests:                  # Listed in result_analysis stage via
                                    #   GenericPromptAdapter:191-202.
  - t_test
  - bootstrap_ci

output_formats:                     # Consumed by writing/export stage
  - latex_table
  - line_plot

figure_types:                       # Hints for the figure agent
  - bar_chart_metric_vs_baseline
  - learning_curve

github_search_terms:                # Used by literature search heuristics
  - <plain English search snippet>

paper_keywords:                     # Used in paper_outline / metadata
  - keyword 1
  - keyword 2

# ── Final blueprint hints (the only narrative text in this YAML) ──────────
# This is read by PromptAdapter.get_blueprint_context() and concatenated
# verbatim onto the code-blueprint prompt (prompt_adapter.py:101-103).
# Keep it short and concrete — instructions, not philosophy.
code_generation_hints: |
  Domain code requirements:
  1. <do this>
  2. <use that library>
  3. <write outputs to results.json with these keys>

  ANTI-PATTERNS for <my_domain> (DO NOT do these):
  - <thing the model gets wrong by default>
  - <another thing>
```

> **Tip — narrative belongs in the prompt bank, not the YAML.** After the Phase-B refactor (see `researchclaw/prompts/hep.py:1-23`), per-stage prose moved out of the YAML and into a dedicated bank module. Only `code_generation_hints` is left in YAML because it feeds the blueprint context.

## 5. Prompt Adapter Skeleton

Inherit from `PromptAdapter` (defined at `researchclaw/domains/prompt_adapter.py:52`). Each method returns a `PromptBlocks` dataclass (`prompt_adapter.py:26-49`); empty fields fall back to defaults.

```python
# researchclaw/domains/adapters/my_domain.py
"""My-domain prompt adapter."""
from __future__ import annotations
from typing import Any
from researchclaw.domains.prompt_adapter import PromptAdapter, PromptBlocks


class MyDomainPromptAdapter(PromptAdapter):
    """Adapter for <description of domain>."""

    # ── Stage 11 (code generation) ──────────────────────────────────────
    def get_code_generation_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        # Return PromptBlocks() (all empty) if you have a full prompt bank
        # in researchclaw/prompts/<id>.py — the bank already covers this
        # stage natively. (HEPPhPromptAdapter at hep_ph.py:24-25 does this.)
        #
        # If you don't have a bank, the GenericPromptAdapter pattern is to
        # populate the four common blocks from DomainProfile fields:
        domain = self.domain
        return PromptBlocks(
            compute_budget=domain.compute_budget_guidance or "",
            dataset_guidance=domain.dataset_guidance or "",
            hp_reporting=domain.hp_reporting_guidance or "",
            code_generation_hints=domain.code_generation_hints or "",
            output_format_guidance=(
                'Output results to results.json:\n'
                '{"conditions": {"method": {"metric": value}}, '
                '"metadata": {"domain": "my_domain"}}'
            ),
        )

    # ── Stage 10 (experiment design) ────────────────────────────────────
    def get_experiment_design_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        domain = self.domain
        design_context = (
            f"This is a **{domain.display_name}** experiment.\n\n"
            "Key principles:\n"
            "1. <first principle>\n"
            "2. <use canonical metric M>\n"
            "3. <compare against established baselines B1, B2>\n"
        )
        return PromptBlocks(
            experiment_design_context=design_context,
            statistical_test_guidance=(
                "Use <test family> for significance; apply <correction> "
                "for multiple comparisons."
            ),
        )

    # ── Stage 13 (result analysis) ──────────────────────────────────────
    def get_result_analysis_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks(
            result_analysis_hints=(
                "My-domain result analysis:\n"
                "- Report <metric A>, <metric B>, runtime\n"
                "- Distinguish primary vs secondary findings\n"
            ),
        )

    # ── Stage 22 (export / publish) ─────────────────────────────────────
    def get_export_publish_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        # Used when domain has its own LaTeX template and final-pass
        # formatting rules. HEP example: hep_ph.py:33-44.
        guidance = (
            "This is a <my_domain> manuscript; the export pass must "
            "preserve <domain conventions>. Do NOT insert "
            "<inappropriate template artifacts>."
        )
        return PromptBlocks(
            export_publish_guidance=guidance,
            preferred_template="my_template",   # registered in
                                                #   templates/conference.py
        )

    # ── Blueprint hint (called from blueprint stage) ────────────────────
    # Inherits the default from PromptAdapter.get_blueprint_context (lines
    # 87-105), which auto-renders typical_file_structure + core_libraries
    # + code_generation_hints from the YAML. Override only if you need
    # something dynamic.
```

### How the `PromptBlocks` fields map to rendered prompts

| `PromptBlocks` field | Stage that reads it | Effect |
|---|---|---|
| `compute_budget` | code generation | Replaces the default budget paragraph |
| `dataset_guidance` | code generation | Replaces the default dataset paragraph |
| `hp_reporting` | code generation | Replaces the default hyperparameter format |
| `code_generation_hints` | code generation | Replaces "domain hints" block |
| `output_format_guidance` | code generation | Replaces results.json schema example |
| `experiment_design_context` | experiment design | Replaces the high-level domain pitch |
| `statistical_test_guidance` | experiment design + result analysis | Names the appropriate stat tests |
| `result_analysis_hints` | result analysis | Replaces the default analysis checklist |
| `export_publish_guidance` | export/publish (stage 22) | Final-pass formatting rule (no NeurIPS checklists in JHEP, etc.) |
| `preferred_template` | export/publish | Selects a `templates/conference.py` entry when user hasn't set `export.target_conference` |

Real-world examples to crib from:
- `researchclaw/domains/adapters/biology.py` — full `GenericPromptAdapter`-style overlay (recommended starting point for bio/chem/neuro).
- `researchclaw/domains/adapters/hep_ph.py` — minimal adapter that returns empty blocks because all narrative lives in the prompt bank `prompts/hep.py`.

## 6. Prompt Bank Skeleton (optional — file 4)

If your domain's per-stage prose deviates substantially from ML defaults (the HEP-ph case), create a dedicated bank module. The contract:

1. Module exposes `STAGES: dict[str, dict[str, Any]]` whose keys **exactly match** those in `researchclaw/prompts/ml.py`. The parity test `tests/test_prompt_bank_parity.py` will fail if you add or drop a stage.
2. Each stage value is `{"system": str, "user": str, "json_mode": bool, "max_tokens": int}` (the latter two are optional; defaults `False` / `None`).
3. The `user` template uses `{placeholder}` substitution (the regex in `prompts/manager.py:39-51` is `r"\{(\w+)\}"`). The set of placeholders for each stage **must match the corresponding ML stage** so the call sites in the pipeline (which pass the same kwargs regardless of domain) work unchanged.
4. Optionally export `DEBATE_ROLES_HYPOTHESIS` and `DEBATE_ROLES_ANALYSIS` — dicts of `{role_name: {"system": ..., "user": ...}}` used by the multi-agent debate at the hypothesis/analysis stages. ML uses innovator/pragmatist/contrarian; HEP-ph uses theorist/phenomenologist/experimentalist (`prompts/hep.py:34-192`).

The full canonical stage list (from `prompts/hep.py`):

```
topic_init, problem_decompose, search_strategy, literature_collect,
literature_screen, knowledge_extract, synthesis, hypothesis_gen,
experiment_design, code_generation, resource_planning, result_analysis,
research_decision, paper_outline, paper_draft, peer_review,
paper_revision, quality_gate, knowledge_archive, export_publish
```

Example stage entry — `hypothesis_gen` from `prompts/hep.py:437-488`:

```python
STAGES["hypothesis_gen"] = {
    "system": (
        "You formulate testable HEP-phenomenology hypotheses that address "
        "gaps NOT covered by existing experimental results. Every "
        "hypothesis must be:\n"
        "1. NOVEL: Not replicating a published recast or an existing "
        "collaboration exclusion.\n"
        "..."
    ),
    "user": (
        "Generate at least 2 falsifiable HEP-ph hypotheses from the "
        "synthesis below.\n"
        "For each hypothesis provide:\n"
        "- **Hypothesis statement**: A clear claim in physics language, "
        "  naming the BSM model / operator and the observable.\n"
        "..."
        "{domain_context}"
        "Synthesis:\n{synthesis}"
    ),
}
```

The two placeholders `{domain_context}` and `{synthesis}` are exactly the kwargs the hypothesis stage handler passes — so the same handler works for both `prompts/ml.py` and `prompts/hep.py`.

### Wiring the bank into the manager

After creating `researchclaw/prompts/my_domain.py`, two single-line edits:

**`researchclaw/prompts/manager.py:31`**
```python
SUPPORTED_DOMAINS = ("ml", "hep_ph", "my_domain")
```

**`researchclaw/prompts/manager.py:74-92`** (`_load_bank`)
```python
def _load_bank(domain: str) -> tuple[...]:
    if domain == "hep_ph":
        from researchclaw.prompts import hep as _bank
    elif domain == "my_domain":
        from researchclaw.prompts import my_domain as _bank
    else:
        from researchclaw.prompts import ml as _bank
    ...
```

Anything not in `SUPPORTED_DOMAINS` falls back to the ML bank — see line 119:  `self._domain = domain if domain in SUPPORTED_DOMAINS else "ml"`. So if you forget to register, your domain silently uses ML prose.

## 7. Detector Keyword Rule

Auto-routing happens via a flat list of `(phrases, domain_id)` tuples scanned top-to-bottom in `researchclaw/domains/detector.py:_KEYWORD_RULES` (lines 245–351). The first rule whose keyword list intersects the topic text wins.

Rule format — one line per domain, most-specific-first:

```python
(["dark matter", "wimp", "direct detection", "dark photon",
  "axion", "neutralino", "bsm", "beyond standard model",
  "effective field theory", "relic density", "annihilation cross section",
  "hep-ph", "hep-ex", "madgraph5", "feynrules", "delphes", "pythia8",
  "collider phenomenology", "monojet", "mono-x", "missing et",
  "simplified model", "mediator mass", "portal interaction",
  "spin-independent", "spin-dependent", "xenon1t", "pandax", "lz experiment",
  "exclusion contour", "atlas dark matter", "cms dark matter"],
 "hep_ph"),
```

**Ordering rule (most-specific-first).** Place narrower domains before broader ones. The HEP-ph rule sits at lines 283–292 of `detector.py`, **before** the generic physics rules at lines 298–307, so a topic about "dark matter direct detection" hits `hep_ph` rather than being swallowed by the broader `physics_*` block. Similarly the neuroscience rules (lines 264–276) precede the ML catch-all (lines 279–281) so "spiking neural" routes to `neuroscience_computational` instead of ML.

When you add your domain, ask: *which already-listed rule could accidentally swallow my topic?* Place your tuple **above** that rule.

## 8. External-Agent Integration (the ColliderAgent pattern)

When your domain pipeline isn't a single Python script but a multi-tool toolchain — ColliderAgent runs Lagrangian → FeynRules → UFO → MadGraph5 → Delphes → MadAnalysis5 — wrap it in an experiment mode. The plug-in surface is exactly five edits:

### Step 1 — Register the mode

`researchclaw/config.py:98-106`
```python
EXPERIMENT_MODES = {
    "simulated",
    "sandbox",
    "docker",
    "ssh_remote",
    "colab_drive",
    "agentic",
    "collider_agent",     # ← existing example
    "my_domain_agent",    # ← your addition
}
```

### Step 2 — Define the config dataclass

Mirror `ColliderAgentConfig` at `config.py:296-333`:

```python
@dataclass(frozen=True)
class MyDomainAgentConfig:
    """Configuration for my-domain external-agent experiment mode."""

    # Path to your toolchain repo (used to install skills/agents)
    my_domain_agent_dir: str = "/path/to/MyDomainAgent"
    working_dir: str = "my_domain_workspace"
    timeout_sec: int = 3600
    claude_binary: str = ""                        # auto-detect if empty
    extra_args: tuple[str, ...] = ("--dangerously-skip-permissions",)
    install_skills: bool = True                    # copy skills → ~/.claude
    max_turns: int = 100
    # Add cloud creds, GPU flags, etc. as needed
    incremental: bool = False
```

### Step 3 — Wire it into `ExperimentConfig`

`researchclaw/config.py:475` — append a field next to `collider_agent`:

```python
@dataclass(frozen=True)
class ExperimentConfig:
    ...
    collider_agent: ColliderAgentConfig = field(default_factory=ColliderAgentConfig)
    my_domain_agent: MyDomainAgentConfig = field(default_factory=MyDomainAgentConfig)   # ← add
    ...
```

### Step 4 — Add the parser

`researchclaw/config.py:1094-1110` — mirror `_parse_collider_agent_config`:

```python
def _parse_my_domain_agent_config(data: dict[str, Any]) -> MyDomainAgentConfig:
    if not data:
        return MyDomainAgentConfig()
    extra_raw = data.get("extra_args", ("--dangerously-skip-permissions",))
    if isinstance(extra_raw, str):
        extra_raw = [extra_raw]
    return MyDomainAgentConfig(
        my_domain_agent_dir=data.get("my_domain_agent_dir", "/path/to/MyDomainAgent"),
        working_dir=data.get("working_dir", "my_domain_workspace"),
        timeout_sec=_safe_int(data.get("timeout_sec"), 3600),
        claude_binary=data.get("claude_binary", ""),
        extra_args=tuple(extra_raw),
        install_skills=bool(data.get("install_skills", True)),
        max_turns=_safe_int(data.get("max_turns"), 100),
    )
```

Then call it from `_parse_experiment_config` (around line 1179):

```python
my_domain_agent=_parse_my_domain_agent_config(data.get("my_domain_agent") or {}),
```

### Step 5 — Create the sandbox class

`researchclaw/experiment/my_domain_agent_sandbox.py` — mirror `collider_agent_sandbox.py` (≈656 lines). The minimum viable shape:

```python
"""MyDomainAgent sandbox — runs <domain> experiments via Claude Code."""
from __future__ import annotations
import json, os, shutil, subprocess, time
from pathlib import Path
from typing import Any

from researchclaw.config import MyDomainAgentConfig
from researchclaw.experiment.sandbox import SandboxResult

_PROMPT_FILENAME = "my_domain_plan.md"
_CLAUDE_INSTRUCTION = "Execute the analysis following " + _PROMPT_FILENAME


class MyDomainAgentSandbox:
    def __init__(self, config: MyDomainAgentConfig, workdir: Path) -> None:
        self.config = config
        self.workdir = workdir

    def run(self, prompt_text: str, *, timeout_sec: int | None = None) -> SandboxResult:
        timeout_sec = timeout_sec if timeout_sec is not None else self.config.timeout_sec
        workspace = self._prepare_workspace(prompt_text)
        cmd = self._build_command()

        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, cwd=str(workspace), env=self._build_env(),
                capture_output=True, text=True, timeout=timeout_sec,
            )
            returncode, stdout, stderr, timed_out = proc.returncode, proc.stdout, proc.stderr, False
        except subprocess.TimeoutExpired as exc:
            returncode, stdout, stderr, timed_out = -1, exc.stdout or "", exc.stderr or "", True

        elapsed = time.monotonic() - start
        artifacts = self._collect_artifacts(workspace)
        metrics = {
            "my_domain_agent_success": 1.0 if returncode == 0 and not timed_out else 0.0,
            "figures_produced": float(len(artifacts.get("figures", []))),
            "primary_metric": float(len(artifacts.get("figures", []))) / max(1.0, ...),
        }
        self._write_summary(workspace, returncode, elapsed, artifacts, timed_out)
        return SandboxResult(
            returncode=returncode, stdout=stdout, stderr=stderr,
            elapsed_sec=elapsed, metrics=metrics, timed_out=timed_out,
        )

    def _prepare_workspace(self, prompt_text: str) -> Path:
        ws = self.workdir
        ws.mkdir(parents=True, exist_ok=True)
        (ws / _PROMPT_FILENAME).write_text(prompt_text, encoding="utf-8")
        for sub in ("models", "scripts", "output/figures", "output/data", "progress"):
            (ws / sub).mkdir(parents=True, exist_ok=True)
        if self.config.install_skills:
            self._install_skills(ws)
        return ws

    def _install_skills(self, workspace: Path) -> None:
        # Mirror collider_agent_sandbox.py:445-505 — copy
        # <repo>/src/skills and <repo>/src/agents into both
        # ~/.claude/{skills,agents} (global) and workspace/.claude/{...}
        # (project-scoped, takes precedence in the CWD).
        ...

    def _build_command(self) -> list[str]:
        binary = self.config.claude_binary or shutil.which("claude") or "claude"
        cmd = [binary, "-p", _CLAUDE_INSTRUCTION]
        if self.config.max_turns > 0:
            cmd += ["--max-turns", str(self.config.max_turns)]
        cmd += [a for a in self.config.extra_args if a]
        return cmd

    def _build_env(self) -> dict[str, str]:
        env = os.environ.copy()
        # add credentials, paths, etc.
        return env

    def _collect_artifacts(self, workspace: Path) -> dict[str, list[str]]:
        # Walk workspace/output/** and categorize
        artifacts: dict[str, list[str]] = {"figures": [], "data": [], "scripts": [], "models": [], "logs": []}
        for p in sorted(workspace.glob("output/figures/*.pdf")):
            artifacts["figures"].append(str(p.relative_to(workspace)))
        # ...
        return artifacts

    def _write_summary(self, workspace, returncode, elapsed, artifacts, timed_out) -> None:
        # Merge sandbox metadata into workspace/results.json without
        # clobbering keys that the agent itself wrote (see
        # collider_agent_sandbox.py:610-655 for the merge contract).
        ...
```

The two design rules to copy from `ColliderAgentSandbox`:

1. **Existing keys win** for "soft" fields — the agent's own `results.json` is authoritative for things like `metrics` and `structured_results`; the sandbox only fills in `source`, `artifacts`, `status`. (`collider_agent_sandbox.py:626-655`)
2. **`returncode`, `elapsed_sec`, `timed_out` are sandbox-authoritative** — always overwritten regardless of what the agent wrote.

### Step 6 — Add the factory dispatch

`researchclaw/experiment/factory.py:85-89` — a dispatch case parallel to `collider_agent`:

```python
if config.mode == "my_domain_agent":
    from researchclaw.experiment.my_domain_agent_sandbox import MyDomainAgentSandbox
    return MyDomainAgentSandbox(config.my_domain_agent, workdir)
```

### Step 7 — Set the preference in your profile YAML

```yaml
preferred_experiment_mode: my_domain_agent

my_domain_agent:
  timeout_sec: 3600
  max_turns: 100
  install_skills: true
  extra_args:
    - "--dangerously-skip-permissions"
```

That's the entire Layer 5 surface. The pipeline runner doesn't change.

### Step 8 — Mandate a canonical `results.json` in the agent prompt

**This is non-optional for bench scoring.** Agent-based pipelines are atomic: the agent runs end-to-end inside one Claude Code session and exits. The downstream pipeline (stage 14 RESULT_ANALYSIS, stage 15 RESEARCH_DECISION, the bench rubric judge) only reads what's on disk afterwards. If the agent's scientific numbers don't reach a known-location structured file, the rubric scores all-null and the bench is meaningless.

In your `_prepare_workspace` (Step 5), append a **MANDATORY CANONICAL OUTPUT** footer to the prompt that instructs the agent to write `results.json` at the workspace root with this fixed schema:

```json
{
  "primary_metric": <number>,
  "metric_key": "<string>",
  "metrics": { "<domain_key_1>": <number>, "<domain_key_2>": <number>, ... },
  "hypotheses": {
    "h1": {"supported": true|false, "value": <number>, "details": "..."},
    "h2": {"supported": true|false, "details": "..."},
    "h3": {"supported": true|false, "details": "..."}
  },
  "summary": "human-readable narrative",
  "structured_results": {"artifacts": {"figures": [...], "data": [...]}}
}
```

See `biology_agent_sandbox.py:_prepare_workspace` and `collider_agent_sandbox.py:_prepare_workspace` for the exact instruction text — copy it verbatim.

In `_build_metrics`, read this file via a static `_read_agent_results(workspace)` helper and **merge `metrics.*` into the SandboxResult.metrics dict**, plus convert `hypotheses.<id>.supported` flags into `hypothesis_<id>_supported` 0/1 metrics. This makes the agent's scientific numbers visible to stage 14 and the rubric. See `biology_agent_sandbox.py:374-470` for the full pattern.

Crucial guard: the sandbox itself writes a meta stub to `results.json` (returncode, elapsed_sec, artifacts). `_read_agent_results` must skip that stub by requiring at least one of `metrics`, `primary_metric`, `hypotheses`, `structured_results` to be present, otherwise it picks up its own stub and forwards garbage. The fallback chain (`analysis/summary.json`, `analysis/flux_analysis_summary.json`) lets the agent use older conventions without breaking.

### Step 9 — Implement `run_project()` (SandboxProtocol parity)

The pipeline's stage-14 repair loop calls `sandbox.run_project(project_dir)` to re-execute. Without this method, repair cycles fail silently with `'XYZAgentSandbox' object has no attribute 'run_project'`. For agent-based sandboxes the implementation is trivial — a single Claude Code session IS the project — so dispatch to `run()` after reading the existing plan markdown:

```python
def run_project(self, project_dir, *, entry_point="main.py",
                timeout_sec=300, args=None, env_overrides=None):
    del entry_point, args, env_overrides  # SandboxProtocol parity only
    for cand in (project_dir / "REPAIR_PROMPT.md",
                 project_dir / _PROMPT_FILENAME,
                 self.workdir / _PROMPT_FILENAME):
        if cand.is_file():
            return self.run(cand.read_text(encoding="utf-8"),
                            timeout_sec=timeout_sec)
    return SandboxResult(returncode=-1, stdout="",
                         stderr="no plan found", elapsed_sec=0.0,
                         metrics={}, timed_out=False)
```

### Step 10 — Skip stage 13 + stage-14 repair for your mode

For agent-based modes, the python-code refinement loop in stage 13 ITERATIVE_REFINE and the stage-14 repair cycles are dead code: they iterate on python files the agent never executed, then re-spawn the agent atomically anyway. Two one-line edits skip them cleanly:

* `researchclaw/pipeline/stage_impls/_execution.py:519` — extend the existing `if config.experiment.mode == "collider_agent"` guard at the top of `_execute_iterative_refine` to also include `"my_domain_agent"`.
* `researchclaw/pipeline/runner.py:670` — extend the gate above `_run_experiment_diagnosis` / `_run_experiment_repair` so it skips when `config.experiment.mode in ("collider_agent", "biology_agent", "my_domain_agent")`.

After these edits the pipeline reduces to: stage 12 (agent runs, writes `results.json`) → stage 13 (no-op, copies artifacts forward) → stage 14 (reads `results.json`, builds summary) → stage 15 (proceed-or-reject decision based on the summary). No abstract code refinement.

### Step 11 — Declare requirements + plug into the LLM gate

For agent modes the pipeline replaces the python-style numeric-threshold repair with an **LLM-driven proceed/rerun gate** at stage 15 RESEARCH_DECISION. Each manifest declares:

```yaml
requirements:
  - id: req_<short_name>
    type: numeric | discussion | artifact   # advisory; LLM uses freely
    description: "natural-language statement of what must be true post-run"
    must_pass: true                          # true → unmet ⇒ rerun once
```

Mechanics:

1. `experiments/arc_bench/scripts/prepare_run.py:write_requirements()` copies the list to `run_dir/stage-09/requirements.json` and stashes the full manifest under `run_dir/stage-07/topic_manifest.json` for fallback lookup.
2. At stage 15, `researchclaw.pipeline.stage_impls._analysis._agent_requirements_decision()` fires (only when `experiment.mode in ("collider_agent", "biology_agent")`):
   - reads `requirements.json`
   - reads the most recent `experiment_summary.json` and the agent's canonical `results.json` (with the same fallback chain as the sandbox: `analysis/summary.json`, `analysis/flux_analysis_summary.json`, `output/data/results.json`)
   - calls `researchclaw.pipeline.requirements_judge.judge_requirements()` — LLM produces `{verdict: proceed|reject|partial, per_requirement: [...], delta_feedback}`
   - normalizes verdict from `per_requirement.met` (defends against LLM envelope inconsistency)
3. **On `reject` AND retry budget remains** (default 1 retry): writes `REPAIR_PROMPT.md` to the stage-12 sandbox workspace listing the unmet must_pass items, sets `decision = "refine"`. Runner-side override at `runner.py:718` redirects `refine` → `EXPERIMENT_RUN` for agent modes (not the python-refine `ITERATIVE_REFINE`), so the agent re-runs atomically. The sandbox's `_prepare_workspace()` consumes `REPAIR_PROMPT.md` (deletes it) and prepends it as a **FOLLOWUP DELTA** section ahead of the original plan.
4. **On `reject` with retry exhausted**, `proceed`, or `partial`: sets `decision = "proceed"`. The `requirements_unmet` flag (when present) flows into `requirements_verdict.json` at run root and downstream stages can surface caveats.

To raise the retry budget, change `_REQUIREMENTS_MAX_RETRIES` (default 1) in `_analysis.py`. To gate ML modes the same way, drop the `experiment.mode in ("collider_agent", "biology_agent")` guard at the top of `_execute_research_decision`.

Tight requirements work best — keep the must_pass set to **2-5 items** that the agent can unambiguously satisfy or fail. Use must_pass=false for nice-to-haves (mechanistic discussion, seed documentation) so the LLM can flag them without forcing a rerun.

### Step 12 — Paper-quality meta-rubric (applies to ALL topics)

Per-topic rubrics in `config/<domain>/rubrics/<id>.json` grade the **science**.
A separate file — `experiments/arc_bench/config/_meta_paper_quality.json` —
grades the **paper output** uniformly across every topic. You do NOT need to
write a separate paper-quality rubric for your domain: the same 19 leaves
(paper-content / code-orchestration / visual-layout / content-accuracy) apply
to ML, physics, biology, and any future domain.

The meta-rubric is graded **manually** via `scripts/judge_paper_manual.sh`,
which launches a vision-equipped Claude Code session against the run's
deliverable directory. The bench pipeline does NOT auto-invoke this — paper
quality is too expensive (~$0.5 + 10 min per run) and too subtle (figure
inspection, code review) to bake into every CI cycle.

Your domain only needs to make sure its **deliverables are present** for the
manual grader to find:
- `paper_final.md` (or `paper_revised.md`, or `paper_draft.md`) under any
  `stage-22/`, `stage-19/`, `stage-17/`, or `deliverables/`
- A `charts/` directory (PNG / PDF) under `stage-22/` or `deliverables/`
- A `code/` or `experiment_final/` directory with your domain's source

These are produced by the standard pipeline stages 16-22, so no extra wiring
is required.

### Step 13 — Place the agent repo under `external/agents/` with attribution

Don't reference absolute paths like `/home/<user>/MyDomainAgent` in the default config. Instead:

```bash
mkdir -p external/agents
ln -s /path/to/MyDomainAgent external/agents/MyDomainAgent
```

Then in `MyDomainAgentConfig`:

```python
my_domain_agent_dir: str = "external/agents/MyDomainAgent"
```

(Resolved relative to the repo root, which is the cwd when researchclaw runs.) Add an entry to `external/agents/README.md` crediting the upstream — for `ColliderAgent` the upstream is `https://github.com/HET-AGI/ColliderAgent`. The bench's per-run README must mention which external agent produced the results so reviewers can attribute correctly.

## 9. Validation Steps

Run these in order. Each command prints success/failure for one layer.

```bash
# 1. Profile loads (Layer 1)
python -c "from researchclaw.domains.detector import load_all_profiles; \
           print([p.domain_id for p in load_all_profiles()])"
# Expected: a list including "my_domain"

# 2. Detector matches your topic (Layer 4)
python -c "from researchclaw.domains.detector import detect_domain; \
           print(detect_domain('your topic with my_domain keyword'))"
# Expected: DomainProfile(domain_id="my_domain", ...)

# 3. Adapter dispatches (Layer 2)
python -c "from researchclaw.domains.detector import detect_domain; \
           from researchclaw.domains.prompt_adapter import get_adapter; \
           p = detect_domain('your topic with my_domain keyword'); \
           print(type(get_adapter(p)).__name__)"
# Expected: MyDomainPromptAdapter

# 4. Prompt bank loads (Layer 3 — only if you added one)
python -c "from researchclaw.prompts.manager import PromptManager; \
           pm = PromptManager(domain='my_domain'); \
           print(pm.domain, pm.stage_names()[:5])"
# Expected: ('my_domain', ['topic_init', 'problem_decompose', ...])

# 5. Parity test passes (catches missing stages or placeholder mismatches)
pytest tests/test_prompt_bank_parity.py -v
# Expected: all green; failures call out exactly which stage/placeholder
# diverged from the ML reference.

# 6. End-to-end smoke (single iteration, full 23 stages)
python -m researchclaw run \
    --profile my_domain \
    --topic "your domain-relevant topic" \
    --auto-approve \
    --max-iterations 1
# Expected: pipeline runs to completion; stage outputs land in the
# configured run_dir; the export stage emits a paper PDF in your
# preferred template.
```

If step 5 fails with "extra stage in my_domain" or "missing placeholder `{X}` in stage Y", fix the bank module — those are the precise contract violations the parity test catches.

## 10. Worked Example: `hep_ph` (ColliderAgent)

How the seven layers fit together for the existing HEP integration.

| Layer | File / line | What it contributes |
|---|---|---|
| 1. Profile | `researchclaw/domains/profiles/hep_ph.yaml` (131 lines) | `domain_id: hep_ph`, `preferred_experiment_mode: collider_agent`, `preferred_target_conference: jhep`, baselines = LZ/XENON1T/PandaX/ATLAS/CMS, statistical_tests = `cls_exclusion`, condition_terminology maps `metric` → "cross section / exclusion limit / signal significance", `code_generation_hints` injects the natural-units + anti-ML-pattern guidance into the blueprint stage. |
| 2. Adapter | `researchclaw/domains/adapters/hep_ph.py` | `HEPPhPromptAdapter` — minimal class. Three stage methods return empty `PromptBlocks()` because the prompt bank covers them; only `get_export_publish_blocks` is non-trivial — it returns `preferred_template="jhep"` and a guidance string telling the export pass to keep natural units and skip NeurIPS-style broader-impact paragraphs (`hep_ph.py:33-44`). |
| 2. Adapter registration | `researchclaw/domains/prompt_adapter.py:322-327` | Lazy import inside `_build_adapter_registry`; both exact key `"hep_ph"` and prefix `"hep_ph_"` map to `HEPPhPromptAdapter`. |
| 3. Prompt bank | `researchclaw/prompts/hep.py` (1404 lines) | Full STAGES dict with 20 entries (`topic_init` through `export_publish`); HEP-native debate roles `theorist / phenomenologist / experimentalist` for hypothesis (lines 34-118) and `model_builder / phenomenologist / experimentalist` for analysis (lines 121-192); HYPOTHESIS_GEN system prompt at lines 437-488 demands BSM Lagrangians, natural units, falsification numbers in cm²/pb. |
| 3. Bank registration | `researchclaw/prompts/manager.py:31, 85-86` | `SUPPORTED_DOMAINS = ("ml", "hep_ph")`; `_load_bank` branches on `domain == "hep_ph"` to import `researchclaw.prompts.hep`. |
| 4. Detector | `researchclaw/domains/detector.py:283-291` (with backup tuple at 293-296) | 27 keyword phrases (`dark matter`, `wimp`, `madgraph5`, `feynrules`, `delphes`, `xenon1t`, `pandax`, `monojet`, `mono-x`, `exclusion contour`, …) routed to `hep_ph`. Placed BEFORE the generic `physics_simulation` rule at line 299 so dark-matter topics don't get reclassified as molecular dynamics. |
| 5. Experiment mode | `researchclaw/config.py:105` (`"collider_agent"` in `EXPERIMENT_MODES`) | Adds the mode token. |
| 5. Config dataclass | `researchclaw/config.py:296-333` (`ColliderAgentConfig`) | Holds `collider_agent_dir`, `working_dir`, `timeout_sec=7200`, `extra_args=("--dangerously-skip-permissions",)`, `install_skills=True`, `max_turns=150`, optional `magnus_address`/`magnus_token`, and `incremental` re-entry flag. |
| 5. Wired into ExperimentConfig | `researchclaw/config.py:475` | `collider_agent: ColliderAgentConfig = field(default_factory=ColliderAgentConfig)` |
| 5. Parser | `researchclaw/config.py:1094-1110` (`_parse_collider_agent_config`) | Reads `experiment.collider_agent.*` from user YAML. |
| 5. Sandbox | `researchclaw/experiment/collider_agent_sandbox.py` (656 lines) | `ColliderAgentSandbox.run(prompt_text)` writes `collider_plan.md`, `mkdir`s the canonical subtree (`models/`, `scripts/`, `events/`, `analysis/`, `output/figures/`, `output/data/`, `progress/`) (line 261), copies `<ColliderAgentDir>/src/{skills,agents}` into both `~/.claude/` (global, line 459) and `workspace/.claude/` (project-scoped, line 492), invokes `claude -p "Execute the analysis following collider_plan.md" --max-turns 150 --dangerously-skip-permissions` (lines 507-524), then collects artifacts (figures/data/scripts/models/logs) and merges them into `results.json` without clobbering ColliderAgent's own structured output (lines 538-655). Also implements an `incremental` re-entry mode that snapshots prior stage-12 runs into `stage-12_v{N}/`, builds a workspace manifest, and prepends a CONTINUATION CONTEXT block so the next run touches only the deltas (lines 169-258, 270-409). |
| 5. Factory dispatch | `researchclaw/experiment/factory.py:85-89` | `if config.mode == "collider_agent": return ColliderAgentSandbox(config.collider_agent, workdir)` |
| 6. LaTeX template | `researchclaw/templates/conference.py:345-373` | `JHEP` template (`name="jhep"`, `style_package="jheppub"`, `author_format="jhep"`, points to the official JHEP TeXclass download URL); registered under alias `"jhep"` at line 531. Selected automatically via `HEPPhPromptAdapter.get_export_publish_blocks(...).preferred_template == "jhep"` whenever the user hasn't manually set `export.target_conference`. |

End-to-end flow when a user runs `python -m researchclaw run --profile hep_ph --topic "dark photon mediator dark matter"`:

1. `deploy.py` reads `profiles/hep_ph.yaml` → fills `experiment.mode = "collider_agent"`, `export.target_conference = "jhep"`, time budget 7200 s, etc.
2. `PromptManager(domain="hep_ph")` loads `prompts/hep.py` STAGES.
3. Pipeline runs stages 0–10. Hypothesis generation uses the theorist/phenomenologist/experimentalist debate roles. Code generation stage's blueprint context is enriched with `typical_file_structure` and `code_generation_hints` from the YAML via `HEPPhPromptAdapter.get_blueprint_context()`.
4. Stage 12 (experiment execution) calls `create_sandbox(config)` → factory dispatches to `ColliderAgentSandbox` → writes the assembled physics plan to `collider_plan.md`, installs skills, invokes Claude Code, collects artifacts back into `metrics`.
5. Stage 13 result analysis uses the model_builder/phenomenologist/experimentalist debate roles.
6. Stage 22 export reads `HEPPhPromptAdapter.get_export_publish_blocks()` → selects the JHEP template → renders the paper using `jheppub.cls`.

The 23-stage runner code is unchanged from the ML pipeline.

## 11. What You Do NOT Need to Touch

The plug-in surface is intentionally narrow. **None of the following ever needs domain-specific edits**:

- The pipeline runner (`researchclaw/pipeline/runner.py`) — it iterates stages by name and calls `pm.for_stage(name, **vars)`.
- Stage handlers (`researchclaw/pipeline/stages/*.py`) — they request a `RenderedPrompt` from the manager and pass the same kwarg set regardless of domain.
- LLM dispatch (`researchclaw/llm/*.py`) — model selection, retries, token accounting.
- Gates and judges (`researchclaw/pipeline/gates/*.py`, `researchclaw/judge/*`) — they evaluate outputs against generic structural and quality rubrics.
- Knowledge base writer (`researchclaw/kb/*.py`) — markdown/Obsidian backends are domain-agnostic.
- Evaluators / scoreboards (`researchclaw/evaluator/*`).
- Experiment auto-repair (`researchclaw/experiment/repair*.py`).
- Code-generation agent core (`researchclaw/code_agent/*`) — it consumes the blueprint context the adapter produced.
- The CLI (`researchclaw/__main__.py`, `researchclaw/cli/*`).

If you find yourself editing any of these to make a new domain work, stop — that's a sign the plug-in surface needs widening (or you're doing too much). The five layers above are the contract.

---

### Quick reference: minimum viable new domain

```text
1. researchclaw/domains/profiles/<id>.yaml         — write the YAML
2. researchclaw/domains/adapters/<id>.py           — copy biology.py, edit
3. researchclaw/domains/adapters/__init__.py       — import + __all__
   researchclaw/domains/prompt_adapter.py          — add to _build_adapter_registry
4. researchclaw/domains/detector.py:_KEYWORD_RULES — append your tuple
5. pytest tests/test_prompt_bank_parity.py         — must pass (no-op
                                                      unless you added a bank)
6. python -m researchclaw run --profile <id> ...   — smoke test
```

That's the whole thing. The HEP integration adds layers 5/6 (external agent + JHEP template) on top of the same skeleton.
