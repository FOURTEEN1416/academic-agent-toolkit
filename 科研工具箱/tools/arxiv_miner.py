#!/usr/bin/env python3
"""
arxiv_miner.py - arxiv + duckduckgo 实时检索

用法：
  python arxiv_miner.py --query "graph neural network"
  python arxiv_miner.py --query "调度优化" --max-results 5
  python arxiv_miner.py --topic optimization --method genetic

退出码：0 = 成功（检索或离线兜底至少命中一条）；1 = 检索失败（在线全部
失败且离线兜底无结果，或参数缺失——后者同时打印用法错误）。
"""

import argparse
import json
import sys
from typing import List, Dict
from pathlib import Path


def _elem_text(elem, default: str = "") -> str:
    """Element.text 安全取值：元素缺失（find None）或空元素（text None）不炸。"""
    if elem is None or elem.text is None:
        return default
    return elem.text.strip().replace("\n", " ")


def search_arxiv(query: str, max_results: int = 10) -> List[Dict]:
    """从 arxiv API 搜索论文（无需 API key）"""
    try:
        import urllib.parse
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
            title = _elem_text(entry.find("atom:title", ns))
            summary = _elem_text(entry.find("atom:summary", ns))
            link = _elem_text(entry.find("atom:id", ns))
            authors = [_elem_text(a.find("atom:name", ns))
                       for a in entry.findall("atom:author", ns)]
            authors = [a for a in authors if a]
            if not title:
                continue
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
        import urllib.parse
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


def main() -> int:
    parser = argparse.ArgumentParser(
        description="arxiv + duckduckgo 实时检索",
        epilog="退出码：0 = 成功（至少命中一条）；1 = 检索失败（在线全部失败且离线兜底"
               "无结果，或参数缺失）")
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
        return 1

    print(f"[检索] {query}\n")

    papers = []
    if not args.offline:
        papers.extend(search_arxiv(query, args.max_results))
        if len(papers) < 3:
            papers.extend(search_duckduckgo(query, 5))
    if not papers:
        print("[INFO] 在线检索失败，使用离线模式")
        papers = offline_fallback(query)
    if not papers:
        print("[FAIL] 在线检索与离线兜底均无结果", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps({"query": query, "results": papers}, ensure_ascii=False, indent=2))
        return 0

    print(f"[找到 {len(papers)} 条结果]\n")
    for i, p in enumerate(papers, 1):
        print(f"--- [{i}] [{p['source']}] {p['title']}")
        if p.get("authors"):
            print(f"    作者: {', '.join(p['authors'])}")
        print(f"    摘要: {p.get('summary', '')}")
        if p.get("url"):
            print(f"    链接: {p['url']}")
        print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
