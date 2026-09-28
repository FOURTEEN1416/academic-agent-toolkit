# 参考资料索引

本目录包含commit-with-reflection技能的所有参考文档。

## 文档列表

### 核心参考文档

1. **[error-taxonomy.md](error-taxonomy.md)** - 错误分类体系
   - 7种错误类型详解(语法、类型、逻辑、架构、集成、性能、安全)
   - 严重程度评级标准(严重、重要、次要)
   - 常见错误模式库
   - 错误分类决策树
   - 使用指南

2. **[best-practices.md](best-practices.md)** - 反思报告最佳实践指南
   - 核心原则(及时性、深度分析、可执行性、模式识别)
   - 10个章节的详细编写指南
   - 高级技巧(思维导图、个人模式库、定期回顾)
   - 常见问题解答
   - 质量检查清单

## 快速导航

### 按使用场景

**编写反思报告时**:
- 查看 [best-practices.md](best-practices.md) 了解如何编写高质量报告
- 参考 [error-taxonomy.md](error-taxonomy.md) 对错误进行分类和评级

**分析错误时**:
- 使用 [error-taxonomy.md](error-taxonomy.md) 中的决策树确定错误类型
- 查看常见错误模式库寻找类似案例

**制定预防策略时**:
- 参考 [best-practices.md](best-practices.md) 中的预防策略示例
- 查看 [error-taxonomy.md](error-taxonomy.md) 中各错误类型的预防方法

### 按文档类型

**规范类**:
- [error-taxonomy.md](error-taxonomy.md) - 错误分类标准

**指南类**:
- [best-practices.md](best-practices.md) - 编写指南

## 使用建议

### 首次使用

1. 阅读 [best-practices.md](best-practices.md) 的"核心原则"部分
2. 浏览 [error-taxonomy.md](error-taxonomy.md) 了解错误分类体系
3. 查看 `../examples/` 目录中的示例报告
4. 尝试编写第一份反思报告

### 日常使用

1. 遇到错误时,使用 [error-taxonomy.md](error-taxonomy.md) 进行分类
2. 编写报告时,参考 [best-practices.md](best-practices.md) 的章节指南
3. 定期回顾积累的报告,更新个人模式库

### 持续改进

1. 每周回顾本周的所有反思报告
2. 识别重复出现的错误模式
3. 更新预防策略和检查清单
4. 分享有价值的经验给团队

## 相关资源

### 内部资源
- `../SKILL.md` - 技能主文档
- `../assets/` - 报告模板
- `../examples/` - 示例报告
- `../scripts/` - 辅助脚本

### 外部资源
- [5 Whys Technique](https://en.wikipedia.org/wiki/Five_whys) - 根本原因分析方法
- [Postmortem Culture](https://sre.google/sre-book/postmortem-culture/) - Google SRE的事后分析文化
- [Learning from Incidents](https://www.learningfromincidents.io/) - 从事故中学习

## 维护说明

### 更新频率
- 错误分类体系: 每季度审查一次
- 最佳实践指南: 根据反馈持续更新
- 示例报告: 每月添加新示例

### 贡献指南
如果发现文档问题或有改进建议:
1. 在项目中创建Issue描述问题
2. 提交PR with改进建议
3. 在团队会议中讨论

---

**最后更新**: 2026-02-15
**维护者**: Claude Sonnet 4.5
