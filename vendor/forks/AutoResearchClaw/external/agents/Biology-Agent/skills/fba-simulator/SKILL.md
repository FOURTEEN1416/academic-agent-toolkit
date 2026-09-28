---
name: fba-simulator
description: >
  Run Flux Balance Analysis (FBA) and related constraint-based simulations
  using COBRApy. Covers standard FBA, parsimonious FBA (pFBA), Flux
  Variability Analysis (FVA), loopless FBA, gene/reaction knockouts, and
  carbon source swapping. Outputs flux distributions and CSV files.
metadata:
  category: domain
  trigger-keywords: "metabolic,FBA,pFBA,FVA,Flux Balance Analysis,COBRApy,knockout,carbon source,medium swap,flux distribution,growth rate"
  applicable-stages: "9,10,11,12,13,14,15"
  priority: "1"
---

## Overview

The `fba-simulator` skill executes constraint-based metabolic simulations on
a validated COBRApy model. FBA solves a linear program to find the flux
distribution that maximizes (or minimizes) the objective function subject to
stoichiometric and thermodynamic constraints.

This skill sits between model construction (`gsmm-builder`) and biological
interpretation (`flux-analyzer`). All simulations are non-destructive: COBRApy
context managers restore model state after each perturbation.

---

## Workflow

### Step 1 — Load Validated Model

```python
import cobra
import cobra.io
import cobra.flux_analysis
import pandas as pd

model = cobra.io.load_json_model("my_model.json")
print(f"Model: {model.id}  Solver: {model.solver}")
```

### Step 2 — Standard FBA

FBA maximizes the objective (typically biomass) subject to stoichiometric
steady-state constraints: `S·v = 0`, `lb ≤ v ≤ ub`.

```python
# Run FBA
solution = model.optimize()

print(f"Status          : {solution.status}")
print(f"Growth rate     : {solution.objective_value:.4f} h^-1")
print(f"Glucose uptake  : "
      f"{solution.fluxes['EX_glc__D_e']:.4f} mmol/gDW/h")
print(f"O2 uptake       : "
      f"{solution.fluxes.get('EX_o2_e', 0):.4f} mmol/gDW/h")
print(f"Acetate sec.    : "
      f"{solution.fluxes.get('EX_ac_e', 0):.4f} mmol/gDW/h")

# Save full flux distribution
solution.fluxes.to_csv("fba_fluxes.csv", header=["flux_mmol_gDW_h"])
```

### Step 3 — Parsimonious FBA (pFBA)

pFBA first maximizes growth, then minimizes total absolute flux, producing
the most "economical" solution consistent with maximum growth. This avoids
biologically unrealistic high-flux split cycles.

```python
pfba_solution = cobra.flux_analysis.pfba(model)

print(f"pFBA growth rate : {pfba_solution.objective_value:.4f} h^-1")
print(f"Total flux norm  : {pfba_solution.fluxes.abs().sum():.2f}")

pfba_solution.fluxes.to_csv("pfba_fluxes.csv", header=["flux_mmol_gDW_h"])
```

### Step 4 — Flux Variability Analysis (FVA)

FVA computes the minimum and maximum flux each reaction can carry while
maintaining at least `fraction_of_optimum` of the maximum growth rate. This
reveals which fluxes are uniquely determined vs. flexible.

```python
from cobra.flux_analysis import flux_variability_analysis

# FVA at 90% of maximum growth
fva_result = flux_variability_analysis(
    model,
    fraction_of_optimum=0.90,
    processes=4,          # parallel workers
)

# fva_result is a DataFrame with columns "minimum" and "maximum"
print(fva_result.head(10))

# Identify rigidly constrained reactions (min ≈ max)
TOLERANCE = 1e-6
rigid = fva_result[
    (fva_result["maximum"] - fva_result["minimum"]).abs() < TOLERANCE
]
print(f"\nRigid reactions (min=max): {len(rigid)}")

fva_result.to_csv("fva_result.csv")
```

### Step 5 — Loopless FBA

Standard FBA may route flux through thermodynamically infeasible energy-
generating cycles. Loopless FBA enforces thermodynamic feasibility.

```python
loopless_sol = cobra.flux_analysis.loopless_solution(model)

print(f"Loopless growth  : {loopless_sol.objective_value:.4f} h^-1")
loopless_sol.fluxes.to_csv("loopless_fluxes.csv",
                            header=["flux_mmol_gDW_h"])
```

### Step 6 — Gene Knockout Simulations

