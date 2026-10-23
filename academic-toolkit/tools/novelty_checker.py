#!/usr/bin/env python3
"""
novelty_checker.py - 查重（避免和历年国一撞方法）

用法：
  python novelty_checker.py --method "遗传算法"
  python novelty_checker.py --method "ARIMA" --json
  python novelty_checker.py --list-common

口径：novelty_score 是"与离线常见方法名字面表的重合度反向指标"，
命中数越多分越低；0 命中输出"未知"，需人工/语料比对，不构成新颖性结论。
"""

import argparse
import json
import sys


# 离线常见方法名字面表（手工维护，约 73 条；不接入仓内 2021-2025 获奖论文语料，
# 故只能做字面重合检测，不能作为新颖性判据）
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


def _matched_common_methods(method: str) -> list:
    """返回 method 字面命中的离线常见方法名（跨题型去重）。

    只做字面包含匹配：库内方法名出现在 method 中即算命中。
    若某命中名是另一命中名的子串（如 SARIMA→ARIMA、图神经网络→神经网络），
    只保留更长者，避免单一方法被重复计数。
    """
    method_lower = method.lower()
    matched = []
    for methods in COMMON_NSF_METHODS.values():
        for m in methods:
            if m.lower() in method_lower and m not in matched:
                matched.append(m)
    return [
        m for m in matched
        if not any(m != other and m.lower() in other.lower() for other in matched)
    ]


def detect_category(method: str) -> str:
    """按命中方法所属题型给出提示性分类（编辑性口径，非官方题型分类）"""
    matched = _matched_common_methods(method)
    for cat, methods in COMMON_NSF_METHODS.items():
        if any(m in methods for m in matched):
            return cat
    return "未知"


def calculate_novelty(method: str) -> dict:
    """计算与离线常见方法库的字面重合度（单调口径：命中越多，分越低）。

    novelty_score 不是新颖性证明：工具无法判断"有无改进"，
    0 命中只代表离线表未收录，一律输出"未知"。
    """
    matched = _matched_common_methods(method)
    hits = len(matched)
    category = detect_category(method)

    if hits == 0:
        return {
            "method": method,
            "category": category,
            "common_method_hits": 0,
            "common_methods_matched": [],
            "novelty_score": None,
            "is_common": None,
            "verdict": "未知",
            "suggestion": (
                "离线方法库未命中：未命中不等于新颖，不构成创新性结论。"
                "需人工/语料比对后再判断是否与历年国一撞方法"
                "（真源：academic-toolkit/data/historical_problems.json + 获奖论文语料）。"
            ),
        }

    novelty = round(1.0 / (1 + hits), 2)
    return {
        "method": method,
        "category": category,
        "common_method_hits": hits,
        "common_methods_matched": matched,
        "novelty_score": novelty,
        "is_common": True,
        "verdict": "命中离线常见方法名",
        "suggestion": (
            f"离线库命中 {hits} 个常见方法名（{'、'.join(matched)}），命中越多分越低。"
            "纯用标准方法（无改进/无差异化）不构成创新点，判断口径见 "
            "academic-toolkit/data/case_patterns.md §3；"
            "工具无法识别'有无改进'，差异化点需人工说明并给出量化验证。"
        ),
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
        print("\n=== 离线常见方法名字面表（手工维护）===\n")
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
    print(f"[命中常见方法数] {result['common_method_hits']}")
    if result["common_methods_matched"]:
        print(f"[命中方法] {'、'.join(result['common_methods_matched'])}")
    if result["novelty_score"] is None:
        print("[新颖度] 未知（离线库未命中，需人工/语料比对）")
    else:
        print(f"[新颖度] {result['novelty_score']:.2f} / 1.00（越高=字面重合越少，不是新颖性证明）")
    if result["is_common"] is None:
        print("[是否常见] 未知")
    else:
        print(f"[是否常见] {'是' if result['is_common'] else '否'}")
    print(f"\n[建议]\n  {result['suggestion']}\n")
    print("[创新方向套路（启发用，非结论）]")
    for i, s in enumerate(result["innovation_suggestions"], 1):
        print(f"  {i}. {s}")


if __name__ == "__main__":
    main()
