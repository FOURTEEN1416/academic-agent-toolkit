# CodeSucker 融合设计

## 目标

将 `fanbuz/codesucker` 的适配能力融合进数学建模全流程套件，形成离线、可复现、可审计的软著源码材料生产子系统，并让资产清点、软著草稿、正式资料构建和工作流引擎共享同一套源码事实底稿。

本设计只复用适合当前系统的能力：源码发现、排除、排序、编码识别、状态机清洗、敏感信息脱敏、署名证据、前后段截取、显式分页、DOCX/TXT 渲染、风险审计和版本追踪。不搬运 Electron 桌面壳、重复调度器或重复配置中心。

## 架构

```text
用户项目
  -> assets-inventory
  -> codesucker_bridge.py
  -> codesucker-cli.mjs
  -> vendored CodeSucker core
       discover -> clean -> select -> render -> audit
  -> 标准化 source-materials manifest
  -> copyright-draft
  -> copyright-build
  -> engine quality gates / execution evidence / final audit
```

### Vendored core

在 `数学建模全流程套件/tools/codesucker-core/` 保存经过适配的上游 core 源码和来源文件。默认锁定上游 `v0.4.4` 对应 commit `b065a1825f4e32dca4c4b7fd8bccf3e020a77c5c`。目录不包含 Electron 代码。

必须保留：

- 上游 `LICENSE`；
- 上游 `NOTICE`；
- `UPSTREAM.md`，记录仓库、tag、commit、同步时间、修改文件和适配原因；
- `THIRD_PARTY_NOTICES.txt`，记录随本套件分发的 Node 依赖许可证。

### 稳定适配层

`tools/codesucker-cli.mjs` 接受一个 JSON 配置文件，执行完整流水线并把结构化结果写入工作区；不得让技能直接导入 core 内部模块。

`tools/codesucker_bridge.py` 是 Python 侧唯一稳定入口，负责：

- 检查 Node 版本和 vendored core 文件；
- 生成规范化配置；
- 调用 CLI；
- 校验 stdout/stderr、退出码和 JSON 结构；
- 生成输入/输出 SHA-256；
- 将路径规范化为工作区相对路径；
- 标记 `backend: vendored-codesucker-core`；
- 仅在显式 `--allow-legacy-fallback` 时调用旧 Python 实现，并把 backend 标记为 `legacy-python-fallback`。

## 标准输入

`source-materials.config.json`：

```json
{
  "schemaVersion": 1,
  "root": "D:/project",
  "title": "软件全称 V1.0",
  "owner": "著作权人",
  "foundedDate": "2026-01-01",
  "extensions": ["py", "ts", "tsx"],
  "excludes": ["node_modules", ".git", "*.lock"],
  "sortMode": "entry",
  "manualOrder": [],
  "clean": {
    "removeComments": true,
    "removeBlankLines": true,
    "maskSensitive": true,
    "wrapLongLines": true,
    "maxLineWidth": 78,
    "tabWidth": 4
  },
  "linesPerPage": 50,
  "maxPages": 60,
  "outputDir": "source-materials"
}
```

配置必须显式记录 `rulesVersion`、`coreVersion`、`coreCommit` 和 `configSchemaVersion`，不能依赖运行时推断。

## 标准输出

每次执行都产生以下结构化产物：

- `source-materials/files.json`：发现文件、编码、大小、原始行数、mtime、语言、入口评分、是否纳入；
- `source-materials/cleaned.json`：清洗统计、清洗后行数、脱敏计数和署名证据；
- `source-materials/selection.json`：页列表、前后段分界、首末文件、选中相对路径；
- `source-materials/audit.json`：每项 pass/warn/fail、定位文件、行号、证据文本；
- `source-materials/stats.json`：文件、语言、行数、页数和错误统计；
- `source-materials/rendered/`：DOCX/TXT；
- `source-materials/SOURCE_MATERIALS_MANIFEST.json`：输入路径、配置哈希、core 哈希、输出哈希、规则版本、backend 和命令；
- `source-materials/SOURCE_MATERIALS_REPORT.md`：给 agent 和用户阅读的摘要报告。

所有 JSON 使用 UTF-8、稳定排序、固定字段名。绝不把源码内容写入网络请求；报告可以包含源码路径和审计证据，但不包含未脱敏的敏感值。

## 与现有技能融合

### assets-inventory

保留 `ASSETS_INVENTORY.md` 的用户资产盘点职责；当识别到代码资产或项目目录时，调用 bridge 生成源码资产摘要，并在清单中引用 `SOURCE_MATERIALS_MANIFEST.json`。不在资产清点阶段直接生成最终 DOCX。

### copyright-draft

真实材料模式下，先调用源码流水线，再基于 `files.json` 和 `selection.json` 生成 `代码文件选择.json` 与代码材料 Markdown。代码 Markdown 必须来自流水线已选中的真实清洗结果，禁止再次自行拼接或编造。无真实材料时仍保留合成示例源码路径，但必须在 manifest 中标注 `sourceMode: synthetic`。

### copyright-build

优先消费 `source-materials/rendered/` 中的 DOCX/TXT；只有没有标准源码产物时才使用旧 Markdown 构建路径。正式资料报告必须引用源码流水线报告和审计结果，且保留 warning/fail，不得把 warning 改写为 pass。

### 新技能 copyright-source-materials

新增技能负责 standalone 源码材料生产：读取项目目录、配置和用户选择，调用 bridge，检查门禁，生成标准输出并向 workflow runner 回报证据。

## 门禁

新增 `check_source_materials()`，至少验证：

1. manifest 有效且 `backend` 为标准 backend；
2. 输入、配置、core 和输出 SHA-256 与 manifest 一致；
3. `files.json`、`selection.json`、`audit.json`、`stats.json` 均为有效 JSON；
4. 有效源码内容不为零；
5. 非末页至少 50 行；
6. 页数不超过配置上限；
7. audit 不含 fail；
8. 署名冲突和敏感信息证据已保留；
9. rendered DOCX/TXT 至少一个存在且非空；
10. 产物 manifest 可被 `ArtifactManifest` 校验。

warning 允许交付但必须进入报告和 execution evidence；fail 阻断 `complete_step()`。

## 版本与升级

- 产品版本、配置 schema、规则版本、core 版本独立记录；
- vendored core 升级必须更新 `UPSTREAM.md`、许可证清单和适配测试；
- 每次升级运行 core smoke、字符串/注释回归、署名、排除规则、空结果、异步取消和真实项目测试；
- 旧 Python 后端仅用于迁移诊断，不能默认兜底静默运行。

## 错误处理

- Node 不存在、core 缺失、协议 JSON 无效、退出码非零：步骤失败；
- 单文件读取/清洗失败：记录 `errors.json`，若导致审计 fail 则阻断，否则作为 warning 交付；
- 用户取消：保留部分日志但不写完成证据；
- 输出已存在：使用临时目录和原子替换，旧结果不能覆盖新 session；
- 路径越界、符号链接逃逸、非法排除规则：拒绝执行。

## 验证

验证分三层：

1. 单元测试：bridge、协议、哈希、路径安全、门禁；
2. 回归测试：上游 core 的字符串、注释、署名、分页、编码、空结果、排除规则和异步行为；
3. 集成测试：真实项目目录 -> workflow runner -> complete_step -> execution evidence -> copyright-build -> final audit。

验收标准是：标准 backend 可独立运行，结果可重复，所有声明产物可被 manifest 校验，任何未申报或未脱敏的关键操作不能被报告为成功。
