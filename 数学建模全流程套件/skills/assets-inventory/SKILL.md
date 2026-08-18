---
name: assets-inventory
description: "扫描用户上传的资产（题目/代码/数据/图/结果），输出资产清单 ASSETS_INVENTORY.md 与一致性冲突报告 ASSETS_CONFLICTS.md，供后续步骤决定哪些资产已有、哪些需要补全。Use when user says \"资产清点\", \"assets inventory\", \"已有资产\"."
argument-hint: [paper-type]
allowed-tools: Bash(*), Read, Write, Edit, Grep, Glob
---

# 已有资产清点 + 一致性检查

把用户上传到 `user_data/` 的所有资产做一次盘点，并交叉检查这些资产之间是否一致。这是「从已有资产生成论文」工作流的第一步。

## 输入

- `user_data/` 下的所有上传文件
- `CLAUDE.md` 中的"用户自定义写作要求"段落（如果有）
- 论文类型（从工作流参数 `paper_type_target` 读取，可能值: `academic_zh / academic_en / competition / course / nature`）

## 必须输出

1. `ASSETS_INVENTORY.md` — 资产清单
2. `ASSETS_CONFLICTS.md` — 冲突报告（**只在检测到不一致时才写**；没冲突就不写这个文件）

## 工作流程

### Step 1: 扫描 user_data/

```bash
echo "=== 扫描 user_data/ ==="
ls -la user_data/ 2>/dev/null || { echo "user_data/ 不存在"; mkdir -p user_data; }
echo ""
echo "=== 文件清单（按类别分组）==="
echo ""
echo "[题目/要求]"
ls user_data/*.pdf user_data/*.docx user_data/*.md user_data/*.txt 2>/dev/null | grep -v "_extracted" | head -20

echo ""
echo "[代码]"
ls user_data/*.py user_data/*.ipynb user_data/*.zip 2>/dev/null | head -30

echo ""
echo "[数据]"
ls user_data/*.csv user_data/*.xlsx user_data/*.xls user_data/*.tsv user_data/*.json 2>/dev/null | head -30

echo ""
echo "[图]"
ls user_data/*.png user_data/*.jpg user_data/*.jpeg user_data/*.pdf user_data/*.svg 2>/dev/null | head -30

echo ""
echo "[结果文件]"
ls user_data/RESULTS* user_data/results* user_data/result* 2>/dev/null | head -20

echo ""
echo "[模板文件]"
ls user_data/*.tex user_data/*.cls user_data/*.sty user_data/*.docx user_data/*.dotx 2>/dev/null | head -10
```

### Step 2: 分类识别（基于文件后缀+内容启发式）

对每个文件，判断它属于以下哪一类（一个文件只能归一类，按优先级）：

| 类别 | 识别规则 | 示例 |
|------|---------|------|
| `problem` 题目 | 文件名含 problem/题目/赛题/requirement，或目录中只有 1 个 PDF/DOCX | `problem.pdf`, `2024 A 题.pdf`, `requirements.md` |
| `code` 代码 | 后缀 `.py/.ipynb/.zip/.r/.m/.cpp/.java` | `main.py`, `analysis.ipynb` |
| `data` 数据 | 后缀 `.csv/.xlsx/.xls/.tsv/.json/.parquet` | `load.csv`, `train.json` |
| `figure` 图 | 后缀 `.png/.jpg/.jpeg/.svg`，或非题目类 PDF | `fig1.png` |
| `result` 结果 | 文件名含 results/output/RESULTS，或 `.json` 含数值结果 | `results.json`, `RESULTS.md` |
| `template` 模板 | 后缀 `.tex/.cls/.sty/.docx/.dotx`，且和已有题目区分 | `thesis.cls`, `template.docx` |

