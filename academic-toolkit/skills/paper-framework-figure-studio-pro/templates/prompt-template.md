# Prompt Template v3.2.15f

## S0 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，进入并只执行 S0-PAPER-FOUNDATION。
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。
```

## S0-To-S1 Non-Copyable First-Round Surface-Style Note

S0 must show this as prose outside the copyable S1 prompt block. Do not insert it into the suggested S1 prompt:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格；这只约束渲染表面，不等同于候选图的叙事、布局或处理方案。若要修改，请在下一轮 S1 请求中另行明确写入表面风格选择或取消默认表面风格；请不要把本说明复制进默认提示词块。
```

## S1 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 S0 产物，进入并只执行 S1-FIGURE-STRATEGY。
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。

S1 必须内置完成 S2 preparation：先规划 8 个互补且内部不矛盾的风格组合，按综合评价选出最高的 4 个组合，说明每个入选组合中各风格为何互补，然后只为 C01-C04 生成 S2 prompt packages、candidate registry、layout/routing/edge contracts、prompt-index 和 image-only handoff。

S1 必须先读取并消费 `outputs/S0-paper-foundation/s0-semantic-precision-contract.json`：把其中的 role_visual_realization_contract、process_instance_budget、forbidden_misimplementation_locks 写入每个相关 S2 prompt package。不得把 S0 中“保留/区分/体现角色或条件差异”之类的语句误实现为每个角色各画一套完整流程；只有 contract 明确允许 true parallel/comparison lanes 且有源证据时才可画多条完整流程。

每个 prompt package 必须包含 palette_strategy、palette_semantic_mapping、palette_anti_ai_artifact_rules、human_aesthetic_rationale 和 color_accessibility_note。配色必须符合人类审美，避免 AI 味：禁止通用蓝紫渐变、霓虹高饱和、玻璃/光球/光斑、营销海报光效和无语义彩虹渐变。

对每个生图 prompt 做严格契约审核与最多 5 次修复循环，检查所有箭头/连线的论文证据、连接线去重/合并、变量在线上/port/tag 表达、不得画不消费/不变换该变量的跨模块假中继数据流、模块化不碎片化、内部示意图简洁通用、workflow 不重复、背景只占小部分、算法/模型/方法框架图采用紧凑但可读的 manuscript density、主机制占据画面中心和主要面积、禁止大面积空白/上方背景知识面板/散点式微模块岛。不要生成图片。
```

## S2 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 S1 已登记产物，进入并只执行 S2-SKETCH-EXPLORE 的 IMAGE_GENERATE。
读取 S1 生成的 S2 prompt-index，逐一读取 C01-C04 每个 candidate 的 prompt_path，并按同一行 candidate_id 生成/登记对应 target_image_path；candidate_id、prompt_path、target_image_path、状态文件、artifact 和 checkpoint 必须一致。
只生成 4 张图，不补候选、不跳号、不改名。禁止 SVG、Python/PIL、Matplotlib、Graphviz、TikZ、Mermaid、canvas、PPT/PDF、截图或本地程序化 PNG/WebP。只生成图像，不写审计、排名、解释、修复、聚合或下一步文本。
```

## S1-To-S2 Non-Copyable First-Round Surface-Style Options Note

S1 must show this as prose outside the copyable S2 prompt block. Do not insert it into the suggested S2 prompt:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格，除非 S1 已在 prompt-index 中记录了显式覆盖或取消默认表面风格；S2 只会按该记录生成图片。若想在运行 S2 前修改第一轮表面风格，需要回到 S1 重做 prompt packages，而不是改 S2 生图提示词。
```

## S3 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 S0/S1 产物、S2 已生成图像，进入并只执行 S3-DIRECTION-SELECT。
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。
S3 必须先内置完成 S2 outputs review 和 exploration aggregate，再做方向选择。用户可在本提示中指定倾向的一个或多个第一轮候选图 ID 作为参考信号，但 S3 仍需基于论文证据和契约审核选择方向；如记录用户偏好，必须传给 S4，并说明 S4 必须把偏好覆盖收敛到两个 S5 候选内。
```

## S3-To-S4 Non-Copyable Second-Round Surface-Style Note

