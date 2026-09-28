"""
Minimal 3-reaction toy glycolysis model built from scratch using COBRApy.

Reactions:
  EX_glc__D_e : glucose exchange (uptake)
  GLYCOLYSIS   : glucose → 2 ATP  (simplified)
  BIOMASS      : 10 ATP → biomass  (growth)

Usage:
  python minimal_model.py

Outputs:
  minimal_model.json   — serialized COBRApy model
  fba_solution.csv     — flux distribution at optimal growth
"""

from pathlib import Path

import cobra
import cobra.io
from cobra import Metabolite, Model, Reaction


# ---------------------------------------------------------------------------
# 1. Define metabolites
# ---------------------------------------------------------------------------

def build_metabolites() -> dict:
    """Return a dict of Metabolite objects keyed by their BIGG IDs."""
    return {
        "glc__D_e": Metabolite(
            "glc__D_e",
            formula="C6H12O6",
            name="D-Glucose (extracellular)",
            compartment="e",
            charge=0,
        ),
        "glc__D_c": Metabolite(
            "glc__D_c",
            formula="C6H12O6",
            name="D-Glucose (cytosol)",
            compartment="c",
            charge=0,
        ),
        "atp_c": Metabolite(
            "atp_c",
            formula="C10H12N5O13P3",
            name="ATP",
            compartment="c",
            charge=-4,
        ),
        "adp_c": Metabolite(
            "adp_c",
            formula="C10H12N5O10P2",
            name="ADP",
            compartment="c",
            charge=-3,
        ),
        "h_c": Metabolite(
            "h_c",
            formula="H",
            name="H+",
            compartment="c",
            charge=1,
        ),
        "pi_c": Metabolite(
            "pi_c",
            formula="HO4P",
            name="Phosphate",
            compartment="c",
            charge=-2,
        ),
        "biomass_c": Metabolite(
            "biomass_c",
            formula="",
            name="Biomass",
            compartment="c",
            charge=0,
        ),
    }


# ---------------------------------------------------------------------------
# 2. Define reactions
# ---------------------------------------------------------------------------

def build_reactions(mets: dict) -> list:
    """Return a list of Reaction objects with stoichiometry assigned."""

    # --- Exchange: glucose uptake from environment ---
    ex_glc = Reaction("EX_glc__D_e")
    ex_glc.name = "D-Glucose exchange"
    ex_glc.lower_bound = -10.0   # uptake: 10 mmol/gDW/h
    ex_glc.upper_bound = 1000.0  # allow secretion (no reason to block)
    # Sign convention: positive stoichiometry, negative flux = net uptake
    ex_glc.add_metabolites({mets["glc__D_e"]: 1.0})

    # --- Transport: extracellular glucose → cytosol ---
    glc_transport = Reaction("GLCt")
    glc_transport.name = "Glucose transport (simplified)"
    glc_transport.lower_bound = -1000.0
    glc_transport.upper_bound = 1000.0
    glc_transport.add_metabolites({
        mets["glc__D_e"]: -1.0,
        mets["glc__D_c"]:  1.0,
    })

    # --- Glycolysis: glucose + 2 ADP + 2 Pi → 2 ATP (net, simplified) ---
    # Real glycolysis: C6H12O6 + 2 ADP + 2 Pi → 2 pyruvate + 2 ATP + 2 H2O
    # Here we collapse to ATP production only for a toy model.
    glycolysis = Reaction("GLYCOLYSIS")
    glycolysis.name = "Glycolysis (simplified, glucose → ATP)"
    glycolysis.lower_bound = 0.0
    glycolysis.upper_bound = 1000.0
    glycolysis.add_metabolites({
        mets["glc__D_c"]: -1.0,  # consume 1 glucose
        mets["adp_c"]:    -2.0,  # consume 2 ADP
        mets["pi_c"]:     -2.0,  # consume 2 phosphate
        mets["atp_c"]:     2.0,  # produce 2 ATP  (net)
        mets["h_c"]:       2.0,  # produce 2 H+
    })

    # --- ATP maintenance demand ---
    atp_maintenance = Reaction("ATPM")
    atp_maintenance.name = "ATP maintenance (non-growth associated)"
    atp_maintenance.lower_bound = 3.15   # typical iJO1366 value (mmol/gDW/h)
    atp_maintenance.upper_bound = 1000.0
    atp_maintenance.add_metabolites({
        mets["atp_c"]: -1.0,
        mets["h2o_c"] if "h2o_c" in mets else mets["adp_c"]: 0.0,  # placeholder
        mets["adp_c"]:  1.0,
        mets["pi_c"]:   1.0,
        mets["h_c"]:    1.0,
    })
    # Simplify: just drain ATP with no water (mass imbalance acceptable in toy)
    atp_maintenance = Reaction("ATPM")
    atp_maintenance.name = "ATP maintenance demand"
    atp_maintenance.lower_bound = 0.0
    atp_maintenance.upper_bound = 1000.0
    atp_maintenance.add_metabolites({
        mets["atp_c"]: -1.0,
        mets["adp_c"]:  1.0,
        mets["pi_c"]:   1.0,
    })

    # --- Biomass: ATP consumption → biomass accumulation ---
    biomass_rxn = Reaction("BIOMASS")
    biomass_rxn.name = "Biomass production (growth objective)"
    biomass_rxn.lower_bound = 0.0
    biomass_rxn.upper_bound = 1000.0
    # Each unit of biomass costs 10 ATP (arbitrary toy coefficient)
    biomass_rxn.add_metabolites({
        mets["atp_c"]:     -10.0,
        mets["adp_c"]:      10.0,
        mets["pi_c"]:       10.0,
        mets["biomass_c"]:   1.0,
    })

    # --- Exchange: ADP/Pi not tracked separately; add demand reactions ---
    adp_demand = Reaction("DM_adp_c")
    adp_demand.name = "ADP demand (sink)"
    adp_demand.lower_bound = 0.0
    adp_demand.upper_bound = 1000.0
    adp_demand.add_metabolites({mets["adp_c"]: -1.0})

    pi_demand = Reaction("DM_pi_c")
    pi_demand.name = "Phosphate demand (sink)"
    pi_demand.lower_bound = 0.0
    pi_demand.upper_bound = 1000.0
    pi_demand.add_metabolites({mets["pi_c"]: -1.0})

    h_demand = Reaction("DM_h_c")
    h_demand.name = "H+ demand (sink)"
    h_demand.lower_bound = 0.0
    h_demand.upper_bound = 1000.0
    h_demand.add_metabolites({mets["h_c"]: -1.0})

    return [ex_glc, glc_transport, glycolysis, atp_maintenance,
            biomass_rxn, adp_demand, pi_demand, h_demand]


