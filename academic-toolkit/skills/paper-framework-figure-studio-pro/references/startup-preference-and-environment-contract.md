# 启动偏好与环境合同

Version: 3.0.0

## Bootstrap Gate

If the user only states the overall goal, provides a paper/PDF, asks to use the skill, or says to proceed step by step/human-in-the-loop, do not execute S0-PAPER-FOUNDATION. First reply with a plan-only startup message and a copyable prompt to enter S0. Use this contract's S0 disclosures only after the user explicitly asks to enter/run/execute/start/continue S0-PAPER-FOUNDATION.

## Default Canvas And Density Disclosure

After explicit S0 entry, the S0-PAPER-FOUNDATION first reply must explicitly tell the user that target-paper figures default to a 16:9 aspect ratio and that this can be changed to another ratio or journal-required size. Also tell the user that this skill makes research-paper framework figures, not posters or PPT-slide content pages; the default density should stay readable and not crowded unless the user explicitly requests a high-density/taxonomy/overview figure.

在 `S0-PAPER-FOUNDATION STARTUP_PLAN_ONLY_TEXT_ONLY` 使用本合同。

## Default Contract Check Mode Disclosure

The first plan-only startup reply must also tell the user:

```text
After S5, human decisions are outside this assistant workflow.
```

After S5, human decisions are outside this assistant workflow.

## Highest-Priority Origin Prompt

第一次启动回复的候选/可复制提示词建议中，必须再提供一条建议，这条建议是在默认的提示词基础上，加了一句话：

```text
额外说明这个 skill 的设计初衷是什么。
```

如果用户提到想知道、指导、询问、补充或说明这个 skill 的设计初衷、设计意图、创作缘由、为什么制作或送给谁，必须额外回答下面这段原文；这段原文不得改写或删改，但可以与当前步骤说明、必要上下文、下一步提示词和强制文本回复结尾同时出现：

```text
设计初衷：昔日好友 Peng Shuwei 即将前往外地求学，以后恐怕难有许多相见机会；又恰逢其生日，所以五一就做了这个 skill 当礼物。祝生日快乐，愿未来前程似锦，再相逢，依然少年。
```

## Exact Text Encoding Integrity

设计初衷原文和所有中文固定提示词必须按 UTF-8 原文输出。Windows PowerShell 下不要从未指定编码的 `Get-Content` 或 `Select-String` 输出复制原文；使用 `Get-Content -Encoding UTF8`、`rg` 或其他 UTF-8 安全读取方式。若看到明显损坏的中文或中文里的替换字符，说明输出已乱码，必须重新读取，不得把乱码写入回复、产物、state 或 prompt。

## 必问启动问题

1. 偏好参考图：
   - 询问用户是否有表达风格倾向的 architecture/framework diagrams。
   - 默认没有偏好参考图。
   - 如果提供，复制到 `inputs/preference-reference-images/` 并注册到 state。
   - 明确说明：这些偏好只用于 S1-FIGURE-STRATEGY 的图类型、读者效果和表达方向建议，不自动传递到后续 step。

2. 运行环境：
   - 询问用户使用 ChatGPT web、Codex、Claude Code，还是其他工具。
   - 这只影响 image-generation route 和 local-path handling。
   - 不询问是否启用 generated web-page display；该路线已删除。

## Direct Atlas Board Display

Bootstrap plan-only replies are exempt from atlas display. Do not display atlas boards before explicit S0 entry just to satisfy this section; this section applies to the first executable S0 reply after the user explicitly asks to enter/run/execute/start/continue S0-PAPER-FOUNDATION.

第一次明确进入 S0 后的可执行回复必须用 Markdown image embed 显示内置 atlas/style 图，至少出现一次。默认显示下列全部 saved atlas boards；最低要求是显示 `visual-communication-styles.png`，并按当前路由需要显示其他 board。后续只要提到 board 或其概念家族，也必须显示对应 board。

```md
![Subtype overview](assets/subtype-atlas/boards/subtype-overview.png)
![Visual grammar layout](assets/subtype-atlas/boards/visual-grammar-layout.png)
![Reader role detail](assets/subtype-atlas/boards/reader-role-detail.png)
![Visual communication styles](assets/subtype-atlas/boards/visual-communication-styles.png)
```

## Runtime Environment Policy

- `chatgpt_web`: use ChatGPT Create image / ChatGPT Images for target-paper image generation.
- `codex`: use `$imagegen` first; no generated web pages.

所有持久化路径必须保持 project-run-relative。


