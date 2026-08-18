#!/usr/bin/env python3
"""
反AI检测工具链测试套件
覆盖：anti_ai_detector.py v2（基线校准）、de_ai_writer.py、ai_usage_declaration.py、
reference_paper_baseline.py（基线解析）

验证点：
- 人类风格文本判定为 low（假阳性防护）
- AI风格文本至少 medium 且 AI模板词特征高
- 基线文件存在且包含 20 篇论文特征
- de_ai_writer 能定位 AI 模板句
- AI 使用声明符合 2026 国赛新规
"""
import json
import os
import sys
import re

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))

from 数学建模全流程套件.tools.anti_ai_detector import AntiAIDetector
from 数学建模全流程套件.tools.de_ai_writer import DeAiWriter
from 数学建模全流程套件.tools.ai_usage_declaration import (
    build_declaration, build_detail_md, TEMPLATE_NOT_USED, TEMPLATE_USED,
)

TOOLS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "数学建模全流程套件", "tools")
BASELINE_JSON = os.path.join(TOOLS_DIR, "..", "baseline", "human_paper_baseline.json")

HUMAN_SAMPLE = """针对问题一，本文建立了基于变步长搜索算法求解的单目标优化模型。本文将工作抛物面尽可能贴近理想抛物面作为目标函数，将促动器伸缩量作为决策变量。通过变步长搜索算法，求得促动器最优伸缩量。针对问题二，本文在问题一的基础上，进一步考虑了促动器的调节成本，建立了多目标优化模型。利用粒子群算法进行求解，得到促动器的调节方案。数值实验表明，本文建立的模型能够有效解决主动反射面的形状调节问题，具有一定的实用价值。"""

AI_SAMPLE = """随着人工智能技术的快速发展，大规模语言模型在自然语言处理领域取得了显著进展。近年来，基于Transformer架构的大语言模型如GPT系列、BERT等，在文本生成、机器翻译、问答系统等任务中展现出强大的能力。值得注意的是，这些模型不仅能够生成流畅自然的文本，还能在一定程度上理解上下文语义，为人工智能的应用开辟了新的可能性。然而，随着AI生成文本质量的不断提升，如何检测和区分AI生成的文本与人类撰写的文本成为一个重要的研究课题。本文旨在探讨AI生成文本的特征分析方法，提出一种基于多维特征的检测框架。首先，本文从语言表达、结构框架、逻辑关系等8个维度对AI生成文本进行分析。其次，通过统计特征提取和机器学习分类器，实现了对AI生成文本的有效检测。最后，实验结果表明，本文提出的方法在多个基准数据集上取得了优异的性能。总而言之，本文的研究为AI生成文本检测提供了新的思路和方法，具有重要的理论价值和实际应用意义。综上所述，随着深度学习的不断发展，该领域的研究将会不断深入，为相关领域的进一步研究奠定了坚实的基础。"""


def test_detector_rejects_ai_sample():
    det = AntiAIDetector(AI_SAMPLE)
    r = det.detect()
    # AI 样本：AI模板词命中应显著
    template_score = [s for s in r.statistical_scores if s["name"] == "AI模板词"][0]
    assert template_score["ai_likelihood"] >= 0.3, f"AI模板词评分过低: {template_score}"
    assert r.risk_level in ("medium", "high", "critical") or r.overall_score >= 0.2, \
        f"AI样本应至少 medium: {r.risk_level} {r.overall_score}"


def test_detector_not_false_positive_on_human():
    det = AntiAIDetector(HUMAN_SAMPLE)
    r = det.detect()
    # 人类样本不应判 high/critical
    assert r.risk_level in ("low", "medium"), f"人类样本误判: {r.risk_level}"
    # 人类样本 AI模板词命中应 <3
    template_score = [s for s in r.statistical_scores if s["name"] == "AI模板词"][0]
    assert template_score["value"] < 3, f"人类样本AI模板词过多: {template_score['value']}"


def test_baseline_exists_and_valid():
    assert os.path.exists(BASELINE_JSON), f"基线文件不存在: {BASELINE_JSON}"
    with open(BASELINE_JSON, encoding="utf-8") as f:
        bl = json.load(f)
    assert bl["paper_count"] >= 15, f"基线论文数不足: {bl['paper_count']}"
    feats = bl["features"]
    for key in ["short_sent_pct", "passive_pct", "connector_density_per_1000"]:
        assert key in feats, f"缺少特征 {key}"
        assert feats[key]["mean"] is not None, f"特征 {key} 均值为空"
    # 基线区间合理性
    assert 50 < feats["short_sent_pct"]["mean"] < 85
    assert feats["passive_pct"]["mean"] < 5


def test_de_ai_writer_finds_issues():
    engine = DeAiWriter(AI_SAMPLE)
    r = engine.analyze()
    types = {s["issue_type"] for s in r.suggestions}
    assert "AI模板句" in types, f"未定位AI模板句: {types}"
    assert r.issues_found >= 1


def test_ai_declaration_used_and_not_used():
    used = build_declaration(used=True, usage="语言润色")
    assert "使用了AI工具" in used and "语言润色" in used
    assert "参考文献" not in used  # 声明本身不含无关内容
    not_used = build_declaration(used=False, usage="")
    assert "未使用任何AI工具" in not_used
    assert "未使用" in TEMPLATE_NOT_USED and "主要用于" in TEMPLATE_USED


def test_ai_declaration_detail_template():
    detail = build_detail_md("代码调试", [], "", "", "", "")
    assert "AI工具使用详情" in detail
    assert "名称、版本或型号" in detail
    assert "采纳、人工修改和核验" in detail
    assert "2026年试行" in detail


def test_detector_json_output_serializable():
    import dataclasses
    det = AntiAIDetector(AI_SAMPLE)
    r = det.detect()
    d = dataclasses.asdict(r)
    json.dumps(d, ensure_ascii=False)  # 必须可序列化


if __name__ == "__main__":
    import traceback
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    passed = 0
    for t in tests:
        try:
            t()
            print(f"PASS {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"FAIL {t.__name__}: {e}")
        except Exception as e:
            traceback.print_exc()
            print(f"ERROR {t.__name__}: {e}")
    print(f"\n{passed}/{len(tests)} passed")
    sys.exit(0 if passed == len(tests) else 1)
