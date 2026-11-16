---
name: schematics
description: Creates or refines publication-quality technical diagrams with the native generate_image tool (Nano Banana Pro through Ace or a Gemini key, GPT Image 2 through an OpenAI key), method and architecture overviews, pipelines, CONSORT and PRISMA flows, experimental workflows, biological pathways, circuits and conceptual schematics, described component by component, rendered under publication standards, scored against a document-type threshold and re-rendered once from the critique. Use for any figure whose content is structure rather than data. Not for plots of measured numbers (use figures) and not for illustrations or artwork (use generate-image). Never hand-drawn as TikZ or SVG.
summary: "Method, pipeline and pathway diagrams rendered with generate_image: describe, render, score, refine. Never TikZ."
category: core
role: workflow
allowed-tools: [Read, Write, Edit, generate_image]
license: MIT
version: 2.0.0
author: Synthetic Sciences
metadata:
  upstream: K-Dense-AI/scientific-agent-skills
  upstream-url: https://github.com/K-Dense-AI/scientific-agent-skills
  upstream-path: skills/scientific-schematics
  upstream-license: MIT
  upstream-relationship: workflow, prompt standards, review rubric and references adapted
  adapted-by: Synthetic Sciences
  skill-author: K-Dense Inc.
  method: K-Dense scientific-schematics generate-review-refine loop; PaperBanana (Zhu et al., 2026) content planning
---

# Schematics

A methodology diagram carries the paper's central idea in one glance, and it is the figure
most often faked: outdated palettes, boxes that say nothing, arrows that go the wrong way,
components the text never mentions. Image models draw clean diagrams with legible text when
they are told the publication standards on every call and their output is judged against a
rubric, not admired. This skill is that loop: describe the diagram precisely, render it under
the standards, score it, and re-render once from the critique.

## The medium

- `generate_image` with `purpose: "schematic"` is the medium for every diagram. The tool
  prepends the publication framing (white background, one sans-serif face, Okabe-Ito palette
  with one accent, one reading direction, verbatim labels, no invented parts, no figure
  numbers or captions inside the image) to your description, so you write the content, not
  the house style. It renders with Nano Banana Pro through Ace or the user's own Gemini key,
  or GPT Image 2 through the user's own OpenAI key; the environment line names the route.
- Use `image_size: "1K"` while iterating and `"2K"` for the accepted render of anything
  printed; set `aspect_ratio` from the page slot (16:9 or 21:9 for a full-width overview,
  4:3 or 1:1 for a column). Score the 1K render; the 2K file is written for the manuscript
  and is not read back. It weighs several megabytes, and a request carrying a few of them
  is too large for the Ace gateway (images over 2 MB are not sent on that route at all). Pass `reference_paths` when the paper's earlier figures or a
  cited paper's diagram set the style (up to 14 on a Gemini or OpenAI key; Ace takes one
  image per request). Output is raster at print resolution; `\includegraphics` takes the PNG.
- Do not hand-draw a schematic as TikZ, SVG, Graphviz, Mermaid or matplotlib shapes, and do
  not offer that as a fallback: language models draw these badly and the result reads as an
  unfinished figure. Exact labels are handled by giving the model the exact labels and
  checking them, not by switching medium.
- Plots of numbers are never image-generated (hallucinated values, repeated elements). Load
  the figures skill for data.
- If the environment says image generation is unavailable, stop before drawing: tell the
  user once that schematics need Ace, or a Gemini or OpenAI key connected in Customize →
  Models, leave an `\fbox{}` placeholder with the planned caption in the manuscript if one is
  being written, and continue with the rest of the request.

## Workflow

Copy this checklist and work through it.

- [ ] 1. Read the source and choose the document type.
- [ ] 2. Write the description: type, components, flow, labels, emphasis.
- [ ] 3. Render at 1K with `purpose: "schematic"`.
- [ ] 4. Score the render on the rubric; stop if it meets the threshold.
- [ ] 5. Otherwise re-render once from the critique; keep the better of the two.
- [ ] 6. Render the accepted description at 2K, save, write the caption, report open issues.

One figure is faster done here than delegated: a worker starts without your context and
re-reads the source. Two or more figures, or one figure while you still have text to write,
are worth a background worker each (`task` with `background: true`, `subagent_type: "data"`
or `"general"`): give it steps 1–6 with the component list, the document type and its
threshold, the output path, and ask for the score and what it changed. The worker sees the
render the same way you do; you get the score, the file and your own time back.

