---
name: paper-framework-figure-studio-pro
description: "论文方法框架图的多候选共设计（人在环）：按论文内容生成架构/流程/方法/系统数据流/机理图候选，逐轮由人挑选后再精修，含候选阶段与终局人工决策边界。触发词：框架图多方案、方法图候选、pipeline 图设计、架构图共设计。"
---


# Paper Framework Figure Studio Pro

Version: `3.2.15f`.

Candidate-count contract: S1/S2 use C01-C04 only; S4/S5 use F01-F02 only.

本 skill 用于为工程与应用科学研究论文设计并生成 publication-ready 候选框架图、架构图、流程图、机制图和方法总览图。它只服务论文框架图，不服务海报、宣传图、封面图、展板、营销视觉或把 PPT 页面内容塞进图里的演示页。


## Highest-Priority Answer, Origin, Checkpoint, And Prompt-Fidelity Principles

This section is the controller-level highest-priority rule set. Later workflow rules may specialize it, but may not weaken it.

### Design origin and fixed reply boundary

第一次启动回复的候选/可复制提示词建议中，必须再提供一条建议，这条建议是在默认的提示词基础上，加了一句话：

```text
额外说明这个 skill 的设计初衷是什么。
```

如果用户提到想知道、指导、询问、补充或说明这个 skill 的设计初衷、设计意图、创作缘由、为什么制作或送给谁，必须额外回答下面这段原文；这段原文不得改写或删改，但可以与当前步骤说明、必要上下文、下一步提示词、checkpoint 状态和强制文本回复结尾同时出现：

```text
设计初衷：昔日好友 Peng Shuwei 即将前往外地求学，以后恐怕难有许多相见机会；又恰逢其生日，所以五一就做了这个 skill 当礼物。祝生日快乐，愿未来前程似锦，再相逢，依然少年。
```

**Exact-text encoding integrity rule:** the dedication/origin text above is UTF-8 Chinese exact text. Never copy this exact text from mojibake shell output. On Windows PowerShell, do not read Chinese/exact-text files with plain `Get-Content` or plain `Select-String`; use `Get-Content -Encoding UTF8`, `rg`, or another UTF-8-aware reader. If any output shows visibly corrupted Chinese or replacement characters inside Chinese text, treat that output as corrupted, re-read the source with UTF-8, and do not quote it.

每一次非终端文本回复都必须在回复最后单独追加这一句原文；不得只作为可选提示词、不得改写或省略。若回复同时包含下一步候选提示词、checkpoint 链接或 checkpoint 状态，这一句仍必须作为最后一行出现。

```text
如果不知道如何提问，请说：请使用 paper-framework-figure-studio-pro skill 根据当前状态只建议下一步提示词，不要自动执行下一步
```

Exception: S5 has no next workflow prompt. For S5 terminal-complete replies or post-S5 “what remains” questions, the final line must be exactly `我的任务已经完成，剩下由人类来决策。` and no next-step prompt should be appended.

第一次 plan-only 启动回复不得提供、询问或暴露任何可配置的契约检查选项。固定候选契约策略已经内置：S2/S5 不再有独立候选级重型文本审计或候选级修改环节，但源证据约束、核心模块内部机制锁、箭头方向证据、edge-label-first 规则、semantic-vs-visual graph separation、变量/指标/权重优先走边/port 标签规则、以及 prompt contradiction audit 仍然必须执行。S1/S4 的准备职责必须把这些约束写进 prompt-index 和候选 prompt packages；S3 必须对 S2 候选图做默认 issue-ledger 式探索审计与汇总后再选方向。S5 生图后任务结束，不再由 assistant 做 S5 全候选审计。

### Text-response cumulative checkpoint zip gate

任何阶段或子阶段只要产生纯文本回复、文本报告、state、manifest、candidate matrix、prompt-index、audit、repair log、checkpoint、guidance 或 handoff prompt，就必须生成或确认一个项目起点到当前状态的累加 checkpoint zip 镜像，并执行完整性审核。该 zip 必须包含所有已存在的累计 `state/`、`inputs/`、`outputs/`、prompt packages、prompt-index、candidate matrix、manifest、issue ledger、repair log、active image registry、已生成并注册的 raster images、stage-local image mirrors、pending image target records、以及根级 checkpoint metadata。

每一次工作流纯文本回复呈现之前，必须使用固定脚本或等价纸张无关检查确认至少一个可恢复 zip 存在并通过审核：

```bash
python scripts/figure_studio_response_checkpoint_zip_gate.py --run-dir figure-studio-runs/<project_id> --stage <active_or_just_completed_stage> --build-if-missing --fail-on-error
```

一个可对用户称为“累加 checkpoint / restore bundle”的 zip 至少必须包含 `checkpoint-manifest.json`、`checkpoint-cumulative-integrity.json`、`checkpoint-integrity-audit.json`，manifest scope 必须是 cumulative，且完整性状态必须是 `PASS` 或 `complete_restore_ready`。不得只因为目录里有 zip、文件名最新、序号最大、或 zip 中有当前阶段文件，就把它称为可恢复 checkpoint。

如果没有合格 zip，必须当场从累计 roots 重建并重新运行 gate。若现有文件不足但当前对话历史足以恢复文本状态，必须先把历史对话中的 stage/state/manifest/prompt-index/candidate/audit/guidance 信息重建进 `outputs/_conversation-reconstruction/` 或对应正式输出路径，再重建 zip。若缺失的是已生成 raster、外部源文件或用户确认，必须明确请求该缺失前提或 redo 对应生成/注册阶段；不得把 fallback zip 伪装成 complete restore-ready checkpoint。

### Source-faithful image-prompt audit and symbol disambiguation

S1/S4 在准备任何 S2/S5 生图 prompt package、prompt-index 或候选矩阵之前，必须执行源证据忠实性审核。任何 prompt 中的实体、模块、角色、空间、变量、指标、公式、符号、箭头、port、fork/merge、拓扑、数据流、模型流、控制流、评价流、生成/聚合/训练关系、视觉隐喻和文字标签，都不得与论文、补充材料、用户材料、S0 精读报告或风险寄存器相违背。

每个实体和关系/连线必须满足以下二选一：直接由论文/精读报告提供证据锚点，或能由这些证据经过严格、可记录的逻辑推理得到。推理得到的关系必须写明前提和推理链；不能把“视觉上顺畅”“常见画法”“图像模型可能理解”当作证据。任何 unsupported、contradictory、ambiguous 或 symbol-mixing 的 prompt 内容都是 handoff blocker。

符号不能混淆：同一符号、字母、颜色、图标、线型、边标签或视觉 token 不得同时表示不同论文概念；不同论文概念也不得被压缩成同一符号，除非 prompt 中明确说明它们是 source-supported group/aggregate 且不会改变含义。变量/指标/权重/阈值/概率/精度/损失/模型参数等 edge-label-eligible items 默认放在线、port、fork/merge 或 tag 上，不得作为同级模块盒子。若审核三轮修复后仍存在违背论文或符号混淆，必须停止在文本 checkpoint/residual-risk ledger，不得进入 S2/S5 image-only handoff。

### Package context economy

打包和维护 reusable skill 时，`SKILL.md` 应保持为短控制器；细节规则按需放入 `references/` 并在当前任务需要时加载，脚本放入 `scripts/`，项目论文事实只进入 run outputs。纯净 release 包不得保留历史 patch report、旧版本 validation report、临时构建目录、缓存文件或项目运行产物。

