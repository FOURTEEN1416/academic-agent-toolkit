# SOURCE — figure-craft 收编溯源与差异声明

- **收编日期**：2026-10-16
- **收编来源**：本地包 `D:\Desktop\figure-craft`（非外部上游仓库；该包由本仓绘图资产于 2026-09-23 抽取而成，
  属**自有资产回流**，故不适用 `vendor/forks` + `UPSTREAM.md` 的外部 fork 流程，改以本文件声明）。
- **收编方式**：**增量收编（delta）**——只收编本包**独有**的部分；与工具箱共享的文件**不复制第二份**，
  统一引用唯一真源 `academic-toolkit/skills/_utils/`（避免双副本漂移，也避免触发查重台账棘轮）。

## 一、逐文件裁定（2026-10-16 实测）

### 收编（独有件）

| 文件 | 字节 | 说明 |
|---|---:|---|
| `_utils/figstyle.py` | 13,289 | **本包唯一真实新增能力**：质感三件套 API（gradient_bar/area、fade_area_x、glow_*、gradient_box、save_fig） |
| `_utils/gates_override.example.json` | 890 | 验收豁免示例（配合 `skills/_utils/figure_check.sh` 的 gates_override 机制） |
| `assets/palette_registry.json` | 11,375 | 色板注册表（9 色板 + 5 场景 + 5 禁用 + 10 规则） |
| `assets/palette_v6.json` | 3,820 | 夏日海滩 v6 主色板 |
| `references/acceptance-gates.md` | 3,049 | 验收管线操作细节 |
| `references/chart-type-map.md` | 3,650 | 图型改造映射表 |
| `references/pitfalls.md` | 2,922 | 实测坑清单 |
| `references/plotting-playbook.md` | 4,313 | figstyle 函数签名与默认值 |
| `references/scenarios.md` | 7,027 | 场景化选色 |
| `references/skill-router.md` | 3,563 | 工具箱绘图技能委派表 |
| `references/source-summary-图表改造.md` | 7,879 | 图型改造素材综述 |

### 不收编（与工具箱重复，改引真源）

| 本包文件 | 裁定理由 | 唯一真源 |
|---|---|---|
| `_utils/fig_include_size.py` | **字节全同** | `academic-toolkit/skills/_utils/fig_include_size.py` |
| `_utils/fig_size_consistency_check.py` | **字节全同** | `skills/_utils/fig_size_consistency_check.py` |
| `_utils/figure_check.py` | **字节全同** | `skills/_utils/figure_check.py` |
| `_utils/figure_text_budget.py` | **字节全同** | `skills/_utils/figure_text_budget.py` |
| `_utils/paper_source_scope.py` | **字节全同** | `skills/_utils/paper_source_scope.py` |
| `assets/figure_recipes_basic.md` | **字节全同** | `skills/_utils/figure_recipes_basic.md` |
| `assets/figure_recipes_advanced.md` | **字节全同** | `skills/_utils/figure_recipes_advanced.md` |
| `assets/figure_recipes_competition.md` | **字节全同** | `skills/_utils/figure_recipes_competition.md` |
| `assets/figure_recipes_empirical.md` | **字节全同** | `skills/_utils/figure_recipes_empirical.md` |
| `references/color-system.md` | **字节全同** | `skills/paper-figure-palette/references/color-system.md` |
| `_utils/figure_check.sh` | 近似（本包 41,245 / 真源 40,963）——真源为后继版本 | `skills/_utils/figure_check.sh` |
| `_utils/figure_pdf_quality_check.py` | 近似（真源已含 SKIP 语义等修订） | `skills/_utils/figure_pdf_quality_check.py` |
| `_utils/plot_utils.py` | 近似（本包 283,115 / 真源 283,945）——真源为后继版本 | `skills/_utils/plot_utils.py` |
| `_utils/get_recipe.py` / `_utils/recipe_audit.py` | 近似（真源为后继版本） | `skills/_utils/` 同名件 |
| `assets/figure_exemplars.md` | 近似（真源为后继版本） | `skills/_utils/figure_exemplars.md` |
| `assets/figure_recipes_academic.md` | 近似（真源为后继版本） | `skills/_utils/figure_recipes_academic.md` |
| `assets/figure_style_guide.md` | 近似（真源为后继版本） | `skills/_utils/figure_style_guide.md` |
| `examples/`（含 demo 脚本与 PNG/PDF 产物） | 示例产物，非技能必需件；PNG 163KB/PDF 33KB 二进制不入库 | — |

**真源更新方向的判定依据**：工具箱 `skills/_utils/` 同名件 mtime 为 2026-10-01 及之后（晚于本包 2026-09-23），
且内容为超集（如 `plot_utils` +830B、`figure_pdf_quality_check` 含 SKIP 语义修订）。

## 二、本地化适应性改写内容

1. **路径重绑**：SKILL.md 中全部共享脚本调用改为工具箱相对路径 `skills/_utils/...`（原先的包内 `_utils/` 路径
   在本仓形态下会指向不存在的副本）。
2. **配色方法论改引真源**：`references/color-system.md` 不随包分发，改引
   `skills/paper-figure-palette/references/color-system.md`。
3. **导入路径示例**：`import figstyle` 前补 `sys.path.insert` 指向本技能 `_utils/`，使示例照抄可跑。
4. **描述口径**：frontmatter description 改写为**路由索引**口径（≤120 字符，见工具箱常驻上下文预算纪律），
   原包长描述中的实现细节移入正文。
5. **未改动**：`figstyle.py` / 两个色板 JSON / 七篇 references **逐字节照搬**，未做内容编辑。

## 三、升级规则

- 若日后工具箱 `skills/_utils/` 与本地包再次分叉，**以工具箱为唯一真源**，本技能只保留 §一「收编」表内独有件。
- 若 `figure-craft` 上游（本地包）更新，先比对 `figstyle.py` 与色板是否有新版本，再决定是否重收编，并更新本文件。
