# Paper-Neutral Hardcoding Lint Policy v3.2.15f

Reusable skill files must not contain target-paper facts. Project-specific facts, modules, variables, datasets, topologies, and forbidden items belong only in run outputs.

## Active-core lint

Before packaging, scan active reusable files such as `SKILL.md`, scripts, templates, examples, metadata, publish text, and non-vector policy references for accidental target-paper bindings. The scanner should accept a configurable denylist supplied at release time and must not hard-code a specific paper topic.

## Vector-library exception

Icon and motif libraries may contain many domain terms. They are not prompt doctrine. During prompt generation, a motif can be used only if the current paper source, S0 report, S1/S4 brief, or user constraints justify it. Retrieval metadata alone is not evidence.

## Coding rule

Detection code must derive candidate IDs, counts, paths, stages, and styles from prompt-index rows, manifests, state, and files. It must not hard-code candidate image counts, page counts, project IDs, or target-paper module names.
