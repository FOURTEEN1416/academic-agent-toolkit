# 技能/长文档写法范式（治理结构评估维度）

> 范式归纳自 [figures4papers](https://github.com/ChenLiu-1996/figures4papers)
> `scientific-figure-making/SKILL.md`（pinned commit `3c181f8`，License CC BY-NC-4.0；
> 溯源登记于 `skills/paper-figure/references/UPSTREAM.md`）。2026-09-10 适应性改写为
> 本仓文档治理的结构评估维度——非上游原文，口径对齐本仓六件套与治理铁律。

## 四条范式

上游样本：主文件仅 38 行、纯路由，529 行知识全部下沉 5 份单主题 references
（每份 30~152 行），开头一句显式指令"references 按需打开，禁止预载全部"，
并用 "When to load / When not to load" 成对声明适用边界。

1. **超薄主入口**：主文件只承载"是什么 / 何时用 / 怎么路由 / 硬约束"，
   不承载知识细节。经验参照：主文件 ≤60 行；硬红线 100 行，超线先想
   **下沉**（切块进 references/），不先想删内容。
2. **渐进披露**：主文件开头显式声明"按需打开 references，禁止预载"；
   每份下沉文件在主文件有一行路由（Open when——什么时机才打开它）。
3. **双向适用边界**：When to load / When not to load 成对声明（正反两路，
   宿主可快速判否）。只有"何时用"没有"何时不用"的技能/文档，治理时标记补齐。
4. **单主题切分**：一份 reference 管一个主题（30~150 行量级为宜）；
   两份文件主题重叠即合并候选，一份文件塞多主题即切分候选。

## 治理用法

- 对技能 / 长文档做**结构评估**时按四条逐项对照；不符合项归 **P3（结构整改）**，
  不阻塞内容正确性处置（P0/P1 优先——先清污染，再调结构）。
- **整改模板**：①主文件"知识段"按主题切块下沉 `references/`；②主文件留
  路由表（每份一行 Open when）；③主文件补双向边界声明；④复验主文件行数。
- 本技能自身即按此范式改造的样例（2026-09-10：范式本体下沉本文件，主文件
  仅加一段 5 行路由；改造前主文件 61 行零 references，改造后 68 行 +
  本文件 37 行）——治理时可直接引为对照样本。

## Related

- `../SKILL.md` — 本技能入口（用户铁律 / 真源锚点 / 生命周期三态）
- `skills/paper-figure/references/UPSTREAM.md` — 上游溯源登记（pinned/License）
