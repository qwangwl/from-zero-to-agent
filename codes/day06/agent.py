import json

from openai import OpenAI
from tools import TOOLS, TOOL_REGISTRY


class Agent:
    def __init__(self, client: OpenAI, model_id: str, system_prompt: str, max_step: int = 10):
        self.client = client
        self.model_id = model_id
        self.system_prompt = system_prompt
        self.max_step = max_step
        self.messages = []

    def run(self, user_input: str):
        self.messages.append({
            "role": "user",
            "content": user_input,
        })

        for step in range(self.max_step):
            print(f"--- 循环 {step + 1} ---\n")

            # 3. 将工具描述和当前 Context 一起发送给 LLM。
            response = self.client.responses.create(
                model=self.model_id,
                instructions=self.system_prompt,
                input=self.messages,
                tools=TOOLS,
            )

            # 4. 保存本次 response.output，供下一轮请求继续使用。
            self.messages.extend(response.output)

            function_calls = [
                item
                for item in response.output
                if item.type == "function_call"
            ]

            # 没有 Function Call，说明模型已经生成最终回答
            if not function_calls:
                print(response.output_text)
                break

            for function_call in function_calls:
                arguments = json.loads(function_call.arguments)

                tool = TOOL_REGISTRY.get(function_call.name)

                if tool is None:
                    result = f"Unknown tool: {function_call.name}"
                else:
                    result = tool(**arguments)

                print(
                    f"Tool Call: {function_call.name}({arguments})"
                )

                self.messages.append({
                    "type": "function_call_output",
                    "call_id": function_call.call_id,
                    "output": json.dumps(result, ensure_ascii=False),
                })
