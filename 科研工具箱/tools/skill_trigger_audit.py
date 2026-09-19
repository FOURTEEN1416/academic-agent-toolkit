#!/usr/bin/env python3
"""Skill 触发条件与能力边界审计（P3 技能覆盖度件的反馈闭环件）。

技能能不能被"准确调用"，取决于两件事，且两者都可机检：

  1. **触发条件可判**（Layer A/B）——SKILL.md frontmatter 的 description 是唯一的
     "路由索引"：它必须存在、合规（name == 目录名、长度 ≤1024），并且写出**何时使用**
     （触发信号）。缺了它，技能会不会被激活就变成抽样。
  2. **能力边界可判**（Layer C）——两个技能触发词高度重叠时，描述里必须给出**判别说明**
     （"只用于 X；Y 场景改用 Z"），否则路由在同一句话上产生二义，调用准确性无从保证。

  3. **可知性对账**（Layer D）——每个技能必须同时登记在能力目录与全库技能地图中
     （复用既有工具，不重复实现）。

阈值来源（2026-09-19 全库 260 技能实测标定，非拍脑袋）：
  Jaccard ≥ 0.30 且 交集词元 ≥ 6 → 视为"路由歧义候选"。
  实测该阈值命中 10 对，其中 5 对缺判别说明——这是一个可闭环修的规模；
  阈值放松到 0.25 会让家族变体（语言/格式档）大量涌入，反而淹没真歧义。

用法：
  python tools/skill_trigger_audit.py                 # 全量审计，人读输出
  python tools/skill_trigger_audit.py --json          # 机读 JSON
  python tools/skill_trigger_audit.py --strict        # 存在 ERROR 时 exit 1
  python tools/skill_trigger_audit.py --min-jaccard 0.25 --min-shared 5

退出码：默认恒 0（报告件）；--strict 时发现 ERROR exit 1。
"""
from __future__ import annotations

import argparse
import itertools
from collections import Counter
import json
import math
import re
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = TOOLBOX_ROOT.parent
SKILLS_ROOT = TOOLBOX_ROOT / "skills"

# 非技能目录（与 check_asset_utilization / CONTEST_SKILL_MAP 口径一致）
NON_SKILL_DIRS = {"_utils", "shared-scripts"}

DESC_MAX = 1024
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.S)
DESC_RE = re.compile(r"^description:\s*(.+?)(?=\n[a-zA-Z_-]+:|\Z)", re.S | re.M)
NAME_RE = re.compile(r"^name:\s*(.+)$", re.M)

# 触发信号：描述里必须给出"何时使用"的判据（任一中即算）
TRIGGER_RE = re.compile(
    r"触发词|trigger|当用户|使用时|用这个|use when|适用于|当需要|当要|当出现|当有|在.*时使用",
    re.I,
)
# 判别说明：显式排除"另一种场景"（互斥声明）
DISCRIMINATOR_RE = re.compile(
    r"但(?!是)|而非|不用|改用|仅(?!要)|只(?!要)|专门|专属|区别于|与[^。]{0,12}不同|"
    r"instead|not for|only for|use .{0,20}for",
    re.I,
)

# 词元抽取的噪声表（实测标定：去掉这些后家族变体不再虚高命中）
NOISE = set(
    "the a an and or for to of in on with use when is are this that it its as by be from at "
    "into out up not but only also should before provides asks using needs make says wants "
    "user based main step full complete add file code skill under such any all new your you we".split()
)


def iter_skill_names(skills_root: Path = SKILLS_ROOT) -> list[str]:
    return sorted(
        d.name for d in skills_root.iterdir()
        if d.is_dir() and d.name not in NON_SKILL_DIRS and (d / "SKILL.md").is_file()
    )


def parse_frontmatter(text: str) -> dict[str, str]:
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}
    fm = m.group(1)
    dm = DESC_RE.search(fm)
    nm = NAME_RE.search(fm)
    return {
        "description": (dm.group(1).strip() if dm else ""),
        "name": (nm.group(1).strip().strip("\"'") if nm else ""),
        "raw": fm,
    }


def tokenize(text: str) -> set[str]:
    """词元抽取（**歧义检测专用**）：英文词 + 中文 2-4 字贪婪块，去噪声词。

    注意：本函数的口径与阈值（Jaccard≥0.30 且共词≥6）是**一起标定**的，
    改动它会移动歧义检测的灵敏度。路由诊断请用 `route_tokens`（见其 docstring）。
    """
    lowered = text.lower()
    en = set(re.findall(r"[a-z][a-z0-9\-]{2,}", lowered))
    zh = set(re.findall(r"[\u4e00-\u9fff]{2,4}", lowered))
    return {t for t in en | zh if t not in NOISE}


