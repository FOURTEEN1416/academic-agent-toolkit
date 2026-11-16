# Execution Efficiency and Exact Reuse

Reuse useful work and stop unproductive retries without skipping requested science.
This method supports current-scope delivery; it does not introduce new status gates.

## One-Read Instruction Set

1. For the current public host workflow, read `SKILL.md`, this file and
   `product-v1-workflow.md`. Read applicable scientific methods through
   `current-method-routing.md`; old `resume.md` and `product-runner-host-route.md`
   administrative commands apply only to an explicitly selected legacy Runner.
2. Read the applicable method for the actual work, including dependencies it
   names. A stage label does not replace the original scientific method.
3. Keep a compact continuation note containing the same profile/task, actual
   task version, last consumed event sequence, relevant source/output paths,
   pending decision and next action. Runner tokens/revisions and gate receipts
   belong only to an explicit legacy workflow.
4. Reuse valid unchanged outputs. Do not replay the complete task history or
   reload every source on each iteration; recover only missing context needed for
   the next action. Verify consequential notes against original passages.
5. Read large evidence by page/section/line range and save source coordinates.
   Tool-output summaries never replace the underlying hash-bound source.
6. Before a full-file read, record its path, byte size, SHA-256, and intended
   line range in the compact checkpoint. Never batch several full-file reads
   when their combined bytes can exceed the tool-output budget. If output is
   truncated, request only the unread line range; never restart at line 1.
7. Artifact reuse and method recall are different. After context loss, reopen
   original passages needed for the next action even if the file is unchanged.
   Read the full method if the scope cannot be located reliably. A past read marker
   is not knowledge; necessary recovery is not a `repeated_read_miss` and needs
   no telemetry receipt.

A new task version (or explicit legacy Runner revision), material snapshot, manuscript hash, target, or user
authority can invalidate the relevant checkpoint fields. Reload only the
changed authority and downstream playbooks.

## Expensive Operation Receipt

When exact caching is useful, the existing optional helper can check a task-local
receipt. Do not require receipt creation for ordinary paper work:

```bash
python scripts/execution_receipt.py check \
  --receipt paper_rewriting_output/execution_receipts/pdf-render.json \
  --operation pdf-render --tool "pdftoppm@<exact-version-or-path>" \
  --input paper_rewriting_output/final_paper/paper.pdf \
  --output paper_rewriting_output/visual_audit/pages
```

- Exit `0` / `REUSABLE`: operation, tool identity, complete input snapshot,
  and complete output snapshot match. Reuse the output.
- Exit `3` / `MISS`: run the operation once, validate the result, then record
  the new receipt with the same arguments and `record` instead of `check`.
- Exit `2` / `ERROR`: repair malformed or missing receipt inputs; do not call
  this a cache hit.

Store receipts under `paper_rewriting_output/execution_receipts/`, outside the
output directory being hashed. Use separate receipts for PDF rendering, DOCX
rendering, format conversion, citation-audit snapshots, and other expensive
deterministic operations. Include every input that can change the result and an
exact executable/version/config identity in `--tool`.

Receipt reuse proves only computational identity. It does not infer
`scientific_content_ready`, `visual_ready`, citation correctness, author
approval, submission readiness, or authorization. Human or multimodal
inspection may be reused only for the same actually inspected objects and unaffected
dependencies. A receipt identifies bytes, not inspection or quality. `visual_readiness_check.py --prepare` preserves an
exact current visual manifest and completed inspection; any bound PDF, TeX,
`figure_requests.json`, figure asset, render, or DPI change rebuilds it as
pending.

## Renderer Preflight

Discover renderer availability once per environment and record the selected
executable/version in the receipt. Do not repeatedly invoke missing backends.

- PDF page rendering: preflight `pdftoppm` and `pdfinfo` once.
- DOCX surface rendering: choose one available, policy-compatible renderer
  after preflight. On Windows, Word automation may be used when available;
  LibreOffice may be used only when its executable is actually present.
- A renderer failure does not authorize changing manuscript content. Preserve
  the source and record the exact command, exit status, and first actionable
  error.

## Bounded Failure Recovery

For one command and one unchanged input snapshot:

1. Run once.
2. Classify the failure: input, dependency, environment, transient provider,
   permission, contract, or scientific blocker.
3. Make one concrete corrective change, then retry once.
4. Never run a third materially identical attempt. Report the blocker, exact
   evidence, responsible owner, and recovery action instead.

Changed inputs or restored dependencies may justify a retry; a new hash, filename
or task version alone does not reset an unchanged defect. After two targeted fixes
leave the same problem unimproved, change the layout/method rather than keep nudging
coordinates. Preserve a usable version and stop optional polish; do not present an
incorrect number, unreadable label or misleading relation as if it were fixed.

When a task produces no events, inspect the exact task once, perform one
bounded wait, then one final state read. Do not spin on unchanged task or thread
state. A clean replacement task is allowed only when the user requested a clean
simulation or run; it must use a new output root and may not import answers or
completion artifacts from the failed task.

## Incremental Work, One Final Full Pass

Check affected files and their downstream use. Before requested complete-paper
delivery, inspect whole-paper consistency and actual requested formats. Fix owning
sources and recheck affected outputs; a focused review or minor correction does not
require every historical audit command or a mandatory extra full pass.

Record measured tokens, elapsed time, retry number, reuse or miss status,
receipt path, input hashes, and output artifacts in `usage_ledger.jsonl` when
the host exposes them. Never estimate billed tokens from file size.
