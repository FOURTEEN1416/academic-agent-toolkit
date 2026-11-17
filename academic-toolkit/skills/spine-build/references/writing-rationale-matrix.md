# Writing Rationale Matrix

Use this reference in both `rewrite_existing` and `build_from_materials`.

The matrix is the core writing method. It must be written before final prose and
then used as the checklist for drafting/revision. It is not a post-hoc change
log and it is not a fixed IMRaD template. Before substantive writing or
revision, apply the matrix's motivation, evidence and structural questions, and
record the useful decisions in the existing notes, outline, or matrix rows. A
narrow edit may reuse its still-valid plan; no fixed form or row quota
substitutes for this reasoning, and a post-hoc account is not evidence of prior
planning.

## Principle

Create one row for each smallest useful writing unit that needs a deliberate
choice. The unit size depends on the task:

- journal or conference paper: framework, title/abstract units, Introduction
  moves, method-design explanations, result evidence units, figure/table claims,
  discussion moves, captions, and claim-bearing headings;
- report or review: executive summary units, problem/background units, taxonomy
  or comparison units, evidence synthesis units, recommendation units,
  limitation/future-work units, and important headings/figures/tables;
- competition paper/report: problem restatement, assumptions, notation, model
  design, solution procedure, validation, sensitivity/robustness, strengths and
  weaknesses, recommendations, and visual/table claims.

Do not force every task into Abstract/Introduction/Methods/Results/Discussion.
Do not use only one row per top-level section. Split the manuscript into
paragraph-sized or claim-sized units whenever the writing decision changes.

## Required Table

| Row ID | Manuscript Unit | Current Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change/Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|

## Required Coverage

- The first data row must justify the whole-work framework, structure, or main
  throughline.
- Every subsequent row should correspond to a real writing unit in manuscript
  order.
- Use task-specific units rather than a fixed template. For example, a
  competition solution may need rows for assumptions, symbols, model derivation,
  algorithm steps, sensitivity analysis, and recommendations; a review may need
  rows for search scope, inclusion logic, taxonomy, comparison dimensions, and
  synthesis claims.
- Include titles, subsection headings, figure captions, and table captions when
  they carry argument logic.
- If one paragraph has two separate functions, split it into two rows. If three
  short paragraphs share one function, one row may cover that paragraph group.

## Reason Quality Bar

Every row must contain concrete reasoning, not generic polishing language. It
should explain how the unit uses all major anchors whenever possible:

- advances, validates, interprets, or bounds a confirmed contribution promise,
- aligns that promise with the confirmed motivation without enlarging it —
  motivation explains why the promise matters, but cannot substitute for the
  promise or exceed its claim boundary,
- transfers a structural move learned from SOTA/example work without copying
  wording or results,
- matches a target journal/conference/report/competition norm,
- uses a specific user evidence item, figure, table, result, or citation anchor,
- moves evidence next to the claim it supports,
- creates a front/back echo with an earlier or later unit,
- fixes an original logic failure,
- prevents overclaiming beyond available evidence.

Generic reasons such as "improve clarity", "make academic", "polish wording",
or "add detail" do not pass.

Minimum depth requirement:

- Cover the actual writing decisions at a useful granularity: use at least 8
  rows for ordinary manuscripts/reports, and many more for long or complex
  papers — but row count alone does not establish depth; a short manuscript or
  narrow revision may legitimately need few rows.
- The first row is the whole-work framework row. It must deeply explain the
  controlling structure: which contribution promise governs it, how the
  confirmed motivation establishes its necessity, what SOTA/example pattern it
  transfers, how it matches the target scene, which user evidence anchors it,
  and how later sections will be checked against it.
- Each non-trivial row must contain enough detail to teach the writing decision,
  not only name the section. Include the contribution promise and motivation
  link, learned reference/SOTA pattern, target-scene norm, evidence/citation
  anchor, planned text move, and final check. If any of these is not
  applicable, state why.
- Do not compress a large decision into one phrase such as "conservation-first
  abstract" or "add ablation section". Explain why that move changes the paper's
  logic and how the final text will prove it.

