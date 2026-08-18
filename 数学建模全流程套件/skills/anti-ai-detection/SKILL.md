# 反AI特征检测 (Anti-AI Detection) v2.0

> **用途**：检测中文学术文本的AI生成特征，提供8维度+8统计特征分析、AI味改写建议、2026国赛AI使用声明生成。
> **触发条件**：用户说"反AI检测"、"AI痕迹检查"、"去AI味"、"anti-ai"、"检测AI生成"、"AI使用声明"。

## 一、工具链总览

| 工具 | 用途 | 调用 |
|------|------|------|
| `tools/anti_ai_detector.py` | 反AI特征检测（v2，基线校准） | `python tools/anti_ai_detector.py <文件> --json` |
| `tools/reference_paper_baseline.py` | 解析参考论文→人类写作基线 | `python tools/reference_paper_baseline.py` |
| `tools/de_ai_writer.py` | AI味逐句定位与改写建议 | `python tools/de_ai_writer.py <文件>` |
| `tools/ai_usage_declaration.py` | 2026国赛AI工具使用声明生成 | `python tools/ai_usage_declaration.py --used --usage "语言润色"` |
| `baseline/human_paper_baseline.json` | 62篇获奖论文基线（20篇OCR可用） | 检测器自动加载 |
| `baseline/REFERENCE_PAPER_ANTI_AI_ANALYSIS.md` | 参考论文反AI特征分析报告 | 只读 |

## 二、检测框架（v2 双层）

### 层1：8维度框架（内容/结构视角，60%权重）
引文特征 / 数据特征 / 观点结论 / 结构框架 / 逻辑关系 / 内容一致性 / 概念阐释 / 语言表达

### 层2：8统计特征（语言统计视角，40%权重，基线校准）
| 特征 | 人类区间（20篇获奖论文） | 超出判定 |
|------|------------------------|---------|
| 突发性Burstiness | 分句CV 0.60-1.10 | <0.45 疑AI（句长过均匀） |
| 句长分布 | 短句54.4-82.3%/中句17.4-42.3%/长句0-7.7% | 长句>10% 疑AI |
| 连接词密度 | 4.2-12.3‰ | >12.3‰ 疑AI |
| 被动语态 | 0.2-4.8% | >4.8% 疑AI |
| 段落CV | 0.5-1.0 | <0.3 疑AI（结构均匀） |
| 压缩比 | 0.58-0.78 | <0.45 疑AI（词汇重复） |
| 字符熵 | bigram熵 9.6-10.2（长文本） | <9.0 疑AI |
| AI模板词 | 0-3个 | ≥5个 疑AI |

### 置信度保护
- <300字：句长分布/连接词/被动/突发性按比例打折（短文本统计不可靠）
- <1000字：字符熵返回中性分
- AI模板词为逐词计数证据，不打折

## 三、使用方法

### 3.1 检测
```bash
# 基本用法（自动加载基线）
python tools/anti_ai_detector.py <文件路径或文本>

# JSON输出（供程序消费）
python tools/anti_ai_detector.py <文件> --json --output result.json
```

### 3.2 改写建议
```bash
python tools/de_ai_writer.py <文件> --output de_ai_report.md
# 输出：AI模板句/被动语态/超长句/模板化连接词序列 逐条定位+改写建议
```

### 3.3 AI使用声明（2026国赛新规）
```bash
# 未使用AI（默认）
python tools/ai_usage_declaration.py --output <工作区>

# 使用了AI
python tools/ai_usage_declaration.py --used --usage "语言润色、代码调试" --output <工作区>
# 生成：AI工具使用声明.tex（插在参考文献前）+ AI工具使用详情.md（转PDF入支撑材料）
```

### 3.4 重新生成基线（参考论文更新后）
```bash
python tools/reference_paper_baseline.py
```

## 四、风险等级
| 等级 | 分数 | 处理 |
|------|------|------|
| low | <25% | 通过 |
| medium | 25-40% | 用 de_ai_writer 定位问题并改写 |
| high | 40-60% | 改写后重测，重点检查模板词与句长分布 |
| critical | >60% | 大段重写，逐段复查 |

## 五、2026 国赛合规铁律
1. 论文参考文献之前必须设置「AI工具使用声明」（二选一，措辞固定）
2. 使用AI必须提供 AI工具使用详情.pdf（工具/版本、用途、提示过程、采纳核验）
3. 故意隐瞒或虚假声明 → 取消评奖资格
4. 声明内容不允许修改措辞

## 六、参考文献
1. 安彤等.基于多维特征分析的AI生成期刊论文内容识别与应对策略研究.知识管理论坛,2025
2. Tian et al. GPTZero: Towards Detecting AI-Generated Text via Zero-Shot Distinguishing with Common n-gram Analysis. 2023
3. Solidjonov. Detecting AI-generated academic language. AI Ethics, 2026
4. Su et al. Research on AI-generated Chinese text detection. AIMS, 2025
5. Qing et al. C-ReD: A Comprehensive Chinese Benchmark. ACL Findings, 2026
6. 全国大学生数学建模竞赛人工智能工具使用规定（2026年试行）
7. Lupynow/math-modeling-skills v1.4.0（八类AI写作痕迹识别）

## 七、注意事项
1. 本工具基于统计特征与规则，**不能替代人工审查**
2. 检测结果供修改方向参考；改写后必须复查
3. 专业领域文本部分特征可能不适用
4. 可选用 HuggingFace 中文检测模型交叉验证（AnxForever/chinese-ai-detector-bert 等，需联网）
