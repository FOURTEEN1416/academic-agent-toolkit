# External Claude-Code agents

This directory holds the **external Claude-Code agent suites** that the
AutoResearchClaw pipeline invokes at stage 12 (`EXPERIMENT_RUN`) when a
domain-specific `experiment.mode` calls for an agent-based sandbox.

These are *not* AutoResearchClaw subagents. The pipeline reads them at runtime
via the `*AgentConfig.<id>_agent_dir` field (see `researchclaw/config.py`); the
defaults point here so a fresh clone works out of the box for the vendored
agents.

## Layout

```
external/
└── agents/
    ├── README.md            (this file)
    ├── Biology-Agent/       (vendored — committed)
    ├── stat_research_agent/ (vendored — committed)
    └── ColliderAgent/       (pointer README only; clone upstream here)
```

Each agent ships a `skills/` directory of skill packages and an `agents/`
directory of subagent markdowns. The sandboxes copy these into `~/.claude/` and
the workspace's `.claude/` directory before invoking `claude -p ...`, so the
agent's skill suite is loaded by the Claude Code session.

## Repos

### Biology-Agent  (vendored)
- **Purpose**: end-to-end constraint-based metabolic-modelling pipeline
  (BIGG model → COBRApy → FBA / pFBA / FVA / KO screen → Escher map)
- **Layout**: `skills/` and `agents/` at the directory root
- **Wired via**: `researchclaw.experiment.biology_agent_sandbox.BiologyAgentSandbox`
- **Profile**: `researchclaw/domains/profiles/biology_metabolic.yaml`
  (`preferred_experiment_mode: biology_agent`)
- **Config**: `researchclaw.config.BiologyAgentConfig` —
  default `biology_agent_dir = "external/agents/Biology-Agent"`

### stat_research_agent  (vendored)
- **Purpose**: end-to-end statistical-methodology pipeline (problem formulation
  → method design → theory analysis → experimental evaluation → comparison →
  synthesis), plain CPU Python (numpy / scipy / pandas / sklearn / statsmodels)
- **Layout**: `skills/` and `agents/` at the directory root
- **Wired via**: `researchclaw.experiment.stat_agent_sandbox.StatAgentSandbox`
- **Config**: `researchclaw.config.StatAgentConfig` —
  default `stat_agent_dir = "external/agents/stat_research_agent"`

### ColliderAgent  (external — not vendored)
- **Upstream**: <https://github.com/HET-AGI/ColliderAgent>
- **Purpose**: end-to-end HEP phenomenology pipeline (Lagrangian → FeynRules →
  UFO → MadGraph5 → Pythia8 → Delphes → MadAnalysis5 → figure)
- **Layout note**: skills + agents live under `src/skills/` and `src/agents/`
- **Wired via**: `researchclaw.experiment.collider_agent_sandbox.ColliderAgentSandbox`
- **Profile**: `researchclaw/domains/profiles/hep_ph.yaml`
  (`preferred_experiment_mode: collider_agent`)
- **Config**: `researchclaw.config.ColliderAgentConfig` —
  default `collider_agent_dir = "external/agents/ColliderAgent"`
- **Install**: `git clone https://github.com/HET-AGI/ColliderAgent.git external/agents/ColliderAgent`
  (only `ColliderAgent/README.md` is tracked; a local checkout here is git-ignored).
  See `external/agents/ColliderAgent/README.md`.

## Adding a new external agent

1. Place the agent at `external/agents/<Name>/` with a `skills/` directory of
   skill packages and an `agents/` directory of subagent markdowns.
2. Implement a `<name>_agent_sandbox.py` mirroring
   `researchclaw/experiment/biology_agent_sandbox.py`.
3. Register the new mode in `EXPERIMENT_MODES` (`config.py`), add a
   `<Name>AgentConfig` dataclass, factory dispatch, and a profile that sets
   `preferred_experiment_mode: <name>_agent`.
4. See `docs/DOMAIN_INTEGRATION_GUIDE.md` for the full checklist.

## Attribution policy for ARC-Bench

When an ARC-Bench physics topic (`P*`) or biology topic (`B*`) is run, the
bench's per-run README and the bench's top-level scoreboard MUST credit the
upstream agent that produced the results. See `experiments/arc_bench/README.md`
for the wording.
