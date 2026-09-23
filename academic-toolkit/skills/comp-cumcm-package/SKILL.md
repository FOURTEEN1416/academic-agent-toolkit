---
name: comp-cumcm-package
description: ">- 竞赛提交阶段打包沙演与合规终审入口（默认 CUMCM 口径；华为杯/研究生数模走 --compliance-profile comp_huawei，口径数据驱动自 comp_rules.json）。"
---

# 竞赛提交打包沙演（comp-cumcm-package）

**定位**：提交阶段（T-4h ~ 上传）的**防呆闸**。只做提交前可机检的硬项，
**不代替官方客户端上传**，**不生成 .rar**（WinRAR 手工压 RAR 是国赛口径，本技能给 --zip 沙演）。
名称保留 cumcm 前缀（catalog/地图已登记）；**能力覆盖两族**：国赛默认口径 +
华为杯 `--compliance-profile comp_huawei` 分支（与 S14 `comp-final-audit`
的 compliance_profile 做法同构）。

## 口径分支（compliance_profile，机器真源：`engine/modex-core/comp_rules.json`）

| 判据 | comp_cumcm（国赛，默认） | comp_huawei（华为杯） |
|---|---|---|
| 承诺书页 | ⛔ 电子版**禁含**承诺书/编号专用页（`pledge_page: forbidden_in_electronic`，系统另收） | ✅ 前 3 页**必须含**参赛承诺书（`pledge_page: required`，gmcmthesis 首页即承诺书） |
| 电子版首页 | 摘要专用页（机检硬项） | 封面/承诺书页——**禁止**套用国赛"首页必须摘要"硬检查 |
| 正文页限 | ≤30 页（人工项） | ≤50 页、目标 40-60（人工项，`max_body_pages: 50`） |
| 图表总量 | 常规 | 30-46 张（`figure_total_range`，人工项） |
| 封面模板 | cumcmthesis | 官方第 21 届 Word/PDF 模板指针：`skills/comp-paper-zh/_templates/huawei/official_docx/`（gitignored，按指针取用勿复制入库）+ LaTeX `gmcmthesis` |
| 正式包格式 | WinRAR 压 .rar（云南赛区） | 以当届研究生竞赛章程为准，勿默认套用国赛 RAR 口径 |

⛔ 两族承诺书方向**相反**——华为杯链走到 S14 后打包必须显式带 `--compliance-profile comp_huawei`；
不带旗标按国赛口径跑会把正确的含承诺书 PDF 判为硬失败。

## 何时用

- `comp-final-audit`（S14，同带 compliance_profile）通过、准备组包上传时——两族链同用本技能。
- 需要确认"支撑材料里有没有夹带身份信息（含 PDF 文档属性）"。
- 需要复核"论文与支撑材料各自 ≤20MB"（该上限为 CUMCM 官方口径；华为杯当届限额未入库真源，
  本脚本按 20MB 防呆底线执行，正式限额以当届规程为准）、拿到两份文件的 MD5。

## 执行

```bash
# 国赛（默认口径，行为与 G2 之前完全一致）
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws>

# 华为杯：承诺书必含 + 首页摘要硬检查停用
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> \
  --compliance-profile comp_huawei

# 沙演打包（另生成 .zip 验证语料清单；正式包格式见上表口径分支）
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> --zip

# 机读输出（report.compliance_profile 记录口径）
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> --json
```

退出码：`0` = 硬项（体积 / 首页判据含承诺书方向 / 身份）全部通过；`1` = 有硬项失败，先修再提交。

## 脚本机检什么

| 检查 | 依据 | 失败即硬失败 |
|---|---|---|
| 论文电子版存在且为 PDF | 清单 第五部分 | ✓ |
| 论文 ≤20MB、不压缩 | 清单 第五部分（CUMCM 上限，两族同按防呆底线） | ✓ |
| 承诺书方向：国赛前 3 页禁含承诺书/编号页；华为杯前 3 页必含承诺书 | comp_rules.json `compliance.pledge_page` | ✓ |
| 首页必须是摘要专用页（**仅国赛口径**；华为杯首页为承诺书/封面页，此项停用） | 清单 第五部分 | ✓ |
| PDF 文档属性无身份线索 | 清单 第五部分（⚠️ 含元数据） | ✓ |
| 支撑材料语料齐备（源程序 + result*.xlsx + figures/*.json + AI工具使用详情.pdf） | 清单 第五部分 | — |
| 支撑材料合计 ≤20MB | 清单 第五部分 | ✓ |
| 路径（文件名/目录名）无身份线索 | 清单 第五部分（⚠️ 文件夹名、文件名） | ✓ |
| 论文与沙演包 MD5 | 清单 第六部分 | — |

> 页数/首页/承诺书/元数据检查依赖 `PyMuPDF`；未安装时自动跳过并打 `[note]`，体积与身份检查仍执行（标准库）。

## 人工项（脚本查不了，必看 `references/submission_checklist.md` 对应口径分节）

- **国赛**：论文内容与纸质版一致、**不含**承诺书与编号专用页、第三页起页码连续、正文无目录 ≤30 页。
- **华为杯**：前 3 页**含**参赛承诺书（与国赛相反，勿凭国赛肌肉记忆删页）、正文 ≤50 页（目标 40-60）、
  图表 30-46 张、封面标识按当届官方模板替换（模板指针见上表）。
- 两族共通：附录含**支撑材料文件列表 + 全部完整可运行源程序**（没用到程序则注明"本论文没有用到程序"）；
  支撑材料**内容与论文相符**（⚠️ 不符可能取消评奖资格）；源程序除附录外**同时放入支撑材料**。
- 时间节点：**国赛** 9/13 20:00 撰写 → 9/13 20:30 MD5 上传（报名第一位学生）→ 9/14 14:00 双文件上传；
  **华为杯**以当届组委会/赛区通知为准，禁止套用国赛日期。

## 硬约束

1. ⛔ **不生成 .rar**——本机无 `rar.exe` 时不可行；`--zip` 只是沙演，正式包**国赛**用 WinRAR 压 RAR
   （云南赛区要求），**华为杯**以当届章程为准。
2. ⛔ **不写死任何一族口径**——承诺书方向/页限一律 `--compliance-profile` 数据驱动自
   `engine/modex-core/comp_rules.json`；新增竞赛族只改真源不改本脚本判定分支语义。
3. ⛔ **不改工作区**——除非显式 `--zip`（只往 `_submit/` 写沙演包）。
4. ⛔ **重编译后必须重清元数据**再打包（hyperref 每次编译会重写 title/subject/creator）。
5. ⛔ **不与运行中的工作流抢文件**——对 `workspaces/<ws>` 只读巡检，打包输出写到独立目录。

## STEP_MANIFEST 产出声明

| 产出 | 类型 | 说明 |
|---|---|---|
| 巡检报告（stdout / `--json`） | 门禁信号 | 体积/承诺书方向/首页判据/身份硬检查 + MD5 + 语料清单 + compliance_profile 回执 |
| `_submit/支撑材料_沙演.zip` | 沙演产物（可选） | 仅验证语料与体积，非正式提交件 |
