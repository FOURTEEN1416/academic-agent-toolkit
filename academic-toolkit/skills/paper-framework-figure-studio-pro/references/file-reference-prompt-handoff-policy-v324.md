# File-Reference Prompt Handoff Policy v3.2.4

After S5, human decisions are outside this assistant workflow.

## Core Rule

Long image prompts are artifacts, not user-visible prose. A text-preparation unit must save full image-generation prompts to files and show the user only a short handoff that references a prompt index or one final prompt file.

Do not inline multiple full candidate image prompts in a visible next-step prompt. Do not print a long selected image prompt when a file reference can be used.

## Required Files

For multi-candidate generation, write:

```text
outputs/<stage-output-root>/prompt-index.json
outputs/<stage-output-root>/candidates/<candidate_id>/prompt-v01.md
outputs/<stage-output-root>/candidates/<candidate_id>/target.json        # optional but recommended
```

After S5, human decisions are outside this assistant workflow.

```text
After S5, human decisions are outside this assistant workflow.
After S5, human decisions are outside this assistant workflow.
```

or the equivalent project-relative paths recorded in state/manifests.

## Prompt Index Schema

A prompt index must be project-relative and data-driven:

```json
{
  "stage": "<public stage>",
  "substage": "<next image unit>",
  "prompt_mode": "file_reference_handoff",
  "candidate_ids": ["<dynamic ids>"],
  "candidates": {
    "<candidate_id>": {
      "prompt_path": "outputs/.../candidates/<candidate_id>/prompt-v01.md",
      "target_image_path": "outputs/.../candidates/<candidate_id>/image-v01.png",
      "caption_contract_path": "outputs/.../<optional-caption-contract>.md"
    }
  },
  "visible_handoff_rule": "The user-visible next prompt references this index and does not inline full candidate prompts."
}
```

Candidate IDs, paths, and counts must come from the candidate registry or prompt index; never hard-code them in reusable instructions.

## User-Visible Handoff Template

Use a short visible handoff like:

```text
进入 <stage> / <IMAGE_GENERATE unit>。请读取并使用已保存的 prompt index：

<project-relative prompt-index path>

为 index 中列出的全部候选逐一读取对应 prompt-v01.md，并生成/附加独立候选图。生成后把图像注册到 index 指定的 target_image_path，并更新 image generation manifest、candidate registry 与 checkpoint guidance。

本轮为 image-only：只生成/附加候选图像；不要写解释、审核、排序、修复建议、下一步提示词或文字报告。
```

After S5, human decisions are outside this assistant workflow.

## Checkpoint Interaction

Prompt files and prompt-index files are required existing assets once written. Planned future target images named in the index are pending future assets until an image generation event completes or the target image file exists.


## v3.2.6 Semantic Graph Prompt Handoff Addendum

When `references/semantic-graph-prompt-contract-policy-v326.md` applies, the prompt index must point to the actual file containing the full image-only prompt and embedded semantic graph contract. The image-generation unit must read the exact `prompt_path`, confirm the file exists, and confirm that the prompt includes `semantic_graph_spec`, `visible_text_whitelist`, `internal_text_blacklist`, and an exact edge registry before generating. If the actual saved prompt is named `image-only-prompt.txt`, do not index it as `prompt-v01.md` unless a real `prompt-v01.md` also exists with identical full content.

Record `prompt_file_read_audit` in the generation manifest or candidate status. Do not generate from a prompt index summary alone.
