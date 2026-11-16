"""OpenAlex API client — thin, dependency-light wrapper over ``requests``.

Adapted from K-Dense-AI/claude-scientific-skills (MIT License); rebuilt here to
match this skill's SKILL.md contract (search / two-step entity lookup / batch
DOI lookup / cursor pagination / aggregation / filter syntax).

Usage (relative to this skill's directory)::

    from scripts.openalex_client import OpenAlexClient

    client = OpenAlexClient(email="user@example.edu")  # email -> polite pool (10x rate limit)
    results = client.search_works(search="CRISPR",
                                  filter_params={"publication_year": ">2020", "is_oa": "true"},
                                  sort="cited_by_count:desc")

The client handles rate limiting (polite ``mailto`` param), retries with
exponential backoff, and cursor-based pagination.
"""

from __future__ import annotations

import time
import urllib.parse
from typing import Any, Dict, Iterable, List, Optional

import requests

BASE_URL = "https://api.openalex.org"
MAX_BATCH = 50  # OpenAlex allows at most 50 OR-joined values per filter
DEFAULT_TIMEOUT = 30.0


def format_filter(filter_params: Dict[str, Any]) -> str:
    """Convert ``{"publication_year": ">2020", "is_oa": "true"}`` to
    ``"publication_year:>2020,is_oa:true"`` (OpenAlex filter syntax)."""
    return ",".join(f"{key}:{value}" for key, value in filter_params.items())


class OpenAlexClient:
    """Small requests-based client for the OpenAlex scholarly API."""

    def __init__(
        self,
        email: Optional[str] = None,
        max_retries: int = 3,
        backoff_seconds: float = 1.0,
        timeout: float = DEFAULT_TIMEOUT,
    ) -> None:
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "openalex-search-skill/1.0"})
        self.email = email
        self.max_retries = max_retries
        self.backoff_seconds = backoff_seconds
        self.timeout = timeout

    # ------------------------------------------------------------------ core
    def _params(self, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        merged = dict(params or {})
        if self.email:
            merged.setdefault("mailto", self.email)
        return merged

    def _request(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        url = path if path.startswith("http") else f"{BASE_URL}{path}"
        merged = self._params(params)
        last_exc: Optional[BaseException] = None
        for attempt in range(self.max_retries):
            try:
                resp = self.session.get(url, params=merged, timeout=self.timeout)
                # Rate-limited or transient server error -> retry with backoff.
                if resp.status_code == 429 or resp.status_code >= 500:
                    resp.raise_for_status()
                resp.raise_for_status()
                return resp.json()
            except (requests.RequestException, ValueError) as exc:
                last_exc = exc
                time.sleep(self.backoff_seconds * (2**attempt))
        assert last_exc is not None
        raise last_exc

    def get(self, path: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """GET any OpenAlex endpoint, e.g. ``client.get('/authors', params={'search': '...'})``."""
        return self._request(path, params)

    # --------------------------------------------------------------- helpers
    def get_entity(self, entity_type: str, entity_id: str) -> Dict[str, Any]:
        """Fetch one entity by OpenAlex ID or external ID (DOI URL, ORCID, ROR, ISSN).

        Example: ``client.get_entity('works', 'https://doi.org/10.1038/s41586-021-03819-2')``
        """
        if entity_id.startswith("http"):
            entity_id = urllib.parse.quote(entity_id, safe="")
        return self._request(f"/{entity_type}/{entity_id}")

    def search_works(
        self,
        search: Optional[str] = None,
        filter_params: Optional[Dict[str, Any]] = None,
        sort: Optional[str] = None,
        per_page: int = 25,
        **extra: Any,
    ) -> Dict[str, Any]:
        """Search works; ``filter_params`` uses OpenAlex filter syntax as a dict."""
        params: Dict[str, Any] = {"per-page": per_page}
        if search:
            params["search"] = search
        if filter_params:
            params["filter"] = format_filter(filter_params)
        if sort:
            params["sort"] = sort
        params.update(extra)
        return self.get("/works", params=params)

    def batch_lookup(
        self,
        entity_type: str,
        values: Iterable[str],
        id_field: str = "doi",
    ) -> Dict[str, Any]:
        """Look up up to 50 entities per request via an OR-joined filter
        (``filter=doi:10.1/aa|10.1/bb``). Larger inputs are chunked."""
        results: List[Dict[str, Any]] = []
        items = list(values)
        for start in range(0, len(items), MAX_BATCH):
            chunk = items[start : start + MAX_BATCH]
            filt = f"{id_field}:" + "|".join(chunk)
            data = self.get(f"/{entity_type}", params={"filter": filt, "per-page": MAX_BATCH})
            results.extend(data.get("results", []))
        return {"results": results}

    def paginate_all(
        self,
        path: str,
        params: Optional[Dict[str, Any]] = None,
        max_results: int = 10000,
    ) -> List[Dict[str, Any]]:
        """Cursor-based pagination over any list endpoint; stops at ``max_results``."""
        merged = dict(params or {})
        merged.setdefault("per-page", 200)
        merged["cursor"] = "*"
        collected: List[Dict[str, Any]] = []
        while len(collected) < max_results:
            data = self._request(path, merged)
            page = data.get("results", [])
            collected.extend(page)
            next_cursor = (data.get("meta") or {}).get("next_cursor")
            if not next_cursor or not page:
                break
            merged["cursor"] = next_cursor
        return collected[:max_results]

    def group_by(
        self,
        entity_type: str,
        field: str,
        filter_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Aggregate counts by a field, e.g. ``group_by('works', 'publication_year')``."""
        params: Dict[str, Any] = {"group_by": field}
        if filter_params:
            params["filter"] = format_filter(filter_params)
        return self.get(f"/{entity_type}", params=params)


__all__ = ["OpenAlexClient", "format_filter", "BASE_URL"]
