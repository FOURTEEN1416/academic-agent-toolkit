---
name: flux-analyzer
description: >
  Analyse FBA flux distributions to extract biological insights. Covers gene
  essentiality, phenotypic phase planes, flux sampling, pathway-level
  aggregation, secretion product prediction, and production of publication-
  quality figures.
metadata:
  category: domain
  trigger-keywords: "metabolic,flux analysis,gene essentiality,synthetic lethality,production envelope,phase plane,flux sampling,secretion,yield,metabolic engineering"
  applicable-stages: "9,10,12,13,14,15,16,17,20"
  priority: "1"
---

## Overview

The `flux-analyzer` skill transforms raw FBA output into actionable biological
knowledge. It operates on FBA result files and the COBRApy model to produce
gene essentiality maps, phenotypic phase planes (PPP), flux sampling
distributions, pathway-level summaries, and product secretion profiles.

This skill is the metabolic-modelling analogue of event reconstruction and
phenomenology summary stage in the ColliderAgent pipeline: it turns numbers
into biology.

---

## Workflow

### Step 1 — Load Model and FBA Results

```python
import cobra
import cobra.io
import cobra.flux_analysis
import cobra.sampling
import pandas as pd
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

model = cobra.io.load_json_model("my_model.json")
fba_fluxes = pd.read_csv("fba_fluxes.csv", index_col=0)["flux_mmol_gDW_h"]
wt_growth = model.optimize().objective_value
print(f"Wild-type growth: {wt_growth:.4f} h^-1")
```

### Step 2 — Gene Essentiality Analysis

Essential genes are those whose deletion reduces growth to below 5% of
wild-type — a widely used lethality criterion.

```python
from cobra.flux_analysis import single_gene_deletion, double_gene_deletion

# --- Single gene essentiality ---
sg_deletion = single_gene_deletion(model)
sg_deletion.columns = ["growth", "status"]
sg_deletion["is_essential"] = sg_deletion["growth"] < 0.05 * wt_growth
sg_deletion["growth_fraction"] = sg_deletion["growth"] / wt_growth

essential_genes = sg_deletion[sg_deletion["is_essential"]]
print(f"Essential genes: {len(essential_genes)} / {len(model.genes)}")
sg_deletion.to_csv("gene_essentiality.csv")

# --- Double gene essentiality (synthetic lethality) ---
# Limit to a focused gene set to reduce compute time
target_genes = list(model.genes)[:50]   # adjust as needed
dg_deletion = double_gene_deletion(model, target_genes, target_genes)
dg_deletion.columns = ["growth", "status"]
dg_deletion["is_synthetic_lethal"] = dg_deletion["growth"] < 0.05 * wt_growth
dg_deletion.to_csv("double_gene_essentiality.csv")
```

### Step 3 — Reaction Essentiality Analysis

```python
from cobra.flux_analysis import single_reaction_deletion

sr_deletion = single_reaction_deletion(model)
sr_deletion.columns = ["growth", "status"]
sr_deletion["is_essential"] = sr_deletion["growth"] < 0.05 * wt_growth
essential_rxns = sr_deletion[sr_deletion["is_essential"]]
print(f"Essential reactions: {len(essential_rxns)} / {len(model.reactions)}")
sr_deletion.to_csv("reaction_essentiality.csv")
```

### Step 4 — Phenotypic Phase Plane (PPP)

The PPP maps growth rate over a 2D grid of two nutrient uptake rates, revealing
metabolic phase transitions (aerobic growth, mixed-acid fermentation, etc.).

```python
from cobra.flux_analysis import production_envelope

# Phase plane: glucose uptake vs. oxygen uptake
ppp = production_envelope(
    model,
    ["EX_glc__D_e", "EX_o2_e"],   # x and y axes
    objective=model.reactions.get_by_id("BIOMASS_Ec_iJO1366_core_53p95M"),
    points=20,
)

print(ppp.head())

# Plot heatmap
fig, ax = plt.subplots(figsize=(8, 6))
pivot = ppp.pivot_table(
    index="EX_o2_e", columns="EX_glc__D_e", values="flux_maximum"
)
im = ax.imshow(pivot.values, aspect="auto", origin="lower",
               cmap="viridis",
               extent=[ppp["EX_glc__D_e"].min(), ppp["EX_glc__D_e"].max(),
                       ppp["EX_o2_e"].min(),    ppp["EX_o2_e"].max()])
plt.colorbar(im, ax=ax, label="Growth rate (h$^{-1}$)")
ax.set_xlabel("Glucose uptake (mmol/gDW/h)")
ax.set_ylabel("O$_2$ uptake (mmol/gDW/h)")
ax.set_title("Phenotypic Phase Plane")
fig.tight_layout()
fig.savefig("phenotypic_phase_plane.pdf", dpi=300)
fig.savefig("phenotypic_phase_plane.png", dpi=150)
plt.close(fig)
print("PPP saved to phenotypic_phase_plane.pdf")
```

### Step 5 — Flux Sampling

Flux sampling explores the full space of feasible steady-state flux
distributions, revealing which reactions have wide vs. narrow feasible ranges.

