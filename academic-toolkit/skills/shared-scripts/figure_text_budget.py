# -*- coding: utf-8 -*-
"""图内文字预算闸 —— 抓"把整段说明画进图里"。

治的病（实测坐实）：25 个真实工作区 1015 个出图脚本里，`fig.text` 中位显示宽
**69**（约 35 个汉字）、64% 是成句长文；`ax.text`/`annotate` 另有 99 处长句。
这些字画在像素上，跟曲线柱子抢位置 —— 实测某工作区底部说明压 x 轴标签 44 处。

规范依据（各家一致）：
  - AIAA: "do not repeat all or part of the figure caption within the figure itself"
  - Nature figure guide: 图内只放轴标签/刻度/图例/panel 标号，且有字号下限
  - 常规做法: 面板标号用大写字母、不加框不加句点

判据（只抓"成句的长文本"，短标签一律放过）：
  1. 剥掉 mathtext（$...$）再量显示宽 —— 公式不是"一段话"，不能算违规
  2. 显示宽 > MAX_W（默认 24 ≈ 12 汉字）
  3. 且（含句读 或 显示宽 > 2*MAX_W）
豁免：面板标号、纯数值+单位、坐标轴/图例/标题（本来就该有字）

用法:
    python figure_text_budget.py [根目录] [--max-w 24] [--json] [--quiet]
退出码 0 = 无确定性违规，1 = 发现违规；运行异常另行报告，不按违规处数退出。
"""
import argparse
import ast
import json
import os
import re
import sys

CJK = re.compile(r'[一-鿿]')
# 句读：出现这些说明在"说话"，不是在"标注"
SENT_PUNCT = re.compile(r'[。；，、：？！;]')
# mathtext：$...$（跳过转义 \$）
MATH = re.compile(r'(?<!\\)\$.*?(?<!\\)\$', re.S)
# 面板标号：a / (a) / a. / A
PANEL = re.compile(r'^[\(\[]?[a-zA-Z][\)\]\.]?$')

# ── 数值标注白名单 ────────────────────────────────────────
# 判据：剥掉 mathtext 后，剩下的必须是"数值 (+单位)"，不能是词句。
# 允许：8188.06 / 45% / -0.5 pp / 1007 张 / 3.2e-4 / 120 dBm / n=30 / ≈0.47
# 拦掉：最优解 / 收敛区间 / 诊断结论：… / 任何成句
_NUM_CORE = r'[\d][\d,\s]*(?:\.\d+)?(?:[eE][+\-]?\d+)?'
# 中文单位【显式白名单】——⛔ 不能写成"≤3 个汉字"：
#   单位(元/张/人)和说明词(阈值线/最优解)都是 1-3 字，靠字数分不开。
#   实测 `ROI=3.0 阈值线` 会被"≤3 汉字"规则当成单位放行（漏判）。
_CN_UNITS = (
    '元万元亿元千元角分张人个次条只件台辆家户种类档级层组批轮期步代'
    '天年月日时秒毫秒微秒分钟小时周季度'
    '米千米公里厘米毫米微米纳米平米亩顷'
    '克千克吨斤两升毫升立方米'
    '度倍成位点单位样本人次万亿千百'
    '折票席局盘发枚束根支片块袋箱盒瓶罐幅面维阶'
    '行列格卡源核簇桶帧步轮迭种子'          # 从真实工作区统计补入的量词
)
# ⛔ 下列是【说明词不是单位】，别往白名单里加（真实数据里出现过，必须拦）：
#   执行 / 仿真 / 时谷 / 时峰 / 精度线 / 初始 / 阈值 / 均值 / 中位 / 临界点
# ⛔ 判据用【反面】写法，不要枚举数值的正面形状 ——
#   形状枚举不完：8188.06 / 45% / (9/20) / 3.2e-4 / n=30 / 0.5–1.2 元 / ±0.3 pp …
#   实测枚举版漏掉分数 `(9/20)`，而 `45%\n(9/20)` 是最常见的标注形态之一。
#   反面判定只问两件事：① 有没有数字 ② 有没有散文字符。稳健得多。
_DIGIT = re.compile(r'\d')
# 数值标注允许出现的非字母字符（含常见运算/区间/括号/上标）
# ⛔ 必须含【全角】标点与箭头：真实数据里 '$T_{M0}$=0 s　（…）' 的全角空格 U+3000、
#   '1-PER（M6-c）' 的全角括号、'0 → 0' 的箭头，都曾因不在白名单被判违规（误报 8/8）。
_NUM_PUNCT = set(
    ' \t\r\n.,;:%‰/\\|()[]{}<>=±+-–—~≈≤≥*^²³°′″\'"$&#@!?…·•'
    '　'                    # 全角空格
    '，。；：、（）【】《》〈〉「」『』〔〕％‰＋－＝×÷＜＞～'   # 全角标点
    '→←↑↓↔⇒⇐⇔∼≠≡∈∝∞'          # 箭头与数学关系符
    # ⛔ U+2212 MINUS SIGN「−」必须单列：它不是 ASCII '-'、也不是 en/em dash，
    #   中文排版里的正规负号就是它。缺了会把 '−2729 (0.55%)' 判成非数值（实测误报）。
    '−＋±×÷∕⁄'
)
# 单位里允许的 ASCII 字母串长度上限（dBm=3, mmol=4, count=5, kg=2, ms=2…）
_MAX_UNIT_LETTERS = 5