# ---------------------------------------------------------------------------
# 3. Assemble model
# ---------------------------------------------------------------------------

def build_model() -> cobra.Model:
    model = Model("toy_glycolysis")
    model.name = "Minimal Glycolysis Toy Model"

    mets = build_metabolites()
    rxns = build_reactions(mets)
    model.add_reactions(rxns)

    # Set biomass as the objective (maximize)
    model.objective = "BIOMASS"

    return model


# ---------------------------------------------------------------------------
# 4. Validate and run FBA
# ---------------------------------------------------------------------------

def validate_and_run(model: cobra.Model) -> cobra.Solution:
    print(f"\nModel: {model.id}")
    print(f"  Reactions   : {len(model.reactions)}")
    print(f"  Metabolites : {len(model.metabolites)}")
    print(f"  Genes       : {len(model.genes)}")

    # Check mass balance on key reactions
    print("\nMass balance check:")
    for rxn in model.reactions:
        imbalance = rxn.check_mass_balance()
        status = "OK" if not imbalance else f"IMBALANCED {imbalance}"
        print(f"  {rxn.id:<20} {status}")

    # Run FBA
    solution = model.optimize()
    print(f"\nFBA result:")
    print(f"  Status          : {solution.status}")
    print(f"  Objective value : {solution.objective_value:.4f} h^-1")

    if solution.status == "optimal":
        print("\nNon-zero fluxes:")
        for rxn_id, flux in solution.fluxes.items():
            if abs(flux) > 1e-6:
                print(f"  {rxn_id:<20} {flux:>10.4f} mmol/gDW/h")

    return solution


# ---------------------------------------------------------------------------
# 5. Export
# ---------------------------------------------------------------------------

def export_model(model: cobra.Model, solution: cobra.Solution,
                 output_dir: str = ".") -> None:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    model_path = out / "minimal_model.json"
    cobra.io.save_json_model(model, str(model_path))
    print(f"\nModel saved to: {model_path}")

    if solution.status == "optimal":
        csv_path = out / "fba_solution.csv"
        solution.fluxes.to_csv(str(csv_path), header=["flux_mmol_gDW_h"])
        print(f"FBA solution saved to: {csv_path}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    model = build_model()
    solution = validate_and_run(model)
    export_model(model, solution, output_dir="output")
