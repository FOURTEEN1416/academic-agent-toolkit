# Bundled Skill Retention Matrix

## Conclusion

The current product runtime does not expose a built-in specialist starter set.

The default `minimal` and `full` profiles expose the Vibe controller and public wrapper entries. Specialist capability comes from host-declared local skill roots with readable `SKILL.md` files.

Anything that still exists under historical `bundled/skills/` paths should currently be read as reference corpus or migration-era residue, not as the default public extension story or an execution authority.

## Why This File Exists

The repo may still contain bundled skill references in historical plans, tests, or migration documents. That physical or textual count is not the same thing as the live specialist surface.

The runtime benchmark, install story, and packaging inventory now use the packaging contract as the source of truth:

- `minimal` is the default profile
- the live built-in specialist count is `0`
- `full` does not add an internal specialist corpus
- raw folder count under historical `bundled/skills/` paths is not the runtime specialist count

## Retention Matrix

| Bucket | Current rule | What belongs here now | Public story |
|:---|:---|:---|:---|
| Built-in specialist set | Disabled for product runtime execution. | No specialist skill belongs here in `minimal` or `full`. | Do not describe built-in specialists as live. |
| External or reference corpus | Keep repo-owned historical or migration materials only as source material, not as a default starter claim. | Historical `bundled/skills/*` references and archived material that may still be useful for migration review. | Do not present this bucket as the normal extension path. The normal story is host-managed and user-owned local roots only. |
| Archive or migration residue | Use this bucket only when a skill or note has been explicitly moved out of the active bundled tree into a history or migration holding area. | No skill directory is moved into this bucket by Task 6. If a later bounded cleanup pass relocates material, it should land under `references/bundled-skill-corpus/` or `docs/archive/bundled-skill-history/` with a narrow proof note. | This bucket exists to keep history honest, not to expand the runtime story. |

## Current Decision

This pass does not force a broad historical-document move.

That is deliberate:

- the package contract already disables the internal specialist corpus
- runtime authority now comes from local installed skill roots
- a broad historical archive move would touch guarded surfaces and create more risk than this alignment pass needs

## Impact

This lets the public docs and benchmark say something simple and true:

- the default product story is a controller plus local installed skills
- the optional `full` profile does not add built-in specialist execution
- historical bundled references are not the runtime extension story
- any future physical move should happen as a separate bounded cleanup with its own proof
