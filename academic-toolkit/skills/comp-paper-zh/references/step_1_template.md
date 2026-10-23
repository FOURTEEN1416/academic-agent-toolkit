## Step 1: Select template（复制、落地断言与骨架核对）

本文件是 `skills/comp-paper-zh/SKILL.md` Step 1 的执行细则。**模板选择分支（`if [ -z "$CONTEST_ID" ] … case … esac`）内联在 SKILL.md「Step 1」**，本文件承接选中 `$TMPL` 之后的复制、断言与核验。

选中 `$TMPL` 之后继续：

```bash
[ -d "$TMPL_BASE/$TMPL" ] || { echo "❌ 模板目录缺失：$TMPL_BASE/$TMPL/（入库位置 skills/comp-paper-zh/_templates/$TMPL/）。报能力缺口并停止，不得改用其他赛事模板。"; exit 1; }
# 按 .tex/.cls/.sty 逐文件复制：模板库中的子目录（如华为杯 official_docx/ 参考资料指针）
# 不是骨架组成，整体 glob 复制会因目录报错中断——这里只取骨架文件，逐文件显式失败
for _f in "$TMPL_BASE/$TMPL/"*.tex "$TMPL_BASE/$TMPL/"*.cls "$TMPL_BASE/$TMPL/"*.sty; do
    [ -e "$_f" ] || continue
    cp "$_f" paper/ || { echo "❌ 模板复制失败：$_f -> paper/"; exit 1; }
done
# 图/书目族（wuyi image2.png、dongsansheng refs.bib、huawei gmcm.bst 等骨架组成）
for _f in "$TMPL_BASE/$TMPL/"*.png "$TMPL_BASE/$TMPL/"*.bib "$TMPL_BASE/$TMPL/"*.bst; do
    [ -e "$_f" ] || continue
    cp "$_f" paper/ || { echo "❌ 模板复制失败：$_f -> paper/"; exit 1; }
done
# 字体子目录（huazhong/shuweibei 等模板以 Path=fonts/ 相对引用，整目录随迁）
if [ -d "$TMPL_BASE/$TMPL/fonts" ]; then cp -r "$TMPL_BASE/$TMPL/fonts" paper/; fi
echo "Template source: $CONTEST_ID -> $TMPL_BASE/$TMPL"

# ⛔ 同文档类复用核对（复制后立即执行）：复用骨架不携带另一赛事的封面、队号或声明。
# 逐项核对 paper/main.tex：源骨架注释口径、封面/标题占位、队号/编号设置、赛事声明——
# 一律替换/移除为本赛事当届口径；把源赛事专属元素留在交付物里属合规失败。

# ⛔ 模板落地断言：防止模板缺失时 cp 静默跳过、拖到编译阶段才炸——
#   此处硬性断言 cls/sty 已就位，否则立即失败并给出补救路径。
if ls paper/*.cls paper/*.sty > /dev/null 2>&1; then
    echo "✅ 模板文件已就位: $(ls paper/*.cls paper/*.sty 2>/dev/null | tr '
' ' ')"
else
    echo "❌ 模板缺失：$TMPL_BASE/ 下没有本题竞赛模板（paper/ 无 .cls/.sty）"
    echo "   补救路径："
    echo "   ① 国赛 cumcm：内置模板在 skills/comp-paper-zh/_templates/cumcm/，执行"
    echo "      cp skills/comp-paper-zh/_templates/cumcm/*.cls skills/comp-paper-zh/_templates/cumcm/*.sty paper/"
    echo "   ② 其他赛事：从赛事官方渠道获取模板文件夹放入 $TMPL_BASE/<赛事名>/ 后重跑"
    exit 1
fi

# Rename to main.tex if needed

[ -f paper/main.tex ] && echo "Template copied: $(wc -l < paper/main.tex) lines" || echo "ERROR: template not found!"

```

**⛔ 模板复制后立即验证（必须通过才能继续）：**

```bash

python skills/_utils/template_integrity_check.py --fingerprint --template-base skills/comp-paper-zh/_templates 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --fingerprint --template-base academic-toolkit/skills/comp-paper-zh/_templates 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --fingerprint --template-base ../../skills/comp-paper-zh/_templates

```

`--fingerprint` 按 documentclass 行定位模板原文，对比 paper/main.tex 前 20 行 preamble：差异过大（>10 行）说明骨架被重写——必须从模板重新复制、只替换占位符（字体/边距/编号/引用格式都在 preamble 里调好，重写必炸）。

Read the copied template to understand its structure before writing:

```bash

cat paper/main.tex

```

**⛔ 你必须完整读取 main.tex 模板内容。后续写章节时，只修改 sections/*.tex 文件，不要重写 main.tex。**

**模板骨架纪律（复制后必读）：`skills/comp-paper-zh/references/format-playbook.md` §2** —— 只改方括号占位符与 `\input` 文件名，不重写 preamble；CRITICAL TEMPLATE RULES 1-7、五一杯专项验证、封面占位符、不得修改清单与宏包位置都在该节。⛔ 出现违规（重写 main.tex / 手写图表清单 / 改 documentclass 或 geometry）即判版式返工。

**⛔ 华为杯专属（仅 `CONTEST_ID=comp_huawei` 时跑，其余赛事跳过）：**

```bash
# 标题机检：拦 \title{} 强制换行 + AI 风格自创标题
python skills/_utils/template_integrity_check.py --full 2>/dev/null || python academic-toolkit/skills/_utils/template_integrity_check.py --full 2>/dev/null || python ../../skills/_utils/template_integrity_check.py --full
```

版式/摘要/引用/提交逐项自检表见 `skills/comp-paper-zh/references/format-playbook.md` §3，标题硬约束见同文件 §4；完整证据 `skills/comp-paper-zh/references/huawei-official-format.md`，机检口径 `quick_gates --compliance-profile comp_huawei`。

Write all chapter content in separate `paper/sections/*.tex` files. The main.tex `\input{sections/...}` lines load them automatically. Do not paste chapter content directly into main.tex.

**正文引用命令按模板选择，唯一真源见 SKILL.md「引用命令」表**：`\upcite` 只在 cumcm / 华中杯 / wuyi / dongsansheng 有定义，其余模板禁用（undefined → 编译失败）。

Do not redefine LaTeX built-in commands (`\sin`, `\cos`, `\tanh`, `\log`, `\exp`, `\max`, `\min`, etc.) in math_commands.tex.
