---
name: lit-review-systematic
description: "Conduct comprehensive, systematic literature reviews using multiple academic databases (PubMed, arXiv, bioRxiv, Semantic Scholar), with thematic synthesis and verified citations."
allowed-tools: Read Write Edit Bash
license: MIT license
metadata:
  version: "1.1"
  skill-author: K-Dense Inc.
---


<!--ACAT-ADAPTED: 资产补齐自 K-Dense-AI/scientific-agent-skills@36d8f13a1e754618794bf42f417884940077b4ae（MIT，fork FOURTEEN1416）。上游 research-lookup/parallel-cli 等 API 依赖在本仓库不可直接运行，以执行侧 web_search/web_fetch 工具替代；溯源见 references/UPSTREAM.md。2026-09-09 专项治理。2026-11-16 重收编：融入上游 2d2065f（v2.72.0，目录已重组为 literature-review）增量——11 个参考件/脚本/资产文件按上游补丁更新、五脚本 py_compile 通过；正文补 PRISMA 2020 流程与 records/reports/studies 三分计数、引用量不参与资格判定、双人资格判定与分歧留痕、AI 示意图新契约（OpenRouter 端点/模型/1-2 轮迭代、success≠科学准确、禁在 prompt 编造研究计数）与"DOI 存在≠论断有据"核验边界。-->
# Literature Review

## Overview

Conduct systematic, comprehensive literature reviews following rigorous academic methodology. Search multiple literature databases, synthesize findings thematically, verify all citations for accuracy, and generate professional output documents in markdown and PDF formats.

**Default primary web search channel**: the `lit-multi-db-search` skill's REST query templates, or executor-side `web_search` / `web_fetch` tools. If the `parallel-cli` tool (parallel-web) is installed locally, it may be used as an **optional accelerator** for broad search and URL extraction. Specialized database access skills (gget, bioservices, datacommons-client) may supplement coverage where available. This skill also provides specialized tools for citation verification, result aggregation, and document generation.

## When to Use This Skill

Use this skill when:
- Conducting a systematic literature review for research or publication
- Synthesizing current knowledge on a specific topic across multiple sources
- Performing meta-analysis or scoping reviews
- Writing the literature review section of a research paper or thesis
- Investigating the state of the art in a research domain
- Identifying research gaps and future directions
- Requiring verified citations and professional formatting

## Visual Enhancement with Scientific Schematics

**Recommended: include 1-2 figures when they add real value to the review** (e.g., a PRISMA flow diagram for systematic reviews). Figures are optional, not a completion requirement — add them only when they genuinely aid understanding.

