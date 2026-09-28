---
name: metabolic-study-planner
description: >
  Plan publishable constraint-based metabolic modelling studies when the user
  has a broad biological or metabolic-engineering topic but no concrete dataset,
  organism, model, or hypothesis. Selects feasible BiGG/COBRA models, objectives,
  perturbations, analyses, metrics, figures, and risk controls before FBA code is
  generated.
metadata:
  category: domain
  trigger-keywords: "metabolic idea,metabolic study,metabolic engineering,FBA,COBRApy,BIGG,no idea,study planner,hypothesis generation,organism selection,target product"
  applicable-stages: "1,2,7,8,9,10,14,15,16,17"
  priority: "1"
---

# Metabolic Study Planner

## Overview

Use this skill before `gsmm-builder`, `fba-simulator`, and `flux-analyzer` when
the project starts from a broad prompt such as "do a metabolic flux analysis
paper" or "find a publishable idea in microbial metabolism".

The goal is to turn a vague topic into a concrete, executable, paper-shaped
study plan:

```text
organism + model + condition + perturbation + metric + figure set + claim
```

This is the MFA analogue of choosing a collider process and parameter scan
before generating events.

## Planning Inputs

Extract or infer the following:

| Field | Examples |
|---|---|
| Biological scope | microbial metabolism, cancer metabolism, yeast fermentation, tuberculosis |
| Organism | E. coli, S. cerevisiae, human Recon3D, M. tuberculosis |
| Model source | BiGG ID, local SBML/JSON, manually constructed toy model |
| Objective | biomass, product secretion, ATP maintenance, dual objective |
| Condition | aerobic, anaerobic, carbon source, nutrient limitation |
| Perturbation | gene knockout, reaction knockout, medium swap, oxygen sweep |
| Target output | growth, product yield, essential genes, secretion profile |
| Paper type | mechanism hypothesis, metabolic engineering strategy, benchmark, reproduction |

If the user provides no organism, start with one of these low-risk defaults:

| Default | Model | Why |
|---|---|---|
| *E. coli* K-12 | `iJO1366` or core model | Fast, well curated, standard for FBA papers |
| *S. cerevisiae* | `iMM904` | Fermentation and product-yield studies |
| Human metabolism | `Recon3D` | Disease metabolism, but larger and harder |
| *M. tuberculosis* | `iNJ661` | Essentiality and drug-target hypotheses |

Prefer *E. coli* for fully autonomous first runs because it is fast and
interpretable.

## Study Archetypes

### Archetype A: Knockout Strategy for Product Overproduction

Use when the topic mentions metabolic engineering, bio-production, yield, or
fermentation.

Plan:
1. Select a product exchange reaction, e.g. succinate, lactate, ethanol, acetate.
2. Run WT FBA and pFBA under a defined medium.
3. Screen single reaction/gene knockouts.
4. Rank perturbations by product secretion subject to retaining growth.
5. Validate top candidates with FVA and carbon-source sensitivity.

Required metrics:
- WT growth rate
- mutant growth fraction
- product secretion flux
- product yield per glucose uptake
- robustness across oxygen/carbon-source bounds

Paper claim format:
> Constraint-based screening predicts that perturbing `<pathway>` improves
> `<product>` secretion while preserving `<growth_fraction>` of WT growth.

### Archetype B: Nutrient-Condition Phase Map

Use when the topic mentions adaptation, nutrient limitation, aerobic/anaerobic
growth, diauxie, or environmental stress.

Plan:
1. Choose two exchange reactions, usually glucose and oxygen.
2. Generate a 2D production envelope / phenotype phase plane.
3. Compare secretion profiles across regimes.
4. Identify transitions between respiration, overflow metabolism, and no-growth
   regions.

Required metrics:
- growth `flux_maximum`
- glucose uptake
- oxygen uptake
- major byproduct secretion fluxes
- regime labels

Paper claim format:
> A two-axis nutrient envelope reveals distinct feasible metabolic regimes and
> predicts condition-specific secretion shifts.

### Archetype C: Essentiality and Drug-Target Prioritisation

Use when the topic mentions antimicrobial targets, cancer metabolism, essential
genes, or robustness.

Plan:
1. Select an organism/model relevant to the disease.
2. Run single gene/reaction deletion.
3. Filter essential genes/reactions.
4. Remove non-specific housekeeping artifacts where possible.
5. Prioritise targets by subsystem, growth impact, and flux centrality.

Required metrics:
- essential gene count
- essential reaction count
- subsystem enrichment
- growth fraction after deletion
- rescue condition sensitivity

Paper claim format:
> FBA essentiality analysis prioritises `<subsystem>` as a condition-dependent
> vulnerability under `<medium>`.

### Archetype D: Method/Protocol Benchmark

Use when the topic is methodological or AutoResearchClaw asks for a benchmark.

Plan:
1. Compare FBA, pFBA, loopless FBA, and FVA-derived predictions.
2. Run across multiple models or media.
3. Evaluate stability of growth, secretion, and essentiality calls.

Required metrics:
- runtime
- solver status rate
- agreement of essential genes/reactions
- flux sparsity
- objective consistency

Paper claim format:
> A standardised COBRApy protocol improves reproducibility of metabolic
> phenotype predictions across models and media.

## Feasibility Gate

Before committing to a study, score candidate ideas from 1-5:

| Criterion | Reject if |
|---|---|
| Model availability | no BiGG/SBML/JSON model or no clear toy model |
| Runtime | requires exhaustive double knockouts on large models |
| Interpretability | no identifiable pathway/subsystem or biological claim |
| Output richness | fewer than 3 meaningful figures/tables |
| Reproducibility | depends on undocumented proprietary data |

Proceed only if total score is at least 18/25. Otherwise choose a simpler
organism, narrower product, or smaller perturbation space.

## Required Study Card

Write a `study_card.md` before code generation:

```markdown
# Metabolic Study Card

## Research Question
One sentence.

## Hypothesis
One falsifiable claim.

## Model
- Organism:
- Model ID / source:
- Objective reaction:

## Conditions
- Medium:
- Carbon source:
- Oxygen bounds:

## Analyses
- FBA:
- pFBA:
- FVA:
- Knockout screen:
- Production envelope:

## Metrics
- Growth rate:
- Product flux:
- Yield:
- Essentiality:
- Robustness:

## Figures
1. WT vs perturbation flux summary
2. Product yield ranking
3. Production envelope / phase map
4. Essentiality or subsystem enrichment plot

## Risks
- Model curation risk:
- Solver/runtime risk:
- Biological interpretation risk:
```

## AutoResearchClaw Guidance

When this skill is matched in AutoResearchClaw:

- In `hypothesis_gen`, propose hypotheses tied to a named model and analysis.
- In `experiment_design`, include a concrete model ID, objective reaction,
  perturbation set, and metrics.
- In `code_generation`, generate a self-contained COBRApy script that can run
  either on a local model file or on a minimal fallback toy model if the full
  model is unavailable.
- In `result_analysis`, do not overclaim experimental validation. Phrase results
  as model-based predictions.
- In paper writing, explicitly state that conclusions are constraint-based
  computational predictions requiring wet-lab validation.

## Recommended First Autonomous Topic

If the user has no idea, start with:

```text
Predict robust reaction knockout strategies for succinate overproduction in
E. coli using COBRApy FBA, pFBA, FVA, and oxygen/glucose production envelopes.
```

This topic is computationally feasible, uses a standard organism, produces
multiple figures, and has an interpretable metabolic-engineering narrative.
