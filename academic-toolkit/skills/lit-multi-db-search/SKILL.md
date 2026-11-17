---
name: lit-multi-db-search
description: "Search 18 scholarly APIs (PubMed, PMC, Europe PMC, bioRxiv, medRxiv, arXiv, OpenAlex, Crossref, Semantic Scholar, CORE, Unpaywall, OpenCitations, PubTator3, Zenodo, Figshare, ROR, BioStudies, DOAJ) for papers, preprints, citations, open-access full text, repository records, journal OA status; reproducible provenance."
metadata:
  version: "1.1"
  skill-author: K-Dense Inc.
---


<!--ACAT-ADAPTED: 资产补齐自 K-Dense-AI/scientific-agent-skills@36d8f13a1e754618794bf42f417884940077b4ae（MIT，fork FOURTEEN1416）。上游 research-lookup/parallel-cli 等 API 依赖在本仓库不可直接运行，以执行侧 web_search/web_fetch 工具替代；溯源见 references/UPSTREAM.md。2026-09-09 专项治理。2026-11-16 重收编：融入上游 2d2065f（v2.72.0，目录已重组为 paper-lookup）增量——22 个参考件/脚本文件按上游补丁更新并新增 7 份数据库参考件（OpenCitations/PubTator3/Zenodo/Figshare/ROR/BioStudies/DOAJ），四个脚本 py_compile 通过；正文补"HTTP 200 也会说谎"危害清单、18 库选型与标识符表扩容、限速/重试纪律（Retry-After、只跨不同主机并行）。-->
# Paper Lookup

You have access to 18 scholarly APIs through their REST endpoints. Your job is to figure out which database(s) best serve the user's query, call them in a bounded and rate-limited way, and return results with enough provenance (endpoints, parameters, identifiers, access date) that the retrieval can be repeated.

## Core Workflow

1. **Understand the query** -- What is the user looking for? A specific paper by DOI? Papers on a topic? An author's publications? Open access PDFs? Full text? This determines which database(s) to hit.

2. **Select database(s)** -- Use the database selection guide below. Many queries benefit from hitting multiple databases -- for example, searching PubMed for papers and then checking Unpaywall for open access copies.

3. **Read the reference file** -- Each database has a reference file in `references/` with endpoint details, query formats, and example calls. Read the relevant file(s) before making API calls.

4. **Make the API call(s)** -- See the **Making API Calls** section below for which HTTP fetch tool to use on your platform.

5. **Return results** -- Always return:
   - The **raw JSON** (or parsed XML for arXiv) response from each database
   - A **list of databases queried** with the specific endpoints used
   - If a query returned no results, say so explicitly rather than omitting it

## Database Selection Guide

Match the user's intent to the right database(s).

### By Use Case

| User is asking about... | Primary database(s) | Also consider |
|---|---|---|
| Papers on a biomedical topic | PubMed | Semantic Scholar, OpenAlex |
| Full text of a biomedical article | PMC | CORE |
| Biology preprints | bioRxiv | Semantic Scholar, OpenAlex |
| Health/medical preprints | medRxiv | Semantic Scholar, OpenAlex |
| Physics, math, or CS preprints | arXiv | Semantic Scholar, OpenAlex |
| Papers across all fields | OpenAlex | Semantic Scholar, Crossref |
| A specific paper by DOI | Crossref | Unpaywall, Semantic Scholar |
| Open access PDF for a paper | Unpaywall | CORE, PMC |
| Citation graph (who cites whom) | Semantic Scholar | OpenAlex, Europe PMC, OpenCitations |
| Open citation edges / OCI | OpenCitations | Semantic Scholar, Europe PMC |
| Is this paper retracted? | Crossref (`update-type:retraction`, inspect `update-to`) | PubMed publication types / publisher notices |
| Genes/diseases/chemicals in a paper | PubTator3 | Europe PMC Annotations API |
| Institution / affiliation → ROR ID | ROR | OpenAlex (already-linked ROR) |
| Deposited dataset, software, or poster | Zenodo | Figshare, BioStudies |
| EBI study package / supplementary archive | BioStudies | Zenodo |
| Is this *journal* in DOAJ? | DOAJ | OpenAlex (`sources.is_in_doaj`) for the yes/no; Unpaywall (article-level OA) |
| Author's publications | Semantic Scholar | OpenAlex |
| Paper recommendations | Semantic Scholar | -- |
| Full text (any field) | CORE | PMC (biomedical only) |
| Journal/publisher metadata | Crossref | OpenAlex |
| Funder information | Crossref | OpenAlex |
| Convert between PMID/PMCID/DOI | PMC (ID Converter) | Crossref |
| Recent preprints by date | bioRxiv, medRxiv | arXiv |