```python
# OptGP sampler: Markov-chain Monte Carlo in flux cone
samples = cobra.sampling.sample(model, n=1000, method="optgp",
                                thinning=100, processes=4)
# samples is a DataFrame: rows = samples, columns = reaction IDs
samples.to_csv("flux_samples.csv", index=False)

# Violin plot for key central metabolism reactions
KEY_REACTIONS = ["PFK", "PGI", "PDH", "CS", "AKGDH",
                 "EX_glc__D_e", "EX_ac_e", "EX_co2_e"]
key_data = samples[[r for r in KEY_REACTIONS if r in samples.columns]]

fig, ax = plt.subplots(figsize=(10, 5))
ax.violinplot([key_data[c].values for c in key_data.columns],
              positions=range(len(key_data.columns)),
              showmedians=True)
ax.set_xticks(range(len(key_data.columns)))
ax.set_xticklabels(key_data.columns, rotation=45, ha="right")
ax.set_ylabel("Flux (mmol/gDW/h)")
ax.set_title("Flux Sampling Distribution (n=1000)")
fig.tight_layout()
fig.savefig("flux_sampling_violin.pdf", dpi=300)
plt.close(fig)
print("Flux sampling violin plot saved.")
```

### Step 6 — Pathway-Level Flux Aggregation

Group reactions by metabolic subsystem and compute total absolute flux per
pathway — a proxy for pathway activity.

```python
pathway_flux = {}

for rxn in model.reactions:
    subsystem = rxn.subsystem or "Unknown"
    flux_val = abs(fba_fluxes.get(rxn.id, 0.0))
    pathway_flux[subsystem] = pathway_flux.get(subsystem, 0.0) + flux_val

pathway_df = (pd.Series(pathway_flux, name="total_abs_flux")
              .sort_values(ascending=False)
              .reset_index()
              .rename(columns={"index": "subsystem"}))

pathway_df.to_csv("pathway_flux_summary.csv", index=False)

# Bar chart of top 15 pathways
top15 = pathway_df.head(15)
fig, ax = plt.subplots(figsize=(10, 6))
ax.barh(top15["subsystem"][::-1], top15["total_abs_flux"][::-1],
        color="steelblue")
ax.set_xlabel("Sum of |flux| (mmol/gDW/h)")
ax.set_title("Top 15 Pathway Activities (FBA)")
fig.tight_layout()
fig.savefig("pathway_activity.pdf", dpi=300)
plt.close(fig)
print("Pathway activity chart saved.")
```

### Step 7 — Secretion Product Prediction

Identify exchange reactions carrying positive flux (secretion) at optimal
growth — these are by-products and potential products of interest.

```python
secretion = {}

for rxn in model.exchanges:
    flux = fba_fluxes.get(rxn.id, 0.0)
    if flux > 1e-6:   # positive = secretion
        met = list(rxn.metabolites)[0]
        secretion[rxn.id] = {
            "metabolite": met.name,
            "formula": met.formula,
            "flux_mmol_gDW_h": flux,
        }

sec_df = pd.DataFrame(secretion).T.sort_values("flux_mmol_gDW_h",
                                                ascending=False)
print("\nSecreted products:")
print(sec_df.to_string())
sec_df.to_csv("secretion_profile.csv")
```

---

## Key Conventions

| Analysis | Lethality Threshold | Standard Reference |
|---|---|---|
| Single gene deletion | growth < 5% WT | Joyce & Palsson, 2006 |
| Double gene deletion (synthetic lethal) | growth < 5% WT | Deutscher et al., 2008 |
| Reaction deletion | growth < 5% WT | Consistent with gene deletion |
| PPP nutrient grid | 0–20 mmol/gDW/h, 50 steps | COBRApy default |
| Flux sampling (OptGP) | n = 1000, thinning = 100 | Megchelenbrink et al., 2014 |

### Output File Conventions

| File | Content |
|---|---|
| `gene_essentiality.csv` | Per-gene growth fraction and essentiality flag |
| `double_gene_essentiality.csv` | Pairwise synthetic lethality matrix |
| `reaction_essentiality.csv` | Per-reaction growth fraction and essentiality flag |
| `phenotypic_phase_plane.pdf` | 2D heatmap of growth vs. two nutrients |
| `flux_samples.csv` | Raw 1000-sample flux matrix |
| `flux_sampling_violin.pdf` | Violin plot of key reaction distributions |
| `pathway_flux_summary.csv` | Total absolute flux per metabolic subsystem |
| `pathway_activity.pdf` | Bar chart of top 15 active pathways |
| `secretion_profile.csv` | All secreted by-products at optimal growth |

### Common Failure Modes

- **PPP returns all zeros**: objective reaction ID does not match model; check
  `model.objective.expression` for correct reaction ID.
- **Flux sampling ACHR crashes**: `optgp` (default) is more stable for large
  models; for models with >5000 reactions use `processes=1` to debug.
- **No secretion products**: model may be forced to be strictly aerobic with
  all carbon converted to CO2; verify exchange bounds allow secretion
  (`ub = 1000` on exchange reactions).
