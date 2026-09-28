# Runtime Contract Proof

Tracked governed-runtime replay goldens are no longer retained in this directory.

Current governed-runtime verification is artifact-driven:

- `scripts/verify/vibe-governed-runtime-contract-gate.ps1` runs a fresh governed-runtime smoke flow
- the gate validates required files, stage-specific artifacts, frozen `$vibe` routing, and specialist-dispatch invariants

This keeps runtime proof aligned with the live governed runtime instead of preserving stale replay snapshots.
