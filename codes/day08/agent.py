import json

from tools import ToolRegistry


class Agent:
    def __init__(self, client, model_id: str, system_prompt: str,
                 tool_registry: ToolRegistry, max_step: int = 10):
        if max_step < 1:
            raise ValueError("max_step 必须大于 0。")
        self.client = client
        self.model_id = model_id
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

            response = self.client.responses.create(
                model=self.model_id,
                instructions=self.system_prompt,
                input=self.messages,
                tools=self.tool_registry.get_schemas(),
            )

            # 保存完整响应项，包括可能存在的 reasoning 项。
            self.messages.extend(response.output)

            function_calls = [
                item 
                for item in response.output 
                if item.type == "function_call"
            ]

            if not function_calls:
                return response.output_text

            for call in function_calls:
                
                arguments = json.loads(call.arguments)
                result = self.tool_registry.execute(call.name, arguments)

                print(f"Tool Call: {call.name}({arguments})")

                self.messages.append({
                    "type": "function_call_output",
                    "call_id": call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })

        return "已达到工具调用轮次上限，任务尚未完成；已执行的文件操作不会自动撤销。"