**边缘情况处理**：
- 文件名含特殊字符/中文/空格 → 在清单中保留原名，不重命名
- 同名多版本（如 `results_v1.json`, `results_final.json`）→ 都列出，按修改时间标注最新
- `.zip` 文件 → 列出，**不自动解压**（在清单里写明"建议手动解压"）
- `.ipynb` → 标注"含代码 + 已有 cell 输出，可作为代码 + 结果同时使用"
- 已有 `*_extracted.txt`（系统已自动提取的 PDF 文本）→ 跳过，不重复列出

### Step 3: 把已识别资产从 `user_data/` 复制/移动到工作目录

按类别移动到工作目录（**只复制不删除**，保留 user_data/ 原件）：

```bash
mkdir -p code data figures
```

| 类别 | 目标目录 | 命名规则 |
|------|---------|---------|
| `code` | `code/` | 保留原名 |
| `data` | `data/` | 保留原名 |
| `figure` | `figures/` | 保留原名（如果原名不以 `fig_` 开头，加前缀 `user_fig_` 避免与自动生成的图冲突） |
| `result` | 工作根目录 | `results.json` 或 `RESULTS.md` 直接用 |
| `template` | `_user_templates/` | 保留原名 |
| `problem` | 不动 | 留在 user_data/ |

```bash
# 示例：复制图片
for img in user_data/*.png user_data/*.jpg user_data/*.jpeg user_data/*.svg; do
    [ -f "$img" ] || continue
    base=$(basename "$img")
    # 题目相关的 PDF 不算图
    case "$base" in
        problem*|题目*|赛题*) continue ;;
    esac
    # 命名规范化
    if [[ "$base" != fig_* && "$base" != user_fig_* ]]; then
        cp "$img" "figures/user_fig_${base}"
    else
        cp "$img" "figures/${base}"
    fi
done
```

### Step 4: 一致性检查（核心边缘情况防御）

⛔ **必须做的 6 项交叉检查**：

#### 4.1 数据 vs 代码（数据维度匹配？）
- 读 `code/main.py`（或其他 `.py`），找 `pd.read_csv("xxx.csv")` 或 `np.load(...)`
- 看代码引用的数据文件名是否在 `data/` 中存在
- 看代码假设的数据形状（如 `df.shape`）是否与实际 CSV 维度匹配

#### 4.2 图 vs 数据（图描述了的数据是否存在？）
- 看图文件名（如 `fig1_load_curve.png`）→ 推测该图描述的内容
- 在 `data/` 或 `results.json` 中找对应数据
- 找不到 → 标记"figure-data orphan"

#### 4.3 图 vs 代码（图中算法/方法 vs 代码用的算法？）
- 用 vision 描述（已自动放在 CLAUDE.md "上传图片内容（AI 自动识别）" 段）找出图中提到的方法名（NSGA-II / LSTM / ...）
- 在代码中搜对应关键词
- 不匹配 → 标记"method-mismatch"

#### 4.4 结果数值 vs 图中数值（最严重的不一致类型）
- 解析 `results.json` 中的关键数值（best_obj, accuracy, RMSE 等）
- 看 vision 识别的图描述里是否有相近但不同的数值（如 results 写 0.847，图标注 0.85）
- 差异 > 5% 视为严重；差异 < 1% 视为可接受

#### 4.5 数据/题目 主题对齐？
- 题目要预测电力负荷，数据传的是房价 → "topic-mismatch" 严重
- 用关键词匹配：题目里出现的核心词（如"光伏"、"电力"）应该在数据列名/代码注释里出现

#### 4.6 完整性检查
- 题目说有 4 问，看是否每问都有对应的代码/结果
- 没覆盖的问号 → 标记"missing-coverage"

#### 4.7 ⛔ 竞赛模式: 赛题问号覆盖度（核心检查）

**仅当 `paper_type_target=competition` 时执行**。

1. 通读题目 PDF/MD，列出所有问号编号（Q1/Q2/Q3/Q4 或"问题一/二/三/四"或主要任务点）
2. 对每个问号检查 3 类证据：
   - **代码证据**：`code/q1_*.py` / `code/main.py` 中是否有针对 Q1 的求解块
   - **结果证据**：`results.json` 中是否有 `q1_*` 字段，或 `RESULTS.md` 中 "Q1 / 问题一" 段
   - **图证据**：`figures/` 中文件名含 `q1_` / 内容是 Q1 输出
