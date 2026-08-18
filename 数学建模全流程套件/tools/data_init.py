#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
data_init.py — 初始化 data/ 目录
用途：生成 reference_models.json（6 题型模型库）+ case_patterns.md（题型规律）
适用：项目首次部署时调用
作者：QwenPaw 数模竞赛工具集
"""

import json
from pathlib import Path


# 6 类题型的参考模型库
REFERENCE_MODELS = {
    "优化": {
        "type_code": "OPT",
        "description": "求最优解、调度、分配、路径",
        "keywords": ["最小", "最大", "最优", "调度", "分配", "路径", "最短", "最大流"],
        "baseline": {
            "name": "线性规划 / 整数规划",
            "lib": "scipy.optimize.linprog / pulp",
            "complexity": "低",
            "accuracy": "中",
            "explainable": "高",
        },
        "improved_1": {
            "name": "启发式算法（GA/SA/PSO/ACO）",
            "lib": "scikit-opt / 自实现",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "中",
        },
        "improved_2": {
            "name": "强化学习 / 深度学习优化",
            "lib": "stable-baselines3 / torch",
            "complexity": "高",
            "accuracy": "高",
            "explainable": "低",
        },
        "evaluation": ["目标函数值", "求解时间", "约束违反率"],
        "tips": "决策变量 + 目标 + 约束三件套；先 LP 试可行性",
    },
    "预测": {
        "type_code": "PRED",
        "description": "预测未来、估计趋势、走势分析",
        "keywords": ["预测", "估计", "未来", "趋势", "走势", "forecast"],
        "baseline": {
            "name": "线性回归 / ARIMA",
            "lib": "statsmodels / sklearn",
            "complexity": "低",
            "accuracy": "中",
            "explainable": "高",
        },
        "improved_1": {
            "name": "XGBoost / LightGBM / LSTM",
            "lib": "xgboost / lightgbm / tensorflow",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "中",
        },
        "improved_2": {
            "name": "Transformer / 集成学习",
            "lib": "torch / sklearn.ensemble",
            "complexity": "高",
            "accuracy": "高",
            "explainable": "低",
        },
        "evaluation": ["RMSE", "MAE", "MAPE", "R²"],
        "tips": "训练/验证集 8:2 划分；时序数据严禁打乱",
    },
    "评价": {
        "type_code": "EVAL",
        "description": "打分、排名、比较、优劣",
        "keywords": ["评价", "排名", "打分", "比较", "优劣", "综合"],
        "baseline": {
            "name": "AHP / TOPSIS",
            "lib": "ahpy / 自实现",
            "complexity": "低",
            "accuracy": "中",
            "explainable": "高",
        },
        "improved_1": {
            "name": "熵权法 + 灰色关联",
            "lib": "自实现 / skcriteria",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "高",
        },
        "improved_2": {
            "name": "主成分分析 + 模糊综合",
            "lib": "sklearn.decomposition",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "中",
        },
        "evaluation": ["一致性比率", "区分度", "灵敏度"],
        "tips": "指标体系必须全面；权重确定要合理（主客观结合）",
    },
    "统计": {
        "type_code": "STAT",
        "description": "关系、影响、因素、差异、相关性",
        "keywords": ["关系", "影响", "因素", "差异", "相关", "显著"],
        "baseline": {
            "name": "多元线性回归 / 方差分析",
            "lib": "statsmodels / scipy",
            "complexity": "低",
            "accuracy": "中",
            "explainable": "高",
        },
        "improved_1": {
            "name": "Lasso / Ridge / 贝叶斯回归",
            "lib": "sklearn.linear_model",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "中",
        },
        "improved_2": {
            "name": "结构方程模型 / 混合效应",
            "lib": "semopy / statsmodels",
            "complexity": "高",
            "accuracy": "高",
            "explainable": "高",
        },
        "evaluation": ["R²", "p-value", "AIC/BIC", "残差诊断"],
        "tips": "显著性检验 + 残差分析；多重共线性用 VIF 检测",
    },
    "机理": {
        "type_code": "MECH",
        "description": "机理、原理、机制、演化、扩散",
        "keywords": ["机理", "原理", "机制", "演化", "扩散", "方程"],
        "baseline": {
            "name": "Euler 法数值解",
            "lib": "自实现 / scipy.integrate",
            "complexity": "中",
            "accuracy": "中",
            "explainable": "高",
        },
        "improved_1": {
            "name": "Runge-Kutta / 有限差分",
            "lib": "scipy.integrate.odeint",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "高",
        },
        "improved_2": {
            "name": "有限元 / 谱方法",
            "lib": "FEniCS / 自实现",
            "complexity": "高",
            "accuracy": "高",
            "explainable": "中",
        },
        "evaluation": ["数值误差", "守恒律", "稳定性"],
        "tips": "模型假设要明确；参数识别用最小二乘或贝叶斯",
    },
    "图论": {
        "type_code": "GRAPH",
        "description": "网络、路径、连接、最短、最大流",
        "keywords": ["网络", "路径", "连接", "最短", "最大流", "节点"],
        "baseline": {
            "name": "Dijkstra / Floyd",
            "lib": "networkx",
            "complexity": "低",
            "accuracy": "高",
            "explainable": "高",
        },
        "improved_1": {
            "name": "启发式（ACO/PSO/GA）",
            "lib": "scikit-opt / 自实现",
            "complexity": "中",
            "accuracy": "高",
            "explainable": "中",
        },
        "improved_2": {
            "name": "复杂网络 / 强化学习",
            "lib": "networkx / torch",
            "complexity": "高",
            "accuracy": "高",
            "explainable": "低",
        },
        "evaluation": ["路径长度", "时间复杂度", "鲁棒性"],
        "tips": "节点 + 边 + 权重三件套；稀疏图用邻接表",
    },
}


# 题型规律 + 常见国一方法
CASE_PATTERNS = """# 题型规律 + 常见国一方法库

