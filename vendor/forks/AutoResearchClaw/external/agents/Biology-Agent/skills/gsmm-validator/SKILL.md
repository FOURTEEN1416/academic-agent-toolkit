---
name: gsmm-validator
description: >
  Validate a COBRApy genome-scale metabolic model for mass/charge balance,
  stoichiometric consistency, biomass producibility, dead-end metabolites,
  thermodynamic loops, and GPR rule formatting. Outputs a structured
  validation report with errors and warnings.
metadata:
  category: domain
  trigger-keywords: "metabolic,COBRApy,model validation,mass balance,charge balance,dead-end metabolites,biomass growth,thermodynamic loops,GPR"
  applicable-stages: "9,10,12,13,14,20"
  priority: "2"
---

## Overview

The `gsmm-validator` skill performs rigorous quality control on a COBRApy
`Model` before it enters any flux analysis pipeline. An invalid model
silently produces biologically meaningless fluxes; validation catches
structural errors early.

Validation covers six categories: (1) mass/charge balance, (2) feasibility
and biomass production, (3) dead-end metabolites, (4) stoichiometric
consistency, (5) thermodynamic loop detection, and (6) GPR rule integrity.

---

## Workflow

### Step 1 — Load the Model

```python
import cobra
import cobra.io

model = cobra.io.load_json_model("my_model.json")
print(f"Loaded: {model.id} ({len(model.reactions)} reactions)")
```

### Step 2 — Mass and Charge Balance Check

Unbalanced reactions are among the most common modelling errors. COBRApy
computes elemental balance per reaction.

```python
errors = []
warnings = []

print("=== Mass/Charge Balance ===")
for rxn in model.reactions:
    # Returns dict like {"C": -1, "H": 2} if imbalanced; empty dict if OK
    imbalance = rxn.check_mass_balance()
    if imbalance:
        # Exchange and demand reactions are expected to be imbalanced
        if rxn.id.startswith(("EX_", "DM_", "SK_", "BIOMASS")):
            warnings.append(f"WARN  [{rxn.id}] boundary reaction imbalanced "
                            f"(expected): {imbalance}")
        else:
            errors.append(f"ERROR [{rxn.id}] mass/charge imbalance: "
                          f"{imbalance}")

for msg in errors + warnings:
    print(msg)
print(f"  {len(errors)} error(s), {len(warnings)} warning(s)")
```

### Step 3 — Biomass Producibility (FBA Feasibility)

```python
print("\n=== Biomass Producibility ===")
solution = model.optimize()

if solution.status != "optimal":
    errors.append(f"ERROR Model is {solution.status} — "
                  f"cannot produce biomass under current medium.")
    print(f"  FAIL: {solution.status}")
elif solution.objective_value < 1e-6:
    errors.append("ERROR Growth rate is effectively zero "
                  "(< 1e-6 h^-1). Check medium and objective reaction.")
    print(f"  FAIL: growth = {solution.objective_value:.6f} h^-1")
else:
    print(f"  PASS: growth = {solution.objective_value:.4f} h^-1")
```

### Step 4 — Dead-End Metabolite Detection

A metabolite is a dead-end if it is produced by at least one reaction but
consumed by none, or vice versa. Dead-ends create infeasibility in network
regions.

```python
from cobra.manipulation import find_blocked_reactions

print("\n=== Dead-End Metabolites ===")
dead_end_mets = []

for met in model.metabolites:
    producers = [r for r in met.reactions
                 if r.get_coefficient(met) > 0]
    consumers = [r for r in met.reactions
                 if r.get_coefficient(met) < 0]

    if producers and not consumers:
        dead_end_mets.append((met.id, "produced but never consumed"))
    elif consumers and not producers:
        dead_end_mets.append((met.id, "consumed but never produced"))

if dead_end_mets:
    for met_id, reason in dead_end_mets:
        warnings.append(f"WARN  [{met_id}] dead-end: {reason}")
    print(f"  {len(dead_end_mets)} dead-end metabolite(s) found")
else:
    print("  PASS: no dead-end metabolites")

for msg in warnings[-len(dead_end_mets):]:
    print(f"  {msg}")
```

### Step 5 — Blocked Reaction Detection

