---
name: copyright-source-materials
description: "从真实本地项目离线抽取、清洗、分页、审计并导出软著源程序材料。Use when user asks to prepare software copyright source-code materials from an existing project."
allowed-tools: Bash, Read, Edit, Glob, Grep
---

# 软著源程序材料

## 输入契约

- `StepAction.workspace`：所有产物唯一写入位置。
- 本地项目根目录、软件全称和版本号、著作权人；成立日期、文件排序和清洗选项可选。
- 真实源码模式不得生成或混入虚构代码。

## 执行

1. 先确认 `tools/codesucker-core/UPSTREAM.md`、LICENSE、NOTICE 和 Node/tsx 依赖存在。
2. 在 workspace 写入 `source-materials.config.json`。标题必须含版本号，项目根目录不得指向 workspace 外的未授权路径。
3. 调用：

```powershell
python tools/codesucker_bridge.py --config <workspace>/source-materials.config.json --workspace <workspace>
```

4. 读取 `source-materials/audit.json`。任何 `fail` 必须修复配置、文件选择或真实源码问题后重跑；不得将 fail 解释为通过。
5. 调用 `QualityGate(workspace).check_source_materials()`，并检查声明产物 manifest。
6. 在 `complete_step()` 中申报 `source-materials/`、`SOURCE_MATERIALS_REPORT.md`、配置、stdout/stderr 日志及 execution evidence。证据必须记录 core commit、规则版本、配置/核心/输出哈希、实际命令及退出码。

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
