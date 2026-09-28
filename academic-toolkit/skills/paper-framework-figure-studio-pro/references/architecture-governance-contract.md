# Architecture Governance Contract v3.1.9

The skill is modular and human-in-the-loop.

- **Loose coupling:** each public stage reads registered upstream artifacts and writes its own output root.
- **High cohesion:** state helpers each own one narrow task.
- **Layered on-demand calls:** load detailed reference files only when the current step needs them.
- After S5, human decisions are outside this assistant workflow.
- **Failure resume:** cumulative checkpoints must restore from S0 to the current substage.
- **Abstraction:** workflow stages and artifact roles are declared in constants and project state.
- After S5, human decisions are outside this assistant workflow.
- **Retrievability:** canonical outputs and registries make generated material discoverable after resume.
- **Vulnerability checks:** validation rejects unsafe paths, forbidden target-image substitutes, and secret-like keys.

After S5, human decisions are outside this assistant workflow.
