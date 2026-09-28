---
name: gsmm-builder
description: >
  Build or load a genome-scale metabolic model (GSMM) using COBRApy.
  Covers loading from BIGG, constructing minimal models from scratch,
  setting medium constraints, and exporting validated .json model files.
metadata:
  category: domain
  trigger-keywords: "metabolic,metabolism,GSMM,COBRApy,COBRA,BIGG,genome-scale model,stoichiometric model,model loading,medium constraints"
  applicable-stages: "9,10,11,12,13"
  priority: "2"
---

## Overview

The `gsmm-builder` skill constructs or loads genome-scale metabolic models
(GSMMs) in the COBRApy framework. It is the entry point for every metabolic
flux analysis pipeline. Output is a validated COBRApy `Model` object
serialized to a JSON file ready for downstream FBA and flux analysis.

GSMMs encode every known metabolic reaction in an organism as a
stoichiometric matrix. Constraints (reaction bounds, medium composition,
objective function) turn the model into a solvable linear program.

---

## Workflow

### Step 1 — Decide: Load Existing or Build from Scratch

**Option A: Load a curated BIGG model**

```python
import cobra
import cobra.io

# Load E. coli iJO1366 from a local SBML file
model = cobra.io.read_sbml_model("iJO1366.xml")

# Or load from a pre-downloaded JSON file
model = cobra.io.load_json_model("iJO1366.json")

print(f"Loaded {model.id}: {len(model.reactions)} reactions, "
      f"{len(model.metabolites)} metabolites, {len(model.genes)} genes")
```

Key BIGG model IDs:
- `iJO1366` — *E. coli* K-12 MG1655 (2583 reactions)
- `Recon3D` — *Homo sapiens* (13543 reactions)
- `iMM904` — *S. cerevisiae* (1577 reactions)
- `iNJ661` — *M. tuberculosis* (1049 reactions)

**Option B: Build a minimal model from scratch**

```python
from cobra import Model, Metabolite, Reaction

model = Model("toy_glycolysis")

# Define metabolites with compartments and formula
glc_e = Metabolite("glc__D_e", formula="C6H12O6", name="D-Glucose",
                   compartment="e")
glc_c = Metabolite("glc__D_c", formula="C6H12O6", name="D-Glucose",
                   compartment="c")
atp_c = Metabolite("atp_c",  formula="C10H12N5O13P3", name="ATP",
                   compartment="c")
biomass = Metabolite("biomass", formula="", name="Biomass", compartment="c")

# Build reactions
ex_glc = Reaction("EX_glc__D_e")
ex_glc.lower_bound = -10.0  # uptake (negative = import)
ex_glc.upper_bound = 0.0
ex_glc.add_metabolites({glc_e: 1.0})

transport = Reaction("GLCt")
transport.lower_bound = -1000.0
transport.upper_bound = 1000.0
transport.add_metabolites({glc_e: -1.0, glc_c: 1.0})

# Stoichiometry: 1 glucose + ADP -> 2 ATP (simplified glycolysis)
glycolysis = Reaction("GLYCOLYSIS")
glycolysis.lower_bound = 0.0
glycolysis.upper_bound = 1000.0
glycolysis.add_metabolites({glc_c: -1.0, atp_c: 2.0})

biomass_rxn = Reaction("BIOMASS")
biomass_rxn.lower_bound = 0.0
biomass_rxn.upper_bound = 1000.0
biomass_rxn.add_metabolites({atp_c: -10.0, biomass: 1.0})

model.add_reactions([ex_glc, transport, glycolysis, biomass_rxn])
```

### Step 2 — Set the Objective Function

```python
# Set biomass as the optimization target
model.objective = "BIOMASS_Ec_iJO1366_core_53p95M"  # reaction ID string

# Verify objective is set
print(model.objective.to_json())
```

### Step 3 — Define the Growth Medium

```python
# M9 minimal medium with glucose (aerobic)
M9_MEDIUM = {
    "EX_glc__D_e": -10.0,   # glucose uptake, mmol/gDW/h
    "EX_o2_e":    -20.0,    # oxygen (aerobic)
    "EX_nh4_e":  -1000.0,   # ammonium (unlimited)
    "EX_pi_e":   -1000.0,   # phosphate (unlimited)
    "EX_so4_e":  -1000.0,   # sulfate (unlimited)
    "EX_h2o_e":  -1000.0,   # water (unlimited)
    "EX_h_e":    -1000.0,   # protons (unlimited)
}

# Apply medium: close all exchange reactions first, then open selected
medium = model.medium  # returns dict of current open exchange lb magnitudes
for rxn_id, lb in M9_MEDIUM.items():
    if rxn_id in model.reactions:
        model.reactions.get_by_id(rxn_id).lower_bound = lb

# Anaerobic: set O2 uptake to zero
# model.reactions.get_by_id("EX_o2_e").lower_bound = 0.0
```

### Step 4 — Export Model

```python
import cobra.io

cobra.io.save_json_model(model, "output/my_model.json")
cobra.io.write_sbml_model(model, "output/my_model.xml")
print("Model saved.")
```

---

## Key Conventions

| Convention | Detail |
|---|---|
| Metabolite ID format | `<bigg_id>_<compartment>` e.g. `glc__D_c`, `atp_m` |
| Compartment codes | `c` cytosol, `e` extracellular, `m` mitochondria, `n` nucleus |
| Exchange reaction prefix | `EX_` e.g. `EX_glc__D_e` |
| Transport reaction prefix | `t` or species-specific e.g. `GLCt`, `PGI` |
| Uptake bound sign | Negative lower bound = import (e.g. `lb = -10`) |
| Secretion bound sign | Positive upper bound = export (e.g. `ub = 1000`) |
| Biomass objective | Reaction with ID containing `BIOMASS` or `Growth` |
| Aerobic medium | `EX_o2_e` lb = -20 (mmol/gDW/h) |
| Anaerobic medium | `EX_o2_e` lb = 0 |
| Default irreversible rxn | `lb = 0, ub = 1000` |
| Default reversible rxn | `lb = -1000, ub = 1000` |

### BIGG Database Downloads

```bash
# Download model directly from BIGG REST API
curl -O "http://bigg.ucsd.edu/static/models/iJO1366.json"
curl -O "http://bigg.ucsd.edu/static/models/Recon3D.json"
```

### Common Failure Modes

- **Infeasible model**: missing exchange reaction or closed medium — run
  `model.optimize()` and check `solution.status == "infeasible"`.
- **Negative growth**: objective reaction direction inverted — ensure
  `biomass_rxn.lower_bound = 0`.
- **Dead-end metabolites**: metabolite produced but never consumed — run
  `gsmm-validator` before FBA.