def route_tokens(text: str) -> set[str]:
    """路由诊断专用词元：中文按 **2-3 字滑窗 n-gram** 展开。

    为什么单独一套：贪婪 2-4 字切分会把「编译中文论文」切成交错块（查询切出
    「帮我编译 / 中文论文」，而描述里是「编译中文 / 论文」），导致该命中不命中——
    实测中这让「编译中文论文」误路由到英文版 `paper-compile`。
    n-gram 滑窗（编译/译中/中文/文论/论文 + 编译中/…）能让同一短语的任意切法都产生
    交集，这才是"这个词到底出现没出现"的可靠判据。

    不与 `tokenize` 合并的原因：本函数会显著抬高任意两段中文的重叠量，直接用于
    歧义检测会让阈值失去标定意义（大量家族变体涌入）。两套口径各司其职，
    并在 docstring 里写明用途，避免后来者误用。
    """
    lowered = text.lower()
    en = set(re.findall(r"[a-z][a-z0-9\-]{2,}", lowered))
    zh_texts = re.findall(r"[\u4e00-\u9fff]+", lowered)
    grams: set[str] = set()
    for chunk in zh_texts:
        for n in (2, 3):
            grams.update(chunk[i:i + n] for i in range(max(0, len(chunk) - n + 1)))
    return {t for t in en | grams if t not in NOISE}


def audit_skills(skills_root: Path) -> dict:
    """Layer A/B：frontmatter 合规性与触发信号。"""
    errors, warns, records = [], [], {}
    for name in iter_skill_names(skills_root):
        text = (skills_root / name / "SKILL.md").read_text(encoding="utf-8", errors="ignore")
        fm = parse_frontmatter(text)
        if not fm:
            errors.append({"skill": name, "kind": "no_frontmatter",
                           "detail": "SKILL.md 缺少 YAML frontmatter"})
            continue
        desc = fm["description"]
        records[name] = {"description": desc, "tokens": tokenize(desc)}
        if not desc:
            errors.append({"skill": name, "kind": "no_description", "detail": "description 为空"})
            continue
        if fm["name"] and fm["name"] != name:
            errors.append({"skill": name, "kind": "name_mismatch",
                           "detail": f"frontmatter name={fm['name']!r} 与目录名不一致"})
        if len(desc) > DESC_MAX:
            errors.append({"skill": name, "kind": "description_too_long",
                           "detail": f"description {len(desc)} 字符 > {DESC_MAX}（常驻上下文，越短越好）"})
        if len(desc) < 40:
            warns.append({"skill": name, "kind": "description_too_short",
                          "detail": f"description 仅 {len(desc)} 字符，难以承载 what + when"})
        if not TRIGGER_RE.search(desc):
            warns.append({"skill": name, "kind": "no_trigger_signal",
                          "detail": "description 未给出触发信号（何时使用/触发词），激活将不可预期"})
    return {"errors": errors, "warns": warns, "records": records}


def audit_overlaps(records: dict, min_jaccard: float, min_shared: int) -> dict:
    """Layer C：路由歧义候选对 + 判别说明检查。"""
    ambiguities, undiscriminated = [], []
    for a, b in itertools.combinations(sorted(records), 2):
        ta, tb = records[a]["tokens"], records[b]["tokens"]
        if not ta or not tb:
            continue
        shared = ta & tb
        if len(shared) < min_shared:
            continue
        jaccard = len(shared) / len(ta | tb)
        if jaccard < min_jaccard:
            continue
        da, db = records[a]["description"], records[b]["description"]
        mutual = (a in db) or (b in da) or (a.replace("paper-", "") in db) or (b.replace("paper-", "") in da)
        discriminated = mutual or (bool(DISCRIMINATOR_RE.search(da)) and bool(DISCRIMINATOR_RE.search(db)))
        item = {"a": a, "b": b, "jaccard": round(jaccard, 3),
                "shared": sorted(shared)[:12], "mutual_reference": mutual,
                "discriminated": discriminated}
        ambiguities.append(item)
        if not discriminated:
            undiscriminated.append(item)
    ambiguities.sort(key=lambda x: -x["jaccard"])
    undiscriminated.sort(key=lambda x: -x["jaccard"])
    return {"candidates": ambiguities, "undiscriminated": undiscriminated}


