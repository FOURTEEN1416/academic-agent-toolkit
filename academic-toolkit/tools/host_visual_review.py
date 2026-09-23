#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""宿主独立窗口视觉审核驱动（2026-09-23 第三次用户裁定：换驱动，不拆机制）。

视觉审核的底层驱动从「填 APIKey 调外部视觉 LLM API」整体置换为：
**项目驱动宿主自身具备视觉能力的 LLM，在独立窗口完成读图审核。**

本模块是三个视觉质检工具（data_fig / tikz / drawio）的共享实现本体。
CLI 契约与旧实现完全兼容：入口名、<image> 参数、--review 开关、
exit 语义（0=pass 或 STOP 定稿放行 / 1=发现 issue / 2=unavailable）均不变，
下游（visual_bridge、绘图技能脚本、引擎闸、测试 mock）零改动。

流程：
1. 开发期防死循环计数（沿用旧实现 STOP_VISION_LOOP 全套治理：图名归一、
   per-图 2 轮、全局 图数×2+2、--review 审核模式不计数不受限）；
2. 确定性检查（PIL/PyMuPDF 解码、尺寸、页数）——辅助，不阻断；
3. 若独立窗口已回写 verdict（visual_review_tasks/<stem>.verdict.md），
   校验并汇总输出 PASS / ISSUE N: ...；
4. 否则生成独立窗口审核任务卡（<stem>.task.md）并提示派发，exit 2。

审核执行者永远是宿主独立窗口（视觉审子代理/独立会话），本工具只做
任务卡生成与证据收集：不发起任何网络 API 调用、不读取任何 API key。
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

TASK_DIR_NAME = "visual_review_tasks"
REVIEWED_BY_PREFIX = "Reviewed-by:"
MAX_PER_FIG = 2
STOP_TAG = "STOP_VISION_LOOP"

# 数据图/draw.io 通用检查单（与 comp-visual-review SKILL.md 铁律逐项对应）
CHECKLIST = [
    "坐标轴名称与单位",
    "刻度可读性",
    "图例完整且不遮挡曲线",
    "颜色区分与色盲（红绿色弱）可辨",
    "黑白打印下仅靠色相区分的系列有线型/hatch 冗余编码",
    "无截断、无重叠",
    "无误导性比例",
    "题注对应",
    "文字无溢出",
    "配色对比度",
]

# TikZ 几何图/流程图/架构图专属检查单（沿旧实现 PROMPT 六条）
TIKZ_CHECKLIST = [
    "文字是否被截断、重叠或超出节点边框",
    "连线上的标注文字是否跟节点重叠或被遮挡",
    "节点间距是否均匀，有没有挤在一起",
    "有没有大片空白区域（布局不紧凑）",
    "箭头方向是否合理，有没有连线穿过节点",
    "整体是否美观、专业、适合放在学术论文中",
]


# ---------------- 旧实现防死循环计数（本地治理，原样保留） ----------------

def _norm_fig_key(img_path: Path) -> str:
    """把不同临时命名归一到图本身：wrap_chord / chord_v / chord_dfv → chord，
    保证「脚本内循环」与「AI 脚本外手动调」对同一张图共用一个计数。"""
    stem = img_path.stem
    if stem.startswith("wrap_"):
        stem = stem[len("wrap_"):]
    for suf in ("_v", "_dfv", "_vision"):
        if stem.endswith(suf):
            stem = stem[: -len(suf)]
    return stem


def _locate_counter(img_path: Path) -> Path:
    """计数文件统一放工作区 _tmp/（沿用旧实现文件名，历史计数不失效）。"""
    p = img_path.resolve()
    for anc in [p.parent, *p.parents]:
        if anc.name == "_tmp":
            return anc / ".tikz_vision_calls.json"
        cand = anc / "_tmp"
        if cand.is_dir():
            return cand / ".tikz_vision_calls.json"
    return p.parent / ".tikz_vision_calls.json"


def _count_real_tikz_figs(counter_file: Path) -> int:
    """数工作区真实视觉产物数（tikz_*.pdf + fig_*.png + 含 tikzpicture 的 .tex）。
    全局上限 = 图数×2+2 基于它，改文件名绕不过、也不误伤多图工作区。"""
    try:
        ws = counter_file.parent.parent          # _tmp/ 的父 = 工作区根
        figdir = ws / "figures"
        if not figdir.is_dir():
            return 0
        names = set()
        for pdf in figdir.glob("tikz_*.pdf"):
            names.add(pdf.stem)
        for png in figdir.glob("fig_*.png"):
            names.add(png.stem)
        for tex in figdir.glob("*.tex"):
            try:
                if "\\begin{tikzpicture}" in tex.read_text(encoding="utf-8", errors="ignore"):
                    names.add(tex.stem)
            except Exception:
                pass
        return len(names)
    except Exception:
        return 0


