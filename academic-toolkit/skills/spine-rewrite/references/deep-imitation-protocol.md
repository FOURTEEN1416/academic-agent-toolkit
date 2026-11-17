# Deep Imitation Protocol

Use this reference when the user says the revision must learn from or imitate excellent papers. This protocol is designed to prevent shallow edits that merely add a few sentences to the old draft.

## What "Learning From Papers" Means

Learning is not copying phrases and not loosely "sounding academic." It is extracting reusable writing decisions:

| Layer | What to Learn | Output |
|---|---|---|
| Argument architecture | how the paper moves from field problem to contribution | move sequence |
| Section rhythm | paragraph count, paragraph jobs, length distribution | section blueprint |
| Claim calibration | how strongly claims are stated given evidence | claim rules |
| Evidence placement | where numbers, figures, citations, and caveats appear | evidence placement map |
| Sentence architecture | sentence roles and slots, not copied sentences | skeleton bank |
| Reader contract | what the paper assumes, explains, and omits | audience rule |

The output of learning is `style_profile.md` plus `section_blueprints.md`. If
these artifacts do not exist, no deep imitation has happened. Judge deep
imitation by the observed reasoning and writing changes, not by the existence
of particular filenames alone.

## Three-Table Method

For each target section needing structural revision, compare exemplar moves,
current draft moves and the intended evidence-led outline. The three tables
below are one way to record that comparison; existing notes can carry it. The
scientific work is the same either way: read the selected original sections,
locate their paragraph functions and evidence, compare those functions with the
draft, and apply the suitable pattern in an actual revised section. Reopen both
texts to judge whether the diagnosed argument problem was repaired while the
study's facts and claim boundary were preserved. A list of paper titles or a
completed profile alone does not do this.

### Table 1: Exemplar Move Table

```markdown
| Exemplar | Paragraph | Move | Evidence Type | Opening Function | Closing Function | Notes |
|---|---|---|---|---|---|---|
```

Fill this from 3-6 exemplar papers. Use exact quotations only inside analysis notes. Convert them into abstract patterns before rewriting.

### Table 2: User Draft Move Table

```markdown
| Draft Paragraph | Current Move | Evidence Present | Problem | Keepable Content |
|---|---|---|---|---|
```

Mark problems honestly:

- wrong move,
- move missing,
- multiple moves in one paragraph,
- unsupported claim,
- weak transition,
- wrong level of detail,
- not aligned with target style.

### Table 3: Target Section Blueprint

```markdown
| Target Paragraph | Move | Source Evidence | Exemplar Pattern | Target Length | Required Operation |
|---|---|---|---|---|---|
```

Allowed operations:

- `REWRITE`: old content is retained as evidence, but prose and structure are regenerated.
- `SPLIT`: one overpacked draft paragraph becomes multiple target paragraphs.
- `MERGE`: several weak paragraphs become one stronger paragraph.
- `DELETE`: unsupported or off-thread content is removed.
- `MOVE`: content moves to a better section.
- `ADD`: new connective or explanatory text is added from existing evidence.
- `KEEP`: paragraph is retained nearly as-is, with explicit justification.

Choose the operation that repairs the actual weakness. `KEEP` should be rare in
style imitation and `ADD` secondary, but retaining already-effective text is
correct; an operation ratio is not a measure of learning.

## Closed-Book Section Rewrite

Use this procedure for each important section:

1. Read the original section and extract facts, claims, citations, figure references, and numbers into notes.
2. Read the exemplar move table and section blueprint (or the equivalent notes).
3. Stop looking at the original prose.
4. Draft the new section from notes and blueprint.
5. Reopen the original only to verify that claims, numbers, citations, and figure references are preserved.
6. Compare the original and revised argument against the diagnosed weakness; run `revision_audit.py` to locate near-identical paragraphs. Its similarity ratio is a diagnostic, not the verdict on scientific or writing quality.

This prevents the common failure mode where the model simply edits one sentence, adds one sentence, and leaves the rest untouched.

## Minimum Rewrite Standards

For substantive revision, the output should usually satisfy:

| Metric | Target |
|---|---|
| Near-identical paragraph ratio | Diagnostic: assess whether the identified weaknesses were repaired; retain justified valid text |
| Dominant operation | not `ADD` |
| `KEEP` rows | No quota: keep valid, unaffected content and justify it when substantive restructuring was requested |
| Missing obligatory moves | 0 |
| Unsupported new claims | 0 |
| Numbers without source | 0 |

These are not universal quality metrics, but they catch shallow revision.

## Section Blueprint Requirements

Each blueprint must answer:

1. What is this section's communicative job?
2. Which exemplar paper provides the closest section structure?
3. What moves are obligatory?
4. What order should the moves appear in?
5. What old content should be deleted, merged, split, or moved?
6. What evidence from the user's materials supports each target paragraph?
7. What style constraints apply: sentence length, citation density, claim strength, opening/closing style?

**Section economy is a budget, not a wish.** Section structure follows the
article's argument and target requirements: read the exemplars' section
functions and proportions as orientation, then choose the structure the present
evidence needs. Combine short or redundant sections only when their
intellectual jobs remain clear. Applied journal/conference papers commonly run
4-6 top-level sections; `section_economy_check.py` hard-fails a top-level
section count above the budget, so a bloated blueprint will not pass the final
gate — and the count warning is never a reason to remove required content.

## Results and Discussion Discipline

For Results:

- Do not borrow results from exemplar papers.
- Do not infer numerical values from figures unless the user permits visual estimation.
- Prefer exact values from tables/logs/source draft.
- If raw arrays are unavailable, retain the supported values and findings
  explicitly reported in the user's materials, and distinguish those reported
  results from independent reproduction. Describe only what the figure itself
  supports when no numeric source exists, and flag specific ambiguities rather
  than marking all supplied work unverified.

For Discussion:

- Resolve the Introduction's gap using the user's results.
- Compare to relevant prior work whose cited point has actually been verified,
  including justified public-literature retrieval. Honor explicit offline
  instructions; a materials-only research scope excludes new analyses, not
  normal public citation checks.
- Limit future work and limitations to claims supported by the study design.

## Failure Pattern: Patch Writing

Patch writing looks like:

- "This paragraph is adequate; minor polish only" repeated across the matrix.
- Most actions are `ADD` or `KEEP`.
- A new subsection is added, but existing weak sections are untouched.
- Exemplar papers appear in the report but not in the actual paragraph plan.
- No section blueprint exists.
- No audit compares original and revised text.

When this happens, repair the affected section with the closed-book method.
Preserve effective changes and unaffected prose rather than discarding work to
satisfy an operation ratio.
