import json
import tempfile
import unittest
from unittest.mock import patch
from pathlib import Path
from types import SimpleNamespace

import httpx
from openai import OpenAI

from code_explain_agent.agent import AgentError, CodeExplainAgent, read_file
from code_explain_agent.cli import build_agent


class FakeMessage:
    def __init__(self, content=None, tool_calls=None):
        self.content = content
        self.tool_calls = tool_calls

    def model_dump(self, exclude_none=True):
        result = {"role": "assistant"}
        if self.content is not None:
            result["content"] = self.content
        if self.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.function.name,
                        "arguments": call.function.arguments,
                    },
                }
                for call in self.tool_calls
            ]
        return result


class FakeCompletions:
    def __init__(self, messages):
        self.responses = list(messages)
        self.requests = []

    def create(self, **kwargs):
        self.requests.append(kwargs)
        return SimpleNamespace(choices=[SimpleNamespace(message=self.responses.pop(0))])


class ReadFileTests(unittest.TestCase):
    def test_reads_with_line_numbers(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("x = 1\nprint(x)\n", encoding="utf-8")
            result = read_file(root, "demo.py")
            self.assertIn("文件：demo.py", result)
            self.assertIn("   2: print(x)", result)

    def test_rejects_path_outside_project(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "project"
            root.mkdir()
            (Path(directory) / "secret.py").write_text("secret", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "项目目录内"):
                read_file(root, "../secret.py")

    def test_missing_file_returns_clear_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "文件不存在"):
                read_file(Path(directory), "missing.py")


class AgentLoopTests(unittest.TestCase):
    def test_deepseek_configuration_disables_thinking(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.dict("os.environ", {
                "CODE_AGENT_API_KEY": "test-key",
                "CODE_AGENT_BASE_URL": "https://api.deepseek.com",
                "CODE_AGENT_MODEL": "deepseek-flash",
            }):
                agent = build_agent(Path(directory), quiet=True)

        self.assertEqual(agent.model, "deepseek-flash")
        self.assertEqual(
            agent.request_options,
            {"extra_body": {"thinking": {"type": "disabled"}}},
        )

    def test_tool_result_is_sent_back_to_model(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("x = 1\n", encoding="utf-8")
            call = SimpleNamespace(
                id="call_1",
                function=SimpleNamespace(name="read_file", arguments=json.dumps({"path": "demo.py"})),
            )
            completions = FakeCompletions([
                FakeMessage(tool_calls=[call]),
                FakeMessage(content="第 1 行把 1 赋给 x。"),
            ])
            client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
            agent = CodeExplainAgent(client, "test-model", root, show_tool_calls=False)

            answer = agent.ask("解释 demo.py")

            self.assertIn("第 1 行", answer)
            self.assertEqual(len(completions.requests), 2)
            second_messages = completions.requests[1]["messages"]
            self.assertEqual(second_messages[-1]["role"], "tool")
            self.assertIn("   1: x = 1", second_messages[-1]["content"])
            self.assertEqual(agent.last_file, "demo.py")

    def test_empty_question_does_not_call_model(self):
        completions = FakeCompletions([])
        client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
        with tempfile.TemporaryDirectory() as directory:
            agent = CodeExplainAgent(client, "test-model", Path(directory), show_tool_calls=False)
            with self.assertRaises(AgentError):
                agent.ask("   ")
        self.assertEqual(completions.requests, [])

    def test_openai_compatible_request_round_trip(self):
        requests = []

        def handler(request):
            payload = json.loads(request.content)
            requests.append(payload)
            if len(requests) == 1:
                message = {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "id": "call_1",
                        "type": "function",
                        "function": {"name": "read_file", "arguments": '{"path":"demo.py"}'},
                    }],
                }
                finish_reason = "tool_calls"
            else:
                message = {"role": "assistant", "content": "demo.py 第 1 行定义了 x。"}
                finish_reason = "stop"
            return httpx.Response(200, json={
                "id": "chatcmpl-test",
                "object": "chat.completion",
                "created": 1,
                "model": "test-model",
                "choices": [{"index": 0, "message": message, "finish_reason": finish_reason}],
            })

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "demo.py").write_text("x = 1\n", encoding="utf-8")
            http_client = httpx.Client(transport=httpx.MockTransport(handler))
            client = OpenAI(api_key="test-key", base_url="https://example.test/v1", http_client=http_client)
            agent = CodeExplainAgent(
                client,
                "test-model",
                root,
                show_tool_calls=False,
                request_options={"extra_body": {"thinking": {"type": "disabled"}}},
            )
            self.assertIn("第 1 行", agent.ask("解释 demo.py"))

        self.assertEqual(len(requests), 2)
        self.assertEqual(requests[0]["thinking"], {"type": "disabled"})
        self.assertEqual(requests[1]["thinking"], {"type": "disabled"})
        self.assertEqual(requests[0]["tools"][0]["function"]["name"], "read_file")
        self.assertEqual(requests[1]["messages"][-1]["role"], "tool")
        self.assertIn("x = 1", requests[1]["messages"][-1]["content"])


if __name__ == "__main__":
    unittest.main()
