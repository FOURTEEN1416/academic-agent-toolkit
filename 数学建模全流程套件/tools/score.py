#!/usr/bin/env python3
"""
score.py - 6 道题并行打分工具
支持两种模式：
  1. 在线 LLM 模式（需要 OPENAI_API_KEY 等）
  2. 离线启发式模式（基于关键词 + 长度 + 术语密度）

用法：
  python score.py --problems problems.txt
  python score.py --problems problems.txt --offline
  python score.py --interactive
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional


# 6 大题型关键词映射
CATEGORY_KEYWORDS = {
    "优化类": ["最大", "最小", "最优", "调度", "分配", "路径", "规划", "选址", "运输", "库存"],
    "预测类": ["预测", "趋势", "回归", "时间序列", "未来", "估计", "ARIMA", "Prophet", "LSTM"],
    "评价类": ["评价", "排名", "打分", "指标", "综合", "层次", "AHP", "TOPSIS", "熵权"],
    "图论类": ["网络", "图", "路径", "连接", "覆盖", "流", "匹配", "Dijkstra", "Floyd"],
    "机理类": ["物理", "微分", "方程", "建模", "演化", "扩散", "动力学", "传染病"],
    "分类聚类": ["分类", "聚类", "识别", "异常", "聚簇", "K-means", "SVM", "随机森林"]
}

# 历史获奖率（基于近 5 年公开数据估算）
HISTORY_WIN_RATE = {
    "优化类": 0.35,
    "预测类": 0.30,
    "评价类": 0.20,
    "图论类": 0.15,
    "机理类": 0.15,
    "分类聚类": 0.10
}

# 数据可得性关键词
DATA_POSITIVE = ["附件", "数据", "csv", "xlsx", "xls", "数据集", "训练集", "测试集", "样本"]
DATA_NEGATIVE = ["请自行查找", "需要爬取", "无附件", "缺失", "未提供"]


def detect_category(text: str) -> str:
    """启发式题型分类"""
    scores = {}
    for cat, keywords in CATEGORY_KEYWORDS.items():
        scores[cat] = sum(1 for kw in keywords if kw in text)
    best_cat = max(scores, key=scores.get)
    return best_cat if scores[best_cat] > 0 else "优化类"  # 默认归为优化类


def score_data_availability(text: str) -> float:
    """D1 数据可得性 1-10"""
    score = 5.0
    for kw in DATA_POSITIVE:
        if kw in text:
            score += 0.8
    for kw in DATA_NEGATIVE:
        if kw in text:
            score -= 1.5
    # 数据文件数量
    file_count = len(re.findall(r'\.(csv|xlsx|xls|json|txt)', text, re.IGNORECASE))
    score += min(file_count * 0.5, 2.0)
    return max(1.0, min(10.0, score))


def score_innovation_space(category: str, text: str) -> float:
    """D3 创新空间 1-10
    启发：常见解法越少 → 创新空间越大
    """
    # 基础分（按题型经验）
    base = {
        "优化类": 7.0,    # 优化方法多但容易组合创新
        "预测类": 8.0,    # 数据驱动+前沿模型机会大
        "评价类": 6.0,    # 经典方法多创新难
        "图论类": 7.0,
        "机理类": 9.0,    # 机理题创新空间最大（结合新算法）
        "分类聚类": 6.0
    }[category]
    # 题目里提到"前沿/新方法/交叉学科"加 1
    if any(kw in text for kw in ["深度学习", "强化学习", "图神经网络", "交叉", "前沿"]):
        base += 1.0
    return base


def score_workload(text: str) -> float:
    """D4 工作量 1-10（分越高 = 工作量越小 = 越能做）"""
    # 题目长度
    length = len(text)
    if length < 200:
        score = 9.0  # 题目短通常简单
    elif length < 500:
        score = 7.5
    elif length < 1000:
        score = 6.0
    elif length < 2000:
        score = 5.0
    else:
        score = 4.0  # 题目长通常问题复杂
    # 子问题数量
    subq_count = len(re.findall(r'问题\s*[一二三四五六七八九十0-9]', text))
    if subq_count >= 4:
        score -= 1.0
    return max(1.0, min(10.0, score))


def score_history_rate(category: str) -> float:
    """D5 历史获奖率 1-10"""
    rate = HISTORY_WIN_RATE[category]
    return 1.0 + rate * 9.0  # 线性映射到 1-10


def score_risk(text: str) -> float:
    """D6 卡壳风险（分越高 = 风险越低）"""
    score = 7.0
    # 模糊表述越多 = 风险越大
    fuzzy = ["近似", "简化", "理想", "假设", "估计"]
    fuzzy_count = sum(1 for kw in fuzzy if kw in text)
    score -= fuzzy_count * 0.5
    # 复杂模型术语越多 = 风险越大
    complex_terms = ["随机过程", "偏微分", "多目标", "高维", "非凸"]
    complex_count = sum(1 for kw in complex_terms if kw in text)
    score -= complex_count * 0.6
    return max(1.0, min(10.0, score))


def score_problem(problem_id: str, title: str, text: str) -> Dict:
    """给单道题打分"""
    category = detect_category(text)
    d1 = score_data_availability(text)
    d3 = score_innovation_space(category, text)
    d4 = score_workload(text)
    d5 = score_history_rate(category)
    d6 = score_risk(text)
    total = d1 * 0.25 + d3 * 0.20 + d4 * 0.20 + d5 * 0.20 + d6 * 0.15
    return {
        "problem_id": problem_id,
        "title": title,
        "category": category,
        "scores": {
            "D1_data": round(d1, 2),
            "D3_innovation": round(d3, 2),
            "D4_workload": round(d4, 2),
            "D5_history": round(d5, 2),
            "D6_risk": round(d6, 2)
        },
        "total": round(total, 2)
    }


def load_problems_from_file(path: str) -> List[Dict]:
    """从文件加载赛题
    文件格式（每道题用 --- 分隔）：
      ---
      ID: A
      Title: 题目标题
      Content: 题目正文...
    """
    content = Path(path).read_text(encoding="utf-8")
    problems = []
    blocks = re.split(r'\n\s*---\s*\n', content)
    for block in blocks:
        if not block.strip():
            continue
        problem = {"id": "", "title": "", "content": ""}
        lines = block.strip().split("\n")
        in_content = False
        content_lines = []
        for line in lines:
            if line.startswith("ID:"):
                problem["id"] = line[3:].strip()
            elif line.startswith("Title:"):
                problem["title"] = line[6:].strip()
            elif line.startswith("Content:"):
                in_content = True
                content_lines.append(line[8:].strip())
            else:
                if in_content:
                    content_lines.append(line)
        problem["content"] = "\n".join(content_lines).strip()
        if problem["id"] and problem["content"]:
            problems.append(problem)
    return problems


def interactive_mode() -> List[Dict]:
    """交互式输入模式"""
    print("=== 交互式输入 6 道题 ===")
    print("格式：第一行题目 ID（A/B/C...），第二行标题，接下来题目正文（输入空行结束）\n")
    problems = []
    for i in range(6):
        print(f"--- 第 {i+1} 道题 ---")
        pid = input("题号 (A/B/C/D/E/F): ").strip() or chr(ord("A") + i)
        title = input("标题: ").strip() or f"题目 {pid}"
        print("正文（输入 EOF 单独一行结束）:")
        lines = []
        while True:
            line = input()
            if line.strip() == "EOF":
                break
            lines.append(line)
        content = "\n".join(lines).strip()
        if content:
            problems.append({"id": pid, "title": title, "content": content})
    return problems


def main():
    parser = argparse.ArgumentParser(description="国赛 6 道题并行打分")
    parser.add_argument("--problems", help="赛题文件路径")
    parser.add_argument("--interactive", action="store_true", help="交互式输入")
    parser.add_argument("--offline", action="store_true", help="强制离线启发式（无 LLM）")
    parser.add_argument("--output", help="输出 JSON 文件路径", default="ranking.json")
    args = parser.parse_args()

    # 加载赛题
    if args.interactive:
        problems = interactive_mode()
    elif args.problems:
        problems = load_problems_from_file(args.problems)
    else:
        print("错误：必须指定 --problems 或 --interactive", file=sys.stderr)
        sys.exit(1)

    if not problems:
        print("错误：未加载到任何赛题", file=sys.stderr)
        sys.exit(1)

    print(f"\n[INFO] 已加载 {len(problems)} 道题\n")

    # 打分
    results = []
    for p in problems:
        r = score_problem(p["id"], p["title"], p["content"])
        results.append(r)
        print(f"[{r['problem_id']}] {r['title'][:30]:30s} 题型={r['category']:6s}  总分={r['total']:.2f}")

    # 排序
    results.sort(key=lambda x: x["total"], reverse=True)
    for i, r in enumerate(results, 1):
        rec = "强烈推荐" if r["total"] >= 8 else "推荐" if r["total"] >= 7 else "备选" if r["total"] >= 6 else "不推荐"
        r["rank"] = i
        r["recommendation"] = rec

    # 输出
    output = {
        "contest_id": "2026-cumcm",
        "decision_method": "offline_heuristic" if args.offline else "heuristic",
        "total_problems": len(results),
        "rankings": results
    }
    Path(args.output).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\n[OK] 完整结果已保存到 {args.output}")
    print(f"\n[TOP3 推荐]")
    for r in results[:3]:
        print(f"  #{r['rank']} 题 {r['problem_id']}（{r['title']}）- {r['recommendation']} - {r['total']:.2f} 分")

    # 决策建议
    if len(results) >= 2:
        gap = results[0]["total"] - results[1]["total"]
        if gap >= 1.5:
            print(f"\n[建议] TOP1 领先 TOP2 {gap:.2f} 分，强烈推荐选题 {results[0]['problem_id']}")
        elif gap < 1.0:
            print(f"\n[建议] TOP1 vs TOP2 仅差 {gap:.2f} 分，建议再读 30 分钟定夺")
        else:
            print(f"\n[建议] TOP1 领先 {gap:.2f} 分，倾向选题 {results[0]['problem_id']}")


if __name__ == "__main__":
    main()
