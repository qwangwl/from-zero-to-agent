import json
from dataclasses import dataclass
from typing import Iterator, Literal

from core.llm import LLM
from tools import ToolRegistry


@dataclass
class AgentEvent:
    """Agent 运行过程中的一步，由调用方决定如何展示。"""

    kind: Literal["step", "text", "usage", "tool_call", "tool_result", "final"]
    text: str = ""
    step: int | None = None
    usage: dict[str, int] | None = None


class Agent:
    def __init__(self, llm: LLM, system_prompt: str,
                 tool_registry: ToolRegistry, max_step: int = 10):
        if max_step < 1:
            raise ValueError("max_step 必须大于 0。")
        self.llm = llm
        self.system_prompt = system_prompt
        self.tool_registry = tool_registry
        self.max_step = max_step
        self.messages = []

    def run(self, user_input: str) -> str:
        """等待运行结束，返回最终文本。"""
        answer = ""
        for event in self.run_stream(user_input):
            if event.kind == "final":
                answer = event.text
        return answer

    def run_stream(self, user_input: str) -> Iterator[AgentEvent]:
        """逐步返回 Agent 事件；迭代结束后，对话历史已更新。"""
        self.messages.append({"role": "user", "content": user_input})

        for step in range(self.max_step):
            yield AgentEvent(kind="step", step=step + 1)
            response = None
            received_text = False
            for event in self.llm.stream_invoke(
                messages=self.messages,
                instructions=self.system_prompt,
                tools=self.tool_registry.get_schemas(),
            ):
                if event.kind == "text":
                    received_text = True
                    yield AgentEvent(kind="text", text=event.text)
                elif event.kind == "completed":
                    response = event.response

            if response is None:
                raise RuntimeError("模型未返回完整响应。")
            if not received_text and response.text:
                yield AgentEvent(kind="text", text=response.text)
            yield AgentEvent(kind="usage", usage=response.usage)
            self.messages.extend(response.content)

            if not response.tool_calls:
                answer = response.text or "模型未返回文本或工具调用。"
                if not response.text:
                    yield AgentEvent(kind="text", text=answer)
                yield AgentEvent(kind="final", text=answer)
                return

            for call in response.tool_calls:
                arguments = json.loads(call.arguments)
                yield AgentEvent(kind="tool_call", text=f"{call.name}({arguments})")
                result = self.tool_registry.execute(name=call.name, arguments=arguments)
                yield AgentEvent(kind="tool_result", text=str(result.error_info))
                self.messages.append({
                    "type": "function_call_output",
                    "call_id": call.id,
                    "output": result.to_json(),
                })

        message = "已达到模型调用轮次上限，尚未获得最终回答；已执行的文件操作不会自动撤销。"
        yield AgentEvent(kind="text", text=message)
        yield AgentEvent(kind="final", text=message)
