---
name: editaplot
description: "在装有 Origin/OriginPro 2021+ 的 Windows 实体机上，把实验表格（CSV/TXT/XLS/XLSX）画成可编辑 OPJU + PNG/PDF/TIF 出版级科研图。材料光谱（XPS/XRD/GSAS/XAS/FTIR/NMR/DSC/PL/UV-Vis/EIS/CV/LSV）、通用统计、医学与深度学习（ROC/PR/DCA/SHAP）专用模板；逐列确认数据用途、方案哈希冻结、Origin 对象反读校验。本机无 Origin 时如实降级，不伪造通过。"
---

# EditaPlot · 艾迪图（Origin 可编辑科研绘图）

> **收编出处**：上游 [hang-jin/editaplot](https://github.com/hang-jin/editaplot)（Apache-2.0），
> 快照日期 2026-09-22。本目录 LICENSE/NOTICE/references/ 为上游同步副本，未改动其合同语义。
> **runtime 引擎不在本技能内**：引擎与启动器在 `vendor/forks/editaplot/`（仓库根相对路径，
> `editaplot.cmd` 在该目录根）。上游原文 SKILL.md 保留在
> `vendor/forks/editaplot/skill/editaplot/SKILL.md`，与本文件冲突时**以本文件为准**（本仓适配层）。
> **硬前提**：仅物理 Windows 10/11 x64 + CPython 3.10–3.12 + 本地 Origin/OriginPro 2021+
>（验证基线 2024b）。**本机未装 Origin 时本技能不可用——如实报告缺口，不伪造通过**
>（TOOL_GAP 纪律）。Origin 的安装永远是用户手动完成的系统级变更，本技能不代装。

## 一、本仓适配（与上游 Codex 版的差异，优先级最高）

上游 SKILL.md 与 references/runtime.md、references/origin-safety.md 中的 **Codex 沙箱流程**
（`origin_codex_sandbox_context`、formal local-execution request、auto-reviewer handoff）
在本仓**不适用，整体替换**为本仓三段式边界：

| 上游概念 | 本仓替代 |
|---|---|
| Codex 沙箱审批 handoff | 读数据/分析/规划＝Always 自走；**启动 Origin COM（origin-smoke/render）＝跨工具操作，Ask first**：首次渲染前向用户要方向；同一会话内用户已确认目标后，setup→doctor→smoke→render→verify 连续执行不重复询问 |
| formal request / auto-reviewer | 用户主权：用户说画就画；渲染产生的文件写入是可逆操作，无需逐文件审批 |
| （上游红线） | **保留为 Never 硬停**：不请求管理员权限；不改 DCOM/注册表/防火墙/用户组/Origin 安装；不用鼠标自动化；不重置/覆盖/关闭用户自有 Origin 工程（`attach_existing` 仅显式高级模式，退出用 detach 不强杀）；不把选中文件上传任何网络服务 |

其余适配规则：

1. **启动器路径**：一律 `vendor/forks/editaplot/editaplot.cmd`（相对仓库根；脚本内用绝对路径时按当前检出解析）。不要求用户选 Python 解释器，不直接调 `scripts/editaplot.py`。
2. **产物去向**：默认沿用上游规则——源数据同目录自动建 `<源文件名>_EditaPlot_YYYYMMDD_HHMMSS/`；不重定向到仓库、技能目录或全局共享目录。若任务走工作流引擎（StepAction 指定 workspace），将产物**复制登记**到该 workspace 并在 evidence 中注明两处路径。
3. **complete_step 协议**：被引擎工作流调用时，完成步骤必须回报 `complete_step` 并附 execution_evidence：`skill_sha256`＝本文件 SHA-256；`commands`＝实际执行的 editaplot.cmd 命令与返回码；`outputs`＝OPJU/PNG/PDF/TIF 与校验产物路径。引擎只编排不代执行，无证据＝未执行。
4. **宿主中立**：references 副本中残留的 Codex 字样一律按本节规则替换理解，不再逐文件修改（避免与上游 diff 失真）。
5. **语言**：与用户交流用中文；命令、字段名、错误码保留原文。

## 二、环境启动（每次新工作流）

```powershell
# 首次使用（一次）：装 Python 依赖到项目级 .editaplot-venv（绝不装/改 Origin）
vendor\forks\editaplot\editaplot.cmd setup
# 每个新工作流（只读体检，不启动 Origin）：
vendor\forks\editaplot\editaplot.cmd doctor
# 缺依赖时仅允许项目级修复，范围不扩大：
vendor\forks\editaplot\editaplot.cmd doctor --repair
```

- `doctor` 只做只读发现（`Origin.Application`/`Origin.ApplicationSI`、Python、originpro、OriginExt），
  **绝不启动 Origin**；`ready_for_render` 只代表技术就绪，不代表实时连接成功。
- 缺 Origin / 缺 Python / 缺依赖时：报告缺口与安装前置，**停止**，等待用户自行解决后重跑。
  平台不支持（macOS/Linux/WSL/VM）直接拒绝并说明。

## 三、核心流程（8 步）

1. **读取与推荐**：`editaplot.cmd start <数据文件> [--intent "<用户意图>"]`。inspect/recommend 载荷是内部工作态；对新手只说：识别出了什么、最佳 1–3 种图及理由、还差哪个最小科学决策。附件只有临时副本时，先问一次真实源/输出目录，不猜。
2. **逐列理解**：选定候选模板后 `editaplot.cmd understand <数据文件> --template-id <id>`。把结果整理成清单：数据类型；要画的列；仅辅助/校验的列；保留不画的列；将出现的图形元素；**不会自动做的计算**。每个源列恰好出现一次；任何 `uncertain` 项＝追问，不得替用户确认或规划。
3. **科学确认（哈希冻结）**：请用户确认一句话科学目的＋元素清单后，`plan` 冻结 `proposal_hash`、已批准派生项与歧义选择到 `--semantic-confirmation-json`。**源文件、列映射、目的或 proposal_hash 任一变化，确认即失效重做**。
4. **配色**：颜色可自选时 `editaplot.cmd palettes`，展示 `assets/palettes/palette-selector-public.zh-CN.png`，推荐 ≤2 个兼容 `palette_id`；冻结前读 `references/palettes.md`。
5. **精确样式（可选）**：XPS 等路线支持 `--visual-style-json` 冻结用户精确值，合法字段仅：`series_colors`、`line_width_pt`、`fill_transparency_percent`、`page_size_cm`、`legend_visible`、`legend_position`、`legend_frame`。非法值**快速失败请用户修正**，不静默回退默认。
6. **Origin 预检烟测（强制）**：`editaplot.cmd origin-smoke --output-dir <独立空目录>`（`launch_isolated`：启动并独占专用 Origin 实例＋版本握手＋模板能力判定）。**计划之后、正式渲染之前必须通过**。激活失败按上游有界重试策略（清理成功才允许一次全新隔离实例重试）；`origin_com_class_not_registered`/`origin_com_activation_access_denied` 直接停止不重试；不因 Python worker 运行久就强杀（它可能持有隐藏 Origin 实例）。
7. **渲染**：烟测通过后 `editaplot.cmd render <plan>`。产物默认落在源文件旁的时间戳目录；渲染计划副本 `render-plan.json` 随产物归档。
8. **校验**：`editaplot.cmd verify <输出目录>`＋**人工视觉 QA**。正式成功＝可编辑 OPJU＋PNG＋PDF＋TIF＋对象反读＋人工 QA **六件齐**；缺任一（含只有 Python 预览图）只能称预览，不得宣称完成。

渲染前必读：`references/origin-safety.md`、`references/figure-contract.md`、`references/verification.md`；新表/新图型决策加读 `references/data-contracts.md`、`references/chart-selection.md`、`references/semantic-understanding.md`；带参考图时加读 `references/reference-figures.md`。

## 四、科学决策纪律（保留用户主权，继承上游红线）

- **源数据文件不可变**：不覆盖、不补列、不编造测量值；辅助列只存在于内存或可编辑 Origin 工程中。
- 每列先分类（主证据/可见辅助/仅计算/保留不画/不确定）再规划；未知数值列是一个**问题**，不是一条自动新曲线。
- **科学分析与显示变换分离**：绝不静默归一化、平滑、拟合、剔异常点、算误差棒、认物相、指认峰。SHAP 只接受上游预计算的逐样本贡献表，绝不训练模型或调用 SHAP。
- GSAS/GSAS-II：区分 Observed/Calculated/可选 Background/上游自带 Difference/显式 Phase 刻线与控制列；上游 Publication 的 `Diff` 按源值画，**不做第二次偏移**。
- XPS：外观偏好与科学合同分离；结合能轴高→低方向、组分身份、残差处置、已验证的单区域填充实现**不可**被样式请求或参考图改写。
- 医学数据/参考图检查前，要求用户确认已脱敏并去除烧录文字；`panel-plan` 是布局门禁，不是 PHI 检测器。
- 3D 必须有真实科学含义的第三轴，拒绝装饰性 3D；新 3D 路线保持 experimental 直到全套门禁通过。
- 模板路线状态（verified/experimental/unsupported）与主机兼容状态分开陈述，不把 `compatible_unverified` 说成 verified。
- 图表必须能辩护一个明确结论；技术上画得出来但会误导的图，**拒绝**。

## 五、出版图形合同

白底、Arial、克制配色（拒绝彩虹色与装饰性 3D）；物理尺寸由图型/数据密度/系列数/标签长度推导；单位换算正确，小字号期刊值不直接塞进 Origin API；同条件跨面板颜色一致，palette ID 与 HEX 冻结进 plan；用户显式样式 > 参考图风格建议，但都要过能力门禁并归类 applied/retained/rejected；优先可编辑 Origin 对象与标签——Python 预览或内嵌位图不是 Origin 交付物。成果只能称 **"publication-informed"**，不得称 "Nature compliant" 或期刊认可。

## 六、报告格式（中文人话）

报出：识别的数据形状与各列角色；选定图型与备选；置信度与已确认变换；输出目录（源文件旁）；OPJU/PNG/PDF/TIF 路径；校验/反读结果；剩余需人工检查项。对新手把内部标识符翻译成自然语言，技术路径放在结论之后。向 complete_step 申报时用精确路径与命令。

## 七、按需加载 references（上游同步副本）

| 文件 | 内容 |
|---|---|
| `references/runtime.md` | 启动器、setup、Python 发现、CLI 命令、产物清单 |
| `references/chart-selection.md` | 图族、排序规则、支持级别 |
| `references/data-contracts.md` | 接受的数据布局、列语义、修复指引 |
| `references/semantic-understanding.md` | 逐列用途、元素清单、派生数据血缘、哈希确认门禁 |
| `references/reference-figures.md` | 参考图安全语法、绑定、改编上限、独立确认 |
| `references/figure-contract.md` | 证据逻辑、视觉层级、字体、颜色规则 |
| `references/origin-safety.md` | 本地 Automation 与已验证 API 护栏 |
| `references/verification.md` | 必备产物、反读、人工 QA |
| `references/showcase.md` | 中性演示数据与图库政策 |
| `references/palettes.md` | 中文配色选择器、兼容性、无障碍上限 |

## 八、上游维护

- 上游更新：`cd vendor/forks/editaplot && git pull --ff-only`，然后 diff 本目录 references/ 与
  `vendor/forks/editaplot/skill/editaplot/references/`，重新同步副本并复读本 SKILL.md 校对适配层。
- 本技能 tracked 入库依据：Apache-2.0 + NOTICE 随目录保留（同 academic-figure-skill 收编先例）；
  vendor/ 快照本身不入库。
- 本机现状（2026-09-22）：Origin 未安装，COM 未注册——本技能处于**登记待用**状态，首次实际出图前
  需用户安装 Origin 2021+。