## v3.2.15f Terminal Candidate Workflow

Main workflow:

```text
Bootstrap / plan-only gate
  ↓
S0-PAPER-FOUNDATION
  ↓
S1-FIGURE-STRATEGY
  └─ prepares S2 prompt packages
  ↓
S2-SKETCH-EXPLORE
  └─ IMAGE_GENERATE only
  ↓
S3-DIRECTION-SELECT
  ├─ reviews generated S2 candidates
  ├─ aggregates S2 exploration signals
  └─ direction selection
  ↓
S4-CANDIDATE-BRIEF
  └─ prepares S5 prompt packages
  ↓
S5-CANDIDATE-IMAGE
  └─ IMAGE_GENERATE only
  ↓
END — human decision boundary
```

There is no assistant workflow after S5. Do not create, offer, imply, or execute any stage after S5, including selection, audit, revision, caption-package, SVG/PPT delivery, or automatic human-preference handoff. If the user asks what remains after S5, answer exactly:

```text
我的任务已经完成，剩下由人类来决策。
```

## Core Cross-Stage Control Rules

S1/S2/S3/S4/S5 must apply the academic hierarchy and image-asset mirror gates in `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`, the contribution-type visual priority gate in `references/contribution-type-visual-priority-policy-v3215e.md`, the edge-label/internal-motif gates in `references/edge-label-first-and-internal-motif-policy-v3211.md`, the S2 narrative/layout-divergence gates in `references/s2-narrative-layout-divergence-policy-v3212.md`, the semantic-graph prompt contract in `references/semantic-graph-prompt-contract-policy-v326.md`, the strict source-grounded modular prompt contract in `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md`, the layout density/mainline balance policy in `references/layout-density-mainline-balance-policy-v3215f.md`, the no-false-relay data-flow policy in `references/no-false-relay-data-flow-policy-v3215d.md`, the public-stage human wait barrier in `references/public-stage-human-wait-barrier-policy-v3215d.md`, the entity-compression and active-stage navigation guard in `references/entity-compression-and-active-stage-navigation-guard-policy-v3215a.md`, the first-round default-style guidance in `references/first-round-default-style-guidance-policy-v3215a.md`, the style-combination selection and human palette policy in `references/style-combination-selection-and-human-palette-policy-v3215d.md`, the preferred first-round carryover and preference-led second-round coverage policies in `references/preferred-first-round-carryover-policy-v3215b.md`, `references/preference-led-second-round-coverage-policy-v3215b.md`, and `references/s3-preference-carryover-formal-candidate-policy-v3215b.md`, the S5 S2 reference-image input policy in `references/s5-s2-reference-image-input-policy-v3215f.md`, the S0 semantic precision and role-variation lock in `references/s0-semantic-precision-and-role-variation-lock-policy-v3215f.md`, the optional ACM/IEEE/AAAI first-/second-round line-art schematic style policy in `references/acm-ieee-aaai-line-art-schematic-style-policy-v3215c.md`, the cumulative checkpoint response/repair-or-redo gates in `references/cumulative-checkpoint-response-gate-policy-v3215b.md`, `references/checkpoint-response-and-repair-gate-policy-v3215b.md`, and `references/restore-repair-or-redo-policy-v3215b.md`, the paper-neutral hardcoding lint policy in `references/paper-neutral-hardcoding-lint-policy-v3215b.md`, the response checkpoint zip gate policy in `references/response-checkpoint-zip-gate-policy-v3215b.md`, the source-faithful prompt audit and symbol disambiguation policy in `references/source-faithful-image-prompt-audit-policy-v3215b.md`, the skill packaging context economy policy in `references/skill-packaging-context-on-demand-policy-v3215b.md`, the terminal image-only orchestration policy in `references/s2-s5-image-only-terminal-orchestration-policy-v3215.md`, the row-atomic image-generation guard policy in `references/s2-s5-row-atomic-image-generation-guard-policy-v3215f.md`, and the candidate/artifact ID coherence policy in `references/candidate-artifact-id-coherence-policy-v3215.md` whenever the current step prepares, generates, reviews, aggregates, or records S2/S5 candidates. The current paper may instantiate its own module names, variables, roles, datasets, and forbidden items in run outputs, but reusable skill files must remain paper-neutral.

S1/S4 must also apply `references/routing-line-style-and-callout-abstraction-policy-v3215f.md` whenever a prompt package uses dashed/dotted lines, feedback/exchange/reuse connectors, zooms, cutaways, insets, detail panels, or mechanism strips. This paper-neutral policy is mandatory for preventing meaningless auxiliary line work and for separating an abstract main-framework module from its detailed callout or magnified view.

S0 must apply `references/s0-semantic-precision-and-role-variation-lock-policy-v3215f.md` before it marks the foundation ready. S0 analysis may not leave broad figure directives as ambiguous prose. Any instruction such as preserving role differences, showing multiple actors, highlighting heterogeneity, reflecting interactions, or distinguishing conditions must be converted into concrete scientific meaning, visual-safe implementation, forbidden misimplementation, and downstream carry-forward records in `outputs/S0-paper-foundation/s0-semantic-precision-contract.json`. If repeated roles/actors/conditions share the same canonical workflow, S0 must explicitly forbid implementing the difference as one complete workflow per role and prescribe compact markers, chips, branches-only-where-distinct, topology/context inset, comparison lanes, or caption-only representation as source evidence permits. S1/S4 must consume this contract and may not reinterpret vague S0 language as permission for duplicated full lanes. If the contract is missing or incomplete while S0 contains high-risk vague directives, S1/S4 must stop and repair or rerun S0 before prompt preparation.

