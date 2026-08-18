---
name: copyright-draft
description: >
  一句话/一段描述/一份大纲 → 起草软件著作权申请资料草稿。AI 直接撰写业务理解、
  申请表信息、代码材料（合成可运行的示例源码）、操作手册，并生成模拟页面截图，
  产出成品脚本所需的全部草稿与门禁 JSON。是"一句话生成软著申请资料"工作流的第一步。
user-invocable: false
allowed-tools: >
  Bash, Read, Write, Edit, Glob, Grep, WebSearch, WebFetch
metadata:
  short-description: 起草软著申请资料草稿
  stage: draft
---

# 软著申请资料 · 起草阶段（copyright-draft）

本步骤根据 `CLAUDE.md` 中注入的**软件全称、版本号、软件描述/大纲**，由 AI **直接撰写**软件著作权申请资料的全部草稿，并写出成品脚本校验所需的门禁 JSON。下一步 `copyright-build` 会读取这些草稿生成正式 Word/TXT。

## 场景与硬约束

- **两种输入模式，先判断当前属于哪种：**
  - **A. 用户上传了真实材料**：`CLAUDE.md` 会写明"用户已上传真实材料"，且 `user_data/` 目录下有文件（源代码、项目文件夹展平后的文件、说明文档等）。此时**代码材料必须取自 `user_data/` 里的真实源码**，先通读再据实挑选整理，**不得凭空另编一套示例代码**；业务理解、申请表、操作手册也以真实材料为准。
  - **B. 用户未上传材料**：`user_data/` 为空（或 `CLAUDE.md` 未提"已上传真实材料"）。此时代码材料由 AI 按软件功能**合成可运行的示例源码**（真实、连贯、能体现软件功能的代码，不是伪代码）。老版本"代码材料必须来自真实项目源码、禁止 AI 编造代码"的铁律在模式 B **不适用**。
  - 无论哪种模式，下面的产出文件清单、代码材料格式（`## 第N页` + 围栏代码块）、5 个门禁 JSON 字段要求**完全一致**，成品脚本据此校验，不得改动。
- 固定输出目录：当前工作目录下的 `软件著作权申请资料/`。草稿写入 `软件著作权申请资料/草稿/`，截图相关文件写入 `软件著作权申请资料/截图/`，门禁 JSON `截图方式确认.json` 写在 `软件著作权申请资料/` 根部。
- 起草阶段**由 AI 自主完成全部草稿并写好 5 个门禁 JSON**（都标记为已确认）。平台会在本步骤结束后触发一次人工检查点，由用户在平台上审阅确认；老 skill 里的 7 道命令行门禁（environment/project/business/application-fields/code-selection/screenshot-method/markdown）**不再逐个停下问用户**，改为一次性产出草稿 + 门禁 JSON。
- 不依赖任何外部脚本收集证据。不要调用 `check_environment.py`、`analyze_project.py`、`propose_code_selection.py` 等脚本（它们在本工作流中不存在）。也不要引用 `vendor/docx-toolkit`。正式 Word/TXT 由下一步的成品脚本生成。
- 软件全称、版本号一经确定，必须在 `申请表信息.md`、代码材料页眉、操作手册标题中保持一致。

## 必须产出的文件清单（下一步成品脚本据此校验）

成品脚本 `build_docx_from_md.py` 会检查以下内容，缺一不可：

1. `软件著作权申请资料/草稿/业务理解.md` 和 `业务理解.json`（JSON 含 `"user_confirmed": true`）
2. `软件著作权申请资料/草稿/代码文件选择.json`（含 `"user_confirmed": true`）
3. `软件著作权申请资料/草稿/申请表信息.md`（`➤字段名：值` 全角冒号格式，**不得残留"待用户确认"**）
4. `软件著作权申请资料/草稿/申请表字段确认.json`（含 `"application_fields_confirmed": true`）
5. `软件著作权申请资料/草稿/最终生成确认.json`（含 `"markdown_confirmed": true`）
6. `软件著作权申请资料/截图方式确认.json`（**注意在 `软件著作权申请资料/` 根部**，含 `"screenshot_method_confirmed": true` 和 `"screenshot_method"` 字段）
7. 代码材料：≥60 页时生成 `草稿/代码-前30页.md` + `草稿/代码-后30页.md`；<60 页时生成 `草稿/代码-全部.md`
8. `软件著作权申请资料/草稿/操作手册.md`

