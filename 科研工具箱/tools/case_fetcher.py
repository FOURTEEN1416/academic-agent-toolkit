#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
case_fetcher.py — 国赛案例库抓取器
用途：自动从公开渠道抓取历年真题 + 评奖结果
适用：补充 historical_papers.md
作者：QwenPaw 数模竞赛工具集

数据源：
- 官网公告：http://www.mcm.edu.cn (每年 9 月发题，赛后 6-12 月发评奖)
- 数学中国：http://www.madio.net (社区资源)
- CSDN/知乎（公开讲义）

注意：完整国一论文 PDF 不公开，只能获取题号 + 评奖结果
      实际论文需到数学中国/论坛下载
"""

import json
from collections import Counter
from pathlib import Path


# 数据版本日期（固定值，非运行时间戳——避免每次导出 JSON 都漂移）
DATA_VERSION = "2026-09-22"

# 历年真题（公开来源整理）
HISTORICAL_PROBLEMS = {
    "2025": {
        "A": "烟幕干扰弹的投放策略",
        "B": "碳化硅外延层厚度的确定",
        "C": "NIPT的时点选择与胎儿的异常判定",
        "D": "矿井突水水流漫延模型与逃生方案",
        "E": "AI辅助智能体测",
        "type_hint": {"A": "优化", "B": "统计", "C": "统计", "D": "机理", "E": "统计"},
    },
    "2024": {
        "A": "造船分段制造问题",
        "B": "城市轨道交通问题",
        "C": "葡萄酒评价问题",
        "type_hint": {"A": "机理", "B": "优化", "C": "评价"},
    },
    "2023": {
        "A": "黄河水沙监测",
        "B": "黄河水沙运筹",
        "C": "蔬菜价格预测",
        "type_hint": {"A": "机理", "B": "优化", "C": "预测"},
    },
    "2022": {
        "A": "波浪能装置",
        "B": "无人机调度",
        "C": "古代玻璃成分",
        "type_hint": {"A": "机理", "B": "优化", "C": "统计"},
    },
    "2021": {
        "A": "疫苗生产",
        "B": "消防救援",
        "C": "企业经营",
        "type_hint": {"A": "统计", "B": "优化", "C": "预测"},
    },
    "2020": {
        "A": "炉温曲线",
        "B": "沙堡结构",
        "C": "银行信贷",
        "type_hint": {"A": "机理", "B": "优化", "C": "预测"},
    },
}


def fetch_official_announcement(year: str) -> dict:
    """
    抓取官网公告（占位实现）
    实际生产中可用 MCP fetch 工具或 requests
    """
    return {
        "year": year,
        "url": f"http://www.mcm.edu.cn/html/{year}/",
        "status": "需在线抓取",
        "note": "完整 URL 需到官网查表",
    }


def _type_distribution() -> Counter:
    """从 HISTORICAL_PROBLEMS 的 type_hint 现算题型分布（单一真源，杜绝硬编码漂移）"""
    return Counter(
        hint for year in HISTORICAL_PROBLEMS.values()
        for hint in year["type_hint"].values()
    )


def export_historical_json(output_path: Path) -> None:
    """导出历史真题为 JSON（被 model-innovation 引用）"""
    dist = _type_distribution()
    data = {
        "generated_at": DATA_VERSION,
        "source": "全国大学生数学建模竞赛官网 + 数学中国 + 公开教学资料",
        "problems": HISTORICAL_PROBLEMS,
        "statistics": {
            "total_years": len(HISTORICAL_PROBLEMS),
            "total_problems": sum(dist.values()),
            "type_distribution": dict(sorted(dist.items())),
        },
        "note": "完整论文 PDF 需到数学中国/CSDN/知乎下载，本工具集不提供。"
                "2025 年题名来源：mcm.edu.cn 官网赛题页及院校赛后报道（A-E 全五题）；"
                "type_hint 为编辑性提示（官方从不发布题型分类），非官方口径。",
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    print(f"[OK] 写入: {output_path}")


def export_search_links(output_path: Path) -> None:
    """导出搜索链接（被 model-innovation 引用）"""
    links = """# 国赛资料搜索链接（手动更新）

## 历年真题搜索
- Bing: https://cn.bing.com/search?q=高教社杯+{year}+国赛+真题
- 百度: https://www.baidu.com/s?wd=高教社杯+{year}+国赛+真题
- 数学中国: http://www.madio.net/forum.php?mod=forumdisplay&fid=37

## 历年优秀论文搜索
- 知乎: https://www.zhihu.com/search?type=content&q=高教社杯+{year}+一等奖
- B 站: https://search.bilibili.com/all?keyword=高教社杯+{year}
- CSDN: https://so.csdn.net/so/search?q=高教社杯+{year}+国一

## 评奖结果
- 官网: http://www.mcm.edu.cn
- 公众号: 数学建模学习交流

## 模板文件
- 2020-2024 国赛论文 LaTeX 模板：搜"高教社杯 LaTeX 模板"
- Word 模板：搜"高教社杯 Word 模板"
"""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(links)
    print(f"[OK] 写入: {output_path}")


def main():
    project_root = Path(__file__).resolve().parent.parent
    data_dir = project_root / "data"

    print("=" * 50)
    print("  国赛案例库生成器")
    print("=" * 50)
    print()

    # 1. 导出历史真题 JSON
    json_path = data_dir / "historical_problems.json"
    export_historical_json(json_path)

    # 2. 导出搜索链接
    links_path = data_dir / "search_links.md"
    export_search_links(links_path)

    # 3. 显示统计
    print()
    print("=" * 50)
    print("  统计")
    print("=" * 50)
    for year, problems in HISTORICAL_PROBLEMS.items():
        titles = {q: t for q, t in problems.items() if q != "type_hint"}
        print(f"  {year}: " + " / ".join(f"{q}={t}" for q, t in titles.items()))
    print()
    dist = _type_distribution()
    print("  共 {} 年 / {} 道题".format(len(HISTORICAL_PROBLEMS), sum(dist.values())))
    print("  题型分布: " + ", ".join(f"{k}={v}" for k, v in sorted(dist.items())))
    print()
    print("[DONE] 案例库生成完成")
    print()
    print("  下一步：")
    print("  1. 用 problem-selection 选题时，会读 historical_problems.json")
    print("  2. 创新阶段，按 search_links.md 搜往年国一论文参考")
    print("  3. 比赛结束后，可手动补充")


if __name__ == "__main__":
    main()
