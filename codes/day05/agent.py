from tools import list_files, read_file

class Agent:
    def __init__(self, client, model_id, system_prompt):
        self.client = client
        self.model_id = model_id
        self.system_prompt = system_prompt

    def run(self, user_input: str):
        messages = [{
            "role": "user",
            "content": user_input,
        }]

        for i in range(10):
            print(f"--- 循环 {i + 1} ---\n")

            # 将当前 Context 发送给 LLM，让 LLM 决定下一步 Action
            response = self.client.responses.create(
                model=self.model_id,
                instructions=self.system_prompt,
                input=messages,
            )

            assistant_message = response.output_text

            messages.append({
                "role": "assistant",
                "content": assistant_message,
            })

            print()
            print(assistant_message)
            print()

            # 解析 LLM 返回的 Action
            action = self.parse_action(assistant_message)

            # 如果 LLM 返回 Finish，提取最终答案并结束本次任务
            if self.is_finish(action):
                answer = self.parse_finish(action)

                print("任务完成:", answer)
                print()

                break

            # 执行 Tool
            observation = None

            if action == "list_files()":
                observation = list_files()

            if action.startswith("read_file("):
                path = action.split('path="')[1].split('"')[0]
                observation = read_file(path)

            # 将 Tool Result 作为 Observation 放回 Context
            messages.append({
                "role": "user",
                "content": f"Observation: {observation}",
            })

    def parse_action(self, response: str):
        marker = "Action:"
        marker_index = response.find(marker)

        if marker_index == -1:
            return None

        return response[marker_index + len(marker):].strip()

    def is_finish(self, action: str):
        return action.startswith("Finish[") and action.endswith("]")

    def parse_finish(self, action: str):
        return action[len("Finish["):-1]
