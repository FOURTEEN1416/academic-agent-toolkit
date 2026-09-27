# Search Strategies

Google Scholar and PubMed query construction: operators, field tags, MeSH terms,
date and publication-type filters, and worked query examples.

## Search Strategies

### Google Scholar Best Practices

**Finding Seminal and High-Impact Papers** (CRITICAL):

When ranking what to read and retrieve, prioritize papers based on citation count, venue quality, and author reputation. **These are retrieval-ranking heuristics, not validity proxies**: citation counts and prestige can guide which papers to pull, but evidence evaluation must check whether the cited source actually supports the claim — never substitute citation count or author/venue prestige for that support check.

**Citation Count Thresholds:**
| Paper Age | Citations | Classification |
|-----------|-----------|----------------|
| 0-3 years | 20+ | Noteworthy |
| 0-3 years | 100+ | Highly Influential |
| 3-7 years | 100+ | Significant |
| 3-7 years | 500+ | Landmark Paper |
| 7+ years | 500+ | Seminal Work |
| 7+ years | 1000+ | Foundational |

**Venue Quality Tiers:**
- **Tier 1 (Prefer):** Nature, Science, Cell, NEJM, Lancet, JAMA, PNAS
- **Tier 2 (High Priority):** Impact Factor >10, top conferences (NeurIPS, ICML, ICLR)
- **Tier 3 (Good):** Specialized journals (IF 5-10)
- **Tier 4 (Sparingly):** Lower-impact peer-reviewed venues

**Author Reputation Indicators:**
- Senior researchers with h-index >40
- Multiple publications in Tier-1 venues
- Leadership at recognized institutions
- Awards and editorial positions

**Search Strategies for High-Impact Papers:**
- Sort by citation count (most cited first)
- Look for review articles from Tier-1 journals for overview
- Check "Cited by" for impact assessment and recent follow-up work
- Use citation alerts for tracking new citations to key papers
- Filter by top venues using `source:Nature` or `source:Science`
- Search for papers by known field leaders using `author:LastName`

**Advanced Operators** (full list in `references/google_scholar_search.md`):
```
"exact phrase"           # Exact phrase matching
author:lastname          # Search by author
intitle:keyword          # Search in title only
source:journal           # Search specific journal
-exclude                 # Exclude terms
OR                       # Alternative terms
```

Year ranges are **not** query operators in Google Scholar — filter with the
script's `--year-start`/`--year-end` flags (or the web interface's custom range).

**Example Searches**:
```
# Find recent reviews on a topic (pair with --year-start 2023 --year-end 2024)
"CRISPR" intitle:review

# Find papers by specific author on topic
author:Church "synthetic biology"

# Find highly cited foundational work (sorting by citations is done via
# the script's --sort-by citations, not a query operator; pair with --year-start 2012 --year-end 2015)
"deep learning"

# Exclude surveys and focus on methods
"protein folding" -survey -review intitle:method
```

### PubMed Best Practices

**Using MeSH Terms**:
MeSH (Medical Subject Headings) provides controlled vocabulary for precise searching.

1. **Find MeSH terms** at https://meshb.nlm.nih.gov/search
2. **Use in queries**: `"Diabetes Mellitus, Type 2"[MeSH]`
3. **Combine with keywords** for comprehensive coverage

**Field Tags**:
```
[Title]              # Search in title only
[Title/Abstract]     # Search in title or abstract
[Author]             # Search by author name
[Journal]            # Search specific journal
[Publication Date]   # Date range
[Publication Type]   # Article type
[MeSH]              # MeSH term
```

**Building Complex Queries**:
```bash
# Clinical trials on diabetes treatment published recently
"Diabetes Mellitus, Type 2"[MeSH] AND "Drug Therapy"[MeSH] 
AND "Clinical Trial"[Publication Type] AND 2020:2024[Publication Date]

# Reviews on CRISPR in specific journal
"CRISPR-Cas Systems"[MeSH] AND "Nature"[Journal] AND "Review"[Publication Type]

# Specific author's recent work
"Smith AB"[Author] AND cancer[Title/Abstract] AND 2022:2024[Publication Date]
```

**E-utilities for Automation**:
The scripts use NCBI E-utilities API for programmatic access:
- **ESearch**: Search and retrieve PMIDs
- **EFetch**: Retrieve full metadata
- **ESummary**: Get summary information
- **ELink**: Find related articles

See `references/pubmed_search.md` for complete API documentation.
