---
name: market-research-reports
description: Generate comprehensive market research reports and industry/competitive analysis in the style of top consulting firms. Use for market sizing, competitive landscape, market entry, investment thesis, strategic recommendations, and consulting-style business reports. Do not use for scientific reports, paper writing, LaTeX submission/PDF builds, EDGAR/FRED/Treasury/Data Commons data retrieval, or biomedical literature evidence work.
allowed-tools: Read Write Edit Bash
license: MIT license
metadata:
    skill-author: K-Dense Inc.
---

# Market Research Reports

## Overview

Market research reports are strategic documents for analyzing industries, markets, and competitive landscapes. They support business decisions, investment theses, due diligence, market entry, product strategy, and executive planning.

**Key Features:**
- **Comprehensive length**: Reports are designed to be 50+ pages with no token constraints
- **Visual-rich content**: Plan the core market, competitive, risk, and roadmap visuals before drafting
- **Data-driven analysis**: Ground market claims in cited public, company, industry, and government sources
- **Multi-framework approach**: Porter's Five Forces, PESTLE, SWOT, BCG Matrix, TAM/SAM/SOM
- **Professional formatting**: Consulting-firm quality typography, colors, and layout
- **Actionable recommendations**: Strategic focus with implementation roadmaps

**Output Format:** A professional market-report package, usually Markdown or LaTeX/PDF when the task asks for a deliverable document. Use the bundled `assets/market_research.sty` and `assets/market_report_template.tex` when a LaTeX report is appropriate.

## Routing Boundary

Use this skill for market research report, industry report, competitive analysis, market sizing, market entry, due diligence, investment thesis, and consulting-style strategic report tasks.

Do not use this skill for:

- Scientific reports, technical reports, IMRAD papers, or experimental results reports
- LaTeX manuscript construction, submission PDF builds, journal templates, or paper packaging
- EDGAR/SEC filings, 10-K/10-Q/XBRL/13F extraction
- FRED macro time series
- U.S. Treasury Fiscal Data, national debt, federal spending, or deficit queries
- Data Commons statistical graph queries
- PubMed, ClinicalTrials.gov, biomedical evidence tables, or literature reviews

## When to Use This Skill

This skill should be used when:

- Creating comprehensive market analysis for investment decisions
- Developing industry reports for strategic planning
- Analyzing competitive landscapes and market dynamics
- Conducting market sizing exercises such as TAM/SAM/SOM
- Evaluating market entry opportunities
- Preparing due diligence materials for M&A activities
- Developing go-to-market strategy documentation
- Analyzing regulatory and policy impacts on markets
- Building business cases for new product launches

## Workflow

### 1. Define Scope

- Define the target market, geography, customer segment, and time horizon.
- State included and excluded segments.
- Identify the decisions the report must support.
- Capture assumptions that cannot be verified directly.

### 2. Gather Source Evidence

Gather market data from relevant public, company, government, industry association, and academic sources. Store source notes under `sources/`, record citations, and mark unsupported claims as assumptions.

Recommended source categories:

- Company filings, investor presentations, earnings transcripts, and annual reports
- Government statistics and regulatory publications
- Industry association reports and market datasets
- Academic or technical studies for technology adoption, cost curves, and risk context
- Credible news and analyst commentary when primary data is unavailable

### 3. Build the Analysis

Apply only the frameworks that fit the report question:

- **Market Sizing**: TAM, SAM, SOM with explicit assumptions
- **Porter's Five Forces**: supplier power, buyer power, new entrants, substitutes, rivalry
- **PESTLE**: political, economic, social, technological, legal, environmental forces
- **SWOT**: strengths, weaknesses, opportunities, threats
- **Competitive Positioning**: competitor clusters, positioning axes, and market share
- **Risk Heatmap**: probability, impact, mitigation owner, and time horizon

### 4. Plan Visuals

Market research reports should include key visual content. Plan 6 essential visuals at the start, then add only the visuals required by the report's actual sections.

Use the repository's available figure-generation or plotting approach for the current execution environment. Do not route to, invoke, or inline another skill from inside this skill document. Treat visual creation as part of this market-report deliverable, not as an auxiliary expert call.

Recommended starting visuals:

- Market growth trajectory chart
- TAM/SAM/SOM breakdown diagram
- Porter's Five Forces diagram
- Competitive positioning matrix
- Risk heatmap
- Executive summary infographic or dashboard

### 5. Draft the Report

