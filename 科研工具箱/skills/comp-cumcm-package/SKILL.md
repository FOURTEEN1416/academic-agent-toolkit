---
name: comp-cumcm-package
description: ">- CUMCM 提交阶段打包沙演与合规终审入口。"
---

# CUMCM 提交打包沙演（comp-cumcm-package）

**定位**：提交阶段（T-4h ~ 上传）的**防呆闸**。只做提交前可机检的硬项，
**不代替官方客户端上传**，**不生成 .rar**（WinRAR 手工压 RAR，本技能给 --zip 沙演）。

## 何时用

- `comp-final-audit` 通过、准备组包上传时。
- 需要确认"支撑材料里有没有夹带身份信息（含 PDF 文档属性）"。
- 需要复核"论文与支撑材料各自 ≤20MB"、拿到两份文件的 MD5。

## 执行

```bash
# 只检查（只读，不改工作区）——推荐先跑
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws>

# 沙演打包（另生成 .zip 验证语料清单，正式提交仍用 WinRAR 压 .rar）
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> --zip

# 机读输出
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> --json
```

退出码：`0` = 三项硬检查（体积 / 首页摘要 / 身份）通过；`1` = 有硬项失败，先修再提交。

## 脚本机检什么

| 检查 | 依据 | 失败即硬失败 |
|---|---|---|
| 论文电子版存在且为 PDF | 清单 第五部分 | ✓ |
| 论文 ≤20MB、不压缩 | 清单 第五部分 | ✓ |
| 首页必须是摘要专用页（检出"摘要"） | 清单 第五部分 | ✓ |
| PDF 文档属性无身份线索 | 清单 第五部分（⚠️ 含元数据） | ✓ |
| 支撑材料语料齐备（源程序 + result*.xlsx + figures/*.json + AI工具使用详情.pdf） | 清单 第五部分 | — |
| 支撑材料合计 ≤20MB | 清单 第五部分 | ✓ |
| 路径（文件名/目录名）无身份线索 | 清单 第五部分（⚠️ 文件夹名、文件名） | ✓ |
| 论文与沙演包 MD5 | 清单 第六部分 | — |

> 页数/首页/元数据检查依赖 `PyMuPDF`；未安装时自动跳过并打 `[note]`，体积与身份检查仍执行（标准库）。

## 人工项（脚本查不了，必看 `references/submission_checklist.md`）

- 论文**内容与纸质版一致**、不含承诺书与编号专用页、第三页起页码连续、正文无目录 ≤30 页。
- 附录含**支撑材料文件列表 + 全部完整可运行源程序**（没用到程序则注明"本论文没有用到程序"）。
- 支撑材料**内容与论文相符**（⚠️ 不符可能取消评奖资格）；源程序除附录外**同时放入支撑材料**。
- 承诺书、编号专用页**未**放进支撑材料。
- 时间节点：9/13 20:00 撰写 → 9/13 20:30 MD5 上传（报名第一位学生）→ 9/14 14:00 双文件上传。

## 硬约束

1. ⛔ **不生成 .rar**——本机无 `rar.exe` 时不可行；`--zip` 只是沙演，正式包必须 WinRAR 压 RAR（云南赛区要求）。
2. ⛔ **不改工作区**——除非显式 `--zip`（只往 `_submit/` 写沙演包）。
3. ⛔ **重编译后必须重清元数据**再打包（hyperref 每次编译会重写 title/subject/creator）。
4. ⛔ **不与运行中的工作流抢文件**——对 `workspaces/<ws>` 只读巡检，打包输出写到独立目录。

## STEP_MANIFEST 产出声明

| 产出 | 类型 | 说明 |
|---|---|---|
| 巡检报告（stdout / `--json`） | 门禁信号 | 体积/首页/身份三项硬检查 + MD5 + 语料清单 |
| `_submit/支撑材料_沙演.zip` | 沙演产物（可选） | 仅验证语料与体积，非正式提交件 |
