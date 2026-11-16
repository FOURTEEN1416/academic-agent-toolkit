---
name: generate-image
description: Generates or edits images with the native generate_image tool (Nano Banana Pro through Ace or a Gemini key, GPT Image 2 through an OpenAI key), for illustrations, cover art, graphical abstracts, conceptual visuals, photo-style figures and edits of existing images, saved straight into the workspace and checked before use. Use for any image that is not a technical diagram or a plot of data. For method, pipeline, pathway and architecture diagrams load schematics; for plots of measured numbers load figures.
summary: "Illustrations, graphical abstracts and image edits with generate_image; never hand-drawn."
category: core
role: workflow
allowed-tools: [Read, generate_image]
license: MIT
version: 2.0.0
author: Synthetic Sciences
metadata:
  upstream: K-Dense-AI/scientific-agent-skills
  upstream-url: https://github.com/K-Dense-AI/scientific-agent-skills
  upstream-path: scientific-skills/generate-image
  upstream-license: MIT
  upstream-relationship: prompt guidance adapted; rewritten around the native tool
  skill-author: Synthetic Sciences
  adapted-by: Synthetic Sciences
---

# Generate Image

Generate or edit an image with the native `generate_image` tool. The tool keeps credentials
in the trusted host, renders through whichever route the person has, and saves the image
into the connected workspace, where `read` opens it for inspection and a manuscript
includes it directly.

## The route

The environment line `Image generation:` says whether a route exists and which one:

- **Ace**: the managed account. Renders Nano Banana Pro (`google/gemini-3-pro-image`) and
  settles the cost from the Wallet, like any other Ace request. One reference image per
  request.
- **A Gemini key** the user connected in Customize → Models: Nano Banana Pro
  (`gemini-3-pro-image`) on their own account, up to 14 reference images.
- **An OpenAI key** the user connected: GPT Image 2 (`gpt-image-2`) on their own account,
  reference images as an edit.

A personal OpenRouter key is not a route. When the line says image generation is
unavailable, say once that it needs Ace or a Gemini or OpenAI key connected in Customize →
Models, then continue with the rest of the request. Never ask the user to paste a key into
chat, never call the tool to "check", and never draw the image by hand as TikZ, SVG,
Graphviz or matplotlib shapes in its place.

## Tool contract

Call `generate_image` with:

- `prompt` (required): what the image shows and how. Prompt quality decides output quality
  more than the model does. Name, in one sentence each: the **subject** and how much of it is
  in frame ("a single pipette tip above a 96-well plate"); the **medium and style**
  (scientific illustration, flat vector, watercolour, 3D render, photograph); the **lighting
  and palette** ("soft diffuse light, cool blue and white palette"); the **composition**
  ("wide shot, subject left of centre, empty space on the right for a title"); and what to
  **avoid** ("no text, no labels, no watermark"). Any text that must appear is quoted
  verbatim. Asking for empty space where a caption or title will go is the single most useful
  compositional instruction for posters and slides.
- `purpose`: `illustration` for a conceptual figure or graphical abstract (the tool prepends
  publication framing: clean background, restrained palette, no invented text or data);
  `edit` when changing an existing image; `schematic` belongs to the schematics skill.
- `output_path`: destination in the workspace, `.png` (any route), `.jpg` or `.webp`
  (Ace and OpenAI). Default `generated-image.png`.
- `input_path`: an existing image to edit. Omit it entirely for a new image; never pass a
  directory, `.`, `/dev/null` or a blank canvas.
- `reference_paths`: existing images whose style or components the result should follow.
  Up to 14 on a Gemini or OpenAI key; on Ace pass one image in total (either `input_path`
  or one reference).
- `aspect_ratio`: `1:1`, `3:2`, `2:3`, `4:3`, `3:4`, `16:9`, `9:16` or `21:9`, from the slot
  the image fills.
- `image_size`: `1K` while iterating (default), `2K` for anything printed, `4K` only for a
  poster or cover.

There is no `model` parameter: the route decides the model.

Example generation:

```json
{
  "prompt": "A DNA double helix with one mutation site highlighted, close enough that the base pairs read. Flat scientific illustration. Restrained blue and amber palette on white. Helix runs diagonally from lower left to upper right, empty space upper left for a caption. No text, no labels, no watermark.",
  "purpose": "illustration",
  "output_path": "figures/dna-mutation.png",
  "aspect_ratio": "3:2"
}
```

Example edit:

```json
{
  "prompt": "Keep every element and label exactly as drawn; widen the margins and increase contrast for a two-column paper",
  "purpose": "edit",
  "input_path": "figures/abstract-draft.png",
  "output_path": "figures/abstract.png",
  "aspect_ratio": "4:3",
  "image_size": "2K"
}
```

## Workflow

1. Read the destination first: the document, slide or page the image goes into, its width,
   and what is around it. An image made without its context is resized and recolored later.
2. Write the prompt from the communication goal: what a viewer should take from it in one
   glance, what must be present, what must not (no invented text, no logos, no decorative
   icons, no numbers). Set `aspect_ratio` from the slot.
3. Generate one candidate at `1K` with `purpose: "illustration"`. Never fill an output slot with
   an image nobody asked for. To refine rather than restart, pass the candidate back as
   `input_path` with `purpose: "edit"` and describe only the change.
4. Open the saved file with `read` and check it: subject correct, requested text spelled
   exactly, nothing invented, legible at the final size, palette accessible, no watermark or
   border.
5. Refine only against a named defect, passing the candidate as `input_path` and stating the
   change; two rounds at most. Then render the accepted prompt at `2K` if it will be printed.
6. Report the file, the route it used and anything the image could not do.

For a technical architecture, method flow, pathway or experimental diagram, load
`schematics`, whose plan-style-render-check workflow is built for exact labels and
connections; it uses the same tool.

## Standalone script

`scripts/generate_image.py` is a helper for use outside OpenScience with a personal
OpenRouter key from `--api-key`, `OPENROUTER_API_KEY` or `.env`. Inside OpenScience it is
never the route: the native tool is.
