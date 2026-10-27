#!/usr/bin/env python3
"""论文正文「AI 痕迹措辞」审计闸。

用法:
  python ai_tell_check.py                 # 在工作区根目录跑，自动找 paper/
  python ai_tell_check.py paper/main.md   # 指定文件
  python ai_tell_check.py --strict        --strict 下剩余空话（由此可见/换言之等）也计入失败

退出码: 0=干净  1=查出禁用语汇(必修)  2=没找到正文文件(跳过不阻塞)

⛔ 为什么需要这个闸：这类词是【内部工程/质检语汇】，从流水线提示词流进论文正文。
   实测 10 个真实工作区命中 442 次，「口径」单独 225 次——是所有 AI 痕迹里最密集的一类。
   人工通读会漏（单篇最高 96 次），必须机器扫。
   中文套话（值得注意的是/综上所述/不难发现/显而易见/在此基础上/随着…的发展）
   2026-10-01 起与工程词同级硬拦——评审把这类开头直接判为 AI 痕迹，技能文档不再教、正文不得用。
   同日二批校准（一手证据：《AI 论痕检测提示词 V5.0》附录A、《降重与降低AI味讲义》§3.6 套话表、
   真实检测报告 P-003/P-004/P-008/P-009）：新增硬拦 众所周知/毋庸置疑/需要指出的是/国奖，
   新增模式「具有良好××」「等显著优点」「建立了完整的」「元注释残留」。
   ⛔ 反证不入表：「本文」「针对问题k」「进行+名词」「进一步」「证实了模型的准确性」经
   award-paper-mining/data 获奖论文句式库证实是获奖论文正当句式（8/8、4/8、75% 等出现率），永不硬拦。
   ⛔ 三批语料反证（2026-10-01，assets-local/award-papers 735 篇真实获奖论文 PDF 全量扫描）：
   链路/上游/下游/流水线/复用/闭环/落地/抓手/工作流/口径 在获奖论文中大量作
   【字面义领域术语】（通信链路与链路预算 38 篇、河流上下游 84 篇、频谱复用 34 篇、闭环控制
   19 篇、各维度上 54 篇、机械臂末端抓手、生产流水线调度、落地点坐标），
   词级硬拦属误伤（替代写法会把领域正确句子改错）——收窄为只拦工程泄漏构式，字面义放行。
   维度上/修正项 经同批反证（各维度上 54 篇、误差修正项 ECM 标准术语 11 篇）无干净构式
   可区分工程泄漏与领域正用，整体放行、不作机检硬拦（写作侧仍建议优先「在……方面」「修正量」）。
   「Agent/Skill」内部标记排除 Multi-Agent 仿真术语（2015 A题「Multi-Agent 火力分配」48 次）；
   「口径」放行 统计口径/数据口径/大口径/小口径（统计类论文标准术语，25 篇）；参考文献区
   （被引文献标题非作者所能改写）不再扫描。批二模式（建立了完整的/具有良好××/随着…的发展）
   在真实论文中确有用例（47/6/150 处），但其替代写法保义、属策略性收紧，维持硬拦。

⛔ 全标准库实现，与项目其它 tools 一致，不引第三方。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


sys.path.insert(0, str(Path(__file__).resolve().parent))
from paper_source_scope import active_sources, strip_comments

# ⛔ 强制 UTF-8 输出：Windows 控制台默认 GBK，重定向到文件后中文与 ❌ 变成 GBK 字节，
#    调用方用 grep 按 UTF-8 找就全落空（实测 writing_check.sh 因此只打印提示、丢了明细）。
#    在脚本内部解决，这样无论调用方有没有加 -X utf8 都正确。
for _s in (sys.stdout, sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError):
        pass

# ===== 硬拦项：工程/质检语汇（词 → 学术替代）=====
# ⛔ 三批校准（735 篇真实获奖论文反证）：字面义领域术语（口径的统计口径义、闭环的闭环控制义、
#    上下游的河流/交通流义、链路/复用/落地/抓手/工作流/流水线同理）不再词级硬拦，
#    移至 BANNED_PATTERNS 只拦工程泄漏构式；维度上/修正项（各维度上 54 篇、误差修正项 11 篇）
#    无干净构式可辨、整体放行。此处仅保留无字面义冲突或替代写法保义的词。
BANNED = {
    "台账": "汇总表 / 一览表",
    "自检": "校验 / 一致性检验 / 复核",
    "对账": "核对 / 一致性检验",
    "兜底": "缺省处理 / 默认取值",
    "回填": "补充取值 / 反向代入",
    "打通": "贯通 / 衔接",
    "拉齐": "统一 / 一致化",
    "颗粒度": "粒度 / 精细程度 / 分辨率",
    "赋能": "（删改为具体说法）",
    "约束验证": "（删去验收式标题；把有意义的余量自然写入结果讨论）",
    "约束校验": "可行性分析 / 容量余量 / 误差范围",
    "代码内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "代码中内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "程序中内置": "（删去实现痕迹，直接陈述方法或观察到的结果）",
    "内置断言": "（删去实现痕迹，直接陈述参数变化规律）",
    "可证伪断言": "敏感性分析 / 参数变化规律",
    "可证伪的有效性保证": "误差分析 / 参数变化规律 / 适用范围",
    "铁证": "证据 / 结果表明（优先直接陈述具体事实）",
    "降维失败": "近似偏差 / 模型偏离题意",
    "质量门": "（正文删除；仅保留内部报告）",
    "能力审计": "（正文删除；仅保留内部报告）",
    "能力项": "（正文删除；直接陈述模型、方法或结果）",
    "验收项": "（正文删除；直接陈述模型、方法或结果）",
    "能力验收": "（正文删除；仅保留内部报告）",
    "运行时断言": "（正文删除；直接陈述数学关系或数值现象）",
    "健康阈值": "阈值 / 判定界限（仅在确有数学含义时保留）",
    "审计报告": "（正文删除；仅保留内部报告）",
    "审计状态": "（正文删除；仅保留内部报告）",
    "审计项": "（正文删除；直接陈述检查对象）",
    "任务返修": "（正文删除；修改过程不得写入论文）",
    "返修记录": "（正文删除；修改过程不得写入论文）",
    "自动返修": "（正文删除；修改过程不得写入论文）",
    "零越界": "未超过容量上限，并给出最大利用率或余量",
    "全流程校验": "（删去验收流程，直接陈述误差、余量或适用范围）",
    "constraint validation passed": "report the concrete feasibility margin or residual",
    "all checks passed": "remove the log-style statement and discuss only informative results",
    "built-in assertion": "state the observed parameter trend without implementation details",
    "audit passed": "remove the internal audit status",
    "quality gate": "remove from the paper; keep only in the internal report",
}

# ===== 硬拦项：中文套话（与工程词同级；2026-10-01 从 SOFT 升级，评审实锤判 AI 痕迹）=====
BANNED.update({
    "值得注意的是": "（删去，直接陈述事实）",
    "综上所述": "（删去；确需收束时陈述具体结论，如「以上结果表明……」）",
    "不难发现": "（删去，直接给出观察与数值）",
    "显而易见": "（删去；结论需要理由就给理由，不需要就整句删）",
    "在此基础上": "（写明衔接的具体对象，如「在去噪后的位移序列上」）",
    # —— 2026-10-01 二批（V5.0 附录A 阈值>0/>1 次；检测报告 P-003/P-004 元注释残留实锤）：
    "需要指出的是": "（删去，直接陈述事实）",
    "众所周知": "（删去；确需交代背景就注明依据，如「文献[2]指出……」）",
    "毋庸置疑": "（删去，直接给出依据）",
    "国奖": "（删除评奖对标/自评话术，改述具体检验结论，如误差大小与扰动范围）",
})

# ===== 硬拦项：正则类套话（dict 只收字面量，模式类单列；display 用于输出可读性）=====
BANNED_PATTERNS = [
    (r"随着.{0,16}的(?:快速)?发展", "随着…的发展",
     "（删去套话开头，首句直接给现实矛盾、数据或问题对象）"),
    # —— 2026-10-01 二批：一手资料点名的模式类套话（讲义 §3.6 套话表；检测报告 P-001/P-008/P-009）
    (r"(?:模型|方法|算法|方案)具有良好(?:的)?(?:性能|效果|鲁棒性|稳健性|适应性|可靠性|有效性|泛化能力|可推广性|推广价值)",
     "「具有良好××」空泛评价",
     "（给出具体指标与扰动范围，如「参数±20%扰动时前三名不变」）"),
    (r"等(?:显著|突出|明显)优点", "「等显著优点」标签式自夸",
     "（删去「显著优点」标签，直接列举优势或给具体数字）"),
    (r"(?:建立|构建)(?:了)?(?:一个)?完整(?!性)(?:的)?", "「建立了完整的」自夸修饰",
     "（删去「完整的」，直接写模型包含哪些部分，如「建立了包含A、B、C三部分的××模型」）"),
    (r"核心分水岭|评分点", "写作元注释残留",
     "（删除——写作提示/评分话术不得出现在成稿正文）"),
    # —— 2026-10-01 三批：735 篇真实获奖论文 PDF 反证后，把原词级硬拦的领域多义词收窄为
    #    「只拦工程泄漏构式」；括注的字面义在真实论文中大量出现且替代写法会改错句，放行。
    (r"(?:全|决策|信任|责任|价值|业务)链路|链路(?:的)?(?:打通|贯通|拉通)", "「链路」隐喻义",
     "（写明具体的模块间传递关系；通信链路、链路预算、传动链路等字面义不受限）"),
    (r"(?:本文|我们)(?:的)?流水线|(?:建模|写作|审计|质检|评估|生成)流水线|流水线(?:分为|分成|思维|化管理|化)", "「流水线」自指处理流程",
     "（改述具体计算流程与步骤；生产流水线、多级流水线、流水线调度/级数/包含的基本块等字面义不受限）"),
    (r"(?:代码|模块|函数|程序|脚本|结论|结果|参数|变量|框架|逻辑|设计|组件)(?:的)?复用|复用(?:已有|现有|之前|先前|原来|历史|旧|上述|该|其)", "「复用」工程义",
     "（写明沿用对象，如「沿用问题二的约束」；频谱复用、正交频分复用、特征复用等术语不受限）"),
    (r"(?:业务|商业|管理|质量|工作|服务|生态|监督|考核)闭环|反馈闭环|闭环(?:管理|思维|生态|运作|体系)", "「闭环」管理比喻义",
     "（写明具体的反馈步骤；闭环控制、路线成闭环等字面义不受限）"),
    (r"(?:方案|项目|成果|模型|算法|政策|策略|技术|系统|规划|措施|举措)(?:得以|成功)?(?:的)?落地|推动(?:快速)?落地|落地(?:实施|应用|生效|推广|建成)", "「落地」工程比喻义",
     "（写明具体实现或应用；落地点、落地浓度、落地时间等字面义不受限）"),
    (r"(?:核心|关键|主要|有力|重要|监管|治理|服务|工作)(?:的)?抓手", "「抓手」比喻义",
     "（删去比喻，直接写具体措施；机械臂末端抓手等字面义不受限）"),
    (r"工作流(?!程)", "「工作流」工程义",
     "（写明研究/计算过程；「工作流程」指算法流程图时不受限）"),
    (r"(?:模块|服务|接口|环节|流程|阶段|数据流)(?:的)?(?:上游|下游)", "「上游/下游」流程环节义",
     "（写明具体输入来源或输出去向；河流、交通流、产业链上下游不受限）"),
    (r"(?<!统计)(?<!数据)(?<!大)(?<!小)口径", "「口径」质检义",
     "（定义 / 取法 / 计算方式 / 统计范围；统计口径、数据口径、大/小口径等字面义不受限）"),
]

# ===== 硬拦项：内部标记 =====
MARK_PATTERNS = [
    (r"[⛔✅❌⚠]", "内部标记符号"),
    (r"\b(?:RESULTS|PARAMS_RAW|MODELING_REPORT|PROBLEM_ANALYSIS|AUDIT_REPORT|"
     r"COMPILE_REPORT|PAPER_MODELING_QUALITY_REPORT|CAPABILITY_AUDIT)\.md\b",
     "内部文件名"),
    (r"\bCAPABILITY_CHECKLIST(?:\.json)?\b", "内部文件名"),
    (r"\bMETHOD_CLAIMS\b", "内部标记"),
    (r"\bHC-\d+", "内部质检编号"),
    (r"\bP\d+[-_]C\d+(?:[-_]\d+)?\b", "内部能力编号"),
    # ⛔ 三批校准：Multi-Agent/演化Agent/基于Agent/裸 Agent 是获奖论文的 ABM 标准术语
    #    （2015 A题实锤 48 次），Skill Score/HSS 是标准验证指标，被引标题含 Skills（2023 C题实锤）；
    #    故仅当机器语境（编排/调用/提示词等）邻近时才拦，其余放行。
    #    ⛔ 词尾不能写 \b：CJK 是 Python re 的 \w 词字符，「Agent编排」在 t|编 之间无边界面
    #    永不匹配（独立复核实测漏检）；用 (?![A-Za-z]) 判词尾，CJK 邻接同样进入语境检查。
    (r"\b(?:Agent|Skill)s?(?![A-Za-z])(?!\s*[Ss]core)(?=[^\n]{0,16}(?:编排|调用|执行任务|提示词|工作流|自动审查|自动改写|自动撰写))",
     "智能体内部术语"),
    (r"\b(?:validate(?:_|\\_)constraints|validate(?:_|\\_)storage|monotonicity(?:_|\\_)check)\b",
     "内部检查函数名"),
    (r"\bok\s*=\s*true\b", "内部通过状态"),
    (r"(?:约束|程序|代码|断言|检查|自检).{0,12}(?:全部|均)(?:通过|成立)",
     "验收式通过结论"),
]

# ===== 仅警告项：剩余空话（--strict 时计入失败；前两批套话已升硬拦）=====
# 具有重要意义：讲义 §3.4/§3.6 万能结尾组件；范式：讲义 §3.6「研究范式/发展范式」常被滥用。
SOFT = ["由此可见", "换言之", "具有重要的理论意义", "具有重要意义", "创新性地", "深入探讨", "范式"]

# ⛔ 只扫论文正文；报告/审计/清单类文件本就该用工程语汇，扫它们是误报
EXCLUDE_NAME = re.compile(
    r"REPORT|AUDIT|CHECK|TODO|PROFILE|LEDGER|MANIFEST|CHECKLIST|VERDICT"
    r"|ANALYSIS|PARAMS|RESULTS|README|_writing_context", re.I)

# ⛔ 三批校准（735 篇真实获奖论文反证）：参考文献区是被引文献的标题/出处，措辞非作者所能改写
#    （实测 2024/2025 年获奖论文引用标题含「赋能」等词），从该区起不再扫描。只认整行标题行，
#    正文提及「详见参考文献[3]」不受影响。
REF_SECTION = re.compile(
    r"\\begin\{thebibliography\}|\\bibliography(?:\{|\[)|\\printbibliography"
    r"|\\section\*?\{参考文献\}"
    r"|^[>#\s*]*(?:参考文献|References|Bibliography|REFERENCES)\s*$", re.M)


def _discover_dir(d: Path) -> list[Path]:
    """把目录参数展开为正文文件清单（工作区根 / paper 根 / sections 目录均可）。

    2026-10-02 修复：目录形态参数（如 SKILL.md 教的 `--strict paper/`）此前被
    「只认文件」过滤整批丢弃 → targets 为空 → exit 2 且一行"未找到正文"——
    真实工作区实测闸门零扫描（终稿 12 处 AI 痕迹因此漏拦进交付物）。
    目录与文件参数同等对待：目录递归发现正文，口径与无参 paper_mode 一致
    （_ 开头工作文件排除；paper 语义内 2_analysis.tex 等合法正文不按文件名排除）。

    防误用（2026-10-02 复核补）：在无 paper/ 子目录的大目录（如仓库根）会递归
    吸入全部 SKILL.md/文档（实测 1763 文件 20s 跑不完）——非 paper 语义目录
    应用 EXCLUDE_NAME 排除（对齐无参根目录口径），且候选超 MAX_DIR_TARGETS
    时拒绝扫描并指引正确用法。
    """
    MAX_DIR_TARGETS = 300
    has_paper = (d / "paper").is_dir()
    paper = d / "paper" if has_paper else d
    if (paper / "main.tex").is_file():
        try:
            srcs = active_sources(paper)
        except Exception:
            srcs = []
        if srcs:
            return srcs
    if (paper / "main.md").is_file():
        return [paper / "main.md"]
    out = []
    for pat in ("*.md", "*.tex"):
        for f in sorted(paper.rglob(pat)):
            if f.name.startswith("_"):
                continue
            # 非 paper 语义目录（用户直接传散文件目录/仓库根）按无参根目录口径
            # 排除报告/审计类工程文件；paper 语义内 2_analysis.tex 等是合法正文不排。
            if not has_paper and EXCLUDE_NAME.search(f.name):
                continue
            out.append(f)
    if len(out) > MAX_DIR_TARGETS:
        print("⚠ 目录 %s 递归发现 %d 个候选正文（>%d）——疑似传错目录："
              "请传工作区根、paper/ 目录或具体正文文件后重试。" % (d, len(out), MAX_DIR_TARGETS),
              file=sys.stderr)
        return []
    return out


def find_targets(args_paths):
    if args_paths:
        out = []
        for p in args_paths:
            pth = Path(p)
            if pth.is_file():
                out.append(pth)
            elif pth.is_dir():
                out.extend(_discover_dir(pth))
        # 去重保序
        seen, uniq = set(), []
        for f in out:
            k = f.resolve()
            if k not in seen:
                seen.add(k)
                uniq.append(f)
        return uniq
    # ⛔ 有 paper/ 就【只】扫 paper/，不要回落到根目录：
    #    根目录散落着 _format_reference.md、_s123.md 这类工作文件，
    #    它们本就该用工程语汇，扫了全是误报（实测踩到）。
    paper_mode = Path("paper").is_dir()
    if paper_mode and Path("paper/main.tex").is_file():
        return active_sources(Path("paper"))
    if paper_mode and Path("paper/main.md").is_file():
        return [Path("paper/main.md")]
    dirs = [Path("paper")] if paper_mode else [Path(".")]
    if not paper_mode:
        # ⛔ 治理文档哨兵：无 paper/ 且顶层有仓库治理文件 → 大概率是仓库根，
        #    无参扫描会把 AGENTS.md 等工程文档当论文正文判（实测误报 exit 1）。
        governance = [n for n in ("AGENTS.md", "CONTEST_SKILL_MAP.md", "README.md")
                      if (Path(".") / n).is_file()]
        if governance:
            print("⚠ 当前目录像是仓库/工程根（发现 %s）而非论文工作区——无参扫描会误把"
                  "治理文档当正文。请显式传入论文路径（paper/、工作区根或具体 .tex/.md 文件）。"
                  % "、".join(governance), file=sys.stderr)
            sys.exit(2)
    out = []
    for d in dirs:
        if not d.is_dir():
            continue
        for pat in ("*.md", "*.tex"):
            iterator = d.rglob(pat) if paper_mode else d.glob(pat)
            for f in sorted(iterator):
                # ⛔ 排除 _ 开头的临时/工作文件（_writing_context.md、_s123.md 等）
                # paper/ 内的 2_analysis.tex 等是合法正文，不得因文件名含 ANALYSIS 被误跳过。
                if f.name.startswith("_") or (not paper_mode and EXCLUDE_NAME.search(f.name)):
                    continue
                out.append(f)
    # 去重保序
    seen, uniq = set(), []
    for f in out:
        k = f.resolve()
        if k not in seen:
            seen.add(k)
            uniq.append(f)
    return uniq


def strip_noscan(text: str) -> str:
    """挖掉不该扫的区域，避免误报：
    ⛔ 代码块/lstlisting（附录贴的代码里出现 self_check 之类是正常的）
    ⛔ 注释（LaTeX % 与 Markdown <!-- -->）
    用等长空白替换，保持行号与列号不变。
    """
    def blank(m):
        return re.sub(r"[^\n]", " ", m.group(0))

    # ⛔ 先挖【更长的围栏】：Markdown 允许 ```` 包裹 ```，若先挖 ``` 会把外层拆散，
    #    残留的内层内容被当成正文（对抗测试实测误报）。从 6 个反引号往下试。
    for n in range(6, 2, -1):
        f = "`" * n
        text = re.sub(re.escape(f) + r".*?" + re.escape(f), blank, text, flags=re.S)
    for n in range(6, 2, -1):
        f = "~" * n
        text = re.sub(re.escape(f) + r".*?" + re.escape(f), blank, text, flags=re.S)
    # 未闭合围栏：从起始处挖到文末（否则后面全被当正文，或反之）
    text = re.sub(r"(?m)^\s*(?:`{3,}|~{3,}).*\Z", blank, text, flags=re.S)
    text = re.sub(
        r"\\begin\{(?P<env>lstlisting|verbatim|minted)\}.*?"
        r"\\end\{(?P=env)\}",
        blank,
        text,
        flags=re.S,
    )
    text = re.sub(
        r"\\verb\*?(?P<delim>[^A-Za-z0-9\s]).*?(?P=delim)",
        blank,
        text,
    )
    text = re.sub(r"<!--.*?-->", blank, text, flags=re.S)
    text = re.sub(r"`[^`\n]*`", blank, text)
    # LaTeX 行注释：% 前面不是 \（\% 是转义百分号）
    text = re.sub(r"(?<!\\)%[^\n]*", blank, text)
    return text


def scan(path: Path):
    try:
        raw = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return [], [], []
    txt = strip_noscan(raw)
    # ⛔ 参考文献区不扫：被引标题的措辞不可改（「赋能」等出现在引用标题里不是作者的错误）
    m_ref = REF_SECTION.search(txt)
    if m_ref:
        txt = txt[: m_ref.start()]
    lines = txt.split("\n")
    hard, marks, soft = [], [], []
    for i, ln in enumerate(lines, 1):
        for w, alt in BANNED.items():
            # ⛔ 同一行同一词出现多次时合并显示（×N），但计数按真实次数
            n = len(re.findall(re.escape(w), ln, flags=re.IGNORECASE))
            if n:
                hard.append((i, w, alt, ln.strip()[:70], n))
        for pat, disp, alt in BANNED_PATTERNS:
            n = len(re.findall(pat, ln))
            if n:
                hard.append((i, disp, alt, ln.strip()[:70], n))
        for pat, kind in MARK_PATTERNS:
            found = re.findall(pat, ln)
            if found:
                marks.append((i, found[0], kind, ln.strip()[:70], len(found)))
        for w in SOFT:
            if w in ln:
                soft.append((i, w, ln.strip()[:70]))
    return hard, marks, soft


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="*", help="要扫的文件或目录（paper/、工作区根均可，目录递归找正文）；缺省自动找 paper/")
    ap.add_argument("--strict", action="store_true", help="剩余空话（SOFT）也计入失败")
    ap.add_argument("--max-errors", type=int, default=0,
                    help="容许通过的最大命中数（默认 0=零容忍）。引擎闸定标：真实获奖论文"
                         "抽样 8 篇硬伤+空话 0-2 处/篇，阈值 3 ≈ 获奖水平上界（2026-10-02 实测）")
    ap.add_argument("--max-show", type=int, default=8, help="每类最多列几条")
    a = ap.parse_args()

    targets = find_targets(a.paths)
    if not targets:
        print("⚠ 未找到论文正文文件（paper/*.md 或 paper/sections/*.tex）— 跳过，不阻塞")
        sys.exit(2)

    tot_hard = tot_mark = tot_soft = 0
    wcount: dict[str, int] = {}
    print("=== AI 痕迹措辞审计 ===")
    print("扫描 %d 个正文文件（已排除代码块/注释/报告类文件）\n" % len(targets))

    for f in targets:
        hard, marks, soft = scan(f)
        if not (hard or marks or soft):
            continue
        print("--- %s ---" % f)
        for i, w, alt, ctx, n in hard[:a.max_show]:
            xn = ("×%d" % n) if n > 1 else ""
            print("  ❌ 第%d行 「%s」%s → 改为：%s" % (i, w, xn, alt))
            print("       %s" % ctx)
        if len(hard) > a.max_show:
            print("  … 另有 %d 行含禁用语汇" % (len(hard) - a.max_show))
        for i, sym, kind, ctx, n in marks[:a.max_show]:
            xn = ("×%d" % n) if n > 1 else ""
            print("  ❌ 第%d行 %s「%s」%s — 内部标记不得进正文" % (i, kind, sym, xn))
        if len(marks) > a.max_show:
            print("  … 另有 %d 行含内部标记" % (len(marks) - a.max_show))
        for i, w, ctx in soft[:3]:
            print("  ⚠ 第%d行 空话「%s」" % (i, w))
        print()
        tot_hard += sum(r[4] for r in hard)
        tot_mark += sum(r[4] for r in marks)
        tot_soft += len(soft)
        for r in hard:
            wcount[r[1]] = wcount.get(r[1], 0) + r[4]

    print("=== 汇总 ===")
    print("禁用语汇 %d 处 · 内部标记 %d 处 · 空话套话 %d 处（--strict 时计失败）"
          % (tot_hard, tot_mark, tot_soft))
    if wcount:
        top = sorted(wcount.items(), key=lambda kv: -kv[1])[:8]
        print("最多的词：" + "、".join("%s×%d" % (w, n) for w, n in top))

    fail = tot_hard + tot_mark + (tot_soft if a.strict else 0)
    if fail <= a.max_errors:
        if fail == 0:
            print("✅ PASS — 正文无 AI 痕迹措辞")
        else:
            print("✅ PASS（阈值内）— %d 处命中 ≤ 容许上限 %d（获奖论文水平）" % (fail, a.max_errors))
        sys.exit(0)
    print("\n⛔ 共 %d 处必修 — 逐条按替代说法改写，改完重跑本脚本。" % fail)
    print("   替代表见《shared-scripts/writing_rules.md》De-AI Polish 一节。")
    sys.exit(1)


if __name__ == "__main__":
    main()