DEFAULT_MAX_W = 24          # 兼容旧调用；numeric-only 模式下不再作为主判据
# 限长档上限（≈18 汉字）：轴标签 / 标题 / 图例系列名 / 刻度标签
# ⛔ 36 不是拍脑袋 —— 量了 25 个真实工作区的分布定的：
#     set_xlabel n=491 中位15 P90=31 P95=36 最大70
#     set_ylabel n=517 中位13 P90=23 P95=27 最大42
#     label=     n=476 中位12 P90=20 P95=24 最大35
#   正常轴标签（轴名+单位+口径括注）P95 落在 36，所以 36 只抓尾部 5% 的"塞说明"。
#   ⛔ 别往回改成 24：实测会误伤 '搜索区间宽度 (%，对数刻度)'(25)、
#     '假阳性率 FPR (1 - 特异度)'(25)、'峰值冲击力 $F_{peak}$ (体重倍数 BW)'(25)
#     这类完全正常的轴标签。
SHORT_MAX_W = 36
# 限长档的"成句"判据：只认句号/分号 ——
# ⛔ 逗号/顿号/冒号在括注里是正常的（'(%，对数刻度)'），算进去会大量误伤。
_HARD_SENT = re.compile(r'[。；;]')


def disp_width(s):
    """显示宽度：中文/全角按 2 算，其余按 1"""
    return sum(2 if CJK.match(c) else 1 for c in s)


def strip_math(s):
    """剥掉 mathtext，公式不计入"话的长度"。

    ⛔ 必须剥：实测最长那条是 195 宽的偏导数公式
       $(\\mathrm{d}C/\\mathrm{d}\\varphi_B)_{...}$，它是公式不是说明文字，
       不剥就会被误判违规，AI 会去删该留的公式。
    """
    return MATH.sub('', s)


def is_numeric_label(body, raw=None):
    """反面判定：这段文本算不算"纯数值标注"。

    条件全部满足才算：
      ① 至少有一个数字（⛔ 在【原文】里找，不是剥公式后的残余）
      ② 汉字只能是白名单里的计量单位
      ③ ASCII 字母串长度 ≤ 5（放行 dBm/pp/kg/mmol，拦掉 solution/optimal）
      ④ 其余字符只能是数字/标点/运算符
    多行按整体判（换行本身在允许标点里）。
    """
    # ⛔ 数字要在【原文】里找：`$\pm1$ ulp`、`$p_{\min}=0$ m` 这类数字全在公式内，
    #   剥掉 mathtext 后只剩 ' ulp' / ' m' → 按剥后判会说"一个数字都没有"【误报】。
    #   实测真实工作区 8 处 non-numeric 全是这么来的。
    probe = raw if raw is not None else body
    if not _DIGIT.search(probe):
        return False        # 一个数字都没有 → 不是数值标注
    # ② 汉字必须都是单位
    for ch in body:
        if CJK.match(ch) and ch not in _CN_UNITS:
            return False
    # ③ ASCII 字母串不能太长
    for run in re.findall(r'[a-zA-Z]+', body):
        if len(run) > _MAX_UNIT_LETTERS:
            return False
    # ④ 其余字符白名单
    for ch in body:
        if ch.isdigit() or ch in _NUM_PUNCT:
            continue
        if CJK.match(ch):            # 已在 ② 校验过是单位
            continue
        if ch.isalpha():             # ASCII/希腊字母，长度已在 ③ 校验
            continue
        return False
    return True


# ── 短锚点标签档（第三档，介于「纯数值」与「散文」之间）──────────────────
# 为什么需要（实测事故，2026-08）：学术图里阈值线要说明是什么线、最优点要标是
#   最优点，否则读者看不懂 —— Nature 正刊亦然。只按「有中文且非单位 → 违规」判，
#   会把 `肘部拐点 $k$=8` / `预算绑定区` / `ROI 下限 3.0` 这类 4-6 字标签全误杀。
#   17 个真实工作区 523 处违规里 335 处（64%）是这类合法标签。AI 被逼着删完
#   → 图变得没法读，比留着更糟；更糟的是 AI 会学会无视本闸的全部输出。
# 边界在哪：标签是「给东西起名」，结论是「下判断」。前者放行，后者赶进正文。
#
# 体量上限按 17 个真实工作区 302 条放行样本的分布定（中位 16 / P90 35）：
_ANCHOR_MAX_W            = 45   # 总显示宽（P90 35 之上留一档；实测 46+ 已混入叙述）
_ANCHOR_MAX_LINES        = 3    # 行数（超过就是说明块不是标签）
_ANCHOR_MAX_CJK_TOTAL    = 12   # 全部行汉字总量（防多行拼成段落）
# ⛔ 单行判据不是「汉字数」而是「有数字 or 汉字极少」——这是散文与标签的真分界：
#   标签要么给东西起名（`预算绑定区`，≤5 字、无需数字），
#   要么是名+值（`肘部拐点 k=8`，带数字）。
#   而 `此刻已错过 AP₁ 的 Preamble`（6 汉字、无数字）就是叙述句的签名。
#   只卡汉字数（曾定 8）会让 2-3 行叙述钻过去 —— 实测漏放过 w47/w48 两类。
_ANCHOR_NAME_ONLY_CJK    = 5    # 无数字行允许的汉字上限（纯命名）

# 括号里的完整中文解释不是“锚点”，而是被藏进图内的微型图注。
# 例如「判据线（下方=遮蔽成立）」单看总字数不长，却同时承担命名和解释，
# 在多 panel 图里最容易与曲线、图例叠在一起。短单位/口径括注仍允许。
_PAREN_CJK_EXPLANATION = re.compile(r'[（(]([^）)]*[\u4e00-\u9fff][^）)]*)[）)]')
_ANCHOR_PROSE_PUNCT = re.compile(r'[，。；：？！;]')

