#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sync Skill Code to GitHub
Manual script to sync knowledge-steward skill code changes
"""

import os
import sys
from pathlib import Path
from datetime import datetime

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

def get_changed_files(path):
    """Get list of changed files"""
    success, stdout, stderr = git_sync.run_git_command(['git', 'status', '--porcelain'], path)
    if not success:
        return []

    files = []
    for line in stdout.strip().split('\n'):
        if line:
            # Format: "M  file.py" or "A  file.py"
            parts = line.strip().split(maxsplit=1)
            if len(parts) == 2:
                files.append(parts[1])
    return files

def generate_commit_message(files):
    """Generate commit message based on changed files"""
    if not files:
        return "Update skill code"

    # Categorize changes
    categories = {
        'scripts': [],
        'config': [],
        'docs': [],
        'assets': [],
        'other': []
    }

    for file in files:
        if file.startswith('scripts/'):
            categories['scripts'].append(file)
        elif file.startswith('config') or file.endswith('.yaml'):
            categories['config'].append(file)
        elif file.endswith('.md'):
            categories['docs'].append(file)
        elif file.startswith('assets/'):
            categories['assets'].append(file)
        else:
            categories['other'].append(file)

    # Build message
    parts = []
    if categories['scripts']:
        parts.append(f"scripts ({len(categories['scripts'])} files)")
    if categories['config']:
        parts.append("config")
    if categories['docs']:
        parts.append("docs")
    if categories['assets']:
        parts.append("assets")
    if categories['other']:
        parts.append(f"other ({len(categories['other'])} files)")

    if parts:
        return f"Update: {', '.join(parts)}"
    else:
        return "Update skill code"

def main():
    """Main sync function"""
    print("\n" + "=" * 60)
    print("  Knowledge Steward - 同步技能代码")
    print("=" * 60 + "\n")

    # Load config
    skill_path = Path(__file__).parent.parent
    config = git_sync.load_config()

    if not config.get('git', {}).get('enabled'):
        print("✗ Git 同步未启用")
        print("请在 config.yaml 中启用 git.enabled")
        return 1

    # Setup logging
    logger = git_sync.setup_logging(config)

    # Get skill path from config
    skill_path = Path(config['paths']['skill_path'])

    print(f"技能路径: {skill_path}")

    # Check if it's a git repo
    if not git_sync.is_git_repo(str(skill_path)):
        print("✗ 不是 Git 仓库")
        print("请先运行: python scripts/init_git_repos.py")
        return 1

    # Check for changes
    changed_files = get_changed_files(str(skill_path))

    if not changed_files:
        print("✓ 没有更改需要同步")
        return 0

    print(f"\n发现 {len(changed_files)} 个更改的文件:")
    for file in changed_files[:10]:  # Show first 10
        print(f"  - {file}")
    if len(changed_files) > 10:
        print(f"  ... 还有 {len(changed_files) - 10} 个文件")

    # Generate commit message
    commit_message = generate_commit_message(changed_files)
    print(f"\n提交信息: {commit_message}")

    # Confirm
    print("\n是否继续同步? (y/n): ", end='')
    response = input().strip().lower()

    if response != 'y':
        print("取消同步")
        return 0

    # Sync changes
    print("\n同步中...")
    auto_pull = config['repositories']['skill_code'].get('auto_pull', False)

    result = git_sync.sync_changes(
        str(skill_path),
        commit_message,
        config=config,
        auto_pull=auto_pull,
        logger=logger
    )

    if result['success']:
        print("\n✓ 同步成功！")
        print(f"提交信息: {commit_message}")
        return 0
    else:
        print(f"\n✗ 同步失败: {result['message']}")
        if 'error' in result:
            error_msg = git_sync.handle_error(result['error'], logger)
            print(error_msg)
        return 1

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