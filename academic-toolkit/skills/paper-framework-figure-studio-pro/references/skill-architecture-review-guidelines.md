# Skill Architecture Review Guidelines

Review architecture changes against these checks:

- Workflow constants, state schema, artifact roles, image generation gates, cleanup helpers, and release checks remain separate.
- After S5, human decisions are outside this assistant workflow.
- S2/S5 target images remain generated raster images.
- S5 formal candidates are schematic raster references with paper-relevant icons, precise arrows/colors, visible core anchors, and style-aware caption plans; they are not SVG outputs.
- After S5, human decisions are outside this assistant workflow.
- State files store relative paths only.
- Release packages contain no caches, temporary test outputs, or host-specific absolute paths.
