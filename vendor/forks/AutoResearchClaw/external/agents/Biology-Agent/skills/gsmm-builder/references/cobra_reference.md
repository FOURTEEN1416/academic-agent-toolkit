# COBRApy API Reference

## Core API Methods

| Method | Signature | Description |
|---|---|---|
| `load_json_model` | `cobra.io.load_json_model(filename)` | Load model from JSON file |
| `read_sbml_model` | `cobra.io.read_sbml_model(filename)` | Load model from SBML/XML file |
| `save_json_model` | `cobra.io.save_json_model(model, filename)` | Serialize model to JSON |
| `write_sbml_model` | `cobra.io.write_sbml_model(model, filename)` | Serialize model to SBML |
| `model.optimize` | `model.optimize(objective_sense="maximize")` | Run FBA, returns Solution |
| `flux_variability_analysis` | `cobra.flux_analysis.flux_variability_analysis(model, fraction_of_optimum=0.9)` | Return min/max flux range for each reaction |
| `pfba` | `cobra.flux_analysis.pfba(model)` | Parsimonious FBA (minimize total flux) |
| `single_gene_deletion` | `cobra.flux_analysis.single_gene_deletion(model)` | Compute growth after each single gene KO |
| `double_gene_deletion` | `cobra.flux_analysis.double_gene_deletion(model, gene_list1, gene_list2)` | Compute growth for all pairwise gene KOs |
| `single_reaction_deletion` | `cobra.flux_analysis.single_reaction_deletion(model)` | Compute growth after each single reaction KO |
| `production_envelope` | `cobra.flux_analysis.production_envelope(model, reactions, objective=None, points=20)` | Growth envelope / phenotype phase plane over one or two reaction axes |
| `sample` | `cobra.sampling.sample(model, n, method="optgp")` | Sample feasible flux distributions |
| `check_mass_balance` | `reaction.check_mass_balance()` | Returns dict of unbalanced elements (empty = balanced) |

## Solution Object Fields

```python
solution = model.optimize()

solution.status          # "optimal", "infeasible", "unbounded"
solution.objective_value # float, e.g. 0.982 h^-1 growth rate
solution.fluxes          # pd.Series indexed by reaction ID
solution.shadow_prices   # pd.Series indexed by metabolite ID (dual variables)
solution.reduced_costs   # pd.Series indexed by reaction ID
```

## BIGG Database Conventions

### Metabolite Naming
- Format: `<bigg_base_id>_<compartment>`
- Double underscore separates stereo/charge disambiguators: `glc__D_c` (D-glucose in cytosol)
- Common suffixes: `_c` (cytosol), `_e` (extracellular), `_m` (mitochondria), `_p` (periplasm), `_n` (nucleus), `_r` (ER), `_x` (peroxisome)

### Reaction Naming
- Exchange reactions: `EX_<metabolite_bigg_id>` e.g. `EX_glc__D_e`
- Transport reactions: metabolite abbreviation + `t` or `t2` e.g. `GLCt`, `PYRt2`
- Enzymatic reactions: enzyme abbreviation e.g. `PFK` (phosphofructokinase), `PGI` (phosphoglucose isomerase)
- Demand reactions: `DM_<metabolite_id>` — sink reactions for testing
- Sink reactions: `SK_<metabolite_id>` — allow metabolite accumulation

### Exchange Reaction Sign Convention

```
EX_glc__D_e: { glc__D_e: 1 }

lower_bound = -10  →  net uptake of 10 mmol/gDW/h  (glucose consumed)
lower_bound =   0  →  no uptake allowed
upper_bound =   0  →  no secretion allowed
upper_bound = 1000 →  unlimited secretion
```

This single-metabolite convention means:
- **Negative flux = uptake** (metabolite flows into the cell)
- **Positive flux = secretion** (metabolite flows out of the cell)

## Common Medium Definitions

### M9 Minimal Medium (Aerobic, Glucose)

```python
M9_GLUCOSE_AEROBIC = {
    "EX_glc__D_e":  -10.0,   # glucose, 10 mmol/gDW/h
    "EX_o2_e":      -20.0,   # oxygen
    "EX_nh4_e":  -1000.0,    # ammonium (unlimited)
    "EX_pi_e":   -1000.0,    # inorganic phosphate (unlimited)
    "EX_so4_e":  -1000.0,    # sulfate (unlimited)
    "EX_h2o_e":  -1000.0,    # water (unlimited)
    "EX_h_e":    -1000.0,    # protons (unlimited)
    "EX_co2_e":  -1000.0,    # CO2 (allow uptake for autotrophs)
    "EX_fe2_e":  -1000.0,    # iron(II) (unlimited)
    "EX_mg2_e":  -1000.0,    # magnesium (unlimited)
    "EX_k_e":    -1000.0,    # potassium (unlimited)
    "EX_na1_e":  -1000.0,    # sodium (unlimited)
}
```

### M9 Minimal Medium (Anaerobic, Glucose)

```python
M9_GLUCOSE_ANAEROBIC = {
    **M9_GLUCOSE_AEROBIC,
    "EX_o2_e": 0.0,          # no oxygen
}
```

### LB Rich Medium (Aerobic)

```python
# LB approximation: open all exchange reactions
LB_RICH_AEROBIC = {rxn.id: -1000.0
                   for rxn in model.exchanges
                   if rxn.id != "EX_o2_e"}
LB_RICH_AEROBIC["EX_o2_e"] = -20.0
```

### Glucose-Xylose Co-utilization (Aerobic)

```python
GLUCOSE_XYLOSE_AEROBIC = {
    **M9_GLUCOSE_AEROBIC,
    "EX_xyl__D_e": -10.0,   # xylose, 10 mmol/gDW/h
}
```

## Context Manager for Temporary Perturbations

```python
# Temporarily knock out a reaction without modifying the model permanently
with model:
    model.reactions.get_by_id("PFK").knock_out()
    ko_solution = model.optimize()
    print(ko_solution.objective_value)
# Model is restored here
```

## Installation

```bash
pip install cobra
pip install cobra[all]       # includes optional solvers
conda install -c conda-forge cobra
```

## Default Solver Priority

COBRApy tries solvers in this order: `glpk_exact`, `glpk`, `cplex`, `gurobi`.
Set explicitly:

```python
model.solver = "glpk"      # open-source, always available
model.solver = "cplex"     # commercial, fastest for large models
model.solver = "gurobi"    # commercial, alternative high-performance
```