Each S2/S5 prompt package must derive a paper-specific `contribution_type_visual_priority`, `primary_reader_question`, `visual_mainline_decision`, `data_flow_mainline_justification`, `primary_module_whitelist`, classify non-module artifacts/symbols/metrics/parameters into non-peer visual roles, create `edge_support_ledger`, `visual_hierarchy_plan`, `artifact_block_guard`, `connector_bundling_plan`, `connector_multiplicity_audit`, `data_consumer_transformer_ledger`, `false_relay_data_flow_audit`, `modularity_not_fragmentation_gate`, `simple_internal_motif_gate`, `core_operation_chain_ledger`, `core_operation_location_binding`, `operation_result_non_substitution_audit`, `image_required_core_operation_location_plan`, `background_context_budget_gate`, `layout_information_density_plan`, `canvas_area_budget`, `context_inset_budget`, `mainline_center_of_gravity_gate`, `layout_density_audit`, `academic_layout_hierarchy_gate`, `edge_label_first_artifact_policy`, `visual_render_graph`, `line_carried_variable_registry`, `visible_text_contract`, `internal_visual_motif_plan`, `redundancy_budget`, `entity_variant_classification`, `process_instance_budget`, `multiplicity_positive_lock`, `variant_to_lane_risk_audit`, `adversarial_generation_risk_audit`, `source_faithfulness_audit`, `symbol_disambiguation_audit`, `strict_logical_inference_ledger`, `prompt_contradiction_audit`, `palette_strategy`, `palette_semantic_mapping`, `palette_anti_ai_artifact_rules`, `human_aesthetic_rationale`, and `color_accessibility_note`, and use bundled connector families before image generation. S4/S5 prompt packages must additionally record `s5_reference_image_input_plan` and row-level `reference_image_paths` pointing to relevant registered S2 raster outputs; S5 must use those images as references when the active image route supports image inputs and must ignore them automatically when it does not. S1 and S4 must audit and repair prompt packages up to five cycles; if blockers remain after the fifth cycle, they must stop at a textual checkpoint/residual-risk ledger rather than hand off to image generation. S3 text review of S2 images must record `artifact_as_block_error`, `variable_as_block_error`, `edge_label_eligible_box_error`, `false_relay_data_flow_error`, `visual_mainline_mismatch`, `data_flow_overdominance`, `visual_render_graph_violation`, `text_only_core_mechanism_error`, `missing_core_operation_step`, `missing_operation_location_binding`, `output_or_state_substituted_for_operation`, `unanchored_core_effect_error`, `bullet_list_substitution`, `hierarchy_flattening`, `unbundled_parallel_edges`, `line_semantics_ambiguous`, `excessive_whitespace`, `core_method_underfilled_canvas`, `fragmented_microblock_scatter`, `off_center_mainline`, `top_heavy_context_panel`, `support_context_area_overrun`, and `context_inset_dominates_method` when visible sketches violate those gates. Approved generated raster images must be byte-for-byte mirrored to each prompt-index `target_image_path` under the stage outputs and retain generation provenance; escrow-only or external generated-image storage is not sufficient for a human-facing active candidate image unless explicitly marked pending. prompt-index `candidate_id` is the source of truth. The prompt-index row-level `candidate_id` is the source of truth: the same id must match the `prompt_path`, `target_image_path`, stage manifest, substage `candidate_ids`, candidate registry key, artifact `candidate_id`, active image path, reference image path records where present, and checkpoint image inventory. Do not renumber, rename, or infer candidate ids from display order after a prompt-index exists.

When dashed/dotted connectors, feedback/exchange/reuse links, zooms, cutaways, insets, mechanism strips, or detail panels appear in S1/S4 planning, each affected S2/S5 prompt package must additionally include `connector_style_semantic_budget`, `dashed_line_budget`, `routing_geometry_contract`, `callout_abstraction_contract`, `detail_panel_new_information_audit`, and `main_detail_nonduplication_gate`. S3 issue ledgers must additionally record `meaningless_dashed_line`, `line_style_semantic_overload`, `floating_or_unanchored_connector`, `long_auxiliary_rail`, `main_detail_duplicate`, `foreign_detail_import`, and `callout_as_flow_error` when visible candidates violate those contracts.

If an S3 prompt, S3 user message, S3 issue ledger, or S3 direction record names one or more user-preferred first-round S2 candidate IDs, S3 must record those IDs in machine-readable form as `user_preferred_first_round_candidate_ids`. S4 must then allocate at least one second-round S5 local-essence refinement led by each preferred S2 candidate for every active S5 style/treatment family that S4 keeps after feasibility planning. The S5 row must record fields equivalent to `source_first_round_candidate_id`, `dominant_source_candidate_id`, `style_id`, `style_family`, `lineage_role: preference_led_local_essence_refinement`, and `preference_coverage_role: preferred_first_round_local_essence_lead`. S4 must fit the formal candidate matrix into exactly two S5 candidates. If preference × style coverage cannot fit within two candidates, S4 must repair/replan the style-slot/preference allocation or ask the user to narrow preferences/styles before S5 handoff; it must not silently drop preference-led rows or create a third scheme. This rule is generic and derives candidate IDs and style families from S3/S4/S5 records; it must not hard-code any project, paper, ID list, page count, or domain terms.

S2/S5 candidate-level rerun is removed. Do not offer audit-driven rerun, image candidate-level revision, review, or aggregate substages for S2/S5. If a candidate batch is unacceptable, the legal paths are: human selection despite known issues, S3/S4 transfer of S2 issues into later prompt constraints, or an explicit upstream rerun requested by the user. S5 has no assistant-side downstream rerun path.

## Strict Prompt Contract For S1/S4 Image Prompts

S1 and S4 prompt packages must include a hard-constraint block inside every image-generation prompt. The block must enforce contribution-type visual priority, source-supported connectors, one bundled connector between two block-level modules unless distinct labeled quantities justify multiple lines, no false relay data-flow edges through non-consuming/non-transforming modules, variables on connectors/ports/forks/merges/tags rather than peer module boxes, modular-not-fragmented structure, simple reviewer-recognizable internal motifs, source-grounded core operation chains, no redundant duplicate workflow or duplicate inset, small background/context budget, method-framework priority, compact-balanced layout density, centered mainline visual focus, small subordinate context/inset budget, one canonical process by default, and compact-marker compression for repeated entity families unless source evidence justifies distinct branches.

For every arrow or line, S1/S4 must be able to point to the paper/material evidence for both upstream and downstream endpoint meaning and to the true consumer or transformer of every carried quantity. If A produces data `x` and C consumes `x` while B does not use, transform, filter, store, or route `x`, the prompt must not draw or label A->B as carrying `x`; draw A->C, attach `x` to C's input/port/tag, or move `x` to caption/legend when a direct connector would clutter the figure. For every source-grounded core mechanism, S1/S4 must preserve the minimal `input/context -> operation/change -> output/effect` chain at the correct module, phase, loop, path, or layer; a visible output, state, structure, decision, signal, material, configuration, or effect alone does not cover the operation that creates, selects, transforms, validates, routes, applies, or updates it. Unsupported arrows, decorative connectors, false pass-through relay edges, repeated parallel lines with the same meaning, unlocated core operations, dense internal mini-workflows, complex submodule diagrams, and repeated workflows are prompt blockers. Internal submodule visuals should use simple common conventions such as process-step tokens, state/structure changes, measurement tags, decision gates, merge/fork cues, score/evidence tags, and light feedback/update loops; they should not become a second full algorithm inside the figure.

Before S1/S4 hands off to S2/S5 image generation, every prompt package must include a source-fidelity table covering visible entities, labels, symbols, arrows/lines, and inferred relations. Entries must be marked `direct_source`, `strict_logical_inference`, `remove`, or `revise`; `remove`/`revise` entries block handoff until repaired. Symbol tokens, variables, metrics, and edge labels must be one-to-one with the paper semantics or explicitly grouped without semantic loss.

This modularity requirement applies across all style choices. A formal publication schematic, low-fidelity sketch, blueprint, scientific illustration, storyboard, or infographic surface may vary visually, but the figure must remain a modular paper-framework map rather than a fragmented set of micro-panels. For algorithm/model/framework figures, whitespace must be compact and functional: the primary method content should occupy the central visual field, background or topology context must stay subordinate, and large empty quadrants or top-heavy context banners are prompt blockers unless a physical-layout exception is recorded.

Every S1/S4 prompt package must also include the v3.2.15f human palette contract: restrained publication-grade palette, source-supported color semantics, grayscale legibility, one primary accent plus one secondary accent where possible, and explicit avoidance of generic AI-blue/purple gradients, neon saturation, glossy orb/glass effects, bokeh, marketing-poster lighting, and decorative color ramps.

