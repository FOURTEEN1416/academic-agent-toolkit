"""Biology domain prompt adapter.

Provides domain-specific prompt blocks for bioinformatics
experiments (single-cell analysis, genomics, protein science) and a
dedicated overlay for constraint-based metabolic modelling
(``biology_metabolic``) which targets the Biology-Agent (FBA / pFBA / FVA
via COBRApy + BIGG) execution backend.
"""

from __future__ import annotations

from typing import Any

from researchclaw.domains.prompt_adapter import PromptAdapter, PromptBlocks


class BiologyPromptAdapter(PromptAdapter):
    """Adapter for biology/bioinformatics domains (single-cell, genomics, protein)."""

    def get_code_generation_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        domain = self.domain

        return PromptBlocks(
            compute_budget=domain.compute_budget_guidance or (
                "Bioinformatics analyses can be memory-intensive:\n"
                "- Use small/subsampled datasets for testing\n"
                "- Single-cell: cap at 5000 cells for benchmarks\n"
                "- Genomics: use small chromosomes/regions"
            ),
            dataset_guidance=domain.dataset_guidance or (
                "Generate synthetic biological data in code:\n"
                "- Single-cell: use scanpy.datasets or simulate with splatter\n"
                "- Genomics: generate synthetic sequences\n"
                "- Do NOT download external datasets"
            ),
            hp_reporting=domain.hp_reporting_guidance or (
                "Report analysis parameters:\n"
                "HYPERPARAMETERS: {'n_cells': ..., 'n_genes': ..., "
                "'n_hvg': ..., 'n_pcs': ..., 'resolution': ...}"
            ),
            code_generation_hints=domain.code_generation_hints or self._default_hints(),
            output_format_guidance=(
                "Output results to results.json:\n"
                '{"conditions": {"method": {"ARI": 0.85, "NMI": 0.82}},\n'
                ' "metadata": {"domain": "biology_singlecell"}}'
            ),
        )

    def get_experiment_design_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        domain = self.domain

        design_context = (
            f"This is a **{domain.display_name}** experiment.\n\n"
            "Key principles:\n"
            "1. Proper preprocessing is critical (QC, normalization)\n"
            "2. Use standard evaluation metrics (ARI, NMI for clustering)\n"
            "3. Compare against established methods in the field\n"
            "4. Include sensitivity analysis for key parameters\n"
        )

        return PromptBlocks(
            experiment_design_context=design_context,
            statistical_test_guidance=(
                "Use Wilcoxon rank-sum test with FDR correction "
                "for differential expression. Use ARI/NMI for clustering."
            ),
        )

    def get_result_analysis_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks(
            result_analysis_hints=(
                "Biology result analysis:\n"
                "- Clustering: ARI, NMI, silhouette score\n"
                "- DE: number of DEGs at FDR < 0.05\n"
                "- Trajectory: pseudotime correlation\n"
                "- Report runtime alongside quality metrics"
            ),
        )

    def _default_hints(self) -> str:
        return (
            "Bioinformatics code requirements:\n"
            "1. Use scanpy for single-cell analysis\n"
            "2. Standard pipeline: load → QC → normalize → log1p → HVG → PCA → neighbors\n"
            "3. Compare clustering methods (Leiden, Louvain, K-means)\n"
            "4. Evaluate with ARI against known cell types\n"
            "5. Output results to results.json\n"
        )


# ---------------------------------------------------------------------------
# Constraint-based metabolic modelling overlay (Biology-Agent backend)
# ---------------------------------------------------------------------------


