# -*- coding: utf-8 -*-
"""facts_audit NUM_RE 回归测试。

2026-09-11 CUMCM2026-A 赛时实锤：原 lookbehind (?<![\w.]) 在 Python Unicode 模式下
把中文当前缀，题面"密度为820"、"温度为28"、"为2.55"句式的数字全部漏抓，导致
14 个真实题面参数被误判"疑似 AI 虚构"。修复为只排除 ASCII 字母数字前缀。
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "skills" / "_utils"))
from facts_audit import extract_numbers_from_text  # noqa: E402


def test_chinese_prefixed_numbers_extracted():
    # 题面最典型句式：中文+为+数字，数字必须被抓到
    nums = extract_numbers_from_text(
        "密度为820 kg/m3、比热容为2600 J/(kg·K)，温度为28°C，"
        "水分浓度（即干基含水率）为2.55 kg/kg，长为25 cm，半径为2 cm"
    )
    assert 820.0 in nums
    assert 2600.0 in nums
    assert 28.0 in nums
    assert 2.55 in nums
    assert 25.0 in nums
    assert 2.0 in nums


def test_ascii_identifier_prefix_still_excluded():
    # 变量名 x2 / 函数名 f1 的尾巴数字不得被抓（修复不得放宽到过宽）
    nums = extract_numbers_from_text("x2 = f1(a3) + y4")
    assert 2.0 not in nums
    assert 1.0 not in nums
    assert 3.0 not in nums
    assert 4.0 not in nums


def test_decimal_and_unit_tail():
    # 小数完整抓取（不把 2.55 拆成 2 和 55）；单位尾巴 km/s 允许
    nums = extract_numbers_from_text("步长 0.1 cm，速率 12km/s，间隔1.5h")
    assert 0.1 in nums
    assert 12.0 in nums
    assert 1.5 in nums


def test_unicode_minus_normalized():
    # U+2212（数学负号 −）归一化：题面 "e−0.89"/"10−7" 的负数形式必须进 OCR 集合。
    # 注意 "e−0.89" 被 "-0.89" 整体消费，正形式 0.89 不再单独出现（正形式由
    # DATA_FACTS/PROBLEM_FACTS 数值字段补登，见 modeling 三源合并审计）。
    nums = extract_numbers_from_text("𝐷= 7 × 10−9e−0.89\n𝐶\n𝐷= 2.4 × 10−3e−0.45𝐶e−3850\n𝑇")
    assert -0.89 in nums
    assert -0.45 in nums
    assert 3850.0 in nums