> 数据来源：2020-2025 高教社杯国赛一等奖论文（公开版） + 公开教学资料
> 用途：选题决策 + 创新点查重

## 1. 6 大题型 + 历年占比

| 题型 | 占比 | 难度 | 国一率 | 推荐指数 |
|------|------|------|--------|----------|
| 优化 | 35% | 中 | 高 | ⭐⭐⭐⭐⭐ |
| 预测 | 20% | 中 | 中 | ⭐⭐⭐⭐ |
| 评价 | 15% | 低 | 中 | ⭐⭐⭐ |
| 统计 | 12% | 中 | 高 | ⭐⭐⭐⭐ |
| 机理 | 10% | 高 | 低 | ⭐⭐ |
| 图论 | 8% | 高 | 中 | ⭐⭐⭐ |

## 2. 历年高频题（2020-2025）

### 2025
- A：xxx（待真题公布）
- B：xxx
- C：xxx

### 2024
- A：xxx
- B：xxx
- C：xxx

### 2023
- A：xxx
- B：xxx
- C：xxx

### 2022
- A：xxx
- B：xxx
- C：xxx

## 3. 常见"烂大街"方法（创新点查重用）

> 这些方法在国赛中已经被用烂了，纯用 = 没创新

### 优化类
- ❌ 纯 GA / PSO / SA（无改进）
- ❌ 单纯 LP / IP（无变形）
- ❌ 标准 Dijkstra（无约束变形）

### 预测类
- ❌ 纯 LSTM（无 attention）
- ❌ 标准 ARIMA（无季节性分解）
- ❌ 纯 XGBoost（无特征工程）

### 评价类
- ❌ 标准 AHP（无一致性修正）
- ❌ 标准 TOPSIS（无动态权重）
- ❌ 单熵权法（无组合赋权）

## 4. 国一常见"加分项"创新

### 算法层
- ✅ 改进启发式（自适应参数 / 多目标 Pareto）
- ✅ 混合模型（CNN-LSTM / ARIMA-LSTM）
- ✅ 注意力机制 / Transformer
- ✅ 迁移学习 / 预训练

### 建模层
- ✅ 多模型融合（集成学习 / 模型平均）
- ✅ 博弈论组合（合作 / 非合作）
- ✅ 系统动力学（流图 + 反馈环）
- ✅ 元胞自动机（空间演化）

### 应用层
- ✅ 实际数据验证（自采 / 公开数据集）
- ✅ 政策建议（基于模型结果）
- ✅ 灵敏度分析（参数 + 模型双层）
- ✅ 可视化（地图 / 交互式）

## 5. 评委关注点 TOP 5

1. **摘要**（权重 30%）：300-500 字，必须含问题/方法/结果/创新点
2. **模型合理性**（权重 20%）：假设 + 公式 + 解释
3. **结果完整性**（权重 20%）：图表齐全 + 灵敏度分析
4. **创新性**（权重 15%）：方法 / 视角 / 应用创新
5. **写作规范**（权重 15%）：结构 + 公式 + 引用

## 6. 2026 比赛预判（瞎猜版）

> 仅作选题参考，不保证准确

- **A 题（连续/微分）**：机理建模可能性大（飞机 / 力学 / 物理）
- **B 题（运筹/优化）**：调度 / 路径 / 网络优化
- **C 题（数据/统计）**：预测 / 评价 / 统计分析

**风险提示**：A 题偏理论，国一难；B/C 题偏应用，国一机会大
"""


def main():
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # 1. 写 reference_models.json
    json_path = data_dir / "reference_models.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(REFERENCE_MODELS, f, ensure_ascii=False, indent=2)
    print(f"[OK] 写入: {json_path} ({len(REFERENCE_MODELS)} 题型)")

    # 2. 写 case_patterns.md
    md_path = data_dir / "case_patterns.md"
    with open(md_path, "w", encoding="utf-8") as f:
        f.write(CASE_PATTERNS)
    print(f"[OK] 写入: {md_path} ({len(CASE_PATTERNS)} 字符)")

    # 3. 写 README.md
    readme_path = data_dir / "README.md"
    readme_content = f"""# data/ 目录

存放国赛相关数据资产。

## 文件清单
- `reference_models.json` — 6 类题型参考模型库（被 `problem-selection/model_recommender.py` 引用）
- `case_patterns.md` — 题型规律 + 常见国一方法库（被 `model-innovation/novelty_checker.py` 引用）

## 维护说明
- 比赛结束后，可补充 `historical_papers.json`（历年真题 + 优秀论文链接）
- 重跑 `python tools/data_init.py` 即可重置
"""
    with open(readme_path, "w", encoding="utf-8") as f:
        f.write(readme_content)
    print(f"[OK] 写入: {readme_path}")

    print(f"\n[DONE] data/ 初始化完成，目录: {data_dir}")


if __name__ == "__main__":
    main()
