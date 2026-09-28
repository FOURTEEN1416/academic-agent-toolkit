#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Initialize Git Repositories for Knowledge Steward
Sets up git in both the knowledge base and skill directories
"""

import os
import sys
import subprocess
from pathlib import Path
import yaml

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    # Only wrap if not already wrapped and buffer exists
    if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, codecs.StreamWriter):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, codecs.StreamWriter):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import git_sync module
sys.path.insert(0, str(Path(__file__).parent))
import git_sync

def print_header(text):
    """Print formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(step_num, text):
    """Print step"""
    print(f"\n[步骤 {step_num}] {text}")
    print("-" * 60)

def create_gitignore_knowledge_base(path):
    """Create .gitignore for knowledge base"""
    gitignore_content = """# OS files
.DS_Store
Thumbs.db
desktop.ini

# Temporary files
*.tmp
*.temp
~$*

# Obsidian
.obsidian/workspace*
.obsidian/cache

# Logs
*.log
"""
    gitignore_path = Path(path) / '.gitignore'
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    print(f"✓ 创建 .gitignore: {gitignore_path}")

def create_gitignore_skill(path):
    """Create .gitignore for skill directory"""
    gitignore_content = """# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python

# Logs
logs/
*.log

# Configuration (keep example, ignore actual)
config.yaml

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS files
.DS_Store
Thumbs.db
"""
    gitignore_path = Path(path) / '.gitignore'
    with open(gitignore_path, 'w', encoding='utf-8') as f:
        f.write(gitignore_content)
    print(f"✓ 创建 .gitignore: {gitignore_path}")

def create_readme_knowledge_base(path):
    """Create README for knowledge base"""
    readme_content = """# Claude Knowledge Base

这是我的 AI 辅助学习知识库，由 Claude Knowledge Steward 自动管理。

## 目录结构

- `提示词/` - 有效的提示词和对话技巧
- `模式/` - 设计模式和架构模式
- `问题修复/` - 问题解决方案和调试经验
- `想法/` - 创意和思考记录
- `效率优化/` - 效率提升技巧和工具

## 使用方式

所有笔记由 Claude Code 的 knowledge-steward 技能自动生成和同步。

每条笔记包含:
- 背景信息 (Context)
- 核心内容 (Content)
- 苏格拉底式分析 (Analysis)

## 同步

本仓库通过 Git 自动同步，每次保存笔记时自动提交和推送。
"""
    readme_path = Path(path) / 'README.md'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✓ 创建 README.md: {readme_path}")

def create_readme_skill(path):
    """Create README for skill directory"""
    readme_content = """# Knowledge Steward Skill

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
"""
    readme_path = Path(path) / 'README.md'
    with open(readme_path, 'w', encoding='utf-8') as f:
        f.write(readme_content)
    print(f"✓ 创建 README.md: {readme_path}")