3. 输出对照表（必须打印到终端，写入 `_assets_index.json` 的 `competition_coverage` 字段）：
   ```
   === 赛题覆盖度对照 ===
   Q1: ✓ 已有 (code/q1_*.py + results.q1_obj=0.847)
   Q2: ✓ 已有 (code/q2_*.py + results.q2_pareto)
   Q3: ✗ 缺失 — 需要 comp-modeling + comp-code 补全
   Q4: ✗ 缺失 — 需要 comp-modeling + comp-code 补全
   ```
4. 如果题目里没有明确问号编号（纯文本要求），按主要任务点拆分，每个任务点视为一个虚拟"问号"
5. 在 `_assets_index.json` 中输出：
   ```json
   {
     "competition_coverage": {
       "total_questions": 4,
       "covered": ["Q1", "Q2"],
       "missing": ["Q3", "Q4"]
     }
   }
   ```
   并在 `missing_assets` 中追加 `q3_code`、`q3_results`、`q4_code`、`q4_results` 等具体缺口标识

### Step 5: 输出 ASSETS_INVENTORY.md

按下面的固定结构输出（**字段不能省略，找不到的写"无"**）：

```markdown
# 资产清单（assets-inventory）

> 生成时间：YYYY-MM-DD HH:MM
> 论文类型：{paper_type_target}
> 用户自定义要求：{custom_requirements 摘要 / "无"}

## ✓ 已有资产

### 题目/要求
- `user_data/problem.pdf` — CUMCM 2024 A 题，4 问
  - 已自动提取文本：`user_data/problem_extracted.txt`

### 代码
- `code/main.py` — NSGA-II 多目标优化 (350 行)
- `code/utils.py` — 数据预处理工具 (80 行)
- `user_data/notebook.ipynb` — Jupyter 笔记本（含已运行的 cell 输出）

### 数据
- `data/load.csv` — 城市负荷曲线 (100×168, 第一列日期, 后 167 列负荷值)
- `data/poi.json` — POI 数据 (3000 条)

### 图
- `figures/user_fig_demand.png` — 各城市需求热力图（用户上传，未重命名前: fig_demand.png）
- `figures/user_fig_pareto.pdf` — NSGA-II Pareto 前沿

### 结果
- `RESULTS.md` — 用户提供的结果说明（含 best_obj=0.847, iter=200）
- `results.json` — 结构化结果数据

### 模板
- `_user_templates/thesis.cls` — 用户提供的 LaTeX 类
- `_user_templates/main.tex` — 起始模板

## ✗ 缺失资产（自动补全策略）

### Q3 / Q4 的代码与结果（用户只提供了 Q1+Q2）
- 缺失类别：code + result
- 补全策略：后续 paper-analysis 步骤根据题目需求自动生成
- 补全位置：`code/q3_*.py`, `code/q4_*.py`, 追加到 `results.json`

### 技术路线图
- 缺失类别：figure (roadmap)
- 补全策略：后续 paper-figure-drawio 步骤生成
- 补全位置：`figures/fig_roadmap.png`

### 灵敏度分析图
- 缺失类别：figure
- 补全策略：后续 paper-figure 步骤生成
- 补全位置：`figures/fig_sensitivity.pdf`

## ⛔ 写作铁律（注入到 paper-plan / paper-write）

1. **已有结果 = 真值，逐字保留**
   - results.json 中所有数字在论文里**逐字保留**
   - 禁止四舍五入（0.847 ≠ 0.85）、禁止单位换算
   - 禁止编造未出现在 results 中的数值

2. **已有图 = 真值，直接引用**
   - 上面"图"列表中的每个文件必须**直接 `\includegraphics`**
   - 禁止重绘已有图
   - 图 caption 必须如实描述图内容，不允许写"如图 X 所示"但图里其实没有的内容

3. **已有代码 = 方法依据**
   - 论文中描述的方法必须与 `code/` 中实际实现一致
   - 禁止论文写"使用 NSGA-II"但代码里其实是 LSTM
   - 论文超参数（epochs, lr, batch_size）必须从代码或 results 中来

4. **用户自定义写作要求 = 强制约束**
   - {custom_requirements 全文，如果有}

5. **缺失资产由对应步骤自动补全**
   - 不要试图绕过 paper-analysis/paper-figure 步骤直接在 paper-write 里造数字/造图描述

## 资产文件索引（供后续步骤引用）

```json
{
  "problem": ["user_data/problem.pdf"],
  "problem_text": ["user_data/problem_extracted.txt"],
  "code": ["code/main.py", "code/utils.py", "user_data/notebook.ipynb"],
  "data": ["data/load.csv", "data/poi.json"],
  "figures": ["figures/user_fig_demand.png", "figures/user_fig_pareto.pdf"],
  "results": ["RESULTS.md", "results.json"],
  "templates": ["_user_templates/thesis.cls", "_user_templates/main.tex"]
}
```
（同时写入 `_assets_index.json` 供工作流引擎读取）
```