## Rewrite And Build Discipline

The final manuscript should be drafted row by row. For rewrite tasks, each row
should be traceable to the original logic map and/or a deliberate structural
change. For build-from-materials tasks, each row should be traceable to the
source inventory, evidence bank, claim register, or figure asset map.

**Scaffolding stays internal (fourth-wall rule).** The matrix's reasoning
columns — the motivation link, the "close-the-supervisor/reviewer-comment"
justifications, the planned structural moves, and any `A -> B -> C` throughline —
are PLANNING NOTATION. Draft *from* them, but never copy them into the
manuscript. The reader-facing prose must never name the writing process, a
supervisor or reviewer, their comments/feedback, an earlier or previous draft,
or narrate that the paper was "reorganized/restructured" to address anything.
A sentence like "针对导师对前期初稿的审阅意见，本文沿一条主线重新组织：…→…→…" is
a leak of this matrix row into the body — render it instead as a direct
motivation statement. `integrity_audit.py` hard-fails such process language.
Judge a passage by its scientific or transparency function, not by the mere
presence of a word: required AI-use/writing-assistance disclosures and review
procedures that belong to the research Methods stay in the manuscript.

After drafting, update the `Final Text Check` column. The value must start with
`PASS` or `FAIL`, then give the final location or the reason it still fails.
Examples: `PASS: Section 2 paragraph 3 now states the claim after citation C12.`
or `FAIL: no verified citation yet for this mechanism claim.` Values that only
say a location, "done", or a vague note do not pass audit.

## Detail Standard

A row should be detailed enough that the user can learn the writing logic from
it. Do not write rows like "graphic path fix" or "rewrite abstract" as the main
explanation. For every non-trivial row, include:

- what the original or planned unit is trying to achieve,
- why the current version is logically weak or why this unit is needed,
- which confirmed contribution promise controls this unit,
- how the confirmed motivation supports that promise,
- which SOTA/example/target-scene pattern is being transferred,
- which user evidence, figure, table, result, or citation anchor supports it,
- what exact rhetorical move will be made,
- how the final text should be checked.

For important units, prefer 2-4 sentences inside cells rather than keywords.
The matrix should be useful as a learning document, not only an audit checklist.

## Deep Framework Row Example

The whole-work row should look more like a design memo than a TODO item:

| Row ID | Manuscript Unit | Current Problem or Planned Function | Motivation Link | Reference/SOTA Pattern Learned | Target Scene or Venue Norm | User Evidence or Citation Anchor | Planned Change/Text Move | Final Text Check |
|---|---|---|---|---|---|---|---|---|
| F1 | Whole-work framework | Decide the paper's controlling argument before editing any paragraph. The current draft may contain multiple valid technical points, but the paper needs one dominant contribution and a sequence of evidence that makes that contribution inevitable. | The governing contribution promise becomes the spine: the paper first exposes the unresolved problem, then shows why the proposed design is necessary, then lets evidence test the promise without inflating it. Secondary engineering choices are positioned as enabling mechanisms, not competing innovations. | Learn from SOTA and target examples at the level of structure: how they stage gap, design rationale, evidence order, failure modes, and bounded discussion. Do not copy wording; transfer the move that makes the reader accept why this paper had to be written. | The target scene expects a recognizable argument architecture. A journal paper may need IMRaD and independent evaluation; a competition report may need assumptions, model logic, validation, sensitivity, and recommendations; a course report may need rubric-visible evidence. | Anchor the framework to the user's actual draft/materials: source_map.md, evidence_bank.md, figures/tables, citations, experiment settings, claim register, and any special requirements. External papers may teach writing structure and support verified background, methods or interpretation; their findings must remain attributed and must not be presented as this study's results. | Reframe the manuscript so every major section answers one part of the same governing promise. Move background, method rationale, results interpretation, captions, and discussion claims until the evidence sequence and claim boundary are visible. | PASS: Reader can state the paper's contribution, why it matters, which evidence validates it, and what it does not claim, from ordered section openings and captions. |
