# Publication Surface Scrub

Internal IDs and audit artifacts are drafting infrastructure, not manuscript
content. After the final language pass, remove bracketed claim/evidence/source/
numeric/method/outcome/result tags, workflow filenames, gate narration, and
other process scaffolding from the reader-facing TeX/Markdown.

Preserve the scientific boundary in natural prose. Do not delete a real
limitation, author-input requirement, or disclosed uncertainty merely because
it originated in an audit.

Also remove defensive audit voice. The final paper should not repeatedly say
“within the supplied materials,” “user-authoritative,” “the evidence ledger
shows,” or stack `may/might/potentially` around an observed result. Follow
`references/assertive-scientific-writing.md`: state supported findings directly
and keep one clear qualification at the point where the inference changes.

```bash
python scripts/publication_surface_check.py paper_rewriting_output --markdown --write
```

Run this before visual preparation and again during final audit. A clean
publication surface is part of `artifact_portable`; it is not evidence that the
underlying scientific ledger may be deleted.
