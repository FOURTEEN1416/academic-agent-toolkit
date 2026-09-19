"""技能路由回归（吸收同类项目的"触发词测试法"并机械化，2026-09-19 建立）。

**背景**：Claude 技能规范要求每个技能准备"3-5 条应触发的提示 + 2-3 条不应触发的提示"，
但没说怎么在 CI 里跑。本文件把它落成**词法路由回归**：用 `skill_trigger_audit.route()`
（中文 2-3 字 n-gram + 英文词元，按重叠/√描述长度 打分）对固定查询集做排序断言。

**诚实边界（必须随测试一起读）**：宿主真实路由是语义的，本文件测的是**词法可分性**——
正确路由的必要条件而非充分条件。词法都分不开的一对，语义路由必然摇摆；词法分开
不等于语义一定分对。因此：
  - "应正确路由"的查询必须是**词法上可判**的（含该技能独有词汇），不写语义擦边题；
  - **词法不可分的对**登记在 `KNOWN_LEXICAL_LIMITS`（清单制，新增必须显式登记，
    不许悄悄放过）——与仓库既有的"断链棘轮/ASSET-GAP 清单制"同一纪律；
  - 权威路由通道始终是引擎 StepAction 显式下发 skill_path（见 P4 技能绑定），
    描述匹配只是第二通道。

**本轮实测发现的真问题（记录在案，不是猜测）**：
上一轮为消除路由二义，给 `humanities-write` 加了"需 LaTeX/PDF 交付时改用
humanities-write-latex"这类判别句——判别句**必然把对手的词汇引进自己的描述**
（"LaTeX"进了 humanities-write 的描述），于是含 LaTeX 的请求反而更可能命中
humanities-write。这是判别句的固有代价：可读性/可解释性换词法可分性。
故本项目选择"判别句 + 显式绑定"双轨，而不是追求描述层面的完全可分。
"""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))

import skill_trigger_audit as sta  # noqa: E402

RECORDS = sta.audit_skills(ROOT / "skills")["records"]

# ── 应正确路由的查询（词法可判；rank 1 必须是指定技能） ────────────────────
SHOULD_ROUTE: tuple[tuple[str, str], ...] = (
    ("帮我编译中文论文，输出PDF", "paper-compile-zh"),
    ("我要做PPT演讲幻灯", "paper-slides"),
    ("打开 docx 模板识别占位", "docx-template-map"),
    ("英文竞赛论文 docx 模式产出 main.md", "comp-paper-en-docx"),
    ("照着这张图复现配色和字体", "plot-from-image"),
    ("灰度打印要可读的配色方案", "paper-figure-palette"),
    ("论文段落改写法 UCSB 中心句", "paper-writing-ucsb"),
    ("中文论文大纲规划", "paper-plan-zh"),
    ("赛后复盘把教训写进项目", "contest-retrospective"),
    ("AI 工具使用详情申报四节怎么写", "comp-cumcm-disclosure"),
)

# ── 词法不可分的对（清单制：新增必须显式登记，附不可分原因） ────────────────
KNOWN_LEXICAL_LIMITS: tuple[tuple[str, str, str], ...] = (
    ("humanities-write", "humanities-write-latex",
     "判别句互引导致词法互染：前者为说明边界而写了 LaTeX，反被含 LaTeX 的请求命中"),
    ("sci-latex-posters", "paper-poster",
     "同域海报技能，词汇几乎完全重叠；靠 StepAction 绑定与 SKILL.md 边界判别"),
    ("auto-review-loop-llm", "auto-review-loop-minimax",
     "除 API 厂商名外描述同构；查询含明确厂商名时可分，不含时不可分"),
    ("paper-write-docx", "paper-write-zh-docx",
     "两变体描述同构，且中文论文类请求被短描述高频词的 paper-plan-zh 持续抢分"),
    ("paper-write-nature-docx", "paper-write-zh-docx",
     "同为 docx 变体，仅风格/语言前缀不同；靠判别句与 StepAction 绑定区分"),
    ("paper-write-docx", "paper-write-nature-docx",
     "同上：判别句互引的风格名（Nature）会进入对方词表，属判别句固有代价"),
)

# ── 词法可分的歧义对（必须给出"判别查询"并验证能正确排序） ──────────────────
# 未登记为 limit 的候选对，必须在这里给出可判查询——否则等于"承认不可分却不登记"。
SEPARABLE_PAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("comp-paper-en-docx", "comp-paper-zh-docx",
     "英文竞赛论文 docx 模式产出 main.md", "comp-paper-en-docx"),
    ("paper-plan", "paper-plan-zh",
     "中文论文大纲规划", "paper-plan-zh"),
)


def _rank1(query: str) -> str | None:
    hits = sta.route(query, RECORDS, top_k=1)
    return hits[0]["skill"] if hits else None


def _rank(query: str, skill: str) -> int | None:
    hits = sta.route(query, RECORDS, top_k=200)
    for i, hit in enumerate(hits, 1):
        if hit["skill"] == skill:
            return i
    return None


# ── 正向：词法可判的请求必须命中正确技能 ────────────────────────────────────

@pytest.mark.parametrize("query,expected", SHOULD_ROUTE)
def test_query_routes_to_expected_skill(query: str, expected: str) -> None:
    # 公开 clone 不交付被根 .gitignore 隔离的技能（无 License 上游件）——
    # 该目标的"必须命中"用例无从验证，按语义 skip；其余用例仍严格校验，
    # 不放宽 _rank1 判据本身。
    if expected not in RECORDS:
        pytest.skip(f"非完整本地仓：技能 {expected} 不随公开仓交付")
    assert _rank1(query) == expected, f"{query!r} → {_rank1(query)!r}，期望 {expected!r}"