def audit_registry(skills_root: Path) -> dict:
    """Layer D：能力目录与全库技能地图的可知性对账（复用既有实现，不重复造）。"""
    names = set(iter_skill_names(skills_root))
    result: dict[str, object] = {"skills_total": len(names), "missing_in_catalog": [], "missing_in_map": []}
    try:
        catalog = json.loads((REPO_ROOT / "capabilities" / "catalog.json").read_text(encoding="utf-8"))
        mapped = {str(i.get("capability_id")) for items in catalog.values() for i in items}
        result["missing_in_catalog"] = sorted(names - mapped)
    except Exception as exc:  # 目录不可读时不阻断
        result["catalog_error"] = str(exc)
    try:
        sys.path.insert(0, str(TOOLBOX_ROOT / "tools"))
        import check_asset_utilization as cau  # noqa: PLC0415
        cov = cau.load_map_coverage(TOOLBOX_ROOT / "CONTEST_SKILL_MAP.md", sorted(names))
        result["missing_in_map"] = sorted(cov.get("missing") or [])
    except Exception as exc:
        result["map_error"] = str(exc)
    return result


def audit_contract_sections(skills_root: Path) -> dict:
    """Layer E：主链技能的"退出判据 + 常见合理化"契约段（融合自同类项目的 SKILL.md 骨架）。

    同行的 SKILL.md 是固定 19 段骨架，其中两段是硬要求：
      - `## Verification`（退出判据 checklist）——把"何时算做完"写在技能里，
        而不是留给 agent 现场发挥；
      - `## Common Rationalizations`（反合理化表）——把该岗位最常见的逃避借口
        预先配好反驳。

    本项目的做法：**主链自动派生**——名单直接读 `templates.json` 的 comp_cumcm 子步骤，
    因此新增/替换主链技能会自动要求补齐这两段（不需要手改本工具）。非主链技能不强制
    （外域集成件的骨架随上游，不强行加段）。
    """
    templates_path = TOOLBOX_ROOT / "engine" / "modex-core" / "templates.json"
    try:
        templates = json.loads(templates_path.read_text(encoding="utf-8"))
        main_chain = [s["skill_name"] for s in templates["comp_cumcm"]["sub_steps"]]
    except Exception as exc:  # 模板不可读时不阻断，如实降级
        return {"main_chain": [], "missing": [], "error": f"templates.json 不可读: {exc}"}

    missing = []
    for name in main_chain:
        path = skills_root / name / "SKILL.md"
        if not path.is_file():
            missing.append({"skill": name, "why": "SKILL.md 缺失"})
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        if "## 退出判据（Verification）" not in text:
            missing.append({"skill": name, "why": "缺「退出判据（Verification）」段"})
        if "## 常见合理化（Common Rationalizations）" not in text:
            missing.append({"skill": name, "why": "缺「常见合理化（Common Rationalizations）」段"})
            continue
        block = text.split("## 常见合理化（Common Rationalizations）", 1)[1]
        rows = [ln for ln in block.splitlines() if ln.strip().startswith("|")
                and "---" not in ln and "合理化" not in ln]
        if len(rows) < 3:
            missing.append({"skill": name,
                            "why": f"合理化表不足 3 行（实际 {len(rows)} 行）"})
    return {"main_chain": main_chain, "missing": missing, "error": ""}


ROUTING_INDEX_PATH = TOOLBOX_ROOT / "data" / "skill_routing_index.json"


def load_routing_index() -> dict[str, dict]:
    """读分层常驻的**按需层完整描述**索引。

    分层常驻（`tools/build_skill_index.py`）把按需层技能的常驻描述压成短索引，完整
    描述与触发词移到这里。因此：**只靠常驻描述不足以路由到按需层技能**——这正是
    索引存在的理由（也是它必须被真正读取的原因，否则分层就是拿路由质量换指标）。
    读取失败时如实返回空并降级（不静默假装索引存在）。
    """
    try:
        data = json.loads(ROUTING_INDEX_PATH.read_text(encoding="utf-8"))
        return {k: v for k, v in (data.get("skills") or {}).items()
                if v.get("tier") == "ondemand"}
    except Exception:
        return {}


def augmented_records(records: dict | None = None) -> dict:
    """常驻记录 + 按需层完整描述（with_index 路由用）。"""
    pool = dict(records if records is not None else audit_skills(SKILLS_ROOT)["records"])
    for name, entry in load_routing_index().items():
        full = entry.get("full_description") or ""
        if name in pool and len(full) > len(pool[name]["description"]):
            pool[name] = {"description": full, "tokens": route_tokens(full)}
    return pool


