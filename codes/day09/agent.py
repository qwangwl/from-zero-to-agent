import json
from core.llm import LLM
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
        self.messages.append({
            "role": "user", 
             "content": user_input
        })

        for step in range(self.max_step):
            print(f"--- 循环 {step + 1} ---")

            response = self.llm.generate(
                messages=self.messages,
                instructions=self.system_prompt,
                tools=self.tool_registry.get_schemas(),
            )
            self.messages.extend(response.content)

            if not response.tool_calls:
                return response.text or "模型未返回文本或工具调用。"
            
            print("Usage:", response.usage)
            print("Assistant:", response.text)

            for call in response.tool_calls:
                arguments = json.loads(call.arguments)
                result = self.tool_registry.execute(name=call.name, arguments=arguments)
                print(f"Tool Call: {call.name}({arguments})")

                self.messages.append({
                    "type": "function_call_output",
                    "call_id": call.id,
                    "output": result.to_json(),
                })

        return "已达到模型调用轮次上限，尚未获得最终回答；已执行的文件操作不会自动撤销。"
