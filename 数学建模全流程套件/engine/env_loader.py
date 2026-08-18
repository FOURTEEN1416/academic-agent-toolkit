#!/usr/bin/env python3
"""env_loader.py — 从项目 .env 文件加载 API 配置
供 quality_gates.py 和各工具脚本使用，统一读取配置
"""
from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
ENV_FILE = PROJECT_ROOT / ".env"


def load_env(path: Path | None = None) -> dict[str, str]:
    """加载 .env 文件内容（不覆盖已存在的环境变量）"""
    config = {}
    env_file = path or ENV_FILE
    if not env_file.exists():
        return config
    with open(env_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                config[key] = value
    return config


def apply_env(path: Path | None = None):
    """把 .env 的值写入 os.environ（不覆盖已有环境变量）"""
    for key, value in load_env(path).items():
        if key not in os.environ and value:
            os.environ[key] = value


def get(key: str, default: str = "", path: Path | None = None) -> str:
    """获取配置值（优先环境变量，其次 .env 文件）"""
    val = os.environ.get(key)
    if val:
        return val
    return load_env(path).get(key, default)


if __name__ == "__main__":
    apply_env()
    # 只输出配置状态，不输出任何密钥片段。
    for k in ["EDITOR_AI_API_KEY", "OPENAI_API_KEY", "GPT_IMAGE_API_KEY",
              "SENSENOVA_API_KEY", "AGNES_API_KEY"]:
        v = os.environ.get(k, "")
        print(f"{k}: {'已配置' if v and not v.startswith('<') else '未配置'}")