def route(query: str, records: dict | None = None, top_k: int = 3,
          with_index: bool = False) -> list[dict]:
    """确定性词法路由（用于回归测试与人工诊断）。

    **定位与诚实边界**：宿主真实的路由是语义的（模型读 description 判断）。本函数用
    纯词法重叠给候选排序，因此它测的是"描述是否具备足够的**词法可分性**"——
    这是正确路由的**必要条件而非充分条件**：词法都分不开的一对技能，语义路由也必然
    摇摆；反之词法分开不等于语义一定分对。

    计分：重叠词元数 / sqrt(描述词元数)——除以长度是必要的，否则长描述仅凭"词多"
    就能压倒精准的短描述（这与我们刚做的常驻瘦身同一动机）。

    用途：`--route "<用户原话>"` 做人工诊断；`tests/test_skill_trigger_audit.py`
    用它做"判别词翻转"回归（给出含判别词的请求，正确技能必须排到对手之前）。
    """
    pool = augmented_records(records) if with_index else         (records if records is not None else audit_skills(SKILLS_ROOT)["records"])
    q = route_tokens(query)
    if not q:
        return []
    token_cache = _route_token_cache(pool)
    # IDF 加权（第二次排序）：词元在全库描述里出现得越多，区分度越低。
    # 为什么必须加：实测 `paper-plan-zh` 因描述短且「中文/论文」这类高频词密集，
    # 对任何中文论文类请求都抢分（"词法黑洞"）——纯重叠计分无法识别"这个词人人都写"。
    # IDF 让高频词的贡献趋近于 1、稀有词（如 minimax / beamerposter / UCSB）贡献放大，
    # 这才是"请求里哪个词真正指向某个技能"的判据。
    df = Counter()
    for tokens in token_cache.values():
        df.update(tokens)
    total = max(len(token_cache), 1)

    def idf(token: str) -> float:
        return math.log((total + 1) / (df.get(token, 0) + 1)) + 1.0

    scored = []
    for name, tokens in token_cache.items():
        if not tokens:
            continue
        overlap = q & tokens
        if not overlap:
            continue
        score = sum(idf(tok) for tok in overlap) / (len(tokens) ** 0.5)
        # 诊断字段：**查询里的英文词元优先展示**——它们通常正是"判别词"
        # （UCSB / beamerposter / minimax 这类）。此前单纯按 IDF 取前 8，会被
        # 大量稀有中文 n-gram 挤掉（中文 2-3 字滑窗一个描述能产出几十个词元），
        # 造成"明明命中了 ucsb，matched 里却看不见"。
        # 更隐蔽的后果：该字段因此依赖**全库 df 统计**，技能集规模一变
        # （本机完整仓 261 vs 公开 clone 256）排序就翻转，使回归断言退化为
        # "看环境"的不稳定判据。score 与排名口径完全不变，只修展示。
        _ranked = sorted(overlap, key=lambda x: -idf(x))
        _shown = [t for t in sorted(q) if t.isascii() and t in overlap]
        _shown += [t for t in _ranked if t not in _shown]
        scored.append({"skill": name, "score": round(score, 4),
                       "matched": _shown[:12]})
    scored.sort(key=lambda x: (-x["score"], x["skill"]))
    return scored[:top_k]


def _route_token_cache(pool: dict) -> dict[str, set[str]]:
    """为本次调用计算词元（**不做跨调用缓存**）。

    为什么刻意不加缓存：曾用 `(id(pool), len(pool))` 作键做过缓存，结果在 pytest 全量
    运行中偶发命中错误池——CPython 的对象回收会复用 `id()`，两个 dict 拿到同一键就串了
    数据（症状：单文件跑绿、全量跑红）。正确性优先于这点性能：261 条描述的 n-gram
    分词是毫秒级，而错误的路由结果会污染回归判据。
    """
    return {name: route_tokens(rec["description"]) for name, rec in pool.items()}


