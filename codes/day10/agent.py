import json

from core.llm import LLM
from core.llm_response import LLMResponse
from tools import ToolRegistry


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
        """非流式运行：等待每轮模型响应完成后再显示。"""
        self.messages.append({"role": "user", "content": user_input})

        for step in range(self.max_step):
            print(f"--- 循环 {step + 1} ---")
            response = self.llm.invoke(
                messages=self.messages,
                instructions=self.system_prompt,
                tools=self.tool_registry.get_schemas(),
            )
            self.messages.extend(response.content)

            if response.text:
                print("Assistant:", response.text)
            print("Usage:", response.usage)

            if not response.tool_calls:
                answer = response.text or "模型未返回文本或工具调用。"
                if not response.text:
                    print("Assistant:", answer)
                return answer

            self._execute_tools(response)

        answer = "已达到模型调用轮次上限，尚未获得最终回答；已执行的文件操作不会自动撤销。"
        print("Assistant:", answer)
        return answer

    def run_stream(self, user_input: str) -> str:
        """流式运行：逐段显示文本，并完成后续工具调用。"""
        self.messages.append({"role": "user", "content": user_input})

        for step in range(self.max_step):
            print(f"--- 循环 {step + 1} ---")
            response = None
            printed_text = False
            for event in self.llm.stream_invoke(
                messages=self.messages,
                instructions=self.system_prompt,
                tools=self.tool_registry.get_schemas(),
            ):
                if event.kind == "text" and event.text:
                    # 文本片段一到就显示，无需等待这一轮模型响应结束。
                    if not printed_text:
                        print("Assistant: ", end="", flush=True)
                        printed_text = True
                    print(event.text, end="", flush=True)
                elif event.kind == "completed":
                    # 完整响应用于读取工具调用和用量，不重复打印已显示的文本。
                    response = event.response

            if response is None:
                raise RuntimeError("模型未返回完整响应。")
            print()
            print("Usage:", response.usage)
            # 保存模型原始输出项，供工具结果返回后的下一轮请求使用。
            self.messages.extend(response.content)

            if not response.tool_calls:
                answer = response.text or "模型未返回文本或工具调用。"
                if not response.text:
                    print("Assistant:", answer)
                return answer

            # 工具调用需要完整参数，因此等本轮流结束后统一执行。
            self._execute_tools(response)

        answer = "已达到模型调用轮次上限，尚未获得最终回答；已执行的文件操作不会自动撤销。"
        print("Assistant:", answer)
        return answer

    def _execute_tools(self, response: LLMResponse) -> None:
        """执行本轮所有工具，并将结果加入下一轮模型输入。"""
        for call in response.tool_calls:
            arguments = json.loads(call.arguments)
            print(f"Tool Call: {call.name}({arguments})")
            result = self.tool_registry.execute(name=call.name, arguments=arguments)

            self.messages.append({
                "type": "function_call_output",
                "call_id": call.id,
                "output": result.to_json(),
            })
