#!/usr/bin/env bash
# paper-search: 单篇论文详情查询（OpenAlex keyless API）
# ACAT-GOVERNANCE 标注（2026-11-16）：上游 paper.sh 未随仓集成（ASSET-GAP 登记）；
# 按 SKILL.md 契约重建为本地可执行版。非上游原样文件。
# 用法: paper.sh <https://doi.org/10.xxxx/yy | 裸 DOI | OpenAlex_ID 如 W2789811475>
ARG="${1:?usage: paper.sh <DOI_URL | bare DOI | OpenAlex_ID>}"

if [[ "$ARG" == https://doi.org/* ]]; then
  IDENT="doi:${ARG#https://doi.org/}"
elif [[ "$ARG" == http://doi.org/* ]]; then
  IDENT="doi:${ARG#http://doi.org/}"
elif [[ "$ARG" =~ ^10\.[0-9]+/[^[:space:]]+$ ]]; then
  IDENT="doi:${ARG}"
else
  IDENT="openalex:${ARG}"
fi

curl -s --max-time 25 "https://api.openalex.org/works/${IDENT}?mailto=acat-paper-search%40example.org" | python -c "
import json, sys
d = json.load(sys.stdin)
if d.get('error') or not d.get('id'):
    print(json.dumps({'error': d.get('error', 'entity not found')}, ensure_ascii=False))
    sys.exit(1)
inv = d.get('abstract_inverted_index')
abstract = None
if inv:
    pos = {}
    for word, idxs in inv.items():
        for i in idxs:
            pos[i] = word
    abstract = ' '.join(pos[i] for i in sorted(pos)) if pos else None
out = {
    'id': d.get('id'),
    'title': d.get('display_name'),
    'authors': [a.get('author', {}).get('display_name') for a in d.get('authorships', [])],
    'year': d.get('publication_year'),
    'doi': d.get('doi'),
    'cited_by_count': d.get('cited_by_count'),
    'concepts': [c.get('display_name') for c in (d.get('concepts') or [])[:8]],
    'open_access_pdf': (d.get('best_oa_location') or {}).get('pdf_url'),
    'abstract': abstract,
    'related_works': (d.get('related_works') or [])[:10],
}
print(json.dumps(out, indent=2, ensure_ascii=False))
"
