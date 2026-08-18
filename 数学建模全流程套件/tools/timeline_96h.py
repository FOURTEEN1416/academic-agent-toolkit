#!/usr/bin/env python3
"""
timeline_96h.py - 4 天 96 小时倒计时 + 阶段门禁提醒

用法：
  python timeline_96h.py                      # 立即进入交互式
  python timeline_96h.py --start "2026-09-10 18:00"
  python timeline_96h.py --report            # 输出一份进度报告
  python timeline_96h.py --monitor           # 后台监控模式（每 30 分钟打印）
"""

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path


# 国赛硬编码
CONTEST_START = datetime(2026, 9, 10, 18, 0, 0)
CONTEST_END = datetime(2026, 9, 13, 20, 0, 0)
TOTAL_HOURS = 96

# 阶段门禁定义
PHASES = [
    {"time": 0,    "name": "开赛选题",            "checkpoint": "拿到 6 道题"},
    {"time": 0.5,  "name": "选题决策",            "checkpoint": "AI 排序输出 TOP3"},
    {"time": 2,    "name": "分工确定",            "checkpoint": "3 人分工 + 问题拆解"},
    {"time": 4,    "name": "模型方向",            "checkpoint": "3 个候选模型确定"},
    {"time": 12,   "name": "数据处理完成",         "checkpoint": "数据干净 + 3 张表"},
    {"time": 24,   "name": "第一天门禁",          "checkpoint": "主模型跑通 + 论文 0.5"},
    {"time": 36,   "name": "模型求解中",          "checkpoint": "2 个模型结果 + 敏感性"},
    {"time": 48,   "name": "第二天门禁",          "checkpoint": "全模型完成 + 论文 0.8"},
    {"time": 60,   "name": "第三天上午",          "checkpoint": "论文 90%"},
    {"time": 72,   "name": "第三天门禁（倒 24h）", "checkpoint": "图表 300dpi + 摘要"},
    {"time": 84,   "name": "论文精修",            "checkpoint": "全文校对 + 查重"},
    {"time": 90,   "name": "最终检查",            "checkpoint": "格式 + 公式 + 引用"},
    {"time": 94,   "name": "提交准备",            "checkpoint": "PDF + MD5 + 备份"},
    {"time": 96,   "name": "提交截止",            "checkpoint": "上传成功"}
]


def current_phase(now: datetime) -> dict:
    """根据当前时间判断在哪个阶段"""
    elapsed = (now - CONTEST_START).total_seconds() / 3600
    if elapsed < 0:
        return {"name": "赛前", "elapsed": elapsed, "remaining": TOTAL_HOURS, "checkpoint": "等待开赛"}
    if elapsed >= TOTAL_HOURS:
        return {"name": "赛后", "elapsed": elapsed, "remaining": 0, "checkpoint": "比赛已结束"}

    # 找到当前阶段
    current = None
    next_phase = None
    for i, p in enumerate(PHASES):
        if elapsed >= p["time"]:
            current = p
            if i + 1 < len(PHASES):
                next_phase = PHASES[i + 1]
        else:
            break
    return {
        "name": current["name"],
        "elapsed_hours": round(elapsed, 2),
        "remaining_hours": round(TOTAL_HOURS - elapsed, 2),
        "checkpoint": current["checkpoint"],
        "next_phase": next_phase["name"] if next_phase else "已结束",
        "next_phase_in": round(next_phase["time"] - elapsed, 2) if next_phase else 0
    }


