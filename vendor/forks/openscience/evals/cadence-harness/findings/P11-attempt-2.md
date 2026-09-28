# P11 attempt 2 — completed plant-genomics panel

## Outcome

The fresh rerun completed in 971 seconds with a normal user-facing response and a valid Result bundle. It used 40 model calls and 91 tool calls for $1.32 in recorded inference cost. No subagents or remote compute were needed.

Evidence bundle:

`~/.openscience-dev/researchagent-test/campaigns/run-2026-08-27T06-24-17-601Z-p11-09413761/runs/p11`

## Deliverable review

- The bundle contains 21 files: a 24-accession panel, locus hypotheses, ancestry-stratified meta-analysis, leave-one-group-out results, population diagnostics, the 768-row factorial randomization, source-derived intermediates, scripts, a figure, README, and report.
- The accession table has 24 unique accessions across 10 ancestry labels, with no label represented more than four times.
- The randomization is a complete 24 accession × 2 drought × 2 heat × 8 replicate design. Every treatment cell contains 192 plants and every accession contributes 32 rows.
- The figure is a valid 1980×810 PNG with readable ancestry/genomic-PC and provenance-climate panels.
- Claims remain appropriately associational. The report explains climate/ancestry confounding, marker sparsity, and the need for common-garden validation.
- No LaTeX/PDF was requested by P11, so their absence is not a deliverable failure.

## General harness findings

1. The trajectory runner aborted a healthy SSE after five quiet seconds, switched to durable polling, then allowed Bun's internal AbortError to make the wrapper exit nonzero after the run had completed. A live research stream must not treat normal reasoning silence as a stalled connection.
2. The dev permission pump rejected managed environment mutation despite this explicitly authorized local campaign. The agent recovered by manually downloading a compatible wheel, but that was slower and less representative than the product path.
3. The phrase `provenance climate` accidentally activated the provenance-recording tool four times. Scientific nouns are not an explicit request for a provenance workflow.
4. The Result is scientifically useful but not independently regenerable from the ZIP alone: it lacks an environment lock and an exact raw-source acquisition/checksum manifest. This is a cross-task research-execution gap to monitor in P15 before adding any new controller ceremony.
5. Skill search returned unrelated specialties and the agent correctly ignored them. A low-confidence result should eventually be empty rather than distracting, but one run is not enough evidence for a routing change.

## Corrections before P15

- Preserve the live SSE by default; only an explicit diagnostic stall setting may force replay.
- Allow a scoped managed-environment mutation in explicitly authorized dev runs while keeping batch campaigns fail-closed by default.
- Require an action phrase such as “record provenance” before exposing provenance tools.
- Record cancellation intent first, let abort-aware tools and the assistant message settle, and append `runtime.cancelled` last so the captured trace is complete.

## Verification

- Runtime cancellation tests: 25 passed.
- Tool-selection and cadence-runner tests: 36 passed.
- Backend TypeScript check and `git diff --check` passed.
