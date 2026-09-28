#!/usr/bin/env python3
"""Inject `requirements:` blocks into every physics manifest P01-P10.

Each topic gets the same 5 must_pass generic requirements (results.json
schema, metrics presence, hypothesis flags, figure artifact, model
implementation) plus 1 topic-specific must_pass derived from the topic's
H1, plus 2 optional must_pass=false items (mechanistic writeup, MC
reproducibility info).

Idempotent: skips topics that already declare a requirements: block.
"""

from __future__ import annotations
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent / "config" / "physics" / "manifests"

# Topic-specific must_pass requirement derived from each topic's H1.
# (Description text is what the LLM judge will grade against.)
TOPIC_SPECIFIC: dict[str, dict[str, str]] = {
    "P01": {
        "id": "req_kk1_peak_position",
        "description": (
            "results.json metrics MUST report a numeric `peak_position_gev` (or "
            "equivalent first-KK-resonance position) within ±5% of 600 GeV — i.e. "
            "in the interval [570, 630] GeV — after the RS scan over √s ∈ "
            "{200..1200} GeV."
        ),
    },
    "P02": {
        "id": "req_xsec_at_mN_200",
        "description": (
            "results.json metrics MUST report a numeric "
            "`sigma_pp_to_muN_at_mN200_14TeV_fb` (or equivalent) within ±30% of "
            "the published reference value at m_N=200 GeV, √s=14 TeV."
        ),
    },
    "P03": {
        "id": "req_g1prime_threshold",
        "description": (
            "results.json metrics MUST report the g1' coordinate where the 2σ "
            "exclusion contour at M_Z'=2 TeV crosses the g̃=0 axis, in the "
            "interval [0.07, 0.26] (i.e. published [0.10, 0.20] ±30%)."
        ),
    },
    "P04": {
        "id": "req_xsec_Zprime_2TeV",
        "description": (
            "results.json metrics MUST report `sigma_pp_to_Zprime_2TeV_panelA_fb` "
            "(at M_Z'=2 TeV, g̃=0, g1'=0.10) within ±30% of the published "
            "Panel A reference cross section."
        ),
    },
    "P05": {
        "id": "req_met_peak_bin",
        "description": (
            "results.json metrics MUST report the peak bin of the normalized "
            "E_T^miss distribution; the bin center must lie in [100, 250] GeV "
            "and the distribution must integrate to 1.0 (normalized)."
        ),
    },
    "P06": {
        "id": "req_lq_coupling_band",
        "description": (
            "results.json metrics MUST report the 2σ combined ATLAS+CMS "
            "√(g_c* g_b) exclusion band at M_U1=1 TeV; the band lower edge "
            "must be in [0.21, 0.39] and the upper edge in [1.05, 1.95] "
            "(published [0.3, 1.5] ±30%)."
        ),
    },
    "P07": {
        "id": "req_mej_peak_position",
        "description": (
            "results.json metrics MUST report the reconstructed m_ej peak "
            "position (after Pythia8+Delphes smearing) in the interval "
            "[2850, 3150] GeV (input M_LQ=3 TeV ±5%)."
        ),
    },
    "P08": {
        "id": "req_ssm_psi_ratio",
        "description": (
            "results.json metrics MUST report the ratio σ_SSM/σ_ψ at M_Z'=2 TeV, "
            "√s=13 TeV, and that ratio MUST be in [3, 30]."
        ),
    },
    "P09": {
        "id": "req_central_bin_excess",
        "description": (
            "results.json metrics MUST report the normalized central-|η|<0.1 "
            "fraction for β_L^32=1.0, m_LQ=1 TeV, AND the same fraction for SM, "
            "AND the LQ fraction MUST exceed SM by ≥50%."
        ),
    },
    "P10": {
        "id": "req_14tev_excl_reach",
        "description": (
            "results.json metrics MUST report the 95% CL exclusion β_L^32 reach "
            "at m_LQ=10 TeV, √s=14 TeV, 20 ab^-1; the value MUST be ≤ 0.02 "
            "(published ≤0.01 within a factor of 2)."
        ),
    },
}

