# Vibe-Skills Verification

This context defines the testing and verification language for the Vibe-Skills repository. It exists so contributors can talk about proof, audits, and regression scope with the same meaning.

## Language

**Default Regression Set**:
The small always-run verification set that protects the repository's real runtime abilities and public contracts.
_Avoid_: Full sweep, everything gate, all checks

**Optional Audit**:
A non-default check that is only run when a change touches the surface that the audit exists to inspect.
_Avoid_: Default regression, mandatory gate, always-on proof

**Behavior Contract Test**:
A test that proves externally visible behavior, artifact shape, or command contract rather than internal wording or implementation layout.
_Avoid_: Wording test, implementation-style test, history-preservation test

**Capability-Based Verification**:
A way of organizing proof around the user-facing ability being protected, such as install, runtime entry, routing, or truth artifacts.
_Avoid_: Directory-based verification, filename-based verification, suite-sprawl

**Core Capability**:
A user-visible ability that must keep working for the repository to remain trustworthy, such as install, runtime entry, routing, or truth-artifact generation.
_Avoid_: Historical cleanup topic, wording concern, archive housekeeping

**Touched-Surface Proof**:
Verification that only becomes necessary when a change actually modifies the surface being protected, such as packaging, release, or mirror hygiene.
_Avoid_: Always-on regression, default closure, universal gate

**Delivery Hygiene**:
Checks that keep a change clean to review and ship, such as patch formatting or repo cleanliness, without proving a product ability by themselves.
_Avoid_: Core capability proof, runtime contract proof, behavior guarantee

**Failure-First Test**:
A test written from the expected user-visible failure or contract breakage, so it can fail for a meaningful reason before the implementation is corrected.
_Avoid_: Snapshot of current wording, implementation freeze, repository grep

**TDD Test Intent**:
The discipline that a test should state the capability promise first, then drive the implementation toward satisfying that promise with the smallest necessary proof.
_Avoid_: After-the-fact assertion pile, historical cleanup lock, style policing by test

**Live Contract**:
A stable, undated normative contract that defines current repository behavior and may be consumed by the runtime or default verification.
_Avoid_: Current plan, dated status page, historical proof

**Entry Document**:
A human-facing navigation or operating guide that points readers to live contracts without owning runtime truth.
_Avoid_: Canonical contract, executable policy

**Release Artifact**:
Run-specific requirements, plans, status, and proof retained with CI or a release instead of the tracked live documentation surface.
_Avoid_: Live documentation, permanent repository status page

**Historical Record**:
Completed or superseded governance material preserved through Git history or release artifacts and excluded from the live control plane.
_Avoid_: Current contract, default verification dependency

**Live Documentation Budget**:
The bounded set of tracked human-facing Markdown documents maintained as current repository guidance, capped at thirty documents across the root, `docs`, and `references` surfaces.
_Avoid_: Unbounded archive, dated worklog collection
