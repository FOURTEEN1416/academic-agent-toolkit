# Publication Target Profile

Research the actual destination using target-journal-research.md and
manuscript-format.md; reuse still-valid task notes. Create or refresh
`publication_target_profile.json` only when the invoked publication-cycle
assembler consumes it. Use publication-cycle-contracts.md for that machine input.
The schema is not a prerequisite for writing, reading-layout export or safe
local delivery; pending author facts limit submission readiness.

## Evidence streams

1. **Official requirements** — the live Guide/Instructions for Authors,
   article-type page, submission portal help, and official template. These own
   file types, limits, declarations, anonymity, figures/tables, and attachments.
2. **Published corpus** — recent, comparable papers from the venue. These teach
   the five-part narrative preferences and the evidence/novelty bar.
3. **Paper-specific fit** — the user's confirmed contribution, study design,
   evidence, limitations, article type, and submission preferences.

Record every profile statement with source IDs. `official` statements may be
hard requirements. `published_corpus` statements are empirical preferences.
`inferred` statements remain labeled and must not become invented editorial
policy. Do not invent acceptance rates, turnaround, indexing, APCs, or editor
preferences.

Re-open the official guide immediately before final bundle assembly. When the
guide changed, update the profile, producing a new hash; a package plan bound to
the old hash must fail rather than silently inherit stale rules.

## Analyze the user's paper before recommending

Read the canonical manuscript, confirmed contribution, claim boundary,
evidence ledger, figures/tables, and any rejection/reviewer letter. Preserve a
short scientific identity:

- primary question and contribution;
- study/design type and available evidence;
- population/data/domain and generalization boundary;
- strongest results and material limitations;
- article type the work can honestly support.

Then collect the user's destination preferences: must-haves, nice-to-haves,
deal-breakers, budget/access model, timing, and format preferences. Compare at
least two contrasting candidates unless the user already named the destination.
For each, return `SUBMIT`, `RESHAPE`, or `REDIRECT` with evidence-backed reasons
and tradeoffs. Fit is a recommendation, never an acceptance probability.

## Five-part narrative preferences

Use exactly these canonical slots even when the venue uses different headings:

1. `front_matter` — title, abstract, keywords, highlights, accessible summary;
2. `introduction` — opening, gap, contribution, and question/hypothesis moves;
3. `methods_or_approach` — design rationale, reproducibility, ethics, and detail;
4. `results_or_analysis` — ordering, statistics/evidence, figure/table reading;
5. `discussion_and_conclusion` — interpretation, contribution return,
   limitations, implications, and ending.

For each slot record preferred moves, evidence expectations, things to avoid,
and source IDs. If the venue is non-IMRaD, map its real sections into these
slots rather than forcing IMRaD headings.

## Package requirements

Turn every official requirement into one `package_requirements` record. Common
roles include main/blinded manuscript, title page, cover letter, highlights,
graphical abstract, separate figures/tables, supplementary files, reporting
checklist/flow diagram, data/code statement, CRediT contribution statement,
conflict/funding/ethics/consent/AI-use declarations, source archive, and forms.

Do not make common items universally required. Use `required`, `conditional`,
or `optional`, and resolve each condition from the paper and author. If a
conditional item remains `unresolved`, the profile may be researched but the
upload-ready submission claim must remain blocked; a safe, explicitly limited
local manuscript/workspace package may still be delivered.

## Structured hard-rule coverage

The profile's `compliance.coverage` must explicitly cover all nine areas:
`title`, `abstract`, `body`, `figures`, `tables`, `references`, `attachments`,
`required_sections`, and `required_materials`. For each area use exactly one:

- `known` — one or more structured rules are present;
- `not_applicable` — the current official guide supports that no separate rule
  applies, with a source locator and note;
- `pending` — the rule could not yet be established. This is honest but blocks
  profile readiness and every READY bundle.

Do not turn an approximate page impression, recent-paper convention, or generic
publisher habit into a formal limit. Non-advisory rules must cite an `official`
source. Each rule records `observed`, `limit`, `unit`, source URL/locator,
status, and remediation when checked, and declares one verification class:
`machine_verifiable`, `needs_author_confirmation`, or `advisory`.

During writing, precheck the current analyzable manuscript source:

```bash
python scripts/publication_cycle.py rules-check \
  <target>/publication_target_profile.json paper_rewriting_output/final_paper/main.tex \
  --phase writing --markdown --write
```

Use `.tex`, `.md`, or `.txt` as `compliance_inputs.manuscript_path`. A portal
PDF/Word may remain the uploaded manuscript, but an unanalyzable file cannot be
used as the only machine-count source. The plan's file-level validation receipts
remain responsible for proving that the uploaded rendering matches that source.
For TeX, abstract word checks recognize balanced `\abstract{...}` macros (as
used by OUP templates), `abstract` environments, and an `Abstract` section;
nested groups and escaped braces inside a macro do not terminate extraction.
When the official limit is pages, use `metric=page_count`,
`scope=rendered_manuscript`, and set `compliance_inputs.rendered_pdf_path` (or
pass `--rendered-pdf` during the writing precheck). If the PDF parser or the
render is unavailable, observed stays pending and the hard rule blocks; never
replace it with “the total pages look roughly acceptable.”

## Validation

```bash
python scripts/publication_cycle.py profile-check \
  paper_rewriting_output/publication_cycle/targets/<target>/publication_target_profile.json \
  --markdown --write
```

Resolve structural and source failures before claiming the affected target requirements or final bundle ready. Continue supported local writing and correction while unrelated author or submission facts remain unknown. When the assembler is used, its current final rule evaluation is still required; a writing precheck does not substitute for it.
