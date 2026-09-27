---
name: copyright-source-materials
description: "从真实本地项目离线抽取、清洗、分页、审计并导出软著源程序材料。"
allowed-tools: Bash, Read, Edit, Glob, Grep
---

# 软著源程序材料

## 输入契约

- `StepAction.workspace`：所有产物唯一写入位置。
- 本地项目根目录、软件全称和版本号、著作权人；成立日期、文件排序和清洗选项可选。
- 真实源码模式不得生成或混入虚构代码。

## 执行

1. 先确认 `third_party/codesucker-core/UPSTREAM.md`、LICENSE、NOTICE 和 Node/tsx 依赖存在。
2. 在 workspace 写入 `source-materials.config.json`。标题必须含版本号，项目根目录不得指向 workspace 外的未授权路径。
3. 调用：

```powershell
python tools/codesucker_bridge.py --config <workspace>/source-materials.config.json --workspace <workspace>
```

4. 读取 `source-materials/audit.json`。任何 `fail` 必须修复配置、文件选择或真实源码问题后重跑；不得将 fail 解释为通过。
5. 使用执行会话运行真实CodeSucker命令，声明当前步骤合同规定的产物；`finish` 自动调用source_materials检查并保留工具原始manifest。
6. 程序记录core commit、规则版本、配置/核心/输出摘要和真实返回码，模型不复制这些字段到另一份回执。报告路径为 `source-materials/SOURCE_MATERIALS_REPORT.md`，不另造根目录同名报告。

## 输出契约

- `source-materials/files.json`
- `source-materials/cleaned.json`
- `source-materials/selection.json`
- `source-materials/audit.json`
- `source-materials/stats.json`
- `source-materials/rendered/*.docx` 和 `*.txt`
- `source-materials/SOURCE_MATERIALS_MANIFEST.json`
- `source-materials/SOURCE_MATERIALS_REPORT.md`

## 质量铁律

- 标准 backend 必须是 `vendored-codesucker-core`，旧 Python 工具不得默认回退。
- 源码处理不发出网络请求。
- 字符串中的 `//`、`#` 等不能被当作注释误删；敏感值必须脱敏；署名冲突必须保留定位证据。
- 所有路径、输入和输出必须可追溯到 workspace manifest。