### Step 6: 输出 ASSETS_CONFLICTS.md（仅当有冲突）

只有当 Step 4 检测到 **>= 1 处不一致** 时才创建此文件。结构：

```markdown
# 资产一致性检查报告

> 生成时间：YYYY-MM-DD HH:MM
> 共检测到 N 处不一致，请用户确认处理策略

## 严重不一致（建议必须解决）

### 1. method-mismatch: 代码与图中算法不一致
- `code/main.py` 第 45 行：使用 `from torch.nn import LSTM`
- `figures/user_fig_arch.png` AI 描述：标注的架构是 Transformer
- 严重程度：HIGH（论文方法描述会自相矛盾）
- 处理选项：
  - [A] 以代码为准：删图，让 paper-figure 重新画 LSTM 架构图
  - [B] 以图为准：让 paper-analysis 重写代码用 Transformer
  - [C] 论文中明确说明用了两种方法做对比

## 中等不一致

### 2. value-mismatch: 结果数值与图中标注不同
- `results.json`: best_obj = 0.847
- `figures/user_fig_pareto.pdf` AI 描述：标注的最优解 = 0.85
- 差异：0.4% (可能只是显示精度)
- 严重程度：MEDIUM
- 处理选项：
  - [A] 以 results.json 为准（推荐）：论文写 0.847，图保留
  - [B] 以图为准：把 results.json 中的 0.847 改成 0.85（不推荐）

## 轻微不一致

### 3. missing-coverage: 题目要求 4 问但只覆盖 2 问
- 题目：CUMCM 2024 A 题, Q1-Q4
- 已有：results.json 含 Q1+Q2，缺 Q3+Q4
- 严重程度：LOW（paper-analysis 会自动补全）
- 处理：自动跑 paper-analysis 补全 Q3+Q4 代码与结果

## ✓ 一致性 OK 的部分

- `data/load.csv` 形状 (100, 168) 与 `code/main.py` 中 `df.shape == (100, 168)` 一致
- `figures/user_fig_demand.png` 描述与 `RESULTS.md` 中"Q1 输出热力图"对应
- 题目"光伏选址"关键词在 `data/poi.json` 列名中出现

## 用户决策提示

如果 ASSETS_CONFLICTS.md 中有 HIGH 严重等级的冲突，**强烈建议用户在工作流暂停时手动确认处理策略**。否则后续步骤会按以下默认策略处理：
- HIGH → 以"已有资产"为准（保留用户上传的图/结果，让代码重新生成匹配）
- MEDIUM → 以"results.json"为准
- LOW → paper-analysis/paper-figure 自动补全
```

