# Publication Cycle Contracts

All contracts use `schema_version: "1.0"`. Paths in plans/rounds/requests are
resolved relative to that JSON file and must remain under `project_root`.

These domain contracts are invoked across the PaperSpine/PaperSpine5 boundary
through `publication-cycle-interface.md`. Its request/result envelopes use
`interface_version: "1.0"` and the machine schemas under
`references/contracts/`; do not substitute an envelope version for a domain
artifact's `schema_version`.

## `publication_target_profile.json`

```json
{
  "schema_version": "1.0",
  "target": {
    "name": "Exact journal name",
    "publisher": "Publisher",
    "article_type": "Research Article",
    "researched_at": "2026-08-23"
  },
  "sources": [
    {
      "id": "official-guide",
      "authority": "official",
      "url": "https://journal.example/guide-for-authors",
      "checked_at": "2026-08-23"
    },
    {
      "id": "recent-corpus",
      "authority": "published_corpus",
      "url": "https://journal.example/recent-articles",
      "checked_at": "2026-08-23"
    }
  ],
  "format": {
    "manuscript_formats": [".docx", ".tex"],
    "format_free": false,
    "template_required": true,
    "anonymity": "double_anonymous",
    "word_limit": 8000,
    "abstract": {"style": "structured", "word_limit": 250, "headings": ["Background", "Methods", "Results", "Conclusions"]},
    "references": {"style": "target style", "format_free": false},
    "figures": {"separate_files": true, "extensions": [".tiff", ".eps"], "minimum_dpi": 300},
    "source_ids": ["official-guide"]
  },
  "five_part_preferences": {
    "front_matter": {"preferred_moves": ["..."], "evidence_expectations": ["..."], "avoid": ["..."], "source_ids": ["official-guide", "recent-corpus"]},
    "introduction": {"preferred_moves": ["..."], "evidence_expectations": ["..."], "avoid": ["..."], "source_ids": ["recent-corpus"]},
    "methods_or_approach": {"preferred_moves": ["..."], "evidence_expectations": ["..."], "avoid": ["..."], "source_ids": ["recent-corpus"]},
    "results_or_analysis": {"preferred_moves": ["..."], "evidence_expectations": ["..."], "avoid": ["..."], "source_ids": ["recent-corpus"]},
    "discussion_and_conclusion": {"preferred_moves": ["..."], "evidence_expectations": ["..."], "avoid": ["..."], "source_ids": ["recent-corpus"]}
  },
  "compliance": {
    "coverage": [
      {"area": "title", "status": "known", "source_ids": ["official-guide"], "source_locator": "Title limits", "note": "Official maximum applies."},
      {"area": "abstract", "status": "known", "source_ids": ["official-guide"], "source_locator": "Abstract", "note": "Official maximum applies."},
      {"area": "body", "status": "known", "source_ids": ["official-guide"], "source_locator": "Article length", "note": "Official maximum applies."},
      {"area": "figures", "status": "not_applicable", "source_ids": ["official-guide"], "source_locator": "Figures", "note": "No separate count limit is stated for this article type."},
      {"area": "tables", "status": "not_applicable", "source_ids": ["official-guide"], "source_locator": "Tables", "note": "No separate count limit is stated for this article type."},
      {"area": "references", "status": "not_applicable", "source_ids": ["official-guide"], "source_locator": "References", "note": "No separate count limit is stated for this article type."},
      {"area": "attachments", "status": "not_applicable", "source_ids": ["official-guide"], "source_locator": "Submission files", "note": "No aggregate attachment-count limit is stated."},
      {"area": "required_sections", "status": "known", "source_ids": ["official-guide"], "source_locator": "Article structure", "note": "Named sections are required."},
      {"area": "required_materials", "status": "known", "source_ids": ["official-guide"], "source_locator": "Submission files", "note": "Named files are required."}
    ],
    "rules": [
      {"id": "title-words-max", "area": "title", "verification": "machine_verifiable", "metric": "word_count", "scope": "title", "operator": "max", "limit": 20, "unit": "words", "source_ids": ["official-guide"], "source_locator": "Title limits", "remediation": "Shorten the title while preserving the scientific identity."},
      {"id": "abstract-words-max", "area": "abstract", "verification": "machine_verifiable", "metric": "word_count", "scope": "abstract", "operator": "max", "limit": 250, "unit": "words", "source_ids": ["official-guide"], "source_locator": "Abstract", "remediation": "Compress the abstract without dropping supported findings."},
      {"id": "body-words-max", "area": "body", "verification": "machine_verifiable", "metric": "word_count", "scope": "body", "operator": "max", "limit": 8000, "unit": "words", "source_ids": ["official-guide"], "source_locator": "Article length", "remediation": "Move secondary detail to an allowed supplement."},
      {"id": "required-sections", "area": "required_sections", "verification": "machine_verifiable", "metric": "required_sections", "operator": "required", "limit": ["Introduction", "Methods", "Results", "Discussion"], "unit": "sections", "source_ids": ["official-guide"], "source_locator": "Article structure", "remediation": "Add the missing required section with supported content."},
      {"id": "required-files", "area": "required_materials", "verification": "machine_verifiable", "metric": "required_material", "operator": "required", "limit": ["main-manuscript"], "unit": "materials", "source_ids": ["official-guide"], "source_locator": "Submission files", "remediation": "Provide and validate every required file."}
    ]
  },
  "package_requirements": [
    {
      "id": "main-manuscript",
      "name": "Blinded main manuscript",
      "role": "main_manuscript",
      "disposition": "required",
      "condition_status": "applies",
      "accepted_extensions": [".docx"],
      "reuse_policy": "revalidate",
      "source_ids": ["official-guide"]
    },
    {
      "id": "reporting-checklist",
      "name": "Applicable reporting checklist",
      "role": "reporting_checklist",
      "disposition": "conditional",
      "condition_status": "unresolved",
      "accepted_extensions": [".docx", ".pdf"],
      "reuse_policy": "author_supply",
      "source_ids": ["official-guide"]
    }
  ]
}
```

