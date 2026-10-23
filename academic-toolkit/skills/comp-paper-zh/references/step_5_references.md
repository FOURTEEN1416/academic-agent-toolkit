## Step 5: References

本文件是 `skills/comp-paper-zh/SKILL.md` Step 5 的执行细则；正文引用命令的唯一口径见 SKILL.md「引用命令」表。

Follow the `<references_workflow>` in `skills/_utils/writing_rules.md`.

统计建模 ≥20 条参考文献。**正文引用命令按模板选择，唯一真源见 SKILL.md「引用命令」表。** 文献系统按模板：stats 用 `\bibliography{references}` + `\bibliographystyle{plainnat}`；cumcm / wuyi 用 `gbt7714-numerical` + `\bibliography{references}`；华中杯用手写 `\begin{thebibliography}{99}` 的 `\bibitem`（不用 `\bibliography{}`）。

**⛔ 使用 scholar_fetch.py 工具获取所有参考文献的 BibTeX。禁止凭记忆编造 BibTeX。**

**⛔⛔ 引用编号必须全局递增（严格，不可违反）：** 全文首次引用必须按 [1], [2], [3]... 顺序出现；先 [3] 后 [8] 再回 [1]、或已现 [5] 后又出新引用 [3]，都是编号跳跃/回退，均不可违反。保证方法：key 在 .bib / thebibliography 里的排列顺序 = 正文首次出现顺序（`\begin{thebibliography}` 模板手工排，`\bibliography{references}` 模板 BibTeX 自动排）；写作中新加的引用编号自然排到当前最大值+1；写完全文逐段扫一遍编号确认严格递增（只许重复已出现的编号）。

**⛔ 中文竞赛论文引用必须上标**：模板已配上标（natbib `super` / `gbt7714-numerical`）直接用 `\cite{}`；模板未配上标时用 `\upcite{}`（仅限有定义的模板）或 `\textsuperscript{\cite{}}`。每模板的具体命令见 SKILL.md「引用命令」表。

**⛔ 多引用合并规则（合并必须按编号升序）：** `方法A\cite{a,b,c}` 一个命令逗号分隔，且 key 顺序必须对应编号升序（[1,2,5]）；编号不相邻（如 [3] 与 [7]）可分开写 `\cite{a}\cite{b}`；连续相邻的多个 `\cite` 必须合并；**宁愿分开写也不要错序合并**（`\cite{c,a,b}` 对应 [5,1,2] 是错误）。写作时难以预知最终编号，先按 key 出现逻辑合并，编译后用 compile_check.sh 检查调整。

**⛔ 引用写法规则：写正文时，citation key 必须包含描述性关键词，格式为 `作者姓_年份_主题关键词`。**

例如：`\cite{wang_2023_supply_chain_resilience}` 而不是 `\cite{wang2023supply}`。

不确定作者/年份时用 `TODO__` 前缀：`\cite{TODO__digital_economy_spatial_spillover}`。

```bash

# Step 5a: 收集所有引用 key

grep -roh '\\cite[tp]*{[^}]*}' paper/sections/*.tex paper/main.tex 2>/dev/null \

  | grep -oP '\{[^}]+\}' | tr -d '{}' | tr ',' '\n' | sed 's/^ *//;s/ *$//' | sort -u > _tmp/_cited_keys.txt

echo "引用 key 数量: $(wc -l < _tmp/_cited_keys.txt)"

# Step 5b: 逐个搜索并获取 BibTeX（用描述性关键词搜索）

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

SCHOLAR_SCRIPT="tools/scholar_fetch.py"

while IFS= read -r key; do

    query=$(echo "$key" | sed 's/^TODO__//; s/_/ /g')

    echo "--- 获取: $key (搜索: $query) ---"

    $PYTHON "$SCHOLAR_SCRIPT" bibtex "$query" --max 3

    sleep 0.5

done < _tmp/_cited_keys.txt

```

处理每个搜索结果：

1. 检查 `match_label`：`"good"` → 直接使用。`"partial"` → 核实标题。`"low"` → 很可能搜错了，换关键词或用 WebSearch。

2. `match_score` < 0.3 说明大概率不是目标论文，不要盲目使用。

3. 将 .tex 中的 citation key 替换为 BibTeX 条目中的实际 key。

4. `bibtex_source=auto` 的条目加 `% [VERIFY]`。`match_label="low"` 的加 `% [LOW_MATCH]`。
