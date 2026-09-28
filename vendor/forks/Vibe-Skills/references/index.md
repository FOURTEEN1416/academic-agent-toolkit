# VCO References Index

`references/` contains the maintained contributor and verification contracts.
Runtime truth lives in executable configuration and per-run artifacts.

## Start Here

- [`contributor-zone-decision-table.md`](contributor-zone-decision-table.md)
  classifies repository surfaces before editing.
- [`change-proof-matrix.md`](change-proof-matrix.md) maps change classes to
  the smallest required evidence.
- [`developer-entry-contract.md`](developer-entry-contract.md) defines the
  stable contributor entry path.
- [`../config/live-document-contract.json`](../config/live-document-contract.json)
  is the machine-readable live-document and artifact-sink contract.

## Adjacent Surfaces

- [CI proof](https://github.com/foryourhealth111-pixel/Vibe-Skills/actions/workflows/vco-gates.yml)
- [Latest GitHub Release metadata](https://github.com/foryourhealth111-pixel/Vibe-Skills/releases/latest)
- [`../scripts/verify/gate-family-index.md`](../scripts/verify/gate-family-index.md)
- [`../docs/README.md`](../docs/README.md)

## Rules

- Every maintained Markdown document under the governed roots is registered in
  the live-document contract.
- Time-bound execution evidence belongs to the run artifact sink, CI, or a
  formal release artifact.
- `bundled/skills` and legal/provenance material follow their separate
  retention contracts.