# 结论/因果词 —— 出现即判违规（这些是「下判断」，该写进论文正文）
_CONCL_WORDS = (
    '始终', '一律', '因此', '所以', '可见', '表明', '说明', '导致', '意味',
    '不会', '无用', '故而', '建议', '应当', '必须', '证明', '反映', '由于',
    # Single-character substrings hit normal nouns (故障、劣化、必须条件).
    # 比较判断（`较 X 劣 Y`）与全称量词（`全落在`）—— 实测漏放过这两类。
    # 是「下判断」不是「起名」，且是小闭合类，不是打地鼠。
    '优于', '劣于', '全落在', '全部落在', '均落在', '一致优',
)
# ⛔ 故意【不】收「贴死 / 绑定 / 有余量 / 高估」这类状态描述词：
#    它们是给区域/点的状态起名（`ROI 绑定区`、`d=50 高估 -0.062`），
#    配着数值用是合法标签。真正的结论靠上面的因果词 + 下面的箭头判据抓。

# ⛔ 箭头要两条规则，各抓一半，缺一漏一（实测）：
#   ① 行首箭头 = 推导/结论 → `→ 200k 时隙已收敛`（后面跟数字，规则②抓不到）
#   ② 箭头后紧跟中文 = 导读 → `题给 $B$=0 元 → 在图右`（在行中，规则①抓不到）
#   合法的是「箭头两侧都是数值」的区间/映射：
#   `0.12 → 0.03 元`、`$d$:5→50`、`EIRP 9 → 29 dBm`
_ARROW_LEADS_LINE = re.compile(r'(?:^|\n)\s*[→⇒➜►]')
_ARROW_THEN_CJK   = re.compile(r'[→⇒➜►]\s*[一-鿿]')


def is_short_anchor(body, raw=None):
    """这段文本算不算「短锚点标签」（给图上的线/点/区域起名）。

    放行条件全部满足：
      ① 不含结论/因果词
      ② 箭头不在行首、后面不紧跟中文
      ③ 不成句（无句号分号 —— 复用限长档的同一判据）
      ④ 总显示宽 ≤ 45，行数 ≤ 3，总汉字 ≤ 12
      ⑤ 每行「有数字」或「汉字 ≤ 5」（散文 = 无数字的长中文行）

    ⛔ 判据在 --selftest 里有 53 项覆盖，改这里必须先跑它。
    """
    # ① 结论词
    for w in _CONCL_WORDS:
        if w in body:
            return False
    # ② 箭头：行首（推导）或后跟中文（导读）
    if _ARROW_LEADS_LINE.search(body) or _ARROW_THEN_CJK.search(body):
        return False
    # ③ 短锚点不承担分句：中文逗号/冒号已经意味着在解释过程或结论。
    # 英文冒号仍允许统计量写法（Youden: J=...）。
    if _ANCHOR_PROSE_PUNCT.search(body):
        return False
    # ③b 括号中出现四个及以上汉字，通常已经是解释句而不是名称。
    # 「95% CI」「均值」等短口径不受影响。
    for match in _PAREN_CJK_EXPLANATION.finditer(body):
        if sum(1 for ch in match.group(1) if CJK.match(ch)) >= 4:
            return False
    # ④ 体量：总宽 / 行数 / 总汉字
    if disp_width(body) > _ANCHOR_MAX_W:
        return False
    lines = [ln for ln in body.split('\n') if ln.strip()]
    if len(lines) > _ANCHOR_MAX_LINES:
        return False
    total_cjk = sum(1 for ch in body if CJK.match(ch))
    if total_cjk > _ANCHOR_MAX_CJK_TOTAL:
        return False
    # ⑤ 逐行：有数字 or 汉字极少（纯命名）
    for ln in lines:
        n_cjk = sum(1 for ch in ln if CJK.match(ch))
        if _DIGIT.search(ln):
            continue                        # 名+值，合法
        if n_cjk <= _ANCHOR_NAME_ONLY_CJK:
            continue                        # 纯命名，合法
        return False                        # 无数字的长中文行 = 叙述
    # ⑥ 一个标签只给【一样】东西起名：同一行里若有 ≥2 段「不带数字的中文词」，
    #    那是把多个标签塞进一个文字框（`最优解 · 收敛区间 · 预算上限 3271 元`），
    #    该拆成多个 annotate 或移进正文。
    #    ⛔ 与多值读数区分：`加权 R²=0.87 / RMSE=1.2` 每段都带数字 → 放行。
    for ln in lines:
        bare = 0
        # ⛔ 只按【视觉分隔符】切，不切 `/` 和逗号：
        #   `/` 在单位里是「每」（`GMV/人`、`元/人`、`km/h`）—— 切了会把
        #   `边际 GMV/人` 误判成两个标签【实测误伤】；
        #   逗号常出现在多值读数里（`J=0.42, θ*=0.31`）。
        for seg in re.split(r'[·•｜|]', ln):
            if not CJK.search(seg):
                continue                    # 该段没中文，不算
            if not _DIGIT.search(seg):
                bare += 1                   # 有中文但无数字的段
        if bare >= 2:
            return False
    return True


def classify(s, max_w=DEFAULT_MAX_W):
    """图内标注只准是数值 —— 返回 (是否违规, 显示宽, 原因)。

    规则（`ax.text` / `ax.annotate` 专用）：
      放行  panel 标号 a/b/c、纯数值(+单位)、纯公式、数值+公式
      拦掉  任何词句（中英文散文），无论长短 —— "最优解" 也算违规

    ⛔ 本函数【不管】坐标轴标签 / 刻度 / 图例系列名 / 标题 ——
       那些是图的必备构件，不是"标注"。扫描器只取 .text()/.annotate() 的
       文本实参，天然不会碰到它们（set_xlabel/legend 走别的 API）。
    """
    raw = s.strip()
    if not raw:
        return False, 0, 'empty'
    # 放行：面板标号（期刊硬标准，多 panel 必须有）
    if PANEL.match(raw):
        return False, disp_width(raw), 'panel-label'
    w_all = disp_width(raw)
    # 剥掉公式后看剩什么
    body = strip_math(raw).strip()
    # 全是公式 → 放行
    if not body or disp_width(body) <= 2:
        return False, w_all, 'math-only'
    if is_numeric_label(body, raw):
        return False, w_all, 'numeric'
    # 放行：短锚点标签（给图上的线/点/区域起名，学术图常规做法）
    if is_short_anchor(body, raw):
        return False, w_all, 'short-anchor'
    # 到这里就是词句 —— 一律违规
    if SENT_PUNCT.search(body):
        why = 'sentence'
    elif CJK.search(body) or re.search(r'[a-zA-Z]{4,}', body):
        why = 'prose'
    else:
        why = 'non-numeric'
    return True, w_all, why


