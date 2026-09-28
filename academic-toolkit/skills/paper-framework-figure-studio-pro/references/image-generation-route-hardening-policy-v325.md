# Image Generation Route Hardening Policy v3.2.5

> v3.2.13 override: the assistant workflow ends at S5. This policy applies only to S0-S5 responsibilities and cannot create a assistant stage after S5.


This policy is generic and paper-agnostic. It governs the production route for target-paper figure images in every project, regardless of paper domain, dataset, method names, module names, or candidate counts.

## Scope

This policy applies to every target-paper image unit:

- S2 `IMAGE_GENERATE` and any authorized S2 `deleted candidate revision unit`;
- S5 `IMAGE_GENERATE` and any authorized S5 `deleted candidate revision unit`;
- any future internal unit that creates, regenerates, reruns, replaces, adopts, promotes, registers, or records a target-paper sketch, candidate, pending selected figure, reruned selected figure, or submitted selected figure.

A target-paper image is any image intended to stand as a paper framework / architecture / pipeline / method / mechanism figure candidate or selected figure. Support files such as prompt files, JSON manifests, audits, captions, vector-library icons, style references, and reconstruction specifications are not target-paper images unless they are registered as an S2/S5 raster candidate/final artifact.

## Non-Negotiable Environment Route

Resolve `runtime_environment.environment` before any target-paper IMAGE_* unit.

| Runtime | Required target-image route | Forbidden substitute examples |
|---|---|---|
| `codex` | call Codex Image Gen through `image_gen` | `create-image`, Python/PIL/Pillow, Matplotlib/Plotly, Graphviz, TikZ/LaTeX, Mermaid, SVG/HTML/canvas, browser screenshots, SVG-to-PNG, PPT/PDF rendering, hand-written PNG files |
| `chatgpt_web` | use Create Image / ChatGPT Images 2.0 | direct SVG output, Mermaid/HTML/canvas, Python/PIL/Pillow, Matplotlib/Plotly, Graphviz, TikZ/LaTeX, screenshots, SVG-to-PNG, PPT/PDF rendering, any local raster renderer |
| `claude_code` / `other` | named approved image-generation API only | any programmatic renderer, drawing script, screenshot pipeline, SVG/PPT/PDF conversion, or prompt-only placeholder |
| `unknown` | blocked | all image generation and registration |

The rule is route-based, not extension-based. A `.png`, `.jpg`, `.jpeg`, or `.webp` file is invalid if it was produced by a forbidden local/programmatic renderer.

## Image-Only Means Tool/API Call, Not Local File Fabrication

For target-paper image units, `target_image_path` is an output registration target, not a license to synthesize the image by any convenient local method. Filling that path with a raster file is compliant only when the raster came from the required environment route.

A target-paper image unit must not:

- draw a diagram with Python, PIL/Pillow, Matplotlib, Plotly, Graphviz, TikZ, LaTeX, Mermaid, HTML, canvas, SVG, PPT/PPTX, PDF, or any screenshot/render/conversion pipeline;
- answer with SVG code or Mermaid code and then treat it as a generated figure;
- export a programmatically drawn SVG/PPT/PDF to PNG/WebP and register it as a candidate;
- set state fields such as `generator=create-image`, `generator=image_gen`, or `generator=approved-image-api` unless that exact route was actually used;
- register a local raster file as a target image without a matching `image_generation_event` provenance record from the required route.

## Approved API Fallback

`approved-image-api` is not a general escape hatch. It is allowed only in non-Codex/non-ChatGPT runtimes where neither Codex `image_gen` nor ChatGPT web Create Image is available. The state must record:

- `approved_api_name`;
- `route_unavailable_reason`;
- generated project-run-relative raster paths;
- any API limitations that may affect audit or rerun.

The approved API must be an actual image-generation model/API. A local drawing script, deterministic renderer, screenshot tool, SVG converter, PPT renderer, or browser canvas is never an approved image-generation API.

## Provenance Recording And Registration

Every target-paper generation event must record:

- `environment`;
- canonical `generator` value: `image_gen`, `create-image`, or `approved-image-api`;
- `required_generator` for the environment;
- `route_guard_status=passed`;
- at least one existing project-run-relative `generated_path` using `.png`, `.jpg`, `.jpeg`, or `.webp`.

After S5, human decisions are outside this assistant workflow.

## Rerun And Adoption

Reruns are fresh full-image regenerations through the same environment route. They are not local retouches, cropping, inpainting, vector edits, screenshot patches, SVG edits, or code-drawn replacements.

After S5, human decisions are outside this assistant workflow.

## Direct Delete Protection

Direct artifact delete is prohibited for active target-paper image artifacts. To invalidate a bad generation, mark the artifact/candidate stale, reset the candidate, or run explicit rewind-step cleanup for a rerun. Direct deletion loses provenance and can make state/manifest/checkpoint records lie about what exists.

## Failure Behavior

When the required image route is unavailable, the correct behavior is to stop, mark the image unit blocked, and ask the user to run the image unit in a runtime that has the required route. Do not downgrade the task to SVG, code, screenshots, renderer output, or prompt-only placeholders.
