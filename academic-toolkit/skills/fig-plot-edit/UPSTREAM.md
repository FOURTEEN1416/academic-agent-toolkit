# UPSTREAM 溯源台账 — fig-plot-edit

- Upstream: https://github.com/hang-jin/editaplot
- Pinned commit: d93cd31（main @ 2026-11-16 实测 HEAD，d93cd319c789d078da55acd75d120209b9288c83；原 pin 0172103 @ 2026-09-07）
- License: Apache-2.0（见本目录 LICENSE；NOTICE 一并保留）
- Local use: `skills/fig-plot-edit/`（2026-09-22 B 方案整技能收编：复制上游
  `skill/editaplot/` 全包，删除上游平台专属 `agents/openai.yaml`，SKILL.md 深度改写为本仓适配层）
- Local adaptation: SKILL.md 重写为中文适配层——①上游执行器沙箱审批流程整体替换为本仓
  三段式边界（渲染=Ask first；管理员/注册表/DCOM 红线保留为 Never）；②runtime 引擎不随包，
  启动器指向 `vendor/forks/editaplot/editaplot.cmd`（vendor/ 快照不入库，gitignored）；
  ③新增 complete_step/evidence 申报协议与本机无 Origin 如实降级条款。
  references/ 已同步中性化（2026-10 清洗批），其余为上游原样副本。
- Verification: 本机 Origin 未安装，smoke/render/verify 全链未在本机验证（登记待用；
  上游模板验证基线 Origin 2024b）。安装 Origin 后首跑 `editaplot.cmd doctor` + `origin-smoke`。
- 上游更新方法见本技能 SKILL.md §八。
- 同步记录（2026-11-16，0172103→d93cd31，4 commits）: 上游更新为 research figures 升级 +
  secure Python runtime（editaplot.cmd 新增 managed-runtime 指针，Python 探测收窄 3.11–3.12）+
  heatmap 行标签修复 + 双语 README。vendor/forks/editaplot 已整体同步至实测 HEAD（保留本机
  runtime/.editaplot-venv 环境文件）。技能侧 references/scripts 适配层重放**待专项执行**：
  本仓 SKILL.md 为深度改写适配层，上游 12 个 skill 文件变更（+301/−102）须逐件人工合并，
  盲目覆盖会破坏中性化适配（fig-plot-edit 当前登记待用，不同步技能侧不影响既有功能）。