_VAR_PLACEHOLDER = '0'      # f-string 变量位 → 当作数值占位


def classify_short(s, max_w=SHORT_MAX_W):
    """限长档：轴标签 / 标题 / 图例系列名 / 刻度标签。

    允许有文字（"迭代次数"、"核销率 q" 这类），但：
      ① 显示宽 ≤ max_w（默认 24 ≈ 12 汉字）
      ② 不许成句（带 。；，：等句读即算成句）
    公式不计入长度（同 numeric 档）。

    ⛔ 为什么要有这一档：AI 被"只准数值"拦住后，最省事的规避就是把整段说明
       塞进 set_xlabel / set_title / label= —— 实测这几条全能绕过。
       但这些 API 本该有几个字，不能按"只准数值"判，否则轴标签全废。
    """
    raw = s.strip()
    if not raw:
        return False, 0, 'empty'
    body = strip_math(raw).strip()
    w = disp_width(body)
    if w == 0:
        return False, disp_width(raw), 'math-only'
    # 句号/分号出现在轴标签里就是在写句子（逗号顿号不算，括注里正常）
    if _HARD_SENT.search(body):
        return True, w, 'sentence-in-label'
    # ⛔ 多行必须【逐行】判：分组刻度标签常写成
    #   'P3-C（交付）\n预测 occ\n实测 PER\n实测档位' —— 4 行各自很短、排出来是
    #   竖排一列，完全正常；按整体 37 宽判会误伤。取最长那一行比。
    lines = [ln.strip() for ln in body.splitlines() if ln.strip()]
    w_line = max((disp_width(ln) for ln in lines), default=w)
    if w_line > max_w:
        return True, w_line, 'label-too-long'
    return False, w_line, 'short'


