# Core Contract Layer

`core/` holds the first host-neutral skill contracts extracted from the current official runtime.

## Principles

- additive only during early universalization
- no replacement of runtime `SKILL.md`
- canonical contract points back to bundled source truth
- compatibility and degrade behavior are explicit

## First Extraction Set

The first wave intentionally freezes only the smallest universalization-critical skills:

- `vibe`
- `tdd-guide`
- `systematic-debugging`
- `code-reviewer`
- `brainstorming`
- `writing-plans`
- `subagent-driven-development`

These are enough to define routing, implementation, debugging, review, and planning entry behavior without trying to normalize the entire skill corpus in one batch.

