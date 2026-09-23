#!/usr/bin/env bash
# paper-search: 学术论文检索（OpenAlex keyless API）
# ACAT-GOVERNANCE 标注（2026-08-30）：上游契约引用 ~/.claude 插件脚本但脚本从未入库；
# 按契约重建为本地可执行版（OpenAlex keyless，双宿主可用）。非上游原样文件。
# 用法: search.sh "<query>" [limit] [sort:relevance|cites] [page]
# v2: cites 模式客户端被引排序（relevance 拉取）。
QUERY="${1:?usage: search.sh \"<query>\" [limit] [sort] [page]}"
LIMIT="${2:-10}"
SORT="${3:-relevance}"
PAGE="${4:-1}"
FETCH=$(( LIMIT * 3 > 50 ? 50 : LIMIT * 3 + 2 ))
# v3: filter=title_and_abstract.search: 为 AND 语义——裸 search 长查询是 OR（混入全库高引不相关论文，实测留档）
Q_ENC=$(python -c "import urllib.parse,sys;print(urllib.parse.quote(sys.argv[1]))" "$QUERY")
RAW=$(curl -s --max-time 25 "https://api.openalex.org/works?filter=title_and_abstract.search:${Q_ENC}&per-page=${FETCH}&page=${PAGE}&mailto=acat-paper-search%40example.org")
echo "$RAW" | python -c "
import json, sys, urllib.parse
d = json.load(sys.stdin)
q_tokens = [w for w in urllib.parse.unquote(sys.argv[3]).lower().split() if len(w) > 3]
items = d.get('results', [])
# 客户端相关性守卫：OpenAlex 空格语义不稳定（实测混入无关高引）——确定性过滤标题至少含一个 >4 字符查询词
rel = [w for w in items if any(tok in w.get('display_name','').lower() for tok in q_tokens)]
sort = sys.argv[1]
if sort == 'cites':
    rel = sorted(rel, key=lambda w: w.get('cited_by_count', 0), reverse=True)
d['results'] = rel[:int(sys.argv[2])]
d['client_relevance_filter'] = {'query_tokens': q_tokens, 'api_returned': len(items), 'kept': len(d['results'])}
print(json.dumps(d, ensure_ascii=False))
" "$SORT" "$LIMIT" "$QUERY"
