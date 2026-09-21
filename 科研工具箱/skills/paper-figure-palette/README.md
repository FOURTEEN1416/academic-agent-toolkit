# paper-figure-palette — 入库溯源（README）

| 项 | 内容 |
|---|---|
| 入库日期 | 2026-09-13 |
| 版本 | v6（与 CUMCM 2026A 论文定稿色板同源） |
| 来源 | 从 WorkBuddy 用户级技能 `<home>/.workbuddy/skills/paper-figure-palette/` 原样复制入库 |
| 出处工程 | `<workbuddy_space>/cumcm2026A`（论文 21 张插图的实测配色体系） |
| 设计源头 | 用户指定 8 色「夏日海滩」（参考图/科研配色提取与调色结果.json 第 2 组），经 LCH 去灰提彩（v5→v6） |
| 设计器 | 工程内 `_tools/design_palette_v6.py`；体检方法论前身 `palette_kit_v6/`（已入库为技能 `palette-health-check`） |
| 完整文档 | `<workbuddy_space>/cumcm2026A/docs/配色方案与使用指南_v6.md`（九章版） |
| 验证状态 | `palette_kit.py check` 五组判据全 PASS；CUMCM 2026A 全 21 图印刷实测；灰度/色盲（CVD）复核通过 |

## 与 palette-health-check 的关系

- `palette-health-check`（本库既有）：配色**体检与修复**方法论（去灰指标、deepen 替代 darken、
  色带单调性、CVD 复核）——回答"配色发灰/发浊怎么诊断怎么改"。
- `paper-figure-palette`（本技能）：一套**已定稿可直接用**的配色体系 + 使用规则 + 移植配方
  （matplotlib / TikZ / Word / PPT / Excel）——回答"新图用什么色、怎么搭、怎么不出错"。
- 两者互补：出新图先用本技能取色排版；对既有配色不满时用 palette-health-check 诊断。

## 文件清单

```
paper-figure-palette/
├── SKILL.md                  # 色板速查 + 五条铁律 + 工作流 + 诊断口诀
├── README.md                 # 本文件（入库溯源）
├── references/
│   ├── color-system.md       # 设计原理（两族结构/互补对/LCH/墨色/灰度色盲）
│   └── recipes.md            # 移植配方（matplotlib/TikZ/Word/PPT/Excel/图型映射/自检清单）
├── scripts/
│   └── palette_kit.py        # check 体检 / preview 色卡 / hex 色值；独立实现色彩数学
└── assets/
    ├── palette_v6.json       # 色板真源（LCH 量测 + 墨色映射 + 色带端点）
    └── palette_preview.png   # 色卡总览目检图
```

## 快速验证

```bash
python "科研工具箱/skills/paper-figure-palette/scripts/palette_kit.py" check     # 五组判据
python "科研工具箱/skills/paper-figure-palette/scripts/palette_kit.py" preview   # 出色卡
```