**Step 1. Read the source.** The method section, the caption slot, and any existing figure.
Identify the claim the figure must make, every component the text names, the relationships
and their direction, what is input, what is learned, what is frozen, what is compared. A
figure that shows a component the text never mentions is wrong even if it is pretty. Note the
document type: it sets the bar in step 4.

**Step 2. Write the description.** The model draws what it is told and nothing it can infer,
so the description is a specification, not a mood. Name, in this order:

- **Type**: flowchart, architecture diagram, pipeline, pathway, circuit, block diagram.
- **Components**: every element, with its exact label as it appears in the text, and counts
  where they matter (`Screened (n = 500)`).
- **Flow and direction**: left-to-right or top-to-bottom, and each connection as
  `A -> B (meaning)`; name the labelled arrows (`RAF -> MEK, labelled "phosphorylation"`).
- **Emphasis**: the contribution in the single accent colour; standard parts in grey; dashed
  borders for frozen or optional parts.
- **Style constraints beyond the defaults**: panel letters, a legend, a scale bar, the
  reference figures' palette.

Keep it to what fits: more than about twelve labelled elements needs a second figure or a
zoomed inset, not smaller text. Good and bad descriptions, and four worked examples, are in
`references/review-loop.md`; the standards a figure is judged against are in
`references/best-practices.md` and `references/style-guide.md`.

**Step 3. Render.** Call `generate_image` with the description as `prompt`,
`purpose: "schematic"`, the `aspect_ratio`, `image_size: "1K"`, and any `reference_paths`.
Do not restate the house style in the prompt; the tool adds it. Do not ask for a title,
caption or figure number.

**Step 4. Score it.** Open the PNG with `read` and score it yourself on the rubric, 0–2 each:

| Criterion | 2 points means |
| --- | --- |
| Scientific accuracy | every named component present and labelled exactly, every connection present and in the right direction, nothing invented |
| Clarity and readability | the claim is legible at a glance, one visual hierarchy, no ambiguous element |
| Label quality | every element labelled, no misspelling, sizes consistent and readable at column width |
| Layout and composition | one reading direction, balanced whitespace, nothing overlapping or clipped |
| Professional appearance | flat, crisp, white background, restrained colorblind-safe palette, no decoration |

The threshold depends on where the figure goes: **journal 8.5**, conference, thesis or
grant **8.0**, preprint or report **7.5**, poster **7.0**, slides **6.5**. Write the score
and the specific issues in the activity trace. A misspelled label or a wrong arrow is a
failure regardless of the total.

**Step 5. Refine once.** If the score is below the threshold, re-render from the same
description with the issues appended as constraints ("the arrow from Encoder to Decoder is
reversed; remove the third block labelled 'Model'; the label 'Randomised' is misspelled"), or
pass the failed render as `input_path` with `purpose: "edit"` and the delta as the prompt
when the layout is right and only details are wrong. Score again; keep the better of the two
renders. Two renders at most: if connectivity still fails, simplify the description (fewer
components, one panel, a stated reading order) and render that. A correct simple diagram
beats a wrong detailed one, and a hand-drawn vector is not an option.

**Step 6. Finalize.** Render the accepted description at `image_size: "2K"` into the working
folder (`figs/<name>.png` beside a paper), then trim the canvas to the content: the model
paints the whole requested aspect ratio, so a wide flowchart arrives with an empty band above
and below it that would waste half a page. Run
`python <this skill's directory>/scripts/trim_margins.py figs/<name>.png` (in place, 3% pad;
`--out` for a copy), and use the trimmed file's real aspect ratio when sizing it in the
manuscript. Write the caption from the claim (bold phrase, then what the arrows and colours
mean, every abbreviation defined), reference it in the text before it appears, and report
anything the image could not do: a label the model kept misspelling, a component
simplified, a panel dropped. Record the description that produced the accepted render so
the figure can be regenerated.

## Refining an existing diagram

For a human-drawn figure that needs polish, keep the content and change only the style:
pass the original as `input_path` with `purpose: "edit"`, the style references as
`reference_paths`, and describe the same components and connections with the new palette,
typography and spacing. Score it with the same rubric; a polish that adds or removes a box is
a failure.

## Scope

Do the figures the user asked for, at the count asked for. Do not expand a figure request
into a literature review, citation audit or new experiments. When refining a manuscript,
leave its claims and unaffected figures alone. Save into the session or project workspace
and update the manuscript only when asked.