### Cross-Database Queries

| User is asking about... | Databases to query |
|---|---|
| Everything about a paper (metadata + citations + OA) | Crossref + Semantic Scholar + Unpaywall |
| Comprehensive literature search | PubMed + OpenAlex + Semantic Scholar |
| Find and read a paper | PubMed (find) + Unpaywall (OA link) + PMC or CORE (full text) |
| Preprint and its published version | bioRxiv/medRxiv + Crossref |
| Author overview with citation metrics | Semantic Scholar + OpenAlex |

When a query spans multiple needs (e.g., "find papers about CRISPR and get me the PDFs"), query the relevant databases in parallel.

## Common Identifier Formats

Different databases use different identifier systems. If a query fails, the identifier format may be wrong.

| Identifier | Format | Example | Used by |
|---|---|---|---|
| DOI | `10.xxxx/xxxxx` | `10.1038/nature12373` | All databases |
| PMID | Integer | `34567890` | PubMed, PMC, Semantic Scholar |
| PMCID | `PMC` + digits | `PMC7029759` | PMC, Europe PMC |
| arXiv ID | `YYMM.NNNNN` or legacy `archive/YYMMNNN` | `2103.15348`, `hep-th/9901001` | arXiv, Semantic Scholar |
| OpenAlex ID | `W` + digits | `W2741809807` | OpenAlex |
| Semantic Scholar ID | 40-char hex | `649def34f8be...` | Semantic Scholar |
| ORCID | `0000-XXXX-XXXX-XXXX` | `0000-0001-6187-6610` | OpenAlex, Crossref |
| ISSN | `XXXX-XXXX` | `0028-0836` | Crossref, OpenAlex, DOAJ |
| ROR ID | `https://ror.org/` + 9 chars | `https://ror.org/05a0ya142` | ROR, OpenAlex, Crossref |
| OCI | `{citing}-{cited}` omid suffixes | `06101801781-06180334099` | OpenCitations |
| Zenodo record | integer; concept record ≠ version record | `3246411` (version of `3246410`) | Zenodo |
| BioStudies accession | `S-` / `E-` prefix | `S-BSST12345`, `E-MTAB-1234` | BioStudies |

**Cross-referencing IDs:** Semantic Scholar accepts DOI, PMID, PMCID, and arXiv ID via prefixes (e.g., `DOI:10.1038/nature12373`, `PMID:34567890`, `ARXIV:2103.15348`). OpenAlex accepts DOI and PMID via prefixes (`doi:10.1038/...`, `pmid:34567890`). Use the PMC ID Converter to translate between PMID, PMCID, and DOI.

## API Keys and Access

Most of these databases are fully open. A few benefit from API keys for higher rate limits.

### Databases requiring or benefiting from API keys