`_references/` 目录下有字段规范可参考：`application_fields.md`（申请表字段口径）、`manual_structure.md`（操作手册骨架）、`business_understanding_rules.md`、`code_selection_rules.md`、`mock_ui_design_spec.md`（⛔ mock 界面 UI 设计规范——生成截图前必读，含风格种子 + 组件样式 + 高端审美）。

## 工作流

### 1. 形成业务理解

阅读 `CLAUDE.md` 注入的软件描述/大纲，判断软件的行业、目标用户、核心价值、主要功能和典型操作流程。信息不足时可用 WebSearch 了解相近产品的行业表达（只用于理解行业口径，不编造软件不存在的功能）。

写出 `草稿/业务理解.md`（面向人读的说明）和 `草稿/业务理解.json`。JSON 至少包含：

```json
{
  "user_confirmed": true,
  "product_positioning": "...",
  "industry": "...",
  "target_users": "...",
  "core_value": "...",
  "main_functions": ["...", "..."],
  "operation_flow": ["...", "..."],
  "manual_modules": [
    {
      "title": "页面/流程名称",
      "purpose": "该页面在软件中的用途",
      "usage_scenario": "用户在什么业务场景下使用",
      "entry": "从哪里进入",
      "visible_elements": ["输入框", "按钮", "列表", "..."],
      "operation_steps": ["用户动作1", "用户动作2"],
      "validation_rules": ["必填/长度/权限等，可为空数组"],
      "feedback": "操作后用户看到的结果",
      "screenshot": "截图预留说明"
    }
  ],
  "system_requirements": {"最低配置": "...", "推荐配置": "..."},
  "faq": [{"q": "...", "a": "..."}],
  "glossary": [{"term": "...", "desc": "..."}]
}
```

`manual_modules` 是操作手册的核心输入，按软件真实页面或业务流程组织，每个模块字段填全。`user_confirmed` 直接写 `true`（平台检查点统一确认）。

### 2. 准备源码并生成代码材料

**模式 A（用户上传了真实材料）**：先用 `Glob`（**递归** `user_data/**`）列出并 `Read` 通读 `user_data/` 下的文件——注意用户上传的压缩包（zip/tar.gz 等）已被后端**自动解压成子目录**，源码在子目录里，务必递归查找。识别其中的源代码（`.ts/.tsx/.js/.vue/.py/.java/.go/.c/.cpp` 等）。据实挑选能体现软件核心功能的真实源码，**不要凭空另编**。若真实源码明显不足 60 页，可参照已上传代码的真实风格适度补齐**同一软件**的合理源码，但主体必须是上传的真实代码。上传的文档（需求/设计/说明）用来写业务理解、申请表功能描述、操作手册。

真实材料模式必须先运行 `copyright-source-materials` 标准流水线，读取 `source-materials/files.json`、`cleaned.json`、`selection.json`、`audit.json` 和 `SOURCE_MATERIALS_MANIFEST.json`。`代码文件选择.json` 只能引用该流水线的入选文件；代码材料 Markdown 必须由 `selection.json` 的分页结果生成，并在每页代码块首行保留来源文件说明。任何 audit `fail` 阻断后续草稿；warning 必须原样写入正式资料生成报告。

使用 `python tools/codesucker_materials.py --workspace <workspace> --output <workspace>/软件著作权申请资料/草稿/代码-全部.md --title "<软件全称> <版本号>"` 生成真实源码代码材料；不要手工重新分页。