def _bump_and_check(img_path: Path, mode: str = "dev"):
    """计数并判断是否放行。返回 (是否允许, 该图当前次数, 是否撞全局上限)。
    ① per-图（同图 > 2 轮，拦固定命名空转）；② 全局（> 图数×2+2，拦换名绕过）。
    mode="review"（审核/终审）：不累计、不受限——审核必须真实产生视觉证据，
    不能被开发迭代额度耗尽逼成"定稿/绕过工具"（那等于伪造审核证据）。
    计数失败一律放行，绝不因计数器本身故障阻断正常质检。"""
    key = _norm_fig_key(img_path)
    cf = _locate_counter(img_path)
    data = {}
    try:
        if cf.exists():
            data = json.loads(cf.read_text(encoding="utf-8"))
            if not isinstance(data, dict):
                data = {}
    except Exception:
        data = {}
    try:
        n = int(data.get(key, 0)) + 1
    except Exception:
        n = 1
    try:
        total = int(data.get("__total__", 0)) + 1
    except Exception:
        total = 1
    if mode == "review":
        return (True, n, False)
    data[key] = n
    data["__total__"] = total
    try:
        cf.parent.mkdir(parents=True, exist_ok=True)
        cf.write_text(json.dumps(data), encoding="utf-8")
    except Exception:
        pass
    nfig = _count_real_tikz_figs(cf)
    global_cap = (nfig * 2 + 2) if nfig > 0 else 6
    per_key_ok = n <= MAX_PER_FIG
    global_ok = total <= global_cap
    return (per_key_ok and global_ok, n, not global_ok)


# ---------------- 确定性检查（辅助，不阻断） ----------------

def deterministic_check(image_path: Path) -> list[str]:
    notes: list[str] = []
    if image_path.suffix.lower() == ".pdf":
        try:
            import fitz  # PyMuPDF

            with fitz.open(image_path) as doc:
                notes.append(f"PDF 页数: {doc.page_count}（独立窗口请逐页审查嵌入图）")
        except Exception as exc:  # noqa: BLE001
            notes.append(f"确定性 PDF 检查跳过: {exc}")
        return notes
    try:
        from PIL import Image

        with Image.open(image_path) as im:
            size = im.size
            dpi = im.info.get("dpi", "未标注")
        notes.append(f"尺寸: {size[0]}x{size[1]} DPI: {dpi}")
    except Exception as exc:  # noqa: BLE001
        notes.append(f"确定性图像检查跳过: {exc}")
    return notes


# ---------------- 任务卡 / 证据（宿主独立窗口驱动核心） ----------------

def task_dir(workspace: Path) -> Path:
    return Path(workspace) / TASK_DIR_NAME


def task_card_path(workspace: Path, image_path: Path) -> Path:
    return task_dir(workspace) / f"{image_path.stem}.task.md"


def verdict_path(workspace: Path, image_path: Path) -> Path:
    return task_dir(workspace) / f"{image_path.stem}.verdict.md"


def build_task_card(backend: str, image_path: Path, review: bool,
                    checklist: list[str] | None = None) -> str:
    """生成宿主独立窗口审核任务卡。审核执行者=宿主视觉模型独立窗口。"""
    items = checklist if checklist is not None else CHECKLIST
    lines = [
        "# 独立窗口视觉审核任务卡",
        "",
        f"- backend: {backend}",
        f"- 待审图件: {image_path}",
        "- 执行者要求: 必须由项目驱动宿主的**独立窗口**（视觉审子代理/独立会话，"
        "与产出该图的窗口隔离）中的视觉能力 LLM **实际读图**执行；"
        "禁止由产图窗口自审，禁止以确定性检查结果冒充视觉结论。",
        "- 审查模式: " + ("review（审核/终审，证据供 review 闸）" if review else "dev（开发迭代）"),
        "",
        "## 逐项检查单",
        "",
    ]
    lines += [f"- [ ] {item}" for item in items]
    lines += [
        "",
        "## 回写要求（完成审核后写入本文件同目录的 <同名>.verdict.md）",
        "",
        "格式（缺一即判证据无效）:",
        "",
        "```markdown",
        f"{REVIEWED_BY_PREFIX} <执行窗口标识，如 zcode-visual-judge>",
        "",
        "PASS",
        "",
        "# 或发现问题:",
        "ISSUE 1: [位置] [问题描述]",
        "ISSUE 2: ...",
        "```",
    ]
    return "\n".join(lines) + "\n"


