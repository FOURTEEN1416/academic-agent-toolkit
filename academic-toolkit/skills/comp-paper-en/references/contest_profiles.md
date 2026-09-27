# Contest profiles reference (comp-paper-en)

任务裁决用参考资料。**只读当前 `CONTEST_ID` 对应的条目**，不读其他赛事条目。
数值与格式规则以 `engine/modex-core/comp_rules.json`（引擎经 `contest_profile` 下发）为唯一真源；
本文件不复制数值，只记录：条目要点、AI 声明规定状态、能力缺口。

条目状态标记：`[evidenced]` = 档案已有带来源的规定；`[待核实]` = 档案暂无该规定，
须取当届官方规程核实后由 E 窗入库，不得用通用说明冒充合规。

## comp_mcm（MCM/ICM，COMAP）

- 模板骨架：`_templates/mcm/`（`mcmthesis.cls`，pdflatex）。`contest_profile.template_cls=mcmthesis`。
- 结构/Summary Sheet 等要求：档案 `rules_highlights` 为准（Summary 独立成页、含 team control number）。
- 页数：上限只认下发的 `PAGE_CAP`；`page_scope` 档案暂缺 → 计数口径 `[待核实]`
  （COMAP 当届 instructions：正文/总页口径以当届文字为准，投稿前核对）。
- AI use report：当届官方 AI use policy `[待核实]` —— 档案暂无 disclosure 字段。
  按 Step 4.7 规则：有用户确认记录（`.mh/ai_disclosure.json`）则按当届官方格式如实生成；
  无规定入库则上报待核实项，不用通用短说明充当合规。

## comp_apmcm（亚太赛，英文）

- 模板骨架：`_templates/apmcm/`（`apmcmthesis.cls`，pdflatex）。
- 提交格式按官网 PDF 模板 `[待核实]`（当届简章未入库）。
- AI 声明：当届规定 `[待核实]`，处理同上。

## comp_certcup_en（认证杯国际赛 / 小美赛）

- 模板骨架：档案写明"使用 article 或 mcmthesis 文档类"——Step 1 取 `_templates/mcm/`
  （mcmthesis 为档案点名的合法选项，不是跨赛事冒用）。
- AI 声明 / 当届格式细则：`[待核实]`。

## comp_shuwei_en（数维杯国际赛，ISTIC）——已声明能力缺口

- 档案 `template_cls: article`，仓库内**无英文 article 起始骨架**
  （`mcm/`=mcmthesis、`apmcm/`=apmcmthesis，均非本赛档案指定类）。
- 处置：Step 1 显式报能力缺口并停止；**禁止**偷偷套用 mcmthesis/其他赛事模板。
- 解除条件：入库 article 类英文骨架（或 E 窗修订档案指定类）后更新本条目与 Step 1 case 表。

## 维护约定

- 本文件只增改事实与状态标记，不写数值规则（数值归档案，E 窗取证、B 窗解析下发）。
- `[待核实]` 项经 E 窗取证入库 `comp_rules.json` 后，由本窗或后续任务改为 `[evidenced]` 并注明档案字段。
