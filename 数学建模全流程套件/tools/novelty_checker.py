#!/usr/bin/env python3
"""
novelty_checker.py - 查重（避免和历年国一撞方法）

用法：
  python novelty_checker.py --method "遗传算法"
  python novelty_checker.py --method "ARIMA" --check
"""

import argparse
import json
import re
import sys
from pathlib import Path


# 历年国一常见方法（基于近 5 年公开数据 + 公开获奖论文统计）
COMMON_NSF_METHODS = {
    "优化类": [
        "线性规划", "整数规划", "动态规划", "遗传算法", "蚁群算法", "粒子群",
        "模拟退火", "拉格朗日松弛", "分支定界", "图论", "网络流",
        "强化学习", "多目标优化", "Pareto"
    ],
    "预测类": [
        "ARIMA", "SARIMA", "Prophet", "灰色预测", "指数平滑", "Holt-Winters",
        "随机森林", "XGBoost", "LightGBM", "LSTM", "GRU", "Transformer",
        "CNN", "RNN", "神经网络", "回归分析", "时间序列"
    ],
    "评价类": [
        "AHP", "层次分析法", "TOPSIS", "熵权法", "灰色关联", "模糊综合评价",
        "主成分分析", "PCA", "因子分析", "DEA", "数据包络"
    ],
    "图论类": [
        "Dijkstra", "Floyd", "网络流", "最大流", "最小费用流", "匹配",
        "图神经网络", "GNN", "PageRank", "中心性"
    ],
    "机理类": [
        "微分方程", "ODE", "PDE", "元胞自动机", "传染病模型", "SIR", "SEIR",
        "动力学", "多智能体", "ABM", "仿真"
    ],
    "分类聚类": [
        "K-means", "DBSCAN", "层次聚类", "随机森林", "SVM", "支持向量机",
        "孤立森林", "OneClass-SVM", "朴素贝叶斯", "KNN"
    ]
}


def detect_category(method: str) -> str:
    """根据方法名猜测题型"""
    method_lower = method.lower()
    for cat, methods in COMMON_NSF_METHODS.items():
        for m in methods:
            if m.lower() in method_lower or method_lower in m.lower():
                return cat
    return "未知"


def calculate_novelty(method: str) -> dict:
    """计算方法的新颖度（0-1，1 = 完全新颖）"""
    category = detect_category(method)
    if category == "未知":
        return {
            "method": method,
            "category": "未知",
            "novelty_score": 0.5,
            "is_common": False,
            "suggestion": "未识别的方法，建议人工评估"
        }

    # 检查是否在常见国一方法中
    common_methods = COMMON_NSF_METHODS[category]
    is_in_list = any(m.lower() in method.lower() or method.lower() in m.lower() for m in common_methods)

    # 基于"包含多少个常见方法"打分
    hits = sum(1 for m in common_methods if m.lower() in method.lower())

    if hits == 0:
        novelty = 0.9  # 完全没见过的
        is_common = False
    elif hits == 1:
        novelty = 0.7  # 单方法
        is_common = True
    elif hits == 2:
        novelty = 0.5  # 组合 2 个
        is_common = True
    else:
        novelty = 0.3  # 组合 3+ 个（很常见）
        is_common = True

    # 判定
    if novelty < 0.3:
        suggestion = f"风险高：'{method}' 与历年国一方法高度雷同，必须创新（魔改/组合/加新机制）"
    elif novelty < 0.7:
        suggestion = f"可接受：'{method}' 较常见，建议在论文中强调'为什么选这个方法 + 差异化点'"
    else:
        suggestion = f"新颖度高：'{method}' 不常见，可作为卖点"

    return {
        "method": method,
        "category": category,
        "novelty_score": novelty,
        "is_common": is_common,
        "suggestion": suggestion
    }


def suggest_innovations(method: str) -> list:
    """根据方法推荐创新方向"""
    base_innovations = [
        "加注意力机制（适用：深度学习类）",
        "加多目标 Pareto（适用：单目标方法）",
        "加元学习/迁移学习（适用：数据驱动）",
        "加图神经网络补充（适用：传统机器学习）",
        "加时间动态维度（适用：静态模型）",
        "加不确定性区间估计（适用：点估计方法）",
        "加可解释性模块（SHAP/LIME）（适用：黑盒模型）",
        "加跨领域组合（如：运筹+ML）"
    ]
    return base_innovations[:5]


def main():
    parser = argparse.ArgumentParser(description="方法新颖度查重")
    parser.add_argument("--method", help="拟用方法名")
    parser.add_argument("--list-common", action="store_true", help="列出所有常见国一方法")
    parser.add_argument("--json", action="store_true", help="JSON 输出")
    args = parser.parse_args()

    if args.list_common:
        print("\n=== 历年国一常见方法库 ===\n")
        for cat, methods in COMMON_NSF_METHODS.items():
            print(f"[{cat}]")
            for m in methods:
                print(f"  - {m}")
            print()
        return

    if not args.method:
        print("错误：必须指定 --method 或 --list-common", file=sys.stderr)
        sys.exit(1)

    result = calculate_novelty(args.method)
    result["innovation_suggestions"] = suggest_innovations(args.method)

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return

    print(f"\n[方法] {result['method']}")
    print(f"[题型] {result['category']}")
    print(f"[新颖度] {result['novelty_score']:.2f} / 1.00")
    print(f"[是否常见] {'是' if result['is_common'] else '否'}")
    print(f"\n[建议]\n  {result['suggestion']}\n")
    print(f"[创新方向建议]")
    for i, s in enumerate(result["innovation_suggestions"], 1):
        print(f"  {i}. {s}")


if __name__ == "__main__":
    main()
