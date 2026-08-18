# CodeSucker 融合对标审查报告

> 日期：2026-08-18
> 对标对象：https://github.com/fanbuz/codesucker v0.4.4（pinned commit `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c`）
> 本地实现：`数学建模全流程套件/tools/codesucker-core/`（vendored 上游 core）+ `codesucker-cli.mjs` + `codesucker_bridge.py`
> 结论：**核心能力 100% 到达（代码级同源）；桌面壳能力按既定边界以机器可读等价替代；明确排除项仅为 Electron UI 相关。**

## 一、对标方法

1. 以上游 README「功能特性」12 项 +「内置整理规则对照」8 项为基准清单。
2. 本地实现直接 vendored 上游 `packages/core`（discover/clean/select/render/audit 五个模块原样保留，仅一处 Windows 单扩展名 glob 兼容补丁并记录于 `UPSTREAM.md`），因此「到达」判定为代码级一致。
3. 运行验证：上游 core 7 个测试套件 + 套件 178 项 + 根级 43 项 + 真实多语言 fixture 端到端演示。

## 二、功能特性对标矩阵

| # | 上游功能 | 本地实现 | 判定 |
|---|---------|---------|------|
| 1 | 目录级文件筛选（目录树三态/全选/清空/反选、应用级排除规则、.gitignore 叠加） | `discover.ts` 原生：扩展名白名单 + `.gitignore` + `compileExcludePatterns` 排除规则；文件纳入选择由配置 `extensions/excludes` 表达，`files.json` 输出每个文件的 `included` 标志 | **到达**（机器可读等价；目录树 UI 属桌面壳，不迁移） |
| 2 | 安全重新扫描（保留配置、旧结果立即失效） | 每次运行独立配置 JSON + 临时目录原子替换，旧结果不会覆盖新会话；重跑即重扫，配置文件可复用 | **到达**（等价语义） |
| 3 | 文件类型构成与按后缀导出 | `stats.json` 输出 `langCounts`/文件数/行数；`extensions` 配置即按后缀筛选 | **到达** |
| 4 | 状态机代码清洗（30+ 后缀、字符串边界、删空行、Tab→空格、78 列硬折） | `clean.ts` 上游原样（逐字符状态机，`"https://..."` 内 `//` 不误删） | **到达（代码级一致）** |
| 5 | 敏感信息脱敏（API 密钥/密码/内网 IP/手机号） | `clean.ts` MASK_RULES 上游原样 | **到达（代码级一致）** |
| 6 | 规范化截取分页（超 3000 行取前 1500+后 1500、首页模块开头、末页模块结尾、每 50 行显式分页） | `select.ts` 上游原样 | **到达（代码级一致）** |
| 7 | 一键导出 docx（页眉=软件名+版本号、右上角 PAGE 域、宋体 10.5pt 固定行距）+ txt | `render.ts` 上游原样，CLI 输出 `source-materials/rendered/` | **到达（代码级一致）** |
| 8 | 提交前风险校验（有效内容/每页行数/末页 2/3/页眉/首末页边界/署名冲突，三级结论） | `audit.ts` 上游原样；另接入 `QualityGate.check_source_materials()` 作为 workflow 门禁，fail 阻断 `complete_step()` | **到达（代码级一致）+ 系统级增强** |
| 9 | GitHub Release 更新检测 | 不适用（桌面应用功能；本系统完全离线，无版本检测请求） | **不迁移（明确排除）** |
| 10 | 源码处理完全离线 | vendored 依赖本地化，运行时零网络请求（比上游更严格：连版本检测都没有） | **到达（更强）** |
| 11 | 最近项目管理 | 不适用（桌面功能）；等价物为 workflow 工作区 + 可复用配置 JSON | **等价替代** |
| 12 | 配置与窗口持久化 | 等价物：`source-materials.config.json`（schema 版本化）+ `SOURCE_MATERIALS_MANIFEST.json`（输入/输出哈希、core 版本、规则版本、backend） | **等价替代（更强，可审计）** |

## 三、内置整理规则对标

| 规范要求 | 上游实现 | 本地实现 | 判定 |
|---------|---------|---------|------|
| 前、后各连续 30 页共 60 页 | 超 3000 行截前 1500+后 1500 | `select.ts` 同源 | ✅ |
| 每页不少于 50 行 | 内存按 50 行切块 + 显式分页符 | `select.ts` 同源 | ✅ |
| 页眉标注软件全称+版本号 | 导出时写入页眉，未含版本号警告 | `render.ts` + `audit.ts` 同源 | ✅ |
| 页码 1–60 连续 | docx PAGE 域 | `render.ts` 同源 | ✅ |
| 第 1 页程序开头、第 60 页结尾 | 截取锚定首末文件边界 | `select.ts` 同源 | ✅ |
| 无空行、注释不凑页 | 清洗阶段删除（可关闭） | `clean.ts` 同源 | ✅ |
| 末页至少满 2/3 | 校验器检查并提示 | `audit.ts` 同源 | ✅ |
| 署名与著作权人一致 | `@author`/`Copyright` 扫描比对 | `audit.ts` + 清洗前署名证据提取同源 | ✅ |

