# Vector-First Minimal Semantic Rule

After S5, human decisions are outside this assistant workflow.

Vector-first is no longer the dominant design objective in v3.1.6. S2/S5 output generated raster images, not SVG. The useful part of vector-first is only this: avoid fused, unreadable geometry when a clean paper figure would benefit from separable modules, icons, and connectors. Do not force a candidate to look SVG-oriented when another paper-faithful style communicates the paper better.

S5 formal raster candidates should still preserve semantic element separability. Treat every major concept-level object as a later-extractable semantic primitive: module card, icon, label, token, formula anchor, connector, arrowhead, inset frame, and legend swatch. These primitives should have clear boundaries, visible spacing, and minimal occlusion. This supports downstream layer extraction and vector reconstruction without turning S5 itself into an SVG-generation step.

Avoid overlapping distinct concepts. A connector should not run through an icon, label, formula token, or important module interior. Distinct icons should not sit on top of one another. Labels should not touch or cover glyphs. If a visual object is intentionally composite, it must behave as one semantic atom and should be described in the S4/S5 contract.

Default figure shape:

- one clear visual sentence;
- 3-6 main modules;
- one dominant flow and 0-3 secondary flows;
- few large landmark icons;
- short labels;
- usually no formulas or symbols unless the designer can state why the paper's core idea cannot be expressed without them.
- caption/legend/body text that completes the image instead of forcing all explanations into pixels.

Minimal does not permit deleting non-droppable core substeps. If the source-grounded method depends on a sequence such as train -> generate, filter -> use, score -> weight, or evaluate -> update, S5 formal candidates must preserve that sequence in the generated image body, connected inset, zoom/cutaway, or compact mechanism panel. Captions may explain visible steps, but they must not be the only carrier.

If the paper presents a core innovation through substantial method prose, formulas, or explicit "improvement" language, the figure must include a clear visual anchor for that innovation. The anchor may be a module-internal mechanism, a formula token, a comparison/gating mark, an update loop, a before/after contrast, or a highlighted transformation, but it cannot be absent from the image.

Entity icons must be chosen for paper meaning and explanatory power. Generic icon style is allowed, but the icon's semantic role must match the paper's domain entities, model modules, algorithm operations, data objects, or evaluation concepts. Ease of SVG redrawing is secondary and must not override semantic clarity.

After S5, human decisions are outside this assistant workflow.
