# Knowledge Steward Skill

Claude Code 技能：自动保存和管理知识笔记到 Obsidian 和 GitHub。

## 功能

- 自动保存对话中的有价值内容
- 分类管理（提示词、模式、问题修复、想法、效率优化）
- 自动生成标签和苏格拉底式分析
- 自动同步到 GitHub

## 使用

在 Claude Code 中说：
- "保存这个提示词"
- "记录这个想法"
- "Save this insight"

## 配置

复制 `config.example.yaml` 到 `config.yaml` 并修改配置。

## 设置

1. 运行 `python scripts/setup_github.py` 创建 GitHub 仓库
2. 运行 `python scripts/init_git_repos.py` 初始化 Git
3. 开始使用！

## 文档

详见 `references/index.md` 和 `assets/setup-guide.md`。