| Database | Env Variable | Required? | Registration |
|---|---|---|---|
| NCBI (PubMed, PMC) | `NCBI_API_KEY` | No (3 req/s without, 10 with) | https://www.ncbi.nlm.nih.gov/account/settings/ |
| CORE | `CORE_API_KEY` | Yes for full text | https://core.ac.uk/services/api |
| Semantic Scholar | `S2_API_KEY` | No (shared pool without) | https://www.semanticscholar.org/product/api#api-key-form |
| OpenAlex | `OPENALEX_API_KEY` | Recommended | https://openalex.org/settings/api |

### Fully open databases (no key needed)

| Database | Notes |
|---|---|
| bioRxiv / medRxiv | No auth, no documented rate limits |
| arXiv | No auth, max 1 request per 3 seconds |
| Crossref | No auth; add `mailto` param for polite pool (2x rate limit) |
| Unpaywall | No auth; requires `email` parameter |

### Loading API keys

1. **Check the environment first** -- the key may already be exported (e.g., `$NCBI_API_KEY`).
2. **Fall back to `.env`** -- check `.env` in the current working directory.
3. **Proceed without** -- most APIs still work at lower rate limits. Tell the user which key is missing and how to get one.

## Making API Calls

**⚠️ These APIs can fail with HTTP 200（上游 v2.72.0 增补的核心危害清单）.** Verify the *shape* of what you got, not just the status code:

- PMC eFetch returns a well-formed article with **no `<body>`** when the publisher forbids redistribution.
- arXiv returns `totalResults: 1` and one entry titled `Error` for a malformed parameter, and silently rewrites an unknown field prefix to `all:`.
- Europe PMC puts `errCode` in a 200 body.
- bioRxiv treats cursors as absolute offsets — an incorrect step silently skips records.
- Figshare `GET /articles?search_for=` ignores the query and still 200s.
- OpenCitations answers an unknown DOI with `[{"count": "0"}]`.

None of these raise; every one produces a confident, wrong answer. Check counts against the query, inspect returned titles/errors, and record the endpoint + parameters + access date as provenance.

Use your execution environment's HTTP fetch capability to call REST endpoints:

1. If a dedicated HTTP fetch tool is available, use it to call REST endpoints.
2. If there is none, use the current shell to run `curl -s <url>` (add `-H`/`--data` etc. as needed) and report failures honestly.
3. If the fetch tool fails, fall back to `curl` via whatever shell tool is available.

### Special cases

- **arXiv returns Atom XML**, not JSON. Parse it or use `curl` and extract the relevant fields. Consider piping through a simple parser if available.
- **PMC eFetch returns JATS XML** for full text. This is expected -- full text articles are in XML format.
- **Crossref and Unpaywall** benefit from including a `mailto` parameter or email for the polite/fast pool.

### Request guidelines

- For **NCBI APIs** (PubMed, PMC): max 3 req/sec without key, 10 with key. Make requests sequentially.
- For **arXiv**: max 1 request every 3 seconds. Be patient.
- For **Crossref** list queries: 1 req/sec public, 3 with `mailto`; single records 5/10. The bundled paginator conservatively uses 1 req/s.
- **PubTator3**: 3 req/s — serialize. **OpenCitations**: 180 req/min/IP. **Zenodo** public search: 30 req/min. **Figshare** public records: ~1 req/s. **ROR**: 2000 req / 5 min. **DOAJ** search: 2 req/s. **Unpaywall**: requires a real `email` parameter — placeholders like `test@example.com` are rejected with HTTP 422.
- **Parallelize across *different* open APIs only** (OpenAlex, Crossref, Semantic Scholar, Europe PMC, Unpaywall, OpenCitations, Zenodo, ROR, BioStudies, DOAJ may run concurrently); keep only a handful of requests in flight, and never parallelize against the same rate-limited host. Serialize PubTator3 and NCBI.
- On **HTTP 429/503**, honor `Retry-After` or service reset headers and retry once when allowed. A depleted daily budget needs a reset, not a short retry. Semantic Scholar without a key hits this often — one retry, then tell the user a key would help.

### Error recovery

