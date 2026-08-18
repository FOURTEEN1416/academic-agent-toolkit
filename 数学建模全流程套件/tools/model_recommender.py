#!/usr/bin/env python3
"""
model_recommender.py - 按题型推荐 3-5 个模型
支持离线模式（基于预置模型库），无需 LLM 也能跑

用法：
  python model_recommender.py --category 优化类
  python model_recommender.py --interactive
"""

import argparse
import json
import sys
from pathlib import Path


# 预置模型库（6 大题型 × 4-5 模型）
MODEL_LIBRARY = {
    "优化类": [
        {
            "name": "整数规划 (ILP)",
            "difficulty": "中",
            "libs": ["pulp", "ortools", "scipy.optimize"],
            "innovation_potential": "中",
            "data_needs": "低",
            "use_case": "离散决策（选址/分配/调度）"
        },
        {
            "name": "遗传算法 + 局部搜索",
            "difficulty": "中",
            "libs": ["scikit-opt", "geatpy"],
            "innovation_potential": "高",
            "data_needs": "低",
            "use_case": "复杂非凸/多目标优化"
        },
        {
            "name": "强化学习 (Q-Learning / DQN)",
            "difficulty": "高",
            "libs": ["stable-baselines3", "gym"],
            "innovation_potential": "高",
            "data_needs": "中",
            "use_case": "序贯决策/动态调度"
        },
        {
            "name": "拉格朗日松弛 + 启发式",
            "difficulty": "高",
            "libs": ["gurobipy", "numpy"],
            "innovation_potential": "高",
            "data_needs": "低",
            "use_case": "大规模组合优化"
        },
        {
            "name": "多目标进化 (NSGA-II/III)",
            "difficulty": "中",
            "libs": ["pymoo", "deap"],
            "innovation_potential": "中",
            "data_needs": "低",
            "use_case": "多目标 Pareto 前沿"
        }
    ],
    "预测类": [
        {
            "name": "ARIMA / SARIMA",
            "difficulty": "低",
            "libs": ["statsmodels", "pmdarima"],
            "innovation_potential": "低",
            "data_needs": "中",
            "use_case": "平稳时间序列"
        },
        {
            "name": "Prophet",
            "difficulty": "低",
            "libs": ["prophet"],
            "innovation_potential": "低",
            "data_needs": "中",
            "use_case": "带季节性的趋势"
        },
        {
            "name": "XGBoost / LightGBM",
            "difficulty": "中",
            "libs": ["xgboost", "lightgbm"],
            "innovation_potential": "中",
            "data_needs": "高",
            "use_case": "表格数据 + 特征工程"
        },
        {
            "name": "LSTM / Transformer 时序",
            "difficulty": "高",
            "libs": ["pytorch", "tensorflow"],
            "innovation_potential": "高",
            "data_needs": "高",
            "use_case": "长序列 + 复杂依赖"
        },
        {
            "name": "灰色预测 + 残差修正",
            "difficulty": "中",
            "libs": ["numpy"],
            "innovation_potential": "高",
            "data_needs": "低",
            "use_case": "小样本预测（国赛加分项）"
        }
    ],
    "评价类": [
        {
            "name": "AHP 层次分析法",
            "difficulty": "低",
            "libs": ["numpy"],
            "innovation_potential": "低",
            "data_needs": "低",
            "use_case": "主观权重 + 一致性检验"
        },
        {
            "name": "TOPSIS 优劣解距离法",
            "difficulty": "低",
            "libs": ["numpy", "scipy"],
            "innovation_potential": "低",
            "data_needs": "中",
            "use_case": "多指标客观评价"
        },
        {
            "name": "熵权法 + 灰色关联",
            "difficulty": "中",
            "libs": ["numpy"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "客观权重 + 关联度"
        },
        {
            "name": "模糊综合评价",
            "difficulty": "中",
            "libs": ["scikit-fuzzy"],
            "innovation_potential": "中",
            "data_needs": "低",
            "use_case": "模糊语义评价"
        },
        {
            "name": "主成分分析 (PCA) + 综合得分",
            "difficulty": "中",
            "libs": ["sklearn"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "降维 + 综合得分"
        }
    ],
    "图论类": [
        {
            "name": "Dijkstra / Floyd 最短路",
            "difficulty": "低",
            "libs": ["networkx"],
            "innovation_potential": "低",
            "data_needs": "中",
            "use_case": "静态网络最短路"
        },
        {
            "name": "网络流（最大流/最小费用流）",
            "difficulty": "中",
            "libs": ["networkx", "ortools"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "流量分配"
        },
        {
            "name": "图神经网络 (GNN)",
            "difficulty": "高",
            "libs": ["pytorch-geometric", "dgl"],
            "innovation_potential": "高",
            "data_needs": "高",
            "use_case": "节点/边分类、链路预测"
        },
        {
            "name": "复杂网络中心性",
            "difficulty": "中",
            "libs": ["networkx"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "关键节点识别"
        }
    ],
    "机理类": [
        {
            "name": "微分方程（ODE/PDE）数值解",
            "difficulty": "中",
            "libs": ["scipy.integrate", "sympy"],
            "innovation_potential": "中",
            "data_needs": "低",
            "use_case": "物理/生物机理"
        },
        {
            "name": "元胞自动机",
            "difficulty": "中",
            "libs": ["numpy", "mesa"],
            "innovation_potential": "高",
            "data_needs": "低",
            "use_case": "空间演化/传染病"
        },
        {
            "name": "多智能体仿真 (ABM)",
            "difficulty": "高",
            "libs": ["mesa", "repast4py"],
            "innovation_potential": "高",
            "data_needs": "中",
            "use_case": "个体决策 + 群体涌现"
        },
        {
            "name": "SIR/SEIR 传染病模型",
            "difficulty": "中",
            "libs": ["scipy", "numpy"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "流行病传播"
        }
    ],
    "分类聚类": [
        {
            "name": "K-means / DBSCAN",
            "difficulty": "低",
            "libs": ["sklearn"],
            "innovation_potential": "低",
            "data_needs": "中",
            "use_case": "无监督聚类"
        },
        {
            "name": "随机森林 / XGBoost",
            "difficulty": "中",
            "libs": ["sklearn", "xgboost"],
            "innovation_potential": "中",
            "data_needs": "高",
            "use_case": "监督分类"
        },
        {
            "name": "孤立森林 / OneClass-SVM",
            "difficulty": "中",
            "libs": ["sklearn", "pyod"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "异常检测"
        },
        {
            "name": "t-SNE / UMAP 可视化",
            "difficulty": "中",
            "libs": ["sklearn", "umap-learn"],
            "innovation_potential": "中",
            "data_needs": "中",
            "use_case": "高维数据降维可视化"
        }
    ]
}


def recommend(category: str, top_k: int = 5) -> list:
    """返回指定题型的 top_k 模型"""
    if category not in MODEL_LIBRARY:
        print(f"错误：未知题型 '{category}'", file=sys.stderr)
        print(f"支持的题型：{', '.join(MODEL_LIBRARY.keys())}", file=sys.stderr)
        sys.exit(1)
    models = MODEL_LIBRARY[category]
    # 按 innovation_potential 排序（高 > 中 > 低）
    priority = {"高": 3, "中": 2, "低": 1}
    models_sorted = sorted(models, key=lambda m: priority[m["innovation_potential"]], reverse=True)
    return models_sorted[:top_k]


def interactive():
    print("=== 模型推荐 ===\n")
    print("支持的题型：")
    for i, cat in enumerate(MODEL_LIBRARY.keys(), 1):
        print(f"  {i}. {cat}")
    choice = input("\n请选择题型（输入数字或名称）: ").strip()
    if choice.isdigit():
        cat = list(MODEL_LIBRARY.keys())[int(choice) - 1]
    else:
        cat = choice
    print(f"\n[推荐模型 - {cat}]\n")
    for i, m in enumerate(recommend(cat), 1):
        print(f"  {i}. 【{m['name']}】")
        print(f"     难度: {m['difficulty']} | 创新潜力: {m['innovation_potential']} | 数据需求: {m['data_needs']}")
        print(f"     Python 库: {', '.join(m['libs'])}")
        print(f"     适用场景: {m['use_case']}\n")


def main():
    parser = argparse.ArgumentParser(description="按题型推荐模型")
    parser.add_argument("--category", help="题型名称")
    parser.add_argument("--top-k", type=int, default=5, help="推荐 top-k")
    parser.add_argument("--interactive", action="store_true", help="交互式")
    parser.add_argument("--list", action="store_true", help="列出所有题型")
    args = parser.parse_args()

    if args.list:
        print("支持的题型：")
        for cat in MODEL_LIBRARY.keys():
            print(f"  - {cat}")
        return

    if args.interactive:
        interactive()
    elif args.category:
        models = recommend(args.category, args.top_k)
        output = {"category": args.category, "recommendations": models}
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print("错误：必须指定 --category 或 --interactive 或 --list", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
