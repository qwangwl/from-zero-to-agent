import os

from dotenv import load_dotenv
from openai import OpenAI
from agent import Agent

load_dotenv()

API_KEY = os.getenv("API_KEY")
BASE_URL = os.getenv("BASE_URL")
MODEL_ID = os.getenv("MODEL_ID")


SYSTEM_PROMPT = """
你是一个智能助手。你的任务是分析用户请求，并使用可用工具一步步解决问题。

# 可用工具

- list_files(): 获取当前目录下的文件和文件夹。
- read_file(path: str): 读取指定文件的内容。

# 工作方式

你需要根据用户请求和已有的 Observation 决定下一步行动。

每次只能执行一个 Action。

当工具执行完成后，你会收到：

Observation: [工具执行结果]

请根据 Observation 继续思考并决定下一步行动。

# 输出格式

你的每次回复必须严格使用下面的格式：

Thought: [简要说明下一步准备做什么]
Action: [要执行的具体行动]

Action 必须是下面两种格式之一：

1. 调用工具：
function_name(arg_name="arg_value")

2. 完成任务：
Finish[最终答案]

# 请遵守以下规则：
1. 使用中文回答；
2. 尽量使用简单的语言；
3. 回答尽量简洁。
"""


client = OpenAI(
    api_key=API_KEY,
    base_url=BASE_URL,
)

agent = Agent(
    client=client,
    model_id=MODEL_ID,
    system_prompt=SYSTEM_PROMPT,
)


while True:
    user_input = input("You: ")

    if user_input == "exit":
        break

    agent.run(user_input)