class BiologyMetabolicPromptAdapter(PromptAdapter):
    """Adapter for constraint-based metabolic modelling (FBA / pFBA / FVA).

    This overlay targets the Biology-Agent execution backend (COBRApy +
    BIGG via Claude Code). The narrative stage prompts live in
    :mod:`researchclaw.prompts.biology` (a thin bank that re-uses the ML
    bank for unmodified stages and overrides hypothesis_gen,
    experiment_design, code_generation, result_analysis and paper_outline
    with metabolic-modelling vocabulary).

    The three YAML-driven hooks below carry the COBRApy / BIGG /
    phenotypic-phase-plane / escher vocabulary so that downstream stages
    that consume `PromptBlocks` (rather than the bank directly) still see
    metabolic-modelling guidance.
    """

    def get_code_generation_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        domain = self.domain
        return PromptBlocks(
            compute_budget=domain.compute_budget_guidance or (
                "Constraint-based modelling compute envelope:\n"
                "- Single FBA / pFBA: < 1 s on a CPU\n"
                "- FVA over all reactions for a 2-3k-reaction GEM: < 5 min\n"
                "- Single-gene knockout screen for E. coli iJO1366 (~1.4k genes): < 10 min\n"
                "- Cap double-knockout / scan jobs at 100 conditions per run\n"
                "- Phenotypic phase-plane grid: ≤ 50 × 50 substrate-uptake combinations"
            ),
            dataset_guidance=domain.dataset_guidance or (
                "Use a published genome-scale metabolic model (GEM) — do NOT hand-roll a "
                "stoichiometric matrix:\n"
                "- E. coli: iJO1366 (1366 genes), iAF1260, iML1515\n"
                "- S. cerevisiae: iMM904, Yeast8\n"
                "- Human: Recon3D, Human-GEM\n"
                "Load via `cobra.io.load_model(<id>)` (BIGG fetch) or "
                "`cobra.io.read_sbml_model(path)`. Print the loaded model id, "
                "n_reactions, n_metabolites, n_genes."
            ),
            hp_reporting=domain.hp_reporting_guidance or (
                "Report all FBA / scan parameters:\n"
                "HYPERPARAMETERS: {'model_id': ..., 'objective': ..., 'medium': {...}, "
                "'fva_fraction_of_optimum': 0.95, 'solver': 'glpk', 'tolerance': 1e-7, "
                "'n_knockouts': ..., 'phase_plane_grid': [n_x, n_y]}"
            ),
            code_generation_hints=domain.code_generation_hints or self._default_metabolic_hints(),
            output_format_guidance=(
                "Output results to results.json with units encoded:\n"
                '{"wild_type_growth_rate_per_h": 0.982,\n'
                ' "objective_reaction": "BIOMASS_Ec_iJO1366_core_53p95M",\n'
                ' "medium": {"EX_glc__D_e": 10.0, "EX_o2_e": 18.5},\n'
                ' "essential_genes": ["b0001", "b0002", ...],\n'
                ' "knockout_growth_table": [{"gene": "b0001", "growth_per_h": 0.0, '
                '"ratio_to_wt": 0.0}, ...],\n'
                ' "metadata": {"domain": "biology_metabolic", "model_id": "iJO1366", '
                '"cobra_version": "..."}}'
            ),
        )

    def get_experiment_design_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        domain = self.domain
        design_context = (
            f"This is a **{domain.display_name}** in-silico experiment.\n\n"
            "Design principles for constraint-based modelling:\n"
            "1. **Pick a published GEM** that matches the organism (BIGG / "
            "BioModels). State its id, version, and reference.\n"
            "2. **Define the medium explicitly** — exchange-reaction bounds drive "
            "every downstream answer. Mirror the experimental medium "
            "(M9, MOPS, YPD, ...).\n"
            "3. **State the objective.** Biomass for growth questions; demand or "
            "exchange reaction for product-yield questions.\n"
            "4. **FBA → pFBA → FVA pipeline.** Always run all three at the "
            "wild-type optimum so flux variability is quantified, not just the "
            "single optimal flux distribution.\n"
            "5. **Knockout / perturbation screens.** Use `with model:` blocks "
            "and `gene.knock_out()`. Report KO growth-rate ratio relative to "
            "wild-type. Cap the screen at 100 single KOs (or ≤ 50 doubles) per "
            "run unless explicitly requested.\n"
            "6. **Phenotypic phase planes.** Sweep two exchange fluxes "
            "(e.g. glucose vs oxygen) on a ≤ 50×50 grid. Plot the optimal "
            "biomass surface — this is the canonical FBA figure.\n"
            "7. **Compare against an experimental reference** "
            "(Keio / OGEE essentiality, Edwards-Palsson phase-plane data, "
            "13C-MFA fluxes when available).\n"
        )
        return PromptBlocks(
            experiment_design_context=design_context,
            statistical_test_guidance=(
                "Use **flux variability analysis** to bound each flux at "
                "fraction_of_optimum ≥ 0.95. Use **Monte Carlo flux sampling** "
                "(`cobra.sampling.sample`) for posterior-style flux distributions. "
                "Use a **hypergeometric test** for essential-gene enrichment in "
                "a pathway / subsystem. Bootstrap 95% CIs on growth-rate "
                "predictions when comparing strains."
            ),
        )

    def get_result_analysis_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        return PromptBlocks(
            result_analysis_hints=(
                "Constraint-based modelling result analysis:\n"
                "- Wild-type growth rate (1/h) — compare to measured doubling time "
                "(t_d = ln 2 / mu). Flag > 30% disagreement.\n"
                "- Phenotypic phase plane — overlay the optimal-biomass surface "
                "and the line of optimality (LO). Identify futile / dual-substrate "
                "regions.\n"
                "- Gene-essentiality table — report precision / recall vs Keio "
                "(E. coli) or comparable curated set. Flag false positives "
                "(model essential, organism viable) for missing isoenzymes / "
                "transport reactions.\n"
                "- FVA envelope — width of [v_min, v_max] at fraction_of_optimum "
                "0.95 indicates flux flexibility; near-zero width = uniquely "
                "constrained reaction.\n"
                "- Knockout heatmap — rows = genes, columns = media; colour = "
                "growth_rate_KO / growth_rate_WT.\n"
                "- Always report **units** (mmol/gDW/h for fluxes, 1/h for "
                "growth, dimensionless for ratios).\n"
                "- Generate at least one Escher map for the headline pathway "
                "(`escher.Builder(map_name=..., reaction_data=...)`)."
            ),
        )

    def get_export_publish_blocks(self, context: dict[str, Any]) -> PromptBlocks:
        guidance = (
            "This is a constraint-based metabolic modelling manuscript. The "
            "export pass must preserve COBRApy / BIGG terminology, GEM "
            "identifiers (e.g. iJO1366), explicit flux units (mmol/gDW/h, 1/h), "
            "and citations to the original genome-scale model papers. Do NOT "
            "insert NeurIPS checklists, broader-impact paragraphs, or "
            "ML-leaderboard tables during final formatting."
        )
        return PromptBlocks(
            export_publish_guidance=guidance,
            preferred_template="nature_methods",
        )

    @staticmethod
    def _default_metabolic_hints() -> str:
        return (
            "Constraint-based metabolic modelling code requirements:\n"
            "1. Load a published GEM via COBRApy (BIGG `cobra.io.load_model` "
            "or `cobra.io.read_sbml_model`).\n"
            "2. Set the medium explicitly through `model.medium = {...}` and "
            "print the dict.\n"
            "3. Set the biomass reaction (or product demand) as the objective.\n"
            "4. Run FBA → pFBA → FVA at the optimum and reconcile growth rates.\n"
            "5. Perform knockouts inside `with model:` contexts using "
            "`model.genes.<gene>.knock_out()`.\n"
            "6. Persist outputs to results.json with explicit units in field names.\n"
            "7. Render at least a phenotypic phase plane and an Escher map.\n"
        )
