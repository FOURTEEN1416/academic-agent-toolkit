# Contributor Zone Decision Table

Use this table before editing files.

If you cannot classify your target path confidently, treat it as guarded and
read [`../docs/developer-change-governance.md`](../docs/developer-change-governance.md)
before continuing.

| Zone | Typical paths | Ordinary contributor default | Read first | Minimum proof floor | Stop and escalate when |
| --- | --- | --- | --- | --- | --- |
| `Z0 Frozen Control Plane` | `install.*`, `check.*`, `SKILL.md`, `protocols/**`, `scripts/router/**`, routing locks and manifests | No | [`../docs/developer-change-governance.md`](../docs/developer-change-governance.md) and the relevant plan | Plan first, then runtime proof bundle | You are changing install, routing, protocol semantics, or default runtime behavior |
| `Z1 Guarded Governance and Policy` | `config/**` outside frozen routing files, `hooks/**`, `rules/**`, `agents/**`, root `README.md`, `LICENSE`, `NOTICE`, `THIRD_PARTY_LICENSES.md` | Only with explicit scope and updated docs | [`../docs/developer-change-governance.md`](../docs/developer-change-governance.md) | Relevant gate set plus updated public docs | You are changing public promises, policy, disclosure, or governance without matching evidence |
| `Z2 Guarded Mirror, Fixture, Provenance, and Compliance` | `bundled/**`, `references/fixtures/**`, tracked `outputs/**`, `third_party/**`, `vendor/**` | No mirror-first edits | [`../docs/developer-change-governance.md`](../docs/developer-change-governance.md) and the source-of-truth doc | Canonical-first sync plus parity, boundary, and provenance proof | You cannot point to the canonical source, provenance record, or required sync path |
| `Z3 Preferred Contribution Zones` | `docs/**`, `references/**` except fixtures, `scripts/governance/**`, `scripts/verify/**`, `templates/**` | Yes | [`../CONTRIBUTING.md`](../CONTRIBUTING.md) | `git diff --check` and path/link sanity at minimum | The change starts leaking into frozen, mirrored, or runtime-sensitive paths |

## Quick Rules

- Default to `Z3`.
- Never treat `bundled/**` as editable source.
- Never treat tracked `outputs/**` as hand-maintained source.
- If a docs change changes public guarantees, it is not "just docs"; re-check
  the proof matrix.
