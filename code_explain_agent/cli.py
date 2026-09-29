"""Command-line interface for the code explanation agent."""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from urllib.parse import urlparse

from .agent import AgentError, CodeExplainAgent


def build_agent(root: Path, quiet: bool) -> CodeExplainAgent:
    try:
        from openai import OpenAI
    except ImportError as exc:
        raise AgentError("缺少 openai 依赖，请先运行 pip install -r requirements.txt。") from exc

    api_key = (
        os.getenv("CODE_AGENT_API_KEY")
        or os.getenv("DEEPSEEK_API_KEY")
        or os.getenv("DASHSCOPE_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )
    model = os.getenv("CODE_AGENT_MODEL")
    base_url = os.getenv("CODE_AGENT_BASE_URL")
    if not api_key:
        raise AgentError("请设置 CODE_AGENT_API_KEY（也支持 DEEPSEEK_API_KEY、DASHSCOPE_API_KEY 或 OPENAI_API_KEY）。")
    if not model:
        raise AgentError("请设置 CODE_AGENT_MODEL。")

    options = {"api_key": api_key, "max_retries": 2, "timeout": 30.0}
    if base_url:
        options["base_url"] = base_url
    client = OpenAI(**options)
    request_options = {}
    if base_url and urlparse(base_url).hostname == "api.deepseek.com":
        # DeepSeek defaults to thinking mode. This agent retains concise chat
        # history, so use its documented non-thinking mode for tool calls.
        request_options["extra_body"] = {"thinking": {"type": "disabled"}}
    return CodeExplainAgent(
        client, model, root, show_tool_calls=not quiet, request_options=request_options
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="读取项目代码并用大语言模型解释。")
    parser.add_argument("--root", type=Path, default=Path.cwd(), help="允许读取的项目目录，默认为当前目录")
    parser.add_argument("--question", help="只回答这一个问题；不指定则进入交互模式")
    parser.add_argument("--quiet", action="store_true", help="不显示工具调用过程")
    args = parser.parse_args()

    try:
        agent = build_agent(args.root, args.quiet)
    except AgentError as exc:
        parser.exit(2, f"错误：{exc}\n")

    if args.question is not None:
        try:
            print(agent.ask(args.question))
            return 0
        except AgentError as exc:
            parser.exit(1, f"错误：{exc}\n")

    print(f"代码解释 Agent | 项目目录：{agent.root}")
    print("输入问题；/clear 清除会话，/exit 退出。")
    while True:
        try:
            question = input("\n你> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见。")
            return 0
        if question == "/exit":
            return 0
        if question == "/clear":
            agent.clear()
            print("会话已清除。")
            continue
        if not question:
            continue
        try:
            print(f"\nAgent> {agent.ask(question)}")
        except AgentError as exc:
            print(f"错误：{exc}")


if __name__ == "__main__":
    raise SystemExit(main())
