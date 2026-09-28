# Submission Package

Use this reference when the user requests submission materials, cover letter,
highlights, journal submission package, or final files for a target journal.

## Output Directory

Write all submission materials under:

```text
paper_rewriting_output/submission_package/
```

Outputs depend on `output_language` and `translation_package` in
`paper_spine_config.json` (read from the submission package directory or its
parent). The default run is English-only, so by default only the `*.en.*`
files are produced.

English deliverables (produced unless the run is Chinese-only,
`output_language: zh`):

- `cover_letter.en.md`
- `cover_letter.en.docx`
- `highlights.en.md`
- `highlights.en.docx`

Chinese deliverables (produced only when `output_language: zh` or
`translation_package: zh`):

- `cover_letter.zh.md`
- `cover_letter.zh.docx`
- `highlights.zh.md`
- `highlights.zh.docx`

Plus, in every run:

- `submission_check.md` after running `submission_check.py --write`

Do not generate `*.zh.*` files for a default English-only run. `submission_check.py`
is config-driven: it only demands the files for the configured language(s) and
will not fail an English-only package for missing Chinese files (any Chinese
file that *is* present is still validated).

The `.docx` files are the formal user-facing outputs. The `.md` files are
auditable source drafts for checking and regeneration.

## Source Discipline

Allowed PaperSpine inputs:

- `paper_rewriting_output/final_paper/main.tex`
- `paper_rewriting_output/confirmed_motivation.md`
- `paper_rewriting_output/claim_register.md`
- `paper_rewriting_output/evidence_bank.md`
- `paper_rewriting_output/research_dossier.md`

Allowed external input:

- any user-provided `.tex`, `.docx`, or `.md` draft path

For an external draft, first extract candidate contribution points, show them
to the user, and get confirmation before generating submission materials.

Do not invent contributions. Claims must trace to `confirmed_motivation.md`,
`claim_register.md`, `evidence_bank.md`, or `final_paper/main.tex`.

Do not invent author names, affiliations, email addresses, reviewer names, or
reviewer contact details. Use explicit placeholders such as:

- `[CORRESPONDING AUTHOR NAME]`
- `[CORRESPONDING AUTHOR AFFILIATION]`
- `[CORRESPONDING AUTHOR EMAIL]`
- `[MANUSCRIPT TITLE]`
- `[MANUSCRIPT TYPE]`
- `[JOURNAL NAME]`
- `[RECOMMENDED REVIEWER NAME]`

End both cover letters with a fill-in checklist listing every remaining
placeholder.

## Highlights Format

Follow the common Elsevier-style highlights format unless the target journal has
stricter rules:

- 3 to 5 bullet points.
- Each bullet no more than 85 characters, including spaces.
- One finding or implication per bullet.
- Use present tense where natural.
- No citations, including `\cite{}`, `[@key]`, or numbered citations like `[1]`.
- No undefined abbreviations, jargon, TODO markers, or double-bracket
  placeholders.
- Submission-facing highlights contain only bullet lines, not rationale notes.

Use this shape:

```markdown
# Highlights

- Antimicrobial peptides offer alternatives against resistant bacteria.
- The review maps peptide sources, functions, and mechanisms.
- Peptide redesign supports future anti-resistance drug discovery.
```

The Chinese highlights should be a clean bilingual review version, not a
teaching draft. Keep it concise and citation-free.

## Cover Letter Format

Write `cover_letter.en.md` as a concise one-page letter, normally 250-400 words.
Use this order:

1. Date line.
2. Editor salutation.
3. Submission sentence with manuscript title and manuscript type.
4. Brief journal-fit paragraph using `research_dossier.md` when available.
5. Two or three contribution sentences, derived from the same claim sources as
   the highlights but not copied verbatim.
6. Originality and not-under-consideration statement.
7. Conflict of interest statement.
8. Corresponding author line with placeholders where needed.
9. Fill-in checklist for unresolved placeholders.

Write `cover_letter.zh.md` with the same functional content in Chinese and the
same clean one-page structure.

Recommended English statement:

```text
We confirm that this manuscript is original, has not been published previously,
and is not under consideration by any other journal.
```

Keep recommended reviewers out of the main letter unless the target journal
explicitly asks for them there. Put reviewer placeholders in the fill-in
checklist.

## Word Output

Generate Word files for the deliverables required by the configured language
(see "Output Directory" above). For a default English-only run that is:

```text
paper_rewriting_output/submission_package/cover_letter.en.docx
paper_rewriting_output/submission_package/highlights.en.docx
```

When Chinese deliverables are required (`output_language: zh` or
`translation_package: zh`), also generate:

```text
paper_rewriting_output/submission_package/cover_letter.zh.docx
paper_rewriting_output/submission_package/highlights.zh.docx
```

Use pandoc from the submission package directory, converting each Markdown
source that exists:

```bash
cd paper_rewriting_output/submission_package
pandoc cover_letter.en.md -o cover_letter.en.docx
pandoc highlights.en.md -o highlights.en.docx
# Only when Chinese deliverables are required:
pandoc cover_letter.zh.md -o cover_letter.zh.docx
pandoc highlights.zh.md -o highlights.zh.docx
```

### LaTeX Command Sanitization Before Pandoc

Before converting Markdown to .docx, ensure the source Markdown is free of raw
LaTeX commands that pandoc cannot render. Common leaks include:

| Raw LaTeX | Rendered Form | Notes |
|---|---|---|
| `\AA{}` / `\AA` | Å | Angstrom symbol (U+00C5) |
| `\textit{...}` | *italic text* | Use Markdown `*...*` or `_..._` |
| `\textsubscript{...}` | subscript text | Use HTML `<sub>...</sub>` or pandoc `~...~` |
| `\textsuperscript{...}` | superscript text | Use HTML `<sup>...</sup>` or pandoc `^...^` |
| `\%` | % | Literal percent sign |
| `\$` | $ | Literal dollar sign |
| `\&` | & | Literal ampersand |
| `\_` | _ | Literal underscore |
| `\#` | # | Literal hash |
| `\{` / `\}` | { / } | Literal braces |

These must be normalized **in the Markdown source** before running pandoc, not
after. Post-processing .docx files in-place is a last resort for already-generated
files. The `word_guard.py` script will FAIL any .docx that contains raw LaTeX
commands; this is intentional and must not be relaxed.

After generation, set Word fonts consistently:

- Chinese / East Asian text: SimSun (宋体).
- English / Latin text: Times New Roman.
- Page setup: A4 paper with 1-inch margins.

This font rule applies to both Chinese and English submission files because
placeholder labels, journal names, and English terms may appear in Chinese
letters.

If pandoc is unavailable, keep the Markdown source files, record the skipped
docx generation in the final response or audit notes, and do not claim that the
Word versions were produced.

## Validation

Run:

```bash
python scripts/submission_check.py paper_rewriting_output/submission_package --fix-fonts --markdown --write
```

Fix all FAIL findings before presenting the package. Placeholder warnings are
allowed, but the cover letters must list them in the fill-in checklist so the
user knows what to complete manually.
