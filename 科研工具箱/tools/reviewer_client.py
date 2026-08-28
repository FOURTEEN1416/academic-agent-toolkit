#!/usr/bin/env python3
"""reviewer_client.py — 调用外部 LLM 进行评审（替代 Codex MCP）

环境变量:
    OPENAI_API_KEY      — API Key（必填）
    OPENAI_BASE_URL     — Base URL，如 https://api.openai.com/v1（必填）
    REVIEWER_MODEL_ID   — 模型名，如 gpt-4o（可选，默认 gpt-4o）

用法:
    # 单次评审
    python reviewer_client.py --prompt "请评审这份论文..."

    # 从文件读取 prompt
    python reviewer_client.py --prompt-file prompt.txt

    # 从 stdin 读取
    echo "请评审..." | python reviewer_client.py

    # 多轮对话（自动保存/恢复上下文）
    python reviewer_client.py --prompt "第一轮评审..." --thread-file review_thread.json
    python reviewer_client.py --prompt "根据修改重新评审..." --thread-file review_thread.json

    # 添加 system prompt
    python reviewer_client.py --system "你是一个资深ML审稿人" --prompt "..."
"""
import argparse
import http.client
import json
import os
import ssl
import sys
from pathlib import Path
from urllib.parse import urlparse


def load_project_env(path: Path | None = None) -> None:
    """Load project-local provider settings without overriding process values."""
    project_root = Path(__file__).resolve().parent.parent
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    try:
        from engine.env_loader import apply_env
        apply_env(path)
    except ImportError:
        return


def call_api(base_url: str, api_key: str, model: str,
             messages: list, timeout: int = 600,
             _max_retries: int = 3, _retry_delay: float = 2.0) -> str:
    """调用 OpenAI 兼容的 Chat Completions API。

    对 429（限流）与 5xx（服务端错误）做指数退避重试（默认 3 次），
    解决"全局配额只够一次审核、复核必然失败"的限流问题。
    """
    parsed = urlparse(base_url)
    scheme = parsed.scheme or "https"
    host = parsed.hostname
    port = parsed.port or (443 if scheme == "https" else 80)

    if not host:
        raise RuntimeError(f"无法解析 Base URL: {base_url}")

    path = (parsed.path or "").rstrip("/")
    if "/chat/completions" not in path:
        path = path + "/v1/chat/completions"
    # 避免双 /v1
    path = path.replace("/v1/v1/", "/v1/")

    payload = json.dumps({
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": 4000,  # 推理模型需要足够输出空间
    }, ensure_ascii=False)
    payload_bytes = payload.encode("utf-8")

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json; charset=utf-8",
        "Content-Length": str(len(payload_bytes)),
    }

    import time as _time
    last_error = None
    for attempt in range(_max_retries):
        conn = None
        try:
            if scheme == "https":
                ctx = ssl.create_default_context()
                conn = http.client.HTTPSConnection(host, port, timeout=timeout, context=ctx)
            else:
                conn = http.client.HTTPConnection(host, port, timeout=timeout)

            conn.request("POST", path, payload_bytes, headers)
            res = conn.getresponse()
            data = res.read()

            if res.status == 429 or res.status >= 500:
                # 限流或服务端错误：退避重试
                error_text = data.decode("utf-8", errors="replace")[:300]
                last_error = RuntimeError(f"API 返回 HTTP {res.status}: {error_text}")
                if attempt < _max_retries - 1:
                    delay = _retry_delay * (2 ** attempt)  # 2s, 4s 指数退避
                    _time.sleep(delay)
                    continue
                raise last_error

            if res.status != 200:
                error_text = data.decode("utf-8", errors="replace")[:1000]
                raise RuntimeError(f"API 返回 HTTP {res.status}: {error_text}")

            result = json.loads(data.decode("utf-8"))
            if "choices" in result and len(result["choices"]) > 0:
                message = result["choices"][0].get("message", {})
                content = message.get("content") or ""
                # 推理模型可能把内容放在 reasoning/reasoning_content 里，content 为空
                if not content.strip():
                    reasoning = message.get("reasoning") or message.get("reasoning_content") or ""
                    if reasoning.strip():
                        content = reasoning
                return content

            raise RuntimeError(f"API 响应格式错误: {json.dumps(result)[:500]}")
        finally:
            if conn:
                conn.close()
    raise last_error if last_error else RuntimeError("API 调用失败")


def load_thread(path: str) -> list:
    """加载对话历史"""
    if not os.path.exists(path):
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return []


def save_thread(path: str, messages: list):
    """保存对话历史"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(messages, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="调用外部 LLM 进行评审")
    parser.add_argument("--prompt", help="评审 prompt（直接传入文本）")
    parser.add_argument("--prompt-file", help="从文件读取 prompt")
    parser.add_argument("--thread-file", help="多轮对话文件路径（自动保存/恢复上下文）")
    parser.add_argument("--system", help="System prompt", default="")
    parser.add_argument("--timeout", type=int, default=600, help="请求超时秒数（默认600）")
    args = parser.parse_args()

    load_project_env()
    # 读取环境变量
    api_key = os.environ.get("OPENAI_API_KEY", "")
    base_url = os.environ.get("OPENAI_BASE_URL", "")
    model = os.environ.get("REVIEWER_MODEL_ID", "gpt-4o")

    if not api_key:
        print("错误: 未设置 OPENAI_API_KEY 环境变量。请在 MH Agent 设置页面配置审稿者 Agent 的 API Key。",
              file=sys.stderr)
        sys.exit(1)
    if not base_url:
        print("错误: 未设置 OPENAI_BASE_URL 环境变量。请在 MH Agent 设置页面配置审稿者 Agent 的 Base URL。",
              file=sys.stderr)
        sys.exit(1)

    # 获取 prompt
    prompt = ""
    if args.prompt:
        prompt = args.prompt
    elif args.prompt_file:
        with open(args.prompt_file, "r", encoding="utf-8") as f:
            prompt = f.read()
    elif not sys.stdin.isatty():
        prompt = sys.stdin.read()
    else:
        print("错误: 请通过 --prompt、--prompt-file 或 stdin 提供评审内容。", file=sys.stderr)
        sys.exit(1)

    if not prompt.strip():
        print("错误: prompt 为空。", file=sys.stderr)
        sys.exit(1)

    # 构建消息列表
    messages = []

    # 加载已有的对话历史（多轮）
    if args.thread_file:
        messages = load_thread(args.thread_file)

    # 如果是新对话且有 system prompt，添加到开头
    if not messages and args.system:
        messages.append({"role": "system", "content": args.system})

    # 添加用户消息
    messages.append({"role": "user", "content": prompt})

    # 调用 API
    try:
        response = call_api(base_url, api_key, model, messages, timeout=args.timeout)
    except Exception as e:
        print(f"评审 API 调用失败: {e}", file=sys.stderr)
        sys.exit(1)

    # 保存 assistant 回复到对话历史
    messages.append({"role": "assistant", "content": response})
    if args.thread_file:
        save_thread(args.thread_file, messages)

    # 输出结果
    print(response)


if __name__ == "__main__":
    main()