Suggested figures for comprehensive reviews:
1. A PRISMA flow diagram (systematic reviews) — 使用 [PRISMA 2020 flow template](https://www.prisma-statement.org/prisma-2020-flow-diagram) 与核对后的筛选计数：区分 records / reports / studies，含"报告未获取"与全文排除原因；精确数字优先用表格或确定性绘图，不用 AI 生图编造计数
2. A search strategy flowchart, thematic synthesis diagram, or conceptual framework

**How to generate figures (optional):**
- Use the **scientific-schematics** skill where available to generate AI-powered publication-quality diagrams
- Describe your desired diagram in natural language; the image backend available in the current environment generates and refines the schematic

**How to generate schematics:**
```bash
python scripts/generate_schematic.py "your diagram description" -o figures/output.png --doc-type journal --iterations 2
```

助手契约（上游 v2.72.0 更新）：生成走 OpenRouter `POST /api/v1/images`（`google/gemini-3.1-flash-image`），评审走 `POST /api/v1/chat/completions`（`google/gemini-3.7-flash`）；需 `OPENROUTER_API_KEY`，输出路径须以 `.png` 结尾，迭代上限 1-2 次，精修失败保留前一张草稿。日志中的 `success` 只表示"存了图"，`quality_met`/`final_reviewed`/`termination_reason` 只描述自动评审——都不证明科学准确性；标签、计数、箭头与无障碍性须人工核查。运行付费生成前确认模型可用性；**不得在图像 prompt 里编造研究计数**。

**When to add schematics:**
- PRISMA flow diagrams for systematic reviews
- Literature search strategy flowcharts
- Thematic synthesis diagrams
- Research gap visualization maps
- Citation network diagrams
- Conceptual framework illustrations
- Any complex concept that benefits from visualization

For detailed guidance on creating schematics, refer to the scientific-schematics skill documentation.

---

## Core Workflow

Literature reviews follow a structured, multi-phase workflow:

### Phase 1: Planning and Scoping

1. **Define Research Question**: Use PICO framework (Population, Intervention, Comparison, Outcome) for clinical/biomedical reviews
   - Example: "What is the efficacy of CRISPR-Cas9 (I) for treating sickle cell disease (P) compared to standard care (C)?"

2. **Establish Scope and Objectives**:
   - Define clear, specific research questions
   - Determine review type (narrative, systematic, scoping, meta-analysis)
   - Set boundaries (time period, geographic scope, study types)

3. **Develop Search Strategy**:
   - Identify 2-4 main concepts from research question
   - List synonyms, abbreviations, and related terms for each concept
   - Plan Boolean operators (AND, OR, NOT) to combine terms
   - Select minimum 3 complementary databases
   - **For initial scoping**, run a quick broad search (default: executor-side `web_search`; optional `parallel-cli search` when installed locally) to gauge the landscape before formal database searches

4. **Set Inclusion/Exclusion Criteria**:
   - Date range (e.g., last 10 years: 2015-2024)
   - Language (typically English, or specify multilingual)
   - Publication types (peer-reviewed, preprints, reviews)
   - Study designs (RCTs, observational, in vitro, etc.)
   - Document all criteria clearly

### Phase 2: Systematic Literature Search

1. **Multi-Database Search**:

   Select databases appropriate for the domain. **Start with broad web-based academic coverage** — default: the `lit-multi-db-search` skill's REST query templates, or executor-side `web_search` — then supplement with domain-specific databases.

   **Web-Based Academic Search (default channel — START HERE):**
   - Default: use the `lit-multi-db-search` REST query templates, or executor-side `web_search` with academic domain filtering, for broad scholarly coverage
   - Optional accelerator: if `parallel-cli` is installed locally, `parallel-cli search` may substitute for the `web_search` calls below; if not installed, skip these commands and use the default channel
   - Run two searches: academic-focused + general to catch all relevant sources
   ```bash
   # OPTIONAL ACCELERATOR — only when parallel-cli is installed locally.
   # Default path: lit-multi-db-search REST templates or executor-side web_search/web_fetch.

   # Academic-focused search across scholarly sources
   parallel-cli search "your research topic" -q "keyword1" -q "keyword2" \
     --json --max-results 10 --excerpt-max-chars-total 27000 \
     --include-domains "scholar.google.com,arxiv.org,pubmed.ncbi.nlm.nih.gov,semanticscholar.org,biorxiv.org,medrxiv.org,ncbi.nlm.nih.gov,nature.com,science.org,ieee.org,acm.org,springer.com,wiley.com,cell.com,pnas.org,nih.gov" \
     -o sources/litreview_<topic>-academic.json

   # General search for supplementary sources
   parallel-cli search "your research topic" -q "keyword1" -q "keyword2" \
     --json --max-results 10 --excerpt-max-chars-total 27000 \
     -o sources/litreview_<topic>-general.json
   ```
   - Fetch full content from specific paper URLs or PDFs found in search results: default via executor-side `web_fetch`; optional `parallel-cli extract` when installed locally
   ```bash
   # Optional accelerator (only when parallel-cli is installed locally)
   parallel-cli extract "https://arxiv.org/abs/XXXX.XXXXX" --json
   ```

   **Biomedical & Life Sciences:**
   - Use `gget` skill: `gget search pubmed "search terms"` for PubMed/PMC
   - Use `gget` skill: `gget search biorxiv "search terms"` for preprints
   - Use `bioservices` skill for ChEMBL, KEGG, UniProt, etc.

   **General Scientific Literature:**
   - Search arXiv via direct API (preprints in physics, math, CS, q-bio)
   - Search Semantic Scholar via API (200M+ papers, cross-disciplinary)
   - Use Google Scholar for comprehensive coverage (manual or careful scraping)

   **Specialized Databases:**
   - Use `gget alphafold` for protein structures
   - Use `gget cosmic` for cancer genomics
   - Use `datacommons-client` for demographic/statistical data
   - Use specialized databases as appropriate for the domain

2. **Document Search Parameters**:
   ```markdown
   ## Search Strategy

   ### Database: PubMed
   - **Date searched**: 2024-10-25
   - **Date range**: 2015-01-01 to 2024-10-25
   - **Search string**:
     ```
     ("CRISPR"[Title] OR "Cas9"[Title])
     AND ("sickle cell"[MeSH] OR "SCD"[Title/Abstract])
     AND 2015:2024[Publication Date]
     ```
   - **Results**: 247 articles
   ```

   Repeat for each database searched.

3. **Export and Aggregate Results**:
   - Export results in JSON format from each database
   - Combine all results into a single file
   - Use `scripts/search_databases.py` for post-processing:
     ```bash
     python search_databases.py combined_results.json \
       --deduplicate \
       --format markdown \
       --output aggregated_results.md
     ```

### Phase 3: Screening and Selection

1. **Deduplication**:
   ```bash
   python search_databases.py results.json --deduplicate --output unique_results.json
   ```
   - Removes duplicates by DOI (primary) or title (fallback)
   - Document number of duplicates removed

2. **Title Screening**:
   - Review all titles against inclusion/exclusion criteria
   - Exclude obviously irrelevant studies
   - Document number excluded at this stage

3. **Abstract Screening**:
   - Read abstracts of remaining studies
   - Apply inclusion/exclusion criteria rigorously
   - Document reasons for exclusion

4. **Full-Text Screening**:
   - Obtain full texts of remaining studies
   - Conduct detailed review against all criteria
   - Document specific reasons for exclusion
   - Record final number of included studies

5. **Create PRISMA Flow Diagram**:
   ```
   Initial search: n = X
   ├─ After deduplication: n = Y
   ├─ After title screening: n = Z
   ├─ After abstract screening: n = A
   └─ Included in review: n = B
   ```

6. **Screening log (筛选理由留痕，必填)**: every exclusion decision is recorded in
   `screening_log.csv` so the PRISMA counts stay auditable:

   ```csv
   study_id,doi,title,stage,decision,reason_criterion,note,date
   S001,10.1234/abc,"Example title",abstract_screen,exclude,"E3: no eligible outcome","reviewer judgement",2026-11-16
   S002,10.1234/def,"Another title",full_text,include,,"",2026-11-16
   ```

   - `stage` ∈ {dedup, title_screen, abstract_screen, full_text}; `decision` ∈ {include, exclude}
   - `reason_criterion` must cite the inclusion/exclusion criterion ID (e.g. I1–I3 / E1–E5); a bare "not relevant" is not a reason
   - Keep this log beside the PRISMA counts; its `include` rows feed the evidence table in Phase 4.

7. **Records、reports 与 studies 要分开计数（上游 v2.72.0 增补）**: DOI/标题去重只去掉重复检索命中，不等于识别"同一研究"的全部论文——预印本、期刊版、协议与后续随访报告要用试验登记号、队列描述、站点与招募日期关联。维护 study-to-report 映射并注明每个结局取自哪份报告，meta-analysis 不对重叠参与者重复计数。PRISMA 各级计数（records screened / reports sought / not retrieved / assessed / excluded with reasons / included studies）分别核对，报告数可以多于研究数（参见 [Cochrane Handbook ch.4](https://www.cochrane.org/authors/handbooks-and-manuals/handbook/current/chapter-04)）。系统性评审的最终全文资格判定尽量双人独立进行并记录分歧解决方式；单人评审须如实披露。
8. **引用量不参与资格判定（上游 v2.72.0 增补）**: 引用数可用于探索性阅读排序，但不得决定入选与否，也不能替代偏倚风险评诂；检索与筛选阶段获取的每条合格记录都要保留。

### Phase 4: Data Extraction and Quality Assessment

1. **Extract Key Data** from each included study:
   - Study metadata (authors, year, journal, DOI)
   - Study design and methods
   - Sample size and population characteristics
   - Key findings and results
   - Limitations noted by authors
   - Funding sources and conflicts of interest

2. **Evidence table (证据表，Markdown + CSV 双形态必产出)**: one row per included
   study, structured by PICOS + effect measures. Save as `evidence_table.md`
   (human-readable) and `evidence_table.csv` (machine-readable, same columns):

   | Column | Meaning |
   |---|---|
   | `study_id` | ID carried over from the screening log (S001…) |
   | `citation` | Authors, year, journal, DOI |
   | `P` / `I` / `C` / `O` / `S` | PICOS: Population, Intervention, Comparator, Outcome, Study design |
   | `n` | Sample size (per arm where applicable) |
   | `population` | Population characteristics (age, condition, setting) |
   | `effect_measure` | Effect-size type: RR / OR / SMD / HR / beta / mean diff … |
   | `effect_value` | Point estimate with 95% CI (e.g. `0.72 [0.61-0.85]`) |
   | `quality` | Risk-of-bias rating from step 3 (High/Moderate/Low/Very Low) |
   | `theme` | Theme assignment(s) from step 4 |
   | `notes` | Limitations, funding/COI, caveats |

   ```csv
   study_id,citation,P,I,C,O,S,n,population,effect_measure,effect_value,quality,theme,notes
   S002,"Doe J, 2023, J Clin Epi, 10.1234/def","adults with X","drug A","placebo","mortality at 12m","RCT",450,"age>=18, hospitalized","RR","0.72 [0.61-0.85]","Moderate","theme-1","industry-funded"
   ```

   - Every `effect_value` must carry its measure type and CI; write `not reported` rather than guessing.
   - Keep the CSV and Markdown in sync; the CSV is the audit source of truth.

3. **Assess Study Quality**:
   - **For RCTs**: Use Cochrane Risk of Bias tool
   - **For observational studies**: Use Newcastle-Ottawa Scale
   - **For systematic reviews**: Use AMSTAR 2
   - Rate each study: High, Moderate, Low, or Very Low quality
   - Consider excluding very low-quality studies

4. **Organize by Themes**:
   - Identify 3-5 major themes across studies
   - Group studies by theme (studies may appear in multiple themes)
   - Note patterns, consensus, and controversies

### Phase 5: Synthesis and Analysis

1. **Create Review Document** from template:
   ```bash
   cp assets/review_template.md my_literature_review.md
   ```

2. **Write Thematic Synthesis** (NOT study-by-study summaries):
   - Organize Results section by themes or research questions
   - Synthesize findings across multiple studies within each theme
   - Compare and contrast different approaches and results
   - Identify consensus areas and points of controversy
   - Highlight the strongest evidence

   Example structure:
   ```markdown
   #### 3.3.1 Theme: CRISPR Delivery Methods

   Multiple delivery approaches have been investigated for therapeutic
   gene editing. Viral vectors (AAV) were used in 15 studies^1-15^ and
   showed high transduction efficiency (65-85%) but raised immunogenicity
   concerns^3,7,12^. In contrast, lipid nanoparticles demonstrated lower
   efficiency (40-60%) but improved safety profiles^16-23^.
   ```

3. **Critical Analysis**:
   - Evaluate methodological strengths and limitations across studies
   - Assess quality and consistency of evidence
   - Identify knowledge gaps and methodological gaps
   - Note areas requiring future research

4. **Write Discussion**:
   - Interpret findings in broader context
   - Discuss clinical, practical, or research implications
   - Acknowledge limitations of the review itself
   - Compare with previous reviews if applicable
   - Propose specific future research directions

### Phase 6: Citation Verification

**CRITICAL**: All citations must be verified for accuracy before final submission.

1. **Verify All DOIs**:
   ```bash
   python scripts/verify_citations.py my_literature_review.md
   ```

   This script:
   - Extracts all DOIs from the document
   - Verifies each DOI resolves correctly
   - Retrieves metadata from CrossRef
   - Generates verification report
   - Outputs properly formatted citations

2. **Review Verification Report**:
   - Check for any failed DOIs
   - Verify author names, titles, and publication details match
   - Correct any errors in the original document
   - Re-run verification until all citations pass

3. **Format Citations Consistently**:
   - Choose one citation style and use throughout (see `references/citation_styles.md`)
   - Common styles: APA, Nature, Vancouver, Chicago, IEEE
   - Use verification script output to format citations correctly
   - Ensure in-text citations match reference list format

4. **核对"引用是否支持论断"（上游 v2.72.0 增补）**: `verify_citations.py` 只验证 DOI 可解析与元数据一致——**DOI 存在不等于证据成立**：注册 DOI 仍可能指向别的论文。逐条把参考文献与被引论断对照原文，检查身份一致、论断有据、更正与撤稿状态；无法获取原文的标注"未获取"而不臆断。

### Phase 7: Document Generation

1. **Generate PDF**:
   ```bash
   python scripts/generate_pdf.py my_literature_review.md \
     --citation-style apa \
     --output my_review.pdf
   ```

   Options:
   - `--citation-style`: apa, nature, chicago, vancouver, ieee
   - `--no-toc`: Disable table of contents
   - `--no-numbers`: Disable section numbering
   - `--check-deps`: Check if pandoc/xelatex are installed

2. **Review Final Output**:
   - Check PDF formatting and layout
   - Verify all sections are present
   - Ensure citations render correctly
   - Check that figures/tables appear properly
   - Verify table of contents is accurate

3. **Quality Checklist**:
   - [ ] All DOIs verified with verify_citations.py
   - [ ] Citations formatted consistently
   - [ ] PRISMA flow diagram included (for systematic reviews)
   - [ ] Search methodology fully documented
   - [ ] Inclusion/exclusion criteria clearly stated
   - [ ] Results organized thematically (not study-by-study)
   - [ ] Quality assessment completed
   - [ ] Limitations acknowledged
   - [ ] References complete and accurate
   - [ ] PDF generates without errors

## Database-Specific Search Guidance

### PubMed / PubMed Central

Access via `gget` skill:
```bash
# Search PubMed
gget search pubmed "CRISPR gene editing" -l 100

# Search with filters
# Use PubMed Advanced Search Builder to construct complex queries
# Then execute via gget or direct Entrez API
```

**Search tips**:
- Use MeSH terms: `"sickle cell disease"[MeSH]`
- Field tags: `[Title]`, `[Title/Abstract]`, `[Author]`
- Date filters: `2020:2024[Publication Date]`
- Boolean operators: AND, OR, NOT
- See MeSH browser: https://meshb.nlm.nih.gov/search

### bioRxiv / medRxiv

Access via `gget` skill:
```bash
gget search biorxiv "CRISPR sickle cell" -l 50
```

**Important considerations**:
- Preprints are not peer-reviewed
- Verify findings with caution
- Check if preprint has been published (CrossRef)
- Note preprint version and date

### arXiv

Access via direct API or WebFetch:
```python
# Example search categories:
# q-bio.QM (Quantitative Methods)
# q-bio.GN (Genomics)
# q-bio.MN (Molecular Networks)
# cs.LG (Machine Learning)
# stat.ML (Machine Learning Statistics)

# Search format: category AND terms
search_query = "cat:q-bio.QM AND ti:\"single cell sequencing\""
```

### Semantic Scholar

Access via direct API (requires API key, or use free tier):
- 200M+ papers across all fields
- Excellent for cross-disciplinary searches
- Provides citation graphs and paper recommendations
- Use for finding highly influential papers

### Specialized Biomedical Databases

Use appropriate skills:
- **ChEMBL**: `bioservices` skill for chemical bioactivity
- **UniProt**: `gget` or `bioservices` skill for protein information
- **KEGG**: `bioservices` skill for pathways and genes
- **COSMIC**: `gget` skill for cancer mutations
- **AlphaFold**: `gget alphafold` for protein structures
- **PDB**: `gget` or direct API for experimental structures

### Citation Chaining

Expand search via citation networks:

1. **Forward citations** (papers citing key papers):
   - Find papers citing a specific work — default: Semantic Scholar or OpenAlex APIs, executor-side `web_search`, or Google Scholar "Cited by"; optional `parallel-cli search` when installed locally:
     ```bash
     # Optional accelerator (only when parallel-cli is installed locally)
     parallel-cli search "papers citing [Author et al. Year] [paper title]" \
       -q "citing" -q "[key author]" \
       --json --max-results 10 --excerpt-max-chars-total 27000 \
       --include-domains "scholar.google.com,semanticscholar.org,arxiv.org,pubmed.ncbi.nlm.nih.gov" \
       -o sources/litreview_forward_citations.json
     ```
   - Identifies newer research building on seminal work

2. **Backward citations** (references from key papers):
   - Fetch full text of key papers and extract their reference lists — default: executor-side `web_fetch`; optional `parallel-cli extract` when installed locally:
     ```bash
     # Optional accelerator (only when parallel-cli is installed locally)
     parallel-cli extract "https://doi.org/10.xxxx/yyyy" --json
     ```
   - Extract references from included papers
   - Identify highly cited foundational work
   - Find papers cited by multiple included studies

## Citation Style Guide

Detailed formatting guidelines are in `references/citation_styles.md`. Quick reference:

### APA (7th Edition)
- In-text: (Smith et al., 2023)
- Reference: Smith, J. D., Johnson, M. L., & Williams, K. R. (2023). Title. *Journal*, *22*(4), 301-318. https://doi.org/10.xxx/yyy

### Nature
- In-text: Superscript numbers^1,2^
- Reference: Smith, J. D., Johnson, M. L. & Williams, K. R. Title. *Nat. Rev. Drug Discov.* **22**, 301-318 (2023).

### Vancouver
- In-text: Superscript numbers^1,2^
- Reference: Smith JD, Johnson ML, Williams KR. Title. Nat Rev Drug Discov. 2023;22(4):301-18.

**Always verify citations** with verify_citations.py before finalizing.

### Prioritizing High-Impact Papers (CRITICAL)

**Always prioritize influential, highly-cited papers from reputable authors and top venues.** Quality matters more than quantity in literature reviews.

#### Citation Count Thresholds

Use citation counts to identify the most impactful papers:

| Paper Age | Citation Threshold | Classification |
|-----------|-------------------|----------------|
| 0-3 years | 20+ citations | Noteworthy |
| 0-3 years | 100+ citations | Highly Influential |
| 3-7 years | 100+ citations | Significant |
| 3-7 years | 500+ citations | Landmark Paper |
| 7+ years | 500+ citations | Seminal Work |
| 7+ years | 1000+ citations | Foundational |

#### Journal and Venue Tiers

Prioritize papers from higher-tier venues:

- **Tier 1 (Always Prefer):** Nature, Science, Cell, NEJM, Lancet, JAMA, PNAS, Nature Medicine, Nature Biotechnology
- **Tier 2 (Strong Preference):** High-impact specialized journals (IF>10), top conferences (NeurIPS, ICML for ML/AI)
- **Tier 3 (Include When Relevant):** Respected specialized journals (IF 5-10)
- **Tier 4 (Use Sparingly):** Lower-impact peer-reviewed venues

#### Author Reputation Assessment

Prefer papers from:
- **Senior researchers** with high h-index (>40 in established fields)
- **Leading research groups** at recognized institutions (Harvard, Stanford, MIT, Oxford, etc.)
- **Authors with multiple Tier-1 publications** in the relevant field
- **Researchers with recognized expertise** (awards, editorial positions, society fellows)

#### Identifying Seminal Papers

For any topic, identify foundational work by:
1. **High citation count** (typically 500+ for papers 5+ years old)
2. **Frequently cited by other included studies** (appears in many reference lists)
3. **Published in Tier-1 venues** (Nature, Science, Cell family)
4. **Written by field pioneers** (often cited as establishing concepts)

## Best Practices

### Search Strategy
1. **Start with broad web coverage**: Use the `lit-multi-db-search` REST templates or executor-side `web_search` with academic domains for initial broad coverage before querying specialized databases (optional `parallel-cli search` when installed locally)
2. **Use multiple databases** (minimum 3): Ensures comprehensive coverage
3. **Include preprint servers**: Captures latest unpublished findings
4. **Document everything**: Search strings, dates, result counts for reproducibility — save all search output to `sources/`
5. **Test and refine**: Run pilot searches, review results, adjust search terms
6. **Sort by citations**: When available, sort search results by citation count to surface influential work first
7. **Fetch full content**: Use executor-side `web_fetch` (or optional `parallel-cli extract` when installed locally) on promising URLs found during search to verify relevance before full-text screening

### Screening and Selection
1. **Use clear criteria**: Document inclusion/exclusion criteria before screening
2. **Screen systematically**: Title → Abstract → Full text
3. **Document exclusions**: Record reasons for excluding studies
4. **Consider dual screening**: For systematic reviews, have two reviewers screen independently

### Synthesis
1. **Organize thematically**: Group by themes, NOT by individual studies
2. **Synthesize across studies**: Compare, contrast, identify patterns
3. **Be critical**: Evaluate quality and consistency of evidence
4. **Identify gaps**: Note what's missing or understudied

### Quality and Reproducibility
1. **Assess study quality**: Use appropriate quality assessment tools
2. **Verify all citations**: Run verify_citations.py script
3. **Document methodology**: Provide enough detail for others to reproduce
4. **Follow guidelines**: Use PRISMA for systematic reviews

### Writing
1. **Be objective**: Present evidence fairly, acknowledge limitations
2. **Be systematic**: Follow structured template
3. **Be specific**: Include numbers, statistics, effect sizes where available
4. **Be clear**: Use clear headings, logical flow, thematic organization

## Common Pitfalls to Avoid

1. **Single database search**: Misses relevant papers; always search multiple databases
2. **No search documentation**: Makes review irreproducible; document all searches
3. **Study-by-study summary**: Lacks synthesis; organize thematically instead
4. **Unverified citations**: Leads to errors; always run verify_citations.py
5. **Too broad search**: Yields thousands of irrelevant results; refine with specific terms
6. **Too narrow search**: Misses relevant papers; include synonyms and related terms
7. **Ignoring preprints**: Misses latest findings; include bioRxiv, medRxiv, arXiv
8. **No quality assessment**: Treats all evidence equally; assess and report quality
9. **Publication bias**: Only positive results published; note potential bias
10. **Outdated search**: Field evolves rapidly; clearly state search date

## Example Workflow

Complete workflow for a biomedical literature review:

```bash
# 1. Create review document from template
cp assets/review_template.md crispr_sickle_cell_review.md

# 2. Broad academic search — DEFAULT: lit-multi-db-search REST templates or
#    executor-side web_search. The parallel-cli commands below are an OPTIONAL
#    accelerator, only when parallel-cli is installed locally.
parallel-cli search "CRISPR Cas9 sickle cell disease gene therapy efficacy" \
  -q "CRISPR" -q "sickle cell" -q "gene therapy" \
  --json --max-results 10 --excerpt-max-chars-total 27000 \
  --include-domains "scholar.google.com,arxiv.org,pubmed.ncbi.nlm.nih.gov,semanticscholar.org,biorxiv.org,nature.com,science.org,cell.com,pnas.org,nih.gov" \
  -o sources/litreview_crispr_scd-academic.json

parallel-cli search "CRISPR sickle cell disease clinical trials treatment" \
  -q "CRISPR" -q "sickle cell" \
  --json --max-results 10 --excerpt-max-chars-total 27000 \
  -o sources/litreview_crispr_scd-general.json

# 3. Search specialized databases using appropriate skills
# - Use gget skill for PubMed, bioRxiv
# - Use direct API access for arXiv, Semantic Scholar
# - Export results in JSON format

# 4. Aggregate and process results (combine web search + database results)
python scripts/search_databases.py combined_results.json \
  --deduplicate \
  --rank citations \
  --year-start 2015 \
  --year-end 2024 \
  --format markdown \
  --output search_results.md \
  --summary

# 5. Screen results and extract data
# - Use web_fetch (or optional parallel-cli extract when installed locally) to fetch full content from promising URLs
# - Manually screen titles, abstracts, full texts
# - Extract key data into the review document
# - Organize by themes

# 6. Write the review following template structure
# - Introduction with clear objectives
# - Detailed methodology section
# - Results organized thematically
# - Critical discussion
# - Clear conclusions

# 7. Verify all citations
python scripts/verify_citations.py crispr_sickle_cell_review.md

# Review the citation report
cat crispr_sickle_cell_review_citation_report.json

# Fix any failed citations and re-verify
python scripts/verify_citations.py crispr_sickle_cell_review.md

# 8. Generate professional PDF
python scripts/generate_pdf.py crispr_sickle_cell_review.md \
  --citation-style nature \
  --output crispr_sickle_cell_review.pdf

# 9. Review final PDF and markdown outputs
```

## Integration with Other Skills

This skill works seamlessly with other scientific skills:

### Web Search & Extraction (default: lit-multi-db-search REST templates / web_search / web_fetch)
- **Default channel**: the `lit-multi-db-search` skill's REST query templates and executor-side `web_search` / `web_fetch` — use for initial scoping, finding papers, citation chaining, fetching full content, and supplementary searches
- **Optional accelerator — `parallel-cli`, only when installed locally:**
  - `parallel-cli search`: broad academic and general web search with domain filtering — an optional substitute for the default `web_search` channel
  - `parallel-cli extract`: fetch full content from paper URLs, journal websites, and preprint servers — an optional substitute for the default `web_fetch` channel
  - `parallel-cli search --include-domains`: academic-focused search across scholarly domains (arxiv.org, pubmed, nature.com, etc.)

### Database Access Skills
- **gget**: PubMed, bioRxiv, COSMIC, AlphaFold, Ensembl, UniProt
- **bioservices**: ChEMBL, KEGG, Reactome, UniProt, PubChem
- **datacommons-client**: Demographics, economics, health statistics

### Analysis Skills
- **pydeseq2**: RNA-seq differential expression (for methods sections)
- **scanpy**: Single-cell analysis (for methods sections)
- **anndata**: Single-cell data (for methods sections)
- **biopython**: Sequence analysis (for background sections)

### Visualization Skills
- **matplotlib**: Generate figures and plots for review
- **seaborn**: Statistical visualizations

### Writing Skills
- **brand-guidelines**: Apply institutional branding to PDF
- **internal-comms**: Adapt review for different audiences

## Resources

### Bundled Resources

**Scripts:**
- `scripts/verify_citations.py`: Verify DOIs and generate formatted citations
- `scripts/generate_pdf.py`: Convert markdown to professional PDF
- `scripts/search_databases.py`: Process, deduplicate, and format search results

**References:**
- `references/citation_styles.md`: Detailed citation formatting guide (APA, Nature, Vancouver, Chicago, IEEE)
- `references/database_strategies.md`: Comprehensive database search strategies

**Assets:**
- `assets/review_template.md`: Complete literature review template with all sections

### External Resources

**Guidelines:**
- PRISMA (Systematic Reviews): http://www.prisma-statement.org/
- Cochrane Handbook: https://training.cochrane.org/handbook
- AMSTAR 2 (Review Quality): https://amstar.ca/

**Tools:**
- MeSH Browser: https://meshb.nlm.nih.gov/search
- PubMed Advanced Search: https://pubmed.ncbi.nlm.nih.gov/advanced/
- Boolean Search Guide: https://www.ncbi.nlm.nih.gov/books/NBK3827/

**Citation Styles:**
- APA Style: https://apastyle.apa.org/
- Nature Portfolio: https://www.nature.com/nature-portfolio/editorial-policies/reporting-standards
- NLM/Vancouver: https://www.nlm.nih.gov/bsd/uniform_requirements.html

## Dependencies

### Required CLI Tools
```bash
# No CLI installation is required for the default search channel:
# lit-multi-db-search REST templates + executor-side web_search/web_fetch.
#
# Optional accelerator (only if you choose to install it locally):
# parallel-cli — see https://parallel.ai for official installation instructions.
```

### Required Python Packages
```bash
pip install requests  # For citation verification
```

### Required System Tools
```bash
# For PDF generation
brew install pandoc  # macOS
apt-get install pandoc  # Linux

# For LaTeX (PDF generation)
brew install --cask mactex  # macOS
apt-get install texlive-xetex  # Linux
```

Check dependencies:
```bash
python scripts/generate_pdf.py --check-deps
```

## Summary

This literature-review skill provides:

1. **Systematic methodology** following academic best practices
2. **Broad academic search** via the `lit-multi-db-search` REST templates or executor-side `web_search` / `web_fetch`, with optional `parallel-cli` acceleration when installed locally, and scholarly domain filtering
3. **Multi-database integration** via existing scientific skills (gget, bioservices, datacommons-client)
4. **Citation verification** ensuring accuracy and credibility
5. **Professional output** in markdown and PDF formats
6. **Comprehensive guidance** covering the entire review process
7. **Quality assurance** with verification and validation tools
8. **Reproducibility** through detailed documentation requirements

Conduct thorough, rigorous literature reviews that meet academic standards and provide comprehensive synthesis of current knowledge in any domain.

