# 华为杯（研赛）LaTeX 模板

`gmcmthesis.cls` + 骨架 `main.tex` + 封面 `logo.pdf` / `title.pdf`（2026-09-22 自本地
modex-3-skills 模板目录入库，修复 SKILL.md 华为杯分支 `cp _templates/huawei/*` 空操作断链）。

## 字体依赖（未随库分发，41MB 超仓库卫生红线）

cls 用 `\setCJKmainfont` 系列声明 **SimSun / SimHei / KaiTi / LiSu**：

- Windows：SimSun/SimHei/KaiTi 随系统自带；LiSu（隶书，SIMLI.TTF）随中文语言包/Office 提供；
- 非 Windows 或缺字体：从本地 `modex-3-skills/modex-3-skills/comp-paper-zh/templates/huawei/`
  取 `simsun.ttf / SimHei.ttf / KaiTi.ttf / LiSu.ttf` 与本目录文件同放 `paper/`（或装系统字体）。

## 使用

comp-paper-zh Step 1 华为杯分支自动 `cp _templates/huawei/* paper/`；
落地断言要求 paper/ 出现 `.cls` 才放行。骨架占位符（标题/队号/成员）按 SKILL.md
华为杯标题硬约束填写：标题必须照抄赛题官方原标题，禁止 `\\` 强制换行。