def run(skills_root: Path = SKILLS_ROOT, min_jaccard: float = 0.30, min_shared: int = 6) -> dict:
    base = audit_skills(skills_root)
    overlaps = audit_overlaps(base["records"], min_jaccard, min_shared)
    registry = audit_registry(skills_root)
    sections = audit_contract_sections(skills_root)
    errors = list(base["errors"])
    for item in overlaps["undiscriminated"]:
        errors.append({"skill": f"{item['a']} × {item['b']}", "kind": "ambiguous_triggers",
                       "detail": f"Jaccard={item['jaccard']} 共 {len(item['shared'])} 词元重叠但无判别说明；"
                                 "路由会产生二义——请在描述中写明'只用于…／…场景改用…'"})
    for item in sections["missing"]:
        errors.append({"skill": item["skill"], "kind": "missing_contract_section",
                       "detail": f"主链技能契约不全：{item['why']}"})
    for key, kind in (("missing_in_catalog", "not_in_catalog"), ("missing_in_map", "not_in_skill_map")):
        for name in registry.get(key) or []:
            errors.append({"skill": name, "kind": kind, "detail": f"未登记于 {key}"})
    return {
        "skills_total": registry["skills_total"],
        "frontmatter_errors": base["errors"],
        "warns": base["warns"],
        "overlap_candidates": overlaps["candidates"],
        "undiscriminated_pairs": overlaps["undiscriminated"],
        "contract_sections": sections,
        "registry": registry,
        "errors": errors,
        "ok": not errors,
        "thresholds": {"min_jaccard": min_jaccard, "min_shared": min_shared},
    }



def _print_report(res: dict) -> None:
    print("=" * 72)
    print(f"Skill 触发条件与能力边界审计（skills={res['skills_total']}）")
    print("=" * 72)
    kinds: dict[str, int] = {}
    for err in res["frontmatter_errors"]:
        kinds[err["kind"]] = kinds.get(err["kind"], 0) + 1
    print(f"\n[1] frontmatter 合规：ERROR {len(res['frontmatter_errors'])} 条"
          + (f"（{kinds}）" if kinds else " —— OK"))
    wkinds: dict[str, int] = {}
    for w in res["warns"]:
        wkinds[w["kind"]] = wkinds.get(w["kind"], 0) + 1
    print(f"[2] 触发信号质量：WARN {len(res['warns'])} 条" + (f"（{wkinds}）" if wkinds else " —— OK"))
    if wkinds.get("no_trigger_signal"):
        samples = [w["skill"] for w in res["warns"] if w["kind"] == "no_trigger_signal"][:10]
        print(f"      无触发信号样例: {', '.join(samples)} …")
    print(f"[3] 路由歧义候选对：{len(res['overlap_candidates'])} 对"
          f"（阈值 Jaccard≥{res['thresholds']['min_jaccard']} 且 共词≥{res['thresholds']['min_shared']}）")
    for item in res["overlap_candidates"]:
        mark = "已判别" if item["discriminated"] else "**缺判别**"
        print(f"      J={item['jaccard']:<6} {item['a']} × {item['b']}  {mark}")
    sec = res.get("contract_sections") or {}
    print(f"[4] 主链契约段（退出判据 + 常见合理化）：主链 {len(sec.get('main_chain') or [])} 个技能 / "
          f"缺段 {len(sec.get('missing') or [])}")
    for item in (sec.get("missing") or [])[:6]:
        print(f"      {item['skill']}: {item['why']}")
    reg = res["registry"]
    print(f"[5] 可知性对账：目录缺 {len(reg.get('missing_in_catalog') or [])} / "
          f"地图漏网 {len(reg.get('missing_in_map') or [])}")
    verdict = "全部通过" if res["ok"] else "存在 %d 项 ERROR" % len(res["errors"])
    print("\n结论：" + verdict)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Skill 触发条件与能力边界审计")
    parser.add_argument("--skills", default=str(SKILLS_ROOT), help="技能根目录")
    parser.add_argument("--min-jaccard", type=float, default=0.30, help="歧义候选 Jaccard 阈值")
    parser.add_argument("--min-shared", type=int, default=6, help="歧义候选最小共词数")
    parser.add_argument("--json", action="store_true", dest="as_json", help="输出机读 JSON")
    parser.add_argument("--strict", action="store_true", help="存在 ERROR 时 exit 1")
    parser.add_argument("--route", default="", help="诊断：给一句用户原话，看词法路由会把哪些技能排前面")
    parser.add_argument("--with-index", action="store_true",
                        help="路由时并入按需层完整描述（分层常驻的索引通道）")
    args = parser.parse_args(argv)

    if args.route:
        hits = route(args.route, audit_skills(Path(args.skills))["records"],
                     with_index=args.with_index)
        print(f"词法路由诊断：{args.route!r}")
        for i, hit in enumerate(hits, 1):
            print(f"  {i}. {hit['skill']:<40} score={hit['score']}  匹配={hit['matched']}")
        return 0

    res = run(Path(args.skills), args.min_jaccard, args.min_shared)
    if args.as_json:
        print(json.dumps(res, ensure_ascii=False, indent=2))
    else:
        _print_report(res)
    if args.strict and not res["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
