# Journal Transfer and Resubmission

Use this mode after desk rejection, peer-review rejection, a declined transfer
offer, or a user request to move the manuscript elsewhere.

## 1. Preserve the paper identity

Hash-bind the canonical manuscript and `confirmed_contribution.md`; restate the
claim boundary. Analyze the decision letter into:

- scope/fit reasons;
- evidence or method concerns;
- framing/narrative concerns;
- presentation/format problems;
- useful reviewer feedback that remains valid independent of venue.

Do not assume rejection proves the science is wrong, and do not discard valid
criticism merely because it came from a rejecting venue.

## 2. Read user expectations and recommend

Record must-haves, nice-to-haves, deal-breakers, budget/access model, timing,
and format preferences. Research current official sources and paper corpora for
candidate venues. Compare at least two contrasting candidates unless the user
named the destination. Return `SUBMIT`, `RESHAPE`, or `REDIRECT` with concrete
reasons and tradeoffs; do not produce acceptance probabilities from
unsupported data.

Publisher transfer offers can reduce administrative work, but they do not
guarantee acceptance and do not select a destination for the author. The user
must confirm the destination before files are rebuilt or an external transfer
is accepted.

## 3. Create destination profile and request

Build a fresh `publication_target_profile.json` for the selected destination.
Create `transfer_request.json` using `publication-cycle-contracts.md`; bind the
origin/destination names, candidate comparison, user preferences, fit verdict,
canonical manuscript/contribution hashes, and confirmed claim boundary.

If the destination is `RESHAPE`, list the actual reshape actions and obtain
author confirmation. If it is `REDIRECT`, stop and recommend another target.

## 4. Generate the delta

```bash
python scripts/publication_cycle.py transfer-plan \
  <origin>/publication_target_profile.json \
  <destination>/publication_target_profile.json \
  paper_rewriting_output/publication_cycle/transfers/<id>/transfer_request.json \
  paper_rewriting_output/publication_cycle/transfers/<id>/delta \
  --markdown
```

The delta always reopens three surfaces:

1. **Format:** template, file types, limits, anonymity, references,
   figures/tables, supplements, and rendering.
2. **Five-part narrative:** front matter, introduction, methods/approach,
   results/analysis, and discussion/conclusion are rebuilt from the destination
   profile even when headings look similar.
3. **Delivery package:** target-specific letters, title/blinded pages,
   declarations, attachments, source archive, and upload names are regenerated
   or revalidated according to the destination requirement.

## 5. Rebuild, do not patch the old submission

Start from the canonical manuscript, not the old upload copy. Preserve
scientific facts, contribution, results, and claim boundary unless the author
and new evidence explicitly change them. Apply the destination narrative moves,
convert into its accepted format, and render-verify the full paper. Invalidate
old figure/visual/citation/metadata/artifact receipts when affected.

Create a new destination `submission_package_plan.json` with the previous venue
in `forbidden_target_terms`, then assemble a new immutable READY bundle. Never
reuse the previous cover letter, target title page, filename scheme, or journal
name merely because a publisher portal copied the files automatically.
