#!/usr/bin/env python3
"""
arxiv_miner.py - arxiv + duckduckgo 实时检索

用法：
  python arxiv_miner.py --query "graph neural network"
  python arxiv_miner.py --query "调度优化" --max-results 5
  python arxiv_miner.py --topic optimization --method genetic
"""

import argparse
import json
import sys
import urllib.parse
from typing import List, Dict
from pathlib import Path


def search_arxiv(query: str, max_results: int = 10) -> List[Dict]:
    """从 arxiv API 搜索论文（无需 API key）"""
    try:
        import urllib.request
        import xml.etree.ElementTree as ET

        encoded = urllib.parse.quote(query)
        url = f"https://export.arxiv.org/api/query?search_query=all:{encoded}&start=0&max_results={max_results}"
        req = urllib.request.Request(url, headers={"User-Agent": "MCM-NSFC-Tool/1.0"})
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read().decode("utf-8")
        root = ET.fromstring(data)
        ns = {"atom": "http://www.w3.org/2005/Atom"}

        papers = []
        for entry in root.findall("atom:entry", ns):
            title = entry.find("atom:title", ns).text.strip().replace("\n", " ")
            summary = entry.find("atom:summary", ns).text.strip().replace("\n", " ")
            link = entry.find("atom:id", ns).text.strip()
            authors = [a.find("atom:name", ns).text for a in entry.findall("atom:author", ns)]
            papers.append({
                "source": "arxiv",
                "title": title,
                "summary": summary[:300] + ("..." if len(summary) > 300 else ""),
                "authors": authors[:3],
                "url": link
            })
        return papers
    except Exception as e:
        print(f"[WARN] arxiv 检索失败: {e}", file=sys.stderr)
        return []


def search_duckduckgo(query: str, max_results: int = 5) -> List[Dict]:
    """DuckDuckGo 即时答案（无需 API key）"""
    try:
        # 使用 DDG 的 instant answer API（轻量）
        import urllib.request
        encoded = urllib.parse.quote(query)
        url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1"
        req = urllib.request.Request(url, headers={"User-Agent": "MCM-NSFC-Tool/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        results = []
        for r in data.get("RelatedTopics", [])[:max_results]:
            if "Text" in r:
                results.append({
                    "source": "duckduckgo",
                    "title": r.get("Text", "")[:100],
                    "summary": r.get("Text", "")[:300],
                    "url": r.get("FirstURL", "")
                })
        return results
    except Exception as e:
        print(f"[WARN] DuckDuckGo 检索失败: {e}", file=sys.stderr)
        return []


def offline_fallback(query: str) -> List[Dict]:
    """离线兜底：返回 data/case_patterns.md 中的相关条目"""
    patterns_path = Path(__file__).resolve().parent.parent / "data" / "case_patterns.md"
    if not patterns_path.exists():
        return []
    content = patterns_path.read_text(encoding="utf-8")
    # 简单关键词匹配
    keywords = query.split()
    matches = []
    for line in content.split("\n"):
        if any(kw in line for kw in keywords) and line.strip().startswith("-"):
            matches.append({
                "source": "offline_patterns",
                "title": line.strip("- ").strip()[:100],
                "summary": line.strip(),
                "url": "data/case_patterns.md"
            })
    return matches[:5]


def main():
    parser = argparse.ArgumentParser(description="arxiv + duckduckgo 实时检索")
    parser.add_argument("--query", help="检索关键词")
    parser.add_argument("--topic", help="题型")
    parser.add_argument("--method", help="拟用方法")
    parser.add_argument("--max-results", type=int, default=10, help="最大结果数")
    parser.add_argument("--offline", action="store_true", help="强制离线")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    query = args.query
    if not query and args.topic and args.method:
        query = f"{args.topic} {args.method}"
    if not query:
        print("错误：必须指定 --query 或 --topic+--method", file=sys.stderr)
        sys.exit(1)

    print(f"[检索] {query}\n")

    papers = []
    if not args.offline:
        papers.extend(search_arxiv(query, args.max_results))
        if len(papers) < 3:
            papers.extend(search_duckduckgo(query, 5))
    if not papers:
        print("[INFO] 在线检索失败，使用离线模式")
        papers = offline_fallback(query)

    if args.json:
        print(json.dumps({"query": query, "results": papers}, ensure_ascii=False, indent=2))
        return

    print(f"[找到 {len(papers)} 条结果]\n")
    for i, p in enumerate(papers, 1):
        print(f"--- [{i}] [{p['source']}] {p['title']}")
        if p.get("authors"):
            print(f"    作者: {', '.join(p['authors'])}")
        print(f"    摘要: {p.get('summary', '')}")
        if p.get("url"):
            print(f"    链接: {p['url']}")
        print()


if __name__ == "__main__":
    main()