`authority` is `official`, `published_corpus`, `user_supplied`, or `inferred`.
`reuse_policy` is `reuse_if_identical`, `revalidate`, `regenerate`, or
`author_supply`.

Every profile must carry exactly one coverage record for `title`, `abstract`,
`body`, `figures`, `tables`, `references`, `attachments`,
`required_sections`, and `required_materials`. Use `pending` rather than
guessing; `profile-check` blocks pending/missing coverage. Non-advisory rules
must cite an official source. See
`references/contracts/publication-target-profile.schema.json`.

## `submission_package_plan.json`

```json
{
  "schema_version": "1.0",
  "project_root": "../../..",
  "target_name": "Exact journal name",
  "target_profile_sha256": "64-hex profile hash",
  "compliance_inputs": {
    "manuscript_path": "final_paper/main.tex",
    "rendered_pdf_path": "final_paper/paper.pdf",
    "bibliography_paths": ["final_paper/references.bib"]
  },
  "author_confirmations": [
    {"id": "target_selected", "status": "confirmed"},
    {"id": "author_identity_and_order", "status": "confirmed"},
    {"id": "declarations_approved", "status": "confirmed"},
    {"id": "exclusive_submission", "status": "confirmed"}
  ],
  "items": [
    {
      "requirement_id": "main-manuscript",
      "status": "ready",
      "source_path": "final_paper/paper.docx",
      "output_name": "manuscript.docx",
      "transformation": "destination template + verified Word render",
      "validation_receipts": [
        {"path": "word_report.md", "sha256": "64-hex receipt hash"}
      ]
    }
  ],
  "forbidden_target_terms": ["Previous Journal Name"]
}
```

