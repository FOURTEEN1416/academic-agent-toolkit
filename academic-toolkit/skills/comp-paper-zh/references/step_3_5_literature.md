## Step 3.5: 文献预检索（写正文之前必须完成）

本文件是 `skills/comp-paper-zh/SKILL.md` Step 3.5 的执行细则；触发条件与放行判据见 SKILL.md「Workflow」。

**⛔ 在写任何 \cite{} 之前，必须先建立已验证的文献池。** 往届优秀论文（`academic-toolkit/data/historical_papers.md` 与本地优秀论文页面图）仅作写法/模式借鉴——其无著录信息，禁止据此编造 bib 条目。

```bash

PYTHON=""; for _c in "$MH_PYTHON" python python3; do [ -z "$_c" ] && continue; if $_c -c "import sys" >/dev/null 2>&1; then PYTHON="$_c"; break; fi; done; [ -z "$PYTHON" ] && PYTHON=python

mkdir -p _tmp

# 根据论文主题搜索真实论文，建立引用池

# 示例（根据实际选题调整）：

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的核心方法关键词" --max 5

#   $PYTHON "$SCHOLAR_SCRIPT" bibtex "你的研究领域关键词" --max 5

```

搜索后创建 `_tmp/_verified_refs.txt`，写正文时只引用池子里的论文。需要新引用时先搜索验证再加入池子。

**兜底**：如果 `scholar_fetch.py` 搜不到或 `match_label="low"`，用 WebSearch 在 Google Scholar / Semantic Scholar 网站上搜索，手动核实标题+作者+年份后再加入池子。