1. **Check the identifier format** -- use the Common Identifier Formats table. A PMID won't work in arXiv, an arXiv ID won't work in PubMed directly.
2. **Try alternative identifiers** -- if a DOI fails in one database, try the title or PMID instead.
3. **Try a different database** -- if PubMed returns nothing for a CS paper, try Semantic Scholar or OpenAlex.
4. **Report the failure** -- tell the user which database failed, the error, and what you tried instead.

## Output Format

Structure your response like this:

```
## Databases Queried
- **PubMed** -- esearch + esummary for "CRISPR gene therapy"
- **Unpaywall** -- DOI lookup for 10.1038/...

## Results

### PubMed
[raw JSON response or formatted results]

### Unpaywall
[raw JSON response]
```

If results are very large, present the most relevant portion and note that more data is available. But default to showing the full raw JSON -- the user asked for it.

## Available Databases

Read the relevant reference file before making any API call.

### Biomedical Literature
| Database | Reference File | What it covers |
|---|---|---|
| PubMed | `references/pubmed.md` | 37M+ biomedical citations, abstracts, MeSH terms |
| PMC | `references/pmc.md` | 10M+ full-text biomedical articles (JATS XML), ID conversion |
| Europe PMC | `references/europepmc.md` | Biomedical literature with annotations API and citation data |

### Preprint Servers
| Database | Reference File | What it covers |
|---|---|---|
| bioRxiv | `references/biorxiv.md` | Biology preprints (browse by date/DOI, no keyword search) |
| medRxiv | `references/medrxiv.md` | Health sciences preprints (browse by date/DOI, no keyword search) |
| arXiv | `references/arxiv.md` | Physics, math, CS, biology, economics preprints (keyword search, Atom XML) |

### Multidisciplinary Indexes
| Database | Reference File | What it covers |
|---|---|---|
| OpenAlex | `references/openalex.md` | 250M+ works, authors, institutions, topics, citation data |
| Crossref | `references/crossref.md` | 150M+ DOI metadata, journals, funders, references |
| Semantic Scholar | `references/semantic-scholar.md` | 200M+ papers, citation graphs, AI-generated TLDRs, recommendations |

### Open Access & Full Text
| Database | Reference File | What it covers |
|---|---|---|
| CORE | `references/core.md` | 37M+ full texts from OA repositories worldwide |
| Unpaywall | `references/unpaywall.md` | OA status and PDF links for any DOI |

### Citations & Biomedical Entities（上游 v2.72.0 新增）
| Database | Reference File | What it covers |
|---|---|---|
| OpenCitations | `references/opencitations.md` | Open citation edges (OCI) between COCI-indexed papers |
| PubTator3 | `references/pubtator.md` | Genes/diseases/chemicals/species annotations for biomedical papers |

### Repositories, Registries & Directories（上游 v2.72.0 新增）
| Database | Reference File | What it covers |
|---|---|---|
| Zenodo | `references/zenodo.md` | Deposited datasets, software, posters; concept vs version records |
| Figshare | `references/figshare.md` | Institutional/repository research outputs |
| BioStudies | `references/biostudies.md` | EBI study packages and supplementary archives (`S-`/`E-` accessions) |
| ROR | `references/ror.md` | Institution/affiliation → stable ROR ID resolution |
| DOAJ | `references/doaj.md` | Journal-level open-access directory membership |

## Helper Scripts (in `scripts/`)

Deterministic helpers bundled with this skill (run from the repo root or this skill's directory):

| Script | Purpose |
|---|---|
| `_common.py` | Shared HTTP session, API-key loading, retry/rate-limit helpers |
| `arxiv_atom.py` | Parse arXiv Atom XML responses into structured records |
| `jats_to_text.py` | Convert PMC JATS XML full text to plain text |
| `openalex_abstract.py` | Rebuild abstract text from OpenAlex `abstract_inverted_index` |
| `paginate.py` | Cursor/page-based pagination helper for list endpoints |
