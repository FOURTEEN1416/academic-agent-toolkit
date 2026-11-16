---
name: bionemo-nims
description: Run NVIDIA BioNeMo NIMs through the hosted scientific_capability tool with your own NVIDIA API key. Boltz-2 and OpenFold2/OpenFold3 structure prediction, MSA Search alignments, DiffDock docking, ProteinMPNN sequence design, RFdiffusion backbones, GenMol and MolMIM molecule generation, Evo 2 genomic sequence modeling. Use when a request names one of these models, "BioNeMo", "NIM", or asks for a hosted structure, docking or design prediction; not for self-hosted containers on Modal (see protein-binder-design).
summary: "Hosted NVIDIA BioNeMo NIMs via scientific_capability: list, describe, plan, start, wait, artifacts; one approval per request."
category: biology
tags:
  - bionemo
  - nvidia
  - structure-prediction
  - docking
  - protein-design
role: workflow
allowed-tools: [scientific_capability, read, artifact]
license: CC-BY-4.0
metadata:
  skill-author: Synthetic Sciences
  upstream: NVIDIA-BioNeMo/bionemo-agent-toolkit
  upstream-license: CC-BY-4.0 (skills) / Apache-2.0 (code)
version: 1.0.0
---

# NVIDIA BioNeMo NIMs (hosted)

The ten BioNeMo NIM adapters run against NVIDIA's hosted endpoints with the user's own
NVIDIA API key. Every request goes through the `scientific_capability` tool; nothing here
installs software or starts compute. The capability ids are `boltz2`, `openfold2`,
`openfold3`, `msa-search`, `diffdock`, `proteinmpnn`, `rfdiffusion`, `genmol`, `molmim`
and `evo2`.

## Before the first request

- `scientific_capability` with `action: "list"` shows the catalog and each entry's maturity.
  `action: "doctor", id: "<id>"` says whether the NVIDIA key is connected and the endpoint
  is reachable. Without a key, stop and tell the user: connect one under
  **Customize → Connectors → NVIDIA API** (an `nvapi-…` key from build.nvidia.com); requests
  are billed to that NVIDIA account under NVIDIA's terms. Do not look for the key in the
  environment, in compute targets, or in Modal secrets; the hosted route is separate from the
  self-hosted BioNeMo containers that `protein-binder-design` runs on Modal.
- `action: "describe", id: "<id>"` returns the hosted `request_schema`, the endpoint, the API
  schema version and the terms. Build `payload` from that schema exactly; field names and
  enumerations differ between NIMs (a sequence list for Boltz-2, a PDB string plus ligand
  SMILES for DiffDock, an alignment for OpenFold2).

## Each request

1. `action: "plan", id, payload` validates every cross-field requirement locally. Nothing is
   sent and nothing is spent. Fix what it reports before going on.
2. `action: "start", id, payload, name, purpose` sends the request. The user sees an approval
   card bound to this exact request: endpoint, schema version, payload size, request hash and
   what leaves the device (sequences, structures, ligands). The approval is one-time; a
   changed payload asks again. Say in `purpose` what the result is for.
3. `action: "wait", job_id` (or `status`) until it settles; long predictions poll NVIDIA's
   status endpoint for you. `action: "artifacts", job_id` lists the delivered files with
   their SHA-256; `read` a structure or JSON from there, and save what the user keeps with
   `artifact save_file`.
4. Report the model, the API schema version from `describe`, the request hash and the
   artifact hashes with the result. A predicted structure or pose is a prediction: give its
   confidence (pLDDT, iptm, DiffDock confidence) and never call it experimental validation.

## Choosing a NIM

| Need | Capability |
| --- | --- |
| Protein or complex structure from sequence, ligands and ions allowed | `boltz2` |
| Monomer structure from an MSA (`msa-search` first) | `openfold2` |
| Complex structure with templates | `openfold3` |
| Protein–ligand poses for a given pocket | `diffdock` |
| Sequences for a fixed backbone | `proteinmpnn` |
| New backbones or binders against a target | `rfdiffusion` |
| Small molecules from a fragment or property target | `genmol`, `molmim` |
| DNA sequence generation and scoring | `evo2` |

For a full binder campaign (RFdiffusion → ProteinMPNN → Boltz-2 refold → ranking), load
`protein-binder-design`, which chains these the way the BioNeMo Agent Toolkit does.
