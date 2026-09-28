# Degrade Replay Fixtures

These fixtures encode **explicit degrade/abstain behavior** when a provider is missing.

The goal is to prove:

- Missing credentials do not cause silent behavior changes.
- The system emits an explicit, machine-readable "abstained" state with a reason code.

Validated by: `scripts/verify/vibe-cross-host-degrade-contract-gate.ps1`

