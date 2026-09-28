# Security And Portability Policy

- Store project paths as relative paths.
- Reject path traversal and host-specific absolute paths in state fields.
- Do not store API keys, tokens, passwords, credentials, or secret-like fields in project state.
- Do not include Python caches, temporary smoke-test output, or local runtime artifacts in release packages.
- S2/S5 target-paper outputs must be generated raster images from the runtime-locked image-generation route: Codex `image_gen`, ChatGPT web Create Image / ChatGPT Images 2.0, or a named approved image-generation API only in other runtimes. They must not be code-drawn or programmatic/local raster substitutes such as Python/PIL, Matplotlib, Graphviz, TikZ, Mermaid, screenshots, SVG-to-PNG, or PPT/PDF-rendered diagrams.
- Run the release path scanner before packaging.