def test_empty_query_returns_no_route() -> None:
    assert sta.route("", RECORDS) == []
    assert sta.route("。。。", RECORDS) == []


# ── 负向：词法不可分的对必须有登记，且**新出现的不可分对会被拦下** ───────────

@pytest.mark.parametrize("a,b,reason", KNOWN_LEXICAL_LIMITS)
def test_known_lexical_limits_are_registered(a: str, b: str, reason: str) -> None:
    """登记项必须真实存在且理由非空（防"登记一个不存在的豁免"）。"""
    assert a in RECORDS and b in RECORDS, (a, b)
    assert reason.strip()


def test_every_ambiguous_pair_is_classified() -> None:
    """审计认定的歧义候选对必须**二分完毕**：要么登记为词法不可分，要么给出可判查询。

    这条把"新出现的歧义对"逼到台面上：既不许当不可分放过，也不许假装可分。
    """
    res = sta.run()
    candidates = {tuple(sorted((i["a"], i["b"]))) for i in res["overlap_candidates"]}
    limits = {tuple(sorted((a, b))) for a, b, _ in KNOWN_LEXICAL_LIMITS}
    separable = {tuple(sorted((a, b))) for a, b, _q, _w in SEPARABLE_PAIRS}
    unclassified = candidates - limits - separable
    assert not unclassified, (
        f"存在未分类的歧义候选对（须登记为词法不可分，或补一条可判查询）: {sorted(unclassified)}")


@pytest.mark.parametrize("a,b,query,winner", SEPARABLE_PAIRS)
def test_separable_pairs_have_working_discriminator_query(a, b, query, winner) -> None:
    """登记为"词法可分"的对，其判别查询必须真的把正确的那个排到前面。"""
    assert _rank1(query) == winner, f"{query!r} → {_rank1(query)!r}，期望 {winner!r}"
    # 分离性断言：赢家必须**严格高于**对手；对手完全不进候选（零重叠）同样算分离。
    scores = {h["skill"]: h["score"] for h in sta.route(query, RECORDS, top_k=200)}
    rival = b if winner == a else a
    assert scores.get(winner, 0) > scores.get(rival, 0),         f"{query!r}: {winner}={scores.get(winner)} 未高于 {rival}={scores.get(rival)}"


def test_discriminator_clause_is_present_in_descriptions() -> None:
    """登记为"词法不可分"的对，必须在描述层保判别句（词法靠不住时靠人读/引擎绑定）。"""
    import re
    for a, b, _reason in KNOWN_LEXICAL_LIMITS:
        for name, rival in ((a, b), (b, a)):
            desc = RECORDS[name]["description"]
            assert re.search(r"只(用于|做|产出|交)|改用|区别于|而非|不用", desc), \
                f"{name} 缺判别句（对手 {rival}）"


# ── 打分口径 ────────────────────────────────────────────────────────────────

def test_route_tokens_expands_chinese_ngrams() -> None:
    """中文按 2-3 字滑窗展开：同一短语的不同切法必须产生交集。"""
    a = sta.route_tokens("编译中文论文")
    b = sta.route_tokens("帮我编译中文论文并输出")
    assert {"编译", "译中", "中文", "文论", "论文"} <= a
    assert a & b, "不同切法应至少有一个共同词元"


def test_route_tokens_keeps_english_words() -> None:
    assert "minimax" in sta.route_tokens("用 MiniMax 审稿")
    assert "docx" in sta.route_tokens("导出 DOCX")


def test_route_prefers_specific_over_verbose() -> None:
    """计分除以 √描述长度：长描述不得仅靠"词多"压倒精准短描述。"""
    hits = sta.route("docx 模板占位", RECORDS, top_k=5)
    assert hits[0]["skill"] == "docx-template-map"


# ── 词法黑洞回归（IDF 加权） ────────────────────────────────────────────────

def test_high_frequency_terms_do_not_black_hole() -> None:
    """IDF 回归：短描述 + 高频词密集的技能，不得对任意中文论文类请求抢分。

    实测背景：加 IDF 之前，`paper-plan-zh`（描述短、「中文/论文」密集）对
    「把报告写成英文论文 docx 草稿」这类与它无关的请求也排第一——纯重叠计分
    识别不出"这个词人人都写"。IDF 把高频词权重压到趋近 1 后该现象消失。
    本测试把结论钉住：**无论将来怎么调权重，这条不许回退**。
    """
    for query in ("把报告写成英文论文 docx 草稿", "帮我做一张A0会议海报"):
        assert _rank1(query) != "paper-plan-zh", f"{query!r} 又被 paper-plan-zh 抢分"


def test_idf_prefers_rare_terms() -> None:
    """稀有词必须压过高频词：含 UCSB 的请求只有 paper-writing-ucsb 能命中。"""
    hits = sta.route("论文段落改写法 UCSB 中心句", RECORDS, top_k=1)
    assert hits[0]["skill"] == "paper-writing-ucsb"
    assert "ucsb" in hits[0]["matched"], hits[0]["matched"]


def test_ambiguity_tokenize_unchanged_by_route_tokens() -> None:
    """两套词元口径各司其职：歧义检测用 tokenize（已标定），不得被 route_tokens 顶替。"""
    res = sta.run()
    assert res["thresholds"]["min_jaccard"] == 0.30
    assert res["thresholds"]["min_shared"] == 6
    # tokenize 仍是贪婪 2-4 字块口径（"编译中文论文" → 「编译中文」+「论文」）
    assert "编译中文" in sta.tokenize("编译中文论文")
