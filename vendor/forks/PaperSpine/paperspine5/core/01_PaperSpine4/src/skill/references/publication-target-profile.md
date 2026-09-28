# Publication Target Profile

Create or refresh `publication_target_profile.json` for every named destination
before formatting, submission packaging, rebuttal finalization, or transfer.
Use `publication-cycle-contracts.md` for the machine fields.

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
delivery bundle must be blocked.

## Validation

```bash
python scripts/publication_cycle.py profile-check \
  paper_rewriting_output/publication_cycle/targets/<target>/publication_target_profile.json \
  --markdown --write
```

Fix structural/source failures before writing target-specific materials.