Item status is `ready`, `needs_author`, or `not_applicable`. The assembler
accepts only files, so a LaTeX project must first become a validated `.zip` or
other target-accepted source archive. `compliance_inputs.manuscript_path` is the
current project-local `.tex`, `.md`, or `.txt` authority used for writing-stage
and final deterministic rule checks; it may differ from an uploaded PDF/Word
artifact only when validation receipts prove the rendering is synchronized.

## `review_round.json`

```json
{
  "schema_version": "1.0",
  "project_root": "../../..",
  "decision_type": "major_revision",
  "round_number": 1,
  "round_id": "round-1",
  "cover_note": "Author-approved opening to the editor and reviewers.",
  "source_decision_files": [
    {"path": "decision-letter.pdf", "sha256": "64-hex source hash"}
  ],
  "comments": [
    {
      "id": "R1.C1",
      "reviewer": "Reviewer 1",
      "quoted_comment": "Exact atomic reviewer wording.",
      "quoted_comment_sha256": "SHA-256 of the UTF-8 quoted_comment string",
      "atomic_issue": "One independent concern or request.",
      "issue_type": "major",
      "strategy": "experiment",
      "author_intent": {"status": "confirmed", "position": "Run the requested bounded analysis."},
      "evidence": [
        {"id": "EV-R1-C1", "type": "new_analysis", "source": "results_validation.md", "verification_status": "verified"}
      ],
      "manuscript_changes": [
        {"locator": "Results, Robustness", "summary": "Added the verified analysis.", "status": "verified", "evidence_ids": ["EV-R1-C1"]}
      ],
      "response": {"status": "final", "final_text": "Author-approved response text."}
    }
  ],
  "revalidation": [
    {"dimension": "scientific_content", "status": "passed", "path": "scientific-evidence-check.md", "sha256": "64-hex receipt hash"},
    {"dimension": "visual", "status": "passed", "path": "visual_readiness_check.md", "sha256": "64-hex receipt hash"},
    {"dimension": "citation", "status": "passed", "path": "citation_bank_check.md", "sha256": "64-hex receipt hash"},
    {"dimension": "metadata", "status": "passed", "path": "metadata_readiness_check.md", "sha256": "64-hex receipt hash"},
    {"dimension": "artifact", "status": "passed", "path": "artifact_check.md", "sha256": "64-hex receipt hash"}
  ]
}
```

For later rounds add:

```json
"previous_round": {"path": "../round-1/review_round.json", "sha256": "64-hex hash"}
```

## `transfer_request.json`

```json
{
  "schema_version": "1.0",
  "project_root": "../../..",
  "origin_target": "Previous Journal",
  "selected_target": "Destination Journal",
  "selected_target_confirmed": true,
  "user_named_destination": false,
  "user_preferences": {
    "must_haves": ["indexed in the user's required database"],
    "nice_to_haves": ["format-free first submission"],
    "deal_breakers": ["mandatory APC above the confirmed budget"],
    "budget_or_access": "Author-confirmed statement",
    "timing": "Author-confirmed statement",
    "format_preferences": ["Word accepted"]
  },
  "candidate_comparison": [
    {"target": "Destination Journal", "verdict": "submit", "reasons": ["..."], "tradeoffs": ["..."]},
    {"target": "Alternative Journal", "verdict": "reshape", "reasons": ["..."], "tradeoffs": ["..."]}
  ],
  "fit_assessment": {"verdict": "submit", "reasons": ["..."], "reshape_actions": []},
  "paper_identity": {
    "canonical_manuscript": {"path": "final_paper/main.tex", "sha256": "64-hex hash"},
    "confirmed_contribution": {"path": "confirmed_contribution.md", "sha256": "64-hex hash"},
    "claim_boundary": "Confirmed boundary",
    "confirmed": true
  }
}
```

If the fit verdict is `reshape`, add non-empty `reshape_actions` and
`reshape_confirmed: true`. A `redirect` verdict blocks the destination rebuild.