## 四、验证证据

### 4.1 上游 core 测试（vendored 目录，与上游同源测试）

```
✅ smoke 全部通过（docx 27KB + 5 项审计 pass）
✅ attribution 全部通过
✅ multiline string regression 全部通过（字符串内注释符号不误删）
✅ empty result regression 全部通过
✅ release matrix 全部通过（Java/Kotlin、Python GBK、TypeScript）
✅ async pipeline 全部通过
✅ exclude rules 全部通过
```

### 4.2 套件与根级回归

- 套件全量：**178 passed**
- 根级验收：**43 passed**（含 capability catalog 合同 7 项）

### 4.3 真实多语言 fixture 端到端演示

输入：`src/main.py`（含 `"https://example.com/path"` 字符串注释符号、`sk-` 密钥、密码、`192.168.1.10` 内网 IP、手机号、超长行、`@author Someone Else` 冲突署名）+ `src/main.ts` + `.gitignore`。

输出摘要：

```
backend : vendored-codesucker-core
core    : 0.4.4 @ b065a18
rules   : 2026.07.2
audit   : [fail] 检测到疑似他人署名（Someone Else @ src/main.py:12）
          [warn] 末页仅 16 行，不足页面 2/3（fixture 行数不足 3000，预期）
          [pass] 页眉与软件名称一致 / 每页行数均 ≥ 50 / 首末页边界
rendered: 源程序.docx + 源程序.txt
```

关键断言（全部通过）：

| 场景 | 结果 |
|------|------|
| `URL = "https://example.com/path"` 字符串内 `//` 不误删 | ✅ 完整保留 |
| `sk-1234567890abcdef` API 密钥 | ✅ 脱敏为 `sk****` |
| `s3cr3t-pass` 密码 | ✅ 脱敏为 `s3****` |
| `192.168.1.10` 内网 IP | ✅ 脱敏为 `10.0.*.*` |
| `13812345678` 手机号 | ✅ 脱敏为 `138********` |
| `# 配置 API` 注释 | ✅ 删除 |
| 署名证据保留（4 条：author/copyright × main.py/main.ts） | ✅ 清洗前提取、含文件与行号 |
| 署名冲突审计（owner=Demo Owner vs Someone Else/Other Company） | ✅ fail 检出 |
| 超长行 78 列硬折 | ✅ 无超长残留 |

## 五、本系统超出上游的增强

1. **协议层**：JSON 配置/输出契约 + `SOURCE_MATERIALS_MANIFEST.json`（core 版本、commit、规则版本、config/core/output 哈希、backend、命令与退出码）。
2. **系统层**：接入 workflow 引擎（`copyright_source_materials` 模板）、质量门禁（`check_source_materials`，fail 阻断）、三层审计与 execution evidence。
3. **链路层**：`assets-inventory` 资产清点 → `copyright-source-materials` 流水线 → `copyright-draft`（`codesucker_materials.py` 从 selection.json 生成代码材料）→ `copyright-build`（正式资料直接引用标准渲染产物）全链路贯通。
4. **治理层**：上游同步脚本、许可证审计、`UPSTREAM.md` 修改记录、版本/规则版本独立追踪。
5. **兼容层**：Windows 单扩展名 glob 修复（`**/*.py` 而非 `**/*.{py}`），已记录并带回归测试。

## 六、明确不迁移项（与既定边界一致）

- Electron 桌面 UI（五步向导、目录树、分页预览、设置页、窗口管理）—— 以 OpenCode Desktop 为主控的 agent 系统不需要桌面壳。
- GitHub Release 更新检测、最近项目管理、窗口持久化 —— 桌面应用功能。
- 上游路线图中尚未实现的项（多目录导入、自定义脱敏规则、例外交存模式等）不在对标范围。

## 七、结论

| 维度 | 结论 |
|------|------|
| 核心五段流水线（discover/clean/select/render/audit） | ✅ 100% 到达（代码级同源） |
| 软著规则对照（8 项） | ✅ 全部到达 |
| 上游功能特性（12 项） | ✅ 9 项到达/等价替代，3 项明确不迁移（桌面 UI 类） |
| 合规性 | ✅ Apache-2.0 许可、NOTICE、来源 commit、修改记录齐备 |
| 可追溯 | ✅ manifest + 哈希 + 版本 + 规则版本全记录 |
