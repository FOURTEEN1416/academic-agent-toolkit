# Figma MCP tools and prompt patterns

Quick reference for the Figma MCP toolset, when to use each tool, and prompt examples to steer output toward your stack.

## Core tools

- `get_design_context` (Figma Design, Figma Make): primary tool. Returns structured design data and default React + Tailwind code. Selection-based prompting works on desktop; the remote server uses a frame or layer link to extract the node ID.
- `get_variable_defs` (Figma Design): lists variables and styles used in the selection. Useful to align with tokens.
- `get_metadata` (Figma Design): sparse XML outline of layer IDs, names, types, positions, and sizes. Use before re-calling `get_design_context` on large nodes to avoid truncation.
- `get_screenshot` (Figma Design, FigJam): screenshot of the selection for visual fidelity checks.
- `get_figjam` (FigJam): XML and screenshots for FigJam diagrams.
- `create_design_system_rules` (no file context): generates a rule file with design-to-code guidance for your stack.
- `get_code_connect_map` (Figma Design): returns mapping of Figma node IDs to code components.
- `add_code_connect_map` (Figma Design): adds or updates a mapping between a Figma node and a code component.
- `get_strategy_for_mapping` (alpha, local only): Figma-prompted tool to decide mapping strategy for connecting a node to a code component.
- `send_get_strategy_response` (alpha, local only): sends the response after `get_strategy_for_mapping`.
- `whoami` (remote only): returns the authenticated Figma user identity.

## Prompt patterns

- Change framework: "generate my Figma selection in Vue", "in plain HTML + CSS", or "for iOS".
- Use project components: "generate my Figma selection using components from `src/components/ui`".
- Combine stack choices: "generate my Figma selection using components from `src/ui` and style with Tailwind".
- Variables and styles: "get the variables used in my Figma selection" or "list the variable names and their values used in my Figma selection".
- Code connect: "show the code connect map for this selection" or "map this node to `src/components/ui/Button.tsx` with name `Button`".

## Best-practice flow reminder

Use `get_design_context`, then `get_metadata` only when the node is too large, then `get_screenshot`. Apply the generated output through the project rules in `SKILL.md`; do not treat MCP output as final code style.