Write insight-first prose. Each section should start with the conclusion, then support it with evidence, assumptions, and uncertainty. Avoid unsupported market-size claims and vague growth language.

### 6. Compile and Review

For LaTeX outputs, compile from the report project folder and verify that figures, references, tables, and page breaks render correctly. For Markdown outputs, verify internal links, table formatting, and image paths.

## Report Structure

### Front Matter

- Cover page
- Table of contents
- List of figures and tables if the report is long
- Executive summary

### Executive Summary

Include:

- Market snapshot
- Investment thesis or strategic answer
- Top findings
- Recommended actions
- Key uncertainties and evidence gaps

### Market Overview

Include:

- Market definition and boundaries
- Industry ecosystem
- Value chain
- Customer and buyer structure
- Historical development

### Market Size and Growth

Include:

- Current market size with source attribution
- Historical growth
- Forward projection with assumptions
- Regional and segment breakdowns
- TAM/SAM/SOM model where useful

### Competitive Landscape

Include:

- Market structure
- Major player profiles
- Market share or relative positioning
- Barriers to entry
- Competitive dynamics
- Positioning matrix when useful

### Drivers and Trends

Include:

- Technology shifts
- Regulatory and policy changes
- Customer behavior changes
- Macroeconomic factors
- Adoption barriers and catalysts

### Risks

Include:

- Market risks
- Competitive risks
- Regulatory risks
- Technology risks
- Operational risks
- Mitigation options

### Recommendations

Include:

- Prioritized strategic actions
- Rationale and evidence
- Expected benefits
- Dependencies
- Timeline and milestones
- Metrics for success

### Appendices

Include:

- Methodology
- Assumption table
- Data tables
- Source list
- Company profiles

## LaTeX Formatting

When producing a LaTeX report, start from `assets/market_report_template.tex` and include the bundled style package:

```latex
\documentclass[11pt,letterpaper]{report}
\usepackage{market_research}
```

Use boxed environments for executive summary findings, market snapshots, risks, and recommendations:

```latex
\begin{keyinsightbox}[Key Finding]
The market is projected to grow at 15.3\% CAGR through 2030 under the base-case assumptions.
\end{keyinsightbox}

\begin{marketdatabox}[Market Snapshot]
\begin{itemize}
    \item Market Size: \$45.2B
    \item Projected Size: \$98.7B
    \item CAGR: 15.3\%
\end{itemize}
\end{marketdatabox}

\begin{riskbox}[Critical Risk]
Regulatory changes could alter near-term adoption assumptions.
\end{riskbox}

\begin{recommendationbox}[Strategic Recommendation]
Prioritize the segment with the strongest growth, margin, and execution fit.
\end{recommendationbox}
```

Figure example:

```latex
\begin{figure}[htbp]
\centering
\includegraphics[width=0.9\textwidth]{../figures/market_growth.png}
\caption{Market Growth Trajectory. Source: report analysis and cited market data.}
\label{fig:market_growth}
\end{figure}
```

## Quality Standards

### Evidence Quality

- Every statistic has a source or is labeled as an assumption
- Projections state base-case assumptions and limitations
- Primary sources are preferred over secondary summaries
- Conflicting data is called out instead of silently averaged

### Visual Quality

- Charts answer a specific business question
- Axes, units, dates, and sources are labeled
- Colors are consistent and readable
- Figures are referenced in the text

### Writing Quality

- Lead with the answer
- Separate facts, assumptions, and recommendations
- Use specific numbers when defensible
- State uncertainty plainly
- Keep recommendations actionable

## Checklist

Before finalizing the report, verify:

- [ ] Scope and exclusions are explicit
- [ ] Executive summary answers the business question
- [ ] Market size and growth claims cite sources
- [ ] Competitive claims cite evidence
- [ ] Frameworks are used only where they add clarity
- [ ] Visuals render and are cited
- [ ] Recommendations include owner, timing, and evidence
- [ ] Bibliography or source list is complete
- [ ] PDF or Markdown output opens correctly

## Resources

Reference files:

- `references/report_structure_guide.md`: section-by-section content requirements
- `references/visual_generation_guide.md`: visual planning prompts and chart guidance
- `references/data_analysis_patterns.md`: templates for Porter's, PESTLE, SWOT, and related frameworks

Assets:

- `assets/market_research.sty`: LaTeX style package
- `assets/market_report_template.tex`: report template
- `assets/FORMATTING_GUIDE.md`: formatting reference

Script:

- `scripts/generate_market_visuals.py`: optional batch helper for standard market report visuals