**模式 B（未上传材料）**：按业务理解合成一套**可运行、连贯、能体现软件功能**的示例源码（前端入口、路由、页面、核心组件、接口封装、状态管理、工具函数为主；前端不足再补后端服务、业务处理）。代码要真实成体系，避免占位注释和空壳函数。

两种模式都先写 `草稿/代码文件选择.json`，记录入选源码清单和理由（模式 A 的 `path` 用真实文件路径，模式 B 用合成路径）：

```json
{
  "user_confirmed": true,
  "files": [
    {"path": "src/main.ts", "selected": true, "model_reason": "应用入口，体现启动与路由装载"},
    {"path": "src/views/Dashboard.vue", "selected": true, "model_reason": "核心页面，展示主要业务功能"}
  ]
}
```

然后把源码按**每页约 50 行**切分，写入代码材料 Markdown。分页规则：

- 源码 ≥60 页：生成 `草稿/代码-前30页.md` 和 `草稿/代码-后30页.md`（各 30 页）。
- 源码 <60 页：只生成 `草稿/代码-全部.md`。为保证达到软著常规页数，建议使代码总量尽量达到 60 页（模式 A 用真实源码，模式 B 合成足量源码）。

代码材料格式必须严格遵守（成品脚本按此解析）：每页一个 `## 第N页` 标题，其后紧跟一个 ```` ``` ```` 围栏代码块：

````markdown
## 第1页

```
// src/main.ts
import { createApp } from 'vue'
import App from './App.vue'
...（约 50 行）
```

## 第2页

```
...
```
````

页码从 1 连续递增。围栏语言标识可留空。

⛔ **少产空行、别切出短页（用户反馈问题③⑤：代码页随机 1-2 行+空白、空行过多）：** 每页尽量切满 ~50 行**有效代码**，不要出现某页只有一两行的短页；源码里**连续的空行最多留 1 个**，不要一次空两三行。（成品脚本 `build_docx_from_md.py` 会再做一道"折叠连续空行 + 按 48 行定长重排"兜底，但你在源头就切匀、少空行，产出最干净。）

### 3. 生成申请表信息

参照 `_references/application_fields.md` 的字段顺序和口径，写 `草稿/申请表信息.md`。每个字段一行，用 `➤字段名：值`（**全角冒号 `：`**）格式。**所有字段必须填实际值，不得残留"待用户确认"**（本工作流由平台检查点统一确认，起草时直接给出合理值）。

关键字段：

- `➤软件全称：<CLAUDE.md 注入的软件全称>`（最终文件名、页眉均以此为准）
- `➤版本号：<CLAUDE.md 注入的版本号，默认 V1.0>`
- `➤软件分类：应用软件`
- `➤开发方式：单独开发`
- `➤软件说明：原创`
- `➤发表状态：未发表`
- `➤编程语言：<按合成源码填，如 TypeScript、JavaScript>`
- `➤源程序量：<合成源码总行数，纯数字>`
- 硬件/系统环境字段（`开发的硬件环境`/`运行的硬件环境`/`开发该软件的操作系统`/`软件开发环境 / 开发工具`/`该软件的运行平台 / 操作系统`/`软件运行支撑环境 / 支持软件`）：各 ≤50 字符，给合理默认值。
- `➤软件的主要功能：<500~1300字>`
- `➤面向领域 / 行业：<≤50字符>`
- `➤开发目的：<≤50字符，一句话，不能只写软件名>`
- `➤页数：<代码材料实际页数>`

字段值的日期用 `YYYY-MM-DD`。

写 `草稿/申请表字段确认.json`：

```json
{"application_fields_confirmed": true}
```

### 4. 生成模拟页面截图（可降级）

⛔⛔ **先读设计规范 + 算风格种子（解决用户反馈「界面都一样、很丑」的根本手段）：** 生成任何 mock HTML 前，**必须先通读 `_references/mock_ui_design_spec.md`**（软著 mock 界面 UI 设计规范），并按其第 1 节算出本项目的**确定性风格种子**：

```bash
# 风格种子 = 工作区目录名哈希 → 每个软著项目界面风格确定性不同、同项目所有页统一、重跑可复现
WFID=$(basename "$PWD")
if command -v cksum >/dev/null 2>&1; then
    UISEED=$(printf '%s' "$WFID" | cksum | cut -d' ' -f1)
