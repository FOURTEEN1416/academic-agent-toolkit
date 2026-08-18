---
name: openalex
user_invocable: true
description: Query and analyze scholarly literature using the OpenAlex API (240M+ works). Use for literature searches, finding papers by author/institution, citation analysis, and bibliometric queries.
---

# openalex — Scholarly Literature Search

Query the [OpenAlex](https://openalex.org) API for academic papers, authors, institutions, and citation data. No API key required.

## When to Use

- "find papers by", "search for papers on", "who cites this"
- Literature search, citation analysis, bibliometric queries
- Finding works by author, institution, or topic

## Client

```python
from scripts.openalex_client import OpenAlexClient

client = OpenAlexClient(email="user@example.edu")  # email → 10x rate limit
```

> Script paths are relative to this skill's directory.

The client handles rate limiting, retries with exponential backoff, and cursor-based pagination.

## Key Patterns

### Search works
```python
results = client.search_works(search="CRISPR", filter_params={"publication_year": ">2020", "is_oa": "true"}, sort="cited_by_count:desc")
```

### Two-step entity lookup (always get ID first, never filter by name)
```python
author = client.get("/authors", params={"search": "Jennifer Doudna", "per-page": 1})
author_id = author["results"][0]["id"].split("/")[-1]
works = client.search_works(filter_params={"authorships.author.id": author_id})
```

### Get entity by external ID
```python
work = client.get_entity("works", "https://doi.org/10.1038/s41586-021-03819-2")
author = client.get_entity("authors", "https://orcid.org/0000-0003-1613-5981")
```

### Batch DOI lookup (up to 50 per request)
```python
works = client.batch_lookup("works", doi_list, "doi")
```

### Paginate large results (cursor-based)
```python
all_papers = client.paginate_all("/works", params={"search": "quantum computing", "filter": "publication_year:2022-2024"}, max_results=5000)
```

### Aggregate by field
```python
by_year = client.group_by("works", "publication_year", filter_params={"authorships.author.id": author_id})
```

## Filter Syntax

```
Single:     publication_year:2023
AND:        publication_year:>2020,is_oa:true
OR:         type:journal-article|book
NOT:        type:!paratext
Range:      publication_year:2020-2024
Greater:    cited_by_count:>100
Both inst:  authorships.institutions.id:ID1+ID2    (AND)
Either:     authorships.institutions.id:ID1|ID2    (OR)
```

Common filters: `publication_year`, `is_oa`, `cited_by_count`, `type`, `authorships.author.id`, `authorships.institutions.id`, `primary_location.source.id`, `topics.id`, `has_doi`.

## Attribution

OpenAlex client adapted from [K-Dense-AI/claude-scientific-skills](https://github.com/K-Dense-AI/claude-scientific-skills) (MIT License).