def parse_verdict(text: str) -> tuple[str, list[str], str]:
    """解析独立窗口 verdict。返回 (reviewed_by, issues, verdict_word)。"""
    reviewed_by = ""
    issues: list[str] = []
    verdict_word = ""
    for raw in text.splitlines():
        line = raw.strip()
        if line.startswith(REVIEWED_BY_PREFIX):
            reviewed_by = line[len(REVIEWED_BY_PREFIX):].strip()
        elif line.upper().startswith("PASS"):
            verdict_word = verdict_word or "PASS"
        elif line.upper().startswith("ISSUE"):
            issues.append(line)
            verdict_word = verdict_word or "ISSUE"
    return reviewed_by, issues, verdict_word


def collect_and_report(workspace: Path, image_path: Path) -> tuple[int, str]:
    """校验独立窗口回写的 verdict 并汇总。返回 (exit_code, 输出文本)。"""
    vpath = verdict_path(workspace, image_path)
    if not vpath.is_file():
        return 2, "NO_HOST_WINDOW_VERDICT: 独立窗口尚未回写审核结论"
    reviewed_by, issues, verdict_word = parse_verdict(_read_text(vpath))
    if not reviewed_by:
        return 2, "INVALID_VERDICT: 缺少 Reviewed-by 执行窗口标识（独立窗口证据必须注明执行者）"
    if not verdict_word:
        return 2, "INVALID_VERDICT: 既无 PASS 也无 ISSUE 行，不构成审核结论"
    if issues:
        return 1, f"ISSUE {len(issues)} (reviewed-by: {reviewed_by}):\n" + "\n".join(issues)
    return 0, f"PASS (reviewed-by: {reviewed_by})"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def run(backend: str, image_arg: str, review: bool = False,
        workspace: str | None = None, collect_only: bool = False,
        checklist: list[str] | None = None) -> int:
    """三个视觉质检工具的统一入口（CLI 契约兼容旧实现）。"""
    image_path = Path(image_arg)
    ws = Path(workspace) if workspace else Path.cwd()
    if not image_path.is_file():
        print(f"File not found: {image_path}")
        return 2

    # ⛔ 开发期防死循环刹车（审核模式 --review 绕过；STOP 定稿放行=exit 0，沿旧实现）
    allowed, ncall, global_hit = _bump_and_check(image_path, mode="review" if review else "dev")
    if not allowed:
        why = ("本工作区视觉自检【总调用次数】已达全局上限（换名也绕不过）"
               if global_hit else
               f"本图视觉自检已达 {MAX_PER_FIG} 轮上限（本次第 {ncall} 次）")
        print(
            f"{STOP_TAG}: {why}。【用当前最新图件定稿，不要再改坐标/重编/重调】。"
            f"【如需审核/终审真实复核，请加 --review 参数】"
        )
        return 0

    if not collect_only:
        pass  # 任务卡生成与计数已在上方完成

    exit_code, report = collect_and_report(ws, image_path)
    if exit_code == 2 and not collect_only:
        card = task_card_path(ws, image_path)
        card.parent.mkdir(parents=True, exist_ok=True)
        card.write_text(build_task_card(backend, image_path, review, checklist),
                        encoding="utf-8")
        print(f"任务卡已生成: {card}")
        for note in deterministic_check(image_path):
            print(f"[确定性] {note}")
        print(
            "PENDING_HOST_WINDOW_REVIEW: 请派发宿主独立窗口（视觉审子代理/独立会话）"
            f"按任务卡实际读图审核，并将结论回写 {verdict_path(ws, image_path)} "
            "后重跑本命令收集。"
        )
        print(report)
        return 2
    print(report)
    return exit_code


def workspace_from_args(argv: list[str]) -> tuple[list[str], str | None, bool]:
    """轻量参数预处理：抽取 --workspace/--collect-only，其余原样传递。"""
    rest: list[str] = []
    workspace = None
    collect_only = False
    i = 0
    while i < len(argv):
        arg = argv[i]
        if arg == "--workspace" and i + 1 < len(argv):
            workspace = argv[i + 1]
            i += 2
            continue
        if arg == "--collect-only":
            collect_only = True
            i += 1
            continue
        rest.append(arg)
        i += 1
    return rest, workspace, collect_only


def main_stub(backend: str, usage: str, checklist: list[str] | None = None) -> int:
    argv, workspace, collect_only = workspace_from_args(sys.argv[1:])
    review = "--review" in argv
    image_args = [a for a in argv if not a.startswith("--")]
    if not image_args:
        print(usage)
        return 2
    return run(backend, image_args[0], review=review, workspace=workspace,
               collect_only=collect_only, checklist=checklist)
