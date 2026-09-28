# Superseded Dynamic Substage Policy

This file is retained only for compatibility with older package references. In v3.2.15f, the active policy is:

- `references/s2-s5-image-only-terminal-orchestration-policy-v3215.md`

The active workflow no longer uses text/image/text candidate substages. S1 prepares S2 prompts, S2 only generates images, S3 reviews/aggregates S2 and selects direction, S4 prepares S5 prompts, S5 only generates images, and the assistant workflow ends.

In v3.2.15f, candidate and artifact IDs are governed by `references/candidate-artifact-id-coherence-policy-v3215.md`; prompt-index `candidate_id` must not be rewritten by later stages or scripts.
