# Prompt Generation Policy v3.2.15f

Long image prompts must be saved to files and referenced through `prompt-index.json`; user-visible handoff text must not inline full multi-candidate prompts.

S1 prepares exactly four S2 first-round prompts after planning eight complementary style-combination proposals and selecting the top four. S4 prepares exactly two S5 formal-candidate prompts. S2 and S5 only read those prompts and generate images using the environment-locked image route.

Prompt packages must remain paper-grounded: semantic graph and visual render graph are separated, visible text is whitelisted, edge direction is evidence-backed, variables/metrics/weights default to line/port/fork/merge/tag labels, and core modules include simple pictorial internal motifs.

S1/S4 prompt packages must also include `palette_strategy`, `palette_semantic_mapping`, `palette_anti_ai_artifact_rules`, `human_aesthetic_rationale`, and `color_accessibility_note`. Use restrained publication-grade palettes with paper-supported color semantics, grayscale legibility, accessible contrast, and no generic AI-blue/purple gradients, neon saturation, glossy orb/glass effects, bokeh, marketing-poster lighting, or decorative rainbow ramps.

S1/S4 prompt generation must apply `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md`. In particular:

- every connector must have paper/material support for upstream endpoint, downstream endpoint, direction, transferred meaning, and the true consumer/transformer of every carried item;
- between two block-level modules, use a single bundled connector unless distinct source-supported transferred quantities justify multiple labeled connectors;
- do not draw false relay data-flow edges through modules that do not consume, transform, filter, store, route, evaluate, update, or emit the carried item;
- inter-module variables must appear on connectors, ports, forks, merges, or small tags, not as peer module boxes;
- the figure must be modular, not fragmented into many small disconnected micro-blocks;
- internal submodule motifs must be simple and reviewer-recognizable, using common schematic conventions instead of complex miniature algorithms;
- do not duplicate a workflow across a main block and a zoom/cutaway; if a cutaway is needed, simplify the parent block;
- keep background/context minor and preserve method-framework priority.

S1/S4 must audit and repair prompt packages for these conditions up to five cycles. If blockers remain after the fifth cycle, stop before image-generation handoff and write a residual-risk ledger.

When S1 records active first-round `style_id` or `first_round_style_surface: acm_ieee_aaai_line_art_schematic`, each affected S2 prompt package must include the prompt block from `references/acm-ieee-aaai-line-art-schematic-style-policy-v3215c.md`. When S4 records active second-round `style_id: acm_ieee_aaai_line_art_schematic`, each affected S5 prompt package must include the same prompt block. This surface style is optional and must not be injected unless explicitly requested in the S1 prompt after a non-copyable first-round surface-style note, or in the S4/S5 prompt or S3-to-S4 handoff for the second round. Optional surface-style menus must be shown outside copyable suggested prompt blocks at S0-to-S1, S1-to-S2, and S3-to-S4. The S1-to-S2 note is informational only: because S2 follows the S1 prompt-index, changing the first-round surface after S1 requires rerunning S1 before S2. S4-to-S5 must not repeat a second-round surface-style reminder. If the explicit second-round request appears only in the current S5 image-only prompt, S5 may apply the style block at image-prompt assembly time without creating a text planning step or changing prompt-index ids/paths.

A surface style is never the whole candidate style. S1/S4 prompt packages must combine it with the candidate's narrative role, layout grammar, semantic emphasis, density budget, connector hierarchy, and paper-source constraints.

No prompt generation stage exists after S5.
