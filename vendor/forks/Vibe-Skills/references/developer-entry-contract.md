# Developer Entry Contract

Up: [index.md](index.md)

This contract defines the minimum stable developer-entry verification surface.

Scope for this slice:
- Verify the repository exposes a canonical developer-entry path.
- Verify `CONTRIBUTING.md` exists and points contributors to zone, proof, and executable live-contract surfaces.
- Verify only documentation and verification entry surfaces.

Out of scope for this slice:
- PR template enforcement
- Canary contributor journey execution
- Runtime/router/install non-regression gates beyond linking to their proof surface

<!-- developer-entry-contract:start -->
```json
{
  "contract_version": 1,
  "root_entry": {
    "path": "README.md",
    "required_links": [
      "CONTRIBUTING.md"
    ]
  },
  "developer_entry": {
    "path": "CONTRIBUTING.md",
    "required_files": [
      "docs/developer-change-governance.md",
      "references/contributor-zone-decision-table.md",
      "references/change-proof-matrix.md",
      "config/live-document-contract.json"
    ],
    "required_links": [
      "docs/developer-change-governance.md",
      "references/contributor-zone-decision-table.md",
      "references/change-proof-matrix.md",
      "config/live-document-contract.json"
    ],
    "required_marker_groups": [
      [
        "Z0",
        "Frozen Control Plane"
      ],
      [
        "Z3",
        "Preferred Contribution Zones",
        "Default Safe Contribution Path"
      ],
      [
        "default safe contribution path",
        "默认安全工作面"
      ],
      [
        "proof bundle",
        "required proof",
        "验证"
      ]
    ]
  },
  "artifact_output": {
    "json": "outputs/verify/vibe-developer-entry-gate.json",
    "markdown": "outputs/verify/vibe-developer-entry-gate.md"
  }
}
```
<!-- developer-entry-contract:end -->

## Contract Semantics

- `root_entry.required_links`: the canonical root README must expose a direct developer-entry jump.
- `developer_entry.required_files`: the downstream governance files that must exist for the entry path to be considered structurally complete.
- `developer_entry.required_links`: the documents that must be reachable directly from `CONTRIBUTING.md`.
- `developer_entry.required_marker_groups`: contributor-facing content signals that prove the entry doc is describing zone boundaries and proof expectations, not just linking around them.

## Gate Result Meaning

- `PASS`: the developer-entry path is structurally present and contributor-facing guidance is linked and visible.
- `FAIL`: at least one required file, link, or marker group is missing. This is a documentation and governance gap, not a runtime mutation.

## Evidence Standard

Use the developer-entry gate with the normal proof format:

- Command
- Output
- Claim
