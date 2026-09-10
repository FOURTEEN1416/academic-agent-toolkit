#!/usr/bin/env python3
"""Deterministic guardrails for reader-facing mathematical-modeling papers.

The checker is deliberately conservative: it catches high-confidence process
leakage and structural writing defects, while leaving ordinary mathematical
terms such as ``约束条件`` and ``误差检验`` untouched.
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import NamedTuple

sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources


for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass


APPENDIX_RE = re.compile(r"appendix|(?:^|[_-])code(?:[-_.]|$)|附录|代码", re.I)
RESTATEMENT_NAME_RE = re.compile(r"restate|restatement|problem[_-]?statement|问题重述|题目重述", re.I)
ANALYSIS_NAME_RE = re.compile(r"(?:^|[_-])analysis(?:[_-]|\.)|问题分析|赛题分析", re.I)
PUBLIC_FILE_RE = re.compile(
    r"(?<![A-Za-z0-9_])(?:[A-Za-z0-9_.-]+[/\\])*[A-Za-z0-9_.-]+\."
    r"(?:xlsx?|csv|json|py|m|md|tex|pdf|docx?|png|jpe?g|svg|drawio)(?![A-Za-z0-9_])",
    re.I,
)
RESULT_LEAK_RE = re.compile(
    r"(?:最终(?:得到|确定|求得|结果)?(?:为|达到)?|计算(?:可)?得|求得|结果(?:为|达到)|"
    r"最优(?:值|解|成本|方案)(?:为|达到)?|终止时刻(?:为|达到)?|"
    r"最大(?:速度|收益|利润|载荷)(?:为|达到)?|最小(?:值|距离|螺距|成本)(?:为|达到)?)"
    r"[^。；\n]{0,28}?[-+]?\d+(?:\.\d+)?",
)
MONOTONE_CLAIM_RE = re.compile(
    r"(?:可行域|可行集)[^。；\n]{0,90}(?:严格包含|真包含|嵌套|单调|不增|不减|更优|不会变差)"
    r"|(?:目标值|最优值)[^。；\n]{0,90}(?:单调|不增|不减|不会变差|必然更优)",
)
STRICT_INCLUSION_RE = re.compile(r"\\(?:var)?(?:sub|super)setneq\b")
SAME_OBJECTIVE_RE = re.compile(r"同一目标|相同目标|目标函数(?:完全)?相同|目标定义(?:保持)?不变")
PROOF_CUE_RE = re.compile(r"逐项|一一对应|映射|证明|由定义|由于|因此|从而")
TEX_HEADING_RE = re.compile(r"\\(?:part|chapter|section|subsection)\*?\{([^{}]+)\}")
MD_HEADING_RE = re.compile(r"(?m)^#{1,4}\s+(.+?)\s*$")
PROBLEM_TOKEN_RE = re.compile(r"问题\s*([一二三四五六七八九十]|[1-9]\d*)")

CN_NUMBERS = {
    "一": 1, "二": 2, "三": 3, "四": 4, "五": 5,
    "六": 6, "七": 7, "八": 8, "九": 9, "十": 10,
}


class Issue(NamedTuple):
    path: Path
    line: int
    message: str
    severity: str = "error"


def _blank(match: re.Match[str]) -> str:
    return re.sub(r"[^\n]", " ", match.group(0))


def strip_nonspeech(text: str, *, keep_math: bool = True) -> str:
    """Remove comments and code while preserving line numbers."""
    for fence in ("```", "~~~~"):
        text = re.sub(re.escape(fence) + r".*?" + re.escape(fence), _blank, text, flags=re.S)
    text = re.sub(
        r"\\begin\{(?P<env>lstlisting|verbatim|minted)\}.*?\\end\{(?P=env)\}",
        _blank, text, flags=re.S,
    )
    text = re.sub(r"<!--.*?-->", _blank, text, flags=re.S)
    text = re.sub(r"(?m)(?<!\\)%[^\n]*", _blank, text)
    text = re.sub(r"`[^`\n]*`", _blank, text)
    if not keep_math:
        text = re.sub(r"\$\$.*?\$\$|\\\[.*?\\\]|\\begin\{(?:equation\*?|align\*?|aligned|gather\*?)\}.*?"
                      r"\\end\{(?:equation\*?|align\*?|aligned|gather\*?)\}", _blank, text, flags=re.S)
        text = re.sub(r"(?<!\\)\$[^$\n]*?(?<!\\)\$", _blank, text)
    return text


def _line(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def _visible(text: str) -> str:
    text = strip_nonspeech(text, keep_math=False)
    text = TEX_HEADING_RE.sub(r"\1", text)
    text = re.sub(r"\\[A-Za-z@]+\*?(?:\[[^]]*\])?", " ", text)
    return re.sub(r"[{}\\]", " ", text)


def _kind(path: Path, text: str) -> str:
    name = path.name
    if RESTATEMENT_NAME_RE.search(name):
        return "restatement"
    if ANALYSIS_NAME_RE.search(name):
        return "analysis"
    headings = TEX_HEADING_RE.findall(text) + MD_HEADING_RE.findall(text)
    joined = " ".join(headings)
    if re.search(r"问题重述|题目重述", joined):
        return "restatement"
    if re.search(r"问题分析|赛题分析", joined):
        return "analysis"
    return "body"


def _named_section(text: str, title_pattern: str) -> str | None:
    """Extract one reader section from a monolithic Markdown/LaTeX source."""
    markdown = list(re.finditer(r"(?m)^(#{1,6})\s+(.+?)\s*$", text))
    for index, match in enumerate(markdown):
        if not re.search(title_pattern, match.group(2), re.I):
            continue
        level = len(match.group(1))
        end = len(text)
        for candidate in markdown[index + 1:]:
            if len(candidate.group(1)) <= level:
                end = candidate.start()
                break
        return text[match.end():end]
    latex = list(re.finditer(r"\\(section|chapter)\*?\{([^{}]+)\}", text))
    for index, match in enumerate(latex):
        if not re.search(title_pattern, match.group(2), re.I):
            continue
        end = latex[index + 1].start() if index + 1 < len(latex) else len(text)
        return text[match.end():end]
    return None


def _problem_index(token: str) -> int | None:
    if token.isdigit():
        return int(token)
    if token in CN_NUMBERS:
        return CN_NUMBERS[token]
    if token.startswith("十") and len(token) == 2 and token[1] in CN_NUMBERS:
        return 10 + CN_NUMBERS[token[1]]
    return None


def _expected_problems(all_text: str) -> set[int]:
    headings = TEX_HEADING_RE.findall(all_text) + MD_HEADING_RE.findall(all_text)
    found: set[int] = set()
    for heading in headings:
        for match in PROBLEM_TOKEN_RE.finditer(heading):
            value = _problem_index(match.group(1))
            if value:
                found.add(value)
    return found


def _analysis_heading_problems(all_text: str) -> set[int]:
    """Return subproblem ids carried by real analysis headings, not prose labels."""
    headings = TEX_HEADING_RE.findall(all_text) + MD_HEADING_RE.findall(all_text)
    found: set[int] = set()
    for heading in headings:
        if "分析" not in heading:
            continue
        for match in PROBLEM_TOKEN_RE.finditer(heading):
            value = _problem_index(match.group(1))
            if value:
                found.add(value)
    return found


def _is_standalone_analysis(path: Path, text: str) -> bool:
    """Tell a dedicated analysis section from a local model subsection."""
    if ANALYSIS_NAME_RE.search(path.name):
        return True
    for heading in TEX_HEADING_RE.findall(text) + MD_HEADING_RE.findall(text):
        compact = re.sub(r"\s+", "", heading)
        if re.fullmatch(r"(?:\d+(?:\.\d+)*[、.]?)?(?:问题|赛题)分析", compact):
            return True
        if "问题重述" in compact and "问题分析" in compact:
            return True
    return False


def _check_restatement(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []
    visible = _visible(text)
    for match in PUBLIC_FILE_RE.finditer(visible):
        issues.append(Issue(path, _line(visible, match.start()),
                            f"问题重述出现交付文件名“{match.group(0)}”；只说明任务要求，不写文件路径或输出名"))
    numeric = re.findall(r"(?<![A-Za-z])[-+]?\d+(?:\.\d+)?%?", visible)
    meaningful = re.findall(r"[\u3400-\u9fffA-Za-z0-9]", visible)
    if len(numeric) >= 18 and len(numeric) / max(1, len(meaningful)) > 0.065:
        issues.append(Issue(path, 1,
                            f"问题重述含 {len(numeric)} 个数值，疑似逐项复述参数；保留决定模型结构的条件，其余回指题面"))
    return issues


def _check_analysis(
    path: Path,
    text: str,
    expected: set[int],
    *,
    enforce_coverage: bool = True,
) -> list[Issue]:
    issues: list[Issue] = []
    visible = _visible(text)
    if enforce_coverage and len(expected) >= 2:
        present = {
            value for match in PROBLEM_TOKEN_RE.finditer(visible)
            if (value := _problem_index(match.group(1))) is not None
        }
        missing = sorted(expected - present)
        if missing:
            label = "、".join(str(item) for item in missing)
            issues.append(Issue(path, 1, f"问题分析未分别覆盖问题 {label}；多问题赛题应逐问说明难点、关系和建模思路"))
        for paragraph in re.split(r"\n\s*\n", visible):
            mentioned = {
                value for match in PROBLEM_TOKEN_RE.finditer(paragraph)
                if (value := _problem_index(match.group(1))) is not None
            }
            # Cross-references are normal dependencies. Only multiple explicit
            # question introductions in the same paragraph demonstrate packing.
            introductions = re.findall(r"(?:^|[。；])\s*(?:针对)?问题\s*(?:[一二三四五六七八九十]|[1-9]\d*)\s*[：:]", paragraph)
            if len(mentioned) > 1 and len(introductions) > 1:
                pos = visible.find(paragraph)
                issues.append(Issue(
                    path, _line(visible, max(0, pos)),
                    "问题分析把多个子问题挤在同一自然段；应按问题分别说明难点、关键关系和建模路线",
                ))
    for match in RESULT_LEAK_RE.finditer(visible):
        issues.append(Issue(path, _line(visible, match.start()),
                            "问题分析提前写入最终数值；此处只说明建模理由与求解思路，答案留到结果部分"))
    return issues


def _check_monotonicity(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []
    for paragraph in re.split(r"\n\s*\n|(?<=[。；])", strip_nonspeech(text)):
        claim = MONOTONE_CLAIM_RE.search(paragraph)
        if not claim:
            continue
        # Descent of an iterative algorithm is not a comparison of feasible
        # sets across problems. Missing proof keywords are not a disproof.
        if not re.search(r"可行域|可行集|跨问题|问题[一二三四五六七八九十\d]+.*问题", paragraph):
            continue
        if not (STRICT_INCLUSION_RE.search(paragraph)
                and SAME_OBJECTIVE_RE.search(paragraph)
                and PROOF_CUE_RE.search(paragraph)):
            issues.append(Issue(
                path, _line(text, text.find(paragraph) if paragraph in text else 0),
                "跨问题最优值比较需核对可行域包含、变量对应及相同目标；非严格包含可支持不劣，严格包含本身也不保证严格更优，请结合证明核实",
                "warning",
            ))
    return issues


def _check_typography_and_punctuation(path: Path, text: str) -> list[Issue]:
    issues: list[Issue] = []
    if APPENDIX_RE.search(path.name):
        return issues
    speech = strip_nonspeech(text, keep_math=False)
    for match in re.finditer(r"\\texttt\s*\{", speech):
        issues.append(Issue(path, _line(speech, match.start()),
                            "中文正文使用等宽体强调；文件名应移出正文，普通强调统一使用少量黑体加粗"))
    for match in re.finditer(r"（[^（）\n]*\)|\([^()\n]*）", speech):
        issues.append(Issue(path, _line(speech, match.start()), "中文括号左右样式不一致（半括号）"))
    if speech.count("（") != speech.count("）"):
        issues.append(Issue(path, 1, "中文全角括号数量不平衡，请补齐或改写为完整句"))
    if speech.count("(") != speech.count(")"):
        issues.append(Issue(path, 1, "半角括号数量不平衡，请补齐；中文叙述优先使用成对全角括号"))
    if re.search(r"（[^（）\n]*（|）[^（）\n]*）", speech):
        issues.append(Issue(path, 1, "正文存在嵌套中文括号；主要论点应移出括号单独成句"))
    cjk_count = len(re.findall(r"[\u3400-\u9fff]", speech))
    dash_count = speech.count("——")
    dash_limit = max(2, (cjk_count + 2999) // 3000 * 2)
    if dash_count > dash_limit:
        issues.append(Issue(path, 1, f"正文使用 {dash_count} 处双破折号，超过当前篇幅建议上限 {dash_limit}；优先拆句"))
    for paragraph in re.split(r"\n\s*\n", speech):
        cjk = len(re.findall(r"[\u3400-\u9fff]", paragraph))
        # LaTeX reference keys routinely contain colons (fig:q1, eq:model,
        # tab:result).  They are identifiers, not reader-facing punctuation,
        # and counting them caused valid mathematical prose to be rewritten.
        prose_punctuation = re.sub(
            r"\\(?:eqref|ref|autoref|cref|Cref|label)\s*\{[^{}]*\}",
            "",
            paragraph,
        )
        prose_punctuation = re.sub(r"https?://\S+", "", prose_punctuation)
        colon_count = prose_punctuation.count("：") + prose_punctuation.count(":")
        if cjk >= 80 and colon_count >= 3:
            pos = speech.find(paragraph)
            issues.append(Issue(path, _line(speech, max(0, pos)),
                                f"同一自然段出现 {colon_count} 个冒号，疑似标签式堆叠；改成完整句或真正的总分结构"))
    return issues


def find_targets(paper_dir: Path) -> list[Path]:
    candidates = ([paper_dir / "main.md"] if (paper_dir / "main.md").is_file()
                  and not (paper_dir / "main.tex").is_file() else active_sources(paper_dir))
    return [path for path in candidates if path.is_file() and not path.name.startswith("_")]


def check(paper_dir: Path) -> list[Issue]:
    targets = find_targets(paper_dir)
    payloads = [(path, path.read_text(encoding="utf-8", errors="ignore")) for path in targets]
    all_text = "\n".join(text for _, text in payloads)
    expected = _expected_problems(all_text)
    issues: list[Issue] = []
    if len(expected) >= 2:
        analysis_headings = _analysis_heading_problems(all_text)
        missing_headings = sorted(expected - analysis_headings)
        if missing_headings:
            label = "、".join(str(item) for item in missing_headings)
            anchor = next(
                (path for path, text in payloads if _is_standalone_analysis(path, text)),
                targets[0],
            )
            issues.append(Issue(
                anchor,
                1,
                f"问题分析缺少按题号设置的小节标题：问题 {label}；请使用“2.1 问题一的分析”等真实标题逐问组织，不能只在段落中提到题号",
            ))
    for path, text in payloads:
        kind = _kind(path, text)
        if kind == "restatement":
            section = _named_section(text, r"问题重述|题目重述") if path.stem.lower() == "main" else None
            issues.extend(_check_restatement(path, section if section is not None else text))
        elif kind == "analysis":
            section = _named_section(text, r"问题分析|赛题分析") if path.stem.lower() == "main" else None
            analysis_text = section if section is not None else text
            issues.extend(_check_analysis(
                path,
                analysis_text,
                expected,
                enforce_coverage=_is_standalone_analysis(path, text),
            ))
        # A monolithic main.md/main.tex contains both sections.  Classifying
        # the file as one or the other would silently skip the second section.
        if path.stem.lower() == "main":
            restatement = _named_section(text, r"问题重述|题目重述")
            analysis = _named_section(text, r"问题分析|赛题分析")
            if restatement is not None and kind != "restatement":
                issues.extend(_check_restatement(path, restatement))
            if analysis is not None and kind != "analysis":
                issues.extend(_check_analysis(path, analysis, expected))
        issues.extend(_check_monotonicity(path, text))
        issues.extend(_check_typography_and_punctuation(path, text))
    return issues


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("paper_dir", nargs="?", default="paper")
    args = parser.parse_args(argv)
    paper_dir = Path(args.paper_dir)
    targets = find_targets(paper_dir)
    if not targets:
        print("  (未找到论文正文，跳过人类作者文风检查)")
        return 0
    issues = check(paper_dir)
    if not issues:
        print("  OK: 问题重述、问题分析、数学结论与正文标点符合读者文稿规范")
        return 0
    errors = [issue for issue in issues if issue.severity == "error"]
    print(f"  {'FAIL' if errors else 'WARN'}: 文稿检查 {len(errors)} 项明确问题，{len(issues)-len(errors)} 项待核实")
    for issue in issues[:16]:
        print(f"    - {issue.severity}: {issue.path}:{issue.line}: {issue.message}")
    if len(issues) > 16:
        print(f"    - 其余 {len(issues) - 16} 项已省略")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
