# P15 attempt 1 — partial Tara Oceans analysis with invalid ranking

## Outcome

The run failed after 5,572 seconds when the final provider request became idle. One child completed and the root wrote substantial analysis code and tables, but no user-facing response or explicit Result was delivered.

Evidence bundle:

`~/.openscience-dev/researchagent-test/campaigns/run-2026-08-27T06-51-49-108Z-p15-08200db5/runs/p15`

The session-owned workspace remains at:

`~/.openscience-dev/researchagent-test/data/workspaces/prj_64a5dffac2294560a40032e91fe7309d/ses_fbe02c743ffe1fq7tFENFLVQ2o`

## Scientific review

- The BioSample join was exact and one-to-one for 93 samples. The agent recovered from unavailable Excel packages with a dependency-free XLSX reader and produced reproducible intermediate tables.
- The requested ranking is invalid. The analysis CLR-transformed Table S12's 1,077 redundant-reference distributions and only then removed nonrepresentatives. The official workflow remaps reads in Table S3 against the final 957-MAG nonredundant catalog; filtering competing references after mapping is not equivalent.
- An independent unchanged-model recomputation on Table S3 retained only 2 of the frozen top 10. One frozen leader changed from a significant positive silicate association to beta approximately -0.03 and global q approximately 0.94.
- Rare-MAG filtering was effectively vacuous, occurred after CLR, and used abundance greater than zero rather than a prespecified detection rule. LORO stability meant point estimates kept one sign, not that fold-specific uncertainty excluded zero.
- Separate correlated-nutrient regressions did not establish nutrient-specific attribution. The missing final response also meant no causal caveat, alternative-explanation synthesis, or nitrate-by-phosphate validation experiment reached the user.

This exact ranking must be discarded. The fresh rerun should discover and use Table S3 itself; the harness should not encode a Tara-specific source rule.

## General harness findings

1. A preceding `ECONNRESET` incremented the shared retry counter and silently consumed the one side-effect-free idle replay. Transient retries and the idle replay need independent state.
2. Every Bash call synchronously bootstrapped both Python and R. The R starter had been solved under a random staging prefix and renamed, leaving macOS dylib paths pointed at a deleted directory. Each shell call detected the broken R environment, rebuilt it, and broke it again. Sixteen P11 Bash calls each created one rollback; the isolated profile accumulated 133 rollback copies.
3. Four parallel shell launches waited behind environment repair inside the global spawn-authority lease and timed out. The safety lease should remain, but environment discovery/provisioning must finish before acquiring it.
4. A universal five-minute raw-body inactivity deadline was neither a semantic-progress deadline nor diagnostically useful. The route produced decoded progress and then later failed after a much longer visible gap. Inactivity limits should be explicit/route-configured rather than an arbitrary default.
5. The runner considered only final assistant text and explicit Results usable. It preserved path/size metadata for 23 files but copied none of the scripts, JSON audit, or analysis tables, so a late provider failure made 52 minutes of completed work appear empty.
6. The child returned a useful source/join memo, but the root repeated much of the acquisition work. This is an efficiency observation, not a reason for a new delegation quota or controller workflow.

## General corrections before rerun

- Keep transient retry accounting separate from the one idle replay.
- Solve Conda environments at their durable final prefixes, cache readiness per language, and never make Python execution validate or repair R.
- Resolve managed environments before the global process-spawn authority lease while revalidating authority immediately before spawn.
- Disable the universal provider inactivity cutoff by default; retain caller cancellation and explicit route/total limits.
- Freeze a bounded, hashed snapshot of session-owned code and outputs on every terminal run. Keep it distinct from durable Results and inherited read grants; classify an error after recoverable outputs as partial.
- Settle SDK SSE cancellation even when the underlying reader rejects its cancellation promise.

## Verification

- Focused environment, shell, provider, retry, WebFetch, and runner tests: 129 passed.
- SDK runtime tests: 6 passed.
- Backend TypeScript check passed.
- Repaired R starter launches from its durable prefix; 5.6 GB of broken generated rollback/staging residue was identified for cleanup.
