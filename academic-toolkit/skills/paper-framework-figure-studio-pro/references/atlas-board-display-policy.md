# Atlas Board Display Policy

Version: 3.0.0

The generated web-page display layer is not used by this workflow. Codex, ChatGPT web, Claude Code, and other environments should use normal text replies plus direct Markdown image embeds for saved atlas/category boards.

## Mandatory display rule

Whenever a reply mentions one of the already-generated category/atlas boards, or discusses the concept family represented by the board, display the corresponding PNG immediately. A prose-only mention is not enough.

Bootstrap plan-only replies are exempt from atlas display: before explicit S0 entry, do not display atlas boards just to satisfy first-reply display rules. After the user explicitly asks to enter/run/execute/start/continue S0-PAPER-FOUNDATION, the first executable S0 reply for a new project must display the built-in atlas/style images at least once. Default: display all canonical embeds below. Minimum acceptable S0 first reply: display `visual-communication-styles.png` plus any board needed for the current routing context. If the host cannot render an image, list the package-relative path and record the render failure; do not omit the built-in style/atlas image requirement after explicit S0 entry.

Canonical embeds:

```md
![Subtype overview](assets/subtype-atlas/boards/subtype-overview.png)
![Visual grammar layout](assets/subtype-atlas/boards/visual-grammar-layout.png)
![Reader role detail](assets/subtype-atlas/boards/reader-role-detail.png)
![Visual communication styles](assets/subtype-atlas/boards/visual-communication-styles.png)
```

## Mapping

- Mentioning figure subtype, taxonomy, paper slot, method framework, architecture, pipeline, mechanism, case walkthrough, or evidence-board choices requires `subtype-overview.png`.
- Mentioning layout grammar, layout skeleton, panel choreography, module topology, arrow grammar, or visual structure requires `visual-grammar-layout.png`.
- Mentioning reader role, reader question, reweb-display-facing detail, or cognitive load requires `reader-role-detail.png`.
- Mentioning visual communication style, style family, density/detail level, visual rhetoric, color semantics, or illustration style requires `visual-communication-styles.png`.

## Removed route

Do not create, reference, or maintain web-page display pages, display-record JSON, page indexes, JavaScript/CSS web assets, or web-display-specific state fields.