### Step 7: 写 `_assets_index.json`（机器可读，供 workflow_engine 读）

```bash
cat > _assets_index.json <<'EOF'
{
  "has_problem": true,
  "has_code": true,
  "has_data": true,
  "has_figures": true,
  "has_results": true,
  "has_templates": false,
  "missing_assets": ["roadmap_figure", "sensitivity_figure", "q3_q4_code_results"],
  "conflicts": [
    {"type": "method-mismatch", "severity": "high", "files": ["code/main.py", "figures/user_fig_arch.png"]},
    {"type": "value-mismatch", "severity": "medium", "files": ["results.json", "figures/user_fig_pareto.pdf"]}
  ],
  "conflict_count": 2,
  "high_severity_count": 1
}
EOF
```

**字段含义**（workflow_engine 决定动态步骤跳过/执行时读这些字段）：
- `has_*`：用户是否提供了对应类别的资产
- `missing_assets`：缺失的资产标识（用于决定哪些步骤要跑）
- `conflicts[].severity`：`high / medium / low`
- `high_severity_count`：高严重等级冲突数（>0 时工作流应暂停让用户确认）

## 自检（写入 ASSETS_INVENTORY.md 后必做）

```bash
# 必须文件存在
[ -f ASSETS_INVENTORY.md ] || { echo "❌ ASSETS_INVENTORY.md 缺失"; exit 1; }
[ -f _assets_index.json ] || { echo "❌ _assets_index.json 缺失"; exit 1; }

# JSON 合法性
python3 -c "import json; json.load(open('_assets_index.json'))" || { echo "❌ _assets_index.json 非法"; exit 1; }

# 关键段落存在
grep -q "## ✓ 已有资产" ASSETS_INVENTORY.md || { echo "❌ 缺少'已有资产'段"; exit 1; }
grep -q "## ✗ 缺失资产" ASSETS_INVENTORY.md || { echo "❌ 缺少'缺失资产'段"; exit 1; }
grep -q "## ⛔ 写作铁律" ASSETS_INVENTORY.md || { echo "❌ 缺少'写作铁律'段"; exit 1; }

echo "✅ 资产清单生成完成"
```

## 边缘情况清单（必须处理）

| 边缘情况 | 处理策略 |
|---------|---------|
| user_data/ 完全空 | 写极简版 ASSETS_INVENTORY.md，标注「无任何资产，将退化到全自动模式」，`has_*` 全为 false |
| 只有题目，没其他资产 | 正常输出清单，`missing_assets` 列出全部缺口（code/data/figures/results/roadmap_figure 等） |
| 同名多版本（results_v1.json + results_final.json） | 都列出，按 mtime 选最新作为权威，旧版本标注 `[archive]` |
| .zip 文件 | 列出但不自动解压；`ASSETS_INVENTORY.md` 中提示用户手动解压 |
| .ipynb 文件 | 标注"代码+已有 cell 输出"双角色 |
| 文件名含中文/空格/特殊字符 | 保留原名，引用时用反引号包裹路径 |
| results.json 格式不规范（不是 JSON） | 当 `RESULTS.md` 处理（纯文本） |
| 中文图但要写英文论文 | 在 conflicts 里标注 "language-mismatch"，建议重绘 |
| 图分辨率太低（< 800px） | 在 conflicts 里标注 "low-resolution-figure"，建议重绘 |
| 文件超过 100MB | 在 inventory 中标注大小，提示无法直接 cat，需 sample 处理 |
| code/ 中有 .py 但没 main.py | 选最大的 .py 文件作为入口标注 |
| 同时有 zip 和解压后的目录 | 优先用解压目录，zip 标注「重复，已忽略」 |

## 不做的事

- ⛔ 不重新跑用户的代码（避免与用户结果冲突）
- ⛔ 不修改 `user_data/` 中的原始文件
- ⛔ 不重绘用户上传的图
- ⛔ 不编造数值（即使 results.json 缺失某指标，也不补，让后续步骤补）