else
    UISEED=$(python -c "import sys,zlib;print(zlib.crc32(sys.argv[1].encode()))" "$WFID")
fi
HUE=$(( UISEED % 360 ))
# ⛔ while 反复修正(步长37,不死循环)：单次修正会把低值红区推进黄绿区(11→56)，须循环到彻底脱离
while { [ $HUE -ge 50 ] && [ $HUE -lt 70 ]; } || [ $HUE -ge 350 ] || [ $HUE -lt 12 ]; do HUE=$(( (HUE + 37) % 360 )); done
SCHEME=$(( (UISEED / 7) % 3 )); NAV=$(( (UISEED / 11) % 3 ))
RAD=$(( (UISEED / 13) % 3 )); DENS=$(( (UISEED / 17) % 3 ))
echo "🎨 UI种子 HUE=$HUE° SCHEME=$SCHEME NAV=$NAV RAD=$RAD DENS=$DENS（本项目所有mock页共用）"
```

按 `manual_modules` 里的核心页面，为每个页面生成一份**模拟页面 HTML**（写到 `软件著作权申请资料/截图/mock/页面名.html`）。⛔ **每份 HTML 必须严格按 `mock_ui_design_spec.md` 设计**：配色从 `HUE` 用 HSL 推导（品牌色 ≤15% 只点睛、主体中性灰阶）、骨架按 `SCHEME`/`NAV`、圆角按 `RAD`、间距按 `DENS`、组件按第 4 节样式库（顶栏/侧导航/表格/卡片/表单/按钮/状态标签），并守第 5 节高端审美 + 对齐硬纪律。**本项目所有页共用同一组种子值 → 像同一个软件的不同页面；不同项目种子不同 → 千人千面、不撞脸、不像默认 admin 模板。**

⛔⛔ **页面丰富度硬要求（防"描述简单→页面单调很空"，用户反馈问题①）：** 即使用户描述很短，mock 页面也**不许是空壳**。每个页面**必须**按其在软件里的真实形态填满合理内容：顶部标题栏/logo + 左侧或顶部**导航菜单（≥4 项）** + 主体区按页面类型放**真实感控件与示例数据**——列表/表格页至少 **6~10 行示例数据**（真实字段名+像样的值，不是"数据1/数据2"）、表单页至少 **5~8 个带标签的输入项** + 操作按钮组、仪表盘页放 **3~4 个统计卡片 + 1~2 个图表占位块（带坐标轴/图例样式）**、详情页放字段分组 + 状态标签。描述没给的细节，按软件所属**行业的常见界面**合理补全（不编造软件没有的功能，但要把该类页面"长什么样"补丰满）。**判据：单看这张 mock 截图，像一个真实在用的软件界面，而不是几个孤零零控件的空页。**

⛔⛔ **每个功能模块必须内容不同、一模块一图、禁止复用（用户反馈问题④：不同模块用了同一张图）：** 逐个 `manual_modules` 生成 mock，**每份 HTML 的标题、导航高亮项、主体控件、示例数据都要按该模块的 `purpose`/`visible_elements` 差异化**——工作台≠数据管理页≠设置页，长相必须明显不同。⛔ 绝不允许多个模块指向同一个 HTML/PNG，也不允许换个标题、主体照抄。截图清单里**每个页面对应独立文件名**（`dashboard.png`/`data_manage.png`/`settings.png`…），不得两个模块共用一个文件。生成后自检：任意两张 mock 的主体内容是否雷同？雷同就按模块用途重做。

先探测截图能力：

```bash
python3 _utils/screenshot_capture.py --check
```

- 探测成功（exit 0）：逐个把 HTML 截成 PNG：

  ```bash
  python3 _utils/screenshot_capture.py --file 软件著作权申请资料/截图/mock/dashboard.html --out 软件著作权申请资料/截图/dashboard.png
  ```

  全部截完后写 `软件著作权申请资料/截图/截图清单.json`：

  ```json
  {"screenshots": [{"page": "工作台", "file": "dashboard.png"}]}
  ```

  并写 `软件著作权申请资料/截图方式确认.json`：

  ```json
  {"screenshot_method_confirmed": true, "screenshot_method": "html-mock"}
  ```

- 探测失败（exit 2，Electron 不可用）：**降级为跳过截图**，写：

  ```json
  {"screenshot_method_confirmed": true, "screenshot_method": "skip"}
  ```

  操作手册中保留可见的截图预留文字（见下一步），不阻塞正式资料生成。

无论哪种情况，`截图方式确认.json` 都必须写在 `软件著作权申请资料/` 根部（不是 `草稿/`）。

### 5. 生成操作手册

参照 `_references/manual_structure.md` 的骨架，基于 `业务理解.json` 的 `manual_modules` 写 `草稿/操作手册.md`。一级章节用中文大写序号（如 `一、相关文档`）。相关文档章节用表格。功能特点和页面操作章节用连续段落，不堆项目符号或编号列表。语言面向普通用户，说清页面用途、进入位置、看到什么、操作什么、结果如何，避免代码/框架/接口等技术化表达和 AI 套话。

⛔⛔ **图文平衡硬要求（防"文字少、图大、不平衡"，用户反馈问题②）：** 每个页面章节**先有充分文字、再配图**，做到图文交错、文字撑得住图：
- 每个页面操作章节的正文**≥180 字**（分 2~4 段自然叙述：这个页面是做什么的、从哪进入、界面上有哪些区域和控件、典型怎么一步步操作、操作后会看到什么结果），**不能只有一两句话配一张大图**。
- 一个章节里**图不要连着放**：一张截图前后都要有说明文字，避免"标题→大图→标题→大图"的空洞排布。截图是正文的旁证，不是主体。
- 图片在 Word 里已限宽 12cm（成品脚本控制），你只需保证**文字量足够托住图**，让每页文字和图的比例协调，不出现"半页大图 + 一行字"的失衡。
- 判据：把图片都去掉，单看文字也能读懂这个页面怎么用——文字自身就是完整的说明，图只是辅助。

截图引用：操作手册里的图片路径**相对于 `草稿/` 目录**解析（成品脚本以 `草稿/` 为 base）。截图存在时写 `![工作台](../截图/dashboard.png)`；跳过截图时，在每个核心页面章节保留可见预留文字，例如：

```
【截图预留：请在此处插入"工作台"页面截图。】
```

不要用 HTML 注释作占位（正式 Word 里看不到）。

### 6. 写最终确认门禁并交给平台检查点

全部草稿写完后，写 `草稿/最终生成确认.json`：

```json
{"markdown_confirmed": true}
```

然后向用户简要汇报已生成的草稿清单（业务理解、代码材料页数、申请表信息、操作手册、截图方式），说明将进入正式 Word/TXT 生成。平台会在此触发人工检查点等待用户确认；用户确认后自动进入 `copyright-build` 步骤。

## 完成自检

结束前确认这些文件都已生成且门禁字段就位：

- `草稿/业务理解.json` → `user_confirmed: true`
- `草稿/代码文件选择.json` → `user_confirmed: true`
- `截图方式确认.json`（根部）→ `screenshot_method_confirmed: true` + `screenshot_method`
- `草稿/申请表信息.md` → 无"待用户确认"，含 `➤软件全称：` 和 `➤版本号：`
- `草稿/申请表字段确认.json` → `application_fields_confirmed: true`
- `草稿/最终生成确认.json` → `markdown_confirmed: true`
- `草稿/代码-前30页.md`+`代码-后30页.md` 或 `代码-全部.md`（`## 第N页` + 围栏代码）
- `草稿/操作手册.md`

任一缺失或门禁未置真，下一步成品脚本会打印 `STOP_FOR_USER` 并退出。
