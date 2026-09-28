#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Git Sync Module for Knowledge Steward
Handles automatic git operations for syncing notes to GitHub
"""

import os
import sys
import subprocess
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Tuple
import yaml

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    # Only wrap if not already wrapped and buffer exists
    if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, codecs.StreamWriter):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, codecs.StreamWriter):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Configure logging
def setup_logging(config: Dict) -> logging.Logger:
    """Setup logging based on configuration"""
    logger = logging.getLogger('git_sync')
    logger.setLevel(getattr(logging, config.get('logging', {}).get('level', 'INFO')))

    # Create logs directory if it doesn't exist
    skill_path = Path(__file__).parent.parent
    log_dir = skill_path / 'logs'
    log_dir.mkdir(exist_ok=True)

    # Extract just the filename from the config path
    log_file_config = config.get('logging', {}).get('file', 'logs/git_sync.log')
    log_filename = Path(log_file_config).name  # Get just the filename, not the path
    log_file = log_dir / log_filename

    # File handler
    handler = logging.FileHandler(log_file, encoding='utf-8')
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    return logger

def load_config(config_path: Optional[str] = None) -> Dict:
    """Load configuration from YAML file"""
    if config_path is None:
        # Default config path
        skill_path = Path(__file__).parent.parent
        config_path = skill_path / 'config.yaml'

    config_path = Path(config_path)

    if not config_path.exists():
        # Return default config if file doesn't exist
        return {
            'git': {'enabled': False},
            'logging': {'enabled': True, 'level': 'INFO', 'file': 'logs/git_sync.log'}
        }

    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        return config
    except Exception as e:
        print(f"Error loading config: {e}")
        return {'git': {'enabled': False}}

def is_git_available() -> bool:
    """Check if git is installed and available"""
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

def run_git_command(command: list, cwd: str, logger: Optional[logging.Logger] = None) -> Tuple[bool, str, str]:
    """
    Run a git command and return success status, stdout, stderr

    Args:
        command: Git command as list (e.g., ['git', 'status'])
        cwd: Working directory
        logger: Optional logger for logging operations

    Returns:
        Tuple of (success, stdout, stderr)
    """
    try:
        if logger:
            logger.debug(f"Running command: {' '.join(command)} in {cwd}")

        result = subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding='utf-8',
            timeout=30
        )

        success = result.returncode == 0

        if logger:
            if success:
                logger.debug(f"Command succeeded: {result.stdout[:200]}")
            else:
                logger.warning(f"Command failed: {result.stderr[:200]}")

        return success, result.stdout, result.stderr

    except subprocess.TimeoutExpired:
        error_msg = "Git command timed out"
        if logger:
            logger.error(error_msg)
        return False, "", error_msg

    except Exception as e:
        error_msg = f"Error running git command: {str(e)}"
        if logger:
            logger.error(error_msg)
        return False, "", error_msg

def is_git_repo(path: str) -> bool:
    """Check if directory is a git repository"""
    git_dir = Path(path) / '.git'
    return git_dir.exists()

def has_changes(path: str, logger: Optional[logging.Logger] = None) -> bool:
    """Check if there are uncommitted changes"""
    success, stdout, stderr = run_git_command(['git', 'status', '--porcelain'], path, logger)
    return success and len(stdout.strip()) > 0

def init_repo(path: str, remote_url: str, logger: Optional[logging.Logger] = None) -> Dict:
    """
    Initialize a git repository if not already initialized

    Args:
        path: Directory path
        remote_url: GitHub repository URL
        logger: Optional logger

    Returns:
        Dict with 'success' and 'message' keys
    """
    path = Path(path)

    if not path.exists():
        return {'success': False, 'message': f"Directory does not exist: {path}"}

    # Check if already a git repo
    if is_git_repo(str(path)):
        if logger:
            logger.info(f"Directory is already a git repository: {path}")
        return {'success': True, 'message': 'Already a git repository'}

    # Initialize git
    success, stdout, stderr = run_git_command(['git', 'init'], str(path), logger)
    if not success:
        return {'success': False, 'message': f"Failed to initialize git: {stderr}"}

    # Add remote
    success, stdout, stderr = run_git_command(
        ['git', 'remote', 'add', 'origin', remote_url],
        str(path),
        logger
    )
    if not success:
        return {'success': False, 'message': f"Failed to add remote: {stderr}"}

    if logger:
        logger.info(f"Initialized git repository at {path} with remote {remote_url}")

    return {'success': True, 'message': 'Repository initialized successfully'}

def sync_changes(
    path: str,
    commit_message: str,
    config: Optional[Dict] = None,
    auto_pull: bool = True,
    logger: Optional[logging.Logger] = None
) -> Dict:
    """
    Main sync function: pull, commit, and push changes

    Args:
        path: Directory path to sync
        commit_message: Commit message
        config: Configuration dict
        auto_pull: Whether to pull before push
        logger: Optional logger

    Returns:
        Dict with 'success', 'message', and optional 'error' keys
    """
    path = Path(path)

    # Check if git is available
    if not is_git_available():
        error_msg = "Git is not installed or not available in PATH"
        if logger:
            logger.error(error_msg)
        return {'success': False, 'message': error_msg, 'error': 'git_not_available'}

    # Check if it's a git repo
    if not is_git_repo(str(path)):
        error_msg = f"Not a git repository: {path}"
        if logger:
            logger.error(error_msg)
        return {'success': False, 'message': error_msg, 'error': 'not_git_repo'}

    # Pull if auto_pull enabled
    if auto_pull:
        if logger:
            logger.info("Pulling latest changes from remote")

        # Fetch first
        success, stdout, stderr = run_git_command(['git', 'fetch', 'origin'], str(path), logger)
        if not success:
            if logger:
                logger.warning(f"Failed to fetch: {stderr}")

        # Check if remote has changes
        success, stdout, stderr = run_git_command(
            ['git', 'rev-list', 'HEAD...origin/main', '--count'],
            str(path),
            logger
        )

        if success and stdout.strip() != '0':
            # Remote has changes, pull them
            success, stdout, stderr = run_git_command(
                ['git', 'pull', '--rebase', 'origin', 'main'],
                str(path),
                logger
            )
            if not success:
                if logger:
                    logger.warning(f"Failed to pull: {stderr}")

    # Check if there are changes to commit
    if not has_changes(str(path), logger):
        if logger:
            logger.info("No changes to commit")
        return {'success': True, 'message': 'No changes to commit'}

    # Stage all changes
    success, stdout, stderr = run_git_command(['git', 'add', '.'], str(path), logger)
    if not success:
        error_msg = f"Failed to stage changes: {stderr}"
        if logger:
            logger.error(error_msg)
        return {'success': False, 'message': error_msg, 'error': 'stage_failed'}

    # Commit
    success, stdout, stderr = run_git_command(
        ['git', 'commit', '-m', commit_message],
        str(path),
        logger
    )
    if not success:
        error_msg = f"Failed to commit: {stderr}"
        if logger:
            logger.error(error_msg)
        return {'success': False, 'message': error_msg, 'error': 'commit_failed'}

    # Push
    max_retries = config.get('sync', {}).get('max_retries', 3) if config else 3
    retry_delay = config.get('sync', {}).get('retry_delay_seconds', 5) if config else 5

    for attempt in range(max_retries):
        success, stdout, stderr = run_git_command(
            ['git', 'push', 'origin', 'main'],
            str(path),
            logger
        )

        if success:
            if logger:
                logger.info(f"Successfully pushed changes: {commit_message}")
            return {'success': True, 'message': 'Changes synced successfully'}

        if attempt < max_retries - 1:
            if logger:
                logger.warning(f"Push failed (attempt {attempt + 1}/{max_retries}): {stderr}")
            import time
            time.sleep(retry_delay)
        else:
            error_msg = f"Failed to push after {max_retries} attempts: {stderr}"
            if logger:
                logger.error(error_msg)
            return {'success': False, 'message': error_msg, 'error': 'push_failed'}

    return {'success': False, 'message': 'Unknown error', 'error': 'unknown'}

def handle_error(error: str, logger: Optional[logging.Logger] = None) -> str:
    """
    Provide user-friendly error messages

    Args:
        error: Error code
        logger: Optional logger

    Returns:
        User-friendly error message
    """
    error_messages = {
        'git_not_available': '错误：未安装 Git 或 Git 不在 PATH 中。请安装 Git for Windows。',
        'not_git_repo': '错误：目录不是 Git 仓库。请先运行 init_git_repos.py 初始化。',
        'stage_failed': '错误：无法暂存更改。请检查文件权限。',
        'commit_failed': '错误：无法提交更改。请检查 Git 配置。',
        'push_failed': '错误：无法推送到 GitHub。请检查网络连接和认证。',
        'network_error': '错误：网络连接失败。请检查网络设置。',
        'auth_error': '错误：认证失败。请检查 GitHub 凭据。',
    }

    message = error_messages.get(error, f'未知错误：{error}')

    if logger:
        logger.error(message)

    return message

# CLI interface for testing
if __name__ == '__main__':
    import argparse

    parser = argparse.ArgumentParser(description='Git Sync Module')
    parser.add_argument('--test-config', action='store_true', help='Test configuration loading')
    parser.add_argument('--check-git', action='store_true', help='Check if git is available')
    parser.add_argument('--sync', type=str, help='Sync directory')
    parser.add_argument('--message', type=str, default='Test commit', help='Commit message')

    args = parser.parse_args()

    if args.test_config:
        config = load_config()
        print("Configuration loaded successfully:")
        print(yaml.dump(config, default_flow_style=False))

    elif args.check_git:
        if is_git_available():
            print("✓ Git is available")
        else:
            print("✗ Git is not available")

    elif args.sync:
        config = load_config()
        logger = setup_logging(config)
        result = sync_changes(args.sync, args.message, config, logger=logger)
        print(f"Sync result: {result}")