Repeated entity families are not allowed to become repeated full process lanes by default. S1/S4 must classify repeated entity families, declare a process instance budget, include a positive multiplicity lock, run a variant-to-lane risk audit, and run an adversarial generation risk audit. If those checks leave high residual risk, stop before image-only handoff and write a residual-risk checkpoint.

Next-step prompt suggestions must resolve conversation-aware `navigation_state` before `restore_state`: current-conversation stage execution and image generation events outrank checkpoint recency. Generate user-facing next prompts only from the active stage transition table; if the generated prompt names the wrong next public stage or asks an image-only stage to review/rank/audit/select, block and regenerate it.

## v3.2.15f Preference Coverage And Checkpoint Repair Gates

进入/执行 S3-DIRECTION-SELECT 时，一旦用户输入或确认一个或多个偏好 first-round candidate IDs，后续 S4/S5 第二轮候选矩阵必须分别以这些 ID 为主线进行覆盖：每个用户偏好 ID 至少要主导构造 1 个第二轮候选图，且该候选必须在机器可读字段中记录其来源偏好 ID、lineage role、coverage role、对应 S5 candidate_id 与 target_image_path。不得把多个偏好 ID 合并成一个笼统参考信号后只生成单一候选；不得因为默认候选数量不足而遗漏任一偏好 ID，若数量冲突则必须在两个 S5 候选上限内修复/replan 或请求用户缩窄偏好/风格槽。

任何阶段或子阶段如果是纯文本回复，则必须生成项目起点到当前状态的累加 checkpoint zip，运行完整性审核，并写入 checkpoint/audit/repair 状态；不得遗漏已有信息，不得只写增量 checkpoint，不得在未通过审核时宣称 checkpoint 可恢复或阶段已完成。

If the S3 user prompt names one or more preferred first-round S2 candidate IDs, S3 must record them in a paper-neutral preference-signal field and carry them into S4 as weighted preference signals. S4 must then include at least one S5 second-round local-essence candidate led by each preferred first-round candidate for every S4-declared formal style/treatment slot that remains feasible after planning. This requirement is dynamic but bounded: derive the required rows from the preference IDs and style slots, and never exceed two second-round S5 schemes. If the preference × style coverage cannot fit within two, the related S4 matrix/prompt-preparation step must be repaired/replanned or redone with a feasible style-slot/candidate allocation before S5 handoff; do not silently drop preferred IDs, active styles, candidate rows, page counts, or paths, and do not create a third S5 row. Do not hard-code preferred IDs, style counts, candidate counts, page counts, or project-specific image paths.

Preference-led second-round candidates must preserve only the useful local visual essence of the preferred first-round candidate; they must repair S3 issue-ledger problems and continue to obey source-grounded arrows, modular hierarchy, edge-label-first variables, and the selected S3 direction. A user preference is a coverage and weighting signal, not permission to copy unsupported or flawed first-round structures.

Whenever code or helper scripts write candidate matrices, prompt-index files, image registrations, or checkpoints, the run must include a generic validation step. If a cumulative checkpoint is missing any prior-stage root, existing asset, registered raster image, active stage-local mirror, `checkpoint-manifest.json`, or passing `checkpoint-cumulative-integrity.json`, and `checkpoint-integrity-audit.json`, rebuild from cumulative roots and rerun the guard before presenting the checkpoint as usable. Never choose a checkpoint by sequence number alone.

If validation still cannot produce a complete cumulative restore bundle, the current or affected public step is not allowed to close as restore-ready. The workflow must identify the earliest affected stage, redo that stage or its image-output registration/prompt-preparation step, and then rebuild the cumulative checkpoint until the guard passes. `redo_required` is not a final user-facing checkpoint status in v3.2.15f; diagnostic reports may say `redo_required`, but a checkpoint link may only be presented when it is `complete_restore_ready`.

## Strict Human-In-The-Loop Step Alternation

This rule is mandatory and applies to every runtime environment. The workflow is not an autonomous pipeline.

Initial bootstrap gate is stricter than the normal one-step rule. If the user only gives an overall goal such as "use this skill", "draw a diagram for this paper", "strictly follow the workflow", "逐步通过人机交互绘制 diagram", or provides a paper/PDF without explicitly saying "进入/执行 S0-PAPER-FOUNDATION" in the current user turn, do not execute S0. Do not read the paper, extract text, create a project, create or modify state, register artifacts, write outputs, run workflow scripts, or mark any step complete. The first reply must be plan-only: explain that S0 is the recommended first step, list missing inputs or environment assumptions, provide a copyable prompt to enter S0-PAPER-FOUNDATION, include the required design-origin prompt suggestion, and stop.

For each user turn, execute at most one explicitly requested public step. After completing that step, stop. This is a hard runtime human wait barrier: the next public step requires a later explicit user message or a source-allowed explicit skip/default/automation choice recorded before the barrier. Reviewer gates, internal agent handoffs, specialist completion, checkpoint success, silent defaults, and copyable next prompts do not satisfy the human wait barrier. The reply may provide the next legal copyable prompt, except after S5 where the workflow is complete. Copyable prompts are inert handoff text. Never self-consume or execute a prompt that you just wrote in the same assistant response.

Never combine adjacent public steps in one reply. In particular: S0 must not auto-run S1; S1 must not auto-generate S2 images; S2 must not auto-run S3 direction selection; S3 must not auto-run S4; S4 must not auto-generate S5 images; S5 must not auto-run anything.

Every text public-step response must explicitly close the current public step by its exact ID when that public step actually closes. At the end of S0-S4, write that the current public step is complete/ended, state that the next public step has not been executed, and provide only the next copyable prompt. S2 and S5 are image-only public stages; they do not contain text planning, text review, candidate-level revision, review, or aggregate substages.

## Mandatory Surface-Style Handoff Reminders

These reminders are mandatory visible user-facing text, not optional summaries. Do not compress them to "style options exist" and do not omit the option list. They must appear outside the copyable next-step prompt block so optional style text is not accidentally copied into the default prompt.

### S0-to-S1 and S1-to-S2 first-round reminder

S0-to-S1 and S1-to-S2 handoffs must explicitly tell the user that the first-round S2 default surface style is `formal_publication_schematic` / 正式出版风格. The handoff must also state that changing or cancelling this default requires an explicit sentence in the S1 request before S1 prepares S2 prompt packages. If S1 has already closed, changing the surface before S2 requires rerunning S1 because S2 follows the S1 prompt-index.

