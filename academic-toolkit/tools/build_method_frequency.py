#!/usr/bin/env python3
"""build_method_frequency.py — 从本地获奖论文语料抽取「方法→出现年份/题号」频次表。

用途：给创新性查重提供**语料侧的离线兜底依据**。`tools/novelty_checker.py` 只做
离线方法名字面命中，且明确声明"命中/未命中都不构成新颖性结论"；本工具产出
`academic-toolkit/data/method_frequency.json`，回答"这个方法在历年获奖论文里有多常见、
出现在哪些年份与题号"，供查重判定与人工比对使用。

数据源（全部只读；`assets-local/` 为本地私有材料，公开 clone 不交付）：
  1. `assets-local/award-papers/graduate/corpus_manifest.json`
     华为杯/研赛 686 篇；逐篇 `model_types_used`（摘要关键词机抽）
  2. `assets-local/award-papers/mathorcup-bigdata/corpus_manifest.json`
     MathorCup 大数据 49 篇；字段同上
  3. `assets-local/award-papers/layout-distill/*.json`
     国赛版面卡 19 张（2021/2022）；全文关键词命中
  4. `assets-local/award-papers/论文风格分析报告.md`
     国赛 OCR 文本 20 篇（2021×17 + 2022×3）；逐篇块关键词命中
  5. `academic-toolkit/data/historical_problems.json`
     国赛题号清单（元数据层，2020-2025）
  6. `academic-toolkit/data/award_paper_exemplars.json`
     国赛 62 篇聚合的 `model_stats`（元数据层，无逐篇/逐年归属）

计数口径（写进输出文件，消费方以文件内 `counted_unit` 为准）：
  - 计数单位 = **篇**：同一论文对同一方法只计 1 次；跨源重复（版面卡与风格报告
    命中同一 paper_id）按 paper_id 去重。
  - 语料清单篇目只收 `verification.contest_evidence == "yes"`——语料自身口径：
    无参赛佐证者不用于赛事归纳（见 `new_corpus_stats_2026-10-01.md`）。
  - 版面卡/风格报告是**方法名关键词命中**（`confidence: term_match`），
    不等于人工核验过"该论文用了该方法"。
  - 2023-2025 国赛无逐篇可机读正文：只给题号清单与 62 篇聚合题型分布
    （`metadata_only`），不给逐年逐篇方法归属。

用法：
  python tools/build_method_frequency.py                # 写 data/method_frequency.json
  python tools/build_method_frequency.py --json         # 另打印机读摘要
  python tools/build_method_frequency.py --out <path>   # 改输出位置
  python tools/build_method_frequency.py --repo-root <仓库根>  # 默认本文件上两级

退出码：0 = 已写出（源缺失或全部源都抽不到时如实写空表，并在 stdout 说明）；
        2 = 参数错误或输出不可写。
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLBOX_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_REPO_ROOT = TOOLBOX_ROOT.parent
DEFAULT_OUT = TOOLBOX_ROOT / "data" / "method_frequency.json"

SCHEMA_VERSION = 1

# 方法词表：canonical（与语料清单 `model_types_used` 的原生分类同名）→ (题型域, 别名)。
# 语料清单命中的是 canonical 本身；版面卡/风格报告用别名做关键词召回。
# 别名为拉丁文者按词边界匹配，中文按去空白后的子串匹配（OCR 文本会在汉字间插空格）。
METHOD_LEXICON: dict[str, tuple[str, tuple[str, ...]]] = {
    # —— 优化 ——
    "线性规划": ("优化", ("线性规划", "linear programming", "单纯形法")),
    "整数规划": ("优化", ("整数规划", "0-1规划", "0-1 规划", "integer programming")),
    "非线性规划": ("优化", ("非线性规划", "nonlinear programming")),
    "动态规划": ("优化", ("动态规划", "dynamic programming")),
    "多目标优化": ("优化", ("多目标优化", "多目标规划", "pareto")),
    "遗传算法": ("优化", ("遗传算法", "genetic algorithm")),
    "粒子群": ("优化", ("粒子群", "particle swarm", "pso")),
    "模拟退火": ("优化", ("模拟退火", "simulated annealing")),
    "蚁群算法": ("优化", ("蚁群算法", "ant colony")),
    "强化学习": ("优化", ("强化学习", "reinforcement learning")),
    "启发式/贪心": ("优化", ("启发式", "贪心", "heuristic")),
    # —— 预测 / 统计 ——
    "回归分析": ("预测/统计", ("回归分析", "回归模型", "多元回归", "线性回归", "logistic")),
    "时间序列": ("预测/统计", ("时间序列", "arima", "指数平滑", "holt-winters")),
    "灰色系统": ("预测/统计", ("灰色系统", "灰色预测", "gm(1,1)", "gm(1, 1)")),
    "马尔可夫": ("预测/统计", ("马尔可夫", "马尔科夫", "markov")),
    "蒙特卡罗": ("预测/统计", ("蒙特卡罗", "蒙特卡洛", "monte carlo")),
    # —— 评价 ——
    "层次分析法": ("评价", ("层次分析法", "ahp")),
    "TOPSIS/熵权": ("评价", ("topsis", "熵权", "熵值法")),
    "模糊综合评价": ("评价", ("模糊综合评价", "模糊评价")),
    "主成分/因子": ("评价", ("主成分", "pca", "因子分析")),
    "数据包络": ("评价", ("数据包络", "dea")),
    # —— 机器学习 / 分类聚类 ——
    "神经网络": ("机器学习", ("神经网络", "lstm", "gru", "cnn", "rnn", "transformer", "bp神经")),
    "聚类": ("机器学习", ("聚类", "k-means", "kmeans", "dbscan")),
    "分类/判别": ("机器学习", ("分类", "判别分析", "支持向量机", "svm", "随机森林",
                            "xgboost", "lightgbm", "朴素贝叶斯", "knn")),
    # —— 机理 / 仿真 ——
    "微分方程": ("机理", ("微分方程", "常微分", "偏微分", "ode", "pde")),
    "元胞自动机": ("机理", ("元胞自动机", "cellular automaton")),
    "仿真": ("机理", ("仿真", "abm", "多智能体", "agent-based", "agent based")),
    # —— 图论 / 网络 ——
    "图论/网络": ("图论", ("图论", "复杂网络", "dijkstra", "floyd", "pagerank", "最短路径")),
    "网络流": ("图论", ("网络流", "最大流", "最小费用流")),
    # —— 随机服务 ——
    "排队论": ("随机服务", ("排队论", "排队模型")),
}

_ASCII_RE = re.compile(r"^[a-z0-9()\- ]+$")
_PAPER_ID_RE = re.compile(r"^(\d{4})_([A-Z])(\d+)$")
_ASCII_TOKEN_RE_CACHE: dict[str, re.Pattern[str]] = {}


def _normalize(text: str) -> str:
    """去掉空白与连字符/下划线并转小写：OCR 文本会在汉字/单词间插空格。"""
    return re.sub(r"[\s\-_]+", "", str(text)).lower()


def _ascii_pattern(token: str) -> re.Pattern[str]:
    pattern = _ASCII_TOKEN_RE_CACHE.get(token)
    if pattern is None:
        pattern = re.compile(r"(?<![a-z0-9])" + re.escape(token) + r"(?![a-z0-9])")
        _ASCII_TOKEN_RE_CACHE[token] = pattern
    return pattern


def match_methods(text: str) -> dict[str, str]:
    """返回 {canonical: 命中的别名}。

    冲突处理：若某别名是另一条更长命中别名的子串（如「线性规划」⊂「非线性规划」），
    只保留更长者，避免一个方法名污染另一类计数。
    """
    haystack = _normalize(text)
    found: list[tuple[int, str, str]] = []
    for canonical, (_category, aliases) in METHOD_LEXICON.items():
        for alias in aliases:
            needle = _normalize(alias)
            if not needle:
                continue
            if _ASCII_RE.match(needle):
                hit = bool(_ascii_pattern(needle).search(haystack))
            else:
                hit = needle in haystack
            if hit:
                found.append((len(needle), needle, canonical))
    matched: dict[str, str] = {}
    for length, needle, canonical in found:
        shadowed = any(
            length < other_len and needle in other_needle and canonical != other_canonical
            for other_len, other_needle, other_canonical in found
        )
        if not shadowed:
            matched.setdefault(canonical, needle)
    return matched


def _problem_type_from_paper_id(paper_id: str) -> tuple[str, str]:
    """`2021_A028` → ("2021", "A")；不合格式返回 ("unavailable", "unavailable")。"""
    match = _PAPER_ID_RE.match(str(paper_id or ""))
    if not match:
        return "unavailable", "unavailable"
    return match.group(1), match.group(2)


class _Tally:
    """按 (方法, 论文) 去重的计数累加器。"""

    def __init__(self) -> None:
        # method -> paper_id -> {"year","problem","contest","sources": set}
        self._rows: dict[str, dict[str, dict[str, object]]] = {}

    def add(
        self,
        method: str,
        paper_id: str,
        *,
        contest: str,
        year: str,
        problem: str,
        source: str,
    ) -> None:
        if method not in METHOD_LEXICON:
            return
        bucket = self._rows.setdefault(method, {})
        row = bucket.get(paper_id)
        if row is None:
            row = {"contest": contest, "year": str(year) or "unavailable",
                   "problem": str(problem) or "unavailable", "sources": set()}
            bucket[paper_id] = row
        row["sources"].add(source)  # type: ignore[union-attr]

    def paper_count(self) -> int:
        return sum(len(bucket) for bucket in self._rows.values())

    def years_by_contest(self) -> dict[str, list[str]]:
        """各赛事有逐篇方法证据的年份（不含元数据层）。"""
        years: dict[str, set[str]] = {}
        for bucket in self._rows.values():
            for row in bucket.values():
                contest = str(row["contest"])
                years.setdefault(contest, set()).add(str(row["year"]))
        return {contest: sorted(values) for contest, values in sorted(years.items())}

    def to_json(self) -> dict[str, dict[str, object]]:
        out: dict[str, dict[str, object]] = {}
        for method in sorted(self._rows):
            bucket = self._rows[method]
            by_contest: dict[str, int] = {}
            by_year: dict[str, int] = {}
            by_problem: dict[str, int] = {}
            by_year_problem: dict[str, int] = {}
            by_source: dict[str, int] = {}
            for paper_id in sorted(bucket):
                row = bucket[paper_id]
                contest = str(row["contest"])
                year = str(row["year"])
                problem = str(row["problem"])
                by_contest[contest] = by_contest.get(contest, 0) + 1
                by_year[year] = by_year.get(year, 0) + 1
                by_problem[problem] = by_problem.get(problem, 0) + 1
                key = f"{year}/{problem}"
                by_year_problem[key] = by_year_problem.get(key, 0) + 1
                for source in row["sources"]:  # type: ignore[union-attr]
                    by_source[str(source)] = by_source.get(str(source), 0) + 1
            category, aliases = METHOD_LEXICON[method]
            out[method] = {
                "category": category,
                "aliases": list(aliases),
                "paper_count": len(bucket),
                "by_contest": dict(sorted(by_contest.items())),
                "by_year": dict(sorted(by_year.items())),
                "by_problem": dict(sorted(by_problem.items())),
                "by_year_problem": dict(sorted(by_year_problem.items())),
                "by_source": dict(sorted(by_source.items())),
                "papers": sorted(bucket),
            }
        return out


def _read_json(path: Path) -> tuple[object | None, str]:
    try:
        return json.loads(path.read_text(encoding="utf-8")), "read"
    except FileNotFoundError:
        return None, "missing"
    except (OSError, ValueError) as exc:
        return None, f"unreadable: {exc}"


def _load_corpus_manifest(
    path: Path,
    contest: str,
    tally: _Tally,
    *,
    repo_root: Path,
) -> dict[str, object]:
    """逐篇读取语料清单的 `model_types_used` 并入账。"""
    rel = path.relative_to(repo_root).as_posix()
    data, status = _read_json(path)
    info: dict[str, object] = {"path": rel, "contest": contest, "status": status,
                               "field": "model_types_used",
                               "extract_method": "machine_keyword_from_abstract"}
    if not isinstance(data, dict):
        return info
    papers = data.get("papers") or []
    with_methods = 0
    counted = 0
    skipped_no_evidence = 0
    for paper in papers:
        if not isinstance(paper, dict):
            continue
        methods = paper.get("model_types_used") or []
        if not methods:
            continue
        if paper.get("model_extract_method") != "machine_keyword_from_abstract":
            continue
        with_methods += 1
        verification = paper.get("verification") or {}
        if verification.get("contest_evidence") != "yes":
            skipped_no_evidence += 1
            continue
        counted += 1
        paper_id = str(paper.get("paper_id") or "")
        year = str(paper.get("year") or "unavailable")
        problem = str(paper.get("problem_code") or "unavailable")
        for method in methods:
            tally.add(str(method), paper_id, contest=contest, year=year,
                      problem=problem, source="corpus_manifest")
    info.update({
        "papers_total": len(papers),
        "papers_with_methods": with_methods,
        "papers_counted": counted,
        "skipped_no_contest_evidence": skipped_no_evidence,
    })
    return info


def _load_layout_cards(
    directory: Path,
    tally: _Tally,
    *,
    repo_root: Path,
) -> dict[str, object]:
    """版面卡全文关键词命中（国赛 2021/2022 共 19 张）。"""
    rel = directory.relative_to(repo_root).as_posix()
    info: dict[str, object] = {"path": f"{rel}/*.json", "contest": "cumcm",
                               "status": "missing", "confidence": "term_match"}
    if not directory.is_dir():
        return info
    cards = sorted(directory.glob("*.json"))
    counted = 0
    inspected = 0
    for card in cards:
        if card.name == "progress.json":
            continue
        data, status = _read_json(card)
        if status != "read" or not isinstance(data, dict):
            continue
        inspected += 1
        paper_id = str(data.get("paper_id") or card.stem)
        year, problem = _problem_type_from_paper_id(paper_id)
        matched = match_methods(json.dumps(data, ensure_ascii=False))
        if matched:
            counted += 1
        for method in matched:
            tally.add(method, paper_id, contest="cumcm", year=year,
                      problem=problem, source="layout_card")
    info.update({"status": "read", "cards_inspected": inspected,
                 "cards_with_method_terms": counted})
    return info


def _load_style_report(
    path: Path,
    tally: _Tally,
    *,
    repo_root: Path,
) -> dict[str, object]:
    """论文风格分析报告逐篇块关键词命中（OCR 覆盖 2021×17 + 2022×3）。"""
    rel = path.relative_to(repo_root).as_posix()
    info: dict[str, object] = {"path": rel, "contest": "cumcm", "status": "missing",
                               "confidence": "term_match"}
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return info
    except OSError as exc:
        info["status"] = f"unreadable: {exc}"
        return info
    blocks = re.split(r"(?=【\d{4}_[A-Z]\d+】)", text)
    inspected = 0
    counted = 0
    for block in blocks:
        header = re.match(r"【(\d{4}_[A-Z]\d+)】", block)
        if not header:
            continue
        inspected += 1
        paper_id = header.group(1)
        year, problem = _problem_type_from_paper_id(paper_id)
        matched = match_methods(block)
        if matched:
            counted += 1
        for method in matched:
            tally.add(method, paper_id, contest="cumcm", year=year,
                      problem=problem, source="style_report")
    info.update({"status": "read", "papers_inspected": inspected,
                 "papers_with_method_terms": counted})
    return info


def _metadata_only(repo_root: Path, cumcm_years_with_evidence: list[str]) -> dict[str, object]:
    """拿不到逐篇正文的年份，用已有元数据补齐题号清单与聚合题型分布。"""
    meta: dict[str, object] = {"cumcm": {}}
    problems_path = repo_root / "academic-toolkit" / "data" / "historical_problems.json"
    problems, problems_status = _read_json(problems_path)
    cumcm = meta["cumcm"]  # type: ignore[index]
    if isinstance(problems, dict):
        cumcm["problem_inventory"] = {
            "schema": "historical_problems",
            "years": sorted(problems.get("problems") or {}),
            "by_year": problems.get("problems") or {},
            "type_distribution": (problems.get("statistics") or {}).get("type_distribution"),
            "note": "题号与题名；type_hint 为编辑性提示（官方不发布题型分类）",
        }
    else:
        cumcm["problem_inventory"] = {"status": problems_status}

    exemplars_path = repo_root / "academic-toolkit" / "data" / "award_paper_exemplars.json"
    exemplars, exemplars_status = _read_json(exemplars_path)
    if isinstance(exemplars, dict):
        cumcm["model_stats_aggregate"] = {
            "schema": "award_paper_exemplars.model_stats",
            "counts": exemplars.get("counts"),
            "model_stats": exemplars.get("model_stats") or {},
            "note": "62 篇国赛范文的聚合题型分布（方法→题型，A/B/C…），"
                    "无逐篇/逐年归属，不可当作频次使用",
        }
        exemplar_years = (exemplars.get("counts") or {}).get("years") or []
        metadata_only_years = sorted({str(y) for y in exemplar_years}
                                     - set(cumcm_years_with_evidence))
    else:
        cumcm["model_stats_aggregate"] = {"status": exemplars_status}
        metadata_only_years = []
    cumcm["years_metadata_only"] = {
        "years": metadata_only_years,
        "note": "国赛范文清单覆盖但无逐篇可机读正文的年份（版面卡与 OCR 仅覆盖 2021/2022）："
                "只有题号清单与 62 篇聚合题型分布，不给逐年逐篇方法归属",
    }
    return meta


def _layout_progress(repo_root: Path) -> dict[str, object]:
    path = repo_root / "assets-local" / "award-papers" / "layout-distill" / "progress.json"
    data, status = _read_json(path)
    if not isinstance(data, dict):
        return {"status": status}
    return {
        "status": "read",
        "schema": data.get("schema"),
        "counts": data.get("counts"),
        "updated": data.get("updated"),
    }


def build(repo_root: Path) -> dict[str, object]:
    """组装频次表（不写盘）。"""
    tally = _Tally()
    award_root = repo_root / "assets-local" / "award-papers"
    sources: list[dict[str, object]] = []

    sources.append(_load_corpus_manifest(
        award_root / "graduate" / "corpus_manifest.json", "graduate", tally,
        repo_root=repo_root))
    sources.append(_load_corpus_manifest(
        award_root / "mathorcup-bigdata" / "corpus_manifest.json",
        "mathorcup-bigdata", tally, repo_root=repo_root))
    sources.append(_load_layout_cards(award_root / "layout-distill", tally,
                                      repo_root=repo_root))
    sources.append(_load_style_report(award_root / "论文风格分析报告.md", tally,
                                      repo_root=repo_root))

    methods = tally.to_json()
    years_by_contest = tally.years_by_contest()
    metadata_only = _metadata_only(repo_root, years_by_contest.get("cumcm", []))
    cumcm_metadata_years = (
        (metadata_only.get("cumcm") or {}).get("years_metadata_only", {}).get("years", []))
    distinct_papers = {paper for item in methods.values() for paper in item["papers"]}

    missing_sources = [s["path"] for s in sources if s.get("status") != "read"]
    return {
        "schema_version": SCHEMA_VERSION,
        "title": "方法频次表（获奖论文语料 · 方法→出现年份/题号）",
        "generator": "academic-toolkit/tools/build_method_frequency.py",
        "usage": (
            "创新性查重的语料侧离线依据：查 'methods.<方法名>' 得 paper_count / by_year / "
            "by_problem / by_year_problem；0 或缺项只表示语料未覆盖，不构成新颖性结论。"
            "与 tools/novelty_checker.py 的字面命中表互补：后者判'是否教科书常见方法'，"
            "本表判'在历年获奖语料里有多常见、出现在哪些年份与题号'。"
        ),
        "counted_unit": "篇（同一论文对同一方法只计 1 次；跨源按 paper_id 去重）",
        "scope": {
            "method_vocabulary": sorted(METHOD_LEXICON),
            "vocabulary_with_zero_hits": sorted(set(METHOD_LEXICON) - set(methods)),
            "vocabulary_source": "语料清单 model_types_used 原生分类 + 少量常用同义扩展",
            "papers_with_methods": len(distinct_papers),
            "confidence": {
                "corpus_manifest": "逐篇字段（摘要关键词机抽，非人工核验）",
                "layout_card": "term_match（版面卡全文关键词命中）",
                "style_report": "term_match（OCR 逐篇块关键词命中）",
            },
            "years_with_paper_level_evidence": dict(sorted(years_by_contest.items())),
            "years_metadata_only": {"cumcm": cumcm_metadata_years},
        },
        "sources": sources,
        "layout_distillation": _layout_progress(repo_root),
        "methods": methods,
        "metadata_only": metadata_only,
        "limitations": [
            "语料清单的 model_types_used 为摘要关键词机抽，未逐篇人工核验",
            "版面卡/风格报告命中仅为方法名关键词，可能漏计（只读摘要/前 10 页）",
            "国赛 2023-2025 无逐篇可机读正文，仅有题号清单与 62 篇聚合题型分布",
            "全部语料 award_unverified（自媒体合集，无逐篇获奖佐证）；"
            "contest_evidence=no 的篇目未计入",
            "paper_count 不是'该方法的创新度'：常见方法可做创新，冷门方法也可能没价值",
        ] + ([f"源缺失或不可读（按空表处理）: {p}" for p in missing_sources] if missing_sources else []),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="从本地获奖论文语料抽取「方法→出现年份/题号」频次表")
    parser.add_argument("--repo-root", default=str(DEFAULT_REPO_ROOT),
                        help="仓库根（默认本文件上两级）")
    parser.add_argument("--out", default=str(DEFAULT_OUT),
                        help="输出路径（默认 academic-toolkit/data/method_frequency.json）")
    parser.add_argument("--json", action="store_true", dest="as_json",
                        help="打印机读摘要")
    args = parser.parse_args(argv)

    repo_root = Path(args.repo_root).resolve()
    out_path = Path(args.out).resolve()
    if not repo_root.is_dir():
        print(f"[FAIL] 仓库根不存在: {repo_root}", file=sys.stderr)
        return 2

    payload = build(repo_root)
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8", newline="\n")
    except OSError as exc:
        print(f"[FAIL] 写出失败: {exc}", file=sys.stderr)
        return 2

    methods = payload["methods"]
    distinct_papers = {paper for item in methods.values() for paper in item["papers"]}
    summary = {
        "out": str(out_path),
        "methods": len(methods),
        "papers_with_methods": len(distinct_papers),
        "sources_read": [s["path"] for s in payload["sources"] if s.get("status") == "read"],
        "sources_missing": [s["path"] for s in payload["sources"] if s.get("status") != "read"],
        "empty": not methods,
    }
    if args.as_json:
        print(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        print(f"[OK] 已写出 {out_path}")
        print(f"     方法 {summary['methods']} 类；"
              f"读入源 {len(summary['sources_read'])}/{len(payload['sources'])}；"
              f"缺失源 {len(summary['sources_missing'])}")
        if summary["empty"]:
            print("[WARN] 未从任何源抽到方法：已如实输出空表。"
                  "公开 clone 不交付 assets-local/，属预期；本机请检查语料是否在位。")
        for path in summary["sources_missing"]:
            print(f"[WARN] 源缺失/不可读: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
