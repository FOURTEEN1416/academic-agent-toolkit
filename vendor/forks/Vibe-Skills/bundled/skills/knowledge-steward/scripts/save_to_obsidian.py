#!/usr/bin/env python3
"""
Knowledge Steward - Save to Obsidian Script

This script saves AI work insights, prompts, bug fixes, and ideas to an Obsidian vault
with structured metadata and auto-generated analysis.

Usage:
    python save_to_obsidian.py --title "Title" --type "提示词" --content "Content" [options]

Examples:
    python save_to_obsidian.py --title "使用苏格拉底式提问" --type "提示词" --content "..."
    python save_to_obsidian.py --title "npm依赖冲突" --type "问题修复" --content "..." --tags "npm,依赖"
"""

import os
import sys
import argparse
import datetime
import json
import re
from collections import Counter
from pathlib import Path

# Fix Windows console encoding
if sys.platform == 'win32':
    import codecs
    # Only wrap if not already wrapped and buffer exists
    if hasattr(sys.stdout, 'buffer') and not isinstance(sys.stdout, codecs.StreamWriter):
        sys.stdout = codecs.getwriter('utf-8')(sys.stdout.buffer, 'strict')
    if hasattr(sys.stderr, 'buffer') and not isinstance(sys.stderr, codecs.StreamWriter):
        sys.stderr = codecs.getwriter('utf-8')(sys.stderr.buffer, 'strict')

# Import git_sync module
try:
    import git_sync
    GIT_SYNC_AVAILABLE = True
except ImportError:
    GIT_SYNC_AVAILABLE = False

# Configuration
VAULT_PATH = r"D:\Documents\ai技能外置大脑"
INSIGHTS_DIR = "Claude_Insights"

# Load config if available
def load_vault_config():
    """Load vault path from config if available"""
    if GIT_SYNC_AVAILABLE:
        try:
            config = git_sync.load_config()
            if config and 'paths' in config and 'vault_path' in config['paths']:
                return config['paths']['vault_path'], config
        except Exception:
            pass
    return VAULT_PATH, None

# Try to load config
VAULT_PATH, CONFIG = load_vault_config()

# Category mappings
CATEGORIES = {
    "提示词": "提示词",
    "prompt": "提示词",
    "prompts": "提示词",
    "模式": "模式",
    "pattern": "模式",
    "patterns": "模式",
    "问题修复": "问题修复",
    "bugfix": "问题修复",
    "bugfixes": "问题修复",
    "bug": "问题修复",
    "想法": "想法",
    "idea": "想法",
    "ideas": "想法",
    "效率优化": "效率优化",
    "efficiency": "效率优化",
    "optimization": "效率优化"
}

# Analysis templates
ANALYSIS_TEMPLATES = {
    "提示词": "为什么这个提示词有效/无效？背后的原理是什么？它利用了什么样的对话机制或认知模式？",
    "模式": "这个模式解决了什么问题？它的核心思想是什么？在什么场景下最适用？",
    "问题修复": "这个问题的根本原因是什么？为什么这个解决方案有效？如何避免类似问题再次发生？",
    "想法": "这个想法的核心价值是什么？它解决了什么痛点？如何验证其可行性？需要什么前置条件？",
    "效率优化": "这个优化提升了什么？为什么能提高效率？它的适用范围是什么？有什么潜在的权衡？"
}


def sanitize_filename(title):
    """
    Sanitize filename by removing special characters while preserving Chinese characters.
    """
    # Remove or replace special characters
    # Keep: Chinese characters, alphanumeric, spaces, hyphens, underscores
    sanitized = re.sub(r'[<>:"/\\|?*]', '', title)
    sanitized = re.sub(r'[\s]+', '_', sanitized.strip())

    # Limit length to avoid filesystem issues
    if len(sanitized) > 100:
        sanitized = sanitized[:100]

    return sanitized


def extract_keywords(text, num_keywords=5):
    """
    Extract keywords from text using simple frequency analysis.
    """
    # Remove common Chinese stop words
    stop_words = {
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都', '一', '一个',
        '上', '也', '很', '到', '说', '要', '去', '你', '会', '着', '没有', '看', '好',
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with',
        'is', 'are', 'was', 'were', 'be', 'been', 'being', 'this', 'that', 'these', 'those'
    }

    # Extract words (both Chinese and English)
    # Chinese: \u4e00-\u9fff
    # English: a-zA-Z
    words = re.findall(r'[\u4e00-\u9fff]+|[a-zA-Z]+', text.lower())

    # Filter out stop words and short words
    filtered_words = [w for w in words if w not in stop_words and len(w) > 1]

    # Count frequency
    word_counts = Counter(filtered_words)

    # Get top keywords
    keywords = [word for word, count in word_counts.most_common(num_keywords)]

    return keywords


def generate_analysis(content, note_type, context=""):
    """
    Generate Socratic analysis based on content and type.
    """
    template = ANALYSIS_TEMPLATES.get(note_type, "这个内容的核心要点是什么？它为什么重要？")

    # Simple analysis generation
    # In a real implementation, this could use an LLM API
    analysis = f"{template}\n\n"
    analysis += "**初步思考**：\n"
    analysis += f"- 这个{note_type}涉及的核心概念和方法\n"
    analysis += "- 它在实际工作中的应用场景\n"
    analysis += "- 可能的改进方向和延伸思考\n\n"
    analysis += "*注：此分析由系统自动生成，建议后续补充个人见解*"

    return analysis


def check_duplicate(vault_path, category, filename):
    """
    Check if a file with the same name already exists.
    """
    category_path = os.path.join(vault_path, INSIGHTS_DIR, category)
    file_path = os.path.join(category_path, filename)

    return os.path.exists(file_path)