At S0-to-S1, include this full non-copyable Chinese reminder outside the copyable S1 prompt block; do not summarize it:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格；这只约束渲染表面，不等同于候选图的叙事、布局或处理方案。若要修改，请在下一轮 S1 请求中另行明确写入表面风格选择或取消默认表面风格；请不要把本说明复制进默认提示词块。可写例如“第一轮采用 ACM/IEEE/AAAI 双栏论文 line-art schematic 表面风格”，也可以写“取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格”。可选表面风格包括：正式出版风格、低保真草图、白板线框、干净扁平极简线稿、正式 schematic 布局草案、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、手绘故事板、ACM/IEEE/AAAI 双栏论文 line-art schematic。
```

At S1-to-S2, include this full non-copyable Chinese reminder outside the copyable S2 image-only prompt block; do not summarize it:

```text
非复制表面风格提示：第一轮 S2 默认表面风格为正式出版风格，除非 S1 已在 prompt-index 中记录了显式覆盖或取消默认表面风格；S2 只会按该记录生成图片。若想在运行 S2 前修改第一轮表面风格，需要回到 S1 重做 prompt packages，而不是改 S2 生图提示词。可选表面风格包括：正式出版风格、低保真草图、白板线框、干净扁平极简线稿、正式 schematic 布局草案、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、手绘故事板、ACM/IEEE/AAAI 双栏论文 line-art schematic。可在重新执行 S1 时另行写入例如“第一轮采用 轻量蓝图精密稿 表面风格”或“取消默认表面风格，请 S1 根据论文实际需要自行设置表面风格”。
```

### S3-to-S4 second-round reminder

S3-to-S4 handoff must include the full second-round surface-style reminder outside the copyable S4 prompt block. It must tell the user that any second-round S5 surface-style choice or default-surface cancellation must be written explicitly in the next S4 request, because S4 owns second-round surface-style recording and S5 prompt-package injection. S3 must not insert optional surface-style text into the copyable S4 prompt, and S4-to-S5 must not repeat this reminder.

Use this full non-copyable Chinese reminder at S3-to-S4; do not summarize it:

```text
可选第二轮表面风格：S5 正式候选默认由 S4 根据论文需要设置表面风格；表面风格只约束渲染层，不改变候选图的论文语义、布局骨架、连线证据和密度预算。若希望指定第二轮表面风格，请在下一轮 S4 请求中另行写入“第二轮采用 <表面风格名> 表面风格”。可选项包括：正式出版风格、干净扁平极简线稿、轻量蓝图精密稿、轻量科学插画、轻量界面隐喻、轻量等距结构、轻量信息图板、ACM/IEEE/AAAI 双栏论文 line-art schematic。也可以写“取消默认表面风格，请 S4 根据论文实际需要自行设置 S5 表面风格”。低保真草图、白板线框、手绘故事板默认只适合第一轮探索；若要用于第二轮，必须在 S4 请求中明确说明它仍需保持 formal candidate 可读性。
```

## ChatGPT Web Text-Only Guard

For every text-only public step, the displayed copyable prompt must include:

```text
本轮纯文字：只执行文字、state、manifest、brief、audit、guidance 或 checkpoint 写入；不要生成任何图片。
```

This applies to `S0-PAPER-FOUNDATION`, `S1-FIGURE-STRATEGY`, `S3-DIRECTION-SELECT`, and `S4-CANDIDATE-BRIEF`. It also applies to embedded S2 preparation inside S1, embedded S2 audit/aggregate inside S3, and embedded S5 preparation inside S4. A later user turn may run S2 or S5 only when that later prompt is explicitly image-only.

## Public Stages

- **S0-PAPER-FOUNDATION**: text-only foundation stage. Build paper/source foundation, runtime state, framework-figure readiness state, semantic precision contract, optional author supplement request, risk register, and the non-copyable S0-to-S1 first-round surface-style note. S0 must disambiguate high-risk visual directives into concrete downstream constraints; it must not design or generate images.
- **S1-FIGURE-STRATEGY**: text-only strategy stage. It must consume S0 foundation/risk register, define reader question, figure role, paper-core semantics lock, candidate strategy, style/layout matrices, any first-round surface-style override or default-surface cancellation explicitly supplied with the S1 request, core-detail display requirements, edge/port seed contracts, visible text whitelist, repetition compression plan, and the S2 prompt-package preparation. S1 must output S2 prompt packages and prompt-index, then stop before S2 image generation.
- **S2-SKETCH-EXPLORE**: image-only stage. It only generates first-round framework candidates from the S1-prepared prompt-index, using the formal publication surface-style default unless an explicit compatible override or default-surface cancellation is already recorded in S1 artifacts. It must execute the prompt-index as a row-atomic queue: one image-generation call per selected/non-skipped row, one candidate_id, one prompt_path, one target_image_path, and no multi-row composite. It must not write audit, ranking, explanation, rerun guidance, checkpoint narrative, surface-style negotiation, or next-step prose.
- **S3-DIRECTION-SELECT**: text-only selection stage. It must first perform the S3 review/aggregate responsibilities over S2 outputs by reading generated S2 candidates and their registry, writing issue-ledger/visual-signal summaries, recording which visual ideas are useful or risky, recording any explicit user-preferred first-round candidate IDs as weighted preference signals, and creating the cumulative S3 checkpoint. Then it selects the paper-grounded refinement direction. S3 does not generate images and does not rerun S2 images.
- **S4-CANDIDATE-BRIEF**: text-only formal-brief stage. It must consume S0-S3 evidence, transfer S2 issues into S5 negative constraints, create formal candidate matrix, enforce preference-led second-round coverage when S3 recorded explicit preferred first-round candidates, create layout/routing/arrow contracts, text whitelist, line-carried variable registry, internal visual motif plan, caption-support plan, prompt contradiction audit, and the S5 prompt-package preparation. S4 owns second-round surface-style recording and injection; S3 exposes a non-copyable second-round surface-style options note so the user can add a style sentence to the next S4 request. S4 must output S5 prompt packages and prompt-index, then stop before S5 image generation without adding a S4-to-S5 surface-style reminder.
- **S5-CANDIDATE-IMAGE**: image-only terminal stage. It only generates formal publication-schematic raster candidates from the S4-prepared prompt-index, applying an explicit compatible surface-style override only when it is recorded in S4 artifacts or the current S5 image-only prompt. It must execute the prompt-index as a row-atomic queue: one image-generation call per selected/non-skipped row, one candidate_id, one prompt_path, one target_image_path, and no multi-row composite. It must not write audit, ranking, explanation, rerun guidance, assistant-continuation guidance, caption package, checkpoint narrative, or next-step prose. After S5 image generation, assistant workflow is complete.

## S0-PAPER-FOUNDATION

S0 internal responsibilities:

1. `S0-00-input-inventory`: register paper files/text, supplemental materials, user constraints, runtime, canvas defaults, and preference references.
2. `S0-01-paper-deep-read`: read source text and write `paper-foundation-report.md`.
3. `S0-02-semantic-precision-contract`: write `s0-semantic-precision-contract.json` and mirror it in the report. Normalize every high-risk vague directive into concrete meaning, visual-safe instruction, forbidden interpretation, repeated-role/condition representation decision, and downstream S1/S4 carry-forward.
4. `S0-03-framework-figure-risk-screen`: detect missing information, unresolved vague directives, ambiguities, contradictions, unsupported lineage, opaque core modules, and scope mismatch.
5. `S0-04-author-supplement-request-or-risk-lock`: request author supplement when needed, or record risk lock if user chooses to continue.
6. `S0-05-user-response-integration`: integrate user supplements and update the semantic precision contract.
7. `S0-06-foundation-lock`: write `framework-figure-risk-register.md` and readiness state.
8. `S0-07-s0-to-s1-handoff`: provide the S1 copyable prompt, then separately show the first-round surface-style choice note outside the copyable prompt block. The optional surface-style menu, ACM/IEEE/AAAI phrase, and default-surface cancellation phrase must not be inserted into the suggested S1 prompt text.

Readiness states: `S0_FOUNDATION_READY`, `S0_FOUNDATION_READY_WITH_RISK`, `S0_NEEDS_AUTHOR_SUPPLEMENT`, `S0_NOT_SUITABLE_FOR_COMPLETE_FRAMEWORK`.

S0 precision lock: the output `s0-semantic-precision-contract.json` is required before S0 can close. It must include `ambiguous_directive_normalization`, `actor_or_condition_variation_matrix`, `role_visual_realization_contract`, `process_instance_budget`, `forbidden_misimplementation_locks`, and `downstream_s1_s4_carry_forward`. A phrase like “保留角色差异 / preserve role differences” is invalid unless S0 also says exactly whether the role difference is drawn as compact markers, branch-only distinct segment, true parallel lanes, comparison lanes, topology/context inset, or caption-only, and exactly what must not be drawn.

## S1-FIGURE-STRATEGY — prepares S2 prompt packages

S1 must not merely say that S2 preparation may happen later. Before S1 closes, it must complete the S2 prompt-package preparation responsibilities as embedded duties:

- S2 candidate registry and exactly 4 selected first-round candidate cards. S1 must first plan 8 complementary style combinations, score all 8, select the top 4 overall combinations, explain how each selected combination's style ingredients are complementary rather than contradictory, and map only those 4 selections to `C01`-`C04`.
- S2 orthogonal style-feature matrix and narrative/layout-divergence matrix.
- Contribution-type visual priority gate: classify the paper's primary contribution as method/process, architecture/module, system/interaction, model-state/update, data/dataset/database/data-pipeline, evaluation/benchmark, or hybrid; record the primary reader question, visual mainline, and whether a data-flow mainline is source-justified. Data flow may be the main visual backbone only when the contribution itself is about data construction, database/data management, retrieval, generation, governance, or pipeline design; otherwise data labels must remain supportive and compact.
- Complete-framework eligibility audit: required S2 candidates must be full-framework candidates unless the user explicitly requested scoped probes.
- S0 semantic precision consumption: read `outputs/S0-paper-foundation/s0-semantic-precision-contract.json` before candidate-card or prompt-package preparation. Carry every role/condition representation decision and every forbidden misimplementation lock into S2 prompt packages. Do not turn a shared-role marker contract into duplicated full workflows.
- Core-detail display matrix: source-grounded core contribution modules need visible internal mechanisms, not empty title boxes or bullet lists.
- Entity/artifact/symbol classification and semantic graph vs visual render graph split.
- Edge/port/arrow seed contract with direction evidence and forbidden-edge list.
- Edge-label-first and line-carried variable registry.
- Strict prompt audit: contribution-type visual priority check, edge-support ledger, connector multiplicity/bundling check, data consumer/transformer ledger, false relay data-flow check, variable placement check, modularity-not-fragmentation gate, simple internal motif gate, workflow redundancy gate, and background/context budget gate; repair prompt packages up to 5 cycles before writing prompt-index.
- Visible text whitelist and prompt contradiction audit.
- First-round default surface-style contract: unless the user explicitly overrides or cancels it, every S2 prompt package uses `first_round_default_style_id: formal_publication_schematic` and requests a clean formal publication-style framework schematic as the first-round surface.
- Surface-style dimension contract: a surface style is only the rendering layer. S1 must combine any surface style with narrative role, layout grammar, semantic focus, density, detail strategy, visual rhetoric, connector hierarchy, and source-grounded constraints; the surface style must not be treated as the whole candidate style.
- First-round surface-style decision intake: S1 must read any first-round surface-style override or default-surface cancellation that the user explicitly added to the S1 request after seeing the S0-to-S1 non-copyable surface-style note. If no override or cancellation is present, record `first_round_default_style_id: formal_publication_schematic`.
- Optional first-round surface menu: if the S1 user prompt explicitly requests a compatible first-round surface style, S1 must record the selected surface style in state/prompt packages and inject any required style block. `acm_ieee_aaai_line_art_schematic` still uses the style block from `references/acm-ieee-aaai-line-art-schematic-style-policy-v3215c.md`. S1-to-S2 must expose the full mandatory non-copyable first-round surface-style reminder from "Mandatory Surface-Style Handoff Reminders" outside the copyable S2 prompt so users know alternatives exist. Because S2 is image-only and follows the S1 prompt-index, this S1-to-S2 note must say that changing the already prepared first-round surface requires rerunning S1 before S2, not editing the S2 image-only prompt.
- Prompt packages and `outputs/S2-sketch-explore/prompt-index.json`; default S2 ids are exactly `C01`-`C04`, and every row must keep `candidate_id`, `prompt_path`, and `target_image_path` coherent. S1 must not write prompt packages for the four rejected style-combination planning rows.
- Cumulative S1 checkpoint containing all S2 prompt-preparation outputs as pending future image targets.

S1 closes by giving the S2 image-only prompt plus the full mandatory non-copyable first-round surface-style options note outside the copyable S2 prompt. It may state the recorded first-round surface-style decision in state/audit outputs. It must not place optional first-round surface-style text inside the copyable S2 prompt, and it must clearly say that any first-round surface change after S1 requires rerunning S1 before S2 because S2 follows the prepared prompt-index. It must not generate S2 images.

## S2-SKETCH-EXPLORE — IMAGE_GENERATE only

S2 is a pure image-generation public stage. It reads the S1-prepared prompt-index and generates exactly 4 requested first-round candidates through the environment-locked image route. If the prompt-index defines a different selected/non-skipped row set that has already passed S1 validation, use that row set as the source of truth without inventing extra candidates. If the prompt-index does not contain an explicit first-round surface-style override or default-surface cancellation recorded by S1, S2 uses the formal publication surface-style default. S2 must keep the exact prompt-index candidate ids, read each row's `prompt_path`, apply only the surface-style and human-palette decisions already recorded in S1 artifacts, and register/mirror generated raster images to the same row's `target_image_path`.

S2 row-atomic generation gate: before generating, create/obey an image-call queue from prompt-index selected/non-skipped rows. Each queue unit has exactly one `candidate_id`, one `prompt_path`, one `target_image_path`, and optional row-local reference fields only when the stage allows them. A single image-generation call cannot satisfy more than one queue unit, even if the runtime can request multiple outputs. A generated raster that is not mirrored to the matching row `target_image_path` and bound to the same candidate id is an orphan and is not an active S2 candidate. S2 is incomplete until every queue unit has its own registered raster; do not advance to S3 or claim S2 completion after only one generated image when more rows remain. S2 must not perform text planning, audit, aggregate, revision, review, ranking, surface-style discussion, surface-style negotiation, or finalization.

## S3-DIRECTION-SELECT — reviews and aggregates generated S2 candidates

S3 must complete review and aggregation over S2 outputs before direction selection:

- Read all registered S2 candidate images and prompt-index rows.
- Create issue-ledger style notes for visible problems, semantic violations, visual mainline mismatch, data-flow overdominance, missing core internal motifs, arrow/connector confusion, variable-as-block errors, unsupported topology, excessive density, unbalanced whitespace, and caption-burden risks.
- Summarize visual exploration signals without treating S2 audit as a score-only ranking.
- Create the S2 exploration aggregate within the S3 report/checkpoint.
- Select the refinement direction using S0/S1 evidence, S2 visual signals, and user preference.
- If the user names preferred first-round S2 candidate IDs, record them as `user_preferred_first_round_candidate_ids` and preserve them as S4 carryover requirements unless the user withdraws them.
- Record which S2 ideas S4 should absorb, avoid, or transform.
- If the S3 handoff prompt is being suggested after S2, remind the user that they may name one or several preferred first-round candidate IDs as reference signals for S3/S4; S3 still performs evidence-based issue-ledger review and source-faithful direction selection.

S3 closes by giving the S4 prompt plus the full mandatory non-copyable second-round surface-style options note outside the copyable S4 prompt. It must not generate images and must not rerun S2 candidates. The suggested S4 prompt itself must not include optional surface-style text. S3 does not set or inject the second-round surface style. If the user manually writes a compatible second-round surface choice or a default-surface cancellation into the S4 request, S4 must carry that surface-style policy into S5 prompt packages.

## S4-CANDIDATE-BRIEF — prepares S5 prompt packages

S4 must not merely say that S5 preparation may happen later. Before S4 closes, it must complete the S5 prompt-package preparation responsibilities as embedded duties:

- Formal candidate matrix, exactly 2 candidates for complete-framework tasks. Default formal ids are `F01`-`F02` unless a validated S5 prompt-index defines a different safe two-row id set. If S3 recorded user-preferred S2 candidate IDs, S4 must fit preference-led second-round local-essence coverage into the two S5 rows by reducing/merging active style slots only when that does not drop a recorded preference. If the required coverage exceeds two rows, repair/replan or ask the user to narrow preferences/styles before S5 handoff. These rows must be led by the named preferred source candidate as a visual-preference signal while repairing any S2/S3 issues and preserving source-grounded semantics.
- A machine-readable `preference_carryover_coverage_audit` covering preferred IDs, style families, required pairs, satisfying S5 IDs, and unsatisfied pairs. S4 must run `scripts/figure_studio_preference_coverage_guard.py` or an equivalent paper-neutral coverage check and block S5 handoff if any required pair is unsatisfied.
- S2 issue transfer into S5 negative constraints and must-fix prompt rules.
- S2 reference-image input plan: every F01-F02 S5 prompt-index row must list relevant registered S2 raster images in `reference_image_paths`; these are visual reference inputs for S5 when supported and are automatically ignored when unsupported.
- Element layout contract, routing/arrow/port contract, connector line-style semantic budget, callout abstraction contract, text whitelist, line-carried variable registry, internal visual motif plan, and caption-support plan.
- Contribution-type visual priority gate: carry forward or revise the S3-selected reader question and visual mainline; preserve data-flow as the main visual backbone only when source evidence says the contribution is data/dataset/database/retrieval/generation/governance/pipeline centered.
- Strict prompt audit: contribution-type visual priority check, edge-support ledger, connector multiplicity/bundling check, line-style semantic-budget check, dashed-line budget check, routing geometry check, main-detail nonduplication gate, data consumer/transformer ledger, false relay data-flow check, variable placement check, modularity-not-fragmentation gate, simple internal motif gate, workflow redundancy gate, and background/context budget gate; repair prompt packages up to 5 cycles before writing prompt-index.
- Formal prompt contradiction audit and prompt-file-read audit.
- If the S4 user prompt explicitly requests a compatible second-round surface style, record `style_id`, `style_label`, `style_family`, and row/stage scope as active S5 surface-style/treatment slots and inject any required style block into every affected S5 image prompt package. `acm_ieee_aaai_line_art_schematic` uses the prompt block from `references/acm-ieee-aaai-line-art-schematic-style-policy-v3215c.md`; other compatible surfaces must still be formal-candidate-safe and source-grounded. If the S4 user prompt explicitly cancels the default surface style, record that cancellation and derive each S5 surface from paper needs.
- S4-to-S5 surface-style reminder rule: do not include a second-round surface-style reminder outside or inside the copyable S5 prompt. Surface-style decisions should be recorded during S4 from S3-to-S4/S4 input; after S4, the next public prompt is S5 image-only.

- S0 semantic precision carry-forward: preserve `role_visual_realization_contract`, `process_instance_budget`, and `forbidden_misimplementation_locks` from S0/S1/S3 unless a source-grounded S4 repair explicitly changes them. S5 formal prompts must not re-expand compact role/condition markers into one full process per repeated role.
- Prompt packages and `outputs/S5-candidate-image/prompt-index.json`; default S5 ids are exactly `F01`-`F02`, and every row must keep `candidate_id`, `prompt_path`, and `target_image_path` coherent. S4 must include a non-AI-looking human palette contract in every S5 prompt package.
- Cumulative S4 checkpoint containing all S5 prompt-preparation outputs as pending future image targets.

S4 closes by giving only the S5 image-only prompt. It must not generate S5 images and must not add a second-round surface-style reminder.

## S5-CANDIDATE-IMAGE — IMAGE_GENERATE only and terminal

S5 is a pure image-generation public stage. It reads the S4-prepared prompt-index and generates exactly 2 requested formal candidates through the environment-locked image route unless a validated S5 prompt-index defines a different safe two-row-equivalent set. It must keep the exact prompt-index candidate ids, read each row's `prompt_path`, read each row's S2 `reference_image_paths`, apply an explicit compatible surface-style override such as `acm_ieee_aaai_line_art_schematic` only when recorded in S4 artifacts or stated in the current S5 image-only prompt, apply recorded default-surface cancellation when present, apply the S4 human-palette contract, and register/mirror generated raster images to the same row's `target_image_path`. When the active S5 image route supports image inputs, pass the listed S2 images as visual references together with the prompt; when it cannot accept images, ignore those inputs automatically and continue with the text prompt.

S5 row-atomic generation gate: before generating, create/obey an image-call queue from prompt-index selected/non-skipped rows. Each queue unit has exactly one `candidate_id`, one `prompt_path`, one `target_image_path`, and only that row's `reference_image_paths`. A single image-generation call cannot satisfy more than one queue unit, even if the runtime can request multiple outputs. A generated raster that is not mirrored to the matching row `target_image_path` and bound to the same candidate id is an orphan and is not an active S5 candidate. S5 is incomplete until every queue unit has its own registered raster; do not claim terminal completion after only one generated image when more rows remain. S5 must not write audit, ranking, explanation, caption package, rerun guidance, assistant-continuation guidance, aggregate checkpoint, or next-step prompt.

After S5, the workflow ends. If the user asks what comes next, answer exactly:

```text
我的任务已经完成，剩下由人类来决策。
```

## Image Generation Route Lock

Target paper images must be generated only through the approved image route for the runtime:

- Codex: `image_gen`.
- ChatGPT web: Create Image / ChatGPT Images 2.0.
- Other runtimes: a named approved image-generation API only when first-party routes are unavailable and the reason is recorded.

Do not use SVG, Mermaid, HTML/canvas, Python/PIL/Pillow, Matplotlib/Plotly, Graphviz, TikZ/LaTeX, PPT/PDF rendering, screenshots, SVG-to-PNG, or any local programmatic raster substitute for target paper images.

## Checkpoints And State

Every text public stage or pure-text substage must create or validate a cumulative project-start-to-current restore bundle zip before any user-facing text reply closes or advances the stage. S1 checkpoint includes S2 prompt-index as pending future image targets. S3 checkpoint includes S2 generated-image registry plus embedded S2 audit/aggregate summaries and direction selection, and must contain the active registered S2 candidate images at their prompt-index target paths before S4 handoff. S4 checkpoint includes S5 prompt-index as pending future image targets, S5 `reference_image_paths` pointing to existing S2 raster references, plus any preference-carryover coverage audit. S2 and S5 are image-only stages; they register image generation events and active image paths but do not create text aggregate checkpoints. Because image-only stages may not update cumulative checkpoints, next-step guidance must use conversation-aware navigation state rather than checkpoint recency alone. Any response that links a checkpoint must first validate the linked zip's embedded cumulative integrity report and root audit; a delta bundle or zip without `checkpoint-manifest.json`, PASS `checkpoint-cumulative-integrity.json`, and `checkpoint-integrity-audit.json` must not be described or linked as a usable checkpoint.

Repair-or-redo gate: a missing or incomplete cumulative checkpoint must be repaired before the workflow can close the stage or present a usable checkpoint. If bounded generic repair cannot restore every required existing asset, registered raster, prompt package, state file, and integrity metadata item, the relevant producing stage/substage must be redone and the checkpoint rebuilt until it passes. `restore_repair_required_stage_redo` is a transient diagnostic status only; it is not a valid final close status and must not be used to proceed or to present a checkpoint as recoverable.

State files and registries must store relative paths only. Never add target-project paper facts, module names, datasets, claims, generated candidate summaries, output paths, or audit conclusions to the reusable skill package.

Useful state commands. When a prompt-index exists, pass it to `plan-substages` or rely on the default prompt-index path so candidate ids come from the prompt-index rather than from stage defaults:

```bash
python scripts/figure_studio_state.py plan-substages --project-id <project_id> --step S2-SKETCH-EXPLORE --runtime chatgpt_web --prompt-index outputs/S2-sketch-explore/prompt-index.json
python scripts/figure_studio_image_only_row_guard.py --run-dir figure-studio-runs/<project_id> --stage S2-SKETCH-EXPLORE --mode preflight --write-queue --fail-on-error
python scripts/figure_studio_state.py scan-substages --project-id <project_id> --step S2-SKETCH-EXPLORE
python scripts/figure_studio_image_only_row_guard.py --run-dir figure-studio-runs/<project_id> --stage S2-SKETCH-EXPLORE --mode postflight --require-state-provenance --fail-on-error
python scripts/figure_studio_state.py recommend-next-action --project-id <project_id> --step S5-CANDIDATE-IMAGE
python scripts/figure_studio_state.py register-image-batch --project-id <project_id> --step S2-SKETCH-EXPLORE --batch-id <row_batch_id> --prompt-index outputs/S2-sketch-explore/prompt-index.json --use-target-image-paths --start-index <row_ordinal> --output-dir outputs/S2-sketch-explore/registered-generated-images --source <one_row_generated_png> --generation-event-id <row_event_id> --replace
python scripts/figure_studio_state.py create-checkpoint --project-id <project_id> --stage S4-CANDIDATE-BRIEF --checkpoint-type stage-final --sequence 1
python scripts/figure_studio_checkpoint_guard.py --run-dir figure-studio-runs/<project_id> --stage S4-CANDIDATE-BRIEF --zip checkpoints/S4-CANDIDATE-BRIEF/stage-final-0001.zip --fail-on-error
python scripts/figure_studio_response_checkpoint_zip_gate.py --run-dir figure-studio-runs/<project_id> --stage S4-CANDIDATE-BRIEF --build-if-missing --fail-on-error
python scripts/figure_studio_preference_coverage_guard.py --s3-record outputs/S3-direction-select/direction-selection-record.json --prompt-index outputs/S5-candidate-image/prompt-index.json --fail-on-error
python scripts/figure_studio_state.py doctor --project-id <project_id>
```

## On-Demand Reference Loading

Keep this `SKILL.md` as the short controller. Load detailed references only when the current request needs them:

- `references/workflow-and-state-contract.md`
- `references/architecture-governance-contract.md`
- `references/module-orchestration-contract.md`
- `references/human-step-execution-contract.md`
- `references/image-generation-route-hardening-policy-v325.md`
- `references/first-round-default-style-guidance-policy-v3215a.md`
- `references/style-combination-selection-and-human-palette-policy-v3215d.md`
- `references/paper-deep-reading-contract.md`
- `references/s0-foundation-readiness-and-candidate-status-policy-v316.md`
- `references/s0-semantic-precision-and-role-variation-lock-policy-v3215f.md`
- `references/startup-preference-and-environment-contract.md`
- `references/startup-style-lens-decision-policy-v315.md`
- `references/prompt-generation-policy.md`
- `references/file-reference-prompt-handoff-policy-v324.md`
- `references/semantic-graph-prompt-contract-policy-v326.md`
- `references/framework-abstraction-flowline-and-rerun-prompt-policy-v328.md`
- `references/academic-framework-hierarchy-and-asset-mirroring-policy-v3210.md`
- `references/contribution-type-visual-priority-policy-v3215e.md`
- `references/edge-label-first-and-internal-motif-policy-v3211.md`
- `references/paper-core-semantics-and-prompt-contract-policy-v323.md`
- `references/source-grounded-prompt-audit-and-style-policy-v320.md`
- `references/visual-information-economy-and-repetition-control-policy-v322.md`
- `references/first-round-diversity-matrix-policy.md`
- `references/s2-s5-layout-routing-prompt-audit-policy-v317.md`
- `references/routing-line-style-and-callout-abstraction-policy-v3215f.md`
- `references/strict-source-grounded-modular-prompt-contract-policy-v3215a.md`
- `references/entity-compression-and-active-stage-navigation-guard-policy-v3215a.md`
- `references/first-glance-layout-sanity-policy-v318.md`
- `references/s2-sketch-mode-core-detail-area-policy.md`
- `references/choice-prompt-policy.md`
- `references/response-prompt-options-policy.md`
- `references/s2-s5-image-only-terminal-orchestration-policy-v3215.md`
- `references/s5-s2-reference-image-input-policy-v3215f.md`
- `references/candidate-artifact-id-coherence-policy-v3215.md`
- `references/substage-user-guidance-policy-v316.md`
- `references/continue-next-action-policy-v316.md`
- `references/chatgpt-web-checkpoint-bundle-policy.md`
- `references/figure-caption-codesign-policy-v311.md`
- `references/figure-caption-symbiosis-policy-v314a.md`
- `references/candidate-issue-ledger-and-caption-burden-policy-v324.md`
- `references/core-submodule-detail-policy-v313.md`
- `references/semantic-lineage-dual-use-policy-v315.md`
- `references/connector-provenance-and-area-budget-policy-v315-hotfix.md`
- `references/s2-model-contract-and-audit-policy-v315-hotfix.md`
- `references/security-and-portability-policy.md`
- `references/step-rewind-cleanup-contract.md`

- `references/preference-led-second-round-coverage-policy-v3215b.md`

- `references/checkpoint-response-and-repair-gate-policy-v3215b.md`
- `references/stage-redo-on-unrepairable-checkpoint-policy-v3215b.md`
- `references/preferred-first-round-carryover-policy-v3215b.md`
- `references/cumulative-checkpoint-response-gate-policy-v3215b.md`
- `references/paper-neutral-hardcoding-lint-policy-v3215b.md`
- `references/response-checkpoint-zip-gate-policy-v3215b.md`
- `references/source-faithful-image-prompt-audit-policy-v3215b.md`
- `references/skill-packaging-context-on-demand-policy-v3215b.md`
