# Submission Metadata

Create `paper_rewriting_output/submission_metadata.json` before final audit.
Keep missing author inputs explicit; do not invent names, affiliations,
funding, conflicts, ethics approvals, contribution roles, or availability
statements.

The `fields` object must contain: `title`, `authors`, `affiliations`,
`corresponding_author`, `funding`, `conflicts`, `ethics`,
`data_availability`, `code_availability`, `author_contributions`, and
`ai_use_disclosure`.

Each field is an object with one state:

- `provided`: include a non-empty `value`;
- `not_applicable`: include a concrete `reason`;
- `blinded`: include a reason tied to the venue's anonymous-review policy.

`blocked`, `missing`, empty values, and generic placeholders do not pass. For
double-blind review, author-related fields may be `blinded`; the unblinded
submission package remains a separate controlled artifact.

```bash
python scripts/metadata_readiness_check.py paper_rewriting_output --markdown --write
```
