#!/usr/bin/env python3
"""学术文献搜索与 BibTeX 获取工具 — AMiner + Semantic Scholar + CrossRef + DBLP 四级 fallback。

用法：
    python scholar_fetch.py search "attention mechanism" --max 5
    python scholar_fetch.py search "Vaswani attention is all you need" --max 3
    python scholar_fetch.py bibtex "attention is all you need" --max 5
    python scholar_fetch.py bibtex-doi "10.1145/3292500.3330919"
    python scholar_fetch.py bibtex-id "S2:204e3073870fae3d05bcbc2f6a8e263d9b72e776"

四个 API：
- AMiner（论文问答搜索）：中文学术场景最佳，支持自然语言查询 + 联合关键词，返回真实论文 ID
- Semantic Scholar：学术搜索，返回标题/作者/年份/DOI/摘要/引用数
- CrossRef：通过 DOI 获取权威 BibTeX
- DBLP：CS 领域最权威的 BibTeX 来源

搜索策略：
1. 优先用 AMiner 搜索（中文场景最准，返回真实论文）
2. AMiner 无结果时 fallback 到 Semantic Scholar
3. 对每个结果，优先从 DBLP 获取 BibTeX（最干净）
4. DBLP 失败则用 CrossRef DOI 获取 BibTeX
5. 都失败则从元数据自动生成 BibTeX
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Optional

_USER_AGENT = "MHAgent-ScholarFetch/1.0 (academic research tool)"
_TIMEOUT = 15  # 单次请求超时秒数
_RATE_DELAY = 0.3  # 请求间隔（秒），避免被限流

# 使用系统证书存储验证 HTTPS 连接。证书问题应由运行环境修复，不能绕过验证。
import ssl as _ssl


# ============================================================
# 通用 HTTP 工具
# ============================================================

_MAX_RETRIES = 3  # API 调用失败时最多重试次数
_RETRY_DELAY = 1.0  # 重试间隔（秒）


def _http_get(url: str, headers: Optional[dict] = None, timeout: int = _TIMEOUT) -> Optional[str]:
    """发送经证书验证的 GET 请求，返回响应文本。失败返回 None。"""
    hdrs = {"User-Agent": _USER_AGENT}
    if headers:
        hdrs.update(headers)
    req = urllib.request.Request(url, headers=hdrs)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (_ssl.SSLError, urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        _log(f"HTTP GET failed: {url} -> {e}")
        return None


def _http_post(url: str, body: dict, headers: Optional[dict] = None, timeout: int = _TIMEOUT) -> Optional[str]:
    """发送经证书验证的 POST 请求，返回响应文本。失败返回 None。"""
    hdrs = {"User-Agent": _USER_AGENT, "Content-Type": "application/json"}
    if headers:
        hdrs.update(headers)
    data = json.dumps(body, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=hdrs, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except (_ssl.SSLError, urllib.error.URLError, urllib.error.HTTPError, OSError, TimeoutError) as e:
        _log(f"HTTP POST failed: {url} -> {e}")
        return None


def _log(msg: str):
    """输出日志到 stderr（不干扰 stdout 的 JSON 输出）。"""
    print(f"[scholar_fetch] {msg}", file=sys.stderr)


# ============================================================
# AMiner 论文问答搜索 API（最高优先级）
# ============================================================

# AMiner is optional. Configure AMINER_API_KEY explicitly to enable it.
_AMINER_API_KEY = os.environ.get("AMINER_API_KEY", "").strip()
_AMINER_BASE_URL = os.environ.get("AMINER_BASE_URL", "https://datacenter.aminer.cn")


def aminer_search(query: str, max_results: int = 10, sci_only: bool = False,
                  year_range: Optional[list] = None) -> list[dict]:
    """AMiner 搜索入口：使用免费的论文搜索 API（$0/次）。
    
    API: GET /api/paper/search?page=1&size=N&title=QUERY
    返回 first_author、title、venue_name、year、doi、n_citation_bucket。
    
    搜索后用论文信息 API（$0/次）补全前 5 篇的完整作者列表。
    内置 3 次重试机制，网络波动时自动重试。
    """
    if not _AMINER_API_KEY:
        return []
    
    # 带重试的免费搜索（最多 3 次）
    results = []
    for _retry in range(_MAX_RETRIES):
        results = _aminer_free_search(query, max_results)
        if results:
            break
        if _retry < _MAX_RETRIES - 1:
            _log(f"AMiner free search returned 0, retrying ({_retry + 2}/{_MAX_RETRIES})...")
            time.sleep(_RETRY_DELAY)
    
    # 免费 API 3 次都失败时 fallback 到 qa/search（$0.008/次，也带重试）
    if not results:
        _has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
        if _has_chinese:
            for _retry in range(2):  # qa/search 最多重试 2 次（要花钱）
                results = _aminer_qa_search(query, max_results)
                if results:
                    break
                time.sleep(_RETRY_DELAY)
    
    # 用论文信息 API 补全完整作者列表（$0/次，只补前 5 篇）
    _enrich_count = min(len(results), 5)
    if _enrich_count > 0:
        _log(f"Enriching top {_enrich_count} results via paper detail API...")
        for paper in results[:_enrich_count]:
            aminer_id = paper.get("aminer_id", "")
            if not aminer_id:
                continue
            if len(paper["authors"]) <= 1:
                try:
                    detail = _aminer_paper_detail(aminer_id)
                    if detail:
                        if detail.get("authors"):
                            paper["authors"] = detail["authors"]
                        if not paper["year"] and detail.get("year"):
                            paper["year"] = detail["year"]
                        if not paper["abstract"] and detail.get("abstract"):
                            paper["abstract"] = detail["abstract"]
                        if not paper["doi"] and detail.get("doi"):
                            paper["doi"] = detail["doi"]
                    time.sleep(_RATE_DELAY)
                except Exception:
                    pass
    
    _log(f"AMiner returned {len(results)} results for: {query[:50]}")
    return results


def _aminer_free_search(query: str, max_results: int = 10) -> list[dict]:
    """AMiner 免费论文搜索（$0/次）。用 title 参数搜索，中英文都支持。

    ⛔ 中文 query 选词策略 (修复历史 bug):
    - 之前用 max(words, key=len) 按字节长度选, 让 5 字节英文 "TOPSIS" 输给 12 字节
      "综合评价"; 但用户搜 "TOPSIS 综合评价" 时英文术语反而是核心主题
    - AMiner title 参数实测: 多个空格分隔的实词搜不到, 单实词搜得到
    - 改为: 先用单一最长实词搜, 命中即返回; 命中空时降级试 query[:20]
    """
    # 对中文 query 提取核心关键词（去掉"基于""的""与"等虚词）
    _has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    if _has_chinese:
        # 按虚词切分, 提取实词
        parts = re.split(r'[,，\s]+|(?:基于|通过|利用|采用|进行|的|与|和|及|对|在|应用)', query)
        words = [w.strip() for w in parts if w.strip() and len(w.strip()) >= 2]
        # 优先用最长实词 (单词搜索 AMiner 命中率更高)
        if words:
            search_title = max(words, key=len)
        else:
            search_title = query[:20]
    else:
        search_title = query

    def _do_search(title_param: str) -> Optional[list]:
        params = {
            "page": 1,
            "size": min(max_results, 20),
            "title": title_param,
        }
        qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
        url = f"{_AMINER_BASE_URL}/gateway/open_platform/api/paper/search?{qs}"
        headers = {"Authorization": _AMINER_API_KEY}

        text = _http_get(url, headers=headers, timeout=15)
        if not text:
            return None
        try:
            resp = json.loads(text)
        except json.JSONDecodeError:
            return None
        if resp.get("code") != 200:
            _log(f"AMiner free search error: code={resp.get('code')} msg={resp.get('msg', '')[:80]}")
            return None
        papers = resp.get("data") or []
        return papers if isinstance(papers, list) else []

    papers = _do_search(search_title)
    # 命中空 + 中文 + 还有其他实词 → 试每个实词一次, 选第一个有结果的
    if (not papers) and _has_chinese and words and len(words) > 1:
        for fallback_word in sorted(set(words) - {search_title}, key=len, reverse=True):
            _log(f"AMiner free search retry with fallback word: {fallback_word}")
            papers = _do_search(fallback_word)
            if papers:
                break

    if papers is None or not papers:
        return []

    results = []
    for p in papers:
        title = (p.get("title_zh") or p.get("title") or "").strip()
        if not title:
            continue
        
        first_author = (p.get("first_author") or "").strip()
        authors = [first_author] if first_author else []
        venue = (p.get("venue_name") or "").strip()
        doi = (p.get("doi") or "").strip()
        year = p.get("year")
        citation_count = 0
        bucket = p.get("n_citation_bucket") or ""
        if bucket:
            parts = bucket.replace("+", "").split("-")
            try:
                citation_count = int(parts[0])
            except (ValueError, IndexError):
                pass
        
        results.append({
            "source": "aminer",
            "aminer_id": p.get("id", ""),
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "arxiv_id": "",
            "dblp_id": "",
            "venue": venue,
            "citation_count": citation_count,
            "abstract": (p.get("abstract") or "")[:500],
        })
    
    return results


def _aminer_search_pro(query: str, max_results: int = 10) -> list[dict]:
    """AMiner 论文搜索 Pro（$0.002/次）。备用，当免费 API 不够用时。"""
    params = {"size": min(max_results, 20), "page": 0, "keyword": query}
    qs = urllib.parse.urlencode(params, quote_via=urllib.parse.quote)
    url = f"{_AMINER_BASE_URL}/gateway/open_platform/api/paper/search/pro?{qs}"
    headers = {"Authorization": _AMINER_API_KEY}
    
    text = _http_get(url, headers=headers, timeout=15)
    if not text:
        return []
    
    try:
        resp = json.loads(text)
    except json.JSONDecodeError:
        return []
    
    if resp.get("code") != 200:
        return []
    
    papers = resp.get("data") or []
    if not isinstance(papers, list):
        return []
    
    results = []
    for p in papers:
        title = (p.get("title_zh") or p.get("title") or "").strip()
        if not title:
            continue
        
        first_author = (p.get("first_author") or "").strip()
        authors = [first_author] if first_author else []
        venue = (p.get("venue_name") or "").strip()
        doi = (p.get("doi") or "").strip()
        year = p.get("year")
        citation_count = 0
        bucket = p.get("n_citation_bucket") or ""
        if bucket:
            parts = bucket.replace("+", "").split("-")
            try:
                citation_count = int(parts[0])
            except (ValueError, IndexError):
                pass
        
        results.append({
            "source": "aminer",
            "aminer_id": p.get("id", ""),
            "title": title,
            "authors": authors,
            "year": year,
            "doi": doi,
            "arxiv_id": "",
            "dblp_id": "",
            "venue": venue,
            "citation_count": citation_count,
            "abstract": (p.get("abstract") or "")[:500],
        })
    
    return results


def _aminer_qa_search(query: str, max_results: int = 10) -> list[dict]:
    """AMiner 论文问答搜索（fallback，$0.008/次）。当 search/pro 失败时使用。"""
    url = f"{_AMINER_BASE_URL}/gateway/open_platform/api/paper/qa/search"
    
    keywords = [w.strip() for w in re.split(r'[,，\s]+', query) if w.strip()]
    topic_high = json.dumps([keywords[:5]], ensure_ascii=False)
    
    body = {
        "query": query,
        "use_topic": True,
        "topic_high": topic_high,
        "size": min(max_results, 20),
        "offset": 0,
        "n_citation_flag": True,
    }
    headers = {"Authorization": _AMINER_API_KEY}
    
    text = _http_post(url, body, headers=headers, timeout=20)
    if not text:
        return []
    
    try:
        resp = json.loads(text)
    except json.JSONDecodeError:
        return []
    
    if not resp.get("success") or resp.get("code") != 200:
        return []
    
    papers = resp.get("data", [])
    results = []
    for p in papers:
        title = (p.get("title_zh") or p.get("title") or "").strip()
        doi = (p.get("doi") or "").strip()
        if not title and not doi:
            continue
        results.append({
            "source": "aminer",
            "aminer_id": p.get("id", ""),
            "title": title,
            "authors": [],
            "year": p.get("year"),
            "doi": doi,
            "arxiv_id": "",
            "dblp_id": "",
            "venue": (p.get("venue") or "").strip(),
            "citation_count": 0,
            "abstract": "",
        })
    return results


def _aminer_paper_detail(paper_id: str) -> Optional[dict]:
    """通过 AMiner 论文信息 API 获取完整信息（authors/year/abstract/venue）。
    
    POST /api/paper/info  body: {"ids": ["xxx"]}
    费用：$0/次（免费！）
    """
    if not _AMINER_API_KEY:
        return None
    
    url = f"{_AMINER_BASE_URL}/gateway/open_platform/api/paper/info"
    headers = {"Authorization": _AMINER_API_KEY}
    body = {"ids": [paper_id]}
    
    text = _http_post(url, body, headers=headers, timeout=15)
    if not text:
        return None
    
    try:
        resp = json.loads(text)
    except json.JSONDecodeError:
        return None
    
    if resp.get("code") != 200 or not resp.get("data"):
        return None
    
    papers = resp.get("data", [])
    if not papers:
        return None
    
    p = papers[0] if isinstance(papers, list) else papers
    
    # 提取作者（优先中文名）
    authors = []
    for a in (p.get("authors") or []):
        name = a.get("name_zh") or a.get("name") or ""
        if name:
            authors.append(name)
    
    # 提取年份
    year = p.get("year")
    
    # 提取期刊/会议
    venue_raw = p.get("venue") or p.get("venue_name") or ""
    if isinstance(venue_raw, dict):
        venue = (venue_raw.get("name") or venue_raw.get("name_zh") or venue_raw.get("raw") or "").strip()
    else:
        venue = str(venue_raw).strip()
    
    # 提取摘要（优先中文）
    abstract = (p.get("abstract_zh_slice") or p.get("abstract_slice") or p.get("abstract_zh") or p.get("abstract") or "")[:500]
    
    # DOI
    doi = (p.get("doi") or "").strip()
    
    return {
        "authors": authors,
        "year": year,
        "venue": venue,
        "abstract": abstract,
        "doi": doi,
    }


# ============================================================
# Semantic Scholar API
# ============================================================

def semantic_scholar_search(query: str, max_results: int = 5) -> list[dict]:
    """搜索 Semantic Scholar，返回论文列表。
    
    API 文档: https://api.semanticscholar.org/api-docs/graph
    免费限额: 100 次/5分钟（无 key），1000 次/5分钟（有 key）
    """
    fields = "title,authors,year,externalIds,abstract,citationCount,venue,publicationTypes,journal"
    params = urllib.parse.urlencode({
        "query": query,
        "limit": min(max_results, 20),
        "fields": fields,
    })
    url = f"https://api.semanticscholar.org/graph/v1/paper/search?{params}"
    
    text = _http_get(url)
    if not text:
        return []
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        _log(f"S2 JSON parse error: {text[:200]}")
        return []
    
    papers = data.get("data", [])
    results = []
    for p in papers:
        ext_ids = p.get("externalIds") or {}
        authors_raw = p.get("authors") or []
        authors = [a.get("name", "") for a in authors_raw if a.get("name")]
        
        result = {
            "source": "semantic_scholar",
            "s2_id": p.get("paperId", ""),
            "title": (p.get("title") or "").strip(),
            "authors": authors,
            "year": p.get("year"),
            "doi": ext_ids.get("DOI", ""),
            "arxiv_id": ext_ids.get("ArXiv", ""),
            "dblp_id": ext_ids.get("DBLP", ""),
            "venue": (p.get("venue") or "").strip(),
            "citation_count": p.get("citationCount", 0),
            "abstract": (p.get("abstract") or "")[:500],
        }
        # 从 journal 字段补充 venue
        if not result["venue"] and p.get("journal"):
            result["venue"] = (p["journal"].get("name") or "").strip()
        results.append(result)
    
    return results


def semantic_scholar_by_id(paper_id: str) -> Optional[dict]:
    """通过 Semantic Scholar Paper ID / DOI / ArXiv ID 获取单篇论文详情。
    
    支持的 ID 格式:
    - S2 Paper ID: "204e3073870fae3d05bcbc2f6a8e263d9b72e776"
    - DOI: "DOI:10.1145/xxx" 或 "10.1145/xxx"
    - ArXiv: "ArXiv:2301.07041" 或 "ARXIV:2301.07041"
    - DBLP: "DBLP:conf/nips/VaswaniSPUJGKP17"
    """
    fields = "title,authors,year,externalIds,abstract,citationCount,venue,journal,publicationTypes"
    # 自动加前缀
    if re.match(r"^10\.\d{4,}/", paper_id):
        paper_id = f"DOI:{paper_id}"
    elif re.match(r"^\d{4}\.\d{4,5}", paper_id):
        paper_id = f"ARXIV:{paper_id}"
    
    url = f"https://api.semanticscholar.org/graph/v1/paper/{urllib.parse.quote(paper_id, safe='')}?fields={fields}"
    text = _http_get(url)
    if not text:
        return None
    
    try:
        p = json.loads(text)
    except json.JSONDecodeError:
        return None
    
    if "error" in p or not p.get("paperId"):
        return None
    
    ext_ids = p.get("externalIds") or {}
    authors_raw = p.get("authors") or []
    authors = [a.get("name", "") for a in authors_raw if a.get("name")]
    
    result = {
        "source": "semantic_scholar",
        "s2_id": p.get("paperId", ""),
        "title": (p.get("title") or "").strip(),
        "authors": authors,
        "year": p.get("year"),
        "doi": ext_ids.get("DOI", ""),
        "arxiv_id": ext_ids.get("ArXiv", ""),
        "dblp_id": ext_ids.get("DBLP", ""),
        "venue": (p.get("venue") or "").strip(),
        "citation_count": p.get("citationCount", 0),
        "abstract": (p.get("abstract") or "")[:500],
    }
    if not result["venue"] and p.get("journal"):
        result["venue"] = (p["journal"].get("name") or "").strip()
    return result



# ============================================================
# CrossRef API（通过 DOI 获取 BibTeX）
# ============================================================

def crossref_bibtex_by_doi(doi: str) -> Optional[str]:
    """通过 DOI 从 CrossRef 获取 BibTeX。这是最权威的 BibTeX 来源之一。
    
    使用 content negotiation: Accept: application/x-bibtex
    """
    if not doi:
        return None
    
    url = f"https://doi.org/{urllib.parse.quote(doi, safe='/:')}"
    text = _http_get(url, headers={"Accept": "application/x-bibtex"})
    if text and text.strip().startswith("@"):
        return text.strip()
    return None


def crossref_search(query: str, max_results: int = 5) -> list[dict]:
    """搜索 CrossRef，返回论文列表。
    
    API 文档: https://api.crossref.org/swagger-ui/index.html
    """
    params = urllib.parse.urlencode({
        "query": query,
        "rows": min(max_results, 20),
        "select": "DOI,title,author,published-print,published-online,container-title,type",
    })
    url = f"https://api.crossref.org/works?{params}"
    
    text = _http_get(url)
    if not text:
        return []
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    
    items = data.get("message", {}).get("items", [])
    results = []
    for item in items:
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        
        authors_raw = item.get("author", [])
        authors = []
        for a in authors_raw:
            given = a.get("given", "")
            family = a.get("family", "")
            if family:
                authors.append(f"{given} {family}".strip())
        
        # 提取年份
        year = None
        for date_field in ["published-print", "published-online"]:
            date_parts = item.get(date_field, {}).get("date-parts", [[]])
            if date_parts and date_parts[0] and date_parts[0][0]:
                year = date_parts[0][0]
                break
        
        venue_list = item.get("container-title", [])
        venue = venue_list[0] if venue_list else ""
        
        results.append({
            "source": "crossref",
            "doi": item.get("DOI", ""),
            "title": title.strip(),
            "authors": authors,
            "year": year,
            "venue": venue.strip(),
            "type": item.get("type", ""),
        })
    
    return results


def openalex_search(query: str, max_results: int = 5) -> list[dict]:
    """搜索 OpenAlex（2.5亿+ 论文，免费无 Key，人文社科/多语种/中文覆盖最广）。

    作为 AMiner/S2/DBLP/CrossRef 全部无结果时的兜底源，降低"搜不到→编造文献"的概率。
    API 文档: https://docs.openalex.org/  返回真实 DOI，后续 BibTeX 仍走 CrossRef DOI。
    """
    params = urllib.parse.urlencode({
        "search": query,
        "per_page": min(max(max_results, 1), 25),
        "sort": "relevance_score:desc",
    })
    url = f"https://api.openalex.org/works?{params}"
    # mailto 进入 polite pool（更稳定），不暴露真实邮箱
    text = _http_get(url, headers={"User-Agent": "modex-scholar/1.0 (mailto:support@modex.local)"})
    if not text:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    results = []
    for item in (data.get("results") or [])[:max_results]:
        title = (item.get("title") or "").strip()
        if not title:
            continue
        authors = []
        for a in (item.get("authorships") or []):
            name = ((a.get("author") or {}).get("display_name") or "").strip()
            if name:
                authors.append(name)
        year = item.get("publication_year") or None
        doi = item.get("doi") or ""
        if doi.startswith("https://doi.org/"):
            doi = doi[len("https://doi.org/"):]
        venue = ""
        ploc = item.get("primary_location") or {}
        src = ploc.get("source") or {}
        venue = (src.get("display_name") or "").strip()
        results.append({
            "source": "openalex",
            "doi": doi,
            "title": title,
            "authors": authors,
            "year": year,
            "venue": venue,
            "citation_count": item.get("cited_by_count") or 0,
            "type": (item.get("type") or ""),
        })
    return results


# ============================================================
# DBLP API（CS 领域最权威的 BibTeX）
# ============================================================

def dblp_search(query: str, max_results: int = 5) -> list[dict]:
    """搜索 DBLP，返回论文列表。
    
    API 文档: https://dblp.org/faq/How+to+use+the+dblp+search+API.html
    """
    params = urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "h": min(max_results, 20),
    })
    url = f"https://dblp.org/search/publ/api?{params}"
    
    text = _http_get(url)
    if not text:
        return []
    
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []
    
    hits = data.get("result", {}).get("hits", {}).get("hit", [])
    results = []
    for hit in hits:
        info = hit.get("info", {})
        
        # DBLP 的 authors 可能是 dict 或 list
        authors_raw = info.get("authors", {}).get("author", [])
        if isinstance(authors_raw, dict):
            authors_raw = [authors_raw]
        authors = []
        for a in authors_raw:
            if isinstance(a, dict):
                authors.append(a.get("text", ""))
            elif isinstance(a, str):
                authors.append(a)
        
        results.append({
            "source": "dblp",
            "dblp_key": info.get("key", ""),
            "title": (info.get("title") or "").strip().rstrip("."),
            "authors": authors,
            "year": int(info["year"]) if info.get("year", "").isdigit() else None,
            "venue": (info.get("venue") or "").strip(),
            "doi": (info.get("doi") or "").strip(),
            "url": (info.get("url") or "").strip(),
            "type": (info.get("type") or "").strip(),
        })
    
    return results


def dblp_bibtex(dblp_key: str) -> Optional[str]:
    """通过 DBLP key 获取 BibTeX。
    
    例如: dblp_key = "conf/nips/VaswaniSPUJGKP17"
    """
    if not dblp_key:
        return None
    
    # 确保 key 格式正确
    key = dblp_key.strip()
    if key.startswith("DBLP:"):
        key = key[5:]
    
    url = f"https://dblp.org/rec/{key}.bib"
    text = _http_get(url)
    if text and text.strip().startswith("@"):
        return text.strip()
    return None


def dblp_search_bibtex(query: str, original_title: str = "") -> Optional[str]:
    """搜索 DBLP 并返回第一个匹配结果的 BibTeX。

    ⛔ 严格相似度过滤 (修复历史 Bug):
    - DBLP 几乎不索引中文期刊, 中文 query 必然误匹配 EN 论文 → 直接拒绝
    - 即使 EN query, 也要求结果标题与 original_title 有合理相似度 (>= 0.4)
    - 防止 DBLP 模糊匹配命中无关文章 (如中文标题 → 完全不相关的 EN 论文)
    """
    # 中文 query → DBLP 没有中文索引, 直接放弃
    if re.search(r'[\u4e00-\u9fff]', query):
        return None

    results = dblp_search(query, max_results=3)  # 取 3 个候选, 再做相似度筛选
    if not results:
        return None

    # 用 original_title (或 query) 做相似度校验
    target = original_title or query
    best = None
    best_score = 0.0
    for r in results:
        if not r.get("title"):
            continue
        score = _compute_match_score(target, r.get("title", ""), r.get("authors") or [])
        if score > best_score:
            best_score = score
            best = r

    # 严格阈值: ≥ 0.4 (good=0.6, partial=0.3, 这里取中间值平衡召回/精度)
    if best is None or best_score < 0.4:
        return None

    key = best.get("dblp_key", "")
    if key:
        return dblp_bibtex(key)
    return None


# ============================================================
# 智能 BibTeX 获取（三级 fallback）
# ============================================================

def _make_citation_key(authors: list[str], year, title: str) -> str:
    """生成 BibTeX citation key: firstauthor_year_keyword"""
    # 第一作者姓氏
    first_author = ""
    if authors:
        name = authors[0]
        # 处理 "Last, First" 和 "First Last" 两种格式
        if "," in name:
            first_author = name.split(",")[0].strip()
        else:
            parts = name.split()
            first_author = parts[-1] if parts else "unknown"
    first_author = re.sub(r"[^a-zA-Z]", "", first_author).lower() or "unknown"
    
    # 年份
    yr = str(year) if year else "xxxx"
    
    # 标题关键词（取第一个有意义的词）
    stop_words = {"a", "an", "the", "of", "for", "and", "in", "on", "to", "with", "is", "are", "by"}
    words = re.findall(r"[a-zA-Z]+", title.lower())
    keyword = ""
    for w in words:
        if w not in stop_words and len(w) > 2:
            keyword = w
            break
    keyword = keyword or "paper"
    
    return f"{first_author}_{yr}_{keyword}"


def _compute_match_score(query: str, title: str, authors: list[str] = None) -> float:
    """计算搜索查询和返回结果的匹配度（0.0-1.0）。

    用于检测搜索结果是否真的是用户想要的论文，防止"标题相近但实际不同"的假匹配。

    策略 (修复中文不打分 Bug):
    - 英文: 词级 Jaccard + query 覆盖率
    - 中文: 字符级 2-gram Jaccard (中文按空格 tokenize 不可靠)
    - 中英混合: 取 max(中文 score, 英文 score)
    - 作者姓氏匹配加分
    """
    import re

    if not query or not title:
        return 0.0

    q_has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    t_has_chinese = bool(re.search(r'[\u4e00-\u9fff]', title))

    score = 0.0

    # 英文分数 (永远计算, 中英混合也用得上)
    def tokenize(text: str) -> set[str]:
        text = text.lower().strip()
        tokens = re.split(r'[\s_\-:,;.(){}]+', text)
        return {t for t in tokens if len(t) >= 2 and not t.isdigit()}

    q_tokens = tokenize(query)
    t_tokens = tokenize(title)

    if q_tokens and t_tokens:
        intersection = q_tokens & t_tokens
        union = q_tokens | t_tokens
        jaccard = len(intersection) / len(union) if union else 0.0
        query_coverage = len(intersection) / len(q_tokens) if q_tokens else 0.0
        score = 0.4 * jaccard + 0.6 * query_coverage

    # 中文分数 (中文按 2-gram 字符匹配)
    if q_has_chinese or t_has_chinese:
        def cn_chars(text: str) -> str:
            return ''.join(re.findall(r'[\u4e00-\u9fffA-Za-z0-9]', text.lower()))

        def bigrams(s: str) -> set[str]:
            return {s[i:i+2] for i in range(len(s) - 1)} if len(s) >= 2 else set()

        q_cn = cn_chars(query)
        t_cn = cn_chars(title)
        q_bg = bigrams(q_cn)
        t_bg = bigrams(t_cn)
        if q_bg and t_bg:
            inter_bg = q_bg & t_bg
            union_bg = q_bg | t_bg
            jaccard_cn = len(inter_bg) / len(union_bg) if union_bg else 0.0
            cov_cn = len(inter_bg) / len(q_bg) if q_bg else 0.0
            cn_score = 0.4 * jaccard_cn + 0.6 * cov_cn
            score = max(score, cn_score)

    # 作者匹配加分
    if authors:
        q_lower = query.lower()
        for author in authors:
            surname = author.strip().split()[-1].lower() if author.strip() else ""
            if surname and len(surname) >= 2 and surname in q_lower:
                score = min(1.0, score + 0.15)
                break

    return round(min(1.0, score), 3)


def _match_label(score: float) -> str:
    """根据匹配度分数返回标签。"""
    if score >= 0.6:
        return "good"
    elif score >= 0.3:
        return "partial"
    else:
        return "low"


def _escape_bibtex(text: str) -> str:
    """转义 BibTeX 特殊字符。"""
    # 保留已有的 LaTeX 命令（如 {\"u}）
    text = text.replace("&", r"\&")
    text = text.replace("%", r"\%")
    text = text.replace("#", r"\#")
    return text


def _generate_bibtex_from_metadata(paper: dict) -> str:
    """从元数据自动生成 BibTeX（最后的 fallback）。"""
    authors = paper.get("authors", [])
    title = paper.get("title", "Unknown Title")
    year = paper.get("year", "")
    doi = paper.get("doi", "")
    venue = paper.get("venue", "")
    arxiv_id = paper.get("arxiv_id", "")
    
    key = _make_citation_key(authors, year, title)
    author_str = " and ".join(authors) if authors else "Unknown"
    
    # 判断类型
    if arxiv_id and not venue:
        # arXiv 预印本
        lines = [
            f"@misc{{{key},",
            f"  title = {{{_escape_bibtex(title)}}},",
            f"  author = {{{_escape_bibtex(author_str)}}},",
            f"  year = {{{year}}},",
            f"  eprint = {{{arxiv_id}}},",
            f"  archiveprefix = {{arXiv}},",
        ]
        if doi:
            lines.append(f"  doi = {{{doi}}},")
        lines.append(f"  note = {{[AUTO-GENERATED] Verify before submission}}")
        lines.append("}")
    elif venue:
        # 有 venue，判断是会议还是期刊
        conf_keywords = {"conference", "proceedings", "workshop", "symposium",
                         "ICML", "NeurIPS", "ICLR", "AAAI", "IJCAI", "ACL",
                         "EMNLP", "CVPR", "ICCV", "ECCV", "KDD", "WWW",
                         "SIGIR", "SIGMOD", "VLDB", "ICDE", "CIKM"}
        is_conf = any(kw.lower() in venue.lower() for kw in conf_keywords)
        
        if is_conf:
            lines = [
                f"@inproceedings{{{key},",
                f"  title = {{{_escape_bibtex(title)}}},",
                f"  author = {{{_escape_bibtex(author_str)}}},",
                f"  booktitle = {{{_escape_bibtex(venue)}}},",
                f"  year = {{{year}}},",
            ]
        else:
            lines = [
                f"@article{{{key},",
                f"  title = {{{_escape_bibtex(title)}}},",
                f"  author = {{{_escape_bibtex(author_str)}}},",
                f"  journal = {{{_escape_bibtex(venue)}}},",
                f"  year = {{{year}}},",
            ]
        if doi:
            lines.append(f"  doi = {{{doi}}},")
        lines.append(f"  note = {{[AUTO-GENERATED] Verify before submission}}")
        lines.append("}")
    else:
        # 最简格式
        lines = [
            f"@misc{{{key},",
            f"  title = {{{_escape_bibtex(title)}}},",
            f"  author = {{{_escape_bibtex(author_str)}}},",
            f"  year = {{{year}}},",
        ]
        if doi:
            lines.append(f"  doi = {{{doi}}},")
        lines.append(f"  note = {{[AUTO-GENERATED] Verify before submission}}")
        lines.append("}")
    
    return "\n".join(lines)


def fetch_bibtex(query: str, max_results: int = 10) -> list[dict]:
    """智能获取 BibTeX：搜索论文 + 四级 fallback 获取 BibTeX。
    
    搜索策略：
    - 中文 query → AMiner 优先（中文学术最准），Semantic Scholar 补充
    - 英文 query → Semantic Scholar 优先（英文覆盖广），AMiner 补充
    - 两者结果合并去重（按 DOI 或标题相似度去重）
    - 内置 3 次重试机制
    
    BibTeX 获取优先级：DBLP → CrossRef DOI → 自动生成
    默认返回 10 篇论文。
    
    返回格式: [{"title": ..., "authors": [...], "year": ..., "bibtex": "...", "source": "dblp/crossref/auto", ...}]
    """
    # 检测 query 是否包含中文
    _has_chinese = bool(re.search(r'[\u4e00-\u9fff]', query))
    
    papers = []
    
    if _has_chinese:
        # 中文 query：AMiner 优先（已内置重试），Semantic Scholar 补充
        if _AMINER_API_KEY:
            _log(f"[中文] Searching AMiner: {query}")
            papers = aminer_search(query, max_results=max_results)
        # ⛔ AMiner 全失败兜底: CrossRef 也支持中文搜索 (修复 bug: AMiner 有时返空 / 网关挂)
        if not papers:
            _log(f"[中文兜底] AMiner 无结果, 尝试 CrossRef: {query}")
            cr_papers = crossref_search(query, max_results=max_results)
            for cr in cr_papers:
                papers.append({
                    "title": cr.get("title", ""),
                    "authors": cr.get("authors") or [],
                    "year": cr.get("year"),
                    "doi": cr.get("doi", ""),
                    "dblp_id": "",
                    "arxiv_id": "",
                    "venue": cr.get("venue", ""),
                    "citation_count": 0,
                    "abstract": "",
                    "source": "crossref",
                })
        # Semantic Scholar 补充（可能有英文相关论文），带重试
        if len(papers) < max_results:
            _log(f"[补充] Searching Semantic Scholar: {query}")
            s2_papers = []
            for _retry in range(_MAX_RETRIES):
                s2_papers = semantic_scholar_search(query, max_results=max_results - len(papers))
                if s2_papers:
                    break
                if _retry < _MAX_RETRIES - 1:
                    time.sleep(_RETRY_DELAY)
            # 去重：按 DOI 或标题前 30 字符
            existing_dois = {p.get("doi", "").lower() for p in papers if p.get("doi")}
            existing_titles = {p.get("title", "").lower()[:30] for p in papers if p.get("title")}
            for sp in s2_papers:
                sp_doi = (sp.get("doi") or "").lower()
                sp_title = (sp.get("title") or "").lower()[:30]
                if sp_doi and sp_doi in existing_dois:
                    continue
                if sp_title and sp_title in existing_titles:
                    continue
                papers.append(sp)
    else:
        # 英文 query：Semantic Scholar 优先（原本就准），带重试
        _log(f"[英文] Searching Semantic Scholar: {query}")
        for _retry in range(_MAX_RETRIES):
            papers = semantic_scholar_search(query, max_results=max_results)
            if papers:
                break
            if _retry < _MAX_RETRIES - 1:
                _log(f"S2 returned 0, retrying ({_retry + 2}/{_MAX_RETRIES})...")
                time.sleep(_RETRY_DELAY)
        # AMiner 补充（可能有中文相关论文）
        if _AMINER_API_KEY and len(papers) < max_results:
            _log(f"[补充] Searching AMiner: {query}")
            aminer_papers = aminer_search(query, max_results=max_results - len(papers))
            existing_dois = {p.get("doi", "").lower() for p in papers if p.get("doi")}
            existing_titles = {p.get("title", "").lower()[:30] for p in papers if p.get("title")}
            for ap in aminer_papers:
                ap_doi = (ap.get("doi") or "").lower()
                ap_title = (ap.get("title") or "").lower()[:30]
                if ap_doi and ap_doi in existing_dois:
                    continue
                if ap_title and ap_title in existing_titles:
                    continue
                papers.append(ap)
    
    # 如果两个都没结果，尝试 DBLP
    if not papers:
        _log("No results from primary sources, trying DBLP...")
        dblp_results = dblp_search(query, max_results=max_results)
        for dr in dblp_results:
            papers.append({
                "title": dr["title"],
                "authors": dr["authors"],
                "year": dr["year"],
                "doi": dr.get("doi", ""),
                "dblp_id": dr.get("dblp_key", ""),
                "arxiv_id": "",
                "venue": dr.get("venue", ""),
                "citation_count": 0,
                "abstract": "",
                "source": "dblp",
            })
    
    # 如果还没结果，尝试 CrossRef
    if not papers:
        _log("DBLP returned no results, trying CrossRef...")
        cr_results = crossref_search(query, max_results=max_results)
        for cr in cr_results:
            papers.append({
                "title": cr["title"],
                "authors": cr["authors"],
                "year": cr["year"],
                "doi": cr.get("doi", ""),
                "dblp_id": "",
                "arxiv_id": "",
                "venue": cr.get("venue", ""),
                "citation_count": 0,
                "abstract": "",
                "source": "crossref",
            })

    # 仍无结果 → OpenAlex 兜底（2.5亿+，人文社科/多语种/中文覆盖最广，防"搜不到→编造"）
    if not papers:
        _log("CrossRef returned no results, trying OpenAlex...")
        oa_results = openalex_search(query, max_results=max_results)
        for oa in oa_results:
            papers.append({
                "title": oa["title"],
                "authors": oa["authors"],
                "year": oa["year"],
                "doi": oa.get("doi", ""),
                "dblp_id": "",
                "arxiv_id": "",
                "venue": oa.get("venue", ""),
                "citation_count": oa.get("citation_count", 0),
                "abstract": "",
                "source": "openalex",
            })

    if not papers:
        _log("No results from any source")
        return []

    # Step 2: 对每篇论文获取 BibTeX（三级 fallback）
    results = []
    for paper in papers:
        bibtex = None
        bib_source = "auto"
        
        # 尝试 1: DBLP（最干净的 BibTeX）
        dblp_id = paper.get("dblp_id", "")
        if dblp_id:
            _log(f"  Trying DBLP BibTeX: {dblp_id}")
            bibtex = dblp_bibtex(dblp_id)
            if bibtex:
                bib_source = "dblp"
                _log(f"  ✓ Got BibTeX from DBLP")
            time.sleep(_RATE_DELAY)
        
        # 尝试 1b: DBLP 搜索（如果没有 dblp_id）
        # ⛔ 用 paper["title"] 当 original_title 让 DBLP 兜底做严格相似度校验
        # 防止 DBLP 模糊匹配命中无关论文 (如中文 query 被命中无关 EN 文章)
        if not bibtex and paper.get("title"):
            title = paper["title"]
            first_author = paper["authors"][0].split()[-1] if paper.get("authors") else ""
            dblp_query = f"{title} {first_author}".strip()
            _log(f"  Trying DBLP search: {dblp_query[:60]}...")
            dblp_bib = dblp_search_bibtex(dblp_query, original_title=title)
            if dblp_bib:
                bibtex = dblp_bib
                bib_source = "dblp"
                _log(f"  ✓ Got BibTeX from DBLP search")
            time.sleep(_RATE_DELAY)
        
        # 尝试 2: CrossRef DOI
        if not bibtex and paper.get("doi"):
            _log(f"  Trying CrossRef DOI: {paper['doi']}")
            bibtex = crossref_bibtex_by_doi(paper["doi"])
            if bibtex:
                bib_source = "crossref"
                _log(f"  ✓ Got BibTeX from CrossRef")
            time.sleep(_RATE_DELAY)
        
        # 尝试 3: 自动生成
        if not bibtex:
            _log(f"  Generating BibTeX from metadata")
            bibtex = _generate_bibtex_from_metadata(paper)
            bib_source = "auto"
        
        results.append({
            "title": paper.get("title", ""),
            "authors": paper.get("authors", []),
            "year": paper.get("year"),
            "doi": paper.get("doi", ""),
            "arxiv_id": paper.get("arxiv_id", ""),
            "venue": paper.get("venue", ""),
            "citation_count": paper.get("citation_count", 0),
            "abstract": paper.get("abstract", ""),
            "bibtex": bibtex,
            "bibtex_source": bib_source,
            "match_score": _compute_match_score(query, paper.get("title", ""), paper.get("authors", [])),
            "match_label": _match_label(_compute_match_score(query, paper.get("title", ""), paper.get("authors", []))),
        })

    # ⛔ 按 match_score 倒序排列, 让高匹配度的论文优先返回
    # SKILL 拿到结果后可按 match_label != "low" 过滤掉假匹配
    results.sort(key=lambda r: r.get("match_score", 0.0), reverse=True)

    # ⛔ 兜底数据质量警告: 全部 low 时记日志, 让 SKILL 走 WebSearch 兜底
    if results and all(r.get("match_label") == "low" for r in results):
        _log(f"⚠ All {len(results)} results are low-match for '{query[:60]}'. "
             f"SKILL should fallback to WebSearch on Google Scholar.")

    return results


def fetch_bibtex_by_doi(doi: str) -> Optional[dict]:
    """通过 DOI 获取单篇论文的 BibTeX。"""
    # 先从 CrossRef 获取 BibTeX
    bibtex = crossref_bibtex_by_doi(doi)
    bib_source = "crossref" if bibtex else None
    
    # 获取元数据
    paper = semantic_scholar_by_id(doi)
    
    if not bibtex and paper:
        # 尝试 DBLP
        dblp_id = paper.get("dblp_id", "")
        if dblp_id:
            bibtex = dblp_bibtex(dblp_id)
            if bibtex:
                bib_source = "dblp"
    
    if not bibtex and paper:
        bibtex = _generate_bibtex_from_metadata(paper)
        bib_source = "auto"
    
    if not bibtex:
        return None
    
    return {
        "title": paper.get("title", "") if paper else "",
        "authors": paper.get("authors", []) if paper else [],
        "year": paper.get("year") if paper else None,
        "doi": doi,
        "bibtex": bibtex,
        "bibtex_source": bib_source,
    }


# ============================================================
# CLI 入口
# ============================================================

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="学术文献搜索与 BibTeX 获取工具（Semantic Scholar + CrossRef + DBLP）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python scholar_fetch.py search "transformer attention mechanism" --max 5
  python scholar_fetch.py bibtex "attention is all you need" --max 3
  python scholar_fetch.py bibtex-doi "10.1145/3292500.3330919"
  python scholar_fetch.py bibtex-id "ARXIV:2301.07041"
        """,
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    # search: 搜索论文（返回元数据，不含 BibTeX）
    sp_search = subparsers.add_parser("search", help="搜索论文（返回元数据）")
    sp_search.add_argument("query", help="搜索关键词或论文标题")
    sp_search.add_argument("--max", type=int, default=5, help="最大结果数（默认 5）")
    
    # bibtex: 搜索论文并获取 BibTeX
    sp_bib = subparsers.add_parser("bibtex", help="搜索论文并获取 BibTeX（三级 fallback）")
    sp_bib.add_argument("query", help="搜索关键词或论文标题")
    sp_bib.add_argument("--max", type=int, default=5, help="最大结果数（默认 5）")
    
    # bibtex-doi: 通过 DOI 获取 BibTeX
    sp_doi = subparsers.add_parser("bibtex-doi", help="通过 DOI 获取 BibTeX")
    sp_doi.add_argument("doi", help="DOI 标识符，如 10.1145/3292500.3330919")
    
    # bibtex-id: 通过 Semantic Scholar / ArXiv / DBLP ID 获取 BibTeX
    sp_id = subparsers.add_parser("bibtex-id", help="通过论文 ID 获取 BibTeX")
    sp_id.add_argument("paper_id", help="论文 ID（S2 ID / DOI:xxx / ARXIV:xxx / DBLP:xxx）")
    
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_parser().parse_args(argv)
    
    if args.command == "search":
        results = semantic_scholar_search(args.query, max_results=args.max)
        if not results:
            # fallback to DBLP
            results = dblp_search(args.query, max_results=args.max)
        if not results:
            # 最终兜底 OpenAlex（人文社科/多语种/中文覆盖最广，防"搜不到→编造"）
            results = openalex_search(args.query, max_results=args.max)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    
    elif args.command == "bibtex":
        results = fetch_bibtex(args.query, max_results=args.max)
        print(json.dumps(results, ensure_ascii=False, indent=2))
        return 0
    
    elif args.command == "bibtex-doi":
        result = fetch_bibtex_by_doi(args.doi)
        if result:
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        else:
            print(json.dumps({"error": f"No BibTeX found for DOI: {args.doi}"}))
            return 1
    
    elif args.command == "bibtex-id":
        paper = semantic_scholar_by_id(args.paper_id)
        if not paper:
            print(json.dumps({"error": f"Paper not found: {args.paper_id}"}))
            return 1
        
        # 获取 BibTeX
        bibtex = None
        bib_source = "auto"
        
        if paper.get("dblp_id"):
            bibtex = dblp_bibtex(paper["dblp_id"])
            if bibtex:
                bib_source = "dblp"
        
        if not bibtex and paper.get("doi"):
            bibtex = crossref_bibtex_by_doi(paper["doi"])
            if bibtex:
                bib_source = "crossref"
        
        if not bibtex:
            bibtex = _generate_bibtex_from_metadata(paper)
            bib_source = "auto"
        
        paper["bibtex"] = bibtex
        paper["bibtex_source"] = bib_source
        print(json.dumps(paper, ensure_ascii=False, indent=2))
        return 0
    
    return 1


if __name__ == "__main__":
    sys.exit(main())
