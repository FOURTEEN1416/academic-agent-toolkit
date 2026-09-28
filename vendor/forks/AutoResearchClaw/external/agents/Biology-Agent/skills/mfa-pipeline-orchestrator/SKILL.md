---
name: mfa-pipeline-orchestrator
description: Orchestrate the full metabolic flux analysis pipeline from model loading to phenotype prediction and publication figures. Triggers when the user provides an organism name, BIGG model ID, or custom reaction list and wants end-to-end metabolic modelling run automatically.
metadata:
  category: domain
  trigger-keywords: "metabolic flux analysis,MFA,FBA,COBRApy,BIGG,metabolic engineering,genome-scale metabolic model,knockout,yield,phenotype prediction"
  applicable-stages: "8,9,10,11,12,13,14,15,16,17"
  priority: "1"
---

# MFA Pipeline Orchestrator

## Overview

Coordinates all mfa-agent sub-agents in sequence, tracking progress via `progress/` markdown files so any failed step can be resumed independently.

**Full pipeline:**
```
Model source (BIGG ID / custom reactions)
  → [model-builder]     models/<Model>.json  +  validation report
  → [fba-runner]        simulations/fba_fluxes.csv  +  scan_summary.json
  → [flux-analyzer]     analysis/essentiality.csv  +  phase_plane.png
  → [metabolic-pheno-analyzer]  output/figures/*.pdf  +  yield table
```

## Workflow

### Step 0: Parse User Request

Extract and record in `progress/step0_inputs.md`:
- Model source (BIGG ID or custom)
- Organism and condition (aerobic/anaerobic, carbon source, concentration)
- Objective reaction (biomass or product)
- Gene knockouts to apply
- Analysis goals (essentiality, phase plane, yield optimisation, WT vs. mutant comparison)
- Target product (if yield analysis requested)

### Step 1: Invoke model-builder

Provide: model source, medium constraints, objective, knockouts.
Wait for `progress/step1_metabolic_model.md`.
Read: model file path, WT growth rate, model statistics.

### Step 2: Invoke fba-runner

Provide: model path, simulation types requested (FBA, pFBA, FVA, knockout screen), carbon source sweep if requested.
Wait for `progress/step2_fba_simulation.md`.
Read: flux CSV paths, essential gene count, secretion fluxes.

### Step 3: Invoke flux-analyzer

Provide: model path, FBA results, analysis goals (essentiality, phase plane, sampling), nutrient pair for phase plane.
Wait for `progress/step3_flux_analysis.md`.
Read: essential genes, phase plane optimum, engineering targets.

### Step 4: Invoke metabolic-pheno-analyzer

Provide: model path, all previous results, target product, publication requirements.
Wait for `progress/step4_metabolic_phenotype.md`.
Read: max theoretical yield, figure paths.

## Progress File Specification

### `progress/step1_metabolic_model.md`
```markdown
# Step 1: Metabolic Model
## Status: PASS / FAIL
## Model: <BIGG_ID>.json
## Reactions: N  Metabolites: M  Genes: G
## WT growth rate: X h⁻¹
## Validation: mass balance errors=0, dead-ends=N
```

### `progress/step2_fba_simulation.md`
```markdown
# Step 2: FBA Simulation
## Status: PASS / FAIL
## Runs: FBA, pFBA, FVA, knockout screen
## WT growth rate: X h⁻¹ (pFBA: Y h⁻¹)
## Essential genes: N
## Key secretion products: [ethanol: X mmol/gDW/h, ...]
## Files: simulations/fba_fluxes.csv, simulations/gene_essentiality.csv
```

### `progress/step3_flux_analysis.md`
```markdown
# Step 3: Flux Analysis
## Status: PASS / FAIL
## Essential gene count: N
## Phase plane optimum: glucose=X, O2=Y → growth=Z h⁻¹
## Top engineering targets: [gene1, gene2, gene3]
## Files: analysis/phase_plane.png, analysis/essentiality.csv
```

## Key Conventions

- **Never re-run completed steps** — check progress file status before invoking sub-agents
- **Maximum total sub-agent retries: 10** across all steps
- **All file paths relative to working directory**
- **The orchestrator does not run FBA itself** — all computation delegated to sub-agents