S3 must show this as prose outside the copyable S4 prompt block. Do not insert it into the suggested S4 prompt:

```text
可选第二轮表面风格：S5 正式候选默认由 S4 根据论文需要设置表面风格。表面风格只约束渲染层，不改变候选图的论文语义、布局骨架、连线证据和密度预算。若希望指定第二轮表面风格，请在下一轮 S4 请求中另行写入“第二轮采用 <表面风格名> 表面风格”。
```

## S4 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 S3 方向选择结果，进入并只执行 S4-CANDIDATE-BRIEF。
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。

S4 必须内置完成 S5 preparation：生成正式候选矩阵、S2 风险转移、图文分工、元素布局合同、routing/arrow/port 合同、visible text whitelist、line-carried variable registry、internal visual motif plan，并只为 F01-F02 生成 S5 prompt packages、prompt-index 和 image-only handoff。

S4 必须继续继承 S0/S1/S3 中的 semantic precision locks，尤其是 role_visual_realization_contract、process_instance_budget 和 forbidden_misimplementation_locks。S5 formal prompt 不得把 compact role/context markers 再扩写成每个角色一条完整 pipeline；如需改变表示方式，必须写明新的源证据和修复记录。

S4 必须把相关 S2 产出图像作为 S5 参考图输入写入每个 F01-F02 prompt package 和 prompt-index 行的 `reference_image_paths`；这些路径必须指向已注册的 S2 raster 输出图。S5 支持图像输入时使用这些参考图；不支持时自动忽略，不得阻断 S5。

如果 S3 记录了用户偏好的第一轮候选 ID，S4 必须把偏好覆盖收敛到 2 个 S5 候选内；若无法容纳，先修复/重规划/请求用户取舍，不得生成第三个 S5 候选。

每个 S5 prompt package 必须包含 palette_strategy、palette_semantic_mapping、palette_anti_ai_artifact_rules、human_aesthetic_rationale 和 color_accessibility_note。配色必须符合人类审美，避免 AI 味：禁止通用蓝紫渐变、霓虹高饱和、玻璃/光球/光斑、营销海报光效和无语义彩虹渐变。

对每个生图 prompt 做严格契约审核与最多 5 次修复循环，并检查不得画不消费/不变换该变量的跨模块假中继数据流；同时检查 layout_information_density_plan、canvas_area_budget、context_inset_budget 与 mainline_center_of_gravity_gate，避免大留白、碎片化、视觉重心偏移和背景信息区喧宾夺主。不要生成图片。
```

## S4-To-S5 Surface-Style Reminder Rule

S4 must not show a second-round surface-style reminder beside or inside the copyable S5 prompt. After S4, the next public prompt is S5 image-only.

## S5 Prompt

```text
请使用 paper-framework-figure-studio-pro skill，根据当前状态和 S4 已登记产物，进入并只执行 S5-CANDIDATE-IMAGE 的 IMAGE_GENERATE。
读取 S4 生成的 S5 prompt-index，逐一读取 F01-F02 每个 candidate 的 prompt_path 和 reference_image_paths；如果当前 image generation route 支持参考图/图像输入，则把 reference_image_paths 中的 S2 图像作为参考输入一起用于该 candidate 生图；如果不支持图像输入，则自动忽略这些参考图输入并继续用文本 prompt 生成。按同一行 candidate_id 生成/登记对应 target_image_path；candidate_id、prompt_path、target_image_path、状态文件、artifact 和 checkpoint 必须一致，reference_image_paths 必须保持为该行登记的 S2 参考路径且不得被改写成 S5 目标路径；不要把 F01-F02 改写成 C01-C02 或数字序号。
只生成 2 张图，不补候选、不跳号、不改名。禁止 SVG、Python/PIL、Matplotlib、Graphviz、TikZ、Mermaid、canvas、PPT/PDF、截图或本地程序化 PNG/WebP。只生成图像，不写审计、排名、解释、修复、聚合、最终 caption 或下一步文本。S5 生图后 assistant workflow 结束。
```

## Terminal Answer

```text
我的任务已经完成，剩下由人类来决策。
```