def save_note(title, note_type, content, context="", user_tags=None, auto_analysis=True, no_sync=False):
    """
    Save a note to the Obsidian vault.

    Args:
        title: Note title
        note_type: Type of note (提示词, 模式, 问题修复, 想法, 效率优化)
        content: Main content
        context: Optional context about what was being done
        user_tags: Optional list of user-provided tags
        auto_analysis: Whether to auto-generate analysis
        no_sync: Skip git sync even if enabled

    Returns:
        dict: Result with success status and file path
    """
    try:
        # Normalize type
        note_type_normalized = CATEGORIES.get(note_type.lower(), note_type)

        # Generate timestamp
        now = datetime.datetime.now()
        timestamp = now.strftime("%Y-%m-%d %H:%M:%S")
        date_str = now.strftime("%Y-%m-%d")

        # Sanitize title for filename
        safe_title = sanitize_filename(title)
        filename = f"{date_str}_{safe_title}.md"

        # Create category directory
        category_path = os.path.join(VAULT_PATH, INSIGHTS_DIR, note_type_normalized)
        os.makedirs(category_path, exist_ok=True)

        # Check for duplicates
        if check_duplicate(VAULT_PATH, note_type_normalized, filename):
            return {
                "success": False,
                "error": "duplicate",
                "message": f"文件已存在：{filename}",
                "file_path": os.path.join(category_path, filename)
            }

        # Generate tags
        auto_tags = extract_keywords(content + " " + title, num_keywords=5)
        if user_tags:
            all_tags = list(set(auto_tags + user_tags))
        else:
            all_tags = auto_tags

        # Add type tag
        all_tags.insert(0, note_type_normalized)

        # Generate analysis
        if auto_analysis:
            analysis = generate_analysis(content, note_type_normalized, context)
        else:
            analysis = "*待补充分析*"

        # Build markdown content
        md_content = f"""---
created: {timestamp}
type: {note_type_normalized}
tags: {json.dumps(all_tags, ensure_ascii=False)}
status: inbox
source: claude-code
---

# {title}

## 背景 (Context)

{context if context else "在Claude Code会话中生成"}

## 内容 (Content)

{content}

## 分析 (Analysis)

{analysis}
"""

        # Write file
        file_path = os.path.join(category_path, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)

        result = {
            "success": True,
            "file_path": file_path,
            "category": note_type_normalized,
            "tags": all_tags,
            "message": f"✓ 已保存到 Obsidian\n文件：{file_path}\n类型：{note_type_normalized}\n标签：{', '.join(['#' + tag for tag in all_tags])}"
        }

        # Git sync if enabled
        if not no_sync and GIT_SYNC_AVAILABLE and CONFIG and CONFIG.get('git', {}).get('enabled') and CONFIG.get('git', {}).get('auto_sync'):
            try:
                logger = git_sync.setup_logging(CONFIG)
                vault_insights_path = os.path.join(VAULT_PATH, INSIGHTS_DIR)

                # Generate commit message
                commit_message = f"Add: {note_type_normalized} - {title}"

                # Sync changes
                auto_pull = CONFIG.get('repositories', {}).get('knowledge_base', {}).get('auto_pull', True)
                sync_result = git_sync.sync_changes(
                    vault_insights_path,
                    commit_message,
                    config=CONFIG,
                    auto_pull=auto_pull,
                    logger=logger
                )

                if sync_result['success']:
                    result['message'] += "\n✓ 已同步到 GitHub"
                    result['synced'] = True
                else:
                    result['message'] += f"\n⚠ 同步失败: {sync_result.get('message', 'Unknown error')}"
                    result['synced'] = False
                    result['sync_error'] = sync_result.get('error')

            except Exception as e:
                result['message'] += f"\n⚠ 同步失败: {str(e)}"
                result['synced'] = False

        return result

    except Exception as e:
        return {
            "success": False,
            "error": "exception",
            "message": f"保存失败：{str(e)}"
        }


def main():
    parser = argparse.ArgumentParser(
        description="Save AI work insights to Obsidian vault",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python save_to_obsidian.py --title "使用苏格拉底式提问" --type "提示词" --content "请用苏格拉底式提问引导我..."
  python save_to_obsidian.py --title "npm依赖冲突" --type "问题修复" --content "..." --tags "npm,依赖"
  python save_to_obsidian.py --title "Event Sourcing" --type "想法" --content "..." --context "讨论架构设计时"
        """
    )

    parser.add_argument("--title", required=True, help="Note title")
    parser.add_argument("--type", required=True,
                       choices=list(set(CATEGORIES.values())),
                       help="Note type")
    parser.add_argument("--content", required=True, help="Main content")
    parser.add_argument("--context", default="", help="Optional context")
    parser.add_argument("--tags", help="Comma-separated user tags")
    parser.add_argument("--no-analysis", action="store_true",
                       help="Skip auto-generating analysis")
    parser.add_argument("--no-sync", action="store_true",
                       help="Skip git sync to GitHub")
    parser.add_argument("--json", action="store_true",
                       help="Output result as JSON")

    args = parser.parse_args()

    # Parse tags
    user_tags = []
    if args.tags:
        user_tags = [tag.strip() for tag in args.tags.split(",")]

    # Save note
    result = save_note(
        title=args.title,
        note_type=args.type,
        content=args.content,
        context=args.context,
        user_tags=user_tags,
        auto_analysis=not args.no_analysis,
        no_sync=args.no_sync
    )

    # Output result
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        if result["success"]:
            print(result["message"])
        else:
            print(f"错误：{result['message']}", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
