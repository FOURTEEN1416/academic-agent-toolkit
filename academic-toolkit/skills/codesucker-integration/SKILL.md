---
name: codesucker-integration
description: "CodeSucker 软著源程序文档抽取器 — 集成技能——基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) (Apache-2.0) 的 Python 移植版。"
---

# CodeSucker 软著源程序文档抽取器 — 集成技能

> 基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) (Apache-2.0) 的 Python 移植版。
> 将代码项目自动整理成符合中国版权局要求的 60 页源程序鉴别材料文档。

## 输入契约

| 参数 | 必需 | 默认值 | 说明 |
|------|------|--------|------|
| `root` | ✅ | — | 项目根目录路径 |
| `title` | ✅ | — | 软件全称 + 版本号（如 "MyApp V1.0"） |
| `owner` | ❌ | `''` | 葫作权人（用于署名校验） |
| `output` | ❌ | `.` | 输出目录 |
| `extensions` | ❌ | 30+ 种 | 文件扩展名过滤 |
| `max_pages` | ❌ | 60 | 最大页数 |
| `lines_per_page` | ❌ | 50 | 每页行数 |

## 执行步骤

### 步骤 1：调用工具生成文档

```bash
python tools/codesucker_python.py <项目目录> \
  --title "<软件全称+版本号>" \
  --owner "<著作权人>" \
  --output <输出目录> \
  --max-pages 60 \
  --json
```

### 步骤 2：检查审计结果

工具自动执行 7 项合规检查：
1. ✅ 每页行数 ≥ 50
2. ✅ 末页 ≥ 2/3 满
3. ✅ 总页数 ≤ 60
4. ✅ 无残留空行
5. ✅ 首页为程序开头
6. ✅ 末页为程序结尾
7. ✅ 署名与著作权人一致

### 步骤 3：输出文件

- `<title>_source_code.docx` — 主文档（宋体 10.5pt，固定行距，页眉含软件名）
- 审计报告打印到终端

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
| codesucker_python.py | tools/codesucker_python.py | 核心流水线（Python 移植版） |

## 关联能力

- `copyright_draft_build` — 软著申请资料生成（本技能的上游）
- `copyright_draft` — 软著草稿撰写
- `anti_ai_detection` — 反 AI 检测（可配合使用）

## 授权

本集成基于 [fanbuz/codesucker](https://github.com/fanbuz/codesucker) 的核心算法，
遵循 Apache-2.0 许可证。Python 移植保留原始算法逻辑，适配纯 Python 环境。
