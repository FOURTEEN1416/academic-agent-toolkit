# Top-Conference Figure Caption Policy v3.1.9

This policy is paper-generic. It must never include target-paper-specific method names, dataset names, algorithm names, or claims in the reusable skill package.

## Goal

The selected figure and caption should let a computer-science reviewer understand the paper's core method or system at a high level before reading the full method section. The caption is part of the scientific artifact: it guides the reader through the visual, defines essential semantics, and states the method contribution without unsupported claims.

## Preferred caption structure

A strong framework-figure caption usually has 2-5 concise sentences:

1. **What the figure shows.** Start with “Overview of ...” or an equivalent factual phrase. Identify the method/system level and the main visual organization.
2. **How to read it.** Walk through panels, phases, or arrows in the same order as the figure. Mention only the essential modules and artifacts.
3. **What is new or important.** State the core design idea, coupling, feedback, decision rule, or data/model interaction. Avoid hype.
4. **How semantics are encoded.** Define only essential colors, line styles, symbols, or notation if they are not already obvious in the legend.
5. **Result/benefit statement only when warranted.** Include empirical or performance claims only if the paper reports them and the statement is scoped and factual.

## Style requirements

- Use precise, venue-appropriate language for ML/CV/NLP/systems/HCI/security/database/graphics papers.
- Prefer short declarative sentences over marketing prose.
- Avoid unsupported superlatives such as “powerful,” “revolutionary,” “best,” or “perfect.”
- Avoid repeating every label already visible in the figure; the caption should explain relationships, not duplicate the diagram.
- Avoid hiding essential visual content in the caption. If a mechanism is central, it needs a visible anchor in the figure.
- Keep notation consistent with the paper and figure.
- Define abbreviations if the figure relies on them.
- Do not introduce new modules, datasets, tasks, losses, metrics, or claims absent from the source paper.

## Post-S5 Boundary Removed In v3.2.13

After S5, human decisions are outside this assistant workflow.

- `final-title`: a concise figure title suitable for a paper figure.
- `paper-ready-caption`: the main caption, usually 90-160 words for a complex framework figure, shorter when the figure is simple.
- `optional-extended-caption`: a longer version for appendix, website, or author iteration when useful.
- `legend-notes`: essential visual encoding definitions that should either appear in the figure legend or caption.
- `body-reference-sentence`: a one-sentence way to introduce the figure in the manuscript body.
- `caption-audit`: checklist results for factuality, visual alignment, claim scope, notation, and readability.

## Caption audit checklist

A caption passes only if:

- every claim is supported by S0/S1/S4/S5 evidence or the user-provided source;
- the reading order matches the selected figure layout;
- all described arrows, panels, artifacts, and roles exist visually;
- the caption does not claim a causal/data/model relation that the image contradicts;
- the caption does not compensate for a missing or false core visual anchor;
- terminology matches the paper;
- the style is compact, objective, and suitable for a top computer-science venue.