def _str_of(node):
    """取字面量字符串。f-string 的变量位用 '0' 占位。

    ⛔⛔ 变量位【必须补占位】，不能直接丢：
       `f'{pct}%\\n({a}/{b})'` 真实渲染是 `45%\\n(9/20)`（纯数值，合规）。
       丢掉变量得到 `'%\\n(/)'` → 不像数值 → 被判 non-numeric【误报】。
       实测这是第一条命中项，属系统性误报（真实工作区 f-string 标注极多）。
       补成 `'0%\\n(0/0)'` 后能被 NUMERIC 正确识别。
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.JoinedStr):
        out = []
        for v in node.values:
            if isinstance(v, ast.Constant) and isinstance(v.value, str):
                out.append(v.value)
            else:
                out.append(_VAR_PLACEHOLDER)     # FormattedValue
        return ''.join(out)
    if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
        # ⛔ 一侧解析不出【不能整条放弃】，补占位就好（同 f-string 的处理）：
        #   `'结论' + str(x)` 里 str(x) 取不到值，旧写法要求两侧都非 None → 整条漏判。
        l, r = _str_of(node.left), _str_of(node.right)
        if l is None and r is None:
            return None
        return (l if l is not None else _VAR_PLACEHOLDER) + \
               (r if r is not None else _VAR_PLACEHOLDER)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        base = _str_of(node.func.value)
        if base is not None:
            # '\n'.join([...]) → 把列表里的字面量拼起来（多行说明的常见写法）
            if node.func.attr == 'join' and node.args:
                arg = node.args[0]
                if isinstance(arg, (ast.List, ast.Tuple)):
                    parts = [_str_of(e) or '' for e in arg.elts]
                    return base.join(parts)
            return base
    # 常见显示/翻译包装器：cn(f"...")、_("...")、gettext("...")。
    # 旧实现停在 Call 节点，导致真正画进图里的长句只要套一层 cn() 就完全绕过
    # 静态闸；当前工作区 15 个脚本正是这种写法。这里只解开确定不会改变文本
    # 语义的一参包装器，不对任意函数做猜测，避免误报数据格式化函数。
    if isinstance(node, ast.Call) and node.args:
        fname = None
        if isinstance(node.func, ast.Name):
            fname = node.func.id
        elif isinstance(node.func, ast.Attribute):
            fname = node.func.attr
        if fname in {'cn', '_', 'gettext', 'ugettext', 'str'}:
            return _str_of(node.args[0])
    return None


# ── 两档判据 ──────────────────────────────────────────────
# 【只准数值】档：这些 API 画出来的是"浮在数据上的标注"，一个字都不该有
_NUMERIC_APIS = {
    'text':      ('arg2', 's'),        # ax.text / fig.text / plt.text
    'figtext':   ('arg2', 's'),        # plt.figtext（与 fig.text 同义，曾漏）
    'annotate':  ('arg0', 'text'),     # ax.annotate / plt.annotate
}
# 【限长】档：这些本该有几个字（轴标签/系列名），但不该塞整段说明
_SHORT_APIS = {
    'set_title':       ('arg0', 'label'),
    'suptitle':        ('arg0', 't'),
    'set_xlabel':      ('arg0', 'xlabel'),
    'set_ylabel':      ('arg0', 'ylabel'),
    'set_zlabel':      ('arg0', 'zlabel'),
    'title':           ('arg0', 'label'),      # plt.title
    'xlabel':          ('arg0', 'xlabel'),     # plt.xlabel
    'ylabel':          ('arg0', 'ylabel'),
}
# 只在关键字里出现的文本参数：(API 名 或 None=任意调用, 关键字名, 档位)
_KW_TARGETS = (
    ('legend',      'title',  'short'),
    (None,          'label',  'short'),     # plot/bar/axhline… 的 label= → 图例
    ('bar_label',   'labels', 'numeric'),   # 自定义柱标签（列表）
    ('AnchoredText', None,    'numeric'),   # 文本框：位置参数 0
)
_TICK_APIS = {'set_xticklabels', 'set_yticklabels', 'set_zticklabels',
              'set_ticklabels'}
_PANEL_HELPERS = {'panel'}


def _pick(node, spec):
    """按 (位置, 关键字) 取实参节点"""
    pos, kw = spec
    idx = {'arg0': 0, 'arg2': 2}.get(pos)
    if idx is not None and len(node.args) > idx:
        return node.args[idx]
    if kw:
        return next((k.value for k in node.keywords if k.arg == kw), None)
    return None


def _collect_consts(tree):
    """常量表：NAME='字面量' / NAME=['a','b'] / NAME={'k':'v'}。

    ⛔ 必须做：AI 被拦后最自然的写法就是先赋值再传
       （`_s='整段说明'; ax.text(1,2,_s)`），实测这条能绕过。
       只做同文件、字面量级别的传播 —— 够覆盖真实写法，不做数据流分析。
    """
    consts, seqs = {}, {}
    for n in ast.walk(tree):
        if not isinstance(n, ast.Assign):
            continue
        val = n.value
        for tgt in n.targets:
            if not isinstance(tgt, ast.Name):
                continue
            if isinstance(val, (ast.Constant, ast.JoinedStr, ast.BinOp)):
                s = _str_of(val)
                if s is not None:
                    consts[tgt.id] = s
            elif isinstance(val, (ast.List, ast.Tuple, ast.Set)):
                items = [_str_of(e) for e in val.elts]
                items = [x for x in items if x is not None]
                if items:
                    seqs[tgt.id] = items
            elif isinstance(val, ast.Dict):
                items = [_str_of(e) for e in val.values]
                items = [x for x in items if x is not None]
                if items:
                    seqs[tgt.id] = items

    # ── for 循环的迭代变量绑定 ──
    # ⛔ 必须做：`L=[...]; for i,s in enumerate(L): ax.text(1,i,s)` 是
    #   出图脚本里最常见的批量标注写法，不绑定就整条漏过（实测能绕过闸）。
    def _seq_items(node):
        """从可迭代表达式取字面量元素（平铺，不管嵌套层次）"""
        if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            got = [_str_of(e) for e in node.elts]
            return [x for x in got if x is not None]
        if isinstance(node, ast.Name):
            return list(seqs.get(node.id, []))
        return []

    def _seq_col(node, col):
        """从「元组的元组」里按列取字面量。

        ⛔ 必须支持嵌套：出图脚本大量用
             for xi, v, txt in ((0, B, f'…'), (1, B, f'…')):
                 ax.text(xi, v, txt)
           文字在【内层 tuple 的第 col 个位置】。旧写法只对外层 elts 调
           _str_of，对内层 Tuple 返回 None → 整批漏判。
           实测天府杯 fig_q2_budget_slack 的两处互压百分比标注就是这么漏的。
        """
        if not isinstance(node, (ast.List, ast.Tuple, ast.Set)):
            return []
        out = []
        for e in node.elts:
            if isinstance(e, (ast.Tuple, ast.List)) and len(e.elts) > col:
                s = _str_of(e.elts[col])
                if s is not None:
                    out.append(s)
        return out

    for n in ast.walk(tree):
        if not isinstance(n, (ast.For, ast.AsyncFor, ast.comprehension)):
            continue
        it = n.iter
        tgt = n.target
        # enumerate(L) / list(L) / sorted(L) / reversed(L) → 取内层
        wrapped = None
        if isinstance(it, ast.Call) and isinstance(it.func, ast.Name):
            fn = it.func.id
            if fn in ('enumerate', 'list', 'sorted', 'reversed', 'tuple') and it.args:
                wrapped = fn
                inner = it.args[0]
            elif fn == 'zip':
                # for a, b in zip(X, Y) → 按位置对应
                if isinstance(tgt, ast.Tuple):
                    for sub, arg in zip(tgt.elts, it.args):
                        if isinstance(sub, ast.Name):
                            items = _seq_items(arg)
                            if items:
                                seqs[sub.id] = items
                continue
            else:
                continue
        else:
            inner = it
        items = _seq_items(inner)
        # ⛔ 不能在这里 `if not items: continue` —— 嵌套元组
        #   `for xi, v, txt in ((0,B,'…'),(1,B,'…'))` 的 _seq_items 必然返回空
        #   （内层是 Tuple，_str_of 给 None），提前退出会让下面按列取值的
        #   _seq_col 永远执行不到（实测天府杯那两处互压标注就这么漏掉的）。
        has_col = isinstance(tgt, ast.Tuple) and any(
            _seq_col(inner, c) for c in range(len(tgt.elts)))
        if not items and not has_col:
            continue
        if wrapped == 'enumerate' and isinstance(tgt, ast.Tuple) and len(tgt.elts) == 2:
            # (idx, value) —— 只有第二个是文本
            second = tgt.elts[1]
            if isinstance(second, ast.Name):
                seqs[second.id] = items
        elif isinstance(tgt, ast.Name):
            seqs[tgt.id] = items
        elif isinstance(tgt, ast.Tuple):
            # for xi, v, txt in ((…), (…)) —— 按【列】对应，取内层 tuple 的第 i 个
            for col, sub in enumerate(tgt.elts):
                if not isinstance(sub, ast.Name):
                    continue
                col_items = _seq_col(inner, col)
                if col_items:
                    seqs[sub.id] = col_items
                else:
                    seqs.setdefault(sub.id, items)
    return consts, seqs


def _texts_from(node, consts, seqs):
    """从实参节点取出所有候选文本（含变量/容器展开）"""
    s = _str_of(node)
    if s is not None:
        return [s]
    # 变量名 → 常量表
    if isinstance(node, ast.Name):
        if node.id in consts:
            return [consts[node.id]]
        if node.id in seqs:
            return list(seqs[node.id])
        return []
    # 下标取值 D['k'] / L[i] → 该容器的全部字面量
    if isinstance(node, ast.Subscript):
        base = node.value
        if isinstance(base, ast.Name):
            if base.id in seqs:
                return list(seqs[base.id])
            if base.id in consts:
                return [consts[base.id]]
        return []
    # 列表/元组字面量（bar_label(labels=[...]) / set_xticklabels([...])）
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        out = []
        for e in node.elts:
            out += _texts_from(e, consts, seqs)
        return out
    return []


def scan_file(path, max_w=DEFAULT_MAX_W, short_max_w=SHORT_MAX_W):
    """返回违规列表 [(kind, text, width, reason, lineno)]"""
    try:
        with open(path, encoding='utf-8', errors='replace') as f:
            tree = ast.parse(f.read())
    except (OSError, SyntaxError, ValueError):
        return []
    consts, seqs = _collect_consts(tree)
    out = []
    seen = set()

    def _emit(kind, node, tier, lineno):
        for s in _texts_from(node, consts, seqs):
            key = (lineno, s, kind)
            if key in seen:
                continue
            seen.add(key)
            if tier == 'numeric':
                bad, w, why = classify(s, max_w)
            else:
                bad, w, why = classify_short(s, short_max_w)
            if bad:
                out.append((kind, s, w, why, lineno))

    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        # AnchoredText('…') —— 直接调用，不是属性调用
        fname = None
        if isinstance(n.func, ast.Name):
            fname = n.func.id
        elif isinstance(n.func, ast.Attribute):
            fname = n.func.attr
        if fname == 'AnchoredText' and n.args:
            _emit('AnchoredText', n.args[0], 'numeric', n.lineno)
            continue
        # 项目推荐的 _figbase.panel(ax, tag) / panel(ax, tag) 本质上就是
        # set_title(tag)。若不检查，模型会把整句结论塞进 panel helper 绕过限长档。
        if fname in _PANEL_HELPERS and len(n.args) >= 2:
            _emit('panel-title', n.args[1], 'short', n.lineno)
            continue
        if not isinstance(n.func, ast.Attribute):
            continue
        attr = n.func.attr
        v = n.func.value
        recv = ''
        if isinstance(v, ast.Name):
            recv = v.id
        elif isinstance(v, ast.Attribute):
            recv = v.attr
        elif isinstance(v, ast.Subscript):
            recv = 'axs[]'

        if attr in _NUMERIC_APIS:
            node = _pick(n, _NUMERIC_APIS[attr])
            if node is not None:
                kind = ('fig.text' if (attr == 'figtext' or recv.startswith('fig'))
                        else ('annotate' if attr == 'annotate' else 'ax.text'))
                _emit(kind, node, 'numeric', n.lineno)
        elif attr in _SHORT_APIS:
            node = _pick(n, _SHORT_APIS[attr])
            if node is not None:
                _emit(attr, node, 'short', n.lineno)
        elif attr in _TICK_APIS:
            node = n.args[0] if n.args else next(
                (k.value for k in n.keywords if k.arg == 'labels'), None)
            if node is not None:
                _emit(attr, node, 'short', n.lineno)
        elif attr == 'bar_label':
            node = next((k.value for k in n.keywords if k.arg == 'labels'), None)
            if node is not None:
                _emit('bar_label', node, 'numeric', n.lineno)

        # 任意调用的 label= / title=（图例文字）
        for k in n.keywords:
            if k.arg == 'label' and attr not in _SHORT_APIS:
                _emit(f'{attr}(label=)', k.value, 'short', n.lineno)
            elif k.arg == 'title' and attr == 'legend':
                _emit('legend(title=)', k.value, 'short', n.lineno)
    return out


# ── 判据自测 ────────────────────────────────────────────────────────────
# ⛔ 为什么必须有：本文件的判据经历过两轮"看着对、打到真实数据上误报一片"：
#   第一轮 8 处误报（公式内数字 / 全角标点 / U+2212 / f-string 残骸）；
#   第二轮 335 处误杀（合法短锚点标签被当散文）。
#   每条用例都对应一次实测事故，不是凭空想的。改判据先跑这个。
#
# 用例格式：(文本, 期望是否违规, 说明)
_SELFTEST_CASES = (
    # ── 纯数值档：必须放行 ──
    ('8188.06',                          False, '纯数值'),
    ('45%',                              False, '百分比'),
    ('1007 张',                          False, '数值+中文量词'),
    ('n=30',                             False, '统计量'),
    ('$q^*$=0.47',                       False, '公式+数值'),
    ('45%\n(9/20)',                      False, '多行数值+分数'),
    ('−2,729 (0.55%)',                   False, 'U+2212 负号（非 ASCII 减号）'),
    ('$\\pm1$ ulp',                      False, '数字全在公式内'),
    ('$T_{M0}$=0 s　（基准）',             False, '全角空格 U+3000'),
    ('1-PER（M6-c）',                     False, '全角括号'),
    ('ROI=3.0 阈值线',                    False, '「阈值线」不是单位但属短锚点'),
    ('a',                                False, 'panel 标号'),
    ('(b)',                              False, 'panel 标号带括号'),
    ('c)',                               False, 'panel 标号变体'),

    # ── 短锚点标签档：必须放行（本档就是为这些加的）──
    ('预算绑定区',                         False, '纯命名 5 字无数字'),
    ('肘部拐点 $k$=8',                    False, '名+值'),
    ('ROI 下限 3.0',                      False, '阈值线命名'),
    ('膝点 $B^\\ast\\approx$3.2 万元',     False, '膝点命名'),
    ('约束切换点\n$B\\approx$1.7 万元',     False, '两行短标签'),
    ('全体候选率 39.5%',                   False, '指标命名+数值'),
    ('Youden: J=0.42, θ*=0.31',          False, '最优点命名+数值'),
    ('加权 R²=0.87 / RMSE=1.2',           False, '多指标并列'),
    ('边际 GMV/人\n0.12 → 0.03 元',        False, '行中箭头=数值区间'),
    ('EIRP 9 → 29 dBm',                  False, '行中箭头=区间'),
    ('$d$:5→50 ×10 ｜ GMV ×2.3 ｜ 预算 ×18.3',
                                          False, '压缩后的多值锚点'),
    ('d=50 高估 $-$0.062',                False, '状态词+数值（状态≠结论）'),
    ('ROI 绑定区\nROI 贴死 3.0',            False, '状态词配数值'),
    ('00 时峰 0.42',                       False, '时峰命名+值'),
    ('簇 $\\{8,9\\}$（贴右面，含 $F_R$ 节点 8, 9）',
                                          True,  '括号内是完整解释，应移入图注'),
    ('相切不变量 $R_1+R_2=K=1.7$ m\n$\\varphi=0.43$ rad',
                                          False, '不变量命名+数值读数'),
    ('前沿在 $\\alpha$=90% 处的点\n$(\\varphi_A,\\varphi_B)$=(1%, 2%)\n成本 3',
                                          False, '三行数值读数'),
    ('最优解',                            False, '3 字命名（给点起名）'),

    # ── 结论/因果：必须拦 ──
    ('全区间贴死下限\n→ ROI 始终绑定',       True,  '含「始终」+ 行首箭头'),
    ('题给 $B$=500000 元 → 在图右',        True,  '箭头后跟中文=导读'),
    ('末两检查点 $\\rho$ 差 0.001\n→ 200k 时隙已收敛',
                                          True,  '行首箭头（后跟数字，靠规则①抓）'),
    ('因此最优解取 8 个点',                 True,  '含「因此」'),
    ('样本仅 530 条，说明高估',             True,  '含「说明」'),
    ('加预算无用',                         True,  '含「无用」'),
    ('须限量或不发',                        True,  '含「须」'),
    ('可见 ROI 单调下降',                   True,  '含「可见」'),
    ('$\\varphi_B$=1.5% 处上界 2% < 90%\n严格不可行',
                                          True,  '含「不可行」'),
    ('基线 8 bin：RMSE 0.4 μs\n（较 16 bin 的 0.2 μs 劣 2$\\times$）',
                                          True,  '比较判断「劣」'),
    ('thinning 的 $\\tau$ 全落在 [1, 2]\n中位 1.5 倍',
                                          True,  '全称量词「全落在」'),

    # ── 成句 / 超体量：必须拦 ──
    ('这是最优解。',                        True,  '句号成句'),
    ('右侧：有 ROI 余量，可放量发\n左侧：亏 ROI，须限量或不发',
                                          True,  '两行叙述+含「须」'),
    ('面额 5→50 涨 10 倍\n人均增量 GMV 仅涨 2.3 倍\n预算占用却涨 18.3 倍\n（全池均值口径）',
                                          True,  '4 行说明块（真实事故样本）'),
    ('AP$_2$ 先结束传输，\n此刻已错过 AP$_1$ 的 Preamble',
                                          True,  '叙述句：无数字的长中文行'),
    ('两簇之间无接触边：$\\mathcal{R}(F_L)\\cap\\mathcal{R}(F_R)=\\varnothing$',
                                          True,  '论断（冒号引出）'),
    ('本方法在所有基线上均取得最优表现',       True,  '13 汉字单行超上限'),
    ('收敛区间内目标函数单调递减稳定',         True,  '14 汉字超上限'),
    ('最优解 · 收敛区间 · 预算上限 3271 元',   True,  '多个概念堆叠'),
)

# 限长档用例：(文本, 期望是否违规, 说明)
_SELFTEST_SHORT = (
    ('迭代次数',                                       False, '短轴标签'),
    ('峰值冲击力 $F_{peak}$ (体重倍数 BW)',             False, '量名+单位'),
    ('假阳性率 FPR (1 - 特异度)',                       False, '25 宽，曾误伤'),
    ('搜索区间宽度 (%，对数刻度)',                       False, '25 宽，曾误伤'),
    ('相对改进百分比 (%，右为更优；误差棒为两端 95% CI 的保守组合)',
                                                       True,  '含分号且超 36 宽'),
)


def selftest():
    """跑判据自测。返回 0 = 全过，非 0 = 失败项数。"""
    fail = 0
    print('=' * 72)
    print('  figure_text_budget 判据自测')
    print('=' * 72)
    for text, want_bad, note in _SELFTEST_CASES:
        got_bad, w, why = classify(text)
        if got_bad != want_bad:
            fail += 1
            print('  FAIL [标注档] %-34s 期望%s 实际%s(%s)' % (
                text.replace('\n', '/')[:34],
                '违规' if want_bad else '放行',
                '违规' if got_bad else '放行', why))
    for text, want_bad, note in _SELFTEST_SHORT:
        got_bad, w, why = classify_short(text)
        if got_bad != want_bad:
            fail += 1
            print('  FAIL [限长档] %-34s 期望%s 实际%s(%s)' % (
                text.replace('\n', '/')[:34],
                '违规' if want_bad else '放行',
                '违规' if got_bad else '放行', why))
    total = len(_SELFTEST_CASES) + len(_SELFTEST_SHORT)
    print('  共 %d 项（标注档 %d + 限长档 %d），PASS %d，FAIL %d' % (
        total, len(_SELFTEST_CASES), len(_SELFTEST_SHORT), total - fail, fail))
    print('=' * 72)
    if fail:
        print('  ⛔ 判据自测未全过 —— 不要拿它去扫真实工作区（会制造误报/漏报）')
    return fail


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument('root', nargs='?', default='.')
    ap.add_argument('--max-w', type=int, default=DEFAULT_MAX_W)
    ap.add_argument('--short-max-w', type=int, default=SHORT_MAX_W,
                    help=f'限长档上限，默认 {SHORT_MAX_W}（按真实分布 P95 定）')
    ap.add_argument('--json', action='store_true')
    ap.add_argument('--quiet', action='store_true')
    ap.add_argument('--only', action='append', default=[], help='仅检查本次图或生成脚本，可重复指定')
    ap.add_argument('--selftest', action='store_true',
                    help='跑判据自测（56 项）。改判据后必须先跑它，全过才算对')
    a = ap.parse_args()

    if a.selftest:
        return selftest()

    files = []
    for dp, dn, fn in os.walk(a.root):
        dn[:] = [d for d in dn
                 if d not in ('__pycache__', '.git', 'node_modules', '.venv')]
        for f in fn:
            if f.endswith('.py') and f != os.path.basename(__file__):
                files.append(os.path.join(dp, f))

    if a.only:
        from pathlib import Path
        names = {Path(x.replace('\\', '/')).stem.removeprefix('gen_').casefold() for x in a.only}
        selected = []
        for file in files:
            if Path(file).stem.removeprefix('gen_').casefold() in names:
                selected.append(file)
                continue
            try:
                tree = ast.parse(Path(file).read_text(encoding='utf-8', errors='replace'))
                outputs = {Path(node.value.replace('\\', '/')).stem.casefold()
                           for node in ast.walk(tree) if isinstance(node, ast.Constant) and isinstance(node.value, str)}
                if names & outputs:
                    selected.append(file)
            except (OSError, SyntaxError):
                pass
        files = selected
        if not files and not a.json:
            print('[WARN] 本次图未定位到可静态检查的生成脚本；继续检查实际 PDF，不扫描无关旧脚本')

    hits = []
    for f in files:
        for rec in scan_file(f, a.max_w, a.short_max_w):
            hits.append((f,) + rec)

    if a.json:
        print(json.dumps([{'file': f, 'kind': k, 'text': s, 'width': w,
                           'reason': why, 'line': ln}
                          for f, k, s, w, why, ln in hits],
                         ensure_ascii=False, indent=1))
        return int(bool(hits))

    if not hits:
        if not a.quiet:
            print(f'[OK] 图内文字：{len(files)} 个脚本通过'
                  f'（标注只含必要数值/短锚点；轴标签/标题/图例 ≤{a.short_max_w} 显示宽）')
        return 0

    n_num = sum(1 for h in hits if h[4] in ('prose', 'sentence', 'non-numeric'))
    n_lab = len(hits) - n_num
    print(f'[违规] 图内文字超标 {len(hits)} 处'
          f'（标注 {n_num} + 轴标签/标题/图例 {n_lab}）')
    print()
    print('  ① 标注档【只准必要数值或短锚点】—— ax.text / annotate / fig.text / figtext /')
    print('     AnchoredText / bar_label(labels=)')
    print('     ✅ 8188.06 · 45% · n=30 · $q^*$=0.47 · 最优点 · 上限 21 · a b c')
    print('     ❌ 结论、因果、方法说明、参数罗列及任何解释性成句')
    print(f'  ② 限长档【≤{a.short_max_w} 显示宽 ≈ {a.short_max_w // 2} 汉字，且不许有句号分号】')
    print('     —— set_xlabel / set_ylabel / set_title / suptitle /')
    print('        legend(title=) / label= / set_xticklabels')
    print('     ✅ 迭代次数 · 峰值冲击力 $F_{peak}$ (体重倍数 BW) · 假阳性率 FPR (1 - 特异度)')
    print('     ❌ 相对改进百分比 (%，右为更优；误差棒为两端 95% CI 的保守组合)')
    print()
    print('  → 标注档超标：只留必要数值/短锚点，文字阐述写进论文正文。')
    print('  → 限长档超标：轴标签只写「量名（单位）」，口径/结论移出图外。')
    print()
    by_kind = {}
    for f, k, s, w, why, ln in hits:
        by_kind.setdefault(k, []).append((w, f, ln, s, why))
    for k in ('fig.text', 'ax.text', 'annotate'):
        v = sorted(by_kind.get(k, []), reverse=True)
        if not v:
            continue
        print(f'  ── {k}：{len(v)} 处')
        for w, f, ln, s, why in v[:8]:
            rel = f.replace('\\', '/')
            body = s.replace('\n', '⏎')[:64]
            print(f'     {rel}:{ln}  宽{w} [{why}]')
            print(f'       {body}')
        if len(v) > 8:
            print(f'     … 另有 {len(v) - 8} 处')
    return int(bool(hits))


if __name__ == '__main__':
    sys.exit(min(main(), 250))
