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

Record the actual exemplar-to-manuscript learning in the same task's notes, using a style profile or section blueprint where useful. Judge deep imitation by the observed reasoning and writing changes, not by the existence of particular filenames.

## Three-Table Method

For a section needing structural revision, compare exemplar moves, current
draft moves and the intended evidence-led outline. The tables below are optional
ways to do that comparison; existing notes can carry it.

The scientific work remains the same whichever format carries it: read the
selected original sections, locate their paragraph functions and evidence,
compare those functions with the draft, and apply the suitable pattern in an
actual revised section. Reopen both texts to judge whether the diagnosed
argument problem was repaired while the study's facts and claim boundary were
preserved. A list of paper titles or a completed profile alone does not do this.

### Table 1: Exemplar Move Table

```markdown
| Exemplar | Paragraph | Move | Evidence Type | Opening Function | Closing Function | Notes |
|---|---|---|---|---|---|---|
```

Use the saved exemplar counts and the sections actually read. Use exact quotations only inside analysis notes. Convert them into abstract patterns before rewriting.

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

Choose the operation that repairs the actual weakness. Retain already-effective
text; an operation ratio is not a measure of learning.

## Closed-Book Section Rewrite

Use this procedure for each important section:

1. Read the original section and extract facts, claims, citations, figure references, and numbers into notes.
2. Read the source-located exemplar moves and evidence-led section plan, whether recorded in tables or existing notes.
3. Stop looking at the original prose.
4. Draft the new section from notes and blueprint.
5. Reopen the original only to verify that claims, numbers, citations, and figure references are preserved.
6. Compare the original and revised argument and paragraphs against the diagnosed weakness. `revision_audit.py` can help locate near-identical text; its similarity ratio does not decide scientific or writing quality.

This prevents the common failure mode where the model simply edits one sentence, adds one sentence, and leaves the rest untouched.

## Minimum Rewrite Standards

For substantive revision, the output should usually satisfy:

| Metric | Target |
|---|---|
| Near-identical paragraph ratio | Diagnostic only; assess whether the identified weaknesses were repaired and retain justified valid text |
| Dominant operation | not `ADD` |
| `KEEP` rows | No quota; keep valid, unaffected content and explain its fit when substantive restructuring was requested |
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

**Section economy follows the article's argument and target requirements.** Read the exemplars' section functions and proportions as orientation, then choose the structure needed by the present evidence. Combine short or redundant sections only when their intellectual jobs remain clear. A separate Discussion or Conclusion may be appropriate. Treat section_economy_check.py's count warnings as diagnostics, never as a reason to remove required content.

## Results and Discussion Discipline

For Results:

- Do not borrow results from exemplar papers.
- Do not infer numerical values from figures unless the user permits visual estimation.
- Prefer exact values from tables/logs/source draft.
- If raw arrays are unavailable, retain supported values and findings explicitly reported in the user's materials. Distinguish those reported results from independent reproduction. Describe only what the figure itself supports when no numeric source exists, and flag specific ambiguities rather than marking all supplied work unverified.

For Discussion:

- Resolve the Introduction's gap using the user's results.
- Compare to relevant prior work whose cited point has actually been verified, including justified public-literature retrieval. Honor explicit offline instructions; materials_only excludes new analyses, not normal public citation checks.
- Limit future work and limitations to claims supported by the study design.

## Failure Pattern: Patch Writing

Patch writing looks like:

- "This paragraph is adequate; minor polish only" repeated across the matrix.
- Most actions are `ADD` or `KEEP`.
- A new subsection is added, but existing weak sections are untouched.
- Exemplar papers appear in the report but not in the actual paragraph plan.
- No section blueprint exists.
- No audit compares original and revised text.

If an identified argument weakness remains, repair that section using the
comparison above; a closed-book rewrite may help. Preserve effective changes
and unaffected prose rather than discarding work to satisfy an operation ratio.
