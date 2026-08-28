# data/ 目录

存放国赛相关数据资产。

## 文件清单
- `reference_models.json` — 6 类题型参考模型库（被 `problem-selection/model_recommender.py` 引用）
- `case_patterns.md` — 题型规律 + 常见国一方法库（被 `model-innovation/novelty_checker.py` 引用）

## 维护说明
- 比赛结束后，可补充 `historical_papers.json`（历年真题 + 优秀论文链接）
- 重跑 `python tools/data_init.py` 即可重置
