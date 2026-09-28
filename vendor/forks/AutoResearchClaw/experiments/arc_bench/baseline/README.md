# ARC-Bench baselines

Self-contained baseline framework integrations. Everything needed to
clone, install, configure, and run each baseline lives under this
directory.

## Layout

- `adapters/` — ARC-Bench `FrameworkAdapter` implementations (one .py per
  baseline). All adapters subclass `base.FrameworkAdapter` and produce a
  `submission/` directory in the standard ARC-Bench layout that
  `scripts/judge.py` can read.
- `external/` — upstream framework clones (gitignored). Recreate via the
  setup steps below.
- `interventions/` — rc_copilot's scripted HITL JSONs (T01-T25). One file
  per topic; auto-derived by `scripts/hitl_suggestor.py` from rc_full's
  prior failure modes.

## Baselines integrated

| Adapter | Framework ID | External repo | Install location | Conda env |
|---------|-------------|---------------|------------------|-----------|
| `aide_adapter.py` | `aide_ml` | WecoAI AIDE | `external/aideml/` | `/playpen2/.../aide_ml/conda_env/` (editable install of `external/aideml/`) |
| `agent_lab_adapter.py` | `agent_lab` | samuelschmidgall/AgentLaboratory | `external/AgentLaboratory/` | `/playpen2/.../agent_lab/conda_env/` |
| `ai_scientist_v2_adapter.py` | `ais_v2` | SakanaAI/AI-Scientist-v2 | `external/AI-Scientist-v2/` | `/playpen2/shiqiu/arc_bench/ais_v2_venv/` |
| `researchclaw_adapter.py` | `rc_full` / `rc_copilot` | autoclaw (this repo) | n/a — uses `experiments/researchclaw/` upstream | n/a — uses repo-root env |

`AI-Scientist v1` was deliberately removed (template-constrained on a
fixed set of starter papers; not applicable to ARC-Bench's open-ended
research questions).

## One-time install (per baseline)

### AIDE ML

```bash
git clone https://github.com/WecoAI/aideml.git \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/aideml

# Create conda env on /playpen2 (large dependency tree)
conda create -p /playpen2/shiqiu/arc_bench/baselines/aide_ml/conda_env python=3.11 -y
PIP_CACHE_DIR=/playpen2/shiqiu/arc_bench/baselines/aide_ml/pip_cache \
  /playpen2/shiqiu/arc_bench/baselines/aide_ml/conda_env/bin/pip install -e \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/aideml

# Patch the AIDE backend to read OPENAI_BASE_URL from env (one-line)
# in baseline/external/aideml/aide/backend/backend_openai.py:
#   OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
```

### AgentLaboratory

```bash
git clone https://github.com/SamuelSchmidgall/AgentLaboratory.git \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/AgentLaboratory

conda create -p /playpen2/shiqiu/arc_bench/baselines/agent_lab/conda_env python=3.11 -y
/playpen2/shiqiu/arc_bench/baselines/agent_lab/conda_env/bin/pip install -r \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/AgentLaboratory/requirements.txt

# Apply ARC-Bench env-var patch (AGENTLAB_RESEARCH_DIR support)
# See `experiments/framework_comparison/patches/AgentLab_research_dir_env.diff`
# in the repo history if you need the original patch context.
```

### AI Scientist v2

```bash
git clone https://github.com/SakanaAI/AI-Scientist-v2.git \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/AI-Scientist-v2

python -m venv /playpen2/shiqiu/arc_bench/ais_v2_venv
/playpen2/shiqiu/arc_bench/ais_v2_venv/bin/pip install -r \
    /path/to/AutoResearchClaw/experiments/arc_bench/baseline/external/AI-Scientist-v2/requirements.txt
```

## Per-baseline runtime contracts

| Baseline | Code/metrics output | Writeup output | Special notes |
|----------|---------------------|----------------|---------------|
| aide_ml | `submission/results/metrics.json` + workspace `*.csv` | `native/report.md` | Heavy on /playpen2 (logs + workspaces accumulate) |
| agent_lab | `native/research_dir_*/final_results.json` | `native/research_dir_*/research_report.md` | Fair-input runs die in lit-review SUMMARY-loop (see UNIFIED_JUDGE.md) |
| ais_v2 | `submission/results/metrics.json` | `submission/README.md` | Sparse input (title-only); manifest drift common |
| rc_full | `submission/results/metrics.json` + `stage-14/experiment_summary.json` | `submission/README.md` | Multi-stage autoclaw pipeline |
| rc_copilot | same as rc_full | same | + uses `interventions/<Txx>.json` |

## Adapter API

All adapters implement:

```python
class FrameworkAdapter:
    framework_id: str  # one of {ais_v2, agent_lab, aide_ml}
    def is_available(self) -> tuple[bool, str]: ...
    def run(self, topic: dict, output_dir: Path) -> FrameworkResult: ...
```

`topic` is the merged `config/topics.yaml` entry + `config/manifests/<id>.yaml`.

`output_dir` is the `native/` subdirectory of the per-run results dir
(`results/<framework>/<topic>/<run_id>/native/`).

`FrameworkResult` carries status (`completed | failed | timeout |
skipped`), elapsed time, and `StandardArtifacts` (paper text, stages_done,
experiment_summary, etc.) which `scripts/run_baseline.py` then translates
into the `submission/` layout the judge reads.

## rc_copilot interventions

`interventions/<Txx>.json` files are the auto-derived HITL guidance that
rc_copilot consumes on top of rc_full's normal pipeline. They are
generated from rc_full's prior failure modes by:

```bash
python experiments/arc_bench/scripts/hitl_suggestor.py --topic T01
# or
python experiments/arc_bench/scripts/hitl_suggestor.py --all
```

The interventions are derivative of the framework's own observed failure
modes — no human authoring — which is what makes rc_copilot a fair-input
auto-HITL framework, not a scaffolded one.