GENERIC_BLOCK = """
# ---------------------------------------------------------------------------
# Agent-mode requirements (consumed by researchclaw.pipeline.requirements_judge
# at stage 15 RESEARCH_DECISION). Schema mirrors B01.yaml:
#   id          — stable identifier
#   type        — advisory hint to the LLM judge (numeric | artifact | discussion)
#   description — natural-language statement of what must be true post-run
#   must_pass   — true → unmet ⇒ rerun (1 retry max); false → optional
#
# The five generic must_pass items apply uniformly across P01-P10; the sixth
# is topic-specific (mirrors this manifest's H1).  The two must_pass=false
# items reward mechanistic interpretation and MC-reproducibility metadata
# without blocking proceed-vs-rerun on them.
# ---------------------------------------------------------------------------
requirements:
  - id: req_results_json
    type: artifact
    description: >-
      A canonical results.json file exists at the workspace root with at least
      the keys: primary_metric (number), metric_key (string), metrics (object
      with numeric keys), hypotheses (object with h1/h2/h3 entries each
      carrying a `supported` boolean), summary (non-empty string).
    must_pass: true

  - id: req_metrics_numeric
    type: numeric
    description: >-
      results.json metrics MUST contain at least 3 numeric (non-null, finite)
      values directly relevant to the headline physics observable named in
      the experiment_design.metrics list above — these are the numbers the
      paper will report in its Results section.
    must_pass: true

  - id: req_hypotheses_supported_flags
    type: discussion
    description: >-
      results.json hypotheses.h1/h2/h3 each MUST have an explicit `supported`
      boolean AND a `details` string ≥ 40 characters quoting the numerical
      evidence (specific values + their source artifact) used to reach the
      verdict.
    must_pass: true

  - id: req_publication_figure
    type: artifact
    description: >-
      At least one publication-quality figure file (PDF or PNG, ≥150 DPI for
      raster) exists under figures/ or output/figures/ with axes labeled in
      physical units (GeV / pb / fb / dimensionless) and a legend if multiple
      series are plotted.  The figure must directly support a hypothesis
      verdict.
    must_pass: true

  - id: req_model_implementation
    type: artifact
    description: >-
      The BSM Lagrangian is implemented either as a FeynRules .fr file
      (models/*.fr) with a matching UFO directory (models/*_UFO/ containing
      at least particles.py, parameters.py, couplings.py, vertices.py), OR
      as analytic Python code that explicitly computes the cross sections
      from the Lagrangian terms.  A pure SM baseline with no BSM piece is
      NOT sufficient.
    must_pass: true

"""

TOPIC_SPECIFIC_TEMPLATE = """  - id: {id}
    type: numeric
    description: >-
      {description}
    must_pass: true

"""

OPTIONAL_BLOCK = """  - id: req_mechanistic_writeup
    type: discussion
    description: >-
      The summary or structured_results section provides a one-paragraph
      mechanistic interpretation of WHY the headline observable comes out the
      way it does (which interference / propagator structure / cut effect
      drives the result).  Nice-to-have, not blocking proceed.
    must_pass: false

  - id: req_mc_reproducibility
    type: discussion
    description: >-
      results.json or a sibling reproducibility section names: (a) the
      MadGraph5_aMC@NLO version, (b) the PDF set used (if applicable), (c)
      at least one explicit random seed.  Required for full reproducibility
      but not for scientific correctness.
    must_pass: false
"""


def inject_into(path: Path) -> bool:
    text = path.read_text(encoding="utf-8")
    if "\nrequirements:" in text or text.startswith("requirements:"):
        return False  # already has block
    tid = path.stem  # "P01"
    spec = TOPIC_SPECIFIC.get(tid)
    if spec is None:
        return False
    topic_block = TOPIC_SPECIFIC_TEMPLATE.format(**spec)
    new_text = text.rstrip() + "\n" + GENERIC_BLOCK + topic_block + OPTIONAL_BLOCK
    path.write_text(new_text, encoding="utf-8")
    return True


def main() -> int:
    n_added = 0
    for n in range(1, 11):
        tid = f"P{n:02d}"
        p = ROOT / f"{tid}.yaml"
        if not p.is_file():
            print(f"  skip {tid}: file missing")
            continue
        if inject_into(p):
            print(f"  + {tid}: requirements block added")
            n_added += 1
        else:
            print(f"    {tid}: already has requirements (skipped)")
    print(f"\n  done — {n_added}/10 manifests updated")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
