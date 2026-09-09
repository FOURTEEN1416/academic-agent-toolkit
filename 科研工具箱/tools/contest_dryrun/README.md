# contest_dryrun — 赛前全链自检（链路验证级）

两道赛前体检工具（2026-09-09 独立审计全链驱动入库通用化）。**产物是链路验证级样例，
只用于验证引擎/门禁/审计链/编译链在当台机器上走得通，绝不冒充真实参赛交付。**

| 脚本 | 作用 | 覆盖 |
|------|------|------|
| `chain_driver.py` | 14 步 CUMCM 工作流端到端驱动：状态机推进、4 次 checkpoint 硬闸（blocked→approve）、每步 STEP_MANIFEST、执行证据申报、真实 xelatex 编译、真实 pulp 求解 | 引擎/门禁/审计/模板编译 |
| `final_review_probe.py` | 用**当前配置的模型**真实调用终审（API 响应 id 留痕） | strict 模型比对所需的真实证据 |

## 比赛时用法（ZCode 主控）

```bash
# 1) 全链推进（前 11 步 + 编辑步自动完成；review/视觉步会停下等子智能体产物）
python tools/contest_dryrun/chain_driver.py --ws <工作区目录>
# 2) review / visual / final 三步由主控派子智能体产出（模型=contest_models.json 所配）
python tools/contest_dryrun/final_review_probe.py --ws <同一工作区>
# 3) 续跑
python tools/contest_dryrun/chain_driver.py --ws <同一工作区> --wf <打印的 WF_ID>
```

前置：`.env` 或环境里有其一终审端点（ACAT_FINAL_*/SENSENOVA_*/EDITOR_AI_*）；
`engine/modex-core/contest_models.json` 已填写比赛模型（否则 strict 比对降级 warn，见其 `_comment`）。