```python
# Single gene knockout (context manager — model is restored after)
gene_id = "b0720"  # pgi in E. coli iJO1366

with model:
    model.genes.get_by_id(gene_id).knock_out()
    ko_solution = model.optimize()
    print(f"KO {gene_id} growth: {ko_solution.objective_value:.4f} h^-1")

# Batch single gene deletions
from cobra.flux_analysis import single_gene_deletion

deletion_results = single_gene_deletion(model)
# Returns DataFrame: index = frozenset({gene_id}), columns = [growth, status]
deletion_results.to_csv("gene_deletions.csv")

# Essential genes: growth < 5% of wild-type
wt_growth = model.optimize().objective_value
essential = deletion_results[
    deletion_results["growth"] < 0.05 * wt_growth
]
print(f"\nEssential genes: {len(essential)}")
print(essential.head())
```

### Step 7 — Reaction Knockout Simulations

```python
from cobra.flux_analysis import single_reaction_deletion

rxn_deletion_results = single_reaction_deletion(model)
rxn_deletion_results.to_csv("reaction_deletions.csv")

essential_rxns = rxn_deletion_results[
    rxn_deletion_results["growth"] < 0.05 * wt_growth
]
print(f"Essential reactions: {len(essential_rxns)}")
```

### Step 8 — Carbon Source Swapping

```python
CARBON_SOURCES = {
    "glucose":   ("EX_glc__D_e", -10.0),
    "fructose":  ("EX_fru_e",    -10.0),
    "acetate":   ("EX_ac_e",     -10.0),
    "glycerol":  ("EX_glyc_e",   -10.0),
    "succinate": ("EX_succ_e",   -10.0),
}

results = []

for carbon, (rxn_id, bound) in CARBON_SOURCES.items():
    with model:
        # Close all carbon exchange reactions first
        for r in model.exchanges:
            if r.lower_bound < 0 and r.id != "EX_o2_e":
                r.lower_bound = 0.0

        # Open the target carbon source
        if rxn_id in model.reactions:
            model.reactions.get_by_id(rxn_id).lower_bound = bound
            sol = model.optimize()
            results.append({
                "carbon_source": carbon,
                "growth_rate": sol.objective_value,
                "status": sol.status,
            })
        else:
            results.append({
                "carbon_source": carbon,
                "growth_rate": None,
                "status": "reaction_not_in_model",
            })

carbon_df = pd.DataFrame(results)
print(carbon_df)
carbon_df.to_csv("carbon_source_comparison.csv", index=False)
```

### Step 9 — Aggregate and Save Results

```python
summary = {
    "model_id": model.id,
    "wt_growth_fba": wt_growth,
    "wt_growth_pfba": pfba_solution.objective_value,
    "wt_growth_loopless": loopless_sol.objective_value,
    "n_essential_genes": len(essential),
    "n_essential_reactions": len(essential_rxns),
}

import json
with open("simulation_summary.json", "w") as f:
    json.dump(summary, f, indent=2)
print("Summary written to simulation_summary.json")
```

---

## Key Conventions

| Parameter | Recommended Value | Rationale |
|---|---|---|
| `fraction_of_optimum` (FVA) | 0.9 | 10% growth slack — realistic variability |
| Essentiality threshold | growth < 5% WT | Standard in metabolic engineering |
| pFBA norm | L1 (sum abs fluxes) | COBRApy default; correlates with enzyme cost |
| Loopless FBA | Use for publication | Standard FBA may inflate central metabolism |
| `processes` (FVA) | 4 or CPU count | Scales near-linearly; avoid >8 for small models |

### Output File Conventions

| File | Content |
|---|---|
| `fba_fluxes.csv` | Standard FBA flux vector |
| `pfba_fluxes.csv` | pFBA flux vector (minimum total flux) |
| `fva_result.csv` | FVA minimum/maximum per reaction |
| `loopless_fluxes.csv` | Loopless-constrained flux vector |
| `gene_deletions.csv` | Growth rate for each single gene KO |
| `reaction_deletions.csv` | Growth rate for each single reaction KO |
| `carbon_source_comparison.csv` | Growth across different carbon sources |
| `simulation_summary.json` | Scalar summary of all simulation runs |

### Common Failure Modes

- **`solution.status = "infeasible"`**: medium is too restrictive or objective
  reaction bounds are wrong. Run `gsmm-validator` first.
- **Negative growth in pFBA**: can occur if `cobra.flux_analysis.pfba` is
  called on an infeasible model — always check `model.optimize()` first.
- **FVA hangs**: reduce `processes` or set `loopless=False`; large models
  (>10,000 reactions) may require HPC clusters.
- **Carbon source absent from model**: check BIGG ID spelling carefully;
  use `model.reactions.query("EX_")` to list available exchanges.