def generate_report(now: datetime) -> str:
    """生成进度报告（Markdown）"""
    phase = current_phase(now)
    elapsed = phase.get("elapsed_hours", 0)
    remaining = phase.get("remaining_hours", TOTAL_HOURS)
    progress_pct = round(elapsed / TOTAL_HOURS * 100, 1)

    report = f"""# 进度报告 - T+{elapsed:.1f}h

**生成时间**: {now.strftime("%Y-%m-%d %H:%M:%S")}
**比赛开始**: {CONTEST_START.strftime("%Y-%m-%d %H:%M")}
**比赛结束**: {CONTEST_END.strftime("%Y-%m-%d %H:%M")}
**当前阶段**: {phase['name']}
**进度**: {progress_pct}% ({elapsed:.1f}h / {TOTAL_HOURS}h)
**剩余**: {remaining:.1f}h

## 当前门禁

**{phase['name']}**: {phase['checkpoint']}

"""
    if "next_phase" in phase:
        report += f"**下一阶段**: {phase['next_phase']}（{phase['next_phase_in']:.1f}h 后）\n"

    # 进度条
    bar_len = 50
    filled = int(bar_len * progress_pct / 100)
    bar = "=" * filled + ">" + " " * (bar_len - filled - 1)
    code_fence = "```"
    report += f"\n{code_fence}\n[{bar}] {progress_pct}%\n{code_fence}\n"

    # 3 个 todo 提示
    report += "\n## 待办（按紧迫度）\n"
    if phase["name"] == "开赛选题":
        report += "1. **立刻**: @problem-selection 输入 6 道题\n"
        report += "2. **30 分钟内**: 团队粗读 TOP3\n"
        report += "3. **1 小时内**: 选定题 + 3 人分工\n"
    elif "门禁" in phase["name"]:
        report += "1. **立刻**: 检查门禁清单（见 SKILL.md）\n"
        report += "2. **未达**: 30 分钟会议调方向\n"
        report += "3. **记录**: 写调整日志\n"
    elif "精修" in phase["name"] or "检查" in phase["name"]:
        report += "1. **立刻**: @paper-writing 摘要优化器\n"
        report += "2. **重点**: 公式 + 图表 + 引用\n"
        report += "3. **最后**: 查重 + 格式\n"
    elif phase["name"] == "提交截止":
        report += "1. **立刻**: 上传系统\n"
        report += "2. **同步**: 备份 3 份到云端\n"
        report += "3. **庆祝**: 🎉\n"
    else:
        report += "1. 按当前阶段推进\n"
        report += "2. 每 6 小时同步一次进度\n"
        report += "3. 遇坑立即 @ 全员\n"
    return report


def show_overview():
    """显示完整时间表"""
    print("\n=== 4 天 96 小时 阶段门禁 ===\n")
    print(f"{'T+h':>6s}  {'阶段':18s}  {'门禁':40s}  {'绝对时间'}")
    print("-" * 90)
    for p in PHASES:
        abs_time = CONTEST_START + timedelta(hours=p["time"])
        print(f"{p['time']:>6.1f}  {p['name']:18s}  {p['checkpoint']:40s}  {abs_time.strftime('%m-%d %H:%M')}")


def interactive():
    """交互式：打印当前进度 + 实时刷新"""
    show_overview()
    print("\n=== 当前进度 ===\n")
    now = datetime.now()
    phase = current_phase(now)

    # 赛前
    if phase.get("elapsed_hours", 0) < 0:
        days_to_start = -phase["elapsed_hours"] / 24
        print(f"[赛前] 距离比赛开始还有 {days_to_start:.1f} 天")
        return

    # 赛中
    elapsed = phase["elapsed_hours"]
    remaining = phase["remaining_hours"]
    print(f"[当前阶段] {phase['name']}")
    print(f"[已用] {elapsed:.1f}h / [剩余] {remaining:.1f}h")
    print(f"[门禁] {phase['checkpoint']}")
    if "next_phase" in phase:
        print(f"[下一阶段] {phase['next_phase']}（{phase['next_phase_in']:.1f}h 后）")

    progress_pct = round(elapsed / TOTAL_HOURS * 100, 1)
    bar_len = 50
    filled = int(bar_len * progress_pct / 100)
    bar = "=" * filled + ">" + " " * (bar_len - filled - 1)
    print(f"\n[{bar}] {progress_pct}%\n")

    # 提示
    print(generate_report(now))


def main():
    parser = argparse.ArgumentParser(description="4 天 96h 倒计时 + 阶段门禁")
    parser.add_argument("--start", help="自定义开始时间（默认 2026-09-10 18:00）")
    parser.add_argument("--report", action="store_true", help="输出 Markdown 进度报告")
    parser.add_argument("--overview", action="store_true", help="显示完整时间表")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.start:
        global CONTEST_START
        CONTEST_START = datetime.strptime(args.start, "%Y-%m-%d %H:%M")

    if args.overview:
        show_overview()
        return

    if args.report:
        print(generate_report(datetime.now()))
        return

    if args.json:
        phase = current_phase(datetime.now())
        phase["contest_start"] = CONTEST_START.isoformat()
        phase["contest_end"] = CONTEST_END.isoformat()
        print(json.dumps(phase, ensure_ascii=False, indent=2))
        return

    interactive()


if __name__ == "__main__":
    main()
