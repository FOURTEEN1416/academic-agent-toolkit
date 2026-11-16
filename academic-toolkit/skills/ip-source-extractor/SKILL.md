---
name: ip-source-extractor
description: "CodeSucker 软著源程序文档抽取器 — 集成技能——基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) (Apache-2.0) vendored core 的稳定桥接入口。"
---

# CodeSucker 软著源程序文档抽取器 — 集成技能

> 基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) (Apache-2.0) 的 vendored core（`academic-toolkit/third_party/codesucker-core`）。
> 将代码项目自动整理成符合中国版权局要求的 60 页源程序鉴别材料文档。
> 执行入口为 `tools/codesucker_bridge.py`（vendored core 稳定桥接，带 manifest + sha256 审计链）。
> 旧 Python 移植版 `tools/codesucker_python.py` 已废弃，不得作为执行入口。

## 输入契约

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `workspace` | ✅ | — | 所有产物唯一写入位置（工作区目录） |
| `root` | ✅ | — | 项目根目录路径（不得指向 workspace 外的未授权路径） |
| `title` | ✅ | — | 软件全称 + 版本号（如 "MyApp V1.0"，必须含版本号） |
| `owner` | ❌ | `''` | 著作权人（用于署名校验） |
| `extensions` | ❌ | 30+ 种 | 文件扩展名过滤 |
| `maxPages` | ❌ | 60 | 最大页数 |
| `linesPerPage` | ❌ | 50 | 每页行数 |

## 执行步骤

### 步骤 1：写入配置并调用 vendored core 桥接

先在 workspace 写入 `source-materials.config.json`（字段：`root`、`title`、`owner`、`extensions`、`excludes`、`linesPerPage`、`maxPages`），然后调用：

```bash
python tools/codesucker_bridge.py \
  --config <workspace>/source-materials.config.json \
  --workspace <workspace>
```

前置检查：确认 `third_party/codesucker-core/UPSTREAM.md`、LICENSE、NOTICE 与 Node/tsx 依赖存在。真实源码模式（`sourceMode: real`）不得生成或混入虚构代码。

### 步骤 2：检查审计结果

桥接运行后读取 `source-materials/audit.json`。工具自动执行 7 项合规检查：
1. ✅ 每页行数 ≥ 50
2. ✅ 末页 ≥ 2/3 满
3. ✅ 总页数 ≤ 60
4. ✅ 无残留空行
5. ✅ 首页为程序开头
6. ✅ 末页为程序结尾
7. ✅ 署名与著作权人一致

任何 `fail` 项必须修复配置、文件选择或真实源码问题后重跑；不得将 fail 解释为通过。

### 步骤 3：输出文件（产物契约与 copyright-source-materials 一致）

- `source-materials/files.json` — 文件发现清单
- `source-materials/cleaned.json` — 清洗后代码
- `source-materials/selection.json` — 截取选择记录
- `source-materials/audit.json` — 7 项合规审计结果
- `source-materials/stats.json` — 统计信息
- `source-materials/rendered/*.docx`、`*.txt` — 主文档（宋体 10.5pt，固定行距，页眉含软件名）
- `source-materials/SOURCE_MATERIALS_MANIFEST.json` — 审计链清单（core commit、规则版本、配置/核心/输出 sha256、真实返回码）
- `source-materials/SOURCE_MATERIALS_REPORT.md` — 报告（不另造根目录同名报告）

## 质量铁律

1. **输出必须包含 docx 文件** — 不接受纯 TXT 作为最终交付
2. **审计必须 0 fail** — 有 fail 项时必须修复后重新生成
3. **每页必须恰好 50 行** — 除末页外不允许少于 50 行
4. **截取策略：前 1500 + 后 1500 行** — 超过 3000 行时自动截取

## 五段流水线

```
discover → clean → select → render → audit
  发现      清洗     截取     渲染     审计
```

1. **Discover**: 递归扫描目录，按扩展名过滤，跳过二进制/大文件
2. **Clean**: 逐字符状态机剥离注释（30+ 语言），脱敏 API 密钥/密码/IP/手机号
3. **Select**: ≤3000 行全部输出；>3000 行取前 1500 + 后 1500 行
4. **Render**: 生成 DOCX（宋体 10.5pt，固定行距，页眉，PAGE 页码域）
5. **Audit**: 7 项合规检查，三级结论（pass/warn/fail）

## 关联工具

| 工具 | 路径 | 用途 |
|------|------|------|
| codesucker_bridge.py | tools/codesucker_bridge.py | 核心流水线稳定入口（vendored core 桥接，产出 SOURCE_MATERIALS_MANIFEST.json 审计链） |

## 关联能力

- `copyright_draft_build` — 软著申请资料生成（本技能的上游）
- `copyright_draft` — 软著草稿撰写
- `anti_ai_detection` — 反 AI 检测（可配合使用）

## 授权

本集成基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) 的核心算法，
遵循 Apache-2.0 许可证。核心以 vendored 形式收编于 `academic-toolkit/third_party/codesucker-core`，
经 `tools/codesucker_bridge.py` 桥接调用；溯源信息见该目录 UPSTREAM.md/LICENSE/NOTICE。
