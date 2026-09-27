---
name: comp-cumcm-package
description: "竞赛提交打包沙演与合规终审入口；口径必须显式选择（国赛 comp_cumcm / 华为杯 comp_huawei），不按文本猜赛事。触发词：竞赛打包、合规终审、提交沙演。"
---

# 竞赛提交打包沙演（comp-cumcm-package）

**定位**：提交阶段（T-4h ~ 上传）的**防呆闸**。只做提交前可机检的硬项，
**不代替官方客户端上传**，**不生成 .rar**（WinRAR 手工压 RAR 是国赛口径，本技能给 --zip 沙演）。
名称保留 cumcm 前缀（catalog/地图已登记）；**能力覆盖两族**：国赛默认口径 +
华为杯 `--compliance-profile comp_huawei` 分支（与 S14 `comp-final-audit`
的 compliance_profile 做法同构）。

## 口径分支（compliance_profile，机器真源：`engine/modex-core/comp_rules.json`）

**口径选择属任务裁决**：按当次任务的赛事身份（`contest_profile.contest_id` 或用户显式指定）选择
comp_cumcm / comp_huawei；未指明时先向用户确认，**不静默套用任何默认**
（`pack_submission.py` 的 `--compliance-profile` 旧默认 comp_cumcm 已移除，现为**必填**——
两族口径必须显式声明）。

| 判据 | comp_cumcm（国赛，默认） | comp_huawei（华为杯） |
|---|---|---|
| 承诺书页 | ⛔ 电子版**禁含**承诺书/编号专用页（`pledge_page: forbidden_in_electronic`，系统另收） | ⛔ 官方模板**全无承诺书页**（`pledge_page: absent_in_official_template`，2026-09-25 按官方开赛公告勘误：承诺书为校级材料，签字盖章扫描件交培养单位，不入论文） |
| 电子版首页 | 摘要专用页（机检硬项） | 封皮页（不可删除、4 logo 不能替换）——**禁止**套用国赛"首页必须摘要"硬检查；除首页外不得出现单位/姓名/队号 |
| 正文页限 | profiles 约束经引擎 bound 快照注入（`gate_page_cap`/`gate_page_scope`；cumcm 电子版 `official_verified` 30） | 当届 operative 页限 **unknown**（`hw-page-limit` 无 verified 值）——80 仅是 huawei2026d_zcode 本轮投稿的 migration_evidence 任务口径（不继承新任务），50 为历轮配置基线已不作数；页限未知按"待核实"上报，不编默认 |
| 图表总量 | 常规 | 档案 `compliance.figure_total_range` [30,46]——来源为经验汇编（figure_exemplars.md），**非已证官方规则**：按建议区间对待，不作为硬门禁（待 E 取证当届规程后升级） |
| 封面模板 | cumcmthesis | 官方第 21 届 Word/PDF 模板指针：`skills/comp-paper-zh/_templates/huawei/official_docx/`（gitignored，按指针取用勿复制入库）+ LaTeX `gmcmthesis` |
| 正式包格式 | WinRAR 压 .rar（云南赛区） | 以当届研究生竞赛章程为准，勿默认套用国赛 RAR 口径 |

⛔ 华为杯链走到 S14 后打包必须显式带 `--compliance-profile comp_huawei`——不带旗标按国赛口径跑，
会把正确的**封皮首页** PDF 判为首页判据硬失败（两族承诺书方向现为同向禁含：国赛系统另收、
华为杯官方模板本就无此页；首页判据方向仍相反）。

## 何时用

- `comp-final-audit`（S14，同带 compliance_profile）通过、准备组包上传时——两族链同用本技能。
- 需要确认"支撑材料里有没有夹带身份信息（含 PDF 文档属性）"。
- 需要复核"论文与支撑材料各自 ≤20MB"（该上限为 CUMCM 官方口径；华为杯当届限额未入库真源，
  本脚本按 20MB 防呆底线执行，正式限额以当届规程为准）、拿到两份文件的 MD5。

## 执行

```bash
# 国赛：显式带 comp_cumcm 口径（--compliance-profile 已必填，无默认）
python skills/comp-cumcm-package/scripts/pack_submission.py --workspace workspaces/<ws> \
  --compliance-profile comp_cumcm

# 华为杯：官方模板无承诺书页 + 首页摘要硬检查停用（首页为封皮）
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
| 承诺书方向：国赛前 3 页禁含承诺书/编号页；华为杯官方模板全无承诺书页（前 3 页同样不得出现） | comp_rules.json `compliance.pledge_page` | ✓ |
| 首页必须是摘要专用页（**仅国赛口径**；华为杯首页为封皮页，此项停用） | 清单 第五部分 | ✓ |
| PDF 文档属性无身份线索 | 清单 第五部分（⚠️ 含元数据） | ✓ |
| 支撑材料语料齐备（源程序 + result*.xlsx + figures/*.json + AI工具使用详情.pdf） | 清单 第五部分 | — |
| 支撑材料合计 ≤20MB | 清单 第五部分 | ✓ |
| 路径（文件名/目录名）无身份线索 | 清单 第五部分（⚠️ 文件夹名、文件名） | ✓ |
| 论文与沙演包 MD5 | 清单 第六部分 | — |

> 页数/首页/承诺书/元数据检查依赖 `PyMuPDF`；未安装时自动跳过并打 `[note]`，体积与身份检查仍执行（标准库）。

## 人工项（脚本查不了，必看 `references/submission_checklist.md` 对应口径分节）

- **国赛**：论文内容与纸质版一致、**不含**承诺书与编号专用页、第三页起页码连续、正文无目录、
  正文页数不超过档案 `compliance.max_body_pages`。
- **华为杯**：全文**不含**承诺书页（官方模板无此页；承诺书为校级材料签字盖章扫描件交培养单位，
  勿按旧口径往论文里塞承诺书）、首页为封皮（不可删除、4 logo 不能替换）、除首页外不得出现
  单位/姓名/队号、正文页数不超过档案 `compliance.max_body_pages`（"目标 40-60"为经验区间非硬门禁）、
  图表总量参照档案 `figure_total_range`（经验建议非硬门禁，见上表）、封面标识按当届官方模板替换（模板指针见上表）。
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

## 执行与产出

| 产出 | 类型 | 说明 |
|---|---|---|
| 巡检报告（stdout / `--json`） | 门禁信号 | 体积/承诺书方向/首页判据/身份硬检查 + MD5 + 语料清单 + compliance_profile 回执 |
| `_submit/支撑材料_沙演.zip` | 沙演产物（可选） | 仅验证语料与体积，非正式提交件 |
