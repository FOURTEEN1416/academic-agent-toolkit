# ColliderAgent

ColliderAgent is **not vendored** into this repository. Get it from upstream:

> **https://github.com/HET-AGI/ColliderAgent**

## Purpose

End-to-end HEP phenomenology pipeline (Lagrangian → FeynRules → UFO →
MadGraph5 → Pythia8 → Delphes → MadAnalysis5 → figure). AutoResearchClaw
invokes it at stage 12 (`EXPERIMENT_RUN`) when `experiment.mode = collider_agent`.

## Install

Clone (or symlink) the upstream repo into this directory so the path matches the
default `collider_agent_dir = "external/agents/ColliderAgent"`:

```bash
git clone https://github.com/HET-AGI/ColliderAgent.git \
    external/agents/ColliderAgent
```

Or point `ColliderAgentConfig.collider_agent_dir` (config.py / your run config)
at wherever you checked it out.

The agent's skills + agents live under `src/skills/` and `src/agents/`; the
sandbox (`researchclaw.experiment.collider_agent_sandbox`) copies these into
`~/.claude/` and the workspace `.claude/` before launching `claude -p ...`.

> Everything in this directory other than this `README.md` is git-ignored, so a
> local checkout of ColliderAgent here will not be committed.