```python
from cobra.flux_analysis import find_blocked_reactions

print("\n=== Blocked Reactions ===")
blocked = find_blocked_reactions(model, open_exchanges=True)

if blocked:
    warnings.append(f"WARN  {len(blocked)} blocked reaction(s): "
                    f"{blocked[:5]} ...")
    print(f"  {len(blocked)} blocked reactions (cannot carry flux)")
else:
    print("  PASS: no blocked reactions")
```

### Step 6 — Thermodynamic Loop Detection (Loopless FBA)

Energy-generating cycles violate thermodynamics and inflate apparent fluxes.

```python
print("\n=== Thermodynamic Loops ===")
try:
    loopless_solution = cobra.flux_analysis.loopless_solution(model)
    standard_solution = model.optimize()

    # Compare objective values; large discrepancy suggests loop inflation
    delta = abs(loopless_solution.objective_value
                - standard_solution.objective_value)
    if delta > 0.01:
        warnings.append(
            f"WARN  Loop detected: standard FBA growth "
            f"{standard_solution.objective_value:.4f} vs loopless "
            f"{loopless_solution.objective_value:.4f} (delta={delta:.4f})"
        )
        print(f"  WARN: possible thermodynamic loops (delta={delta:.4f})")
    else:
        print(f"  PASS: no significant loops (delta={delta:.6f})")
except Exception as exc:
    warnings.append(f"WARN  Loopless FBA failed: {exc}")
    print(f"  SKIP: loopless FBA unavailable ({exc})")
```

### Step 7 — GPR Rule Validation

Gene-Protein-Reaction associations must use valid gene IDs and boolean logic.

```python
import re

print("\n=== GPR Rule Integrity ===")
all_gene_ids = {g.id for g in model.genes}
gpr_errors = []

for rxn in model.reactions:
    gpr = rxn.gene_reaction_rule
    if not gpr:
        continue  # spontaneous or non-enzymatic reactions are fine

    # Extract gene IDs referenced in GPR
    referenced = set(re.findall(r"[A-Za-z0-9_\-\.]+", gpr))
    # Remove boolean keywords
    referenced -= {"and", "or", "not", "AND", "OR", "NOT"}

    missing = referenced - all_gene_ids
    if missing:
        gpr_errors.append(f"ERROR [{rxn.id}] GPR references unknown genes: "
                          f"{missing}")

if gpr_errors:
    errors.extend(gpr_errors)
    print(f"  {len(gpr_errors)} GPR error(s)")
else:
    print("  PASS: all GPR rules reference valid gene IDs")
```

### Step 8 — Write Validation Report

```python
import json
from datetime import datetime

report = {
    "model_id": model.id,
    "timestamp": datetime.utcnow().isoformat() + "Z",
    "n_reactions": len(model.reactions),
    "n_metabolites": len(model.metabolites),
    "n_genes": len(model.genes),
    "growth_rate": (solution.objective_value
                    if solution.status == "optimal" else None),
    "status": "FAIL" if errors else "PASS",
    "errors": errors,
    "warnings": warnings,
}

with open("validation_report.json", "w") as f:
    json.dump(report, f, indent=2)

print(f"\n=== Summary ===")
print(f"  Status   : {report['status']}")
print(f"  Errors   : {len(errors)}")
print(f"  Warnings : {len(warnings)}")
print("  Report written to validation_report.json")
```

---

## Key Conventions

| Check | Failure Condition | Severity |
|---|---|---|
| Mass balance | Non-exchange reaction has elemental imbalance | ERROR |
| Biomass producibility | `solution.status != "optimal"` or growth < 1e-6 | ERROR |
| Dead-end metabolites | Produced but never consumed (or vice versa) | WARNING |
| Blocked reactions | Reaction carries zero flux under all conditions | WARNING |
| Thermodynamic loops | Standard FBA growth >> loopless FBA growth | WARNING |
| GPR integrity | GPR string references gene IDs not in `model.genes` | ERROR |

### Interpretation Guide

- **ERROR** — must fix before proceeding to FBA. These cause incorrect results.
- **WARNING** — may indicate incomplete reconstruction; investigate per case.
- Boundary reactions (`EX_`, `DM_`, `SK_`, `BIOMASS`) are excluded from mass
  balance errors because they intentionally have no counter-reaction.
- A model with only warnings is acceptable for exploratory FBA but should be
  corrected for publication-quality analysis.