def init_repository(path, remote_url, repo_type):
    """Initialize a git repository"""
    path = Path(path)

    print(f"\n初始化 {repo_type} 仓库...")
    print(f"路径: {path}")
    print(f"远程: {remote_url}")

    # Check if directory exists
    if not path.exists():
        print(f"✗ 目录不存在: {path}")
        return False

    # Create .gitignore
    if repo_type == "knowledge-base":
        create_gitignore_knowledge_base(path)
        create_readme_knowledge_base(path)
    else:
        create_gitignore_skill(path)
        create_readme_skill(path)

    # Initialize git if not already
    if not git_sync.is_git_repo(str(path)):
        success, stdout, stderr = git_sync.run_git_command(['git', 'init'], str(path))
        if not success:
            print(f"✗ Git 初始化失败: {stderr}")
            return False
        print("✓ Git 仓库已初始化")
    else:
        print("ℹ 已经是 Git 仓库")

    # Check if remote exists
    success, stdout, stderr = git_sync.run_git_command(['git', 'remote', 'get-url', 'origin'], str(path))

    if success:
        current_remote = stdout.strip()
        if current_remote != remote_url:
            print(f"ℹ 更新远程 URL: {current_remote} -> {remote_url}")
            git_sync.run_git_command(['git', 'remote', 'set-url', 'origin', remote_url], str(path))
        else:
            print(f"✓ 远程已配置: {remote_url}")
    else:
        # Add remote
        success, stdout, stderr = git_sync.run_git_command(['git', 'remote', 'add', 'origin', remote_url], str(path))
        if not success:
            print(f"✗ 添加远程失败: {stderr}")
            return False
        print(f"✓ 远程已添加: {remote_url}")

    # Check if there are files to commit
    success, stdout, stderr = git_sync.run_git_command(['git', 'status', '--porcelain'], str(path))
    if not success or not stdout.strip():
        print("ℹ 没有文件需要提交")
        return True

    # Stage all files
    success, stdout, stderr = git_sync.run_git_command(['git', 'add', '.'], str(path))
    if not success:
        print(f"✗ 暂存文件失败: {stderr}")
        return False
    print("✓ 文件已暂存")

    # Create initial commit
    commit_message = f"Initial commit: {repo_type}"
    success, stdout, stderr = git_sync.run_git_command(['git', 'commit', '-m', commit_message], str(path))
    if not success:
        print(f"✗ 提交失败: {stderr}")
        return False
    print("✓ 初始提交完成")

    # Check if main branch exists on remote
    success, stdout, stderr = git_sync.run_git_command(['git', 'ls-remote', '--heads', 'origin', 'main'], str(path))

    # Rename branch to main if needed
    success, stdout, stderr = git_sync.run_git_command(['git', 'branch', '-M', 'main'], str(path))

    # Push to remote
    print("\n推送到 GitHub...")
    success, stdout, stderr = git_sync.run_git_command(['git', 'push', '-u', 'origin', 'main'], str(path))

    if not success:
        print(f"✗ 推送失败: {stderr}")
        print("\n可能的原因:")
        print("1. 网络连接问题")
        print("2. 认证失败 - 请检查 GitHub 凭据")
        print("3. 仓库不存在 - 请先在 GitHub 上创建仓库")
        print("\n您可以稍后手动推送:")
        print(f"  cd \"{path}\"")
        print("  git push -u origin main")
        return False

    print("✓ 推送成功")
    return True

def main():
    """Main initialization function"""
    print_header("Knowledge Steward - Git 仓库初始化")

    # Load config
    skill_path = Path(__file__).parent.parent
    config_path = skill_path / 'config.yaml'

    if not config_path.exists():
        print("✗ 配置文件不存在")
        print(f"请先运行: python scripts/setup_github.py")
        return 1

    print(f"✓ 加载配置: {config_path}")
    config = git_sync.load_config(str(config_path))

    # Initialize knowledge base repository
    print_step(1, "初始化知识库仓库")
    kb_path = Path(config['paths']['vault_path']) / 'Claude_Insights'
    kb_url = config['repositories']['knowledge_base']['url']

    if not init_repository(kb_path, kb_url, "knowledge-base"):
        print("\n⚠ 知识库仓库初始化未完全成功")

    # Initialize skill repository
    print_step(2, "初始化技能代码仓库")
    skill_path = Path(config['paths']['skill_path'])
    skill_url = config['repositories']['skill_code']['url']

    if not init_repository(skill_path, skill_url, "skill-code"):
        print("\n⚠ 技能代码仓库初始化未完全成功")

    # Summary
    print_header("初始化完成")
    print("✓ Git 仓库已设置")
    print("✓ .gitignore 文件已创建")
    print("✓ README 文件已创建")
    print("\n下一步:")
    print("1. 测试保存笔记:")
    print("   python scripts/save_to_obsidian.py --title \"测试\" --type \"想法\" --content \"测试内容\"")
    print("\n2. 检查 GitHub 仓库确认文件已上传")
    print("\n3. 开始使用 Knowledge Steward 技能！")

    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\n用户取消操作")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)