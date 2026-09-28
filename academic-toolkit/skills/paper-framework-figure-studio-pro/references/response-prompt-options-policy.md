# Response Prompt Options Policy v3.1.9

A printed prompt is a handoff for a future user turn. Never execute it in the current response.

When choices exist, provide:

- a default prompt using the recommended option;
- a placeholder prompt where the user can fill preferred candidate ID, image path, or design notes.

After S5, human decisions are outside this assistant workflow.

```text
我倾向的第二轮图片/候选是：<填写候选ID、图片编号、路径或描述>
我希望修改的地方：<填写布局、模块、箭头、文字、颜色、密度、caption 重点或其他修改要求>
我希望最终 caption 强调：<填写方法主线、贡献、读者首先应理解的机制、重要但不宜塞进图里的说明>
```

After S5, human decisions are outside this assistant workflow.

## Long Prompt Display Limit v3.2.4

When the next action uses multiple long image prompts, response options must show only a compact file-reference handoff. Do not display the full image prompt text for each candidate. Provide links/paths to prompt package files and prompt-index files instead.
