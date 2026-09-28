#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub Setup Wizard for Knowledge Steward
Interactive script to guide users through GitHub repository setup
"""

import os
import sys
import subprocess
from pathlib import Path
import yaml

# Fix Windows console encoding for Chinese characters
if sys.platform == 'win32':
    import codecs
    # Only wrap if not already wrapped and buffer exists
    if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, codecs.StreamWriter):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, codecs.StreamWriter):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

def print_header(text):
    """Print a formatted header"""
    print("\n" + "=" * 60)
    print(f"  {text}")
    print("=" * 60 + "\n")

def print_step(step_num, text):
    """Print a step number and description"""
    print(f"\n[步骤 {step_num}] {text}")
    print("-" * 60)

def check_gh_cli():
    """Check if GitHub CLI is installed"""
    try:
        result = subprocess.run(
            ['gh', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def check_git():
    """Check if git is installed"""
    try:
        result = subprocess.run(
            ['git', '--version'],
            capture_output=True,
            text=True,
            timeout=5
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False

def get_github_username():
    """Get GitHub username from user"""
    print("\n请输入您的 GitHub 用户名:")
    print("(Please enter your GitHub username)")
    username = input("> ").strip()
    return username

def choose_auth_method():
    """Let user choose authentication method"""
    print("\n请选择认证方式 (Choose authentication method):")
    print("1. HTTPS (推荐 - 使用 Git Credential Manager)")
    print("2. SSH (需要配置 SSH 密钥)")
    print()
    choice = input("请选择 (1 或 2): ").strip()
    return 'https' if choice == '1' else 'ssh'

def create_repo_manual_instructions(repo_name, is_private=True):
    """Provide manual instructions for creating a repository"""
    print(f"\n请手动创建 GitHub 仓库: {repo_name}")
    print("(Please manually create the GitHub repository)")
    print("\n步骤:")
    print(f"1. 访问: https://github.com/new")
    print(f"2. Repository name: {repo_name}")
    print(f"3. 设置为: {'Private (私有)' if is_private else 'Public (公开)'}")
    print("4. 不要勾选 'Add a README file'")
    print("5. 不要勾选 'Add .gitignore'")
    print("6. 点击 'Create repository'")
    print("\n完成后按 Enter 继续...")
    input()

def create_repo_with_gh(repo_name, is_private=True):
    """Create repository using gh CLI"""
    visibility = '--private' if is_private else '--public'
    try:
        result = subprocess.run(
            ['gh', 'repo', 'create', repo_name, visibility, '--confirm'],
            capture_output=True,
            text=True,
            timeout=30
        )
        return result.returncode == 0
    except Exception as e:
        print(f"创建仓库失败: {e}")
        return False

def test_git_auth(auth_method):
    """Test git authentication"""
    print("\n测试 Git 认证...")
    if auth_method == 'ssh':
        try:
            result = subprocess.run(
                ['ssh', '-T', 'git@github.com'],
                capture_output=True,
                text=True,
                timeout=10
            )
            # SSH test returns 1 even on success with message
            if 'successfully authenticated' in result.stderr.lower():
                print("✓ SSH 认证成功")
                return True
            else:
                print("✗ SSH 认证失败")
                print("请配置 SSH 密钥: https://docs.github.com/en/authentication/connecting-to-github-with-ssh")
                return False
        except Exception as e:
            print(f"✗ SSH 测试失败: {e}")
            return False
    else:
        print("✓ HTTPS 认证将在首次 push 时进行")
        return True

def generate_config(username, auth_method):
    """Generate config.yaml from template"""
    skill_path = Path(__file__).parent.parent
    config_example = skill_path / 'config.example.yaml'
    config_path = skill_path / 'config.yaml'

    # Load template
    with open(config_example, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)

    # Update with user's information
    if auth_method == 'ssh':
        config['repositories']['knowledge_base']['url'] = f"git@github.com:{username}/knowledge-base.git"
        config['repositories']['skill_code']['url'] = f"git@github.com:{username}/claude-skill-knowledge-steward.git"
    else:
        config['repositories']['knowledge_base']['url'] = f"https://github.com/{username}/knowledge-base.git"
        config['repositories']['skill_code']['url'] = f"https://github.com/{username}/claude-skill-knowledge-steward.git"

    # Save config
    with open(config_path, 'w', encoding='utf-8') as f:
        yaml.dump(config, f, default_flow_style=False, allow_unicode=True)

    print(f"\n✓ 配置文件已创建: {config_path}")
    return config_path

def main():
    """Main setup wizard"""
    print_header("Knowledge Steward - GitHub 设置向导")

    # Step 1: Check prerequisites
    print_step(1, "检查系统环境")

    if not check_git():
        print("✗ 未检测到 Git")
        print("请安装 Git for Windows: https://git-scm.com/download/win")
        return 1

    print("✓ Git 已安装")

    has_gh_cli = check_gh_cli()
    if has_gh_cli:
        print("✓ GitHub CLI 已安装")
    else:
        print("ℹ GitHub CLI 未安装 (将使用手动方式创建仓库)")

    # Step 2: Get GitHub username
    print_step(2, "获取 GitHub 信息")
    username = get_github_username()

    if not username:
        print("✗ 用户名不能为空")
        return 1

    print(f"✓ GitHub 用户名: {username}")

    # Step 3: Choose authentication method
    print_step(3, "选择认证方式")
    auth_method = choose_auth_method()
    print(f"✓ 认证方式: {auth_method.upper()}")

    # Test authentication
    if not test_git_auth(auth_method):
        print("\n⚠ 认证测试失败，但可以继续设置")
        print("首次 push 时可能需要输入凭据")

    # Step 4: Create repositories
    print_step(4, "创建 GitHub 仓库")

    repos = [
        ('knowledge-base', '存储知识笔记'),
        ('claude-skill-knowledge-steward', '存储技能代码')
    ]

    for repo_name, description in repos:
        print(f"\n创建仓库: {repo_name} ({description})")

        if has_gh_cli:
            print("尝试使用 gh CLI 创建...")
            if create_repo_with_gh(repo_name, is_private=True):
                print(f"✓ 仓库 {repo_name} 创建成功")
            else:
                print(f"✗ 自动创建失败，请手动创建")
                create_repo_manual_instructions(repo_name)
        else:
            create_repo_manual_instructions(repo_name)

    # Step 5: Generate configuration
    print_step(5, "生成配置文件")
    config_path = generate_config(username, auth_method)

    # Step 6: Next steps
    print_step(6, "下一步")
    print("\n设置完成！接下来请运行:")
    print("\n  python scripts/init_git_repos.py")
    print("\n这将初始化 Git 仓库并进行首次提交。")

    print("\n" + "=" * 60)
    print("  设置向导完成！")
    print("=" * 60 + "\n")

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